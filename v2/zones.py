"""
GreenRoute Mesh v2 — Zone Interpolation Engine

Converts discrete sensor points into continuous air-quality zones
using Inverse Distance Weighting (IDW) interpolation.

Output formats:
  1. **Heatmap grid** — uniform grid cells with interpolated AQI / PM2.5
  2. **Contour zones** — polygons grouped by AQI category (Good, Moderate, …)

Both returned as GeoJSON FeatureCollections for easy map rendering.
"""

import math
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger("greenroute.zones")


# ── AQI category bands ───────────────────────────────────────────────────────
AQI_BANDS = [
    (0,   50,  "Good",                          "#00e400"),
    (51,  100, "Moderate",                       "#ffff00"),
    (101, 150, "Unhealthy for Sensitive Groups", "#ff7e00"),
    (151, 200, "Unhealthy",                      "#ff0000"),
    (201, 300, "Very Unhealthy",                 "#8f3f97"),
    (301, 500, "Hazardous",                      "#7e0023"),
]


def _aqi_band(aqi: float) -> Tuple[str, str]:
    """Return (category, hex_color) for an AQI value."""
    for lo, hi, cat, color in AQI_BANDS:
        if lo <= aqi <= hi:
            return cat, color
    return "Hazardous", "#7e0023"


# ── Haversine (metres) ───────────────────────────────────────────────────────

def _haversine_m(lat1, lon1, lat2, lon2) -> float:
    R = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ═════════════════════════════════════════════════════════════════════════════
#  IDW INTERPOLATION
# ═════════════════════════════════════════════════════════════════════════════

def idw_interpolate(
    points: np.ndarray,   # (N, 2)  lat, lon
    values: np.ndarray,   # (N,)    AQI or PM2.5
    grid_lat: np.ndarray, # (rows, cols)
    grid_lon: np.ndarray, # (rows, cols)
    power: float = 2.0,
    radius_m: float = 500.0,
) -> np.ndarray:
    """
    Inverse Distance Weighting on a lat/lon grid.

    Parameters
    ----------
    points   : sensor locations (lat, lon)
    values   : measured values at each point
    grid_lat : 2-D meshgrid of latitudes
    grid_lon : 2-D meshgrid of longitudes
    power    : distance exponent (higher → sharper falloff)
    radius_m : max influence radius in metres (points beyond this ignored)

    Returns
    -------
    2-D array of interpolated values, same shape as grid_lat.
    NaN where no sensor is within radius.
    """
    rows, cols = grid_lat.shape
    result = np.full((rows, cols), np.nan)

    for i in range(rows):
        for j in range(cols):
            glat, glon = grid_lat[i, j], grid_lon[i, j]

            # Distances to every sensor (in metres)
            dists = np.array([
                _haversine_m(glat, glon, points[k, 0], points[k, 1])
                for k in range(len(points))
            ])

            # Sensors within radius
            mask = dists <= radius_m
            if not mask.any():
                continue

            d = dists[mask]
            v = values[mask]

            # If a grid point is right on top of a sensor, use that value
            zero_mask = d < 1e-9
            if zero_mask.any():
                result[i, j] = v[zero_mask].mean()
                continue

            weights = 1.0 / np.power(d, power)
            result[i, j] = np.sum(weights * v) / np.sum(weights)

    return result


# ═════════════════════════════════════════════════════════════════════════════
#  ZONE BUILDER
# ═════════════════════════════════════════════════════════════════════════════

