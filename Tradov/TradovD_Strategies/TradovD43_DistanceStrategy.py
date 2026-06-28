#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovD_Strategies
Module: TradovD43_DistanceStrategy.py
Purpose: Distance-approach (SSD) pairs trading strategy

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    BaseStrategy wrapper around the Distance Approach engine (D55). Forms
    the closest (lowest-SSD) stock/ETF pairs over a formation window and
    trades the normalised spread with a +/- k-sigma band, exiting on mean
    reversion (zero crossing).

    Emits PairTradingSignal objects (reusing the D50 pair types) on the
    shared event bus so the D31 StrategyOrchestrator / LiveEngine can route
    both legs. Does not place orders itself.

    Configuration via env vars:
        TRADOV_DIST_ENTRY_K     (default 2.0)   trading band in std units
        TRADOV_DIST_TOP_N       (default 20)    pairs to retain
        TRADOV_DIST_FORMATION   (default 252)   formation window (bars)
        TRADOV_DIST_SIZE_PCT    (default 0.02)  notional per leg
        Open pair cap is fixed at 3 system-wide.
        TRADOV_DIST_SAME_SECTOR (default 0)     1 to require same sector
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, UTC
from typing import Any, Callable

import pandas as pd

from Tradov.TradovA_Core.TradovA05_EventManager import EventManager
from Tradov.TradovD_Strategies.TradovD01_BaseStrategy import (
    BaseStrategy,
    RiskProfile,
    SignalStrength,
    SignalType,
    StrategyPosition,
    TradingSignal,
    SIGNAL_EXPIRY_SECONDS,
)
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    PairPosition,
    PairSide,
    PairScanResult,
    PairTradingSignal,
)
from Tradov.TradovD_Strategies.TradovD58_PairScanDecisionAdapter import (
    build_formed_pair_scan_context,
)
from Tradov.TradovD_Strategies.TradovD59_PairCorpusPolicy import (
    load_pair_trading_corpus_policy,
)
from Tradov.TradovD_Strategies.TradovD55_DistanceEngine import (
    DistanceApproachEngine,
    DistancePair,
)
from config.config import PAIR_TRADING_MAX_OPEN


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


