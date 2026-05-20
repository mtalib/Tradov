#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN07_OPRAGreeksHandler.py
Group: N (Options Analytics)
Purpose: Compatibility Greeks handler used by N09/D09 integrations

Description:
    This module provides a lightweight OPRA-greeks-compatible handler so legacy
    modules can depend on a stable interface (`validated_greeks` plus
    `calculate_portfolio_greeks`) without requiring a dedicated OPRA pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
import logging


try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    class SpyderLogger:  # type: ignore[no-redef]
        """Fallback logger adapter for standalone usage."""

        @staticmethod
        def get_logger(name: str):
            return logging.getLogger(name)

    class SpyderErrorHandler:  # type: ignore[no-redef]
        """Fallback error handler for standalone usage."""

        def handle_error(self, error: Exception, context: str | None = None) -> None:
            logging.getLogger(__name__).error("Error in %s: %s", context or "unknown", error)


@dataclass
class ValidatedGreeks:
    """Validated option Greeks snapshot for a single symbol."""

    symbol: str
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class PortfolioGreeksSummary:
    """Aggregate portfolio Greeks used by downstream analytics."""

    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_theta: float = 0.0
    total_vega: float = 0.0
    total_rho: float = 0.0


class OPRAGreeksHandler:
    """Compatibility handler for OPRA-style Greeks access patterns."""

    def __init__(self) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.validated_greeks: dict[str, ValidatedGreeks] = {}
        self.logger.debug("OPRAGreeksHandler initialized")

    def upsert_greeks(
        self,
        symbol: str,
        delta: float = 0.0,
        gamma: float = 0.0,
        theta: float = 0.0,
        vega: float = 0.0,
        rho: float = 0.0,
    ) -> None:
        """Insert or update a symbol Greeks snapshot."""
        self.validated_greeks[symbol] = ValidatedGreeks(
            symbol=symbol,
            delta=float(delta),
            gamma=float(gamma),
            theta=float(theta),
            vega=float(vega),
            rho=float(rho),
        )

    def bulk_upsert(self, greeks_by_symbol: dict[str, dict[str, float]]) -> None:
        """Bulk insert/update from a mapping of symbol -> greek fields."""
        for symbol, values in greeks_by_symbol.items():
            self.upsert_greeks(
                symbol=symbol,
                delta=values.get("delta", 0.0),
                gamma=values.get("gamma", 0.0),
                theta=values.get("theta", 0.0),
                vega=values.get("vega", 0.0),
                rho=values.get("rho", 0.0),
            )

    def calculate_portfolio_greeks(
        self, positions: dict[str, int] | None = None
    ) -> PortfolioGreeksSummary:
        """Aggregate Greeks across validated symbols.

        Args:
            positions: Optional symbol quantities. If omitted, quantity 1 is
                assumed for each validated symbol.
        """
        summary = PortfolioGreeksSummary()
        try:
            for symbol, greeks in self.validated_greeks.items():
                quantity = positions.get(symbol, 1) if positions else 1
                summary.total_delta += greeks.delta * quantity
                summary.total_gamma += greeks.gamma * quantity
                summary.total_theta += greeks.theta * quantity
                summary.total_vega += greeks.vega * quantity
                summary.total_rho += greeks.rho * quantity
        except Exception as exc:
            self.error_handler.handle_error(exc, "OPRAGreeksHandler.calculate_portfolio_greeks")
        return summary
