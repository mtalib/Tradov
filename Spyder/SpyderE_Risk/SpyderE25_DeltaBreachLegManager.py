#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE25_DeltaBreachLegManager.py
Purpose: Delta-based single-leg breach manager for SPX/SPXW short options.
"""

from __future__ import annotations

from Spyder.SpyderN_OptionsAnalytics.SpyderN16_LiveDeltaEstimator import estimate_live_delta
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU51_OptionTypesAndTime import ShortLeg


class DeltaBreachLegManager:
    """Monitor active short legs and trigger immediate close on delta breach."""

    def __init__(self, *, broker_client, max_short_delta: float = 0.35) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self.broker = broker_client
        self.max_short_delta = max_short_delta
        self._active: dict[str, ShortLeg] = {}

    def register_legs(self, legs: list[ShortLeg]) -> None:
        for leg in legs:
            self._active[leg.symbol] = leg

    def remove_leg(self, symbol: str) -> None:
        self._active.pop(symbol, None)

    def active_count(self) -> int:
        return len(self._active)

    def evaluate_once(self, quote_map: dict[str, dict]) -> list[ShortLeg]:
        """Return list of legs that were closed due to delta breaches."""

        closed: list[ShortLeg] = []
        for symbol in list(self._active.keys()):
            leg = self._active.get(symbol)
            quote = quote_map.get(symbol)
            if leg is None or quote is None:
                continue

            delta = estimate_live_delta(leg, quote)
            if delta is None:
                delta = self._broker_delta_fallback(quote)
            if delta is None:
                continue

            if abs(delta) < self.max_short_delta:
                continue

            if self._close_short_leg(leg):
                self._active.pop(symbol, None)
                closed.append(leg)

        return closed

    @staticmethod
    def _broker_delta_fallback(quote: dict) -> float | None:
        greeks = quote.get("greeks") or {}
        value = greeks.get("delta")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _close_short_leg(self, leg: ShortLeg) -> bool:
        """Close one threatened short leg immediately using marketable order semantics."""

        try:
            self.broker.place_multileg_order(
                underlying="SPX",
                legs=[{"option_symbol": leg.symbol, "side": "buy_to_close", "quantity": leg.quantity}],
                order_type="market",
                duration="day",
                tag=f"{leg.order_tag}-delta-stop",
            )
            self.logger.warning(
                "Delta breach close executed for %s at threshold %.2f",
                leg.symbol,
                self.max_short_delta,
            )
            return True
        except Exception as exc:  # noqa: BLE001
            self.logger.error("Delta breach close failed for %s: %s", leg.symbol, exc)
            return False
