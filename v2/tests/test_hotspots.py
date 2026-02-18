#!/usr/bin/env python3
"""
Test 4: Hotspot Detection & API
Tests detection trigger, listing, individual retrieval, and filtering.

Usage:  python tests/test_hotspots.py
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


def test_trigger_detection():
    section("Trigger Hotspot Detection")

    resp = api.post("/api/hotspots/detect", json_data={"lookback_hours": 72})
    data = resp.json()

    if resp.status_code == 200 and data.get("ok"):
        info(f"Detection returned: {data.get('message', '?')}")
        detected = data.get("detected", 0)
        resolved = data.get("resolved", 0)
        kv("Detected", detected)
        kv("Resolved", resolved)
        ok("Detection endpoint works")
        r.track(True)
    else:
        fail(f"Detection failed: {resp.status_code} {data}")
        r.track(False)


def test_list_all_hotspots():
    section("List All Hotspots")

    # All (active + resolved)
    resp = api.get("/api/hotspots", params={"include_resolved": "true"})
    data = resp.json()

    total = data.get("count", 0)
    kv("All hotspots", total)

    if resp.status_code == 200 and isinstance(data.get("hotspots"), list):
        ok("Listing works")
        r.track(True)
    else:
        fail(f"List failed: {resp.status_code}")
        r.track(False)

    # Show a few
    for h in data.get("hotspots", [])[:3]:
        loc = h.get("location", "?")
        aqi = h.get("peak_aqi", "?")
        active = "ACTIVE" if h.get("is_active") else "RESOLVED"
        info(f"  {loc}: AQI {aqi} [{active}]")

    return data.get("hotspots", [])


def test_list_active():
    section("List Active Hotspots")

    resp = api.get("/api/hotspots/active")
    data = resp.json()

    count = data.get("count", 0)
    kv("Active hotspots", count)

    # All returned should be active
    all_active = all(h.get("is_active", True) for h in data.get("hotspots", []))
    if all_active:
        ok("All returned hotspots are active")
        r.track(True)
    else:
        fail("Some returned hotspots are NOT active")
        r.track(False)


def test_get_single_hotspot(hotspots):
    section("Get Single Hotspot")

    if not hotspots:
        warn("No hotspots exist — nothing to retrieve")
        r.skip()
        return

    hid = hotspots[0].get("id")
    resp = api.get(f"/api/hotspots/{hid}")
    data = resp.json()

    if data.get("ok"):
        h = data["hotspot"]
        kv("ID", h.get("id"))
        kv("Location", h.get("location"))
        kv("Primary Pollutant", h.get("primary_pollutant"))
        kv("Peak AQI", h.get("peak_aqi"))
        kv("Severity", h.get("severity_level"))
        kv("Readings", h.get("contributing_readings"))
        ok("Single hotspot retrieval works")
        r.track(True)
    else:
        fail(f"Get hotspot failed: {data}")
        r.track(False)

    # Non-existent ID
    resp2 = api.get("/api/hotspots/00000000-0000-0000-0000-000000000000")
    if resp2.status_code == 404:
        ok("404 for non-existent hotspot")
        r.track(True)
    else:
        fail(f"Expected 404, got {resp2.status_code}")
        r.track(False)


def test_hotspot_summary():
    section("Hotspot Summary / Stats")

    resp = api.get("/api/hotspots")
    data = resp.json()

    if resp.status_code == 200:
        summary = data.get("summary", {})
        kv("Active count", summary.get("active", data.get("count", 0)))
        ok("Summary available")
        r.track(True)
    else:
        fail(f"Summary failed: {resp.status_code}")
        r.track(False)


if __name__ == "__main__":
    banner("Test: Hotspot Detection & API")
    print(f"  {DIM}Time:{RESET}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start = time.time()

    test_health()
    test_trigger_detection()
    hotspots = test_list_all_hotspots()
    test_list_active()
    test_get_single_hotspot(hotspots)
    test_hotspot_summary()

    kv("Duration", f"{time.time() - start:.2f}s")
    success = r.summary()
    sys.exit(0 if success else 1)
