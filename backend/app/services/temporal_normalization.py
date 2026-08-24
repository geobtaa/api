"""Helpers for normalizing OGM temporal indexing fields."""

from __future__ import annotations

import re
from typing import Any, Optional

_DATE_RANGE_START_YEAR = re.compile(r"^\s*\[?\s*(\d{1,4})(?=\D|$)")


def normalize_index_year(value: Any) -> Optional[list[int]]:
    """Normalize an OGM index-year value to the database's ``list[int]`` shape."""
    values = value if isinstance(value, (list, tuple)) else [value]
    years: list[int] = []

    for candidate in values:
        if isinstance(candidate, bool) or candidate is None:
            continue
        text = str(candidate).strip()
        if text.isdigit():
            years.append(int(text))

    return years or None


def derive_index_year(date_range: Any) -> Optional[list[int]]:
    """Derive the start year from the first OGM date-range value.

    Bridge records store editable ranges as ``YYYY-YYYY`` while canonical
    Aardvark records commonly use ``[YYYY TO YYYY]``. The legacy application
    used the start year of the first range for ``gbl_indexYear_im``.
    """
    if isinstance(date_range, (list, tuple)):
        if not date_range:
            return None
        first_value = date_range[0]
    else:
        first_value = date_range
    if first_value is None:
        return None

    match = _DATE_RANGE_START_YEAR.match(str(first_value))
    if not match:
        return None
    return [int(match.group(1))]


def normalize_or_derive_index_year(index_year: Any, date_range: Any) -> Optional[list[int]]:
    """Preserve valid supplied index years, otherwise derive the range's start year."""
    return normalize_index_year(index_year) or derive_index_year(date_range)
