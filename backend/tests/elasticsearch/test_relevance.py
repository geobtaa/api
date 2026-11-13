import copy
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.elasticsearch import collection_context, relevance
from app.elasticsearch.mappings import INDEX_MAPPING
from app.elasticsearch.search import _build_all_fields_query


@pytest.fixture(autouse=True)
def clear_process_cache():
    relevance.clear_matching_cache()
    yield
    relevance.clear_matching_cache()


@pytest.mark.asyncio
async def test_incremental_revision_failure_is_an_indexing_failure(monkeypatch):
    from app.elasticsearch import index

    client = MagicMock()
    client.index = AsyncMock(return_value={"result": "updated"})
    client.indices.refresh = AsyncMock()
    monkeypatch.setattr(index, "es", client)
    monkeypatch.setattr(index, "_get_failure_logger", MagicMock())
    monkeypatch.setattr(
        index, "advance_search_revision", AsyncMock(side_effect=RuntimeError("revision failed"))
    )
    result = await index.perform_individual_indexing([{"id": "member"}], "test-index")
    assert result["errors"] == 1


@pytest.mark.asyncio
async def test_full_index_cannot_be_ready_when_preparation_skips_rows(monkeypatch):
    from app.elasticsearch import client, index

    es = MagicMock()
    es.indices.exists = AsyncMock(return_value=False)
    monkeypatch.setattr(index, "es", es)
    monkeypatch.setattr(client, "init_elasticsearch", AsyncMock())
    monkeypatch.setattr(index.database, "fetch_all", AsyncMock(side_effect=[[{"id": "bad"}], []]))
    monkeypatch.setattr(index, "prepare_bulk_data", AsyncMock(return_value=[]))
    revision = AsyncMock()
    monkeypatch.setattr(index, "advance_search_revision", revision)
    result = await index.reindex_resources()
    assert result["errors"] == 1
    assert result["attempted"] == 1
    revision.assert_not_awaited()


@pytest.mark.parametrize(
    "query",
    [
        '"Minneapolis streetcar"',
        'maps "streetcar routes"',
        "maps AND streetcar",
        "maps OR streetcar",
        "maps NOT streetcar",
        "streetcar*",
        "map~2",
        "(map streetcar)",
        "+maps streetcar",
        "maps -roads",
        "p16022coll245:2",
        "2026-11-13",
        "08d-03",
        "msn-id-1896",
        "https://example.org/maps",
        "",
        "64bd8c4c-8e60-4956-b43d-bdc3f93db488",
    ],
)
def test_explicit_searches_are_literal(query):
    assert not relevance.is_ordinary_query(query)


@pytest.mark.parametrize(
    "query",
    [
        "Maps of Minneapolis that show streetcar routes",
        "Minneapolis streetcar",
        "Saint-Paul maps",
        "Hudson's map",
        "Québec maps",
        "maps of Saint-Paul",
    ],
)
def test_ordinary_searches(query):
    assert relevance.is_ordinary_query(query)
    assert not relevance.is_ordinary_query(query, search_fields="dct_title_s")
    assert not relevance.is_ordinary_query(query, adv_q=[{"op": "AND", "q": "maps"}])


def test_literal_boost_cannot_admit_candidates():
    clause = relevance.text_query("maps Minneapolis streetcar", _build_all_fields_query("maps"))
    assert clause["bool"]["must"][0]["combined_fields"]["operator"] == "and"
    assert len(clause["bool"]["should"]) == 3


@pytest.fixture
def stage_cache(monkeypatch):
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.generate_cache_key = relevance.CacheService.generate_cache_key
    monkeypatch.setattr(relevance, "CacheService", lambda: cache)
    monkeypatch.setenv("SEARCH_RELEVANCE_VERSION", "v2")
    return cache


@pytest.mark.asyncio
async def test_probe_uses_total_not_page_and_cache_separates_generations(stage_cache):
    es = AsyncMock()
    es.search.return_value = {"hits": {"total": {"value": 1}, "hits": []}}
    strict = {"bool": {"filter": [{"term": {"publication_state": "published"}}]}}
    result = await relevance.resolve_matching(es, "index", strict, generation="index:one")
    assert result.mode == "all_terms"
    assert es.search.call_args.kwargs["query"] == strict
    first_key = stage_cache.get.call_args.args[0]
    await relevance.resolve_matching(es, "index", strict, generation="index:two")
    assert stage_cache.get.call_args.args[0] != first_key
    assert stage_cache.set.call_args.kwargs["ttl"] == 60


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {"timed_out": True, "hits": {"total": {"value": 0}}},
        {"_shards": {"failed": 1}, "hits": {"total": {"value": 0}}},
    ],
)
async def test_incomplete_probe_never_broadens(body, stage_cache):
    es = AsyncMock()
    es.search.return_value = body
    with pytest.raises(HTTPException):
        await relevance.resolve_matching(es, "index", {}, generation="index:one")
    stage_cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_zero_probe_and_cache_hit(stage_cache):
    es = AsyncMock()
    es.search.return_value = {"hits": {"total": {"value": 0}}}
    result = await relevance.resolve_matching(es, "index", {}, generation="index:one")
    assert result.metadata() == {"mode": "partial_terms", "broadened": True, "version": "v2"}
    stage_cache.get.return_value = "partial_terms"
    relevance.clear_matching_cache()
    es.search.reset_mock()
    assert await relevance.resolve_matching(es, "index", {}, generation="index:one") == result
    es.search.assert_not_called()


