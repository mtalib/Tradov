#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD15_MACrossover.py
Group: D (Trading Strategies)
Purpose: Moving average crossover strategy

Description:
    This module implements a moving average crossover strategy using 9 EMA and
    21 EMA on 15-minute charts. The strategy enters call spreads on bullish
    crossovers and put spreads on bearish crossovers, as recommended by the
    research findings.

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
from SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from SpyderB_Broker.SpyderB06_ContractBuilder import OptionContract
from SpyderE_Risk.SpyderE03_StrategyHealthMonitor import get_strategy_health_monitor

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Moving average parameters
FAST_EMA_PERIOD = 9
SLOW_EMA_PERIOD = 21
MIN_BARS_REQUIRED = 50

# Crossover parameters
CROSSOVER_CONFIRMATION_BARS = 2
MIN_CROSSOVER_DISTANCE = 0.10  # Minimum $0.10 between EMAs
MAX_BARS_SINCE_CROSS = 5  # Enter within 5 bars of crossover

# Trading windows
TRADING_START = time(9, 45)
TRADING_END = time(15, 30)
NO_NEW_TRADES_AFTER = time(15, 0)

# Option parameters
SPREAD_WIDTH = 2.5  # $2.50 spreads
TARGET_DTE_MIN = 1
TARGET_DTE_MAX = 5
MIN_IV_RANK = 30

# Position management
MAX_POSITIONS = 3
PROFIT_TARGET = 0.50  # 50% of max profit
STOP_LOSS = 1.00  # 100% of max profit (2:1)
TRAILING_STOP_ACTIVE_PCT = 0.30  # Activate trailing stop at 30% profit

# ==============================================================================
# ENUMS
# ==============================================================================
class CrossoverType(Enum):
    """Type of moving average crossover"""
    BULLISH = auto()
    BEARISH = auto()
    NONE = auto()

class TrendStrength(Enum):
    """Strength of the trend"""
    STRONG = auto()
    MODERATE = auto()
    WEAK = auto()

class MAState(Enum):
    """Moving average state"""
    BULLISH_ALIGNED = auto()  # Fast > Slow > Price trending up
    BEARISH_ALIGNED = auto()  # Fast < Slow < Price trending down
    CONVERGING = auto()
    DIVERGING = auto()
    NEUTRAL = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CrossoverSignal:
    """Moving average crossover signal"""
    crossover_type: CrossoverType
    crossover_price: float
    fast_ema_value: float
    slow_ema_value: float
    ema_distance: float
    trend_strength: TrendStrength
    volume_surge: bool
    momentum_confirmation: bool
    bars_since_cross: int
    confidence: float

@dataclass
class MAPosition:
    """Active MA crossover position tracking"""
    entry_time: datetime
    crossover_type: CrossoverType
    entry_ema_distance: float
    max_favorable_distance: float
    trend_continuation: bool
    bars_in_position: int = 0
    trailing_stop_active: bool = False
    trailing_stop_level: float = 0.0

