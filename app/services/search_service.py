import logging
import os
import time
from typing import Dict, Optional
from urllib.parse import parse_qs

from elasticsearch.exceptions import NotFoundError
from fastapi import HTTPException

from app.api.v1.shared import SORT_MAPPINGS
from app.api.v1.utils import sanitize_for_json
from app.elasticsearch import search_resources
from app.elasticsearch.client import es
from app.elasticsearch.search import _normalize_geo_params
from app.services.citation_service import CitationService
from app.services.distribution_repository import (
    build_distribution_context,
    fetch_distribution_context,
    fetch_distribution_context_map,
)
from app.services.download_service import DownloadService
from app.services.image_service import ImageService
from app.services.relationship_service import RelationshipService
from app.services.viewer_service import ViewerService, create_viewer_attributes
from db.database import database

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(self):
        self.index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
        self.es = es

    async def search(
        self,
        q: Optional[str],
        page: int = 1,
        limit: int = 10,
        sort: Optional[str] = None,
        search_fields: Optional[str] = None,
        request_query_params: Optional[str] = None,
        callback: Optional[str] = None,
        facets: Optional[str] = None,
        include_filters: Optional[Dict] = None,
        exclude_filters: Optional[Dict] = None,
        fq_direct: Optional[Dict] = None,
        adv_q: Optional[list] = None,
    ) -> Dict:
        """Search endpoint with caching support."""
        try:
            timings = {}
            start_time = time.time()

            # Calculate skip from page/limit
            skip = (page - 1) * limit

            # Get filter queries either from direct input (POST) or from request params (GET)
            if fq_direct is not None:
                filter_query = fq_direct
            else:
                filter_query = (
                    self.extract_filter_queries(request_query_params)
                    if request_query_params
                    else {}
                )

            logger.info(f"SearchService.search: include_filters={include_filters}, exclude_filters={exclude_filters}, request_query_params={request_query_params[:200] if request_query_params else None}...")
            if include_filters is None or exclude_filters is None:
                logger.info("SearchService.search: Extracting new style filters from request_query_params")
                parsed_include, parsed_exclude = self.extract_new_style_filters(
                    request_query_params
                )
                logger.info(f"SearchService.search: Parsed include_filters={parsed_include}, exclude_filters={parsed_exclude}")
                include_filters = include_filters if include_filters is not None else parsed_include
                exclude_filters = exclude_filters if exclude_filters is not None else parsed_exclude
            logger.info(f"SearchService.search: Final include_filters={include_filters}, exclude_filters={exclude_filters}")

            # Get sort mapping
            sort_mapping = SORT_MAPPINGS.get(sort, None)

            # Elasticsearch query
            es_start = time.time()
            results = await search_resources(
                query=q,
                fq=filter_query,
                skip=skip,
                limit=limit,
                sort=sort_mapping,
                search_fields=search_fields,
                include_filters=include_filters,
                exclude_filters=exclude_filters,
                facets=facets,
                adv_q=adv_q,
            )
            # Defensive: ensure results is a dict
            if not isinstance(results, dict):
                results = {}
            es_time = (time.time() - es_start) * 1000
            timings["elasticsearch"] = f"{es_time:.0f}ms"

            # Process each resource
            process_start = time.time()
            docs_processed = 0
            citation_time = 0
            thumbnail_time = 0
            viewer_time = 0

            resource_ids = [
                resource.get("id") for resource in results.get("data", []) if resource.get("id")
            ]
            distribution_contexts = await fetch_distribution_context_map(resource_ids)

            for resource in results.get("data", []):
                doc_start = time.time()
                resource_id = resource.get("id")
                distribution_context = distribution_contexts.get(
                    resource_id, build_distribution_context(resource_id or "", [])
                )

                # Add thumbnail URL
                thumb_start = time.time()
                image_service = ImageService(
                    resource["attributes"], distribution_context=distribution_context
                )
                resource["attributes"]["ui_thumbnail_url"] = image_service.get_thumbnail_url()
                thumbnail_time += time.time() - thumb_start

                # Add citation
                cite_start = time.time()
                citation_service = CitationService(
                    resource["attributes"], distribution_context=distribution_context
                )
                resource["attributes"]["ui_citation"] = citation_service.get_citation()
                citation_time += time.time() - cite_start

                # Add viewer attributes
                viewer_start = time.time()
                viewer_attrs = create_viewer_attributes(
                    resource["attributes"], distribution_context=distribution_context
                )
                resource["attributes"].update(viewer_attrs)
                viewer_time += time.time() - viewer_start

                docs_processed += 1

            process_time = time.time() - process_start
            timings["resource_processing"] = {
                "total": f"{(process_time * 1000):.0f}ms",
                "per_resource": (
                    f"{((process_time / docs_processed) * 1000):.0f}ms"
                    if docs_processed > 0
                    else "0ms"
                ),
                "thumbnail_service": f"{(thumbnail_time * 1000):.0f}ms",
                "citation_service": f"{(citation_time * 1000):.0f}ms",
                "viewer_service": f"{(viewer_time * 1000):.0f}ms",
            }

            total_time = time.time() - start_time
            timings["total_response_time"] = f"{(total_time * 1000):.0f}ms"

            results["query_time"] = timings

            # Extract and add suggestions to meta if they exist
            if isinstance(results, dict) and "meta" in results and "suggestions" in results["meta"]:
                results["meta"]["spelling_suggestions"] = results["meta"].pop("suggestions")

            # Sanitize the entire results object for JSON
            sanitized_results = sanitize_for_json(results)

            return sanitized_results

        except Exception as e:
            logger.error("Search service error", exc_info=True)
            error_response = {
                "message": "Search operation failed",
                "error": str(e),
                "query": q,
                "filters": filter_query if "filter_query" in locals() else None,
                "sort": sort,
            }
            return error_response

    async def get_resource(
        self,
        id: str,
        callback: Optional[str] = None,
        include_relationships: bool = True,
        include_summaries: bool = True,
    ) -> Dict:
        """Get a single resource by ID."""
        try:
            # Get the resource from Elasticsearch
            try:
                result = await self.es.get(index=self.index_name, id=id)
            except NotFoundError:
                raise HTTPException(status_code=404, detail="Resource not found") from None
            except Exception as e:
                logger.error(f"Elasticsearch error getting resource {id}: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e)) from e

            source_data = result["_source"]

            # Create services
            distribution_context = await fetch_distribution_context(id)
            download_service = DownloadService(
                source_data, distribution_context=distribution_context
            )
            viewer_service = ViewerService(source_data, distribution_context=distribution_context)
            citation_service = CitationService(
                source_data, distribution_context=distribution_context
            )

            # Add UI attributes in the same order as the original code
            source_data["ui_thumbnail_url"] = source_data.get("thumbnail_url")
            source_data["ui_citation"] = citation_service.get_citation()
            source_data["ui_downloads"] = download_service.get_download_options()

            # Add viewer attributes
            viewer_attributes = viewer_service.get_viewer_attributes()
            source_data.update(viewer_attributes)

            # Add relationships if requested
            if include_relationships:
                try:
                    relationship_service = RelationshipService()
                    relationships = await relationship_service.get_resource_relationships(id)
                    source_data["ui_relationships"] = relationships
                except Exception as e:
                    logger.error(f"Error getting relationships: {e}", exc_info=True)
                    source_data["ui_relationships"] = {}

            # Add summaries if requested
            if include_summaries:
                try:
                    summaries_query = """
                        SELECT * FROM resource_ai_enrichments 
                        WHERE resource_id = :resource_id 
                        ORDER BY created_at DESC
                    """
                    summaries = await database.fetch_all(summaries_query, {"resource_id": id})
                    source_data["ui_summaries"] = [
                        sanitize_for_json(dict(summary)) for summary in summaries
                    ]
                except Exception as e:
                    logger.error(f"Error getting summaries: {e}", exc_info=True)
                    source_data["ui_summaries"] = []

            # Create the response structure
            response = {
                "data": {
                    "type": "resource",
                    "id": id,
                    "attributes": source_data,
                }
            }

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting resource {id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def suggest(self, q: str, resource_class: Optional[str] = None, size: int = 5) -> Dict:
        """Get search suggestions."""
        try:
            suggest_query = {
                "_source": [
                    "dct_title_s",
                    "dct_creator_sm",
                    "dct_publisher_sm",
                    "schema_provider_s",
                    "dct_subject_sm",
                    "dct_spatial_sm",
                ],
                "suggest": {
                    "my-suggestion": {
                        "prefix": q,
                        "completion": {
                            "field": "suggest",
                            "size": size,
                            "skip_duplicates": True,
                            "fuzzy": {"fuzziness": "AUTO"},
                        },
                    }
                },
            }
            response = await es.search(index=self.index_name, body=suggest_query)
            response_dict = response.body
            suggestions = []
            seen_ids = set()

            if response_dict.get("suggest", {}).get("my-suggestion"):
                for suggestion in response_dict["suggest"]["my-suggestion"]:
                    if options := suggestion.get("options", []):
                        for option in options:
                            suggestion_id = option["_id"]
                            if suggestion_id not in seen_ids:
                                seen_ids.add(suggestion_id)
                                suggestions.append(
                                    {
                                        "type": "suggestion",
                                        "id": suggestion_id,
                                        "attributes": {
                                            "text": option.get("text", ""),
                                            "title": option.get("_source", {}).get(
                                                "dct_title_s", ""
                                            ),
                                            "score": option.get("_score", 0),
                                        },
                                    }
                                )
            return {
                "data": suggestions,
                "meta": {
                    "query": q,
                    "resource_class": resource_class,
                    "es_query": suggest_query,
                    "es_response": response_dict,
                },
            }
        except Exception as e:
            logger.error(f"Error getting suggestions: {str(e)}", exc_info=True)
            return {"data": [], "meta": {"error": str(e)}}

    def extract_filter_queries(self, params: str) -> Dict:
        """Extract filter queries from request parameters."""
        filter_query = {}
        # Parse the raw query string to handle multiple values
        raw_params = parse_qs(str(params))

        agg_to_field = {
            "id_agg": "id.keyword",
            "spatial_agg": "dct_spatial_sm",
            "resource_type_agg": "gbl_resourceType_sm",
            "resource_class_agg": "gbl_resourceClass_sm",
            "index_year_agg": "gbl_indexYear_im",
            "language_agg": "dct_language_sm",
            "creator_agg": "dct_creator_sm",
            "provider_agg": "schema_provider_s",
            "access_rights_agg": "dct_accessRights_s",
            "georeferenced_agg": "gbl_georeferenced_b",
            # Spatial facet fields
            "geo_country_agg": "geo_country",
            "geo_region_agg": "geo_region",
            "geo_county_agg": "geo_county",
        }

        # Define allowed direct fields (the mapping values)
        allowed_direct_fields = set(agg_to_field.values())

        for key, values in raw_params.items():
            if key.startswith("fq[") and key.endswith("][]"):
                # Allow aggregation aliases or direct ES fields; ignore unknown
                name = key[3:-3]  # Remove 'fq[' and '[]'
                if name in agg_to_field:
                    es_field = agg_to_field[name]
                elif name in allowed_direct_fields:
                    es_field = name
                else:
                    continue
                if values:
                    filter_query[es_field] = values
            elif key.startswith("fq[") and key.endswith("]"):
                # Single value form fq[field]=value
                name = key[3:-1]
                if name in agg_to_field:
                    es_field = agg_to_field[name]
                elif name in allowed_direct_fields:
                    es_field = name
                else:
                    continue
                if values:
                    filter_query[es_field] = values[0]

        return filter_query

    def extract_new_style_filters(self, params: Optional[str]) -> tuple[Dict, Dict]:
        """
        Extract include/exclude filters passed as
        include_filters[field][]= and exclude_filters[field][].
        Also handles geospatial filters like include_filters[geo][type]=bbox.
        """
        include_filters: Dict[str, list] = {}
        exclude_filters: Dict[str, list] = {}
        if not params:
            logger.info("extract_new_style_filters: No params provided")
            return include_filters, exclude_filters
        logger.info(f"extract_new_style_filters: Parsing params: {params[:200] if params else 'None'}...")
        # parse_qs expects a URL-decoded query string
        # If params is URL-encoded (contains %5B for [), decode it first
        from urllib.parse import unquote
        if params and '%5B' in params:
            # URL-encoded brackets detected, decode first
            decoded_params = unquote(params)
            logger.info(f"extract_new_style_filters: Decoded params sample: {decoded_params[:200]}")
            raw_params = parse_qs(decoded_params)
        elif isinstance(params, str):
            raw_params = parse_qs(params)
        else:
            raw_params = parse_qs(str(params))
        logger.info(f"extract_new_style_filters: Found {len(raw_params)} raw params")
        geo_keys = [k for k in raw_params.keys() if 'geo' in k.lower()]
        logger.info(f"extract_new_style_filters: Geo-related keys: {geo_keys}")
        logger.info(f"extract_new_style_filters: All keys sample: {list(raw_params.keys())[:10]}")

        # Handle geospatial filters
        geo_filters = {}
        for key, values in raw_params.items():
            if key.startswith("include_filters[geo]["):
                # Skip array-style parameters like "include_filters[geo][]" - these are duplicates/artifacts
                if key == "include_filters[geo][]" or key.endswith("][]") and key.count("[") == 2:
                    # This is an array-style parameter without a proper key name, skip it
                    continue
                
                # Extract the geospatial parameter (e.g., "type", "field", "top_left[lat]")
                # Handle both "include_filters[geo][param]" and "include_filters[geo][param][]" formats
                prefix = "include_filters[geo]["
                if key.endswith("][]"):
                    # Array-style parameter like "include_filters[geo][type][]"
                    geo_param = key[len(prefix) : -len("][]")]
                elif key.startswith(prefix):
                    # Regular parameter like "include_filters[geo][type]" or "include_filters[geo][top_left][lat]"
                    # Remove the prefix, keep the rest (including any nested brackets)
                    geo_param = key[len(prefix):]
                    # Remove trailing ] if present (for simple params like "type]")
                    # But keep it if it's part of nested structure like "top_left][lat]"
                    if geo_param.endswith("]"):
                        # Check if this is a nested param (has [ before the final ])
                        last_bracket_idx = geo_param.rfind("[")
                        if last_bracket_idx == -1:
                            # No nested brackets, remove trailing ]
                            geo_param = geo_param[:-1]
                        else:
                            # Has nested brackets, the structure is "parent][child]"
                            # We want "parent[child]", so remove the ] before the [
                            # Actually, the structure is correct: "top_left][lat]" means parent="top_left]", child="lat"
                            # But we want parent="top_left", child="lat", so we need to fix this
                            # The issue is that "top_left][lat]" should be parsed as parent="top_left", child="lat"
                            # So we need to split on "][" to get ["top_left", "lat]"] and then remove the trailing ] from the child
                            if "][" in geo_param:
                                parts = geo_param.split("][")
                                if len(parts) == 2:
                                    parent = parts[0]
                                    child = parts[1].rstrip("]")
                                    geo_param = f"{parent}[{child}]"
                else:
                    continue
                
                # Skip empty parameter names
                if not geo_param:
                    continue
                
                # Handle nested parameters like top_left[lat]
                if "[" in geo_param and "]" in geo_param:
                    # This is a nested parameter like "top_left[lat]"
                    parent_key = geo_param.split("[")[0]
                    child_key = geo_param.split("[")[1].split("]")[0]
                    if parent_key not in geo_filters:
                        geo_filters[parent_key] = {}
                    geo_filters[parent_key][child_key] = values[0] if values else None
                    logger.info(f"  Added nested param: {parent_key}[{child_key}] = {values[0] if values else None}")
                else:
                    # For simple parameters, use the first value if not already set
                    # This handles duplicate parameters by taking the first occurrence
                    if geo_param not in geo_filters:
                        geo_filters[geo_param] = values[0] if values else None
                        logger.info(f"  Added simple param: {geo_param} = {values[0] if values else None}")

        # If we have geospatial filters, add them to include_filters
        if geo_filters:
            logger.info(f"Raw geo_filters before normalization: {geo_filters}")
            normalized_geo = _normalize_geo_params(geo_filters)
            logger.info(f"Normalized geo_filters: {normalized_geo}")
            include_filters["geo"] = normalized_geo
        else:
            logger.warning(f"No geo_filters found! Processed {len(raw_params)} params, geo_keys: {geo_keys}")

        # Handle regular field filters
        for key, values in raw_params.items():
            if (
                key.startswith("include_filters[")
                and key.endswith("][]")
                and not key.startswith("include_filters[geo][")
            ):
                field = key[len("include_filters[") : -len("][]")]
                include_filters[field] = values
            if key.startswith("exclude_filters[") and key.endswith("][]"):
                field = key[len("exclude_filters[") : -len("][]")]
                exclude_filters[field] = values
        return include_filters, exclude_filters
