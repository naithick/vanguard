"""
GreenRoute Mesh - Air Quality Data Processing Pipeline

Pipeline modules for processing ESP32 air quality sensor data:
- EDA Module: Exploratory Data Analysis and reporting
- Preprocessing Module: Outlier removal, imputation, transformation, PCA
- Resampling Module: Spatial and temporal resampling

Usage:
    from pipeline import AirQualityPipeline, run_pipeline
    
    # Quick run
    results = run_pipeline("data.csv")
    
    # Custom configuration
    pipeline = AirQualityPipeline(config={...})
    results = pipeline.run_full_pipeline("data.csv")
"""

from .eda_module import EDAModule, run_eda
from .preprocessing_module import (
    PreprocessingModule, 
    OutlierRemoval, 
    Imputation, 
    DataTransformation,
    PCATransformer,
    run_preprocessing
)
from .resampling_module import (
    ResamplingModule,
    TemporalResampling,
    SpatialResampling,
    SpatioTemporalResampling,
    run_resampling
)
from .main_pipeline import AirQualityPipeline, run_pipeline

__version__ = "1.0.0"
__all__ = [
    'AirQualityPipeline',
    'run_pipeline',
    'EDAModule',
    'run_eda',
    'PreprocessingModule',
    'OutlierRemoval',
    'Imputation',
    'DataTransformation',
    'PCATransformer',
    'run_preprocessing',
    'ResamplingModule',
    'TemporalResampling',
    'SpatialResampling',
    'SpatioTemporalResampling',
    'run_resampling'
]
