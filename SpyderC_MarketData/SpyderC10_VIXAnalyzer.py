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
Date Created: 2025-07-01
Last Updated: 2025-07-01 Time: 15:00:00
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
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderB_Broker.SpyderB01_SpyderClient import IBClient
from SpyderC_MarketData.SpyderC01_DataFeed import DataFeed
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# VIX Futures months and symbols
VIX_FUTURES_MONTHS = [
    'F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'
]

# VIX regime thresholds
VIX_LOW_THRESHOLD = 15.0
VIX_MEDIUM_THRESHOLD = 20.0
VIX_HIGH_THRESHOLD = 30.0
VIX_EXTREME_THRESHOLD = 40.0

# Term structure analysis parameters
TERM_STRUCTURE_MONTHS = 6
CONTANGO_THRESHOLD = 0.02  # 2% slope
BACKWARDATION_THRESHOLD = -0.02  # -2% slope

# Mean reversion parameters
MEAN_REVERSION_LOOKBACK = 252  # 1 year of trading days
MEAN_REVERSION_ZSCORE_THRESHOLD = 2.0
PERCENTILE_EXTREME_THRESHOLD = 95

# VIX options parameters
VIX_OPTIONS_STRIKES_RANGE = 20  # Number of strikes above/below ATM
MIN_VIX_OPTION_VOLUME = 10
MIN_VIX_OPTION_OI = 50

# Update frequencies
VIX_UPDATE_FREQUENCY = 5  # seconds
TERM_STRUCTURE_UPDATE_FREQUENCY = 30  # seconds
HISTORICAL_DATA_DAYS = 504  # 2 years

# ==============================================================================
# ENUMS
# ==============================================================================
class VIXRegime(Enum):
    """VIX volatility regimes"""
    ULTRA_LOW = "ultra_low"        # < 12
    LOW = "low"                    # 12-15
    NORMAL = "normal"              # 15-20
    ELEVATED = "elevated"          # 20-30
    HIGH = "high"                  # 30-40
    EXTREME = "extreme"            # > 40

class TermStructureShape(Enum):
    """VIX term structure shapes"""
    STEEP_CONTANGO = "steep_contango"
    CONTANGO = "contango"
    FLAT = "flat"
    BACKWARDATION = "backwardation"
    STEEP_BACKWARDATION = "steep_backwardation"

class VIXSignal(Enum):
    """VIX-based trading signals"""
    BULLISH_MEAN_REVERSION = "bullish_mean_reversion"
    BEARISH_MEAN_REVERSION = "bearish_mean_reversion"
    VOLATILITY_EXPANSION = "volatility_expansion"
    VOLATILITY_CONTRACTION = "volatility_contraction"
    REGIME_SHIFT_UP = "regime_shift_up"
    REGIME_SHIFT_DOWN = "regime_shift_down"
    NEUTRAL = "neutral"

class VIXEventType(Enum):
    """VIX event types"""
    SPIKE = "spike"
    CRASH = "crash"
    REGIME_CHANGE = "regime_change"
    STRUCTURE_INVERSION = "structure_inversion"
    EXTREME_READING = "extreme_reading"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VIXData:
    """Current VIX data point"""
    timestamp: datetime
    vix_spot: float
    vix_change: float
    vix_change_pct: float
    vix9d: Optional[float] = None
    vix3m: Optional[float] = None
    vix6m: Optional[float] = None
    vix_vix3m_ratio: Optional[float] = None
    volume: Optional[int] = None
    open_interest: Optional[int] = None

@dataclass
class VIXFuturesData:
    """VIX futures data"""
    contract_month: str
    days_to_expiry: int
    price: float
    volume: int
    open_interest: int
    bid: float
    ask: float
    spread: float
    implied_volatility: Optional[float] = None

@dataclass
class VIXTermStructure:
    """VIX term structure analysis"""
    timestamp: datetime
    futures_curve: List[VIXFuturesData]
    shape: TermStructureShape
    slope: float
    curvature: float
    front_month_basis: float
    second_month_basis: float
    daily_roll: float
    term_structure_percentile: float

