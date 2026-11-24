"""Build native GeoLibre projects for cataloged, browser-readable raster services."""

import asyncio
import hashlib
import math
import os
import re
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

from app.services import ogc_capabilities

WMS = "http://www.opengis.net/def/serviceType/ogc/wms"
WMTS = "http://www.opengis.net/def/serviceType/ogc/wmts"
CORNELL_WMTS = "https://cugir.library.cornell.edu/geoserver/gwc/service/wmts"
WMS_ENDPOINTS = {
    "https://cugir.library.cornell.edu/geoserver/cugir/wms",
    "https://geoservices.lib.berkeley.edu/geoserver/wms",
}


def _legacy_source(uri, url, identifier):
    if not isinstance(url, str) or not url.isprintable() or url != url.strip():
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    endpoint = parts._replace(query="").geturl()
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    query = {key.lower(): value for key, value in pairs}
    if len(query) != len(pairs) or query.keys() - {
        "request",
        "layers",
        "layer",
        "service",
        "version",
    }:
        return None
    layer = query.get("layers") or query.get("layer") or identifier
    if not isinstance(layer, str) or not re.fullmatch(r"[\w.:-]+", layer):
        return None
    if uri == WMS and endpoint in WMS_ENDPOINTS:
        params = dict(
            SERVICE="WMS",
            REQUEST="GetMap",
            VERSION="1.1.1",
            LAYERS=layer,
            STYLES="",
            FORMAT="image/png",
            TRANSPARENT="TRUE",
            SRS="EPSG:3857",
            WIDTH=256,
            HEIGHT=256,
        )
        tile = endpoint + "?" + urlencode(params) + "&BBOX={bbox-epsg-3857}"
        return dict(
            url=endpoint,
            layers=layer,
            styles="",
            format="image/png",
            transparent=True,
            version="1.1.1",
            tiles=[tile],
        )
    if uri == WMTS and endpoint == CORNELL_WMTS:
        # Cornell advertises EPSG:3857 with individual matrices named EPSG:900913:<zoom>.
        if ":" not in layer:
            layer = "cugir:" + layer
        params = dict(
            SERVICE="WMTS",
            REQUEST="GetTile",
            VERSION="1.0.0",
            LAYER=layer,
            STYLE="",
            FORMAT="image/png",
            TILEMATRIXSET="EPSG:3857",
        )
        tile = (
            endpoint
            + "?"
            + urlencode(params)
            + "&TILEMATRIX=EPSG%3A900913%3A{z}&TILEROW={y}&TILECOL={x}"
        )
        return dict(url=tile, tiles=[tile])
    return None


def _entries(references, identifier):
    for uri in (WMS, WMTS):
        entries = references.get(uri, [])
        for entry in entries if isinstance(entries, list) else [entries]:
            url = entry.get("url") if isinstance(entry, dict) else entry
            request = ogc_capabilities.request_for(uri, url, identifier)
            if request:
                yield uri, entry, url, request


async def capabilities_for(references, identifier):
    urls = sorted({request[0] for _, _, _, request in _entries(references, identifier)})
    return dict(zip(urls, await asyncio.gather(*(ogc_capabilities.document(url) for url in urls))))


def _bounds(values):
    try:
        west, south, east, north = map(float, values)
    except (TypeError, ValueError):
        return None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        return None
    south, north = max(-85.05113, south), min(85.05113, north)
    return [west, south, east, north] if south < north else None


def _map_view(bounds):
    west, south, east, north = bounds
    # Fit the extent into a 512-pixel map at startup, including a small margin.
    lat_span = math.degrees(
        math.asinh(math.tan(math.radians(north))) - math.asinh(math.tan(math.radians(south)))
    )
    return dict(
        center=[(west + east) / 2, (south + north) / 2],
        zoom=max(0, min(18, math.log2(360 / max(east - west, lat_span)) - 0.25)),
        pitch=0,
        bearing=0,
    )


def raster_projects(references, identifier, bbox, title, documents=None):
    projects = {}
    for uri, entry, url, (cap_url, selector) in _entries(references, identifier):
        # Keep the original project URLs usable, including during a provider outage.
        legacy = _legacy_source(uri, url, identifier)
        doc = (
            documents.get(cap_url)
            if documents is not None
            else ogc_capabilities.cached_document(cap_url)
        )
        discovered = ogc_capabilities.discover(doc, selector)
        if discovered:
            kind, source = discovered
        elif legacy and doc is None:
            kind, source = uri.rsplit("/", 1)[1], legacy
        else:
            continue
        identity = legacy["tiles"][0] if legacy else f"{cap_url}#{selector or ''}"
        key = kind + "-" + hashlib.sha256(identity.encode()).hexdigest()[:20]
        name = (entry.get("label") if isinstance(entry, dict) else None) or title or kind.upper()
        bounds = _bounds(bbox.split(",")) if bbox else None
        bounds = bounds or _bounds(source.get("bounds"))
        if not bounds:
            continue
        view = _map_view(bounds)
        source.update(type="raster", bounds=bounds)
        source.setdefault("tileSize", 256)
        # MapLibre chooses source zoom relative to a 512-pixel tile.
        offset = math.log2(512 / source["tileSize"])
        zoom = max(
            source.get("minzoom", 0) - offset, min(view["zoom"], source.get("maxzoom", 24) - offset)
        )
        layer = dict(
            id=key,
            type=kind,
            name=name,
            visible=True,
            opacity=1,
            style={},
            source=source,
            metadata={"service": kind},
        )
        projects[key] = dict(
            version="0.1.0",
            name=title or name,
            mapView={**view, "zoom": zoom},
            basemapStyleUrl="https://tiles.openfreemap.org/styles/positron",
            basemapVisible=True,
            basemapOpacity=1,
            styles={},
            layers=[layer],
        )
    return projects


def raster_links(resource_id, projects):
    base = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/").removesuffix("/api/v1")
    links = []
    for key, project in sorted(projects.items()):
        layer = project["layers"][0]
        label = layer["type"].upper()
        if sum(p["layers"][0]["type"] == layer["type"] for p in projects.values()) > 1:
            label += " — " + (layer["source"].get("layers") or layer["name"])
        url = f"{base}/api/v1/resources/{quote(resource_id, safe='')}/geolibre/{key}.geolibre.json"
        links.append(
            {"label": label, "url": "https://web.geolibre.app/?" + urlencode({"url": url})}
        )
    return links
