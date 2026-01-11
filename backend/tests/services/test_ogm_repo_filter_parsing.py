import pytest

from app.services.search_service import SearchService


@pytest.mark.unit
def test_ogm_repo_bracket_filter_maps_to_include_filters():
    svc = SearchService()
    include_filters, exclude_filters = svc.extract_new_style_filters(
        "ogm_repo[]=edu.stanford.purl&ogm_repo[]=edu.umn"
    )
    assert exclude_filters == {}
    assert include_filters.get("ogm_repo") == ["edu.stanford.purl", "edu.umn"]

