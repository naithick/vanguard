# GreenRoute Mesh

Real-time air quality monitoring system with XGBoost ML calibration for accurate pollution tracking.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-green.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)

## Features

- **Real-time Air Quality Monitoring** — Live PM2.5, CO2, CO, temperature, humidity tracking
- **XGBoost ML Calibration** — 33% accuracy improvement over raw sensor data
- **False Positive Detection** — Identifies smoking, traffic, kitchen, industrial pollution sources
- **Pollution Hotspot Detection** — Automatic zone identification with influence radius
- **Interactive Dashboard** — React + Vite frontend with maps and charts
- **PDF Report Generation** — Automated air quality reports
- **ESP32 Integration** — Low-cost sensor nodes with WiFi connectivity

## Architecture

```
greenroute/
├── backend/              # Flask API Server
│   ├── app.py            # Main server (port 5001)
│   ├── processor.py      # Raw → calibrated data pipeline
│   ├── hotspots.py       # Pollution zone detection
│   ├── zones.py          # Zone boundary management
│   ├── report_gen.py     # PDF report generation
│   ├── xgboost_inference.py  # ML inference engine
│   ├── models/           # Trained XGBoost weights
│   │   ├── calibration_model.json
│   │   ├── false_positive_model.json
│   │   └── radius_model.json
│   └── esp32/            # Arduino sensor code
│
└── frontend/             # React + Vite Dashboard
    └── src/
        ├── components/   # UI components
        ├── api/          # Backend API client
        └── hooks/        # React hooks
```

---

## Installation

### Prerequisites

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.9+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| Git | Latest | [git-scm.com](https://git-scm.com/) |

### Clone Repository

```bash
git clone https://github.com/yourusername/greenroute-mesh.git
cd greenroute-mesh
```

---

## Linux Setup

### Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your Supabase credentials

# Start server
python app.py
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Quick Start (Linux)

```bash
# Terminal 1 - Backend
./start_backend.sh

# Terminal 2 - Frontend
./start_frontend.sh
```

---

## macOS Setup

### Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
open -e .env  # Edit with TextEdit, add Supabase credentials

# Start server
python app.py
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Quick Start (macOS)

```bash
# Terminal 1 - Backend
./start_backend.sh

# Terminal 2 - Frontend
./start_frontend.sh
```

---

## Windows Setup

### Backend

```powershell
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
notepad .env  # Add your Supabase credentials

# Start server
python app.py
```

### Frontend

```powershell
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Quick Start (Windows)

Create `start_backend.bat`:
```batch
@echo off
cd backend
call venv\Scripts\activate
python app.py
```

Create `start_frontend.bat`:
```batch
@echo off
cd frontend
npm run dev
```

---

## Environment Configuration

Create `backend/.env` with:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

### Getting Supabase Credentials

1. Go to [supabase.com](https://supabase.com) and create a project
2. Navigate to **Settings** → **API**
3. Copy **Project URL** → `SUPABASE_URL`
4. Copy **service_role key** → `SUPABASE_SERVICE_KEY`

---

## Database Setup

Run these SQL commands in Supabase SQL Editor:

```sql
-- Devices table
CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    name TEXT,
    status TEXT DEFAULT 'active',
    static_latitude FLOAT,
    static_longitude FLOAT,
    dust_calibration FLOAT DEFAULT 1.0,
    mq135_calibration FLOAT DEFAULT 1.0,
    mq7_calibration FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Raw telemetry from ESP32
CREATE TABLE raw_telemetry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id TEXT REFERENCES devices(device_id),
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    raw_dust FLOAT,
    raw_mq135 FLOAT,
    raw_mq7 FLOAT,
    temperature FLOAT,
    humidity FLOAT,
    pressure FLOAT,
    gas_resistance FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    speed FLOAT
);

