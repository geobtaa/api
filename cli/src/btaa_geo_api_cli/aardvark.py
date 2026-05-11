from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from jsonschema import Draft7Validator

NS = {
    "gco": "http://www.isotc211.org/2005/gco",
    "gmd": "http://www.isotc211.org/2005/gmd",
    "gmi": "http://www.isotc211.org/2005/gmi",
    "gml": "http://www.opengis.net/gml",
    "gmx": "http://www.isotc211.org/2005/gmx",
}

AARDVARK_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/schema#",
    "title": "OpenGeoMetadata Aardvark core validation schema",
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "dct_title_s": {"type": "string"},
        "dct_description_sm": {"type": "array", "items": {"type": "string"}},
        "dct_creator_sm": {"type": "array", "items": {"type": "string"}},
        "dct_publisher_sm": {"type": "array", "items": {"type": "string"}},
        "schema_provider_s": {"type": "string"},
        "gbl_resourceClass_sm": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "Datasets",
                    "Maps",
                    "Imagery",
                    "Collections",
                    "Websites",
                    "Web services",
                    "Other",
                ],
            },
        },
        "gbl_resourceType_sm": {"type": "array", "items": {"type": "string"}},
        "dct_subject_sm": {"type": "array", "items": {"type": "string"}},
        "dcat_theme_sm": {"type": "array", "items": {"type": "string"}},
        "dct_temporal_sm": {"type": "array", "items": {"type": "string"}},
        "dct_issued_s": {"type": "string"},
        "gbl_indexYear_im": {"type": "array", "items": {"type": "integer"}},
        "dct_spatial_sm": {"type": "array", "items": {"type": "string"}},
        "locn_geometry": {"type": "string"},
        "dcat_bbox": {"type": "string"},
        "dct_accessRights_s": {"type": "string"},
        "dct_format_s": {"type": "string"},
        "dct_references_s": {"type": "string"},
        "gbl_mdVersion_s": {"type": "string", "const": "Aardvark"},
    },
    "required": [
        "id",
        "dct_title_s",
        "gbl_resourceClass_sm",
        "dct_accessRights_s",
        "gbl_mdVersion_s",
    ],
}

