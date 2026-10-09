import hashlib
import io
import os
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.services import thumbnail_capture as capture
from app.services import thumbnail_policy as policy


class MemoryCache:
    def __init__(self):
        self.values = {}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value
        return True

    def delete(self, key):
        return int(self.values.pop(key, None) is not None)

    def setex(self, key, ttl, value):
        return self.set(key, value)


def png(color="red", size=(900, 600)):
    output = io.BytesIO()
    Image.new("RGBA", size, color).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def storage(monkeypatch):
    assets, links = {}, {}

    def persist(resource_id, signature, image_hash, body, mime):
        assets[image_hash] = (body, mime)
        links[(resource_id, signature)] = image_hash

    monkeypatch.setattr(capture, "_persist_thumbnail", persist)
    monkeypatch.setattr(capture, "durable_visual_asset_enabled", lambda: True)
    monkeypatch.setattr(capture, "get_durable_visual_asset", assets.get)
    monkeypatch.setattr(
        capture,
        "get_durable_visual_asset_hash_for_resource",
        lambda rid, **kw: links.get((rid, kw["source_signature"])),
    )
    return MemoryCache(), assets, links


def test_restore_after_all_caches_lost_without_provider(storage):
    cache, assets, _ = storage
    source = "https://example.org/manifest.json"
    image_hash = capture.publish_thumbnail(source, "map", png(), "image/png", cache=cache)
    cache.values.clear()
    with patch("requests.get", side_effect=AssertionError("Provider must not be contacted")):
        result = capture.capture_thumbnail(source, "map", cache=cache)
    assert result.status == "cached"
    assert result.image_hash == image_hash
    assert cache.get(f"image:{image_hash}") == assets[image_hash][0]


def test_regeneration_has_new_url_and_preserves_old_bytes(storage):
    cache, assets, _ = storage
    old_hash = capture.publish_thumbnail("source", "map", png("red"), "image/png", cache=cache)
    old_bytes = assets[old_hash][0]
    new_hash = capture.publish_thumbnail("source", "map", png("blue"), "image/png", cache=cache)
    assert old_hash != new_hash
    assert assets[old_hash][0] == old_bytes
    assert hashlib.sha256(assets[new_hash][0]).hexdigest() == new_hash
    assert capture.find_thumbnail("map", "source", cache=cache) == new_hash


def test_storage_failure_never_publishes_cache_mapping(storage, monkeypatch):
    cache, _, _ = storage

    def fail(*args):
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(capture, "_persist_thumbnail", fail)
    with pytest.raises(RuntimeError, match="Database unavailable"):
        capture.publish_thumbnail("source", "map", png(), "image/png", cache=cache)
    assert not cache.values


def test_redis_failure_does_not_lose_committed_thumbnail(storage):
    _, assets, _ = storage
    broken = MagicMock()
    broken.set.side_effect = RuntimeError("Redis unavailable")
    image_hash = capture.publish_thumbnail("source", "map", png(), "image/png", cache=broken)
    assert image_hash in assets
    assert capture.find_thumbnail("map", "source", cache=MemoryCache()) == image_hash


@pytest.mark.parametrize("bad", [b"not an image", png(size=(2048, 2048))])
def test_bad_restored_images_are_rejected(storage, bad):
    cache, assets, links = storage
    image_hash = hashlib.sha256(bad).hexdigest()
    links[("map", policy.source_signature("source"))] = image_hash
    assets[image_hash] = bad, "image/png"
    assert capture.find_thumbnail("map", "source", cache=cache) is None


def test_corrupt_redis_copy_is_repaired_from_durable_bytes(storage):
    cache, assets, _ = storage
    image_hash = capture.publish_thumbnail("source", "map", png(), "image/png", cache=cache)
    cache.values[f"image:{image_hash}"] = b"corrupt"
    assert capture.find_thumbnail("map", "source", cache=cache) == image_hash
    assert cache.get(f"image:{image_hash}") == assets[image_hash][0]


def test_policy_change_requires_new_mapping(storage, monkeypatch):
    cache, _, _ = storage
    capture.publish_thumbnail("source", "map", png(), "image/png", cache=cache)
    monkeypatch.setattr(policy, "THUMBNAIL_JPEG_QUALITY", 60)
    assert capture.find_thumbnail("map", "source", cache=cache) is None


@pytest.mark.parametrize("kind", ["remote", "manifest", "cog", "pmtiles"])
def test_all_capture_paths_publish_through_same_contract(storage, kind):
    cache, assets, _ = storage
    source = {
        "remote": "https://example.org/map.jpg",
        "manifest": "https://example.org/manifest.json",
        "cog": "https://example.org/map.tif",
        "pmtiles": "https://example.org/map.pmtiles",
    }[kind]
    response = MagicMock(content=png(), headers={"Content-Type": "image/png"})
    with (
        patch("app.tasks.worker._resolve_image_url", return_value="https://example.org/image.jpg"),
        patch("app.tasks.worker._generate_cog_thumbnail_bytes", return_value=png()),
        patch("app.tasks.worker._generate_pmtiles_thumbnail_bytes", return_value=png()),
        patch.object(capture, "requests") as requests,
        patch.object(capture, "provider_origin_cooldown_remaining", return_value=0),
        patch.object(capture, "provider_request_slot", return_value=nullcontext()),
        patch.object(capture, "record_provider_success"),
    ):
        requests.get.return_value = response
        result = capture.capture_thumbnail(source, "map", cache=cache)
    assert result.status == "generated"
    assert policy.valid_thumbnail(assets[result.image_hash][0], result.image_hash)


