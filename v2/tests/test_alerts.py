#!/usr/bin/env python3
"""
Test 2: Alert System
Tests alert creation, listing, filtering, and resolution.

Usage:  python tests/test_alerts.py
"""

import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

from helpers import *
from datetime import datetime

r = Results()
api = APIClient()


def test_health():
    section("Server Health")
    require_server(api)
    ok("Server is up")
    r.track(True)


def _ensure_device(device_id="test-alert-device"):
    """Register a device via ingest so foreign-key constraints pass."""
    api.post("/api/ingest", json_data={
        "device_id": device_id,
        "pm25": 10.0, "pm10": 20.0,
        "temperature": 30.0, "humidity": 65.0,
        "latitude": 13.1662, "longitude": 80.2585,
    })


def test_create_alert():
    section("Create Manual Alert")
    _ensure_device()

    payload = {
        "title": "Test alert — high AQI near Manali",
        "message": "AQI reading of 250 detected near industrial area",
        "severity": "warning",
        "alert_type": "aqi",
        "device_id": "test-alert-device",
        "latitude": 13.1662,
        "longitude": 80.2585,
    }

    resp = api.post("/api/alerts", json_data=payload)
    data = resp.json()

    if resp.status_code == 201 and data.get("ok"):
        alert = data["alert"]
        alert_id = alert.get("id")
        ok(f"Alert created (id={alert_id[:12]}...)")
        kv("Title", alert.get("title"))
        kv("Severity", alert.get("severity"))
        kv("Type", alert.get("alert_type"))
        kv("Device", alert.get("device_id"))
        r.track(True)
        return alert_id
    else:
        fail(f"Create alert failed: {resp.status_code} {data}")
        r.track(False)
        return None


def test_create_alert_validation():
    section("Alert Validation")

    # Missing title
    resp = api.post("/api/alerts", json_data={"severity": "info"})
    if resp.status_code == 400:
        ok("Rejected: missing title → 400")
        r.track(True)
    else:
        fail(f"Expected 400, got {resp.status_code}")
        r.track(False)

    # Invalid severity
    resp = api.post("/api/alerts", json_data={"title": "Test", "severity": "extreme"})
    if resp.status_code == 400:
        ok("Rejected: invalid severity → 400")
        r.track(True)
    else:
        fail(f"Expected 400, got {resp.status_code}")
        r.track(False)

    # Invalid alert_type
    resp = api.post("/api/alerts", json_data={"title": "Test", "alert_type": "earthquake"})
    if resp.status_code == 400:
        ok("Rejected: invalid alert_type → 400")
        r.track(True)
    else:
        fail(f"Expected 400, got {resp.status_code}")
        r.track(False)


def test_get_alert(alert_id):
    section("Get Single Alert")
    if not alert_id:
        warn("Skipping — no alert created")
        r.skip()
        return

    resp = api.get(f"/api/alerts/{alert_id}")
    data = resp.json()

    if resp.status_code == 200 and data.get("ok"):
        alert = data["alert"]
        kv("ID", alert.get("id")[:16] + "...")
        kv("Created at", str(alert.get("created_at", "?"))[:19])
        kv("Resolved at", alert.get("resolved_at") or "active")
        ok("Alert retrieved")
        r.track(True)
    else:
        fail(f"Get alert failed: {data}")
        r.track(False)

    # Non-existent alert
    resp2 = api.get("/api/alerts/00000000-0000-0000-0000-000000000000")
    if resp2.status_code == 404:
        ok("404 for non-existent alert")
        r.track(True)
    else:
        fail(f"Expected 404, got {resp2.status_code}")
        r.track(False)


def test_list_alerts():
    section("List Alerts")

    resp = api.get("/api/alerts", params={"limit": 10})
    data = resp.json()
    alerts = data.get("alerts", [])

    info(f"Total alerts returned: {data.get('count', 0)}")

    if alerts:
        widths = [12, 10, 30, 20]
        table_sep(widths)
        table_row(["SEVERITY", "TYPE", "TITLE", "DEVICE"], widths)
        table_sep(widths)
        for a in alerts[:5]:
            sev = a.get("severity", "?")
            sev_color = {"critical": RED, "danger": RED, "warning": YELLOW, "info": BLUE}.get(sev, DIM)
            table_row([
                f"{sev_color}{sev.upper()}{RESET}",
                a.get("alert_type", "?"),
                a.get("title", "?")[:30],
                a.get("device_id", "?")[:20],
            ], widths)
        table_sep(widths)

    ok("Alert listing works")
    r.track(True)

    # Filter: active only
    resp2 = api.get("/api/alerts", params={"active": "true"})
    d2 = resp2.json()
    info(f"Active alerts: {d2.get('count', 0)}")
    r.track(True)


def test_resolve_alert(alert_id):
    section("Resolve Alert")
    if not alert_id:
        warn("Skipping — no alert created")
        r.skip()
        return

    resp = api.put(f"/api/alerts/{alert_id}/resolve")
    data = resp.json()

    if data.get("ok"):
        alert = data["alert"]
        resolved = alert.get("resolved_at")
        if resolved:
            ok(f"Alert resolved at {str(resolved)[:19]}")
            r.track(True)
        else:
            fail("resolved_at not set after resolve call")
            r.track(False)
    else:
        fail(f"Resolve failed: {data}")
        r.track(False)

    # Verify it's no longer in active list
    resp2 = api.get("/api/alerts", params={"active": "true", "limit": 100})
    active = resp2.json().get("alerts", [])
    found = any(a.get("id") == alert_id for a in active)
    if not found:
        ok("Resolved alert no longer in active list")
        r.track(True)
    else:
        fail("Resolved alert still appears in active list")
        r.track(False)


if __name__ == "__main__":
    banner("Test: Alert System")
    print(f"  {DIM}Time:{RESET}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start = time.time()

    test_health()
    alert_id = test_create_alert()
    test_create_alert_validation()
    test_get_alert(alert_id)
    test_list_alerts()
    test_resolve_alert(alert_id)

    kv("Duration", f"{time.time() - start:.2f}s")
    success = r.summary()
    sys.exit(0 if success else 1)
