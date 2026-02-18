"""
GreenRoute Mesh v2 — Hotspot Detection Engine

Identifies pollution hotspots from processed_data and writes them to
the identified_hotspots table in Supabase.

Table schema (identified_hotspots):
  id                    uuid PK
  latitude              double precision NOT NULL
  longitude             double precision NOT NULL
  location              geography(Point)
  radius_m              int  DEFAULT 100
  severity_level        text DEFAULT 'moderate'
  primary_pollutant     text NOT NULL
  peak_value            double precision
  peak_aqi              int
  contributing_readings int  DEFAULT 1
  first_detected_at     timestamptz
  last_updated_at       timestamptz
  resolved_at           timestamptz
  is_active             boolean DEFAULT true

Algorithm:
  1. Fetch recent processed readings (last N hours)
  2. Group by device / station
  3. Compute per-station statistics (avg AQI, peak AQI, peak PM2.5)
  4. Stations with avg AQI >= threshold AND enough readings → hotspot
  5. Upsert into identified_hotspots (match by lat/lon proximity)
  6. Auto-resolve hotspots where AQI has dropped below threshold
"""

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

log = logging.getLogger("greenroute.hotspots")

# ── Hotspot detection thresholds ──────────────────────────────────────────────
AQI_HOTSPOT_THRESHOLD = 100        # avg AQI above this → hotspot candidate
SUSTAINED_READINGS_MIN = 3         # need at least N readings to declare hotspot
LOOKBACK_HOURS = 24                # analyze data from the last N hours
RESOLVE_BELOW_AQI = 80            # auto-resolve if avg drops below this
HOTSPOT_RADIUS_M = 500             # default radius for a station-level hotspot


def _severity_from_aqi(avg_aqi: float) -> str:
    """Map average AQI to severity_level."""
    if avg_aqi >= 300:  return "critical"
    if avg_aqi >= 200:  return "severe"
    if avg_aqi >= 150:  return "high"
    if avg_aqi >= 100:  return "moderate"
    return "low"


def _primary_pollutant(pm25: float, co: float) -> str:
    """Determine which pollutant is driving the AQI."""
    if pm25 is not None and pm25 > 35.4:
        return "PM2.5"
    if co is not None and co > 9.4:
        return "CO"
    return "PM2.5"


