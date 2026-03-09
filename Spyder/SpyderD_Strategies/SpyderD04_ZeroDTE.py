#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD04_ZeroDTE.py
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
from datetime import datetime, time, timedelta, date
from typing import Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import pytz

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy, TradingSignal, SignalType, SignalStrength,
    StrategyPosition, EventManager, RiskProfile, Event, EventType
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    ZERO_DTE_MAX_TRADES,
    MAX_OVERNIGHT_GAP,
    SPY_CONTRACT_MULTIPLIER
)

# ==============================================================================
# ENHANCED CONSTANTS (LEAN-based)
# ==============================================================================
# Entry timing (LEAN pattern: 1 minute after open)
ENTRY_DELAY_MINUTES = 1
MARKET_OPEN_TIME = time(9, 30)
MARKET_CLOSE_TIME = time(16, 0)
ENTRY_TIME = time(9, 31)  # 1 minute after open
EXIT_TIME = time(15, 50)  # 10 minutes before close

# Strike selection
OTM_STRIKE_OFFSET = 2  # $2 OTM for 0DTE
DELTA_TARGET_PUT = -0.20  # Target delta for short puts
DELTA_TARGET_CALL = 0.20  # Target delta for short calls

# Position management
MAX_CONCURRENT_POSITIONS = 2  # Max 0DTE positions
MIN_PREMIUM = 0.50  # Minimum premium to collect
PROFIT_TARGET_PERCENT = 0.25  # Close at 25% profit
STOP_LOSS_PERCENT = 2.00  # Stop at 200% loss
TIME_STOP_HOUR = 15  # Close all by 3 PM

# Market filters
MIN_VOLUME = 50000000  # Minimum SPY volume
MAX_VIX = 30  # Maximum VIX level
MIN_IVR = 30  # Minimum IV rank

# ==============================================================================
# ENUMS
# ==============================================================================
class ZeroDTEStrategy(Enum):
    """0DTE strategy types"""
    SHORT_PUT = auto()
    SHORT_CALL = auto()
    IRON_CONDOR = auto()
    IRON_BUTTERFLY = auto()
    CREDIT_SPREAD = auto()

class ZeroDTEState(Enum):
    """0DTE position states"""
    PENDING = auto()
    ACTIVE = auto()
    PROFIT_TARGET = auto()
    STOP_LOSS = auto()
    TIME_STOP = auto()
    EXPIRED = auto()
    CLOSED = auto()

class MarketPhase(Enum):
    """Intraday market phases"""
    PRE_OPEN = auto()
    OPENING = auto()
    MORNING = auto()
    MIDDAY = auto()
    AFTERNOON = auto()
    CLOSING = auto()
    AFTER_HOURS = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ZeroDTEPosition:
    """0DTE position tracking"""
    position_id: str
    strategy_type: ZeroDTEStrategy
    entry_time: datetime
    expiry_date: date
    strikes: dict[str, float]  # e.g., {'short_put': 445, 'long_put': 440}
    contracts: int
    entry_premium: float
    current_value: float = 0.0
    state: ZeroDTEState = ZeroDTEState.PENDING

    # P&L tracking
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_profit: float = 0.0
    max_loss: float = 0.0

    # Risk metrics
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0

    # Exit tracking
    exit_time: datetime | None = None
    exit_reason: str | None = None

    # Metadata
    entry_conditions: dict[str, Any] = field(default_factory=dict)

    @property
    def time_to_expiry(self) -> float:
        """Hours to expiry"""
        if self.expiry_date == date.today():
            close_time = datetime.combine(date.today(), MARKET_CLOSE_TIME)
            return max(0, (close_time - datetime.now()).total_seconds() / 3600)
        return 0

    @property
    def profit_percentage(self) -> float:
        """Current profit as percentage of max profit"""
        return self.unrealized_pnl / self.max_profit if self.max_profit > 0 else 0

