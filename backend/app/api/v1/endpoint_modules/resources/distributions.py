from typing import Optional

from fastapi import HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.sql import select

from app.api.schemas import ResourceDistributionsResponse
from app.api.v1.utils import create_response, sanitize_for_json
from app.services.cache_service import cached_endpoint
from db.models import resources

from . import RESOURCE_CACHE_TTL, async_session, logger, router


@router.get("/resources/{id}/distributions", response_model=ResourceDistributionsResponse)
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource_distributions(
    request: Request,
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get all distributions for a resource."""
    try:
        # First check if the resource exists
        async with async_session() as session:
            resource_query = select(resources.c.id).where(resources.c.id == id)
            resource_result = await session.execute(resource_query)
            resource_row = resource_result.fetchone()

            if not resource_row:
                raise HTTPException(status_code=404, detail="Resource not found")

            # Get distributions with distribution type information
            distributions_query = text("""
                SELECT 
                    rd.id,
                    rd.resource_id,
                    rd.url,
                    rd.label,
                    rd.position,
                    rd.created_at,
                    rd.updated_at,
                    rd.import_distribution_id,
                    dt.id as distribution_type_id,
                    dt.name as distribution_type_name,
                    dt.distribution_type,
                    dt.distribution_uri,
                    dt.note as distribution_note
                FROM resource_distributions rd
                JOIN distribution_types dt ON rd.distribution_type_id = dt.id
                WHERE rd.resource_id = :resource_id
                ORDER BY rd.position ASC, rd.created_at ASC
            """)

            result = await session.execute(distributions_query, {"resource_id": id})
            distributions = result.fetchall()

            # Convert to list of dicts and sanitize
            distributions_list = []
            for dist in distributions:
                dist_dict = sanitize_for_json(dict(dist._mapping))
                distributions_list.append(dist_dict)

            response_payload = {
                "id": id,
                "distributions": distributions_list,
            }

            return create_response(response_payload, callback)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting distributions for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get distributions") from e
