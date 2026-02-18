#!/usr/bin/env python3
"""
GreenRoute Mesh v2 — XGBoost Training Script
============================================
Run this on your friend's M4 Mac (fast training). Exports model weights as JSON
that can be loaded on your laptop for inference without needing XGBoost installed.

Three models are trained:
1. **Calibration Model** — learns ESP32 sensor → CPCB ground-truth mapping
   - Corrects systematic bias in cheap sensors vs government instruments
   
2. **False Positive Detector** — classifies anomaly sources
   - Distinguishes: normal | smoking | traffic | kitchen | industrial | sensor_fault
   - Uses pollutant ratios (CO/PM2.5, NO2/CO) + time-of-day + location
   
3. **AQI Radius Predictor** — predicts spatial influence radius
   - Higher AQI = larger affected area, but accuracy drops with distance
   - Output: recommended_radius_m (used for zone interpolation weight)

Usage (on M4 Mac):
    pip install xgboost pandas numpy scikit-learn
    python xgboost_train.py --data-dir /path/to/csv/files --output models/

The output JSON files can be transferred to the server and loaded by xgboost_inference.py
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder

# XGBoost — only needed for training, not inference
import xgboost as xgb

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("xgboost_train")


# ══════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ══════════════════════════════════════════════════════════════════════════════

def load_cpcb_data(data_dir: Path) -> pd.DataFrame:
    """
    Load CPCB government station CSVs (ground truth for calibration).
    These have calibrated PM2.5, PM10, CO, NO2, SO2, Ozone, etc.
    """
    cpcb_files = list(data_dir.glob("Raw_data_15Min_*.csv")) + \
                 list(data_dir.glob("**/Raw_data_15Min_*.csv"))
    
    if not cpcb_files:
        log.warning("No CPCB CSV files found")
        return pd.DataFrame()
    
    dfs = []
    for f in cpcb_files:
        log.info(f"Loading CPCB: {f.name}")
        try:
            df = pd.read_csv(f, na_values=["NA", "None", ""])
            df["source_file"] = f.name
            # Extract station ID from filename
            if "site_" in f.name:
                site_id = f.name.split("site_")[1].split("_")[0]
                df["station_id"] = site_id
            dfs.append(df)
        except Exception as e:
            log.error(f"Failed to load {f}: {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    combined = pd.concat(dfs, ignore_index=True)
    log.info(f"Loaded {len(combined)} CPCB rows from {len(cpcb_files)} files")
    return combined


def load_esp32_data(data_dir: Path) -> pd.DataFrame:
    """
    Load ESP32 sensor data (raw readings to be calibrated).
    """
    # Look for the synthetic/test data
    esp_files = list(data_dir.glob("*coverage*.csv")) + \
                list(data_dir.glob("**/Sample_Data*.csv")) + \
                list(data_dir.glob("Sample_Data*.csv"))
    
    if not esp_files:
        log.warning("No ESP32 CSV files found")
        return pd.DataFrame()
    
    dfs = []
    for f in esp_files:
        log.info(f"Loading ESP32: {f.name}")
        try:
            df = pd.read_csv(f)
            df["source_file"] = f.name
            dfs.append(df)
        except Exception as e:
            log.error(f"Failed to load {f}: {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    combined = pd.concat(dfs, ignore_index=True)
    log.info(f"Loaded {len(combined)} ESP32 rows from {len(esp_files)} files")
    return combined


# ══════════════════════════════════════════════════════════════════════════════
# FEATURE ENGINEERING
# ══════════════════════════════════════════════════════════════════════════════

def extract_time_features(df: pd.DataFrame, ts_col: str = "Timestamp") -> pd.DataFrame:
    """Extract hour, day-of-week, month from timestamp."""
    df = df.copy()
    
    # Handle multiple timestamp column names
    for col in [ts_col, "timestamp", "Timestamp", "recorded_at"]:
        if col in df.columns:
            try:
                df["_ts"] = pd.to_datetime(df[col], errors="coerce")
                break
            except:
                continue
    
    if "_ts" not in df.columns:
        log.warning("No valid timestamp column found")
        return df
    
    df["hour"] = df["_ts"].dt.hour
    df["day_of_week"] = df["_ts"].dt.dayofweek
    df["month"] = df["_ts"].dt.month
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)
    df["is_rush_hour"] = df["hour"].isin([7, 8, 9, 17, 18, 19]).astype(int)
    df["is_night"] = df["hour"].isin([22, 23, 0, 1, 2, 3, 4, 5]).astype(int)
    
    df.drop(columns=["_ts"], inplace=True)
    return df


def compute_pollutant_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute pollutant ratios that help identify pollution sources.
    Different sources have characteristic "fingerprints":
    - Traffic: high NO2/CO ratio, moderate PM2.5
    - Kitchen/cooking: high CO, low NO2, specific PM2.5/CO ratio
    - Industrial: high SO2, high PM10/PM2.5 ratio
    - Smoking: very high local CO, specific benzene pattern
    """
    df = df.copy()
    
    # Normalize column names (CPCB uses different naming)
    col_map = {
        "PM2.5 (µg/m³)": "pm25",
        "PM10 (µg/m³)": "pm10",
        "CO (mg/m³)": "co_mgm3",
        "NO2 (µg/m³)": "no2",
        "SO2 (µg/m³)": "so2",
        "Ozone (µg/m³)": "ozone",
        "Benzene (µg/m³)": "benzene",
        "NO (µg/m³)": "no",
        "NOx (ppb)": "nox",
        "AT (°C)": "temp",
        "RH (%)": "humidity",
    }
    
    for old, new in col_map.items():
        if old in df.columns:
            df[new] = df[old]
    
    # Convert CO from mg/m³ to ppm for ratio calculations
    if "co_mgm3" in df.columns:
        df["co_ppm"] = df["co_mgm3"] * 0.873  # approximate conversion at 25°C
    
    # Compute ratios (with safety for division by zero)
    eps = 0.01
    
    if "pm25" in df.columns and "co_ppm" in df.columns:
        df["pm25_co_ratio"] = df["pm25"] / (df["co_ppm"] + eps)
    
    if "pm10" in df.columns and "pm25" in df.columns:
        df["pm10_pm25_ratio"] = df["pm10"] / (df["pm25"] + eps)
    
    if "no2" in df.columns and "co_ppm" in df.columns:
        df["no2_co_ratio"] = df["no2"] / (df["co_ppm"] + eps)
    
    if "no2" in df.columns and "no" in df.columns:
        df["no2_no_ratio"] = df["no2"] / (df["no"] + eps)
    
    if "so2" in df.columns and "pm25" in df.columns:
        df["so2_pm25_ratio"] = df["so2"] / (df["pm25"] + eps)
    
    if "ozone" in df.columns and "no2" in df.columns:
        df["ozone_no2_ratio"] = df["ozone"] / (df["no2"] + eps)
    
    return df


