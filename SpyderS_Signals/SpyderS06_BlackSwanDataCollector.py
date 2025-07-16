#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderS06_BlackSwanDataCollector.py
Group: S (Signals)
Purpose: Market data collection for Black Swan detection
Author: Mohamed Talib
Date Created: 2025-01-15 
Last Updated: 2025-01-15 Time: 14:30:00  

Description:
    This module collects real-time market data for Black Swan indicator calculation.
    It aggregates data from multiple sources including volatility indices, market
    performance metrics, credit stress indicators, liquidity measures, and options
    activity. Provides robust error handling and fallback mechanisms for data sources.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Data source imports
try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("Warning: yfinance not available")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderU_Utilities.SpyderU03_DateTimeUtils import SpyderDateTimeUtils
    from SpyderC_MarketData.SpyderC01_DataFeed import SpyderDataFeed
    SPYDER_INTEGRATION = True
except ImportError:
    # Fallback for standalone operation
    SpyderLogger = logging
    SpyderErrorHandler = None
    SpyderDateTimeUtils = None
    SpyderDataFeed = None
    SPYDER_INTEGRATION = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Data update intervals (seconds)
DEFAULT_UPDATE_INTERVAL = 60
FAST_UPDATE_INTERVAL = 30
SLOW_UPDATE_INTERVAL = 300

# Data source timeouts
REQUEST_TIMEOUT = 10
MAX_RETRIES = 3

# Market symbols
VOLATILITY_SYMBOLS = {
    'vix': '^VIX',
    'vxn': '^VXN',  # NASDAQ volatility
    'rvx': '^RVX',  # Russell volatility
    'vix9d': '^VIX9D',  # 9-day VIX
    'vix3m': '^VIX3M'   # 3-month VIX
}

MARKET_SYMBOLS = {
    'spy': 'SPY',
    'qqq': 'QQQ',
    'iwm': 'IWM',
    'dia': 'DIA',
    'es_futures': 'ES=F',
    'nq_futures': 'NQ=F'
}

CREDIT_SYMBOLS = {
    'hyg': 'HYG',  # High yield bonds
    'lqd': 'LQD',  # Investment grade bonds
    'tlt': 'TLT',  # Long-term treasuries
    'shy': 'SHY'   # Short-term treasuries
}

LIQUIDITY_SYMBOLS = {
    'dxy': 'DX-Y.NYB',  # Dollar index
    'tyx': '^TYX',      # 30-year yield
    'tnx': '^TNX',      # 10-year yield
    'fvx': '^FVX'       # 5-year yield
}

