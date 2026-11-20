import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from test_sets import api as api
from test_sets import create, headers

from app.work.cadence import advance
from app.work.models import tasks

pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/tasks"
PERMISSIONS = {
    "tasks:read",
    "tasks:create",
    "tasks:update",
    "tasks:complete",
    "work:configure",
    "work:report",
}


async def setup(api):
    client, actor = api
    actor[0] = replace(actor[0], permissions=actor[0].permissions | PERMISSIONS)
    subject = await create(client)
    return client, actor, subject


async def task(client, subject, **values):
    response = await client.post(
        BASE,
        headers=headers(),
        json={
            "set_id": subject["set_id"],
            "work_type": "review",
            "title": "Review imagery",
            "due_on": "2026-08-31",
            **values,
        },
    )
    assert response.status_code == 201, response.text
    assert response.headers["location"] == BASE + "/" + response.json()["task_id"]
    return response.json()


async def test_tasks_queue_calendar_completion_and_named_period_reporting(api):
    client, _, subject = await setup(api)
    item = await task(client, subject, planned_on="2026-09-02")
    path = BASE + "/" + item["task_id"]
    calendar = (
        await client.get(BASE, params={"calendar_from": "2026-09-01", "calendar_to": "2026-09-30"})
    ).json()
    assert calendar["total"] == 1
    assert (await client.get(BASE, params={"calendar_to": "2026-08-31"})).json()["total"] == 0
    body = {
        "lock_version": 1,
        "completed_at": "2026-09-02T15:00:00Z",
        "summary": "Reviewed all metadata",
        "processed_count": 200,
        "changed_count": 12,
        "evidence": [{"label": "Review notes", "url": "https://example.org/report"}],
    }
    key = headers()
    result = await client.post(path + "/completion", headers=key, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "completed"
    assert result.json()["completed_at"] != result.json()["completion_recorded_at"]
    assert (await client.post(path + "/completion", headers=key, json=body)).json() == result.json()
    assert (await client.get(BASE)).json()["total"] == 0
    assert (
        await client.get(BASE, params={"status": "completed", "completed_to": "2026-08-31"})
    ).json()["total"] == 0
    for group in ["source", "set", "work_type", "completed_by"]:
        report = await client.get(
            BASE + "/report",
            params={
                "starts_on": "2026-09-01",
                "ends_on": "2026-09-30",
                "group_by": group,
                "q": " imagery ",
            },
        )
        assert report.status_code == 200, report.text
        report = report.json()
        assert (report["completed"], report["processed"], report["changed"], report["late"]) == (
            1,
            200,
            12,
            1,
        )
        assert report["total_groups"] == 1 and report["groups"][0]["completed"] == 1
    period = await client.post(
        "/api/v1/admin/work-periods",
        headers=headers(),
        json={"name": "Fall semester 2026", "starts_on": "2026-08-24", "ends_on": "2026-12-18"},
    )
    assert period.status_code == 201, period.text
    assert (await client.get(period.headers["location"])).json() == period.json()
    assert (await client.get(f"/api/v1/admin/work-periods/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/admin/work-periods")).json()[0][
        "name"
    ] == "Fall semester 2026"
    activity = (await client.get(path + "/activity")).json()
    assert activity["total"] == 2
    assert activity["items"][0]["action"] == "task.completed"
    edit = await client.patch(
        path,
        headers=headers(),
        json={"lock_version": 2, "title": "Rewrite history", "reason": "test"},
    )
    assert edit.status_code == 409


async def test_recurring_completion_is_atomic_and_deduplicated(api, database_engine):
    client, _, subject = await setup(api)
    rulepath = f"/api/v1/admin/sets/{subject['set_id']}/maintenance/review"
    body = {"lock_version": 0, "interval": "P1M", "next_due_on": "2026-01-31"}
    key = headers()
    result = await client.put(rulepath, headers=key, json=body)
    assert result.status_code == 200, result.text
    assert (await client.put(rulepath, headers=key, json=body)).json() == result.json()
    item = (await client.get(BASE)).json()["items"][0]
    path = BASE + "/" + item["task_id"] + "/completion"
    completion = {"lock_version": 1, "completed_at": "2026-01-31T23:30:00Z", "summary": "Reviewed"}
    key = headers()
    first, replay = await asyncio.gather(
        client.post(path, headers=key, json=completion),
        client.post(path, headers=key, json=completion),
    )
    assert first.status_code == replay.status_code == 200, first.text
    pending = (await client.get(BASE)).json()
    assert pending["total"] == 1
    assert pending["items"][0]["due_on"] == "2026-02-28"
    assert pending["items"][0]["predecessor_id"] == item["task_id"]
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(tasks)) == 2
    assert (await client.post(path, headers=headers(), json=completion)).status_code == 409
    assert (await client.get(f"/api/v1/admin/sets/{subject['set_id']}/maintenance")).json()[0][
        "interval"
    ] == "P1M"


