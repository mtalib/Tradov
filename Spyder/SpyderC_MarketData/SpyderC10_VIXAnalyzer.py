#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC10_VIXAnalyzer.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics
import math
import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats, signal
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils, MarketSession
from Spyder.SpyderU_Utilities.SpyderU07_Constants import TimeFrame
try:
    from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import MAType as MovingAverageType
except ImportError:
    from enum import Enum
    class MovingAverageType(Enum):
        SMA = "sma"
        EMA = "ema"
        WMA = "wma"

try:
    from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
    _ti = TechnicalIndicators()
    RSI = _ti.calculate_rsi  # type: ignore
    BollingerBands = _ti.calculate_bollinger_bands  # type: ignore
except ImportError:
    RSI = None  # type: ignore
    BollingerBands = None  # type: ignore
from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import DataFeedManager, MarketTick
from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import DataValidator
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

VIX_SYMBOLS = {
    'VIX': '^VIX',      # CBOE Volatility Index
    'VIX9D': '^VIX9D',  # CBOE 9-Day Volatility Index
    'VVIX': '^VVIX',    # VIX of VIX
    'VXV': '^VXV',      # VIX 3-Month
    'VXMT': '^VXMT',    # VIX 6-Month
    'VXST': '^VXST',    # VIX 9-Day
}

# VIX Analysis Parameters
VIX_LOW_THRESHOLD = 15.0    # Low volatility threshold
VIX_HIGH_THRESHOLD = 30.0   # High volatility threshold
VIX_EXTREME_HIGH = 50.0     # Extreme volatility threshold
VIX_EXTREME_LOW = 10.0      # Extreme low volatility threshold

# Volatility Regime Parameters
REGIME_LOOKBACK_PERIODS = [10, 20, 50, 100, 200]
REGIME_THRESHOLD_PERCENTILES = [20, 80]  # 20th and 80th percentiles
BREAKOUT_LOOKBACK = 20      # Days for breakout analysis
CONTANGO_BACKWARDATION_THRESHOLD = 0.05  # 5% threshold

# Term Structure Parameters
TERM_STRUCTURE_PAIRS = [
    ('VIX9D', 'VIX'),      # 9D vs 30D
    ('VIX', 'VXV'),        # 30D vs 3M
    ('VXV', 'VXMT'),       # 3M vs 6M
]

# Risk Premium Parameters
HISTORICAL_VOLATILITY_PERIODS = [10, 20, 30, 60, 90]
RISK_PREMIUM_LOOKBACK = 252  # 1 year of trading days

# Signal Configuration
SIGNAL_CONFIDENCE_THRESHOLD = 0.7
MIN_DATA_POINTS = 50
UPDATE_INTERVAL = 60  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityRegime(Enum):
    """Volatility regime classification."""
    EXTREME_LOW = "extreme_low"     # VIX < 10
    LOW = "low"                     # VIX 10-15
    NORMAL_LOW = "normal_low"       # VIX 15-20
    NORMAL = "normal"               # VIX 20-25
    ELEVATED = "elevated"           # VIX 25-30
    HIGH = "high"                   # VIX 30-40
    EXTREME_HIGH = "extreme_high"   # VIX > 40
    CRISIS = "crisis"               # VIX > 50

class VolatilityTrend(Enum):
    """Volatility trend direction."""
    RISING = "rising"
    FALLING = "falling"
    STABLE = "stable"
    BREAKOUT = "breakout"
    BREAKDOWN = "breakdown"

class TermStructureState(Enum):
    """VIX term structure state."""
    STEEP_CONTANGO = "steep_contango"       # Strong upward slope
    CONTANGO = "contango"                   # Normal upward slope
    FLAT = "flat"                           # Minimal slope
    BACKWARDATION = "backwardation"         # Downward slope
    STEEP_BACKWARDATION = "steep_backwardation"  # Strong downward slope

class VIXSignal(Enum):
    """VIX-based trading signals."""


class VIXRegime(Enum):
    """VIX regime classification (compatibility alias)."""
    ULTRA_LOW = "ultra_low"     # VIX < 12
    LOW = "low"                 # VIX 12-18
    NORMAL = "normal"           # VIX 18-25
    ELEVATED = "elevated"       # VIX 25-32
    HIGH = "high"               # VIX 32-45
    EXTREME = "extreme"         # VIX > 45
    VOLATILITY_EXPANSION = "vol_expansion"
    VOLATILITY_CONTRACTION = "vol_contraction"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT_CONTINUATION = "breakout_continuation"
    REGIME_SHIFT = "regime_shift"
    EXTREME_READING = "extreme_reading"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VIXData:
    """VIX data point."""
    symbol: str
    value: float
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None

@dataclass
class VolatilityMetrics:
    """Comprehensive volatility metrics."""
    vix: float
    vix9d: float
    vvix: float
    vxv: float
    vxmt: float
    regime: VolatilityRegime
    trend: VolatilityTrend
    term_structure: TermStructureState
    percentile_20d: float
    percentile_50d: float
    percentile_200d: float
    z_score: float
    rsi: float
    bollinger_position: float  # Position within Bollinger Bands
    timestamp: datetime

