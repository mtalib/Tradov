#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies
Module: TradovD44_PCAStrategy.py
Purpose: PCA / eigenportfolio statistical-arbitrage strategy (Avellaneda-Lee)

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-15 Time: 00:00:00

Module Description:
    BaseStrategy wrapper around the PCA eigenportfolio engine (D56). Builds
    eigenportfolios from the cross-section of stock/ETF returns, computes the
    idiosyncratic-residual s-score for each name, and emits market-neutral
    single-name long/short signals from Avellaneda-Lee thresholds.

    Each name is treated as its own position (BUY = long, SELL = short). The
    resulting book is approximately dollar/beta neutral because longs and
    shorts are balanced across the eigenportfolio factor structure. Signals
    are published on the shared event bus; this class places no orders.

    Configuration via env vars:
        TRADOV_PCA_CORR_WINDOW  (default 252)  PCA correlation lookback
        TRADOV_PCA_RESID_WINDOW (default 60)   residual / OU lookback
        TRADOV_PCA_KAPPA_MIN    (default 8.4)  min reversion speed
        TRADOV_PCA_SBO          (default 1.25) open-long cutoff
        TRADOV_PCA_SSO          (default 1.25) open-short cutoff
        TRADOV_PCA_SBC          (default 0.75) close-long cutoff
        TRADOV_PCA_SSC          (default 0.50) close-short cutoff
        TRADOV_PCA_SIZE_PCT     (default 0.01) notional per name
        TRADOV_PCA_MAX_POS      (default 20)   max concurrent names
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, UTC
from typing import Any

import numpy as np
import pandas as pd

