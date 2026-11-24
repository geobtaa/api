import asyncio
import csv
import io
import json
from dataclasses import replace

import asyncpg
import pytest
import test_resources
from test_managing_sets import headers
from test_resource_csv import document, preview
from test_resource_editor import seed
from test_resources import BASE

api = test_resources.api
pytestmark = pytest.mark.integration


async def test_facets_results_export_share_scope_and_filter_semantics(api, database_engine):
    client, actor, scope, _ = await seed(api)
    records = [
        ["a", "Map A", '["Maps", "Maps"]', '["Wisconsin"]', "P1", "[2000]"],
        ["b", "Map B", '["Maps"]', '["Minnesota"]', "P2", "[2001]"],
        ["c", "Dataset C", '["Datasets"]', '["Wisconsin"]', "P1", "[2000,2002]"],
    ]
    body, _ = await preview(
        client,
        scope,
        document(
            [
                "id",
                "dct_title_s",
                "gbl_resourceClass_sm",
                "dct_spatial_sm",
                "schema_provider_s",
                "gbl_indexYear_im",
            ],
            *records,
        ),
        "create",
    )
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 200
    contract = (await client.get(BASE + "/facets")).json()
    assert [item["field"] for item in contract] == [
        "imports",
        "resource_class",
        "resource_type",
        "is_harvested",
        "last_harvested",
        "accrual_method",
        "accrual_periodicity",
        "website_platform",
        "endpoint_description",
        "harvest_workflow",
        "date_accessioned",
        "date_retired",
        "date_created",
        "access",
    ]
    filters = json.dumps({"resource_class": ["Maps", "Datasets"], "place": ["Wisconsin"]})
    page = (await client.get(BASE, params={"filters": filters})).json()
    assert {item["id"] for item in page["items"]} == {"a", "c"}
    exported = await client.get(BASE + "/csv/export", params={"filters": filters})
    assert {row["id"] for row in csv.DictReader(io.StringIO(exported.text))} == {"a", "c"}
    # Counts exclude the facet's own selections, retaining all other predicates.
    options = (
        await client.get(BASE + "/facets/resource_class", params={"filters": filters})
    ).json()
    assert {item["value"]: item["count"] for item in options["items"]} == {"Datasets": 1, "Maps": 1}
    all_classes = (await client.get(BASE + "/facets/resource_class")).json()
    assert next(item for item in all_classes["items"] if item["value"] == "Maps")["count"] == 2
    years = (await client.get(BASE, params={"filters": json.dumps({"year": ["2000"]})})).json()
    assert {item["id"] for item in years["items"]} == {"a", "c"}
    lc = (await client.get(BASE + "/facets/set")).json()["items"][0]
    assert lc["value"] == scope["set_id"] and lc["count"] == 4
    assert (await client.get(BASE, params={"filters": json.dumps({"set": [lc["value"]]})})).json()[
        "total"
    ] == 4
    search = await client.get(BASE + "/facets/provider", params={"term": "P", "limit": 1})
    assert search.json()["more"]
    second = await client.get(
        BASE + "/facets/provider", params={"term": "P", "limit": 1, "offset": 1}
    )
    assert second.json()["items"][0]["value"] != search.json()["items"][0]["value"]
    assert search.json()["total"] == 3
    for sort, expected in [
        ("count_desc", "P1"),
        ("count_asc", "P2"),
        ("alpha_asc", "P1"),
        ("alpha_desc", "Provider"),
    ]:
        sorted_page = (
            await client.get(
                BASE + "/facets/provider", params={"term": "P", "limit": 1, "sort": sort}
            )
        ).json()
        assert sorted_page["items"][0]["value"] == expected
        assert sorted_page["total"] == 3
    empty_page = (await client.get(BASE + "/facets/provider", params={"offset": 100})).json()
    assert empty_page["total"] == 3 and empty_page["items"] == []
    assert (await client.get(BASE + "/facets/provider", params={"term": "absent"})).json()[
        "total"
    ] == 0
    assert (
        await client.get(BASE + "/facets/provider", params={"sort": "invalid"})
    ).status_code == 422
    actor[0] = replace(actor[0], set_ids=frozenset())
    assert (await client.get(BASE + "/facets/provider")).json()["items"] == []
    assert (await client.get(BASE + "/facets/provider")).json()["total"] == 0
    assert (await client.get(BASE, params={"filters": filters})).json()["total"] == 0
    assert (
        list(
            csv.DictReader(
                io.StringIO(
                    (await client.get(BASE + "/csv/export", params={"filters": filters})).text
                )
            )
        )
        == []
    )


