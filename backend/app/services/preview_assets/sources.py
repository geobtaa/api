"""Pure source selection and service request construction."""

import json
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from shapely.geometry import shape

from .geometry import metadata_coverage
from .models import Outcome, PreviewError

COG = "https://github.com/cogeotiff/cog-spec"
PMTILES = "https://github.com/protomaps/PMTiles"
INDEX = "https://openindexmaps.org"
WMS = "http://www.opengis.net/def/serviceType/ogc/wms"


def retryable_attempts(attempts):
    return any(
        attempt.get("status") == "unavailable"
        and re.search(
            r"provider busy|timed? ?out|timeout|connection reset|HTTP (429|500|502|503|504)\b",
            attempt.get("detail", ""),
            re.I,
        )
        for attempt in attempts
    )


@dataclass(frozen=True)
class Source:
    url: str
    kind: str
    layer: str | None = None


def references(record):
    raw = record.get("dct_references_s") or {}
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, dict):
        raise PreviewError(Outcome.INVALID, "References must be an object")
    assigned = {}
    for item in record.get("_preview_sources", []):
        if item.get("uri") and item.get("url"):
            assigned.setdefault(item["uri"], []).append(item["url"])
    raw = {**raw, **assigned}
    return raw


def urls(value):
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, dict):
        return urls(value.get("url"))
    if isinstance(value, list):
        return [url for item in value for url in urls(item)]
    return []


def discover(record):
    refs = references(record)
    candidates = []
    for key, kind in (
        (COG, "cog"),
        (PMTILES, "pmtiles"),
        (INDEX, "index"),
        ("http://iiif.io/api/image", "iiif"),
        ("http://iiif.io/api/presentation#manifest", "iiif-manifest"),
        (WMS, "wms"),
    ):
        candidates.extend(
            Source(
                url, kind, record.get("gbl_wxsIdentifier_s") or record.get("gbl_wxsidentifier_s")
            )
            for url in urls(refs.get(key))
        )
    for key, value in refs.items():
        if key.startswith("urn:x-esri:serviceType:ArcGIS#"):
            candidates.extend(Source(url, "arcgis") for url in urls(value))
    for key in (
        "http://geojson.org/geojson-spec.html",
        "http://schema.org/downloadUrl",
        "https://schema.org/downloadUrl",
    ):
        candidates.extend(Source(url, "download") for url in urls(refs.get(key)))
    return candidates


def query_url(url, params):
    parts = urlsplit(url)
    replaced = {key.lower() for key in params}
    pairs = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in replaced]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode([*pairs, *params.items()]), "")
    )


def iiif_manifest_image(manifest):
    """Resolve an embedded v2/v3 painting image without following page graphs."""
    sequences = manifest.get("sequences", [])
    canvases = sequences[0].get("canvases", []) if sequences else manifest.get("items", [])
    if not canvases:
        raise PreviewError(Outcome.NEEDS_REVIEW, "IIIF manifest has no embedded canvases")
    canvas = canvases[0]
    if sequences:
        bodies = [annotation.get("resource") for annotation in canvas.get("images", [])]
    else:
        bodies = [
            annotation.get("body")
            for page in canvas.get("items", [])
            for annotation in page.get("items", [])
            if annotation.get("motivation") == "painting"
        ]
    images = [
        body
        for body in bodies
        if isinstance(body, dict)
        and (body.get("type") or body.get("@type")) in {"Image", "dctypes:Image"}
    ]
    if len(images) != 1 or len(bodies) != 1:
        raise PreviewError(Outcome.NEEDS_REVIEW, "IIIF canvas requires image composition or choice")
    body = images[0]
    services = body.get("service", [])
    services = [services] if isinstance(services, dict) else services
    for service in services:
        identifier = service.get("id") or service.get("@id")
        if identifier and (
            service.get("type") in {"ImageService2", "ImageService3"}
            or "iiif.io/api/image" in str(service.get("@context", ""))
            or "iiif.io/api/image" in str(service.get("profile", ""))
        ):
            return Source(identifier, "iiif"), len(canvases) > 1
    identifier = body.get("id") or body.get("@id")
    if not identifier:
        raise PreviewError(Outcome.NEEDS_REVIEW, "IIIF painting image URL missing")
    return Source(identifier, "image"), len(canvases) > 1


def wms_image(source: Source, record, version=None, crs=None):
    if not source.layer:
        raise PreviewError(Outcome.NEEDS_REVIEW, "WMS layer identifier missing")
    coverage = metadata_coverage(record)
    if not coverage.geometry:
        raise PreviewError(Outcome.NEEDS_REVIEW, "WMS extent missing")
    west, south, east, north = shape(coverage.geometry).bounds
    configured = {key.upper(): value for key, value in parse_qsl(urlsplit(source.url).query)}
    version = version or configured.get("VERSION", "1.3.0")
    crs = crs or configured.get("CRS") or configured.get("SRS") or "EPSG:4326"
    if version not in {"1.1.1", "1.3.0"}:
        raise PreviewError(Outcome.UNSUPPORTED, "Unsupported WMS version")
    if crs.upper() not in {"EPSG:4326", "CRS:84", "EPSG:3857"}:
        raise PreviewError(Outcome.NEEDS_REVIEW, "WMS CRS requires a configured adapter")
    if crs.upper() == "EPSG:3857":
        from rasterio.warp import transform_bounds

        west, south, east, north = transform_bounds("EPSG:4326", crs, west, south, east, north)
    bounds = (
        (south, west, north, east)
        if version == "1.3.0" and crs.upper() == "EPSG:4326"
        else (west, south, east, north)
    )
    return query_url(
        source.url,
        {
            "SERVICE": "WMS",
            "VERSION": version,
            "REQUEST": "GetMap",
            "LAYERS": source.layer,
            "STYLES": "",
            "CRS" if version == "1.3.0" else "SRS": crs,
            "BBOX": ",".join(map(str, bounds)),
            "WIDTH": 512,
            "HEIGHT": 512,
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE",
        },
    )


def arcgis_export(url, metadata):
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    selected_layer = None
    if path.rsplit("/", 1)[-1].isdigit():
        path, selected_layer = path.rsplit("/", 1)
    image = path.lower().endswith("/imageserver")
    if not image and not path.lower().endswith("/mapserver"):
        raise PreviewError(
            Outcome.UNSUPPORTED, "Feature service requires a bounded feature adapter"
        )
    extent = metadata.get("extent") or metadata.get("fullExtent") or metadata.get("initialExtent")
    if not extent:
        raise PreviewError(Outcome.NEEDS_REVIEW, "Service extent missing")
    sr = extent.get("spatialReference", {})
    spatial_ref = sr.get("latestWkid") or sr.get("wkid") or sr.get("wkt")
    if not spatial_ref:
        raise PreviewError(Outcome.NEEDS_REVIEW, "Service CRS missing")
    params = {
        "f": "image",
        "bbox": ",".join(str(extent[k]) for k in ("xmin", "ymin", "xmax", "ymax")),
        "bboxSR": spatial_ref,
        "imageSR": 3857,
        "size": "512,512",
        "format": "png32",
        "transparent": "true",
    }
    if selected_layer:
        params["layers"] = "show:" + selected_layer
    endpoint = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            path + ("/exportImage" if image else "/export"),
            parts.query,
            "",
        )
    )
    return query_url(endpoint, params)