from Tradov.TradovA_Core.TradovA05_EventManager import EventManager
from Tradov.TradovD_Strategies.TradovD01_BaseStrategy import (
    BaseStrategy,
    PositionType,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
    SIGNAL_EXPIRY_SECONDS,
)
from Tradov.TradovD_Strategies.TradovD56_PCAEngine import (
    PCAEigenPortfolioEngine,
    PCAResult,
)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class PCAStatArbStrategy(BaseStrategy):
    """Market-neutral single-name stat-arb driven by PCA eigenportfolios."""

    def __init__(
        self,
        name: str,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any] | None,
        strategy_type: str | None = None,
    ):
        super().__init__(name, event_manager, risk_profile, config, strategy_type)
        cfg = self.config

        self.corr_window = int(cfg.get("corr_window", _env("TRADOV_PCA_CORR_WINDOW", "252")))
        self.residual_window = int(cfg.get("residual_window", _env("TRADOV_PCA_RESID_WINDOW", "60")))
        self.kappa_min = float(cfg.get("kappa_min", _env("TRADOV_PCA_KAPPA_MIN", str(252.0 / 30.0))))
        self.sbo = float(cfg.get("sbo", _env("TRADOV_PCA_SBO", "1.25")))
        self.sso = float(cfg.get("sso", _env("TRADOV_PCA_SSO", "1.25")))
        self.sbc = float(cfg.get("sbc", _env("TRADOV_PCA_SBC", "0.75")))
        self.ssc = float(cfg.get("ssc", _env("TRADOV_PCA_SSC", "0.50")))
        self.size_pct = float(cfg.get("size_pct", _env("TRADOV_PCA_SIZE_PCT", "0.01")))
        self.max_positions_pca = int(cfg.get("max_positions", _env("TRADOV_PCA_MAX_POS", "20")))

        self.engine = PCAEigenPortfolioEngine(
            kappa_min=self.kappa_min,
            corr_window=self.corr_window,
            residual_window=self.residual_window,
            sbo=self.sbo,
            sso=self.sso,
            sbc=self.sbc,
            ssc=self.ssc,
            n_components=cfg.get("n_components"),
        )

        self.price_history: dict[str, list[float]] = {}
        self._buffer_len = self.corr_window + 5
        # symbol -> current target sign (+1/-1) for names we hold.
        self.symbol_positions: dict[str, int] = {}
        self.latest_result: PCAResult | None = None

    def _initialize_strategy(self) -> None:
        self.logger.info(
            "PCAStatArbStrategy initialized: corr=%d resid=%d kappa_min=%.2f max_pos=%d",
            self.corr_window,
            self.residual_window,
            self.kappa_min,
            self.max_positions_pca,
        )

    # ------------------------------------------------------------------ #
    # Data intake
    # ------------------------------------------------------------------ #
    def update_price(self, symbol: str, price: float) -> None:
        buf = self.price_history.setdefault(symbol, [])
        buf.append(price)
        if len(buf) > self._buffer_len:
            del buf[: len(buf) - self._buffer_len]

    def _ingest_market_data(self, market_data: pd.DataFrame) -> None:
        if market_data is None or market_data.empty:
            return
        last_row = market_data.iloc[-1]
        for symbol in market_data.columns:
            value = last_row[symbol]
            if pd.notna(value):
                self.update_price(symbol, float(value))

    def _returns_frame(self) -> pd.DataFrame | None:
        min_len = self.residual_window + 2
        ready = {
            sym: buf for sym, buf in self.price_history.items() if len(buf) >= min_len
        }
        if len(ready) < 2:
            return None
        max_len = max(len(b) for b in ready.values())
        aligned = {sym: ([np.nan] * (max_len - len(b)) + b) for sym, b in ready.items()}
        prices = pd.DataFrame(aligned)
        return prices.pct_change().dropna(how="all")

    # ------------------------------------------------------------------ #
    # Signal generation
    # ------------------------------------------------------------------ #
    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        self._ingest_market_data(market_data)
        returns = self._returns_frame()
        if returns is None or returns.empty:
            return []

        result = self.engine.compute_signals(returns, current_positions=self.symbol_positions)
        self.latest_result = result

        signals: list[TradingSignal] = []
        held = len(self.symbol_positions)
        for symbol, target in result.target_weights.items():
            if self.symbol_positions.get(symbol, 0) == target:
                continue  # already aligned
            if target != 0 and held >= self.max_positions_pca:
                continue
            price = self._latest(symbol)
            if price is None:
                continue
            signal = self._build_signal(symbol, target, price, result)
            if signal is not None:
                signals.append(signal)
                held += 1
        return signals

    def _build_signal(
        self, symbol: str, target: int, price: float, result: PCAResult
    ) -> TradingSignal | None:
        score = result.s_scores.get(symbol)
        s_val = score.s_score if score else 0.0
        signal_type = SignalType.BUY if target > 0 else SignalType.SELL
        notional = self.risk_profile.account_size * self.size_pct
        qty = max(1, int(notional / max(price, 1e-6)))

        abs_s = abs(s_val)
        if abs_s >= 2.0:
            strength = SignalStrength.STRONG
        elif abs_s >= 1.5:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK
        confidence = float(min(1.0, abs_s / 2.5))

        now = datetime.now(UTC)
        return TradingSignal(
            signal_id=str(uuid.uuid4()),
            signal_type=signal_type,
            symbol=symbol,
            strength=strength,
            confidence=confidence,
            entry_price=price,
            stop_loss=0.0,
            take_profit=0.0,
            position_size=qty,
            timestamp=now,
            expires_at=now + timedelta(seconds=SIGNAL_EXPIRY_SECONDS),
            metadata={
                "strategy_id": self.name,
                "strategy_type": "pca_stat_arb",
                "action": signal_type.value,
                "side": signal_type.value,
                "s_score": s_val,
                "kappa": score.kappa if score else 0.0,
            },
        )

    def _latest(self, symbol: str) -> float | None:
        buf = self.price_history.get(symbol)
        return buf[-1] if buf else None

    # ------------------------------------------------------------------ #
    # Validation / sizing / exit
    # ------------------------------------------------------------------ #
    def validate_signal(self, signal: TradingSignal) -> bool:
        if not signal.is_valid():
            return False
        if signal.position_size <= 0:
            return False
        return signal.confidence >= 0.3

    def calculate_position_size(self, signal: TradingSignal) -> int:
        return max(1, int(self.risk_profile.account_size * self.size_pct / max(signal.entry_price, 1e-6)))

    def should_exit_position(
        self, position: StrategyPosition, market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        if self.latest_result is None:
            return False, ""
        score = self.latest_result.s_scores.get(position.symbol)
        if score is None:
            return False, ""

        current = 1 if position.position_type == PositionType.LONG else -1
        # Close rules: long closes when s rises back above -sbc, short when s
        # falls back below +ssc; also exit if the residual stops mean-reverting.
        if not score.fast_reverting:
            return True, "Residual no longer fast mean-reverting"
        s = score.s_score
        if current > 0 and s > -self.sbc:
            return True, f"PCA long exit: s={s:.2f} > -{self.sbc}"
        if current < 0 and s < self.ssc:
            return True, f"PCA short exit: s={s:.2f} < {self.ssc}"
        return False, ""

    # ------------------------------------------------------------------ #
    # Position bookkeeping helpers
    # ------------------------------------------------------------------ #
    def register_fill(self, symbol: str, target: int) -> None:
        """Record an executed entry/exit so close-side cutoffs apply correctly.

        ``target`` is +1 (now long), -1 (now short), or 0 (flat).
        """
        if target == 0:
            self.symbol_positions.pop(symbol, None)
        else:
            self.symbol_positions[symbol] = target

    def get_state(self) -> dict[str, Any]:
        base = super().get_state()
        base.update({
            "pca_names_held": len(self.symbol_positions),
            "corr_window": self.corr_window,
            "residual_window": self.residual_window,
            "n_components": self.latest_result.n_components if self.latest_result else 0,
            "kappa_min": self.kappa_min,
        })
        return base


__all__ = ["PCAStatArbStrategy"]
