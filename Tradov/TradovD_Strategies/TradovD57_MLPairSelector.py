#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies.TradovD50_PairDiscovery
Module: TradovD57_MLPairSelector.py
Purpose: ML-based pairs selection (PCA + OPTICS/DBSCAN clustering)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-15 Time: 00:00:00

Module Description:
    Implements the ML-based pairs selection workflow of
    Sarmento & Horta (2020), "A Machine Learning based Pairs Trading
    Investment Strategy", over a stock/ETF universe.

    Workflow:
      1. Dimensionality reduction: PCA on standardised returns to a compact
         feature vector per security (number of components empirically capped
         at 15 to avoid the curse of dimensionality).
      2. Unsupervised clustering: OPTICS (default) or DBSCAN groups securities
         that share latent risk factors. These methods do not require the
         number of clusters in advance and may leave securities unclustered.
      3. Candidate generation: form all within-cluster pairs.
      4. Spread filtering, keeping a pair only if its OLS spread satisfies:
           - mean reversion:   Hurst exponent H < 0.5,
           - tradeable speed:  1 day < half-life < 252 days,
           - liquidity:        at least ~1 mean-crossing per month.

    The output is a ranked list of candidate pairs intended to feed the
    existing cointegration scanner (D51/D52) / PairTradingStrategy (D42),
    so this module is a *selection* tool rather than a trading strategy.
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
class MLPairCandidate:
    """A clustered, spread-filtered candidate pair."""

    symbol_a: str
    symbol_b: str
    cluster_id: int
    hurst: float
    half_life: float
    mean_crossings: int
    hedge_ratio: float
    spread_std: float
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.symbol_a}/{self.symbol_b}"

    def as_tuple(self) -> tuple[str, str]:
        return (self.symbol_a, self.symbol_b)


