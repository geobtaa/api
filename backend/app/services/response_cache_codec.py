"""Versioned Redis encoding; durable records and HTTP bodies remain unchanged."""

import json
import zlib
from typing import Any

COMPRESSION_PREFIX = b"BTAA-RC\x01"
MIN_COMPRESSION_BYTES = 4096
MAX_DECOMPRESSED_BYTES = 16 * 1024 * 1024


def encode_response_record(record: dict[str, Any], *, compress: bool = False) -> bytes:
    raw = json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if compress and MIN_COMPRESSION_BYTES <= len(raw) <= MAX_DECOMPRESSED_BYTES:
        encoded = COMPRESSION_PREFIX + zlib.compress(raw, level=1)
        if len(encoded) <= len(raw) * 0.9:
            return encoded
    return raw


def decode_response_record(raw: bytes | str) -> Any:
    if isinstance(raw, bytes) and raw.startswith(COMPRESSION_PREFIX):
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(raw[len(COMPRESSION_PREFIX) :], MAX_DECOMPRESSED_BYTES + 1)
        if len(decoded) > MAX_DECOMPRESSED_BYTES:
            raise ValueError("Compressed response record exceeds size limit")
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("Invalid compressed response record")
        raw = decoded
    return json.loads(raw)