class ZoneBuilder:
    """Build continuous air-quality zones from discrete processed readings."""

    def __init__(
        self,
        grid_resolution: int = 30,     # NxN grid cells
        padding_m: float = 200.0,      # metres to pad beyond data bounds
        idw_power: float = 2.0,        # IDW distance exponent
        influence_radius_m: float = 500.0,  # max interpolation radius
    ):
        self.grid_resolution = grid_resolution
        self.padding_m = padding_m
        self.idw_power = idw_power
        self.influence_radius_m = influence_radius_m

    # ─────────────────────────────────────────────────────────────────────
    #  Aggregate duplicate coordinates (average AQI at same GPS point)
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _aggregate_points(
        readings: List[Dict], field: str = "aqi_value"
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Group readings by (lat, lon), average the field value.
        Returns (points (M,2), values (M,)).
        """
        buckets: Dict[Tuple[float, float], List[float]] = {}
        for r in readings:
            lat = r.get("latitude")
            lon = r.get("longitude")
            val = r.get(field)
            if lat is None or lon is None or val is None:
                continue
            key = (round(lat, 6), round(lon, 6))
            buckets.setdefault(key, []).append(val)

        if not buckets:
            return np.empty((0, 2)), np.empty(0)

        pts = np.array(list(buckets.keys()))
        vals = np.array([np.mean(v) for v in buckets.values()])
        return pts, vals

    # ─────────────────────────────────────────────────────────────────────
    #  Build the interpolation grid
    # ─────────────────────────────────────────────────────────────────────

    def _make_grid(
        self, points: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray, float, float, float, float]:
        """
        Create a meshgrid that covers the data bounding box + padding.
        Returns (grid_lat, grid_lon, lat_min, lat_max, lon_min, lon_max).
        """
        # one degree of lat ≈ 111 320 m
        pad_deg_lat = self.padding_m / 111_320
        # one degree of lon depends on latitude
        mean_lat = points[:, 0].mean()
        pad_deg_lon = self.padding_m / (111_320 * math.cos(math.radians(mean_lat)))

        lat_min = points[:, 0].min() - pad_deg_lat
        lat_max = points[:, 0].max() + pad_deg_lat
        lon_min = points[:, 1].min() - pad_deg_lon
        lon_max = points[:, 1].max() + pad_deg_lon

        lats = np.linspace(lat_min, lat_max, self.grid_resolution)
        lons = np.linspace(lon_min, lon_max, self.grid_resolution)
        grid_lon, grid_lat = np.meshgrid(lons, lats)

        return grid_lat, grid_lon, lat_min, lat_max, lon_min, lon_max

    # ─────────────────────────────────────────────────────────────────────
    #  Heatmap grid → GeoJSON
    # ─────────────────────────────────────────────────────────────────────

    def build_heatmap(
        self,
        readings: List[Dict],
        field: str = "aqi_value",
    ) -> Dict:
        """
        Generate a GeoJSON FeatureCollection where each feature is a grid
        cell (rectangle) with interpolated value + AQI category/color.

        Parameters
        ----------
        readings : list of processed_data dicts (must have latitude, longitude, field)
        field    : which numeric field to interpolate ("aqi_value", "pm25_ugm3", etc.)

        Returns
        -------
        GeoJSON FeatureCollection
        """
        points, values = self._aggregate_points(readings, field)

        if len(points) < 2:
            log.warning("Need at least 2 unique GPS points for interpolation")
            return self._empty_fc()

        grid_lat, grid_lon, lat_min, lat_max, lon_min, lon_max = self._make_grid(points)
        surface = idw_interpolate(
            points, values, grid_lat, grid_lon,
            power=self.idw_power,
            radius_m=self.influence_radius_m,
        )

        dlat = (lat_max - lat_min) / self.grid_resolution
        dlon = (lon_max - lon_min) / self.grid_resolution

        features = []
        rows, cols = surface.shape
        for i in range(rows):
            for j in range(cols):
                val = surface[i, j]
                if np.isnan(val):
                    continue

                clat = grid_lat[i, j]
                clon = grid_lon[i, j]
                cat, color = _aqi_band(val) if field == "aqi_value" else ("", "#888888")

                # Cell rectangle (SW → SE → NE → NW → SW)
                sw_lat, sw_lon = clat - dlat / 2, clon - dlon / 2
                ne_lat, ne_lon = clat + dlat / 2, clon + dlon / 2

                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [sw_lon, sw_lat],
                            [ne_lon, sw_lat],
                            [ne_lon, ne_lat],
                            [sw_lon, ne_lat],
                            [sw_lon, sw_lat],
                        ]],
                    },
                    "properties": {
                        "value": round(float(val), 1),
                        "field": field,
                        "category": cat,
                        "color": color,
                        "opacity": self._value_opacity(val, values),
                    },
                })

        log.info(
            f"Heatmap: {len(features)} cells from {len(points)} unique points "
            f"({field} range {values.min():.0f}–{values.max():.0f})"
        )

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "field": field,
                "grid_resolution": self.grid_resolution,
                "point_count": len(points),
                "cell_count": len(features),
                "value_range": [round(float(values.min()), 1),
                                round(float(values.max()), 1)],
                "bounds": {
                    "lat_min": round(lat_min, 6),
                    "lat_max": round(lat_max, 6),
                    "lon_min": round(lon_min, 6),
                    "lon_max": round(lon_max, 6),
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    #  Contour zones → GeoJSON  (AQI bands as merged polygons)
    # ─────────────────────────────────────────────────────────────────────

    def build_contour_zones(
        self,
        readings: List[Dict],
        field: str = "aqi_value",
    ) -> Dict:
        """
        Generate AQI-band contour zones.  Each feature is one AQI category
        covering the area where interpolated AQI falls in that band.

        Returns GeoJSON FeatureCollection with one MultiPolygon per band.
        """
        points, values = self._aggregate_points(readings, field)

        if len(points) < 2:
            return self._empty_fc()

        grid_lat, grid_lon, lat_min, lat_max, lon_min, lon_max = self._make_grid(points)
        surface = idw_interpolate(
            points, values, grid_lat, grid_lon,
            power=self.idw_power,
            radius_m=self.influence_radius_m,
        )

        dlat = (lat_max - lat_min) / self.grid_resolution
        dlon = (lon_max - lon_min) / self.grid_resolution

        # Group cells by AQI band
        band_cells: Dict[str, List] = {}
        rows, cols = surface.shape
        for i in range(rows):
            for j in range(cols):
                val = surface[i, j]
                if np.isnan(val):
                    continue
                cat, color = _aqi_band(val)
                key = f"{cat}|{color}"
                clat = grid_lat[i, j]
                clon = grid_lon[i, j]
                sw_lat, sw_lon = clat - dlat / 2, clon - dlon / 2
                ne_lat, ne_lon = clat + dlat / 2, clon + dlon / 2
                band_cells.setdefault(key, []).append([
                    [sw_lon, sw_lat],
                    [ne_lon, sw_lat],
                    [ne_lon, ne_lat],
                    [sw_lon, ne_lat],
                    [sw_lon, sw_lat],
                ])

        features = []
        for key, polygons in band_cells.items():
            cat, color = key.split("|", 1)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [[p] for p in polygons],
                },
                "properties": {
                    "category": cat,
                    "color": color,
                    "cell_count": len(polygons),
                },
            })

        log.info(f"Contour zones: {len(features)} bands from {len(points)} points")

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "field": field,
                "band_count": len(features),
                "point_count": len(points),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    #  Point summary → GeoJSON  (raw sensor positions as markers)
    # ─────────────────────────────────────────────────────────────────────

    def build_point_layer(
        self,
        readings: List[Dict],
        field: str = "aqi_value",
    ) -> Dict:
        """
        Simple GeoJSON of aggregated sensor positions (averaged values).
        Useful as a marker overlay on top of the heatmap.
        """
        points, values = self._aggregate_points(readings, field)

        features = []
        for k in range(len(points)):
            cat, color = _aqi_band(values[k]) if field == "aqi_value" else ("", "#888")
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(points[k, 1]), float(points[k, 0])],
                },
                "properties": {
                    "value": round(float(values[k]), 1),
                    "field": field,
                    "category": cat,
                    "color": color,
                },
            })

        return {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "field": field,
                "point_count": len(features),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _value_opacity(val: float, all_values: np.ndarray) -> float:
        """Map value to 0.15–0.7 opacity range for subtle rendering."""
        vmin, vmax = all_values.min(), all_values.max()
        if vmax == vmin:
            return 0.4
        norm = (val - vmin) / (vmax - vmin)
        return round(0.15 + norm * 0.55, 2)

    @staticmethod
    def _empty_fc() -> Dict:
        return {
            "type": "FeatureCollection",
            "features": [],
            "metadata": {"error": "insufficient data", "point_count": 0},
        }


# ── Singleton ─────────────────────────────────────────────────────────────────
zone_builder = ZoneBuilder()
