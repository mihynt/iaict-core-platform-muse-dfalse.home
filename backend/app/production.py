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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from .config import settings
from .deps import require_role
from .store import CODED_KINDS, RECORD_REFS, RefUnknown, User, store
from . import pii
from .tenancy import require_tenant

router = APIRouter(tags=["production"])

RESERVED = {"id", "tenant_id", "created_at", "updated_at", "data"}

# API-level defaults, applied identically on every storage backend.
DEFAULTS: dict[str, dict] = {
    "zones": {"status": "ACTIVE"},
    "mother_plants": {"status": "ALIVE"},
    "crop_plans": {"status": "DRAFT"},
    "lots": {"status": "IN_STOCK", "unit": "kg"},
    "packing_lots": {"status": "PACKED"},
    "traceability_records": {"sync_status": "PENDING_SYNC",
                             "data_carrier_type": "QR_CODE"},
}


class RecordIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")
    name: str | None = None
    status: str | None = None
    # GD3 Bang 14/16/19-22: livestock + monitoring logs
    facility_actor_code: str | None = None
    management_granularity: str | None = None
    species_code: str | None = None
    breed_variety_name: str | None = None
    birth_or_import_date: str | None = None
    initial_head_count: int | None = None
    current_head_count: int | None = None
    lifecycle_status: str | None = None
    registration_date: str | None = None
    expected_harvest_start: str | None = None
    supervising_agency_name: str | None = None
    supervision_date: str | None = None
    pest_control_compliant: bool | None = None
    diary_records_compliant: bool | None = None
    supervision_outcome: str | None = None
    report_minutes_no: str | None = None
    declarant_actor_code: str | None = None
    monitoring_type: str | None = None
    inspection_timestamp: str | None = None
    pest_species_detected: str | None = None
    pest_density_index: str | None = None
    quarantine_cert_no: str | None = None
    compliance_conclusion: str | None = None
    monitoring_id: int | None = None
    measured_timestamp: str | None = None
    water_salinity_permille: float | None = None
    ph_value: float | None = None
    dissolved_oxygen_mg_l: float | None = None
    water_temp_celsius: float | None = None
    nh3_unionized_mg_l: float | None = None
    no2_nitrite_mg_l: float | None = None
    alkalinity_mg_l: float | None = None
    is_within_safe_range: bool | None = None
    sampling_standard_code: str | None = None
    mrl_rule_code: str | None = None
    measured_value: float | None = None
    measurement_unit: str | None = None
    applied_mrl_limit: float | None = None
    is_mrl_exceeded: bool | None = None
    testing_lab_name: str | None = None
    lab_test_report_no: str | None = None
    species_category_code: str | None = None
    declared_quantity: float | None = None
    quantity_unit: str | None = None
    farming_purpose: str | None = None
    # GD3 Bang 8-10: market approvals, foreign warnings, certifications
    foreign_approval_code: str | None = None
    submitted_to_foreign_date: str | None = None
    foreign_approved_date: str | None = None
    foreign_market_status: str | None = None
    violated_facility_actor_code: str | None = None
    violated_packing_lot_code: str | None = None
    official_notice_number: str | None = None
    notification_date: str | None = None
    violation_type: str | None = None
    detected_pest_or_substance: str | None = None
    foreign_sanction_action: str | None = None
    remediation_report_sent_at: str | None = None
    sanction_lifted_date: str | None = None
    certified_entity_type: str | None = None
    facility_actor_code: str | None = None
    scheme_code: str | None = None
    certificate_number: str | None = None
    cert_body_name: str | None = None
    cert_status: str | None = None
    cert_scan_url: str | None = None
    # REF catalogues (GD3, Bang 1-5) + zone jurisdiction link
    parent_unit_code: str | None = None
    admin_level: str | None = None
    official_name: str | None = None
    puc_prefix_code: str | None = None
    boundary_polygon_gis: dict | None = None
    is_active: bool | None = None
    market_name: str | None = None
    requires_bilateral_pre_approval: bool | None = None
    competent_authority_name: str | None = None
    protocol_reference_doc: str | None = None
    quarantine_special_rules: str | None = None
    substance_code: str | None = None
    substance_name: str | None = None
    substance_category: str | None = None
    market_code: str | None = None
    commodity_group_code: str | None = None
    approval_status: str | None = None
    mrl_threshold_value: float | None = None
    mrl_measurement_unit: str | None = None
    default_phi_days: int | None = None
    legal_circular_ref: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    scheme_name: str | None = None
    scheme_level: str | None = None
    applicable_sector: str | None = None
    cb_accreditation_req: str | None = None
    mode_name: str | None = None
    vehicle_id_format_rule: str | None = None
    customs_circular_ref: str | None = None
    jurisdiction_commune_code: str | None = None
    # ZON
    area_ha: float | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    geom: dict | None = None
    # ZON — industry code & VietGAP buffer distances (T-024, Bang 7)
    vsic_code: str | None = None
    dist_to_residential_m: float | None = None
    dist_to_sensitive_zone_m: float | None = None
    bee_site_min_dist_km: float | None = None
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
    is_group_leader: bool | None = None
    legal_id: str | None = None
    # Traceability dossier Bang 6/18 descriptive fields (T-028 audit)
    gs1_role_ai: str | None = None
    dosage_concentration: str | None = None
    total_quantity_applied: str | None = None
    crop_animal_growth_stage: str | None = None
    target_pest_disease_reason: str | None = None
    ics_training_completed: bool | None = None
    valid_from: date | None = None
    valid_to: date | None = None
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
    owner_consent_doc_url: str | None = None
    status_change_reason: str | None = None
    status_decision_doc: str | None = None
    status_remediation: str | None = None
    # T-031 conformance sweep (DEC-013: fields follow the 33 tables)
    farm_scale_tier: str | None = None
    submission_channel: str | None = None
    application_received_at: datetime | None = None
    forest_origin_type: str | None = None
    aquaculture_water_type: str | None = None
    earth_terrace_compliant: bool | None = None
    vessel_reg_number: str | None = None
    vessel_length_max_m: float | None = None
    tech_safety_cert_no: str | None = None
    vms_device_serial: str | None = None
    forest_harvest_plan_no: str | None = None
    departure_port_code: str | None = None
    arrival_port_code: str | None = None
    food_safety_cert_id: str | None = None
    carcass_serial_id: str | None = None
    ecdt_cc_cert_number: str | None = None
    cites_permit_number: str | None = None
    cites_specimen_mark_code: str | None = None
    forestry_enterprise_class: str | None = None
    harvest_time: str | None = None
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
    purchase_invoice_no: str | None = None
    qcvn_scheme_id: str | None = None
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
    phi_days: int | None = None
    application_method: str | None = None
    fruit_bagging_count: int | None = None
    safe_harvest_date: date | None = None
    # LOT
    harvest_date: date | None = None
    quantity: float | None = None
    unit: str | None = None
    expiry_date: date | None = None
    weigh_slip_number: str | None = None
    traceability_code: str | None = None
    data_retention_until: date | None = None
    # PKL/PKI/PKU/TXR/CTE — packing chain & traceability records (D-STD-01 ph.2)
    phc_code: str | None = None
    product_name: str | None = None
    output_weight_kg: float | None = None
    yield_norm_ratio: float | None = None
    storage_type: str | None = None
    packed_at: datetime | None = None
    allocated_weight_kg: float | None = None
    linked_at: datetime | None = None
    level: str | None = None
    gtin_code: str | None = None
    sscc_code: str | None = None
    package_spec: str | None = None
    units_count: int | None = None
    product_image_url: str | None = None
    business_unit_name: str | None = None
    business_unit_address: str | None = None
    production_event_time: datetime | None = None
    brand_trademark_serial: str | None = None
    expiration_date: date | None = None
    data_carrier_type: str | None = None
    sync_status: str | None = None
    stage_no: int | None = None
    stage_name: str | None = None
    product_trace_code: str | None = None
    location_trace_code: str | None = None
    batch_lot_number: str | None = None
    event_time: datetime | None = None
    scheme_code: str | None = None
    planting_density: float | None = None
    seed_origin_doc: str | None = None
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
    facility_code: str | None = None
    packing_lot_code: str | None = None
    harvest_lot_code: str | None = None
    packaging_unit_code: str | None = None


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
        dated = [(e["safe_harvest_date"], e) for e in events
                 if e.get("plan_code") == plan_code
                 and e.get("safe_harvest_date")]
        max_safe = max((d for d, _ in dated), default=None)
        # Bang 24 (LOG_PHI_VALIDATION): keep a reference to the treatment
        # whose PHI ends last — the one that set the safe date.
        last_ref = None
        if max_safe is not None:
            last_event = max(dated, key=lambda de: de[0])[1]
            last_ref = str(last_event.get("id"))
        blocked = max_safe is not None and fields["harvest_date"] < max_safe
        await store.create_record(tenant, "phi_validations", {
            "lot_code": fields.get("code"), "plan_code": plan_code,
            "max_safe_harvest_date": max_safe,
            "actual_harvest_date": fields["harvest_date"],
            "validation_outcome": "BLOCKED_VIOLATION_PHI" if blocked else "PASSED_SAFE",
            "last_treatment_ref": last_ref,
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


async def _prepare_packing_input(tenant: str, fields: dict) -> None:
    """A packing-input link must name BOTH ends (T-017/S1: a dangling link
    used to be creatable and later crashed traceability issuance), and a
    harvest lot cannot be allocated to packing beyond the quantity it
    actually holds (ENT_PACKING_INPUT_LINK rule, D-STD-01 phase 2)."""
    if not fields.get("packing_lot_code") or not fields.get("harvest_lot_code"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REF_REQUIRED",
                    "message": "A packing input link requires both "
                               "packing_lot_code and harvest_lot_code"})
    code = fields.get("harvest_lot_code")
    allocated = fields.get("allocated_weight_kg")
    if allocated is None:
        return
    harvest = await store.get_record_by_code(tenant, "lots", code)
    if harvest is None or harvest.get("quantity") is None:
        return
    used = sum(i.get("allocated_weight_kg") or 0
               for i in await store.list_records(tenant, "packing_inputs")
               if i.get("harvest_lot_code") == code)
    if used + allocated > harvest["quantity"] + 1e-9:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "HARVEST_LOT_OVER_ALLOCATED",
                    "message": f"Harvest lot {code} holds {harvest['quantity']} kg; "
                               f"{used} kg already allocated, cannot add {allocated} kg"})


