"""Organization business logic and role enforcement.

Role model (backend-enforced):

- ``owner``  — full control: update org, manage members (including changing roles), create workspaces.
- ``admin``  — update org, create workspaces, manage members (not owner).
- ``member`` — view the organization and its workspaces.

The creator of an organization becomes its owner.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import bad_request, forbidden, not_found
from app.core.slugs import unique_slug
from app.models import Organization, OrganizationMember, User
from app.schemas import organization as org_schemas

ORGANIZATION_ROLES = ("owner", "admin", "member")
MANAGING_ROLES = ("owner", "admin")


def _membership(db: Session, organization_id: int, user_id: int) -> OrganizationMember | None:
    return db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    ).scalar_one_or_none()


def get_membership_or_404(db: Session, organization_id: int, user_id: int) -> OrganizationMember:
    membership = _membership(db, organization_id, user_id)
    if membership is None:
        raise not_found("Organization not found.", code="organization_not_found")
    return membership


def require_member(
    db: Session, organization_id: int, user_id: int, *, roles: tuple[str, ...] = ORGANIZATION_ROLES
) -> OrganizationMember:
    membership = get_membership_or_404(db, organization_id, user_id)
    if membership.role not in roles:
        raise forbidden("You do not have the required organization role.")
    return membership


def list_for_user(db: Session, user_id: int) -> list[dict]:
    memberships = (
        db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.user_id == user_id)
            .join(Organization)
            .order_by(Organization.name)
        )
        .scalars()
        .all()
    )
    return [
        org_schemas.OrganizationResponse.model_validate(
            {
                "id": m.organization.id,
                "name": m.organization.name,
                "slug": m.organization.slug,
                "description": m.organization.description,
                "created_at": m.organization.created_at,
                "updated_at": m.organization.updated_at,
                "role": m.role,
            }
        ).model_dump(mode="json")
        for m in memberships
    ]


def create(db: Session, user: User, data: org_schemas.OrganizationCreate) -> Organization:
    slug = data.slug or unique_slug(db, Organization, data.name)
    organization = Organization(name=data.name, slug=slug, description=data.description)
    db.add(organization)
    db.flush()
    db.add(OrganizationMember(organization_id=organization.id, user_id=user.id, role="owner"))
    db.flush()
    return organization


def list_members(db: Session, organization_id: int, user_id: int | None = None) -> list[dict]:
    if user_id is not None:
        get_membership_or_404(db, organization_id, user_id)
    members = (
        db.execute(
            select(OrganizationMember)
            .where(OrganizationMember.organization_id == organization_id)
            .join(User)
        )
        .scalars()
        .all()
    )
    return [
        org_schemas.OrganizationMemberResponse(
            id=m.id,
            organization_id=m.organization_id,
            user_id=m.user_id,
            role=m.role,
            created_at=m.created_at,
            user={
                "id": m.user.id,
                "email": m.user.email,
                "username": m.user.username,
                "full_name": m.user.full_name,
            },
        ).model_dump(mode="json")
        for m in members
    ]


def get_for_user(db: Session, user_id: int, organization_id: int) -> dict:
    membership = get_membership_or_404(db, organization_id, user_id)
    org = db.get(Organization, organization_id)
    if org is None:
        raise not_found("Organization not found.", code="organization_not_found")
    return org_schemas.OrganizationDetailResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        description=org.description,
        created_at=org.created_at,
        updated_at=org.updated_at,
        role=membership.role,
        members=list_members(db, organization_id),
    ).model_dump(mode="json")


def update(
    db: Session, user_id: int, organization_id: int, data: org_schemas.OrganizationUpdate
) -> Organization:
    require_member(db, organization_id, user_id, roles=MANAGING_ROLES)
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise not_found("Organization not found.", code="organization_not_found")
    if data.name is not None:
        organization.name = data.name
    if data.slug is not None:
        organization.slug = data.slug
    if data.description is not None:
        organization.description = data.description
    db.flush()
    return organization


def add_member(
    db: Session, actor_id: int, organization_id: int, user_id: int, role: str
) -> OrganizationMember:
    require_member(db, organization_id, actor_id, roles=MANAGING_ROLES)
    if role not in ("admin", "member"):
        raise bad_request("Only 'admin' or 'member' roles can be assigned to a new member.")
    if _membership(db, organization_id, user_id) is not None:
        raise bad_request("User is already a member of this organization.", code="already_member")
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User not found.", code="user_not_found")
    membership = OrganizationMember(organization_id=organization_id, user_id=user_id, role=role)
    db.add(membership)
    db.flush()
    return membership


def update_member_role(
    db: Session, actor_id: int, organization_id: int, user_id: int, role: str
) -> OrganizationMember:
    require_member(db, organization_id, actor_id, roles=MANAGING_ROLES)
    target = _membership(db, organization_id, user_id)
    if target is None:
        raise not_found("Member not found.", code="member_not_found")
    if target.role == "owner":
        if actor_id != user_id:
            raise forbidden("The owner's role cannot be changed by another member.")
        if role != "owner":
            raise bad_request("The owner's role cannot be demoted while no other owner exists.")
    if role not in ORGANIZATION_ROLES:
        raise bad_request(f"Invalid role '{role}'. Valid roles: {', '.join(ORGANIZATION_ROLES)}.")
    target.role = role
    db.flush()
    return target


def remove_member(db: Session, actor_id: int, organization_id: int, user_id: int) -> None:
    require_member(db, organization_id, actor_id, roles=MANAGING_ROLES)
    target = _membership(db, organization_id, user_id)
    if target is None:
        raise not_found("Member not found.", code="member_not_found")
    if target.role == "owner":
        raise forbidden("The organization owner cannot be removed.")
    db.delete(target)
    db.flush()
