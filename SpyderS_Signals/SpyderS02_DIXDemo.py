#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderS02_DIXDemo.py
Group: S (Signals)
Purpose: DIX Demo Calculator Using Major S&P 500 Stocks

Description:
    This module provides a demonstration version of the DIX calculator using
    approximately 50 major S&P 500 stocks for faster execution and testing.
    It maintains the same calculation methodology as the full version but with
    a reduced dataset, making it ideal for development, testing, and real-time
    applications where speed is critical.

Spyder Version: 1.0
Author: Manus AI
Date Created: 2025-07-14
Last Updated: 2025-07-15 Time: 11:15:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import time
import warnings
from io import StringIO

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import logging

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderS_Signals.SpyderS01_DIXCalculator import (
        DataSource, CalculationStatus, StockDPI, DIXResult,
        FINRA_BASE_URL, FINRA_FILE_PREFIX, FINRA_DATE_FORMAT
    )
except ImportError:
    # Fallback for standalone operation
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    SpyderLogger = logging
    
    class SpyderErrorHandler:
        def handle_error(self, error, code):
            logging.error(f"{code}: {error}")
    
    # Import from local if running standalone
    from SpyderS01_DIXCalculator import (
        DataSource, CalculationStatus, StockDPI, DIXResult,
        FINRA_BASE_URL, FINRA_FILE_PREFIX, FINRA_DATE_FORMAT
    )

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Demo Configuration
DEMO_STOCK_COUNT = 50  # Number of stocks to use in demo
DEMO_PROCESSING_DELAY = 0.2  # Delay between API calls

# Demo Stock List - Top 50 S&P 500 by market cap
DEMO_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
    'UNH', 'JNJ', 'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'BAC',
    'ABBV', 'PFE', 'AVGO', 'KO', 'MRK', 'TMO', 'COST', 'PEP', 'WMT',
    'CSCO', 'ABT', 'ACN', 'MCD', 'VZ', 'ADBE', 'NEE', 'DHR', 'TXN',
    'BMY', 'LIN', 'ORCL', 'PM', 'CRM', 'NFLX', 'WFC', 'DIS', 'CMCSA',
    'NKE', 'AMD', 'T', 'UPS', 'QCOM', 'RTX', 'LOW', 'SPGI', 'HON'
]

