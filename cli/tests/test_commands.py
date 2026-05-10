from __future__ import annotations

import json

from conftest import invoke


def test_help_lists_core_commands(runner):
    result = invoke(runner, ["--help"])

    assert result.exit_code == 0
    for command in ["search", "schema", "facets", "get", "download", "ogc", "admin"]:
        assert command in result.output


def test_search_sends_include_and_exclude_filters(runner, mock_client, sample_search_payload):
    recorder = mock_client({"/api/v1/search": sample_search_payload})

    result = invoke(
        runner,
        [
            "--no-analytics",
            "search",
            "water",
            "--include",
            "dct_spatial_sm=Iowa,Minnesota",
            "--exclude",
            "gbl_resourceType_sm=Websites",
            "--output",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    request = recorder.requests[0]
    params = dict(request.url.params.multi_items())
    assert params["include_filters[dct_spatial_sm][]"] == "Minnesota"
    assert ("include_filters[dct_spatial_sm][]", "Iowa") in request.url.params.multi_items()
    assert params["exclude_filters[gbl_resourceType_sm][]"] == "Websites"


def test_search_rejects_bad_advanced_query(runner, mock_client):
    mock_client({})

    result = invoke(runner, ["search", "water", "--adv-q", "not-json"])

    assert result.exit_code != 0
    assert "valid JSON" in result.output


def test_schema_facets_uses_registry(runner, mock_client):
    mock_client({})

    result = invoke(runner, ["--no-analytics", "schema", "facets", "--output", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {"name": "dct_spatial_sm"} in payload
    assert {"name": "schema_provider_s"} in payload


def test_schema_queryables_calls_ogc_endpoint(runner, mock_client):
    recorder = mock_client(
        {
            "/api/v1/ogc/collections/btaa-records/queryables": {
                "properties": {"title": {"type": "string"}}
            }
        }
    )

    result = invoke(runner, ["--no-analytics", "schema", "queryables", "--output", "json"])

    assert result.exit_code == 0
    assert recorder.requests[0].url.path == "/api/v1/ogc/collections/btaa-records/queryables"


def test_facets_table_uses_hits_as_count(runner, mock_client):
    mock_client(
        {
            "/api/v1/search/facets/dct_spatial_sm": {
                "data": [
                    {
                        "type": "facet_value",
                        "id": "Illinois",
                        "attributes": {"value": "Illinois", "hits": 42},
                    }
                ],
                "meta": {"totalCount": 1},
            }
        }
    )

    result = invoke(runner, ["--no-analytics", "facets", "dct_spatial_sm", "--q", "water"])

    assert result.exit_code == 0, result.output
    assert "Illinois" in result.output
    assert "42" in result.output


def test_get_resource_routes_to_resource_endpoint(runner, mock_client):
    recorder = mock_client({"/api/v1/resources/b1g_test": {"data": {"id": "b1g_test"}}})

    result = invoke(runner, ["--no-analytics", "get", "b1g_test"])

    assert result.exit_code == 0
    assert recorder.requests[0].url.path == "/api/v1/resources/b1g_test"


def test_cite_bibtex_route(runner, mock_client):
    recorder = mock_client({"/api/v1/resources/b1g_test/citation/bibtex": "@misc{test}"})

    result = invoke(runner, ["--no-analytics", "cite", "b1g_test", "--format", "bibtex"])

    assert result.exit_code == 0
    assert "@misc" in result.output
    assert recorder.requests[0].url.path == "/api/v1/resources/b1g_test/citation/bibtex"
