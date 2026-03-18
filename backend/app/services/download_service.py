import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
from urllib.parse import urlencode

from sqlalchemy import select

from app.services.distribution_repository import (
    DistributionContext,
    build_distribution_context,
)
from db.database import database
from db.models import resource_assets

logger = logging.getLogger(__name__)


@dataclass
class DownloadOption:
    """Represents a download option with its parameters."""

    label: str
    type: str
    extension: str
    service_type: str
    content_type: str
    request_params: Dict
    reflect: bool = False


class IIIFDownloadService:
    """Service for generating IIIF image download options."""

    # Standard IIIF image sizes
    SIZES = {
        "thumb": {"width": 150, "height": 150},
        "small": {"width": 800, "height": 800},
        "medium": {"width": 1200, "height": 1200},
        "large": {"width": 2000, "height": 2000},
    }

    def __init__(self, references_or_endpoint: Optional[object]):
        """
        Initialize with references dict (legacy) or a direct IIIF Image API endpoint string.
        """
        endpoint: Optional[str] = None
        self.manifest_url: Optional[str] = None
        if isinstance(references_or_endpoint, str) or references_or_endpoint is None:
            endpoint = references_or_endpoint  # type: ignore[assignment]
        elif isinstance(references_or_endpoint, dict):
            # Legacy: extract from references map
            endpoint = references_or_endpoint.get("http://iiif.io/api/image")  # type: ignore[index]
            if not isinstance(endpoint, str):
                endpoint = None
            manifest = references_or_endpoint.get("http://iiif.io/api/presentation#manifest")  # type: ignore[index]
            if isinstance(manifest, str):
                self.manifest_url = manifest
        self.image_api_endpoint = endpoint

    def get_download_options(self) -> List[Dict]:
        """Generate download options for IIIF images."""
        if not self.image_api_endpoint:
            return []

        # Remove /info.json from endpoint if present
        base_url = self.image_api_endpoint.replace("/info.json", "")

        downloads = []

        # Add standard size options
        for size_name, dimensions in self.SIZES.items():
            downloads.append(
                {
                    "label": f"{size_name.title()} Image",
                    "url": (
                        f"{base_url}/full/{dimensions['width']},"
                        f"{dimensions['height']}/0/default.jpg"
                    ),
                    "type": "image/jpeg",
                }
            )

        # Add full size option
        downloads.append(
            {
                "label": "Full Resolution Image",
                "url": f"{base_url}/full/full/0/default.jpg",
                "type": "image/jpeg",
            }
        )

        return downloads


