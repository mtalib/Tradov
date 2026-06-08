#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovE_Risk
Module: TradovE00_RiskProtocol.py
Purpose: Typed Protocol interfaces for the E-Series ↔ D-Series series boundary

Defines:
    BoundarySignalType    — canonical signal direction enum at the boundary
    RiskValidationRequest — normalised pre-trade risk check request dataclass
    RiskValidationResult  — normalised approval / rejection result dataclass
    OverlayPretradeVerdict — structured result for overlay-slot risk checks
    RiskManagerProtocol   — structural Protocol that every E-Series risk gate must satisfy
    StrategyStateProvider — structural Protocol that D-Series strategies must satisfy

Any object that implements all methods of a Protocol satisfies it without
inheriting from it (structural subtyping).

Concrete satisfiers (no inheritance required):
    RiskManager (TradovE01) already satisfies RiskManagerProtocol structurally.
    BaseStrategy (TradovD01) already satisfies StrategyStateProvider structurally.

Usage::

    from Tradov.TradovE_Risk.TradovE00_RiskProtocol import (
        OverlayPretradeVerdict, RiskValidationRequest, RiskValidationResult, RiskManagerProtocol,
        StrategyStateProvider,
    )
    assert isinstance(my_risk_manager, RiskManagerProtocol)   # runtime check

Author: Tradov Dev
Year Created: 2026
Last Updated: 2026-04-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

try:
    from typing import Protocol, runtime_checkable
except ImportError:                                     # Python < 3.8 fallback
    from typing import Protocol, runtime_checkable  # type: ignore[assignment]

# ==============================================================================
# LOGGER
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# CANONICAL ENUMS
# ==============================================================================


class BoundarySignalType(Enum):
    """Canonical trade-direction enum at the E↔D series boundary.

    Use this type in RiskValidationRequest so the E-Series risk layer is not
    coupled to the SignalType enum defined inside TradovD01_BaseStrategy.
    """

    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    ADJUST = "adjust"
    HOLD = "hold"


# ==============================================================================
# CANONICAL DATA TYPES
# ==============================================================================


@dataclass
class RiskValidationRequest:
    """Normalised pre-trade risk check request passed from D-Series to E-Series.

    D-Series strategies map their internal TradingSignal or Order object to
    this dataclass before crossing the series boundary so that the E-Series
    risk layer is decoupled from D-Series implementation details.

    Attributes:
        symbol:       Ticker symbol (e.g., "TRAD" or an OCC options symbol).
        quantity:     Proposed contract / share quantity (positive integer).
        signal_type:  Canonical direction of the proposed trade.
        strategy_id:  Identifier of the originating strategy instance.
        entry_price:  Intended entry price; 0.0 means market order.
        stop_loss:    Stop-loss price; 0.0 means no hard stop defined.
        take_profit:  Take-profit price; 0.0 means no hard target.
        confidence:   Strategy confidence score in [0.0, 1.0].
        metadata:     Arbitrary key-value pairs for extensibility.
    """

    symbol: str = ""
    quantity: int = 0
    signal_type: BoundarySignalType = BoundarySignalType.BUY
    strategy_id: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskValidationResult:
    """Normalised result returned by the E-Series risk layer to D-Series callers.

    Attributes:
        approved:          True if the trade request may proceed as-is.
        rejection_reason:  Human-readable reason when approved is False.
        risk_score:        Composite risk score in [0.0, 1.0]; higher is riskier.
        max_safe_quantity: Maximum quantity the risk layer will permit; may be
                           less than the requested quantity on a partial approval.
        violations:        List of specific rule codes that were breached
                           (e.g., "DELTA_LIMIT_EXCEEDED", "MAX_DAILY_LOSS").
        timestamp:         When the validation check was performed.
    """

    approved: bool = False
    rejection_reason: str = ""
    risk_score: float = 0.0
    max_safe_quantity: int = 0
    violations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class OverlayPretradeVerdict:
    """Structured result returned by the E-Series overlay-slot gate.

    Attributes:
        allow: True when the requested overlay slot may proceed.
        reason_code: Machine-readable allow/deny reason.
        limits_snapshot: Effective thresholds used for the decision.
        computed_values: Actual computed inputs inspected by the gate.
        timestamp: When the verdict was produced.
    """

    allow: bool = False
    reason_code: str = ""
    limits_snapshot: dict[str, Any] = field(default_factory=dict)
    computed_values: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


# ==============================================================================
# PROTOCOL DEFINITIONS
# ==============================================================================


@runtime_checkable
class RiskManagerProtocol(Protocol):
    """Structural Protocol for E-Series risk gate implementations.

    Any object implementing all three methods satisfies this Protocol without
    inheriting from it.  TradovE01.RiskManager already satisfies it
    structurally.

    Methods:
        validate_signal:  Synchronous pre-trade risk gate; the primary boundary call.
        validate_overlay_slot: Overlay-specific gate for optional third-slot admission.
        get_risk_metrics: Current portfolio risk metrics snapshot.
        get_positions:    Currently tracked open positions keyed by symbol.
    """

    def validate_signal(
        self,
        request: RiskValidationRequest,
    ) -> RiskValidationResult:
        """Run synchronous pre-trade risk checks and return an approval result.

        Args:
            request: Normalised risk check request from the D-Series caller.

        Returns:
            RiskValidationResult indicating approval, risk score, and any rule
            violations.
        """
        ...

    def validate_overlay_slot(
        self,
        request: RiskValidationRequest,
    ) -> OverlayPretradeVerdict:
        """Run the overlay-slot pre-trade gate.

        Args:
            request: Normalised overlay-slot request from the D-Series caller.

        Returns:
            OverlayPretradeVerdict with allow/deny result, thresholds, and
            computed inputs used by the decision.
        """
        ...

    def get_risk_metrics(self) -> dict[str, Any]:
        """Return a snapshot of current portfolio risk metrics.

        Returns:
            Mapping of metric name → value; expected keys include
            ``total_exposure``, ``daily_pnl``, ``margin_used``, and
            ``risk_level``.
        """
        ...

    def get_positions(self) -> dict[str, Any]:
        """Return all currently tracked open positions.

        Returns:
            Mapping of symbol → position data dict; empty dict when flat.
        """
        ...


@runtime_checkable
class StrategyStateProvider(Protocol):
    """Structural Protocol for D-Series strategy state reporting.

    Exposes the minimum surface that E-Series risk and monitoring layers need
    to query a strategy without depending on BaseStrategy internals or any
    other D-Series class.  TradovD01.BaseStrategy already satisfies it
    structurally.

    Methods:
        get_state:               Current strategy operational state.
        get_performance_summary: Aggregated performance metrics as a plain dictionary.
        get_open_positions:      Open positions currently held by this strategy.
    """

    def get_state(self) -> dict[str, Any]:
        """Return the current operational state of the strategy.

        Returns:
            Mapping with expected keys: ``strategy_id``, ``status``,
            ``is_running``, ``current_regime``.
        """
        ...

    def get_performance_summary(self) -> dict[str, Any]:
        """Return aggregated performance metrics.

        Returns:
            Mapping with expected keys: ``sharpe_ratio``, ``win_rate``,
            ``total_pnl``, ``trade_count``.
        """
        ...

    def get_open_positions(self) -> list[Any]:
        """Return all open positions currently managed by this strategy.

        Returns:
            List of position objects or dicts; empty list when the strategy is
            flat.
        """
        ...
