# GreenRoute Mesh v2 — Project Context

> Last updated: 2026-02-17 · **v0.2**

## Overview

Clean rewrite of the GreenRoute Mesh backend. ESP32 nodes send raw air-quality
telemetry to a Flask API, which stores it in Supabase. A background worker
processes the data every 25 seconds.

## Architecture

```
ESP32 node  ──(POST JSON every 5 s)──►  Flask /api/ingest
                                             │
                                             ▼
                                      raw_telemetry (Supabase)
                                             │
                                    background worker (25 s)
                                             │
                                             ▼
                                     processed_data (Supabase)
```

## Data Flow

1. **Ingestion** — ESP32 POSTs raw sensor JSON to `/api/ingest` every 5 seconds.
   Device is auto-registered on first contact.
2. **Storage** — Raw payload written to `raw_telemetry` table as-is.
3. **Processing** — Background thread wakes every 25 s, fetches all
   `processed=false` rows, runs calibration + derived metrics, writes
   enriched rows to `processed_data`, marks originals as processed.

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
| GET | `/api/stats` | Summary counts |
| GET | `/api/health` | Health check |

## Files

```
v2/
├── app.py              # Flask server + background worker
├── config.py           # Supabase creds, calibration defaults, AQI breakpoints
├── processor.py        # Raw → processed conversion (AQI, heat index, etc.)
├── supabase_client.py  # Thin Supabase wrapper (devices, raw, processed)
├── load_csv.py         # One-shot CSV loader (safe to re-run, --force to reload)
├── requirements.txt    # Frozen pip dependencies
├── CONTEXT.md          # This file
└── venv/               # Python virtual environment (gitignored)
```

## Processing Pipeline (per row)

1. **Calibrate sensors** — dust→PM2.5, MQ135→CO₂, MQ7→CO
2. **GPS fallback** — if (0,0) use device's static location
3. **Derived metrics** — AQI (EPA), heat index, toxic gas index, respiratory risk
4. **Movement** — speed + distance from previous GPS fix

## CSV Test Loader

```bash
python load_csv.py                 # loads 250 rows (skips if data exists)
python load_csv.py --force          # wipes test-device data, reloads
python load_csv.py --limit 100      # load only 100 rows
python load_csv.py --dry-run        # parse only, no DB writes
```

- Uses device ID `esp32-csv-test` (auto-registered)
- **Safe re-run:** skips if rows already exist; `--force` to reload
- Default limit: 250 rows (out of 1176 in CSV)

## Version History

| Version | Commit | What changed |
|---|---|---|
| v0.1 | `59d5ced` | ESP32 ingestion → Supabase `raw_telemetry` |
| v0.2 | `f2e2c1e` | Processing pipeline + 25 s background worker |
| v0.3 | — | CSV loader + full pipeline test (250 rows end-to-end) |

## Running

```bash
cd v2
source venv/bin/activate
python app.py          # starts on :5001 with background worker
```

## Environment Variables (optional)

| Var | Default | Description |
|---|---|---|
| `SUPABASE_URL` | hardcoded | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | hardcoded | Service-role key |
| `PORT` | `5001` | Flask listen port |
| `PROCESS_INTERVAL` | `25` | Background worker interval (seconds) |
