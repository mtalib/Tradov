#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC15_GEXDEXCalculator.py
Group: C (Market Data)
Purpose: Custom Gamma Exposure (GEX) and Delta Exposure (DEX) Calculator

Description:
    This module calculates real-time Gamma Exposure (GEX) and Delta Exposure (DEX)
    from options data to identify key support/resistance levels and predict market
    volatility regimes. It integrates with the existing OptionChainManager to provide
    proprietary market structure analysis for enhanced AI agent decision-making.

Author: Spyder AI
Date: 2024-12-30
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import SPY_CONTRACT_MULTIPLIER
from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager, OptionData, OptionType
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# GEX/DEX Configuration
UPDATE_INTERVAL = 60  # Update every 60 seconds
CACHE_SIZE = 1000    # Keep last 1000 calculations
CONTRACT_SIZE = 100  # Standard options contract size

# Strike filtering
MAX_STRIKE_DISTANCE = 50  # Only consider strikes within $50 of spot
MIN_OPEN_INTEREST = 100   # Minimum OI to consider

# Regime thresholds
POSITIVE_GEX_THRESHOLD = 0
HIGH_GEX_THRESHOLD = 1_000_000_000  # 1 billion
ZERO_GAMMA_TOLERANCE = 2.0  # Within $2 is "near zero gamma"

# Database
DB_RETENTION_DAYS = 30  # Keep 30 days of GEX/DEX history

# ==============================================================================
# ENUMS
# ==============================================================================
class GEXRegime(Enum):
    """Gamma exposure regime classification"""
    POSITIVE = "positive"     # Market makers long gamma (dampens volatility)
    NEGATIVE = "negative"     # Market makers short gamma (amplifies volatility)
    NEUTRAL = "neutral"       # Near zero gamma

class MarketMakerPosition(Enum):
    """Market maker position assumptions"""
    SHORT_CALLS = -1  # Market makers typically short calls
    LONG_PUTS = 1     # Market makers typically long puts

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GEXDEXData:
    """Complete GEX/DEX calculation results"""
    timestamp: datetime
    underlying_price: float
    total_gex: float
    call_gex: float
    put_gex: float
    total_dex: float
    call_dex: float
    put_dex: float
    zero_gamma_level: Optional[float]
    gex_regime: GEXRegime
    gex_by_strike: Dict[float, float]
    dex_by_strike: Dict[float, float]
    key_levels: List[Dict[str, Any]]
    
