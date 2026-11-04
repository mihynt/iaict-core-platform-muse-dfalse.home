"""Storage boundary for the platform.

Two backends implement the same interface, so the API contracts and the
tenant-isolation rules tested against them do not change with storage:
- InMemoryStore: process memory; the default for local runs and the
  Cloudflare Workers beta (no database configured there yet).
- PgStore (app.pgstore): PostgreSQL, selected when DATABASE_URL is set.

Invariants kept here for every backend:
- tenants are registered before use (deny by default),
- users and records exist only inside a tenant,
- object references resolve only inside the caller's tenant,
- the audit log is append-only.
"""
from __future__ import annotations

import itertools
import os
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
    # Bang 32 (SYS_USER_ACCOUNT), T-031
    linked_actor_code: str | None = None
    account_status: str = "ACTIVE"  # ACTIVE | LOCKED | REVOKED
    jurisdiction_admin_code: str | None = None
    auth_provider_type: str | None = None


# Production record kinds (SRS v2.0 groups ZON/MPL/FLD/LOT): reference fields
# map to the kind they must resolve to *within the same tenant*. Coded kinds
# carry a tenant-unique `code`; field_events are append-style (no code).
# RECORD_REFS is generated from the field registry (records_spec.py) —
# the single source of truth since T-032 slice 2. (A hand-kept copy lived
# here until T-039/GD3 exposed it as stale; it is imported, not copied.)
from .records_spec import RECORD_REFS  # noqa: E402,F401
CODED_KINDS = {"zones", "mother_plants", "crop_plans", "lots",
               "actors", "spatial_units", "input_lots",
               "packing_lots", "packaging_units",
               "ref_admin_units", "ref_market_regulations",
               "ref_active_substance_mrls", "ref_certification_schemes",
               "ref_transport_modes", "livestock_units", "iot_devices"}


LINK_UNIQUE_FIELDS: dict[str, tuple[str, ...]] = {
    "zone_parcel_links": ("zone_code", "parcel_code"),
    "zone_market_approvals": ("zone_code", "market_code"),
    "packing_inputs": ("packing_lot_code", "harvest_lot_code"),
}


class RefUnknown(ValueError):
    """A record field references an object that does not exist in the tenant."""

    def __init__(self, field_name: str):
        super().__init__(f"REF_UNKNOWN:{field_name}")
        self.field_name = field_name


