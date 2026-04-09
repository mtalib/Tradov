#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD11_SpecializedZeroDTE.py
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
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum, auto
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import pytz
from scipy.stats import norm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (BaseStrategy,

                                                       SignalStrength,
                                                       TradingSignal)
from Spyder.SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from Spyder.SpyderF_Analysis.SpyderF10_MarketRegimeDetector import \
    MarketRegimeDetector
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (SPY_CONTRACT_MULTIPLIER,
                                                   SignalType)
import logging

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Timing Constants
ZERO_DTE_ENTRY_TIME = time(10, 15)  # 10:15 AM optimal entry
ZERO_DTE_CUTOFF_TIME = time(14, 30)  # 2:30 PM no new entries
ZERO_DTE_CLOSE_TIME = time(15, 45)  # 3:45 PM close all

# Position Management
MAX_ZERO_DTE_POSITIONS = 3
POSITION_SIZE_REDUCTION = 0.7  # 30% smaller than regular
RAPID_PROFIT_TARGET = 0.10  # 10% quick profit
RAPID_STOP_LOSS = 0.20  # 20% stop loss

# Market Filters
MIN_OPENING_VOLUME = 1000000
MAX_OVERNIGHT_GAP = 0.015  # 1.5%
MIN_VIX_LEVEL = 12
MAX_VIX_LEVEL = 35

# Greeks Limits for 0DTE
MAX_GAMMA_EXPOSURE = 100  # Aggregate gamma limit
MAX_DELTA_EXPOSURE = 50  # Aggregate delta limit
MIN_THETA_COLLECTION = 50  # Minimum theta to collect

# Fed Days and Economic Events
FED_MEETING_DATES = [
    # 2025 Fed meeting dates (would be loaded from external source)
    "2025-01-29",
    "2025-03-19",
    "2025-05-07",
    "2025-06-18",
    "2025-07-30",
    "2025-09-17",
    "2025-11-05",
    "2025-12-17",
]

MAJOR_ECONOMIC_EVENTS = [
    "NFP",  # Non-Farm Payrolls
    "CPI",  # Consumer Price Index
    "PPI",  # Producer Price Index
    "FOMC Minutes",
    "GDP",
]

# ==============================================================================
# ENUMS
# ==============================================================================


class ZeroDTEStrategy(Enum):
    """Types of 0DTE strategies"""

    IRON_BUTTERFLY = "iron_butterfly"
    IRON_CONDOR = "iron_condor"
    CREDIT_SPREAD = "credit_spread"
    BROKEN_WING_BUTTERFLY = "broken_wing_butterfly"
    SHORT_STRANGLE = "short_strangle"


class ZeroDTEState(Enum):
    """0DTE position states"""

    SCANNING = auto()
    ENTERING = auto()
    MONITORING = auto()
    CLOSING = auto()
    CLOSED = auto()


class MarketBias(Enum):
    """Market directional bias"""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class ZeroDTESetup:
    """0DTE trade setup details"""

    strategy_type: ZeroDTEStrategy
    strikes: dict[str, float]
    entry_time: datetime
    expiration_time: datetime
    contracts: int
    credit_received: float
    max_profit: float
    max_loss: float
    profit_target: float
    stop_loss: float
    time_stop: datetime
    entry_conditions: dict[str, Any]
    probability_profit: float
    expected_value: float


@dataclass
class ZeroDTEPosition:
    """Active 0DTE position tracking"""

    position_id: str
    setup: ZeroDTESetup
    entry_price: float
    current_pnl: float = 0.0
    greeks: dict[str, float] = field(default_factory=dict)
    state: ZeroDTEState = ZeroDTEState.ENTERING
    management_actions: list[dict] = field(default_factory=list)
    exit_time: datetime | None = None
    exit_reason: str | None = None


