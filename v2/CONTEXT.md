# GreenRoute Mesh v2 — Project Context

> Last updated: 2026-02-18 · **v1.4**

## Overview

GreenRoute Mesh v2 backend — Flask API + Supabase, with two data sources:
1. **ESP32 nodes** — real-time air-quality telemetry via ngrok tunnel
2. **CPCB government stations** — bulk-loaded historical data from 5 Chennai
   monitoring stations (PM2.5, NO₂, SO₂, CO, Ozone, Benzene, etc.)

A background worker processes raw data every 30 seconds and runs hotspot
detection every 5 cycles (~2.5 min). Batch operations use chunks of 500 rows
with `returning='minimal'` for optimal throughput.

**Current status:** 6,805 raw rows loaded from 5 CPCB stations → ~3,286
processed. Avg AQI: ~131 (Sensitive). 4 active hotspots detected.
Map centered on Chennai with live device markers, hotspot overlays, and
zone interpolation.

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
                                                          ┌────────┴────────┐
                                                          ▼                 ▼
                                                  processed_data     identified_hotspots
                                                  (AQI, metrics)    (auto-detect every 5 cycles)
                                                          │
                                                          ▼
                                                      alerts (auto + manual)
                                                      reports (anonymous user)
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
   metrics + **NULL imputation**, batch-upserts into `processed_data`.
5. **Hotspot Detection** — Every 5 background cycles, `hotspots.py` scans
   recent processed data, groups by device, and creates/updates/resolves hotspots
   in `identified_hotspots` based on AQI thresholds and sustained reading counts.
6. **Alerts** — Auto-generated when AQI exceeds thresholds during processing;
   also supports manual creation via API.
7. **Reports** — Anonymous users can submit pollution reports, upvote, and
   track status (open → investigating → resolved).

## Supabase Tables

| Table | Purpose |
|---|---|
| `devices` | Node registry — ESP32 + CPCB stations (auto-created) |
| `raw_telemetry` | Verbatim sensor readings (ESP32 + CPCB loader) |
| `processed_data` | Calibrated + enriched readings (AQI, heat index, etc.) |
| `alerts` | Air quality alerts (auto-generated + manual) |
| `reports` | Anonymous user pollution reports with upvotes |
| `identified_hotspots` | Detected pollution hotspots (auto-detect + manual trigger) |

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
| **Alerts** | | |
| GET | `/api/alerts` | List alerts (filter: `?severity=`, `?is_resolved=`) |
| GET | `/api/alerts/<id>` | Get single alert |
| POST | `/api/alerts` | Create manual alert (title, severity, alert_type, device_id) |
| PUT | `/api/alerts/<id>/resolve` | Resolve an alert |
| **Reports** | | |
| GET | `/api/reports` | List reports (filter: `?category=`, `?status=`, `?limit=`) |
| GET | `/api/reports/<id>` | Get single report |
| POST | `/api/reports` | Create anonymous report (title, category, severity, lat/lon) |
| PUT | `/api/reports/<id>/status` | Update status (open → investigating → resolved) |
| POST | `/api/reports/<id>/upvote` | Upvote a report |
| **Hotspots** | | |
| GET | `/api/hotspots` | List hotspots (`?include_resolved=true`, `?limit=`) |
| GET | `/api/hotspots/active` | Active hotspots only, sorted by severity |
| GET | `/api/hotspots/<id>` | Get single hotspot detail |
| POST | `/api/hotspots/detect` | Manually trigger detection (`{lookback_hours: 24}`) |

## Files

```
v2/
├── app.py              # Flask server + background worker (30 s cycle + hotspot detection)
├── config.py           # Supabase creds, calibration defaults, AQI breakpoints
├── processor.py        # Raw → processed (AQI, heat index, NULL imputation, etc.)
├── hotspots.py         # Hotspot detection engine (AQI threshold, auto-resolve)
├── zones.py            # IDW interpolation → continuous air-quality zones (GeoJSON)
├── supabase_client.py  # Supabase wrapper (batch upsert, chunks of 500)
├── load_csv.py         # Legacy CSV loader (esp32-csv-test device)
├── load_cpcb.py        # CPCB station loader (5 stations, reverse calibration)
├── map.html            # Map viewer (Leaflet — devices, hotspots, heatmap, auto-refresh)
├── start.py            # Launcher: Flask + ngrok in one command
├── requirements.txt    # Frozen pip dependencies
├── CONTEXT.md          # This file
├── tests/
│   ├── helpers.py          # Shared test utilities (formatting, HTTP client, tracker)
│   ├── test_processing.py  # Processing pipeline tests (ingest, calibrate, AQI, imputation)
│   ├── test_alerts.py      # Alert system tests (CRUD, validation, resolve)
│   ├── test_reports.py     # Report system tests (CRUD, upvote, status lifecycle)
│   ├── test_hotspots.py    # Hotspot detection tests (trigger, list, detail)
│   └── test_full_pipeline.py  # End-to-end pipeline test (all features)
├── esp32/
│   └── greenroute_node.ino   # ESP32 Arduino firmware
└── venv/               # Python virtual environment (gitignored)
```

## Processing Pipeline (per row)

0. **Data validation** — bounds check, zero-value filter, IQR outlier clipping
1. **NULL imputation** — per-device running median for temperature, humidity,
   pressure; falls back to Chennai climatological defaults (30°C, 70%, 1010 hPa)
