from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.utils import create_jsonapi_response, sanitize_for_json

from . import get_async_session, router


@router.get("/resources/{id}/summaries")
async def get_resource_summaries(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    request: Request = None,
):
    """Get all summaries for a resource."""
    try:
        # Query the database for summaries
        async with get_async_session() as session:
            query = text("""
                SELECT * FROM resource_ai_enrichments 
                WHERE resource_id = :resource_id 
                ORDER BY created_at DESC
            """)
            result = await session.execute(query, {"resource_id": id})
            summaries = result.fetchall()

            # Convert to list of dicts and sanitize
            summaries_list = [sanitize_for_json(dict(summary)) for summary in summaries]

            # Create JSON:API compliant response
            request_url = str(request.url) if request else None
            jsonapi_response = create_jsonapi_response(
                data={"type": "summaries", "id": id, "attributes": {"summaries": summaries_list}},
                request_url=request_url,
                callback=callback,
            )

            return JSONResponse(content=jsonapi_response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

