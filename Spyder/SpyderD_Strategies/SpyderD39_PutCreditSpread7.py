#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD39_PutCreditSpread7.py
Purpose: Seven-DTE put credit spread strategy with weekly timing and hybrid exits

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-05-29 Time: 00:00:00

Module Description:
        Implements a research-driven seven-DTE bull put credit spread adapted for
        SPY options from an SPX weekly premium-selling template. The strategy keeps
        the execution contract paper safe by emitting explicit two-leg metadata for
        D31 paper routing.

    Strategy refinements relative to the source note:
        - Adapts the spread ladder and sizing defaults to SPY while preserving the
            source strategy's defined-risk posture.
    - Keeps the documented weekly Friday entry cadence, with optional Thursday
      holiday handling for weeks where Friday is closed.
        - Defaults entries to the near-close 15:45 ET window so the setup uses the
            day's settled trend and volatility context.
        - Defaults to a conservative pre-close expiration exit to avoid carrying
            ETF option assignment and pin-risk exposure into the close.
        - Fails closed unless an option chain is available for the target expiry,
            so the strategy cannot synthesize a spread from heuristics alone.
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
import math
from typing import Any
import uuid
from zoneinfo import ZoneInfo

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from pandas.tseries.holiday import GoodFriday, USFederalHolidayCalendar

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy,
    EventManager,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
)
from Spyder.SpyderU_Utilities.SpyderU07_Constants import (
    SPX_CONTRACT_MULTIPLIER,
    SPY_CONTRACT_MULTIPLIER,
)


# ==============================================================================
# CONSTANTS
# ==============================================================================
ET_ZONE = ZoneInfo("America/New_York")

PUT_CREDIT_7_ALLOWED_WIDTHS = (25.0, 40.0, 50.0, 100.0, 200.0)
PUT_CREDIT_7_DEFAULT_TARGET_DTE = 7
PUT_CREDIT_7_DEFAULT_SHORT_DELTA = 0.10
PUT_CREDIT_7_DEFAULT_ENTRY_TIME = time(hour=15, minute=45)
PUT_CREDIT_7_DEFAULT_SIGNAL_EXPIRY_SECONDS = 600
PUT_CREDIT_7_DEFAULT_EXPIRATION_EXIT_TIME = time(hour=15, minute=55)
PUT_CREDIT_7_DEFAULT_NARROW_OTM_THRESHOLD = 0.02
PUT_CREDIT_7_DEFAULT_WIDE_OTM_THRESHOLD = 0.005
PUT_CREDIT_7_DEFAULT_TREND_BUFFER = 0.005
PUT_CREDIT_7_DEFAULT_SYMBOL = "SPY"
PUT_CREDIT_7_MINI_ALLOWED_WIDTHS = (2.5, 4.0, 5.0, 10.0, 20.0)
PUT_CREDIT_7_INDEX_ALLOWED_WIDTHS = (25.0, 40.0, 50.0, 100.0, 200.0)
PUT_CREDIT_7_DEFAULT_MINI_SPREAD_WIDTH = 5.0
PUT_CREDIT_7_DEFAULT_INDEX_SPREAD_WIDTH = 50.0
PUT_CREDIT_7_DEFAULT_MINI_MAX_CONTRACTS = 80
PUT_CREDIT_7_DEFAULT_INDEX_MAX_CONTRACTS = 8
PUT_CREDIT_7_DEFAULT_MINI_NARROW_WIDTH_CUTOFF = 4.0
PUT_CREDIT_7_DEFAULT_INDEX_NARROW_WIDTH_CUTOFF = 40.0
PUT_CREDIT_7_DEFAULT_PROFIT_TARGET_ENABLED = False
PUT_CREDIT_7_DEFAULT_PROFIT_TARGET_FRACTION = 0.50
PUT_CREDIT_7_DEFAULT_STOP_LOSS_BAR_MINUTES = 5
PUT_CREDIT_7_DEFAULT_BID_ASK_SPREAD_RATIO = 0.10
PUT_CREDIT_7_DEFAULT_MIN_OPEN_INTEREST = 500
PUT_CREDIT_7_DEFAULT_MIN_DAILY_VOLUME = 100
PUT_CREDIT_7_DEFAULT_EXPIRY_FLEX_DAYS = 2


def _parse_put_credit_spread_7_time(candidate: Any) -> time:
    """Parse an ET time value from a config field or helper input."""
    if isinstance(candidate, time):
        return candidate.replace(tzinfo=None)
    if isinstance(candidate, str):
        parts = candidate.strip().split(":")
        if len(parts) >= 2:
            try:
                hour = int(parts[0])
                minute = int(parts[1])
                second = int(parts[2]) if len(parts) > 2 else 0
                return time(hour=hour, minute=minute, second=second)
            except ValueError:
                pass
    return PUT_CREDIT_7_DEFAULT_ENTRY_TIME


