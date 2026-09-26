from scripts.export_discovery_outcomes_2026 import public_constraints


def test_context_exports_only_public_search_parameters():
    constraints = {
        "q": "redlining",
        "exclude_filters[gbl_resourceClass_sm][]": ["Datasets", "Web services"],
        "geo": {"bbox": [1, 2, 3, 4]},
        "page": "2",
        "api_key": "never-export",
        "visit_token": "never-export",
        "utm_source": "not-search-context",
        "unexpected": "never-export",
    }
    result = public_constraints(constraints)
    assert set(result) == {"q", "exclude_filters[gbl_resourceClass_sm][]", "geo", "page"}
    assert result["exclude_filters[gbl_resourceClass_sm][]"] == ["Datasets", "Web services"]


def test_missing_or_malformed_constraints_do_not_become_raw_exports():
    assert public_constraints(None) == {}
    assert public_constraints("not an object") == {}
    assert public_constraints({"include_filters[x][];unsafe": "x"}) == {}
