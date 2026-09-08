import base64
import json
import zlib

import pytest

from app.services import response_cache_codec as codec


def test_compressed_record_preserves_binary_body_and_metadata():
    record = {
        "schema": 2,
        "body_b64": base64.b64encode(bytes(range(256)) * 100).decode(),
        "headers": {"content-type": "application/octet-stream"},
        "etag": 'W/"unchanged"',
        "soft_exp": 100,
        "hard_exp": 200,
        "status": 200,
    }
    encoded = codec.encode_response_record(record, compress=True)
    assert encoded.startswith(codec.COMPRESSION_PREFIX)
    assert len(encoded) < len(json.dumps(record)) / 2
    assert codec.decode_response_record(encoded) == record


@pytest.mark.parametrize("as_text", [False, True])
def test_reads_legacy_json(as_text):
    record = {"schema": 2, "body_b64": "e30="}
    raw = json.dumps(record)
    assert codec.decode_response_record(raw if as_text else raw.encode()) == record


def test_compression_is_opt_in_and_small_records_stay_json():
    for record, enabled in [({"body": "x" * 10000}, False), ({"body": "small"}, True)]:
        assert json.loads(codec.encode_response_record(record, compress=enabled)) == record


def test_skips_values_without_meaningful_savings(monkeypatch):
    monkeypatch.setattr(codec, "MIN_COMPRESSION_BYTES", 1)
    record = {"body": "abcdef"}
    raw = codec.encode_response_record(record)
    encoded = codec.encode_response_record(record, compress=True)
    assert encoded == raw
    assert codec.decode_response_record(encoded) == record


@pytest.mark.parametrize("kind", ["truncated", "trailing", "invalid", "unknown_version"])
def test_rejects_invalid_compressed_values(kind):
    encoded = codec.encode_response_record({"body": "x" * 10000}, compress=True)
    values = {
        "truncated": encoded[:-1],
        "trailing": encoded + b"extra",
        "invalid": codec.COMPRESSION_PREFIX + b"invalid zlib",
        "unknown_version": b"BTAA-RC\x02" + encoded[len(codec.COMPRESSION_PREFIX) :],
    }
    with pytest.raises((ValueError, zlib.error)):
        codec.decode_response_record(values[kind])


def test_bounds_decompression_and_leaves_oversized_records_uncompressed(monkeypatch):
    record = {"body": "x" * 20000}
    encoded = codec.encode_response_record(record, compress=True)
    monkeypatch.setattr(codec, "MAX_DECOMPRESSED_BYTES", 10000)
    with pytest.raises(ValueError, match="size limit"):
        codec.decode_response_record(encoded)
    assert json.loads(codec.encode_response_record(record, compress=True)) == record
