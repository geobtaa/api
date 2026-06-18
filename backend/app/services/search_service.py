import inspect
import json
import logging
import os
import time
from typing import Dict, Optional
from urllib.parse import parse_qs

from elasticsearch.exceptions import NotFoundError
from fastapi import HTTPException

from app.api.v1.shared import SORT_MAPPINGS
from app.api.v1.utils import create_jsonapi_resource, sanitize_for_json
from app.elasticsearch import search_resources
from app.elasticsearch.client import es
from app.elasticsearch.search import (
    _normalize_geo_params,
    is_public_resource_document,
    public_visibility_filter_clauses,
)
from app.elasticsearch.suggest import (
    SUGGEST_SOURCE_FIELDS,
    build_suggest_inputs,
    normalize_suggestion_text,
    suggestion_sort_key,
)
from app.services.citation_service import CitationService
from app.services.distribution_repository import fetch_distribution_context
from app.services.download_service import DownloadService
from app.services.relationship_service import RelationshipService
from app.services.viewer_service import ViewerService
from db.database import database

logger = logging.getLogger(__name__)
_SEARCH_ERROR_CODE = "search_request_failed"


def _search_error_payload(error: object) -> Dict[str, str]:
    return {
        "message": "Search operation failed",
        "error": _SEARCH_ERROR_CODE,
        "error_type": _search_error_type(error),
    }


def _search_error_text(error: object) -> str:
    """Serialize nested framework/client errors for classification."""
    if isinstance(error, BaseException):
        parts = [str(error)]
        detail = getattr(error, "detail", None)
        if detail is not None:
            parts.append(_search_error_text(detail))
        return " ".join(parts)

    if isinstance(error, dict):
        try:
            return json.dumps(sanitize_for_json(error), default=str)
        except Exception:
            return str(error)

    return str(error)


