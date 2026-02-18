"""
GreenRoute Mesh v2 — CSV Loader  (one-shot, safe to re-run)

Loads sensor CSV data into raw_telemetry.
Auto-detects two CSV formats:
  A) Old: Millis,Dust,MQ135,MQ7,Temperature,Humidity,Pressure,Gas,Latitude,Longitude
  B) New: timestamp,temperature,humidity,pressure,gas,dust,latitude,longitude

Skips loading if data already exists for the test device unless --force is passed.

Usage:
    python load_csv.py                          # loads new CSV (all rows)
    python load_csv.py --csv path/to/file.csv   # specify CSV path
    python load_csv.py --force                   # wipe test-device rows, then reload
    python load_csv.py --limit 100               # load only 100 rows
    python load_csv.py --dry-run                 # parse only, no DB writes
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
# Default to new CSV with real GPS coordinates
CSV_NEW = os.path.join(os.path.dirname(__file__), "..", "Sample_Data_with_location .csv")
CSV_OLD = os.path.join(os.path.dirname(__file__), "..", "ESP32_Air_Quality_Data.csv")
CSV_PATH = CSV_NEW if os.path.exists(CSV_NEW) else CSV_OLD

TEST_DEVICE_ID = "esp32-csv-test"


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


def load_csv(csv_path: str, dry_run: bool = False, limit: int = 0) -> int:
    """
    Read the CSV and insert each row into raw_telemetry.
    Auto-detects old (MQ135/MQ7) vs new (timestamp/gas/dust) format.
    limit=0 means load all rows.
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

    # Try utf-8 first, fall back to latin-1 (old CSV has degree symbol)
    for enc in ("utf-8", "latin-1"):
        try:
            with open(csv_path, newline="", encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            break
        except UnicodeDecodeError:
            continue

    total = len(rows)
    if limit > 0:
        rows = rows[:limit]
    log.info(f"CSV has {total} rows total, loading {len(rows)}")

    if not rows:
        return 0

    # ── Auto-detect format ────────────────────────────────────────────────
    cols = set(c.lower().strip() for c in rows[0].keys())
    has_timestamp = "timestamp" in cols
    has_mq = "mq135" in cols
    has_uppercase_dust = "Dust" in rows[0].keys()

    if has_timestamp and has_mq:
        fmt = "full"  # Full format: timestamp,temperature,humidity,pressure,gas,dust,mq135,mq7,latitude,longitude
        log.info("Detected FULL CSV format (timestamp + MQ135/MQ7 + GPS)")
    elif has_timestamp and not has_mq:
        fmt = "new"   # New format: no MQ columns
        log.info("Detected NEW CSV format (timestamp, real GPS coordinates)")
    else:
        fmt = "old"   # Old format: Millis, uppercase columns
        log.info("Detected OLD CSV format (Millis, MQ135, MQ7)")

    # For old format: find columns with encoding-mangled names
    if fmt == "old":
        all_cols = rows[0].keys()
        def _find(prefix):
            for c in all_cols:
                if c.startswith(prefix):
                    return c
            return prefix
        temp_col = _find("Temperature")
        hum_col  = _find("Humidity")
        pres_col = _find("Pressure")
        gas_col  = _find("Gas")

    for i, row in enumerate(rows):
        try:
            if fmt == "full":
                # Full format: all lowercase columns including mq135/mq7
                payload = {
                    "dust":        float(row.get("dust", 0) or 0),
                    "mq135":       float(row.get("mq135", 0) or 0),
                    "mq7":         float(row.get("mq7", 0) or 0),
                    "temperature": float(row.get("temperature", 0) or 0),
                    "humidity":    float(row.get("humidity", 0) or 0),
                    "pressure":    float(row.get("pressure", 0) or 0),
                    "gas":         float(row.get("gas", 0) or 0) * 1000,  # kΩ → Ω
                    "latitude":    float(row.get("latitude", 0) or 0),
                    "longitude":   float(row.get("longitude", 0) or 0),
                }
                ts_str = row.get("timestamp", "").strip()
            elif fmt == "new":
                # New format: timestamp,temperature,humidity,pressure,gas,dust,latitude,longitude
                # gas is in kΩ, no MQ135/MQ7 columns
                payload = {
                    "dust":        float(row.get("dust", 0) or 0),
                    "mq135":       0.0,  # not available in new format
                    "mq7":         0.0,  # not available in new format
                    "temperature": float(row.get("temperature", 0) or 0),
                    "humidity":    float(row.get("humidity", 0) or 0),
                    "pressure":    float(row.get("pressure", 0) or 0),
                    "gas":         float(row.get("gas", 0) or 0) * 1000,  # kΩ → Ω
                    "latitude":    float(row.get("latitude", 0) or 0),
                    "longitude":   float(row.get("longitude", 0) or 0),
                }
                ts_str = row.get("timestamp", "").strip()
            else:
                # Old format: Millis,Dust,MQ135,MQ7,Temperature,Humidity,Pressure,Gas,Lat,Lon
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
                ts_str = ""

            if dry_run:
                if i < 3:
                    log.info(f"  [dry-run] row {i}: {payload}")
                continue

            # Determine timestamp
            if ts_str:
                try:
                    # Try multiple timestamp formats
                    for fmt_str in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
                        try:
                            dt = datetime.strptime(ts_str, fmt_str)
                            break
                        except ValueError:
                            continue
                    else:
                        raise ValueError(f"Unknown timestamp format: {ts_str}")
                    fake_time = dt.replace(tzinfo=timezone.utc).isoformat()
                except ValueError:
                    fake_time = (base_time + timedelta(seconds=i * 5)).isoformat()
            else:
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

            if loaded % 25 == 0:
                log.info(f"  loaded {loaded}/{len(rows)} ...")

        except Exception as exc:
            log.error(f"Row {i} failed: {exc}")

    return loaded


def main():
    parser = argparse.ArgumentParser(description="Load ESP32 CSV into Supabase")
    parser.add_argument("--csv", type=str, default=None,
                        help="Path to CSV file (auto-detects format)")
    parser.add_argument("--force", action="store_true",
                        help="Delete existing test-device data before loading")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse CSV but don't write to DB")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max rows to load (0 = all)")
    args = parser.parse_args()

    csv_path = args.csv or CSV_PATH

    # Safety check: don't re-insert if data already exists
    existing = count_existing_rows(TEST_DEVICE_ID)

    if existing > 0 and not args.force and not args.dry_run:
        log.info(f"Found {existing} existing rows for {TEST_DEVICE_ID}. "
                 f"Skipping load. Use --force to reload.")
        return

    if args.force and existing > 0:
        delete_device_data(TEST_DEVICE_ID)

    log.info(f"Loading CSV: {csv_path}")
    n = load_csv(csv_path, dry_run=args.dry_run, limit=args.limit)

    if args.dry_run:
        log.info(f"Dry run complete — {n} rows would be loaded")
    else:
        log.info(f"Loaded {n} rows into raw_telemetry for {TEST_DEVICE_ID}")
        log.info("Start the server (python app.py) and the background worker "
                 "will process them within 15 seconds.")


if __name__ == "__main__":
    main()
