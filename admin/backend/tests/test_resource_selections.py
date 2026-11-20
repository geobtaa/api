import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.exc import DBAPIError
from test_jobs import MANAGER, setup
from test_managing_sets import api as set_api
from test_managing_sets import headers

from app.resources.models import resources
from app.resources.selection_models import selection_items, selections

api = set_api
pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/resources/selections"


async def test_all_matching_selection_is_set_based_paginated_immutable_and_replayable(
    api, database_engine
):
    client, actor = api
    await setup(api, database_engine, 1005)
    key = uuid4()
    first, replay = await asyncio.gather(
        *[client.post(BASE, headers=headers(key), json={}) for _ in range(2)]
    )
    assert first.status_code == replay.status_code == 201, first.text
    assert first.json() == replay.json()
    assert first.json()["total"] == 1005
    sid = first.json()["selection_id"]
    page = await client.get(BASE + "/" + sid + "?offset=1000&limit=500")
    assert page.status_code == 200, page.text
    assert len(page.json()["items"]) == 5
    assert page.json()["total"] == 1005
    async with database_engine.begin() as connection:
        await connection.execute(
            update(resources).where(resources.c.id == "resource-0").values(lock_version=2)
        )
    saved = (await client.get(BASE + "/" + sid + "?limit=1")).json()["items"][0]
    assert saved["resource_version"] == 1 and saved["current_version"] == 2
    for statement in [
        update(selection_items).values(resource_version=3),
        update(selections).values(query={"q": "changed"}),
        insert(selection_items).values(
            selection_id=UUID(sid),
            resource_id="other",
            set_id=saved["set_id"],
            resource_version=1,
        ),
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(statement)
    assert (
        await client.post(BASE, headers=headers(key), json={"q": "different"})
    ).status_code == 409
    actor[0] = replace(MANAGER, set_ids=frozenset())
    assert (await client.get(BASE + "/" + sid)).status_code == 404
    assert (await client.post(BASE, headers=headers(key), json={})).status_code == 404
    actor[0] = replace(MANAGER, actor_id="another-user")
    assert (await client.get(BASE + "/" + sid)).status_code == 404
    actor[0] = replace(MANAGER, kind="service_account")
    assert (await client.post(BASE, headers=headers(), json={})).status_code == 403


async def test_selection_predicates_match_search_and_invalid_ids_fail_atomically(
    api, database_engine
):
    client, _ = api
    body, _ = await setup(api, database_engine, 20)
    query = {
        "q": "Resource 1",
        "set_id": body["set_id"],
        "filters": {"publication": ["draft"]},
    }
    snapshot = await client.post(BASE, headers=headers(), json=query)
    assert snapshot.status_code == 201, snapshot.text
    assert snapshot.json()["total"] == 11
    assert (
        await client.post(BASE, headers=headers(), json={"ids": ["missing"]})
    ).status_code == 404
    assert (
        await client.post(BASE, headers=headers(), json={"filters": {"unknown": []}})
    ).status_code == 422
    assert (await client.post(BASE, headers=headers(), json={"ids": []})).status_code == 422
    selected = await client.post(BASE, headers=headers(), json={"ids": ["resource-0"]})
    assert selected.status_code == 201 and selected.json()["total"] == 1
    async with database_engine.connect() as connection:
        assert len((await connection.execute(select(selections))).all()) == 2


async def test_selection_query_configuration_is_bounded():
    from pydantic import ValidationError

    from app.resources.selections import SelectionRequest

    with pytest.raises(ValidationError, match="at most 1 MB"):
        SelectionRequest(filters={"provider": ["x" * 1_000_001]})
