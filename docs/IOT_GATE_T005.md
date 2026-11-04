# T-005 — IoT Gate Package (M3a, day-90 go/no-go)

Prepared by T-045 as the final stage of the FULL programme (Owner
directive 2026-11-04, "Làm full tất cả"). This package gives the Owner
everything needed for the M3a go/no-go decision on the IoT workstream
without pre-empting it: the platform side is proven end-to-end with
simulated devices; the three decisions that are genuinely the Owner's
are listed at the end, still open.

## What the gate is deciding

Whether to connect real field devices (water-quality sensors, AI
insect traps, weather stations) to the platform for the pilot tenant,
on the M3a timeline (day 90 of the SRS baseline schedule), given that
the implementation plan assigns the core team **0 IoT FTE** (measured
in the 2026-11-02 three-document review of KH v3.1).

## What is proven (simulation slice, live on the beta)

- **Device registry** (`iot_devices`): coded devices with type
  (water sensor / AI trap / weather station), installation zone and
  parcel, firmware version. Managed in the "Giám sát & kê khai" UI.
- **Ingestion endpoint** (`POST /api/v1/iot/readings`): authenticated
  by the calling device's OWN key (`X-Iot-Key` header). Per-device
  keys were added by T-046 on the Owner's direction: each device
  receives a random key at registration (and on rotation), the
  platform stores only an HMAC hash, and the raw key is shown exactly
  once. A device with no active key is refused (403
  DEVICE_KEY_INACTIVE), a wrong key is refused (401), unknown devices
  are rejected (404 DEVICE_UNKNOWN), empty readings are rejected
  (400 READING_EMPTY); every accepted reading writes an `IOT_READING`
  audit row under actor `iot:<device_code>`. The T-045 tenant-wide
  shared key was retired — one compromised device no longer opens the
  whole tenant gate.
- **Landing zones are the dossier's own tables** — no parallel IoT
  schema: water metrics become Bảng 20 water-quality records on the
  device's parcel; trap counts become Bảng 19 monitoring records of
  type `AI_INSECT_TRAP_REALTIME` on the device's zone. From there the
  readings flow through the existing reports and PHI machinery.
- **Simulator** (`tools/simulate_iot.py`): sends plausible telemetry
  exactly as a field gateway would, so the whole chain can be
  exercised before any hardware exists.

## What real devices would still need (not built, by design)

1. ~~**Per-device credentials.**~~ **Done (T-046):** per-device keys
   with admin-driven rotation and revocation, hash-only storage,
   one-time display. (mTLS remains a future option if a vendor
   requires it.)
2. **A transport decision.** Devices/gateways would post HTTPS
   directly (simplest, matches the slice), or via an MQTT broker /
   vendor cloud webhook (most sensor vendors push from their own
   cloud). The endpoint shape supports either; the choice follows the
   hardware vendor, which is not selected yet.
3. **Offline buffering & clock discipline** on the gateway side, plus
   reading-rate limits once real fleets exist.
4. **Alerting rules** on top of the landed data (e.g. salinity > 1.0‰
   warning already implied by Bảng 20) — a rules task, not ingestion.

## Decisions for the Owner (open)

1. **Simulation-first or wait for hardware?** The slice proves the
   platform side now. Going further (per-device credentials, vendor
   integration) only pays off once a hardware vendor and device list
   exist.
2. **Who owns IoT?** KH v3.1 assigns the core team 0 IoT FTE. Options:
   an external device vendor delivers integrated gateways; a partner
   team owns devices while this platform owns ingestion (the slice's
   assumption); or the plan is amended to staff it.
3. **Timeline anchor.** Gate by the relative milestone (M0+90 days per
   the SRS baseline) or only after INT-02 locks the master schedule?
   The SOW/SRS/KH timeline mismatch (+4/+9/+40 days between document
   sets) is still unresolved at IAICT level.

Until these are decided, the gate stays closed in production in
practice: no production device has been issued a key yet, and devices
without an active key are refused.
