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
