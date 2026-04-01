#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD27_EarningsStrategy.py
Purpose: Earnings event-based options trading strategies with IV crush plays

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-12-27

Module Description:
    This module provides comprehensive earnings-based options strategies:
    - Expected move calculation from straddle pricing
    - IV crush prediction and trading
    - Pre-earnings IV expansion plays
    - Post-earnings directional plays
    - Straddle/Strangle selling for IV crush
    - Iron condor positioning around expected moves

    Key concepts:
    - IV Crush: Sharp decline in implied volatility after earnings announcement
    - Expected Move: ATM straddle price represents market's expected move
    - IV Rush: Increase in IV as earnings approach

References:
    - Option Alpha: IV Crush and Earnings Strategies
    - CBOE: Options and Earnings Events
    - Research on earnings volatility patterns
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Optional, Any
from enum import Enum
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
try:
    from Spyder.SpyderB_Broker.SpyderB40_TradierClient import (
        TradierClient,
        GreekData,
        create_tradier_client_from_env,
    )
    HAS_TRADIER = True
except ImportError:
    TradierClient = None  # type: ignore[assignment,misc]
    GreekData = None  # type: ignore[assignment,misc]
    create_tradier_client_from_env = None  # type: ignore[assignment]
    HAS_TRADIER = False
try:
    from Spyder.SpyderC_MarketData.SpyderC00_MarketDataProtocol import (
        OptionsDataProvider,
        create_options_data_provider,
    )
except ImportError:
    OptionsDataProvider = None  # type: ignore[assignment,misc]
    create_options_data_provider = None  # type: ignore[assignment]

# ==============================================================================
# CONSTANTS
# ==============================================================================
EARNINGS_LOOKBACK_QUARTERS = 8  # Historical earnings for analysis
IV_CRUSH_THRESHOLD = 0.3  # 30% IV drop considered significant
EXPECTED_MOVE_BUFFER = 1.1  # 10% buffer on expected move

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = SpyderLogger.get_logger(__name__)


# ==============================================================================
# ENUMS
# ==============================================================================
class EarningsPhase(Enum):
    """Current phase relative to earnings."""
    PRE_EARNINGS = "pre_earnings"      # Before announcement
    EARNINGS_DAY = "earnings_day"      # Day of announcement
    POST_EARNINGS = "post_earnings"    # After announcement
    NO_EARNINGS = "no_earnings"        # No upcoming earnings


class EarningsStrategy(Enum):
    """Earnings strategy types."""
    STRADDLE_SELL = "straddle_sell"           # Sell ATM straddle for IV crush
    STRANGLE_SELL = "strangle_sell"           # Sell OTM strangle for IV crush
    IRON_CONDOR = "iron_condor"               # IC outside expected move
    IRON_BUTTERFLY = "iron_butterfly"         # Iron butterfly at expected close
    CALENDAR_SPREAD = "calendar_spread"       # Sell front, buy back
    DIRECTIONAL_SPREAD = "directional_spread" # Directional bet post-earnings
    STRADDLE_BUY = "straddle_buy"            # Buy for big move expectation


