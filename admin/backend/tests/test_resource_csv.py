import csv
import io
import json
from dataclasses import replace
from uuid import uuid4

import pytest
import test_resources
from sqlalchemy import func, select, text
from test_managing_sets import EDITOR, headers
from test_resource_editor import seed
from test_resources import BASE

from app.resources import csv_format
from app.resources.csv_io import CsvRequest, columns, parse
from app.resources.models import resources
from app.sets.models import commands
from app.url_ids import encode_id

api = test_resources.api
pytestmark = pytest.mark.integration


def document(header, *rows):
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


async def resource_upload(client, source, mode):
    """Build full CSV fixtures by overlaying test cells on the current export."""
    reader = csv.reader(io.StringIO(source))
    header = next(reader)
    names = [csv_format.field_name(name) for name in header]
    missing = [name for name in columns(EDITOR) if name not in names]
    if not missing:
        return source
    existing = {}
    if mode != "create":
        exported = await client.get(BASE + "/csv/export")
        assert exported.status_code == 200, exported.text
        existing = {row["id"]: row for row in csv.DictReader(io.StringIO(exported.text))}
    out = io.StringIO(newline="")
    writer = csv.writer(out)
    writer.writerow([*header, *missing])
    for cells in reader:
        supplied = dict(zip(names, cells, strict=True))
        original = existing.get(supplied["id"], {})
        appended = [
            ""
            if name in {"set_id", "source_id", "lock_version", "_csv_encoding"}
            or supplied.get(name + "__clear") == "true"
            else original.get(name, "")
            for name in missing
        ]
        writer.writerow([*cells, *appended])
    return out.getvalue()


async def preview(client, scope, source, mode="update"):
    payload = {
        "set_id": scope["set_id"],
        "mode": mode,
        "csv": await resource_upload(client, source, mode),
    }
    response = await client.post(BASE + "/csv/preview", headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    return {
        **payload,
        "preview_hash": response.json()["preview_hash"],
        "confirmed": True,
    }, response.json()


async def test_csv_round_trip_selective_updates_and_retry(api, database_engine):
    client, _, scope, _ = await seed(api)
    exported = await client.get(BASE + "/csv/export", params={"set_id": scope["set_id"]})
    assert exported.status_code == 200 and "attachment" in exported.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == 1 and rows[0]["id"] == "editor/test"
    assert rows[0]["dct_description_sm"] == '["One", "Two"]'
    body, plan = await preview(client, scope, exported.text)
    assert plan["items"][0]["outcome"] == "unchanged"
    source = document(
        [
            "id",
            "lock_version",
            "schema_provider_s",
            "schema_provider_s__clear",
            "dct_description_sm",
            "gbl_indexYear_im",
            "gbl_georeferenced_b",
        ],
        ["editor/test", "1", "", "true", "[]", "[0]", "false"],
    )
    body, plan = await preview(client, scope, source)
    assert plan["ready"] == 1
    assert plan["items"][0]["changes"]["schema_provider_s"] == {"before": "Provider", "after": None}
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(resources.c.lock_version)) == 1
    key = uuid4()
    first = await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    assert first.status_code == 200, first.text
    assert first.json()["items"][0]["outcome"] == "updated"
    assert (
        await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    ).json() == first.json()
    assert (
        await client.post(
            BASE + "/csv/import", headers=headers(key), json={**body, "csv": source + "\n"}
        )
    ).status_code == 409
    saved = (await client.get(BASE + "/" + encode_id("editor/test"), params={})).json()
    assert saved["metadata"]["dct_title_s"] == "Original title"
    assert "schema_provider_s" not in saved["metadata"]
    assert saved["metadata"]["gbl_georeferenced_b"] is False
    assert saved["metadata"]["gbl_indexYear_im"] == [0]
    assert saved["metadata"]["dct_description_sm"] == []
    assert saved["source_record"]["schema_provider_s"] == "Provider"


