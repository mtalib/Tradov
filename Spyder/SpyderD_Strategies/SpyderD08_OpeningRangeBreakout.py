#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD08_OpeningRangeBreakout.py
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
from datetime import datetime, time, timedelta
from typing import Any
from dataclasses import dataclass
from enum import Enum, auto
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy, TradingSignal, SignalType, SignalStrength,
    StrategyPosition, EventManager, RiskProfile, Event, EventType
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import SPY_CONTRACT_MULTIPLIER
from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from Spyder.SpyderC_MarketData.SpyderC05_VolumeProfile import VolumeProfileAnalyzer
from Spyder.SpyderF_Analysis.SpyderF02_PriceAction import PriceActionAnalyzer

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Range formation parameters
RANGE_START = time(9, 30)      # Market open
RANGE_END_15 = time(9, 45)     # 15-minute range
RANGE_END_30 = time(10, 0)     # 30-minute range
TRADING_START = time(9, 45)    # Start trading after range
TRADING_END = time(15, 30)     # Stop new entries

# Breakout parameters
MIN_RANGE_SIZE = 0.50          # Minimum $0.50 range
MAX_RANGE_SIZE = 3.00          # Maximum $3 range
BREAKOUT_BUFFER = 0.10         # $0.10 above/below range
VOLUME_SURGE_RATIO = 1.5       # 50% volume increase on breakout
FALSE_BREAKOUT_PULLBACK = 0.15 # 15% pullback = false breakout

# Risk parameters
STOP_LOSS_ATR_MULTIPLE = 1.5   # Stop loss at 1.5x ATR
TRAILING_STOP_PERCENT = 0.005  # 0.5% trailing stop
PROFIT_TARGET_RATIO = 2.0      # 2:1 risk/reward
MAX_DAILY_TRADES = 2           # Maximum trades per day

# Option parameters
OPTION_DELTA_CALL = 0.40       # Delta for call options
OPTION_DELTA_PUT = -0.40       # Delta for put options
MIN_OPTION_VOLUME = 100        # Minimum option volume
MAX_OPTION_SPREAD = 0.10       # Maximum bid-ask spread

# Days of week (0=Monday, 4=Friday)
PREFERRED_DAYS = [0, 1]        # Monday and Tuesday

# ==============================================================================
# ENUMS
# ==============================================================================
class RangeState(Enum):
    """Opening range state"""
    FORMING = auto()
    ESTABLISHED = auto()
    BROKEN = auto()
    INVALID = auto()

class BreakoutType(Enum):
    """Types of breakouts"""
    BULLISH = auto()
    BEARISH = auto()
    FALSE = auto()

class BreakoutQuality(Enum):
    """Breakout quality assessment"""
    STRONG = auto()
    MODERATE = auto()
    WEAK = auto()
    FALSE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OpeningRange:
    """Opening range data"""
    date: datetime
    range_start: time
    range_end: time
    high: float
    low: float
    open_price: float
    close_price: float
    volume: int
    vwap: float
    range_size: float
    state: RangeState

    # Volume profile within range
    volume_at_high: int = 0
    volume_at_low: int = 0
    poc: float = 0.0  # Point of Control

    # Pre-market levels
    pre_market_high: float = 0.0
    pre_market_low: float = 0.0
    gap_size: float = 0.0

    @property
    def midpoint(self) -> float:
        """Range midpoint"""
        return (self.high + self.low) / 2

    @property
    def is_valid(self) -> bool:
        """Check if range is valid for trading"""
        return (MIN_RANGE_SIZE <= self.range_size <= MAX_RANGE_SIZE and
                self.state == RangeState.ESTABLISHED)

@dataclass
class BreakoutSignal:
    """Breakout signal data"""
    signal_id: str
    timestamp: datetime
    breakout_type: BreakoutType
    breakout_price: float
    range_reference: OpeningRange
    volume_surge: float  # Volume relative to average
    momentum: float
    quality: BreakoutQuality

    # Entry levels
    entry_price: float
    stop_loss: float
    initial_target: float

    # Option setup
    option_type: str  # 'call' or 'put'
    strike: float
    expiry: datetime
    delta: float

    # Validation
    false_breakout_risk: float  # 0-1 scale
    confidence: float

