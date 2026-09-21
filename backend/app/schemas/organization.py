"""Organization and membership schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserSummary

OrganizationRole = Literal["owner", "admin", "member"]
ORGANIZATION_ROLES = ("owner", "admin", "member")


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$", max_length=100
    )
    description: str | None = Field(default=None, max_length=1000)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(
        default=None, pattern=r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$", max_length=100
    )
    description: str | None = Field(default=None, max_length=1000)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    role: OrganizationRole


class OrganizationMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: int
    role: OrganizationRole
    created_at: datetime
    user: UserSummary


class OrganizationDetailResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    role: OrganizationRole
    members: list[OrganizationMemberResponse]


class MemberAddRequest(BaseModel):
    user_id: int
    role: Literal["admin", "member"] = "member"


class MemberRoleUpdateRequest(BaseModel):
    role: Literal["owner", "admin", "member"]


class MemberRemoveResponse(BaseModel):
    ok: bool = True
