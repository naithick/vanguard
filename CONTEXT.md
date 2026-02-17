# GreenRoute Mesh — Project Context

## Team Vanguard Hackathon Project

Real-time air quality monitoring using ESP32 IoT nodes on buses/bikes.
Data flows from edge devices → Supabase (cloud) → Flask API → React Map UI.

---

## Project Structure

```
/home/naithick/hackaton/
├── CONTEXT.md                       # This file
├── ESP32_Air_Quality_Data.csv       # Raw sensor CSV (1,176 records)
├── schema.sql                       # Full Supabase PostgreSQL schema
├── create_alerts_table.sql          # Standalone SQL — run in Supabase SQL Editor
├── supabase_rls_esp32.sql           # RLS policies for ESP32 anon-key INSERT
│
├── backend/                         # Python Flask API + processing
│   ├── api.py                       # Flask API server (port 5001)
│   ├── config.py                    # Supabase credentials & calibration config
│   ├── supabase_client.py           # All Supabase DB operations
│   ├── processor.py                 # Raw → processed data enrichment
│   ├── load_csv.py                  # One-shot CSV → Supabase loader
│   └── test_direct_insert.py        # Test script for ESP32-style direct insert
│
├── pipeline/                        # Offline data-science pipeline
│   ├── main_pipeline.py
│   ├── eda_module.py
│   ├── preprocessing_module.py
│   ├── resampling_module.py
│   └── processed_data/              # Pipeline output CSVs
│
├── green-path-ui/                   # Reference React app (DigitalGeographyLab)
│   └── src/                         # Used as design reference for our map UI
│
├── hope-graph-builder/              # Reference graph builder (not actively used)
│
└── .venv/                           # Python 3.14.3 virtual environment
```

---

## Supabase Cloud Database

| Setting      | Value |
|-------------|-------|
| **Project**  | `vwvnrqtakrgnnjbvkkhr` |
| **URL**      | `https://vwvnrqtakrgnnjbvkkhr.supabase.co` |
| **Auth Key** | Service-role key (in `backend/config.py`) |

### Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `devices` | 1 (`esp32-vanguard-001`) | Device registry + calibration |
| `raw_telemetry` | 1,176 | Raw ESP32 sensor readings |
| `processed_data` | 1,176 | Enriched data (AQI, heat index, toxic gas index, respiratory risk) |
| `identified_hotspots` | 0 | Pollution hotspot tracking |
| `community_reports` | 0 | Citizen-science input (future) |
| `alerts` | — | Threshold-based alerts (**run `create_alerts_table.sql` to create**) |

### Data Status
- All 1,176 CSV rows loaded into `raw_telemetry` + `processed_data`
- GPS fallback to Bangalore center (12.9716, 77.5946) — original CSV had (0,0)
- Single device registered: `esp32-vanguard-001`
- AQI across all rows: 500 (Hazardous) — real-world sensor readings

---

## ✅ COMPLETED

### 1. Supabase Integration
- Service-role key authentication (bypasses RLS)
- Full CRUD client in `supabase_client.py`
- CSV bulk loader (`load_csv.py`) with encoding fix (latin-1) + column auto-rename

