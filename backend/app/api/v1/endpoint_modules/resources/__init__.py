import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.config import DATABASE_URL

# Load environment variables from .env file
load_dotenv()

# Create router
router = APIRouter()

# Logger
logger = logging.getLogger(__name__)

# Create async engine and session with connection pool settings
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections after 30 minutes
    pool_pre_ping=True,  # Verify connections before using them
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def get_async_session():
    """Get async session - allows tests to mock async_session.

    This function uses the module's async_session attribute, which tests can mock.
    """
    import sys

    # Get the current module (resources.__init__)
    module = sys.modules[__name__]
    # Use the module's async_session attribute (which tests can replace)
    session_factory = getattr(module, "async_session", async_session)
    return session_factory()


base_url = os.getenv("APPLICATION_URL", "http://localhost:8000/api/v1/")

# Cache TTL configuration in seconds
RESOURCE_CACHE_TTL = int(os.getenv("RESOURCE_CACHE_TTL", 86400))  # 24 hours
LIST_CACHE_TTL = int(os.getenv("LIST_CACHE_TTL", 43200))  # 12 hours


def filter_resource_fields(resource_dict: dict, fields_param: Optional[str]) -> dict:
    """
    Filter resource fields based on the fields parameter.
    Always includes 'id' field even if not specified.

    Args:
        resource_dict: The resource dictionary to filter
        fields_param: Comma-separated string of field names to include

    Returns:
        Filtered resource dictionary
    """
    if not fields_param:
        return resource_dict

    # Parse the fields parameter
    requested_fields = [field.strip() for field in fields_param.split(",") if field.strip()]

    # Always include 'id' field
    if "id" not in requested_fields:
        requested_fields.append("id")

    # Filter the resource dictionary to only include requested fields
    filtered_resource = {}
    for field in requested_fields:
        if field in resource_dict:
            filtered_resource[field] = resource_dict[field]

    return filtered_resource


# Import all endpoint modules to register routes
# These imports must come after router/constants are defined
# Export FastAPI imports for testing
from fastapi import HTTPException, Query, Request  # noqa: E402, I001
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402, I001

# Export classes and utilities for testing
from app.api.v1.utils import (  # noqa: E402, I001
    create_jsonapi_response,
    create_response,
    process_resource,
    process_resource_homepage,
    sanitize_for_json,
)
from app.services.link_service import LinkService  # noqa: E402, I001
from app.services.ogm_field_mapper import OGMFieldMapper  # noqa: E402, I001
from app.services.relationship_service import RelationshipService  # noqa: E402, I001
from app.services.spatial_facet_service import SpatialFacetService  # noqa: E402, I001
from db.models import resources  # noqa: E402, I001

from . import (  # noqa: E402, I001
    list,
    get,
    citation,
    data_dictionaries,
    distributions,
    downloads,
    links,
    metadata,
    ogm_viewer,
    relationships,
    similar_items,
    spatial_facets,
    static_map,
    thumbnail,
    viewer,
)

# Export endpoint functions for testing
from .get import get_resource  # noqa: E402, I001
from .data_dictionaries import get_resource_data_dictionaries  # noqa: E402, I001
from .links import get_resource_links  # noqa: E402, I001
from .list import list_resources  # noqa: E402, I001
from .metadata import get_resource_metadata  # noqa: E402, I001
from .ogm_viewer import get_resource_viewer  # noqa: E402, I001
from .relationships import get_resource_relationships  # noqa: E402, I001
from .spatial_facets import get_resource_spatial_facets  # noqa: E402, I001

# from .summaries import get_resource_summaries  # noqa: E402  # Temporarily disabled

# Alias for backward compatibility with tests
get_resource_ogm = get_resource_metadata
