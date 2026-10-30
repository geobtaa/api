"""Display geometry only; never changes source metadata or search indexing."""

import json
import math
import re

from shapely import affinity, wkt
from shapely.errors import ShapelyError
from shapely.geometry import LineString, Point, box, mapping, shape
from shapely.ops import split, transform, unary_union

from .models import Coverage, Outcome, PreviewError


def bounds_geometry(bounds):
    west, south, east, north = bounds
    if west == east and south == north:
        return normalized_geometry(mapping(Point(west, south)))
    if west == east or south == north:
        return normalized_geometry(mapping(LineString([(west, south), (east, north)])))
    return normalized_geometry(f"ENVELOPE({west},{east},{north},{south})")


def normalized_geometry(value):
    if not isinstance(value, (str, dict)):
        raise ValueError("Geometry must be WKT or GeoJSON")
    if isinstance(value, str):
        value = value.strip()
        if value.upper().startswith("ENVELOPE"):
            nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
            if len(nums) != 4:
                raise ValueError("Invalid envelope")
            west, east, north, south = map(float, nums)
            geom = box(west, south, east if east >= west else east + 360, north)
        elif value.startswith("{"):
            return normalized_geometry(json.loads(value))
        elif re.fullmatch(r"[-+\d.eE\s,]+", value) and len(value.split(",")) == 4:
            return bounds_geometry(list(map(float, value.split(","))))
        else:
            geom = wkt.loads(value)
    else:
        geom = shape(value.get("geometry", value))
    if geom.is_empty or not geom.is_valid or not all(math.isfinite(v) for v in geom.bounds):
        raise ValueError("Invalid display geometry")
    if geom.bounds[1] < -90 or geom.bounds[3] > 90 or geom.bounds[0] < -180 or geom.bounds[2] > 360:
        raise ValueError("Geometry is not geographic")
    # Unwrap rings at the dateline before splitting. Preserve wide, explicitly
    # rectangular metadata extents; their width alone is not an error.
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        polygons = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        parts = []
        for polygon in polygons:
            if polygon.bounds[2] - polygon.bounds[0] > 180 and not polygon.equals(polygon.envelope):
                polygon = transform(lambda x, y, z=None: (x + 360 if x < 0 else x, y), polygon)
            for part in split(polygon, LineString([(180, -90), (180, 90)])).geoms:
                parts.append(
                    affinity.translate(part, xoff=-360)
                    if part.representative_point().x > 180
                    else part
                )
        geom = unary_union(parts)
    return geom


def metadata_coverage(record: dict) -> Coverage:
    fields = {k.lower(): v for k, v in record.items()}
    for field in ("locn_geometry", "dcat_bbox"):
        if fields.get(field):
            try:
                geom = normalized_geometry(fields[field])
                focus = bool(
                    set(fields.get("gbl_resourceclass_sm", [])) & {"Websites", "Collections"}
                )
                return Coverage(
                    geometry=mapping(geom),
                    kind="geographic-focus" if focus else "metadata-extent",
                    label="Geographic focus" if focus else "Metadata extent",
                    provenance=field,
                )
            except (ValueError, TypeError, KeyError, ShapelyError):
                continue
    return Coverage(
        kind="unavailable", label="Location unavailable", provenance="No usable geometry"
    )


def valid_index_members(collection: dict) -> list[dict]:
    valid = []
    for feature in collection.get("features", []):
        try:
            geom = normalized_geometry(feature["geometry"])
            if geom.geom_type not in {"Polygon", "MultiPolygon"}:
                raise ValueError("Index geometry must be polygonal")
            valid.append({**feature, "geometry": mapping(geom)})
        except (ValueError, KeyError, TypeError, ShapelyError):
            continue
    if not valid:
        raise PreviewError(Outcome.NEEDS_REVIEW, "Index contains no valid polygons")
    return valid


def index_coverage(collection: dict) -> Coverage:
    members = valid_index_members(collection)
    omitted = len(collection.get("features", [])) - len(members)
    polygons = [shape(feature["geometry"]) for feature in members]
    return Coverage(
        geometry=mapping(unary_union(polygons)),
        kind="indexed-coverage",
        label="Indexed coverage (incomplete)" if omitted else "Indexed coverage",
        provenance=(
            "Union of valid index member polygons; availability not implied"
            + (f"; {omitted} invalid geometries omitted; requires review" if omitted else "")
        ),
    )


def representative_members(collection: dict) -> list[dict]:
    features = valid_index_members(collection)
    coverage = shape(index_coverage(collection).geometry)
    # A circular longitude mean prevents dateline collections choosing Greenwich.
    centers = [shape(f["geometry"]).representative_point() for f in features]
    longitude = math.degrees(
        math.atan2(
            sum(math.sin(math.radians(p.x)) for p in centers),
            sum(math.cos(math.radians(p.x)) for p in centers),
        )
    )
    latitude = coverage.centroid.y

    def key(feature):
        center = shape(feature["geometry"]).representative_point()
        dx = ((center.x - longitude + 180) % 360) - 180
        props = feature.get("properties") or {}
        identity = (
            props.get("label")
            or props.get("title")
            or feature.get("id")
            or json.dumps(feature, sort_keys=True)
        )
        return (
            dx * dx * math.cos(math.radians(latitude)) ** 2 + (center.y - latitude) ** 2,
            str(identity),
        )

    return sorted(features, key=key)[:3]
