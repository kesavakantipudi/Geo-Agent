"""Geometry parsing and validation (Phase 3: strict shapely-based checks).

The SRID is pinned to 4326 (WGS 84). Inputs are accepted as:

- a GeoJSON geometry object (Point, LineString, Polygon, and the Multi* forms),
- a GeoJSON ``Feature`` / ``FeatureCollection`` carrying a single geometry,
- a WKT / EWKT string (``SRID=4326;...``).

Validation covers structure, coordinate order (``[lon, lat]``), coordinate
ranges, ring closure, vertex-count limits, and validity checks (e.g.
self-intersecting polygons) provided by the underlying geometry library
(shapely). Coordinates are never silently reinterpreted: a supplied SRID
other than 4326 is rejected.
"""

from __future__ import annotations

import math
from typing import Any

from geoalchemy2.elements import WKTElement
from shapely import GEOSException, get_coordinates, transform
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.validation import explain_validity
from shapely.wkt import loads as wkt_loads

from app.core.config import get_settings
from app.core.exceptions import ApiError, bad_request

SRID = 4326
LON_MIN, LON_MAX = -180.0, 180.0
LAT_MIN, LAT_MAX = -90.0, 90.0

# Geometry types that can be measured for area.
AREA_TYPES = ("Polygon", "MultiPolygon")

_GEOMETRY_TYPES = (
    "Point",
    "LineString",
    "Polygon",
    "MultiPoint",
    "MultiLineString",
    "MultiPolygon",
    "GeometryCollection",
)


class _CoordinateCounter:
    """Enforces the vertex-count limit while the recursive parser walks input."""

    def __init__(self) -> None:
        self.count = 0

    def add(self, n: int) -> None:
        self.count += n
        limit = get_settings().max_geometry_points
        if self.count > limit:
            raise bad_request(
                f"Geometry is too complex: more than {limit} vertices are not allowed.",
                code="geometry_too_complex",
            )


def _parse_position(value: Any, path: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) < 2:
        raise bad_request(f"{path} must be a [longitude, latitude] coordinate.")
    try:
        lon = float(value[0])
        lat = float(value[1])
    except (TypeError, ValueError) as exc:
        raise bad_request(f"{path} must contain numeric longitude and latitude.") from exc
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise bad_request(f"{path} must contain finite numbers.")
    if not (LON_MIN <= lon <= LON_MAX):
        raise bad_request(f"Longitude {lon} is out of range [{LON_MIN}, {LON_MAX}] at {path}.")
    if not (LAT_MIN <= lat <= LAT_MAX):
        raise bad_request(f"Latitude {lat} is out of range [{LAT_MIN}, {LAT_MAX}] at {path}.")
    return (lon, lat)


def _positions_of(value: Any, path: str, counter: _CoordinateCounter) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        raise bad_request(f"{path} must be a list of coordinates.")
    counter.add(len(value))
    return [_parse_position(pos, f"{path}[{i}]") for i, pos in enumerate(value)]


def _rings_of(
    value: Any, path: str, counter: _CoordinateCounter
) -> list[list[tuple[float, float]]]:
    if not isinstance(value, list) or not value:
        raise bad_request(f"{path} must contain at least one ring.")
    rings = []
    for i, ring in enumerate(value):
        positions = _positions_of(ring, f"{path}[{i}]", counter)
        if len(positions) < 4:
            raise bad_request(f"{path}[{i}] must be a ring with at least 4 points.")
        if positions[0] != positions[-1]:
            raise bad_request(
                f"{path}[{i}] must be a closed ring (first and last coordinates equal)."
            )
        rings.append(positions)
    return rings


def _multi_parts(value: Any, type_name: str, counter: _CoordinateCounter) -> list[Any]:
    if not isinstance(value, list):
        raise bad_request(f"{type_name}.coordinates must be a list.")
    return value


