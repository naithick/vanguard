"""
GreenRoute Mesh v2 — CPCB Station Data Loader

Loads real CPCB (Central Pollution Control Board) station data from Chennai
weather station Excel files into Supabase.

Data sources: 4 CPCB monitoring stations in Chennai
  - site_288  → Velachery Res. Area, Chennai - CPCB
  - site_5092 → Manali Village, Chennai - TNPCB
  - site_5361 → Arumbakkam, Chennai - TNPCB
  - site_5363 → Perungudi, Chennai - TNPCB

Also supports the Alandur Bus Depot 15-minute CSV.

NOTE: CPCB data has ALREADY-CALIBRATED pollutant values (PM2.5 in µg/m³,
CO in mg/m³, etc.) — no raw-sensor calibration needed. We insert directly
into processed_data, bypassing the raw_telemetry → processor pipeline
since these are government-grade instruments, not raw ESP32 ADC values.

Usage:
    python load_cpcb.py                    # load all 4 stations + Alandur CSV
    python load_cpcb.py --station 288      # load only one station
    python load_cpcb.py --dry-run          # parse only, no DB writes
    python load_cpcb.py --force            # wipe existing station data first
    python load_cpcb.py --limit 500        # limit per station
"""

import os
import sys
import math
import argparse
import logging
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase_client import db
from config import processing_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-22s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("greenroute.cpcb_loader")

# ── Station metadata ─────────────────────────────────────────────────────────
STATIONS = {
    "288": {
        "file": "site_28820260218031028.xlsx",
        "name": "Velachery Res. Area, Chennai - CPCB",
        "device_id": "cpcb-velachery-288",
        "lat": 12.9815,
        "lon": 80.2180,
    },
    "5092": {
        "file": "site_509220260218030137.xlsx",
        "name": "Manali Village, Chennai - TNPCB",
        "device_id": "cpcb-manali-5092",
        "lat": 13.1662,
        "lon": 80.2585,
    },
    "5361": {
        "file": "site_536120260218030742.xlsx",
        "name": "Arumbakkam, Chennai - TNPCB",
        "device_id": "cpcb-arumbakkam-5361",
        "lat": 13.0694,
        "lon": 80.2121,
    },
    "5363": {
        "file": "site_536320260218031442.xlsx",
        "name": "Perungudi, Chennai - TNPCB",
        "device_id": "cpcb-perungudi-5363",
        "lat": 12.9611,
        "lon": 80.2420,
    },
}

ALANDUR_CSV = "Raw_data_15Min_2025_site_293_Alandur_Bus_Depot_Chennai_CPCB_15Min (2).csv"
ALANDUR_META = {
    "device_id": "cpcb-alandur-293",
    "name": "Alandur Bus Depot, Chennai - CPCB",
    "lat": 13.0067,
    "lon": 80.2006,
}

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


# ── AQI calculation (reuse from processor logic) ─────────────────────────────
def _linear_aqi(conc: float, bp_table: list) -> int:
    for c_lo, c_hi, i_lo, i_hi in bp_table:
        if c_lo <= conc <= c_hi:
            return round(((i_hi - i_lo) / (c_hi - c_lo)) * (conc - c_lo) + i_lo)
    return 500


def calculate_aqi(pm25: float, co_ppm: float):
    pm25_aqi = _linear_aqi(pm25 or 0, processing_config.pm25_breakpoints)
    co_aqi = _linear_aqi(co_ppm or 0, processing_config.co_breakpoints)
    aqi = max(pm25_aqi, co_aqi)
    if aqi <= 50:    cat = "Good"
    elif aqi <= 100: cat = "Moderate"
    elif aqi <= 150: cat = "Unhealthy for Sensitive Groups"
    elif aqi <= 200: cat = "Unhealthy"
    elif aqi <= 300: cat = "Very Unhealthy"
    else:            cat = "Hazardous"
    return aqi, cat


def heat_index(temp_c, rh):
    if temp_c is None or rh is None:
        return None
    if temp_c < 27 or rh < 40:
        return temp_c
    t = temp_c * 9 / 5 + 32
    hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh
          - 0.22475541 * t * rh - 0.00683783 * t * t
          - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
          + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
    return round((hi - 32) * 5 / 9, 1)


def toxic_gas_index(co_ppm, co2_ppm):
    co_s = min((co_ppm or 0) / 50 * 100, 100) * 0.6
    co2_s = min((co2_ppm or 400) / 2000 * 100, 100) * 0.4
    return round(min(co_s + co2_s, 100), 1)