async def _packing_context(tenant: str, fields: dict):
    """Resolve packaging unit -> packing lot -> facility actor."""
    unit = None
    if fields.get("packaging_unit_code"):
        unit = await store.get_record_by_code(tenant, "packaging_units",
                                              fields["packaging_unit_code"])
    plot = None
    if unit is not None and unit.get("packing_lot_code"):
        plot = await store.get_record_by_code(tenant, "packing_lots",
                                              unit["packing_lot_code"])
    facility = None
    if plot is not None and plot.get("facility_code"):
        facility = await store.get_record_by_code(tenant, "actors",
                                                  plot["facility_code"])
    return unit, plot, facility


async def _prepare_traceability_record(tenant: str, fields: dict) -> None:
    """National traceability record (SYS_TRACEABILITY_RECORD, TT 02/2024):
    the packing mass-balance gate runs here — no traceability code may be
    issued for a packed lot whose output exceeds inputs x yield norm —
    then the record is completed from the packing chain and stamped with
    its code and retention date."""
    unit, plot, facility = await _packing_context(tenant, fields)
    if not fields.get("packaging_unit_code"):
        # T-017/M2: a national record is meaningless without its packaging
        # unit (dossier: packaging_unit_id FK NOT NULL, code NOT NULL).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "TRACEABILITY_UNIT_REQUIRED",
                    "message": "packaging_unit_code is required to issue a "
                               "traceability record"})
    if unit is not None and plot is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PACKING_CHAIN_INCOMPLETE",
                    "message": f"Packaging unit {unit['code']} is not linked "
                               "to a packing lot"})
    if plot is None:
        return  # unknown unit code: the generic REF_UNKNOWN check reports it
    output = plot.get("output_weight_kg")
    norm = plot.get("yield_norm_ratio")
    if output is None or norm is None:
        # T-017/M1: the mass-balance gate must not be skippable by leaving
        # the norm (NOT NULL in the dossier) or the output undeclared.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PACKING_DATA_INCOMPLETE",
                    "message": f"Packing lot {plot['code']} must declare "
                               "output_weight_kg and yield_norm_ratio before "
                               "a traceability record can be issued"})
    inputs = sum(i.get("allocated_weight_kg") or 0
                 for i in await store.list_records(tenant, "packing_inputs")
                 if i.get("packing_lot_code") == plot["code"])
    if inputs * norm + 1e-9 < output:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PACKING_MASS_BALANCE_EXCEEDED",
                    "message": f"Packed output {output} kg exceeds "
                               f"{inputs} kg inputs x yield norm {norm}"})
    fields.setdefault("product_name", plot.get("product_name"))
    if fields.get("expiration_date") is None and plot.get("expiry_date"):
        fields["expiration_date"] = plot["expiry_date"]
    if fields.get("production_event_time") is None and plot.get("packed_at"):
        fields["production_event_time"] = plot["packed_at"]
    if facility is not None:
        fields.setdefault("business_unit_name", facility.get("name"))
        fields.setdefault("business_unit_address", facility.get("address"))
    if not fields.get("traceability_code"):
        location = plot.get("phc_code") or plot.get("facility_code") or ""
        event_time = fields.get("production_event_time") or date.today().isoformat()
        fields["traceability_code"] = "|".join([
            (unit or {}).get("gtin_code") or (unit or {}).get("code") or "",
            location, plot["code"], str(event_time)])
    # T-017/M3: traceability codes are unique per tenant (dossier: UNIQUE).
    existing = await store.list_records(tenant, "traceability_records")
    if any(r.get("traceability_code") == fields["traceability_code"]
           for r in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "TRACEABILITY_CODE_EXISTS",
                    "message": f"Traceability code {fields['traceability_code']} "
                               "was already issued"})
    if not fields.get("data_retention_until"):
        expiry = _iso_date(fields.get("expiration_date"))
        packed = _iso_date(fields.get("production_event_time"))
        if expiry is not None:
            fields["data_retention_until"] = _add_months(expiry, 12).isoformat()
        elif plot.get("storage_type") == "FROZEN_PROCESSED" and packed is not None:
            fields["data_retention_until"] = _add_months(packed, 24).isoformat()
        else:
            # T-017/M5 (fresh case): the dossier anchors retention for
            # produce without an expiry date to the HARVEST date (+12
            # months) — the latest harvest among the packing inputs —
            # not to the packing date.
            harvest_dates = []
            for link in await store.list_records(tenant, "packing_inputs"):
                if link.get("packing_lot_code") != plot["code"]:
                    continue
                harvest = await store.get_record_by_code(
                    tenant, "lots", link.get("harvest_lot_code") or "")
                day = _iso_date((harvest or {}).get("harvest_date"))
                if day is not None:
                    harvest_dates.append(day)
            anchor = max(harvest_dates) if harvest_dates else packed
            if anchor is not None:
                fields["data_retention_until"] = _add_months(anchor, 12).isoformat()


