import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
FIXTURES_ROOT = BACKEND_ROOT / "data" / "fixtures"
GEOMG_FIXTURES_ROOT = REPO_ROOT / "geomg" / "fixtures"
HARVEST_RECORDS_ROOT = GEOMG_FIXTURES_ROOT / "harvest-records"
GEOMG_RESOURCES_ROOT = GEOMG_FIXTURES_ROOT / "resources"

FIXTURE_FILES = (
    "gbl_fixtures_data/actual-point1.json",
    "gbl_fixtures_data/public_direct_download.json",
    "gbl_fixtures_data/restricted-line.json",
    "gbl_fixtures_data/multiple-downloads.json",
    "gbl_fixtures_data/iiif-eastern-hemisphere.json",
    "gbl_fixtures_data/metadata_no_provider.json",
    "btaa_fixtures_data/018b1db0-726a-4727-af0a-5c7e18783ace.json",
    "btaa_fixtures_data/999-0011-california.json",
    "btaa_fixtures_data/88be737b-4fea-4f23-9433-a008ed6b18b5.json",
    "btaa_fixtures_data/b1g_BtbnzIbFhMiC.json",
)


REFERENCE_LABELS = {
    "http://schema.org/downloadUrl": "Download",
    "http://schema.org/url": "Landing page",
    "http://schema.org/thumbnailUrl": "Thumbnail",
    "http://iiif.io/api/presentation#manifest": "IIIF manifest",
    "http://www.isotc211.org/schemas/2005/gmd/": "ISO metadata",
    "http://www.loc.gov/mods/v3": "MODS metadata",
    "http://www.opengis.net/def/serviceType/ogc/wfs": "WFS",
    "http://www.opengis.net/def/serviceType/ogc/wms": "WMS",
}

HARVEST_FIELD_ORDER = (
    "geomg_id_s",
    "b1g_code_s",
    "dct_title_s",
    "b1g_harvestWorkflow_s",
    "b1g_websitePlatform_s",
    "b1g_dct_accrualMethod_s",
    "b1g_dct_accrualPeriodicity_s",
    "b1g_lastHarvested_dt",
    "b1g_dateAccessioned_dt",
    "b1g_dcat_endpointDescription_s",
    "b1g_dcat_endpointURL_s",
    "dct_subject_sm",
    "dct_description_sm",
    "b1g_dct_provenance_sm",
    "b1g_adminNote_sm",
    "b1g_adminTags_sm",
    "dct_identifier_sm",
    "date_created_dtsi",
    "date_modified_dtsi",
    "gbl_mdVersion_s",
)

HARVEST_OVERVIEW_FIELDS = (
    "dct_title_s",
    "geomg_id_s",
    "b1g_code_s",
    "dct_subject_sm",
    "dct_description_sm",
    "b1g_dct_provenance_sm",
    "b1g_adminNote_sm",
    "b1g_adminTags_sm",
    "dct_identifier_sm",
)

HARVEST_WORKFLOW_FIELDS = (
    "b1g_harvestWorkflow_s",
    "b1g_websitePlatform_s",
    "b1g_dct_accrualMethod_s",
    "b1g_dct_accrualPeriodicity_s",
    "b1g_lastHarvested_dt",
    "b1g_dateAccessioned_dt",
    "b1g_dcat_endpointDescription_s",
    "b1g_dcat_endpointURL_s",
)

HARVEST_ADMIN_FIELDS = (
    "date_created_dtsi",
    "date_modified_dtsi",
    "gbl_mdVersion_s",
)

HARVEST_FIELD_LABELS = {
    "associated_resource_count": "Associated resources",
    "geomg_id_s": "GEOMG ID",
    "b1g_code_s": "B1G code",
    "dct_title_s": "Title",
    "b1g_harvestWorkflow_s": "Harvest workflow",
    "b1g_websitePlatform_s": "Website platform",
    "b1g_dct_accrualMethod_s": "Accrual method",
    "b1g_dct_accrualPeriodicity_s": "Accrual periodicity",
    "b1g_lastHarvested_dt": "Last harvested",
    "b1g_dateAccessioned_dt": "Date accessioned",
    "b1g_dcat_endpointDescription_s": "Endpoint type",
    "b1g_dcat_endpointURL_s": "Endpoint URL",
    "dct_subject_sm": "Subject",
    "dct_description_sm": "Description",
    "b1g_dct_provenance_sm": "Provenance",
    "b1g_adminNote_sm": "Admin note",
    "b1g_adminTags_sm": "Admin tags",
    "dct_identifier_sm": "Identifier",
    "date_created_dtsi": "Created",
    "date_modified_dtsi": "Modified",
    "gbl_mdVersion_s": "Metadata version",
}