def respiratory_risk(pm25):
    if pm25 is None or pm25 <= 12.0:
        return "Low"
    if pm25 <= 35.4:
        return "Moderate"
    if pm25 <= 55.4:
        return "High"
    if pm25 <= 150.4:
        return "Very High"
    return "Severe"


def safe_float(val):
    """Convert value to float, return None if not possible."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return None
    try:
        v = float(val)
        return v if not math.isnan(v) and not math.isinf(v) else None
    except (ValueError, TypeError):
        return None


def reverse_mq7(co_ppm: float) -> float:
    """Reverse the MQ7 calibration: CO ppm → raw ADC value.
    Forward: co = 99.042 * (raw/590)^-1.518
    Reverse: raw = 590 * (co_ppm / 99.042) ^ (-1/1.518)
    """
    if co_ppm is None or co_ppm <= 0:
        return 0.0
    rs_r0 = (co_ppm / 99.042) ** (-1.0 / 1.518)
    raw = 590 * rs_r0
    return min(raw, 4095)  # cap at ESP32 12-bit ADC max


# ── Parse CPCB XLSX ──────────────────────────────────────────────────────────
def parse_cpcb_xlsx(filepath: str) -> pd.DataFrame:
    """
    Parse a CPCB Excel file. Header is at row index 16, data starts at 17.
    Returns a clean DataFrame with standardized column names.
    """
    df = pd.read_excel(filepath, header=None)

    # Extract station info
    station_name = str(df.iloc[6, 1]) if len(df) > 6 else "Unknown"

    # Row 16 = actual column headers, data starts row 17
    headers = df.iloc[16].tolist()
    data = df.iloc[17:].copy()
    data.columns = headers

    # Remove rows where From Date is NaN
    data = data.dropna(subset=["From Date"])

    # Standardize column names
    col_map = {}
    for c in data.columns:
        cl = str(c).strip()
        col_map[c] = cl

    data = data.rename(columns=col_map)

    log.info(f"Parsed {filepath}: {len(data)} rows, station='{station_name}'")
    return data


# ── Parse Alandur 15-min CSV ─────────────────────────────────────────────────
def parse_alandur_csv(filepath: str) -> pd.DataFrame:
    """Parse the Alandur Bus Depot 15-minute interval CSV."""
    df = pd.read_csv(filepath)
    log.info(f"Parsed Alandur CSV: {len(df)} rows")
    return df


# ── Insert CPCB station data ─────────────────────────────────────────────────
def load_station(station_id: str, dry_run: bool = False, limit: int = 0, force: bool = False) -> int:
    """Load one CPCB XLSX station into Supabase. Returns rows loaded."""
    meta = STATIONS[station_id]
    filepath = os.path.join(DATA_DIR, meta["file"])

    if not os.path.exists(filepath):
        log.error(f"File not found: {filepath}")
        return 0

    device_id = meta["device_id"]

    if force and not dry_run:
        log.warning(f"Force: deleting existing data for {device_id}")
        db.client.table("processed_data").delete().eq("device_id", device_id).execute()
        db.client.table("raw_telemetry").delete().eq("device_id", device_id).execute()

    # Register device
    if not dry_run:
        db.get_or_create_device(device_id, name=meta["name"])
        # Update static coordinates
        db.client.table("devices").update({
            "static_latitude": meta["lat"],
            "static_longitude": meta["lon"],
            "name": meta["name"],
        }).eq("device_id", device_id).execute()

    df = parse_cpcb_xlsx(filepath)

    if limit > 0:
        df = df.head(limit)

    loaded = 0
    skipped = 0
    batch_raw = []
    BATCH_SIZE = 500

    for _, row in df.iterrows():
        try:
            # Parse timestamp
            from_date = str(row.get("From Date", "")).strip()
            if not from_date or from_date == "nan":
                skipped += 1
                continue

            # Parse date: "17-02-2025 00:00" format
            try:
                ts = datetime.strptime(from_date, "%d-%m-%Y %H:%M")
                ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                try:
                    ts = datetime.strptime(from_date, "%d-%m-%Y %H:%M:%S")
                    ts = ts.replace(tzinfo=timezone.utc)
                except ValueError:
                    skipped += 1
                    continue

            # Extract pollutant values (already calibrated by CPCB instruments)
            pm25 = safe_float(row.get("PM2.5"))
            co_mgm3 = safe_float(row.get("CO"))
            co_ppm = round(co_mgm3 * 0.873, 2) if co_mgm3 is not None else None
            temp = safe_float(row.get("Temp"))
            rh = safe_float(row.get("RH"))
            bp = safe_float(row.get("BP"))
            pressure_hpa = round(bp * 1.33322, 1) if bp is not None else None

            # We need at LEAST PM2.5 to compute AQI
            if pm25 is None:
                skipped += 1
                continue

            # Map CPCB calibrated values to raw_telemetry fields:
            # Reverse the calibration so processor yields correct values
            raw_dust = pm25 / 1.5   # processor does raw * 1.5 = pm25
            raw_mq7 = reverse_mq7(co_ppm) if co_ppm is not None else 0
            raw_mq135 = 900  # neutral value → ~400 ppm CO₂

            raw_row = {
                "device_id": device_id,
                "raw_dust": round(raw_dust, 2),
                "raw_mq135": round(raw_mq135, 2),
                "raw_mq7": round(raw_mq7, 2),
                "temperature_c": temp,
                "humidity_pct": rh,
                "pressure_hpa": pressure_hpa,
                "gas_resistance": 50000,  # neutral gas resistance
                "raw_latitude": meta["lat"],
                "raw_longitude": meta["lon"],
                "processed": False,
                "received_at": ts.isoformat(),
                "recorded_at": ts.isoformat(),
            }

            if dry_run:
                if loaded < 3:
                    aqi_val, aqi_cat = calculate_aqi(pm25, co_ppm or 0)
                    log.info(f"[DRY-RUN] {ts.isoformat()} PM2.5={pm25} AQI={aqi_val} ({aqi_cat})")
                loaded += 1
                continue

            batch_raw.append(raw_row)
            loaded += 1

            # Flush batch
            if len(batch_raw) >= BATCH_SIZE:
                db.client.table("raw_telemetry").insert(
                    batch_raw, returning="minimal", default_to_null=True
                ).execute()
                log.info(f"  {meta['name']}: {loaded} rows inserted into raw_telemetry...")
                batch_raw = []

        except Exception as e:
            log.warning(f"  Row error: {e}")
            skipped += 1
            continue

    # Flush remaining
    if batch_raw and not dry_run:
        db.client.table("raw_telemetry").insert(
            batch_raw, returning="minimal", default_to_null=True
        ).execute()

    log.info(f"Station {meta['name']}: raw_telemetry loaded={loaded}, skipped={skipped}")
    return loaded


# ── Insert Alandur 15-min CSV (aggregated to 8-hour windows) ──────────────────
def load_alandur(dry_run: bool = False, limit: int = 0, force: bool = False) -> int:
    """Load the Alandur Bus Depot CSV, aggregated to 8-hour windows, into Supabase."""
    filepath = os.path.join(DATA_DIR, ALANDUR_CSV)

    if not os.path.exists(filepath):
        log.warning(f"Alandur CSV not found: {filepath}")
        return 0

    device_id = ALANDUR_META["device_id"]

    if force and not dry_run:
        log.warning(f"Force: deleting existing data for {device_id}")
        db.client.table("processed_data").delete().eq("device_id", device_id).execute()
        db.client.table("raw_telemetry").delete().eq("device_id", device_id).execute()

    if not dry_run:
        db.get_or_create_device(device_id, name=ALANDUR_META["name"])
        db.client.table("devices").update({
            "static_latitude": ALANDUR_META["lat"],
            "static_longitude": ALANDUR_META["lon"],
            "name": ALANDUR_META["name"],
        }).eq("device_id", device_id).execute()

    df = parse_alandur_csv(filepath)

    # Parse timestamps and aggregate to 8-hour windows
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    df = df.dropna(subset=["Timestamp"])

    # Create 8-hour bins: 00:00, 08:00, 16:00
    df["window"] = df["Timestamp"].dt.floor("8h")

    # Aggregate: mean of each window
    agg_cols = {
        "PM2.5 (µg/m³)": "mean",
        "PM10 (µg/m³)": "mean",
        "SO2 (µg/m³)": "mean",
        "CO (mg/m³)": "mean",
        "Ozone (µg/m³)": "mean",
        "AT (°C)": "mean",
        "RH (%)": "mean",
        "WS (m/s)": "mean",
        "WD (deg)": "mean",
        "BP (mmHg)": "mean",
    }
    # Only aggregate columns that exist
    agg_cols = {k: v for k, v in agg_cols.items() if k in df.columns}
    agg = df.groupby("window").agg(agg_cols).reset_index()

    log.info(f"Alandur: {len(df)} raw rows → {len(agg)} 8-hour windows")

    if limit > 0:
        agg = agg.head(limit)

    loaded = 0
    skipped = 0
    batch_raw = []
    BATCH_SIZE = 500

    for _, row in agg.iterrows():
        try:
            ts = row["window"].to_pydatetime().replace(tzinfo=timezone.utc)

            pm25 = safe_float(row.get("PM2.5 (µg/m³)"))
            co_mgm3 = safe_float(row.get("CO (mg/m³)"))
            co_ppm = round(co_mgm3 * 0.873, 2) if co_mgm3 is not None else None
            temp = safe_float(row.get("AT (°C)"))
            rh = safe_float(row.get("RH (%)"))
            bp = safe_float(row.get("BP (mmHg)"))
            pressure_hpa = round(bp * 1.33322, 1) if bp is not None else None

            if pm25 is None:
                skipped += 1
                continue

            # Reverse-map calibrated values to raw sensor equivalents
            raw_dust = pm25 / 1.5
            raw_mq7 = reverse_mq7(co_ppm) if co_ppm is not None else 0
            raw_mq135 = 900

            raw_row = {
                "device_id": device_id,
                "raw_dust": round(raw_dust, 2),
                "raw_mq135": round(raw_mq135, 2),
                "raw_mq7": round(raw_mq7, 2),
                "temperature_c": round(temp, 1) if temp is not None else None,
                "humidity_pct": round(rh, 1) if rh is not None else None,
                "pressure_hpa": pressure_hpa,
                "gas_resistance": 50000,
                "raw_latitude": ALANDUR_META["lat"],
                "raw_longitude": ALANDUR_META["lon"],
                "processed": False,
                "received_at": ts.isoformat(),
                "recorded_at": ts.isoformat(),
            }

            if dry_run:
                if loaded < 3:
                    aqi_val, aqi_cat = calculate_aqi(pm25, co_ppm or 0)
                    log.info(f"[DRY-RUN] {ts.isoformat()} PM2.5={round(pm25,2)} AQI={aqi_val} ({aqi_cat})")
                loaded += 1
                continue

            batch_raw.append(raw_row)
            loaded += 1

            if len(batch_raw) >= BATCH_SIZE:
                db.client.table("raw_telemetry").insert(
                    batch_raw, returning="minimal", default_to_null=True
                ).execute()
                log.info(f"  Alandur: {loaded} rows inserted into raw_telemetry...")
                batch_raw = []

        except Exception as e:
            log.warning(f"  Row error: {e}")
            skipped += 1
            continue

    if batch_raw and not dry_run:
        db.client.table("raw_telemetry").insert(
            batch_raw, returning="minimal", default_to_null=True
        ).execute()

    log.info(f"Alandur Bus Depot (8hr avg): raw_telemetry loaded={loaded}, skipped={skipped}")
    return loaded


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Load CPCB Chennai station data into Supabase")
    parser.add_argument("--station", type=str, default=None,
                        help="Load only one station (288, 5092, 5361, 5363, alandur)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse only, no DB writes")
    parser.add_argument("--force", action="store_true",
                        help="Delete existing station data before loading")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max rows to load per station (0 = all)")
    parser.add_argument("--no-alandur", action="store_true",
                        help="Skip the Alandur 15-min CSV")
    args = parser.parse_args()

    total = 0

    if args.station:
        if args.station.lower() == "alandur":
            total += load_alandur(dry_run=args.dry_run, limit=args.limit, force=args.force)
        elif args.station in STATIONS:
            total += load_station(args.station, dry_run=args.dry_run, limit=args.limit, force=args.force)
        else:
            log.error(f"Unknown station: {args.station}. Options: {list(STATIONS.keys()) + ['alandur']}")
            sys.exit(1)
    else:
        # Load all 4 CPCB XLSX stations
        for sid in STATIONS:
            total += load_station(sid, dry_run=args.dry_run, limit=args.limit, force=args.force)

        # Load Alandur CSV (35k rows)
        if not args.no_alandur:
            total += load_alandur(dry_run=args.dry_run, limit=args.limit, force=args.force)

    log.info(f"\n{'='*60}")
    log.info(f"TOTAL ROWS LOADED: {total}")
    log.info(f"{'='*60}")

    if args.dry_run:
        log.info("(Dry run — no data was written to the database)")


if __name__ == "__main__":
    main()