@pytest.mark.asyncio
async def test_unbuilt_index_rejected():
    es = AsyncMock()
    mapping = copy.deepcopy(INDEX_MAPPING["mappings"])
    es.indices.get_mapping.return_value = {"index": {"mappings": mapping}}
    with pytest.raises(HTTPException, match="completed catalog reindex"):
        await relevance.index_generation(es, "alias")
    mapping["_meta"]["search_relevance_ready"] = True
    assert await relevance.index_generation(es, "alias") == "index:initial"
    del mapping["properties"]["collection_titles"]["fields"]["search_en"]
    with pytest.raises(HTTPException):
        await relevance.index_generation(es, "alias")


@pytest.mark.asyncio
async def test_generation_is_reused_only_within_request():
    mapping = copy.deepcopy(INDEX_MAPPING["mappings"])
    mapping["_meta"].update(search_relevance_ready=True, search_revision="one")
    es = AsyncMock()
    es.indices.get_mapping.return_value = {"index": {"mappings": mapping}}

    @relevance.generation_scope
    async def request():
        first = await relevance.index_generation(es, "alias")
        assert await relevance.index_generation(es, "index") == first
        assert await relevance.index_generation(es, "alias") == first
        return first

    assert await request() == "index:one"
    es.indices.get_mapping.assert_awaited_once()
    mapping["_meta"]["search_revision"] = "two"
    assert await request() == "index:two"
    assert es.indices.get_mapping.await_count == 2


@pytest.mark.asyncio
async def test_failed_scope_does_not_leak_generation():
    @relevance.generation_scope
    async def request():
        relevance._request_generations.get()["sentinel"] = "stale"
        raise RuntimeError("failed request")

    with pytest.raises(RuntimeError):
        await request()
    assert relevance._request_generations.get() is None


@pytest.mark.asyncio
async def test_local_stage_cache_is_bounded_expires_and_respects_revisions(
    stage_cache, monkeypatch
):
    now = [100.0]
    monkeypatch.setattr(relevance.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(relevance, "MATCHING_CACHE_SIZE", 2)
    strict = {"match_all": {}}
    await relevance.store_matching(strict, relevance.Matching("all_terms", "index:one"))
    stage_cache.get.reset_mock()
    assert (await relevance.cached_matching(strict, "index:one")).mode == "all_terms"
    stage_cache.get.assert_not_called()
    assert await relevance.cached_matching(strict, "index:two") is None
    now[0] += 61
    assert await relevance.cached_matching(strict, "index:one") is None
    for revision in ["a", "b", "c"]:
        await relevance.store_matching(strict, relevance.Matching("partial_terms", revision))
    assert len(relevance._matching_cache) == 2
    assert await relevance.cached_matching(strict, "a") is None


@pytest.mark.asyncio
async def test_collection_context_visibility_and_deduplication(monkeypatch):
    parent = {
        "id": "parent",
        "dct_title_s": "Coal maps",
        "publication_state": "published",
        "gbl_resourceClass_sm": ["Collections"],
        "gbl_suppressed_b": False,
    }
    database = MagicMock()
    database.fetch_all = AsyncMock(
        return_value=[
            parent,
            {**parent, "id": "duplicate"},
            {**parent, "id": "hidden", "gbl_suppressed_b": True},
            {**parent, "id": "draft", "publication_state": "draft"},
            {**parent, "id": "noncollection", "gbl_resourceClass_sm": ["Maps"]},
        ]
    )
    monkeypatch.setattr(collection_context, "database", database)
    row = {
        "id": "child",
        "pcdm_memberOf_sm": ["parent", "duplicate", "child", "missing"],
        "dct_isPartOf_sm": ["parent", "hidden", "draft", "noncollection"],
    }
    assert await collection_context.collection_titles_for_rows([row]) == {"child": ["Coal maps"]}
    database.fetch_all.assert_awaited_once()
    parent["dct_title_s"] = "Renamed maps"
    assert (await collection_context.collection_titles_for_rows([row]))["child"] == [
        "Coal maps",
        "Renamed maps",
    ]
    database.fetch_all.return_value = []
    assert await collection_context.collection_titles_for_rows([row]) == {"child": []}
    database.fetch_all.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError):
        await collection_context.collection_titles_for_rows([row])


@pytest.mark.asyncio
async def test_context_batch_bounds_and_removed_membership(monkeypatch):
    fetch = AsyncMock(return_value=[])
    monkeypatch.setattr(collection_context.database, "fetch_all", fetch)
    rows = [{"id": str(i), "pcdm_memberOf_sm": [f"p{i}"]} for i in range(2001)]
    assert len(await collection_context.collection_titles_for_rows(rows)) == 2001
    assert fetch.await_count == 3
    fetch.reset_mock()
    assert await collection_context.collection_titles_for_rows([{"id": "removed"}]) == {
        "removed": []
    }
    fetch.assert_not_called()
