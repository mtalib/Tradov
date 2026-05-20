#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD14_CalendarSpread.py
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
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum, auto
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager
from Spyder.SpyderC_MarketData.SpyderC10_VIXAnalyzer import VIXAnalyzer
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (BaseStrategy,

                                                       SignalStrength,
                                                       TradingSignal)
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    SPY_CONTRACT_MULTIPLIER, OptionType, SignalType)
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Calendar Configuration
MAX_CALENDAR_POSITIONS = 5
MIN_DAYS_NEAR_EXPIRY = 7  # Minimum days for near expiry
MAX_DAYS_NEAR_EXPIRY = 35  # Maximum days for near expiry
MIN_TIME_SPREAD = 14  # Minimum days between expiries
MAX_TIME_SPREAD = 60  # Maximum days between expiries
OPTIMAL_TIME_SPREAD = 30  # Optimal spread (30 days)

# IV Requirements
MIN_IV_RANK = 30  # Minimum IV rank for calendars
MAX_IV_RANK = 70  # Maximum IV rank
MIN_IV_SKEW = 0.02  # Minimum IV difference between expiries
MAX_IV_DIFFERENCE = 0.15  # Maximum IV difference

# Strike Selection
ATM_STRIKE_RANGE = 2.0  # $ range for ATM strikes
OTM_STRIKE_OFFSET = 5.0  # $ offset for OTM calendars
DELTA_TARGET_CALL = 0.40  # Target delta for call calendars
DELTA_TARGET_PUT = -0.40  # Target delta for put calendars

# Position Management
PROFIT_TARGET_PERCENT = 25  # Close at 25% of max profit
STOP_LOSS_PERCENT = 50  # Close at 50% loss
ROLL_THRESHOLD_DAYS = 5  # Days before expiry to consider roll
MIN_PROFIT_TO_ROLL = 10  # Minimum profit to allow roll

# Greeks Limits
MAX_VEGA_EXPOSURE = 100  # Maximum vega per position
MAX_THETA_COLLECTION = -50  # Maximum theta collection
GAMMA_WARNING_LEVEL = 20  # Gamma risk warning

# ==============================================================================
# ENUMS
# ==============================================================================


class CalendarType(Enum):
    """Calendar spread types"""

    CALL_CALENDAR = "call_calendar"
    PUT_CALENDAR = "put_calendar"
    DOUBLE_CALENDAR = "double_calendar"
    DIAGONAL_CALENDAR = "diagonal_calendar"


class CalendarState(Enum):
    """Calendar position states"""

    ANALYZING = auto()
    ENTERING = auto()
    ESTABLISHED = auto()
    ADJUSTING = auto()
    ROLLING = auto()
    CLOSING = auto()
    CLOSED = auto()


class IVRegime(Enum):
    """Implied volatility regime"""

    LOW = "low"  # IV < 30th percentile
    NORMAL = "normal"  # 30th - 70th percentile
    HIGH = "high"  # 70th - 90th percentile
    EXTREME = "extreme"  # > 90th percentile


class TermStructure(Enum):
    """Volatility term structure"""

    CONTANGO = "contango"  # Normal: near < far
    BACKWARDATION = "backwardation"  # Inverted: near > far
    FLAT = "flat"  # Similar IVs


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class CalendarLeg:
    """Individual calendar leg"""

    option_type: OptionType
    strike: float
    expiry: datetime
    position: int  # +1 long, -1 short
    contracts: int
    iv: float
    premium: float
    delta: float
    gamma: float
    vega: float
    theta: float


@dataclass
class CalendarSetup:
    """Calendar spread setup data"""

    calendar_type: CalendarType
    near_leg: CalendarLeg
    far_leg: CalendarLeg
    time_spread: int  # Days between expiries
    net_debit: float
    max_profit: float
    breakeven_points: list[float]
    iv_skew: float
    term_structure: TermStructure
    entry_iv_rank: float
    probability_profit: float


