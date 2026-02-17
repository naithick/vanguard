"""
GreenRoute Mesh - Data Processor
Converts raw ESP32 sensor readings into enriched processed data

Calculations:
- AQI (US EPA) from PM2.5 and CO
- Heat Index from temperature + humidity
- Toxic Gas Index from CO + MQ135
- Respiratory Risk Label from PM2.5
- Speed/Distance from GPS coordinates
"""

import math
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
import logging

from config import processing_config, device_defaults

log = logging.getLogger('greenroute.processor')


class DataProcessor:
    """Process raw sensor data into enriched readings"""
    
    # Cache for previous readings (for speed calculation)
    _previous_readings: Dict[str, Dict] = {}
    
    # =========================================================================
    # CALIBRATION
    # =========================================================================
    
    @staticmethod
    def calibrate_dust(raw_dust: float, calibration_factor: float = 1.0) -> float:
        """
        Convert raw dust spike count to PM2.5 µg/m³
        
        Raw sensor outputs 0-71 spike count.
        Calibration factor is device-specific from co-location testing.
        """
        if raw_dust is None:
            return None
        # Linear conversion with calibration
        # Typical: 1 spike ≈ 1-2 µg/m³ PM2.5
        pm25 = raw_dust * 1.5 * calibration_factor
        return round(pm25, 2)
    
    @staticmethod
    def calibrate_mq135(raw_adc: float, calibration_factor: float = 1.0) -> float:
        """
        Convert MQ135 ADC reading to CO2-equivalent PPM
        
        MQ135 responds to CO2, NH3, NOx, alcohol, benzene, smoke.
        We approximate CO2-equivalent using Rs/R0 log-log curve.
        
        Typical baseline: 890-915 ADC on 10-bit (clean air)
        """
        if raw_adc is None:
            return None
        
        # Rs/R0 ratio estimation (simplified)
        # R0 = sensor resistance in clean air
        # Typical: ADC 900 = ~400 PPM CO2 (ambient)
        r0_baseline = 900
        rs_r0 = raw_adc / r0_baseline
        
        # Log-log approximation for CO2-equivalent
        # PPM = 116.6020682 * (Rs/R0)^(-2.769034857)
        if rs_r0 > 0:
            co2_ppm = 116.6 * math.pow(rs_r0, -2.769) * calibration_factor
            co2_ppm = max(400, min(co2_ppm, 5000))  # Clamp to realistic range
        else:
            co2_ppm = 400
        
        return round(co2_ppm, 1)
    
    @staticmethod
    def calibrate_mq7(raw_adc: float, calibration_factor: float = 1.0) -> float:
        """
        Convert MQ7 ADC reading to CO PPM
        
        MQ7 is specifically for carbon monoxide detection.
        Typical baseline: 560-620 ADC on 10-bit (clean air)
        """
        if raw_adc is None:
            return None
        
        # Rs/R0 ratio estimation
        r0_baseline = 590
        rs_r0 = raw_adc / r0_baseline
        
        # Log-log approximation for CO
        # Based on MQ7 datasheet sensitivity curve
        if rs_r0 > 0:
            co_ppm = 99.042 * math.pow(rs_r0, -1.518) * calibration_factor
            co_ppm = max(0, min(co_ppm, 1000))  # Clamp
        else:
            co_ppm = 0
        
        return round(co_ppm, 2)
    
    # =========================================================================
    # AQI CALCULATION (US EPA)
    # =========================================================================
    
    @staticmethod
    def calculate_aqi(pm25: float, co_ppm: float) -> Tuple[int, str]:
        """
        Calculate US EPA AQI from PM2.5 and CO
        Returns: (aqi_value, aqi_category)
        
        Uses the higher of the two sub-indices as the final AQI.
        """
        def linear_aqi(concentration: float, breakpoints: list) -> int:
            """Linear interpolation within EPA breakpoint table"""
            for c_lo, c_hi, i_lo, i_hi in breakpoints:
                if c_lo <= concentration <= c_hi:
                    aqi = ((i_hi - i_lo) / (c_hi - c_lo)) * (concentration - c_lo) + i_lo
                    return round(aqi)
            # Above highest breakpoint
            return 500
        
        # Calculate sub-indices
        pm25_aqi = linear_aqi(pm25 or 0, processing_config.pm25_breakpoints)
        co_aqi = linear_aqi(co_ppm or 0, processing_config.co_breakpoints)
        
        # Final AQI is the maximum
        aqi = max(pm25_aqi, co_aqi)
        
        # Determine category
        if aqi <= 50:
            category = 'Good'
        elif aqi <= 100:
            category = 'Moderate'
        elif aqi <= 150:
            category = 'Unhealthy for Sensitive Groups'
        elif aqi <= 200:
            category = 'Unhealthy'
        elif aqi <= 300:
            category = 'Very Unhealthy'
        else:
            category = 'Hazardous'
        
        return aqi, category
    
    # =========================================================================
    # DERIVED METRICS
    # =========================================================================
    
    @staticmethod
    def calculate_heat_index(temp_c: float, humidity: float) -> Optional[float]:
        """
        Calculate Heat Index (perceived temperature)
        
        Uses Rothfusz regression equation when T >= 27°C and RH >= 40%
        Otherwise returns actual temperature.
        """
        if temp_c is None or humidity is None:
            return None
        
        if temp_c < 27 or humidity < 40:
            return temp_c
        
        # Rothfusz regression (converted from Fahrenheit version)
        t = temp_c * 9/5 + 32  # Convert to F for formula
        rh = humidity
        
        hi = -42.379 + 2.04901523*t + 10.14333127*rh - 0.22475541*t*rh \
             - 0.00683783*t*t - 0.05481717*rh*rh + 0.00122874*t*t*rh \
             + 0.00085282*t*rh*rh - 0.00000199*t*t*rh*rh
        
        # Convert back to Celsius
        heat_index_c = (hi - 32) * 5/9
        return round(heat_index_c, 1)
    
    @staticmethod
    def calculate_toxic_gas_index(co_ppm: float, co2_ppm: float) -> float:
        """
        Calculate Toxic Gas Index (0-100 scale)
        
        Composite score: 60% CO contribution + 40% CO2 contribution
        Higher = more dangerous
        """
        co_score = min((co_ppm or 0) / 50 * 100, 100) * 0.6
        co2_score = min((co2_ppm or 400) / 2000 * 100, 100) * 0.4
        
        return round(min(co_score + co2_score, 100), 1)
    
    @staticmethod
    def calculate_respiratory_risk(pm25: float) -> str:
        """
        Determine respiratory risk label based on PM2.5
        
        Based on EPA breakpoints:
        - Low: <= 12.0 µg/m³
        - Moderate: 12.1-35.4
        - High: 35.5-55.4
        - Very High: 55.5-150.4
        - Severe: > 150.4
        """
        if pm25 is None:
            return 'Low'
        
        if pm25 <= 12.0:
            return 'Low'
        elif pm25 <= 35.4:
            return 'Moderate'
        elif pm25 <= 55.4:
            return 'High'
        elif pm25 <= 150.4:
            return 'Very High'
        else:
            return 'Severe'
    
    # =========================================================================
    # GPS & MOVEMENT
    # =========================================================================
    
    @staticmethod
    def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in meters between two GPS coordinates"""
        R = 6371000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def calculate_movement(self, device_id: str, lat: float, lon: float, 
                          timestamp: datetime) -> Tuple[float, float]:
        """
        Calculate speed and distance from previous reading
        Returns: (speed_kmh, distance_m)
        """
        prev = self._previous_readings.get(device_id)
        
        if prev and prev.get('lat') and prev.get('lon'):
            distance_m = self.haversine_distance(prev['lat'], prev['lon'], lat, lon)
            
            time_delta = (timestamp - prev['timestamp']).total_seconds()
            if time_delta > 0:
                speed_kmh = (distance_m / time_delta) * 3.6  # m/s to km/h
            else:
                speed_kmh = 0
        else:
            distance_m = 0
            speed_kmh = 0
        
        # Update cache
        self._previous_readings[device_id] = {
            'lat': lat,
            'lon': lon,
            'timestamp': timestamp
        }
        
        return round(speed_kmh, 2), round(distance_m, 2)
    
    # =========================================================================
    # MAIN PROCESSING
    # =========================================================================
    
    def process_raw_telemetry(self, raw: Dict, device: Dict) -> Dict:
        """
        Process a single raw telemetry row into enriched data
        
        Args:
            raw: Raw telemetry row from database
            device: Device record with calibration factors
        
        Returns:
            Processed data ready for insertion
        """
        # Get calibration factors
        dust_cal = device.get('dust_calibration', 1.0) or 1.0
        mq135_cal = device.get('mq135_calibration', 1.0) or 1.0
        mq7_cal = device.get('mq7_calibration', 1.0) or 1.0
        
        # Calibrate sensors
        pm25 = self.calibrate_dust(raw.get('raw_dust'), dust_cal)
        co2_ppm = self.calibrate_mq135(raw.get('raw_mq135'), mq135_cal)
        co_ppm = self.calibrate_mq7(raw.get('raw_mq7'), mq7_cal)
        
        # Pass-through environmental
        temperature = raw.get('temperature_c')
        humidity = raw.get('humidity_pct')
        pressure = raw.get('pressure_hpa')
        gas_resistance = raw.get('gas_resistance')
        
        # GPS fallback logic
        raw_lat = raw.get('raw_latitude', 0) or 0
        raw_lon = raw.get('raw_longitude', 0) or 0
        
        if raw_lat == 0 and raw_lon == 0:
            # Use device static location or default
            latitude = device.get('static_latitude') or device_defaults.default_latitude
            longitude = device.get('static_longitude') or device_defaults.default_longitude
            gps_fallback = True
        else:
            latitude = raw_lat
            longitude = raw_lon
            gps_fallback = False
        
        # Calculate derived metrics
        aqi_value, aqi_category = self.calculate_aqi(pm25, co_ppm)
        heat_index = self.calculate_heat_index(temperature, humidity)
        toxic_gas_index = self.calculate_toxic_gas_index(co_ppm, co2_ppm)
        respiratory_risk = self.calculate_respiratory_risk(pm25)
        
        # Calculate movement
        recorded_at = datetime.fromisoformat(raw['recorded_at'].replace('Z', '+00:00'))
        speed_kmh, distance_m = self.calculate_movement(
            raw['device_id'], latitude, longitude, recorded_at
        )
        
        return {
            'raw_telemetry_id': raw['id'],
            'device_id': raw['device_id'],
            'recorded_at': raw['recorded_at'],
            
            # Calibrated values
            'pm25_ugm3': pm25,
            'co2_ppm': co2_ppm,
            'co_ppm': co_ppm,
            
            # Environmental
            'temperature_c': temperature,
            'humidity_pct': humidity,
            'pressure_hpa': pressure,
            'gas_resistance': gas_resistance,
            
            # Location
            'latitude': latitude,
            'longitude': longitude,
            'gps_fallback_used': gps_fallback,
            
            # Derived metrics
            'aqi_value': aqi_value,
            'aqi_category': aqi_category,
            'heat_index_c': heat_index,
            'toxic_gas_index': toxic_gas_index,
            'respiratory_risk_label': respiratory_risk,
            
            # Movement
            'speed_kmh': speed_kmh,
            'distance_moved_m': distance_m
        }


# Global processor instance
processor = DataProcessor()
