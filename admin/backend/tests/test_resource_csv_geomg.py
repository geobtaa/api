"""Synthetic GEOMGv1 examples; never copy staff exports into the repository."""

import csv
import io
import json
from uuid import uuid4

import pytest
import test_resources
from test_managing_sets import headers
from test_resource_csv import document, preview
from test_resource_editor import seed
from test_resources import BASE

from app.url_ids import encode_id

api = test_resources.api
pytestmark = pytest.mark.integration


async def test_primary_import_evidence_and_copy_roundtrip(api):
    client, _, scope, _ = await seed(api)
    source = document(
        [
            "ID",
            "Title",
            "Description",
            "Resource Class",
            "Index Year",
            "Georeferenced",
            "Provenance",
            "Publication State",
            "Harvest Workflow",
            "Admin Note",
        ],
        [
            "primary/example",
            'Synthetic, quoted "map"',
            "First paragraph\ncontinued|Second",
            "Maps|Datasets",
            "1900|2000",
            "false",
            "Source statement",
            "published",
            "legacy-workflow",
            "Synthetic internal note",
        ],
    )
    body, plan = await preview(client, scope, source, "create")
    assert plan["ready"] == 1
    assert any("Admin Note" in item for item in plan["items"][0]["warnings"])
    response = await client.post(BASE + "/csv/import", headers=headers(uuid4()), json=body)
    assert response.status_code == 200, response.text
    saved = (await client.get(BASE + "/" + encode_id("primary/example"), params={})).json()
    assert saved["metadata"]["b1g_dct_provenance_sm"] == ["Source statement"]
    assert saved["source_record"]["geomg_v1_source"]["Publication State"] == "published"
    assert saved["publication_state"] == "draft"
    exported = await client.get(BASE + "/csv/export", params={"format": "geomg"})
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    row = next(row for row in rows if row["ID"] == "primary/example")
    assert list(row)[:3] == ["Title", "Alternative Title", "Description"]
    assert row["Resource Class"] == "Maps|Datasets"
    assert row["Index Year"] == "1900|2000"
    assert row["Georeferenced"] == "false"
    assert "Admin Note" not in row
    _, result = await preview(client, scope, exported.text)
    assert all(item["outcome"] == "unchanged" for item in result["items"])
    template = await client.get(BASE + "/csv/template?format=geomg")
    assert next(csv.reader(io.StringIO(template.text))) == list(row)


@pytest.mark.parametrize(
    "values",
    [
        [],
        ["A|B", "C"],
        ["[literal]"],
        [""],
        ["A", ""],
        ["A", " ", "B"],
        ["=1+1", "'quoted"],
        ["Back\\slash", "Unicode café"],
    ],
)
async def test_lossless_friendly_lists(api, values):
    client, _, scope, _ = await seed(api)
    source = document(
        ["id", "lock_version", "dct_description_sm"], ["editor/test", "1", json.dumps(values)]
    )
    body, _ = await preview(client, scope, source)
    assert (
        await client.post(BASE + "/csv/import", headers=headers(uuid4()), json=body)
    ).status_code == 200
    exported = await client.get(BASE + "/csv/export?format=geomg")
    _, plan = await preview(client, scope, exported.text)
    assert plan["items"][0]["outcome"] == "unchanged", plan


async def test_friendly_validation_and_optimistic_conflicts(api):
    client, _, scope, _ = await seed(api)
    for names, values in [(["ID", "id"], ["a", "a"]), (["ID", "Unknown"], ["a", "x"])]:
        response = await client.post(
            BASE + "/csv/preview",
            headers=headers(),
            json={
                "set_id": scope["set_id"],
                "mode": "create",
                "csv": document(names, values),
            },
        )
        assert response.status_code == 422
    for names, values in [
        (["Description"], ["A||B"]),
        (["Index Year"], ["no year"]),
        (["Title"], ["New title"]),
    ]:
        _, plan = await preview(client, scope, document(["ID", *names], ["editor/test", *values]))
        assert plan["items"][0]["outcome"] == "invalid"
    body, plan = await preview(
        client,
        scope,
        document(["ID", "Lock Version", "Provider__clear"], ["editor/test", "1", "true"]),
    )
    assert plan["ready"] == 1
    assert (
        await client.post(BASE + "/csv/import", headers=headers(uuid4()), json=body)
    ).status_code == 200
    assert (
        await client.post(BASE + "/csv/import", headers=headers(uuid4()), json=body)
    ).status_code == 409


async def test_large_place_array_and_explicit_empty_subject_round_trip(api):
    client, _, scope, _ = await seed(api)
    places = [f"Place {i}" for i in range(2000)]
    source = document(
        ["ID", "Title", "Spatial Coverage", "dct_subject_sm"],
        ["large-places", "Many places", "|".join(places), '["A","","B"]'],
    )
    body, plan = await preview(client, scope, source, "create")
    assert plan["ready"] == 1
    assert (
        await client.post(BASE + "/csv/import", headers=headers(uuid4()), json=body)
    ).status_code == 200
    detail = (await client.get(BASE + "/" + encode_id("large-places"), params={})).json()
    assert detail["metadata"]["dct_spatial_sm"] == places
    assert detail["metadata"]["dct_subject_sm"] == ["A", "", "B"]
    exported = await client.get(BASE + "/csv/export?format=geomg")
    _, plan = await preview(client, scope, exported.text)
    assert all(row["outcome"] == "unchanged" for row in plan["items"]), [
        (r["outcome"], r["errors"], list(r["changes"])) for r in plan["items"]
    ]


@pytest.mark.parametrize("format", ["technical", "geomg", "gbl-admin"])
async def test_complete_resource_header_required_before_any_row_can_be_imported(api, format):
    from app.resources import csv_format

    client, _, scope, _ = await seed(api)
    if format == "gbl-admin":
        header = [*csv_format.PRIMARY, *sorted(csv_format.EVIDENCE)]
    else:
        template = await client.get(BASE + "/csv/template", params={"format": format})
        header = next(csv.reader(io.StringIO(template.text)))
    header.reverse()
    values = {"id": "header-test", "dct_title_s": "Example map"}
    row = [values.get(csv_format.field_name(name), "") for name in header]
    original = {"csv": document(header, row), "set_id": scope["set_id"]}
    accepted = await client.post(BASE + "/csv/preview", headers=headers(), json=original)
    assert accepted.status_code == 200 and accepted.json()["ready"] == 1

    missing = {
        "technical": ["id", "schema_provider_s"],
        "geomg": ["Provider", "Distributions"],
        "gbl-admin": ["Provider", "Admin Note"],
    }[format]
    keep = [i for i, heading in enumerate(header) if heading not in missing]
    incomplete = {**original, "csv": document([header[i] for i in keep], [row[i] for i in keep])}
    for endpoint in ("preview", "import"):
        body = dict(incomplete)
        if endpoint == "import":
            body.update(confirmed=True, preview_hash=accepted.json()["preview_hash"])
        result = await client.post(BASE + "/csv/" + endpoint, headers=headers(), json=body)
        assert result.status_code == 422
        error = result.json()["detail"]
        assert error["code"] == "invalid_csv"
        assert "Missing columns" in error["message"]
        assert all(name in error["message"] for name in missing)
    assert (await client.get(BASE + "/header-test")).status_code == 404
