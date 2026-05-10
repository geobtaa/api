import pytest

import app.services.durable_response_cache as durable_cache
from app.services.durable_response_cache import delete_durable_api_responses_for_tags


@pytest.mark.asyncio
async def test_delete_durable_api_responses_for_tags_chunks_large_tag_lists(monkeypatch):
    class FakeResult:
        rowcount = 2

    class FakeTransaction:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    class FakeSession:
        def __init__(self):
            self.batches = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            return FakeTransaction()

        async def execute(self, stmt):
            params = stmt.compile().params
            batch = next(value for value in params.values() if isinstance(value, list))
            self.batches.append(batch)
            return FakeResult()

    fake_session = FakeSession()
    monkeypatch.setattr(durable_cache, "API_RESPONSE_DURABLE_CACHE_STORE", "database")
    monkeypatch.setattr(durable_cache, "API_RESPONSE_DURABLE_DELETE_BATCH_SIZE", 2)
    monkeypatch.setattr(durable_cache, "async_session_factory", lambda: fake_session)

    deleted = await delete_durable_api_responses_for_tags(
        ["resource:r3", "resource:r1", "resource:r2"]
    )

    assert deleted == 4
    assert fake_session.batches == [["resource:r1", "resource:r2"], ["resource:r3"]]
