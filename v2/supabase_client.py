"""
GreenRoute Mesh v2 — Supabase Client
Thin wrapper around supabase-py for the three core tables:
  devices · raw_telemetry · processed_data
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from supabase import create_client, Client
from config import supabase_config

log = logging.getLogger("greenroute.db")


class SupabaseClient:
    """All database operations live here."""

    def __init__(self):
        self.client: Client = create_client(
            supabase_config.url,
            supabase_config.service_key,
        )
        log.info(f"Supabase connected → {supabase_config.url}")

    # ─────────────────────────────────────────────────────────────────────
    # DEVICES
    # ─────────────────────────────────────────────────────────────────────

    def get_device(self, device_id: str) -> Optional[Dict]:
        """Look up a device by its string device_id."""
        res = (
            self.client.table("devices")
            .select("*")
            .eq("device_id", device_id)
            .execute()
        )
        return res.data[0] if res.data else None

    def register_device(
        self,
        device_id: str,
        name: str,
        static_lat: float = None,
        static_lon: float = None,
    ) -> Optional[Dict]:
        """Register a brand-new ESP32 node."""
        row = {"device_id": device_id, "name": name, "status": "active"}
        if static_lat and static_lon:
            row["static_latitude"] = static_lat
            row["static_longitude"] = static_lon
        res = self.client.table("devices").insert(row).execute()
        log.info(f"Registered device: {device_id}")
        return res.data[0] if res.data else None

    def get_or_create_device(self, device_id: str, name: str = None) -> Dict:
        """Return existing device or auto-register a new one."""
        device = self.get_device(device_id)
        if device:
            return device
        return self.register_device(device_id, name or f"ESP32-{device_id[:8]}")

    def get_all_devices(self) -> List[Dict]:
        """Fetch all registered devices."""
        res = self.client.table("devices").select("*").execute()
        return res.data

    # ─────────────────────────────────────────────────────────────────────
    # RAW TELEMETRY  (ESP32 → Supabase)
    # ─────────────────────────────────────────────────────────────────────

    def insert_raw_telemetry(self, device_id: str, data: Dict) -> Optional[Dict]:
        """
        Store exactly what the ESP32 sent.

        Expected keys in *data*:
            dust, mq135, mq7, temperature, humidity, pressure,
            gas, latitude, longitude
        """
        row = {
            "device_id": device_id,
            "raw_dust": data.get("dust"),
            "raw_mq135": data.get("mq135"),
            "raw_mq7": data.get("mq7"),
            "temperature_c": data.get("temperature"),
            "humidity_pct": data.get("humidity"),
            "pressure_hpa": data.get("pressure"),
            "gas_resistance": data.get("gas"),
            "raw_latitude": data.get("latitude", 0),
            "raw_longitude": data.get("longitude", 0),
            "processed": False,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        res = self.client.table("raw_telemetry").insert(row).execute()
        log.debug(f"Raw telemetry stored for {device_id}")
        return res.data[0] if res.data else None

    # ─────────────────────────────────────────────────────────────────────
    # RAW TELEMETRY — Processing helpers
    # ─────────────────────────────────────────────────────────────────────

    def get_unprocessed_telemetry(self, limit: int = 100) -> List[Dict]:
        """Fetch rows where processed = false, oldest first."""
        res = (
            self.client.table("raw_telemetry")
            .select("*, devices(*)")
            .eq("processed", False)
            .order("received_at", desc=False)
            .limit(limit)
            .execute()
        )
        return res.data

    def mark_telemetry_processed(self, telemetry_id: str) -> bool:
        """Flip processed → true for a given row."""
        res = (
            self.client.table("raw_telemetry")
            .update({"processed": True})
            .eq("id", telemetry_id)
            .execute()
        )
        return bool(res.data)

    # ─────────────────────────────────────────────────────────────────────
    # PROCESSED DATA
    # ─────────────────────────────────────────────────────────────────────

    def insert_processed_data(self, data: Dict) -> Optional[Dict]:
        """Write one enriched / calibrated row."""
        res = self.client.table("processed_data").insert(data).execute()
        log.debug(f"Processed data stored for {data.get('device_id')}")
        return res.data[0] if res.data else None

    def batch_insert_processed(self, rows: list) -> int:
        """Batch-upsert processed rows (chunks of 500, returning='minimal'). Returns count inserted."""
        if not rows:
            return 0
        total = 0
        CHUNK = 500
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i:i + CHUNK]
            self.client.table("processed_data").upsert(
                chunk, on_conflict="raw_telemetry_id",
                returning="minimal",
                default_to_null=True,
            ).execute()
            total += len(chunk)
        return total

    def batch_mark_processed(self, ids: list) -> int:
        """Mark multiple raw_telemetry rows as processed in one call per chunk."""
        if not ids:
            return 0
        total = 0
        CHUNK = 500
        for i in range(0, len(ids), CHUNK):
            chunk = ids[i:i + CHUNK]
            self.client.table("raw_telemetry").update(
                {"processed": True}
            ).in_("id", chunk).execute()
            total += len(chunk)
        return total

    def get_latest_processed(self, device_id: str = None, limit: int = 100) -> List[Dict]:
        """Most recent processed rows (optionally per device)."""
        q = self.client.table("processed_data").select("*")
        if device_id:
            q = q.eq("device_id", device_id)
        return q.order("recorded_at", desc=True).limit(limit).execute().data

    # ─────────────────────────────────────────────────────────────────────
    # STATISTICS  (lightweight)
    # ─────────────────────────────────────────────────────────────────────

    def get_statistics(self) -> Dict:
        """Quick summary counts for /api/stats."""
        devices = self.client.table("devices").select("id", count="exact").execute()
        processed = self.client.table("processed_data").select("id", count="exact").execute()

        latest = (
            self.client.table("processed_data")
            .select("aqi_value")
            .order("recorded_at", desc=True)
            .limit(100)
            .execute()
        )
        aqi_vals = [r["aqi_value"] for r in latest.data if r.get("aqi_value")]
        avg_aqi = round(sum(aqi_vals) / len(aqi_vals), 1) if aqi_vals else 0

        return {
            "device_count": devices.count or 0,
            "total_readings": processed.count or 0,
            "avg_aqi_recent": avg_aqi,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ─────────────────────────────────────────────────────────────────────
    # ALERTS
    # ─────────────────────────────────────────────────────────────────────

    def create_alert(self, data: Dict) -> Optional[Dict]:
        """Create a new alert (manual or auto-generated)."""
        row = {
            "device_id":  data.get("device_id"),
            "alert_type": data.get("alert_type", "aqi"),
            "severity":   data.get("severity", "warning"),
            "title":      data.get("title", "Air Quality Alert"),
            "message":    data.get("message", ""),
            "latitude":   data.get("latitude"),
            "longitude":  data.get("longitude"),
        }
        res = self.client.table("alerts").insert(row).execute()
        log.info(f"Alert created: {row['alert_type']} / {row['severity']}")
        return res.data[0] if res.data else None

    def get_alerts(
        self,
        active_only: bool = False,
        severity: str = None,
        alert_type: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Fetch alerts with optional filters."""
        q = self.client.table("alerts").select("*")
        if active_only:
            q = q.is_("resolved_at", "null")
        if severity:
            q = q.eq("severity", severity)
        if alert_type:
            q = q.eq("alert_type", alert_type)
        return q.order("created_at", desc=True).limit(limit).execute().data

    def get_alert(self, alert_id: str) -> Optional[Dict]:
        """Fetch a single alert by id."""
        res = self.client.table("alerts").select("*").eq("id", alert_id).execute()
        return res.data[0] if res.data else None

    def resolve_alert(self, alert_id: str) -> Optional[Dict]:
        """Mark an alert as resolved."""
        res = (
            self.client.table("alerts")
            .update({"resolved_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", alert_id)
            .execute()
        )
        log.info(f"Alert resolved: {alert_id}")
        return res.data[0] if res.data else None

    def get_active_alert_for_device(self, device_id: str, alert_type: str) -> Optional[Dict]:
        """Check if there's already an active (unresolved) alert of this type for this device."""
        res = (
            self.client.table("alerts")
            .select("*")
            .eq("device_id", device_id)
            .eq("alert_type", alert_type)
            .is_("resolved_at", "null")
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None

    # ─────────────────────────────────────────────────────────────────────
    # USER REPORTS  (anonymous, no login)
    # ─────────────────────────────────────────────────────────────────────

    def create_report(self, data: Dict) -> Optional[Dict]:
        """Create a new anonymous user report."""
        row = {
            "title":         data.get("title"),
            "description":   data.get("description", ""),
            "category":      data.get("category", "general"),
            "severity":      data.get("severity", "medium"),
            "latitude":      data.get("latitude"),
            "longitude":     data.get("longitude"),
            "reporter_name": data.get("reporter_name", "Anonymous"),
            "device_id":     data.get("device_id"),
            "station_name":  data.get("station_name"),
            "status":        "open",
            "upvotes":       0,
        }
        res = self.client.table("reports").insert(row).execute()
        log.info(f"Report created: {row['category']} — {row['title']}")
        return res.data[0] if res.data else None

    def get_reports(
        self,
        status: str = None,
        category: str = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Fetch reports with optional filters."""
        q = self.client.table("reports").select("*")
        if status:
            q = q.eq("status", status)
        if category:
            q = q.eq("category", category)
        return q.order("created_at", desc=True).limit(limit).execute().data

    def get_report(self, report_id: str) -> Optional[Dict]:
        """Fetch a single report by id."""
        res = self.client.table("reports").select("*").eq("id", report_id).execute()
        return res.data[0] if res.data else None

    def update_report_status(self, report_id: str, status: str) -> Optional[Dict]:
        """Update report status (open / investigating / resolved)."""
        update = {"status": status}
        if status == "resolved":
            update["resolved_at"] = datetime.now(timezone.utc).isoformat()
        res = (
            self.client.table("reports")
            .update(update)
            .eq("id", report_id)
            .execute()
        )
        log.info(f"Report {report_id} → {status}")
        return res.data[0] if res.data else None

    def upvote_report(self, report_id: str) -> Optional[Dict]:
        """Increment upvote count on a report."""
        report = self.get_report(report_id)
        if not report:
            return None
        new_count = (report.get("upvotes") or 0) + 1
        res = (
            self.client.table("reports")
            .update({"upvotes": new_count})
            .eq("id", report_id)
            .execute()
        )
        return res.data[0] if res.data else None


# ── Singleton ─────────────────────────────────────────────────────────────────
db = SupabaseClient()
