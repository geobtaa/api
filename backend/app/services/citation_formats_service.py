"""Service for converting resource metadata to citation-friendly formats.

Supports JSON-LD (Schema.org), RIS, and BibTeX for ingestion by Zotero,
EndNote, Mendeley, and other citation tools.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.services.distribution_repository import DistributionContext
from app.services.linked_data import geoportal_base_url, resource_jsonld, resource_uri


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
        base_url: Optional[str] = None,
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
            _strip_suffix((base_url or geoportal_base_url()).rstrip("/"), "/api/v1"), "/api/v1/"
        ).rstrip("/")

    def _resource_url(self, resource_id: str) -> str:
        """Canonical URL for the resource (Geoportal page)."""
        return resource_uri(resource_id, self.base_url)

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
        """Produce the same standalone graph embedded in public resource responses."""
        return resource_jsonld(
            self.document,
            resource_id,
            base_url=self.base_url,
            distribution_context=self.distribution_context,
        )

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
