"""
Resampling Module - Spatial and Temporal Resampling
For mobile air quality data analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from scipy import stats
from scipy.interpolate import griddata
import warnings
warnings.filterwarnings('ignore')


class TemporalResampling:
    """Temporal resampling for time-series sensor data"""
    
    def __init__(self, interval_ms: int = 1000, aggregation: str = 'mean'):
        """
        Args:
            interval_ms: Resampling interval in milliseconds
            aggregation: 'mean', 'median', 'max', 'min', 'sum'
        """
        self.interval_ms = interval_ms
        self.aggregation = aggregation
        
    def resample(self, df: pd.DataFrame, time_column: str = 'Millis',
                 value_columns: List[str] = None) -> pd.DataFrame:
        """
        Resample data to regular time intervals
        
        Args:
            df: Input dataframe
            time_column: Column containing timestamps (milliseconds)
            value_columns: Columns to aggregate (None = all numeric except time)
        """
        df_copy = df.copy()
        
        if value_columns is None:
            value_columns = [c for c in df.select_dtypes(include=[np.number]).columns 
                           if c != time_column]
        
        # Create time bins
        min_time = df_copy[time_column].min()
        max_time = df_copy[time_column].max()
        
        # Create bin edges
        bins = np.arange(min_time, max_time + self.interval_ms, self.interval_ms)
        df_copy['time_bin'] = pd.cut(df_copy[time_column], bins=bins, labels=bins[:-1])
        
        # Aggregate
        agg_funcs = {col: self.aggregation for col in value_columns}
        
        # Handle GPS columns differently (take last valid value in bin)
        for gps_col in ['Latitude', 'Longitude']:
            if gps_col in df_copy.columns:
                agg_funcs[gps_col] = 'last'
        
        df_resampled = df_copy.groupby('time_bin', observed=True).agg(agg_funcs).reset_index()
        df_resampled = df_resampled.rename(columns={'time_bin': time_column})
        df_resampled[time_column] = df_resampled[time_column].astype(float)
        
        return df_resampled
    
    def resample_to_datetime(self, df: pd.DataFrame, time_column: str = 'Millis',
                            freq: str = '1S', start_time: pd.Timestamp = None) -> pd.DataFrame:
        """
        Resample with datetime index
        
        Args:
            df: Input dataframe
            time_column: Column with milliseconds timestamp
            freq: Pandas frequency string (e.g., '1S' for 1 second, '30S' for 30 seconds)
            start_time: Optional start timestamp (defaults to now)
        """
        df_copy = df.copy()
        
        if start_time is None:
            start_time = pd.Timestamp.now()
        
        # Convert millis to datetime
        df_copy['datetime'] = start_time + pd.to_timedelta(df_copy[time_column], unit='ms')
        df_copy = df_copy.set_index('datetime')
        
        # Resample
        numeric_cols = df_copy.select_dtypes(include=[np.number]).columns.tolist()
        
        if self.aggregation == 'mean':
            df_resampled = df_copy[numeric_cols].resample(freq).mean()
        elif self.aggregation == 'median':
            df_resampled = df_copy[numeric_cols].resample(freq).median()
        elif self.aggregation == 'max':
            df_resampled = df_copy[numeric_cols].resample(freq).max()
        elif self.aggregation == 'min':
            df_resampled = df_copy[numeric_cols].resample(freq).min()
        else:
            df_resampled = df_copy[numeric_cols].resample(freq).sum()
        
        return df_resampled.dropna().reset_index()


class SpatialResampling:
    """Spatial resampling and grid-based aggregation for geo-tagged data"""
    
    def __init__(self, grid_size: float = 0.0001, aggregation: str = 'mean'):
        """
        Args:
            grid_size: Grid cell size in degrees (~11m at equator for 0.0001)
            aggregation: 'mean', 'median', 'max', 'min'
        """
        self.grid_size = grid_size
        self.aggregation = aggregation
        
    def create_grid(self, df: pd.DataFrame, lat_col: str = 'Latitude',
                    lon_col: str = 'Longitude') -> Tuple[np.ndarray, np.ndarray]:
        """Create spatial grid based on data extent"""
        # Filter out invalid coordinates (0,0 or NaN)
        valid_mask = (df[lat_col] != 0) & (df[lon_col] != 0) & \
                     df[lat_col].notna() & df[lon_col].notna()
        
        if valid_mask.sum() == 0:
            return None, None
        
        df_valid = df[valid_mask]
        
        lat_min, lat_max = df_valid[lat_col].min(), df_valid[lat_col].max()
        lon_min, lon_max = df_valid[lon_col].min(), df_valid[lon_col].max()
        
        # Create grid
        lat_bins = np.arange(lat_min, lat_max + self.grid_size, self.grid_size)
        lon_bins = np.arange(lon_min, lon_max + self.grid_size, self.grid_size)
        
        return lat_bins, lon_bins
    
    def resample_to_grid(self, df: pd.DataFrame, value_columns: List[str],
                         lat_col: str = 'Latitude', lon_col: str = 'Longitude') -> pd.DataFrame:
        """
        Aggregate data points to grid cells
        
        Args:
            df: Input dataframe with geo-coordinates
            value_columns: Columns to aggregate
            lat_col: Latitude column name
            lon_col: Longitude column name
        """
        df_copy = df.copy()
        
        # Filter invalid coordinates
        valid_mask = (df_copy[lat_col] != 0) & (df_copy[lon_col] != 0) & \
                     df_copy[lat_col].notna() & df_copy[lon_col].notna()
        
        if valid_mask.sum() == 0:
            print("⚠️  No valid GPS coordinates found. Returning original data.")
            return df_copy
        
        df_valid = df_copy[valid_mask].copy()
        
        # Create grid bins
        df_valid['lat_bin'] = (df_valid[lat_col] / self.grid_size).round() * self.grid_size
        df_valid['lon_bin'] = (df_valid[lon_col] / self.grid_size).round() * self.grid_size
        
        # Aggregate by grid cell
        agg_funcs = {col: self.aggregation for col in value_columns if col in df_valid.columns}
        agg_funcs['count'] = (value_columns[0], 'count')  # Add count per cell
        
        df_grid = df_valid.groupby(['lat_bin', 'lon_bin']).agg(
            **{col: (col, self.aggregation) for col in value_columns if col in df_valid.columns},
            sample_count=(value_columns[0], 'count')
        ).reset_index()
        
        df_grid = df_grid.rename(columns={'lat_bin': lat_col, 'lon_bin': lon_col})
        
        return df_grid
    
    def interpolate_to_grid(self, df: pd.DataFrame, value_column: str,
                           lat_col: str = 'Latitude', lon_col: str = 'Longitude',
                           resolution: int = 100, method: str = 'linear') -> Dict[str, np.ndarray]:
        """
        Interpolate scattered data to regular grid (for heatmaps)
        
        Args:
            df: Input dataframe
            value_column: Column to interpolate
            lat_col, lon_col: Coordinate columns
            resolution: Grid resolution (points per axis)
            method: 'linear', 'nearest', 'cubic'
        
        Returns:
            Dictionary with grid arrays for heatmap visualization
        """
        # Filter valid coordinates
        valid_mask = (df[lat_col] != 0) & (df[lon_col] != 0) & \
                     df[lat_col].notna() & df[lon_col].notna() & \
                     df[value_column].notna()
        
        if valid_mask.sum() < 4:
            return {'error': 'Insufficient valid data points for interpolation'}
        
        df_valid = df[valid_mask]
        
        # Create interpolation grid
        lat_min, lat_max = df_valid[lat_col].min(), df_valid[lat_col].max()
        lon_min, lon_max = df_valid[lon_col].min(), df_valid[lon_col].max()
        
        lat_grid = np.linspace(lat_min, lat_max, resolution)
        lon_grid = np.linspace(lon_min, lon_max, resolution)
        lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)
        
        # Interpolate
        points = df_valid[[lon_col, lat_col]].values
        values = df_valid[value_column].values
        
        grid_values = griddata(points, values, (lon_mesh, lat_mesh), method=method)
        
        return {
            'latitude': lat_grid,
            'longitude': lon_grid,
            'lat_mesh': lat_mesh,
            'lon_mesh': lon_mesh,
            'values': grid_values,
            'bounds': {
                'lat_min': lat_min, 'lat_max': lat_max,
                'lon_min': lon_min, 'lon_max': lon_max
            }
        }


class SpatioTemporalResampling:
    """Combined spatial and temporal resampling"""
    
    def __init__(self, temporal_interval_ms: int = 1000, 
                 spatial_grid_size: float = 0.0001,
                 aggregation: str = 'mean'):
        """
        Args:
            temporal_interval_ms: Time interval in milliseconds
            spatial_grid_size: Grid size in degrees
            aggregation: Aggregation method
        """
        self.temporal = TemporalResampling(temporal_interval_ms, aggregation)
        self.spatial = SpatialResampling(spatial_grid_size, aggregation)
        self.aggregation = aggregation
        
    def resample(self, df: pd.DataFrame, value_columns: List[str],
                time_column: str = 'Millis',
                lat_col: str = 'Latitude', lon_col: str = 'Longitude',
                mode: str = 'temporal_first') -> pd.DataFrame:
        """
        Apply spatio-temporal resampling
        
        Args:
            df: Input dataframe
            value_columns: Columns to aggregate
            mode: 'temporal_first', 'spatial_first', 'combined'
        """
        if mode == 'temporal_first':
            # First resample temporally, then spatially
            df_temp = self.temporal.resample(df, time_column, value_columns + [lat_col, lon_col])
            df_result = self.spatial.resample_to_grid(df_temp, value_columns, lat_col, lon_col)
            
        elif mode == 'spatial_first':
            # First resample spatially, then temporally
            df_spatial = self.spatial.resample_to_grid(df, value_columns + [time_column], lat_col, lon_col)
            df_result = self.temporal.resample(df_spatial, time_column, value_columns)
            
        else:  # combined
            # Create spatio-temporal bins
            df_copy = df.copy()
            
            # Temporal binning
            min_time = df_copy[time_column].min()
            time_bins = np.arange(min_time, df_copy[time_column].max() + self.temporal.interval_ms, 
                                 self.temporal.interval_ms)
            df_copy['time_bin'] = pd.cut(df_copy[time_column], bins=time_bins, labels=time_bins[:-1])
            
            # Spatial binning (only for valid coordinates)
            valid_gps = (df_copy[lat_col] != 0) & (df_copy[lon_col] != 0)
            df_copy.loc[valid_gps, 'lat_bin'] = (df_copy.loc[valid_gps, lat_col] / 
                                                  self.spatial.grid_size).round() * self.spatial.grid_size
            df_copy.loc[valid_gps, 'lon_bin'] = (df_copy.loc[valid_gps, lon_col] / 
                                                  self.spatial.grid_size).round() * self.spatial.grid_size
            
            # Aggregate
            group_cols = ['time_bin']
            if valid_gps.any():
                group_cols.extend(['lat_bin', 'lon_bin'])
            
            agg_dict = {col: self.aggregation for col in value_columns if col in df_copy.columns}
            df_result = df_copy.groupby(group_cols, observed=True).agg(agg_dict).reset_index()
        
        return df_result


class ResamplingModule:
    """Complete resampling pipeline module"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: Configuration dictionary
        """
        self.config = config or {
            'temporal_interval_ms': 1000,  # 1 second
            'spatial_grid_size': 0.0001,   # ~11 meters
            'aggregation': 'mean',
            'include_temporal': True,
            'include_spatial': True
        }
        
        self.temporal_resampler = TemporalResampling(
            self.config['temporal_interval_ms'],
            self.config['aggregation']
        )
        self.spatial_resampler = SpatialResampling(
            self.config['spatial_grid_size'],
            self.config['aggregation']
        )
        
    def process(self, df: pd.DataFrame, value_columns: List[str] = None,
               time_column: str = 'Millis',
               lat_col: str = 'Latitude', lon_col: str = 'Longitude') -> Dict[str, Any]:
        """
        Run resampling pipeline
        
        Returns:
            Dictionary with resampled data and metadata
        """
        results = {
            'original': df.copy(),
            'original_count': len(df)
        }
        
        # Auto-detect value columns
        if value_columns is None:
            exclude = [time_column, lat_col, lon_col]
            value_columns = [c for c in df.select_dtypes(include=[np.number]).columns 
                           if c not in exclude]
        
        self.value_columns = value_columns
        df_processed = df.copy()
        
        # Check for valid GPS data
        has_valid_gps = False
        if lat_col in df.columns and lon_col in df.columns:
            valid_gps = (df[lat_col] != 0) & (df[lon_col] != 0) & \
                       df[lat_col].notna() & df[lon_col].notna()
            has_valid_gps = valid_gps.sum() > 0
        
        # Temporal resampling
        if self.config['include_temporal']:
            df_temporal = self.temporal_resampler.resample(
                df_processed, time_column, 
                value_columns + ([lat_col, lon_col] if has_valid_gps else [])
            )
            results['temporal'] = {
                'data': df_temporal,
                'count': len(df_temporal),
                'interval_ms': self.config['temporal_interval_ms']
            }
            df_processed = df_temporal
        
        # Spatial resampling (only if valid GPS data exists)
        if self.config['include_spatial'] and has_valid_gps:
            df_spatial = self.spatial_resampler.resample_to_grid(
                df_processed, value_columns, lat_col, lon_col
            )
            results['spatial'] = {
                'data': df_spatial,
                'count': len(df_spatial),
                'grid_size': self.config['spatial_grid_size']
            }
            results['final'] = df_spatial
        else:
            results['spatial'] = {
                'data': None,
                'message': 'No valid GPS coordinates - spatial resampling skipped'
            }
            results['final'] = df_processed
        
        results['final_count'] = len(results['final'])
        
        return results
    
    def print_report(self, results: Dict[str, Any]):
        """Print resampling report"""
        print("\n" + "=" * 60)
        print("RESAMPLING REPORT")
        print("=" * 60)
        
        print(f"\n📊 Original Data: {results['original_count']} records")
        
        if 'temporal' in results:
            print("\n⏱️  TEMPORAL RESAMPLING")
            print("-" * 40)
            print(f"  Interval: {results['temporal']['interval_ms']} ms")
            print(f"  Records after: {results['temporal']['count']}")
            reduction = (1 - results['temporal']['count'] / results['original_count']) * 100
            print(f"  Reduction: {reduction:.1f}%")
        
        if 'spatial' in results and results['spatial']['data'] is not None:
            print("\n🗺️  SPATIAL RESAMPLING")
            print("-" * 40)
            print(f"  Grid size: {results['spatial']['grid_size']} degrees (~{results['spatial']['grid_size'] * 111000:.0f}m)")
            print(f"  Grid cells: {results['spatial']['count']}")
        elif 'spatial' in results:
            print("\n🗺️  SPATIAL RESAMPLING")
            print("-" * 40)
            print(f"  ⚠️  {results['spatial']['message']}")
        
        print(f"\n✅ Final Data: {results['final_count']} records")
        print("=" * 60)


def run_resampling(df: pd.DataFrame, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run resampling pipeline on dataframe"""
    resampler = ResamplingModule(config)
    results = resampler.process(df)
    resampler.print_report(results)
    return results
