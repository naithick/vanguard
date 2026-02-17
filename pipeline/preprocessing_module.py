"""
Pre-processing Module - Data cleaning and transformation pipeline
Includes: Outlier Removal → Imputation → Data Transformation → PCA
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer, KNNImputer
import warnings
warnings.filterwarnings('ignore')


class OutlierRemoval:
    """Outlier detection and removal methods"""
    
    def __init__(self, method: str = 'iqr', threshold: float = 1.5):
        """
        Args:
            method: 'iqr', 'zscore', 'isolation_forest', 'clip'
            threshold: IQR multiplier (default 1.5) or Z-score threshold (default 3)
        """
        self.method = method
        self.threshold = threshold
        self.bounds = {}
        
    def fit(self, df: pd.DataFrame, columns: List[str] = None):
        """Fit outlier bounds on training data"""
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        for col in columns:
            if col in df.columns:
                col_data = df[col].dropna()
                
                if self.method == 'iqr':
                    Q1 = col_data.quantile(0.25)
                    Q3 = col_data.quantile(0.75)
                    IQR = Q3 - Q1
                    self.bounds[col] = {
                        'lower': Q1 - self.threshold * IQR,
                        'upper': Q3 + self.threshold * IQR
                    }
                elif self.method == 'zscore':
                    mean = col_data.mean()
                    std = col_data.std()
                    self.bounds[col] = {
                        'lower': mean - self.threshold * std,
                        'upper': mean + self.threshold * std
                    }
                elif self.method == 'percentile':
                    self.bounds[col] = {
                        'lower': col_data.quantile(0.01),
                        'upper': col_data.quantile(0.99)
                    }
        return self
    
    def transform(self, df: pd.DataFrame, action: str = 'clip') -> pd.DataFrame:
        """
        Remove or handle outliers
        
        Args:
            df: DataFrame to transform
            action: 'remove' (drop rows), 'clip' (cap values), 'nan' (replace with NaN)
        """
        df_clean = df.copy()
        
        for col, bounds in self.bounds.items():
            if col in df_clean.columns:
                if action == 'remove':
                    mask = (df_clean[col] >= bounds['lower']) & (df_clean[col] <= bounds['upper'])
                    df_clean = df_clean[mask]
                elif action == 'clip':
                    df_clean[col] = df_clean[col].clip(lower=bounds['lower'], upper=bounds['upper'])
                elif action == 'nan':
                    mask = (df_clean[col] < bounds['lower']) | (df_clean[col] > bounds['upper'])
                    df_clean.loc[mask, col] = np.nan
        
        return df_clean
    
    def fit_transform(self, df: pd.DataFrame, columns: List[str] = None, 
                      action: str = 'clip') -> pd.DataFrame:
        """Fit and transform in one step"""
        self.fit(df, columns)
        return self.transform(df, action)
    
    def get_outlier_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get report of outliers found"""
        report = {}
        for col, bounds in self.bounds.items():
            if col in df.columns:
                outliers = ((df[col] < bounds['lower']) | (df[col] > bounds['upper'])).sum()
                report[col] = {
                    'outlier_count': int(outliers),
                    'outlier_pct': float(outliers / len(df) * 100),
                    'bounds': bounds
                }
        return report


