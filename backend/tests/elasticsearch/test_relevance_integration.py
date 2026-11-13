"""Real Elasticsearch contract tests; never use the application's configured index."""

import copy
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from app.elasticsearch import relevance, search
from app.elasticsearch.collection_context import advance_search_revision
from app.elasticsearch.index import _update_bbox_metrics
from app.elasticsearch.mappings import INDEX_MAPPING

FIXTURES = Path(__file__).parents[1] / "fixtures"
STREETCARS = json.loads((FIXTURES / "search_relevance.json").read_text())
COAL = json.loads((FIXTURES / "collection_search_483.json").read_text())
A = "Maps of Minneapolis that show streetcar routes"
B = "Maps Minneapolis streetcar"
C = "Minneapolis streetcar"
COLLECTION_TITLE = COAL["documents"][0]["dct_title_s"]
pytestmark = pytest.mark.elasticsearch


@pytest_asyncio.fixture(loop_scope="function")
async def catalog(monkeypatch):
    relevance.clear_matching_cache()
    url = os.getenv("SEARCH_RELEVANCE_TEST_URL")
    if not url:
        pytest.skip("Set SEARCH_RELEVANCE_TEST_URL to an isolated Elasticsearch 9 service")
    client = AsyncElasticsearch(url)
    index = f"test-search-relevance-{uuid4().hex}"
    monkeypatch.setenv("SEARCH_RELEVANCE_VERSION", "v2")
    monkeypatch.setenv("ELASTICSEARCH_INDEX", index)
    monkeypatch.setattr(search, "es", client)
    from app.services import cache_service

    monkeypatch.setattr(cache_service, "ENDPOINT_CACHE", False)
    mapping = copy.deepcopy(INDEX_MAPPING)
    await client.indices.create(index=index, **mapping)
    try:
        docs = copy.deepcopy(STREETCARS["documents"] + COAL["documents"])
        # All synthetic examples below are distractors or explicitly labeled boundary cases.
        docs += [
            {"id": "synthetic-unrelated", "dct_title_s": "Minneapolis park maps"},
            {"id": "synthetic-other-city", "dct_title_s": "Chicago streetcar route maps"},
            {"id": "synthetic-class-only", "dct_title_s": "Minneapolis streetcar system"},
            {"id": "synthetic-coal", "dct_title_s": "Coal production in Ohio"},
            {"id": "synthetic-hidden", "dct_title_s": C, "gbl_suppressed_b": True},
            {"id": "synthetic-draft", "dct_title_s": C, "publication_state": "draft"},
            {"id": "synthetic-accent", "dct_title_s": "Québec Saint-Paul Hudson's mines"},
        ]
        for doc in docs:
            doc.setdefault("publication_state", "published")
            doc.setdefault("gbl_suppressed_b", False)
            doc.setdefault("gbl_resourceClass_sm", ["Maps"])
            if "08d-03" in doc.get("dct_isPartOf_sm", []):
                doc["collection_titles"] = [COLLECTION_TITLE]
            bbox = doc.get("dcat_bbox")
            if bbox:
                west, south, east, north = map(float, bbox.split(","))
                doc["dcat_bbox"] = {
                    "type": "envelope",
                    "coordinates": [[west, north], [east, south]],
                }
                _update_bbox_metrics(doc, doc["dcat_bbox"])
                doc["dcat_centroid"] = [(west + east) / 2, (south + north) / 2]
            else:
                doc["dcat_centroid"] = [-93.26, 44.98]
            doc["h3_res5"] = "85275027fffffff"
            await client.index(index=index, id=doc["id"], document=doc)
        await client.indices.refresh(index=index)
        await advance_search_revision(client, index, ready=True)
        yield client, index
    finally:
        await client.indices.delete(index=index)
        await client.close()


async def run_query(query, *, skip=0, include_filters=None, **kwargs):
    params = search.SearchParams.from_inputs(
        query=query,
        fq=None,
        skip=skip,
        limit=100,
        sort=None,
        search_fields=None,
        include_filters=include_filters,
        exclude_filters=kwargs.get("exclude_filters"),
        facets=None,
        adv_q=kwargs.get("adv_q"),
        hydrate_hits=False,
    )
    await search.prepare_matching(params)
    plan = search.SearchQueryBuilder(
        params, params.criteria(), search.SearchFacetSelection({}, ())
    ).build()
    response = await search.es.search(
        index=params.index_name,
        query=plan.search_query["query"],
        size=params.limit,
        from_=skip,
        track_total_hits=True,
    )
    return params, response


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("query,mode", [(A, "partial_terms"), (B, "all_terms"), (C, "all_terms")])
async def test_streetcar_recall_and_ranking(catalog, query, mode):
    params, response = await run_query(query)
    ids = [hit["_id"] for hit in response["hits"]["hits"]]
    relevant = set(STREETCARS["relevant_ids"])
    assert relevant <= set(ids)
    assert {"msn-id-1896", "msn-id-1897"} <= set(ids[:5])
    assert len(relevant & set(ids[:10])) >= 8
    assert params.matching.mode == mode
    assert "synthetic-class-only" in ids
    assert "synthetic-hidden" not in ids and "synthetic-draft" not in ids


