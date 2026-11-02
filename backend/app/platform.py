"""Platform administration: tenant registry and lifecycle (M1 foundation).

These endpoints are platform-scoped, not tenant-scoped, and are guarded by
the platform key (see deps.require_platform_key).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .deps import require_platform_key
from .store import store
from .tenancy import TENANT_ID_RE

router = APIRouter(prefix="/platform", tags=["platform"])


class TenantIn(BaseModel):
    slug: str = Field(min_length=2, max_length=63)
    name: str = Field(min_length=1, max_length=200)


class TenantStatusIn(BaseModel):
    status: str = Field(pattern="^(ACTIVE|SUSPENDED)$")


def _tenant_view(t) -> dict:
    return {"slug": t.slug, "name": t.name, "status": t.status, "created_at": t.created_at}


@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_tenant(body: TenantIn, actor: str = Depends(require_platform_key)) -> dict:
    if not TENANT_ID_RE.match(body.slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_INVALID", "message": "Slug must be lowercase letters, digits and dashes"},
        )
    tenant = await store.create_tenant(body.slug, body.name)
    if tenant is None:
        await store.record_audit(scope="platform", tenant_id=body.slug, actor=actor,
                           action="TENANT_CREATE", target=body.slug, outcome="CONFLICT")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TENANT_EXISTS", "message": "Tenant slug already registered"},
        )
    await store.record_audit(scope="platform", tenant_id=tenant.slug, actor=actor,
                       action="TENANT_CREATE", target=tenant.slug, outcome="OK")
    return _tenant_view(tenant)


@router.get("/tenants")
async def list_tenants(_: str = Depends(require_platform_key)) -> dict:
    return {"items": [_tenant_view(t) for t in await store.list_tenants()]}


@router.get("/tenants/{slug}")
async def get_tenant(slug: str, _: str = Depends(require_platform_key)) -> dict:
    tenant = await store.get_tenant(slug)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "TENANT_NOT_FOUND", "message": "Tenant not found"})
    return _tenant_view(tenant)


@router.patch("/tenants/{slug}/status")
async def set_tenant_status(slug: str, body: TenantStatusIn,
                            actor: str = Depends(require_platform_key)) -> dict:
    tenant = await store.set_tenant_status(slug, body.status)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "TENANT_NOT_FOUND", "message": "Tenant not found"})
    await store.record_audit(scope="platform", tenant_id=slug, actor=actor,
                       action="TENANT_STATUS", target=slug, outcome=body.status)
    return _tenant_view(tenant)


@router.get("/audit")
async def platform_audit(_: str = Depends(require_platform_key)) -> dict:
    return {"items": await store.list_audit()}