2. **Calibrate sensors** — dust→PM2.5, MQ135→CO₂, MQ7→CO
3. **GPS fallback** — if (0,0) use device's static location
4. **Derived metrics** — AQI (EPA), heat index, toxic gas index, respiratory risk
5. **Movement** — speed + distance from previous GPS fix

### Validation details

| Check | Action | Example |
|---|---|---|
| Null critical fields | DROP row | `raw_dust` is null |
| Sensor out of bounds | DROP row | `dust=0` (no-read), `dust=674` (>500) |
| IQR outlier (dust) | CLIP to fence | `dust=221` → clipped to ~61 |
| NULL temp/humidity/pressure | IMPUTE | Device median or Chennai defaults |

### Hotspot Detection (`hotspots.py`)

| Parameter | Value | Description |
|---|---|---|
| `AQI_HOTSPOT_THRESHOLD` | 100 | Minimum AQI to flag as hotspot |
| `SUSTAINED_READINGS_MIN` | 3 | Min readings above threshold |
| `LOOKBACK_HOURS` | 24 | Time window for detection |
| `HOTSPOT_RADIUS_M` | 500 | Influence radius per hotspot |

**Logic:** Groups processed readings by device, computes stats (avg AQI, peak,
reading count). If a device has ≥3 readings with AQI ≥100 in the lookback
window, a hotspot is created/updated. Hotspots with no recent readings above
threshold are auto-resolved.

### v1 preprocessing features — ported to v2

| Feature | v1 module | v2 Status |
|---|---|---|
| Outlier removal (IQR, 1.5×) | `OutlierRemoval` | ✅ Ported (clip action on dust) |
| Sensor bounds checking | implicit in v1 | ✅ Ported (hard bounds + zero-filter) |
| Null/missing detection | implicit in v1 | ✅ Ported |
| Imputation (median) | `Imputation` | ✅ Ported (per-device median for weather fields) |
| Normalization (z-score / minmax) | `DataTransformation` | ❌ Not needed (raw values stored) |
| PCA (95% variance) | `DataTransformation` | ❌ Not needed (no dimensionality issue) |

### What v2 has that v1 did NOT

- EPA AQI calculation (PM2.5 + CO sub-indices)
- Heat index (Rothfusz regression)
- Toxic gas index (composite CO + CO₂ score)
- Respiratory risk label
- GPS fallback + movement tracking (speed/distance)
- Real-time row-by-row processing (v1 was batch-only)
- Hotspot detection engine with auto-resolve
- Alert system (auto-generated + manual)
- Anonymous user reporting with upvotes and status tracking

## Map Viewer (`map.html`)

Interactive Leaflet map with three dynamic layers:

| Layer | Source | Auto-refresh |
|---|---|---|
| **Devices** | `/api/devices` | every 60 s |
| **Hotspots** | `/api/hotspots/active` | every 60 s |
| **Zones** | `/api/zones` (heatmap/contour/points) | every 60 s |

**Features:**
- Device markers colored by AQI with detailed popups (PM2.5, temp, humidity, risk)
- Hotspot pulsing markers + translucent radius circles (500 m) with severity coloring
- Layer toggles to show/hide each layer independently
- Metric picker (AQI, PM2.5, CO₂, CO, temperature, humidity, heat index, toxic gas)
- Three zone view modes: heatmap (smooth canvas), contours, points
- Resolution and opacity controls
- Auto-refresh every 60 seconds with countdown indicator

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

### Data source files (in `dump/`)

- `site_288*.xlsx` — Velachery
- `site_5092*.xlsx` — Manali
- `site_5361*.xlsx` — Arumbakkam
- `site_5363*.xlsx` — Perungudi
- `Raw_data_15Min*.csv` — Alandur (different format)

## Test Suite

5 modular test files under `v2/tests/`:

| File | Tests | Scope |
|---|---|---|
| `test_processing.py` | 15 | Ingest, calibration, AQI, derived metrics, NULL imputation |
| `test_alerts.py` | 11 | Alert CRUD, validation, resolve lifecycle |
| `test_reports.py` | 13 | Report CRUD, upvote, status lifecycle, filtering |
| `test_hotspots.py` | 7 | Detection trigger, list active, single retrieval |
| `test_full_pipeline.py` | 11 | End-to-end: health → ingest → process → alerts → reports → hotspots → zones |
| **Total** | **57** | |

```bash
cd v2
source venv/bin/activate
python app.py &                    # start server first
python tests/test_processing.py    # run individual test
python tests/test_full_pipeline.py # run full e2e
```

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
| `field` | `aqi_value` | Metric to interpolate |
| `resolution` | `30` | Grid size N×N (5–80) |
| `radius` | `500` | Influence radius in metres |
| `device_id` | — | Filter by device (optional) |
| `limit` | `200` | Max readings to use |

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
| v1.1 | `8f74e5a` | CPCB station loader, batch optimization, map re-centered for Chennai |
| v1.2 | `6d4a6cd` | Alert system + anonymous user reporting (backend only, no auth) |
| v1.3 | `3ae34d0` | Hotspot detection, NULL imputation, modular test suite (57 checks) |
| v1.4 | — | Dynamic map: live devices, hotspot overlays, auto-refresh, CONTEXT update |
