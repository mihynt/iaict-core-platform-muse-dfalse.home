"""Production core objects (M2, task T-004; traceability standard D-STD-01).

Tenant-scoped CRUD for the SRS v2.0 production groups:
- ZON  zones            (vùng nguyên liệu / site / thửa)
- MPL  mother plants    (cây/cụm cây đầu dòng)
- FLD  crop plans + field events (mùa vụ / nhật ký đồng ruộng)
- LOT  harvest lots     (lô thu hoạch)

Plus the phase-1 traceability-standard entities (D-STD-01):
actors (nông hộ/chủ thể), spatial units (thửa đất/ao/lô rừng), zone-parcel
links, input lots (lô vật tư) and the PHI validation log. Lot creation
enforces the PHI gate and the cycle mass-balance ceiling, and stamps the
national traceability code + data-retention date (see docs/DATA_MODEL.md).

Writes require role OPERATOR or higher. Object references (zone_code,
plant_code, plan_code, parcel_code, farmer_code, ...) resolve only inside
the caller's tenant. Field definitions: docs/DATA_MODEL.md.
"""
from datetime import date, datetime, timedelta

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
    # ZON — PUC identity block (D-STD-01)
    puc_code: str | None = None
    puc_status: str | None = None
    sector_category: str | None = None
    market_scope: str | None = None
    primary_species: str | None = None
    issue_date: date | None = None
    post_inspect_due_date: date | None = None
    # ACT — actors / households (D-STD-01)
    actor_type: str | None = None
    gln_code: str | None = None
    province_code: str | None = None
    district_code: str | None = None
    commune_code: str | None = None
    phone: str | None = None
    email: str | None = None
    # SPU — spatial units (D-STD-01)
    unit_type: str | None = None
    national_land_parcel_id: str | None = None
    map_sheet_number: str | None = None
    parcel_number: str | None = None
    land_tenure_doc_type: str | None = None
    land_cert_serial: str | None = None
    land_legal_owner_name: str | None = None
    forest_subzone_code: str | None = None
    forest_compartment_code: str | None = None
    forest_plot_code: str | None = None
    area_m2: float | None = None
    slope_degree: float | None = None
    # ZPL — zone/parcel membership (D-STD-01)
    registered_area_m2: float | None = None
    membership_status: str | None = None
    joined_date: date | None = None
    left_date: date | None = None
    # INP — input material lots (D-STD-01)
    category: str | None = None
    substance_code: str | None = None
    vn_registration_number: str | None = None
    batch_no: str | None = None
    purchase_date: date | None = None
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
    variety_name: str | None = None
    seed_origin: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    target_yield_kg: float | None = None
    event_type: str | None = None
    occurred_at: datetime | None = None
    actor: str | None = None
    device: str | None = None
    notes: str | None = None
    materials: list[dict] | None = None
    growth_stage: str | None = None
    target_pest: str | None = None
    dosage: str | None = None
    quantity_applied: float | None = None
    phi_days: int | None = None
    safe_harvest_date: date | None = None
    # LOT
    harvest_date: date | None = None
    quantity: float | None = None
    unit: str | None = None
    harvested_by: str | None = None
    quality_grade: str | None = None
    expiry_date: date | None = None
    weigh_slip_number: str | None = None
    traceability_code: str | None = None
    data_retention_until: date | None = None
    # references (resolved inside the tenant)
    zone_code: str | None = None
    plant_code: str | None = None
    plan_code: str | None = None
    parcel_code: str | None = None
    farmer_code: str | None = None
    supplier_code: str | None = None
    operator_code: str | None = None
    parent_code: str | None = None
    input_lot_code: str | None = None


def _iso_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
    days = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return date(y, m, min(d.day, days[m - 1]))


async def _prepare_field_event(tenant: str, fields: dict) -> None:
    """PHI bookkeeping (LOG_CULTIVATION_TREATMENT, D-STD-01): the safe
    harvest date is the treatment date plus the input lot's mandatory
    pre-harvest interval, computed at write time."""
    if fields.get("phi_days") is None and fields.get("input_lot_code"):
        input_lot = await store.get_record_by_code(tenant, "input_lots",
                                                   fields["input_lot_code"])
        if input_lot is not None and input_lot.get("phi_days") is not None:
            fields["phi_days"] = input_lot["phi_days"]
    occurred = _iso_date(fields.get("occurred_at"))
    if occurred is not None and fields.get("phi_days") is not None \
            and not fields.get("safe_harvest_date"):
        fields["safe_harvest_date"] = (
            occurred + timedelta(days=int(fields["phi_days"]))).isoformat()


