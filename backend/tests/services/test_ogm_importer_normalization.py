from app.services.ogm_harvest.importer import OGMResourceImporter


def test_normalize_record_coerces_harvest_workflow_list_to_scalar():
    importer = OGMResourceImporter()
    record = {
        "id": "test-id",
        "b1g_harvestWorkflow_s": ["Aardvark", "extra"],
    }

    normalized = importer._normalize_record(record, repo_name="edu.utexas")

    assert normalized["b1g_harvestWorkflow_s"] == "Aardvark"


def test_normalize_record_coerces_title_list_to_scalar():
    importer = OGMResourceImporter()
    record = {
        "id": "test-id",
        "dct_title_s": ["Sanborn Fire Insurance Maps [Houston, Texas, 1907, Sheet 17]"],
    }

    normalized = importer._normalize_record(record, repo_name="edu.utexas")

    assert (
        normalized["dct_title_s"] == "Sanborn Fire Insurance Maps [Houston, Texas, 1907, Sheet 17]"
    )


def test_normalize_record_defaults_publication_state_to_published():
    importer = OGMResourceImporter()
    record = {
        "id": "test-id",
        "dct_title_s": "Test Title",
    }

    normalized = importer._normalize_record(record, repo_name="edu.utexas")

    assert normalized["publication_state"] == "published"
    assert normalized["b1g_publication_state_s"] == "published"


def test_normalize_record_copies_b1g_publication_state_to_publication_state():
    importer = OGMResourceImporter()
    record = {
        "id": "test-id",
        "b1g_publication_state_s": ["published"],
    }

    normalized = importer._normalize_record(record, repo_name="edu.utexas")

    assert normalized["publication_state"] == "published"
    assert normalized["b1g_publication_state_s"] == "published"


def test_normalize_record_derives_index_year_from_date_range():
    importer = OGMResourceImporter()
    record = {
        "id": "test-id",
        "gbl_dateRange_drsim": ["[1922 TO 1962]"],
    }

    normalized = importer._normalize_record(record, repo_name="edu.utexas")

    assert normalized["gbl_indexYear_im"] == [1922]


def test_normalize_record_preserves_supplied_index_years():
    importer = OGMResourceImporter()
    record = {
        "id": "test-id",
        "gbl_indexYear_im": [1922, 1924, 1927],
        "gbl_dateRange_drsim": ["[1922 TO 1962]"],
    }

    normalized = importer._normalize_record(record, repo_name="edu.utexas")

    assert normalized["gbl_indexYear_im"] == [1922, 1924, 1927]
