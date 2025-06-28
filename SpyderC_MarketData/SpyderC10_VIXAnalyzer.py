#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC10_VIXAnalyzer.py
Group: C (Market Data)
Purpose: Advanced VIX analysis and volatility regime detection

Description:
    This module provides comprehensive VIX analysis including term structure,
    contango/backwardation detection, volatility regime identification, and
    mean reversion signals. It analyzes VIX futures, VIX options, and related
    volatility products to generate actionable trading signals for SPY options
    strategies.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 18:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
import bisect
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Tuple, Any, Set, Deque
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum, auto
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats, interpolate
from sklearn.linear_model import LinearRegression

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderB_Broker.SpyderB01_IBClient import IBClient
from SpyderC_MarketData.SpyderC01_DataFeed import DataFeed
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# VIX Levels and Regimes
VIX_LOW = 12.0
VIX_NORMAL_LOW = 15.0
VIX_NORMAL_HIGH = 20.0
VIX_ELEVATED = 25.0
VIX_HIGH = 30.0
VIX_EXTREME = 40.0

# Term Structure Parameters
CONTANGO_THRESHOLD = 0.05  # 5% premium for contango
BACKWARDATION_THRESHOLD = -0.05  # 5% discount for backwardation
STEEP_CURVE_THRESHOLD = 0.15  # 15% for steep curve

# Mean Reversion Parameters
VIX_MEAN = 16.0  # Long-term VIX mean
MEAN_REVERSION_SPEED = 5.0  # Ornstein-Uhlenbeck parameter
ZSCORE_THRESHOLD = 2.0  # Standard deviations for signals

# Trading Signal Parameters
VIX_SPY_CORRELATION_WINDOW = 20  # Days
DIVERGENCE_THRESHOLD = 0.3  # Correlation divergence
SPIKE_THRESHOLD = 0.25  # 25% intraday spike

# VIX Futures Symbols
VIX_FUTURES_MONTHS = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
MAX_FUTURES_MONTHS = 9  # Track up to 9 months out

# Update Frequencies
VIX_UPDATE_INTERVAL = 5  # Seconds
TERM_STRUCTURE_UPDATE = 60  # Seconds
REGIME_CHECK_INTERVAL = 30  # Seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class VIXRegime(Enum):
    """VIX volatility regimes"""
    LOW_VOL = "low_volatility"          # VIX < 12
    NORMAL = "normal"                   # VIX 12-20
    ELEVATED = "elevated"               # VIX 20-25
    HIGH_VOL = "high_volatility"        # VIX 25-30
    STRESS = "market_stress"            # VIX 30-40
    PANIC = "panic"                     # VIX > 40

class TermStructureShape(Enum):
    """VIX term structure shapes"""
    CONTANGO = "contango"               # Normal, upward sloping
    BACKWARDATION = "backwardation"     # Inverted, stress
    FLAT = "flat"                       # Neutral
    STEEP_CONTANGO = "steep_contango"   # Very bullish
    STEEP_BACKWARDATION = "steep_backwardation"  # Very bearish

class VIXSignal(Enum):
    """VIX-based trading signals"""
    MEAN_REVERSION_LONG = "mean_reversion_long"
    MEAN_REVERSION_SHORT = "mean_reversion_short"
    REGIME_CHANGE = "regime_change"
    TERM_STRUCTURE_TRADE = "term_structure_trade"
    VOLATILITY_SPIKE = "volatility_spike"
    DIVERGENCE_SIGNAL = "divergence_signal"
    CONTANGO_ROLL = "contango_roll"
    COMPLACENCY_WARNING = "complacency_warning"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VIXData:
    """Current VIX data snapshot"""
    timestamp: datetime
    vix_spot: float
    vix_close: float
    vix_high: float
    vix_low: float
    vix_change: float
    vix_change_pct: float
    
    # Related indices
    vix9d: Optional[float] = None  # 9-day VIX
    vix3m: Optional[float] = None  # 3-month VIX
    vvix: Optional[float] = None   # VIX of VIX
    
    # Ratios
    vix_vix3m_ratio: Optional[float] = None
    vix_vix9d_ratio: Optional[float] = None

@dataclass
class VIXFuture:
    """VIX future contract data"""
    symbol: str
    expiry: date
    price: float
    volume: int
    open_interest: int
    days_to_expiry: int
    basis: float  # vs spot VIX
    roll_yield: float  # vs previous month

@dataclass
class TermStructure:
    """VIX term structure analysis"""
    timestamp: datetime
    spot_vix: float
    futures: List[VIXFuture]
    
    # Structure metrics
    shape: TermStructureShape
    slope: float  # Overall slope
    curvature: float  # Second derivative
    
    # Key spreads
    front_month_basis: float
    second_month_basis: float
    calendar_spread: float  # M2-M1
    
    # Roll characteristics
    daily_roll: float  # Contango/backwardation cost
    annualized_roll: float

@dataclass
class VIXRegimeAnalysis:
    """Comprehensive VIX regime analysis"""
    timestamp: datetime
    current_regime: VIXRegime
    regime_duration: int  # Days in current regime
    
    # Statistical measures
    percentile_1y: float  # 1-year percentile
    percentile_5y: float  # 5-year percentile
    zscore: float  # Standard score
    
    # Mean reversion
    distance_from_mean: float
    expected_reversion: float  # Target level
    reversion_probability: float
    
    # Regime transition probabilities
    regime_transitions: Dict[VIXRegime, float]

