import json
import logging
from typing import Dict, Optional, Union

from app.services.distribution_repository import (
    DistributionContext,
    build_distribution_context,
)

from ..viewers import ItemViewer

logger = logging.getLogger(__name__)


def _to_base_dict(document: object) -> Dict:
    """Best-effort conversion of an arbitrary document to a dictionary."""
    if isinstance(document, dict):
        return document
    # SQLAlchemy RowMapping
    mapping = getattr(document, "_mapping", None)
    if mapping is not None:
        try:
            return dict(mapping)
        except Exception:
            pass
    # Regular Python objects
    dunder = getattr(document, "__dict__", None)
    if dunder is not None and isinstance(dunder, dict):
        return {k: v for k, v in dunder.items() if not k.startswith("_")}
    # Fallback to dict() if the object is iterable of pairs
    try:
        return dict(document)  # type: ignore[arg-type]
    except Exception:
        return {}


def _coerce_reference_value(value):
    """Convert mixed distribution payloads into simple string URLs when possible."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("url", "@id", "id"):
            if value.get(key):
                return value[key]
        return None
    if isinstance(value, list):
        for item in value:
            coerced = _coerce_reference_value(item)
            if coerced:
                return coerced
        return None
    return None


def parse_references(
    document: Union[Dict, object],
    distribution_context: Optional[DistributionContext] = None,
) -> Dict:
    """Build a reference map for viewer logic using resource distributions."""
    try:
        references: Dict = {}

        if distribution_context is None and isinstance(document, dict):
            distribution_context = build_distribution_context(document.get("id", ""), [])

        if distribution_context:
            for uri, value in distribution_context.legacy_reference_payload.items():
                coerced = _coerce_reference_value(value)
                if coerced:
                    references[uri] = coerced
                    if uri.startswith("https://iiif.io/"):
                        http_uri = "http://" + uri[len("https://") :]
                        references.setdefault(http_uri, coerced)

        if not references:
            if isinstance(document, dict):
                raw_refs = document.get("dct_references_s", {})
            else:
                # Prefer direct attribute if present
                if hasattr(document, "dct_references_s"):
                    raw_refs = getattr(document, "dct_references_s", {})
                elif hasattr(document, "get"):
                    raw_refs = document.get("dct_references_s", {})
                else:
                    raw_refs = {}

            if isinstance(raw_refs, str):
                try:
                    raw_refs = json.loads(raw_refs)
                except json.JSONDecodeError:
                    raw_refs = {}

            if isinstance(raw_refs, dict):
                for uri, value in raw_refs.items():
                    coerced = _coerce_reference_value(value)
                    if coerced:
                        references[uri] = coerced
                        if uri.startswith("https://iiif.io/"):
                            http_uri = "http://" + uri[len("https://") :]
                            references.setdefault(http_uri, coerced)

        # Add geometry if present
        if isinstance(document, dict):
            geom = document.get("locn_geometry")
        else:
            if hasattr(document, "locn_geometry"):
                geom = getattr(document, "locn_geometry", None)
            elif hasattr(document, "get"):
                geom = document.get("locn_geometry", None)
            else:
                geom = None

        if geom:
            references["locn_geometry"] = geom

        return references
    except Exception as e:
        logger.error(f"Error parsing references: {str(e)}", exc_info=True)
        return {}


def create_viewer_attributes(
    document: Union[Dict, object], distribution_context: Optional[DistributionContext] = None
) -> Dict:
    """Create viewer attributes from the document."""
    # Convert Record to dict if needed
    document = _to_base_dict(document)

    references = parse_references(document, distribution_context=distribution_context)
    logger.debug(f"Parsed references for viewer: {references}")

    viewer = ItemViewer(references)

    try:
        geometry = viewer.viewer_geometry()
        logger.debug(f"Viewer geometry: {geometry}")
    except Exception as e:
        logger.error(f"Error getting viewer geometry: {str(e)}", exc_info=True)
        geometry = None

    return {
        "ui_viewer_protocol": viewer.viewer_protocol(),
        "ui_viewer_endpoint": viewer.viewer_endpoint(),
        "ui_viewer_geometry": geometry,
    }


class ViewerService:
    """Service for handling viewer-related functionality."""

    def __init__(
        self,
        document: Union[Dict, object],
        distribution_context: Optional[DistributionContext] = None,
    ):
        """Initialize the service with a document."""
        self.document = document
        base_dict = _to_base_dict(document)
        if distribution_context is None:
            distribution_context = build_distribution_context(base_dict.get("id", ""), [])
        self.distribution_context = distribution_context
        self.references = parse_references(base_dict, distribution_context=distribution_context)
        self.viewer = ItemViewer(self.references)

    def get_viewer_attributes(self) -> Dict:
        """Get all viewer attributes for the document."""
        try:
            geometry = self.viewer.viewer_geometry()
            logger.debug(f"Viewer geometry: {geometry}")
        except Exception as e:
            logger.error(f"Error getting viewer geometry: {str(e)}", exc_info=True)
            geometry = None

        return {
            "ui_viewer_protocol": self.viewer.viewer_protocol(),
            "ui_viewer_endpoint": self.viewer.viewer_endpoint(),
            "ui_viewer_geometry": geometry,
        }
