"""Tests for CitationFormatsService (JSON-LD, RIS, BibTeX)."""

from app.services.citation_formats_service import CitationFormatsService
from app.services.distribution_repository import DistributionContext


def _minimal_distribution_context(resource_id: str) -> DistributionContext:
    return DistributionContext(
        resource_id=resource_id,
        records=[],
        by_uri={},
        by_name={},
        reference_payload={},
        legacy_reference_payload={},
    )


class TestCitationFormatsServiceJsonLd:
    """Tests for JSON-LD (Schema.org) output."""

    def test_json_ld_minimal_dataset(self):
        doc = {
            "id": "test-uuid-123",
            "dct_title_s": "Test Dataset",
            "dct_description_sm": ["A test dataset."],
            "gbl_resourceType_sm": ["Datasets"],
            "schema_provider_s": "University of Test",
        }
        ctx = _minimal_distribution_context("test-uuid-123")
        svc = CitationFormatsService(
            doc, distribution_context=ctx, base_url="https://geo.example.org"
        )
        ld = svc.to_json_ld("test-uuid-123")
        assert ld["@context"] == "https://schema.org"
        assert ld["@type"] == "Dataset"
        assert ld["name"] == "Test Dataset"
        assert ld["description"] == "A test dataset."
        assert ld["url"] == "https://geo.example.org/resources/test-uuid-123"
        assert ld["@id"] == ld["url"]
        assert ld["publisher"]["name"] == "University of Test"
        assert ld["includedInDataCatalog"]["name"] == "Big Ten Academic Alliance Geoportal"

    def test_json_ld_map_type(self):
        doc = {
            "id": "map-456",
            "dct_title_s": "Historic Map",
            "gbl_resourceType_sm": ["Maps"],
        }
        svc = CitationFormatsService(doc, base_url="https://geo.example.org")
        ld = svc.to_json_ld("map-456")
        assert ld["@type"] == "Map"

    def test_json_ld_creators_and_keywords(self):
        doc = {
            "id": "xyz",
            "dct_title_s": "T",
            "dct_creator_sm": ["Author One", "Author Two"],
            "dcat_keyword_sm": ["GIS", "maps"],
            "dct_subject_sm": ["Geography"],
        }
        svc = CitationFormatsService(doc, base_url="https://geo.example.org")
        ld = svc.to_json_ld("xyz")
        assert len(ld["author"]) == 2
        assert "GIS" in ld["keywords"] and "Geography" in ld["keywords"]


class TestCitationFormatsServiceRis:
    """Tests for RIS format output."""

    def test_ris_structure(self):
        doc = {
            "id": "r-1",
            "dct_title_s": "Test Resource",
            "dct_creator_sm": ["Smith, John"],
            "dct_issued_s": "2023",
            "schema_provider_s": "Test Library",
        }
        svc = CitationFormatsService(doc, base_url="https://geo.example.org")
        ris = svc.to_ris("r-1")
        lines = ris.strip().split("\n")
        assert lines[0] == "TY  - GEN"
        assert any("TI  - Test Resource" in line for line in lines)
        assert any("AU  - Smith, John" in line for line in lines)
        assert any("PY  - 2023" in line for line in lines)
        assert any(line.strip().startswith("ER  -") for line in lines)

    def test_ris_dataset_type(self):
        doc = {"id": "d-1", "dct_title_s": "D", "gbl_resourceType_sm": ["Datasets"]}
        svc = CitationFormatsService(doc, base_url="https://geo.example.org")
        ris = svc.to_ris("d-1")
        assert "TY  - DATA" in ris

    def test_ris_map_type(self):
        doc = {"id": "m-1", "dct_title_s": "M", "gbl_resourceType_sm": ["Maps"]}
        svc = CitationFormatsService(doc, base_url="https://geo.example.org")
        ris = svc.to_ris("m-1")
        assert "TY  - MAP" in ris


class TestCitationFormatsServiceBibtex:
    """Tests for BibTeX format output."""

    def test_bibtex_structure(self):
        doc = {
            "id": "b-1",
            "dct_title_s": "BibTeX Test",
            "dct_creator_sm": ["Author, A."],
            "dct_issued_s": "2024",
        }
        svc = CitationFormatsService(doc, base_url="https://geo.example.org")
        bib = svc.to_bibtex("b-1")
        assert bib.startswith("@misc{")
        assert "title = {BibTeX Test}" in bib
        assert "year = {2024}" in bib
        assert "url = {https://geo.example.org/resources/b-1}" in bib


class TestCitationServiceFormalStyles:
    """Tests for APA, MLA, Chicago formatting in CitationService."""

    def test_apa_format(self):
        from app.services.citation_service import CitationService

        doc = {
            "id": "x",
            "dct_creator_sm": ["Smith, John"],
            "dct_issued_s": "2023",
            "dct_title_s": "Test Dataset",
            "schema_provider_s": "University Press",
            "gbl_resourceType_sm": ["Datasets"],
        }
        svc = CitationService(doc)
        apa = svc.get_citation("apa")
        assert "Smith" in apa
        assert "(2023)." in apa
        assert "Test Dataset" in apa
        assert "[Data set]" in apa
        assert "University Press" in apa

    def test_mla_format(self):
        from app.services.citation_service import CitationService

        doc = {
            "dct_creator_sm": ["Doe, Jane"],
            "dct_title_s": "Historic Map",
            "dct_issued_s": "2022",
            "gbl_resourceType_sm": ["Maps"],
        }
        svc = CitationService(doc)
        mla = svc.get_citation("mla")
        assert "Doe, Jane." in mla
        assert '"Historic Map."' in mla
        assert "Big Ten Academic Alliance Geoportal" in mla

    def test_chicago_format(self):
        from app.services.citation_service import CitationService

        doc = {
            "dct_creator_sm": ["Author, A."],
            "dct_title_s": "Chicago Test",
            "dct_issued_s": "2024",
        }
        svc = CitationService(doc)
        chicago = svc.get_citation("chicago")
        assert "Author" in chicago
        assert "2024" in chicago
        assert "Chicago Test" in chicago
        assert "Big Ten Academic Alliance" in chicago

    def test_get_all_citations(self):
        from app.services.citation_service import CitationService

        doc = {
            "dct_creator_sm": ["Creator"],
            "dct_title_s": "Title",
            "dct_issued_s": "2020",
        }
        svc = CitationService(doc)
        all_cits = svc.get_all_citations()
        assert set(all_cits.keys()) == {"apa", "mla", "chicago"}
        assert all(isinstance(v, str) for v in all_cits.values())