@dataclass
class VIXDivergence:
    """VIX-SPY divergence analysis"""
    timestamp: datetime
    vix_spy_correlation: float
    historical_correlation: float
    divergence_score: float
    
    # Divergence details
    vix_trend: str  # 'up', 'down', 'flat'
    spy_trend: str
    is_divergent: bool
    divergence_type: str  # 'bullish' or 'bearish'
    
    # Signal strength
    confidence: float
    suggested_action: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class VIXAnalyzer:
    """
    Advanced VIX analysis and volatility regime detection.
    
    This class provides comprehensive VIX analysis including term structure,
    mean reversion signals, regime detection, and SPY correlation analysis.
    It generates actionable trading signals for volatility strategies.
    
    Attributes:
        logger: Module logger
        current_vix: Current VIX data
        term_structure: Current term structure
        regime_analysis: Current regime analysis
        
    Example:
        >>> vix_analyzer = VIXAnalyzer()
        >>> regime = vix_analyzer.get_current_regime()
        >>> signals = vix_analyzer.generate_vix_signals()
    """
    
    def __init__(self,
                 ib_client: Optional[IBClient] = None,
                 data_feed: Optional[DataFeed] = None):
        """
        Initialize VIX analyzer.
        
        Args:
            ib_client: IB client for market data
            data_feed: Data feed for real-time updates
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data sources
        self.ib_client = ib_client or IBClient()
        self.data_feed = data_feed or DataFeed()
        self.event_manager = get_event_manager()
        
        # Current state
        self.current_vix: Optional[VIXData] = None
        self.term_structure: Optional[TermStructure] = None
        self.regime_analysis: Optional[VIXRegimeAnalysis] = None
        
        # Historical data
        self.vix_history: Deque[VIXData] = deque(maxlen=390 * 20)  # 20 days intraday
        self.regime_history: Deque[Tuple[datetime, VIXRegime]] = deque(maxlen=1000)
        self.term_structure_history: Deque[TermStructure] = deque(maxlen=100)
        
        # Futures tracking
        self.vix_futures: Dict[str, VIXFuture] = {}
        self.futures_expirations: List[date] = []
        
        # Statistical parameters
        self.vix_mean = VIX_MEAN
        self.vix_std = 8.0  # Will be updated dynamically
        self.mean_reversion_speed = MEAN_REVERSION_SPEED
        
        # SPY correlation tracking
        self.spy_prices: Deque[float] = deque(maxlen=390 * 20)
        self.correlation_window = VIX_SPY_CORRELATION_WINDOW
        
        # Threading
        self._lock = threading.RLock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        
        # Initialize components
        self._initialize_historical_data()
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - REAL-TIME ANALYSIS
    # ==========================================================================
    
    def update_vix_data(self, vix_data: Optional[Dict[str, float]] = None) -> VIXData:
        """
        Update current VIX data.
        
        Args:
            vix_data: Optional VIX data dict, fetches if None
            
        Returns:
            Updated VIX data
        """
        try:
            if vix_data is None:
                vix_data = self._fetch_vix_data()
            
            # Create VIX data object
            prev_vix = self.current_vix.vix_spot if self.current_vix else vix_data['close']
            
            current = VIXData(
                timestamp=datetime.now(),
                vix_spot=vix_data['last'],
                vix_close=vix_data['close'],
                vix_high=vix_data['high'],
                vix_low=vix_data['low'],
                vix_change=vix_data['last'] - vix_data['close'],
                vix_change_pct=(vix_data['last'] - vix_data['close']) / vix_data['close'] * 100,
                vix9d=vix_data.get('vix9d'),
                vix3m=vix_data.get('vix3m'),
                vvix=vix_data.get('vvix')
            )
            
            # Calculate ratios
            if current.vix3m:
                current.vix_vix3m_ratio = current.vix_spot / current.vix3m
            if current.vix9d:
                current.vix_vix9d_ratio = current.vix_spot / current.vix9d
            
            # Update state
            with self._lock:
                self.current_vix = current
                self.vix_history.append(current)
            
            # Check for significant changes
            self._check_vix_alerts(current, prev_vix)
            
            return current
            
        except Exception as e:
            self.logger.error(f"Error updating VIX data: {e}")
            self.error_handler.handle_error(e)
            raise
    
    def analyze_term_structure(self) -> TermStructure:
        """
        Analyze VIX futures term structure.
        
        Returns:
            Term structure analysis
        """
        try:
            # Update futures data
            self._update_futures_data()
            
            if not self.vix_futures or not self.current_vix:
                raise ValueError("Insufficient data for term structure analysis")
            
            # Sort futures by expiry
            sorted_futures = sorted(self.vix_futures.values(), key=lambda x: x.expiry)
            
            # Calculate shape and metrics
            shape = self._determine_term_structure_shape(sorted_futures)
            slope = self._calculate_term_slope(sorted_futures)
            curvature = self._calculate_curvature(sorted_futures)
            
            # Key spreads
            front_month = sorted_futures[0] if sorted_futures else None
            second_month = sorted_futures[1] if len(sorted_futures) > 1 else None
            
            front_basis = front_month.basis if front_month else 0
            second_basis = second_month.basis if second_month else 0
            calendar_spread = (second_month.price - front_month.price) if (front_month and second_month) else 0
            
            # Roll calculations
            daily_roll = self._calculate_daily_roll(front_month, second_month) if (front_month and second_month) else 0
            
            structure = TermStructure(
                timestamp=datetime.now(),
                spot_vix=self.current_vix.vix_spot,
                futures=sorted_futures,
                shape=shape,
                slope=slope,
                curvature=curvature,
                front_month_basis=front_basis,
                second_month_basis=second_basis,
                calendar_spread=calendar_spread,
                daily_roll=daily_roll,
                annualized_roll=daily_roll * 252
            )
            
            # Update state
            with self._lock:
                self.term_structure = structure
                self.term_structure_history.append(structure)
            
            # Generate signals if applicable
            self._check_term_structure_signals(structure)
            
            return structure
            
        except Exception as e:
            self.logger.error(f"Error analyzing term structure: {e}")
            self.error_handler.handle_error(e)
            raise
    
    def analyze_regime(self) -> VIXRegimeAnalysis:
        """
        Analyze current VIX regime and transition probabilities.
        
        Returns:
            Comprehensive regime analysis
        """
        try:
            if not self.current_vix:
                raise ValueError("No current VIX data available")
            
            vix = self.current_vix.vix_spot
            
            # Determine current regime
            regime = self._classify_vix_regime(vix)
            
            # Calculate regime duration
            regime_duration = self._calculate_regime_duration(regime)
            
            # Statistical measures
            percentile_1y = self._calculate_percentile(vix, 252)
            percentile_5y = self._calculate_percentile(vix, 252 * 5)
            zscore = (vix - self.vix_mean) / self.vix_std
            
            # Mean reversion analysis
            distance_from_mean = vix - self.vix_mean
            expected_reversion = self._calculate_mean_reversion_target(vix)
            reversion_prob = self._calculate_reversion_probability(vix)
            
            # Regime transition probabilities
            transitions = self._calculate_regime_transitions(regime)
            
            analysis = VIXRegimeAnalysis(
                timestamp=datetime.now(),
                current_regime=regime,
                regime_duration=regime_duration,
                percentile_1y=percentile_1y,
                percentile_5y=percentile_5y,
                zscore=zscore,
                distance_from_mean=distance_from_mean,
                expected_reversion=expected_reversion,
                reversion_probability=reversion_prob,
                regime_transitions=transitions
            )
            
            # Update state
            with self._lock:
                self.regime_analysis = analysis
                
                # Track regime changes
                if not self.regime_history or self.regime_history[-1][1] != regime:
                    self.regime_history.append((datetime.now(), regime))
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing regime: {e}")
            self.error_handler.handle_error(e)
            raise
    
    def detect_divergence(self, spy_price: float) -> VIXDivergence:
        """
        Detect VIX-SPY divergence.
        
        Args:
            spy_price: Current SPY price
            
        Returns:
            Divergence analysis
        """
        try:
            if not self.current_vix:
                raise ValueError("No current VIX data")
            
            # Update SPY price history
            self.spy_prices.append(spy_price)
            
            # Need sufficient history
            if len(self.vix_history) < self.correlation_window * 78:  # 78 = 5-min bars per day
                return self._create_no_divergence()
            
            # Calculate correlations
            vix_spy_corr = self._calculate_vix_spy_correlation(self.correlation_window)
            historical_corr = self._calculate_historical_correlation()
            
            # Determine trends
            vix_trend = self._determine_trend(
                [v.vix_spot for v in list(self.vix_history)[-78:]]
            )
            spy_trend = self._determine_trend(list(self.spy_prices)[-78:])
            
            # Check for divergence
            is_divergent = abs(vix_spy_corr - historical_corr) > DIVERGENCE_THRESHOLD
            
            # Classify divergence
            divergence_type = 'none'
            suggested_action = 'hold'
            
            if is_divergent:
                if vix_trend == 'up' and spy_trend == 'up':
                    divergence_type = 'bearish'
                    suggested_action = 'buy_puts'
                elif vix_trend == 'down' and spy_trend == 'down':
                    divergence_type = 'bullish'
                    suggested_action = 'buy_calls'
            
            # Calculate confidence
            divergence_score = abs(vix_spy_corr - historical_corr)
            confidence = min(divergence_score / 0.5, 1.0) if is_divergent else 0
            
            divergence = VIXDivergence(
                timestamp=datetime.now(),
                vix_spy_correlation=vix_spy_corr,
                historical_correlation=historical_corr,
                divergence_score=divergence_score,
                vix_trend=vix_trend,
                spy_trend=spy_trend,
                is_divergent=is_divergent,
                divergence_type=divergence_type,
                confidence=confidence,
                suggested_action=suggested_action
            )
            
            return divergence
            
        except Exception as e:
            self.logger.error(f"Error detecting divergence: {e}")
            return self._create_no_divergence()
    
    # ==========================================================================
    # PUBLIC METHODS - SIGNAL GENERATION
    # ==========================================================================
    
    def generate_vix_signals(self) -> List[Dict[str, Any]]:
        """
        Generate comprehensive VIX-based trading signals.
        
        Returns:
            List of actionable trading signals
        """
        signals = []
        
        if not all([self.current_vix, self.regime_analysis, self.term_structure]):
            self.logger.warning("Insufficient data for signal generation")
            return signals
        
        # Mean reversion signals
        mean_rev_signals = self._generate_mean_reversion_signals()
        signals.extend(mean_rev_signals)
        
        # Term structure signals
        term_signals = self._generate_term_structure_signals()
        signals.extend(term_signals)
        
        # Regime change signals
        regime_signals = self._generate_regime_signals()
        signals.extend(regime_signals)
        
        # Spike/crash signals
        spike_signals = self._generate_spike_signals()
        signals.extend(spike_signals)
        
        # Sort by confidence
        signals.sort(key=lambda x: x['confidence'], reverse=True)
        
        return signals
    
    def get_volatility_forecast(self, horizon: int = 5) -> Dict[str, float]:
        """
        Forecast volatility over specified horizon.
        
        Args:
            horizon: Forecast horizon in days
            
        Returns:
            Volatility forecast metrics
        """
        if not self.current_vix:
            return {}
        
        current_vix = self.current_vix.vix_spot
        
        # Mean reversion forecast
        mean_rev_forecast = self._mean_reversion_forecast(current_vix, horizon)
        
        # Term structure implied forecast
        term_forecast = self._term_structure_forecast(horizon)
        
        # Regime-based forecast
        regime_forecast = self._regime_based_forecast(horizon)
        
        # Weighted average
        weights = {'mean_rev': 0.4, 'term': 0.3, 'regime': 0.3}
        weighted_forecast = (
            weights['mean_rev'] * mean_rev_forecast +
            weights['term'] * term_forecast +
            weights['regime'] * regime_forecast
        )
        
        return {
            'current_vix': current_vix,
            'mean_reversion_forecast': mean_rev_forecast,
            'term_structure_forecast': term_forecast,
            'regime_forecast': regime_forecast,
            'weighted_forecast': weighted_forecast,
            'confidence_interval': self._calculate_forecast_ci(weighted_forecast, horizon)
        }
    
    # ==========================================================================
    # PRIVATE METHODS - DATA FETCHING
    # ==========================================================================
    
    def _fetch_vix_data(self) -> Dict[str, float]:
        """Fetch current VIX data from IB."""
        try:
            # Get VIX index data
            vix_contract = self.ib_client.create_index_contract('VIX')
            vix_data = self.ib_client.get_market_data(vix_contract)
            
            # Get related indices if available
            vix9d_data = self._safe_fetch_index('VIX9D')
            vix3m_data = self._safe_fetch_index('VIX3M')
            vvix_data = self._safe_fetch_index('VVIX')
            
            return {
                'last': vix_data['last'],
                'close': vix_data['close'],
                'high': vix_data['high'],
                'low': vix_data['low'],
                'vix9d': vix9d_data.get('last') if vix9d_data else None,
                'vix3m': vix3m_data.get('last') if vix3m_data else None,
                'vvix': vvix_data.get('last') if vvix_data else None
            }
            
        except Exception as e:
            self.logger.error(f"Error fetching VIX data: {e}")
            # Return mock data for testing
            return {
                'last': 16.5,
                'close': 16.0,
                'high': 17.0,
                'low': 15.5,
                'vix9d': 15.0,
                'vix3m': 18.0,
                'vvix': 90.0
            }
    
    def _safe_fetch_index(self, symbol: str) -> Optional[Dict[str, float]]:
        """Safely fetch index data."""
        try:
            contract = self.ib_client.create_index_contract(symbol)
            return self.ib_client.get_market_data(contract)
        except:
            return None
    
    def _update_futures_data(self) -> None:
        """Update VIX futures data."""
        try:
            # Generate futures symbols
            futures_symbols = self._generate_futures_symbols()
            
            # Clear old data
            self.vix_futures.clear()
            
            # Fetch each future
            for symbol in futures_symbols[:MAX_FUTURES_MONTHS]:
                try:
                    contract = self.ib_client.create_futures_contract(
                        symbol=symbol,
                        exchange='CFE'
                    )
                    
                    data = self.ib_client.get_market_data(contract)
                    if data and data.get('last'):
                        # Create future object
                        expiry = self._parse_futures_expiry(symbol)
                        days_to_expiry = (expiry - date.today()).days
                        
                        future = VIXFuture(
                            symbol=symbol,
                            expiry=expiry,
                            price=data['last'],
                            volume=data.get('volume', 0),
                            open_interest=data.get('open_interest', 0),
                            days_to_expiry=days_to_expiry,
                            basis=data['last'] - self.current_vix.vix_spot,
                            roll_yield=0  # Calculated later
                        )
                        
                        self.vix_futures[symbol] = future
                        
                except Exception as e:
                    self.logger.debug(f"Could not fetch {symbol}: {e}")
            
            # Calculate roll yields
            self._calculate_roll_yields()
            
        except Exception as e:
            self.logger.error(f"Error updating futures data: {e}")
    
    def _generate_futures_symbols(self) -> List[str]:
        """Generate VIX futures symbols for next N months."""
        symbols = []
        current_date = date.today()
        
        for i in range(MAX_FUTURES_MONTHS):
            future_date = current_date + timedelta(days=30 * i)
            month_code = VIX_FUTURES_MONTHS[future_date.month - 1]
            year_code = str(future_date.year)[-1]
            symbols.append(f"VX{month_code}{year_code}")
        
        return symbols
    
    # ==========================================================================
    # PRIVATE METHODS - ANALYSIS
    # ==========================================================================
    
    def _classify_vix_regime(self, vix: float) -> VIXRegime:
        """Classify VIX level into regime."""
        if vix < VIX_LOW:
            return VIXRegime.LOW_VOL
        elif vix < VIX_NORMAL_HIGH:
            return VIXRegime.NORMAL
        elif vix < VIX_ELEVATED:
            return VIXRegime.ELEVATED
        elif vix < VIX_HIGH:
            return VIXRegime.HIGH_VOL
        elif vix < VIX_EXTREME:
            return VIXRegime.STRESS
        else:
            return VIXRegime.PANIC
    
    def _determine_term_structure_shape(self, futures: List[VIXFuture]) -> TermStructureShape:
        """Determine term structure shape."""
        if len(futures) < 2:
            return TermStructureShape.FLAT
        
        # Calculate average slope
        slopes = []
        for i in range(len(futures) - 1):
            slope = (futures[i+1].price - futures[i].price) / futures[i].price
            slopes.append(slope)
        
        avg_slope = np.mean(slopes)
        
        if avg_slope > CONTANGO_THRESHOLD:
            if avg_slope > STEEP_CURVE_THRESHOLD:
                return TermStructureShape.STEEP_CONTANGO
            return TermStructureShape.CONTANGO
        elif avg_slope < BACKWARDATION_THRESHOLD:
            if avg_slope < -STEEP_CURVE_THRESHOLD:
                return TermStructureShape.STEEP_BACKWARDATION
            return TermStructureShape.BACKWARDATION
        else:
            return TermStructureShape.FLAT
    
    def _calculate_mean_reversion_target(self, current_vix: float) -> float:
        """Calculate mean reversion target using Ornstein-Uhlenbeck."""
        # OU process: dX = θ(μ - X)dt + σdW
        # Expected value: E[X(t)] = X(0)e^(-θt) + μ(1 - e^(-θt))
        
        time_horizon = 20 / 252  # 20 trading days
        theta = self.mean_reversion_speed
        
        expected_vix = (
            current_vix * np.exp(-theta * time_horizon) +
            self.vix_mean * (1 - np.exp(-theta * time_horizon))
        )
        
        return expected_vix
    
    def _calculate_reversion_probability(self, current_vix: float) -> float:
        """Calculate probability of mean reversion."""
        zscore = abs((current_vix - self.vix_mean) / self.vix_std)
        
        # Higher z-score = higher probability of reversion
        if zscore > 3:
            return 0.95
        elif zscore > 2:
            return 0.85
        elif zscore > 1:
            return 0.70
        else:
            return 0.50
    
    def _calculate_vix_spy_correlation(self, window: int) -> float:
        """Calculate rolling VIX-SPY correlation."""
        if len(self.vix_history) < window or len(self.spy_prices) < window:
            return -0.75  # Default negative correlation
        
        # Get returns
        vix_values = [v.vix_spot for v in list(self.vix_history)[-window:]]
        spy_values = list(self.spy_prices)[-window:]
        
        vix_returns = pd.Series(vix_values).pct_change().dropna()
        spy_returns = pd.Series(spy_values).pct_change().dropna()
        
        if len(vix_returns) < 2:
            return -0.75
        
        return vix_returns.corr(spy_returns)
    
    def _generate_mean_reversion_signals(self) -> List[Dict[str, Any]]:
        """Generate mean reversion trading signals."""
        signals = []
        
        if not self.regime_analysis:
            return signals
        
        zscore = self.regime_analysis.zscore
        
        # Long volatility signal (VIX too low)
        if zscore < -ZSCORE_THRESHOLD:
            signals.append({
                'type': VIXSignal.MEAN_REVERSION_LONG,
                'direction': 'LONG_VOL',
                'confidence': min(abs(zscore) / 3, 1.0),
                'entry_vix': self.current_vix.vix_spot,
                'target_vix': self.regime_analysis.expected_reversion,
                'suggested_trades': [
                    'Buy VIX calls',
                    'Buy SPY puts',
                    'Long volatility ETFs'
                ],
                'timeframe': '5-20 days',
                'risk': 'Time decay if VIX stays low'
            })
        
        # Short volatility signal (VIX too high)
        elif zscore > ZSCORE_THRESHOLD:
            signals.append({
                'type': VIXSignal.MEAN_REVERSION_SHORT,
                'direction': 'SHORT_VOL',
                'confidence': min(zscore / 3, 1.0),
                'entry_vix': self.current_vix.vix_spot,
                'target_vix': self.regime_analysis.expected_reversion,
                'suggested_trades': [
                    'Sell VIX calls',
                    'Sell SPY puts',
                    'Short volatility ETFs'
                ],
                'timeframe': '5-20 days',
                'risk': 'Volatility can spike higher'
            })
        
        return signals
    
    def _generate_term_structure_signals(self) -> List[Dict[str, Any]]:
        """Generate term structure based signals."""
        signals = []
        
        if not self.term_structure:
            return signals
        
        # Steep contango - sell volatility
        if self.term_structure.shape == TermStructureShape.STEEP_CONTANGO:
            signals.append({
                'type': VIXSignal.CONTANGO_ROLL,
                'direction': 'SHORT_VOL',
                'confidence': 0.8,
                'structure': 'Steep Contango',
                'daily_roll': f"{self.term_structure.daily_roll:.3f}",
                'suggested_trades': [
                    'Short VXX/UVXY',
                    'VIX call spreads',
                    'SPY put spreads (sell)'
                ],
                'timeframe': 'Daily roll harvest',
                'risk': 'Volatility spike risk'
            })
        
        # Backwardation - volatility event likely
        elif self.term_structure.shape in [TermStructureShape.BACKWARDATION, 
                                          TermStructureShape.STEEP_BACKWARDATION]:
            signals.append({
                'type': VIXSignal.TERM_STRUCTURE_TRADE,
                'direction': 'HEDGE',
                'confidence': 0.9,
                'structure': 'Backwardation',
                'message': 'Market stress - hedging recommended',
                'suggested_trades': [
                    'Buy portfolio protection',
                    'Reduce risk exposure',
                    'Long volatility positions'
                ],
                'timeframe': 'Immediate',
                'risk': 'Whipsaw if stress resolves quickly'
            })
        
        return signals
    
    def _check_vix_alerts(self, current: VIXData, prev_vix: float) -> None:
        """Check for VIX-based alerts."""
        # Intraday spike detection
        intraday_change = abs(current.vix_spot - prev_vix) / prev_vix
        
        if intraday_change > SPIKE_THRESHOLD:
            event = Event(
                type=EventType.MARKET_ALERT,
                data={
                    'alert_type': 'VIX_SPIKE',
                    'current_vix': current.vix_spot,
                    'previous_vix': prev_vix,
                    'change_pct': intraday_change * 100,
                    'message': f'VIX spike detected: {intraday_change*100:.1f}% move',
                    'action': 'Review positions and hedges'
                }
            )
            self.event_manager.emit(event)
        
        # Regime change detection
        if self.regime_analysis:
            current_regime = self._classify_vix_regime(current.vix_spot)
            if self.regime_history and self.regime_history[-1][1] != current_regime:
                event = Event(
                    type=EventType.ANALYTICS,
                    data={
                        'type': 'VIX_REGIME_CHANGE',
                        'old_regime': self.regime_history[-1][1].value,
                        'new_regime': current_regime.value,
                        'vix_level': current.vix_spot,
                        'implications': self._get_regime_implications(current_regime)
                    }
                )
                self.event_manager.emit(event)
    
    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================
    
    def _initialize_historical_data(self) -> None:
        """Initialize historical VIX statistics."""
        try:
            # Fetch historical VIX data
            historical_data = self.ib_client.get_historical_data(
                contract=self.ib_client.create_index_contract('VIX'),
                duration='1 Y',
                bar_size='1 day'
            )
            
            if historical_data and not historical_data.empty:
                # Calculate statistics
                vix_values = historical_data['close'].values
                self.vix_mean = np.mean(vix_values)
                self.vix_std = np.std(vix_values)
                
                self.logger.info(f"VIX statistics initialized: mean={self.vix_mean:.2f}, std={self.vix_std:.2f}")
            
        except Exception as e:
            self.logger.warning(f"Could not initialize historical data: {e}")
            # Use defaults
            self.vix_mean = VIX_MEAN
            self.vix_std = 8.0
    
    def _calculate_percentile(self, value: float, lookback_days: int) -> float:
        """Calculate historical percentile rank."""
        if len(self.vix_history) < lookback_days:
            return 50.0
        
        historical_values = [v.vix_spot for v in list(self.vix_history)[-lookback_days*78:]]
        return stats.percentileofscore(historical_values, value)
    
    def _calculate_regime_duration(self, current_regime: VIXRegime) -> int:
        """Calculate days in current regime."""
        if not self.regime_history:
            return 0
        
        # Find last regime change
        for i in range(len(self.regime_history) - 1, -1, -1):
            if self.regime_history[i][1] != current_regime:
                regime_start = self.regime_history[i][0]
                return (datetime.now() - regime_start).days
        
        # If no change found, return total history length
        return (datetime.now() - self.regime_history[0][0]).days
    
    def _calculate_regime_transitions(self, current_regime: VIXRegime) -> Dict[VIXRegime, float]:
        """Calculate regime transition probabilities."""
        # Simplified transition matrix based on historical patterns
        transitions = {regime: 0.0 for regime in VIXRegime}
        
        # Define typical transitions
        if current_regime == VIXRegime.LOW_VOL:
            transitions[VIXRegime.NORMAL] = 0.7
            transitions[VIXRegime.LOW_VOL] = 0.2
            transitions[VIXRegime.ELEVATED] = 0.1
            
        elif current_regime == VIXRegime.NORMAL:
            transitions[VIXRegime.NORMAL] = 0.5
            transitions[VIXRegime.LOW_VOL] = 0.2
            transitions[VIXRegime.ELEVATED] = 0.3
            
        elif current_regime == VIXRegime.ELEVATED:
            transitions[VIXRegime.NORMAL] = 0.4
            transitions[VIXRegime.HIGH_VOL] = 0.3
            transitions[VIXRegime.ELEVATED] = 0.3
            
        elif current_regime == VIXRegime.HIGH_VOL:
            transitions[VIXRegime.ELEVATED] = 0.4
            transitions[VIXRegime.STRESS] = 0.2
            transitions[VIXRegime.NORMAL] = 0.2
            transitions[VIXRegime.HIGH_VOL] = 0.2
            
        elif current_regime == VIXRegime.STRESS:
            transitions[VIXRegime.HIGH_VOL] = 0.5
            transitions[VIXRegime.PANIC] = 0.2
            transitions[VIXRegime.STRESS] = 0.3
            
        else:  # PANIC
            transitions[VIXRegime.STRESS] = 0.6
            transitions[VIXRegime.HIGH_VOL] = 0.3
            transitions[VIXRegime.PANIC] = 0.1
        
        return transitions
    
    def _get_regime_implications(self, regime: VIXRegime) -> str:
        """Get trading implications for regime."""
        implications = {
            VIXRegime.LOW_VOL: "Complacency risk - consider cheap protection",
            VIXRegime.NORMAL: "Normal market conditions - standard strategies",
            VIXRegime.ELEVATED: "Increased caution - reduce position sizes",
            VIXRegime.HIGH_VOL: "Risk-off environment - defensive positioning",
            VIXRegime.STRESS: "Market stress - prioritize capital preservation",
            VIXRegime.PANIC: "Extreme conditions - wait for stabilization"
        }
        return implications.get(regime, "Monitor closely")
    
    def _parse_futures_expiry(self, symbol: str) -> date:
        """Parse expiry date from futures symbol."""
        # VX{month}{year} format
        month_code = symbol[2]
        year_code = symbol[3]
        
        month = VIX_FUTURES_MONTHS.index(month_code) + 1
        year = 2020 + int(year_code)
        
        # VIX futures expire on Wednesday, 30 days before SPX expiry
        # Simplified - would need actual calendar in production
        return date(year, month, 15)
    
    def _calculate_daily_roll(self, front: VIXFuture, second: VIXFuture) -> float:
        """Calculate daily roll between futures."""
        if not front or not second:
            return 0.0
        
        # Daily theta from contango/backwardation
        days_between = (second.expiry - front.expiry).days
        if days_between == 0:
            return 0.0
        
        return (second.price - front.price) / days_between
    
    def _calculate_roll_yields(self) -> None:
        """Calculate roll yields for all futures."""
        sorted_futures = sorted(self.vix_futures.values(), key=lambda x: x.expiry)
        
        for i in range(1, len(sorted_futures)):
            curr = sorted_futures[i]
            prev = sorted_futures[i-1]
            
            days_diff = (curr.expiry - prev.expiry).days
            if days_diff > 0:
                curr.roll_yield = ((curr.price / prev.price) - 1) * 365 / days_diff
    
    def _determine_trend(self, values: List[float]) -> str:
        """Determine trend direction."""
        if len(values) < 2:
            return 'flat'
        
        # Simple linear regression
        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)
        
        if slope > 0.001:
            return 'up'
        elif slope < -0.001:
            return 'down'
        else:
            return 'flat'
    
    def _create_no_divergence(self) -> VIXDivergence:
        """Create default no-divergence object."""
        return VIXDivergence(
            timestamp=datetime.now(),
            vix_spy_correlation=-0.75,
            historical_correlation=-0.75,
            divergence_score=0,
            vix_trend='flat',
            spy_trend='flat',
            is_divergent=False,
            divergence_type='none',
            confidence=0,
            suggested_action='hold'
        )
    
    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    
    def start_monitoring(self) -> None:
        """Start VIX monitoring."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="VIX-Monitor",
            daemon=True
        )
        self._monitor_thread.start()
        self.logger.info("VIX monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop VIX monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        self.logger.info("VIX monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        last_vix_update = time.time()
        last_structure_update = time.time()
        last_regime_check = time.time()
        
        while self._running:
            try:
                current_time = time.time()
                
                # Update VIX data
                if current_time - last_vix_update >= VIX_UPDATE_INTERVAL:
                    self.update_vix_data()
                    last_vix_update = current_time
                
                # Update term structure
                if current_time - last_structure_update >= TERM_STRUCTURE_UPDATE:
                    self.analyze_term_structure()
                    last_structure_update = current_time
                
                # Check regime
                if current_time - last_regime_check >= REGIME_CHECK_INTERVAL:
                    self.analyze_regime()
                    last_regime_check = current_time
                
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    # ==========================================================================
    # PUBLIC METHODS - VISUALIZATION
    # ==========================================================================
    
    def plot_vix_analysis(self, save_path: Optional[str] = None) -> None:
        """Create comprehensive VIX analysis plot."""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        
        # Plot 1: VIX time series with regimes
        if self.vix_history:
            times = [v.timestamp for v in self.vix_history]
            values = [v.vix_spot for v in self.vix_history]
            
            ax1.plot(times, values, 'b-', linewidth=2)
            ax1.axhline(self.vix_mean, color='red', linestyle='--', alpha=0.5, label='Mean')
            ax1.fill_between(times, self.vix_mean - self.vix_std, self.vix_mean + self.vix_std,
                           alpha=0.2, color='gray', label='±1 STD')
            
            # Mark regime zones
            ax1.axhspan(0, VIX_LOW, alpha=0.1, color='green', label='Low Vol')
            ax1.axhspan(VIX_HIGH, VIX_EXTREME, alpha=0.1, color='red', label='High Vol')
            
            ax1.set_title('VIX Level and Regimes')
            ax1.set_ylabel('VIX')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
        
        # Plot 2: Term Structure
        if self.term_structure and self.term_structure.futures:
            expiries = [f.days_to_expiry for f in self.term_structure.futures]
            prices = [f.price for f in self.term_structure.futures]
            
            ax2.plot(expiries, prices, 'go-', linewidth=2, markersize=8, label='Futures')
            ax2.axhline(self.current_vix.vix_spot, color='blue', linestyle='--', label='Spot VIX')
            
            ax2.set_title(f'VIX Term Structure ({self.term_structure.shape.value})')
            ax2.set_xlabel('Days to Expiry')
            ax2.set_ylabel('VIX Level')
            ax2.legend()
            ax2.grid(True, alpha=0.3)
        
        # Plot 3: VIX Distribution
        if len(self.vix_history) > 100:
            recent_values = [v.vix_spot for v in list(self.vix_history)[-1000:]]
            ax3.hist(recent_values, bins=30, alpha=0.7, color='blue', edgecolor='black')
            ax3.axvline(self.current_vix.vix_spot, color='red', linewidth=2, label='Current')
            ax3.axvline(self.vix_mean, color='green', linestyle='--', label='Mean')
            
            ax3.set_title('VIX Distribution (Recent)')
            ax3.set_xlabel('VIX Level')
            ax3.set_ylabel('Frequency')
            ax3.legend()
        
        # Plot 4: Regime Transition Matrix
        if self.regime_analysis:
            regimes = list(VIXRegime)
            transitions = self.regime_analysis.regime_transitions
            
            # Create matrix
            matrix = np.zeros((len(regimes), len(regimes)))
            current_idx = regimes.index(self.regime_analysis.current_regime)
            
            for i, regime in enumerate(regimes):
                matrix[current_idx, i] = transitions.get(regime, 0)
            
            im = ax4.imshow(matrix, cmap='YlOrRd', aspect='auto')
            ax4.set_xticks(range(len(regimes)))
            ax4.set_yticks(range(len(regimes)))
            ax4.set_xticklabels([r.value.split('_')[0] for r in regimes], rotation=45)
            ax4.set_yticklabels([r.value.split('_')[0] for r in regimes])
            ax4.set_title('Regime Transition Probabilities')
            
            # Add probability text
            for i in range(len(regimes)):
                for j in range(len(regimes)):
                    if matrix[i, j] > 0:
                        ax4.text(j, i, f'{matrix[i, j]:.2f}', ha='center', va='center')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
    
    def get_summary_dashboard(self) -> Dict[str, Any]:
        """Get VIX analysis summary for dashboard."""
        if not all([self.current_vix, self.regime_analysis, self.term_structure]):
            return {'status': 'insufficient_data'}
        
        return {
            'vix_spot': self.current_vix.vix_spot,
            'vix_change': f"{self.current_vix.vix_change:+.2f}",
            'vix_change_pct': f"{self.current_vix.vix_change_pct:+.1f}%",
            'regime': self.regime_analysis.current_regime.value,
            'regime_duration': f"{self.regime_analysis.regime_duration}d",
            'percentile_1y': f"{self.regime_analysis.percentile_1y:.0f}%",
            'zscore': f"{self.regime_analysis.zscore:+.2f}",
            'term_structure': self.term_structure.shape.value,
            'front_month_basis': f"{self.term_structure.front_month_basis:+.2f}",
            'daily_roll': f"${self.term_structure.daily_roll*1000:+.0f}/1000 vega",
            'mean_reversion_target': f"{self.regime_analysis.expected_reversion:.1f}",
            'reversion_probability': f"{self.regime_analysis.reversion_probability:.0%}",
            'vix_vix3m_ratio': f"{self.current_vix.vix_vix3m_ratio:.2f}" if self.current_vix.vix_vix3m_ratio else "N/A"
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_vix_analyzer(ib_client: Optional[IBClient] = None) -> VIXAnalyzer:
    """
    Factory function to create VIX analyzer.
    
    Args:
        ib_client: IB client instance
        
    Returns:
        Configured VIXAnalyzer instance
    """
    return VIXAnalyzer(ib_client)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Module-level initialization code
pass

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER C10 - VIX Analyzer Test")
    print("=" * 80)
    
    # Create analyzer
    vix_analyzer = VIXAnalyzer()
    
    # Update VIX data
    print("\n1. Updating VIX Data...")
    vix_data = vix_analyzer.update_vix_data()
    print(f"VIX Spot: {vix_data.vix_spot:.2f}")
    print(f"Change: {vix_data.vix_change:+.2f} ({vix_data.vix_change_pct:+.1f}%)")
    
    # Analyze regime
    print("\n2. Analyzing VIX Regime...")
    regime = vix_analyzer.analyze_regime()
    print(f"Current Regime: {regime.current_regime.value}")
    print(f"Z-Score: {regime.zscore:+.2f}")
    print(f"Mean Reversion Target: {regime.expected_reversion:.2f}")
    print(f"Reversion Probability: {regime.reversion_probability:.0%}")
    
    # Analyze term structure
    print("\n3. Analyzing Term Structure...")
    structure = vix_analyzer.analyze_term_structure()
    print(f"Shape: {structure.shape.value}")
    print(f"Front Month Basis: {structure.front_month_basis:+.2f}")
    print(f"Daily Roll: ${structure.daily_roll*1000:+.2f} per 1000 vega")
    
    # Generate signals
    print("\n4. Generating VIX Signals...")
    signals = vix_analyzer.generate_vix_signals()
    for signal in signals[:3]:
        print(f"\nSignal: {signal['type'].value}")
        print(f"Direction: {signal['direction']}")
        print(f"Confidence: {signal['confidence']:.0%}")
        if 'suggested_trades' in signal:
            print(f"Trades: {', '.join(signal['suggested_trades'][:2])}")
    
    # Get summary
    print("\n5. Dashboard Summary:")
    summary = vix_analyzer.get_summary_dashboard()
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    print("\n" + "=" * 80)
    print("VIX Analyzer test completed successfully!")
