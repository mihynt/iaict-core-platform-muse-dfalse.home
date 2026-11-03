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
    # Bang 32 (SYS_USER_ACCOUNT), T-031
    linked_actor_code: str | None = None
    jurisdiction_admin_code: str | None = None
    auth_provider_type: str | None = Field(
        default=None,
        pattern="^(VNEID_NATIONAL_SSO|ECDT_MOBILE_AUTH|INTERNAL_PKI_MFA)$")


class UserPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    linked_actor_code: str | None = None
    account_status: str | None = Field(
        default=None, pattern="^(ACTIVE|LOCKED|REVOKED)$")
    jurisdiction_admin_code: str | None = None
    auth_provider_type: str | None = Field(
        default=None,
        pattern="^(VNEID_NATIONAL_SSO|ECDT_MOBILE_AUTH|INTERNAL_PKI_MFA)$")


def _user_view(u: User) -> dict:
    return {"username": u.username, "display_name": u.display_name,
            "role": u.role, "created_at": u.created_at,
            "linked_actor_code": u.linked_actor_code,
            "account_status": u.account_status,
            "jurisdiction_admin_code": u.jurisdiction_admin_code,
            "auth_provider_type": u.auth_provider_type}


async def _check_linked_actor(tenant: str, code: str | None) -> None:
    if code is None:
        return
    actors = await store.list_records(tenant, "actors")
    if all(a.get("code") != code for a in actors):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REF_UNKNOWN",
                    "message": f"Reference does not exist in this tenant: linked_actor_code"})


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(body: UserIn, tenant: str = Depends(require_tenant),
                      x_actor: str | None = Header(default=None)) -> dict:
    bootstrap = await store.tenant_user_count(tenant) == 0
    if bootstrap:
        role = "TENANT_ADMIN"  # first user is always the tenant administrator
        actor_name = "bootstrap"
        action = "USER_BOOTSTRAP"
    else:
        if x_actor is None or await store.get_user(tenant, x_actor.strip()) is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "ACTOR_UNKNOWN", "message": "Actor is not a user of this tenant"},
            )
        actor = await store.get_user(tenant, x_actor.strip())
        if actor.role != "TENANT_ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ROLE_FORBIDDEN", "message": "Requires role TENANT_ADMIN"},
            )
        role = body.role
        actor_name = actor.username
        action = "USER_CREATE"
    await _check_linked_actor(tenant, body.linked_actor_code)
    user = await store.create_user(
        tenant, body.username, body.display_name, role,
        linked_actor_code=body.linked_actor_code,
        jurisdiction_admin_code=body.jurisdiction_admin_code,
        auth_provider_type=body.auth_provider_type)
    if user is None:
        await store.record_audit(scope="tenant", tenant_id=tenant, actor=actor_name,
                           action=action, target=body.username, outcome="CONFLICT")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "USER_EXISTS", "message": "Username already exists in this tenant"},
        )
    await store.record_audit(scope="tenant", tenant_id=tenant, actor=actor_name,
                       action=action, target=user.username, outcome="OK")
    return {"tenant_id": tenant, **_user_view(user)}


@router.get("/users")
async def list_users(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant, "items": [_user_view(u) for u in await store.list_users(tenant)]}


@router.patch("/users/{username}")
async def update_user(username: str, body: UserPatch,
                      tenant: str = Depends(require_tenant),
                      x_actor: str | None = Header(default=None)) -> dict:
    actor = await store.get_user(tenant, (x_actor or "").strip())
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACTOR_UNKNOWN", "message": "Actor is not a user of this tenant"})
    if actor.role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ROLE_FORBIDDEN", "message": "Requires role TENANT_ADMIN"})
    target = await store.get_user(tenant, username)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND", "message": "Object not found"})
    fields = body.model_dump(exclude_none=True)
    await _check_linked_actor(tenant, fields.get("linked_actor_code"))
    if fields.get("account_status") not in (None, "ACTIVE") \
            and target.role == "TENANT_ADMIN" and target.account_status == "ACTIVE":
        # never leave the tenant without an active administrator
        others = [u for u in await store.list_users(tenant)
                  if u.username != username and u.role == "TENANT_ADMIN"
                  and u.account_status == "ACTIVE"]
        if not others:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "LAST_ADMIN",
                        "message": "Cannot deactivate the last active TENANT_ADMIN"})
    before = _user_view(target)
    user = await store.update_user(tenant, username, fields)
    await store.record_audit(
        scope="tenant", tenant_id=tenant, actor=actor.username,
        action="USER_UPDATE", target=username, outcome="OK",
        old_value=str(before), new_value=str(_user_view(user)))
    return {"tenant_id": tenant, **_user_view(user)}


@router.get("/audit")
async def tenant_audit(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant, "items": await store.audit_for_tenant(tenant)}
