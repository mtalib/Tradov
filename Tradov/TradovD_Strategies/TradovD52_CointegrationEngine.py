#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies.TradovD50_PairDiscovery
Module: TradovD52_CointegrationEngine.py
Purpose: Engle-Granger and Johansen cointegration testing

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Performs cointegration tests on price series pairs using:
      - Engle-Granger two-step (statsmodels coint)
      - Johansen trace/eigen test (statsmodels vecm or manual)
    Returns CointegrationResult with hedge ratio, half-life estimate,
    and spread statistics.
"""

from __future__ import annotations

import logging
from datetime import datetime, UTC
from typing import Any

import numpy as np

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    CointegrationMethod,
    CointegrationResult,
)


class CointegrationEngine:
    def __init__(
        self,
        significance_level: float = 0.05,
        min_half_life: float = 1.0,
        max_half_life: float = 30.0,
        logger: logging.Logger | None = None,
    ):
        self.significance_level = significance_level
        self.min_half_life = min_half_life
        self.max_half_life = max_half_life
        self.logger = logger or TradovLogger.get_logger("CointegrationEngine")

    def test(
        self,
        series_a: np.ndarray,
        series_b: np.ndarray,
        method: CointegrationMethod = CointegrationMethod.BOTH,
        pair_key: str = "",
    ) -> CointegrationResult:
        if method == CointegrationMethod.ENGLE_GRANGER:
            return self._engle_granger(series_a, series_b, pair_key)
        if method == CointegrationMethod.JOHANSEN:
            return self._johansen(series_a, series_b, pair_key)
        eg = self._engle_granger(series_a, series_b, pair_key)
        if eg.is_cointegrated:
            return eg
        return self._johansen(series_a, series_b, pair_key)

    def _engle_granger(
        self, series_a: np.ndarray, series_b: np.ndarray, pair_key: str
    ) -> CointegrationResult:
        try:
            from statsmodels.tsa.stattools import coint, OLS
            from statsmodels.tools.tools import add_constant

            score, p_value, critical_values = coint(series_a, series_b)
            X = add_constant(series_b)
            model = OLS(series_a, X).fit()
            hedge_ratio = float(model.params[1])
            spread = series_a - hedge_ratio * series_b
            half_life = self._estimate_half_life(spread)
            spread_mean = float(np.mean(spread))
            spread_std = float(np.std(spread, ddof=1))
            is_cointegrated = p_value <= self.significance_level

            return CointegrationResult(
                pair_key=pair_key,
                is_cointegrated=is_cointegrated,
                p_value=float(p_value),
                hedge_ratio=hedge_ratio,
                half_life=half_life,
                spread_mean=spread_mean,
                spread_std=spread_std,
                method=CointegrationMethod.ENGLE_GRANGER,
                test_statistic=float(score),
                critical_value=float(critical_values[0]),
                sample_size=len(series_a),
            )
        except Exception as e:
            self.logger.warning("Engle-Granger test failed for %s: %s", pair_key, e)
            return CointegrationResult(
                pair_key=pair_key,
                is_cointegrated=False,
                p_value=1.0,
                hedge_ratio=1.0,
                half_life=0.0,
                spread_mean=0.0,
                spread_std=1.0,
                method=CointegrationMethod.ENGLE_GRANGER,
                test_statistic=0.0,
                critical_value=0.0,
                sample_size=len(series_a),
            )

    def _johansen(
        self, series_a: np.ndarray, series_b: np.ndarray, pair_key: str
    ) -> CointegrationResult:
        try:
            from statsmodels.tsa.vector_ar.vecm import coint_johansen

            data = np.column_stack([series_a, series_b])
            result = coint_johansen(data, det_order=0, k_ar_diff=1)
            trace_stat = result.lr1[0]
            trace_cv = result.cvt[0, 1]
            is_cointegrated = trace_stat > trace_cv
            if is_cointegrated and result.evec is not None and result.evec.shape[1] > 0:
                ev = result.evec[:, 0]
                hedge_ratio = -ev[1] / ev[0] if abs(ev[0]) > 1e-10 else 1.0
            else:
                hedge_ratio = 1.0
            spread = series_a - hedge_ratio * series_b
            half_life = self._estimate_half_life(spread)
            spread_mean = float(np.mean(spread))
            spread_std = float(np.std(spread, ddof=1))
            p_value = 0.01 if is_cointegrated else 0.5

            return CointegrationResult(
                pair_key=pair_key,
                is_cointegrated=is_cointegrated,
                p_value=float(p_value),
                hedge_ratio=float(hedge_ratio),
                half_life=half_life,
                spread_mean=spread_mean,
                spread_std=spread_std,
                method=CointegrationMethod.JOHANSEN,
                test_statistic=float(trace_stat),
                critical_value=float(trace_cv),
                sample_size=len(series_a),
            )
        except Exception as e:
            self.logger.warning("Johansen test failed for %s: %s", pair_key, e)
            return CointegrationResult(
                pair_key=pair_key,
                is_cointegrated=False,
                p_value=1.0,
                hedge_ratio=1.0,
                half_life=0.0,
                spread_mean=0.0,
                spread_std=1.0,
                method=CointegrationMethod.JOHANSEN,
                test_statistic=0.0,
                critical_value=0.0,
                sample_size=len(series_a),
            )

    @staticmethod
    def _estimate_half_life(spread: np.ndarray) -> float:
        if len(spread) < 2:
            return 0.0
        lag = spread[:-1]
        diff = np.diff(spread)
        lag_with_const = np.column_stack([lag, np.ones(len(lag))])
        try:
            beta = np.linalg.lstsq(lag_with_const, diff, rcond=None)[0]
            lam = beta[0]
            if lam >= 0:
                return float("inf")
            half_life = -np.log(2) / lam
            return float(half_life)
        except Exception:
            return 0.0

    def rolling_test(
        self,
        series_a: np.ndarray,
        series_b: np.ndarray,
        window: int = 60,
        pair_key: str = "",
    ) -> list[CointegrationResult]:
        n = min(len(series_a), len(series_b))
        if n < window:
            return []
        results: list[CointegrationResult] = []
        step = max(1, window // 4)
        for start in range(0, n - window + 1, step):
            end = start + window
            result = self._engle_granger(
                series_a[start:end], series_b[start:end], pair_key
            )
            results.append(result)
        return results


__all__ = ["CointegrationEngine"]