def test_deferred_provider_does_not_publish_success(storage):
    cache, assets, _ = storage
    with patch.object(capture, "provider_origin_cooldown_remaining", return_value=60):
        result = capture.capture_thumbnail("https://example.org/map.jpg", "map", cache=cache)
    assert result.status == "deferred"
    assert not assets


def test_noisy_png_respects_byte_budget():
    import random

    image = Image.frombytes("RGBA", (512, 512), random.Random(437).randbytes(512 * 512 * 4))
    source = io.BytesIO()
    image.save(source, format="PNG")
    content, mime = policy.normalize_thumbnail_image(source.getvalue(), "image/png")
    assert mime == "image/png"
    assert len(content) <= policy.THUMBNAIL_MAX_BYTES
    assert policy.valid_thumbnail(content, hashlib.sha256(content).hexdigest())


@pytest.mark.integration
def test_postgres_transaction_and_offline_restore(monkeypatch):
    """Run only against an explicitly supplied disposable test database."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError

    from app.services import visual_asset_cache
    from db.models import generated_visual_asset_links, generated_visual_assets

    url = os.getenv("THUMBNAIL_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set THUMBNAIL_TEST_DATABASE_URL to an isolated PostgreSQL database")
    engine = create_engine(url)
    monkeypatch.setattr(capture, "app_sync_engine", engine)
    monkeypatch.setattr(visual_asset_cache, "app_sync_engine", engine)
    monkeypatch.setattr(capture, "durable_visual_asset_enabled", lambda: True)
    monkeypatch.setattr(visual_asset_cache, "durable_visual_asset_enabled", lambda: True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS resources (id VARCHAR(255) PRIMARY KEY)"))
        conn.execute(text("INSERT INTO resources VALUES ('thumbnail-test') ON CONFLICT DO NOTHING"))
    generated_visual_assets.create(engine, checkfirst=True)
    generated_visual_asset_links.create(engine, checkfirst=True)
    cache = MemoryCache()
    image_hash = capture.publish_thumbnail(
        "source", "thumbnail-test", png(), "image/png", cache=cache
    )
    cache.values.clear()
    assert capture.find_thumbnail("thumbnail-test", "source", cache=cache) == image_hash
    # An invalid resource makes the link insert fail after the asset insert.
    invalid_cache = MemoryCache()
    body = png("green")
    normalized, _ = policy.normalize_thumbnail_image(body, "image/png")
    missing_hash = hashlib.sha256(normalized).hexdigest()
    with pytest.raises(IntegrityError):
        capture.publish_thumbnail("other", "nonexistent", body, "image/png", cache=invalid_cache)
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM generated_visual_assets WHERE asset_hash=:h"),
                {"h": missing_hash},
            ).scalar_one()
            == 0
        )
    assert not invalid_cache.values
    assert capture.invalidate_thumbnail("thumbnail-test", "source", cache=cache)
    assert capture.find_thumbnail("thumbnail-test", "source", cache=cache) is None
    assert capture.get_durable_visual_asset(image_hash) is not None
    engine.dispose()


def test_manifest_fetch_succeeds_during_redis_outage():
    from app.services.image_service import ImageService

    service = ImageService({})
    manifest = {"sequences": []}
    response = MagicMock()
    response.json.return_value = manifest
    with (
        patch.object(service.cache, "get", side_effect=RuntimeError("Redis down")),
        patch.object(service.cache, "setex", side_effect=RuntimeError("Redis down")),
        patch("app.services.image_service.requests.get", return_value=response),
    ):
        assert service._get_manifest("https://example.org/manifest.json") == manifest


def test_resume_does_not_trust_redis_only_success(storage):
    cache, assets, _ = storage
    capture.publish_thumbnail("source", "map", png(), "image/png", cache=cache)
    assets.clear()  # A restored database is missing the supposedly completed asset.
    assert capture.find_thumbnail("map", "source", cache=cache, require_durable=True) is None


@pytest.mark.asyncio
async def test_asset_delivery_survives_redis_outage():
    from app.services.image_service import ImageService

    service = ImageService({})
    body = png()
    with (
        patch.object(service.image_cache, "get", side_effect=RuntimeError("Redis down")),
        patch(
            "app.services.image_service.get_durable_visual_asset", return_value=(body, "image/png")
        ),
        patch(
            "app.services.image_service.cache_visual_asset", side_effect=RuntimeError("Redis down")
        ),
    ):
        assert await service.get_cached_image("a" * 64) == body
