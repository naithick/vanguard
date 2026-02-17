"""
EDA Module - Exploratory Data Analysis for Air Quality Data
Generates reports on raw data quality and statistics
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
import warnings
warnings.filterwarnings('ignore')


class EDAModule:
    """Exploratory Data Analysis for Air Quality Curation"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.report = {}
        
    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive EDA report on raw data"""
        self.report = {
            'basic_info': self._basic_info(),
            'missing_values': self._missing_values_analysis(),
            'statistical_summary': self._statistical_summary(),
            'outlier_detection': self._outlier_detection(),
            'data_quality_score': self._data_quality_score(),
            'sensor_health': self._sensor_health_check(),
            'temporal_analysis': self._temporal_analysis(),
            'correlation_matrix': self._correlation_analysis()
        }
        return self.report
    
    def _basic_info(self) -> Dict[str, Any]:
        """Basic dataset information"""
        return {
            'total_records': len(self.df),
            'total_columns': len(self.df.columns),
            'columns': list(self.df.columns),
            'dtypes': self.df.dtypes.astype(str).to_dict(),
            'memory_usage_mb': self.df.memory_usage(deep=True).sum() / 1024**2
        }
    
    def _missing_values_analysis(self) -> Dict[str, Any]:
        """Analyze missing values in the dataset"""
        missing = self.df.isnull().sum()
        missing_pct = (missing / len(self.df)) * 100
        
        return {
            'missing_counts': missing.to_dict(),
            'missing_percentages': missing_pct.to_dict(),
            'total_missing': int(missing.sum()),
            'columns_with_missing': list(missing[missing > 0].index)
        }
    
    def _statistical_summary(self) -> Dict[str, Any]:
        """Statistical summary for numerical columns"""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        summary = {}
        
        for col in numeric_cols:
            col_data = self.df[col].dropna()
            if len(col_data) > 0:
                summary[col] = {
                    'mean': float(col_data.mean()),
                    'std': float(col_data.std()),
                    'min': float(col_data.min()),
                    'max': float(col_data.max()),
                    'median': float(col_data.median()),
                    'q1': float(col_data.quantile(0.25)),
                    'q3': float(col_data.quantile(0.75)),
                    'skewness': float(col_data.skew()),
                    'kurtosis': float(col_data.kurtosis())
                }
        return summary
    
    def _outlier_detection(self) -> Dict[str, Any]:
        """Detect outliers using IQR method"""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        outliers = {}
        
        for col in numeric_cols:
            col_data = self.df[col].dropna()
            if len(col_data) > 0:
                Q1 = col_data.quantile(0.25)
                Q3 = col_data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                outlier_mask = (col_data < lower_bound) | (col_data > upper_bound)
                outlier_count = outlier_mask.sum()
                
                outliers[col] = {
                    'count': int(outlier_count),
                    'percentage': float((outlier_count / len(col_data)) * 100),
                    'lower_bound': float(lower_bound),
                    'upper_bound': float(upper_bound)
                }
        return outliers
    
    def _data_quality_score(self) -> Dict[str, float]:
        """Calculate overall data quality score"""
        # Completeness score (% of non-null values)
        completeness = (1 - self.df.isnull().sum().sum() / self.df.size) * 100
        
        # Validity score (% of values within expected ranges)
        validity_scores = []
        sensor_ranges = {
            'Dust': (0, 1000),
            'MQ135': (0, 4095),
            'MQ7': (0, 4095),
            'Temperature (°C)': (-40, 85),
            'Humidity (%)': (0, 100),
            'Pressure (hPa)': (300, 1100),
            'Gas (kΩ)': (0, 500)
        }
        
        for col, (min_val, max_val) in sensor_ranges.items():
            # Handle different column name encodings
            matching_col = None
            for df_col in self.df.columns:
                if col.split(' ')[0].lower() in df_col.lower():
                    matching_col = df_col
                    break
            
            if matching_col and matching_col in self.df.columns:
                valid = ((self.df[matching_col] >= min_val) & (self.df[matching_col] <= max_val)).mean()
                validity_scores.append(valid * 100)
        
        validity = np.mean(validity_scores) if validity_scores else 100
        
        # Uniqueness score for timestamps
        if 'Millis' in self.df.columns:
            uniqueness = (self.df['Millis'].nunique() / len(self.df)) * 100
        else:
            uniqueness = 100
        
        overall = (completeness + validity + uniqueness) / 3
        
        return {
            'completeness': float(completeness),
            'validity': float(validity),
            'uniqueness': float(uniqueness),
            'overall_score': float(overall)
        }
    
    def _sensor_health_check(self) -> Dict[str, Any]:
        """Check sensor health based on data patterns"""
        health = {}
        
        # Define sensor columns (handle encoding issues)
        sensor_cols = ['Dust', 'MQ135', 'MQ7']
        
        for col in sensor_cols:
            if col in self.df.columns:
                col_data = self.df[col].dropna()
                if len(col_data) > 0:
                    # Check for stuck values (same value for too long)
                    value_counts = col_data.value_counts()
                    max_repeat_pct = (value_counts.max() / len(col_data)) * 100
                    
                    # Check variance (low variance might indicate sensor issues)
                    variance = col_data.var()
                    
                    # Check for zero readings
                    zero_pct = (col_data == 0).sum() / len(col_data) * 100
                    
                    health[col] = {
                        'status': 'OK' if max_repeat_pct < 50 and variance > 0 else 'WARNING',
                        'max_repeat_percentage': float(max_repeat_pct),
                        'variance': float(variance),
                        'zero_readings_pct': float(zero_pct)
                    }
        return health
    
    def _temporal_analysis(self) -> Dict[str, Any]:
        """Analyze temporal aspects of the data"""
        if 'Millis' not in self.df.columns:
            return {'error': 'No timestamp column found'}
        
        millis = self.df['Millis'].dropna()
        if len(millis) < 2:
            return {'error': 'Insufficient data for temporal analysis'}
        
        # Calculate sampling intervals
        intervals = millis.diff().dropna()
        
        return {
            'duration_seconds': float((millis.max() - millis.min()) / 1000),
            'avg_sampling_interval_ms': float(intervals.mean()),
            'min_interval_ms': float(intervals.min()),
            'max_interval_ms': float(intervals.max()),
            'sampling_rate_hz': float(1000 / intervals.mean()) if intervals.mean() > 0 else 0,
            'irregular_intervals': int((intervals > intervals.mean() * 2).sum())
        }
    
    def _correlation_analysis(self) -> Dict[str, Any]:
        """Analyze correlations between sensor readings"""
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        # Exclude Millis, Latitude, Longitude from correlation
        sensor_cols = [c for c in numeric_cols if c not in ['Millis', 'Latitude', 'Longitude']]
        
        if len(sensor_cols) < 2:
            return {'error': 'Insufficient columns for correlation analysis'}
        
        corr_matrix = self.df[sensor_cols].corr()
        
        # Find highly correlated pairs
        high_corr = []
        for i in range(len(sensor_cols)):
            for j in range(i+1, len(sensor_cols)):
                corr_val = corr_matrix.iloc[i, j]
                if abs(corr_val) > 0.7:
                    high_corr.append({
                        'pair': (sensor_cols[i], sensor_cols[j]),
                        'correlation': float(corr_val)
                    })
        
        return {
            'correlation_matrix': corr_matrix.to_dict(),
            'highly_correlated_pairs': high_corr
        }
    
    def print_report(self):
        """Print formatted EDA report"""
        if not self.report:
            self.generate_report()
        
        print("=" * 60)
        print("EDA REPORT - RAW DATA ANALYSIS")
        print("=" * 60)
        
        # Basic Info
        print("\n📊 BASIC INFORMATION")
        print("-" * 40)
        info = self.report['basic_info']
        print(f"  Total Records: {info['total_records']}")
        print(f"  Total Columns: {info['total_columns']}")
        print(f"  Memory Usage: {info['memory_usage_mb']:.2f} MB")
        
        # Data Quality
        print("\n📈 DATA QUALITY SCORE")
        print("-" * 40)
        quality = self.report['data_quality_score']
        print(f"  Completeness: {quality['completeness']:.1f}%")
        print(f"  Validity: {quality['validity']:.1f}%")
        print(f"  Uniqueness: {quality['uniqueness']:.1f}%")
        print(f"  Overall Score: {quality['overall_score']:.1f}%")
        
        # Missing Values
        print("\n❓ MISSING VALUES")
        print("-" * 40)
        missing = self.report['missing_values']
        if missing['total_missing'] == 0:
            print("  No missing values detected ✓")
        else:
            for col in missing['columns_with_missing']:
                print(f"  {col}: {missing['missing_counts'][col]} ({missing['missing_percentages'][col]:.1f}%)")
        
        # Outliers
        print("\n⚠️  OUTLIERS DETECTED (IQR Method)")
        print("-" * 40)
        for col, stats in self.report['outlier_detection'].items():
            if stats['count'] > 0:
                print(f"  {col}: {stats['count']} outliers ({stats['percentage']:.1f}%)")
        
        # Sensor Health
        print("\n🔧 SENSOR HEALTH CHECK")
        print("-" * 40)
        for sensor, health in self.report['sensor_health'].items():
            status_icon = "✓" if health['status'] == 'OK' else "⚠️"
            print(f"  {sensor}: {health['status']} {status_icon}")
        
        # Temporal Analysis
        print("\n⏱️  TEMPORAL ANALYSIS")
        print("-" * 40)
        temporal = self.report['temporal_analysis']
        if 'error' not in temporal:
            print(f"  Duration: {temporal['duration_seconds']:.1f} seconds")
            print(f"  Avg Sampling Interval: {temporal['avg_sampling_interval_ms']:.1f} ms")
            print(f"  Sampling Rate: {temporal['sampling_rate_hz']:.2f} Hz")
        
        print("\n" + "=" * 60)
        
        return self.report


def run_eda(filepath: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run EDA on a CSV file and return dataframe and report"""
    df = pd.read_csv(filepath)
    eda = EDAModule(df)
    report = eda.generate_report()
    eda.print_report()
    return df, report
