"""Display geometry only; never changes source metadata or search indexing."""

import json
import math
import re

from shapely import affinity, get_num_coordinates, wkt
from shapely.errors import ShapelyError
from shapely.geometry import LineString, MultiLineString, Point, box, mapping, shape
from shapely.ops import split, transform, unary_union

from .models import Coverage, Outcome, PreviewError, fingerprint


def display_coverage(coverage):
    """Persist one display geometry for static maps and all UI overlays."""
    if not coverage or not coverage.geometry:
        return coverage
    geometry = shape(coverage.geometry)
    if get_num_coordinates(geometry) <= 2000:
        return coverage
    west, south, east, north = geometry.bounds
    tolerance = max(east - west, north - south) / 8000
    simplified = geometry.simplify(tolerance, preserve_topology=True)
    return coverage.model_copy(
        update={
            "geometry": mapping(simplified),
            "provenance": coverage.provenance
            + (
                f"; display simplification tolerance {tolerance:.8g} degrees; "
                f"source geometry SHA256 {fingerprint(coverage.geometry)}"
            ),
        }
    )


def point_regions(coordinates):
    """Regional envelopes from actual points, preserving remote/dateline groups.

    A bounded five-degree occupancy grid groups neighboring points. Envelopes
    describe geographic extent, not a claim of continuous data between points.
    """
    cells = {}
    for longitude, latitude in coordinates:
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise PreviewError(Outcome.INVALID, "Point coordinate is not geographic")
        key = (min(71, math.floor((longitude + 180) / 5)), min(35, math.floor((latitude + 90) / 5)))
        previous = cells.get(key, [longitude, latitude, longitude, latitude])
        cells[key] = [
            min(previous[0], longitude),
            min(previous[1], latitude),
            max(previous[2], longitude),
            max(previous[3], latitude),
        ]
    groups = []
    while cells:
        seed = min(cells)
        pending, bounds = [seed], []
        while pending:
            cell = pending.pop()
            if cell not in cells:
                continue
            bounds.append(cells.pop(cell))
            pending.extend(
                ((cell[0] + dx) % 72, cell[1] + dy)
                for dx in (-1, 0, 1)
                for dy in (-1, 0, 1)
                if dx or dy
            )
        longitudes = sorted({value for extent in bounds for value in (extent[0], extent[2])})
        if len(longitudes) == 1:
            west = east = longitudes[0]
        else:
            gaps = [
                (
                    longitudes[(i + 1) % len(longitudes)]
                    + (360 if i == len(longitudes) - 1 else 0)
                    - value,
                    i,
                )
                for i, value in enumerate(longitudes)
            ]
            _, gap = max(gaps)
            west, east = longitudes[(gap + 1) % len(longitudes)], longitudes[gap]
        south, north = min(b[1] for b in bounds), max(b[3] for b in bounds)
        groups.append(bounds_geometry([west, south, east, north]))
    return unary_union(groups) if groups else None


def validate_index_content(record, member, manifest):
    """Withhold a sample when its geography or known band meaning conflicts."""
    area = normalized_geometry(member["geometry"])
    if manifest.layers and all(layer.bounds for layer in manifest.layers):
        if not any(area.intersects(bounds_geometry(layer.bounds)) for layer in manifest.layers):
            raise PreviewError(
                Outcome.NEEDS_REVIEW, "Index member data lies outside its indexed geometry"
            )
    title = record.get("dct_title_s", "")
    if re.search(r"\b(DEM|DSM|digital elevation model|digital surface model)\b", title, re.I):
        if not re.search(r"\b(imagery|photograph|scan)\b", title, re.I):
            if any(
                layer.format == "cog" and layer.recipe and layer.recipe.kind != "scalar"
                for layer in manifest.layers
            ):
                raise PreviewError(
                    Outcome.NEEDS_REVIEW, "Elevation index title conflicts with member band meaning"
                )


def bounds_geometry(bounds):
    west, south, east, north = bounds
    if west == east and south == north:
        return normalized_geometry(mapping(Point(west, south)))
    if west == east or south == north:
        if west > east:
            return MultiLineString([[(west, south), (180, south)], [(-180, south), (east, south)]])
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