async def test_task_guards_failure_history_and_rollback(api, database_engine):
    client, actor, subject = await setup(api)
    item = await task(client, subject)
    path = BASE + "/" + item["task_id"]
    blocked = await client.patch(
        path,
        headers=headers(),
        json={"lock_version": 1, "status": "blocked", "reason": "Remote endpoint unavailable"},
    )
    assert blocked.status_code == 200, blocked.text
    assert blocked.json()["completed_at"] is None
    assert (
        await client.patch(
            path, headers=headers(), json={"lock_version": 1, "title": "Stale", "reason": "edit"}
        )
    ).status_code == 409
    assert (await client.post(BASE, json={"set_id": subject["set_id"]})).status_code == 422
    assert (
        await client.patch(
            path,
            headers=headers(),
            json={"lock_version": 2, "assignee_id": str(uuid4()), "reason": "Assign"},
        )
    ).status_code == 422
    assert (
        await client.post(
            path + "/completion",
            headers=headers(),
            json={
                "lock_version": 2,
                "completed_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
                "summary": "future",
            },
        )
    ).status_code == 422
    original = actor[0]
    for permission in ["tasks:read", "sets:read", "sources:read"]:
        actor[0] = replace(original, permissions=original.permissions - {permission})
        assert (await client.get(path)).status_code == 403
    actor[0] = replace(original, kind="service_account")
    assert (await client.get(path)).status_code == 403
    actor[0] = original
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""CREATE FUNCTION fail_work_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'test rollback'; END $$""")
        )
        await connection.execute(
            text("""CREATE TRIGGER fail_work_event BEFORE INSERT ON work_task_events
