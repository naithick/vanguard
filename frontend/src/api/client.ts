/**
 * GreenRoute Mesh v2 — Frontend API Client
 * Matches the exact backend endpoints and processed_data schema.
 */

const API_BASE = 'http://localhost:5001/api';

// ── Interfaces ──────────────────────────────────────────────────────────────

/** A single processed reading — mirrors processor.py output exactly. */
export interface Reading {
    id?: string;
    raw_telemetry_id?: string;
    device_id: string;
    recorded_at: string;

    // Calibrated sensors
    pm25_ugm3: number;
    co2_ppm: number;
    co_ppm: number;
    temperature_c: number;
    humidity_pct: number;
    pressure_hpa: number;
    gas_resistance: number;

    // Location
    latitude: number;
    longitude: number;
    gps_fallback_used: boolean;

    // Derived metrics
    aqi_value: number;
    aqi_category: string;
    heat_index_c: number;
    toxic_gas_index: number;
    respiratory_risk_label: string;

    // Movement
    speed_kmh: number;
    distance_moved_m: number;

    // [SYNTHESIZED FIELDS]
    rssi?: number;
    battery_level?: number;
    weather_condition?: string;
}

/** A registered ESP32 device. */
export interface Device {
    device_id: string;
    name: string;
    status: string;
    static_latitude?: number;
    static_longitude?: number;
    dust_calibration?: number;
    mq135_calibration?: number;
    mq7_calibration?: number;
}

/** Device enriched with its most recent reading. */
export interface DeviceWithReading {
    device: Device;
    latest_reading: Reading | null;
}

/** Aggregate statistics from /api/stats. */
export interface Stats {
    device_count: number;
    total_readings: number;
    avg_aqi_recent: number;
    alert_count?: number;
    active_alert_count?: number;
    report_count?: number;
    open_report_count?: number;
    active_hotspot_count?: number;
    timestamp?: string;
    last_data_at?: string;
}

/** Health check response. */
export interface HealthStatus {
    status: string;
    service: string;
    timestamp: string;
    uptime_seconds?: number;
}

// ── API Client ──────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string): Promise<T | null> {
    try {
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    }
}

export const apiClient = {
    /** GET /api/readings — latest processed readings */
    async getReadings(limit = 100, deviceId?: string): Promise<Reading[]> {
        let url = `/readings?limit=${limit}`;
        if (deviceId) url += `&device_id=${deviceId}`;
        const json = await apiFetch<{ ok: boolean; data: Reading[]; count: number }>(url);
        return json?.data ?? [];
    },

    /** GET /api/devices — all registered devices with latest reading */
    async getDevices(): Promise<DeviceWithReading[]> {
        const json = await apiFetch<{ ok: boolean; devices: DeviceWithReading[]; count: number }>('/devices');
        return json?.devices ?? [];
    },

    /** GET /api/devices/:id — detailed device info + recent readings */
    async getDeviceInfo(deviceId: string): Promise<{
        device: Device;
        recent_readings: Reading[];
        readings_count: number;
    } | null> {
        return apiFetch(`/devices/${deviceId}`);
    },

    /** GET /api/devices/:id/latest — most recent reading for a device */
    async getDeviceLatest(deviceId: string): Promise<Reading | null> {
        const json = await apiFetch<{ ok: boolean; latest_reading: Reading }>(`/devices/${deviceId}/latest`);
        return json?.latest_reading ?? null;
    },

    /** GET /api/stats — aggregate statistics */
    async getStats(): Promise<Stats | null> {
        return apiFetch('/stats');
    },

    /** GET /api/health — backend health check */
    async getHealth(): Promise<HealthStatus | null> {
        return apiFetch('/health');
    },

    /** GET /api/zones — interpolated air-quality zones */
    async getZones(mode = 'heatmap', field = 'aqi_value', resolution = 30): Promise<any> {
        return apiFetch(`/zones?mode=${mode}&field=${field}&resolution=${resolution}`);
    },

    async getMonthlyHistory(year: number, month: number): Promise<any> {
        const json = await apiFetch<{ ok: boolean; data: any[] }>(`/readings/history/monthly?year=${year}&month=${month}`);
        return json?.data ?? [];
    },

    async getTrendAnalysis(): Promise<{ data: any[], analysis: any }> {
        const json = await apiFetch<{ ok: boolean; data: any[]; analysis: any }>('/analytics/trend');
        return { data: json?.data ?? [], analysis: json?.analysis };
    },

    // ── Hotspots ─────────────────────────────────────────────────────────────

    /** GET /api/hotspots/active — currently active hotspots */
    async getActiveHotspots(): Promise<any[]> {
        const json = await apiFetch<{ ok: boolean; hotspots: any[] }>('/hotspots/active');
        return json?.hotspots ?? [];
    },

    /** GET /api/hotspots — all hotspots (history) */
    async getHotspots(limit = 50): Promise<any[]> {
        const json = await apiFetch<{ ok: boolean; hotspots: any[] }>(`/hotspots?limit=${limit}`);
        return json?.hotspots ?? [];
    },

    /** POST /api/hotspots/detect — trigger detection manually */
    async triggerHotspotDetection(lookbackHours = 24): Promise<any> {
        // fetch with POST
        try {
            const res = await fetch(`${API_BASE}/hotspots/detect`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lookback_hours: lookbackHours })
            });
            return await res.json();
        } catch {
            return null;
        }
    },

    // ── Alerts ───────────────────────────────────────────────────────────────

    /** GET /api/alerts — list alerts */
    async getAlerts(activeOnly = true, limit = 50): Promise<any[]> {
        const json = await apiFetch<{ ok: boolean; alerts: any[] }>(`/alerts?active=${activeOnly}&limit=${limit}`);
        return json?.alerts ?? [];
    },

    // ── Reports ──────────────────────────────────────────────────────────────

    /** GET /api/reports — list user reports */
    async getReports(limit = 50, status?: string): Promise<any[]> {
        let url = `/reports?limit=${limit}`;
        if (status) url += `&status=${status}`;
        const json = await apiFetch<{ ok: boolean; reports: any[] }>(url);
        return json?.reports ?? [];
    },

    /** POST /api/reports — create report */
    async createReport(data: any): Promise<any> {
        try {
            const res = await fetch(`${API_BASE}/reports`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            return await res.json();
        } catch {
            return null;
        }
    },
};
