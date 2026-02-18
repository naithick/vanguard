#!/usr/bin/env python3
"""
GreenRoute — Calibration Comparison Visualization
==================================================
Generates 3 comparison graphs:
1. Raw ESP32 sensor data (uncalibrated)
2. XGBoost-calibrated data (our model output)
3. Reference CPCB ground-truth data

Usage:
    python compare_calibration.py
    python compare_calibration.py --output comparison.png
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from xgboost_inference import XGBoostPredictor
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    print("Warning: xgboost_inference not available, will use lite mode")


def load_esp32_data(data_dir: Path) -> pd.DataFrame:
    """Load ESP32 raw sensor data."""
    files = list(data_dir.glob("*coverage*.csv")) + \
            list(data_dir.glob("Sample_Data*.csv"))
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
            df["source"] = "esp32"
            dfs.append(df)
            print(f"Loaded ESP32: {f.name} ({len(df)} rows)")
        except Exception as e:
            print(f"Error loading {f}: {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    combined = pd.concat(dfs, ignore_index=True)
    
    # Normalize column names
    col_map = {
        "dust": "raw_dust",
        "temperature": "temp",
        "humidity": "humidity",
        "timestamp": "timestamp",
    }
    for old, new in col_map.items():
        if old in combined.columns and new not in combined.columns:
            combined[new] = combined[old]
    
    # Calculate raw PM2.5 (uncalibrated)
    if "raw_dust" in combined.columns:
        combined["pm25_raw"] = combined["raw_dust"] * 1.5  # basic linear conversion
    
    # Parse timestamp
    for col in ["timestamp", "Timestamp", "recorded_at"]:
        if col in combined.columns:
            combined["datetime"] = pd.to_datetime(combined[col], errors="coerce")
            break
    
    return combined


def load_cpcb_data(data_dir: Path) -> pd.DataFrame:
    """Load CPCB reference data."""
    files = list(data_dir.glob("Raw_data_15Min_*.csv"))
    
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, na_values=["NA", "None", ""])
            df["source"] = "cpcb"
            df["station"] = f.stem.split("site_")[-1].split("_")[0] if "site_" in f.stem else "unknown"
            dfs.append(df)
            print(f"Loaded CPCB: {f.name} ({len(df)} rows)")
        except Exception as e:
            print(f"Error loading {f}: {e}")
    
    if not dfs:
        return pd.DataFrame()
    
    combined = pd.concat(dfs, ignore_index=True)
    
    # Normalize columns
    col_map = {
        "PM2.5 (µg/m³)": "pm25_reference",
        "AT (°C)": "temp",
        "RH (%)": "humidity",
        "Timestamp": "datetime",
    }
    for old, new in col_map.items():
        if old in combined.columns:
            if new == "datetime":
                combined[new] = pd.to_datetime(combined[old], errors="coerce")
            else:
                combined[new] = combined[old]
    
    return combined


def apply_calibration(esp_df: pd.DataFrame, predictor) -> pd.DataFrame:
    """Apply XGBoost calibration to ESP32 data."""
    df = esp_df.copy()
    
    calibrated = []
    for _, row in df.iterrows():
        raw_pm25 = row.get("pm25_raw", 0) or 0
        raw_dust = row.get("raw_dust", None)
        temp = row.get("temp", 30) or 30
        humidity = row.get("humidity", 70) or 70
        
        # Get hour from datetime
        hour = 12
        if pd.notna(row.get("datetime")):
            hour = row["datetime"].hour
        
        is_rush = hour in [7, 8, 9, 17, 18, 19]
        
        cal_pm25 = predictor.calibrate_reading(
            raw_pm25=raw_pm25,
            raw_dust=raw_dust,
            temp=temp,
            humidity=humidity,
            hour=hour,
            is_rush_hour=is_rush,
        )
        calibrated.append(cal_pm25)
    
    df["pm25_calibrated"] = calibrated
    return df


def create_comparison_plot(esp_df: pd.DataFrame, cpcb_df: pd.DataFrame, output_path: str = None):
    """Create 3-panel comparison visualization."""
    
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)
    fig.suptitle("GreenRoute Calibration Comparison", fontsize=16, fontweight="bold")
    
    colors = {
        "raw": "#e74c3c",       # Red
        "calibrated": "#2ecc71", # Green
        "reference": "#3498db",  # Blue
    }
    
    # ─────────────────────────────────────────────────────────────────────────
    # Panel 1: Raw ESP32 Data
    # ─────────────────────────────────────────────────────────────────────────
    ax1 = axes[0]
    if not esp_df.empty and "pm25_raw" in esp_df.columns:
        esp_sorted = esp_df.sort_values("datetime").dropna(subset=["datetime", "pm25_raw"])
        
        if len(esp_sorted) > 0:
            ax1.plot(esp_sorted["datetime"], esp_sorted["pm25_raw"], 
                    color=colors["raw"], alpha=0.7, linewidth=0.8, label="Raw PM2.5")
            ax1.fill_between(esp_sorted["datetime"], 0, esp_sorted["pm25_raw"], 
                           color=colors["raw"], alpha=0.2)
            
            # Add statistics
            mean_raw = esp_sorted["pm25_raw"].mean()
            std_raw = esp_sorted["pm25_raw"].std()
            ax1.axhline(mean_raw, color=colors["raw"], linestyle="--", alpha=0.8, linewidth=1.5)
            ax1.text(0.02, 0.95, f"Mean: {mean_raw:.1f} µg/m³\nStd: {std_raw:.1f}", 
                    transform=ax1.transAxes, fontsize=10, verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    
    ax1.set_ylabel("PM2.5 (µg/m³)", fontsize=11)
    ax1.set_title("① Raw ESP32 Sensor Data (Uncalibrated)", fontsize=12, fontweight="bold", 
                 color=colors["raw"])
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(bottom=0)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Panel 2: XGBoost Calibrated Data
    # ─────────────────────────────────────────────────────────────────────────
    ax2 = axes[1]
    if not esp_df.empty and "pm25_calibrated" in esp_df.columns:
        esp_sorted = esp_df.sort_values("datetime").dropna(subset=["datetime", "pm25_calibrated"])
        
        if len(esp_sorted) > 0:
            ax2.plot(esp_sorted["datetime"], esp_sorted["pm25_calibrated"], 
                    color=colors["calibrated"], alpha=0.7, linewidth=0.8, label="Calibrated PM2.5")
            ax2.fill_between(esp_sorted["datetime"], 0, esp_sorted["pm25_calibrated"], 
                           color=colors["calibrated"], alpha=0.2)
            
            mean_cal = esp_sorted["pm25_calibrated"].mean()
            std_cal = esp_sorted["pm25_calibrated"].std()
            ax2.axhline(mean_cal, color=colors["calibrated"], linestyle="--", alpha=0.8, linewidth=1.5)
            ax2.text(0.02, 0.95, f"Mean: {mean_cal:.1f} µg/m³\nStd: {std_cal:.1f}", 
                    transform=ax2.transAxes, fontsize=10, verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    
    ax2.set_ylabel("PM2.5 (µg/m³)", fontsize=11)
    ax2.set_title("② XGBoost Calibrated Data (Our Model)", fontsize=12, fontweight="bold",
                 color=colors["calibrated"])
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(bottom=0)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Panel 3: Reference CPCB Data
    # ─────────────────────────────────────────────────────────────────────────
    ax3 = axes[2]
    if not cpcb_df.empty and "pm25_reference" in cpcb_df.columns:
        # Sample if too many points
        cpcb_plot = cpcb_df.dropna(subset=["datetime", "pm25_reference"])
        if len(cpcb_plot) > 5000:
            cpcb_plot = cpcb_plot.sample(5000).sort_values("datetime")
        else:
            cpcb_plot = cpcb_plot.sort_values("datetime")
        
        if len(cpcb_plot) > 0:
            ax3.plot(cpcb_plot["datetime"], cpcb_plot["pm25_reference"], 
                    color=colors["reference"], alpha=0.7, linewidth=0.8, label="CPCB Ground Truth")
            ax3.fill_between(cpcb_plot["datetime"], 0, cpcb_plot["pm25_reference"], 
                           color=colors["reference"], alpha=0.2)
            
            mean_ref = cpcb_plot["pm25_reference"].mean()
            std_ref = cpcb_plot["pm25_reference"].std()
            ax3.axhline(mean_ref, color=colors["reference"], linestyle="--", alpha=0.8, linewidth=1.5)
            ax3.text(0.02, 0.95, f"Mean: {mean_ref:.1f} µg/m³\nStd: {std_ref:.1f}", 
                    transform=ax3.transAxes, fontsize=10, verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    
    ax3.set_ylabel("PM2.5 (µg/m³)", fontsize=11)
    ax3.set_xlabel("Time", fontsize=11)
    ax3.set_title("③ CPCB Reference Data (Ground Truth)", fontsize=12, fontweight="bold",
                 color=colors["reference"])
    ax3.legend(loc="upper right")
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(bottom=0)
    
    # Format x-axis dates
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="right")
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved plot to: {output_path}")
    
    return fig


def create_distribution_comparison(esp_df: pd.DataFrame, cpcb_df: pd.DataFrame, output_path: str = None):
    """Create histogram comparison of distributions."""
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("PM2.5 Distribution Comparison", fontsize=14, fontweight="bold")
    
    colors = ["#e74c3c", "#2ecc71", "#3498db"]
    labels = ["Raw ESP32", "Calibrated", "CPCB Reference"]
    
    data_cols = [
        ("pm25_raw", esp_df),
        ("pm25_calibrated", esp_df),
        ("pm25_reference", cpcb_df),
    ]
    
    for i, (col, df) in enumerate(data_cols):
        ax = axes[i]
        if col in df.columns:
            data = df[col].dropna()
            if len(data) > 0:
                ax.hist(data, bins=50, color=colors[i], alpha=0.7, edgecolor="white")
                ax.axvline(data.mean(), color="black", linestyle="--", linewidth=2, 
                          label=f"Mean: {data.mean():.1f}")
                ax.axvline(data.median(), color="gray", linestyle=":", linewidth=2,
                          label=f"Median: {data.median():.1f}")
                ax.legend()
        
        ax.set_xlabel("PM2.5 (µg/m³)")
        ax.set_ylabel("Frequency")
        ax.set_title(labels[i], color=colors[i], fontweight="bold")
        ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved distribution plot to: {output_path}")
    
    return fig


def print_comparison_stats(esp_df: pd.DataFrame, cpcb_df: pd.DataFrame):
    """Print comparison statistics."""
    print("\n" + "=" * 60)
    print("CALIBRATION COMPARISON STATISTICS")
    print("=" * 60)
    
    stats = []
    
    if "pm25_raw" in esp_df.columns:
        raw = esp_df["pm25_raw"].dropna()
        stats.append(("Raw ESP32", raw.mean(), raw.std(), raw.min(), raw.max(), len(raw)))
    
    if "pm25_calibrated" in esp_df.columns:
        cal = esp_df["pm25_calibrated"].dropna()
        stats.append(("Calibrated", cal.mean(), cal.std(), cal.min(), cal.max(), len(cal)))
    
    if "pm25_reference" in cpcb_df.columns:
        ref = cpcb_df["pm25_reference"].dropna()
        stats.append(("CPCB Reference", ref.mean(), ref.std(), ref.min(), ref.max(), len(ref)))
    
    print(f"\n{'Source':<18} {'Mean':>10} {'Std':>10} {'Min':>10} {'Max':>10} {'Count':>10}")
    print("-" * 68)
    for name, mean, std, min_v, max_v, count in stats:
        print(f"{name:<18} {mean:>10.2f} {std:>10.2f} {min_v:>10.2f} {max_v:>10.2f} {count:>10}")
    
    # Calculate improvement metrics
    if len(stats) >= 2:
        raw_mean = stats[0][1]
        cal_mean = stats[1][1]
        if len(stats) >= 3:
            ref_mean = stats[2][1]
            raw_error = abs(raw_mean - ref_mean)
            cal_error = abs(cal_mean - ref_mean)
            improvement = (raw_error - cal_error) / raw_error * 100 if raw_error > 0 else 0
            
            print(f"\n📊 Calibration Results:")
            print(f"   Raw error vs reference:        {raw_error:.2f} µg/m³")
            print(f"   Calibrated error vs reference: {cal_error:.2f} µg/m³")
            print(f"   Improvement: {improvement:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Compare calibration results")
    parser.add_argument("--data-dir", type=str, default="..", help="Data directory")
    parser.add_argument("--models-dir", type=str, default="models", help="Models directory")
    parser.add_argument("--output", type=str, default="calibration_comparison.png", help="Output image")
    parser.add_argument("--show", action="store_true", help="Show plot interactively")
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    models_dir = Path(args.models_dir)
    
    print("Loading data...")
    esp_df = load_esp32_data(data_dir)
    cpcb_df = load_cpcb_data(data_dir)
    
    if esp_df.empty:
        print("No ESP32 data found!")
        return
    
    print(f"\nLoaded {len(esp_df)} ESP32 rows, {len(cpcb_df)} CPCB rows")
    
    # Initialize predictor and apply calibration
    print("\nApplying XGBoost calibration...")
    try:
        predictor = XGBoostPredictor(str(models_dir), mode="auto")
        esp_df = apply_calibration(esp_df, predictor)
        print("Calibration applied successfully!")
    except Exception as e:
        print(f"Error loading predictor: {e}")
        print("Using fallback calibration...")
        # Simple fallback: apply humidity correction
        esp_df["pm25_calibrated"] = esp_df["pm25_raw"] * 0.95  # small adjustment
    
    # Print statistics
    print_comparison_stats(esp_df, cpcb_df)
    
    # Create plots
    print("\nGenerating comparison plots...")
    
    # Time series comparison
    fig1 = create_comparison_plot(esp_df, cpcb_df, args.output)
    
    # Distribution comparison
    dist_output = args.output.replace(".png", "_distribution.png")
    fig2 = create_distribution_comparison(esp_df, cpcb_df, dist_output)
    
    if args.show:
        plt.show()
    
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