@dataclass
class VIXRegimeAnalysis:
    """VIX regime analysis"""
    timestamp: datetime
    current_regime: VIXRegime
    regime_duration: int  # days in current regime
    previous_regime: VIXRegime
    regime_transition_probability: Dict[VIXRegime, float]
    percentile_1y: float
    percentile_3m: float
    zscore: float
    expected_reversion: float
    reversion_probability: float
    regime_stability: float

@dataclass
class VIXOptionsFlow:
    """VIX options flow analysis"""
    timestamp: datetime
    call_volume: int
    put_volume: int
    call_put_ratio: float
    net_premium: float
    max_pain: float
    gamma_exposure: float
    unusual_activity: List[Dict[str, Any]]

@dataclass
class VIXEvent:
    """VIX event detection"""
    timestamp: datetime
    event_type: VIXEventType
    magnitude: float
    duration: timedelta
    description: str
    impact_score: float
    related_events: List[str]

@dataclass
class VIXForecast:
    """VIX forecast data"""
    timestamp: datetime
    forecast_horizon: int  # days
    expected_vix: float
    confidence_interval: Tuple[float, float]
    probability_distribution: Dict[float, float]
    regime_probabilities: Dict[VIXRegime, float]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class VIXAnalyzer:
    """
    Advanced VIX analysis system for volatility regime detection,
    term structure analysis, and mean reversion signals.
    """
    
    def __init__(self, ib_client: Optional[IBClient] = None, config: Optional[Dict] = None):
        """
        Initialize VIX analyzer.
        
        Args:
            ib_client: Interactive Brokers client for live data
            config: Configuration dictionary
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        
        # Configuration
        self.config = config or {}
        self.ib_client = ib_client
        
        # Data storage
        self.current_vix: Optional[VIXData] = None
        self.vix_history: deque = deque(maxlen=HISTORICAL_DATA_DAYS)
        self.futures_data: Dict[str, VIXFuturesData] = {}
        self.term_structure: Optional[VIXTermStructure] = None
        self.regime_analysis: Optional[VIXRegimeAnalysis] = None
        self.options_flow: Optional[VIXOptionsFlow] = None
        
        # Analysis components
        self.regime_detector = VIXRegimeDetector()
        self.term_structure_analyzer = TermStructureAnalyzer()
        self.event_detector = VIXEventDetector()
        self.forecaster = VIXForecaster()
        
        # State tracking
        self.is_running = False
        self.last_update = None
        self.update_thread = None
        
        # Initialize
        self._initialize_historical_data()
        
        self.logger.info("VIX Analyzer initialized successfully")

    # ==========================================================================
    # PUBLIC METHODS - DATA UPDATES
    # ==========================================================================
    
    def start_real_time_analysis(self) -> None:
        """Start real-time VIX analysis"""
        if self.is_running:
            self.logger.warning("VIX analysis already running")
            return
            
        self.is_running = True
        self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.update_thread.start()
        
        self.logger.info("Started real-time VIX analysis")

    def stop_real_time_analysis(self) -> None:
        """Stop real-time VIX analysis"""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=5.0)
        
        self.logger.info("Stopped real-time VIX analysis")

    def update_vix_data(self) -> VIXData:
        """
        Update current VIX data.
        
        Returns:
            Current VIX data
        """
        try:
            if self.ib_client:
                vix_data = self._fetch_live_vix_data()
            else:
                vix_data = self._fetch_simulated_vix_data()
            
            self.current_vix = vix_data
            self.vix_history.append(vix_data)
            self.last_update = datetime.now()
            
            # Emit update event
            self.event_manager.emit_event(Event(
                type=EventType.DATA_UPDATE,
                source=self.__class__.__name__,
                data={'vix_data': vix_data}
            ))
            
            return vix_data
            
        except Exception as e:
            self.error_handler.handle_error(e, "update_vix_data")
            raise

    def update_futures_data(self) -> Dict[str, VIXFuturesData]:
        """
        Update VIX futures data.
        
        Returns:
            Dictionary of VIX futures data by contract month
        """
        try:
            if self.ib_client:
                futures_data = self._fetch_live_futures_data()
            else:
                futures_data = self._fetch_simulated_futures_data()
            
            self.futures_data = futures_data
            
            # Update term structure analysis
            self.term_structure = self.term_structure_analyzer.analyze(
                list(futures_data.values())
            )
            
            return futures_data
            
        except Exception as e:
            self.error_handler.handle_error(e, "update_futures_data")
            raise

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================
    
    def analyze_regime(self) -> VIXRegimeAnalysis:
        """
        Analyze current VIX regime.
        
        Returns:
            VIX regime analysis
        """
        if not self.current_vix or len(self.vix_history) < 30:
            raise ValueError("Insufficient VIX data for regime analysis")
        
        try:
            regime_analysis = self.regime_detector.analyze(
                self.current_vix,
                list(self.vix_history)
            )
            
            self.regime_analysis = regime_analysis
            
            # Check for regime changes
            if (self.regime_analysis and 
                regime_analysis.current_regime != self.regime_analysis.current_regime):
                
                self._emit_regime_change_event(regime_analysis)
            
            return regime_analysis
            
        except Exception as e:
            self.error_handler.handle_error(e, "analyze_regime")
            raise

    def analyze_term_structure(self) -> VIXTermStructure:
        """
        Analyze VIX term structure.
        
        Returns:
            Term structure analysis
        """
        if not self.futures_data:
            self.update_futures_data()
        
        try:
            term_structure = self.term_structure_analyzer.analyze(
                list(self.futures_data.values())
            )
            
            self.term_structure = term_structure
            
            # Check for structure inversions
            if term_structure.shape in [TermStructureShape.BACKWARDATION, 
                                      TermStructureShape.STEEP_BACKWARDATION]:
                self._emit_structure_inversion_event(term_structure)
            
            return term_structure
            
        except Exception as e:
            self.error_handler.handle_error(e, "analyze_term_structure")
            raise

    def detect_events(self) -> List[VIXEvent]:
        """
        Detect VIX events (spikes, crashes, etc.).
        
        Returns:
            List of detected VIX events
        """
        if len(self.vix_history) < 20:
            return []
        
        try:
            events = self.event_detector.detect_events(
                self.current_vix,
                list(self.vix_history)
            )
            
            # Emit events
            for event in events:
                self._emit_vix_event(event)
            
            return events
            
        except Exception as e:
            self.error_handler.handle_error(e, "detect_events")
            return []

    def generate_signals(self) -> List[VIXSignal]:
        """
        Generate VIX-based trading signals.
        
        Returns:
            List of VIX signals
        """
        if not all([self.current_vix, self.regime_analysis, self.term_structure]):
            return [VIXSignal.NEUTRAL]
        
        try:
            signals = []
            
            # Mean reversion signals
            if self.regime_analysis.zscore > MEAN_REVERSION_ZSCORE_THRESHOLD:
                signals.append(VIXSignal.BEARISH_MEAN_REVERSION)
            elif self.regime_analysis.zscore < -MEAN_REVERSION_ZSCORE_THRESHOLD:
                signals.append(VIXSignal.BULLISH_MEAN_REVERSION)
            
            # Volatility expansion/contraction
            if (self.current_vix.vix_change_pct > 20 and 
                self.regime_analysis.current_regime in [VIXRegime.HIGH, VIXRegime.EXTREME]):
                signals.append(VIXSignal.VOLATILITY_EXPANSION)
            elif (self.current_vix.vix_change_pct < -15 and 
                  self.regime_analysis.current_regime == VIXRegime.LOW):
                signals.append(VIXSignal.VOLATILITY_CONTRACTION)
            
            # Regime shift signals
            regime_prob = max(self.regime_analysis.regime_transition_probability.values())
            if regime_prob > 0.7:
                target_regime = max(
                    self.regime_analysis.regime_transition_probability.items(),
                    key=lambda x: x[1]
                )[0]
                
                if target_regime.value > self.regime_analysis.current_regime.value:
                    signals.append(VIXSignal.REGIME_SHIFT_UP)
                else:
                    signals.append(VIXSignal.REGIME_SHIFT_DOWN)
            
            return signals if signals else [VIXSignal.NEUTRAL]
            
        except Exception as e:
            self.error_handler.handle_error(e, "generate_signals")
            return [VIXSignal.NEUTRAL]

    def forecast_vix(self, horizon_days: int = 5) -> VIXForecast:
        """
        Generate VIX forecast.
        
        Args:
            horizon_days: Forecast horizon in days
            
        Returns:
            VIX forecast
        """
        if len(self.vix_history) < 50:
            raise ValueError("Insufficient data for VIX forecasting")
        
        try:
            forecast = self.forecaster.generate_forecast(
                list(self.vix_history),
                horizon_days
            )
            
            return forecast
            
        except Exception as e:
            self.error_handler.handle_error(e, "forecast_vix")
            raise

    # ==========================================================================
    # PUBLIC METHODS - UTILITY
    # ==========================================================================
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive VIX analysis summary.
        
        Returns:
            Dictionary containing VIX analysis summary
        """
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

    # ==========================================================================
    # PRIVATE METHODS - DATA FETCHING
    # ==========================================================================
    
    def _fetch_live_vix_data(self) -> VIXData:
        """Fetch live VIX data from IB"""
        # Implementation for live data fetching
        # This would use the IB client to get real VIX data
        pass

    def _fetch_simulated_vix_data(self) -> VIXData:
        """Generate simulated VIX data for testing"""
        base_vix = 20.0
        if self.current_vix:
            base_vix = self.current_vix.vix_spot
        
        # Simple random walk with mean reversion
        change = np.random.normal(0, 0.5) - 0.1 * (base_vix - 20.0) / 20.0
        new_vix = max(5.0, base_vix + change)
        
        return VIXData(
            timestamp=datetime.now(),
            vix_spot=new_vix,
            vix_change=change,
            vix_change_pct=(change / base_vix) * 100,
            vix9d=new_vix * np.random.uniform(0.95, 1.05),
            vix3m=new_vix * np.random.uniform(1.0, 1.2),
            vix6m=new_vix * np.random.uniform(1.1, 1.3),
            vix_vix3m_ratio=new_vix / (new_vix * np.random.uniform(1.0, 1.2)),
            volume=np.random.randint(100000, 500000),
            open_interest=np.random.randint(1000000, 3000000)
        )

    def _fetch_live_futures_data(self) -> Dict[str, VIXFuturesData]:
        """Fetch live VIX futures data from IB"""
        # Implementation for live futures data
        pass

    def _fetch_simulated_futures_data(self) -> Dict[str, VIXFuturesData]:
        """Generate simulated VIX futures data"""
        futures_data = {}
        base_vix = self.current_vix.vix_spot if self.current_vix else 20.0
        
        for i, month in enumerate(VIX_FUTURES_MONTHS[:6]):
            days_to_expiry = 30 + i * 30
            # Futures typically in contango
            price = base_vix * (1 + 0.02 * i + np.random.uniform(-0.01, 0.01))
            
            futures_data[month] = VIXFuturesData(
                contract_month=month,
                days_to_expiry=days_to_expiry,
                price=price,
                volume=np.random.randint(1000, 10000),
                open_interest=np.random.randint(10000, 50000),
                bid=price - 0.05,
                ask=price + 0.05,
                spread=0.10
            )
        
        return futures_data

    # ==========================================================================
    # PRIVATE METHODS - HELPER FUNCTIONS
    # ==========================================================================
    
    def _initialize_historical_data(self) -> None:
        """Initialize historical VIX data"""
        # In a real implementation, this would load historical data
        # For now, generate some sample data
        for i in range(100):
            self.vix_history.append(self._fetch_simulated_vix_data())

    def _update_loop(self) -> None:
        """Main update loop for real-time analysis"""
        while self.is_running:
            try:
                # Update VIX data
                self.update_vix_data()
                
                # Update futures data every 30 seconds
                if (not self.last_update or 
                    (datetime.now() - self.last_update).seconds >= TERM_STRUCTURE_UPDATE_FREQUENCY):
                    self.update_futures_data()
                
                # Run analysis
                self.analyze_regime()
                self.analyze_term_structure()
                self.detect_events()
                
                time.sleep(VIX_UPDATE_FREQUENCY)
                
            except Exception as e:
                self.error_handler.handle_error(e, "_update_loop")
                time.sleep(10)  # Wait longer on error

    def _emit_regime_change_event(self, regime_analysis: VIXRegimeAnalysis) -> None:
        """Emit regime change event"""
        event_data = {
            'previous_regime': regime_analysis.previous_regime.value,
            'new_regime': regime_analysis.current_regime.value,
            'transition_probability': max(regime_analysis.regime_transition_probability.values())
        }
        
        self.event_manager.emit_event(Event(
            type=EventType.SIGNAL_GENERATED,
            source=self.__class__.__name__,
            data=event_data
        ))

    def _emit_structure_inversion_event(self, term_structure: VIXTermStructure) -> None:
        """Emit term structure inversion event"""
        event_data = {
            'structure_shape': term_structure.shape.value,
            'slope': term_structure.slope,
            'front_month_basis': term_structure.front_month_basis
        }
        
        self.event_manager.emit_event(Event(
            type=EventType.SIGNAL_GENERATED,
            source=self.__class__.__name__,
            data=event_data
        ))

    def _emit_vix_event(self, vix_event: VIXEvent) -> None:
        """Emit VIX event"""
        event_data = {
            'event_type': vix_event.event_type.value,
            'magnitude': vix_event.magnitude,
            'impact_score': vix_event.impact_score,
            'description': vix_event.description
        }
        
        self.event_manager.emit_event(Event(
            type=EventType.SIGNAL_GENERATED,
            source=self.__class__.__name__,
            data=event_data
        ))