# ==============================================================================
# MA CROSSOVER STRATEGY
# ==============================================================================
class MACrossoverStrategy(BaseStrategy):
    """
    Moving average crossover strategy implementation.
    
    Strategy rules:
    - 9 EMA / 21 EMA crossover on 15-minute chart
    - Call spreads on bullish crossover
    - Put spreads on bearish crossover
    - Enter within 5 bars of crossover
    - Use trailing stops after 30% profit
    """
    
    def __init__(self, event_manager, risk_profile, config):
        """Initialize MA crossover strategy"""
        super().__init__("MACrossover", event_manager, risk_profile, config)
        
        # Components
        self.indicators = TechnicalIndicators()
        self.iv_calculator = get_iv_rank_calculator()
        self.health_monitor = get_strategy_health_monitor()
        
        # Register with health monitor
        self.health_monitor.register_strategy(self.name)
        
        # MA tracking
        self.fast_ema = None
        self.slow_ema = None
        self.ma_state = MAState.NEUTRAL
        self.last_crossover = None
        self.crossover_history = []
        
        # Position tracking
        self.active_positions: Dict[str, MAPosition] = {}
        self.completed_trades = []
        
        # Performance metrics
        self.crossover_success_rate = 0.5
        self.avg_trend_duration = 20  # bars
        self.false_signal_rate = 0.2
        
        self.logger.info("MACrossover strategy initialized")
    
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """Generate MA crossover signals"""
        signals = []
        
        # Check if strategy is enabled
        if not self.health_monitor.is_strategy_enabled(self.name):
            return signals
        
        # Check time window
        current_time = datetime.now().time()
        if not (TRADING_START <= current_time <= TRADING_END):
            return signals
        
        # No new trades in last 30 minutes
        if current_time >= NO_NEW_TRADES_AFTER:
            return signals
        
        # Need enough data
        if len(market_data) < MIN_BARS_REQUIRED:
            return signals
        
        # Calculate EMAs
        self.fast_ema = market_data['close'].ewm(span=FAST_EMA_PERIOD, adjust=False).mean()
        self.slow_ema = market_data['close'].ewm(span=SLOW_EMA_PERIOD, adjust=False).mean()
        
        # Update MA state
        self._update_ma_state()
        
        # Check for crossover
        crossover_signal = self._check_crossover(market_data)
        
        if crossover_signal and self._validate_crossover(crossover_signal, market_data):
            trading_signal = self._create_trading_signal(crossover_signal, market_data)
            if trading_signal:
                signals.append(trading_signal)
        
        return signals
    
    def _update_ma_state(self) -> None:
        """Update moving average state"""
        if self.fast_ema is None or self.slow_ema is None:
            return
        
        fast_current = self.fast_ema.iloc[-1]
        slow_current = self.slow_ema.iloc[-1]
        fast_prev = self.fast_ema.iloc[-2]
        slow_prev = self.slow_ema.iloc[-2]
        
        # Calculate distances
        current_distance = fast_current - slow_current
        prev_distance = fast_prev - slow_prev
        
        # Determine state
        if current_distance > 0 and prev_distance > 0:
            if current_distance > prev_distance:
                self.ma_state = MAState.BULLISH_ALIGNED
            else:
                self.ma_state = MAState.CONVERGING
        elif current_distance < 0 and prev_distance < 0:
            if current_distance < prev_distance:
                self.ma_state = MAState.BEARISH_ALIGNED
            else:
                self.ma_state = MAState.CONVERGING
        else:
            self.ma_state = MAState.NEUTRAL
    
    def _check_crossover(self, market_data: pd.DataFrame) -> Optional[CrossoverSignal]:
        """Check for MA crossover"""
        if self.fast_ema is None or self.slow_ema is None or len(self.fast_ema) < 2:
            return None
        
        # Current and previous values
        fast_current = self.fast_ema.iloc[-1]
        slow_current = self.slow_ema.iloc[-1]
        fast_prev = self.fast_ema.iloc[-2]
        slow_prev = self.slow_ema.iloc[-2]
        
        # Check for crossover
        crossover_type = CrossoverType.NONE
        crossover_bar_index = -1
        
        # Bullish crossover (fast crosses above slow)
        if fast_prev <= slow_prev and fast_current > slow_current:
            crossover_type = CrossoverType.BULLISH
            crossover_bar_index = len(market_data) - 1
        
        # Bearish crossover (fast crosses below slow)
        elif fast_prev >= slow_prev and fast_current < slow_current:
            crossover_type = CrossoverType.BEARISH
            crossover_bar_index = len(market_data) - 1
        
        # Check recent crossover (within MAX_BARS_SINCE_CROSS)
        elif self.last_crossover:
            bars_since = len(market_data) - self.last_crossover['bar_index']
            if bars_since <= MAX_BARS_SINCE_CROSS:
                crossover_type = self.last_crossover['type']
                crossover_bar_index = self.last_crossover['bar_index']
        
        if crossover_type == CrossoverType.NONE:
            return None
        
        # Calculate crossover details
        ema_distance = abs(fast_current - slow_current)
        crossover_price = market_data['close'].iloc[crossover_bar_index]
        bars_since_cross = len(market_data) - crossover_bar_index
        
        # Check trend strength
        trend_strength = self._assess_trend_strength(market_data, crossover_type)
        
        # Check volume
        volume_surge = self._check_volume_surge(market_data)
        
        # Check momentum
        momentum_confirmation = self._check_momentum_confirmation(market_data, crossover_type)
        
        # Calculate confidence
        confidence = self._calculate_crossover_confidence(
            ema_distance, trend_strength, volume_surge, 
            momentum_confirmation, bars_since_cross
        )
        
        # Store crossover
        if bars_since_cross == 0:
            self.last_crossover = {
                'type': crossover_type,
                'bar_index': crossover_bar_index,
                'price': crossover_price
            }
            self.crossover_history.append(self.last_crossover)
        
        return CrossoverSignal(
            crossover_type=crossover_type,
            crossover_price=crossover_price,
            fast_ema_value=fast_current,
            slow_ema_value=slow_current,
            ema_distance=ema_distance,
            trend_strength=trend_strength,
            volume_surge=volume_surge,
            momentum_confirmation=momentum_confirmation,
            bars_since_cross=bars_since_cross,
            confidence=confidence
        )
    
    def _assess_trend_strength(self, market_data: pd.DataFrame, 
                              crossover_type: CrossoverType) -> TrendStrength:
        """Assess strength of the trend"""
        if len(market_data) < 20:
            return TrendStrength.WEAK
        
        # Calculate ADX for trend strength
        adx = self.indicators.adx(
            market_data['high'],
            market_data['low'],
            market_data['close'],
            period=14
        )
        
        if len(adx) == 0:
            return TrendStrength.WEAK
        
        current_adx = adx.iloc[-1]
        
        # Check price action
        price_ma = market_data['close'].rolling(10).mean()
        if len(price_ma) > 0:
            price_trend = (market_data['close'].iloc[-1] - price_ma.iloc[-1]) / price_ma.iloc[-1]
        else:
            price_trend = 0
        
        # Determine strength
        if current_adx > 30 and abs(price_trend) > 0.01:
            return TrendStrength.STRONG
        elif current_adx > 20 and abs(price_trend) > 0.005:
            return TrendStrength.MODERATE
        else:
            return TrendStrength.WEAK
    
    def _check_volume_surge(self, market_data: pd.DataFrame) -> bool:
        """Check for volume surge on crossover"""
        if len(market_data) < 20:
            return False
        
        current_volume = market_data['volume'].iloc[-1]
        avg_volume = market_data['volume'].rolling(20).mean().iloc[-1]
        
        return current_volume > avg_volume * 1.5
    
    def _check_momentum_confirmation(self, market_data: pd.DataFrame, 
                                   crossover_type: CrossoverType) -> bool:
        """Check if momentum confirms crossover"""
        if len(market_data) < 14:
            return False
        
        # Use RSI for momentum
        rsi = self.indicators.rsi(market_data['close'], period=14)
        if len(rsi) == 0:
            return False
        
        current_rsi = rsi.iloc[-1]
        
        if crossover_type == CrossoverType.BULLISH:
            return current_rsi > 50 and current_rsi < 70
        else:  # BEARISH
            return current_rsi < 50 and current_rsi > 30
    
    def _calculate_crossover_confidence(self, ema_distance: float, trend_strength: TrendStrength,
                                      volume_surge: bool, momentum_conf: bool, 
                                      bars_since_cross: int) -> float:
        """Calculate crossover signal confidence"""
        confidence = 0.5
        
        # EMA distance factor
        if ema_distance >= MIN_CROSSOVER_DISTANCE * 2:
            confidence += 0.2
        elif ema_distance >= MIN_CROSSOVER_DISTANCE:
            confidence += 0.1
        
        # Trend strength factor
        if trend_strength == TrendStrength.STRONG:
            confidence += 0.2
        elif trend_strength == TrendStrength.MODERATE:
            confidence += 0.1
        
        # Volume confirmation
        if volume_surge:
            confidence += 0.1
        
        # Momentum confirmation
        if momentum_conf:
            confidence += 0.1
        
        # Recency penalty
        if bars_since_cross > 2:
            confidence -= 0.05 * (bars_since_cross - 2)
        
        return max(0.3, min(0.95, confidence))
    
    def _validate_crossover(self, signal: CrossoverSignal, 
                           market_data: pd.DataFrame) -> bool:
        """Validate crossover signal"""
        # Check minimum EMA distance
        if signal.ema_distance < MIN_CROSSOVER_DISTANCE:
            return False
        
        # Check IV rank
        iv_rank = self.iv_calculator.get_current_iv_rank("SPY")
        if iv_rank < MIN_IV_RANK:
            self.logger.debug(f"IV rank too low: {iv_rank}")
            return False
        
        # Check if we already have a position in this direction
        for pos_id, pos in self.active_positions.items():
            if pos.crossover_type == signal.crossover_type:
                return False
        
        # Check confidence
        if signal.confidence < 0.5:
            return False
        
        # Position limit
        if len(self.active_positions) >= MAX_POSITIONS:
            return False
        
        return True
    
    def _create_trading_signal(self, crossover: CrossoverSignal,
                              market_data: pd.DataFrame) -> Optional[TradingSignal]:
        """Create trading signal from crossover"""
        try:
            current_price = market_data['close'].iloc[-1]
            
            # Find expiration
            expiration = self._find_optimal_expiration()
            if not expiration:
                return None
            
            # Create spread based on crossover type
            if crossover.crossover_type == CrossoverType.BULLISH:
                contracts = self._create_bull_call_spread(current_price, expiration)
                signal_type = SignalType.BUY
                direction = "BULLISH"
            else:  # BEARISH
                contracts = self._create_bear_put_spread(current_price, expiration)
                signal_type = SignalType.SELL
                direction = "BEARISH"
            
            if not contracts:
                return None
            
            # Calculate targets
            max_profit = SPREAD_WIDTH * 100  # Per contract
            stop_loss = current_price - (max_profit * STOP_LOSS / 100) if crossover.crossover_type == CrossoverType.BULLISH \
                       else current_price + (max_profit * STOP_LOSS / 100)
            
            take_profit = current_price + (max_profit * PROFIT_TARGET / 100) if crossover.crossover_type == CrossoverType.BULLISH \
                         else current_price - (max_profit * PROFIT_TARGET / 100)
            
            # Determine signal strength
            if crossover.trend_strength == TrendStrength.STRONG and crossover.confidence > 0.7:
                strength = SignalStrength.VERY_STRONG
            elif crossover.trend_strength == TrendStrength.MODERATE and crossover.confidence > 0.6:
                strength = SignalStrength.STRONG
            else:
                strength = SignalStrength.MODERATE
            
            # Create signal
            signal = TradingSignal(
                signal_id=f"MA_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                strategy_name=self.name,
                signal_type=signal_type,
                strength=strength,
                contracts=contracts,
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=1,  # Will be calculated
                confidence=crossover.confidence,
                metadata={
                    'crossover_type': crossover.crossover_type.name,
                    'direction': direction,
                    'fast_ema': crossover.fast_ema_value,
                    'slow_ema': crossover.slow_ema_value,
                    'ema_distance': crossover.ema_distance,
                    'trend_strength': crossover.trend_strength.name,
                    'volume_surge': crossover.volume_surge,
                    'momentum_confirmation': crossover.momentum_confirmation,
                    'bars_since_cross': crossover.bars_since_cross,
                    'iv_rank': self.iv_calculator.get_current_iv_rank("SPY")
                }
            )
            
            self.logger.info(
                f"MA crossover signal: {direction} crossover, "
                f"9EMA={crossover.fast_ema_value:.2f}, 21EMA={crossover.slow_ema_value:.2f}"
            )
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error creating MA crossover signal: {e}")
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
        if not (TRADING_START <= current_time < NO_NEW_TRADES_AFTER):
            return False
        
        # Verify crossover is still valid
        if self.fast_ema is None or self.slow_ema is None:
            return False
        
        fast_current = self.fast_ema.iloc[-1]
        slow_current = self.slow_ema.iloc[-1]
        
        if signal.metadata['crossover_type'] == 'BULLISH':
            if fast_current <= slow_current:  # Crossover invalidated
                return False
        else:  # BEARISH
            if fast_current >= slow_current:  # Crossover invalidated
                return False
        
        return True
    
    def should_exit_position(self, position) -> bool:
        """Check if position should be exited"""
        position_id = position.position_id
        
        # Initialize tracking if needed
        if position_id not in self.active_positions:
            self.active_positions[position_id] = MAPosition(
                entry_time=position.entry_time,
                crossover_type=CrossoverType[position.metadata.get('crossover_type', 'NONE')],
                entry_ema_distance=position.metadata.get('ema_distance', 0),
                max_favorable_distance=position.metadata.get('ema_distance', 0),
                trend_continuation=True
            )
        
        ma_pos = self.active_positions[position_id]
        ma_pos.bars_in_position += 1
        
        # Time-based exit
        if datetime.now().time() >= time(15, 45):
            self.logger.info("Closing position near market close")
            return True
        
        # Check opposite crossover (trend reversal)
        if self._check_opposite_crossover(ma_pos):
            self.logger.info("Opposite crossover detected - exiting position")
            return True
        
        # Check trailing stop
        if self._check_trailing_stop(position, ma_pos):
            self.logger.info("Trailing stop triggered")
            return True
        
        # Check profit target
        if self._check_profit_target(position):
            return True
        
        # Check stop loss
        if self._check_stop_loss(position):
            return True
        
        # Check if trend has stalled
        if self._check_trend_stall(ma_pos):
            self.logger.info("Trend stalled - exiting position")
            return True
        
        return False
    
    def _check_opposite_crossover(self, ma_pos: MAPosition) -> bool:
        """Check if opposite crossover occurred"""
        if self.fast_ema is None or self.slow_ema is None:
            return False
        
        fast_current = self.fast_ema.iloc[-1]
        slow_current = self.slow_ema.iloc[-1]
        
        if ma_pos.crossover_type == CrossoverType.BULLISH:
            # Check for bearish crossover
            return fast_current < slow_current
        else:  # BEARISH position
            # Check for bullish crossover
            return fast_current > slow_current
    
    def _check_trailing_stop(self, position, ma_pos: MAPosition) -> bool:
        """Check and update trailing stop"""
        # Calculate current P&L
        entry_cost = position.entry_price * position.position_size * 100
        pnl_percent = position.unrealized_pnl / entry_cost if entry_cost > 0 else 0
        
        # Activate trailing stop at 30% profit
        if pnl_percent >= TRAILING_STOP_ACTIVE_PCT and not ma_pos.trailing_stop_active:
            ma_pos.trailing_stop_active = True
            ma_pos.trailing_stop_level = self.current_price * 0.995  # 0.5% trailing
            self.logger.info(f"Trailing stop activated at ${ma_pos.trailing_stop_level:.2f}")
        
        # Update trailing stop
        if ma_pos.trailing_stop_active:
            if ma_pos.crossover_type == CrossoverType.BULLISH:
                # For bullish positions, trail upward
                ma_pos.trailing_stop_level = max(
                    ma_pos.trailing_stop_level,
                    self.current_price * 0.995
                )
                # Check if hit
                if self.current_price <= ma_pos.trailing_stop_level:
                    return True
            else:  # BEARISH
                # For bearish positions, trail downward
                ma_pos.trailing_stop_level = min(
                    ma_pos.trailing_stop_level,
                    self.current_price * 1.005
                )
                # Check if hit
                if self.current_price >= ma_pos.trailing_stop_level:
                    return True
        
        return False
    
    def _check_profit_target(self, position) -> bool:
        """Check if profit target reached"""
        entry_cost = position.entry_price * position.position_size * 100
        pnl_percent = position.unrealized_pnl / entry_cost if entry_cost > 0 else 0
        
        if pnl_percent >= PROFIT_TARGET:
            self.logger.info(f"Profit target reached: {pnl_percent:.1%}")
            return True
        
        return False
    
    def _check_stop_loss(self, position) -> bool:
        """Check if stop loss hit"""
        entry_cost = position.entry_price * position.position_size * 100
        pnl_percent = position.unrealized_pnl / entry_cost if entry_cost > 0 else 0
        
        if pnl_percent <= -STOP_LOSS:
            self.logger.info(f"Stop loss triggered: {pnl_percent:.1%}")
            return True
        
        return False
    
    def _check_trend_stall(self, ma_pos: MAPosition) -> bool:
        """Check if trend has stalled"""
        if self.fast_ema is None or self.slow_ema is None:
            return False
        
        # Update max favorable distance
        current_distance = abs(self.fast_ema.iloc[-1] - self.slow_ema.iloc[-1])
        ma_pos.max_favorable_distance = max(ma_pos.max_favorable_distance, current_distance)
        
        # Check if EMAs are converging significantly
        convergence_ratio = current_distance / ma_pos.max_favorable_distance if ma_pos.max_favorable_distance > 0 else 1
        
        # Exit if EMAs have converged more than 50%
        if convergence_ratio < 0.5 and ma_pos.bars_in_position > 10:
            return True
        
        return False
    
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size"""
        # Base size on signal strength and confidence
        base_contracts = 2
        
        if signal.strength == SignalStrength.VERY_STRONG:
            contracts = base_contracts * 2
        elif signal.strength == SignalStrength.STRONG:
            contracts = int(base_contracts * 1.5)
        else:
            contracts = base_contracts
        
        # Adjust for confidence
        if signal.confidence >= 0.8:
            contracts = int(contracts * 1.2)
        elif signal.confidence < 0.6:
            contracts = int(contracts * 0.8)
        
        # Risk limit
        max_risk = self.risk_profile.max_loss_per_trade
        max_loss_per_spread = SPREAD_WIDTH * 100  # Max loss per spread
        max_contracts = int(max_risk / max_loss_per_spread)
        
        return max(1, min(contracts, max_contracts, 10))
    
    # ==========================================================================
    # OPTION CREATION
    # ==========================================================================
    def _find_optimal_expiration(self) -> Optional[datetime]:
        """Find optimal expiration for spreads"""
        today = datetime.now().date()
        
        # Prefer 2-5 DTE for crossover trades
        for days in range(TARGET_DTE_MIN, TARGET_DTE_MAX + 1):
            exp_date = today + timedelta(days=days)
            
            # Skip weekends
            if exp_date.weekday() < 5:
                return datetime.combine(exp_date, time(16, 0))
        
        return None
    
    def _create_bull_call_spread(self, spot_price: float, 
                                expiration: datetime) -> Optional[List[OptionContract]]:
        """Create bull call spread"""
        # ATM long call, OTM short call
        long_strike = round(spot_price)
        short_strike = long_strike + SPREAD_WIDTH
        
        contracts = [
            OptionContract(
                symbol="SPY",
                strike=long_strike,
                expiration=expiration,
                right=OptionType.CALL,
                multiplier=100,
                action="BUY"
            ),
            OptionContract(
                symbol="SPY",
                strike=short_strike,
                expiration=expiration,
                right=OptionType.CALL,
                multiplier=100,
                action="SELL"
            )
        ]
        
        return contracts
    
    def _create_bear_put_spread(self, spot_price: float,
                               expiration: datetime) -> Optional[List[OptionContract]]:
        """Create bear put spread"""
        # ATM long put, OTM short put
        long_strike = round(spot_price)
        short_strike = long_strike - SPREAD_WIDTH
        
        contracts = [
            OptionContract(
                symbol="SPY",
                strike=long_strike,
                expiration=expiration,
                right=OptionType.PUT,
                multiplier=100,
                action="BUY"
            ),
            OptionContract(
                symbol="SPY",
                strike=short_strike,
                expiration=expiration,
                right=OptionType.PUT,
                multiplier=100,
                action="SELL"
            )
        ]
        
        return contracts
    
    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================
    def on_position_closed(self, position, pnl: float) -> None:
        """Handle position closed event"""
        position_id = position.position_id
        
        # Update health monitor
        self.health_monitor.update_trade_result(self.name, pnl)
        
        # Track crossover performance
        if position_id in self.active_positions:
            ma_pos = self.active_positions[position_id]
            
            self.completed_trades.append({
                'crossover_type': ma_pos.crossover_type.name,
                'entry_ema_distance': ma_pos.entry_ema_distance,
                'max_favorable_distance': ma_pos.max_favorable_distance,
                'bars_in_position': ma_pos.bars_in_position,
                'trailing_stop_used': ma_pos.trailing_stop_active,
                'pnl': pnl
            })
            
            # Update performance metrics
            self._update_performance_metrics()
            
            # Remove from active positions
            del self.active_positions[position_id]
    
    def _update_performance_metrics(self) -> None:
        """Update strategy performance metrics"""
        if not self.completed_trades:
            return
        
        # Calculate success rate
        successful_trades = [t for t in self.completed_trades if t['pnl'] > 0]
        self.crossover_success_rate = len(successful_trades) / len(self.completed_trades)
        
        # Calculate average trend duration
        trend_durations = [t['bars_in_position'] for t in successful_trades]
        if trend_durations:
            self.avg_trend_duration = np.mean(trend_durations)
        
        # Calculate false signal rate
        quick_exits = [t for t in self.completed_trades if t['bars_in_position'] < 5]
        self.false_signal_rate = len(quick_exits) / len(self.completed_trades) if self.completed_trades else 0
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        stats = super().get_performance()
        
        # Add MA-specific stats
        stats.update({
            'ma_state': self.ma_state.name if self.ma_state else 'UNKNOWN',
            'fast_ema': self.fast_ema.iloc[-1] if self.fast_ema is not None and len(self.fast_ema) > 0 else None,
            'slow_ema': self.slow_ema.iloc[-1] if self.slow_ema is not None and len(self.slow_ema) > 0 else None,
            'active_positions': len(self.active_positions),
            'crossover_success_rate': self.crossover_success_rate,
            'avg_trend_duration_bars': self.avg_trend_duration,
            'false_signal_rate': self.false_signal_rate,
            'completed_trades': len(self.completed_trades),
            'last_crossover': self.last_crossover,
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
    strategy = MACrossoverStrategy(event_manager, risk_profile, config)
    
    # Simulate MA crossover
    print("MA Crossover Strategy Test")
    print("=" * 40)
    
    # Create sample data with crossover pattern
    dates = pd.date_range(start=datetime.now().replace(hour=10, minute=0), periods=100, freq='15min')
    
    # Create crossover pattern
    t = np.linspace(0, 4*np.pi, 100)
    
    # Fast EMA oscillates more
    fast_pattern = 450 + 2 * np.sin(t * 1.5)
    # Slow EMA oscillates less
    slow_pattern = 450 + 1.5 * np.sin(t)
    
    # Add some noise
    prices = (fast_pattern + slow_pattern) / 2 + np.random.randn(100) * 0.3
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices - 0.1,
        'high': prices + 0.3,
        'low': prices - 0.3,
        'close': prices,
        'volume': np.random.randint(500000, 1500000, 100)
    })
    
    # Add volume surge at crossovers
    for i in range(1, len(market_data)):
        if i >= SLOW_EMA_PERIOD:
            fast_ema = market_data['close'].iloc[:i+1].ewm(span=FAST_EMA_PERIOD, adjust=False).mean()
            slow_ema = market_data['close'].iloc[:i+1].ewm(span=SLOW_EMA_PERIOD, adjust=False).mean()
            
            if len(fast_ema) >= 2 and len(slow_ema) >= 2:
                # Check for crossover
                if ((fast_ema.iloc[-2] <= slow_ema.iloc[-2] and fast_ema.iloc[-1] > slow_ema.iloc[-1]) or
                    (fast_ema.iloc[-2] >= slow_ema.iloc[-2] and fast_ema.iloc[-1] < slow_ema.iloc[-1])):
                    market_data.loc[i, 'volume'] *= 2  # Volume surge
    
    # Process data
    for i in range(MIN_BARS_REQUIRED, len(market_data)):
        data_slice = market_data.iloc[:i+1]
        signals = strategy.generate_signals(data_slice)
        
        if signals:
            print(f"\nTime: {dates[i].strftime('%H:%M')}")
            print(f"Price: ${prices[i]:.2f}")
            if strategy.fast_ema is not None and strategy.slow_ema is not None:
                print(f"9 EMA: ${strategy.fast_ema.iloc[-1]:.2f}")
                print(f"21 EMA: ${strategy.slow_ema.iloc[-1]:.2f}")
            for signal in signals:
                print(f"Signal: {signal.metadata['direction']} crossover")
                print(f"Trend Strength: {signal.metadata['trend_strength']}")
                print(f"Confidence: {signal.confidence:.1%}")
                print(f"Volume Surge: {signal.metadata['volume_surge']}")
    
    # Print final stats
    stats = strategy.get_strategy_stats()
    print(f"\nStrategy Stats:")
    print(f"MA State: {stats['ma_state']}")
    print(f"Success Rate: {stats['crossover_success_rate']:.1%}")
    print(f"Avg Trend Duration: {stats['avg_trend_duration_bars']:.1f} bars")
    print(f"False Signal Rate: {stats['false_signal_rate']:.1%}")