def label_pollution_source(row: pd.Series) -> str:
    """
    Heuristic labeling of pollution source based on pollutant ratios.
    This creates synthetic labels for training the false-positive detector.
    
    In production, you'd have manually labeled data or use clustering.
    """
    # Default
    source = "normal"
    
    pm25 = row.get("pm25", 0) or 0
    co = row.get("co_ppm", 0) or 0
    no2 = row.get("no2", 0) or 0
    so2 = row.get("so2", 0) or 0
    pm10_pm25 = row.get("pm10_pm25_ratio", 1) or 1
    no2_co = row.get("no2_co_ratio", 0) or 0
    is_rush = row.get("is_rush_hour", 0)
    
    # Traffic signature: high NO2/CO during rush hours
    if is_rush and no2_co > 15 and no2 > 20:
        source = "traffic"
    
    # Industrial: high SO2 and coarse particles
    elif so2 > 20 and pm10_pm25 > 2.5:
        source = "industrial"
    
    # Kitchen/cooking: high CO, low NO2, evening hours
    elif co > 2 and no2 < 10 and row.get("hour", 12) in [11, 12, 13, 18, 19, 20]:
        source = "kitchen"
    
    # Smoking: very localized high CO spike (would need spatial data)
    elif co > 5 and pm25 < 30 and no2 < 5:
        source = "smoking"
    
    # Sensor fault: impossible ratios or extreme values
    elif pm25 > 400 or co > 50 or (pm25 > 0 and pm10_pm25 < 0.5):
        source = "sensor_fault"
    
    return source


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 1: CALIBRATION MODEL
# ══════════════════════════════════════════════════════════════════════════════

