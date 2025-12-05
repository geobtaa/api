from typing import Optional

from fastapi import HTTPException, Query, Request
from sqlalchemy.sql import select

from app.api.v1.utils import create_jsonapi_response
from app.services.spatial_facet_service import SpatialFacetService
from db.models import resources

from . import get_async_session, logger, router


@router.get("/resources/{id}/spatial-facets")
async def get_resource_spatial_facets(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    debug: bool = Query(False, description="Include overlap ratios in results"),
    request: Request = None,
):
    """Get spatial hierarchical facets (country, state, county) and bounding box for a resource."""
    try:
        # Fetch the resource data first using the proper async session
        async with get_async_session() as session:
            query = select(resources.c.id, resources.c.dcat_bbox).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                # Return empty response for nonexistent resource
                response_data = {"id": id, "type": "spatial_facets", "attributes": {}}
                request_url = str(request.url) if request else None
                return create_jsonapi_response(response_data, request_url, callback)

            # Convert to dict
            resource_dict = dict(row._mapping)

            # Get spatial facets using the SpatialFacetService with the resource data
            service = SpatialFacetService(resource_dict)
            spatial_facets = await service.get_spatial_facets_with_wof_ids(session, debug=debug)

            # Prepare attributes with dcat_bbox first, then spatial facets
            attributes = {}
            if resource_dict.get("dcat_bbox"):
                attributes["dcat_bbox"] = resource_dict["dcat_bbox"]
            # Add spatial facets after dcat_bbox
            attributes.update(spatial_facets)

            # Create JSON:API compliant response
            response_data = {"id": id, "type": "spatial_facets", "attributes": attributes}

            request_url = str(request.url) if request else None
            return create_jsonapi_response(response_data, request_url, callback)

    except Exception as e:
        logger.error(f"Error getting spatial facets for resource {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error retrieving spatial facets: {str(e)}"
        ) from e

