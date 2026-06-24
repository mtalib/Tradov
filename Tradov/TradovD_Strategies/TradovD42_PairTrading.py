#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies
Module: TradovD42_PairTrading.py
Purpose: Statistical arbitrage / pair trading strategy

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Pair trading strategy that inherits from BaseStrategy. Generates
    PairTradingSignal objects based on z-score entry/exit from the
    spread of cointegrated pairs. Uses KalmanHedgeRatio for dynamic
    hedge ratios and OUProcessFitter for half-life gating.

    Configuration via env vars:
        TRADOV_PAIR_ENTRY_Z   (default 2.0)
        TRADOV_PAIR_EXIT_Z    (default 0.5)
        TRADOV_PAIR_STOP_Z    (default 3.5)
        TRADOV_PAIR_LOOKBACK  (default 60)
        TRADOV_PAIR_MAX_HALF_LIFE (default 30)
        TRADOV_PAIR_SIZE_PCT  (default 0.02)
        TRADOV_PAIR_MAX_OPEN  (default 10)
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
    PerformanceMetrics,
    PositionState,
    PositionType,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
    SIGNAL_EXPIRY_SECONDS,
)
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    CointegrationResult,
    PairDefinition,
    PairPosition,
    PairSide,
    PairStatus,
    PairTradingSignal,
)
from Tradov.TradovD_Strategies.TradovD51_PairScanner import (
    PairScanner,
)
from Tradov.TradovD_Strategies.TradovD54_KalmanHedgeRatio import (
    KalmanHedgeRatio,
)
from Tradov.TradovD_Strategies.TradovD53_OUProcessFitter import (
    OUProcessFitter,
)


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class PairTradingStrategy(BaseStrategy):
    def __init__(
        self,
        name: str,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: dict[str, Any] | None,
        strategy_type: str | None = None,
    ):
        super().__init__(name, event_manager, risk_profile, config, strategy_type)

        self.entry_z = float(config.get("entry_z", _env("TRADOV_PAIR_ENTRY_Z", "2.0")))
        self.exit_z = float(config.get("exit_z", _env("TRADOV_PAIR_EXIT_Z", "0.5")))
        self.stop_z = float(config.get("stop_z", _env("TRADOV_PAIR_STOP_Z", "3.5")))
        self.lookback = int(config.get("lookback", _env("TRADOV_PAIR_LOOKBACK", "60")))
        self.max_half_life = float(config.get("max_half_life", _env("TRADOV_PAIR_MAX_HALF_LIFE", "30")))
        self.size_pct = float(config.get("size_pct", _env("TRADOV_PAIR_SIZE_PCT", "0.02")))
        self.max_open_pairs = int(config.get("max_open_pairs", _env("TRADOV_PAIR_MAX_OPEN", "10")))

        self.scanner = PairScanner()
        self.kalman_filters: dict[str, KalmanHedgeRatio] = {}
        self.ou_fitter = OUProcessFitter(
            entry_z=self.entry_z,
            exit_z=self.exit_z,
            stop_z=self.stop_z,
            max_half_life=self.max_half_life,
        )

        self.pair_positions: dict[str, PairPosition] = {}
        self.coint_results: dict[str, CointegrationResult] = {}
        self.price_history: dict[str, list[float]] = {}
        self._price_buffer_len = self.lookback * 2

    def _initialize_strategy(self) -> None:
        self.logger.info(
            "PairTradingStrategy initialized: entry_z=%.1f exit_z=%.1f stop_z=%.1f max_open=%d",
            self.entry_z,
            self.exit_z,
            self.stop_z,
            self.max_open_pairs,
        )

    def _refresh_pair_state(self) -> dict[str, PairDefinition]:
        """Refresh pair metadata and ensure adaptive hedge-ratio state exists."""
        pair_defs = self.scanner.get_pair_definitions()
        for pair_key, coint in self.coint_results.items():
            if coint.is_tradeable and pair_key not in self.kalman_filters:
                self.kalman_filters[pair_key] = KalmanHedgeRatio(lookback=self.lookback)
        return pair_defs

    def _pair_is_entry_candidate(
        self,
        pair_key: str,
        pair_def: PairDefinition,
        coint: CointegrationResult,
    ) -> tuple[bool, str]:
        if pair_def.status != PairStatus.VALIDATED:
            return False, "pair not validated"
        if pair_key in self.pair_positions:
            return False, "pair already open"
        if coint.half_life > self.max_half_life:
            return False, "half-life above threshold"
        return True, ""

    def _compute_pair_signal(
        self,
        pair_def: PairDefinition,
        coint: CointegrationResult,
        z_score: float,
        market_data: pd.DataFrame,
    ) -> PairTradingSignal | None:
        sym_a = pair_def.symbol_a
        sym_b = pair_def.symbol_b

        price_a = self._get_latest_price(sym_a, market_data)
        price_b = self._get_latest_price(sym_b, market_data)
        if price_a is None or price_b is None:
            return None

        if z_score > 0:
            pair_side = PairSide.LONG_SHORT
            signal_type = SignalType.SELL
        else:
            pair_side = PairSide.SHORT_LONG
            signal_type = SignalType.BUY

        hedge_ratio = coint.hedge_ratio
        notional = self.risk_profile.account_size * self.size_pct
        qty_a = max(1, int(notional / price_a))
        qty_b = max(1, int(qty_a * hedge_ratio * price_a / price_b))

        strength = SignalStrength.STRONG if abs(z_score) >= 2.5 else SignalStrength.MODERATE
        confidence = min(1.0, abs(z_score) / self.stop_z)

        spread_price = price_a - hedge_ratio * price_b

        now = datetime.now(UTC)
        return PairTradingSignal(
            signal_id=str(uuid.uuid4()),
            signal_type=signal_type,
            symbol=f"{sym_a}/{sym_b}",
            strength=strength,
            confidence=confidence,
            entry_price=abs(spread_price),
            stop_loss=abs(spread_price) * (1 + self.stop_z / abs(z_score + 1e-6)),
            take_profit=0.0,
            position_size=qty_a,
            timestamp=now,
            expires_at=now + timedelta(seconds=SIGNAL_EXPIRY_SECONDS),
            pair_key=pair_def.key,
            pair_side=pair_side,
            hedge_ratio=hedge_ratio,
            z_score=z_score,
            half_life=coint.half_life,
            spread_price=spread_price,
            symbol_a=sym_a,
            symbol_b=sym_b,
            quantity_a=qty_a,
            quantity_b=qty_b,
            metadata={
                "strategy_id": self.name,
                "strategy_type": "pair_trading",
                "action": signal_type.value,
            },
        )

    def update_price(self, symbol: str, price: float) -> None:
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        buf = self.price_history[symbol]
        buf.append(price)
        if len(buf) > self._price_buffer_len:
            del buf[: len(buf) - self._price_buffer_len]

    def update_cointegration(self, results: list[CointegrationResult]) -> None:
        for r in results:
            self.coint_results[r.pair_key] = r
            if r.is_tradeable and r.pair_key not in self.kalman_filters:
                self.kalman_filters[r.pair_key] = KalmanHedgeRatio(lookback=self.lookback)

    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        signals: list[TradingSignal] = []

        if len(self.pair_positions) >= self.max_open_pairs:
            return signals

        pair_defs = self._refresh_pair_state()
        for pair_key, pair_def in pair_defs.items():
            if pair_key not in self.coint_results:
                continue

            coint = self.coint_results[pair_key]
            is_candidate, reason = self._pair_is_entry_candidate(pair_key, pair_def, coint)
            if not is_candidate:
                self.logger.debug("Skipping pair %s: %s", pair_key, reason)
                continue

            z_score = self._compute_z_score(pair_key, pair_def, market_data)
            if z_score is None:
                continue

            if abs(z_score) >= self.entry_z:
                signal = self._compute_pair_signal(pair_def, coint, z_score, market_data)
                if signal is not None:
                    signals.append(signal)

        return signals

    def _compute_z_score(
        self,
        pair_key: str,
        pair_def: PairDefinition,
        market_data: pd.DataFrame,
    ) -> float | None:
        sym_a = pair_def.symbol_a
        sym_b = pair_def.symbol_b

        hist_a = self.price_history.get(sym_a, [])
        hist_b = self.price_history.get(sym_b, [])
        if len(hist_a) < self.lookback or len(hist_b) < self.lookback:
            return None

        arr_a = np.array(hist_a[-self.lookback:])
        arr_b = np.array(hist_b[-self.lookback:])

        kf = self.kalman_filters.get(pair_key)
        if kf is None:
            return None

        result = kf.fit(arr_a, arr_b)
        return result.latest_z()

    def _get_latest_price(self, symbol: str, market_data: pd.DataFrame) -> float | None:
        hist = self.price_history.get(symbol, [])
        if hist:
            return hist[-1]
        if symbol in market_data.columns:
            return float(market_data[symbol].iloc[-1])
        return None

    def validate_signal(self, signal: TradingSignal) -> bool:
        if not isinstance(signal, PairTradingSignal):
            return False
        if not signal.is_valid():
            return False
        if signal.pair_key in self.pair_positions:
            return False
        if len(self.pair_positions) >= self.max_open_pairs:
            return False
        if signal.confidence < 0.3:
            return False
        return True

    def calculate_position_size(self, signal: TradingSignal) -> int:
        if isinstance(signal, PairTradingSignal):
            return signal.quantity_a
        return max(1, int(self.risk_profile.account_size * self.size_pct / signal.entry_price))

    def should_exit_position(
        self, position: StrategyPosition, market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        for pair_key, pair_pos in self.pair_positions.items():
            if pair_pos.position_id == position.position_id:
                return self._check_pair_exit(pair_pos, market_data)
        return False, ""

    def _check_pair_exit(
        self, pair_pos: PairPosition, market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        current_z = pair_pos.current_z

        if abs(current_z) <= self.exit_z:
            return True, f"Z-score mean reversion: z={current_z:.2f}"

        if abs(current_z) >= self.stop_z:
            return True, f"Z-score stop breach: z={current_z:.2f}"

        if pair_pos.duration and pair_pos.duration > timedelta(days=self.max_half_life * 3):
            return True, f"Position aged out: {pair_pos.duration.days}d > {self.max_half_life * 3}d"

        return False, ""

    def open_pair_position(self, signal: PairTradingSignal) -> PairPosition | None:
        if signal.pair_key in self.pair_positions:
            self.logger.warning("Pair %s already has open position", signal.pair_key)
            return None

        pair_pos = PairPosition(
            pair_key=signal.pair_key,
            pair_side=signal.pair_side,
            state=PositionState.OPENING,
            symbol_a=signal.symbol_a,
            symbol_b=signal.symbol_b,
            quantity_a=signal.quantity_a,
            quantity_b=signal.quantity_b,
            entry_price_a=0.0,
            entry_price_b=0.0,
            hedge_ratio=signal.hedge_ratio,
            entry_z=signal.z_score,
            current_z=signal.z_score,
            strategy_name=self.name,
            metadata={"signal_id": signal.signal_id},
        )
        self.pair_positions[signal.pair_key] = pair_pos
        self.logger.info(
            "Opening pair position: %s side=%s z=%.2f",
            signal.pair_key,
            signal.pair_side.value,
            signal.z_score,
        )
        return pair_pos

    def close_pair_position(self, pair_key: str, reason: str = "Manual") -> bool:
        pair_pos = self.pair_positions.get(pair_key)
        if pair_pos is None:
            return False
        pair_pos.close(
            pair_pos.current_price_a or pair_pos.entry_price_a,
            pair_pos.current_price_b or pair_pos.entry_price_b,
            reason,
        )
        self.performance.total_trades += 1
        pnl = pair_pos.realized_pnl
        if pnl > 0:
            self.performance.winning_trades += 1
        else:
            self.performance.losing_trades += 1
        self.performance.total_pnl += pnl

        del self.pair_positions[pair_key]
        self.logger.info(
            "Closed pair %s: pnl=%.2f reason=%s", pair_key, pnl, reason
        )
        return True

    def update_pair_prices(self, prices: dict[str, float]) -> None:
        for pair_key, pair_pos in self.pair_positions.items():
            pa = prices.get(pair_pos.symbol_a)
            pb = prices.get(pair_pos.symbol_b)
            if pa is not None and pb is not None:
                coint = self.coint_results.get(pair_key)
                sm = coint.spread_mean if coint else 0.0
                ss = coint.spread_std if coint else 1.0
                pair_pos.update_prices(pa, pb, sm, ss)

    def get_state(self) -> dict[str, Any]:
        base = super().get_state()
        base.update({
            "open_pairs": len(self.pair_positions),
            "tracked_coint_pairs": len(self.coint_results),
            "kalman_filters": len(self.kalman_filters),
            "entry_z": self.entry_z,
            "exit_z": self.exit_z,
            "stop_z": self.stop_z,
            "max_open_pairs": self.max_open_pairs,
        })
        return base

    def get_pair_positions(self) -> dict[str, PairPosition]:
        return dict(self.pair_positions)

    def stop(self) -> bool:
        for pair_key in list(self.pair_positions.keys()):
            self.close_pair_position(pair_key, "Strategy stopped")
        return super().stop()


__all__ = ["PairTradingStrategy"]