@pytest.mark.parametrize(
    "filters",
    [
        "null",
        "[]",
        "bad",
        '{"unknown":["x"]}',
        '{"year":["hello"]}',
        '{"year":["999999999999"]}',
        '{"provider":"x"}',
        '{"provider":[1]}',
        '{"set":["bad scope"]}',
    ],
)
async def test_invalid_facets_rejected_consistently(api, filters):
    client, _, _, _ = await seed(api)
    for path in ["", "/csv/export", "/facets/provider"]:
        assert (await client.get(BASE + path, params={"filters": filters})).status_code == 422
    assert (await client.get(BASE + "/facets/unknown")).status_code == 422


async def test_copy_producer_failure_and_early_disconnect(database_engine):
    from sqlalchemy import text

    from app.resources.copy_export import stream

    # Producer failure reaches the consumer and releases its connection.
    with pytest.raises(asyncpg.UndefinedColumnError):
        _ = [chunk async for chunk in stream(database_engine, text("SELECT missing_column"))]
    generator = stream(database_engine, text("SELECT i FROM generate_series(1,1000000) i"))
    assert await anext(generator)
    await asyncio.wait_for(generator.aclose(), timeout=5)
    async with database_engine.connect() as connection:
        assert await connection.scalar(text("SELECT 1")) == 1


async def test_include_exclude_nulls_all_and_scope(api):
    client, actors, scope, _ = await seed(api)
    body, _ = await preview(
        client,
        scope,
        document(
            ["id", "dct_title_s", "gbl_resourceClass_sm", "schema_provider_s", "gbl_indexYear_im"],
            ["both", "Both", '["Maps","Datasets"]', "P1", "[2000,2001]"],
            ["map", "Map", '["Maps"]', "P2", "[2000]"],
            ["missing", "Missing", "", "", ""],
        ),
        "create",
    )
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 200
    cases = [
        ({"provider": {"exclude": ["P1", "P2"]}}, {"missing", "editor/test"}),
        ({"resource_class": {"exclude": ["Maps"]}}, {"missing", "editor/test"}),
        ({"resource_class": {"include": ["Maps", "Datasets"], "operator": "and"}}, {"both"}),
        ({"resource_class": {"include": ["Maps"], "exclude": ["Datasets"]}}, {"map"}),
        ({"resource_class": ["Maps"], "provider": {"exclude": ["P1"]}}, {"map"}),
        ({"year": {"include": ["2000", "2001"], "operator": "and"}}, {"both"}),
        ({"year": {"exclude": ["2000"]}}, {"missing", "editor/test"}),
        ({"provider": {"include": ["P1", "P2"], "operator": "and"}}, set()),
        ({"set": {"exclude": [scope["set_id"]]}}, set()),
    ]
    for filters, expected in cases:
        params = {"filters": json.dumps(filters)}
        page = (await client.get(BASE, params=params)).json()
        assert {row["id"] for row in page["items"]} == expected, filters
        exported = await client.get(BASE + "/csv/export", params={**params, "format": "geomg"})
        assert {row["ID"] for row in csv.DictReader(io.StringIO(exported.text))} == expected
    filters = json.dumps({"resource_class": {"exclude": ["Maps"]}, "provider": ["P1"]})
    counts = (await client.get(BASE + "/facets/resource_class", params={"filters": filters})).json()
    assert {row["value"]: row["count"] for row in counts["items"]} == {"Maps": 1, "Datasets": 1}
    # Other facets' exclusions remain active in counts.
    counts = (await client.get(BASE + "/facets/provider", params={"filters": filters})).json()
    assert {row["value"] for row in counts["items"]} == {"Provider"}
    selected = await client.get(
        BASE + "/csv/export",
        params={"ids": ["both", "map"], "filters": json.dumps({"provider": {"exclude": ["P1"]}})},
    )
    assert {row["id"] for row in csv.DictReader(io.StringIO(selected.text))} == {"map"}
    actors[0] = replace(actors[0], set_ids=frozenset())
    for path in ["", "/facets/provider"]:
        assert (await client.get(BASE + path, params={"filters": filters})).json()["items"] == []
    exported = await client.get(BASE + "/csv/export", params={"filters": filters})
    assert list(csv.DictReader(io.StringIO(exported.text))) == []


