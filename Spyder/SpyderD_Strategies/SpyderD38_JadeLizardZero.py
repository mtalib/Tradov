#!/usr/bin/env python3
"""Zero/one-DTE Jade Lizard strategy with intraday-safe time handling."""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import Enum, auto
from math import erf, exp, log, pi, sqrt
from typing import Any
from zoneinfo import ZoneInfo

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU07_Constants import SPY_CONTRACT_MULTIPLIER

try:
    from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager  # noqa: F401
except ImportError:
    EventManager = Any  # type: ignore[misc,assignment]


# ==============================================================================
# CONSTANTS
# ==============================================================================
ET_ZONE = ZoneInfo("America/New_York")

ZERO_JADE_ALLOWED_TARGET_DTES = {0, 1}
ZERO_JADE_DEFAULT_TARGET_DTE = 0
ZERO_JADE_SIGNAL_EXPIRY_MINUTES = 10
ZERO_JADE_DEFAULT_STRIKE_INTERVAL = 1.0
ZERO_JADE_MIN_TIME_TO_EXPIRY_SECONDS = 60.0
ZERO_JADE_DEFAULT_MIN_CREDIT = 0.30
ZERO_JADE_DEFAULT_MIN_PROBABILITY = 0.52
ZERO_JADE_DEFAULT_PROFIT_TARGET = 0.75
ZERO_JADE_DEFAULT_STOP_LOSS_MULTIPLE = 2.0
ZERO_JADE_DEFAULT_PUT_DELTA = -0.22
ZERO_JADE_DEFAULT_CALL_DELTA = 0.12
ZERO_JADE_MIN_IV = 0.10
ZERO_JADE_MAX_IV = 0.80
ZERO_JADE_ZERO_DTE_CUTOFF_ET = "14:30"


# ==============================================================================
# ENUMS
# ==============================================================================
class ZeroJadeLizardState(Enum):
    """Lifecycle state for the short-dated Jade Lizard."""

    ANALYZING = auto()
    READY_TO_ENTER = auto()
    ENTERING = auto()
    ACTIVE = auto()
    MONITORING = auto()
    EXITING = auto()
    CLOSED = auto()
    ERROR = auto()


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ZeroJadeLeg:
    """One option leg for the short-dated Jade Lizard."""

    option_type: str
    strike: float
    position: str
    contracts: int
    premium: float
    delta: float
    expiration: datetime

    def serialize(self) -> dict[str, Any]:
        """Return a D31-compatible serialized leg payload."""
        return {
            "option_type": self.option_type,
            "strike": self.strike,
            "position": self.position,
            "contracts": self.contracts,
            "premium": self.premium,
            "delta": self.delta,
            "expiration": self.expiration.date().isoformat(),
        }


