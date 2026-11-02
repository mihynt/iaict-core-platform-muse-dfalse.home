# Requirements baseline — public-safe summary

This repository is developed against a controlled requirements baseline held
by the project Owner. The full documents are internal and are **not** published
here; this page records only the metadata needed to verify what the code is
built against.

| Item | Value |
|---|---|
| Requirements document | SRS — Software Requirements Specification, IAICT Core Platform |
| Document ID | `IAICT/SRS-CORE/2026/V2.0` |
| Version / date | 2.0 — 2026-11-02 |
| SRS SHA-256 | `3a5d21e1bf34650dd3fdb4af844eccc34823cbaa7a48bc4d2fd0beec66866fe1` |
| Source specification | SOW v2.2.0-R21 (2026-10-31), SHA-256 `3a05a6d7fd03062fad550cccc8557355140cbad46d4842f6c647900eac909ba6` |

## Scope in numbers (from the baseline)

- 302 functional requirements in 22 groups (platform core, tenancy, production
  objects, field operations, lots & traceability, IoT, mobile, reporting,
  integrations, compliance, commercial operations)
- 56 non-functional requirements, 31 security controls, 11 hardware baselines
- 12 compliance rules (Rule Pack CMP-01..12) for the first vertical pack
- 115 acceptance scenarios (UAT-01..115), 64 deliverables (D-01..D-64),
  82 minimum reports
- Milestones M0–M7 over 240 days; hard day-90 gate (M3a) for the field-device
  baseline; pilot go-live at M5; commercial readiness at M7

## Change control

Requirement changes are appended to `pcs/SRS_CHANGES.md` as deltas against the
baseline above. The baseline document itself is never edited in place; a new
baseline version supersedes it and is recorded in `pcs/STATE.json`.
