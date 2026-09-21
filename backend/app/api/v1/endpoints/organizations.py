"""Organization endpoints (roles: owner / admin / member)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import organization as org_schemas
from app.schemas import workspace as ws_schemas
from app.services import organization_service, workspace_service

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get(
    "",
    response_model=list[org_schemas.OrganizationResponse],
    summary="List organizations I belong to",
)
def list_organizations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return organization_service.list_for_user(db, user.id)


@router.post(
    "",
    response_model=org_schemas.OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization",
)
def create_organization(
    data: org_schemas.OrganizationCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    organization = organization_service.create(db, user, data)
    db.commit()
    return org_schemas.OrganizationResponse.model_validate(
        {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "description": organization.description,
            "created_at": organization.created_at,
            "updated_at": organization.updated_at,
            "role": "owner",
        }
    )


@router.get(
    "/{organization_id}",
    response_model=org_schemas.OrganizationDetailResponse,
    summary="Organization detail with members",
)
def get_organization(
    organization_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return organization_service.get_for_user(db, user.id, organization_id)


@router.patch(
    "/{organization_id}",
    response_model=org_schemas.OrganizationResponse,
    summary="Update organization (owner/admin)",
)
def update_organization(
    organization_id: int,
    data: org_schemas.OrganizationUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    organization = organization_service.update(db, user.id, organization_id, data)
    membership = organization_service.get_membership_or_404(db, organization_id, user.id)
    db.commit()
    return org_schemas.OrganizationResponse.model_validate(
        {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "description": organization.description,
            "created_at": organization.created_at,
            "updated_at": organization.updated_at,
            "role": membership.role,
        }
    )


@router.get(
    "/{organization_id}/members",
    response_model=list[org_schemas.OrganizationMemberResponse],
    summary="List organization members",
)
def list_members(
    organization_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return organization_service.list_members(db, organization_id, user.id)


@router.post(
    "/{organization_id}/members",
    response_model=org_schemas.OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member (owner/admin)",
)
def add_member(
    organization_id: int,
    data: org_schemas.MemberAddRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    membership = organization_service.add_member(
        db, user.id, organization_id, data.user_id, data.role
    )
    db.commit()
    return org_schemas.OrganizationMemberResponse.model_validate(membership)


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=org_schemas.OrganizationMemberResponse,
    summary="Update a member's role (owner/admin)",
)
def update_member_role(
    organization_id: int,
    user_id: int,
    data: org_schemas.MemberRoleUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    membership = organization_service.update_member_role(
        db, user.id, organization_id, user_id, data.role
    )
    db.commit()
    return org_schemas.OrganizationMemberResponse.model_validate(membership)


@router.delete(
    "/{organization_id}/members/{user_id}",
    response_model=org_schemas.MemberRemoveResponse,
    summary="Remove a member (owner/admin)",
)
def remove_member(
    organization_id: int,
    user_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    organization_service.remove_member(db, user.id, organization_id, user_id)
    db.commit()
    return org_schemas.MemberRemoveResponse()


@router.get(
    "/{organization_id}/workspaces",
    response_model=list[ws_schemas.WorkspaceResponse],
    summary="List workspaces in an organization",
)
def list_organization_workspaces(
    organization_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    organization_service.get_membership_or_404(db, organization_id, user.id)
    return workspace_service.list_by_organization(db, organization_id, user.id)


@router.post(
    "/{organization_id}/workspaces",
    response_model=ws_schemas.WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workspace (owner/admin)",
)
def create_workspace(
    organization_id: int,
    data: ws_schemas.WorkspaceCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = workspace_service.create(db, user.id, organization_id, data)
    db.commit()
    return ws_schemas.WorkspaceResponse.model_validate(
        {
            "id": workspace.id,
            "organization_id": workspace.organization_id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
            "role": "manager",
        }
    )
