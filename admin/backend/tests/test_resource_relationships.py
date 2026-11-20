from dataclasses import replace

import pytest
import test_resources
from test_managing_sets import create, headers
from test_resource_editor import patch, seed
from test_resources import BASE, preview

from app.url_ids import encode_id

api = test_resources.api
pytestmark = pytest.mark.integration


async def test_navigation_import_edit_clear_scope_and_pagination(api):
    client, actors, scope, record = await seed(api)
    other = await create(client, code="other-relations")
    payload, _ = await preview(
        client,
        other,
        [
            dict(record, id="parent", dct_title_s="Parent", dct_source_sm=["editor/test"]),
            dict(record, id="child", dct_title_s="Child", pcdm_memberOf_sm=["editor/test"]),
        ],
    )
    assert (
        await client.post(BASE + "/imports", headers=headers(), json=payload)
    ).status_code == 200
    assert (
        await patch(
            client,
            {
                "lock_version": 1,
                "values": {
                    "dct_isPartOf_sm": ["parent", "parent", "missing", "editor/test"],
                    "dct_relation_sm": ["https://example.org/external"],
                },
            },
        )
    ).status_code == 200

    async def get(**params):
        return await client.get(
            BASE + "/" + encode_id("editor/test") + "/relationships", params={**params}
        )

    response = await get()
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    rows = response.json()["items"]
    assert response.json()["total"] == 5
    assert {(r["relationship"], r["id"]) for r in rows} == {
        ("Is part of", "parent"),
        ("Is part of", "missing"),
        ("Related to", "https://example.org/external"),
        ("Is source of", "parent"),
        ("Has member", "child"),
    }
    assert next(r for r in rows if r["id"] == "parent")["title"] == "Parent"
    assert (await get(limit=2, offset=2)).json()["items"] == rows[2:4]
    assert (await get(limit=101)).status_code == 422
    actors[0] = replace(actors[0], set_ids=frozenset({scope["set_id"]}))
    scoped = (await get()).json()
    assert scoped["total"] == 3  # Inverse edges from inaccessible records must not leak.
    assert all(r["title"] is None and r["set_id"] is None for r in scoped["items"])
    assert (
        await patch(
            client, {"lock_version": 2, "clear_fields": ["dct_isPartOf_sm", "dct_relation_sm"]}
        )
    ).status_code == 200
    assert (await get()).json()["total"] == 0
    actors[0] = replace(actors[0], set_ids=frozenset())
    assert (await get()).status_code == 404
    actors[0] = replace(actors[0], permissions=frozenset())
    assert (await get()).status_code == 403
