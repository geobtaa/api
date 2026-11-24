"""Discover browser raster tile templates from public OGC capabilities documents."""

import asyncio
import ipaddress
import math
import re
import socket
from collections import OrderedDict
from time import monotonic
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

import aiohttp
from lxml import etree

XLINK = "{http://www.w3.org/1999/xlink}href"
FORMATS = ("image/png", "image/jpeg", "image/webp")
MAX_DOCUMENT = 12 * 1024 * 1024
_cache = OrderedDict()
_pending = {}
_slots = asyncio.Semaphore(6)


def _public_address(address):
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast and not getattr(ip, "ipv4_mapped", None)


def _public_url(url):
    try:
        p = urlsplit(url)
        if (
            p.scheme != "https"
            or not p.hostname
            or p.username is not None
            or p.password is not None
            or p.port not in (None, 443)
            or p.fragment
            or "\\" in url
            or not url.isprintable()
            or url != url.strip()
        ):
            return False
        try:
            return _public_address(p.hostname)
        except ValueError:
            return (
                not re.fullmatch(
                    r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*\.?", p.hostname, re.I
                )
                and "." in p.hostname
                and re.fullmatch(r"[A-Za-z0-9.-]+", p.hostname)
                and not p.hostname.lower().rstrip(".").endswith((".local", ".localhost"))
            )
    except (TypeError, ValueError):
        return False


class _PublicResolver(aiohttp.resolver.ThreadedResolver):
    async def resolve(self, host, port=0, family=socket.AF_UNSPEC):
        addresses = await super().resolve(host, port, family)
        if not addresses or not all(_public_address(a["host"]) for a in addresses):
            raise OSError("Expected a public OGC service")
        return addresses


def request_for(uri, url, identifier):
    """Keep dataset selectors but exclude credentials and arbitrary query parameters."""
    if not isinstance(url, str) or not _public_url(url):
        return None
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    query = {k.lower(): v for k, v in pairs}
    if len(query) != len(pairs) or query.keys() - {
        "service",
        "version",
        "request",
        "layers",
        "layer",
        "map",
    }:
        return None
    layer = query.get("layers") or query.get("layer") or identifier
    if layer and (not isinstance(layer, str) or not layer.isprintable() or len(layer) > 512):
        return None
    params = [(k, v) for k, v in pairs if k.lower() == "map"]
    if not parts.path.lower().endswith(".xml"):
        params += [("SERVICE", uri.rsplit("/", 1)[-1].upper()), ("REQUEST", "GetCapabilities")]
        if query.get("version"):
            params.append(("VERSION", query["version"]))
    return urlunsplit(parts._replace(query=urlencode(params))), layer


async def _download(url):
    try:
        async with (
            asyncio.timeout(12),
            _slots,
            aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(resolver=_PublicResolver()),
                auto_decompress=False,
                headers={"Accept-Encoding": "identity"},
            ) as session,
        ):
            for _ in range(4):
                async with session.get(url, allow_redirects=False) as response:
                    if response.status in {301, 302, 303, 307, 308}:
                        url = urljoin(url, response.headers.get("Location", ""))
                        if not _public_url(url):
                            break
                        continue
                    if response.status != 200 or (response.content_length or 0) > MAX_DOCUMENT:
                        break
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > MAX_DOCUMENT:
                            return None, 0
                    parser = etree.XMLParser(
                        resolve_entities=False, no_network=True, load_dtd=False
                    )
                    root = await asyncio.to_thread(etree.fromstring, bytes(body), parser)
                    return (url, root), len(body)
    except (aiohttp.ClientError, TimeoutError, OSError, etree.XMLSyntaxError, ValueError):
        # Cache unavailable or unreadable capabilities briefly, then retry on a later request.
        return None, 0
    return None, 0


async def _fill(url):
    try:
        doc, size = await _download(url)
        _cache[url] = (monotonic() + (3600 if doc else 90), doc, size)
        while len(_cache) > 128 or sum(item[2] for item in _cache.values()) > 32 * 1024 * 1024:
            _cache.popitem(last=False)
        return doc
    finally:
        _pending.pop(url, None)


def cached_document(url):
    entry = _cache.get(url)
    return entry[1] if entry and entry[0] > monotonic() else None


async def document(url):
    entry = _cache.get(url)
    if entry and entry[0] > monotonic():
        _cache.move_to_end(url)
        return entry[1]
    if url not in _pending:
        _pending[url] = asyncio.create_task(_fill(url))
    return await asyncio.shield(_pending[url])


