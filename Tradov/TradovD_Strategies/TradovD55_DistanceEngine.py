#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies.TradovD50_PairDiscovery
Module: TradovD55_DistanceEngine.py
Purpose: Distance-approach (SSD) pairs selection and signalling

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-15 Time: 00:00:00

Module Description:
    Implements the classic distance approach to pairs trading
    (Gatev, Goetzmann & Rouwenhorst, 2006; Do & Faff, 2010/2012).

    Formation step:
      - Normalise each symbol's price series to [0, 1] over a formation
        window: P_norm = (P - min) / (max - min).
      - Compute the sum of squared distances (SSD) between every candidate
        pair of normalised series and keep the N smallest (closest) pairs.
      - Record the historical std of the normalised spread per pair, used
        as the trading-band reference, plus formation min/max so the
        out-of-sample (trading) prices are normalised consistently.

    Trading step (per Gatev et al.):
      - Spread = P_norm_a - P_norm_b.
      - Open SHORT-spread (sell A / buy B) when spread >= +k * std.
      - Open LONG-spread  (buy A / sell B) when spread <= -k * std.
      - Close when the spread crosses zero (mean reversion).

    This engine deals only in stock/ETF price series (Tradov trades stocks
    and ETFs, not options spreads), so no contract multipliers are applied.

    Optional refined selection criteria (Do & Faff):
      - same-sector matching,
      - preference for pairs with more zero-crossings (mean-reversion),
      - preference for higher spread std (profitability proxy).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger


@dataclass
class DistancePair:
    """A formed distance pair with normalisation state and band reference."""

    symbol_a: str
    symbol_b: str
    ssd: float
    spread_mean: float
    spread_std: float
    zero_crossings: int
    sector: str | None = None
    # Formation min/max used to normalise out-of-sample prices consistently.
    min_a: float = 0.0
    max_a: float = 1.0
    min_b: float = 0.0
    max_b: float = 1.0
    sample_size: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.symbol_a}/{self.symbol_b}"

    def normalize_a(self, price: float) -> float:
        rng = self.max_a - self.min_a
        return (price - self.min_a) / rng if rng > 1e-12 else 0.0

    def normalize_b(self, price: float) -> float:
        rng = self.max_b - self.min_b
        return (price - self.min_b) / rng if rng > 1e-12 else 0.0

    def spread(self, price_a: float, price_b: float) -> float:
        """Normalised spread for a fresh pair of (raw) prices."""
        return self.normalize_a(price_a) - self.normalize_b(price_b)

    def z_score(self, price_a: float, price_b: float) -> float:
        if self.spread_std <= 1e-12:
            return 0.0
        return (self.spread(price_a, price_b) - self.spread_mean) / self.spread_std


