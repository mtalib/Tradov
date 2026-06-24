#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies.TradovD50_PairDiscovery
Module: TradovD51_PairScanner.py
Purpose: Universe scanner for cointegrated pairs with FDR correction

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Scans the symbol universe for cointegrated pairs using Engle-Granger
    and/or Johansen tests. Applies Benjamini-Hochberg FDR correction to
    control false discoveries. Runs on a weekly schedule (Saturday).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, UTC
from dataclasses import replace
from itertools import combinations
from typing import Any

import numpy as np
import pandas as pd

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    CointegrationMethod,
    CointegrationResult,
    PairDefinition,
    PairScanResult,
    PairStatus,
)
from Tradov.TradovU_Utilities.TradovU49_SymbolCatalog import (
    DEFAULT_PAIR_DEFINITIONS,
    PAIR_EQUITY_SECTORS,
    get_pair_universe,
)
from Tradov.TradovD_Strategies.TradovD52_CointegrationEngine import (
    CointegrationEngine,
)


class PairScanner:
    def __init__(
        self,
        price_history: pd.DataFrame | None = None,
        fdr_alpha: float = 0.05,
        fdr_method: str = "benjamini_hochberg",
        min_sample_size: int = 60,
        method: CointegrationMethod = CointegrationMethod.BOTH,
        use_ml_selection: bool = False,
        ml_selector: Any | None = None,
        account_size: float | None = None,
        logger: logging.Logger | None = None,
    ):
        self.price_history = price_history
        self.fdr_alpha = fdr_alpha
        self.fdr_method = fdr_method
        self.min_sample_size = min_sample_size
        self.method = method
        # When enabled, candidate pairs are drawn from ML clustering
        # (PCA + OPTICS/DBSCAN, D57) instead of the sector-based heuristic.
        self.use_ml_selection = use_ml_selection
        self._ml_selector = ml_selector
        self.account_size = float(account_size) if account_size is not None else None
        self.logger = logger or TradovLogger.get_logger("PairScanner")
        self.coint_engine = CointegrationEngine()
        self._pair_defs: dict[str, PairDefinition] = {}
        self._last_scan: PairScanResult | None = None
        self._build_default_pairs()

    @property
    def ml_selector(self) -> Any:
        """Lazily construct the ML pair selector (D57) on first use."""
        if self._ml_selector is None:
            from Tradov.TradovD_Strategies.TradovD57_MLPairSelector import (
                MLPairSelector,
            )
            self._ml_selector = MLPairSelector()
        return self._ml_selector

    def ml_candidate_pairs(
        self, prices: pd.DataFrame
    ) -> list[tuple[str, str]]:
        """Return ML-clustered candidate pairs for the given price frame.

        Pairs that the ML selector already accepts (clustered + Hurst /
        half-life / mean-crossing filtered) are returned as ``(a, b)`` tuples
        ready to feed ``scan``.
        """
        try:
            return self.ml_selector.get_candidate_tuples(prices)
        except Exception as e:
            self.logger.warning("ML candidate selection failed: %s", e)
            return []

    def _build_default_pairs(self) -> None:
        for sym_a, sym_b, sector, ptype in DEFAULT_PAIR_DEFINITIONS:
            pair = PairDefinition(
                symbol_a=sym_a,
                symbol_b=sym_b,
                sector=sector,
                pair_type=ptype,
                status=PairStatus.CANDIDATE,
            )
            self._pair_defs[pair.key] = pair

    def add_pair(self, pair: PairDefinition) -> None:
        self._pair_defs[pair.key] = pair

    def remove_pair(self, pair_key: str) -> None:
        self._pair_defs.pop(pair_key, None)

    def get_pair_definitions(self) -> dict[str, PairDefinition]:
        return dict(self._pair_defs)

    def scan(
        self,
        price_history: pd.DataFrame | None = None,
        candidate_pairs: list[tuple[str, str]] | None = None,
    ) -> PairScanResult:
        prices = price_history if price_history is not None else self.price_history
        if prices is None or prices.empty:
            self.logger.warning("No price history available for scanning")
            empty_result = PairScanResult()
            empty_result.build_decision_context()
            return empty_result

        if candidate_pairs is None:
            if self.use_ml_selection:
                candidate_pairs = self.ml_candidate_pairs(prices)
                self.logger.info(
                    "ML selection produced %d candidate pairs", len(candidate_pairs)
                )
                # Fall back to the sector heuristic if clustering finds nothing.
                if not candidate_pairs:
                    candidate_pairs = self._generate_candidates(prices)
            else:
                candidate_pairs = self._generate_candidates(prices)

        self.logger.info(
            "Scanning %d candidate pairs across %d symbols",
            len(candidate_pairs),
            len(prices.columns),
        )

        raw_results: list[CointegrationResult] = []
        for sym_a, sym_b in candidate_pairs:
            if sym_a not in prices.columns or sym_b not in prices.columns:
                continue
            series_a = prices[sym_a].dropna()
            series_b = prices[sym_b].dropna()
            min_len = min(len(series_a), len(series_b))
            if min_len < self.min_sample_size:
                continue
            series_a = series_a.iloc[-min_len:]
            series_b = series_b.iloc[-min_len:]

            result = self.coint_engine.test(
                series_a.values,
                series_b.values,
                method=self.method,
                pair_key=f"{sym_a}/{sym_b}",
            )
            result.metadata = dict(result.metadata or {})
            pair_def = self._pair_defs.get(result.pair_key)
            if pair_def is not None:
                price_a = float(series_a.iloc[-1])
                price_b = float(series_b.iloc[-1])
                notional_base = self.account_size * pair_def.size_pct if self.account_size else 0.0
                if notional_base <= 0.0:
                    notional_base = max(price_a + price_b, 1.0) * 100.0
                qty_a = max(1, int(notional_base / max(price_a, 1e-6)))
                qty_b = max(1, int(qty_a * max(result.hedge_ratio, 1e-6) * price_a / max(price_b, 1e-6)))
                entry_cost_dollars = abs(qty_a * price_a) + abs(qty_b * price_b)
                max_loss_dollars = entry_cost_dollars
                result.metadata.update({
                    "symbol_a": sym_a,
                    "symbol_b": sym_b,
                    "price_a": price_a,
                    "price_b": price_b,
                    "estimated_notional_dollars": notional_base,
                    "entry_cost_dollars": entry_cost_dollars,
                    "cost_dollars": entry_cost_dollars,
                    "estimated_cost_dollars": entry_cost_dollars,
                    "funds_held_dollars": max_loss_dollars,
                    "cash_held_dollars": max_loss_dollars,
                    "buying_power_held": max_loss_dollars,
                    "max_loss_dollars": max_loss_dollars,
                    "quantity_a": qty_a,
                    "quantity_b": qty_b,
                    "pair_size_pct": pair_def.size_pct,
                })
            raw_results.append(result)

        validated = self._apply_fdr(raw_results)
        ranked = self._rank_results(validated)
        for result in validated:
            pair_key = result.pair_key
            if pair_key in self._pair_defs:
                self._pair_defs[pair_key] = replace(
                    self._pair_defs[pair_key],
                    status=PairStatus.VALIDATED if result.is_tradeable else PairStatus.EXCLUDED,
                )

        scan_result = PairScanResult(
            total_candidates=len(candidate_pairs),
            validated_pairs=validated,
            ranked_pairs=ranked,
            fdr_method=self.fdr_method,
            fdr_alpha=self.fdr_alpha,
        )
        scan_result.build_decision_context()
        self._last_scan = scan_result
        self.logger.info(
            "Scan complete: %d/%d pairs tradeable",
            scan_result.tradeable_count,
            len(candidate_pairs),
        )
        return scan_result

    def _rank_results(self, results: list[CointegrationResult]) -> list[CointegrationResult]:
        if not results:
            return []

        ranked_results = list(results)
        for result in ranked_results:
            p_component = -math.log10(max(result.p_value, 1e-12))
            half_life_component = 1.0 / (1.0 + max(result.half_life, 0.0))
            spread_component = 1.0 / (1.0 + max(result.spread_std, 0.0))
            sample_component = min(result.sample_size / 252.0, 1.0)
            ranking_score = (
                0.45 * p_component
                + 0.25 * half_life_component
                + 0.20 * spread_component
                + 0.10 * sample_component
            )
            result.ranking_score = float(ranking_score)
            result.ranking_components = {
                "p_value": float(p_component),
                "half_life": float(half_life_component),
                "spread_std": float(spread_component),
                "sample_size": float(sample_component),
            }
            result.metadata["ranking_score"] = result.ranking_score

        ranked_results.sort(key=lambda r: r.ranking_score, reverse=True)
        for idx, result in enumerate(ranked_results, start=1):
            result.metadata["rank"] = idx
        return ranked_results

    def _generate_candidates(self, prices: pd.DataFrame) -> list[tuple[str, str]]:
        universe = get_pair_universe()
        available = [s for s in prices.columns if s in universe]
        candidates = []
        for sym_a, sym_b in combinations(sorted(available), 2):
            sector_a = self._get_sector(sym_a)
            sector_b = self._get_sector(sym_b)
            if sector_a and sector_b and sector_a == sector_b:
                candidates.append((sym_a, sym_b))
        for sym_a, sym_b in combinations(sorted(available), 2):
            if (sym_a, sym_b) not in candidates:
                sector_a = self._get_sector(sym_a)
                sector_b = self._get_sector(sym_b)
                if sector_a and sector_b and sector_a != sector_b:
                    continue
                candidates.append((sym_a, sym_b))
        return candidates

    def _get_sector(self, symbol: str) -> str | None:
        for sector, symbols in PAIR_EQUITY_SECTORS.items():
            if symbol in symbols:
                return sector
        return None

    def _apply_fdr(self, results: list[CointegrationResult]) -> list[CointegrationResult]:
        if not results:
            return []
        sorted_results = sorted(results, key=lambda r: r.p_value)
        m = len(sorted_results)
        validated: list[CointegrationResult] = []
        for i, result in enumerate(sorted_results):
            if self.fdr_method == "benjamini_hochberg":
                threshold = (i + 1) / m * self.fdr_alpha
            elif self.fdr_method == "bonferroni":
                threshold = self.fdr_alpha / m
            else:
                threshold = self.fdr_alpha
            if result.p_value <= threshold:
                validated.append(result)
            elif self.fdr_method == "benjamini_hochberg":
                break
        return validated

    @property
    def last_scan(self) -> PairScanResult | None:
        return self._last_scan


__all__ = ["PairScanner"]
