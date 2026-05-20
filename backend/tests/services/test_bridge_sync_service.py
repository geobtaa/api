from __future__ import annotations

import json
import os
from datetime import datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.bridge_sync.batched import (
    queue_batched_bridge_sync,
    sync_bridge_resource_batch,
)
from app.services.bridge_sync.client import BridgePage
from app.services.bridge_sync.harvest import sync_bridge
from app.services.bridge_sync.importer import BridgeResourceImporter
from app.services.bridge_sync.repository import BridgeSyncRepository
from db.database import database
from db.migrations.create_bridge_sync_tables import create_bridge_sync_tables
from db.migrations.create_resource_aux_tables import create_resource_aux_tables
from db.models import (
    bridge_resource_state,
    bridge_sync_runs,
    resource_assets,
    resource_distributions,
    resource_downloads,
    resource_licensed_accesses,
    resources,
)


class FakeBridgeClient:
    def __init__(self, pages, records=None):
        self.pages = pages
        self.records = records or {}
        self.calls = []

    def fetch_page(self, *, cursor=None, limit=None, changed_since=None):
        call = {"cursor": cursor, "limit": limit}
        if changed_since is not None:
            call["changed_since"] = changed_since
        self.calls.append(call)
        key = cursor or "__first__"
        return self.pages[key]

    def fetch_record(self, resource_id):
        self.calls.append({"resource_id": resource_id})
        return self.records.get(resource_id)


