#!/usr/bin/env python3
"""
Test 1: Processing Pipeline
Tests the full ingest → process → read cycle.
Verifies sensor calibration, AQI calculation, imputation of NULL fields.

Usage:  python tests/test_processing.py
"""

import sys, os, random, time
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


def test_ingest_and_process():
    section("Ingest → Real-time Processing")

    payload = {
        "device_id": "test-proc-001",
        "dust":         round(random.uniform(20, 90), 1),
        "mq135":        round(random.uniform(400, 1100), 0),
        "mq7":          round(random.uniform(250, 650), 0),
        "temperature":  round(random.uniform(28, 36), 1),
        "humidity":     round(random.uniform(55, 85), 1),
        "pressure":     round(random.uniform(1005, 1018), 1),
        "gas":          round(random.uniform(15000, 70000), 0),
        "latitude":     13.0067 + random.uniform(-0.005, 0.005),
        "longitude":    80.2006 + random.uniform(-0.005, 0.005),
    }

    info("Sending simulated sensor reading:")
    for k, v in payload.items():
        kv(k, v, indent=6)
    print()

    resp = api.post("/api/ingest", json_data=payload)
    data = resp.json()

    if resp.status_code != 201 or not data.get("ok"):
        fail(f"Ingest failed: {resp.status_code} {data}")
        r.track(False)
        return None

    ok(f"Ingested (id={data.get('telemetry_id', '?')[:16]}...)")
    kv("Process status", data.get("process_status"))
    r.track(True)

    processed = data.get("processed")
    if not processed:
        warn("Row not processed inline (deferred or dropped)")
        r.track(data.get("process_status") == "dropped")
        return None

    return processed


def test_calibration(processed):
    section("Sensor Calibration Check")
    if not processed:
        warn("Skipping — no processed data")
        r.skip()
        return

    pm25 = processed.get("pm25_ugm3")
    co2 = processed.get("co2_ppm")
    co = processed.get("co_ppm")

    # PM2.5 should be > 0 and reasonable
    if pm25 is not None and 0 < pm25 < 1000:
        ok(f"PM2.5 = {pm25} µg/m³ (valid range)")
        r.track(True)
    else:
        fail(f"PM2.5 = {pm25} (unexpected)")
        r.track(False)

    # CO2 should be 400-5000
    if co2 is not None and 400 <= co2 <= 5000:
        ok(f"CO₂ = {co2} ppm (valid range)")
        r.track(True)
    else:
        fail(f"CO₂ = {co2} (unexpected)")
        r.track(False)

    # CO should be 0-1000
    if co is not None and 0 <= co <= 1000:
        ok(f"CO = {co} ppm (valid range)")
        r.track(True)
    else:
        fail(f"CO = {co} (unexpected)")
        r.track(False)


def test_aqi(processed):
    section("AQI Calculation")
    if not processed:
        warn("Skipping — no processed data")
        r.skip()
        return

    aqi = processed.get("aqi_value")
    cat = processed.get("aqi_category")

    if aqi is not None and 0 <= aqi <= 500:
        color = aqi_color(aqi)
        ok(f"AQI = {color}{aqi}{RESET} — {cat}")
        r.track(True)
    else:
        fail(f"AQI = {aqi}, category = {cat}")
        r.track(False)

    # Verify category matches AQI value
    expected_cats = {
        (0, 50): "Good", (51, 100): "Moderate",
        (101, 150): "Unhealthy for Sensitive Groups",
        (151, 200): "Unhealthy", (201, 300): "Very Unhealthy",
        (301, 500): "Hazardous",
    }
    for (lo, hi), expected_cat in expected_cats.items():
        if lo <= (aqi or 0) <= hi:
            if cat == expected_cat:
                ok(f"Category matches AQI range [{lo}-{hi}]")
                r.track(True)
            else:
                fail(f"Category mismatch: got '{cat}', expected '{expected_cat}' for AQI {aqi}")
                r.track(False)
            break


def test_derived_metrics(processed):
    section("Derived Metrics")
    if not processed:
        warn("Skipping — no processed data")
        r.skip()
        return

    # Heat index
    hi = processed.get("heat_index_c")
    if hi is not None:
        ok(f"Heat index = {hi}°C")
        r.track(True)
    else:
        fail("Heat index is NULL")
        r.track(False)

    # Toxic gas index (0-100)
    tgi = processed.get("toxic_gas_index")
    if tgi is not None and 0 <= tgi <= 100:
        ok(f"Toxic gas index = {tgi}/100")
        r.track(True)
    else:
        fail(f"Toxic gas index = {tgi} (expected 0-100)")
        r.track(False)

    # Respiratory risk label
    rr = processed.get("respiratory_risk_label")
    valid_labels = {"Low", "Moderate", "High", "Very High", "Severe"}
    if rr in valid_labels:
        ok(f"Respiratory risk = {rr}")
        r.track(True)
    else:
        fail(f"Respiratory risk = '{rr}' (unexpected)")
        r.track(False)


def test_null_imputation():
    section("NULL Imputation (weather fields)")

    # Ingest a reading with MISSING weather fields (like CPCB data)
    payload = {
        "device_id": "test-impute-001",
        "dust": 40.0,
        "mq135": 900,
        "mq7": 500,
        # NO temperature, humidity, pressure, gas — simulating CPCB gaps
        "latitude": 13.0, "longitude": 80.2,
    }

    resp = api.post("/api/ingest", json_data=payload)
    data = resp.json()

    if resp.status_code != 201:
        fail(f"Ingest failed: {data}")
        r.track(False)
        return

    processed = data.get("processed")
    if not processed:
        warn(f"Row status: {data.get('process_status')} — cannot verify imputation")
        r.skip()
        return

    # After imputation, these should NOT be NULL
    temp = processed.get("temperature_c")
    hum = processed.get("humidity_pct")
    pres = processed.get("pressure_hpa")
    hi = processed.get("heat_index_c")

    if temp is not None:
        ok(f"temperature_c imputed = {temp}°C (was NULL)")
        r.track(True)
    else:
        fail("temperature_c still NULL after imputation")
        r.track(False)

    if hum is not None:
        ok(f"humidity_pct imputed = {hum}% (was NULL)")
        r.track(True)
    else:
        fail("humidity_pct still NULL after imputation")
        r.track(False)

    if pres is not None:
        ok(f"pressure_hpa imputed = {pres} hPa (was NULL)")
        r.track(True)
    else:
        fail("pressure_hpa still NULL after imputation")
        r.track(False)

    if hi is not None:
        ok(f"heat_index_c computed = {hi}°C (from imputed values)")
        r.track(True)
    else:
        warn("heat_index_c still NULL (temp may be below threshold)")
        r.track(True)  # acceptable — heat index only triggers above 27°C


def test_readings_readback():
    section("Readings Read-back")
    resp = api.get("/api/readings", params={"device_id": "test-proc-001", "limit": 3})
    data = resp.json()
    readings = data.get("data", [])

    if readings:
        ok(f"Retrieved {len(readings)} reading(s) for test-proc-001")
        r.track(True)
    else:
        fail("No readings found for test device")
        r.track(False)


if __name__ == "__main__":
    banner("Test: Processing Pipeline")
    print(f"  {DIM}Time:{RESET}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    start = time.time()

    test_health()
    processed = test_ingest_and_process()
    test_calibration(processed)
    test_aqi(processed)
    test_derived_metrics(processed)
    test_null_imputation()
    test_readings_readback()

    kv("Duration", f"{time.time() - start:.2f}s")
    success = r.summary()
    sys.exit(0 if success else 1)