FOR EACH ROW EXECUTE FUNCTION fail_work_event()""")
        )
    completion = {"lock_version": 2, "completed_at": "2026-09-01T00:00:00Z", "summary": "Done"}
    key = headers()
    result = await client.post(path + "/completion", headers=key, json=completion)
    assert result.status_code == 503
    assert (await client.get(path)).json()["status"] == "blocked"
    async with database_engine.begin() as connection:
        await connection.execute(text("DROP TRIGGER fail_work_event ON work_task_events"))
    assert (
        await client.post(path + "/completion", headers=key, json=completion)
    ).status_code == 200
    with pytest.raises(Exception, match="immutable"):
        async with database_engine.begin() as connection:
            await connection.execute(text("UPDATE work_task_events SET action='fabricated'"))


@pytest.mark.parametrize(
    "day,interval,expected",
    [
        ("2024-02-29", "P1Y", "2025-02-28"),
        ("2026-01-31", "P1M", "2026-02-28"),
        ("2026-09-23", "P2W", "2026-10-07"),
        ("2026-12-31", "P1D", "2027-01-01"),
    ],
)
def test_calendar_recurrence(day, interval, expected):
    assert advance(date.fromisoformat(day), interval) == date.fromisoformat(expected)


async def test_paused_set_completion_resumes_exactly_once_and_retirement_guards_work(api):
    client, actor, subject = await setup(api)
    actor[0] = replace(actor[0], permissions=actor[0].permissions | {"sets:retire"})
    setpath = f"/api/v1/admin/sets/{subject['set_id']}"
    result = await client.put(
        setpath + "/maintenance/ingest",
        headers=headers(),
        json={"lock_version": 0, "interval": "P1M", "next_due_on": "2026-08-01"},
    )
    assert result.status_code == 200, result.text
    assert (
        await client.put(
            setpath + "/state",
            headers=headers(),
            json={
                "lock_version": 1,
                "target": "retired",
                "reason": "End collection",
                "confirmed": True,
            },
        )
    ).status_code == 409
    assert (
        await client.put(
            setpath + "/state",
            headers=headers(),
            json={
                "lock_version": 1,
                "target": "inactive",
                "reason": "Pause collection",
                "confirmed": True,
            },
        )
    ).status_code == 200
    item = (await client.get(BASE)).json()["items"][0]
    assert (
        await client.post(
            BASE + "/" + item["task_id"] + "/completion",
            headers=headers(),
            json={"lock_version": 1, "completed_at": "2026-08-02T12:00:00Z", "summary": "Imported"},
        )
    ).status_code == 200
    assert (await client.get(BASE)).json()["total"] == 0
    rule = (await client.get(setpath + "/maintenance")).json()[0]
    assert rule["next_due_on"] == "2026-09-02"
    key = headers()
    activation = {
        "lock_version": 2,
        "target": "active",
        "reason": "Resume collection",
        "confirmed": True,
    }
    assert (await client.put(setpath + "/state", headers=key, json=activation)).status_code == 200
    assert (await client.put(setpath + "/state", headers=key, json=activation)).status_code == 200
    assert (await client.get(BASE)).json()["total"] == 1
    assert (await client.get(BASE)).json()["items"][0]["due_on"] == "2026-09-02"


async def test_set_scope_protects_queue_report_history_and_replays(api):
    client, actor, subject = await setup(api)
    other = await create(client, set_id="other", title="Other Set")
    item = await task(client, other)
    key = headers()
    command = {"lock_version": 1, "completed_at": "2026-09-01T12:00:00Z", "summary": "Done"}
    path = BASE + "/" + item["task_id"]
    assert (await client.post(path + "/completion", headers=key, json=command)).status_code == 200
    actor[0] = replace(actor[0], set_ids=frozenset({subject["set_id"]}))
    assert (await client.get(BASE, params={"status": "completed"})).json()["total"] == 0
    assert (await client.get("/api/v1/admin/sets")).json()["total"] == 1
    for url in [path, path + "/activity", "/api/v1/admin/sets/other/maintenance"]:
        assert (await client.get(url)).status_code == 404
    assert (await client.post(path + "/completion", headers=key, json=command)).status_code == 404
    report = await client.get(
        BASE + "/report", params={"starts_on": "2026-09-01", "ends_on": "2026-09-30"}
    )
    assert report.json()["completed"] == 0
    actor[0] = replace(actor[0], set_ids=frozenset())
    assert (await client.get("/api/v1/admin/sets")).json()["total"] == 0


async def test_assignment_requires_full_current_access_and_recurrence_handles_revocation(
    api, database_engine
):
    from sqlalchemy import delete, insert

    from app.identity.models import accounts, grants
    from app.persistence import actors
    from app.work.service import ASSIGNEE_PERMISSIONS

    client, _, subject = await setup(api)
    staff_id = uuid4()
    async with database_engine.begin() as connection:
        await connection.execute(
            insert(actors).values(
                id=staff_id, subject_key="work-assignee", kind="user", display_name="Staff member"
            )
        )
        await connection.execute(insert(accounts).values(actor_id=staff_id, all_sets=True))
        await connection.execute(
            insert(grants),
            [
                {"actor_id": staff_id, "permission": permission}
                for permission in ASSIGNEE_PERMISSIONS - {"sources:read"}
            ],
        )
    rulepath = f"/api/v1/admin/sets/{subject['set_id']}/maintenance/review"
    payload = {
        "lock_version": 0,
        "interval": "P1M",
        "next_due_on": "2026-08-01",
        "assignee_id": str(staff_id),
    }
    assert (await client.put(rulepath, headers=headers(), json=payload)).status_code == 422
    assert all(
        row["actor_id"] != str(staff_id) for row in (await client.get(BASE + "/assignees")).json()
    )
    async with database_engine.begin() as connection:
        await connection.execute(
            insert(grants).values(actor_id=staff_id, permission="sources:read")
        )
    assert (await client.put(rulepath, headers=headers(), json=payload)).status_code == 200
    assert any(
        row["actor_id"] == str(staff_id) for row in (await client.get(BASE + "/assignees")).json()
    )
    item = (await client.get(BASE)).json()["items"][0]
    async with database_engine.begin() as connection:
        await connection.execute(
            delete(grants).where(
                grants.c.actor_id == staff_id, grants.c.permission == "tasks:update"
            )
        )
    result = await client.post(
        BASE + "/" + item["task_id"] + "/completion",
        headers=headers(),
        json={"lock_version": 1, "completed_at": "2026-08-02T12:00:00Z", "summary": "Done"},
    )
    assert result.status_code == 200, result.text
    pending = (await client.get(BASE)).json()["items"][0]
    assert pending["assignee_id"] is None
    assert pending["predecessor_id"] == item["task_id"]


async def test_calendar_paginates_in_planned_date_order(api):
    client, _, subject = await setup(api)
    first = await task(client, subject, due_on="2026-09-30", planned_on="2026-09-01")
    await task(client, subject, due_on="2026-09-01", planned_on="2026-09-30")
    page = (
        await client.get(
            BASE, params={"calendar_from": "2026-09-01", "calendar_to": "2026-09-30", "limit": 1}
        )
    ).json()
    assert page["total"] == 2
    assert page["items"][0]["task_id"] == first["task_id"]


async def test_editing_occurrence_due_date_keeps_maintenance_and_versions_consistent(api):
    client, _, subject = await setup(api)
    base = f"/api/v1/admin/sets/{subject['set_id']}/maintenance"
    assert (
        await client.put(
            base + "/review",
            headers=headers(),
            json={"lock_version": 0, "interval": "P1M", "next_due_on": "2026-10-01"},
        )
    ).status_code == 200
    item = (await client.get(BASE)).json()["items"][0]
    result = await client.patch(
        BASE + "/" + item["task_id"],
        headers=headers(),
        json={"lock_version": 1, "due_on": "2026-10-15", "reason": "Align review with delivery"},
    )
    assert result.status_code == 200, result.text
    rule = (await client.get(base)).json()[0]
    assert rule["next_due_on"] == "2026-10-15"
    assert rule["lock_version"] == 2
    assert (
        await client.put(
            base + "/review", headers=headers(), json={"lock_version": 1, "interval": "P2M"}
        )
    ).status_code == 409
