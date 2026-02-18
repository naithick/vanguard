"""
GreenRoute Mesh v2 — Configuration
Single source of truth for Supabase credentials, calibration defaults,
and processing constants.

Reads secrets from environment variables (or .env file via python-dotenv).
NEVER hardcode API keys here.
"""

import os
from dataclasses import dataclass
from pathlib import Path

# Load .env file if present (keeps secrets out of code)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv not installed — rely on env vars


@dataclass
class SupabaseConfig:
    """Supabase connection settings (service-role key bypasses RLS)."""
    url: str = os.environ.get("SUPABASE_URL", "")
    service_key: str = os.environ.get("SUPABASE_SERVICE_KEY", "")


@dataclass
class DeviceDefaults:
    """Default calibration factors for new / uncalibrated ESP32 nodes."""
    dust_calibration: float = 1.0
    mq135_calibration: float = 1.0
    mq7_calibration: float = 1.0
    # Fallback GPS (Bangalore centre)
    default_latitude: float = 12.9716
    default_longitude: float = 77.5946


@dataclass
class ProcessingConfig:
    """EPA AQI breakpoint tables used by the processor module."""

    # PM2.5 (µg/m³) → AQI
    pm25_breakpoints = [
        (0.0,   12.0,  0,   50),    # Good
        (12.1,  35.4,  51,  100),   # Moderate
        (35.5,  55.4,  101, 150),   # Unhealthy for Sensitive
        (55.5,  150.4, 151, 200),   # Unhealthy
        (150.5, 250.4, 201, 300),   # Very Unhealthy
        (250.5, 500.4, 301, 500),   # Hazardous
    ]

    # CO (ppm) → AQI
    co_breakpoints = [
        (0.0,  4.4,   0,   50),
        (4.5,  9.4,   51,  100),
        (9.5,  12.4,  101, 150),
        (12.5, 15.4,  151, 200),
        (15.5, 30.4,  201, 300),
        (30.5, 50.4,  301, 500),
    ]


# ── Global singletons ────────────────────────────────────────────────────────
supabase_config = SupabaseConfig()
device_defaults = DeviceDefaults()
processing_config = ProcessingConfig()