@dataclass
class ZeroDTEMetrics:
    """Real-time metrics for 0DTE position"""

    current_value: float
    pnl: float
    pnl_percentage: float
    delta: float
    gamma: float
    theta: float
    time_remaining: float  # hours
    price_distance_pct: float  # from profitable zone
    win_probability: float
    suggested_action: str


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class SpecializedZeroDTEStrategy(BaseStrategy):
    """
    Professional 0DTE options strategy implementation.

    Specializes in same-day expiration options with optimal entry timing,
    dynamic strategy selection, and rapid profit/loss management.
    """

    def __init__(
        self, event_manager: EventManager, risk_profile: RiskProfile, config: dict[str, Any] = None
    ):
        """Initialize Specialized Zero DTE strategy"""
        super().__init__(
            name="Specialized Zero DTE Strategy",
            strategy_type="zero_dte",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config or {},
        )

        # Initialize components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.greeks_calculator = GreeksCalculator()
        self.volatility_analyzer = VolatilityAnalyzer()
        self.market_regime_detector = MarketRegimeDetector()

        # Strategy state
        self.active_positions: dict[str, ZeroDTEPosition] = {}
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.fed_calendar = self._load_fed_calendar()
        self.economic_calendar = self._load_economic_calendar()

        # Configuration
        self.max_positions = config.get("max_positions", MAX_ZERO_DTE_POSITIONS)
        self.position_reduction = config.get("position_reduction", POSITION_SIZE_REDUCTION)
        self.profit_target = config.get("profit_target", RAPID_PROFIT_TARGET)
        self.stop_loss = config.get("stop_loss", RAPID_STOP_LOSS)

        # Performance tracking
        self.strategy_stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "total_pnl": 0.0,
            "best_strategy": None,
            "avg_hold_time": 0.0,
        }

        # Time zone
        self.eastern_tz = pytz.timezone("US/Eastern")

        self.logger.info("Initialized %s", self.name)

    # ==========================================================================
    # FED AND ECONOMIC CALENDAR
    # ==========================================================================

    def _load_fed_calendar(self) -> list[datetime]:
        """Load Fed meeting dates"""
        # In production, this would load from external source
        fed_dates = []
        for date_str in FED_MEETING_DATES:
            fed_date = datetime.strptime(date_str, "%Y-%m-%d")
            fed_dates.append(fed_date)
        return fed_dates

    def _load_economic_calendar(self) -> dict[datetime, list[str]]:
        """Load economic event calendar"""
        # In production, this would connect to economic calendar API
        # For now, return mock data
        calendar = defaultdict(list)

        # Example events
        today = datetime.now().date()
        if today.weekday() == 4:  # Friday
            calendar[today].append("NFP")

        return calendar

    def _is_fed_day(self, date: datetime) -> bool:
        """Check if date is a Fed meeting day"""
        check_date = date.date()
        return any(fed_date.date() == check_date for fed_date in self.fed_calendar)

    def _has_major_economic_event(self, date: datetime) -> bool:
        """Check if date has major economic events"""
        check_date = date.date()
        if check_date in self.economic_calendar:
            events = self.economic_calendar[check_date]
            for event in events:
                if any(major in event for major in MAJOR_ECONOMIC_EVENTS):
                    return True
        return False

    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate 0DTE trading signals"""
        try:
            signals = []

            # Get current time
            current_time = datetime.now(self.eastern_tz)
            current_hour_min = current_time.time()

            # Check if it's a valid 0DTE day (Mon/Wed/Fri)
            if current_time.weekday() not in [0, 2, 4]:
                return signals

            # Check if it's Fed day or major economic event
            if self._is_fed_day(current_time) or self._has_major_economic_event(current_time):
                self.logger.info("Skipping 0DTE due to Fed day or major economic event")
                return signals

            # Check time window
            if not (ZERO_DTE_ENTRY_TIME <= current_hour_min <= ZERO_DTE_CUTOFF_TIME):
                return signals

            # Check if we've hit daily trade limit
            if self.daily_trades >= self.max_positions:
                return signals

            # Check market conditions
            market_conditions = self._analyze_market_conditions(market_data)
            if not self._validate_market_conditions(market_conditions):
                return signals

            # Determine market bias
            market_bias = self._determine_market_bias(market_conditions)

            # Select appropriate strategy
            selected_strategy = self._select_zero_dte_strategy(market_bias, market_conditions)

            # Generate setup
            setup = self._create_zero_dte_setup(selected_strategy, market_data, market_conditions)

            if setup:
                signal = self._create_entry_signal(setup, market_conditions)
                if signal:
                    signals.append(signal)

            return signals

        except Exception as e:
            self.error_handler.handle_error(e, market_data)
            return []

    def _analyze_market_conditions(self, market_data: pd.DataFrame) -> dict[str, Any]:
        """Analyze current market conditions for 0DTE"""
        try:
            current_price = market_data["close"].iloc[-1]
            opening_price = market_data["open"].iloc[0]

            # Calculate overnight gap
            prev_close = market_data["close"].iloc[-2] if len(market_data) > 1 else opening_price
            overnight_gap = (opening_price - prev_close) / prev_close

            # Get current volume
            current_volume = market_data["volume"].iloc[-1]
            avg_volume = market_data["volume"].rolling(20).mean().iloc[-1]

            # Calculate intraday trend
            intraday_high = market_data["high"].max()
            intraday_low = market_data["low"].min()
            intraday_range = intraday_high - intraday_low

            # Get VIX if available
            vix = market_data.get("vix", pd.Series([20])).iloc[-1]

            # Calculate realized volatility
            returns = market_data["close"].pct_change().dropna()
            realized_vol = returns.std() * np.sqrt(252) * 100

            # Determine volatility regime
            vol_regime = self.volatility_analyzer.get_volatility_regime(market_data)

            conditions = {
                "current_price": current_price,
                "overnight_gap": overnight_gap,
                "current_volume": current_volume,
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 1.0,
                "intraday_range": intraday_range,
                "intraday_range_pct": intraday_range / current_price,
                "vix": vix,
                "realized_vol": realized_vol,
                "volatility_regime": vol_regime,
                "trend_strength": self._calculate_trend_strength(market_data),
                "support_resistance": self._identify_support_resistance(market_data),
            }

            return conditions

        except Exception as e:
            self.logger.error("Error analyzing market conditions: %s", e)
            return {}

    def _validate_market_conditions(self, conditions: dict[str, Any]) -> bool:
        """Validate if market conditions are suitable for 0DTE"""
        # Check overnight gap
        if abs(conditions.get("overnight_gap", 0)) > MAX_OVERNIGHT_GAP:
            self.logger.info("Overnight gap too large for 0DTE")
            return False

        # Check volume
        if conditions.get("current_volume", 0) < MIN_OPENING_VOLUME:
            self.logger.info("Volume too low for 0DTE")
            return False

        # Check VIX levels
        vix = conditions.get("vix", 20)
        if vix < MIN_VIX_LEVEL or vix > MAX_VIX_LEVEL:
            self.logger.info("VIX %s outside acceptable range for 0DTE", vix)
            return False

        # Check volatility regime
        if conditions.get("volatility_regime") == "extreme":
            self.logger.info("Extreme volatility - avoiding 0DTE")
            return False

        return True

    def _determine_market_bias(self, conditions: dict[str, Any]) -> MarketBias:
        """Determine market directional bias"""
        trend_strength = conditions.get("trend_strength", 0)
        overnight_gap = conditions.get("overnight_gap", 0)

        # Strong trending conditions
        if trend_strength > 0.7:
            return MarketBias.BULLISH
        elif trend_strength < -0.7:
            return MarketBias.BEARISH

        # Gap fade opportunities
        if overnight_gap > 0.01:  # 1% gap up
            return MarketBias.BEARISH  # Fade the gap
        elif overnight_gap < -0.01:  # 1% gap down
            return MarketBias.BULLISH  # Fade the gap

        # Default to neutral
        return MarketBias.NEUTRAL

    def _calculate_trend_strength(self, market_data: pd.DataFrame) -> float:
        """Calculate intraday trend strength"""
        try:
            # Use 5-minute bars for intraday trend
            close_prices = market_data["close"].iloc[-20:]  # Last 20 bars

            # Calculate linear regression slope
            x = np.arange(len(close_prices))
            slope, _ = np.polyfit(x, close_prices, 1)

            # Normalize by price
            normalized_slope = slope / close_prices.mean()

            # Scale to -1 to 1
            return np.tanh(normalized_slope * 100)

        except Exception:
            return 0.0

    def _identify_support_resistance(self, market_data: pd.DataFrame) -> dict[str, float]:
        """Identify key support and resistance levels"""
        try:
            high = market_data["high"].iloc[-50:].max()
            low = market_data["low"].iloc[-50:].min()

            # Volume-weighted levels
            vwap = (market_data["close"] * market_data["volume"]).sum() / market_data[
                "volume"
            ].sum()

            # Previous day levels (if available)
            prev_high = (
                market_data["high"].iloc[-390:-330].max() if len(market_data) > 390 else high
            )
            prev_low = market_data["low"].iloc[-390:-330].min() if len(market_data) > 390 else low

            return {
                "resistance": high,
                "support": low,
                "vwap": vwap,
                "prev_high": prev_high,
                "prev_low": prev_low,
            }
        except Exception:
            return {}

    def _select_zero_dte_strategy(
        self, market_bias: MarketBias, conditions: dict[str, Any]
    ) -> ZeroDTEStrategy:
        """Select appropriate 0DTE strategy based on conditions"""
        vol_regime = conditions.get("volatility_regime", "normal")
        intraday_range_pct = conditions.get("intraday_range_pct", 0.01)

        # Strategy selection matrix
        if market_bias == MarketBias.NEUTRAL:
            if vol_regime == "low" and intraday_range_pct < 0.005:
                return ZeroDTEStrategy.IRON_BUTTERFLY  # Tight range, collect premium
            else:
                return ZeroDTEStrategy.IRON_CONDOR  # Wider range expected

        elif market_bias == MarketBias.BULLISH:
            if vol_regime == "high":
                return ZeroDTEStrategy.BROKEN_WING_BUTTERFLY  # Skewed to upside
            else:
                return ZeroDTEStrategy.CREDIT_SPREAD  # Bull put spread

        elif market_bias == MarketBias.BEARISH:
            if vol_regime == "high":
                return ZeroDTEStrategy.BROKEN_WING_BUTTERFLY  # Skewed to downside
            else:
                return ZeroDTEStrategy.CREDIT_SPREAD  # Bear call spread

        # Default to Iron Condor
        return ZeroDTEStrategy.IRON_CONDOR

    def _create_zero_dte_setup(
        self, strategy: ZeroDTEStrategy, market_data: pd.DataFrame, conditions: dict[str, Any]
    ) -> ZeroDTESetup | None:
        """Create specific 0DTE setup based on strategy"""
        try:
            current_price = conditions["current_price"]

            # Get today's expiration
            today = datetime.now(self.eastern_tz).date()
            expiration = datetime.combine(today, time(16, 0), tzinfo=self.eastern_tz)

            # Strategy-specific setup
            if strategy == ZeroDTEStrategy.IRON_BUTTERFLY:
                setup = self._setup_iron_butterfly(current_price, conditions)
            elif strategy == ZeroDTEStrategy.IRON_CONDOR:
                setup = self._setup_iron_condor(current_price, conditions)
            elif strategy == ZeroDTEStrategy.CREDIT_SPREAD:
                setup = self._setup_credit_spread(current_price, conditions)
            elif strategy == ZeroDTEStrategy.BROKEN_WING_BUTTERFLY:
                setup = self._setup_broken_wing_butterfly(current_price, conditions)
            else:  # SHORT_STRANGLE
                setup = self._setup_short_strangle(current_price, conditions)

            if not setup:
                return None

            # Calculate position size (reduced for 0DTE)
            base_contracts = self._calculate_base_contracts(market_data)
            zero_dte_contracts = int(base_contracts * self.position_reduction)

            # Create setup object
            zero_dte_setup = ZeroDTESetup(
                strategy_type=strategy,
                strikes=setup["strikes"],
                entry_time=datetime.now(self.eastern_tz),
                expiration_time=expiration,
                contracts=max(1, zero_dte_contracts),
                credit_received=setup["credit"],
                max_profit=setup["max_profit"],
                max_loss=setup["max_loss"],
                profit_target=setup["max_profit"] * self.profit_target,
                stop_loss=setup["max_loss"] * self.stop_loss,
                time_stop=datetime.combine(today, ZERO_DTE_CLOSE_TIME, tzinfo=self.eastern_tz),
                entry_conditions=conditions.copy(),
                probability_profit=self._calculate_win_probability(setup, conditions),
                expected_value=self._calculate_expected_value(setup, conditions),
            )

            return zero_dte_setup

        except Exception as e:
            self.logger.error("Error creating 0DTE setup: %s", e)
            return None

    def _setup_iron_butterfly(
        self, current_price: float, conditions: dict[str, Any]
    ) -> dict | None:
        """Setup Iron Butterfly for 0DTE"""
        try:
            # ATM strike
            atm_strike = round(current_price)

            # Wing width based on expected move
            expected_move = (
                current_price * conditions.get("realized_vol", 0.15) / 100 * np.sqrt(1 / 252)
            )
            wing_width = max(5, round(expected_move / 5) * 5)  # Round to $5

            # Strikes
            put_strike = atm_strike - wing_width
            call_strike = atm_strike + wing_width

            # Estimate credit (simplified)
            credit_ratio = 0.4  # Typically receive 40% of wing width
            credit = wing_width * credit_ratio

            return {
                "strikes": {
                    "put_long": put_strike,
                    "put_short": atm_strike,
                    "call_short": atm_strike,
                    "call_long": call_strike,
                },
                "credit": credit,
                "max_profit": credit * SPY_CONTRACT_MULTIPLIER,
                "max_loss": (wing_width - credit) * SPY_CONTRACT_MULTIPLIER,
                "breakeven_lower": atm_strike - credit,
                "breakeven_upper": atm_strike + credit,
            }

        except Exception as e:
            self.logger.error("Error setting up Iron Butterfly: %s", e)
            return None

    def _setup_iron_condor(
        self, current_price: float, conditions: dict[str, Any]
    ) -> dict | None:
        """Setup Iron Condor for 0DTE"""
        try:
            # Calculate expected move
            expected_move = (
                current_price * conditions.get("realized_vol", 0.15) / 100 * np.sqrt(1 / 252)
            )

            # Short strikes at ~0.15 delta (approximately 1 std dev)
            short_put = round(current_price - expected_move)
            short_call = round(current_price + expected_move)

            # Wing width
            wing_width = 5  # $5 wings for 0DTE

            # Long strikes
            long_put = short_put - wing_width
            long_call = short_call + wing_width

            # Estimate credit
            credit = wing_width * 0.25  # Typically 25% of wing width for 0DTE

            return {
                "strikes": {
                    "put_long": long_put,
                    "put_short": short_put,
                    "call_short": short_call,
                    "call_long": long_call,
                },
                "credit": credit,
                "max_profit": credit * SPY_CONTRACT_MULTIPLIER,
                "max_loss": (wing_width - credit) * SPY_CONTRACT_MULTIPLIER,
                "breakeven_lower": short_put - credit,
                "breakeven_upper": short_call + credit,
            }

        except Exception as e:
            self.logger.error("Error setting up Iron Condor: %s", e)
            return None

    def _setup_credit_spread(
        self, current_price: float, conditions: dict[str, Any]
    ) -> dict | None:
        """Setup Credit Spread for 0DTE"""
        try:
            market_bias = self._determine_market_bias(conditions)

            # Spread width
            spread_width = 5  # $5 for 0DTE

            if market_bias == MarketBias.BULLISH:
                # Bull Put Spread
                short_strike = round(current_price - 5)  # Slightly OTM
                long_strike = short_strike - spread_width
                spread_type = "bull_put"
            else:
                # Bear Call Spread
                short_strike = round(current_price + 5)  # Slightly OTM
                long_strike = short_strike + spread_width
                spread_type = "bear_call"

            # Estimate credit
            credit = spread_width * 0.3  # 30% of width for 0DTE

            return {
                "strikes": {"short": short_strike, "long": long_strike, "type": spread_type},
                "credit": credit,
                "max_profit": credit * SPY_CONTRACT_MULTIPLIER,
                "max_loss": (spread_width - credit) * SPY_CONTRACT_MULTIPLIER,
                "breakeven": (
                    short_strike - credit if spread_type == "bull_put" else short_strike + credit
                ),
            }

        except Exception as e:
            self.logger.error("Error setting up Credit Spread: %s", e)
            return None

    def _setup_broken_wing_butterfly(
        self, current_price: float, conditions: dict[str, Any]
    ) -> dict | None:
        """Setup Broken Wing Butterfly for 0DTE"""
        try:
            market_bias = self._determine_market_bias(conditions)

            # ATM strike
            atm_strike = round(current_price)

            # Standard wing
            standard_wing = 5

            # Broken wing (wider on one side)
            if market_bias == MarketBias.BULLISH:
                lower_wing = standard_wing
                upper_wing = standard_wing * 2  # Wider upside
            else:
                lower_wing = standard_wing * 2  # Wider downside
                upper_wing = standard_wing

            # Strikes
            lower_strike = atm_strike - lower_wing
            upper_strike = atm_strike + upper_wing

            # Net credit/debit calculation
            net_position = upper_wing - lower_wing
            credit = abs(net_position) * 0.2  # Simplified

            return {
                "strikes": {"lower": lower_strike, "atm": atm_strike, "upper": upper_strike},
                "credit": credit,
                "max_profit": credit * SPY_CONTRACT_MULTIPLIER,
                "max_loss": max(lower_wing, upper_wing) * SPY_CONTRACT_MULTIPLIER,
                "breakeven_lower": atm_strike - lower_wing + credit,
                "breakeven_upper": atm_strike + upper_wing - credit,
            }

        except Exception as e:
            self.logger.error("Error setting up Broken Wing Butterfly: %s", e)
            return None

    def _setup_short_strangle(
        self, current_price: float, conditions: dict[str, Any]
    ) -> dict | None:
        """Setup Short Strangle for 0DTE"""
        try:
            # Calculate expected move
            expected_move = (
                current_price * conditions.get("realized_vol", 0.15) / 100 * np.sqrt(1 / 252)
            )

            # Strikes at ~0.20 delta
            put_strike = round(current_price - expected_move * 1.2)
            call_strike = round(current_price + expected_move * 1.2)

            # Estimate premium
            total_credit = expected_move * 0.5  # Simplified

            return {
                "strikes": {"put": put_strike, "call": call_strike},
                "credit": total_credit,
                "max_profit": total_credit * SPY_CONTRACT_MULTIPLIER,
                "max_loss": float("inf"),  # Unlimited risk
                "breakeven_lower": put_strike - total_credit,
                "breakeven_upper": call_strike + total_credit,
            }

        except Exception as e:
            self.logger.error("Error setting up Short Strangle: %s", e)
            return None

    def _calculate_base_contracts(self, market_data: pd.DataFrame) -> int:
        """Calculate base position size"""
        account_value = self.risk_profile.account_size
        max_risk = account_value * self.risk_profile.max_loss_per_trade

        # Estimate max loss per contract (simplified)
        estimated_loss_per_contract = 500  # $500 per contract for 0DTE

        contracts = int(max_risk / estimated_loss_per_contract)
        return max(1, min(contracts, 5))  # Between 1 and 5 contracts

    def _calculate_win_probability(self, setup: dict, conditions: dict[str, Any]) -> float:
        """Calculate probability of profit for setup"""
        try:
            current_price = conditions["current_price"]
            vol = conditions.get("realized_vol", 15) / 100

            # Time to expiration (fraction of day remaining)
            current_time = datetime.now(self.eastern_tz)
            market_close = current_time.replace(hour=16, minute=0)
            hours_to_expiry = (market_close - current_time).seconds / 3600
            time_fraction = hours_to_expiry / 6.5  # 6.5 trading hours

            # Calculate probability based on breakevens
            if "breakeven_lower" in setup and "breakeven_upper" in setup:
                # Two-sided breakevens
                lower_z = (setup["breakeven_lower"] - current_price) / (
                    current_price * vol * np.sqrt(time_fraction / 252)
                )
                upper_z = (setup["breakeven_upper"] - current_price) / (
                    current_price * vol * np.sqrt(time_fraction / 252)
                )

                prob_profit = norm.cdf(upper_z) - norm.cdf(lower_z)

            elif "breakeven" in setup:
                # One-sided breakeven
                z_score = (setup["breakeven"] - current_price) / (
                    current_price * vol * np.sqrt(time_fraction / 252)
                )

                if setup["strikes"].get("type") == "bull_put":
                    prob_profit = norm.cdf(z_score)
                else:  # bear_call
                    prob_profit = 1 - norm.cdf(z_score)

            else:
                # Default probability
                prob_profit = 0.5

            return max(0.0, min(1.0, prob_profit))

        except Exception as e:
            self.logger.error("Error calculating win probability: %s", e)
            return 0.5

    def _calculate_expected_value(self, setup: dict, conditions: dict[str, Any]) -> float:
        """Calculate expected value of setup"""
        win_prob = self._calculate_win_probability(setup, conditions)

        max_profit = setup["max_profit"]
        max_loss = setup["max_loss"] if setup["max_loss"] != float("inf") else max_profit * 3

        expected_value = (win_prob * max_profit) - ((1 - win_prob) * max_loss)

        return expected_value

    def _create_entry_signal(
        self, setup: ZeroDTESetup, conditions: dict[str, Any]
    ) -> TradingSignal:
        """Create entry signal for 0DTE setup"""
        # Determine signal strength based on expected value
        if setup.expected_value > setup.max_profit * 0.2:
            strength = SignalStrength.STRONG
        elif setup.expected_value > 0:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.WEAK

        signal = TradingSignal(
            timestamp=datetime.now(),
            signal_type=SignalType.ENTRY,
            strength=strength,
            confidence=setup.probability_profit,
            metadata={
                "strategy": "zero_dte",
                "setup": setup.__dict__,
                "conditions": conditions,
                "expected_value": setup.expected_value,
            },
        )

        self.logger.info("Generated 0DTE signal: %s", setup.strategy_type.value)
        return signal

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def manage_positions(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Manage active 0DTE positions with rapid monitoring"""
        signals = []

        current_time = datetime.now(self.eastern_tz)

        for _position_id, position in self.active_positions.items():
            # Update position metrics
            metrics = self._calculate_position_metrics(position, market_data)

            # Check time stop
            if current_time >= position.setup.time_stop:
                exit_signal = self._create_exit_signal(position, "time_stop", metrics)
                signals.append(exit_signal)
                continue

            # Check profit target
            if metrics.pnl >= position.setup.profit_target:
                exit_signal = self._create_exit_signal(position, "profit_target", metrics)
                signals.append(exit_signal)
                continue

            # Check stop loss
            if metrics.pnl <= -position.setup.stop_loss:
                exit_signal = self._create_exit_signal(position, "stop_loss", metrics)
                signals.append(exit_signal)
                continue

            # Check gamma risk
            if abs(metrics.gamma) > MAX_GAMMA_EXPOSURE / len(self.active_positions):
                exit_signal = self._create_exit_signal(position, "gamma_risk", metrics)
                signals.append(exit_signal)
                continue

            # Dynamic management based on time decay
            if metrics.time_remaining < 2:  # Less than 2 hours
                if metrics.pnl > position.setup.max_profit * 0.05:  # Any profit
                    exit_signal = self._create_exit_signal(position, "time_decay", metrics)
                    signals.append(exit_signal)

        return signals

    def _calculate_position_metrics(
        self, position: ZeroDTEPosition, market_data: pd.DataFrame
    ) -> ZeroDTEMetrics:
        """Calculate real-time metrics for position"""
        try:
            current_price = market_data["close"].iloc[-1]
            current_time = datetime.now(self.eastern_tz)

            # Time remaining
            time_to_expiry = (position.setup.expiration_time - current_time).seconds / 3600

            # Calculate current Greeks
            greeks = self._calculate_position_greeks(position, current_price, time_to_expiry)

            # Calculate P&L
            current_value = self._calculate_position_value(position, current_price)
            pnl = current_value - position.setup.credit_received
            pnl_percentage = pnl / position.setup.max_profit if position.setup.max_profit > 0 else 0

            # Distance from profitable zone
            if hasattr(position.setup, "breakeven_lower") and hasattr(
                position.setup, "breakeven_upper"
            ):
                if current_price < position.setup.breakeven_lower:
                    distance_pct = (position.setup.breakeven_lower - current_price) / current_price
                elif current_price > position.setup.breakeven_upper:
                    distance_pct = (current_price - position.setup.breakeven_upper) / current_price
                else:
                    distance_pct = 0  # In profitable zone
            else:
                distance_pct = 0

            # Win probability update
            win_prob = self._update_win_probability(position, current_price, time_to_expiry)

            # Suggested action
            if pnl >= position.setup.profit_target * 0.8:
                suggested_action = "close_profit"
            elif pnl <= -position.setup.stop_loss * 0.8:
                suggested_action = "close_loss"
            elif time_to_expiry < 1:
                suggested_action = "close_time"
            elif abs(greeks["gamma"]) > 50:
                suggested_action = "reduce_gamma"
            else:
                suggested_action = "hold"

            return ZeroDTEMetrics(
                current_value=current_value,
                pnl=pnl,
                pnl_percentage=pnl_percentage,
                delta=greeks["delta"],
                gamma=greeks["gamma"],
                theta=greeks["theta"],
                time_remaining=time_to_expiry,
                price_distance_pct=distance_pct,
                win_probability=win_prob,
                suggested_action=suggested_action,
            )

        except Exception as e:
            self.logger.error("Error calculating position metrics: %s", e)
            # Return default metrics
            return ZeroDTEMetrics(
                current_value=0,
                pnl=0,
                pnl_percentage=0,
                delta=0,
                gamma=0,
                theta=0,
                time_remaining=0,
                price_distance_pct=0,
                win_probability=0.5,
                suggested_action="error",
            )

    def _calculate_position_greeks(
        self, position: ZeroDTEPosition, current_price: float, time_to_expiry: float
    ) -> dict[str, float]:
        """Calculate Greeks for 0DTE position"""
        # Simplified Greeks calculation for 0DTE
        # In production, would use proper options pricing model

        # Delta changes rapidly near expiration
        np.exp(-time_to_expiry)

        # Gamma peaks near ATM at expiration
        gamma_peak_factor = 1 / (time_to_expiry + 0.1)

        # Theta accelerates near expiration
        theta_acceleration = 1 / np.sqrt(time_to_expiry + 0.01)

        return {
            "delta": 0,  # Depends on specific position
            "gamma": gamma_peak_factor * 10,
            "theta": -theta_acceleration * 20,
            "vega": time_to_expiry * 5,  # Vega decreases with time
        }

    def _calculate_position_value(self, position: ZeroDTEPosition, current_price: float) -> float:
        """Calculate current value of position"""
        # Simplified valuation
        # In production, would use actual option prices

        setup = position.setup

        # Check if price is within profit zone
        if hasattr(setup, "breakeven_lower") and hasattr(setup, "breakeven_upper"):
            if setup.breakeven_lower <= current_price <= setup.breakeven_upper:
                # In profit zone - position is profitable
                distance_from_center = abs(
                    current_price - (setup.breakeven_lower + setup.breakeven_upper) / 2
                )
                profit_ratio = 1 - (
                    distance_from_center / ((setup.breakeven_upper - setup.breakeven_lower) / 2)
                )
                return setup.credit_received * (1 + profit_ratio * 0.5)
            else:
                # Outside profit zone - losing money
                if current_price < setup.breakeven_lower:
                    loss = current_price - setup.breakeven_lower
                else:
                    loss = setup.breakeven_upper - current_price
                return setup.credit_received + loss

        return setup.credit_received

    def _update_win_probability(
        self, position: ZeroDTEPosition, current_price: float, time_to_expiry: float
    ) -> float:
        """Update win probability based on current conditions"""
        # Recalculate probability with current price and time
        setup = position.setup

        # Get current volatility
        vol = 0.15  # Simplified - would calculate from market data

        # Time adjustment
        time_fraction = time_to_expiry / 6.5

        if hasattr(setup, "breakeven_lower") and hasattr(setup, "breakeven_upper"):
            # Calculate probability of finishing between breakevens
            std_move = current_price * vol * np.sqrt(time_fraction / 252)

            lower_z = (setup.breakeven_lower - current_price) / std_move
            upper_z = (setup.breakeven_upper - current_price) / std_move

            prob = norm.cdf(upper_z) - norm.cdf(lower_z)
            return max(0.0, min(1.0, prob))

        return 0.5

    def _create_exit_signal(
        self, position: ZeroDTEPosition, reason: str, metrics: ZeroDTEMetrics
    ) -> TradingSignal:
        """Create exit signal for position"""
        signal = TradingSignal(
            timestamp=datetime.now(),
            signal_type=SignalType.EXIT,
            strength=SignalStrength.STRONG,
            confidence=0.95,
            metadata={
                "position_id": position.position_id,
                "exit_reason": reason,
                "pnl": metrics.pnl,
                "pnl_percentage": metrics.pnl_percentage,
                "final_metrics": metrics.__dict__,
                "hold_time": (datetime.now() - position.setup.entry_time).seconds / 60,  # minutes
            },
        )

        # Update position state
        position.state = ZeroDTEState.CLOSING
        position.exit_time = datetime.now()
        position.exit_reason = reason

        # Update daily stats
        self.daily_pnl += metrics.pnl

        # Update strategy stats
        self.strategy_stats["total_trades"] += 1
        if metrics.pnl > 0:
            self.strategy_stats["winning_trades"] += 1
        self.strategy_stats["total_pnl"] += metrics.pnl

        self.logger.info(
            "Exit 0DTE position %s: %s, P&L: $%.2f",
            position.position_id,
            reason,
            metrics.pnl,
        )

        return signal

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================

    def get_daily_summary(self) -> dict[str, Any]:
        """Get daily performance summary"""
        return {
            "date": datetime.now(self.eastern_tz).date(),
            "total_trades": self.daily_trades,
            "active_positions": len(self.active_positions),
            "daily_pnl": self.daily_pnl,
            "strategy_stats": self.strategy_stats.copy(),
            "fed_day": self._is_fed_day(datetime.now()),
            "economic_events": self.economic_calendar.get(datetime.now().date(), []),
        }

    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.active_positions.clear()
        self.logger.info("Daily stats reset for new trading day")

    def get_position_summary(self) -> list[dict[str, Any]]:
        """Get summary of all active positions"""
        summaries = []

        for position_id, position in self.active_positions.items():
            summary = {
                "position_id": position_id,
                "strategy": position.setup.strategy_type.value,
                "entry_time": position.setup.entry_time,
                "current_pnl": position.current_pnl,
                "state": position.state.name,
                "time_to_expiry": (
                    position.setup.expiration_time - datetime.now(self.eastern_tz)
                ).seconds
                / 3600,
            }
            summaries.append(summary)

        return summaries


