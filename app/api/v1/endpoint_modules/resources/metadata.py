import json
from typing import Optional

from fastapi import HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_response, sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.ogm_field_mapper import OGMFieldMapper
from db.models import resources

from . import filter_resource_fields, get_async_session, logger, router


@router.get("/resources/{id}/metadata")
async def get_resource_metadata(
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get just the OpenGeoMetadata Aardvark record for a resource by ID."""
    try:
        async with get_async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Convert to dict and sanitize datetime objects
            resource_dict = sanitize_for_json(dict(row._mapping))

            # Map database column names to official Aardvark field names
            aardvark_attributes = OGMFieldMapper.map_resource_fields(resource_dict)

            # Filter out null values and empty arrays
            aardvark_record = {}
            for key, value in aardvark_attributes.items():
                if value is not None and value != "":
                    # Handle empty arrays
                    if isinstance(value, list) and len(value) == 0:
                        continue
                    # Handle arrays with only None/empty values
                    if isinstance(value, list) and all(
                        item is None or item == "" for item in value
                    ):
                        continue
                    aardvark_record[key] = value

            # Apply field filtering if fields parameter is provided
            if fields:
                aardvark_record = filter_resource_fields(aardvark_record, fields)
                logger.info(f"Filtered OGM record: {aardvark_record}")

            # Rebuild dct_references_s from resource_distributions for OGM output
            try:
                distribution_context = await fetch_distribution_context(id)
                legacy_refs = distribution_context.legacy_reference_payload
                if legacy_refs:
                    aardvark_record["dct_references_s"] = json.dumps(legacy_refs)
            except Exception:
                pass

            # Return just the cleaned attributes (the Aardvark record)
            return create_response(aardvark_record, callback)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting Aardvark record for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

