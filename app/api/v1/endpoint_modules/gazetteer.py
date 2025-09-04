import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, func, or_, select

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
async def list_gazetteers():
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

        return {
            "data": [
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
        }
    except Exception as e:
        logger.error(f"Error listing gazetteers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list gazetteers")


@router.get("/gazetteers/geonames/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_geonames(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
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
            # Handle geometry field if present
            if "geometry" in row_dict and row_dict["geometry"]:
                try:
                    import json
                    row_dict["geometry"] = json.loads(row_dict["geometry"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["geometry"] = None
            
            # Format as JSON:API resource
            formatted_row = {
                "id": str(row_dict.get("geonameid", row_dict.get("id", ""))),
                "type": "geoname",
                "attributes": row_dict
            }
            data.append(formatted_row)

        return {"data": data}

    except Exception as e:
        logger.error(f"Error searching GeoNames: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search GeoNames")


@router.get("/gazetteers/wof/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_wof(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
):
    """Search Who's on First gazetteer."""
    try:
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

        query = (
            select(gazetteer_wof_spr)
            .where(and_(*conditions))
            .order_by(gazetteer_wof_spr.c.name)
            .limit(limit)
            .offset(offset)
        )

        results = await database.fetch_all(query)

        # Convert results to JSON:API format
        data = []
        for row in results:
            row_dict = dict(row)
            # Handle geometry field if present
            if "geometry" in row_dict and row_dict["geometry"]:
                try:
                    import json
                    row_dict["geometry"] = json.loads(row_dict["geometry"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["geometry"] = None
            
            # Format as JSON:API resource
            formatted_row = {
                "id": str(row_dict.get("wok_id", row_dict.get("id", ""))),
                "type": "wof",
                "attributes": row_dict
            }
            data.append(formatted_row)

        return {"data": data}

    except Exception as e:
        logger.error(f"Error searching WOF: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search WOF")


@router.get("/gazetteers/btaa/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_btaa(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, description="Maximum number of results", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
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
            # Handle geometry field if present
            if "geometry" in row_dict and row_dict["geometry"]:
                try:
                    import json
                    row_dict["geometry"] = json.loads(row_dict["geometry"])
                except (json.JSONDecodeError, TypeError):
                    row_dict["geometry"] = None
            
            # Format as JSON:API resource
            formatted_row = {
                "id": str(row_dict.get("id", "")),
                "type": "btaa",
                "attributes": row_dict
            }
            data.append(formatted_row)

        return {"data": data}

    except Exception as e:
        logger.error(f"Error searching BTAA: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search BTAA")


@router.get("/gazetteers/search")
@cached_endpoint(ttl=GAZETTEER_CACHE_TTL)
async def search_all_gazetteers(
    q: str = Query(..., description="Search query"),
    gazetteer: Optional[str] = Query(None, description="Specific gazetteer to search"),
    limit: int = Query(10, description="Maximum number of results per gazetteer", ge=1, le=100),
    offset: int = Query(0, description="Number of results to skip", ge=0),
):
    """Search across all gazetteers or a specific one."""
    try:
        if gazetteer:
            if gazetteer == "geonames":
                return await search_geonames(q, limit, offset)
            elif gazetteer == "wof":
                return await search_wof(q, limit, offset)
            elif gazetteer == "btaa":
                return await search_btaa(q, limit, offset)
            else:
                raise HTTPException(status_code=400, detail="Invalid gazetteer specified")

        # Search all gazetteers
        results = {}
        results["geonames"] = await search_geonames(q, limit, offset)
        results["wof"] = await search_wof(q, limit, offset)
        results["btaa"] = await search_btaa(q, limit, offset)

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching all gazetteers: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to search gazetteers")
