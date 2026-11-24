"""Build native GeoLibre projects for cataloged, browser-readable raster services."""

import hashlib
import math
import os
import re
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

WMS = "http://www.opengis.net/def/serviceType/ogc/wms"
WMTS = "http://www.opengis.net/def/serviceType/ogc/wmts"
CORNELL_WMTS = "https://cugir.library.cornell.edu/geoserver/gwc/service/wmts"
WMS_ENDPOINTS = {
    "https://cugir.library.cornell.edu/geoserver/cugir/wms",
    "https://geoservices.lib.berkeley.edu/geoserver/wms",
}


def _source(uri, url, identifier):
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


def raster_projects(references, identifier, bbox, title):
    if not bbox or not (WMS in references or WMTS in references):
        return {}
    west, south, east, north = bounds = [float(n) for n in bbox.split(",")]
    if not (-180 <= west < east <= 180 and -85.05113 <= south < north <= 85.05113):
        return {}
    # Fit the extent into a 512-pixel map at startup, including a small margin.
    lat_span = math.degrees(
        math.asinh(math.tan(math.radians(north))) - math.asinh(math.tan(math.radians(south)))
    )
    view = dict(
        center=[(west + east) / 2, (south + north) / 2],
        zoom=max(0, min(18, math.log2(360 / max(east - west, lat_span)) - 0.25)),
        pitch=0,
        bearing=0,
    )
    projects = {}
    for uri in (WMS, WMTS):
        kind = uri.rsplit("/", 1)[1]
        entries = references.get(uri, [])
        for entry in entries if isinstance(entries, list) else [entries]:
            url = entry.get("url") if isinstance(entry, dict) else entry
            source = _source(uri, url, identifier)
            if not source:
                continue
            key = kind + "-" + hashlib.sha256(source["tiles"][0].encode()).hexdigest()[:20]
            name = (
                (entry.get("label") if isinstance(entry, dict) else None) or title or kind.upper()
            )
            source.update(type="raster", tileSize=256, bounds=bounds)
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
                mapView=view,
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
