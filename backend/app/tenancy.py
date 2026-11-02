"""Tenant context for the API.

Baseline rule (SRS tenancy/security groups): every tenant-scoped resource is
deny-by-default. A request without a valid tenant context is rejected; data of
one tenant is never visible to another.
"""
import re

from fastapi import Header, HTTPException, status

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
    return tenant
