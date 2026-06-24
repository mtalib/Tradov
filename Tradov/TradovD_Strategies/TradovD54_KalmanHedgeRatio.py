#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies.TradovD50_PairDiscovery
Module: TradovD54_KalmanHedgeRatio.py
Purpose: Dynamic hedge ratio estimation via Kalman filter

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Estimates a time-varying hedge ratio using a Kalman filter with
    a random-walk state model. Falls back to rolling OLS if pykalman
    is unavailable. Provides spread and z-score series for signal
    generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger


@dataclass
class KalmanResult:
    hedge_ratios: np.ndarray
    spreads: np.ndarray
    z_scores: np.ndarray
    spread_mean: float
    spread_std: float
    state_covariances: np.ndarray | None = None
    method: str = "kalman"

    def latest_ratio(self) -> float:
        return float(self.hedge_ratios[-1]) if len(self.hedge_ratios) > 0 else 1.0

    def latest_z(self) -> float:
        return float(self.z_scores[-1]) if len(self.z_scores) > 0 else 0.0


class KalmanHedgeRatio:
    def __init__(
        self,
        delta: float = 1e-4,
        obs_cov: float = 1e-3,
        initial_ratio: float = 1.0,
        lookback: int = 60,
        logger: logging.Logger | None = None,
    ):
        self.delta = delta
        self.obs_cov = obs_cov
        self.initial_ratio = initial_ratio
        self.lookback = lookback
        self.logger = logger or TradovLogger.get_logger("KalmanHedgeRatio")
        self._last_result: KalmanResult | None = None

    def fit(
        self, series_a: np.ndarray, series_b: np.ndarray
    ) -> KalmanResult:
        try:
            result = self._fit_pykalman(series_a, series_b)
            self._last_result = result
            return result
        except Exception as e:
            self.logger.debug(
                "pykalman fit failed, falling back to rolling OLS: %s", e
            )
            result = self._fit_rolling_ols(series_a, series_b)
            self._last_result = result
            return result

    def _fit_pykalman(
        self, series_a: np.ndarray, series_b: np.ndarray
    ) -> KalmanResult:
        from pykalman import KalmanFilter

        n = len(series_a)
        transition_matrix = np.eye(2)
        observation_matrix = np.vstack(
            [np.ones(n), series_b]
        ).T.reshape(n, 1, 2)

        kf = KalmanFilter(
            transition_matrices=transition_matrix,
            observation_matrices=observation_matrix,
            transition_covariance=self.delta * np.eye(2),
            observation_covariance=self.obs_cov,
            initial_state_mean=np.array([0.0, self.initial_ratio]),
            initial_state_covariance=np.eye(2),
        )

        state_means, state_covs = kf.filter(series_a)
        hedge_ratios = state_means[:, 1]
        intercepts = state_means[:, 0]
        spreads = series_a - intercepts - hedge_ratios * series_b

        return self._compute_spread_stats(
            hedge_ratios, spreads, state_covs, "kalman"
        )

    def _fit_rolling_ols(
        self, series_a: np.ndarray, series_b: np.ndarray
    ) -> KalmanResult:
        n = len(series_a)
        window = min(self.lookback, n)
        hedge_ratios = np.full(n, np.nan)
        spreads = np.full(n, np.nan)

        for i in range(window - 1, n):
            y = series_a[i - window + 1 : i + 1]
            x = series_b[i - window + 1 : i + 1]
            X = np.column_stack([np.ones(window), x])
            try:
                beta = np.linalg.lstsq(X, y, rcond=None)[0]
                hedge_ratios[i] = beta[1]
                spreads[i] = series_a[i] - beta[0] - beta[1] * series_b[i]
            except Exception:
                hedge_ratios[i] = 1.0
                spreads[i] = series_a[i] - series_b[i]

        valid = ~np.isnan(hedge_ratios)
        hr_clean = hedge_ratios[valid]
        sp_clean = spreads[valid]
        if len(hr_clean) < 2:
            hr_clean = np.array([1.0])
            sp_clean = np.array([0.0])

        full_ratios = np.where(valid, hedge_ratios, hr_clean[-1] if len(hr_clean) > 0 else 1.0)
        full_spreads = np.where(valid, spreads, sp_clean[-1] if len(sp_clean) > 0 else 0.0)

        return self._compute_spread_stats(full_ratios, full_spreads, None, "rolling_ols")

    def _compute_spread_stats(
        self,
        hedge_ratios: np.ndarray,
        spreads: np.ndarray,
        state_covs: np.ndarray | None,
        method: str,
    ) -> KalmanResult:
        spread_mean = float(np.mean(spreads))
        spread_std = float(np.std(spreads, ddof=1))
        if spread_std < 1e-10:
            spread_std = 1.0
        z_scores = (spreads - spread_mean) / spread_std

        return KalmanResult(
            hedge_ratios=hedge_ratios,
            spreads=spreads,
            z_scores=z_scores,
            spread_mean=spread_mean,
            spread_std=spread_std,
            state_covariances=state_covs,
            method=method,
        )

    def update_incremental(
        self,
        price_a: float,
        price_b: float,
        prev_ratio: float | None = None,
    ) -> tuple[float, float]:
        if self._last_result is None:
            ratio = prev_ratio or self.initial_ratio
        else:
            ratio = self._last_result.latest_ratio()

        spread = price_a - ratio * price_b
        if self._last_result is not None:
            mean = self._last_result.spread_mean
            std = self._last_result.spread_std
            if std > 1e-10:
                z = (spread - mean) / std
            else:
                z = 0.0
        else:
            z = 0.0

        return ratio, z

    @property
    def last_result(self) -> KalmanResult | None:
        return self._last_result


__all__ = ["KalmanHedgeRatio", "KalmanResult"]