@pytest.mark.asyncio(loop_scope="function")
async def test_real_strict_natural_language_hit_prevents_fallback(catalog):
    client, index = catalog
    document = STREETCARS["full_catalog_strict_match"]
    await client.index(index=index, id=document["id"], document=document, refresh=True)
    await advance_search_revision(client, index, ready=True)
    params, response = await run_query(A)
    assert params.matching.mode == "all_terms"
    assert [hit["_id"] for hit in response["hits"]["hits"]] == [document["id"]]

    # A logical exclusion restores a genuine zero, enabling the partial stage.
    params, response = await run_query(A, exclude_filters={"id": [document["id"]]})
    assert params.matching.mode == "partial_terms"
    assert set(STREETCARS["relevant_ids"]) <= {hit["_id"] for hit in response["hits"]["hits"]}


@pytest.mark.asyncio(loop_scope="function")
async def test_analyzer_contract(catalog):
    client, index = catalog

    async def tokens(value):
        result = await client.indices.analyze(index=index, analyzer="catalog_english", text=value)
        return [token["token"] for token in result["tokens"]]

    for first, second in [("map", "maps"), ("mine", "mines"), ("route", "routes")]:
        assert await tokens(first) == await tokens(second)
    assert await tokens("of that the") == []
    assert "show" in await tokens(A)
    assert await tokens("Hudson's") == await tokens("Hudson")
    assert len(await tokens("Saint-Paul")) == 2
    assert (await tokens("Québec"))[0].startswith("qué")


@pytest.mark.asyncio(loop_scope="function")
async def test_collection_title_and_spatial_constraints(catalog):
    params, response = await run_query(COLLECTION_TITLE)
    ids = [hit["_id"] for hit in response["hits"]["hits"]]
    members = {d["id"] for d in COAL["documents"][1:]}
    assert ids[0] == "08d-03"
    assert members <= set(ids)
    assert params.matching.mode == "all_terms"
    for relation in ["within", "intersects"]:
        filters = {
            "geo": {
                "type": "bbox",
                "field": "dcat_bbox",
                "relation": relation,
                "top_left": {"lat": 40.34, "lon": -79.92},
                "bottom_right": {"lat": 40.24, "lon": -79.74},
            }
        }
        _, response = await run_query(COLLECTION_TITLE, include_filters=filters)
        ids = {hit["_id"] for hit in response["hits"]["hits"]}
        assert members <= ids
        if relation == "within":
            assert "08d-03" not in ids
        result = await search.search_resources(
            query=COLLECTION_TITLE,
            include_filters=filters,
            hydrate_hits=False,
            facets="gbl_resourceClass_sm",
        )
        for document in result["data"]:
            if document["id"] in members:
                assert document["bbox_overlap_ratio"] > 0
                assert document["bbox_containment_ratio"] > 0
        filters["geo"]["top_left"] = {"lat": 45, "lon": -94}
        filters["geo"]["bottom_right"] = {"lat": 44, "lon": -93}
        _, response = await run_query(COLLECTION_TITLE, include_filters=filters)
        assert not members & {hit["_id"] for hit in response["hits"]["hits"]}


