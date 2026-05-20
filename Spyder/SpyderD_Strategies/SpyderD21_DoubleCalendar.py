#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD21_DoubleCalendar.py
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
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum, auto
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (

    BaseStrategy, TradingSignal, SignalStrength
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    SignalType, OptionType, SPY_CONTRACT_MULTIPLIER
)
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from Spyder.SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from Spyder.SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy Configuration
MAX_DOUBLE_CALENDAR_POSITIONS = 3
OPTIMAL_STRIKE_SEPARATION = 10.0  # Points between call and put strikes
MIN_STRIKE_SEPARATION = 5.0
MAX_STRIKE_SEPARATION = 20.0

# Time Spreads
MIN_NEAR_EXPIRY_DTE = 20
MAX_NEAR_EXPIRY_DTE = 35
MIN_TIME_SPREAD = 21          # Days between expiries
MAX_TIME_SPREAD = 35
OPTIMAL_TIME_SPREAD = 28

# Strike Selection
CALL_STRIKE_OFFSET = 5.0      # Points above ATM
PUT_STRIKE_OFFSET = 5.0       # Points below ATM
DELTA_NEUTRAL_TARGET = 0.0    # Target net delta

# IV Requirements
MIN_IV_RANK = 30
MAX_IV_RANK = 70
OPTIMAL_IV_RANK = 50
MIN_IV_TERM_PREMIUM = 0.02    # 2% premium for far expiry

# Position Management
PROFIT_TARGET_PERCENT = 25     # Close at 25% of max profit
STOP_LOSS_PERCENT = 40         # Close at 40% max loss
ADJUSTMENT_IV_CHANGE = 0.05    # 5% IV change triggers adjustment
THETA_DECAY_TARGET = 30        # Target daily theta

# Risk Limits
MAX_VEGA_EXPOSURE = 200        # Maximum vega per position
MAX_TOTAL_DEBIT = 5000         # Maximum debit per position
CORRELATION_WARNING = 0.80     # Strike correlation warning level

# ==============================================================================
# ENUMS
# ==============================================================================
class DoubleCalendarType(Enum):
    """Types of double calendar configurations"""
    SYMMETRIC = "symmetric"        # Equal distance from ATM
    SKEWED_BULLISH = "skewed_bullish"   # Calls closer to ATM
    SKEWED_BEARISH = "skewed_bearish"   # Puts closer to ATM
    WIDE = "wide"                  # Maximum strike separation
    TIGHT = "tight"                # Minimum strike separation

class IVRegime(Enum):
    """Implied volatility regime classification"""
    LOW = "low"                    # IV < 30th percentile
    NORMAL = "normal"              # 30th - 70th percentile
    HIGH = "high"                  # 70th - 90th percentile
    EXTREME = "extreme"            # > 90th percentile

class PositionState(Enum):
    """Double calendar position states"""
    BUILDING = auto()
    ESTABLISHED = auto()
    ADJUSTING = auto()
    REDUCING = auto()
    CLOSING = auto()
    COMPLETE = auto()

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class CalendarLeg:
    """Individual calendar spread leg"""
    option_type: OptionType
    strike: float
    near_expiry: datetime
    far_expiry: datetime
    near_premium: float
    far_premium: float
    net_debit: float
    delta: float
    gamma: float
    vega: float
    theta: float
    iv_near: float
    iv_far: float

@dataclass
class DoubleCalendarSetup:
    """Complete double calendar setup"""
    call_calendar: CalendarLeg
    put_calendar: CalendarLeg
    calendar_type: DoubleCalendarType
    total_debit: float
    max_profit: float
    profit_zone: tuple[float, float]
    breakeven_points: list[float]
    net_delta: float
    net_vega: float
    net_theta: float
    strike_correlation: float
    iv_regime: IVRegime
    term_structure_slope: float
    expected_theta_decay: float

@dataclass
class IVAnalysis:
    """IV environment analysis"""
    current_iv: float
    iv_rank: float
    iv_percentile: float
    iv_regime: IVRegime
    term_structure: dict[int, float]  # DTE -> IV
    skew_profile: dict[float, float]  # Strike -> IV
    optimal_strikes: dict[str, float]  # 'call' and 'put' strikes
    term_structure_slope: float = 0.0

