"""Service for converting resource metadata to citation-friendly formats.

Supports JSON-LD (Schema.org), RIS, and BibTeX for ingestion by Zotero,
EndNote, Mendeley, and other citation tools.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.services.distribution_repository import DistributionContext


def _ensure_list(val: Any) -> List[str]:
    """Ensure value is a list of strings, filtering None/empty."""
    if val is None:
        return []
    if isinstance(val, str):
        return [val] if val.strip() else []
    if isinstance(val, list):
        return [str(v).strip() for v in val if v is not None and str(v).strip()]
    return []


def _first(val: Any) -> Optional[str]:
    """Return first element of list or scalar."""
    lst = _ensure_list(val)
    return lst[0] if lst else None


def _strip_suffix(s: str, suffix: str) -> str:
    """Remove trailing suffix if present."""
    if s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def _bibtex_sanitize(s: str) -> str:
    """Sanitize string for BibTeX (escape braces and special chars)."""
    if not s:
        return ""
    s = s.replace("{", "{{").replace("}", "}}")
    # BibTeX doesn't like unescaped special chars
    s = s.replace("&", "\\&").replace("#", "\\#")
    return s


def _ris_escape(s: str) -> str:
    """Escape RIS-problematic characters if needed."""
    if not s:
        return ""
    # RIS uses newlines as record separators; replace internal newlines
    return s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ").strip()


class CitationFormatsService:
    """Convert resource metadata to JSON-LD, RIS, and BibTeX formats."""

    def __init__(
        self,
        document: Dict[str, Any],
        distribution_context: Optional[DistributionContext] = None,
        base_url: str = "https://geoportal.btaa.org",
    ):
        self.document = document
        self.distribution_context = distribution_context or DistributionContext(
            resource_id=document.get("id", ""),
            records=[],
            by_uri={},
            by_name={},
            reference_payload={},
            legacy_reference_payload={},
        )
        self.base_url = _strip_suffix(
            _strip_suffix(base_url.rstrip("/"), "/api/v1"), "/api/v1/"
        ).rstrip("/")

    def _resource_url(self, resource_id: str) -> str:
        """Canonical URL for the resource (Geoportal page)."""
        return f"{self.base_url}/resources/{resource_id}"

    def _get_url(self) -> Optional[str]:
        """Primary URL for the document."""
        by_uri = self.distribution_context.by_uri
        if url_records := by_uri.get("http://schema.org/url"):
            return url_records[0].url
        if dl_records := by_uri.get("http://schema.org/downloadUrl"):
            return dl_records[0].url
        refs = self._parse_references()
        val = refs.get("http://schema.org/url")
        if isinstance(val, str):
            return val
        val = refs.get("http://schema.org/downloadUrl")
        if isinstance(val, str):
            return val
        return None

    def _parse_references(self) -> Dict[str, Any]:
        raw = self.document.get("dct_references_s")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = None
        return raw if isinstance(raw, dict) else {}

    def _resource_type_for_schema(self) -> str:
        """Schema.org type: Dataset for data/services, Map for maps, else CreativeWork."""
        types = _ensure_list(self.document.get("gbl_resourceType_sm"))
        types_lower = [t.lower() for t in types]
        if any(t in types_lower for t in ("datasets", "dataset", "web services")):
            return "Dataset"
        if any(t in types_lower for t in ("maps", "map", "imagery", "imagery and other")):
            return "Map"
        return "CreativeWork"

    def _resource_type_for_ris(self) -> str:
        """RIS TY code: DATA for datasets, MAP for maps, GEN for generic."""
        types = _ensure_list(self.document.get("gbl_resourceType_sm"))
        types_lower = [t.lower() for t in types]
        if any(t in types_lower for t in ("datasets", "dataset", "web services")):
            return "DATA"
        if any(t in types_lower for t in ("maps", "map", "imagery", "imagery and other")):
            return "MAP"
        return "GEN"

    def _resource_type_for_bibtex(self) -> str:
        """BibTeX type: misc is most universal for maps/datasets."""
        return "misc"

    def to_json_ld(self, resource_id: str) -> Dict[str, Any]:
        """Produce Schema.org JSON-LD for the resource."""
        url = self._resource_url(resource_id)
        schema_type = self._resource_type_for_schema()
        title = _first(self.document.get("dct_title_s")) or "Untitled"
        desc_list = _ensure_list(self.document.get("dct_description_sm"))
        description = desc_list[0] if desc_list else None
        date = _first(self.document.get("dct_issued_s"))
        keywords = _ensure_list(self.document.get("dcat_keyword_sm")) + _ensure_list(
            self.document.get("dct_subject_sm")
        )
        spatial = _ensure_list(self.document.get("dct_spatial_sm"))
        temporal = _ensure_list(self.document.get("dct_temporal_sm"))
        languages = _ensure_list(self.document.get("dct_language_sm"))
        licenses = _ensure_list(self.document.get("dct_license_sm"))
        identifiers = _ensure_list(self.document.get("dct_identifier_sm"))
        creators = _ensure_list(self.document.get("dct_creator_sm"))
        publishers = _ensure_list(self.document.get("dct_publisher_sm"))
        provider = _first(self.document.get("schema_provider_s"))
        format_str = _first(self.document.get("dct_format_s"))
        access_rights = _first(self.document.get("dct_accessRights_s"))

        obj: Dict[str, Any] = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "@id": url,
            "url": url,
            "name": title,
        }
        if description:
            obj["description"] = description
        if date:
            obj["datePublished"] = date
        if keywords:
            obj["keywords"] = ", ".join(keywords[:20])  # Limit for readability
        if spatial:
            obj["spatialCoverage"] = [{"@type": "Place", "name": p} for p in spatial[:5]]
        if temporal:
            obj["temporalCoverage"] = temporal[0] if temporal else None
        if languages:
            obj["inLanguage"] = languages[0] if languages else None
        if licenses:
            obj["license"] = licenses[0] if licenses else None
        if identifiers:
            obj["identifier"] = identifiers[0] if len(identifiers) == 1 else identifiers
        if creators:
            obj["author"] = [
                {"@type": "Organization" if " " in c or "," in c else "Person", "name": c}
                for c in creators[:10]
            ]
        if publishers:
            obj["publisher"] = {
                "@type": "Organization",
                "name": publishers[0] if len(publishers) == 1 else ", ".join(publishers),
            }
        elif provider:
            obj["publisher"] = {"@type": "Organization", "name": provider}
        if format_str:
            obj["encodingFormat"] = format_str
        if access_rights:
            obj["accessMode"] = access_rights
        # Included in DataCatalog (Geoportal)
        obj["includedInDataCatalog"] = {
            "@type": "DataCatalog",
            "name": "Big Ten Academic Alliance Geoportal",
            "url": self.base_url,
        }
        # Distribution (download/view links)
        by_uri = self.distribution_context.by_uri
        distributions = []
        for _uri, records in by_uri.items():
            for r in records:
                distributions.append(
                    {
                        "@type": "DataDownload",
                        "contentUrl": r.url,
                        "encodingFormat": format_str or "application/octet-stream",
                    }
                )
        if distributions:
            obj["distribution"] = distributions[:5]
        # Primary link if no distribution
        if not distributions:
            prim = self._get_url()
            if prim:
                obj["url"] = [url, prim]

        return obj

    def to_ris(self, resource_id: str) -> str:
        """Produce RIS format text for the resource."""
        lines: List[str] = []
        ty = self._resource_type_for_ris()
        lines.append(f"TY  - {ty}")
        for creator in _ensure_list(self.document.get("dct_creator_sm"))[:20]:
            lines.append(f"AU  - {_ris_escape(creator)}")
        year = _first(self.document.get("dct_issued_s"))
        if year:
            # RIS year: 4 digits
            match = re.search(r"\d{4}", str(year))
            if match:
                lines.append(f"PY  - {match.group(0)}")
        title = _first(self.document.get("dct_title_s"))
        if title:
            lines.append(f"TI  - {_ris_escape(title)}")
        provider = _first(self.document.get("schema_provider_s"))
        if provider:
            lines.append(f"PB  - {_ris_escape(provider)}")
        else:
            for pub in _ensure_list(self.document.get("dct_publisher_sm"))[:3]:
                lines.append(f"PB  - {_ris_escape(pub)}")
        url = self._resource_url(resource_id)
        lines.append(f"UR  - {url}")
        desc_list = _ensure_list(self.document.get("dct_description_sm"))
        if desc_list:
            ab = _ris_escape(desc_list[0][:500])  # Limit length
            lines.append(f"AB  - {ab}")
        for kw in (
            _ensure_list(self.document.get("dcat_keyword_sm"))
            + _ensure_list(self.document.get("dct_subject_sm"))
        )[:15]:
            lines.append(f"KW  - {_ris_escape(kw)}")
        resource_type = _first(self.document.get("gbl_resourceType_sm"))
        if resource_type:
            lines.append(f"M1  - {_ris_escape(resource_type)}")
        spatial = _ensure_list(self.document.get("dct_spatial_sm"))
        if spatial:
            lines.append(f"N1  - Geographic coverage: {_ris_escape(', '.join(spatial[:5]))}")
        lines.append(f"DO  - {url}")
        lines.append("ER  - ")
        return "\n".join(lines)

    def to_bibtex(self, resource_id: str) -> str:
        """Produce BibTeX format for the resource."""
        cite_key = re.sub(r"[^\w]", "_", resource_id)[:50] or "geo"
        bt_type = self._resource_type_for_bibtex()
        lines: List[str] = [f"@{bt_type}{{{cite_key},"]
        title = _first(self.document.get("dct_title_s"))
        if title:
            lines.append(f"  title = {{{_bibtex_sanitize(title)}}},")
        authors = _ensure_list(self.document.get("dct_creator_sm"))
        if authors:
            lines.append(f"  author = {{{_bibtex_sanitize(' and '.join(authors[:10]))}}},")
        year = _first(self.document.get("dct_issued_s"))
        if year:
            match = re.search(r"\d{4}", str(year))
            if match:
                lines.append(f"  year = {{{match.group(0)}}},")
        provider = _first(self.document.get("schema_provider_s"))
        if provider:
            lines.append(f"  publisher = {{{_bibtex_sanitize(provider)}}},")
        url = self._resource_url(resource_id)
        lines.append(f"  url = {{{url}}},")
        resource_type = _first(self.document.get("gbl_resourceType_sm"))
        if resource_type:
            lines.append(f"  note = {{{_bibtex_sanitize(resource_type)}}},")
        lines.append("}")
        return "\n".join(lines)