@dataclass(frozen=True)
class AdminImport:
    source: str
    imported_at: str
    record_count: int
    status: str
    notes: str


class AdminFixtureStore:
    """Small in-memory data layer for the standalone GEOMG prototype."""

    def __init__(self) -> None:
        self._resources = [
            _normalize_record(path_and_index) for path_and_index in _fixture_paths()
        ]
        self._resource_map = {resource["id"]: resource for resource in self._resources}
        self._prototype_resources = [
            _normalize_prototype_resource(path)
            for path in _json_paths(GEOMG_RESOURCES_ROOT)
        ]
        self._resource_counts_by_code = _count_by_code(self._prototype_resources)
        self._harvest_records = [
            _normalize_harvest_record(
                path,
                self._resource_counts_by_code,
                self._prototype_resources,
            )
            for path in _json_paths(HARVEST_RECORDS_ROOT)
        ]
        self._harvest_record_map = {
            record["id"]: record for record in self._harvest_records
        }
        self._harvest_columns = _harvest_columns(self._harvest_records)
        self.imports = [
            AdminImport(
                source="Existing BTAA and GBL fixture JSON",
                imported_at="2026-06-29 09:00",
                record_count=len(self._resources),
                status="Loaded for local prototype",
                notes="In-memory seed data; no writes are persisted.",
            )
        ]

    def list_resources(
        self,
        query: str | None = None,
        resource_class: str | None = None,
        resource_type: str | None = None,
        provider: str | None = None,
        publisher: str | None = None,
        publication_state: str | None = None,
    ) -> list[dict[str, Any]]:
        resources = self._resources
        if query:
            needle = query.strip().lower()
            resources = [
                resource
                for resource in resources
                if needle in resource["id"].lower()
                or needle in resource["title"].lower()
                or needle in resource["resource_class"].lower()
                or needle in resource["resource_type"].lower()
                or needle in resource["provider"].lower()
                or needle in resource["publisher"].lower()
                or needle in resource["publication_state"].lower()
            ]
        if resource_class:
            resources = [
                resource
                for resource in resources
                if resource["resource_class"].lower() == resource_class.lower()
            ]
        if resource_type:
            resources = [
                resource
                for resource in resources
                if resource["resource_type"].lower() == resource_type.lower()
            ]
        if provider:
            resources = [
                resource
                for resource in resources
                if resource["provider"].lower() == provider.lower()
            ]
        if publisher:
            resources = [
                resource
                for resource in resources
                if resource["publisher"].lower() == publisher.lower()
            ]
        if publication_state:
            resources = [
                resource
                for resource in resources
                if resource["publication_state"].lower() == publication_state.lower()
            ]
        return resources

    def get_resource(self, resource_id: str) -> dict[str, Any] | None:
        return self._resource_map.get(resource_id)

    def list_harvest_records(self, query: str | None = None) -> list[dict[str, Any]]:
        if not query:
            return self._harvest_records
        needle = query.strip().lower()
        return [
            record
            for record in self._harvest_records
            if any(needle in value.lower() for value in record["fields"].values())
        ]

    def get_harvest_record(self, harvest_id: str) -> dict[str, Any] | None:
        return self._harvest_record_map.get(harvest_id)

    @property
    def harvest_columns(self) -> list[dict[str, str]]:
        return self._harvest_columns

    @property
    def providers(self) -> list[str]:
        return sorted(
            {
                resource["provider"]
                for resource in self._resources
                if resource["provider"]
            }
        )

    @property
    def publishers(self) -> list[str]:
        return sorted(
            {
                resource["publisher"]
                for resource in self._resources
                if resource["publisher"]
            }
        )

    @property
    def resource_classes(self) -> list[str]:
        return sorted(
            {
                resource["resource_class"]
                for resource in self._resources
                if resource["resource_class"]
            }
        )

    @property
    def resource_types(self) -> list[str]:
        return sorted(
            {
                resource["resource_type"]
                for resource in self._resources
                if resource["resource_type"]
            }
        )

    @property
    def publication_states(self) -> list[str]:
        return ["Draft", "Published", "Unpublished"]


