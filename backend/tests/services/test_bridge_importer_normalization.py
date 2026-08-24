from app.services.bridge_sync.importer import BridgeResourceImporter


def test_normalize_record_copies_publication_state_to_b1g_publication_state():
    importer = BridgeResourceImporter()
    record = {
        "id": "bridge-test-id",
        "publication_state": "published",
        "import_id": 582,
    }

    normalized = importer._normalize_record(record)

    assert normalized["publication_state"] == "published"
    assert normalized["b1g_publication_state_s"] == "published"
    assert normalized["import_id"] == "582"


def test_normalize_record_derives_index_year_from_bridge_date_range():
    importer = BridgeResourceImporter()
    record = {
        "id": "cf4baf3c439247b4b51aaefa62cd9f37_0",
        "gbl_indexYear_im": [],
        "gbl_dateRange_drsim": ["2024-2024"],
    }

    normalized = importer._normalize_record(record)

    assert normalized["gbl_indexYear_im"] == [2024]


def test_normalize_record_handles_empty_temporal_fields():
    importer = BridgeResourceImporter()
    record = {
        "id": "undated-resource",
        "gbl_indexYear_im": [],
        "gbl_dateRange_drsim": [],
    }

    normalized = importer._normalize_record(record)

    assert normalized["gbl_indexYear_im"] is None