async def _emit_cte_stages(tenant: str, record: dict,
                           actor: User | None = None) -> None:
    """Auto-build the CTE stage chain for a fresh traceability record:
    one harvest stage per packing input, then the packing stage."""
    unit, plot, _facility = await _packing_context(tenant, record)
    if unit is None or plot is None:
        return
    code = record.get("traceability_code")
    if not code:
        return
    inputs = [i for i in await store.list_records(tenant, "packing_inputs")
              if i.get("packing_lot_code") == plot["code"]]
    for link in inputs:
        # T-017/S1: tolerate legacy links without a harvest end instead of
        # crashing after the record has already been created.
        if not link.get("harvest_lot_code"):
            continue
        harvest = await store.get_record_by_code(tenant, "lots",
                                                 link["harvest_lot_code"])
        if harvest is None:
            continue
        location = harvest.get("zone_code") or ""
        if harvest.get("zone_code"):
            zone = await store.get_record_by_code(tenant, "zones",
                                                  harvest["zone_code"])
            if zone is not None and zone.get("puc_code"):
                location = zone["puc_code"]
        stage = await store.create_record(tenant, "cte_stages", {
            "traceability_code": code, "stage_no": 1,
            "stage_name": "Thu hoach tai vung trong",
            "product_trace_code": harvest["code"],
            "location_trace_code": location,
            "batch_lot_number": harvest["code"],
            "event_time": harvest.get("harvest_date"),
        })
        if actor is not None and stage is not None:
            await store.record_audit(
                scope="tenant", tenant_id=tenant, actor=actor.username,
                action="CTE_CREATE", target=code, outcome="OK")
    stage = await store.create_record(tenant, "cte_stages", {
        "traceability_code": code, "stage_no": 2,
        "stage_name": "So che va dong goi",
        "product_trace_code": unit.get("gtin_code") or unit["code"],
        "location_trace_code": plot.get("phc_code") or plot.get("facility_code") or "",
        "batch_lot_number": plot["code"],
        "event_time": record.get("production_event_time"),
    })
    if actor is not None and stage is not None:
        await store.record_audit(
            scope="tenant", tenant_id=tenant, actor=actor.username,
            action="CTE_CREATE", target=code, outcome="OK")


