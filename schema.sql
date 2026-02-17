-- =============================================================================
-- Real-Time Urban Environmental Quality Monitor & Alert Network
-- PostgreSQL Schema for Supabase
-- =============================================================================
-- This schema supports the full data pipeline:
--   ESP32 Edge Nodes → raw_telemetry → Python Processing → processed_data
--                                                        → identified_hotspots
-- Plus a community_reports table for citizen-science input.
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 0. Extensions
-- ─────────────────────────────────────────────────────────────────────────────
-- PostGIS: spatial types & functions (ST_Distance, ST_MakePoint, geography casts)
-- pgcrypto: gen_random_uuid() for UUID primary keys (built-in on PG ≥ 14)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ─────────────────────────────────────────────────────────────────────────────
-- 1. devices — Asset Management & Per-Device Calibration
-- ─────────────────────────────────────────────────────────────────────────────
-- Every ESP32 node is registered here before it can submit telemetry.
-- Calibration factors are stored per device because optical dust sensors and
-- MQ-series gas sensors exhibit significant unit-to-unit variance that must
-- be corrected during the processing stage.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS devices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Human-readable identifier burned into the ESP32 firmware.
    device_id       TEXT        NOT NULL UNIQUE,
    name            TEXT        NOT NULL,

    -- Operational status: 'active' | 'inactive' | 'maintenance' | 'decommissioned'
    status          TEXT        NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'inactive', 'maintenance', 'decommissioned')),

    -- ── Per-Device Calibration Factors ──────────────────────────────────────
    -- Dust sensor: multiplicative factor applied to the raw spike count (0–71)
    -- to convert it into PM2.5 µg/m³.  Derived from co-location with a
    -- reference-grade instrument (e.g., BAM-1020).  Default 1.0 = uncalibrated.
    dust_calibration    DOUBLE PRECISION NOT NULL DEFAULT 1.0,

    -- MQ135 (broad-spectrum air quality / CO₂-proxy): slope factor for the
    -- log-log Rs/R0 → PPM conversion curve.  Each unit's R0 differs.
    mq135_calibration   DOUBLE PRECISION NOT NULL DEFAULT 1.0,

    -- MQ7 (carbon monoxide): same approach — per-unit R0 correction factor.
    mq7_calibration     DOUBLE PRECISION NOT NULL DEFAULT 1.0,

    -- ── GPS Fallback (Static Location) ──────────────────────────────────────
    -- If the GPS module returns (0, 0) or fails to get a fix, the processing
    -- layer substitutes the static location registered for this device.
    -- Stored as a PostGIS POINT in SRID 4326 (WGS-84) for spatial queries.
    static_location     GEOGRAPHY(POINT, 4326),

    -- Convenience columns so the static lat/lon are easy to read without
    -- PostGIS function calls (useful in Supabase dashboard / REST queries).
    static_latitude     DOUBLE PRECISION,
    static_longitude    DOUBLE PRECISION,

    -- Firmware version currently running on the node (helpful for OTA tracking).
    firmware_version    TEXT,

    -- Free-form notes (installation site description, mounting height, etc.).
    description         TEXT,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on device_id for fast lookups when raw telemetry arrives.
CREATE INDEX IF NOT EXISTS idx_devices_device_id ON devices (device_id);

COMMENT ON TABLE  devices IS 'Registry of ESP32 edge nodes with per-unit calibration factors and GPS-fallback locations.';
COMMENT ON COLUMN devices.dust_calibration  IS 'Multiplicative factor: raw_dust_spikes × dust_calibration ≈ PM2.5 µg/m³.';
COMMENT ON COLUMN devices.mq135_calibration IS 'R0 correction factor for MQ135 Rs/R0 → CO₂-equivalent PPM curve.';
COMMENT ON COLUMN devices.mq7_calibration   IS 'R0 correction factor for MQ7 Rs/R0 → CO PPM curve.';
COMMENT ON COLUMN devices.static_location   IS 'Fallback GPS point (SRID 4326) used when hardware GPS returns (0,0).';