def _shape_from_geojson(geometry: dict[str, Any], counter: _CoordinateCounter) -> Any:
    """Build a shapely geometry from a GeoJSON geometry object.

    Raises a 400 ``ApiError`` for structural, range, closure, or complexity
    violations. ``counter`` accumulates the running vertex count.
    """
    type_name = geometry.get("type")
    if not isinstance(type_name, str):
        raise bad_request("Geometry is missing a 'type'.")
    if type_name not in _GEOMETRY_TYPES:
        raise bad_request(f"Unsupported GeoJSON geometry type '{type_name}'.")
    coordinates = geometry.get("coordinates")

    if type_name == "Point":
        counter.add(1)
        return Point(_parse_position(coordinates, "Point.coordinates"))

    if type_name == "LineString":
        positions = _positions_of(coordinates, "LineString.coordinates", counter)
        if len(positions) < 2:
            raise bad_request("LineString requires at least two points.")
        return LineString(positions)

    if type_name == "Polygon":
        rings = _rings_of(coordinates, "Polygon.coordinates", counter)
        return Polygon(rings[0], rings[1:])

    if type_name == "MultiPoint":
        parts = _multi_parts(coordinates, type_name, counter)
        counter.add(max(0, len(parts)))
        return MultiPoint(
            [
                Point(_parse_position(pos, f"MultiPoint.coordinates[{i}]"))
                for i, pos in enumerate(parts)
            ]
        )

    if type_name == "MultiLineString":
        lines = []
        for i, part in enumerate(_multi_parts(coordinates, type_name, counter)):
            positions = _positions_of(part, f"MultiLineString.coordinates[{i}]", counter)
            if len(positions) < 2:
                raise bad_request(f"MultiLineString.coordinates[{i}] requires at least two points.")
            lines.append(LineString(positions))
        return MultiLineString(lines)

    if type_name == "MultiPolygon":
        polygons = []
        for i, part in enumerate(_multi_parts(coordinates, type_name, counter)):
            rings = _rings_of(part, f"MultiPolygon.coordinates[{i}]", counter)
            polygons.append(Polygon(rings[0], rings[1:]))
        return MultiPolygon(polygons)

    # GeometryCollection
    geometries = geometry.get("geometries")
    if not isinstance(geometries, list):
        raise bad_request("GeometryCollection.geometries must be a list.")
    return GeometryCollection([_shape_from_geojson(item, counter) for item in geometries])


