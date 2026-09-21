"""Domain error type and consistent error response shape.

Every API error is returned as:

    {"error": {"code": "<machine-code>", "message": "<human message>", "details": [...]}}
"""

from __future__ import annotations


class ApiError(Exception):
    """An application-level error with an HTTP status and a stable code."""

    def __init__(
        self, status_code: int, code: str, message: str, details: list | None = None
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


def not_found(message: str = "Resource not found.", code: str = "not_found") -> ApiError:
    return ApiError(404, code, message)


def forbidden(
    message: str = "You do not have permission to perform this action.", code: str = "forbidden"
) -> ApiError:
    return ApiError(403, code, message)


def unauthorized(message: str = "Authentication required.", code: str = "unauthorized") -> ApiError:
    return ApiError(401, code, message)


def conflict(message: str = "Resource already exists.", code: str = "conflict") -> ApiError:
    return ApiError(409, code, message)


def bad_request(message: str, code: str = "bad_request") -> ApiError:
    return ApiError(400, code, message)