-- Processed/calibrated data
CREATE TABLE processed_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_telemetry_id UUID REFERENCES raw_telemetry(id),
    device_id TEXT REFERENCES devices(device_id),
    recorded_at TIMESTAMPTZ,
    pm25_ugm3 FLOAT,
    pm25_calibrated FLOAT,
    co2_ppm FLOAT,
    co_ppm FLOAT,
    temperature_c FLOAT,
    humidity_pct FLOAT,
    pressure_hpa FLOAT,
    gas_resistance FLOAT,
    latitude FLOAT,
    longitude FLOAT,
    aqi_value INT,
    aqi_category TEXT,
    heat_index_c FLOAT,
    toxic_gas_index FLOAT,
    respiratory_risk_label TEXT,
    source_classification TEXT,
    is_false_positive BOOLEAN DEFAULT FALSE,
    influence_radius_m FLOAT,
    speed_kmh FLOAT,
    distance_moved_m FLOAT,
    gps_fallback_used BOOLEAN DEFAULT FALSE
);

-- Alerts
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id TEXT REFERENCES devices(device_id),
    alert_type TEXT,
    severity TEXT,
    message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    acknowledged BOOLEAN DEFAULT FALSE
);

-- Reports
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    report_type TEXT,
    zone_name TEXT,
    start_date DATE,
    end_date DATE,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    pdf_data BYTEA
);

-- Hotspots
CREATE TABLE hotspots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_name TEXT,
    center_lat FLOAT,
    center_lng FLOAT,
    radius_m FLOAT,
    avg_aqi FLOAT,
    peak_aqi FLOAT,
    reading_count INT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/readings` | Latest processed readings |
| GET | `/api/readings?device_id=X` | Readings for specific device |
| GET | `/api/devices` | All registered devices |
| GET | `/api/stats` | Aggregate statistics |
| GET | `/api/hotspots` | Active pollution hotspots |
| GET | `/api/zones` | Zone boundaries |
| POST | `/api/reports/generate` | Generate PDF report |
| POST | `/api/telemetry` | Receive ESP32 data |

### Example API Calls

```bash
# Health check
curl http://localhost:5001/api/health

# Get latest readings
curl http://localhost:5001/api/readings?limit=10

# Get all devices
curl http://localhost:5001/api/devices

# Get statistics
curl http://localhost:5001/api/stats
```

---

## XGBoost ML Pipeline

### Models

| Model | Purpose | Input Features | Output |
|-------|---------|----------------|--------|
| `calibration_model.json` | Sensor calibration | raw_dust, temp, humidity, pressure | Calibrated PM2.5 |
| `false_positive_model.json` | Source detection | PM2.5, CO2, CO, gas_resistance | Source type (0-4) |
| `radius_model.json` | Influence radius | AQI, wind_speed, readings_count | Radius (50-500m) |

### Source Classifications

| Code | Source | Description |
|------|--------|-------------|
| 0 | ambient | Normal environmental pollution |
| 1 | smoking | Cigarette/tobacco smoke nearby |
| 2 | traffic | Vehicle exhaust emissions |
| 3 | kitchen | Cooking fumes |
| 4 | industrial | Factory/industrial emissions |

### Training (for developers)

```bash
# On a powerful machine (e.g., M4 Mac)
cd backend
python xgboost_train.py

# Models saved to backend/models/
```

---

## ESP32 Sensor Setup

### Hardware Required

- ESP32 DevKit
- GP2Y1010AU0F dust sensor
- MQ-135 air quality sensor
- MQ-7 CO sensor
- BME680 environmental sensor
- GPS module (optional)

### Flashing

1. Open `backend/esp32/greenroute_node.ino` in Arduino IDE
2. Install required libraries: WiFi, HTTPClient, ArduinoJson
3. Update WiFi credentials and server URL
4. Flash to ESP32

---

## Troubleshooting

### Backend won't start

```bash
# Check Python version
python --version  # Should be 3.9+

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check .env file exists
cat backend/.env
```

### Frontend build fails

```bash
# Clear npm cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### Database connection error

1. Verify Supabase URL and key in `.env`
2. Check Supabase project is active
3. Ensure tables are created

### XGBoost models not loading

```bash
# Verify models exist
ls -la backend/models/

# Should show:
# calibration_model.json
# false_positive_model.json
# radius_model.json
```

---

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- CPCB India for ground truth air quality data
- XGBoost team for the ML library
- Supabase for the backend infrastructure
