# GreenRoute Mesh - Air Quality Monitoring System

A real-time air quality monitoring platform using ESP32 mesh networks with ML-powered sensor calibration and predictive analytics.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   ESP32 Nodes   │────▶│  Flask Backend  │────▶│  React Frontend │
│   (Sensors)     │     │  Port 5001      │     │  Port 5173      │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                        ┌────────▼────────┐
                        │    Supabase     │
                        │   (PostgreSQL)  │
                        └─────────────────┘
```

## Tech Stack

- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Backend**: Flask (Python 3.10+)
- **Database**: Supabase (PostgreSQL)
- **ML Models**: XGBoost (sensor calibration, false positive detection, radius prediction)
- **Maps**: Leaflet + react-leaflet
- **Charts**: Recharts

---

## Backend API Endpoints

### Core Data
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ingest` | POST | ESP32 sends raw sensor data |
| `/api/readings` | GET | Latest processed readings |
| `/api/readings/history/monthly` | GET | Daily aggregates for calendar view |
| `/api/devices` | GET | All devices with latest reading |
| `/api/devices/<id>` | GET | Device details with recent readings |
| `/api/stats` | GET | System statistics (counts, averages) |
| `/api/health` | GET | Backend health check |

### Zones & Maps
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/zones` | GET | Interpolated air quality GeoJSON |
| Query: `mode` | | `heatmap`, `contours`, `points`, `all` |
| Query: `field` | | `aqi_value`, `pm25_ugm3`, `co_ppm`, etc. |
| Query: `resolution` | | Grid size (5-80, default 30) |

### Alerts (Auto-generated from AQI thresholds)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/alerts` | GET | List alerts (filter: `active`, `severity`, `alert_type`) |
| `/api/alerts/<id>` | GET | Single alert |
| `/api/alerts` | POST | Create manual alert |
| `/api/alerts/<id>/resolve` | PUT | Resolve an alert |

### User Reports (Anonymous)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reports` | GET | List reports (filter: `status`, `category`) |
| `/api/reports/<id>` | GET | Single report |
| `/api/reports` | POST | Create report |
| `/api/reports/<id>/status` | PUT | Update status |
| `/api/reports/<id>/upvote` | POST | Upvote a report |

### Hotspots (ML-detected pollution clusters)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/hotspots` | GET | All hotspots |
| `/api/hotspots/active` | GET | Currently active hotspots |
| `/api/hotspots/<id>` | GET | Single hotspot |
| `/api/hotspots/detect` | POST | Trigger detection manually |

