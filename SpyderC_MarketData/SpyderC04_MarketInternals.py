#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC04_MarketInternals.py
Group: C (Market Data)
Purpose: Market breadth and internals (TICK, ADD, VOLD)

Description:
    This module tracks and analyzes market internals including NYSE TICK, 
    Advance-Decline Line (ADD), and Volume Difference (VOLD). These indicators
    provide insight into market breadth and internal strength, helping to
    confirm or diverge from price movements in major indices.

Author: Mohamed Talib
Date: 2025-01-20
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import datetime
from datetime import time as dt_time
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque
import statistics
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Market internal symbols (Interactive Brokers format)
TICK_SYMBOL = "TICK-NYSE"  # NYSE Tick Index
ADD_SYMBOL = "ADD-NYSE"    # NYSE Advance-Decline
VOLD_SYMBOL = "VOLD-NYSE"  # NYSE Volume Difference
TRIN_SYMBOL = "TRIN-NYSE"  # NYSE Arms Index
VIX_SYMBOL = "VIX"         # CBOE Volatility Index

# Threshold levels
TICK_EXTREME_HIGH = 800
TICK_EXTREME_LOW = -800
TICK_VERY_EXTREME_HIGH = 1000
TICK_VERY_EXTREME_LOW = -1000

ADD_STRONG_BULLISH = 1500
ADD_STRONG_BEARISH = -1500
ADD_EXTREME_BULLISH = 2000
ADD_EXTREME_BEARISH = -2000

VOLD_STRONG_RATIO = 2.0
VOLD_WEAK_RATIO = 0.5

# Update intervals
UPDATE_INTERVAL = 1  # seconds
CUMULATIVE_RESET_TIME = dt_time(9, 30)  # Reset cumulative values at market open

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketBreadth(Enum):
    """Market breadth classification"""
    VERY_BULLISH = auto()
    BULLISH = auto()
    NEUTRAL = auto()
    BEARISH = auto()
    VERY_BEARISH = auto()

class TickExtreme(Enum):
    """TICK extreme classification"""
    VERY_HIGH = auto()
    HIGH = auto()
    NORMAL = auto()
    LOW = auto()
    VERY_LOW = auto()

class InternalsDivergence(Enum):
    """Divergence between internals and price"""
    BULLISH_DIVERGENCE = auto()
    BEARISH_DIVERGENCE = auto()
    NO_DIVERGENCE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class InternalsData:
    """Market internals data point"""
    timestamp: datetime.datetime
    tick: float
    add: float
    vold: float
    vold_ratio: float  # UVOL/DVOL ratio
    trin: Optional[float] = None
    vix: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'tick': self.tick,
            'add': self.add,
            'vold': self.vold,
            'vold_ratio': self.vold_ratio,
            'trin': self.trin,
            'vix': self.vix
        }

class InternalsAnalysis:
    """Analysis of market internals"""
    timestamp: datetime.datetime
    breadth: MarketBreadth
    tick_extreme: TickExtreme
    cumulative_tick: float
    cumulative_add: float
    tick_trend: str  # 'up', 'down', 'neutral'
    add_trend: str   # 'up', 'down', 'neutral'
    vold_trend: str  # 'up', 'down', 'neutral'
    divergence: InternalsDivergence
    strength_score: float  # -100 to 100
    notes: List[str] = field(default_factory=list)

class InternalsSignal:
    """Trading signal from internals"""
    timestamp: datetime.datetime
    signal_type: str  # 'buy', 'sell', 'neutral'
    strength: float   # 0 to 1
    components: Dict[str, float]
    reasons: List[str]

