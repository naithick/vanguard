-- Run this in Supabase SQL Editor (Dashboard > SQL Editor > New Query)
-- Creates the reports table for anonymous user reporting

CREATE TABLE IF NOT EXISTS reports (
    id              uuid            DEFAULT gen_random_uuid() PRIMARY KEY,
    device_id       text,
    station_name    text,
    category        text            NOT NULL DEFAULT 'general',
    severity        text            NOT NULL DEFAULT 'medium',
    title           text            NOT NULL,
    description     text,
    latitude        double precision,
    longitude       double precision,
    reporter_name   text            DEFAULT 'Anonymous',
    status          text            NOT NULL DEFAULT 'open',
    upvotes         int             DEFAULT 0,
    created_at      timestamptz     DEFAULT now(),
    resolved_at     timestamptz
);

-- Enable Row Level Security but allow all operations (no login required)
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anonymous read"  ON reports FOR SELECT USING (true);
CREATE POLICY "Allow anonymous insert" ON reports FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow anonymous update" ON reports FOR UPDATE USING (true);

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (status);
CREATE INDEX IF NOT EXISTS idx_reports_category ON reports (category);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports (created_at DESC);
