import asyncio
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlencode

import requests
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

    GENERATED_DOWNLOAD_OPTIONS = {
        "shapefile": {
            "label": "EPSG:4326 Shapefile",
            "extension": "zip",
            "content_type": "application/zip",
            "service_type": "wfs",
            "reflect": False,
            "request_params": {
                "service": "wfs",
                "version": "2.0.0",
                "request": "GetFeature",
                "srsName": "EPSG:4326",
                "outputformat": "SHAPE-ZIP",
            },
        },
        "geojson": {
            "label": "GeoJSON",
            "extension": "geojson",
            "content_type": "application/json",
            "service_type": "wfs",
            "reflect": False,
            "request_params": {
                "service": "wfs",
                "version": "2.0.0",
                "request": "GetFeature",
                "srsName": "EPSG:4326",
                "outputformat": "application/json",
            },
        },
        "csv": {
            "label": "CSV",
            "extension": "csv",
            "content_type": "text/csv",
            "service_type": "wfs",
            "reflect": False,
            "request_params": {
                "service": "wfs",
                "version": "2.0.0",
                "request": "GetFeature",
                "srsName": "EPSG:4326",
                "outputformat": "csv",
            },
        },
        "kmz": {
            "label": "KMZ",
            "extension": "kmz",
            "content_type": "application/vnd.google-earth.kmz",
            "service_type": "wms",
            "reflect": False,
            "request_params": {
                "service": "wms",
                "version": "1.1.0",
                "request": "GetMap",
                "srsName": "EPSG:3857",
                "format": "application/vnd.google-earth.kmz",
                "width": 2000,
                "height": 2000,
            },
        },
        "geotiff": {
            "label": "GeoTIFF",
            "extension": "tif",
            "content_type": "image/geotiff",
            "service_type": "wms",
            "reflect": True,
            "request_params": {
                "format": "image/geotiff",
                "width": 4096,
            },
        },
    }
    GENERATED_CONTENT_TYPE_FALLBACKS = {
        "application/zip": {"application/octet-stream"},
        "application/vnd.google-earth.kmz": {"application/octet-stream"},
        "text/csv": {"application/csv", "application/vnd.ms-excel", "application/octet-stream"},
        "image/geotiff": {"image/tiff", "application/octet-stream"},
    }

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
        downloads.extend(self.get_generated_download_options())

        return downloads

    def get_generated_download_options(self) -> List[Dict]:
        """
        Return generated download links that mirror GeoBlacklight behavior.

        These links are not direct files; they point to an API route that prepares
        and caches the derived file on demand.
        """
        resource_id = self.document.get("id")
        if not isinstance(resource_id, str) or not resource_id.strip():
            return []

        options: List[Dict] = []
        for download_type in ("shapefile", "kmz", "geojson", "csv", "geotiff"):
            try:
                spec = self._build_generated_download_spec(download_type)
            except ValueError:
                continue

            prepare_path = f"/api/v1/resources/{resource_id}/downloads/generated/{download_type}"
            options.append(
                {
                    "label": spec.label,
                    "url": prepare_path,
                    "type": spec.content_type,
                    "format": download_type,
                    "generated": True,
                    "download_type": download_type,
                    "generation_path": prepare_path,
                }
            )

        return options

    @staticmethod
    def generated_download_directory() -> Path:
        configured = os.getenv("DOWNLOAD_PATH", "").strip()
        if configured:
            return Path(configured)

        # data-api/backend/app/services/download_service.py -> data-api/
        project_root = Path(__file__).resolve().parents[3]
        return project_root / "tmp" / "cache" / "downloads"

    async def ensure_generated_download(self, download_type: str) -> Dict[str, str]:
        """Create a generated file (if needed) and return file metadata."""
        spec = self._build_generated_download_spec(download_type)

        file_path = self.generated_download_directory() / spec.file_name
        if not file_path.exists():
            await asyncio.to_thread(self._create_generated_download_file, spec, file_path)

        resource_id = self.document.get("id")
        return {
            "download_type": spec.download_type,
            "file_name": spec.file_name,
            "file_path": str(file_path),
            "content_type": spec.content_type,
            "download_url": (
                f"/api/v1/resources/{resource_id}/downloads/generated/{spec.download_type}/file"
            ),
        }

    def generated_download_file_path(self, download_type: str) -> Optional[Path]:
        """Return generated file path if it exists."""
        try:
            spec = self._build_generated_download_spec(download_type)
        except ValueError:
            return None
        path = self.generated_download_directory() / spec.file_name
        return path if path.exists() else None

    def _build_generated_download_spec(self, download_type: str) -> "GeneratedDownloadSpec":
        config = self.GENERATED_DOWNLOAD_OPTIONS.get(download_type)
        if not config:
            raise ValueError(f"Unsupported generated download type '{download_type}'")

        layer_name = self._wxs_identifier()
        if not layer_name:
            raise ValueError(
                f"Generated download '{download_type}' unavailable: missing gbl_wxsIdentifier_s"
            )

        service_url = self._get_service_url(config["service_type"])
        if not service_url:
            raise ValueError(
                f"Generated download '{download_type}' unavailable: missing "
                f"{config['service_type'].upper()} distribution URL"
            )

        params = dict(config["request_params"])
        if config["service_type"] == "wfs":
            params["typeName"] = layer_name
        elif download_type == "kmz":
            bbox_wsen = self._bbox_wsen()
            if not bbox_wsen:
                raise ValueError("Generated download 'kmz' unavailable: missing/invalid dcat_bbox")
            params["layers"] = layer_name
            params["bbox"] = bbox_wsen
        elif download_type == "geotiff":
            params["layers"] = layer_name

        return GeneratedDownloadSpec(
            download_type=download_type,
            label=config["label"],
            extension=config["extension"],
            content_type=config["content_type"],
            service_url=service_url,
            reflect=bool(config.get("reflect")),
            request_params=params,
            file_name=self._generated_file_name(download_type, config["extension"]),
        )

    def _generated_file_name(self, download_type: str, extension: str) -> str:
        resource_id = str(self.document.get("id", "resource")).replace("/", "_")
        return f"{resource_id}-{download_type}.{extension}"

    def _wxs_identifier(self) -> Optional[str]:
        for key in ("gbl_wxsIdentifier_s", "gbl_wxsidentifier_s"):
            value = self.document.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _bbox_wsen(self) -> Optional[str]:
        raw = self.document.get("dcat_bbox")
        if not isinstance(raw, str):
            return None

        bbox = raw.strip()
        try:
            if bbox.startswith("ENVELOPE(") and bbox.endswith(")"):
                # ENVELOPE(west,east,north,south) -> west,south,east,north
                content = bbox[len("ENVELOPE(") : -1]
                west, east, north, south = [float(part.strip()) for part in content.split(",")]
                return f"{west},{south},{east},{north}"

            # Also support plain bbox form: minx,miny,maxx,maxy
            west, south, east, north = [float(part.strip()) for part in bbox.split(",")]
            return f"{west},{south},{east},{north}"
        except Exception:
            return None

    def _create_generated_download_file(
        self, spec: "GeneratedDownloadSpec", output_path: Path
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        service_url = f"{spec.service_url}/reflect" if spec.reflect else spec.service_url
        try:
            response = requests.get(service_url, params=spec.request_params, timeout=30)
            response.raise_for_status()
        except requests.HTTPError as upstream_error:
            fallback_response = self._try_geoblacklight_download_fallback(spec)
            if fallback_response is None:
                raise upstream_error
            response = fallback_response

        self._assert_content_type_matches(spec, response.headers.get("Content-Type", ""))

        with open(tmp_path, "wb") as file_handle:
            file_handle.write(response.content)

        tmp_path.replace(output_path)

    def _try_geoblacklight_download_fallback(
        self, spec: "GeneratedDownloadSpec"
    ) -> Optional[requests.Response]:
        """
        Stanford-specific fallback:
        GeoBlacklight can sometimes generate derivatives even when direct WFS/WMS
        requests fail due to provider layer naming differences.
        """
        if not self._is_stanford_resource():
            return None

        resource_id = self.document.get("id")
        if not isinstance(resource_id, str) or not resource_id:
            return None

        trigger_url = f"https://earthworks.stanford.edu/download/{resource_id}"
        try:
            trigger_response = requests.get(
                trigger_url,
                params={"type": spec.download_type},
                timeout=30,
                headers={"Accept": "application/json"},
            )
            trigger_response.raise_for_status()
            download_path = self._extract_geoblacklight_download_path(trigger_response.text)
            if not download_path:
                return None

            download_url = (
                download_path
                if download_path.startswith("http")
                else f"https://earthworks.stanford.edu{download_path}"
            )
            file_response = requests.get(download_url, timeout=60)
            file_response.raise_for_status()
            return file_response
        except Exception:
            logger.exception(
                "GeoBlacklight fallback download failed for resource %s (%s)",
                resource_id,
                spec.download_type,
            )
            return None

    def _extract_geoblacklight_download_path(self, body: str) -> Optional[str]:
        """
        GeoBlacklight returns payloads like:
        [[["success","..."]],"/download/file/stanford-...-shapefile.zip"]
        """
        try:
            payload = json.loads(body)
        except Exception:
            return None

        if isinstance(payload, list) and len(payload) >= 2 and isinstance(payload[1], str):
            return payload[1]

        if isinstance(payload, dict):
            for key in ("download_url", "url", "path"):
                value = payload.get(key)
                if isinstance(value, str):
                    return value

        return None

    def _is_stanford_resource(self) -> bool:
        provider = self.document.get("schema_provider_s")
        resource_id = self.document.get("id")
        if isinstance(provider, str) and "stanford" in provider.lower():
            return True
        if isinstance(resource_id, str) and resource_id.startswith("stanford-"):
            return True
        return False

    def _assert_content_type_matches(
        self, spec: "GeneratedDownloadSpec", actual_header: str
    ) -> None:
        if not actual_header:
            return

        actual = actual_header.split(";")[0].strip().lower()
        expected = spec.content_type.lower()
        fallback = self.GENERATED_CONTENT_TYPE_FALLBACKS.get(expected, set())

        if actual == expected or actual in fallback:
            return

        raise ValueError(
            f"Unexpected content type for generated {spec.download_type}: "
            f"expected {spec.content_type}, got {actual_header}"
        )

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


@dataclass
class GeneratedDownloadSpec:
    download_type: str
    label: str
    extension: str
    content_type: str
    service_url: str
    reflect: bool
    request_params: Dict[str, object]
    file_name: str
