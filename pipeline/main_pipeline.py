"""
GreenRoute Mesh - Air Quality Data Processing Pipeline
Main pipeline orchestrator for ESP32 sensor data

Pipeline Flow (as per architecture):
    Raw Data → EDA → Pre-processing → Resampling → Processed Data
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime

# Import pipeline modules
from eda_module import EDAModule, run_eda
from preprocessing_module import PreprocessingModule, run_preprocessing
from resampling_module import ResamplingModule, run_resampling


class AirQualityPipeline:
    """
    Complete data processing pipeline for GreenRoute Mesh
    ESP32 Air Quality sensor data processing
    """
    
    # Default column mappings for ESP32 data
    DEFAULT_COLUMNS = {
        'timestamp': 'Millis',
        'dust': 'Dust',
        'mq135': 'MQ135',
        'mq7': 'MQ7',
        'temperature': 'Temperature (°C)',
        'humidity': 'Humidity (%)',
        'pressure': 'Pressure (hPa)',
        'gas': 'Gas (kΩ)',
        'latitude': 'Latitude',
        'longitude': 'Longitude'
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize pipeline with configuration
        
        Args:
            config: Pipeline configuration dictionary
        """
        self.config = config or self._default_config()
        self.eda_module = None
        self.preprocessing_module = None
        self.resampling_module = None
        self.results = {}
        
    def _default_config(self) -> Dict[str, Any]:
        """Default pipeline configuration"""
        return {
            # EDA settings
            'eda': {
                'generate_report': True
            },
            
            # Pre-processing settings
            'preprocessing': {
                'outlier_method': 'iqr',        # 'iqr', 'zscore', 'percentile'
                'outlier_threshold': 1.5,        # IQR multiplier
                'outlier_action': 'clip',        # 'clip', 'remove', 'nan'
                'imputation_method': 'median',   # 'mean', 'median', 'knn', 'interpolate'
                'transformation_method': 'standard',  # 'standard', 'minmax', 'robust'
                'pca_variance_threshold': 0.95,
                'pca_n_components': None,        # None = auto
                'include_pca': True
            },
            
            # Resampling settings
            'resampling': {
                'temporal_interval_ms': 1000,    # 1 second
                'spatial_grid_size': 0.0001,     # ~11 meters
                'aggregation': 'mean',
                'include_temporal': True,
                'include_spatial': True
            },
            
            # Output settings
            'output': {
                'save_intermediate': True,
                'output_dir': 'processed_data',
                'formats': ['csv']  # 'csv', 'json', 'parquet'
            }
        }
    
    def load_data(self, filepath: str) -> pd.DataFrame:
        """Load data from CSV file"""
        print(f"\n📂 Loading data from: {filepath}")
        
        # Try to detect encoding
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        # Clean column names (handle encoding issues)
        df.columns = df.columns.str.strip()
        
        # Standardize common column name variations
        column_mapping = {}
        for col in df.columns:
            col_lower = col.lower()
            if 'temp' in col_lower:
                column_mapping[col] = 'Temperature (°C)'
            elif 'humid' in col_lower:
                column_mapping[col] = 'Humidity (%)'
            elif 'press' in col_lower:
                column_mapping[col] = 'Pressure (hPa)'
            elif 'gas' in col_lower and 'k' in col_lower:
                column_mapping[col] = 'Gas (kΩ)'
        
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        print(f"   Loaded {len(df)} records with {len(df.columns)} columns")
        self.raw_data = df
        return df
    
    def run_eda(self, df: pd.DataFrame = None) -> Dict[str, Any]:
        """Run EDA module"""
        if df is None:
            df = self.raw_data
            
        print("\n" + "=" * 60)
        print("STAGE 1: EXPLORATORY DATA ANALYSIS")
        print("=" * 60)
        
        self.eda_module = EDAModule(df)
        eda_report = self.eda_module.generate_report()
        self.eda_module.print_report()
        
        self.results['eda'] = {
            'report': eda_report,
            'data': df
        }
        
        return eda_report
    
    def run_preprocessing(self, df: pd.DataFrame = None) -> Dict[str, Any]:
        """Run pre-processing module"""
        if df is None:
            df = self.raw_data
            
        print("\n" + "=" * 60)
        print("STAGE 2: PRE-PROCESSING")
        print("=" * 60)
        
        self.preprocessing_module = PreprocessingModule(self.config['preprocessing'])
        
        # Get sensor columns (exclude timestamp and GPS)
        exclude_cols = ['Millis', 'Latitude', 'Longitude']
        sensor_cols = [c for c in df.select_dtypes(include=[np.number]).columns 
                      if c not in exclude_cols]
        
        results = self.preprocessing_module.fit_transform(
            df, 
            sensor_columns=sensor_cols,
            include_pca=self.config['preprocessing']['include_pca']
        )
        self.preprocessing_module.print_report(results)
        
        self.results['preprocessing'] = results
        
        return results
    
    def run_resampling(self, df: pd.DataFrame = None) -> Dict[str, Any]:
        """Run resampling module"""
        if df is None:
            # Use preprocessed data if available
            if 'preprocessing' in self.results:
                df = self.results['preprocessing']['final']
            else:
                df = self.raw_data
        
        print("\n" + "=" * 60)
        print("STAGE 3: SPATIAL & TEMPORAL RESAMPLING")
        print("=" * 60)
        
        self.resampling_module = ResamplingModule(self.config['resampling'])
        
        # Get value columns (sensor readings)
        exclude_cols = ['Millis', 'Latitude', 'Longitude']
        # Also exclude PCA columns for resampling
        exclude_cols += [c for c in df.columns if c.startswith('PC')]
        value_cols = [c for c in df.select_dtypes(include=[np.number]).columns 
                     if c not in exclude_cols]
        
        results = self.resampling_module.process(df, value_columns=value_cols)
        self.resampling_module.print_report(results)
        
        self.results['resampling'] = results
        
        return results
    
    def run_full_pipeline(self, filepath: str = None, df: pd.DataFrame = None) -> Dict[str, Any]:
        """
        Run complete pipeline: EDA → Pre-processing → Resampling
        
        Args:
            filepath: Path to CSV file (optional if df provided)
            df: DataFrame (optional if filepath provided)
        """
        print("\n" + "=" * 70)
        print("🚀 GREENROUTE MESH - AIR QUALITY DATA PROCESSING PIPELINE")
        print("=" * 70)
        print(f"   Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load data
        if df is None:
            if filepath is None:
                raise ValueError("Either filepath or df must be provided")
            df = self.load_data(filepath)
        else:
            self.raw_data = df
        
        # Stage 1: EDA
        self.run_eda(df)
        
        # Stage 2: Pre-processing
        preprocessing_results = self.run_preprocessing(df)
        
        # Stage 3: Resampling (use preprocessed data)
        resampling_results = self.run_resampling(preprocessing_results['final'])
        
        # Final results
        self.results['final'] = resampling_results['final']
        
        # Save outputs
        if self.config['output']['save_intermediate']:
            self._save_outputs()
        
        # Print summary
        self._print_summary()
        
        return self.results
    
    def _save_outputs(self):
        """Save processed data to files"""
        output_dir = Path(self.config['output']['output_dir'])
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        print("\n💾 Saving outputs...")
        
        # Save final processed data
        if 'csv' in self.config['output']['formats']:
            final_path = output_dir / f'processed_data_{timestamp}.csv'
            self.results['final'].to_csv(final_path, index=False)
            print(f"   Saved: {final_path}")
        
        if 'json' in self.config['output']['formats']:
            # Save EDA report as JSON
            report_path = output_dir / f'eda_report_{timestamp}.json'
            with open(report_path, 'w') as f:
                # Convert numpy types to native Python types
                report = self._convert_to_serializable(self.results['eda']['report'])
                json.dump(report, f, indent=2)
            print(f"   Saved: {report_path}")
    
    def _convert_to_serializable(self, obj):
        """Convert numpy types to JSON serializable types"""
        if isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_serializable(v) for v in obj]
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, tuple):
            return list(obj)
        else:
            return obj
    
    def _print_summary(self):
        """Print pipeline summary"""
        print("\n" + "=" * 70)
        print("📊 PIPELINE SUMMARY")
        print("=" * 70)
        
        print(f"\n   Raw Data:        {len(self.raw_data):,} records")
        
        if 'preprocessing' in self.results:
            pp_data = self.results['preprocessing']['final']
            print(f"   After Pre-proc:  {len(pp_data):,} records ({len(pp_data.columns)} columns)")
        
        if 'resampling' in self.results:
            final = self.results['final']
            print(f"   Final Output:    {len(final):,} records ({len(final.columns)} columns)")
        
        # Data reduction
        reduction = (1 - len(self.results['final']) / len(self.raw_data)) * 100
        print(f"\n   Data Reduction:  {reduction:.1f}%")
        
        print(f"\n   Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        print("✅ Pipeline completed successfully!")
        print("=" * 70)
    
    def get_processed_data(self) -> pd.DataFrame:
        """Get final processed dataframe"""
        return self.results.get('final', None)
    
    def get_eda_report(self) -> Dict[str, Any]:
        """Get EDA report"""
        return self.results.get('eda', {}).get('report', None)


def run_pipeline(filepath: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Convenience function to run the full pipeline
    
    Args:
        filepath: Path to CSV data file
        config: Optional configuration dictionary
    
    Returns:
        Dictionary with all pipeline results
    """
    pipeline = AirQualityPipeline(config)
    return pipeline.run_full_pipeline(filepath=filepath)


# Main execution
if __name__ == "__main__":
    import sys
    
    # Default to sample data file
    data_file = sys.argv[1] if len(sys.argv) > 1 else "../ESP32_Air_Quality_Data.csv"
    
    # Run pipeline
    results = run_pipeline(data_file)
    
    # Show final data preview
    print("\n📋 Final Processed Data Preview:")
    print(results['final'].head(10).to_string())
