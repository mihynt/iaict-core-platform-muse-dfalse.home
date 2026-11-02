"""IAICT Core Platform API.

M1 foundation: service health, platform tenant registry, tenant context
enforcement (deny by default), tenant identity skeleton, append-only audit,
and tenant-isolated workspaces. Storage is in-memory at this stage; the M2
persistence work does not change the tenant-isolation contract tested here.
"""
from fastapi import Depends, FastAPI, status
from pydantic import BaseModel, Field

from . import identity, platform
from .config import settings
from .deps import require_role
from .store import User, store
from .tenancy import require_tenant

app = FastAPI(title="IAICT Core Platform API", version="0.2.0")
app.include_router(platform.router, prefix=settings.api_prefix)
app.include_router(identity.router, prefix=settings.api_prefix)


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env,
            "version": app.version}


@app.get(f"{settings.api_prefix}/context")
async def context(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant}


@app.post(f"{settings.api_prefix}/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceIn, tenant: str = Depends(require_tenant),
                           actor: User = Depends(require_role("OPERATOR"))) -> dict:
    bucket = store.workspaces.setdefault(tenant, {})
    if body.name in bucket:
        return {"tenant_id": tenant, "name": body.name, "created": False}
    bucket[body.name] = {"name": body.name}
    store.record_audit(scope="tenant", tenant_id=tenant, actor=actor.username,
                       action="WORKSPACE_CREATE", target=body.name, outcome="OK")
    return {"tenant_id": tenant, "name": body.name, "created": True}


@app.get(f"{settings.api_prefix}/workspaces")
async def list_workspaces(tenant: str = Depends(require_tenant)) -> dict:
    bucket = store.workspaces.get(tenant, {})
    return {"tenant_id": tenant, "items": sorted(bucket.keys())}
