#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD13_OpeningRangeBreakout.py
Group: D (Trading Strategies)
Purpose: Opening range breakout strategy

Description:
    This module implements an opening range breakout strategy that monitors
    the first 15-30 minutes of trading to establish a range, then trades
    breakouts from that range. The strategy focuses on Monday/Tuesday and
    uses tight trailing stops as recommended by the research.

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
from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF10_IVRankCalculator import get_iv_rank_calculator
from SpyderB_Broker.SpyderB06_ContractBuilder import OptionContract
from SpyderE_Risk.SpyderE03_StrategyHealthMonitor import get_strategy_health_monitor

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
OPENING_RANGE_MINUTES = 30  # First 30 minutes
MIN_RANGE_SIZE = 0.50      # Minimum $0.50 range
MAX_RANGE_SIZE = 3.00      # Maximum $3.00 range
BREAKOUT_CONFIRMATION_BARS = 2  # Bars to confirm breakout
TRAILING_STOP_PERCENT = 0.005   # 0.5% trailing stop
PROFIT_TARGET_RATIO = 2.0       # 2:1 reward/risk
MAX_DAILY_TRADES = 2           # Maximum trades per day

# Time windows
MARKET_OPEN = time(9, 30)
RANGE_END = time(10, 0)
TRADING_START = time(9, 45)    # Start trading at 9:45 AM
TRADING_END = time(15, 30)     # Stop new entries at 3:30 PM

# Option parameters
DELTA_TARGET = 0.40            # Target delta for options
MIN_VOLUME = 100               # Minimum option volume
MIN_IV_RANK = 30               # Minimum IV rank

# ==============================================================================
# ENUMS
# ==============================================================================
class BreakoutDirection(Enum):
    """Breakout direction"""
    BULLISH = auto()
    BEARISH = auto()
    NONE = auto()

class RangeState(Enum):
    """Opening range state"""
    FORMING = auto()
    ESTABLISHED = auto()
    BROKEN = auto()
    INVALID = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OpeningRange:
    """Opening range data"""
    high: float
    low: float
    range_size: float
    midpoint: float
    established_time: datetime
    volume: int
    state: RangeState
    bars_in_range: int = 0

@dataclass
class BreakoutSignal:
    """Breakout signal data"""
    direction: BreakoutDirection
    breakout_price: float
    entry_price: float
    stop_loss: float
    target: float
    volume_surge: float
    strength: float
    confirmed: bool = False
    confirmation_bars: int = 0