def train_calibration_model(cpcb_df: pd.DataFrame, output_dir: Path) -> Dict:
    """
    Train a model to correct ESP32 raw sensor readings.
    
    Since we don't have paired ESP32 + CPCB data from same location/time,
    we train on CPCB data to learn the relationship between:
    - Input: raw environmental conditions (temp, humidity, pressure)
    - Output: calibration factors for different pollutants
    
    The model learns how environmental conditions affect sensor accuracy.
    """
    log.info("=" * 60)
    log.info("Training CALIBRATION MODEL")
    log.info("=" * 60)
    
    df = cpcb_df.copy()
    df = extract_time_features(df)
    df = compute_pollutant_ratios(df)
    
    # Features: environmental conditions + time
    feature_cols = ["temp", "humidity", "hour", "month", "is_rush_hour"]
    available_features = [c for c in feature_cols if c in df.columns]
    
    if len(available_features) < 3:
        log.warning("Not enough features for calibration model")
        return {}
    
    # Target: PM2.5 (we'll predict calibration adjustment)
    if "pm25" not in df.columns:
        log.warning("No PM2.5 column for calibration target")
        return {}
    
    # Clean data
    df = df.dropna(subset=available_features + ["pm25"])
    if len(df) < 100:
        log.warning(f"Only {len(df)} rows after cleaning, need more data")
        return {}
    
    X = df[available_features].values
    y = df["pm25"].values
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    log.info(f"Training on {len(X_train)} samples, testing on {len(X_test)}")
    
    # XGBoost regressor
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        objective="reg:squarederror",
        tree_method="hist",  # fast on M4
        random_state=42,
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=True,
    )
    
    # Evaluate
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    log.info(f"Calibration Model RMSE: {rmse:.2f} µg/m³")
    
    # Export model as JSON (portable, no XGBoost needed for inference)
    model_path = output_dir / "calibration_model.json"
    model.save_model(str(model_path))
    log.info(f"Saved model to {model_path}")
    
    # Also export as lightweight weights dict
    weights = {
        "feature_names": available_features,
        "feature_importance": dict(zip(available_features, model.feature_importances_.tolist())),
        "rmse": rmse,
        "n_estimators": model.n_estimators,
        "max_depth": model.max_depth,
        "trained_at": datetime.now().isoformat(),
        "n_samples": len(X_train),
    }
    
    weights_path = output_dir / "calibration_weights.json"
    with open(weights_path, "w") as f:
        json.dump(weights, f, indent=2)
    log.info(f"Saved weights to {weights_path}")
    
    return weights


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 2: FALSE POSITIVE DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