class InMemoryStore:
    kind = "memory"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tenants: dict[str, Tenant] = {}
        self.users: dict[str, dict[str, User]] = {}
        self.workspaces: dict[str, dict[str, dict]] = {}
        self.audit: list[dict] = []
        self._seq = itertools.count(1)
        # records[kind][tenant] = {"by_code": {code: record}, "events": [record]}
        self.records: dict[str, dict[str, dict]] = {k: {} for k in RECORD_REFS}
        self._ids = {k: itertools.count(1) for k in RECORD_REFS}

    async def reset(self) -> None:
        with self._lock:
            self.tenants.clear()
            self.users.clear()
            self.workspaces.clear()
            self.audit.clear()
            self._seq = itertools.count(1)
            self.records = {k: {} for k in RECORD_REFS}
            self._ids = {k: itertools.count(1) for k in RECORD_REFS}

    def _bucket(self, kind: str, tenant: str) -> dict:
        return self.records[kind].setdefault(tenant, {"by_code": {}, "events": []})

    # ---- audit ---------------------------------------------------------
    async def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
                     action: str, target: str, outcome: str,
                     old_value: str | None = None,
                     new_value: str | None = None) -> dict:
        from . import auditctx
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
                "old_value": old_value,
                "new_value": new_value,
                "client_ip": auditctx.client_ip(),
                "user_agent": auditctx.user_agent(),
            }
            self.audit.append(entry)
            return entry

    async def list_audit(self) -> list[dict]:
        return list(self.audit)

    async def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return [e for e in self.audit if e["tenant_id"] == tenant_id]

    # ---- tenants -------------------------------------------------------
    async def create_tenant(self, slug: str, name: str) -> Tenant | None:
        with self._lock:
            if slug in self.tenants:
                return None
            tenant = Tenant(slug=slug, name=name)
            self.tenants[slug] = tenant
            self.users.setdefault(slug, {})
            self.workspaces.setdefault(slug, {})
            return tenant

    async def get_tenant(self, slug: str) -> Tenant | None:
        return self.tenants.get(slug)

    async def list_tenants(self) -> list[Tenant]:
        return sorted(self.tenants.values(), key=lambda t: t.slug)

    async def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
        with self._lock:
            tenant = self.tenants.get(slug)
            if tenant is None:
                return None
            tenant.status = status
            return tenant

    # ---- users ---------------------------------------------------------
    async def create_user(self, tenant: str, username: str, display_name: str, role: str,
                          linked_actor_code: str | None = None,
                          jurisdiction_admin_code: str | None = None,
                          auth_provider_type: str | None = None) -> User | None:
        with self._lock:
            bucket = self.users.setdefault(tenant, {})
            if username in bucket:
                return None
            user = User(username=username, display_name=display_name, role=role,
                        linked_actor_code=linked_actor_code,
                        jurisdiction_admin_code=jurisdiction_admin_code,
                        auth_provider_type=auth_provider_type)
            bucket[username] = user
            return user

    async def update_user(self, tenant: str, username: str, fields: dict) -> User | None:
        with self._lock:
            user = self.users.get(tenant, {}).get(username)
            if user is None:
                return None
            for key in ("display_name", "role", "linked_actor_code",
                        "account_status", "jurisdiction_admin_code",
                        "auth_provider_type"):
                if key in fields and fields[key] is not None:
                    setattr(user, key, fields[key])
            return user

    async def get_user(self, tenant: str, username: str) -> User | None:
        return self.users.get(tenant, {}).get(username)

    async def list_users(self, tenant: str) -> list[User]:
        return sorted(self.users.get(tenant, {}).values(), key=lambda u: u.username)

    async def tenant_user_count(self, tenant: str) -> int:
        return len(self.users.get(tenant, {}))

    # ---- workspaces ------------------------------------------------------
    async def create_workspace(self, tenant: str, name: str) -> bool:
        with self._lock:
            bucket = self.workspaces.setdefault(tenant, {})
            if name in bucket:
                return False
            bucket[name] = {"name": name}
            return True

    async def list_workspace_names(self, tenant: str) -> list[str]:
        return sorted(self.workspaces.get(tenant, {}).keys())

    # ---- production records ---------------------------------------------
    async def create_record(self, tenant: str, kind: str, fields: dict) -> dict | None:
        """Insert a record. Returns None on a duplicate code within the
        tenant; raises RefUnknown for a reference that does not resolve."""
        refs = RECORD_REFS[kind]
        with self._lock:
            bucket = self._bucket(kind, tenant)
            for ref_field, ref_kind in refs.items():
                code = fields.get(ref_field)
                if code is not None and code not in self._bucket(ref_kind, tenant)["by_code"]:
                    raise RefUnknown(ref_field)
            record = {"id": next(self._ids[kind]), "tenant_id": tenant, **fields,
                      "created_at": utcnow(), "updated_at": utcnow()}
            if kind in CODED_KINDS:
                if fields.get("code") in bucket["by_code"]:
                    return None
                bucket["by_code"][fields["code"]] = record
            else:
                # Parity with the SQL stores (T-024): link kinds carry a
                # UNIQUE constraint over their two ends there; a duplicate
                # link must return None (-> 409) here too, not append.
                unique_fields = LINK_UNIQUE_FIELDS.get(kind)
                if unique_fields and any(
                        all(e.get(f) == fields.get(f) for f in unique_fields)
                        for e in bucket["events"]):
                    return None
                bucket["events"].append(record)
            return record

    async def list_records(self, tenant: str, kind: str) -> list[dict]:
        bucket = self._bucket(kind, tenant)
        if kind in CODED_KINDS:
            return [bucket["by_code"][k] for k in sorted(bucket["by_code"])]
        return sorted(bucket["events"], key=lambda r: r["id"])

    async def get_record_by_code(self, tenant: str, kind: str, code: str) -> dict | None:
        return self._bucket(kind, tenant)["by_code"].get(code)

    async def update_record(self, tenant: str, kind: str, code: str,
                            fields: dict) -> dict | None:
        record = self._bucket(kind, tenant)["by_code"].get(code)
        if record is None:
            return None
        for ref_field, ref_kind in RECORD_REFS[kind].items():
            ref_code = fields.get(ref_field)
            if ref_code is not None and \
                    self._bucket(ref_kind, tenant)["by_code"].get(ref_code) is None:
                raise RefUnknown(ref_field)
        for key, value in fields.items():
            if key != "code":
                record[key] = value
        record["updated_at"] = utcnow()
        return record

    async def update_record_by_id(self, tenant: str, kind: str,
                                  record_id: int, fields: dict) -> dict | None:
        bucket = self._bucket(kind, tenant)
        record = None
        for candidate in list(bucket["by_code"].values()) + bucket["events"]:
            if candidate.get("id") == record_id:
                record = candidate
                break
        if record is None:
            return None
        for ref_field, ref_kind in RECORD_REFS[kind].items():
            ref_code = fields.get(ref_field)
            if ref_code is not None and \
                    self._bucket(ref_kind, tenant)["by_code"].get(ref_code) is None:
                raise RefUnknown(ref_field)
        for key, value in fields.items():
            if key != "code":
                record[key] = value
        record["updated_at"] = utcnow()
        return record

    async def delete_record(self, tenant: str, kind: str, code: str) -> dict | None:
        bucket = self._bucket(kind, tenant)
        return bucket["by_code"].pop(code, None)

    async def count_records(self, tenant: str, kind: str) -> int:
        bucket = self._bucket(kind, tenant)
        if kind in CODED_KINDS:
            return len(bucket["by_code"])
        return len(bucket["events"])