class EarningsBias(Enum):
    """Directional bias for earnings."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TradeAction(Enum):
    """Trade action recommendation."""
    ENTER = "enter"
    WAIT = "wait"
    SKIP = "skip"
    EXIT = "exit"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class EarningsEvent:
    """Single earnings event."""
    symbol: str
    earnings_date: date
    earnings_time: str  # "BMO" (before market open), "AMC" (after market close)
    quarter: str        # e.g., "Q4 2024"
    eps_estimate: float | None = None
    eps_actual: float | None = None
    revenue_estimate: float | None = None
    revenue_actual: float | None = None
    surprise_percent: float | None = None
    price_move_percent: float | None = None

    @property
    def is_upcoming(self) -> bool:
        return self.earnings_date >= date.today()

    @property
    def days_until(self) -> int:
        return (self.earnings_date - date.today()).days

    @property
    def is_beat(self) -> bool | None:
        if self.eps_actual is None or self.eps_estimate is None:
            return None
        return self.eps_actual > self.eps_estimate

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "earnings_date": self.earnings_date.isoformat(),
            "earnings_time": self.earnings_time,
            "quarter": self.quarter,
            "eps_estimate": self.eps_estimate,
            "eps_actual": self.eps_actual,
            "surprise_percent": self.surprise_percent,
            "days_until": self.days_until,
            "is_upcoming": self.is_upcoming,
        }


@dataclass
class ExpectedMove:
    """Expected move calculation from options pricing."""
    symbol: str
    timestamp: datetime
    current_price: float
    expected_move_dollars: float
    expected_move_percent: float
    upper_expected: float  # Current + expected move
    lower_expected: float  # Current - expected move
    straddle_price: float  # ATM straddle price (raw expected move)
    implied_volatility: float
    days_to_expiry: int
    confidence_1sd: float  # ~68% probability range
    confidence_2sd: float  # ~95% probability range

    @property
    def expected_range(self) -> tuple[float, float]:
        return (self.lower_expected, self.upper_expected)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "expected_move_dollars": self.expected_move_dollars,
            "expected_move_percent": self.expected_move_percent,
            "upper_expected": self.upper_expected,
            "lower_expected": self.lower_expected,
            "straddle_price": self.straddle_price,
            "implied_volatility": self.implied_volatility,
            "expected_range": self.expected_range,
        }


@dataclass
class IVCrushAnalysis:
    """IV crush prediction analysis."""
    symbol: str
    timestamp: datetime
    current_iv: float
    historical_avg_iv: float
    historical_post_earnings_iv: float
    expected_iv_crush_percent: float
    iv_percentile: float  # Current IV rank
    historical_crush_avg: float  # Average historical IV crush
    is_iv_elevated: bool
    crush_probability: float
    optimal_strategy: EarningsStrategy

    @property
    def is_favorable_for_selling(self) -> bool:
        """Check if conditions favor selling premium."""
        return (
            self.is_iv_elevated and
            self.expected_iv_crush_percent > 20 and
            self.crush_probability > 0.7
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_iv": self.current_iv,
            "historical_avg_iv": self.historical_avg_iv,
            "expected_iv_crush_percent": self.expected_iv_crush_percent,
            "iv_percentile": self.iv_percentile,
            "is_iv_elevated": self.is_iv_elevated,
            "crush_probability": self.crush_probability,
            "optimal_strategy": self.optimal_strategy.value,
            "is_favorable_for_selling": self.is_favorable_for_selling,
        }


@dataclass
class EarningsTradeSetup:
    """Complete trade setup for earnings play."""
    symbol: str
    strategy: EarningsStrategy
    action: TradeAction
    earnings_event: EarningsEvent
    expected_move: ExpectedMove
    iv_analysis: IVCrushAnalysis
    entry_timing: str
    strikes: dict[str, float]
    expiry: date
    max_profit: float
    max_loss: float
    probability_of_profit: float
    risk_reward_ratio: float
    rationale: str
    warnings: list[str] = field(default_factory=list)

    @property
    def is_recommended(self) -> bool:
        return (
            self.action == TradeAction.ENTER and
            self.probability_of_profit >= 0.5 and
            len(self.warnings) == 0
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy.value,
            "action": self.action.value,
            "earnings_date": self.earnings_event.earnings_date.isoformat(),
            "strikes": self.strikes,
            "expiry": self.expiry.isoformat(),
            "max_profit": self.max_profit,
            "max_loss": self.max_loss,
            "probability_of_profit": self.probability_of_profit,
            "risk_reward_ratio": self.risk_reward_ratio,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "is_recommended": self.is_recommended,
        }


@dataclass
class HistoricalEarningsPattern:
    """Historical earnings behavior patterns."""
    symbol: str
    quarters_analyzed: int
    avg_move_percent: float
    avg_iv_crush_percent: float
    beat_rate: float  # % of beats
    move_vs_expected_ratio: float  # Actual move / expected move
    positive_surprise_avg_move: float
    negative_surprise_avg_move: float
    consistency_score: float  # How consistent is behavior

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "quarters_analyzed": self.quarters_analyzed,
            "avg_move_percent": self.avg_move_percent,
            "avg_iv_crush_percent": self.avg_iv_crush_percent,
            "beat_rate": self.beat_rate,
            "move_vs_expected_ratio": self.move_vs_expected_ratio,
            "consistency_score": self.consistency_score,
        }


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class EarningsStrategyHandler:
    """
    Comprehensive earnings-based options trading handler.

    Provides:
    - Earnings calendar tracking
    - Expected move calculation
    - IV crush analysis and prediction
    - Strategy selection and trade setup
    - Historical pattern analysis

    Example:
        >>> handler = EarningsStrategyHandler()
        >>> setup = handler.get_earnings_trade("AAPL")
        >>> if setup.is_recommended:
        ...     print(f"Strategy: {setup.strategy.value}")
        ...     print(f"Strikes: {setup.strikes}")
        ...     print(f"POP: {setup.probability_of_profit:.1%}")
    """

    def __init__(
        self,
        data_provider: Optional['OptionsDataProvider'] = None,
        default_expiry_days: int = 7
    ):
        """
        Initialize Earnings Strategy Handler.

        Args:
            data_provider: OptionsDataProvider instance (e.g. TradierClient or
                DatabentoMarketDataAdapter). If None, auto-created via
                create_options_data_provider() using MARKET_DATA_PROVIDER env var.
            default_expiry_days: Default days for expiry selection
        """
        self.default_expiry_days = default_expiry_days
        if data_provider is not None:
            self._data_provider: Any = data_provider
        elif create_options_data_provider is not None:
            try:
                self._data_provider = create_options_data_provider()
            except Exception as e:
                logger.warning(f"OptionsDataProvider unavailable: {e}", exc_info=True)
                self._data_provider = None
        else:
            self._data_provider = None

        # Caches
        self._earnings_cache: dict[str, list[EarningsEvent]] = {}
        self._iv_cache: dict[str, tuple[float, datetime]] = {}

        logger.info("EarningsStrategyHandler initialized")

    # ==========================================================================
    # EARNINGS CALENDAR
    # ==========================================================================

    def get_upcoming_earnings(
        self,
        symbol: str,
        days_ahead: int = 30
    ) -> list[EarningsEvent]:
        """
        Get upcoming earnings events for a symbol.

        Args:
            symbol: Stock symbol
            days_ahead: Days to look ahead

        Returns:
            List of EarningsEvent
        """
        try:
            # Check cache
            if symbol in self._earnings_cache:
                cached = [e for e in self._earnings_cache[symbol] if e.is_upcoming]
                if cached:
                    return cached

            # Fetch from API
            events = self._fetch_earnings_calendar(symbol, days_ahead)
            self._earnings_cache[symbol] = events

            return [e for e in events if e.is_upcoming]

        except Exception as e:
            logger.error(f"Earnings fetch failed: {e}", exc_info=True)
            return []

    def get_next_earnings(self, symbol: str) -> EarningsEvent | None:
        """Get next upcoming earnings event."""
        upcoming = self.get_upcoming_earnings(symbol)
        return upcoming[0] if upcoming else None

    def get_earnings_phase(self, symbol: str) -> EarningsPhase:
        """Determine current phase relative to earnings."""
        next_earnings = self.get_next_earnings(symbol)

        if not next_earnings:
            return EarningsPhase.NO_EARNINGS

        days = next_earnings.days_until

        if days == 0:
            return EarningsPhase.EARNINGS_DAY
        elif days > 0:
            return EarningsPhase.PRE_EARNINGS
        else:
            return EarningsPhase.POST_EARNINGS

    def _fetch_earnings_calendar(
        self,
        symbol: str,
        days_ahead: int
    ) -> list[EarningsEvent]:
        """Fetch earnings calendar from API."""
        try:
            # Using a mock/estimated approach; Databento integration pending
            # In production, would integrate with Earnings Whispers, Zacks, etc.

            # For SPY/ETFs, there are no earnings
            if symbol in ["SPY", "QQQ", "IWM", "DIA"]:
                return []

            # Estimate next earnings (quarterly)
            today = date.today()
            # Companies typically report ~45 days after quarter end
            quarters_end = [
                date(today.year, 3, 31),
                date(today.year, 6, 30),
                date(today.year, 9, 30),
                date(today.year, 12, 31),
            ]

            events = []
            for qe in quarters_end:
                earnings_date = qe + timedelta(days=45)
                if earnings_date >= today and (earnings_date - today).days <= days_ahead:
                    quarter = f"Q{(qe.month - 1) // 3 + 1} {qe.year}"
                    events.append(EarningsEvent(
                        symbol=symbol,
                        earnings_date=earnings_date,
                        earnings_time="AMC",
                        quarter=quarter
                    ))

            return events

        except Exception as e:
            logger.error(f"Earnings calendar fetch error: {e}", exc_info=True)
            return []

    # ==========================================================================
    # EXPECTED MOVE CALCULATION
    # ==========================================================================

    def calculate_expected_move(
        self,
        symbol: str,
        expiry: date | None = None
    ) -> ExpectedMove:
        """
        Calculate expected move from ATM straddle pricing.

        The expected move is the market's implied range for the stock
        based on options pricing.

        Formula: Expected Move = ATM Call Price + ATM Put Price

        Args:
            symbol: Stock symbol
            expiry: Target expiration (default: nearest post-earnings)

        Returns:
            ExpectedMove with calculations

        Example:
            >>> em = handler.calculate_expected_move("AAPL")
            >>> print(f"Expected Move: ±${em.expected_move_dollars:.2f}")
            >>> print(f"Range: ${em.lower_expected:.2f} - ${em.upper_expected:.2f}")
        """
        try:
            current_price = self._get_current_price(symbol)
            if current_price == 0:
                return self._empty_expected_move(symbol)

            # Get expiry if not specified
            if expiry is None:
                next_earnings = self.get_next_earnings(symbol)
                if next_earnings:
                    expiry = self._get_expiry_after_earnings(next_earnings.earnings_date)
                else:
                    expiry = self._get_nearest_expiry(symbol)

            days_to_expiry = (expiry - date.today()).days

            # Fetch ATM options
            chain = self._fetch_option_chain(symbol, expiry)
            if chain.empty:
                return self._empty_expected_move(symbol)

            # Find ATM strike
            strikes = sorted(chain['strike'].unique())
            atm_strike = min(strikes, key=lambda x: abs(x - current_price))

            # Get ATM call and put prices
            calls = chain[(chain['strike'] == atm_strike) &
                         (chain['contract_type'].str.lower() == 'call')]
            puts = chain[(chain['strike'] == atm_strike) &
                        (chain['contract_type'].str.lower() == 'put')]

            if calls.empty or puts.empty:
                return self._empty_expected_move(symbol)

            call_price = calls.iloc[0].get('last_price', 0)
            put_price = puts.iloc[0].get('last_price', 0)

            # Straddle price = expected move
            straddle_price = call_price + put_price
            expected_move_dollars = straddle_price
            expected_move_percent = (straddle_price / current_price) * 100

            # Calculate range
            upper = current_price + expected_move_dollars
            lower = current_price - expected_move_dollars

            # Get IV
            iv = calls.iloc[0].get('implied_volatility', 0.3)

            return ExpectedMove(
                symbol=symbol,
                timestamp=datetime.now(),
                current_price=current_price,
                expected_move_dollars=expected_move_dollars,
                expected_move_percent=expected_move_percent,
                upper_expected=upper,
                lower_expected=lower,
                straddle_price=straddle_price,
                implied_volatility=iv,
                days_to_expiry=days_to_expiry,
                confidence_1sd=0.68,
                confidence_2sd=0.95
            )

        except Exception as e:
            logger.error(f"Expected move calculation failed: {e}", exc_info=True)
            return self._empty_expected_move(symbol)

    def _empty_expected_move(self, symbol: str) -> ExpectedMove:
        """Return empty expected move."""
        return ExpectedMove(
            symbol=symbol,
            timestamp=datetime.now(),
            current_price=0,
            expected_move_dollars=0,
            expected_move_percent=0,
            upper_expected=0,
            lower_expected=0,
            straddle_price=0,
            implied_volatility=0,
            days_to_expiry=0,
            confidence_1sd=0,
            confidence_2sd=0
        )

    # ==========================================================================
    # IV CRUSH ANALYSIS
    # ==========================================================================

    def analyze_iv_crush(
        self,
        symbol: str,
        expiry: date | None = None
    ) -> IVCrushAnalysis:
        """
        Analyze expected IV crush after earnings.

        IV crush occurs when implied volatility drops sharply after the
        uncertainty of earnings is resolved.

        Args:
            symbol: Stock symbol
            expiry: Target expiration

        Returns:
            IVCrushAnalysis with predictions

        Example:
            >>> analysis = handler.analyze_iv_crush("AAPL")
            >>> if analysis.is_favorable_for_selling:
            ...     print("Good setup for selling premium")
        """
        try:
            # Get current IV
            current_iv = self._get_current_iv(symbol)

            # Get historical IV patterns
            historical = self._get_historical_iv_pattern(symbol)

            # Calculate IV percentile
            iv_percentile = self._calculate_iv_percentile(symbol, current_iv)

            # Estimate post-earnings IV
            historical_post_iv = historical.get('post_earnings_iv', current_iv * 0.7)
            expected_crush = ((current_iv - historical_post_iv) / current_iv) * 100

            # Is IV elevated?
            is_elevated = iv_percentile > 60

            # Crush probability based on historical data
            crush_prob = historical.get('crush_probability', 0.8)

            # Determine optimal strategy
            if is_elevated and expected_crush > 30:
                if iv_percentile > 80:
                    optimal = EarningsStrategy.STRADDLE_SELL
                else:
                    optimal = EarningsStrategy.IRON_CONDOR
            elif expected_crush > 20:
                optimal = EarningsStrategy.STRANGLE_SELL
            else:
                optimal = EarningsStrategy.CALENDAR_SPREAD

            return IVCrushAnalysis(
                symbol=symbol,
                timestamp=datetime.now(),
                current_iv=current_iv,
                historical_avg_iv=historical.get('avg_iv', current_iv),
                historical_post_earnings_iv=historical_post_iv,
                expected_iv_crush_percent=expected_crush,
                iv_percentile=iv_percentile,
                historical_crush_avg=historical.get('avg_crush', 25),
                is_iv_elevated=is_elevated,
                crush_probability=crush_prob,
                optimal_strategy=optimal
            )

        except Exception as e:
            logger.error(f"IV crush analysis failed: {e}", exc_info=True)
            return IVCrushAnalysis(
                symbol=symbol,
                timestamp=datetime.now(),
                current_iv=0.3,
                historical_avg_iv=0.25,
                historical_post_earnings_iv=0.2,
                expected_iv_crush_percent=30,
                iv_percentile=50,
                historical_crush_avg=25,
                is_iv_elevated=False,
                crush_probability=0.7,
                optimal_strategy=EarningsStrategy.IRON_CONDOR
            )

    def _get_current_iv(self, symbol: str) -> float:
        """Get current implied volatility."""
        # Check cache
        if symbol in self._iv_cache:
            iv, cache_time = self._iv_cache[symbol]
            if (datetime.now() - cache_time).seconds < 300:
                return iv

        try:
            expiry = self._get_nearest_expiry(symbol)
            chain = self._fetch_option_chain(symbol, expiry)

            if chain.empty:
                return 0.3  # Default

            iv = chain['implied_volatility'].mean()
            self._iv_cache[symbol] = (iv, datetime.now())
            return iv

        except Exception:
            return 0.3

    def _calculate_iv_percentile(self, symbol: str, current_iv: float) -> float:
        """Calculate IV percentile (rank)."""
        # Would use historical IV data
        # For now, estimate based on typical ranges
        if current_iv > 0.5:
            return 90
        elif current_iv > 0.4:
            return 75
        elif current_iv > 0.3:
            return 50
        elif current_iv > 0.2:
            return 25
        else:
            return 10

    def _get_historical_iv_pattern(self, symbol: str) -> dict[str, float]:
        """Get historical IV pattern around earnings."""
        # Would analyze historical data
        # Return typical patterns
        return {
            'avg_iv': 0.25,
            'pre_earnings_iv': 0.35,
            'post_earnings_iv': 0.22,
            'avg_crush': 35,
            'crush_probability': 0.85
        }

    # ==========================================================================
    # STRATEGY GENERATION
    # ==========================================================================

    def get_earnings_trade(
        self,
        symbol: str,
        strategy: EarningsStrategy | None = None,
        bias: EarningsBias = EarningsBias.NEUTRAL
    ) -> EarningsTradeSetup:
        """
        Generate complete earnings trade setup.

        Args:
            symbol: Stock symbol
            strategy: Specific strategy (or auto-select)
            bias: Directional bias if any

        Returns:
            EarningsTradeSetup with complete trade details

        Example:
            >>> setup = handler.get_earnings_trade("AAPL")
            >>> print(f"Strategy: {setup.strategy.value}")
            >>> print(f"Strikes: {setup.strikes}")
            >>> print(f"Max Profit: ${setup.max_profit:.2f}")
        """
        # Get earnings info
        earnings = self.get_next_earnings(symbol)
        if not earnings:
            return self._no_earnings_setup(symbol)

        # Calculate expected move
        expected_move = self.calculate_expected_move(symbol)

        # Analyze IV crush
        iv_analysis = self.analyze_iv_crush(symbol)

        # Select strategy if not specified
        if strategy is None:
            strategy = self._select_optimal_strategy(
                earnings, expected_move, iv_analysis, bias
            )

        # Generate strikes based on strategy
        strikes, expiry = self._generate_strikes(
            symbol, strategy, expected_move, earnings
        )

        # Calculate risk/reward
        max_profit, max_loss, pop = self._calculate_risk_reward(
            strategy, strikes, expected_move
        )

        # Determine action timing
        entry_timing = self._get_entry_timing(earnings, strategy)

        # Generate rationale
        rationale = self._generate_rationale(
            symbol, strategy, expected_move, iv_analysis, earnings
        )

        # Check for warnings
        warnings = self._check_warnings(
            symbol, strategy, expected_move, iv_analysis
        )

        # Determine action
        action = self._determine_action(
            earnings, iv_analysis, pop, warnings
        )

        return EarningsTradeSetup(
            symbol=symbol,
            strategy=strategy,
            action=action,
            earnings_event=earnings,
            expected_move=expected_move,
            iv_analysis=iv_analysis,
            entry_timing=entry_timing,
            strikes=strikes,
            expiry=expiry,
            max_profit=max_profit,
            max_loss=max_loss,
            probability_of_profit=pop,
            risk_reward_ratio=max_profit / max_loss if max_loss > 0 else 0,
            rationale=rationale,
            warnings=warnings
        )

    def _select_optimal_strategy(
        self,
        earnings: EarningsEvent,
        expected_move: ExpectedMove,
        iv_analysis: IVCrushAnalysis,
        bias: EarningsBias
    ) -> EarningsStrategy:
        """Select optimal strategy based on conditions."""
        days_until = earnings.days_until

        # Pre-earnings strategies
        if days_until > 3:
            if bias != EarningsBias.NEUTRAL:
                return EarningsStrategy.DIRECTIONAL_SPREAD
            return EarningsStrategy.CALENDAR_SPREAD

        # Close to earnings - IV crush plays
        if iv_analysis.is_favorable_for_selling:
            if iv_analysis.iv_percentile > 80:
                return EarningsStrategy.STRADDLE_SELL
            elif iv_analysis.iv_percentile > 60:
                return EarningsStrategy.IRON_CONDOR
            else:
                return EarningsStrategy.STRANGLE_SELL
        else:
            # Low IV - consider buying
            if expected_move.expected_move_percent < 3:
                return EarningsStrategy.STRADDLE_BUY
            return EarningsStrategy.IRON_CONDOR

    def _generate_strikes(
        self,
        symbol: str,
        strategy: EarningsStrategy,
        expected_move: ExpectedMove,
        earnings: EarningsEvent
    ) -> tuple[dict[str, float], date]:
        """Generate strike prices for strategy."""
        current = expected_move.current_price
        em = expected_move.expected_move_dollars * EXPECTED_MOVE_BUFFER

        # Get expiry after earnings
        expiry = self._get_expiry_after_earnings(earnings.earnings_date)

        # Round to nearest strike
        def round_strike(price: float, direction: int = 0) -> float:
            # Round to nearest $1 for most stocks, $5 for indices
            increment = 1 if current < 100 else 5
            if direction > 0:  # Round up
                return np.ceil(price / increment) * increment
            elif direction < 0:  # Round down
                return np.floor(price / increment) * increment
            return round(price / increment) * increment

        strikes = {}

        if strategy == EarningsStrategy.STRADDLE_SELL:
            atm = round_strike(current)
            strikes = {"call": atm, "put": atm}

        elif strategy == EarningsStrategy.STRANGLE_SELL:
            strikes = {
                "short_call": round_strike(current + em, 1),
                "short_put": round_strike(current - em, -1)
            }

        elif strategy == EarningsStrategy.IRON_CONDOR:
            strikes = {
                "short_call": round_strike(current + em, 1),
                "long_call": round_strike(current + em + 5, 1),
                "short_put": round_strike(current - em, -1),
                "long_put": round_strike(current - em - 5, -1)
            }

        elif strategy == EarningsStrategy.IRON_BUTTERFLY:
            atm = round_strike(current)
            strikes = {
                "short_call": atm,
                "long_call": atm + 5,
                "short_put": atm,
                "long_put": atm - 5
            }

        elif strategy == EarningsStrategy.STRADDLE_BUY:
            atm = round_strike(current)
            strikes = {"call": atm, "put": atm}

        elif strategy == EarningsStrategy.DIRECTIONAL_SPREAD:
            strikes = {
                "long_call": round_strike(current, 1),
                "short_call": round_strike(current + 5, 1)
            }

        return strikes, expiry

    def _calculate_risk_reward(
        self,
        strategy: EarningsStrategy,
        strikes: dict[str, float],
        expected_move: ExpectedMove
    ) -> tuple[float, float, float]:
        """Calculate max profit, max loss, and POP."""
        current = expected_move.current_price
        em_pct = expected_move.expected_move_percent / 100

        if strategy == EarningsStrategy.STRADDLE_SELL:
            # Max profit = straddle premium
            # Max loss = unlimited (capped at estimate)
            premium = expected_move.straddle_price
            max_profit = premium * 100  # Per contract
            max_loss = (current * 0.10) * 100  # Estimate 10% max move
            pop = 0.68  # 1 standard deviation

        elif strategy == EarningsStrategy.STRANGLE_SELL:
            premium = expected_move.straddle_price * 0.6  # OTM strangle
            max_profit = premium * 100
            max_loss = (current * 0.15 - premium) * 100
            pop = 0.72

        elif strategy == EarningsStrategy.IRON_CONDOR:
            width = 5
            premium = expected_move.straddle_price * 0.3  # Net credit
            max_profit = premium * 100
            max_loss = (width - premium) * 100
            # POP based on expected move vs strikes
            pop = min(0.80, 1 - em_pct * 0.5)

        elif strategy == EarningsStrategy.IRON_BUTTERFLY:
            premium = expected_move.straddle_price * 0.8
            width = 5
            max_profit = premium * 100
            max_loss = (width - premium) * 100
            pop = 0.50

        elif strategy == EarningsStrategy.STRADDLE_BUY:
            premium = expected_move.straddle_price
            max_profit = (current * 0.20 - premium) * 100  # Estimate
            max_loss = premium * 100
            pop = 0.40

        else:
            max_profit = 250
            max_loss = 250
            pop = 0.50

        return max_profit, max_loss, pop

    def _get_entry_timing(
        self,
        earnings: EarningsEvent,
        strategy: EarningsStrategy
    ) -> str:
        """Determine optimal entry timing."""
        days = earnings.days_until

        if strategy in [EarningsStrategy.STRADDLE_SELL,
                       EarningsStrategy.STRANGLE_SELL,
                       EarningsStrategy.IRON_CONDOR]:
            if days <= 2:
                return "Enter immediately - max IV"
            elif days <= 5:
                return "Enter 1-2 days before earnings"
            else:
                return f"Wait until {days - 2} days before"

        elif strategy == EarningsStrategy.CALENDAR_SPREAD:
            return "Enter 5-7 days before earnings"

        elif strategy == EarningsStrategy.STRADDLE_BUY:
            return "Enter 1-3 weeks before earnings to capture IV rise"

        return f"Enter {days} days before earnings"

    def _generate_rationale(
        self,
        symbol: str,
        strategy: EarningsStrategy,
        expected_move: ExpectedMove,
        iv_analysis: IVCrushAnalysis,
        earnings: EarningsEvent
    ) -> str:
        """Generate trade rationale."""
        parts = []

        parts.append(f"{symbol} earnings on {earnings.earnings_date} ({earnings.earnings_time})")
        parts.append(f"Expected move: ±${expected_move.expected_move_dollars:.2f} "
                    f"({expected_move.expected_move_percent:.1f}%)")
        parts.append(f"IV Percentile: {iv_analysis.iv_percentile:.0f}%")

        if iv_analysis.is_favorable_for_selling:
            parts.append("Elevated IV suggests selling premium")
            parts.append(f"Expected IV crush: {iv_analysis.expected_iv_crush_percent:.0f}%")

        if strategy == EarningsStrategy.IRON_CONDOR:
            parts.append("Iron condor placed outside expected move range")

        return ". ".join(parts)

    def _check_warnings(
        self,
        symbol: str,
        strategy: EarningsStrategy,
        expected_move: ExpectedMove,
        iv_analysis: IVCrushAnalysis
    ) -> list[str]:
        """Check for trade warnings."""
        warnings = []

        if iv_analysis.iv_percentile < 30:
            warnings.append("IV is low - selling premium less attractive")

        if expected_move.expected_move_percent > 10:
            warnings.append("High expected move - increased risk")

        if strategy in [EarningsStrategy.STRADDLE_SELL, EarningsStrategy.STRANGLE_SELL]:
            warnings.append("Undefined risk strategy - use position sizing")

        return warnings

    def _determine_action(
        self,
        earnings: EarningsEvent,
        iv_analysis: IVCrushAnalysis,
        pop: float,
        warnings: list[str]
    ) -> TradeAction:
        """Determine trade action."""
        days = earnings.days_until

        if days < 0:
            return TradeAction.SKIP

        if days > 14:
            return TradeAction.WAIT

        if len(warnings) >= 3:
            return TradeAction.SKIP

        if pop >= 0.5 and iv_analysis.is_iv_elevated:
            return TradeAction.ENTER

        if pop >= 0.6:
            return TradeAction.ENTER

        return TradeAction.WAIT

    def _no_earnings_setup(self, symbol: str) -> EarningsTradeSetup:
        """Return setup when no earnings found."""
        return EarningsTradeSetup(
            symbol=symbol,
            strategy=EarningsStrategy.IRON_CONDOR,
            action=TradeAction.SKIP,
            earnings_event=EarningsEvent(
                symbol=symbol,
                earnings_date=date.today() + timedelta(days=90),
                earnings_time="TBD",
                quarter="Unknown"
            ),
            expected_move=self._empty_expected_move(symbol),
            iv_analysis=IVCrushAnalysis(
                symbol=symbol,
                timestamp=datetime.now(),
                current_iv=0,
                historical_avg_iv=0,
                historical_post_earnings_iv=0,
                expected_iv_crush_percent=0,
                iv_percentile=0,
                historical_crush_avg=0,
                is_iv_elevated=False,
                crush_probability=0,
                optimal_strategy=EarningsStrategy.IRON_CONDOR
            ),
            entry_timing="N/A",
            strikes={},
            expiry=date.today(),
            max_profit=0,
            max_loss=0,
            probability_of_profit=0,
            risk_reward_ratio=0,
            rationale="No upcoming earnings found",
            warnings=["No earnings data available"]
        )

    # ==========================================================================
    # HISTORICAL ANALYSIS
    # ==========================================================================

    def get_historical_patterns(
        self,
        symbol: str,
        quarters: int = EARNINGS_LOOKBACK_QUARTERS
    ) -> HistoricalEarningsPattern:
        """
        Analyze historical earnings patterns.

        Args:
            symbol: Stock symbol
            quarters: Number of quarters to analyze

        Returns:
            HistoricalEarningsPattern with analysis
        """
        # Would analyze historical earnings data
        # Return estimated patterns
        return HistoricalEarningsPattern(
            symbol=symbol,
            quarters_analyzed=quarters,
            avg_move_percent=4.5,
            avg_iv_crush_percent=35,
            beat_rate=0.75,
            move_vs_expected_ratio=0.85,
            positive_surprise_avg_move=5.0,
            negative_surprise_avg_move=-6.5,
            consistency_score=0.7
        )

    # DATA FETCHING (Databento — stub implementations)
    # TODO: Implement using SpyderC26_DatabentoClient for live options chain data
    # ==========================================================================

    @staticmethod
    def _greek_data_to_df(greek_data: list) -> pd.DataFrame:
        """
        Normalize List[GreekData] from TradierClient into a standard options chain DataFrame.

        Columns: strike, contract_type, open_interest, volume, bid, ask,
                 last_price, mid, implied_volatility, delta, gamma, theta, vega, rho, symbol.
        """
        if not greek_data:
            return pd.DataFrame()
        return pd.DataFrame([{
            'symbol': g.symbol,
            'strike': g.strike,
            'contract_type': g.option_type,
            'open_interest': g.open_interest,
            'volume': g.volume,
            'bid': g.bid,
            'ask': g.ask,
            'last_price': g.last,
            'mid': g.mid,
            'implied_volatility': g.iv,
            'delta': g.delta,
            'gamma': g.gamma,
            'theta': g.theta,
            'vega': g.vega,
            'rho': g.rho,
        } for g in greek_data])

    def _fetch_option_chain(self, symbol: str, expiry) -> pd.DataFrame:
        """Fetch option chain from market data provider."""
        if self._data_provider is None:
            logger.warning(f"_fetch_option_chain({symbol}): OptionsDataProvider not available.")
            return pd.DataFrame()
        try:
            expiry_str = expiry.strftime('%Y-%m-%d') if hasattr(expiry, 'strftime') else str(expiry)
            greek_data = self._data_provider.get_option_chain_with_greeks(symbol, expiry_str)
            df = self._greek_data_to_df(greek_data)
            if df.empty:
                logger.warning(f"Empty option chain from Tradier for {symbol} {expiry_str}")
            return df
        except Exception as e:
            logger.error(f"_fetch_option_chain({symbol}): Tradier error: {e}", exc_info=True)
            return pd.DataFrame()

    def _get_current_price(self, symbol: str) -> float:
        """Get current stock price from market data provider."""
        if self._data_provider is None:
            logger.warning(f"_get_current_price({symbol}): OptionsDataProvider not available.")
            return 0.0
        try:
            response = self._data_provider.get_quotes([symbol])
            quote = response.get('quotes', {}).get('quote', {})
            if isinstance(quote, list):
                quote = quote[0]
            return float(quote.get('last', 0.0) or 0.0)
        except Exception as e:
            logger.error(f"_get_current_price({symbol}): Tradier error: {e}", exc_info=True)
            return 0.0

    def _get_nearest_expiry(self, symbol: str) -> date:
        """Get nearest options expiration from Tradier."""
        if self._data_provider is not None:
            try:
                response = self._data_provider.get_option_expirations(symbol)
                dates = response.get('expirations', {}).get('date', [])
                if isinstance(dates, str):
                    dates = [dates]
                today = date.today()
                future = sorted(date.fromisoformat(d) for d in dates if date.fromisoformat(d) >= today)
                if future:
                    return future[0]
            except Exception as e:
                logger.warning(f"_get_nearest_expiry({symbol}): Tradier error: {e}", exc_info=True)
        today = date.today()
        days = (4 - today.weekday()) % 7 or 7
        return today + timedelta(days=days)

    def _get_expiry_after_earnings(self, earnings_date: date) -> date:
        """Get first options expiry on or after the earnings date."""
        if self._data_provider is not None:
            try:
                response = self._data_provider.get_option_expirations('SPY')
                dates = response.get('expirations', {}).get('date', [])
                if isinstance(dates, str):
                    dates = [dates]
                future = sorted(date.fromisoformat(d) for d in dates if date.fromisoformat(d) >= earnings_date)
                if future:
                    return future[0]
            except Exception as e:
                logger.warning(f"_get_expiry_after_earnings: Tradier error: {e}", exc_info=True)
        days_until_friday = (4 - earnings_date.weekday()) % 7 or 7
        return earnings_date + timedelta(days=days_until_friday)


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_earnings_handler_from_env() -> 'EarningsStrategyHandler':
    """Create EarningsStrategyHandler using the configured OptionsDataProvider."""
    data_provider = None
    if create_options_data_provider is not None:
        try:
            data_provider = create_options_data_provider()
        except Exception as e:
            logger.warning(f"Could not create OptionsDataProvider: {e}", exc_info=True)
    return EarningsStrategyHandler(data_provider=data_provider)


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    handler = EarningsStrategyHandler()

    # Test with a stock that has earnings
    symbol = "AAPL"


    # Get earnings
    earnings = handler.get_next_earnings(symbol)
    if earnings:
        pass
    else:
        pass

    # Expected move
    em = handler.calculate_expected_move(symbol)

    # IV Crush
    iv = handler.analyze_iv_crush(symbol)

    # Full trade setup
    setup = handler.get_earnings_trade(symbol)
    if setup.warnings:
        pass
