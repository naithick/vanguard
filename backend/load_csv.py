"""
GreenRoute Mesh - CSV Data Loader
Load existing ESP32 CSV data into Supabase

Usage:
    python load_csv.py ../ESP32_Air_Quality_Data.csv
"""

import sys
import os
import pandas as pd
from datetime import datetime, timezone
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import device_defaults
from supabase_client import db
from processor import processor

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('greenroute.loader')


def load_csv_to_supabase(csv_path: str, device_id: str = "esp32-vanguard-001"):
    """
    Load CSV data into Supabase
    
    CSV columns expected:
    Dust, MQ135, MQ7, Temperature, Humidity, Pressure, Gas, Latitude, Longitude
    """
    log.info(f"Loading {csv_path}")
    
    # Read CSV (handle encoding issues from special chars like °C, Ω, etc.)
    df = pd.read_csv(csv_path, encoding='latin-1')
    log.info(f"Found {len(df)} rows")
    
    # First, register the device
    log.info(f"Registering device: {device_id}")
    device = db.get_or_create_device(
        device_id=device_id,
        name="ESP32 Vanguard Node 1"
    )
    
    if not device:
        log.error("Failed to register device")
        return
    
    log.info(f"Device registered: {device.get('id')}")
    
    # Normalise column names (the CSV uses e.g. "Temperature (°C)")
    df.columns = df.columns.str.strip()
    rename_map = {}
    for col in df.columns:
        lower = col.lower()
        if 'dust' in lower:
            rename_map[col] = 'Dust'
        elif 'mq135' in lower:
            rename_map[col] = 'MQ135'
        elif 'mq7' in lower:
            rename_map[col] = 'MQ7'
        elif 'temperature' in lower or 'temp' in lower:
            rename_map[col] = 'Temperature'
        elif 'humidity' in lower:
            rename_map[col] = 'Humidity'
        elif 'pressure' in lower:
            rename_map[col] = 'Pressure'
        elif 'gas' in lower and 'resistance' not in lower:
            rename_map[col] = 'Gas'
        elif 'latitude' in lower or 'lat' in lower:
            rename_map[col] = 'Latitude'
        elif 'longitude' in lower or 'lon' in lower:
            rename_map[col] = 'Longitude'
    df.rename(columns=rename_map, inplace=True)
    log.info(f"Columns after rename: {list(df.columns)}")

    # Map CSV columns to telemetry format
    column_map = {
        'Dust': 'dust',
        'MQ135': 'mq135', 
        'MQ7': 'mq7',
        'Temperature': 'temperature',
        'Humidity': 'humidity',
        'Pressure': 'pressure',
        'Gas': 'gas',
        'Latitude': 'latitude',
        'Longitude': 'longitude'
    }
    
    processed_count = 0
    error_count = 0
    
    for idx, row in df.iterrows():
        try:
            # Build telemetry data
            data = {}
            for csv_col, api_col in column_map.items():
                if csv_col in row:
                    data[api_col] = row[csv_col] if pd.notna(row[csv_col]) else None
            
            # Insert raw telemetry
            raw_result = db.insert_raw_telemetry(device_id, data)
            
            if raw_result:
                # Immediately process it
                processed = processor.process_raw_telemetry(raw_result, device)
                db.insert_processed_data(processed)
                db.mark_telemetry_processed(raw_result['id'])
                processed_count += 1
                
                if processed_count % 100 == 0:
                    log.info(f"Processed {processed_count}/{len(df)} rows...")
            
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                log.error(f"Row {idx} error: {e}")
    
    log.info(f"Complete! Processed: {processed_count}, Errors: {error_count}")
    
    # Show stats
    stats = db.get_statistics()
    log.info(f"Database stats: {stats}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python load_csv.py <csv_file> [device_id]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    device_id = sys.argv[2] if len(sys.argv) > 2 else "esp32-vanguard-001"
    
    load_csv_to_supabase(csv_path, device_id)