@dataclass
class KeyLevel:
    """Key support/resistance level based on GEX"""
    strike: float
    gex_value: float
    level_type: str  # 'support' or 'resistance'
    strength: float  # 1-5 scale
    distance_from_spot: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class GEXDEXCalculator:
    """
    Custom Gamma and Delta Exposure Calculator for SPY Options.
    
    This class calculates real-time GEX and DEX values from options chain data,
    identifies key support/resistance levels, and provides market structure signals
    for AI agents and trading strategies.
    """
    
    def __init__(self, option_chain_manager: OptionChainManager, 
                 event_manager: EventManager,
                 db_path: str = "spyder_gex_dex.db"):
        """Initialize GEX/DEX Calculator"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.option_chain = option_chain_manager
        self.event_manager = event_manager
        self.db_path = db_path
        
        # Data storage
        self.historical_data = deque(maxlen=CACHE_SIZE)
        self.current_data: Optional[GEXDEXData] = None
        self.last_update = datetime.now()
        
        # Threading
        self.running = False
        self.update_thread = None
        self._lock = threading.Lock()
        
        # Initialize database
        self._init_database()
        
        self.logger.info("GEX/DEX Calculator initialized")
    
    # ==========================================================================
    # DATABASE METHODS
    # ==========================================================================
    def _init_database(self):
        """Initialize SQLite database for GEX/DEX storage"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Main GEX/DEX table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gex_dex_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    underlying_price REAL,
                    total_gex REAL,
                    call_gex REAL,
                    put_gex REAL,
                    total_dex REAL,
                    call_dex REAL,
                    put_dex REAL,
                    zero_gamma_level REAL,
                    gex_regime TEXT,
                    data_json TEXT
                )
            ''')
            
            # Key levels table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS gex_key_levels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    strike REAL,
                    gex_value REAL,
                    level_type TEXT,
                    strength REAL
                )
            ''')
            
            # Create indices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_gex_timestamp ON gex_dex_data(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_levels_timestamp ON gex_key_levels(timestamp)')
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
    
    # ==========================================================================
    # CALCULATION METHODS
    # ==========================================================================
    def calculate_gex_dex(self) -> Optional[GEXDEXData]:
        """
        Calculate current GEX and DEX values from options chain.
        
        Returns:
            GEXDEXData object with complete calculations
        """
        try:
            # Get current option chain data
            chains = self.option_chain.get_all_chains()
            if not chains:
                self.logger.warning("No option chain data available")
                return None
            
            # Get underlying price
            underlying_price = self.option_chain.get_underlying_price()
            if not underlying_price:
                self.logger.warning("No underlying price available")
                return None
            
            # Initialize accumulators
            total_gex = 0.0
            call_gex = 0.0
            put_gex = 0.0
            total_dex = 0.0
            call_dex = 0.0
            put_dex = 0.0
            gex_by_strike = defaultdict(float)
            dex_by_strike = defaultdict(float)
            
            # Process each expiration
            for expiry, chain in chains.items():
                # Process calls
                for strike, call_data in chain.calls.items():
                    if self._should_include_option(call_data, underlying_price):
                        option_gex = self._calculate_option_gex(
                            call_data, underlying_price, is_call=True
                        )
                        option_dex = self._calculate_option_dex(
                            call_data, is_call=True
                        )
                        
                        call_gex += option_gex
                        total_gex += option_gex
                        gex_by_strike[strike] += option_gex
                        
                        call_dex += option_dex
                        total_dex += option_dex
                        dex_by_strike[strike] += option_dex
                
                # Process puts
                for strike, put_data in chain.puts.items():
                    if self._should_include_option(put_data, underlying_price):
                        option_gex = self._calculate_option_gex(
                            put_data, underlying_price, is_call=False
                        )
                        option_dex = self._calculate_option_dex(
                            put_data, is_call=False
                        )
                        
                        put_gex += option_gex
                        total_gex += option_gex
                        gex_by_strike[strike] += option_gex
                        
                        put_dex += option_dex
                        total_dex += option_dex
                        dex_by_strike[strike] += option_dex
            
            # Find zero gamma level
            zero_gamma_level = self._find_zero_gamma_level(
                dict(gex_by_strike), underlying_price
            )
            
            # Determine regime
            gex_regime = self._determine_gex_regime(total_gex, zero_gamma_level, underlying_price)
            
            # Identify key levels
            key_levels = self._identify_key_levels(
                dict(gex_by_strike), underlying_price
            )
            
            # Create result
            result = GEXDEXData(
                timestamp=datetime.now(),
                underlying_price=underlying_price,
                total_gex=total_gex,
                call_gex=call_gex,
                put_gex=put_gex,
                total_dex=total_dex,
                call_dex=call_dex,
                put_dex=put_dex,
                zero_gamma_level=zero_gamma_level,
                gex_regime=gex_regime,
                gex_by_strike=dict(gex_by_strike),
                dex_by_strike=dict(dex_by_strike),
                key_levels=key_levels
            )
            
            # Store current data
            with self._lock:
                self.current_data = result
                self.historical_data.append(result)
                self.last_update = datetime.now()
            
            # Store in database
            self._store_to_database(result)
            
            # Emit event
            self._emit_gex_update_event(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error calculating GEX/DEX: {e}")
            self.error_handler.handle_error(e, "calculate_gex_dex")
            return None
    
    def _calculate_option_gex(self, option: OptionData, spot_price: float, 
                            is_call: bool) -> float:
        """
        Calculate GEX for a single option.
        
        GEX = Gamma × Contract Size × Open Interest × Spot Price² × 0.01 × Position
        """
        if not option.gamma or not option.open_interest:
            return 0.0
        
        # Market maker position (short calls, long puts)
        position = MarketMakerPosition.SHORT_CALLS.value if is_call else MarketMakerPosition.LONG_PUTS.value
        
        gex = (
            option.gamma * 
            CONTRACT_SIZE * 
            option.open_interest * 
            spot_price * spot_price * 
            0.01 *  # For 1% move
            position
        )
        
        return gex
    
    def _calculate_option_dex(self, option: OptionData, is_call: bool) -> float:
        """
        Calculate DEX for a single option.
        
        DEX = Delta × Contract Size × Open Interest × Position
        """
        if not option.delta or not option.open_interest:
            return 0.0
        
        # Market maker position (short calls, long puts)
        # Both result in negative delta exposure
        position = -1  # Always negative for market maker perspective
        
        dex = (
            option.delta * 
            CONTRACT_SIZE * 
            option.open_interest * 
            position
        )
        
        return dex
    
    def _should_include_option(self, option: OptionData, spot_price: float) -> bool:
        """Determine if option should be included in calculations"""
        # Check strike distance
        if abs(option.strike - spot_price) > MAX_STRIKE_DISTANCE:
            return False
        
        # Check open interest
        if not option.open_interest or option.open_interest < MIN_OPEN_INTEREST:
            return False
        
        # Check if we have Greeks
        if not option.gamma or not option.delta:
            return False
        
        return True
    
    def _find_zero_gamma_level(self, gex_by_strike: Dict[float, float], 
                              spot_price: float) -> Optional[float]:
        """Find the price level where gamma exposure is zero"""
        if not gex_by_strike:
            return None
        
        # Sort strikes
        strikes = sorted(gex_by_strike.keys())
        
        # Calculate cumulative GEX from lowest strike
        cumulative_gex = 0.0
        prev_strike = strikes[0]
        prev_cumulative = 0.0
        
        for strike in strikes:
            cumulative_gex += gex_by_strike[strike]
            
            # Check for zero crossing
            if prev_cumulative <= 0 <= cumulative_gex or prev_cumulative >= 0 >= cumulative_gex:
                # Linear interpolation
                if cumulative_gex != prev_cumulative:
                    weight = abs(prev_cumulative) / (abs(prev_cumulative) + abs(cumulative_gex))
                    zero_gamma = prev_strike + weight * (strike - prev_strike)
                    return round(zero_gamma, 2)
            
            prev_strike = strike
            prev_cumulative = cumulative_gex
        
        return None
    
    def _determine_gex_regime(self, total_gex: float, zero_gamma: Optional[float],
                            spot_price: float) -> GEXRegime:
        """Determine current GEX regime"""
        if abs(total_gex) < 1e6:  # Less than 1 million
            return GEXRegime.NEUTRAL
        
        if total_gex > POSITIVE_GEX_THRESHOLD:
            return GEXRegime.POSITIVE
        else:
            return GEXRegime.NEGATIVE
    
    def _identify_key_levels(self, gex_by_strike: Dict[float, float],
                           spot_price: float) -> List[Dict[str, Any]]:
        """Identify key support/resistance levels based on GEX concentration"""
        if not gex_by_strike:
            return []
        
        # Sort by absolute GEX value
        sorted_strikes = sorted(
            gex_by_strike.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        
        key_levels = []
        max_abs_gex = abs(sorted_strikes[0][1]) if sorted_strikes else 1
        
        for strike, gex in sorted_strikes[:10]:  # Top 10 levels
            # Determine level type
            if gex > 0:
                level_type = "support"  # Positive GEX acts as support
            else:
                level_type = "resistance"  # Negative GEX acts as resistance
            
            # Calculate strength (1-5 scale)
            strength = min(5, 1 + (abs(gex) / max_abs_gex) * 4)
            
            # Distance from current price
            distance = abs(strike - spot_price)
            
            key_levels.append({
                'strike': strike,
                'gex': gex,
                'type': level_type,
                'strength': round(strength, 1),
                'distance': round(distance, 2)
            })
        
        return key_levels
    
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def get_trading_signals(self) -> Dict[str, Any]:
        """Generate trading signals based on current GEX/DEX data"""
        if not self.current_data:
            return {}
        
        data = self.current_data
        signals = {
            'regime': data.gex_regime.value,
            'volatility_expectation': 'low' if data.gex_regime == GEXRegime.POSITIVE else 'high',
            'key_support': None,
            'key_resistance': None,
            'near_zero_gamma': False,
            'recommended_strategy': None
        }
        
        # Find nearest support/resistance
        for level in data.key_levels:
            if level['type'] == 'support' and level['strike'] < data.underlying_price:
                if not signals['key_support'] or level['strike'] > signals['key_support']:
                    signals['key_support'] = level['strike']
            elif level['type'] == 'resistance' and level['strike'] > data.underlying_price:
                if not signals['key_resistance'] or level['strike'] < signals['key_resistance']:
                    signals['key_resistance'] = level['strike']
        
        # Check if near zero gamma
        if data.zero_gamma_level:
            distance = abs(data.underlying_price - data.zero_gamma_level)
            signals['near_zero_gamma'] = distance <= ZERO_GAMMA_TOLERANCE
        
        # Recommend strategy
        signals['recommended_strategy'] = self._recommend_strategy(data, signals)
        
        return signals
    
    def _recommend_strategy(self, data: GEXDEXData, signals: Dict[str, Any]) -> str:
        """Recommend trading strategy based on GEX/DEX analysis"""
        if signals['near_zero_gamma']:
            return "LONG_VOLATILITY"  # Expect breakout
        
        if data.gex_regime == GEXRegime.POSITIVE:
            if data.total_dex < 0:
                return "BULL_PUT_SPREAD"  # Bullish bias, sell volatility
            else:
                return "BEAR_CALL_SPREAD"  # Bearish bias, sell volatility
        else:  # Negative GEX
            if abs(data.total_gex) > HIGH_GEX_THRESHOLD:
                return "IRON_CONDOR_WIDE"  # Very high volatility expected
            else:
                return "DIRECTIONAL_OPTIONS"  # Moderate volatility, trend following
    
    # ==========================================================================
    # REAL-TIME UPDATES
    # ==========================================================================
    def start_monitoring(self):
        """Start real-time GEX/DEX monitoring"""
        if self.running:
            self.logger.warning("Monitoring already running")
            return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._monitoring_loop)
        self.update_thread.daemon = True
        self.update_thread.start()
        
        self.logger.info("GEX/DEX monitoring started")
    
    def stop_monitoring(self):
        """Stop real-time monitoring"""
        self.running = False
        if self.update_thread:
            self.update_thread.join(timeout=5)
        
        self.logger.info("GEX/DEX monitoring stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Calculate GEX/DEX
                self.calculate_gex_dex()
                
                # Log summary
                if self.current_data:
                    self.logger.info(
                        f"GEX Update: Total={self.current_data.total_gex:,.0f}, "
                        f"Regime={self.current_data.gex_regime.value}, "
                        f"Zero Gamma={self.current_data.zero_gamma_level}"
                    )
                
                # Check for regime changes
                self._check_regime_changes()
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
            
            # Wait for next update
            time.sleep(UPDATE_INTERVAL)
    
    def _check_regime_changes(self):
        """Check for significant regime changes and emit alerts"""
        if len(self.historical_data) < 2:
            return
        
        current = self.historical_data[-1]
        previous = self.historical_data[-2]
        
        # Check for regime change
        if current.gex_regime != previous.gex_regime:
            self.logger.warning(
                f"GEX REGIME CHANGE: {previous.gex_regime.value} → {current.gex_regime.value}"
            )
            self._emit_regime_change_event(previous.gex_regime, current.gex_regime)
        
        # Check for zero gamma level movement
        if current.zero_gamma_level and previous.zero_gamma_level:
            zg_move = abs(current.zero_gamma_level - previous.zero_gamma_level)
            if zg_move > 5:  # More than $5 move
                self.logger.warning(f"ZERO GAMMA MOVE: {zg_move:.2f} points")
                self._emit_zero_gamma_move_event(zg_move)
    
    # ==========================================================================
    # DATABASE OPERATIONS
    # ==========================================================================
    def _store_to_database(self, data: GEXDEXData):
        """Store GEX/DEX data to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Store main data
            cursor.execute('''
                INSERT INTO gex_dex_data (
                    timestamp, underlying_price, total_gex, call_gex, put_gex,
                    total_dex, call_dex, put_dex, zero_gamma_level, gex_regime, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.timestamp,
                data.underlying_price,
                data.total_gex,
                data.call_gex,
                data.put_gex,
                data.total_dex,
                data.call_dex,
                data.put_dex,
                data.zero_gamma_level,
                data.gex_regime.value,
                json.dumps({
                    'gex_by_strike': data.gex_by_strike,
                    'dex_by_strike': data.dex_by_strike,
                    'key_levels': data.key_levels
                })
            ))
            
            # Store key levels
            for level in data.key_levels[:5]:  # Top 5 levels
                cursor.execute('''
                    INSERT INTO gex_key_levels (timestamp, strike, gex_value, level_type, strength)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    data.timestamp,
                    level['strike'],
                    level['gex'],
                    level['type'],
                    level['strength']
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Database storage failed: {e}")
    
    # ==========================================================================
    # EVENT MANAGEMENT
    # ==========================================================================
    def _emit_gex_update_event(self, data: GEXDEXData):
        """Emit GEX update event"""
        event = Event(
            event_type=EventType.MARKET_DATA,
            data={
                'type': 'gex_update',
                'total_gex': data.total_gex,
                'gex_regime': data.gex_regime.value,
                'zero_gamma': data.zero_gamma_level,
                'key_levels': data.key_levels[:3]  # Top 3 levels
            }
        )
        self.event_manager.emit(event)
    
    def _emit_regime_change_event(self, old_regime: GEXRegime, new_regime: GEXRegime):
        """Emit regime change event"""
        event = Event(
            event_type=EventType.SIGNAL,
            data={
                'type': 'gex_regime_change',
                'old_regime': old_regime.value,
                'new_regime': new_regime.value,
                'timestamp': datetime.now()
            }
        )
        self.event_manager.emit(event)
    
    def _emit_zero_gamma_move_event(self, move_size: float):
        """Emit zero gamma move event"""
        event = Event(
            event_type=EventType.SIGNAL,
            data={
                'type': 'zero_gamma_move',
                'move_size': move_size,
                'timestamp': datetime.now()
            }
        )
        self.event_manager.emit(event)
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def get_current_gex_dex(self) -> Optional[Dict[str, Any]]:
        """Get current GEX/DEX values for quick access"""
        if not self.current_data:
            return None
        
        return {
            'gex': self.current_data.total_gex,
            'dex': self.current_data.total_dex,
            'zero_gamma': self.current_data.zero_gamma_level,
            'regime': self.current_data.gex_regime.value,
            'last_update': self.last_update
        }
    
    def get_historical_data(self, hours: int = 24) -> pd.DataFrame:
        """Get historical GEX/DEX data as DataFrame"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        data = []
        for item in self.historical_data:
            if item.timestamp >= cutoff:
                data.append({
                    'timestamp': item.timestamp,
                    'gex': item.total_gex,
                    'dex': item.total_dex,
                    'zero_gamma': item.zero_gamma_level,
                    'regime': item.gex_regime.value
                })
        
        return pd.DataFrame(data)

# ==============================================================================
# TESTING
# ==============================================================================
if __name__ == "__main__":
    print("Testing GEX/DEX Calculator...")
    
    # Initialize components
    event_manager = EventManager()
    
    # You would use your actual OptionChainManager here
    # For testing, we'll create a mock
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    
    # Initialize broker connection
    ib_client = SpyderClient()
    if ib_client.connect():
        print("✅ Connected to IBKR")
        
        # Initialize option chain manager
        option_chain = OptionChainManager(ib_client, event_manager)
        option_chain.start()
        
        # Initialize GEX/DEX calculator
        gex_calculator = GEXDEXCalculator(option_chain, event_manager)
        
        # Calculate once
        print("\nCalculating GEX/DEX...")
        result = gex_calculator.calculate_gex_dex()
        
        if result:
            print(f"\n📊 GEX/DEX Results:")
            print(f"Total GEX: {result.total_gex:,.0f}")
            print(f"Call GEX: {result.call_gex:,.0f}")
            print(f"Put GEX: {result.put_gex:,.0f}")
            print(f"Total DEX: {result.total_dex:,.0f}")
            print(f"Zero Gamma: {result.zero_gamma_level}")
            print(f"Regime: {result.gex_regime.value}")
            
            print(f"\n🎯 Key Levels:")
            for level in result.key_levels[:5]:
                print(f"  {level['strike']}: {level['type'].upper()} "
                      f"(Strength: {level['strength']}, GEX: {level['gex']:,.0f})")
            
            # Get trading signals
            signals = gex_calculator.get_trading_signals()
            print(f"\n📡 Trading Signals:")
            print(f"Volatility Expectation: {signals['volatility_expectation']}")
            print(f"Key Support: {signals['key_support']}")
            print(f"Key Resistance: {signals['key_resistance']}")
            print(f"Near Zero Gamma: {signals['near_zero_gamma']}")
            print(f"Recommended Strategy: {signals['recommended_strategy']}")
            
            # Start monitoring
            print("\n🔄 Starting real-time monitoring...")
            gex_calculator.start_monitoring()
            
            # Run for a bit
            time.sleep(30)
            
            # Stop monitoring
            gex_calculator.stop_monitoring()
            
        # Cleanup
        option_chain.stop()
        ib_client.disconnect()
        
    print("\n✅ Test completed!")
