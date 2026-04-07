import re
import unicodedata
from typing import Any

SUGGEST_MAX_INPUT_LENGTH = 50
SUGGEST_SOURCE_FIELDS = (
    "dct_title_s",
    "dct_creator_sm",
    "dct_publisher_sm",
    "schema_provider_s",
    "dct_subject_sm",
    "dct_spatial_sm",
    "dcat_keyword_sm",
)

_YEAR_PATTERN = re.compile(r"\b(?:1[0-9]{3}|20[0-9]{2})\b\.?")
_SEPARATOR_PATTERN = re.compile(r"[\(\)\[\]\{\}/:;|]+")
_DASH_PATTERN = re.compile(r"[-\u2010-\u2015]+")
_EXTRA_PUNCTUATION_PATTERN = re.compile(r"[^\w,\s]")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_COMMA_SPACING_PATTERN = re.compile(r"\s*,\s*")


def normalize_suggestion_text(value: Any) -> str | None:
    """Normalize suggestion text for cleaner autosuggest display."""
    if value is None:
        return None

    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    if not text:
        return None

    text = text.replace("&", " and ")
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    text = _YEAR_PATTERN.sub(" ", text)
    text = text.replace("'", "")
    text = text.replace(".", "")
    text = _DASH_PATTERN.sub(" ", text)
    text = _SEPARATOR_PATTERN.sub(" ", text)
    text = _COMMA_SPACING_PATTERN.sub(", ", text)
    text = text.replace("_", " ")
    text = _EXTRA_PUNCTUATION_PATTERN.sub(" ", text)
    text = _WHITESPACE_PATTERN.sub(" ", text).strip(" ,")

    if not text or not any(char.isalnum() for char in text):
        return None

    return text[:SUGGEST_MAX_INPUT_LENGTH].rstrip(" ,") or None


def build_suggest_inputs(doc: dict[str, Any]) -> list[str]:
    """Build normalized suggestion inputs for Elasticsearch completion."""
    seen: set[str] = set()
    suggestion_inputs: list[str] = []

    for field in SUGGEST_SOURCE_FIELDS:
        value = doc.get(field)
        values = value if isinstance(value, list) else [value]

        for candidate in values:
            normalized = normalize_suggestion_text(candidate)
            if normalized and normalized not in seen:
                seen.add(normalized)
                suggestion_inputs.append(normalized)

    return suggestion_inputs


def suggestion_sort_key(
    text: str, query: str, score: float
) -> tuple[int, int, int, int, float, str]:
    """Sort exact and shorter normalized suggestions ahead of noisier ones."""
    normalized_query = normalize_suggestion_text(query) or query.strip().lower()
    return (
        0 if text == normalized_query else 1,
        0 if normalized_query and text.startswith(normalized_query) else 1,
        len(text.split()),
        len(text),
        -float(score),
        text,
    )