@pytest.mark.parametrize(
    "selection",
    [
        {"include": "Maps"},
        {"exclude": [1]},
        {"exclude": ["Maps"], "include": ["Maps"]},
        {"operator": "xor"},
        {"unexpected": []},
        {"exclude": ["invalid"], "operator": []},
    ],
)
async def test_invalid_include_exclude(api, selection):
    client, _, _, _ = await seed(api)
    for path in ["", "/csv/export", "/facets/provider"]:
        response = await client.get(
            BASE + path, params={"filters": json.dumps({"provider": selection})}
        )
        assert response.status_code == 422


async def test_operational_facets_dates_imports_and_exports(api, database_engine):
    from datetime import date, datetime

    from sqlalchemy import update

    from app.resources.models import resources

    client, actor, scope, _ = await seed(api)
    body, _ = await preview(
        client,
        scope,
        document(["id", "dct_title_s"], ["older", "Older"], ["newer", "Newer"]),
        "create",
    )
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 200
    async with database_engine.begin() as connection:
        await connection.execute(
            update(resources)
            .where(resources.c.id == "older")
            .values(
                import_id="legacy-batch",
                b1g_isHarvested_b=False,
                b1g_dateAccessioned_s=date(2026, 9, 1),
                date_created_dtsi=datetime(2026, 9, 1),
            )
        )
        await connection.execute(
            update(resources)
            .where(resources.c.id == "newer")
            .values(
                b1g_isHarvested_b=True,
                b1g_lastHarvested_dt=datetime(2026, 9, 23, 23, 59),
                b1g_harvestWorkflow_s="py_ogm_aardvark",
                b1g_dct_accrualMethod_s="Harvest",
                b1g_dct_accrualPeriodicity_s="Monthly",
                b1g_websitePlatform_s="ArcGIS",
                b1g_dcat_endpointDescription_s="API",
                date_created_dtsi=datetime(2026, 9, 23, 23, 59),
            )
        )
    for field, value in {
        "is_harvested": "true",
        "harvest_workflow": "py_ogm_aardvark",
        "accrual_method": "Harvest",
        "accrual_periodicity": "Monthly",
        "website_platform": "ArcGIS",
        "endpoint_description": "API",
    }.items():
        response = await client.get(BASE + "/facets/" + field)
        assert response.status_code == 200, response.text
        assert any(item["value"] == value for item in response.json()["items"])
        result = await client.get(BASE, params={"filters": json.dumps({field: [value]})})
        assert [item["id"] for item in result.json()["items"]] == ["newer"]
    filters = json.dumps({"date_created": {"from": "2026-09-23", "to": "2026-09-23"}})
    result = await client.get(BASE, params={"filters": filters})
    assert [item["id"] for item in result.json()["items"]] == ["newer"]
    exported = await client.get(BASE + "/csv/export", params={"filters": filters})
    assert [row["id"] for row in csv.DictReader(io.StringIO(exported.text))] == ["newer"]
    dates = await client.get(BASE + "/facets/date_accessioned")
    assert any(item["value"] == "2026-09-01" for item in dates.json()["items"])
    batches = await client.get(BASE + "/facets/imports", params={"sort": "recent"})
    assert batches.status_code == 200, batches.text
    assert any(item["value"] == "legacy-batch" for item in batches.json()["items"])
    assert any(item["timestamp"] for item in batches.json()["items"])
    timestamps = [item["timestamp"] for item in batches.json()["items"] if item["timestamp"]]
    assert timestamps == sorted(timestamps, reverse=True)
    for item in batches.json()["items"]:
        result = await client.get(
            BASE, params={"filters": json.dumps({"imports": [item["value"]]})}
        )
        assert result.json()["total"] == item["count"]
    for invalid in [
        {"date_created": {"from": "2026-09-24", "to": "2026-09-23"}},
        {"date_created": {"to": "nonsense"}},
        {"provider": {"from": "2026-09-23"}},
        {"is_harvested": ["maybe"]},
    ]:
        assert (await client.get(BASE, params={"filters": json.dumps(invalid)})).status_code == 422
    actor[0] = replace(actor[0], set_ids=frozenset())
    assert (await client.get(BASE + "/facets/imports")).json()["items"] == []