# ==============================================================================
# HELPER CLASSES
# ==============================================================================
class VIXRegimeDetector:
    """VIX regime detection and classification"""
    
    def __init__(self):
        self.regime_history = deque(maxlen=1000)
        self.scaler = StandardScaler()
        self.kmeans = KMeans(n_clusters=6, random_state=42)
    
    def analyze(self, current_vix: VIXData, vix_history: List[VIXData]) -> VIXRegimeAnalysis:
        """Analyze VIX regime"""
        # Determine current regime
        current_regime = self._classify_regime(current_vix.vix_spot)
        
        # Calculate regime duration
        regime_duration = self._calculate_regime_duration(current_regime)
        
        # Calculate statistics
        vix_values = [v.vix_spot for v in vix_history[-252:]]  # 1 year
        percentile_1y = stats.percentileofscore(vix_values, current_vix.vix_spot)
        
        vix_values_3m = [v.vix_spot for v in vix_history[-63:]]  # 3 months
        percentile_3m = stats.percentileofscore(vix_values_3m, current_vix.vix_spot)
        
        mean_vix = np.mean(vix_values)
        std_vix = np.std(vix_values)
        zscore = (current_vix.vix_spot - mean_vix) / std_vix
        
        # Calculate mean reversion
        expected_reversion = self._calculate_mean_reversion_target(vix_values)
        reversion_probability = self._calculate_reversion_probability(
            current_vix.vix_spot, expected_reversion, std_vix
        )
        
        # Calculate regime transition probabilities
        transition_probs = self._calculate_transition_probabilities(
            current_regime, vix_history
        )
        
        return VIXRegimeAnalysis(
            timestamp=datetime.now(),
            current_regime=current_regime,
            regime_duration=regime_duration,
            previous_regime=self.regime_history[-1] if self.regime_history else current_regime,
            regime_transition_probability=transition_probs,
            percentile_1y=percentile_1y,
            percentile_3m=percentile_3m,
            zscore=zscore,
            expected_reversion=expected_reversion,
            reversion_probability=reversion_probability,
            regime_stability=self._calculate_regime_stability(vix_history)
        )
    
    def _classify_regime(self, vix_level: float) -> VIXRegime:
        """Classify VIX regime based on level"""
        if vix_level < 12:
            return VIXRegime.ULTRA_LOW
        elif vix_level < 15:
            return VIXRegime.LOW
        elif vix_level < 20:
            return VIXRegime.NORMAL
        elif vix_level < 30:
            return VIXRegime.ELEVATED
        elif vix_level < 40:
            return VIXRegime.HIGH
        else:
            return VIXRegime.EXTREME
    
    def _calculate_regime_duration(self, current_regime: VIXRegime) -> int:
        """Calculate how long current regime has persisted"""
        if not self.regime_history:
            return 1
        
        duration = 1
        for regime in reversed(self.regime_history):
            if regime == current_regime:
                duration += 1
            else:
                break
        
        return duration
    
    def _calculate_mean_reversion_target(self, vix_values: List[float]) -> float:
        """Calculate mean reversion target"""
        # Use exponentially weighted mean for target
        weights = np.exp(np.linspace(-1, 0, len(vix_values)))
        weights = weights / weights.sum()
        return np.average(vix_values, weights=weights)
    
    def _calculate_reversion_probability(self, current_vix: float, 
                                       target: float, std: float) -> float:
        """Calculate probability of mean reversion"""
        z = abs(current_vix - target) / std
        # Higher z-score means higher reversion probability
        return min(0.95, 1 / (1 + np.exp(-z + 2)))
    
    def _calculate_transition_probabilities(self, current_regime: VIXRegime,
                                          vix_history: List[VIXData]) -> Dict[VIXRegime, float]:
        """Calculate regime transition probabilities"""
        # Simplified transition model
        transitions = {regime: 0.1 for regime in VIXRegime}
        transitions[current_regime] = 0.4  # Persistence
        
        # Adjust based on recent volatility
        recent_volatility = np.std([v.vix_spot for v in vix_history[-20:]])
        if recent_volatility > 3:
            # High volatility increases transition probability
            if current_regime in [VIXRegime.LOW, VIXRegime.NORMAL]:
                transitions[VIXRegime.ELEVATED] += 0.2
                transitions[VIXRegime.HIGH] += 0.1
            elif current_regime == VIXRegime.ELEVATED:
                transitions[VIXRegime.HIGH] += 0.2
                transitions[VIXRegime.EXTREME] += 0.1
        
        # Normalize probabilities
        total = sum(transitions.values())
        return {k: v/total for k, v in transitions.items()}
    
    def _calculate_regime_stability(self, vix_history: List[VIXData]) -> float:
        """Calculate regime stability score"""
        if len(vix_history) < 20:
            return 0.5
        
        # Count regime changes in recent history
        regimes = [self._classify_regime(v.vix_spot) for v in vix_history[-20:]]
        changes = sum(1 for i in range(1, len(regimes)) if regimes[i] != regimes[i-1])
        
        # Higher stability = fewer changes
        return max(0.0, 1.0 - changes / 19.0)


