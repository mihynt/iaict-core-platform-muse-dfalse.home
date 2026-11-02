"""Tenant context for the API.

Baseline rule (SRS tenancy/security groups): every tenant-scoped resource is
deny-by-default. A request is accepted only when it carries a tenant context
that (1) is well-formed, (2) belongs to a registered tenant, and (3) that
tenant is ACTIVE.
"""
import re

from fastapi import Header, HTTPException, status

from .store import store

TENANT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


async def require_tenant(x_tenant_id: str | None = Header(default=None)) -> str:
    """FastAPI dependency: resolve and validate the tenant context header."""
    if x_tenant_id is None or x_tenant_id.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_REQUIRED", "message": "X-Tenant-Id header is required"},
        )
    tenant = x_tenant_id.strip()
    if not TENANT_ID_RE.match(tenant):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TENANT_INVALID", "message": "X-Tenant-Id has an invalid format"},
        )
    record = await store.get_tenant(tenant)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TENANT_UNKNOWN", "message": "Tenant is not registered"},
        )
    if record.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "TENANT_SUSPENDED", "message": "Tenant is suspended"},
        )
    return tenant
