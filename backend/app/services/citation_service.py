import logging
import re
from typing import Dict, List, Literal, Optional

from app.services.distribution_repository import (
    DistributionContext,
    build_distribution_context,
)

logger = logging.getLogger(__name__)

CitationStyle = Literal["default", "apa", "mla", "chicago"]


class CitationService:
    """Service for generating citations in multiple formal styles."""

    def __init__(
        self,
        document: Dict,
        distribution_context: Optional[DistributionContext] = None,
    ):
        self.document = document
        if distribution_context is None:
            distribution_context = build_distribution_context(document.get("id", ""), [])
        self.distribution_context = distribution_context
        self.by_uri = distribution_context.by_uri

    def _extract_year(self) -> str:
        """Extract 4-digit year from issued date."""
        date = self.document.get("dct_issued_s")
        if not date:
            return "n.d."
        match = re.search(r"\d{4}", str(date))
        return match.group(0) if match else "n.d."

    def _get_url(self) -> Optional[str]:
        """Get the primary URL for the document."""
        # Prefer distribution context first
        if url_records := self.by_uri.get("http://schema.org/url"):
            return url_records[0].url
        if download_records := self.by_uri.get("http://schema.org/downloadUrl"):
            return download_records[0].url
        # Fallback to legacy dct_references_s on the document
        refs = self._parse_references()
        val = refs.get("http://schema.org/url")
        if isinstance(val, str):
            return val
        val = refs.get("http://schema.org/downloadUrl")
        if isinstance(val, str):
            return val
        return None

    def _get_resource_type(self) -> str:
        """Get the resource type with error handling."""
        resource_types = self.document.get("gbl_resourceType_sm") or self.document.get(
            "gbl_resourcetype_sm", []
        )
        if isinstance(resource_types, list) and resource_types:
            return resource_types[0] if isinstance(resource_types[0], str) else ""
        return ""

    def _get_creators(self) -> List[str]:
        """Get creators with error handling."""
        creators = self.document.get("dct_creator_sm", [])
        if isinstance(creators, list):
            return [c for c in creators if isinstance(c, str) and c.strip()]
        return []

    def _get_publishers(self) -> List[str]:
        """Get publishers with error handling."""
        publishers = self.document.get("dct_publisher_sm", [])
        if isinstance(publishers, list):
            return [p for p in publishers if isinstance(p, str) and p.strip()]
        return []

    def get_citation(self, style: CitationStyle = "default") -> str:
        """Generate a citation string in the specified style."""
        try:
            if style == "default":
                return self._format_default()
            if style == "apa":
                return self._format_apa()
            if style == "mla":
                return self._format_mla()
            if style == "chicago":
                return self._format_chicago()
            return self._format_default()
        except Exception as e:
            logger.error(f"Citation generation failed ({style}): {str(e)}")
            logger.error(f"Document: {self.document}")
            return "Citation unavailable"

    def get_all_citations(self) -> Dict[str, str]:
        """Return citations in all supported styles (APA, MLA, Chicago)."""
        return {
            "apa": self.get_citation("apa"),
            "mla": self.get_citation("mla"),
            "chicago": self.get_citation("chicago"),
        }

    def _get_apa_publisher(self) -> str:
        """Publisher or provider for APA."""
        resource_type = self._get_resource_type().lower()
        provider = self.document.get("schema_provider_s")
        provider_text = provider.strip() if isinstance(provider, str) else ""
        if resource_type in ["datasets", "web services"]:
            return provider_text

        publishers = self._get_publishers()
        return publishers[0] if publishers else provider_text

    def _get_descriptor(self) -> str:
        """Bracketed descriptor [Data set], [Map], etc."""
        rt = self._get_resource_type().lower()
        if rt in ["datasets", "dataset"]:
            return "[Data set]"
        if rt in ["web services", "web service"]:
            return "[Data set]"
        if rt in ["maps", "map", "imagery", "imagery and other"]:
            return "[Map]"
        return ""

    def _get_singular_resource_type(self) -> str:
        """Singular, lowercase resource type for legacy default citation."""
        rt = self._get_resource_type().strip().lower()
        if not rt:
            return ""
        if rt.endswith("ies") and len(rt) > 3:
            return rt[:-3] + "y"
        if rt.endswith("s") and len(rt) > 1:
            return rt[:-1]
        return rt

    def _get_default_date(self) -> str:
        """Date string for default citation style."""
        issued = self.document.get("dct_issued_s")
        if issued is None:
            return "n.d."
        if isinstance(issued, str):
            return issued.strip() or "n.d."
        return str(issued)

    def _get_default_title(self) -> str:
        """Title string for default citation style."""
        title = self.document.get("dct_title_s")
        if isinstance(title, str):
            return title.strip() or "Untitled"
        return "Untitled"

    def _get_default_author(self) -> str:
        """Creator list for default citation style."""
        creators = self._get_creators()
        if creators:
            return ", ".join(creators) + "."
        return "[Creator not found],"

    def _format_default(self) -> str:
        """
        Legacy default citation format used by UI and existing tests:
        Author. (Date). Title. (resource type). Publisher. URL
        """
        author = self._get_default_author()
        date = self._get_default_date()
        title = self._get_default_title()
        publisher = self._get_apa_publisher()
        resource_type = self._get_singular_resource_type()
        url = self._get_url() or ""

        parts: List[str] = [f"{author} ({date}).", f"{title}."]
        if resource_type:
            parts.append(f"({resource_type}).")
        if publisher:
            parts.append(f"{publisher}.")
        if url:
            parts.append(url)
        return " ".join(parts)

    def _format_apa(self) -> str:
        """APA 7th edition: Author. (Year). Title [Descriptor]. Publisher. URL"""
        creators = self._get_creators()
        author = ", ".join(creators) if creators else "Unknown"
        if creators and len(creators) > 1:
            author = ", ".join(creators[:-1]) + ", & " + creators[-1]
        year = self._extract_year()
        title = self._get_default_title()
        descriptor = self._get_descriptor()
        publisher = self._get_apa_publisher()
        url = self._get_url() or ""

        title_part = f"{title} {descriptor}".strip() if descriptor else title
        out = f"{author}. ({year}). {title_part}."
        if publisher:
            out += f" {publisher}."
        if url:
            out += f" {url}"
        return out

    def _format_mla(self) -> str:
        """MLA 9th edition: Author. "Title." Container, Publisher, Date, URL."""
        creators = self._get_creators()
        author = ", ".join(creators) if creators else "Unknown"
        if len(creators) > 1:
            author = ", ".join(creators[:-1]) + ", and " + creators[-1]
        title = self.document.get("dct_title_s") or "Untitled"
        publisher = self._get_apa_publisher() or "Big Ten Academic Alliance Geoportal"
        date = self.document.get("dct_issued_s") or "n.d."
        url = self._get_url() or ""

        out = f'{author}. "{title}." '
        out += f"Big Ten Academic Alliance Geoportal, {publisher}, {date}"
        if url:
            out += f", {url}"
        out += "."
        return out

    def _format_chicago(self) -> str:
        """Chicago author-date: Author. Year. "Title." Publisher. URL."""
        creators = self._get_creators()
        author = ", ".join(creators) if creators else "Unknown"
        if len(creators) > 1:
            author = ", ".join(creators[:-1]) + ", and " + creators[-1]
        year = self._extract_year()
        title = self.document.get("dct_title_s") or "Untitled"
        publisher = self._get_apa_publisher() or "Big Ten Academic Alliance Geoportal"
        url = self._get_url() or ""

        out = f'{author}. {year}. "{title}." {publisher}.'
        if url:
            out += f" {url}."
        return out

    def _parse_references(self) -> Dict:
        """Parse legacy dct_references_s if present on the document."""
        raw = self.document.get("dct_references_s")
        if isinstance(raw, str):
            try:
                import json

                raw = json.loads(raw)
            except Exception:
                raw = None
        return raw if isinstance(raw, dict) else {}
