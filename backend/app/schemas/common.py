"""Shared response/error schemas and small reusable models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base schema with ORM attribute loading enabled."""

    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list = []


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthResponse(BaseModel):
    status: str
    version: str
    time: datetime


class DatabaseHealthResponse(BaseModel):
    status: str
    database: bool
    postgis: bool
    postgis_version: str | None = None
    time: datetime
