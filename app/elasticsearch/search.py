import json
import logging
import os
import time
from urllib.parse import urlencode

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy.sql import text

from app.services.viewer_service import create_viewer_attributes  # Updated import
from db.database import database
from db.models import resources

from .client import es

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Facet size configuration
GEO_COUNTRY_FACET_SIZE = int(os.getenv("GEO_COUNTRY_FACET_SIZE", "20"))
GEO_REGION_FACET_SIZE = int(os.getenv("GEO_REGION_FACET_SIZE", "50"))
GEO_COUNTY_FACET_SIZE = int(os.getenv("GEO_COUNTY_FACET_SIZE", "100"))
DEFAULT_FACET_SIZE = int(os.getenv("DEFAULT_FACET_SIZE", "10"))


def get_search_criteria(query: str, fq: dict, skip: int, limit: int, sort: list = None):
    """Return the currently applied search criteria."""
    return {
        "query": query,
        "filters": fq,
        "pagination": {"skip": skip, "limit": limit},
        "sort": sort or [{"_score": "desc"}],
    }


async def search_resources(
    query: str = None,
    fq: dict = None,
    skip: int = 0,
    limit: int = 20,
    sort: list = None,
    search_fields: str | None = None,
):
    """Search resources in Elasticsearch with optional filters, sorting, and spelling
    suggestions."""
    # Ensure limit is not zero to avoid division by zero errors
    if limit <= 0:
        limit = 20  # Default to 20 if limit is zero or negative

    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_ogm_api")

    try:
        # Get the current search criteria
        search_criteria = get_search_criteria(query, fq, skip, limit, sort)
        logger.debug(f"Search criteria: {search_criteria}")

        # Construct the filter query
        filter_clauses = []
        if fq:
            for field, values in fq.items():
                logger.debug(f"Processing filter - Field: {field}, Values: {values}")
                if isinstance(values, list):
                    filter_clauses.append({"terms": {field: values}})
                else:
                    filter_clauses.append({"term": {field: values}})

        # Build the search query
        if search_criteria.get("query"):
            query_text = search_criteria["query"] or ""
            is_phrase = (
                len(query_text) >= 2 and query_text.startswith('"') and query_text.endswith('"')
            )
            phrase = query_text[1:-1] if is_phrase else query_text

            # If specific fields are requested (and not 'all_fields'),
            # use multi_match across provided fields
            scoped = bool(search_fields) and search_fields.strip().lower() != "all_fields"
            if scoped:
                requested_fields = [f.strip() for f in search_fields.split(",") if f.strip()]
                # Prefer exact matches via .keyword when available,
                # but also search the analyzed field
                expanded_fields = []
                for f in requested_fields:
                    expanded_fields.append(f)
                    expanded_fields.append(f"{f}.keyword")

                base_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "multi_match": {
                                        "query": phrase,
                                        "type": "best_fields" if not is_phrase else "phrase",
                                        "operator": "AND",
                                        "fields": expanded_fields,
                                    }
                                }
                            ],
                            "filter": filter_clauses,
                        }
                    }
                }
            else:
                # Default behavior across boosted fields using query_string
                base_query = {
                    "query": {
                        "bool": {
                            "must": [
                                {
                                    "query_string": {
                                        "query": query_text,
                                        "fields": [
                                            "id^5",
                                            "dct_title_s^3",
                                            "dct_description_sm^2",
                                            "summary^2",
                                            "dct_creator_sm^2",
                                            "dct_subject_sm^1.5",
                                            "dcat_keyword_sm^1.5",
                                            "dct_publisher_sm",
                                            "schema_provider_s",
                                            "dct_spatial_sm",
                                            "gbl_displaynote_sm",
                                        ],
                                        "default_operator": "AND",
                                        "analyze_wildcard": True,
                                        "allow_leading_wildcard": True,
                                    }
                                }
                            ],
                            "filter": filter_clauses,
                        }
                    },
                }

            search_query = {
                **base_query,
                "from": skip,
                "size": limit,
                "sort": sort or [{"_score": "desc"}],
                "track_total_hits": True,
                "aggs": {
                    "spatial_agg": {
                        "terms": {"field": "dct_spatial_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "resource_class_agg": {
                        "terms": {"field": "gbl_resourceClass_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "resource_type_agg": {
                        "terms": {"field": "gbl_resourceType_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "index_year_agg": {
                        "terms": {"field": "gbl_indexYear_im", "size": DEFAULT_FACET_SIZE}
                    },
                    "language_agg": {
                        "terms": {"field": "dct_language_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "creator_agg": {
                        "terms": {"field": "dct_creator_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "provider_agg": {
                        "terms": {"field": "schema_provider_s", "size": DEFAULT_FACET_SIZE}
                    },
                    "access_rights_agg": {
                        "terms": {"field": "dct_accessRights_s", "size": DEFAULT_FACET_SIZE}
                    },
                    "georeferenced_agg": {
                        "terms": {"field": "gbl_georeferenced_b", "size": DEFAULT_FACET_SIZE}
                    },
                    # Spatial facet aggregations with configurable sizes
                    "geo_country_agg": {
                        "terms": {"field": "geo_country", "size": GEO_COUNTRY_FACET_SIZE}
                    },
                    "geo_region_agg": {
                        "terms": {"field": "geo_region", "size": GEO_REGION_FACET_SIZE}
                    },
                    "geo_county_agg": {
                        "terms": {"field": "geo_county", "size": GEO_COUNTY_FACET_SIZE}
                    },
                },
            }

            # Only add suggest if query is not empty
            if search_criteria["query"].strip():
                search_query["suggest"] = {
                    "text": search_criteria["query"],
                    "simple_phrase": {
                        "phrase": {
                            "field": "dct_title_s",
                            "size": 1,
                            "gram_size": 3,
                            "direct_generator": [
                                {"field": "dct_title_s", "suggest_mode": "always"},
                                {"field": "dct_description_sm", "suggest_mode": "always"},
                            ],
                            "highlight": {"pre_tag": "<em>", "post_tag": "</em>"},
                        }
                    },
                }
        else:
            search_query = {
                "query": {"bool": {"must": [{"match_all": {}}], "filter": filter_clauses}},
                "from": skip,
                "size": limit,
                "sort": sort or [{"_score": "desc"}],
                "track_total_hits": True,
                "aggs": {
                    "id_agg": {"terms": {"field": "id", "size": DEFAULT_FACET_SIZE}},
                    "spatial_agg": {
                        "terms": {"field": "dct_spatial_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "resource_class_agg": {
                        "terms": {"field": "gbl_resourceClass_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "resource_type_agg": {
                        "terms": {"field": "gbl_resourceType_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "index_year_agg": {
                        "terms": {"field": "gbl_indexYear_im", "size": DEFAULT_FACET_SIZE}
                    },
                    "language_agg": {
                        "terms": {"field": "dct_language_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "creator_agg": {
                        "terms": {"field": "dct_creator_sm", "size": DEFAULT_FACET_SIZE}
                    },
                    "provider_agg": {
                        "terms": {"field": "schema_provider_s", "size": DEFAULT_FACET_SIZE}
                    },
                    "access_rights_agg": {
                        "terms": {"field": "dct_accessRights_s", "size": DEFAULT_FACET_SIZE}
                    },
                    "georeferenced_agg": {
                        "terms": {"field": "gbl_georeferenced_b", "size": DEFAULT_FACET_SIZE}
                    },
                    # Spatial facet aggregations with configurable sizes
                    "geo_country_agg": {
                        "terms": {"field": "geo_country", "size": GEO_COUNTRY_FACET_SIZE}
                    },
                    "geo_region_agg": {
                        "terms": {"field": "geo_region", "size": GEO_REGION_FACET_SIZE}
                    },
                    "geo_county_agg": {
                        "terms": {"field": "geo_county", "size": GEO_COUNTY_FACET_SIZE}
                    },
                },
            }

        logger.debug(f"ES Query: {json.dumps(search_query, indent=2)}")

        try:
            response = await es.search(
                index=index_name,
                query=search_query["query"],
                from_=skip,
                size=limit,
                sort=sort or [{"_score": "desc"}],
                track_total_hits=True,
                aggs=search_query["aggs"],
                suggest=search_query.get("suggest"),  # Only include suggest if it exists
            )
        except Exception as es_error:
            logger.error(f"Elasticsearch error: {str(es_error)}", exc_info=True)
            error_detail = {
                "message": "Elasticsearch query failed",
                "error": str(es_error),
                "query": search_query,
                "index": index_name,
            }
            if hasattr(es_error, "info"):
                error_detail["info"] = es_error.info
            if hasattr(es_error, "status_code"):
                error_detail["status_code"] = es_error.status_code
            raise HTTPException(status_code=500, detail=error_detail) from es_error

        logger.info(f"ES Response status: {response.meta.status}")

        return await process_search_response(response, limit, skip, search_criteria)

    except Exception as e:
        logger.error(f"Search documents error: {str(e)}", exc_info=True)
        raise


def get_sort_options(search_criteria):
    """Generate sort options for the response."""
    base_url = os.getenv("APPLICATION_URL") + "/api/v1/search"
    current_params = {"q": search_criteria["query"] or "", "search_field": "all_fields"}

    # Add any existing filters to the params
    if search_criteria["filters"]:
        for field, values in search_criteria["filters"].items():
            if isinstance(values, list):
                for value in values:
                    current_params[f"fq[{field}][]"] = value
            else:
                current_params[f"fq[{field}][]"] = values

    sort_options = [
        {
            "type": "sort",
            "id": "relevance",
            "attributes": {"label": "Relevance"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'relevance'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "year_desc",
            "attributes": {"label": "Year (Newest first)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'year_desc'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "year_asc",
            "attributes": {"label": "Year (Oldest first)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'year_asc'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "title_asc",
            "attributes": {"label": "Title (A-Z)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'title_asc'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "title_desc",
            "attributes": {"label": "Title (Z-A)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'title_desc'}, doseq=True)}"
                )
            },
        },
    ]
    return sort_options


async def process_search_response(response, limit, skip, search_criteria):
    """Process Elasticsearch response and format for API output."""
    try:
        total_hits = response["hits"]["total"]["value"]
        logger.debug(f"Total hits: {total_hits}")

        document_ids = [hit["_source"]["id"] for hit in response["hits"]["hits"]]
        logger.debug(f"Found document IDs: {document_ids}")

        # Process spelling suggestions
        suggestions = []
        if "suggest" in response:
            simple_phrase = response["suggest"].get("simple_phrase", [])
            for suggestion in simple_phrase:
                if suggestion.get("options"):
                    for option in suggestion["options"]:
                        suggestions.append(
                            {
                                "text": option.get("text"),
                                "highlighted": option.get("highlighted"),
                                "score": option.get("score"),
                            }
                        )

        if not document_ids:
            logger.debug("No documents found")
            return {
                "status": "success",
                "query_time": {
                    "elasticsearch": response["took"].__str__() + "ms",
                    "postgresql": "0ms",
                },
                "meta": {
                    "pages": {
                        "current_page": (skip // limit) + 1,
                        "next_page": None,
                        "prev_page": (skip // limit) if skip > 0 else None,
                        "total_pages": 0,
                        "limit_value": limit,
                        "offset_value": skip,
                        "total_count": total_hits,
                        "first_page?": True,
                        "last_page?": True,
                    },
                    "suggestions": suggestions,  # Add suggestions to meta
                },
                "data": [],
                "included": [],
            }

        start_time = time.time()
        # Create a CASE statement to preserve the order of document_ids
        order_case = (
            "CASE "
            + " ".join(
                f"WHEN id = '{doc_id}' THEN {index}" for index, doc_id in enumerate(document_ids)
            )
            + " END"
        )

        query = (
            resources.select().where(resources.c.id.in_(document_ids)).order_by(text(order_case))
        )

        resource_rows = await database.fetch_all(query)
        processed_resources = []

        for resource in resource_rows:
            processed_resources.append(
                {
                    "type": "document",
                    "id": resource["id"],
                    "score": next(
                        hit["_score"]
                        for hit in response["hits"]["hits"]
                        if hit["_source"]["id"] == resource["id"]
                    ),
                    "attributes": {**resource, **create_viewer_attributes(resource)},
                }
            )

        pg_query_time = (time.time() - start_time) * 1000

        included = [
            *process_aggregations(response.get("aggregations", {}), search_criteria),
            *get_sort_options(search_criteria),
        ]

        return {
            "status": "success",
            "query_time": {
                "elasticsearch": response["took"].__str__() + "ms",
                "postgresql": f"{round(pg_query_time)}ms",
            },
            "meta": {
                "pages": {
                    "current_page": (skip // limit) + 1,
                    "next_page": ((skip // limit) + 2) if (skip + limit) < total_hits else None,
                    "prev_page": (skip // limit) if skip > 0 else None,
                    "total_pages": (
                        (total_hits // limit) + (1 if total_hits % limit > 0 else 0)
                        if limit > 0
                        else 0
                    ),
                    "limit_value": limit,
                    "offset_value": skip,
                    "total_count": total_hits,
                    "first_page?": (skip == 0),
                    "last_page?": (skip + limit) >= total_hits,
                },
                "suggestions": suggestions,  # Add suggestions to meta
            },
            "data": processed_resources,
            "included": included,
        }

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"Process response error: {str(e)}", exc_info=True)
        logger.error(f"Full traceback:\n{error_trace}")
        logger.error(f"Response body: {response}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "traceback": error_trace, "response": response},
        ) from e


def process_aggregations(aggregations, search_criteria):
    """Transform Elasticsearch aggregations into JSON:API includes."""
    # Define custom labels for aggregations
    agg_labels = {
        "id_agg": "ID",
        "spatial_agg": "Spatial Coverage",
        "resource_class_agg": "Resource Class",
        "resource_type_agg": "Resource Type",
        "index_year_agg": "Index Year",
        "language_agg": "Language",
        "creator_agg": "Creator",
        "provider_agg": "Provider",
        "access_rights_agg": "Access Rights",
        "georeferenced_agg": "Georeferenced",
        "geo_country_agg": "Country",
        "geo_region_agg": "Region",
        "geo_county_agg": "County",
    }

    return [
        {
            "type": "facet",
            "id": agg_name,
            "attributes": {
                "label": agg_labels.get(
                    agg_name, agg_name.replace("_sm", "").replace("_", " ").title()
                ),
                "items": [
                    {
                        "attributes": {
                            "label": bucket["key"],
                            "value": bucket["key"],
                            "hits": bucket["doc_count"],
                        },
                        "links": {
                            "self": generate_facet_link(agg_name, bucket["key"], search_criteria)
                        },
                    }
                    for bucket in agg_data["buckets"]
                ],
            },
        }
        for agg_name, agg_data in aggregations.items()
    ]


def generate_facet_link(agg_name, facet_value, search_criteria):
    """Generate a link for a facet with current search parameters."""
    base_url = os.getenv("APPLICATION_URL", "http://localhost:8000") + "/api/v1/search"
    query_params = {
        "q": search_criteria["query"] or "",
        "search_field": "all_fields",
        **{
            f"fq[{key}][]": value
            for key, values in search_criteria["filters"].items()
            for value in (values if isinstance(values, list) else [values])
        },
        f"fq[{agg_name}][]": facet_value,
    }
    query_string = "&".join(f"{key}={value}" for key, value in query_params.items())
    return f"{base_url}?{query_string}"
