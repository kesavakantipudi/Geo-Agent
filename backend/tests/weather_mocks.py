"""Shared builders and fake provider handlers for the Phase 5 weather tests.

No live network access: every provider ``httpx.Client`` is routed through an
``httpx.MockTransport`` handler (same mechanism as the Phase 4 satellite mocks).
"""

from __future__ import annotations

from typing import Any

FORECAST_HOST = "api.open-meteo.com"
ARCHIVE_HOST = "archive-api.open-meteo.com"

TIMES = ["2024-07-05T00:00", "2024-07-05T01:00", "2024-07-05T02:00"]


def openmeteo_payload(
    *,
    times: list[str] | None = None,
    variables: dict[str, list[Any]] | None = None,
    units: dict[str, str] | None = None,
    timezone: str = "UTC",
    lat: float = 12.95,
    lon: float = 77.55,
    model: str | None = None,
) -> dict[str, Any]:
    """Build an Open-Meteo-style ``hourly`` response payload."""
    times = times or TIMES
    variables = variables or {
        "temperature_2m": [23.5, 23.1, 22.8],
        "relative_humidity_2m": [82, 80, 79],
    }
    hourly_units = {"time": "iso8601"}
    hourly: dict[str, list[Any]] = {"time": times}
    for var, values in variables.items():
        hourly[var] = values
        hourly_units[var] = (units or {}).get(var, "°C")
    payload: dict[str, Any] = {
        "latitude": lat,
        "longitude": lon,
        "timezone": timezone,
        "hourly_units": hourly_units,
        "hourly": hourly,
    }
    if model:
        payload["model"] = model
    return payload


def weather_handler(
    payload: dict[str, Any] | None = None,
    *,
    archive_payload: dict[str, Any] | None = None,
    historical_payload: dict[str, Any] | None = None,
    error: tuple[int, str] | None = None,
    raise_timeout: bool = False,
    captured: list[dict[str, Any]] | None = None,
):
    """Build an ``httpx.MockTransport`` handler for Open-Meteo endpoints."""
    forecast = payload if payload is not None else openmeteo_payload()
    archive = archive_payload if archive_payload is not None else forecast
    historical = historical_payload if historical_payload is not None else forecast

    def handler(request) -> Any:
        import httpx

        url = str(request.url)
        if captured is not None:
            captured.append({"url": url, "body": request.content})
        if raise_timeout:
            raise httpx.ConnectTimeout("connection timed out", request=request)
        if error is not None:
            return httpx.Response(error[0], json={"reason": error[1]})
        if ARCHIVE_HOST in url:
            return httpx.Response(200, json=archive)
        if "historical-forecast-api" in url:
            return httpx.Response(200, json=historical)
        return httpx.Response(200, json=forecast)

    return handler