### Report Generation
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/reports/generate` | GET | Generate summary report |
| Query: `period` | | `day`, `week`, `month`, `quarter`, `year` |
| Query: `format` | | `json`, `excel`, `pdf` |

---

## Database Schema (Supabase)

### `devices`
- `device_id` (string, PK) - ESP32 identifier
- `name` (string) - Human-readable name
- `status` (enum) - active/inactive/maintenance
- `static_latitude`, `static_longitude` - Fixed location
- `dust_calibration`, `mq135_calibration`, `mq7_calibration` - Calibration factors

### `raw_telemetry`
Raw sensor data from ESP32 before processing:
- `dust`, `mq135`, `mq7` - Raw sensor values
- `temperature`, `humidity`, `pressure`, `gas` - Environmental
- `latitude`, `longitude` - GPS coordinates
- `processed` (bool) - Processing flag

### `processed_data`
Calibrated and enriched readings:
- Calibrated: `pm25_ugm3`, `co2_ppm`, `co_ppm`
- Environmental: `temperature_c`, `humidity_pct`, `pressure_hpa`, `gas_resistance`
- Derived: `aqi_value`, `aqi_category`, `heat_index_c`, `toxic_gas_index`, `respiratory_risk_label`
- Movement: `speed_kmh`, `distance_moved_m`

### `alerts`
- `alert_type` (enum) - aqi, pm25, co
- `severity` (enum) - critical, danger, warning, info
- `title`, `message`, `latitude`, `longitude`
- `active` (bool), `resolved_at`

### `reports`
User-submitted pollution reports:
- `category` (enum) - smoke, dust, smell, traffic, industrial, etc.
- `severity` (enum) - low, medium, high, critical
- `status` (enum) - open, investigating, resolved
- `upvotes` (int)

### `hotspots`
ML-detected pollution clusters:
- `center_lat`, `center_lon`, `radius_m`
- `avg_aqi`, `severity`
- `contributing_devices` (array)
- `resolved_at`

---

## ML Models (`backend/models/`)

### `calibration_model.json`
XGBoost model for sensor calibration. Converts raw MQ/dust sensor values to calibrated PM2.5/CO readings.

### `false_positive_model.json`
Detects anomalous readings that are likely sensor errors rather than actual pollution events.

### `radius_model.json`
Predicts the radius of a pollution hotspot based on AQI values and environmental conditions.

---

## Frontend Structure

### Views (`frontend/src/components/views/`)
| View | Description |
|------|-------------|
| `DashboardView` | Main overview with health index, fleet status, weather |
| `MapView` | Interactive map with heatmap/contours/points modes |
| `AlertsView` | Real-time alerts list |
| `ReportsView` | User reports management |
| `CalendarView` | Historical daily data calendar |
| `HistoryView` | Time-series charts |
| `AnalyticsView` | Trend analysis and insights |
| `SettingsView` | Configuration |

### Key Components
| Component | Data Source |
|-----------|-------------|
| `CityHealthIndex` | `/api/readings` - Real-time AQI gauge |
| `FleetStatus` | `/api/devices` - Device online percentage |
| `SystemStatus` | `/api/stats` - Pipeline metrics |
| `PollutantLevels` | `/api/readings` - Real-time telemetry chart |
| `AIInsightCards` | `/api/alerts` - Live alert feed |
| `PredictiveHotspots` | `/api/hotspots/active` - Hotspot predictions |
| `WeatherDetails` | `/api/readings` - Temperature, humidity, pressure |

---

## ESP32 Sensor Node

### Hardware
- ESP32 DevKit
- PMS5003 (PM2.5 dust sensor)
- MQ-135 (CO2/air quality)
- MQ-7 (CO)
- BME680 (temperature, humidity, pressure, gas)
- GPS module (optional)

### Firmware (`backend/esp32/greenroute_node.ino`)
Posts JSON to `/api/ingest`:
```json
{
  "device_id": "esp32-001",
  "dust": 45.0,
  "mq135": 890.0,
  "mq7": 580.0,
  "temperature": 28.5,
  "humidity": 65.0,
  "pressure": 1013.25,
  "gas": 50000.0,
  "latitude": 12.9716,
  "longitude": 77.5946
}
```

---

## Environment Variables

### Backend (`backend/.env`)
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
PORT=5001
PROCESS_INTERVAL=30
```

---

## Quick Start

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py

# Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Or use the start scripts:
```bash
./start_all.sh        # Linux/Mac
start_all.bat         # Windows
```

---

## Processing Pipeline

1. **Ingest**: ESP32 → `/api/ingest` → `raw_telemetry` table
2. **Process**: XGBoost calibration → bounds check → outlier filtering → enrichment
3. **Store**: `processed_data` table with all derived metrics
4. **Alert**: Auto-create alerts if AQI > thresholds
5. **Hotspot**: Background worker runs every 5 cycles to detect clusters
6. **Zones**: Build interpolated GeoJSON for map visualization

---

## AQI Thresholds (Auto-alerts)

| AQI Range | Severity | Description |
|-----------|----------|-------------|
| > 300 | Critical | Hazardous |
| > 200 | Danger | Very Unhealthy |
| > 150 | Warning | Unhealthy |
| > 100 | Info | Sensitive Groups |

---

## Development

- Backend: Flask with hot reload disabled for stability
- Frontend: Vite HMR enabled
- Background worker: 30s interval for processing stragglers
- Hotspot detection: Every 5 processing cycles (~2.5 min)