### 2. Flask API Server (port 5001)
**Endpoints:**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/ingest` | ESP32 raw data ingestion → `raw_telemetry` |
| `POST` | `/api/process` | Trigger processing of pending telemetry |
| `GET` | `/api/readings` | Processed readings (flat list) |
| `GET` | `/api/readings/bubbles` | Legacy bubble format |
| `GET` | `/api/zones` | **Aggregated bubble zones** (clustered) |
| `GET` | `/api/hotspots` | Active pollution hotspots |
| `GET` | `/api/stats` | Overall statistics |
| `GET` | `/api/device/:id` | Device info |
| `POST` | `/api/device` | Register new device |
| `GET` | `/api/alerts` | Active alerts (popup data) |
| `POST` | `/api/alerts/:id/ack` | Acknowledge/dismiss an alert |
| `POST` | `/api/alerts/evaluate` | Manually trigger alert check |
| `GET` | `/api/health` | Health check |

### 3. Zone Clustering System
- Geohash-style grid: rounds lat/lng to configurable precision
- `precision=3` → ~111 m cells, `precision=2` → ~1.1 km cells
- Score types: `overall`, `aqi`, `pm25`, `co`, `temperature`, `toxic_gas`, `humidity`
- Each zone returns: center lat/lng, radius, color, opacity, aggregate metrics
- Radius & opacity scale with severity + reading count

### 4. Alert System
- Threshold-based evaluation against zone aggregates
- Alert types: `aqi`, `pm25`, `co`, `heat`, `toxic_gas`
- Severity levels: `info`, `warning`, `danger`, `critical`
- Dedup: one alert per type per zone per severity
- Background worker checks every ~30 seconds
- Human-readable messages with action guidance

### 5. Data Processing Pipeline (`processor.py`)
- `calibrate_dust()` → PM2.5 µg/m³
- `calibrate_mq135()` → CO₂ ppm
- `calibrate_mq7()` → CO ppm
- `calculate_aqi()` → EPA AQI (PM2.5 + CO sub-indices)
- `calculate_heat_index()` → Rothfusz regression
- `calculate_toxic_gas_index()` → 0-100 composite
- `calculate_respiratory_risk()` → Low/Moderate/High/Very High/Severe

### 6. ESP32 Direct-to-Cloud (prepared)
- RLS policies for anon-key INSERT (`supabase_rls_esp32.sql`)
- Arduino sketch pattern for ESP32 → Supabase REST POST (friend roaming scenario)

### 7. Offline Pipeline
- EDA, preprocessing, resampling modules
- 1,176 → 378 records (67.9% reduction via time-series aggregation)

---

## 🔜 TODO

1. **Run `create_alerts_table.sql`** in Supabase SQL Editor → enables alert persistence
2. **Map UI** — Embeddable React component using zone bubbles from `/api/zones`
3. **Real GPS data** — Currently all at one point (ESP32 GPS was 0,0)
4. **ESP32 OTA** — Flash the Arduino sketch to the physical device
5. **Email/SMS alerts** — Currently API-only (dummy popup); add notification channels
6. **Community reporting** — Citizen-science report submission
7. **WebSocket / Supabase Realtime** — Push-based updates instead of polling

---

## Commands Reference

### Start API Server
```bash
cd /home/naithick/hackaton
source .venv/bin/activate
python backend/api.py
```

### Kill Port 5001
```bash
fuser -k 5001/tcp
```

### Test API
```bash
curl http://localhost:5001/api/health
curl http://localhost:5001/api/stats
curl http://localhost:5001/api/zones
curl http://localhost:5001/api/zones?score=pm25&precision=2
curl http://localhost:5001/api/alerts
curl -X POST http://localhost:5001/api/alerts/evaluate
```

### Load CSV (one-time)
```bash
python backend/load_csv.py
```

---

## Data Schema

### ESP32 Raw Sensor Fields
| Field | Description |
|-------|-------------|
| Dust | Particulate matter (raw ADC) |
| MQ135 | Air quality sensor (CO₂, NH₃, etc.) |
| MQ7 | Carbon monoxide sensor |
| Temperature | Celsius |
| Humidity | Percentage |
| Pressure | Atmospheric hPa |
| Gas | General gas reading |
| Latitude/Longitude | GPS (0,0 in CSV → fallback 12.9716, 77.5946) |

### Processed Data (enriched)
| Field | Description |
|-------|-------------|
| pm25_ugm3 | Calibrated PM2.5 (µg/m³) |
| co_ppm | Calibrated CO (ppm) |
| co2_ppm | Calibrated CO₂ (ppm) |
| aqi_value | EPA AQI (0-500) |
| aqi_category | Good / Moderate / … / Hazardous |
| heat_index_c | Heat index (°C) |
| toxic_gas_index | 0-100 composite |
| respiratory_risk_label | Low → Severe |

### Zone Aggregate (from `/api/zones`)
| Field | Description |
|-------|-------------|
| zone_id | Grid key (e.g. "12.972,77.595") |
| lat, lng | Zone center |
| radius_m | Bubble radius (metres) |
| color | Hex color from AQI ramp |
| opacity | 0.15 – 0.85 |
| primary_score | 0-100 based on score_type |
| avg_aqi, max_aqi | Zone AQI stats |
| reading_count | Number of readings in zone |

---

## Tech Stack
- **Runtime**: Python 3.14.3 (venv)
- **Backend**: Flask 3.1.2, flask-cors 6.0.2
- **Database**: Supabase (PostgreSQL + PostGIS + Realtime)
- **Client SDK**: supabase-py 2.28.0
- **Frontend** (planned): React (based on green-path-ui patterns)
- **IoT**: ESP32 with dust/MQ135/MQ7/BME280 sensors
- **Reference**: github.com/DigitalGeographyLab/green-path-ui

---

*Last Updated: February 17, 2026*
