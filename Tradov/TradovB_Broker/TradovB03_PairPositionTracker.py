#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovB_Broker
Module: TradovB03_PairPositionTracker.py
Purpose: Pair position group tracking with aggregated P&L and risk metrics

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Tracks pair positions as unified groups, maintaining both-leg state,
    aggregated P&L, and pair-level risk metrics. Designed to be wired
    into the existing B03 PositionTracker or used standalone.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, UTC
from typing import Any

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    PairPosition,
    PairSide,
    PairStatus,
)
from Tradov.TradovD_Strategies.TradovD01_BaseStrategy import PositionState


class PairPositionTracker:
    def __init__(self, logger: logging.Logger | None = None):
        self.logger = logger or TradovLogger.get_logger("PairPositionTracker")
        self._positions: dict[str, PairPosition] = {}
        self._history: list[PairPosition] = []
        self._lock = threading.RLock()

    def open_position(self, position: PairPosition) -> None:
        with self._lock:
            position.state = PositionState.OPEN
            self._positions[position.pair_key] = position
        self.logger.info(
            "Pair position opened: %s side=%s qty_a=%d qty_b=%d",
            position.pair_key,
            position.pair_side.value,
            position.quantity_a,
            position.quantity_b,
        )

    def close_position(
        self, pair_key: str, price_a: float, price_b: float, reason: str = "Manual"
    ) -> PairPosition | None:
        with self._lock:
            pos = self._positions.get(pair_key)
            if pos is None:
                return None
            pos.close(price_a, price_b, reason)
            self._history.append(pos)
            del self._positions[pair_key]
        self.logger.info(
            "Pair position closed: %s pnl=%.2f reason=%s",
            pair_key,
            pos.realized_pnl,
            reason,
        )
        return pos

    def update_prices(
        self,
        pair_key: str,
        price_a: float,
        price_b: float,
        spread_mean: float = 0.0,
        spread_std: float = 1.0,
    ) -> None:
        with self._lock:
            pos = self._positions.get(pair_key)
            if pos is not None:
                pos.update_prices(price_a, price_b, spread_mean, spread_std)

    def get_position(self, pair_key: str) -> PairPosition | None:
        with self._lock:
            return self._positions.get(pair_key)

    def get_all_positions(self) -> dict[str, PairPosition]:
        with self._lock:
            return dict(self._positions)

    def get_history(self, limit: int | None = None) -> list[PairPosition]:
        with self._lock:
            hist = list(self._history)
        if limit:
            hist = hist[-limit:]
        return hist

    def get_total_unrealized_pnl(self) -> float:
        with self._lock:
            return sum(p.unrealized_pnl for p in self._positions.values())

    def get_total_realized_pnl(self) -> float:
        with self._lock:
            return sum(p.realized_pnl for p in self._history)

    def get_total_notional(self) -> float:
        with self._lock:
            return sum(
                abs(p.quantity_a * p.current_price_a) + abs(p.quantity_b * p.current_price_b)
                for p in self._positions.values()
            )

    def get_total_entry_cost(self) -> float:
        with self._lock:
            return sum(
                abs(p.quantity_a * p.entry_price_a) + abs(p.quantity_b * p.entry_price_b)
                for p in self._positions.values()
            )

    def get_total_funds_held(self) -> float:
        with self._lock:
            total = 0.0
            for pos in self._positions.values():
                metadata = pos.metadata or {}
                candidate = metadata.get("cash_held_dollars")
                if candidate in (None, ""):
                    candidate = metadata.get("buying_power_held")
                if candidate in (None, ""):
                    candidate = metadata.get("max_loss_dollars")
                if candidate in (None, ""):
                    candidate = metadata.get("funds_held_dollars")
                if candidate not in (None, ""):
                    try:
                        total += abs(float(candidate))
                        continue
                    except (TypeError, ValueError):
                        pass
                total += abs(pos.quantity_a * pos.entry_price_a) + abs(pos.quantity_b * pos.entry_price_b)
            return total

    def get_net_dollar_exposure(self) -> dict[str, float]:
        with self._lock:
            exposure: dict[str, float] = {}
            for pos in self._positions.values():
                if pos.pair_side == PairSide.LONG_SHORT:
                    exp_a = pos.quantity_a * pos.current_price_a
                    exp_b = -pos.quantity_b * pos.current_price_b
                else:
                    exp_a = -pos.quantity_a * pos.current_price_a
                    exp_b = pos.quantity_b * pos.current_price_b
                exposure[pos.symbol_a] = exposure.get(pos.symbol_a, 0.0) + exp_a
                exposure[pos.symbol_b] = exposure.get(pos.symbol_b, 0.0) + exp_b
            return exposure

    def get_sector_summary(self, sector_map: dict[str, str]) -> dict[str, dict[str, Any]]:
        with self._lock:
            summary: dict[str, dict[str, Any]] = {}
            for pos in self._positions.values():
                sector = sector_map.get(pos.pair_key, "unknown")
                if sector not in summary:
                    summary[sector] = {"count": 0, "notional": 0.0, "unrealized_pnl": 0.0}
                summary[sector]["count"] += 1
                summary[sector]["notional"] += abs(
                    pos.quantity_a * pos.current_price_a
                ) + abs(pos.quantity_b * pos.current_price_b)
                summary[sector]["unrealized_pnl"] += pos.unrealized_pnl
            return summary

    def get_position_count(self) -> int:
        with self._lock:
            return len(self._positions)

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "open_positions": {k: p.to_dict() for k, p in self._positions.items()},
                "total_unrealized_pnl": self.get_total_unrealized_pnl(),
                "total_realized_pnl": self.get_total_realized_pnl(),
                "total_notional": self.get_total_notional(),
                "position_count": len(self._positions),
            }


__all__ = ["PairPositionTracker"]
