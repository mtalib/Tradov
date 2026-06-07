#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD41_ZeroHFT.py
Purpose: Standalone ZeroHFT micro-tranche strategy for SPX/SPXW.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import datetime as dt
from typing import Any
import os
import uuid

import pandas as pd

from Spyder.SpyderA_Core.SpyderA09_EventCalendarService import EventCalendarService
from Spyder.SpyderU_Utilities.SpyderU51_OptionTypesAndTime import (
    GammaRegime,
    OptionType,
    ShortLeg,
    et_time,
    now_et,
    within_window,
)

from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy,
    EventManager,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
)
from Spyder.SpyderD_Strategies.SpyderD40_MicroTrancheExecutor import (
    MicroTrancheExecutor,
    MicroTranchePlan,
)


ZERO_HFT_ALIAS = "ZeroHFT"

# SPX-focused defaults. Any field can be overridden via config.
_ZERO_HFT_DEFAULT_CONFIG: dict[str, Any] = {
    "alias": ZERO_HFT_ALIAS,
    "profile": "micro_tranche",
    "symbol": "SPX",
    "entry_delay_minutes": 2,
    "runtime_cadence_enabled": True,
    "runtime_cadence_seconds": 60,
    "entry_window_end": "15:35",
    "time_stop": "15:50",
    "max_daily_trades": 48,
    "max_positions": 4,
    "tranche_quantity": 1,
    "spread_width_points": 3.0,
    "short_delta_min": 0.07,
    "short_delta_max": 0.18,
    "short_delta_target": 0.10,
    "min_premium": 0.35,
    "profit_target": 0.30,
    "stop_loss": 1.50,
    "max_short_delta": 0.35,
    "min_probability_profit": 0.60,
    "min_iv_rank": 25,
    "max_vix": 35,
    "prefer_delta_selection": True,
    "calendar_halt_enabled": True,
    "gamma_gate_enabled": True,
    "paper_only": True,
    "require_defined_risk_entry": True,
    "tail_hedge_required": True,
    "tail_hedge_max_retries": 3,
    "tail_hedge_retry_seconds": 30,
}


def _coerce_intraday_time(value: Any, fallback_hour: int, fallback_minute: int):
    """Normalize string or time values to ET-aware time objects."""
    fallback = et_time(fallback_hour, fallback_minute)
    if value is None:
        return fallback
    if hasattr(value, "hour") and hasattr(value, "minute"):
        try:
            return et_time(int(value.hour), int(value.minute))
        except Exception:
            return fallback

    text = str(value).strip()
    if not text:
        return fallback

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
            return et_time(parsed.hour, parsed.minute)
        except ValueError:
            continue
    return fallback


