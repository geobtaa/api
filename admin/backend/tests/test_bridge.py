import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
import test_resources
from sqlalchemy import func, select
from test_managing_sets import BASE as SET_BASE
from test_managing_sets import create, headers
from test_resources import BASE

from app.resources.association_models import resource_assets, resource_data_dictionary_entries
from app.resources.bridge import adapt
from app.resources.models import evidence, imports, resources

api = test_resources.api
pytestmark = pytest.mark.integration


async def test_retirement_between_bridge_scope_read_and_lock_blocks_new_resources(
    api, database_engine, monkeypatch
):
    from app.resources import bridge

    client, actors = api
    actors[0] = replace(actors[0], permissions=actors[0].permissions | {"sets:retire"})
    scope = await create(client)
    checked = asyncio.Event()
    retired = asyncio.Event()
    original = bridge.get_set
    first = True

    async def pause_after_read(*args):
        nonlocal first
        result = await original(*args)
        if first:
            first = False
            checked.set()
            await asyncio.wait_for(retired.wait(), timeout=5)
        return result

    monkeypatch.setattr(bridge, "get_set", pause_after_read)
    pending = asyncio.create_task(
        client.post(
            BASE + "/bridge/batches",
            headers=headers(),
            json={"set_id": scope["set_id"], "records": [record()]},
        )
    )
    await asyncio.wait_for(checked.wait(), timeout=5)
    try:
        result = await client.put(
            SET_BASE + "/" + scope["set_id"] + "/state",
            headers=headers(),
            json={
                "target": "retired",
                "lock_version": 1,
                "reason": "Source closed",
                "confirmed": True,
            },
        )
        assert result.status_code == 200
    finally:
        retired.set()
    response = await asyncio.wait_for(pending, timeout=5)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "retired"
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(resources)) == 0
        assert await connection.scalar(select(func.count()).select_from(imports)) == 0


def record(rid="bridge/one"):
    return dict(
        id=rid,
        dct_title_s="Bridge map",
        gbl_mdVersion_s="1.0",
        schema_provider_s=None,
        dct_references_s="[]",
        document_distributions=[
            dict(reference_type_id=2, url="https://example.org/service", label=None)
        ],
        document_downloads=[dict(id=1, value="https://example.org/data.zip", position=0)],
        document_licensed_accesses=[
            dict(institution_code="UMN", url="https://example.org/license")
        ],
        assets=[
            dict(
                id="asset1",
                parent_id="parent",
                file={"url": "https://example.org/image", "metadata": {"width": 100}},
                thumbnail=False,
            )
        ],
        document_data_dictionaries=[dict(id=10, name="Fields", tags=["one"])],
        document_data_dictionary_entries=[
            dict(id=11, document_data_dictionary_id=10, field_name="name")
        ],
    )


async def test_bridge_aggregate_receipts_scope_and_raw_evidence(api, database_engine):
    client, actors = api
    scope = await create(client)
    payload = dict(set_id=scope["set_id"], records=[record()])
    key = uuid4()
    result = await client.post(BASE + "/bridge/batches", headers=headers(key), json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["created"] == 1
    assert (
        await client.post(BASE + "/bridge/batches", headers=headers(key), json=payload)
    ).json() == result.json()
    assert (
        await client.post(
            BASE + "/bridge/batches",
            headers=headers(key),
            json={**payload, "records": [record("different")]},
        )
    ).status_code == 409
    assert (await client.post(BASE + "/bridge/batches", headers=headers(), json=payload)).json()[
        "items"
    ][0]["outcome"] == "existing"
    async with database_engine.connect() as c:
        assert await c.scalar(select(evidence.c.source_record)) == record()
        assert await c.scalar(select(func.count()).select_from(resource_assets)) == 1
        assert (
            await c.scalar(select(func.count()).select_from(resource_data_dictionary_entries)) == 1
        )
    actors[0] = replace(actors[0], set_ids=frozenset())
    assert (
        await client.post(BASE + "/bridge/batches", headers=headers(), json=payload)
    ).status_code == 404
    actors[0] = replace(actors[0], permissions=frozenset())
    assert (
        await client.post(BASE + "/bridge/batches", headers=headers(), json=payload)
    ).status_code == 403


async def test_bridge_invalid_deleted_duplicate_and_rollback(api, database_engine):
    client, _ = api
    scope = await create(client)
    invalid = record("invalid")
    invalid["document_distributions"][0]["reference_type_id"] = 999
    payload = dict(
        set_id=scope["set_id"],
        records=[invalid, dict(id="gone", deleted=True), record("dup"), record("dup")],
    )
    response = await client.post(BASE + "/bridge/batches", headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    assert [r["outcome"] for r in response.json()["items"]] == [
        "invalid",
        "source_deleted",
        "invalid",
        "invalid",
    ]
    # Global legacy dictionary uniqueness fails the aggregate and its receipt together.
    payload["records"] = [record("first"), record("second")]
    response = await client.post(BASE + "/bridge/batches", headers=headers(), json=payload)
    assert response.status_code == 503, response.text
    async with database_engine.connect() as c:
        assert await c.scalar(select(func.count()).select_from(resources)) == 0
        assert await c.scalar(select(func.count()).select_from(imports)) == 1


async def test_bridge_large_batch(api):
    client, _ = api
    scope = await create(client)
    response = await client.post(
        BASE + "/bridge/batches",
        headers=headers(),
        json=dict(
            set_id=scope["set_id"],
            records=[
                dict(id=f"batch/{i}", dct_title_s="Map", dct_references_s="[]") for i in range(500)
            ],
        ),
    )
    assert response.status_code == 200, response.text
    assert response.json()["created"] == 500


def test_bridge_mapping_failures_and_legacy_shapes():
    values, links, *_ = adapt(
        dict(id="x", dct_title_s=["Title"], dct_subject_sm="Maps", dct_references_s="[]")
    )
    assert values["dct_subject_sm"] == ["Maps"] and links == []
    with pytest.raises(ValueError):
        adapt(
            dict(
                record(),
                document_data_dictionary_entries=[dict(id=1, document_data_dictionary_id=999)],
            )
        )
    with pytest.raises(ValueError):
        adapt(dict(record(), document_downloads="bad"))


def test_crawler_resume_reuses_page_and_batch_identity(tmp_path, monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts/import_kithe_bridge.py"
    spec = importlib.util.spec_from_file_location("bridge_crawler", path)
    crawler = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(crawler)
    monkeypatch.setenv("KITHE_BRIDGE_URL", "https://example.org/bridge")
    monkeypatch.setenv("KITHE_BRIDGE_TOKEN", "test")
    monkeypatch.setattr(sys, "argv", ["crawl", "--output", str(tmp_path), "--set-id", "local"])
    keys = []

    def lost_response(url, **kwargs):
        if kwargs.get("token"):
            return {"data": [{"id": "one"}], "has_more": False}
        keys.append(kwargs["key"])
        raise RuntimeError("Lost response after commit")

    monkeypatch.setattr(crawler, "request", lost_response)
    with pytest.raises(RuntimeError):
        crawler.main()
    assert not (tmp_path / "checkpoint.json").exists()

    def replay(url, **kwargs):
        assert not kwargs.get("token")  # Source page is already durable.
        keys.append(kwargs["key"])
        return {"items": [{"outcome": "created"}]}

    monkeypatch.setattr(crawler, "request", replay)
    crawler.main()
    crawler.main()  # Completed crawl does not repeat requests.
    assert len(keys) == 2 and keys[0] == keys[1]
