from datetime import datetime, timedelta

import pytest
from sqlalchemy import delete, func, or_, select

from app.services.ogm_harvest.importer import OGMResourceImporter
from app.services.ogm_harvest.repository import OGMHarvestRepository
from db.database import database
from db.migrations.create_ogm_harvest_tables import create_ogm_harvest_tables
from db.models import (
    ogm_repos,
    ogm_resource_state,
    resource_distributions,
    resource_relationships,
    resources,
)


@pytest.mark.integration
@pytest.mark.database
class TestOGMHarvestService:
    def setup_method(self):
        # Ensure tables exist in the integration DB
        create_ogm_harvest_tables()

    @pytest.mark.asyncio(scope="session")
    async def test_import_and_missing_tracking_and_tags(self, tmp_path):
        # This test exercises the global `db.database.database` (databases/asyncpg).
        # The underlying asyncpg pool is bound to the event loop that created it.
        # Run this test on the session loop to avoid "Future attached to a different loop".
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
            await database.execute(
                delete(ogm_resource_state).where(ogm_resource_state.c.ogm_repo_name == repo_name)
            )
            await database.execute(delete(ogm_repos).where(ogm_repos.c.ogm_repo_name == repo_name))
            await database.execute(
                delete(resources).where(resources.c.id.in_(["test-ogm-a", "test-ogm-b"]))
            )

            # Ensure repo exists
            await repo.upsert_repo(
                ogm_repo_name=repo_name, ogm_enabled=True, ogm_watch_mode="weekly"
            )

            # First run: A and B present
            run1_started = datetime.utcnow()
            stats1 = await importer.upsert_stream(
                repo_name=repo_name,
                record_stream=[
                    (record_a, "metadata-aardvark/a.json"),
                    (record_b, "metadata-aardvark/b.json"),
                ],
                source_commit_sha="deadbeef",
                batch_size=2,
                run_started_at=run1_started,
            )
            assert stats1["imported"] == 2

            # Verify tags injected
            row_a = await database.fetch_one(
                select(
                    resources.c.id,
                    resources.c.b1g_adminTags_sm,
                    resources.c.publication_state,
                    resources.c.b1g_publication_state_s,
                ).where(resources.c.id == "test-ogm-a")
            )
            assert row_a is not None
            tags = row_a["b1g_adminTags_sm"] or []
            assert f"ogm_repo:{repo_name}" in tags
            assert row_a["publication_state"] == "published"
            assert row_a["b1g_publication_state_s"] == "published"

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
                await database.execute(
                    delete(ogm_resource_state).where(
                        ogm_resource_state.c.ogm_repo_name == repo_name
                    )
                )
                await database.execute(
                    delete(ogm_repos).where(ogm_repos.c.ogm_repo_name == repo_name)
                )
                await database.execute(
                    delete(resources).where(resources.c.id.in_(["test-ogm-a", "test-ogm-b"]))
                )
            except Exception:
                pass

    @pytest.mark.asyncio(scope="session")
    async def test_import_syncs_distributions_and_relationships(self):
        repo_name = "edu.utexas"
        parent_id = "test-ogm-parent"
        child_id = "test-ogm-child"
        distribution_uri = "urn:x-esri:serviceType:ArcGIS#FeatureLayer"

        parent_record = {
            "id": parent_id,
            "gbl_mdVersion_s": "Aardvark",
            "schema_provider_s": "UT Austin",
            "dct_title_s": "Test Parent",
            "dct_references_s": {distribution_uri: "https://example.com/parent/feature-layer"},
        }
        child_record = {
            "id": child_id,
            "gbl_mdVersion_s": "Aardvark",
            "schema_provider_s": "UT Austin",
            "dct_title_s": "Test Child",
            "dct_isPartOf_sm": [parent_id],
            "dct_references_s": {distribution_uri: "https://example.com/child/feature-layer"},
        }
        child_record_updated = {
            **child_record,
            "dct_isPartOf_sm": None,
            "dct_references_s": None,
        }

        repo = OGMHarvestRepository()
        importer = OGMResourceImporter(repo=repo)

        if not database.is_connected:
            await database.connect()

        try:
            await database.execute(
                delete(resource_relationships).where(
                    or_(
                        resource_relationships.c.subject_id.in_([parent_id, child_id]),
                        resource_relationships.c.object_id.in_([parent_id, child_id]),
                    )
                )
            )
            await database.execute(
                delete(resource_distributions).where(
                    resource_distributions.c.resource_id.in_([parent_id, child_id])
                )
            )
            await database.execute(
                delete(ogm_resource_state).where(ogm_resource_state.c.ogm_repo_name == repo_name)
            )
            await database.execute(delete(ogm_repos).where(ogm_repos.c.ogm_repo_name == repo_name))
            await database.execute(
                delete(resources).where(resources.c.id.in_([parent_id, child_id]))
            )

            await repo.upsert_repo(
                ogm_repo_name=repo_name, ogm_enabled=True, ogm_watch_mode="weekly"
            )

            first_run_started = datetime.utcnow()
            stats = await importer.upsert_stream(
                repo_name=repo_name,
                record_stream=[
                    (parent_record, "metadata-aardvark/parent.json"),
                    (child_record, "metadata-aardvark/child.json"),
                ],
                source_commit_sha="deadbeef",
                batch_size=2,
                run_started_at=first_run_started,
            )
            assert stats["imported"] == 2

            distribution_count = await database.fetch_val(
                select(func.count())
                .select_from(resource_distributions)
                .where(resource_distributions.c.resource_id.in_([parent_id, child_id]))
            )
            assert distribution_count == 2

            relationship_rows = await database.fetch_all(
                select(
                    resource_relationships.c.subject_id,
                    resource_relationships.c.predicate,
                    resource_relationships.c.object_id,
                ).where(
                    or_(
                        resource_relationships.c.subject_id.in_([parent_id, child_id]),
                        resource_relationships.c.object_id.in_([parent_id, child_id]),
                    )
                )
            )
            relationship_set = {
                (row["subject_id"], row["predicate"], row["object_id"]) for row in relationship_rows
            }
            assert (child_id, "dct:isPartOf", parent_id) in relationship_set
            assert (parent_id, "dct:hasPart", child_id) in relationship_set

            second_run_started = datetime.utcnow() + timedelta(seconds=1)
            stats_updated = await importer.upsert_stream(
                repo_name=repo_name,
                record_stream=[
                    (parent_record, "metadata-aardvark/parent.json"),
                    (child_record_updated, "metadata-aardvark/child.json"),
                ],
                source_commit_sha="feedface",
                batch_size=2,
                run_started_at=second_run_started,
            )
            assert stats_updated["imported"] == 2

            child_distribution_count = await database.fetch_val(
                select(func.count())
                .select_from(resource_distributions)
                .where(resource_distributions.c.resource_id == child_id)
            )
            assert child_distribution_count == 0

            updated_relationship_rows = await database.fetch_all(
                select(
                    resource_relationships.c.subject_id,
                    resource_relationships.c.predicate,
                    resource_relationships.c.object_id,
                ).where(
                    or_(
                        resource_relationships.c.subject_id.in_([parent_id, child_id]),
                        resource_relationships.c.object_id.in_([parent_id, child_id]),
                    )
                )
            )
            updated_relationship_set = {
                (row["subject_id"], row["predicate"], row["object_id"])
                for row in updated_relationship_rows
            }
            assert (child_id, "dct:isPartOf", parent_id) not in updated_relationship_set
            assert (parent_id, "dct:hasPart", child_id) not in updated_relationship_set

        finally:
            try:
                await database.execute(
                    delete(resource_relationships).where(
                        or_(
                            resource_relationships.c.subject_id.in_([parent_id, child_id]),
                            resource_relationships.c.object_id.in_([parent_id, child_id]),
                        )
                    )
                )
                await database.execute(
                    delete(resource_distributions).where(
                        resource_distributions.c.resource_id.in_([parent_id, child_id])
                    )
                )
                await database.execute(
                    delete(ogm_resource_state).where(
                        ogm_resource_state.c.ogm_repo_name == repo_name
                    )
                )
                await database.execute(
                    delete(ogm_repos).where(ogm_repos.c.ogm_repo_name == repo_name)
                )
                await database.execute(
                    delete(resources).where(resources.c.id.in_([parent_id, child_id]))
                )
            except Exception:
                pass