class DownloadService:
    """Service for generating download options for documents."""

    def __init__(
        self,
        document: Dict,
        distribution_context: Optional[DistributionContext] = None,
    ):
        """Initialize with document."""
        self.document = document
        self.wxs_identifier = document.get("gbl_wxsidentifier_s", "")
        if distribution_context is None:
            resource_id = document.get("id", "")
            distribution_context = build_distribution_context(resource_id, [])
        self.distribution_context = distribution_context
        self.by_uri = self.distribution_context.by_uri
        self._legacy_refs_cache: Optional[Dict] = None

    def _get_direct_downloads(self) -> List[Dict]:
        """Get direct download URLs from schema.org references."""
        downloads = []
        # Prefer distribution context
        download_records = self.by_uri.get("http://schema.org/downloadUrl", [])

        for record in download_records:
            label = record.label or self._default_download_label(record.url)
            fmt = self._guess_format(record.url)
            downloads.append(
                {
                    "label": label,
                    "url": record.url,
                    "type": fmt,
                    "format": fmt,
                }
            )

        # Fallback to legacy references if none found
        if not downloads:
            refs = self._parse_references()
            val = refs.get("http://schema.org/downloadUrl")
            if isinstance(val, str):
                fmt = self._guess_format(val)
                downloads.append(
                    {
                        "label": self._default_download_label(val),
                        "url": val,
                        "type": fmt,
                        "format": fmt,
                    }
                )
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        url = item
                        label = self._default_download_label(url)
                        fmt = self._guess_format(url)
                    elif isinstance(item, dict):
                        url = item.get("url")
                        label = item.get("label") or (
                            self._default_download_label(url) if url else None
                        )
                        fmt = self._guess_format(url) if url else "unknown"
                    else:
                        continue
                    if not url:
                        continue
                    downloads.append(
                        {
                            "label": label or self._default_download_label(url),
                            "url": url,
                            "type": fmt,
                            "format": fmt,
                        }
                    )
            elif isinstance(val, dict):
                url = val.get("url")
                if url:
                    fmt = self._guess_format(url)
                    label = val.get("label") or self._default_download_label(url)
                    downloads.append(
                        {
                            "label": label,
                            "url": url,
                            "type": fmt,
                            "format": fmt,
                        }
                    )

        return downloads

    def _guess_format(self, url: str) -> str:
        """Guess the format from the URL."""
        if url.lower().endswith(".zip"):
            return "zip"
        elif url.lower().endswith(".pdf"):
            return "pdf"
        elif url.lower().endswith(".tif") or url.lower().endswith(".tiff"):
            return "tiff"
        elif url.lower().endswith(".json"):
            return "json"
        return "unknown"

    def _get_service_url(self, service_type: str) -> Optional[str]:
        """Get the endpoint URL for a specific service type."""
        service_map = {
            "wfs": "http://www.opengis.net/def/serviceType/ogc/wfs",
            "wms": "http://www.opengis.net/def/serviceType/ogc/wms",
        }
        uri = service_map.get(service_type)
        if not uri:
            return None
        records = self.by_uri.get(uri, [])
        if records:
            return records[0].url
        # Fallback to legacy refs
        refs = self._parse_references()
        val = refs.get(uri)
        return val if isinstance(val, str) else None

    def _build_download_url(self, option: DownloadOption) -> Optional[str]:
        """Build the download URL with parameters."""
        base_url = self._get_service_url(option.service_type)
        if not base_url:
            return None

        url = f"{base_url}/reflect" if option.reflect else base_url
        return f"{url}?{urlencode(option.request_params)}"

    def get_download_options(self) -> List[Dict]:
        """Get all available download options."""
        downloads = []

        # Check for IIIF image API
        iiif_image_url = self._first_url("http://iiif.io/api/image")
        if iiif_image_url:
            iiif_service = IIIFDownloadService(iiif_image_url)
            downloads.extend(iiif_service.get_download_options())

        # Add direct download URLs (handles dict/list/string)
        downloads.extend(self._get_direct_downloads())

        return downloads

    def _first_url(self, uri: str) -> Optional[str]:
        records = self.by_uri.get(uri, [])
        if records:
            return records[0].url
        refs = self._parse_references()
        val = refs.get(uri)
        if isinstance(val, str):
            return val
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("url")
        if isinstance(val, dict):
            return val.get("url")
        return None

    def _default_download_label(self, url: str) -> str:
        format_type = self._guess_format(url)
        return f"Download {format_type.upper()}"

    def _parse_references(self) -> Dict:
        """
        Legacy helper: parse dct_references_s from the document if present
        and return a URI->value map.
        """
        if self._legacy_refs_cache is not None:
            return self._legacy_refs_cache
        refs = {}
        raw = self.document.get("dct_references_s")
        if isinstance(raw, str):
            try:
                import json

                raw = json.loads(raw)
            except Exception:
                raw = None
        if isinstance(raw, dict):
            refs = raw
        self._legacy_refs_cache = refs
        return refs

    def _format_file_size(self, file_size: Optional[int]) -> Optional[str]:
        """Format file sizes for UI labels."""
        if file_size is None:
            return None
        try:
            size = int(file_size)
        except (TypeError, ValueError):
            return None

        if size < 1024:
            return f"{size} bytes"

        units = ["KB", "MB", "GB", "TB", "PB"]
        value = float(size)
        unit_index = -1
        while value >= 1024 and unit_index < len(units) - 1:
            value /= 1024
            unit_index += 1

        # Keep it compact: 1 decimal place is usually enough.
        unit = units[max(unit_index, 0)]
        return f"{value:.1f} {unit}"

    async def get_download_options_with_bridge_asset_downloads(
        self,
    ) -> List[Dict]:
        """
        Extend `get_download_options()` with downloads coming from `resource_assets`.

        The bridge API stores these in:
        - `resource_assets.dct_references_uri_key == "download"`
        - `resource_assets.file_url` for the actual link
        - `resource_assets.file_size` for UI label size hints
        - `resource_assets.label` for the link text
        """
        base_downloads = self.get_download_options()

        resource_id = self.document.get("id") or ""
        if not resource_id:
            return base_downloads

        try:
            if not database.is_connected:
                await database.connect()

            query = (
                select(
                    resource_assets.c.label,
                    resource_assets.c.title,
                    resource_assets.c.file_url,
                    resource_assets.c.file_mime_type,
                    resource_assets.c.file_size,
                    resource_assets.c.position,
                    resource_assets.c.id,
                )
                .where(
                    resource_assets.c.resource_id == resource_id,
                    resource_assets.c.dct_references_uri_key == "download",
                    resource_assets.c.file_url.is_not(None),
                )
                .order_by(resource_assets.c.position.asc(), resource_assets.c.id.asc())
            )

            rows = await database.fetch_all(query)
        except Exception:
            logger.exception(
                "Failed to fetch bridge asset downloads for resource %s",
                resource_id,
            )
            return base_downloads

        existing_by_url = {d.get("url"): d for d in base_downloads if d.get("url")}
        downloads: List[Dict] = list(base_downloads)

        for row in rows:
            # `databases` Record behaves like a mapping; dict works too in tests.
            try:
                file_url = row["file_url"]
                label = row["label"]
                title = row["title"]
                file_size = row["file_size"]
                file_mime_type = row["file_mime_type"]
            except Exception:
                continue

            if not isinstance(file_url, str):
                continue
            file_url = file_url.strip()
            if not file_url:
                continue

            if not label:
                label = title
            if not label:
                label = self._default_download_label(file_url)

            formatted_size = self._format_file_size(file_size)
            display_label = f"{label} ({formatted_size})" if formatted_size else str(label)

            type_value = file_mime_type if isinstance(file_mime_type, str) else "unknown"

            if file_url in existing_by_url:
                continue

            downloads.append(
                {
                    "label": display_label,
                    "url": file_url,
                    "type": type_value,
                    "format": type_value,
                }
            )

        return downloads
