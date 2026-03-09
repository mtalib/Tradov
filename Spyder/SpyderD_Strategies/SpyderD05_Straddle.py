#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD05_Straddle.py
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
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass
from enum import Enum, auto
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy.stats import norm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy, TradingSignal, SignalType, SignalStrength,
    StrategyPosition, EventManager, RiskProfile, Event
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    SPY_CONTRACT_MULTIPLIER,
    OPTIMAL_ENTRY_START,
    OPTIMAL_ENTRY_END
)
from Spyder.SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
MIN_IMPLIED_VOL_RANK = 20  # Minimum IV rank for entry
MAX_IMPLIED_VOL_RANK = 50  # Maximum IV rank (avoid when too expensive)
MIN_EXPECTED_MOVE = 0.015  # Minimum expected move (1.5%)
MAX_DAYS_TO_EXPIRY = 45
MIN_DAYS_TO_EXPIRY = 7

# Straddle/Strangle parameters
STRANGLE_DELTA = 0.30  # Delta for strangle strikes
STRADDLE_ATM_THRESHOLD = 0.50  # Strike within 0.5% of spot for straddle
MIN_PROFIT_TARGET = 0.25  # 25% profit target
MAX_LOSS_PERCENT = 0.50  # 50% max loss

# Event-based parameters
EARNINGS_WINDOW_DAYS = 3  # Days before/after earnings
FOMC_WINDOW_DAYS = 2  # Days before/after FOMC
HIGH_VOL_EVENTS = ['earnings', 'fomc', 'cpi', 'jobs_report', 'opex']

# Greeks thresholds
MIN_VEGA = 0.10  # Minimum vega exposure
MAX_THETA_DECAY = -0.05  # Maximum theta decay per day
MIN_GAMMA = 0.01  # Minimum gamma

# Position limits
MAX_STRADDLE_POSITIONS = 3
POSITION_SIZE_PERCENT = 0.015  # 1.5% of capital per position

# ==============================================================================
# ENUMS
# ==============================================================================
class StrategyType(Enum):
    """Straddle/Strangle strategy types"""
    LONG_STRADDLE = auto()
    LONG_STRANGLE = auto()
    SHORT_STRADDLE = auto()
    SHORT_STRANGLE = auto()

class VolatilityRegime(Enum):
    """Volatility regime classification"""
    LOW = auto()
    NORMAL = auto()
    ELEVATED = auto()
    HIGH = auto()

class EventType(Enum):
    """Market event types"""
    NONE = auto()
    EARNINGS = auto()
    FOMC = auto()
    ECONOMIC_DATA = auto()
    OPEX = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionLeg:
    """Single option leg for straddle/strangle"""
    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'call' or 'put'
    position: str  # 'long' or 'short'
    quantity: int
    entry_price: float
    current_price: float = 0.0
    iv: float = 0.0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0

@dataclass
class StraddlePosition:
    """Straddle/Strangle position structure"""
    position_id: str
    strategy_type: StrategyType
    call_leg: OptionLeg
    put_leg: OptionLeg
    entry_time: datetime
    expiry: datetime
    quantity: int

    # Pricing
    total_debit: float  # For long positions
    total_credit: float = 0.0  # For short positions
    current_value: float = 0.0

    # P&L
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    max_profit: float = float('inf')  # Unlimited for long
    max_loss: float = 0.0

    # Greeks (combined)
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0

    # Breakevens
    breakeven_up: float = 0.0
    breakeven_down: float = 0.0

    # Event tracking
    event_type: EventType = EventType.NONE
    event_date: datetime | None = None

    # Exit management
    exit_time: datetime | None = None
    exit_reason: str | None = None

    @property
    def is_long(self) -> bool:
        """Check if long position"""
        return self.strategy_type in [StrategyType.LONG_STRADDLE, StrategyType.LONG_STRANGLE]

    @property
    def days_to_expiry(self) -> int:
        """Days until expiration"""
        return (self.expiry - datetime.now()).days

    @property
    def expected_move(self) -> float:
        """Expected move based on straddle price"""
        if self.is_long:
            return self.total_debit / ((self.call_leg.strike + self.put_leg.strike) / 2)
        else:
            return self.total_credit / ((self.call_leg.strike + self.put_leg.strike) / 2)

    def update_greeks(self) -> None:
        """Update combined Greeks"""
        self.net_delta = self.call_leg.delta + self.put_leg.delta
        self.net_gamma = self.call_leg.gamma + self.put_leg.gamma
        self.net_theta = self.call_leg.theta + self.put_leg.theta
        self.net_vega = self.call_leg.vega + self.put_leg.vega

    def update_breakevens(self) -> None:
        """Update breakeven points"""
        if self.strategy_type == StrategyType.LONG_STRADDLE:
            # Same strike for both legs
            strike = self.call_leg.strike
            self.breakeven_up = strike + self.total_debit
            self.breakeven_down = strike - self.total_debit
        elif self.strategy_type == StrategyType.LONG_STRANGLE:
            # Different strikes
            self.breakeven_up = self.call_leg.strike + self.total_debit
            self.breakeven_down = self.put_leg.strike - self.total_debit

