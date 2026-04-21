"""
Tests for the Elasticsearch search functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.elasticsearch.search import (
    BBOX_SPATIAL_BOOST_WEIGHT,
    MIN_BBOX_IOU_OVERLAP_RATIO,
    _compute_bbox_spatial_metrics,
    _escape_query_string_brackets,
    get_search_criteria,
    map_h3_aggregation,
    search_resources,
)


class TestElasticsearchSearch:
    """Test cases for Elasticsearch search functionality."""

    def test_escape_query_string_brackets(self):
        """Literal [] in user queries should be escaped for query_string."""
        query = "Michigan Aquaculture Testing Veterinarians [Michigan]"
        escaped = _escape_query_string_brackets(query)
        assert escaped == r"Michigan Aquaculture Testing Veterinarians \[Michigan\]"

    def test_escape_query_string_curly_braces(self):
        """Literal {} in user queries should be escaped for query_string."""
        query = "Precipitation (08) [Minnesota] {1991-2020 August}"
        escaped = _escape_query_string_brackets(query)
        assert escaped == r"Precipitation (08) \[Minnesota\] \{1991-2020 August\}"

    def test_escape_query_string_colon_in_identifier(self):
        """Literal colons in identifiers should not become fielded-query syntax."""
        query = "p16022coll244:471"
        escaped = _escape_query_string_brackets(query)
        assert escaped == r"p16022coll244\:471"

    def test_get_search_criteria(self):
        """Test the get_search_criteria function."""
        criteria = get_search_criteria(
            query="test query",
            fq={"dct_spatial_sm": ["Minnesota"]},
            skip=10,
            limit=20,
            sort=[{"_score": "desc"}],
        )

        assert criteria["query"] == "test query"
        assert criteria["filters"] == {"dct_spatial_sm": ["Minnesota"]}
        assert criteria["sort"] == [{"_score": "desc"}]

    def test_compute_bbox_spatial_metrics_rewards_containment(self):
        """Contained extents should still score well even when query bbox is larger."""
        metrics = _compute_bbox_spatial_metrics(
            d_minx=-93.4,
            d_maxx=-93.1,
            d_miny=44.9,
            d_maxy=45.1,
            q_minx=-93.5,
            q_maxx=-92.9,
            q_miny=44.8,
            q_maxy=45.2,
        )

        assert metrics["containment_ratio"] == pytest.approx(1.0)
        assert metrics["overlap_ratio"] < metrics["containment_ratio"]
        assert metrics["spatial_score"] > metrics["overlap_ratio"]

    def test_compute_bbox_spatial_metrics_returns_zero_for_no_overlap(self):
        """Non-overlapping extents should not receive a spatial boost."""
        metrics = _compute_bbox_spatial_metrics(
            d_minx=-100.0,
            d_maxx=-99.0,
            d_miny=40.0,
            d_maxy=41.0,
            q_minx=-93.5,
            q_maxx=-92.9,
            q_miny=44.8,
            q_maxy=45.2,
        )

        assert metrics == {
            "overlap_ratio": 0.0,
            "containment_ratio": 0.0,
            "spatial_score": 0.0,
        }

    @pytest.mark.asyncio
    async def test_search_resources_with_id_field_in_query_string(self):
        """Test that search_resources includes id field in query_string query."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources with a query
                await search_resources(
                    query="test-resource-id", fq=None, skip=0, limit=10, sort=None
                )

                # Verify that es.search was called
                mock_es.search.assert_called_once()

                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify the query structure
                assert search_query is not None
                assert "bool" in search_query
                assert "must" in search_query["bool"]

                # Find the query_string query in the must clause
                query_string_found = False
                for clause in search_query["bool"]["must"]:
                    if "query_string" in clause:
                        query_string_found = True
                        query_string = clause["query_string"]

                        # Verify that the id field is included with boost
                        fields = query_string["fields"]
                        id_field_found = False
                        for field in fields:
                            if field.startswith("id^"):
                                id_field_found = True
                                # Verify it has a high boost (^5)
                                assert field == "id^5"
                                break

                        assert id_field_found, (
                            "ID field with boost not found in query_string fields"
                        )
                        break

                assert query_string_found, "query_string query not found in search"

    @pytest.mark.asyncio
    async def test_search_resources_without_query(self):
        """Test search_resources without a query (match_all)."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources without a query
                await search_resources(query=None, fq=None, skip=0, limit=10, sort=None)

                # Verify that es.search was called
                mock_es.search.assert_called_once()

                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify the query structure for match_all
                assert search_query is not None
                assert "bool" in search_query
                assert "must" in search_query["bool"]
                assert {"match_all": {}} in search_query["bool"]["must"]

    @pytest.mark.asyncio
    async def test_search_resources_with_filters(self):
        """Test search_resources with filter queries."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources with filters
                await search_resources(
                    query="test",
                    fq={"dct_spatial_sm": ["Minnesota", "Wisconsin"]},
                    skip=0,
                    limit=10,
                    sort=None,
                )

                # Verify that es.search was called
                mock_es.search.assert_called_once()

                # Get the search query that was passed
                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify the query structure includes filters
                assert search_query is not None
                assert "bool" in search_query
                assert "filter" in search_query["bool"]

                # Verify the filter clause
                filter_clauses = search_query["bool"]["filter"]
                assert len(filter_clauses) == 1
                assert "terms" in filter_clauses[0]
                # Field is resolved to .keyword suffix via _resolve_filter_field
                assert filter_clauses[0]["terms"]["dct_spatial_sm.keyword"] == [
                    "Minnesota",
                    "Wisconsin",
                ]

    @pytest.mark.asyncio
    async def test_map_h3_aggregation_applies_adv_q_to_hexes_and_global_count(self):
        """Advanced clauses should constrain both map hexes and the map global count."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "aggregations": {
                "h3_terms": {"buckets": []},
                "global_bucket_agg": {"doc_count": 0},
            }
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.es", mock_es):
            await map_h3_aggregation(
                q="",
                adv_q=[{"op": "OR", "f": "dct_title_s", "q": "water"}],
                bbox="-80,40,-74,43",
                resolution=5,
            )

        assert mock_es.search.await_count == 2

        first_query = mock_es.search.await_args_list[0].kwargs["query"]["bool"]
        second_query = mock_es.search.await_args_list[1].kwargs["query"]["bool"]

        for bool_query in (first_query, second_query):
            assert bool_query["should"] == [
                {"match": {"dct_title_s": {"query": "water", "operator": "and"}}}
            ]
            assert bool_query["minimum_should_match"] == 1

    @pytest.mark.asyncio
    async def test_search_resources_relationship_filters_use_keyword_subfield(self):
        """Relationship filters (dct_isPartOf_sm, pcdm_memberOf_sm) use .keyword for exact match."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None,
                    include_filters={
                        "dct_isPartOf_sm": ["parent-id-123"],
                        "pcdm_memberOf_sm": ["collection-id-456"],
                    },
                )

                mock_es.search.assert_called_once()
                search_query = mock_es.search.call_args.kwargs["query"]
                filter_clauses = search_query["bool"]["filter"]

                terms_filters = [c for c in filter_clauses if "terms" in c]
                assert len(terms_filters) == 2
                by_field = {
                    list(f["terms"].keys())[0]: list(f["terms"].values())[0] for f in terms_filters
                }
                assert "dct_isPartOf_sm.keyword" in by_field
                assert "pcdm_memberOf_sm.keyword" in by_field
                assert by_field["dct_isPartOf_sm.keyword"] == ["parent-id-123"]
                assert by_field["pcdm_memberOf_sm.keyword"] == ["collection-id-456"]

    @pytest.mark.asyncio
    async def test_search_resources_with_geospatial_polygon_filter(self):
        """Ensure include_filters.geo polygon creates a geo_shape filter."""

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    fq=None,
                    skip=0,
                    limit=5,
                    sort=None,
                    include_filters={
                        "geo": {
                            "type": "polygon",
                            "field": "locn_geometry",
                            "relation": "intersects",
                            "points": [
                                {"lat": 45.0, "lon": -104.0},
                                {"lat": 45.0, "lon": -109.0},
                                {"lat": 41.0, "lon": -109.0},
                                {"lat": 41.0, "lon": -104.0},
                            ],
                        }
                    },
                )

                mock_es.search.assert_called_once()
                search_query = mock_es.search.call_args.kwargs["query"]
                filters = search_query["bool"]["filter"]

                geo_filter = next((f for f in filters if "geo_shape" in f), None)
                assert geo_filter is not None, "Geo filter not present in ES query"

                geo_shape = geo_filter["geo_shape"]
                assert "locn_geometry" in geo_shape
                shape = geo_shape["locn_geometry"]["shape"]
                assert shape["type"] == "polygon"
                coords = shape["coordinates"][0]
                assert coords[0] == coords[-1], "Polygon should be closed"

    @pytest.mark.asyncio
    async def test_search_resources_with_geospatial_bbox_filter(self):
        """Ensure bbox include filter generates geo_bounding_box."""

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    fq=None,
                    skip=0,
                    limit=5,
                    sort=None,
                    include_filters={
                        "geo": {
                            "type": "bbox",
                            "field": "dcat_bbox",
                            "top_left": {"lat": 45.0, "lon": -109.0},
                            "bottom_right": {"lat": 41.0, "lon": -104.0},
                        }
                    },
                )

                search_query = mock_es.search.call_args.kwargs["query"]
                # Query might be wrapped in script_score for bbox, or be a bool query
                if "script_score" in search_query:
                    bool_query = search_query["script_score"]["query"]["bool"]
                else:
                    bool_query = search_query["bool"]

                # Filter should exist when geo filter is present
                assert "filter" in bool_query
                filters = bool_query["filter"]
                # For dcat_bbox field, it uses geo_shape, not geo_bounding_box
                geo_filter = next(
                    (f for f in filters if "geo_shape" in f or "geo_bounding_box" in f),
                    None,
                )
                assert geo_filter is not None
                # For dcat_bbox, the code uses geo_shape with envelope type
                if "geo_shape" in geo_filter:
                    shape = geo_filter["geo_shape"]["dcat_bbox"]["shape"]
                    assert shape["type"] == "envelope"
                    # Envelope format: [[min_lon, max_lat], [max_lon, min_lat]]
                    coords = shape["coordinates"]
                    assert coords[0] == [-109.0, 45.0]  # [min_lon, max_lat]
                    assert coords[1] == [-104.0, 41.0]  # [max_lon, min_lat]
                else:
                    # Fallback for geo_bounding_box (used for geo_point fields)
                    box = geo_filter["geo_bounding_box"]["dcat_bbox"]
                    assert box["top_left"] == {"lat": 45.0, "lon": -109.0}
                    assert box["bottom_right"] == {"lat": 41.0, "lon": -104.0}

                # BBox searches now apply an overlap-ratio hard filter by default.
                script_filter = next((f for f in filters if "script" in f), None)
                assert script_filter is not None
                params = script_filter["script"]["script"]["params"]
                assert params["minOverlapRatio"] == MIN_BBOX_IOU_OVERLAP_RATIO

                script_score = search_query["script_score"]["script"]
                assert "containmentRatio" in script_score["source"]
                assert "spatialScore" in script_score["source"]
                assert script_score["params"]["spatialBoostWeight"] == pytest.approx(
                    BBOX_SPATIAL_BOOST_WEIGHT
                )

    @pytest.mark.asyncio
    async def test_search_resources_with_geospatial_bbox_relation(self):
        """BBox include filter should honor relation parameter."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    fq=None,
                    skip=0,
                    limit=5,
                    sort=None,
                    include_filters={
                        "geo": {
                            "type": "bbox",
                            "field": "dcat_bbox",
                            "relation": "within",
                            "top_left": {"lat": 45.0, "lon": -109.0},
                            "bottom_right": {"lat": 41.0, "lon": -104.0},
                        }
                    },
                )

                search_query = mock_es.search.call_args.kwargs["query"]
                bool_query = search_query["script_score"]["query"]["bool"]
                filters = bool_query["filter"]
                geo_filter = next((f for f in filters if "geo_shape" in f), None)
                assert geo_filter is not None
                assert geo_filter["geo_shape"]["dcat_bbox"]["relation"] == "within"

    @pytest.mark.asyncio
    async def test_search_resources_with_invalid_bbox_relation_falls_back_to_intersects(self):
        """Invalid bbox relation should default to intersects."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    fq=None,
                    skip=0,
                    limit=5,
                    sort=None,
                    include_filters={
                        "geo": {
                            "type": "bbox",
                            "field": "dcat_bbox",
                            "relation": "invalid-relation",
                            "top_left": {"lat": 45.0, "lon": -109.0},
                            "bottom_right": {"lat": 41.0, "lon": -104.0},
                        }
                    },
                )

                search_query = mock_es.search.call_args.kwargs["query"]
                bool_query = search_query["script_score"]["query"]["bool"]
                filters = bool_query["filter"]
                geo_filter = next((f for f in filters if "geo_shape" in f), None)
                assert geo_filter is not None
                assert geo_filter["geo_shape"]["dcat_bbox"]["relation"] == "intersects"

    @pytest.mark.asyncio
    async def test_search_resources_with_geospatial_distance_filter(self):
        """Ensure distance include filter generates geo_distance."""

        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query=None,
                    fq=None,
                    skip=0,
                    limit=5,
                    sort=None,
                    include_filters={
                        "geo": {
                            "type": "distance",
                            "field": "dcat_centroid",
                            "center": {"lat": 43.5, "lon": -106.2},
                            "distance": "25km",
                        }
                    },
                )

                search_query = mock_es.search.call_args.kwargs["query"]
                filters = search_query["bool"]["filter"]
                geo_filter = next((f for f in filters if "geo_distance" in f), None)
                assert geo_filter is not None
                distance = geo_filter["geo_distance"]
                assert distance["distance"] == "25km"
                assert distance["dcat_centroid"] == {
                    "lat": 43.5,
                    "lon": -106.2,
                }

    @pytest.mark.asyncio
    async def test_search_resources_geo_filter_reduces_results_and_matches_pg(self, monkeypatch):
        """Geo filter should reduce results and align with PostGIS row count."""

        monkeypatch.setenv("APPLICATION_URL", "http://localhost:8000")

        baseline_response = MagicMock()
        baseline_response.body = {
            "hits": {
                "total": {"value": 5, "relation": "eq"},
                "hits": [
                    {
                        "_index": "btaa_ogm_api",
                        "_id": "baseline-1",
                        "_score": 1.0,
                        "_source": {"id": "baseline-1"},
                    },
                    {
                        "_index": "btaa_ogm_api",
                        "_id": "baseline-2",
                        "_score": 0.9,
                        "_source": {"id": "baseline-2"},
                    },
                ],
            },
            "took": 7,
            "aggregations": {},
        }

        geo_response = MagicMock()
        geo_response.body = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [
                    {
                        "_index": "btaa_ogm_api",
                        "_id": "geo-1",
                        "_score": 1.0,
                        "_source": {"id": "geo-1"},
                    }
                ],
            },
            "took": 5,
            "aggregations": {},
        }

        async def search_side_effect(*, query=None, **kwargs):
            filters = query.get("bool", {}).get("filter", []) if query else []
            if any("geo_shape" in clause for clause in filters):
                return geo_response
            return baseline_response

        mock_es = AsyncMock()
        mock_es.search.side_effect = search_side_effect

        baseline_rows = [
            {"id": "baseline-1", "dct_title_s": "Baseline 1"},
            {"id": "baseline-2", "dct_title_s": "Baseline 2"},
        ]
        geo_rows = [
            {"id": "geo-1", "dct_title_s": "Geo 1"},
        ]

        fetch_all_mock = AsyncMock(side_effect=[baseline_rows, geo_rows])

        with (
            patch("app.elasticsearch.search.database.fetch_all", fetch_all_mock),
            patch("app.elasticsearch.search.es", mock_es),
            patch("app.elasticsearch.search.create_viewer_attributes", return_value={}),
        ):
            baseline = await search_resources(
                query=None,
                fq=None,
                skip=0,
                limit=10,
                sort=None,
                include_filters={"gbl_resourceClass_sm": ["Maps"]},
            )

            geo = await search_resources(
                query=None,
                fq=None,
                skip=0,
                limit=10,
                sort=None,
                include_filters={
                    "gbl_resourceClass_sm": ["Maps"],
                    "geo": {
                        "type": "polygon",
                        "field": "locn_geometry",
                        "relation": "intersects",
                        "points": [
                            {"lat": 45.0, "lon": -104.0},
                            {"lat": 45.0, "lon": -109.0},
                            {"lat": 41.0, "lon": -109.0},
                            {"lat": 41.0, "lon": -104.0},
                        ],
                    },
                },
            )

        baseline_total = baseline["meta"]["pages"]["total_count"]
        geo_total = geo["meta"]["pages"]["total_count"]
        assert geo_total < baseline_total

        pg_row_count = len(geo["data"])
        assert geo_total == pg_row_count

    @pytest.mark.asyncio
    async def test_search_resources_error_handling(self):
        """Test search_resources error handling."""
        # Mock the Elasticsearch client to raise an exception
        mock_es = AsyncMock()
        mock_es.search.side_effect = Exception("Elasticsearch connection error")

        # Mock the es client
        with patch("app.elasticsearch.search.es", mock_es):
            # Call search_resources and expect an exception
            with pytest.raises(Exception) as exc_info:
                await search_resources(query="test", fq=None, skip=0, limit=10, sort=None)

            assert "Elasticsearch connection error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_resources_with_suggestions(self):
        """Test search_resources includes suggestions when query is provided."""
        # Mock the Elasticsearch client
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
            "suggest": {
                "simple_phrase": [
                    {
                        "text": "test",
                        "offset": 0,
                        "length": 4,
                        "options": [{"text": "testing", "score": 0.8}],
                    }
                ]
            },
        }
        mock_es.search.return_value = mock_response

        # Mock the database fetch_all
        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            # Mock the es client
            with patch("app.elasticsearch.search.es", mock_es):
                # Call search_resources with a query
                await search_resources(query="test", fq=None, skip=0, limit=10, sort=None)

                # Verify that es.search was called with suggest parameter
                mock_es.search.assert_called_once()
                call_args = mock_es.search.call_args

                # Verify suggest was included in the call
                assert "suggest" in call_args.kwargs
                suggest = call_args.kwargs["suggest"]
                assert "text" in suggest
                assert "simple_phrase" in suggest

    @pytest.mark.asyncio
    async def test_search_resources_with_or_operator(self):
        """Test that OR operator is properly passed to query_string."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                # Test OR query
                await search_resources(
                    query="Lake Superior OR Lake Erie", fq=None, skip=0, limit=10, sort=None
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the OR operator
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == "Lake Superior OR Lake Erie"

    @pytest.mark.asyncio
    async def test_search_resources_with_not_operator(self):
        """Test that NOT operator is properly passed to query_string."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                # Test NOT query
                await search_resources(
                    query="Lake Superior NOT Michigan", fq=None, skip=0, limit=10, sort=None
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the NOT operator
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == "Lake Superior NOT Michigan"

    @pytest.mark.asyncio
    async def test_search_resources_with_grouping(self):
        """Test that parentheses grouping is properly passed to query_string."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                # Test grouped query
                await search_resources(
                    query="(Lake Superior OR Lake Erie) AND Map",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None,
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the grouped query
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == "(Lake Superior OR Lake Erie) AND Map"

    @pytest.mark.asyncio
    async def test_search_resources_with_phrase_query(self):
        """Test that phrase queries with quotes are properly passed to query_string."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                # Test phrase query
                await search_resources(
                    query='"Lake Superior"', fq=None, skip=0, limit=10, sort=None
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                # Verify query_string receives the phrase query with quotes
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == '"Lake Superior"'

    @pytest.mark.asyncio
    async def test_search_resources_escapes_square_brackets_for_query_string(self):
        """Bracketed text should be treated as literal, not query syntax."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query="Michigan Aquaculture Testing Veterinarians [Michigan]",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None,
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == (
                    r"Michigan Aquaculture Testing Veterinarians \[Michigan\]"
                )

    @pytest.mark.asyncio
    async def test_search_resources_escapes_curly_braces_for_query_string(self):
        """Curly-braced text should be treated as literal, not query syntax."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query="Precipitation (08) [Minnesota] {1991-2020 August}",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None,
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == (
                    r"Precipitation (08) \[Minnesota\] \{1991-2020 August\}"
                )

    @pytest.mark.asyncio
    async def test_search_resources_escapes_colon_for_identifier_query_string(self):
        """Identifier-style queries with colons should be treated literally."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(
                    query="p16022coll244:471",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=None,
                )

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")
                query_string_clause = search_query["bool"]["must"][0]["query_string"]
                assert query_string_clause["query"] == r"p16022coll244\:471"

    @pytest.mark.asyncio
    async def test_query_string_has_correct_parameters(self):
        """Test that query_string has the correct configuration parameters."""
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 0}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                await search_resources(query="test query", fq=None, skip=0, limit=10, sort=None)

                call_args = mock_es.search.call_args
                search_query = call_args.kwargs.get("query")

                query_string_clause = search_query["bool"]["must"][0]["query_string"]

                # Verify configuration
                assert query_string_clause["default_operator"] == "AND"
                assert query_string_clause["analyze_wildcard"] is True
                assert query_string_clause["allow_leading_wildcard"] is True

    @pytest.mark.asyncio
    async def test_year_sort_uses_correct_field_name(self):
        """Test that year sorting uses the correct field name gbl_indexYear_im (with capital Y).

        This test prevents regression where the field name was incorrectly set to
        gbl_indexyear_im (lowercase), which would cause 0 results when sorting by year.
        """
        from app.api.v1.shared import SORT_MAPPINGS, SortOption

        # Verify the sort mappings use the correct field name
        year_desc_sort = SORT_MAPPINGS[SortOption.YEAR_NEWEST]
        year_asc_sort = SORT_MAPPINGS[SortOption.YEAR_OLDEST]

        # Check that both use gbl_indexYear_im (with capital Y)
        assert year_desc_sort[0] == {"gbl_indexYear_im": "desc"}
        assert year_asc_sort[0] == {"gbl_indexYear_im": "asc"}

        # Verify the field name is NOT the incorrect lowercase version
        assert "gbl_indexyear_im" not in str(year_desc_sort)
        assert "gbl_indexyear_im" not in str(year_asc_sort)

        # Mock Elasticsearch to verify the sort is passed correctly
        mock_es = AsyncMock()
        mock_response = MagicMock()
        mock_response.body = {
            "hits": {"total": {"value": 2}, "hits": []},
            "took": 1,
            "aggregations": {},
        }
        mock_es.search.return_value = mock_response

        with patch("app.elasticsearch.search.database.fetch_all") as mock_fetch:
            mock_fetch.return_value = []

            with patch("app.elasticsearch.search.es", mock_es):
                # Test year_desc sort
                await search_resources(
                    query="test",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=year_desc_sort,
                )

                # Verify Elasticsearch was called with correct sort
                call_args = mock_es.search.call_args
                sort_param = call_args.kwargs.get("sort")

                # Verify the sort uses the correct field name
                assert sort_param is not None
                assert len(sort_param) >= 1
                assert sort_param[0] == {"gbl_indexYear_im": "desc"}
                assert "gbl_indexyear_im" not in str(sort_param)  # Should not use lowercase

                # Reset mock for next test
                mock_es.reset_mock()

                # Test year_asc sort
                await search_resources(
                    query="test",
                    fq=None,
                    skip=0,
                    limit=10,
                    sort=year_asc_sort,
                )

                # Verify Elasticsearch was called with correct sort
                call_args = mock_es.search.call_args
                sort_param = call_args.kwargs.get("sort")

                # Verify the sort uses the correct field name
                assert sort_param is not None
                assert len(sort_param) >= 1
                assert sort_param[0] == {"gbl_indexYear_im": "asc"}
                assert "gbl_indexyear_im" not in str(sort_param)  # Should not use lowercase