def _put_credit_spread_7_next_day_market_closed(current_date: date) -> bool:
    """Return True when the next calendar day is a market holiday or closure."""
    next_day = current_date + timedelta(days=1)
    if next_day.weekday() >= 5:
        return True

    holidays = set(
        USFederalHolidayCalendar().holidays(
            start=current_date,
            end=next_day + timedelta(days=365),
        ).date
    )
    if next_day in holidays:
        return True

    good_fridays = set(
        pd.DatetimeIndex(
            GoodFriday.dates(current_date, next_day + timedelta(days=365))
        ).date
    )
    return next_day in good_fridays


def resolve_put_credit_spread_7_entry_day(
    now_et: datetime,
    allow_preholiday_thursday: bool = True,
) -> str | None:
    """Return the eligible entry-day label for the weekly seven-DTE strategy."""
    weekday = now_et.weekday()
    if weekday == 4:
        return "friday"
    if (
        weekday == 3
        and allow_preholiday_thursday
        and _put_credit_spread_7_next_day_market_closed(now_et.date())
    ):
        return "thursday_preholiday"
    return None


def is_put_credit_spread_7_entry_day(
    now_et: datetime,
    allow_preholiday_thursday: bool = True,
) -> bool:
    """Return True when the weekly entry schedule is open."""
    return resolve_put_credit_spread_7_entry_day(
        now_et,
        allow_preholiday_thursday=allow_preholiday_thursday,
    ) is not None


def resolve_put_credit_spread_7_entry_window(
    now_et: datetime,
    allow_preholiday_thursday: bool = True,
    entry_time_et: Any = PUT_CREDIT_7_DEFAULT_ENTRY_TIME,
) -> str | None:
    """Return the eligible entry-day label once the near-close entry window is open."""
    entry_day = resolve_put_credit_spread_7_entry_day(
        now_et,
        allow_preholiday_thursday=allow_preholiday_thursday,
    )
    if entry_day is None:
        return None

    current_time = now_et.time().replace(tzinfo=None)
    entry_time = _parse_put_credit_spread_7_time(entry_time_et)
    if (current_time.hour, current_time.minute) != (entry_time.hour, entry_time.minute):
        return None
    return entry_day


def is_put_credit_spread_7_entry_window_open(
    now_et: datetime,
    allow_preholiday_thursday: bool = True,
    entry_time_et: Any = PUT_CREDIT_7_DEFAULT_ENTRY_TIME,
) -> bool:
    """Return True when the near-close weekly entry window is open."""
    return resolve_put_credit_spread_7_entry_window(
        now_et,
        allow_preholiday_thursday=allow_preholiday_thursday,
        entry_time_et=entry_time_et,
    ) is not None


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PutCreditSpread7Leg:
    """One option leg for the seven-DTE put credit spread."""

    strike: float
    position: str
    premium: float
    delta: float
    expiration: datetime

    def serialize(self) -> dict[str, Any]:
        """Return a D31-compatible serialized leg payload."""
        return {
            "option_type": "put",
            "strike": self.strike,
            "position": self.position,
            "premium": round(self.premium, 2),
            "delta": self.delta,
            "expiration_date": self.expiration.date().isoformat(),
        }


