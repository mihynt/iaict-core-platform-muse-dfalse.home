"""IAICT Core Platform API.

M1 foundation: service health, platform tenant registry, tenant context
enforcement (deny by default), tenant identity skeleton, append-only audit,
and tenant-isolated workspaces. M2 adds the production core objects
(ZON/MPL/FLD/LOT) and the PostgreSQL persistence backend behind the same
store boundary; the tenant-isolation contract does not change with storage.
"""
from fastapi import Depends, FastAPI, Request, status
from pydantic import BaseModel, Field

from . import identity, platform, production
from .config import settings
from .deps import require_role
from .store import User, store
from .tenancy import require_tenant

app = FastAPI(title="IAICT Core Platform API", version="0.2.0")
app.include_router(platform.router, prefix=settings.api_prefix)
app.include_router(identity.router, prefix=settings.api_prefix)
app.include_router(production.router, prefix=settings.api_prefix)


class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


@app.middleware("http")
async def _bind_store_backend(request: Request, call_next):
    """On serverless Workers the Hyperdrive binding arrives per-request in
    the ASGI scope env; hand it to the lazy store backend when present."""
    bind = getattr(store, "bind_env", None)
    scope_env = request.scope.get("env")
    if bind is not None and scope_env is not None:
        bind(scope_env)
    return await call_next(request)


@app.get("/health")
async def health(request: Request) -> dict:
    env_name = settings.app_env
    scope_env = request.scope.get("env")
    if scope_env is not None and getattr(scope_env, "APP_ENV", None):
        env_name = scope_env.APP_ENV
    return {"status": "ok", "service": settings.app_name, "env": env_name,
            "version": app.version, "storage": getattr(store, "kind", "unknown")}


@app.get(f"{settings.api_prefix}/context")
async def context(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant}


@app.post(f"{settings.api_prefix}/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceIn, tenant: str = Depends(require_tenant),
                           actor: User = Depends(require_role("OPERATOR"))) -> dict:
    created = store.create_workspace(tenant, body.name)
    if created:
        store.record_audit(scope="tenant", tenant_id=tenant, actor=actor.username,
                           action="WORKSPACE_CREATE", target=body.name, outcome="OK")
    return {"tenant_id": tenant, "name": body.name, "created": created}


@app.get(f"{settings.api_prefix}/workspaces")
async def list_workspaces(tenant: str = Depends(require_tenant)) -> dict:
    return {"tenant_id": tenant, "items": store.list_workspace_names(tenant)}