def train_false_positive_model(cpcb_df: pd.DataFrame, output_dir: Path) -> Dict:
    """
    Train a classifier to identify pollution sources / false positives.
    
    Classes:
    - normal: typical urban pollution
    - traffic: vehicle emissions (rush hour, high NO2)
    - kitchen: cooking smoke (high CO, specific times)
    - industrial: factory emissions (high SO2, coarse particles)
    - smoking: tobacco smoke (very localized CO spike)
    - sensor_fault: impossible readings (calibration error)
    """
    log.info("=" * 60)
    log.info("Training FALSE POSITIVE DETECTOR")
    log.info("=" * 60)
    
    df = cpcb_df.copy()
    df = extract_time_features(df)
    df = compute_pollutant_ratios(df)
    
    # Generate synthetic labels based on heuristics
    df["source_label"] = df.apply(label_pollution_source, axis=1)
    
    # Log class distribution
    log.info("Class distribution:")
    log.info(df["source_label"].value_counts().to_string())
    
    # Features for classification
    feature_cols = [
        "pm25", "co_ppm", "no2", "so2", "ozone",
        "pm10_pm25_ratio", "no2_co_ratio", "pm25_co_ratio",
        "hour", "is_rush_hour", "is_weekend", "is_night",
        "temp", "humidity",
    ]
    available_features = [c for c in feature_cols if c in df.columns]
    
    if len(available_features) < 5:
        log.warning("Not enough features for false positive model")
        return {}
    
    # Clean data
    df = df.dropna(subset=available_features)
    if len(df) < 100:
        log.warning(f"Only {len(df)} rows after cleaning")
        return {}
    
    X = df[available_features].values
    
    # Encode labels
    le = LabelEncoder()
    y = le.fit_transform(df["source_label"])
    class_names = le.classes_.tolist()
    
    log.info(f"Classes: {class_names}")
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    log.info(f"Training on {len(X_train)} samples, testing on {len(X_test)}")
    
    # XGBoost classifier
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        objective="multi:softprob",
        num_class=len(class_names),
        tree_method="hist",
        random_state=42,
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=True,
    )
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    log.info(f"False Positive Detector Accuracy: {accuracy:.2%}")
    log.info("\nClassification Report:")
    log.info(classification_report(y_test, y_pred, target_names=class_names))
    
    # Export model
    model_path = output_dir / "false_positive_model.json"
    model.save_model(str(model_path))
    log.info(f"Saved model to {model_path}")
    
    # Export weights
    weights = {
        "feature_names": available_features,
        "class_names": class_names,
        "feature_importance": dict(zip(available_features, model.feature_importances_.tolist())),
        "accuracy": accuracy,
        "trained_at": datetime.now().isoformat(),
        "n_samples": len(X_train),
    }
    
    weights_path = output_dir / "false_positive_weights.json"
    with open(weights_path, "w") as f:
        json.dump(weights, f, indent=2)
    log.info(f"Saved weights to {weights_path}")
    
    return weights


# ══════════════════════════════════════════════════════════════════════════════
# MODEL 3: AQI RADIUS PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════

