import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, or_, select

from app.api.v1.strong_params import GAZETTEER_ALLOWED_PARAMS
from app.api.v1.utils import (
    create_gazetteer_meta_and_links,
    create_jsonapi_response,
    sanitize_for_json,
)
from app.services.cache_service import cached_endpoint
from db.database import database
from db.models import (
    gazetteer_btaa,
    gazetteer_geonames,
    gazetteer_wof_ancestors,
    gazetteer_wof_concordances,
    gazetteer_wof_geojson,
    gazetteer_wof_names,
    gazetteer_wof_spr,
)

# Load environment variables from .env file
load_dotenv()

router = APIRouter()
logger = logging.getLogger(__name__)

# Cache TTL for gazetteer endpoints (1 hour)
GAZETTEER_CACHE_TTL = int(os.getenv("GAZETTEER_CACHE_TTL", 3600))


@router.get("/gazetteers")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def list_gazetteers(
    request: Request = None,
):
    """List all available gazetteers with record counts."""
    try:
        # Get record counts for each gazetteer
        geonames_count = await database.fetch_val(
            select(func.count()).select_from(gazetteer_geonames)
        )

        wof_spr_count = await database.fetch_val(
            select(func.count()).select_from(gazetteer_wof_spr)
        )

        btaa_count = await database.fetch_val(select(func.count()).select_from(gazetteer_btaa))

        # Additional WOF table counts
        wof_ancestors_count = await database.fetch_val(
            select(func.count()).select_from(gazetteer_wof_ancestors)
        )

        wof_concordances_count = await database.fetch_val(
            select(func.count()).select_from(gazetteer_wof_concordances)
        )

        wof_geojson_count = await database.fetch_val(
            select(func.count()).select_from(gazetteer_wof_geojson)
        )

        wof_names_count = await database.fetch_val(
            select(func.count()).select_from(gazetteer_wof_names)
        )

        # Create the data structure
        data = [
            {
                "id": "geonames",
                "type": "gazetteer",
                "attributes": {
                    "name": "GeoNames",
                    "description": "GeoNames geographical database",
                    "record_count": geonames_count or 0,
                    "website": "https://www.geonames.org/",
                },
            },
            {
                "id": "wof",
                "type": "gazetteer",
                "attributes": {
                    "name": "Who's on First",
                    "description": "Who's on First gazetteer from Mapzen",
                    "record_count": wof_spr_count or 0,
                    "website": "https://whosonfirst.org/",
                    "additional_tables": {
                        "ancestors": wof_ancestors_count or 0,
                        "concordances": wof_concordances_count or 0,
                        "geojson": wof_geojson_count or 0,
                        "names": wof_names_count or 0,
                    },
                },
            },
            {
                "id": "btaa",
                "type": "gazetteer",
                "attributes": {
                    "name": "BTAA",
                    "description": "Big Ten Academic Alliance Geoportal gazetteer",
                    "record_count": btaa_count or 0,
                    "website": "https://geo.btaa.org/",
                },
            },
        ]

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(data=data, request_url=request_url)

        return JSONResponse(content=jsonapi_response)
    except Exception as e:
        logger.error(f"Error listing gazetteers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list gazetteers") from e


