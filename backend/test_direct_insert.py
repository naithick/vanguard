"""
Test script: Simulate ESP32 sending data directly to Supabase REST API.

This proves the ESP32 can POST from ANY network to Supabase.
Run this AFTER applying supabase_rls_esp32.sql in the Supabase SQL Editor.

Usage:
    source .venv/bin/activate
    python backend/test_direct_insert.py
"""

import requests
import json
import sys
from datetime import datetime, timezone

# Supabase config (same as in config.py)
SUPABASE_URL = "https://vwvnrqtakrgnnjbvkkhr.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ3dm5ycXRha3Jnbm5qYnZra2hyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Mzk3ODU2NjUsImV4cCI6MjA1NTM2MTY2NX0.OnH0GoXAklwQlOBM4xv70LglFt5ophleeglvGVTdXYU"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

DEVICE_ID = "esp32-test-direct"


def test_device_registration():
    """Test registering a device via REST API (like ESP32 would)"""
    print("=" * 60)
    print("TEST 1: Device Registration via REST API")
    print("=" * 60)
    
    # Check if device exists
    url = f"{SUPABASE_URL}/rest/v1/devices?device_id=eq.{DEVICE_ID}&select=device_id"
    resp = requests.get(url, headers=HEADERS)
    
    if resp.status_code == 200 and resp.json():
        print(f"  [OK] Device '{DEVICE_ID}' already exists")
        return True
    
    # Register device
    url = f"{SUPABASE_URL}/rest/v1/devices"
    data = {
        "device_id": DEVICE_ID,
        "name": "Test Direct Insert Device",
        "status": "active",
        "static_latitude": 12.9716,
        "static_longitude": 77.5946,
        "description": "Test device for direct Supabase access"
    }
    
    resp = requests.post(url, headers=HEADERS, json=data)
    
    if resp.status_code in (200, 201):
        print(f"  [OK] Device registered: {DEVICE_ID}")
        return True
    else:
        print(f"  [FAIL] HTTP {resp.status_code}: {resp.text}")
        if resp.status_code == 403:
            print("\n  >>> RLS POLICY MISSING! Run supabase_rls_esp32.sql first <<<")
        return False


def test_raw_telemetry_insert():
    """Test inserting raw telemetry via REST API (like ESP32 would)"""
    print("\n" + "=" * 60)
    print("TEST 2: Raw Telemetry Insert via REST API")
    print("=" * 60)
    
    url = f"{SUPABASE_URL}/rest/v1/raw_telemetry"
    data = {
        "device_id": DEVICE_ID,
        "raw_dust": 42.5,
        "raw_mq135": 895.0,
        "raw_mq7": 575.0,
        "temperature_c": 29.0,
        "humidity_pct": 62.0,
        "pressure_hpa": 1012.5,
        "gas_resistance": 48000.0,
        "raw_latitude": 12.9750,
        "raw_longitude": 77.5900,
        "processed": False
    }
    
    resp = requests.post(url, headers=HEADERS, json=data)
    
    if resp.status_code in (200, 201):
        result = resp.json()
        row_id = result[0].get('id') if result else 'unknown'
        print(f"  [OK] Telemetry inserted! ID: {row_id}")
        return True
    else:
        print(f"  [FAIL] HTTP {resp.status_code}: {resp.text}")
        if resp.status_code == 403:
            print("\n  >>> RLS POLICY MISSING! Run supabase_rls_esp32.sql first <<<")
        return False


def test_read_processed():
    """Test reading processed data (dashboard would do this)"""
    print("\n" + "=" * 60)
    print("TEST 3: Read Processed Data (Dashboard)")
    print("=" * 60)
    
    url = f"{SUPABASE_URL}/rest/v1/processed_data?select=*&order=recorded_at.desc&limit=5"
    resp = requests.get(url, headers=HEADERS)
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"  [OK] Got {len(data)} processed rows")
        for row in data[:3]:
            print(f"      Device: {row.get('device_id')}, AQI: {row.get('aqi_value')}, "
                  f"Cat: {row.get('aqi_category')}")
        return True
    else:
        print(f"  [FAIL] HTTP {resp.status_code}: {resp.text}")
        return False


def main():
    print("\n" + "#" * 60)
    print("#  GreenRoute Mesh - Direct Supabase Access Test")
    print("#  Simulates ESP32 sending data over the internet")
    print("#" * 60)
    print(f"\nSupabase URL: {SUPABASE_URL}")
    print(f"Device ID:    {DEVICE_ID}")
    print(f"Timestamp:    {datetime.now(timezone.utc).isoformat()}\n")
    
    results = []
    
    results.append(("Device Registration", test_device_registration()))
    results.append(("Raw Telemetry Insert", test_raw_telemetry_insert()))
    results.append(("Read Processed Data", test_read_processed()))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False
    
    if all_pass:
        print("\n  All tests passed! ESP32 can send data directly to Supabase.")
        print("  Your friend can roam on any network — data goes straight to the cloud.\n")
    else:
        print("\n  Some tests FAILED. Likely causes:")
        print("  1. RLS policies not applied → Run supabase_rls_esp32.sql in Supabase SQL Editor")
        print("  2. Tables not created → Run schema.sql first")
        print("  3. Network issue → Check internet connection\n")
    
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
