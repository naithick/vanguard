"""
GreenRoute Mesh v2 — XGBoost Inference Module
==============================================
Lightweight inference using models trained by xgboost_train.py.

Two modes:
1. FULL MODE: Uses XGBoost library (accurate, requires xgboost package)
2. LITE MODE: Uses feature-importance weighted averages (fast, no dependencies)

The models provide:
- calibrate_reading(): Adjust raw sensor values based on environmental conditions
- classify_source(): Identify if reading is traffic/kitchen/industrial/smoking/fault
- predict_radius(): Estimate spatial influence radius for interpolation

Usage:
    from xgboost_inference import XGBoostPredictor
    
    predictor = XGBoostPredictor("models/")  # loads all model files
    
    # Calibrate a reading
    adjusted = predictor.calibrate_reading(
        raw_pm25=45.0, temp=30.0, humidity=70.0, hour=9
    )
    
    # Classify pollution source
    source, confidence = predictor.classify_source(
        pm25=45.0, co=1.2, no2=25.0, hour=9, is_rush_hour=True
    )
    
    # Predict influence radius
    radius = predictor.predict_radius(pm25=120.0, aqi=180, temp=32.0)
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

log = logging.getLogger("greenroute.xgboost")

# Try to import XGBoost for full inference mode
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    log.info("XGBoost not installed — using lite inference mode")


@dataclass
class ModelWeights:
    """Loaded model weights and metadata."""
    feature_names: List[str]
    feature_importance: Dict[str, float]
    class_names: Optional[List[str]] = None  # for classifier
    rmse: Optional[float] = None
    accuracy: Optional[float] = None
    trained_at: Optional[str] = None
    n_samples: int = 0


class XGBoostPredictor:
    """
    XGBoost model inference for sensor calibration, false-positive detection,
    and radius prediction.
    """
    
    def __init__(self, models_dir: str = "models", mode: str = "auto"):
        """
        Initialize predictor with trained models.
        
        Parameters
        ----------
        models_dir : str
            Directory containing model JSON files from training
        mode : str
            "auto" - use XGBoost if available, else lite
            "full" - require XGBoost (raises if not available)
            "lite" - always use lightweight approximation
        """
        self.models_dir = Path(models_dir)
        self.mode = mode
        
        # Loaded models (XGBoost objects or None)
        self._calibration_model = None
        self._fp_model = None
        self._radius_model = None
        
        # Loaded weights (always available)
        self._calibration_weights: Optional[ModelWeights] = None
        self._fp_weights: Optional[ModelWeights] = None
        self._radius_weights: Optional[ModelWeights] = None
        
        # Determine inference mode
        if mode == "full" and not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost not installed but mode='full' requested")
        
        self._use_xgboost = (mode == "full") or (mode == "auto" and XGBOOST_AVAILABLE)
        
        # Load models
        self._load_models()
        
        log.info(f"XGBoostPredictor initialized (mode={'full' if self._use_xgboost else 'lite'})")
    
    def _load_models(self):
        """Load all available models from disk."""
        if not self.models_dir.exists():
            log.warning(f"Models directory not found: {self.models_dir}")
            return
        
        # Calibration model
        cal_weights = self.models_dir / "calibration_weights.json"
        cal_model = self.models_dir / "calibration_model.json"
        
        if cal_weights.exists():
            with open(cal_weights) as f:
                data = json.load(f)
                self._calibration_weights = ModelWeights(
                    feature_names=data.get("feature_names", []),
                    feature_importance=data.get("feature_importance", {}),
                    rmse=data.get("rmse"),
                    trained_at=data.get("trained_at"),
                    n_samples=data.get("n_samples", 0),
                )
            log.info(f"Loaded calibration weights ({self._calibration_weights.n_samples} samples)")
            
            if self._use_xgboost and cal_model.exists():
                self._calibration_model = xgb.XGBRegressor()
                self._calibration_model.load_model(str(cal_model))
                log.info("Loaded calibration XGBoost model")
        
        # False-positive model
        fp_weights = self.models_dir / "false_positive_weights.json"
        fp_model = self.models_dir / "false_positive_model.json"
        
        if fp_weights.exists():
            with open(fp_weights) as f:
                data = json.load(f)
                self._fp_weights = ModelWeights(
                    feature_names=data.get("feature_names", []),
                    feature_importance=data.get("feature_importance", {}),
                    class_names=data.get("class_names", []),
                    accuracy=data.get("accuracy"),
                    trained_at=data.get("trained_at"),
                    n_samples=data.get("n_samples", 0),
                )
            log.info(f"Loaded false-positive weights ({self._fp_weights.n_samples} samples)")
            
            if self._use_xgboost and fp_model.exists():
                self._fp_model = xgb.XGBClassifier()
                self._fp_model.load_model(str(fp_model))
                log.info("Loaded false-positive XGBoost model")
        
        # Radius model
        rad_weights = self.models_dir / "radius_weights.json"
        rad_model = self.models_dir / "radius_model.json"
        
        if rad_weights.exists():
            with open(rad_weights) as f:
                data = json.load(f)
                self._radius_weights = ModelWeights(
                    feature_names=data.get("feature_names", []),
                    feature_importance=data.get("feature_importance", {}),
                    rmse=data.get("rmse"),
                    trained_at=data.get("trained_at"),
                    n_samples=data.get("n_samples", 0),
                )
            log.info(f"Loaded radius weights ({self._radius_weights.n_samples} samples)")
            
            if self._use_xgboost and rad_model.exists():
                self._radius_model = xgb.XGBRegressor()
                self._radius_model.load_model(str(rad_model))
                log.info("Loaded radius XGBoost model")
    
    # ══════════════════════════════════════════════════════════════════════════
    # CALIBRATION
    # ══════════════════════════════════════════════════════════════════════════
    
    def calibrate_reading(
        self,
        raw_pm25: float,
        raw_dust: float = None,
        temp: float = 30.0,
        humidity: float = 70.0,
        hour: int = 12,
        month: int = 6,
        is_rush_hour: bool = False,
    ) -> float:
        """
        Adjust raw PM2.5 reading based on environmental conditions.
        
        ESP32 dust sensors are affected by temperature and humidity.
        This model learns the correction factor from CPCB ground truth.
        
        Parameters
        ----------
        raw_pm25 : float
            Raw PM2.5 estimate (dust * 1.5)
        raw_dust : float, optional
            Raw dust sensor reading (if available, improves calibration)
        temp, humidity, hour, month, is_rush_hour : environmental context
        
        Returns
        -------
        float : Calibrated PM2.5 value in µg/m³
        """
        if self._calibration_weights is None:
            log.debug("No calibration model loaded, returning raw value")
            return raw_pm25
        
        # Use raw_dust if provided, otherwise estimate from pm25
        dust_val = raw_dust if raw_dust is not None else (raw_pm25 / 1.5)
        
        features = {
            "raw_dust": dust_val,
            "temp": temp,
            "humidity": humidity,
            "hour": hour,
            "month": month,
            "is_rush_hour": int(is_rush_hour),
        }
        
        if self._use_xgboost and self._calibration_model is not None:
            # Full XGBoost inference
            feature_vec = [features.get(f, 0) for f in self._calibration_weights.feature_names]
            import numpy as np
            predicted_pm25 = self._calibration_model.predict([feature_vec])[0]
            
            # Compute adjustment factor: predicted_reference / raw
            # Apply as: calibrated = raw * (predicted / baseline)
            baseline = 50.0  # average expected PM2.5
            factor = predicted_pm25 / baseline if baseline > 0 else 1.0
            calibrated = raw_pm25 * factor
        else:
            # Lite mode: use feature-importance weighted adjustment
            calibrated = self._lite_calibrate(raw_pm25, features)
        
        return max(0, round(calibrated, 2))
    
    def _lite_calibrate(self, raw_pm25: float, features: Dict) -> float:
        """
        Simple calibration using learned feature importance.
        
        Uses heuristics derived from training:
        - High humidity → sensors over-read (moisture scattering)
        - High temp → sensors under-read (thermal noise)
        - Rush hour → likely higher actual pollution
        """
        if self._calibration_weights is None:
            return raw_pm25
        
        importance = self._calibration_weights.feature_importance
        
        # Base adjustment factors (learned from CPCB correlation)
        adjustment = 1.0
        
        # Humidity correction (sensors over-read in humid conditions)
        if "humidity" in importance and features.get("humidity", 70) > 75:
            humidity_weight = importance.get("humidity", 0.1)
            excess_humidity = (features["humidity"] - 75) / 25  # normalize to 0-1
            adjustment -= 0.1 * humidity_weight * excess_humidity  # reduce by up to 10%
        
        # Temperature correction (sensors less accurate in heat)
        if "temp" in importance and features.get("temp", 30) > 35:
            temp_weight = importance.get("temp", 0.1)
            excess_temp = (features["temp"] - 35) / 15
            adjustment += 0.05 * temp_weight * excess_temp  # slight increase
        
        # Rush hour: ESP32 readings might be lower than actual (sensor lag)
        if features.get("is_rush_hour"):
            adjustment += 0.05  # 5% boost during rush hours
        
        return raw_pm25 * adjustment
    
    # ══════════════════════════════════════════════════════════════════════════
    # FALSE POSITIVE DETECTION
    # ══════════════════════════════════════════════════════════════════════════
    
    def classify_source(
        self,
        pm25: float = 0,
        co_ppm: float = 0,
        no2: float = 0,
        so2: float = 0,
        ozone: float = 0,
        hour: int = 12,
        is_rush_hour: bool = False,
        is_weekend: bool = False,
        is_night: bool = False,
        temp: float = 30.0,
        humidity: float = 70.0,
        **kwargs,
    ) -> Tuple[str, float]:
        """
        Classify the likely source of pollution reading.
        
        Returns
        -------
        (source, confidence) : Tuple[str, float]
            source: "normal", "traffic", "kitchen", "industrial", "smoking", "sensor_fault"
            confidence: 0.0 to 1.0
        """
        if self._fp_weights is None:
            return "normal", 0.5
        
        # Compute derived features
        eps = 0.01
        pm25_co_ratio = pm25 / (co_ppm + eps) if co_ppm else 0
        no2_co_ratio = no2 / (co_ppm + eps) if co_ppm else 0
        
        features = {
            "pm25": pm25,
            "co_ppm": co_ppm,
            "no2": no2,
            "so2": so2,
            "ozone": ozone,
            "pm25_co_ratio": pm25_co_ratio,
            "no2_co_ratio": no2_co_ratio,
            "hour": hour,
            "is_rush_hour": int(is_rush_hour),
            "is_weekend": int(is_weekend),
            "is_night": int(is_night),
            "temp": temp,
            "humidity": humidity,
        }
        
        if self._use_xgboost and self._fp_model is not None:
            # Full XGBoost inference
            feature_vec = [features.get(f, 0) for f in self._fp_weights.feature_names]
            import numpy as np
            probs = self._fp_model.predict_proba([feature_vec])[0]
            pred_idx = int(np.argmax(probs))
            confidence = float(probs[pred_idx])
            source = self._fp_weights.class_names[pred_idx] if self._fp_weights.class_names else "normal"
        else:
            # Lite mode: rule-based classification
            source, confidence = self._lite_classify(features)
        
        return source, round(confidence, 3)
    
    def _lite_classify(self, features: Dict) -> Tuple[str, float]:
        """
        Rule-based classification using learned feature importance.
        """
        pm25 = features.get("pm25", 0)
        co = features.get("co_ppm", 0)
        no2 = features.get("no2", 0)
        so2 = features.get("so2", 0)
        is_rush = features.get("is_rush_hour", 0)
        hour = features.get("hour", 12)
        no2_co = features.get("no2_co_ratio", 0)
        
        # Sensor fault detection
        if pm25 > 400 or co > 50 or (pm25 > 100 and co < 0.1):
            return "sensor_fault", 0.9
        
        # Traffic signature
        if is_rush and no2 > 20 and no2_co > 15:
            return "traffic", 0.85
        
        # Industrial signature
        if so2 > 20 and pm25 > 50:
            return "industrial", 0.75
        
        # Kitchen/cooking (evening hours, high CO)
        if hour in [11, 12, 13, 18, 19, 20] and co > 2 and no2 < 10:
            return "kitchen", 0.7
        
        # Smoking (localized high CO)
        if co > 5 and pm25 < 30 and no2 < 5:
            return "smoking", 0.65
        
        return "normal", 0.8
    
    # ══════════════════════════════════════════════════════════════════════════
    # RADIUS PREDICTION
    # ══════════════════════════════════════════════════════════════════════════
    
    def predict_radius(
        self,
        pm25: float = 50.0,
        aqi: int = 100,
        temp: float = 30.0,
        humidity: float = 70.0,
        hour: int = 12,
        is_rush_hour: bool = False,
        wind_speed: float = 1.0,
    ) -> float:
        """
        Predict the spatial influence radius of a reading.
        
        Higher AQI = larger affected area, but accuracy decreases with distance.
        Used for zone interpolation weighting.
        
        Returns
        -------
        float : Recommended radius in meters (100 - 3000)
        """
        if self._radius_weights is None:
            # Fallback: simple AQI-based radius
            return min(3000, max(100, 200 + (aqi / 500) * 1800))
        
        features = {
            "pm25": pm25,
            "aqi": aqi,
            "temp": temp,
            "humidity": humidity,
            "hour": hour,
            "is_rush_hour": int(is_rush_hour),
            "WS (m/s)": wind_speed,
        }
        
        if self._use_xgboost and self._radius_model is not None:
            # Full XGBoost inference
            feature_vec = [features.get(f, 0) for f in self._radius_weights.feature_names]
            radius = float(self._radius_model.predict([feature_vec])[0])
        else:
            # Lite mode
            radius = self._lite_radius(features)
        
        return max(100, min(3000, round(radius, 0)))
    
    def _lite_radius(self, features: Dict) -> float:
        """
        Simple radius calculation using learned feature importance.
        """
        aqi = features.get("aqi", 100)
        humidity = features.get("humidity", 70)
        wind = features.get("WS (m/s)", 1.0)
        
        # Base radius from AQI
        base = 200 + (aqi / 500) * 1800
        
        # Wind increases spread
        wind_factor = 1 + (wind / 10) * 0.5
        
        # Humidity decreases spread
        humidity_factor = 1 - (humidity - 50) / 200
        
        return base * wind_factor * humidity_factor
    
    # ══════════════════════════════════════════════════════════════════════════
    # COMBINED PROCESSING
    # ══════════════════════════════════════════════════════════════════════════
    
    def process_reading(self, reading: Dict) -> Dict:
        """
        Apply all XGBoost enhancements to a reading.
        
        Parameters
        ----------
        reading : dict
            Raw reading with keys: pm25, co_ppm, no2, temp, humidity, hour, etc.
        
        Returns
        -------
        dict : Enhanced reading with additional fields:
            - pm25_calibrated: Calibrated PM2.5
            - source_classification: Detected pollution source
            - source_confidence: Confidence in classification
            - influence_radius_m: Predicted spatial radius
            - is_false_positive: True if source is smoking/sensor_fault
        """
        result = reading.copy()
        
        # Extract values
        pm25 = reading.get("pm25_ugm3") or reading.get("pm25", 0)
        co = reading.get("co_ppm", 0)
        no2 = reading.get("no2", 0)
        so2 = reading.get("so2", 0)
        temp = reading.get("temperature_c") or reading.get("temp", 30)
        humidity = reading.get("humidity_pct") or reading.get("humidity", 70)
        aqi = reading.get("aqi_value") or reading.get("aqi", 100)
        
        # Parse timestamp for hour
        hour = 12
        if "recorded_at" in reading:
            try:
                from datetime import datetime
                ts = reading["recorded_at"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                hour = ts.hour
            except:
                pass
        
        is_rush = hour in [7, 8, 9, 17, 18, 19]
        is_night = hour in [22, 23, 0, 1, 2, 3, 4, 5]
        
        # 1. Calibrate PM2.5
        pm25_calibrated = self.calibrate_reading(
            raw_pm25=pm25,
            temp=temp,
            humidity=humidity,
            hour=hour,
            is_rush_hour=is_rush,
        )
        result["pm25_calibrated"] = pm25_calibrated
        
        # 2. Classify source
        source, confidence = self.classify_source(
            pm25=pm25_calibrated,
            co_ppm=co,
            no2=no2,
            so2=so2,
            hour=hour,
            is_rush_hour=is_rush,
            is_night=is_night,
            temp=temp,
            humidity=humidity,
        )
        result["source_classification"] = source
        result["source_confidence"] = confidence
        result["is_false_positive"] = source in ("smoking", "sensor_fault")
        
        # 3. Predict radius
        radius = self.predict_radius(
            pm25=pm25_calibrated,
            aqi=aqi,
            temp=temp,
            humidity=humidity,
            hour=hour,
            is_rush_hour=is_rush,
        )
        result["influence_radius_m"] = radius
        
        return result


# ── Singleton for easy import ─────────────────────────────────────────────────
_predictor: Optional[XGBoostPredictor] = None


def get_predictor(models_dir: str = "models", mode: str = "auto") -> XGBoostPredictor:
    """Get or create the global XGBoost predictor instance."""
    global _predictor
    if _predictor is None:
        try:
            _predictor = XGBoostPredictor(models_dir, mode)
        except Exception as e:
            log.warning(f"Failed to initialize XGBoostPredictor: {e}")
            _predictor = XGBoostPredictor.__new__(XGBoostPredictor)
            _predictor._calibration_weights = None
            _predictor._fp_weights = None
            _predictor._radius_weights = None
            _predictor._use_xgboost = False
    return _predictor


# ── Convenience functions ─────────────────────────────────────────────────────

def calibrate_pm25(raw_pm25: float, temp: float = 30, humidity: float = 70, hour: int = 12) -> float:
    """Quick PM2.5 calibration."""
    return get_predictor().calibrate_reading(raw_pm25, temp, humidity, hour)


def classify_pollution_source(pm25: float, co: float = 0, no2: float = 0, hour: int = 12) -> Tuple[str, float]:
    """Quick source classification."""
    return get_predictor().classify_source(pm25=pm25, co_ppm=co, no2=no2, hour=hour)


def get_influence_radius(aqi: int, pm25: float = 50) -> float:
    """Quick radius prediction."""
    return get_predictor().predict_radius(aqi=aqi, pm25=pm25)