class DistanceTradingStrategy(BaseStrategy):
    """Pairs trading via the normalised-price distance approach."""

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

        self.entry_k = float(cfg.get("entry_k", _env("TRADOV_DIST_ENTRY_K", "2.0")))
        self.top_n = int(cfg.get("top_n", _env("TRADOV_DIST_TOP_N", "20")))
        self.formation = int(cfg.get("formation", _env("TRADOV_DIST_FORMATION", "252")))
        self.size_pct = float(cfg.get("size_pct", _env("TRADOV_DIST_SIZE_PCT", "0.02")))
        self.max_open_pairs = PAIR_TRADING_MAX_OPEN
        self.same_sector_only = bool(int(cfg.get("same_sector", _env("TRADOV_DIST_SAME_SECTOR", "0"))))

        self.engine = DistanceApproachEngine(
            entry_threshold=self.entry_k,
            top_n=self.top_n,
            same_sector_only=self.same_sector_only,
        )
        self._corpus_policy = load_pair_trading_corpus_policy()
        self.sector_map: dict[str, str] = cfg.get("sector_map", {})

        self.formed_pairs: dict[str, DistancePair] = {}
        self.pair_positions: dict[str, PairPosition] = {}
        self.price_history: dict[str, list[float]] = {}
        self._buffer_len = self.formation
        self._bars_since_formation = 0
        self._reformation_interval = int(cfg.get("reformation_interval", self.formation))
        self._pair_scan_sink: Callable[[PairScanResult], None] | None = None

    def _initialize_strategy(self) -> None:
        self.logger.info(
            "DistanceTradingStrategy initialized: entry_k=%.1f top_n=%d formation=%d max_open=%d",
            self.entry_k,
            self.top_n,
            self.formation,
            self.max_open_pairs,
        )

    def set_pair_scan_sink(self, sink: Callable[[PairScanResult], None] | None) -> None:
        """Receive the latest scan result from the orchestrator wiring."""
        self._pair_scan_sink = sink

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

    def _formation_frame(self) -> pd.DataFrame | None:
        ready = {
            sym: buf[-self.formation:]
            for sym, buf in self.price_history.items()
            if len(buf) >= self.formation
        }
        if len(ready) < 2:
            return None
        return pd.DataFrame(ready)

    def _maybe_form_pairs(self) -> None:
        if self.formed_pairs and self._bars_since_formation < self._reformation_interval:
            return
        frame = self._formation_frame()
        if frame is None:
            return
        pairs = self.engine.form_pairs(frame, sector_map=self.sector_map)
        if self._corpus_policy.active_pair_keys:
            pairs = [p for p in pairs if self._corpus_policy.allows_pair_key(p.key)]
        self.formed_pairs = {p.key: p for p in pairs}
        self._bars_since_formation = 0

    def _build_scan_context(self) -> PairScanResult | Any:
        return build_formed_pair_scan_context(self.formed_pairs.values())

    # ------------------------------------------------------------------ #
    # Signal generation
    # ------------------------------------------------------------------ #
    def generate_signals(self, market_data: pd.DataFrame) -> list[TradingSignal]:
        self._ingest_market_data(market_data)
        self._bars_since_formation += 1
        self._maybe_form_pairs()

        scan_result = self._build_scan_context()
        if self._pair_scan_sink is not None:
            try:
                self._pair_scan_sink(scan_result)
            except Exception:
                self.logger.debug("Distance scan sink update failed", exc_info=True)

        if getattr(scan_result, "decision_state", "ready") != "ready":
            self.logger.debug(
                "Skipping distance signal generation due to scan state=%s reason=%s",
                getattr(scan_result, "decision_state", "unknown"),
                getattr(scan_result, "decision_reason", ""),
            )
            return []

        signals: list[TradingSignal] = []
        if len(self.pair_positions) >= self.max_open_pairs:
            return signals

        for key, pair in self.formed_pairs.items():
            if key in self.pair_positions:
                continue
            price_a = self._latest(pair.symbol_a)
            price_b = self._latest(pair.symbol_b)
            if price_a is None or price_b is None:
                continue

            target = self.engine.generate_signal(pair, price_a, price_b, in_position=0)
            if target == 0:
                continue

            signal = self._build_signal(pair, price_a, price_b, target)
            if signal is not None:
                signals.append(signal)
                if len(self.pair_positions) + len(signals) >= self.max_open_pairs:
                    break
        return signals

    def _build_signal(
        self, pair: DistancePair, price_a: float, price_b: float, target: int
    ) -> PairTradingSignal | None:
        if target > 0:
            pair_side = PairSide.LONG_SHORT      # long A, short B
            signal_type = SignalType.BUY
        else:
            pair_side = PairSide.SHORT_LONG      # short A, long B
            signal_type = SignalType.SELL

        notional = self.risk_profile.account_size * self.size_pct
        qty_a = max(1, int(notional / price_a))
        qty_b = max(1, int(notional / price_b))

        z = pair.z_score(price_a, price_b)
        strength = SignalStrength.STRONG if abs(z) >= (self.entry_k + 0.5) else SignalStrength.MODERATE
        confidence = float(min(1.0, abs(z) / (self.entry_k * 2.0)))
        spread_price = pair.spread(price_a, price_b)

        now = datetime.now(UTC)
        return PairTradingSignal(
            signal_id=str(uuid.uuid4()),
            signal_type=signal_type,
            symbol=pair.key,
            strength=strength,
            confidence=confidence,
            entry_price=abs(spread_price),
            stop_loss=0.0,
            take_profit=0.0,
            position_size=qty_a,
            timestamp=now,
            expires_at=now + timedelta(seconds=SIGNAL_EXPIRY_SECONDS),
            pair_key=pair.key,
            pair_side=pair_side,
            hedge_ratio=1.0,
            z_score=z,
            half_life=0.0,
            spread_price=spread_price,
            symbol_a=pair.symbol_a,
            symbol_b=pair.symbol_b,
            quantity_a=qty_a,
            quantity_b=qty_b,
            metadata={
                "strategy_id": self.name,
                "strategy_type": "distance_approach",
                "action": signal_type.value,
                "ssd": pair.ssd,
            },
        )

    def _latest(self, symbol: str) -> float | None:
        buf = self.price_history.get(symbol)
        return buf[-1] if buf else None

    # ------------------------------------------------------------------ #
    # Validation / sizing / exit
    # ------------------------------------------------------------------ #
    def validate_signal(self, signal: TradingSignal) -> bool:
        if not isinstance(signal, PairTradingSignal):
            return False
        if not signal.is_valid():
            return False
        if signal.pair_key in self.pair_positions:
            return False
        if len(self.pair_positions) >= self.max_open_pairs:
            return False
        return signal.confidence >= 0.2

    def calculate_position_size(self, signal: TradingSignal) -> int:
        if isinstance(signal, PairTradingSignal):
            return signal.quantity_a
        return max(1, int(self.risk_profile.account_size * self.size_pct / max(signal.entry_price, 1e-6)))

    def should_exit_position(
        self, position: StrategyPosition, market_data: pd.DataFrame
    ) -> tuple[bool, str]:
        for key, pair_pos in self.pair_positions.items():
            if pair_pos.position_id != position.position_id:
                continue
            pair = self.formed_pairs.get(key)
            if pair is None:
                return False, ""
            price_a = self._latest(pair.symbol_a)
            price_b = self._latest(pair.symbol_b)
            if price_a is None or price_b is None:
                return False, ""
            current = 1 if pair_pos.pair_side == PairSide.LONG_SHORT else -1
            target = self.engine.generate_signal(pair, price_a, price_b, in_position=current)
            if target == 0:
                return True, f"Spread mean reversion: z={pair.z_score(price_a, price_b):.2f}"
            return False, ""
        return False, ""

    # ------------------------------------------------------------------ #
    # Pair lifecycle
    # ------------------------------------------------------------------ #
    def open_pair_position(self, signal: PairTradingSignal) -> PairPosition | None:
        if signal.pair_key in self.pair_positions:
            return None
        pair_pos = PairPosition(
            pair_key=signal.pair_key,
            pair_side=signal.pair_side,
            symbol_a=signal.symbol_a,
            symbol_b=signal.symbol_b,
            quantity_a=signal.quantity_a,
            quantity_b=signal.quantity_b,
            hedge_ratio=signal.hedge_ratio,
            entry_z=signal.z_score,
            current_z=signal.z_score,
            strategy_name=self.name,
            metadata={"signal_id": signal.signal_id},
        )
        self.pair_positions[signal.pair_key] = pair_pos
        self.logger.info(
            "Opening distance pair %s side=%s z=%.2f",
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
        if pair_pos.realized_pnl > 0:
            self.performance.winning_trades += 1
        else:
            self.performance.losing_trades += 1
        self.performance.total_pnl += pair_pos.realized_pnl
        del self.pair_positions[pair_key]
        self.logger.info("Closed distance pair %s: pnl=%.2f reason=%s", pair_key, pair_pos.realized_pnl, reason)
        return True

    def get_state(self) -> dict[str, Any]:
        base = super().get_state()
        base.update({
            "formed_pairs": len(self.formed_pairs),
            "open_pairs": len(self.pair_positions),
            "entry_k": self.entry_k,
            "top_n": self.top_n,
            "formation": self.formation,
        })
        return base

    def stop(self) -> bool:
        for pair_key in list(self.pair_positions.keys()):
            self.close_pair_position(pair_key, "Strategy stopped")
        return super().stop()


__all__ = ["DistanceTradingStrategy"]