class DistanceApproachEngine:
    """Forms distance pairs and produces entry/exit signals on their spread."""

    def __init__(
        self,
        entry_threshold: float = 2.0,
        top_n: int = 20,
        same_sector_only: bool = False,
        min_zero_crossings: int = 0,
        logger: logging.Logger | None = None,
    ):
        """
        Args:
            entry_threshold: trading band width in std units (k). Gatev et al.
                use 2.0 historical standard deviations.
            top_n: number of closest (lowest-SSD) pairs to retain.
            same_sector_only: restrict candidate pairs to the same sector.
            min_zero_crossings: discard pairs whose formation spread crosses
                its mean fewer than this many times (liquidity / reversion).
            logger: optional logger.
        """
        self.entry_threshold = entry_threshold
        self.top_n = top_n
        self.same_sector_only = same_sector_only
        self.min_zero_crossings = min_zero_crossings
        self.logger = logger or TradovLogger.get_logger("DistanceApproachEngine")

    # ------------------------------------------------------------------ #
    # Formation
    # ------------------------------------------------------------------ #
    @staticmethod
    def normalize(series: np.ndarray) -> tuple[np.ndarray, float, float]:
        """Min-max normalise a price series to [0, 1].

        Returns the normalised series along with the min and max used, so the
        same transform can be applied to out-of-sample prices.
        """
        lo = float(np.min(series))
        hi = float(np.max(series))
        rng = hi - lo
        if rng <= 1e-12:
            return np.zeros_like(series, dtype=float), lo, hi
        return (series - lo) / rng, lo, hi

    @staticmethod
    def _zero_crossings(spread: np.ndarray, mean: float) -> int:
        centered = spread - mean
        signs = np.sign(centered)
        # Treat exact zeros as continuation of the previous sign.
        nonzero = signs[signs != 0]
        if len(nonzero) < 2:
            return 0
        return int(np.sum(nonzero[1:] != nonzero[:-1]))

    def form_pairs(
        self,
        prices: pd.DataFrame,
        candidate_pairs: list[tuple[str, str]] | None = None,
        sector_map: dict[str, str] | None = None,
    ) -> list[DistancePair]:
        """Rank candidate pairs by SSD over the formation window.

        Args:
            prices: formation-period prices, one column per symbol.
            candidate_pairs: explicit pairs to evaluate; if None all column
                combinations are used (optionally filtered to same sector).
            sector_map: symbol -> sector, used for same-sector filtering and
                annotation.

        Returns:
            Up to ``top_n`` DistancePair objects sorted by ascending SSD.
        """
        if prices is None or prices.empty or len(prices.columns) < 2:
            return []

        sector_map = sector_map or {}
        symbols = list(prices.columns)

        if candidate_pairs is None:
            candidate_pairs = list(combinations(sorted(symbols), 2))

        normalized: dict[str, tuple[np.ndarray, float, float]] = {}
        for sym in symbols:
            series = prices[sym].dropna().values.astype(float)
            if len(series) > 1:
                normalized[sym] = self.normalize(series)

        formed: list[DistancePair] = []
        for sym_a, sym_b in candidate_pairs:
            if sym_a not in normalized or sym_b not in normalized:
                continue

            sec_a = sector_map.get(sym_a)
            sec_b = sector_map.get(sym_b)
            if self.same_sector_only and sec_a is not None and sec_a != sec_b:
                continue

            norm_a, min_a, max_a = normalized[sym_a]
            norm_b, min_b, max_b = normalized[sym_b]
            n = min(len(norm_a), len(norm_b))
            if n < 2:
                continue
            na = norm_a[-n:]
            nb = norm_b[-n:]

            spread = na - nb
            ssd = float(np.sum(spread ** 2))
            spread_mean = float(np.mean(spread))
            spread_std = float(np.std(spread, ddof=1)) if n > 1 else 0.0
            crossings = self._zero_crossings(spread, spread_mean)

            if crossings < self.min_zero_crossings:
                continue

            formed.append(
                DistancePair(
                    symbol_a=sym_a,
                    symbol_b=sym_b,
                    ssd=ssd,
                    spread_mean=spread_mean,
                    spread_std=spread_std,
                    zero_crossings=crossings,
                    sector=sec_a if sec_a == sec_b else None,
                    min_a=min_a,
                    max_a=max_a,
                    min_b=min_b,
                    max_b=max_b,
                    sample_size=n,
                )
            )

        formed.sort(key=lambda p: p.ssd)
        selected = formed[: self.top_n]
        self.logger.info(
            "Distance formation: %d/%d candidate pairs retained (top_n=%d)",
            len(selected),
            len(formed),
            self.top_n,
        )
        return selected

    # ------------------------------------------------------------------ #
    # Signalling
    # ------------------------------------------------------------------ #
    def generate_signal(
        self,
        pair: DistancePair,
        price_a: float,
        price_b: float,
        in_position: int = 0,
    ) -> int:
        """Return a target position for the spread.

        Args:
            pair: a formed DistancePair.
            price_a, price_b: latest raw prices.
            in_position: current spread position (+1 long, -1 short, 0 flat).

        Returns:
            +1 to be long the spread (long A / short B),
            -1 to be short the spread (short A / long B),
             0 to be flat (mean reversion reached / no entry).
        """
        z = pair.z_score(price_a, price_b)

        # Exit: spread reverted across its mean.
        if in_position == 1 and z >= 0.0:
            return 0
        if in_position == -1 and z <= 0.0:
            return 0
        if in_position != 0:
            return in_position  # hold

        # Entry on band breach.
        if z >= self.entry_threshold:
            return -1  # spread rich -> short A, long B
        if z <= -self.entry_threshold:
            return 1   # spread cheap -> long A, short B
        return 0


__all__ = ["DistanceApproachEngine", "DistancePair"]
