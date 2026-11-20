"""Lossless single-segment URL keys; canonical metadata identity never changes."""

import base64
import binascii
import re

# Shared by API, browser and CLI builders. Reserve the collection route vocabulary.
RESERVED = frozenset(
    {
        "new",
        "import",
        "imports",
        "csv",
        "selections",
        "facets",
        "source-candidates",
        "bridge",
        "detail",
        "association",
        "associations",
        "relationships",
        "metadata",
        "preview-metadata",
        "editor-contract",
        "contract",
        "ui",
    }
)


def encode_id(identifier: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", identifier) and identifier not in RESERVED:
        return identifier
    return "~" + base64.urlsafe_b64encode(identifier.encode("utf-8")).decode("ascii").rstrip("=")


def decode_id(key: str) -> str:
    try:
        value = (
            base64.b64decode(
                key[1:] + "=" * (-len(key[1:]) % 4), altchars=b"-_", validate=True
            ).decode("utf-8")
            if key.startswith("~")
            else key
        )
    except (ValueError, binascii.Error, UnicodeError) as exc:
        raise ValueError("Invalid Resource URL key") from exc
    if not value.strip() or len(value) > 512 or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid Resource identifier")
    if encode_id(value) != key:
        raise ValueError("Use the canonical Resource URL key")
    return value