@pytest.mark.asyncio(loop_scope="function")
async def test_aggregation_and_pagination_parity(catalog):
    _, result = await run_query(A)
    total = result["hits"]["total"]["value"]
    buckets = await search.get_facet_values("gbl_resourceClass_sm", query=A)
    assert buckets.matching.mode == "partial_terms"
    assert sum(bucket["doc_count"] for bucket in buckets) == total
    map_result = await search.map_h3_aggregation(q=A)
    assert map_result["matching"]["mode"] == "partial_terms"
    assert sum(count for _, count in map_result["hexes"]) == total
    # A rendering viewport cannot turn a successful strict query into partial matches.
    map_result = await search.map_h3_aggregation(q=C, bbox="0,0,1,1")
    assert map_result["matching"]["mode"] == "all_terms"
    assert map_result["hexes"] == []
    params, result = await run_query(C, skip=1000)
    assert params.matching.mode == "all_terms" and result["hits"]["hits"] == []


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize("query", ["of the that", "Minneapolis zzzunfindable", "zzzunfindable"])
async def test_no_match_all_or_single_term_relaxation(catalog, query):
    _, response = await run_query(query)
    assert response["hits"]["total"]["value"] == 0


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize(
    "query", ['"Minneapolis streetcar"', "Minneapolis AND streetcar", "msn-id-1896"]
)
async def test_literal_queries_keep_legacy_results(catalog, query):
    client, index = catalog
    params, response = await run_query(query)
    assert params.matching.mode == "literal"
    legacy = await client.search(
        index=index,
        query={
            "bool": {
                "must": [search._build_all_fields_query(query)],
                "filter": search.public_visibility_filter_clauses(),
            }
        },
        size=100,
    )
    assert {h["_id"] for h in response["hits"]["hits"]} == {
        h["_id"] for h in legacy["hits"]["hits"]
    }


