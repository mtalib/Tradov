#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovD_Strategies.TradovD50_PairDiscovery
Module: TradovD56_PCAEngine.py
Purpose: PCA / eigenportfolio statistical arbitrage (Avellaneda-Lee)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Implements the PCA approach to statistical arbitrage from
    Avellaneda & Lee (2010), "Statistical Arbitrage in the U.S.
    Equities Market", applied to a universe of stocks/ETFs.

    Pipeline:
      1. Standardise daily returns:  Y_ik = (R_ik - mean_i) / std_i.
      2. Build the empirical correlation matrix over a (default 252-day)
         estimation window and eigen-decompose it.
      3. Form eigenportfolios: weights Q_i^(j) = v_i^(j) / std_i, and
         eigenportfolio returns F_jk = sum_i Q_i^(j) R_ik.
      4. Regress each stock's returns on the top-m eigenportfolio (factor)
         returns over a shorter (default 60-day) residual window; the
         residual is the idiosyncratic return.
      5. Model the cumulative residual X_i(t) as a mean-reverting AR(1) /
         Ornstein-Uhlenbeck process and compute the s-score
         s_i = (X_i - m_i) / sigma_eq,i.
      6. Generate market-neutral long/short single-name signals from the
         s-score using Avellaneda-Lee cut-offs.

    Signal rules (defaults from the paper):
      open  long  if s < -sbo   (1.25)
      close long  if s > -sbc   (0.75)
      open  short if s > +sso   (1.25)
      close short if s < +ssc   (0.50)
    A fast-mean-reversion filter (kappa > 252/30 ~= 8.4) discards residuals
    that revert too slowly to be tradeable.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger


@dataclass
class SScore:
    """Per-symbol s-score and the OU parameters it was derived from."""

    symbol: str
    s_score: float
    kappa: float          # mean-reversion speed (annualised)
    m: float              # long-run mean of cumulative residual
    sigma_eq: float       # equilibrium std of the OU process
    fast_reverting: bool  # kappa above the tradeability threshold
    target: int = 0       # +1 long, -1 short, 0 flat (after threshold rules)


@dataclass
class PCAResult:
    """Output of one PCA scoring pass over the universe."""

    s_scores: dict[str, SScore] = field(default_factory=dict)
    target_weights: dict[str, int] = field(default_factory=dict)
    n_components: int = 0
    eigen_explained: float = 0.0
    corr_window: int = 0
    residual_window: int = 0

    def open_longs(self) -> list[str]:
        return [s for s, t in self.target_weights.items() if t > 0]

    def open_shorts(self) -> list[str]:
        return [s for s, t in self.target_weights.items() if t < 0]


