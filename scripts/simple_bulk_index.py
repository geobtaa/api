#!/usr/bin/env python3
"""
Simple bulk indexing script using raw database values.
With ignore_malformed=true in mappings, this should index all resources.
"""

import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from db.database import database
from db.models import resources

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


async def get_spatial_facets(resource_id):
    """Get spatial facets for a resource."""
    try:
        query = """
            SELECT geo_global, geo_country, geo_region, geo_county
            FROM resource_spatial_facets
            WHERE resource_id = :resource_id
        """
        result = await database.fetch_one(query, {"resource_id": resource_id})

        if result:
            spatial_facets = dict(result)

            # Parse JSON fields and format as pipe-delimited strings for faceting
            if spatial_facets.get("geo_country"):
                try:
                    country_data = json.loads(spatial_facets["geo_country"])
                    if isinstance(country_data, dict) and all(
                        key in country_data for key in ["wok_id", "parent_id", "name"]
                    ):
                        # Format: wok_id|parent_id|name
                        spatial_facets["geo_country"] = (
                            f"{country_data['wok_id']}|{country_data['parent_id']}|{country_data['name']}"
                        )
                    else:
                        spatial_facets["geo_country"] = None
                except (json.JSONDecodeError, TypeError):
                    spatial_facets["geo_country"] = None

            if spatial_facets.get("geo_region"):
                try:
                    region_data = json.loads(spatial_facets["geo_region"])
                    if isinstance(region_data, list):
                        # Format as pipe-delimited strings
                        formatted_regions = []
                        for region in region_data:
                            if isinstance(region, dict) and all(
                                key in region for key in ["wok_id", "parent_id", "name"]
                            ):
                                formatted_regions.append(
                                    f"{region['wok_id']}|{region['parent_id']}|{region['name']}"
                                )
                        spatial_facets["geo_region"] = formatted_regions
                    else:
                        spatial_facets["geo_region"] = None
                except (json.JSONDecodeError, TypeError):
                    spatial_facets["geo_region"] = None

            if spatial_facets.get("geo_county"):
                try:
                    county_data = json.loads(spatial_facets["geo_county"])
                    if isinstance(county_data, list):
                        # Format as pipe-delimited strings: wok_id|parent_id|state_abbrev|name
                        formatted_counties = []
                        for county in county_data:
                            if isinstance(county, dict) and all(
                                key in county
                                for key in ["wok_id", "parent_id", "state_abbrev", "name"]
                            ):
                                formatted_counties.append(
                                    f"{county['wok_id']}|{county['parent_id']}|{county['state_abbrev']}|{county['name']}"
                                )
                        spatial_facets["geo_county"] = formatted_counties
                    else:
                        spatial_facets["geo_county"] = None
                except (json.JSONDecodeError, TypeError):
                    spatial_facets["geo_county"] = None

            return spatial_facets
    except Exception as e:
        logger.warning(f"Error getting spatial facets for {resource_id}: {e}")

    return {}


def build_suggest_field(doc):
    """Build the suggest field for autocomplete."""
    suggestion_inputs = []

    # Add title if it exists
    if title := doc.get("dct_title_s"):
        suggestion_inputs.append(title)

    # Add creators
    if creators := doc.get("dct_creator_sm"):
        if isinstance(creators, list):
            suggestion_inputs.extend(creators)
        else:
            suggestion_inputs.append(creators)

    # Add publishers
    if publishers := doc.get("dct_publisher_sm"):
        if isinstance(publishers, list):
            suggestion_inputs.extend(publishers)
        else:
            suggestion_inputs.append(publishers)

    # Add provider
    if provider := doc.get("schema_provider_s"):
        suggestion_inputs.append(provider)

    # Add subjects
    if subjects := doc.get("dct_subject_sm"):
        if isinstance(subjects, list):
            suggestion_inputs.extend(subjects)
        else:
            suggestion_inputs.append(subjects)

    # Add spatial
    if spatial := doc.get("dct_spatial_sm"):
        if isinstance(spatial, list):
            suggestion_inputs.extend(spatial)
        else:
            suggestion_inputs.append(spatial)

    # Add keywords
    if keywords := doc.get("dcat_keyword_sm"):
        if isinstance(keywords, list):
            suggestion_inputs.extend(keywords)
        else:
            suggestion_inputs.append(keywords)

    # Filter out None values and empty strings
    suggestion_inputs = [s for s in suggestion_inputs if s and str(s).strip()]
    # Coerce to strings and truncate to match completion max_input_length (50)
    suggestion_inputs = [str(s).strip()[:50] for s in suggestion_inputs]
    # Remove empties after truncation and de-duplicate while preserving order
    seen = set()
    deduped = []
    for s in suggestion_inputs:
        if s and s not in seen:
            seen.add(s)
            deduped.append(s)
    suggestion_inputs = deduped

    return {"input": suggestion_inputs}


