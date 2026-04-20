import json

from app.services.reference_reconstruction import (
    build_asset_record_from_kithe_model,
    build_distribution_rows_from_payload,
    build_effective_reference_payload,
    build_storage_file_url,
    serialize_reference_payload,
)


def test_build_effective_reference_payload_merges_legacy_sources():
    payload = build_effective_reference_payload(
        {"http://lccn.loc.gov/sh85035852": "https://example.org/reference-guide"},
        document_distributions=[
            {
                "reference_type_id": 9,
                "url": "https://example.org/metadata.xml",
                "label": "FGDC XML",
            }
        ],
        document_downloads=[
            {
                "label": "Shapefile",
                "value": "https://example.org/download.zip",
            }
        ],
        assets=[
            {
                "dct_references_uri_key": "download",
                "label": "GeoPackage",
                "file": {"url": "https://example.org/geopackage.zip"},
            },
            {
                "dct_references_uri_key": "pmtiles",
                "file": {"url": "https://example.org/tiles.pmtiles"},
            },
        ],
        reference_type_id_to_uri={9: "http://www.opengis.net/cat/csw/csdgm"},
    )

    assert payload["http://lccn.loc.gov/sh85035852"] == "https://example.org/reference-guide"
    assert payload["http://www.opengis.net/cat/csw/csdgm"] == [
        {"url": "https://example.org/metadata.xml", "label": "FGDC XML"}
    ]
    assert payload["http://schema.org/downloadUrl"] == [
        {"url": "https://example.org/download.zip", "label": "Shapefile"},
        {"url": "https://example.org/geopackage.zip", "label": "GeoPackage"},
    ]
    assert payload["https://github.com/protomaps/PMTiles"] == "https://example.org/tiles.pmtiles"

    serialized = serialize_reference_payload(payload)
    assert serialized is not None
    assert json.loads(serialized) == payload

    rows = build_distribution_rows_from_payload(
        "resource-1",
        payload,
        uri_to_type_id={
            "http://lccn.loc.gov/sh85035852": 1,
            "http://www.opengis.net/cat/csw/csdgm": 2,
            "http://schema.org/downloadUrl": 3,
            "https://github.com/protomaps/PMTiles": 4,
        },
    )
    assert [(row["distribution_type_id"], row["url"], row["label"]) for row in rows] == [
        (1, "https://example.org/reference-guide", None),
        (2, "https://example.org/metadata.xml", "FGDC XML"),
        (3, "https://example.org/download.zip", "Shapefile"),
        (3, "https://example.org/geopackage.zip", "GeoPackage"),
        (4, "https://example.org/tiles.pmtiles", None),
    ]


def test_build_asset_record_from_kithe_model_builds_storage_backed_asset():
    file_data = {
        "storage": "store",
        "id": "asset/abc123/file.pmtiles",
        "metadata": {
            "mime_type": "application/vnd.pmtiles",
            "size": 456789,
            "width": None,
            "height": None,
            "md5": "abc",
            "sha1": "def",
            "sha512": "ghi",
        },
    }

    assert (
        build_storage_file_url(file_data, base_url="https://assets.example.org")
        == "https://assets.example.org/store/asset/abc123/file.pmtiles"
    )

    asset = build_asset_record_from_kithe_model(
        {
            "id": "kithe-asset-1",
            "friendlier_id": "asset-1",
            "parent_id": "parent-1",
            "title": "PMTiles asset",
            "label": None,
            "thumbnail": False,
            "dct_references_uri_key": "pmtiles",
            "position": 4,
            "file_data": file_data,
        },
        resource_id="resource-1",
        asset_base_url="https://assets.example.org",
    )

    assert asset == {
        "id": "kithe-asset-1",
        "resource_id": "resource-1",
        "title": "PMTiles asset",
        "friendlier_id": "asset-1",
        "parent_id": "parent-1",
        "label": None,
        "thumbnail": False,
        "dct_references_uri_key": "pmtiles",
        "position": 4,
        "created_at": None,
        "updated_at": None,
        "file_url": "https://assets.example.org/store/asset/abc123/file.pmtiles",
        "file_mime_type": "application/vnd.pmtiles",
        "file_size": 456789,
        "file_width": None,
        "file_height": None,
        "file_md5": "abc",
        "file_sha1": "def",
        "file_sha512": "ghi",
    }