def _match(nodes, field, selector):
    named = [(n.findtext("{*}" + field), n) for n in nodes if n.findtext("{*}" + field)]
    if not selector:
        return named[0] if len(named) == 1 else (None, None)
    matches = [pair for pair in named if pair[0] == selector]
    if not matches and ":" not in selector:
        matches = [pair for pair in named if pair[0].rsplit(":", 1)[-1] == selector]
    if not matches and ":" in selector:
        matches = [pair for pair in named if pair[0] == selector.rsplit(":", 1)[-1]]
    return matches[0] if len(matches) == 1 else (None, None)


def _advertised(base, href):
    if not href:
        return None
    url = urljoin(base, href)
    p = urlsplit(url)
    if p.scheme == "http" and p.netloc == urlsplit(base).netloc:
        url = urlunsplit(p._replace(scheme="https"))
    return url if _public_url(url) else None


def _kvp(endpoint, params):
    parsed = urlsplit(endpoint)
    overrides = {k.lower() for k in params}
    pairs = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in overrides]
    return urlunsplit(parsed._replace(query=urlencode(pairs + list(params.items()), safe="{}")))


def _layer_bounds(layer):
    for node in [layer, *layer.iterancestors()]:
        box = node.find("{*}EX_GeographicBoundingBox")
        if box is not None:
            return [
                box.findtext("{*}" + d + "BoundLongitude")
                if d in ("west", "east")
                else box.findtext("{*}" + d + "BoundLatitude")
                for d in ("west", "south", "east", "north")
            ]
        box = node.find("{*}LatLonBoundingBox")
        if box is not None:
            return [box.get(k) for k in ("minx", "miny", "maxx", "maxy")]
        box = node.find("{*}WGS84BoundingBox")
        if box is not None:
            return (
                box.findtext("{*}LowerCorner", "") + " " + box.findtext("{*}UpperCorner", "")
            ).split()
    return None


def _wms(base, root, selector):
    name, layer = _match(root.findall(".//{*}Capability//{*}Layer"), "Name", selector)
    if layer is None:
        return None
    crs = set()
    for node in [layer, *layer.iterancestors()]:
        for tag in ("CRS", "SRS"):
            for item in node.findall("{*}" + tag):
                crs.update((item.text or "").upper().split())
    crs_name = next((s for s in ("EPSG:3857", "EPSG:900913") if s in crs), None)
    op = root.find(".//{*}Request/{*}GetMap")
    if not crs_name or op is None:
        return None
    fmt = next((f for f in FORMATS if f in [e.text for e in op.findall("{*}Format")]), None)
    online = op.find(".//{*}Get/{*}OnlineResource")
    endpoint = _advertised(base, online.get(XLINK)) if online is not None else None
    version = root.get("version")
    if not endpoint or not fmt or version not in {"1.1.0", "1.1.1", "1.3.0"}:
        return None
    params = dict(
        SERVICE="WMS",
        REQUEST="GetMap",
        VERSION=version,
        LAYERS=name,
        STYLES="",
        FORMAT=fmt,
        TRANSPARENT="TRUE",
        WIDTH=256,
        HEIGHT=256,
        BBOX="{bbox-epsg-3857}",
    )
    params["CRS" if version == "1.3.0" else "SRS"] = crs_name
    return "wms", dict(
        url=endpoint,
        layers=name,
        styles="",
        format=fmt,
        transparent=True,
        version=version,
        tileSize=256,
        bounds=_layer_bounds(layer),
        tiles=[_kvp(endpoint, params)],
    )


def _grid(node):
    """Require the global Web Mercator XYZ geometry and a templatable matrix ID."""
    if not re.search(r"[:/](3857|900913)$", node.findtext("{*}SupportedCRS", ""), re.I):
        return None
    levels = {}
    for m in node.findall("{*}TileMatrix"):
        width = int(m.findtext("{*}MatrixWidth"))
        size = int(m.findtext("{*}TileWidth"))
        if width < 1 or width & (width - 1) or int(m.findtext("{*}MatrixHeight")) != width:
            return None
        z = width.bit_length() - 1
        origin = [float(n) for n in m.findtext("{*}TopLeftCorner", "").split()]
        if (
            size not in (256, 512)
            or int(m.findtext("{*}TileHeight")) != size
            or len(origin) != 2
            or not all(
                math.isclose(x, y, rel_tol=1e-6)
                for x, y in zip(origin, (-20037508.342789, 20037508.342789))
            )
            or not math.isclose(
                float(m.findtext("{*}ScaleDenominator")) * 0.00028,
                40075016.685578 / (width * size),
                rel_tol=1e-5,
            )
        ):
            return None
        match = re.fullmatch(r"(.*?)(\d+)", m.findtext("{*}Identifier", ""))
        if not match or match[2] != str(z) or z in levels:
            return None
        levels[z] = (match[1] + "{z}", size)
    if not levels or len(set(levels.values())) != 1 or max(levels) - min(levels) + 1 != len(levels):
        return None
    template, size = next(iter(levels.values()))
    return template, size, min(levels), max(levels)