@dataclass
class VolatilityAnalysis:
    """Volatility analysis results"""
    current_iv: float
    iv_rank: float
    iv_percentile: float
    hv_20: float  # 20-day historical volatility
    hv_60: float  # 60-day historical volatility
    iv_hv_ratio: float
    term_structure: dict[int, float]  # DTE -> IV
    volatility_regime: VolatilityRegime
    upcoming_events: list[dict[str, Any]]
    expected_move_1sd: float
    expected_move_2sd: float

# ==============================================================================
# STRADDLE STRATEGY CLASS
# ==============================================================================
class StraddleStrategy(BaseStrategy):
    """
    Long straddle and strangle strategy implementation.

    Designed to profit from significant price movements in either direction,
    particularly effective before high-volatility events.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any]):
        """Initialize straddle strategy"""
        super().__init__("Straddle", event_manager, risk_profile, config)

        # Configuration
        self.max_positions = config.get('max_positions', MAX_STRADDLE_POSITIONS)
        self.position_size_pct = config.get('position_size_pct', POSITION_SIZE_PERCENT)
        self.use_straddles = config.get('use_straddles', True)
        self.use_strangles = config.get('use_strangles', True)
        self.min_iv_rank = config.get('min_iv_rank', MIN_IMPLIED_VOL_RANK)
        self.max_iv_rank = config.get('max_iv_rank', MAX_IMPLIED_VOL_RANK)

        # Components
        self.tech_indicators = TechnicalIndicators()
        self.greeks_calculator = GreeksCalculator()

        # Position tracking
        self.active_positions: dict[str, StraddlePosition] = {}
        self.position_history: list[StraddlePosition] = []

        # Market analysis
        self.volatility_analysis: VolatilityAnalysis | None = None
        self.upcoming_events: list[dict[str, Any]] = []

        # Performance tracking
        self.strategy_metrics = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_pnl': 0.0,
            'avg_holding_days': 0.0,
            'event_trades': 0,
            'non_event_trades': 0,
            'best_strategy': None  # straddle vs strangle
        }

        self.logger.info("StraddleStrategy initialized")

    # ==========================================================================
    # REQUIRED ABSTRACT METHOD IMPLEMENTATIONS
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate straddle/strangle trading signals"""
        signals = []

        try:
            # Check position limits
            if len(self.active_positions) >= self.max_positions:
                return signals

            # Update volatility analysis
            self._analyze_volatility(market_data)

            # Check for upcoming events
            self._check_upcoming_events()

            # Check entry conditions
            if not self._check_entry_conditions():
                return signals

            # Get current price
            current_price = market_data['close'].iloc[-1]

            # Determine optimal strategy
            strategy_type = self._determine_strategy_type(current_price)

            if strategy_type:
                signal = self._create_straddle_signal(strategy_type, current_price, market_data)
                if signal:
                    signals.append(signal)
                    self.logger.info(f"Generated {strategy_type.name} signal")

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_signals',
                'market_data_shape': market_data.shape
            })

        return signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate straddle/strangle signal"""
        try:
            # Check signal validity
            if not signal.is_valid():
                return False

            # Check straddle data
            straddle_data = signal.metadata.get('straddle_data')
            if not straddle_data:
                return False

            # Validate strikes
            if straddle_data['strategy_type'] == StrategyType.LONG_STRADDLE:
                # Both strikes should be the same (ATM)
                if straddle_data['call_strike'] != straddle_data['put_strike']:
                    return False
            else:  # STRANGLE
                # Strikes should be different
                if straddle_data['call_strike'] <= straddle_data['put_strike']:
                    return False

            # Validate expected move
            if straddle_data['expected_move'] < MIN_EXPECTED_MOVE:
                return False

            # Validate Greeks
            if straddle_data['vega'] < MIN_VEGA:
                return False

            return not straddle_data['theta'] < MAX_THETA_DECAY

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'validate_signal',
                'signal_id': signal.signal_id
            })
            return False

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size for straddle/strangle"""
        try:
            # Get account value and total debit
            account_value = self.risk_profile.account_size
            total_debit = signal.metadata['straddle_data']['total_debit']

            # Calculate contracts based on position size percentage
            max_position_value = account_value * self.position_size_pct
            contracts = int(max_position_value / (total_debit * SPY_CONTRACT_MULTIPLIER))

            # Apply limits
            contracts = max(1, min(contracts, 10))

            # Adjust for signal strength
            if signal.strength == SignalStrength.WEAK:
                contracts = max(1, contracts // 2)
            elif signal.strength == SignalStrength.VERY_STRONG:
                contracts = min(10, int(contracts * 1.5))

            # Reduce size for high IV
            if self.volatility_analysis and self.volatility_analysis.iv_rank > 80:
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
        """Determine if straddle/strangle should be exited"""
        try:
            # Get straddle position
            straddle_pos = self.active_positions.get(position.position_id)
            if not straddle_pos:
                return False, ""

            # Update position value and Greeks
            self._update_position(straddle_pos, market_data)

            # Check profit target
            profit_pct = straddle_pos.unrealized_pnl / straddle_pos.total_debit
            if profit_pct >= MIN_PROFIT_TARGET:
                return True, f"Profit target reached: {profit_pct:.1%}"

            # Check stop loss
            if profit_pct <= -MAX_LOSS_PERCENT:
                return True, f"Stop loss triggered: {profit_pct:.1%}"

            # Check days to expiry
            if straddle_pos.days_to_expiry <= 3:
                if profit_pct > -0.20:  # Exit if not too far underwater
                    return True, f"Near expiry exit: {straddle_pos.days_to_expiry} DTE"

            # Check if event has passed
            if straddle_pos.event_type != EventType.NONE and straddle_pos.event_date:
                if datetime.now() > straddle_pos.event_date + timedelta(days=1):
                    return True, "Event has passed"

            # Check theta decay
            if straddle_pos.net_theta < -0.10:  # Losing more than 10% per day
                if profit_pct < -0.10:  # And already down
                    return True, "Excessive theta decay"

            # Check if price moved beyond breakevens
            current_price = market_data['close'].iloc[-1]
            if (current_price > straddle_pos.breakeven_up * 1.02 or
                current_price < straddle_pos.breakeven_down * 0.98):
                return True, "Price moved beyond profitable range"

            return False, ""

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'should_exit_position',
                'position_id': position.position_id
            })
            return False, ""

    # ==========================================================================
    # VOLATILITY ANALYSIS METHODS
    # ==========================================================================

    def _analyze_volatility(self, market_data: pd.DataFrame) -> None:
        """Analyze volatility conditions"""
        try:
            close_prices = market_data['close']

            # Calculate returns
            returns = close_prices.pct_change().dropna()

            # Historical volatility
            hv_20 = returns.rolling(20).std() * np.sqrt(252)
            hv_60 = returns.rolling(60).std() * np.sqrt(252)

            current_hv_20 = hv_20.iloc[-1]
            current_hv_60 = hv_60.iloc[-1]

            # IV rank (simplified - would use actual IV data)
            # For now, estimate based on recent HV
            hv_90d = returns.rolling(90).std() * np.sqrt(252)
            iv_rank = (hv_90d <= current_hv_20).sum() / len(hv_90d) * 100

            # Estimate current IV (simplified)
            current_iv = current_hv_20 * 1.2  # IV typically trades at premium to HV

            # IV percentile
            iv_percentile = iv_rank  # Simplified

            # Determine volatility regime
            if current_iv < 0.15:
                vol_regime = VolatilityRegime.LOW
            elif current_iv < 0.25:
                vol_regime = VolatilityRegime.NORMAL
            elif current_iv < 0.35:
                vol_regime = VolatilityRegime.ELEVATED
            else:
                vol_regime = VolatilityRegime.HIGH

            # Expected moves
            current_price = close_prices.iloc[-1]
            days_to_expiry = 30  # Default
            time_factor = np.sqrt(days_to_expiry / 365)

            expected_move_1sd = current_price * current_iv * time_factor
            expected_move_2sd = expected_move_1sd * 2

            # Create analysis object
            self.volatility_analysis = VolatilityAnalysis(
                current_iv=current_iv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                hv_20=current_hv_20,
                hv_60=current_hv_60,
                iv_hv_ratio=current_iv / current_hv_20 if current_hv_20 > 0 else 1,
                term_structure={},  # Would populate with actual term structure
                volatility_regime=vol_regime,
                upcoming_events=self.upcoming_events,
                expected_move_1sd=expected_move_1sd,
                expected_move_2sd=expected_move_2sd
            )

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_analyze_volatility'})

    def _check_upcoming_events(self) -> None:
        """Check for upcoming volatility events"""
        # In production, would check actual event calendar
        # For now, simulate with placeholder
        self.upcoming_events = []

        # Example: Check if it's near earnings season (quarterly)
        current_month = datetime.now().month
        if current_month in [1, 4, 7, 10]:  # Earnings months
            self.upcoming_events.append({
                'type': EventType.EARNINGS,
                'date': datetime.now() + timedelta(days=5),
                'impact': 'high'
            })

        # Check for FOMC (simplified - every 6 weeks)
        days_since_epoch = (datetime.now() - datetime(2024, 1, 1)).days
        if days_since_epoch % 42 < 7:  # Within a week of 6-week cycle
            self.upcoming_events.append({
                'type': EventType.FOMC,
                'date': datetime.now() + timedelta(days=3),
                'impact': 'high'
            })

    # ==========================================================================
    # ENTRY CONDITION METHODS
    # ==========================================================================

    def _check_entry_conditions(self) -> bool:
        """Check if conditions are suitable for straddle/strangle entry"""
        if not self.volatility_analysis:
            return False

        # Check IV rank
        if not (self.min_iv_rank <= self.volatility_analysis.iv_rank <= self.max_iv_rank):
            self.logger.debug(f"IV rank out of range: {self.volatility_analysis.iv_rank}")
            return False

        # Check expected move
        expected_move_pct = (self.volatility_analysis.expected_move_1sd /
                           self.volatility_analysis.current_iv)
        if expected_move_pct < MIN_EXPECTED_MOVE:
            self.logger.debug(f"Expected move too small: {expected_move_pct:.3f}")
            return False

        # Check time window
        current_time = datetime.now().time()
        if not (OPTIMAL_ENTRY_START <= current_time <= OPTIMAL_ENTRY_END):
            return False

        # Prefer entry before events
        has_upcoming_event = len(self.upcoming_events) > 0
        if not has_upcoming_event and self.volatility_analysis.iv_rank < 40:
            self.logger.debug("No upcoming events and IV rank too low")
            return False

        return True

    def _determine_strategy_type(self, current_price: float) -> StrategyType | None:
        """Determine optimal strategy type based on conditions"""
        if not self.volatility_analysis:
            return None

        # High IV favors strangles (cheaper than straddles)
        if self.volatility_analysis.iv_rank > 70:
            if self.use_strangles:
                return StrategyType.LONG_STRANGLE
            elif self.use_straddles:
                return StrategyType.LONG_STRADDLE

        # Moderate IV with upcoming event favors straddles
        elif self.upcoming_events and self.volatility_analysis.iv_rank > 30:
            if self.use_straddles:
                return StrategyType.LONG_STRADDLE
            elif self.use_strangles:
                return StrategyType.LONG_STRANGLE

        # Low IV but high expected move favors straddles
        elif self.volatility_analysis.expected_move_1sd / current_price > 0.02:
            if self.use_straddles:
                return StrategyType.LONG_STRADDLE

        return None

    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================

    def _create_straddle_signal(self, strategy_type: StrategyType,
                               current_price: float,
                               market_data: pd.DataFrame) -> TradingSignal | None:
        """Create straddle/strangle trading signal"""
        try:
            # Determine strikes
            if strategy_type == StrategyType.LONG_STRADDLE:
                # ATM straddle
                strike = round(current_price)  # Round to nearest dollar
                call_strike = put_strike = strike
            else:  # LONG_STRANGLE
                # OTM strangle
                call_strike = round(current_price + current_price * 0.02)  # 2% OTM
                put_strike = round(current_price - current_price * 0.02)   # 2% OTM

            # Calculate option prices and Greeks (simplified)
            dte = 30  # Default 30 DTE
            option_data = self._calculate_option_metrics(
                current_price, call_strike, put_strike, dte
            )

            if not option_data:
                return None

            # Calculate signal strength
            strength = self._calculate_signal_strength(option_data)

            # Determine if event-driven
            event_info = self._get_nearest_event()

            # Create signal
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol='SPY',
                strength=strength,
                confidence=option_data['probability_profit'],
                entry_price=current_price,
                stop_loss=0,  # Managed differently
                take_profit=0,  # Managed differently
                position_size=1,  # Will be calculated
                timestamp=datetime.now(),
                expires_at=datetime.now() + timedelta(minutes=15),
                metadata={
                    'strategy': 'straddle',
                    'straddle_data': {
                        'strategy_type': strategy_type,
                        'call_strike': call_strike,
                        'put_strike': put_strike,
                        'expiry_days': dte,
                        'total_debit': option_data['total_cost'],
                        'expected_move': option_data['expected_move'],
                        'breakeven_up': option_data['breakeven_up'],
                        'breakeven_down': option_data['breakeven_down'],
                        'delta': option_data['net_delta'],
                        'gamma': option_data['net_gamma'],
                        'theta': option_data['net_theta'],
                        'vega': option_data['net_vega'],
                        'event_type': event_info['type'] if event_info else EventType.NONE,
                        'event_date': event_info['date'] if event_info else None
                    }
                }
            )

            return signal

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_create_straddle_signal'})
            return None

    def _calculate_option_metrics(self, spot: float, call_strike: float,
                                 put_strike: float, dte: int) -> dict[str, Any] | None:
        """Calculate option prices and Greeks"""
        try:
            # Use volatility from analysis
            if not self.volatility_analysis:
                return None

            iv = self.volatility_analysis.current_iv
            r = 0.05  # Risk-free rate
            t = dte / 365

            # Calculate call option metrics
            call_price, call_greeks = self._black_scholes_call(spot, call_strike, t, r, iv)

            # Calculate put option metrics
            put_price, put_greeks = self._black_scholes_put(spot, put_strike, t, r, iv)

            # Total cost
            total_cost = call_price + put_price

            # Breakevens
            if call_strike == put_strike:  # Straddle
                breakeven_up = call_strike + total_cost
                breakeven_down = put_strike - total_cost
            else:  # Strangle
                breakeven_up = call_strike + total_cost
                breakeven_down = put_strike - total_cost

            # Expected move
            expected_move = total_cost

            # Combined Greeks
            net_delta = call_greeks['delta'] + put_greeks['delta']
            net_gamma = call_greeks['gamma'] + put_greeks['gamma']
            net_theta = call_greeks['theta'] + put_greeks['theta']
            net_vega = call_greeks['vega'] + put_greeks['vega']

            # Probability of profit (simplified)
            # Based on probability of moving beyond breakevens
            move_required = min(
                abs(breakeven_up - spot) / spot,
                abs(spot - breakeven_down) / spot
            )
            probability_profit = 2 * norm.cdf(move_required / (iv * np.sqrt(t))) - 1

            return {
                'call_price': call_price,
                'put_price': put_price,
                'total_cost': total_cost,
                'breakeven_up': breakeven_up,
                'breakeven_down': breakeven_down,
                'expected_move': expected_move,
                'net_delta': net_delta,
                'net_gamma': net_gamma,
                'net_theta': net_theta,
                'net_vega': net_vega,
                'probability_profit': max(0.3, min(0.7, probability_profit))
            }

        except Exception as e:
            self.error_handler.handle_error(e, {'method': '_calculate_option_metrics'})
            return None

    def _black_scholes_call(self, S: float, K: float, T: float, r: float,
                           sigma: float) -> tuple[float, dict[str, float]]:
        """Calculate Black-Scholes call price and Greeks"""
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

        # Greeks
        delta = norm.cdf(d1)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) -
                r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100

        return call_price, {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega
        }

    def _black_scholes_put(self, S: float, K: float, T: float, r: float,
                          sigma: float) -> tuple[float, dict[str, float]]:
        """Calculate Black-Scholes put price and Greeks"""
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

        # Greeks
        delta = -norm.cdf(-d1)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        theta = (-S * norm.pdf(d1) * sigma / (2 * np.sqrt(T)) +
                r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
        vega = S * norm.pdf(d1) * np.sqrt(T) / 100

        return put_price, {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega
        }

    def _calculate_signal_strength(self, option_data: dict[str, Any]) -> SignalStrength:
        """Calculate signal strength based on option metrics"""
        score = 0

        # Expected move score
        if option_data['expected_move'] > option_data['total_cost'] * 0.3:
            score += 30
        elif option_data['expected_move'] > option_data['total_cost'] * 0.2:
            score += 20
        elif option_data['expected_move'] > option_data['total_cost'] * 0.15:
            score += 10

        # Vega score (want high vega for long vol)
        if option_data['net_vega'] > 0.5:
            score += 30
        elif option_data['net_vega'] > 0.3:
            score += 20
        elif option_data['net_vega'] > 0.2:
            score += 10

        # Theta score (less negative is better)
        if option_data['net_theta'] > -0.03:
            score += 20
        elif option_data['net_theta'] > -0.05:
            score += 10

        # Event bonus
        if self.upcoming_events:
            score += 20

        # Convert score to strength
        if score >= 80:
            return SignalStrength.VERY_STRONG
        elif score >= 60:
            return SignalStrength.STRONG
        elif score >= 40:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def _get_nearest_event(self) -> dict[str, Any] | None:
        """Get nearest upcoming event"""
        if not self.upcoming_events:
            return None

        # Sort by date and return nearest
        sorted_events = sorted(self.upcoming_events, key=lambda x: x['date'])
        return sorted_events[0] if sorted_events else None

    # ==========================================================================
    # POSITION MANAGEMENT METHODS
    # ==========================================================================

    def open_straddle_position(self, signal: TradingSignal) -> StraddlePosition | None:
        """Open a new straddle/strangle position"""
        try:
            straddle_data = signal.metadata['straddle_data']

            # Create option legs
            expiry = datetime.now() + timedelta(days=straddle_data['expiry_days'])

            call_leg = OptionLeg(
                symbol=f"SPY_C_{straddle_data['call_strike']}_{expiry.strftime('%Y%m%d')}",
                strike=straddle_data['call_strike'],
                expiry=expiry,
                option_type='call',
                position='long',
                quantity=signal.position_size,
                entry_price=0,  # Would be filled by broker
                delta=straddle_data['delta'] / 2,  # Approximate
                gamma=straddle_data['gamma'] / 2,
                theta=straddle_data['theta'] / 2,
                vega=straddle_data['vega'] / 2
            )

            put_leg = OptionLeg(
                symbol=f"SPY_P_{straddle_data['put_strike']}_{expiry.strftime('%Y%m%d')}",
                strike=straddle_data['put_strike'],
                expiry=expiry,
                option_type='put',
                position='long',
                quantity=signal.position_size,
                entry_price=0,  # Would be filled by broker
                delta=straddle_data['delta'] / 2,  # Approximate
                gamma=straddle_data['gamma'] / 2,
                theta=straddle_data['theta'] / 2,
                vega=straddle_data['vega'] / 2
            )

            # Create position
            position = StraddlePosition(
                position_id=str(uuid.uuid4()),
                strategy_type=straddle_data['strategy_type'],
                call_leg=call_leg,
                put_leg=put_leg,
                entry_time=datetime.now(),
                expiry=expiry,
                quantity=signal.position_size,
                total_debit=straddle_data['total_debit'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                max_loss=straddle_data['total_debit'] * signal.position_size * SPY_CONTRACT_MULTIPLIER,
                breakeven_up=straddle_data['breakeven_up'],
                breakeven_down=straddle_data['breakeven_down'],
                event_type=straddle_data.get('event_type', EventType.NONE),
                event_date=straddle_data.get('event_date')
            )

            # Update Greeks and breakevens
            position.update_greeks()
            position.update_breakevens()

            # Add to tracking
            self.active_positions[position.position_id] = position

            # Update metrics
            self.strategy_metrics['total_trades'] += 1
            if position.event_type != EventType.NONE:
                self.strategy_metrics['event_trades'] += 1
            else:
                self.strategy_metrics['non_event_trades'] += 1

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_OPENED,
                self.name,
                {
                    'position_id': position.position_id,
                    'strategy': position.strategy_type.name,
                    'debit': position.total_debit,
                    'event_driven': position.event_type != EventType.NONE
                }
            ))

            self.logger.info(f"Opened {position.strategy_type.name}: {position.position_id}")
            return position

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'open_straddle_position',
                'signal_id': signal.signal_id
            })
            return None

    def _update_position(self, position: StraddlePosition, market_data: pd.DataFrame) -> None:
        """Update straddle position pricing and Greeks"""
        try:
            current_price = market_data['close'].iloc[-1]
            days_remaining = position.days_to_expiry

            if days_remaining <= 0:
                # Expired
                position.current_value = 0
                position.unrealized_pnl = -position.total_debit
                return

            # Recalculate option values
            t = days_remaining / 365
            iv = self.volatility_analysis.current_iv if self.volatility_analysis else 0.25
            r = 0.05

            # Call value
            call_value, call_greeks = self._black_scholes_call(
                current_price, position.call_leg.strike, t, r, iv
            )

            # Put value
            put_value, put_greeks = self._black_scholes_put(
                current_price, position.put_leg.strike, t, r, iv
            )

            # Update leg Greeks
            position.call_leg.delta = call_greeks['delta']
            position.call_leg.gamma = call_greeks['gamma']
            position.call_leg.theta = call_greeks['theta']
            position.call_leg.vega = call_greeks['vega']
            position.call_leg.current_price = call_value

            position.put_leg.delta = put_greeks['delta']
            position.put_leg.gamma = put_greeks['gamma']
            position.put_leg.theta = put_greeks['theta']
            position.put_leg.vega = put_greeks['vega']
            position.put_leg.current_price = put_value

            # Update position values
            position.current_value = (call_value + put_value) * position.quantity * SPY_CONTRACT_MULTIPLIER
            position.unrealized_pnl = position.current_value - position.total_debit

            # Update combined Greeks
            position.update_greeks()

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_update_position',
                'position_id': position.position_id
            })

    def close_straddle_position(self, position_id: str, reason: str) -> bool:
        """Close straddle position"""
        try:
            position = self.active_positions.get(position_id)
            if not position:
                return False

            # Update final values
            position.realized_pnl = position.unrealized_pnl
            position.exit_time = datetime.now()
            position.exit_reason = reason

            # Move to history
            self.position_history.append(position)
            del self.active_positions[position_id]

            # Update metrics
            if position.realized_pnl > 0:
                self.strategy_metrics['winning_trades'] += 1
            self.strategy_metrics['total_pnl'] += position.realized_pnl

            # Calculate average holding days
            holding_days = (position.exit_time - position.entry_time).days
            total_days = sum((p.exit_time - p.entry_time).days for p in self.position_history)
            self.strategy_metrics['avg_holding_days'] = total_days / len(self.position_history)

            # Publish event
            self.event_manager.publish(Event.create(
                EventType.POSITION_CLOSED,
                self.name,
                {
                    'position_id': position_id,
                    'realized_pnl': position.realized_pnl,
                    'exit_reason': reason,
                    'holding_days': holding_days
                }
            ))

            self.logger.info(f"Closed position {position_id}: PnL ${position.realized_pnl:.2f}")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'close_straddle_position',
                'position_id': position_id
            })
            return False

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def get_strategy_summary(self) -> dict[str, Any]:
        """Get comprehensive strategy summary"""
        active_straddles = sum(1 for p in self.active_positions.values()
                              if p.strategy_type == StrategyType.LONG_STRADDLE)
        active_strangles = sum(1 for p in self.active_positions.values()
                              if p.strategy_type == StrategyType.LONG_STRANGLE)

        total_debit = sum(p.total_debit for p in self.active_positions.values())
        total_vega = sum(p.net_vega for p in self.active_positions.values())
        total_theta = sum(p.net_theta for p in self.active_positions.values())

        win_rate = (self.strategy_metrics['winning_trades'] /
                   self.strategy_metrics['total_trades']
                   if self.strategy_metrics['total_trades'] > 0 else 0)

        return {
            'strategy': 'Straddle',
            'state': self.state,
            'active_positions': {
                'straddles': active_straddles,
                'strangles': active_strangles,
                'total': len(self.active_positions)
            },
            'greeks': {
                'total_vega': total_vega,
                'total_theta': total_theta,
                'vega_per_position': total_vega / len(self.active_positions) if self.active_positions else 0
            },
            'exposure': {
                'total_debit': total_debit,
                'avg_debit': total_debit / len(self.active_positions) if self.active_positions else 0
            },
            'performance': {
                'total_trades': self.strategy_metrics['total_trades'],
                'win_rate': win_rate,
                'total_pnl': self.strategy_metrics['total_pnl'],
                'avg_holding_days': self.strategy_metrics['avg_holding_days'],
                'event_trades': self.strategy_metrics['event_trades']
            },
            'volatility': {
                'current_iv': self.volatility_analysis.current_iv if self.volatility_analysis else 0,
                'iv_rank': self.volatility_analysis.iv_rank if self.volatility_analysis else 0,
                'regime': self.volatility_analysis.volatility_regime.name if self.volatility_analysis else 'UNKNOWN'
            }
        }

# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    # Test straddle strategy
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.015,
        max_portfolio_risk=0.05,
        max_loss_per_trade=0.01
    )

    config = {
        'max_positions': 3,
        'use_straddles': True,
        'use_strangles': True,
        'min_iv_rank': 30,
        'max_iv_rank': 80
    }

    strategy = StraddleStrategy(event_manager, risk_profile, config)
    strategy.start()

    # Create sample market data with some volatility
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    base_price = 450

    # Add some volatility
    returns = np.random.randn(100) * 0.005  # 0.5% moves
    prices = base_price * np.exp(np.cumsum(returns))

    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices * (1 + np.random.randn(100) * 0.001),
        'high': prices * (1 + abs(np.random.randn(100) * 0.002)),
        'low': prices * (1 - abs(np.random.randn(100) * 0.002)),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })

    # Process market data
    signals = strategy.generate_signals(market_data)

    # Print results

    if strategy.volatility_analysis:
        pass


    for signal in signals:
        straddle_data = signal.metadata.get('straddle_data', {})

    # Get summary
    summary = strategy.get_strategy_summary()

    strategy.stop()