@dataclass
class PutCreditSpread7Setup:
    """Concrete setup recommendation for the weekly seven-DTE spread."""

    symbol: str
    underlying_price: float
    short_put: PutCreditSpread7Leg
    long_put: PutCreditSpread7Leg
    spread_width: float
    expiration_date: datetime
    days_to_expiry: int
    total_credit: float
    max_profit: float
    max_loss: float
    breakeven_lower: float
    probability_profit: float
    entry_day: str
    credit_model: str
    selection_method: str
    otm_pct: float
    sma_200: float
    trend_distance_pct: float


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class PutCreditSpread7Strategy(BaseStrategy):
    """Weekly seven-DTE bull put credit spread.

    The strategy sells a defined-risk put vertical once per week when the
    underlying is above its 200-day moving average and the structure offers a
    high-probability short strike. It emits explicit leg metadata so paper-mode
    routing can place both option legs instead of collapsing to a synthetic
    equity order.

    Args:
        event_manager: Event bus used by the base strategy.
        risk_profile: Portfolio risk profile for sizing.
        config: Strategy configuration. Common keys include `symbol`,
            `spread_width`, `max_trade_capital`, `total_capital`,
            `allow_preholiday_thursday_entry`, `entry_time_et`, `target_dte`,
            `clock`, and `option_chain`. Defaults are tuned for SPY unless the
            caller explicitly supplies a different underlying.
        name: Optional runtime name override.
        **kwargs: Compatibility kwargs merged into the config.
    """

    STRATEGY_NAME = "PutCreditSpread7"

    def __init__(
        self,
        event_manager: EventManager = None,
        risk_profile: RiskProfile = None,
        config: dict[str, Any] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        resolved_config = dict(config or {})
        if kwargs:
            resolved_config.update(kwargs)

        super().__init__(
            name=name or self.STRATEGY_NAME,
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=resolved_config,
            strategy_type="bull_put_credit_spread",
        )

        self.symbol = str(resolved_config.get("symbol", PUT_CREDIT_7_DEFAULT_SYMBOL)).upper()
        self.proxy_symbol = str(resolved_config.get("trend_proxy_symbol", self.symbol)).upper()
        self.target_dte = max(int(resolved_config.get("target_dte", PUT_CREDIT_7_DEFAULT_TARGET_DTE)), 1)
        self.short_delta_target = abs(
            float(resolved_config.get("short_put_delta", PUT_CREDIT_7_DEFAULT_SHORT_DELTA))
        )
        self.spread_width = self._resolve_spread_width(
            resolved_config.get("spread_width", self._default_spread_width())
        )
        self.total_capital = float(
            resolved_config.get(
                "total_capital",
                getattr(risk_profile, "account_size", 50000.0) or 50000.0,
            )
        )
        self.max_trade_capital = float(resolved_config.get("max_trade_capital", 20000.0))
        self.signal_expiry_seconds = int(
            resolved_config.get("signal_expiry_seconds", PUT_CREDIT_7_DEFAULT_SIGNAL_EXPIRY_SECONDS)
        )
        self.require_sma_200 = bool(resolved_config.get("require_sma_200", True))
        self.allow_preholiday_thursday_entry = bool(
            resolved_config.get("allow_preholiday_thursday_entry", True)
        )
        self.entry_time = _parse_put_credit_spread_7_time(
            resolved_config.get("entry_time_et", PUT_CREDIT_7_DEFAULT_ENTRY_TIME)
        )
        self.narrow_otm_threshold = max(
            float(
                resolved_config.get(
                    "narrow_otm_threshold",
                    PUT_CREDIT_7_DEFAULT_NARROW_OTM_THRESHOLD,
                )
            ),
            0.0,
        )
        self.wide_otm_threshold = max(
            float(
                resolved_config.get(
                    "wide_otm_threshold",
                    PUT_CREDIT_7_DEFAULT_WIDE_OTM_THRESHOLD,
                )
            ),
            0.0,
        )
        self.trend_buffer_pct = max(
            float(resolved_config.get("trend_buffer_pct", PUT_CREDIT_7_DEFAULT_TREND_BUFFER)),
            0.0,
        )
        self.strike_increment = max(
            float(
                resolved_config.get(
                    "strike_increment",
                    5.0 if self.symbol in {"SPX", "XSP"} else 1.0,
                )
            ),
            0.5,
        )
        self.expiration_exit_time = self._parse_exit_time(
            resolved_config.get("expiration_exit_time_et", PUT_CREDIT_7_DEFAULT_EXPIRATION_EXIT_TIME)
        )
        self.max_contracts = max(
            int(resolved_config.get("max_contracts", self._default_max_contracts())),
            1,
        )
        self.enable_profit_target = bool(
            resolved_config.get(
                "enable_profit_target",
                PUT_CREDIT_7_DEFAULT_PROFIT_TARGET_ENABLED,
            )
        )
        self.profit_target_fraction = min(
            max(
                float(
                    resolved_config.get(
                        "profit_target_fraction",
                        PUT_CREDIT_7_DEFAULT_PROFIT_TARGET_FRACTION,
                    )
                ),
                0.0,
            ),
            1.0,
        )
        self.stop_loss_bar_minutes = max(
            int(
                resolved_config.get(
                    "stop_loss_bar_minutes",
                    PUT_CREDIT_7_DEFAULT_STOP_LOSS_BAR_MINUTES,
                )
            ),
            1,
        )
        self.max_bid_ask_spread_ratio = max(
            float(
                resolved_config.get(
                    "max_bid_ask_spread_ratio",
                    PUT_CREDIT_7_DEFAULT_BID_ASK_SPREAD_RATIO,
                )
            ),
            0.0,
        )
        self.min_open_interest = max(
            int(
                resolved_config.get(
                    "min_open_interest",
                    PUT_CREDIT_7_DEFAULT_MIN_OPEN_INTEREST,
                )
            ),
            0,
        )
        self.min_daily_volume = max(
            int(
                resolved_config.get(
                    "min_daily_volume",
                    PUT_CREDIT_7_DEFAULT_MIN_DAILY_VOLUME,
                )
            ),
            0,
        )
        self.expiry_flex_days = max(
            int(
                resolved_config.get(
                    "expiry_flex_days",
                    PUT_CREDIT_7_DEFAULT_EXPIRY_FLEX_DAYS,
                )
            ),
            0,
        )
        self._clock = resolved_config.get("clock")

        self.logger.info(
            "PutCreditSpread7Strategy initialized: symbol=%s width=%.1f target_dte=%d entry_time=%s",
            self.symbol,
            self.spread_width,
            self.target_dte,
            self.entry_time.strftime("%H:%M"),
        )

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate a weekly seven-DTE bull put credit spread entry signal."""
        try:
            if market_data is None or market_data.empty:
                return []

            closes = self._extract_series(market_data, ("close", "Close", self.symbol, self.proxy_symbol, "price", "last"))
            if len(closes) < 3:
                return []

            now_et = self._now_et(market_data)
            entry_day = self._resolve_entry_day(now_et)
            if entry_day is None:
                return []

            spot = float(closes.iloc[-1])
            if spot <= 0.0:
                return []

            sma_200 = self._resolve_sma_200(market_data, closes)
            if self.require_sma_200 and sma_200 is None:
                return []
            if sma_200 is not None and spot < sma_200 * (1.0 + self.trend_buffer_pct):
                return []

            setup = self.build_setup(market_data, spot=spot, now_et=now_et, entry_day=entry_day, sma_200=sma_200 or spot)
            if setup is None:
                return []

            signal = self._create_signal(setup, now_et)
            if signal is None or not self.validate_signal(signal):
                return []

            return [signal]

        except Exception as exc:
            self.logger.error("PutCreditSpread7Strategy.generate_signals error: %s", exc, exc_info=True)
            return []

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate the generated short-premium spread signal."""
        if signal is None or not signal.is_valid():
            return False
        if signal.signal_type != SignalType.SELL:
            return False
        if signal.entry_price <= 0.0:
            return False

        metadata = signal.metadata or {}
        if metadata.get("strategy_id") != self.STRATEGY_NAME:
            return False
        if metadata.get("strategy_type") != "bull_put_credit_spread":
            return False

        short_put = self._coerce_float(metadata.get("short_put_strike"))
        long_put = self._coerce_float(metadata.get("long_put_strike"))
        spread_width = self._coerce_float(metadata.get("spread_width"))
        max_loss = self._coerce_float(metadata.get("max_loss"))
        legs = metadata.get("legs")

        if short_put is None or long_put is None or spread_width is None or max_loss is None:
            return False
        if not (short_put > long_put and spread_width > 0.0 and max_loss > 0.0):
            return False
        if not isinstance(legs, list) or len(legs) != 2:
            return False

        expiration_date = self._coerce_date(metadata.get("expiration_date"))
        if expiration_date is None:
            return False

        return int(signal.position_size) >= 1 and float(signal.confidence) >= 0.50

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Return the precomputed conservative contract size for the spread."""
        configured_size = int(getattr(signal, "position_size", 0) or 0)
        if configured_size > 0:
            return configured_size

        metadata = signal.metadata or {}
        spread_width = self._coerce_float(metadata.get("spread_width")) or self.spread_width
        return self._calculate_contracts(spread_width)

    def should_exit_position(
        self,
        position: StrategyPosition,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Apply strict stop, profit-target, and hybrid exit precedence."""
        try:
            if market_data is None or market_data.empty:
                return False, ""

            closes = self._extract_series(market_data, ("close", "Close", self.symbol, self.proxy_symbol, "price", "last"))
            if closes.empty:
                return False, ""

            spot = float(closes.iloc[-1])
            metadata = getattr(position, "metadata", {}) or {}
            short_put = self._coerce_float(metadata.get("short_put_strike"))
            if short_put is None:
                return False, ""

            if spot < short_put:
                return True, "stop_loss_bar_close"

            total_credit = self._coerce_float(metadata.get("total_credit"))
            if self.enable_profit_target and total_credit is not None and total_credit > 0.0:
                spread_value = self._resolve_current_spread_value(market_data, metadata)
                target_close_value = round(total_credit * (1.0 - self.profit_target_fraction), 4)
                if spread_value is not None and spread_value <= target_close_value:
                    return True, "profit_target"

            now_et = self._now_et(market_data)
            expiration_date = self._coerce_date(metadata.get("expiration_date"))
            if expiration_date is None:
                return False, ""

            if now_et.date() > expiration_date:
                return True, "expired"

            if now_et.date() == expiration_date and now_et.time() >= self.expiration_exit_time:
                return True, "expiration_close"

            days_left = (expiration_date - now_et.date()).days
            if days_left != 1:
                return False, ""
            if now_et.time() < self.expiration_exit_time:
                return False, ""

            otm_threshold = self._hybrid_otm_threshold(self._coerce_float(metadata.get("spread_width")) or self.spread_width)
            otm_pct = (spot - short_put) / short_put if short_put > 0.0 else 0.0
            if otm_pct < otm_threshold:
                return True, "hybrid_one_dte_exit"

            return False, ""

        except Exception as exc:
            self.logger.error("PutCreditSpread7Strategy.should_exit_position error: %s", exc, exc_info=True)
            return False, ""

    def build_setup(
        self,
        market_data: pd.DataFrame,
        *,
        spot: float,
        now_et: datetime,
        entry_day: str,
        sma_200: float,
    ) -> PutCreditSpread7Setup | None:
        """Construct the weekly spread from an option chain, otherwise fail closed."""
        return self._build_setup_from_option_chain(
            market_data,
            spot=spot,
            target_expiration_date=now_et.date() + timedelta(days=self.target_dte),
            entry_day=entry_day,
            sma_200=sma_200,
        )

    def _create_signal(
        self,
        setup: PutCreditSpread7Setup,
        now_et: datetime,
    ) -> TradingSignal | None:
        trend_bonus = min(max(setup.trend_distance_pct, 0.0), 0.05) * 3.0
        otm_bonus = min(max(setup.otm_pct, 0.0), 0.10) * 1.5
        confidence = min(0.94, max(0.58, 0.60 + trend_bonus + otm_bonus + (setup.probability_profit - 0.5) * 0.5))
        if confidence >= 0.84:
            strength = SignalStrength.VERY_STRONG
        elif confidence >= 0.72:
            strength = SignalStrength.STRONG
        else:
            strength = SignalStrength.MODERATE

        now_utc = now_et.astimezone(UTC)
        signal = TradingSignal(
            signal_id=f"PCS7_{uuid.uuid4().hex[:10]}",
            signal_type=SignalType.SELL,
            symbol=setup.symbol,
            strength=strength,
            confidence=confidence,
            entry_price=setup.total_credit,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=self._calculate_contracts(setup.spread_width),
            timestamp=now_utc,
            expires_at=now_utc + timedelta(seconds=self.signal_expiry_seconds),
            metadata={
                "strategy": "put_credit_spread_7",
                "strategy_name": self.STRATEGY_NAME,
                "strategy_id": self.STRATEGY_NAME,
                "strategy_type": "bull_put_credit_spread",
                "action": "sell",
                "direction": "bullish",
                "structure": "put_vertical",
                "entry_schedule": "weekly_friday",
                "entry_day": setup.entry_day,
                "entry_time_et": self.entry_time.strftime("%H:%M:%S"),
                "target_dte": setup.days_to_expiry,
                "days_to_expiry": setup.days_to_expiry,
                "dte": setup.days_to_expiry,
                "expiration_date": setup.expiration_date.date().isoformat(),
                "underlying_spot": setup.underlying_price,
                "sma_200": setup.sma_200,
                "trend_distance_pct": setup.trend_distance_pct,
                "short_put_strike": setup.short_put.strike,
                "long_put_strike": setup.long_put.strike,
                "short_put_delta": abs(setup.short_put.delta),
                "spread_width": setup.spread_width,
                "total_credit": setup.total_credit,
                "expected_credit": setup.total_credit,
                "max_profit": setup.max_profit,
                "max_loss": setup.max_loss,
                "breakeven_lower": setup.breakeven_lower,
                "probability_profit": setup.probability_profit,
                "otm_pct": setup.otm_pct,
                "narrow_otm_threshold": self.narrow_otm_threshold,
                "wide_otm_threshold": self.wide_otm_threshold,
                "credit_model": setup.credit_model,
                "selection_method": setup.selection_method,
                "configured_target_dte": self.target_dte,
                "profit_target_enabled": self.enable_profit_target,
                "profit_target_fraction": self.profit_target_fraction,
                "profit_target_price": round(
                    setup.total_credit * (1.0 - self.profit_target_fraction),
                    2,
                ),
                "stop_loss_bar_minutes": self.stop_loss_bar_minutes,
                "expiration_exit_time_et": self.expiration_exit_time.strftime("%H:%M:%S"),
                "legs": [
                    setup.short_put.serialize(),
                    setup.long_put.serialize(),
                ],
            },
        )
        return signal

    def _build_setup_from_option_chain(
        self,
        market_data: pd.DataFrame,
        *,
        spot: float,
        target_expiration_date: date,
        entry_day: str,
        sma_200: float,
    ) -> PutCreditSpread7Setup | None:
        option_chain = self._resolve_option_chain(market_data)
        if option_chain is None or option_chain.empty:
            return None

        chain = option_chain.copy()
        type_series = chain.get("option_type")
        if type_series is None:
            type_series = chain.get("right")
        if type_series is None:
            return None
        chain = chain.assign(_option_type=type_series.astype(str).str.lower())
        chain = chain.loc[chain["_option_type"].eq("put")].copy()
        if chain.empty:
            return None

        chain["_strike"] = self._numeric_column(chain, ("strike",))
        chain["_delta"] = self._numeric_column(chain, ("delta",))
        chain["_bid"] = self._numeric_column(chain, ("bid", "bid_price", "bidPrice"))
        chain["_ask"] = self._numeric_column(chain, ("ask", "ask_price", "askPrice"))
        chain["_open_interest"] = self._numeric_column(
            chain,
            ("open_interest", "openInterest", "oi"),
        )
        chain["_volume"] = self._numeric_column(
            chain,
            ("volume", "daily_volume", "dailyVolume", "total_volume"),
        )
        chain["_premium"] = chain.apply(self._mid_price_from_row, axis=1)
        chain = chain.dropna(subset=["_strike", "_premium"])
        if chain.empty:
            return None

        expiry_series = self._expiry_column(chain)
        if expiry_series is not None:
            chain = chain.assign(_expiry=expiry_series)
            selected_expiration_date = self._select_expiration_date(
                chain["_expiry"],
                target_expiration_date,
            )
            if selected_expiration_date is None:
                return None
            chain = chain.loc[chain["_expiry"].dt.date.eq(selected_expiration_date)]
        else:
            selected_expiration_date = target_expiration_date
            chain = chain.assign(
                _expiry=datetime.combine(selected_expiration_date, datetime.min.time(), tzinfo=UTC)
            )

        chain = chain.loc[chain["_strike"] < spot].copy()
        if chain.empty:
            return None

        short_row, selection_method = self._select_short_leg(chain, spot, market_data)
        if short_row is None or selection_method is None:
            return None

        short_strike = float(short_row["_strike"])
        target_long_strike = short_strike - self.spread_width
        long_candidates = chain.loc[chain["_strike"] <= target_long_strike + 1e-9].copy()
        if long_candidates.empty:
            return None
        long_candidates["_distance"] = (long_candidates["_strike"] - target_long_strike).abs()
        long_row = long_candidates.sort_values(by=["_distance", "_strike"], ascending=[True, False]).iloc[0]

        long_strike = float(long_row["_strike"])
        realized_width = round(short_strike - long_strike, 2)
        if realized_width <= 0.0:
            return None

        short_premium = round(max(float(short_row["_premium"]), 0.01), 2)
        long_premium = round(max(float(long_row["_premium"]), 0.01), 2)
        total_credit = round(max(short_premium - long_premium, 0.01), 2)
        max_loss = round(
            realized_width * self._contract_multiplier() - total_credit * self._contract_multiplier(),
            2,
        )
        if max_loss <= 0.0:
            return None

        selected_expiration_dt = datetime.combine(
            selected_expiration_date,
            datetime.min.time(),
            tzinfo=UTC,
        )
        otm_pct = max((spot - short_strike) / short_strike, 0.0)
        trend_distance_pct = max((spot - sma_200) / sma_200, 0.0) if sma_200 > 0 else 0.0
        short_delta = self._coerce_float(short_row.get("_delta")) or -self.short_delta_target
        long_delta = self._coerce_float(long_row.get("_delta")) or -(self.short_delta_target / 2)
        probability_profit = min(0.96, max(0.55, 1.0 - abs(short_delta)))

        return PutCreditSpread7Setup(
            symbol=self.symbol,
            underlying_price=spot,
            short_put=PutCreditSpread7Leg(
                strike=short_strike,
                position="short",
                premium=short_premium,
                delta=-abs(short_delta),
                expiration=selected_expiration_dt,
            ),
            long_put=PutCreditSpread7Leg(
                strike=long_strike,
                position="long",
                premium=long_premium,
                delta=-abs(long_delta),
                expiration=selected_expiration_dt,
            ),
            spread_width=realized_width,
            expiration_date=selected_expiration_dt,
            days_to_expiry=max((selected_expiration_date - self._now_et(market_data).date()).days, 1),
            total_credit=total_credit,
            max_profit=round(total_credit * self._contract_multiplier(), 2),
            max_loss=max_loss,
            breakeven_lower=round(short_strike - total_credit, 2),
            probability_profit=probability_profit,
            entry_day=entry_day,
            credit_model="option_chain",
            selection_method=selection_method,
            otm_pct=otm_pct,
            sma_200=sma_200,
            trend_distance_pct=trend_distance_pct,
        )

    def _resolve_option_chain(self, market_data: pd.DataFrame) -> pd.DataFrame | None:
        option_chain = self.config.get("option_chain")
        if option_chain is None and hasattr(market_data, "attrs"):
            option_chain = market_data.attrs.get("option_chain")

        if option_chain is None:
            return None
        if isinstance(option_chain, pd.DataFrame):
            return option_chain
        if isinstance(option_chain, list):
            try:
                return pd.DataFrame(option_chain)
            except Exception:
                return None
        return None

    def _resolve_entry_day(self, now_et: datetime) -> str | None:
        return resolve_put_credit_spread_7_entry_window(
            now_et,
            allow_preholiday_thursday=self.allow_preholiday_thursday_entry,
            entry_time_et=self.entry_time,
        )

    def _resolve_sma_200(self, market_data: pd.DataFrame, closes: pd.Series) -> float | None:
        for key in ("sma_200", "SMA_200", "sma200", "ma_200"):
            if key in market_data.columns:
                value = self._coerce_float(market_data[key].iloc[-1])
                if value is not None and value > 0.0:
                    return value
        if len(closes) < 200:
            return None
        return float(closes.tail(200).mean())

    def _select_short_leg(
        self,
        chain: pd.DataFrame,
        spot: float,
        market_data: pd.DataFrame,
    ) -> tuple[pd.Series | None, str | None]:
        ranked_chain = chain.copy()
        ranked_chain["_delta_distance"] = (
            ranked_chain["_delta"].abs().sub(self.short_delta_target).abs().round(8)
        )

        if ranked_chain["_delta"].notna().any():
            primary = ranked_chain.sort_values(
                by=["_delta_distance", "_strike"],
                ascending=[True, True],
            ).iloc[0]
            if self._row_meets_liquidity(primary):
                return primary, "delta_primary"

            strikes = sorted(float(value) for value in ranked_chain["_strike"].dropna().unique())
            primary_index = strikes.index(float(primary["_strike"]))
            search_window = strikes[max(0, primary_index - 2): primary_index + 3]
            liquid_candidates = ranked_chain.loc[
                ranked_chain["_strike"].isin(search_window)
            ].copy()
            liquid_candidates = liquid_candidates.loc[
                liquid_candidates.apply(self._row_meets_liquidity, axis=1)
            ]
            if not liquid_candidates.empty:
                return (
                    liquid_candidates.sort_values(
                        by=["_delta_distance", "_strike"],
                        ascending=[True, True],
                    ).iloc[0],
                    "delta_search_liquid",
                )

        theoretical_strike = self._resolve_theoretical_short_strike(spot, market_data)
        if theoretical_strike is None:
            return None, None

        fallback_candidates = ranked_chain.copy()
        fallback_candidates["_theoretical_distance"] = (
            fallback_candidates["_strike"] - theoretical_strike
        ).abs()
        return (
            fallback_candidates.sort_values(
                by=["_theoretical_distance", "_strike"],
                ascending=[True, True],
            ).iloc[0],
            "iv_fallback",
        )

    def _resolve_theoretical_short_strike(
        self,
        spot: float,
        market_data: pd.DataFrame,
    ) -> float | None:
        iv_7d = self._resolve_7day_iv(market_data)
        if iv_7d is None or iv_7d <= 0.0:
            return None

        normalized_iv = iv_7d / 100.0 if iv_7d > 1.0 else iv_7d
        theoretical_strike = spot * (1.0 - (normalized_iv / math.sqrt(365.0)) * 1.28)
        return self._snap_strike(theoretical_strike)

    def _resolve_7day_iv(self, market_data: pd.DataFrame) -> float | None:
        configured_iv = self._coerce_float(self.config.get("iv_7d"))
        if configured_iv is not None and configured_iv > 0.0:
            return configured_iv

        for key in ("iv_7d", "iv", "implied_volatility", "atm_iv_7d"):
            if key in market_data.columns:
                value = self._coerce_float(market_data[key].iloc[-1])
                if value is not None and value > 0.0:
                    return value
        return None

    def _select_expiration_date(
        self,
        expiry_series: pd.Series,
        target_expiration_date: date,
    ) -> date | None:
        available_dates = sorted({ts.date() for ts in expiry_series.dropna()})
        if not available_dates:
            return None

        candidates = [
            expiry_date
            for expiry_date in available_dates
            if abs((expiry_date - target_expiration_date).days) <= self.expiry_flex_days
        ]
        if not candidates:
            return None

        return min(
            candidates,
            key=lambda expiry_date: (
                abs((expiry_date - target_expiration_date).days),
                -expiry_date.toordinal(),
            ),
        )

    def _resolve_current_spread_value(
        self,
        market_data: pd.DataFrame,
        metadata: dict[str, Any],
    ) -> float | None:
        option_chain = self._resolve_option_chain(market_data)
        if option_chain is None or option_chain.empty:
            return None

        chain = option_chain.copy()
        type_series = chain.get("option_type")
        if type_series is None:
            type_series = chain.get("right")
        if type_series is None:
            return None

        chain = chain.assign(_option_type=type_series.astype(str).str.lower())
        chain = chain.loc[chain["_option_type"].eq("put")].copy()
        if chain.empty:
            return None

        chain["_strike"] = self._numeric_column(chain, ("strike",))
        chain["_premium"] = chain.apply(self._mid_price_from_row, axis=1)
        expiry_series = self._expiry_column(chain)
        expiration_date = self._coerce_date(metadata.get("expiration_date"))
        if expiration_date is not None and expiry_series is not None:
            chain = chain.assign(_expiry=expiry_series)
            chain = chain.loc[chain["_expiry"].dt.date.eq(expiration_date)]
        if chain.empty:
            return None

        short_put = self._coerce_float(metadata.get("short_put_strike"))
        long_put = self._coerce_float(metadata.get("long_put_strike"))
        if short_put is None or long_put is None:
            return None

        short_leg = chain.loc[(chain["_strike"] - short_put).abs() < 1e-9]
        long_leg = chain.loc[(chain["_strike"] - long_put).abs() < 1e-9]
        if short_leg.empty or long_leg.empty:
            return None

        return round(
            max(float(short_leg.iloc[0]["_premium"]) - float(long_leg.iloc[0]["_premium"]), 0.0),
            4,
        )

    def _row_meets_liquidity(self, row: pd.Series) -> bool:
        bid = self._coerce_float(row.get("_bid"))
        ask = self._coerce_float(row.get("_ask"))
        premium = self._coerce_float(row.get("_premium"))
        open_interest = self._coerce_float(row.get("_open_interest")) or 0.0
        volume = self._coerce_float(row.get("_volume")) or 0.0

        if bid is None or ask is None or premium is None or premium <= 0.0:
            return False
        if bid <= 0.0 or ask <= 0.0 or ask < bid:
            return False

        spread_ratio = (ask - bid) / premium
        return (
            spread_ratio <= self.max_bid_ask_spread_ratio
            and open_interest >= self.min_open_interest
            and volume >= self.min_daily_volume
        )

    def _calculate_contracts(self, spread_width: float) -> int:
        width_risk = max(spread_width, 0.01) * self._contract_multiplier()
        if width_risk <= 0.0:
            return 1
        contracts = int(self.max_trade_capital // width_risk)
        return max(1, min(self.max_contracts, contracts))

    def _contract_multiplier(self) -> int:
        return SPX_CONTRACT_MULTIPLIER if self.symbol in {"SPX", "XSP"} else SPY_CONTRACT_MULTIPLIER

    def _hybrid_otm_threshold(self, spread_width: float) -> float:
        return self.narrow_otm_threshold if spread_width <= self._narrow_width_cutoff() else self.wide_otm_threshold

    def _resolve_spread_width(self, spread_width: Any) -> float:
        candidate = abs(float(spread_width))
        allowed_widths = self._allowed_spread_widths()
        if candidate in allowed_widths:
            return candidate
        return min(allowed_widths, key=lambda width: abs(width - candidate))

    def _allowed_spread_widths(self) -> tuple[float, ...]:
        if self.symbol == "SPX":
            return PUT_CREDIT_7_INDEX_ALLOWED_WIDTHS
        return PUT_CREDIT_7_MINI_ALLOWED_WIDTHS

    def _default_spread_width(self) -> float:
        if self.symbol == "SPX":
            return PUT_CREDIT_7_DEFAULT_INDEX_SPREAD_WIDTH
        return PUT_CREDIT_7_DEFAULT_MINI_SPREAD_WIDTH

    def _default_max_contracts(self) -> int:
        if self.symbol == "SPX":
            return PUT_CREDIT_7_DEFAULT_INDEX_MAX_CONTRACTS
        return PUT_CREDIT_7_DEFAULT_MINI_MAX_CONTRACTS

    def _narrow_width_cutoff(self) -> float:
        if self.symbol == "SPX":
            return PUT_CREDIT_7_DEFAULT_INDEX_NARROW_WIDTH_CUTOFF
        return PUT_CREDIT_7_DEFAULT_MINI_NARROW_WIDTH_CUTOFF

    def _parse_exit_time(self, candidate: Any) -> time:
        resolved = _parse_put_credit_spread_7_time(candidate)
        if candidate is None:
            return PUT_CREDIT_7_DEFAULT_EXPIRATION_EXIT_TIME
        if isinstance(candidate, (time, str)):
            return resolved
        return PUT_CREDIT_7_DEFAULT_EXPIRATION_EXIT_TIME

    def _snap_strike(self, strike: float) -> float:
        snapped = round(strike / self.strike_increment) * self.strike_increment
        return round(snapped, 2)

    def _extract_series(self, market_data: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Series:
        for column in candidates:
            if column in market_data.columns:
                return market_data[column].dropna().astype(float)
        return pd.Series(dtype=float)

    def _now_et(self, market_data: pd.DataFrame | None = None) -> datetime:
        if callable(self._clock):
            now = self._clock()
            if isinstance(now, datetime):
                if now.tzinfo is None:
                    now = now.replace(tzinfo=UTC)
                return now.astimezone(ET_ZONE)

        if market_data is not None and isinstance(market_data.index, pd.DatetimeIndex) and len(market_data.index) > 0:
            ts = market_data.index[-1]
            if ts.tzinfo is None:
                ts = ts.tz_localize(UTC)
            return ts.to_pydatetime().astimezone(ET_ZONE)

        return datetime.now(UTC).astimezone(ET_ZONE)

    @staticmethod
    def _numeric_column(frame: pd.DataFrame, candidates: tuple[str, ...]) -> pd.Series:
        for column in candidates:
            if column in frame.columns:
                return pd.to_numeric(frame[column], errors="coerce")
        return pd.Series(index=frame.index, dtype=float)

    @staticmethod
    def _expiry_column(frame: pd.DataFrame) -> pd.Series | None:
        for column in ("expiration", "expiry", "expiration_date", "expiry_date"):
            if column in frame.columns:
                return pd.to_datetime(frame[column], errors="coerce", utc=True)
        return None

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_date(value: Any) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value in {None, ""}:
            return None
        try:
            return datetime.fromisoformat(str(value)).date()
        except ValueError:
            return None

    @staticmethod
    def _mid_price_from_row(row: pd.Series) -> float:
        for direct_key in ("mark", "mid", "last", "price", "premium"):
            direct = PutCreditSpread7Strategy._coerce_float(row.get(direct_key))
            if direct is not None and direct > 0.0:
                return direct

        bid = PutCreditSpread7Strategy._coerce_float(row.get("bid"))
        ask = PutCreditSpread7Strategy._coerce_float(row.get("ask"))
        if bid is not None and ask is not None and bid > 0.0 and ask > 0.0:
            return round((bid + ask) / 2.0, 4)
        if bid is not None and bid > 0.0:
            return bid
        if ask is not None and ask > 0.0:
            return ask
        return 0.0

    @classmethod
    def create(
        cls,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        **kwargs: Any,
    ) -> PutCreditSpread7Strategy:
        """Convenience factory mirroring the existing strategy family pattern."""
        return cls(event_manager=event_manager, risk_profile=risk_profile, config=kwargs)