-- ─────────────────────────────────────────────────────────────────────────────
-- 2. raw_telemetry — Staging Area (Exactly What the ESP32 Sends)
-- ─────────────────────────────────────────────────────────────────────────────
-- This table is an append-only log of raw sensor readings.
-- NO derived values (AQI, speed, heat index) belong here.
-- NO battery voltage or WiFi RSSI — the hardware does not send them.
-- The Python processing script polls for rows where `processed = FALSE`,
-- performs calibration and inference, then marks them processed.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_telemetry (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- FK to devices.device_id (text match, not UUID, because the ESP32
    -- identifies itself by its burned-in string ID).
    device_id       TEXT        NOT NULL REFERENCES devices (device_id),

    -- Timestamp assigned by the ESP32 (may drift); server receipt time is
    -- captured in `received_at`.
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- ── Raw Dust Sensor ─────────────────────────────────────────────────────
    -- Optical pulse count per sampling window.  Range: 0–71 (integer spikes).
    raw_dust        DOUBLE PRECISION,

    -- ── Raw Gas Sensors ─────────────────────────────────────────────────────
    -- MQ135: analog ADC reading (typical idle ~890–915 on 10-bit ADC).
    raw_mq135       DOUBLE PRECISION,

    -- MQ7: analog ADC reading (typical idle ~560–620 on 10-bit ADC).
    raw_mq7         DOUBLE PRECISION,

    -- ── Environmental ───────────────────────────────────────────────────────
    temperature_c   DOUBLE PRECISION,   -- °C from DHT22 / BME280
    humidity_pct    DOUBLE PRECISION,   -- % RH
    pressure_hpa    DOUBLE PRECISION,   -- hPa (BME280 / BMP280)
    gas_resistance  DOUBLE PRECISION,   -- Ω (BME680 VOC proxy, if equipped)

    -- ── Raw GPS ─────────────────────────────────────────────────────────────
    -- Direct NMEA output.  (0, 0) signals "no fix" and triggers fallback
    -- to devices.static_location during processing.
    raw_latitude    DOUBLE PRECISION,
    raw_longitude   DOUBLE PRECISION,

    -- ── Processing Flag ─────────────────────────────────────────────────────
    -- The Python worker sets this to TRUE after successfully processing the
    -- row and inserting the result into processed_data.
    processed       BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Server-side receipt timestamp (always accurate, unlike recorded_at).
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The processing script's main query: "give me unprocessed rows, oldest first."
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_unprocessed
    ON raw_telemetry (processed, received_at ASC)
    WHERE processed = FALSE;

-- Time-series queries and per-device filtering.
CREATE INDEX IF NOT EXISTS idx_raw_telemetry_device_time
    ON raw_telemetry (device_id, recorded_at DESC);

COMMENT ON TABLE  raw_telemetry IS 'Append-only staging table for raw ESP32 sensor readings. No derived values.';
COMMENT ON COLUMN raw_telemetry.raw_dust    IS 'Optical dust sensor spike count (0–71). Needs per-device calibration to µg/m³.';
COMMENT ON COLUMN raw_telemetry.raw_mq135   IS 'MQ135 ADC value (~890–915 baseline). Converted to CO₂-equivalent PPM in processing.';
COMMENT ON COLUMN raw_telemetry.raw_mq7     IS 'MQ7 ADC value (~560–620 baseline). Converted to CO PPM in processing.';
COMMENT ON COLUMN raw_telemetry.processed   IS 'Set TRUE by the Python worker after calibration + insert into processed_data.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 3. processed_data — Master Record for the Frontend Dashboard
-- ─────────────────────────────────────────────────────────────────────────────
-- Every row here corresponds to exactly one raw_telemetry row after the Python
-- processing layer has applied:
--   • Sensor calibration (dust → PM2.5, MQ135 → CO₂, MQ7 → CO)
--   • GPS fallback (0,0 → static_location)
--   • Derived metrics (AQI, Heat Index, Toxic Gas Index, Respiratory Risk)
--   • Movement calculations (speed, distance from previous point)
-- The frontend reads ONLY from this table (and identified_hotspots).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS processed_data (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Back-reference to the raw row that produced this record.
    raw_telemetry_id    UUID        NOT NULL REFERENCES raw_telemetry (id),
    device_id           TEXT        NOT NULL REFERENCES devices (device_id),

    recorded_at         TIMESTAMPTZ NOT NULL,

    -- ── Calibrated Air Quality Values ───────────────────────────────────────
    -- PM2.5 in µg/m³: raw_dust × devices.dust_calibration
    pm25_ugm3           DOUBLE PRECISION,

    -- CO₂-equivalent in PPM: derived from MQ135 ADC via Rs/R0 log-log curve
    -- corrected by devices.mq135_calibration.
    co2_ppm             DOUBLE PRECISION,

    -- Carbon monoxide in PPM: derived from MQ7 ADC via Rs/R0 log-log curve
    -- corrected by devices.mq7_calibration.
    co_ppm              DOUBLE PRECISION,

    -- ── Pass-Through Environmental Readings ─────────────────────────────────
    temperature_c       DOUBLE PRECISION,
    humidity_pct        DOUBLE PRECISION,
    pressure_hpa        DOUBLE PRECISION,
    gas_resistance      DOUBLE PRECISION,

    -- ── Resolved Location ───────────────────────────────────────────────────
    -- Final lat/lon after GPS-fallback logic:
    --   if (raw_lat == 0 AND raw_lon == 0) → use devices.static_location
    --   else → use raw GPS values.
    latitude            DOUBLE PRECISION   NOT NULL,
    longitude           DOUBLE PRECISION   NOT NULL,

    -- PostGIS geography point for spatial queries (nearest hotspot, geofence).
    location            GEOGRAPHY(POINT, 4326),

    -- TRUE if the static fallback was used instead of live GPS.
    gps_fallback_used   BOOLEAN     NOT NULL DEFAULT FALSE,

    -- ── Enhanced Inferences (Computed by Python Processing Layer) ────────────

    -- AQI: US EPA Air Quality Index (0–500 scale).
    -- Calculated from the dominant pollutant (PM2.5 or CO).
    -- Formula: linear interpolation within EPA breakpoint table.
    aqi_value           INTEGER     CHECK (aqi_value BETWEEN 0 AND 500),

    -- Human-readable AQI band.
    -- 'Good' (0–50) | 'Moderate' (51–100) | 'Unhealthy for Sensitive Groups' (101–150)
    -- | 'Unhealthy' (151–200) | 'Very Unhealthy' (201–300) | 'Hazardous' (301–500)
    aqi_category        TEXT        CHECK (aqi_category IN (
                            'Good',
                            'Moderate',
                            'Unhealthy for Sensitive Groups',
                            'Unhealthy',
                            'Very Unhealthy',
                            'Hazardous'
                        )),

    -- Heat Index in °C: perceived temperature accounting for humidity.
    -- Rothfusz regression equation used when T ≥ 27 °C and RH ≥ 40 %.
    heat_index_c        DOUBLE PRECISION,

    -- Toxic Gas Index: composite 0–100 score combining normalised CO PPM and
    -- MQ135 reading.  Higher = more dangerous.
    -- Formula (example): 0.6 × (co_ppm / 50) × 100  +  0.4 × (co2_ppm / 2000) × 100
    -- Capped at 100.
    toxic_gas_index     DOUBLE PRECISION   CHECK (toxic_gas_index BETWEEN 0 AND 100),

    -- Respiratory Risk Label derived from PM2.5 concentration:
    --   'Low'      : PM2.5 ≤ 12.0 µg/m³
    --   'Moderate'  : 12.1 – 35.4 µg/m³
    --   'High'      : 35.5 – 55.4 µg/m³
    --   'Very High' : 55.5 – 150.4 µg/m³
    --   'Severe'    : > 150.4 µg/m³
    respiratory_risk_label TEXT     CHECK (respiratory_risk_label IN (
                            'Low', 'Moderate', 'High', 'Very High', 'Severe'
                        )),

    -- ── Movement (Calculated from Sequential GPS Points) ────────────────────
    -- Speed in km/h: haversine distance to previous point ÷ time delta.
    -- NULL for the first reading of a device session.
    speed_kmh           DOUBLE PRECISION   DEFAULT 0,

    -- Distance in metres moved since the previous reading for this device.
    distance_moved_m    DOUBLE PRECISION   DEFAULT 0,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dashboard queries: latest readings per device.
CREATE INDEX IF NOT EXISTS idx_processed_device_time
    ON processed_data (device_id, recorded_at DESC);

-- Map tile queries: filter by bounding box / time window.
CREATE INDEX IF NOT EXISTS idx_processed_location
    ON processed_data USING GIST (location);

-- AQI-based alerting / filtering.
CREATE INDEX IF NOT EXISTS idx_processed_aqi
    ON processed_data (aqi_value DESC);

-- Back-reference lookup (ensure 1:1 with raw_telemetry).
CREATE UNIQUE INDEX IF NOT EXISTS idx_processed_raw_ref
    ON processed_data (raw_telemetry_id);

COMMENT ON TABLE  processed_data IS 'Calibrated, enriched sensor data — the single source of truth for the frontend dashboard.';
COMMENT ON COLUMN processed_data.pm25_ugm3          IS 'PM2.5 in µg/m³ after applying per-device dust_calibration factor.';
COMMENT ON COLUMN processed_data.aqi_value           IS 'US EPA AQI (0–500), computed from dominant pollutant breakpoints.';
COMMENT ON COLUMN processed_data.heat_index_c        IS 'Perceived temperature (°C) via Rothfusz regression from T + RH.';
COMMENT ON COLUMN processed_data.toxic_gas_index     IS 'Composite 0–100 danger score from CO + MQ135 gas levels.';
COMMENT ON COLUMN processed_data.respiratory_risk_label IS 'Risk tier (Low → Severe) derived from PM2.5 EPA breakpoints.';
COMMENT ON COLUMN processed_data.speed_kmh           IS 'Calculated km/h from haversine Δ between sequential GPS fixes ÷ Δt.';
COMMENT ON COLUMN processed_data.distance_moved_m    IS 'Haversine distance in metres from the previous GPS fix for this device.';
COMMENT ON COLUMN processed_data.gps_fallback_used   IS 'TRUE when raw GPS was (0,0) and devices.static_location was substituted.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 4. identified_hotspots — Geospatial Pollution Zones
-- ─────────────────────────────────────────────────────────────────────────────
-- A hotspot is a circular zone (centre + radius) where pollution has been
-- persistently elevated.  The Python processing layer creates or updates rows
-- here when multiple processed_data readings within a geographic cluster
-- exceed threshold values over a sliding time window.
--
-- The frontend renders these as coloured circles on the map layer.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS identified_hotspots (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Centre of the hotspot zone.
    latitude            DOUBLE PRECISION   NOT NULL,
    longitude           DOUBLE PRECISION   NOT NULL,

    -- PostGIS point for spatial joins / proximity queries.
    location            GEOGRAPHY(POINT, 4326),

    -- Radius in metres defining the extent of the hotspot zone.
    radius_m            DOUBLE PRECISION   NOT NULL DEFAULT 100,

    -- Severity level drives map colouring and alert priority.
    -- 'low' | 'moderate' | 'high' | 'critical'
    severity_level      TEXT        NOT NULL DEFAULT 'moderate'
                        CHECK (severity_level IN ('low', 'moderate', 'high', 'critical')),

    -- The dominant pollutant responsible for the hotspot flag.
    -- e.g., 'PM2.5', 'CO', 'CO2', 'Toxic Gas Mix'
    primary_pollutant   TEXT        NOT NULL,

    -- Representative pollutant concentration (in its native unit) at time of
    -- last update — gives the frontend a number to display.
    peak_value          DOUBLE PRECISION,

    -- Corresponding AQI value for the peak reading (convenience column).
    peak_aqi            INTEGER,

    -- Number of distinct processed_data readings that contributed to this
    -- hotspot determination (confidence proxy).
    contributing_readings INTEGER   NOT NULL DEFAULT 1,

    -- Time window over which the hotspot was observed.
    first_detected_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- When the hotspot was resolved / pollution returned to normal.
    -- NULL = still active.
    resolved_at         TIMESTAMPTZ,

    -- Active flag for quick filtering (redundant with resolved_at but faster).
    is_active           BOOLEAN     NOT NULL DEFAULT TRUE
);

-- Map rendering: find all active hotspots quickly.
CREATE INDEX IF NOT EXISTS idx_hotspots_active
    ON identified_hotspots (is_active)
    WHERE is_active = TRUE;

-- Spatial clustering / overlap detection.
CREATE INDEX IF NOT EXISTS idx_hotspots_location
    ON identified_hotspots USING GIST (location);

COMMENT ON TABLE  identified_hotspots IS 'Circular pollution zones detected by clustering elevated readings over a sliding time window.';
COMMENT ON COLUMN identified_hotspots.radius_m           IS 'Zone radius in metres – defines the geographic extent of the hotspot.';
COMMENT ON COLUMN identified_hotspots.severity_level     IS 'Alert tier: low | moderate | high | critical.';
COMMENT ON COLUMN identified_hotspots.primary_pollutant  IS 'Dominant pollutant causing the hotspot (PM2.5, CO, CO2, Toxic Gas Mix).';
COMMENT ON COLUMN identified_hotspots.contributing_readings IS 'Count of processed_data rows backing this hotspot (confidence metric).';
COMMENT ON COLUMN identified_hotspots.resolved_at        IS 'NULL while active; set to a timestamp when pollution drops below threshold.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 5. community_reports — Citizen Science / Crowdsourced Observations
-- ─────────────────────────────────────────────────────────────────────────────
-- Allows residents to flag subjective environmental issues (odours, visible
-- smoke, excessive noise) that sensors may not fully capture.
-- A verification_score gamification system lets other users upvote reports,
-- surfacing credible observations.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS community_reports (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Optional FK to a Supabase Auth user.  NULL = anonymous report.
    reporter_id         UUID,

    -- Report category.
    report_type         TEXT        NOT NULL
                        CHECK (report_type IN (
                            'Smell', 'Smoke', 'Noise', 'Dust',
                            'Chemical Spill', 'Water Pollution', 'Other'
                        )),

    -- Free-text description of the observation.
    description         TEXT,

    -- Location where the issue was observed.
    latitude            DOUBLE PRECISION   NOT NULL,
    longitude           DOUBLE PRECISION   NOT NULL,
    location            GEOGRAPHY(POINT, 4326),

    -- Optional photo evidence (Supabase Storage URL).
    image_url           TEXT,

    -- ── Gamification / Verification ─────────────────────────────────────────
    -- Net score from community upvotes/downvotes.
    -- Higher score = more trustworthy report.
    verification_score  INTEGER     NOT NULL DEFAULT 0,

    -- Moderation status: 'pending' | 'verified' | 'rejected'
    status              TEXT        NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'verified', 'rejected')),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Show recent / nearby reports on the map.
CREATE INDEX IF NOT EXISTS idx_community_reports_location
    ON community_reports USING GIST (location);

CREATE INDEX IF NOT EXISTS idx_community_reports_type_time
    ON community_reports (report_type, created_at DESC);

COMMENT ON TABLE  community_reports IS 'Crowdsourced environmental observations with upvote-based verification.';
COMMENT ON COLUMN community_reports.verification_score IS 'Net upvotes – used for gamification and to surface credible reports.';
COMMENT ON COLUMN community_reports.image_url          IS 'URL to photo evidence stored in Supabase Storage bucket.';


-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Helper: auto-update `updated_at` trigger
-- ─────────────────────────────────────────────────────────────────────────────
-- Keeps `updated_at` columns in sync automatically on UPDATE statements.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_community_reports_updated_at
    BEFORE UPDATE ON community_reports
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


-- ─────────────────────────────────────────────────────────────────────────────
-- 7. Row Level Security (RLS) — Supabase Best Practice
-- ─────────────────────────────────────────────────────────────────────────────
-- Enable RLS on all tables.  Policies below are starter examples;
-- tighten them for production based on your auth model.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE devices              ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_telemetry        ENABLE ROW LEVEL SECURITY;
ALTER TABLE processed_data       ENABLE ROW LEVEL SECURITY;
ALTER TABLE identified_hotspots  ENABLE ROW LEVEL SECURITY;
ALTER TABLE community_reports    ENABLE ROW LEVEL SECURITY;

-- Public read access for the dashboard (anon role).
CREATE POLICY "Public read processed_data"
    ON processed_data FOR SELECT
    USING (true);

CREATE POLICY "Public read identified_hotspots"
    ON identified_hotspots FOR SELECT
    USING (true);

CREATE POLICY "Public read community_reports"
    ON community_reports FOR SELECT
    USING (true);

-- Devices & raw_telemetry are internal — only the service_role key may write.
-- (Supabase service_role bypasses RLS by default, so no explicit INSERT
-- policy is needed for the Python worker / ESP32 ingestion endpoints.)

-- Allow authenticated users to submit community reports.
CREATE POLICY "Authenticated users can insert community_reports"
    ON community_reports FOR INSERT
    WITH CHECK (auth.uid() IS NOT NULL);

-- Allow users to update only their own reports.
CREATE POLICY "Users can update own community_reports"
    ON community_reports FOR UPDATE
    USING (auth.uid() = reporter_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- 8. Realtime — Enable Supabase Realtime for live dashboard updates
-- ─────────────────────────────────────────────────────────────────────────────
-- Supabase Realtime listens to Postgres logical replication.
-- Adding tables to the `supabase_realtime` publication pushes INSERT/UPDATE
-- events to connected WebSocket clients.
-- ─────────────────────────────────────────────────────────────────────────────

-- Note: On Supabase hosted projects the publication already exists.
-- If running locally you may need: CREATE PUBLICATION supabase_realtime;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime'
    ) THEN
        CREATE PUBLICATION supabase_realtime;
    END IF;
END $$;

ALTER PUBLICATION supabase_realtime ADD TABLE processed_data;
ALTER PUBLICATION supabase_realtime ADD TABLE identified_hotspots;
ALTER PUBLICATION supabase_realtime ADD TABLE community_reports;


-- ─────────────────────────────────────────────────────────────────────────────
-- 9. alerts — Threshold-Based Environmental Alerts
-- ─────────────────────────────────────────────────────────────────────────────
-- Generated by the Python backend when sensor values exceed thresholds.
-- The frontend polls this table to show popup / banner alerts.
-- Later: trigger email / SMS via Supabase Edge Functions.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Alert classification
    -- 'aqi'           - AQI exceeded threshold
    -- 'pm25'          - PM2.5 spike
    -- 'co'            - Carbon monoxide danger
    -- 'heat'          - Heat index warning
    -- 'toxic_gas'     - Toxic gas index high
    -- 'respiratory'   - Respiratory risk escalation
    alert_type      TEXT        NOT NULL
                    CHECK (alert_type IN (
                        'aqi', 'pm25', 'co', 'heat', 'toxic_gas', 'respiratory'
                    )),

    -- Severity drives UI colour and notification urgency
    -- 'info' | 'warning' | 'danger' | 'critical'
    severity        TEXT        NOT NULL DEFAULT 'warning'
                    CHECK (severity IN ('info', 'warning', 'danger', 'critical')),

    -- Human-readable title shown in popup header
    title           TEXT        NOT NULL,

    -- Detailed message body for the popup / notification
    message         TEXT        NOT NULL,

    -- The metric value that triggered the alert
    trigger_value   DOUBLE PRECISION,

    -- The threshold that was exceeded
    threshold_value DOUBLE PRECISION,

    -- Location where the alert was triggered (zone center)
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    location        GEOGRAPHY(POINT, 4326),

    -- Which zone (if geohash-based) triggered it
    zone_id         TEXT,

    -- Optional back-reference to the device that produced the reading
    device_id       TEXT        REFERENCES devices (device_id),

    -- Has the alert been acknowledged / dismissed by a user?
    acknowledged    BOOLEAN     NOT NULL DEFAULT FALSE,

    -- Is the alert still active (condition still true)?
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,

    -- Timestamps
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Active alerts query (dashboard polls this)
CREATE INDEX IF NOT EXISTS idx_alerts_active
    ON alerts (is_active, triggered_at DESC)
    WHERE is_active = TRUE;

-- Per-type filtering
CREATE INDEX IF NOT EXISTS idx_alerts_type
    ON alerts (alert_type, triggered_at DESC);

-- Spatial alerts
CREATE INDEX IF NOT EXISTS idx_alerts_location
    ON alerts USING GIST (location);

COMMENT ON TABLE  alerts IS 'Threshold-triggered environmental alerts for dashboard popups and future email/SMS.';
COMMENT ON COLUMN alerts.alert_type     IS 'Category: aqi | pm25 | co | heat | toxic_gas | respiratory.';
COMMENT ON COLUMN alerts.severity       IS 'Urgency tier: info | warning | danger | critical.';
COMMENT ON COLUMN alerts.trigger_value  IS 'The actual sensor/index value that crossed the threshold.';
COMMENT ON COLUMN alerts.threshold_value IS 'The threshold that was exceeded.';
COMMENT ON COLUMN alerts.zone_id        IS 'Geohash or zone identifier linking to a bubble zone.';


-- RLS for alerts
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- Public read (dashboard needs to see alerts)
CREATE POLICY "Public read alerts"
    ON alerts FOR SELECT
    USING (true);

-- Backend can insert/update alerts (service_role bypasses anyway, but explicit)
CREATE POLICY "Backend can insert alerts"
    ON alerts FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "Backend can update alerts"
    ON alerts FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

-- Add alerts to realtime
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;


-- =============================================================================
-- Done.  Summary of tables created:
-- -----------------------------------------------------------------------------
--  Table                 | Purpose
-- -----------------------+-----------------------------------------------------
--  devices               | Node registry, per-unit calibration, GPS fallback
--  raw_telemetry         | Append-only raw ESP32 readings (staging)
--  processed_data        | Calibrated & enriched data for the dashboard
--  identified_hotspots   | Persistent pollution zones (centre + radius)
--  community_reports     | Citizen-submitted environmental observations
--  alerts                | Threshold-based environmental alerts & popups
-- =============================================================================
