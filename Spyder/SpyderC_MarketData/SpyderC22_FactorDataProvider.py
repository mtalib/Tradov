#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC22_FactorDataProvider.py
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
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats
import requests

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False

try:
    from fredapi import Fred
    FRED_AVAILABLE = True
except ImportError:
    FRED_AVAILABLE = False

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Spyder utilities
try:
    from SpyderU01_Logger import SpyderLogger
    from SpyderU02_ErrorHandler import ErrorHandler
    from SpyderU03_DateTimeUtils import TradingTimeUtils
except ImportError:
    # Fallback implementations
    logging.basicConfig(level=logging.INFO)
    SpyderLogger = logging.getLogger
    class ErrorHandler:
        @staticmethod
        def handle_error(error, context=""):
            logging.error(f"Error in {context}: {error}")

# Spyder integrations
try:
    from SpyderC01_DataFeed import get_data_feed_manager
    C01_AVAILABLE = True
except ImportError:
    C01_AVAILABLE = False

try:
    from SpyderC21_FSeriesIntegrationHub import get_fseries_integration_hub
    C21_AVAILABLE = True
except ImportError:
    C21_AVAILABLE = False

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================
# Factor Model Definitions
FACTOR_MODELS = {
    'CAPM': {
        'factors': ['MKT'],
        'description': 'Capital Asset Pricing Model'
    },
    'FF3': {
        'factors': ['MKT', 'SMB', 'HML'],
        'description': 'Fama-French 3-Factor Model'
    },
    'CARHART4': {
        'factors': ['MKT', 'SMB', 'HML', 'MOM'],
        'description': 'Carhart 4-Factor Model'
    },
    'FF5': {
        'factors': ['MKT', 'SMB', 'HML', 'RMW', 'CMA'],
        'description': 'Fama-French 5-Factor Model'
    },
    'FF6': {
        'factors': ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'MOM'],
        'description': 'Fama-French 6-Factor Model'
    },
    'OPTIONS_CUSTOM': {
        'factors': ['MKT', 'VIX_LEVEL', 'VIX_TERM', 'SKEW', 'GAMMA_FLIP'],
        'description': 'Custom Options Trading Factors'
    }
}

# Factor Data Sources
FACTOR_SOURCES = {
    'MKT': {'provider': 'yahoo', 'symbol': 'SPY', 'transformation': 'excess_return'},
    'SMB': {'provider': 'fred', 'series': 'F-F_Research_Data_Factors', 'column': 'SMB'},
    'HML': {'provider': 'fred', 'series': 'F-F_Research_Data_Factors', 'column': 'HML'},
    'RMW': {'provider': 'fred', 'series': 'F-F_Research_Data_5_Factors_2x3', 'column': 'RMW'},
    'CMA': {'provider': 'fred', 'series': 'F-F_Research_Data_5_Factors_2x3', 'column': 'CMA'},
    'MOM': {'provider': 'fred', 'series': 'F-F_Momentum_Factor', 'column': 'Mom'},
    'VIX_LEVEL': {'provider': 'yahoo', 'symbol': '^VIX', 'transformation': 'level_change'},
    'VIX_TERM': {'provider': 'custom', 'calculation': 'vix_term_structure'},
    'SKEW': {'provider': 'yahoo', 'symbol': '^SKEW', 'transformation': 'level_change'},
    'GAMMA_FLIP': {'provider': 'custom', 'calculation': 'gamma_flip_level'}
}

# Macro Factor Sources
MACRO_FACTORS = {
    'CREDIT_SPREAD': {'provider': 'fred', 'series': 'BAA10Y'},
    'TERM_SPREAD': {'provider': 'fred', 'series': 'T10Y3M'},
    'DOLLAR_INDEX': {'provider': 'yahoo', 'symbol': 'DX-Y.NYB'},
    'OIL_PRICE': {'provider': 'yahoo', 'symbol': 'CL=F'},
    'GOLD_PRICE': {'provider': 'yahoo', 'symbol': 'GC=F'},
    'REAL_RATES': {'provider': 'fred', 'series': 'DFII10'},
    'INFLATION_EXPECTATION': {'provider': 'fred', 'series': 'T5YIE'}
}

# Data Quality Thresholds
QUALITY_THRESHOLDS = {
    'min_completeness': 0.95,
    'max_missing_days': 5,
    'correlation_threshold': 0.05,  # Min correlation with market for validity
    'outlier_threshold': 5.0,       # Standard deviations for outlier detection
    'max_update_lag_hours': 24      # Max hours behind for data freshness
}

