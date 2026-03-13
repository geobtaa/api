import pytest
import pytest_asyncio

from app.viewers import ItemViewer


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "ignore_event_loop: mark test to ignore event loop closed errors"
    )


@pytest_asyncio.fixture(scope="function")
async def setup_test_database():
    """Setup test database for each test."""
    # Setup code here
    yield
    # Teardown code here


def test_viewer_protocol_with_cog():
    references = {"https://github.com/cogeotiff/cog-spec": "https://example.com/cog.tif"}
    viewer = ItemViewer(references)
    assert viewer.viewer_protocol() == "cog"
    assert viewer.viewer_endpoint() == "https://example.com/cog.tif"


def test_viewer_protocol_with_wms():
    references = {"http://www.opengis.net/def/serviceType/ogc/wms": "https://example.com/wms"}
    viewer = ItemViewer(references)
    assert viewer.viewer_protocol() == "wms"
    assert viewer.viewer_endpoint() == "https://example.com/wms"


def test_viewer_protocol_with_no_references():
    viewer = ItemViewer({})
    assert viewer.viewer_protocol() == "geo_json"
    assert viewer.viewer_endpoint() == ""


def test_viewer_geometry_with_envelope():
    references = {"locn_geometry": "ENVELOPE(-180, 180, 90, -90)"}
    viewer = ItemViewer(references)
    geometry = viewer.viewer_geometry()
    assert geometry["type"] == "Polygon"
    assert geometry["coordinates"] == [
        [
            [-180, 90],  # top left
            [-180, -90],  # bottom left
            [180, -90],  # bottom right
            [180, 90],  # top right
            [-180, 90],  # close the polygon
        ]
    ]


def test_viewer_geometry_with_polygon():
    references = {"locn_geometry": "POLYGON((0 0, 0 1, 1 1, 1 0, 0 0))"}
    viewer = ItemViewer(references)
    geometry = viewer.viewer_geometry()
    assert geometry["type"] == "Polygon"
    assert geometry["coordinates"] == [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]


def test_viewer_geometry_with_geojson():
    references = {"locn_geometry": '{"type": "Point", "coordinates": [0, 0]}'}
    viewer = ItemViewer(references)
    geometry = viewer.viewer_geometry()
    assert geometry["type"] == "Point"
    assert geometry["coordinates"] == [0, 0]


def test_viewer_geometry_with_multipolygon_wkt():
    """MultiPolygon WKT returns GeoJSON MultiPolygon (preserves type for dashed extent)."""
    references = {
        "locn_geometry": "MultiPolygon(((0 0, 0 1, 1 1, 1 0, 0 0)))",
    }
    viewer = ItemViewer(references)
    geometry = viewer.viewer_geometry()
    assert geometry["type"] == "MultiPolygon"
    assert geometry["coordinates"] == [[[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]]


def test_viewer_geometry_with_multipolygon_wkt_two_polygons():
    """MultiPolygon WKT with two polygons returns both."""
    references = {
        "locn_geometry": "MultiPolygon(((0 0, 0 1, 1 1, 1 0, 0 0)), ((2 2, 2 3, 3 3, 3 2, 2 2)))",
    }
    viewer = ItemViewer(references)
    geometry = viewer.viewer_geometry()
    assert geometry["type"] == "MultiPolygon"
    assert len(geometry["coordinates"]) == 2
    assert geometry["coordinates"][0] == [[[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]]]
    assert geometry["coordinates"][1] == [[[2, 2], [2, 3], [3, 3], [3, 2], [2, 2]]]


def test_viewer_geometry_with_shipping_fairways_multipolygon():
    """MultiPolygon WKT from Shipping Fairways [Pennsylvania] PASDA resource."""
    wkt = (
        "MultiPolygon(((-75.6 39.8, -75.8 39.7, -80.5 39.7, -80.5 42.3, -79.8 42.5, "
        "-79.8 42, -75.3 42, -75.1 41.8, -75 41.5, -74.7 41.4, -75.1 41, -75.1 40.9, "
        "-75.2 40.7, -74.7 40.2, -75.1 39.9, -75.6 39.8)))"
    )
    viewer = ItemViewer({"locn_geometry": wkt})
    geometry = viewer.viewer_geometry()
    assert geometry["type"] == "MultiPolygon"
    assert len(geometry["coordinates"]) == 1
    ring = geometry["coordinates"][0][0]
    assert len(ring) >= 16
    assert ring[0] == [-75.6, 39.8]
    assert ring[-1] == [-75.6, 39.8]  # closed


@pytest.mark.asyncio
@pytest.mark.xfail(raises=RuntimeError, reason="Known event loop issue in last test")
async def test_viewer_geometry_with_invalid(setup_test_database):
    """Test viewer geometry handling with invalid input."""
    references = {"locn_geometry": "INVALID"}
    viewer = ItemViewer(references)
    assert viewer.viewer_geometry() is None