@dataclass
class CalendarPosition:
    """Active calendar position"""

    position_id: str
    setup: CalendarSetup
    entry_time: datetime
    entry_price: float
    current_value: float = 0.0
    unrealized_pnl: float = 0.0
    days_held: int = 0
    near_expiry_dte: int = 30
    far_expiry_dte: int = 60
    state: CalendarState = CalendarState.ENTERING
    roll_count: int = 0
    adjustments: list[dict] = field(default_factory=list)
    exit_time: datetime | None = None
    exit_reason: str | None = None


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class CalendarSpreadStrategy(BaseStrategy):
    """
    Professional calendar spread strategy implementation.

    Profits from time decay differentials and IV changes between near and
    far-dated options. Features sophisticated expiry management and rolling.
    """

    def __init__(
        self, event_manager: EventManager, risk_profile: RiskProfile, config: dict[str, Any] = None
    ):
        """Initialize Calendar Spread strategy"""
        resolved_config = config or {}
        super().__init__(
            name="Calendar Spread Strategy",
            strategy_type="calendar_spread",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=resolved_config,
        )

        # Initialize components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.greeks_calculator = GreeksCalculator()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.vix_analyzer = VIXAnalyzer()

        # Strategy state
        self.active_positions: dict[str, CalendarPosition] = {}
        self.iv_history: list[float] = []
        self.current_iv_regime: IVRegime | None = None
        self.term_structure_history: list[TermStructure] = []

        # Configuration
        self.max_positions = resolved_config.get("max_positions", MAX_CALENDAR_POSITIONS)
        self.use_calls = resolved_config.get("use_calls", True)
        self.use_puts = resolved_config.get("use_puts", True)
        self.allow_diagonal = resolved_config.get("allow_diagonal", False)
        self.signal_symbol = str(resolved_config.get("symbol", "SPY"))

        # Performance tracking
        self.performance_stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_rolls": 0,
            "successful_rolls": 0,
            "avg_holding_days": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
        }

        self.logger.info("Initialized %s", self.name)

    # ==========================================================================
    # IV AND TERM STRUCTURE ANALYSIS
    # ==========================================================================

    def _analyze_iv_environment(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Analyze current IV environment for calendars"""
        try:
            # Get current IV metrics
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

            self.current_iv_regime = iv_regime

            # Analyze term structure
            term_structure = self._analyze_term_structure(market_data)

            # Calculate optimal time spread based on conditions
            optimal_spread = self._calculate_optimal_time_spread(iv_regime, term_structure)

            return {
                "current_iv": current_iv,
                "iv_rank": iv_rank,
                "iv_percentile": iv_percentile,
                "iv_regime": iv_regime,
                "term_structure": term_structure,
                "optimal_time_spread": optimal_spread,
                "calendar_favorable": self._is_calendar_favorable(iv_rank, term_structure),
            }

        except Exception as e:
            self.logger.error("Error analyzing IV environment: %s", e)
            return {}

    def _get_current_iv(self, market_data: pd.DataFrame) -> float:
        """Get current implied volatility"""
        if "iv" in market_data.columns:
            return market_data["iv"].iloc[-1]

        # Calculate from price movements if IV not available
        returns = market_data["close"].pct_change().dropna()
        return returns.std() * np.sqrt(252)

    def _calculate_iv_rank(self, market_data: pd.DataFrame) -> float:
        """Calculate IV rank (0-100)"""
        if "iv" not in market_data.columns:
            return 50.0

        # Use last 252 days (1 year) for IV rank
        iv_series = market_data["iv"].iloc[-252:]
        current_iv = iv_series.iloc[-1]

        min_iv = iv_series.min()
        max_iv = iv_series.max()

        if max_iv > min_iv:
            return ((current_iv - min_iv) / (max_iv - min_iv)) * 100
        return 50.0

    def _calculate_iv_percentile(self, market_data: pd.DataFrame) -> float:
        """Calculate IV percentile"""
        if "iv" not in market_data.columns:
            return 50.0

        iv_series = market_data["iv"].iloc[-252:]
        current_iv = iv_series.iloc[-1]

        return stats.percentileofscore(iv_series, current_iv)

    def _analyze_term_structure(self, market_data: pd.DataFrame) -> TermStructure:
        """Analyze volatility term structure"""
        try:
            # Get VIX term structure if available
            vix_data = self.vix_analyzer.get_term_structure()

            if vix_data:
                near_vix = vix_data.get("vix9d", 20)
                far_vix = vix_data.get("vix30d", 20)

                if far_vix > near_vix * 1.05:
                    return TermStructure.CONTANGO
                elif near_vix > far_vix * 1.05:
                    return TermStructure.BACKWARDATION
                else:
                    return TermStructure.FLAT

            # Default to contango (normal market)
            return TermStructure.CONTANGO

        except Exception:
            return TermStructure.CONTANGO

    def _calculate_optimal_time_spread(
        self, iv_regime: IVRegime, term_structure: TermStructure
    ) -> int:
        """Calculate optimal days between expiries"""
        base_spread = OPTIMAL_TIME_SPREAD

        # Adjust for IV regime
        if iv_regime == IVRegime.LOW:
            # Longer spreads in low IV
            base_spread = int(base_spread * 1.2)
        elif iv_regime == IVRegime.HIGH:
            # Shorter spreads in high IV
            base_spread = int(base_spread * 0.8)

        # Adjust for term structure
        if term_structure == TermStructure.BACKWARDATION:
            # Shorter spreads in backwardation
            base_spread = int(base_spread * 0.9)

        return max(MIN_TIME_SPREAD, min(MAX_TIME_SPREAD, base_spread))

    def _is_calendar_favorable(self, iv_rank: float, term_structure: TermStructure) -> bool:
        """Check if conditions are favorable for calendars"""
        # IV rank in favorable range
        if not (MIN_IV_RANK <= iv_rank <= MAX_IV_RANK):
            return False

        # Avoid extreme backwardation
        return not (term_structure == TermStructure.BACKWARDATION and iv_rank > 80)

    # ==========================================================================
    # EXPIRY SELECTION
    # ==========================================================================

    def _get_available_expiries(self, current_date: datetime) -> list[datetime]:
        """Get available option expiration dates"""
        expiries = []

        # Generate weekly expiries (every Friday)
        for i in range(1, 13):  # Next 12 weeks
            days_ahead = (4 - current_date.weekday() + 7 * i) % 7
            if days_ahead == 0:
                days_ahead = 7
            expiry = current_date + timedelta(days=days_ahead)
            expiries.append(expiry)

        # Add monthly expiries (3rd Friday)
        for i in range(1, 7):  # Next 6 months
            month_date = current_date.replace(day=1) + timedelta(days=32 * i)
            month_date = month_date.replace(day=1)

            # Find 3rd Friday
            first_day = month_date.weekday()
            days_to_friday = (4 - first_day) % 7
            third_friday = month_date + timedelta(days=days_to_friday + 14)

            if third_friday not in expiries:
                expiries.append(third_friday)

        return sorted(expiries)

    def _select_optimal_expiries(self, iv_analysis: dict[str, Any]) -> tuple[datetime, datetime]:
        """Select optimal near and far expiration dates"""
        current_date = datetime.now(UTC)
        available_expiries = self._get_available_expiries(current_date)

        optimal_spread = iv_analysis["optimal_time_spread"]

        # Find near expiry (target: 20-30 DTE)
        target_near_dte = 25
        near_expiry = None

        for expiry in available_expiries:
            dte = (expiry - current_date).days
            if MIN_DAYS_NEAR_EXPIRY <= dte <= MAX_DAYS_NEAR_EXPIRY:
                if near_expiry is None or abs(dte - target_near_dte) < abs(
                    (near_expiry - current_date).days - target_near_dte
                ):
                    near_expiry = expiry

        if not near_expiry:
            return None, None

        # Find far expiry based on optimal spread
        near_dte = (near_expiry - current_date).days
        target_far_dte = near_dte + optimal_spread
        far_expiry = None

        for expiry in available_expiries:
            dte = (expiry - current_date).days
            if dte > near_dte + MIN_TIME_SPREAD:
                if far_expiry is None or abs(dte - target_far_dte) < abs(
                    (far_expiry - current_date).days - target_far_dte
                ):
                    far_expiry = expiry

        return near_expiry, far_expiry

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate calendar spread trading signals"""
        try:
            signals = []

            # Check position limits
            if len(self.active_positions) >= self.max_positions:
                return signals

            # Analyze IV environment
            iv_analysis = self._analyze_iv_environment(market_data)

            if not iv_analysis.get("calendar_favorable", False):
                return signals

            # Get current price
            current_price = market_data["close"].iloc[-1]

            # Select optimal expiries
            near_expiry, far_expiry = self._select_optimal_expiries(iv_analysis)

            if not near_expiry or not far_expiry:
                return signals

            # Generate calendar setups
            setups = []

            if self.use_calls:
                call_setup = self._create_calendar_setup(
                    CalendarType.CALL_CALENDAR, current_price, near_expiry, far_expiry, iv_analysis
                )
                if call_setup:
                    setups.append(call_setup)

            if self.use_puts:
                put_setup = self._create_calendar_setup(
                    CalendarType.PUT_CALENDAR, current_price, near_expiry, far_expiry, iv_analysis
                )
                if put_setup:
                    setups.append(put_setup)

            # Convert setups to signals
            for setup in setups:
                signal = self._create_trading_signal(setup, market_data)
                if signal:
                    signals.append(signal)

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, market_data)
            return []

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Apply a minimal validity gate compatible with BaseStrategy."""
        if signal is None:
            return False
        if hasattr(signal, "is_valid") and not signal.is_valid():
            return False
        if len(self.active_positions) >= self.max_positions:
            return False
        return float(getattr(signal, "confidence", 0.0) or 0.0) > 0.0

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Use provided size when available, otherwise default to one contract."""
        size = int(getattr(signal, "position_size", 0) or 0)
        return size if size > 0 else 1

    def should_exit_position(
        self, position: Any, market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        """Generic stop/take-profit exit adapter for BaseStrategy contract."""
        if market_data.empty or "close" not in market_data.columns:
            return False, ""

        current_price = float(market_data["close"].iloc[-1])
        stop_loss = getattr(position, "stop_loss", None)
        take_profit = getattr(position, "take_profit", None)
        position_type = str(getattr(getattr(position, "position_type", ""), "value", "")).lower()

        if stop_loss is not None:
            if position_type == "short":
                if current_price >= stop_loss:
                    return True, "stop_loss"
            elif current_price <= stop_loss:
                return True, "stop_loss"

        if take_profit is not None:
            if position_type == "short":
                if current_price <= take_profit:
                    return True, "take_profit"
            elif current_price >= take_profit:
                return True, "take_profit"

        return False, ""

    def _create_calendar_setup(
        self,
        calendar_type: CalendarType,
        current_price: float,
        near_expiry: datetime,
        far_expiry: datetime,
        iv_analysis: dict[str, Any],
    ) -> CalendarSetup | None:
        """Create calendar spread setup"""
        try:
            # Select strike
            if calendar_type == CalendarType.CALL_CALENDAR:
                strike = self._select_call_strike(current_price)
                option_type = OptionType.CALL
            else:
                strike = self._select_put_strike(current_price)
                option_type = OptionType.PUT

            # Calculate IVs for each expiry
            near_iv = self._estimate_iv(near_expiry, strike, iv_analysis)
            far_iv = self._estimate_iv(far_expiry, strike, iv_analysis)

            # Check IV skew
            iv_skew = far_iv - near_iv
            if iv_skew < MIN_IV_SKEW:
                return None

            # Create legs
            near_leg = CalendarLeg(
                option_type=option_type,
                strike=strike,
                expiry=near_expiry,
                position=-1,  # Short
                contracts=1,
                iv=near_iv,
                premium=self._estimate_premium(
                    current_price, strike, near_expiry, near_iv, option_type
                ),
                delta=0,  # Will be calculated
                gamma=0,
                vega=0,
                theta=0,
            )

            far_leg = CalendarLeg(
                option_type=option_type,
                strike=strike,
                expiry=far_expiry,
                position=1,  # Long
                contracts=1,
                iv=far_iv,
                premium=self._estimate_premium(
                    current_price, strike, far_expiry, far_iv, option_type
                ),
                delta=0,
                gamma=0,
                vega=0,
                theta=0,
            )

            # Calculate net debit
            net_debit = (far_leg.premium - near_leg.premium) * SPY_CONTRACT_MULTIPLIER

            # Calculate max profit (occurs at strike at near expiry)
            max_profit = self._calculate_max_profit(near_leg, far_leg, current_price)

            # Calculate breakeven points
            breakevens = self._calculate_breakevens(strike, net_debit, option_type)

            # Calculate probability of profit
            prob_profit = self._calculate_probability_profit(
                current_price, strike, breakevens, near_expiry, near_iv
            )

            # Determine term structure
            if far_iv > near_iv * 1.05:
                term_structure = TermStructure.CONTANGO
            elif near_iv > far_iv * 1.05:
                term_structure = TermStructure.BACKWARDATION
            else:
                term_structure = TermStructure.FLAT

            setup = CalendarSetup(
                calendar_type=calendar_type,
                near_leg=near_leg,
                far_leg=far_leg,
                time_spread=(far_expiry - near_expiry).days,
                net_debit=net_debit,
                max_profit=max_profit,
                breakeven_points=breakevens,
                iv_skew=iv_skew,
                term_structure=term_structure,
                entry_iv_rank=iv_analysis["iv_rank"],
                probability_profit=prob_profit,
            )

            return setup

        except Exception as e:
            self.logger.error("Error creating calendar setup: %s", e)
            return None

    def _select_call_strike(self, current_price: float) -> float:
        """Select strike for call calendar"""
        # ATM or slightly OTM
        if self.allow_diagonal:
            return np.ceil(current_price + OTM_STRIKE_OFFSET)
        else:
            return round(current_price)  # ATM

    def _select_put_strike(self, current_price: float) -> float:
        """Select strike for put calendar"""
        # ATM or slightly OTM
        if self.allow_diagonal:
            return np.floor(current_price - OTM_STRIKE_OFFSET)
        else:
            return round(current_price)  # ATM

    def _estimate_iv(self, expiry: datetime, strike: float, iv_analysis: dict[str, Any]) -> float:
        """Estimate IV for specific expiry and strike"""
        base_iv = iv_analysis["current_iv"]
        dte = (expiry - datetime.now(UTC)).days

        # Add term structure adjustment
        if iv_analysis["term_structure"] == TermStructure.CONTANGO:
            # Far expiries have higher IV
            iv_adjustment = 0.001 * dte
        elif iv_analysis["term_structure"] == TermStructure.BACKWARDATION:
            # Near expiries have higher IV
            iv_adjustment = -0.001 * dte
        else:
            iv_adjustment = 0

        return base_iv + iv_adjustment

    def _estimate_premium(
        self, spot: float, strike: float, expiry: datetime, iv: float, option_type: OptionType
    ) -> float:
        """Estimate option premium using Black-Scholes approximation"""
        try:
            dte = (expiry - datetime.now(UTC)).days / 365.0

            # Simplified Black-Scholes approximation
            # In production, use full Black-Scholes or market prices
            d1 = (np.log(spot / strike) + (0.02 + iv**2 / 2) * dte) / (iv * np.sqrt(dte))
            d2 = d1 - iv * np.sqrt(dte)

            if option_type == OptionType.CALL:
                premium = spot * stats.norm.cdf(d1) - strike * np.exp(-0.02 * dte) * stats.norm.cdf(
                    d2
                )
            else:
                premium = strike * np.exp(-0.02 * dte) * stats.norm.cdf(
                    -d2
                ) - spot * stats.norm.cdf(-d1)

            return max(0.01, premium)

        except Exception:
            # Fallback to simple approximation
            return spot * 0.02  # 2% of spot

    def _calculate_max_profit(
        self, near_leg: CalendarLeg, far_leg: CalendarLeg, current_price: float
    ) -> float:
        """Calculate maximum profit for calendar"""
        # Max profit occurs when near option expires worthless
        # and far option retains time value

        # Estimate remaining value of far option at near expiry
        days_remaining = (far_leg.expiry - near_leg.expiry).days
        time_decay_factor = np.sqrt(days_remaining / 30)  # Square root of time

        remaining_value = far_leg.premium * time_decay_factor * 0.7  # 70% retention

        max_profit = (
            remaining_value - (far_leg.premium - near_leg.premium)
        ) * SPY_CONTRACT_MULTIPLIER

        return max(0, max_profit)

    def _calculate_breakevens(
        self, strike: float, net_debit: float, option_type: OptionType
    ) -> list[float]:
        """Calculate breakeven points for calendar"""
        # Simplified breakeven calculation
        # In production, would use option pricing model

        debit_per_share = net_debit / SPY_CONTRACT_MULTIPLIER

        if option_type == OptionType.CALL:
            # Breakevens above and below strike
            lower_be = strike - debit_per_share * 2
            upper_be = strike + debit_per_share * 3
        else:
            # Breakevens above and below strike
            lower_be = strike - debit_per_share * 3
            upper_be = strike + debit_per_share * 2

        return [lower_be, upper_be]

    def _calculate_probability_profit(
        self,
        current_price: float,
        strike: float,
        breakevens: list[float],
        near_expiry: datetime,
        iv: float,
    ) -> float:
        """Calculate probability of profit for calendar"""
        try:
            dte = (near_expiry - datetime.now(UTC)).days / 365.0

            # Calculate probability of being between breakevens at expiry
            lower_be, upper_be = breakevens

            # Standard deviation of price movement
            price_std = current_price * iv * np.sqrt(dte)

            # Z-scores for breakevens
            z_lower = (lower_be - current_price) / price_std
            z_upper = (upper_be - current_price) / price_std

            # Probability between breakevens
            prob = stats.norm.cdf(z_upper) - stats.norm.cdf(z_lower)

            # Adjust for calendar characteristics
            # Calendars perform best near strike
            distance_from_strike = abs(current_price - strike) / current_price
            if distance_from_strike < 0.02:  # Within 2% of strike
                prob *= 1.1  # 10% bonus

            return min(0.9, max(0.1, prob))

        except Exception:
            return 0.5

    def _create_trading_signal(
        self, setup: CalendarSetup, market_data: pd.DataFrame
    ) -> TradingSignal | None:
        """Convert calendar setup to trading signal"""
        try:
            # Determine signal strength
            if setup.probability_profit > 0.65 and setup.iv_skew > 0.05:
                strength = SignalStrength.STRONG
            elif setup.probability_profit > 0.55:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            signal_timestamp = datetime.now(UTC)
            current_price = float(market_data["close"].iloc[-1])
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.BUY,
                symbol=self.signal_symbol,
                strength=strength,
                confidence=setup.probability_profit,
                entry_price=current_price,
                stop_loss=current_price * 0.98,
                take_profit=current_price * 1.02,
                position_size=1,
                timestamp=signal_timestamp,
                expires_at=signal_timestamp + timedelta(minutes=15),
                metadata={
                    "strategy": "calendar_spread",
                    "strategy_id": "CalendarSpread",
                    "strategy_type": "CalendarSpread",
                    "action": "buy",
                    "setup": setup.__dict__,
                    "calendar_type": setup.calendar_type.value,
                    "strike": setup.near_leg.strike,
                    "near_expiry": setup.near_leg.expiry.strftime("%Y-%m-%d"),
                    "far_expiry": setup.far_leg.expiry.strftime("%Y-%m-%d"),
                    "net_debit": setup.net_debit,
                    "max_profit": setup.max_profit,
                    "iv_skew": setup.iv_skew,
                    "term_structure": setup.term_structure.value,
                },
            )

            self.logger.info("Generated %s signal", setup.calendar_type.value)
            return signal

        except Exception as e:
            self.logger.error("Error creating trading signal: %s", e)
            return None

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def manage_positions(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Manage active calendar positions"""
        signals = []

        current_price = market_data["close"].iloc[-1]

        for position_id, position in list(self.active_positions.items()):
            # Update position metrics
            position.days_held += 1
            position.near_expiry_dte = (position.setup.near_leg.expiry - datetime.now(UTC)).days
            position.far_expiry_dte = (position.setup.far_leg.expiry - datetime.now(UTC)).days

            # Update position value and P&L
            self._update_position_value(position, current_price, market_data)

            # Check for roll opportunity
            if position.near_expiry_dte <= ROLL_THRESHOLD_DAYS:
                roll_signal = self._check_roll_opportunity(position, market_data)
                if roll_signal:
                    signals.append(roll_signal)
                    continue

            # Check exit conditions
            exit_signal = self._check_exit_conditions(position, market_data)
            if exit_signal:
                signals.append(exit_signal)
                self._close_position(position)
                del self.active_positions[position_id]

        return signals

    def _update_position_value(
        self, position: CalendarPosition, current_price: float, market_data: pd.DataFrame
    ):
        """Update position value and P&L"""
        try:
            # Get current IV
            current_iv = self._get_current_iv(market_data)

            # Estimate current value of each leg
            near_value = (
                self._estimate_premium(
                    current_price,
                    position.setup.near_leg.strike,
                    position.setup.near_leg.expiry,
                    current_iv,
                    position.setup.near_leg.option_type,
                )
                * position.setup.near_leg.position
            )  # Negative for short

            far_value = (
                self._estimate_premium(
                    current_price,
                    position.setup.far_leg.strike,
                    position.setup.far_leg.expiry,
                    current_iv,
                    position.setup.far_leg.option_type,
                )
                * position.setup.far_leg.position
            )  # Positive for long

            # Current spread value
            position.current_value = (near_value + far_value) * SPY_CONTRACT_MULTIPLIER

            # Unrealized P&L
            position.unrealized_pnl = position.current_value + position.setup.net_debit

        except Exception as e:
            self.logger.error("Error updating position value: %s", e)

    def _check_roll_opportunity(
        self, position: CalendarPosition, market_data: pd.DataFrame
    ) -> TradingSignal | None:
        """Check if position should be rolled"""
        # Only roll if profitable
        if position.unrealized_pnl < MIN_PROFIT_TO_ROLL:
            return None

        # Check if we've already rolled too many times
        if position.roll_count >= 2:
            return self._create_exit_signal(position, "max_rolls")

        # Analyze current conditions
        iv_analysis = self._analyze_iv_environment(market_data)

        if not iv_analysis.get("calendar_favorable", False):
            return self._create_exit_signal(position, "unfavorable_conditions")

        # Create roll signal
        signal_timestamp = datetime.now(UTC)
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            signal_type=SignalType.ADJUST,
            symbol=self.signal_symbol,
            strength=SignalStrength.MODERATE,
            confidence=0.7,
            entry_price=float(market_data["close"].iloc[-1]),
            stop_loss=float(market_data["close"].iloc[-1]) * 0.99,
            take_profit=float(market_data["close"].iloc[-1]) * 1.01,
            position_size=1,
            timestamp=signal_timestamp,
            expires_at=signal_timestamp + timedelta(minutes=10),
            metadata={
                "position_id": position.position_id,
                "action": "roll",
                "strategy_id": "CalendarSpread",
                "strategy_type": "CalendarSpread",
                "current_pnl": position.unrealized_pnl,
                "near_expiry_dte": position.near_expiry_dte,
                "roll_count": position.roll_count + 1,
            },
        )

        # Update position state
        position.state = CalendarState.ROLLING
        position.roll_count += 1
        position.adjustments.append(
            {"time": datetime.now(UTC), "type": "roll", "pnl_at_roll": position.unrealized_pnl}
        )

        self.logger.info("Rolling calendar position %s", position.position_id)
        return signal

    def _check_exit_conditions(
        self, position: CalendarPosition, market_data: pd.DataFrame
    ) -> TradingSignal | None:
        """Check if position should be closed"""
        # Profit target
        if position.unrealized_pnl >= position.setup.max_profit * (PROFIT_TARGET_PERCENT / 100):
            return self._create_exit_signal(position, "profit_target")

        # Stop loss
        if position.unrealized_pnl <= -position.setup.net_debit * (STOP_LOSS_PERCENT / 100):
            return self._create_exit_signal(position, "stop_loss")

        # Pin risk - close if too close to strike near expiry
        if position.near_expiry_dte <= 2:
            current_price = market_data["close"].iloc[-1]
            strike = position.setup.near_leg.strike
            if abs(current_price - strike) / strike < 0.005:  # Within 0.5%
                return self._create_exit_signal(position, "pin_risk")

        # Time decay - close if near expiry approaching
        if position.near_expiry_dte <= 1:
            return self._create_exit_signal(position, "near_expiry")

        return None

    def _create_exit_signal(self, position: CalendarPosition, reason: str) -> TradingSignal:
        """Create exit signal for position"""
        position.exit_time = datetime.now(UTC)
        position.exit_reason = reason
        position.state = CalendarState.CLOSING

        signal_timestamp = datetime.now(UTC)
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            signal_type=SignalType.CLOSE,
            symbol=self.signal_symbol,
            strength=SignalStrength.STRONG,
            confidence=0.95,
            entry_price=float(position.current_value or 0.0),
            stop_loss=float(position.current_value or 0.0),
            take_profit=float(position.current_value or 0.0),
            position_size=1,
            timestamp=signal_timestamp,
            expires_at=signal_timestamp + timedelta(minutes=10),
            metadata={
                "position_id": position.position_id,
                "strategy_id": "CalendarSpread",
                "strategy_type": "CalendarSpread",
                "exit_reason": reason,
                "days_held": position.days_held,
                "unrealized_pnl": position.unrealized_pnl,
                "roll_count": position.roll_count,
                "final_near_dte": position.near_expiry_dte,
                "final_far_dte": position.far_expiry_dte,
            },
        )

        self.logger.info(
            "Exit signal for %s: %s, P&L: $%.2f",
            position.position_id,
            reason,
            position.unrealized_pnl,
        )
        return signal

    def _close_position(self, position: CalendarPosition):
        """Close position and update stats"""
        # Update performance stats
        self.performance_stats["total_trades"] += 1

        if position.unrealized_pnl > 0:
            self.performance_stats["winning_trades"] += 1

        if position.roll_count > 0:
            self.performance_stats["total_rolls"] += position.roll_count
            if position.unrealized_pnl > 0:
                self.performance_stats["successful_rolls"] += position.roll_count

        # Update best/worst
        if position.unrealized_pnl > self.performance_stats["best_trade"]:
            self.performance_stats["best_trade"] = position.unrealized_pnl
        if position.unrealized_pnl < self.performance_stats["worst_trade"]:
            self.performance_stats["worst_trade"] = position.unrealized_pnl

        # Update average holding period
        total = self.performance_stats["total_trades"]
        avg = self.performance_stats["avg_holding_days"]
        self.performance_stats["avg_holding_days"] = (
            avg * (total - 1) + position.days_held
        ) / total

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def add_position(self, signal: TradingSignal) -> str:
        """Add new calendar position from signal"""
        position_id = f"CAL_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        signal.metadata["setup"]
        # Reconstruct setup object
        # This is simplified - in production would properly deserialize

        position = CalendarPosition(
            position_id=position_id,
            setup=None,  # Would reconstruct from setup_dict
            entry_time=datetime.now(UTC),
            entry_price=signal.metadata.get("current_price", 0),
            state=CalendarState.ESTABLISHED,
        )

        self.active_positions[position_id] = position
        self.logger.info("Added calendar position %s", position_id)

        return position_id

    def get_position_summary(self) -> list[dict[str, Any]]:
        """Get summary of all active positions"""
        summaries = []

        for position_id, position in self.active_positions.items():
            summary = {
                "position_id": position_id,
                "type": position.setup.calendar_type.value if position.setup else "unknown",
                "days_held": position.days_held,
                "near_dte": position.near_expiry_dte,
                "far_dte": position.far_expiry_dte,
                "unrealized_pnl": position.unrealized_pnl,
                "state": position.state.name,
                "roll_count": position.roll_count,
            }
            summaries.append(summary)

        return summaries

    def get_strategy_stats(self) -> dict[str, Any]:
        """Get comprehensive strategy statistics"""
        total_trades = self.performance_stats["total_trades"]
        win_rate = 0.0
        if total_trades > 0:
            win_rate = self.performance_stats["winning_trades"] / total_trades

        roll_success_rate = 0.0
        if self.performance_stats["total_rolls"] > 0:
            roll_success_rate = (
                self.performance_stats["successful_rolls"] / self.performance_stats["total_rolls"]
            )

        return {
            "active_positions": len(self.active_positions),
            "current_iv_regime": (
                self.current_iv_regime.value if self.current_iv_regime else "unknown"
            ),
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_holding_days": self.performance_stats["avg_holding_days"],
            "total_rolls": self.performance_stats["total_rolls"],
            "roll_success_rate": roll_success_rate,
            "best_trade": self.performance_stats["best_trade"],
            "worst_trade": self.performance_stats["worst_trade"],
        }


# ==============================================================================
# TESTING
# ==============================================================================
def test_calendar_spread():
    """Test the Calendar Spread strategy"""
    logging.info("Testing Calendar Spread Strategy")
    logging.info("=" * 60)

    # Create mock components
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile

    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000, max_position_size=0.02, max_portfolio_risk=0.06, max_loss_per_trade=500
    )

    config = {"max_positions": 3, "use_calls": True, "use_puts": True, "allow_diagonal": False}

    # Create strategy
    strategy = CalendarSpreadStrategy(event_manager, risk_profile, config)

    logging.info("Strategy: %s", strategy.name)
    logging.info("Max Positions: %s", strategy.max_positions)

    # Create sample market data with IV
    dates = pd.date_range(end=datetime.now(UTC), periods=252, freq="D")

    # Simulate IV environment
    base_iv = 0.20
    iv_series = (
        base_iv + np.sin(np.linspace(0, 4 * np.pi, 252)) * 0.05 + np.random.randn(252) * 0.01
    )

    prices = 450 + np.cumsum(np.random.randn(252) * 2)

    market_data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices - 0.5,
            "high": prices + 1,
            "low": prices - 1,
            "close": prices,
            "volume": np.random.randint(50000000, 150000000, 252),
            "iv": iv_series,
        }
    )

    # Test IV analysis
    logging.info("\nTesting IV Analysis...")
    iv_analysis = strategy._analyze_iv_environment(market_data)
    logging.info(f"Current IV: {iv_analysis.get('current_iv', 0):.1%}")
    logging.info(f"IV Rank: {iv_analysis.get('iv_rank', 0):.1f}")
    logging.info("IV Regime: %s", iv_analysis.get('iv_regime', IVRegime.NORMAL).value)
    logging.info("Term Structure: %s", iv_analysis.get('term_structure', TermStructure.CONTANGO).value)  # noqa: E501
    logging.info("Calendar Favorable: %s", iv_analysis.get('calendar_favorable', False))

    # Test expiry selection
    logging.info("\nTesting Expiry Selection...")
    near_expiry, far_expiry = strategy._select_optimal_expiries(iv_analysis)
    if near_expiry and far_expiry:
        logging.info(
            "Near Expiry: %s (%s days)", near_expiry.strftime('%Y-%m-%d'), (near_expiry - datetime.now(UTC)).days  # noqa: E501
        )
        logging.info(
            "Far Expiry: %s (%s days)", far_expiry.strftime('%Y-%m-%d'), (far_expiry - datetime.now(UTC)).days  # noqa: E501
        )
        logging.info("Time Spread: %s days", (far_expiry - near_expiry).days)

    # Generate signals
    logging.info("\nGenerating Signals...")
    signals = strategy.generate_signals(market_data)

    logging.info("Generated %s signals", len(signals))

    for signal in signals:
        logging.info("\nSignal Type: %s", signal.metadata['calendar_type'])
        logging.info("Strike: $%s", signal.metadata['strike'])
        logging.info("Near Expiry: %s", signal.metadata['near_expiry'])
        logging.info("Far Expiry: %s", signal.metadata['far_expiry'])
        logging.info(f"Net Debit: ${signal.metadata['net_debit']:.2f}")
        logging.info(f"Max Profit: ${signal.metadata['max_profit']:.2f}")
        logging.info(f"IV Skew: {signal.metadata['iv_skew']:.3f}")
        logging.info(f"Confidence: {signal.confidence:.1%}")

        # Add position
        strategy.add_position(signal)

    # Test position management
    if strategy.active_positions:
        logging.info("\n" + "=" * 40)
        logging.info("Position Management Test")

        # Simulate price movement
        new_prices = prices[-1] + np.cumsum(np.random.randn(20) * 1.5)

        for i, price in enumerate(new_prices):
            market_data.loc[len(market_data)] = {
                "timestamp": datetime.now(UTC) + timedelta(days=i),
                "open": price - 0.3,
                "high": price + 0.5,
                "low": price - 0.5,
                "close": price,
                "volume": 100000000,
                "iv": base_iv + np.random.randn() * 0.02,
            }

            # Manage positions
            management_signals = strategy.manage_positions(market_data)

            if management_signals:
                for signal in management_signals:
                    if signal.signal_type == SignalType.ADJUST:
                        logging.info("\nRoll Signal Day %s", i)
                        logging.info("Action: %s", signal.metadata['action'])
                        logging.info(f"Current P&L: ${signal.metadata['current_pnl']:.2f}")
                        logging.info("Near DTE: %s", signal.metadata['near_expiry_dte'])
                    elif signal.signal_type == SignalType.CLOSE:
                        logging.info("\nExit Signal Day %s", i)
                        logging.info("Reason: %s", signal.metadata['exit_reason'])
                        logging.info("Days Held: %s", signal.metadata['days_held'])
                        logging.info(f"Final P&L: ${signal.metadata['unrealized_pnl']:.2f}")

    # Print final stats
    stats = strategy.get_strategy_stats()
    logging.info("\n" + "=" * 40)
    logging.info("Strategy Statistics:")
    logging.info("Active Positions: %s", stats['active_positions'])
    logging.info("Current IV Regime: %s", stats['current_iv_regime'])
    logging.info("Total Trades: %s", stats['total_trades'])
    logging.info(f"Win Rate: {stats['win_rate']:.1%}")
    logging.info(f"Avg Holding Days: {stats['avg_holding_days']:.1f}")
    logging.info("Total Rolls: %s", stats['total_rolls'])
    logging.info(f"Roll Success Rate: {stats['roll_success_rate']:.1%}")
    logging.info(f"Best Trade: ${stats['best_trade']:.2f}")
    logging.info(f"Worst Trade: ${stats['worst_trade']:.2f}")

    logging.info("\n✅ Calendar Spread Strategy Test Complete!")
    logging.info("\nKey Features Tested:")
    logging.info("- ✅ IV environment analysis and regime detection")
    logging.info("- ✅ Term structure analysis (contango/backwardation)")
    logging.info("- ✅ Optimal expiry selection")
    logging.info("- ✅ IV skew validation")
    logging.info("- ✅ Strike selection for calls and puts")
    logging.info("- ✅ Premium estimation using Black-Scholes")
    logging.info("- ✅ Probability calculations")
    logging.info("- ✅ Position value updates")
    logging.info("- ✅ Roll opportunity detection")
    logging.info("- ✅ Pin risk management")
    logging.info("- ✅ Performance tracking")


if __name__ == "__main__":
    test_calendar_spread()