class TermStructureAnalyzer:
    """VIX term structure analysis"""
    
    def analyze(self, futures_data: List[VIXFuturesData]) -> VIXTermStructure:
        """Analyze VIX term structure"""
        if len(futures_data) < 2:
            raise ValueError("Insufficient futures data for term structure analysis")
        
        # Sort by expiration
        sorted_futures = sorted(futures_data, key=lambda x: x.days_to_expiry)
        
        # Calculate slope and curvature
        prices = [f.price for f in sorted_futures]
        days = [f.days_to_expiry for f in sorted_futures]
        
        # Linear regression for slope
        slope, intercept, r_value, p_value, std_err = stats.linregress(days, prices)
        
        # Determine shape
        shape = self._determine_shape(slope, prices)
        
        # Calculate basis (futures premium over VIX spot)
        vix_spot = prices[0] * 0.98  # Approximate VIX spot
        front_month_basis = (sorted_futures[0].price - vix_spot) / vix_spot
        second_month_basis = (sorted_futures[1].price - vix_spot) / vix_spot if len(sorted_futures) > 1 else 0
        
        # Calculate daily roll yield
        if len(sorted_futures) >= 2:
            days_diff = sorted_futures[1].days_to_expiry - sorted_futures[0].days_to_expiry
            price_diff = sorted_futures[1].price - sorted_futures[0].price
            daily_roll = price_diff / days_diff if days_diff > 0 else 0
        else:
            daily_roll = 0
        
        # Calculate curvature (second derivative)
        if len(prices) >= 3:
            curvature = prices[2] - 2*prices[1] + prices[0]
        else:
            curvature = 0
        
        return VIXTermStructure(
            timestamp=datetime.now(),
            futures_curve=sorted_futures,
            shape=shape,
            slope=slope,
            curvature=curvature,
            front_month_basis=front_month_basis,
            second_month_basis=second_month_basis,
            daily_roll=daily_roll,
            term_structure_percentile=self._calculate_term_structure_percentile(slope)
        )
    
    def _determine_shape(self, slope: float, prices: List[float]) -> TermStructureShape:
        """Determine term structure shape"""
        if slope > 0.05:
            return TermStructureShape.STEEP_CONTANGO
        elif slope > 0.02:
            return TermStructureShape.CONTANGO
        elif slope > -0.02:
            return TermStructureShape.FLAT
        elif slope > -0.05:
            return TermStructureShape.BACKWARDATION
        else:
            return TermStructureShape.STEEP_BACKWARDATION
    
    def _calculate_term_structure_percentile(self, slope: float) -> float:
        """Calculate where current slope ranks historically"""
        # Historical slopes (this would come from database in real implementation)
        historical_slopes = np.random.normal(0.02, 0.03, 1000)  # Simulated
        return stats.percentileofscore(historical_slopes, slope)