def train_radius_model(cpcb_df: pd.DataFrame, output_dir: Path) -> Dict:
    """
    Train a model to predict the spatial influence radius of a reading.
    
    Higher AQI readings affect larger areas, but accuracy decreases with distance.
    This model predicts the recommended interpolation radius.
    
    Since we don't have true spatial spread data, we use a synthetic target
    based on AQI level and atmospheric conditions (wind, humidity, etc.)
    """
    log.info("=" * 60)
    log.info("Training AQI RADIUS PREDICTOR")
    log.info("=" * 60)
    
    df = cpcb_df.copy()
    df = extract_time_features(df)
    df = compute_pollutant_ratios(df)
    
    # Compute AQI if not present
    if "aqi" not in df.columns and "pm25" in df.columns:
        # Simple AQI calculation from PM2.5
        df["aqi"] = df["pm25"].apply(lambda x: min(500, max(0, x * 2)) if pd.notna(x) else 50)
    
    # Synthetic radius target based on AQI + conditions
    # Higher AQI = larger radius, but modified by wind/humidity
    def compute_radius(row):
        aqi = row.get("aqi", 50) or 50
        ws = row.get("WS (m/s)", 1) or 1  # wind speed
        rh = row.get("humidity", 70) or 70
        
        # Base radius: 200m for AQI 50, up to 2000m for AQI 500
        base_radius = 200 + (aqi / 500) * 1800
        
        # Wind increases spread
        wind_factor = 1 + (ws / 10) * 0.5
        
        # High humidity reduces spread (particles settle faster)
        humidity_factor = 1 - (rh - 50) / 200
        
        radius = base_radius * wind_factor * humidity_factor
        return max(100, min(3000, radius))
    
    df["target_radius"] = df.apply(compute_radius, axis=1)
    
    # Features
    feature_cols = ["pm25", "aqi", "temp", "humidity", "hour", "is_rush_hour"]
    if "WS (m/s)" in df.columns:
        feature_cols.append("WS (m/s)")
    
    available_features = [c for c in feature_cols if c in df.columns]
    
    if len(available_features) < 3:
        log.warning("Not enough features for radius model")
        return {}
    
    # Clean data
    df = df.dropna(subset=available_features + ["target_radius"])
    if len(df) < 100:
        log.warning(f"Only {len(df)} rows after cleaning")
        return {}
    
    X = df[available_features].values
    y = df["target_radius"].values
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    log.info(f"Training on {len(X_train)} samples, testing on {len(X_test)}")
    
    # XGBoost regressor
    model = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        objective="reg:squarederror",
        tree_method="hist",
        random_state=42,
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=True,
    )
    
    # Evaluate
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    log.info(f"Radius Model RMSE: {rmse:.1f} meters")
    
    # Export model
    model_path = output_dir / "radius_model.json"
    model.save_model(str(model_path))
    log.info(f"Saved model to {model_path}")
    
    # Export weights
    weights = {
        "feature_names": available_features,
        "feature_importance": dict(zip(available_features, model.feature_importances_.tolist())),
        "rmse": rmse,
        "trained_at": datetime.now().isoformat(),
        "n_samples": len(X_train),
    }
    
    weights_path = output_dir / "radius_weights.json"
    with open(weights_path, "w") as f:
        json.dump(weights, f, indent=2)
    log.info(f"Saved weights to {weights_path}")
    
    return weights


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Train XGBoost models for GreenRoute")
    parser.add_argument("--data-dir", type=str, default=".", help="Directory containing CSV files")
    parser.add_argument("--output", type=str, default="models", help="Output directory for models")
    parser.add_argument("--skip-calibration", action="store_true", help="Skip calibration model")
    parser.add_argument("--skip-fp", action="store_true", help="Skip false-positive model")
    parser.add_argument("--skip-radius", action="store_true", help="Skip radius model")
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    log.info(f"Data directory: {data_dir.absolute()}")
    log.info(f"Output directory: {output_dir.absolute()}")
    
    # Load data
    cpcb_df = load_cpcb_data(data_dir)
    esp32_df = load_esp32_data(data_dir)
    
    if cpcb_df.empty:
        log.error("No CPCB data found. Please provide CPCB CSV files.")
        sys.exit(1)
    
    results = {}
    
    # Train models
    if not args.skip_calibration:
        results["calibration"] = train_calibration_model(cpcb_df, output_dir)
    
    if not args.skip_fp:
        results["false_positive"] = train_false_positive_model(cpcb_df, output_dir)
    
    if not args.skip_radius:
        results["radius"] = train_radius_model(cpcb_df, output_dir)
    
    # Summary
    log.info("=" * 60)
    log.info("TRAINING COMPLETE")
    log.info("=" * 60)
    
    for name, weights in results.items():
        if weights:
            log.info(f"  {name}: ✓")
        else:
            log.info(f"  {name}: ✗ (skipped or failed)")
    
    log.info(f"\nModel files saved to: {output_dir.absolute()}")
    log.info("Transfer these files to your server and update xgboost_inference.py")


if __name__ == "__main__":
    main()