@dataclass
class TermStructure:
    """VIX term structure analysis."""
    vix9d_vix_ratio: float
    vix_vxv_ratio: float
    vxv_vxmt_ratio: float
    overall_slope: float
    state: TermStructureState
    timestamp: datetime
    
    @property
    def is_contango(self) -> bool:
        """Check if term structure is in contango."""
        return self.state in [TermStructureState.CONTANGO, TermStructureState.STEEP_CONTANGO]
    
    @property
    def is_backwardation(self) -> bool:
        """Check if term structure is in backwardation."""
        return self.state in [TermStructureState.BACKWARDATION, TermStructureState.STEEP_BACKWARDATION]

@dataclass
class VolatilityRiskPremium:
    """Volatility risk premium analysis."""
    symbol: str
    implied_vol: float      # From VIX
    realized_vol_10d: float
    realized_vol_20d: float
    realized_vol_30d: float
    risk_premium_10d: float
    risk_premium_20d: float
    risk_premium_30d: float
    avg_risk_premium: float
    percentile_rank: float
    timestamp: datetime

@dataclass
class VIXSignalData:
    """VIX trading signal."""
    signal_type: VIXSignal
    strength: float         # 0.0 to 1.0
    confidence: float       # 0.0 to 1.0
    description: str
    regime: VolatilityRegime
    supporting_factors: List[str]
    target_strategies: List[str]
    timestamp: datetime

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class VIXAnalyzer:
    """
    Comprehensive VIX and volatility analysis system.
    
    This class provides sophisticated volatility analysis including regime detection,
    term structure analysis, risk premium calculations, and volatility-based trading
    signals. It processes real-time VIX family data to identify optimal timing for
    volatility strategies and provides regime-aware recommendations.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        data_validator: Data validation instance
        vix_data: Current VIX family data
        historical_data: Historical VIX data
        volatility_metrics: Current volatility metrics
        term_structure: Current term structure analysis
        risk_premium: Current risk premium analysis
        
    Example:
        >>> analyzer = VIXAnalyzer()
        >>> analyzer.initialize()
        >>> analyzer.start_analysis()
        >>> metrics = analyzer.get_current_metrics()
        >>> signal = analyzer.get_trading_signal()
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialize VIX analyzer."""
        self.logger = SpyderLogger.get_logger("VIXAnalyzer")
        self.error_handler = SpyderErrorHandler()
        self.data_validator = DataValidator()
        
        # Configuration
        self.config = config or {}
        self.update_interval = self.config.get('update_interval', UPDATE_INTERVAL)
        self.lookback_periods = self.config.get('lookback_periods', REGIME_LOOKBACK_PERIODS)
        
        # Data storage
        self.vix_data: Dict[str, VIXData] = {}
        self.historical_data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=500))
        self.volatility_metrics: Optional[VolatilityMetrics] = None
        self.term_structure: Optional[TermStructure] = None
        self.risk_premium: Optional[VolatilityRiskPremium] = None
        
        # Technical indicators
        self.rsi_calculator = RSI(period=14)
        self.bb_calculator = BollingerBands(period=20, std_dev=2.0)
        
        # Analysis state
        self.is_analyzing = False
        self.last_update = None
        self.regime_history: deque = deque(maxlen=100)
        self.signal_history: deque = deque(maxlen=50)
        
        # Threading
        self._lock = threading.RLock()
        self._analysis_thread = None
        self._data_thread = None
        self._stop_event = threading.Event()
        
        # Event manager integration
        self.event_manager = get_event_manager()
        
        # Performance tracking
        self.stats = {
            'updates_processed': 0,
            'signals_generated': 0,
            'regime_changes': 0,
            'last_data_update': None
        }
        
        self.logger.info("VIX Analyzer initialized")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the VIX analyzer.
        
        Returns:
            True if initialization successful, False otherwise
        """
        try:
            # Load initial historical data
            if not self._load_historical_data():
                self.logger.warning("Failed to load historical data, continuing with limited functionality")
            
            # Register event callbacks
            self._register_event_callbacks()
            
            # Initialize technical indicators
            self._initialize_indicators()
            
            # Perform initial analysis
            self._perform_initial_analysis()
            
            self.logger.info("VIX analyzer initialized successfully")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'initialize',
                'class': 'VIXAnalyzer'
            })
            return False
    
    def _load_historical_data(self) -> bool:
        """Load historical VIX data for analysis."""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=365)  # 1 year of data
            
            for symbol_key, yahoo_symbol in VIX_SYMBOLS.items():
                try:
                    # Download data from Yahoo Finance
                    ticker = yf.Ticker(yahoo_symbol)
                    hist = ticker.history(start=start_date, end=end_date)
                    
                    if hist.empty:
                        self.logger.warning(f"No historical data for {symbol_key}")
                        continue
                    
                    # Convert to VIXData objects
                    for date_idx, row in hist.iterrows():
                        vix_data = VIXData(
                            symbol=symbol_key,
                            value=row['Close'],
                            timestamp=date_idx.to_pydatetime(),
                            open=row['Open'],
                            high=row['High'],
                            low=row['Low'],
                            close=row['Close'],
                            volume=int(row['Volume']) if not pd.isna(row['Volume']) else None
                        )
                        self.historical_data[symbol_key].append(vix_data)
                    
                    self.logger.debug(f"Loaded {len(hist)} data points for {symbol_key}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to load data for {symbol_key}: {e}")
                    continue
            
            return len(self.historical_data) > 0
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_load_historical_data'
            })
            return False
    
    def _register_event_callbacks(self) -> None:
        """Register event manager callbacks."""
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data)
            self.event_manager.subscribe(EventType.VIX_UPDATE, self._on_vix_update)
    
    def _initialize_indicators(self) -> None:
        """Initialize technical indicators with historical data."""
        if 'VIX' in self.historical_data and len(self.historical_data['VIX']) > 20:
            vix_values = [data.value for data in self.historical_data['VIX']]
            
            # Prime RSI calculator
            for value in vix_values[-50:]:  # Use last 50 values
                self.rsi_calculator.update(value)
            
            # Prime Bollinger Bands calculator
            for value in vix_values[-50:]:
                self.bb_calculator.update(value)
    
    def _perform_initial_analysis(self) -> None:
        """Perform initial volatility analysis."""
        if self.historical_data:
            self._update_volatility_metrics()
            self._update_term_structure()
            self._update_risk_premium()

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start_analysis(self) -> None:
        """Start VIX analysis."""
        if self.is_analyzing:
            self.logger.warning("VIX analysis already running")
            return
        
        try:
            self.is_analyzing = True
            self._stop_event.clear()
            
            # Start data collection thread
            self._data_thread = threading.Thread(
                target=self._data_collection_loop,
                name="VIXDataCollection",
                daemon=True
            )
            self._data_thread.start()
            
            # Start analysis thread
            self._analysis_thread = threading.Thread(
                target=self._analysis_loop,
                name="VIXAnalysis",
                daemon=True
            )
            self._analysis_thread.start()
            
            self.logger.info("VIX analysis started")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'start_analysis'
            })
            self.is_analyzing = False
    
    def stop_analysis(self) -> None:
        """Stop VIX analysis."""
        if not self.is_analyzing:
            return
        
        try:
            self.is_analyzing = False
            self._stop_event.set()
            
            # Wait for threads to finish
            if self._data_thread and self._data_thread.is_alive():
                self._data_thread.join(timeout=5.0)
            
            if self._analysis_thread and self._analysis_thread.is_alive():
                self._analysis_thread.join(timeout=5.0)
            
            self.logger.info("VIX analysis stopped")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'stop_analysis'
            })

    # ==========================================================================
    # DATA COLLECTION METHODS
    # ==========================================================================
    def _data_collection_loop(self) -> None:
        """Data collection loop."""
        while not self._stop_event.is_set() and self.is_analyzing:
            try:
                # Update real-time VIX data
                self._update_realtime_data()
                
                # Sleep
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_data_collection_loop'
                })
                time.sleep(60)  # Longer sleep on error
    
    def _update_realtime_data(self) -> None:
        """Update real-time VIX data."""
        try:
            current_time = datetime.now()
            
            # Only update during market hours or near market hours
            if not self._is_update_time(current_time):
                return
            
            for symbol_key, yahoo_symbol in VIX_SYMBOLS.items():
                try:
                    # Get current data from Yahoo Finance
                    ticker = yf.Ticker(yahoo_symbol)
                    info = ticker.info
                    
                    # Get current price
                    current_price = info.get('regularMarketPrice', 0.0)
                    if current_price <= 0:
                        current_price = info.get('previousClose', 0.0)
                    
                    if current_price > 0:
                        vix_data = VIXData(
                            symbol=symbol_key,
                            value=current_price,
                            timestamp=current_time
                        )
                        
                        self.vix_data[symbol_key] = vix_data
                        self.historical_data[symbol_key].append(vix_data)
                        
                        # Update technical indicators for VIX
                        if symbol_key == 'VIX':
                            self.rsi_calculator.update(current_price)
                            self.bb_calculator.update(current_price)
                
                except Exception as e:
                    self.logger.debug(f"Failed to update {symbol_key}: {e}")
                    continue
            
            self.stats['last_data_update'] = current_time
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_realtime_data'
            })
    
    def _is_update_time(self, current_time: datetime) -> bool:
        """Check if it's appropriate time to update data."""
        # Update during market hours and for 2 hours after close
        market_open = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = current_time.replace(hour=18, minute=0, second=0, microsecond=0)  # 2 hours after close
        
        # Skip weekends
        if current_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        return market_open <= current_time <= market_close

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _on_market_data(self, event: Event) -> None:
        """Handle market data events."""
        try:
            data = event.data
            symbol = data.get('symbol', '')
            
            # Check if it's a VIX-related symbol
            for vix_symbol in VIX_SYMBOLS.keys():
                if vix_symbol in symbol:
                    price = float(data.get('price', 0))
                    if price > 0:
                        vix_data = VIXData(
                            symbol=vix_symbol,
                            value=price,
                            timestamp=event.timestamp or datetime.now()
                        )
                        self._process_vix_update(vix_data)
                    break
                    
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_market_data'
            })
    
    def _on_vix_update(self, event: Event) -> None:
        """Handle VIX-specific update events."""
        try:
            data = event.data
            symbol = data.get('symbol', '')
            price = float(data.get('price', 0))
            
            if symbol in VIX_SYMBOLS.keys() and price > 0:
                vix_data = VIXData(
                    symbol=symbol,
                    value=price,
                    timestamp=event.timestamp or datetime.now()
                )
                self._process_vix_update(vix_data)
                
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_on_vix_update'
            })
    
    def _process_vix_update(self, vix_data: VIXData) -> None:
        """Process VIX data update."""
        with self._lock:
            self.vix_data[vix_data.symbol] = vix_data
            self.historical_data[vix_data.symbol].append(vix_data)
            
            # Update technical indicators for VIX
            if vix_data.symbol == 'VIX':
                self.rsi_calculator.update(vix_data.value)
                self.bb_calculator.update(vix_data.value)
            
            self.stats['updates_processed'] += 1

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def _analysis_loop(self) -> None:
        """Main analysis loop."""
        while not self._stop_event.is_set() and self.is_analyzing:
            try:
                # Update volatility metrics
                self._update_volatility_metrics()
                
                # Update term structure
                self._update_term_structure()
                
                # Update risk premium
                self._update_risk_premium()
                
                # Generate trading signals
                self._generate_trading_signals()
                
                # Check for regime changes
                self._check_regime_change()
                
                # Sleep
                time.sleep(5.0)
                
            except Exception as e:
                self.error_handler.handle_error(e, {
                    'method': '_analysis_loop'
                })
                time.sleep(10.0)
    
    def _update_volatility_metrics(self) -> None:
        """Update comprehensive volatility metrics."""
        try:
            if not self._has_sufficient_data():
                return
            
            current_time = datetime.now()
            
            # Get current VIX values
            vix = self.vix_data.get('VIX', VIXData('VIX', 0, current_time)).value
            vix9d = self.vix_data.get('VIX9D', VIXData('VIX9D', 0, current_time)).value
            vvix = self.vix_data.get('VVIX', VIXData('VVIX', 0, current_time)).value
            vxv = self.vix_data.get('VXV', VIXData('VXV', 0, current_time)).value
            vxmt = self.vix_data.get('VXMT', VIXData('VXMT', 0, current_time)).value
            
            if vix <= 0:
                return
            
            # Calculate percentiles
            vix_history = [data.value for data in self.historical_data['VIX']]
            if len(vix_history) >= 20:
                percentile_20d = stats.percentileofscore(vix_history[-20:], vix) / 100.0
                percentile_50d = stats.percentileofscore(vix_history[-50:], vix) / 100.0 if len(vix_history) >= 50 else 0.5
                percentile_200d = stats.percentileofscore(vix_history[-200:], vix) / 100.0 if len(vix_history) >= 200 else 0.5
            else:
                percentile_20d = percentile_50d = percentile_200d = 0.5
            
            # Calculate Z-score
            if len(vix_history) >= 20:
                mean_vix = np.mean(vix_history[-20:])
                std_vix = np.std(vix_history[-20:])
                z_score = (vix - mean_vix) / std_vix if std_vix > 0 else 0.0
            else:
                z_score = 0.0
            
            # Determine regime
            regime = self._classify_volatility_regime(vix, percentile_200d)
            
            # Determine trend
            trend = self._analyze_volatility_trend(vix_history)
            
            # Get technical indicators
            rsi_value = self.rsi_calculator.current_value or 50.0
            bb_position = self._calculate_bollinger_position(vix)
            
            # Create metrics object
            self.volatility_metrics = VolatilityMetrics(
                vix=vix,
                vix9d=vix9d,
                vvix=vvix,
                vxv=vxv,
                vxmt=vxmt,
                regime=regime,
                trend=trend,
                term_structure=self.term_structure.state if self.term_structure else TermStructureState.FLAT,
                percentile_20d=percentile_20d,
                percentile_50d=percentile_50d,
                percentile_200d=percentile_200d,
                z_score=z_score,
                rsi=rsi_value,
                bollinger_position=bb_position,
                timestamp=current_time
            )
            
            self.last_update = current_time
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_volatility_metrics'
            })
    
    def _update_term_structure(self) -> None:
        """Update VIX term structure analysis."""
        try:
            current_time = datetime.now()
            
            # Get required VIX values
            vix9d = self.vix_data.get('VIX9D', VIXData('VIX9D', 0, current_time)).value
            vix = self.vix_data.get('VIX', VIXData('VIX', 0, current_time)).value
            vxv = self.vix_data.get('VXV', VIXData('VXV', 0, current_time)).value
            vxmt = self.vix_data.get('VXMT', VIXData('VXMT', 0, current_time)).value
            
            if not all(v > 0 for v in [vix9d, vix, vxv, vxmt]):
                return
            
            # Calculate ratios
            vix9d_vix_ratio = vix9d / vix
            vix_vxv_ratio = vix / vxv
            vxv_vxmt_ratio = vxv / vxmt
            
            # Calculate overall slope (simplified)
            overall_slope = (vxmt - vix9d) / vix9d
            
            # Classify term structure state
            state = self._classify_term_structure_state(overall_slope, vix_vxv_ratio)
            
            self.term_structure = TermStructure(
                vix9d_vix_ratio=vix9d_vix_ratio,
                vix_vxv_ratio=vix_vxv_ratio,
                vxv_vxmt_ratio=vxv_vxmt_ratio,
                overall_slope=overall_slope,
                state=state,
                timestamp=current_time
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_term_structure'
            })
    
    def _update_risk_premium(self) -> None:
        """Update volatility risk premium analysis."""
        try:
            current_time = datetime.now()
            
            # Get VIX (implied volatility)
            vix = self.vix_data.get('VIX', VIXData('VIX', 0, current_time)).value
            if vix <= 0:
                return
            
            # Get SPY data for realized volatility calculation
            spy_data = self._get_spy_realized_volatility()
            if not spy_data:
                return
            
            # Calculate risk premiums
            risk_premium_10d = vix / 100.0 - spy_data['rv_10d']
            risk_premium_20d = vix / 100.0 - spy_data['rv_20d']
            risk_premium_30d = vix / 100.0 - spy_data['rv_30d']
            avg_risk_premium = np.mean([risk_premium_10d, risk_premium_20d, risk_premium_30d])
            
            # Calculate percentile rank of current risk premium
            historical_premiums = self._get_historical_risk_premiums()
            if historical_premiums:
                percentile_rank = stats.percentileofscore(historical_premiums, avg_risk_premium) / 100.0
            else:
                percentile_rank = 0.5
            
            self.risk_premium = VolatilityRiskPremium(
                symbol="SPY",
                implied_vol=vix / 100.0,
                realized_vol_10d=spy_data['rv_10d'],
                realized_vol_20d=spy_data['rv_20d'],
                realized_vol_30d=spy_data['rv_30d'],
                risk_premium_10d=risk_premium_10d,
                risk_premium_20d=risk_premium_20d,
                risk_premium_30d=risk_premium_30d,
                avg_risk_premium=avg_risk_premium,
                percentile_rank=percentile_rank,
                timestamp=current_time
            )
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_risk_premium'
            })

    # ==========================================================================
    # CLASSIFICATION METHODS
    # ==========================================================================
    def _classify_volatility_regime(self, vix: float, percentile: float) -> VolatilityRegime:
        """Classify volatility regime based on VIX level and percentile."""
        # Absolute level classification
        if vix >= VIX_EXTREME_HIGH:
            return VolatilityRegime.CRISIS
        elif vix >= 40.0:
            return VolatilityRegime.EXTREME_HIGH
        elif vix >= VIX_HIGH_THRESHOLD:
            return VolatilityRegime.HIGH
        elif vix >= 25.0:
            return VolatilityRegime.ELEVATED
        elif vix >= 20.0:
            return VolatilityRegime.NORMAL
        elif vix >= VIX_LOW_THRESHOLD:
            return VolatilityRegime.NORMAL_LOW
        elif vix >= VIX_EXTREME_LOW:
            return VolatilityRegime.LOW
        else:
            return VolatilityRegime.EXTREME_LOW
    
    def _analyze_volatility_trend(self, vix_history: List[float]) -> VolatilityTrend:
        """Analyze volatility trend direction."""
        if len(vix_history) < 10:
            return VolatilityTrend.STABLE
        
        current_vix = vix_history[-1]
        recent_avg = np.mean(vix_history[-5:])
        medium_avg = np.mean(vix_history[-10:])
        
        # Check for breakout/breakdown
        if len(vix_history) >= 20:
            recent_high = max(vix_history[-20:])
            recent_low = min(vix_history[-20:])
            
            if current_vix > recent_high * 1.1:  # 10% above recent high
                return VolatilityTrend.BREAKOUT
            elif current_vix < recent_low * 0.9:  # 10% below recent low
                return VolatilityTrend.BREAKDOWN
        
        # Check for rising/falling trends
        if recent_avg > medium_avg * 1.05:
            return VolatilityTrend.RISING
        elif recent_avg < medium_avg * 0.95:
            return VolatilityTrend.FALLING
        else:
            return VolatilityTrend.STABLE
    
    def _classify_term_structure_state(self, overall_slope: float, vix_vxv_ratio: float) -> TermStructureState:
        """Classify term structure state."""
        if overall_slope > 0.15:  # 15% slope
            return TermStructureState.STEEP_CONTANGO
        elif overall_slope > 0.05:  # 5% slope
            return TermStructureState.CONTANGO
        elif overall_slope > -0.05:  # Flat
            return TermStructureState.FLAT
        elif overall_slope > -0.15:  # Moderate backwardation
            return TermStructureState.BACKWARDATION
        else:  # Steep backwardation
            return TermStructureState.STEEP_BACKWARDATION

    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================
    def _generate_trading_signals(self) -> None:
        """Generate volatility-based trading signals."""
        try:
            if not self.volatility_metrics:
                return
            
            signals = []
            current_time = datetime.now()
            
            # Volatility expansion signal
            if self._detect_volatility_expansion():
                signals.append(VIXSignalData(
                    signal_type=VIXSignal.VOLATILITY_EXPANSION,
                    strength=0.8,
                    confidence=0.7,
                    description="Volatility expanding - consider long volatility strategies",
                    regime=self.volatility_metrics.regime,
                    supporting_factors=["VIX rising", "Term structure flattening"],
                    target_strategies=["Long straddles", "Long calls", "VIX calls"],
                    timestamp=current_time
                ))
            
            # Volatility contraction signal
            if self._detect_volatility_contraction():
                signals.append(VIXSignalData(
                    signal_type=VIXSignal.VOLATILITY_CONTRACTION,
                    strength=0.7,
                    confidence=0.6,
                    description="Volatility contracting - consider short volatility strategies",
                    regime=self.volatility_metrics.regime,
                    supporting_factors=["VIX declining", "Term structure steepening"],
                    target_strategies=["Short straddles", "Iron condors", "Credit spreads"],
                    timestamp=current_time
                ))
            
            # Mean reversion signal
            if self._detect_mean_reversion_opportunity():
                signals.append(VIXSignalData(
                    signal_type=VIXSignal.MEAN_REVERSION,
                    strength=0.6,
                    confidence=0.8,
                    description="VIX at extreme levels - mean reversion opportunity",
                    regime=self.volatility_metrics.regime,
                    supporting_factors=["Extreme VIX reading", "High Z-score"],
                    target_strategies=["Mean reversion trades", "Calendar spreads"],
                    timestamp=current_time
                ))
            
            # Regime shift signal
            if self._detect_regime_shift():
                signals.append(VIXSignalData(
                    signal_type=VIXSignal.REGIME_SHIFT,
                    strength=0.9,
                    confidence=0.8,
                    description="Volatility regime shift detected",
                    regime=self.volatility_metrics.regime,
                    supporting_factors=["Regime change", "Trend change"],
                    target_strategies=["Adjust portfolio allocation", "Hedge positions"],
                    timestamp=current_time
                ))
            
            # Store signals
            for signal in signals:
                self.signal_history.append(signal)
                self._emit_signal_event(signal)
                self.stats['signals_generated'] += 1
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_trading_signals'
            })

    # ==========================================================================
    # SIGNAL DETECTION METHODS
    # ==========================================================================
    def _detect_volatility_expansion(self) -> bool:
        """Detect volatility expansion conditions."""
        if not self.volatility_metrics:
            return False
        
        conditions = [
            self.volatility_metrics.trend in [VolatilityTrend.RISING, VolatilityTrend.BREAKOUT],
            self.volatility_metrics.z_score > 1.0,
            self.volatility_metrics.percentile_20d > 0.8,
            self.volatility_metrics.rsi > 60
        ]
        
        return sum(conditions) >= 2
    
    def _detect_volatility_contraction(self) -> bool:
        """Detect volatility contraction conditions."""
        if not self.volatility_metrics:
            return False
        
        conditions = [
            self.volatility_metrics.trend in [VolatilityTrend.FALLING, VolatilityTrend.BREAKDOWN],
            self.volatility_metrics.z_score < -1.0,
            self.volatility_metrics.percentile_20d < 0.2,
            self.volatility_metrics.rsi < 40
        ]
        
        return sum(conditions) >= 2
    
    def _detect_mean_reversion_opportunity(self) -> bool:
        """Detect mean reversion opportunities."""
        if not self.volatility_metrics:
            return False
        
        # Extreme high or low readings
        extreme_high = (
            self.volatility_metrics.vix > VIX_HIGH_THRESHOLD and
            self.volatility_metrics.percentile_200d > 0.9 and
            abs(self.volatility_metrics.z_score) > 2.0
        )
        
        extreme_low = (
            self.volatility_metrics.vix < VIX_LOW_THRESHOLD and
            self.volatility_metrics.percentile_200d < 0.1 and
            abs(self.volatility_metrics.z_score) > 2.0
        )
        
        return extreme_high or extreme_low
    
    def _detect_regime_shift(self) -> bool:
        """Detect volatility regime shifts."""
        if not self.volatility_metrics or len(self.regime_history) < 5:
            return False
        
        # Check if regime has changed recently
        current_regime = self.volatility_metrics.regime
        recent_regimes = [entry.regime for entry in list(self.regime_history)[-5:]]
        
        # If current regime is different from recent average
        if all(regime != current_regime for regime in recent_regimes):
            return True
        
        return False

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _has_sufficient_data(self) -> bool:
        """Check if we have sufficient data for analysis."""
        return (
            len(self.historical_data.get('VIX', [])) >= MIN_DATA_POINTS and
            'VIX' in self.vix_data
        )
    
    def _calculate_bollinger_position(self, current_vix: float) -> float:
        """Calculate position within Bollinger Bands."""
        if not self.bb_calculator.upper_band or not self.bb_calculator.lower_band:
            return 0.5
        
        band_width = self.bb_calculator.upper_band - self.bb_calculator.lower_band
        if band_width <= 0:
            return 0.5
        
        position = (current_vix - self.bb_calculator.lower_band) / band_width
        return max(0.0, min(1.0, position))
    
    def _get_spy_realized_volatility(self) -> Optional[Dict[str, float]]:
        """Get SPY realized volatility for different periods."""
        try:
            # This would typically get SPY price data and calculate realized vol
            # For now, return simulated values
            return {
                'rv_10d': 0.15,  # 15% annualized
                'rv_20d': 0.18,  # 18% annualized
                'rv_30d': 0.20   # 20% annualized
            }
        except Exception:
            return None
    
    def _get_historical_risk_premiums(self) -> List[float]:
        """Get historical risk premiums for percentile calculation."""
        # This would calculate historical risk premiums
        # For now, return sample data
        return [0.02, 0.03, 0.01, -0.01, 0.05, 0.04, 0.02, -0.02, 0.06, 0.03]
    
    def _check_regime_change(self) -> None:
        """Check for and record regime changes."""
        if not self.volatility_metrics:
            return
        
        # Add current metrics to history
        self.regime_history.append(self.volatility_metrics)
        
        # Check for regime change
        if len(self.regime_history) >= 2:
            previous_regime = self.regime_history[-2].regime
            current_regime = self.volatility_metrics.regime
            
            if previous_regime != current_regime:
                self.stats['regime_changes'] += 1
                self._emit_regime_change_event(previous_regime, current_regime)
    
    def _emit_signal_event(self, signal: VIXSignalData) -> None:
        """Emit VIX signal event."""
        if self.event_manager:
            event = Event(
                event_type=EventType.VIX_SIGNAL,
                data={
                    'signal_type': signal.signal_type.value,
                    'strength': signal.strength,
                    'confidence': signal.confidence,
                    'description': signal.description,
                    'regime': signal.regime.value,
                    'supporting_factors': signal.supporting_factors,
                    'target_strategies': signal.target_strategies
                },
                timestamp=signal.timestamp
            )
            self.event_manager.emit(event)
    
    def _emit_regime_change_event(self, old_regime: VolatilityRegime, new_regime: VolatilityRegime) -> None:
        """Emit regime change event."""
        if self.event_manager:
            event = Event(
                event_type=EventType.REGIME_CHANGE,
                data={
                    'old_regime': old_regime.value,
                    'new_regime': new_regime.value,
                    'timestamp': datetime.now().isoformat()
                },
                timestamp=datetime.now()
            )
            self.event_manager.emit(event)

    # ==========================================================================
    # PUBLIC API METHODS
    # ==========================================================================
    def get_current_metrics(self) -> Optional[VolatilityMetrics]:
        """
        Get current volatility metrics.
        
        Returns:
            VolatilityMetrics if available, None otherwise
        """
        return self.volatility_metrics
    
    def get_term_structure(self) -> Optional[TermStructure]:
        """
        Get current term structure analysis.
        
        Returns:
            TermStructure if available, None otherwise
        """
        return self.term_structure
    
    def get_risk_premium(self) -> Optional[VolatilityRiskPremium]:
        """
        Get current volatility risk premium.
        
        Returns:
            VolatilityRiskPremium if available, None otherwise
        """
        return self.risk_premium
    
    def get_trading_signals(self, limit: int = 5) -> List[VIXSignalData]:
        """
        Get recent trading signals.
        
        Args:
            limit: Maximum number of signals to return
            
        Returns:
            List of recent VIXSignalData
        """
        return list(self.signal_history)[-limit:]
    
    def get_latest_signal(self) -> Optional[VIXSignalData]:
        """
        Get most recent trading signal.
        
        Returns:
            Latest VIXSignalData if available, None otherwise
        """
        return self.signal_history[-1] if self.signal_history else None
    
    def get_regime_history(self, days: int = 30) -> List[VolatilityMetrics]:
        """
        Get volatility regime history.
        
        Args:
            days: Number of days of history to return
            
        Returns:
            List of VolatilityMetrics for specified period
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        return [
            metrics for metrics in self.regime_history
            if metrics.timestamp >= cutoff_date
        ]
    
    def get_vix_percentile(self, period: int = 252) -> Optional[float]:
        """
        Get current VIX percentile rank.
        
        Args:
            period: Lookback period in days
            
        Returns:
            Percentile rank (0.0 to 1.0) if available, None otherwise
        """
        if not self.volatility_metrics:
            return None
        
        if period <= 20:
            return self.volatility_metrics.percentile_20d
        elif period <= 50:
            return self.volatility_metrics.percentile_50d
        else:
            return self.volatility_metrics.percentile_200d
    
    def is_low_volatility_regime(self) -> bool:
        """
        Check if currently in low volatility regime.
        
        Returns:
            True if in low volatility regime, False otherwise
        """
        if not self.volatility_metrics:
            return False
        
        return self.volatility_metrics.regime in [
            VolatilityRegime.EXTREME_LOW,
            VolatilityRegime.LOW,
            VolatilityRegime.NORMAL_LOW
        ]
    
    def is_high_volatility_regime(self) -> bool:
        """
        Check if currently in high volatility regime.
        
        Returns:
            True if in high volatility regime, False otherwise
        """
        if not self.volatility_metrics:
            return False
        
        return self.volatility_metrics.regime in [
            VolatilityRegime.HIGH,
            VolatilityRegime.EXTREME_HIGH,
            VolatilityRegime.CRISIS
        ]
    
    def get_recommended_strategies(self) -> List[str]:
        """
        Get strategy recommendations based on current volatility environment.
        
        Returns:
            List of recommended strategy types
        """
        if not self.volatility_metrics:
            return []
        
        strategies = []
        
        # Based on volatility regime
        if self.is_low_volatility_regime():
            strategies.extend([
                "Short volatility strategies",
                "Iron condors",
                "Credit spreads",
                "Covered calls"
            ])
        elif self.is_high_volatility_regime():
            strategies.extend([
                "Long volatility strategies",
                "Long straddles",
                "Calendar spreads",
                "Protective puts"
            ])
        else:
            strategies.extend([
                "Neutral strategies",
                "Iron butterflies",
                "Ratio spreads"
            ])
        
        # Based on trend
        if self.volatility_metrics.trend == VolatilityTrend.RISING:
            strategies.append("Long volatility")
        elif self.volatility_metrics.trend == VolatilityTrend.FALLING:
            strategies.append("Short volatility")
        
        # Based on term structure
        if self.term_structure:
            if self.term_structure.is_contango:
                strategies.append("VIX calendar spreads")
            elif self.term_structure.is_backwardation:
                strategies.append("Short VIX futures")
        
        return list(set(strategies))  # Remove duplicates
    
    def get_volatility_forecast(self, days_ahead: int = 5) -> Dict[str, float]:
        """
        Get simple volatility forecast.
        
        Args:
            days_ahead: Number of days to forecast
            
        Returns:
            Dictionary with forecast metrics
        """
        if not self.volatility_metrics or not self.historical_data.get('VIX'):
            return {}
        
        current_vix = self.volatility_metrics.vix
        vix_history = [data.value for data in self.historical_data['VIX'][-20:]]
        
        # Simple moving average forecast
        short_ma = np.mean(vix_history[-5:])
        long_ma = np.mean(vix_history[-20:])
        
        # Trend-based adjustment
        trend_factor = 1.0
        if self.volatility_metrics.trend == VolatilityTrend.RISING:
            trend_factor = 1.05
        elif self.volatility_metrics.trend == VolatilityTrend.FALLING:
            trend_factor = 0.95
        
        forecast = short_ma * trend_factor
        
        return {
            'forecast_vix': forecast,
            'current_vix': current_vix,
            'short_ma': short_ma,
            'long_ma': long_ma,
            'trend_factor': trend_factor,
            'confidence': 0.6  # Simple model, low confidence
        }

    # ==========================================================================
    # CLEANUP METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up VIX analyzer resources."""
        try:
            # Stop analysis
            self.stop_analysis()
            
            # Clear data structures
            with self._lock:
                self.vix_data.clear()
                self.historical_data.clear()
                self.regime_history.clear()
                self.signal_history.clear()
                self.volatility_metrics = None
                self.term_structure = None
                self.risk_premium = None
            
            self.logger.info("VIX analyzer cleanup completed")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'cleanup'
            })

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_vix_analyzer(config: Optional[Dict] = None) -> VIXAnalyzer:
    """
    Get singleton instance of VIX analyzer.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        VIXAnalyzer instance
    """
    global _vix_analyzer_instance
    if _vix_analyzer_instance is None:
        _vix_analyzer_instance = VIXAnalyzer(config)
    return _vix_analyzer_instance