def build_zero_hft_runtime_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build ZeroHFT runtime config with safe SPX-oriented defaults."""
    resolved = dict(_ZERO_HFT_DEFAULT_CONFIG)
    resolved.update(dict(config or {}))
    resolved["alias"] = ZERO_HFT_ALIAS
    resolved["symbol"] = str(resolved.get("symbol") or "SPX").upper()
    resolved["entry_delay_minutes"] = int(resolved.get("entry_delay_minutes", 2))
    resolved["runtime_cadence_enabled"] = bool(resolved.get("runtime_cadence_enabled", True))
    resolved["runtime_cadence_seconds"] = max(1, int(resolved.get("runtime_cadence_seconds", 60)))
    resolved["max_daily_trades"] = int(resolved.get("max_daily_trades", 48))
    resolved["max_positions"] = int(resolved.get("max_positions", 4))
    resolved["tranche_quantity"] = max(1, int(resolved.get("tranche_quantity", 1)))
    resolved["short_delta_min"] = float(resolved.get("short_delta_min", 0.07))
    resolved["short_delta_max"] = float(resolved.get("short_delta_max", 0.18))
    resolved["short_delta_target"] = float(resolved.get("short_delta_target", 0.10))
    resolved["max_short_delta"] = float(resolved.get("max_short_delta", 0.35))
    resolved["min_premium"] = float(resolved.get("min_premium", 0.35))
    resolved["profit_target"] = float(resolved.get("profit_target", 0.30))
    resolved["stop_loss"] = float(resolved.get("stop_loss", 1.50))
    resolved["max_vix"] = float(resolved.get("max_vix", 35.0))
    resolved["min_iv_rank"] = float(resolved.get("min_iv_rank", 25.0))
    resolved["min_probability_profit"] = float(resolved.get("min_probability_profit", 0.60))
    resolved["entry_window_end"] = _coerce_intraday_time(
        resolved.get("entry_window_end"),
        15,
        35,
    )
    resolved["time_stop"] = _coerce_intraday_time(
        resolved.get("time_stop"),
        15,
        50,
    )
    resolved["paper_only"] = bool(resolved.get("paper_only", True))
    resolved["require_defined_risk_entry"] = bool(resolved.get("require_defined_risk_entry", True))
    resolved["tail_hedge_required"] = bool(resolved.get("tail_hedge_required", True))
    resolved["tail_hedge_max_retries"] = max(1, int(resolved.get("tail_hedge_max_retries", 3)))
    resolved["tail_hedge_retry_seconds"] = max(1, int(resolved.get("tail_hedge_retry_seconds", 30)))
    return resolved


class ZeroHFTStrategy(BaseStrategy):
    """Standalone ZeroHFT strategy with micro-tranche calendar/gamma gating."""

    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any] | None = None,
    ) -> None:
        runtime_config = build_zero_hft_runtime_config(config)
        super().__init__(
            name=ZERO_HFT_ALIAS,
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=runtime_config,
            strategy_type="zero_hft",
        )

        self.name = ZERO_HFT_ALIAS
        self.runtime_config = runtime_config
        self.runtime_config["alias"] = ZERO_HFT_ALIAS
        self.symbol = str(self.runtime_config["symbol"])
        self.profile_name = str(self.runtime_config.get("profile") or "micro_tranche")
        self.max_positions = int(self.runtime_config["max_positions"])
        self.max_daily_trades = int(self.runtime_config["max_daily_trades"])
        self.tranche_quantity = int(self.runtime_config["tranche_quantity"])
        self.short_delta_min = float(self.runtime_config["short_delta_min"])
        self.short_delta_max = float(self.runtime_config["short_delta_max"])
        self.short_delta_target = float(self.runtime_config["short_delta_target"])
        self.max_short_delta = float(self.runtime_config["max_short_delta"])
        self.min_premium = float(self.runtime_config["min_premium"])
        self.profit_target = float(self.runtime_config["profit_target"])
        self.stop_loss = float(self.runtime_config["stop_loss"])
        self.max_vix = float(self.runtime_config.get("max_vix", 35.0))
        self.min_iv_rank = float(self.runtime_config.get("min_iv_rank", 25.0))
        self.min_probability_profit = float(self.runtime_config.get("min_probability_profit", 0.60))
        self.entry_delay_minutes = int(self.runtime_config["entry_delay_minutes"])
        self.runtime_cadence_enabled = bool(self.runtime_config.get("runtime_cadence_enabled", True))
        self.runtime_cadence_seconds = int(self.runtime_config.get("runtime_cadence_seconds", 120))
        self.entry_window_end = self.runtime_config["entry_window_end"]
        self.time_stop = self.runtime_config["time_stop"]
        self.calendar_halt_enabled = bool(self.runtime_config.get("calendar_halt_enabled", True))
        self.gamma_gate_enabled = bool(self.runtime_config.get("gamma_gate_enabled", True))
        self.paper_only = bool(self.runtime_config.get("paper_only", True))
        self.require_defined_risk_entry = bool(self.runtime_config.get("require_defined_risk_entry", True))
        self.tail_hedge_required = bool(self.runtime_config.get("tail_hedge_required", True))
        self.tail_hedge_max_retries = int(self.runtime_config.get("tail_hedge_max_retries", 3))
        self.tail_hedge_retry_seconds = int(self.runtime_config.get("tail_hedge_retry_seconds", 30))

        self.market_open_time = et_time(9, 30)
        self._daily_tranche_count = 0
        self._daily_tranche_date = now_et().date()
        self._tail_hedged_session_date: dt.date | None = None
        self._tail_hedge_status = "UNKNOWN"
        self._tail_hedge_detail = ""
        self._tail_hedge_retry_attempts = 0
        self._tail_hedge_retry_not_before: dt.datetime | None = None
        self._tail_hedge_retry_session_date: dt.date | None = None
        self._pending_short_legs_by_tag: dict[str, list[ShortLeg]] = {}
        self._active_short_legs: dict[str, ShortLeg] = {}
        self._short_leg_risk_status = "UNKNOWN"
        self._short_leg_risk_detail = ""

        # Optional runtime integrations (injected by orchestrator/runtime config).
        self.calendar_service = self.runtime_config.get("calendar_service")
        if self.calendar_service is None:
            self.calendar_service = EventCalendarService()
        self.gamma_engine = self.runtime_config.get("gamma_engine")
        self.option_chain_fetcher = self.runtime_config.get("option_chain_fetcher")
        self.broker_client = self.runtime_config.get("broker_client")
        self.tail_hedge_establisher = self.runtime_config.get("tail_hedge_establisher")

        self.micro_executor = None
        if self.broker_client is not None and self.gamma_engine is not None and self.calendar_service is not None:
            self.micro_executor = MicroTrancheExecutor(
                broker_client=self.broker_client,
                gamma_engine=self.gamma_engine,
                calendar_service=self.calendar_service,
                target_delta=self.short_delta_target,
                short_delta_min=self.short_delta_min,
                short_delta_max=self.short_delta_max,
                wing_width_points=float(self.runtime_config.get("spread_width_points", 3.0)),
                tranche_quantity=self.tranche_quantity,
                min_net_credit=self.min_premium,
                underlying_symbol=self.symbol,
                option_root=str(self.runtime_config.get("option_root") or "SPXW"),
                paper_only=self.paper_only,
                start_time=self._entry_start_time(),
                end_time=self.entry_window_end,
            )

        self._set_tail_hedge_status("UNKNOWN", "Tail hedge not checked yet")
        self._set_short_leg_risk_status("CLEAR", "No active short legs")

        self.logger.info(
            "ZeroHFTStrategy active with symbol=%s profile=%s",
            self.symbol,
            self.profile_name,
        )

    def _entry_start_time(self, session_date: dt.date | None = None):
        session_date = session_date or now_et().date()
        open_dt = datetime.combine(session_date, self.market_open_time, tzinfo=now_et().tzinfo)
        return (open_dt + timedelta(minutes=self.entry_delay_minutes)).timetz()

    def uses_runtime_cadence(self) -> bool:
        """Return True when D31 should drive this strategy on its cadence loop."""
        return bool(self.runtime_cadence_enabled)

    def next_runtime_evaluation_at(self, now: dt.datetime | None = None) -> dt.datetime | None:
        """Return the next aligned runtime evaluation time for the current session."""
        if not self.runtime_cadence_enabled:
            return None

        now = now or now_et()
        start_dt = datetime.combine(now.date(), self._entry_start_time(now.date()))
        end_dt = datetime.combine(now.date(), self.time_stop)
        if now <= start_dt:
            return start_dt
        if now > end_dt:
            return None

        cadence_seconds = max(int(self.runtime_cadence_seconds), 1)
        elapsed_seconds = max((now - start_dt).total_seconds(), 0.0)
        intervals = int(elapsed_seconds // cadence_seconds)
        if elapsed_seconds % cadence_seconds:
            intervals += 1
        due_at = start_dt + timedelta(seconds=intervals * cadence_seconds)
        if due_at > end_dt:
            return None
        return due_at

    @staticmethod
    def _is_paper_mode() -> bool:
        runtime_mode = str(
            os.getenv("SPYDER_TRADING_MODE")
            or os.getenv("TRADING_MODE")
            or os.getenv("ENVIRONMENT")
            or "paper"
        ).strip().lower()
        return runtime_mode in {"paper", "sim", "simulation", "development", "dev", "test"}

    def _set_tail_hedge_status(self, status: str, detail: str = "") -> None:
        normalized_status = str(status or "UNKNOWN").strip().upper()
        self._tail_hedge_status = normalized_status
        self._tail_hedge_detail = str(detail or "").strip()
        os.environ["SPYDER_ZEROHFT_TAIL_HEDGE_STATUS"] = normalized_status
        os.environ["SPYDER_ZEROHFT_TAIL_HEDGE_DETAIL"] = self._tail_hedge_detail

    def _set_short_leg_risk_status(self, status: str, detail: str = "") -> None:
        normalized_status = str(status or "UNKNOWN").strip().upper()
        self._short_leg_risk_status = normalized_status
        self._short_leg_risk_detail = str(detail or "").strip()
        os.environ["SPYDER_ZEROHFT_SHORT_LEG_STATUS"] = normalized_status
        os.environ["SPYDER_ZEROHFT_SHORT_LEG_DETAIL"] = self._short_leg_risk_detail

    def _publish_short_leg_risk_state(self, *, note: str | None = None) -> None:
        active_count = len(self._active_short_legs)
        suffix = "s" if active_count != 1 else ""
        if active_count <= 0:
            detail = "No active short legs"
            if note:
                detail = f"{str(note).strip()}; {detail}"
            self._set_short_leg_risk_status("CLEAR", detail)
            return

        detail = f"Monitoring {active_count} active short leg{suffix}"
        if note:
            detail = f"{str(note).strip()}; {detail}"
        self._set_short_leg_risk_status("ACTIVE", detail)

    def _reset_tail_hedge_retry_state(self, session_date: dt.date | None = None) -> None:
        self._tail_hedge_retry_attempts = 0
        self._tail_hedge_retry_not_before = None
        self._tail_hedge_retry_session_date = session_date

    def _tail_hedge_retry_detail(self, retry_at: dt.datetime, attempt: int) -> str:
        retry_label = retry_at.strftime("%H:%M:%S")
        retry_zone = retry_at.tzname() or "ET"
        return (
            f"Tail hedge retry scheduled at {retry_label} {retry_zone} "
            f"(attempt {attempt}/{self.tail_hedge_max_retries})"
        )

    @staticmethod
    def _coerce_short_leg_option_type(value: Any) -> OptionType | None:
        normalized = str(value or "").strip().lower()
        if normalized == OptionType.CALL.value:
            return OptionType.CALL
        if normalized == OptionType.PUT.value:
            return OptionType.PUT
        return None

    def _remember_pending_short_legs(self, order_tag: str, short_legs: list[ShortLeg]) -> None:
        normalized_tag = str(order_tag or "").strip()
        if not normalized_tag:
            return

        pending_legs: list[ShortLeg] = []
        for leg in short_legs:
            if not isinstance(leg, ShortLeg):
                continue
            pending_legs.append(
                ShortLeg(
                    symbol=leg.symbol,
                    option_type=leg.option_type,
                    strike=float(leg.strike),
                    entry_delta=float(leg.entry_delta),
                    quantity=max(int(leg.quantity), 1),
                    order_tag=str(leg.order_tag or normalized_tag),
                    opened_at=leg.opened_at,
                )
            )

        if pending_legs:
            self._pending_short_legs_by_tag[normalized_tag] = pending_legs

    def register_dispatched_short_legs(
        self,
        raw_signal: dict[str, Any],
        accepted_leg_orders: list[dict[str, Any]],
    ) -> None:
        metadata = raw_signal.get("metadata") if isinstance(raw_signal, dict) else {}
        if not isinstance(metadata, dict):
            metadata = {}

        order_tag = str(metadata.get("order_tag") or raw_signal.get("order_tag") or "").strip()
        if not order_tag:
            return

        pending_legs = list(self._pending_short_legs_by_tag.pop(order_tag, []))
        if not pending_legs:
            return

        pending_by_symbol = {
            str(leg.symbol).strip(): leg
            for leg in pending_legs
            if str(leg.symbol).strip()
        }
        registered_symbols: set[str] = set()

        for leg_order in accepted_leg_orders:
            if not isinstance(leg_order, dict):
                continue
            if str(leg_order.get("side") or "").strip().lower() != "sell_to_open":
                continue

            symbol = str(leg_order.get("symbol") or "").strip()
            if not symbol:
                continue

            pending_leg = pending_by_symbol.get(symbol)
            if pending_leg is None:
                option_type = self._coerce_short_leg_option_type(leg_order.get("option_type"))
                if option_type is not None:
                    pending_leg = next(
                        (
                            leg
                            for leg in pending_legs
                            if leg.option_type is option_type and leg.symbol not in registered_symbols
                        ),
                        None,
                    )
            if pending_leg is None:
                continue

            quantity = max(int(leg_order.get("quantity") or pending_leg.quantity), 1)
            strike = float(leg_order.get("strike") or pending_leg.strike)
            self._active_short_legs[symbol] = ShortLeg(
                symbol=symbol,
                option_type=pending_leg.option_type,
                strike=strike,
                entry_delta=float(pending_leg.entry_delta),
                quantity=quantity,
                order_tag=order_tag,
            )
            registered_symbols.add(pending_leg.symbol)

        if not self._active_short_legs and pending_legs:
            self._pending_short_legs_by_tag[order_tag] = pending_legs
            return

        if registered_symbols:
            suffix = "s" if len(registered_symbols) != 1 else ""
            self._publish_short_leg_risk_state(
                note=f"Registered {len(registered_symbols)} short leg{suffix}",
            )

    def get_active_short_legs(self) -> list[ShortLeg]:
        return list(self._active_short_legs.values())

    def remove_active_short_legs(self, symbols: list[str], *, note: str | None = None) -> None:
        removed_count = 0
        for symbol in symbols:
            normalized_symbol = str(symbol or "").strip()
            if normalized_symbol:
                if self._active_short_legs.pop(normalized_symbol, None) is not None:
                    removed_count += 1

        if removed_count > 0 or note:
            detail_note = note
            if detail_note is None and removed_count > 0:
                suffix = "s" if removed_count != 1 else ""
                detail_note = f"Removed {removed_count} short leg{suffix}"
            self._publish_short_leg_risk_state(note=detail_note)

    def _ensure_tail_hedge_ready(self) -> bool:
        now = now_et()
        session_date = now.date()
        if getattr(self, "_tail_hedge_retry_session_date", None) != session_date:
            self._reset_tail_hedge_retry_state(session_date)

        if self._tail_hedged_session_date == session_date:
            self._reset_tail_hedge_retry_state(session_date)
            self._set_tail_hedge_status("HEDGED", "Tail hedge verified for current session")
            return True

        hedge_allocator = getattr(self, "tail_hedge_allocator", None)
        if callable(hedge_allocator):
            try:
                hedge_result = hedge_allocator(self.symbol)
                if bool(hedge_result):
                    self._tail_hedged_session_date = session_date
                    self._reset_tail_hedge_retry_state(session_date)
                    self._set_tail_hedge_status("HEDGED", "Tail hedge allocated for current session")
                    return True
            except Exception as exc:
                self.logger.warning("ZeroHFT tail hedge allocation failed: %s", exc)

        if callable(self.tail_hedge_establisher):
            retry_not_before = getattr(self, "_tail_hedge_retry_not_before", None)
            if retry_not_before is not None and now < retry_not_before:
                self._set_tail_hedge_status(
                    "UNKNOWN",
                    self._tail_hedge_retry_detail(
                        retry_not_before,
                        int(getattr(self, "_tail_hedge_retry_attempts", 0)),
                    ),
                )
                return False

            attempt = int(getattr(self, "_tail_hedge_retry_attempts", 0)) + 1
            try:
                if bool(self.tail_hedge_establisher(self.symbol)):
                    self._tail_hedged_session_date = session_date
                    self._reset_tail_hedge_retry_state(session_date)
                    self._set_tail_hedge_status("HEDGED", f"Tail hedge established (attempt {attempt})")
                    return True
            except Exception as exc:
                self.logger.warning("ZeroHFT tail hedge attempt %d failed: %s", attempt, exc)

            self._tail_hedge_retry_attempts = attempt
            self._tail_hedge_retry_session_date = session_date
            if attempt < self.tail_hedge_max_retries:
                delay_seconds = max(1, int(self.tail_hedge_retry_seconds))
                retry_at = now + timedelta(seconds=delay_seconds)
                self._tail_hedge_retry_not_before = retry_at
                self.logger.info(
                    "ZeroHFT tail hedge attempt %d/%d did not establish hedge; retry eligible in %ds",
                    attempt,
                    self.tail_hedge_max_retries,
                    delay_seconds,
                )
                self._set_tail_hedge_status(
                    "UNKNOWN",
                    self._tail_hedge_retry_detail(retry_at, attempt),
                )
                return False

            self._tail_hedge_retry_not_before = None

        if self.tail_hedge_required:
            self._set_tail_hedge_status("HALTED", "HARD policy: no tail hedge, entries blocked")
            return False

        self._set_tail_hedge_status("UNHEDGED", "Tail hedge unavailable; continuing in soft mode")
        return True

    def _refresh_daily_counters(self) -> None:
        current_date = now_et().date()
        if current_date != self._daily_tranche_date:
            self._daily_tranche_date = current_date
            self._daily_tranche_count = 0

    def _within_entry_window(self) -> bool:
        now = now_et()
        delayed_open = datetime.combine(
            now.date(),
            self.market_open_time,
            tzinfo=now.tzinfo,
        ) + timedelta(minutes=self.entry_delay_minutes)
        start_time = delayed_open.timetz()
        return within_window(start_time, self.entry_window_end, now)

    def _calendar_allows_entry(self) -> bool:
        if not self.calendar_halt_enabled:
            return True
        try:
            decision = self.calendar_service.entry_decision(now_et().date())
            if decision.halt:
                self.logger.info("ZeroHFT halted by calendar gate: %s", decision.reason)
                return False
            return True
        except Exception as exc:
            self.logger.warning("ZeroHFT calendar gate failed-open: %s", exc)
            return True

    def _gamma_allows_entry(self) -> bool:
        if not self.gamma_gate_enabled:
            return True
        if self.gamma_engine is None:
            return True
        try:
            regime = self.gamma_engine.current_regime()
            if regime is GammaRegime.NEGATIVE:
                self.logger.info("ZeroHFT vetoed by negative gamma regime")
                return False
            return True
        except Exception as exc:
            self.logger.warning("ZeroHFT gamma gate failed-open: %s", exc)
            return True

    def _active_tranche_count(self) -> int:
        """Count distinct open tranches (one order tag per tranche)."""
        return len({
            str(leg.order_tag).strip()
            for leg in self._active_short_legs.values()
            if str(getattr(leg, "order_tag", "")).strip()
        })

    @staticmethod
    def _extract_latest_scalar(
        market_data: Any,
        candidates: tuple[str, ...],
    ) -> float | None:
        """Return the latest numeric value for any matching market-data column."""
        if not isinstance(market_data, pd.DataFrame):
            return None
        for candidate in candidates:
            if candidate not in market_data:
                continue
            series = market_data[candidate]
            if isinstance(series, pd.Series):
                series = series.dropna()
                if series.empty:
                    continue
                try:
                    return float(series.iloc[-1])
                except (TypeError, ValueError):
                    continue
            try:
                return float(series)
            except (TypeError, ValueError):
                continue
        return None

    def _market_data_allows_entry(self, market_data: pd.DataFrame) -> bool:
        """Apply VIX and IV-rank volatility gates; fail-open when data is absent."""
        vix = self._extract_latest_scalar(market_data, ("vix", "VIX", "^VIX"))
        if vix is not None and vix > self.max_vix:
            self.logger.info("ZeroHFT vetoed: VIX %.2f > max %.2f", vix, self.max_vix)
            return False

        iv_rank = self._extract_latest_scalar(market_data, ("iv_rank", "IVR", "ivr"))
        if iv_rank is not None:
            # Accept either a 0-1 fraction or a 0-100 percentage.
            if 0.0 <= iv_rank <= 1.0:
                iv_rank *= 100.0
            if iv_rank < self.min_iv_rank:
                self.logger.info(
                    "ZeroHFT vetoed: IV rank %.1f < min %.1f", iv_rank, self.min_iv_rank
                )
                return False
        return True

    def _log_entry_gate_block(self, gate: str, reason: str, **details: Any) -> None:
        """Emit a consistent trace line when ZeroHFT skips an entry cycle."""
        detail_bits = ", ".join(
            f"{key}={value}"
            for key, value in details.items()
            if value is not None and value != ""
        )
        if detail_bits:
            self.logger.info("ZeroHFT entry blocked at %s: %s | %s", gate, reason, detail_bits)
        else:
            self.logger.info("ZeroHFT entry blocked at %s: %s", gate, reason)

    def _plan_meets_probability_profit(self, plan: MicroTranchePlan) -> bool:
        """Gate a tranche on approximate probability of profit from short deltas.

        For a defined-risk credit structure the probability that neither short
        leg finishes in the money is approximated by ``1 - |callΔ| - |putΔ|``,
        the standard delta-as-POP proxy.
        """
        pop = 1.0 - abs(float(plan.short_call_delta)) - abs(float(plan.short_put_delta))
        if pop < self.min_probability_profit:
            self.logger.info(
                "ZeroHFT vetoed: est. POP %.2f < min %.2f",
                pop,
                self.min_probability_profit,
            )
            return False
        return True

    @staticmethod
    def _extract_price(option_row: dict[str, Any]) -> tuple[float, float, float]:
        bid = float(option_row.get("bid") or 0.0)
        ask = float(option_row.get("ask") or 0.0)
        mark = float(option_row.get("mid") or option_row.get("mark") or 0.0)
        if mark <= 0.0 and bid > 0.0 and ask > 0.0:
            mark = (bid + ask) / 2.0
        return bid, ask, mark

    @staticmethod
    def _select_delta_targets(
        options: list[dict[str, Any]],
        target_delta: float,
        delta_min: float | None = None,
        delta_max: float | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        calls = [
            opt
            for opt in options
            if str(opt.get("option_type", "")).lower() == OptionType.CALL.value
        ]
        puts = [
            opt
            for opt in options
            if str(opt.get("option_type", "")).lower() == OptionType.PUT.value
        ]

        def _delta(opt: dict[str, Any]) -> float | None:
            greeks = opt.get("greeks") or {}
            raw = greeks.get("delta")
            return float(raw) if raw is not None else None

        def _in_band(opt: dict[str, Any]) -> bool:
            abs_delta = abs(_delta(opt) or 0.0)
            return not (
                (delta_min is not None and abs_delta < delta_min)
                or (delta_max is not None and abs_delta > delta_max)
            )

        calls = [opt for opt in calls if _delta(opt) is not None and _in_band(opt)]
        puts = [opt for opt in puts if _delta(opt) is not None and _in_band(opt)]
        if not calls or not puts:
            return None, None

        short_call = min(calls, key=lambda opt: abs((_delta(opt) or 0.0) - target_delta))
        short_put = min(puts, key=lambda opt: abs(abs(_delta(opt) or 0.0) - target_delta))
        return short_call, short_put

    def _build_signal(
        self,
        *,
        option_row: dict[str, Any],
        signal_side: str,
    ) -> TradingSignal | None:
        option_symbol = str(
            option_row.get("option_symbol")
            or option_row.get("symbol")
            or ""
        ).strip()
        if not option_symbol:
            return None

        bid, ask, mark = self._extract_price(option_row)
        if mark <= 0.0 or mark < self.min_premium:
            return None

        now = datetime.now(UTC)
        stop_loss = round(mark * (1.0 + self.stop_loss), 4)
        take_profit = round(max(0.01, mark * (1.0 - self.profit_target)), 4)
        signal_type = SignalType.SELL if signal_side == "sell" else SignalType.BUY

        return TradingSignal(
            signal_id=f"zerohft-{uuid.uuid4().hex[:10]}",
            signal_type=signal_type,
            symbol=self.symbol,
            strength=SignalStrength.MODERATE,
            confidence=0.65,
            entry_price=mark,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=self.tranche_quantity,
            timestamp=now,
            expires_at=now + timedelta(minutes=2),
            bid=bid,
            ask=ask,
            option_symbol=option_symbol,
            metadata={
                "strategy_id": "ZeroHFT",
                "strategy_type": "zero_hft",
                "action": "sell_to_open",
                "tranche": True,
                "profile": self.profile_name,
                "option_type": str(option_row.get("option_type", "")).lower(),
                "target_delta": self.short_delta_target,
            },
        )

    def _build_multileg_signal(self, plan: MicroTranchePlan) -> TradingSignal:
        """Create one explicit-leg ZeroHFT signal for D31 paper multileg routing."""
        now = datetime.now(UTC)
        entry_price = max(float(plan.net_credit), 0.01)
        stop_loss_multiplier = float(getattr(self, "stop_loss", 1.50))
        profit_target = float(getattr(self, "profit_target", 0.30))
        profile_name = str(getattr(self, "profile_name", "micro_tranche"))
        target_delta = float(getattr(self, "short_delta_target", 0.10))
        return TradingSignal(
            signal_id=f"zerohft-{uuid.uuid4().hex[:10]}",
            signal_type=SignalType.SELL,
            symbol=self.symbol,
            strength=SignalStrength.STRONG,
            confidence=0.72,
            entry_price=entry_price,
            stop_loss=round(entry_price * (1.0 + stop_loss_multiplier), 4),
            take_profit=round(max(0.01, entry_price * (1.0 - profit_target)), 4),
            position_size=max(int(plan.quantity), 1),
            timestamp=now,
            expires_at=now + timedelta(minutes=2),
            metadata={
                "strategy_id": ZERO_HFT_ALIAS,
                "strategy_type": "zero_hft",
                "action": "sell",
                "tranche": True,
                "profile": profile_name,
                "target_delta": target_delta,
                "expiration_date": plan.expiration,
                "target_dte": 0,
                "order_tag": plan.tag,
                "legs": plan.serialized_legs(),
                "setup": {
                    "target_credit": plan.net_credit,
                    "expiration_date": plan.expiration,
                },
            },
        )

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        """Generate tranche entry signals using in-module calendar/gamma gates."""
        self._refresh_daily_counters()
        if self.paper_only and not self._is_paper_mode():
            self._set_tail_hedge_status("HALTED", "ZeroHFT paper-only wiring active")
            self._log_entry_gate_block("paper_mode", "paper_only mode is active outside paper runtime")
            return []

        if not self._ensure_tail_hedge_ready():
            self._log_entry_gate_block(
                "tail_hedge",
                getattr(self, "_tail_hedge_detail", "tail hedge unavailable"),
            )
            return []

        daily_trades = self._daily_tranche_count
        if daily_trades >= self.max_daily_trades:
            self._log_entry_gate_block(
                "daily_trade_limit",
                "daily tranche cap reached",
                count=daily_trades,
                max_daily_trades=self.max_daily_trades,
            )
            return []
        active_tranches = self._active_tranche_count()
        if active_tranches >= self.max_positions:
            self._log_entry_gate_block(
                "position_limit",
                "active tranche cap reached",
                active=active_tranches,
                max_positions=self.max_positions,
            )
            return []
        if not self._within_entry_window():
            now = now_et()
            delayed_open = datetime.combine(
                now.date(),
                self.market_open_time,
                tzinfo=now.tzinfo,
            ) + timedelta(minutes=self.entry_delay_minutes)
            self._log_entry_gate_block(
                "entry_window",
                "outside allowed ET window",
                now=now.strftime("%H:%M:%S ET"),
                start=delayed_open.strftime("%H:%M ET"),
                end=self.entry_window_end.strftime("%H:%M ET"),
            )
            return []
        if not self._calendar_allows_entry():
            return []
        if not self._gamma_allows_entry():
            return []
        if not self._market_data_allows_entry(market_data):
            return []

        if self.micro_executor is not None:
            plan, short_legs = self.micro_executor.plan_once()
            if plan is None:
                self._log_entry_gate_block(
                    "planner",
                    "micro-tranche planner returned no qualifying setup",
                )
                return []
            if not self._plan_meets_probability_profit(plan):
                self._log_entry_gate_block(
                    "pop_gate",
                    "planner setup failed probability-of-profit threshold",
                    call_delta=plan.short_call_delta,
                    put_delta=plan.short_put_delta,
                    min_pop=self.min_probability_profit,
                )
                return []
            signal = self._build_multileg_signal(plan)
            self._remember_pending_short_legs(
                str(signal.metadata.get("order_tag") or plan.tag),
                short_legs,
            )
            self._daily_tranche_count += 1
            return [signal]

        if self.require_defined_risk_entry:
            self.logger.info(
                "ZeroHFT defined-risk planner unavailable; skipping unstructured fallback entry"
            )
            return []

        option_rows: list[dict[str, Any]] = []
        if callable(self.option_chain_fetcher):
            try:
                fetched = self.option_chain_fetcher(self.symbol)
                if isinstance(fetched, list):
                    option_rows = [row for row in fetched if isinstance(row, dict)]
            except Exception as exc:
                self.logger.warning("ZeroHFT option chain fetch failed: %s", exc)

        if not option_rows and isinstance(market_data, pd.DataFrame):
            attrs_chain = market_data.attrs.get("option_chain")
            if isinstance(attrs_chain, list):
                option_rows = [row for row in attrs_chain if isinstance(row, dict)]

        if not option_rows:
            self._log_entry_gate_block(
                "option_chain",
                "no option chain data available for fallback entry",
            )
            return []

        short_call, short_put = self._select_delta_targets(
            option_rows,
            self.short_delta_target,
            delta_min=self.short_delta_min,
            delta_max=self.short_delta_max,
        )
        if short_call is None or short_put is None:
            self._log_entry_gate_block(
                "delta_band",
                "no call/put contracts satisfied the configured delta band",
                target=self.short_delta_target,
                min_delta=self.short_delta_min,
                max_delta=self.short_delta_max,
            )
            return []
        signals: list[TradingSignal] = []
        if short_call is not None:
            signal = self._build_signal(option_row=short_call, signal_side="sell")
            if signal is not None:
                signals.append(signal)
        if short_put is not None:
            signal = self._build_signal(option_row=short_put, signal_side="sell")
            if signal is not None:
                signals.append(signal)

        if signals:
            self._daily_tranche_count += 1
        return signals

    def validate_signal(self, signal: TradingSignal) -> bool:
        """Validate tranche signal bounds and required metadata."""
        if signal.signal_type not in {SignalType.SELL, SignalType.BUY}:
            return False
        if signal.position_size <= 0:
            return False
        if signal.entry_price <= 0:
            return False
        if signal.stop_loss <= signal.entry_price:
            return False
        if signal.take_profit <= 0:
            return False
        metadata = signal.metadata or {}
        explicit_legs = metadata.get("legs")
        has_serialized_multileg = isinstance(explicit_legs, list) and bool(explicit_legs)
        return bool(signal.option_symbol or has_serialized_multileg)

    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Use configured tranche quantity as the canonical sizing unit."""
        return max(1, int(self.tranche_quantity))

    def should_exit_position(
        self,
        position: StrategyPosition,
        market_data: pd.DataFrame,
    ) -> tuple[bool, str]:
        """Exit on stop, target, or configured ET time stop."""
        _ = market_data
        if position.current_price <= 0:
            return False, ""

        if position.current_price >= position.stop_loss:
            return True, "stop_loss"
        if position.current_price <= position.take_profit:
            return True, "profit_target"
        if now_et().timetz() >= self.time_stop:
            return True, "time_stop"
        return False, ""

    @classmethod
    def create(
        cls,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        **kwargs: Any,
    ) -> ZeroHFTStrategy:
        """Factory helper matching other strategy modules."""
        return cls(event_manager=event_manager, risk_profile=risk_profile, config=kwargs)


def create_zero_hft_strategy(
    event_manager: EventManager,
    risk_profile: RiskProfile,
    config: dict[str, Any] | None = None,
) -> ZeroHFTStrategy:
    """Convenience constructor for plugin/registry-style usage."""
    return ZeroHFTStrategy(event_manager=event_manager, risk_profile=risk_profile, config=config)