def _validate_gtin(fields: dict) -> None:
    """GS1 format discipline (T-024): when a GTIN is declared it must be
    all digits. Length (8/12/13/14) and check-digit (mod-10) enforcement
    are deliberately NOT applied yet — placeholder and sample codes
    already in circulation (including dossier-era examples used in
    tests and the UI) fail those rules, so hard enforcement would
    break the pilot; full GS1 validation lands with a data-cleanup
    decision (review leftover L1)."""
    gtin = fields.get("gtin_code")
    if gtin is not None and not str(gtin).isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "GTIN_INVALID",
                    "message": "gtin_code must contain digits only"})


def _snap(record: dict | None) -> str | None:
    """Bang 33 audit snapshot: JSON of the record, size-capped."""
    if record is None:
        return None
    import copy as _copy
    import json as _json
    return _json.dumps(_copy.deepcopy(record), ensure_ascii=False,
                       default=str)[:8000]


def _prepare_residue_detail(fields: dict) -> None:
    """Bang 21: is_mrl_exceeded is a generated flag (measured > limit)."""
    mv, lim = fields.get("measured_value"), fields.get("applied_mrl_limit")
    if mv is not None and lim is not None:
        fields["is_mrl_exceeded"] = mv > lim


async def _prepare_certification(tenant: str, fields: dict) -> None:
    """Bang 10: the certified target must match the declared entity type."""
    etype = fields.get("certified_entity_type")
    if etype == "PRODUCTION_ZONE" and not fields.get("zone_code"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CERT_TARGET_REQUIRED",
                    "message": "certified_entity_type=PRODUCTION_ZONE requires zone_code"})
    if etype == "FACILITY_ACTOR" and not fields.get("facility_actor_code"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CERT_TARGET_REQUIRED",
                    "message": "certified_entity_type=FACILITY_ACTOR requires facility_actor_code"})


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
    if kind == "entity_certifications":
        await _prepare_certification(tenant, fields)
    if kind == "residue_test_details":
        _prepare_residue_detail(fields)
    elif kind == "packing_inputs":
        await _prepare_packing_input(tenant, fields)
    elif kind == "traceability_records":
        await _prepare_traceability_record(tenant, fields)
    elif kind == "packaging_units":
        _validate_gtin(fields)
    if kind == "actors":
        fields = pii.protect(fields, tenant)
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
                       target=record.get("code") or str(record["id"]), outcome="OK",
                       new_value=_snap(record))
    return pii.restore(record) if kind == "actors" else record


