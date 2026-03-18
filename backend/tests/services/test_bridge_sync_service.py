from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.services.bridge_sync.client import BridgePage
from app.services.bridge_sync.harvest import sync_bridge
from app.services.bridge_sync.importer import BridgeResourceImporter
from app.services.bridge_sync.repository import BridgeSyncRepository
from db.database import database
from db.migrations.create_bridge_sync_tables import create_bridge_sync_tables
from db.models import (
    bridge_resource_state,
    bridge_sync_runs,
    resource_assets,
    resource_downloads,
    resource_licensed_accesses,
    resources,
)


class FakeBridgeClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch_page(self, *, cursor=None, limit=None):
        self.calls.append({"cursor": cursor, "limit": limit})
        key = cursor or "__first__"
        return self.pages[key]


@pytest.mark.integration
@pytest.mark.database
class TestBridgeSyncService:
    def setup_method(self):
        create_bridge_sync_tables()

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
                select(resource_downloads).where(resource_downloads.c.resource_id == "bridge-sync-a")
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
                        resource_downloads.c.resource_id.in_(
                            ["bridge-sync-a", "bridge-sync-b"]
                        )
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
                        resource_assets.c.resource_id.in_(
                            ["bridge-sync-a", "bridge-sync-b"]
                        )
                    )
                )
                await database.execute(
                    delete(resources).where(resources.c.id.in_(["bridge-sync-a", "bridge-sync-b"]))
                )
            except Exception:
                pass