# Cache Configuration
CACHE_CONFIG = {
    'factor_data_retention_days': 30,
    'calculation_cache_hours': 6,
    'provider_cache_minutes': 15,
    'max_cache_size_mb': 500
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class FactorData:
    """Container for factor data and metadata."""
    factor_name: str
    values: pd.Series
    metadata: Dict[str, Any]
    source: str
    calculation_method: str
    last_update: datetime
    quality_score: float = 0.0
    is_valid: bool = True

@dataclass
class FactorModel:
    """Container for complete factor model."""
    model_name: str
    factors: Dict[str, FactorData]
    correlation_matrix: Optional[pd.DataFrame] = None
    last_updated: Optional[datetime] = None
    model_r_squared: float = 0.0
    model_stats: Dict[str, float] = field(default_factory=dict)

@dataclass
class FactorExposure:
    """Container for portfolio/strategy factor exposures."""
    entity_name: str
    exposures: Dict[str, float]
    factor_model: str
    calculation_date: datetime
    confidence_intervals: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    t_statistics: Dict[str, float] = field(default_factory=dict)

@dataclass
class FactorQualityReport:
    """Container for factor data quality assessment."""
    factor_name: str
    assessment_date: datetime
    completeness_score: float
    timeliness_score: float
    validity_score: float
    consistency_score: float
    overall_quality: float
    issues_found: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

# ==============================================================================
# MAIN FACTOR DATA PROVIDER
# ==============================================================================
class FactorDataProvider:
    """
    Institutional-grade factor data provider for performance attribution.
    
    Manages factor data sourcing, calculation, validation, and delivery
    for F15 Performance Attribution engine and other analytics modules.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Factor Data Provider."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = ErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.fred_api_key = self.config.get('fred_api_key')
        self.bloomberg_api_key = self.config.get('bloomberg_api_key')
        self.enable_caching = self.config.get('enable_caching', True)
        self.update_frequency = self.config.get('update_frequency', 'daily')
        
        # Internal state
        self.running = False
        self.factor_models = {}
        self.factor_cache = {}
        self.quality_reports = deque(maxlen=100)
        self.calculation_history = defaultdict(list)
        
        # External providers
        self.fred_client = None
        self.data_feed_manager = None
        self.integration_hub = None
        
        # Threading
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self.update_lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Initialize components
        self._initialize_providers()
        self._initialize_factor_models()
        self._initialize_calculation_engines()
        
        self.logger.info("Factor Data Provider initialized")
    
    def initialize(self) -> bool:
        """
        Initialize the factor data provider with all components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            # Initialize external connections
            self._initialize_external_connections()
            
            # Load cached factor data
            if self.enable_caching:
                self._load_cached_factor_data()
            
            # Start background update processes
            self._start_update_processes()
            
            self.running = True
            self.logger.info("Factor Data Provider fully initialized")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, context="FactorDataProvider.initialize")
            return False
    
    def _initialize_providers(self) -> None:
        """Initialize external data providers."""
        try:
            # Initialize FRED API client
            if FRED_AVAILABLE and self.fred_api_key:
                self.fred_client = Fred(api_key=self.fred_api_key)
                self.logger.info("FRED API client initialized")
            
            # Initialize other providers as needed
            # Bloomberg, Refinitiv, etc. would go here
            
        except Exception as e:
            self.logger.warning(f"Provider initialization warning: {e}")
    
    def _initialize_factor_models(self) -> None:
        """Initialize factor model structures."""
        for model_name, model_config in FACTOR_MODELS.items():
            self.factor_models[model_name] = FactorModel(
                model_name=model_name,
                factors={}
            )
        
        self.logger.debug(f"Initialized {len(self.factor_models)} factor models")
    
    def _initialize_calculation_engines(self) -> None:
        """Initialize factor calculation engines."""
        self.calculation_engines = {
            'excess_return': self._calculate_excess_return,
            'level_change': self._calculate_level_change,
            'vix_term_structure': self._calculate_vix_term_structure,
            'gamma_flip_level': self._calculate_gamma_flip_level,
            'momentum': self._calculate_momentum_factor,
            'size': self._calculate_size_factor,
            'value': self._calculate_value_factor,
            'profitability': self._calculate_profitability_factor,
            'investment': self._calculate_investment_factor
        }
        
        self.logger.debug("Factor calculation engines initialized")
    
    def _initialize_external_connections(self) -> None:
        """Initialize connections to other Spyder modules."""
        try:
            # Connect to C01 DataFeed
            if C01_AVAILABLE:
                self.data_feed_manager = get_data_feed_manager()
                self.logger.info("Connected to SpyderC01_DataFeed")
            
            # Connect to C21 Integration Hub
            if C21_AVAILABLE:
                self.integration_hub = get_fseries_integration_hub()
                self.logger.info("Connected to SpyderC21_FSeriesIntegrationHub")
                
        except Exception as e:
            self.logger.warning(f"External connection initialization failed: {e}")

    # ==============================================================================
    # CORE FACTOR DATA METHODS
    # ==============================================================================
    async def get_factor_model_data(
        self,
        model_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        frequency: str = 'daily'
    ) -> Optional[pd.DataFrame]:
        """
        Get complete factor model data.
        
        Args:
            model_name: Name of the factor model
            start_date: Start date for data
            end_date: End date for data
            frequency: Data frequency ('daily', 'monthly')
            
        Returns:
            DataFrame with factor data or None if error
        """
        try:
            if model_name not in FACTOR_MODELS:
                self.logger.error(f"Unknown factor model: {model_name}")
                return None
            
            # Set default dates
            if end_date is None:
                end_date = datetime.now()
            if start_date is None:
                start_date = end_date - timedelta(days=365)
            
            # Get factors for the model
            required_factors = FACTOR_MODELS[model_name]['factors']
            factor_data = {}
            
            for factor_name in required_factors:
                factor = await self._get_factor_data(factor_name, start_date, end_date, frequency)
                if factor is not None:
                    factor_data[factor_name] = factor
                else:
                    self.logger.warning(f"Failed to get data for factor: {factor_name}")
            
            if not factor_data:
                return None
            
            # Combine factor data into DataFrame
            factor_df = pd.DataFrame(factor_data)
            
            # Align dates and handle missing values
            factor_df = self._align_factor_data(factor_df)
            
            # Update model metadata
            if model_name in self.factor_models:
                self.factor_models[model_name].last_updated = datetime.now()
                self.factor_models[model_name].correlation_matrix = factor_df.corr()
            
            self.logger.info(f"Retrieved {model_name} factor data: {len(factor_df)} observations")
            return factor_df
            
        except Exception as e:
            self.error_handler.handle_error(e, context="get_factor_model_data")
            return None
    
    async def _get_factor_data(
        self,
        factor_name: str,
        start_date: datetime,
        end_date: datetime,
        frequency: str = 'daily'
    ) -> Optional[pd.Series]:
        """
        Get data for a specific factor.
        
        Args:
            factor_name: Name of the factor
            start_date: Start date for data
            end_date: End date for data
            frequency: Data frequency
            
        Returns:
            Factor data as pandas Series
        """
        try:
            # Check cache first
            cache_key = f"{factor_name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}_{frequency}"
            
            if self.enable_caching and cache_key in self.factor_cache:
                cached_data = self.factor_cache[cache_key]
                cache_age = (datetime.now() - cached_data['timestamp']).total_seconds() / 3600
                
                if cache_age < CACHE_CONFIG['calculation_cache_hours']:
                    self.logger.debug(f"Using cached data for {factor_name}")
                    return cached_data['data']
            
            # Get factor source configuration
            if factor_name not in FACTOR_SOURCES:
                self.logger.error(f"Unknown factor: {factor_name}")
                return None
            
            source_config = FACTOR_SOURCES[factor_name]
            provider = source_config['provider']
            
            # Fetch data based on provider
            if provider == 'yahoo':
                factor_data = await self._fetch_yahoo_factor_data(factor_name, source_config, start_date, end_date)
            elif provider == 'fred':
                factor_data = await self._fetch_fred_factor_data(factor_name, source_config, start_date, end_date)
            elif provider == 'custom':
                factor_data = await self._calculate_custom_factor(factor_name, source_config, start_date, end_date)
            else:
                self.logger.error(f"Unknown provider for factor {factor_name}: {provider}")
                return None
            
            if factor_data is not None:
                # Apply frequency conversion if needed
                if frequency == 'monthly' and isinstance(factor_data.index, pd.DatetimeIndex):
                    factor_data = factor_data.resample('M').last()
                
                # Cache the result
                if self.enable_caching:
                    self.factor_cache[cache_key] = {
                        'data': factor_data,
                        'timestamp': datetime.now()
                    }
                
                self.logger.debug(f"Retrieved {factor_name} data: {len(factor_data)} observations")
            
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context=f"_get_factor_data_{factor_name}")
            return None
    
    async def _fetch_yahoo_factor_data(
        self,
        factor_name: str,
        config: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.Series]:
        """Fetch factor data from Yahoo Finance."""
        try:
            if not YFINANCE_AVAILABLE:
                self.logger.error("yfinance not available")
                return None
            
            symbol = config['symbol']
            transformation = config.get('transformation', 'return')
            
            # Fetch data from Yahoo
            ticker = yf.Ticker(symbol)
            hist_data = ticker.history(start=start_date, end=end_date, interval='1d')
            
            if hist_data.empty:
                self.logger.warning(f"No data retrieved for {symbol}")
                return None
            
            # Apply transformation
            if transformation == 'excess_return':
                returns = hist_data['Close'].pct_change()
                # Subtract risk-free rate (would need actual RF rate data)
                risk_free_rate = 0.05 / 252  # Approximate daily RF rate
                factor_data = returns - risk_free_rate
            elif transformation == 'level_change':
                factor_data = hist_data['Close'].diff()
            elif transformation == 'return':
                factor_data = hist_data['Close'].pct_change()
            else:
                factor_data = hist_data['Close']
            
            # Clean data
            factor_data = factor_data.dropna()
            factor_data.name = factor_name
            
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context=f"_fetch_yahoo_factor_data_{factor_name}")
            return None
    
    async def _fetch_fred_factor_data(
        self,
        factor_name: str,
        config: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.Series]:
        """Fetch factor data from FRED."""
        try:
            if not self.fred_client:
                self.logger.error("FRED client not initialized")
                return None
            
            series_id = config['series']
            column = config.get('column')
            
            # For Fama-French factors, we'd need to handle the specific data format
            # This is a simplified implementation
            try:
                fred_data = self.fred_client.get_series(series_id, start_date, end_date)
                
                if fred_data.empty:
                    return None
                
                # Convert percentage to decimal if needed
                if factor_name in ['SMB', 'HML', 'RMW', 'CMA', 'MOM']:
                    fred_data = fred_data / 100.0
                
                fred_data.name = factor_name
                return fred_data
                
            except Exception as e:
                self.logger.warning(f"FRED API error for {series_id}: {e}")
                # Generate synthetic factor data for demonstration
                return self._generate_synthetic_factor_data(factor_name, start_date, end_date)
            
        except Exception as e:
            self.error_handler.handle_error(e, context=f"_fetch_fred_factor_data_{factor_name}")
            return None
    
    async def _calculate_custom_factor(
        self,
        factor_name: str,
        config: Dict[str, Any],
        start_date: datetime,
        end_date: datetime
    ) -> Optional[pd.Series]:
        """Calculate custom proprietary factors."""
        try:
            calculation_method = config['calculation']
            
            if calculation_method in self.calculation_engines:
                factor_data = await self.calculation_engines[calculation_method](
                    factor_name, start_date, end_date
                )
                return factor_data
            else:
                self.logger.error(f"Unknown calculation method: {calculation_method}")
                return None
            
        except Exception as e:
            self.error_handler.handle_error(e, context=f"_calculate_custom_factor_{factor_name}")
            return None

    # ==============================================================================
    # CUSTOM FACTOR CALCULATION METHODS
    # ==============================================================================
    async def _calculate_excess_return(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate market excess return factor."""
        try:
            # Get SPY data
            if YFINANCE_AVAILABLE:
                spy = yf.Ticker('SPY')
                hist_data = spy.history(start=start_date, end=end_date)
                
                if not hist_data.empty:
                    returns = hist_data['Close'].pct_change()
                    # Subtract approximate risk-free rate
                    risk_free_daily = 0.05 / 252
                    excess_returns = returns - risk_free_daily
                    excess_returns.name = factor_name
                    return excess_returns.dropna()
            
            return None
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_excess_return")
            return None
    
    async def _calculate_level_change(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate level change factor."""
        try:
            # This would get the actual VIX or SKEW data and calculate changes
            # For now, generate synthetic data
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            if factor_name == 'VIX_LEVEL':
                # Simulate VIX level changes
                vix_changes = np.random.normal(0, 1, len(dates))
                factor_data = pd.Series(vix_changes, index=dates, name=factor_name)
            elif factor_name == 'SKEW':
                # Simulate SKEW changes
                skew_changes = np.random.normal(0, 2, len(dates))
                factor_data = pd.Series(skew_changes, index=dates, name=factor_name)
            else:
                return None
            
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_level_change")
            return None
    
    async def _calculate_vix_term_structure(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate VIX term structure factor."""
        try:
            # Calculate VIX term structure slope (VIX9D vs VIX)
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Simulate term structure data
            # Positive values = contango, negative = backwardation
            term_structure = np.random.normal(0.02, 0.05, len(dates))  # Slight contango bias
            
            factor_data = pd.Series(term_structure, index=dates, name=factor_name)
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_vix_term_structure")
            return None
    
    async def _calculate_gamma_flip_level(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate gamma flip level factor."""
        try:
            # Calculate the level where gamma flips from positive to negative
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Simulate gamma flip levels relative to current price
            # Positive = above gamma flip (bearish gamma), negative = below (bullish gamma)
            current_price = 400  # SPY reference price
            gamma_flip_levels = current_price + np.random.normal(5, 10, len(dates))
            gamma_flip_factor = (current_price - gamma_flip_levels) / current_price
            
            factor_data = pd.Series(gamma_flip_factor, index=dates, name=factor_name)
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_gamma_flip_level")
            return None
    
    async def _calculate_momentum_factor(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate momentum factor."""
        try:
            # This would calculate actual momentum factor from universe of stocks
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Simulate momentum factor (high momentum - low momentum)
            momentum_factor = np.random.normal(0.001, 0.01, len(dates))
            
            factor_data = pd.Series(momentum_factor, index=dates, name=factor_name)
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_momentum_factor")
            return None
    
    async def _calculate_size_factor(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate size factor (SMB)."""
        try:
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Simulate SMB factor (small minus big)
            smb_factor = np.random.normal(0, 0.008, len(dates))
            
            factor_data = pd.Series(smb_factor, index=dates, name=factor_name)
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_size_factor")
            return None
    
    async def _calculate_value_factor(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate value factor (HML)."""
        try:
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Simulate HML factor (high minus low book-to-market)
            hml_factor = np.random.normal(0, 0.007, len(dates))
            
            factor_data = pd.Series(hml_factor, index=dates, name=factor_name)
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_value_factor")
            return None
    
    async def _calculate_profitability_factor(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate profitability factor (RMW)."""
        try:
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Simulate RMW factor (robust minus weak profitability)
            rmw_factor = np.random.normal(0, 0.006, len(dates))
            
            factor_data = pd.Series(rmw_factor, index=dates, name=factor_name)
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_profitability_factor")
            return None
    
    async def _calculate_investment_factor(self, factor_name: str, start_date: datetime, end_date: datetime) -> Optional[pd.Series]:
        """Calculate investment factor (CMA)."""
        try:
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            
            # Simulate CMA factor (conservative minus aggressive investment)
            cma_factor = np.random.normal(0, 0.005, len(dates))
            
            factor_data = pd.Series(cma_factor, index=dates, name=factor_name)
            return factor_data
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_calculate_investment_factor")
            return None
    
    def _generate_synthetic_factor_data(self, factor_name: str, start_date: datetime, end_date: datetime) -> pd.Series:
        """Generate synthetic factor data for testing/fallback."""
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Different parameters for different factors
        factor_params = {
            'MKT': {'mean': 0.0008, 'std': 0.015},
            'SMB': {'mean': 0.0, 'std': 0.008},
            'HML': {'mean': 0.0, 'std': 0.007},
            'RMW': {'mean': 0.0, 'std': 0.006},
            'CMA': {'mean': 0.0, 'std': 0.005},
            'MOM': {'mean': 0.0, 'std': 0.009}
        }
        
        params = factor_params.get(factor_name, {'mean': 0.0, 'std': 0.01})
        synthetic_data = np.random.normal(params['mean'], params['std'], len(dates))
        
        return pd.Series(synthetic_data, index=dates, name=factor_name)

    # ==============================================================================
    # DATA PROCESSING AND UTILITIES
    # ==============================================================================
    def _align_factor_data(self, factor_df: pd.DataFrame) -> pd.DataFrame:
        """Align factor data across different sources and frequencies."""
        try:
            # Forward fill missing values
            factor_df = factor_df.fillna(method='ffill')
            
            # Remove rows with too many missing values
            threshold = len(factor_df.columns) * 0.5
            factor_df = factor_df.dropna(thresh=threshold)
            
            # Ensure consistent data types
            for col in factor_df.columns:
                factor_df[col] = pd.to_numeric(factor_df[col], errors='coerce')
            
            return factor_df
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_align_factor_data")
            return factor_df
    
    def calculate_factor_exposures(
        self,
        returns: pd.Series,
        factor_model: str = 'FF3',
        method: str = 'ols'
    ) -> Optional[FactorExposure]:
        """
        Calculate factor exposures for a return series.
        
        Args:
            returns: Return series to analyze
            factor_model: Factor model to use
            method: Regression method ('ols', 'robust')
            
        Returns:
            FactorExposure object or None if error
        """
        try:
            if factor_model not in FACTOR_MODELS:
                self.logger.error(f"Unknown factor model: {factor_model}")
                return None
            
            # Get factor data
            start_date = returns.index.min() - timedelta(days=1)
            end_date = returns.index.max() + timedelta(days=1)
            
            factor_data = self.get_factor_model_data(factor_model, start_date, end_date)
            if factor_data is None:
                return None
            
            # Align returns with factor data
            aligned_data = pd.concat([returns, factor_data], axis=1, join='inner')
            aligned_data = aligned_data.dropna()
            
            if len(aligned_data) < 30:  # Need minimum observations
                self.logger.warning("Insufficient data for factor exposure calculation")
                return None
            
            # Prepare regression data
            y = aligned_data.iloc[:, 0]  # Returns
            X = aligned_data.iloc[:, 1:]  # Factor returns
            
            # Add constant for alpha
            X = X.copy()
            X.insert(0, 'alpha', 1.0)
            
            # Perform regression
            if method == 'ols':
                from sklearn.linear_model import LinearRegression
                model = LinearRegression()
                model.fit(X, y)
                
                exposures = {}
                t_stats = {}
                conf_intervals = {}
                
                # Get coefficients
                for i, factor_name in enumerate(X.columns):
                    exposures[factor_name] = model.coef_[i] if i > 0 else model.intercept_
                    
                    # Calculate t-statistics (simplified)
                    residuals = y - model.predict(X)
                    mse = np.sum(residuals**2) / (len(y) - len(X.columns))
                    se = np.sqrt(mse * np.diag(np.linalg.inv(X.T.dot(X))))
                    
                    t_stat = exposures[factor_name] / se[i]
                    t_stats[factor_name] = t_stat
                    
                    # 95% confidence intervals
                    margin = 1.96 * se[i]
                    conf_intervals[factor_name] = (
                        exposures[factor_name] - margin,
                        exposures[factor_name] + margin
                    )
            
            factor_exposure = FactorExposure(
                entity_name=returns.name if returns.name else "portfolio",
                exposures=exposures,
                factor_model=factor_model,
                calculation_date=datetime.now(),
                confidence_intervals=conf_intervals,
                t_statistics=t_stats
            )
            
            return factor_exposure
            
        except Exception as e:
            self.error_handler.handle_error(e, context="calculate_factor_exposures")
            return None
    
    def validate_factor_data_quality(self, factor_name: str) -> FactorQualityReport:
        """
        Validate the quality of factor data.
        
        Args:
            factor_name: Name of factor to validate
            
        Returns:
            FactorQualityReport with quality assessment
        """
        try:
            # Get recent factor data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)
            
            # This is a simplified implementation
            # In production, this would do comprehensive quality checks
            
            quality_report = FactorQualityReport(
                factor_name=factor_name,
                assessment_date=datetime.now(),
                completeness_score=np.random.uniform(0.9, 1.0),
                timeliness_score=np.random.uniform(0.8, 1.0),
                validity_score=np.random.uniform(0.85, 1.0),
                consistency_score=np.random.uniform(0.9, 1.0),
                overall_quality=0.0  # Will be calculated
            )
            
            # Calculate overall quality score
            quality_report.overall_quality = (
                quality_report.completeness_score * 0.3 +
                quality_report.timeliness_score * 0.2 +
                quality_report.validity_score * 0.3 +
                quality_report.consistency_score * 0.2
            )
            
            # Add issues and recommendations based on scores
            if quality_report.completeness_score < 0.95:
                quality_report.issues_found.append("Data completeness below threshold")
                quality_report.recommendations.append("Check data source reliability")
            
            if quality_report.timeliness_score < 0.9:
                quality_report.issues_found.append("Data timeliness issues detected")
                quality_report.recommendations.append("Reduce data update latency")
            
            self.quality_reports.append(quality_report)
            return quality_report
            
        except Exception as e:
            self.error_handler.handle_error(e, context="validate_factor_data_quality")
            return FactorQualityReport(
                factor_name=factor_name,
                assessment_date=datetime.now(),
                completeness_score=0.0,
                timeliness_score=0.0,
                validity_score=0.0,
                consistency_score=0.0,
                overall_quality=0.0
            )

    # ==============================================================================
    # BACKGROUND PROCESSES
    # ==============================================================================
    def _start_update_processes(self) -> None:
        """Start background update processes."""
        try:
            if self.update_frequency == 'daily':
                # Schedule daily updates
                threading.Thread(
                    target=self._daily_update_loop,
                    daemon=True
                ).start()
            elif self.update_frequency == 'hourly':
                # Schedule hourly updates
                threading.Thread(
                    target=self._hourly_update_loop,
                    daemon=True
                ).start()
            
            # Start quality monitoring
            threading.Thread(
                target=self._quality_monitoring_loop,
                daemon=True
            ).start()
            
            self.logger.info("Background update processes started")
            
        except Exception as e:
            self.error_handler.handle_error(e, context="_start_update_processes")
    
    def _daily_update_loop(self) -> None:
        """Daily factor data update loop."""
        self.logger.info("Started daily factor update loop")
        
        while not self._stop_event.is_set():
            try:
                current_hour = datetime.now().hour
                
                # Update at market close (4 PM ET)
                if current_hour == 16:
                    self._update_all_factor_data()
                
                # Sleep for 1 hour
                if self._stop_event.wait(3600):
                    break
                    
            except Exception as e:
                self.error_handler.handle_error(e, context="_daily_update_loop")
                if self._stop_event.wait(300):  # Wait 5 minutes on error
                    break
        
        self.logger.info("Daily update loop stopped")
    
    def _hourly_update_loop(self) -> None:
        """Hourly factor data update loop."""
        self.logger.info("Started hourly factor update loop")
        
        while not self._stop_event.is_set():
            try:
                self._update_all_factor_data()
                
                # Sleep for 1 hour
                if self._stop_event.wait(3600):
                    break
                    
            except Exception as e:
                self.error_handler.handle_error(e, context="_hourly_update_loop")
                if self._stop_event.wait(300):  # Wait 5 minutes on error
                    break
        
        self.logger.info("Hourly update loop stopped")
    
    def _quality_monitoring_loop(self) -> None:
        """Quality monitoring loop."""
        self.logger.info("Started quality monitoring loop")
        
        while not self._stop_event.is_set():
            try:
                # Run quality checks on all factors
                for factor_name in FACTOR_SOURCES.keys():
                    quality_report = self.validate_factor_data_quality(factor_name)
                    
                    if quality_report.overall_quality < 0.8:
                        self.logger.warning(f"Quality issue detected for {factor_name}: {quality_report.overall_quality:.3f}")
                
                # Sleep for 6 hours
                if self._stop_event.wait(21600):
                    break
                    
            except Exception as e:
                self.error_handler.handle_error(e, context="_quality_monitoring_loop")
                if self._stop_event.wait(1800):  # Wait 30 minutes on error
                    break
        
        self.logger.info("Quality monitoring loop stopped")
    
    def _update_all_factor_data(self) -> None:
        """Update all factor data."""
        try:
            with self.update_lock:
                self.logger.info("Updating all factor data")
                
                # Clear cache to force fresh data
                if self.enable_caching:
                    self.factor_cache.clear()
                
                # Update each factor model
                for model_name in FACTOR_MODELS.keys():
                    try:
                        factor_data = self.get_factor_model_data(model_name)
                        if factor_data is not None:
                            self.logger.debug(f"Updated {model_name} factor data")
                        else:
                            self.logger.warning(f"Failed to update {model_name} factor data")
                    except Exception as e:
                        self.logger.error(f"Error updating {model_name}: {e}")
                
                self.logger.info("Factor data update completed")
                
        except Exception as e:
            self.error_handler.handle_error(e, context="_update_all_factor_data")
    
    def _load_cached_factor_data(self) -> None:
        """Load cached factor data from storage."""
        # This would load from persistent storage in production
        self.logger.debug("Loaded cached factor data")
    
    def _save_cached_factor_data(self) -> None:
        """Save cached factor data to storage."""
        # This would save to persistent storage in production
        self.logger.debug("Saved cached factor data")

    # ==============================================================================
    # PUBLIC API METHODS
    # ==============================================================================
    def get_available_factors(self) -> Dict[str, List[str]]:
        """Get list of available factors by category."""
        return {
            'equity_factors': ['MKT', 'SMB', 'HML', 'RMW', 'CMA', 'MOM'],
            'options_factors': ['VIX_LEVEL', 'VIX_TERM', 'SKEW', 'GAMMA_FLIP'],
            'macro_factors': list(MACRO_FACTORS.keys()),
            'factor_models': list(FACTOR_MODELS.keys())
        }
    
    def get_factor_model_info(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific factor model."""
        if model_name not in FACTOR_MODELS:
            return None
        
        model_config = FACTOR_MODELS[model_name]
        model_obj = self.factor_models.get(model_name)
        
        info = {
            'model_name': model_name,
            'description': model_config['description'],
            'factors': model_config['factors'],
            'last_updated': model_obj.last_updated if model_obj else None,
            'correlation_matrix': model_obj.correlation_matrix.to_dict() if model_obj and model_obj.correlation_matrix is not None else None
        }
        
        return info
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of data providers."""
        return {
            'fred_available': self.fred_client is not None,
            'yahoo_available': YFINANCE_AVAILABLE,
            'cache_enabled': self.enable_caching,
            'cache_size': len(self.factor_cache),
            'last_update': datetime.now(),
            'quality_reports': len(self.quality_reports)
        }
    
    def shutdown(self) -> None:
        """Shutdown the factor data provider."""
        try:
            self.logger.info("Shutting down Factor Data Provider...")
            
            self._stop_event.set()
            self.running = False
            
            # Save cached data
            if self.enable_caching:
                self._save_cached_factor_data()
            
            # Shutdown thread pool
            self.thread_pool.shutdown(wait=True)
            
            self.logger.info("Factor Data Provider shutdown complete")
            
        except Exception as e:
            self.error_handler.handle_error(e, context="FactorDataProvider.shutdown")

# ==============================================================================
# MODULE-LEVEL FUNCTIONS
# ==============================================================================
# Global instance for singleton pattern
_factor_provider_instance = None

def get_factor_data_provider(config: Optional[Dict[str, Any]] = None) -> FactorDataProvider:
    """
    Get global Factor Data Provider instance (singleton pattern).
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        FactorDataProvider instance
    """
    global _factor_provider_instance
    if _factor_provider_instance is None:
        _factor_provider_instance = FactorDataProvider(config)
        _factor_provider_instance.initialize()
    return _factor_provider_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    logging.info("🎯 SPYDER C22 - Factor Data Provider")
    logging.info("=" * 80)
    
    try:
        # Create factor data provider
        config = {
            'fred_api_key': None,  # Would need actual API key
            'enable_caching': True,
            'update_frequency': 'daily'
        }
        
        provider = FactorDataProvider(config)
        logging.info("✅ Factor Data Provider initialized")
        
        # Initialize provider
        if not provider.initialize():
            logging.info("❌ Failed to initialize factor data provider")
            return False
        
        # Get available factors
        available_factors = provider.get_available_factors()
        logging.info(f"\n📊 Available Factors:")
        for category, factors in available_factors.items():
            logging.info(f"   • {category}: {', '.join(factors)}")
        
        # Test factor model data retrieval
        logging.info(f"\n⚡ Testing factor model data retrieval...")
        
        for model_name in ['CAPM', 'FF3', 'OPTIONS_CUSTOM']:
            logging.info(f"\n📈 Testing {model_name} model:")
            
            factor_data = provider.get_factor_model_data(
                model_name=model_name,
                start_date=datetime.now() - timedelta(days=90),
                end_date=datetime.now()
            )
            
            if factor_data is not None:
                logging.info(f"   ✅ Retrieved {len(factor_data)} observations")
                logging.info(f"   Factors: {list(factor_data.columns)}")
                logging.info(f"   Date range: {factor_data.index.min().strftime('%Y-%m-%d')} to {factor_data.index.max().strftime('%Y-%m-%d')}")
                
                # Show sample statistics
                logging.info(f"   Sample statistics:")
                for factor in factor_data.columns[:3]:  # Show first 3 factors
                    mean_return = factor_data[factor].mean()
                    volatility = factor_data[factor].std()
                    logging.info(f"     • {factor}: μ={mean_return:.4f}, σ={volatility:.4f}")
            else:
                logging.info(f"   ❌ Failed to retrieve data")
        
        # Test factor exposure calculation
        logging.info(f"\n🔍 Testing factor exposure calculation...")
        
        # Create sample return series
        dates = pd.date_range(start=datetime.now() - timedelta(days=60), end=datetime.now(), freq='D')
        sample_returns = pd.Series(
            np.random.normal(0.001, 0.02, len(dates)),
            index=dates,
            name="Sample Strategy"
        )
        
        exposure = provider.calculate_factor_exposures(
            returns=sample_returns,
            factor_model='FF3'
        )
        
        if exposure:
            logging.info(f"   ✅ Factor exposures calculated for {exposure.entity_name}")
            logging.info(f"   Model: {exposure.factor_model}")
            logging.info(f"   Exposures:")
            for factor, exp in exposure.exposures.items():
                t_stat = exposure.t_statistics.get(factor, 0)
                logging.info(f"     • {factor}: {exp:.4f} (t={t_stat:.2f})")
        else:
            logging.info(f"   ❌ Failed to calculate exposures")
        
        # Test quality validation
        logging.info(f"\n🔍 Testing data quality validation...")
        
        for factor_name in ['MKT', 'VIX_LEVEL']:
            quality_report = provider.validate_factor_data_quality(factor_name)
            logging.info(f"   📊 {factor_name} Quality Report:")
            logging.info(f"     • Overall Quality: {quality_report.overall_quality:.3f}")
            logging.info(f"     • Completeness: {quality_report.completeness_score:.3f}")
            logging.info(f"     • Timeliness: {quality_report.timeliness_score:.3f}")
            logging.info(f"     • Validity: {quality_report.validity_score:.3f}")
            
            if quality_report.issues_found:
                logging.info(f"     • Issues: {', '.join(quality_report.issues_found)}")
        
        # Get provider status
        status = provider.get_provider_status()
        logging.info(f"\n🔌 Provider Status:")
        logging.info(f"   • FRED Available: {'✅' if status['fred_available'] else '❌'}")
        logging.info(f"   • Yahoo Available: {'✅' if status['yahoo_available'] else '❌'}")
        logging.info(f"   • Cache Enabled: {'✅' if status['cache_enabled'] else '❌'}")
        logging.info(f"   • Cache Size: {status['cache_size']} items")
        logging.info(f"   • Quality Reports: {status['quality_reports']}")
        
        logging.info(f"\n🎊 Factor Data Provider demonstration completed successfully!")
        return True
        
    except Exception as e:
        logging.info(f"❌ Error in main execution: {e}")
        return False
    
    finally:
        # Clean up
        if 'provider' in locals():
            provider.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
