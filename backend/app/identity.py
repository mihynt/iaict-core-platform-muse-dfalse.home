"""Tenant identity & access skeleton (M1 foundation).

Users live inside a tenant. Bootstrap rule: while a tenant has no users, the
first user may be created without an actor and is forced to TENANT_ADMIN;
afterwards, creating users requires an actor with the TENANT_ADMIN role.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from .store import User, store
from .tenancy import require_tenant

router = APIRouter(tags=["identity"])


class UserIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="VIEWER", pattern="^(TENANT_ADMIN|OPERATOR|VIEWER)$")


def _user_view(u: User) -> dict:
    return {"username": u.username, "display_name": u.display_name,
            "role": u.role, "created_at": u.created_at}


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(body: UserIn, tenant: str = Depends(require_tenant),
                      x_actor: str | None = Header(default=None)) -> dict:
    bootstrap = store.tenant_user_count(tenant) == 0
    if bootstrap:
        role = "TENANT_ADMIN"  # first user is always the tenant administrator
        actor_name = "bootstrap"
        action = "USER_BOOTSTRAP"
    else:
        if x_actor is None or store.get_user(tenant, x_actor.strip()) is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "ACTOR_UNKNOWN", "message": "Actor is not a user of this tenant"},
            )
        actor = store.get_user(tenant, x_actor.strip())
        if actor.role != "TENANT_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ROLE_FORBIDDEN", "message": "Requires role TENANT_ADMIN"},
            )
        role = body.role
        actor_name = actor.username
        action = "USER_CREATE"
    user = store.create_user(tenant, body.username, body.display_name, role)
    if user is None:
        store.record_audit(scope="tenant", tenant_id=tenant, actor=actor_name,
                           action=action, target=body.username, outcome="CONFLICT")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "USER_EXISTS", "message": "Username already exists in this tenant"},
        )
    store.record_audit(scope="tenant", tenant_id=tenant, actor=actor_name,
                       action=action, target=user.username, outcome="OK")
    return {"tenant_id": tenant, **_user_view(user)}


@router.get("/users")
async def list_users(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant, "items": [_user_view(u) for u in store.list_users(tenant)]}


@router.get("/audit")
async def tenant_audit(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant, "items": store.audit_for_tenant(tenant)}