# ==============================================================================
# ENUMS
# ==============================================================================
class DemoMode(Enum):
    """Demo mode settings"""
    FAST = "fast"      # Minimal delays
    NORMAL = "normal"  # Standard delays
    VERBOSE = "verbose"  # Extra logging

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DemoConfig:
    """Configuration for demo mode"""
    symbols: List[str]
    mode: DemoMode
    use_cache: bool
    verbose: bool

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderDIXDemo:
    """
    DIX Demo Calculator using major S&P 500 stocks.
    
    This class provides a faster demonstration version of DIX calculation
    using approximately 50 major S&P 500 stocks. It's ideal for testing,
    development, and real-time applications.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        demo_symbols: List of demo stock symbols
        market_caps: Dictionary of symbol to market cap
        finra_data: FINRA short sale volume data
        
    Example:
        >>> demo = SpyderDIXDemo()
        >>> demo.initialize()
        >>> results = demo.calculate_dix()
    """
    
    def __init__(self, config: Optional[DemoConfig] = None):
        """
        Initialize the DIX Demo Calculator.
        
        Args:
            config: Optional demo configuration
        """
        self.logger = SpyderLogger.get_logger(__name__) if hasattr(SpyderLogger, 'get_logger') else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or DemoConfig(
            symbols=DEMO_SYMBOLS[:DEMO_STOCK_COUNT],
            mode=DemoMode.NORMAL,
            use_cache=True,
            verbose=False
        )
        
        self.demo_symbols = self.config.symbols
        self.market_caps = {}
        self.finra_data = None
        self.status = CalculationStatus.PENDING
        
        # Cache for market caps
        self._market_cap_cache = {}
        self._cache_timestamp = None
        
        # Suppress warnings
        warnings.filterwarnings('ignore')
        
        self.logger.info(f"{self.__class__.__name__} initialized with {len(self.demo_symbols)} symbols")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize demo calculator components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing DIX Demo Calculator...")
            
            # Validate demo symbols
            if not self.demo_symbols:
                raise ValueError("No demo symbols configured")
            
            self.logger.info(f"Demo mode initialized with {len(self.demo_symbols)} stocks")
            return True
            
        except Exception as e:
            self.logger.error(f"Demo initialization failed: {e}")
            self.error_handler.handle_error(e, "DIX_DEMO_INIT_ERROR")
            return False
    
    def calculate_dix(self, date: Optional[str] = None) -> Optional[DIXResult]:
        """
        Calculate DIX using demo stocks.
        
        Args:
            date: Date in YYYYMMDD format (None for latest)
            
        Returns:
            DIXResult object or None if calculation fails
        """
        try:
            self.status = CalculationStatus.IN_PROGRESS
            start_time = datetime.now()
            
            # Determine date
            if date is None:
                date = self._get_latest_trading_date()
            
            self.logger.info(f"Starting demo DIX calculation for {date}")
            
            # Step 1: Get market cap data
            self._fetch_market_caps()
            
            # Step 2: Download FINRA data
            self._download_finra_data(date)
            
            # Step 3: Calculate DPI for demo symbols
            dpi_data = self._calculate_demo_dpi()
            
            # Step 4: Calculate DIX
            dix_value, breakdown = self._calculate_weighted_dix(dpi_data)
            
            # Create result object
            result = DIXResult(
                date=date,
                dix_value=dix_value,
                dix_percentage=dix_value * 100,
                num_components=len(breakdown),
                total_market_cap=sum(comp.market_cap for comp in breakdown.values()),
                breakdown=breakdown,
                calculation_time=datetime.now(),
                metadata={
                    'demo_mode': True,
                    'demo_symbols': len(self.demo_symbols),
                    'symbols_with_market_cap': len(self.market_caps),
                    'symbols_with_dpi': len(dpi_data),
                    'calculation_duration': (datetime.now() - start_time).total_seconds(),
                    'note': 'Demo version using major S&P 500 stocks only'
                }
            )
            
            self.status = CalculationStatus.COMPLETED
            self.logger.info(f"Demo DIX calculation completed: {result.dix_percentage:.2f}%")
            
            return result
            
        except Exception as e:
            self.status = CalculationStatus.FAILED
            self.logger.error(f"Demo DIX calculation failed: {e}")
            self.error_handler.handle_error(e, "DIX_DEMO_CALC_ERROR")
            return None
    
    def run_calculation(self, date: Optional[str] = None) -> Optional[Dict]:
        """
        Run demo DIX calculation (legacy interface).
        
        Args:
            date: Date in YYYYMMDD format (None for latest)
            
        Returns:
            Dictionary with results or None
        """
        result = self.calculate_dix(date)
        
        if result:
            # Convert to legacy format
            return self._convert_to_legacy_format(result)
        
        return None
    
    def get_demo_symbols(self) -> List[str]:
        """
        Get list of demo symbols being used.
        
        Returns:
            List of symbol strings
        """
        return self.demo_symbols.copy()
    
    # ==========================================================================
    # PRIVATE METHODS - DATA FETCHING
    # ==========================================================================
    def _fetch_market_caps(self) -> None:
        """Fetch market cap data for demo symbols."""
        self.logger.info(f"Fetching market cap data for {len(self.demo_symbols)} demo stocks...")
        
        # Check cache if enabled
        if self.config.use_cache and self._is_cache_valid():
            self.market_caps = self._market_cap_cache.copy()
            self.logger.info("Using cached market cap data")
            return
        
        self.market_caps = {}
        failed_symbols = []
        
        for i, symbol in enumerate(self.demo_symbols):
            try:
                if self.config.verbose:
                    self.logger.info(f"Processing {symbol} ({i+1}/{len(self.demo_symbols)})")
                
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                market_cap = self._extract_market_cap(info)
                
                if market_cap and market_cap > 0:
                    self.market_caps[symbol] = float(market_cap)
                    if self.config.verbose:
                        self.logger.info(f"{symbol}: ${market_cap:,.0f}")
                else:
                    failed_symbols.append(symbol)
                    
            except Exception as e:
                failed_symbols.append(symbol)
                self.logger.warning(f"Error fetching {symbol}: {e}")
            
            # Rate limiting
            if self.config.mode != DemoMode.FAST:
                time.sleep(DEMO_PROCESSING_DELAY)
        
        # Update cache
        if self.config.use_cache:
            self._market_cap_cache = self.market_caps.copy()
            self._cache_timestamp = datetime.now()
        
        self.logger.info(f"Fetched market cap for {len(self.market_caps)} symbols")
        if failed_symbols:
            self.logger.warning(f"Failed: {failed_symbols}")
    
    def _download_finra_data(self, date: str) -> None:
        """
        Download FINRA data for demo calculation.
        
        Args:
            date: Date in YYYYMMDD format
        """
        self.logger.info(f"Downloading FINRA data for {date}...")
        
        url = f"{FINRA_BASE_URL}{FINRA_FILE_PREFIX}{date}.txt"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse data
            self.finra_data = pd.read_csv(StringIO(response.text), sep='|')
            self.logger.info(f"Downloaded FINRA data: {len(self.finra_data)} records")
            
        except Exception as e:
            # Try previous day
            self.logger.warning(f"FINRA data not available for {date}, trying previous day")
            prev_date = (datetime.strptime(date, FINRA_DATE_FORMAT) - 
                        timedelta(days=1)).strftime(FINRA_DATE_FORMAT)
            
            url = f"{FINRA_BASE_URL}{FINRA_FILE_PREFIX}{prev_date}.txt"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            self.finra_data = pd.read_csv(StringIO(response.text), sep='|')
            self.logger.info(f"Downloaded FINRA data for {prev_date}: {len(self.finra_data)} records")
    
    # ==========================================================================
    # PRIVATE METHODS - CALCULATION
    # ==========================================================================
    def _calculate_demo_dpi(self) -> Dict[str, StockDPI]:
        """
        Calculate DPI for demo symbols.
        
        Returns:
            Dictionary mapping symbols to StockDPI objects
        """
        self.logger.info("Calculating DPI for demo stocks...")
        
        dpi_data = {}
        
        # Filter FINRA data for demo symbols
        demo_finra = self.finra_data[
            self.finra_data['Symbol'].isin(self.demo_symbols)
        ].copy()
        
        self.logger.info(f"Found FINRA data for {len(demo_finra)} demo symbols")
        
        for _, row in demo_finra.iterrows():
            symbol = row['Symbol']
            short_volume = row['ShortVolume']
            total_volume = row['TotalVolume']
            
            if total_volume > 0:
                dpi = short_volume / total_volume
                
                # Get market cap
                market_cap = self.market_caps.get(symbol, 0)
                
                if market_cap > 0:
                    dpi_data[symbol] = StockDPI(
                        symbol=symbol,
                        short_volume=short_volume,
                        total_volume=total_volume,
                        dpi=dpi,
                        market_cap=market_cap,
                        weight=0,
                        contribution=0
                    )
                    
                    if self.config.verbose:
                        self.logger.info(f"{symbol}: DPI={dpi:.4f} ({short_volume:,}/{total_volume:,})")
        
        self.logger.info(f"Calculated DPI for {len(dpi_data)} symbols")
        return dpi_data
    
    def _calculate_weighted_dix(self, dpi_data: Dict[str, StockDPI]) -> Tuple[float, Dict[str, StockDPI]]:
        """
        Calculate dollar-weighted DIX for demo stocks.
        
        Args:
            dpi_data: Dictionary of StockDPI objects
            
        Returns:
            Tuple of (DIX value, updated breakdown)
        """
        if not dpi_data:
            raise ValueError("No DPI data available for calculation")
        
        # Calculate total market cap
        total_market_cap = sum(stock.market_cap for stock in dpi_data.values())
        
        if total_market_cap == 0:
            raise ValueError("Total market cap is zero")
        
        # Calculate weights and contributions
        weighted_dpi_sum = 0
        
        for symbol, stock in dpi_data.items():
            stock.weight = stock.market_cap / total_market_cap
            stock.contribution = stock.dpi * stock.weight
            weighted_dpi_sum += stock.dpi * stock.market_cap
        
        # Calculate DIX
        dix = weighted_dpi_sum / total_market_cap
        
        self.logger.info(f"Demo DIX calculated: {dix:.4f} ({dix*100:.2f}%)")
        self.logger.info(f"Based on {len(dpi_data)} demo components")
        
        return dix, dpi_data
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    def _get_latest_trading_date(self) -> str:
        """Get latest trading date in YYYYMMDD format."""
        today = datetime.now()
        
        # If weekend, go back to Friday
        if today.weekday() >= 5:
            days_back = today.weekday() - 4
            target_date = today - timedelta(days=days_back)
        else:
            target_date = today
            
        return target_date.strftime(FINRA_DATE_FORMAT)
    
    def _extract_market_cap(self, info: Dict) -> Optional[float]:
        """Extract market cap from yfinance info dict."""
        # Try different keys
        for key in ['marketCap', 'market_cap', 'sharesOutstanding']:
            if key in info and info[key] is not None:
                if key == 'sharesOutstanding':
                    # Calculate from shares and price
                    shares = info[key]
                    price = info.get('currentPrice') or info.get('regularMarketPrice')
                    if shares and price:
                        return shares * price
                else:
                    return info[key]
        
        return None
    
    def _is_cache_valid(self) -> bool:
        """Check if market cap cache is still valid."""
        if not self._cache_timestamp:
            return False
        
        # Cache valid for 24 hours
        age = datetime.now() - self._cache_timestamp
        return age.total_seconds() < 86400
    
    def _convert_to_legacy_format(self, result: DIXResult) -> Dict:
        """Convert DIXResult to legacy dictionary format."""
        return {
            'dix': result.dix_value,
            'dix_percentage': result.dix_percentage,
            'date': result.date,
            'num_symbols': result.num_components,
            'total_market_cap': result.total_market_cap,
            'breakdown': {
                symbol: {
                    'dpi': comp.dpi,
                    'market_cap': comp.market_cap,
                    'weighted_dpi': comp.dpi * comp.market_cap,
                    'weight': comp.weight
                }
                for symbol, comp in result.breakdown.items()
            },
            'metadata': result.metadata
        }
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up module resources."""
        self.market_caps = {}
        self.finra_data = None
        self._market_cap_cache = {}
        self.logger.info("DIX Demo cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def quick_dix_demo() -> Optional[float]:
    """
    Quick demo DIX calculation.
    
    Returns:
        DIX percentage or None
    """
    try:
        demo = SpyderDIXDemo()
        demo.initialize()
        result = demo.calculate_dix()
        return result.dix_percentage if result else None
    except Exception as e:
        logging.error(f"Quick demo failed: {e}")
        return None

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_demo_instance: Optional[SpyderDIXDemo] = None

def get_demo_instance() -> SpyderDIXDemo:
    """
    Get singleton instance of demo calculator.
    
    Returns:
        Demo calculator instance
    """
    global _demo_instance
    if _demo_instance is None:
        _demo_instance = SpyderDIXDemo()
        _demo_instance.initialize()
    return _demo_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("="*70)
    print("DIX DEMO CALCULATOR TEST")
    print("="*70)
    
    # Test different modes
    configs = [
        DemoConfig(DEMO_SYMBOLS[:10], DemoMode.FAST, True, False),
        DemoConfig(DEMO_SYMBOLS[:25], DemoMode.NORMAL, True, True),
        DemoConfig(DEMO_SYMBOLS[:50], DemoMode.NORMAL, False, False)
    ]
    
    for i, config in enumerate(configs):
        print(f"\n🧪 Test {i+1}: {len(config.symbols)} symbols, mode={config.mode.value}")
        
        demo = SpyderDIXDemo(config)
        
        if demo.initialize():
            result = demo.calculate_dix()
            
            if result:
                print(f"✅ DIX: {result.dix_percentage:.2f}%")
                print(f"   Components: {result.num_components}")
                print(f"   Duration: {result.metadata['calculation_duration']:.1f}s")
            else:
                print("❌ Calculation failed")
        
        demo.cleanup()
    
    print("\n✅ DIX Demo tests completed")
