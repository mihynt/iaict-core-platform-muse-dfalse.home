"""PostgreSQL backend for serverless Workers, via Hyperdrive (M2, T-004).

Same store contract as app.pgstore, but with the pure-Python pg8000 driver:
it is the driver Cloudflare supports for PostgreSQL in Python Workers,
where the Hyperdrive binding provides the connection fields and Hyperdrive
itself terminates TLS and pools connections to the database (Neon).
Standard SQL only (app/schema.sql), so this backend and the psycopg one are
interchangeable; the entrypoint chooses (see app.store.make_store).

Connection policy (revised 2026-11-02, T-011): one cached connection per
store instance (i.e. per Worker isolate), health-checked with SELECT 1
before each operation and dropped + re-established whenever an operation
fails, so a stale connection self-heals instead of surfacing as a 500.
The original per-operation-connection policy made every request pay a
full pg8000 handshake through Hyperdrive; under parallel browser loads
requests took 6-8s and intermittently died with Cloudflare error 1102
(Worker CPU limit) — observed live on the dashboard's crop-plans call.

Every operation runs inside ONE explicit transaction (autocommit off,
commit at the end of the operation). This is load-bearing, not style:
Hyperdrive pools upstream sessions at transaction boundaries, and
pg8000's extended protocol splits a call into PARSE / DESCRIBE / BIND /
EXECUTE messages — outside a transaction the unnamed prepared statement
could land on a different upstream session than the DESCRIBE, failing
with SQLSTATE 26000 "unnamed prepared statement does not exist"
(observed live in wrangler tail after the first connection-reuse
deploy). Inside a transaction Hyperdrive pins the upstream session for
the whole operation.

Round-trip diet (revised 2026-11-02, T-012): live measurement showed a
successful list call still cost 7-10s and only ~40% of sequential calls
succeeded — the per-request protocol chatter, not the database, was the
bottleneck. Three cuts:
- Tenant and user lookups (the guard runs on EVERY request) are cached
  per isolate for 30s (unknown slugs for 10s); writes through this
  instance update/invalidate the cache immediately. Worst case, a
  status change made through another isolate takes up to 30s to be
  seen here — accepted for the beta and documented, not silent.
- Read operations skip the SELECT 1 ping and instead run optimistically
  on the cached connection, retrying ONCE on a fresh connection when
  the cached one turns out stale. Writes keep the pinged path.
- A fresh connection probes the schema with ONE cheap query
  (SELECT 1 FROM tenants) instead of replaying the whole DDL file;
  the full DDL runs only when the probe shows the tables are missing.
"""
from __future__ import annotations

import json
import pathlib
import threading
import time
from contextlib import contextmanager

import pg8000

from .records_spec import REF_ID_COLUMN, SPECS, conv as _conv
from .store import CODED_KINDS, RECORD_REFS, RefUnknown, Tenant, User

_SCHEMA = pathlib.Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def _is_unique_violation(exc: BaseException) -> bool:
    return bool(exc.args and isinstance(exc.args[0], dict)
                and exc.args[0].get("C") == "23505")


