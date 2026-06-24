#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovD_Strategies
Module: TradovD50_PairTypes.py
Purpose: Data structures for statistical arbitrage / pair trading

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Canonical data classes for pair (stat-arb) trading:
      - PairDefinition: static metadata for a candidate pair
      - PairTradingSignal: extends TradingSignal with pair-specific fields
      - PairPosition: tracks both legs of an open pair trade
      - PairScanResult: result from a cointegration scanner run
      - CointegrationResult: per-pair cointegration test output
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, UTC
from enum import Enum
from typing import Any

from Tradov.TradovD_Strategies.TradovD01_BaseStrategy import (
    TradingSignal,
    SignalType,
    SignalStrength,
    PositionState,
)


class PairSide(Enum):
    LONG_SHORT = "long_short"
    SHORT_LONG = "short_long"


class PairStatus(Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    ACTIVE = "active"
    DEGRADED = "degraded"
    BROKEN = "broken"
    EXCLUDED = "excluded"


class CointegrationMethod(Enum):
    ENGLE_GRANGER = "engle_granger"
    JOHANSEN = "johansen"
    BOTH = "both"


@dataclass(frozen=True)
class PairDefinition:
    symbol_a: str
    symbol_b: str
    sector: str
    pair_type: str
    status: PairStatus = PairStatus.CANDIDATE
    entry_z: float = 2.0
    exit_z: float = 0.5
    stop_z: float = 3.5
    max_half_life: int = 30
    size_pct: float = 0.02
    lookback: int = 60

    @property
    def key(self) -> str:
        return f"{self.symbol_a}/{self.symbol_b}"


@dataclass
class CointegrationResult:
    pair_key: str
    is_cointegrated: bool
    p_value: float
    hedge_ratio: float
    half_life: float
    spread_mean: float
    spread_std: float
    method: CointegrationMethod
    test_statistic: float
    critical_value: float
    sample_size: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    ranking_score: float = 0.0
    ranking_components: dict[str, float] = field(default_factory=dict)

    @property
    def is_tradeable(self) -> bool:
        return self.is_cointegrated and self.half_life > 0 and self.half_life < 30


@dataclass
class PairScanResult:
    scan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_candidates: int = 0
    validated_pairs: list[CointegrationResult] = field(default_factory=list)
    ranked_pairs: list[CointegrationResult] = field(default_factory=list)
    fdr_method: str = "benjamini_hochberg"
    fdr_alpha: float = 0.05

    @property
    def tradeable_count(self) -> int:
        return sum(1 for r in self.validated_pairs if r.is_tradeable)


@dataclass
class PairTradingSignal(TradingSignal):
    pair_key: str = ""
    pair_side: PairSide = PairSide.LONG_SHORT
    hedge_ratio: float = 1.0
    z_score: float = 0.0
    half_life: float = 0.0
    spread_price: float = 0.0
    symbol_a: str = ""
    symbol_b: str = ""
    quantity_a: int = 0
    quantity_b: int = 0

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "pair_key": self.pair_key,
            "pair_side": self.pair_side.value,
            "hedge_ratio": self.hedge_ratio,
            "z_score": self.z_score,
            "half_life": self.half_life,
            "spread_price": self.spread_price,
            "symbol_a": self.symbol_a,
            "symbol_b": self.symbol_b,
            "quantity_a": self.quantity_a,
            "quantity_b": self.quantity_b,
        })
        return base


@dataclass
class PairPosition:
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pair_key: str = ""
    pair_side: PairSide = PairSide.LONG_SHORT
    state: PositionState = PositionState.PENDING
    symbol_a: str = ""
    symbol_b: str = ""
    quantity_a: int = 0
    quantity_b: int = 0
    entry_price_a: float = 0.0
    entry_price_b: float = 0.0
    current_price_a: float = 0.0
    current_price_b: float = 0.0
    hedge_ratio: float = 1.0
    entry_z: float = 0.0
    current_z: float = 0.0
    entry_spread: float = 0.0
    current_spread: float = 0.0
    entry_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    exit_time: datetime | None = None
    exit_reason: str | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    strategy_name: str = "PairTrading"
    order_id_a: str | None = None
    order_id_b: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def update_prices(self, price_a: float, price_b: float, spread_mean: float = 0.0, spread_std: float = 1.0) -> None:
        self.current_price_a = price_a
        self.current_price_b = price_b
        self.current_spread = price_a - self.hedge_ratio * price_b
        if spread_std > 0:
            self.current_z = (self.current_spread - spread_mean) / spread_std
        if self.pair_side == PairSide.LONG_SHORT:
            self.unrealized_pnl = (
                (price_a - self.entry_price_a) * self.quantity_a
                + (self.entry_price_b - price_b) * self.quantity_b
            )
        else:
            self.unrealized_pnl = (
                (self.entry_price_a - price_a) * self.quantity_a
                + (price_b - self.entry_price_b) * self.quantity_b
            )

    def close(self, price_a: float, price_b: float, reason: str) -> None:
        self.update_prices(price_a, price_b)
        self.realized_pnl = self.unrealized_pnl
        self.unrealized_pnl = 0.0
        self.exit_time = datetime.now(UTC)
        self.exit_reason = reason
        self.state = PositionState.CLOSED

    @property
    def is_open(self) -> bool:
        return self.state in {PositionState.PENDING, PositionState.OPENING, PositionState.OPEN}

    @property
    def duration(self) -> timedelta | None:
        if self.exit_time:
            return self.exit_time - self.entry_time
        return datetime.now(UTC) - self.entry_time

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "pair_key": self.pair_key,
            "pair_side": self.pair_side.value,
            "state": self.state.value,
            "symbol_a": self.symbol_a,
            "symbol_b": self.symbol_b,
            "quantity_a": self.quantity_a,
            "quantity_b": self.quantity_b,
            "entry_price_a": self.entry_price_a,
            "entry_price_b": self.entry_price_b,
            "current_price_a": self.current_price_a,
            "current_price_b": self.current_price_b,
            "hedge_ratio": self.hedge_ratio,
            "entry_z": self.entry_z,
            "current_z": self.current_z,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "duration_seconds": self.duration.total_seconds() if self.duration else None,
            "exit_reason": self.exit_reason,
            "strategy_name": self.strategy_name,
        }


__all__ = [
    "PairSide",
    "PairStatus",
    "CointegrationMethod",
    "PairDefinition",
    "CointegrationResult",
    "PairScanResult",
    "PairTradingSignal",
    "PairPosition",
]
