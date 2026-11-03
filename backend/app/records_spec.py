"""Shared record layout for the PostgreSQL backends (psycopg and pg8000).

Maps each production record kind to its table and principal columns.
Column kinds: text | int | float | num (Decimal) | date | ts (timestamp) |
json. Reference code fields live in store.RECORD_REFS; their FK columns are
in REF_ID_COLUMN. Fields not listed here are stored in the `data` JSONB
column (see docs/DATA_MODEL.md).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

SPECS: dict[str, tuple[str, dict[str, str]]] = {
    "zones": ("zones", {
        "name": "text", "area_ha": "num", "address": "text", "lat": "float",
        "lon": "float", "geom": "json", "crop_group": "text", "season": "text",
        "water_source": "text", "managing_entity": "text", "status": "text",
        "owner_actor_code": "text",
        "puc_code": "text", "puc_status": "text", "sector_category": "text",
        "market_scope": "text", "primary_species": "text",
        "scientific_name": "text", "issue_date": "date",
        "issuing_authority": "text", "post_inspect_due_date": "date",
        "vsic_code": "text", "dist_to_residential_m": "num",
        "dist_to_sensitive_zone_m": "num", "bee_site_min_dist_km": "num",
    }),
    "mother_plants": ("mother_plants", {
        "species": "text", "variety": "text", "scientific_name": "text",
        "origin": "text", "planting_year": "int", "lat": "float", "lon": "float",
        "owner_manager": "text", "recognition_no": "text",
        "issuing_authority": "text", "valid_from": "date", "valid_to": "date",
        "status": "text",
    }),
    "actors": ("actors", {
        "name": "text", "actor_type": "text", "gln_code": "text",
        "province_code": "text", "district_code": "text", "commune_code": "text",
        "address": "text", "phone": "text", "email": "text",
    }),
    "spatial_units": ("spatial_units", {
        "name": "text", "unit_type": "text", "national_land_parcel_id": "text",
        "map_sheet_number": "text", "parcel_number": "text",
        "land_tenure_doc_type": "text", "land_cert_serial": "text",
        "land_legal_owner_name": "text", "forest_subzone_code": "text",
        "forest_compartment_code": "text", "forest_plot_code": "text",
        "area_m2": "num", "slope_degree": "num",
    }),
    "zone_parcel_links": ("zone_parcel_links", {
        "registered_area_m2": "num", "membership_status": "text",
        "joined_date": "date", "left_date": "date",
    }),
    "input_lots": ("input_lots", {
        "name": "text", "category": "text", "substance_code": "text",
        "vn_registration_number": "text", "batch_no": "text",
        "purchase_date": "date", "quantity": "num", "unit": "text",
        "phi_days": "int", "expiry_date": "date",
        "purchase_invoice_no": "text", "qcvn_scheme_id": "text",
    }),
    "crop_plans": ("crop_plans", {
        "name": "text", "crop_name": "text", "variety_name": "text",
        "seed_origin": "text", "planting_density": "num",
        "seed_origin_doc": "text", "start_date": "date",
        "end_date": "date", "target_yield_kg": "num", "status": "text",
    }),
    "field_events": ("field_events", {
        "event_type": "text", "occurred_at": "ts", "lat": "float", "lon": "float",
        "actor": "text", "device": "text", "notes": "text", "materials": "json",
        "growth_stage": "text", "target_pest": "text", "dosage": "text",
        "quantity_applied": "num", "phi_days": "int", "safe_harvest_date": "date",
        "application_method": "text", "fruit_bagging_count": "int",
    }),
    "lots": ("lots", {
        "harvest_date": "date", "quantity": "num", "unit": "text",
        "harvested_by": "text", "quality_grade": "text", "status": "text",
        "expiry_date": "date", "weigh_slip_number": "text",
        "traceability_code": "text", "data_retention_until": "date",
    }),
    "zone_status_history": ("zone_status_history", {
        "zone_code": "text", "previous_status": "text", "new_status": "text",
        "trigger_reason_code": "text", "decision_doc_number": "text",
        "remediation_measures": "text", "changed_by": "text",
    }),
    "phi_validations": ("phi_validations", {
        "lot_code": "text", "plan_code": "text",
        "max_safe_harvest_date": "date", "actual_harvest_date": "date",
        "outcome": "text", "last_treatment_ref": "text",
    }),
    "packing_lots": ("packing_lots", {
        "phc_code": "text", "product_name": "text", "output_weight_kg": "num",
        "yield_norm_ratio": "num", "storage_type": "text", "packed_at": "ts",
        "expiry_date": "date", "status": "text",
    }),
    "packing_inputs": ("packing_inputs", {
        "allocated_weight_kg": "num", "linked_at": "ts",
    }),
    "packaging_units": ("packaging_units", {
        "level": "text", "gtin_code": "text", "sscc_code": "text",
        "package_spec": "text", "units_count": "int",
    }),
    "traceability_records": ("traceability_records", {
        "traceability_code": "text", "product_name": "text",
        "product_image_url": "text", "business_unit_name": "text",
        "business_unit_address": "text", "production_event_time": "ts",
        "brand_trademark_serial": "text", "expiration_date": "date",
        "data_carrier_type": "text", "data_retention_until": "date",
        "sync_status": "text", "synced_at": "ts",
    }),
    "cte_stages": ("cte_stages", {
        "traceability_code": "text", "stage_no": "int", "stage_name": "text",
        "product_trace_code": "text", "location_trace_code": "text",
        "batch_lot_number": "text", "event_time": "ts", "scheme_code": "text",
    }),
}
REF_ID_COLUMN = {
    "zone_code": "zone_id", "owner_actor_code": "owner_actor_id", "plant_code": "plant_id", "plan_code": "plan_id",
    "parcel_code": "parcel_id", "farmer_code": "farmer_id",
    "input_lot_code": "input_lot_id", "supplier_code": "supplier_id",
    "operator_code": "operator_id", "parent_code": "parent_id",
    "facility_code": "facility_id", "packing_lot_code": "packing_lot_id",
    "harvest_lot_code": "harvest_lot_id",
    "packaging_unit_code": "packaging_unit_id",
}


def conv(value, kind: str):
    """Normalize a database value into the API record shape."""
    if value is None:
        return None
    if kind == "num" and isinstance(value, Decimal):
        return float(value)
    if kind in ("date", "ts") and isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