async def _list(tenant: str, kind: str) -> dict:
    items = await store.list_records(tenant, kind)
    if kind == "actors":
        items = [pii.restore(r) for r in items]
    return {"tenant_id": tenant, "items": items}


async def _get(tenant: str, kind: str, code: str) -> dict:
    record = await store.get_record_by_code(tenant, kind, code)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND", "message": "Object not found"})
    return pii.restore(record) if kind == "actors" else record


# ---- ZON -------------------------------------------------------------------
@router.post("/zones", status_code=status.HTTP_201_CREATED)
async def create_zone(body: RecordIn, tenant: str = Depends(require_tenant),
                      actor: User = Depends(require_role("OPERATOR"))) -> dict:
    record = await _create(tenant, actor, "zones", "ZON", body)
    if record.get("puc_status"):
        await _log_zone_status(tenant, actor, record, None, body)
    return record


DASHBOARD_KINDS = ("zones", "mother_plants", "crop_plans", "field_events",
                   "lots", "actors", "input_lots", "packing_lots",
                   "traceability_records")


@router.get("/dashboard")
async def dashboard(request: Request, tenant: str = Depends(require_tenant)) -> dict:
    """One-call summary for the UI home screen (audit T-021, pack P1):
    per-kind counts plus the latest audit entries, replacing the previous
    fan-out of one health call + one full list per stat card."""
    counts = {}
    for kind in DASHBOARD_KINDS:
        counts[kind] = await store.count_records(tenant, kind)
    counts["users"] = await store.tenant_user_count(tenant)
    audit = await store.audit_for_tenant(tenant)
    env_name = settings.app_env
    scope_env = request.scope.get("env")
    if scope_env is not None and getattr(scope_env, "APP_ENV", None):
        env_name = scope_env.APP_ENV
    return {"tenant": tenant, "counts": counts,
            "recent_audit": list(reversed(audit[-5:])),
            "storage": getattr(store, "kind", "unknown"),
            "env": env_name, "version": request.app.version}


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


@router.post("/zone-parcel-links/{link_id}/withdraw")
async def withdraw_zone_parcel_link(link_id: int,
                                    tenant: str = Depends(require_tenant),
                                    actor: User = Depends(require_role("OPERATOR"))) -> dict:
    links = await store.list_records(tenant, "zone_parcel_links")
    link = next((x for x in links if x.get("id") == link_id), None)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND", "message": "Object not found"})
    if link.get("membership_status") == "WITHDRAWN_FROM_ZONE":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "ALREADY_WITHDRAWN",
                                    "message": "Parcel already withdrawn from the zone"})
    record = await store.update_record_by_id(
        tenant, "zone_parcel_links", link_id,
        {"membership_status": "WITHDRAWN_FROM_ZONE",
         "left_date": date.today().isoformat()})
    await store.record_audit(scope="tenant", tenant_id=tenant,
                             actor=actor.username, action="ZPL_WITHDRAW",
                             target=f"{link.get('zone_code')}/{link.get('parcel_code')}",
                             outcome="OK")
    return record


@router.get("/phi-validations")
async def list_phi_validations(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "phi_validations")


# ---- Packing chain & traceability records (D-STD-01, phase 2) ---------------
@router.post("/packing-lots", status_code=status.HTTP_201_CREATED)
async def create_packing_lot(body: RecordIn, tenant: str = Depends(require_tenant),
                             actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "packing_lots", "PKL", body)


@router.get("/packing-lots")
async def list_packing_lots(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "packing_lots")


@router.get("/packing-lots/{code}")
async def get_packing_lot(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "packing_lots", code)


@router.post("/packing-inputs", status_code=status.HTTP_201_CREATED)
async def create_packing_input(body: RecordIn, tenant: str = Depends(require_tenant),
                               actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "packing_inputs", "PKI", body)


@router.get("/packing-inputs")
async def list_packing_inputs(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "packing_inputs")


@router.post("/packaging-units", status_code=status.HTTP_201_CREATED)
async def create_packaging_unit(body: RecordIn, tenant: str = Depends(require_tenant),
                                actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "packaging_units", "PKU", body)


@router.get("/packaging-units")
async def list_packaging_units(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "packaging_units")


@router.get("/packaging-units/{code}")
async def get_packaging_unit(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "packaging_units", code)


@router.post("/traceability-records", status_code=status.HTTP_201_CREATED)
async def create_traceability_record(body: RecordIn, tenant: str = Depends(require_tenant),
                                     actor: User = Depends(require_role("OPERATOR"))) -> dict:
    record = await _create(tenant, actor, "traceability_records", "TXR", body)
    await _emit_cte_stages(tenant, record, actor)
    return record


@router.get("/traceability-records")
async def list_traceability_records(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "traceability_records")


@router.post("/cte-stages", status_code=status.HTTP_201_CREATED)
async def create_cte_stage(body: RecordIn, tenant: str = Depends(require_tenant),
                           actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "cte_stages", "CTE", body)


@router.get("/cte-stages")
async def list_cte_stages(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "cte_stages")


