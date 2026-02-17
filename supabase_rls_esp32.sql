-- =============================================================================
-- RLS policies to allow ESP32 devices to insert data directly via anon key
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New Query)
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Allow anon role to SELECT and INSERT into devices
--    (ESP32 needs to auto-register / check if device exists)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE POLICY "ESP32 can read devices"
    ON devices FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "ESP32 can register devices"
    ON devices FOR INSERT
    TO anon
    WITH CHECK (true);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Allow anon role to INSERT into raw_telemetry
--    (ESP32 sends raw sensor data here; processing happens server-side)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE POLICY "ESP32 can insert raw_telemetry"
    ON raw_telemetry FOR INSERT
    TO anon
    WITH CHECK (true);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Allow service role (Python processor) to do everything
--    (service_role bypasses RLS by default, but if you need explicit):
-- ─────────────────────────────────────────────────────────────────────────────

-- The Python backend uses the anon key currently. Let's also allow it to
-- read raw_telemetry and update the processed flag:

CREATE POLICY "Backend can read raw_telemetry"
    ON raw_telemetry FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "Backend can update raw_telemetry processed flag"
    ON raw_telemetry FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);

-- Allow backend to insert and read processed_data
CREATE POLICY "Backend can insert processed_data"
    ON processed_data FOR INSERT
    TO anon
    WITH CHECK (true);

-- Allow backend to manage hotspots
CREATE POLICY "Backend can insert hotspots"
    ON identified_hotspots FOR INSERT
    TO anon
    WITH CHECK (true);

CREATE POLICY "Backend can update hotspots"
    ON identified_hotspots FOR UPDATE
    TO anon
    USING (true)
    WITH CHECK (true);


-- =============================================================================
-- Done! Now the ESP32 can POST directly to:
--   https://vwvnrqtakrgnnjbvkkhr.supabase.co/rest/v1/raw_telemetry
-- with the anon key in the headers.
-- =============================================================================
