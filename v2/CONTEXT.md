# GreenRoute Mesh v2 — Project Context

> Last updated: 2026-02-17 · **v0.6**

## Overview

Clean rewrite of the GreenRoute Mesh backend. ESP32 nodes send raw air-quality
telemetry to a Flask API (exposed via ngrok), which stores it in Supabase.
A background worker processes the data every 15 seconds (5 ESP32 cycles).

**Current status:** Processing pipeline has calibration + derived metrics +
data validation (bounds checking, zero-value filtering, IQR outlier clipping).
Ported from v1's preprocessing module.

## Architecture

```
ESP32 node  ──(POST JSON every 3 s)──►  ngrok tunnel
                                             │
                                             ▼
                                      Flask /api/ingest (:5001)
                                             │
                                             ▼
                                      raw_telemetry (Supabase)
                                             │
                                    background worker (15 s / 5 cycles)
                                             │
                                             ▼
                                     processed_data (Supabase)
```

## Data Flow

1. **Ingestion** — ESP32 POSTs raw sensor JSON to `/api/ingest` every 3 seconds
   via ngrok tunnel. Device is auto-registered on first contact.
2. **Storage** — Raw payload written to `raw_telemetry` table immediately.
3. **Processing** — Background thread wakes every 15 s (= 5 ESP32 cycles),
   fetches all `processed=false` rows, runs calibration + derived metrics,
   writes enriched rows to `processed_data`, marks originals as processed.

## Supabase Tables Used

