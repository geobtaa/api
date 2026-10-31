"""Optional private MapLibre renderer; storage remains in StaticMapService."""

import hashlib
import io
import json
import os
import time
import uuid

import requests
from PIL import Image

from app.services.visual_asset_cache import (
    cache_visual_asset,
    durable_visual_asset_enabled,
    get_durable_visual_asset,
    get_durable_visual_asset_hash_for_resource,
    get_durable_visual_asset_hash_for_signature,
)


def renderer_url():
    return os.getenv("STATIC_MAP_RENDERER_URL", "http://map_renderer:8080").rstrip("/")


def revision():
    # Bump when styles, tiles, fonts, or renderer settings change.
    return os.getenv("STATIC_MAP_RENDER_REVISION", "openfreemap-liberty-native-v1")


def signature(value):
    return hashlib.sha256(
        json.dumps(
            [
                revision(),
                os.getenv("STATIC_MAP_STYLE_URL", "https://tiles.openfreemap.org/styles/liberty"),
                "maplibre-native-6.4.1",
                value,
            ],
            sort_keys=True,
        ).encode()
    ).hexdigest()


def _generate_uncached(
    service,
    resource_id,
    geometry=None,
    *,
    overlay=True,
    center=None,
    zoom=None,
    source_signature=None,
    hydrate_asset=True,
):
    spec = {"width": service.map_width, "height": service.map_height}
    no_geometry = False
    if center is not None:
        spec.update(center=center, leafletZoom=zoom)
    else:
        bounds = service._parse_geometry_to_bbox(geometry)
        # Preserve dateline-crossing envelopes rather than interpreting them as missing data.
        import re

        if isinstance(geometry, str) and geometry.strip().upper().startswith("ENVELOPE"):
            values = re.findall(r"[-+]?(?:\d*\.)?\d+(?:[eE][-+]?\d+)?", geometry)
            if len(values) == 4:
                west, east, north, south = map(float, values)
                if -180 <= east < west <= 180:
                    bounds = (west, south, east + 360, north)
        no_geometry = not bounds or service._is_global_bbox(bounds)
        if no_geometry:
            spec.update(center=[0, 0], leafletZoom=1)
        elif bounds[0] == bounds[2] and bounds[1] == bounds[3]:
            spec.update(
                center=[bounds[0], max(-85.05112878, min(85.05112878, bounds[1]))], leafletZoom=12
            )
        else:
            west, south, east, north = bounds
            south = max(-85.05112878, min(85.05112878, south))
            north = max(-85.05112878, min(85.05112878, north))
            # Flat lines and polar extents still need an area for camera fitting.
            if east - west < 0.001:
                west, east = west - 0.001, east + 0.001
            if north - south < 0.001:
                south, north = max(-85.05112878, south - 0.001), min(85.05112878, north + 0.001)
            bounds = (west, south, east, north)
            spec["bounds"] = list(bounds)
        if overlay and not no_geometry:
            geojson = service._geometry_to_geojson_dict(geometry)
            if geojson is None:
                w, s, e, n = bounds
                geojson = {
                    "type": "Polygon",
                    "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
                }
            spec["geometry"] = geojson
    for attempt in range(3):
        response = requests.post(renderer_url() + "/render", json=spec, timeout=(5, 75))
        if response.status_code not in (429, 503) or attempt == 2:
            break
        time.sleep(3 * (attempt + 1))
    response.raise_for_status()
    data = response.content
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Renderer did not return PNG")
    with Image.open(io.BytesIO(data)) as image:
        if image.size != (service.map_width, service.map_height):
            raise ValueError("Renderer returned incorrect dimensions")
        image.verify()
    if overlay and no_geometry:
        image = service._overlay_no_data_symbol(Image.open(io.BytesIO(data)))
        output = io.BytesIO()
        image.save(output, "PNG")
        data = output.getvalue()
    variant = service.geometry_variant() if overlay else service.basemap_variant()
    source_signature = source_signature or service.geometry_signature(geometry)
    digest = service.materialize_asset_sync(
        resource_id,
        variant=variant,
        map_bytes=data,
        source_signature=source_signature,
        hydrate_asset=hydrate_asset,
    )
    if not digest or (
        durable_visual_asset_enabled() and get_durable_visual_asset(digest) != (data, "image/png")
    ):
        raise RuntimeError("Could not persist rendered asset")
    if (
        durable_visual_asset_enabled()
        and not resource_id.startswith("institution:")
        and (
            get_durable_visual_asset_hash_for_resource(
                resource_id, asset_kind=variant, source_signature=source_signature
            )
            != digest
        )
    ):
        raise RuntimeError("Could not link rendered asset")
    if hydrate_asset:
        # materialize_asset_sync already guarantees durable storage or a usable
        # hot asset. Mutable-key hydration must not hide a committed image.
        cache_visual_asset(
            service.map_cache,
            service._cache_key(resource_id, variant=variant, source_signature=source_signature),
            data,
        )
    return data


def reuse_geometry(
    service, resource_id, geometry, *, overlay=True, source_signature=None, hydrate_asset=True
):
    variant = service.geometry_variant() if overlay else service.basemap_variant()
    source_signature = source_signature or service.geometry_signature(geometry)
    digest = get_durable_visual_asset_hash_for_signature(variant, source_signature)
    if not digest:
        return None
    data = service.get_cached_asset_sync(digest)
    if not data:
        return None
    linked = service.materialize_asset_sync(
        resource_id,
        variant=variant,
        map_bytes=data,
        source_signature=source_signature,
        hydrate_asset=hydrate_asset,
    )
    if (
        linked != digest
        or get_durable_visual_asset_hash_for_resource(
            resource_id, asset_kind=variant, source_signature=source_signature
        )
        != digest
    ):
        raise RuntimeError("Could not link reusable map")
    return data


def generate(service, resource_id, geometry=None, **kwargs):
    # Campus cameras use a separate identity and do not have resource foreign keys.
    if resource_id.startswith("institution:") or kwargs.get("center") is not None:
        return _generate_uncached(service, resource_id, geometry, **kwargs)
    reuse_args = {
        key: kwargs[key]
        for key in ("overlay", "source_signature", "hydrate_asset")
        if key in kwargs
    }
    data = reuse_geometry(service, resource_id, geometry, **reuse_args)
    if data:
        return data
    sig = kwargs.get("source_signature") or service.geometry_signature(geometry)
    kind = service.geometry_variant() if kwargs.get("overlay", True) else service.basemap_variant()
    lock = f"native-render:{kind}:{sig}"
    token = uuid.uuid4().hex
    if not service.map_cache.set(lock, token, nx=True, ex=120):
        raise RuntimeError("Identical geometry is already rendering; retry")
    try:
        # Another worker may have finished between the first lookup and locking.
        data = reuse_geometry(service, resource_id, geometry, **reuse_args)
        return data or _generate_uncached(service, resource_id, geometry, **kwargs)
    finally:
        service.map_cache.eval(
            "if redis.call('get',KEYS[1]) == ARGV[1] then "
            "return redis.call('del',KEYS[1]) else return 0 end",
            1,
            lock,
            token,
        )


def pregenerate_thumbnail(resource_id, geometry, *, hydrate_asset=True):
    from app.services.static_map_service import StaticMapService

    service = StaticMapService(384, 288)
    return generate(service, resource_id, geometry, hydrate_asset=hydrate_asset)
