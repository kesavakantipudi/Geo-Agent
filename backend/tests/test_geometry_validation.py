"""Phase 3 geometry validation tests (shapely-based, pure + endpoint)."""

from __future__ import annotations

import pytest

from app.core.exceptions import ApiError
from app.services import geometry as geometry_service

SRID = 4326


def _polygon(*points) -> dict:
    coords = [list(p) for p in points]
    coords.append(list(points[0]))
    return {"type": "Polygon", "coordinates": [coords]}


class TestValidateGeometry:
    def test_valid_point(self):
        info = geometry_service.validate_geometry(
            {"type": "Point", "coordinates": [77.5946, 12.9716]}
        )
        assert info["geometry_type"] == "Point"
        assert info["is_valid"] is True
        assert info["point_count"] == 1
        assert info["bbox"] == [77.5946, 12.9716, 77.5946, 12.9716]
        assert info["centroid"] == {"lon": 77.5946, "lat": 12.9716}
        assert info["area_m2_approx"] == 0.0

    def test_valid_polygon_area_and_centroid(self):
        info = geometry_service.validate_geometry(
            {
                "type": "Polygon",
                "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
            }
        )
        assert info["geometry_type"] == "Polygon"
        assert info["bbox"] == [0.0, 0.0, 1.0, 1.0]
        assert info["centroid"] == {"lon": 0.5, "lat": 0.5}
        # ~ (111.32 km)^2 for a 1°x1° square near the equator
        assert 1.1e10 <= info["area_m2_approx"] <= 1.4e10

    def test_out_of_range_longitude_rejected(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry({"type": "Point", "coordinates": [200.0, 0.0]})
        assert exc.value.status_code == 400
        assert "out of range" in exc.value.message

    def test_out_of_range_latitude_rejected(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry({"type": "Point", "coordinates": [0.0, 91.0]})
        assert exc.value.status_code == 400

    def test_open_ring_rejected(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry(
                {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}
            )
        assert exc.value.status_code == 400
        assert "closed ring" in exc.value.message

    def test_self_intersecting_polygon_rejected(self):
        bowtie = {"type": "Polygon", "coordinates": [[[0, 0], [2, 2], [0, 2], [2, 0], [0, 0]]]}
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry(bowtie)
        assert exc.value.status_code == 400
        assert "not valid" in exc.value.message.lower()

    def test_unknown_type_rejected(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry({"type": "Doughnut", "coordinates": []})
        assert exc.value.status_code == 400

    def test_non_closed_line_rejected(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry({"type": "LineString", "coordinates": [[0, 0]]})
        assert exc.value.status_code == 400

    def test_too_many_points_rejected(self):
        edge = 2001
        points = [(0.001 * i, 0.0) for i in range(edge)]
        geometry = {"type": "LineString", "coordinates": [list(p) for p in points]}
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry(geometry)
        assert exc.value.status_code == 400
        assert exc.value.code == "geometry_too_complex"

    def test_ewkt_string_srid_mismatch_rejected(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry("SRID=3857;POINT(0 0)")
        assert exc.value.status_code == 400
        assert "Only SRID" in exc.value.message

    def test_ewkt_string_round_trip(self):
        element = geometry_service.parse_geometry("loc", "SRID=4326;POINT(81.83 17.0)")
        assert element.srid == 4326
        assert "POINT" in element.data

    def test_geojson_feature_wrapper_unwrapped(self):
        info = geometry_service.validate_geometry(
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [81.0, 17.0]}}
        )
        assert info["geometry_type"] == "Point"

    def test_feature_collection_with_multiple_rejected(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [0, 0]}},
                        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 1]}},
                    ],
                }
            )
        assert exc.value.status_code == 400

    def test_require_area_rejects_point(self):
        with pytest.raises(ApiError) as exc:
            geometry_service.validate_geometry(
                {"type": "Point", "coordinates": [0, 0]}, require_area=True
            )
        assert exc.value.status_code == 400
        assert exc.value.code == "aoi_not_polygon"

    def test_require_area_accepts_polygon(self):
        info = geometry_service.validate_geometry(
            _polygon((0, 0), (1, 0), (1, 1), (0, 1)), require_area=True
        )
        assert info["geometry_type"] == "Polygon"

    def test_multipolygon_with_hole_area(self):
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]],
                    [[0.5, 0.5], [1.5, 0.5], [1.5, 1.5], [0.5, 1.5], [0.5, 0.5]],
                ]
            ],
        }
        info = geometry_service.validate_geometry(geometry)
        assert info["geometry_type"] == "MultiPolygon"
        assert info["area_m2_approx"] > 1e9

    def test_invalid_ewkt_rejected(self):
        with pytest.raises(ApiError):
            geometry_service.validate_geometry("SRID=4326;POINT(not a number)")


class TestValidateEndpoint:
    def test_unauthenticated_rejected(self, client):
        response = client.post(
            "/api/v1/geometries/validate",
            json={"geometry": {"type": "Point", "coordinates": [0, 0]}},
        )
        assert response.status_code == 401

    def test_valid_geometry_returned(self, client):
        register(client)
        response = client.post(
            "/api/v1/geometries/validate",
            json={"geometry": {"type": "Point", "coordinates": [77.5946, 12.9716]}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["geometry_type"] == "Point"
        assert body["srid"] == SRID
        assert body["bbox"] == [77.5946, 12.9716, 77.5946, 12.9716]

    def test_invalid_geometry_returns_400(self, client):
        register(client)
        response = client.post(
            "/api/v1/geometries/validate",
            json={"geometry": {"type": "Point", "coordinates": [999.0, 0.0]}},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "bad_request"

    def test_require_area_via_endpoint(self, client):
        register(client)
        response = client.post(
            "/api/v1/geometries/validate",
            json={
                "geometry": {"type": "Point", "coordinates": [0, 0]},
                "require_area": True,
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "aoi_not_polygon"


def register(client):
    from conftest import register_user as _register

    _register(client, "geom@example.com", "geomuser")