def _as_geometry_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Unwrap a GeoJSON Feature / FeatureCollection into a geometry object."""
    type_name = value.get("type")
    if type_name in ("Feature", "FeatureCollection"):
        features = value.get("features") if type_name == "FeatureCollection" else [value]
        geometries = [
            f.get("geometry")
            for f in features
            if isinstance(f, dict) and isinstance(f.get("geometry"), dict)
        ]
        if not geometries:
            raise bad_request("Geometry feature contains no geometry.")
        if len(geometries) > 1:
            raise bad_request(
                "Multiple geometries are not supported here; import a single feature or geometry."
            )
        return geometries[0]
    if not isinstance(type_name, str) or type_name not in _GEOMETRY_TYPES:
        raise bad_request(f"Unsupported GeoJSON geometry type '{type_name}'.")
    return value


def _geometry_from_ewkt(text: str) -> Any:
    if not isinstance(text, str) or not text.strip():
        raise bad_request("Geometry must be a WKT/EWKT string or a GeoJSON object.")
    raw = text.strip()
    srid = SRID
    wkt = raw
    if raw.upper().startswith("SRID="):
        if ";" not in raw:
            raise bad_request("Malformed EWKT string: missing ';' separator.")
        srid_text, wkt = raw.split(";", 1)
        try:
            srid = int(srid_text[5:].strip())
        except ValueError as exc:
            raise bad_request("Malformed EWKT string: invalid SRID.") from exc
    if srid != SRID:
        raise bad_request(f"Only SRID {SRID} is supported; got SRID {srid}.")
    try:
        geom = wkt_loads(wkt.strip())
    except (GEOSException, ValueError) as exc:
        raise bad_request(f"Could not parse WKT geometry: {exc}") from exc
    if geom is None or geom.is_empty:
        raise bad_request("Geometry is empty.")
    _check_coordinate_ranges(geom)
    _check_validity(geom)
    count = len(get_coordinates(geom))
    limit = get_settings().max_geometry_points
    if count > limit:
        raise bad_request(
            f"Geometry is too complex: more than {limit} vertices are not allowed.",
            code="geometry_too_complex",
        )
    return geom


def _check_coordinate_ranges(geom: Any) -> None:
    for lon, lat in get_coordinates(geom):
        if not (math.isfinite(lon) and math.isfinite(lat)):
            raise bad_request("Geometry contains non-finite coordinates.")
        if not (LON_MIN <= lon <= LON_MAX):
            raise bad_request(f"Longitude {lon} is out of range [{LON_MIN}, {LON_MAX}].")
        if not (LAT_MIN <= lat <= LAT_MAX):
            raise bad_request(f"Latitude {lat} is out of range [{LAT_MIN}, {LAT_MAX}].")


def _check_validity(geom: Any) -> None:
    if not geom.is_valid:
        reason = explain_validity(geom) or "geometry is not valid"
        raise bad_request(f"Geometry is not valid: {reason}", code="geometry_not_valid")


def approximate_area_m2(geom: Any) -> float:
    """Approximate area in square meters using an equal-area projection.

    The geometry is projected with a Lambert Azimuthal Equal Area projection
    centered at its centroid. A planar (degree-based) fallback is used only if
    the projection library is unavailable.
    """
    if geom.is_empty or geom.geom_type not in AREA_TYPES or not geom.area:
        return 0.0
    centroid = geom.centroid
    try:
        from pyproj import Transformer

        projection = (
            f"+proj=laea +lat_0={centroid.y:.6f} +lon_0={centroid.x:.6f} +datum=WGS84 +units=m"
        )
        transformer = Transformer.from_crs("EPSG:4326", projection, always_xy=True)
        projected = transform(geom, transformer.transform)
        return max(0.0, float(projected.area))
    except Exception:
        scale = 111_320.0
        cos_lat = max(0.0, math.cos(math.radians(centroid.y)))
        return max(0.0, float(geom.area)) * scale * scale * cos_lat


def _info_from_geometry(geom: Any, point_count: int) -> dict[str, Any]:
    bounds = geom.bounds if not geom.is_empty else (0.0, 0.0, 0.0, 0.0)
    centroid = geom.centroid if not geom.is_empty else Point(0.0, 0.0)
    return {
        "geometry_type": geom.geom_type,
        "is_valid": True,
        "point_count": point_count,
        "bbox": [
            round(float(bounds[0]), 6),
            round(float(bounds[1]), 6),
            round(float(bounds[2]), 6),
            round(float(bounds[3]), 6),
        ],
        "centroid": {"lon": round(float(centroid.x), 6), "lat": round(float(centroid.y), 6)},
        "area_m2_approx": round(approximate_area_m2(geom), 2),
    }


def _require_area(geom: Any) -> None:
    if geom.geom_type not in AREA_TYPES:
        raise bad_request(
            f"An AOI must be a Polygon (or MultiPolygon); got '{geom.geom_type}'.",
            code="aoi_not_polygon",
        )
    if not geom.area or geom.area <= 0:
        raise bad_request("The AOI has zero area; draw or import a real area.", code="aoi_empty")


def validate_geometry(
    value: str | dict[str, Any], name: str = "geometry", require_area: bool = False
) -> dict[str, Any]:
    """Validate raw geometry input and return normalized geometry info.

    Raises a 400 ``ApiError`` on any problem. ``require_area`` additionally
    demands a Polygon/MultiPolygon with measurable area (used for AOIs).
    """
    input_value = dict(value) if isinstance(value, dict) else value
    if isinstance(input_value, dict):
        input_value = _as_geometry_dict(input_value)
    try:
        counter = _CoordinateCounter()
        if isinstance(input_value, dict):
            geom = _shape_from_geojson(input_value, counter)
            point_count = counter.count
        else:
            geom = _geometry_from_ewkt(input_value)
            point_count = len(get_coordinates(geom))
        if require_area:
            _require_area(geom)
        _check_validity(geom)
    except ApiError:
        raise
    except (GEOSException, ValueError, TypeError) as exc:
        raise bad_request(f"Could not parse geometry: {exc}") from exc
    info = _info_from_geometry(geom, point_count)
    info["warnings"] = []
    info["srid"] = SRID
    return info


def parse_geometry(name: str, value: str | dict[str, Any]) -> WKTElement:
    """Convert validated input into a geoalchemy2 WKT element (SRID 4326)."""
    if isinstance(value, dict):
        geometry_dict = _as_geometry_dict(value)
        if geometry_dict.get("type") == "GeometryCollection":
            raise bad_request(
                f"'{name}' must be a single geometry; GeometryCollections are not supported."
            )
        counter = _CoordinateCounter()
        geom = _shape_from_geojson(geometry_dict, counter)
        geom_wkt = geom.wkt
    else:
        validate_geometry(value, name=name)
        raw = (value or "").strip()
        geom_wkt = raw.split(";", 1)[1].strip() if raw.upper().startswith("SRID=") else raw
    return WKTElement(f"SRID={SRID};{geom_wkt}", srid=SRID)


def geometry_info_from_ewkt(ewkt: str | None) -> dict[str, Any] | None:
    """Return geometry info for an EWKT string read back from the database."""
    if not ewkt:
        return None
    try:
        geom = _geometry_from_ewkt(ewkt)
    except ApiError:
        return None
    info = _info_from_geometry(geom, len(get_coordinates(geom)))
    info["warnings"] = []
    info["srid"] = SRID
    return info


def _to_lists(value: Any) -> Any:
    """Recursively convert tuples (e.g. shapely ``__geo_interface__``) to lists."""
    if isinstance(value, dict):
        return {key: _to_lists(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_to_lists(item) for item in value]
    if isinstance(value, list):
        return [_to_lists(item) for item in value]
    return value


def geojson_from_ewkt(ewkt: str | None) -> dict[str, Any] | None:
    """Convert an EWKT string from the database into a GeoJSON geometry dict.

    Coordinates are normalized to plain lists so the result round-trips through
    :func:`validate_geometry` and the strict GeoJSON parser.
    """
    if not ewkt:
        return None
    try:
        geom = _geometry_from_ewkt(ewkt)
    except ApiError:
        return None
    return _to_lists(geom.__geo_interface__)