@pytest.mark.asyncio(loop_scope="function")
async def test_fixture_benchmark_report(catalog, monkeypatch):
    """Optional diagnostic artifact, not a timing-sensitive pass/fail test."""
    import math
    import random
    from time import perf_counter

    report_path = os.getenv("SEARCH_RELEVANCE_BENCHMARK_REPORT")
    if not report_path:
        pytest.skip("Set SEARCH_RELEVANCE_BENCHMARK_REPORT for a fixture microbenchmark")
    client, index = catalog
    optimized_prepare = search.prepare_matching
    optimized_kwargs = search.SearchExecutor._primary_kwargs

    def original_kwargs(executor):
        kwargs = optimized_kwargs(executor)
        kwargs.pop("source_includes", None)
        return kwargs

    async def original_prepare(params, **_):
        """Frozen pre-optimization v2 path, for paired same-run measurements."""
        if relevance.relevance_version() != "v2":
            return
        mapping = await client.indices.get_mapping(index=params.index_name)
        name, entry = next(iter(mapping.items()))
        meta = entry["mappings"]["_meta"]
        assert meta["search_relevance_ready"]
        generation = f"{name}:{meta['search_revision']}"
        params.index_name = name
        params.matching = relevance.Matching("literal", generation)
        if not relevance.is_ordinary_query(params.query, params.search_fields, params.adv_q):
            return
        query = params.query.strip()
        literal = search._build_all_fields_query(query)
        params.text_clause = relevance.text_query(query, literal)
        strict = search.SearchQueryBuilder(
            params, params.criteria(), search.SearchFacetSelection({}, ())
        ).build()
        params.matching = await relevance.resolve_matching(
            client, name, {"bool": strict.bool_query}, generation=generation
        )
        if params.matching.mode == "partial_terms":
            params.text_clause = relevance.text_query(query, literal, partial=True)

    legacy_index = f"test-search-relevance-{uuid4().hex}"
    v2_index = f"test-search-relevance-{uuid4().hex}"
    legacy_mapping = copy.deepcopy(INDEX_MAPPING)
    legacy_mapping["mappings"].pop("_meta", None)
    for definition in legacy_mapping["mappings"]["properties"].values():
        definition.get("fields", {}).pop("search_en", None)
    legacy_mapping["mappings"]["properties"].pop("collection_titles", None)
    records = await client.search(index=index, size=100, query={"match_all": {}})
    documents = [hit["_source"] for hit in records["hits"]["hits"]]
    copies = int(os.getenv("SEARCH_RELEVANCE_BENCHMARK_COPIES", "1"))
    if not 1 <= copies <= 1000:
        raise ValueError("SEARCH_RELEVANCE_BENCHMARK_COPIES must be between 1 and 1000")
    if copies > 1:
        documents = [
            {**document, "id": f"synthetic-benchmark-{copy_number}-{document['id']}"}
            for copy_number in range(copies)
            for document in documents
        ]
    await client.indices.create(index=legacy_index, **legacy_mapping)
    await client.indices.create(index=v2_index, **copy.deepcopy(INDEX_MAPPING))
    try:
        start = perf_counter()
        await async_bulk(
            client,
            (
                {
                    "_index": legacy_index,
                    "_id": doc["id"],
                    "_source": {k: v for k, v in doc.items() if k != "collection_titles"},
                }
                for doc in documents
            ),
            chunk_size=500,
        )
        await client.indices.refresh(index=legacy_index)
        legacy_ingest_ms = (perf_counter() - start) * 1000
        start = perf_counter()
        await async_bulk(
            client,
            ({"_index": v2_index, "_id": doc["id"], "_source": doc} for doc in documents),
            chunk_size=500,
        )
        await client.indices.refresh(index=v2_index)
        v2_ingest_ms = (perf_counter() - start) * 1000
        await advance_search_revision(client, v2_index, ready=True)
        # Warm both implementations, interleave queries with a reproducible shuffle,
        # and retain per-query transport costs instead of only an aggregate p95.
        samples = {"legacy": [], "original_v2": [], "v2": []}
        measurements = []
        calls = []
        perform_request = client.transport.perform_request

        async def traced_request(method, target, **kwargs):
            started = perf_counter()
            response = await perform_request(method, target, **kwargs)
            body = kwargs.get("body")
            probe = isinstance(body, dict) and body.get("terminate_after") == 1
            calls.append(
                {
                    "operation": "mapping"
                    if "_mapping" in target
                    else "probe"
                    if probe
                    else "search",
                    "ms": (perf_counter() - started) * 1000,
                    "es_took_ms": response.body.get("took")
                    if isinstance(response.body, dict)
                    else None,
                }
            )
            return response

        monkeypatch.setattr(client.transport, "perform_request", traced_request)
        iterations = int(os.getenv("SEARCH_RELEVANCE_BENCHMARK_ITERATIONS", "100"))
        workload = os.getenv("SEARCH_RELEVANCE_BENCHMARK_WORKLOAD", "query")
        stage_cache = os.getenv("SEARCH_RELEVANCE_BENCHMARK_STAGE_CACHE", "cold")
        if workload not in {"query", "results"} or stage_cache not in {"cold", "warm"}:
            raise ValueError("Benchmark workload must be query/results and stage cache cold/warm")
        signatures = {}
        rng = random.Random(483)
        for iteration in range(iterations + 10):
            jobs = [
                (mode, target, query)
                for mode, target in [
                    ("legacy", legacy_index),
                    ("original_v2", v2_index),
                    ("v2", v2_index),
                ]
                for query in [A, B, C, COLLECTION_TITLE]
            ]
            rng.shuffle(jobs)
            for mode, target, query in jobs:
                monkeypatch.setenv(
                    "SEARCH_RELEVANCE_VERSION", "legacy" if mode == "legacy" else "v2"
                )
                monkeypatch.setenv("ELASTICSEARCH_INDEX", target)
                monkeypatch.setattr(
                    search,
                    "prepare_matching",
                    original_prepare if mode == "original_v2" else optimized_prepare,
                )
                monkeypatch.setattr(
                    search.SearchExecutor,
                    "_primary_kwargs",
                    original_kwargs if mode == "original_v2" else optimized_kwargs,
                )
                calls.clear()
                if stage_cache == "cold":
                    relevance.clear_matching_cache()
                start = perf_counter()
                if workload == "results":
                    result = await search.search_resources(
                        query=query, hydrate_hits=False, limit=20, facets="gbl_resourceClass_sm"
                    )
                else:
                    await run_query(query)
                elapsed = (perf_counter() - start) * 1000
                if workload == "results":
                    signatures[(mode, query)] = (
                        result["meta"].get("matching"),
                        result["meta"]["pages"]["total_count"],
                        [doc["id"] for doc in result["data"]],
                    )
                if iteration >= 10:
                    samples[mode].append(elapsed)
                    measurements.append(
                        {"mode": mode, "query": query, "ms": elapsed, "calls": list(calls)}
                    )
        if workload == "results":
            for query in [A, B, C, COLLECTION_TITLE]:
                assert signatures[("v2", query)] == signatures[("original_v2", query)]
        p95 = {
            mode: sorted(values)[math.ceil(len(values) * 0.95) - 1]
            for mode, values in samples.items()
        }
        size = {}
        for mode, target in [("legacy", legacy_index), ("v2", v2_index)]:
            stats = await client.indices.stats(index=target, metric="store")
            size[mode] = stats["_all"]["primaries"]["store"]["size_in_bytes"]
        Path(report_path).write_text(
            json.dumps(
                {
                    "scope": "fixture microbenchmark; not a full-catalog activation benchmark",
                    "workload": workload,
                    "stage_cache": stage_cache,
                    "baseline": (
                        "original_v2 reproduces the pre-optimization mapping/probe/result "
                        "path on the same v2 index; both modes use the same stage-cache "
                        "implementation, so warm comparisons exclude Redis/L1 savings"
                    ),
                    "documents": len(documents),
                    "fixture_copies": copies,
                    "indexing_method": "bulk batches of 500 preprepared documents",
                    "requests_per_mode": len(samples["v2"]),
                    "uncached_query_p95_ms": p95,
                    "index_bytes": size,
                    "ingest_ms": {"legacy_insert": legacy_ingest_ms, "v2_insert": v2_ingest_ms},
                    "p95_regression_over_20_percent": p95["v2"] > 1.2 * p95["legacy"],
                    "warmup_queries_per_mode": 40,
                    "measurements": measurements,
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        await client.indices.delete(index=legacy_index)
        await client.indices.delete(index=v2_index)


@pytest.mark.asyncio(loop_scope="function")
async def test_full_search_response_matching_and_filters(catalog):
    result = await search.search_resources(
        query=A, hydrate_hits=False, limit=100, facets="gbl_resourceClass_sm"
    )
    assert result["meta"]["matching"]["mode"] == "partial_terms"
    assert set(STREETCARS["relevant_ids"]) <= {doc["id"] for doc in result["data"]}
    collection = await search.search_resources(
        query=COLLECTION_TITLE,
        hydrate_hits=False,
        limit=100,
        facets="gbl_resourceClass_sm",
        sort=[{"dct_title_s.keyword": "asc"}],
        exclude_filters={"gbl_resourceClass_sm": ["Collections"]},
    )
    assert "08d-03" not in {doc["id"] for doc in collection["data"]}
    assert collection["meta"]["matching"]["mode"] == "all_terms"
    assert {doc["id"] for doc in collection["data"]} == {d["id"] for d in COAL["documents"][1:]}


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.parametrize(
    "query,skip,searches,mode",
    [
        (C, 0, 1, "all_terms"),
        (C, 1000, 1, "all_terms"),
        (A, 0, 2, "partial_terms"),
        ("Minneapolis streetcar zzz", 0, 2, "partial_terms"),
    ],
)
async def test_cold_results_reuse_strict_totals(catalog, monkeypatch, query, skip, searches, mode):
    client, _ = catalog
    relevance.clear_matching_cache()
    original_search = client.search

    async def run(**kwargs):
        return await original_search(**kwargs)

    spy = AsyncMock(side_effect=run)
    monkeypatch.setattr(client, "search", spy)
    result = await search.search_resources(
        query=query, skip=skip, hydrate_hits=False, facets="gbl_resourceClass_sm"
    )
    assert result["meta"]["matching"]["mode"] == mode
    assert spy.await_count == searches
    if searches == 2:
        if query == A:
            assert spy.call_args_list[0].kwargs["terminate_after"] == 1
            assert spy.call_args_list[1].kwargs["suggest"]
        else:
            assert spy.call_args_list[0].kwargs["suggest"]
            assert spy.call_args_list[1].kwargs["suggest"] is None


@pytest.mark.asyncio(loop_scope="function")
async def test_result_stage_is_reused_by_facets_and_maps_and_invalidated(catalog, monkeypatch):
    client, index = catalog
    original_search = client.search

    async def run(**kwargs):
        return await original_search(**kwargs)

    spy = AsyncMock(side_effect=run)
    monkeypatch.setattr(client, "search", spy)
    result = await search.search_resources(
        query=A, hydrate_hits=False, facets="gbl_resourceClass_sm"
    )
    assert result["meta"]["matching"]["mode"] == "partial_terms"
    assert spy.await_count == 2
    assert (
        await search.get_facet_values("gbl_resourceClass_sm", query=A)
    ).matching.mode == "partial_terms"
    assert (await search.map_h3_aggregation(q=A))["matching"]["mode"] == "partial_terms"
    assert spy.await_count == 4  # no additional probes for either aggregation
    await client.index(
        index=index,
        id="new-strict",
        document={
            "id": "new-strict",
            "dct_title_s": "Maps Minneapolis show streetcar routes",
            "publication_state": "published",
            "gbl_suppressed_b": False,
        },
        refresh=True,
    )
    await advance_search_revision(client, index)
    result = await search.search_resources(
        query=A, hydrate_hits=False, facets="gbl_resourceClass_sm"
    )
    assert result["meta"]["matching"]["mode"] == "all_terms"
    assert [doc["id"] for doc in result["data"]] == ["new-strict"]
    assert spy.await_count == 6  # a new generation requires another probe for long queries


@pytest.mark.asyncio(loop_scope="function")
async def test_incomplete_strict_results_never_trigger_partial_retrieval(catalog, monkeypatch):
    from fastapi import HTTPException

    client, _ = catalog
    spy = AsyncMock(return_value={"timed_out": True, "hits": {"total": {"value": 0}, "hits": []}})
    monkeypatch.setattr(client, "search", spy)
    with pytest.raises(HTTPException):
        await search.search_resources(query=A, hydrate_hits=False)
    assert spy.await_count == 1
    assert not relevance._matching_cache
