"""
Organizations API — multi-tenancy management.
"""
from __future__ import annotations

import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user, require_admin
from app.persistence.database import SessionLocal
from app.persistence.models import Organization, User, UserRole

router = APIRouter(prefix="/organizations", tags=["organizations"])


def get_db():
    with SessionLocal() as db:
        yield db


DbDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[dict, Depends(get_current_user)]
AdminDep = Annotated[dict, Depends(require_admin)]


class OrgCreate(BaseModel):
    name: str
    slug: str | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v.strip()

    @field_validator("slug")
    @classmethod
    def slug_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[a-z0-9-]{2,64}$", v):
            raise ValueError("slug must be lowercase alphanumeric with dashes, 2-64 chars")
        return v


class OrgUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None


class OrgOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    active: bool
    member_count: int


class MemberAdd(BaseModel):
    user_id: uuid.UUID


class MemberOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    org_id: uuid.UUID | None


@router.get("", response_model=list[OrgOut])
def list_organizations(db: DbDep, user: UserDep):
    is_admin = user.get("role") == "admin"
    if is_admin:
        orgs = db.query(Organization).all()
    else:
        # Regular users see only their own org (looked up by user UUID from JWT sub)
        import uuid as _uuid
        db_user = db.query(User).filter(User.id == _uuid.UUID(user.get("sub"))).first()
        org_id = getattr(db_user, "org_id", None) if db_user else None
        if not org_id:
            return []
        org = db.get(Organization, org_id)
        orgs = [org] if org else []

    result = []
    for org in orgs:
        count = db.query(User).filter(User.org_id == org.id).count()
        result.append(OrgOut(id=org.id, name=org.name, slug=org.slug,
                             active=org.active, member_count=count))
    return result


@router.post("", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_organization(body: OrgCreate, db: DbDep, _: AdminDep):
    slug = body.slug or re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")[:64]

    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=409, detail=f"Slug '{slug}' already taken")
    if db.query(Organization).filter(Organization.name == body.name).first():
        raise HTTPException(status_code=409, detail=f"Name '{body.name}' already taken")

    org = Organization(id=uuid.uuid4(), name=body.name, slug=slug)
    db.add(org)
    db.commit()
    db.refresh(org)
    return OrgOut(id=org.id, name=org.name, slug=org.slug, active=org.active, member_count=0)


@router.get("/{org_id}", response_model=OrgOut)
def get_organization(org_id: uuid.UUID, db: DbDep, user: UserDep):
    org = _get_org_or_404(db, org_id)
    _check_access(user, org_id)
    count = db.query(User).filter(User.org_id == org.id).count()
    return OrgOut(id=org.id, name=org.name, slug=org.slug, active=org.active, member_count=count)


@router.patch("/{org_id}", response_model=OrgOut)
def update_organization(org_id: uuid.UUID, body: OrgUpdate, db: DbDep, _: AdminDep):
    org = _get_org_or_404(db, org_id)
    if body.name is not None:
        org.name = body.name
    if body.active is not None:
        org.active = body.active
    db.commit()
    count = db.query(User).filter(User.org_id == org.id).count()
    return OrgOut(id=org.id, name=org.name, slug=org.slug, active=org.active, member_count=count)


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization(org_id: uuid.UUID, db: DbDep, _: AdminDep):
    org = _get_org_or_404(db, org_id)
    if org.slug == "default":
        raise HTTPException(status_code=403, detail="Cannot delete the default organization")
    org.active = False
    db.commit()


@router.get("/{org_id}/members", response_model=list[MemberOut])
def list_members(org_id: uuid.UUID, db: DbDep, user: UserDep):
    _get_org_or_404(db, org_id)
    _check_access(user, org_id)
    members = db.query(User).filter(User.org_id == org_id).all()
    return [MemberOut(id=m.id, username=m.username, role=m.role.value, org_id=m.org_id)
            for m in members]


@router.post("/{org_id}/members", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def add_member(org_id: uuid.UUID, body: MemberAdd, db: DbDep, _: AdminDep):
    _get_org_or_404(db, org_id)
    member = db.get(User, body.user_id)
    if not member:
        raise HTTPException(status_code=404, detail="User not found")
    member.org_id = org_id
    db.commit()
    return MemberOut(id=member.id, username=member.username, role=member.role.value,
                     org_id=member.org_id)


@router.delete("/{org_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(org_id: uuid.UUID, user_id: uuid.UUID, db: DbDep, _: AdminDep):
    _get_org_or_404(db, org_id)
    member = db.get(User, user_id)
    if not member or member.org_id != org_id:
        raise HTTPException(status_code=404, detail="Member not found in this org")
    member.org_id = None
    db.commit()


def _get_org_or_404(db: Session, org_id: uuid.UUID) -> Organization:
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _check_access(user: dict, org_id: uuid.UUID) -> None:
    if user.get("role") == "admin":
        return
    # Non-admin: look up their org_id from DB
    import uuid as _uuid
    from app.persistence.database import SessionLocal
    with SessionLocal() as db:
        db_user = db.query(User).filter(User.id == _uuid.UUID(user.get("sub"))).first()
        if not db_user or db_user.org_id != org_id:
            raise HTTPException(status_code=403, detail="Access denied")
