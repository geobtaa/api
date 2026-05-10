from __future__ import annotations

import pytest

from btaa_geo_api_cli.filters import apply_filter_params, parse_filters


def test_parse_repeated_and_comma_filters():
    filters = parse_filters(
        ["dct_spatial_sm=Iowa,Minnesota", "dct_accessRights_s=Public"],
        ["gbl_resourceType_sm=Websites"],
    )

    assert filters.include["dct_spatial_sm"] == ["Iowa", "Minnesota"]
    assert filters.include["dct_accessRights_s"] == ["Public"]
    assert filters.exclude["gbl_resourceType_sm"] == ["Websites"]


def test_invalid_filter_syntax():
    with pytest.raises(ValueError):
        parse_filters(["not-a-filter"], None)


def test_apply_filter_params_uses_api_contract():
    params = apply_filter_params(
        {"q": "water"},
        parse_filters(["dct_spatial_sm=Iowa"], ["schema_provider_s=Penn State"]),
    )

    assert params["include_filters[dct_spatial_sm][]"] == ["Iowa"]
    assert params["exclude_filters[schema_provider_s][]"] == ["Penn State"]
