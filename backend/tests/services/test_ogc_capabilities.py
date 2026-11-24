import asyncio
from urllib.parse import parse_qs, urlsplit

import pytest
from lxml import etree

from app.services import ogc_capabilities as caps
from app.services.geolibre_raster import WMS, WMTS, raster_projects

WMS_XML = """<WMS_Capabilities version="1.3.0" xmlns:xlink="http://www.w3.org/1999/xlink">
<Capability>
<Request>
<GetMap>
<Format>image/png</Format>
<DCPType>
<HTTP>
<Get>
<OnlineResource xlink:href="https://gis.example.org/render?map=parks&amp;service=WMS"/>
</Get>
</HTTP>
</DCPType>
</GetMap>
</Request>
<Layer>
<CRS>EPSG:3857</CRS>
<LatLonBoundingBox minx="-80" miny="40" maxx="-79" maxy="41"/>
<Layer>
<Name>parks</Name>
</Layer>
<Layer>
<Name>roads</Name>
</Layer>
</Layer>
</Capability>
</WMS_Capabilities>"""
WMTS_XML = """<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1"
 xmlns:xlink="http://www.w3.org/1999/xlink">
<ows:OperationsMetadata>
<ows:Operation name="GetTile">
<ows:DCP>
<ows:HTTP>
 <ows:Get xlink:href="/wmts/tiles"/>
</ows:HTTP>
</ows:DCP>
</ows:Operation>
</ows:OperationsMetadata>
 <Contents>
<Layer>
<ows:Identifier>sheet</ows:Identifier>
<Style isDefault="true">
<ows:Identifier>color</ows:Identifier>
 </Style>
<Format>image/png</Format>
<TileMatrixSetLink>
<TileMatrixSet>web</TileMatrixSet>
</TileMatrixSetLink>
 <ResourceURL resourceType="tile" format="image/png"
 template="/tiles/{Style}/{TileMatrixSet}/{TileMatrix}/{TileCol}/{TileRow}.png"/>
 </Layer>
<TileMatrixSet>
<ows:Identifier>web</ows:Identifier>
<ows:SupportedCRS>urn:ogc:def:crs:EPSG::3857</ows:SupportedCRS>
 <TileMatrix>
<ows:Identifier>L9</ows:Identifier>
<ScaleDenominator>1091957.546931</ScaleDenominator>
 <TopLeftCorner>-20037508.343 20037508.343</TopLeftCorner>
<TileWidth>256</TileWidth>
<TileHeight>256</TileHeight>
 <MatrixWidth>512</MatrixWidth>
<MatrixHeight>512</MatrixHeight>
</TileMatrix>
</TileMatrixSet>
</Contents>
</Capabilities>"""
URL = "https://gis.example.org/capabilities.xml"


def parse(xml):
    return URL, etree.fromstring(xml.encode())


def test_wms_uses_layer_inheritance_and_advertised_operation():
    doc = parse(WMS_XML)
    (p,) = raster_projects({WMS: URL}, "city:parks", None, "City parks", {URL: doc}).values()
    (layer,) = p["layers"]
    assert layer["source"]["bounds"] == [-80, 40, -79, 41]
    target = urlsplit(layer["source"]["tiles"][0])
    assert target.path == "/render"
    query = parse_qs(target.query)
    assert [query[k][0] for k in ("map", "LAYERS", "CRS", "BBOX")] == [
        "parks",
        "parks",
        "EPSG:3857",
        "{bbox-epsg-3857}",
    ]
    assert caps.discover(doc, None) is None
    assert caps.discover(doc, "missing") is None
    assert caps.discover(parse(WMS_XML.replace("EPSG:3857", "EPSG:4326")), "parks") is None


def test_single_layer_wmts_uses_native_grid_and_actual_protocol():
    (p,) = raster_projects(
        {WMS: URL}, None, "-75,40,-74,41", "Map", {URL: parse(WMTS_XML)}
    ).values()
    (layer,) = p["layers"]
    assert layer["type"] == "wmts"
    source = layer["source"]
    assert source["minzoom"] == source["maxzoom"] == 9
    assert source["tiles"] == ["https://gis.example.org/tiles/color/web/L{z}/{x}/{y}.png"]
    assert (
        caps.discover(parse(WMTS_XML.replace("<MatrixWidth>512", "<MatrixWidth>500")), None) is None
    )
    assert caps.discover(parse(WMTS_XML.replace("20037508.343", "20")), None) is None


def test_wmts_kvp_uses_advertised_operation_and_default_style():
    doc = parse(WMTS_XML)
    layer = doc[1].find(".//{*}Layer")
    layer.remove(layer.find("{*}ResourceURL"))
    kind, source = caps.discover(doc, "sheet")
    assert kind == "wmts"
    target = urlsplit(source["tiles"][0])
    assert target.path == "/wmts/tiles"
    q = parse_qs(target.query)
    assert [
        q[k][0] for k in ("LAYER", "STYLE", "TILEMATRIXSET", "TILEMATRIX", "TILEROW", "TILECOL")
    ] == ["sheet", "color", "web", "L{z}", "{y}", "{x}"]


@pytest.mark.parametrize(
    "url",
    [
        "http://gis.example.org",
        "https://localhost/wms",
        "https://127.0.0.1",
        "https://127.1",
        "https://0177.0.0.1",
        "https://maps.example.org/?token=abc",
        "https://me:pass@gis.example.org",
        "https://[::1]/",
        "https://geo.local/wms",
    ],
)
def test_service_requests_are_public(url):
    assert caps.request_for(WMTS, url, None) is None


@pytest.mark.asyncio
async def test_shared_document_fetched_once(monkeypatch):
    calls = []

    async def fetch(url):
        calls.append(url)
        await asyncio.sleep(0)
        return parse(WMS_XML), len(WMS_XML)

    monkeypatch.setattr(caps, "_download", fetch)
    monkeypatch.setattr(caps, "_cache", caps.OrderedDict())
    assert await asyncio.gather(caps.document(URL), caps.document(URL))
    assert await caps.document(URL)
    assert calls == [URL]
