"""
GreenRoute Mesh v2 — CSV Loader  (one-shot, safe to re-run)

Loads ESP32_Air_Quality_Data.csv into raw_telemetry using the /api/ingest
endpoint format.  Skips loading if data already exists for the test device
unless --force is passed.

Usage:
    python load_csv.py                  # loads only if raw_telemetry is empty
    python load_csv.py --force          # wipe test-device rows, then reload
    python load_csv.py --dry-run        # just print what would happen
"""

import csv
import sys
import os
import argparse
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_client import db
from processor import processor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-22s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("greenroute.csv_loader")

# ── Config ────────────────────────────────────────────────────────────────────
CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "ESP32_Air_Quality_Data.csv")
TEST_DEVICE_ID = "esp32-csv-test"
# Bangalore centre — used as static location for the test device
DEFAULT_LAT = 12.9716
DEFAULT_LON = 77.5946


def count_existing_rows(device_id: str) -> int:
    """How many raw_telemetry rows already exist for this device?"""
    res = (
        db.client.table("raw_telemetry")
        .select("id", count="exact")
        .eq("device_id", device_id)
        .execute()
    )
    return res.count or 0


def delete_device_data(device_id: str):
    """Remove all raw_telemetry + processed_data for a device (for --force)."""
    log.warning(f"Deleting all data for device {device_id} ...")
    # processed_data first (FK on raw_telemetry_id)
    db.client.table("processed_data").delete().eq("device_id", device_id).execute()
    db.client.table("raw_telemetry").delete().eq("device_id", device_id).execute()
    log.info("Deleted existing rows.")


def load_csv(csv_path: str, dry_run: bool = False, limit: int = 250) -> int:
    """
    Read the CSV and insert each row into raw_telemetry via the DB client.
    Returns the number of rows loaded.
    """
    if not os.path.exists(csv_path):
        log.error(f"CSV not found: {csv_path}")
        return 0

    # Ensure test device exists
    if not dry_run:
        db.get_or_create_device(TEST_DEVICE_ID, name="CSV Test Node")

    loaded = 0
    base_time = datetime.now(timezone.utc) - timedelta(hours=2)

    with open(csv_path, newline="", encoding="latin-1") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    log.info(f"CSV has {len(rows)} rows total, loading first {limit}")
    rows = rows[:limit]

    # Column names may have encoding-mangled chars — find them by prefix
    cols = rows[0].keys() if rows else []
    def _find(prefix):
        for c in cols:
            if c.startswith(prefix):
                return c
        return prefix

    temp_col = _find("Temperature")
    hum_col  = _find("Humidity")
    pres_col = _find("Pressure")
    gas_col  = _find("Gas")

    for i, row in enumerate(rows):
        try:
            # Build the payload matching what ESP32 would send
            payload = {
                "dust":        float(row.get("Dust", 0) or 0),
                "mq135":       float(row.get("MQ135", 0) or 0),
                "mq7":         float(row.get("MQ7", 0) or 0),
                "temperature": float(row.get(temp_col, 0) or 0),
                "humidity":    float(row.get(hum_col, 0) or 0),
                "pressure":    float(row.get(pres_col, 0) or 0),
                "gas":         float(row.get(gas_col, 0) or 0) * 1000,  # kΩ → Ω
                "latitude":    float(row.get("Latitude", 0) or 0),
                "longitude":   float(row.get("Longitude", 0) or 0),
            }

            if dry_run:
                if i < 3:
                    log.info(f"  [dry-run] row {i}: {payload}")
                continue

            # Spread readings across the last 2 hours (5 s apart)
            fake_time = (base_time + timedelta(seconds=i * 5)).isoformat()

            # Insert raw telemetry directly
            db_row = {
                "device_id":     TEST_DEVICE_ID,
                "raw_dust":      payload["dust"],
                "raw_mq135":     payload["mq135"],
                "raw_mq7":       payload["mq7"],
                "temperature_c": payload["temperature"],
                "humidity_pct":  payload["humidity"],
                "pressure_hpa":  payload["pressure"],
                "gas_resistance": payload["gas"],
                "raw_latitude":  payload["latitude"],
                "raw_longitude": payload["longitude"],
                "processed":     False,
                "received_at":   fake_time,
                "recorded_at":   fake_time,
            }

            db.client.table("raw_telemetry").insert(db_row).execute()
            loaded += 1

            if loaded % 100 == 0:
                log.info(f"  loaded {loaded}/{len(rows)} ...")

        except Exception as exc:
            log.error(f"Row {i} failed: {exc}")

    return loaded


def main():
    parser = argparse.ArgumentParser(description="Load ESP32 CSV into Supabase")
    parser.add_argument("--force", action="store_true",
                        help="Delete existing test-device data before loading")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse CSV but don't write to DB")
    parser.add_argument("--limit", type=int, default=250,
                        help="Max rows to load (default 250)")
    args = parser.parse_args()

    # Safety check: don't re-insert if data already exists
    existing = count_existing_rows(TEST_DEVICE_ID)

    if existing > 0 and not args.force and not args.dry_run:
        log.info(f"Found {existing} existing rows for {TEST_DEVICE_ID}. "
                 f"Skipping load. Use --force to reload.")
        return

    if args.force and existing > 0:
        delete_device_data(TEST_DEVICE_ID)

    log.info(f"Loading CSV: {CSV_PATH}")
    n = load_csv(CSV_PATH, dry_run=args.dry_run, limit=args.limit)

    if args.dry_run:
        log.info(f"Dry run complete — {n} rows would be loaded")
    else:
        log.info(f"Loaded {n} rows into raw_telemetry for {TEST_DEVICE_ID}")
        log.info("Start the server (python app.py) and the background worker "
                 "will process them within 25 seconds.")


if __name__ == "__main__":
    main()
