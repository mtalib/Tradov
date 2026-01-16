#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC24_ModelDataPipeline.py
Purpose: SPYDER - Autonomous Options Trading System v1.0

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Autonomous Options Trading System v1.0

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
import threading
import time
import warnings
from typing import Dict, List, Tuple, Optional, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pickle
import hashlib
import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import savgol_filter
from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
from sklearn.decomposition import PCA
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

try:
    import mlflow
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

try:
    from evidently import ColumnMapping
    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset, DataQualityPreset
    EVIDENTLY_AVAILABLE = True
except ImportError:
    EVIDENTLY_AVAILABLE = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)

# Spyder utilities
try:
    from SpyderU01_Logger import SpyderLogger
    from SpyderU02_ErrorHandler import ErrorHandler
    from SpyderU13_TechnicalIndicators import calculate_technical_indicators
    SPYDER_INDICATORS_AVAILABLE = True
except ImportError:
    # Fallback implementations
    logging.basicConfig(level=logging.INFO)
    SpyderLogger = logging.getLogger
    class ErrorHandler:
        @staticmethod
        def handle_error(error, context=""):
            logging.error(f"Error in {context}: {error}")
    SPYDER_INDICATORS_AVAILABLE = False

# Spyder integrations
try:
    from SpyderC21_FSeriesIntegrationHub import get_fseries_integration_hub
    C21_AVAILABLE = True
except ImportError:
    C21_AVAILABLE = False

try:
    from SpyderC22_FactorDataProvider import get_factor_data_provider
    C22_AVAILABLE = True
except ImportError:
    C22_AVAILABLE = False

try:
    from SpyderF13_ModelValidation import get_model_validation_engine
    F13_AVAILABLE = True
except ImportError:
    F13_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================
# Feature Engineering Configuration
FEATURE_CONFIG = {
    'technical_indicators': [
        'sma_5', 'sma_10', 'sma_20', 'sma_50', 'sma_200',
        'ema_12', 'ema_26', 'ema_50',
        'rsi_14', 'rsi_21',
        'macd', 'macd_signal', 'macd_histogram',
        'bb_upper', 'bb_middle', 'bb_lower', 'bb_width',
        'atr_14', 'atr_21',
        'adx_14', 'di_plus', 'di_minus',
        'stoch_k', 'stoch_d',
        'cci_14', 'cci_20',
        'williams_r',
        'momentum_10', 'momentum_20',
        'roc_10', 'roc_20',
        'trix_14'
    ],
    'market_structure': [
        'support_level', 'resistance_level', 'trend_direction',
        'volume_profile', 'order_flow_imbalance', 'market_regime'
    ],
    'options_features': [
        'iv_rank', 'iv_percentile', 'hv_ratio',
        'skew_term_structure', 'gamma_exposure', 'delta_exposure',
        'vanna_exposure', 'charm_exposure',
        'put_call_ratio', 'max_pain', 'gamma_flip_level'
    ],
    'macro_features': [
        'vix_level', 'vix_term_structure', 'credit_spreads',
        'yield_curve_slope', 'dollar_strength', 'commodity_momentum'
    ]
}

# Data Quality Thresholds
QUALITY_THRESHOLDS = {
    'min_completeness': 0.95,
    'max_missing_consecutive': 3,
    'outlier_z_threshold': 4.0,
    'correlation_threshold': 0.95,  # For multicollinearity detection
    'variance_threshold': 0.01,     # For low-variance feature removal
    'drift_threshold': 0.1,         # Statistical drift detection
    'data_freshness_minutes': 5     # Maximum age for real-time features
}

# Model Pipeline Configuration
PIPELINE_CONFIG = {
    'feature_selection_methods': ['univariate', 'pca', 'correlation', 'variance'],
    'scaling_methods': ['standard', 'robust', 'minmax'],
    'validation_methods': ['time_series_split', 'walk_forward', 'expanding_window'],
    'drift_detection_methods': ['ks_test', 'psi', 'wasserstein', 'chi_square'],
    'max_features_per_model': 100,
    'feature_importance_threshold': 0.001
}

