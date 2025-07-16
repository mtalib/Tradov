#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderS01_DIXCalculator.py
Group: S (Signals)
Purpose: Full S&P 500 DIX (Dark Index) Calculation Engine

Description:
    This module implements the complete DIX calculation methodology as described by 
    SqueezeMetrics. It calculates the dollar-weighted Dark Pool Indicator (DPI) 
    across all S&P 500 components using FINRA short sale data and market 
    capitalization weighting. The module provides the core calculation engine for 
    institutional dark pool sentiment analysis used in SPY options trading decisions.

Spyder Version: 1.0
Author: Manus AI
Date Created: 2025-07-14
Last Updated: 2025-07-15 Time: 11:00:00
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
except ImportError:
    # Fallback for standalone operation
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    SpyderLogger = logging
    
    class SpyderErrorHandler:
        def handle_error(self, error, code):
            logging.error(f"{code}: {error}")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# FINRA Data Constants
FINRA_BASE_URL = "https://cdn.finra.org/equity/regsho/daily/"
FINRA_FILE_PREFIX = "CNMSshvol"
FINRA_DATE_FORMAT = "%Y%m%d"

# S&P 500 Data Source
SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# API Rate Limiting
YFINANCE_DELAY = 0.1  # seconds between requests
BATCH_SIZE = 10  # symbols per batch
BATCH_DELAY = 1.0  # seconds between batches

# Calculation Constants
MIN_VOLUME_THRESHOLD = 0  # minimum volume to include in calculation
MAX_RETRY_ATTEMPTS = 3

# ==============================================================================
# ENUMS
# ==============================================================================
class DataSource(Enum):
    """Data source types"""
    FINRA = "finra"
    YFINANCE = "yfinance"
    WIKIPEDIA = "wikipedia"

