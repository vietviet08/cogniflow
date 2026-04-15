import uuid
from typing import Annotated
import secrets

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import hash_password, require_current_user, require_organization_role
from app.services.audit_service import log_audit_event
from app.storage.models import User, OrganizationMembership, Organization
from app.storage.repositories.organization_repository import OrganizationRepository
from app.storage.repositories.organization_membership_repository import OrganizationMembershipRepository
from app.storage.repositories.user_repository import UserRepository

router = APIRouter(prefix="/organizations")


DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]

class CreateOrganizationRequest(BaseModel):
    name: str

@router.post("")
def create_organization(
    payload: CreateOrganizationRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    repo = OrganizationRepository(db)
    membership_repo = OrganizationMembershipRepository(db)
    
    org = repo.create(name=payload.name)
    membership_repo.create(
        organization_id=org.id,
        user_id=current_user.id,
        role="owner"
    )
    return success_response(
        request,
        {
            "id": str(org.id),
            "name": org.name,
        },
        status_code=201,
    )

@router.get("")
def list_organizations(
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    # If superadmin, arguably return all orgs, but for now normal path
    orgs = (
        db.query(Organization, OrganizationMembership.role)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .filter(OrganizationMembership.user_id == current_user.id)
        .order_by(Organization.created_at.desc())
        .all()
    )
    
    return success_response(
        request,
        {
            "items": [
                {
                    "id": str(org.id),
                    "name": org.name,
                    "slug": org.slug,
                    "role": role,
                }
                for org, role in orgs
            ],
            "total": len(orgs)
        }
    )

@router.get("/{organization_id}/members")
def list_organization_members(
    organization_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_organization_role(db, organization_id=organization_id, user=current_user, minimum_role="admin")
    
    members = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == organization_id)
        .all()
    )
    
    return success_response(
        request,
        {
            "items": [
                {
                    "membership_id": str(m.id),
                    "user_id": str(u.id),
                    "email": u.email,
                    "display_name": u.display_name,
                    "role": m.role,
                    "joined_at": m.created_at.isoformat() if m.created_at else None
                }
                for m, u in members
            ]
        }
    )

class AddMemberRequest(BaseModel):
    email: str
    role: str = "member"


def _display_name_from_email(email: str) -> str:
    local_part = email.split("@", maxsplit=1)[0].strip() or "user"
    return local_part.replace(".", " ").replace("_", " ").title()

@router.post("/{organization_id}/members")
def add_organization_member(
    organization_id: uuid.UUID,
    payload: AddMemberRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_organization_role(db, organization_id=organization_id, user=current_user, minimum_role="admin")

    if payload.role not in ["owner", "admin", "member"]:
        return error_response(
            request,
            code="ORG_ROLE_INVALID",
            message="Invalid role.",
            status_code=400,
        )

    user_repo = UserRepository(db)
    user_to_add = user_repo.get_by_email(payload.email)
    created_new_user = False
    if not user_to_add:
        # Provision a basic user account and attach it to the current organization.
        temporary_password = secrets.token_urlsafe(24)
        user_to_add = user_repo.create(
            email=payload.email,
            display_name=_display_name_from_email(payload.email),
            password_hash=hash_password(temporary_password),
            role="user",
        )
        created_new_user = True

    membership_repo = OrganizationMembershipRepository(db)
    # Check if already in org
    existing = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_to_add.id
    ).first()
    
    if existing:
        return error_response(
            request,
            code="ORG_MEMBER_EXISTS",
            message="User is already a member.",
            status_code=400,
        )

    membership = membership_repo.create(
        organization_id=organization_id,
        user_id=user_to_add.id,
        role=payload.role
    )
    log_audit_event(
        db,
        action="organization.member.add",
        target_type="organization_membership",
        target_id=str(membership.id),
        user_id=current_user.id,
        organization_id=organization_id,
        payload={
            "member_user_id": str(user_to_add.id),
            "role": payload.role,
            "created_new_user": created_new_user,
        },
    )
    db.commit()
    
    return success_response(
        request,
        {
            "membership_id": str(membership.id),
            "user_id": str(user_to_add.id),
            "role": membership.role,
            "created_new_user": created_new_user,
        },
        status_code=201
    )

class UpdateMemberRequest(BaseModel):
    role: str

@router.patch("/{organization_id}/members/{user_id}")
def update_organization_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateMemberRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_organization_role(db, organization_id=organization_id, user=current_user, minimum_role="admin")
    
    if payload.role not in ["owner", "admin", "member"]:
        return error_response(
            request,
            code="ORG_ROLE_INVALID",
            message="Invalid role.",
            status_code=400,
        )
        
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id
    ).first()
    
    if not membership:
        return error_response(
            request,
            code="ORG_MEMBERSHIP_NOT_FOUND",
            message="Membership not found.",
            status_code=404,
        )
        
    # Prevent changing own role if owner, or requires owner to change owner
    # For simplicity, if changing someone to owner, you must be owner.
    current_user_role = db.query(OrganizationMembership.role).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == current_user.id
    ).scalar()
    
    if payload.role == "owner" and current_user_role != "owner":
        return error_response(
            request,
            code="ORG_OWNER_REQUIRED",
            message="Only owners can grant owner role.",
            status_code=403,
        )
        
    membership.role = payload.role
    log_audit_event(
        db,
        action="organization.member.update_role",
        target_type="organization_membership",
        target_id=str(membership.id),
        user_id=current_user.id,
        organization_id=organization_id,
        payload={"member_user_id": str(user_id), "role": payload.role},
    )
    db.commit()
    
    return success_response(request, {"role": membership.role})

@router.delete("/{organization_id}/members/{user_id}")
def remove_organization_member(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_organization_role(db, organization_id=organization_id, user=current_user, minimum_role="admin")
    
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == user_id
    ).first()
    
    if not membership:
        return error_response(
            request,
            code="ORG_MEMBERSHIP_NOT_FOUND",
            message="Membership not found.",
            status_code=404,
        )
        
    # Prevent removing the last owner? We skip that check for now, but prevent removing oneself if owner
    current_user_role = db.query(OrganizationMembership.role).filter(
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.user_id == current_user.id
    ).scalar()
    
    if membership.role == "owner" and current_user_role != "owner":
        return error_response(
            request,
            code="ORG_OWNER_REQUIRED",
            message="Only owners can remove owners.",
            status_code=403,
        )

    log_audit_event(
        db,
        action="organization.member.remove",
        target_type="organization_membership",
        target_id=str(membership.id),
        user_id=current_user.id,
        organization_id=organization_id,
        payload={"member_user_id": str(user_id)},
    )
        
    db.delete(membership)
    db.commit()
    
    return success_response(request, {"success": True})
