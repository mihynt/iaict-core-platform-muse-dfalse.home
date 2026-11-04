#!/usr/bin/env python3
"""IoT ingestion simulator for the T-005 gate slice (T-045).

Sends plausible telemetry for a registered device to the platform's
ingestion endpoint, the way a field gateway would. Usage:

    IAICT_DEVICE_KEY=<the device key shown once at issue time> \
    python tools/simulate_iot.py \
        --base https://iaict-core-platform.mihy.workers.dev \
        --tenant beta-pilot --device WQ-01 --count 3

Each device has its own key (T-046), shown exactly once when the
device is created or its key is rotated in the admin UI; the platform
stores only a hash. A device without an active key is refused (403).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import urllib.request
from datetime import datetime, timezone


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--tenant", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--count", type=int, default=1)
    args = ap.parse_args()
    key = os.environ.get("IAICT_DEVICE_KEY")
    if not key:
        raise SystemExit("IAICT_DEVICE_KEY is not set in the environment")
    url = args.base.rstrip("/") + "/api/v1/iot/readings"
    for i in range(args.count):
        reading = {
            "device_code": args.device,
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "water": {
                "ph_value": round(random.uniform(6.5, 8.0), 2),
                "water_temp_celsius": round(random.uniform(24, 31), 1),
                "dissolved_oxygen_mg_l": round(random.uniform(4.5, 7.5), 2),
                "water_salinity_permille": round(random.uniform(0.2, 0.9), 2),
            },
            "trap": {
                "pest_species_detected": "Sau cuon la (Spodoptera litura)",
                "pest_density_index": f"{random.randint(0, 12)} con/bay",
            },
        }
        req = urllib.request.Request(
            url, method="POST",
            headers={"Content-Type": "application/json",
                     "X-Tenant-Id": args.tenant, "X-Iot-Key": key,
                     "User-Agent": "iaict-iot-simulator/1.0"},
            data=json.dumps(reading).encode())
        with urllib.request.urlopen(req) as resp:
            print(resp.status, resp.read().decode())


if __name__ == "__main__":
    main()
