"""Geometry parsing helpers for saved locations.

Phase 2 accepts EWKT strings or GeoJSON geometry objects. SRID is pinned to
4326 (WGS 84). A tiny WKT writer covers the geometry types needed by Phase 2;
richer types can be delegated to a geometry library in a later phase.
"""

from __future__ import annotations

from typing import Any

from geoalchemy2.elements import WKTElement

from app.core.exceptions import bad_request

SRID = 4326


def _format_number(value: Any) -> str:
    return f"{value:.10f}".rstrip("0").rstrip(".")


def _coords_wkt(geometry: dict[str, Any], type_name: str) -> str:
    """Return the inner coordinates text for the given GeoJSON geometry type."""
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list):
        raise bad_request("GeoJSON geometry is missing 'coordinates'.")

    if type_name == "Point":
        if len(coordinates) < 2:
            raise bad_request("Point geometry requires [longitude, latitude].")
        return f"{_format_number(coordinates[0])} {_format_number(coordinates[1])}"

    if type_name == "LineString":
        if not coordinates or not all(isinstance(c, list) and len(c) >= 2 for c in coordinates):
            raise bad_request("LineString geometry requires at least two [lon, lat] points.")
        return ", ".join(f"{_format_number(c[0])} {_format_number(c[1])}" for c in coordinates)

    if type_name == "Polygon":
        rings = []
        for ring in coordinates:
            if (
                not isinstance(ring, list)
                or len(ring) < 4
                or not all(isinstance(c, list) and len(c) >= 2 for c in ring)
            ):
                raise bad_request("Polygon rings must be closed polygons (4+ points).")
            points = ", ".join(f"{_format_number(c[0])} {_format_number(c[1])}" for c in ring)
            rings.append(f"({points})")
        return ", ".join(rings)

    raise bad_request(f"GeoJSON geometry type '{type_name}' is not supported in Phase 2.")


def parse_geometry(name: str, value: str | dict[str, Any]) -> WKTElement:
    """Convert a user-supplied geometry into a geoalchemy2 WKT element (SRID 4326)."""
    try:
        if isinstance(value, str):
            text = value.strip()
            if text.upper().startswith("SRID="):
                return WKTElement(text, srid=SRID)
            return WKTElement(f"SRID={SRID};{text}", srid=SRID)

        if isinstance(value, dict):
            type_name = value.get("type")
            if not isinstance(type_name, str):
                raise bad_request(f"'{name}'.geometry is missing a 'type'.")
            inner = _coords_wkt(value, type_name)
            return WKTElement(f"SRID={SRID};{type_name.upper()}({inner})", srid=SRID)

        raise bad_request(f"'{name}'.geometry must be a WKT/EWKT string or GeoJSON object.")
    except ValueError as exc:
        raise bad_request(f"'geometry' could not be parsed: {exc}") from exc