@router.get("/gazetteers/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_all_gazetteers(
    q: str = Query(..., description="Search query"),
    gazetteer: Optional[str] = Query(None, description="Specific gazetteer to search"),
    limit: int = Query(10, description="Maximum number of results per gazetteer", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
    request: Request = None,
):
    """Search across all gazetteers or a specific one."""
    try:
        if gazetteer:
            if gazetteer == "geonames":
                return await search_geonames(q, limit, offset, request)
            elif gazetteer == "wof":
                return await search_wof(q, limit, offset, request)
            elif gazetteer == "btaa":
                return await search_btaa(q, limit, offset, request)
            else:
                raise HTTPException(status_code=400, detail="Invalid gazetteer specified")

        # Search all gazetteers
        results = {}
        results["geonames"] = await search_geonames(q, limit, offset, request)
        results["wof"] = await search_wof(q, limit, offset, request)
        results["btaa"] = await search_btaa(q, limit, offset, request)

        # Extract data from JSONResponse objects for the combined response
        combined_results = {}
        for gazetteer_name, response in results.items():
            if hasattr(response, "body"):
                # Extract the JSON content from the response
                import json

                response_data = json.loads(response.body.decode())
                combined_results[gazetteer_name] = response_data
            else:
                combined_results[gazetteer_name] = response

        return combined_results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching all gazetteers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search gazetteers") from e


@router.get("/gazetteers/btaa/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_btaa(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
    request: Request = None,
):
    """Search BTAA gazetteer."""
    try:
        # Build search query
        search_terms = q.split()
        conditions = []

        for term in search_terms:
            conditions.append(
                or_(
                    gazetteer_btaa.c.fast_area.ilike(f"%{term}%"),
                )
            )

        query = (
            select(gazetteer_btaa)
            .where(and_(*conditions))
            .order_by(gazetteer_btaa.c.fast_area)
            .limit(limit)
            .offset(offset)
        )

        results = await database.fetch_all(query)

        # Convert results to JSON:API format
        data = []
        for row in results:
            row_dict = dict(row)
            # Sanitize the data for JSON serialization
            row_dict = sanitize_for_json(row_dict)

            # Format as JSON:API resource
            formatted_row = {
                "id": str(row_dict.get("id", "")),
                "type": "btaa",
                "attributes": row_dict,
            }
            data.append(formatted_row)

        # Create meta and links using utility function with strong parameters
        meta, links = create_gazetteer_meta_and_links(
            request, q, limit, offset, len(data), "btaa", allowed_params=GAZETTEER_ALLOWED_PARAMS
        )

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(data=data, request_url=request_url)

        # Add our custom links and meta
        jsonapi_response["links"] = links
        jsonapi_response["meta"] = meta

        # Reorder the response to put meta before data
        reordered_response = {
            "jsonapi": jsonapi_response["jsonapi"],
            "links": jsonapi_response["links"],
            "meta": jsonapi_response["meta"],
            "data": jsonapi_response["data"],
        }

        return JSONResponse(content=reordered_response)

    except Exception as e:
        logger.error(f"Error searching BTAA: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search BTAA") from e


@router.get("/gazetteers/geonames/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_geonames(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
    request: Request = None,
):
    """Search GeoNames gazetteer."""
    try:
        # Build search query
        search_terms = q.split()
        conditions = []

        for term in search_terms:
            conditions.append(
                or_(
                    gazetteer_geonames.c.name.ilike(f"%{term}%"),
                    gazetteer_geonames.c.asciiname.ilike(f"%{term}%"),
                    gazetteer_geonames.c.alternatenames.ilike(f"%{term}%"),
                )
            )

        query = (
            select(gazetteer_geonames)
            .where(and_(*conditions))
            .order_by(gazetteer_geonames.c.population.desc())
            .limit(limit)
            .offset(offset)
        )

        results = await database.fetch_all(query)

        # Convert results to JSON:API format
        data = []
        for row in results:
            row_dict = dict(row)
            # Sanitize the data for JSON serialization
            row_dict = sanitize_for_json(row_dict)

            # Format as JSON:API resource
            formatted_row = {
                "id": str(row_dict.get("geonameid", row_dict.get("id", ""))),
                "type": "geoname",
                "attributes": row_dict,
            }
            data.append(formatted_row)

        # Create meta and links using utility function with strong parameters
        meta, links = create_gazetteer_meta_and_links(
            request,
            q,
            limit,
            offset,
            len(data),
            "geonames",
            allowed_params=GAZETTEER_ALLOWED_PARAMS,
        )

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(data=data, request_url=request_url)

        # Add our custom links and meta
        jsonapi_response["links"] = links
        jsonapi_response["meta"] = meta

        # Reorder the response to put meta before data
        reordered_response = {
            "jsonapi": jsonapi_response["jsonapi"],
            "links": jsonapi_response["links"],
            "meta": jsonapi_response["meta"],
            "data": jsonapi_response["data"],
        }

        return JSONResponse(content=reordered_response)

    except Exception as e:
        logger.error(f"Error searching GeoNames: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search GeoNames") from e


@router.get("/gazetteers/wof/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_wof(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
    exclude_placetypes: Optional[str] = Query(
        None, description="Comma-separated list of placetypes to exclude (default: microhood,neighbourhood,venue)"
    ),
    request: Request = None,
):
    """Search Who's on First gazetteer."""
    try:
        # Default placetypes to exclude for autosuggestion
        if exclude_placetypes is None:
            exclude_placetypes = "microhood,neighbourhood,venue"
        
        excluded_types = [pt.strip() for pt in exclude_placetypes.split(",") if pt.strip()]

        # Build search query
        search_terms = q.split()
        conditions = []

        for term in search_terms:
            conditions.append(
                or_(
                    gazetteer_wof_spr.c.name.ilike(f"%{term}%"),
                    gazetteer_wof_spr.c.placetype.ilike(f"%{term}%"),
                )
            )

        # Exclude confusing placetypes for autosuggestion
        # Keep records where placetype is NULL or not in excluded list
        if excluded_types:
            conditions.append(
                or_(
                    gazetteer_wof_spr.c.placetype.is_(None),
                    ~gazetteer_wof_spr.c.placetype.in_(excluded_types)
                )
            )

        query = (
            select(gazetteer_wof_spr)
            .where(and_(*conditions))
            .order_by(gazetteer_wof_spr.c.name)
            .limit(limit)
            .offset(offset)
        )

        results = await database.fetch_all(query)

        # Collect wok_ids for batch fetching ancestors and geojson
        wok_ids = [result["wok_id"] for result in results]

        # Fetch ancestors for all results in batch
        ancestors_map = {}
        if wok_ids:
            ancestors_query = select(gazetteer_wof_ancestors).where(
                gazetteer_wof_ancestors.c.wok_id.in_(wok_ids)
            )
            ancestors = await database.fetch_all(ancestors_query)
            
            # Group ancestors by wok_id
            for ancestor in ancestors:
                wok_id = ancestor["wok_id"]
                if wok_id not in ancestors_map:
                    ancestors_map[wok_id] = []
                ancestors_map[wok_id].append(dict(ancestor))
            
            # Fetch ancestor names from spr table
            ancestor_ids = list(set([a["ancestor_id"] for ancestors_list in ancestors_map.values() for a in ancestors_list]))
            if ancestor_ids:
                # Compare ancestor_id (Integer) with wok_id (BigInteger) - PostgreSQL handles type coercion
                ancestor_spr_query = select(gazetteer_wof_spr).where(
                    gazetteer_wof_spr.c.wok_id.in_(ancestor_ids)
                )
                ancestor_sprs = await database.fetch_all(ancestor_spr_query)
                ancestor_names_map = {spr["wok_id"]: spr["name"] for spr in ancestor_sprs}
                
                # Add names to ancestors
                for wok_id, ancestors_list in ancestors_map.items():
                    for ancestor in ancestors_list:
                        ancestor["name"] = ancestor_names_map.get(ancestor["ancestor_id"])

        # Fetch GeoJSON for all results in batch
        geojson_map = {}
        if wok_ids:
            geojson_query = select(gazetteer_wof_geojson).where(
                gazetteer_wof_geojson.c.wok_id.in_(wok_ids)
            ).order_by(
                # Prefer non-alt geometries, then by source preference
                gazetteer_wof_geojson.c.is_alt.asc(),
                gazetteer_wof_geojson.c.source.asc()
            )
            geojson_records = await database.fetch_all(geojson_query)
            
            # Group by wok_id, keeping only the first (best) one
            for geojson_record in geojson_records:
                wok_id = geojson_record["wok_id"]
                if wok_id not in geojson_map:
                    geojson_map[wok_id] = dict(geojson_record)

        # Convert results to JSON:API format
        data = []
        for row in results:
            row_dict = dict(row)
            wok_id = row_dict.get("wok_id")
            
            # Get ancestors for this place
            ancestors = ancestors_map.get(wok_id, [])
            
            # Build hierarchy: prefer region, county, locality for display
            hierarchy_parts = []
            hierarchy_placetypes = ["region", "county", "locality"]
            
            # Sort ancestors by placetype priority
            sorted_ancestors = sorted(
                ancestors,
                key=lambda a: hierarchy_placetypes.index(a.get("ancestor_placetype", "")) 
                if a.get("ancestor_placetype") in hierarchy_placetypes 
                else 999
            )
            
            for ancestor in sorted_ancestors:
                if ancestor.get("ancestor_placetype") in hierarchy_placetypes and ancestor.get("name"):
                    hierarchy_parts.append(ancestor["name"])
            
            # Build display name: "Name, Parent1, Parent2, Country"
            display_parts = [row_dict.get("name", "")]
            display_parts.extend(hierarchy_parts)
            if row_dict.get("country"):
                display_parts.append(row_dict["country"])
            display_name = ", ".join(display_parts)

            # Get GeoJSON for this place
            geojson_record = geojson_map.get(wok_id)
            geojson_data = None
            if geojson_record:
                try:
                    geojson_data = json.loads(geojson_record["body"])
                except (json.JSONDecodeError, TypeError):
                    geojson_data = None

            # Sanitize the data for JSON serialization
            row_dict = sanitize_for_json(row_dict)

            # Sanitize ancestors/hierarchy data (may contain date fields)
            sanitized_ancestors = sanitize_for_json(ancestors)

            # Add enhanced fields
            row_dict["display_name"] = display_name
            row_dict["hierarchy"] = sanitized_ancestors
            row_dict["geojson"] = geojson_data

            # Format as JSON:API resource
            formatted_row = {
                "id": str(row_dict.get("wok_id", row_dict.get("id", ""))),
                "type": "wof",
                "attributes": row_dict,
            }
            data.append(formatted_row)

        # Create meta and links using utility function with strong parameters
        meta, links = create_gazetteer_meta_and_links(
            request, q, limit, offset, len(data), "wof", allowed_params=GAZETTEER_ALLOWED_PARAMS
        )

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(data=data, request_url=request_url)

        # Add our custom links and meta
        jsonapi_response["links"] = links
        jsonapi_response["meta"] = meta

        # Reorder the response to put meta before data
        reordered_response = {
            "jsonapi": jsonapi_response["jsonapi"],
            "links": jsonapi_response["links"],
            "meta": jsonapi_response["meta"],
            "data": jsonapi_response["data"],
        }

        return JSONResponse(content=reordered_response)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error searching WOF: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to search WOF: {error_msg}") from e
