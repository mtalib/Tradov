#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderN_OptionsAnalytics
Module: SpyderN15_GammaRegimeEngine.py
Purpose: Lightweight gamma-regime estimator for SPX/SPXW premium-selling gates.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU51_OptionTypesAndTime import GammaRegime, now_et

logger = SpyderLogger.get_logger(__name__)

_CONTRACT_MULTIPLIER = 100


class GammaRegimeEngine:
    """Estimate net dealer gamma sign from current 0DTE chain greeks + OI."""

    def __init__(self, chain_fetcher, *, underlying: str = "SPX", refresh_s: float = 60.0) -> None:
        self._chain_fetcher = chain_fetcher
        self.underlying = underlying
        self.refresh_s = refresh_s
        self._lock = threading.Lock()
        self._regime = GammaRegime.UNKNOWN
        self._flip_level: float | None = None
        self._last_refresh = 0.0

    def current_regime(self) -> GammaRegime:
        if time.monotonic() - self._last_refresh > self.refresh_s:
            try:
                self.refresh()
            except Exception:  # noqa: BLE001
                logger.exception("Gamma regime refresh failed")
        with self._lock:
            return self._regime

    def flip_level(self) -> float | None:
        with self._lock:
            return self._flip_level

    def refresh(self) -> None:
        chain = self._chain_fetcher(self.underlying, now_et().date().isoformat())
        regime, flip = self._compute(chain)
        with self._lock:
            self._regime = regime
            self._flip_level = flip
            self._last_refresh = time.monotonic()

    def _compute(self, chain: list[dict[str, Any]]) -> tuple[GammaRegime, float | None]:
        total = 0.0
        per_strike: list[tuple[float, float]] = []

        for option in chain:
            greeks = option.get("greeks") or {}
            gamma = greeks.get("gamma")
            oi = option.get("open_interest")
            strike = option.get("strike")
            option_type = str(option.get("option_type") or "").lower()
            if gamma is None or oi is None or strike is None:
                continue

            # Starting assumption: dealers long calls / short puts.
            sign = 1.0 if option_type == "call" else -1.0
            contribution = sign * float(gamma) * float(oi) * _CONTRACT_MULTIPLIER
            total += contribution
            per_strike.append((float(strike), contribution))

        if not per_strike:
            return GammaRegime.UNKNOWN, None

        regime = GammaRegime.POSITIVE if total >= 0.0 else GammaRegime.NEGATIVE
        per_strike.sort(key=lambda item: item[0])

        cumulative = 0.0
        flip: float | None = None
        for strike, contribution in per_strike:
            prev = cumulative
            cumulative += contribution
            if (prev <= 0.0 <= cumulative) or (prev >= 0.0 >= cumulative):
                flip = strike

        return regime, flip
