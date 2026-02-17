# GreenRoute Mesh v2 — Project Context

> Last updated: 2026-02-18 · **v1.1**

## Overview

Clean rewrite of the GreenRoute Mesh backend. ESP32 nodes send raw air-quality
telemetry to a Flask API (exposed via ngrok), which stores it in Supabase.
A background worker processes the data every 15 seconds (5 ESP32 cycles).

**Current status:** Processing pipeline has calibration + derived metrics +
data validation (bounds checking, zero-value filtering, IQR outlier clipping).
Ported from v1's preprocessing module.

## Architecture

```
ESP32 node  ──(POST JSON every 3 s)──►  ngrok tunnel ──►  Flask /api/ingest (:5001)
                                                                   │
CPCB .xlsx/.csv  ──►  load_cpcb.py (reverse calibration)  ──►      │
                                                                   ▼
                                                          raw_telemetry (Supabase)
                                                                   │
                                                         background worker (30 s)
                                                                   │
                                                                   ▼
                                                          processed_data (Supabase)
```

## Data Flow

1. **Ingestion** — ESP32 POSTs raw sensor JSON to `/api/ingest` every 3 seconds
   via ngrok tunnel. Device is auto-registered on first contact.
2. **CPCB Loader** — `load_cpcb.py` reads government station Excel/CSV files,
   applies reverse calibration (PM2.5→raw_dust, etc.), and bulk-inserts into
   `raw_telemetry` (chunks of 500, `returning='minimal'`).
3. **Storage** — Raw payload written to `raw_telemetry` table immediately.
4. **Processing** — Background thread wakes every 30 s, fetches all
   `processed=false` rows (up to 1000), runs validation + calibration + derived
   metrics, batch-upserts into `processed_data` (chunks of 500), marks
   originals as processed.

## Supabase Tables Used

| Table | Purpose |
|---|---|
| `devices` | Node registry — ESP32 + CPCB stations (auto-created) |
| `raw_telemetry` | Verbatim sensor readings (ESP32 + CPCB loader) |
| `processed_data` | Calibrated + enriched readings (AQI, heat index, etc.) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/ingest` | ESP32 sends raw sensor JSON |
| POST | `/api/process` | Manually trigger processing |
| GET | `/api/readings` | Latest processed data |
| GET | `/api/devices` | All devices + latest reading per device |
| GET | `/api/devices/<id>` | Single device info |
| GET | `/api/devices/<id>/latest` | Latest reading for a device |
| GET | `/api/zones` | Interpolated air-quality zones (GeoJSON) |
| GET | `/api/stats` | Summary counts (device_count, total, avg AQI) |
| GET | `/api/health` | Health check |

## Files

```
v2/
├── app.py              # Flask server + background worker (15 s cycle)
├── config.py           # Supabase creds, calibration defaults, AQI breakpoints
├── processor.py        # Raw → processed conversion (AQI, heat index, etc.)
├── zones.py            # IDW interpolation → continuous air-quality zones (GeoJSON)
├── supabase_client.py  # Supabase wrapper (batch upsert, chunks of 500)
├── load_csv.py         # Legacy CSV loader (esp32-csv-test device)
├── load_cpcb.py        # CPCB station loader (5 stations, reverse calibration)
├── map.html            # Map viewer (Leaflet + heatmap, centered on Chennai)
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

## CPCB Station Loader

```bash
python load_cpcb.py                 # load all 5 stations (skips if data exists)
python load_cpcb.py --force          # wipe all CPCB data, reload from scratch
python load_cpcb.py --limit 500      # load max 500 rows per station
python load_cpcb.py --dry-run        # parse only, no DB writes
```

### 5 Chennai CPCB Monitoring Stations

| Station | Device ID | Lat | Lon | Rows |
|---|---|---|---|---|
| Velachery | `cpcb-velachery-288` | 12.9815 | 80.2180 | 458 |
| Manali | `cpcb-manali-5092` | 13.1662 | 80.2585 | 499 |
| Arumbakkam | `cpcb-arumbakkam-5361` | 13.0694 | 80.2121 | 165 |
| Perungudi | `cpcb-perungudi-5363` | 12.9611 | 80.2420 | 496 |
| Alandur | `cpcb-alandur-293` | 13.0067 | 80.2006 | 836 |
| **Total** | | | | **6,805** |

### Reverse calibration (CPCB → raw sensor values)

- `raw_dust = PM2.5 / 1.5` (inverse of processor's calibration)
- `raw_mq135 = 900 × (CO₂ / 116.6)^(-1/2.769)`
- `raw_mq7 = 590 × (CO / 99.042)^(-1/1.518)`
- Alandur: 8-hour rolling windows → synthetic 15-min readings

### Data source files (in parent dir)

- `site_288*.xlsx` — Velachery
- `site_5092*.xlsx` — Manali
- `site_5361*.xlsx` — Arumbakkam
- `site_5363*.xlsx` — Perungudi
- `Raw_data_15Min*.csv` — Alandur (different format)

## Legacy CSV Loader

```bash
python load_csv.py --force           # old 77-row test CSV
```

## Version History

| Version | Commit | What changed |
|---|---|---|
| v0.1 | `59d5ced` | ESP32 ingestion → Supabase `raw_telemetry` |
| v0.2 | `f2e2c1e` | Processing pipeline + 25 s background worker |
| v0.3 | `b8281d1` | CSV loader + full pipeline test (250 rows end-to-end) |
| v0.4 | `b93685d` | ngrok tunnel + ESP32 firmware + 15 s processing interval |
| v0.5 | `d3134b6` | Real GPS CSV loader + full pipeline verification (77 rows) |
| v0.6 | `5d365ac` | Data validation: bounds check, zero-filter, IQR clip (77→65 rows) |
| v0.7 | `2ece4f7` | Zone interpolation: IDW heatmap + contour zones (GeoJSON) |
| v0.8 | `b6a3243` | Map viewer: Leaflet + smooth canvas heatmap, metric picker |
| v0.9 | `87ab3a4` | CSV loader — 3-way format detection |
| v1.0 | `50e7464` | Remove v1 files — repo now v2 only |
| v1.1 | `8f74e5a` | CPCB station loader, batch optimization, map re-centered |

## CPCB Data Results (6,805 rows)

| Metric | Value |
|---|---|
| Total raw rows loaded | 6,805 |
| Processed (passed validation) | 3,286 (48%) |
| Dropped (raw_dust=0, out of bounds) | ~3,519 |
| Active devices | 5 |
| Avg AQI (recent) | 131.6 (Sensitive) |

### Per-station pass rates

| Station | Raw | Processed | Pass % | Notes |
|---|---|---|---|---|
| Velachery | 458 | ~0 | 0% | raw_dust=0 / pressure out of bounds |
| Manali | 499 | ~454 | 91% | Good quality |
| Arumbakkam | 165 | ~165 | 100% | Clean data |
| Perungudi | 496 | ~496 | 100% | Clean data |
| Alandur | 836 | ~485 | 58% | Many out-of-bounds values |

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
