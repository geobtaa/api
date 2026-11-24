"""Build the private DEC-009 legacy source-to-Lifecycle mapping artifact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

CODE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GENERIC_WEBSITE_CODE = "w00_01"
BATCH_HARVEST_RECORDS = {
    "harvest_standalone_resources",
    "harvest_standalone_websites",
}
MAPPING_FIELDS = (
    "source_system",
    "source_snapshot",
    "legacy_record_kind",
    "legacy_record_id",
    "legacy_uuid",
    "legacy_code",
    "legacy_identifier",
    "candidate_key",
    "target_lifecycle_id",
    "target_code",
    "mapping_disposition",
    "represented_by_id",
    "workflow_process",
    "confidence",
    "reason",
    "review_required",
    "review_owner",
    "reviewed_at",
    "resource_count",
    "distribution_count",
    "count_scope",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a DEC-009 mapping from read-only production exports."
    )
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--resource-counts", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def values(value: Any) -> list[str]:
    if value is None:
        return []
    source_values = value if isinstance(value, list) else [value]
    return [str(item).strip() for item in source_values if str(item).strip()]


def scalar(value: Any) -> str:
    return values(value)[0] if values(value) else ""


def join_values(value: Any) -> str:
    return "|".join(values(value))


def normalize_code(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return (
        normalized
        if 3 <= len(normalized) <= 63 and CODE_PATTERN.fullmatch(normalized)
        else ""
    )


def normalize_url(value: str) -> str:
    cleaned = value.strip()
    if not cleaned.lower().startswith(("http://", "https://")):
        return ""
    parsed = urlsplit(cleaned)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return ""
    port = parsed.port
    netloc = hostname
    if port and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{hostname}:{port}"
    path = re.sub(r"/+$", "", parsed.path) or ""
    return urlunsplit((scheme, netloc, path, parsed.query, ""))


def evidence_urls(record: dict[str, Any]) -> set[str]:
    candidates = [
        record.get("endpoint_url"),
        record.get("legacy_identifier"),
        record.get("source"),
    ]
    return {
        normalized
        for candidate in candidates
        for item in values(candidate)
        if (normalized := normalize_url(item))
    }


def aggregate_resource_counts(payload: dict[str, Any]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = defaultdict(
        lambda: {"resource_count": 0, "distribution_count": 0}
    )
    for row in payload.get("counts", []):
        code = str(row.get("legacy_code", ""))
        result[code]["resource_count"] += int(row.get("resource_count", 0))
        result[code]["distribution_count"] += int(row.get("distribution_count", 0))
    return dict(result)


def base_mapping(
    record: dict[str, Any],
    source_snapshot: str,
    count_by_code: dict[str, dict[str, int]],
) -> dict[str, Any]:
    legacy_code = scalar(record.get("legacy_code"))
    counts = count_by_code.get(legacy_code, {})
    return {
        "source_system": "geoportal_admin",
        "source_snapshot": source_snapshot,
        "legacy_record_kind": record["legacy_record_kind"],
        "legacy_record_id": record["legacy_record_id"],
        "legacy_uuid": record["legacy_uuid"],
        "legacy_code": legacy_code,
        "legacy_identifier": join_values(record.get("legacy_identifier")),
        "candidate_key": f"geoportal_admin:{record['legacy_record_kind']}:{record['legacy_record_id']}",
        "target_lifecycle_id": "",
        "target_code": "",
        "mapping_disposition": "unresolved",
        "represented_by_id": "",
        "workflow_process": scalar(record.get("harvest_workflow")),
        "confidence": "low",
        "reason": "No deterministic mapping rule applied.",
        "review_required": "yes",
        "review_owner": "GEOMG product owner",
        "reviewed_at": "",
        "resource_count": counts.get("resource_count", ""),
        "distribution_count": counts.get("distribution_count", ""),
        "count_scope": "legacy_code" if legacy_code else "unavailable",
    }


def build_mapping(
    source_payload: dict[str, Any], count_payload: dict[str, Any], source_hash: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = source_payload.get("records", [])
    websites = [row for row in records if row["legacy_record_kind"] == "website"]
    harvests = [row for row in records if row["legacy_record_kind"] == "harvest_record"]
    website_by_id = {row["legacy_record_id"]: row for row in websites}
    if len(website_by_id) != len(websites):
        raise ValueError("Website legacy_record_id values are not unique")

    code_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for website in websites:
        code_groups[scalar(website.get("legacy_code"))].append(website)

    website_urls = {row["legacy_record_id"]: evidence_urls(row) for row in websites}
    count_by_code = aggregate_resource_counts(count_payload)
    source_snapshot = (
        f"{source_payload['audit_metadata']['captured_at']};sha256={source_hash}"
    )
    mappings: list[dict[str, Any]] = []
    website_targets: dict[str, str] = {}

    for code, group in sorted(code_groups.items()):
        group = sorted(
            group, key=lambda row: (row["legacy_record_id"], row["legacy_uuid"])
        )
        generic_or_blank = not code or code == GENERIC_WEBSITE_CODE

        if generic_or_blank:
            for website in group:
                mapping = base_mapping(website, source_snapshot, count_by_code)
                target_code = normalize_code(website["legacy_record_id"])
                mapping.update(
                    {
                        "target_code": target_code,
                        "mapping_disposition": "create"
                        if target_code
                        else "unresolved",
                        "represented_by_id": website["legacy_record_id"]
                        if target_code
                        else "",
                        "confidence": "medium" if target_code else "low",
                        "reason": (
                            "Generic or blank Website code; propose the normalized unique Website ID "
                            "as the canonical code."
                            if target_code
                            else "Website ID cannot be normalized safely into a DEC-002 code."
                        ),
                        "review_required": "yes",
                        "count_scope": (
                            "shared_generic_legacy_code" if code else "unavailable"
                        ),
                    }
                )
                website_targets[website["legacy_record_id"]] = target_code
                mappings.append(mapping)
            continue

        if len(group) == 1:
            website = group[0]
            mapping = base_mapping(website, source_snapshot, count_by_code)
            target_code = normalize_code(code)
            mapping.update(
                {
                    "target_code": target_code,
                    "mapping_disposition": "create" if target_code else "unresolved",
                    "represented_by_id": website["legacy_record_id"]
                    if target_code
                    else "",
                    "confidence": "high" if target_code else "low",
                    "reason": (
                        "Unique Website code retained as the canonical Lifecycle code."
                        if target_code
                        else "Unique legacy code is not valid under DEC-002 and needs a replacement."
                    ),
                    "review_required": "no" if target_code else "yes",
                }
            )
            website_targets[website["legacy_record_id"]] = target_code
            mappings.append(mapping)
            continue

        common_urls = set.intersection(
            *(website_urls[row["legacy_record_id"]] for row in group)
        )
        if common_urls:
            primary = next(
                (row for row in group if row["legacy_record_id"] == code),
                group[0],
            )
            target_code = normalize_code(code)
            primary_represents_lifecycle = primary["legacy_record_id"] == code
            for website in group:
                is_primary = website is primary
                mapping = base_mapping(website, source_snapshot, count_by_code)
                mapping.update(
                    {
                        "target_code": target_code,
                        "mapping_disposition": "create"
                        if is_primary
                        else "merge_alias",
                        "represented_by_id": (
                            primary["legacy_record_id"]
                            if is_primary and primary_represents_lifecycle
                            else ""
                        ),
                        "confidence": "medium",
                        "reason": (
                            "Duplicate Website code and shared normalized endpoint; propose one "
                            "Lifecycle with every Website row preserved as qualified evidence."
                        ),
                        "review_required": "yes",
                        "count_scope": "shared_duplicate_legacy_code",
                    }
                )
                website_targets[website["legacy_record_id"]] = target_code
                mappings.append(mapping)
            continue

        for website in group:
            mapping = base_mapping(website, source_snapshot, count_by_code)
            target_code = normalize_code(website["legacy_record_id"])
            mapping.update(
                {
                    "target_code": target_code,
                    "mapping_disposition": "create" if target_code else "unresolved",
                    "represented_by_id": website["legacy_record_id"]
                    if target_code
                    else "",
                    "confidence": "medium" if target_code else "low",
                    "reason": (
                        "Duplicate legacy code but distinct endpoint evidence; propose separate "
                        "Lifecycles using normalized Website IDs."
                    ),
                    "review_required": "yes",
                    "count_scope": "shared_duplicate_legacy_code",
                }
            )
            website_targets[website["legacy_record_id"]] = target_code
            mappings.append(mapping)

    representatives_by_code: dict[str, set[str]] = defaultdict(set)
    for mapping in mappings:
        if mapping["target_code"] and mapping["represented_by_id"]:
            representatives_by_code[mapping["target_code"]].add(
                mapping["represented_by_id"]
            )
    target_representatives = {
        code: next(iter(representatives))
        for code, representatives in representatives_by_code.items()
        if len(representatives) == 1
    }

    for harvest in sorted(
        harvests, key=lambda row: (row["legacy_record_id"], row["legacy_uuid"])
    ):
        mapping = base_mapping(harvest, source_snapshot, count_by_code)
        identifiers = values(harvest.get("legacy_identifier"))
        id_matches = sorted({item for item in identifiers if item in website_by_id})

        if len(id_matches) == 1:
            website_id = id_matches[0]
            target_code = website_targets[website_id]
            mapping.update(
                {
                    "target_code": target_code,
                    "mapping_disposition": "attach_workflow",
                    "represented_by_id": target_representatives.get(target_code, ""),
                    "confidence": "high",
                    "reason": "Harvest identifier exactly matches one Website ID.",
                    "review_required": "no",
                }
            )
            mappings.append(mapping)
            continue

        harvest_urls = evidence_urls(harvest)
        endpoint_matches = sorted(
            website_id
            for website_id, urls in website_urls.items()
            if harvest_urls.intersection(urls)
        )
        endpoint_target_codes = {
            website_targets[website_id]
            for website_id in endpoint_matches
            if website_targets[website_id]
        }

        if endpoint_matches and len(endpoint_target_codes) == 1:
            target_code = next(iter(endpoint_target_codes))
            mapping.update(
                {
                    "target_code": target_code,
                    "mapping_disposition": "attach_workflow",
                    "represented_by_id": target_representatives.get(target_code, ""),
                    "confidence": "medium",
                    "reason": (
                        "No Website-ID match; normalized endpoint evidence resolves to one "
                        "proposed Lifecycle."
                    ),
                    "review_required": "yes",
                }
            )
            mappings.append(mapping)
            continue

        if harvest["legacy_record_id"] in BATCH_HARVEST_RECORDS:
            mapping.update(
                {
                    "mapping_disposition": "workflow_definition",
                    "confidence": "high",
                    "reason": "Shared standalone batch operation; it is not a Lifecycle identity.",
                    "review_required": "no",
                    "resource_count": "",
                    "distribution_count": "",
                    "count_scope": "not_applicable",
                }
            )
            mappings.append(mapping)
            continue

        target_code = normalize_code(
            scalar(harvest.get("legacy_code"))
        ) or normalize_code(harvest["legacy_record_id"].removeprefix("harvest_"))
        mapping.update(
            {
                "target_code": target_code,
                "mapping_disposition": "create_candidate"
                if target_code
                else "unresolved",
                "confidence": "low",
                "reason": (
                    "No Website-ID or endpoint match; review whether this is a distinct managed "
                    "set, an attachment, a merge, or historical evidence."
                ),
                "review_required": "yes",
            }
        )
        mappings.append(mapping)

    create_codes = [
        row["target_code"]
        for row in mappings
        if row["mapping_disposition"] in {"create", "create_candidate"}
        and row["target_code"]
    ]
    duplicate_targets = {
        code for code, count in Counter(create_codes).items() if count > 1
    }
    if duplicate_targets:
        for row in mappings:
            if row["target_code"] in duplicate_targets and row[
                "mapping_disposition"
            ] in {"create", "create_candidate"}:
                row["mapping_disposition"] = "unresolved"
                row["confidence"] = "low"
                row["review_required"] = "yes"
                row["reason"] += (
                    " Proposed target code collides with another create row."
                )

    mappings.sort(key=lambda row: (row["legacy_record_kind"], row["legacy_record_id"]))
    summary = {
        "source_record_count": len(records),
        "website_count": len(websites),
        "harvest_record_count": len(harvests),
        "mapping_row_count": len(mappings),
        "dispositions": dict(
            sorted(Counter(row["mapping_disposition"] for row in mappings).items())
        ),
        "confidence": dict(
            sorted(Counter(row["confidence"] for row in mappings).items())
        ),
        "review_required_count": sum(
            row["review_required"] == "yes" for row in mappings
        ),
        "unresolved_count": sum(
            row["mapping_disposition"] == "unresolved" for row in mappings
        ),
        "source_sha256": source_hash,
        "resource_counts_sha256": "",
    }
    return mappings, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=MAPPING_FIELDS, extrasaction="ignore"
        )
        writer.writeheader()
        writer.writerows(rows)
    path.chmod(0o600)


def main() -> None:
    args = parse_args()
    source_payload = load_json(args.sources)
    count_payload = load_json(args.resource_counts)
    if source_payload.get("audit_metadata", {}).get("transaction_read_only") != "on":
        raise ValueError("Source export does not prove transaction_read_only=on")
    if count_payload.get("audit_metadata", {}).get("transaction_read_only") != "on":
        raise ValueError(
            "Resource-count export does not prove transaction_read_only=on"
        )

    source_hash = sha256(args.sources)
    mappings, summary = build_mapping(source_payload, count_payload, source_hash)
    summary["resource_counts_sha256"] = sha256(args.resource_counts)
    if summary["mapping_row_count"] != summary["source_record_count"]:
        raise ValueError("Mapping output does not reconcile to the source record count")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "lifecycle-mapping-proposed.csv", mappings)
    write_csv(
        args.output_dir / "lifecycle-mapping-review-queue.csv",
        [row for row in mappings if row["review_required"] == "yes"],
    )
    summary_path = args.output_dir / "lifecycle-mapping-summary.json"
    with summary_path.open("w", encoding="utf-8") as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write("\n")
    summary_path.chmod(0o600)

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