CROSSWALK_TABLES: dict[str, list[dict[str, str]]] = {
    "iso": [
        {"aardvark": "id", "source": "gmd:fileIdentifier or citation identifier"},
        {"aardvark": "dct_title_s", "source": "gmd:CI_Citation/gmd:title"},
        {"aardvark": "dct_description_sm", "source": "gmd:abstract"},
        {"aardvark": "dct_creator_sm", "source": "responsible party role=originator"},
        {"aardvark": "dct_publisher_sm", "source": "responsible party role=publisher"},
        {"aardvark": "schema_provider_s", "source": "distributor or metadata contact org"},
        {"aardvark": "gbl_resourceClass_sm", "source": "hierarchyLevelName"},
        {"aardvark": "gbl_resourceType_sm", "source": "geometric object or spatial type"},
        {"aardvark": "dct_subject_sm", "source": "theme descriptive keywords"},
        {"aardvark": "dct_spatial_sm", "source": "place descriptive keywords"},
        {"aardvark": "dct_issued_s", "source": "citation date"},
        {"aardvark": "dcat_bbox", "source": "EX_GeographicBoundingBox"},
        {"aardvark": "dct_accessRights_s", "source": "legal constraints"},
        {"aardvark": "dct_format_s", "source": "distribution format name"},
        {"aardvark": "dct_references_s", "source": "online resource linkages"},
    ],
    "fgdc": [
        {"aardvark": "id", "source": "idinfo/citation/citeinfo/onlink or title slug"},
        {"aardvark": "dct_title_s", "source": "idinfo/citation/citeinfo/title"},
        {"aardvark": "dct_description_sm", "source": "idinfo/descript/abstract"},
        {"aardvark": "dct_creator_sm", "source": "idinfo/citation/citeinfo/origin"},
        {"aardvark": "dct_publisher_sm", "source": "idinfo/citation/citeinfo/pubinfo/publish"},
        {"aardvark": "schema_provider_s", "source": "distinfo/metainfo contact org"},
        {"aardvark": "gbl_resourceClass_sm", "source": "default Datasets"},
        {"aardvark": "gbl_resourceType_sm", "source": "sdtstype, direct, geoform"},
        {"aardvark": "dct_subject_sm", "source": "idinfo/keywords/theme/themekey"},
        {"aardvark": "dct_spatial_sm", "source": "idinfo/keywords/place/placekey"},
        {"aardvark": "dct_issued_s", "source": "idinfo/citation/citeinfo/pubdate"},
        {"aardvark": "dcat_bbox", "source": "idinfo/spdom/bounding"},
        {"aardvark": "dct_accessRights_s", "source": "idinfo/accconst and useconst"},
        {"aardvark": "dct_format_s", "source": "distinfo/stdorder/digform/digtinfo/formname"},
        {"aardvark": "dct_references_s", "source": "onlink and metadata XML path"},
    ],
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[dict[str, str]]


def validate_aardvark(record: dict[str, Any]) -> ValidationResult:
    validator = Draft7Validator(AARDVARK_SCHEMA)
    errors = []
    for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or "$"
        errors.append({"path": location, "message": error.message})
    return ValidationResult(valid=not errors, errors=errors)


def load_json_record(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Aardvark record must be a JSON object.")
    return payload


def crosswalk(path: Path, source: str) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    if source == "iso":
        record = _crosswalk_iso(root)
    elif source == "fgdc":
        record = _crosswalk_fgdc(root)
    else:
        raise ValueError("source must be 'iso' or 'fgdc'.")
    return _clean_record(record)


def _crosswalk_iso(root: ET.Element) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": _first_text(
            root,
            [
                ".//gmd:fileIdentifier/gco:CharacterString",
                ".//gmd:CI_Citation/gmd:identifier//gmd:code//gco:CharacterString",
                ".//gmd:CI_Citation/gmd:identifier//gmd:code//gmx:Anchor",
                ".//gmd:onLine//gmd:URL",
            ],
        ),
        "dct_title_s": _first_text(root, [".//gmd:CI_Citation/gmd:title//gco:CharacterString"]),
        "dct_description_sm": _texts(root, [".//gmd:abstract//gco:CharacterString"]),
        "dct_creator_sm": _iso_responsible_parties(root, "originator"),
        "dct_publisher_sm": _iso_responsible_parties(root, "publisher"),
        "schema_provider_s": _first_text(
            root,
            [
                ".//gmd:distributorContact//gmd:organisationName//gco:CharacterString",
                ".//gmd:contact//gmd:organisationName//gco:CharacterString",
            ],
        ),
        "gbl_resourceClass_sm": [_iso_resource_class(root)],
        "gbl_resourceType_sm": _iso_resource_types(root),
        "dct_subject_sm": _iso_keywords(root, "theme"),
        "dcat_theme_sm": _texts(root, [".//gmd:topicCategory/gmd:MD_TopicCategoryCode"]),
        "dct_spatial_sm": _iso_keywords(root, "place"),
        "dct_issued_s": _first_text(
            root,
            [
                ".//gmd:CI_Citation/gmd:date//gco:Date",
                ".//gmd:CI_Citation/gmd:date//gco:DateTime",
            ],
        ),
        "dct_accessRights_s": _iso_access_rights(root),
        "dct_format_s": _first_text(root, [".//gmd:MD_Format/gmd:name//gco:CharacterString"]),
        "dct_references_s": _references_json(_texts(root, [".//gmd:onLine//gmd:URL"])),
        "gbl_mdVersion_s": "Aardvark",
    }
    _add_bbox(record, _iso_bbox(root))
    _add_year(record)
    return record


