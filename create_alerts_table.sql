-- =============================================================================
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- Creates the 'alerts' table for threshold-based environmental notifications
-- =============================================================================

CREATE TABLE IF NOT EXISTS alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type      TEXT        NOT NULL CHECK (alert_type IN ('aqi', 'pm25', 'co', 'heat', 'toxic_gas', 'respiratory')),
    severity        TEXT        NOT NULL DEFAULT 'warning' CHECK (severity IN ('info', 'warning', 'danger', 'critical')),
    title           TEXT        NOT NULL,
    message         TEXT        NOT NULL,
    trigger_value   DOUBLE PRECISION,
    threshold_value DOUBLE PRECISION,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    zone_id         TEXT,
    device_id       TEXT        REFERENCES devices (device_id),
    acknowledged    BOOLEAN     NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    acknowledged_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_alerts_active ON alerts (is_active, triggered_at DESC) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts (alert_type, triggered_at DESC);

-- RLS
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read alerts" ON alerts FOR SELECT USING (true);
CREATE POLICY "Backend can insert alerts" ON alerts FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Backend can update alerts" ON alerts FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