def detect_hotspots(db, lookback_hours: int = LOOKBACK_HOURS) -> Dict:
    """
    Run hotspot detection on recent processed data.

    Returns {"created", "updated", "resolved", "active", "stations_analyzed"}
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()

    # ── 1. Fetch recent processed data ────────────────────────────────────
    try:
        res = (
            db.client.table("processed_data")
            .select("device_id, aqi_value, aqi_category, pm25_ugm3, co_ppm, "
                    "temperature_c, latitude, longitude, recorded_at")
            .gte("recorded_at", cutoff)
            .order("recorded_at", desc=True)
            .limit(5000)
            .execute()
        )
        readings = res.data
    except Exception as e:
        log.error(f"Hotspot detection: failed to fetch data: {e}")
        return {"error": str(e)}

    if not readings:
        log.info("Hotspot detection: no recent readings found")
        return {"created": 0, "updated": 0, "resolved": 0, "active": 0,
                "stations_analyzed": 0}

    # ── 2. Group by device ────────────────────────────────────────────────
    by_device: Dict[str, List[dict]] = defaultdict(list)
    for r in readings:
        if r.get("device_id") and r.get("aqi_value") is not None:
            by_device[r["device_id"]].append(r)

    # ── 3. Per-device stats ───────────────────────────────────────────────
    station_stats = {}
    for device_id, rows in by_device.items():
        aqi_vals = [r["aqi_value"] for r in rows if r["aqi_value"] is not None]
        pm25_vals = [r["pm25_ugm3"] for r in rows if r.get("pm25_ugm3") is not None]
        co_vals = [r["co_ppm"] for r in rows if r.get("co_ppm") is not None]

        if not aqi_vals:
            continue

        avg_aqi = sum(aqi_vals) / len(aqi_vals)
        above = sum(1 for v in aqi_vals if v >= AQI_HOTSPOT_THRESHOLD)
        latest = rows[0]

        station_stats[device_id] = {
            "avg_aqi":          round(avg_aqi, 1),
            "peak_aqi":         int(max(aqi_vals)),
            "avg_pm25":         round(sum(pm25_vals) / len(pm25_vals), 1) if pm25_vals else 0,
            "peak_pm25":        round(max(pm25_vals), 1) if pm25_vals else 0,
            "avg_co":           round(sum(co_vals) / len(co_vals), 2) if co_vals else 0,
            "peak_co":          round(max(co_vals), 2) if co_vals else 0,
            "total_readings":   len(aqi_vals),
            "above_threshold":  above,
            "latitude":         latest.get("latitude"),
            "longitude":        latest.get("longitude"),
            "first_seen":       rows[-1].get("recorded_at"),
            "last_seen":        rows[0].get("recorded_at"),
        }

    # ── 4. Get existing active hotspots ───────────────────────────────────
    try:
        existing_res = (
            db.client.table("identified_hotspots")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        existing_by_loc = {}
        for h in existing_res.data:
            key = f"{round(h['latitude'], 3)}_{round(h['longitude'], 3)}"
            existing_by_loc[key] = h
    except Exception as e:
        log.warning(f"Could not fetch existing hotspots: {e}")
        existing_by_loc = {}

    created = 0
    updated = 0
    resolved = 0
    active_locs = set()

    # ── 5. Create / update hotspots ───────────────────────────────────────
    for device_id, stats in station_stats.items():
        avg_aqi = stats["avg_aqi"]
        above = stats["above_threshold"]
        lat = stats["latitude"]
        lon = stats["longitude"]

        if lat is None or lon is None:
            continue

        is_hotspot = (avg_aqi >= AQI_HOTSPOT_THRESHOLD and above >= SUSTAINED_READINGS_MIN)
        if not is_hotspot:
            continue

        loc_key = f"{round(lat, 3)}_{round(lon, 3)}"
        active_locs.add(loc_key)

        severity = _severity_from_aqi(avg_aqi)
        pollutant = _primary_pollutant(stats["avg_pm25"], stats["avg_co"])
        peak_val = stats["peak_pm25"] if pollutant == "PM2.5" else stats["peak_co"]

        hotspot_row = {
            "latitude":              lat,
            "longitude":             lon,
            "radius_m":              HOTSPOT_RADIUS_M,
            "severity_level":        severity,
            "primary_pollutant":     pollutant,
            "peak_value":            peak_val,
            "peak_aqi":              stats["peak_aqi"],
            "contributing_readings": stats["total_readings"],
            "last_updated_at":       datetime.now(timezone.utc).isoformat(),
            "is_active":             True,
            "resolved_at":           None,
        }

        if loc_key in existing_by_loc:
            hs_id = existing_by_loc[loc_key]["id"]
            try:
                db.client.table("identified_hotspots").update(
                    hotspot_row
                ).eq("id", hs_id).execute()
                updated += 1
                log.info(f"Hotspot updated: {device_id} @ ({lat},{lon}) AQI={avg_aqi}")
            except Exception as e:
                log.error(f"Failed to update hotspot {device_id}: {e}")
        else:
            hotspot_row["first_detected_at"] = stats["first_seen"]
            try:
                db.client.table("identified_hotspots").insert(
                    hotspot_row
                ).execute()
                created += 1
                log.info(f"NEW HOTSPOT: {device_id} @ ({lat},{lon}) AQI={avg_aqi} [{severity}]")
            except Exception as e:
                log.error(f"Failed to create hotspot {device_id}: {e}")

    # ── 6. Auto-resolve improved hotspots ─────────────────────────────────
    for loc_key, hs in existing_by_loc.items():
        if loc_key not in active_locs:
            try:
                db.client.table("identified_hotspots").update({
                    "is_active":      False,
                    "resolved_at":    datetime.now(timezone.utc).isoformat(),
                    "last_updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", hs["id"]).execute()
                resolved += 1
                log.info(f"Hotspot resolved: ({hs['latitude']},{hs['longitude']})")
            except Exception as e:
                log.error(f"Failed to resolve hotspot: {e}")

    # Count active
    try:
        active_count = (
            db.client.table("identified_hotspots")
            .select("id", count="exact")
            .eq("is_active", True)
            .execute()
        ).count or 0
    except Exception:
        active_count = 0

    result = {
        "created": created,
        "updated": updated,
        "resolved": resolved,
        "active": active_count,
        "stations_analyzed": len(station_stats),
    }
    log.info(f"Hotspot detection complete: {result}")
    return result


def get_hotspot_summary(db) -> List[Dict]:
    """Get all active hotspots, sorted by peak AQI."""
    try:
        return (
            db.client.table("identified_hotspots")
            .select("*")
            .eq("is_active", True)
            .order("peak_aqi", desc=True)
            .execute()
        ).data
    except Exception as e:
        log.error(f"Failed to get hotspot summary: {e}")
        return []


def get_all_hotspots(db, include_resolved: bool = False, limit: int = 50) -> List[Dict]:
    """Get hotspots with optional resolved filter."""
    try:
        q = db.client.table("identified_hotspots").select("*")
        if not include_resolved:
            q = q.eq("is_active", True)
        return q.order("last_updated_at", desc=True).limit(limit).execute().data
    except Exception as e:
        log.error(f"Failed to get hotspots: {e}")
        return []


def get_hotspot(db, hotspot_id: str) -> Optional[Dict]:
    """Get a single hotspot by ID."""
    try:
        res = db.client.table("identified_hotspots").select("*").eq("id", hotspot_id).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        log.error(f"Failed to get hotspot {hotspot_id}: {e}")
        return None