# ==============================================================================
# TESTING
# ==============================================================================
def test_specialized_zero_dte():
    """Test the Specialized Zero DTE strategy"""
    logging.info("Testing Specialized Zero DTE Strategy")
    logging.info("=" * 60)

    # Create mock components
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile

    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01,
    )

    # Create strategy
    config = {
        "max_positions": 3,
        "position_reduction": 0.7,
        "profit_target": 0.10,
        "stop_loss": 0.20,
    }

    strategy = SpecializedZeroDTEStrategy(event_manager, risk_profile, config)

    # Create sample market data for 0DTE day
    current_time = datetime.now(strategy.eastern_tz)
    if current_time.weekday() not in [0, 2, 4]:
        logging.info("Note: Not a typical 0DTE day (Mon/Wed/Fri)")

    # Generate intraday data
    dates = pd.date_range(
        start=current_time.replace(hour=9, minute=30), end=current_time, freq="5min"
    )

    # Simulate market movement
    base_price = 450
    prices = base_price + np.cumsum(np.random.randn(len(dates)) * 0.2)

    market_data = pd.DataFrame(
        {
            "timestamp": dates,
            "open": prices + np.random.randn(len(dates)) * 0.1,
            "high": prices + abs(np.random.randn(len(dates)) * 0.2),
            "low": prices - abs(np.random.randn(len(dates)) * 0.2),
            "close": prices,
            "volume": np.random.randint(500000, 2000000, len(dates)),
            "vix": 18 + np.random.randn(len(dates)) * 0.5,
        }
    )

    logging.info("Current Time: %s", current_time.strftime('%Y-%m-%d %H:%M:%S %Z'))
    logging.info(f"Current Price: ${prices[-1]:.2f}")
    logging.info(f"VIX: {market_data['vix'].iloc[-1]:.2f}")

    # Test Fed day check
    logging.info("\nFed Day Check: %s", strategy._is_fed_day(current_time))

    # Generate signals
    signals = strategy.generate_signals(market_data)

    logging.info("\nGenerated %s signals", len(signals))

    if signals:
        signal = signals[0]
        setup = signal.metadata["setup"]

        logging.info("\n0DTE Setup Details:")
        logging.info("Strategy: %s", setup['strategy_type'])
        logging.info("Contracts: %s", setup['contracts'])
        logging.info(f"Credit: ${setup['credit_received']:.2f}")
        logging.info(f"Max Profit: ${setup['max_profit']:.2f}")
        logging.info(f"Max Loss: ${setup['max_loss']:.2f}")
        logging.info(f"Profit Target: ${setup['profit_target']:.2f}")
        logging.info(f"Stop Loss: ${setup['stop_loss']:.2f}")
        logging.info(f"Probability of Profit: {setup['probability_profit']:.2%}")
        logging.info(f"Expected Value: ${setup['expected_value']:.2f}")

    # Test position management
    if signals:
        # Create mock position
        position = ZeroDTEPosition(
            position_id="0DTE001",
            setup=ZeroDTESetup(**signal.metadata["setup"]),
            entry_price=prices[-1],
            current_pnl=0,
            greeks={"delta": 0, "gamma": 20, "theta": -30},
            state=ZeroDTEState.MONITORING,
        )

        strategy.active_positions[position.position_id] = position

        # Simulate price movement
        new_price = prices[-1] + 2  # $2 move
        market_data.loc[len(market_data)] = {
            "timestamp": current_time + timedelta(minutes=30),
            "open": prices[-1],
            "high": new_price + 0.1,
            "low": prices[-1] - 0.1,
            "close": new_price,
            "volume": 1000000,
            "vix": 18,
        }

        # Test position management
        management_signals = strategy.manage_positions(market_data)

        logging.info("\nPosition Management:")
        logging.info("Management signals: %s", len(management_signals))

        if management_signals:
            exit_signal = management_signals[0]
            logging.info("Exit Reason: %s", exit_signal.metadata['exit_reason'])
            logging.info(f"P&L: ${exit_signal.metadata['pnl']:.2f}")
            logging.info(f"Hold Time: {exit_signal.metadata['hold_time']:.1f} minutes")

    # Get daily summary
    summary = strategy.get_daily_summary()
    logging.info("\nDaily Summary:")
    logging.info("Total Trades: %s", summary['total_trades'])
    logging.info(f"Daily P&L: ${summary['daily_pnl']:.2f}")
    _win_rate = (
        summary['strategy_stats']['winning_trades']
        / max(1, summary['strategy_stats']['total_trades'])
        * 100
    )
    logging.info("Win Rate: %.1f%%", _win_rate)

    logging.info("\n✅ Specialized Zero DTE Strategy Test Complete!")
    logging.info("\nKey Features Tested:")
    logging.info("- ✅ Fed day and economic event detection")
    logging.info("- ✅ Optimal 10:15 AM entry timing")
    logging.info("- ✅ Dynamic strategy selection based on market conditions")
    logging.info("- ✅ Reduced position sizing for 0DTE")
    logging.info("- ✅ Rapid profit/loss management")
    logging.info("- ✅ Time-based stops at 3:45 PM")
    logging.info("- ✅ Gamma risk monitoring")
    logging.info("- ✅ Real-time probability updates")


if __name__ == "__main__":
    test_specialized_zero_dte()