async def main():
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_data_api")
    chunk_size = 500

    logger.info("=" * 70)
    logger.info(f"Bulk indexing all resources to {index_name}")
    logger.info("=" * 70)

    await database.connect()
    es = AsyncElasticsearch(os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200"))

    try:
        # Delete existing index
        if await es.indices.exists(index=index_name):
            logger.info(f"Deleting existing index {index_name}")
            await es.indices.delete(index=index_name)

        # Create index with updated mapping
        from app.elasticsearch.client import init_elasticsearch

        await init_elasticsearch()

        # Fetch all resources
        logger.info("Fetching all resources from database...")
        all_rows = await database.fetch_all(resources.select())
        total = len(all_rows)
        logger.info(f"Fetched {total:,} resources")

        # Prepare bulk actions with array normalization, suggestions, and spatial facets
        async def actions():
            for i, row in enumerate(all_rows):
                if i % 1000 == 0:
                    logger.info(f"Processing resource {i + 1:,}/{total:,}")

                doc = dict(row)

                # Fix array fields: normalize strings to arrays AND fix character-split arrays
                array_fields = [
                    "gbl_resourceClass_sm",
                    "gbl_resourceType_sm",
                    "dct_language_sm",
                    "dct_creator_sm",
                    "dct_publisher_sm",
                    "dct_subject_sm",
                    "dcat_theme_sm",
                    "dcat_keyword_sm",
                    "dct_spatial_sm",
                ]
                for field in array_fields:
                    if field in doc:
                        val = doc[field]
                        # If it's a string, wrap in array
                        if isinstance(val, str):
                            doc[field] = [val]
                        # If it's an array of single characters, join them
                        elif (
                            isinstance(val, list)
                            and val
                            and all(isinstance(v, str) and len(v) == 1 for v in val)
                        ):
                            doc[field] = ["".join(val)]

                # Add autocomplete suggestions
                doc["suggest"] = build_suggest_field(doc)

                # Add spatial facets
                spatial_facets = await get_spatial_facets(doc["id"])
                if spatial_facets:
                    doc["geo_global"] = spatial_facets.get("geo_global", False)
                    doc["geo_country"] = spatial_facets.get("geo_country")
                    doc["geo_region"] = spatial_facets.get("geo_region")
                    doc["geo_county"] = spatial_facets.get("geo_county")

                yield {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": doc["id"],
                    "_source": doc,
                }

        # Bulk index
        logger.info(f"Bulk indexing with chunk_size={chunk_size}...")
        success, errors = await async_bulk(
            es,
            actions(),
            chunk_size=chunk_size,
            raise_on_error=False,
            refresh=True,
        )

        logger.info("=" * 70)
        logger.info("Bulk indexing complete!")
        logger.info(f"Successful: {success:,}")
        logger.info(f"Errors: {len(errors):,}")

        if errors:
            logger.warning("\nFirst 10 errors:")
            for i, err in enumerate(errors[:10], 1):
                logger.warning(f"{i}. {err}")

        # Verify count
        es_count = (await es.count(index=index_name)).get("count", 0)
        logger.info(f"\nElasticsearch count: {es_count:,}")
        logger.info(f"Database count: {total:,}")
        logger.info(f"Missing: {total - es_count:,}")
        logger.info("=" * 70)

    finally:
        try:
            await database.disconnect()
        except Exception:
            pass
        try:
            await es.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
