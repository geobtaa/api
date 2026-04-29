import logging
from collections import Counter
from unittest.mock import AsyncMock, patch

import pytest

import scripts.prime_resource_representation_cache as prime_resource_cache


class DummyProgress:
    def __init__(self, *args, **kwargs):
        self.total = kwargs.get("total")
        self.updated = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def update(self, amount):
        self.updated += amount


class FakeSessionFactory:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_configure_logging_quiet_suppresses_app_info_logs(capsys):
    service_logger = logging.getLogger("app.services.allmaps_service")
    original_level = service_logger.level

    try:
        service_logger.setLevel(logging.INFO)
        prime_resource_cache.configure_logging(verbose=False)

        service_logger.info("too noisy for cache priming")
        service_logger.warning("important cache priming warning")

        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert "too noisy for cache priming" not in output
        assert "important cache priming warning" in output
    finally:
        service_logger.setLevel(original_level)
        logging.basicConfig(level=logging.WARNING, force=True)


@pytest.mark.asyncio
async def test_prime_resource_representation_builds_core_resource_and_stores_cache():
    resource_dict = {"id": "resource-1", "dc_title_s": "Resource 1"}
    processed = {"id": "resource-1", "type": "resources"}
    session = object()

    with (
        patch.object(
            prime_resource_cache,
            "async_session_factory",
            return_value=FakeSessionFactory(session),
        ),
        patch.object(
            prime_resource_cache, "process_resource", AsyncMock(return_value=processed)
        ) as mock_process,
        patch.object(
            prime_resource_cache, "store_resource_representation", new=AsyncMock()
        ) as mock_store,
    ):
        result = await prime_resource_cache._prime_resource_representation(resource_dict)

    assert result == ("primed", "resource-1")
    mock_process.assert_awaited_once_with(
        resource_dict,
        session,
        include_similar_items=False,
    )
    mock_store.assert_awaited_once_with("resource-1", processed)


@pytest.mark.asyncio
async def test_prime_batch_skips_cached_resources_and_primes_misses():
    batch = [{"id": "cached"}, {"id": "missing"}]
    progress = DummyProgress()

    with (
        patch.object(
            prime_resource_cache,
            "get_cached_resource_representations",
            AsyncMock(return_value={"cached": {"id": "cached"}}),
        ) as mock_get_cached,
        patch.object(
            prime_resource_cache,
            "_prime_resource_representation",
            AsyncMock(return_value=("primed", "missing")),
        ) as mock_prime,
    ):
        counters = await prime_resource_cache._prime_batch(
            batch,
            force=False,
            concurrency=2,
            progress=progress,
        )

    assert counters == Counter({"cached": 1, "primed": 1})
    assert progress.updated == 2
    mock_get_cached.assert_awaited_once_with(["cached", "missing"])
    mock_prime.assert_awaited_once_with({"id": "missing"})


@pytest.mark.asyncio
async def test_prime_batch_force_rebuilds_cached_resources():
    batch = [{"id": "cached"}, {"id": "missing"}]
    progress = DummyProgress()

    with (
        patch.object(
            prime_resource_cache,
            "get_cached_resource_representations",
            AsyncMock(),
        ) as mock_get_cached,
        patch.object(
            prime_resource_cache,
            "_prime_resource_representation",
            AsyncMock(side_effect=[("primed", "cached"), ("primed", "missing")]),
        ) as mock_prime,
    ):
        counters = await prime_resource_cache._prime_batch(
            batch,
            force=True,
            concurrency=1,
            progress=progress,
        )

    assert counters == Counter({"primed": 2})
    assert progress.updated == 2
    mock_get_cached.assert_not_awaited()
    assert mock_prime.await_count == 2


@pytest.mark.asyncio
async def test_prime_resource_cache_counts_missing_explicit_resource_ids():
    fetched = [{"id": "resource-1"}]

    with (
        patch.object(prime_resource_cache, "tqdm", DummyProgress),
        patch.object(
            prime_resource_cache,
            "_fetch_resources_by_ids",
            AsyncMock(return_value=fetched),
        ) as mock_fetch,
        patch.object(
            prime_resource_cache,
            "_prime_batch",
            AsyncMock(return_value=Counter({"primed": 1})),
        ) as mock_prime_batch,
    ):
        counters = await prime_resource_cache.prime_resource_representation_cache(
            resource_ids=["resource-1", "resource-missing"],
            limit=None,
            batch_size=100,
            concurrency=4,
            force=False,
        )

    assert counters == Counter({"primed": 1, "missing": 1})
    mock_fetch.assert_awaited_once_with(["resource-1", "resource-missing"], None)
    mock_prime_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_prime_resource_cache_paginates_all_resources_until_limit():
    batch_one = [{"id": "a"}, {"id": "b"}]
    batch_two = [{"id": "c"}]

    with (
        patch.object(prime_resource_cache, "tqdm", DummyProgress),
        patch.object(prime_resource_cache, "_count_resources", AsyncMock(return_value=3)),
        patch.object(
            prime_resource_cache,
            "_fetch_resource_batch",
            AsyncMock(side_effect=[batch_one, batch_two]),
        ) as mock_fetch_batch,
        patch.object(
            prime_resource_cache,
            "_prime_batch",
            AsyncMock(side_effect=[Counter({"primed": 2}), Counter({"primed": 1})]),
        ) as mock_prime_batch,
    ):
        counters = await prime_resource_cache.prime_resource_representation_cache(
            resource_ids=[],
            limit=3,
            batch_size=2,
            concurrency=4,
            force=False,
        )

    assert counters == Counter({"primed": 3})
    assert mock_fetch_batch.await_args_list[0].args == (None, 2, 3)
    assert mock_fetch_batch.await_args_list[1].args == ("b", 2, 1)
    assert mock_prime_batch.await_count == 2


def test_main_returns_failure_status_when_any_resource_fails():
    with (
        patch.object(
            prime_resource_cache,
            "_parse_args",
            return_value=type(
                "Args",
                (),
                {
                    "resource_ids": ["bad-resource"],
                    "limit": None,
                    "batch_size": 0,
                    "concurrency": 0,
                    "force": False,
                    "verbose": False,
                },
            )(),
        ),
        patch.object(
            prime_resource_cache.asyncio,
            "run",
            return_value=Counter({"failed": 1}),
        ) as mock_run,
    ):
        result = prime_resource_cache.main()

    assert result == 1
    priming_call = mock_run.call_args.args[0]
    assert priming_call.cr_code.co_name == "prime_resource_representation_cache"
    priming_call.close()