def _fixture_paths() -> list[tuple[Path, int]]:
    paths = []
    for index, relative_path in enumerate(FIXTURE_FILES):
        path = FIXTURES_ROOT / relative_path
        if path.exists():
            paths.append((path, index))
    return paths


def _json_paths(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def _load_raw_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _count_by_code(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        code = _first(record.get("b1g_code_s"))
        if code:
            counts[code] = counts.get(code, 0) + 1
    return counts


def _normalize_prototype_resource(path: Path) -> dict[str, Any]:
    raw = _load_raw_json(path)
    return {
        "id": _first(raw.get("geomg_id_s"), fallback=path.stem),
        "code": _first(raw.get("b1g_code_s")),
        "title": _first(raw.get("dct_title_s"), fallback=path.stem),
        "resource_class": _join(raw.get("gbl_resourceClass_sm")),
        "resource_type": _join(raw.get("gbl_resourceType_sm")),
        "provider": _first(raw.get("schema_provider_s")),
        "publication_state": _publication_state(raw),
        "fixture_path": str(path.relative_to(REPO_ROOT)),
    }


def _normalize_harvest_record(
    path: Path,
    resource_counts_by_code: dict[str, int],
    prototype_resources: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = _load_raw_json(path)
    code = _first(raw.get("b1g_code_s"))
    fields = {
        key: _display_value(value) for key, value in raw.items() if _filled(value)
    }
    for hidden_field in (
        "b1g_publication_state_s",
        "gbl_resourceClass_sm",
        "dct_accessRights_s",
        "gbl_suppressed_b",
    ):
        fields.pop(hidden_field, None)
    fields["associated_resource_count"] = str(resource_counts_by_code.get(code, 0))
    return {
        "id": _first(raw.get("geomg_id_s"), fallback=path.stem),
        "code": code,
        "title": _first(raw.get("dct_title_s"), fallback=path.stem),
        "fields": fields,
        "overview_fields": _harvest_field_group(fields, HARVEST_OVERVIEW_FIELDS),
        "workflow_fields": _harvest_field_group(fields, HARVEST_WORKFLOW_FIELDS),
        "admin_fields": _harvest_field_group(fields, HARVEST_ADMIN_FIELDS),
        "associated_resources": [
            resource for resource in prototype_resources if resource["code"] == code
        ],
        "fixture_path": str(path.relative_to(REPO_ROOT)),
        "raw": raw,
        "raw_json": json.dumps(raw, indent=2, sort_keys=True),
    }


def _harvest_columns(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    populated_fields = {
        field
        for record in records
        for field, value in record["fields"].items()
        if _filled(value)
    }
    ordered_fields = [
        field for field in HARVEST_FIELD_ORDER if field in populated_fields
    ]
    ordered_fields.append("associated_resource_count")
    ordered_fields.extend(
        sorted(populated_fields - set(ordered_fields) - {"associated_resource_count"})
    )
    return [
        {"key": field, "label": HARVEST_FIELD_LABELS.get(field, field)}
        for field in ordered_fields
    ]


def _harvest_field_group(
    fields: dict[str, str], field_names: tuple[str, ...]
) -> list[dict[str, str]]:
    return [
        {
            "key": field_name,
            "label": HARVEST_FIELD_LABELS.get(field_name, field_name),
            "value": fields[field_name],
        }
        for field_name in field_names
        if _filled(fields.get(field_name))
    ]


def _filled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "{}", "[]"}
    if isinstance(value, list | tuple | set):
        return any(_filled(item) for item in value)
    if isinstance(value, dict):
        return any(_filled(item) for item in value.values())
    return True


def _display_value(value: Any) -> str:
    if not _filled(value):
        return ""
    if isinstance(value, list | tuple | set):
        return "; ".join(_display_value(item) for item in value if _filled(item))
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _normalize_record(path_and_index: tuple[Path, int]) -> dict[str, Any]:
    path, index = path_and_index
    raw = json.loads(path.read_text(encoding="utf-8"))
    references = _parse_references(raw.get("dct_references_s"))
    publication_state = _publication_state(raw)
    validation = _validation_messages(raw, references)

    resource = {
        "id": str(raw.get("id") or raw.get("geomg_id_s") or path.stem),
        "title": _first(raw.get("dct_title_s")),
        "provider": _first(raw.get("schema_provider_s")),
        "publisher": _join(raw.get("dct_publisher_sm")),
        "resource_class": _join(raw.get("gbl_resourceClass_sm")),
        "resource_type": _join(raw.get("gbl_resourceType_sm")),
        "publication_state": publication_state,
        "last_modified": _first(
            raw.get("gbl_mdModified_dt") or raw.get("date_modified_dtsi")
        ),
        "access": _first(raw.get("dct_accessRights_s")),
        "format": _first(raw.get("dct_format_s")),
        "description": _join(raw.get("dct_description_sm"), separator="\n\n"),
        "subjects": _join(raw.get("dct_subject_sm")),
        "keywords": _join(raw.get("dcat_keyword_sm")),
        "spatial": _join(raw.get("dct_spatial_sm")),
        "temporal": _join(raw.get("dct_temporal_sm")),
        "identifiers": _join(raw.get("dct_identifier_sm")),
        "geometry": _first(raw.get("locn_geometry") or raw.get("dcat_bbox")),
        "references": references,
        "validation": validation,
        "checked_out_by": _checked_out_by(index),
        "fixture_path": str(path.relative_to(REPO_ROOT)),
        "raw_json": json.dumps(raw, indent=2, sort_keys=True),
    }
    resource["validation_summary"] = _validation_summary(validation)
    return resource


def _first(value: Any, fallback: str = "") -> str:
    if isinstance(value, list):
        return str(value[0]) if value else fallback
    if value is None or value == "":
        return fallback
    return str(value)


def _join(value: Any, fallback: str = "", separator: str = "; ") -> str:
    if isinstance(value, list):
        values = [str(item) for item in value if item not in (None, "")]
        return separator.join(values) if values else fallback
    return _first(value, fallback=fallback)


def _publication_state(raw: dict[str, Any]) -> str:
    explicit = _first(raw.get("b1g_publication_state_s"))
    if explicit:
        return explicit.replace("_", " ").title()
    if raw.get("gbl_suppressed_b") is True:
        return "Unpublished"
    if _first(raw.get("dct_accessRights_s")).lower() == "public":
        return "Published"
    return "Draft"


def _parse_references(raw_references: Any) -> list[dict[str, str]]:
    if not raw_references:
        return []
    try:
        parsed = (
            json.loads(raw_references)
            if isinstance(raw_references, str)
            else raw_references
        )
    except json.JSONDecodeError:
        return [{"type": "Raw references", "label": str(raw_references), "url": ""}]

    references: list[dict[str, str]] = []
    if not isinstance(parsed, dict):
        return references

    for reference_type, value in parsed.items():
        label = REFERENCE_LABELS.get(reference_type, reference_type)
        if isinstance(value, list):
            for item in value:
                references.append(_reference_item(label, item))
        else:
            references.append(_reference_item(label, value))
    return references


def _reference_item(reference_type: str, value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        url = _first(value.get("url") or value.get("@id") or value.get("href"))
        label = _first(
            value.get("label") or value.get("name"), fallback=url or reference_type
        )
    else:
        url = _first(value)
        label = url
    return {"type": reference_type, "label": label, "url": url}


def _validation_messages(
    raw: dict[str, Any], references: list[dict[str, str]]
) -> list[dict[str, str]]:
    messages = []
    if not raw.get("dct_title_s"):
        messages.append({"level": "error", "message": "Missing title."})
    if not raw.get("schema_provider_s"):
        messages.append({"level": "warning", "message": "Provider is not assigned."})
    if not raw.get("locn_geometry") and not raw.get("dcat_bbox"):
        messages.append(
            {"level": "warning", "message": "No geometry or bounding box is present."}
        )
    if _first(raw.get("dct_accessRights_s")).lower() == "restricted":
        messages.append(
            {
                "level": "warning",
                "message": "Restricted access needs review before publish.",
            }
        )
    if not any(reference["type"] == "Download" for reference in references):
        messages.append({"level": "info", "message": "No direct download link found."})
    if not messages:
        messages.append(
            {"level": "ok", "message": "Fixture passes the demo validation checks."}
        )
    return messages


def _validation_summary(messages: list[dict[str, str]]) -> str:
    if any(message["level"] == "error" for message in messages):
        return "Needs fixes"
    if any(message["level"] == "warning" for message in messages):
        return "Review"
    return "Ready"


def _checked_out_by(index: int) -> str:
    if index == 2:
        return "metadata.editor@btaa.org"
    if index == 5:
        return "qa.reviewer@btaa.org"
    return "Available"


store = AdminFixtureStore()
