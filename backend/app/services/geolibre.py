"""Build GeoLibre launch links from public, browser-readable distributions."""

import re
from collections import Counter
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, quote, unquote, urlsplit

# Public file collections checked in the hosted viewer. Keep these scoped to
# dataset paths on providers that serve other kinds of content on the same host.
PUBLIC_COLLECTIONS = {
    "assets.geolibre.app": "/data/",
    "data.source.coop": "/giswqs/opengeos/",
    "geobtaa-assets-prod.s3.us-east-2.amazonaws.com": "/store/asset/",
}
FORMAT_BY_URI = {
    "http://geojson.org/geojson-spec.html": "GeoJSON",
    "https://github.com/protomaps/PMTiles": "PMTiles",
    "https://github.com/cogeotiff/cog-spec": "COG",
}
FILE_SUFFIXES = {
    "GeoJSON": {".geojson", ".json"},
    "GeoParquet": {".parquet", ".geoparquet"},
    "PMTiles": {".pmtiles"},
    "COG": {".tif", ".tiff"},
}
DOWNLOAD_FORMATS = {name.casefold(): name for name in FILE_SUFFIXES}
DOWNLOAD_FORMATS["cloud optimized geotiff"] = "COG"


def _eligible_file(url: str, format_name: str) -> bool:
    if (
        url != url.strip()
        or not url.isprintable()
        or "\\" in url
        or re.search(r"%(?![0-9a-fA-F]{2})", url)
    ):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False

    # Match the entire authority to exclude userinfo, custom ports and lookalike hosts.
    prefix = PUBLIC_COLLECTIONS.get(parts.netloc.lower())
    path = unquote(parts.path)
    if parts.scheme != "https" or not prefix or not path.startswith(prefix) or parts.fragment:
        return False
    if ".." in path.split("/") or "\\" in path or not path.isprintable():
        return False
    # Forward only ordinary dataset selectors. Credentials and expiring signatures
    # should never become part of the external launch URL.
    if any(
        key.lower() not in {"layer", "version", "v", "bbox", "limit"}
        for key, _ in parse_qsl(parts.query, keep_blank_values=True)
    ):
        return False
    return PurePosixPath(parts.path).suffix.lower() in FILE_SUFFIXES[format_name]


def geolibre_links(references: dict) -> list[dict[str, str]]:
    candidates = set()
    for uri, value in references.items():
        for entry in value if isinstance(value, list) else [value]:
            url = entry.get("url") if isinstance(entry, dict) else entry
            label = entry.get("label") if isinstance(entry, dict) else None
            label = label.strip() if isinstance(label, str) else ""
            format_name = FORMAT_BY_URI.get(uri)
            if uri == "http://schema.org/downloadUrl":
                format_name = DOWNLOAD_FORMATS.get(label.casefold())
            if format_name and isinstance(url, str) and _eligible_file(url, format_name):
                # Prefer a layer label over a generic format label for the same URL.
                layer = "" if label.casefold() in DOWNLOAD_FORMATS else label
                candidates.add((format_name, layer, url))

    unique = {}
    for fmt, layer, url in sorted(candidates, key=lambda item: (not item[1], *item)):
        unique.setdefault(url, (fmt, layer))

    counts = Counter(fmt for fmt, _ in unique.values())
    numbers = Counter()
    links = []
    for url, (fmt, layer) in sorted(unique.items(), key=lambda item: (*item[1], item[0])):
        numbers[fmt] += 1
        label = f"{fmt} {numbers[fmt]}" if counts[fmt] > 1 else fmt
        if layer:
            label += f" — {layer}"
        links.append(
            {"label": label, "url": f"https://web.geolibre.app/?data={quote(url, safe='')}"}
        )
    return links