@pytest.mark.parametrize(
    "columns,values,expected",
    [
        (["schema_provider_s"], [""], "update"),
        (["schema_provider_s"], ["null"], "update"),
        (["schema_provider_s"], [" "], "invalid"),
        (["schema_provider_s", "schema_provider_s__clear"], ["X", "true"], "invalid"),
        (["schema_provider_s__clear"], ["yes"], "invalid"),
        (["schema_provider_s__clear"], ["false"], "unchanged"),
        (["dct_description_sm"], ["null"], "invalid"),
        (["dct_description_sm"], ["bad JSON"], "invalid"),
        (["gbl_georeferenced_b"], ["0"], "invalid"),
        (["dct_title_s__clear"], ["true"], "invalid"),
        (
            ["distributions"],
            ['[{"distribution_type_id":999,"url":"https://example.org"}]'],
            "invalid",
        ),
        (
            ["distributions"],
            ['[{"distribution_type_id":7,"url":"javascript:alert(1)"}]'],
            "invalid",
        ),
        (["distributions__clear"], ["true"], "update"),
    ],
)
async def test_csv_cell_semantics(api, columns, values, expected):
    client, _, scope, _ = await seed(api)
    _, plan = await preview(
        client, scope, document(["id", "lock_version", *columns], ["editor/test", "1", *values])
    )
    assert plan["items"][0]["outcome"] == expected, plan


async def test_csv_create_validation_export_scope_and_formula_encoding(api):
    client, actor, scope, _ = await seed(api)
    source = document(
        ["id", "dct_title_s", "dct_description_sm", "distributions"],
        [
            "=formula",
            "=1+1",
            '["Unicode café, comma\\nline"]',
            '[{"distribution_type_id":7,"url":"https://example.org/file","label":"File"}]',
        ],
        ["editor/test", "Existing", "", ""],
        ["invalid", "", "", ""],
    )
    body, plan = await preview(client, scope, source, "create")
    assert [row["outcome"] for row in plan["items"]] == ["create", "skipped", "invalid"]
    response = await client.post(BASE + "/csv/import", headers=headers(), json=body)
    assert response.status_code == 200, response.text
    exported = await client.get(BASE + "/csv/export", params={"q": "=formula"})
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert rows[0]["id"] == "'=formula" and rows[0]["dct_title_s"] == "'=1+1"
    _, plan = await preview(client, scope, exported.text)
    assert plan["items"][0]["outcome"] == "unchanged"
    selected = await client.get(BASE + "/csv/export", params={"ids": "editor/test"})
    assert len(list(csv.DictReader(io.StringIO(selected.text)))) == 1
    actor[0] = replace(actor[0], set_ids=frozenset())
    assert (
        len(list(csv.DictReader(io.StringIO((await client.get(BASE + "/csv/export")).text)))) == 0
    )
    assert (
        await client.post(
            BASE + "/csv/preview",
            headers=headers(),
            json={k: v for k, v in body.items() if k not in {"preview_hash", "confirmed"}},
        )
    ).status_code == 404
    actor[0] = replace(actor[0], permissions=frozenset())
    assert (await client.get(BASE + "/csv/export")).status_code == 403


async def test_csv_stale_permissions_invalid_structure_and_rollback(api, database_engine):
    client, actor, scope, _ = await seed(api)
    source = document(["id", "lock_version", "dct_title_s"], ["editor/test", "1", "Changed"])
    body, _ = await preview(client, scope, source)
    original = actor[0]
    actor[0] = replace(original, permissions=original.permissions - {"resources:update"})
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 403
    actor[0] = original
    assert (
        await client.post(
            BASE + "/csv/import", headers=headers(), json={**body, "confirmed": False}
        )
    ).status_code == 422
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE FUNCTION reject_csv() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'test'; END $$"
            )
        )
        await connection.execute(
            text(
                "CREATE TRIGGER reject_csv BEFORE INSERT ON lifecycle_activity_entries "
                "FOR EACH ROW EXECUTE FUNCTION reject_csv()"
            )
        )
    key = uuid4()
    assert (
        await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    ).status_code == 503
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(resources.c.lock_version)) == 1
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(commands)
                .where(commands.c.operation == "resource:csv")
            )
            == 0
        )
        await connection.execute(text("DROP TRIGGER reject_csv ON lifecycle_activity_entries"))
    assert (
        await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    ).status_code == 200
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 409
    _, plan = await preview(client, scope, source)
    assert plan["items"][0]["outcome"] == "conflict"
    for invalid in ["", "id,id\na,a", "id,unknown\na,b", "title\nx", 'id\n"unterminated']:
        result = await client.post(
            BASE + "/csv/preview",
            headers=headers(),
            json={"set_id": scope["set_id"], "mode": "update", "csv": invalid},
        )
        assert result.status_code == 422
    template = await client.get(BASE + "/csv/template")
    assert "__clear" not in template.text


