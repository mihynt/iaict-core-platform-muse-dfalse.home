"""IAICT Core Platform API — foundation slice.

Milestone M1 foundation: service health, tenant context enforcement and a
tenant-scoped workspace resource demonstrating strict tenant isolation.
Storage is in-memory at this stage; persistence arrives with the data-model
work (M2) and does not change the tenant-isolation contract tested here.
"""
from fastapi import Depends, FastAPI, status
from pydantic import BaseModel, Field

from .config import settings
from .tenancy import require_tenant

app = FastAPI(title="IAICT Core Platform API", version="0.1.0")

# tenant_id -> {workspace_name: record}
_workspaces: dict[str, dict[str, dict]] = {}


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "env": settings.app_env}


@app.get(f"{settings.api_prefix}/context")
async def context(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant}


@app.post(f"{settings.api_prefix}/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceIn, tenant: str = Depends(require_tenant)) -> dict:
    store = _workspaces.setdefault(tenant, {})
    if body.name in store:
        return {"tenant_id": tenant, "name": body.name, "created": False}
    store[body.name] = {"name": body.name}
    return {"tenant_id": tenant, "name": body.name, "created": True}


@app.get(f"{settings.api_prefix}/workspaces")
async def list_workspaces(tenant: str = Depends(require_tenant)) -> dict:
    store = _workspaces.get(tenant, {})
    return {"tenant_id": tenant, "items": sorted(store.keys())}