@dataclass
class DoubleCalendarPosition:
    """Active double calendar position"""
    position_id: str
    setup: DoubleCalendarSetup
    entry_time: datetime
    entry_price: float
    iv_at_entry: IVAnalysis
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    theta_collected: float = 0.0
    days_held: int = 0
    near_dte: int = 30
    far_dte: int = 58
    state: PositionState = PositionState.BUILDING
    adjustments: list[dict] = field(default_factory=list)
    current_iv_regime: IVRegime | None = None
    exit_time: datetime | None = None
    exit_reason: str | None = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DoubleCalendarStrategy(BaseStrategy):
    """
    Professional double calendar spread strategy implementation.

    Maximizes theta collection through synchronized call and put calendars
    with optimal strike placement and IV regime management.
    """

    def __init__(self, event_manager: EventManager, risk_profile: RiskProfile,
                 config: dict[str, Any] = None):
        """Initialize Double Calendar strategy"""
        super().__init__(
            name="Double Calendar Strategy",
            strategy_type="double_calendar",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config or {}
        )

        # Initialize components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.greeks_calculator = GreeksCalculator()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.volatility_regime = VolatilityRegimeAnalyzer()
        self.vix_analyzer = VIXAnalyzer()

        # Strategy state
        self.active_positions: dict[str, DoubleCalendarPosition] = {}
        self.current_iv_analysis: IVAnalysis | None = None
        self.portfolio_theta: float = 0.0
        self.portfolio_vega: float = 0.0

        # Configuration
        self.max_positions = config.get('max_positions', MAX_DOUBLE_CALENDAR_POSITIONS)
        self.target_theta = config.get('target_theta', THETA_DECAY_TARGET)
        self.allow_skewed = config.get('allow_skewed', True)
        self.dynamic_sizing = config.get('dynamic_sizing', True)

        # Performance tracking
        self.performance_stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'total_theta_collected': 0.0,
            'avg_holding_period': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'iv_regime_performance': {
                'low': {'trades': 0, 'wins': 0},
                'normal': {'trades': 0, 'wins': 0},
                'high': {'trades': 0, 'wins': 0}
            }
        }

        self.logger.info("Initialized %s", self.name)

    # ==========================================================================
    # IV ANALYSIS
    # ==========================================================================

    def _analyze_iv_environment(self, market_data: pd.DataFrame) -> IVAnalysis:
        """Comprehensive IV environment analysis"""
        try:
            current_price = market_data['close'].iloc[-1]

            # Basic IV metrics
            current_iv = self._get_current_iv(market_data)
            iv_rank = self._calculate_iv_rank(market_data)
            iv_percentile = self._calculate_iv_percentile(market_data)

            # Determine IV regime
            if iv_rank < 30:
                iv_regime = IVRegime.LOW
            elif iv_rank < 70:
                iv_regime = IVRegime.NORMAL
            elif iv_rank < 90:
                iv_regime = IVRegime.HIGH
            else:
                iv_regime = IVRegime.EXTREME

            # Term structure analysis
            term_structure = self._analyze_term_structure(current_iv)
            term_slope = self._calculate_term_structure_slope(term_structure)

            # Skew analysis
            skew_profile = self._analyze_volatility_skew(current_price, current_iv)

            # Optimal strike selection
            optimal_strikes = self._select_optimal_strikes(
                current_price, skew_profile, iv_regime
            )

            analysis = IVAnalysis(
                current_iv=current_iv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                iv_regime=iv_regime,
                term_structure=term_structure,
                skew_profile=skew_profile,
                optimal_strikes=optimal_strikes,
                term_structure_slope=term_slope
            )

            self.current_iv_analysis = analysis
            return analysis

        except Exception as e:
            self.logger.error("Error analyzing IV environment: %s", e)
            return self._create_default_iv_analysis()

    def _get_current_iv(self, market_data: pd.DataFrame) -> float:
        """Get current implied volatility"""
        if 'iv' in market_data.columns:
            return market_data['iv'].iloc[-1]

        # Calculate from returns
        returns = market_data['close'].pct_change().dropna()
        return returns.std() * np.sqrt(252)

    def _calculate_iv_rank(self, market_data: pd.DataFrame) -> float:
        """Calculate IV rank over past year"""
        if 'iv' not in market_data.columns:
            return 50.0

        iv_series = market_data['iv'].iloc[-252:]
        current_iv = iv_series.iloc[-1]

        min_iv = iv_series.min()
        max_iv = iv_series.max()

        if max_iv > min_iv:
            return ((current_iv - min_iv) / (max_iv - min_iv)) * 100
        return 50.0

    def _calculate_iv_percentile(self, market_data: pd.DataFrame) -> float:
        """Calculate IV percentile"""
        if 'iv' not in market_data.columns:
            return 50.0

        iv_series = market_data['iv'].iloc[-252:]
        current_iv = iv_series.iloc[-1]

        return stats.percentileofscore(iv_series, current_iv)

    def _analyze_term_structure(self, base_iv: float) -> dict[int, float]:
        """Analyze IV term structure"""
        # In production, would get actual term structure from options chain
        # Simulate realistic term structure
        term_structure = {}

        # Common term structure patterns
        for dte in [7, 14, 21, 30, 45, 60, 90]:
            if dte < 30:
                # Near-term often has higher IV (event risk)
                adjustment = 0.02 * (30 - dte) / 30
            else:
                # Longer-term typically has slight premium
                adjustment = 0.01 * (dte - 30) / 60

            term_structure[dte] = base_iv + adjustment

        return term_structure

    def _calculate_term_structure_slope(self, term_structure: dict[int, float]) -> float:
        """Calculate slope of term structure"""
        if len(term_structure) < 2:
            return 0.0

        # Linear regression on term structure
        x = list(term_structure.keys())
        y = list(term_structure.values())

        slope, _ = np.polyfit(x, y, 1)
        return slope

    def _analyze_volatility_skew(self, spot: float, base_iv: float) -> dict[float, float]:
        """Analyze volatility skew across strikes"""
        # Simulate realistic skew
        skew_profile = {}

        for offset in range(-20, 21, 5):
            strike = spot + offset

            # Typical equity skew pattern
            if offset < 0:  # Put side
                skew_adjustment = abs(offset) * 0.002  # Higher IV for OTM puts
            else:  # Call side
                skew_adjustment = -offset * 0.001  # Lower IV for OTM calls

            skew_profile[strike] = base_iv + skew_adjustment

        return skew_profile

    def _select_optimal_strikes(self, spot: float, skew_profile: dict[float, float],
                              iv_regime: IVRegime) -> dict[str, float]:
        """Select optimal strikes for double calendar"""
        # Base strikes
        if iv_regime == IVRegime.LOW:
            # Wider strikes in low IV
            call_offset = CALL_STRIKE_OFFSET * 1.5
            put_offset = PUT_STRIKE_OFFSET * 1.5
        elif iv_regime == IVRegime.HIGH:
            # Tighter strikes in high IV
            call_offset = CALL_STRIKE_OFFSET * 0.8
            put_offset = PUT_STRIKE_OFFSET * 0.8
        else:
            call_offset = CALL_STRIKE_OFFSET
            put_offset = PUT_STRIKE_OFFSET

        # Round to valid strikes
        call_strike = round((spot + call_offset) / 5) * 5
        put_strike = round((spot - put_offset) / 5) * 5

        # Ensure minimum separation
        if call_strike - put_strike < MIN_STRIKE_SEPARATION:
            adjustment = (MIN_STRIKE_SEPARATION - (call_strike - put_strike)) / 2
            call_strike += adjustment
            put_strike -= adjustment

        return {
            'call': round(call_strike),
            'put': round(put_strike)
        }

    def _create_default_iv_analysis(self) -> IVAnalysis:
        """Create default IV analysis when data unavailable"""
        return IVAnalysis(
            current_iv=0.20,
            iv_rank=50.0,
            iv_percentile=50.0,
            iv_regime=IVRegime.NORMAL,
            term_structure={30: 0.20, 60: 0.21},
            skew_profile={},
            optimal_strikes={},
            term_structure_slope=0.0
        )

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate double calendar trading signals"""
        try:
            signals = []

            # Check position limits
            if len(self.active_positions) >= self.max_positions:
                return signals

            # Analyze IV environment
            iv_analysis = self._analyze_iv_environment(market_data)

            # Check IV regime suitability
            if not self._is_iv_suitable(iv_analysis):
                return signals

            # Create double calendar setup
            setup = self._create_double_calendar_setup(market_data, iv_analysis)

            if setup and self._validate_setup(setup):
                signal = self._create_trading_signal(setup, market_data, iv_analysis)
                if signal:
                    signals.append(signal)

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, market_data)
            return []

    def _is_iv_suitable(self, iv_analysis: IVAnalysis) -> bool:
        """Check if IV conditions suitable for double calendar"""
        # Check IV rank
        if not (MIN_IV_RANK <= iv_analysis.iv_rank <= MAX_IV_RANK):
            return False

        # Avoid extreme IV regimes
        if iv_analysis.iv_regime == IVRegime.EXTREME:
            return False

        # Check term structure
        return abs(iv_analysis.term_structure_slope) <= 0.001  # Not too steep

    def _create_double_calendar_setup(self, market_data: pd.DataFrame,
                                    iv_analysis: IVAnalysis) -> DoubleCalendarSetup | None:
        """Create double calendar spread setup"""
        try:
            current_price = market_data['close'].iloc[-1]

            # Get optimal strikes
            call_strike = iv_analysis.optimal_strikes.get('call', current_price + CALL_STRIKE_OFFSET)  # noqa: E501
            put_strike = iv_analysis.optimal_strikes.get('put', current_price - PUT_STRIKE_OFFSET)

            # Select expiries
            near_expiry, far_expiry = self._select_optimal_expiries()

            # Create call calendar
            call_calendar = self._create_calendar_leg(
                OptionType.CALL, call_strike, near_expiry, far_expiry,
                current_price, iv_analysis
            )

            # Create put calendar
            put_calendar = self._create_calendar_leg(
                OptionType.PUT, put_strike, near_expiry, far_expiry,
                current_price, iv_analysis
            )

            # Calculate combined metrics
            total_debit = call_calendar.net_debit + put_calendar.net_debit

            # Determine calendar type
            calendar_type = self._determine_calendar_type(
                call_strike, put_strike, current_price
            )

            # Calculate profit zone and breakevens
            profit_zone, breakevens = self._calculate_profit_zones(
                call_calendar, put_calendar, current_price
            )

            # Calculate max profit
            max_profit = self._estimate_max_profit(
                call_calendar, put_calendar, total_debit
            )

            # Net Greeks
            net_delta = call_calendar.delta + put_calendar.delta
            net_vega = call_calendar.vega + put_calendar.vega
            net_theta = call_calendar.theta + put_calendar.theta

            # Strike correlation
            strike_correlation = self._calculate_strike_correlation(
                call_strike, put_strike, current_price
            )

            # Expected theta decay
            expected_theta = net_theta * SPY_CONTRACT_MULTIPLIER

            setup = DoubleCalendarSetup(
                call_calendar=call_calendar,
                put_calendar=put_calendar,
                calendar_type=calendar_type,
                total_debit=total_debit * SPY_CONTRACT_MULTIPLIER,
                max_profit=max_profit,
                profit_zone=profit_zone,
                breakeven_points=breakevens,
                net_delta=net_delta,
                net_vega=net_vega,
                net_theta=net_theta,
                strike_correlation=strike_correlation,
                iv_regime=iv_analysis.iv_regime,
                term_structure_slope=iv_analysis.term_structure_slope,
                expected_theta_decay=expected_theta
            )

            return setup

        except Exception as e:
            self.logger.error("Error creating double calendar setup: %s", e)
            return None

    def _select_optimal_expiries(self) -> tuple[datetime, datetime]:
        """Select optimal expiration dates"""
        current_date = datetime.now(UTC)

        # Near expiry target
        near_target = current_date + timedelta(days=28)
        near_expiry = self._next_expiry_after(near_target)

        # Ensure within range
        near_dte = (near_expiry - current_date).days
        if near_dte < MIN_NEAR_EXPIRY_DTE:
            near_expiry = self._next_expiry_after(current_date + timedelta(days=MIN_NEAR_EXPIRY_DTE))  # noqa: E501
        elif near_dte > MAX_NEAR_EXPIRY_DTE:
            near_expiry = self._prev_expiry_before(current_date + timedelta(days=MAX_NEAR_EXPIRY_DTE))  # noqa: E501

        # Far expiry with optimal spread
        far_target = near_expiry + timedelta(days=OPTIMAL_TIME_SPREAD)
        far_expiry = self._next_expiry_after(far_target)

        return near_expiry, far_expiry

    def _next_expiry_after(self, target: datetime) -> datetime:
        """Find next Friday expiry after target"""
        days_to_friday = (4 - target.weekday()) % 7
        if days_to_friday == 0:
            days_to_friday = 7
        return target + timedelta(days=days_to_friday)

    def _prev_expiry_before(self, target: datetime) -> datetime:
        """Find previous Friday expiry before target"""
        days_from_friday = (target.weekday() - 4) % 7
        if days_from_friday == 0:
            days_from_friday = 7
        return target - timedelta(days=days_from_friday)

    def _create_calendar_leg(self, option_type: OptionType, strike: float,
                           near_expiry: datetime, far_expiry: datetime,
                           spot: float, iv_analysis: IVAnalysis) -> CalendarLeg:
        """Create individual calendar leg"""
        # Get IVs for each expiry
        near_dte = (near_expiry - datetime.now(UTC)).days
        far_dte = (far_expiry - datetime.now(UTC)).days

        near_iv = iv_analysis.term_structure.get(near_dte, iv_analysis.current_iv)
        far_iv = iv_analysis.term_structure.get(far_dte, iv_analysis.current_iv * 1.02)

        # Calculate premiums
        near_premium = self._calculate_option_premium(
            strike, spot, near_expiry, near_iv, option_type
        )
        far_premium = self._calculate_option_premium(
            strike, spot, far_expiry, far_iv, option_type
        )

        # Net debit
        net_debit = far_premium - near_premium

        # Calculate Greeks
        greeks = self._calculate_calendar_greeks(
            strike, spot, near_expiry, far_expiry, near_iv, far_iv, option_type
        )

        return CalendarLeg(
            option_type=option_type,
            strike=strike,
            near_expiry=near_expiry,
            far_expiry=far_expiry,
            near_premium=near_premium,
            far_premium=far_premium,
            net_debit=net_debit,
            delta=greeks['delta'],
            gamma=greeks['gamma'],
            vega=greeks['vega'],
            theta=greeks['theta'],
            iv_near=near_iv,
            iv_far=far_iv
        )

    def _calculate_option_premium(self, strike: float, spot: float,
                                expiry: datetime, iv: float,
                                option_type: OptionType) -> float:
        """Calculate option premium using Black-Scholes"""
        dte = (expiry - datetime.now(UTC)).days / 365.0

        d1 = (np.log(spot / strike) + (0.02 + iv**2/2) * dte) / (iv * np.sqrt(dte))
        d2 = d1 - iv * np.sqrt(dte)

        if option_type == OptionType.CALL:
            premium = spot * stats.norm.cdf(d1) - strike * np.exp(-0.02 * dte) * stats.norm.cdf(d2)
        else:
            premium = strike * np.exp(-0.02 * dte) * stats.norm.cdf(-d2) - spot * stats.norm.cdf(-d1)  # noqa: E501

        return max(0.10, premium)

    def _calculate_calendar_greeks(self, strike: float, spot: float,
                                 near_expiry: datetime, far_expiry: datetime,
                                 near_iv: float, far_iv: float,
                                 option_type: OptionType) -> dict[str, float]:
        """Calculate net Greeks for calendar spread"""
        near_dte = (near_expiry - datetime.now(UTC)).days / 365.0
        far_dte = (far_expiry - datetime.now(UTC)).days / 365.0

        # Near option Greeks (short)
        near_d1 = (np.log(spot / strike) + (0.02 + near_iv**2/2) * near_dte) / (near_iv * np.sqrt(near_dte))  # noqa: E501

        if option_type == OptionType.CALL:
            near_delta = -stats.norm.cdf(near_d1)  # Negative because short
        else:
            near_delta = -(stats.norm.cdf(near_d1) - 1)

        near_gamma = -stats.norm.pdf(near_d1) / (spot * near_iv * np.sqrt(near_dte))
        near_vega = -spot * stats.norm.pdf(near_d1) * np.sqrt(near_dte) / 100
        near_theta = (spot * stats.norm.pdf(near_d1) * near_iv / (2 * np.sqrt(near_dte))) / 365

        # Far option Greeks (long)
        far_d1 = (np.log(spot / strike) + (0.02 + far_iv**2/2) * far_dte) / (far_iv * np.sqrt(far_dte))  # noqa: E501

        if option_type == OptionType.CALL:
            far_delta = stats.norm.cdf(far_d1)
        else:
            far_delta = stats.norm.cdf(far_d1) - 1

        far_gamma = stats.norm.pdf(far_d1) / (spot * far_iv * np.sqrt(far_dte))
        far_vega = spot * stats.norm.pdf(far_d1) * np.sqrt(far_dte) / 100
        far_theta = -(spot * stats.norm.pdf(far_d1) * far_iv / (2 * np.sqrt(far_dte))) / 365

        # Net Greeks
        return {
            'delta': near_delta + far_delta,
            'gamma': near_gamma + far_gamma,
            'vega': near_vega + far_vega,
            'theta': near_theta + far_theta
        }

    def _determine_calendar_type(self, call_strike: float, put_strike: float,
                               spot: float) -> DoubleCalendarType:
        """Determine type of double calendar"""
        call_distance = abs(call_strike - spot)
        put_distance = abs(put_strike - spot)
        total_width = call_strike - put_strike

        if abs(call_distance - put_distance) < 1:
            return DoubleCalendarType.SYMMETRIC
        elif call_distance < put_distance:
            return DoubleCalendarType.SKEWED_BULLISH
        elif put_distance < call_distance:
            return DoubleCalendarType.SKEWED_BEARISH
        elif total_width >= MAX_STRIKE_SEPARATION * 0.9:
            return DoubleCalendarType.WIDE
        else:
            return DoubleCalendarType.TIGHT

    def _calculate_profit_zones(self, call_calendar: CalendarLeg,
                              put_calendar: CalendarLeg,
                              spot: float) -> tuple[tuple[float, float], list[float]]:
        """Calculate profit zone and breakeven points"""
        # Simplified calculation
        # In production, would use option pricing model

        # Profit zone is typically between the strikes
        profit_zone = (put_calendar.strike, call_calendar.strike)

        # Breakevens approximately at strikes +/- net debit
        total_debit = call_calendar.net_debit + put_calendar.net_debit

        breakevens = [
            put_calendar.strike - total_debit * 1.5,
            call_calendar.strike + total_debit * 1.5
        ]

        return profit_zone, breakevens

    def _estimate_max_profit(self, call_calendar: CalendarLeg,
                           put_calendar: CalendarLeg,
                           total_debit: float) -> float:
        """Estimate maximum profit for double calendar"""
        # Max profit occurs when both calendars are at peak value
        # Typically 20-40% of debit for well-positioned calendars

        time_value_factor = 0.3  # Conservative estimate
        max_profit = total_debit * time_value_factor * SPY_CONTRACT_MULTIPLIER

        return max_profit

    def _calculate_strike_correlation(self, call_strike: float,
                                    put_strike: float, spot: float) -> float:
        """Calculate correlation between strike positions"""
        # Measure how related the two strikes are
        total_distance = call_strike - put_strike
        spot_position = (spot - put_strike) / total_distance

        # Correlation higher when spot is between strikes
        if 0 < spot_position < 1:
            correlation = 1 - 2 * abs(spot_position - 0.5)
        else:
            correlation = max(0, 1 - abs(spot_position - 0.5))

        return correlation

    def _validate_setup(self, setup: DoubleCalendarSetup) -> bool:
        """Validate double calendar setup"""
        # Check minimum debit
        if setup.total_debit > MAX_TOTAL_DEBIT:
            self.logger.info("Double calendar debit too high")
            return False

        # Check vega exposure
        if abs(setup.net_vega) * SPY_CONTRACT_MULTIPLIER > MAX_VEGA_EXPOSURE:
            self.logger.info("Vega exposure too high")
            return False

        # Check theta collection
        if setup.expected_theta_decay < self.target_theta * 0.5:
            self.logger.info("Insufficient theta decay")
            return False

        # Warn on high correlation
        if setup.strike_correlation > CORRELATION_WARNING:
            self.logger.warning("High strike correlation - reduced profit potential")

        return True

    def _create_trading_signal(self, setup: DoubleCalendarSetup,
                             market_data: pd.DataFrame,
                             iv_analysis: IVAnalysis) -> TradingSignal | None:
        """Convert setup to trading signal"""
        try:
            # Determine signal strength
            if setup.expected_theta_decay > self.target_theta and setup.iv_regime == IVRegime.NORMAL:  # noqa: E501
                strength = SignalStrength.STRONG
            elif setup.expected_theta_decay > self.target_theta * 0.7:
                strength = SignalStrength.MEDIUM
            else:
                strength = SignalStrength.WEAK

            # Calculate confidence
            confidence = self._calculate_signal_confidence(setup, iv_analysis)

            signal = TradingSignal(
                timestamp=datetime.now(UTC),
                signal_type=SignalType.ENTRY,
                strength=strength,
                confidence=confidence,
                metadata={
                    'strategy': 'double_calendar',
                    'setup': setup.__dict__,
                    'calendar_type': setup.calendar_type.value,
                    'strikes': {
                        'call': setup.call_calendar.strike,
                        'put': setup.put_calendar.strike
                    },
                    'total_debit': setup.total_debit,
                    'expected_theta': setup.expected_theta_decay,
                    'iv_regime': setup.iv_regime.value,
                    'profit_zone': setup.profit_zone,
                    'position_size': self._calculate_position_size(setup),
                    'stop_loss': setup.total_debit * (1 + STOP_LOSS_PERCENT / 100),
                    'profit_target': setup.total_debit * (1 - PROFIT_TARGET_PERCENT / 100)
                }
            )

            return signal

        except Exception as e:
            self.logger.error("Error creating trading signal: %s", e)
            return None

    def _calculate_signal_confidence(self, setup: DoubleCalendarSetup,
                                   iv_analysis: IVAnalysis) -> float:
        """Calculate trading signal confidence"""
        confidence = 50.0

        # IV rank factor
        if MIN_IV_RANK + 10 <= iv_analysis.iv_rank <= MAX_IV_RANK - 10:
            confidence += 10

        # Term structure factor
        if abs(iv_analysis.term_structure_slope) < 0.0005:
            confidence += 10

        # Expected theta factor
        if setup.expected_theta_decay > self.target_theta:
            confidence += 15

        # Strike correlation factor
        if 0.3 < setup.strike_correlation < 0.7:
            confidence += 10

        # Net delta neutrality
        if abs(setup.net_delta) < 0.05:
            confidence += 5

        return min(100, max(0, confidence))

    def _calculate_position_size(self, setup: DoubleCalendarSetup) -> int:
        """Calculate appropriate position size"""
        if not self.dynamic_sizing:
            return 1

        # Base size on IV regime
        if setup.iv_regime == IVRegime.NORMAL:
            base_size = 2
        else:
            base_size = 1

        # Adjust for expected theta
        if setup.expected_theta_decay > self.target_theta * 1.5:
            base_size += 1

        # Cap at maximum
        return min(base_size, 3)

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def manage_positions(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Manage existing double calendar positions"""
        try:
            signals = []
            current_price = market_data['close'].iloc[-1]

            # Update current IV analysis
            self._analyze_iv_environment(market_data)

            # Manage each position
            for _position_id, position in list(self.active_positions.items()):
                position_signals = self._manage_single_position(
                    position, market_data, current_price
                )
                signals.extend(position_signals)

            # Update portfolio Greeks
            self._update_portfolio_greeks()

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, market_data)
            return []

    def _manage_single_position(self, position: DoubleCalendarPosition,
                              market_data: pd.DataFrame,
                              current_price: float) -> list[TradingSignal]:
        """Manage individual double calendar position"""
        signals = []

        # Update position metrics
        self._update_position_metrics(position, current_price)

        # Check exit conditions
        if self._should_exit_position(position, current_price):
            exit_signal = self._create_exit_signal(position, current_price)
            if exit_signal:
                signals.append(exit_signal)
                self._close_position(position)

        # Check adjustment conditions
        elif self._should_adjust_position(position, current_price):
            adjustment_signals = self._create_adjustment_signals(position, current_price)
            signals.extend(adjustment_signals)

        return signals

    def _update_position_metrics(self, position: DoubleCalendarPosition,
                                current_price: float) -> None:
        """Update position value and metrics"""
        # Update days held
        position.days_held = (datetime.now(UTC) - position.entry_time).days

        # Update DTEs
        position.near_dte = (position.setup.call_calendar.near_expiry - datetime.now(UTC)).days
        position.far_dte = (position.setup.call_calendar.far_expiry - datetime.now(UTC)).days

        # Calculate current value
        current_value = self._calculate_position_value(position, current_price)
        position.current_value = current_value

        # Update P&L
        position.unrealized_pnl = current_value - position.setup.total_debit

        # Update theta collected
        position.theta_collected += position.setup.net_theta * SPY_CONTRACT_MULTIPLIER

        # Update current IV regime
        if self.current_iv_analysis:
            position.current_iv_regime = self.current_iv_analysis.iv_regime

    def _calculate_position_value(self, position: DoubleCalendarPosition,
                                current_price: float) -> float:
        """Calculate current position value"""
        # Simplified calculation
        # In production, would use option pricing model

        # Time decay factor
        time_decay = position.days_held / 30.0

        # Price movement factor
        price_in_zone = (position.setup.profit_zone[0] <= current_price <=
                        position.setup.profit_zone[1])

        if price_in_zone:
            # Position gaining value
            value_multiplier = 1 + (time_decay * 0.3)
        else:
            # Position losing value
            distance_from_zone = min(
                abs(current_price - position.setup.profit_zone[0]),
                abs(current_price - position.setup.profit_zone[1])
            )
            value_multiplier = 1 - (distance_from_zone / 100) * 0.5

        return position.setup.total_debit * value_multiplier

    def _should_exit_position(self, position: DoubleCalendarPosition,
                            current_price: float) -> bool:
        """Determine if position should be closed"""
        # Profit target hit
        if position.unrealized_pnl >= position.setup.max_profit * (PROFIT_TARGET_PERCENT / 100):
            position.exit_reason = "Profit target reached"
            return True

        # Stop loss hit
        if position.unrealized_pnl <= -position.setup.total_debit * (STOP_LOSS_PERCENT / 100):
            position.exit_reason = "Stop loss triggered"
            return True

        # Near expiry approaching
        if position.near_dte <= 7:
            position.exit_reason = "Near expiry approaching"
            return True

        # Price moved too far from profit zone
        if current_price < position.setup.breakeven_points[0] or \
           current_price > position.setup.breakeven_points[1]:
            position.exit_reason = "Price outside breakeven zone"
            return True

        # IV regime change
        if position.current_iv_regime == IVRegime.EXTREME:
            position.exit_reason = "IV regime change to extreme"
            return True

        return False

    def _should_adjust_position(self, position: DoubleCalendarPosition,
                              current_price: float) -> bool:
        """Determine if position needs adjustment"""
        # IV change threshold
        if self.current_iv_analysis:
            iv_change = abs(self.current_iv_analysis.current_iv -
                          position.iv_at_entry.current_iv)
            if iv_change > ADJUSTMENT_IV_CHANGE:
                return True

        # Price near edge of profit zone
        zone_buffer = 2.0  # Points from edge
        if (abs(current_price - position.setup.profit_zone[0]) < zone_buffer or
            abs(current_price - position.setup.profit_zone[1]) < zone_buffer):
            return True

        # Delta imbalance
        return abs(position.setup.net_delta) > 0.1

    def _create_exit_signal(self, position: DoubleCalendarPosition,
                          current_price: float) -> TradingSignal | None:
        """Create position exit signal"""
        try:
            signal = TradingSignal(
                timestamp=datetime.now(UTC),
                signal_type=SignalType.EXIT,
                strength=SignalStrength.STRONG,
                confidence=90.0,
                metadata={
                    'strategy': 'double_calendar',
                    'position_id': position.position_id,
                    'exit_reason': position.exit_reason,
                    'days_held': position.days_held,
                    'unrealized_pnl': position.unrealized_pnl,
                    'theta_collected': position.theta_collected,
                    'current_price': current_price,
                    'strikes': {
                        'call': position.setup.call_calendar.strike,
                        'put': position.setup.put_calendar.strike
                    }
                }
            )

            return signal

        except Exception as e:
            self.logger.error("Error creating exit signal: %s", e)
            return None

    def _create_adjustment_signals(self, position: DoubleCalendarPosition,
                                 current_price: float) -> list[TradingSignal]:
        """Create position adjustment signals"""
        signals = []

        # Roll strikes if needed
        if self._should_roll_strikes(position, current_price):
            roll_signal = self._create_roll_signal(position, current_price)
            if roll_signal:
                signals.append(roll_signal)

        # Adjust for delta neutrality
        if abs(position.setup.net_delta) > 0.10:
            delta_signal = self._create_delta_adjustment_signal(position)
            if delta_signal:
                signals.append(delta_signal)

        return signals

    def _should_roll_strikes(self, position: DoubleCalendarPosition,
                           current_price: float) -> bool:
        """Determine if strikes should be rolled"""
        # Check if price moved significantly from entry
        price_move = abs(current_price - position.entry_price) / position.entry_price
        return price_move > 0.03  # 3% move

    def _create_roll_signal(self, position: DoubleCalendarPosition,
                          current_price: float) -> TradingSignal | None:
        """Create strike roll signal"""
        try:
            # Determine new strikes
            new_call_strike = round((current_price + CALL_STRIKE_OFFSET) / 5) * 5
            new_put_strike = round((current_price - PUT_STRIKE_OFFSET) / 5) * 5

            signal = TradingSignal(
                timestamp=datetime.now(UTC),
                signal_type=SignalType.ADJUSTMENT,
                strength=SignalStrength.MEDIUM,
                confidence=75.0,
                metadata={
                    'strategy': 'double_calendar',
                    'position_id': position.position_id,
                    'adjustment_type': 'roll_strikes',
                    'old_strikes': {
                        'call': position.setup.call_calendar.strike,
                        'put': position.setup.put_calendar.strike
                    },
                    'new_strikes': {
                        'call': new_call_strike,
                        'put': new_put_strike
                    },
                    'current_price': current_price
                }
            )

            # Record adjustment
            position.adjustments.append({
                'timestamp': datetime.now(UTC),
                'type': 'roll_strikes',
                'details': signal.metadata
            })

            return signal

        except Exception as e:
            self.logger.error("Error creating roll signal: %s", e)
            return None

    def _create_delta_adjustment_signal(self, position: DoubleCalendarPosition) -> TradingSignal | None:  # noqa: E501
        """Create delta neutrality adjustment signal"""
        try:
            # Determine which side to adjust
            if position.setup.net_delta > 0:
                adjustment_side = 'call'
                adjustment_action = 'reduce'
            else:
                adjustment_side = 'put'
                adjustment_action = 'reduce'

            signal = TradingSignal(
                timestamp=datetime.now(UTC),
                signal_type=SignalType.ADJUSTMENT,
                strength=SignalStrength.MEDIUM,
                confidence=70.0,
                metadata={
                    'strategy': 'double_calendar',
                    'position_id': position.position_id,
                    'adjustment_type': 'delta_neutral',
                    'adjustment_side': adjustment_side,
                    'adjustment_action': adjustment_action,
                    'current_delta': position.setup.net_delta
                }
            )

            return signal

        except Exception as e:
            self.logger.error("Error creating delta adjustment signal: %s", e)
            return None

    def _close_position(self, position: DoubleCalendarPosition) -> None:
        """Close position and update tracking"""
        position.exit_time = datetime.now(UTC)
        position.state = PositionState.COMPLETE

        # Update performance stats
        self.performance_stats['total_trades'] += 1
        if position.unrealized_pnl > 0:
            self.performance_stats['winning_trades'] += 1

        self.performance_stats['total_theta_collected'] += position.theta_collected

        # Update best/worst trade
        if position.unrealized_pnl > self.performance_stats['best_trade']:
            self.performance_stats['best_trade'] = position.unrealized_pnl
        if position.unrealized_pnl < self.performance_stats['worst_trade']:
            self.performance_stats['worst_trade'] = position.unrealized_pnl

        # Update IV regime performance
        entry_regime = position.iv_at_entry.iv_regime.value
        if entry_regime in self.performance_stats['iv_regime_performance']:
            self.performance_stats['iv_regime_performance'][entry_regime]['trades'] += 1
            if position.unrealized_pnl > 0:
                self.performance_stats['iv_regime_performance'][entry_regime]['wins'] += 1

        # Remove from active positions
        del self.active_positions[position.position_id]

        self.logger.info(f"Closed double calendar position {position.position_id}: "
                        f"P&L: ${position.unrealized_pnl:.2f}, "
                        f"Theta collected: ${position.theta_collected:.2f}")

    def _update_portfolio_greeks(self) -> None:
        """Update total portfolio Greeks"""
        total_theta = 0.0
        total_vega = 0.0

        for position in self.active_positions.values():
            total_theta += position.setup.net_theta * SPY_CONTRACT_MULTIPLIER
            total_vega += position.setup.net_vega * SPY_CONTRACT_MULTIPLIER

        self.portfolio_theta = total_theta
        self.portfolio_vega = total_vega

    # ==========================================================================
    # ANALYSIS AND REPORTING
    # ==========================================================================

    def analyze_performance(self) -> dict[str, Any]:
        """Analyze strategy performance"""
        if self.performance_stats['total_trades'] == 0:
            return self.performance_stats

        # Calculate averages
        self.performance_stats['avg_holding_period'] = (
            sum(p.days_held for p in self.active_positions.values()) /
            max(1, len(self.active_positions))
        )

        # Win rate
        win_rate = (self.performance_stats['winning_trades'] /
                   self.performance_stats['total_trades'] * 100)
        self.performance_stats['win_rate'] = win_rate

        # Average trade
        total_pnl = self.performance_stats['best_trade'] + self.performance_stats['worst_trade']
        self.performance_stats['avg_trade'] = total_pnl / 2

        return self.performance_stats

    def get_position_summary(self) -> dict[str, Any]:
        """Get summary of current positions"""
        return {
            'active_positions': len(self.active_positions),
            'total_theta': self.portfolio_theta,
            'total_vega': self.portfolio_vega,
            'positions': [
                {
                    'id': pos.position_id,
                    'strikes': {
                        'call': pos.setup.call_calendar.strike,
                        'put': pos.setup.put_calendar.strike
                    },
                    'unrealized_pnl': pos.unrealized_pnl,
                    'days_held': pos.days_held,
                    'near_dte': pos.near_dte,
                    'state': pos.state.name
                }
                for pos in self.active_positions.values()
            ]
        }

    # ==========================================================================
    # EXECUTION
    # ==========================================================================

    def execute_signal(self, signal: TradingSignal) -> bool:
        """Execute trading signal"""
        try:
            if signal.signal_type == SignalType.ENTRY:
                return self._execute_entry(signal)
            elif signal.signal_type == SignalType.EXIT:
                return self._execute_exit(signal)
            elif signal.signal_type == SignalType.ADJUSTMENT:
                return self._execute_adjustment(signal)

            return False

        except Exception as e:
            self.logger.error("Error executing signal: %s", e)
            return False

    def _execute_entry(self, signal: TradingSignal) -> bool:
        """Execute entry signal"""
        try:
            # Create new position
            position = DoubleCalendarPosition(
                position_id=str(uuid.uuid4()),
                setup=self._reconstruct_setup_from_signal(signal),
                entry_time=datetime.now(UTC),
                entry_price=signal.metadata.get('current_price', 0),
                iv_at_entry=self.current_iv_analysis or self._create_default_iv_analysis()
            )

            # Add to active positions
            self.active_positions[position.position_id] = position

            # Emit position opened event
            self.event_manager.emit(EventType.POSITION_OPENED, {
                'strategy': self.name,
                'position_id': position.position_id,
                'setup': position.setup
            })

            self.logger.info("Opened double calendar position %s", position.position_id)
            return True

        except Exception as e:
            self.logger.error("Error executing entry: %s", e)
            return False

    def _execute_exit(self, signal: TradingSignal) -> bool:
        """Execute exit signal"""
        position_id = signal.metadata.get('position_id')
        if position_id in self.active_positions:
            position = self.active_positions[position_id]
            self._close_position(position)

            # Emit position closed event
            self.event_manager.emit(EventType.POSITION_CLOSED, {
                'strategy': self.name,
                'position_id': position_id,
                'pnl': position.unrealized_pnl
            })

            return True
        return False

    def _execute_adjustment(self, signal: TradingSignal) -> bool:
        """Execute adjustment signal"""
        position_id = signal.metadata.get('position_id')
        if position_id not in self.active_positions:
            return False

        adjustment_type = signal.metadata.get('adjustment_type')

        if adjustment_type == 'roll_strikes':
            # In production, would execute the roll
            self.logger.info("Rolling strikes for position %s", position_id)
        elif adjustment_type == 'delta_neutral':
            # In production, would adjust for delta
            self.logger.info("Adjusting delta for position %s", position_id)

        return True

    def _reconstruct_setup_from_signal(self, signal: TradingSignal) -> DoubleCalendarSetup:
        """Reconstruct setup from signal metadata"""
        # This would recreate the setup object from signal metadata
        # For now, return a placeholder
        metadata = signal.metadata

        # Create placeholder calendar legs
        call_leg = CalendarLeg(
            option_type=OptionType.CALL,
            strike=metadata['strikes']['call'],
            near_expiry=datetime.now(UTC) + timedelta(days=30),
            far_expiry=datetime.now(UTC) + timedelta(days=60),
            near_premium=10.0,
            far_premium=15.0,
            net_debit=5.0,
            delta=0.1,
            gamma=0.01,
            vega=0.5,
            theta=-0.05,
            iv_near=0.20,
            iv_far=0.21
        )

        put_leg = CalendarLeg(
            option_type=OptionType.PUT,
            strike=metadata['strikes']['put'],
            near_expiry=datetime.now(UTC) + timedelta(days=30),
            far_expiry=datetime.now(UTC) + timedelta(days=60),
            near_premium=10.0,
            far_premium=15.0,
            net_debit=5.0,
            delta=-0.1,
            gamma=0.01,
            vega=0.5,
            theta=-0.05,
            iv_near=0.20,
            iv_far=0.21
        )

        return DoubleCalendarSetup(
            call_calendar=call_leg,
            put_calendar=put_leg,
            calendar_type=DoubleCalendarType.SYMMETRIC,
            total_debit=metadata['total_debit'],
            max_profit=metadata.get('max_profit', 300),
            profit_zone=tuple(metadata['profit_zone']),
            breakeven_points=metadata.get('breakeven_points', []),
            net_delta=0.0,
            net_vega=1.0,
            net_theta=-0.1,
            strike_correlation=0.5,
            iv_regime=IVRegime.NORMAL,
            term_structure_slope=0.0,
            expected_theta_decay=metadata['expected_theta']
        )

    # ==========================================================================
    # CLEANUP
    # ==========================================================================

    def cleanup(self) -> None:
        """Cleanup strategy resources"""
        # Close all positions
        for position in list(self.active_positions.values()):
            position.exit_reason = "Strategy cleanup"
            self._close_position(position)

        # Log final performance
        self.logger.info("Double Calendar Strategy Final Performance: %s", self.analyze_performance())  # noqa: E501

        super().cleanup()

    # ------------------------------------------------------------------
    # BaseStrategy abstract contract
    # ------------------------------------------------------------------
    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate a generated signal meets minimum requirements."""
        return bool(signal and getattr(signal, 'symbol', None) and getattr(signal, 'quantity', 0) > 0)  # noqa: E501

    def calculate_position_size(self, signal: TradingSignal, account_value: float) -> int:
        """Return contract count scaled by account value and per-trade risk budget."""
        risk_budget = account_value * self.config.get('max_risk_per_trade', 0.02)
        premium_per_contract = getattr(signal, 'entry_price', 1.0) * 100 or 100
        return max(1, int(risk_budget / premium_per_contract))

    def should_exit_position(self, position: dict, current_data: dict) -> bool:
        """Return True when the position should be closed based on P&L thresholds."""
        pnl_pct = current_data.get('pnl_pct', 0.0)
        stop_loss = self.config.get('stop_loss_pct', -1.0)
        profit_target = self.config.get('profit_target_pct', 0.50)
        return pnl_pct <= stop_loss or pnl_pct >= profit_target


# ==============================================================================
# END OF FILE
# ==============================================================================