def test_csv_parser_bounds_and_row_failures():
    from test_managing_sets import EDITOR

    from app.domain import DomainError

    for source in ["id\n"]:
        with pytest.raises(DomainError):
            parse(CsvRequest(set_id=str(uuid4()), mode="create", csv=source), EDITOR)
    header = columns(EDITOR)

    def row(identifier, title):
        values = {"id": identifier, "dct_title_s": title}
        return [values.get(name, "") for name in header]

    source = document(header, row("a", "x"), row("a", "y"), ["b"], row(" ", "z"))
    rows = parse(CsvRequest(set_id=str(uuid4()), mode="create", csv=source), EDITOR)
    assert all(row["errors"] for row in rows)


async def test_csv_batch_failure_rolls_back_preceding_rows(api, database_engine):
    client, _, scope, _ = await seed(api)
    body, _ = await preview(
        client, scope, document(["id", "dct_title_s"], ["z-second", "Second"]), "create"
    )
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 200
    body, plan = await preview(
        client,
        scope,
        document(
            ["id", "lock_version", "dct_title_s"],
            ["editor/test", "1", "Changed first"],
            ["z-second", "1", "Changed second"],
        ),
    )
    assert plan["ready"] == 2
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                "CREATE FUNCTION reject_second() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                "IF NEW.details->>'resource_id' = 'z-second' THEN RAISE EXCEPTION 'test'; END IF; "
                "RETURN NEW; END $$"
            )
        )
        await connection.execute(
            text(
                "CREATE TRIGGER reject_second BEFORE INSERT ON lifecycle_activity_entries "
                "FOR EACH ROW EXECUTE FUNCTION reject_second()"
            )
        )
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 503
    async with database_engine.connect() as connection:
        assert list((await connection.execute(select(resources.c.lock_version))).scalars()) == [
            1,
            1,
        ]
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(commands)
                .where(commands.c.operation.like("resource:update:%"))
            )
            == 0
        )


async def test_stream_export_crosses_chunks_and_preserves_distribution_order(api):
    client, _, scope, _ = await seed(api)
    for start, stop in [(0, 100), (100, 102)]:
        source = document(
            ["id", "dct_title_s"],
            *[[f"stream-{i:03}", "Stream record"] for i in range(start, stop)],
        )
        body, _ = await preview(client, scope, source, "create")
        assert (
            await client.post(BASE + "/csv/import", headers=headers(), json=body)
        ).status_code == 200
    exported = await client.get(BASE + "/csv/export", params={"q": "Stream record"})
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == 102 and len({row["id"] for row in rows}) == 102

    links = [
        {"distribution_type_id": kind, "url": f"https://example.org/{i}", "label": None}
        for i, kind in enumerate([7, 8, 7])
    ]
    body, _ = await preview(
        client,
        scope,
        document(["id", "dct_title_s", "distributions"], ["ordered", "Ordered", json.dumps(links)]),
        "create",
    )
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 200
    saved = (await client.get(BASE + "/" + encode_id("ordered"), params={})).json()
    assert saved["distributions"] == links