# ---- REF catalogues (D-STD-01 phase 3, Bang 1-5) ---------------------------

@router.post("/ref-admin-units", status_code=status.HTTP_201_CREATED)
async def create_ref_admin_unit(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "ref_admin_units", "ADM", body)


@router.get("/ref-admin-units")
async def list_ref_admin_units(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "ref_admin_units")


@router.get("/ref-admin-units/{code}")
async def get_ref_admin_unit(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "ref_admin_units", code)

@router.post("/ref-market-regulations", status_code=status.HTTP_201_CREATED)
async def create_ref_market_regulation(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "ref_market_regulations", "MKT", body)


@router.get("/ref-market-regulations")
async def list_ref_market_regulations(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "ref_market_regulations")


@router.get("/ref-market-regulations/{code}")
async def get_ref_market_regulation(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "ref_market_regulations", code)

@router.post("/ref-active-substance-mrls", status_code=status.HTTP_201_CREATED)
async def create_ref_active_substance_mrl(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "ref_active_substance_mrls", "MRL", body)


@router.get("/ref-active-substance-mrls")
async def list_ref_active_substance_mrls(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "ref_active_substance_mrls")


@router.get("/ref-active-substance-mrls/{code}")
async def get_ref_active_substance_mrl(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "ref_active_substance_mrls", code)

@router.post("/ref-certification-schemes", status_code=status.HTTP_201_CREATED)
async def create_ref_certification_scheme(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "ref_certification_schemes", "SCH", body)


@router.get("/ref-certification-schemes")
async def list_ref_certification_schemes(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "ref_certification_schemes")


@router.get("/ref-certification-schemes/{code}")
async def get_ref_certification_scheme(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "ref_certification_schemes", code)

@router.post("/ref-transport-modes", status_code=status.HTTP_201_CREATED)
async def create_ref_transport_mode(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "ref_transport_modes", "TRM", body)


@router.get("/ref-transport-modes")
async def list_ref_transport_modes(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "ref_transport_modes")


@router.get("/ref-transport-modes/{code}")
async def get_ref_transport_mode(code: str, tenant: str = Depends(require_tenant)) -> dict:
    return await _get(tenant, "ref_transport_modes", code)


# ---- GD3 group B: approvals, warnings, certifications (Bang 8-10) ----------

@router.post("/zone-market-approvals", status_code=status.HTTP_201_CREATED)
async def create_zone_market_approval(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "zone_market_approvals", "ZMA", body)


@router.get("/zone-market-approvals")
async def list_zone_market_approvals(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "zone_market_approvals")

@router.post("/foreign-warnings", status_code=status.HTTP_201_CREATED)
async def create_foreign_warning(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "foreign_warnings", "FWN", body)


@router.get("/foreign-warnings")
async def list_foreign_warnings(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "foreign_warnings")

@router.post("/entity-certifications", status_code=status.HTTP_201_CREATED)
async def create_entity_certification(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "entity_certifications", "ECT", body)


@router.get("/entity-certifications")
async def list_entity_certifications(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "entity_certifications")


# ---- GD3 monitoring group (Bang 14, 16, 19-22) ------------------------------

@router.post("/livestock-units", status_code=status.HTTP_201_CREATED)
async def create_livestock_unit(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "livestock_units", "LVU", body)


@router.get("/livestock-units")
async def list_livestock_units(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "livestock_units")

@router.post("/pre-harvest-supervisions", status_code=status.HTTP_201_CREATED)
async def create_pre_harvest_supervision(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "pre_harvest_supervisions", "PHS", body)


@router.get("/pre-harvest-supervisions")
async def list_pre_harvest_supervisions(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "pre_harvest_supervisions")

@router.post("/monitoring-declarations", status_code=status.HTTP_201_CREATED)
async def create_monitoring_declaration(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "monitoring_declarations", "MON", body)


@router.get("/monitoring-declarations")
async def list_monitoring_declarations(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "monitoring_declarations")

@router.post("/water-quality-tests", status_code=status.HTTP_201_CREATED)
async def create_water_quality_test(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "water_quality_tests", "WQT", body)


@router.get("/water-quality-tests")
async def list_water_quality_tests(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "water_quality_tests")

@router.post("/residue-test-details", status_code=status.HTTP_201_CREATED)
async def create_residue_test_detail(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "residue_test_details", "RTD", body)


@router.get("/residue-test-details")
async def list_residue_test_details(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "residue_test_details")

