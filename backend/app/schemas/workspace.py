"""Workspace and membership schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserSummary

WorkspaceRole = Literal["manager", "member"]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$", max_length=100
    )
    description: str | None = Field(default=None, max_length=1000)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$", max_length=100
    )
    description: str | None = Field(default=None, max_length=1000)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    slug: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    role: WorkspaceRole


class WorkspaceMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    user_id: int
    role: WorkspaceRole
    created_at: datetime
    user: UserSummary


class WorkspaceMemberAddRequest(BaseModel):
    user_id: int


class WorkspaceMemberRemoveResponse(BaseModel):
    ok: bool = True