def _search_error_status(error: object) -> int | None:
    if isinstance(error, BaseException):
        status_code = getattr(error, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        detail = getattr(error, "detail", None)
        if detail is not None:
            return _search_error_status(detail)
        return None

    if isinstance(error, dict):
        for key in ("status_code", "status"):
            status_code = error.get(key)
            if isinstance(status_code, int):
                return status_code
        for key in ("detail", "info"):
            nested = error.get(key)
            if isinstance(nested, dict):
                nested_status = _search_error_status(nested)
                if nested_status is not None:
                    return nested_status

    return None


def _search_error_type(error: object) -> str:
    """Classify search dependency failures for stable caller payloads."""
    status_code = _search_error_status(error)
    error_text = _search_error_text(error).lower()
    connection_terms = (
        '"status": 503',
        '"status_code": 503',
        "'status': 503",
        "'status_code': 503",
        "apierror(503",
        "cannot connect",
        "connect call failed",
        "connection",
        "connection refused",
        "nodename",
        "operation not permitted",
        "service unavailable",
        "servname",
        "timed out",
        "timeout",
    )

    if status_code == 503 or any(term in error_text for term in connection_terms):
        return "connection"
    if "elasticsearch" in error_text:
        return "elasticsearch"
    return "unknown"


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
        hydrate_hits: bool = True,
        sanitize_response: bool = True,
        include_non_public: bool = False,
    ) -> Dict:
        """Search endpoint with caching support."""
        try:
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

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "SearchService.search: include_filters=%s, exclude_filters=%s, "
                    "request_query_params=%s...",
                    include_filters,
                    exclude_filters,
                    request_query_params[:200] if request_query_params else None,
                )
            if include_filters is None or exclude_filters is None:
                logger.debug(
                    "SearchService.search: Extracting new style filters from request_query_params"
                )
                parsed_include, parsed_exclude = self.extract_new_style_filters(
                    request_query_params
                )
                logger.debug(
                    "SearchService.search: Parsed include_filters=%s, exclude_filters=%s",
                    parsed_include,
                    parsed_exclude,
                )
                include_filters = include_filters if include_filters is not None else parsed_include
                exclude_filters = exclude_filters if exclude_filters is not None else parsed_exclude
            logger.debug(
                "SearchService.search: Final include_filters=%s, exclude_filters=%s",
                include_filters,
                exclude_filters,
            )

            # Get sort mapping
            sort_mapping = SORT_MAPPINGS.get(sort, None)

            # Elasticsearch query
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
                hydrate_hits=hydrate_hits,
                include_non_public=include_non_public,
            )
            # Defensive: ensure results is a dict
            if not isinstance(results, dict):
                results = {}
            if "error" in results:
                results.update(_search_error_payload(results))

            total_time = time.time() - start_time
            query_timings = results.get("queryTime", {})
            if not isinstance(query_timings, dict):
                query_timings = {}
            query_timings.setdefault(
                "resourceProcessing",
                {
                    "total": "0ms",
                    "perResource": "0ms",
                    "thumbnailService": "0ms",
                    "citationService": "0ms",
                    "viewerService": "0ms",
                },
            )
            query_timings["totalResponseTime"] = f"{(total_time * 1000):.0f}ms"
            results["queryTime"] = query_timings

            # Extract and add suggestions to meta if they exist
            if isinstance(results, dict) and "meta" in results and "suggestions" in results["meta"]:
                results["meta"]["spellingSuggestions"] = results["meta"].pop("suggestions")

            # Sanitize the entire results object for JSON
            if not sanitize_response:
                return results

            sanitized_results = sanitize_for_json(results)
            return sanitized_results

        except Exception as e:
            logger.error("Search service error", exc_info=True)
            return _search_error_payload(e)

    async def get_resource(
        self,
        id: str,
        callback: Optional[str] = None,
        include_relationships: bool = True,
        include_summaries: bool = True,
        include_non_public: bool = False,
    ) -> Dict:
        """Get a single resource by ID."""
        try:
            # Get the resource from Elasticsearch
            try:
                result = es.get(index=self.index_name, id=id)
                if inspect.isawaitable(result):
                    result = await result
            except NotFoundError:
                raise HTTPException(status_code=404, detail="Resource not found") from None
            except Exception as e:
                logger.error("Elasticsearch error getting resource %s", id, exc_info=True)
                detail = str(e)
                if _search_error_type(e) == "connection":
                    detail = f"Elasticsearch connection/unavailable error: {detail}"
                raise HTTPException(status_code=500, detail=detail) from e

            source_data = result["_source"]
            if not include_non_public and not is_public_resource_document(source_data):
                raise HTTPException(status_code=404, detail="Resource not found")

            references = source_data.get("dct_references_s")
            if isinstance(references, str):
                try:
                    source_data["dct_references_s"] = json.loads(references)
                except json.JSONDecodeError:
                    pass

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
            ui_downloads = download_service.get_download_options_with_bridge_asset_downloads()
            if inspect.isawaitable(ui_downloads):
                ui_downloads = await ui_downloads
            source_data["ui_downloads"] = ui_downloads

            # Add viewer attributes
            viewer_attributes = viewer_service.get_viewer_attributes()
            source_data.update(viewer_attributes)

            # Add relationships if requested
            if include_relationships:
                try:
                    relationship_service = RelationshipService()
                    relationships = relationship_service.get_resource_relationships(id)
                    if inspect.isawaitable(relationships):
                        relationships = await relationships
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
                    summaries = database.fetch_all(summaries_query, {"resource_id": id})
                    if inspect.isawaitable(summaries):
                        summaries = await summaries
                    source_data["ui_summaries"] = [
                        sanitize_for_json(dict(summary)) for summary in summaries
                    ]
                except Exception as e:
                    logger.error(f"Error getting summaries: {e}", exc_info=True)
                    source_data["ui_summaries"] = []

            response = {"data": create_jsonapi_resource(source_data)}

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error getting resource %s", id, exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from e

    async def suggest(
        self,
        q: str,
        resource_class: Optional[str] = None,
        size: int = 5,
        include_non_public: bool = False,
    ) -> Dict:
        """Get search suggestions."""
        try:
            raw_size = max(size * 4, 10)
            normalized_query = normalize_suggestion_text(q) or q.strip().lower()
            filter_clauses = public_visibility_filter_clauses(include_non_public=include_non_public)
            if resource_class:
                filter_clauses.append({"term": {"gbl_resourceClass_sm.keyword": resource_class}})

            bool_query = {
                "must": [
                    {
                        "multi_match": {
                            "query": q,
                            "type": "bool_prefix",
                            "fields": list(SUGGEST_SOURCE_FIELDS),
                        }
                    }
                ]
            }
            if filter_clauses:
                bool_query["filter"] = filter_clauses

            suggest_query = {
                "query": {
                    "bool": bool_query,
                },
                "_source": list(SUGGEST_SOURCE_FIELDS),
                "size": raw_size,
            }
            response = es.search(
                index=self.index_name,
                query=suggest_query["query"],
                size=raw_size,
                _source=suggest_query["_source"],
            )
            if inspect.isawaitable(response):
                response = await response
            response_dict = response.body if hasattr(response, "body") else response
            suggestions_by_id = {}
            suggestions_by_text = {}

            hits = response_dict.get("hits", {}).get("hits", [])
            for hit in hits:
                hit_id = hit.get("_id")
                source = hit.get("_source", {}) or {}
                hit_score = hit.get("_score", 0)
                for suggestion_text in build_suggest_inputs(source):
                    if normalized_query and normalized_query not in suggestion_text:
                        continue
                    suggestion_candidate = {
                        "type": "suggestion",
                        "id": hit_id,
                        "attributes": {
                            "text": suggestion_text,
                            "score": hit_score,
                        },
                    }
                    existing_by_id = suggestions_by_id.get(hit_id)
                    if existing_by_id and suggestion_sort_key(
                        existing_by_id["attributes"]["text"],
                        q,
                        existing_by_id["attributes"]["score"],
                    ) <= suggestion_sort_key(suggestion_text, q, hit_score):
                        continue

                    suggestions_by_id[hit_id] = suggestion_candidate

            # Compatibility fallback for older mocks/responses shaped like completion suggesters.
            if not suggestions_by_id and response_dict.get("suggest", {}).get("my-suggestion"):
                for suggestion in response_dict["suggest"]["my-suggestion"]:
                    if options := suggestion.get("options", []):
                        for option in options:
                            normalized_text = normalize_suggestion_text(option.get("text", ""))
                            if not normalized_text:
                                continue

                            suggestion_score = option.get("_score", 0)
                            suggestion_candidate = {
                                "type": "suggestion",
                                "id": option["_id"],
                                "attributes": {
                                    "text": normalized_text,
                                    "score": suggestion_score,
                                },
                            }
                            existing_by_id = suggestions_by_id.get(option["_id"])
                            if existing_by_id and suggestion_sort_key(
                                existing_by_id["attributes"]["text"],
                                q,
                                existing_by_id["attributes"]["score"],
                            ) <= suggestion_sort_key(normalized_text, q, suggestion_score):
                                continue

                            suggestions_by_id[option["_id"]] = suggestion_candidate

            for suggestion_candidate in suggestions_by_id.values():
                normalized_text = suggestion_candidate["attributes"]["text"]
                existing_by_text = suggestions_by_text.get(normalized_text)
                if existing_by_text and suggestion_sort_key(
                    existing_by_text["attributes"]["text"],
                    q,
                    existing_by_text["attributes"]["score"],
                ) <= suggestion_sort_key(
                    normalized_text,
                    q,
                    suggestion_candidate["attributes"]["score"],
                ):
                    continue

                suggestions_by_text[normalized_text] = suggestion_candidate

            suggestions = sorted(
                suggestions_by_text.values(),
                key=lambda item: suggestion_sort_key(
                    item["attributes"]["text"],
                    q,
                    item["attributes"]["score"],
                ),
            )[:size]
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
            logger.error("Error getting suggestions", exc_info=True)
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
            "language_agg": "b1g_language_sm",
            "creator_agg": "dct_creator_sm",
            "publisher_agg": "dct_publisher_sm",
            "provider_agg": "schema_provider_s",
            "b1g_code_agg": "b1g_code_s",
            "access_rights_agg": "dct_accessRights_s",
            "georeferenced_agg": "gbl_georeferenced_b",
            "map_overlay_agg": "b1g_georeferenced_allmaps_b",
            # Spatial facet fields
            "geo_country_agg": "geo_country",
            "geo_region_agg": "geo_region",
            "geo_county_agg": "geo_county",
            # Relationship filters (has part / is part of; collection records / member of)
            "dct_isPartOf_sm": "dct_isPartOf_sm",
            "pcdm_memberOf_sm": "pcdm_memberOf_sm",
            # Local collection label (facets in Full Details)
            "b1g_localCollectionLabel_sm": "b1g_localCollectionLabel_sm",
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
            logger.debug("extract_new_style_filters: No params provided")
            return include_filters, exclude_filters
        logger.debug(
            "extract_new_style_filters: Parsing params: %s...",
            params[:200] if params else "None",
        )
        # parse_qs expects a URL-decoded query string
        # If params is URL-encoded (contains %5B for [), decode it first
        from urllib.parse import unquote

        if params and "%5B" in params:
            # URL-encoded brackets detected, decode first
            decoded_params = unquote(params)
            logger.debug(
                "extract_new_style_filters: Decoded params sample: %s",
                decoded_params[:200],
            )
            raw_params = parse_qs(decoded_params)
        elif isinstance(params, str):
            raw_params = parse_qs(params)
        else:
            raw_params = parse_qs(str(params))
        geo_keys: list[str] = []
        if logger.isEnabledFor(logging.DEBUG):
            geo_keys = [k for k in raw_params.keys() if "geo" in k.lower()]
            logger.debug("extract_new_style_filters: Found %s raw params", len(raw_params))
            logger.debug("extract_new_style_filters: Geo-related keys: %s", geo_keys)
            logger.debug(
                "extract_new_style_filters: All keys sample: %s",
                list(raw_params.keys())[:10],
            )

        # Convenience filters (non-bracket style) for common client use cases.
        # Example: ogm_repo[]=edu.stanford.purl&ogm_repo[]=edu.umn
        if "ogm_repo[]" in raw_params:
            include_filters.setdefault("ogm_repo", []).extend(raw_params.get("ogm_repo[]") or [])

        # Handle geospatial filters
        geo_filters = {}
        for key, values in raw_params.items():
            if key.startswith("include_filters[geo]["):
                # Skip array-style parameters like "include_filters[geo][]"
                # These are duplicates/artifacts
                if key == "include_filters[geo][]" or key.endswith("][]") and key.count("[") == 2:
                    # This is an array-style parameter without a proper key name, skip it
                    continue

                # Extract the geospatial parameter (e.g., "type", "field", "top_left[lat]")
                # Handle both "include_filters[geo][param]"
                # and "include_filters[geo][param][]" formats
                prefix = "include_filters[geo]["
                if key.endswith("][]"):
                    # Array-style parameter like "include_filters[geo][type][]"
                    geo_param = key[len(prefix) : -len("][]")]
                elif key.startswith(prefix):
                    # Regular parameter like "include_filters[geo][type]"
                    # or "include_filters[geo][top_left][lat]"
                    # or "include_filters[geo][points][0][lat]"
                    # Remove the prefix, keep the rest (including any nested brackets)
                    geo_param = key[len(prefix) :]

                    # Special handling for points array format: "points][0][lat]"
                    # Handle this before general bracket processing - skip conversion
                    if geo_param.startswith("points][") and geo_param.count("][") >= 2:
                        # Keep as "points][0][lat]" format for special handling below
                        # Don't modify geo_param, it will be handled in the points parsing section
                        pass
                    # Remove trailing ] if present (for simple params like "type]")
                    # But keep it if it's part of nested structure like "top_left][lat]"
                    elif geo_param.endswith("]"):
                        # Check if this is a nested param (has [ before the final ])
                        last_bracket_idx = geo_param.rfind("[")
                        if last_bracket_idx == -1:
                            # No nested brackets, remove trailing ]
                            geo_param = geo_param[:-1]
                        else:
                            # Has nested brackets, the structure is "parent][child]"
                            # We want "parent[child]", so remove the ] before the [
                            # Actually, the structure is correct:
                            # "top_left][lat]" means parent="top_left]", child="lat"
                            # But we want parent="top_left", child="lat", so we need to fix this
                            # The issue is that "top_left][lat]" should be parsed as
                            # parent="top_left", child="lat"
                            # So we need to split on "][" to get ["top_left", "lat]"]
                            # and then remove the trailing ] from the child
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

                # Handle nested parameters like top_left[lat] or points[0][lat]
                # Note: points][0][lat] format should be passed through to _normalize_geo_params
                # which handles the conversion from flat keys to nested structure
                if "[" in geo_param and "]" in geo_param:
                    # Check if this is an array-style parameter like "points][0][lat]"
                    # or "points[0][lat]"
                    # The format after prefix removal is "points][0][lat]" (with ] between parts)
                    if geo_param.startswith("points"):
                        # For points, we need to pass the key through to _normalize_geo_params
                        # which will handle the conversion. Store it with the original key format.
                        # The _normalize_geo_params function expects keys like "points][0][lat]"
                        # So we store it as a flat key that will be processed by normalization
                        geo_filters[geo_param] = values[0] if values else None
                        value_str = values[0] if values else None
                        logger.debug("Added points param (raw): %s = %s", geo_param, value_str)
                        continue

                    # This is a nested parameter like "top_left][lat]" or "top_left[lat]"
                    if "][" in geo_param:
                        # Format: "top_left][lat]"
                        parts = geo_param.split("][")
                        if len(parts) == 2:
                            parent_key = parts[0]
                            child_key = parts[1].rstrip("]")
                            if parent_key not in geo_filters:
                                geo_filters[parent_key] = {}
                            geo_filters[parent_key][child_key] = values[0] if values else None
                            logger.debug(
                                "Added nested param: %s[%s] = %s",
                                parent_key,
                                child_key,
                                values[0] if values else None,
                            )
                    else:
                        # Format: "top_left[lat]"
                        parent_key = geo_param.split("[")[0]
                        child_key = geo_param.split("[")[1].split("]")[0]
                        if parent_key not in geo_filters:
                            geo_filters[parent_key] = {}
                        geo_filters[parent_key][child_key] = values[0] if values else None
                        logger.debug(
                            "Added nested param: %s[%s] = %s",
                            parent_key,
                            child_key,
                            values[0] if values else None,
                        )
                else:
                    # For simple parameters, use the first value if not already set
                    # This handles duplicate parameters by taking the first occurrence
                    if geo_param not in geo_filters:
                        geo_filters[geo_param] = values[0] if values else None
                        logger.debug(
                            "Added simple param: %s = %s",
                            geo_param,
                            values[0] if values else None,
                        )

        # If we have geospatial filters, add them to include_filters
        if geo_filters:
            logger.debug("Raw geo_filters before normalization: %s", geo_filters)
            normalized_geo = _normalize_geo_params(geo_filters)
            logger.debug("Normalized geo_filters: %s", normalized_geo)
            include_filters["geo"] = normalized_geo
        else:
            logger.debug(
                "No geo_filters found. Processed %s params, geo_keys: %s",
                len(raw_params),
                geo_keys,
            )

        # Handle year_range filters
        year_range_filters = {}
        for key, values in raw_params.items():
            if key.startswith("include_filters[year_range][") and key.endswith("]"):
                sub_key = key[len("include_filters[year_range][") : -1]  # start or end
                year_range_filters[sub_key] = values[0] if values else None

        if year_range_filters:
            include_filters["year_range"] = year_range_filters

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