def _crosswalk_fgdc(root: ET.Element) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": _first_text(root, ["./idinfo/citation/citeinfo/onlink"])
        or _slug(_first_text(root, ["./idinfo/citation/citeinfo/title"])),
        "dct_title_s": _first_text(root, ["./idinfo/citation/citeinfo/title"]),
        "dct_description_sm": _texts(root, ["./idinfo/descript/abstract"]),
        "dct_creator_sm": _texts(root, ["./idinfo/citation/citeinfo/origin"]),
        "dct_publisher_sm": _texts(root, ["./idinfo/citation/citeinfo/pubinfo/publish"]),
        "schema_provider_s": _first_text(
            root,
            [
                "./distinfo/distrib/cntinfo/cntorgp/cntorg",
                "./metainfo/metc/cntinfo/cntorgp/cntorg",
            ],
        ),
        "gbl_resourceClass_sm": ["Datasets"],
        "gbl_resourceType_sm": _fgdc_resource_types(root),
        "dct_subject_sm": _texts(root, ["./idinfo/keywords/theme/themekey"]),
        "dct_spatial_sm": _texts(root, ["./idinfo/keywords/place/placekey"]),
        "dct_issued_s": _fgdc_date(_first_text(root, ["./idinfo/citation/citeinfo/pubdate"])),
        "dct_accessRights_s": _fgdc_access_rights(root),
        "dct_format_s": _first_text(root, ["./distinfo/stdorder/digform/digtinfo/formname"]),
        "dct_references_s": _references_json(_texts(root, ["./idinfo/citation/citeinfo/onlink"])),
        "gbl_mdVersion_s": "Aardvark",
    }
    _add_bbox(record, _fgdc_bbox(root))
    _add_year(record)
    return record


def _first_text(root: ET.Element, paths: list[str]) -> str:
    for path in paths:
        for item in root.findall(path, NS):
            text = _node_text(item)
            if text:
                return text
    return ""


def _texts(root: ET.Element, paths: list[str]) -> list[str]:
    values = []
    for path in paths:
        for item in root.findall(path, NS):
            text = _node_text(item)
            if text and text not in values:
                values.append(text)
    return values


def _node_text(node: ET.Element) -> str:
    text = " ".join(part.strip() for part in node.itertext() if part.strip())
    return re.sub(r"\s+", " ", text).strip()


def _iso_responsible_parties(root: ET.Element, role: str) -> list[str]:
    values = []
    for party in root.findall(".//gmd:CI_ResponsibleParty", NS):
        role_code = party.find(".//gmd:CI_RoleCode", NS)
        if role_code is None:
            continue
        if role_code.attrib.get("codeListValue") != role and _node_text(role_code) != role:
            continue
        name = _first_text(
            party,
            [
                "./gmd:organisationName/gco:CharacterString",
                "./gmd:individualName/gco:CharacterString",
            ],
        )
        if name and name not in values:
            values.append(name)
    return values


def _iso_keywords(root: ET.Element, keyword_type: str) -> list[str]:
    values = []
    for keywords in root.findall(".//gmd:MD_Keywords", NS):
        type_node = keywords.find("./gmd:type/gmd:MD_KeywordTypeCode", NS)
        type_value = type_node.attrib.get("codeListValue") if type_node is not None else ""
        if type_value != keyword_type:
            continue
        for keyword in keywords.findall("./gmd:keyword", NS):
            text = _node_text(keyword)
            if text and text not in values:
                values.append(text)
    return values


def _iso_resource_class(root: ET.Element) -> str:
    hierarchy = _first_text(root, [".//gmd:hierarchyLevelName/gco:CharacterString"]).lower()
    if "service" in hierarchy:
        return "Web services"
    return "Datasets"


def _iso_resource_types(root: ET.Element) -> list[str]:
    haystack = " ".join(
        _texts(
            root,
            [
                ".//gmd:MD_GeometricObjectTypeCode",
                ".//gmd:spatialRepresentationType//gmd:MD_SpatialRepresentationTypeCode",
                ".//gmd:MD_Format/gmd:name//gco:CharacterString",
            ],
        )
    ).lower()
    if "point" in haystack:
        return ["Point data"]
    if "curve" in haystack or "line" in haystack:
        return ["Line data"]
    if "surface" in haystack or "polygon" in haystack:
        return ["Polygon data"]
    if "grid" in haystack or "raster" in haystack:
        return ["Raster data"]
    return []