@dataclass
class ZeroJadeLizardSetup:
    """Concrete short-dated Jade Lizard setup recommendation."""

    underlying_price: float
    expiration_date: datetime
    days_to_expiry: int
    short_put: ZeroJadeLeg
    short_call: ZeroJadeLeg
    long_call: ZeroJadeLeg
    total_credit: float
    put_credit: float
    call_spread_credit: float
    call_spread_width: float
    max_profit: float
    max_loss: float
    breakeven_lower: float
    no_upside_risk: bool
    probability_profit: float
    expected_move: float
    entry_quality_score: float


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class JadeLizardZeroStrategy(BaseStrategy):
    """0DTE/1DTE Jade Lizard strategy.

    The structure sells one OTM put and a call spread on the same short-dated
    expiration. The strategy emits serialized leg metadata so D31 can route the
    structure through the paper multileg path, and it uses second-resolution
    time-to-expiry so same-day setups do not collapse to zero-time math.
    """

    def __init__(
        self,
        event_manager: EventManager = None,
        risk_profile: RiskProfile = None,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ):
        """Initialize the short-dated Jade Lizard strategy.

        Args:
            event_manager: Event bus used by the base strategy.
            risk_profile: Portfolio risk profile.
            config: Strategy configuration.
            **kwargs: Compatibility kwargs accepted by D31 when constructing.
        """
        resolved_config = dict(config or {})
        if kwargs:
            resolved_config.update(kwargs)

        super().__init__(
            name="Jade Lizard Zero Strategy",
            strategy_type="jade_lizard_zero",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=resolved_config,
        )

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.symbol = str(resolved_config.get("symbol", "SPY")).upper()
        self.target_dte = self._resolve_target_dte(resolved_config.get("target_dte"))
        self.default_contracts = max(1, int(resolved_config.get("contracts", 1) or 1))
        self.strike_interval = float(
            resolved_config.get("strike_interval", ZERO_JADE_DEFAULT_STRIKE_INTERVAL)
        )
        self.call_spread_width = float(
            resolved_config.get(
                "call_spread_width",
                10.0 if self.symbol in {"SPX", "XSP"} else 1.0,
            )
        )
        self.put_delta_target = float(
            resolved_config.get("put_delta_target", ZERO_JADE_DEFAULT_PUT_DELTA)
        )
        self.call_delta_target = float(
            resolved_config.get("call_delta_target", ZERO_JADE_DEFAULT_CALL_DELTA)
        )
        self.min_credit = float(
            resolved_config.get("min_credit", ZERO_JADE_DEFAULT_MIN_CREDIT)
        )
        self.min_probability = float(
            resolved_config.get("min_probability", ZERO_JADE_DEFAULT_MIN_PROBABILITY)
        )
        self.profit_target_fraction = float(
            resolved_config.get("profit_target_fraction", ZERO_JADE_DEFAULT_PROFIT_TARGET)
        )
        self.stop_loss_multiple = float(
            resolved_config.get(
                "stop_loss_multiple",
                ZERO_JADE_DEFAULT_STOP_LOSS_MULTIPLE,
            )
        )
        self.min_iv = float(resolved_config.get("min_iv", ZERO_JADE_MIN_IV))
        self.max_iv = float(resolved_config.get("max_iv", ZERO_JADE_MAX_IV))
        self.zero_dte_cutoff_et = str(
            resolved_config.get("zero_dte_entry_cutoff_et", ZERO_JADE_ZERO_DTE_CUTOFF_ET)
        )
        self.state = ZeroJadeLizardState.ANALYZING

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate a short-dated Jade Lizard entry signal.

        Args:
            market_data: Current market data.

        Returns:
            A list containing one entry signal when a setup qualifies.
        """
        if market_data is None or market_data.empty or "close" not in market_data.columns:
            return []

        if not self._entry_window_open():
            return []

        try:
            setup = self.build_setup(market_data)
            if setup is None:
                return []

            signal = self._create_trading_signal(setup, market_data)
            if signal is None or not self.validate_signal(signal):
                return []

            self.state = ZeroJadeLizardState.READY_TO_ENTER
            return [signal]
        except Exception as exc:
            self.state = ZeroJadeLizardState.ERROR
            self.error_handler.handle_error(exc, market_data)
            return []

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate a generated signal before dispatch.

        Args:
            signal: Trading signal under review.

        Returns:
            True when the signal carries the minimum dispatchable contract.
        """
        if signal is None or not signal.is_valid():
            return False

        metadata = signal.metadata or {}
        legs = metadata.get("legs")
        target_dte = metadata.get("target_dte")
        if not isinstance(legs, list) or len(legs) != 3:
            return False
        if target_dte not in ZERO_JADE_ALLOWED_TARGET_DTES:
            return False
        if not bool(metadata.get("no_upside_risk")):
            return False
        return float(getattr(signal, "confidence", 0.0) or 0.0) > 0.0

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Use requested contract size when present.

        Args:
            signal: Trading signal.

        Returns:
            Position size in contracts.
        """
        size = int(getattr(signal, "position_size", 0) or 0)
        return size if size > 0 else self.default_contracts

    def should_exit_position(
        self,
        position: StrategyPosition,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Apply minimal exit rules for ultra-short entries.

        Args:
            position: Current strategy position.
            market_data: Current market data.

        Returns:
            Tuple of exit decision and reason.
        """
        metadata = getattr(position, "metadata", {}) or {}
        now_et = self._now_et()

        expiration_date = self._coerce_date(metadata.get("expiration_date"))
        if expiration_date is not None and now_et.date() > expiration_date:
            return True, "expired"

        if (
            self._coerce_int(metadata.get("target_dte")) == 0
            and now_et.time() >= time(hour=15, minute=55)
        ):
            return True, "zero_dte_close_window"

        breakeven_lower = self._coerce_float(metadata.get("breakeven_lower"))
        if (
            breakeven_lower is not None
            and market_data is not None
            and not market_data.empty
            and "close" in market_data.columns
        ):
            current_price = float(market_data["close"].iloc[-1])
            if current_price <= breakeven_lower:
                return True, "breakeven_breach"

        return False, ""

    def build_setup(self, market_data: pd.DataFrame) -> ZeroJadeLizardSetup | None:
        """Construct a candidate 0DTE/1DTE Jade Lizard.

        Args:
            market_data: Current market data.

        Returns:
            A qualifying setup or ``None``.
        """
        current_price = float(market_data["close"].iloc[-1])
        current_iv = self._get_current_iv(market_data)
        if current_iv < self.min_iv or current_iv > self.max_iv:
            return None

        if not self._supports_market_bias(market_data):
            return None

        expiration_date = self._resolve_target_expiration()
        short_put_strike = self._find_strike_by_delta(
            current_price,
            self.put_delta_target,
            expiration_date,
            current_iv,
            "put",
        )
        short_call_strike = self._find_strike_by_delta(
            current_price,
            self.call_delta_target,
            expiration_date,
            current_iv,
            "call",
        )
        long_call_strike = self._ceil_to_interval(short_call_strike + self.call_spread_width)
        if long_call_strike <= short_call_strike:
            long_call_strike = short_call_strike + self.strike_interval

        short_put_snapshot = self._calculate_option_snapshot(
            short_put_strike,
            current_price,
            expiration_date,
            current_iv,
            "put",
        )
        short_call_snapshot = self._calculate_option_snapshot(
            short_call_strike,
            current_price,
            expiration_date,
            current_iv,
            "call",
        )
        long_call_snapshot = self._calculate_option_snapshot(
            long_call_strike,
            current_price,
            expiration_date,
            current_iv,
            "call",
        )

        put_credit = short_put_snapshot["premium"]
        call_spread_credit = short_call_snapshot["premium"] - long_call_snapshot["premium"]
        total_credit = put_credit + call_spread_credit
        no_upside_risk = total_credit >= (long_call_strike - short_call_strike)
        if total_credit < self.min_credit or not no_upside_risk:
            return None

        breakeven_lower = short_put_strike - total_credit
        probability_profit = self._calculate_probability_profit(
            current_price,
            breakeven_lower,
            expiration_date,
            current_iv,
        )
        if probability_profit < self.min_probability:
            return None

        max_profit = total_credit * SPY_CONTRACT_MULTIPLIER
        max_loss = max(short_put_strike - total_credit, 0.0) * SPY_CONTRACT_MULTIPLIER
        expected_move = current_price * current_iv * sqrt(self._time_to_expiry_years(expiration_date))

        short_put = ZeroJadeLeg(
            option_type="put",
            strike=short_put_strike,
            position="short",
            contracts=1,
            premium=put_credit,
            delta=short_put_snapshot["delta"],
            expiration=expiration_date,
        )
        short_call = ZeroJadeLeg(
            option_type="call",
            strike=short_call_strike,
            position="short",
            contracts=1,
            premium=short_call_snapshot["premium"],
            delta=short_call_snapshot["delta"],
            expiration=expiration_date,
        )
        long_call = ZeroJadeLeg(
            option_type="call",
            strike=long_call_strike,
            position="long",
            contracts=1,
            premium=long_call_snapshot["premium"],
            delta=long_call_snapshot["delta"],
            expiration=expiration_date,
        )

        return ZeroJadeLizardSetup(
            underlying_price=current_price,
            expiration_date=expiration_date,
            days_to_expiry=self.target_dte,
            short_put=short_put,
            short_call=short_call,
            long_call=long_call,
            total_credit=round(total_credit, 2),
            put_credit=round(put_credit, 2),
            call_spread_credit=round(call_spread_credit, 2),
            call_spread_width=round(long_call_strike - short_call_strike, 2),
            max_profit=round(max_profit, 2),
            max_loss=round(max_loss, 2),
            breakeven_lower=round(breakeven_lower, 2),
            no_upside_risk=True,
            probability_profit=probability_profit,
            expected_move=round(expected_move, 2),
            entry_quality_score=self._score_setup(
                market_data,
                total_credit,
                probability_profit,
                current_iv,
            ),
        )

    def _create_trading_signal(
        self,
        setup: ZeroJadeLizardSetup,
        market_data: pd.DataFrame,
    ) -> TradingSignal | None:
        """Convert a setup into a D31-dispatchable trading signal."""
        try:
            confidence = float(max(min(setup.entry_quality_score, 0.99), 0.05))
            if confidence >= 0.8:
                strength = SignalStrength.VERY_STRONG
            elif confidence >= 0.65:
                strength = SignalStrength.STRONG
            elif confidence >= 0.5:
                strength = SignalStrength.MODERATE
            else:
                strength = SignalStrength.WEAK

            current_price = float(market_data["close"].iloc[-1])
            now = datetime.now(UTC)
            signal = TradingSignal(
                signal_id=str(uuid.uuid4()),
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                strength=strength,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=0.0,
                take_profit=0.0,
                position_size=self.default_contracts,
                timestamp=now,
                expires_at=now + timedelta(minutes=ZERO_JADE_SIGNAL_EXPIRY_MINUTES),
                metadata={
                    "strategy": "jade_lizard_zero",
                    "strategy_id": "JadeLizardZero",
                    "strategy_type": "jade_lizard_zero",
                    "action": "sell",
                    "direction": "neutral_to_slightly_bullish",
                    "target_dte": setup.days_to_expiry,
                    "days_to_expiry": setup.days_to_expiry,
                    "dte": setup.days_to_expiry,
                    "expiration_date": setup.expiration_date.date().isoformat(),
                    "short_put_strike": setup.short_put.strike,
                    "short_call_strike": setup.short_call.strike,
                    "long_call_strike": setup.long_call.strike,
                    "total_credit": setup.total_credit,
                    "put_credit": setup.put_credit,
                    "call_spread_credit": setup.call_spread_credit,
                    "call_spread_width": setup.call_spread_width,
                    "max_profit": setup.max_profit,
                    "max_loss": setup.max_loss,
                    "breakeven_lower": setup.breakeven_lower,
                    "no_upside_risk": setup.no_upside_risk,
                    "probability_profit": setup.probability_profit,
                    "expected_move": setup.expected_move,
                    "profit_target_fraction": self.profit_target_fraction,
                    "stop_loss_multiple": self.stop_loss_multiple,
                    "legs": [
                        setup.short_put.serialize(),
                        setup.short_call.serialize(),
                        setup.long_call.serialize(),
                    ],
                },
            )
            self.state = ZeroJadeLizardState.ENTERING
            return signal
        except Exception as exc:
            self.logger.error("D38 signal creation failed: %s", exc, exc_info=True)
            self.state = ZeroJadeLizardState.ERROR
            return None

    def _supports_market_bias(self, market_data: pd.DataFrame) -> bool:
        """Reject strongly bearish tapes for the short-put-heavy structure."""
        close_prices = market_data["close"].astype(float)
        if len(close_prices) < 3:
            return True

        lookback = min(len(close_prices) - 1, 10)
        baseline = float(close_prices.iloc[-lookback - 1])
        current = float(close_prices.iloc[-1])
        if baseline <= 0:
            return True

        recent_return = (current - baseline) / baseline
        return recent_return > -0.01

    def _entry_window_open(self) -> bool:
        """Fail closed on weekends and after the 0DTE new-risk cutoff."""
        now_et = self._now_et()
        if now_et.weekday() >= 5:
            return False

        if self.target_dte == 0:
            try:
                cutoff = time.fromisoformat(self.zero_dte_cutoff_et)
            except ValueError:
                cutoff = time(hour=14, minute=30)
            if now_et.time() >= cutoff:
                return False

        return True

    def _resolve_target_dte(self, raw_target_dte: Any) -> int:
        """Clamp the configured target DTE to the supported 0/1 range."""
        try:
            target_dte = int(raw_target_dte)
        except (TypeError, ValueError):
            return ZERO_JADE_DEFAULT_TARGET_DTE

        if target_dte in ZERO_JADE_ALLOWED_TARGET_DTES:
            return target_dte
        return 0 if target_dte <= 0 else 1

    def _resolve_target_expiration(self) -> datetime:
        """Return the expiration timestamp at the target market close."""
        now_et = self._now_et()
        target_date = self._shift_trading_days(now_et.date(), self.target_dte)
        expiration_et = datetime.combine(
            target_date,
            time(hour=16, minute=0),
            tzinfo=ET_ZONE,
        )
        return expiration_et.astimezone(UTC)

    def _shift_trading_days(self, anchor: date, offset: int) -> date:
        """Advance a date by trading days, skipping weekends."""
        candidate = anchor
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)

        remaining = max(offset, 0)
        while remaining > 0:
            candidate += timedelta(days=1)
            if candidate.weekday() < 5:
                remaining -= 1
        return candidate

    def _get_current_iv(self, market_data: pd.DataFrame) -> float:
        """Return implied volatility or a realized-vol fallback."""
        if "iv" in market_data.columns:
            iv_value = float(market_data["iv"].iloc[-1])
            if iv_value > 0:
                return iv_value

        returns = market_data["close"].astype(float).pct_change().dropna()
        if returns.empty:
            return 0.20
        realized_vol = float(returns.std() * sqrt(252.0))
        return max(realized_vol, 0.10)

    def _find_strike_by_delta(
        self,
        spot: float,
        target_delta: float,
        expiration_date: datetime,
        iv: float,
        option_type: str,
    ) -> float:
        """Select the nearest strike for a target delta using a local scan."""
        window = max(spot * 0.08, self.call_spread_width * 8.0, self.strike_interval * 12.0)
        start = self._floor_to_interval(max(self.strike_interval, spot - window))
        end = self._ceil_to_interval(spot + window)

        best_strike = self._round_to_interval(spot)
        best_error = float("inf")
        for strike in np.arange(start, end + self.strike_interval, self.strike_interval):
            snapshot = self._calculate_option_snapshot(
                float(strike),
                spot,
                expiration_date,
                iv,
                option_type,
            )
            delta = float(snapshot["delta"])
            error = abs(delta - target_delta)
            if error < best_error:
                best_error = error
                best_strike = float(strike)

        if option_type == "call" and best_strike <= spot:
            return self._ceil_to_interval(spot + self.strike_interval)
        if option_type == "put" and best_strike >= spot:
            return self._floor_to_interval(max(self.strike_interval, spot - self.strike_interval))
        return round(best_strike, 2)

    def _calculate_option_snapshot(
        self,
        strike: float,
        spot: float,
        expiration_date: datetime,
        iv: float,
        option_type: str,
    ) -> dict[str, float]:
        """Estimate premium and delta with floored time-to-expiry."""
        time_to_expiry = self._time_to_expiry_years(expiration_date)
        sigma = max(iv, 0.05)
        strike = max(strike, self.strike_interval)

        sigma_root_t = sigma * sqrt(time_to_expiry)
        d1 = (log(max(spot, 0.01) / strike) + (0.5 * sigma * sigma) * time_to_expiry) / sigma_root_t
        d2 = d1 - sigma_root_t

        if option_type == "call":
            premium = spot * self._normal_cdf(d1) - strike * self._normal_cdf(d2)
            delta = self._normal_cdf(d1)
        else:
            premium = strike * self._normal_cdf(-d2) - spot * self._normal_cdf(-d1)
            delta = self._normal_cdf(d1) - 1.0

        return {
            "premium": round(max(premium, 0.01), 2),
            "delta": delta,
        }

    def _calculate_probability_profit(
        self,
        spot: float,
        breakeven_lower: float,
        expiration_date: datetime,
        iv: float,
    ) -> float:
        """Estimate the probability price remains above the downside breakeven."""
        expected_move = max(
            spot * max(iv, 0.05) * sqrt(self._time_to_expiry_years(expiration_date)),
            self.strike_interval,
        )
        z_score = (breakeven_lower - spot) / expected_move
        probability = 1.0 - self._normal_cdf(z_score)
        return float(max(0.05, min(probability, 0.98)))

    def _score_setup(
        self,
        market_data: pd.DataFrame,
        total_credit: float,
        probability_profit: float,
        iv: float,
    ) -> float:
        """Produce a bounded confidence score for signal strength mapping."""
        close_prices = market_data["close"].astype(float)
        baseline = float(close_prices.iloc[max(len(close_prices) - min(len(close_prices), 10), 0)])
        current = float(close_prices.iloc[-1])
        recent_return = ((current - baseline) / baseline) if baseline > 0 else 0.0
        trend_component = max(0.0, 1.0 - min(abs(recent_return) / 0.02, 1.0))
        iv_midpoint = (self.min_iv + self.max_iv) / 2.0
        iv_component = max(0.0, 1.0 - min(abs(iv - iv_midpoint) / max(iv_midpoint, 0.01), 1.0))
        credit_component = min(total_credit / max(self.call_spread_width, 0.01), 1.5) / 1.5
        score = (
            probability_profit * 0.45
            + credit_component * 0.30
            + iv_component * 0.15
            + trend_component * 0.10
        )
        return float(max(0.05, min(score, 0.99)))

    def _time_to_expiry_years(self, expiration_date: datetime) -> float:
        """Return a strictly positive year fraction to expiry."""
        now = datetime.now(UTC)
        seconds = max(
            (expiration_date - now).total_seconds(),
            ZERO_JADE_MIN_TIME_TO_EXPIRY_SECONDS,
        )
        return seconds / (365.0 * 24.0 * 60.0 * 60.0)

    @staticmethod
    def _normal_cdf(value: float) -> float:
        """Return the standard normal CDF."""
        return 0.5 * (1.0 + erf(value / sqrt(2.0)))

    @staticmethod
    def _normal_pdf(value: float) -> float:
        """Return the standard normal PDF."""
        return exp(-0.5 * value * value) / sqrt(2.0 * pi)

    @staticmethod
    def _now_et() -> datetime:
        """Return the current time in US/Eastern."""
        return datetime.now(UTC).astimezone(ET_ZONE)

    def _round_to_interval(self, value: float) -> float:
        """Round a strike to the configured strike interval."""
        return round(round(value / self.strike_interval) * self.strike_interval, 2)

    def _floor_to_interval(self, value: float) -> float:
        """Floor a strike to the configured strike interval."""
        return round(np.floor(value / self.strike_interval) * self.strike_interval, 2)

    def _ceil_to_interval(self, value: float) -> float:
        """Ceil a strike to the configured strike interval."""
        return round(np.ceil(value / self.strike_interval) * self.strike_interval, 2)

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        """Return a float when coercion succeeds."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        """Return an int when coercion succeeds."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_date(value: Any) -> date | None:
        """Parse an ISO date string when present."""
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str) and value:
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None
