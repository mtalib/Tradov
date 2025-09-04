#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC04_MarketInternals.py
Group: C (Market Data)
Purpose: Market internals analysis (TICK, ADD, VOLD, TRIN, etc.)

Description:
    This module provides comprehensive market internals analysis including NYSE TICK,
    ADD (Advance/Decline), VOLD (Volume), TRIN (Arms Index), and other breadth
    indicators. It monitors market sentiment, breadth divergences, and generates
    trading signals based on market internal conditions.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-01-04
Last Updated: 2025-01-06 Time: 10:30:00
"""

import json
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import statistics
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Optional

import numpy as np
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from scipy import stats

from SpyderA_Core.SpyderA05_EventManager import Event, EventBus, EventType
# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Internal symbols to track
INTERNAL_SYMBOLS = {
    "TICK": "NYSE:TICK",  # NYSE Tick Index
    "TICKI": "NASDAQ:TICKI",  # Nasdaq Tick Index
    "ADD": "NYSE:ADD",  # NYSE Advance/Decline
    "VOLD": "NYSE:VOLD",  # NYSE Up/Down Volume
    "TRIN": "NYSE:TRIN",  # Arms Index (Trading Index)
    "VIX": "INDEX:VIX",  # Volatility Index
    "VIX9D": "INDEX:VIX9D",  # 9-day VIX
    "PCALL": "INDEX:PCALL",  # Put/Call Ratio (All)
    "PCSP": "INDEX:PCSP",  # Put/Call Ratio (SPX)
    "CPCE": "INDEX:CPCE",  # CBOE Equity Put/Call
    "SKEW": "INDEX:SKEW",  # CBOE Skew Index
    "SPXHILO": "NYSE:SPXHILO",  # S&P 500 New Highs/Lows
    "NYHL": "NYSE:NYHL",  # NYSE New Highs/Lows
    "NQHL": "NASDAQ:NQHL",  # Nasdaq New Highs/Lows
}

# Thresholds
TICK_EXTREME_HIGH = 1000
TICK_EXTREME_LOW = -1000
TICK_OVERBOUGHT = 600
TICK_OVERSOLD = -600

TRIN_BULLISH = 0.7
TRIN_BEARISH = 1.3

VIX_LOW = 12
VIX_NORMAL = 20
VIX_HIGH = 25
VIX_EXTREME = 30

# Update intervals (seconds)
UPDATE_INTERVAL = 1
ANALYSIS_INTERVAL = 5

# ==============================================================================
# ENUMS
# ==============================================================================


class MarketCondition(Enum):
    """Market condition based on internals"""

    EXTREMELY_BULLISH = "extremely_bullish"
    BULLISH = "bullish"
    MODERATELY_BULLISH = "moderately_bullish"
    NEUTRAL = "neutral"
    MODERATELY_BEARISH = "moderately_bearish"
    BEARISH = "bearish"
    EXTREMELY_BEARISH = "extremely_bearish"


class BreadthCondition(Enum):
    """Market breadth condition"""

    EXTREMELY_STRONG = "extremely_strong"
    STRONG = "strong"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    WEAK = "weak"
    EXTREMELY_WEAK = "extremely_weak"


class MarketPhase(Enum):
    """Market phase detection"""

    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class InternalData:
    """Data structure for market internal"""

    symbol: str
    value: float
    timestamp: datetime
    change: float = 0.0
    percent_change: float = 0.0


@dataclass
class MarketInternalsSnapshot:
    """Snapshot of all market internals"""

    timestamp: datetime
    tick: float
    ticki: float
    add: float
    vold: float
    trin: float
    vix: float
    vix9d: float
    pcall: float
    pcsp: float
    cpce: float
    skew: float
    spx_hilo: float
    ny_hilo: float
    nq_hilo: float


@dataclass
class InternalsAnalysis:
    """Analysis of market internals"""

    timestamp: datetime
    market_condition: MarketCondition
    breadth_condition: BreadthCondition
    market_phase: MarketPhase
    tick_extreme: bool
    breadth_divergence: bool
    volume_confirmation: bool
    signal_strength: float  # -1 to 1
    confidence: float  # 0 to 1
    indicators: Dict[str, float]
    warnings: List[str]


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class MarketInternalsAnalyzer:
    """
    Market internals analyzer for comprehensive market breadth analysis.

    This class monitors all major market internals including TICK, ADD, VOLD,
    TRIN, and various other breadth indicators to assess market sentiment
    and generate trading signals.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_bus: Event management system
        internals_data: Current internal values
        history: Historical data for analysis

    Example:
        >>> analyzer = MarketInternalsAnalyzer()
        >>> analyzer.initialize()
        >>> analysis = analyzer.get_current_analysis()
    """

    def __init__(self):
        """Initialize the market internals analyzer."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_bus = EventBus()

        # Data storage
        self.internals_data: Dict[str, InternalData] = {}
        self.history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.snapshots: deque = deque(maxlen=500)

        # Analysis state
        self.current_analysis: Optional[InternalsAnalysis] = None
        self.market_phase_history: deque = deque(maxlen=100)
        self.divergence_history: deque = deque(maxlen=50)

        # Control flags
        self.is_running = False
        self.update_thread: Optional[threading.Thread] = None
        self.analysis_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Callbacks
        self.analysis_callbacks: List[callable] = []

        self.logger.info("MarketInternalsAnalyzer initialized")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize market internals monitoring.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing market internals monitoring")

            # Initialize data structures
            for symbol_key, symbol in INTERNAL_SYMBOLS.items():
                self.internals_data[symbol_key] = InternalData(
                    symbol=symbol, value=0.0, timestamp=datetime.now()
                )

            # Subscribe to market data events
            self.event_bus.subscribe(EventType.MARKET_DATA, self._handle_market_data)

            # Start monitoring
            self.start()

            self.logger.info("Market internals monitoring initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False

    def start(self) -> None:
        """Start internals monitoring."""
        if not self.is_running:
            self.is_running = True

            # Start update thread
            self.update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self.update_thread.start()

            # Start analysis thread
            self.analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
            self.analysis_thread.start()

            self.logger.info("Market internals monitoring started")

    def stop(self) -> None:
        """Stop internals monitoring."""
        self.is_running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        if self.analysis_thread:
            self.analysis_thread.join(timeout=5)
        self.logger.info("Market internals monitoring stopped")

    def update_internal(self, symbol: str, value: float) -> None:
        """
        Update internal value.

        Args:
            symbol: Internal symbol (e.g., 'TICK')
            value: Current value
        """
        with self.lock:
            if symbol in self.internals_data:
                old_value = self.internals_data[symbol].value
                self.internals_data[symbol].value = value
                self.internals_data[symbol].timestamp = datetime.now()
                self.internals_data[symbol].change = value - old_value
                if old_value != 0:
                    self.internals_data[symbol].percent_change = (
                        (value - old_value) / abs(old_value) * 100
                    )

                # Add to history
                self.history[symbol].append({"timestamp": datetime.now(), "value": value})

    def get_current_analysis(self) -> Optional[InternalsAnalysis]:
        """
        Get current market internals analysis.

        Returns:
            Current analysis or None
        """
        return self.current_analysis

    def get_internal_value(self, symbol: str) -> Optional[float]:
        """
        Get current value for internal.

        Args:
            symbol: Internal symbol

        Returns:
            Current value or None
        """
        if symbol in self.internals_data:
            return self.internals_data[symbol].value
        return None

    def get_market_condition(self) -> MarketCondition:
        """
        Get current market condition.

        Returns:
            Current market condition
        """
        if self.current_analysis:
            return self.current_analysis.market_condition
        return MarketCondition.NEUTRAL

    def get_breadth_condition(self) -> BreadthCondition:
        """
        Get current breadth condition.

        Returns:
            Current breadth condition
        """
        if self.current_analysis:
            return self.current_analysis.breadth_condition
        return BreadthCondition.NEUTRAL

    def register_analysis_callback(self, callback: callable) -> None:
        """
        Register callback for analysis updates.

        Args:
            callback: Function to call with analysis
        """
        self.analysis_callbacks.append(callback)

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================
    def analyze_tick(self) -> Tuple[float, bool]:
        """
        Analyze NYSE TICK.

        Returns:
            Tuple of (signal_strength, is_extreme)
        """
        tick = self.get_internal_value("TICK") or 0

        # Calculate signal strength
        if tick >= TICK_EXTREME_HIGH:
            signal = 1.0
            extreme = True
        elif tick >= TICK_OVERBOUGHT:
            signal = 0.5 + 0.5 * (tick - TICK_OVERBOUGHT) / (TICK_EXTREME_HIGH - TICK_OVERBOUGHT)
            extreme = False
        elif tick <= TICK_EXTREME_LOW:
            signal = -1.0
            extreme = True
        elif tick <= TICK_OVERSOLD:
            signal = -0.5 - 0.5 * (tick - TICK_OVERSOLD) / (TICK_EXTREME_LOW - TICK_OVERSOLD)
            extreme = False
        else:
            signal = tick / TICK_OVERBOUGHT * 0.5
            extreme = False

        return signal, extreme

    def analyze_breadth(self) -> Tuple[BreadthCondition, float]:
        """
        Analyze market breadth.

        Returns:
            Tuple of (breadth_condition, breadth_score)
        """
        add = self.get_internal_value("ADD") or 0
        vold = self.get_internal_value("VOLD") or 0

        # Calculate breadth score
        add_score = np.clip(add / 1000, -1, 1)
        vold_score = np.clip(vold / 1e9, -1, 1)
        breadth_score = (add_score + vold_score) / 2

        # Determine condition
        if breadth_score >= 0.8:
            condition = BreadthCondition.EXTREMELY_STRONG
        elif breadth_score >= 0.6:
            condition = BreadthCondition.STRONG
        elif breadth_score >= 0.2:
            condition = BreadthCondition.POSITIVE
        elif breadth_score >= -0.2:
            condition = BreadthCondition.NEUTRAL
        elif breadth_score >= -0.6:
            condition = BreadthCondition.NEGATIVE
        elif breadth_score >= -0.8:
            condition = BreadthCondition.WEAK
        else:
            condition = BreadthCondition.EXTREMELY_WEAK

        return condition, breadth_score

    def analyze_trin(self) -> float:
        """
        Analyze TRIN (Arms Index).

        Returns:
            TRIN signal (-1 to 1)
        """
        trin = self.get_internal_value("TRIN") or 1.0

        if trin <= TRIN_BULLISH:
            # Bullish
            signal = 1.0 - (trin / TRIN_BULLISH)
        elif trin >= TRIN_BEARISH:
            # Bearish
            signal = -1.0 * min((trin - TRIN_BEARISH) / TRIN_BEARISH, 1.0)
        else:
            # Neutral
            signal = (TRIN_BULLISH - trin) / (TRIN_BEARISH - TRIN_BULLISH)

        return signal

    def detect_divergence(self) -> Tuple[bool, float]:
        """
        Detect price/breadth divergence.

        Returns:
            Tuple of (has_divergence, divergence_strength)
        """
        # Get recent history
        if len(self.snapshots) < 20:
            return False, 0.0

        recent_snapshots = list(self.snapshots)[-20:]

        # Calculate trends
        tick_values = [s.tick for s in recent_snapshots]
        add_values = [s.add for s in recent_snapshots]
        timestamps = list(range(len(recent_snapshots)))

        # Linear regression for trends
        tick_slope, _, tick_r, _, _ = stats.linregress(timestamps, tick_values)
        add_slope, _, add_r, _, _ = stats.linregress(timestamps, add_values)

        # Check for divergence
        divergence = False
        strength = 0.0

        if abs(tick_r) > 0.7 and abs(add_r) > 0.7:
            # Strong trends detected
            if (tick_slope > 0 and add_slope < 0) or (tick_slope < 0 and add_slope > 0):
                divergence = True
                strength = abs(tick_slope - add_slope) / max(abs(tick_slope), abs(add_slope))

        return divergence, strength

    def detect_market_phase(self) -> MarketPhase:
        """
        Detect current market phase.

        Returns:
            Current market phase
        """
        if len(self.snapshots) < 50:
            return MarketPhase.ACCUMULATION

        recent_snapshots = list(self.snapshots)[-50:]

        # Calculate indicators
        tick_avg = statistics.mean([s.tick for s in recent_snapshots])
        add_avg = statistics.mean([s.add for s in recent_snapshots])
        vold_avg = statistics.mean([s.vold for s in recent_snapshots])
        trin_avg = statistics.mean([s.trin for s in recent_snapshots])

        # Determine phase
        if tick_avg > 200 and add_avg > 500 and trin_avg < 1.0:
            phase = MarketPhase.MARKUP
        elif tick_avg < -200 and add_avg < -500 and trin_avg > 1.0:
            phase = MarketPhase.MARKDOWN
        elif abs(tick_avg) < 200 and trin_avg > 0.9 and trin_avg < 1.1:
            if vold_avg > 0:
                phase = MarketPhase.DISTRIBUTION
            else:
                phase = MarketPhase.ACCUMULATION
        else:
            phase = MarketPhase.ACCUMULATION

        return phase

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _update_loop(self) -> None:
        """Update loop for fetching internal data."""
        while self.is_running:
            try:
                # Create snapshot
                snapshot = self._create_snapshot()
                if snapshot:
                    with self.lock:
                        self.snapshots.append(snapshot)

                time.sleep(UPDATE_INTERVAL)

            except Exception as e:
                self.logger.error(f"Update loop error: {e}")
                time.sleep(UPDATE_INTERVAL)

    def _analysis_loop(self) -> None:
        """Analysis loop for processing internals."""
        while self.is_running:
            try:
                # Perform analysis
                analysis = self._perform_analysis()
                if analysis:
                    self.current_analysis = analysis

                    # Notify callbacks
                    for callback in self.analysis_callbacks:
                        try:
                            callback(analysis)
                        except Exception as e:
                            self.logger.error(f"Callback error: {e}")

                    # Publish event
                    event = Event(
                        type=EventType.MARKET_INTERNALS,
                        data={"analysis": analysis, "timestamp": datetime.now()},
                    )
                    self.event_bus.publish(event)

                time.sleep(ANALYSIS_INTERVAL)

            except Exception as e:
                self.logger.error(f"Analysis loop error: {e}")
                time.sleep(ANALYSIS_INTERVAL)

    def _create_snapshot(self) -> Optional[MarketInternalsSnapshot]:
        """Create snapshot of current internals."""
        try:
            with self.lock:
                snapshot = MarketInternalsSnapshot(
                    timestamp=datetime.now(),
                    tick=self.get_internal_value("TICK") or 0,
                    ticki=self.get_internal_value("TICKI") or 0,
                    add=self.get_internal_value("ADD") or 0,
                    vold=self.get_internal_value("VOLD") or 0,
                    trin=self.get_internal_value("TRIN") or 1.0,
                    vix=self.get_internal_value("VIX") or 20,
                    vix9d=self.get_internal_value("VIX9D") or 20,
                    pcall=self.get_internal_value("PCALL") or 1.0,
                    pcsp=self.get_internal_value("PCSP") or 1.0,
                    cpce=self.get_internal_value("CPCE") or 1.0,
                    skew=self.get_internal_value("SKEW") or 125,
                    spx_hilo=self.get_internal_value("SPXHILO") or 0,
                    ny_hilo=self.get_internal_value("NYHL") or 0,
                    nq_hilo=self.get_internal_value("NQHL") or 0,
                )
                return snapshot

        except Exception as e:
            self.logger.error(f"Error creating snapshot: {e}")
            return None

    def _perform_analysis(self) -> Optional[InternalsAnalysis]:
        """Perform comprehensive internals analysis."""
        try:
            # Get component analyses
            tick_signal, tick_extreme = self.analyze_tick()
            breadth_condition, breadth_score = self.analyze_breadth()
            trin_signal = self.analyze_trin()
            has_divergence, divergence_strength = self.detect_divergence()
            market_phase = self.detect_market_phase()

            # Calculate overall signal
            overall_signal = tick_signal * 0.4 + breadth_score * 0.3 + trin_signal * 0.3

            # Determine market condition
            if overall_signal >= 0.8:
                condition = MarketCondition.EXTREMELY_BULLISH
            elif overall_signal >= 0.5:
                condition = MarketCondition.BULLISH
            elif overall_signal >= 0.2:
                condition = MarketCondition.MODERATELY_BULLISH
            elif overall_signal >= -0.2:
                condition = MarketCondition.NEUTRAL
            elif overall_signal >= -0.5:
                condition = MarketCondition.MODERATELY_BEARISH
            elif overall_signal >= -0.8:
                condition = MarketCondition.BEARISH
            else:
                condition = MarketCondition.EXTREMELY_BEARISH

            # Check volume confirmation
            vold = self.get_internal_value("VOLD") or 0
            volume_confirmation = (overall_signal > 0 and vold > 0) or (
                overall_signal < 0 and vold < 0
            )

            # Calculate confidence
            confidence = min(
                abs(overall_signal), 1.0 - divergence_strength, 0.8 if volume_confirmation else 0.6
            )

            # Generate warnings
            warnings = []
            if tick_extreme:
                warnings.append("TICK at extreme levels")
            if has_divergence:
                warnings.append("Price/breadth divergence detected")
            if not volume_confirmation:
                warnings.append("Volume not confirming price action")

            # Create analysis
            analysis = InternalsAnalysis(
                timestamp=datetime.now(),
                market_condition=condition,
                breadth_condition=breadth_condition,
                market_phase=market_phase,
                tick_extreme=tick_extreme,
                breadth_divergence=has_divergence,
                volume_confirmation=volume_confirmation,
                signal_strength=overall_signal,
                confidence=confidence,
                indicators={
                    "tick_signal": tick_signal,
                    "breadth_score": breadth_score,
                    "trin_signal": trin_signal,
                    "divergence_strength": divergence_strength,
                },
                warnings=warnings,
            )

            return analysis

        except Exception as e:
            self.logger.error(f"Error performing analysis: {e}")
            return None

    def _handle_market_data(self, event: Event) -> None:
        """Handle market data events."""
        try:
            data = event.data
            symbol = data.get("symbol", "")

            # Check if it's an internal symbol
            for key, internal_symbol in INTERNAL_SYMBOLS.items():
                if symbol == internal_symbol:
                    value = data.get("last", 0)
                    self.update_internal(key, value)
                    break

        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")

    # ==========================================================================
    # ADVANCED ANALYSIS
    # ==========================================================================
    def get_sector_rotation_signals(self) -> Dict[str, float]:
        """
        Get sector rotation signals based on internals.

        Returns:
            Dict of sector to signal strength
        """
        signals = {}

        # Analyze different internal combinations
        risk_on_score = 0.0
        defensive_score = 0.0

        # Risk-on indicators
        if self.get_internal_value("VIX") < VIX_LOW:
            risk_on_score += 0.3
        if self.get_internal_value("CPCE") < 0.7:
            risk_on_score += 0.3
        if self.get_internal_value("ADD") > 1000:
            risk_on_score += 0.4

        # Defensive indicators
        if self.get_internal_value("VIX") > VIX_HIGH:
            defensive_score += 0.3
        if self.get_internal_value("CPCE") > 1.2:
            defensive_score += 0.3
        if self.get_internal_value("ADD") < -1000:
            defensive_score += 0.4

        # Map to sectors
        if risk_on_score > defensive_score:
            signals["XLK"] = risk_on_score  # Technology
            signals["XLF"] = risk_on_score * 0.8  # Financials
            signals["XLY"] = risk_on_score * 0.7  # Consumer Discretionary
            signals["XLU"] = -risk_on_score * 0.5  # Utilities (inverse)
            signals["XLP"] = -risk_on_score * 0.5  # Consumer Staples (inverse)
        else:
            signals["XLU"] = defensive_score  # Utilities
            signals["XLP"] = defensive_score  # Consumer Staples
            signals["XLV"] = defensive_score * 0.8  # Healthcare
            signals["XLK"] = -defensive_score * 0.5  # Technology (inverse)
            signals["XLF"] = -defensive_score * 0.5  # Financials (inverse)

        return signals

    def get_trading_signals(self) -> Dict[str, Any]:
        """
        Generate trading signals based on internals.

        Returns:
            Dict of trading signals and recommendations
        """
        if not self.current_analysis:
            return {}

        signals = {
            "timestamp": datetime.now(),
            "market_condition": self.current_analysis.market_condition.value,
            "signal_strength": self.current_analysis.signal_strength,
            "confidence": self.current_analysis.confidence,
            "recommendations": [],
        }

        # Generate recommendations based on conditions
        if self.current_analysis.tick_extreme:
            if self.current_analysis.signal_strength > 0.8:
                signals["recommendations"].append(
                    {
                        "action": "FADE",
                        "reason": "Extreme overbought TICK",
                        "strategy": "Bear Call Spread",
                    }
                )
            elif self.current_analysis.signal_strength < -0.8:
                signals["recommendations"].append(
                    {
                        "action": "FADE",
                        "reason": "Extreme oversold TICK",
                        "strategy": "Bull Put Spread",
                    }
                )

        if self.current_analysis.breadth_divergence:
            signals["recommendations"].append(
                {
                    "action": "CAUTION",
                    "reason": "Price/breadth divergence",
                    "strategy": "Reduce position size",
                }
            )

        # Market phase specific recommendations
        if self.current_analysis.market_phase == MarketPhase.MARKUP:
            signals["recommendations"].append(
                {
                    "action": "TREND_FOLLOW",
                    "reason": "Strong markup phase",
                    "strategy": "Bull Put Spreads",
                }
            )
        elif self.current_analysis.market_phase == MarketPhase.MARKDOWN:
            signals["recommendations"].append(
                {
                    "action": "TREND_FOLLOW",
                    "reason": "Strong markdown phase",
                    "strategy": "Bear Call Spreads",
                }
            )

        return signals


# ==============================================================================
# TEST SECTION
# ==============================================================================
if __name__ == "__main__":
    # Test the market internals analyzer
    analyzer = MarketInternalsAnalyzer()

    if analyzer.initialize():
        print("Market Internals Analyzer initialized successfully")

        # Simulate some data updates
        test_data = {"TICK": 450, "ADD": 1200, "VOLD": 1.5e9, "TRIN": 0.85, "VIX": 18.5}

        for symbol, value in test_data.items():
            analyzer.update_internal(symbol, value)

        # Wait for analysis
        time.sleep(6)

        # Get analysis
        analysis = analyzer.get_current_analysis()
        if analysis:
            print(f"\nMarket Condition: {analysis.market_condition.value}")
            print(f"Breadth Condition: {analysis.breadth_condition.value}")
            print(f"Market Phase: {analysis.market_phase.value}")
            print(f"Signal Strength: {analysis.signal_strength:.2f}")
            print(f"Confidence: {analysis.confidence:.2f}")

            if analysis.warnings:
                print("\nWarnings:")
                for warning in analysis.warnings:
                    print(f"  - {warning}")

        # Get trading signals
        signals = analyzer.get_trading_signals()
        if signals.get("recommendations"):
            print("\nTrading Recommendations:")
            for rec in signals["recommendations"]:
                print(f"  - {rec['action']}: {rec['reason']} ({rec['strategy']})")

        # Stop analyzer
        analyzer.stop()
        print("\nMarket Internals Analyzer stopped")

class MarketInternals:
    """Main market internals coordinator class"""
    
    def __init__(self):
        self.current_data: Optional[InternalData] = None
        self.current_snapshot: Optional[MarketInternalsSnapshot] = None
        self.current_analysis: Optional[InternalsAnalysis] = None
    
    def update_data(self, data: InternalData) -> None:
        """Update internal data"""
        self.current_data = data
    
    def update_snapshot(self, snapshot: MarketInternalsSnapshot) -> None:
        """Update market internals snapshot"""
        self.current_snapshot = snapshot
    
    def update_analysis(self, analysis: InternalsAnalysis) -> None:
        """Update internals analysis"""
        self.current_analysis = analysis
    
    def get_current_condition(self) -> MarketCondition:
        """Get current market condition"""
        if self.current_analysis:
            return getattr(self.current_analysis, 'condition', MarketCondition.UNKNOWN)
        return MarketCondition.UNKNOWN
    
    def get_breadth_condition(self) -> BreadthCondition:
        """Get current breadth condition"""
        if self.current_analysis:
            return getattr(self.current_analysis, 'breadth', BreadthCondition.NEUTRAL)
        return BreadthCondition.NEUTRAL
    
    def get_market_phase(self) -> MarketPhase:
        """Get current market phase"""
        if self.current_analysis:
            return getattr(self.current_analysis, 'phase', MarketPhase.UNKNOWN)
        return MarketPhase.UNKNOWN

def get_market_internals() -> MarketInternals:
    """Factory function to get MarketInternals instance"""
    return MarketInternals()
