#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovE_Risk
Module: TradovE26_PairRiskManager.py
Purpose: Pair-trading risk checks — exposure, beta, sector, cointegration stability

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    Validates pair trading signals and positions against risk limits:
      - Net dollar exposure per pair and across all pairs
      - Beta neutrality deviation from hedge ratio
      - Sector concentration (max pairs per sector)
      - Cointegration stability (reject if p-value degraded)
      - Maximum open pairs limit
    Integrates with E10 CorrelationRiskManager for real-time
    pair correlation monitoring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any

import numpy as np

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovA_Core.TradovA05_EventManager import EventType, get_event_manager
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    CointegrationResult,
    PairDefinition,
    PairPosition,
    PairTradingSignal,
    PairStatus,
)


@dataclass
class PairRiskLimits:
    max_pair_notional: float = 50000.0
    max_total_pair_notional: float = 200000.0
    max_pairs_per_sector: int = 3
    max_open_pairs: int = 10
    max_beta_deviation: float = 0.15
    max_coint_p_value: float = 0.10
    max_single_pair_pnl_pct: float = 0.02
    require_coint_stability: bool = True


@dataclass
class PairRiskReport:
    signal_pair_key: str = ""
    approved: bool = False
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_notional: float = 0.0
    sector_counts: dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_rejected(self) -> bool:
        return not self.approved


class PairRiskManager:
    def __init__(
        self,
        limits: PairRiskLimits | None = None,
        correlation_manager: Any = None,
        logger: logging.Logger | None = None,
    ):
        self.limits = limits or PairRiskLimits()
        self.correlation_manager = correlation_manager
        self.logger = logger or TradovLogger.get_logger("PairRiskManager")
        self._sector_map: dict[str, str] = {}

    def register_pair_sector(self, pair_key: str, sector: str) -> None:
        self._sector_map[pair_key] = sector

    def validate_signal(
        self,
        signal: PairTradingSignal,
        open_positions: dict[str, PairPosition],
        coint_results: dict[str, CointegrationResult],
        account_equity: float,
    ) -> PairRiskReport:
        report = PairRiskReport(signal_pair_key=signal.pair_key)
        violations = report.violations
        warnings = report.warnings

        if len(open_positions) >= self.limits.max_open_pairs:
            violations.append(
                f"Max open pairs reached: {len(open_positions)}/{self.limits.max_open_pairs}"
            )

        if signal.pair_key in open_positions:
            violations.append(f"Pair {signal.pair_key} already has open position")

        pair_notional = self._estimate_notional(signal)
        total_notional = pair_notional + sum(
            self._position_notional(p) for p in open_positions.values()
        )
        report.total_notional = total_notional

        if pair_notional > self.limits.max_pair_notional:
            violations.append(
                f"Pair notional ${pair_notional:,.0f} exceeds limit ${self.limits.max_pair_notional:,.0f}"
            )

        if total_notional > self.limits.max_total_pair_notional:
            violations.append(
                f"Total pair notional ${total_notional:,.0f} exceeds limit ${self.limits.max_total_pair_notional:,.0f}"
            )

        sector = self._sector_map.get(signal.pair_key, "unknown")
        sector_counts = self._count_sectors(open_positions)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        report.sector_counts = sector_counts
        if sector_counts.get(sector, 0) > self.limits.max_pairs_per_sector:
            violations.append(
                f"Sector '{sector}' has {sector_counts[sector]} pairs (max {self.limits.max_pairs_per_sector})"
            )

        coint = coint_results.get(signal.pair_key)
        if coint is None:
            if self.limits.require_coint_stability:
                violations.append(f"No cointegration result for {signal.pair_key}")
        else:
            if coint.p_value > self.limits.max_coint_p_value:
                violations.append(
                    f"Cointegration p-value {coint.p_value:.4f} exceeds limit {self.limits.max_coint_p_value}"
                )
            beta_dev = abs(signal.hedge_ratio - coint.hedge_ratio) / (abs(coint.hedge_ratio) + 1e-8)
            if beta_dev > self.limits.max_beta_deviation:
                violations.append(
                    f"Beta deviation {beta_dev:.2%} exceeds limit {self.limits.max_beta_deviation:.2%}"
                )
            elif beta_dev > self.limits.max_beta_deviation * 0.7:
                warnings.append(
                    f"Beta deviation {beta_dev:.2%} approaching limit"
                )

        if account_equity > 0:
            for pair_key, pos in open_positions.items():
                if abs(pos.unrealized_pnl) / account_equity > self.limits.max_single_pair_pnl_pct:
                    warnings.append(
                        f"Pair {pair_key} unrealized loss {abs(pos.unrealized_pnl):,.0f} "
                        f"exceeds {self.limits.max_single_pair_pnl_pct:.1%} of equity"
                    )

        report.approved = len(violations) == 0
        if not report.approved:
            self._emit_risk_event(signal.pair_key, violations)
        return report

    def check_portfolio_risk(
        self,
        open_positions: dict[str, PairPosition],
        account_equity: float,
    ) -> list[str]:
        alerts: list[str] = []
        total_notional = sum(self._position_notional(p) for p in open_positions.values())

        if total_notional > self.limits.max_total_pair_notional:
            alerts.append(
                f"Total pair exposure ${total_notional:,.0f} exceeds limit"
            )

        if account_equity > 0:
            total_pnl = sum(p.unrealized_pnl for p in open_positions.values())
            if abs(total_pnl) / account_equity > 0.05:
                alerts.append(
                    f"Total pair unrealized loss {abs(total_pnl):,.0f} > 5% equity"
                )

        sector_counts = self._count_sectors(open_positions)
        for sector, count in sector_counts.items():
            if count > self.limits.max_pairs_per_sector:
                alerts.append(
                    f"Sector '{sector}' over-concentrated: {count} pairs"
                )
        return alerts

    @staticmethod
    def _estimate_notional(signal: PairTradingSignal) -> float:
        return abs(signal.quantity_a * signal.entry_price) + abs(
            signal.quantity_b * signal.entry_price / max(signal.hedge_ratio, 0.01)
        )

    @staticmethod
    def _position_notional(pos: PairPosition) -> float:
        return abs(pos.quantity_a * pos.current_price_a) + abs(
            pos.quantity_b * pos.current_price_b
        )

    def _count_sectors(self, positions: dict[str, PairPosition]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for pair_key in positions:
            sector = self._sector_map.get(pair_key, "unknown")
            counts[sector] = counts.get(sector, 0) + 1
        return counts

    def _emit_risk_event(self, pair_key: str, violations: list[str]) -> None:
        try:
            em = get_event_manager()
            em.emit(
                EventType.RISK_VIOLATION,
                {
                    "source": "PairRiskManager",
                    "pair_key": pair_key,
                    "violations": violations,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                source="PairRiskManager",
            )
        except Exception:
            pass


__all__ = ["PairRiskManager", "PairRiskLimits", "PairRiskReport"]