@router.post("/livestock-decl-items", status_code=status.HTTP_201_CREATED)
async def create_livestock_decl_item(body: RecordIn, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _create(tenant, actor, "livestock_decl_items", "LDI", body)


@router.get("/livestock-decl-items")
async def list_livestock_decl_items(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "livestock_decl_items")


@router.patch("/livestock-units/{rec_id}")
async def update_livestock_unit(rec_id: int, body: RecordIn,
                                tenant: str = Depends(require_tenant),
                                actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update_by_id(tenant, actor, "livestock_units", "LVU", rec_id, body)


# ---- Updates (T-023) -------------------------------------------------------
# Master-data kinds can be corrected after creation; evidence-like kinds
# (field events, harvest lots, packing links, traceability records, CTE
# stages, PHI validations) stay append-only, and creation gates are NOT
# re-run on update — dependent gates read current values when they run
# (e.g. the packing mass-balance gate at record issuance).

async def _update(tenant: str, actor: User, kind: str, prefix: str,
                  code: str, body: RecordIn) -> dict:
    fields = body.model_dump(mode="json", exclude_none=True)
    for key in RESERVED:
        fields.pop(key, None)
    if "code" in fields and fields["code"] != code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "CODE_IMMUTABLE",
                    "message": "code cannot be changed after creation"})
    fields.pop("code", None)
    if kind == "actors":
        fields = pii.protect(fields, tenant)
    import copy as _copy
    _before = await store.get_record_by_code(tenant, kind, code)
    _before = _copy.deepcopy(_before) if _before is not None else None
    try:
        record = await store.update_record(tenant, kind, code, fields)
    except RefUnknown as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REF_UNKNOWN",
                    "message": f"Reference does not exist in this tenant: {exc.field_name}"},
        ) from exc
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND",
                                    "message": "Object not found"})
    await store.record_audit(scope="tenant", tenant_id=tenant,
                             actor=actor.username,
                             action=f"{prefix}_UPDATE",
                             target=code, outcome="OK",
                             old_value=_snap(_before), new_value=_snap(record))
    return pii.restore(record) if kind == "actors" else record


async def _log_zone_status(tenant: str, actor: User, zone: dict,
                           previous: str | None, body: RecordIn) -> None:
    """Bang 13 (LOG_ZONE_STATUS_HISTORY): one row per PUC status change."""
    await store.create_record(tenant, "zone_status_history", {
        "zone_code": zone["code"], "previous_status": previous,
        "new_status": zone.get("puc_status"), "changed_by": actor.username,
        "trigger_reason_code": body.status_change_reason,
        "decision_doc_number": body.status_decision_doc,
        "remediation_measures": body.status_remediation})
    await store.record_audit(scope="tenant", tenant_id=tenant,
                             actor=actor.username, action="ZON_STATUS_CHANGE",
                             target=zone["code"], outcome="OK")


@router.patch("/zones/{code}")
async def update_zone(code: str, body: RecordIn,
                      tenant: str = Depends(require_tenant),
                      actor: User = Depends(require_role("OPERATOR"))) -> dict:
    old = await store.get_record_by_code(tenant, "zones", code)
    old_status = old.get("puc_status") if old else None
    reason, doc, remed = (body.status_change_reason, body.status_decision_doc,
                          body.status_remediation)
    body.status_change_reason = body.status_decision_doc = None
    body.status_remediation = None
    record = await _update(tenant, actor, "zones", "ZON", code, body)
    if old is not None and record.get("puc_status") != old_status:
        body.status_change_reason, body.status_decision_doc = reason, doc
        body.status_remediation = remed
        await _log_zone_status(tenant, actor, record, old_status, body)
    return record


@router.get("/zone-status-history")
async def list_zone_status_history(tenant: str = Depends(require_tenant)) -> dict:
    return await _list(tenant, "zone_status_history")


@router.patch("/mother-plants/{code}")
async def update_mother_plant(code: str, body: RecordIn,
                              tenant: str = Depends(require_tenant),
                              actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "mother_plants", "MPL", code, body)


@router.patch("/actors/{code}")
async def update_actor(code: str, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "actors", "ACT", code, body)


@router.patch("/spatial-units/{code}")
async def update_spatial_unit(code: str, body: RecordIn,
                              tenant: str = Depends(require_tenant),
                              actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "spatial_units", "SPU", code, body)


@router.patch("/input-lots/{code}")
async def update_input_lot(code: str, body: RecordIn,
                           tenant: str = Depends(require_tenant),
                           actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "input_lots", "INP", code, body)


@router.patch("/packing-lots/{code}")
async def update_packing_lot(code: str, body: RecordIn,
                             tenant: str = Depends(require_tenant),
                             actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "packing_lots", "PKL", code, body)


@router.patch("/packaging-units/{code}")
async def update_packaging_unit(code: str, body: RecordIn,
                                tenant: str = Depends(require_tenant),
                                actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "packaging_units", "PKU", code, body)



@router.patch("/ref-admin-units/{code}")
async def update_ref_admin_unit(code: str, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "ref_admin_units", "ADM", code, body)


@router.patch("/ref-market-regulations/{code}")
async def update_ref_market_regulation(code: str, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "ref_market_regulations", "MKT", code, body)


@router.patch("/ref-active-substance-mrls/{code}")
async def update_ref_active_substance_mrl(code: str, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "ref_active_substance_mrls", "MRL", code, body)


@router.patch("/ref-certification-schemes/{code}")
async def update_ref_certification_scheme(code: str, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "ref_certification_schemes", "SCH", code, body)


