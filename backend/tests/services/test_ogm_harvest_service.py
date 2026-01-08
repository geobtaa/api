import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.services.ogm_harvest.importer import OGMResourceImporter
from app.services.ogm_harvest.repository import OGMHarvestRepository
from db.database import database
from db.migrations.create_ogm_harvest_tables import create_ogm_harvest_tables
from db.models import ogm_repos, ogm_resource_state, resources


@pytest.mark.integration
@pytest.mark.database
class TestOGMHarvestService:
    def setup_method(self):
        # Ensure tables exist in the integration DB
        create_ogm_harvest_tables()

    @pytest.mark.asyncio
    async def test_import_and_missing_tracking_and_tags(self, tmp_path):
        repo_name = "edu.stanford.purl"
        record_a = {
            "id": "test-ogm-a",
            "gbl_mdVersion_s": "Aardvark",
            "schema_provider_s": "Stanford",
            "dct_title_s": "Test A",
            "dct_description_sm": ["Desc A"],
        }
        record_b = {
            "id": "test-ogm-b",
            "gbl_mdVersion_s": "Aardvark",
            "schema_provider_s": "Stanford",
            "dct_title_s": "Test B",
            "dct_description_sm": ["Desc B"],
        }

        repo = OGMHarvestRepository()
        importer = OGMResourceImporter(repo=repo)

        if not database.is_connected:
            await database.connect()

        try:
            # Clean up any leftovers from previous runs
            await database.execute(delete(ogm_resource_state).where(ogm_resource_state.c.ogm_repo_name == repo_name))
            await database.execute(delete(ogm_repos).where(ogm_repos.c.ogm_repo_name == repo_name))
            await database.execute(delete(resources).where(resources.c.id.in_(["test-ogm-a", "test-ogm-b"])))

            # Ensure repo exists
            await repo.upsert_repo(ogm_repo_name=repo_name, ogm_enabled=True, ogm_watch_mode="weekly")

            # First run: A and B present
            run1_started = datetime.utcnow()
            stats1 = await importer.upsert_stream(
                repo_name=repo_name,
                record_stream=[(record_a, "metadata-aardvark/a.json"), (record_b, "metadata-aardvark/b.json")],
                source_commit_sha="deadbeef",
                batch_size=2,
                run_started_at=run1_started,
            )
            assert stats1["imported"] == 2

            # Verify tags injected
            row_a = await database.fetch_one(select(resources).where(resources.c.id == "test-ogm-a"))
            assert row_a is not None
            tags = row_a["b1g_adminTags_sm"] or []
            assert f"ogm_repo:{repo_name}" in tags

            # Verify no missing yet
            missing_rows = await database.fetch_all(
                select(ogm_resource_state)
                .where(ogm_resource_state.c.ogm_repo_name == repo_name)
                .where(ogm_resource_state.c.ogm_missing_since.is_not(None))
            )
            assert missing_rows == []

            # Second run: B removed, only A present
            run2_started = datetime.utcnow() + timedelta(seconds=1)
            stats2 = await importer.upsert_stream(
                repo_name=repo_name,
                record_stream=[(record_a, "metadata-aardvark/a.json")],
                source_commit_sha="feedface",
                batch_size=1,
                run_started_at=run2_started,
            )
            assert stats2["imported"] == 1

            missing_rows2 = await database.fetch_all(
                select(ogm_resource_state)
                .where(ogm_resource_state.c.ogm_repo_name == repo_name)
                .where(ogm_resource_state.c.ogm_resource_id == "test-ogm-b")
            )
            assert len(missing_rows2) == 1
            assert missing_rows2[0]["ogm_missing_since"] is not None

        finally:
            # Cleanup
            try:
                await database.execute(delete(ogm_resource_state).where(ogm_resource_state.c.ogm_repo_name == repo_name))
                await database.execute(delete(ogm_repos).where(ogm_repos.c.ogm_repo_name == repo_name))
                await database.execute(delete(resources).where(resources.c.id.in_(["test-ogm-a", "test-ogm-b"])))
            except Exception:
                pass