@pytest.mark.integration
@pytest.mark.database
class TestBridgeSyncService:
    def setup_method(self):
        os.environ["BRIDGE_SEARCH_INDEX_REFRESH_ENABLED"] = "false"
        os.environ["BRIDGE_CACHE_REFRESH_ENABLED"] = "false"
        create_bridge_sync_tables()
        create_resource_aux_tables()

    @pytest.mark.asyncio(scope="session")
    async def test_queue_batched_bridge_sync_creates_parent_run_and_batch_jobs(self):
        repo = BridgeSyncRepository()
        resource_ids = [
            "bridge-batched-queue-a",
            "bridge-batched-queue-b",
            "bridge-batched-queue-c",
        ]

        if not database.is_connected:
            await database.connect()

        queued_batches = []

        def enqueue_batch(**kwargs):
            queued_batches.append(kwargs)
            return f"task-{kwargs['batch_number']}"

        try:
            await database.execute(delete(bridge_sync_runs))
            await database.execute(delete(bridge_resource_state))
            await database.execute(
                pg_insert(bridge_resource_state).values(
                    [
                        {
                            "bridge_resource_id": rid,
                        }
                        for rid in resource_ids
                    ]
                )
            )

            result = await queue_batched_bridge_sync(
                trigger="manual_batched",
                batch_size=2,
                resource_scope="bridge_active",
                max_resources=3,
                enqueue_batch=enqueue_batch,
                repo=repo,
            )

            assert result["queued_batches"] == 2
            assert len(queued_batches) == 2
            assert queued_batches[0]["resource_ids"] == [
                "bridge-batched-queue-a",
                "bridge-batched-queue-b",
            ]
            assert queued_batches[1]["resource_ids"] == ["bridge-batched-queue-c"]

            run = await repo.get_sync_run(result["bridge_id"])
            assert run is not None
            assert run["bridge_status"] == "running"
            stats = run["bridge_stats_json"]
            assert stats["scope"] == "batched_full"
            assert stats["resource_scope"] == "bridge_active"
            assert stats["total_resources"] == 3
            assert stats["total_batches"] == 2
            assert stats["batches_queued"] == 2
        finally:
            await database.execute(delete(bridge_sync_runs))
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id.in_(resource_ids)
                )
            )

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_resource_batch_imports_missing_and_finalizes_parent_run(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)
        found_id = "bridge-batched-found"
        missing_id = "bridge-batched-missing"
        resource_ids = [found_id, missing_id]
        record = {
            "id": found_id,
            "import_id": "batched-1",
            "publication_state": "published",
            "dct_title_s": "Bridge Batched Found",
            "dct_description_sm": ["Found record"],
            "dct_references_s": "[]",
        }

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id.in_(resource_ids)
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(delete(resources).where(resources.c.id.in_(resource_ids)))
            await database.execute(
                pg_insert(resources).values(
                    {
                        "id": missing_id,
                        "dct_title_s": "Bridge Batched Missing",
                        "publication_state": "published",
                        "b1g_publication_state_s": "published",
                    }
                )
            )

            run_id = await repo.create_sync_run(bridge_trigger="manual_batched")
            await repo.update_sync_run(
                bridge_id=run_id,
                bridge_stats_json={
                    "scope": "batched_full",
                    "resource_scope": "all",
                    "stage": "batching",
                    "estimated_total": 2,
                    "total_resources": 2,
                    "total_batches": 1,
                    "batches_queued": 1,
                    "batches_completed": 0,
                    "batches_failed": 0,
                    "processed": 0,
                    "imported": 0,
                    "skipped": 0,
                    "errors": 0,
                    "missing": 0,
                    "retired": 0,
                },
            )

            client = FakeBridgeClient({}, records={found_id: record})
            result = await sync_bridge_resource_batch(
                bridge_id=run_id,
                resource_ids=resource_ids,
                batch_number=1,
                total_batches=1,
                task_id="batch-task-1",
                client=client,
                importer=importer,
                repo=repo,
            )

            assert result["stats"]["processed"] == 2
            assert result["stats"]["imported"] == 1
            assert result["stats"]["missing"] == 1
            assert result["stats"]["retired"] == 1

            run = await repo.get_sync_run(run_id)
            assert run is not None
            assert run["bridge_status"] == "success"
            stats = run["bridge_stats_json"]
            assert stats["stage"] == "complete"
            assert stats["batches_completed"] == 1
            assert stats["processed"] == 2
            assert stats["imported"] == 1
            assert stats["missing"] == 1
            assert stats["retired"] == 1

            found = await database.fetch_one(
                select(resources.c.id, resources.c.dct_title_s).where(resources.c.id == found_id)
            )
            missing = await database.fetch_one(
                select(
                    resources.c.id,
                    resources.c.publication_state,
                    resources.c.b1g_publication_state_s,
                ).where(resources.c.id == missing_id)
            )
            assert found is not None
            assert found["dct_title_s"] == "Bridge Batched Found"
            assert missing is not None
            assert missing["publication_state"] == "retired"
            assert missing["b1g_publication_state_s"] == "retired"
        finally:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id.in_(resource_ids)
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(delete(resources).where(resources.c.id.in_(resource_ids)))

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_paginates_and_retires_missing_records(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        record_a = {
            "id": "bridge-sync-a",
            "import_id": "100",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync A",
            "dct_description_sm": ["Record A"],
            "dct_references_s": "[]",
            "document_downloads": [
                {
                    "label": "Download A",
                    "value": "https://example.org/a.zip",
                    "position": 1,
                }
            ],
            "document_licensed_accesses": [
                {
                    "friendlier_id": "bridge-sync-a",
                    "institution_code": "IU",
                    "access_url": "https://licenses.example.org/a",
                }
            ],
            "assets": [
                {
                    "id": "asset-a-1",
                    "friendlier_id": "a1",
                    "parent_id": "parent-a",
                    "parent_friendlier_id": "bridge-sync-a",
                    "title": "Asset A 1",
                    "label": "Thumb A",
                    "thumbnail": True,
                    "dct_references_uri_key": None,
                    "position": 0,
                    "file": {
                        "url": "https://example.org/a-thumb.jpg",
                        "metadata": {
                            "mime_type": "image/jpeg",
                            "size": 12345,
                            "width": 640,
                            "height": 480,
                            "md5": "abc",
                            "sha1": "def",
                            "sha512": "ghi",
                        },
                    },
                }
            ],
        }
        record_b = {
            "id": "bridge-sync-b",
            "import_id": "101",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync B",
            "dct_description_sm": ["Record B"],
            "dct_references_s": "[]",
        }

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id.in_(
                        ["bridge-sync-a", "bridge-sync-b"]
                    )
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(
                delete(resource_downloads).where(
                    resource_downloads.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                )
            )
            await database.execute(
                delete(resource_licensed_accesses).where(
                    resource_licensed_accesses.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                )
            )
            await database.execute(
                delete(resource_assets).where(
                    resource_assets.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                )
            )
            await database.execute(
                delete(resources).where(resources.c.id.in_(["bridge-sync-a", "bridge-sync-b"]))
            )

            first_client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record_a],
                        next_cursor="cursor-2",
                        has_more=True,
                    ),
                    "cursor-2": BridgePage(
                        data=[record_b],
                        next_cursor=None,
                        has_more=False,
                    ),
                }
            )
            first_result = await sync_bridge(
                trigger="manual",
                limit=1,
                client=first_client,
                importer=importer,
                repo=repo,
            )

            assert first_client.calls == [
                {"cursor": None, "limit": 1},
                {"cursor": "cursor-2", "limit": 1},
            ]
            assert first_result["stats"]["imported"] == 2
            assert first_result["stats"]["retired"] == 0

            second_client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record_a],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )
            second_result = await sync_bridge(
                trigger="manual",
                limit=1,
                client=second_client,
                importer=importer,
                repo=repo,
            )

            assert second_result["stats"]["imported"] == 1
            assert second_result["stats"]["missing"] == 1
            assert second_result["stats"]["retired"] == 1

            downloads_a = await database.fetch_all(
                select(resource_downloads).where(
                    resource_downloads.c.resource_id == "bridge-sync-a"
                )
            )
            assert len(downloads_a) == 1
            assert downloads_a[0]["label"] == "Download A"
            assert downloads_a[0]["value"] == "https://example.org/a.zip"

            licensed_a = await database.fetch_all(
                select(resource_licensed_accesses).where(
                    resource_licensed_accesses.c.resource_id == "bridge-sync-a"
                )
            )
            assert len(licensed_a) == 1
            assert licensed_a[0]["institution_code"] == "IU"
            assert licensed_a[0]["access_url"] == "https://licenses.example.org/a"

            assets_a = await database.fetch_all(
                select(resource_assets).where(resource_assets.c.resource_id == "bridge-sync-a")
            )
            assert len(assets_a) == 1
            assert assets_a[0]["thumbnail"] is True
            assert assets_a[0]["file_url"] == "https://example.org/a-thumb.jpg"

            row_a = await database.fetch_one(
                select(
                    resources.c.id,
                    resources.c.publication_state,
                    resources.c.b1g_publication_state_s,
                ).where(resources.c.id == "bridge-sync-a")
            )
            row_b = await database.fetch_one(
                select(
                    resources.c.id,
                    resources.c.publication_state,
                    resources.c.b1g_publication_state_s,
                    resources.c.b1g_dateRetired_s,
                ).where(resources.c.id == "bridge-sync-b")
            )
            state_b = await database.fetch_one(
                select(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id == "bridge-sync-b"
                )
            )

            assert row_a is not None
            assert row_a["publication_state"] == "published"
            assert row_a["b1g_publication_state_s"] == "published"

            assert row_b is not None
            assert row_b["publication_state"] == "retired"
            assert row_b["b1g_publication_state_s"] == "retired"
            assert row_b["b1g_dateRetired_s"] is not None

            assert state_b is not None
            assert state_b["bridge_missing_since"] is not None
            assert state_b["bridge_retired_at"] is not None
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id.in_(
                            ["bridge-sync-a", "bridge-sync-b"]
                        )
                    )
                )
                await database.execute(delete(bridge_sync_runs))
                await database.execute(
                    delete(resource_downloads).where(
                        resource_downloads.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                    )
                )
                await database.execute(
                    delete(resource_licensed_accesses).where(
                        resource_licensed_accesses.c.resource_id.in_(
                            ["bridge-sync-a", "bridge-sync-b"]
                        )
                    )
                )
                await database.execute(
                    delete(resource_assets).where(
                        resource_assets.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                    )
                )
                await database.execute(
                    delete(resources).where(resources.c.id.in_(["bridge-sync-a", "bridge-sync-b"]))
                )
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_records_estimated_total_from_last_successful_full_run(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        record = {
            "id": "bridge-sync-estimate",
            "import_id": "999",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync Estimate",
            "dct_description_sm": ["Estimate me"],
            "dct_references_s": "[]",
        }

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id == "bridge-sync-estimate"
                )
            )
            await database.execute(
                delete(resources).where(resources.c.id == "bridge-sync-estimate")
            )
            await database.execute(delete(bridge_sync_runs))

            await database.execute(
                pg_insert(bridge_sync_runs).values(
                    bridge_trigger="manual",
                    bridge_started_at=datetime(2026, 4, 19, 0, 0),
                    bridge_completed_at=datetime(2026, 4, 19, 0, 10),
                    bridge_status="success",
                    bridge_stats_json={
                        "scope": "full",
                        "stage": "complete",
                        "processed": 84000,
                        "imported": 84000,
                        "skipped": 0,
                        "errors": 0,
                    },
                )
            )

            client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )

            result = await sync_bridge(
                trigger="manual",
                limit=1,
                client=client,
                importer=importer,
                repo=repo,
            )

            assert result["stats"]["estimated_total"] == 84000
            assert result["stats"]["estimated_total_source"] == "last_successful_full_run"

            latest_run = await database.fetch_one(
                select(bridge_sync_runs).order_by(bridge_sync_runs.c.bridge_id.desc())
            )
            assert latest_run is not None
            stats = latest_run["bridge_stats_json"]
            assert stats["estimated_total"] == 84000
            assert stats["estimated_total_source"] == "last_successful_full_run"
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id == "bridge-sync-estimate"
                    )
                )
                await database.execute(
                    delete(resources).where(resources.c.id == "bridge-sync-estimate")
                )
                await database.execute(delete(bridge_sync_runs))
            finally:
                if database.is_connected:
                    await database.disconnect()

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_delta_does_not_retire_missing_records(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        record_a = {
            "id": "bridge-sync-a",
            "import_id": "100",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync A",
            "dct_description_sm": ["Record A"],
            "dct_references_s": "[]",
        }
        record_b = {
            "id": "bridge-sync-b",
            "import_id": "101",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync B",
            "dct_description_sm": ["Record B"],
            "dct_references_s": "[]",
        }

        if not database.is_connected:
            await database.connect()

        try:
            # Seed the DB with a full snapshot.
            full_client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record_a, record_b],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )
            await sync_bridge(
                trigger="manual",
                limit=10,
                client=full_client,
                importer=importer,
                repo=repo,
            )

            # Delta crawl returns only record_a since a cutoff date.
            cutoff = "2025-08-01T00:00:00Z"
            delta_client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record_a],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )
            result = await sync_bridge(
                trigger="manual",
                limit=10,
                changed_since=cutoff,
                client=delta_client,
                importer=importer,
                repo=repo,
            )

            assert result["stats"]["missing"] == 0
            assert result["stats"]["retired"] == 0
            assert result["stats"]["search_index_refresh"]["enabled"] is False
            assert result["stats"]["cache_refresh"]["enabled"] is False

            # record_b should remain published (i.e., not retired just because it
            # wasn't returned in the delta crawl).
            row_b = await database.fetch_one(
                select(
                    resources.c.id,
                    resources.c.publication_state,
                    resources.c.b1g_publication_state_s,
                    resources.c.b1g_dateRetired_s,
                ).where(resources.c.id == "bridge-sync-b")
            )
            assert row_b is not None
            assert row_b["publication_state"] == "published"
            assert row_b["b1g_publication_state_s"] == "published"
            assert row_b["b1g_dateRetired_s"] is None

            state_b = await database.fetch_one(
                select(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id == "bridge-sync-b"
                )
            )
            assert state_b is not None
            assert state_b["bridge_missing_since"] is None
            assert state_b["bridge_retired_at"] is None
            assert delta_client.calls == [{"cursor": None, "limit": 10, "changed_since": cutoff}]
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id.in_(
                            ["bridge-sync-a", "bridge-sync-b"]
                        )
                    )
                )
                await database.execute(delete(bridge_sync_runs))
                await database.execute(
                    delete(resource_downloads).where(
                        resource_downloads.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                    )
                )
                await database.execute(
                    delete(resource_licensed_accesses).where(
                        resource_licensed_accesses.c.resource_id.in_(
                            ["bridge-sync-a", "bridge-sync-b"]
                        )
                    )
                )
                await database.execute(
                    delete(resource_assets).where(
                        resource_assets.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                    )
                )
                await database.execute(
                    delete(resources).where(resources.c.id.in_(["bridge-sync-a", "bridge-sync-b"]))
                )
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_reconstructs_references_from_assets_and_downloads(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        resource_id = "bridge-sync-references"
        record = {
            "id": resource_id,
            "import_id": "102",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync References",
            "dct_description_sm": ["Reference reconstruction test"],
            "dct_references_s": {
                "http://lccn.loc.gov/sh85035852": "https://example.org/reference-guide"
            },
            "document_downloads": [
                {
                    "label": "Shapefile",
                    "value": "https://example.org/reference-shapefile.zip",
                    "position": 1,
                }
            ],
            "assets": [
                {
                    "id": "asset-ref-download",
                    "friendlier_id": "asset-ref-download",
                    "parent_id": "parent-ref",
                    "parent_friendlier_id": resource_id,
                    "title": "GeoPackage asset",
                    "label": "GeoPackage",
                    "thumbnail": False,
                    "dct_references_uri_key": "download",
                    "position": 2,
                    "file": {
                        "url": "https://example.org/reference-geopackage.zip",
                        "metadata": {
                            "mime_type": "application/zip",
                            "size": 23456,
                        },
                    },
                },
                {
                    "id": "asset-ref-pmtiles",
                    "friendlier_id": "asset-ref-pmtiles",
                    "parent_id": "parent-ref",
                    "parent_friendlier_id": resource_id,
                    "title": "PMTiles asset",
                    "label": None,
                    "thumbnail": False,
                    "dct_references_uri_key": "pmtiles",
                    "position": 3,
                    "file": {
                        "url": "https://example.org/reference.pmtiles",
                        "metadata": {
                            "mime_type": "application/vnd.pmtiles",
                            "size": 34567,
                        },
                    },
                },
            ],
        }

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id == resource_id
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(
                delete(resource_distributions).where(
                    resource_distributions.c.resource_id == resource_id
                )
            )
            await database.execute(
                delete(resource_downloads).where(resource_downloads.c.resource_id == resource_id)
            )
            await database.execute(
                delete(resource_assets).where(resource_assets.c.resource_id == resource_id)
            )
            await database.execute(delete(resources).where(resources.c.id == resource_id))

            client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )

            result = await sync_bridge(
                trigger="manual",
                limit=10,
                client=client,
                importer=importer,
                repo=repo,
            )

            assert result["stats"]["imported"] == 1

            row = await database.fetch_one(
                select(resources.c.id, resources.c.dct_references_s).where(
                    resources.c.id == resource_id
                )
            )
            assert row is not None

            references = json.loads(row["dct_references_s"])
            assert (
                references["http://lccn.loc.gov/sh85035852"]
                == "https://example.org/reference-guide"
            )
            download_entries = references["http://schema.org/downloadUrl"]
            assert {entry["url"] for entry in download_entries if isinstance(entry, dict)} == {
                "https://example.org/reference-shapefile.zip",
                "https://example.org/reference-geopackage.zip",
            }
            assert (
                references["https://github.com/protomaps/PMTiles"]
                == "https://example.org/reference.pmtiles"
            )

            distribution_rows = await database.fetch_all(
                select(
                    resource_distributions.c.url,
                    resource_distributions.c.label,
                    resource_distributions.c.position,
                )
                .where(resource_distributions.c.resource_id == resource_id)
                .order_by(resource_distributions.c.position.asc())
            )
            assert [row["url"] for row in distribution_rows] == [
                "https://example.org/reference-guide",
                "https://example.org/reference-shapefile.zip",
                "https://example.org/reference-geopackage.zip",
                "https://example.org/reference.pmtiles",
            ]

            download_rows = await database.fetch_all(
                select(resource_downloads).where(resource_downloads.c.resource_id == resource_id)
            )
            assert len(download_rows) == 1
            assert download_rows[0]["value"] == "https://example.org/reference-shapefile.zip"

            asset_rows = await database.fetch_all(
                select(resource_assets).where(resource_assets.c.resource_id == resource_id)
            )
            assert len(asset_rows) == 2
            assert {row["dct_references_uri_key"] for row in asset_rows} == {"download", "pmtiles"}
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id == resource_id
                    )
                )
                await database.execute(delete(bridge_sync_runs))
                await database.execute(
                    delete(resource_distributions).where(
                        resource_distributions.c.resource_id == resource_id
                    )
                )
                await database.execute(
                    delete(resource_downloads).where(
                        resource_downloads.c.resource_id == resource_id
                    )
                )
                await database.execute(
                    delete(resource_assets).where(resource_assets.c.resource_id == resource_id)
                )
                await database.execute(delete(resources).where(resources.c.id == resource_id))
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_prunes_deleted_distribution_urls_from_legacy_references(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        resource_id = "bridge-sync-prune-deleted-distribution"
        current_url = "https://example.org/current-download.zip"
        deleted_url = "https://example.org/deleted-download.zip"
        record = {
            "id": resource_id,
            "import_id": "103",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync Prune Deleted Distribution",
            "dct_description_sm": ["Distribution pruning test"],
            "dct_references_s": {
                "http://schema.org/downloadUrl": [
                    {"url": current_url, "label": "Current download"},
                    {"url": deleted_url, "label": "Deleted download"},
                ],
            },
            "document_distributions": [
                {
                    "reference_type_id": 8,
                    "url": current_url,
                    "label": "Current download",
                    "position": 0,
                }
            ],
        }

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id == resource_id
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(
                delete(resource_distributions).where(
                    resource_distributions.c.resource_id == resource_id
                )
            )
            await database.execute(delete(resources).where(resources.c.id == resource_id))

            client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )

            result = await sync_bridge(
                trigger="manual",
                limit=10,
                client=client,
                importer=importer,
                repo=repo,
            )

            assert result["stats"]["imported"] == 1

            row = await database.fetch_one(
                select(resources.c.id, resources.c.dct_references_s).where(
                    resources.c.id == resource_id
                )
            )
            assert row is not None
            assert json.loads(row["dct_references_s"]) == {
                "http://schema.org/downloadUrl": [{"url": current_url, "label": "Current download"}]
            }

            distribution_rows = await database.fetch_all(
                select(resource_distributions.c.url, resource_distributions.c.label).where(
                    resource_distributions.c.resource_id == resource_id
                )
            )
            assert [(row["url"], row["label"]) for row in distribution_rows] == [
                (current_url, "Current download")
            ]
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id == resource_id
                    )
                )
                await database.execute(delete(bridge_sync_runs))
                await database.execute(
                    delete(resource_distributions).where(
                        resource_distributions.c.resource_id == resource_id
                    )
                )
                await database.execute(delete(resources).where(resources.c.id == resource_id))
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_real_reported_records_ignore_stale_document_downloads(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        oneida_id = "0011D7A3-0EC0-4B1D-AF20-C055274B6DAE"
        oneida_current = "https://web.s3.wisc.edu/parcels/pre_V1/Oneida_Parcels_2014.zip"
        oneida_stale = "https://gisdata.wisc.edu/public/Oneida_Parcels_2014.zip"
        michigan_id = "002a86d5-ff04-4d71-b7d2-5b4be4d79102"
        michigan_current = (
            "https://michigan.access.preservica.com/download/file/"
            "IO_002a86d5-ff04-4d71-b7d2-5b4be4d79102"
        )
        michigan_stale = (
            "https://michiganology.org/download/file/IO_002a86d5-ff04-4d71-b7d2-5b4be4d79102"
        )
        resource_ids = [oneida_id, michigan_id]

        records = [
            {
                "id": oneida_id,
                "import_id": "662",
                "publication_state": "published",
                "dct_title_s": "Parcels Oneida County, WI 2014",
                "dct_description_sm": ["Distribution pruning test"],
                "dct_references_s": "[]",
                "document_distributions": [
                    {
                        "reference_type_id": 7,
                        "url": "https://gis.co.oneida.wi.us/gismapping/",
                    },
                    {
                        "reference_type_id": 8,
                        "url": oneida_current,
                        "label": "Geodatabase",
                    },
                    {
                        "reference_type_id": 16,
                        "url": (
                            "https://web.s3.wisc.edu/rml-gisdata/metadata/Oneida_Parcels_2014.xml"
                        ),
                    },
                ],
                "document_downloads": [
                    {
                        "label": "Geodatabase",
                        "value": oneida_stale,
                    }
                ],
            },
            {
                "id": michigan_id,
                "import_id": "664",
                "publication_state": "published",
                "dct_title_s": (
                    "30N 07W - Survey Map of Kearney Township, Antrim County [Michigan]"
                ),
                "dct_description_sm": ["Distribution pruning test"],
                "dct_references_s": "[]",
                "document_distributions": [
                    {
                        "reference_type_id": 7,
                        "url": (
                            "https://michigan.access.preservica.com/uncategorized/"
                            "IO_002a86d5-ff04-4d71-b7d2-5b4be4d79102"
                        ),
                    },
                    {
                        "reference_type_id": 8,
                        "url": michigan_current,
                        "label": "JPEG2000",
                    },
                ],
                "document_downloads": [
                    {
                        "label": "JPEG2000",
                        "value": michigan_stale,
                    }
                ],
            },
        ]

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id.in_(resource_ids)
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(
                delete(resource_distributions).where(
                    resource_distributions.c.resource_id.in_(resource_ids)
                )
            )
            await database.execute(
                delete(resource_downloads).where(resource_downloads.c.resource_id.in_(resource_ids))
            )
            await database.execute(delete(resources).where(resources.c.id.in_(resource_ids)))

            client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=records,
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )

            result = await sync_bridge(
                trigger="manual",
                limit=10,
                client=client,
                importer=importer,
                repo=repo,
            )

            assert result["stats"]["imported"] == 2

            for resource_id, current_url, stale_url in (
                (oneida_id, oneida_current, oneida_stale),
                (michigan_id, michigan_current, michigan_stale),
            ):
                resource_row = await database.fetch_one(
                    select(resources.c.dct_references_s).where(resources.c.id == resource_id)
                )
                assert resource_row is not None
                references = json.loads(resource_row["dct_references_s"])
                download_refs = references["http://schema.org/downloadUrl"]
                assert download_refs == [
                    {
                        "url": current_url,
                        "label": "Geodatabase" if resource_id == oneida_id else "JPEG2000",
                    }
                ]
                assert stale_url not in json.dumps(references)

                distribution_rows = await database.fetch_all(
                    select(resource_distributions.c.url).where(
                        resource_distributions.c.resource_id == resource_id
                    )
                )
                distribution_urls = {row["url"] for row in distribution_rows}
                assert current_url in distribution_urls
                assert stale_url not in distribution_urls

                download_rows = await database.fetch_all(
                    select(resource_downloads).where(
                        resource_downloads.c.resource_id == resource_id
                    )
                )
                assert download_rows == []
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id.in_(resource_ids)
                    )
                )
                await database.execute(delete(bridge_sync_runs))
                await database.execute(
                    delete(resource_distributions).where(
                        resource_distributions.c.resource_id.in_(resource_ids)
                    )
                )
                await database.execute(
                    delete(resource_downloads).where(
                        resource_downloads.c.resource_id.in_(resource_ids)
                    )
                )
                await database.execute(delete(resources).where(resources.c.id.in_(resource_ids)))
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_empty_nested_downloads_clear_previous_rows(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        resource_id = "bridge-sync-clear-deleted-downloads"
        stale_url = "https://example.org/stale-download.zip"
        initial_record = {
            "id": resource_id,
            "import_id": "104",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync Clear Deleted Downloads",
            "dct_description_sm": ["Nested download clearing test"],
            "dct_references_s": {},
            "document_downloads": [
                {
                    "label": "Stale download",
                    "value": stale_url,
                    "position": 0,
                }
            ],
        }
        updated_record = {
            "id": resource_id,
            "import_id": "104",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync Clear Deleted Downloads",
            "dct_description_sm": ["Nested download clearing test"],
            "dct_references_s": {
                "http://schema.org/downloadUrl": [{"url": stale_url, "label": "Stale download"}],
            },
            "document_downloads": [],
        }

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id == resource_id
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(
                delete(resource_distributions).where(
                    resource_distributions.c.resource_id == resource_id
                )
            )
            await database.execute(
                delete(resource_downloads).where(resource_downloads.c.resource_id == resource_id)
            )
            await database.execute(delete(resources).where(resources.c.id == resource_id))

            first_client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[initial_record],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )
            await sync_bridge(
                trigger="manual",
                limit=10,
                client=first_client,
                importer=importer,
                repo=repo,
            )

            seeded_downloads = await database.fetch_all(
                select(resource_downloads.c.value).where(
                    resource_downloads.c.resource_id == resource_id
                )
            )
            assert [row["value"] for row in seeded_downloads] == [stale_url]

            second_client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[updated_record],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )
            await sync_bridge(
                trigger="manual",
                limit=10,
                client=second_client,
                importer=importer,
                repo=repo,
            )

            row = await database.fetch_one(
                select(resources.c.id, resources.c.dct_references_s).where(
                    resources.c.id == resource_id
                )
            )
            assert row is not None
            assert row["dct_references_s"] is None

            downloads = await database.fetch_all(
                select(resource_downloads).where(resource_downloads.c.resource_id == resource_id)
            )
            assert downloads == []

            distribution_rows = await database.fetch_all(
                select(resource_distributions).where(
                    resource_distributions.c.resource_id == resource_id
                )
            )
            assert distribution_rows == []
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id == resource_id
                    )
                )
                await database.execute(delete(bridge_sync_runs))
                await database.execute(
                    delete(resource_distributions).where(
                        resource_distributions.c.resource_id == resource_id
                    )
                )
                await database.execute(
                    delete(resource_downloads).where(
                        resource_downloads.c.resource_id == resource_id
                    )
                )
                await database.execute(delete(resources).where(resources.c.id == resource_id))
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_resource_id_stops_on_match_without_retiring_others(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        record_a = {
            "id": "bridge-sync-a",
            "import_id": "100",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync A",
            "dct_description_sm": ["Record A"],
            "dct_references_s": "[]",
        }
        record_b = {
            "id": "bridge-sync-b",
            "import_id": "101",
            "publication_state": "published",
            "dct_title_s": "Bridge Sync B",
            "dct_description_sm": ["Record B"],
            "dct_references_s": "[]",
        }

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id.in_(
                        ["bridge-sync-a", "bridge-sync-b"]
                    )
                )
            )
            await database.execute(delete(bridge_sync_runs))
            await database.execute(
                delete(resource_distributions).where(
                    resource_distributions.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                )
            )
            await database.execute(
                delete(resource_downloads).where(
                    resource_downloads.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                )
            )
            await database.execute(
                delete(resource_assets).where(
                    resource_assets.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                )
            )
            await database.execute(
                delete(resources).where(resources.c.id.in_(["bridge-sync-a", "bridge-sync-b"]))
            )

            seed_client = FakeBridgeClient(
                {
                    "__first__": BridgePage(
                        data=[record_a, record_b],
                        next_cursor=None,
                        has_more=False,
                    )
                }
            )
            await sync_bridge(
                trigger="manual",
                limit=10,
                client=seed_client,
                importer=importer,
                repo=repo,
            )

            targeted_client = FakeBridgeClient({}, records={"bridge-sync-a": record_a})
            result = await sync_bridge(
                trigger="manual",
                limit=1,
                resource_id="bridge-sync-a",
                client=targeted_client,
                importer=importer,
                repo=repo,
            )

            assert targeted_client.calls == [
                {"resource_id": "bridge-sync-a"},
            ]
            assert result["stats"]["imported"] == 1
            assert result["stats"]["missing"] == 0
            assert result["stats"]["retired"] == 0
            assert result["stats"]["found"] is True

            row_b = await database.fetch_one(
                select(
                    resources.c.id,
                    resources.c.publication_state,
                    resources.c.b1g_publication_state_s,
                    resources.c.b1g_dateRetired_s,
                ).where(resources.c.id == "bridge-sync-b")
            )
            assert row_b is not None
            assert row_b["publication_state"] == "published"
            assert row_b["b1g_publication_state_s"] == "published"
            assert row_b["b1g_dateRetired_s"] is None

            state_b = await database.fetch_one(
                select(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id == "bridge-sync-b"
                )
            )
            assert state_b is not None
            assert state_b["bridge_missing_since"] is None
            assert state_b["bridge_retired_at"] is None
        finally:
            try:
                await database.execute(
                    delete(bridge_resource_state).where(
                        bridge_resource_state.c.bridge_resource_id.in_(
                            ["bridge-sync-a", "bridge-sync-b"]
                        )
                    )
                )
                await database.execute(delete(bridge_sync_runs))
                await database.execute(
                    delete(resource_distributions).where(
                        resource_distributions.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                    )
                )
                await database.execute(
                    delete(resource_downloads).where(
                        resource_downloads.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                    )
                )
                await database.execute(
                    delete(resource_assets).where(
                        resource_assets.c.resource_id.in_(["bridge-sync-a", "bridge-sync-b"])
                    )
                )
                await database.execute(
                    delete(resources).where(resources.c.id.in_(["bridge-sync-a", "bridge-sync-b"]))
                )
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_sync_bridge_resource_id_raises_when_record_missing(self):
        repo = BridgeSyncRepository()
        importer = BridgeResourceImporter(repo=repo)

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(delete(bridge_sync_runs))
            targeted_client = FakeBridgeClient({}, records={})

            with pytest.raises(
                RuntimeError, match="Bridge resource bridge-sync-missing was not found"
            ):
                await sync_bridge(
                    trigger="manual",
                    limit=1,
                    resource_id="bridge-sync-missing",
                    client=targeted_client,
                    importer=importer,
                    repo=repo,
                )

            assert targeted_client.calls == [{"resource_id": "bridge-sync-missing"}]
        finally:
            try:
                await database.execute(delete(bridge_sync_runs))
            except Exception:
                pass