@dataclass
class MarketConditions:
    """Intraday market conditions for 0DTE"""
    timestamp: datetime
    spot_price: float
    opening_price: float
    high_of_day: float
    low_of_day: float
    volume: int
    vix: float
    iv_rank: float
    market_phase: MarketPhase
    trend_direction: str  # 'up', 'down', 'sideways'
    momentum: float
    overnight_gap: float

    @property
    def gap_percentage(self) -> float:
        """Overnight gap as percentage"""
        return self.overnight_gap / self.opening_price if self.opening_price > 0 else 0

    @property
    def intraday_range(self) -> float:
        """Intraday price range"""
        return self.high_of_day - self.low_of_day

@dataclass
class ZeroDTESetup:
    """0DTE trade setup configuration"""
    strategy_type: ZeroDTEStrategy
    strikes: dict[str, float]
    expiry: datetime
    contracts: int
    estimated_credit: float
    max_profit: float
    max_loss: float
    probability_profit: float
    entry_conditions: MarketConditions
    score: float  # Setup quality score

# ==============================================================================
# ZERO DTE STRATEGY CLASS
# ==============================================================================
class ZeroDTEStrategy(BaseStrategy):
    """
    Enhanced 0DTE strategy with LEAN patterns.

    Implements professional 0DTE trading with precise timing, risk management,
    and position lifecycle handling based on LEAN algorithm patterns.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any]):
        """Initialize 0DTE strategy"""
        super().__init__("ZeroDTE", event_manager, risk_profile, config)

        # Configuration
        self.max_positions = config.get('max_positions', MAX_CONCURRENT_POSITIONS)
        self.profit_target = config.get('profit_target', PROFIT_TARGET_PERCENT)
        self.stop_loss = config.get('stop_loss', STOP_LOSS_PERCENT)
        self.entry_delay_minutes = config.get('entry_delay_minutes', ENTRY_DELAY_MINUTES)

        # Timezone handling
        self.eastern_tz = pytz.timezone('US/Eastern')

        # Position tracking
        self.active_positions: dict[str, ZeroDTEPosition] = {}
        self.today_trades = 0
        self.last_trade_date: date | None = None

        # Market monitoring
        self.current_conditions: MarketConditions | None = None
        self.option_chain_cache: dict[str, pd.DataFrame] = {}

        # Performance tracking
        self.daily_stats = {
            'trades_executed': 0,
            'trades_won': 0,
            'trades_lost': 0,
            'total_pnl': 0.0,
            'time_stops': 0,
            'profit_targets': 0,
            'stop_losses': 0,
            'expired_otm': 0
        }

        # Schedule entry check
        self._schedule_entry_check()

        self.logger.info("ZeroDTEStrategy initialized with LEAN enhancements")

    # ==========================================================================
    # REQUIRED ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate 0DTE trading signals"""
        signals = []

        try:
            # Update market conditions
            self._update_market_conditions(market_data)

            # Check if we can trade 0DTE today
            if not self._can_trade_0dte():
                return signals

            # Check entry time window
            if not self._is_entry_time():
                return signals

            # Get 0DTE option chain
            option_chain = self._get_0dte_options(market_data)
            if option_chain.empty:
                return signals

            # Find best 0DTE setup
            setup = self._find_optimal_0dte_setup(option_chain)
            if setup and self._validate_setup(setup):
                signal = self._create_signal_from_setup(setup)
                if signal:
                    signals.append(signal)
                    self.logger.info(f"Generated 0DTE signal: {signal.signal_id}")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'market_data_shape': market_data.shape
            })

        return signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate 0DTE signal"""
        try:
            # Check signal validity
            if not signal.is_valid():
                return False

            # Check 0DTE specific metadata
            setup_data = signal.metadata.get('setup_data')
            if not setup_data:
                return False

            # Validate expiry is today
            expiry = datetime.fromisoformat(setup_data['expiry'])
            if expiry.date() != date.today():
                return False

            # Validate premium
            if setup_data['estimated_credit'] < MIN_PREMIUM:
                return False

            # Validate probability
            if setup_data['probability_profit'] < 0.60:
                return False

            # Check market conditions haven't changed significantly
            if self.current_conditions:
                if abs(self.current_conditions.spot_price - signal.entry_price) > 2:
                    return False

            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'validate_signal',
                'signal_id': signal.signal_id
            })
            return False

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size for 0DTE"""
        try:
            # Get setup data
            setup_data = signal.metadata.get('setup_data', {})
            max_loss = setup_data.get('max_loss', 1000)

            # Risk-based sizing
            account_value = self.risk_profile.account_size
            max_risk = account_value * 0.005  # 0.5% risk for 0DTE

            contracts = int(max_risk / (max_loss * SPY_CONTRACT_MULTIPLIER))

            # Apply limits
            contracts = max(1, min(contracts, 5))  # 1-5 contracts for 0DTE

            # Reduce size based on market conditions
            if self.current_conditions:
                if self.current_conditions.vix > 25:
                    contracts = max(1, contracts // 2)
                if abs(self.current_conditions.gap_percentage) > 0.01:
                    contracts = max(1, contracts - 1)

            return contracts

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'calculate_position_size',
                'signal_id': signal.signal_id
            })
            return 1

    def should_exit_position(self, position: StrategyPosition,
                           market_data: pd.DataFrame) -> tuple[bool, str]:
        """Determine if 0DTE position should be exited"""
        try:
            # Get 0DTE position
            dte_position = self.active_positions.get(position.position_id)
            if not dte_position:
                return False, ""

            # Update position value
            self._update_position_value(dte_position, market_data)

            # Check profit target
            if dte_position.profit_percentage >= self.profit_target:
                return True, f"Profit target reached: {dte_position.profit_percentage:.1%}"

            # Check stop loss
            loss_pct = abs(dte_position.unrealized_pnl) / dte_position.max_loss
            if loss_pct >= self.stop_loss:
                return True, f"Stop loss triggered: {loss_pct:.1%}"

            # Check time stop
            current_time = datetime.now(self.eastern_tz).time()
            if current_time >= time(TIME_STOP_HOUR, 0):
                return True, f"Time stop at {TIME_STOP_HOUR}:00"

            # Check if position is threatened
            spot_price = market_data['close'].iloc[-1]
            if self._is_position_threatened(dte_position, spot_price):
                return True, "Position threatened by price movement"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'should_exit_position',
                'position_id': position.position_id
            })
            return False, ""

    # ==========================================================================
    # 0DTE SPECIFIC METHODS
    # ==========================================================================

    def _can_trade_0dte(self) -> bool:
        """Check if we can trade 0DTE today"""
        today = date.today()

        # Reset daily counter
        if self.last_trade_date != today:
            self.today_trades = 0
            self.last_trade_date = today
            self._reset_daily_stats()

        # Check daily trade limit
        if self.today_trades >= ZERO_DTE_MAX_TRADES:
            return False

        # Check active positions
        if len(self.active_positions) >= self.max_positions:
            return False

        # Check market conditions
        if not self.current_conditions:
            return False

        # Validate market filters
        if self.current_conditions.vix > MAX_VIX:
            self.logger.debug(f"VIX too high: {self.current_conditions.vix}")
            return False

        if self.current_conditions.iv_rank < MIN_IVR:
            self.logger.debug(f"IV rank too low: {self.current_conditions.iv_rank}")
            return False

        if abs(self.current_conditions.gap_percentage) > MAX_OVERNIGHT_GAP:
            self.logger.debug(f"Overnight gap too large: {self.current_conditions.gap_percentage:.2%}")
            return False

        return True

    def _is_entry_time(self) -> bool:
        """Check if current time is valid for 0DTE entry"""
        current_time = datetime.now(self.eastern_tz).time()

        # Must be after entry delay
        entry_time = time(
            MARKET_OPEN_TIME.hour,
            MARKET_OPEN_TIME.minute + self.entry_delay_minutes
        )

        # Must be before midday
        return entry_time <= current_time <= time(12, 0)

    def _update_market_conditions(self, market_data: pd.DataFrame) -> None:
        """Update intraday market conditions"""
        try:
            current_time = datetime.now(self.eastern_tz)
            current_price = market_data['close'].iloc[-1]

            # Get opening price (first bar of the day)
            today_data = market_data[market_data.index.date == date.today()]
            if today_data.empty:
                return

            opening_price = today_data['open'].iloc[0]
            high_of_day = today_data['high'].max()
            low_of_day = today_data['low'].min()
            total_volume = today_data['volume'].sum()

            # Calculate overnight gap
            yesterday_close = market_data[market_data.index.date < date.today()]['close'].iloc[-1]
            overnight_gap = opening_price - yesterday_close

            # Determine market phase
            market_phase = self._get_market_phase(current_time.time())

            # Simple trend detection
            sma_5 = market_data['close'].rolling(5).mean().iloc[-1]
            sma_20 = market_data['close'].rolling(20).mean().iloc[-1]

            if current_price > sma_5 > sma_20:
                trend_direction = 'up'
                momentum = (current_price - sma_20) / sma_20
            elif current_price < sma_5 < sma_20:
                trend_direction = 'down'
                momentum = (sma_20 - current_price) / sma_20
            else:
                trend_direction = 'sideways'
                momentum = 0.0

            # Create conditions object
            self.current_conditions = MarketConditions(
                timestamp=current_time,
                spot_price=current_price,
                opening_price=opening_price,
                high_of_day=high_of_day,
                low_of_day=low_of_day,
                volume=total_volume,
                vix=20.0,  # Placeholder - would get from VIX data
                iv_rank=45.0,  # Placeholder - would calculate
                market_phase=market_phase,
                trend_direction=trend_direction,
                momentum=momentum,
                overnight_gap=overnight_gap
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_update_market_conditions'})

    def _get_market_phase(self, current_time: time) -> MarketPhase:
        """Determine current market phase"""
        if current_time < MARKET_OPEN_TIME:
            return MarketPhase.PRE_OPEN
        elif current_time < time(10, 0):
            return MarketPhase.OPENING
        elif current_time < time(12, 0):
            return MarketPhase.MORNING
        elif current_time < time(14, 0):
            return MarketPhase.MIDDAY
        elif current_time < time(15, 30):
            return MarketPhase.AFTERNOON
        elif current_time < MARKET_CLOSE_TIME:
            return MarketPhase.CLOSING
        else:
            return MarketPhase.AFTER_HOURS

    def _get_0dte_options(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """Get options expiring today"""
        # In production, this would fetch real 0DTE option chain
        # For now, return empty DataFrame
        return pd.DataFrame()

    def _find_optimal_0dte_setup(self, option_chain: pd.DataFrame) -> ZeroDTESetup | None:
        """Find optimal 0DTE setup based on market conditions"""
        try:
            if option_chain.empty or not self.current_conditions:
                return None

            spot_price = self.current_conditions.spot_price

            # Determine strategy based on market conditions
            if self.current_conditions.trend_direction == 'up':
                # Bullish: Short put spread or short put
                strategy_type = ZeroDTEStrategy.SHORT_PUT
                strikes = self._find_put_spread_strikes(option_chain, spot_price)
            elif self.current_conditions.trend_direction == 'down':
                # Bearish: Short call spread or short call
                strategy_type = ZeroDTEStrategy.SHORT_CALL
                strikes = self._find_call_spread_strikes(option_chain, spot_price)
            else:
                # Neutral: Iron condor or iron butterfly
                strategy_type = ZeroDTEStrategy.IRON_CONDOR
                strikes = self._find_iron_condor_strikes(option_chain, spot_price)

            if not strikes:
                return None

            # Calculate setup metrics
            setup_metrics = self._calculate_setup_metrics(
                strategy_type, strikes, option_chain
            )

            if not setup_metrics:
                return None

            # Create setup
            setup = ZeroDTESetup(
                strategy_type=strategy_type,
                strikes=strikes,
                expiry=datetime.combine(date.today(), MARKET_CLOSE_TIME),
                contracts=1,  # Will be sized later
                estimated_credit=setup_metrics['credit'],
                max_profit=setup_metrics['max_profit'],
                max_loss=setup_metrics['max_loss'],
                probability_profit=setup_metrics['probability'],
                entry_conditions=self.current_conditions,
                score=self._score_setup(setup_metrics)
            )

            return setup

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_find_optimal_0dte_setup'})
            return None

    def _find_put_spread_strikes(self, option_chain: pd.DataFrame,
                                spot_price: float) -> dict[str, float] | None:
        """Find strikes for put spread"""
        # Simplified - would use actual option chain
        short_put = round(spot_price - OTM_STRIKE_OFFSET)
        long_put = short_put - 5  # $5 wide spread

        return {
            'short_put': short_put,
            'long_put': long_put
        }

    def _find_call_spread_strikes(self, option_chain: pd.DataFrame,
                                 spot_price: float) -> dict[str, float] | None:
        """Find strikes for call spread"""
        # Simplified - would use actual option chain
        short_call = round(spot_price + OTM_STRIKE_OFFSET)
        long_call = short_call + 5  # $5 wide spread

        return {
            'short_call': short_call,
            'long_call': long_call
        }

    def _find_iron_condor_strikes(self, option_chain: pd.DataFrame,
                                 spot_price: float) -> dict[str, float] | None:
        """Find strikes for iron condor"""
        # Simplified - would use actual option chain
        return {
            'long_put': round(spot_price - 7),
            'short_put': round(spot_price - 2),
            'short_call': round(spot_price + 2),
            'long_call': round(spot_price + 7)
        }

    def _calculate_setup_metrics(self, strategy_type: ZeroDTEStrategy,
                               strikes: dict[str, float],
                               option_chain: pd.DataFrame) -> dict[str, Any] | None:
        """Calculate metrics for 0DTE setup"""
        # Simplified calculation - would use actual option prices

        if strategy_type == ZeroDTEStrategy.SHORT_PUT:
            spread_width = strikes['short_put'] - strikes['long_put']
            credit = spread_width * 0.20  # 20% of width for 0DTE
            max_profit = credit
            max_loss = spread_width - credit
            probability = 0.75  # Simplified

        elif strategy_type == ZeroDTEStrategy.SHORT_CALL:
            spread_width = strikes['long_call'] - strikes['short_call']
            credit = spread_width * 0.20  # 20% of width for 0DTE
            max_profit = credit
            max_loss = spread_width - credit
            probability = 0.75  # Simplified

        elif strategy_type == ZeroDTEStrategy.IRON_CONDOR:
            put_width = strikes['short_put'] - strikes['long_put']
            call_width = strikes['long_call'] - strikes['short_call']
            credit = (put_width + call_width) * 0.15  # Lower for IC
            max_profit = credit
            max_loss = max(put_width, call_width) - credit
            probability = 0.70  # Simplified

        else:
            return None

        return {
            'credit': credit,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'probability': probability,
            'risk_reward': max_profit / max_loss if max_loss > 0 else 0
        }

    def _score_setup(self, metrics: dict[str, Any]) -> float:
        """Score 0DTE setup quality"""
        score = 0.0

        # Credit quality
        if metrics['credit'] >= 1.0:
            score += 30
        elif metrics['credit'] >= 0.75:
            score += 20
        elif metrics['credit'] >= 0.50:
            score += 10

        # Risk/reward ratio
        if metrics['risk_reward'] >= 0.33:
            score += 30
        elif metrics['risk_reward'] >= 0.25:
            score += 20
        elif metrics['risk_reward'] >= 0.20:
            score += 10

        # Probability of profit
        if metrics['probability'] >= 0.80:
            score += 30
        elif metrics['probability'] >= 0.70:
            score += 20
        elif metrics['probability'] >= 0.60:
            score += 10

        # Market conditions bonus
        if self.current_conditions:
            if self.current_conditions.market_phase == MarketPhase.MORNING:
                score += 10  # Prefer morning entries
            if abs(self.current_conditions.momentum) < 0.5:
                score += 5  # Prefer less volatile conditions

        return score

    def _validate_setup(self, setup: ZeroDTESetup) -> bool:
        """Validate 0DTE setup meets criteria"""
        # Minimum credit
        if setup.estimated_credit < MIN_PREMIUM:
            return False

        # Minimum probability
        if setup.probability_profit < 0.60:
            return False

        # Minimum score
        if setup.score < 40:
            return False

        # Risk/reward check
        return not setup.max_profit / setup.max_loss < 0.2

    def _create_signal_from_setup(self, setup: ZeroDTESetup) -> TradingSignal | None:
        """Create trading signal from 0DTE setup"""
        try:
            # Calculate signal strength
            if setup.score >= 80:
                strength = SignalStrength.VERY_STRONG
            elif setup.score >= 60:
                strength = SignalStrength.STRONG
            elif setup.score >= 40:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            # Create signal
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol='SPY',
                strength=strength,
                confidence=setup.probability_profit,
                entry_price=self.current_conditions.spot_price,
                stop_loss=0,  # Managed differently
                take_profit=0,  # Managed differently
                position_size=1,  # Will be calculated
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=5),
                metadata={
                    'strategy': '0dte',
                    'setup_data': {
                        'strategy_type': setup.strategy_type.name,
                        'strikes': setup.strikes,
                        'expiry': setup.expiry.isoformat(),
                        'estimated_credit': setup.estimated_credit,
                        'max_profit': setup.max_profit,
                        'max_loss': setup.max_loss,
                        'probability_profit': setup.probability_profit,
                        'score': setup.score
                    }
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_signal_from_setup'})
            return None

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def open_0dte_position(self, signal: TradingSignal) -> ZeroDTEPosition | None:
        """Open a new 0DTE position"""
        try:
            setup_data = signal.metadata['setup_data']

            # Create position
            position = ZeroDTEPosition(
                position_id=str(uuid.uuid4()),
                strategy_type=ZeroDTEStrategy[setup_data['strategy_type']],
                entry_time=datetime.now(),
                expiry_date=date.today(),
                strikes=setup_data['strikes'],
                contracts=signal.position_size,
                entry_premium=setup_data['estimated_credit'],
                max_profit=setup_data['max_profit'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                max_loss=setup_data['max_loss'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                state=ZeroDTEState.ACTIVE,
                entry_conditions={
                    'spot_price': signal.entry_price,
                    'vix': self.current_conditions.vix if self.current_conditions else 0,
                    'iv_rank': self.current_conditions.iv_rank if self.current_conditions else 0,
                    'gap': self.current_conditions.gap_percentage if self.current_conditions else 0
                }
            )

            # Add to tracking
            self.active_positions[position.position_id] = position
            self.today_trades += 1
            self.daily_stats['trades_executed'] += 1

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_OPENED,
                self.name,
                {
                    'position_id': position.position_id,
                    'strategy': '0dte',
                    'type': position.strategy_type.name,
                    'premium': position.entry_premium,
                    'max_profit': position.max_profit
                }
            ))

            self.logger.info(f"Opened 0DTE position: {position.position_id}")
            return position

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'open_0dte_position',
                'signal_id': signal.signal_id
            })
            return None

    def _update_position_value(self, position: ZeroDTEPosition,
                             market_data: pd.DataFrame) -> None:
        """Update 0DTE position value"""
        try:
            current_price = market_data['close'].iloc[-1]

            # Simplified P&L calculation
            # In production, would use actual option prices

            if position.strategy_type == ZeroDTEStrategy.SHORT_PUT:
                short_strike = position.strikes.get('short_put', 0)
                if current_price < short_strike:
                    # ITM - losing money
                    intrinsic = short_strike - current_price
                    position.unrealized_pnl = -intrinsic * position.contracts * SPY_CONTRACT_MULTIPLIER
                else:
                    # OTM - keeping premium
                    time_decay = position.time_to_expiry / 6.5  # Trading hours
                    position.unrealized_pnl = position.entry_premium * (1 - time_decay) * position.contracts * SPY_CONTRACT_MULTIPLIER

            elif position.strategy_type == ZeroDTEStrategy.SHORT_CALL:
                short_strike = position.strikes.get('short_call', 0)
                if current_price > short_strike:
                    # ITM - losing money
                    intrinsic = current_price - short_strike
                    position.unrealized_pnl = -intrinsic * position.contracts * SPY_CONTRACT_MULTIPLIER
                else:
                    # OTM - keeping premium
                    time_decay = position.time_to_expiry / 6.5  # Trading hours
                    position.unrealized_pnl = position.entry_premium * (1 - time_decay) * position.contracts * SPY_CONTRACT_MULTIPLIER

            # Cap P&L at max profit/loss
            position.unrealized_pnl = max(-position.max_loss,
                                        min(position.max_profit, position.unrealized_pnl))

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position_value',
                'position_id': position.position_id
            })

    def _is_position_threatened(self, position: ZeroDTEPosition, spot_price: float) -> bool:
        """Check if position is threatened by price movement"""
        threat_buffer = 1.0  # $1 buffer

        if position.strategy_type == ZeroDTEStrategy.SHORT_PUT:
            short_strike = position.strikes.get('short_put', 0)
            return spot_price <= short_strike + threat_buffer

        elif position.strategy_type == ZeroDTEStrategy.SHORT_CALL:
            short_strike = position.strikes.get('short_call', 0)
            return spot_price >= short_strike - threat_buffer

        elif position.strategy_type == ZeroDTEStrategy.IRON_CONDOR:
            short_put = position.strikes.get('short_put', 0)
            short_call = position.strikes.get('short_call', 0)
            return (spot_price <= short_put + threat_buffer or
                   spot_price >= short_call - threat_buffer)

        return False

    def close_0dte_position(self, position_id: str, reason: str) -> bool:
        """Close 0DTE position"""
        try:
            position = self.active_positions.get(position_id)
            if not position:
                return False

            # Update final P&L
            position.realized_pnl = position.unrealized_pnl
            position.exit_time = datetime.now()
            position.exit_reason = reason

            # Update state based on reason
            if "profit target" in reason.lower():
                position.state = ZeroDTEState.PROFIT_TARGET
                self.daily_stats['profit_targets'] += 1
            elif "stop loss" in reason.lower():
                position.state = ZeroDTEState.STOP_LOSS
                self.daily_stats['stop_losses'] += 1
            elif "time stop" in reason.lower():
                position.state = ZeroDTEState.TIME_STOP
                self.daily_stats['time_stops'] += 1
            else:
                position.state = ZeroDTEState.CLOSED

            # Update daily stats
            if position.realized_pnl > 0:
                self.daily_stats['trades_won'] += 1
            else:
                self.daily_stats['trades_lost'] += 1

            self.daily_stats['total_pnl'] += position.realized_pnl

            # Remove from active
            del self.active_positions[position_id]

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_CLOSED,
                self.name,
                {
                    'position_id': position_id,
                    'realized_pnl': position.realized_pnl,
                    'exit_reason': reason
                }
            ))

            self.logger.info(f"Closed 0DTE position {position_id}: PnL ${position.realized_pnl:.2f}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'close_0dte_position',
                'position_id': position_id
            })
            return False

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _schedule_entry_check(self) -> None:
        """Schedule daily entry check at specified time"""
        # In production, would use proper scheduler
        # This is a placeholder
        self.logger.info(f"Scheduled 0DTE entry check at {ENTRY_TIME}")

    def _reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        self.daily_stats = {
            'trades_executed': 0,
            'trades_won': 0,
            'trades_lost': 0,
            'total_pnl': 0.0,
            'time_stops': 0,
            'profit_targets': 0,
            'stop_losses': 0,
            'expired_otm': 0
        }

    def expire_positions(self) -> None:
        """Handle end-of-day expiration"""
        positions_to_expire = list(self.active_positions.keys())

        for position_id in positions_to_expire:
            position = self.active_positions[position_id]

            # Check if expired OTM
            if position.unrealized_pnl > 0:
                position.state = ZeroDTEState.EXPIRED
                self.daily_stats['expired_otm'] += 1
                reason = "Expired OTM"
            else:
                reason = "Expired ITM"

            self.close_0dte_position(position_id, reason)

    def get_strategy_summary(self) -> dict[str, Any]:
        """Get comprehensive strategy summary"""
        active_by_type = defaultdict(int)
        total_exposure = 0.0

        for position in self.active_positions.values():
            active_by_type[position.strategy_type.name] += 1
            total_exposure += position.max_loss

        win_rate = (self.daily_stats['trades_won'] /
                   self.daily_stats['trades_executed']
                   if self.daily_stats['trades_executed'] > 0 else 0)

        return {
            'strategy': 'ZeroDTE',
            'state': self.state,
            'active_positions': len(self.active_positions),
            'today_trades': self.today_trades,
            'positions_by_type': dict(active_by_type),
            'total_exposure': total_exposure,
            'daily_stats': self.daily_stats.copy(),
            'win_rate': win_rate,
            'market_conditions': {
                'spot_price': self.current_conditions.spot_price if self.current_conditions else 0,
                'vix': self.current_conditions.vix if self.current_conditions else 0,
                'market_phase': self.current_conditions.market_phase.name if self.current_conditions else 'UNKNOWN'
            }
        }

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create components
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.01,
        max_portfolio_risk=0.05,
        max_loss_per_trade=0.005
    )

    config = {
        'max_positions': 2,
        'profit_target': 0.25,
        'stop_loss': 2.0,
        'entry_delay_minutes': 1
    }

    # Create strategy
    strategy = ZeroDTEStrategy(event_manager, risk_profile, config)

    # Start strategy
    strategy.start()

    # Create intraday market data
    current_time = datetime.now()
    market_open = current_time.replace(hour=9, minute=30, second=0)

    # Generate 5-minute bars from market open
    time_index = pd.date_range(
        start=market_open,
        end=current_time,
        freq='5min'
    )

    # Simulate intraday price movement
    base_price = 450
    prices = base_price + np.cumsum(np.random.randn(len(time_index)) * 0.2)

    market_data = pd.DataFrame({
        'open': prices + np.random.randn(len(time_index)) * 0.1,
        'high': prices + abs(np.random.randn(len(time_index)) * 0.2),
        'low': prices - abs(np.random.randn(len(time_index)) * 0.2),
        'close': prices,
        'volume': np.random.randint(1000000, 3000000, len(time_index))
    }, index=time_index)

    # Process market data
    signals = strategy.generate_signals(market_data)

    # Display results

    if signals:
        signal = signals[0]
        setup = signal.metadata.get('setup_data', {})

    # Get strategy summary
    summary = strategy.get_strategy_summary()

    # Stop strategy
    strategy.stop()