class VIXEventDetector:
    """VIX event detection system"""
    
    def __init__(self):
        self.event_history = deque(maxlen=1000)
    
    def detect_events(self, current_vix: VIXData, vix_history: List[VIXData]) -> List[VIXEvent]:
        """Detect VIX events"""
        events = []
        
        if len(vix_history) < 20:
            return events
        
        # Spike detection
        spike_event = self._detect_spike(current_vix, vix_history)
        if spike_event:
            events.append(spike_event)
        
        # Crash detection
        crash_event = self._detect_crash(current_vix, vix_history)
        if crash_event:
            events.append(crash_event)
        
        # Extreme reading detection
        extreme_event = self._detect_extreme_reading(current_vix, vix_history)
        if extreme_event:
            events.append(extreme_event)
        
        return events
    
    def _detect_spike(self, current_vix: VIXData, vix_history: List[VIXData]) -> Optional[VIXEvent]:
        """Detect VIX spikes"""
        if current_vix.vix_change_pct > 25:  # 25% daily increase
            return VIXEvent(
                timestamp=current_vix.timestamp,
                event_type=VIXEventType.SPIKE,
                magnitude=current_vix.vix_change_pct,
                duration=timedelta(days=1),
                description=f"VIX spike of {current_vix.vix_change_pct:.1f}%",
                impact_score=min(1.0, current_vix.vix_change_pct / 50),
                related_events=[]
            )
        return None
    
    def _detect_crash(self, current_vix: VIXData, vix_history: List[VIXData]) -> Optional[VIXEvent]:
        """Detect VIX crashes"""
        if current_vix.vix_change_pct < -20:  # 20% daily decrease
            return VIXEvent(
                timestamp=current_vix.timestamp,
                event_type=VIXEventType.CRASH,
                magnitude=abs(current_vix.vix_change_pct),
                duration=timedelta(days=1),
                description=f"VIX crash of {current_vix.vix_change_pct:.1f}%",
                impact_score=min(1.0, abs(current_vix.vix_change_pct) / 30),
                related_events=[]
            )
        return None
    
    def _detect_extreme_reading(self, current_vix: VIXData, vix_history: List[VIXData]) -> Optional[VIXEvent]:
        """Detect extreme VIX readings"""
        vix_values = [v.vix_spot for v in vix_history[-252:]]  # 1 year
        percentile = stats.percentileofscore(vix_values, current_vix.vix_spot)
        
        if percentile > 95 or percentile < 5:
            return VIXEvent(
                timestamp=current_vix.timestamp,
                event_type=VIXEventType.EXTREME_READING,
                magnitude=percentile if percentile > 95 else 100 - percentile,
                duration=timedelta(days=1),
                description=f"Extreme VIX reading: {percentile:.0f}th percentile",
                impact_score=min(1.0, (percentile - 50) / 50 if percentile > 50 else (50 - percentile) / 50),
                related_events=[]
            )
        return None


