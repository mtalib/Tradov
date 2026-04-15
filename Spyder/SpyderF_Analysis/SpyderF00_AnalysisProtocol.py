#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF00_AnalysisProtocol.py
Purpose: Typed Protocol interfaces for the F-Series ↔ X-Series series boundary

Defines:
    AnalyticsSignalType       — canonical directional signal enum at the boundary
    IndicatorSnapshot         — normalised, lightweight indicator values dataclass
    RegimeSnapshot            — normalised market regime state dataclass
    AnalyticsProviderProtocol — structural Protocol that F-Series providers must satisfy
    RegimeAwareAgentProtocol  — structural Protocol for X-Series agents consuming regime data

Any object that implements all methods of a Protocol satisfies it without
inheriting from it (structural subtyping).

Concrete satisfiers (no inheritance required):
    IndicatorCalculator (SpyderF01) already satisfies AnalyticsProviderProtocol
    structurally via calculate_all_indicators / get_trading_signals.
    MarketRegimeDetector (SpyderF10) already satisfies AnalyticsProviderProtocol
    structurally via get_current_regime.
    X-Series agents (X03, X13, X14) satisfy RegimeAwareAgentProtocol structurally.

Usage::

    from Spyder.SpyderF_Analysis.SpyderF00_AnalysisProtocol import (
        RegimeSnapshot, AnalyticsProviderProtocol, RegimeAwareAgentProtocol,
    )
    assert isinstance(my_regime_detector, AnalyticsProviderProtocol)

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
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


class AnalyticsSignalType(Enum):
    """Canonical directional signal classification at the F↔X series boundary.

    F-Series modules translate their internal enum types to this set before
    crossing the boundary so that X-Series agents are not coupled to
    F-Series-specific enumerations.
    """

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNDEFINED = "undefined"


# ==============================================================================
# CANONICAL DATA TYPES
# ==============================================================================


@dataclass
class IndicatorSnapshot:
    """Lightweight, normalised snapshot of technical indicator values.

    F-Series modules (F01, F04, F08) produce this dataclass when crossing
    the series boundary so that X-Series agents consume a stable, typed
    surface rather than provider-specific DataFrames or raw dicts.

    Attributes:
        symbol:      Ticker symbol (e.g., "SPY").
        timestamp:   ISO-8601 timestamp of the underlying data bar.
        rsi:         RSI(14) value in [0, 100]; ``float("nan")`` when
                     insufficient data is available.
        macd_signal: MACD histogram value; positive = bullish momentum,
                     negative = bearish momentum.
        atr:         ATR(14) average true range (absolute price units).
        vwap:        Session VWAP price.
        bb_upper:    Bollinger Band upper price level.
        bb_lower:    Bollinger Band lower price level.
        signal_type: Aggregated directional bias derived from indicator consensus.
        confidence:  Model confidence score in [0.0, 1.0].
        raw:         Full indicator mapping for exotic consumers that need
                     additional fields not included in the standard snapshot.
    """

    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    rsi: float = field(default_factory=lambda: math.nan)
    macd_signal: float = field(default_factory=lambda: math.nan)
    atr: float = field(default_factory=lambda: math.nan)
    vwap: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    signal_type: AnalyticsSignalType = AnalyticsSignalType.UNDEFINED
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_overbought(self) -> bool:
        """True when RSI is above the conventional 70 threshold."""
        return (not math.isnan(self.rsi)) and self.rsi > 70.0

    @property
    def is_oversold(self) -> bool:
        """True when RSI is below the conventional 30 threshold."""
        return (not math.isnan(self.rsi)) and self.rsi < 30.0

    def is_valid_rsi(self) -> bool:
        """True when RSI is populated and within [0, 100]."""
        return (not math.isnan(self.rsi)) and 0.0 <= self.rsi <= 100.0