class MLPairSelector:
    """PCA + density clustering pairs selector with spread-quality filters."""

    def __init__(
        self,
        n_components: int = 5,
        min_samples: int = 3,
        algorithm: str = "optics",
        max_hurst: float = 0.5,
        min_half_life: float = 1.0,
        max_half_life: float = 252.0,
        min_monthly_crossings: float = 1.0,
        trading_days_per_month: int = 21,
        dbscan_eps: float = 0.5,
        logger: logging.Logger | None = None,
    ):
        """
        Args:
            n_components: PCA feature dimensions (empirically capped at 15).
            min_samples: min cluster size for OPTICS/DBSCAN.
            algorithm: "optics" or "dbscan".
            max_hurst: keep pairs with Hurst exponent strictly below this.
            min_half_life / max_half_life: tradeable half-life band, in days.
            min_monthly_crossings: required mean crossings per month.
            trading_days_per_month: month length used for the crossing rule.
            dbscan_eps: neighbourhood radius for DBSCAN.
            logger: optional logger.
        """
        self.n_components = min(n_components, 15)
        self.min_samples = min_samples
        self.algorithm = algorithm.lower()
        self.max_hurst = max_hurst
        self.min_half_life = min_half_life
        self.max_half_life = max_half_life
        self.min_monthly_crossings = min_monthly_crossings
        self.trading_days_per_month = trading_days_per_month
        self.dbscan_eps = dbscan_eps
        self.logger = logger or TradovLogger.get_logger("MLPairSelector")

    # ------------------------------------------------------------------ #
    # 1-2. Dimensionality reduction + clustering
    # ------------------------------------------------------------------ #
    def cluster(self, returns: pd.DataFrame) -> dict[int, list[str]]:
        """Cluster securities by PCA feature vectors.

        Args:
            returns: daily returns frame, one column per security.

        Returns:
            Mapping cluster_id -> list of symbols. Unclustered securities
            (label -1) are excluded.
        """
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler

        clean = returns.dropna(axis=1, how="any")
        symbols = list(clean.columns)
        if len(symbols) < self.min_samples:
            self.logger.warning(
                "Too few symbols (%d) to cluster", len(symbols)
            )
            return {}

        # Each security is a sample; its return time series are the raw
        # features that PCA compresses into a feature vector.
        feature_matrix = clean.values.T  # (n_securities, n_days)
        scaled = StandardScaler().fit_transform(feature_matrix)

        n_comp = min(self.n_components, scaled.shape[0], scaled.shape[1])
        components = PCA(n_components=n_comp).fit_transform(scaled)

        labels = self._run_clusterer(components)

        clusters: dict[int, list[str]] = {}
        for sym, label in zip(symbols, labels, strict=False):
            if label == -1:  # noise / unclustered
                continue
            clusters.setdefault(int(label), []).append(sym)

        self.logger.info(
            "Clustering (%s): %d clusters from %d securities",
            self.algorithm,
            len(clusters),
            len(symbols),
        )
        return clusters

    def _run_clusterer(self, components: np.ndarray) -> np.ndarray:
        if self.algorithm == "dbscan":
            from sklearn.cluster import DBSCAN

            return DBSCAN(
                eps=self.dbscan_eps, min_samples=self.min_samples
            ).fit_predict(components)

        from sklearn.cluster import OPTICS

        # OPTICS needs at least min_samples + 1 points to run.
        if components.shape[0] <= self.min_samples:
            return np.full(components.shape[0], -1)
        return OPTICS(min_samples=self.min_samples).fit_predict(components)

    # ------------------------------------------------------------------ #
    # 4. Spread-quality metrics
    # ------------------------------------------------------------------ #
    @staticmethod
    def hurst_exponent(series: np.ndarray, max_lag: int = 20) -> float:
        """Estimate the Hurst exponent via the rescaled-lag variance method.

        H < 0.5 indicates mean reversion, H ~ 0.5 a random walk, H > 0.5
        a trending series.
        """
        n = len(series)
        if n < max_lag + 2:
            max_lag = max(2, n - 2)
        lags = range(2, max_lag)
        tau = []
        valid_lags = []
        for lag in lags:
            diff = series[lag:] - series[:-lag]
            std = np.std(diff)
            if std > 1e-12:
                tau.append(std)
                valid_lags.append(lag)
        if len(valid_lags) < 2:
            return 0.5
        poly = np.polyfit(np.log(valid_lags), np.log(tau), 1)
        return float(poly[0])

    @staticmethod
    def half_life(spread: np.ndarray) -> float:
        """OU half-life of a spread via an AR(1) regression of the change."""
        if len(spread) < 2:
            return float("inf")
        lag = spread[:-1]
        diff = np.diff(spread)
        A = np.column_stack([lag, np.ones(len(lag))])
        try:
            beta, *_ = np.linalg.lstsq(A, diff, rcond=None)
        except np.linalg.LinAlgError:
            return float("inf")
        lam = beta[0]
        if lam >= 0:
            return float("inf")
        return float(-np.log(2) / lam)

    @staticmethod
    def mean_crossings(spread: np.ndarray) -> int:
        centered = spread - np.mean(spread)
        signs = np.sign(centered)
        nonzero = signs[signs != 0]
        if len(nonzero) < 2:
            return 0
        return int(np.sum(nonzero[1:] != nonzero[:-1]))

    @staticmethod
    def _spread(series_a: np.ndarray, series_b: np.ndarray) -> tuple[np.ndarray, float]:
        """OLS spread a - beta*b and the hedge ratio beta (no intercept term
        in the spread, but estimated with an intercept)."""
        A = np.column_stack([np.ones(len(series_b)), series_b])
        beta, *_ = np.linalg.lstsq(A, series_a, rcond=None)
        hedge_ratio = float(beta[1])
        spread = series_a - hedge_ratio * series_b
        return spread, hedge_ratio

    # ------------------------------------------------------------------ #
    # 3-4. Candidate generation + filtering
    # ------------------------------------------------------------------ #
    def select_pairs(
        self,
        prices: pd.DataFrame,
        returns: pd.DataFrame | None = None,
    ) -> list[MLPairCandidate]:
        """Cluster, form within-cluster pairs, and filter by spread quality.

        Args:
            prices: price frame used to build spreads (one column per symbol).
            returns: returns frame used for clustering; if None it is derived
                from ``prices`` via pct_change.

        Returns:
            Ranked list of MLPairCandidate passing all spread filters.
        """
        if prices is None or prices.empty or len(prices.columns) < 2:
            return []
        if returns is None:
            returns = prices.pct_change().dropna(how="all")

        clusters = self.cluster(returns)
        candidates: list[MLPairCandidate] = []
        monthly_required = self.min_monthly_crossings

        for cluster_id, symbols in clusters.items():
            for sym_a, sym_b in combinations(sorted(symbols), 2):
                if sym_a not in prices.columns or sym_b not in prices.columns:
                    continue
                pa = prices[sym_a].dropna()
                pb = prices[sym_b].dropna()
                idx = pa.index.intersection(pb.index)
                if len(idx) < 30:
                    continue
                a = pa.loc[idx].values.astype(float)
                b = pb.loc[idx].values.astype(float)

                spread, hedge_ratio = self._spread(a, b)
                hurst = self.hurst_exponent(spread)
                if hurst >= self.max_hurst:
                    continue

                hl = self.half_life(spread)
                if not (self.min_half_life < hl < self.max_half_life):
                    continue

                crossings = self.mean_crossings(spread)
                months = len(spread) / self.trading_days_per_month
                if months > 0 and (crossings / months) < monthly_required:
                    continue

                spread_std = float(np.std(spread, ddof=1))
                # Lower Hurst and shorter half-life are both more desirable.
                score = (0.5 - hurst) + 1.0 / (1.0 + hl)
                candidates.append(
                    MLPairCandidate(
                        symbol_a=sym_a,
                        symbol_b=sym_b,
                        cluster_id=cluster_id,
                        hurst=hurst,
                        half_life=hl,
                        mean_crossings=crossings,
                        hedge_ratio=hedge_ratio,
                        spread_std=spread_std,
                        score=float(score),
                    )
                )

        candidates.sort(key=lambda c: c.score, reverse=True)
        self.logger.info(
            "ML pair selection: %d candidates passed filters across %d clusters",
            len(candidates),
            len(clusters),
        )
        return candidates

    def get_candidate_tuples(
        self, prices: pd.DataFrame, returns: pd.DataFrame | None = None
    ) -> list[tuple[str, str]]:
        """Convenience: pairs as (sym_a, sym_b) tuples for the scanner."""
        return [c.as_tuple() for c in self.select_pairs(prices, returns)]


__all__ = ["MLPairSelector", "MLPairCandidate"]
