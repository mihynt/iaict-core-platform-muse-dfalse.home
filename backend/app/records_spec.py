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
    }),
    "mother_plants": ("mother_plants", {
        "species": "text", "variety": "text", "scientific_name": "text",
        "origin": "text", "planting_year": "int", "lat": "float", "lon": "float",
        "owner_manager": "text", "recognition_no": "text",
        "issuing_authority": "text", "valid_from": "date", "valid_to": "date",
        "status": "text",
    }),
    "crop_plans": ("crop_plans", {
        "name": "text", "crop_name": "text", "start_date": "date",
        "end_date": "date", "target_yield_kg": "num", "status": "text",
    }),
    "field_events": ("field_events", {
        "event_type": "text", "occurred_at": "ts", "lat": "float", "lon": "float",
        "actor": "text", "device": "text", "notes": "text", "materials": "json",
    }),
    "lots": ("lots", {
        "harvest_date": "date", "quantity": "num", "unit": "text",
        "harvested_by": "text", "quality_grade": "text", "status": "text",
        "expiry_date": "date",
    }),
}
REF_ID_COLUMN = {"zone_code": "zone_id", "plant_code": "plant_id", "plan_code": "plan_id"}


def conv(value, kind: str):
    """Normalize a database value into the API record shape."""
    if value is None:
        return None
    if kind == "num" and isinstance(value, Decimal):
        return float(value)
    if kind in ("date", "ts") and isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
