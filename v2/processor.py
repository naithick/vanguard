"""
GreenRoute Mesh v2 — Data Processor
Converts one raw_telemetry row into one processed_data row.

Pipeline per row:
  1. Sensor calibration   (dust→PM2.5, MQ135→CO₂, MQ7→CO)
  2. GPS fallback         (0,0 → device static location)
  3. Derived metrics      (AQI, Heat Index, Toxic Gas Index, Respiratory Risk)
  4. Movement             (speed + distance from previous GPS fix)
"""

import math
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

from config import processing_config, device_defaults

log = logging.getLogger("greenroute.processor")


class DataProcessor:
    """Stateless-ish processor (only caches last GPS fix per device)."""

    # previous GPS fix per device — needed for speed / distance
    _prev: Dict[str, Dict] = {}

    # ─────────────────────────────────────────────────────────────────────
    # 1. SENSOR CALIBRATION
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def calibrate_dust(raw: float, cal: float = 1.0) -> Optional[float]:
        """Raw spike count → PM2.5 µg/m³  (linear × cal factor)."""
        if raw is None:
            return None
        return round(raw * 1.5 * cal, 2)

    @staticmethod
    def calibrate_mq135(raw_adc: float, cal: float = 1.0) -> Optional[float]:
        """MQ135 ADC → CO₂-equivalent PPM  (log-log Rs/R0 curve)."""
        if raw_adc is None:
            return None
        r0 = 900
        rs_r0 = raw_adc / r0
        if rs_r0 <= 0:
            return 400.0
        co2 = 116.6 * math.pow(rs_r0, -2.769) * cal
        return round(max(400, min(co2, 5000)), 1)

    @staticmethod
    def calibrate_mq7(raw_adc: float, cal: float = 1.0) -> Optional[float]:
        """MQ7 ADC → CO PPM  (log-log Rs/R0 curve)."""
        if raw_adc is None:
            return None
        r0 = 590
        rs_r0 = raw_adc / r0
        if rs_r0 <= 0:
            return 0.0
        co = 99.042 * math.pow(rs_r0, -1.518) * cal
        return round(max(0, min(co, 1000)), 2)

    # ─────────────────────────────────────────────────────────────────────
    # 2. AQI  (US EPA — higher of PM2.5 and CO sub-indices)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _linear_aqi(conc: float, bp_table: list) -> int:
        for c_lo, c_hi, i_lo, i_hi in bp_table:
            if c_lo <= conc <= c_hi:
                return round(((i_hi - i_lo) / (c_hi - c_lo)) * (conc - c_lo) + i_lo)
        return 500  # above highest breakpoint

    @classmethod
    def calculate_aqi(cls, pm25: float, co_ppm: float) -> Tuple[int, str]:
        pm25_aqi = cls._linear_aqi(pm25 or 0, processing_config.pm25_breakpoints)
        co_aqi   = cls._linear_aqi(co_ppm or 0, processing_config.co_breakpoints)
        aqi = max(pm25_aqi, co_aqi)

        if   aqi <= 50:  cat = "Good"
        elif aqi <= 100: cat = "Moderate"
        elif aqi <= 150: cat = "Unhealthy for Sensitive Groups"
        elif aqi <= 200: cat = "Unhealthy"
        elif aqi <= 300: cat = "Very Unhealthy"
        else:            cat = "Hazardous"
        return aqi, cat

    # ─────────────────────────────────────────────────────────────────────
    # 3. DERIVED METRICS
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def heat_index(temp_c: float, rh: float) -> Optional[float]:
        """Rothfusz Heat Index (returns plain temp when below threshold)."""
        if temp_c is None or rh is None:
            return None
        if temp_c < 27 or rh < 40:
            return temp_c
        t = temp_c * 9 / 5 + 32  # → °F for the regression
        hi = (-42.379 + 2.04901523 * t + 10.14333127 * rh
              - 0.22475541 * t * rh - 0.00683783 * t * t
              - 0.05481717 * rh * rh + 0.00122874 * t * t * rh
              + 0.00085282 * t * rh * rh - 0.00000199 * t * t * rh * rh)
        return round((hi - 32) * 5 / 9, 1)

    @staticmethod
    def toxic_gas_index(co_ppm: float, co2_ppm: float) -> float:
        """Composite 0-100 score  (60 % CO + 40 % CO₂)."""
        co_s  = min((co_ppm or 0) / 50 * 100, 100) * 0.6
        co2_s = min((co2_ppm or 400) / 2000 * 100, 100) * 0.4
        return round(min(co_s + co2_s, 100), 1)

    @staticmethod
    def respiratory_risk(pm25: float) -> str:
        if pm25 is None or pm25 <= 12.0:
            return "Low"
        if pm25 <= 35.4:
            return "Moderate"
        if pm25 <= 55.4:
            return "High"
        if pm25 <= 150.4:
            return "Very High"
        return "Severe"

    # ─────────────────────────────────────────────────────────────────────
    # 4. MOVEMENT  (haversine between consecutive GPS fixes)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        """Distance in metres."""
        R = 6_371_000
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def movement(self, device_id: str, lat: float, lon: float,
                 ts: datetime) -> Tuple[float, float]:
        """Returns (speed_kmh, distance_m)."""
        prev = self._prev.get(device_id)
        if prev and prev["lat"] and prev["lon"]:
            dist = self._haversine(prev["lat"], prev["lon"], lat, lon)
            dt = (ts - prev["ts"]).total_seconds()
            speed = (dist / dt * 3.6) if dt > 0 else 0.0
        else:
            dist, speed = 0.0, 0.0
        self._prev[device_id] = {"lat": lat, "lon": lon, "ts": ts}
        return round(speed, 2), round(dist, 2)

    # ─────────────────────────────────────────────────────────────────────
    # MAIN ENTRY POINT
    # ─────────────────────────────────────────────────────────────────────

    def process(self, raw: Dict, device: Dict) -> Dict:
        """
        Transform one raw_telemetry row → one processed_data row.

        Parameters
        ----------
        raw     : row from raw_telemetry (dict)
        device  : matching devices row   (dict)
        """
        # calibration factors
        d_cal  = device.get("dust_calibration", 1.0) or 1.0
        m135   = device.get("mq135_calibration", 1.0) or 1.0
        m7     = device.get("mq7_calibration", 1.0) or 1.0

        pm25    = self.calibrate_dust(raw.get("raw_dust"), d_cal)
        co2     = self.calibrate_mq135(raw.get("raw_mq135"), m135)
        co      = self.calibrate_mq7(raw.get("raw_mq7"), m7)

        temp = raw.get("temperature_c")
        hum  = raw.get("humidity_pct")
        pres = raw.get("pressure_hpa")
        gas  = raw.get("gas_resistance")

        # GPS fallback
        rlat = raw.get("raw_latitude", 0) or 0
        rlon = raw.get("raw_longitude", 0) or 0
        if rlat == 0 and rlon == 0:
            lat = device.get("static_latitude") or device_defaults.default_latitude
            lon = device.get("static_longitude") or device_defaults.default_longitude
            fb  = True
        else:
            lat, lon, fb = rlat, rlon, False

        aqi_val, aqi_cat = self.calculate_aqi(pm25, co)
        hi  = self.heat_index(temp, hum)
        tgi = self.toxic_gas_index(co, co2)
        rr  = self.respiratory_risk(pm25)

        ts = datetime.fromisoformat(raw["recorded_at"].replace("Z", "+00:00"))
        speed, dist = self.movement(raw["device_id"], lat, lon, ts)

        return {
            "raw_telemetry_id":     raw["id"],
            "device_id":            raw["device_id"],
            "recorded_at":          raw["recorded_at"],

            "pm25_ugm3":            pm25,
            "co2_ppm":              co2,
            "co_ppm":               co,

            "temperature_c":        temp,
            "humidity_pct":         hum,
            "pressure_hpa":         pres,
            "gas_resistance":       gas,

            "latitude":             lat,
            "longitude":            lon,
            "gps_fallback_used":    fb,

            "aqi_value":            aqi_val,
            "aqi_category":         aqi_cat,
            "heat_index_c":         hi,
            "toxic_gas_index":      tgi,
            "respiratory_risk_label": rr,

            "speed_kmh":            speed,
            "distance_moved_m":     dist,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
processor = DataProcessor()
