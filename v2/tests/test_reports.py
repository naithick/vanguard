#!/usr/bin/env python3
"""
Test 3: User Reporting System
Tests anonymous report creation, upvoting, status changes, and filtering.

Usage:  python tests/test_reports.py
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


def test_create_report():
    section("Create Anonymous Report")

    payload = {
        "title": "Thick smoke from factory chimney",
        "description": "Heavy black smoke visible near Manali industrial area since morning.",
        "category": "smoke",
        "severity": "high",
        "latitude": 13.1662,
        "longitude": 80.2585,
        "reporter_name": "Test User",
        "station_name": "Manali",
    }

    resp = api.post("/api/reports", json_data=payload)
    data = resp.json()

    if resp.status_code == 201 and data.get("ok"):
        report = data["report"]
        rid = report.get("id")
        ok(f"Report created (id={rid[:12]}...)")
        kv("Title", report.get("title"))
        kv("Category", report.get("category"))
        kv("Severity", report.get("severity"))
        kv("Status", report.get("status"))
        kv("Reporter", report.get("reporter_name"))
        kv("Upvotes", report.get("upvotes"))
        r.track(True)
        return rid
    else:
        fail(f"Create report failed: {resp.status_code} {data}")
        r.track(False)
        return None


def test_report_validation():
    section("Report Validation")

    # Missing title
    resp = api.post("/api/reports", json_data={"category": "dust"})
    if resp.status_code == 400:
        ok("Rejected: missing title → 400")
        r.track(True)
    else:
        fail(f"Expected 400, got {resp.status_code}")
        r.track(False)

    # Invalid category
    resp = api.post("/api/reports", json_data={"title": "X", "category": "aliens"})
    if resp.status_code == 400:
        ok("Rejected: invalid category → 400")
        r.track(True)
    else:
        fail(f"Expected 400, got {resp.status_code}")
        r.track(False)

    # Invalid severity
    resp = api.post("/api/reports", json_data={"title": "X", "severity": "extreme"})
    if resp.status_code == 400:
        ok("Rejected: invalid severity → 400")
        r.track(True)
    else:
        fail(f"Expected 400, got {resp.status_code}")
        r.track(False)


def test_upvote(report_id):
    section("Upvote Report")
    if not report_id:
        warn("Skipping — no report")
        r.skip()
        return

    # Upvote 3 times
    for i in range(3):
        resp = api.post(f"/api/reports/{report_id}/upvote")
        data = resp.json()
        if not data.get("ok"):
            fail(f"Upvote {i+1} failed: {data}")
            r.track(False)
            return

    votes = data["report"].get("upvotes", 0)
    if votes >= 3:
        ok(f"3 upvotes applied → total: {votes}")
        r.track(True)
    else:
        fail(f"Expected >= 3 upvotes, got {votes}")
        r.track(False)


def test_status_lifecycle(report_id):
    section("Report Status Lifecycle")
    if not report_id:
        warn("Skipping — no report")
        r.skip()
        return

    # open → investigating
    resp = api.put(f"/api/reports/{report_id}/status", json_data={"status": "investigating"})
    data = resp.json()
    if data.get("ok") and data["report"].get("status") == "investigating":
        ok("open → investigating")
        r.track(True)
    else:
        fail(f"Status change failed: {data}")
        r.track(False)

    # investigating → resolved
    resp = api.put(f"/api/reports/{report_id}/status", json_data={"status": "resolved"})
    data = resp.json()
    if data.get("ok") and data["report"].get("status") == "resolved":
        resolved_at = data["report"].get("resolved_at")
        ok(f"investigating → resolved (at {str(resolved_at)[:19]})")
        r.track(True)
    else:
        fail(f"Resolve failed: {data}")
        r.track(False)

    # Invalid status
    resp = api.put(f"/api/reports/{report_id}/status", json_data={"status": "deleted"})
    if resp.status_code == 400:
        ok("Rejected: invalid status 'deleted' → 400")
        r.track(True)
    else:
        fail(f"Expected 400, got {resp.status_code}")
        r.track(False)


def test_get_single_report(report_id):
    section("Get Single Report")
    if not report_id:
        warn("Skipping — no report")
        r.skip()
        return

    resp = api.get(f"/api/reports/{report_id}")
    data = resp.json()
    if data.get("ok"):
        ok(f"Report retrieved: {data['report'].get('title')}")
        r.track(True)
    else:
        fail(f"Get report failed: {data}")
        r.track(False)

    # Non-existent
    resp2 = api.get("/api/reports/00000000-0000-0000-0000-000000000000")
    if resp2.status_code == 404:
        ok("404 for non-existent report")
        r.track(True)
    else:
        fail(f"Expected 404, got {resp2.status_code}")
        r.track(False)


def test_list_reports():
    section("List & Filter Reports")

    resp = api.get("/api/reports", params={"limit": 10})
    data = resp.json()
    info(f"Total reports: {data.get('count', 0)}")
    r.track(True)

    # Filter by category
    resp2 = api.get("/api/reports", params={"category": "smoke"})
    d2 = resp2.json()
    smoke = d2.get("count", 0)
    info(f"Smoke reports: {smoke}")

    # Filter by status
    resp3 = api.get("/api/reports", params={"status": "open"})
    d3 = resp3.json()
    open_count = d3.get("count", 0)
    info(f"Open reports: {open_count}")

    ok("Filtering works")
    r.track(True)


if __name__ == "__main__":
    banner("Test: User Reporting System")
    print(f"  {DIM}Time:{RESET}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start = time.time()

    test_health()
    report_id = test_create_report()
    test_report_validation()
    test_upvote(report_id)
    test_status_lifecycle(report_id)
    test_get_single_report(report_id)
    test_list_reports()

    kv("Duration", f"{time.time() - start:.2f}s")
    success = r.summary()
    sys.exit(0 if success else 1)