# ==============================================================================
# OPENING RANGE BREAKOUT STRATEGY
# ==============================================================================
class OpeningRangeBreakoutStrategy(BaseStrategy):
    """
    Opening range breakout strategy implementation.
    
    Strategy rules:
    - Monitor first 30 minutes to establish range
    - Trade breakouts after 9:45 AM
    - Use tight trailing stops
    - Focus on Monday/Tuesday
    - Maximum 2 trades per day
    """
    
    def __init__(self, event_manager, risk_profile, config):
        """Initialize opening range breakout strategy"""
        super().__init__("OpeningRangeBreakout", event_manager, risk_profile, config)
        
        # Components
        self.iv_calculator = get_iv_rank_calculator()
        self.health_monitor = get_strategy_health_monitor()
        
        # Register with health monitor
        self.health_monitor.register_strategy(self.name)
        
        # Range tracking
        self.current_range: Optional[OpeningRange] = None
        self.range_history: List[OpeningRange] = []
        self.pending_breakout: Optional[BreakoutSignal] = None
        
        # Daily tracking
        self.daily_trades = 0
        self.last_trade_date = None
        
        # Performance
        self.breakout_success_rate = 0.5
        self.avg_range_size = 1.0
        
        self.logger.info("OpeningRangeBreakout strategy initialized")
    
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """Generate opening range breakout signals"""
        signals = []
        
        # Check if strategy is enabled
        if not self.health_monitor.is_strategy_enabled(self.name):
            return signals
        
        current_time = datetime.now().time()
        current_date = datetime.now().date()
        
        # Reset daily counter
        if self.last_trade_date != current_date:
            self.daily_trades = 0
            self.last_trade_date = current_date
        
        # Check if Monday or Tuesday (preferred days)
        if datetime.now().weekday() not in [0, 1]:  # Monday=0, Tuesday=1
            return signals
        
        # Update or establish range
        if current_time <= RANGE_END:
            self._update_opening_range(market_data)
        
        # Check for breakouts after range established
        if (self.current_range and 
            self.current_range.state == RangeState.ESTABLISHED and
            TRADING_START <= current_time <= TRADING_END and
            self.daily_trades < MAX_DAILY_TRADES):
            
            # Check for breakout
            breakout = self._check_breakout(market_data)
            
            if breakout:
                # Confirm breakout
                if self._confirm_breakout(breakout, market_data):
                    signal = self._create_breakout_signal(breakout, market_data)
                    if signal:
                        signals.append(signal)
                        self.daily_trades += 1
        
        return signals
    
    def _update_opening_range(self, market_data: pd.DataFrame) -> None:
        """Update or establish opening range"""
        if len(market_data) < 1:
            return
        
        current_bar = market_data.iloc[-1]
        current_time = datetime.now()
        
        # Initialize range on first bar after market open
        if not self.current_range and current_time.time() >= MARKET_OPEN:
            self.current_range = OpeningRange(
                high=current_bar['high'],
                low=current_bar['low'],
                range_size=current_bar['high'] - current_bar['low'],
                midpoint=(current_bar['high'] + current_bar['low']) / 2,
                established_time=current_time,
                volume=current_bar['volume'],
                state=RangeState.FORMING
            )
            self.logger.info("Opening range formation started")
        
        # Update range
        elif self.current_range and self.current_range.state == RangeState.FORMING:
            self.current_range.high = max(self.current_range.high, current_bar['high'])
            self.current_range.low = min(self.current_range.low, current_bar['low'])
            self.current_range.range_size = self.current_range.high - self.current_range.low
            self.current_range.midpoint = (self.current_range.high + self.current_range.low) / 2
            self.current_range.volume += current_bar['volume']
            self.current_range.bars_in_range += 1
            
            # Check if range is established
            if current_time.time() >= RANGE_END:
                self._establish_range()
    
    def _establish_range(self) -> None:
        """Establish the opening range"""
        if not self.current_range:
            return
        
        # Validate range
        if MIN_RANGE_SIZE <= self.current_range.range_size <= MAX_RANGE_SIZE:
            self.current_range.state = RangeState.ESTABLISHED
            self.range_history.append(self.current_range)
            
            # Update average range size
            if len(self.range_history) > 0:
                self.avg_range_size = np.mean([r.range_size for r in self.range_history[-20:]])
            
            self.logger.info(
                f"Opening range established: ${self.current_range.low:.2f} - "
                f"${self.current_range.high:.2f} (${self.current_range.range_size:.2f})"
            )
        else:
            self.current_range.state = RangeState.INVALID
            self.logger.warning(
                f"Invalid range size: ${self.current_range.range_size:.2f}"
            )
    
    def _check_breakout(self, market_data: pd.DataFrame) -> Optional[BreakoutSignal]:
        """Check for range breakout"""
        if not self.current_range or len(market_data) < 2:
            return None
        
        current_bar = market_data.iloc[-1]
        prev_bar = market_data.iloc[-2]
        
        # Check for existing pending breakout
        if self.pending_breakout and not self.pending_breakout.confirmed:
            return self._update_pending_breakout(current_bar)
        
        # Check for new breakout
        # Bullish breakout
        if (current_bar['close'] > self.current_range.high and 
            prev_bar['close'] <= self.current_range.high):
            
            volume_surge = current_bar['volume'] / market_data['volume'].rolling(20).mean().iloc[-1]
            
            return BreakoutSignal(
                direction=BreakoutDirection.BULLISH,
                breakout_price=self.current_range.high,
                entry_price=current_bar['close'],
                stop_loss=self.current_range.midpoint,
                target=self.current_range.high + (self.current_range.range_size * PROFIT_TARGET_RATIO),
                volume_surge=volume_surge,
                strength=self._calculate_breakout_strength(current_bar, BreakoutDirection.BULLISH)
            )
        
        # Bearish breakout
        elif (current_bar['close'] < self.current_range.low and 
              prev_bar['close'] >= self.current_range.low):
            
            volume_surge = current_bar['volume'] / market_data['volume'].rolling(20).mean().iloc[-1]
            
            return BreakoutSignal(
                direction=BreakoutDirection.BEARISH,
                breakout_price=self.current_range.low,
                entry_price=current_bar['close'],
                stop_loss=self.current_range.midpoint,
                target=self.current_range.low - (self.current_range.range_size * PROFIT_TARGET_RATIO),
                volume_surge=volume_surge,
                strength=self._calculate_breakout_strength(current_bar, BreakoutDirection.BEARISH)
            )
        
        return None
    
    def _update_pending_breakout(self, current_bar: pd.Series) -> Optional[BreakoutSignal]:
        """Update pending breakout confirmation"""
        if not self.pending_breakout:
            return None
        
        # Check if still breaking out
        if self.pending_breakout.direction == BreakoutDirection.BULLISH:
            if current_bar['close'] > self.pending_breakout.breakout_price:
                self.pending_breakout.confirmation_bars += 1
            else:
                # Failed breakout
                self.pending_breakout = None
                return None
        else:  # Bearish
            if current_bar['close'] < self.pending_breakout.breakout_price:
                self.pending_breakout.confirmation_bars += 1
            else:
                # Failed breakout
                self.pending_breakout = None
                return None
        
        # Check if confirmed
        if self.pending_breakout.confirmation_bars >= BREAKOUT_CONFIRMATION_BARS:
            self.pending_breakout.confirmed = True
            self.pending_breakout.entry_price = current_bar['close']
            return self.pending_breakout
        
        return None
    
    def _confirm_breakout(self, breakout: BreakoutSignal, market_data: pd.DataFrame) -> bool:
        """Confirm breakout is valid"""
        # Store as pending if not yet confirmed
        if not breakout.confirmed:
            self.pending_breakout = breakout
            return False
        
        # Check volume surge
        if breakout.volume_surge < 1.5:  # Need 50% above average
            self.logger.debug("Insufficient volume for breakout")
            return False
        
        # Check IV rank
        iv_rank = self.iv_calculator.get_current_iv_rank("SPY")
        if iv_rank < MIN_IV_RANK:
            self.logger.debug(f"IV rank too low: {iv_rank}")
            return False
        
        # Check breakout strength
        if breakout.strength < 0.6:
            self.logger.debug("Breakout strength too weak")
            return False
        
        return True
    
    def _calculate_breakout_strength(self, bar: pd.Series, direction: BreakoutDirection) -> float:
        """Calculate breakout strength score"""
        strength = 0.5  # Base score
        
        if direction == BreakoutDirection.BULLISH:
            # How far above the range high
            breakout_distance = (bar['close'] - self.current_range.high) / self.current_range.range_size
            strength += min(breakout_distance * 0.3, 0.3)
            
            # Close near high of bar
            bar_range = bar['high'] - bar['low']
            if bar_range > 0:
                close_position = (bar['close'] - bar['low']) / bar_range
                strength += close_position * 0.2
        else:  # Bearish
            # How far below the range low
            breakout_distance = (self.current_range.low - bar['close']) / self.current_range.range_size
            strength += min(breakout_distance * 0.3, 0.3)
            
            # Close near low of bar
            bar_range = bar['high'] - bar['low']
            if bar_range > 0:
                close_position = (bar['high'] - bar['close']) / bar_range
                strength += close_position * 0.2
        
        return min(strength, 1.0)
    
    def _create_breakout_signal(self, breakout: BreakoutSignal, 
                               market_data: pd.DataFrame) -> Optional[TradingSignal]:
        """Create trading signal from breakout"""
        try:
            # Get IV rank
            iv_rank = self.iv_calculator.get_current_iv_rank("SPY")
            
            # Find suitable expiration (0-2 DTE for breakouts)
            expiration = self._find_optimal_expiration(0, 2)
            if not expiration:
                return None
            
            # Create option contracts based on direction
            if breakout.direction == BreakoutDirection.BULLISH:
                # Buy call spread
                contracts = self._create_call_spread(
                    breakout.entry_price,
                    expiration,
                    DELTA_TARGET
                )
                signal_type = SignalType.BUY
            else:
                # Buy put spread
                contracts = self._create_put_spread(
                    breakout.entry_price,
                    expiration,
                    DELTA_TARGET
                )
                signal_type = SignalType.SELL
            
            if not contracts:
                return None
            
            # Determine signal strength
            if breakout.strength > 0.8:
                strength = SignalStrength.VERY_STRONG
            elif breakout.strength > 0.7:
                strength = SignalStrength.STRONG
            elif breakout.strength > 0.6:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK
            
            # Create signal
            signal = TradingSignal(
                signal_id=f"ORB_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now(),
                strategy_name=self.name,
                signal_type=signal_type,
                strength=strength,
                contracts=contracts,
                entry_price=breakout.entry_price,
                stop_loss=breakout.stop_loss,
                take_profit=breakout.target,
                position_size=self._calculate_position_size(breakout),
                confidence=breakout.strength,
                metadata={
                    'breakout_direction': breakout.direction.name,
                    'range_high': self.current_range.high,
                    'range_low': self.current_range.low,
                    'range_size': self.current_range.range_size,
                    'volume_surge': breakout.volume_surge,
                    'iv_rank': iv_rank
                }
            )
            
            self.logger.info(
                f"Opening range breakout signal: {breakout.direction.name} at "
                f"${breakout.entry_price:.2f}, target ${breakout.target:.2f}"
            )
            
            return signal
            
        except Exception as e:
            self.logger.error(f"Error creating breakout signal: {e}")
            return None
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    def should_enter_position(self, signal: TradingSignal) -> bool:
        """Check if position should be entered"""
        # Check if strategy is still enabled
        if not self.health_monitor.is_strategy_enabled(self.name):
            return False
        
        # Verify we haven't exceeded daily limit
        if self.daily_trades >= MAX_DAILY_TRADES:
            return False
        
        # Verify time window
        current_time = datetime.now().time()
        if not (TRADING_START <= current_time <= TRADING_END):
            return False
        
        # Verify range hasn't been broken already
        if self.current_range and self.current_range.state == RangeState.BROKEN:
            return False
        
        return True
    
    def should_exit_position(self, position) -> bool:
        """Check if position should be exited"""
        # Time-based exit
        if datetime.now().time() >= time(15, 50):  # Exit by 3:50 PM
            return True
        
        # Check if trailing stop hit
        if self._check_trailing_stop(position):
            return True
        
        # Check if target reached
        if self._check_profit_target(position):
            return True
        
        # Check if initial stop hit
        pnl_percent = position.unrealized_pnl / (position.entry_price * position.position_size * 100)
        if pnl_percent <= -0.02:  # 2% stop loss
            return True
        
        return False
    
    def _check_trailing_stop(self, position) -> bool:
        """Check if trailing stop is hit"""
        # Get highest/lowest price since entry
        if position.metadata.get('breakout_direction') == 'BULLISH':
            # For bullish positions, trail from highest price
            highest = position.metadata.get('highest_price', position.entry_price)
            current_price = self.current_price
            
            # Update highest
            if current_price > highest:
                position.metadata['highest_price'] = current_price
                highest = current_price
            
            # Check trailing stop
            trailing_stop = highest * (1 - TRAILING_STOP_PERCENT)
            if current_price <= trailing_stop:
                return True
                
        else:  # Bearish
            # For bearish positions, trail from lowest price
            lowest = position.metadata.get('lowest_price', position.entry_price)
            current_price = self.current_price
            
            # Update lowest
            if current_price < lowest:
                position.metadata['lowest_price'] = current_price
                lowest = current_price
            
            # Check trailing stop
            trailing_stop = lowest * (1 + TRAILING_STOP_PERCENT)
            if current_price >= trailing_stop:
                return True
        
        return False
    
    def _check_profit_target(self, position) -> bool:
        """Check if profit target reached"""
        if not position.take_profit:
            return False
        
        if position.metadata.get('breakout_direction') == 'BULLISH':
            return self.current_price >= position.take_profit
        else:
            return self.current_price <= position.take_profit
    
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size"""
        # Base size on risk
        risk_per_contract = abs(signal.entry_price - signal.stop_loss) * 100
        max_risk = self.risk_profile.max_loss_per_trade
        
        contracts = int(max_risk / risk_per_contract)
        
        # Adjust based on signal strength
        if signal.strength == SignalStrength.VERY_STRONG:
            contracts = int(contracts * 1.2)
        elif signal.strength == SignalStrength.WEAK:
            contracts = int(contracts * 0.8)
        
        # Apply limits
        return max(1, min(contracts, 10))
    
    def _calculate_position_size(self, breakout: BreakoutSignal) -> int:
        """Calculate position size for breakout"""
        # Risk per contract
        risk_per_contract = abs(breakout.entry_price - breakout.stop_loss) * 100
        max_risk = self.risk_profile.max_loss_per_trade
        
        contracts = int(max_risk / risk_per_contract)
        
        # Adjust based on breakout strength
        if breakout.strength > 0.8:
            contracts = int(contracts * 1.2)
        elif breakout.strength < 0.6:
            contracts = int(contracts * 0.8)
        
        return max(1, min(contracts, 10))
    
    # ==========================================================================
    # OPTION CREATION
    # ==========================================================================
    def _find_optimal_expiration(self, min_dte: int, max_dte: int) -> Optional[datetime]:
        """Find optimal expiration date"""
        # For opening range breakout, prefer 0-2 DTE
        today = datetime.now().date()
        
        for days in range(min_dte, max_dte + 1):
            exp_date = today + timedelta(days=days)
            
            # Skip weekends
            if exp_date.weekday() < 5:  # Monday = 0, Friday = 4
                return datetime.combine(exp_date, time(16, 0))
        
        return None
    
    def _create_call_spread(self, spot_price: float, expiration: datetime, 
                           target_delta: float) -> Optional[List[OptionContract]]:
        """Create bull call spread"""
        # Find strikes
        long_strike = self._find_strike_by_delta(spot_price, target_delta, OptionType.CALL, expiration)
        short_strike = long_strike + 2.5  # $2.50 spread
        
        if not long_strike:
            return None
        
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
    
    def _create_put_spread(self, spot_price: float, expiration: datetime,
                          target_delta: float) -> Optional[List[OptionContract]]:
        """Create bear put spread"""
        # Find strikes
        long_strike = self._find_strike_by_delta(spot_price, -target_delta, OptionType.PUT, expiration)
        short_strike = long_strike - 2.5  # $2.50 spread
        
        if not long_strike:
            return None
        
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
    
    def _find_strike_by_delta(self, spot: float, target_delta: float, 
                             option_type: OptionType, expiration: datetime) -> Optional[float]:
        """Find strike price for target delta"""
        # Simplified - would use actual option chain
        # For calls: higher delta = lower strike
        # For puts: higher delta (less negative) = higher strike
        
        if option_type == OptionType.CALL:
            # Approximate strike for call delta
            if target_delta >= 0.4:
                offset = -1.0  # ITM
            elif target_delta >= 0.3:
                offset = 0.5   # Near ATM
            else:
                offset = 2.0   # OTM
            
            strike = round(spot + offset, 0)
            
        else:  # PUT
            # Approximate strike for put delta
            if abs(target_delta) >= 0.4:
                offset = 1.0   # ITM
            elif abs(target_delta) >= 0.3:
                offset = -0.5  # Near ATM
            else:
                offset = -2.0  # OTM
            
            strike = round(spot + offset, 0)
        
        return strike
    
    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================
    def on_position_closed(self, position, pnl: float) -> None:
        """Handle position closed event"""
        # Update health monitor
        self.health_monitor.update_trade_result(self.name, pnl)
        
        # Update success rate
        total_trades = len([p for p in self.performance.trade_history])
        if total_trades > 0:
            winning_trades = len([p for p in self.performance.trade_history if p['pnl'] > 0])
            self.breakout_success_rate = winning_trades / total_trades
        
        # Mark range as broken
        if self.current_range:
            self.current_range.state = RangeState.BROKEN
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        stats = super().get_performance()
        
        # Add breakout-specific stats
        stats.update({
            'breakout_success_rate': self.breakout_success_rate,
            'avg_range_size': self.avg_range_size,
            'current_range': {
                'high': self.current_range.high if self.current_range else None,
                'low': self.current_range.low if self.current_range else None,
                'size': self.current_range.range_size if self.current_range else None,
                'state': self.current_range.state.name if self.current_range else None
            },
            'daily_trades': self.daily_trades,
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
        'max_positions': 2,
        'position_size_pct': 0.02
    }
    
    # Create strategy
    strategy = OpeningRangeBreakoutStrategy(event_manager, risk_profile, config)
    
    # Simulate opening range
    print("Opening Range Breakout Strategy Test")
    print("=" * 40)
    
    # Create sample data with opening range
    dates = pd.date_range(start=datetime.now().replace(hour=9, minute=30), periods=100, freq='5min')
    
    # Create opening range pattern
    prices = np.zeros(100)
    # First 30 minutes - range formation
    prices[:6] = 450 + np.random.uniform(-0.5, 0.5, 6)  # Range bound
    # Breakout
    prices[6:] = 450.5 + np.cumsum(np.random.uniform(0, 0.2, 94))  # Upward breakout
    
    volumes = np.random.randint(500000, 2000000, 100)
    volumes[6] = 3000000  # Volume surge on breakout
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices - 0.1,
        'high': prices + 0.2,
        'low': prices - 0.2,
        'close': prices,
        'volume': volumes
    })
    
    # Process each bar
    for i in range(len(market_data)):
        data_slice = market_data.iloc[:i+1]
        signals = strategy.generate_signals(data_slice)
        
        if signals:
            print(f"\nTime: {dates[i].strftime('%H:%M')}")
            for signal in signals:
                print(f"Signal: {signal.signal_type}")
                print(f"Direction: {signal.metadata.get('breakout_direction')}")
                print(f"Entry: ${signal.entry_price:.2f}")
                print(f"Target: ${signal.take_profit:.2f}")
                print(f"Stop: ${signal.stop_loss:.2f}")
                print(f"Strength: {signal.strength.name}")
    
    # Print final stats
    stats = strategy.get_strategy_stats()
    print(f"\nStrategy Stats:")
    print(f"Daily Trades: {stats['daily_trades']}")
    if stats['current_range']['state']:
        print(f"Range State: {stats['current_range']['state']}")
        print(f"Range: ${stats['current_range']['low']:.2f} - ${stats['current_range']['high']:.2f}")