@dataclass
class RegimeSnapshot:
    """Normalised slice of market regime state at the F↔X series boundary.

    F10.MarketRegimeDetector.get_current_regime() maps its RegimeState to
    this dataclass before crossing the boundary so that X-Series agents
    consume a stable, typed surface decoupled from F10 internals.

    Attributes:
        timestamp:              When the regime was last classified.
        volatility_regime:      String name of the volatility regime
                                (mirrors F10.MarketRegime values, e.g.
                                ``"NORMAL"``, ``"HIGH_VOLATILITY"``).
        trend_regime:           String name of the trend regime
                                (mirrors F10.TrendRegime values, e.g.
                                ``"BULLISH"``, ``"BEARISH"``).
        regime_confidence:      Confidence level in [0.0, 1.0].
        risk_adjustment_factor: Recommended position-size scalar for the
                                current regime; 1.0 = no adjustment.
        optimal_strategies:     Strategy names recommended for this regime.
        transition_probability: Probability [0.0, 1.0] that the regime is
                                about to change.
    """

    symbol: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    regime: str = "unknown"
    confidence: float = 0.0
    iv_rank: float = 0.0
    vix_level: float = 0.0

    # Extended fields used by newer consumers.
    volatility_regime: str = "UNDEFINED"
    trend_regime: str = "UNDEFINED"
    regime_confidence: float = 0.0
    risk_adjustment_factor: float = 1.0
    optimal_strategies: list[str] = field(default_factory=list)
    transition_probability: float = 0.0

    @property
    def is_high_volatility(self) -> bool:
        """True when the regime is HIGH_VOLATILITY or EXTREME_VOLATILITY."""
        return self.volatility_regime in ("HIGH_VOLATILITY", "EXTREME_VOLATILITY")

    @property
    def is_transitioning(self) -> bool:
        """True when transition probability exceeds 50 %."""
        return self.transition_probability > 0.5

    def is_high_confidence(self) -> bool:
        """True when boundary confidence is at least 0.70."""
        return self.confidence >= 0.70


# ==============================================================================
# PROTOCOL DEFINITIONS
# ==============================================================================


@runtime_checkable
class AnalyticsProviderProtocol(Protocol):
    """Structural Protocol for F-Series analysis providers.

    Any F-Series module that delivers market analytics to X-Series agents
    satisfies this Protocol without inheriting from it.

    Methods:
        calculate_all_indicators: Return the current IndicatorSnapshot for a symbol.
        get_trading_signals:      Return aggregated directional signals for a symbol.
        get_current_regime:       Return the latest RegimeSnapshot for a symbol.
    """

    def calculate_all_indicators(self, symbol: str, data: Any) -> IndicatorSnapshot:
        """Return the latest normalised indicator snapshot for a symbol.

        Args:
            symbol: Ticker symbol (e.g., ``"SPY"``).

        Returns:
            IndicatorSnapshot populated with the latest computed values.
        """
        ...

    def get_current_regime(self, symbol: str) -> RegimeSnapshot:
        """Return the most recently computed market regime state.

        Returns:
            RegimeSnapshot with volatility/trend regime classifications and
            confidence levels.
        """
        ...

    def get_trading_signals(self, symbol: str) -> list[Any]:
        """Return aggregated directional signals for a symbol.

        Args:
            symbol: Ticker symbol (e.g., ``"SPY"``).

        Returns:
            List of signal payloads.
        """
        ...


@runtime_checkable
class RegimeAwareAgentProtocol(Protocol):
    """Structural Protocol for X-Series agents that consume regime analytics.

    Agents satisfying this Protocol can be discovered by orchestration layers
    (X14, Y08) and automatically updated whenever a regime transition is
    detected by the F-Series.

    Methods:
        on_regime_change: Called when a new RegimeSnapshot is available.
        get_regime_context: Returns the current regime context.
    """

    def on_regime_change(self, snapshot: RegimeSnapshot) -> None:
        """Receive and process a new regime snapshot.

        Args:
            snapshot: Normalised regime state from the F-Series boundary.
        """
        ...

    def get_regime_context(self) -> RegimeSnapshot | None:
        """Return current regime context.

        Returns:
            RegimeSnapshot or None when unavailable.
        """
        ...