| Table | Purpose |
|---|---|
| `devices` | ESP32 node registry (auto-created on first ingest) |
| `raw_telemetry` | Verbatim sensor readings from ESP32 |
| `processed_data` | Calibrated + enriched readings (AQI, heat index, etc.) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/ingest` | ESP32 sends raw sensor JSON |
| POST | `/api/process` | Manually trigger processing |
| GET | `/api/readings` | Latest processed data |
| GET | `/api/zones` | Interpolated air-quality zones (GeoJSON) |
| GET | `/api/stats` | Summary counts |
| GET | `/api/health` | Health check |

## Files

```
v2/
├── app.py              # Flask server + background worker (15 s cycle)
├── config.py           # Supabase creds, calibration defaults, AQI breakpoints
├── processor.py        # Raw → processed conversion (AQI, heat index, etc.)
├── zones.py            # IDW interpolation → continuous air-quality zones (GeoJSON)
├── supabase_client.py  # Thin Supabase wrapper (devices, raw, processed)
├── load_csv.py         # One-shot CSV loader (safe to re-run, --force to reload)
├── start.py            # Launcher: Flask + ngrok in one command
├── requirements.txt    # Frozen pip dependencies
├── CONTEXT.md          # This file
├── esp32/
│   └── greenroute_node.ino   # ESP32 Arduino firmware
└── venv/               # Python virtual environment (gitignored)
```

## Processing Pipeline (per row)

0. **Data validation** — bounds check, zero-value filter, IQR outlier clipping
1. **Calibrate sensors** — dust→PM2.5, MQ135→CO₂, MQ7→CO
2. **GPS fallback** — if (0,0) use device's static location
3. **Derived metrics** — AQI (EPA), heat index, toxic gas index, respiratory risk
4. **Movement** — speed + distance from previous GPS fix

### Validation details

| Check | Action | Example |
|---|---|---|
| Null critical fields | DROP row | `raw_dust` is null |
| Sensor out of bounds | DROP row | `dust=0` (no-read), `dust=674` (>500) |
| IQR outlier (dust) | CLIP to fence | `dust=221` → clipped to ~61 |
| Temperature/humidity/pressure | Track only | Natural variation, not noise |

### v1 preprocessing features — ported to v2

| Feature | v1 module | v2 Status |
|---|---|---|
| Outlier removal (IQR, 1.5×) | `OutlierRemoval` | ✅ Ported (clip action on dust) |
| Sensor bounds checking | implicit in v1 | ✅ Ported (hard bounds + zero-filter) |
| Null/missing detection | implicit in v1 | ✅ Ported |
| Imputation (median / KNN) | `Imputation` | ❌ Not needed (row-by-row, drop instead) |
| Normalization (z-score / minmax) | `DataTransformation` | ❌ Not needed (raw values stored) |
| PCA (95% variance) | `DataTransformation` | ❌ Not needed (no dimensionality issue) |

### What v2 has that v1 did NOT

- EPA AQI calculation (PM2.5 + CO sub-indices)
- Heat index (Rothfusz regression)
- Toxic gas index (composite CO + CO₂ score)
- Respiratory risk label
- GPS fallback + movement tracking (speed/distance)
- Real-time row-by-row processing (v1 was batch-only)

## CSV Test Loader

```bash
python load_csv.py                 # loads new CSV (all rows, skips if data exists)
python load_csv.py --force          # wipes test-device data, reloads
python load_csv.py --limit 50       # load only 50 rows
python load_csv.py --csv path.csv   # specify any CSV file
python load_csv.py --dry-run        # parse only, no DB writes
```

- Auto-detects CSV format: old (MQ135/MQ7) or new (timestamp, real GPS)
- Default CSV: `Sample_Data_with_location .csv` (77 rows, real GPS coords)
- Uses device ID `esp32-csv-test` (auto-registered)
- **Safe re-run:** skips if rows already exist; `--force` to reload

## Version History

| Version | Commit | What changed |
|---|---|---|
| v0.1 | `59d5ced` | ESP32 ingestion → Supabase `raw_telemetry` |
| v0.2 | `f2e2c1e` | Processing pipeline + 25 s background worker |
| v0.3 | `b8281d1` | CSV loader + full pipeline test (250 rows end-to-end) |
| v0.4 | `b93685d` | ngrok tunnel + ESP32 firmware + 15 s processing interval |
| v0.5 | `d3134b6` | Real GPS CSV loader + full pipeline verification (77 rows) |
| v0.6 | `5d365ac` | Data validation: bounds check, zero-filter, IQR clip (77→65 rows) |
| v0.7 | — | Zone interpolation: IDW heatmap + contour zones (GeoJSON) |

## Test Results (77-row CSV)

| Metric | Value |
|---|---|
| Total raw rows | 77 |
| Dropped (dust=0 no-read) | 11 |
| Dropped (dust>500 hardware fail) | 1 |
| IQR-clipped (dust outliers) | ~9 (kept, values capped) |
| Final processed rows | 65 (84.4% pass rate) |

## Zone Interpolation (`/api/zones`)

Converts discrete sensor points into continuous air-quality zones using
**Inverse Distance Weighting (IDW)** interpolation.

### Modes

| Mode | Description |
|---|---|
| `heatmap` (default) | Grid cells with interpolated AQI + opacity |
| `contours` | AQI-band polygons (Good/Moderate/Unhealthy/…) |
| `points` | Raw sensor markers (aggregated by GPS coord) |
| `all` | All three layers in one response |

### Query Params

| Param | Default | Description |
|---|---|---|
| `mode` | `heatmap` | Output format |
| `field` | `aqi_value` | Metric to interpolate (`pm25_ugm3`, `co_ppm`, etc.) |
| `resolution` | `30` | Grid size N×N (5–80) |
| `radius` | `500` | Influence radius in metres |
| `device_id` | — | Filter by device (optional) |
| `limit` | `200` | Max readings to use |

### Example

```bash
curl http://localhost:5001/api/zones?mode=contours
curl http://localhost:5001/api/zones?mode=heatmap\&resolution=50\&field=pm25_ugm3
curl http://localhost:5001/api/zones?mode=all
```

## Running

```bash
cd v2
source venv/bin/activate

# Option A: Flask + ngrok (ESP32 can reach you over internet)
python start.py

# Option B: Flask only (local network / testing)
python start.py --no-ngrok

# Option C: raw Flask (no start script)
python app.py
```

## ESP32 Setup

1. Flash `esp32/greenroute_node.ino` to your board
2. Run `python start.py` — it prints the ngrok URL
3. Paste the URL into the firmware's `serverURL` and re-flash
4. ESP32 starts sending data every 3 s → backend stores + processes

## Environment Variables (optional)

| Var | Default | Description |
|---|---|---|
| `SUPABASE_URL` | hardcoded | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | hardcoded | Service-role key |
| `PORT` | `5001` | Flask listen port |
| `PROCESS_INTERVAL` | `15` | Background worker interval (seconds) |