@dataclass
class BreakoutPosition:
    """Active breakout position - FIXED field ordering"""
    # Required fields (no defaults) MUST come first
    position_id: str
    breakout_signal: BreakoutSignal
    entry_time: datetime
    option_contracts: int
    entry_price: float
    current_stop: float  # MOVED: This field without default must come before fields with defaults

    # Optional fields (with defaults) come after required fields
    current_price: float = 0.0

    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0

    # Risk management
    trailing_stop_active: bool = False
    highest_price: float = 0.0  # For trailing stop
    lowest_price: float = 0.0   # For trailing stop

    # Exit tracking
    exit_time: datetime | None = None
    exit_reason: str | None = None
    bars_in_trade: int = 0

# ==============================================================================
# OPENING RANGE BREAKOUT STRATEGY CLASS
# ==============================================================================
class OpeningRangeBreakoutStrategy(BaseStrategy):
    """
    Opening range breakout strategy implementation.

    Monitors the first 15-30 minutes to establish a range, then trades
    breakouts with volume confirmation and false breakout detection.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any]):
        """Initialize opening range breakout strategy"""
        super().__init__("OpeningRangeBreakout", event_manager, risk_profile, config)

        # Components
        self.tech_indicators = TechnicalIndicators()
        self.volume_profile = VolumeProfileAnalyzer()
        self.price_action = PriceActionAnalyzer()

        # Configuration
        self.range_minutes = config.get('range_minutes', 30)  # 15 or 30 minute range
        self.use_volume_profile = config.get('use_volume_profile', True)
        self.enable_pre_market = config.get('enable_pre_market', True)
        self.max_daily_trades = config.get('max_daily_trades', MAX_DAILY_TRADES)

        # Range tracking
        self.current_range: OpeningRange | None = None
        self.range_history: list[OpeningRange] = []
        self.pending_breakout: BreakoutSignal | None = None

        # Position tracking
        self.active_breakouts: dict[str, BreakoutPosition] = {}
        self.daily_trades = 0
        self.last_trade_date: datetime | None = None

        # Pre-market data
        self.pre_market_data: dict[str, Any] = {}

        # Performance tracking
        self.breakout_stats = {
            'total_breakouts': 0,
            'successful_breakouts': 0,
            'false_breakouts': 0,
            'avg_range_size': 0.0,
            'avg_breakout_move': 0.0,
            'monday_trades': 0,
            'tuesday_trades': 0,
            'other_day_trades': 0
        }

        self.logger.info("OpeningRangeBreakout strategy initialized with %smin range", self.range_minutes)

    # ==========================================================================
    # REQUIRED ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate opening range breakout signals"""
        signals = []

        try:
            current_time = datetime.now().time()
            current_date = datetime.now().date()

            # Reset daily counter
            if self.last_trade_date != current_date:
                self.daily_trades = 0
                self.last_trade_date = current_date
                self.current_range = None

            # Check if preferred trading day
            if datetime.now().weekday() not in PREFERRED_DAYS:
                self.logger.debug("Not a preferred trading day")
                # Still track range but reduce position size

            # Check daily trade limit
            if self.daily_trades >= self.max_daily_trades:
                return signals

            # Collect pre-market data if enabled
            if self.enable_pre_market and current_time < RANGE_START:
                self._collect_pre_market_data(market_data)

            # Update or establish range
            if RANGE_START <= current_time <= self._get_range_end():
                self._update_opening_range(market_data)

            # Check for breakouts after range established
            if (self.current_range and
                self.current_range.is_valid and
                TRADING_START <= current_time <= TRADING_END):

                breakout = self._check_for_breakout(market_data)
                if breakout:
                    signal = self._create_breakout_signal(breakout, market_data)
                    if signal:
                        signals.append(signal)

            # Update existing positions
            self._update_positions(market_data)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'market_data_shape': market_data.shape
            })

        return signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate breakout signal"""
        try:
            # Check signal validity
            if not signal.is_valid():
                return False

            # Check breakout data
            breakout_data = signal.metadata.get('breakout_data')
            if not breakout_data:
                return False

            # Validate breakout quality
            if breakout_data['quality'] == BreakoutQuality.FALSE.name:
                return False

            # Check false breakout risk
            if breakout_data['false_breakout_risk'] > 0.7:
                return False

            # Check volume confirmation
            if breakout_data['volume_surge'] < VOLUME_SURGE_RATIO:
                return False

            # Validate option setup
            return not breakout_data['option_spread'] > MAX_OPTION_SPREAD

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'validate_signal',
                'signal_id': signal.signal_id
            })
            return False

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size for breakout trade"""
        try:
            # Base position size
            account_value = self.risk_profile.account_size
            risk_amount = account_value * 0.01  # 1% risk per trade

            # Get stop loss distance
            breakout_data = signal.metadata.get('breakout_data', {})
            stop_distance = abs(breakout_data['entry_price'] - breakout_data['stop_loss'])

            # Calculate contracts
            contracts = int(risk_amount / (stop_distance * SPY_CONTRACT_MULTIPLIER))

            # Adjust for day of week
            if datetime.now().weekday() not in PREFERRED_DAYS:
                contracts = max(1, contracts // 2)

            # Adjust for signal strength
            if signal.strength == SignalStrength.WEAK:
                contracts = max(1, contracts // 2)
            elif signal.strength == SignalStrength.VERY_STRONG:
                contracts = min(10, int(contracts * 1.5))

            # Limit position size
            contracts = max(1, min(contracts, 10))

            return contracts

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_position_size',
                'signal_id': signal.signal_id
            })
            return 1

    def should_exit_position(self, position: StrategyPosition,
                           market_data: pd.DataFrame) -> tuple[bool, str]:
        """Determine if breakout position should be exited"""
        try:
            # Get breakout position
            breakout_pos = self.active_breakouts.get(position.position_id)
            if not breakout_pos:
                return False, ""

            current_price = market_data['close'].iloc[-1]

            # Update position metrics
            self._update_breakout_position(breakout_pos, current_price)

            # Check stop loss
            if breakout_pos.breakout_signal.breakout_type == BreakoutType.BULLISH:
                if current_price <= breakout_pos.current_stop:
                    return True, "Stop loss hit"
            else:  # BEARISH
                if current_price >= breakout_pos.current_stop:
                    return True, "Stop loss hit"

            # Check profit target
            if breakout_pos.unrealized_pnl >= breakout_pos.max_profit * 0.9:
                return True, "Profit target reached"

            # Check for false breakout
            if self._is_false_breakout(breakout_pos, market_data):
                return True, "False breakout detected"

            # Check time-based exit
            if breakout_pos.bars_in_trade > 30:  # 2.5 hours at 5min bars
                if breakout_pos.unrealized_pnl > 0:
                    return True, "Time-based exit with profit"

            # Check end of day
            if datetime.now().time() >= time(15, 45):
                return True, "End of day exit"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'should_exit_position',
                'position_id': position.position_id
            })
            return False, ""

    # ==========================================================================
    # RANGE FORMATION METHODS
    # ==========================================================================

    def _get_range_end(self) -> time:
        """Get range end time based on configuration"""
        if self.range_minutes == 15:
            return RANGE_END_15
        else:
            return RANGE_END_30

    def _collect_pre_market_data(self, market_data: pd.DataFrame) -> None:
        """Collect pre-market high/low data"""
        try:
            # Get pre-market data (simplified - would use actual pre-market feed)
            pre_market_high = market_data['high'].max()
            pre_market_low = market_data['low'].min()

            self.pre_market_data = {
                'high': pre_market_high,
                'low': pre_market_low,
                'last': market_data['close'].iloc[-1]
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_collect_pre_market_data'})

    def _update_opening_range(self, market_data: pd.DataFrame) -> None:
        """Update or establish opening range"""
        try:
            current_time = datetime.now().time()

            # Filter data for range period
            today_data = market_data[market_data.index.time >= RANGE_START]
            if today_data.empty:
                return

            # Initialize range if needed
            if not self.current_range:
                self.current_range = OpeningRange(
                    date=datetime.now(),
                    range_start=RANGE_START,
                    range_end=self._get_range_end(),
                    high=today_data['high'].max(),
                    low=today_data['low'].min(),
                    open_price=today_data['open'].iloc[0],
                    close_price=today_data['close'].iloc[-1],
                    volume=today_data['volume'].sum(),
                    vwap=self._calculate_vwap(today_data),
                    range_size=0,
                    state=RangeState.FORMING
                )

                # Add pre-market data
                if self.pre_market_data:
                    self.current_range.pre_market_high = self.pre_market_data['high']
                    self.current_range.pre_market_low = self.pre_market_data['low']
                    self.current_range.gap_size = (self.current_range.open_price -
                                                  self.pre_market_data['last'])

            # Update range
            self.current_range.high = today_data['high'].max()
            self.current_range.low = today_data['low'].min()
            self.current_range.close_price = today_data['close'].iloc[-1]
            self.current_range.volume = today_data['volume'].sum()
            self.current_range.vwap = self._calculate_vwap(today_data)
            self.current_range.range_size = self.current_range.high - self.current_range.low

            # Calculate volume profile if enabled
            if self.use_volume_profile:
                self._calculate_range_volume_profile(today_data)

            # Check if range is established
            if current_time >= self._get_range_end():
                self.current_range.state = RangeState.ESTABLISHED
                self._validate_range()

                # Add to history
                self.range_history.append(self.current_range)

                # Update stats
                self._update_range_statistics()

                self.logger.info(f"Opening range established: ${self.current_range.low:.2f} - ${self.current_range.high:.2f}")

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_update_opening_range'})

    def _calculate_vwap(self, data: pd.DataFrame) -> float:
        """Calculate volume-weighted average price"""
        try:
            typical_price = (data['high'] + data['low'] + data['close']) / 3
            return (typical_price * data['volume']).sum() / data['volume'].sum()
        except Exception:
            return data['close'].mean()

    def _calculate_range_volume_profile(self, data: pd.DataFrame) -> None:
        """Calculate volume profile within range"""
        try:
            if not self.current_range:
                return

            # Get volume at different price levels
            price_levels = np.linspace(self.current_range.low,
                                     self.current_range.high, 10)

            volume_profile = {}
            for level in price_levels:
                # Find volume traded near this level
                mask = (data['low'] <= level) & (data['high'] >= level)
                volume_profile[level] = data.loc[mask, 'volume'].sum()

            # Find Point of Control (POC)
            if volume_profile:
                self.current_range.poc = max(volume_profile, key=volume_profile.get)

                # Volume at extremes
                self.current_range.volume_at_high = volume_profile.get(
                    max(price_levels), 0
                )
                self.current_range.volume_at_low = volume_profile.get(
                    min(price_levels), 0
                )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_calculate_range_volume_profile'})

    def _validate_range(self) -> None:
        """Validate if range is suitable for trading"""
        if not self.current_range:
            return

        # Check range size
        if self.current_range.range_size < MIN_RANGE_SIZE:
            self.current_range.state = RangeState.INVALID
            self.logger.info(f"Range too small: ${self.current_range.range_size:.2f}")
        elif self.current_range.range_size > MAX_RANGE_SIZE:
            self.current_range.state = RangeState.INVALID
            self.logger.info(f"Range too large: ${self.current_range.range_size:.2f}")

        # Check for inside day (range within yesterday's range)
        # This would need historical data

    def _update_range_statistics(self) -> None:
        """Update range statistics"""
        if self.range_history:
            valid_ranges = [r for r in self.range_history if r.is_valid]
            if valid_ranges:
                self.breakout_stats['avg_range_size'] = statistics.mean(
                    [r.range_size for r in valid_ranges]
                )

    # ==========================================================================
    # BREAKOUT DETECTION METHODS
    # ==========================================================================

    def _check_for_breakout(self, market_data: pd.DataFrame) -> BreakoutSignal | None:
        """Check for breakout from opening range"""
        try:
            if not self.current_range or not self.current_range.is_valid:
                return None

            current_price = market_data['close'].iloc[-1]
            current_volume = market_data['volume'].iloc[-1]
            avg_volume = market_data['volume'].rolling(20).mean().iloc[-1]

            # Calculate momentum
            momentum = self._calculate_breakout_momentum(market_data)

            # Check for bullish breakout
            if current_price > self.current_range.high + BREAKOUT_BUFFER:
                volume_surge = current_volume / avg_volume if avg_volume > 0 else 1

                if volume_surge >= VOLUME_SURGE_RATIO:
                    return self._create_breakout_signal_data(
                        BreakoutType.BULLISH,
                        current_price,
                        volume_surge,
                        momentum,
                        market_data
                    )

            # Check for bearish breakout
            elif current_price < self.current_range.low - BREAKOUT_BUFFER:
                volume_surge = current_volume / avg_volume if avg_volume > 0 else 1

                if volume_surge >= VOLUME_SURGE_RATIO:
                    return self._create_breakout_signal_data(
                        BreakoutType.BEARISH,
                        current_price,
                        volume_surge,
                        momentum,
                        market_data
                    )

            return None

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_check_for_breakout'})
            return None

    def _calculate_breakout_momentum(self, market_data: pd.DataFrame) -> float:
        """Calculate momentum at breakout"""
        try:
            # Simple momentum calculation
            close_prices = market_data['close']

            # Rate of change over last 5 bars
            if len(close_prices) >= 5:
                momentum = (close_prices.iloc[-1] - close_prices.iloc[-5]) / close_prices.iloc[-5]
                return momentum

            return 0.0

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_calculate_breakout_momentum'})
            return 0.0

    def _create_breakout_signal_data(self, breakout_type: BreakoutType,
                                   breakout_price: float, volume_surge: float,
                                   momentum: float, market_data: pd.DataFrame) -> BreakoutSignal:
        """Create breakout signal data structure"""
        try:
            # Calculate ATR for stop loss
            atr = self.tech_indicators.calculate_atr(market_data, 14).iloc[-1]

            # Determine entry and stops
            if breakout_type == BreakoutType.BULLISH:
                entry_price = breakout_price
                stop_loss = self.current_range.low - (atr * STOP_LOSS_ATR_MULTIPLE)
                initial_target = entry_price + (entry_price - stop_loss) * PROFIT_TARGET_RATIO
                option_type = 'call'
                delta = OPTION_DELTA_CALL
                strike = round(breakout_price + 1)  # 1 point OTM
            else:
                entry_price = breakout_price
                stop_loss = self.current_range.high + (atr * STOP_LOSS_ATR_MULTIPLE)
                initial_target = entry_price - (stop_loss - entry_price) * PROFIT_TARGET_RATIO
                option_type = 'put'
                delta = OPTION_DELTA_PUT
                strike = round(breakout_price - 1)  # 1 point OTM

            # Assess breakout quality
            quality = self._assess_breakout_quality(
                breakout_type, volume_surge, momentum, market_data
            )

            # Calculate false breakout risk
            false_breakout_risk = self._calculate_false_breakout_risk(
                breakout_type, breakout_price, market_data
            )

            # Create signal
            signal = BreakoutSignal(
                signal_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
                breakout_type=breakout_type,
                breakout_price=breakout_price,
                range_reference=self.current_range,
                volume_surge=volume_surge,
                momentum=momentum,
                quality=quality,
                entry_price=entry_price,
                stop_loss=stop_loss,
                initial_target=initial_target,
                option_type=option_type,
                strike=strike,
                expiry=datetime.now() + timedelta(days=7),  # Weekly options
                delta=delta,
                false_breakout_risk=false_breakout_risk,
                confidence=1 - false_breakout_risk
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_breakout_signal_data'})
            return None

    def _assess_breakout_quality(self, breakout_type: BreakoutType,
                               volume_surge: float, momentum: float,
                               market_data: pd.DataFrame) -> BreakoutQuality:
        """Assess quality of breakout"""
        score = 0

        # Volume score
        if volume_surge >= 2.0:
            score += 40
        elif volume_surge >= 1.5:
            score += 20
        else:
            score += 10

        # Momentum score
        if abs(momentum) >= 0.01:  # 1% move
            score += 30
        elif abs(momentum) >= 0.005:  # 0.5% move
            score += 20
        else:
            score += 10

        # Range size score (prefer moderate ranges)
        if 1.0 <= self.current_range.range_size <= 2.0:
            score += 20
        elif 0.5 <= self.current_range.range_size <= 3.0:
            score += 10

        # Time of day score (prefer morning breakouts)
        if datetime.now().time() < time(11, 0):
            score += 10

        # Convert score to quality
        if score >= 80:
            return BreakoutQuality.STRONG
        elif score >= 60:
            return BreakoutQuality.MODERATE
        elif score >= 40:
            return BreakoutQuality.WEAK
        else:
            return BreakoutQuality.FALSE

    def _calculate_false_breakout_risk(self, breakout_type: BreakoutType,
                                      breakout_price: float,
                                      market_data: pd.DataFrame) -> float:
        """Calculate risk of false breakout"""
        risk = 0.0

        # Check if breakout is too far from range
        if breakout_type == BreakoutType.BULLISH:
            distance = (breakout_price - self.current_range.high) / self.current_range.high
        else:
            distance = (self.current_range.low - breakout_price) / self.current_range.low

        if distance > 0.02:  # More than 2% beyond range
            risk += 0.3

        # Check if near previous resistance/support
        # This would need more historical data

        # Check time of day (late breakouts more likely false)
        if datetime.now().time() > time(14, 0):
            risk += 0.2

        # Check if range was too small (prone to false breakouts)
        if self.current_range.range_size < 0.75:
            risk += 0.2

        return min(1.0, risk)

    def _is_false_breakout(self, position: BreakoutPosition,
                          market_data: pd.DataFrame) -> bool:
        """Check if breakout has failed"""
        current_price = market_data['close'].iloc[-1]

        if position.breakout_signal.breakout_type == BreakoutType.BULLISH:
            # Check if price pulled back below range high
            pullback = (self.current_range.high - current_price) / self.current_range.high
            if pullback > FALSE_BREAKOUT_PULLBACK:
                return True
        else:  # BEARISH
            # Check if price pulled back above range low
            pullback = (current_price - self.current_range.low) / self.current_range.low
            if pullback > FALSE_BREAKOUT_PULLBACK:
                return True

        return False

    # ==========================================================================
    # SIGNAL CREATION METHODS
    # ==========================================================================

    def _create_breakout_signal(self, breakout: BreakoutSignal,
                              market_data: pd.DataFrame) -> TradingSignal | None:
        """Create trading signal from breakout"""
        try:
            # Determine signal strength
            if breakout.quality == BreakoutQuality.STRONG:
                strength = SignalStrength.VERY_STRONG
            elif breakout.quality == BreakoutQuality.MODERATE:
                strength = SignalStrength.STRONG
            elif breakout.quality == BreakoutQuality.WEAK:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Create signal
            signal = TradingSignal(
                signal_id=breakout.signal_id,
                signal_type=SignalType.BUY,
                symbol='SPY',
                strength=strength,
                confidence=breakout.confidence,
                entry_price=breakout.entry_price,
                stop_loss=breakout.stop_loss,
                take_profit=breakout.initial_target,
                position_size=1,  # Will be calculated
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5),
                metadata={
                    'strategy': 'opening_range_breakout',
                    'breakout_data': {
                        'breakout_type': breakout.breakout_type.name,
                        'breakout_price': breakout.breakout_price,
                        'range_high': self.current_range.high,
                        'range_low': self.current_range.low,
                        'range_size': self.current_range.range_size,
                        'volume_surge': breakout.volume_surge,
                        'momentum': breakout.momentum,
                        'quality': breakout.quality.name,
                        'entry_price': breakout.entry_price,
                        'stop_loss': breakout.stop_loss,
                        'initial_target': breakout.initial_target,
                        'option_type': breakout.option_type,
                        'strike': breakout.strike,
                        'delta': breakout.delta,
                        'false_breakout_risk': breakout.false_breakout_risk,
                        'option_spread': 0.05  # Placeholder
                    }
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_breakout_signal'})
            return None

    # ==========================================================================
    # POSITION MANAGEMENT METHODS
    # ==========================================================================

    def open_breakout_position(self, signal: TradingSignal) -> BreakoutPosition | None:
        """Open a new breakout position"""
        try:
            breakout_data = signal.metadata['breakout_data']

            # Create breakout signal object
            breakout_signal = BreakoutSignal(
                signal_id=signal.signal_id,
                timestamp=signal.timestamp,
                breakout_type=BreakoutType[breakout_data['breakout_type']],
                breakout_price=breakout_data['breakout_price'],
                range_reference=self.current_range,
                volume_surge=breakout_data['volume_surge'],
                momentum=breakout_data['momentum'],
                quality=BreakoutQuality[breakout_data['quality']],
                entry_price=breakout_data['entry_price'],
                stop_loss=breakout_data['stop_loss'],
                initial_target=breakout_data['initial_target'],
                option_type=breakout_data['option_type'],
                strike=breakout_data['strike'],
                expiry=signal.timestamp + timedelta(days=7),
                delta=breakout_data['delta'],
                false_breakout_risk=breakout_data['false_breakout_risk'],
                confidence=signal.confidence
            )

            # Create position - FIXED: proper field ordering
            position = BreakoutPosition(
                position_id=str(uuid.uuid4()),
                breakout_signal=breakout_signal,
                entry_time=datetime.now(),
                option_contracts=signal.position_size,
                entry_price=breakout_data['entry_price'],
                current_stop=breakout_data['stop_loss'],  # Now properly ordered
                # Optional fields with defaults:
                highest_price=breakout_data['entry_price'],
                lowest_price=breakout_data['entry_price'],
                max_profit=(breakout_data['initial_target'] - breakout_data['entry_price']) *
                          signal.position_size * SPY_CONTRACT_MULTIPLIER,
                max_loss=(breakout_data['entry_price'] - breakout_data['stop_loss']) *
                        signal.position_size * SPY_CONTRACT_MULTIPLIER
            )

            # Add to tracking
            self.active_breakouts[position.position_id] = position
            self.daily_trades += 1

            # Update stats
            self.breakout_stats['total_breakouts'] += 1

            # Track by day
            if datetime.now().weekday() == 0:
                self.breakout_stats['monday_trades'] += 1
            elif datetime.now().weekday() == 1:
                self.breakout_stats['tuesday_trades'] += 1
            else:
                self.breakout_stats['other_day_trades'] += 1

            # Mark range as broken
            if self.current_range:
                self.current_range.state = RangeState.BROKEN

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_OPENED,
                self.name,
                {
                    'position_id': position.position_id,
                    'breakout_type': position.breakout_signal.breakout_type.name,
                    'entry_price': position.entry_price,
                    'stop_loss': position.current_stop
                }
            ))

            self.logger.info("Opened %s breakout: %s", position.breakout_signal.breakout_type.name, position.position_id)
            return position

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'open_breakout_position',
                'signal_id': signal.signal_id
            })
            return None

    def _update_positions(self, market_data: pd.DataFrame) -> None:
        """Update all active breakout positions"""
        for position in self.active_breakouts.values():
            current_price = market_data['close'].iloc[-1]
            self._update_breakout_position(position, current_price)

    def _update_breakout_position(self, position: BreakoutPosition, current_price: float) -> None:
        """Update individual breakout position"""
        try:
            position.current_price = current_price
            position.bars_in_trade += 1

            # Update P&L
            if position.breakout_signal.breakout_type == BreakoutType.BULLISH:
                position.unrealized_pnl = (current_price - position.entry_price) * \
                                        position.option_contracts * SPY_CONTRACT_MULTIPLIER

                # Update highest price for trailing stop
                if current_price > position.highest_price:
                    position.highest_price = current_price

                    # Activate trailing stop if profitable
                    if position.unrealized_pnl > position.max_profit * 0.5:
                        position.trailing_stop_active = True

                # Update trailing stop
                if position.trailing_stop_active:
                    new_stop = position.highest_price * (1 - TRAILING_STOP_PERCENT)
                    position.current_stop = max(position.current_stop, new_stop)

            else:  # BEARISH
                position.unrealized_pnl = (position.entry_price - current_price) * \
                                        position.option_contracts * SPY_CONTRACT_MULTIPLIER

                # Update lowest price for trailing stop
                if current_price < position.lowest_price:
                    position.lowest_price = current_price

                    # Activate trailing stop if profitable
                    if position.unrealized_pnl > position.max_profit * 0.5:
                        position.trailing_stop_active = True

                # Update trailing stop
                if position.trailing_stop_active:
                    new_stop = position.lowest_price * (1 + TRAILING_STOP_PERCENT)
                    position.current_stop = min(position.current_stop, new_stop)

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_breakout_position',
                'position_id': position.position_id
            })

    def close_breakout_position(self, position_id: str, reason: str) -> bool:
        """Close breakout position"""
        try:
            position = self.active_breakouts.get(position_id)
            if not position:
                return False

            # Update final P&L
            position.realized_pnl = position.unrealized_pnl
            position.exit_time = datetime.now()
            position.exit_reason = reason

            # Update stats
            if position.realized_pnl > 0:
                self.breakout_stats['successful_breakouts'] += 1
            else:
                if "false breakout" in reason.lower():
                    self.breakout_stats['false_breakouts'] += 1

            # Calculate average move
            if position.breakout_signal.breakout_type == BreakoutType.BULLISH:
                move = position.current_price - position.breakout_signal.breakout_price
            else:
                move = position.breakout_signal.breakout_price - position.current_price

            # Update average (simplified)
            self.breakout_stats['avg_breakout_move'] = (
                (self.breakout_stats['avg_breakout_move'] * (self.breakout_stats['total_breakouts'] - 1) + move) /
                self.breakout_stats['total_breakouts']
            )

            # Remove from active
            del self.active_breakouts[position_id]

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_CLOSED,
                self.name,
                {
                    'position_id': position_id,
                    'realized_pnl': position.realized_pnl,
                    'exit_reason': reason,
                    'bars_in_trade': position.bars_in_trade
                }
            ))

            self.logger.info(f"Closed breakout position {position_id}: P&L ${position.realized_pnl:.2f}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'close_breakout_position',
                'position_id': position_id
            })
            return False

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def get_strategy_summary(self) -> dict[str, Any]:
        """Get comprehensive strategy summary"""
        return {
            'strategy': 'OpeningRangeBreakout',
            'state': self.state,
            'current_range': {
                'state': self.current_range.state.name if self.current_range else 'NONE',
                'high': self.current_range.high if self.current_range else 0,
                'low': self.current_range.low if self.current_range else 0,
                'size': self.current_range.range_size if self.current_range else 0,
                'poc': self.current_range.poc if self.current_range else 0
            },
            'active_positions': len(self.active_breakouts),
            'daily_trades': self.daily_trades,
            'statistics': self.breakout_stats.copy(),
            'performance': {
                'success_rate': (self.breakout_stats['successful_breakouts'] /
                               self.breakout_stats['total_breakouts']
                               if self.breakout_stats['total_breakouts'] > 0 else 0),
                'false_breakout_rate': (self.breakout_stats['false_breakouts'] /
                                      self.breakout_stats['total_breakouts']
                                      if self.breakout_stats['total_breakouts'] > 0 else 0)
            }
        }

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Test opening range breakout strategy
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01
    )

    config = {
        'range_minutes': 30,
        'use_volume_profile': True,
        'enable_pre_market': True,
        'max_daily_trades': 2
    }

    strategy = OpeningRangeBreakoutStrategy(event_manager, risk_profile, config)
    strategy.start()

    # Create sample intraday data
    current_date = datetime.now().replace(hour=9, minute=0, second=0)
    time_index = pd.date_range(start=current_date, periods=100, freq='5min')

    # Simulate opening range and breakout
    prices = np.zeros(100)
    base_price = 450

    # Pre-market
    prices[:6] = base_price + np.random.uniform(-0.5, 0.5, 6)

    # Opening range (9:30-10:00)
    range_high = base_price + 1
    range_low = base_price - 0.5
    prices[6:12] = np.random.uniform(range_low, range_high, 6)

    # Breakout above range
    prices[12] = range_high + 0.2
    prices[13:20] = range_high + 0.5 + np.cumsum(np.random.uniform(0, 0.1, 7))

    # Continue trend
    prices[20:] = prices[19] + np.cumsum(np.random.randn(80) * 0.1)

    # Create volume pattern
    volumes = np.random.randint(500000, 1000000, 100)
    volumes[12] = 2000000  # Volume surge on breakout

    market_data = pd.DataFrame({
        'open': prices - 0.05,
        'high': prices + 0.1,
        'low': prices - 0.1,
        'close': prices,
        'volume': volumes
    }, index=time_index)

    # Process each bar
    signals_generated = []
    for i in range(len(market_data)):
        if i > 0:
            data_slice = market_data.iloc[:i+1]
            signals = strategy.generate_signals(data_slice)

            if signals:
                signals_generated.extend(signals)
                for signal in signals:
                    breakout_data = signal.metadata.get('breakout_data', {})

    # Get strategy summary
    summary = strategy.get_strategy_summary()
    if summary['current_range']['high'] > 0:
        pass

    strategy.stop()
