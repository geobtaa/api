from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from app.viewers import ItemViewer

REFERENCE_NAME_TO_URI = {value: key for key, value in ItemViewer.REFERENCE_URI_TO_NAME.items()}


@dataclass
class ReferenceEntry:
    url: str
    label: Optional[str] = None


def build_effective_reference_payload(
    base_payload: Any,
    *,
    document_distributions: Sequence[Mapping[str, Any]] | None = None,
    document_downloads: Sequence[Mapping[str, Any]] | None = None,
    assets: Sequence[Mapping[str, Any]] | None = None,
    reference_type_id_to_uri: Mapping[int, str] | None = None,
    asset_key_to_uri: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    """
    Merge all known legacy/bridge reference sources into a single Aardvark payload.

    The result only emits scalar strings or arrays, never top-level objects, so it
    remains compatible with distribution sync code that reparses `dct_references_s`.
    """

    grouped = _group_reference_payload(base_payload)

    for distribution in document_distributions or []:
        uri = _reference_uri_for_distribution(distribution, reference_type_id_to_uri)
        if not uri:
            continue
        _add_entry(
            grouped,
            uri,
            ReferenceEntry(
                url=_coerce_nonempty_string(distribution.get("url")) or "",
                label=_coerce_nonempty_string(distribution.get("label")),
            ),
        )

    download_uri = REFERENCE_NAME_TO_URI.get("download", "http://schema.org/downloadUrl")
    for download in document_downloads or []:
        _add_entry(
            grouped,
            download_uri,
            ReferenceEntry(
                url=_coerce_nonempty_string(download.get("value")) or "",
                label=_coerce_nonempty_string(download.get("label")),
            ),
        )

    key_to_uri = dict(REFERENCE_NAME_TO_URI)
    if asset_key_to_uri:
        key_to_uri.update(asset_key_to_uri)

    for asset in assets or []:
        asset_key = _coerce_nonempty_string(asset.get("dct_references_uri_key"))
        if not asset_key:
            continue
        uri = key_to_uri.get(asset_key)
        if not uri:
            continue
        _add_entry(
            grouped,
            uri,
            ReferenceEntry(
                url=_extract_asset_file_url(asset) or "",
                label=_coerce_nonempty_string(asset.get("label")),
            ),
        )

    return _collapse_grouped_entries(grouped)


def serialize_reference_payload(payload: Mapping[str, Any]) -> Optional[str]:
    if not payload:
        return None
    return json.dumps(payload)


def build_distribution_rows_from_payload(
    resource_id: str,
    payload: Mapping[str, Any],
    *,
    uri_to_type_id: Mapping[str, int],
    created_at: Optional[datetime] = None,
    updated_at: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    position = 0
    created_value = created_at or datetime.now(timezone.utc).replace(tzinfo=None)
    updated_value = updated_at or created_value

    for uri, raw_value in payload.items():
        type_id = uri_to_type_id.get(uri)
        if not type_id:
            continue
        for entry in _iter_entries(raw_value):
            rows.append(
                {
                    "resource_id": resource_id,
                    "distribution_type_id": type_id,
                    "url": entry.url,
                    "label": entry.label,
                    "position": position,
                    "created_at": created_value,
                    "updated_at": updated_value,
                }
            )
            position += 1

    return rows


def build_storage_file_url(file_data: Any, *, base_url: str) -> Optional[str]:
    payload = _coerce_json_object(file_data)
    if not payload:
        return None

    storage = _coerce_nonempty_string(payload.get("storage"))
    identifier = _coerce_nonempty_string(payload.get("id"))
    if not storage or not identifier:
        return None

    return f"{base_url.rstrip('/')}/{storage}/{identifier.lstrip('/')}"


def build_asset_record_from_kithe_model(
    row: Mapping[str, Any],
    *,
    resource_id: str,
    asset_base_url: str,
) -> Optional[Dict[str, Any]]:
    file_payload = _coerce_json_object(row.get("file_data"))
    if not file_payload:
        return None

    metadata = _coerce_json_object(file_payload.get("metadata"))
    file_url = build_storage_file_url(file_payload, base_url=asset_base_url)
    if not file_url:
        return None

    return {
        "id": _coerce_nonempty_string(row.get("id")),
        "resource_id": resource_id,
        "title": _coerce_nonempty_string(row.get("title")),
        "friendlier_id": _coerce_nonempty_string(row.get("friendlier_id")),
        "parent_id": _coerce_nonempty_string(row.get("parent_id")),
        "label": _coerce_nonempty_string(row.get("label")),
        "thumbnail": bool(row.get("thumbnail")),
        "dct_references_uri_key": _coerce_nonempty_string(row.get("dct_references_uri_key")),
        "position": row.get("position") or 0,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "file_url": file_url,
        "file_mime_type": _coerce_nonempty_string(metadata.get("mime_type")),
        "file_size": metadata.get("size"),
        "file_width": metadata.get("width"),
        "file_height": metadata.get("height"),
        "file_md5": _coerce_nonempty_string(metadata.get("md5")),
        "file_sha1": _coerce_nonempty_string(metadata.get("sha1")),
        "file_sha512": _coerce_nonempty_string(metadata.get("sha512")),
    }


def _collapse_grouped_entries(grouped: Dict[str, List[ReferenceEntry]]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}

    for uri, entries in grouped.items():
        cleaned = [entry for entry in entries if entry.url]
        if not cleaned:
            continue

        if len(cleaned) == 1 and not cleaned[0].label:
            payload[uri] = cleaned[0].url
            continue

        values: List[Any] = []
        for entry in cleaned:
            if entry.label:
                values.append({"url": entry.url, "label": entry.label})
            else:
                values.append(entry.url)
        payload[uri] = values

    return payload


def _group_reference_payload(raw_payload: Any) -> Dict[str, List[ReferenceEntry]]:
    payload = _coerce_reference_mapping(raw_payload)
    grouped: Dict[str, List[ReferenceEntry]] = {}

    for uri, raw_value in payload.items():
        for entry in _iter_entries(raw_value):
            _add_entry(grouped, uri, entry)

    return grouped


def _add_entry(
    grouped: Dict[str, List[ReferenceEntry]],
    uri: str,
    entry: ReferenceEntry,
) -> None:
    if not uri or not entry.url:
        return

    entries = grouped.setdefault(uri, [])
    for existing in entries:
        if existing.url != entry.url:
            continue
        if not existing.label and entry.label:
            existing.label = entry.label
        return
    entries.append(entry)


def _iter_entries(raw_value: Any) -> Iterable[ReferenceEntry]:
    if isinstance(raw_value, list):
        for item in raw_value:
            entry = _entry_from_value(item)
            if entry:
                yield entry
        return

    entry = _entry_from_value(raw_value)
    if entry:
        yield entry


def _entry_from_value(raw_value: Any) -> Optional[ReferenceEntry]:
    if isinstance(raw_value, Mapping):
        url = _coerce_nonempty_string(raw_value.get("url"))
        if not url:
            return None
        return ReferenceEntry(url=url, label=_coerce_nonempty_string(raw_value.get("label")))

    url = _coerce_nonempty_string(raw_value)
    if not url:
        return None
    return ReferenceEntry(url=url)


def _reference_uri_for_distribution(
    distribution: Mapping[str, Any],
    reference_type_id_to_uri: Mapping[int, str] | None,
) -> Optional[str]:
    raw_type_id = distribution.get("reference_type_id") or distribution.get("distribution_type_id")
    try:
        type_id = int(raw_type_id)
    except (TypeError, ValueError):
        return None
    if not reference_type_id_to_uri:
        return None
    return reference_type_id_to_uri.get(type_id)


def _extract_asset_file_url(asset: Mapping[str, Any]) -> Optional[str]:
    file_payload = asset.get("file")
    if isinstance(file_payload, Mapping):
        file_url = _coerce_nonempty_string(file_payload.get("url"))
        if file_url:
            return file_url
    return _coerce_nonempty_string(asset.get("file_url"))


def _coerce_reference_mapping(raw_payload: Any) -> Dict[str, Any]:
    if raw_payload is None:
        return {}
    if isinstance(raw_payload, str):
        try:
            parsed = json.loads(raw_payload)
        except (json.JSONDecodeError, TypeError):
            return {}
    else:
        parsed = raw_payload
    if not isinstance(parsed, dict):
        return {}
    return {str(key): value for key, value in parsed.items()}


def _coerce_json_object(raw_value: Any) -> Dict[str, Any]:
    if isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            return {}
    else:
        parsed = raw_value
    if not isinstance(parsed, dict):
        return {}
    return dict(parsed)


def _coerce_nonempty_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