def _wmts(base, root, selector):
    contents = root.find("{*}Contents")
    if contents is None:
        return None
    name, layer = _match(contents.findall("{*}Layer"), "Identifier", selector)
    if layer is None:
        return None
    styles = layer.findall("{*}Style")
    default = next((s for s in styles if s.get("isDefault") in ("true", "1")), None)
    style = (
        default.findtext("{*}Identifier", "")
        if default is not None
        else (styles[0].findtext("{*}Identifier", "") if len(styles) == 1 else "")
    )
    dimensions = {}
    for dim in layer.findall("{*}Dimension"):
        key, value = dim.findtext("{*}Identifier"), dim.findtext("{*}Default")
        if not key or not value:
            return None
        dimensions[key] = value
    grids = {g.findtext("{*}Identifier"): g for g in contents.findall("{*}TileMatrixSet")}
    for link in layer.findall("{*}TileMatrixSetLink"):
        matrix_set = link.findtext("{*}TileMatrixSet")
        if matrix_set not in grids or not (grid := _grid(grids[matrix_set])):
            continue
        matrix, size, low, high = grid
        limits = link.findall("{*}TileMatrixSetLimits/{*}TileMatrixLimits/{*}TileMatrix")
        if limits:
            allowed = {item.text for item in limits}
            levels = [z for z in range(low, high + 1) if matrix.replace("{z}", str(z)) in allowed]
            if not levels or max(levels) - min(levels) + 1 != len(levels):
                continue
            low, high = min(levels), max(levels)
        resources = layer.findall("{*}ResourceURL")
        for fmt in FORMATS:
            if fmt not in [f.text for f in layer.findall("{*}Format")]:
                continue
            url = None
            for r in resources:
                if r.get("resourceType") != "tile" or r.get("format") != fmt:
                    continue
                raw = r.get("template", "")
                for key, value in {
                    "Style": style,
                    "TileMatrixSet": matrix_set,
                    **dimensions,
                }.items():
                    raw = re.sub(re.escape("{" + key + "}"), quote(value, safe=""), raw, flags=re.I)
                for key, value in {
                    "TileMatrix": matrix,
                    "TileRow": "{y}",
                    "TileCol": "{x}",
                }.items():
                    raw = raw.replace("{" + key + "}", value)
                if set(re.findall(r"\{[^}]+\}", raw)) == {"{z}", "{y}", "{x}"}:
                    url = _advertised(base, raw)
                    if url:
                        break
            if not url:
                for get in root.findall(".//{*}Operation[@name='GetTile']/{*}DCP/{*}HTTP/{*}Get"):
                    enc = get.findall(
                        "{*}Constraint[@name='GetEncoding']/{*}AllowedValues/{*}Value"
                    )
                    endpoint = _advertised(base, get.get(XLINK))
                    if endpoint and (not enc or any(v.text == "KVP" for v in enc)):
                        url = _kvp(
                            endpoint,
                            dict(
                                SERVICE="WMTS",
                                VERSION="1.0.0",
                                REQUEST="GetTile",
                                LAYER=name,
                                STYLE=style,
                                FORMAT=fmt,
                                TILEMATRIXSET=matrix_set,
                                TILEMATRIX=matrix,
                                TILEROW="{y}",
                                TILECOL="{x}",
                                **dimensions,
                            ),
                        )
                        break
            if url:
                return "wmts", dict(
                    url=url,
                    tiles=[url],
                    bounds=_layer_bounds(layer),
                    tileSize=size,
                    minzoom=low,
                    maxzoom=high,
                )
    return None


def discover(doc, selector):
    if doc is None:
        return None
    base, root = doc
    try:
        kind = etree.QName(root).localname
        if kind in {"WMS_Capabilities", "WMT_MS_Capabilities"}:
            return _wms(base, root, selector)
        if (
            kind == "Capabilities"
            and etree.QName(root).namespace == "http://www.opengis.net/wmts/1.0"
        ):
            return _wmts(base, root, selector)
    except (TypeError, ValueError, OverflowError):
        # Malformed provider metadata cannot describe a usable raster layer.
        return None
    return None