async def test_ten_thousand_row_create_update_export(api, database_engine):
    import time

    client, _, scope, _ = await seed(api)
    source = document(
        ["id", "dct_title_s", "dct_description_sm", "gbl_resourceClass_sm"],
        *[
            [
                f"large-{i:05}",
                f"Large resource {i}",
                json.dumps(["Description " * 20]),
                json.dumps(["Maps" if i % 2 == 0 else "Datasets"]),
            ]
            for i in range(10_000)
        ],
    )
    assert len(source.encode()) > 1_000_000
    started = time.monotonic()
    body, plan = await preview(client, scope, source, "create")
    assert plan["ready"] == 10_000
    result = await client.post(BASE + "/csv/import", headers=headers(), json=body)
    assert result.status_code == 200, result.text[:500]
    assert sum(row["outcome"] == "created" for row in result.json()["items"]) == 10_000
    created = time.monotonic()
    source = document(
        ["id", "lock_version", "schema_provider_s"],
        *[[f"large-{i:05}", "1", "Updated provider"] for i in range(10_000)],
    )
    body, plan = await preview(client, scope, source)
    assert plan["ready"] == 10_000
    key = uuid4()
    result = await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    assert result.status_code == 200, result.text[:500]
    assert sum(row["outcome"] == "updated" for row in result.json()["items"]) == 10_000
    assert (
        await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    ).json() == result.json()
    updated = time.monotonic()
    from legacy_csv_export import legacy_export

    from app.resources import csv_io

    original_actor = api[1][0]

    # Warm each path, then compare repeated complete exports of identical rows.
    async def collect_copy():
        return b"".join(
            [part async for part in csv_io.export(database_engine, original_actor, q="large-")]
        )

    async def collect_legacy():
        return "".join(
            [part async for part in legacy_export(database_engine, original_actor, q="large-")]
        ).encode()

    timings = {"copy": [], "legacy": []}
    for label, collect in [("legacy", collect_legacy), ("copy", collect_copy)] * 3:
        before = time.monotonic()
        payload = await collect()
        timings[label].append(time.monotonic() - before)
        assert len(list(csv.DictReader(io.StringIO(payload.decode())))) == 10_000
    print("EXPORT_BENCHMARK " + json.dumps(timings))
    exported = await client.get(BASE + "/csv/export", params={"q": "large-"})
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert len(rows) == 10_000 and all(row["lock_version"] == "2" for row in rows)
    assert all(row["schema_provider_s"] == "Updated provider" for row in rows)
    friendly = await client.get(BASE + "/csv/export", params={"q": "large-", "format": "geomg"})
    friendly_rows = list(csv.DictReader(io.StringIO(friendly.text)))
    assert len(friendly_rows) == 10_000
    assert all(row["Provider"] == "Updated provider" for row in friendly_rows)
    _, friendly_plan = await preview(client, scope, friendly.text)
    assert all(row["outcome"] == "unchanged" for row in friendly_plan["items"])
    from app.resources import copy_export

    filters = {
        "resource_class": {"exclude": ["Maps"]},
        "provider": {"exclude": ["Unwanted provider"]},
    }
    started_export = time.monotonic()
    exported = await client.get(
        BASE + "/csv/export", params={"q": "large-", "filters": json.dumps(filters)}
    )
    elapsed_export = time.monotonic() - started_export
    assert {row["id"] for row in csv.DictReader(io.StringIO(exported.text))} == {
        f"large-{i:05}" for i in range(1, 10_000, 2)
    }
    result = (await client.get(BASE, params={"q": "large-", "filters": json.dumps(filters)})).json()
    assert result["total"] == 5000
    statement = copy_export.query(
        original_actor, csv_io.columns(original_actor), "large-", None, filters, None
    )
    async with database_engine.connect() as connection:
        compiled = statement.compile(
            dialect=connection.dialect, compile_kwargs={"render_postcompile": True}
        )
        raw = await connection.get_raw_connection()
        plans = await raw.driver_connection.fetch(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + str(compiled),
            *[compiled.params[name] for name in compiled.positiontup],
        )
        measured = plans[0][0][0]
        assert measured["Plan"]["Actual Rows"] == 5000
        print(
            "EXCLUSION_BENCHMARK "
            + json.dumps(
                {
                    "rows": 5000,
                    "export_seconds": elapsed_export,
                    "query_ms": measured["Execution Time"],
                    "shared_reads": measured["Plan"]["Shared Read Blocks"],
                }
            )
        )

    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(resources)) == 10_001
    print(
        f"10,000 rows: create preview+apply {created - started:.2f}s; "
        f"update preview+apply+replay {updated - created:.2f}s; "
        f"export {time.monotonic() - updated:.2f}s"
    )


def test_row_iterator_preserves_csv_rules_without_reading_ahead():
    from test_managing_sets import EDITOR

    from app.resources.csv_io import parse_rows

    command = CsvRequest(set_id=str(uuid4()), mode="update", csv="placeholder")
    consumed = []

    more_columns = [
        name for name in columns(EDITOR) if name not in {"id", "lock_version", "dct_title_s"}
    ]
    empty_cells = "," * len(more_columns)

    def source():
        for line in [
            '\ufeff"id",lock_version,dct_title_s,dct_description_sm__clear,'
            + ",".join(more_columns)
            + "\r\n",
            'one,1,"Title with\n',
            'newline",true' + empty_cells + "\r\n",
            "two,2,Second,false" + empty_cells + "\r\n",
        ]:
            consumed.append(line)
            yield line

    rows = parse_rows(source(), command, EDITOR)
    first = next(rows)
    assert len(consumed) == 3
    assert first["resource_id"] == "one"
    assert first["values"] == {"dct_title_s": "Title with\nnewline"}
    assert first["clear_fields"] == ["dct_description_sm"]
    assert next(rows)["resource_id"] == "two"
    with pytest.raises(StopIteration):
        next(rows)
