#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD40_MicroTrancheExecutor.py
Purpose: SPX/SPXW micro-tranche entry executor with regime and calendar gating.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
import re
from typing import Any
import uuid

from Spyder.SpyderA_Core.SpyderA09_EventCalendarService import EventCalendarService
from Spyder.SpyderB_Broker.SpyderB41_SmartLimitRouter import SmartLimitRouter
from Spyder.SpyderB_Broker.SpyderB40_TradierClient import OptionLeg, OrderSide
from Spyder.SpyderN_OptionsAnalytics.SpyderN15_GammaRegimeEngine import GammaRegimeEngine
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU51_OptionTypesAndTime import (
    GammaRegime,
    OptionType,
    ShortLeg,
    TrancheResult,
    et_time,
    now_et,
    within_window,
)


_OCC_OPTION_SYMBOL_RE = re.compile(r"^([A-Z]{1,6})\d{6}[CP]\d{8}$")


@dataclass
class MicroTranchePlan:
    """Explicit-leg micro-tranche entry plan for downstream paper routing."""

    underlying: str
    expiration: str
    long_put_symbol: str
    long_put_strike: float
    long_put_price: float
    short_put_symbol: str
    short_put_strike: float
    short_put_price: float
    short_put_delta: float
    short_call_symbol: str
    short_call_strike: float
    short_call_price: float
    short_call_delta: float
    long_call_symbol: str
    long_call_strike: float
    long_call_price: float
    net_credit: float
    quantity: int
    tag: str
    timestamp: dt.datetime = field(default_factory=now_et)

    def serialized_legs(self) -> list[dict[str, Any]]:
        """Return explicit long/short leg metadata for D31 paper routing."""
        return [
            {
                "role": "long_put",
                "option_type": OptionType.PUT.value,
                "strike": self.long_put_strike,
                "position": "long",
                "contracts": self.quantity,
                "premium": self.long_put_price,
                "expiration": self.expiration,
            },
            {
                "role": "short_put",
                "option_type": OptionType.PUT.value,
                "strike": self.short_put_strike,
                "position": "short",
                "contracts": self.quantity,
                "premium": self.short_put_price,
                "expiration": self.expiration,
            },
            {
                "role": "short_call",
                "option_type": OptionType.CALL.value,
                "strike": self.short_call_strike,
                "position": "short",
                "contracts": self.quantity,
                "premium": self.short_call_price,
                "expiration": self.expiration,
            },
            {
                "role": "long_call",
                "option_type": OptionType.CALL.value,
                "strike": self.long_call_strike,
                "position": "long",
                "contracts": self.quantity,
                "premium": self.long_call_price,
                "expiration": self.expiration,
            },
        ]