class VIXForecaster:
    """VIX forecasting system"""
    
    def __init__(self):
        self.models = {}
        self.ensemble_weights = {}
    
    def generate_forecast(self, vix_history: List[VIXData], horizon_days: int) -> VIXForecast:
        """Generate VIX forecast"""
        vix_values = [v.vix_spot for v in vix_history]
        
        # Simple models for demonstration
        forecasts = {
            'mean_reversion': self._mean_reversion_forecast(vix_values, horizon_days),
            'random_walk': self._random_walk_forecast(vix_values, horizon_days),
            'ar_model': self._ar_forecast(vix_values, horizon_days)
        }
        
        # Ensemble forecast
        weights = {'mean_reversion': 0.4, 'random_walk': 0.3, 'ar_model': 0.3}
        expected_vix = sum(forecasts[model] * weight for model, weight in weights.items())
        
        # Confidence intervals (simplified)
        std_dev = np.std(vix_values[-30:])  # Recent volatility
        confidence_interval = (
            expected_vix - 1.96 * std_dev,
            expected_vix + 1.96 * std_dev
        )
        
        # Regime probabilities
        regime_probs = self._forecast_regime_probabilities(expected_vix)
        
        return VIXForecast(
            timestamp=datetime.now(),
            forecast_horizon=horizon_days,
            expected_vix=expected_vix,
            confidence_interval=confidence_interval,
            probability_distribution={},  # Would be populated in full implementation
            regime_probabilities=regime_probs
        )
    
    def _mean_reversion_forecast(self, vix_values: List[float], horizon: int) -> float:
        """Mean reversion forecast"""
        current_vix = vix_values[-1]
        long_term_mean = np.mean(vix_values[-252:])  # 1 year mean
        reversion_speed = 0.1  # Assumption
        
        # Exponential decay toward mean
        return long_term_mean + (current_vix - long_term_mean) * np.exp(-reversion_speed * horizon)
    
    def _random_walk_forecast(self, vix_values: List[float], horizon: int) -> float:
        """Random walk forecast"""
        return vix_values[-1]  # Random walk forecast is current value
    
    def _ar_forecast(self, vix_values: List[float], horizon: int) -> float:
        """Autoregressive forecast"""
        if len(vix_values) < 20:
            return vix_values[-1]
        
        # Simple AR(1) model
        y = np.array(vix_values[1:])
        x = np.array(vix_values[:-1])
        
        # Linear regression
        slope, intercept = np.polyfit(x, y, 1)
        
        # Forecast
        forecast = vix_values[-1]
        for _ in range(horizon):
            forecast = intercept + slope * forecast
        
        return forecast
    
    def _forecast_regime_probabilities(self, expected_vix: float) -> Dict[VIXRegime, float]:
        """Forecast regime probabilities"""
        # Simple classification based on expected VIX
        probs = {regime: 0.1 for regime in VIXRegime}
        
        if expected_vix < 12:
            probs[VIXRegime.ULTRA_LOW] = 0.6
        elif expected_vix < 15:
            probs[VIXRegime.LOW] = 0.6
        elif expected_vix < 20:
            probs[VIXRegime.NORMAL] = 0.6
        elif expected_vix < 30:
            probs[VIXRegime.ELEVATED] = 0.6
        elif expected_vix < 40:
            probs[VIXRegime.HIGH] = 0.6
        else:
            probs[VIXRegime.EXTREME] = 0.6
        
        # Normalize
        total = sum(probs.values())
        return {k: v/total for k, v in probs.items()}

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
    term_structure = vix_analyzer.analyze_term_structure()
    print(f"Shape: {term_structure.shape.value}")
    print(f"Slope: {term_structure.slope:.4f}")
    print(f"Front Month Basis: {term_structure.front_month_basis:.2%}")
    
    # Generate signals
    print("\n4. Generating Signals...")
    signals = vix_analyzer.generate_signals()
    print(f"Signals: {[s.value for s in signals]}")
    
    # Get summary
    print("\n5. VIX Summary...")
    summary = vix_analyzer.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print("\n✅ VIX Analyzer test completed successfully")