@router.patch("/ref-transport-modes/{code}")
async def update_ref_transport_mode(code: str, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update(tenant, actor, "ref_transport_modes", "TRM", code, body)


async def _update_by_id(tenant: str, actor: User, kind: str, prefix: str,
                        rec_id: int, body: RecordIn) -> dict:
    """PATCH for uncoded record kinds (approvals, certifications),
    addressed by numeric id; mirrors _update's audit discipline."""
    fields = body.model_dump(mode="json", exclude_none=True)
    for key in RESERVED:
        fields.pop(key, None)
    fields.pop("code", None)
    import copy as _copy
    rows = await store.list_records(tenant, kind)
    before = next((r for r in rows if r.get("id") == rec_id), None)
    if before is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND",
                                    "message": "Object not found"})
    before = _copy.deepcopy(before)
    try:
        record = await store.update_record_by_id(tenant, kind, rec_id, fields)
    except RefUnknown as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "REF_UNKNOWN",
                    "message": f"Reference does not exist in this tenant: {exc.field_name}"},
        ) from exc
    await store.record_audit(
        scope="tenant", tenant_id=tenant, actor=actor.username,
        action=f"{prefix}_UPDATE", target=str(rec_id), outcome="OK",
        old_value=_snap(before), new_value=_snap(record))
    return record



@router.patch("/zone-market-approvals/{rec_id}")
async def update_zone_market_approval(rec_id: int, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update_by_id(tenant, actor, "zone_market_approvals", "ZMA", rec_id, body)


@router.patch("/entity-certifications/{rec_id}")
async def update_entity_certification(rec_id: int, body: RecordIn,
                       tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("OPERATOR"))) -> dict:
    return await _update_by_id(tenant, actor, "entity_certifications", "ECT", rec_id, body)


# ---- Deletes (T-026) -------------------------------------------------------
# Master-data kinds can be deleted by a TENANT_ADMIN when nothing else
# references them; a referenced record is refused with 409 RECORD_IN_USE
# (checked in the API layer so every store behaves identically, and the
# composite FKs back it up on the SQL stores). Evidence-like kinds stay
# append-only: no DELETE route exists for them.

async def _delete(tenant: str, actor: User, kind: str, prefix: str,
                  code: str) -> dict:
    existing = await store.get_record_by_code(tenant, kind, code)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND",
                                    "message": "Object not found"})
    for other_kind, refs in RECORD_REFS.items():
        for ref_field, target_kind in refs.items():
            if target_kind != kind:
                continue
            for record in await store.list_records(tenant, other_kind):
                if record.get(ref_field) == code and \
                        not (other_kind == kind and record.get("code") == code):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"code": "RECORD_IN_USE",
                                "message": f"Still referenced by {other_kind} "
                                           f"record {record.get('code') or record.get('id')} "
                                           f"via {ref_field}"})
    deleted = await store.delete_record(tenant, kind, code)
    if deleted is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail={"code": "NOT_FOUND",
                                    "message": "Object not found"})
    await store.record_audit(scope="tenant", tenant_id=tenant,
                             actor=actor.username,
                             action=f"{prefix}_DELETE",
                             target=code, outcome="OK",
                             old_value=_snap(existing))
    return {"code": code, "deleted": True}


@router.delete("/zones/{code}")
async def delete_zone(code: str, tenant: str = Depends(require_tenant),
                      actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "zones", "ZON", code)


@router.delete("/mother-plants/{code}")
async def delete_mother_plant(code: str, tenant: str = Depends(require_tenant),
                              actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "mother_plants", "MPL", code)


@router.delete("/actors/{code}")
async def delete_actor(code: str, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "actors", "ACT", code)


@router.delete("/spatial-units/{code}")
async def delete_spatial_unit(code: str, tenant: str = Depends(require_tenant),
                              actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "spatial_units", "SPU", code)


@router.delete("/input-lots/{code}")
async def delete_input_lot(code: str, tenant: str = Depends(require_tenant),
                           actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "input_lots", "INP", code)


@router.delete("/packing-lots/{code}")
async def delete_packing_lot(code: str, tenant: str = Depends(require_tenant),
                             actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "packing_lots", "PKL", code)


@router.delete("/packaging-units/{code}")
async def delete_packaging_unit(code: str, tenant: str = Depends(require_tenant),
                                actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "packaging_units", "PKU", code)


@router.delete("/ref-admin-units/{code}")
async def delete_ref_admin_unit(code: str, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "ref_admin_units", "ADM", code)


@router.delete("/ref-market-regulations/{code}")
async def delete_ref_market_regulation(code: str, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "ref_market_regulations", "MKT", code)


@router.delete("/ref-active-substance-mrls/{code}")
async def delete_ref_active_substance_mrl(code: str, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "ref_active_substance_mrls", "MRL", code)


@router.delete("/ref-certification-schemes/{code}")
async def delete_ref_certification_scheme(code: str, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "ref_certification_schemes", "SCH", code)


@router.delete("/ref-transport-modes/{code}")
async def delete_ref_transport_mode(code: str, tenant: str = Depends(require_tenant),
                       actor: User = Depends(require_role("TENANT_ADMIN"))) -> dict:
    return await _delete(tenant, actor, "ref_transport_modes", "TRM", code)
