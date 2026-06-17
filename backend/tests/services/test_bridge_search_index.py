from unittest.mock import AsyncMock

import pytest

import app.services.bridge_sync.search_index as search_index


class FakeDatabase:
    def __init__(self, rows):
        self.is_connected = True
        self.rows = rows
        self.fetch_calls = 0

    async def connect(self):
        self.is_connected = True

    async def fetch_all(self, _query):
        self.fetch_calls += 1
        return self.rows


class FakeIndices:
    def __init__(self):
        self.refreshed = []

    async def refresh(self, *, index):
        self.refreshed.append(index)


class FakeElasticsearch:
    def __init__(self):
        self.indexed = []
        self.deleted = []
        self.indices = FakeIndices()
        self.options_kwargs = {}

    def options(self, **kwargs):
        self.options_kwargs = kwargs
        return self

    async def index(self, *, index, id, document):
        self.indexed.append({"index": index, "id": id, "document": document})

    async def delete(self, *, index, id):
        self.deleted.append({"index": index, "id": id, "options": self.options_kwargs})


@pytest.mark.asyncio
async def test_index_changed_resources_indexes_every_changed_id_even_if_legacy_limit_is_set(
    monkeypatch,
):
    rows = [{"id": f"resource-{i}", "dct_title_s": f"Resource {i}"} for i in range(3)]
    fake_database = FakeDatabase(rows)
    fake_es = FakeElasticsearch()

    async def fake_process_resource(row):
        return {"id": row["id"], "title": row["dct_title_s"]}

    monkeypatch.setenv("BRIDGE_SEARCH_INDEX_REFRESH_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_SEARCH_INDEX_MAX_RESOURCE_IDS", "1")
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
    monkeypatch.setattr(search_index, "database", fake_database)
    monkeypatch.setattr(search_index, "es", fake_es)
    monkeypatch.setattr(search_index, "process_resource", fake_process_resource)

    stats = await search_index.index_changed_resources(
        ["resource-0", "resource-1", "resource-0", "", "resource-2"]
    )

    assert stats == {
        "enabled": True,
        "resource_ids": 3,
        "batch_size": 1,
        "batches": 3,
        "indexed": 3,
        "missing": 0,
        "errors": 0,
    }
    assert [entry["id"] for entry in fake_es.indexed] == [
        "resource-0",
        "resource-1",
        "resource-2",
    ]
    assert fake_database.fetch_calls == 3
    assert fake_es.indices.refreshed == ["btaa_geospatial_api"]


@pytest.mark.asyncio
async def test_index_changed_resources_deletes_missing_ids(monkeypatch):
    fake_database = FakeDatabase([])
    fake_es = FakeElasticsearch()

    monkeypatch.setenv("BRIDGE_SEARCH_INDEX_REFRESH_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_SEARCH_INDEX_MAX_RESOURCE_IDS", "5000")
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
    monkeypatch.setattr(search_index, "database", fake_database)
    monkeypatch.setattr(search_index, "es", fake_es)
    monkeypatch.setattr(search_index, "process_resource", AsyncMock())

    stats = await search_index.index_changed_resources(["missing-resource"])

    assert stats == {
        "enabled": True,
        "resource_ids": 1,
        "batch_size": 5000,
        "batches": 1,
        "indexed": 0,
        "missing": 1,
        "errors": 0,
    }
    assert fake_es.deleted == [
        {
            "index": "btaa_geospatial_api",
            "id": "missing-resource",
            "options": {"ignore_status": [404]},
        }
    ]
    assert fake_es.indices.refreshed == ["btaa_geospatial_api"]


@pytest.mark.asyncio
async def test_index_changed_resources_can_be_disabled(monkeypatch):
    monkeypatch.setenv("BRIDGE_SEARCH_INDEX_REFRESH_ENABLED", "false")
    monkeypatch.setattr(search_index, "database", FakeDatabase([]))
    monkeypatch.setattr(search_index, "es", FakeElasticsearch())
    monkeypatch.setattr(search_index, "process_resource", AsyncMock())

    stats = await search_index.index_changed_resources(["resource-1"])

    assert stats == {"enabled": False, "resource_ids": 0, "indexed": 0, "errors": 0}