class PCAEigenPortfolioEngine:
    """Avellaneda-Lee PCA statistical-arbitrage signal engine."""

    def __init__(
        self,
        kappa_min: float = 252.0 / 30.0,   # ~8.4: reversion time < ~1.5 months
        corr_window: int = 252,
        residual_window: int = 60,
        sbo: float = 1.25,
        sso: float = 1.25,
        sbc: float = 0.75,
        ssc: float = 0.50,
        n_components: int | None = None,
        explained_variance: float = 0.55,
        logger: logging.Logger | None = None,
    ):
        """
        Args:
            kappa_min: minimum annualised mean-reversion speed to trade.
            corr_window: lookback (days) for the correlation matrix / PCA.
            residual_window: lookback (days) for factor regression + OU fit.
            sbo, sso, sbc, ssc: s-score cut-offs for open/close long/short.
            n_components: fixed number of eigenportfolios; if None it is
                chosen to reach ``explained_variance`` (capped at 15).
            explained_variance: target cumulative variance when auto-selecting
                the number of components.
            logger: optional logger.
        """
        self.kappa_min = kappa_min
        self.corr_window = corr_window
        self.residual_window = residual_window
        self.sbo = sbo
        self.sso = sso
        self.sbc = sbc
        self.ssc = ssc
        self.n_components = n_components
        self.explained_variance = explained_variance
        self.logger = logger or TradovLogger.get_logger("PCAEigenPortfolioEngine")

    # ------------------------------------------------------------------ #
    # Building blocks
    # ------------------------------------------------------------------ #
    @staticmethod
    def standardize_data(returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
        """Standardise returns to zero mean / unit variance per column.

        Returns the standardised frame and the per-symbol std (needed to
        scale eigenvector loadings into eigenportfolio weights).
        """
        std = returns.std(ddof=1).replace(0.0, np.nan)
        standardized = (returns - returns.mean()) / std
        return standardized.fillna(0.0), std.fillna(0.0)

    def _select_n_components(self, eigenvalues: np.ndarray) -> int:
        if self.n_components is not None:
            return max(1, min(self.n_components, len(eigenvalues)))
        total = float(np.sum(eigenvalues))
        if total <= 0:
            return 1
        cumulative = np.cumsum(eigenvalues) / total
        # +1 because searchsorted returns the insertion index.
        k = int(np.searchsorted(cumulative, self.explained_variance) + 1)
        return max(1, min(k, 15, len(eigenvalues)))

    def get_factor_weights(self, returns: pd.DataFrame) -> pd.DataFrame:
        """Eigenportfolio weight matrix (factors x symbols).

        Weights are Q_i^(j) = v_i^(j) / sigma_i where v^(j) is the j-th
        eigenvector of the correlation matrix.
        """
        standardized, std = self.standardize_data(returns)
        corr = np.corrcoef(standardized.values, rowvar=False)
        corr = np.nan_to_num(corr, nan=0.0)

        eigenvalues, eigenvectors = np.linalg.eigh(corr)
        # eigh returns ascending order; reverse to descending.
        order = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[order]
        eigenvectors = eigenvectors[:, order]

        k = self._select_n_components(eigenvalues)
        symbols = list(returns.columns)
        inv_std = np.where(std.values > 1e-12, 1.0 / std.values, 0.0)

        weights = {}
        for j in range(k):
            weights[f"factor_{j}"] = eigenvectors[:, j] * inv_std
        frame = pd.DataFrame(weights, index=symbols).T

        total = float(np.sum(eigenvalues))
        self._last_explained = (
            float(np.sum(eigenvalues[:k]) / total) if total > 0 else 0.0
        )
        return frame

    @staticmethod
    def get_residuals(
        returns: pd.DataFrame, factor_returns: pd.DataFrame
    ) -> dict[str, np.ndarray]:
        """Regress each symbol's returns on factor returns; return residuals.

        OLS with intercept per symbol over the residual window.
        """
        F = factor_returns.values
        X = np.column_stack([np.ones(len(F)), F])
        residuals: dict[str, np.ndarray] = {}
        for sym in returns.columns:
            y = returns[sym].values
            try:
                beta, *_ = np.linalg.lstsq(X, y, rcond=None)
                residuals[sym] = y - X @ beta
            except np.linalg.LinAlgError:
                residuals[sym] = np.zeros_like(y)
        return residuals

    def _s_score_from_residual(self, symbol: str, residual: np.ndarray) -> SScore:
        """Fit AR(1) to the cumulative residual and compute the s-score.

        Following Avellaneda-Lee: the auxiliary process X_n = cumsum(residual)
        is modelled as X_{n+1} = a + b X_n + zeta with
            kappa    = -log(b) * 252,
            m        = a / (1 - b),
            sigma_eq = sqrt(var(zeta) / (1 - b^2)),
            s        = (X_last - m) / sigma_eq.
        """
        x = np.cumsum(residual)
        n = len(x)
        if n < 3:
            return SScore(symbol, 0.0, 0.0, 0.0, 0.0, False)

        x_lag = x[:-1]
        x_next = x[1:]
        A = np.column_stack([np.ones(len(x_lag)), x_lag])
        try:
            coef, *_ = np.linalg.lstsq(A, x_next, rcond=None)
        except np.linalg.LinAlgError:
            return SScore(symbol, 0.0, 0.0, 0.0, 0.0, False)

        a, b = float(coef[0]), float(coef[1])
        # Require genuine mean reversion: 0 < b < 1.
        if not (0.0 < b < 1.0):
            return SScore(symbol, 0.0, 0.0, 0.0, 0.0, False)

        kappa = -np.log(b) * 252.0
        m = a / (1.0 - b)
        zeta = x_next - (a + b * x_lag)
        var_zeta = float(np.var(zeta, ddof=1)) if len(zeta) > 1 else 0.0
        sigma_eq = np.sqrt(var_zeta / (1.0 - b * b)) if var_zeta > 0 else 0.0
        if sigma_eq <= 1e-12:
            return SScore(symbol, 0.0, kappa, m, 0.0, False)

        # Avellaneda-Lee de-mean the s-score (residual drift removed).
        s = (x[-1] - m) / sigma_eq
        fast = kappa > self.kappa_min
        return SScore(symbol, float(s), float(kappa), float(m), float(sigma_eq), fast)

    def get_s_scores(self, residuals: dict[str, np.ndarray]) -> dict[str, SScore]:
        return {
            sym: self._s_score_from_residual(sym, res)
            for sym, res in residuals.items()
        }

    # ------------------------------------------------------------------ #
    # Signal rules
    # ------------------------------------------------------------------ #
    def _target_from_score(self, score: SScore, current: int) -> int:
        if not score.fast_reverting:
            return 0
        s = score.s_score
        # Manage existing positions first (close rules).
        if current > 0:  # currently long
            return 0 if s > -self.sbc else 1
        if current < 0:  # currently short
            return 0 if s < self.ssc else -1
        # Flat: open rules.
        if s < -self.sbo:
            return 1
        if s > self.sso:
            return -1
        return 0

    def compute_signals(
        self,
        returns: pd.DataFrame,
        current_positions: dict[str, int] | None = None,
    ) -> PCAResult:
        """Run the full PCA pipeline and produce per-symbol target positions.

        Args:
            returns: daily returns frame (symbols in columns). The most recent
                ``corr_window`` rows train the PCA; the most recent
                ``residual_window`` rows drive the factor regression / OU fit.
            current_positions: existing per-symbol position (+1/-1/0) so the
                close-side cut-offs can be applied with hysteresis.

        Returns:
            A PCAResult with s-scores and integer target weights.
        """
        current_positions = current_positions or {}
        if returns is None or returns.empty or len(returns.columns) < 2:
            return PCAResult()

        clean = returns.dropna(axis=1, how="any")
        if len(clean.columns) < 2 or len(clean) < 3:
            self.logger.warning("Insufficient clean return data for PCA")
            return PCAResult()

        corr_data = clean.iloc[-self.corr_window:]
        self._last_explained = 0.0
        factor_weights = self.get_factor_weights(corr_data)

        resid_data = clean.iloc[-self.residual_window:]
        # Factor returns over the residual window: F = R @ Q^T.
        factor_returns = pd.DataFrame(
            resid_data.values @ factor_weights.values.T,
            index=resid_data.index,
            columns=factor_weights.index,
        )

        residuals = self.get_residuals(resid_data, factor_returns)
        s_scores = self.get_s_scores(residuals)

        targets: dict[str, int] = {}
        for sym, score in s_scores.items():
            target = self._target_from_score(score, current_positions.get(sym, 0))
            score.target = target
            if target != 0:
                targets[sym] = target

        result = PCAResult(
            s_scores=s_scores,
            target_weights=targets,
            n_components=len(factor_weights),
            eigen_explained=getattr(self, "_last_explained", 0.0),
            corr_window=self.corr_window,
            residual_window=self.residual_window,
        )
        self.logger.info(
            "PCA scoring: %d factors (%.1f%% var), %d long / %d short signals",
            result.n_components,
            result.eigen_explained * 100.0,
            len(result.open_longs()),
            len(result.open_shorts()),
        )
        return result


__all__ = ["PCAEigenPortfolioEngine", "PCAResult", "SScore"]
