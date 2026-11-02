"""Production core objects (M2, task T-004).

Tenant-scoped CRUD for the SRS v2.0 production groups:
- ZON  zones            (vùng nguyên liệu / site / thửa)
- MPL  mother plants    (cây/cụm cây đầu dòng)
- FLD  crop plans + field events (mùa vụ / nhật ký đồng ruộng)
- LOT  harvest lots     (lô thu hoạch)

Writes require role OPERATOR or higher. Object references (zone_code,
plant_code, plan_code) resolve only inside the caller's tenant. Field
definitions: docs/DATA_MODEL.md.
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from .deps import require_role
from .store import CODED_KINDS, RefUnknown, User, store
from .tenancy import require_tenant

router = APIRouter(tags=["production"])

RESERVED = {"id", "tenant_id", "created_at", "updated_at", "data"}

# API-level defaults, applied identically on every storage backend.
DEFAULTS: dict[str, dict] = {
    "zones": {"status": "ACTIVE"},
    "mother_plants": {"status": "ALIVE"},
    "crop_plans": {"status": "DRAFT"},
    "lots": {"status": "IN_STOCK", "unit": "kg"},
}


class RecordIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
    name: str | None = None
    status: str | None = None
    # ZON
    area_ha: float | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    geom: dict | None = None
    crop_group: str | None = None
    season: str | None = None
    water_source: str | None = None
    managing_entity: str | None = None
    # MPL
    species: str | None = None
    variety: str | None = None
    scientific_name: str | None = None
    origin: str | None = None
    planting_year: int | None = None
    owner_manager: str | None = None
    recognition_no: str | None = None
    issuing_authority: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    # FLD
    crop_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    target_yield_kg: float | None = None
    event_type: str | None = None
    occurred_at: datetime | None = None
    actor: str | None = None
    device: str | None = None
    notes: str | None = None
    materials: list[dict] | None = None
    # LOT
    harvest_date: date | None = None
    quantity: float | None = None
    unit: str | None = None
    harvested_by: str | None = None
    quality_grade: str | None = None
    expiry_date: date | None = None
    # references (resolved inside the tenant)
    zone_code: str | None = None
    plant_code: str | None = None
    plan_code: str | None = None


async def _create(tenant: str, actor: User, kind: str, prefix: str, body: RecordIn) -> dict:
    fields = body.model_dump(mode="json", exclude_none=True)
    for key in RESERVED:
        fields.pop(key, None)
    for key, value in DEFAULTS.get(kind, {}).items():
        fields.setdefault(key, value)
    if kind in CODED_KINDS and not fields.get("code"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CODE_REQUIRED", "message": "code is required for this object type"},
        )
    try:
        record = await store.create_record(tenant, kind, fields)
    except RefUnknown as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REF_UNKNOWN",
                    "message": f"Reference does not exist in this tenant: {exc.field_name}"},
        ) from exc
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CODE_EXISTS", "message": "code already exists in this tenant"},
        )
    await store.record_audit(scope="tenant", tenant_id=tenant, actor=actor.username,
                       action=f"{prefix}_CREATE",
                       target=record.get("code") or str(record["id"]), outcome="OK")
    return record


async def _list(tenant: str, kind: str) -> dict:
    return {"tenant_id": tenant, "items": await store.list_records(tenant, kind)}


async def _get(tenant: str, kind: str, code: str) -> dict:
    record = await store.get_record_by_code(tenant, kind, code)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND", "message": "Object not found"})
    return record


# ---- ZON -------------------------------------------------------------------
@router.post("/zones", status_code=status.HTTP_201_CREATED)
async def create_zone(body: RecordIn, tenant: str = Depends(require_tenant),
                      actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "zones", "ZON", body)


@router.get("/zones")
async def list_zones(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "zones")


@router.get("/zones/{code}")
async def get_zone(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "zones", code)


# ---- MPL -------------------------------------------------------------------
@router.post("/mother-plants", status_code=status.HTTP_201_CREATED)
async def create_mother_plant(body: RecordIn, tenant: str = Depends(require_tenant),
                              actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "mother_plants", "MPL", body)


@router.get("/mother-plants")
async def list_mother_plants(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "mother_plants")


@router.get("/mother-plants/{code}")
async def get_mother_plant(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "mother_plants", code)


# ---- FLD -------------------------------------------------------------------
@router.post("/crop-plans", status_code=status.HTTP_201_CREATED)
async def create_crop_plan(body: RecordIn, tenant: str = Depends(require_tenant),
                           actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "crop_plans", "FLD", body)


@router.get("/crop-plans")
async def list_crop_plans(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "crop_plans")


@router.get("/crop-plans/{code}")
async def get_crop_plan(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "crop_plans", code)


@router.post("/field-events", status_code=status.HTTP_201_CREATED)
async def create_field_event(body: RecordIn, tenant: str = Depends(require_tenant),
                             actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "field_events", "FLD", body)


@router.get("/field-events")
async def list_field_events(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "field_events")


# ---- LOT -------------------------------------------------------------------
@router.post("/lots", status_code=status.HTTP_201_CREATED)
async def create_lot(body: RecordIn, tenant: str = Depends(require_tenant),
                     actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "lots", "LOT", body)


@router.get("/lots")
async def list_lots(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "lots")


@router.get("/lots/{code}")
async def get_lot(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "lots", code)
