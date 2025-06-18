#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD14_RSIMeanReversion.py
Group: D (Trading Strategies)
Purpose: RSI mean reversion strategy

Description:
    This module implements an RSI mean reversion strategy that buys calls when
    RSI < 30 (oversold) and buys puts when RSI > 70 (overbought). The strategy
    exits when RSI returns to 50 (neutral) and is most active during the
    11:00 AM - 2:00 PM window as recommended by research.

Author: Mohamed Talib
Date: 2025-01-10
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, TradingSignal, SignalStrength
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import SignalType, OptionType
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF10_IVRankCalculator import get_iv_rank_calculator
from SpyderB_Broker.SpyderB06_ContractBuilder import OptionContract
from SpyderE_Risk.SpyderE03_StrategyHealthMonitor import get_strategy_health_monitor

# ==============================================================================
# CONSTANTS
# ==============================================================================
# RSI parameters
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
RSI_NEUTRAL = 50
RSI_EXIT_BUFFER = 5  # Exit at 45-55 range

# Trading windows (11:00 AM - 2:00 PM optimal)
TRADING_START = time(11, 0)
TRADING_END = time(14, 0)
POSITION_CLOSE_TIME = time(15, 30)

# Option parameters
TARGET_DTE = 1  # 1-day options for mean reversion
MAX_DTE = 3
DELTA_TARGET_CALL = 0.40
DELTA_TARGET_PUT = -0.40
MIN_IV_RANK = 30

# Position management
MAX_POSITIONS = 3
PROFIT_TARGET = 0.50  # 50% of premium
STOP_LOSS = 1.00  # 100% of premium (2:1 risk/reward)
TIME_STOP_HOURS = 4  # Exit after 4 hours if no mean reversion

# ==============================================================================
# ENUMS
# ==============================================================================
class RSIState(Enum):
    """RSI state classification"""
    OVERSOLD = auto()
    OVERBOUGHT = auto()
    NEUTRAL = auto()
    REVERTING_UP = auto()
    REVERTING_DOWN = auto()

class SignalQuality(Enum):
    """Signal quality classification"""
    PREMIUM = auto()
    STANDARD = auto()
    WEAK = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RSISignal:
    """RSI mean reversion signal"""
    rsi_value: float
    rsi_state: RSIState
    divergence: bool
    volume_confirmation: bool
    support_resistance_nearby: bool
    signal_quality: SignalQuality
    entry_price: float
    expected_reversion_price: float
    confidence: float = 0.0

@dataclass
class RSIPosition:
    """Active RSI position tracking"""
    entry_time: datetime
    entry_rsi: float
    direction: str  # 'CALL' or 'PUT'
    target_rsi: float
    max_favorable_rsi: float
    time_in_position: timedelta
    reversion_progress: float = 0.0

