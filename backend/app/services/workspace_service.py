"""Workspace business logic and access control.

Access model (backend-enforced):

- An organization owner/admin can create, update, and manage workspaces.
- A workspace ``manager`` can update the workspace and manage its members.
- A workspace ``member`` can view the workspace.
- Any member of an organization can view that organization's workspaces.

The workspace creator automatically becomes its ``manager``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.core.slugs import unique_slug
from app.models import Organization, OrganizationMember, User, Workspace, WorkspaceMember
from app.schemas import workspace as ws_schemas
from app.services import organization_service


def _workspace_membership(db: Session, workspace_id: int, user_id: int) -> WorkspaceMember | None:
    return db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    ).scalar_one_or_none()


def _org_role(db: Session, organization_id: int, user_id: int) -> str | None:
    membership = db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    ).scalar_one_or_none()
    return membership.role if membership else None


def _get_workspace(db: Session, workspace_id: int) -> Workspace:
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise not_found("Workspace not found.", code="workspace_not_found")
    return workspace


def is_accesible(db: Session, workspace: Workspace, user_id: int) -> bool:
    direct = _workspace_membership(db, workspace.id, user_id)
    if direct is not None:
        return True
    org_role = _org_role(db, workspace.organization_id, user_id)
    return org_role in ("owner", "admin", "member")


def require_member(db: Session, workspace_id: int, user_id: int) -> WorkspaceMember:
    workspace = _get_workspace(db, workspace_id)
    if not is_accesible(db, workspace, user_id):
        raise not_found("Workspace not found.", code="workspace_not_found")
    return _workspace_membership(db, workspace_id, user_id)


def create(
    db: Session, user_id: int, organization_id: int, data: ws_schemas.WorkspaceCreate
) -> Workspace:
    organization_service.require_member(db, organization_id, user_id, roles=("owner", "admin"))
    if db.get(Organization, organization_id) is None:
        raise not_found("Organization not found.", code="organization_not_found")
    slug = data.slug or unique_slug(db, Workspace, data.name)
    workspace = Workspace(
        organization_id=organization_id,
        created_by=user_id,
        name=data.name,
        slug=slug,
        description=data.description,
    )
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, role="manager"))
    db.flush()
    return workspace


def list_for_user(db: Session, user_id: int) -> list[dict]:
    """Workspaces the user can access, with their effective role.

    A user can access a workspace through a direct membership (role from that
    membership) or as a member of the owning organization (view role).
    """
    org_ids = [
        org_id
        for (org_id,) in db.execute(
            select(OrganizationMember.organization_id).where(OrganizationMember.user_id == user_id)
        ).all()
    ]
    direct = (
        db.execute(
            select(WorkspaceMember).where(WorkspaceMember.user_id == user_id).join(Workspace)
        )
        .scalars()
        .all()
    )
    direct_by_ws = {m.workspace_id: m.role for m in direct}

    query = select(Workspace).order_by(Workspace.name)
    rows = db.execute(query).scalars().all()
    accessible = [
        ws for ws in rows if ws.id in direct_by_ws or (org_ids and ws.organization_id in org_ids)
    ]
    return [
        {
            "id": ws.id,
            "organization_id": ws.organization_id,
            "name": ws.name,
            "slug": ws.slug,
            "description": ws.description,
            "created_at": ws.created_at,
            "updated_at": ws.updated_at,
            "role": direct_by_ws.get(ws.id) or "member",
        }
        for ws in accessible
    ]


def get_for_user(db: Session, user_id: int, workspace_id: int) -> Workspace:
    workspace = _get_workspace(db, workspace_id)
    if not is_accesible(db, workspace, user_id):
        raise not_found("Workspace not found.", code="workspace_not_found")
    return workspace


def update(
    db: Session, user_id: int, workspace_id: int, data: ws_schemas.WorkspaceUpdate
) -> Workspace:
    workspace = _get_workspace(db, workspace_id)
    org_role = _org_role(db, workspace.organization_id, user_id)
    direct_role = _workspace_membership(db, workspace_id, user_id)
    can_manage = org_role in ("owner", "admin") or (direct_role and direct_role.role == "manager")
    if not can_manage:
        raise forbidden("You cannot update this workspace.")
    if data.name is not None:
        workspace.name = data.name
    if data.slug is not None:
        workspace.slug = data.slug
    if data.description is not None:
        workspace.description = data.description
    db.flush()
    return workspace


def list_by_organization(db: Session, organization_id: int, user_id: int) -> list[dict]:
    """Workspaces of an organization that ``user_id`` can view, with role."""
    direct = (
        db.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
            .join(Workspace)
            .where(Workspace.organization_id == organization_id)
        )
        .scalars()
        .all()
    )
    direct_by_ws = {m.workspace_id: m.role for m in direct}
    workspaces = (
        db.execute(
            select(Workspace)
            .where(Workspace.organization_id == organization_id)
            .order_by(Workspace.name)
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": ws.id,
            "organization_id": ws.organization_id,
            "name": ws.name,
            "slug": ws.slug,
            "description": ws.description,
            "created_at": ws.created_at,
            "updated_at": ws.updated_at,
            "role": direct_by_ws.get(ws.id) or "member",
        }
        for ws in workspaces
    ]


def add_member(db: Session, actor_id: int, workspace_id: int, user_id: int) -> WorkspaceMember:
    workspace = _get_workspace(db, workspace_id)
    org_role = _org_role(db, workspace.organization_id, actor_id)
    direct_role = _workspace_membership(db, workspace_id, actor_id)
    can_manage = org_role in ("owner", "admin") or (direct_role and direct_role.role == "manager")
    if not can_manage:
        raise forbidden("You cannot manage members of this workspace.")
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User not found.", code="user_not_found")
    if _workspace_membership(db, workspace_id, user_id) is not None:
        raise bad_request("User is already a member of this workspace.", code="already_member")
    membership = WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role="member")
    db.add(membership)
    db.flush()
    return membership


def list_members(db: Session, workspace_id: int) -> list[WorkspaceMember]:
    return (
        db.execute(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id))
        .scalars()
        .all()
    )


def remove_member(db: Session, actor_id: int, workspace_id: int, user_id: int) -> None:
    workspace = _get_workspace(db, workspace_id)
    org_role = _org_role(db, workspace.organization_id, actor_id)
    direct_role = _workspace_membership(db, workspace_id, actor_id)
    can_manage = org_role in ("owner", "admin") or (direct_role and direct_role.role == "manager")
    if not can_manage:
        raise forbidden("You cannot manage members of this workspace.")
    target = _workspace_membership(db, workspace_id, user_id)
    if target is None:
        raise not_found("Member not found.", code="member_not_found")
    db.delete(target)
    db.flush()
