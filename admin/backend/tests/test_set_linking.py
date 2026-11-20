import asyncio
import importlib.util
import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
import test_resources
from sqlalchemy import select
from test_managing_sets import create, headers
from test_resource_sources import setup
from test_resources import BASE, preview
from test_source_linking import LocalApi, candidate, linker

from app.activity import activity
from app.resources.models import evidence, resources

api = test_resources.api
sys.modules.setdefault("local_admin_api", linker)
spec = importlib.util.spec_from_file_location(
    "link_resource_sets", Path(__file__).parents[2] / "scripts/link_resource_sets.py"
)
mover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mover)
ORIGIN = "00000000-0000-0000-0000-000000000001"
TARGET = "00000000-0000-0000-0000-000000000002"


def manifest(origin=ORIGIN, target=TARGET, origin_code="origin", target_code="target"):
    return {
        "schema_version": 3,
        "sets": [
            {
                "set_id": origin,
                "source_id": "parent",
                "legacy_code": origin_code,
                "lock_version": 1,
            },
            {
                "set_id": target,
                "source_id": "Source_A",
                "legacy_code": target_code,
                "lock_version": 1,
            },
        ],
        "assignments": [
            {
                "id": "move-me",
                "source_id": "parent",
                "expected_code": "01a-01",
                "source_set_id": origin,
                "target_set_id": target,
                "resource_version": 1,
                "reason": "Reviewed Source code matches target Set",
            }
        ],
    }


def test_manifest_needs_explicit_targets_versions_and_reasons():
    plan = manifest()
    mover.validate(plan)
    changes = [
        lambda p: p.update(schema_version=0),
        lambda p: p["sets"].append(p["sets"][0]),
        lambda p: p["sets"][0].update(lock_version=True),
        lambda p: p["assignments"].append(p["assignments"][0]),
        lambda p: p["assignments"][0].update(target_set_id="unlisted"),
        lambda p: p["assignments"][0].update(target_set_id=ORIGIN),
        lambda p: p["assignments"][0].update(resource_version=0),
        lambda p: p["assignments"][0].update(reason=" "),
        lambda p: p["assignments"][0].update(source_id=[]),
        lambda p: p["assignments"][0].update(expected_code=[]),
        lambda p: p.update(assignments=[]),
    ]
    for change in changes:
        invalid = deepcopy(plan)
        change(invalid)
        with pytest.raises(ValueError):
            mover.validate(invalid)


@pytest.mark.parametrize(
    "changes,outcome",
    [
        ({}, "candidate"),
        ({"set_id": TARGET, "source_id": "Source_A", "lock_version": 2}, "already_assigned"),
        ({"source_id": "other"}, "changed_source_or_code"),
        ({"b1g_code_s": "other"}, "changed_source_or_code"),
        ({"set_id": "other"}, "changed_set"),
        ({"lock_version": 2}, "stale_version"),
    ],
)
def test_no_rebase_or_move_after_source_changes(changes, outcome):
    current = candidate(set_id=ORIGIN, source_id="parent")
    assert (
        mover.classify(
            {**current, **changes}, manifest()["assignments"][0], mover.validate(manifest())[0]
        )
        == outcome
    )


async def seed(api):
    client, actors, origin, _ = await setup(api)
    actors[0] = replace(actors[0], permissions=actors[0].permissions | {"resources:associate"})
    target = await create(client, code="target", source_id="Source_A")
    record = {
        "id": "move-me",
        "dct_title_s": "Preserve me",
        "b1g_code_s": "01a-01",
        "source_id": "parent",
    }
    body, _ = await preview(client, origin, [record])
    response = await client.post(BASE + "/imports", json=body, headers=headers())
    assert response.status_code == 200, response.text
    plan = manifest(str(origin["set_id"]), str(target["set_id"]), origin["legacy_code"])
    return client, actors, origin, target, plan, record


@pytest.mark.integration
async def test_move_preview_apply_rerun_and_dual_activity(api, database_engine, tmp_path):
    client, _, origin, target, plan, record = await seed(api)
    local = LocalApi(client, asyncio.get_running_loop())
    dry = await asyncio.to_thread(mover.run, local, plan, tmp_path / "dry")
    assert dry["counts"] == {"would_assign": 1} and not local.writes
    applied = await asyncio.to_thread(mover.run, local, plan, tmp_path / "apply", apply=True)
    assert applied["counts"] == {"assigned": 1}
    path, body, key = local.writes[0]
    assert (
        await client.put(linker.PREFIX + path, json=body, headers=headers(key))
    ).status_code == 200
    writes = len(local.writes)
    replay = await asyncio.to_thread(mover.run, local, plan, tmp_path / "rerun", apply=True)
    assert replay["counts"] == {"already_assigned": 1} and len(local.writes) == writes
    async with database_engine.connect() as connection:
        row = (
            (await connection.execute(select(resources).where(resources.c.id == "move-me")))
            .mappings()
            .one()
        )
        assert str(row["set_id"]) == str(target["set_id"])
        assert row["legacy_source_id"] is None and row["lock_version"] == 2
        assert row["dct_title_s"] == "Preserve me"
        assert (
            await connection.scalar(
                select(evidence.c.source_record).where(evidence.c.resource_id == "move-me")
            )
            == record
        )
        entries = (
            (
                await connection.execute(
                    select(activity).where(activity.c.action == "resource.associated")
                )
            )
            .mappings()
            .all()
        )
        assert len(entries) == 2
        assert entries[0]["correlation_id"] == entries[1]["correlation_id"]
        assert {str(e["set_id"]) for e in entries} == {
            str(origin["set_id"]),
            str(target["set_id"]),
        }


@pytest.mark.integration
async def test_changed_source_preflight_and_denied_association_write_nothing(
    api, database_engine, tmp_path
):
    client, actors, _, _, plan, _ = await seed(api)
    local = LocalApi(client, asyncio.get_running_loop())
    wrong = deepcopy(plan)
    wrong["assignments"][0]["source_id"] = "Source-B"
    with pytest.raises(ValueError, match="origin Set"):
        await asyncio.to_thread(mover.run, local, wrong, tmp_path / "changed", apply=True)
    assert not local.writes
    actors[0] = replace(actors[0], permissions=actors[0].permissions - {"resources:associate"})
    with pytest.raises(linker.ApiError) as exc:
        await asyncio.to_thread(mover.run, local, plan, tmp_path / "denied", apply=True)
    assert exc.value.status == 403
    report = json.loads((tmp_path / "denied/summary.json").read_text())
    assert not report["complete"] and not local.writes
    async with database_engine.connect() as connection:
        assert (
            await connection.scalar(
                select(resources.c.lock_version).where(resources.c.id == "move-me")
            )
            == 1
        )
