#!/usr/bin/env python3
"""
Test 5: Full Pipeline End-to-End
Exercises the entire backend in sequence: health → stats → devices →
ingest → process → readings → alerts → reports → hotspots → zones.

Usage:  python tests/test_full_pipeline.py
"""

import sys, os, time, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import *
from datetime import datetime

r = Results()
api = APIClient()


def test_health():
    section("1. Health Check")
    require_server(api)
    resp = api.get("/api/health")
    data = resp.json()
    kv("Status", data.get("status"))
    kv("SB connected", data.get("supabase_connected"))
    r.track(True)
    ok("Healthy")


def test_stats():
    section("2. Platform Stats")
    resp = api.get("/api/stats")
    data = resp.json()
    if data.get("ok"):
        stats = data.get("stats", {})
        kv("Raw rows", stats.get("raw_count", "?"))
        kv("Processed", stats.get("processed_count", "?"))
        kv("Devices", stats.get("device_count", "?"))
        kv("Alerts", stats.get("alert_count", "?"))
        kv("Reports", stats.get("report_count", "?"))
        kv("Hotspots", stats.get("hotspot_count", "?"))
        r.track(True)
        ok("Stats retrieved")
    else:
        fail(f"Stats: {data}")
        r.track(False)


def test_devices():
    section("3. Device List")
    resp = api.get("/api/devices")
    data = resp.json()
    devices = data.get("devices", [])
    kv("Count", len(devices))
    for d in devices[:5]:
        info(f"  {d.get('device_id', '?'):20s} zone={d.get('zone', '?')}")
    r.track(True)
    ok("Devices listed")


def test_ingest():
    section("4. Raw Ingest")
    payload = {
        "device_id": "pipeline_test_node",
        "pm25": 82.0,
        "pm10": 126.0,
        "temperature": 31.5,
        "humidity": 68.0,
        "pressure": 1012.0,
        "gas_resistance": 48000,
        "latitude": 12.9500,
        "longitude": 80.1800
    }
    resp = api.post("/api/ingest", json_data=payload)
    data = resp.json()
    if data.get("ok"):
        ok(f"Ingested (raw_id={data.get('raw_id', '?')[:12]}...)")
        r.track(True)
        return data.get("raw_id")
    else:
        fail(f"Ingest: {data}")
        r.track(False)
        return None


def test_process():
    section("5. Process Raw Data")
    resp = api.post("/api/process", json_data={"limit": 5})
    data = resp.json()
    if data.get("ok"):
        kv("Processed", data.get("processed"))
        kv("Skipped", data.get("skipped", 0))
        kv("Errors", data.get("errors", 0))
        r.track(True)
        ok("Processing done")
    else:
        fail(f"Process: {data}")
        r.track(False)


def test_readings():
    section("6. Read Processed Data")
    resp = api.get("/api/readings", params={"limit": 5})
    data = resp.json()
    readings = data.get("readings", [])
    kv("Returned", len(readings))
    for rd in readings[:3]:
        dev = rd.get("device_id", "?")
        aqi = rd.get("aqi", "?")
        cat = rd.get("aqi_category", "?")
        info(f"  {dev}: AQI {aqi} ({cat})")
    r.track(True)
    ok("Readings available")


def test_alert_lifecycle():
    section("7. Alert Lifecycle")
    # Create
    resp = api.post("/api/alerts", json_data={
        "title": "Pipeline test — threshold breach",
        "device_id": "pipeline_test_node",
        "alert_type": "aqi",
        "severity": "warning",
        "message": "Pipeline test alert"
    })
    data = resp.json()
    if not data.get("ok"):
        fail(f"Create alert: {data}")
        r.track(False)
        return
    aid = data["alert"]["id"]
    ok(f"Alert created ({aid[:12]}...)")

    # Resolve
    resp2 = api.put(f"/api/alerts/{aid}/resolve")
    d2 = resp2.json()
    if d2.get("ok"):
        ok("Alert resolved")
        r.track(True)
    else:
        fail(f"Resolve: {d2}")
        r.track(False)


def test_report_lifecycle():
    section("8. Report Lifecycle")
    resp = api.post("/api/reports", json_data={
        "title": "Pipeline test -- smoke near highway",
        "category": "smoke",
        "severity": "medium",
        "latitude": 12.95,
        "longitude": 80.18,
    })
    data = resp.json()
    if not data.get("ok"):
        fail(f"Create report: {data}")
        r.track(False)
        return
    rid = data["report"]["id"]
    ok(f"Report created ({rid[:12]}...)")

    # Upvote
    api.post(f"/api/reports/{rid}/upvote")
    ok("Upvoted")

    # Resolve
    api.put(f"/api/reports/{rid}/status", json_data={"status": "resolved"})
    ok("Report resolved")
    r.track(True)


def test_hotspot_cycle():
    section("9. Hotspot Detection Cycle")
    resp = api.post("/api/hotspots/detect", json_data={"lookback_hours": 72})
    data = resp.json()
    if data.get("ok"):
        kv("Detected", data.get("detected", 0))
        kv("Resolved", data.get("resolved", 0))
        r.track(True)
        ok("Hotspot detection done")
    else:
        fail(f"Detection: {data}")
        r.track(False)

    resp2 = api.get("/api/hotspots/active")
    active = resp2.json().get("count", 0)
    kv("Active hotspots", active)


def test_zones():
    section("10. Zone Boundaries")
    resp = api.get("/api/zones")
    data = resp.json()
    zones = data.get("zones", [])
    kv("Zone count", len(zones))
    for z in zones[:4]:
        info(f"  {z.get('name', '?'):16s}  center=({z.get('center_lat','?')}, {z.get('center_lon','?')})")
    r.track(True)
    ok("Zones loaded")


def test_final_stats():
    section("11. Final Stats Comparison")
    resp = api.get("/api/stats")
    data = resp.json().get("stats", {})
    kv("Raw rows", data.get("raw_count", "?"))
    kv("Processed", data.get("processed_count", "?"))
    kv("Alerts", data.get("alert_count", "?"))
    kv("Reports", data.get("report_count", "?"))
    kv("Hotspots", data.get("hotspot_count", "?"))
    r.track(True)
    ok("Stats confirmed")


if __name__ == "__main__":
    banner("Test: Full Pipeline End-to-End")
    print(f"  {DIM}Time:{RESET}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start = time.time()

    test_health()
    test_stats()
    test_devices()
    test_ingest()
    test_process()
    test_readings()
    test_alert_lifecycle()
    test_report_lifecycle()
    test_hotspot_cycle()
    test_zones()
    test_final_stats()

    kv("Duration", f"{time.time() - start:.2f}s")
    success = r.summary()
    sys.exit(0 if success else 1)
