#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies.TradovD50_PairDiscovery
Module: TradovD53_OUProcessFitter.py
Purpose: Ornstein-Uhlenbeck process fitting for pair spreads

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Fits an OU process to the spread of a cointegrated pair using
    maximum-likelihood estimation (via ArbitrageLab when available,
    fallback to manual MLE). Provides half-life, mean-reversion
    speed, and optimal entry/exit thresholds (Avellaneda-Lee).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger


@dataclass
class OUFitResult:
    mu: float
    theta: float
    sigma: float
    half_life: float
    entry_threshold: float
    exit_threshold: float
    stop_threshold: float
    score: float
    method: str
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class OUProcessFitter:
    def __init__(
        self,
        dt: float = 1.0 / 252,
        entry_z: float = 2.0,
        exit_z: float = 0.5,
        stop_z: float = 3.5,
        max_half_life: float = 30.0,
        logger: logging.Logger | None = None,
    ):
        self.dt = dt
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.stop_z = stop_z
        self.max_half_life = max_half_life
        self.logger = logger or TradovLogger.get_logger("OUProcessFitter")

    def fit(self, spread: np.ndarray) -> OUFitResult:
        try:
            return self._fit_arbitragelab(spread)
        except Exception as e:
            self.logger.debug(
                "ArbitrageLab OU fit failed, falling back to MLE: %s", e
            )
            return self._fit_mle(spread)

    def _fit_arbitragelab(self, spread: np.ndarray) -> OUFitResult:
        from arbitragelab.fit.ou_fit import OUMLE

        ou = OUMLE(spread)
        params = ou.fit()
        mu = float(params.get("mu", np.mean(spread)))
        theta = float(params.get("theta", 0.1))
        sigma = float(params.get("sigma", np.std(spread, ddof=1)))
        half_life = np.log(2) / theta if theta > 0 else float("inf")
        return self._build_result(mu, theta, sigma, half_life, spread, "arbitragelab")

    def _fit_mle(self, spread: np.ndarray) -> OUFitResult:
        n = len(spread)
        if n < 3:
            return OUFitResult(
                mu=float(np.mean(spread)),
                theta=0.0,
                sigma=float(np.std(spread, ddof=1)),
                half_life=float("inf"),
                entry_threshold=0.0,
                exit_threshold=0.0,
                stop_threshold=0.0,
                score=0.0,
                method="mle",
            )

        S_x = np.sum(spread[:-1])
        S_y = np.sum(spread[1:])
        S_xx = np.sum(spread[:-1] ** 2)
        S_xy = np.sum(spread[:-1] * spread[1:])
        n_eff = n - 1

        mu = (S_y * S_xx - S_x * S_xy) / (n_eff * S_xx - S_x ** 2 + 1e-12)
        theta = -np.log(
            (S_xy - mu * S_x - mu * S_y + n_eff * mu ** 2)
            / (S_xx - 2 * mu * S_x + n_eff * mu ** 2 + 1e-12)
        ) / self.dt if (S_xx - 2 * mu * S_x + n_eff * mu ** 2) > 0 else 0.0

        theta = max(theta, 1e-8)
        sigma2 = (
            np.sum((spread[1:] - spread[:-1] * np.exp(-theta * self.dt) - mu * (1 - np.exp(-theta * self.dt))) ** 2)
            / (n_eff * (1 - np.exp(-2 * theta * self.dt)) / (2 * theta) + 1e-12)
        )
        sigma = np.sqrt(max(sigma2, 1e-12))
        half_life = np.log(2) / theta if theta > 0 else float("inf")
        return self._build_result(mu, theta, sigma, half_life, spread, "mle")

    def _build_result(
        self,
        mu: float,
        theta: float,
        sigma: float,
        half_life: float,
        spread: np.ndarray,
        method: str,
    ) -> OUFitResult:
        sigma_eq = sigma / np.sqrt(2 * theta) if theta > 0 else float(np.std(spread, ddof=1))
        entry_threshold = mu + self.entry_z * sigma_eq
        exit_threshold = mu + self.exit_z * sigma_eq
        stop_threshold = mu + self.stop_z * sigma_eq
        score = self._score_fit(spread, mu, theta, sigma)
        return OUFitResult(
            mu=mu,
            theta=theta,
            sigma=sigma,
            half_life=min(half_life, self.max_half_life * 2),
            entry_threshold=entry_threshold,
            exit_threshold=exit_threshold,
            stop_threshold=stop_threshold,
            score=score,
            method=method,
        )

    @staticmethod
    def _score_fit(
        spread: np.ndarray, mu: float, theta: float, sigma: float
    ) -> float:
        if theta <= 0 or sigma <= 0:
            return 0.0
        n = len(spread)
        residuals = np.diff(spread) - theta * (mu - spread[:-1]) * (1.0 / 252)
        ll = -0.5 * n * np.log(2 * np.pi * sigma ** 2) - 0.5 * np.sum(residuals ** 2) / (sigma ** 2 + 1e-12)
        k = 3
        aic = 2 * k - 2 * ll
        return float(-aic)

    def optimal_thresholds(
        self,
        spread: np.ndarray,
        entry_z: float | None = None,
        exit_z: float | None = None,
        stop_z: float | None = None,
    ) -> tuple[float, float, float]:
        fit = self.fit(spread)
        sigma_eq = fit.sigma / np.sqrt(2 * fit.theta) if fit.theta > 0 else float(np.std(spread, ddof=1))
        ez = entry_z or self.entry_z
        xz = exit_z or self.exit_z
        sz = stop_z or self.stop_z
        return (
            fit.mu + ez * sigma_eq,
            fit.mu + xz * sigma_eq,
            fit.mu + sz * sigma_eq,
        )


__all__ = ["OUProcessFitter", "OUFitResult"]