class LazyWorkerStore:
    """Defers backend creation until the first request supplies the Workers
    env (the Hyperdrive binding only exists per-request there). Falls back
    to in-memory storage when the binding is absent — observable via .kind
    and the /health endpoint, never silent in the response payload.
    """

    def __init__(self) -> None:
        self._impl = None
        self._bind_lock = threading.Lock()

    @property
    def kind(self) -> str:
        return self._impl.kind if self._impl is not None else "hyperdrive-unbound"

    def bind_env(self, env) -> None:
        if self._impl is not None or env is None:
            return
        with self._bind_lock:
            if self._impl is not None:
                return
            binding = getattr(env, "HYPERDRIVE", None)
            if binding is not None:
                from .workerstore import WorkerPgStore  # lazy: pg8000 stays out of other runtimes
                self._impl = WorkerPgStore.from_binding(binding)
            else:
                self._impl = InMemoryStore()

    def bind_params(self, **params) -> None:
        """Direct parameter binding (tests, non-Workers embeddings)."""
        from .workerstore import WorkerPgStore
        self._impl = WorkerPgStore(**params)

    def _d(self):
        if self._impl is None:
            raise RuntimeError("store backend is not bound yet (no request env seen)")
        return self._impl

    def __getattr__(self, name):
        # T-032 slice 1: forward every store operation to the bound
        # backend automatically. New store methods need NO wrapper
        # boilerplate here any more (previously ~22 one-liners per class).
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._d(), name)


class LazyD1Store:
    """Defers D1 backend creation until the first request supplies the
    Workers env (the DB binding only exists per-request there). Falls
    back to in-memory storage when the binding is absent — observable
    via .kind and the /health endpoint, never silent."""

    def __init__(self) -> None:
        self._impl = None
        self._bind_lock = threading.Lock()

    @property
    def kind(self) -> str:
        return self._impl.kind if self._impl is not None else "d1-unbound"

    def bind_env(self, env) -> None:
        if self._impl is not None or env is None:
            return
        with self._bind_lock:
            if self._impl is not None:
                return
            binding = getattr(env, "DB", None)
            if binding is not None:
                from .d1store import D1Store  # lazy: keep D1 code out of other runtimes

                self._impl = D1Store(binding)
            else:
                self._impl = InMemoryStore()

    def bind_db(self, db) -> None:
        """Direct binding injection (tests, non-Workers embeddings)."""
        from .d1store import D1Store

        self._impl = D1Store(db)

    def _d(self):
        if self._impl is None:
            raise RuntimeError("store backend is not bound yet (no request env seen)")
        return self._impl

    def __getattr__(self, name):
        # T-032 slice 1: forward every store operation to the bound
        # backend automatically. New store methods need NO wrapper
        # boilerplate here any more (previously ~22 one-liners per class).
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._d(), name)


def make_store():
    """DATABASE_URL set -> PostgreSQL (psycopg); IAICT_BACKEND=d1 ->
    lazy D1 backend (Workers, T-014); IAICT_BACKEND=hyperdrive
    (set by the Workers entrypoint) -> lazy Hyperdrive backend (legacy
    fallback); otherwise in-memory."""
    dsn = os.environ.get("DATABASE_URL")
    if dsn:
        from .pgstore import PgStore  # lazy: keeps psycopg out of serverless bundles
        return PgStore(dsn)
    if os.environ.get("IAICT_BACKEND") == "d1":
        return LazyD1Store()
    if os.environ.get("IAICT_BACKEND") == "hyperdrive":
        return LazyWorkerStore()
    return InMemoryStore()


store = make_store()

# Backwards-compatible alias (the in-memory backend was the original Store).
Store = InMemoryStore
