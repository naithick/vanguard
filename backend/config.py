"""
GreenRoute Mesh - Configuration
Supabase credentials and settings
"""

import os
from dataclasses import dataclass

_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZ3dm5ycXRha3Jnbm5qYnZra2hyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTMyMDU3NCwiZXhwIjoyMDg2ODk2NTc0fQ.eaDkJG1BTZm_Dz0729iWEdPg6i5gq56CO6uFKYp3llE"

@dataclass
class SupabaseConfig:
    """Supabase connection configuration"""
    url: str = "https://vwvnrqtakrgnnjbvkkhr.supabase.co"
    # Service role key — bypasses RLS, use for backend operations
    service_key: str = _SERVICE_KEY
    # Alias for backward compatibility (also uses service key)
    anon_key: str = _SERVICE_KEY


@dataclass 
class DeviceDefaults:
    """Default calibration values for ESP32 devices"""
    dust_calibration: float = 1.0
    mq135_calibration: float = 1.0
    mq7_calibration: float = 1.0
    # Default location (Bangalore center)
    default_latitude: float = 12.9716
    default_longitude: float = 77.5946


@dataclass
class ProcessingConfig:
    """Data processing configuration"""
    # EPA AQI breakpoints for PM2.5 (µg/m³)
    pm25_breakpoints = [
        (0.0, 12.0, 0, 50),       # Good
        (12.1, 35.4, 51, 100),    # Moderate
        (35.5, 55.4, 101, 150),   # Unhealthy for Sensitive
        (55.5, 150.4, 151, 200),  # Unhealthy
        (150.5, 250.4, 201, 300), # Very Unhealthy
        (250.5, 500.4, 301, 500), # Hazardous
    ]
    
    # EPA AQI breakpoints for CO (ppm)
    co_breakpoints = [
        (0.0, 4.4, 0, 50),
        (4.5, 9.4, 51, 100),
        (9.5, 12.4, 101, 150),
        (12.5, 15.4, 151, 200),
        (15.5, 30.4, 201, 300),
        (30.5, 50.4, 301, 500),
    ]


# Global config instances
supabase_config = SupabaseConfig()
device_defaults = DeviceDefaults()
processing_config = ProcessingConfig()