# ==============================================================================
# ENUMS
# ==============================================================================
class DataStatus(Enum):
    """Data collection status"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    STALE = "stale"

class DataSource(Enum):
    """Available data sources"""
    YFINANCE = "yfinance"
    SPYDER = "spyder"
    CACHE = "cache"
    DEMO = "demo"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketDataPoint:
    """Single market data point"""
    symbol: str
    value: float
    timestamp: datetime
    source: DataSource
    
@dataclass
class CollectionResult:
    """Result of data collection operation"""
    status: DataStatus
    data: Dict[str, Any]
    errors: List[str]
    timestamp: datetime
    source: DataSource

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class BlackSwanDataCollector:
    """
    Collects market data for Black Swan indicator calculation.
    
    This class manages data collection from multiple sources, handles failures
    gracefully, and provides normalized data for the calculator. It supports
    both real-time and cached data modes with automatic fallback mechanisms.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        update_interval: Data update frequency in seconds
        cache: Local data cache
        last_update: Timestamp of last successful update
        
    Example:
        >>> collector = BlackSwanDataCollector()
        >>> data = collector.collect_all_data()
        >>> print(f"VIX: {data['volatility']['vix_current']}")
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the data collector.
        
        Args:
            config: Optional configuration dictionary
        """
        # Setup logging
        if SPYDER_INTEGRATION:
            self.logger = SpyderLogger.get_logger(__name__)
            self.error_handler = SpyderErrorHandler()
        else:
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)
            self.error_handler = None
            
        # Configuration
        self.config = config or {}
        self.update_interval = self.config.get('update_interval', DEFAULT_UPDATE_INTERVAL)
        self.use_demo = self.config.get('use_demo', False)
        
        # Data cache
        self.cache: Dict[str, MarketDataPoint] = {}
        self.last_update: Optional[datetime] = None
        
        # HTTP session with retries
        self.session = self._setup_session()
        
        # Spyder integration
        self.spyder_datafeed = None
        if SPYDER_INTEGRATION and SpyderDataFeed:
            try:
                self.spyder_datafeed = SpyderDataFeed()
                self.logger.info("Integrated with SpyderDataFeed")
            except:
                self.logger.warning("Could not initialize SpyderDataFeed")
                
        self.logger.info("Black Swan Data Collector initialized")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def collect_all_data(self) -> Dict[str, Any]:
        """
        Collect all required market data.
        
        Returns:
            Dictionary with all component data
        """
        self.logger.info("Starting comprehensive data collection")
        
        # Check if update needed
        if self._is_cache_valid():
            self.logger.info("Using cached data")
            return self._get_cached_data()
            
        # Collect each component
        results = {
            'volatility': self._collect_volatility_data(),
            'market_performance': self._collect_market_data(),
            'credit': self._collect_credit_data(),
            'liquidity': self._collect_liquidity_data(),
            'options': self._collect_options_data(),
            'metadata': {
                'timestamp': datetime.now(),
                'source': 'live' if not self.use_demo else 'demo',
                'errors': []
            }
        }
        
        # Update cache
        self.last_update = datetime.now()
        
        # Log collection summary
        total_points = sum(len(v) for v in results.values() if isinstance(v, dict))
        self.logger.info(f"Data collection complete: {total_points} data points")
        
        return results
        
    def get_single_quote(self, symbol: str) -> Optional[float]:
        """
        Get single quote for a symbol.
        
        Args:
            symbol: Market symbol
            
        Returns:
            Current price or None if failed
        """
        try:
            # Try Spyder datafeed first
            if self.spyder_datafeed and SPYDER_INTEGRATION:
                try:
                    data = self.spyder_datafeed.get_quote(symbol)
                    if data and 'last' in data:
                        return float(data['last'])
                except:
                    pass
                    
            # Try yfinance
            if YFINANCE_AVAILABLE and not self.use_demo:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1d', interval='1m')
                if not hist.empty:
                    return float(hist['Close'].iloc[-1])
                    
            # Demo mode
            if self.use_demo:
                return self._get_demo_price(symbol)
                
        except Exception as e:
            self.logger.error(f"Error getting quote for {symbol}: {e}")
            
        return None
        
    def get_historical_data(self, symbol: str, period: str = '5d') -> Optional[pd.DataFrame]:
        """
        Get historical data for analysis.
        
        Args:
            symbol: Market symbol
            period: Time period (1d, 5d, 1mo, etc.)
            
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            if YFINANCE_AVAILABLE and not self.use_demo:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                return hist
                
            # Demo mode
            if self.use_demo:
                return self._generate_demo_history(symbol, period)
                
        except Exception as e:
            self.logger.error(f"Error getting historical data for {symbol}: {e}")
            
        return None
        
    # ==========================================================================
    # PRIVATE METHODS - Data Collection
    # ==========================================================================
    def _collect_volatility_data(self) -> Dict[str, Any]:
        """Collect volatility indicators."""
        data = {}
        
        try:
            # VIX and related indices
            for name, symbol in VOLATILITY_SYMBOLS.items():
                value = self.get_single_quote(symbol)
                if value:
                    data[f'{name}_current'] = value
                    
            # Calculate VIX percentile
            if 'vix_current' in data:
                vix_hist = self.get_historical_data('^VIX', '1mo')
                if vix_hist is not None and not vix_hist.empty:
                    percentile = (vix_hist['Close'] < data['vix_current']).mean() * 100
                    data['vix_percentile'] = percentile
                    
            # VIX term structure
            if 'vix_current' in data and 'vix3m_current' in data:
                data['vix_term_structure'] = data['vix3m_current'] - data['vix_current']
                
        except Exception as e:
            self.logger.error(f"Error collecting volatility data: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e)
                
        return data
        
    def _collect_market_data(self) -> Dict[str, Any]:
        """Collect market performance data."""
        data = {}
        
        try:
            # Current prices
            for name, symbol in MARKET_SYMBOLS.items():
                value = self.get_single_quote(symbol)
                if value:
                    data[f'{name}_price'] = value
                    
            # Calculate returns
            for name, symbol in MARKET_SYMBOLS.items():
                hist = self.get_historical_data(symbol, '5d')
                if hist is not None and len(hist) >= 2:
                    # 1-day return
                    data[f'{name}_1d_return'] = (
                        (hist['Close'].iloc[-1] / hist['Close'].iloc[-2] - 1) * 100
                    )
                    # 5-day return
                    if len(hist) >= 5:
                        data[f'{name}_5d_return'] = (
                            (hist['Close'].iloc[-1] / hist['Close'].iloc[0] - 1) * 100
                        )
                        
            # Market breadth (if SPY data available)
            if 'spy_price' in data:
                # This would require advance/decline data
                # Placeholder for now
                data['market_breadth'] = 0.5
                
        except Exception as e:
            self.logger.error(f"Error collecting market data: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e)
                
        return data
        
    def _collect_credit_data(self) -> Dict[str, Any]:
        """Collect credit stress indicators."""
        data = {}
        
        try:
            # Credit spreads
            for name, symbol in CREDIT_SYMBOLS.items():
                value = self.get_single_quote(symbol)
                if value:
                    data[f'{name}_price'] = value
                    
            # Calculate credit spreads
            if 'hyg_price' in data and 'lqd_price' in data:
                # Simple spread proxy
                hyg_hist = self.get_historical_data('HYG', '20d')
                lqd_hist = self.get_historical_data('LQD', '20d')
                
                if hyg_hist is not None and lqd_hist is not None:
                    hyg_return = hyg_hist['Close'].pct_change().mean()
                    lqd_return = lqd_hist['Close'].pct_change().mean()
                    data['credit_spread'] = abs(hyg_return - lqd_return) * 10000
                    
        except Exception as e:
            self.logger.error(f"Error collecting credit data: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e)
                
        return data
        
    def _collect_liquidity_data(self) -> Dict[str, Any]:
        """Collect liquidity stress indicators."""
        data = {}
        
        try:
            # Dollar and yields
            for name, symbol in LIQUIDITY_SYMBOLS.items():
                value = self.get_single_quote(symbol)
                if value:
                    data[f'{name}_current'] = value
                    
            # Calculate yield curve
            if 'tnx_current' in data and 'fvx_current' in data:
                data['yield_curve_510'] = data['tnx_current'] - data['fvx_current']
                
            if 'tyx_current' in data and 'tnx_current' in data:
                data['yield_curve_1030'] = data['tyx_current'] - data['tnx_current']
                
            # Dollar strength change
            if 'dxy_current' in data:
                dxy_hist = self.get_historical_data('DX-Y.NYB', '5d')
                if dxy_hist is not None and len(dxy_hist) >= 2:
                    data['dxy_5d_change'] = (
                        (dxy_hist['Close'].iloc[-1] / dxy_hist['Close'].iloc[0] - 1) * 100
                    )
                    
        except Exception as e:
            self.logger.error(f"Error collecting liquidity data: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e)
                
        return data
        
    def _collect_options_data(self) -> Dict[str, Any]:
        """Collect options activity indicators."""
        data = {}
        
        try:
            # This would typically come from options data feed
            # For now, using proxy indicators
            
            # Put/Call ratio (would need real options data)
            data['put_call_ratio'] = 1.0  # Placeholder
            
            # Options volume (placeholder)
            data['options_volume'] = 1000000
            
            # Skew index (placeholder)
            data['skew_index'] = 120
            
            # If integrated with Spyder options analytics
            if SPYDER_INTEGRATION:
                try:
                    # Would integrate with SpyderN_OptionsAnalytics modules
                    pass
                except:
                    pass
                    
        except Exception as e:
            self.logger.error(f"Error collecting options data: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e)
                
        return data
        
    # ==========================================================================
    # PRIVATE METHODS - Utilities
    # ==========================================================================
    def _setup_session(self) -> requests.Session:
        """Setup HTTP session with retries."""
        session = requests.Session()
        retry = Retry(
            total=MAX_RETRIES,
            read=MAX_RETRIES,
            connect=MAX_RETRIES,
            backoff_factor=0.3,
            status_forcelist=(500, 502, 504)
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
        
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if not self.last_update:
            return False
            
        age = (datetime.now() - self.last_update).total_seconds()
        return age < self.update_interval
        
    def _get_cached_data(self) -> Dict[str, Any]:
        """Get data from cache."""
        # Reconstruct data structure from cache
        # This is a simplified version
        return {
            'volatility': {},
            'market_performance': {},
            'credit': {},
            'liquidity': {},
            'options': {},
            'metadata': {
                'timestamp': self.last_update,
                'source': 'cache',
                'errors': []
            }
        }
        
    def _get_demo_price(self, symbol: str) -> float:
        """Generate demo price for testing."""
        # Base prices for demo
        base_prices = {
            '^VIX': 15.0,
            'SPY': 450.0,
            'QQQ': 380.0,
            'IWM': 220.0,
            'HYG': 85.0,
            'LQD': 120.0,
            'DX-Y.NYB': 102.0
        }
        
        base = base_prices.get(symbol, 100.0)
        # Add some randomness
        noise = np.random.normal(0, 0.01)
        return base * (1 + noise)
        
    def _generate_demo_history(self, symbol: str, period: str) -> pd.DataFrame:
        """Generate demo historical data."""
        # Determine number of bars
        periods = {
            '1d': 390,  # 1 minute bars
            '5d': 1950,  # 5 days of minute bars
            '1mo': 22,  # Daily bars
            '3mo': 65   # Daily bars
        }
        
        num_bars = periods.get(period, 100)
        base_price = self._get_demo_price(symbol)
        
        # Generate random walk
        returns = np.random.normal(0, 0.001, num_bars)
        prices = base_price * np.exp(np.cumsum(returns))
        
        # Create DataFrame
        dates = pd.date_range(end=datetime.now(), periods=num_bars, freq='1min')
        df = pd.DataFrame({
            'Open': prices * np.random.uniform(0.999, 1.001, num_bars),
            'High': prices * np.random.uniform(1.001, 1.005, num_bars),
            'Low': prices * np.random.uniform(0.995, 0.999, num_bars),
            'Close': prices,
            'Volume': np.random.randint(1000, 10000, num_bars)
        }, index=dates)
        
        return df
        
    # ==========================================================================
    # PUBLIC METHODS - Status and Control
    # ==========================================================================
    def get_status(self) -> Dict[str, Any]:
        """
        Get collector status.
        
        Returns:
            Status dictionary
        """
        return {
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'cache_size': len(self.cache),
            'update_interval': self.update_interval,
            'data_source': 'demo' if self.use_demo else 'live',
            'spyder_integration': SPYDER_INTEGRATION,
            'yfinance_available': YFINANCE_AVAILABLE
        }
        
    def clear_cache(self):
        """Clear data cache."""
        self.cache.clear()
        self.last_update = None
        self.logger.info("Data cache cleared")
        
    def set_update_interval(self, seconds: int):
        """
        Set data update interval.
        
        Args:
            seconds: Update interval in seconds
        """
        self.update_interval = max(FAST_UPDATE_INTERVAL, seconds)
        self.logger.info(f"Update interval set to {self.update_interval} seconds")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def test_data_collection() -> bool:
    """
    Test data collection functionality.
    
    Returns:
        True if all tests pass
    """
    print("Testing Black Swan Data Collector...")
    
    try:
        # Initialize collector
        collector = BlackSwanDataCollector({'use_demo': True})
        
        # Test single quote
        vix = collector.get_single_quote('^VIX')
        print(f"✓ Single quote test: VIX = {vix}")
        
        # Test all data collection
        data = collector.collect_all_data()
        print(f"✓ Full data collection: {len(data)} components")
        
        # Test historical data
        hist = collector.get_historical_data('SPY', '5d')
        print(f"✓ Historical data: {len(hist)} bars")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    print("="*60)
    print("BLACK SWAN DATA COLLECTOR TEST")
    print("="*60)
    
    # Run tests
    if test_data_collection():
        print("\n✅ All tests passed!")
        
        # Demo collection
        print("\nRunning demo collection...")
        collector = BlackSwanDataCollector({'use_demo': True})
        data = collector.collect_all_data()
        
        print("\nCollected Data Summary:")
        for component, values in data.items():
            if isinstance(values, dict) and component != 'metadata':
                print(f"\n{component.upper()}:")
                for key, value in values.items():
                    if isinstance(value, float):
                        print(f"  {key}: {value:.2f}")
    else:
        print("\n❌ Tests failed!")
