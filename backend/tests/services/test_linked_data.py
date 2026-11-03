"""Semantic assertions against a real JSON-LD 1.1 processor, without network IO."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pyld import jsonld

from app.api.schemas import SchemaOrgCitationResponse
from app.api.v1.presenters import ResourcePresenter
from app.services.citation_formats_service import CitationFormatsService
from app.services.linked_data import DCT, PCDM, SCHEMA, resource_jsonld


def no_remote_documents(url, options=None):
    raise AssertionError(f"Unexpected remote context dependency: {url}")


def expand(document):
    return jsonld.expand(document, options={"documentLoader": no_remote_documents})[0]


@pytest.fixture
def record():
    return {
        "id": "address-points",
        "dct_title_s": "Address points",
        "gbl_resourceClass_sm": ["Datasets"],
        "gbl_resourceType_sm": ["Point data"],
        "pcdm_memberOf_sm": ["urban-layers", "https://example.org/collections/roads"],
        "dct_isPartOf_sm": ["state"],
        "dct_issued_s": "2025-07-03",
        "dct_license_sm": ["https://creativecommons.org/licenses/by/4.0/"],
        "dct_creator_sm": ["Jane Smith", "City of Example"],
        "dct_publisher_sm": ["Publisher A", "Publisher B"],
        "schema_provider_s": "Example Library",
        "dct_accessRights_s": "Public",
        "dcat_bbox": "-94,44,-93,45",
        "dct_format_s": "GeoPackage",
        "dct_references_s": json.dumps(
            {
                "http://schema.org/url": "https://example.org/catalog/points",
                "http://schema.org/downloadUrl": {"url": "https://example.org/points.zip"},
                "https://github.com/protomaps/PMTiles": "https://example.org/points.pmtiles",
                "http://iiif.io/api/presentation#manifest": "https://example.org/manifest.json",
            }
        ),
    }


def test_standalone_graph_has_expected_rdf_identities(record, monkeypatch):
    monkeypatch.setenv("GEOPORTAL_BASE_URL", "https://example.org")
    response = ResourcePresenter.serialize_jsonapi_resource(record)
    assert "@context" not in response["meta"]
    assert "@type" not in response["meta"]
    assert response["attributes"]["ogm"]["id"] == "address-points"
    assert "jsonld" not in response["meta"]
    graph = CitationFormatsService(record).to_json_ld(record["id"])
    expanded = expand(graph)
    assert expanded["@id"] == "https://example.org/resources/address-points"
    assert expanded["@type"] == [SCHEMA + "Dataset"]
    assert expanded[SCHEMA + "name"] == [{"@value": "Address points"}]
    assert expanded[PCDM + "memberOf"] == [
        {"@id": "https://example.org/resources/urban-layers"},
        {"@id": "https://example.org/collections/roads"},
    ]
    assert expanded[DCT + "isPartOf"] == [{"@id": "https://example.org/resources/state"}]
    assert expanded[SCHEMA + "license"] == [{"@id": "https://creativecommons.org/licenses/by/4.0/"}]
    rdf = jsonld.to_rdf(
        graph,
        options={
            "format": "application/n-quads",
            "documentLoader": no_remote_documents,
        },
    )
    assert "<https://example.org/resources/address-points>" in rdf
    assert "<http://pcdm.org/models#memberOf> <https://example.org/resources/urban-layers>" in rdf
    assert '"44 -94 45 -93"' in rdf
    assert "BtaaAardvarkRecord" not in rdf
    assert (
        CitationFormatsService(record, base_url="https://example.org").to_json_ld(record["id"])
        == graph
    )
    SchemaOrgCitationResponse.model_validate(graph)


def test_no_false_agent_access_or_distribution_assertions(record):
    graph = resource_jsonld(record, record["id"], base_url="https://example.org")
    assert graph["author"] == [{"name": "Jane Smith"}, {"name": "City of Example"}]
    assert graph["publisher"] == [{"name": "Publisher A"}, {"name": "Publisher B"}]
    assert graph["provider"] == [{"name": "Example Library"}]
    assert graph["conditionsOfAccess"] == "Public"
    assert "accessMode" not in graph
    assert graph["distribution"] == [
        {"@type": "DataDownload", "contentUrl": "https://example.org/points.zip"}
    ]
    expanded = expand(graph)
    assert expanded[SCHEMA + "distribution"][0][SCHEMA + "contentUrl"] == [
        {"@id": "https://example.org/points.zip"}
    ]


@pytest.mark.parametrize(
    "download_value",
    [
        "https://example.org/file.zip",
        {"url": "https://example.org/file.zip"},
        [{"url": "https://example.org/file.zip"}],
    ],
)
def test_supported_legacy_download_shapes(record, download_value):
    record["dct_references_s"] = {"http://schema.org/downloadUrl": download_value}
    assert len(resource_jsonld(record, record["id"])["distribution"]) == 1


def test_normalized_distributions_are_authoritative(record):
    context = SimpleNamespace(
        by_uri={
            "http://schema.org/downloadUrl": [
                SimpleNamespace(url="https://example.org/new.zip", label="Download")
            ],
            "http://schema.org/thumbnailUrl": [
                SimpleNamespace(url="https://example.org/thumb.png", label=None)
            ],
        }
    )
    graph = resource_jsonld(record, record["id"], distribution_context=context)
    assert graph["distribution"] == [
        {
            "@type": "DataDownload",
            "contentUrl": "https://example.org/new.zip",
            "name": "Download",
        }
    ]


def test_multivalued_metadata_is_not_truncated(record):
    record.update(
        {
            "dct_creator_sm": [f"Author {i}" for i in range(12)],
            "dcat_keyword_sm": [f"Keyword {i}" for i in range(30)],
            "dct_spatial_sm": [f"Place {i}" for i in range(8)],
            "dct_description_sm": ["First description", "Second description"],
            "dct_language_sm": ["eng", "fra"],
            "dct_references_s": {
                "http://schema.org/downloadUrl": [
                    {"url": f"https://example.org/{i}.zip"} for i in range(7)
                ]
            },
        }
    )
    graph = resource_jsonld(record, record["id"])
    assert len(graph["author"]) == 12
    assert len(graph["keywords"]) == 30
    assert len(graph["spatialCoverage"]) == 9
    assert len(graph["distribution"]) == 7
    assert graph["description"] == record["dct_description_sm"]
    assert graph["inLanguage"] == ["eng", "fra"]
    SchemaOrgCitationResponse.model_validate(graph)
    expand(graph)


@pytest.mark.parametrize(
    "bbox", ["NaN,44,-93,45", "-94,95,-93,100", "not geometry", "ENVELOPE(-94,-93,45,44"]
)
def test_invalid_geometry_not_claimed_as_geoshape_or_wkt(record, bbox):
    record["dcat_bbox"] = bbox
    graph = resource_jsonld(record, record["id"])
    assert "spatialCoverage" not in graph


def test_envelope_and_literal_license(record):
    record["dcat_bbox"] = "ENVELOPE(-94,-93,45,44)"
    record["dct_license_sm"] = ["Permission required"]
    record["dct_issued_s"] = "circa 1900"
    graph = resource_jsonld(record, record["id"])
    assert graph["spatialCoverage"][0]["geo"]["box"] == "44 -94 45 -93"
    assert graph["license"] == [{"@type": "CreativeWork", "text": "Permission required"}]
    assert "datePublished" not in graph
    assert graph[DCT + "issued"] == "circa 1900"
    expand(graph)


@pytest.mark.parametrize(
    "kind,expected",
    [("Maps", "Map"), ("Collections", "Collection"), ("Web services", "CreativeWork")],
)
def test_non_dataset_types_do_not_claim_dataset_only_properties(record, kind, expected):
    record["gbl_resourceClass_sm"] = [kind]
    graph = resource_jsonld(record, "a b#c", base_url="https://example.org/api/v1/")
    assert graph["@type"] == expected
    assert graph["@id"] == "https://example.org/resources/a%20b%23c"
    assert "includedInDataCatalog" not in graph
    assert "distribution" not in graph
    assert graph["encoding"][0]["@type"] == "MediaObject"
    expand(graph)


def test_invalid_references_do_not_break_serialization(record):
    for references in (
        "{bad JSON",
        [],
        {
            "http://schema.org/downloadUrl": [
                {"url": "https://[invalid"},
                {"url": "javascript:alert(1)"},
                {"url": "relative/path"},
            ]
        },
    ):
        record["dct_references_s"] = references
        assert "distribution" not in resource_jsonld(record, record["id"])


def test_rights_are_resource_nodes_and_coordinates_keep_precision(record):
    record["dct_rights_sm"] = ["https://example.org/rights", "Attribution required"]
    record["dcat_bbox"] = "-94.123456789,44.123456789,-93.123456789,45.123456789"
    expanded = expand(resource_jsonld(record, record["id"]))
    assert expanded[DCT + "rights"][0] == {"@id": "https://example.org/rights"}
    assert expanded[DCT + "rights"][1]["@type"] == [DCT + "RightsStatement"]
    assert expanded[SCHEMA + "spatialCoverage"][0][SCHEMA + "geo"][0][SCHEMA + "box"] == [
        {"@value": "44.123456789 -94.123456789 45.123456789 -93.123456789"}
    ]


def test_advertised_profiles_are_jsonld_with_matching_identities():
    from app.api.v1.utils import create_jsonapi_response

    root = Path(__file__).resolve().parents[3] / "mkdocs/docs/v1/ld/profiles"
    for uri in create_jsonapi_response([])["jsonapi"]["profile"]:
        profile = json.loads((root / uri.rsplit("/", 1)[-1]).read_text())
        expanded = expand(profile)
        assert expanded["@id"] == uri
        assert expanded["@type"] == ["http://www.w3.org/ns/dx/prof/Profile"]
        descriptor = expanded["http://www.w3.org/ns/dx/prof/hasResource"][0]
        assert descriptor["http://www.w3.org/ns/dx/prof/hasArtifact"][0]["@id"].startswith(
            "https://"
        )


def test_citation_http_response_is_processable_jsonld(record, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.endpoint_modules.resources import citation

    monkeypatch.setenv("GEOPORTAL_BASE_URL", "https://example.org")
    session = AsyncMock()
    result = MagicMock()
    result.fetchone.return_value = SimpleNamespace(_mapping=record)
    session.execute.return_value = result
    session_factory = MagicMock()
    session_factory.return_value.__aenter__.return_value = session
    monkeypatch.setattr(citation, "async_session", session_factory)
    monkeypatch.setattr(citation, "fetch_distribution_context", AsyncMock(return_value=None))
    app = FastAPI()
    app.include_router(citation.router, prefix="/api/v1")
    content = app.openapi()["paths"]["/api/v1/resources/{id}/citation/json-ld"]["get"]["responses"][
        "200"
    ]["content"]
    assert set(content) == {"application/ld+json"}
    assert content["application/ld+json"]["schema"]["$ref"].endswith("SchemaOrgCitationResponse")
    resource = ResourcePresenter.serialize_jsonapi_resource(record)
    link = resource["links"]["alternate"]
    assert link["type"] == "application/ld+json"
    response = TestClient(app).get(link["href"])
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/ld+json"
    assert expand(response.json())["@type"] == [SCHEMA + "Dataset"]
    assert response.json() == resource_jsonld(record, record["id"])
    assert "jsonld" not in resource["meta"]


def test_database_field_aliases_have_the_same_graph(record):
    lowercase = {field.lower(): value for field, value in record.items()}
    assert resource_jsonld(lowercase, record["id"]) == resource_jsonld(record, record["id"])


def test_resource_links_to_jsonld_without_building_a_duplicate_graph(record, monkeypatch):
    def unexpected_projection(*args, **kwargs):
        raise AssertionError("Ordinary resources must not build JSON-LD")

    monkeypatch.setattr("app.services.linked_data.resource_jsonld", unexpected_projection)
    record["id"] = "a b#c?"
    resource = ResourcePresenter.serialize_jsonapi_resource(record)

    assert resource["meta"] == {"ui": {}}
    assert resource["attributes"]["ogm"]["dct_title_s"] == "Address points"
    assert resource["links"]["alternate"] == {
        "href": "/api/v1/resources/a%20b%23c%3F/citation/json-ld",
        "type": "application/ld+json",
    }


def test_all_provenance_fields_are_retained_without_duplicate_statements(record):
    record["b1g_dct_provenance_sm"] = ["Original source", "https://example.org/provenance"]
    record["b1g_dct_provenanceStatement_sm"] = ["Exported to GeoPackage", "Original source"]
    graph = expand(resource_jsonld(record, record["id"]))
    assert graph[DCT + "provenance"] == [
        {SCHEMA + "description": [{"@value": "Original source"}]},
        {"@id": "https://example.org/provenance"},
        {SCHEMA + "description": [{"@value": "Exported to GeoPackage"}]},
    ]


@pytest.mark.parametrize(
    "target",
    [
        "https://[invalid",
        "https:///missing-host",
        "https://example.org:bad/id",
        "https://example.org/%GG",
        "https://example.org/a\x00b",
        "https://example.org:99999/id",
        "//example.org/collection",
        "../collection",
        "#collection",
    ],
)
def test_malformed_relationship_references_never_invent_local_identities(record, target):
    record["pcdm_memberOf_sm"] = [target]
    graph = expand(resource_jsonld(record, record["id"]))
    assert PCDM + "memberOf" not in graph


@pytest.mark.parametrize(
    "target",
    [
        "https://example.org/caf\u00e9",
        "urn:uuid:12345678-1234-1234-1234-123456789012",
        "doi:10.1234/example",
        "tag:example.org,2026:collection",
    ],
)
def test_absolute_identifier_schemes_are_preserved(record, target):
    record["pcdm_memberOf_sm"] = [target, target]
    graph = resource_jsonld(record, record["id"])
    assert graph[PCDM + "memberOf"] == [{"@id": target}]
    assert expand(graph)[PCDM + "memberOf"] == [{"@id": target}]
    rdf = jsonld.to_rdf(graph, options={"format": "application/n-quads"})
    assert f"<{target}>" in rdf


def test_dates_are_canonical_typed_rdf_literals(record):
    record["dct_issued_s"] = "20250703"
    graph = resource_jsonld(record, record["id"])
    assert graph["datePublished"] == "2025-07-03"
    assert expand(graph)[SCHEMA + "datePublished"] == [
        {
            "@value": "2025-07-03",
            "@type": "http://www.w3.org/2001/XMLSchema#date",
        }
    ]


def test_default_citation_identity_matches_embedded_graph(record, monkeypatch):
    monkeypatch.setenv("GEOPORTAL_BASE_URL", "https://example.org")
    service = CitationFormatsService(record)
    assert service.to_json_ld(record["id"]) == resource_jsonld(record, record["id"])
    assert "https://example.org/resources/a%20b%23c" in service.to_ris("a b#c")
