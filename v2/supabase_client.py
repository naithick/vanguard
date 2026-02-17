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


# ── Singleton ─────────────────────────────────────────────────────────────────
db = SupabaseClient()