class CalculationStatus(Enum):
    """Calculation status states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StockDPI:
    """Data structure for individual stock DPI information"""
    symbol: str
    short_volume: int
    total_volume: int
    dpi: float
    market_cap: float
    weight: float
    contribution: float

@dataclass
class DIXResult:
    """Data structure for DIX calculation results"""
    date: str
    dix_value: float
    dix_percentage: float
    num_components: int
    total_market_cap: float
    breakdown: Dict[str, StockDPI]
    calculation_time: datetime
    metadata: Dict[str, Any]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderDIXCalculator:
    """
    Full S&P 500 DIX (Dark Index) Calculator.
    
    This class provides the complete implementation of DIX calculation using
    all S&P 500 components. It manages data fetching from FINRA, market cap
    retrieval from yfinance, and the dollar-weighted DIX calculation.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        sp500_symbols: List of S&P 500 symbols
        market_caps: Dictionary of symbol to market cap
        finra_data: FINRA short sale volume data
        
    Example:
        >>> calculator = SpyderDIXCalculator()
        >>> calculator.initialize()
        >>> results = calculator.calculate_dix()
    """
    
    def __init__(self):
        """Initialize the DIX Calculator."""
        self.logger = SpyderLogger.get_logger(__name__) if hasattr(SpyderLogger, 'get_logger') else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        self.sp500_symbols = []
        self.market_caps = {}
        self.finra_data = None
        self.status = CalculationStatus.PENDING
        
        # Suppress warnings
        warnings.filterwarnings('ignore')
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize DIX calculator components.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing DIX Calculator...")
            
            # Fetch S&P 500 constituents
            if not self._fetch_sp500_constituents():
                raise Exception("Failed to fetch S&P 500 constituents")
            
            self.logger.info(f"Initialized with {len(self.sp500_symbols)} S&P 500 symbols")
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.error_handler.handle_error(e, "DIX_INIT_ERROR")
            return False
    
    def calculate_dix(self, date: Optional[str] = None) -> Optional[DIXResult]:
        """
        Calculate DIX for specified date.
        
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
            
            self.logger.info(f"Starting DIX calculation for {date}")
            
            # Step 1: Get market cap data
            self._fetch_market_caps()
            
            # Step 2: Download FINRA data
            self._download_finra_data(date)
            
            # Step 3: Calculate DPI for each symbol
            dpi_data = self._calculate_all_dpi()
            
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
                    'sp500_total': len(self.sp500_symbols),
                    'symbols_with_market_cap': len(self.market_caps),
                    'symbols_with_dpi': len(dpi_data),
                    'calculation_duration': (datetime.now() - start_time).total_seconds()
                }
            )
            
            self.status = CalculationStatus.COMPLETED
            self.logger.info(f"DIX calculation completed: {result.dix_percentage:.2f}%")
            
            return result
            
        except Exception as e:
            self.status = CalculationStatus.FAILED
            self.logger.error(f"DIX calculation failed: {e}")
            self.error_handler.handle_error(e, "DIX_CALC_ERROR")
            return None
    
    def run_calculation(self, date: Optional[str] = None) -> Optional[Dict]:
        """
        Run complete DIX calculation process (legacy interface).
        
        Args:
            date: Date in YYYYMMDD format (None for latest)
            
        Returns:
            Dictionary with results or None
        """
        result = self.calculate_dix(date)
        
        if result:
            # Convert to legacy format for compatibility
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
        
        return None
    
    # ==========================================================================
    # PRIVATE METHODS - DATA FETCHING
    # ==========================================================================
    def _fetch_sp500_constituents(self) -> bool:
        """
        Fetch current S&P 500 constituents from Wikipedia.
        
        Returns:
            bool: True if successful
        """
        try:
            self.logger.info("Fetching S&P 500 constituents from Wikipedia...")
            
            # Read S&P 500 list
            tables = pd.read_html(SP500_WIKI_URL)
            sp500_table = tables[0]
            
            # Extract and clean symbols
            symbols = sp500_table['Symbol'].tolist()
            self.sp500_symbols = [str(symbol).replace('.', '-') for symbol in symbols]
            
            self.logger.info(f"Fetched {len(self.sp500_symbols)} S&P 500 constituents")
            return True
            
        except Exception as e:
            self.logger.error(f"Error fetching S&P 500 constituents: {e}")
            
            # Fallback list
            self.sp500_symbols = self._get_fallback_symbols()
            self.logger.warning(f"Using fallback list of {len(self.sp500_symbols)} symbols")
            return True
    
    def _fetch_market_caps(self) -> None:
        """Fetch market capitalization data for all symbols."""
        self.logger.info(f"Fetching market cap data for {len(self.sp500_symbols)} symbols...")
        
        self.market_caps = {}
        failed_symbols = []
        
        # Process in batches
        for i in range(0, len(self.sp500_symbols), BATCH_SIZE):
            batch = self.sp500_symbols[i:i + BATCH_SIZE]
            self.logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(self.sp500_symbols)-1)//BATCH_SIZE + 1}")
            
            for symbol in batch:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info
                    
                    market_cap = self._extract_market_cap(info)
                    
                    if market_cap and market_cap > 0:
                        self.market_caps[symbol] = float(market_cap)
                        self.logger.debug(f"{symbol}: ${market_cap:,.0f}")
                    else:
                        failed_symbols.append(symbol)
                        
                except Exception as e:
                    failed_symbols.append(symbol)
                    self.logger.warning(f"Error fetching {symbol}: {e}")
                
                time.sleep(YFINANCE_DELAY)
            
            time.sleep(BATCH_DELAY)
        
        self.logger.info(f"Fetched market cap for {len(self.market_caps)} symbols")
        if failed_symbols:
            self.logger.warning(f"Failed: {len(failed_symbols)} symbols")
    
    def _download_finra_data(self, date: str) -> None:
        """
        Download FINRA short sale volume data.
        
        Args:
            date: Date in YYYYMMDD format
        """
        self.logger.info(f"Downloading FINRA data for {date}...")
        
        url = f"{FINRA_BASE_URL}{FINRA_FILE_PREFIX}{date}.txt"
        
        for attempt in range(MAX_RETRY_ATTEMPTS):
            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                # Parse data
                self.finra_data = pd.read_csv(StringIO(response.text), sep='|')
                self.logger.info(f"Downloaded FINRA data: {len(self.finra_data)} records")
                return
                
            except Exception as e:
                if attempt < MAX_RETRY_ATTEMPTS - 1:
                    # Try previous day
                    prev_date = (datetime.strptime(date, FINRA_DATE_FORMAT) - 
                               timedelta(days=1)).strftime(FINRA_DATE_FORMAT)
                    date = prev_date
                    url = f"{FINRA_BASE_URL}{FINRA_FILE_PREFIX}{date}.txt"
                    self.logger.warning(f"Retrying with {prev_date}")
                else:
                    raise Exception(f"Failed to download FINRA data: {e}")
    
    # ==========================================================================
    # PRIVATE METHODS - CALCULATION
    # ==========================================================================
    def _calculate_all_dpi(self) -> Dict[str, StockDPI]:
        """
        Calculate DPI for all S&P 500 symbols.
        
        Returns:
            Dictionary mapping symbols to StockDPI objects
        """
        self.logger.info("Calculating DPI for S&P 500 components...")
        
        dpi_data = {}
        
        # Filter FINRA data for S&P 500 symbols
        sp500_finra = self.finra_data[
            self.finra_data['Symbol'].isin(self.sp500_symbols)
        ].copy()
        
        self.logger.info(f"Found FINRA data for {len(sp500_finra)} symbols")
        
        for _, row in sp500_finra.iterrows():
            symbol = row['Symbol']
            short_volume = row['ShortVolume']
            total_volume = row['TotalVolume']
            
            if total_volume > MIN_VOLUME_THRESHOLD:
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
                        weight=0,  # Will be calculated later
                        contribution=0  # Will be calculated later
                    )
        
        self.logger.info(f"Calculated DPI for {len(dpi_data)} symbols")
        return dpi_data
    
    def _calculate_weighted_dix(self, dpi_data: Dict[str, StockDPI]) -> Tuple[float, Dict[str, StockDPI]]:
        """
        Calculate dollar-weighted DIX.
        
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
        
        self.logger.info(f"DIX calculated: {dix:.4f} ({dix*100:.2f}%)")
        self.logger.info(f"Based on {len(dpi_data)} components, "
                        f"total market cap: ${total_market_cap:,.0f}")
        
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
    
    def _get_fallback_symbols(self) -> List[str]:
        """Get fallback list of major S&P 500 symbols."""
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
            'UNH', 'JNJ', 'JPM', 'V', 'PG', 'XOM', 'HD', 'CVX', 'MA', 'BAC',
            'ABBV', 'PFE', 'AVGO', 'KO', 'MRK', 'TMO', 'COST', 'PEP', 'WMT',
            'CSCO', 'ABT', 'ACN', 'MCD', 'VZ', 'ADBE', 'NEE', 'DHR', 'TXN',
            'BMY', 'LIN', 'ORCL', 'PM', 'CRM', 'NFLX', 'WFC', 'DIS', 'CMCSA',
            'NKE', 'AMD', 'T', 'UPS', 'QCOM', 'RTX', 'LOW', 'SPGI', 'HON'
        ]
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up module resources."""
        self.sp500_symbols = []
        self.market_caps = {}
        self.finra_data = None
        self.logger.info("DIX Calculator cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def calculate_dix_for_date(date: str) -> Optional[float]:
    """
    Helper function to calculate DIX for a specific date.
    
    Args:
        date: Date in YYYYMMDD format
        
    Returns:
        DIX percentage or None
    """
    try:
        calculator = SpyderDIXCalculator()
        calculator.initialize()
        result = calculator.calculate_dix(date)
        return result.dix_percentage if result else None
    except Exception as e:
        logging.error(f"Error calculating DIX: {e}")
        return None

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_calculator_instance: Optional[SpyderDIXCalculator] = None

def get_calculator_instance() -> SpyderDIXCalculator:
    """
    Get singleton instance of the calculator.
    
    Returns:
        Calculator instance
    """
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = SpyderDIXCalculator()
        _calculator_instance.initialize()
    return _calculator_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    calculator = SpyderDIXCalculator()
    
    if calculator.initialize():
        print("✅ DIX Calculator initialized")
        
        # Run calculation
        result = calculator.calculate_dix()
        
        if result:
            print(f"\n📊 DIX Calculation Results:")
            print(f"   Date: {result.date}")
            print(f"   DIX: {result.dix_percentage:.2f}%")
            print(f"   Components: {result.num_components}")
            print(f"   Market Cap: ${result.total_market_cap:,.0f}")
            
            # Show top contributors
            sorted_breakdown = sorted(
                result.breakdown.items(),
                key=lambda x: x[1].contribution,
                reverse=True
            )
            
            print(f"\n🏆 Top 5 Contributors:")
            for symbol, data in sorted_breakdown[:5]:
                print(f"   {symbol}: DPI={data.dpi:.3f}, Weight={data.weight:.3f}")
        
        # Cleanup
        calculator.cleanup()
        print("\n✅ DIX Calculator test completed")
    else:
        print("❌ DIX Calculator initialization failed")