class MicroTrancheExecutor:
    """Evaluate and submit small SPX/SPXW credit tranches on a fixed cadence."""

    def __init__(
        self,
        *,
        broker_client,
        gamma_engine: GammaRegimeEngine,
        calendar_service: EventCalendarService,
        target_delta: float = 0.10,
        wing_width_points: float = 5.0,
        tranche_quantity: int = 1,
        min_net_credit: float = 0.05,
        underlying_symbol: str = "SPX",
        option_root: str = "SPXW",
        paper_only: bool = True,
        start_time: dt.time | None = None,
        end_time: dt.time | None = None,
    ) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self.broker = broker_client
        self.gamma = gamma_engine
        self.calendar = calendar_service
        self.target_delta = target_delta
        self.wing_width = wing_width_points
        self.tranche_quantity = tranche_quantity
        self.min_net_credit = float(min_net_credit)
        self.underlying_symbol = str(underlying_symbol or "SPX").upper()
        self.option_root = str(option_root or "SPXW").upper()
        self.paper_only = bool(paper_only)
        self.start_time = start_time or et_time(9, 32)
        self.end_time = end_time or et_time(15, 50)
        self.router = SmartLimitRouter()

    def _is_paper_mode(self) -> bool:
        runtime_mode = str(
            getattr(self.broker, "trading_mode", "")
            or getattr(self.broker, "mode", "")
            or "paper"
        ).strip().lower()
        return runtime_mode in {"paper", "sim", "simulation", "test"}

    @staticmethod
    def _extract_expiration_dates(payload: dict[str, Any]) -> list[str]:
        expirations = payload.get("expirations", {}) if isinstance(payload, dict) else {}
        raw_dates = expirations.get("date", []) if isinstance(expirations, dict) else []
        if isinstance(raw_dates, str):
            return [raw_dates]
        if isinstance(raw_dates, list):
            return [str(item) for item in raw_dates if str(item).strip()]
        return []

    def _resolve_todays_expiration(self) -> str | None:
        try:
            payload = self.broker.get_option_expirations(self.underlying_symbol)
        except Exception as exc:
            self.logger.warning("MicroTrancheExecutor expiration fetch failed: %s", exc)
            return None

        today_str = now_et().date().isoformat()
        listed = set(self._extract_expiration_dates(payload))
        if today_str not in listed:
            self.logger.info("MicroTrancheExecutor no listed 0DTE expiration for %s", today_str)
            return None
        return today_str

    @staticmethod
    def _extract_quote(option: Any) -> dict[str, Any]:
        if isinstance(option, dict):
            return option
        return {
            "symbol": getattr(option, "symbol", ""),
            "option_type": getattr(option, "option_type", ""),
            "strike": getattr(option, "strike", 0.0),
            "bid": getattr(option, "bid", 0.0),
            "ask": getattr(option, "ask", 0.0),
            "mid": getattr(option, "mid", 0.0),
            "delta": getattr(option, "delta", None),
        }

    @staticmethod
    def _extract_delta(option: dict[str, Any]) -> float | None:
        raw_delta = option.get("delta")
        if raw_delta is not None:
            return float(raw_delta)
        greeks = option.get("greeks") or {}
        value = greeks.get("delta")
        return float(value) if value is not None else None

    @staticmethod
    def _mid_price(option: dict[str, Any]) -> float:
        bid = float(option.get("bid") or 0.0)
        ask = float(option.get("ask") or 0.0)
        mid = float(option.get("mid") or 0.0)
        if mid > 0.0:
            return mid
        if bid > 0.0 and ask > 0.0:
            return round((bid + ask) / 2.0, 4)
        return 0.0

    def _select_wings(
        self,
        options: list[dict[str, Any]],
        short_call: dict[str, Any],
        short_put: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        calls = [opt for opt in options if str(opt.get("option_type", "")).lower() == OptionType.CALL.value]
        puts = [opt for opt in options if str(opt.get("option_type", "")).lower() == OptionType.PUT.value]

        call_target = float(short_call.get("strike", 0.0) or 0.0) + self.wing_width
        put_target = float(short_put.get("strike", 0.0) or 0.0) - self.wing_width

        call_candidates = [opt for opt in calls if float(opt.get("strike", 0.0) or 0.0) >= call_target]
        put_candidates = [opt for opt in puts if float(opt.get("strike", 0.0) or 0.0) <= put_target]

        long_call = min(call_candidates, key=lambda opt: float(opt.get("strike", 0.0) or 0.0)) if call_candidates else None
        long_put = max(put_candidates, key=lambda opt: float(opt.get("strike", 0.0) or 0.0)) if put_candidates else None
        return long_call, long_put

    @staticmethod
    def _option_symbol(option: dict[str, Any]) -> str:
        return str(option.get("option_symbol") or option.get("symbol") or "").strip()

    @staticmethod
    def _extract_occ_underlying(symbol: str) -> str | None:
        normalized = str(symbol or "").strip().upper().replace(" ", "")
        match = _OCC_OPTION_SYMBOL_RE.match(normalized)
        if match is None:
            return None
        return str(match.group(1) or "").strip().upper() or None

    def _spxw_only_entry_symbols_allowed(self, symbols: list[str]) -> tuple[bool, str]:
        blocked_symbols: list[str] = []
        for symbol in symbols:
            underlying = self._extract_occ_underlying(symbol)
            if underlying != "SPXW":
                blocked_symbols.append(str(symbol))

        if blocked_symbols:
            return False, ", ".join(blocked_symbols)
        return True, ""

    def plan_once(self) -> tuple[MicroTranchePlan | None, list[ShortLeg]]:
        """Run one tranche decision cycle and return an explicit-leg entry plan."""
        if self.paper_only and not self._is_paper_mode():
            self.logger.info("MicroTrancheExecutor paper_only gate active; skipping non-paper mode")
            return None, []

        when = now_et()
        if not within_window(self.start_time, self.end_time, when):
            return None, []

        decision = self.calendar.entry_decision(when.date())
        if decision.halt:
            self.logger.info("MicroTrancheExecutor halted by calendar: %s", decision.reason)
            return None, []

        regime = self.gamma.current_regime()
        if regime is GammaRegime.NEGATIVE:
            self.logger.info("MicroTrancheExecutor vetoed by negative gamma regime")
            return None, []

        expiration = self._resolve_todays_expiration()
        if not expiration:
            return None, []

        try:
            raw_chain = self.broker.get_option_chain_with_greeks(self.underlying_symbol, expiration)
        except Exception as exc:
            self.logger.warning("MicroTrancheExecutor chain fetch failed: %s", exc)
            return None, []

        options = [self._extract_quote(opt) for opt in raw_chain or []]
        short_call, short_put = self.select_delta_targets(options, self.target_delta)
        if not short_call or not short_put:
            self.logger.info("MicroTrancheExecutor no short strikes in target delta band")
            return None, []

        long_call, long_put = self._select_wings(options, short_call, short_put)
        if not long_call or not long_put:
            self.logger.info("MicroTrancheExecutor no defining wings available")
            return None, []

        net_credit = round(
            self._mid_price(short_call)
            + self._mid_price(short_put)
            - self._mid_price(long_call)
            - self._mid_price(long_put),
            4,
        )
        if net_credit < self.min_net_credit:
            self.logger.info(
                "MicroTrancheExecutor credit %.4f below minimum %.4f",
                net_credit,
                self.min_net_credit,
            )
            return None, []

        short_call_symbol = self._option_symbol(short_call)
        short_put_symbol = self._option_symbol(short_put)
        long_call_symbol = self._option_symbol(long_call)
        long_put_symbol = self._option_symbol(long_put)
        if not all([short_call_symbol, short_put_symbol, long_call_symbol, long_put_symbol]):
            self.logger.warning("MicroTrancheExecutor missing option symbols for multileg order")
            return None, []

        entry_symbols = [
            short_call_symbol,
            short_put_symbol,
            long_call_symbol,
            long_put_symbol,
        ]
        symbols_allowed, blocked_detail = self._spxw_only_entry_symbols_allowed(entry_symbols)
        if not symbols_allowed:
            self.logger.warning(
                "MicroTrancheExecutor blocked by SPXW-only option entry policy: %s",
                blocked_detail,
            )
            return None, []

        order_tag = f"microtranche-{uuid.uuid4().hex[:10]}"
        short_call_delta = float(self._extract_delta(short_call) or self.target_delta)
        short_put_delta = float(self._extract_delta(short_put) or (-self.target_delta))

        plan = MicroTranchePlan(
            underlying=self.underlying_symbol,
            expiration=expiration,
            long_put_symbol=long_put_symbol,
            long_put_strike=float(long_put.get("strike", 0.0) or 0.0),
            long_put_price=self._mid_price(long_put),
            short_put_symbol=short_put_symbol,
            short_put_strike=float(short_put.get("strike", 0.0) or 0.0),
            short_put_price=self._mid_price(short_put),
            short_put_delta=short_put_delta,
            short_call_symbol=short_call_symbol,
            short_call_strike=float(short_call.get("strike", 0.0) or 0.0),
            short_call_price=self._mid_price(short_call),
            short_call_delta=short_call_delta,
            long_call_symbol=long_call_symbol,
            long_call_strike=float(long_call.get("strike", 0.0) or 0.0),
            long_call_price=self._mid_price(long_call),
            net_credit=net_credit,
            quantity=self.tranche_quantity,
            tag=order_tag,
        )

        short_legs = [
            ShortLeg(
                symbol=short_call_symbol,
                option_type=OptionType.CALL,
                strike=float(short_call.get("strike", 0.0) or 0.0),
                entry_delta=short_call_delta,
                quantity=self.tranche_quantity,
                order_tag=order_tag,
            ),
            ShortLeg(
                symbol=short_put_symbol,
                option_type=OptionType.PUT,
                strike=float(short_put.get("strike", 0.0) or 0.0),
                entry_delta=short_put_delta,
                quantity=self.tranche_quantity,
                order_tag=order_tag,
            ),
        ]
        return plan, short_legs

    def evaluate_once(self) -> tuple[TrancheResult | None, list[ShortLeg]]:
        """Run one tranche decision cycle and submit the selected multileg order."""

        plan, short_legs = self.plan_once()
        if plan is None:
            return None, []

        legs = [
            OptionLeg(plan.short_call_symbol, OrderSide.SELL_TO_OPEN, plan.quantity),
            OptionLeg(plan.long_call_symbol, OrderSide.BUY_TO_OPEN, plan.quantity),
            OptionLeg(plan.short_put_symbol, OrderSide.SELL_TO_OPEN, plan.quantity),
            OptionLeg(plan.long_put_symbol, OrderSide.BUY_TO_OPEN, plan.quantity),
        ]

        try:
            response = self.broker.place_multileg_order(
                symbol=plan.underlying,
                legs=legs,
                order_type="credit",
                price=plan.net_credit,
                tag=plan.tag,
            )
        except Exception as exc:
            self.logger.warning("MicroTrancheExecutor order placement failed: %s", exc)
            return None, []

        order_id = None
        order_bucket = response.get("order", {}) if isinstance(response, dict) else {}
        if isinstance(order_bucket, dict):
            raw_order_id = order_bucket.get("id")
            order_id = int(raw_order_id) if raw_order_id is not None else None

        result = TrancheResult(
            underlying=plan.underlying,
            call_symbol=plan.short_call_symbol,
            put_symbol=plan.short_put_symbol,
            call_strike=plan.short_call_strike,
            put_strike=plan.short_put_strike,
            net_credit=plan.net_credit,
            order_id=order_id,
            filled=bool(order_id),
            tag=plan.tag,
        )
        return result, short_legs

    @staticmethod
    def select_delta_targets(options: list[dict[str, Any]], target_delta: float) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Select nearest call/put options by absolute target delta."""

        calls = [opt for opt in options if str(opt.get("option_type", "")).lower() == OptionType.CALL.value]
        puts = [opt for opt in options if str(opt.get("option_type", "")).lower() == OptionType.PUT.value]

        def _delta(opt: dict[str, Any]) -> float | None:
            greeks = opt.get("greeks") or {}
            value = greeks.get("delta")
            return float(value) if value is not None else None

        calls = [opt for opt in calls if _delta(opt) is not None]
        puts = [opt for opt in puts if _delta(opt) is not None]
        if not calls or not puts:
            return None, None

        short_call = min(calls, key=lambda opt: abs((_delta(opt) or 0.0) - target_delta))
        short_put = min(puts, key=lambda opt: abs(abs(_delta(opt) or 0.0) - target_delta))
        return short_call, short_put
