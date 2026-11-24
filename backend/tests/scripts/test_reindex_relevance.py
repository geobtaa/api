from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts import reindex_atomic as reindex


@pytest.mark.asyncio
async def test_replay_updates_members_deletes_orphans_and_checks_counts(monkeypatch):
    monkeypatch.setattr(
        reindex,
        "_source_versions",
        AsyncMock(
            return_value={
                "parent": "new",
                "member": "same",
                "inserted": "new",
            }
        ),
    )
    members = AsyncMock(return_value=["member"])
    monkeypatch.setattr(reindex, "direct_member_ids", members)
    monkeypatch.setattr(
        reindex.database,
        "fetch_all",
        AsyncMock(
            return_value=[
                {"id": "parent"},
                {"id": "member"},
                {"id": "inserted"},
            ]
        ),
    )
    prepare = AsyncMock(side_effect=lambda ids: [(rid, {"id": rid}) for rid in ids])
    monkeypatch.setattr(reindex, "_prepare_documents_for_chunk", prepare)
    bulk = AsyncMock(return_value={"errors": 0, "indexed": 3})
    monkeypatch.setattr(reindex, "_bulk_index_documents", bulk)
    es = MagicMock()
    es.indices.refresh = AsyncMock()
    es.count = AsyncMock(return_value={"count": 3})
    es.options.return_value.delete = AsyncMock()
    monkeypatch.setattr(reindex, "es", es)

    async def scan(*args, **kwargs):
        for rid in ["parent", "member", "inserted", "deleted", "transient"]:
            yield {"_id": rid}

    monkeypatch.setattr(reindex, "async_scan", scan)
    result = await reindex._reconcile_source_changes(
        "new-index",
        {"parent": "old", "member": "same", "deleted": "old"},
        published_only=False,
        use_b1g_pub_state=False,
        chunk_size=10,
        bulk_size=10,
        bulk_max_retries=0,
    )
    assert result == {"replayed": 3, "deleted": 2, "db_total": 3, "es_count": 3}
    assert set(prepare.call_args.args[0]) == {"parent", "member", "inserted"}
    assert "deleted" in members.call_args.args[0]
    assert es.options.return_value.delete.await_count == 2


@pytest.mark.asyncio
async def test_replay_refuses_cutover_on_incomplete_preparation(monkeypatch):
    monkeypatch.setattr(reindex, "_source_versions", AsyncMock(return_value={"new": "1"}))
    monkeypatch.setattr(reindex, "direct_member_ids", AsyncMock(return_value=[]))
    monkeypatch.setattr(reindex.database, "fetch_all", AsyncMock(return_value=[{"id": "new"}]))
    monkeypatch.setattr(reindex, "_prepare_documents_for_chunk", AsyncMock(return_value=[]))
    with pytest.raises(RuntimeError, match="every changed resource"):
        await reindex._reconcile_source_changes(
            "new-index",
            {},
            published_only=False,
            use_b1g_pub_state=False,
            chunk_size=10,
            bulk_size=10,
            bulk_max_retries=0,
        )
