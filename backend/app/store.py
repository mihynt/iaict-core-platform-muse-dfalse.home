"""In-memory stores for the foundation stage.

All state lives in process memory until the M2 persistence work. The store
keeps the platform's core invariants in one place:
- tenants are registered before use (deny by default),
- users exist only inside a tenant,
- the audit log is append-only.
"""
from __future__ import annotations

import itertools
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Tenant:
    slug: str
    name: str
    status: str = "ACTIVE"  # ACTIVE | SUSPENDED
    created_at: str = field(default_factory=utcnow)


@dataclass
class User:
    username: str
    display_name: str
    role: str  # TENANT_ADMIN | OPERATOR | VIEWER
    created_at: str = field(default_factory=utcnow)


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tenants: dict[str, Tenant] = {}
        self.users: dict[str, dict[str, User]] = {}  # tenant_slug -> {username: User}
        self.workspaces: dict[str, dict[str, dict]] = {}  # tenant_slug -> {name: record}
        self.audit: list[dict] = []
        self._seq = itertools.count(1)

    # ---- audit ---------------------------------------------------------
    def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
                     action: str, target: str, outcome: str) -> dict:
        with self._lock:
            entry = {
                "seq": next(self._seq),
                "ts": utcnow(),
                "scope": scope,          # platform | tenant
                "tenant_id": tenant_id,
                "actor": actor,
                "action": action,
                "target": target,
                "outcome": outcome,
            }
            self.audit.append(entry)
            return entry

    def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return [e for e in self.audit if e["tenant_id"] == tenant_id]

    # ---- tenants -------------------------------------------------------
    def create_tenant(self, slug: str, name: str) -> Tenant | None:
        with self._lock:
            if slug in self.tenants:
                return None
            tenant = Tenant(slug=slug, name=name)
            self.tenants[slug] = tenant
            self.users.setdefault(slug, {})
            self.workspaces.setdefault(slug, {})
            return tenant

    def get_tenant(self, slug: str) -> Tenant | None:
        return self.tenants.get(slug)

    def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
        with self._lock:
            tenant = self.tenants.get(slug)
            if tenant is None:
                return None
            tenant.status = status
            return tenant

    # ---- users ---------------------------------------------------------
    def create_user(self, tenant: str, username: str, display_name: str, role: str) -> User | None:
        with self._lock:
            bucket = self.users.setdefault(tenant, {})
            if username in bucket:
                return None
            user = User(username=username, display_name=display_name, role=role)
            bucket[username] = user
            return user

    def get_user(self, tenant: str, username: str) -> User | None:
        return self.users.get(tenant, {}).get(username)

    def list_users(self, tenant: str) -> list[User]:
        return sorted(self.users.get(tenant, {}).values(), key=lambda u: u.username)

    def tenant_user_count(self, tenant: str) -> int:
        return len(self.users.get(tenant, {}))


store = Store()