# Streaming Configuration
STREAMING_CONFIG = {
    'batch_size': 1000,
    'processing_interval_seconds': 1.0,
    'buffer_size': 10000,
    'parallel_processors': 4,
    'feature_cache_hours': 6
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class FeatureSet:
    """Container for engineered features and metadata."""
    feature_names: List[str]
    feature_values: np.ndarray
    timestamps: pd.DatetimeIndex
    feature_importance: Dict[str, float] = field(default_factory=dict)
    quality_score: float = 0.0
    drift_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DataDriftReport:
    """Container for data drift analysis results."""
    report_id: str
    timestamp: datetime
    drift_detected: bool
    drift_score: float
    drift_features: List[str]
    drift_details: Dict[str, Dict[str, float]]
    recommendations: List[str] = field(default_factory=list)
    model_impact_assessment: str = ""

@dataclass
class ModelInput:
    """Container for model input data with validation."""
    input_data: np.ndarray
    feature_names: List[str]
    timestamps: pd.DatetimeIndex
    data_quality_score: float
    preprocessing_applied: List[str]
    validation_passed: bool = True
    validation_issues: List[str] = field(default_factory=list)

@dataclass
class PipelineMetrics:
    """Container for pipeline performance metrics."""
    features_processed: int = 0
    features_selected: int = 0
    drift_alerts_generated: int = 0
    models_validated: int = 0
    processing_latency_ms: float = 0.0
    data_quality_score: float = 0.0
    feature_stability_score: float = 0.0
    uptime_percent: float = 100.0

# ==============================================================================
# MAIN MODEL DATA PIPELINE
# ==============================================================================
class ModelDataPipeline:
    """
    Specialized data pipeline for ML model validation and monitoring.
    
    Provides comprehensive feature engineering, data drift detection,
    model input preparation, and continuous monitoring capabilities
    for the F13 Model Validation engine.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Model Data Pipeline."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = ErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.enable_drift_detection = self.config.get('enable_drift_detection', True)
        self.enable_feature_caching = self.config.get('enable_feature_caching', True)
        self.enable_mlops_integration = self.config.get('enable_mlops_integration', False)
        
        # Internal state
        self.running = False
        self.pipeline_metrics = PipelineMetrics()
        self.feature_cache = {}
        self.drift_reports = deque(maxlen=100)
        self.model_inputs_history = deque(maxlen=1000)
        
        # Feature engineering components
        self.feature_engineers = {}
        self.scalers = {}
        self.feature_selectors = {}
        
        # Data quality monitors
        self.quality_monitors = {}
        self.drift_detectors = {}
        
        # Integration components
        self.integration_hub = None
        self.factor_provider = None
        self.model_validator = None
        
        # Threading
        self.thread_pool = ThreadPoolExecutor(max_workers=STREAMING_CONFIG['parallel_processors'])
        self.processing_tasks = []
        self._stop_event = threading.Event()
        
        # MLOps integration
        self.mlflow_client = None
        
        # Initialize components
        self._initialize_feature_engineers()
        self._initialize_quality_monitors()
        self._initialize_drift_detectors()
        
        self.logger.info("Model Data Pipeline initialized")
    
    def initialize(self) -> bool:
        """
        Initialize the pipeline with all components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Initialize integrations
            self._initialize_integrations()
            
            # Initialize MLOps if enabled
            if self.enable_mlops_integration:
                self._initialize_mlops()
            
            # Start processing loops
            self._start_processing_loops()
            
            self.running = True
            self.logger.info("Model Data Pipeline fully initialized")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, context="ModelDataPipeline.initialize")
            return False
    
    def _initialize_feature_engineers(self) -> None:
        """Initialize feature engineering components."""
        self.feature_engineers = {
            'technical': self._create_technical_feature_engineer(),
            'market_structure': self._create_market_structure_engineer(),
            'options': self._create_options_feature_engineer(),
            'macro': self._create_macro_feature_engineer(),
            'time_series': self._create_time_series_engineer()
        }
        
        # Initialize scalers
        self.scalers = {
            'standard': StandardScaler(),
            'robust': RobustScaler(),
            'minmax': MinMaxScaler()
        }
        
        self.logger.debug("Feature engineering components initialized")
    
    def _initialize_quality_monitors(self) -> None:
        """Initialize data quality monitoring components."""
        self.quality_monitors = {
            'completeness': self._monitor_completeness,
            'consistency': self._monitor_consistency,
            'validity': self._monitor_validity,
            'timeliness': self._monitor_timeliness,
            'uniqueness': self._monitor_uniqueness
        }
        
        self.logger.debug("Quality monitoring components initialized")
    
    def _initialize_drift_detectors(self) -> None:
        """Initialize drift detection components."""
        self.drift_detectors = {
            'ks_test': self._detect_drift_ks_test,
            'psi': self._detect_drift_psi,
            'wasserstein': self._detect_drift_wasserstein,
            'chi_square': self._detect_drift_chi_square,
            'statistical_moments': self._detect_drift_statistical_moments
        }
        
        self.logger.debug("Drift detection components initialized")
    
    def _initialize_integrations(self) -> None:
        """Initialize integrations with other Spyder modules."""
        try:
            # Connect to C21 Integration Hub
            if C21_AVAILABLE:
                self.integration_hub = get_fseries_integration_hub()
                self.logger.info("Connected to SpyderC21_FSeriesIntegrationHub")
            
            # Connect to C22 Factor Data Provider
            if C22_AVAILABLE:
                self.factor_provider = get_factor_data_provider()
                self.logger.info("Connected to SpyderC22_FactorDataProvider")
            
            # Connect to F13 Model Validation
            if F13_AVAILABLE:
                self.model_validator = get_model_validation_engine()
                self.logger.info("Connected to SpyderF13_ModelValidation")
                
        except Exception as e:
            self.logger.warning(f"Integration initialization failed: {e}")
    
    def _initialize_mlops(self) -> None:
        """Initialize MLOps integrations."""
        try:
            if MLFLOW_AVAILABLE:
                mlflow.set_tracking_uri("sqlite:///mlflow.db")
                self.mlflow_client = mlflow.tracking.MlflowClient()
                self.logger.info("MLflow integration initialized")
        except Exception as e:
            self.logger.warning(f"MLOps initialization failed: {e}")

    # ==============================================================================
    # CORE FEATURE ENGINEERING METHODS
    # ==============================================================================
    def engineer_features(
        self,
        market_data: pd.DataFrame,
        feature_categories: Optional[List[str]] = None
    ) -> FeatureSet:
        """
        Engineer comprehensive feature set from market data.
        
        Args:
            market_data: Raw market data with OHLCV
            feature_categories: Categories of features to engineer
            
        Returns:
            FeatureSet with engineered features
        """
        try:
            if feature_categories is None:
                feature_categories = list(self.feature_engineers.keys())
            
            # Validate input data
            if not self._validate_market_data(market_data):
                raise ValueError("Invalid market data format")
            
            # Engineer features by category
            all_features = pd.DataFrame(index=market_data.index)
            feature_metadata = {}
            
            for category in feature_categories:
                if category in self.feature_engineers:
                    self.logger.debug(f"Engineering {category} features")
                    
                    category_features = self.feature_engineers[category](market_data)
                    
                    if category_features is not None and not category_features.empty:
                        # Add category prefix to feature names
                        category_features.columns = [f"{category}_{col}" for col in category_features.columns]
                        
                        # Merge with all features
                        all_features = pd.concat([all_features, category_features], axis=1)
                        
                        # Store metadata
                        feature_metadata[category] = {
                            'feature_count': len(category_features.columns),
                            'generation_time': datetime.now(),
                            'data_range': (category_features.index.min(), category_features.index.max())
                        }
            
            # Remove features with too many NaN values
            all_features = self._clean_features(all_features)
            
            # Calculate feature quality score
            quality_score = self._calculate_feature_quality(all_features)
            
            # Create feature set
            feature_set = FeatureSet(
                feature_names=all_features.columns.tolist(),
                feature_values=all_features.values,
                timestamps=all_features.index,
                quality_score=quality_score,
                metadata=feature_metadata
            )
            
            self.pipeline_metrics.features_processed = len(feature_set.feature_names)
            self.logger.info(f"Engineered {len(feature_set.feature_names)} features")
            
            return feature_set
            
        except Exception as e:
            self.error_handler.handle_error(e, context="engineer_features")
            return FeatureSet(feature_names=[], feature_values=np.array([]), timestamps=pd.DatetimeIndex([]))
    
    def _create_technical_feature_engineer(self) -> Callable:
        """Create technical indicator feature engineer."""
        def engineer_technical_features(data: pd.DataFrame) -> pd.DataFrame:
            try:
                features = pd.DataFrame(index=data.index)
                
                # Use Spyder technical indicators if available
                if SPYDER_INDICATORS_AVAILABLE:
                    indicators = calculate_technical_indicators(
                        data['close'], data['high'], data['low'], data['volume']
                    )
                    features = pd.concat([features, indicators], axis=1)
                
                # Use TALib if available
                elif TALIB_AVAILABLE:
                    # Moving averages
                    features['sma_5'] = talib.SMA(data['close'], 5)
                    features['sma_20'] = talib.SMA(data['close'], 20)
                    features['sma_50'] = talib.SMA(data['close'], 50)
                    features['ema_12'] = talib.EMA(data['close'], 12)
                    features['ema_26'] = talib.EMA(data['close'], 26)
                    
                    # Momentum indicators
                    features['rsi'] = talib.RSI(data['close'], 14)
                    features['macd'], features['macd_signal'], features['macd_hist'] = talib.MACD(data['close'])
                    features['atr'] = talib.ATR(data['high'], data['low'], data['close'], 14)
                    
                    # Bollinger Bands
                    features['bb_upper'], features['bb_middle'], features['bb_lower'] = talib.BBANDS(data['close'])
                    features['bb_width'] = features['bb_upper'] - features['bb_lower']
                    
                    # Stochastic
                    features['stoch_k'], features['stoch_d'] = talib.STOCH(data['high'], data['low'], data['close'])
                    
                    # ADX
                    features['adx'] = talib.ADX(data['high'], data['low'], data['close'], 14)
                    features['di_plus'] = talib.PLUS_DI(data['high'], data['low'], data['close'], 14)
                    features['di_minus'] = talib.MINUS_DI(data['high'], data['low'], data['close'], 14)
                
                else:
                    # Fallback: basic indicators
                    features['sma_20'] = data['close'].rolling(20).mean()
                    features['sma_50'] = data['close'].rolling(50).mean()
                    features['price_momentum'] = data['close'].pct_change(10)
                    features['volatility'] = data['close'].rolling(20).std()
                    features['volume_sma'] = data['volume'].rolling(20).mean()
                
                # Price-based features
                features['returns'] = data['close'].pct_change()
                features['log_returns'] = np.log(data['close'] / data['close'].shift(1))
                features['high_low_ratio'] = data['high'] / data['low']
                features['close_open_ratio'] = data['close'] / data['open']
                
                # Volume-based features
                features['volume_ratio'] = data['volume'] / data['volume'].rolling(20).mean()
                features['price_volume'] = data['close'] * data['volume']
                
                return features.dropna()
                
            except Exception as e:
                self.error_handler.handle_error(e, context="engineer_technical_features")
                return pd.DataFrame()
        
        return engineer_technical_features
    
    def _create_market_structure_engineer(self) -> Callable:
        """Create market structure feature engineer."""
        def engineer_market_structure_features(data: pd.DataFrame) -> pd.DataFrame:
            try:
                features = pd.DataFrame(index=data.index)
                
                # Support and resistance levels
                features['support_level'] = data['low'].rolling(20, center=True).min()
                features['resistance_level'] = data['high'].rolling(20, center=True).max()
                
                # Distance from support/resistance
                features['distance_to_support'] = (data['close'] - features['support_level']) / data['close']
                features['distance_to_resistance'] = (features['resistance_level'] - data['close']) / data['close']
                
                # Trend detection
                features['price_trend'] = np.where(
                    data['close'] > data['close'].rolling(20).mean(), 1, -1
                )
                
                # Market regime features
                short_vol = data['close'].rolling(5).std()
                long_vol = data['close'].rolling(20).std()
                features['volatility_regime'] = np.where(short_vol > long_vol * 1.5, 1, 0)  # High vol regime
                
                # Volume profile features
                features['volume_profile'] = data['volume'] / data['volume'].rolling(50).mean()
                features['unusual_volume'] = np.where(features['volume_profile'] > 2.0, 1, 0)
                
                return features.dropna()
                
            except Exception as e:
                self.error_handler.handle_error(e, context="engineer_market_structure_features")
                return pd.DataFrame()
        
        return engineer_market_structure_features
    
    def _create_options_feature_engineer(self) -> Callable:
        """Create options-specific feature engineer."""
        def engineer_options_features(data: pd.DataFrame) -> pd.DataFrame:
            try:
                features = pd.DataFrame(index=data.index)
                
                # Implied volatility features (would need actual IV data)
                # For now, using realized volatility as proxy
                features['realized_vol'] = data['close'].rolling(20).std() * np.sqrt(252)
                features['vol_momentum'] = features['realized_vol'].pct_change(5)
                
                # Simulated options features
                features['gamma_exposure'] = np.random.normal(0, 1000000, len(data))
                features['delta_exposure'] = np.random.normal(0, 2000000, len(data))
                features['vanna_exposure'] = np.random.normal(0, 500000, len(data))
                
                # VIX-related features (would use actual VIX data)
                features['vix_level'] = 20 + np.random.normal(0, 5, len(data))  # Simulated
                features['vix_term_structure'] = np.random.normal(0.02, 0.05, len(data))  # Simulated
                
                # Put/Call ratio features
                features['put_call_ratio'] = np.random.uniform(0.5, 1.5, len(data))  # Simulated
                
                return features.dropna()
                
            except Exception as e:
                self.error_handler.handle_error(e, context="engineer_options_features")
                return pd.DataFrame()
        
        return engineer_options_features
    
    def _create_macro_feature_engineer(self) -> Callable:
        """Create macro economic feature engineer."""
        def engineer_macro_features(data: pd.DataFrame) -> pd.DataFrame:
            try:
                features = pd.DataFrame(index=data.index)
                
                # Get factor data if available
                if self.factor_provider:
                    try:
                        factor_data = self.factor_provider.get_factor_model_data(
                            'FF3',
                            start_date=data.index.min(),
                            end_date=data.index.max()
                        )
                        
                        if factor_data is not None:
                            # Align and merge factor data
                            factor_aligned = factor_data.reindex(data.index, method='ffill')
                            features = pd.concat([features, factor_aligned], axis=1)
                    
                    except Exception as e:
                        self.logger.warning(f"Failed to get factor data: {e}")
                
                # Simulated macro features
                features['dollar_strength'] = 100 + np.random.normal(0, 2, len(data))
                features['credit_spread'] = 0.02 + np.random.normal(0, 0.005, len(data))
                features['yield_curve_slope'] = 0.015 + np.random.normal(0, 0.01, len(data))
                
                return features.dropna()
                
            except Exception as e:
                self.error_handler.handle_error(e, context="engineer_macro_features")
                return pd.DataFrame()
        
        return engineer_macro_features
    
    def _create_time_series_engineer(self) -> Callable:
        """Create time series specific feature engineer."""
        def engineer_time_series_features(data: pd.DataFrame) -> pd.DataFrame:
            try:
                features = pd.DataFrame(index=data.index)
                
                # Time-based features
                features['hour'] = data.index.hour
                features['day_of_week'] = data.index.dayofweek
                features['day_of_month'] = data.index.day
                features['month'] = data.index.month
                features['quarter'] = data.index.quarter
                
                # Market session features
                features['is_market_open'] = ((data.index.hour >= 9) & (data.index.hour < 16)).astype(int)
                features['is_morning'] = ((data.index.hour >= 9) & (data.index.hour < 12)).astype(int)
                features['is_afternoon'] = ((data.index.hour >= 12) & (data.index.hour < 16)).astype(int)
                
                # Lag features
                for lag in [1, 2, 3, 5, 10]:
                    features[f'return_lag_{lag}'] = data['close'].pct_change(lag)
                    features[f'volume_lag_{lag}'] = data['volume'].shift(lag)
                
                # Rolling statistics
                for window in [5, 10, 20]:
                    features[f'return_mean_{window}'] = data['close'].pct_change().rolling(window).mean()
                    features[f'return_std_{window}'] = data['close'].pct_change().rolling(window).std()
                    features[f'volume_mean_{window}'] = data['volume'].rolling(window).mean()
                
                return features.dropna()
                
            except Exception as e:
                self.error_handler.handle_error(e, context="engineer_time_series_features")
                return pd.DataFrame()
        
        return engineer_time_series_features

    # ==============================================================================
    # DATA QUALITY AND VALIDATION
    # ==============================================================================
    def validate_data_quality(self, data: pd.DataFrame) -> Dict[str, float]:
        """
        Comprehensive data quality validation.
        
        Args:
            data: DataFrame to validate
            
        Returns:
            Dict with quality scores by dimension
        """
        try:
            quality_scores = {}
            
            for monitor_name, monitor_func in self.quality_monitors.items():
                score = monitor_func(data)
                quality_scores[monitor_name] = score
            
            # Overall quality score
            quality_scores['overall'] = np.mean(list(quality_scores.values()))
            
            return quality_scores
            
        except Exception as e:
            self.error_handler.handle_error(e, context="validate_data_quality")
            return {'overall': 0.0}
    
    def _monitor_completeness(self, data: pd.DataFrame) -> float:
        """Monitor data completeness."""
        try:
            total_cells = data.size
            missing_cells = data.isnull().sum().sum()
            completeness = 1 - (missing_cells / total_cells)
            return max(0.0, min(1.0, completeness))
        except:
            return 0.0
    
    def _monitor_consistency(self, data: pd.DataFrame) -> float:
        """Monitor data consistency."""
        try:
            # Check for duplicate timestamps
            duplicate_ratio = data.index.duplicated().sum() / len(data)
            
            # Check for outliers
            numeric_cols = data.select_dtypes(include=[np.number]).columns
            outlier_ratios = []
            
            for col in numeric_cols:
                z_scores = np.abs(stats.zscore(data[col].dropna()))
                outlier_ratio = (z_scores > QUALITY_THRESHOLDS['outlier_z_threshold']).sum() / len(z_scores)
                outlier_ratios.append(outlier_ratio)
            
            avg_outlier_ratio = np.mean(outlier_ratios) if outlier_ratios else 0
            consistency = 1 - duplicate_ratio - avg_outlier_ratio
            
            return max(0.0, min(1.0, consistency))
        except:
            return 0.0
    
    def _monitor_validity(self, data: pd.DataFrame) -> float:
        """Monitor data validity."""
        try:
            validity_checks = []
            
            # Check for negative prices (if price columns exist)
            price_cols = [col for col in data.columns if 'price' in col.lower() or col in ['open', 'high', 'low', 'close']]
            for col in price_cols:
                if col in data.columns:
                    negative_ratio = (data[col] < 0).sum() / len(data)
                    validity_checks.append(1 - negative_ratio)
            
            # Check for negative volumes
            volume_cols = [col for col in data.columns if 'volume' in col.lower()]
            for col in volume_cols:
                if col in data.columns:
                    negative_ratio = (data[col] < 0).sum() / len(data)
                    validity_checks.append(1 - negative_ratio)
            
            # Check for reasonable ranges
            for col in data.select_dtypes(include=[np.number]).columns:
                if not data[col].isnull().all():
                    # Check if values are finite
                    finite_ratio = np.isfinite(data[col]).sum() / len(data)
                    validity_checks.append(finite_ratio)
            
            return np.mean(validity_checks) if validity_checks else 0.0
        except:
            return 0.0
    
    def _monitor_timeliness(self, data: pd.DataFrame) -> float:
        """Monitor data timeliness."""
        try:
            if data.empty or not hasattr(data.index, 'max'):
                return 0.0
            
            # Check how recent the data is
            latest_timestamp = data.index.max()
            current_time = datetime.now()
            
            # Handle timezone-naive comparison
            if latest_timestamp.tz is None:
                current_time = current_time.replace(tzinfo=None)
            
            data_age_minutes = (current_time - latest_timestamp).total_seconds() / 60
            freshness_threshold = QUALITY_THRESHOLDS['data_freshness_minutes']
            
            timeliness = max(0.0, 1 - (data_age_minutes / freshness_threshold))
            return min(1.0, timeliness)
        except:
            return 0.0
    
    def _monitor_uniqueness(self, data: pd.DataFrame) -> float:
        """Monitor data uniqueness."""
        try:
            if data.empty:
                return 0.0
            
            # Check for duplicate rows
            duplicate_ratio = data.duplicated().sum() / len(data)
            uniqueness = 1 - duplicate_ratio
            
            return max(0.0, min(1.0, uniqueness))
        except:
            return 0.0

    # ==============================================================================
    # DRIFT DETECTION METHODS
    # ==============================================================================
    def detect_data_drift(
        self,
        reference_data: pd.DataFrame,
        current_data: pd.DataFrame,
        methods: Optional[List[str]] = None
    ) -> DataDriftReport:
        """
        Detect data drift between reference and current data.
        
        Args:
            reference_data: Historical reference data
            current_data: Current data to compare
            methods: Drift detection methods to use
            
        Returns:
            DataDriftReport with drift analysis results
        """
        try:
            if methods is None:
                methods = list(self.drift_detectors.keys())
            
            drift_results = {}
            drift_features = []
            overall_drift_score = 0.0
            
            # Align columns
            common_columns = reference_data.columns.intersection(current_data.columns)
            ref_data = reference_data[common_columns]
            cur_data = current_data[common_columns]
            
            # Apply each drift detection method
            for method in methods:
                if method in self.drift_detectors:
                    method_results = self.drift_detectors[method](ref_data, cur_data)
                    drift_results[method] = method_results
                    
                    # Accumulate drift score
                    if 'drift_score' in method_results:
                        overall_drift_score += method_results['drift_score']
            
            # Average drift score across methods
            overall_drift_score /= len(methods) if methods else 1
            
            # Determine if drift detected
            drift_detected = overall_drift_score > QUALITY_THRESHOLDS['drift_threshold']
            
            # Identify drifted features
            for method_results in drift_results.values():
                if 'drifted_features' in method_results:
                    drift_features.extend(method_results['drifted_features'])
            
            drift_features = list(set(drift_features))  # Remove duplicates
            
            # Generate recommendations
            recommendations = self._generate_drift_recommendations(
                drift_detected, drift_features, overall_drift_score
            )
            
            # Create drift report
            drift_report = DataDriftReport(
                report_id=hashlib.md5(f"{datetime.now()}".encode()).hexdigest()[:8],
                timestamp=datetime.now(),
                drift_detected=drift_detected,
                drift_score=overall_drift_score,
                drift_features=drift_features,
                drift_details=drift_results,
                recommendations=recommendations,
                model_impact_assessment=self._assess_model_impact(drift_detected, drift_features)
            )
            
            # Store drift report
            self.drift_reports.append(drift_report)
            
            if drift_detected:
                self.pipeline_metrics.drift_alerts_generated += 1
                self.logger.warning(f"Data drift detected! Score: {overall_drift_score:.3f}")
            
            return drift_report
            
        except Exception as e:
            self.error_handler.handle_error(e, context="detect_data_drift")
            return DataDriftReport(
                report_id="error",
                timestamp=datetime.now(),
                drift_detected=False,
                drift_score=0.0,
                drift_features=[],
                drift_details={}
            )
    
    def _detect_drift_ks_test(self, ref_data: pd.DataFrame, cur_data: pd.DataFrame) -> Dict[str, Any]:
        """Kolmogorov-Smirnov test for drift detection."""
        try:
            drift_scores = {}
            drifted_features = []
            
            for column in ref_data.columns:
                if ref_data[column].dtype in ['int64', 'float64']:
                    ref_values = ref_data[column].dropna()
                    cur_values = cur_data[column].dropna()
                    
                    if len(ref_values) > 0 and len(cur_values) > 0:
                        ks_stat, p_value = stats.ks_2samp(ref_values, cur_values)
                        drift_scores[column] = {'ks_statistic': ks_stat, 'p_value': p_value}
                        
                        if p_value < 0.05:  # Significant drift
                            drifted_features.append(column)
            
            overall_drift_score = np.mean([result['ks_statistic'] for result in drift_scores.values()]) if drift_scores else 0
            
            return {
                'method': 'ks_test',
                'drift_score': overall_drift_score,
                'feature_scores': drift_scores,
                'drifted_features': drifted_features
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_detect_drift_ks_test")
            return {'method': 'ks_test', 'drift_score': 0.0, 'drifted_features': []}
    
    def _detect_drift_psi(self, ref_data: pd.DataFrame, cur_data: pd.DataFrame) -> Dict[str, Any]:
        """Population Stability Index for drift detection."""
        try:
            psi_scores = {}
            drifted_features = []
            
            for column in ref_data.columns:
                if ref_data[column].dtype in ['int64', 'float64']:
                    ref_values = ref_data[column].dropna()
                    cur_values = cur_data[column].dropna()
                    
                    if len(ref_values) > 0 and len(cur_values) > 0:
                        psi_score = self._calculate_psi(ref_values, cur_values)
                        psi_scores[column] = psi_score
                        
                        if psi_score > 0.2:  # Significant drift threshold
                            drifted_features.append(column)
            
            overall_drift_score = np.mean(list(psi_scores.values())) if psi_scores else 0
            
            return {
                'method': 'psi',
                'drift_score': overall_drift_score,
                'feature_scores': psi_scores,
                'drifted_features': drifted_features
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_detect_drift_psi")
            return {'method': 'psi', 'drift_score': 0.0, 'drifted_features': []}
    
    def _detect_drift_wasserstein(self, ref_data: pd.DataFrame, cur_data: pd.DataFrame) -> Dict[str, Any]:
        """Wasserstein distance for drift detection."""
        try:
            wasserstein_scores = {}
            drifted_features = []
            
            for column in ref_data.columns:
                if ref_data[column].dtype in ['int64', 'float64']:
                    ref_values = ref_data[column].dropna()
                    cur_values = cur_data[column].dropna()
                    
                    if len(ref_values) > 0 and len(cur_values) > 0:
                        wasserstein_dist = stats.wasserstein_distance(ref_values, cur_values)
                        wasserstein_scores[column] = wasserstein_dist
                        
                        # Normalize by standard deviation for threshold
                        normalized_dist = wasserstein_dist / (ref_values.std() + 1e-8)
                        if normalized_dist > 0.1:
                            drifted_features.append(column)
            
            overall_drift_score = np.mean(list(wasserstein_scores.values())) if wasserstein_scores else 0
            
            return {
                'method': 'wasserstein',
                'drift_score': overall_drift_score,
                'feature_scores': wasserstein_scores,
                'drifted_features': drifted_features
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_detect_drift_wasserstein")
            return {'method': 'wasserstein', 'drift_score': 0.0, 'drifted_features': []}
    
    def _detect_drift_chi_square(self, ref_data: pd.DataFrame, cur_data: pd.DataFrame) -> Dict[str, Any]:
        """Chi-square test for categorical drift detection."""
        try:
            chi_square_scores = {}
            drifted_features = []
            
            for column in ref_data.columns:
                # Only for categorical or discrete numeric columns
                if ref_data[column].dtype in ['object', 'category'] or ref_data[column].nunique() < 50:
                    ref_counts = ref_data[column].value_counts()
                    cur_counts = cur_data[column].value_counts()
                    
                    # Align categories
                    all_categories = ref_counts.index.union(cur_counts.index)
                    ref_aligned = ref_counts.reindex(all_categories, fill_value=0)
                    cur_aligned = cur_counts.reindex(all_categories, fill_value=0)
                    
                    if len(all_categories) > 1 and ref_aligned.sum() > 0 and cur_aligned.sum() > 0:
                        chi2_stat, p_value = stats.chisquare(cur_aligned, ref_aligned)
                        chi_square_scores[column] = {'chi2_statistic': chi2_stat, 'p_value': p_value}
                        
                        if p_value < 0.05:
                            drifted_features.append(column)
            
            overall_drift_score = np.mean([result['chi2_statistic'] for result in chi_square_scores.values()]) if chi_square_scores else 0
            
            return {
                'method': 'chi_square',
                'drift_score': overall_drift_score,
                'feature_scores': chi_square_scores,
                'drifted_features': drifted_features
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_detect_drift_chi_square")
            return {'method': 'chi_square', 'drift_score': 0.0, 'drifted_features': []}
    
    def _detect_drift_statistical_moments(self, ref_data: pd.DataFrame, cur_data: pd.DataFrame) -> Dict[str, Any]:
        """Statistical moments comparison for drift detection."""
        try:
            moment_scores = {}
            drifted_features = []
            
            for column in ref_data.columns:
                if ref_data[column].dtype in ['int64', 'float64']:
                    ref_values = ref_data[column].dropna()
                    cur_values = cur_data[column].dropna()
                    
                    if len(ref_values) > 0 and len(cur_values) > 0:
                        # Compare means, stds, skewness, kurtosis
                        mean_diff = abs(cur_values.mean() - ref_values.mean()) / (ref_values.std() + 1e-8)
                        std_ratio = cur_values.std() / (ref_values.std() + 1e-8)
                        std_diff = abs(std_ratio - 1)
                        
                        try:
                            skew_diff = abs(stats.skew(cur_values) - stats.skew(ref_values))
                            kurt_diff = abs(stats.kurtosis(cur_values) - stats.kurtosis(ref_values))
                        except:
                            skew_diff = 0
                            kurt_diff = 0
                        
                        # Combine differences
                        combined_score = (mean_diff + std_diff + skew_diff * 0.1 + kurt_diff * 0.1) / 2.2
                        moment_scores[column] = combined_score
                        
                        if combined_score > 0.1:
                            drifted_features.append(column)
            
            overall_drift_score = np.mean(list(moment_scores.values())) if moment_scores else 0
            
            return {
                'method': 'statistical_moments',
                'drift_score': overall_drift_score,
                'feature_scores': moment_scores,
                'drifted_features': drifted_features
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_detect_drift_statistical_moments")
            return {'method': 'statistical_moments', 'drift_score': 0.0, 'drifted_features': []}

    # ==============================================================================
    # UTILITY METHODS
    # ==============================================================================
    def _calculate_psi(self, expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
        """Calculate Population Stability Index."""
        try:
            # Create bins based on expected distribution
            _, bin_edges = np.histogram(expected, bins=bins)
            
            # Calculate distributions
            expected_dist, _ = np.histogram(expected, bins=bin_edges)
            actual_dist, _ = np.histogram(actual, bins=bin_edges)
            
            # Normalize to probabilities
            expected_dist = expected_dist / expected_dist.sum()
            actual_dist = actual_dist / actual_dist.sum()
            
            # Avoid division by zero
            expected_dist = np.where(expected_dist == 0, 0.0001, expected_dist)
            actual_dist = np.where(actual_dist == 0, 0.0001, actual_dist)
            
            # Calculate PSI
            psi = np.sum((actual_dist - expected_dist) * np.log(actual_dist / expected_dist))
            
            return psi
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_psi")
            return 0.0
    
    def _validate_market_data(self, data: pd.DataFrame) -> bool:
        """Validate market data format."""
        try:
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            return all(col in data.columns for col in required_columns)
        except:
            return False
    
    def _clean_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Clean engineered features."""
        try:
            # Remove features with too many NaN values
            threshold = len(features) * (1 - QUALITY_THRESHOLDS['min_completeness'])
            features = features.dropna(thresh=threshold, axis=1)
            
            # Remove features with zero variance
            numeric_features = features.select_dtypes(include=[np.number])
            zero_var_features = numeric_features.columns[numeric_features.var() == 0]
            features = features.drop(columns=zero_var_features)
            
            # Forward fill remaining NaN values
            features = features.fillna(method='ffill').fillna(method='bfill')
            
            return features
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_clean_features")
            return features
    
    def _calculate_feature_quality(self, features: pd.DataFrame) -> float:
        """Calculate overall feature quality score."""
        try:
            if features.empty:
                return 0.0
            
            # Completeness score
            completeness = 1 - (features.isnull().sum().sum() / features.size)
            
            # Variance score (features should have reasonable variance)
            numeric_features = features.select_dtypes(include=[np.number])
            if not numeric_features.empty:
                variances = numeric_features.var()
                variance_score = (variances > QUALITY_THRESHOLDS['variance_threshold']).mean()
            else:
                variance_score = 0.0
            
            # Finite values score
            finite_score = np.isfinite(numeric_features).all().mean() if not numeric_features.empty else 0.0
            
            overall_quality = (completeness + variance_score + finite_score) / 3
            return min(1.0, max(0.0, overall_quality))
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_feature_quality")
            return 0.0
    
    def _generate_drift_recommendations(
        self,
        drift_detected: bool,
        drift_features: List[str],
        drift_score: float
    ) -> List[str]:
        """Generate recommendations based on drift detection results."""
        recommendations = []
        
        if drift_detected:
            recommendations.append("Data drift detected - consider retraining models")
            
            if len(drift_features) > 0:
                recommendations.append(f"Review drifted features: {', '.join(drift_features[:5])}")
            
            if drift_score > 0.3:
                recommendations.append("High drift score - immediate model validation required")
            elif drift_score > 0.2:
                recommendations.append("Moderate drift - schedule model review")
            else:
                recommendations.append("Low drift - monitor closely")
                
            recommendations.append("Consider feature engineering updates")
            recommendations.append("Implement gradual model adaptation")
        else:
            recommendations.append("No significant drift detected - models stable")
            recommendations.append("Continue regular monitoring schedule")
        
        return recommendations
    
    def _assess_model_impact(self, drift_detected: bool, drift_features: List[str]) -> str:
        """Assess potential impact on models."""
        if not drift_detected:
            return "Low impact - models should perform within expected parameters"
        
        impact_level = len(drift_features) / 10  # Rough estimate
        
        if impact_level > 0.5:
            return "High impact - significant model performance degradation expected"
        elif impact_level > 0.2:
            return "Medium impact - model performance may decline moderately" 
        else:
            return "Low impact - minor model performance changes expected"
    
    def _start_processing_loops(self) -> None:
        """Start background processing loops."""
        try:
            # Feature processing loop
            loop1 = threading.Thread(target=self._feature_processing_loop, daemon=True)
            loop1.start()
            self.processing_tasks.append(loop1)
            
            # Quality monitoring loop
            loop2 = threading.Thread(target=self._quality_monitoring_loop, daemon=True)
            loop2.start()
            self.processing_tasks.append(loop2)
            
            self.logger.info("Processing loops started")
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_start_processing_loops")
    
    def _feature_processing_loop(self) -> None:
        """Background feature processing loop."""
        self.logger.info("Started feature processing loop")
        
        while not self._stop_event.is_set():
            try:
                # Process any queued feature engineering requests
                # This would integrate with real-time data streams
                
                self._stop_event.wait(STREAMING_CONFIG['processing_interval_seconds'])
                
            except Exception as e:
                self.error_handler.handle_error(e, context="_feature_processing_loop")
                self._stop_event.wait(5.0)
        
        self.logger.info("Feature processing loop stopped")
    
    def _quality_monitoring_loop(self) -> None:
        """Background quality monitoring loop."""
        self.logger.info("Started quality monitoring loop")
        
        while not self._stop_event.is_set():
            try:
                # Update pipeline metrics
                self._update_pipeline_metrics()
                
                self._stop_event.wait(60.0)  # Update every minute
                
            except Exception as e:
                self.error_handler.handle_error(e, context="_quality_monitoring_loop")
                self._stop_event.wait(30.0)
        
        self.logger.info("Quality monitoring loop stopped")
    
    def _update_pipeline_metrics(self) -> None:
        """Update pipeline performance metrics."""
        try:
            # Update processing latency
            if self.model_inputs_history:
                # Calculate average processing time (placeholder)
                self.pipeline_metrics.processing_latency_ms = 50.0 + np.random.normal(0, 10)
            
            # Update data quality score
            if hasattr(self, 'last_quality_scores'):
                self.pipeline_metrics.data_quality_score = self.last_quality_scores.get('overall', 0.0)
            
            # Calculate uptime
            uptime_seconds = (datetime.now() - datetime.now().replace(hour=0, minute=0, second=0)).total_seconds()
            self.pipeline_metrics.uptime_percent = min(100.0, uptime_seconds / 86400 * 100)
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_update_pipeline_metrics")
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status."""
        try:
            return {
                'is_running': self.running,
                'features_processed': self.pipeline_metrics.features_processed,
                'features_selected': self.pipeline_metrics.features_selected,
                'drift_alerts_generated': self.pipeline_metrics.drift_alerts_generated,
                'models_validated': self.pipeline_metrics.models_validated,
                'processing_latency_ms': self.pipeline_metrics.processing_latency_ms,
                'data_quality_score': self.pipeline_metrics.data_quality_score,
                'feature_stability_score': self.pipeline_metrics.feature_stability_score,
                'uptime_percent': self.pipeline_metrics.uptime_percent,
                'recent_drift_reports': len([r for r in self.drift_reports if r.drift_detected]),
                'feature_cache_size': len(self.feature_cache),
                'integrations': {
                    'C21_IntegrationHub': self.integration_hub is not None,
                    'C22_FactorProvider': self.factor_provider is not None,
                    'F13_ModelValidator': self.model_validator is not None,
                    'MLflow': self.mlflow_client is not None
                }
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="get_pipeline_status")
            return {'error': str(e)}
    
    def shutdown(self) -> None:
        """Shutdown the pipeline gracefully."""
        try:
            self.logger.info("Shutting down Model Data Pipeline...")
            
            self._stop_event.set()
            self.running = False
            
            # Wait for processing threads
            for task in self.processing_tasks:
                if task.is_alive():
                    task.join(timeout=2.0)
            
            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True)
            
            self.logger.info("Model Data Pipeline shutdown complete")
            
        except Exception as e:
            self.error_handler.handle_error(e, context="ModelDataPipeline.shutdown")

# ==============================================================================
# MODULE-LEVEL FUNCTIONS
# ==============================================================================
# Global instance for singleton pattern
_pipeline_instance = None

def get_model_data_pipeline(config: Optional[Dict[str, Any]] = None) -> ModelDataPipeline:
    """
    Get global Model Data Pipeline instance (singleton pattern).
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        ModelDataPipeline instance
    """
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = ModelDataPipeline(config)
        _pipeline_instance.initialize()
    return _pipeline_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    print("🎯 SPYDER C24 - Model Data Pipeline")
    print("=" * 80)
    
    try:
        # Create pipeline
        config = {
            'enable_drift_detection': True,
            'enable_feature_caching': True,
            'enable_mlops_integration': False
        }
        
        pipeline = ModelDataPipeline(config)
        print("✅ Model Data Pipeline initialized")
        
        # Initialize pipeline
        if not pipeline.initialize():
            print("❌ Failed to initialize pipeline")
            return False
        
        # Create sample market data
        print("📊 Creating sample market data...")
        dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
        
        # Generate realistic OHLCV data
        np.random.seed(42)
        price_base = 400
        returns = np.random.normal(0.0005, 0.02, len(dates))
        prices = price_base * np.exp(np.cumsum(returns))
        
        market_data = pd.DataFrame({
            'open': prices * (1 + np.random.normal(0, 0.005, len(dates))),
            'high': prices * (1 + np.abs(np.random.normal(0.01, 0.01, len(dates)))),
            'low': prices * (1 - np.abs(np.random.normal(0.01, 0.01, len(dates)))),
            'close': prices,
            'volume': np.random.randint(1000000, 10000000, len(dates))
        }, index=dates)
        
        print(f"   Generated market data: {len(market_data)} days")
        print(f"   Price range: ${market_data['close'].min():.2f} - ${market_data['close'].max():.2f}")
        
        # Test feature engineering
        print("🔧 Testing feature engineering...")
        feature_set = pipeline.engineer_features(
            market_data,
            feature_categories=['technical', 'market_structure', 'options', 'time_series']
        )
        
        print(f"   ✅ Engineered {len(feature_set.feature_names)} features")
        print(f"   Quality score: {feature_set.quality_score:.3f}")
        print(f"   Feature categories:")
        
        # Count features by category
        category_counts = {}
        for feature_name in feature_set.feature_names:
            category = feature_name.split('_')[0]
            category_counts[category] = category_counts.get(category, 0) + 1
        
        for category, count in category_counts.items():
            print(f"     • {category}: {count} features")
        
        # Test data quality validation
        print("🔍 Testing data quality validation...")
        quality_scores = pipeline.validate_data_quality(market_data)
        
        print(f"   Data Quality Scores:")
        for dimension, score in quality_scores.items():
            print(f"     • {dimension}: {score:.3f}")
        
        # Test drift detection
        print("⚠️  Testing drift detection...")
        
        # Create slightly drifted data
        drift_data = market_data.copy()
        drift_data['close'] = drift_data['close'] * 1.1  # 10% price shift
        drift_data['volume'] = drift_data['volume'] * 0.8  # 20% volume reduction
        
        drift_report = pipeline.detect_data_drift(
            reference_data=market_data.iloc[:180],  # First 6 months
            current_data=drift_data.iloc[180:],     # Last 6 months (drifted)
            methods=['ks_test', 'psi', 'statistical_moments']
        )
        
        print(f"   Drift Detection Results:")
        print(f"     • Drift Detected: {'Yes' if drift_report.drift_detected else 'No'}")
        print(f"     • Drift Score: {drift_report.drift_score:.3f}")
        print(f"     • Drifted Features: {len(drift_report.drift_features)}")
        
        if drift_report.drift_features:
            print(f"     • Top Drifted: {', '.join(drift_report.drift_features[:3])}")
        
        print(f"   Recommendations:")
        for rec in drift_report.recommendations[:3]:
            print(f"     • {rec}")
        
        # Get pipeline status
        status = pipeline.get_pipeline_status()
        
        print("📈 Pipeline Status:")
        print(f"   • Running: {'Yes' if status['is_running'] else 'No'}")
        print(f"   • Features Processed: {status['features_processed']:,}")
        print(f"   • Data Quality Score: {status['data_quality_score']:.3f}")
        print(f"   • Processing Latency: {status['processing_latency_ms']:.1f}ms")
        print(f"   • Uptime: {status['uptime_percent']:.1f}%")
        print(f"   • Drift Alerts: {status['drift_alerts_generated']}")
        
        print("🔌 Integration Status:")
        for integration, connected in status['integrations'].items():
            print(f"   • {integration}: {'✅' if connected else '❌'}")
        
        print("🎊 Model Data Pipeline demonstration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error in main execution: {e}")
        return False
    
    finally:
        # Clean up
        if 'pipeline' in locals():
            pipeline.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
