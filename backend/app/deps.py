"""Shared dependencies: platform administration key and tenant actors.

Skeleton-stage authentication:
- Platform endpoints require the PLATFORM_ADMIN_KEY environment value in the
  X-Platform-Key header. If the key is not configured, platform endpoints are
  disabled (503) rather than open.
- Tenant write operations identify the actor with the X-Actor header
  (a username inside the caller's tenant). Authorization is role-based.
  Real credential authentication (passwords/OIDC) replaces this header
  mechanism in a later milestone without changing the role model.
"""
import os

from fastapi import Depends, Header, HTTPException, Request, status

from .store import User, store
from .tenancy import require_tenant

ROLE_ORDER = {"VIEWER": 1, "OPERATOR": 2, "TENANT_ADMIN": 3}


def _configured_platform_key(request: Request) -> str | None:
    """Platform key from the process environment (uvicorn/VPS), falling back
    to the ASGI scope `env` binding (serverless hosts such as Cloudflare
    Workers expose variables/secrets there instead of os.environ)."""
    key = os.environ.get("PLATFORM_ADMIN_KEY")
    if key:
        return key
    env = request.scope.get("env") if request is not None else None
    if env is not None:
        return getattr(env, "PLATFORM_ADMIN_KEY", None)
    return None


async def require_platform_key(request: Request,
                               x_platform_key: str | None = Header(default=None)) -> str:
    configured = _configured_platform_key(request)
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "PLATFORM_DISABLED", "message": "Platform administration is not configured"},
        )
    if x_platform_key != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "PLATFORM_KEY_INVALID", "message": "Missing or invalid platform key"},
        )
    return "platform-admin"


async def require_actor(
    tenant: str = Depends(require_tenant),
    x_actor: str | None = Header(default=None),
) -> User:
    if x_actor is None or x_actor.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACTOR_REQUIRED", "message": "X-Actor header is required"},
        )
    user = await store.get_user(tenant, x_actor.strip())
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ACTOR_UNKNOWN", "message": "Actor is not a user of this tenant"},
        )
    return user


def require_role(min_role: str):
    async def _dep(actor: User = Depends(require_actor)) -> User:
        if ROLE_ORDER[actor.role] < ROLE_ORDER[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ROLE_FORBIDDEN", "message": f"Requires role {min_role} or higher"},
            )
        return actor

    return _dep
