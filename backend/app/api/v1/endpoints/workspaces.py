"""Workspace endpoints (roles: manager / member; org owner/admin can manage)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User
from app.schemas import workspace as ws_schemas
from app.services import workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get(
    "", response_model=list[ws_schemas.WorkspaceResponse], summary="List workspaces I can access"
)
def list_workspaces(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return workspace_service.list_for_user(db, user.id)


@router.get(
    "/{workspace_id}", response_model=ws_schemas.WorkspaceResponse, summary="Workspace detail"
)
def get_workspace(
    workspace_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = workspace_service.get_for_user(db, user.id, workspace_id)
    membership = workspace_service._workspace_membership(db, workspace_id, user.id)
    return ws_schemas.WorkspaceResponse.model_validate(
        {
            "id": workspace.id,
            "organization_id": workspace.organization_id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
            "role": membership.role if membership else "member",
        }
    )


@router.patch(
    "/{workspace_id}",
    response_model=ws_schemas.WorkspaceResponse,
    summary="Update workspace (org owner/admin or workspace manager)",
)
def update_workspace(
    workspace_id: int,
    data: ws_schemas.WorkspaceUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace = workspace_service.update(db, user.id, workspace_id, data)
    db.commit()
    membership = workspace_service._workspace_membership(db, workspace_id, user.id)
    return ws_schemas.WorkspaceResponse.model_validate(
        {
            "id": workspace.id,
            "organization_id": workspace.organization_id,
            "name": workspace.name,
            "slug": workspace.slug,
            "description": workspace.description,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at,
            "role": membership.role if membership else "member",
        }
    )


@router.get(
    "/{workspace_id}/members",
    response_model=list[ws_schemas.WorkspaceMemberResponse],
    summary="List workspace members",
)
def list_members(
    workspace_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace_service.get_for_user(db, user.id, workspace_id)
    members = workspace_service.list_members(db, workspace_id)
    return [
        ws_schemas.WorkspaceMemberResponse(
            id=m.id,
            workspace_id=m.workspace_id,
            user_id=m.user_id,
            role=m.role,
            created_at=m.created_at,
            user={
                "id": m.user.id,
                "email": m.user.email,
                "username": m.user.username,
                "full_name": m.user.full_name,
            },
        )
        for m in members
    ]


@router.post(
    "/{workspace_id}/members",
    response_model=ws_schemas.WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a workspace member",
)
def add_member(
    workspace_id: int,
    data: ws_schemas.WorkspaceMemberAddRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    membership = workspace_service.add_member(db, user.id, workspace_id, data.user_id)
    db.commit()
    return ws_schemas.WorkspaceMemberResponse.model_validate(membership)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    response_model=ws_schemas.WorkspaceMemberRemoveResponse,
    summary="Remove a workspace member",
)
def remove_member(
    workspace_id: int,
    user_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    workspace_service.remove_member(db, user.id, workspace_id, user_id)
    db.commit()
    return ws_schemas.WorkspaceMemberRemoveResponse()