def classify_volatility_regime(vix_level: float) -> VolatilityRegime:
    """
    Helper function to classify volatility regime.
    
    Args:
        vix_level: Current VIX level
        
    Returns:
        VolatilityRegime classification
    """
    if vix_level >= 50.0:
        return VolatilityRegime.CRISIS
    elif vix_level >= 40.0:
        return VolatilityRegime.EXTREME_HIGH
    elif vix_level >= 30.0:
        return VolatilityRegime.HIGH
    elif vix_level >= 25.0:
        return VolatilityRegime.ELEVATED
    elif vix_level >= 20.0:
        return VolatilityRegime.NORMAL
    elif vix_level >= 15.0:
        return VolatilityRegime.NORMAL_LOW
    elif vix_level >= 10.0:
        return VolatilityRegime.LOW
    else:
        return VolatilityRegime.EXTREME_LOW

def calculate_volatility_risk_premium(implied_vol: float, realized_vol: float) -> float:
    """
    Calculate volatility risk premium.
    
    Args:
        implied_vol: Implied volatility (from VIX)
        realized_vol: Realized volatility
        
    Returns:
        Risk premium (implied - realized)
    """
    return implied_vol - realized_vol

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Global instance
_vix_analyzer_instance: Optional[VIXAnalyzer] = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("📊 Testing VIX Analyzer...")
    
    analyzer = VIXAnalyzer()
    
    if analyzer.initialize():
        print("✅ VIX Analyzer initialized successfully")
        
        # Start analysis
        analyzer.start_analysis()
        
        # Simulate VIX data update
        test_vix_data = VIXData(
            symbol="VIX",
            value=22.5,
            timestamp=datetime.now()
        )
        analyzer._process_vix_update(test_vix_data)
        
        # Wait for analysis
        time.sleep(3)
        
        # Get results
        metrics = analyzer.get_current_metrics()
        if metrics:
            print(f"📈 Volatility Metrics:")
            print(f"  VIX: {metrics.vix:.2f}")
            print(f"  Regime: {metrics.regime.value}")
            print(f"  Trend: {metrics.trend.value}")
            print(f"  20D Percentile: {metrics.percentile_20d:.1%}")
            print(f"  Z-Score: {metrics.z_score:.2f}")
            print(f"  RSI: {metrics.rsi:.1f}")
        
        term_structure = analyzer.get_term_structure()
        if term_structure:
            print(f"📐 Term Structure:")
            print(f"  State: {term_structure.state.value}")
            print(f"  Overall Slope: {term_structure.overall_slope:.3f}")
        
        risk_premium = analyzer.get_risk_premium()
        if risk_premium:
            print(f"💰 Risk Premium:")
            print(f"  Average: {risk_premium.avg_risk_premium:.3f}")
            print(f"  Percentile: {risk_premium.percentile_rank:.1%}")
        
        signals = analyzer.get_trading_signals()
        if signals:
            print(f"🚨 Recent Signals: {len(signals)}")
            for signal in signals[-3:]:  # Show last 3
                print(f"  {signal.signal_type.value}: {signal.description}")
        
        strategies = analyzer.get_recommended_strategies()
        print(f"💡 Recommended Strategies:")
        for strategy in strategies[:5]:  # Show first 5
            print(f"  - {strategy}")
        
        forecast = analyzer.get_volatility_forecast()
        if forecast:
            print(f"🔮 Forecast:")
            print(f"  Predicted VIX: {forecast.get('forecast_vix', 0):.2f}")
            print(f"  Confidence: {forecast.get('confidence', 0):.1%}")
        
        # Test regime classification
        test_vix_levels = [8.5, 12.0, 18.0, 25.0, 35.0, 55.0]
        print(f"\n🎯 Regime Classification Tests:")
        for vix_level in test_vix_levels:
            regime = classify_volatility_regime(vix_level)
            print(f"  VIX {vix_level:.1f}: {regime.value}")
        
        # Test risk premium calculation
        risk_prem = calculate_volatility_risk_premium(0.25, 0.20)
        print(f"\n💼 Risk Premium Test: {risk_prem:.3f}")
        
        time.sleep(2)
        
        # Cleanup
        analyzer.cleanup()
        print("🧹 Cleanup completed")
        
    else:
        print("❌ VIX Analyzer initialization failed")