def _fgdc_resource_types(root: ET.Element) -> list[str]:
    haystack = " ".join(
        _texts(
            root,
            [
                "./spdoinfo/ptvctinf/sdtsterm/sdtstype",
                "./spdoinfo/direct",
                "./idinfo/citation/citeinfo/geoform",
            ],
        )
    ).lower()
    if "point" in haystack:
        return ["Point data"]
    if "string" in haystack or "line" in haystack:
        return ["Line data"]
    if "polygon" in haystack:
        return ["Polygon data"]
    if "raster" in haystack:
        return ["Raster data"]
    return []


def _iso_access_rights(root: ET.Element) -> str:
    text = " ".join(_texts(root, [".//gmd:resourceConstraints//gco:CharacterString"]))
    text += " " + " ".join(_texts(root, [".//gmd:MD_RestrictionCode"]))
    return _rights_from_text(text)


def _fgdc_access_rights(root: ET.Element) -> str:
    text = " ".join(_texts(root, ["./idinfo/accconst", "./idinfo/useconst"]))
    return _rights_from_text(text)


def _rights_from_text(text: str) -> str:
    lowered = text.lower()
    if any(value in lowered for value in ("restricted", "licensed", "license required")):
        return "Restricted"
    if any(value in lowered for value in ("public", "unrestricted", "no restriction", "none")):
        return "Public"
    return "Public"


def _iso_bbox(root: ET.Element) -> tuple[str, str, str, str] | None:
    west = _first_text(root, [".//gmd:westBoundLongitude/gco:Decimal"])
    east = _first_text(root, [".//gmd:eastBoundLongitude/gco:Decimal"])
    north = _first_text(root, [".//gmd:northBoundLatitude/gco:Decimal"])
    south = _first_text(root, [".//gmd:southBoundLatitude/gco:Decimal"])
    return (west, east, north, south) if all((west, east, north, south)) else None


def _fgdc_bbox(root: ET.Element) -> tuple[str, str, str, str] | None:
    west = _first_text(root, ["./idinfo/spdom/bounding/westbc"])
    east = _first_text(root, ["./idinfo/spdom/bounding/eastbc"])
    north = _first_text(root, ["./idinfo/spdom/bounding/northbc"])
    south = _first_text(root, ["./idinfo/spdom/bounding/southbc"])
    return (west, east, north, south) if all((west, east, north, south)) else None


def _add_bbox(record: dict[str, Any], bbox: tuple[str, str, str, str] | None) -> None:
    if not bbox:
        return
    west, east, north, south = bbox
    envelope = f"ENVELOPE({west}, {east}, {north}, {south})"
    record["dcat_bbox"] = envelope
    record["locn_geometry"] = envelope


def _add_year(record: dict[str, Any]) -> None:
    date = str(record.get("dct_issued_s") or "")
    match = re.search(r"\d{4}", date)
    if match:
        record["gbl_indexYear_im"] = [int(match.group(0))]


def _fgdc_date(value: str) -> str:
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    if re.fullmatch(r"\d{6}", value):
        return f"{value[:4]}-{value[4:6]}"
    return value


def _references_json(urls: list[str]) -> str:
    refs = {}
    for url in urls:
        if not url:
            continue
        key = "http://schema.org/url"
        lowered = url.lower()
        if lowered.endswith(".xml") or "metadata" in lowered:
            key = "http://www.isotc211.org/schemas/2005/gmd/"
        refs[key] = url
    return json.dumps(refs, sort_keys=True) if refs else ""


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def _clean_record(record: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in record.items():
        if value in ("", [], None):
            continue
        cleaned[key] = value
    return cleaned