class Imputation:
    """Missing value imputation methods"""
    
    def __init__(self, method: str = 'median', n_neighbors: int = 5):
        """
        Args:
            method: 'mean', 'median', 'mode', 'knn', 'interpolate', 'forward_fill', 'backward_fill'
            n_neighbors: Number of neighbors for KNN imputation
        """
        self.method = method
        self.n_neighbors = n_neighbors
        self.imputer = None
        self.fill_values = {}
        
    def fit(self, df: pd.DataFrame, columns: List[str] = None):
        """Fit imputer on training data"""
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        self.columns = columns
        
        if self.method == 'knn':
            self.imputer = KNNImputer(n_neighbors=self.n_neighbors)
            self.imputer.fit(df[columns])
        elif self.method in ['mean', 'median']:
            self.imputer = SimpleImputer(strategy=self.method)
            self.imputer.fit(df[columns])
        else:
            # Store fill values for other methods
            for col in columns:
                if self.method == 'mode':
                    self.fill_values[col] = df[col].mode().iloc[0] if not df[col].mode().empty else 0
                elif self.method == 'mean':
                    self.fill_values[col] = df[col].mean()
                elif self.method == 'median':
                    self.fill_values[col] = df[col].median()
        
        return self
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply imputation to data"""
        df_imputed = df.copy()
        
        if self.method in ['knn', 'mean', 'median'] and self.imputer is not None:
            df_imputed[self.columns] = self.imputer.transform(df[self.columns])
        elif self.method == 'interpolate':
            df_imputed[self.columns] = df_imputed[self.columns].interpolate(method='linear')
            # Fill remaining NaNs at edges
            df_imputed[self.columns] = df_imputed[self.columns].fillna(method='bfill').fillna(method='ffill')
        elif self.method == 'forward_fill':
            df_imputed[self.columns] = df_imputed[self.columns].fillna(method='ffill')
        elif self.method == 'backward_fill':
            df_imputed[self.columns] = df_imputed[self.columns].fillna(method='bfill')
        else:
            for col, val in self.fill_values.items():
                df_imputed[col] = df_imputed[col].fillna(val)
        
        return df_imputed
    
    def fit_transform(self, df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
        """Fit and transform in one step"""
        self.fit(df, columns)
        return self.transform(df)


class DataTransformation:
    """Data transformation and scaling methods"""
    
    def __init__(self, method: str = 'standard'):
        """
        Args:
            method: 'standard' (z-score), 'minmax' (0-1), 'robust' (median/IQR), 'log', 'sqrt'
        """
        self.method = method
        self.scaler = None
        self.columns = None
        
    def fit(self, df: pd.DataFrame, columns: List[str] = None):
        """Fit scaler on training data"""
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        self.columns = columns
        
        if self.method == 'standard':
            self.scaler = StandardScaler()
        elif self.method == 'minmax':
            self.scaler = MinMaxScaler()
        elif self.method == 'robust':
            self.scaler = RobustScaler()
        
        if self.scaler is not None:
            self.scaler.fit(df[columns])
        
        return self
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply transformation to data"""
        df_transformed = df.copy()
        
        if self.scaler is not None:
            df_transformed[self.columns] = self.scaler.transform(df[self.columns])
        elif self.method == 'log':
            for col in self.columns:
                # Add small constant to handle zeros
                df_transformed[col] = np.log1p(df_transformed[col].clip(lower=0))
        elif self.method == 'sqrt':
            for col in self.columns:
                df_transformed[col] = np.sqrt(df_transformed[col].clip(lower=0))
        
        return df_transformed
    
    def fit_transform(self, df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
        """Fit and transform in one step"""
        self.fit(df, columns)
        return self.transform(df)
    
    def inverse_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reverse the transformation"""
        df_inverse = df.copy()
        
        if self.scaler is not None:
            df_inverse[self.columns] = self.scaler.inverse_transform(df[self.columns])
        elif self.method == 'log':
            for col in self.columns:
                df_inverse[col] = np.expm1(df_inverse[col])
        elif self.method == 'sqrt':
            for col in self.columns:
                df_inverse[col] = df_inverse[col] ** 2
        
        return df_inverse


class PCATransformer:
    """Principal Component Analysis for dimensionality reduction"""
    
    def __init__(self, n_components: Optional[int] = None, variance_threshold: float = 0.95):
        """
        Args:
            n_components: Number of components (None = auto based on variance)
            variance_threshold: Cumulative variance to retain (default 95%)
        """
        self.n_components = n_components
        self.variance_threshold = variance_threshold
        self.pca = None
        self.columns = None
        
    def fit(self, df: pd.DataFrame, columns: List[str] = None):
        """Fit PCA on training data"""
        if columns is None:
            columns = df.select_dtypes(include=[np.number]).columns.tolist()
        
        self.columns = columns
        
        # First fit with all components to determine optimal number
        temp_pca = PCA()
        temp_pca.fit(df[columns])
        
        if self.n_components is None:
            # Find number of components for desired variance
            cumsum = np.cumsum(temp_pca.explained_variance_ratio_)
            self.n_components = np.argmax(cumsum >= self.variance_threshold) + 1
            self.n_components = max(1, min(self.n_components, len(columns)))
        
        self.pca = PCA(n_components=self.n_components)
        self.pca.fit(df[columns])
        
        return self
    
    def transform(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Apply PCA transformation
        
        Returns:
            Tuple of (original df with PCA columns added, PCA-only df)
        """
        pca_values = self.pca.transform(df[self.columns])
        pca_columns = [f'PC{i+1}' for i in range(self.n_components)]
        
        pca_df = pd.DataFrame(pca_values, columns=pca_columns, index=df.index)
        
        # Create combined dataframe (original + PCA)
        df_combined = df.copy()
        for col in pca_columns:
            df_combined[col] = pca_df[col]
        
        return df_combined, pca_df
    
    def fit_transform(self, df: pd.DataFrame, columns: List[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Fit and transform in one step"""
        self.fit(df, columns)
        return self.transform(df)
    
    def get_pca_report(self) -> Dict[str, Any]:
        """Get PCA analysis report"""
        return {
            'n_components': self.n_components,
            'explained_variance_ratio': self.pca.explained_variance_ratio_.tolist(),
            'cumulative_variance': np.cumsum(self.pca.explained_variance_ratio_).tolist(),
            'feature_importance': {
                col: {f'PC{i+1}': float(self.pca.components_[i, j]) 
                      for i in range(self.n_components)}
                for j, col in enumerate(self.columns)
            }
        }


class PreprocessingModule:
    """Complete preprocessing pipeline"""
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Args:
            config: Configuration dictionary with preprocessing parameters
        """
        self.config = config or {
            'outlier_method': 'iqr',
            'outlier_threshold': 1.5,
            'outlier_action': 'clip',
            'imputation_method': 'median',
            'transformation_method': 'standard',
            'pca_variance_threshold': 0.95,
            'pca_n_components': None
        }
        
        self.outlier_remover = None
        self.imputer = None
        self.transformer = None
        self.pca_transformer = None
        self.sensor_columns = None
        
    def fit(self, df: pd.DataFrame, sensor_columns: List[str] = None):
        """Fit all preprocessing components"""
        # Auto-detect sensor columns if not provided
        if sensor_columns is None:
            exclude_cols = ['Millis', 'Latitude', 'Longitude']
            sensor_columns = [c for c in df.select_dtypes(include=[np.number]).columns 
                            if c not in exclude_cols]
        
        self.sensor_columns = sensor_columns
        
        # Initialize components
        self.outlier_remover = OutlierRemoval(
            method=self.config['outlier_method'],
            threshold=self.config['outlier_threshold']
        )
        
        self.imputer = Imputation(
            method=self.config['imputation_method']
        )
        
        self.transformer = DataTransformation(
            method=self.config['transformation_method']
        )
        
        self.pca_transformer = PCATransformer(
            n_components=self.config.get('pca_n_components'),
            variance_threshold=self.config['pca_variance_threshold']
        )
        
        # Fit pipeline sequentially
        df_temp = df.copy()
        
        # 1. Fit outlier remover
        self.outlier_remover.fit(df_temp, sensor_columns)
        df_temp = self.outlier_remover.transform(df_temp, self.config['outlier_action'])
        
        # 2. Fit imputer
        self.imputer.fit(df_temp, sensor_columns)
        df_temp = self.imputer.transform(df_temp)
        
        # 3. Fit transformer
        self.transformer.fit(df_temp, sensor_columns)
        df_temp = self.transformer.transform(df_temp)
        
        # 4. Fit PCA
        self.pca_transformer.fit(df_temp, sensor_columns)
        
        return self
    
    def transform(self, df: pd.DataFrame, include_pca: bool = True) -> Dict[str, Any]:
        """
        Apply full preprocessing pipeline
        
        Returns:
            Dictionary with processed dataframes and reports
        """
        results = {
            'original': df.copy(),
            'stages': {}
        }
        
        df_processed = df.copy()
        
        # 1. Outlier removal
        outlier_report = self.outlier_remover.get_outlier_report(df_processed)
        df_processed = self.outlier_remover.transform(df_processed, self.config['outlier_action'])
        results['stages']['outlier_removal'] = {
            'data': df_processed.copy(),
            'report': outlier_report
        }
        
        # 2. Imputation
        missing_before = df_processed.isnull().sum().sum()
        df_processed = self.imputer.transform(df_processed)
        missing_after = df_processed.isnull().sum().sum()
        results['stages']['imputation'] = {
            'data': df_processed.copy(),
            'report': {
                'missing_before': int(missing_before),
                'missing_after': int(missing_after),
                'values_imputed': int(missing_before - missing_after)
            }
        }
        
        # 3. Data transformation
        df_processed = self.transformer.transform(df_processed)
        results['stages']['transformation'] = {
            'data': df_processed.copy(),
            'report': {
                'method': self.config['transformation_method'],
                'columns_transformed': self.sensor_columns
            }
        }
        
        # 4. PCA (optional)
        if include_pca:
            df_with_pca, pca_df = self.pca_transformer.transform(df_processed)
            results['stages']['pca'] = {
                'data': df_with_pca,
                'pca_only': pca_df,
                'report': self.pca_transformer.get_pca_report()
            }
            results['final'] = df_with_pca
        else:
            results['final'] = df_processed
        
        return results
    
    def fit_transform(self, df: pd.DataFrame, sensor_columns: List[str] = None,
                      include_pca: bool = True) -> Dict[str, Any]:
        """Fit and transform in one step"""
        self.fit(df, sensor_columns)
        return self.transform(df, include_pca)
    
    def print_report(self, results: Dict[str, Any]):
        """Print preprocessing report"""
        print("\n" + "=" * 60)
        print("PRE-PROCESSING REPORT")
        print("=" * 60)
        
        print(f"\n📊 Original Data: {len(results['original'])} records")
        
        # Outlier removal
        print("\n1️⃣  OUTLIER REMOVAL")
        print("-" * 40)
        outlier_report = results['stages']['outlier_removal']['report']
        total_outliers = sum(r['outlier_count'] for r in outlier_report.values())
        print(f"  Method: {self.config['outlier_method'].upper()}")
        print(f"  Action: {self.config['outlier_action']}")
        print(f"  Total outliers handled: {total_outliers}")
        
        # Imputation
        print("\n2️⃣  IMPUTATION")
        print("-" * 40)
        imp_report = results['stages']['imputation']['report']
        print(f"  Method: {self.config['imputation_method']}")
        print(f"  Values imputed: {imp_report['values_imputed']}")
        
        # Transformation
        print("\n3️⃣  DATA TRANSFORMATION")
        print("-" * 40)
        print(f"  Method: {self.config['transformation_method']}")
        print(f"  Columns: {len(self.sensor_columns)}")
        
        # PCA
        if 'pca' in results['stages']:
            print("\n4️⃣  PCA (Dimensionality Reduction)")
            print("-" * 40)
            pca_report = results['stages']['pca']['report']
            print(f"  Components retained: {pca_report['n_components']}")
            total_var = pca_report['cumulative_variance'][-1]
            print(f"  Variance explained: {total_var*100:.1f}%")
        
        print(f"\n✅ Final Data: {len(results['final'])} records, {len(results['final'].columns)} columns")
        print("=" * 60)


def run_preprocessing(df: pd.DataFrame, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Run preprocessing pipeline on dataframe"""
    preprocessor = PreprocessingModule(config)
    results = preprocessor.fit_transform(df)
    preprocessor.print_report(results)
    return results