# ==============================================================================
# MARKET INTERNALS CLASS
# ==============================================================================
class MarketInternals:
    """
    Tracks and analyzes market internals.
    
    Monitors NYSE TICK, ADD, VOLD and other breadth indicators to gauge
    market internal strength and identify potential divergences.
    """
    
    def __init__(self, ib_client: Optional[Any] = None, event_manager: Optional[EventManager] = None):
        """
        Initialize market internals tracker.
        
        Args:
            ib_client: Interactive Brokers client (optional)
            event_manager: Event manager instance (optional)
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Data storage
        self.tick_data: deque = deque(maxlen=390)  # Full trading day
        self.add_data: deque = deque(maxlen=390)
        self.vold_data: deque = deque(maxlen=390)
        self.internals_history: deque = deque(maxlen=1000)
        
        # Current values
        self.current_data: Optional[InternalsData] = None
        self.current_analysis: Optional[InternalsAnalysis] = None
        
        # Cumulative values
        self.cumulative_tick = 0.0
        self.cumulative_add = 0.0
        self.last_reset_date = None
        
        # Subscription tracking
        self.subscriptions: Dict[str, int] = {}  # symbol -> reqId
        self.req_id_counter = 9000  # Start from high number to avoid conflicts
        
        # Threading
        self._update_thread: Optional[threading.Thread] = None
        self._running = False
        self._data_lock = threading.RLock()
        
        # Callbacks
        self.signal_callbacks: List[Callable] = []
        
        # For testing/simulation when no IB connection
        self._simulation_mode = ib_client is None
        
        self.logger.info("MarketInternals initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start tracking market internals"""
        if self._running:
            return
        
        self._running = True
        
        # Subscribe to market data if IB client available
        if self.ib_client and not self._simulation_mode:
            self._subscribe_internals()
        
        # Start update thread
        self._update_thread = threading.Thread(
            target=self._update_loop,
            daemon=True,
            name="MarketInternalsUpdate"
        )
        self._update_thread.start()
        
        self.logger.info("Market internals tracking started")
    
    def stop(self) -> None:
        """Stop tracking market internals"""
        self._running = False
        
        # Unsubscribe from market data
        if self.ib_client and not self._simulation_mode:
            self._unsubscribe_internals()
        
        # Wait for thread to finish
        if self._update_thread:
            self._update_thread.join(timeout=5.0)
        
        self.logger.info("Market internals tracking stopped")
    
    # ==========================================================================
    # DATA SUBSCRIPTION
    # ==========================================================================
    def _subscribe_internals(self) -> None:
        """Subscribe to market internals data"""
        try:
            # Subscribe to TICK
            tick_req_id = self._get_next_req_id()
            self.ib_client.reqMktData(
                tick_req_id,
                self._create_index_contract(TICK_SYMBOL),
                "",
                False,
                False,
                []
            )
            self.subscriptions[TICK_SYMBOL] = tick_req_id
            
            # Subscribe to ADD
            add_req_id = self._get_next_req_id()
            self.ib_client.reqMktData(
                add_req_id,
                self._create_index_contract(ADD_SYMBOL),
                "",
                False,
                False,
                []
            )
            self.subscriptions[ADD_SYMBOL] = add_req_id
            
            # Subscribe to VOLD
            vold_req_id = self._get_next_req_id()
            self.ib_client.reqMktData(
                vold_req_id,
                self._create_index_contract(VOLD_SYMBOL),
                "",
                False,
                False,
                []
            )
            self.subscriptions[VOLD_SYMBOL] = vold_req_id
            
            self.logger.info("Subscribed to market internals data")
            
        except Exception as e:
            self.logger.error(f"Error subscribing to internals: {e}")
            self.error_handler.handle_error(e, "MarketInternals")
    
    def _unsubscribe_internals(self) -> None:
        """Unsubscribe from market internals data"""
        for symbol, req_id in self.subscriptions.items():
            try:
                self.ib_client.cancelMktData(req_id)
            except Exception as e:
                self.logger.error(f"Error unsubscribing {symbol}: {e}")
        
        self.subscriptions.clear()
    
    def _create_index_contract(self, symbol: str) -> Any:
        """Create index contract for IB API"""
        # This would create proper IB contract object
        # Simplified for now
        contract = {
            'symbol': symbol,
            'secType': 'IND',
            'exchange': 'NYSE',
            'currency': 'USD'
        }
        return contract
    
    def _get_next_req_id(self) -> int:
        """Get next request ID"""
        self.req_id_counter += 1
        return self.req_id_counter
    
    # ==========================================================================
    # DATA PROCESSING
    # ==========================================================================
    def _update_loop(self) -> None:
        """Main update loop"""
        while self._running:
            try:
                # Update internals data
                if self._simulation_mode:
                    self._update_simulation_data()
                else:
                    self._process_real_data()
                
                # Analyze internals
                with self._data_lock:
                    if self.current_data:
                        self.current_analysis = self._analyze_internals()
                        
                        # Check for signals
                        signal = self._check_for_signals()
                        if signal:
                            self._emit_signal(signal)
                
                time.sleep(UPDATE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
                self.error_handler.handle_error(e, "MarketInternals")
    
    def _update_simulation_data(self) -> None:
        """Update with simulated data for testing"""
        # Generate realistic-looking internals data
        current_time = datetime.datetime.now()
        
        # Simulate correlated movements
        base_movement = math.sin(time.time() / 100) * 0.5
        
        tick = base_movement * 500 + np.random.randn() * 200
        add = base_movement * 1000 + np.random.randn() * 300
        vold = base_movement * 5e8 + np.random.randn() * 1e8
        
        # Calculate VOLD ratio (UVOL/DVOL)
        if vold > 0:
            vold_ratio = 1.5 + base_movement
        else:
            vold_ratio = 0.5 + base_movement
        
        with self._data_lock:
            self.current_data = InternalsData(
                timestamp=current_time,
                tick=tick,
                add=add,
                vold=vold,
                vold_ratio=vold_ratio,
                trin=1.0 - base_movement * 0.3,
                vix=15 + abs(base_movement) * 5
            )
            
            # Store history
            self.tick_data.append(tick)
            self.add_data.append(add)
            self.vold_data.append(vold)
            self.internals_history.append(self.current_data)
            
            # Update cumulative values
            self._update_cumulative_values()
    
    def _process_real_data(self) -> None:
        """Process real market data from IB"""
        # This would process actual data from IB API
        # For now, using placeholder
        pass
    
    def _update_cumulative_values(self) -> None:
        """Update cumulative TICK and ADD"""
        if not self.current_data:
            return
        
        # Reset at market open
        current_date = datetime.datetime.now().date()
        if self.last_reset_date != current_date:
            self.cumulative_tick = 0.0
            self.cumulative_add = 0.0
            self.last_reset_date = current_date
        
        # Update cumulative values
        self.cumulative_tick += self.current_data.tick
        self.cumulative_add += self.current_data.add
    
    # ==========================================================================
    # ANALYSIS
    # ==========================================================================
    def _analyze_internals(self) -> InternalsAnalysis:
        """Analyze current market internals"""
        if not self.current_data:
            return self._get_neutral_analysis()
        
        # Determine market breadth
        breadth = self._classify_breadth()
        
        # Determine TICK extreme
        tick_extreme = self._classify_tick_extreme()
        
        # Calculate trends
        tick_trend = self._calculate_trend(self.tick_data)
        add_trend = self._calculate_trend(self.add_data)
        vold_trend = self._calculate_trend(self.vold_data)
        
        # Check for divergence
        divergence = self._check_divergence()
        
        # Calculate overall strength score
        strength_score = self._calculate_strength_score()
        
        # Generate analysis notes
        notes = self._generate_analysis_notes(
            breadth, tick_extreme, divergence
        )
        
        return InternalsAnalysis(
            timestamp=datetime.datetime.now(),
            breadth=breadth,
            tick_extreme=tick_extreme,
            cumulative_tick=self.cumulative_tick,
            cumulative_add=self.cumulative_add,
            tick_trend=tick_trend,
            add_trend=add_trend,
            vold_trend=vold_trend,
            divergence=divergence,
            strength_score=strength_score,
            notes=notes
        )
    
    def _classify_breadth(self) -> MarketBreadth:
        """Classify market breadth"""
        if not self.current_data:
            return MarketBreadth.NEUTRAL
        
        add = self.current_data.add
        
        if add >= ADD_EXTREME_BULLISH:
            return MarketBreadth.VERY_BULLISH
        elif add >= ADD_STRONG_BULLISH:
            return MarketBreadth.BULLISH
        elif add <= ADD_EXTREME_BEARISH:
            return MarketBreadth.VERY_BEARISH
        elif add <= ADD_STRONG_BEARISH:
            return MarketBreadth.BEARISH
        else:
            return MarketBreadth.NEUTRAL
    
    def _classify_tick_extreme(self) -> TickExtreme:
        """Classify TICK extreme"""
        if not self.current_data:
            return TickExtreme.NORMAL
        
        tick = self.current_data.tick
        
        if tick >= TICK_VERY_EXTREME_HIGH:
            return TickExtreme.VERY_HIGH
        elif tick >= TICK_EXTREME_HIGH:
            return TickExtreme.HIGH
        elif tick <= TICK_VERY_EXTREME_LOW:
            return TickExtreme.VERY_LOW
        elif tick <= TICK_EXTREME_LOW:
            return TickExtreme.LOW
        else:
            return TickExtreme.NORMAL
    
    def _calculate_trend(self, data: deque) -> str:
        """Calculate trend direction"""
        if len(data) < 20:
            return 'neutral'
        
        # Simple linear regression slope
        recent_data = list(data)[-20:]
        x = np.arange(len(recent_data))
        slope = np.polyfit(x, recent_data, 1)[0]
        
        # Normalize by average absolute value
        avg_abs = np.mean(np.abs(recent_data))
        if avg_abs > 0:
            normalized_slope = slope / avg_abs
        else:
            normalized_slope = 0
        
        if normalized_slope > 0.02:
            return 'up'
        elif normalized_slope < -0.02:
            return 'down'
        else:
            return 'neutral'
    
    def _check_divergence(self) -> InternalsDivergence:
        """Check for divergence between internals and price"""
        # Simplified divergence check
        # In reality, would compare with SPY price action
        
        if not self.current_data:
            return InternalsDivergence.NO_DIVERGENCE
        
        # For now, check if internals are extremely one-sided
        tick = self.current_data.tick
        add = self.current_data.add
        vold_ratio = self.current_data.vold_ratio
        
        # Bullish divergence: internals very positive
        if (tick > TICK_EXTREME_HIGH and 
            add > ADD_STRONG_BULLISH and 
            vold_ratio > VOLD_STRONG_RATIO):
            return InternalsDivergence.BULLISH_DIVERGENCE
        
        # Bearish divergence: internals very negative
        elif (tick < TICK_EXTREME_LOW and 
              add < ADD_STRONG_BEARISH and 
              vold_ratio < VOLD_WEAK_RATIO):
            return InternalsDivergence.BEARISH_DIVERGENCE
        
        return InternalsDivergence.NO_DIVERGENCE
    
    def _calculate_strength_score(self) -> float:
        """Calculate overall market internal strength (-100 to 100)"""
        if not self.current_data:
            return 0.0
        
        # Normalize each component
        tick_score = np.clip(self.current_data.tick / 1000, -1, 1) * 30
        add_score = np.clip(self.current_data.add / 2000, -1, 1) * 40
        vold_score = np.clip((self.current_data.vold_ratio - 1) / 2, -1, 1) * 30
        
        # Combine scores
        total_score = tick_score + add_score + vold_score
        
        return np.clip(total_score, -100, 100)
    
    def _generate_analysis_notes(
        self,
        breadth: MarketBreadth,
        tick_extreme: TickExtreme,
        divergence: InternalsDivergence
    ) -> List[str]:
        """Generate analysis notes"""
        notes = []
        
        # Breadth notes
        if breadth in [MarketBreadth.VERY_BULLISH, MarketBreadth.VERY_BEARISH]:
            notes.append(f"Extreme market breadth: {breadth.name}")
        
        # TICK extreme notes
        if tick_extreme in [TickExtreme.VERY_HIGH, TickExtreme.VERY_LOW]:
            notes.append(f"TICK at extreme level: {self.current_data.tick:.0f}")
        
        # Divergence notes
        if divergence != InternalsDivergence.NO_DIVERGENCE:
            notes.append(f"Potential {divergence.name.lower().replace('_', ' ')}")
        
        # Cumulative notes
        if abs(self.cumulative_tick) > 5000:
            notes.append(f"Cumulative TICK extreme: {self.cumulative_tick:.0f}")
        
        if abs(self.cumulative_add) > 10000:
            notes.append(f"Cumulative ADD extreme: {self.cumulative_add:.0f}")
        
        return notes
    
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def _check_for_signals(self) -> Optional[InternalsSignal]:
        """Check for trading signals from internals"""
        if not self.current_analysis or not self.current_data:
            return None
        
        signal_type = 'neutral'
        strength = 0.0
        components = {}
        reasons = []
        
        # Strong bullish signal
        if (self.current_analysis.breadth == MarketBreadth.VERY_BULLISH and
            self.current_analysis.tick_extreme in [TickExtreme.HIGH, TickExtreme.VERY_HIGH] and
            self.current_data.vold_ratio > VOLD_STRONG_RATIO):
            
            signal_type = 'buy'
            strength = 0.8
            reasons.append("Very strong bullish internals across all indicators")
        
        # Strong bearish signal
        elif (self.current_analysis.breadth == MarketBreadth.VERY_BEARISH and
              self.current_analysis.tick_extreme in [TickExtreme.LOW, TickExtreme.VERY_LOW] and
              self.current_data.vold_ratio < VOLD_WEAK_RATIO):
            
            signal_type = 'sell'
            strength = 0.8
            reasons.append("Very strong bearish internals across all indicators")
        
        # Divergence signals
        elif self.current_analysis.divergence == InternalsDivergence.BULLISH_DIVERGENCE:
            signal_type = 'buy'
            strength = 0.6
            reasons.append("Bullish divergence detected in internals")
        
        elif self.current_analysis.divergence == InternalsDivergence.BEARISH_DIVERGENCE:
            signal_type = 'sell'
            strength = 0.6
            reasons.append("Bearish divergence detected in internals")
        
        # Trend exhaustion signals
        elif (self.current_analysis.tick_extreme == TickExtreme.VERY_HIGH and
              self.cumulative_tick > 8000):
            signal_type = 'sell'
            strength = 0.5
            reasons.append("Potential short-term top - extreme bullish TICK readings")
        
        elif (self.current_analysis.tick_extreme == TickExtreme.VERY_LOW and
              self.cumulative_tick < -8000):
            signal_type = 'buy'
            strength = 0.5
            reasons.append("Potential short-term bottom - extreme bearish TICK readings")
        
        if signal_type != 'neutral':
            # Add component scores
            components = {
                'tick': self.current_data.tick,
                'add': self.current_data.add,
                'vold_ratio': self.current_data.vold_ratio,
                'strength_score': self.current_analysis.strength_score
            }
            
            return InternalsSignal(
                timestamp=datetime.datetime.now(),
                signal_type=signal_type,
                strength=strength,
                components=components,
                reasons=reasons
            )
        
        return None
    
    def _emit_signal(self, signal: InternalsSignal) -> None:
        """Emit trading signal"""
        # Call callbacks
        for callback in self.signal_callbacks:
            try:
                callback(signal)
            except Exception as e:
                self.logger.error(f"Error in signal callback: {e}")
        
        # Emit event if event manager available
        if self.event_manager:
            self.event_manager.emit(Event(
                EventType.SIGNAL,
                {
                    'source': 'market_internals',
                    'signal_type': signal.signal_type,
                    'strength': signal.strength,
                    'components': signal.components,
                    'reasons': signal.reasons
                }
            ))
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def get_current_readings(self) -> Dict[str, float]:
        """
        Get current market internals readings.
        
        Returns:
            Dictionary of current values
        """
        with self._data_lock:
            if not self.current_data:
                return {
                    'TICK': 0,
                    'ADD': 0,
                    'VOLD': 0,
                    'VOLD_RATIO': 1.0,
                    'CUMULATIVE_TICK': 0,
                    'CUMULATIVE_ADD': 0
                }
            
            return {
                'TICK': self.current_data.tick,
                'ADD': self.current_data.add,
                'VOLD': self.current_data.vold,
                'VOLD_RATIO': self.current_data.vold_ratio,
                'CUMULATIVE_TICK': self.cumulative_tick,
                'CUMULATIVE_ADD': self.cumulative_add
            }
    
    def get_analysis(self) -> Optional[InternalsAnalysis]:
        """Get current analysis"""
        with self._data_lock:
            return self.current_analysis
    
    def get_strength_score(self) -> float:
        """Get current strength score (-100 to 100)"""
        with self._data_lock:
            if self.current_analysis:
                return self.current_analysis.strength_score
            return 0.0
    
    def get_historical_data(self, minutes: int = 30) -> pd.DataFrame:
        """
        Get historical internals data.
        
        Args:
            minutes: Number of minutes of history
            
        Returns:
            DataFrame with historical data
        """
        with self._data_lock:
            if not self.internals_history:
                return pd.DataFrame()
            
            # Convert to DataFrame
            data = [d.to_dict() for d in self.internals_history]
            df = pd.DataFrame(data)
            
            # Filter by time
            if minutes > 0:
                cutoff = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df[df['timestamp'] > cutoff]
            
            return df
    
    def register_signal_callback(self, callback: Callable) -> None:
        """
        Register callback for trading signals.
        
        Args:
            callback: Function to call with InternalsSignal
        """
        self.signal_callbacks.append(callback)
    
    def force_analysis(self) -> None:
        """Force immediate analysis update"""
        with self._data_lock:
            if self.current_data:
                self.current_analysis = self._analyze_internals()
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _get_neutral_analysis(self) -> InternalsAnalysis:
        """Get neutral analysis when no data available"""
        return InternalsAnalysis(
            timestamp=datetime.datetime.now(),
            breadth=MarketBreadth.NEUTRAL,
            tick_extreme=TickExtreme.NORMAL,
            cumulative_tick=0.0,
            cumulative_add=0.0,
            tick_trend='neutral',
            add_trend='neutral',
            vold_trend='neutral',
            divergence=InternalsDivergence.NO_DIVERGENCE,
            strength_score=0.0,
            notes=["No market internals data available"]
        )
    
    def update_market_data(self, req_id: int, field: int, value: float) -> None:
        """
        Update market data from IB API callback.
        
        Args:
            req_id: Request ID
            field: Field type
            value: Field value
        """
        # This would be called by IB API wrapper
        # Map req_id to symbol and update appropriate data
        pass

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test market internals
    internals = MarketInternals()
    
    # Define signal callback
    def on_signal(signal: InternalsSignal):
        print(f"\nSIGNAL: {signal.signal_type.upper()} (strength: {signal.strength:.0%})")
        print(f"Components: {signal.components}")
        print(f"Reasons: {signal.reasons}")
    
    # Register callback
    internals.register_signal_callback(on_signal)
    
    # Start tracking
    internals.start()
    
    try:
        # Run for a while
        for i in range(60):
            # Get current readings
            readings = internals.get_current_readings()
            analysis = internals.get_analysis()
            
            if i % 10 == 0:  # Print every 10 seconds
                print(f"\nTime: {datetime.datetime.now()}")
                print(f"TICK: {readings['TICK']:.0f}")
                print(f"ADD: {readings['ADD']:.0f}")
                print(f"VOLD Ratio: {readings['VOLD_RATIO']:.2f}")
                
                if analysis:
                    print(f"Breadth: {analysis.breadth.name}")
                    print(f"Strength Score: {analysis.strength_score:.0f}")
                    if analysis.notes:
                        print(f"Notes: {', '.join(analysis.notes)}")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping...")
    
    finally:
        internals.stop()
        
        # Get historical data
        history = internals.get_historical_data(5)
        if not history.empty:
            print("\nHistorical Summary:")
            print(f"Average TICK: {history['tick'].mean():.0f}")
            print(f"Average ADD: {history['add'].mean():.0f}")
            print(f"Average VOLD Ratio: {history['vold_ratio'].mean():.2f}")
