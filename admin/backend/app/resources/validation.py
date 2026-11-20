"""Draft import validation; publication certification is a separate release gate."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import ARRAY, JSON, Boolean, Date, DateTime, Integer

from app.resources.models import resources

CONTRACT_ROOT = Path(__file__).resolve().parents[2] / "contracts"
VOCABULARY = json.loads((CONTRACT_ROOT / "distribution_types.json").read_text())
SCHEMA = json.loads((CONTRACT_ROOT / "ogm-aardvark-btaa.schema.json").read_text())
TYPES = {item["uri"]: item["id"] for item in VOCABULARY}
# Administrative legacy values survive solely as import evidence.
DESCRIPTIVE_B1G = {
    "b1g_image_ss",
    "b1g_geonames_sm",
    "b1g_language_sm",
    "b1g_creatorID_sm",
    "b1g_dct_conformsTo_sm",
    "b1g_dcat_spatialResolutionInMeters_sm",
    "b1g_geodcat_spatialResolutionAsText_sm",
    "b1g_dct_provenanceStatement_sm",
    "b1g_dct_provenance_sm",
    "b1g_dcat_spatialResolutionInMeters_s",
    "b1g_localCollectionLabel_sm",
}
MANAGED = {
    "lifecycle_id",
    "legacy_source_id",
    "set_id",
    "lock_version",
    "created_at",
    "updated_at",
    "created_by_actor_id",
    "publication_state",
    "import_id",
    "date_created_dtsi",
    "date_modified_dtsi",
}


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def normalize(record, *, publication_required=None, publication_labels=None):
    errors, warnings, values, distributions = [], [], {}, []
    identifier = record.get("id")
    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or len(identifier) > 512
        or any(ord(c) < 32 for c in identifier)
    ):
        errors.append("id must be a nonblank string of at most 512 characters without controls")
    if not isinstance(record.get("dct_title_s"), str) or not record["dct_title_s"].strip():
        errors.append("dct_title_s is required and must be nonblank")
    for name, value in record.items():
        # Validated against the managing Set by import planners; never persisted.
        if name == "source_id":
            continue
        if name in MANAGED or (name.startswith("b1g_") and name not in DESCRIPTIVE_B1G):
            warnings.append(
                f"{name}: retained as source evidence; application administration is separate"
            )
            continue
        if name == "dct_references_s":
            try:
                references = json.loads(value, object_pairs_hook=object_pairs)
                if not isinstance(references, dict):
                    raise ValueError("Expected a reference object")
                for uri, targets in references.items():
                    if uri not in TYPES:
                        warnings.append(f"Unknown reference URI retained in source evidence: {uri}")
                        continue
                    targets = targets if isinstance(targets, list) else [targets]
                    for target in targets:
                        label = None
                        if isinstance(target, dict) and set(target) <= {"url", "label"}:
                            label, target = target.get("label"), target.get("url")
                        if (
                            not isinstance(target, str)
                            or not target.strip()
                            or (label is not None and not isinstance(label, str))
                        ):
                            raise ValueError(
                                "References require nonblank URLs and optional string labels"
                            )
                        distributions.append(
                            {
                                "distribution_type_id": TYPES[uri],
                                "url": target,
                                "label": label,
                                "position": len(distributions),
                            }
                        )
            except ValueError, TypeError:
                errors.append("dct_references_s must encode an object of URLs or labeled URL lists")
            continue
        if name not in resources.c:
            warnings.append(f"Unknown field retained in source evidence: {name}")
            continue
        column = resources.c[name]
        try:
            if value is None:
                raise ValueError("null is not an explicit clear command; omit absent fields")
            if isinstance(column.type, ARRAY):
                item_type = int if isinstance(column.type.item_type, Integer) else str
                if not isinstance(value, list) or any(
                    type(item) is not item_type for item in value
                ):
                    raise ValueError(f"expected an array of {item_type.__name__} values")
                if item_type is int and any(not -(2**31) <= item < 2**31 for item in value):
                    raise ValueError("integer array values must fit PostgreSQL's 32-bit range")
            elif isinstance(column.type, Boolean):
                if type(value) is not bool:
                    raise ValueError("expected a boolean")
            elif isinstance(column.type, DateTime):
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if value.tzinfo is not None:
                    value = value.astimezone(timezone.utc).replace(tzinfo=None)
            elif isinstance(column.type, Date):
                value = date.fromisoformat(value)
            elif isinstance(column.type, JSON):
                if not isinstance(value, dict):
                    raise ValueError("expected an object")
            elif not isinstance(value, str):
                raise ValueError("expected a string")
            values[name] = value
        except (ValueError, TypeError, AttributeError) as exc:
            errors.append(f"{name}: {exc}")
    # A draft can preserve incomplete legacy metadata; it is never publication-ready by implication.
    missing = sorted(
        set(SCHEMA["required"] if publication_required is None else publication_required)
        - record.keys()
    )
    if missing:
        if publication_labels is None:
            warnings.append("Missing publication-schema fields: " + ", ".join(missing))
        else:
            warnings.append(
                "For publication, supply: "
                + ", ".join(publication_labels.get(k, k) for k in missing)
            )
    for name, definition in SCHEMA["properties"].items():
        if "enum" in definition and name in record and record[name] not in definition["enum"]:
            warnings.append(f"{name}: source value is outside the publication schema")
    unique = {}
    for distribution in distributions:
        key = (distribution["distribution_type_id"], distribution["url"])
        if key in unique:
            errors.append("Duplicate reference type/URL in one Resource")
        unique[key] = distribution
    return values, distributions, errors, warnings