class WorkerPgStore:
    kind = "postgresql-hyperdrive"

    def __init__(self, *, host: str, port: int, user: str, password: str, database: str) -> None:
        self._lock = threading.Lock()
        self._params = dict(host=host, port=int(port), user=user,
                            password=password, database=database)
        self._schema_done = False
        self._conn = None
        # Per-isolate lookup caches (T-012, see module docstring).
        self._tenant_cache: dict[str, tuple[float, Tenant | None]] = {}
        self._user_cache: dict[tuple[str, str], tuple[float, User | None]] = {}

    def _drop_conn(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _ensure_schema(self, conn) -> None:
        """One cheap probe instead of replaying the whole DDL file on
        every fresh isolate (T-012); the full DDL runs only when the
        probe shows the tables are not there yet."""
        if self._schema_done:
            return
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM tenants LIMIT 1")
            cur.fetchall()
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            cur = conn.cursor()
            for stmt in _SCHEMA.split(";\n"):
                stmt = stmt.strip()
                if stmt:
                    cur.execute(stmt)
            conn.commit()
        self._schema_done = True

    def _get_conn(self, ping: bool = True):
        """Return the cached connection; reconnect when it is missing or
        (with ping=True) fails its SELECT 1 health check. Applies the
        schema once per store instance."""
        if self._conn is not None:
            if not ping:
                return self._conn
            try:
                cur = self._conn.cursor()
                cur.execute("SELECT 1")
                cur.fetchall()
                return self._conn
            except Exception:
                self._drop_conn()
        # autocommit stays OFF: every operation runs in one explicit
        # transaction so Hyperdrive pins the upstream session (see the
        # module docstring on SQLSTATE 26000).
        conn = pg8000.connect(**self._params, timeout=15)
        self._ensure_schema(conn)
        self._conn = conn
        return conn

    @contextmanager
    def _session(self):
        conn = self._get_conn()
        try:
            yield conn.cursor()
            conn.commit()
        except Exception:
            # Roll back the aborted transaction and drop the connection,
            # so the next operation starts from a clean, known state.
            try:
                conn.rollback()
            except Exception:
                pass
            self._drop_conn()
            raise

    def _run_read(self, work):
        """Run work(cursor) as one read transaction (T-012): optimistic
        first attempt on the cached connection without the ping round
        trip; on failure, drop the connection and retry ONCE on a fresh,
        pinged connection. Returns work's result."""
        for attempt in (1, 2):
            conn = self._get_conn(ping=(attempt == 2))
            try:
                cur = conn.cursor()
                result = work(cur)
                conn.commit()
                return result
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                self._drop_conn()
                if attempt == 2:
                    raise

    @classmethod
    def from_binding(cls, binding) -> "WorkerPgStore":
        """Build from a Hyperdrive binding object (host/port/user/password/
        database attributes), as exposed in the Workers request env."""
        return cls(host=binding.host, port=int(binding.port), user=binding.user,
                   password=binding.password, database=binding.database)

    @staticmethod
    def _rows(cur) -> list[dict]:
        names = [d[0] for d in cur.description]
        return [dict(zip(names, row)) for row in cur.fetchall()]

    def _one(self, cur) -> dict | None:
        rows = self._rows(cur)
        return rows[0] if rows else None

    async def reset(self) -> None:
        self._tenant_cache.clear()
        self._user_cache.clear()
        with self._lock, self._session() as cur:
            cur.execute(
                "TRUNCATE audit_log, lot_relations, field_events, lots, crop_plans,"
                " mother_plant_status_history, mother_plants, zone_boundary_versions,"
                " zones, workspaces, users, tenants RESTART IDENTITY CASCADE"
            )

    # ---- audit ---------------------------------------------------------
    async def record_audit(self, *, scope: str, tenant_id: str | None, actor: str,
                     action: str, target: str, outcome: str,
                     old_value: str | None = None,
                     new_value: str | None = None) -> dict:
        from . import auditctx
        with self._lock, self._session() as cur:
            cur.execute(
                "INSERT INTO audit_log (scope, tenant_id, actor, action, target, outcome,"
                " old_value, new_value, client_ip, user_agent)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING seq, ts",
                (scope, tenant_id, actor, action, target, outcome,
                 old_value, new_value, auditctx.client_ip(), auditctx.user_agent()),
            )
            row = self._one(cur)
        return {"seq": row["seq"], "ts": row["ts"].isoformat(), "scope": scope,
                "tenant_id": tenant_id, "actor": actor, "action": action,
                "target": target, "outcome": outcome, "old_value": old_value,
                "new_value": new_value, "client_ip": auditctx.client_ip(),
                "user_agent": auditctx.user_agent()}

    def _audit_rows(self, where: str, params: tuple) -> list[dict]:
        def work(cur):
            cur.execute(f"SELECT * FROM audit_log {where} ORDER BY seq", params)
            return self._rows(cur)
        with self._lock:
            rows = self._run_read(work)
        return [{**r, "ts": r["ts"].isoformat()} for r in rows]

    async def list_audit(self) -> list[dict]:
        return self._audit_rows("", ())

    async def audit_for_tenant(self, tenant_id: str) -> list[dict]:
        return self._audit_rows("WHERE tenant_id = %s", (tenant_id,))

    # ---- tenants -------------------------------------------------------
    async def create_tenant(self, slug: str, name: str) -> Tenant | None:
        # The unique-violation handler lives OUTSIDE the session on purpose:
        # a swallowed server error would leave the transaction aborted and
        # pg8000 refuses any further statement in a failed transaction.
        try:
            with self._lock, self._session() as cur:
                cur.execute(
                    "INSERT INTO tenants (slug, name) VALUES (%s, %s) RETURNING created_at",
                    (slug, name),
                )
                created = self._one(cur)["created_at"]
        except Exception as exc:
            if _is_unique_violation(exc):
                return None
            raise
        tenant = Tenant(slug=slug, name=name, created_at=created.isoformat())
        self._tenant_cache[slug] = (time.monotonic(), tenant)
        return tenant

    async def get_tenant(self, slug: str) -> Tenant | None:
        now = time.monotonic()
        hit = self._tenant_cache.get(slug)
        if hit is not None:
            ts, val = hit
            if now - ts < (30.0 if val is not None else 10.0):
                return val

        def work(cur):
            cur.execute("SELECT * FROM tenants WHERE slug = %s", (slug,))
            return self._one(cur)

        with self._lock:
            row = self._run_read(work)
        result = None if row is None else Tenant(
            slug=row["slug"], name=row["name"], status=row["status"],
            created_at=row["created_at"].isoformat())
        self._tenant_cache[slug] = (now, result)
        return result

    async def list_tenants(self) -> list[Tenant]:
        def work(cur):
            cur.execute("SELECT * FROM tenants ORDER BY slug")
            return self._rows(cur)

        with self._lock:
            rows = self._run_read(work)
        return [Tenant(slug=r["slug"], name=r["name"], status=r["status"],
                       created_at=r["created_at"].isoformat()) for r in rows]

    async def set_tenant_status(self, slug: str, status: str) -> Tenant | None:
        with self._lock, self._session() as cur:
            cur.execute(
                "UPDATE tenants SET status = %s WHERE slug = %s RETURNING *", (status, slug)
            )
            row = self._one(cur)
        if row is None:
            self._tenant_cache.pop(slug, None)
            return None
        tenant = Tenant(slug=row["slug"], name=row["name"], status=row["status"],
                        created_at=row["created_at"].isoformat())
        self._tenant_cache[slug] = (time.monotonic(), tenant)
        return tenant

    # ---- users ---------------------------------------------------------
    async def create_user(self, tenant: str, username: str, display_name: str, role: str,
                          linked_actor_code: str | None = None,
                          jurisdiction_admin_code: str | None = None,
                          auth_provider_type: str | None = None) -> User | None:
        try:
            with self._lock, self._session() as cur:
                cur.execute(
                    "INSERT INTO users (tenant_id, username, display_name, role,"
                    " linked_actor_code, account_status, jurisdiction_admin_code,"
                    " auth_provider_type)"
                    " VALUES (%s, %s, %s, %s, %s, 'ACTIVE', %s, %s) RETURNING created_at",
                    (tenant, username, display_name, role, linked_actor_code,
                     jurisdiction_admin_code, auth_provider_type),
                )
                created = self._one(cur)["created_at"]
        except Exception as exc:
            if _is_unique_violation(exc):
                return None
            raise
        self._user_cache.pop((tenant, username), None)
        return User(username=username, display_name=display_name, role=role,
                    created_at=created.isoformat(),
                    linked_actor_code=linked_actor_code,
                    jurisdiction_admin_code=jurisdiction_admin_code,
                    auth_provider_type=auth_provider_type)

    async def update_user(self, tenant: str, username: str, fields: dict) -> User | None:
        allowed = ("display_name", "role", "linked_actor_code", "account_status",
                   "jurisdiction_admin_code", "auth_provider_type")
        sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if await self.get_user(tenant, username) is None:
            return None
        if sets:
            assignments = ", ".join(f"{k} = %s" for k in sets)
            with self._lock, self._session() as cur:
                cur.execute(
                    f"UPDATE users SET {assignments}"
                    " WHERE tenant_id = %s AND username = %s",
                    tuple(sets.values()) + (tenant, username))
            self._user_cache.pop((tenant, username), None)
        return await self.get_user(tenant, username)

    async def get_user(self, tenant: str, username: str) -> User | None:
        now = time.monotonic()
        hit = self._user_cache.get((tenant, username))
        if hit is not None:
            ts, val = hit
            if now - ts < (30.0 if val is not None else 10.0):
                return val

        def work(cur):
            cur.execute("SELECT * FROM users WHERE tenant_id = %s AND username = %s",
                        (tenant, username))
            return self._one(cur)

        with self._lock:
            row = self._run_read(work)
        result = None if row is None else User(
            username=row["username"], display_name=row["display_name"],
            role=row["role"], created_at=row["created_at"].isoformat(),
            linked_actor_code=row.get("linked_actor_code"),
            account_status=row.get("account_status") or "ACTIVE",
            jurisdiction_admin_code=row.get("jurisdiction_admin_code"),
            auth_provider_type=row.get("auth_provider_type"))
        self._user_cache[(tenant, username)] = (now, result)
        return result

    async def list_users(self, tenant: str) -> list[User]:
        def work(cur):
            cur.execute("SELECT * FROM users WHERE tenant_id = %s ORDER BY username", (tenant,))
            return self._rows(cur)

        with self._lock:
            rows = self._run_read(work)
        return [User(username=r["username"], display_name=r["display_name"], role=r["role"],
                     created_at=r["created_at"].isoformat(),
                     linked_actor_code=r.get("linked_actor_code"),
                     account_status=r.get("account_status") or "ACTIVE",
                     jurisdiction_admin_code=r.get("jurisdiction_admin_code"),
                     auth_provider_type=r.get("auth_provider_type")) for r in rows]

    async def tenant_user_count(self, tenant: str) -> int:
        def work(cur):
            cur.execute("SELECT count(*) AS n FROM users WHERE tenant_id = %s", (tenant,))
            return self._one(cur)["n"]

        with self._lock:
            return self._run_read(work)

    # ---- workspaces ------------------------------------------------------
    async def create_workspace(self, tenant: str, name: str) -> bool:
        with self._lock, self._session() as cur:
            cur.execute(
                "INSERT INTO workspaces (tenant_id, name) VALUES (%s, %s)"
                " ON CONFLICT DO NOTHING",
                (tenant, name),
            )
            return cur.rowcount == 1

    async def list_workspace_names(self, tenant: str) -> list[str]:
        def work(cur):
            cur.execute("SELECT name FROM workspaces WHERE tenant_id = %s ORDER BY name",
                        (tenant,))
            return [r["name"] for r in self._rows(cur)]

        with self._lock:
            return self._run_read(work)

    # ---- production records ---------------------------------------------
    def _resolve_ref(self, cur, tenant: str, ref_kind: str, code: str) -> int | None:
        table = SPECS[ref_kind][0]
        cur.execute(f"SELECT id FROM {table} WHERE tenant_id = %s AND code = %s",
                    (tenant, code))
        row = self._one(cur)
        return None if row is None else row["id"]

    async def create_record(self, tenant: str, kind: str, fields: dict) -> dict | None:
        try:
            return self._create_record_inner(tenant, kind, fields)
        except Exception as exc:
            if _is_unique_violation(exc):
                return None
            raise

    def _create_record_inner(self, tenant: str, kind: str, fields: dict) -> dict | None:
        table, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        with self._lock, self._session() as cur:
            values: dict[str, object] = {}
            for ref_field, ref_kind in refs.items():
                code = fields.get(ref_field)
                if code is not None:
                    ref_id = self._resolve_ref(cur, tenant, ref_kind, code)
                    if ref_id is None:
                        raise RefUnknown(ref_field)
                    values[REF_ID_COLUMN[ref_field]] = ref_id
                    values[ref_field] = code
            known = set(columns) | set(refs)
            extra = {k: v for k, v in fields.items() if k not in known and k != "code"}
            for col, ckind in columns.items():
                if col in fields:
                    values[col] = json.dumps(fields[col]) if ckind == "json" else fields[col]
            names = ["tenant_id", "data", *values.keys()]
            params = [tenant, json.dumps(extra), *values.values()]
            if kind in CODED_KINDS:
                names.insert(1, "code")
                params.insert(1, fields.get("code"))
            placeholders = ", ".join(["%s"] * len(names))
            cur.execute(
                f"INSERT INTO {table} ({', '.join(names)}) VALUES ({placeholders})"
                " RETURNING id",
                params,
            )
            new_id = self._one(cur)["id"]
            cur.execute(f"SELECT * FROM {table} WHERE id = %s", (new_id,))
            return self._row_to_record(self._one(cur), kind)

    async def update_record(self, tenant: str, kind: str, code: str,
                            fields: dict) -> dict | None:
        table, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        with self._lock, self._session() as cur:
            cur.execute(
                f"SELECT id FROM {table} WHERE tenant_id = %s AND code = %s",
                (tenant, code))
            if self._one(cur) is None:
                return None
            values: dict[str, object] = {}
            for ref_field, ref_kind in refs.items():
                ref_code = fields.get(ref_field)
                if ref_code is not None:
                    ref_id = self._resolve_ref(cur, tenant, ref_kind, ref_code)
                    if ref_id is None:
                        raise RefUnknown(ref_field)
                    values[REF_ID_COLUMN[ref_field]] = ref_id
                    values[ref_field] = ref_code
            for col, ckind in columns.items():
                if col in fields:
                    values[col] = json.dumps(fields[col]) if ckind == "json" \
                        else fields[col]
            known = set(columns) | set(refs)
            extra = {k: v for k, v in fields.items()
                     if k not in known and k != "code"}
            sets = [f"{k} = %s" for k in values]
            params: list = list(values.values())
            if extra:
                sets.append("data = data || %s")
                params.append(json.dumps(extra))
            if kind != "field_events":
                sets.append("updated_at = now()")
            if sets:
                cur.execute(
                    f"UPDATE {table} SET {', '.join(sets)}"
                    " WHERE tenant_id = %s AND code = %s",
                    params + [tenant, code])
            cur.execute(
                f"SELECT * FROM {table} WHERE tenant_id = %s AND code = %s",
                (tenant, code))
            return self._row_to_record(self._one(cur), kind)

    async def update_record_by_id(self, tenant: str, kind: str, record_id: int,
                            fields: dict) -> dict | None:
        table, columns = SPECS[kind]
        refs = RECORD_REFS[kind]
        with self._lock, self._session() as cur:
            cur.execute(
                f"SELECT id FROM {table} WHERE tenant_id = %s AND id = %s",
                (tenant, record_id))
            if self._one(cur) is None:
                return None
            values: dict[str, object] = {}
            for ref_field, ref_kind in refs.items():
                ref_code = fields.get(ref_field)
                if ref_code is not None:
                    ref_id = self._resolve_ref(cur, tenant, ref_kind, ref_code)
                    if ref_id is None:
                        raise RefUnknown(ref_field)
                    values[REF_ID_COLUMN[ref_field]] = ref_id
                    values[ref_field] = ref_code
            for col, ckind in columns.items():
                if col in fields:
                    values[col] = json.dumps(fields[col]) if ckind == "json" \
                        else fields[col]
            known = set(columns) | set(refs)
            extra = {k: v for k, v in fields.items()
                     if k not in known and k != "code"}
            sets = [f"{k} = %s" for k in values]
            params: list = list(values.values())
            if extra:
                sets.append("data = data || %s")
                params.append(json.dumps(extra))
            if kind != "field_events":
                sets.append("updated_at = now()")
            if sets:
                cur.execute(
                    f"UPDATE {table} SET {', '.join(sets)}"
                    " WHERE tenant_id = %s AND id = %s",
                    params + [tenant, record_id])
            cur.execute(
                f"SELECT * FROM {table} WHERE tenant_id = %s AND id = %s",
                (tenant, record_id))
            return self._row_to_record(self._one(cur), kind)

    async def delete_record(self, tenant: str, kind: str, code: str) -> dict | None:
        table, _ = SPECS[kind]
        with self._lock, self._session() as cur:
            cur.execute(
                f"SELECT * FROM {table} WHERE tenant_id = %s AND code = %s",
                (tenant, code))
            row = self._one(cur)
            if row is None:
                return None
            record = self._row_to_record(row, kind)
            cur.execute(
                f"DELETE FROM {table} WHERE tenant_id = %s AND code = %s",
                (tenant, code))
            return record if cur.rowcount else None

    def _row_to_record(self, row: dict, kind: str) -> dict:
        _, columns = SPECS[kind]
        record: dict = {"id": row["id"], "tenant_id": row["tenant_id"]}
        if kind in CODED_KINDS:
            record["code"] = row["code"]
        for col, ckind in columns.items():
            if row.get(col) is not None:
                record[col] = _conv(row[col], ckind)
        for ref_field in RECORD_REFS[kind]:
            if row.get(ref_field) is not None:
                record[ref_field] = row[ref_field]
        data = row.get("data") or {}
        record.update(data if isinstance(data, dict) else json.loads(data))
        record["created_at"] = row["created_at"].isoformat()
        if "updated_at" in row and row["updated_at"] is not None:
            record["updated_at"] = row["updated_at"].isoformat()
        return record

    async def list_records(self, tenant: str, kind: str) -> list[dict]:
        table, _ = SPECS[kind]
        order = "code" if kind in CODED_KINDS else "id"

        def work(cur):
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s ORDER BY {order}",
                        (tenant,))
            return [self._row_to_record(r, kind) for r in self._rows(cur)]

        with self._lock:
            return self._run_read(work)

    async def count_records(self, tenant: str, kind: str) -> int:
        table, _ = SPECS[kind]

        def work(cur):
            cur.execute(f"SELECT count(*) AS n FROM {table} WHERE tenant_id = %s",
                        (tenant,))
            return int(self._one(cur)["n"])

        with self._lock:
            return self._run_read(work)

    async def get_record_by_code(self, tenant: str, kind: str, code: str) -> dict | None:
        table, _ = SPECS[kind]

        def work(cur):
            cur.execute(f"SELECT * FROM {table} WHERE tenant_id = %s AND code = %s",
                        (tenant, code))
            return self._one(cur)

        with self._lock:
            row = self._run_read(work)
        return None if row is None else self._row_to_record(row, kind)