# ==============================================================================
# RSI MEAN REVERSION STRATEGY
# ==============================================================================
class RSIMeanReversionStrategy(BaseStrategy):
    """
    RSI mean reversion strategy implementation.
    
    Strategy rules:
    - Buy calls when RSI < 30 (oversold)
    - Buy puts when RSI > 70 (overbought)
    - Exit when RSI returns to 50 (neutral)
    - Most active 11:00 AM - 2:00 PM
    - Use 1-3 DTE options
    """
    
    def __init__(self, event_manager, risk_profile, config):
        """Initialize RSI mean reversion strategy"""
        super().__init__("RSIMeanReversion", event_manager, risk_profile, config)
        
        # Components
        self.indicators = TechnicalIndicators()
        self.iv_calculator = get_iv_rank_calculator()
        self.health_monitor = get_strategy_health_monitor()
        
        # Register with health monitor
        self.health_monitor.register_strategy(self.name)
        
        # RSI tracking
        self.current_rsi = 50.0
        self.rsi_history = []
        self.rsi_state = RSIState.NEUTRAL
        self.rsi_extremes = {'oversold': [], 'overbought': []}
        
        # Position tracking
        self.active_positions: Dict[str, RSIPosition] = {}
        self.completed_trades = []
        
        # Performance metrics
        self.reversion_success_rate = 0.5
        self.avg_reversion_time = timedelta(hours=2)
        self.avg_reversion_magnitude = 15.0  # RSI points
        
        self.logger.info("RSIMeanReversion strategy initialized")
    
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """Generate RSI mean reversion signals"""
        signals = []
        
        # Check if strategy is enabled
        if not self.health_monitor.is_strategy_enabled(self.name):
            return signals
        
        # Check time window
        current_time = datetime.now().time()
        if not (TRADING_START <= current_time <= TRADING_END):
            return signals
        
        # Need enough data for RSI calculation
        if len(market_data) < RSI_PERIOD + 5:
            return signals
        
        # Calculate RSI
        rsi_series = self.indicators.rsi(market_data['close'], period=RSI_PERIOD)
        self.current_rsi = rsi_series.iloc[-1]
        self.rsi_history.append(self.current_rsi)
        
        # Update RSI state
        self._update_rsi_state(rsi_series)
        
        # Check for mean reversion opportunities
        rsi_signal = self._check_rsi_extremes(market_data, rsi_series)
        
        if rsi_signal and self._validate_signal(rsi_signal, market_data):
            trading_signal = self._create_trading_signal(rsi_signal, market_data)
            if trading_signal:
                signals.append(trading_signal)
        
        return signals
    
    def _update_rsi_state(self, rsi_series: pd.Series) -> None:
        """Update current RSI state"""
        current = rsi_series.iloc[-1]
        prev = rsi_series.iloc[-2] if len(rsi_series) > 1 else current
        
        # Determine state
        if current <= RSI_OVERSOLD:
            self.rsi_state = RSIState.OVERSOLD
            self.rsi_extremes['oversold'].append((datetime.now(), current))
        elif current >= RSI_OVERBOUGHT:
            self.rsi_state = RSIState.OVERBOUGHT
            self.rsi_extremes['overbought'].append((datetime.now(), current))
        elif RSI_NEUTRAL - RSI_EXIT_BUFFER <= current <= RSI_NEUTRAL + RSI_EXIT_BUFFER:
            self.rsi_state = RSIState.NEUTRAL
        elif prev < RSI_NEUTRAL < current:
            self.rsi_state = RSIState.REVERTING_UP
        elif prev > RSI_NEUTRAL > current:
            self.rsi_state = RSIState.REVERTING_DOWN
    
    def _check_rsi_extremes(self, market_data: pd.DataFrame, 
                           rsi_series: pd.Series) -> Optional[RSISignal]:
        """Check for RSI extreme conditions"""
        current_rsi = rsi_series.iloc[-1]
        current_price = market_data['close'].iloc[-1]
        
        # Check for oversold condition (buy calls)
        if current_rsi <= RSI_OVERSOLD and len(self.active_positions) < MAX_POSITIONS:
            # Check for bullish divergence
            divergence = self._check_divergence(market_data, rsi_series, 'bullish')
            
            # Check volume
            volume_confirmation = self._check_volume_confirmation(market_data, 'bullish')
            
            # Check support levels
            support_nearby = self._check_support_resistance(market_data, 'support')
            
            # Determine signal quality
            quality = self._assess_signal_quality(divergence, volume_confirmation, support_nearby)
            
            # Calculate expected reversion
            expected_reversion = self._calculate_expected_reversion(current_price, 'bullish')
            
            return RSISignal(
                rsi_value=current_rsi,
                rsi_state=RSIState.OVERSOLD,
                divergence=divergence,
                volume_confirmation=volume_confirmation,
                support_resistance_nearby=support_nearby,
                signal_quality=quality,
                entry_price=current_price,
                expected_reversion_price=expected_reversion,
                confidence=self._calculate_confidence(quality, current_rsi)
            )
        
        # Check for overbought condition (buy puts)
        elif current_rsi >= RSI_OVERBOUGHT and len(self.active_positions) < MAX_POSITIONS:
            # Check for bearish divergence
            divergence = self._check_divergence(market_data, rsi_series, 'bearish')
            
            # Check volume
            volume_confirmation = self._check_volume_confirmation(market_data, 'bearish')
            
            # Check resistance levels
            resistance_nearby = self._check_support_resistance(market_data, 'resistance')
            
            # Determine signal quality
            quality = self._assess_signal_quality(divergence, volume_confirmation, resistance_nearby)
            
            # Calculate expected reversion
            expected_reversion = self._calculate_expected_reversion(current_price, 'bearish')
            
            return RSISignal(
                rsi_value=current_rsi,
                rsi_state=RSIState.OVERBOUGHT,
                divergence=divergence,
                volume_confirmation=volume_confirmation,
                support_resistance_nearby=resistance_nearby,
                signal_quality=quality,
                entry_price=current_price,
                expected_reversion_price=expected_reversion,
                confidence=self._calculate_confidence(quality, current_rsi)
            )
        
        return None
    
    def _check_divergence(self, market_data: pd.DataFrame, rsi_series: pd.Series, 
                         divergence_type: str) -> bool:
        """Check for price/RSI divergence"""
        if len(market_data) < 10:
            return False
        
        # Look at last 10 bars
        prices = market_data['close'].iloc[-10:]
        rsi_values = rsi_series.iloc[-10:]
        
        if divergence_type == 'bullish':
            # Bullish divergence: price makes lower low, RSI makes higher low
            price_lows = prices.rolling(3).min()
            rsi_lows = rsi_values.rolling(3).min()
            
            if len(price_lows) > 5:
                recent_price_low = price_lows.iloc[-1]
                prev_price_low = price_lows.iloc[-5]
                recent_rsi_low = rsi_lows.iloc[-1]
                prev_rsi_low = rsi_lows.iloc[-5]
                
                if (recent_price_low < prev_price_low and 
                    recent_rsi_low > prev_rsi_low):
                    return True
        
        else:  # bearish
            # Bearish divergence: price makes higher high, RSI makes lower high
            price_highs = prices.rolling(3).max()
            rsi_highs = rsi_values.rolling(3).max()
            
            if len(price_highs) > 5:
                recent_price_high = price_highs.iloc[-1]
                prev_price_high = price_highs.iloc[-5]
                recent_rsi_high = rsi_highs.iloc[-1]
                prev_rsi_high = rsi_highs.iloc[-5]
                
                if (recent_price_high > prev_price_high and 
                    recent_rsi_high < prev_rsi_high):
                    return True
        
        return False
    
    def _check_volume_confirmation(self, market_data: pd.DataFrame, direction: str) -> bool:
        """Check if volume confirms the setup"""
        if len(market_data) < 20:
            return False
        
        current_volume = market_data['volume'].iloc[-1]
        avg_volume = market_data['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # For mean reversion, we want normal or lower volume (not breakout volume)
        return 0.7 <= volume_ratio <= 1.3
    
    def _check_support_resistance(self, market_data: pd.DataFrame, level_type: str) -> bool:
        """Check if near support or resistance"""
        current_price = market_data['close'].iloc[-1]
        
        # Simple support/resistance using recent highs/lows
        if level_type == 'support':
            recent_lows = market_data['low'].rolling(20).min().dropna()
            if len(recent_lows) > 0:
                support_level = recent_lows.iloc[-1]
                distance_pct = abs(current_price - support_level) / current_price
                return distance_pct < 0.005  # Within 0.5%
        
        else:  # resistance
            recent_highs = market_data['high'].rolling(20).max().dropna()
            if len(recent_highs) > 0:
                resistance_level = recent_highs.iloc[-1]
                distance_pct = abs(current_price - resistance_level) / current_price
                return distance_pct < 0.005  # Within 0.5%
        
        return False
    
    def _assess_signal_quality(self, divergence: bool, volume_conf: bool, 
                              sr_nearby: bool) -> SignalQuality:
        """Assess overall signal quality"""
        confirmations = sum([divergence, volume_conf, sr_nearby])
        
        if confirmations >= 2:
            return SignalQuality.PREMIUM
        elif confirmations >= 1:
            return SignalQuality.STANDARD
        else:
            return SignalQuality.WEAK
    
    def _calculate_expected_reversion(self, current_price: float, direction: str) -> float:
        """Calculate expected price after mean reversion"""
        # Use average reversion magnitude
        price_change_pct = self.avg_reversion_magnitude / 100 * 0.3  # RSI moves ~3x price
        
        if direction == 'bullish':
            return current_price * (1 + price_change_pct)
        else:
            return current_price * (1 - price_change_pct)
    
    def _calculate_confidence(self, quality: SignalQuality, rsi_value: float) -> float:
        """Calculate signal confidence"""
        # Base confidence on quality
        if quality == SignalQuality.PREMIUM:
            confidence = 0.8
        elif quality == SignalQuality.STANDARD:
            confidence = 0.6
        else:
            confidence = 0.4
        
        # Adjust for RSI extremity
        if rsi_value <= 20 or rsi_value >= 80:
            confidence += 0.1
        elif rsi_value <= 25 or rsi_value >= 75:
            confidence += 0.05
        
        return min(confidence, 0.95)
    
    def _validate_signal(self, signal: RSISignal, market_data: pd.DataFrame) -> bool:
        """Validate RSI signal"""
        # Check IV rank
        iv_rank = self.iv_calculator.get_current_iv_rank("SPY")
        if iv_rank < MIN_IV_RANK:
            self.logger.debug(f"IV rank too low: {iv_rank}")
            return False
        
        # Check signal quality
        if signal.signal_quality == SignalQuality.WEAK and signal.confidence < 0.5:
            return False
        
        # Check if we already have a position in this direction
        for pos_id, pos in self.active_positions.items():
            if (signal.rsi_state == RSIState.OVERSOLD and pos.direction == 'CALL') or \
               (signal.rsi_state == RSIState.OVERBOUGHT and pos.direction == 'PUT'):
                return False
        
        return True
    
    def _create_trading_signal(self, rsi_signal: RSISignal, 
                              market_data: pd.DataFrame) -> Optional[TradingSignal]:
        """Create trading signal from RSI signal"""
        try:
            # Determine option type
            if rsi_signal.rsi_state == RSIState.OVERSOLD:
                option_type = OptionType.CALL
                signal_type = SignalType.BUY
                direction = 'CALL'
                target_delta = DELTA_TARGET_CALL
            else:  # OVERBOUGHT
                option_type = OptionType.PUT
                signal_type = SignalType.BUY  # We're buying puts
                direction = 'PUT'
                target_delta = DELTA_TARGET_PUT
            
            # Find expiration
            expiration = self._find_optimal_expiration()
            if not expiration:
                return None
            
            # Create option contract
            strike = self._find_strike_by_delta(
                rsi_signal.entry_price,
                target_delta,
                option_type,
                expiration
            )
            
            if not strike:
                return None
            
            contract = OptionContract(
                symbol="SPY",
                strike=strike,
                expiration=expiration,
                right=option_type,
                multiplier=100,
                action="BUY"
            )
            
            # Determine signal strength
            if rsi_signal.signal_quality == SignalQuality.PREMIUM:
                strength = SignalStrength.VERY_STRONG
            elif rsi_signal.signal_quality == SignalQuality.STANDARD:
                strength = SignalStrength.STRONG
            else:
                strength = SignalStrength.MODERATE
            
            # Create signal
            signal = TradingSignal(
                signal_id=f"RSI_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                strategy_name=self.name,
                signal_type=signal_type,
                strength=strength,
                contracts=[contract],
                entry_price=rsi_signal.entry_price,
                stop_loss=None,  # Managed by position logic
                take_profit=rsi_signal.expected_reversion_price,
                position_size=1,  # Will be calculated
                confidence=rsi_signal.confidence,
                metadata={
                    'rsi_value': rsi_signal.rsi_value,
                    'rsi_state': rsi_signal.rsi_state.name,
                    'direction': direction,
                    'target_rsi': RSI_NEUTRAL,
                    'divergence': rsi_signal.divergence,
                    'signal_quality': rsi_signal.signal_quality.name,
                    'iv_rank': self.iv_calculator.get_current_iv_rank("SPY")
                }
            )
            
            self.logger.info(
                f"RSI mean reversion signal: {direction} at RSI {rsi_signal.rsi_value:.1f}, "
                f"target reversion to {RSI_NEUTRAL}"
            )
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error creating RSI signal: {e}")
            return None
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    def should_enter_position(self, signal: TradingSignal) -> bool:
        """Check if position should be entered"""
        # Check if strategy is still enabled
        if not self.health_monitor.is_strategy_enabled(self.name):
            return False
        
        # Verify time window
        current_time = datetime.now().time()
        if not (TRADING_START <= current_time <= TRADING_END):
            return False
        
        # Check position limits
        if len(self.active_positions) >= MAX_POSITIONS:
            return False
        
        return True
    
    def should_exit_position(self, position) -> bool:
        """Check if position should be exited"""
        position_id = position.position_id
        
        # Initialize tracking if needed
        if position_id not in self.active_positions:
            self.active_positions[position_id] = RSIPosition(
                entry_time=position.entry_time,
                entry_rsi=position.metadata.get('rsi_value', 50),
                direction=position.metadata.get('direction', 'UNKNOWN'),
                target_rsi=position.metadata.get('target_rsi', RSI_NEUTRAL),
                max_favorable_rsi=position.metadata.get('rsi_value', 50),
                time_in_position=timedelta()
            )
        
        rsi_pos = self.active_positions[position_id]
        
        # Update time in position
        rsi_pos.time_in_position = datetime.now() - rsi_pos.entry_time
        
        # Time-based exit
        if datetime.now().time() >= POSITION_CLOSE_TIME:
            self.logger.info("Closing position at end of day")
            return True
        
        # Time stop - exit if no reversion after N hours
        if rsi_pos.time_in_position >= timedelta(hours=TIME_STOP_HOURS):
            self.logger.info(f"Time stop triggered after {TIME_STOP_HOURS} hours")
            return True
        
        # Check RSI mean reversion
        if self._check_rsi_reversion(rsi_pos):
            self.logger.info(f"RSI mean reversion complete at {self.current_rsi:.1f}")
            return True
        
        # Profit target
        if self._check_profit_target(position):
            return True
        
        # Stop loss
        if self._check_stop_loss(position):
            return True
        
        return False
    
    def _check_rsi_reversion(self, rsi_pos: RSIPosition) -> bool:
        """Check if RSI has mean reverted"""
        # Update reversion progress
        if rsi_pos.direction == 'CALL':
            # For calls (oversold), we want RSI to increase
            rsi_pos.max_favorable_rsi = max(rsi_pos.max_favorable_rsi, self.current_rsi)
            rsi_pos.reversion_progress = (self.current_rsi - rsi_pos.entry_rsi) / \
                                        (RSI_NEUTRAL - rsi_pos.entry_rsi)
            
            # Exit if RSI reaches neutral zone
            return self.current_rsi >= (RSI_NEUTRAL - RSI_EXIT_BUFFER)
        
        else:  # PUT
            # For puts (overbought), we want RSI to decrease
            rsi_pos.max_favorable_rsi = min(rsi_pos.max_favorable_rsi, self.current_rsi)
            rsi_pos.reversion_progress = (rsi_pos.entry_rsi - self.current_rsi) / \
                                        (rsi_pos.entry_rsi - RSI_NEUTRAL)
            
            # Exit if RSI reaches neutral zone
            return self.current_rsi <= (RSI_NEUTRAL + RSI_EXIT_BUFFER)
    
    def _check_profit_target(self, position) -> bool:
        """Check if profit target reached"""
        # Calculate P&L percentage
        entry_cost = position.entry_price * position.position_size * 100
        pnl_percent = position.unrealized_pnl / entry_cost if entry_cost > 0 else 0
        
        if pnl_percent >= PROFIT_TARGET:
            self.logger.info(f"Profit target reached: {pnl_percent:.1%}")
            return True
        
        return False
    
    def _check_stop_loss(self, position) -> bool:
        """Check if stop loss hit"""
        # Calculate P&L percentage
        entry_cost = position.entry_price * position.position_size * 100
        pnl_percent = position.unrealized_pnl / entry_cost if entry_cost > 0 else 0
        
        if pnl_percent <= -STOP_LOSS:
            self.logger.info(f"Stop loss triggered: {pnl_percent:.1%}")
            return True
        
        return False
    
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size"""
        # Base size on confidence
        base_contracts = 2
        
        if signal.confidence >= 0.8:
            contracts = base_contracts * 2
        elif signal.confidence >= 0.6:
            contracts = int(base_contracts * 1.5)
        else:
            contracts = base_contracts
        
        # Risk-based limit
        max_risk = self.risk_profile.max_loss_per_trade
        # Assume max loss is premium paid
        estimated_premium = 2.0  # $2 per contract estimate
        max_contracts = int(max_risk / (estimated_premium * 100))
        
        return max(1, min(contracts, max_contracts, 10))
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _find_optimal_expiration(self) -> Optional[datetime]:
        """Find optimal expiration for mean reversion"""
        today = datetime.now().date()
        
        # Prefer 1 DTE, but allow up to 3 DTE
        for days in range(TARGET_DTE, MAX_DTE + 1):
            exp_date = today + timedelta(days=days)
            
            # Skip weekends
            if exp_date.weekday() < 5:
                return datetime.combine(exp_date, time(16, 0))
        
        return None
    
    def _find_strike_by_delta(self, spot: float, target_delta: float,
                             option_type: OptionType, expiration: datetime) -> Optional[float]:
        """Find strike for target delta"""
        # Simplified strike selection
        if option_type == OptionType.CALL:
            if target_delta >= 0.4:
                offset = 0  # ATM
            elif target_delta >= 0.3:
                offset = 1  # Slightly OTM
            else:
                offset = 2  # OTM
            
            strike = round(spot + offset, 0)
        
        else:  # PUT
            if abs(target_delta) >= 0.4:
                offset = 0  # ATM
            elif abs(target_delta) >= 0.3:
                offset = -1  # Slightly OTM
            else:
                offset = -2  # OTM
            
            strike = round(spot + offset, 0)
        
        return strike
    
    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================
    def on_position_closed(self, position, pnl: float) -> None:
        """Handle position closed event"""
        position_id = position.position_id
        
        # Update health monitor
        self.health_monitor.update_trade_result(self.name, pnl)
        
        # Track reversion metrics
        if position_id in self.active_positions:
            rsi_pos = self.active_positions[position_id]
            
            self.completed_trades.append({
                'entry_rsi': rsi_pos.entry_rsi,
                'exit_rsi': self.current_rsi,
                'direction': rsi_pos.direction,
                'time_in_position': rsi_pos.time_in_position,
                'reversion_progress': rsi_pos.reversion_progress,
                'pnl': pnl
            })
            
            # Update success metrics
            self._update_performance_metrics()
            
            # Remove from active positions
            del self.active_positions[position_id]
    
    def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics"""
        if not self.completed_trades:
            return
        
        # Calculate success rate
        successful_trades = [t for t in self.completed_trades if t['pnl'] > 0]
        self.reversion_success_rate = len(successful_trades) / len(self.completed_trades)
        
        # Calculate average reversion time
        reversion_times = [t['time_in_position'] for t in successful_trades 
                          if t['reversion_progress'] >= 0.8]
        if reversion_times:
            self.avg_reversion_time = sum(reversion_times, timedelta()) / len(reversion_times)
        
        # Calculate average reversion magnitude
        reversion_magnitudes = []
        for trade in successful_trades:
            if trade['direction'] == 'CALL':
                magnitude = trade['exit_rsi'] - trade['entry_rsi']
            else:
                magnitude = trade['entry_rsi'] - trade['exit_rsi']
            reversion_magnitudes.append(magnitude)
        
        if reversion_magnitudes:
            self.avg_reversion_magnitude = np.mean(reversion_magnitudes)
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        stats = super().get_performance()
        
        # Add RSI-specific stats
        stats.update({
            'current_rsi': self.current_rsi,
            'rsi_state': self.rsi_state.name,
            'active_positions': len(self.active_positions),
            'reversion_success_rate': self.reversion_success_rate,
            'avg_reversion_time': str(self.avg_reversion_time),
            'avg_reversion_magnitude': self.avg_reversion_magnitude,
            'completed_trades': len(self.completed_trades),
            'health_status': self.health_monitor.get_strategy_health(self.name)
        })
        
        return stats

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the strategy
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
    
    # Initialize
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=500
    )
    
    config = {
        'max_positions': 3,
        'position_size_pct': 0.02
    }
    
    # Create strategy
    strategy = RSIMeanReversionStrategy(event_manager, risk_profile, config)
    
    # Simulate RSI extremes
    print("RSI Mean Reversion Strategy Test")
    print("=" * 40)
    
    # Create sample data with RSI extremes
    dates = pd.date_range(start=datetime.now().replace(hour=11, minute=0), periods=100, freq='5min')
    
    # Create oversold then overbought pattern
    prices = np.zeros(100)
    # Start normal
    prices[:20] = 450 + np.random.randn(20) * 0.5
    # Drop to oversold
    prices[20:30] = 450 - np.linspace(0, 3, 10)
    # Revert up
    prices[30:50] = 447 + np.linspace(0, 4, 20)
    # Rise to overbought
    prices[50:70] = 451 + np.linspace(0, 3, 20)
    # Revert down
    prices[70:] = 454 - np.linspace(0, 4, 30)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices - 0.1,
        'high': prices + 0.2,
        'low': prices - 0.2,
        'close': prices,
        'volume': np.random.randint(500000, 1500000, 100)
    })
    
    # Process data and look for signals
    for i in range(RSI_PERIOD + 5, len(market_data)):
        data_slice = market_data.iloc[:i+1]
        signals = strategy.generate_signals(data_slice)
        
        if signals:
            print(f"\nTime: {dates[i].strftime('%H:%M')}")
            print(f"Price: ${prices[i]:.2f}")
            print(f"RSI: {strategy.current_rsi:.1f}")
            for signal in signals:
                print(f"Signal: Buy {signal.metadata['direction']}")
                print(f"Quality: {signal.metadata['signal_quality']}")
                print(f"Confidence: {signal.confidence:.1%}")
                print(f"Divergence: {signal.metadata['divergence']}")
    
    # Print final stats
    stats = strategy.get_strategy_stats()
    print(f"\nStrategy Stats:")
    print(f"Current RSI: {stats['current_rsi']:.1f}")
    print(f"RSI State: {stats['rsi_state']}")
    print(f"Success Rate: {stats['reversion_success_rate']:.1%}")