async def _prepare_lot(tenant: str, fields: dict) -> None:
    """Harvest-lot gates (D-STD-01): PHI validation (logged either way),
    cycle mass-balance ceiling, traceability code and retention date."""
    harvest = _iso_date(fields.get("harvest_date"))
    plan_code = fields.get("plan_code")
    if plan_code and harvest is not None:
        events = await store.list_records(tenant, "field_events")
        safe_dates = [e["safe_harvest_date"] for e in events
                      if e.get("plan_code") == plan_code
                      and e.get("safe_harvest_date")]
        max_safe = max(safe_dates) if safe_dates else None
        blocked = max_safe is not None and fields["harvest_date"] < max_safe
        await store.create_record(tenant, "phi_validations", {
            "lot_code": fields.get("code"), "plan_code": plan_code,
            "max_safe_harvest_date": max_safe,
            "actual_harvest_date": fields["harvest_date"],
            "outcome": "BLOCKED_VIOLATION_PHI" if blocked else "PASSED_SAFE",
        })
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "PHI_VIOLATION",
                        "message": f"Harvest date {fields['harvest_date']} is before "
                                   f"the safe harvest date {max_safe} (PHI not met)"})
    if plan_code and fields.get("quantity") is not None:
        plan = await store.get_record_by_code(tenant, "crop_plans", plan_code)
        ceiling = (plan or {}).get("target_yield_kg")
        if ceiling is not None:
            existing = sum(lot.get("quantity") or 0
                           for lot in await store.list_records(tenant, "lots")
                           if lot.get("plan_code") == plan_code)
            if existing + fields["quantity"] > ceiling:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": "MASS_BALANCE_EXCEEDED",
                            "message": f"Cumulative harvest {existing + fields['quantity']} kg "
                                       f"exceeds the cycle ceiling {ceiling} kg"})
    if not fields.get("traceability_code"):
        location = fields.get("zone_code") or ""
        if fields.get("zone_code"):
            zone = await store.get_record_by_code(tenant, "zones", fields["zone_code"])
            if zone is not None and zone.get("puc_code"):
                location = zone["puc_code"]
        event_time = fields.get("harvest_date") or date.today().isoformat()
        fields["traceability_code"] = "|".join([
            plan_code or fields.get("code") or "", location,
            fields.get("code") or "", str(event_time)])
    if not fields.get("data_retention_until"):
        base = _iso_date(fields.get("expiry_date")) or harvest
        if base is not None:
            fields["data_retention_until"] = _add_months(base, 12).isoformat()


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
    if kind == "field_events":
        await _prepare_field_event(tenant, fields)
    elif kind == "lots":
        await _prepare_lot(tenant, fields)
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


# ---- Traceability standard entities (D-STD-01, phase 1) --------------------
@router.post("/actors", status_code=status.HTTP_201_CREATED)
async def create_actor(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "actors", "ACT", body)


@router.get("/actors")
async def list_actors(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "actors")


@router.get("/actors/{code}")
async def get_actor(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "actors", code)


@router.post("/spatial-units", status_code=status.HTTP_201_CREATED)
async def create_spatial_unit(body: RecordIn, tenant: str = Depends(require_tenant),
                              actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "spatial_units", "SPU", body)


@router.get("/spatial-units")
async def list_spatial_units(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "spatial_units")


@router.get("/spatial-units/{code}")
async def get_spatial_unit(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "spatial_units", code)


@router.post("/zone-parcel-links", status_code=status.HTTP_201_CREATED)
async def create_zone_parcel_link(body: RecordIn, tenant: str = Depends(require_tenant),
                                  actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "zone_parcel_links", "ZPL", body)


@router.get("/zone-parcel-links")
async def list_zone_parcel_links(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "zone_parcel_links")


@router.post("/input-lots", status_code=status.HTTP_201_CREATED)
async def create_input_lot(body: RecordIn, tenant: str = Depends(require_tenant),
                           actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "input_lots", "INP", body)


@router.get("/input-lots")
async def list_input_lots(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "input_lots")


@router.get("/input-lots/{code}")
async def get_input_lot(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "input_lots", code)


@router.get("/phi-validations")
async def list_phi_validations(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "phi_validations")
