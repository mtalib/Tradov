#!/usr/bin/env python3
from __future__ import annotations

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderD_Strategies
Module: SpyderD31_StrategyOrchestrator.py
Purpose: Master Strategy Coordination and Portfolio Management System
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-28 Time: 18:00:00

Module Description:
    Advanced strategy orchestration engine that coordinates multiple simultaneous
    options trading strategies with intelligent allocation, dynamic selection based
    on market regimes, portfolio-level risk management, strategy conflict resolution,
    performance attribution, and real-time health monitoring. Integrates seamlessly
    with the Spyder connectivity management and provides institutional-grade
    portfolio coordination with adaptive strategy rotation algorithms.

Key Features:
    - Multi-strategy lifecycle management and coordination
    - Dynamic portfolio allocation across strategies based on performance
    - Market regime detection for intelligent strategy selection
    - Strategy conflict resolution and portfolio optimization
    - Real-time performance attribution and strategy health monitoring
    - Adaptive strategy rotation with machine learning insights
    - Integration with SpyderB connectivity and SpyderE risk management
    - PyQt6 dashboard for comprehensive strategy monitoring
    - Event-driven architecture with advanced analytics
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import inspect  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
import re  # noqa: E402
import math  # noqa: E402
from fnmatch import fnmatchcase  # noqa: E402
from collections import deque, defaultdict  # noqa: E402
from datetime import datetime, timedelta, time as dt_time, UTC  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from enum import Enum  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from typing import Any  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

try:
    from Spyder.SpyderD_Strategies.SpyderD39_PutCreditSpread7 import (
        is_put_credit_spread_7_entry_window_open as _d31_put_credit_spread_7_entry_window_open,
    )
except Exception:
    def _d31_put_credit_spread_7_entry_window_open(*_args, **_kwargs):
        return False

try:
    from Spyder.SpyderZ_Communication.SpyderZ02_MessageProtocol import (
        extract_agent_handoff_envelope as _extract_agent_handoff_envelope,
        validate_agent_handoff_envelope as _validate_agent_handoff_envelope,
    )
    _D31_AGENT_HANDOFF_VALIDATION_AVAILABLE = True
except Exception:
    _D31_AGENT_HANDOFF_VALIDATION_AVAILABLE = False

    def _extract_agent_handoff_envelope(payload):
        return None, None

    def _validate_agent_handoff_envelope(envelope, schema_name=None):
        return True, None

try:
    from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import now_et as _d31_now_et
except ImportError:
    try:
        import pytz as _d31_pytz

        def _d31_now_et() -> datetime:  # type: ignore[misc]
            return datetime.now(_d31_pytz.timezone("US/Eastern"))

    except ImportError:
        import zoneinfo as _d31_zoneinfo

        def _d31_now_et() -> datetime:  # type: ignore[misc]
            return datetime.now(_d31_zoneinfo.ZoneInfo("America/New_York"))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QGroupBox,
                                QTabWidget, QListWidget,
                                QTableWidget, QTableWidgetItem,
                                QFrame, QComboBox,
                                QSpinBox, QDoubleSpinBox, QHeaderView)
    from PySide6.QtCore import QTimer, Signal
    from PySide6.QtGui import QFont
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    HAS_QT = True
except ImportError:
    HAS_QT = False
    # Headless stubs so the orchestrator's strategy logic works without a display
    QWidget = object
    QTimer = None
    def Signal(*a, **kw):  # noqa: N807
        return property()
    FigureCanvas = object

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    # Core imports
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError  # noqa: F401
    from Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar

    # Strategy imports (optional per strategy; do not disable orchestrator wiring)
    try:
        from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy  # noqa: F401
        from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import is_strategy_class as _is_strategy_class  # noqa: F401
        from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import (
            TradingSignal as BaseTradingSignal,
            SignalType as BaseSignalType,
            SignalStrength as BaseSignalStrength,
        )
    except ImportError:
        BaseStrategy = object  # type: ignore[assignment,misc]
        BaseTradingSignal = None  # type: ignore[assignment]
        BaseSignalType = None  # type: ignore[assignment]
        BaseSignalStrength = None  # type: ignore[assignment]

        def _is_strategy_class(cls: Any) -> bool:  # type: ignore[misc]
            """Fallback when D01 is unavailable."""
            import inspect as _inspect
            if not _inspect.isclass(cls) or _inspect.isabstract(cls):
                return False
            return callable(getattr(cls, "generate_signal", None))

    _OPTIONAL_STRATEGY_CACHE: dict[tuple[str, str], Any] = {}
    _OPTIONAL_STRATEGY_IMPORTS: dict[str, tuple[str, str]] = {
        "IronCondor": ("Spyder.SpyderD_Strategies.SpyderD02_IronCondor", "IronCondorStrategy"),
        "CreditSpread": ("Spyder.SpyderD_Strategies.SpyderD03_CreditSpread", "CreditSpreadStrategy"),
        "ZeroDTE": ("Spyder.SpyderD_Strategies.SpyderD04_ZeroDTE", "ZeroDTEStrategy"),
        "ZeroHFT": ("Spyder.SpyderD_Strategies.SpyderD41_ZeroHFT", "ZeroHFTStrategy"),
        "Straddle": ("Spyder.SpyderD_Strategies.SpyderD05_Straddle", "StraddleStrategy"),
        "BullPutSpread": ("Spyder.SpyderD_Strategies.SpyderD06_BullPutSpread", "BullPutSpreadStrategy"),
        "BearCallSpread": ("Spyder.SpyderD_Strategies.SpyderD07_BearCallSpread", "BearCallSpreadStrategy"),
        "BullCallSpread": ("Spyder.SpyderD_Strategies.SpyderD35_BullCallSpread", "BullCallSpreadStrategy"),
        "BullishStrangle": ("Spyder.SpyderD_Strategies.SpyderD37_BullishStrangle", "BullishStrangleStrategy"),
        "BearPutSpread": ("Spyder.SpyderD_Strategies.SpyderD36_BearPutSpread", "BearPutSpreadStrategy"),
        "PutCreditSpread7": ("Spyder.SpyderD_Strategies.SpyderD39_PutCreditSpread7", "PutCreditSpread7Strategy"),
        "OpeningRangeBreakout": ("Spyder.SpyderD_Strategies.SpyderD08_OpeningRangeBreakout", "OpeningRangeBreakoutStrategy"),
        "GreeksBased": ("Spyder.SpyderD_Strategies.SpyderD09_GreeksBasedStrategy", "GreeksBasedStrategy"),
        "SpecializedZeroDTE": ("Spyder.SpyderD_Strategies.SpyderD11_SpecializedZeroDTE", "SpecializedZeroDTEStrategy"),
        "IronButterfly": ("Spyder.SpyderD_Strategies.SpyderD10_IronButterfly", "IronButterflyStrategy"),
        "BrokenWingButterfly": ("Spyder.SpyderD_Strategies.SpyderD23_BrokenWingButterfly", "BrokenWingButterflyStrategy"),
        "Butterfly": ("Spyder.SpyderD_Strategies.SpyderD24_Butterfly", "ButterflyStrategy"),
        "CalendarSpread": ("Spyder.SpyderD_Strategies.SpyderD14_CalendarSpread", "CalendarSpreadStrategy"),
        "StraddleStrangle": ("Spyder.SpyderD_Strategies.SpyderD15_StraddleStrangle", "StraddleStrangleStrategy"),
        "RatioSpreads": ("Spyder.SpyderD_Strategies.SpyderD16_RatioSpreads", "RatioSpreadsStrategy"),
        "DiagonalSpread": ("Spyder.SpyderD_Strategies.SpyderD17_DiagonalSpread", "DiagonalSpreadStrategy"),
        "JadeLizard": ("Spyder.SpyderD_Strategies.SpyderD19_JadeLizard", "JadeLizardStrategy"),
        "JadeLizardZero": ("Spyder.SpyderD_Strategies.SpyderD38_JadeLizardZero", "JadeLizardZeroStrategy"),
        "VerticalSpreadOptimizer": ("Spyder.SpyderD_Strategies.SpyderD20_VerticalSpreadOptimizer", "VerticalSpreadOptimizer"),
        "DoubleCalendar": ("Spyder.SpyderD_Strategies.SpyderD21_DoubleCalendar", "DoubleCalendarStrategy"),
        "AdaptiveVolatility": ("Spyder.SpyderD_Strategies.SpyderD22_AdaptiveVolatility", "AdaptiveVolatilityStrategy"),
        "GammaScalper": ("Spyder.SpyderD_Strategies.SpyderD26_GammaScalper", "GammaScalperStrategy"),
        "RSIMeanReversion": ("Spyder.SpyderD_Strategies.SpyderD12_RSIMeanReversion", "RSIMeanReversionStrategy"),
        "MACrossover": ("Spyder.SpyderD_Strategies.SpyderD13_MACrossover", "MACrossoverStrategy"),
        "RenaissanceMeanReversion": ("Spyder.SpyderD_Strategies.SpyderD33_RenaissanceMeanReversion", "RenaissanceMeanReversionStrategy"),
        "PivotMeanReversion": ("Spyder.SpyderD_Strategies.SpyderD34_PivotMeanReversion", "PivotMeanReversionStrategy"),
    }

    def _optional_strategy(import_path: str, symbol: str) -> Any:
        cache_key = (import_path, symbol)
        if cache_key in _OPTIONAL_STRATEGY_CACHE:
            return _OPTIONAL_STRATEGY_CACHE[cache_key]
        try:
            module = __import__(import_path, fromlist=[symbol])
            value = getattr(module, symbol)
            _OPTIONAL_STRATEGY_CACHE[cache_key] = value
            return value
        except Exception as err:
            logging.warning("D31 optional strategy unavailable: %s (%s)", symbol, err)
            _OPTIONAL_STRATEGY_CACHE[cache_key] = None
            return None

    class EvolvedCreditSpreadAdapter(BaseStrategy):
        """Adapter to expose D18 strategy through the BaseStrategy contract."""

        def __init__(self, name=None, event_manager=None, risk_profile=None, config=None):
            super().__init__(
                name=name or "EvolvedCreditSpread",
                event_manager=event_manager,
                risk_profile=risk_profile,
                config=config,
                strategy_type="evolved_credit_spread",
            )
            evolved_credit_spread_core = _optional_strategy(
                "Spyder.SpyderD_Strategies.SpyderD18_EvolvedCreditSpread",
                "EvolvedCreditSpreadStrategy",
            )
            self._core = evolved_credit_spread_core(config=config or {}) if evolved_credit_spread_core else None

        @staticmethod
        def _extract_series(data: pd.DataFrame, candidates: list[str]) -> list[float]:
            for col in candidates:
                if col in data.columns:
                    return [float(v) for v in data[col].dropna().tolist()]
            return []

        def _to_d18_market_data(self, market_data: pd.DataFrame) -> dict[str, Any]:
            prices = self._extract_series(market_data, ["SPY", "close", "Close", "price", "last"])
            volumes = self._extract_series(market_data, ["volume", "Volume"])
            vix_series = self._extract_series(market_data, ["VIX", "vix"])

            current_price = float(prices[-1]) if prices else 0.0
            daily_change = 0.0
            if len(prices) >= 2 and prices[-2] != 0:
                daily_change = (prices[-1] - prices[-2]) / prices[-2]

            return {
                "price_series": prices,
                "volume_series": volumes,
                "current_price": current_price,
                "daily_change": daily_change,
                "vix": float(vix_series[-1]) if vix_series else 20.0,
            }

        def _to_base_signal(self, native_signal: Any, default_symbol: str = "SPY") -> BaseTradingSignal | None:
            if BaseTradingSignal is None:
                return None

            action_raw = str(getattr(native_signal, "action", "")).strip().upper()
            position_details = getattr(native_signal, "position_details", {}) or {}

            if action_raw.startswith("ENTER"):
                signal_type = BaseSignalType.SELL
                action = "sell_to_open"
            elif action_raw.startswith("EXIT"):
                signal_type = BaseSignalType.CLOSE
                action = "close"
            else:
                signal_type = BaseSignalType.HOLD
                action = "hold"

            confidence = float(getattr(native_signal, "ai_confidence", 0.0) or 0.0)
            strength_raw = float(getattr(native_signal, "signal_strength", 0.0) or 0.0)
            if strength_raw >= 0.8:
                strength = BaseSignalStrength.VERY_STRONG
            elif strength_raw >= 0.6:
                strength = BaseSignalStrength.STRONG
            elif strength_raw >= 0.4:
                strength = BaseSignalStrength.MODERATE
            else:
                strength = BaseSignalStrength.WEAK

            entry_price = float(position_details.get("estimated_credit") or 0.0)
            if entry_price <= 0:
                entry_price = 1.0

            max_loss = float(position_details.get("max_loss") or 0.0)
            stop_loss = max(entry_price * 2.0, max_loss if max_loss > 0 else 0.0)
            take_profit = max(entry_price * 0.5, 0.01)

            if signal_type == BaseSignalType.CLOSE:
                stop_loss = max(entry_price * 1.25, 0.01)
                take_profit = max(entry_price * 0.75, 0.01)

            timestamp = getattr(native_signal, "timestamp", None) or datetime.now(UTC)

            return BaseTradingSignal(
                signal_id=str(getattr(native_signal, "signal_id", uuid.uuid4().hex)),
                signal_type=signal_type,
                symbol=default_symbol,
                strength=strength,
                confidence=max(0.0, min(1.0, confidence)),
                entry_price=float(entry_price),
                stop_loss=float(stop_loss),
                take_profit=float(take_profit),
                position_size=max(1, int(position_details.get("contracts") or 1)),
                timestamp=timestamp,
                expires_at=timestamp + timedelta(minutes=10),
                metadata={
                    "strategy_id": "evolved_credit_spread",
                    "strategy_type": "evolved_credit_spread",
                    "action": action,
                    "native_action": action_raw,
                    "ai_confidence": confidence,
                    "signal_strength": strength_raw,
                    "position_details": position_details,
                },
            )

        def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
            if self._core is None or BaseTradingSignal is None:
                return []

            try:
                d18_market_data = self._to_d18_market_data(market_data)
                analysis = self._core.analyze_market(d18_market_data)
                native_signals = self._core.generate_signals(analysis)
            except Exception as exc:
                self.logger.error("EvolvedCreditSpreadAdapter signal generation failed: %s", exc, exc_info=True)
                return []

            mapped: list[BaseTradingSignal] = []
            for native in native_signals or []:
                signal = self._to_base_signal(native)
                if signal is not None:
                    mapped.append(signal)
            return mapped

        def validate_signal(self, signal: Any) -> bool:
            return (
                signal is not None
                and getattr(signal, "symbol", "") == "SPY"
                and float(getattr(signal, "confidence", 0.0) or 0.0) >= 0.5
                and int(getattr(signal, "position_size", 0) or 0) > 0
            )

        def calculate_position_size(self, signal: Any) -> int:
            try:
                return max(1, int(getattr(signal, "position_size", 1) or 1))
            except Exception:
                return 1

        def should_exit_position(self, position: Any, market_data: pd.DataFrame) -> tuple[bool, str]:
            return False, ""


    class VIXHedgingAdapter(BaseStrategy):
        """Adapter to expose D28 strategy through the BaseStrategy contract."""

        def __init__(self, name=None, event_manager=None, risk_profile=None, config=None):
            super().__init__(
                name=name or "VIXHedging",
                event_manager=event_manager,
                risk_profile=risk_profile,
                config=config,
                strategy_type="vix_hedging",
            )
            vix_hedging_core = _optional_strategy(
                "Spyder.SpyderD_Strategies.SpyderD28_VIXHedging",
                "VIXHedgingStrategy",
            )
            self._core = vix_hedging_core() if vix_hedging_core else None

        @staticmethod
        def _extract_last(data: pd.DataFrame, candidates: list[str], default: float) -> float:
            for col in candidates:
                if col in data.columns and len(data[col].dropna()) > 0:
                    return float(data[col].dropna().iloc[-1])
            return default

        def _action_to_signal(self, action_value: str) -> tuple[Any, str]:
            normalized = action_value.strip().lower()
            if normalized == "add_hedge":
                return BaseSignalType.BUY, "buy_to_open"
            if normalized in {"reduce_hedge", "remove_hedge", "harvest_premium"}:
                return BaseSignalType.SELL, "sell_to_close"
            return BaseSignalType.HOLD, "hold"

        def _recommendation_to_signal(
            self,
            recommendation: Any,
            market_data: pd.DataFrame,
            portfolio_value: float,
        ) -> BaseTradingSignal | None:
            if BaseTradingSignal is None:
                return None

            action_obj = getattr(recommendation, "action", "maintain")
            action_value = str(getattr(action_obj, "value", action_obj))
            signal_type, action = self._action_to_signal(action_value)
            if signal_type == BaseSignalType.HOLD:
                return None

            target_ratio = float(getattr(recommendation, "portfolio_hedge_ratio", 0.0) or 0.0)
            notional = float(getattr(recommendation, "notional_value", 0.0) or 0.0)
            expected_cost = float(getattr(recommendation, "expected_cost", 0.0) or 0.0)
            expected_protection = float(getattr(recommendation, "expected_protection", 0.0) or 0.0)
            rationale = str(getattr(recommendation, "rationale", ""))

            symbol = "SPY"
            hedge_type_obj = getattr(recommendation, "hedge_type", "")
            hedge_type = str(getattr(hedge_type_obj, "value", hedge_type_obj)).lower()
            if "vix" in hedge_type:
                symbol = "VIX"

            qty = max(1, int(round(notional / max(portfolio_value * 0.01, 1000.0))))
            reference_price = self._extract_last(market_data, [symbol, "SPY", "close", "Close"], 20.0)
            entry_price = max(0.01, expected_cost / max(qty, 1))

            if signal_type == BaseSignalType.BUY:
                stop_loss = max(entry_price * 0.6, 0.01)
                take_profit = max(entry_price * 1.8, entry_price + 0.01)
            else:
                stop_loss = max(entry_price * 1.5, 0.01)
                take_profit = max(entry_price * 0.5, 0.01)

            confidence = 0.75 if signal_type == BaseSignalType.BUY else 0.65
            timestamp = datetime.now(UTC)
            return BaseTradingSignal(
                signal_id=f"VIXHEDGE_{timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
                signal_type=signal_type,
                symbol=symbol,
                strength=BaseSignalStrength.MODERATE,
                confidence=confidence,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                position_size=qty,
                timestamp=timestamp,
                expires_at=timestamp + timedelta(minutes=15),
                metadata={
                    "strategy_id": "vix_hedging",
                    "strategy_type": "vix_hedging",
                    "action": action,
                    "hedge_type": hedge_type,
                    "urgency": str(getattr(recommendation, "urgency", "")),
                    "target_hedge_ratio": target_ratio,
                    "notional_value": notional,
                    "expected_cost": expected_cost,
                    "expected_protection": expected_protection,
                    "reference_price": reference_price,
                    "rationale": rationale,
                },
            )

        def generate_signals(self, market_data: pd.DataFrame) -> list[Any]:
            if self._core is None or BaseTradingSignal is None:
                return []

            portfolio_value = float(getattr(self.risk_profile, "account_size", 100000.0) or 100000.0)
            current_hedge_ratio = float((self.config or {}).get("current_hedge_ratio", 0.0) or 0.0)
            risk_tolerance = str((self.config or {}).get("risk_tolerance", "moderate"))

            try:
                recommendation = self._core.get_hedge_recommendation(
                    portfolio_value=portfolio_value,
                    current_hedge_ratio=current_hedge_ratio,
                    risk_tolerance=risk_tolerance,
                )
            except Exception as exc:
                self.logger.error("VIXHedgingAdapter recommendation failed: %s", exc, exc_info=True)
                return []

            signal = self._recommendation_to_signal(recommendation, market_data, portfolio_value)
            return [signal] if signal is not None else []

        def validate_signal(self, signal: Any) -> bool:
            return (
                signal is not None
                and str(getattr(signal, "symbol", "")).strip() != ""
                and float(getattr(signal, "confidence", 0.0) or 0.0) >= 0.5
                and int(getattr(signal, "position_size", 0) or 0) > 0
            )

        def calculate_position_size(self, signal: Any) -> int:
            try:
                return max(1, int(getattr(signal, "position_size", 1) or 1))
            except Exception:
                return 1

        def should_exit_position(self, position: Any, market_data: pd.DataFrame) -> tuple[bool, str]:
            return False, ""

    # Event management
    from Spyder.SpyderA_Core.SpyderA05_EventManager import (
        EventManager,
        Event,
        EventType,
        EventPriority,
        get_event_manager,
    )

    SPYDER_MODULES_AVAILABLE = True
except ImportError as e:
    logging.critical(
        "CRITICAL — D31 soft-import failed; strategy signal routing is DISABLED: %s. "
        "Set SPYDER_STRICT_IMPORTS=1 to raise on startup.",
        e,
    )
    import os as _os
    if _os.environ.get("SPYDER_STRICT_IMPORTS") == "1":
        raise
    SPYDER_MODULES_AVAILABLE = False
    _record_risk_rejection = None  # type: ignore[assignment]

    # Stub out names that __init__ and methods reference directly so the class
    # can be constructed even when soft imports fail.
    SpyderLogger = None  # type: ignore[assignment]
    SpyderErrorHandler = None  # type: ignore[assignment]
    TradingCalendar = None  # type: ignore[assignment]
    BaseStrategy = object  # type: ignore[assignment,misc]
    EventManager = None  # type: ignore[assignment]
    Event = None  # type: ignore[assignment]
    EventType = None  # type: ignore[assignment]
    EventPriority = None  # type: ignore[assignment]
    get_event_manager = None  # type: ignore[assignment]

    # Fallback enums
    class StrategyState(Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"
        PAUSED = "paused"
        ERROR = "error"

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Portfolio management
# Three-slot concurrency model: keep room for one duplicate-blocked strategy
# plus up to two different active strategy types, including a Mark 0DTE slot
# when permitted by the overlay horizon contract below.
# Override via env: SPYDER_MAX_CONCURRENT_STRATEGIES, SPYDER_MAX_ACTIVE_HORIZON_BUCKETS.
MAX_CONCURRENT_STRATEGIES = 3
MAX_ACTIVE_HORIZON_BUCKETS = 2  # one ultra_short (0DTE/1DTE) + one short/swing
# v9 §10.4 dispatch-state pill (G05 DISPATCH badge): recency window in seconds
# for FLOWING/BLOCKED/ERROR classification. Beyond this, state collapses to IDLE.
DISPATCH_STATE_RECENCY_S = 120.0
DEFAULT_BASE_CAPITAL = 100000  # $100K base allocation
REBALANCE_FREQUENCY_MINUTES = 30  # Rebalance every 30 minutes
STRATEGY_HEALTH_CHECK_INTERVAL = 60  # Check health every minute
INITIAL_STRATEGY_ACTIVATION_DEFER_SECONDS = 0.5

# Performance thresholds
MIN_SHARPE_RATIO = 0.5  # Minimum Sharpe for active strategies
MAX_DRAWDOWN_THRESHOLD = 0.15  # 15% maximum drawdown
CORRELATION_THRESHOLD = 0.7  # Maximum strategy correlation
PERFORMANCE_LOOKBACK_DAYS = 30  # Days for performance analysis

# Market regime detection
VOLATILITY_REGIME_LOOKBACK = 20  # Days for volatility regime
TREND_DETECTION_PERIODS = [5, 10, 20]  # Moving average periods
VIX_REGIME_THRESHOLDS = {'low': 15, 'normal': 20, 'high': 30, 'extreme': 40}

# Per-symbol rolling tick buffer used by _classify_market_regime_unified to
# compute underlying EMA50 / ATR14 and VIX EMA50. Sized to comfortably cover the
# longest indicator window with headroom; bounded to keep cache memory cheap.
_MARKET_TICK_BUFFER = 200

# Strategy allocation limits
MAX_STRATEGY_ALLOCATION = 0.4  # Maximum 40% to any single strategy
MIN_STRATEGY_ALLOCATION = 0.05  # Minimum 5% allocation
ALLOCATION_ADJUSTMENT_STEP = 0.02  # 2% adjustment steps

# Risk management
PORTFOLIO_VAR_LIMIT = 0.02  # 2% daily VaR limit
CONCENTRATION_LIMIT = 0.6  # Maximum 60% in any strategy type
KELLY_FRACTION_CAP = 0.25  # Maximum 25% Kelly allocation

# ==============================================================================
# PROMETHEUS TELEMETRY — SIGNAL DROP COUNTERS (I-4)
# ==============================================================================
# Lightweight counters for visibility into silent signal drops.  Uses
# prometheus_client if available; falls back to no-op stubs.
_PROM_SIGNALS_DROPPED = None
_PROM_SUBSCRIPTIONS_ACTIVE = None
try:
    from prometheus_client import Counter as _PCounter, Gauge as _PGauge  # type: ignore[import]
    try:
        _PROM_SIGNALS_DROPPED = _PCounter(
            "spyder_signals_dropped_total",
            "Signals silently dropped in D31 _on_strategy_signal before dispatch",
            ["stage", "reason"],
        )
    except ValueError:
        # Already registered (e.g., module reloaded in tests) — retrieve existing.
        from prometheus_client import REGISTRY as _PROM_REGISTRY  # type: ignore[import]
        _PROM_SIGNALS_DROPPED = _PROM_REGISTRY._names_to_collectors.get(  # type: ignore[attr-defined]
            "spyder_signals_dropped_total"
        )
    try:
        _PROM_SUBSCRIPTIONS_ACTIVE = _PGauge(
            "spyder_subscriptions_active",
            "Number of STRATEGY_SIGNAL subscriptions registered by D31",
        )
    except ValueError:
        from prometheus_client import REGISTRY as _PROM_REGISTRY  # type: ignore[import]
        _PROM_SUBSCRIPTIONS_ACTIVE = _PROM_REGISTRY._names_to_collectors.get(  # type: ignore[attr-defined]
            "spyder_subscriptions_active"
        )
except Exception:
    pass  # prometheus_client not installed — counters disabled


def _count_drop(stage: str, reason: str) -> None:
    """Increment the signals-dropped counter if Prometheus is available."""
    if _PROM_SIGNALS_DROPPED is not None:
        try:
            _PROM_SIGNALS_DROPPED.labels(stage=stage, reason=reason).inc()
        except Exception:
            pass


def _record_risk_rejection_metric(strategy: str, rejection_reason: str) -> None:
    """Emit broker-layer rejection telemetry without importing broker surfaces at startup."""
    try:
        from Spyder.SpyderB_Broker.SpyderB15_PrometheusMetrics import record_risk_rejection
    except ImportError:
        return

    try:
        record_risk_rejection(strategy=strategy, rejection_reason=rejection_reason)
    except Exception:
        pass

# ==============================================================================
# ENUMS
# ==============================================================================

class OrchestrationMode(Enum):
    """Strategy orchestration modes"""
    CONSERVATIVE = "conservative"  # Lower risk, fewer strategies
    BALANCED = "balanced"         # Moderate risk and diversification
    AGGRESSIVE = "aggressive"     # Higher risk, more strategies
    ADAPTIVE = "adaptive"         # ML-driven dynamic allocation

class MarketRegime(Enum):
    """Market regime classifications"""
    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    SIDEWAYS_LOW_VOL = "sideways_low_vol"
    SIDEWAYS_HIGH_VOL = "sideways_high_vol"
    CRISIS = "crisis"
    RECOVERY = "recovery"
    EVENT_TRANSITION = "event_transition"


_D31_REGIME_POLICY_KEYS = {
    "bull_trend",
    "bear_trend",
    "range_calm",
    "high_vol_mean_reversion",
    "crisis_turbulent",
    "event_transition",
}

_D31_REGIME_POLICY_ALIASES = {
    "bull": "bull_trend",
    "strong_bull": "bull_trend",
    "bear": "bear_trend",
    "strong_bear": "bear_trend",
    "neutral": "range_calm",
    "bull_low_vol": "bull_trend",
    "bull_high_vol": "high_vol_mean_reversion",
    "bear_low_vol": "bear_trend",
    "bear_high_vol": "crisis_turbulent",
    "sideways_low_vol": "range_calm",
    "sideways_high_vol": "high_vol_mean_reversion",
    "crisis": "crisis_turbulent",
    "recovery": "high_vol_mean_reversion",
    "low_volatility": "bull_trend",
    "unknown": "crisis_turbulent",
}

_D31_EXECUTION_GATE_LABELS = {
    "bull_trend": "BULL TREND",
    "bear_trend": "BEAR TREND",
    "range_calm": "RANGE CALM",
    "high_vol_mean_reversion": "HIGH VOL",
    "crisis_turbulent": "CRISIS",
    "event_transition": "EVENT",
}

class AllocationMethod(Enum):
    """Portfolio allocation methods"""
    EQUAL_WEIGHT = "equal_weight"
    PERFORMANCE_BASED = "performance_based"
    RISK_PARITY = "risk_parity"
    KELLY_CRITERION = "kelly_criterion"
    ADAPTIVE_ML = "adaptive_ml"
    MARKET_REGIME = "market_regime"

class RebalanceReason(Enum):
    """Reasons for portfolio rebalancing"""
    SCHEDULED = "scheduled"
    PERFORMANCE_DRIFT = "performance_drift"
    RISK_BREACH = "risk_breach"
    STRATEGY_HEALTH = "strategy_health"
    MARKET_REGIME_CHANGE = "market_regime_change"
    CORRELATION_SPIKE = "correlation_spike"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class StrategyAllocation:
    """Individual strategy allocation information"""
    strategy_id: str
    strategy_name: str
    strategy_type: str
    horizon_bucket: str
    allocated_capital: float
    target_allocation: float
    current_allocation: float
    performance_score: float
    risk_score: float
    health_score: float
    last_rebalance: datetime
    allocation_history: list[tuple[datetime, float]] = field(default_factory=list)

@dataclass
class MarketRegimeData:
    """Market regime analysis data"""
    current_regime: MarketRegime
    regime_confidence: float
    volatility_percentile: float
    trend_strength: float
    vix_level: float
    regime_duration_days: int
    last_regime_change: datetime
    regime_history: list[tuple[datetime, MarketRegime]] = field(default_factory=list)

@dataclass
class PortfolioMetrics:
    """Portfolio-level performance metrics"""
    total_capital: float
    allocated_capital: float
    available_capital: float
    total_pnl: float
    daily_pnl: float
    portfolio_var: float
    portfolio_sharpe: float
    portfolio_sortino: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    active_strategies: int
    total_positions: int
    correlation_matrix: pd.DataFrame | None = None

@dataclass
class StrategyConflict:
    """Strategy conflict detection"""
    strategy_ids: list[str]
    conflict_type: str
    severity: str  # 'low', 'medium', 'high'
    description: str
    resolution_action: str
    detected_at: datetime

@dataclass
class RebalanceEvent:
    """Portfolio rebalancing event"""
    timestamp: datetime
    reason: RebalanceReason
    previous_allocations: dict[str, float]
    new_allocations: dict[str, float]
    capital_movements: dict[str, float]
    expected_impact: dict[str, float]
    execution_status: str = "pending"

# ==============================================================================
# STRATEGY ORCHESTRATOR CORE ENGINE
# ==============================================================================

class StrategyOrchestrator:
    """
    Master strategy coordination and portfolio management engine.

    This class orchestrates multiple trading strategies simultaneously with:
    - Dynamic portfolio allocation based on performance and market conditions
    - Strategy conflict resolution and optimization
    - Market regime detection for intelligent strategy selection
    - Real-time performance attribution and health monitoring
    - Risk management at portfolio level
    - Integration with connectivity and execution systems
    """

    def __init__(self,
                 base_capital: float = DEFAULT_BASE_CAPITAL,
                 orchestration_mode: OrchestrationMode = OrchestrationMode.BALANCED,
                 allocation_method: AllocationMethod = AllocationMethod.PERFORMANCE_BASED,
                 connectivity_manager: Any | None = None,
                 event_manager: EventManager | None = None,
                 regime_engine: Any | None = None):
        """
        Initialize Strategy Orchestrator.

        Args:
            base_capital: Base capital for allocation
            orchestration_mode: Operating mode for strategy coordination
            allocation_method: Method for portfolio allocation
            connectivity_manager: Connectivity management integration
            event_manager: Event management system
            regime_engine: Optional L09 UnifiedRegimeEngine instance for ML-driven regime detection
        """
        # Setup logging and error handling
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None

        # Core configuration
        self.base_capital = base_capital
        self.orchestration_mode = orchestration_mode
        self.allocation_method = allocation_method
        self.max_concurrent_strategies = max(
            1,
            int(os.environ.get("SPYDER_MAX_CONCURRENT_STRATEGIES", str(MAX_CONCURRENT_STRATEGIES)))
        )
        self.max_active_horizon_buckets = max(
            1,
            int(os.environ.get("SPYDER_MAX_ACTIVE_HORIZON_BUCKETS", str(MAX_ACTIVE_HORIZON_BUCKETS)))
        )
        if str(os.environ.get("SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            self.logger.warning(
                "SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT is experimental; D31 only admits "
                "a third ultra_short PivotMeanReversion slot and still requires the "
                "overlay risk gate before dispatch"
            )
        self._startup_cache_seed_enabled = str(
            os.environ.get("SPYDER_ENABLE_STARTUP_CACHE_SEED", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._regime_source_symbol = (
            str(os.environ.get("SPYDER_UNDERLYING_SYMBOL", "SPX")).strip().upper() or "SPX"
        )
        self.connectivity_manager = connectivity_manager
        self.event_manager = event_manager
        self._l09_engine: Any | None = regime_engine          # L09 UnifiedRegimeEngine (optional)
        self._last_l09_confidence: float = 0.0               # confidence from last L09 call
        self._last_l09_consensus: Any | None = None          # latest L09 consensus payload
        self._d30_selector: Any | None = None                # D30 RegimeGatedSelector (lazy)
        self._d30_selector_init_attempted: bool = False
        self._last_selector_feature_flag: str | None = None
        if self.event_manager is None:
            try:
                _gem = get_event_manager  # type: ignore[name-defined]  # noqa: F821
                if callable(_gem):
                    self.event_manager = _gem()
            except NameError:
                pass
            if self.event_manager is None:
                try:
                    from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager as _gem2  # noqa: E501
                    self.event_manager = _gem2()
                except Exception:
                    self.event_manager = None

        self.lean_mode = self._resolve_lean_mode()
        self.lean_strategy_allowlist = {
            "BullPutSpread",
            "BullPutSpreadStrategy",
            "BearCallSpread",
            "BearCallSpreadStrategy",
            "ZeroHFT",
            "ZeroHFTStrategy",
            "Butterfly",
            "ButterflyStrategy",
            "IronCondor",
            "IronCondorStrategy",
            "IronButterfly",
            "IronButterflyStrategy",
            "BrokenWingButterfly",
            "BrokenWingButterflyStrategy",
        }
        # Opt-in extension: D34 PivotMeanReversion. Gated by env flag so the
        # default lean posture remains the baseline lean allowlist contract; setting
        # SPYDER_ENABLE_PIVOT_MEAN_REVERSION=true allows D30 to swap RANGE →
        # PivotMeanReversion when the S08 pivot signal is firing, otherwise
        # falls back to IronCondor for the same regime.
        if os.getenv("SPYDER_ENABLE_PIVOT_MEAN_REVERSION", "").strip().lower() in {
            "1", "true", "yes", "on", "y",
        }:
            self.lean_strategy_allowlist.update({
                "PivotMeanReversion",
                "PivotMeanReversionStrategy",
            })
        if os.getenv("SPYDER_ENABLE_BULL_CALL_SPREAD", "").strip().lower() in {
            "1", "true", "yes", "on", "y",
        }:
            self.lean_strategy_allowlist.update({
                "BullCallSpread",
                "BullCallSpreadStrategy",
            })
        if os.getenv("SPYDER_ENABLE_BEAR_PUT_SPREAD", "").strip().lower() in {
            "1", "true", "yes", "on", "y",
        }:
            self.lean_strategy_allowlist.update({
                "BearPutSpread",
                "BearPutSpreadStrategy",
            })
        if os.getenv("SPYDER_ENABLE_BULLISH_STRANGLE", "").strip().lower() in {
            "1", "true", "yes", "on", "y",
        }:
            self.lean_strategy_allowlist.update({
                "BullishStrangle",
                "BullishStrangleStrategy",
            })
        if os.getenv("SPYDER_ENABLE_PUT_CREDIT_SPREAD_7", "").strip().lower() in {
            "1", "true", "yes", "on", "y",
        }:
            self.lean_strategy_allowlist.update({
                "PutCreditSpread7",
                "PutCreditSpread7Strategy",
            })
        if self._paper_calendar_spread_routing_flag_enabled():
            self.lean_strategy_allowlist.update({
                "CalendarSpread",
                "CalendarSpreadStrategy",
            })
        self._apply_env_allowed_strategies_override()

        # Portfolio state
        self.active_strategies: dict[str, BaseStrategy] = {}
        self.strategy_allocations: dict[str, StrategyAllocation] = {}
        self.available_strategies: dict[str, Any] = {}
        self.paused_strategies: set[str] = set()
        # B3 (v15): lock protecting active_strategies and paused_strategies.
        # Both the orchestration thread and external callers (add/remove/pause/resume)
        # mutate these sets; without a lock the dicts can be corrupted under
        # concurrent access.
        self._strategies_lock = threading.RLock()
        self._strategy_configuration_lock = threading.Lock()

        # Market analysis
        self.market_regime = MarketRegimeData(
            current_regime=MarketRegime.SIDEWAYS_LOW_VOL,
            regime_confidence=0.0,
            volatility_percentile=50.0,
            trend_strength=0.0,
            vix_level=20.0,
            regime_duration_days=0,
            last_regime_change=datetime.now(UTC)
        )

        # Performance tracking
        self.portfolio_metrics = PortfolioMetrics(
            total_capital=base_capital,
            allocated_capital=0.0,
            available_capital=base_capital,
            total_pnl=0.0,
            daily_pnl=0.0,
            portfolio_var=0.0,
            portfolio_sharpe=0.0,
            portfolio_sortino=0.0,
            max_drawdown=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            active_strategies=0,
            total_positions=0
        )

        # Monitoring and control
        self.orchestration_active = False
        self.last_rebalance = datetime.now(UTC)
        self.rebalance_history: list[RebalanceEvent] = []
        self.strategy_conflicts: list[StrategyConflict] = []

        # Threading
        self.orchestration_thread = None
        self.monitoring_thread = None
        self.scheduled_strategy_thread = None
        self.shutdown_event = threading.Event()
        self._scheduled_strategy_due_at: dict[str, float] = {}
        self._scheduled_strategy_lock = threading.Lock()
        self._scheduled_strategy_wakeup = threading.Event()
        self._initial_strategy_activation_pending = False
        self._initial_strategy_activation_ready_at = 0.0
        self._initial_strategy_activation_running = False
        self._initial_strategy_activation_lock = threading.Lock()
        self._paper_startup_regime_engine_pending = False

        # Live engine reference for order dispatch (set via set_live_engine)
        self._live_engine = None
        # OrderManager reference for mid-price walk execution (set via set_order_manager)
        self._order_manager: Any = None
        # VIXAnalyzer for live VIX reads in regime detection (set via set_vix_analyzer)
        self._vix_analyzer: Any | None = None
        # RiskManager — resolved once and cached to avoid per-signal import overhead
        self.risk_manager: Any | None = None
        # EntryFilters + S07 market conditions are resolved lazily on the hot path
        # so D31 can apply trust-policy gating without widening startup failures.
        self._entry_filter_gate: Any | None = None
        self._metrics_orchestrator: Any | None = None
        self._live_options_metrics_snapshot: dict[str, float | None] = {}
        self._live_options_metrics_loaded_monotonic: float = 0.0
        # S18 economic calendar — lazily resolved for eco stand-down gate
        self._eco_calendar: Any | None = None
        self._eco_calendar_resolved: bool = False
        self._regime_policy: dict[str, Any] | None = None
        self._session_window_policy: dict[str, Any] = self._load_session_window_policy()
        self._pin_risk_window_state: str = "inactive"
        self._pin_risk_last_emit_ts: float = 0.0

        # B5: Two distinct pause flags so DATA_FRESH can clear the stale-data
        # pause without also clearing a KILL_SWITCH halt (which is sticky and
        # requires a restart to clear).
        self._paused_kill: bool = False   # set by KILL_SWITCH; sticky — only restart clears
        self._paused_stale: bool = False  # set by DATA_STALE; cleared by DATA_FRESH

        # Signal-flow visibility (runtime-only counters; complements Prometheus).
        # These counters make it easy to see why trades are not being placed
        # without needing external metrics tooling.
        self._signal_flow_counts: dict[str, int] = {
            "seen": 0,
            "dropped": 0,
            "approved": 0,
            "dispatch_submitted": 0,
            "dispatch_rejected": 0,
        }
        self._signal_drop_reasons: dict[str, int] = defaultdict(int)
        self._signal_flow_log_interval_s: float = float(
            os.getenv("SPYDER_D31_SIGNAL_FLOW_LOG_INTERVAL_S", "300")
        )
        self._signal_flow_last_log_monotonic: float = time.monotonic()
        try:
            self._pending_entry_reservation_ttl_s: float = max(
                5.0,
                float(os.getenv("SPYDER_D31_PENDING_ENTRY_RESERVATION_TTL_S", "90")),
            )
        except (TypeError, ValueError):
            self._pending_entry_reservation_ttl_s = 90.0
        try:
            self._pending_exit_reservation_ttl_s: float = max(
                1.0,
                float(os.getenv("SPYDER_D31_PENDING_EXIT_RESERVATION_TTL_S", "15")),
            )
        except (TypeError, ValueError):
            self._pending_exit_reservation_ttl_s = 15.0
        try:
            self._duplicate_entry_warning_interval_s: float = max(
                1.0,
                float(os.getenv("SPYDER_D31_DUPLICATE_ENTRY_WARNING_INTERVAL_S", "300")),
            )
        except (TypeError, ValueError):
            self._duplicate_entry_warning_interval_s = 300.0
        try:
            self._manual_close_reentry_embargo_s: float = max(
                1.0,
                float(os.getenv("SPYDER_D31_MANUAL_CLOSE_REENTRY_EMBARGO_S", "300")),
            )
        except (TypeError, ValueError):
            self._manual_close_reentry_embargo_s = 300.0
        self._pending_entry_reservations: dict[tuple[str, str], float] = {}
        self._pending_entry_reservations_lock = threading.Lock()
        self._pending_exit_reservations: dict[tuple[str, str], float] = {}
        self._pending_exit_reservations_lock = threading.Lock()
        self._duplicate_entry_warning_last_monotonic: dict[tuple[str, str], float] = {}
        self._manual_close_reentry_embargoes: dict[tuple[str, str], float] = {}
        self._manual_close_reentry_embargo_lock = threading.Lock()
        self._signal_drop_audit_enabled: bool = str(
            os.getenv("SPYDER_D31_SIGNAL_DROP_AUDIT", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}
        self._signal_drop_audit_dir: str = str(
            os.getenv("SPYDER_D31_SIGNAL_DROP_AUDIT_DIR", os.path.join("logs", "decisions"))
        )
        self._signal_drop_audit_partition_mode: str = str(
            os.getenv("SPYDER_D31_SIGNAL_DROP_AUDIT_PARTITION_MODE", "auto")
        ).strip().lower()
        self._audit_run_mode: str = "unknown"
        self._audit_source_context: str = "unknown"
        self._audit_session_id: str = f"d31-{uuid.uuid4().hex[:12]}"
        self._paper_midwalk_bypass_marker_emitted: bool = False
        self._last_selector_outcome_audit_fingerprint: tuple[Any, ...] | None = None

        # v9 §10.4: state powering G05 DISPATCH pill. All timestamps are
        # time.monotonic() so they are immune to wall-clock jumps. Lock-free:
        # writes are single-statement and reads tolerate transient None.
        self._last_drop_event: dict[str, Any] | None = None
        self._last_dispatch_ok_ts: float | None = None
        self._last_dispatch_strategy: str | None = None
        self._last_dispatch_error: dict[str, Any] | None = None

        # Y02 StrategyPilotAgent advisory: tracks the last time each strategy type
        # received an LLM-validated approval on the agent bus.  Updated by
        # _on_y02_validated_signal(); consulted (advisory-only) in the signal
        # dispatch path to surface patterns of Y02 disapproval in the logs.
        self._y02_advisory: dict[str, Any] = {}  # strategy_type → last approval datetime
        self._agent_handoff_shadow_validation_enabled = str(
            os.getenv("SPYDER_AGENT_HANDOFF_SHADOW_VALIDATION", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}
        self._agent_handoff_shadow_validation_counts: dict[str, int] = defaultdict(int)
        self._agent_handoff_policy: dict[str, Any] | None = None
        self._agent_handoff_enforcement_counts: dict[str, int] = defaultdict(int)

        # Market data cache (replaced entirely each update, not appended)
        self.market_data_cache = {}
        self.last_market_update = None

        # v27 SPEC-12: dedicated thread pool for non-blocking dispatch.
        # _on_strategy_signal runs on the EventManager dispatcher thread; the
        # broker call inside _dispatch_approved_signal can take up to 30s,
        # which would freeze every other STRATEGY_SIGNAL / MARKET_DATA dispatch.
        # Routing dispatch through this pool returns the bus thread immediately.
        from concurrent.futures import ThreadPoolExecutor
        self._dispatch_executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="D31-dispatch"
        )

        # Performance attribution
        self.performance_history = deque(maxlen=1000)
        self.strategy_correlations = {}

        # Trading calendar
        try:
            self.trading_calendar = TradingCalendar() if TradingCalendar else None
        except (ImportError, TypeError, AttributeError) as e:
            # TradingCalendar not available or failed to initialize
            self.logger.debug("TradingCalendar not available: %s", e)
            self.trading_calendar = None

        # Initialize available strategies
        self._initialize_strategy_registry()

        # Setup event subscriptions
        self._setup_event_subscriptions()

        # Spec-aligned default is fail-closed on cold start. Warm-start cache
        # seeding is available as an explicit opt-in.
        if self._startup_cache_seed_enabled:
            self._seed_cache_from_disk()

        self.logger.debug(f"🎯 Strategy Orchestrator initialized - Mode: {orchestration_mode.value}, Capital: ${base_capital:,.2f}")  # noqa: E501

    def _seed_cache_from_disk(self) -> None:
        """Warm-start market_data_cache from live_data.json and <symbol>_prev_day.json.

        Reads the last known underlying/VIX prices written by G18 MarketDataWorker and
        inserts synthetic tick rows so the regime classifier has ≥2 closes
        from the very first evaluation cycle, avoiding the startup CRISIS.

        This warm-start path is intentionally opt-in via
        ``SPYDER_ENABLE_STARTUP_CACHE_SEED`` to preserve fail-closed behavior
        on cold starts by default.
        """
        from pathlib import Path as _Path
        import json as _json

        _data_dir = _Path.home() / "Projects" / "Spyder" / "market_data"
        _regime_symbol = self._regime_source_symbol

        # Try to get current underlying/VIX from live_data.json
        _underlying_last = None
        _vix_last = None
        try:
            _ld_file = _data_dir / "live_data.json"
            if _ld_file.exists():
                with open(_ld_file) as _f:
                    _ld = _json.load(_f)
                _underlying_e = _ld.get(_regime_symbol)
                _vix_e = _ld.get("VIX")
                if isinstance(_underlying_e, dict) and _underlying_e.get("last"):
                    _underlying_last = float(_underlying_e["last"])
                if isinstance(_vix_e, dict) and _vix_e.get("last"):
                    _vix_last = float(_vix_e["last"])
        except Exception:
            pass

        # Try to get prior close from <symbol>_prev_day.json
        _underlying_prev_close = None
        try:
            _pd_file = _data_dir / f"{_regime_symbol.lower()}_prev_day.json"
            if _pd_file.exists():
                with open(_pd_file) as _f:
                    _pd = _json.load(_f)
                if _pd.get("close"):
                    _underlying_prev_close = float(_pd["close"])
        except Exception:
            pass

        # Seed underlying cache with 2 entries: prev-day close + current last
        # The regime classifier needs ≥2 closes to compute change%.
        if _underlying_last is not None:
            if not isinstance(self.market_data_cache, dict):
                self.market_data_cache = {}
            _underlying_bucket = deque(maxlen=_MARKET_TICK_BUFFER)
            if _underlying_prev_close is not None:
                _underlying_bucket.append(
                    {
                        "close": _underlying_prev_close,
                        "price": _underlying_prev_close,
                        "symbol": _regime_symbol,
                    }
                )
            else:
                # No prev-day file: insert a synthetic previous tick slightly
                # below current so the regime can compute a direction.
                _underlying_bucket.append(
                    {
                        "close": _underlying_last * 0.999,
                        "price": _underlying_last * 0.999,
                        "symbol": _regime_symbol,
                    }
                )
            _underlying_bucket.append(
                {"close": _underlying_last, "price": _underlying_last, "symbol": _regime_symbol}
            )
            self.market_data_cache[_regime_symbol] = _underlying_bucket
            self.logger.debug(
                "D31 cache seeded from disk: %s prev=%.2f current=%.2f",
                _regime_symbol,
                _underlying_bucket[0]["close"],
                _underlying_last,
            )

        # Seed VIX cache with a single entry (prevents VIX-empty CRISIS)
        if _vix_last is not None:
            _vix_bucket = deque(maxlen=_MARKET_TICK_BUFFER)
            _vix_bucket.append({"close": _vix_last, "price": _vix_last, "symbol": "VIX"})
            self.market_data_cache["VIX"] = _vix_bucket

    def _recover_cache_if_cold(self) -> None:
        """Re-seed market_data_cache from live_data.json when regime cache is cold.

        G18 (MarketDataWorker) writes fresh quotes to live_data.json every 10 s
        but does NOT publish EventType.MARKET_DATA events on the A05 event bus.
        In dashboard-only mode this means D31's market_data_cache[<underlying>] never
        gets any entries and the regime classifier fails closed to CRISIS for the
        entire session.

        This method bridges that gap: if the regime-symbol cache has fewer than 2 closes
        (the minimum required for regime classification), it reads the current
        live_data.json written by G18 and seeds the cache identically to the
        startup warm-start path.  Throttled to at most once every 30 s to avoid
        excessive disk I/O on every regime evaluation cycle.
        """
        regime_symbol = self._regime_source_symbol
        regime_ticks = self.market_data_cache.get(regime_symbol, [])
        regime_closes = [
            self._coerce_float(t.get("close", t.get("price")))
            for t in regime_ticks
            if isinstance(t, dict)
        ]
        if len([c for c in regime_closes if c is not None]) >= 2:
            return  # Cache is warm — nothing to do

        now_mono = time.monotonic()
        last = getattr(self, "_last_disk_reseed_monotonic", 0.0)
        if now_mono - last < 30.0:
            return  # Throttle: tried within last 30 s

        self._last_disk_reseed_monotonic = now_mono
        self._seed_cache_from_disk()

    def _load_live_options_metrics_snapshot(self) -> dict[str, float | None]:
        """Read fresh ATM_IV/IVR hints from disk with a short hot-path cache."""
        now = time.monotonic()
        if (now - self._live_options_metrics_loaded_monotonic) < 5.0:
            return dict(self._live_options_metrics_snapshot)

        snapshot: dict[str, float | None] = {"iv": None, "iv_rank": None}
        try:
            from pathlib import Path as _Path
            import json as _json
            max_snapshot_age_sec = 180.0

            def _snapshot_is_fresh(*, _saved_at: Any = None, _file: Any = None) -> bool:
                _saved_ts = self._coerce_float(_saved_at)
                if _saved_ts is not None:
                    return (time.time() - _saved_ts) <= max_snapshot_age_sec
                if _file is None:
                    return False
                try:
                    return (time.time() - float(_file.stat().st_mtime)) <= max_snapshot_age_sec
                except OSError:
                    return False

            def _metric_entry_value(_entry: Any) -> float | None:
                if not isinstance(_entry, dict) or bool(_entry.get("stale")):
                    return None
                for _field in ("value", "last"):
                    _value = self._coerce_float(_entry.get(_field))
                    if _value is not None:
                        return _value
                return None

            def _extract_options_metrics(
                _payload: Any,
                *,
                _saved_at: Any = None,
                _file: Any = None,
            ) -> None:
                if not isinstance(_payload, dict) or not _snapshot_is_fresh(_saved_at=_saved_at, _file=_file):
                    return
                _atm_iv_entry = _payload.get("ATM_IV")
                _ivr_entry = _payload.get("IVR")

                if snapshot["iv"] is None:
                    _atm_iv_value = _metric_entry_value(_atm_iv_entry)
                    if _atm_iv_value is not None:
                        snapshot["iv"] = _atm_iv_value / 100.0 if _atm_iv_value > 1.0 else _atm_iv_value

                if snapshot["iv_rank"] is None:
                    _ivr_value = _metric_entry_value(_ivr_entry)
                    if _ivr_value is not None:
                        snapshot["iv_rank"] = _ivr_value

            _data_dir = _Path.home() / "Projects" / "Spyder" / "market_data"
            _metrics_file = _data_dir / "overview_metrics_snapshot.json"
            if _metrics_file.exists():
                with open(_metrics_file, encoding="utf-8") as _f:
                    _payload = _json.load(_f)
                _metrics_payload = _payload.get("metrics") if isinstance(_payload, dict) else None
                _saved_at = _payload.get("_saved_at") if isinstance(_payload, dict) else None
                _extract_options_metrics(_metrics_payload, _saved_at=_saved_at, _file=_metrics_file)

            for _file_name, _nested_key in (("live_data.json", None), ("dashboard_snapshot.json", "data")):
                if snapshot["iv"] is not None and snapshot["iv_rank"] is not None:
                    break
                _file = _data_dir / _file_name
                if not _file.exists():
                    continue
                with open(_file, encoding="utf-8") as _f:
                    _payload = _json.load(_f)
                _saved_at = _payload.get("_saved_at") if isinstance(_payload, dict) else None
                if _nested_key and isinstance(_payload, dict):
                    _payload = _payload.get(_nested_key)
                _extract_options_metrics(_payload, _saved_at=_saved_at, _file=_file)
        except Exception:
            snapshot = {"iv": None, "iv_rank": None}

        self._live_options_metrics_snapshot = snapshot
        self._live_options_metrics_loaded_monotonic = now
        return dict(snapshot)

    def _enrich_market_df_with_options_metrics(self, market_df: Any) -> Any:
        """Add ATM IV / IVR hints for options strategies without widening startup wiring."""
        if market_df is None or not hasattr(market_df, "columns"):
            return market_df

        options_snapshot = self._load_live_options_metrics_snapshot()
        iv_value = self._coerce_float(options_snapshot.get("iv"))
        iv_rank_value = self._coerce_float(options_snapshot.get("iv_rank"))

        if "iv" not in market_df.columns or market_df["iv"].dropna().empty:
            if iv_value is not None:
                market_df["iv"] = iv_value
            else:
                _cache = self.market_data_cache if isinstance(self.market_data_cache, dict) else {}
                _vix_bucket = _cache.get("VIX")
                if isinstance(_vix_bucket, deque) and _vix_bucket:
                    try:
                        _vix_val = _vix_bucket[-1].get("close") or _vix_bucket[-1].get("price")
                        if _vix_val is not None:
                            market_df["iv"] = float(_vix_val) / 100.0
                    except Exception:
                        pass

        if iv_rank_value is not None and ("iv_rank" not in market_df.columns or market_df["iv_rank"].dropna().empty):
            market_df["iv_rank"] = iv_rank_value

        return market_df

    def _record_signal_drop(
        self,
        stage: str,
        reason: str,
        signal: Any | None = None,
        detail: str | None = None,
        *,
        update_dispatch_state: bool = True,
    ) -> None:
        """Track why strategy signals are dropped.

        Most drops should surface through the shared DISPATCH badge. Duplicate
        entry skips are intentionally quieter: they remain audited and counted
        but should not advertise a global BLOCKED state for unrelated strategy
        slots.
        """
        _count_drop(stage, reason)
        self._signal_flow_counts["dropped"] += 1
        self._signal_drop_reasons[f"{stage}:{reason}"] += 1
        self._persist_signal_drop_audit(
            stage=stage,
            reason=reason,
            signal=signal,
            detail=detail,
        )
        if update_dispatch_state:
            # v9 §10.4: dispatch-state pill input. dispatch_exception is a
            # system error, everything else is a guardrail block.
            now_mono = time.monotonic()
            if stage == "dispatch" and reason == "dispatch_exception":
                self._last_dispatch_error = {
                    "reason": reason,
                    "detail": detail or "",
                    "monotonic_ts": now_mono,
                }
            else:
                self._last_drop_event = {
                    "stage": stage,
                    "reason": reason,
                    "monotonic_ts": now_mono,
                }
        self._log_signal_flow_summary_if_due()

    @staticmethod
    def _signal_value(signal: Any, key: str, default: Any = None) -> Any:
        """Read a field from dict/object signal payloads."""
        if isinstance(signal, dict):
            return signal.get(key, default)
        return getattr(signal, key, default)

    @staticmethod
    def _extract_pivot_block_reason(detail: str | None) -> str | None:
        """Extract ``pivot_block_reason`` from F09 detail text when present."""
        if not detail:
            return None

        marker = "pivot_block_reason="
        detail_text = str(detail)
        start = detail_text.find(marker)
        if start < 0:
            return None

        start += len(marker)
        end = detail_text.find(";", start)
        if end < 0:
            end = len(detail_text)

        reason = detail_text[start:end].strip()
        return reason or None

    def _resolve_selector_feature_flag_for_audit(self, payload: dict[str, Any]) -> str | None:
        """Resolve the feature flag that influenced the current strategy choice."""
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        candidates = [
            payload.get("selector_feature_flag"),
            metadata.get("selector_feature_flag"),
            self._last_selector_feature_flag,
        ]
        for candidate in candidates:
            text = str(candidate).strip()
            if text and text != "None":
                return text
        return None

    def _extract_pivot_signal_payload(
        self,
        signal: Any,
        market_conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Extract a normalized pivot payload from signal/market context."""
        candidates: list[Any] = []

        if isinstance(signal, dict):
            for key in ("pivot_signal", "pivot_mr_signal", "pivot"):
                candidates.append(signal.get(key))
        else:
            for key in ("pivot_signal", "pivot_mr_signal", "pivot"):
                candidates.append(getattr(signal, key, None))

        if isinstance(market_conditions, dict):
            for key in ("pivot_signal", "pivot_mr_signal", "pivot"):
                candidates.append(market_conditions.get(key))

        payload: dict[str, Any] = {}
        for candidate in candidates:
            if isinstance(candidate, dict):
                payload = candidate
                break

        if not payload and isinstance(signal, dict):
            inferred = {
                "fired": signal.get("fired"),
                "direction": signal.get("direction"),
                "score": signal.get("score"),
                "nearest_level_name": signal.get("nearest_level_name") or signal.get("nearest_level"),
                "atr_distance": signal.get("atr_distance"),
            }
            if any(value is not None for value in inferred.values()):
                payload = inferred

        if not payload:
            return {}

        return {
            "fired": payload.get("fired"),
            "direction": payload.get("direction"),
            "score": payload.get("score"),
            "nearest_level_name": payload.get("nearest_level_name") or payload.get("nearest_level"),
            "atr_distance": payload.get("atr_distance"),
        }

    def _build_signal_audit_record(
        self,
        *,
        event: str,
        stage: str,
        reason: str,
        detail: str | None,
        signal: Any | None,
    ) -> dict[str, Any]:
        """Build the structured D31 decision-audit record."""
        payload = signal if isinstance(signal, dict) else {}
        pivot_payload = self._extract_pivot_signal_payload(payload) if payload else None
        strategy_id = self._signal_value(payload, "strategy_id") or self._signal_value(payload, "strategy_name")
        detail_text = detail or ""

        return {
            "ts_utc": datetime.now(UTC).isoformat(),
            "component": "D31",
            "event": event,
            "run_mode": self._audit_run_mode,
            "source_context": self._audit_source_context,
            "session_id": self._audit_session_id,
            "stage": stage,
            "reason": reason,
            "detail": detail_text,
            "symbol": self._signal_value(payload, "symbol", ""),
            "strategy_id": strategy_id or "",
            "action": self._signal_value(payload, "action", self._signal_value(payload, "side", "")),
            "quantity": self._signal_value(payload, "quantity", 0),
            "signal_id": self._signal_value(payload, "signal_id", self._signal_value(payload, "id", "")),
            "regime": self._signal_value(payload, "regime", ""),
            "selector_feature_flag": self._resolve_selector_feature_flag_for_audit(payload),
            "pivot_block_reason": self._extract_pivot_block_reason(detail_text),
            "pivot": {
                "fired": pivot_payload.get("fired") if isinstance(pivot_payload, dict) else None,
                "direction": pivot_payload.get("direction") if isinstance(pivot_payload, dict) else None,
                "score": pivot_payload.get("score") if isinstance(pivot_payload, dict) else None,
                "nearest_level_name": pivot_payload.get("nearest_level_name") if isinstance(pivot_payload, dict) else None,
                "atr_distance": pivot_payload.get("atr_distance") if isinstance(pivot_payload, dict) else None,
            },
        }

    @staticmethod
    def _format_pivot_log_context(pivot_payload: dict[str, Any] | None) -> str:
        """Create compact, stable pivot context for logs and diagnostics."""
        if not isinstance(pivot_payload, dict) or not pivot_payload:
            return "pivot_signal=none"

        fired = pivot_payload.get("fired")
        direction = pivot_payload.get("direction")
        score = pivot_payload.get("score")
        nearest_level = pivot_payload.get("nearest_level_name")
        atr_distance = pivot_payload.get("atr_distance")

        return (
            "pivot_signal("
            f"fired={fired}, "
            f"direction={direction}, "
            f"score={score}, "
            f"nearest_level={nearest_level}, "
            f"atr_distance={atr_distance}"
            ")"
        )

    def set_decision_audit_context(
        self,
        run_mode: str | None = None,
        source_context: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Set stable run metadata attached to every decision-audit record."""
        if run_mode:
            self._audit_run_mode = str(run_mode)
        if source_context:
            self._audit_source_context = str(source_context)
        if session_id:
            self._audit_session_id = str(session_id)

    def set_startup_regime_engine_pending(self, pending: bool) -> None:
        """Mark whether paper startup is still waiting on deferred L09 attach."""
        self._paper_startup_regime_engine_pending = bool(pending)

    def _is_waiting_for_deferred_paper_regime_engine(self) -> bool:
        """Return True while SessionSupervisor paper startup is waiting on L09."""
        return (
            self._paper_startup_regime_engine_pending
            and str(self._audit_run_mode or "").strip().lower() == "paper"
            and str(self._audit_source_context or "").strip().lower() == "session_supervisor"
            and self._l09_engine is None
        )

    def _resolve_signal_audit_file_path(self, now_utc: datetime) -> str:
        """Resolve the daily decision-log path with optional run-mode partitioning.

        Partition policy:
        - ``flat``: always write to ``<base>/<YYYY-MM-DD>.jsonl``
        - ``auto`` (default): for SessionSupervisor-owned paper/live runs, write to
          ``<base>/<run_mode>/<YYYY-MM-DD>.jsonl``; otherwise keep flat path.
        """
        day_key = now_utc.strftime("%Y-%m-%d")
        base_dir = self._signal_drop_audit_dir

        if self._signal_drop_audit_partition_mode == "flat":
            return os.path.join(base_dir, f"{day_key}.jsonl")

        run_mode = str(self._audit_run_mode or "").strip().lower()
        source_ctx = str(self._audit_source_context or "").strip().lower()
        if run_mode in {"paper", "live"} and source_ctx == "session_supervisor":
            return os.path.join(base_dir, run_mode, f"{day_key}.jsonl")

        return os.path.join(base_dir, f"{day_key}.jsonl")

    def emit_decision_audit_marker(
        self,
        event: str,
        detail: str = "",
        extra_fields: dict[str, Any] | None = None,
    ) -> None:
        """Append a non-signal marker to decision logs for session boundaries."""
        if not self._signal_drop_audit_enabled:
            return
        try:
            now_utc = datetime.now(UTC)
            file_path = self._resolve_signal_audit_file_path(now_utc)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            record = {
                "ts_utc": now_utc.isoformat(),
                "component": "D31",
                "event": event,
                "detail": detail,
                "run_mode": self._audit_run_mode,
                "source_context": self._audit_source_context,
                "session_id": self._audit_session_id,
            }
            if isinstance(extra_fields, dict):
                record.update(extra_fields)
            with open(file_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception as exc:
            self.logger.debug("D31: failed to persist audit marker: %s", exc)

        if event == "session_started":
            self._purge_old_decision_logs()

    def _purge_old_decision_logs(self, retention_days: int = 7) -> None:
        """Delete decision-log JSONL files older than *retention_days* days.

        Scans the base audit directory (and one level of subdirectories for
        run-mode partitions such as ``paper/`` and ``live/``) for files whose
        name matches ``YYYY-MM-DD.jsonl`` and removes any that are strictly
        older than *retention_days* calendar days relative to today (UTC).
        """
        try:
            cutoff = datetime.now(UTC).date() - timedelta(days=retention_days)
            base_dir = self._signal_drop_audit_dir
            if not os.path.isdir(base_dir):
                return

            scan_dirs = [base_dir]
            for entry in os.scandir(base_dir):
                if entry.is_dir():
                    scan_dirs.append(entry.path)

            import re as _re
            _date_pattern = _re.compile(r"^(\d{4}-\d{2}-\d{2})\.jsonl$")
            purged = 0
            for scan_dir in scan_dirs:
                try:
                    for fname in os.listdir(scan_dir):
                        m = _date_pattern.match(fname)
                        if not m:
                            continue
                        try:
                            from datetime import date as _date
                            file_date = _date.fromisoformat(m.group(1))
                        except ValueError:
                            continue
                        if file_date < cutoff:
                            try:
                                os.remove(os.path.join(scan_dir, fname))
                                purged += 1
                            except OSError as rm_exc:
                                self.logger.debug(
                                    "D31: could not remove old decision log %s: %s",
                                    fname, rm_exc,
                                )
                except OSError:
                    pass

            if purged:
                self.logger.info(
                    "D31: purged %d decision log file(s) older than %d days",
                    purged, retention_days,
                )
        except Exception as exc:
            self.logger.debug("D31: _purge_old_decision_logs failed: %s", exc)

    def _persist_signal_drop_audit(
        self,
        stage: str,
        reason: str,
        signal: Any | None,
        detail: str | None,
    ) -> None:
        """Append structured drop diagnostics to a daily JSONL file."""
        if not self._signal_drop_audit_enabled:
            return

        try:
            now_utc = datetime.now(UTC)
            file_path = self._resolve_signal_audit_file_path(now_utc)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            record = self._build_signal_audit_record(
                event="signal_dropped",
                stage=stage,
                reason=reason,
                detail=detail,
                signal=signal,
            )

            with open(file_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception as exc:
            self.logger.debug("D31: failed to persist signal-drop audit: %s", exc)

    def _record_signal_dispatch_outcome(
        self,
        outcome: str,
        signal: Any | None = None,
        detail: str | None = None,
    ) -> None:
        """Track order-routing outcomes for approved signals."""
        if outcome in self._signal_flow_counts:
            self._signal_flow_counts[outcome] += 1
        if outcome in {"dispatch_submitted", "dispatch_rejected"}:
            self._persist_signal_dispatch_outcome_audit(
                outcome,
                signal=signal,
                detail=detail,
            )
        # v9 §10.4: stamp last successful dispatch for DISPATCH pill FLOWING state.
        if outcome == "dispatch_submitted":
            self._last_dispatch_ok_ts = time.monotonic()
            if signal is not None:
                strategy_type = self._signal_value(signal, "strategy_type")
                if strategy_type:
                    self._last_dispatch_strategy = str(strategy_type)
        self._log_signal_flow_summary_if_due()

    def _persist_signal_dispatch_outcome_audit(
        self,
        outcome: str,
        signal: Any | None,
        detail: str | None = None,
    ) -> None:
        """Append dispatch outcome records to the daily decision JSONL file."""
        if not self._signal_drop_audit_enabled:
            return

        try:
            now_utc = datetime.now(UTC)
            file_path = self._resolve_signal_audit_file_path(now_utc)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            record = self._build_signal_audit_record(
                event=outcome,
                stage="dispatch",
                reason=outcome,
                detail=str(detail or ""),
                signal=signal,
            )

            with open(file_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception as exc:
            self.logger.debug("D31: failed to persist dispatch outcome audit: %s", exc)

    def _record_selector_outcome_audit(
        self,
        strategy_name: str | None,
        selector_reason: str,
    ) -> None:
        """Persist a deduplicated selector outcome marker for launcher-backed runs."""
        pivot_payload = self._get_cached_pivot_signal_for_selector() or {}
        regime_value = getattr(self.market_regime.current_regime, "value", "")
        strategy_label = strategy_name or ""
        feature_flag = self._last_selector_feature_flag or ""

        fingerprint = (
            strategy_label,
            selector_reason,
            feature_flag,
            regime_value,
            pivot_payload.get("fired"),
            pivot_payload.get("direction"),
            pivot_payload.get("nearest_level_name"),
            pivot_payload.get("score"),
        )
        if fingerprint == self._last_selector_outcome_audit_fingerprint:
            return

        self._last_selector_outcome_audit_fingerprint = fingerprint
        self.emit_decision_audit_marker(
            "selector_outcome",
            detail=f"strategy={strategy_label or 'none'}; reason={selector_reason}",
            extra_fields={
                "strategy_name": strategy_name,
                "selector_reason": selector_reason,
                "selector_feature_flag": self._last_selector_feature_flag,
                "regime": regime_value,
                "pivot": {
                    "fired": pivot_payload.get("fired"),
                    "direction": pivot_payload.get("direction"),
                    "score": pivot_payload.get("score"),
                    "nearest_level_name": pivot_payload.get("nearest_level_name"),
                    "atr_distance": pivot_payload.get("atr_distance"),
                },
            },
        )

    def _record_signal_dispatch_outcome_safe(
        self,
        outcome: str,
        signal: Any | None = None,
        detail: str | None = None,
    ) -> None:
        """Record dispatch outcomes without failing when patched call signatures differ.

        Some tests monkeypatch ``_record_signal_dispatch_outcome`` with a
        single-argument callable. Calling it with ``signal=...`` would raise a
        ``TypeError`` and incorrectly surface as a dispatch exception.
        """
        try:
            self._record_signal_dispatch_outcome(
                outcome,
                signal=signal,
                detail=detail,
            )
        except TypeError:
            try:
                self._record_signal_dispatch_outcome(outcome, signal=signal)
            except TypeError:
                self._record_signal_dispatch_outcome(outcome)

    @staticmethod
    def _normalize_regime_policy_key(
        raw_regime: str,
        regimes: dict[str, Any] | None = None,
    ) -> str:
        """Map raw regime names onto the D31 regime-policy key space."""
        normalized = str(raw_regime or "").strip().lower()
        if not normalized:
            return ""
        if normalized in _D31_REGIME_POLICY_KEYS:
            return normalized
        if isinstance(regimes, dict) and normalized in regimes:
            return normalized
        return _D31_REGIME_POLICY_ALIASES.get(normalized, "")

    @staticmethod
    def _execution_stance_for_regime(raw_regime: str) -> str:
        """Collapse D31's 8-state regime into the dashboard's 3 stance labels."""
        normalized = str(raw_regime or "").strip().lower()
        if normalized in {
            MarketRegime.BULL_LOW_VOL.value,
            MarketRegime.BULL_HIGH_VOL.value,
            MarketRegime.RECOVERY.value,
        }:
            return "BULLISH"
        if normalized in {
            MarketRegime.CRISIS.value,
            MarketRegime.EVENT_TRANSITION.value,
        }:
            return "CRISIS"
        return "CHOPPY"

    @staticmethod
    def _execution_gate_label_for_policy_key(policy_key: str) -> str:
        """Convert D31 regime-policy keys into compact dashboard labels."""
        return _D31_EXECUTION_GATE_LABELS.get(str(policy_key or "").strip().lower(), "")

    def get_execution_pill_state(self) -> dict[str, Any]:
        """Return D31-owned posture labels for the G05 STANCE and GATE pills."""
        if getattr(self, "_last_regime_update_ts", None) is None:
            return {"regime": "", "stance": "", "gate": "", "gate_key": ""}
        current_regime = getattr(getattr(self, "market_regime", None), "current_regime", None)
        raw_regime = str(getattr(current_regime, "value", "") or "").strip().lower()
        if not raw_regime:
            return {"regime": "", "stance": "", "gate": "", "gate_key": ""}
        policy = self._get_regime_policy()
        regimes = policy.get("regimes", {}) if isinstance(policy, dict) else {}
        gate_key = self._normalize_regime_policy_key(raw_regime, regimes if isinstance(regimes, dict) else None)
        return {
            "regime": raw_regime,
            "stance": self._execution_stance_for_regime(raw_regime),
            "gate": self._execution_gate_label_for_policy_key(gate_key),
            "gate_key": gate_key,
        }

    def get_dispatch_state(self) -> dict[str, Any]:
        """Return current dispatch state for the G05 DISPATCH pill (v9 §10.4).

        Priority: ERROR > BLOCKED > FLOWING > IDLE. State is bounded by
        ``DISPATCH_STATE_RECENCY_S`` (default 120s); older events collapse to
        IDLE so the pill does not show stale verdicts after the system recovers.

        Returns a dict with keys:
            ``state``  — one of ``"FLOWING"``, ``"IDLE"``, ``"BLOCKED"``, ``"ERROR"``
            ``reason`` — human-readable detail (e.g. ``"risk_gate:risk_state_cold"``,
                         ``"last dispatched: bull_put_spread"``, ``"no signals in last 120s"``)
            ``age_s``  — seconds since the event, or ``None`` for IDLE
        """
        now = time.monotonic()
        recency = DISPATCH_STATE_RECENCY_S

        last_err = self._last_dispatch_error
        if last_err is not None and (now - last_err["monotonic_ts"]) <= recency:
            err_reason = last_err["reason"]
            detail = last_err.get("detail")
            if detail:
                err_reason = f"{err_reason}: {detail}"
            return {
                "state": "ERROR",
                "reason": err_reason,
                "age_s": now - last_err["monotonic_ts"],
            }

        last_ok = self._last_dispatch_ok_ts
        last_drop = self._last_drop_event

        ok_recent = last_ok is not None and (now - last_ok) <= recency
        drop_recent = (
            last_drop is not None
            and (now - last_drop["monotonic_ts"]) <= recency
        )

        # FLOWING wins when a successful dispatch is at least as recent as the
        # most recent guardrail drop within the recency window.
        if ok_recent and (
            not drop_recent or last_ok >= last_drop["monotonic_ts"]
        ):
            strat = self._last_dispatch_strategy or "unknown"
            return {
                "state": "FLOWING",
                "reason": f"last dispatched: {strat}",
                "age_s": now - last_ok,
            }

        if drop_recent:
            return {
                "state": "BLOCKED",
                "reason": f"{last_drop['stage']}:{last_drop['reason']}",
                "age_s": now - last_drop["monotonic_ts"],
            }

        return {
            "state": "IDLE",
            "reason": f"no signals in last {int(recency)}s",
            "age_s": None,
        }

    def _log_signal_flow_summary_if_due(self, force: bool = False) -> None:
        """Emit periodic counters so operators can diagnose no-trade sessions."""
        now = time.monotonic()
        if not force and (now - self._signal_flow_last_log_monotonic) < self._signal_flow_log_interval_s:
            return
        self._signal_flow_last_log_monotonic = now

        top_reason = "none"
        if self._signal_drop_reasons:
            reason, count = max(self._signal_drop_reasons.items(), key=lambda item: item[1])
            top_reason = f"{reason} x{count}"

        self.logger.info(
            "📈 D31 signal flow: seen=%d approved=%d dropped=%d dispatched=%d rejected=%d top_drop=%s",
            self._signal_flow_counts["seen"],
            self._signal_flow_counts["approved"],
            self._signal_flow_counts["dropped"],
            self._signal_flow_counts["dispatch_submitted"],
            self._signal_flow_counts["dispatch_rejected"],
            top_reason,
        )

    # ==========================================================================
    # PUBLIC INTERFACE - ORCHESTRATION CONTROL
    # ==========================================================================

    def start_orchestration(self, defer_initial_strategy_activation: bool = False) -> bool:
        """
        Start strategy orchestration.

        Args:
            defer_initial_strategy_activation: When True, defer the first
                regime-driven strategy activation onto the orchestration loop
                instead of blocking startup synchronously.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.orchestration_active:
                self.logger.warning("Strategy orchestration already active")
                return True

            self.logger.debug("🚀 Starting strategy orchestration...")

            # P1-02: warn early if no execution engine is wired — approved signals
            # would be silently dropped inside _dispatch_approved_signal otherwise.
            if self._live_engine is None and self._order_manager is None:
                self.logger.critical(
                    "D31 start_orchestration: neither _live_engine nor _order_manager "
                    "is wired — all approved signals will be dropped. "
                    "Call set_live_engine() or set_order_manager() before starting."
                )
                if self.event_manager:
                    try:
                        self.event_manager.emit(
                            EventType.RISK_ALERT,
                            {
                                "severity": "critical",
                                "reason": "no_execution_engine_wired",
                                "message": "StrategyOrchestrator started without execution engine",
                            },
                            source="StrategyOrchestrator",
                        )
                    except Exception:
                        pass
                return False

            # Validate connectivity if available
            if self.connectivity_manager:
                connectivity_report = self.connectivity_manager.get_connectivity_report()
                overall_state = getattr(connectivity_report, "overall_state", None)
                overall_state_value = str(
                    getattr(overall_state, "value", overall_state)
                ).strip().lower()
                if overall_state_value == "failed":
                    self.logger.error("❌ Cannot start orchestration - connectivity failed")
                    return False

            # Initialize market regime detection
            self._update_market_regime()

            # Start monitoring threads — must be set True BEFORE
            # _configure_strategies_for_regime so that add_strategy() calls
            # strategy.start() and transitions each strategy to STRATEGY_ACTIVE.
            # (Without this, all strategies stay STRATEGY_INACTIVE and silently
            # discard every MARKET_DATA event — no signals, no trades.)
            self.orchestration_active = True
            with self._initial_strategy_activation_lock:
                self._initial_strategy_activation_pending = defer_initial_strategy_activation
                self._initial_strategy_activation_running = False
                self._initial_strategy_activation_ready_at = (
                    time.monotonic() + INITIAL_STRATEGY_ACTIVATION_DEFER_SECONDS
                    if defer_initial_strategy_activation else 0.0
                )

            # Load optimal strategy configuration for current regime
            self.shutdown_event.clear()
            self._scheduled_strategy_wakeup.clear()
            with self._scheduled_strategy_lock:
                self._scheduled_strategy_due_at.clear()

            if defer_initial_strategy_activation:
                self.logger.debug(
                    "⏳ Deferring initial strategy activation to orchestration loop"
                )
            else:
                self._configure_strategies_for_regime()

            self.orchestration_thread = threading.Thread(target=self._orchestration_loop, daemon=True)  # noqa: E501
            self.orchestration_thread.start()

            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()

            self.scheduled_strategy_thread = threading.Thread(
                target=self._scheduled_strategy_loop,
                daemon=True,
                name="SpyderD31ScheduledStrategyLoop",
            )
            self.scheduled_strategy_thread.start()

            # Initial portfolio allocation
            if not defer_initial_strategy_activation:
                self._perform_initial_allocation()

            self.logger.debug("✅ Strategy orchestration started successfully")
            return True

        except Exception as e:
            self.logger.error("❌ Failed to start strategy orchestration: %s", e, exc_info=True)
            if self.error_handler:
                self.error_handler.handle_error(e, "StrategyOrchestrator.start_orchestration")
            return False

    def stop_orchestration(self, graceful: bool = True) -> bool:
        """
        Stop strategy orchestration.

        Args:
            graceful: Whether to stop gracefully

        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.orchestration_active:
                self.logger.info("Strategy orchestration already stopped")
                return True

            self.logger.info("🛑 Stopping strategy orchestration...")

            # Signal shutdown
            self.orchestration_active = False
            self.shutdown_event.set()
            self._scheduled_strategy_wakeup.set()

            # Stop all strategies
            if graceful:
                with self._strategies_lock:
                    strategies_to_stop = list(self.active_strategies.items())
                for strategy_id, strategy in strategies_to_stop:
                    self.logger.info("Stopping strategy: %s", strategy_id)
                    try:
                        strategy.stop()
                    except Exception as e:
                        self.logger.error("Error stopping strategy %s: %s", strategy_id, e, exc_info=True)  # noqa: E501

            # Wait for threads to complete
            if self.orchestration_thread:
                self.orchestration_thread.join(timeout=30)
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=30)
            if self.scheduled_strategy_thread:
                self.scheduled_strategy_thread.join(timeout=30)

            # Final portfolio report
            self._generate_final_report()

            self.logger.info("✅ Strategy orchestration stopped")
            return True

        except Exception as e:
            self.logger.error("❌ Error stopping orchestration: %s", e, exc_info=True)
            return False

    def stop(self) -> None:
        """Lifecycle adapter used by SessionSupervisor.

        SessionSupervisor expects components to expose a no-arg ``stop()``.
        Delegate to ``stop_orchestration(graceful=True)`` for compatibility.
        """
        self.stop_orchestration(graceful=True)

    def add_strategy(self, strategy_class: type, config: dict[str, Any],
                     initial_allocation: float | None = None) -> str:
        """
        Add a new strategy to the orchestrator.

        Args:
            strategy_class: Strategy class to instantiate
            config: Strategy configuration
            initial_allocation: Initial capital allocation (0.0-1.0)

        Returns:
            str: Strategy ID
        """
        try:
            # Validate strategy class
            if not inspect.isclass(strategy_class):
                raise ValueError(f"Strategy reference is not a class: {strategy_class!r}")

            if not _is_strategy_class(strategy_class):
                raise ValueError("Strategy class must inherit from BaseStrategy")

            if inspect.isabstract(strategy_class):
                raise ValueError(
                    f"Strategy class is abstract and cannot be instantiated: {strategy_class.__name__}"  # noqa: E501
                )

            strategy_name = strategy_class.__name__
            strategy_type = self._get_strategy_type(strategy_class)
            config = self._apply_strategy_runtime_config_defaults(strategy_type, config)
            if self.lean_mode and strategy_name not in self.lean_strategy_allowlist:
                raise ValueError(
                    f"Lean mode blocks strategy registration: {strategy_name}"
                )
            horizon_bucket = self._resolve_horizon_bucket(strategy_name, config)

            with self._strategies_lock:
                current_active = len(self.active_strategies)
                overlay_registration_allowed = self._allows_overlay_strategy_registration_locked(
                    strategy_type=strategy_type,
                    horizon_bucket=horizon_bucket,
                )
                if (
                    current_active >= self.max_concurrent_strategies
                    and not overlay_registration_allowed
                ):
                    raise ValueError(
                        f"Concurrent strategy limit reached: {current_active}/{self.max_concurrent_strategies}"  # noqa: E501
                    )

                active_bucket_counts = self._get_active_horizon_bucket_counts_locked()
                if (
                    active_bucket_counts.get(horizon_bucket, 0) >= 1
                    and not overlay_registration_allowed
                ):
                    raise ValueError(
                        "Horizon-bucket already occupied: "
                        f"{horizon_bucket}"
                    )

                active_buckets = set(active_bucket_counts)
                would_add_new_bucket = horizon_bucket not in active_buckets
                if (
                    would_add_new_bucket
                    and len(active_buckets) >= self.max_active_horizon_buckets
                    and not overlay_registration_allowed
                ):
                    raise ValueError(
                        "Horizon-bucket limit reached: "
                        f"{sorted(active_buckets)} (max={self.max_active_horizon_buckets})"
                    )

            # Generate strategy ID
            strategy_id = f"{strategy_class.__name__}_{uuid.uuid4().hex[:8]}"

            # Create strategy instance (constructor signatures vary across D-series).
            risk_profile = self._get_risk_profile_for_strategy(strategy_class)
            ctor_attempts = [
                {
                    "name": strategy_id,
                    "event_manager": self.event_manager,
                    "risk_profile": risk_profile,
                    "config": config,
                },
                {
                    "event_manager": self.event_manager,
                    "risk_profile": risk_profile,
                    "config": config,
                },
            ]

            strategy = None
            last_error: Exception | None = None
            for kwargs in ctor_attempts:
                try:
                    strategy = strategy_class(**kwargs)
                    break
                except TypeError as exc:
                    last_error = exc

            if strategy is None:
                raise TypeError(
                    f"Could not instantiate {strategy_class.__name__}; unsupported constructor signature"  # noqa: E501
                ) from last_error

            # Calculate initial allocation
            if initial_allocation is None:
                initial_allocation = self._calculate_optimal_allocation(strategy_class.__name__)

            allocated_capital = self.base_capital * initial_allocation

            # B14 (v15): start the strategy BEFORE registering it in
            # active_strategies.  If start() raises, the strategy never appears
            # in the dict, so the orchestration loop cannot poll a broken object.
            if self.orchestration_active:
                strategy.start()

            # C1 (v18): Pre-construct allocation record before acquiring lock to
            # keep lock duration minimal while still ensuring active_strategies and
            # strategy_allocations are always mutated atomically under the same lock.
            _new_alloc = StrategyAllocation(
                strategy_id=strategy_id,
                strategy_name=strategy_class.__name__,
                strategy_type=strategy_type,
                horizon_bucket=horizon_bucket,
                allocated_capital=allocated_capital,
                target_allocation=initial_allocation,
                current_allocation=initial_allocation,
                performance_score=0.5,  # Neutral starting score
                risk_score=0.5,
                health_score=1.0,
                last_rebalance=datetime.now(UTC)
            )

            # Add to active strategies AND allocation map under the same lock (B3/v15 + C1/v18).
            late_registration_error: ValueError | None = None
            with self._strategies_lock:
                current_active = len(self.active_strategies)
                overlay_registration_allowed = self._allows_overlay_strategy_registration_locked(
                    strategy_type=strategy_type,
                    horizon_bucket=horizon_bucket,
                )
                if (
                    current_active >= self.max_concurrent_strategies
                    and not overlay_registration_allowed
                ):
                    late_registration_error = ValueError(
                        f"Concurrent strategy limit reached: {current_active}/{self.max_concurrent_strategies}"
                    )
                else:
                    active_bucket_counts = self._get_active_horizon_bucket_counts_locked()
                    if (
                        active_bucket_counts.get(horizon_bucket, 0) >= 1
                        and not overlay_registration_allowed
                    ):
                        late_registration_error = ValueError(
                            "Horizon-bucket already occupied: "
                            f"{horizon_bucket}"
                        )
                    else:
                        active_buckets = set(active_bucket_counts)
                        would_add_new_bucket = horizon_bucket not in active_buckets
                        if (
                            would_add_new_bucket
                            and len(active_buckets) >= self.max_active_horizon_buckets
                            and not overlay_registration_allowed
                        ):
                            late_registration_error = ValueError(
                                "Horizon-bucket limit reached: "
                                f"{sorted(active_buckets)} (max={self.max_active_horizon_buckets})"
                            )
                        else:
                            self.active_strategies[strategy_id] = strategy
                            self.strategy_allocations[strategy_id] = _new_alloc

            if late_registration_error is not None:
                if self.orchestration_active:
                    try:
                        strategy.stop()
                    except Exception:
                        pass
                raise late_registration_error

            self._seed_runtime_cadence_for_strategy(strategy_id, strategy)

            # Notify ExitMonitor so it can attribute positions to this strategy.
            # The ExitMonitor is owned by SessionSupervisor and may not exist in
            # all execution contexts (e.g. tests), so we look it up lazily.
            try:
                from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import get_session_supervisor  # noqa: E501
                sup = get_session_supervisor()
                if sup is not None and getattr(sup, "exit_monitor", None) is not None:
                    sup.exit_monitor.register_strategy(strategy_id, strategy)
            except Exception:
                pass  # ExitMonitor unavailable — not fatal

            # Update portfolio metrics
            self._update_portfolio_metrics()

            self.logger.debug(
                "✅ Added strategy: %s with %.1f%% allocation (bucket=%s)",
                strategy_id,
                initial_allocation * 100,
                horizon_bucket,
            )
            return strategy_id

        except Exception as e:
            self.logger.error("❌ Failed to add strategy: %s", e, exc_info=True)
            if self.error_handler:
                self.error_handler.handle_error(e, "StrategyOrchestrator.add_strategy")
            raise

    def remove_strategy(self, strategy_id: str, close_positions: bool = True) -> bool:
        """
        Remove a strategy from orchestration.

        Args:
            strategy_id: Strategy to remove
            close_positions: Whether to close existing positions

        Returns:
            bool: True if removed successfully
        """
        try:
            # B3 (v15) + C1 (v18): snapshot the strategy reference AND remove
            # its allocation record under the same lock acquisition so that
            # background iteration threads never observe a size-changed dict.
            with self._strategies_lock:
                if strategy_id not in self.active_strategies:
                    self.logger.warning("Strategy %s not found", strategy_id)
                    return False
                strategy = self.active_strategies.pop(strategy_id)
                _freed_alloc = self.strategy_allocations.pop(strategy_id, None)
            with self._scheduled_strategy_lock:
                self._scheduled_strategy_due_at.pop(strategy_id, None)
            self._scheduled_strategy_wakeup.set()

            # Stop strategy (outside lock — can block)
            if close_positions:
                strategy.close_all_positions()
            strategy.stop()

            # Redistribute freed capital (outside lock — involves no dict mutation)
            freed_capital = _freed_alloc.allocated_capital if _freed_alloc else 0.0
            if freed_capital:
                self._redistribute_capital(freed_capital)

            # Update portfolio metrics
            self._update_portfolio_metrics()

            self.logger.info("✅ Removed strategy: %s", strategy_id)
            return True

        except Exception as e:
            self.logger.error("❌ Error removing strategy %s: %s", strategy_id, e, exc_info=True)
            return False

    def pause_strategy(self, strategy_id: str) -> bool:
        """Pause a specific strategy"""
        try:
            # B3 (v15): guard both check and mutation under the same lock.
            with self._strategies_lock:
                if strategy_id not in self.active_strategies:
                    return False
                self.active_strategies[strategy_id].pause()
                self.paused_strategies.add(strategy_id)

            self.logger.info("⏸️ Paused strategy: %s", strategy_id)
            return True

        except Exception as e:
            self.logger.error("Error pausing strategy %s: %s", strategy_id, e, exc_info=True)
            return False

    def resume_strategy(self, strategy_id: str) -> bool:
        """Resume a paused strategy"""
        try:
            # B3 (v15): guard both check and mutation under the same lock.
            with self._strategies_lock:
                if strategy_id not in self.active_strategies:
                    return False
                self.active_strategies[strategy_id].resume()
                self.paused_strategies.discard(strategy_id)

            self.logger.info("▶️ Resumed strategy: %s", strategy_id)
            return True

        except Exception as e:
            self.logger.error("Error resuming strategy %s: %s", strategy_id, e, exc_info=True)
            return False

    def rebalance_portfolio(self, reason: RebalanceReason = RebalanceReason.SCHEDULED) -> bool:
        """
        Manually trigger portfolio rebalancing.

        Args:
            reason: Reason for rebalancing

        Returns:
            bool: True if rebalancing was successful
        """
        try:
            self.logger.info("🔄 Manual portfolio rebalancing triggered - Reason: %s", reason.value)
            return self._execute_rebalancing(reason)

        except Exception as e:
            self.logger.error("❌ Manual rebalancing failed: %s", e, exc_info=True)
            return False

    # ==========================================================================
    # PORTFOLIO ANALYTICS AND REPORTING
    # ==========================================================================

    def get_portfolio_status(self) -> dict[str, Any]:
        """Get comprehensive portfolio status"""
        try:
            # B3 (v15) + C1 (v18): snapshot both dicts atomically under one lock.
            with self._strategies_lock:
                n_active = len(self.active_strategies)
                n_paused = len(self.paused_strategies)
                _alloc_snap = dict(self.strategy_allocations)
            return {
                'orchestration_active': self.orchestration_active,
                'total_capital': self.portfolio_metrics.total_capital,
                'allocated_capital': self.portfolio_metrics.allocated_capital,
                'available_capital': self.portfolio_metrics.available_capital,
                'total_pnl': self.portfolio_metrics.total_pnl,
                'daily_pnl': self.portfolio_metrics.daily_pnl,
                'portfolio_sharpe': self.portfolio_metrics.portfolio_sharpe,
                'max_drawdown': self.portfolio_metrics.max_drawdown,
                'active_strategies': n_active,
                'paused_strategies': n_paused,
                'market_regime': self.market_regime.current_regime.value,
                'regime_confidence': self.market_regime.regime_confidence,
                'last_rebalance': self.last_rebalance.isoformat(),
                'strategy_allocations': {
                    sid: {
                        'name': alloc.strategy_name,
                        'allocation': alloc.current_allocation,
                        'capital': alloc.allocated_capital,
                        'performance_score': alloc.performance_score,
                        'health_score': alloc.health_score
                    }
                    for sid, alloc in _alloc_snap.items()
                }
            }

        except Exception as e:
            self.logger.error("Error getting portfolio status: %s", e, exc_info=True)
            return {}

    def get_strategy_performance_attribution(self) -> pd.DataFrame:
        """Get detailed strategy performance attribution"""
        try:
            data = []

            # B3 (v15) + C1 (v18): snapshot both dicts under the same lock so
            # the view of active_strategies and strategy_allocations is consistent.
            with self._strategies_lock:
                active_snap: dict = dict(self.active_strategies)
                alloc_snap: dict = dict(self.strategy_allocations)

            for strategy_id, allocation in alloc_snap.items():
                if strategy_id in active_snap:
                    strategy = active_snap[strategy_id]

                    # Calculate strategy contribution to portfolio
                    strategy_pnl = getattr(strategy, 'total_pnl', 0.0)
                    portfolio_contribution = strategy_pnl * allocation.current_allocation

                    data.append({
                        'strategy_id': strategy_id,
                        'strategy_name': allocation.strategy_name,
                        'strategy_type': allocation.strategy_type,
                        'allocation': allocation.current_allocation,
                        'allocated_capital': allocation.allocated_capital,
                        'strategy_pnl': strategy_pnl,
                        'portfolio_contribution': portfolio_contribution,
                        'performance_score': allocation.performance_score,
                        'risk_score': allocation.risk_score,
                        'health_score': allocation.health_score,
                        'sharpe_ratio': getattr(strategy, 'sharpe_ratio', 0.0),
                        'max_drawdown': getattr(strategy, 'max_drawdown', 0.0),
                        'win_rate': getattr(strategy, 'win_rate', 0.0),
                        'total_trades': getattr(strategy, 'total_trades', 0),
                        'active_positions': len(getattr(strategy, 'positions', {}))
                    })

            return pd.DataFrame(data)

        except Exception as e:
            self.logger.error("Error generating performance attribution: %s", e, exc_info=True)
            return pd.DataFrame()

    def detect_strategy_conflicts(self) -> list[StrategyConflict]:
        """Detect potential conflicts between strategies"""
        try:
            conflicts = []
            # B3 (v15): snapshot under lock before iterating.
            with self._strategies_lock:
                strategies = list(self.active_strategies.items())

            # Check for overlapping positions
            for i, (id1, strategy1) in enumerate(strategies):
                for id2, strategy2 in strategies[i+1:]:
                    conflict = self._analyze_strategy_pair_for_conflicts(id1, strategy1, id2, strategy2)  # noqa: E501
                    if conflict:
                        conflicts.append(conflict)

            # Check for concentration risks
            concentration_conflicts = self._check_concentration_conflicts()
            conflicts.extend(concentration_conflicts)

            # Update stored conflicts
            self.strategy_conflicts = conflicts

            return conflicts

        except Exception as e:
            self.logger.error("Error detecting strategy conflicts: %s", e, exc_info=True)
            return []

    def get_correlation_matrix(self) -> pd.DataFrame | None:
        """Get strategy correlation matrix"""
        try:
            # B3 (v15): snapshot under lock.
            with self._strategies_lock:
                active_snap = list(self.active_strategies.items())
            if len(active_snap) < 2:
                return None

            # Collect strategy returns
            strategy_returns = {}

            for strategy_id, strategy in active_snap:
                if hasattr(strategy, 'daily_returns') and len(strategy.daily_returns) > 10:
                    strategy_returns[strategy_id] = strategy.daily_returns[-30:]  # Last 30 days

            if len(strategy_returns) < 2:
                return None

            # Create DataFrame and calculate correlations
            returns_df = pd.DataFrame(strategy_returns)
            correlation_matrix = returns_df.corr()

            return correlation_matrix

        except Exception as e:
            self.logger.error("Error calculating correlation matrix: %s", e, exc_info=True)
            return None

    # ==========================================================================
    # PRIVATE METHODS - ORCHESTRATION LOOPS
    # ==========================================================================

    def _orchestration_loop(self):
        """Main orchestration loop"""
        while self.orchestration_active and not self.shutdown_event.is_set():
            try:
                if self._initial_strategy_activation_pending:
                    wait_seconds = self._initial_strategy_activation_ready_at - time.monotonic()
                    if wait_seconds > 0:
                        self.shutdown_event.wait(min(wait_seconds, 0.05))
                        continue

                # Update market regime
                self._update_market_regime()

                # Hunting heartbeat — once per rebalance cycle
                with self._strategies_lock:
                    _n_active = len(self.active_strategies)
                _regime_label = (
                    getattr(self.market_regime.current_regime, "value", "unknown")
                    if self.market_regime.current_regime
                    else "unknown"
                )
                self.logger.info(
                    "🔍 Hunting: %d active, regime=%s", _n_active, _regime_label
                )

                self._run_initial_strategy_activation_if_pending()

                # Check if rebalancing is needed
                if self._should_rebalance():
                    reason = self._determine_rebalance_reason()
                    self._execute_rebalancing(reason)

                # Check for strategy conflicts
                conflicts = self.detect_strategy_conflicts()
                if conflicts:
                    self._resolve_strategy_conflicts(conflicts)

                # Adaptive strategy management
                if self.orchestration_mode == OrchestrationMode.ADAPTIVE:
                    self._adaptive_strategy_management()

                # Sleep until next iteration
                self.shutdown_event.wait(REBALANCE_FREQUENCY_MINUTES * 60)

            except Exception as e:
                self.logger.error("Error in orchestration loop: %s", e, exc_info=True)
                self.shutdown_event.wait(60)  # Wait 1 minute on error

    def _run_initial_strategy_activation_if_pending(self) -> None:
        """Perform deferred first strategy activation once after startup."""
        with self._initial_strategy_activation_lock:
            if (
                not self._initial_strategy_activation_pending
                or self._initial_strategy_activation_running
            ):
                return
            if self._is_waiting_for_deferred_paper_regime_engine():
                return
            self._initial_strategy_activation_running = True

        try:
            self._configure_strategies_for_regime()
            self._perform_initial_allocation()
            with self._initial_strategy_activation_lock:
                self._initial_strategy_activation_pending = False
                self._initial_strategy_activation_ready_at = 0.0
        finally:
            with self._initial_strategy_activation_lock:
                self._initial_strategy_activation_running = False

    def _monitoring_loop(self):
        """Strategy health monitoring loop"""
        while self.orchestration_active and not self.shutdown_event.is_set():
            try:
                # Supervision heartbeat — throttled to once every 5 min when positions open
                with self._strategies_lock:
                    _n = len(self.active_strategies)
                if _n > 0:
                    _now_m = time.monotonic()
                    if _now_m - getattr(self, "_last_supervision_log_ts", 0.0) >= 300.0:
                        self.logger.info(
                            "👁 Supervising %d active strateg%s", _n, "ies" if _n != 1 else "y"
                        )
                        self._last_supervision_log_ts = _now_m

                # Monitor strategy health
                self._monitor_strategy_health()

                # Update portfolio metrics
                self._update_portfolio_metrics()

                # Check risk limits
                self._check_risk_limits()

                # Update performance attribution
                self._update_performance_attribution()

                # Sleep until next check
                self.shutdown_event.wait(STRATEGY_HEALTH_CHECK_INTERVAL)

            except Exception as e:
                self.logger.error("Error in monitoring loop: %s", e, exc_info=True)
                self.shutdown_event.wait(30)  # Short wait on error

    def _strategy_uses_runtime_cadence(self, strategy: Any) -> bool:
        """Return True when a strategy should be evaluated by the cadence loop."""
        uses_runtime_cadence = getattr(strategy, "uses_runtime_cadence", None)
        if callable(uses_runtime_cadence):
            try:
                return bool(uses_runtime_cadence())
            except Exception:
                return False

        runtime_config = getattr(strategy, "runtime_config", None)
        if isinstance(runtime_config, dict):
            return bool(runtime_config.get("runtime_cadence_enabled", False))
        return bool(getattr(strategy, "runtime_cadence_enabled", False))

    def _seed_runtime_cadence_for_strategy(
        self,
        strategy_id: str,
        strategy: Any,
        *,
        now: datetime | None = None,
        force: bool = False,
    ) -> None:
        """Seed or refresh the next due time for a cadence-driven strategy."""
        if not self._strategy_uses_runtime_cadence(strategy):
            with self._scheduled_strategy_lock:
                self._scheduled_strategy_due_at.pop(strategy_id, None)
            self._scheduled_strategy_wakeup.set()
            return

        now_et = now or _d31_now_et()
        due_at = None
        next_runtime_evaluation_at = getattr(strategy, "next_runtime_evaluation_at", None)
        if callable(next_runtime_evaluation_at):
            try:
                due_at = next_runtime_evaluation_at(now_et)
            except Exception as exc:
                self.logger.debug(
                    "D31: runtime cadence seed failed for %s: %s",
                    strategy_id,
                    exc,
                )
                due_at = None

        with self._scheduled_strategy_lock:
            if due_at is None:
                self._scheduled_strategy_due_at.pop(strategy_id, None)
            else:
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=now_et.tzinfo)
                if not force and strategy_id in self._scheduled_strategy_due_at:
                    return
                seconds_until_due = max((due_at - now_et).total_seconds(), 0.0)
                self._scheduled_strategy_due_at[strategy_id] = (
                    time.monotonic() + seconds_until_due
                )
        self._scheduled_strategy_wakeup.set()

    def _evaluate_strategy_from_cache(self, strategy_id: str, *, reason: str) -> bool:
        """Evaluate one active strategy using the latest cached symbol history."""
        with self._strategies_lock:
            strategy = self.active_strategies.get(strategy_id)

        if strategy is None:
            return False

        symbol = str(getattr(strategy, "symbol", "") or "").strip().upper()
        if not symbol:
            return False

        market_df = self._build_market_df_for_symbol(symbol)
        if market_df is None or (hasattr(market_df, "empty") and market_df.empty):
            return False

        try:
            strategy.process_market_data(market_df)
            return True
        except Exception as exc:
            self.logger.error(
                "Error feeding cached market data to strategy %s (%s): %s",
                strategy_id,
                reason,
                exc,
                exc_info=True,
            )
            return False

    @staticmethod
    def _coerce_option_quote_row(row: Any) -> dict[str, Any]:
        """Normalize quote-chain rows from dict or object payloads."""
        if isinstance(row, dict):
            normalized = dict(row)
        else:
            normalized = {
                "symbol": getattr(row, "symbol", ""),
                "option_type": getattr(row, "option_type", ""),
                "strike": getattr(row, "strike", None),
                "bid": getattr(row, "bid", None),
                "ask": getattr(row, "ask", None),
                "last": getattr(row, "last", None),
                "mid": getattr(row, "mid", None),
                "expiration_date": getattr(row, "expiration_date", ""),
                "underlying": getattr(row, "underlying", ""),
            }
            delta = getattr(row, "delta", None)
            greeks = getattr(row, "greeks", None)
            if isinstance(greeks, dict):
                normalized["greeks"] = dict(greeks)
            elif delta is not None:
                normalized["greeks"] = {"delta": delta}
            else:
                normalized["greeks"] = {}

        symbol = str(
            normalized.get("symbol")
            or normalized.get("option_symbol")
            or ""
        ).strip().upper()
        normalized["symbol"] = symbol
        normalized.setdefault("option_symbol", symbol)
        option_type = str(normalized.get("option_type") or "").strip().lower()
        if option_type:
            normalized["option_type"] = option_type
        try:
            if normalized.get("strike") is not None:
                normalized["strike"] = float(normalized["strike"])
        except (TypeError, ValueError):
            normalized["strike"] = None
        greeks = normalized.get("greeks")
        if not isinstance(greeks, dict):
            greeks = {}
        normalized["greeks"] = greeks
        return normalized

    def _build_option_quote_map_for_short_legs(self, short_legs: list[Any]) -> dict[str, dict[str, Any]]:
        """Build an option quote map for active short legs using the paper quote client."""
        if not short_legs or self._live_engine is None:
            return {}

        quote_client_factory = getattr(self._live_engine, "_get_paper_option_quote_client", None)
        if not callable(quote_client_factory):
            return {}

        try:
            quote_client = quote_client_factory()
        except Exception as exc:
            self.logger.warning("D31: short-leg quote client bootstrap failed: %s", exc)
            return {}

        get_option_chain_with_greeks = getattr(quote_client, "get_option_chain_with_greeks", None)
        if not callable(get_option_chain_with_greeks):
            return {}

        grouped_legs: dict[tuple[str, str], list[Any]] = {}
        for leg in short_legs:
            details = self._parse_occ_option_symbol(getattr(leg, "symbol", ""))
            underlying = str(details.get("underlying") or "").strip().upper()
            expiration = str(details.get("expiration") or "").strip()
            if not underlying or not expiration:
                continue
            grouped_legs.setdefault((underlying, expiration), []).append(leg)

        quote_map: dict[str, dict[str, Any]] = {}
        for (underlying, expiration), grouped in grouped_legs.items():
            try:
                chain_rows = get_option_chain_with_greeks(underlying, expiration)
            except Exception as exc:
                self.logger.warning(
                    "D31: short-leg quote fetch failed for %s %s: %s",
                    underlying,
                    expiration,
                    exc,
                )
                continue

            normalized_rows = [self._coerce_option_quote_row(row) for row in list(chain_rows or [])]
            rows_by_symbol = {
                str(row.get("symbol") or "").strip().upper(): row
                for row in normalized_rows
                if str(row.get("symbol") or "").strip()
            }

            for leg in grouped:
                leg_symbol = str(getattr(leg, "symbol", "") or "").strip().upper()
                if not leg_symbol:
                    continue

                row = rows_by_symbol.get(leg_symbol)
                if row is None:
                    leg_details = self._parse_occ_option_symbol(leg_symbol)
                    leg_option_type = str(leg_details.get("option_type") or "").strip().lower()
                    leg_strike = self._coerce_float(leg_details.get("strike"))
                    for candidate in normalized_rows:
                        if str(candidate.get("option_type") or "").strip().lower() != leg_option_type:
                            continue
                        candidate_strike = self._coerce_float(candidate.get("strike"))
                        if candidate_strike is None or leg_strike is None:
                            continue
                        if abs(candidate_strike - leg_strike) > 1e-6:
                            continue
                        row = dict(candidate)
                        break

                if row is not None:
                    quote_map[leg_symbol] = dict(row)

        return quote_map

    def _build_short_leg_close_broker(self, strategy_id: str) -> Any:
        """Adapt live-engine execute_order to E25's single-leg close interface."""
        orchestrator = self

        class _EngineLegCloseBroker:
            def place_multileg_order(
                self,
                *,
                underlying: str,
                legs: list[dict[str, Any]],
                order_type: str = "market",
                duration: str = "day",
                tag: str = "",
            ) -> dict[str, Any]:
                _ = underlying, duration
                if not legs:
                    raise ValueError("No legs supplied for short-leg close")
                leg = dict(legs[0])
                option_symbol = str(leg.get("option_symbol") or leg.get("symbol") or "").strip()
                side = str(leg.get("side") or "buy_to_close").strip().lower()
                quantity = max(int(leg.get("quantity") or 1), 1)
                order = {
                    "symbol": option_symbol,
                    "side": side,
                    "quantity": quantity,
                    "order_type": str(order_type or "market").lower(),
                    "strategy_id": strategy_id,
                    "tag": str(tag or ""),
                }
                result = orchestrator._live_engine.execute_order(order)
                status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
                if status in {"rejected", "error", "timeout"}:
                    reason = result.get("reason", status) if isinstance(result, dict) else status
                    raise RuntimeError(str(reason or status))
                return result if isinstance(result, dict) else {"status": status}

        return _EngineLegCloseBroker()

    def _get_open_option_symbols_for_short_leg_reconcile(self) -> set[str] | None:
        """Return authoritative open option symbols when available for short-leg cleanup."""
        try:
            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import get_session_supervisor
        except Exception:
            return None

        supervisor = get_session_supervisor()
        if supervisor is None:
            return None

        position_rows: list[Any] | None = None
        get_positions_for_flatten = getattr(supervisor, "_get_positions_for_flatten", None)
        if callable(get_positions_for_flatten):
            try:
                position_rows = list(get_positions_for_flatten())
            except Exception as exc:
                self.logger.debug("D31: short-leg reconcile flatten inventory lookup failed: %s", exc)
                position_rows = None

        if position_rows is None:
            get_positions = getattr(supervisor, "get_positions", None)
            normalize_rows = getattr(supervisor, "_normalize_position_rows", None)
            if callable(get_positions):
                try:
                    raw_positions = get_positions()
                    if callable(normalize_rows):
                        position_rows = normalize_rows(raw_positions)
                    elif isinstance(raw_positions, list):
                        position_rows = list(raw_positions)
                    elif isinstance(raw_positions, dict):
                        position_rows = list(raw_positions.values())
                    else:
                        position_rows = []
                except Exception as exc:
                    self.logger.debug("D31: short-leg reconcile get_positions lookup failed: %s", exc)
                    position_rows = None

        if position_rows is None:
            return None

        option_symbols: set[str] = set()
        for position in position_rows:
            if isinstance(position, dict):
                quantity = self._coerce_float(position.get("quantity"))
                option_symbol = str(position.get("option_symbol") or position.get("symbol") or "")
            else:
                quantity = self._coerce_float(getattr(position, "quantity", None))
                option_symbol = str(
                    getattr(position, "option_symbol", "")
                    or getattr(position, "symbol", "")
                )

            normalized_symbol = option_symbol.strip().upper()
            if not normalized_symbol or not self._parse_occ_option_symbol(normalized_symbol):
                continue
            if quantity is not None and abs(quantity) <= 1e-9:
                continue
            option_symbols.add(normalized_symbol)

        return option_symbols

    def _reconcile_strategy_active_short_legs(self, strategy: Any) -> list[str]:
        """Drop tracked short legs that no longer exist in authoritative open positions."""
        get_active_short_legs = getattr(strategy, "get_active_short_legs", None)
        remove_active_short_legs = getattr(strategy, "remove_active_short_legs", None)
        if not callable(get_active_short_legs) or not callable(remove_active_short_legs):
            return []

        short_legs = list(get_active_short_legs() or [])
        if not short_legs:
            return []

        open_option_symbols = self._get_open_option_symbols_for_short_leg_reconcile()
        if open_option_symbols is None:
            return []

        missing_symbols = sorted(
            {
                str(getattr(leg, "symbol", "") or "").strip().upper()
                for leg in short_legs
                if str(getattr(leg, "symbol", "") or "").strip().upper()
                and str(getattr(leg, "symbol", "") or "").strip().upper() not in open_option_symbols
            }
        )
        if not missing_symbols:
            return []

        suffix = "s" if len(missing_symbols) != 1 else ""
        remove_active_short_legs(
            missing_symbols,
            note=f"Reconciled {len(missing_symbols)} stale short leg{suffix}",
        )
        self.logger.info(
            "D31: reconciled %d stale short-leg symbols for %s",
            len(missing_symbols),
            getattr(strategy, "name", strategy.__class__.__name__),
        )
        return missing_symbols

    def _evaluate_strategy_short_leg_risk(self, strategy_id: str, strategy: Any) -> list[Any]:
        """Run one E25-style short-leg risk pass for the strategy's active short legs."""
        get_active_short_legs = getattr(strategy, "get_active_short_legs", None)
        if not callable(get_active_short_legs):
            return []

        self._reconcile_strategy_active_short_legs(strategy)

        if self._live_engine is None:
            return []

        short_legs = list(get_active_short_legs() or [])
        if not short_legs:
            return []

        quote_map = self._build_option_quote_map_for_short_legs(short_legs)
        if not quote_map:
            return []

        try:
            from Spyder.SpyderE_Risk.SpyderE25_DeltaBreachLegManager import DeltaBreachLegManager
        except Exception as exc:
            self.logger.warning("D31: DeltaBreachLegManager unavailable: %s", exc)
            return []

        max_short_delta = self._coerce_float(
            getattr(strategy, "max_short_delta", None)
        )
        if max_short_delta is None and isinstance(getattr(strategy, "runtime_config", None), dict):
            max_short_delta = self._coerce_float(strategy.runtime_config.get("max_short_delta"))
        if max_short_delta is None or max_short_delta <= 0:
            max_short_delta = 0.35

        risk_manager = DeltaBreachLegManager(
            broker_client=self._build_short_leg_close_broker(strategy_id),
            max_short_delta=max_short_delta,
        )
        risk_manager.register_legs(short_legs)
        closed_legs = risk_manager.evaluate_once(quote_map)
        if closed_legs:
            remove_active_short_legs = getattr(strategy, "remove_active_short_legs", None)
            if callable(remove_active_short_legs):
                suffix = "s" if len(closed_legs) != 1 else ""
                remove_active_short_legs(
                    [str(leg.symbol) for leg in closed_legs],
                    note=f"Closed {len(closed_legs)} short leg{suffix} via risk pass",
                )
        return closed_legs

    def _scheduled_strategy_loop(self) -> None:
        """Run cadence-driven strategies from cached market data instead of tick fanout."""
        while self.orchestration_active and not self.shutdown_event.is_set():
            try:
                now_et = _d31_now_et()
                now_monotonic = time.monotonic()
                with self._strategies_lock:
                    strategy_snapshot = list(self.active_strategies.items())

                active_ids = {strategy_id for strategy_id, _ in strategy_snapshot}
                with self._scheduled_strategy_lock:
                    stale_ids = [
                        strategy_id
                        for strategy_id in self._scheduled_strategy_due_at
                        if strategy_id not in active_ids
                    ]
                    for strategy_id in stale_ids:
                        self._scheduled_strategy_due_at.pop(strategy_id, None)

                due_strategies: list[tuple[str, Any]] = []
                for strategy_id, strategy in strategy_snapshot:
                    if not self._strategy_uses_runtime_cadence(strategy):
                        with self._scheduled_strategy_lock:
                            self._scheduled_strategy_due_at.pop(strategy_id, None)
                        continue
                    self._seed_runtime_cadence_for_strategy(strategy_id, strategy, now=now_et)
                    with self._scheduled_strategy_lock:
                        due_at = self._scheduled_strategy_due_at.get(strategy_id)
                    if due_at is not None and due_at <= now_monotonic:
                        due_strategies.append((strategy_id, strategy))

                for strategy_id, strategy in due_strategies:
                    self._evaluate_strategy_from_cache(
                        strategy_id,
                        reason="runtime_cadence",
                    )
                    self._seed_runtime_cadence_for_strategy(
                        strategy_id,
                        strategy,
                        now=_d31_now_et() + timedelta(microseconds=1),
                        force=True,
                    )

                for strategy_id, strategy in strategy_snapshot:
                    self._evaluate_strategy_short_leg_risk(strategy_id, strategy)

                wait_seconds = 15.0
                with self._scheduled_strategy_lock:
                    if self._scheduled_strategy_due_at:
                        wait_seconds = max(
                            min(
                                min(self._scheduled_strategy_due_at.values()) - time.monotonic(),
                                15.0,
                            ),
                            0.05,
                        )
                self._scheduled_strategy_wakeup.wait(timeout=wait_seconds)
                self._scheduled_strategy_wakeup.clear()

            except Exception as exc:
                self.logger.error("Error in scheduled strategy loop: %s", exc, exc_info=True)
                self._scheduled_strategy_wakeup.wait(timeout=1.0)
                self._scheduled_strategy_wakeup.clear()

    # ==========================================================================
    # PRIVATE METHODS - ALLOCATION AND REBALANCING
    # ==========================================================================

    def _execute_rebalancing(self, reason: RebalanceReason) -> bool:
        """Execute portfolio rebalancing"""
        try:
            self.logger.info("🔄 Executing portfolio rebalancing - Reason: %s", reason.value)

            # Calculate new allocations
            new_allocations = self._calculate_optimal_allocations()

            if not new_allocations:
                self.logger.warning("No valid allocations calculated")
                return False

            # C1 (v18): snapshot allocations once under lock; use the snapshot
            # throughout this method so concurrent add/remove can't race us.
            with self._strategies_lock:
                _alloc_snap: dict = dict(self.strategy_allocations)

            # Store previous allocations
            previous_allocations = {
                sid: alloc.current_allocation
                for sid, alloc in _alloc_snap.items()
            }

            # Calculate capital movements
            capital_movements = {}
            total_capital = self.portfolio_metrics.total_capital

            for strategy_id, new_allocation in new_allocations.items():
                if strategy_id in _alloc_snap:
                    old_allocation = _alloc_snap[strategy_id].current_allocation
                    capital_change = (new_allocation - old_allocation) * total_capital
                    capital_movements[strategy_id] = capital_change

            # Execute rebalancing
            rebalance_successful = True

            for strategy_id, capital_change in capital_movements.items():
                if abs(capital_change) > 100:  # Only rebalance if change > $100
                    success = self._adjust_strategy_capital(strategy_id, capital_change)
                    if not success:
                        rebalance_successful = False
                        self.logger.error("Failed to adjust capital for strategy %s", strategy_id)

            # Update allocations if successful
            if rebalance_successful:
                for strategy_id, new_allocation in new_allocations.items():
                    if strategy_id in self.strategy_allocations:
                        allocation = self.strategy_allocations[strategy_id]
                        allocation.current_allocation = new_allocation
                        allocation.allocated_capital = new_allocation * total_capital
                        allocation.last_rebalance = datetime.now(UTC)
                        allocation.allocation_history.append((datetime.now(UTC), new_allocation))

            # Record rebalance event
            rebalance_event = RebalanceEvent(
                timestamp=datetime.now(UTC),
                reason=reason,
                previous_allocations=previous_allocations,
                new_allocations=new_allocations,
                capital_movements=capital_movements,
                expected_impact={},  # Could calculate expected impact
                execution_status="completed" if rebalance_successful else "failed"
            )

            self.rebalance_history.append(rebalance_event)
            self.last_rebalance = datetime.now(UTC)

            # Update portfolio metrics
            self._update_portfolio_metrics()

            status = "✅ completed" if rebalance_successful else "❌ failed"
            self.logger.info("Portfolio rebalancing %s", status)

            return rebalance_successful

        except Exception as e:
            self.logger.error("❌ Rebalancing execution failed: %s", e, exc_info=True)
            return False

    def _adjust_strategy_capital(self, strategy_id: str, capital_change: float) -> bool:
        """Validate and log a capital reallocation for a strategy.

        The caller (_execute_rebalancing) performs the actual accounting update
        (current_allocation, allocated_capital) only when ALL adjustments succeed.
        This method validates the strategy exists, logs the change, and returns
        True so the outer commit path proceeds.
        """
        try:
            if strategy_id not in self.strategy_allocations:
                self.logger.warning(
                    "Capital adjustment skipped — unknown strategy_id: %s", strategy_id
                )
                return False

            alloc = self.strategy_allocations[strategy_id]
            direction = "▲" if capital_change > 0 else "▼"
            self.logger.info(
                "Capital adjustment %s $%.0f for strategy %s (current allocated: $%.0f)",
                direction,
                abs(capital_change),
                strategy_id,
                alloc.allocated_capital,
            )
            return True
        except Exception as e:
            self.logger.error("Error in _adjust_strategy_capital for %s: %s", strategy_id, e, exc_info=True)
            return False

    def _get_risk_profile_for_strategy(self, strategy_class: type) -> RiskProfile:  # noqa: F821
        """Return a RiskProfile sized to this strategy's capital slice."""
        from SpyderD_Strategies.SpyderD01_BaseStrategy import RiskProfile  # lazy to avoid circular
        # Fraction of base_capital for a single strategy slot
        n = max(1, len(self.available_strategies))
        slice_size = self.base_capital / n
        return RiskProfile(account_size=slice_size)

    def _get_strategy_type(self, strategy_class: type) -> str:
        """Return a short human-readable strategy type string."""
        name = strategy_class.__name__
        # Strip common suffixes for a clean type label
        for suffix in ("Strategy", "Spyder", "D"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
        return name or strategy_class.__name__

    def _apply_strategy_runtime_config_defaults(
        self,
        strategy_name: str,
        config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Apply strategy defaults needed before admission-time classification."""
        resolved = dict(config or {})
        strategy_type_normalized = self._normalise_strategy_type_for_entry_gate(strategy_name)

        if strategy_type_normalized in {"broken_wing_butterfly", "jade_lizard_zero"}:
            resolved.setdefault("target_dte", 0)

        if strategy_type_normalized == "zero_hft":
            resolved.setdefault("target_dte", 0)
            resolved.setdefault("require_defined_risk_entry", True)
            if str(self._audit_run_mode or "").strip().lower() == "paper":
                if resolved.get("broker_client") is None:
                    broker_client = self._build_zero_hft_paper_quote_broker()
                    if broker_client is not None:
                        resolved["broker_client"] = broker_client
                if resolved.get("gamma_engine") is None and resolved.get("broker_client") is not None:
                    try:
                        from Spyder.SpyderN_OptionsAnalytics.SpyderN15_GammaRegimeEngine import GammaRegimeEngine

                        quote_broker = resolved["broker_client"]
                        resolved["gamma_engine"] = GammaRegimeEngine(
                            lambda underlying, expiration, quote_broker=quote_broker: quote_broker.get_option_chain_with_greeks(underlying, expiration),
                            underlying=str(resolved.get("symbol") or "SPX").upper(),
                        )
                    except Exception as exc:
                        self.logger.warning("ZeroHFT gamma engine defaults unavailable: %s", exc)

        return resolved

    def _build_zero_hft_paper_quote_broker(self) -> Any | None:
        """Build a quote-only paper adapter for ZeroHFT planning in D41."""
        if self._live_engine is None:
            return None

        quote_client_factory = getattr(self._live_engine, "_get_paper_option_quote_client", None)
        if not callable(quote_client_factory):
            return None

        try:
            quote_client = quote_client_factory()
        except Exception as exc:
            self.logger.warning("ZeroHFT quote client bootstrap failed: %s", exc)
            return None

        if quote_client is None:
            return None

        get_option_expirations = getattr(quote_client, "get_option_expirations", None)
        get_option_chain_with_greeks = getattr(quote_client, "get_option_chain_with_greeks", None)
        if not callable(get_option_expirations) or not callable(get_option_chain_with_greeks):
            return None

        return SimpleNamespace(
            trading_mode="paper",
            mode="paper",
            get_option_expirations=get_option_expirations,
            get_option_chain_with_greeks=get_option_chain_with_greeks,
        )

    def _resolve_horizon_bucket(self, strategy_name: str, config: dict[str, Any]) -> str:
        """Resolve strategy horizon bucket used for admission guardrails.

        Buckets:
        - ``ultra_short``: same-day / 0DTE style strategies
        - ``short``: intraday to 1DTE style strategies
        - ``swing``: multi-day decay/structure strategies (calendar/diagonal)

        A strategy can override classification via ``config['horizon_bucket']``.
        """
        raw = str((config or {}).get("horizon_bucket", "")).strip().lower()
        if raw in {"ultra_short", "short", "swing"}:
            return raw

        target_dte_raw = (config or {}).get("target_dte")
        try:
            target_dte = int(target_dte_raw)
        except (TypeError, ValueError):
            target_dte = None
        if target_dte is not None and 0 <= target_dte <= 1:
            return "ultra_short"

        normalized_name = strategy_name
        for suffix in ("Strategy", "Spyder", "D"):
            if normalized_name.endswith(suffix):
                normalized_name = normalized_name[: -len(suffix)]

        strategy_type_normalized = self._normalise_strategy_type_for_entry_gate(normalized_name)
        if strategy_type_normalized == "pivot_mean_reversion":
            return "ultra_short"

        name = strategy_name.lower()
        if "zerodte" in name or "0dte" in name:
            return "ultra_short"

        if any(token in name for token in ("calendar", "diagonal", "doublecalendar", "swing")):
            return "swing"

        return "short"

    def _infer_horizon_bucket_from_allocation(self, alloc: StrategyAllocation) -> str:
        """Return allocation bucket, inferring from strategy_type when absent."""
        bucket = str(getattr(alloc, "horizon_bucket", "")).strip().lower()
        if bucket in {"ultra_short", "short", "swing"}:
            return bucket

        strategy_type = str(getattr(alloc, "strategy_type", ""))
        return self._resolve_horizon_bucket(strategy_type, {})

    def _get_active_horizon_buckets_locked(self) -> set[str]:
        """Return active horizon buckets.

        Must be called while ``self._strategies_lock`` is held.
        """
        buckets: set[str] = set()
        for alloc in self.strategy_allocations.values():
            buckets.add(self._infer_horizon_bucket_from_allocation(alloc))
        return buckets

    def _get_active_horizon_bucket_counts_locked(self) -> dict[str, int]:
        """Return active strategy count per horizon bucket.

        Must be called while ``self._strategies_lock`` is held.

        Paused strategies are excluded from bucket occupancy so that a
        regime-transition ``add_strategy`` call can claim the vacated bucket
        immediately after the outgoing strategy is paused, rather than having
        to wait for a full removal cycle.
        """
        counts: dict[str, int] = {}
        for strategy_id, alloc in self.strategy_allocations.items():
            if strategy_id in self.paused_strategies:
                continue
            bucket = self._infer_horizon_bucket_from_allocation(alloc)
            counts[bucket] = counts.get(bucket, 0) + 1
        return counts

    def _allows_overlay_strategy_registration_locked(
        self,
        *,
        strategy_type: str,
        horizon_bucket: str,
    ) -> bool:
        """Return True when D31 may admit the ODTE overlay allocation exception.

        Must be called while ``self._strategies_lock`` is held.
        """
        if not self._overlay_slot_flag_enabled():
            return False

        # Fail closed if operators widened the baseline contract out-of-band.
        if self.max_concurrent_strategies != MAX_CONCURRENT_STRATEGIES:
            return False
        if self.max_active_horizon_buckets != MAX_ACTIVE_HORIZON_BUCKETS:
            return False

        strategy_type_normalized = self._normalise_strategy_type_for_entry_gate(strategy_type)
        if strategy_type_normalized != "pivot_mean_reversion":
            return False

        if horizon_bucket != "ultra_short":
            return False

        # The overlay only exists to admit PMR as the third live strategy while
        # bypassing the duplicate ultra_short horizon-bucket occupancy. It must
        # not widen the portfolio to a fourth active strategy.
        if len(self.active_strategies) != (MAX_CONCURRENT_STRATEGIES - 1):
            return False

        for alloc in self.strategy_allocations.values():
            active_strategy_type = self._normalise_strategy_type_for_entry_gate(
                getattr(alloc, "strategy_type", "")
            )
            if active_strategy_type == "pivot_mean_reversion":
                return False

        return True

    def _calculate_optimal_allocation(self, strategy_name: str) -> float:
        """Return an initial capital fraction for a single new strategy.

        Uses the regime weight map when available; falls back to equal-weight.
        """
        try:
            weights = self._get_regime_strategy_weights()
            # Match by substring so 'IronCondor' matches 'IronCondorStrategy'
            # C1 (v18): snapshot allocations once under lock before both sum() calls.
            with self._strategies_lock:
                _alloc_vals = list(self.strategy_allocations.values())
            for key, weight in weights.items():
                if key in strategy_name or strategy_name in key:
                    # Normalise so existing strategies retain their share
                    total_existing = sum(a.target_allocation for a in _alloc_vals)
                    remaining = max(0.0, 1.0 - total_existing)
                    return min(weight, remaining)
            # Fallback: equal split of remaining capital
            total_existing = sum(a.target_allocation for a in _alloc_vals)
            remaining = max(0.0, 1.0 - total_existing)
            # B3 (v15): read active_strategies count under lock.
            with self._strategies_lock:
                n_active = len(self.active_strategies)
            return remaining / max(1, len(self.available_strategies) - n_active)
        except Exception:
            return 0.10  # Safe 10 % default

    def _calculate_optimal_allocations(self) -> dict[str, float]:
        """Calculate optimal portfolio allocations"""
        try:
            if not self.active_strategies:
                return {}

            # Choose allocation method
            if self.allocation_method == AllocationMethod.EQUAL_WEIGHT:
                return self._calculate_equal_weight_allocations()
            elif self.allocation_method == AllocationMethod.PERFORMANCE_BASED:
                return self._calculate_performance_based_allocations()
            elif self.allocation_method == AllocationMethod.RISK_PARITY:
                return self._calculate_risk_parity_allocations()
            elif self.allocation_method == AllocationMethod.KELLY_CRITERION:
                return self._calculate_kelly_allocations()
            elif self.allocation_method == AllocationMethod.MARKET_REGIME:
                return self._calculate_regime_based_allocations()
            else:  # ADAPTIVE_ML
                return self._calculate_adaptive_ml_allocations()

        except Exception as e:
            self.logger.error("Error calculating optimal allocations: %s", e, exc_info=True)
            return {}

    def _calculate_performance_based_allocations(self) -> dict[str, float]:
        """Calculate allocations based on strategy performance"""
        try:
            allocations = {}
            performance_scores = {}

            # C1 (v18): snapshot to avoid RuntimeError if add/remove runs concurrently.
            with self._strategies_lock:
                _alloc_snap = list(self.strategy_allocations.items())

            # Calculate performance scores for each strategy
            for strategy_id, allocation in _alloc_snap:
                if strategy_id in self.active_strategies:
                    # Combine multiple performance metrics
                    performance_score = (
                        allocation.performance_score * 0.4 +  # Historical performance
                        allocation.health_score * 0.3 +       # Current health
                        (1 - allocation.risk_score) * 0.3     # Risk-adjusted (lower risk = higher score)  # noqa: E501
                    )

                    # Apply regime adjustment
                    regime_multiplier = self._get_strategy_regime_multiplier(allocation.strategy_type)  # noqa: E501
                    performance_score *= regime_multiplier

                    performance_scores[strategy_id] = max(0.1, performance_score)  # Minimum score

            # Normalize scores to allocations
            total_score = sum(performance_scores.values())

            if total_score > 0:
                for strategy_id, score in performance_scores.items():
                    base_allocation = score / total_score

                    # Apply allocation limits
                    allocation = max(MIN_STRATEGY_ALLOCATION,
                                   min(MAX_STRATEGY_ALLOCATION, base_allocation))

                    allocations[strategy_id] = allocation

                # Normalize to ensure allocations sum to 1.0
                total_allocation = sum(allocations.values())
                if total_allocation > 0:
                    allocations = {
                        sid: alloc / total_allocation
                        for sid, alloc in allocations.items()
                    }

            return allocations

        except Exception as e:
            self.logger.error("Error calculating performance-based allocations: %s", e, exc_info=True)  # noqa: E501
            return {}

    def _calculate_equal_weight_allocations(self) -> dict[str, float]:
        """Calculate equal weight allocations"""
        if not self.active_strategies:
            return {}

        equal_weight = 1.0 / len(self.active_strategies)
        return {strategy_id: equal_weight for strategy_id in self.active_strategies}

    def _calculate_risk_parity_allocations(self) -> dict[str, float]:
        """Calculate risk parity allocations"""
        try:
            allocations = {}
            risk_contributions = {}

            # C1 (v18): snapshot to avoid RuntimeError if add/remove runs concurrently.
            with self._strategies_lock:
                _alloc_snap = list(self.strategy_allocations.items())

            # Calculate risk contribution for each strategy
            for strategy_id, allocation in _alloc_snap:
                if strategy_id in self.active_strategies:
                    # Use inverse of risk score as weight (higher risk = lower weight)
                    risk_weight = 1.0 / max(0.1, allocation.risk_score)
                    risk_contributions[strategy_id] = risk_weight

            # Normalize to allocations
            total_risk_weight = sum(risk_contributions.values())
            if total_risk_weight > 0:
                for strategy_id, weight in risk_contributions.items():
                    allocation = weight / total_risk_weight
                    allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                                 min(MAX_STRATEGY_ALLOCATION, allocation))

                # Renormalize
                total_allocation = sum(allocations.values())
                if total_allocation > 0:
                    allocations = {
                        sid: alloc / total_allocation
                        for sid, alloc in allocations.items()
                    }

            return allocations

        except Exception as e:
            self.logger.error("Error calculating risk parity allocations: %s", e, exc_info=True)
            return {}

    def _calculate_kelly_allocations(self) -> dict[str, float]:
        """Calculate Kelly criterion allocations"""
        try:
            allocations = {}
            kelly_fractions = {}

            # C1 (v18): snapshot to avoid RuntimeError if add/remove runs concurrently.
            with self._strategies_lock:
                _alloc_snap = list(self.strategy_allocations.items())

            for strategy_id, _allocation in _alloc_snap:
                if strategy_id in self.active_strategies:
                    strategy = self.active_strategies[strategy_id]

                    # Calculate Kelly fraction based on win rate and profit factor
                    win_rate = getattr(strategy, 'win_rate', 0.5)
                    profit_factor = getattr(strategy, 'profit_factor', 1.0)

                    if profit_factor > 1.0 and win_rate > 0:
                        # Kelly formula: f = (bp - q) / b
                        # where b = odds received (profit_factor - 1), p = win_rate, q = 1 - p
                        b = profit_factor - 1
                        p = win_rate
                        q = 1 - p

                        kelly_fraction = (b * p - q) / b
                        kelly_fraction = max(0, min(KELLY_FRACTION_CAP, kelly_fraction))
                    else:
                        kelly_fraction = MIN_STRATEGY_ALLOCATION

                    kelly_fractions[strategy_id] = kelly_fraction

            # Normalize Kelly fractions to portfolio allocations
            total_kelly = sum(kelly_fractions.values())
            if total_kelly > 0:
                for strategy_id, fraction in kelly_fractions.items():
                    allocations[strategy_id] = fraction / total_kelly

            return allocations

        except Exception as e:
            self.logger.error("Error calculating Kelly allocations: %s", e, exc_info=True)
            return {}

    def _calculate_regime_based_allocations(self) -> dict[str, float]:
        """Calculate allocations based on current market regime"""
        try:
            allocations = {}
            regime_weights = self._get_regime_strategy_weights()

            if not regime_weights:
                # Fallback to equal weight
                return self._calculate_equal_weight_allocations()

            # Apply regime weights to active strategies
            total_weight = 0
            strategy_weights = {}

            # C1 (v18): snapshot to avoid RuntimeError if add/remove runs concurrently.
            with self._strategies_lock:
                _alloc_snap = list(self.strategy_allocations.items())

            for strategy_id, allocation in _alloc_snap:
                if strategy_id in self.active_strategies:
                    strategy_type = allocation.strategy_type
                    weight = regime_weights.get(strategy_type, 0.1)  # Default low weight

                    # Adjust for strategy health
                    weight *= allocation.health_score

                    strategy_weights[strategy_id] = weight
                    total_weight += weight

            # Normalize to allocations
            if total_weight > 0:
                for strategy_id, weight in strategy_weights.items():
                    allocation = weight / total_weight
                    allocations[strategy_id] = max(MIN_STRATEGY_ALLOCATION,
                                                 min(MAX_STRATEGY_ALLOCATION, allocation))

                # Final normalization
                total_allocation = sum(allocations.values())
                if total_allocation > 0:
                    allocations = {
                        sid: alloc / total_allocation
                        for sid, alloc in allocations.items()
                    }

            return allocations

        except Exception as e:
            self.logger.error("Error calculating regime-based allocations: %s", e, exc_info=True)
            return {}

    # ==========================================================================
    # PRIVATE METHODS - MARKET REGIME ANALYSIS
    # ==========================================================================

    def _update_market_regime(self):
        """Update current market regime analysis"""
        try:
            # This would integrate with market data feeds
            # For now, using simplified regime detection

            # Calculate volatility metrics
            # P1-01: resolve live VIX from C10 VIXAnalyzer, then market_data_cache,
            # then fall back to the conservative 20.0 default.
            current_vix: float = 20.0
            if self._vix_analyzer is not None:
                try:
                    _raw_vix = self._vix_analyzer.get_current_vix()
                    if _raw_vix is not None and float(_raw_vix) > 0:
                        current_vix = float(_raw_vix)
                except Exception as _ve:
                    self.logger.debug("VIXAnalyzer.get_current_vix() failed: %s", _ve)
            else:
                for _vix_key in ("VIX", "^VIX", "CBOE:VIX"):
                    _vix_entry = self.market_data_cache.get(_vix_key)
                    if isinstance(_vix_entry, (list, deque)) and _vix_entry:
                        _last = _vix_entry[-1]
                        _v = (
                            _last.get("close") or _last.get("price") or _last.get("last")
                            if isinstance(_last, dict) else None
                        )
                        if _v and float(_v) > 0:
                            current_vix = float(_v)
                            break
                    elif isinstance(_vix_entry, dict):
                        _v = (
                            _vix_entry.get("close")
                            or _vix_entry.get("price")
                            or _vix_entry.get("last")
                        )
                        if _v and float(_v) > 0:
                            current_vix = float(_v)
                            break
            vix_percentile = self._calculate_vix_percentile(current_vix)

            # Determine trend strength
            trend_strength = self._calculate_trend_strength()

            # Classify regime — prefer L09 UnifiedRegimeEngine when injected
            new_regime = self._classify_market_regime_unified(current_vix, vix_percentile, trend_strength)  # noqa: E501

            # Update regime data
            regime_changed = new_regime != self.market_regime.current_regime

            if regime_changed:
                self.market_regime.last_regime_change = datetime.now(UTC)
                self.market_regime.regime_duration_days = 0
                self.market_regime.regime_history.append((datetime.now(UTC), new_regime))
            else:
                # Update duration
                days_since_change = (datetime.now(UTC) - self.market_regime.last_regime_change).days
                self.market_regime.regime_duration_days = days_since_change

            self.market_regime.current_regime = new_regime
            self.market_regime.vix_level = current_vix
            self.market_regime.volatility_percentile = vix_percentile
            self.market_regime.trend_strength = trend_strength

            # Confidence: L09 supplies a real probability; fall back to duration heuristic
            l09_conf = self._last_l09_confidence
            self.market_regime.regime_confidence = (
                l09_conf if l09_conf > 0.0
                else min(1.0, self.market_regime.regime_duration_days / 5.0)
            )

            if regime_changed:
                self.logger.info("📊 Market regime changed to: %s", new_regime.value)

        except Exception as e:
            self.logger.error("Error updating market regime: %s", e, exc_info=True)

    def _classify_market_regime_unified(
        self,
        vix_level: float,
        vix_percentile: float,
        trend_strength: float,
    ) -> MarketRegime:
        """Classify regime via L09 UnifiedRegimeEngine when injected; else inline heuristic."""
        self._last_l09_confidence = 0.0
        self._last_l09_consensus = None

        # v27 SPEC-5: fail closed when regime cache is cold (boot, reconnect, feed
        # gap). Returning a fabricated regime locks the system into wrong
        # strategies for the cold-start window — the documented "no strategies
        # fire" pathology. CRISIS maps via D31's regime alias to
        # crisis_turbulent → no-trade, which is the safe behavior.
        #
        # v28 bridge: G18 (MarketDataWorker) writes live_data.json every 10 s
        # but does NOT publish EventType.MARKET_DATA events to the event bus, so
        # the cache is always cold in dashboard-only mode.  Attempt a live_data
        # recovery seed before failing to CRISIS (throttled to 30 s).
        self._recover_cache_if_cold()

        regime_symbol = self._regime_source_symbol
        spy_ticks = self.market_data_cache.get(regime_symbol, [])
        spy_closes = [
            self._coerce_float(t.get("close", t.get("price")))
            for t in spy_ticks
            if isinstance(t, dict)
        ]
        spy_closes = [float(c) for c in spy_closes if c is not None]
        if len(spy_closes) < 2:
            self.logger.warning(
                "D31 regime: %s cache has %d closes (<2) — failing closed to CRISIS",
                regime_symbol,
                len(spy_closes),
            )
            return MarketRegime.CRISIS

        if self._l09_engine is not None:
            try:
                from SpyderL_ML.SpyderL09_UnifiedRegimeEngine import (  # noqa: PLC0415
                    MarketConditions as _L09Cond,
                    MarketRegime as _L09R,
                )
                def _ema(values: list[float], period: int) -> float:
                    if len(values) < period:
                        return float("nan")
                    alpha = 2.0 / (period + 1.0)
                    ema_val = values[-period]
                    for val in values[-period + 1:]:
                        ema_val = alpha * val + (1.0 - alpha) * ema_val
                    return ema_val

                def _last_close(series: list[dict[str, Any]]) -> float:
                    for item in reversed(series):
                        if isinstance(item, dict):
                            value = item.get("close") or item.get("price") or item.get("last")
                            numeric = self._coerce_float(value)
                            if numeric is not None:
                                return float(numeric)
                    return float("nan")
                # Build MarketConditions from cached regime symbol + VIX ticks
                spy_ticks = self.market_data_cache.get(regime_symbol, [])
                # v27 SPEC-5: do NOT fall back to a hardcoded $500 — that
                # fabricates regime classification on cold start. Use NaN as the
                # sentinel and fail closed below if the cache lacks ≥2 closes.
                spy_price, spy_change_pct = float("nan"), 0.0
                closes = [
                    self._coerce_float(t.get("close", t.get("price", 0.0)))
                    for t in spy_ticks if isinstance(t, dict)
                ]
                closes = [float(c) for c in closes if c is not None]
                if len(closes) >= 2:
                    spy_price = closes[-1]
                    spy_change_pct = (closes[-1] - closes[0]) / closes[0] * 100.0
                else:
                    # v27 SPEC-5: regime-symbol cache cold (boot, reconnect, or feed gap)
                    # → fail closed to CRISIS so D31's regime alias maps to
                    # crisis_turbulent → no-trade. This closes the documented
                    # "no strategies fire" pathology.
                    self.logger.warning(
                        "D31 regime classification: %s cache has %d closes (<2) — "
                        "failing closed to CRISIS regime",
                        regime_symbol,
                        len(closes),
                    )
                    return MarketRegime.CRISIS

                spy_ema50 = _ema(closes, 50)

                atr = float("nan")
                atr_pct = float("nan")
                if len(spy_ticks) >= 2:
                    highs = [t.get("high") for t in spy_ticks if isinstance(t, dict)]
                    lows = [t.get("low") for t in spy_ticks if isinstance(t, dict)]
                    highs = [self._coerce_float(v) for v in highs]
                    lows = [self._coerce_float(v) for v in lows]
                    highs = [float(v) for v in highs if v is not None]
                    lows = [float(v) for v in lows if v is not None]
                    if highs and lows and len(highs) == len(lows) and len(closes) >= 2:
                        tr_values: list[float] = []
                        for idx in range(1, min(len(highs), len(lows), len(closes))):
                            high = highs[idx]
                            low = lows[idx]
                            prev_close = closes[idx - 1]
                            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                            tr_values.append(tr)
                        if tr_values:
                            atr = sum(tr_values[-14:]) / min(len(tr_values), 14)
                    elif len(closes) >= 2:
                        diffs = [abs(closes[i] - closes[i - 1]) for i in range(1, len(closes))]
                        atr = sum(diffs[-14:]) / min(len(diffs), 14)

                if isinstance(atr, (int, float)) and atr > 0 and spy_price > 0:
                    atr_pct = atr / spy_price

                vix_ticks = self.market_data_cache.get("VIX", [])
                if not vix_ticks:
                    vix_ticks = self.market_data_cache.get("^VIX", [])
                vix_values = [
                    self._coerce_float(t.get("close", t.get("price", 0.0)))
                    for t in vix_ticks if isinstance(t, dict)
                ]
                vix_values = [float(v) for v in vix_values if v is not None]
                # v27 SPEC-5: VIX is required for risk-on/risk-off discrimination.
                # If the VIX cache is cold, fail closed rather than running L09
                # on SPY-only data.
                if not vix_values:
                    self.logger.warning(
                        "D31 regime classification: VIX cache empty — "
                        "failing closed to CRISIS regime"
                    )
                    return MarketRegime.CRISIS
                vix_ema50 = _ema(vix_values, 50)

                vix9d = _last_close(self.market_data_cache.get("VIX9D", []) or self.market_data_cache.get("^VIX9D", []))
                vxv = _last_close(self.market_data_cache.get("VXV", []) or self.market_data_cache.get("^VXV", []))

                event_clock = self.market_data_cache.get("event_clock_state")
                event_state = "clear"
                if isinstance(event_clock, dict):
                    event_state = str(event_clock.get("state", "clear"))

                conditions = _L09Cond(
                    timestamp=datetime.now(UTC),
                    spy_price=spy_price,
                    spy_change_pct=spy_change_pct,
                    volume_ratio=1.0,
                    vix_level=vix_level,
                    vix9d_level=vix9d,
                    vxv_level=vxv,
                    vix_percentile=vix_percentile,
                    spy_ema50=spy_ema50,
                    vix_ema50=vix_ema50,
                    spy_atr=atr,
                    spy_atr_pct=atr_pct,
                    event_clock_state=event_state,
                    trend_strength=trend_strength,
                    volatility_regime=vix_percentile / 100.0,
                )
                consensus = self._l09_engine.get_current_regime(conditions)
                self._last_l09_confidence = consensus.confidence
                self._last_l09_consensus = consensus
                self.logger.debug(
                    "📊 L09 regime: %s (conf=%.2f)", consensus.regime.value, consensus.confidence
                )

                # D30 RegimeGatedSelector already uses confidence_threshold=70 %.
                # Apply the same gate here: if L09's confidence is below that bar,
                # its classification is too ambiguous to override the heuristic path.
                _L09_CONFIDENCE_THRESHOLD = 0.70
                if consensus.confidence < _L09_CONFIDENCE_THRESHOLD:
                    self.logger.debug(
                        "📊 L09 conf %.2f < %.2f threshold — deferring to heuristic classifier "
                        "(L09 said %s)",
                        consensus.confidence,
                        _L09_CONFIDENCE_THRESHOLD,
                        consensus.regime.value,
                    )
                    return self._classify_market_regime(vix_level, vix_percentile, trend_strength)

                is_high_vol = vix_level > VIX_REGIME_THRESHOLDS["high"]
                l09_r = consensus.regime
                if l09_r == _L09R.EVENT_TRANSITION:
                    return MarketRegime.EVENT_TRANSITION
                if l09_r == _L09R.CRISIS_MODE:
                    return MarketRegime.CRISIS
                if l09_r == _L09R.HIGH_VOLATILITY:
                    return MarketRegime.SIDEWAYS_HIGH_VOL
                if l09_r == _L09R.SIDEWAYS_RANGE:
                    return MarketRegime.SIDEWAYS_LOW_VOL
                if l09_r == _L09R.BULL_TRENDING:
                    return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL
                if l09_r == _L09R.BEAR_TRENDING:
                    return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL
                return MarketRegime.SIDEWAYS_HIGH_VOL if is_high_vol else MarketRegime.SIDEWAYS_LOW_VOL

            except Exception as e:
                self.logger.warning("L09 regime detection failed, using fallback: %s", e)

        return self._classify_market_regime(vix_level, vix_percentile, trend_strength)

    def _classify_market_regime(self, vix_level: float, vix_percentile: float, trend_strength: float) -> MarketRegime:  # noqa: E501
        """Classify current market regime"""
        def _ema(values: list[float], period: int) -> float:
            if len(values) < period:
                return float("nan")
            alpha = 2.0 / (period + 1.0)
            ema_val = values[-period]
            for val in values[-period + 1:]:
                ema_val = alpha * val + (1.0 - alpha) * ema_val
            return ema_val

        def _last_close(series: list[dict[str, Any]]) -> float:
            for item in reversed(series):
                if isinstance(item, dict):
                    value = item.get("close") or item.get("price") or item.get("last")
                    numeric = self._coerce_float(value)
                    if numeric is not None:
                        return float(numeric)
            return float("nan")

        is_high_vol = vix_level > VIX_REGIME_THRESHOLDS['high']
        is_crisis = vix_level > VIX_REGIME_THRESHOLDS['extreme']

        event_clock = self.market_data_cache.get("event_clock_state")
        event_state = "clear"
        if isinstance(event_clock, dict):
            event_state = str(event_clock.get("state", "clear")).strip().lower()
        if event_state in {"pre", "live", "post"}:
            return MarketRegime.EVENT_TRANSITION

        regime_symbol = self._regime_source_symbol
        spy_ticks = self.market_data_cache.get(regime_symbol, [])
        spy_closes = [
            self._coerce_float(t.get("close", t.get("price")))
            for t in spy_ticks
            if isinstance(t, dict)
        ]
        spy_closes = [float(c) for c in spy_closes if c is not None]
        spy_price = spy_closes[-1] if spy_closes else float("nan")
        spy_ema50 = _ema(spy_closes, 50)

        atr = float("nan")
        atr_pct = float("nan")
        highs = [self._coerce_float(t.get("high")) for t in spy_ticks if isinstance(t, dict)]
        lows = [self._coerce_float(t.get("low")) for t in spy_ticks if isinstance(t, dict)]
        highs = [float(v) for v in highs if v is not None]
        lows = [float(v) for v in lows if v is not None]
        if highs and lows and len(highs) == len(lows) and len(spy_closes) >= 2:
            tr_values: list[float] = []
            for idx in range(1, min(len(highs), len(lows), len(spy_closes))):
                high = highs[idx]
                low = lows[idx]
                prev_close = spy_closes[idx - 1]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            if tr_values:
                atr = sum(tr_values[-14:]) / min(len(tr_values), 14)
        elif len(spy_closes) >= 2:
            diffs = [abs(spy_closes[i] - spy_closes[i - 1]) for i in range(1, len(spy_closes))]
            if diffs:
                atr = sum(diffs[-14:]) / min(len(diffs), 14)

        if isinstance(atr, (int, float)) and atr > 0 and spy_price > 0:
            atr_pct = atr / spy_price

        vix_ticks = self.market_data_cache.get("VIX", []) or self.market_data_cache.get("^VIX", [])
        vix_values = [
            self._coerce_float(t.get("close", t.get("price", 0.0)))
            for t in vix_ticks
            if isinstance(t, dict)
        ]
        vix_values = [float(v) for v in vix_values if v is not None]
        vix_ema50 = _ema(vix_values, 50)

        vix9d = _last_close(self.market_data_cache.get("VIX9D", []) or self.market_data_cache.get("^VIX9D", []))
        vxv = _last_close(self.market_data_cache.get("VXV", []) or self.market_data_cache.get("^VXV", []))

        spy_change_pct = 0.0
        if len(spy_closes) >= 2 and spy_closes[0] != 0:
            spy_change_pct = (spy_closes[-1] - spy_closes[0]) / spy_closes[0] * 100.0

        if (
            (not math.isnan(vix9d) and vix9d > vix_level)
            or is_crisis
            or (spy_change_pct <= -1.25 and trend_strength < 0 and vix_level >= 4.0)
        ):
            return MarketRegime.CRISIS

        if not math.isnan(spy_price) and not math.isnan(spy_ema50) and not math.isnan(vix_ema50):
            if spy_price > spy_ema50 and vix_level < vix_ema50:
                return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL
            if spy_price < spy_ema50 and vix_level > vix_ema50:
                return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL

        term_structure_ok = False
        if not math.isnan(vix9d):
            term_structure_ok = vix9d <= vix_level
        elif not math.isnan(vxv):
            term_structure_ok = vix_level <= vxv

        if (
            not math.isnan(spy_price)
            and not math.isnan(spy_ema50)
            and not math.isnan(atr)
            and abs(spy_price - spy_ema50) <= atr
            and term_structure_ok
        ):
            return MarketRegime.SIDEWAYS_LOW_VOL

        if (
            not math.isnan(atr_pct)
            and atr_pct >= 0.015
            and (vix_percentile >= 80.0 or vix_level >= 25.0)
        ):
            return MarketRegime.SIDEWAYS_HIGH_VOL

        is_trending_up = trend_strength > 0.3
        is_trending_down = trend_strength < -0.3

        if is_crisis:
            return MarketRegime.CRISIS
        elif is_trending_up:
            return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL
        elif is_trending_down:
            return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL
        else:
            return MarketRegime.SIDEWAYS_HIGH_VOL if is_high_vol else MarketRegime.SIDEWAYS_LOW_VOL

    def _calculate_vix_percentile(self, current_vix: float) -> float:
        """Return an approximate VIX percentile (0-100) based on historical bands."""
        # Long-run VIX distribution approximation
        if current_vix <= 12:
            return 10.0
        elif current_vix <= 16:
            return 25.0
        elif current_vix <= 20:
            return 50.0
        elif current_vix <= 25:
            return 70.0
        elif current_vix <= 30:
            return 85.0
        elif current_vix <= 40:
            return 95.0
        else:
            return 99.0

    def _calculate_trend_strength(self) -> float:
        """Return a trend strength score in [-1, +1] from cached market data.

        Positive = bullish, negative = bearish, 0 = sideways.
        Uses a simple price-momentum heuristic from the active regime symbol.
        """
        try:
            regime_symbol = self._regime_source_symbol
            spy_ticks = self.market_data_cache.get(regime_symbol, [])
            if len(spy_ticks) < 2:
                return 0.0
            # Use last vs first cached price as a simple momentum proxy
            closes = [t.get("close", t.get("price", 0.0)) for t in spy_ticks if isinstance(t, dict)]
            closes = [c for c in closes if c]
            if len(closes) < 2:
                return 0.0
            pct_change = (closes[-1] - closes[0]) / closes[0]
            # Clip to [-1, +1]
            return max(-1.0, min(1.0, pct_change * 20))  # 5 % move → 1.0
        except Exception:
            return 0.0

    def _get_d30_selector(self) -> Any | None:
        """Return cached D30 selector instance, creating it lazily."""
        if self._d30_selector is not None:
            return self._d30_selector
        if self._d30_selector_init_attempted:
            return None

        self._d30_selector_init_attempted = True
        selector_cls = None
        try:
            from Spyder.SpyderD_Strategies.SpyderD30_RegimeGatedSelector import (  # noqa: PLC0415
                RegimeGatedSelector as _Selector,
            )

            selector_cls = _Selector
        except Exception:
            try:
                from SpyderD_Strategies.SpyderD30_RegimeGatedSelector import (  # noqa: PLC0415
                    RegimeGatedSelector as _Selector,
                )

                selector_cls = _Selector
            except Exception as exc:
                self.logger.warning(
                    "D31 lean selector unavailable (D30 import failed): %s",
                    exc,
                )
                return None

        try:
            self._d30_selector = selector_cls()
            self.logger.debug("D31 wired with D30 RegimeGatedSelector")
        except Exception as exc:
            self.logger.warning(
                "D31 could not initialize D30 RegimeGatedSelector: %s",
                exc,
            )
            self._d30_selector = None

        return self._d30_selector

    def _build_d30_consensus(self) -> Any | None:
        """Build a D30-compatible consensus object from the latest regime state."""
        if self._last_l09_consensus is not None and hasattr(self._last_l09_consensus, "regime"):
            return self._last_l09_consensus

        try:
            from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import MarketRegime as _L09R  # noqa: PLC0415
        except Exception:
            try:
                from SpyderL_ML.SpyderL09_UnifiedRegimeEngine import MarketRegime as _L09R  # noqa: PLC0415
            except Exception:
                return None

        recovery_member = getattr(_L09R, "RECOVERY_MODE", getattr(_L09R, "BULL_TRENDING", None))
        regime_map: dict[MarketRegime, Any] = {
            MarketRegime.BULL_LOW_VOL: _L09R.BULL_TRENDING,
            MarketRegime.BULL_HIGH_VOL: _L09R.BULL_TRENDING,
            MarketRegime.BEAR_LOW_VOL: _L09R.BEAR_TRENDING,
            MarketRegime.BEAR_HIGH_VOL: _L09R.BEAR_TRENDING,
            MarketRegime.SIDEWAYS_LOW_VOL: _L09R.SIDEWAYS_RANGE,
            MarketRegime.SIDEWAYS_HIGH_VOL: _L09R.HIGH_VOLATILITY,
            MarketRegime.CRISIS: _L09R.CRISIS_MODE,
            MarketRegime.EVENT_TRANSITION: _L09R.EVENT_TRANSITION,
        }
        if recovery_member is not None:
            regime_map[MarketRegime.RECOVERY] = recovery_member

        current_regime = self.market_regime.current_regime
        l09_regime = regime_map.get(current_regime, getattr(_L09R, "UNKNOWN", None))
        if l09_regime is None:
            return None

        return SimpleNamespace(
            regime=l09_regime,
            confidence=float(getattr(self.market_regime, "regime_confidence", 0.0) or 0.0),
            timestamp=datetime.now(UTC),
        )

    def _get_cached_pivot_signal_for_selector(self) -> dict[str, Any] | None:
        """Return latest pivot payload from cached market conditions if available."""
        cache = self.market_data_cache
        if not isinstance(cache, dict):
            return None

        candidates: list[Any] = []
        for key in ("pivot_signal", "pivot_mr_signal", "pivot"):
            if isinstance(cache.get(key), dict):
                candidates.append(cache.get(key))

        market_conditions = cache.get("market_conditions")
        if isinstance(market_conditions, dict):
            for key in ("pivot_signal", "pivot_mr_signal", "pivot"):
                if isinstance(market_conditions.get(key), dict):
                    candidates.append(market_conditions.get(key))

        for candidate in candidates:
            payload = self._extract_pivot_signal_payload(candidate)
            if payload:
                return payload

        return None

    @staticmethod
    def _map_selector_strategy_to_registry_name(strategy_value: Any) -> str | None:
        """Map D30 StrategyType values to D31 strategy registry keys."""
        raw = str(strategy_value or "").strip().lower()
        strategy_map = {
            "bull_put_spread": "BullPutSpread",
            "put_credit_spread_7": "PutCreditSpread7",
            "bear_call_spread": "BearCallSpread",
            "iron_condor": "IronCondor",
            "iron_butterfly": "IronButterfly",
            "broken_wing_butterfly": "BrokenWingButterfly",
            "bullish_strangle": "BullishStrangle",
            "butterfly": "Butterfly",
            "bull_call_spread": "BullCallSpread",
            "bear_put_spread": "BearPutSpread",
            "calendar_spread": "CalendarSpread",
            "calendar_spreads": "CalendarSpread",
            "pivot_mean_reversion": "PivotMeanReversion",
            "no_trade": None,
        }
        return strategy_map.get(raw)

    @staticmethod
    def _normalize_allowed_strategy_token(token: str, canonical_map: dict[str, str]) -> str | None:
        """Normalize a strategy token to a canonical D31 registry name."""
        cleaned = str(token or "").strip()
        if not cleaned:
            return None

        direct = canonical_map.get(cleaned.lower())
        if direct:
            return direct

        mapped = StrategyOrchestrator._map_selector_strategy_to_registry_name(cleaned)
        if mapped:
            via_selector = canonical_map.get(mapped.lower())
            if via_selector:
                return via_selector

        if cleaned.lower().endswith("strategy"):
            trimmed = cleaned[:-8].strip()
            return canonical_map.get(trimmed.lower())

        return None

    def _apply_env_allowed_strategies_override(self) -> None:
        """Constrain lean allowlist via SPYDER_ALLOWED_STRATEGIES when provided."""
        raw_override = str(os.getenv("SPYDER_ALLOWED_STRATEGIES", "")).strip()
        if not raw_override:
            return

        canonical_base_map: dict[str, str] = {}
        for value in self.lean_strategy_allowlist:
            base = value[:-8] if value.endswith("Strategy") else value
            canonical_base_map[base.lower()] = base

        selected_bases: set[str] = set()
        unknown_tokens: list[str] = []
        for token in raw_override.split(","):
            canonical = self._normalize_allowed_strategy_token(token, canonical_base_map)
            if canonical:
                selected_bases.add(canonical)
            elif str(token).strip():
                unknown_tokens.append(str(token).strip())

        if unknown_tokens:
            self.logger.warning(
                "D31 ignoring unknown SPYDER_ALLOWED_STRATEGIES entries: %s",
                ", ".join(unknown_tokens),
            )

        if not selected_bases:
            self.logger.warning(
                "D31 received SPYDER_ALLOWED_STRATEGIES override but no valid strategies were resolved"
            )
            return

        constrained: set[str] = set()
        for base in selected_bases:
            constrained.add(base)
            constrained.add(f"{base}Strategy")
        self.lean_strategy_allowlist = constrained

        self.logger.info(
            "D31 lean allowlist constrained by SPYDER_ALLOWED_STRATEGIES: %s",
            ", ".join(sorted(selected_bases)),
        )

    def _maybe_override_paper_calendar_spread_selection(
        self,
        strategy_name: str | None,
        selector_reason: str,
    ) -> tuple[str | None, str]:
        """Optionally override low-vol paper lean selections to CalendarSpread."""
        if strategy_name is None:
            return None, selector_reason
        if not self._paper_calendar_spread_routing_flag_enabled() or self._is_live_mode():
            return strategy_name, selector_reason

        regime = self.market_regime.current_regime
        override_candidates = {
            MarketRegime.BULL_LOW_VOL: {"BullPutSpread"},
            MarketRegime.BEAR_LOW_VOL: {"BearCallSpread"},
            MarketRegime.SIDEWAYS_LOW_VOL: {"IronCondor"},
        }
        allowed_sources = override_candidates.get(regime)
        if not allowed_sources or strategy_name not in allowed_sources:
            return strategy_name, selector_reason

        # D31's non-lean regime weights already include CalendarSpread in these
        # low-volatility regimes; this paper-only flag opts lean mode into the
        # same family without changing any live defaults.
        override_reason = f"paper_calendar_spread_override:{regime.value}:{selector_reason or strategy_name}"
        return "CalendarSpread", override_reason

    def _fallback_lean_strategy_name(self) -> str | None:
        """Fallback lean mapping when D30 selector or consensus is unavailable."""
        regime = self.market_regime.current_regime
        if regime in {MarketRegime.CRISIS, MarketRegime.EVENT_TRANSITION}:
            return None

        bull_call_enabled = str(os.getenv("SPYDER_ENABLE_BULL_CALL_SPREAD", "")).strip().lower() in {
            "1", "true", "yes", "on", "y"
        }
        bear_put_enabled = str(os.getenv("SPYDER_ENABLE_BEAR_PUT_SPREAD", "")).strip().lower() in {
            "1", "true", "yes", "on", "y"
        }
        bullish_strangle_enabled = str(
            os.getenv("SPYDER_ENABLE_BULLISH_STRANGLE", "")
        ).strip().lower() in {"1", "true", "yes", "on", "y"}
        put_credit_spread_7_enabled = str(
            os.getenv("SPYDER_ENABLE_PUT_CREDIT_SPREAD_7", "")
        ).strip().lower() in {"1", "true", "yes", "on", "y"}
        pivot_enabled = str(os.getenv("SPYDER_ENABLE_PIVOT_MEAN_REVERSION", "")).strip().lower() in {
            "1", "true", "yes", "on", "y"
        }
        pivot_payload = self._get_cached_pivot_signal_for_selector() or {}
        pivot_fired = bool(pivot_payload.get("fired", False))

        if regime == MarketRegime.RECOVERY and bullish_strangle_enabled:
            return "BullishStrangle"
        if regime in {MarketRegime.BULL_LOW_VOL, MarketRegime.BULL_HIGH_VOL, MarketRegime.RECOVERY}:
            if put_credit_spread_7_enabled and self._put_credit_spread_7_eligible_now():
                return "PutCreditSpread7"
            return "BullCallSpread" if bull_call_enabled else "BullPutSpread"
        if regime in {MarketRegime.BEAR_LOW_VOL, MarketRegime.BEAR_HIGH_VOL}:
            return "BearPutSpread" if bear_put_enabled else "BearCallSpread"
        if regime == MarketRegime.SIDEWAYS_LOW_VOL:
            if pivot_enabled and pivot_fired:
                return "PivotMeanReversion"
            return "IronCondor"
        if regime == MarketRegime.SIDEWAYS_HIGH_VOL:
            if bullish_strangle_enabled and pivot_fired:
                return "BullishStrangle"
            return "IronButterfly"

        return None

    @staticmethod
    def _put_credit_spread_7_eligible_now() -> bool:
        """Return True when the weekly seven-DTE strategy is selectable now."""
        if str(os.getenv("SPYDER_ENABLE_PUT_CREDIT_SPREAD_7", "")).strip().lower() not in {
            "1",
            "true",
            "yes",
            "on",
            "y",
        }:
            return False
        return bool(_d31_put_credit_spread_7_entry_window_open(_d31_now_et()))

    def _paper_fail_closed_selector_reason(
        self,
        strategy_name: str | None,
        selector_reason: str,
    ) -> str | None:
        """Return a fail-closed reason for untyped paper IronCondor selection."""
        if self._is_live_mode() or strategy_name != "IronCondor":
            return None

        normalized_reason = str(selector_reason or "").strip().lower()
        # Only block truly untyped fallbacks (D31 plain fallback and D30's
        # untyped neutral-posture else-branch).  D30 regime-named fallback
        # paths such as "Range/calm fallback regime — Iron Condor" are typed
        # selections and must NOT be blocked.
        _UNTYPED_FALLBACK_TOKENS = ("fallback_lean_mapping", "fallback neutral posture")
        if any(token in normalized_reason for token in _UNTYPED_FALLBACK_TOKENS):
            return f"untyped_selector_iron_condor:{selector_reason or 'fallback_lean_mapping'}"

        return None

    def _select_strategy_name_for_regime(self) -> tuple[str | None, str]:
        """Resolve the current lean strategy via D30, with deterministic fallback."""
        self._last_selector_feature_flag = None
        selector = self._get_d30_selector()
        consensus = self._build_d30_consensus()

        if selector is not None and consensus is not None:
            try:
                selection = selector.select_strategy_from_consensus(
                    consensus,
                    pivot_signal=self._get_cached_pivot_signal_for_selector(),
                )
                self._last_selector_feature_flag = getattr(selection, "selector_feature_flag", None)
                strategy_value = getattr(getattr(selection, "selected_strategy", None), "value", None)
                strategy_name = self._map_selector_strategy_to_registry_name(strategy_value)
                reason = str(getattr(selection, "reason", strategy_value or "selector_result"))
                strategy_name, reason = self._maybe_override_paper_calendar_spread_selection(
                    strategy_name,
                    reason,
                )
                fail_closed_reason = self._paper_fail_closed_selector_reason(strategy_name, reason)
                if fail_closed_reason is not None:
                    self.logger.warning(
                        "D31 paper selector fail-closed: blocking %s due to %s",
                        strategy_name,
                        reason,
                    )
                    return None, f"paper_fail_closed:{fail_closed_reason}"
                return strategy_name, reason
            except Exception as exc:
                self.logger.warning("D31 selector execution failed; using fallback map: %s", exc)

        fallback_name = self._fallback_lean_strategy_name()
        fallback_reason = "fallback_lean_mapping"
        fallback_name, fallback_reason = self._maybe_override_paper_calendar_spread_selection(
            fallback_name,
            fallback_reason,
        )
        fail_closed_reason = self._paper_fail_closed_selector_reason(
            fallback_name,
            fallback_reason,
        )
        if fail_closed_reason is not None:
            self.logger.warning(
                "D31 paper selector fail-closed: blocking %s due to fallback lean mapping",
                fallback_name,
            )
            return None, f"paper_fail_closed:{fail_closed_reason}"
        return fallback_name, fallback_reason

    def _get_regime_strategy_weights(self) -> dict[str, float]:
        """Get optimal strategy weights for current regime"""
        regime = self.market_regime.current_regime

        if self.lean_mode:
            strategy_name, selector_reason = self._select_strategy_name_for_regime()
            self._record_selector_outcome_audit(strategy_name, selector_reason)
            if not strategy_name:
                return {}

            if strategy_name not in self.lean_strategy_allowlist:
                self.logger.warning(
                    "D31 lean selector blocked by allowlist: regime=%s strategy=%s reason=%s",
                    regime.value,
                    strategy_name,
                    selector_reason,
                )
                return {}

            self.logger.debug(
                "D31 lean selector: regime=%s strategy=%s reason=%s feature_flag=%s",
                regime.value,
                strategy_name,
                selector_reason,
                self._last_selector_feature_flag,
            )
            return {strategy_name: 1.0}

        # Strategy weights by regime (this would be backtested/optimized)
        regime_weights = {
            MarketRegime.BULL_LOW_VOL: {
                'IronCondor': 0.3,
                'CreditSpread': 0.2,
                'IronButterfly': 0.15,
                'ZeroDTE': 0.1,
                'Straddle': 0.1,
                'CalendarSpread': 0.1,
                'JadeLizard': 0.05,
                'MACrossover': 0.05,
            },
            MarketRegime.BULL_HIGH_VOL: {
                'CreditSpread': 0.35,
                'Straddle': 0.25,
                'ZeroDTE': 0.2,
                'IronCondor': 0.1,
                'GammaScalper': 0.1,
                'RSIMeanReversion': 0.05,
            },
            MarketRegime.BEAR_LOW_VOL: {
                'CreditSpread': 0.3,
                'IronCondor': 0.25,
                'IronButterfly': 0.2,
                'ZeroDTE': 0.1,
                'CalendarSpread': 0.15,
                'RenaissanceMeanReversion': 0.05,
            },
            MarketRegime.BEAR_HIGH_VOL: {
                'Straddle': 0.35,
                'CreditSpread': 0.3,
                'ZeroDTE': 0.2,
                'GammaScalper': 0.15,
                'RSIMeanReversion': 0.1,
            },
            MarketRegime.SIDEWAYS_LOW_VOL: {
                'IronCondor': 0.35,
                'IronButterfly': 0.25,
                'CalendarSpread': 0.15,
                'CreditSpread': 0.15,
                'JadeLizard': 0.1,
                'PivotMeanReversion': 0.1,
            },
            MarketRegime.SIDEWAYS_HIGH_VOL: {
                'IronCondor': 0.25,
                'Straddle': 0.25,
                'CreditSpread': 0.2,
                'GammaScalper': 0.15,
                'ZeroDTE': 0.15,
                'PivotMeanReversion': 0.1,
            },
            MarketRegime.CRISIS: {
                'CreditSpread': 0.6,
                'Straddle': 0.4,
                'RSIMeanReversion': 0.1,
            }
        }

        if self._put_credit_spread_7_eligible_now():
            bull_low_vol = regime_weights.get(MarketRegime.BULL_LOW_VOL)
            if bull_low_vol is not None:
                bull_low_vol['PutCreditSpread7'] = 0.25
            bull_high_vol = regime_weights.get(MarketRegime.BULL_HIGH_VOL)
            if bull_high_vol is not None:
                bull_high_vol['PutCreditSpread7'] = 0.15

        return regime_weights.get(regime, {})

    # ==========================================================================
    # PRIVATE METHODS - UTILITIES
    # ==========================================================================

    def _configure_strategies_for_regime(self) -> None:
        """Instantiate and start strategies appropriate for the current market regime.

        Reads the regime-weight map, selects the top strategies that are in
        ``available_strategies``, and calls ``add_strategy`` for each one that
        is not already active.  Allocation fractions come from the regime weight
        map (normalised to sum ≤ 1.0).
        """
        with self._strategy_configuration_lock:
            try:
                self.logger.debug(
                    "📋 Configuring strategies for regime: %s",
                    self.market_regime.current_regime.value,
                )

                if not self.available_strategies:
                    self.logger.warning(
                        "No strategy classes registered — cannot configure strategies"
                    )
                    return

                regime_weights = self._get_regime_strategy_weights()
                if not regime_weights:
                    if self.lean_mode:
                        self.logger.info("Lean regime has no active strategies; skipping registration")
                        return
                    # Fallback: equal-weight up to 3 registered strategies
                    names = list(self.available_strategies.keys())[:3]
                    weight = round(1.0 / max(len(names), 1), 4)
                    regime_weights = {n: weight for n in names}

                # Only instantiate strategies not already active (by type name)
                # C1 (v18): snapshot under lock before set-comp to avoid iteration race.
                with self._strategies_lock:
                    active_types = {
                        alloc.strategy_type
                        for alloc in self.strategy_allocations.values()
                    }

                total_w = sum(
                    w for n, w in regime_weights.items()
                    if n in self.available_strategies and n not in active_types
                )

                for strategy_name, weight in regime_weights.items():
                    if strategy_name not in self.available_strategies:
                        continue
                    if strategy_name in active_types:
                        continue

                    allocation = (weight / total_w) * 0.9 if total_w > 0 else 0.1  # cap at 90 % total
                    strategy_class = self._resolve_registered_strategy_class(strategy_name)
                    if strategy_class is None:
                        self.logger.warning(
                            "  ⚠️  Strategy class unavailable at activation time: %s",
                            strategy_name,
                        )
                        continue
                    config: dict[str, Any] = {
                        "symbol": "SPY",
                        "allocated_capital": self.base_capital * allocation,
                    }
                    try:
                        self.add_strategy(strategy_class, config, initial_allocation=allocation)
                        self.logger.debug(
                            "  ✅ %s registered with %.1f%% allocation", strategy_name, allocation * 100
                        )
                    except Exception as exc:
                        self.logger.warning(
                            "  ⚠️  Could not add strategy %s: %s", strategy_name, exc
                        )

            except Exception as e:
                self.logger.error(
                    "Error configuring strategies for regime: %s", e, exc_info=True
                )

    def _perform_initial_allocation(self) -> None:
        """Set initial capital allocations for all currently active strategies."""
        try:
            if not self.active_strategies:
                self.logger.debug("No active strategies — skipping initial allocation")
                return

            self.logger.debug("💰 Performing initial capital allocation…")
            allocations = self._calculate_optimal_allocations()

            for strategy_id, fraction in allocations.items():
                if strategy_id in self.strategy_allocations:
                    self.strategy_allocations[strategy_id].target_allocation = fraction
                    self.strategy_allocations[strategy_id].current_allocation = fraction
                    self.strategy_allocations[strategy_id].allocated_capital = (
                        self.base_capital * fraction
                    )

            self.last_rebalance = datetime.now(UTC)
            self._update_portfolio_metrics()
            self.logger.debug("  ✅ Initial allocation complete for %d strategies", len(allocations))

        except Exception as e:
            self.logger.error("Error performing initial allocation: %s", e, exc_info=True)

    def _resolve_strategy_conflicts(self, conflicts: list[StrategyConflict]) -> None:
        """Resolve detected strategy conflicts by pausing the lower-priority strategy.

        Args:
            conflicts: List of StrategyConflict objects to resolve.
        """
        try:
            for conflict in conflicts:
                if conflict.severity in ("high", "critical"):
                    # Pause the second strategy in the conflicting pair
                    if len(conflict.strategy_ids) >= 2:
                        loser_id = conflict.strategy_ids[-1]
                        if loser_id in self.active_strategies:
                            self.logger.warning(
                                "⚡ Pausing strategy %s to resolve %s conflict",
                                loser_id,
                                conflict.conflict_type,
                            )
                            try:
                                self.active_strategies[loser_id].pause()
                                self.paused_strategies.add(loser_id)
                            except Exception as exc:
                                self.logger.error(
                                    "Could not pause %s: %s", loser_id, exc
                                )
                else:
                    self.logger.info(
                        "ℹ️  Low-severity conflict (%s) — no action taken",
                        conflict.conflict_type,
                    )
        except Exception as e:
            self.logger.error("Error resolving strategy conflicts: %s", e, exc_info=True)

    def _adaptive_strategy_management(self) -> None:
        """Adapt the active strategy set to the current market regime.

        Adds strategies that suit the current regime but are not yet active;
        pauses strategies whose type has zero weight in the current regime.
        """
        try:
            regime_weights = self._get_regime_strategy_weights()
            if not regime_weights:
                if self.lean_mode:
                    return
                return

            # C1 (v18): snapshot to avoid RuntimeError if add/remove runs concurrently.
            with self._strategies_lock:
                active_types: dict[str, str] = {
                    strategy_id: alloc.strategy_type
                    for strategy_id, alloc in list(self.strategy_allocations.items())
                }

            # Pause strategies with zero regime weight
            for strategy_id, strategy_type in active_types.items():
                if regime_weights.get(strategy_type, 0) == 0:
                    if strategy_id not in self.paused_strategies:
                        self.logger.info(
                            "🔄 Pausing %s — zero weight in %s regime",
                            strategy_id,
                            self.market_regime.current_regime.value,
                        )
                        try:
                            self.active_strategies[strategy_id].pause()
                            self.paused_strategies.add(strategy_id)
                        except Exception:
                            pass

            # Activate strategies with nonzero weight that are missing
            existing_types = set(active_types.values())
            for strategy_name, weight in regime_weights.items():
                if weight > 0 and strategy_name not in existing_types:
                    if strategy_name in self.available_strategies:
                        strategy_class = self._resolve_registered_strategy_class(strategy_name)
                        if strategy_class is None:
                            self.logger.warning(
                                "Adaptive add skipped unavailable strategy %s",
                                strategy_name,
                            )
                            continue
                        allocation = weight / max(sum(regime_weights.values()), 1.0)
                        config: dict[str, Any] = {
                            "symbol": "SPY",
                            "allocated_capital": self.base_capital * allocation,
                        }
                        try:
                            self.add_strategy(
                                strategy_class,
                                config,
                                initial_allocation=allocation,
                            )
                        except Exception as exc:
                            self.logger.warning(
                                "Adaptive add of %s failed: %s", strategy_name, exc
                            )

        except Exception as e:
            self.logger.error("Error in adaptive strategy management: %s", e, exc_info=True)

    def _monitor_strategy_health(self) -> None:
        """Inspect each active strategy's state and update its health score.

        Strategies in an error state have their health_score zeroed.  Healthy
        strategies receive a score of 1.0.  Paused strategies are scored 0.5.
        """
        try:
            # C1 (v18): snapshot active_strategies under lock before iterating to
            # avoid RuntimeError if add/remove races with this loop.
            with self._strategies_lock:
                _active_snap = list(self.active_strategies.items())

            for strategy_id, strategy in _active_snap:
                state_val = str(getattr(strategy, "state", "")).lower()
                # Use .get() — strategy_allocations could differ from active_snap
                # if a remove races between the snapshot and this line.
                alloc = self.strategy_allocations.get(strategy_id)
                if alloc is None:
                    continue

                if "error" in state_val:
                    alloc.health_score = 0.0
                    self.logger.warning("⚠️  Strategy %s is in error state", strategy_id)
                elif "paus" in state_val:
                    alloc.health_score = 0.5
                elif "active" in state_val or "running" in state_val:
                    alloc.health_score = min(1.0, alloc.health_score + 0.05)
                else:
                    alloc.health_score = max(0.0, alloc.health_score - 0.1)

        except Exception as e:
            self.logger.error("Error monitoring strategy health: %s", e, exc_info=True)

    def _check_risk_limits(self) -> None:
        """Check portfolio-level risk limits and pause all strategies if breached."""
        try:
            # P1-03: use cached self.risk_manager; lazy-resolve once if not yet wired.
            if self.risk_manager is None:
                try:
                    from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
                    self.risk_manager = get_risk_manager()
                except Exception:
                    return
            risk_manager = self.risk_manager
            if risk_manager is None:
                return

            breached = False
            if hasattr(risk_manager, "check_daily_limits"):
                try:
                    breached = not risk_manager.check_daily_limits()
                except Exception:
                    pass

            if breached:
                if getattr(risk_manager, "_data_stale", False):
                    self.logger.warning(
                        "🛑 Market data stale — pausing all strategies"
                    )
                else:
                    self.logger.warning(
                        "🛑 Daily risk limit breached — pausing all strategies"
                    )
                for strategy_id, strategy in list(self.active_strategies.items()):
                    if strategy_id not in self.paused_strategies:
                        try:
                            strategy.pause()
                            self.paused_strategies.add(strategy_id)
                        except Exception:
                            pass

        except Exception as e:
            self.logger.error("Error checking risk limits: %s", e, exc_info=True)

    def _update_performance_attribution(self) -> None:
        """Snapshot current portfolio metrics into the rolling performance history."""
        try:
            snapshot = {
                "timestamp": datetime.now(UTC).isoformat(),
                "total_pnl": self.portfolio_metrics.total_pnl,
                "daily_pnl": self.portfolio_metrics.daily_pnl,
                "active_strategies": len(self.active_strategies),
                "regime": self.market_regime.current_regime.value,
                "strategy_allocations": {
                    # C1 (v18): dict-comp takes a consistent snapshot under GIL; no iteration loop.
                    sid: alloc.current_allocation
                    for sid, alloc in list(self.strategy_allocations.items())
                },
            }
            self.performance_history.append(snapshot)

        except Exception as e:
            self.logger.error("Error updating performance attribution: %s", e, exc_info=True)

    def _generate_final_report(self) -> None:
        """Log a summary report when orchestration stops."""
        try:
            duration = "unknown"
            if self.performance_history:
                first = self.performance_history[0].get("timestamp", "")
                last = self.performance_history[-1].get("timestamp", "")
                duration = f"{first} → {last}"

            self.logger.info(
                "📊 Final Orchestration Report | Strategies: %d | "
                "Rebalances: %d | Duration: %s | Total P&L: %.2f | Daily P&L: %.2f",
                len(self.active_strategies),
                len(self.rebalance_history),
                duration,
                self.portfolio_metrics.total_pnl,
                self.portfolio_metrics.daily_pnl,
            )

        except Exception as e:
            self.logger.error("Error generating final report: %s", e, exc_info=True)

    def _resolve_registered_strategy_class(self, strategy_name: str) -> type | None:
        """Resolve a registered strategy name to a concrete class on first use."""
        strategy_entry = self.available_strategies.get(strategy_name)
        if strategy_entry is None:
            return None

        if inspect.isclass(strategy_entry):
            return strategy_entry

        if isinstance(strategy_entry, tuple) and len(strategy_entry) == 2:
            import_path, symbol = strategy_entry
            strategy_class = _optional_strategy(import_path, symbol)
            if _is_strategy_class(strategy_class):
                self.available_strategies[strategy_name] = strategy_class
                return strategy_class
            self.available_strategies.pop(strategy_name, None)
            return None

        return None

    def _initialize_strategy_registry(self) -> None:
        """Initialize available strategy registry"""
        if SPYDER_MODULES_AVAILABLE:
            candidate_strategies: dict[str, Any] = {}
            candidate_strategy_names = list(_OPTIONAL_STRATEGY_IMPORTS)
            candidate_strategy_names.extend([
                'EvolvedCreditSpread',
                'VIXHedging',
            ])

            if self.lean_mode:
                candidate_strategy_names = [
                    name
                    for name in candidate_strategy_names
                    if name in self.lean_strategy_allowlist
                ]

            for strategy_name in candidate_strategy_names:
                if strategy_name == 'EvolvedCreditSpread':
                    candidate_strategies[strategy_name] = EvolvedCreditSpreadAdapter
                    continue
                if strategy_name == 'VIXHedging':
                    candidate_strategies[strategy_name] = VIXHedgingAdapter
                    continue

                candidate_strategies[strategy_name] = _OPTIONAL_STRATEGY_IMPORTS[strategy_name]

            self.available_strategies = {
                name: cls
                for name, cls in candidate_strategies.items()
                if isinstance(cls, tuple) or _is_strategy_class(cls)
            }
        else:
            self.available_strategies = {}

        self.logger.debug("📋 Registered %s strategy types", len(self.available_strategies))

    def _setup_event_subscriptions(self):
        """Setup event system subscriptions"""
        global EventType
        # If the soft-import fallback left EventType as None, attempt a direct
        # re-import now so subscriptions are not silently skipped.
        if EventType is None:
            try:
                from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType as _ET
                EventType = _ET
            except Exception:
                try:
                    from SpyderA_Core.SpyderA05_EventManager import EventType as _ET
                    EventType = _ET
                except Exception as exc:
                    self.logger.critical(
                        "D31: EventType unavailable — event subscriptions DISABLED. Cause: %s", exc
                    )
                    return
        try:
            # Subscribe to relevant events
            if self.event_manager:
                self.event_manager.subscribe(EventType.MARKET_DATA, self._on_market_data_event)
                self.event_manager.subscribe(EventType.RISK, self._on_risk_event)
                self.event_manager.subscribe(EventType.STRATEGY_SIGNAL, self._on_strategy_signal)
                self.event_manager.subscribe(EventType.RISK_VIOLATION, self._on_risk_alert)
                self.event_manager.subscribe(EventType.POSITION_UPDATED, self._on_position_updated)
                # P1-1: Pause signal emission when the engine is halted or data
                # becomes stale — strategies must not fire into a silenced engine.
                self.event_manager.subscribe(EventType.KILL_SWITCH, self._on_kill_switch)
                self.event_manager.subscribe(EventType.DATA_STALE, self._on_data_stale)
                # B5: Subscribe to DATA_FRESH so a data-stale pause auto-recovers.
                self.event_manager.subscribe(EventType.DATA_FRESH, self._on_data_fresh)
                self.event_manager.subscribe(EventType.ORDER_FILLED, self._on_terminal_order_event)
                self.event_manager.subscribe(EventType.ORDER_CANCELLED, self._on_terminal_order_event)
                self.event_manager.subscribe(EventType.ORDER_EXPIRED, self._on_terminal_order_event)
                self.event_manager.subscribe(EventType.ORDER_REJECTED, self._on_terminal_order_event)
                # Update the subscriptions-active gauge for observability (I-4).
                if _PROM_SUBSCRIPTIONS_ACTIVE is not None:
                    try:
                        _sub_count = len(
                            self.event_manager.handlers.get(EventType.STRATEGY_SIGNAL, [])
                        )
                        _PROM_SUBSCRIPTIONS_ACTIVE.set(_sub_count)
                    except Exception:
                        pass

        except Exception as e:
            self.logger.error("Error setting up event subscriptions: %s", e, exc_info=True)

    def _check_concentration_conflicts(self) -> list[StrategyConflict]:
        """Detect concentration conflicts by strategy-type allocation."""
        conflicts: list[StrategyConflict] = []
        try:
            with self._strategies_lock:
                allocs = list(self.strategy_allocations.values())

            if not allocs:
                return conflicts

            by_type: dict[str, list[StrategyAllocation]] = {}
            for alloc in allocs:
                by_type.setdefault(alloc.strategy_type, []).append(alloc)

            for strategy_type, items in by_type.items():
                concentration = sum(max(0.0, a.current_allocation) for a in items)
                if concentration <= CONCENTRATION_LIMIT:
                    continue

                strategy_ids = [a.strategy_id for a in items]
                severity = "high" if concentration >= (CONCENTRATION_LIMIT + 0.2) else "medium"
                conflicts.append(
                    StrategyConflict(
                        strategy_ids=strategy_ids,
                        conflict_type="concentration",
                        severity=severity,
                        description=(
                            f"Strategy type '{strategy_type}' concentration {concentration:.1%} "
                            f"exceeds limit {CONCENTRATION_LIMIT:.1%}"
                        ),
                        resolution_action="Reduce allocation across concentrated strategies",
                        detected_at=datetime.now(UTC),
                    )
                )
        except Exception as e:
            self.logger.error("Error checking concentration conflicts: %s", e, exc_info=True)

        return conflicts

    def _analyze_strategy_pair_for_conflicts(
        self,
        strategy_id_1: str,
        strategy_1: Any,
        strategy_id_2: str,
        strategy_2: Any,
    ) -> StrategyConflict | None:
        """Detect pairwise conflicts between two active strategies.

        Keeps logic conservative: only raise conflicts for direct position overlap
        or duplicate strategy-type deployment that can cause over-concentration.
        """
        try:
            # Direct overlap: same instrument keys in positions dict.
            pos_1 = getattr(strategy_1, "positions", {}) or {}
            pos_2 = getattr(strategy_2, "positions", {}) or {}
            keys_1 = set(pos_1.keys()) if isinstance(pos_1, dict) else set()
            keys_2 = set(pos_2.keys()) if isinstance(pos_2, dict) else set()
            overlap = sorted(keys_1 & keys_2)
            if overlap:
                overlap_preview = ", ".join(overlap[:3])
                return StrategyConflict(
                    strategy_ids=[strategy_id_1, strategy_id_2],
                    conflict_type="position_overlap",
                    severity="high",
                    description=(
                        f"Strategies share {len(overlap)} position key(s): {overlap_preview}"
                    ),
                    resolution_action="Pause one strategy or net overlapping exposure",
                    detected_at=datetime.now(UTC),
                )

            # Same-type overlap: medium severity concentration warning.
            alloc_1 = self.strategy_allocations.get(strategy_id_1)
            alloc_2 = self.strategy_allocations.get(strategy_id_2)
            type_1 = getattr(alloc_1, "strategy_type", None)
            type_2 = getattr(alloc_2, "strategy_type", None)
            if type_1 and type_2 and type_1 == type_2:
                return StrategyConflict(
                    strategy_ids=[strategy_id_1, strategy_id_2],
                    conflict_type="strategy_type_overlap",
                    severity="medium",
                    description=f"Multiple active strategies share type '{type_1}'",
                    resolution_action="Rebalance allocation across similar strategy types",
                    detected_at=datetime.now(UTC),
                )

        except Exception as e:
            self.logger.error(
                "Error analyzing strategy pair conflict (%s, %s): %s",
                strategy_id_1,
                strategy_id_2,
                e,
                exc_info=True,
            )

        return None

    def subscribe_agent_bus(self, bus: Any) -> None:
        """Subscribe D31 to autonomous-agent topics on the agent message bus.

        Subscribes to:
        - ``market.regime``   — Y01 MarketSenseAgent regime updates (GAP-4)
                - ``signals.validated`` — Y02 StrategyPilotAgent LLM approvals (GAP-2,
                    with paper-mode policy gating for sender-role/topic/action)

        Call this after construction (e.g. from A06) to wire autonomous agent
        outputs into the strategy-selector and monitoring loop.

        Args:
            bus: AgentMessageBus instance (SpyderI06).
        """
        try:
            bus.subscribe(
                subscriber_id="D31_StrategyOrchestrator",
                topics=["market.regime"],
                callback=self._on_agent_regime_update,
                name="StrategyOrchestrator",
            )
            self.logger.info("📡 D31: Subscribed to agent bus 'market.regime' topic (Y01)")
        except Exception as e:
            self.logger.warning("D31: Could not subscribe to 'market.regime': %s", e)
        try:
            bus.subscribe(
                subscriber_id="D31_StrategyOrchestrator_Y02",
                topics=["signals.validated"],
                callback=self._on_y02_validated_signal,
                name="StrategyOrchestrator_Y02PolicyGate",
            )
            self.logger.info("📡 D31: Subscribed to agent bus 'signals.validated' topic (Y02)")
        except Exception as e:
            self.logger.warning("D31: Could not subscribe to 'signals.validated': %s", e)

    def _on_y02_validated_signal(self, message: Any) -> None:
        """Handle Y02 StrategyPilotAgent validated signals from the agent bus.

        Y02 publishes ``signals.validated`` payloads only for *approved* signals.
        We record the strategy type and timestamp so the orchestrator can surface
        patterns where Y02 has stopped approving a particular strategy.

        Phase 2: execution-relevant handoffs are policy-gated in paper mode.

        Args:
            message: AgentOutput or dict with payload containing ``original_signal``
                     and ``validation`` keys.
        """
        try:
            payload, raw_payload = self._extract_agent_message_payload(message)
            self._shadow_validate_agent_handoff(
                topic="signals.validated",
                payload=payload,
                raw_payload=raw_payload,
            )

            sender = ""
            if isinstance(message, dict):
                sender = str(message.get("sender") or "").strip()
            else:
                sender = str(getattr(message, "sender", "") or "").strip()

            allowed, reason_code = self._enforce_execution_handoff_policy(
                topic="signals.validated",
                sender=sender,
                payload=payload,
                raw_payload=raw_payload,
            )
            if not allowed:
                self._agent_handoff_enforcement_counts["blocked"] += 1
                self.logger.warning(
                    "D31 policy blocked signals.validated sender=%s reason=%s",
                    sender,
                    reason_code,
                )
                self._record_signal_drop("agent_handoff_policy", reason_code, signal=payload)
                return
            self._agent_handoff_enforcement_counts["allowed"] += 1

            original_signal = payload.get("original_signal") or {}
            validation = payload.get("validation") or {}
            approved = bool(validation.get("approved", True))  # only published when True

            strategy_type = str(
                original_signal.get("strategy_type")
                or original_signal.get("strategy")
                or original_signal.get("type")
                or "unknown"
            )
            now = datetime.now(UTC)

            if approved:
                self._y02_advisory[strategy_type] = {
                    "last_approved": now,
                    "regime_alignment": validation.get("regime_alignment", ""),
                    "assessment": validation.get("llm_assessment", "")[:120],
                }
                self.logger.debug(
                    "✅ Y02 approved signal from strategy '%s' (regime_alignment=%s)",
                    strategy_type, validation.get("regime_alignment", ""),
                )
            else:
                self.logger.info(
                    "⚠️  Y02 did not approve signal from strategy '%s'", strategy_type
                )
        except Exception as e:
            self.logger.debug("D31: _on_y02_validated_signal error: %s", e)

    def _extract_agent_message_payload(
        self,
        message: Any,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Normalize agent-bus message shapes to payload dict while preserving wrapper."""
        raw_payload: dict[str, Any] | None = None

        if isinstance(message, dict):
            candidate = message.get("payload")
            if candidate is None:
                candidate = message.get("data")
            if candidate is None:
                candidate = message
            if isinstance(candidate, dict):
                raw_payload = candidate
        else:
            candidate = getattr(message, "payload", None)
            if candidate is None:
                candidate = getattr(message, "data", None)
            if isinstance(candidate, dict):
                raw_payload = candidate

        if not isinstance(raw_payload, dict):
            return {}, None

        nested_data = raw_payload.get("data")
        if isinstance(nested_data, dict):
            return nested_data, raw_payload

        return raw_payload, raw_payload

    def _shadow_validate_agent_handoff(
        self,
        topic: str,
        payload: dict[str, Any],
        raw_payload: dict[str, Any] | None = None,
    ) -> None:
        """Advisory-only handoff validation for Phase 1 shadow mode."""
        if not self._agent_handoff_shadow_validation_enabled:
            return

        if not _D31_AGENT_HANDOFF_VALIDATION_AVAILABLE:
            self._agent_handoff_shadow_validation_counts["validator_unavailable"] += 1
            return

        envelope, schema_name = _extract_agent_handoff_envelope(payload)
        if envelope is None and isinstance(raw_payload, dict) and raw_payload is not payload:
            envelope, schema_name = _extract_agent_handoff_envelope(raw_payload)

        if envelope is None:
            self._agent_handoff_shadow_validation_counts["missing"] += 1
            self.logger.warning(
                "D31 advisory: missing agent handoff envelope on topic=%s",
                topic,
            )
            return

        valid, error = _validate_agent_handoff_envelope(envelope, schema_name)
        if valid:
            self._agent_handoff_shadow_validation_counts["valid"] += 1
            return

        self._agent_handoff_shadow_validation_counts["invalid"] += 1
        self.logger.warning(
            "D31 advisory: invalid agent handoff envelope on topic=%s schema=%s error=%s",
            topic,
            schema_name,
            error,
        )

    def _get_agent_handoff_policy(self) -> dict[str, Any]:
        """Load and cache Phase 2 agent handoff policy."""
        if self._agent_handoff_policy is not None:
            return self._agent_handoff_policy

        policy: dict[str, Any] = {}

        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg = get_config_manager()
            candidate = cfg.get("autonomous_readiness.agent_handoff_policy", {})
            if isinstance(candidate, dict):
                policy = candidate
        except Exception:
            policy = {}

        if not policy:
            policy_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "agent_handoff_policy.json",
            )
            try:
                with open(policy_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    policy = loaded
            except Exception:
                policy = {}

        self._agent_handoff_policy = policy if isinstance(policy, dict) else {}
        return self._agent_handoff_policy

    def _agent_handoff_default_action(self, enforcement: dict[str, Any]) -> str:
        """Resolve policy fallback action for current run mode."""
        if self._is_live_mode_for_agent_handoff_policy():
            return str(enforcement.get("default_action_live", "allow")).strip().lower()
        return str(enforcement.get("default_action_paper", "deny")).strip().lower()

    def _agent_handoff_policy_enabled(self, enforcement: dict[str, Any]) -> bool:
        """Check if Phase 2 policy is enabled for the current run mode."""
        if self._is_live_mode_for_agent_handoff_policy():
            return bool(enforcement.get("live_mode", False))
        return bool(enforcement.get("paper_mode", True))

    def _is_live_mode_for_agent_handoff_policy(self) -> bool:
        """Resolve live/paper mode specifically for handoff policy enforcement."""
        candidates = (
            self._audit_run_mode,
            os.environ.get("SPYDER_TRADING_MODE"),
            os.environ.get("TRADING_MODE"),
        )
        for value in candidates:
            if value is None:
                continue
            text = str(value).strip().lower()
            if text in {"live", "production", "prod"}:
                return True
            if text in {"paper", "sandbox", "sim", "simulation", "development", "dev", "test", "testing"}:
                return False

        return self._is_live_mode()

    @staticmethod
    def _is_execution_relevant_handoff_topic(topic: str) -> bool:
        """Restrict D31 hard-enforcement to execution-relevant handoffs."""
        return topic == "signals.validated" or topic.startswith("execution.")

    @staticmethod
    def _match_policy_patterns(value: str, patterns: Any) -> bool:
        """Match wildcard patterns from policy lists."""
        if not value or not isinstance(patterns, list):
            return False
        return any(isinstance(pattern, str) and pattern and fnmatchcase(value, pattern) for pattern in patterns)

    def _is_agent_sender_in_policy_scope(self, sender: str, enforcement: dict[str, Any]) -> bool:
        """Apply sender-scoped enforcement to avoid blocking non-agent publishers."""
        patterns = enforcement.get("enforce_sender_patterns")
        if not isinstance(patterns, list) or not patterns:
            patterns = ["Y[0-9][0-9]_*", "X[0-9][0-9]_*"]
        return self._match_policy_patterns(sender, patterns)

    def _resolve_agent_sender_role(self, sender: str, role_bindings: dict[str, Any]) -> str | None:
        """Resolve sender role using exact bindings before wildcard bindings."""
        if not sender or not isinstance(role_bindings, dict):
            return None

        exact = role_bindings.get(sender)
        if isinstance(exact, str) and exact:
            return exact

        for pattern, role in role_bindings.items():
            if not isinstance(pattern, str) or not isinstance(role, str):
                continue
            if fnmatchcase(sender, pattern):
                return role

        return None

    def _extract_agent_handoff_action(
        self,
        payload: dict[str, Any],
        raw_payload: dict[str, Any] | None,
    ) -> str | None:
        """Extract normalized handoff action for policy checks."""
        for candidate in (payload, raw_payload):
            if not isinstance(candidate, dict):
                continue

            envelope, _ = _extract_agent_handoff_envelope(candidate)
            if isinstance(envelope, dict):
                handoff_type = envelope.get("handoff_type")
                if isinstance(handoff_type, str) and handoff_type:
                    return handoff_type.strip().lower()

            for key in ("output_type", "action", "intent"):
                value = candidate.get(key)
                if isinstance(value, str) and value:
                    return value.strip().lower()

        return None

    @staticmethod
    def _policy_decision_from_default(reason_code: str, default_action: str) -> tuple[bool, str]:
        """Apply allow/deny fallback policy when specific checks are inconclusive."""
        if default_action == "allow":
            return True, f"{reason_code}_allowed_by_default"
        return False, reason_code

    def _enforce_execution_handoff_policy(
        self,
        topic: str,
        sender: str,
        payload: dict[str, Any],
        raw_payload: dict[str, Any] | None,
    ) -> tuple[bool, str]:
        """Hard-enforce execution-relevant agent handoff policy for Phase 2."""
        if not self._is_execution_relevant_handoff_topic(topic):
            self._agent_handoff_enforcement_counts["skipped"] += 1
            return True, "topic_not_execution_relevant"

        policy = self._get_agent_handoff_policy()
        enforcement = policy.get("enforcement", {}) if isinstance(policy, dict) else {}
        if not isinstance(enforcement, dict):
            self._agent_handoff_enforcement_counts["skipped"] += 1
            return True, "policy_enforcement_unavailable"

        default_action = self._agent_handoff_default_action(enforcement)
        if not self._agent_handoff_policy_enabled(enforcement):
            self._agent_handoff_enforcement_counts["skipped"] += 1
            return True, "policy_disabled"

        if not self._is_agent_sender_in_policy_scope(sender, enforcement):
            self._agent_handoff_enforcement_counts["skipped"] += 1
            return True, "sender_out_of_scope"

        enforce_topics = enforcement.get("enforce_topics")
        if not isinstance(enforce_topics, list):
            enforce_topics = []
        enforce_prefixes = enforcement.get("enforce_topic_prefixes")
        if not isinstance(enforce_prefixes, list):
            enforce_prefixes = []
        in_topic_scope = topic in enforce_topics or any(
            isinstance(prefix, str) and topic.startswith(prefix) for prefix in enforce_prefixes
        )
        if not in_topic_scope:
            self._agent_handoff_enforcement_counts["skipped"] += 1
            return True, "topic_out_of_scope"

        role_bindings = policy.get("role_bindings", {}) if isinstance(policy, dict) else {}
        role = self._resolve_agent_sender_role(sender, role_bindings)
        if not role:
            return self._policy_decision_from_default("sender_role_unbound", default_action)

        role_permissions = policy.get("role_permissions", {}) if isinstance(policy, dict) else {}
        permission = role_permissions.get(role) if isinstance(role_permissions, dict) else None
        if not isinstance(permission, dict):
            return self._policy_decision_from_default("role_not_configured", default_action)

        if self._match_policy_patterns(topic, permission.get("deny_topics", [])):
            return False, "topic_explicitly_denied"

        allow_topics = permission.get("allow_topics", [])
        if isinstance(allow_topics, list) and allow_topics and not self._match_policy_patterns(topic, allow_topics):
            return self._policy_decision_from_default("topic_not_allowed", default_action)

        action = self._extract_agent_handoff_action(payload, raw_payload)
        if not action and topic == "signals.validated":
            action = "signal"

        if action and self._match_policy_patterns(action, permission.get("deny_actions", [])):
            return False, "action_explicitly_denied"

        allow_actions = permission.get("allow_actions", [])
        if isinstance(allow_actions, list) and allow_actions:
            if not action:
                return self._policy_decision_from_default("action_missing", default_action)
            if not self._match_policy_patterns(action, allow_actions):
                return self._policy_decision_from_default("action_not_allowed", default_action)

        return True, "allowed"

    def _on_agent_regime_update(self, message: Any) -> None:
        """Handle regime updates from Y01 MarketSenseAgent via the agent bus.

        Y01 publishes ``{regime: str, confidence: float}`` under the
        ``market.regime`` topic.  The bus wrapper envelopes this as
        ``{data: <payload>, confidence: float}``.
        """
        try:
            data, raw_payload = self._extract_agent_message_payload(message)
            self._shadow_validate_agent_handoff(
                topic="market.regime",
                payload=data,
                raw_payload=raw_payload,
            )

            regime_str = str(data.get("regime", "")).strip()
            confidence = float(data.get("confidence", 0.0))

            if not regime_str or regime_str == "unknown":
                return

            # Map regime string → D31 MarketRegime enum
            try:
                new_regime = MarketRegime(regime_str)
            except ValueError:
                # Fuzzy fallback: Y01 may use strings like "bull_quiet" / "bull_volatile"
                vix = self.market_regime.vix_level
                is_high_vol = vix > VIX_REGIME_THRESHOLDS["high"]
                vol_suffix = "high_vol" if is_high_vol else "low_vol"
                if "bull" in regime_str:
                    new_regime = MarketRegime(f"bull_{vol_suffix}")
                elif "bear" in regime_str:
                    new_regime = MarketRegime(f"bear_{vol_suffix}")
                elif "crisis" in regime_str:
                    new_regime = MarketRegime.CRISIS
                elif "recov" in regime_str:
                    new_regime = MarketRegime.RECOVERY
                else:
                    new_regime = MarketRegime(f"sideways_{vol_suffix}")

            if new_regime != self.market_regime.current_regime:
                self.logger.info(
                    "📡 D31 regime updated by Y01: %s → %s (conf=%.2f)",
                    self.market_regime.current_regime.value, new_regime.value, confidence,
                )
                self.market_regime.current_regime = new_regime
                self.market_regime.regime_confidence = confidence
                self.market_regime.last_regime_change = datetime.now(UTC)
                self.market_regime.regime_duration_days = 0

            # Re-run strategy selection for the updated regime
            self._configure_strategies_for_regime()

        except Exception as e:
            self.logger.warning("D31: Agent regime update failed: %s", e)

    def _on_kill_switch(self, event) -> None:  # type: ignore[override]
        """B5/P1-1: Pause signal emission on KILL_SWITCH. Sticky — restart required."""
        reason = (getattr(event, "data", None) or {}).get("reason", "KILL_SWITCH")
        self._paused_kill = True
        self.logger.critical(
            "⛔ StrategyOrchestrator HALTED by KILL_SWITCH (%s) — restart required to resume.", reason  # noqa: E501
        )

    def _on_data_stale(self, event) -> None:  # type: ignore[override]
        """B5/P1-1: Pause signal emission when market data becomes stale."""
        reason = (getattr(event, "data", None) or {}).get("reason", "DATA_STALE")
        self._paused_stale = True
        self.logger.warning(
            "⏸ StrategyOrchestrator PAUSED by DATA_STALE (%s) — will resume on DATA_FRESH.", reason
        )

    def _on_data_fresh(self, event) -> None:  # type: ignore[override]
        """B5: Clear the stale-data pause when the data feed recovers.

        A KILL_SWITCH pause is NOT cleared here — it requires a restart.
        """
        if self._paused_stale:
            self._paused_stale = False
            symbol = (getattr(event, "data", None) or {}).get("symbol", "?")
            self.logger.info(
                "▶ StrategyOrchestrator RESUMED — DATA_FRESH received for %s.", symbol
            )

    def _on_market_data_event(self, event: Event):
        """Handle market data events and fan out to all active strategies."""
        # B5/P1-1: Do not feed strategies while halted (kill or stale).
        if self._paused_kill or self._paused_stale:
            return
        data = event.data
        if isinstance(data, dict):
            if not isinstance(self.market_data_cache, dict):
                self.market_data_cache = {}
            symbol = data.get("symbol")
            tick = data.get("tick")
            if isinstance(symbol, str):
                row: dict[str, Any] | None = None

                if isinstance(tick, dict):
                    row = dict(tick)
                else:
                    # Some producers publish flat payloads like
                    # {"symbol":"SPY","price":...} instead of {"tick": {...}}.
                    # Normalize that shape into a tick row so regime cache can warm.
                    candidate = {
                        key: data.get(key)
                        for key in ("open", "high", "low", "close", "price", "last", "bid", "ask", "volume")
                        if key in data
                    }
                    if candidate:
                        row = candidate

                if isinstance(row, dict):
                    row.setdefault("symbol", symbol)
                    bucket = self.market_data_cache.get(symbol)
                    if not isinstance(bucket, deque):
                        bucket = deque(maxlen=_MARKET_TICK_BUFFER)
                        self.market_data_cache[symbol] = bucket
                    bucket.append(row)
                else:
                    # Symbol-tagged non-tick payloads (for example dark-pool
                    # block-trade summaries) must not mutate per-symbol tick
                    # buckets, but we still preserve their top-level metadata.
                    for key, value in data.items():
                        if key in {"symbol", "tick"}:
                            continue
                        self.market_data_cache[key] = value
            else:
                # Non-tick payloads (e.g. C12 dark-pool block_trade events,
                # event_clock_state). Merge top-level keys but leave per-symbol
                # buckets untouched — and skip {'symbol', 'tick'} so a malformed
                # tick payload can't corrupt the regime cache.
                for key, value in data.items():
                    if key in {"symbol", "tick"}:
                        continue
                    self.market_data_cache[key] = value
        else:
            # v27 SPEC-16: do NOT replace the entire cache with a non-dict
            # payload — that would wipe every per-symbol bucket and re-trigger
            # the cold-start CRISIS regime. Drop the malformed event with a
            # warning instead.
            self.logger.warning(
                "D31 _on_market_data_event: ignoring non-dict event payload "
                "(type=%s) — would have corrupted per-symbol cache",
                type(data).__name__,
            )
            return
        self.last_market_update = datetime.now(UTC)
        try:
            self._emit_pin_risk_window_events()
        except Exception as _pin_exc:
            self.logger.debug("D31 pin-risk window monitor failed: %s", _pin_exc)

        # v27 SPEC-11: regime is a hot-path concern. Recompute regime up to
        # once every REGIME_UPDATE_THROTTLE_SECONDS (15s) per market-data event
        # instead of waiting for the 30-min orchestration loop. Any regime
        # transition detected here propagates immediately to subsequent
        # strategy gating.
        try:
            now_ts = self.last_market_update
            last_ts = getattr(self, "_last_regime_update_ts", None)
            if last_ts is None or (now_ts - last_ts).total_seconds() >= 15:
                self._update_market_regime()
                self._last_regime_update_ts = now_ts
        except Exception as _regime_exc:
            self.logger.debug("D31 per-tick regime update failed: %s", _regime_exc)

        # v28 COLD-START RECOVERY: if no strategies have been registered yet
        # (e.g. startup CRISIS fail-closed cleared by fresh market data) and
        # the current regime is now tradeable, trigger strategy configuration
        # immediately rather than waiting for the next 30-min orchestration cycle.
        if not self.active_strategies:
            _cur_regime = self.market_regime.current_regime
            _non_tradeable = {MarketRegime.CRISIS, MarketRegime.EVENT_TRANSITION}
            if _cur_regime not in _non_tradeable:
                try:
                    before_count = len(self.active_strategies)
                    if self._initial_strategy_activation_pending:
                        self._run_initial_strategy_activation_if_pending()
                    else:
                        self._configure_strategies_for_regime()
                    if len(self.active_strategies) > before_count:
                        self.logger.info(
                            "D31 warm-up: bootstrapped strategies for regime %s",
                            _cur_regime.value,
                        )
                except Exception as _cfg_exc:
                    self.logger.debug(
                        "D31 warm-up strategy configure failed: %s", _cfg_exc
                    )

        # Feed every active strategy so it can generate signals autonomously.
        if not self.active_strategies:
            return

        market_df = None
        try:
            import pandas as pd
            data = event.data
            if isinstance(data, pd.DataFrame):
                market_df = data
            elif isinstance(data, dict) and data:
                # C01 emits {'symbol': str, 'tick': dict} where tick contains OHLCV
                # fields. Expand the tick payload so strategies receive proper columns
                # (open, high, low, close, volume, bid, ask, last, symbol) instead of
                # a DataFrame with literal columns ['symbol', 'tick'].
                tick_payload = data.get("tick")
                if isinstance(tick_payload, dict):
                    row = dict(tick_payload)
                    _sym = data.get("symbol", row.get("symbol", ""))
                    row.setdefault("symbol", _sym)
                    # Pass the full accumulated tick history so strategies can compute
                    # rolling indicators (SMA-20, SMA-50, vol percentile, etc.).
                    # The cache was already updated with this tick above.
                    _cache = self.market_data_cache if isinstance(self.market_data_cache, dict) else {}
                    _bucket = _cache.get(_sym) if _sym else None
                    if isinstance(_bucket, deque) and len(_bucket) > 1:
                        market_df = pd.DataFrame(list(_bucket))
                        market_df = self._enrich_market_df_with_options_metrics(market_df)
                    else:
                        market_df = pd.DataFrame([row])
                        market_df = self._enrich_market_df_with_options_metrics(market_df)
                else:
                    market_df = pd.DataFrame([data])
                    market_df = self._enrich_market_df_with_options_metrics(market_df)
        except Exception:
            pass

        if market_df is None or (hasattr(market_df, "empty") and market_df.empty):
            return

        for strategy_id, strategy in list(self.active_strategies.items()):
            if self._strategy_uses_runtime_cadence(strategy):
                self._seed_runtime_cadence_for_strategy(strategy_id, strategy)
                continue
            try:
                strategy.process_market_data(market_df)
            except Exception as exc:
                self.logger.error(
                    "Error feeding market data to strategy %s: %s", strategy_id, exc, exc_info=True
                )

    def _on_risk_event(self, event: Event) -> None:
        """Ingest scheduler risk feeds needed by regime and entry gates."""
        try:
            payload = getattr(event, "data", None)
            if not isinstance(payload, dict):
                return

            if str(payload.get("type", "")).strip().lower() != "event_clock_state":
                return

            envelope = payload.get("payload")
            if not isinstance(envelope, dict):
                return

            state_payload = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
            if not isinstance(self.market_data_cache, dict):
                self.market_data_cache = {}
            self.market_data_cache["event_clock_state"] = state_payload
        except Exception as exc:
            self.logger.debug("D31: failed to ingest event_clock_state: %s", exc)

    def _on_position_updated(self, event: Event) -> None:
        """Release in-flight entry reservations once position truth advances."""
        data = getattr(event, "data", None) or {}
        if not isinstance(data, dict):
            return

        symbol = str(data.get("symbol") or "")
        strategy_id = str(data.get("strategy_id") or data.get("strategy") or "")
        status = str(data.get("status") or "").strip().upper()
        reason = str(data.get("reason") or "").strip().lower()
        if symbol:
            self._clear_pending_entry_reservations_for_symbol(symbol)
            self._clear_pending_exit_reservations_for_symbol(symbol)
            underlying_symbol = self._extract_option_underlying(symbol)
            if underlying_symbol and underlying_symbol != symbol:
                self._clear_pending_entry_reservations_for_symbol(underlying_symbol)
                self._clear_pending_exit_reservations_for_symbol(underlying_symbol)

        if (
            symbol
            and strategy_id
            and status in {"CLOSED", "CLOSE_REQUESTED"}
            and reason == "manual_close_dashboard"
        ):
            self._record_manual_close_reentry_embargo(symbol, strategy_id)

    def _on_terminal_order_event(self, event: Event) -> None:
        """Release in-flight entry reservations when an order reaches terminal state."""
        data = getattr(event, "data", None) or {}
        if not isinstance(data, dict):
            return

        event_type = getattr(event, "event_type", None)
        event_type_value = str(getattr(event_type, "value", event_type) or "").strip().lower()
        should_clear_exit_reservations = event_type_value in {
            "order_cancelled",
            "order_expired",
            "order_rejected",
        }

        symbol = str(data.get("symbol") or "")
        raw = data.get("raw") if isinstance(data.get("raw"), dict) else {}
        if not symbol and raw:
            symbol = str(raw.get("symbol") or "")
        if symbol:
            self._clear_pending_entry_reservations_for_symbol(symbol)
            if should_clear_exit_reservations:
                self._clear_pending_exit_reservations_for_symbol(symbol)
            underlying_symbol = self._extract_option_underlying(symbol)
            if underlying_symbol and underlying_symbol != symbol:
                self._clear_pending_entry_reservations_for_symbol(underlying_symbol)
                if should_clear_exit_reservations:
                    self._clear_pending_exit_reservations_for_symbol(underlying_symbol)

    def _on_strategy_signal(self, event: Event):
        """Handle strategy signal events.

        Routes every strategy-generated signal through the E01 RiskManager
        validate_signal() gate before it can be acted upon. If validation
        fails, the signal is dropped and a risk alert event is emitted.
        """
        self._signal_flow_counts["seen"] += 1

        # B5/P1-1: Drop signals while paused (kill-switch sticky; data-stale transient).
        if self._paused_kill or self._paused_stale:
            self._record_signal_drop("pre_risk", "orchestrator_paused")
            return

        signal = getattr(event, "data", None)
        if not signal:
            self._record_signal_drop("pre_risk", "empty_event")
            return

        # P1-13: deterministic dry-run self-test path. When a synthetic signal
        # carries dry_run=True, acknowledge it by emitting ORDER_REJECTED with
        # reason="dry_run" and return before any order routing.
        if isinstance(signal, dict) and bool(signal.get("dry_run", False)):
            try:
                self.event_manager.emit(
                    EventType.ORDER_REJECTED,
                    {
                        "order_id": str(signal.get("order_id") or ""),
                        "reason": "dry_run",
                        "result": {"status": "rejected", "reason": "dry_run"},
                        "signal": signal,
                    },
                    source="StrategyOrchestrator",
                )
            except Exception as exc:
                self.logger.error("Failed to emit dry-run ORDER_REJECTED: %s", exc, exc_info=True)
            return

        if isinstance(signal, dict):
            gate_ok, gate_stage, gate_reason, gate_detail = self._evaluate_pre_risk_signal_gates(signal)
            if not gate_ok:
                self._record_signal_drop(
                    gate_stage,
                    gate_reason,
                    signal=signal,
                    detail=gate_detail,
                )
                if gate_reason == "session_window_gate":
                    # outside_primary_window / weekend_block are expected after-hours
                    # states and are already captured in the drop audit; only log
                    # at WARNING for intraday cutoff cases (zero_dte, broker_cutoff)
                    # that operators may want to investigate during live sessions.
                    _after_hours_detail = gate_detail in (
                        "session_window:outside_primary_window",
                        "session_window:weekend_block",
                    )
                    if _after_hours_detail:
                        self.logger.debug(
                            "Strategy signal skipped — outside trading session: %s",
                            gate_detail,
                        )
                    else:
                        self.logger.warning(
                            "Strategy signal rejected by session window gate: %s",
                            gate_detail,
                        )
                    self._emit_event_safe(
                        EventType.RISK,
                        {
                            "type": "session_window_gate_rejected",
                            "severity": "warning",
                            "reason": gate_detail,
                            "signal": signal,
                        },
                        severity="warning",
                    )
                    return

                if gate_reason == "entry_trust_gate":
                    pivot_context = self._format_pivot_log_context(
                        self._extract_pivot_signal_payload(signal)
                    )
                    self.logger.warning(
                        "Strategy signal rejected by entry trust gate: %s | %s",
                        gate_detail,
                        pivot_context,
                    )
                    if self.event_manager:
                        try:
                            risk_alert_type = (
                                getattr(EventType, "RISK_ALERT", None)
                                or getattr(EventType, "RISK", None)
                                or "RISK_ALERT"
                            )
                            self.event_manager.publish(
                                risk_alert_type,
                                {
                                    "severity": "warning",
                                    "reason": "entry_trust_gate_rejected",
                                    "message": gate_detail,
                                    "signal": signal,
                                },
                            )
                        except Exception:
                            pass
                    return

        pivot_context = self._format_pivot_log_context(
            self._extract_pivot_signal_payload(signal)
        )

        # P1-03: risk_manager is cached on self; lazy-resolve once if not yet wired.
        if self.risk_manager is None:
            try:
                from Spyder.SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
                self.risk_manager = get_risk_manager()
            except Exception:
                pass
        risk_manager = self.risk_manager
        if risk_manager is None or not hasattr(risk_manager, "validate_signal"):
            self._record_signal_drop("pre_risk", "no_risk_gate", signal=signal)
            return  # No risk gate wired — leave signal untouched

        # Build a typed RiskValidationRequest so E01's boundary check passes.
        # Map the signal dict to the canonical boundary type before crossing the
        # D↔E series boundary (audit finding P0-B).
        try:
            from Spyder.SpyderE_Risk.SpyderE00_RiskProtocol import (
                RiskValidationRequest as _RVR,
                BoundarySignalType as _BST,
            )
        except ImportError:
            try:
                from SpyderE_Risk.SpyderE00_RiskProtocol import (  # type: ignore[no-redef]
                    RiskValidationRequest as _RVR,
                    BoundarySignalType as _BST,
                )
            except ImportError:
                self.logger.error("D31: RiskValidationRequest unavailable — signal dropped")
                self._record_signal_drop("pre_risk", "rvr_import_failed", signal=signal)
                return

        _ACTION_MAP: dict[str, Any] = {
            "buy": _BST.BUY, "buy_to_open": _BST.BUY, "buy_to_close": _BST.BUY,
            "sell": _BST.SELL, "sell_to_open": _BST.SELL, "sell_to_close": _BST.SELL,
            "close": _BST.CLOSE, "adjust": _BST.ADJUST, "hold": _BST.HOLD,
        }
        _sig: dict = signal if isinstance(signal, dict) else (signal.to_dict() if hasattr(signal, "to_dict") else {})  # noqa: E501
        _action_raw = str(_sig.get("action", _sig.get("side", "buy"))).lower()
        _signal_type = _ACTION_MAP.get(_action_raw, _BST.BUY)
        _known = {"signal_id", "strategy_id", "symbol", "action", "side",
                  "quantity", "price", "limit_price", "entry_price",
                  "stop_loss", "take_profit", "confidence"}
        try:
            risk_request = _RVR(
                symbol=str(_sig.get("symbol", "")),
                quantity=int(float(_sig.get("quantity", 0) or 0)),
                signal_type=_signal_type,
                strategy_id=str(_sig.get("strategy_id", "")),
                entry_price=float(_sig.get("price") or _sig.get("limit_price") or _sig.get("entry_price") or 0.0),  # noqa: E501
                stop_loss=float(_sig.get("stop_loss") or 0.0),
                take_profit=float(_sig.get("take_profit") or 0.0),
                confidence=float(_sig.get("confidence") or 0.0),
                metadata={k: v for k, v in _sig.items() if k not in _known},
            )
        except Exception as exc:
            self.logger.error("D31: Failed to build RiskValidationRequest: %s", exc, exc_info=True)
            self._record_signal_drop("pre_risk", "rvr_build_failed", signal=signal)
            return

        risk_request.metadata.update(self._build_overlay_gate_metadata(_sig))

        overlay_slot_requested = bool(risk_request.metadata.get("overlay_slot_requested", False))
        if overlay_slot_requested:
            if not hasattr(risk_manager, "validate_overlay_slot"):
                self.logger.warning(
                    "Strategy signal rejected by overlay gate: reason=%s | %s | signal=%s",
                    "unavailable",
                    pivot_context,
                    signal,
                )
                self._record_signal_drop(
                    "pre_risk",
                    "overlay_gate:unavailable",
                    signal=signal,
                    detail="validate_overlay_slot unavailable",
                )
                return

            try:
                overlay_result = risk_manager.validate_overlay_slot(risk_request)
            except Exception as exc:
                self.logger.error("Risk validate_overlay_slot raised: %s", exc, exc_info=True)
                self._record_signal_drop(
                    "pre_risk",
                    "overlay_gate:exception",
                    signal=signal,
                    detail=str(exc),
                )
                return

            overlay_approved = True
            overlay_reason = ""
            overlay_values: dict[str, Any] = {}
            if isinstance(overlay_result, dict):
                overlay_approved = bool(
                    overlay_result.get("allow", overlay_result.get("approved", overlay_result.get("valid", True)))
                )
                overlay_reason = str(
                    overlay_result.get("reason_code") or overlay_result.get("reason") or "unknown"
                )
                if isinstance(overlay_result.get("computed_values"), dict):
                    overlay_values = dict(overlay_result.get("computed_values") or {})
            elif hasattr(overlay_result, "allow"):
                overlay_approved = bool(overlay_result.allow)
                overlay_reason_code = overlay_result.reason_code if hasattr(overlay_result, "reason_code") else ""
                overlay_reason = str(overlay_reason_code or "unknown")
                overlay_computed_values = (
                    overlay_result.computed_values if hasattr(overlay_result, "computed_values") else None
                )
                if isinstance(overlay_computed_values, dict):
                    overlay_values = dict(overlay_computed_values or {})
            elif isinstance(overlay_result, bool):
                overlay_approved = overlay_result
                overlay_reason = "unknown" if not overlay_result else "admitted"

            if not overlay_approved:
                strategy_id = signal.get("strategy_id", "unknown") if isinstance(signal, dict) else "unknown"
                overlay_detail = overlay_reason
                missing_inputs = overlay_values.get("missing_inputs")
                if isinstance(missing_inputs, list) and missing_inputs:
                    overlay_detail = "missing_inputs=" + ",".join(str(item) for item in missing_inputs)
                self.logger.warning(
                    "Strategy signal rejected by overlay gate: reason=%s | %s | signal=%s",
                    overlay_reason,
                    pivot_context,
                    signal,
                )
                _record_risk_rejection_metric(
                    strategy=strategy_id,
                    rejection_reason=f"overlay_gate:{overlay_reason}",
                )
                try:
                    risk_alert_type = (
                        getattr(EventType, "RISK_ALERT", None)
                        or getattr(EventType, "RISK", None)
                        or "RISK_ALERT"
                    )
                    self.event_manager.publish(
                        risk_alert_type,
                        {
                            "severity": "warning",
                            "reason": "validate_overlay_slot_rejected",
                            "overlay_reason": overlay_reason,
                            "signal": signal,
                        },
                    )
                except Exception:
                    pass
                self._record_signal_drop(
                    "pre_risk",
                    f"overlay_gate:{overlay_reason}",
                    signal=signal,
                    detail=overlay_detail,
                )
                return

        try:
            result = risk_manager.validate_signal(risk_request)
        except Exception as exc:
            self.logger.error("Risk validate_signal raised: %s", exc, exc_info=True)
            return

        approved = True
        if isinstance(result, dict):
            approved = bool(result.get("approved", result.get("valid", True)))
        elif hasattr(result, "approved"):
            approved = bool(result.approved)
        elif isinstance(result, bool):
            approved = result

        if not approved:
            strategy_id = signal.get("strategy_id", "unknown") if isinstance(signal, dict) else "unknown"  # noqa: E501
            if isinstance(result, dict):
                reason = result.get("rejection_reason") or result.get("reason", "unknown")
            else:
                reason = getattr(result, "rejection_reason", "unknown") or "unknown"
            self.logger.warning(
                "Strategy signal rejected by risk gate: reason=%s | %s | signal=%s",
                reason,
                pivot_context,
                signal,
            )
            _record_risk_rejection_metric(strategy=strategy_id, rejection_reason=reason)
            try:
                risk_alert_type = (
                    getattr(EventType, "RISK_ALERT", None)
                    or getattr(EventType, "RISK", None)
                    or "RISK_ALERT"
                )
                self.event_manager.publish(
                    risk_alert_type,
                    {"severity": "warning", "reason": "validate_signal_rejected", "signal": signal},
                )
            except Exception:
                pass
            self._record_signal_drop(
                "pre_risk",
                f"risk_gate:{reason}",
                signal=signal,
                detail=getattr(result, "message", "") or reason,
            )

        if approved and isinstance(signal, dict):
            strategy_id = signal.get("strategy_id", signal.get("strategy_name", ""))
            side = signal.get("action", signal.get("side", "buy"))
            symbol = str(signal.get("symbol") or "")
            if self._is_entry_action(side):
                embargo_remaining_s = self._get_manual_close_reentry_embargo_remaining(
                    symbol,
                    strategy_id,
                )
                if embargo_remaining_s is not None:
                    embargo_remaining = max(1, int(math.ceil(embargo_remaining_s)))
                    embargo_detail = (
                        f"symbol={symbol};strategy={strategy_id};"
                        "embargo_source=manual_close_dashboard;"
                        f"embargo_remaining_s={embargo_remaining}"
                    )
                    self.logger.warning(
                        "Strategy signal blocked — manual close reentry embargo active: symbol=%s strategy=%s embargo_remaining_s=%s | %s",
                        symbol,
                        strategy_id,
                        embargo_remaining,
                        pivot_context,
                    )
                    self._record_signal_drop(
                        "pre_dispatch",
                        "manual_close_reentry_embargo",
                        signal=signal,
                        detail=embargo_detail,
                    )
                    self._record_signal_dispatch_outcome_safe(
                        "dispatch_rejected",
                        signal=signal,
                        detail=embargo_detail,
                    )
                    return
            duplicate_source = self._get_duplicate_open_position_source(
                symbol,
                strategy_id,
                side,
            )
            if duplicate_source is not None:
                duplicate_detail = (
                    f"symbol={symbol};strategy={strategy_id};duplicate_source={duplicate_source}"
                )
                self._log_duplicate_entry_warning_if_due(
                    symbol,
                    strategy_id,
                    pivot_context,
                    duplicate_source=duplicate_source,
                    stage="pre_dispatch",
                )
                self._record_signal_drop(
                    "pre_dispatch",
                    "duplicate_open_position",
                    signal=signal,
                    detail=duplicate_detail,
                    update_dispatch_state=False,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=duplicate_detail,
                )
                return
            self._clear_duplicate_entry_warning_state(symbol, strategy_id)
            if self._is_entry_action(side) and not self._reserve_pending_entry(symbol, strategy_id):
                duplicate_detail = (
                    f"symbol={symbol};strategy={strategy_id};"
                    "duplicate_source=pending_entry_reservation"
                )
                self._log_duplicate_entry_warning_if_due(
                    symbol,
                    strategy_id,
                    pivot_context,
                    duplicate_source="pending_entry_reservation",
                    stage="pre_dispatch",
                )
                self._record_signal_drop(
                    "pre_dispatch",
                    "duplicate_open_position",
                    signal=signal,
                    detail=duplicate_detail,
                    update_dispatch_state=False,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=duplicate_detail,
                )
                return

        if approved:
            self._signal_flow_counts["approved"] += 1
            if isinstance(signal, dict):
                _strat = (
                    signal.get("strategy_name")
                    or signal.get("strategy_type")
                    or signal.get("strategy_tag")
                    or signal.get("strategy_id")
                    or "signal"
                )
                _sym = signal.get("symbol", "")
                _exec_label = f"{_strat} · {_sym}" if _sym else str(_strat)
            else:
                _exec_label = "signal dispatched"
            self.logger.info("🎯 Strategy Executed: %s", _exec_label)
            # v27 SPEC-12: dispatch on a worker thread so the EventManager
            # dispatcher thread isn't frozen for ≤30s on a slow broker call.
            try:
                self._dispatch_executor.submit(self._dispatch_approved_signal, signal)
            except Exception as _disp_exc:
                # Pool unavailable (e.g. shut down) — fall back to inline so we
                # don't silently drop an approved signal.
                self.logger.warning(
                    "D31 dispatch executor unavailable, falling back to inline: %s",
                    _disp_exc,
                )
                self._dispatch_approved_signal(signal)

    def _get_entry_filter_gate(self) -> Any | None:
        """Lazily build the F09 gate used for market-structure trust checks."""
        if self._entry_filter_gate is not None:
            return self._entry_filter_gate

        try:
            from Spyder.SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters
        except ImportError:
            try:
                from SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters  # type: ignore[no-redef]
            except ImportError:
                self.logger.debug("D31: EntryFilters unavailable for entry trust gate")
                return None

        config_manager = None
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            config_manager = get_config_manager()
        except Exception:
            try:
                from SpyderA_Core.SpyderA03_Configuration import get_config_manager  # type: ignore[no-redef]

                config_manager = get_config_manager()
            except Exception:
                config_manager = None

        if config_manager is None:
            self.logger.debug("D31: config manager unavailable for entry trust gate")
            return None

        try:
            self._entry_filter_gate = EntryFilters(config_manager=config_manager)
        except Exception as exc:
            self.logger.debug("D31: failed to initialize EntryFilters: %s", exc, exc_info=True)
            self._entry_filter_gate = None

        return self._entry_filter_gate

    def _get_eco_calendar(self) -> Any | None:
        """Lazily resolve the S18 EconomicCalendar singleton."""
        if self._eco_calendar_resolved:
            return self._eco_calendar

        self._eco_calendar_resolved = True
        try:
            from Spyder.SpyderS_Signals.SpyderS18_EconomicCalendar import get_economic_calendar
        except ImportError:
            try:
                from SpyderS_Signals.SpyderS18_EconomicCalendar import get_economic_calendar  # type: ignore[no-redef]
            except ImportError:
                self.logger.debug("D31: S18_EconomicCalendar unavailable — eco gate disabled")
                self._eco_calendar = None
                return None

        try:
            self._eco_calendar = get_economic_calendar()
        except Exception as exc:
            self.logger.debug("D31: failed to init EconomicCalendar: %s", exc, exc_info=True)
            self._eco_calendar = None

        return self._eco_calendar

    def _passes_eco_calendar_gate(self, signal: Any) -> tuple[bool, str]:
        """Block new entries during tier-1 macro-event stand-down windows.

        Closing trades always pass — the gate only guards new entries.
        Returns ``(True, "")`` when trading should proceed.
        """
        if self._is_closing_trade_signal(signal):
            return True, ""

        eco = self._get_eco_calendar()
        if eco is None:
            return True, ""

        try:
            blocked, reason = eco.is_stand_down_active()
            if blocked:
                return False, reason
        except Exception as exc:
            self.logger.debug("D31: eco calendar gate error: %s", exc, exc_info=True)

        return True, ""

    @staticmethod
    def _normalise_strategy_type_for_entry_gate(strategy_type: Any) -> str:
        """Normalize strategy identifiers so gate/policy matching is deterministic."""
        if strategy_type is None:
            return ""

        normalized = str(strategy_type).strip().lower()
        if not normalized:
            return ""

        normalized = re.sub(r"[^a-z0-9]+", "_", normalized).strip("_")
        normalized = re.sub(r"_v\d+$", "", normalized)

        aliases = {
            "bullishstrangle": "bullish_strangle",
            "bullishstranglestrategy": "bullish_strangle",
            "bull_put_spread": "bull_put_credit_spread",
            "bear_call_spread": "bear_call_credit_spread",
            "brokenwingbutterfly": "broken_wing_butterfly",
            "ironbutterfly": "iron_butterfly",
            "jadelizardzero": "jade_lizard_zero",
            "jadelizardzerostrategy": "jade_lizard_zero",
            "putcreditspread7": "put_credit_spread_7",
            "putcreditspread7strategy": "put_credit_spread_7",
            "iron_condor": "iron_condor_defined_risk",
            "zerohft": "zero_hft",
            "zerohftstrategy": "zero_hft",
            "pivotmeanreversion": "pivot_mean_reversion",
            "pivot_mr": "pivot_mean_reversion",
            "d34_pivotmr": "pivot_mean_reversion",
        }
        return aliases.get(normalized, normalized)

    @staticmethod
    def _overlay_slot_flag_enabled() -> bool:
        """Return True when the optional ODTE overlay flag is enabled."""
        return str(os.environ.get("SPYDER_ENABLE_ODTE_PIVOT_OVERLAY_SLOT", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @staticmethod
    def _paper_calendar_spread_routing_flag_enabled() -> bool:
        """Return True when optional paper calendar spread routing is enabled."""
        return str(os.environ.get("SPYDER_ENABLE_PAPER_CALENDAR_SPREAD_ROUTING", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _build_overlay_gate_metadata(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Build overlay-gate metadata for the D31 -> E01 risk request."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        strategy_type_value = (
            signal.get("strategy_type")
            or metadata.get("strategy_type")
            or signal.get("strategy_id")
            or metadata.get("strategy_id")
            or ""
        )
        strategy_type_normalized = self._normalise_strategy_type_for_entry_gate(strategy_type_value)

        with self._strategies_lock:
            active_strategy_count = len(self.active_strategies)

        execution_quality = signal.get("execution_quality")
        if not isinstance(execution_quality, dict):
            execution_quality = (
                metadata.get("execution_quality")
                if isinstance(metadata.get("execution_quality"), dict)
                else {}
            )

        projected_post_trade_greeks = signal.get("projected_post_trade_greeks")
        if not isinstance(projected_post_trade_greeks, dict):
            projected_post_trade_greeks = (
                metadata.get("projected_post_trade_greeks")
                if isinstance(metadata.get("projected_post_trade_greeks"), dict)
                else {}
            )

        event_clock_state = signal.get("event_clock_state")
        if event_clock_state is None:
            event_clock_state = metadata.get("event_clock_state")

        event_window_blocked = signal.get("event_window_blocked", metadata.get("event_window_blocked"))
        if event_window_blocked is None and isinstance(event_clock_state, dict):
            event_state = str(event_clock_state.get("state", "clear")).strip().lower()
            if event_state:
                event_window_blocked = event_state != "clear"

        overlay_gate_missing_inputs = signal.get("overlay_gate_missing_inputs")
        if not isinstance(overlay_gate_missing_inputs, list):
            overlay_gate_missing_inputs = (
                metadata.get("overlay_gate_missing_inputs")
                if isinstance(metadata.get("overlay_gate_missing_inputs"), list)
                else []
            )

        overlay_slot_requested = (
            self._overlay_slot_flag_enabled()
            and strategy_type_normalized == "pivot_mean_reversion"
            and active_strategy_count >= self.max_concurrent_strategies
        )

        overlay_metadata: dict[str, Any] = {
            "strategy_type_normalized": strategy_type_normalized,
            "active_strategy_count": active_strategy_count,
            "overlay_slot_requested": overlay_slot_requested,
            "is_overlay_slot": overlay_slot_requested,
            "daily_risk_used_fraction": signal.get(
                "daily_risk_used_fraction",
                metadata.get("daily_risk_used_fraction"),
            ),
            "projected_post_trade_greeks": projected_post_trade_greeks,
            "execution_quality": execution_quality,
            "event_window_blocked": event_window_blocked,
            "event_clock_state": event_clock_state,
            "overlay_gate_missing_inputs": overlay_gate_missing_inputs,
        }
        if strategy_type_normalized == "pivot_mean_reversion":
            overlay_metadata["strategy_type"] = strategy_type_normalized

        return overlay_metadata

    def _strategy_policy_match_tokens(self, strategy_name: Any) -> set[str]:
        """Build normalized tokens for regime policy strategy allow/block matching."""
        if strategy_name is None:
            return set()

        raw = str(strategy_name).strip().lower()
        if not raw:
            return set()

        compact = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
        compact_no_version = re.sub(r"_v\d+$", "", compact)
        normalized = self._normalise_strategy_type_for_entry_gate(compact_no_version)

        tokens: set[str] = {compact, compact_no_version, normalized}

        if normalized.endswith("_credit_spread"):
            tokens.add("credit_spread")
        if normalized.endswith("_debit_spread"):
            tokens.add("debit_spread")

        return {token for token in tokens if token}

    def _entry_gate_fail_closed(self) -> bool:
        """Resolve whether missing/unhealthy entry-gate context must block signals."""
        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg = get_config_manager()
            configured = cfg.get(
                "autonomous_readiness.fail_closed_if_entry_gate_unavailable",
                None,
            )
            if configured is not None:
                return bool(configured)
        except Exception:
            pass

        return self._is_live_mode()

    def _passes_entry_trust_gate(self, signal: Any) -> tuple[bool, str]:
        """Apply F09 structural trust filters and regime policy gate."""
        if not isinstance(signal, dict):
            return True, ""

        if self._is_closing_trade_signal(signal):
            return True, ""

        entry_gate = self._get_entry_filter_gate()
        if entry_gate is None:
            if self._entry_gate_fail_closed():
                return False, "entry_gate_unavailable"
            return True, ""

        signal_market_conditions = signal.get("market_conditions")
        if isinstance(signal_market_conditions, dict):
            market_conditions = signal_market_conditions
        else:
            cache_conditions = self.market_data_cache.get("market_conditions") if isinstance(self.market_data_cache, dict) else {}  # noqa: E501
            market_conditions = cache_conditions if isinstance(cache_conditions, dict) else {}
            if not market_conditions and self._metrics_orchestrator is not None:
                try:
                    metrics_conditions = self._metrics_orchestrator.get_current_market_conditions()
                except Exception:
                    metrics_conditions = {}
                if isinstance(metrics_conditions, dict):
                    market_conditions = metrics_conditions

        if not market_conditions:
            if self._entry_gate_fail_closed():
                return False, "market_conditions_unavailable"
            return True, ""

        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        action = str(signal.get("action") or signal.get("side") or metadata.get("action") or "").strip().lower()  # noqa: E501
        strategy_type = self._normalise_strategy_type_for_entry_gate(
            signal.get("strategy_type")
            or metadata.get("strategy_type")
            or signal.get("strategy_id")
            or metadata.get("strategy_id")
        )
        pivot_signal = self._extract_pivot_signal_payload(signal, market_conditions)
        params = {
            "strategy_type": strategy_type,
            "position_type": signal.get("position_type") or metadata.get("position_type") or "",
            "direction": signal.get("direction") or metadata.get("direction") or signal.get("bias") or metadata.get("bias") or action,  # noqa: E501
            "action": action,
            "pivot_mr_signal": pivot_signal,
            "market_conditions": market_conditions,
            "event_clock_state": (
                signal.get("event_clock_state")
                or metadata.get("event_clock_state")
                or market_conditions.get("event_clock_state")
                or {}
            ),
        }

        try:
            checks = []
            checks.extend(entry_gate._check_time_filters(params))
            if self.lean_mode:
                checks.extend(entry_gate._check_data_quality_filter(params))
                checks.extend(entry_gate._check_short_term_vol_stress_filter(params))
                checks.extend(entry_gate._check_vix_term_structure_filter())
            else:
                checks.extend(entry_gate._check_data_quality_filter(params))
                checks.extend(entry_gate._check_vol_surface_structure_filter(params))
                checks.extend(entry_gate._check_dealer_flow_filter(params))
                checks.extend(entry_gate._check_vix_term_structure_filter())
                checks.extend(entry_gate._check_short_term_vol_stress_filter(params))
        except Exception as exc:
            self.logger.debug("D31: entry trust gate evaluation failed: %s", exc, exc_info=True)
            if self._entry_gate_fail_closed():
                return False, "entry_gate_evaluation_failed"
            return True, ""

        failures = []
        for check in checks:
            result = getattr(check, "result", None)
            if getattr(result, "value", result) == "fail":
                failures.append(check)
        if not failures:
            return self._passes_regime_policy_gate(signal, market_conditions)

        return False, "; ".join(str(check.message) for check in failures)

    def _evaluate_pre_risk_signal_gates(self, signal: dict[str, Any]) -> tuple[bool, str, str, str]:
        """Evaluate pre-risk policy gates and return canonical drop metadata.

        Returns:
            (is_allowed, stage, reason, detail)
        """
        session_gate_ok, session_gate_reason = self._passes_session_window_gate(signal)
        if not session_gate_ok:
            return False, "pre_risk", "session_window_gate", session_gate_reason

        if (
            self._is_opening_trade_signal(signal)
            and self._is_waiting_for_deferred_paper_regime_engine()
        ):
            return (
                False,
                "pre_risk",
                "paper_startup_regime_wait",
                "paper_startup:waiting_for_l09_regime_engine",
            )

        # S18 economic calendar stand-down gate — block new entries near tier-1 events
        eco_gate_ok, eco_gate_reason = self._passes_eco_calendar_gate(signal)
        if not eco_gate_ok:
            return False, "pre_risk", "eco_calendar_gate", eco_gate_reason

        market_gate_ok, market_gate_reason = self._passes_entry_trust_gate(signal)
        if not market_gate_ok:
            return False, "pre_risk", "entry_trust_gate", market_gate_reason

        return True, "", "", ""

    def _get_regime_policy(self) -> dict[str, Any]:
        """Load six-regime policy from config manager or repo config file."""
        if self._regime_policy is not None:
            return self._regime_policy

        policy: dict[str, Any] = {}

        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager
            cfg = get_config_manager()
            candidate = cfg.get("autonomous_readiness.regime_policy", {})
            if isinstance(candidate, dict):
                policy = candidate
        except Exception:
            policy = {}

        if not policy:
            policy_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "config",
                "regime_policy.json",
            )
            try:
                with open(policy_path, encoding="utf-8") as f:
                    policy = json.load(f)
            except Exception:
                policy = {}

        self._regime_policy = policy if isinstance(policy, dict) else {}
        return self._regime_policy

    def _resolve_lean_mode(self) -> bool:
        """Resolve lean-mode flag from env or configuration."""
        env = os.environ.get("SPYDER_LEAN_MODE")
        if env is not None:
            return env.strip().lower() == "true"

        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager
            cfg = get_config_manager()
            return bool(cfg.get("autonomous_readiness.lean_mode", True))
        except Exception:
            return True

    def _load_session_window_policy(self) -> dict[str, Any]:
        """Load autonomous session window policy with safe defaults."""
        policy: dict[str, Any] = {
            "primary_start_et": "09:30",
            "primary_end_et": "16:15",
            "first_entry_not_before_et": "09:45",
            "zero_dte_no_new_risk_cutoff_et": "14:30",
            "broker_cutoff_et": "16:00",
            "broker_cutoff_buffer_minutes": 10,
            "pin_risk_monitor_end_et": "17:30",
            "fail_closed_if_cutoff_unknown_live": True,
        }

        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager

            cfg = get_config_manager()
            candidate = cfg.get("autonomous_readiness.session_window", {})
            if isinstance(candidate, dict):
                merged = dict(policy)
                merged.update(candidate)
                policy = merged
        except Exception:
            pass

        return policy

    @staticmethod
    def _parse_hhmm(value: Any, fallback: str) -> dt_time:
        """Parse HH:MM strings into ET clock-time values."""
        raw = str(value or fallback).strip()
        try:
            parsed = datetime.strptime(raw, "%H:%M")
            return parsed.time()
        except Exception:
            parsed = datetime.strptime(fallback, "%H:%M")
            return parsed.time()

    def _session_time(self, key: str, fallback: str) -> dt_time:
        """Read a session policy HH:MM value from cached D31 policy."""
        return self._parse_hhmm(self._session_window_policy.get(key, fallback), fallback)

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        """Coerce values to float, returning None on parse errors."""
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_date(value: Any) -> datetime.date | None:
        """Parse date-like values from common ISO formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        text = str(value).strip()
        if not text:
            return None
        text = text.split("T", 1)[0]
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except Exception:
            return None

    def _is_live_mode(self) -> bool:
        """Return True when runtime is configured for live trading."""
        candidates = (
            self._audit_run_mode,
            os.environ.get("SPYDER_TRADING_MODE"),
            os.environ.get("TRADING_MODE"),
        )
        for value in candidates:
            if value is None:
                continue
            text = str(value).strip().lower()
            if text in {"live", "production", "prod"}:
                return True
            if text in {"paper", "sandbox", "sim", "simulation", "development", "dev", "test", "testing"}:
                return False
        return False

    def _has_valid_broker_cutoff(self) -> bool:
        """Check whether broker cutoff is present and parseable."""
        raw = self._session_window_policy.get("broker_cutoff_et")
        if raw is None:
            return False
        try:
            _ = datetime.strptime(str(raw).strip(), "%H:%M")
            return True
        except Exception:
            return False

    def _is_short_option_entry(self, signal: dict[str, Any]) -> bool:
        """Identify short option entry intent from signal payload."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        action = str(
            signal.get("action")
            or signal.get("side")
            or metadata.get("action")
            or metadata.get("side")
            or ""
        ).strip().lower()
        if action not in {"sell", "sell_to_open", "short"}:
            return False

        option_symbol = str(signal.get("option_symbol") or metadata.get("option_symbol") or "").strip()
        symbol = str(signal.get("symbol") or metadata.get("symbol") or "").strip()
        strategy_candidates = (
            signal.get("strategy_type"),
            metadata.get("strategy_type"),
            signal.get("strategy_id"),
            metadata.get("strategy_id"),
        )
        normalized_candidates = {
            self._normalise_strategy_type_for_entry_gate(candidate)
            for candidate in strategy_candidates
            if candidate
        }
        has_short_premium_strategy_hint = any(
            candidate in {
                "iron_condor_defined_risk",
                "iron_butterfly",
                "jade_lizard",
                "credit_spread",
                "evolved_credit_spread",
                "bull_put_credit_spread",
                "bear_call_credit_spread",
            }
            or candidate.endswith("_credit_spread")
            for candidate in normalized_candidates
        )
        has_option_hint = (
            bool(option_symbol)
            or bool(re.search(r"[CP]\d{8}$", symbol))
            or has_short_premium_strategy_hint
        )
        return has_option_hint

    def _is_opening_trade_signal(self, signal: dict[str, Any]) -> bool:
        """Identify signals that open new risk and should respect first-entry embargo."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        action = str(
            signal.get("action")
            or signal.get("side")
            or metadata.get("action")
            or metadata.get("side")
            or ""
        ).strip().lower()
        opening_actions = {
            "buy",
            "buy_to_open",
            "sell_to_open",
            "enter",
            "open",
            "long",
            "short",
            "bot",
            "sld",
        }
        if action == "sell" and self._is_short_option_entry(signal):
            return True
        return action in opening_actions

    def _is_closing_trade_signal(self, signal: dict[str, Any]) -> bool:
        """Identify explicit close/reduce signals that should bypass entry-only gates."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        action = str(
            signal.get("action")
            or metadata.get("action")
            or signal.get("side")
            or metadata.get("side")
            or ""
        ).strip().lower()
        return action in {
            "close",
            "exit",
            "flatten",
            "reduce",
            "de_risk",
            "buy_to_close",
            "sell_to_close",
            "btc",
            "stc",
        }

    def _is_zero_dte_signal(self, signal: dict[str, Any], now_et: datetime) -> bool:
        """Best-effort 0DTE detection from signal metadata."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}

        for key in ("dte", "days_to_expiry", "days_to_expiration"):
            candidate = self._coerce_float(signal.get(key))
            if candidate is None:
                candidate = self._coerce_float(metadata.get(key))
            if candidate is not None:
                return candidate <= 0.0

        for key in ("expiry", "expiration", "expiry_date", "expiration_date"):
            candidate = self._coerce_date(signal.get(key))
            if candidate is None:
                candidate = self._coerce_date(metadata.get(key))
            if candidate is not None:
                return candidate == now_et.date()

        return False

    def _passes_session_window_gate(self, signal: dict[str, Any]) -> tuple[bool, str]:
        """Apply configured session window + 0DTE cutoff controls."""
        if self._is_closing_trade_signal(signal):
            return True, ""

        now_et = _d31_now_et()
        if now_et.weekday() >= 5:
            return False, "session_window:weekend_block"

        start_et = self._session_time("primary_start_et", "09:30")
        end_et = self._session_time("primary_end_et", "16:15")
        current_time = now_et.time()
        if current_time < start_et or current_time >= end_et:
            return False, "session_window:outside_primary_window"

        first_entry_not_before = self._session_time("first_entry_not_before_et", "09:45")
        if self._is_opening_trade_signal(signal) and current_time < first_entry_not_before:
            return False, "session_window:first_entry_embargo"

        fail_closed_live = bool(self._session_window_policy.get("fail_closed_if_cutoff_unknown_live", True))
        if self._is_live_mode() and fail_closed_live and not self._has_valid_broker_cutoff():
            return False, "session_window:missing_broker_cutoff_live"

        if self._is_opening_trade_signal(signal) and self._is_zero_dte_signal(signal, now_et):
            cutoff = self._session_time("zero_dte_no_new_risk_cutoff_et", "14:30")
            if current_time >= cutoff:
                return False, "session_window:zero_dte_no_new_risk_cutoff"

        return True, ""

    @staticmethod
    def _extract_option_strike(option_symbol: str) -> float | None:
        """Parse strike from OCC-style option symbols ending with C/P########."""
        match = re.search(r"[CP](\d{8})$", str(option_symbol).strip())
        if not match:
            return None
        try:
            return int(match.group(1)) / 1000.0
        except Exception:
            return None

    @staticmethod
    def _coerce_datetime(value: Any) -> datetime | None:
        """Parse datetime-like values from common ISO formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _extract_option_underlying(option_symbol: Any) -> str:
        """Return the OCC underlying symbol, or the plain symbol when non-option."""
        text = str(option_symbol or "").strip().upper()
        if not text:
            return ""
        match = re.match(r"^([A-Z]{1,6})\d{6}[CP]\d{8}$", text)
        if match:
            return match.group(1)
        return text

    @staticmethod
    def _parse_occ_option_symbol(option_symbol: Any) -> dict[str, Any]:
        """Parse OCC option symbol details when available."""
        text = str(option_symbol or "").strip().upper()
        match = re.match(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$", text)
        if not match:
            return {}
        try:
            expiry = datetime.strptime(match.group(2), "%y%m%d").date().isoformat()
        except Exception:
            expiry = ""
        return {
            "underlying": match.group(1),
            "expiration": expiry,
            "option_type": "call" if match.group(3) == "C" else "put",
            "option_type_letter": match.group(3),
            "strike": int(match.group(4)) / 1000.0,
        }

    def _get_cached_last_price(self, symbol: str) -> float | None:
        """Read the latest cached price for a symbol from market_data_cache."""
        bucket = self.market_data_cache.get(symbol) if isinstance(self.market_data_cache, dict) else None
        if isinstance(bucket, deque) and bucket:
            last_tick = bucket[-1]
            if isinstance(last_tick, dict):
                for key in ("last", "close", "price"):
                    value = self._coerce_float(last_tick.get(key))
                    if value is not None and value > 0:
                        return value
        return None

    def _get_spy_last_price(self) -> float | None:
        """Read latest configured regime-symbol last-price from cached buckets."""
        return self._get_cached_last_price(self._regime_source_symbol)

    def _build_market_df_for_symbol(
        self,
        symbol: str,
        fallback_price: float | None = None,
    ) -> pd.DataFrame | None:
        """Build a compact market DataFrame from the cached symbol bucket."""
        rows: list[dict[str, Any]] = []
        cache = self.market_data_cache if isinstance(self.market_data_cache, dict) else {}
        bucket = cache.get(symbol)
        if isinstance(bucket, deque) and bucket:
            for tick in list(bucket)[-60:]:
                if not isinstance(tick, dict):
                    continue
                row = dict(tick)
                close_price = self._coerce_float(
                    row.get("close")
                    or row.get("last")
                    or row.get("price")
                    or fallback_price
                )
                if close_price is None or close_price <= 0:
                    continue
                row.setdefault("symbol", symbol)
                row.setdefault("open", close_price)
                row.setdefault("high", close_price)
                row.setdefault("low", close_price)
                row["close"] = close_price
                rows.append(row)

        if not rows:
            if fallback_price is None or fallback_price <= 0:
                return None
            rows = [
                {
                    "symbol": symbol,
                    "open": fallback_price,
                    "high": fallback_price,
                    "low": fallback_price,
                    "close": fallback_price,
                    "last": fallback_price,
                }
                for _ in range(20)
            ]
        elif len(rows) < 20:
            seed_row = dict(rows[0])
            rows = [dict(seed_row) for _ in range(20 - len(rows))] + rows

        market_df = pd.DataFrame(rows)
        return self._enrich_market_df_with_options_metrics(market_df)

    def _extract_iron_condor_setup_payload(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Extract explicit iron-condor strikes/expiry hints when present."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        setup = metadata.get("setup") if isinstance(metadata.get("setup"), dict) else {}
        strikes_source = None
        if isinstance(setup.get("strikes"), dict):
            strikes_source = setup.get("strikes")
        elif isinstance(metadata.get("optimal_strikes"), dict):
            strikes_source = metadata.get("optimal_strikes")

        normalized_strikes: dict[str, float] = {}
        if isinstance(strikes_source, dict):
            key_map = {
                "put_long": ("put_long", "long_put", "long_put_strike"),
                "put_short": ("put_short", "short_put", "short_put_strike"),
                "call_short": ("call_short", "short_call", "short_call_strike"),
                "call_long": ("call_long", "long_call", "long_call_strike"),
            }
            for normalized_key, candidates in key_map.items():
                for candidate in candidates:
                    value = self._coerce_float(strikes_source.get(candidate))
                    if value is not None:
                        normalized_strikes[normalized_key] = float(value)
                        break

        expiration_value = (
            setup.get("expiration_time")
            or signal.get("expiration")
            or signal.get("expiration_date")
            or metadata.get("expiration")
            or metadata.get("expiration_date")
        )
        expiration_dt = self._coerce_datetime(expiration_value)

        dte_value = None
        for key in ("dte", "days_to_expiry", "days_to_expiration"):
            dte_value = self._coerce_float(signal.get(key))
            if dte_value is None:
                dte_value = self._coerce_float(metadata.get(key))
            if dte_value is None:
                dte_value = self._coerce_float(setup.get(key))
            if dte_value is not None:
                break
        if dte_value is None and expiration_dt is not None:
            now_et = _d31_now_et()
            try:
                dte_value = float((expiration_dt.date() - now_et.date()).days)
            except Exception:
                dte_value = None

        target_credit = (
            self._coerce_float(setup.get("credit_received"))
            or self._coerce_float(setup.get("credit"))
            or self._coerce_float(metadata.get("expected_credit"))
            or self._coerce_float(signal.get("price"))
            or self._coerce_float(signal.get("entry_price"))
        )

        return {
            "strikes": normalized_strikes,
            "expiration": expiration_dt,
            "dte": int(dte_value) if dte_value is not None else None,
            "target_credit": target_credit,
        }

    def _extract_iron_butterfly_setup_payload(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Extract explicit iron-butterfly strikes and expiry hints when present."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        setup = metadata.get("setup") if isinstance(metadata.get("setup"), dict) else {}
        strikes_source = setup.get("strikes") if isinstance(setup.get("strikes"), dict) else {}

        normalized_strikes: dict[str, float] = {}
        key_map = {
            "put_long": ("put_long", "long_put", "long_put_strike"),
            "put_short": ("put_short", "short_put", "short_put_strike", "atm_strike"),
            "call_short": ("call_short", "short_call", "short_call_strike", "atm_strike"),
            "call_long": ("call_long", "long_call", "long_call_strike"),
        }
        sources = (signal, metadata, setup, strikes_source)
        for normalized_key, candidates in key_map.items():
            for source in sources:
                if not isinstance(source, dict):
                    continue
                for candidate in candidates:
                    value = self._coerce_float(source.get(candidate))
                    if value is not None:
                        normalized_strikes[normalized_key] = float(value)
                        break
                if normalized_key in normalized_strikes:
                    break

        expiration_value = (
            setup.get("expiration_time")
            or signal.get("expiration")
            or signal.get("expiration_date")
            or metadata.get("expiration")
            or metadata.get("expiration_date")
        )
        expiration_dt = self._coerce_datetime(expiration_value)

        dte_value = None
        for key in ("target_dte", "dte", "days_to_expiry", "days_to_expiration"):
            for source in (signal, metadata, setup):
                if not isinstance(source, dict):
                    continue
                dte_value = self._coerce_float(source.get(key))
                if dte_value is not None:
                    break
            if dte_value is not None:
                break
        if dte_value is None and expiration_dt is not None:
            now_et = _d31_now_et()
            try:
                dte_value = float((expiration_dt.date() - now_et.date()).days)
            except Exception:
                dte_value = None

        target_credit = (
            self._coerce_float(setup.get("credit"))
            or self._coerce_float(setup.get("credit_received"))
            or self._coerce_float(metadata.get("expected_credit"))
            or self._coerce_float(signal.get("price"))
            or self._coerce_float(signal.get("entry_price"))
        )

        return {
            "strikes": normalized_strikes,
            "expiration": expiration_dt,
            "dte": int(dte_value) if dte_value is not None else None,
            "target_credit": target_credit,
        }

    def _extract_calendar_spread_setup_payload(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Extract serialized calendar setup payload for explicit paper leg routing."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        setup_source = signal.get("setup")
        if not isinstance(setup_source, dict):
            setup_source = metadata.get("setup")
        setup = setup_source if isinstance(setup_source, dict) else {}
        near_leg = setup.get("near_leg") if isinstance(setup.get("near_leg"), dict) else {}
        far_leg = setup.get("far_leg") if isinstance(setup.get("far_leg"), dict) else {}
        calendar_type = str(
            setup.get("calendar_type") or metadata.get("calendar_type") or ""
        ).strip().lower()
        return {
            "calendar_type": calendar_type,
            "near_leg": near_leg,
            "far_leg": far_leg,
        }

    def _build_multileg_market_analysis(
        self,
        signal: dict[str, Any],
        symbol: str,
    ) -> Any | None:
        """Build D32-style market analysis from cached market data."""
        cached_symbol_price = self._get_cached_last_price(symbol)
        fallback_price = (
            cached_symbol_price
            or self._coerce_float(signal.get("price"))
            or self._coerce_float(signal.get("entry_price"))
            or self._get_spy_last_price()
        )
        market_df = self._build_market_df_for_symbol(symbol, fallback_price)
        if market_df is None or market_df.empty:
            return None

        try:
            from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import MultiLegMarketAnalyzer
        except Exception as exc:
            self.logger.warning("Paper iron condor routing unavailable: %s", exc)
            return None

        analyzer = MultiLegMarketAnalyzer({})
        return analyzer.analyze_environment(market_df)

    def _resolve_paper_iron_condor_underlying_symbol(self, symbol: Any) -> str:
        """Resolve the paper multileg underlying symbol under SPXW-only policy."""
        _ = symbol
        return "SPX"

    @staticmethod
    def _resolve_paper_iron_condor_option_root(symbol: Any) -> str:
        """Resolve the OCC option root used for paper multileg leg symbols."""
        _ = symbol
        return "SPXW"

    def _build_paper_iron_condor_structure(
        self,
        signal: dict[str, Any],
        symbol: str,
    ) -> Any | None:
        """Construct an iron-condor structure for paper execution."""
        execution_symbol = self._resolve_paper_iron_condor_underlying_symbol(symbol)
        market_analysis = self._build_multileg_market_analysis(signal, execution_symbol)
        if market_analysis is None:
            return None

        try:
            from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
                MultiLegStrategyConstructor,
                MultiLegStrategyType,
                MultiLegStructure,
                OptionLeg,
            )
        except Exception as exc:
            self.logger.warning("Paper iron condor construction unavailable: %s", exc)
            return None

        setup_payload = self._extract_iron_condor_setup_payload(signal)
        constructor = MultiLegStrategyConstructor(
            {"symbol": execution_symbol, "underlying_symbol": execution_symbol}
        )
        strikes = setup_payload.get("strikes") if isinstance(setup_payload.get("strikes"), dict) else {}
        if len(strikes) == 4:
            now_et = _d31_now_et()
            expiration_dt = setup_payload.get("expiration")
            if not isinstance(expiration_dt, datetime):
                dte_fallback = setup_payload.get("dte")
                if dte_fallback is None:
                    dte_fallback = 0 if self._is_zero_dte_signal(signal, now_et) else 30
                expiration_dt = datetime.combine(
                    now_et.date() + timedelta(days=max(int(dte_fallback), 0)),
                    datetime.min.time(),
                    tzinfo=UTC,
                )

            expiration_dt = constructor._resolve_live_option_expiration(execution_symbol, expiration_dt)

            dte_value = setup_payload.get("dte")
            resolved_dte = max((expiration_dt.date() - now_et.date()).days, 0)
            if dte_value is None or int(dte_value) != resolved_dte:
                dte_value = resolved_dte
            pricing_dte = max(int(dte_value), 1)

            legs = [
                OptionLeg("put", float(strikes["put_long"]), 1, expiration_dt),
                OptionLeg("put", float(strikes["put_short"]), -1, expiration_dt),
                OptionLeg("call", float(strikes["call_short"]), -1, expiration_dt),
                OptionLeg("call", float(strikes["call_long"]), 1, expiration_dt),
            ]
            constructor._estimate_legs_pricing_and_greeks(
                legs,
                float(market_analysis.underlying_price),
                float(market_analysis.implied_volatility),
                pricing_dte,
            )

            target_credit = self._coerce_float(setup_payload.get("target_credit"))
            estimated_credit = constructor._calculate_net_credit(legs)
            if target_credit is not None and target_credit > 0 and estimated_credit > 0:
                scale = target_credit / estimated_credit
                for leg in legs:
                    leg.price *= scale

            net_credit = constructor._calculate_net_credit(legs)
            wing_width = max(
                float(strikes["put_short"]) - float(strikes["put_long"]),
                float(strikes["call_long"]) - float(strikes["call_short"]),
            )
            breakeven_lower = float(strikes["put_short"]) - net_credit
            breakeven_upper = float(strikes["call_short"]) + net_credit
            probability_profit = constructor._estimate_probability_profit(
                float(market_analysis.underlying_price),
                [breakeven_lower, breakeven_upper],
                float(market_analysis.expected_move),
            )
            net_delta = sum(leg.delta * leg.quantity for leg in legs)
            net_gamma = sum(leg.gamma * leg.quantity for leg in legs)
            net_theta = sum(leg.theta * leg.quantity for leg in legs)
            net_vega = sum(leg.vega * leg.quantity for leg in legs)
            return MultiLegStructure(
                strategy_type=MultiLegStrategyType.IRON_CONDOR,
                legs=legs,
                net_credit=net_credit,
                max_profit=net_credit,
                max_loss=max(wing_width - net_credit, 0.0),
                breakeven_points=[breakeven_lower, breakeven_upper],
                probability_profit=probability_profit,
                net_delta=net_delta,
                net_gamma=net_gamma,
                net_theta=net_theta,
                net_vega=net_vega,
                wing_width=wing_width,
                body_width=float(strikes["call_short"]) - float(strikes["put_short"]),
                risk_reward_ratio=(max(wing_width - net_credit, 0.0) / net_credit) if net_credit > 0 else 0.0,
            )

        now_et = _d31_now_et()
        fallback_dte = setup_payload.get("dte")
        if fallback_dte is None:
            fallback_dte = 0 if self._is_zero_dte_signal(signal, now_et) else 30
        return constructor.construct_strategy(
            MultiLegStrategyType.IRON_CONDOR,
            market_analysis,
            days_to_expiration=max(int(fallback_dte), 1),
        )

    def _build_paper_iron_condor_leg_orders(
        self,
        signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
    ) -> list[dict[str, Any]]:
        """Decompose an iron-condor structure into explicit option-leg orders."""
        execution_symbol = self._resolve_paper_iron_condor_underlying_symbol(symbol)
        option_root = self._resolve_paper_iron_condor_option_root(execution_symbol)
        structure = self._build_paper_iron_condor_structure(signal, execution_symbol)
        if structure is None or not getattr(structure, "legs", None):
            return []

        try:
            from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
        except Exception as exc:
            self.logger.warning("Option symbol formatting unavailable: %s", exc)
            return []

        leg_roles = ["long_put", "short_put", "short_call", "long_call"]
        orders: list[dict[str, Any]] = []
        for index, leg in enumerate(list(structure.legs)[:4]):
            expiry = leg.expiration.date() if isinstance(leg.expiration, datetime) else _d31_now_et().date()
            option_type_letter = "C" if str(leg.option_type).lower() == "call" else "P"
            option_symbol = DateTimeUtils.format_option_symbol(
                option_root,
                expiry,
                option_type_letter,
                float(leg.strike),
            )
            side = "buy_to_open" if int(leg.quantity) > 0 else "sell_to_open"
            contracts = max(abs(int(leg.quantity)) * max(int(quantity), 1), 1)
            limit_price = round(max(float(getattr(leg, "price", 0.0) or 0.01), 0.01), 2)
            option_details = self._parse_occ_option_symbol(option_symbol)
            orders.append(
                {
                    "symbol": option_symbol,
                    "side": side,
                    "quantity": contracts,
                    "order_type": "limit",
                    "price": limit_price,
                    "strategy_id": strategy_id,
                    "multileg_leg_execution": True,
                    "multileg_parent_symbol": execution_symbol,
                    "multileg_parent_strategy": str(strategy_id or "iron_condor"),
                    "leg_role": leg_roles[index] if index < len(leg_roles) else f"leg_{index + 1}",
                    "expiration": option_details.get("expiration"),
                    "strike": option_details.get("strike"),
                    "option_type": option_details.get("option_type"),
                }
            )
        return orders

    def _dispatch_paper_iron_condor(
        self,
        signal: Any,
        raw_signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
        pivot_context: str,
    ) -> None:
        """Dispatch a paper iron condor as four explicit option-leg orders."""
        if self._live_engine is None:
            self._clear_pending_entry_reservation(symbol, strategy_id)
            self.logger.warning(
                "Paper iron condor dropped — no live engine wired: symbol=%s | %s",
                symbol,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                "no_live_engine_for_paper_iron_condor",
                signal=signal,
            )
            self._record_signal_dispatch_outcome_safe("dispatch_rejected", signal=signal)
            return

        leg_orders = self._build_paper_iron_condor_leg_orders(
            raw_signal,
            symbol,
            quantity,
            strategy_id,
        )
        if len(leg_orders) != 4:
            self._clear_pending_entry_reservation(symbol, strategy_id)
            detail = "paper iron condor routing could not derive four explicit option legs"
            self.logger.warning(
                "Paper iron condor rejected — %s: symbol=%s strategy=%s | %s",
                detail,
                symbol,
                strategy_id,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                "paper_iron_condor_structure_missing",
                signal=signal,
                detail=detail,
            )
            self._record_signal_dispatch_outcome_safe(
                "dispatch_rejected",
                signal=signal,
                detail=detail,
            )
            return

        accepted_leg_orders: list[dict[str, Any]] = []
        for leg_order in leg_orders:
            result = self._live_engine.execute_order(leg_order)
            status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
            if status in {"rejected", "error", "timeout"}:
                rollback_failures = self._rollback_paper_multileg_entry_orders(
                    accepted_leg_orders,
                    strategy_label="Paper iron condor",
                    symbol=symbol,
                    strategy_id=strategy_id,
                    pivot_context=pivot_context,
                )
                self._clear_pending_entry_reservation(symbol, strategy_id)
                reason = result.get("reason", "") if isinstance(result, dict) else ""
                detail = f"leg={leg_order.get('leg_role')};status={status};reason={reason or status}"
                if rollback_failures:
                    detail = f"{detail};rollback={'|'.join(rollback_failures)}"
                self.logger.warning(
                    "Paper iron condor leg rejected: %s symbol=%s strategy=%s | %s",
                    detail,
                    symbol,
                    strategy_id,
                    pivot_context,
                )
                self._record_signal_drop(
                    "dispatch",
                    "paper_iron_condor_leg_rejected",
                    signal=signal,
                    detail=detail,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=detail,
                )
                return

            tracked_leg_order = dict(leg_order)
            order_id = result.get("order_id") if isinstance(result, dict) else None
            if order_id:
                tracked_leg_order["_accepted_order_id"] = str(order_id)
            accepted_leg_orders.append(tracked_leg_order)

        self.logger.info(
            "Paper iron condor dispatched as four option legs: symbol=%s strategy=%s qty=%d | %s",
            symbol,
            strategy_id,
            quantity,
            pivot_context,
        )
        self._record_signal_dispatch_outcome_safe("dispatch_submitted", signal=signal)

    def _build_paper_iron_butterfly_leg_orders(
        self,
        signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
    ) -> list[dict[str, Any]]:
        """Decompose an iron-butterfly structure into explicit option-leg orders."""
        setup_payload = self._extract_iron_butterfly_setup_payload(signal)
        strikes = setup_payload.get("strikes") if isinstance(setup_payload.get("strikes"), dict) else {}
        if len(strikes) != 4:
            return []

        execution_symbol = self._resolve_paper_iron_condor_underlying_symbol(symbol)
        option_root = self._resolve_paper_iron_condor_option_root(execution_symbol)

        market_analysis = self._build_multileg_market_analysis(signal, execution_symbol)
        if market_analysis is None:
            return []

        try:
            from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
                MultiLegStrategyConstructor,
                OptionLeg,
            )
        except Exception as exc:
            self.logger.warning("Paper iron butterfly construction unavailable: %s", exc)
            return []

        try:
            from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
        except Exception as exc:
            self.logger.warning("Option symbol formatting unavailable: %s", exc)
            return []

        constructor = MultiLegStrategyConstructor(
            {
                "symbol": execution_symbol,
                "underlying_symbol": execution_symbol,
            }
        )
        expiration_dt = self._resolve_paper_multileg_expiration(
            signal,
            execution_symbol,
            constructor,
            setup_payload.get("expiration"),
            setup_payload.get("dte"),
        )
        now_et = _d31_now_et()
        resolved_dte = max((expiration_dt.date() - now_et.date()).days, 0)
        pricing_dte = max(int(resolved_dte or setup_payload.get("dte") or 1), 1)

        legs = [
            OptionLeg("put", float(strikes["put_long"]), 1, expiration_dt),
            OptionLeg("put", float(strikes["put_short"]), -1, expiration_dt),
            OptionLeg("call", float(strikes["call_short"]), -1, expiration_dt),
            OptionLeg("call", float(strikes["call_long"]), 1, expiration_dt),
        ]
        constructor._estimate_legs_pricing_and_greeks(
            legs,
            float(market_analysis.underlying_price),
            float(market_analysis.implied_volatility),
            pricing_dte,
        )
        try:
            constructor._get_live_option_chain_strikes(
                execution_symbol,
                expiration_dt.date().isoformat(),
            )
            constructor._apply_live_chain_prices_to_legs(legs)
        except Exception as exc:
            self.logger.debug(
                "Paper iron butterfly live-chain pricing unavailable for %s: %s",
                execution_symbol,
                exc,
            )

        target_credit = self._coerce_float(setup_payload.get("target_credit"))
        estimated_credit = constructor._calculate_net_credit(legs)
        if target_credit is not None and target_credit > 0.0 and estimated_credit > 0.0:
            scale = target_credit / estimated_credit
            for leg in legs:
                leg.price *= scale

        leg_roles = ["long_put", "short_put", "short_call", "long_call"]
        is_closing_signal = self._is_closing_trade_signal(signal)
        orders: list[dict[str, Any]] = []
        for index, leg in enumerate(legs):
            expiry = leg.expiration.date() if isinstance(leg.expiration, datetime) else now_et.date()
            option_symbol = DateTimeUtils.format_option_symbol(
                option_root,
                expiry,
                "C" if str(leg.option_type).lower() == "call" else "P",
                float(leg.strike),
            )
            if is_closing_signal:
                side = "sell_to_close" if int(leg.quantity) > 0 else "buy_to_close"
            else:
                side = "buy_to_open" if int(leg.quantity) > 0 else "sell_to_open"

            contracts = max(abs(int(leg.quantity)) * max(int(quantity), 1), 1)
            limit_price = round(max(float(getattr(leg, "price", 0.0) or 0.01), 0.01), 2)
            option_details = self._parse_occ_option_symbol(option_symbol)
            orders.append(
                {
                    "symbol": option_symbol,
                    "side": side,
                    "quantity": contracts,
                    "order_type": "limit",
                    "price": limit_price,
                    "strategy_id": strategy_id,
                    "multileg_leg_execution": True,
                    "multileg_parent_symbol": execution_symbol,
                    "multileg_parent_strategy": str(strategy_id or "iron_butterfly"),
                    "leg_role": leg_roles[index] if index < len(leg_roles) else f"leg_{index + 1}",
                    "expiration": option_details.get("expiration"),
                    "strike": option_details.get("strike"),
                    "option_type": option_details.get("option_type"),
                }
            )
        return orders

    def _dispatch_paper_iron_butterfly(
        self,
        signal: Any,
        raw_signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
        pivot_context: str,
    ) -> None:
        """Dispatch a paper iron butterfly as four explicit option-leg orders."""
        is_closing_signal = self._is_closing_trade_signal(raw_signal)

        def _clear_reservation() -> None:
            if is_closing_signal:
                self._clear_pending_exit_reservation(symbol, strategy_id)
            else:
                self._clear_pending_entry_reservation(symbol, strategy_id)

        if self._live_engine is None:
            _clear_reservation()
            self.logger.warning(
                "Paper iron butterfly dropped — no live engine wired: symbol=%s | %s",
                symbol,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                "no_live_engine_for_paper_iron_butterfly",
                signal=signal,
            )
            self._record_signal_dispatch_outcome_safe("dispatch_rejected", signal=signal)
            return

        leg_orders = self._build_paper_iron_butterfly_leg_orders(
            raw_signal,
            symbol,
            quantity,
            strategy_id,
        )
        if len(leg_orders) != 4:
            _clear_reservation()
            detail = "paper iron butterfly routing could not derive four explicit option legs"
            self.logger.warning(
                "Paper iron butterfly rejected — %s: symbol=%s strategy=%s | %s",
                detail,
                symbol,
                strategy_id,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                "paper_iron_butterfly_structure_missing",
                signal=signal,
                detail=detail,
            )
            self._record_signal_dispatch_outcome_safe(
                "dispatch_rejected",
                signal=signal,
                detail=detail,
            )
            return

        accepted_leg_orders: list[dict[str, Any]] = []
        for leg_order in leg_orders:
            result = self._live_engine.execute_order(leg_order)
            status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
            if status in {"rejected", "error", "timeout"}:
                rollback_failures: list[str] = []
                if not is_closing_signal:
                    rollback_failures = self._rollback_paper_multileg_entry_orders(
                        accepted_leg_orders,
                        strategy_label="Paper iron butterfly",
                        symbol=symbol,
                        strategy_id=strategy_id,
                        pivot_context=pivot_context,
                    )
                _clear_reservation()
                reason = result.get("reason", "") if isinstance(result, dict) else ""
                detail = f"leg={leg_order.get('leg_role')};status={status};reason={reason or status}"
                if rollback_failures:
                    detail = f"{detail};rollback={'|'.join(rollback_failures)}"
                self.logger.warning(
                    "Paper iron butterfly leg rejected: %s symbol=%s strategy=%s | %s",
                    detail,
                    symbol,
                    strategy_id,
                    pivot_context,
                )
                self._record_signal_drop(
                    "dispatch",
                    "paper_iron_butterfly_leg_rejected",
                    signal=signal,
                    detail=detail,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=detail,
                )
                return

            tracked_leg_order = dict(leg_order)
            order_id = result.get("order_id") if isinstance(result, dict) else None
            if order_id:
                tracked_leg_order["_accepted_order_id"] = str(order_id)
            accepted_leg_orders.append(tracked_leg_order)

        self.logger.info(
            "Paper iron butterfly dispatched as four option legs: symbol=%s strategy=%s qty=%d | %s",
            symbol,
            strategy_id,
            quantity,
            pivot_context,
        )
        self._record_signal_dispatch_outcome_safe("dispatch_submitted", signal=signal)

    def _extract_butterfly_family_setup_payload(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Extract Butterfly/BWB setup metadata for explicit paper leg routing."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        strategy_value = (
            signal.get("strategy_type")
            or metadata.get("strategy_type")
            or signal.get("strategy_id")
            or metadata.get("strategy_id")
            or ""
        )
        normalized_strategy_key = self._normalise_strategy_type_for_entry_gate(strategy_value)

        def _float_value(*keys: str) -> float | None:
            for source in (signal, metadata):
                for key in keys:
                    if key not in source:
                        continue
                    candidate = self._coerce_float(source.get(key))
                    if candidate is not None:
                        return candidate
            return None

        expiration_dt = None
        for source in (signal, metadata):
            for key in ("expiration", "expiry", "expiration_date", "expiry_date"):
                if key not in source:
                    continue
                expiration_dt = self._coerce_datetime(source.get(key))
                if expiration_dt is not None:
                    break
                expiration_date = self._coerce_date(source.get(key))
                if expiration_date is not None:
                    expiration_dt = datetime.combine(
                        expiration_date,
                        datetime.min.time(),
                        tzinfo=UTC,
                    )
                    break
            if expiration_dt is not None:
                break

        dte_value = _float_value(
            "target_dte",
            "days_to_expiry",
            "days_to_expiration",
            "dte",
        )

        if normalized_strategy_key == "butterfly":
            structure = str(
                signal.get("structure") or metadata.get("structure") or "long_call_butterfly"
            ).strip().lower()
            option_type = "put" if "put" in structure else "call"
            lower_strike = _float_value("lower_strike")
            body_strike = _float_value("body_strike")
            upper_strike = _float_value("upper_strike")
            if None in {lower_strike, body_strike, upper_strike}:
                return {}
            return {
                "strategy_key": normalized_strategy_key,
                "option_type": option_type,
                "expiration": expiration_dt,
                "dte": int(dte_value) if dte_value is not None else None,
                "target_premium": _float_value("expected_debit", "target_debit", "debit"),
                "premium_kind": "debit",
                "legs": [
                    {"role": "lower_call", "strike": lower_strike, "quantity": 1},
                    {"role": "body_call", "strike": body_strike, "quantity": -2},
                    {"role": "upper_call", "strike": upper_strike, "quantity": 1},
                ],
            }

        if normalized_strategy_key == "broken_wing_butterfly":
            upper_wing_strike = _float_value("upper_wing_strike")
            body_strike = _float_value("body_strike")
            lower_wing_strike = _float_value("lower_wing_strike")
            if None in {upper_wing_strike, body_strike, lower_wing_strike}:
                return {}
            return {
                "strategy_key": normalized_strategy_key,
                "option_type": "put",
                "expiration": expiration_dt,
                "dte": int(dte_value) if dte_value is not None else None,
                "target_premium": _float_value("expected_credit", "target_credit", "credit"),
                "premium_kind": "credit",
                "legs": [
                    {"role": "upper_put", "strike": upper_wing_strike, "quantity": 1},
                    {"role": "body_put", "strike": body_strike, "quantity": -2},
                    {"role": "lower_put", "strike": lower_wing_strike, "quantity": 1},
                ],
            }

        return {}

    def _resolve_paper_multileg_expiration(
        self,
        signal: dict[str, Any],
        symbol: str,
        constructor: Any,
        expiration_dt: datetime | None,
        dte_value: int | None,
    ) -> datetime:
        """Resolve a paper multileg expiration to a listed contract date when possible."""
        now_et = _d31_now_et()
        resolved_expiration = expiration_dt
        if isinstance(resolved_expiration, datetime) and resolved_expiration.tzinfo is None:
            resolved_expiration = resolved_expiration.replace(tzinfo=UTC)

        if not isinstance(resolved_expiration, datetime):
            fallback_dte = dte_value
            if fallback_dte is None:
                fallback_dte = 0 if self._is_zero_dte_signal(signal, now_et) else 30
            resolved_expiration = datetime.combine(
                now_et.date() + timedelta(days=max(int(fallback_dte), 0)),
                datetime.min.time(),
                tzinfo=UTC,
            )

        try:
            return constructor._resolve_live_option_expiration(symbol, resolved_expiration)
        except Exception:
            return resolved_expiration

    def _build_paper_butterfly_family_leg_orders(
        self,
        signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
    ) -> list[dict[str, Any]]:
        """Decompose Butterfly/BWB paper signals into explicit option-leg orders."""
        setup_payload = self._extract_butterfly_family_setup_payload(signal)
        if not setup_payload:
            return []

        execution_symbol = self._resolve_paper_iron_condor_underlying_symbol(symbol)
        option_root = self._resolve_paper_iron_condor_option_root(execution_symbol)

        market_analysis = self._build_multileg_market_analysis(signal, execution_symbol)
        if market_analysis is None:
            return []

        try:
            from Spyder.SpyderD_Strategies.SpyderD32_MultiLegStrategyCoordinator import (
                MultiLegStrategyConstructor,
                OptionLeg,
            )
        except Exception as exc:
            self.logger.warning("Paper butterfly-family routing unavailable: %s", exc)
            return []

        try:
            from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
        except Exception as exc:
            self.logger.warning("Option symbol formatting unavailable: %s", exc)
            return []

        constructor = MultiLegStrategyConstructor(
            {
                "symbol": execution_symbol,
                "underlying_symbol": execution_symbol,
            }
        )
        expiration_dt = self._resolve_paper_multileg_expiration(
            signal,
            execution_symbol,
            constructor,
            setup_payload.get("expiration"),
            setup_payload.get("dte"),
        )
        now_et = _d31_now_et()
        pricing_dte = max((expiration_dt.date() - now_et.date()).days, 1)

        legs = [
            OptionLeg(
                str(setup_payload["option_type"]),
                float(leg_spec["strike"]),
                int(leg_spec["quantity"]),
                expiration_dt,
            )
            for leg_spec in setup_payload["legs"]
        ]
        constructor._estimate_legs_pricing_and_greeks(
            legs,
            float(market_analysis.underlying_price),
            float(market_analysis.implied_volatility),
            pricing_dte,
        )
        try:
            constructor._get_live_option_chain_strikes(
                execution_symbol,
                expiration_dt.date().isoformat(),
            )
            constructor._apply_live_chain_prices_to_legs(legs)
        except Exception as exc:
            self.logger.debug(
                "Paper butterfly-family live-chain pricing unavailable for %s: %s",
                execution_symbol,
                exc,
            )

        target_premium = self._coerce_float(setup_payload.get("target_premium"))
        estimated_net_credit = constructor._calculate_net_credit(legs)
        if target_premium is not None and target_premium > 0.0:
            scale = None
            if setup_payload.get("premium_kind") == "debit":
                estimated_debit = max(-estimated_net_credit, 0.0)
                if estimated_debit > 0.0:
                    scale = target_premium / estimated_debit
            else:
                estimated_credit = max(estimated_net_credit, 0.0)
                if estimated_credit > 0.0:
                    scale = target_premium / estimated_credit

            if scale is not None and scale > 0.0:
                for leg in legs:
                    leg.price *= scale

        is_closing_signal = self._is_closing_trade_signal(signal)
        orders: list[dict[str, Any]] = []
        for leg_spec, leg in zip(setup_payload["legs"], legs, strict=False):
            expiry = leg.expiration.date() if isinstance(leg.expiration, datetime) else now_et.date()
            option_type = str(getattr(leg, "option_type", setup_payload["option_type"]).lower())
            option_symbol = DateTimeUtils.format_option_symbol(
                option_root,
                expiry,
                "C" if option_type == "call" else "P",
                float(leg.strike),
            )
            if is_closing_signal:
                side = "sell_to_close" if int(leg.quantity) > 0 else "buy_to_close"
            else:
                side = "buy_to_open" if int(leg.quantity) > 0 else "sell_to_open"

            contracts = max(abs(int(leg.quantity)) * max(int(quantity), 1), 1)
            limit_price = round(max(float(getattr(leg, "price", 0.0) or 0.01), 0.01), 2)
            option_details = self._parse_occ_option_symbol(option_symbol)
            orders.append(
                {
                    "symbol": option_symbol,
                    "side": side,
                    "quantity": contracts,
                    "order_type": "limit",
                    "price": limit_price,
                    "strategy_id": strategy_id,
                    "multileg_leg_execution": True,
                    "multileg_parent_symbol": execution_symbol,
                    "multileg_parent_strategy": str(strategy_id or setup_payload.get("strategy_key")),
                    "leg_role": str(leg_spec["role"]),
                    "expiration": option_details.get("expiration"),
                    "strike": option_details.get("strike"),
                    "option_type": option_details.get("option_type"),
                }
            )
        return orders

    @staticmethod
    def _build_paper_multileg_entry_rollback_order(
        accepted_leg_order: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Build a compensating close for an already-submitted paper entry leg."""
        side = str(accepted_leg_order.get("side") or "").strip().lower().replace("-", "_")
        side_map = {
            "buy_to_open": "sell_to_close",
            "sell_to_open": "buy_to_close",
        }
        compensating_side = side_map.get(side)
        if compensating_side is None:
            return None

        rollback_order = dict(accepted_leg_order)
        for transient_key in (
            "_accepted_order_id",
            "order_id",
            "timestamp",
            "correlation_id",
            "price",
            "limit_price",
            "stop_price",
        ):
            rollback_order.pop(transient_key, None)

        rollback_order["side"] = compensating_side
        rollback_order["order_type"] = "market"
        rollback_order["rollback_compensation"] = True
        rollback_order["multileg_leg_execution"] = True
        return rollback_order

    def _rollback_paper_multileg_entry_orders(
        self,
        accepted_leg_orders: list[dict[str, Any]],
        strategy_label: str,
        symbol: str,
        strategy_id: Any,
        pivot_context: str,
    ) -> list[str]:
        """Cancel pending paper entry legs or close them if they already filled."""
        failures: list[str] = []
        for accepted_leg_order in reversed(accepted_leg_orders):
            leg_role = str(accepted_leg_order.get("leg_role") or "leg")
            accepted_order_id = str(accepted_leg_order.get("_accepted_order_id") or "").strip()

            cancelled = False
            if accepted_order_id:
                try:
                    cancelled = bool(self._live_engine.cancel_order(accepted_order_id))
                except Exception as exc:
                    self.logger.warning(
                        "%s rollback cancel raised for %s (%s): %s",
                        strategy_label,
                        leg_role,
                        accepted_order_id,
                        exc,
                    )

            if cancelled:
                continue

            rollback_order = self._build_paper_multileg_entry_rollback_order(accepted_leg_order)
            if rollback_order is None:
                failures.append(f"{leg_role}:no_compensating_close")
                continue

            try:
                rollback_result = self._live_engine.execute_order(rollback_order)
            except Exception as exc:
                failures.append(f"{leg_role}:exception:{exc}")
                continue

            rollback_status = (
                rollback_result.get("status", "unknown")
                if isinstance(rollback_result, dict)
                else str(rollback_result)
            )
            if rollback_status in {"rejected", "error", "timeout"}:
                rollback_reason = (
                    rollback_result.get("reason", "") if isinstance(rollback_result, dict) else ""
                )
                failures.append(
                    f"{leg_role}:{rollback_status}:{rollback_reason or rollback_status}"
                )

        if failures:
            self.logger.critical(
                "%s rollback left unmatched entry legs: symbol=%s strategy=%s failures=%s | %s",
                strategy_label,
                symbol,
                strategy_id,
                failures,
                pivot_context,
            )
        return failures

    def _reject_paper_multileg_dispatch(
        self,
        signal: Any,
        raw_signal: dict[str, Any],
        symbol: str,
        strategy_id: Any,
        pivot_context: str,
        reason_code: str,
        detail: str,
        strategy_label: str,
    ) -> None:
        """Reject paper multileg dispatches that would otherwise flatten into underliers."""
        if self._is_closing_trade_signal(raw_signal):
            self._clear_pending_exit_reservation(symbol, strategy_id)
        else:
            self._clear_pending_entry_reservation(symbol, strategy_id)
        self.logger.warning(
            "%s rejected — %s: symbol=%s strategy=%s | %s",
            strategy_label,
            detail,
            symbol,
            strategy_id,
            pivot_context,
        )
        self._record_signal_drop(
            "dispatch",
            reason_code,
            signal=signal,
            detail=detail,
        )
        self._record_signal_dispatch_outcome_safe(
            "dispatch_rejected",
            signal=signal,
            detail=detail,
        )

    def _dispatch_paper_butterfly_family(
        self,
        signal: Any,
        raw_signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
        pivot_context: str,
    ) -> None:
        """Dispatch Butterfly/BWB paper entries as explicit option-leg orders."""
        normalized_strategy_key = self._normalise_strategy_type_for_entry_gate(strategy_id)
        is_closing_signal = self._is_closing_trade_signal(raw_signal)
        strategy_label = (
            "Paper broken wing butterfly"
            if normalized_strategy_key == "broken_wing_butterfly"
            else "Paper butterfly"
        )

        if self._live_engine is None:
            self._reject_paper_multileg_dispatch(
                signal=signal,
                raw_signal=raw_signal,
                symbol=symbol,
                strategy_id=strategy_id,
                pivot_context=pivot_context,
                reason_code=f"{normalized_strategy_key}_no_live_engine",
                detail="no live engine wired for explicit paper option-leg routing",
                strategy_label=strategy_label,
            )
            return

        leg_orders = self._build_paper_butterfly_family_leg_orders(
            raw_signal,
            symbol,
            quantity,
            strategy_id,
        )
        if len(leg_orders) != 3:
            reason_key = normalized_strategy_key or "paper_butterfly_family"
            self._reject_paper_multileg_dispatch(
                signal=signal,
                raw_signal=raw_signal,
                symbol=symbol,
                strategy_id=strategy_id,
                pivot_context=pivot_context,
                reason_code=f"{reason_key}_structure_missing",
                detail="paper butterfly-family routing could not derive three explicit option legs",
                strategy_label=strategy_label,
            )
            return

        accepted_leg_orders: list[dict[str, Any]] = []
        for leg_order in leg_orders:
            result = self._live_engine.execute_order(leg_order)
            status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
            if status in {"rejected", "error", "timeout"}:
                rollback_failures: list[str] = []
                if not is_closing_signal:
                    rollback_failures = self._rollback_paper_multileg_entry_orders(
                        accepted_leg_orders,
                        strategy_label=strategy_label,
                        symbol=symbol,
                        strategy_id=strategy_id,
                        pivot_context=pivot_context,
                    )
                detail = str(leg_order.get("leg_role") or "leg")
                reason = result.get("reason", "") if isinstance(result, dict) else ""
                rejection_detail = f"leg={detail};status={status};reason={reason or status}"
                if rollback_failures:
                    rejection_detail = f"{rejection_detail};rollback={'|'.join(rollback_failures)}"
                self._reject_paper_multileg_dispatch(
                    signal=signal,
                    raw_signal=raw_signal,
                    symbol=symbol,
                    strategy_id=strategy_id,
                    pivot_context=pivot_context,
                    reason_code=f"{normalized_strategy_key}_leg_rejected",
                    detail=rejection_detail,
                    strategy_label=strategy_label,
                )
                return

            tracked_leg_order = dict(leg_order)
            order_id = result.get("order_id") if isinstance(result, dict) else None
            if order_id:
                tracked_leg_order["_accepted_order_id"] = str(order_id)
            accepted_leg_orders.append(tracked_leg_order)

        self.logger.info(
            "%s dispatched as three option legs: symbol=%s strategy=%s qty=%d | %s",
            strategy_label,
            symbol,
            strategy_id,
            quantity,
            pivot_context,
        )
        self._record_signal_dispatch_outcome_safe("dispatch_submitted", signal=signal)

    def _build_paper_calendar_spread_leg_orders(
        self,
        signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
    ) -> list[dict[str, Any]]:
        """Decompose a serialized calendar spread into explicit option-leg orders."""
        setup_payload = self._extract_calendar_spread_setup_payload(signal)
        near_leg = setup_payload.get("near_leg") if isinstance(setup_payload.get("near_leg"), dict) else {}
        far_leg = setup_payload.get("far_leg") if isinstance(setup_payload.get("far_leg"), dict) else {}
        if not near_leg or not far_leg:
            return []

        execution_symbol = self._resolve_paper_iron_condor_underlying_symbol(symbol)
        option_root = self._resolve_paper_iron_condor_option_root(execution_symbol)

        try:
            from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
        except Exception as exc:
            self.logger.warning("Option symbol formatting unavailable: %s", exc)
            return []

        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        action = str(
            signal.get("action")
            or metadata.get("action")
            or signal.get("side")
            or metadata.get("side")
            or ""
        ).strip().lower()
        is_closing_signal = self._is_closing_trade_signal(signal)
        if not is_closing_signal and action not in {
            "buy",
            "buy_to_open",
            "sell",
            "sell_to_open",
            "enter",
            "open",
            "long",
        }:
            return []

        orders: list[dict[str, Any]] = []
        for leg_role, leg in (("near_leg", near_leg), ("far_leg", far_leg)):
            expiry = self._coerce_date(leg.get("expiry"))
            strike = self._coerce_float(leg.get("strike"))
            option_type = str(leg.get("option_type") or "").strip().lower()
            direction = int(self._coerce_float(leg.get("position")) or 0)
            leg_contracts = int(self._coerce_float(leg.get("contracts")) or abs(direction) or 1)
            if expiry is None or strike is None or option_type not in {"call", "put"} or direction == 0:
                return []

            option_symbol = DateTimeUtils.format_option_symbol(
                option_root,
                expiry,
                "C" if option_type == "call" else "P",
                float(strike),
            )
            if is_closing_signal:
                side = "sell_to_close" if direction > 0 else "buy_to_close"
            else:
                side = "buy_to_open" if direction > 0 else "sell_to_open"

            contracts = max(abs(leg_contracts) * max(int(quantity), 1), 1)
            limit_price = round(
                max(
                    self._coerce_float(leg.get("price"))
                    or self._coerce_float(leg.get("premium"))
                    or 0.01,
                    0.01,
                ),
                2,
            )
            option_details = self._parse_occ_option_symbol(option_symbol)
            orders.append(
                {
                    "symbol": option_symbol,
                    "side": side,
                    "quantity": contracts,
                    "order_type": "limit",
                    "price": limit_price,
                    "strategy_id": strategy_id,
                    "multileg_leg_execution": True,
                    "multileg_parent_symbol": execution_symbol,
                    "multileg_parent_strategy": str(strategy_id or "calendar_spread"),
                    "leg_role": leg_role,
                    "expiration": option_details.get("expiration"),
                    "strike": option_details.get("strike"),
                    "option_type": option_details.get("option_type"),
                    "calendar_type": setup_payload.get("calendar_type") or None,
                }
            )
        return orders

    def _dispatch_paper_calendar_spread(
        self,
        signal: Any,
        raw_signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
        pivot_context: str,
    ) -> None:
        """Dispatch a paper calendar spread as two explicit option-leg orders."""
        is_closing_signal = self._is_closing_trade_signal(raw_signal)

        def _clear_reservation() -> None:
            if is_closing_signal:
                self._clear_pending_exit_reservation(symbol, strategy_id)
            else:
                self._clear_pending_entry_reservation(symbol, strategy_id)

        if self._live_engine is None:
            _clear_reservation()
            self.logger.warning(
                "Paper calendar spread dropped — no live engine wired: symbol=%s | %s",
                symbol,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                "no_live_engine_for_paper_calendar_spread",
                signal=signal,
            )
            self._record_signal_dispatch_outcome_safe("dispatch_rejected", signal=signal)
            return

        leg_orders = self._build_paper_calendar_spread_leg_orders(
            raw_signal,
            symbol,
            quantity,
            strategy_id,
        )
        if len(leg_orders) != 2:
            _clear_reservation()
            detail = "paper calendar spread routing could not derive two explicit option legs"
            self.logger.warning(
                "Paper calendar spread rejected — %s: symbol=%s strategy=%s | %s",
                detail,
                symbol,
                strategy_id,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                "paper_calendar_spread_structure_missing",
                signal=signal,
                detail=detail,
            )
            self._record_signal_dispatch_outcome_safe(
                "dispatch_rejected",
                signal=signal,
                detail=detail,
            )
            return

        accepted_leg_orders: list[dict[str, Any]] = []
        for leg_order in leg_orders:
            result = self._live_engine.execute_order(leg_order)
            status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
            if status in {"rejected", "error", "timeout"}:
                rollback_failures: list[str] = []
                if not is_closing_signal:
                    rollback_failures = self._rollback_paper_multileg_entry_orders(
                        accepted_leg_orders,
                        strategy_label="Paper calendar spread",
                        symbol=symbol,
                        strategy_id=strategy_id,
                        pivot_context=pivot_context,
                    )
                _clear_reservation()
                reason = result.get("reason", "") if isinstance(result, dict) else ""
                detail = f"leg={leg_order.get('leg_role')};status={status};reason={reason or status}"
                if rollback_failures:
                    detail = f"{detail};rollback={'|'.join(rollback_failures)}"
                self.logger.warning(
                    "Paper calendar spread leg rejected: %s symbol=%s strategy=%s | %s",
                    detail,
                    symbol,
                    strategy_id,
                    pivot_context,
                )
                self._record_signal_drop(
                    "dispatch",
                    "paper_calendar_spread_leg_rejected",
                    signal=signal,
                    detail=detail,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=detail,
                )
                return

            tracked_leg_order = dict(leg_order)
            order_id = result.get("order_id") if isinstance(result, dict) else None
            if order_id:
                tracked_leg_order["_accepted_order_id"] = str(order_id)
            accepted_leg_orders.append(tracked_leg_order)

        self.logger.info(
            "Paper calendar spread dispatched as two option legs: symbol=%s strategy=%s qty=%d | %s",
            symbol,
            strategy_id,
            quantity,
            pivot_context,
        )
        self._record_signal_dispatch_outcome_safe("dispatch_submitted", signal=signal)

    def _extract_serialized_multileg_setup_payload(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Extract serialized explicit-leg metadata for paper-safe multileg routing."""
        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        strategy_candidates = [
            signal.get("strategy_id"),
            metadata.get("strategy_id"),
            signal.get("strategy_name"),
            metadata.get("strategy_name"),
            signal.get("strategy_type"),
            metadata.get("strategy_type"),
        ]
        normalized_candidates = {
            self._normalise_strategy_type_for_entry_gate(candidate)
            for candidate in strategy_candidates
            if candidate
        }
        if "put_credit_spread_7" in normalized_candidates:
            normalized_strategy_key = "put_credit_spread_7"
        elif "bullish_strangle" in normalized_candidates:
            normalized_strategy_key = "bullish_strangle"
        elif "jade_lizard_zero" in normalized_candidates:
            normalized_strategy_key = "jade_lizard_zero"
        elif "zero_hft" in normalized_candidates:
            normalized_strategy_key = "zero_hft"
        else:
            return {}

        def _float_value(*keys: str) -> float | None:
            for source in (signal, metadata):
                for key in keys:
                    if key not in source:
                        continue
                    candidate = self._coerce_float(source.get(key))
                    if candidate is not None:
                        return candidate
            return None

        expiration_dt = None
        for source in (signal, metadata):
            for key in ("expiration", "expiry", "expiration_date", "expiry_date"):
                if key not in source:
                    continue
                expiration_dt = self._coerce_datetime(source.get(key))
                if expiration_dt is not None:
                    break
                expiration_date = self._coerce_date(source.get(key))
                if expiration_date is not None:
                    expiration_dt = datetime.combine(
                        expiration_date,
                        datetime.min.time(),
                        tzinfo=UTC,
                    )
                    break
            if expiration_dt is not None:
                break

        dte_value = _float_value(
            "target_dte",
            "days_to_expiry",
            "days_to_expiration",
            "dte",
        )

        legs_source = metadata.get("legs")
        if not isinstance(legs_source, list) or not legs_source:
            return {}

        normalized_legs: list[dict[str, Any]] = []
        for index, leg in enumerate(legs_source, start=1):
            if not isinstance(leg, dict):
                return {}

            option_type = str(leg.get("option_type") or leg.get("right") or "").strip().lower()
            strike = self._coerce_float(leg.get("strike"))
            quantity_value = int(self._coerce_float(leg.get("contracts") or leg.get("quantity") or 1) or 1)
            position_value = str(leg.get("position") or leg.get("side") or "").strip().lower()

            if position_value in {"long", "buy", "buy_to_open"}:
                signed_quantity = max(abs(quantity_value), 1)
            elif position_value in {"short", "sell", "sell_to_open"}:
                signed_quantity = -max(abs(quantity_value), 1)
            else:
                signed_quantity = int(self._coerce_float(leg.get("quantity") or 0) or 0)

            if option_type not in {"call", "put"} or strike is None or signed_quantity == 0:
                return {}

            leg_expiration = None
            for key in ("expiration", "expiry", "expiration_date", "expiry_date"):
                if key not in leg:
                    continue
                leg_expiration = self._coerce_datetime(leg.get(key))
                if leg_expiration is not None:
                    break
                leg_expiry_date = self._coerce_date(leg.get(key))
                if leg_expiry_date is not None:
                    leg_expiration = datetime.combine(
                        leg_expiry_date,
                        datetime.min.time(),
                        tzinfo=UTC,
                    )
                    break

            normalized_legs.append(
                {
                    "role": str(
                        leg.get("role") or f"{'long' if signed_quantity > 0 else 'short'}_{option_type}_{index}"
                    ),
                    "option_type": option_type,
                    "strike": strike,
                    "quantity": signed_quantity,
                    "premium": self._coerce_float(leg.get("price") or leg.get("premium")) or 0.01,
                    "expiration": leg_expiration or expiration_dt,
                }
            )

        return {
            "strategy_key": normalized_strategy_key,
            "expiration": expiration_dt,
            "dte": int(dte_value) if dte_value is not None else None,
            "legs": normalized_legs,
        }

    def _build_paper_serialized_multileg_leg_orders(
        self,
        signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
    ) -> list[dict[str, Any]]:
        """Decompose serialized long-vol structures into explicit paper leg orders."""
        setup_payload = self._extract_serialized_multileg_setup_payload(signal)
        if not setup_payload:
            return []

        execution_symbol = self._resolve_paper_iron_condor_underlying_symbol(symbol)
        option_root = self._resolve_paper_iron_condor_option_root(execution_symbol)

        try:
            from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
        except Exception as exc:
            self.logger.warning("Option symbol formatting unavailable: %s", exc)
            return []

        expiration_dt = setup_payload.get("expiration")
        if isinstance(expiration_dt, datetime) and expiration_dt.tzinfo is None:
            expiration_dt = expiration_dt.replace(tzinfo=UTC)

        now_et = _d31_now_et()
        if not isinstance(expiration_dt, datetime):
            fallback_dte = setup_payload.get("dte")
            if fallback_dte is None:
                fallback_dte = 30
            expiration_dt = datetime.combine(
                now_et.date() + timedelta(days=max(int(fallback_dte), 0)),
                datetime.min.time(),
                tzinfo=UTC,
            )

        is_closing_signal = self._is_closing_trade_signal(signal)
        orders: list[dict[str, Any]] = []
        for leg in setup_payload["legs"]:
            leg_expiration = leg.get("expiration")
            if isinstance(leg_expiration, datetime):
                if leg_expiration.tzinfo is None:
                    leg_expiration = leg_expiration.replace(tzinfo=UTC)
            else:
                leg_expiration = expiration_dt

            expiry = leg_expiration.date() if isinstance(leg_expiration, datetime) else now_et.date()
            option_symbol = DateTimeUtils.format_option_symbol(
                option_root,
                expiry,
                "C" if str(leg["option_type"]).lower() == "call" else "P",
                float(leg["strike"]),
            )
            if is_closing_signal:
                side = "sell_to_close" if int(leg["quantity"]) > 0 else "buy_to_close"
            else:
                side = "buy_to_open" if int(leg["quantity"]) > 0 else "sell_to_open"

            contracts = max(abs(int(leg["quantity"])) * max(int(quantity), 1), 1)
            limit_price = round(max(float(leg.get("premium", 0.0) or 0.01), 0.01), 2)
            option_details = self._parse_occ_option_symbol(option_symbol)
            orders.append(
                {
                    "symbol": option_symbol,
                    "side": side,
                    "quantity": contracts,
                    "order_type": "limit",
                    "price": limit_price,
                    "strategy_id": strategy_id,
                    "multileg_leg_execution": True,
                    "multileg_parent_symbol": execution_symbol,
                    "multileg_parent_strategy": str(strategy_id or setup_payload.get("strategy_key")),
                    "leg_role": str(leg["role"]),
                    "expiration": option_details.get("expiration"),
                    "strike": option_details.get("strike"),
                    "option_type": option_details.get("option_type"),
                }
            )
        return orders

    def _resolve_active_strategy_for_signal(self, signal: dict[str, Any]) -> Any | None:
        """Resolve an active strategy instance from semantic signal identifiers."""
        metadata = signal.get("metadata") if isinstance(signal, dict) else {}
        if not isinstance(metadata, dict):
            metadata = {}

        candidate_tokens = {
            self._normalise_strategy_type_for_entry_gate(
                self._signal_value(signal, "strategy_type")
            ),
            self._normalise_strategy_type_for_entry_gate(
                self._signal_value(signal, "strategy_id")
            ),
            self._normalise_strategy_type_for_entry_gate(
                self._signal_value(signal, "strategy_name")
            ),
            self._normalise_strategy_type_for_entry_gate(metadata.get("strategy_type")),
            self._normalise_strategy_type_for_entry_gate(metadata.get("strategy_id")),
            self._normalise_strategy_type_for_entry_gate(metadata.get("alias")),
        }
        candidate_tokens.discard("")
        if not candidate_tokens:
            return None

        strategies: list[Any]
        strategies_lock = getattr(self, "_strategies_lock", None)
        if strategies_lock is None:
            strategies = list(getattr(self, "active_strategies", {}).values())
        else:
            with strategies_lock:
                strategies = list(getattr(self, "active_strategies", {}).values())

        for strategy in strategies:
            runtime_config = getattr(strategy, "runtime_config", None)
            alias = runtime_config.get("alias") if isinstance(runtime_config, dict) else None
            strategy_tokens = {
                self._normalise_strategy_type_for_entry_gate(getattr(strategy, "strategy_type", None)),
                self._normalise_strategy_type_for_entry_gate(getattr(strategy, "name", None)),
                self._normalise_strategy_type_for_entry_gate(alias),
                self._normalise_strategy_type_for_entry_gate(strategy.__class__.__name__),
            }
            strategy_tokens.discard("")
            if candidate_tokens & strategy_tokens:
                return strategy

        return None

    def _notify_strategy_serialized_multileg_dispatch(
        self,
        raw_signal: dict[str, Any],
        accepted_leg_orders: list[dict[str, Any]],
    ) -> None:
        """Forward accepted paper multileg legs back to the owning strategy when supported."""
        strategy = self._resolve_active_strategy_for_signal(raw_signal)
        if strategy is None:
            return

        register_dispatched_short_legs = getattr(strategy, "register_dispatched_short_legs", None)
        if not callable(register_dispatched_short_legs):
            return

        try:
            register_dispatched_short_legs(raw_signal, accepted_leg_orders)
        except Exception as exc:
            self.logger.error(
                "D31: strategy short-leg registration failed for %s: %s",
                getattr(strategy, "name", strategy.__class__.__name__),
                exc,
                exc_info=True,
            )

    def _dispatch_paper_serialized_multileg(
        self,
        signal: Any,
        raw_signal: dict[str, Any],
        symbol: str,
        quantity: int,
        strategy_id: Any,
        pivot_context: str,
    ) -> None:
        """Dispatch serialized multileg paper signals as explicit option-leg orders."""
        normalized_strategy_key = self._normalise_strategy_type_for_entry_gate(strategy_id)
        is_closing_signal = self._is_closing_trade_signal(raw_signal)

        def _clear_reservation() -> None:
            if is_closing_signal:
                self._clear_pending_exit_reservation(symbol, strategy_id)
            else:
                self._clear_pending_entry_reservation(symbol, strategy_id)

        if self._live_engine is None:
            _clear_reservation()
            self.logger.warning(
                "Paper %s dropped — no live engine wired: symbol=%s | %s",
                normalized_strategy_key or "serialized_multileg",
                symbol,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                f"no_live_engine_for_paper_{normalized_strategy_key or 'serialized_multileg'}",
                signal=signal,
            )
            self._record_signal_dispatch_outcome_safe("dispatch_rejected", signal=signal)
            return

        leg_orders = self._build_paper_serialized_multileg_leg_orders(
            raw_signal,
            symbol,
            quantity,
            strategy_id,
        )
        if len(leg_orders) < 2:
            _clear_reservation()
            reason_key = normalized_strategy_key or "serialized_multileg"
            detail = "paper serialized multileg routing could not derive explicit option legs"
            self.logger.warning(
                "Paper %s rejected — %s: symbol=%s strategy=%s | %s",
                reason_key,
                detail,
                symbol,
                strategy_id,
                pivot_context,
            )
            self._record_signal_drop(
                "dispatch",
                f"paper_{reason_key}_structure_missing",
                signal=signal,
                detail=detail,
            )
            self._record_signal_dispatch_outcome_safe(
                "dispatch_rejected",
                signal=signal,
                detail=detail,
            )
            return

        accepted_leg_orders: list[dict[str, Any]] = []
        for leg_order in leg_orders:
            result = self._live_engine.execute_order(leg_order)
            status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
            if status in {"rejected", "error", "timeout"}:
                rollback_failures: list[str] = []
                if not is_closing_signal:
                    rollback_failures = self._rollback_paper_multileg_entry_orders(
                        accepted_leg_orders,
                        strategy_label=f"Paper {normalized_strategy_key or 'serialized_multileg'}",
                        symbol=symbol,
                        strategy_id=strategy_id,
                        pivot_context=pivot_context,
                    )
                _clear_reservation()
                reason = result.get("reason", "") if isinstance(result, dict) else ""
                reason_key = normalized_strategy_key or "serialized_multileg"
                detail = f"leg={leg_order.get('leg_role')};status={status};reason={reason or status}"
                if rollback_failures:
                    detail = f"{detail};rollback={'|'.join(rollback_failures)}"
                self.logger.warning(
                    "Paper %s leg rejected: %s symbol=%s strategy=%s | %s",
                    reason_key,
                    detail,
                    symbol,
                    strategy_id,
                    pivot_context,
                )
                self._record_signal_drop(
                    "dispatch",
                    f"paper_{reason_key}_leg_rejected",
                    signal=signal,
                    detail=detail,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=detail,
                )
                return

            tracked_leg_order = dict(leg_order)
            order_id = result.get("order_id") if isinstance(result, dict) else None
            if order_id:
                tracked_leg_order["_accepted_order_id"] = str(order_id)
            accepted_leg_orders.append(tracked_leg_order)

        self._notify_strategy_serialized_multileg_dispatch(raw_signal, accepted_leg_orders)

        self.logger.info(
            "Paper %s dispatched as %d option legs: symbol=%s strategy=%s qty=%d | %s",
            normalized_strategy_key or "serialized_multileg",
            len(leg_orders),
            symbol,
            strategy_id,
            quantity,
            pivot_context,
        )
        self._record_signal_dispatch_outcome_safe("dispatch_submitted", signal=signal)

    def _count_at_risk_short_options(self, now_et: datetime) -> int:
        """Best-effort count of unresolved short 0DTE options near the money."""
        try:
            from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import get_session_supervisor

            supervisor = get_session_supervisor()
        except Exception:
            return 0

        if supervisor is None:
            return 0

        positions = self._get_pin_risk_positions(supervisor)
        if not positions:
            return 0

        spy_last = self._get_spy_last_price()
        long_coverage_by_bucket: dict[tuple[str, str, str], float] = {}
        at_risk_shorts: list[tuple[tuple[str, str, str], float, float]] = []
        at_risk_count = 0
        for position in positions:
            if isinstance(position, dict):
                quantity = self._coerce_float(position.get("quantity"))
                option_symbol = str(position.get("option_symbol") or position.get("symbol") or "")
                raw_option_type = position.get("option_type") or position.get("right")
                raw_strike = position.get("strike")
                raw_underlying = position.get("underlying") or position.get("root_symbol")
                expiry = self._coerce_date(
                    position.get("expiry")
                    or position.get("expiration")
                    or position.get("expiry_date")
                    or position.get("expiration_date")
                )
            else:
                quantity = self._coerce_float(getattr(position, "quantity", None))
                option_symbol = str(
                    getattr(position, "option_symbol", "")
                    or getattr(position, "symbol", "")
                )
                raw_option_type = getattr(position, "option_type", None) or getattr(position, "right", None)
                raw_strike = getattr(position, "strike", None)
                raw_underlying = (
                    getattr(position, "underlying", None)
                    or getattr(position, "root_symbol", None)
                )
                expiry = self._coerce_date(
                    getattr(position, "expiry", None)
                    or getattr(position, "expiration", None)
                    or getattr(position, "expiry_date", None)
                    or getattr(position, "expiration_date", None)
                )

            if not option_symbol:
                continue

            option_details = self._parse_occ_option_symbol(option_symbol)
            if expiry is None:
                expiry = self._coerce_date(option_details.get("expiration"))
            if expiry is not None and expiry != now_et.date():
                continue

            option_type = str(raw_option_type or option_details.get("option_type") or "").strip().lower()
            if option_type == "c":
                option_type = "call"
            elif option_type == "p":
                option_type = "put"

            strike = self._coerce_float(raw_strike)
            if strike is None:
                strike = self._coerce_float(option_details.get("strike"))
            if strike is None:
                strike = self._extract_option_strike(option_symbol)

            underlying = str(
                raw_underlying
                or option_details.get("underlying")
                or self._extract_option_underlying(option_symbol)
            ).strip().upper()
            expiry_key = expiry.isoformat() if expiry is not None else ""
            bucket_key = (underlying, expiry_key, option_type)

            if quantity is None:
                continue

            if quantity > 0:
                if self._is_assignment_covering_long_option(option_type, strike, spy_last):
                    long_coverage_by_bucket[bucket_key] = (
                        long_coverage_by_bucket.get(bucket_key, 0.0) + quantity
                    )
                continue

            if strike is None or spy_last is None or spy_last <= 0 or option_type not in {"call", "put"}:
                at_risk_count += 1
                continue

            distance_pct = abs(spy_last - strike) / max(spy_last, 1e-6)
            if distance_pct <= 0.003:
                at_risk_shorts.append((bucket_key, abs(quantity), distance_pct))

        for bucket_key, short_quantity, _distance_pct in sorted(
            at_risk_shorts,
            key=lambda item: item[2],
        ):
            available_coverage = long_coverage_by_bucket.get(bucket_key, 0.0)
            if available_coverage + 1e-9 >= short_quantity:
                long_coverage_by_bucket[bucket_key] = max(
                    0.0,
                    available_coverage - short_quantity,
                )
                continue
            long_coverage_by_bucket[bucket_key] = 0.0
            at_risk_count += 1

        return at_risk_count

    def _get_pin_risk_positions(self, supervisor: Any) -> list[Any]:
        """Return the best available open-position inventory for pin-risk checks.

        In paper mode, prefer authoritative runtime or persisted session-db
        positions and avoid falling back to the non-authoritative PositionTracker
        when those surfaces report no open positions.
        """
        engine = getattr(supervisor, "engine", None)
        mode = str(getattr(supervisor, "mode", "") or "").strip().lower()

        if engine is not None:
            try:
                if hasattr(engine, "get_active_positions_snapshot"):
                    raw_positions = engine.get_active_positions_snapshot()
                else:
                    raw_positions = getattr(engine, "active_positions", {})
            except Exception:
                raw_positions = None

            if isinstance(raw_positions, dict):
                active_positions = list(raw_positions.values())
            elif isinstance(raw_positions, list):
                active_positions = raw_positions
            else:
                active_positions = []

            if active_positions:
                return active_positions

            if mode == "paper":
                persisted_positions = self._get_pin_risk_paper_session_rows(engine)
                if persisted_positions is not None:
                    return persisted_positions
                return []

        position_tracker = getattr(supervisor, "position_tracker", None)
        if position_tracker is None and engine is not None:
            position_tracker = getattr(engine, "position_tracker", None)
        if position_tracker is None:
            return []

        raw_positions = getattr(position_tracker, "positions", None)
        if isinstance(raw_positions, dict):
            return list(raw_positions.values())
        if isinstance(raw_positions, list):
            return raw_positions
        return []

    def _get_pin_risk_paper_session_rows(self, engine: Any) -> list[dict[str, Any]] | None:
        """Return persisted paper open positions when runtime state is empty."""
        session_db = getattr(engine, "_session_db", None)
        if session_db is None:
            return None

        selector_names: list[str] = []
        has_active_marker = getattr(session_db, "has_active_paper_session_marker", None)
        active_session_marker: bool | None = None
        if callable(has_active_marker):
            try:
                active_session_marker = bool(has_active_marker())
            except Exception:
                active_session_marker = None

        get_active_open = getattr(session_db, "get_active_paper_open_positions", None)
        get_resume_open = getattr(session_db, "get_resume_eligible_open_positions", None)
        get_open = getattr(session_db, "get_open_positions", None)

        if active_session_marker is True:
            if callable(get_active_open):
                selector_names.append("get_active_paper_open_positions")
            if callable(get_resume_open):
                selector_names.append("get_resume_eligible_open_positions")
        elif active_session_marker is False:
            if callable(get_resume_open):
                selector_names.append("get_resume_eligible_open_positions")
        else:
            if callable(get_active_open):
                selector_names.append("get_active_paper_open_positions")
            if callable(get_resume_open):
                selector_names.append("get_resume_eligible_open_positions")

        if not selector_names and callable(get_open):
            selector_names.append("get_open_positions")

        for selector_name in selector_names:
            get_rows = getattr(session_db, selector_name, None)
            if not callable(get_rows):
                continue
            try:
                rows = get_rows()
            except Exception:
                continue
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return []

    @staticmethod
    def _is_assignment_covering_long_option(
        option_type: str,
        strike: float | None,
        spot_price: float | None,
    ) -> bool:
        """Return whether a long option is exercisable enough to cover assignment."""
        if strike is None or spot_price is None or spot_price <= 0:
            return False
        normalized_type = str(option_type or "").strip().lower()
        if normalized_type == "call":
            return spot_price > strike
        if normalized_type == "put":
            return spot_price < strike
        return False

    def _emit_event_safe(self, event_type: Any, payload: dict[str, Any], severity: str = "normal") -> None:
        """Emit events through whichever EventManager API is available."""
        if self.event_manager is None:
            return

        try:
            if hasattr(self.event_manager, "emit"):
                priority = EventPriority.NORMAL
                if severity in {"warning", "high"}:
                    priority = EventPriority.HIGH
                elif severity in {"critical", "emergency"}:
                    priority = EventPriority.CRITICAL
                self.event_manager.emit(event_type, payload, priority=priority, source="StrategyOrchestrator")
                return
        except Exception:
            pass

        try:
            self.event_manager.publish(event_type, payload)
        except Exception:
            pass

    def _emit_pin_risk_window_events(self) -> None:
        """Emit post-close assignment-risk state and escalations during pin-risk window."""
        now_et = _d31_now_et()
        end_et = self._session_time("primary_end_et", "16:15")
        monitor_end_et = self._session_time("pin_risk_monitor_end_et", "17:30")
        current_time = now_et.time()

        in_window = (current_time >= end_et) and (current_time < monitor_end_et) and (now_et.weekday() < 5)
        new_state = "monitoring" if in_window else "inactive"
        if new_state != self._pin_risk_window_state:
            self._pin_risk_window_state = new_state
            self._emit_event_safe(
                EventType.RISK,
                {
                    "type": "pin_risk_window_state",
                    "state": new_state,
                    "timestamp_et": now_et.isoformat(),
                },
                severity="high" if in_window else "normal",
            )

        if not in_window:
            return

        at_risk_count = self._count_at_risk_short_options(now_et)
        if at_risk_count <= 0:
            return

        now_mono = time.monotonic()
        if now_mono - self._pin_risk_last_emit_ts < 60.0:
            return
        self._pin_risk_last_emit_ts = now_mono

        payload = {
            "type": "pin_risk_unresolved_shorts",
            "severity": "critical",
            "count": at_risk_count,
            "timestamp_et": now_et.isoformat(),
            "message": "Unresolved short option exposure detected in post-close assignment window",
        }
        self._emit_event_safe(EventType.RISK_VIOLATION, payload, severity="critical")
        self._emit_event_safe(EventType.ALERT, payload, severity="critical")

    def _passes_regime_policy_gate(
        self,
        signal: dict[str, Any],
        market_conditions: dict[str, Any],
    ) -> tuple[bool, str]:
        """Apply conservative regime-policy blocks (fail-open on missing context)."""
        policy = self._get_regime_policy()
        regimes = policy.get("regimes", {}) if isinstance(policy, dict) else {}
        if not isinstance(regimes, dict) or not regimes:
            return True, ""

        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        raw_regime = str(
            signal.get("regime")
            or metadata.get("regime")
            or market_conditions.get("regime")
            or market_conditions.get("current_regime")
            or market_conditions.get("market_regime")
            or market_conditions.get("breadth_regime")
            or ""
        ).strip().lower()
        if not raw_regime:
            return True, ""

        regime_key = self._normalize_regime_policy_key(raw_regime, regimes)
        regime_cfg = regimes.get(regime_key, {}) if regime_key else {}
        if not isinstance(regime_cfg, dict) or not regime_cfg:
            return True, ""

        hard_blocks = regime_cfg.get("hard_blocks", {})
        if isinstance(hard_blocks, dict) and bool(hard_blocks.get("no_trade", False)):
            return False, f"regime_policy:no_trade:{regime_key}"

        strategy_name = str(
            signal.get("strategy_type")
            or signal.get("strategy_id")
            or metadata.get("strategy_type")
            or metadata.get("strategy_id")
            or ""
        ).strip().lower()
        strategy_tokens = self._strategy_policy_match_tokens(strategy_name)

        allowed = regime_cfg.get("allowed_strategies", [])
        if isinstance(allowed, list) and allowed:
            if not strategy_name:
                return False, f"regime_policy:missing_strategy:{regime_key}"

            allow_match = False
            for token in allowed:
                allowed_tokens = self._strategy_policy_match_tokens(token)
                if not allowed_tokens:
                    continue
                for allowed_token in allowed_tokens:
                    if any(
                        (allowed_token in strategy_token) or (strategy_token in allowed_token)
                        for strategy_token in strategy_tokens
                    ):
                        allow_match = True
                        break
                if allow_match:
                    break
            if not allow_match:
                return False, f"regime_policy:not_allowed_strategy:{strategy_name}:{regime_key}"

        if strategy_name:
            blocked = regime_cfg.get("blocked_strategies", [])
            if isinstance(blocked, list):
                for token in blocked:
                    blocked_tokens = self._strategy_policy_match_tokens(token)
                    if any(
                        (blocked_token in strategy_token) or (strategy_token in blocked_token)
                        for blocked_token in blocked_tokens
                        for strategy_token in strategy_tokens
                    ):
                        return False, f"regime_policy:blocked_strategy:{str(token).strip().lower()}:{regime_key}"

        return True, ""

    def set_live_engine(self, engine: Any) -> None:
        """Wire a LiveEngine instance so approved signals are dispatched as orders.

        Args:
            engine: A SpyderR04_LiveEngine (or compatible) instance that exposes
                    ``execute_order(order_dict) -> dict``.
        """
        self._live_engine = engine
        self.logger.debug(
            "LiveEngine wired to StrategyOrchestrator for approved-signal dispatch"
        )

    def set_regime_engine(self, engine: Any) -> None:
        """Attach or replace the optional L09 regime engine after startup."""
        self._l09_engine = engine
        self._last_l09_confidence = 0.0
        self._last_l09_consensus = None
        self._paper_startup_regime_engine_pending = False
        self.logger.debug("UnifiedRegimeEngine attached to StrategyOrchestrator")
        if self.orchestration_active and self._initial_strategy_activation_pending:
            try:
                self._run_initial_strategy_activation_if_pending()
            except Exception as exc:
                self.logger.warning(
                    "Deferred initial strategy activation after L09 attach failed: %s",
                    exc,
                )

    def set_order_manager(self, manager: Any) -> None:
        """Wire an OrderManager so approved signals use mid-price walk execution.

        When an OrderManager is wired and the incoming signal carries ``bid``
        and ``ask`` fields (populated at signal-generation time from the live
        options chain), ``_dispatch_approved_signal`` will call
        ``manager.submit_limit_with_walk()`` instead of sending a bare market
        order through the live engine.  This eliminates full-spread slippage on
        every single-leg entry.

        Args:
            manager: A ``SpyderB02_OrderManager`` (or compatible) instance that
                     exposes ``submit_limit_with_walk(symbol, side, quantity,
                     bid, ask, …) -> OrderResult``.
        """
        self._order_manager = manager
        self.logger.info(
            "OrderManager wired to StrategyOrchestrator for mid-price walk execution"
        )

    def set_vix_analyzer(self, analyzer: Any) -> None:
        """Wire a VIXAnalyzer (C10) so _update_market_regime reads live VIX data.

        Args:
            analyzer: A ``SpyderC10_VIXAnalyzer`` (or compatible) instance that
                      exposes ``get_current_vix() -> float``.
        """
        self._vix_analyzer = analyzer
        self.logger.info(
            "VIXAnalyzer wired to StrategyOrchestrator for live VIX regime detection"
        )

    def set_risk_manager(self, manager: Any) -> None:
        """Wire an E01 RiskManager for pre-trade signal validation.

        Caches the reference so the hot-path ``_on_strategy_signal`` avoids a
        module-level import + singleton lookup on every call.

        Args:
            manager: A ``SpyderE01_RiskManager`` (or compatible) instance that
                     exposes ``validate_signal(request) -> RiskValidationResult``.
        """
        self.risk_manager = manager
        self.logger.debug(
            "RiskManager wired to StrategyOrchestrator for signal pre-validation"
        )

    @staticmethod
    def _is_entry_action(action: Any) -> bool:
        """Return True when a signal action represents opening exposure."""
        normalized = str(action or "").strip().lower()
        return normalized in {
            "buy",
            "sell",
            "buy_to_open",
            "sell_to_open",
            "open",
            "enter",
            "enter_long",
            "enter_short",
        }

    def _pending_entry_reservation_key(
        self,
        symbol: Any,
        strategy_id: Any,
    ) -> tuple[str, str] | None:
        """Normalize the key used to block duplicate in-flight entries."""
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return None
        normalized_strategy = str(strategy_id or "").strip().lower()
        return (normalized_symbol, normalized_strategy)

    def _record_manual_close_reentry_embargo(self, symbol: Any, strategy_id: Any) -> None:
        """Prevent immediate re-entry after an operator-initiated manual close."""
        normalized_strategy = str(strategy_id or "").strip().lower()
        if not normalized_strategy:
            return

        candidate_symbols: list[str] = []
        normalized_symbol = str(symbol or "").strip().upper()
        if normalized_symbol:
            candidate_symbols.append(normalized_symbol)

        underlying_symbol = self._extract_option_underlying(symbol)
        if underlying_symbol:
            normalized_underlying = str(underlying_symbol).strip().upper()
            if normalized_underlying and normalized_underlying not in candidate_symbols:
                candidate_symbols.append(normalized_underlying)

        if not candidate_symbols:
            return

        expires_at = time.monotonic() + self._manual_close_reentry_embargo_s
        with self._manual_close_reentry_embargo_lock:
            for candidate_symbol in candidate_symbols:
                key = self._pending_entry_reservation_key(candidate_symbol, normalized_strategy)
                if key is not None:
                    self._manual_close_reentry_embargoes[key] = expires_at

    def _get_manual_close_reentry_embargo_remaining(
        self,
        symbol: Any,
        strategy_id: Any,
    ) -> float | None:
        """Return remaining manual-close embargo seconds for a symbol/strategy."""
        key = self._pending_entry_reservation_key(symbol, strategy_id)
        if key is None:
            return None

        now_monotonic = time.monotonic()
        with self._manual_close_reentry_embargo_lock:
            expires_at = self._manual_close_reentry_embargoes.get(key)
            if expires_at is None:
                return None
            if expires_at <= now_monotonic:
                self._manual_close_reentry_embargoes.pop(key, None)
                return None
            return expires_at - now_monotonic

    def _has_pending_entry_reservation(self, symbol: Any, strategy_id: Any) -> bool:
        """Return True when the same entry is already reserved for dispatch/fill."""
        key = self._pending_entry_reservation_key(symbol, strategy_id)
        if key is None:
            return False

        now_monotonic = time.monotonic()
        with self._pending_entry_reservations_lock:
            expires_at = self._pending_entry_reservations.get(key)
            if expires_at is None:
                return False
            if expires_at <= now_monotonic:
                self._pending_entry_reservations.pop(key, None)
                return False
            return True

    def _reserve_pending_entry(self, symbol: Any, strategy_id: Any) -> bool:
        """Reserve a same-symbol entry slot until fill or terminal cleanup lands."""
        key = self._pending_entry_reservation_key(symbol, strategy_id)
        if key is None:
            return False

        now_monotonic = time.monotonic()
        expires_at = now_monotonic + self._pending_entry_reservation_ttl_s
        with self._pending_entry_reservations_lock:
            existing_expiry = self._pending_entry_reservations.get(key)
            if existing_expiry is not None and existing_expiry > now_monotonic:
                return False
            self._pending_entry_reservations[key] = expires_at
            return True

    def _clear_pending_entry_reservation(self, symbol: Any, strategy_id: Any) -> None:
        """Clear a single in-flight entry reservation."""
        key = self._pending_entry_reservation_key(symbol, strategy_id)
        if key is None:
            return

        with self._pending_entry_reservations_lock:
            self._pending_entry_reservations.pop(key, None)

    def _clear_pending_entry_reservations_for_symbol(self, symbol: Any) -> None:
        """Clear all in-flight reservations for a symbol once truth advances."""
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return

        with self._pending_entry_reservations_lock:
            keys_to_drop = [
                key for key in self._pending_entry_reservations
                if key[0] == normalized_symbol
            ]
            for key in keys_to_drop:
                self._pending_entry_reservations.pop(key, None)

    def _pending_exit_reservation_key(
        self,
        symbol: Any,
        strategy_id: Any,
    ) -> tuple[str, str] | None:
        """Build a stable key for in-flight close reservations."""
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return None
        normalized_strategy = str(strategy_id or "").strip().lower()
        return normalized_symbol, normalized_strategy

    def _reserve_pending_exit(self, symbol: Any, strategy_id: Any) -> bool:
        """Reserve a same-symbol close slot until fill or terminal cleanup lands."""
        key = self._pending_exit_reservation_key(symbol, strategy_id)
        if key is None:
            return False

        now_monotonic = time.monotonic()
        expires_at = now_monotonic + self._pending_exit_reservation_ttl_s
        with self._pending_exit_reservations_lock:
            existing_expiry = self._pending_exit_reservations.get(key)
            if existing_expiry is not None and existing_expiry > now_monotonic:
                return False
            self._pending_exit_reservations[key] = expires_at
            return True

    def _clear_pending_exit_reservation(self, symbol: Any, strategy_id: Any) -> None:
        """Clear a single in-flight close reservation."""
        key = self._pending_exit_reservation_key(symbol, strategy_id)
        if key is None:
            return

        with self._pending_exit_reservations_lock:
            self._pending_exit_reservations.pop(key, None)

    def _clear_pending_exit_reservations_for_symbol(self, symbol: Any) -> None:
        """Clear all in-flight close reservations for a symbol once truth advances."""
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return

        with self._pending_exit_reservations_lock:
            keys_to_drop = [
                key for key in self._pending_exit_reservations
                if key[0] == normalized_symbol
            ]
            for key in keys_to_drop:
                self._pending_exit_reservations.pop(key, None)

    def _clear_duplicate_entry_warning_state(self, symbol: Any, strategy_id: Any) -> None:
        """Reset duplicate-entry warning throttle after the duplicate block clears."""
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            return

        normalized_strategy = str(strategy_id or "").strip().lower()
        key = (normalized_symbol, normalized_strategy)
        self._duplicate_entry_warning_last_monotonic.pop(key, None)

    def _log_duplicate_entry_warning_if_due(
        self,
        symbol: Any,
        strategy_id: Any,
        pivot_context: str,
        *,
        duplicate_source: str,
        stage: str,
    ) -> None:
        """Throttle duplicate-entry bookkeeping without operator-facing warnings."""
        normalized_symbol = str(symbol or "").strip().upper()
        normalized_strategy = str(strategy_id or "").strip().lower()
        key = (normalized_symbol, normalized_strategy)
        now_mono = time.monotonic()
        last_mono = self._duplicate_entry_warning_last_monotonic.get(key, 0.0)
        if (now_mono - last_mono) < self._duplicate_entry_warning_interval_s:
            return

        self._duplicate_entry_warning_last_monotonic[key] = now_mono
        return

    def _get_duplicate_open_position_source(
        self,
        symbol: str,
        strategy_id: Any,
        side: Any,
        include_pending: bool = True,
    ) -> str | None:
        """Return the surface that is currently blocking a duplicate entry."""
        if not self._is_entry_action(side):
            return None

        if include_pending and self._has_pending_entry_reservation(symbol, strategy_id):
            return "pending_entry_reservation"

        if self._live_engine is None:
            return None

        try:
            if hasattr(self._live_engine, "get_active_positions_snapshot"):
                active_positions = self._live_engine.get_active_positions_snapshot()
            else:
                active_positions = getattr(self._live_engine, "active_positions", {})
        except Exception:
            return None

        if not isinstance(active_positions, dict):
            return None

        current_strategy = str(strategy_id or "").strip().lower()

        lookup_symbols = [str(symbol or "").strip()]
        underlying_symbol = self._extract_option_underlying(symbol)
        if underlying_symbol and underlying_symbol not in lookup_symbols:
            lookup_symbols.append(underlying_symbol)

        def _match_source(existing_position: dict[str, Any], existing_symbol: str) -> str | None:
            try:
                existing_qty = int(existing_position.get("quantity") or 0)
            except (TypeError, ValueError):
                existing_qty = 0
            if existing_qty == 0:
                return None

            existing_strategy = str(existing_position.get("strategy") or "").strip().lower()
            if current_strategy and existing_strategy and existing_strategy != current_strategy:
                return None

            existing_underlying = self._extract_option_underlying(
                existing_position.get("underlying_symbol")
                or existing_position.get("symbol")
                or existing_symbol
            )
            if existing_symbol not in lookup_symbols and existing_underlying not in lookup_symbols:
                return None

            position_source = str(existing_position.get("position_source") or "").strip().lower()
            if position_source == "session_db_hydration":
                return "persisted_carryover"
            return "active_positions"

        for lookup_symbol in lookup_symbols:
            existing = active_positions.get(lookup_symbol)
            if isinstance(existing, dict):
                source = _match_source(existing, lookup_symbol)
                if source is not None:
                    self._clear_pending_entry_reservations_for_symbol(symbol)
                    return source

        for existing_symbol, existing_position in active_positions.items():
            if not isinstance(existing_position, dict):
                continue
            source = _match_source(existing_position, str(existing_symbol))
            if source is not None:
                self._clear_pending_entry_reservations_for_symbol(symbol)
                return source

        # Fallback: consult H05 directly in case active_positions is still
        # empty at startup (race between hydration and first D31 tick).
        session_db = getattr(self._live_engine, "_session_db", None)
        if session_db is not None:
            selector_names: list[str] = []
            has_active_marker = getattr(session_db, "has_active_paper_session_marker", None)
            active_session_marker: bool | None = None
            if callable(has_active_marker):
                try:
                    active_session_marker = bool(has_active_marker())
                except Exception:
                    active_session_marker = None

            get_active_open = getattr(session_db, "get_active_paper_open_positions", None)
            get_resume_open = getattr(session_db, "get_resume_eligible_open_positions", None)
            get_open = getattr(session_db, "get_open_positions", None)

            if active_session_marker is True:
                if callable(get_active_open):
                    selector_names.append("get_active_paper_open_positions")
                if callable(get_resume_open):
                    selector_names.append("get_resume_eligible_open_positions")
            elif active_session_marker is False:
                if callable(get_resume_open):
                    selector_names.append("get_resume_eligible_open_positions")
            else:
                if callable(get_active_open):
                    selector_names.append("get_active_paper_open_positions")
                if callable(get_resume_open):
                    selector_names.append("get_resume_eligible_open_positions")

            if not selector_names and callable(get_open):
                selector_names.append("get_open_positions")

            for selector_name in selector_names:
                get_rows = getattr(session_db, selector_name, None)
                if not callable(get_rows):
                    continue
                try:
                    rows = get_rows()
                except Exception:
                    continue

                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    row_qty = int(row.get("quantity") or 0)
                    if row_qty == 0:
                        continue
                    row_strategy = str(row.get("strategy") or "").strip().lower()
                    if current_strategy and row_strategy and row_strategy != current_strategy:
                        continue
                    row_symbol = str(row.get("symbol") or "").strip()
                    row_underlying = self._extract_option_underlying(row_symbol)
                    if (
                        row_symbol not in lookup_symbols
                        and row_underlying not in lookup_symbols
                    ):
                        continue
                    row_origin = str(row.get("_paper_open_origin") or "").strip().lower()
                    self._clear_pending_entry_reservations_for_symbol(symbol)
                    if (
                        selector_name == "get_resume_eligible_open_positions"
                        or row_origin == "carryover"
                    ):
                        return "persisted_carryover"
                    return "h05_open_position"

        return None

    def _has_duplicate_open_position(
        self,
        symbol: str,
        strategy_id: Any,
        side: Any,
        include_pending: bool = True,
    ) -> bool:
        """Return True when the live engine already holds the same open entry."""
        return (
            self._get_duplicate_open_position_source(
                symbol,
                strategy_id,
                side,
                include_pending=include_pending,
            )
            is not None
        )

    def _dispatch_approved_signal(self, signal: Any) -> None:
        """Convert a risk-approved strategy signal to an order and submit it.

        Execution routing (in priority order):

        1. **Mid-price walk** — if the signal carries ``bid`` + ``ask`` fields
           *and* an ``OrderManager`` is wired via ``set_order_manager()``, the
           order is submitted as a limit at the mid-price and walked toward the
           natural price in $0.01 increments every 5 s (up to 10 ticks / 5 %
           slippage budget).  This eliminates full-spread market-order slippage
           on every single-leg options entry.

        2. **Market order fallback** — if no quote is available on the signal or
           no ``OrderManager`` is wired, the order is sent as a plain market
           order through ``self._live_engine.execute_order()``.

        If neither a live engine nor an order manager is wired the signal is
        silently consumed — the risk gate has already validated it.

        Args:
            signal: Signal dict (or object with ``to_dict()``) from the strategy.
        """
        if self._live_engine is None and self._order_manager is None:
            self._clear_pending_entry_reservation(
                self._signal_value(signal, "symbol", ""),
                self._signal_value(
                    signal,
                    "strategy_id",
                    self._signal_value(signal, "strategy_name", ""),
                ),
            )
            pivot_context = self._format_pivot_log_context(
                self._extract_pivot_signal_payload(signal)
            )
            self.logger.error(
                "D31: Approved signal dropped — no execution engine wired. %s signal=%s",
                pivot_context,
                signal,
            )
            self._record_signal_drop("dispatch", "no_execution_engine", signal=signal)
            return

        try:
            # Normalise signal to dict
            if isinstance(signal, dict):
                raw = signal.get("signal", signal)
            elif hasattr(signal, "to_dict"):
                raw = signal.to_dict()
            else:
                raw = signal

            raw_signal_payload: dict[str, Any] = {}
            if isinstance(raw, dict):
                raw_signal_payload = raw
            elif hasattr(raw, "to_dict"):
                try:
                    candidate_payload = raw.to_dict()
                except Exception:
                    candidate_payload = None
                if isinstance(candidate_payload, dict):
                    raw_signal_payload = candidate_payload

            pivot_context = self._format_pivot_log_context(
                self._extract_pivot_signal_payload(raw_signal_payload or signal)
            )

            def _get(key: str, default: Any = None) -> Any:
                if raw_signal_payload:
                    return raw_signal_payload.get(key, default)
                if isinstance(raw, dict):
                    return raw.get(key, default)
                return getattr(raw, key, default)

            symbol = _get("symbol", "")
            quantity = int(_get("quantity", 0))
            strategy_id = _get("strategy_id", _get("strategy_name", ""))

            if not symbol or not quantity:
                self._clear_pending_entry_reservation(symbol, strategy_id)
                self.logger.warning(
                    "Cannot dispatch approved signal — missing symbol or quantity: %s | %s",
                    pivot_context,
                    signal,
                )
                self._record_signal_drop("dispatch", "invalid_signal_payload", signal=signal)
                return

            side = str(_get("action", _get("side", "buy"))).lower()
            bid = float(_get("bid", 0.0) or 0.0)
            ask = float(_get("ask", 0.0) or 0.0)
            option_symbol = str(_get("option_symbol", "") or "")
            is_paper_run = str(self._audit_run_mode or "").strip().lower() == "paper"
            symbol_option_details = self._parse_occ_option_symbol(symbol)

            if (
                is_paper_run
                and symbol_option_details
                and self._is_entry_action(side)
                and str(symbol_option_details.get("underlying") or "").strip().upper() == "SPY"
            ):
                self._clear_pending_entry_reservation(symbol, strategy_id)
                detail = f"symbol={symbol};policy=spxw_only;blocked_underlying=SPY"
                self.logger.warning(
                    "Paper entry blocked by SPXW-only option policy: %s | %s",
                    detail,
                    pivot_context,
                )
                self._record_signal_drop(
                    "dispatch",
                    "paper_spy_option_entry_blocked",
                    signal=signal,
                    detail=detail,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=detail,
                )
                return

            duplicate_source = self._get_duplicate_open_position_source(
                symbol,
                strategy_id,
                side,
                include_pending=False,
            )
            if duplicate_source is not None:
                duplicate_detail = (
                    f"symbol={symbol};strategy={strategy_id};duplicate_source={duplicate_source}"
                )
                self._log_duplicate_entry_warning_if_due(
                    symbol,
                    strategy_id,
                    pivot_context,
                    duplicate_source=duplicate_source,
                    stage="dispatch",
                )
                self._record_signal_drop(
                    "dispatch",
                    "duplicate_open_position",
                    signal=signal,
                    detail=duplicate_detail,
                    update_dispatch_state=False,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=duplicate_detail,
                )
                return
            self._clear_duplicate_entry_warning_state(symbol, strategy_id)

            normalized_strategy_id = str(strategy_id or "").strip().lower().replace("-", "_")
            normalized_strategy_key = self._normalise_strategy_type_for_entry_gate(strategy_id)
            is_explicit_close_signal = self._is_closing_trade_signal(raw_signal_payload or signal)
            symbol_is_option_leg = bool(self._parse_occ_option_symbol(symbol))
            reserved_pending_exit = False
            if is_explicit_close_signal:
                reserved_pending_exit = self._reserve_pending_exit(symbol, strategy_id)
                if not reserved_pending_exit:
                    self.logger.debug(
                        "Duplicate close suppressed while exit remains in flight: symbol=%s strategy=%s",
                        symbol,
                        strategy_id,
                    )
                    return
            if (
                is_paper_run
                and "iron_condor" in normalized_strategy_id
                and not (is_explicit_close_signal and symbol_is_option_leg)
            ):
                self._dispatch_paper_iron_condor(
                    signal=signal,
                    raw_signal=raw_signal_payload,
                    symbol=str(symbol),
                    quantity=quantity,
                    strategy_id=strategy_id,
                    pivot_context=pivot_context,
                )
                return

            if (
                is_paper_run
                and normalized_strategy_key in {"bullish_strangle", "jade_lizard_zero", "put_credit_spread_7", "zero_hft"}
                and not symbol_is_option_leg
            ):
                self._dispatch_paper_serialized_multileg(
                    signal=signal,
                    raw_signal=raw_signal_payload,
                    symbol=str(symbol),
                    quantity=quantity,
                    strategy_id=strategy_id,
                    pivot_context=pivot_context,
                )
                return

            if (
                is_paper_run
                and normalized_strategy_key in {"butterfly", "broken_wing_butterfly"}
                and not symbol_is_option_leg
            ):
                self._dispatch_paper_butterfly_family(
                    signal=signal,
                    raw_signal=raw_signal_payload,
                    symbol=str(symbol),
                    quantity=quantity,
                    strategy_id=strategy_id,
                    pivot_context=pivot_context,
                )
                return

            if (
                is_paper_run
                and normalized_strategy_key == "iron_butterfly"
                and not symbol_is_option_leg
            ):
                self._dispatch_paper_iron_butterfly(
                    signal=signal,
                    raw_signal=raw_signal_payload,
                    symbol=str(symbol),
                    quantity=quantity,
                    strategy_id=strategy_id,
                    pivot_context=pivot_context,
                )
                return

            if (
                is_paper_run
                and self._paper_calendar_spread_routing_flag_enabled()
                and normalized_strategy_key in {"calendarspread", "calendar_spread"}
                and not symbol_is_option_leg
            ):
                self._dispatch_paper_calendar_spread(
                    signal=signal,
                    raw_signal=raw_signal_payload,
                    symbol=str(symbol),
                    quantity=quantity,
                    strategy_id=strategy_id,
                    pivot_context=pivot_context,
                )
                return

            if bid > 0.0 and ask > 0.0 and self._order_manager is not None and is_paper_run:
                self.logger.info(
                    "Paper mode: bypassing mid-price walk and using engine execution path "
                    "(symbol=%s qty=%d) | %s",
                    symbol,
                    quantity,
                    pivot_context,
                )
                if not self._paper_midwalk_bypass_marker_emitted:
                    self.emit_decision_audit_marker(
                        "paper_midwalk_bypassed",
                        detail=(
                            "Paper mode disables OrderManager mid-walk; "
                            "dispatch falls back to engine/PaperBroker path"
                        ),
                    )
                    self._paper_midwalk_bypass_marker_emitted = True

            # ── Path 1: mid-price walk ────────────────────────────────────────
            if bid > 0.0 and ask > 0.0 and self._order_manager is not None and not is_paper_run:
                walk_result = self._order_manager.submit_limit_with_walk(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    bid=bid,
                    ask=ask,
                    option_symbol=option_symbol or None,
                    strategy_name=strategy_id or None,
                )
                walk_success = bool(getattr(walk_result, "success", False))
                if not walk_success and isinstance(walk_result, dict):
                    walk_success = bool(walk_result.get("success", False))
                walk_message = getattr(walk_result, "message", None)
                if walk_message is None and isinstance(walk_result, dict):
                    walk_message = walk_result.get("message")
                if walk_message is None:
                    walk_message = str(walk_result)
                walk_error_code = getattr(walk_result, "error_code", None)
                if walk_error_code is None and isinstance(walk_result, dict):
                    walk_error_code = walk_result.get("error_code")

                if walk_success:
                    self.logger.info(
                        "MidWalk filled: symbol=%s qty=%d %s | %s",
                        symbol,
                        quantity,
                        walk_message,
                        pivot_context,
                    )
                    self._record_signal_dispatch_outcome_safe("dispatch_submitted", signal=signal)
                else:
                    self._clear_pending_entry_reservation(symbol, strategy_id)
                    if reserved_pending_exit:
                        self._clear_pending_exit_reservation(symbol, strategy_id)
                    self.logger.warning(
                        "MidWalk did not fill: symbol=%s reason=%s error=%s | %s",
                        symbol,
                        walk_message,
                        walk_error_code,
                        pivot_context,
                    )
                    detail = str(walk_message or "")
                    if walk_error_code:
                        detail = f"{detail} (error={walk_error_code})" if detail else f"error={walk_error_code}"
                    self._record_signal_dispatch_outcome_safe(
                        "dispatch_rejected",
                        signal=signal,
                        detail=detail,
                    )
                return  # Mid-price path handled — do not send a market order

            # ── Path 2: market order via live engine ─────────────────────────
            if self._live_engine is None:
                self._clear_pending_entry_reservation(symbol, strategy_id)
                if reserved_pending_exit:
                    self._clear_pending_exit_reservation(symbol, strategy_id)
                self.logger.warning(
                    "No live engine and no bid/ask quote — signal dropped: symbol=%s | %s",
                    symbol,
                    pivot_context,
                )
                self._record_signal_drop("dispatch", "no_live_engine_for_market_fallback", signal=signal)
                return

            order: dict[str, Any] = {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": str(_get("order_type", "market")).lower(),
                "price": _get("price"),
                "strategy_id": strategy_id,
            }

            result = self._live_engine.execute_order(order)

            status = result.get("status", "unknown") if isinstance(result, dict) else str(result)
            if status in ("rejected", "error"):
                self._clear_pending_entry_reservation(symbol, strategy_id)
                if reserved_pending_exit:
                    self._clear_pending_exit_reservation(symbol, strategy_id)
                reason = result.get("reason", "") if isinstance(result, dict) else ""
                self.logger.warning(
                    "Market order rejected by live engine: symbol=%s reason=%s | %s",
                    symbol,
                    reason,
                    pivot_context,
                )
                self._record_signal_dispatch_outcome_safe(
                    "dispatch_rejected",
                    signal=signal,
                    detail=reason or status,
                )
            else:
                self.logger.info(
                    "Market order dispatched: symbol=%s qty=%d status=%s | %s",
                    symbol,
                    quantity,
                    status,
                    pivot_context,
                )
                self._record_signal_dispatch_outcome_safe("dispatch_submitted", signal=signal)

        except Exception as exc:
            self._clear_pending_entry_reservation(
                self._signal_value(signal, "symbol", ""),
                self._signal_value(
                    signal,
                    "strategy_id",
                    self._signal_value(signal, "strategy_name", ""),
                ),
            )
            if 'reserved_pending_exit' in locals() and reserved_pending_exit:
                self._clear_pending_exit_reservation(
                    self._signal_value(signal, "symbol", ""),
                    self._signal_value(
                        signal,
                        "strategy_id",
                        self._signal_value(signal, "strategy_name", ""),
                    ),
                )
            self.logger.error(
                "Error dispatching approved signal: %s", exc, exc_info=True
            )
            self._record_signal_drop("dispatch", "dispatch_exception", signal=signal, detail=str(exc))


    def _on_risk_alert(self, event: Event):
        """Handle risk alert events"""
        if event.data.get('severity') == 'critical':
            # Implement emergency procedures
            self.logger.warning("🚨 Critical risk alert: %s", event.data)

    def _should_rebalance(self) -> bool:
        """Check if portfolio rebalancing is needed"""
        # Never rebalance outside regular market hours (Mon–Fri 09:30–16:00 ET)
        now_et = _d31_now_et()
        if now_et.weekday() >= 5:  # Saturday or Sunday
            return False
        t = now_et.time()
        if not (dt_time(9, 30) <= t <= dt_time(16, 0)):
            return False
        # Time-based rebalancing
        time_since_rebalance = datetime.now(UTC) - self.last_rebalance
        # Performance-driven rebalancing
        # (Implementation would check allocation drift, performance changes, etc.)
        return time_since_rebalance > timedelta(minutes=REBALANCE_FREQUENCY_MINUTES)

    def _determine_rebalance_reason(self) -> RebalanceReason:
        """Determine the reason for rebalancing"""
        # Simplified logic - would be more sophisticated in practice
        time_since_rebalance = datetime.now(UTC) - self.last_rebalance
        if time_since_rebalance > timedelta(minutes=REBALANCE_FREQUENCY_MINUTES):
            return RebalanceReason.SCHEDULED

        return RebalanceReason.PERFORMANCE_DRIFT

    def _update_portfolio_metrics(self):
        """Update portfolio-level metrics"""
        try:
            # C1 (v18): snapshot to avoid RuntimeError from concurrent add/remove.
            with self._strategies_lock:
                _alloc_vals = list(self.strategy_allocations.values())
                _active_strategies = list(self.active_strategies.items())
            _perf_history = list(self.performance_history)
            # Calculate total allocated capital
            total_allocated = sum(alloc.allocated_capital for alloc in _alloc_vals)

            # Update basic metrics
            self.portfolio_metrics.allocated_capital = total_allocated
            self.portfolio_metrics.available_capital = self.base_capital - total_allocated
            self.portfolio_metrics.active_strategies = len(self.active_strategies)

            # Calculate portfolio PnL (sum of all strategy PnL)
            total_pnl = 0.0
            for _strategy_id, strategy in _active_strategies:
                strategy_pnl = getattr(strategy, 'total_pnl', 0.0)
                total_pnl += strategy_pnl

            self.portfolio_metrics.total_pnl = total_pnl

            # Calculate other metrics if we have enough data
            if len(_perf_history) > 10:
                returns: list[float] = []
                capital_base = self.base_capital if self.base_capital > 0 else 1.0

                for entry in _perf_history:
                    if not isinstance(entry, dict):
                        continue

                    if 'daily_return' in entry:
                        value = entry.get('daily_return')
                    elif 'daily_pnl' in entry:
                        value = float(entry.get('daily_pnl', 0.0)) / capital_base
                    else:
                        continue

                    try:
                        returns.append(float(value))
                    except (TypeError, ValueError):
                        continue

                if returns and len(returns) > 1:
                    self.portfolio_metrics.portfolio_sharpe = self._calculate_sharpe_ratio(returns)
                    self.portfolio_metrics.max_drawdown = self._calculate_max_drawdown(returns)

        except Exception as e:
            self.logger.error("Error updating portfolio metrics: %s", e, exc_info=True)

    def _calculate_sharpe_ratio(self, returns: list[float]) -> float:
        """Calculate portfolio Sharpe ratio"""
        try:
            if not returns or len(returns) < 2:
                return 0.0

            mean_return = np.mean(returns)
            std_return = np.std(returns)

            if std_return == 0:
                return 0.0

            # Annualized Sharpe ratio
            return (mean_return * 252) / (std_return * np.sqrt(252))

        except Exception as e:
            self.logger.error("Error calculating Sharpe ratio: %s", e, exc_info=True)
            return 0.0

    def _calculate_max_drawdown(self, returns: list[float]) -> float:
        """Calculate maximum drawdown"""
        try:
            if not returns:
                return 0.0

            cumulative = np.cumprod(1 + np.array(returns))
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max

            return abs(np.min(drawdown))

        except Exception as e:
            self.logger.error("Error calculating max drawdown: %s", e, exc_info=True)
            return 0.0

    # ==========================================================================
    # RAY DISTRIBUTED COMPUTING (Phase 3)
    # ==========================================================================

    def execute_strategies_distributed(
        self,
        market_data: dict[str, Any],
        strategy_configs: list[dict[str, Any]] | None = None,
        num_cpus: int | None = None,
    ) -> dict[str, Any]:
        """
        Execute multiple strategies in parallel using Ray actors.

        Each strategy evaluates independently on a Ray worker,
        enabling true parallel strategy execution.

        Args:
            market_data: Current market data for evaluation.
            strategy_configs: List of strategy configurations to execute.
            num_cpus: Number of CPUs to allocate.

        Returns:
            Aggregated results from all strategy executions.
        """
        try:
            import ray
        except ImportError:
            self.logger.warning("Ray not available for distributed strategy execution", exc_info=True)  # noqa: E501
            return {'status': 'failed', 'reason': 'Ray not installed'}

        import multiprocessing as mproc
        if not ray.is_initialized():
            ray.init(num_cpus=num_cpus or mproc.cpu_count(), ignore_reinit_error=True)

        if strategy_configs is None:
            strategy_configs = [
                {'strategy_id': sid, 'name': s.get('name', sid)}
                for sid, s in self.strategies.items()
            ] if hasattr(self, 'strategies') else []

        if not strategy_configs:
            return {'status': 'completed', 'results': [], 'n_strategies': 0}

        market_ref = ray.put(market_data)

        @ray.remote
        def _execute_strategy(market_ref, config: dict) -> dict:
            """Execute a single strategy on a Ray worker."""
            import numpy as _np
            import time as _time

            start = _time.time()
            _np.random.seed(hash(config.get('strategy_id', '')) % (2**32))

            market = market_ref
            market.get('price', 450)
            market.get('iv', 0.20)

            # Simulate strategy signal generation
            signal_strength = float(_np.random.uniform(-1, 1))
            confidence = float(_np.random.uniform(0.3, 0.95))

            return {
                'strategy_id': config.get('strategy_id', 'unknown'),
                'strategy_name': config.get('name', 'unknown'),
                'signal': signal_strength,
                'confidence': confidence,
                'recommended_action': 'buy' if signal_strength > 0.3 else ('sell' if signal_strength < -0.3 else 'hold'),  # noqa: E501
                'execution_time': _time.time() - start,
                'status': 'completed',
            }

        self.logger.info("Ray strategy execution: %s strategies", len(strategy_configs))

        futures = [_execute_strategy.remote(market_ref, cfg) for cfg in strategy_configs]
        results = ray.get(futures)

        return {
            'status': 'completed',
            'n_strategies': len(results),
            'results': results,
            'consensus_signal': float(np.mean([r['signal'] for r in results if r.get('status') == 'completed'])),  # noqa: E501
            'mean_confidence': float(np.mean([r['confidence'] for r in results if r.get('status') == 'completed'])),  # noqa: E501
        }

    # --------------------------------------------------------------------------
    # RISKFOLIO-LIB: STRATEGY WEIGHT OPTIMIZATION
    # --------------------------------------------------------------------------

    def optimize_strategy_weights_riskfolio(
        self,
        strategy_returns: pd.DataFrame,
        risk_measure: str = 'CVaR',
        objective: str = 'max_sharpe',
    ) -> dict[str, Any]:
        """
        Optimize strategy weights using RiskFolio-Lib with risk constraints.

        Replaces equal-weight or heuristic allocation with institutional-grade
        optimization using CVaR, HRP, or risk parity.

        Args:
            strategy_returns: DataFrame of strategy returns (columns = strategies).
            risk_measure: Risk measure ('MV', 'CVaR', 'CDaR', 'MDD').
            objective: Optimization objective ('max_sharpe', 'min_risk', 'risk_parity').

        Returns:
            Optimized strategy weights and portfolio statistics.
        """
        try:
            import riskfolio as rp
        except ImportError:
            self.logger.warning("riskfolio not installed — using equal weights", exc_info=True)
            n = strategy_returns.shape[1]
            return {'weights': {col: 1.0 / n for col in strategy_returns.columns},
                    '_backend': 'fallback'}

        port = rp.Portfolio(returns=strategy_returns)
        port.assets_stats(method_mu='hist', method_cov='ledoit_wolf')

        weights = None
        if objective == 'risk_parity':
            weights = port.rp_optimization(
                model='Classic', rm=risk_measure, rf=0.05 / 252, b=None)
        else:
            obj_map = {'max_sharpe': 'Sharpe', 'min_risk': 'MinRisk'}
            rp_obj = obj_map.get(objective, 'Sharpe')
            weights = port.optimization(
                model='Classic', rm=risk_measure, obj=rp_obj, rf=0.05 / 252)

        if weights is not None and not weights.empty:
            weight_dict = {col: float(weights.loc[col].iloc[0]) for col in weights.index}
            self.logger.info(f"RiskFolio strategy weights ({objective}/{risk_measure}): "
                             f"{weight_dict}")
            return {
                'weights': weight_dict,
                'objective': objective,
                'risk_measure': risk_measure,
                '_backend': 'riskfolio',
            }

        n = strategy_returns.shape[1]
        return {'weights': {col: 1.0 / n for col in strategy_returns.columns},
                '_backend': 'fallback'}

# ==============================================================================
# PYQT6 ORCHESTRATOR DASHBOARD
# ==============================================================================

_IS_TEST_MODE = str(os.environ.get("SPYDER_TEST_MODE", "")).lower() == "true"
_DASHBOARD_BASE = object if _IS_TEST_MODE else QWidget
_DASHBOARD_SIGNAL = (lambda *args, **kwargs: None) if _IS_TEST_MODE else Signal


class StrategyOrchestratorDashboard(_DASHBOARD_BASE):
    """
    PyQt6 dashboard for Strategy Orchestrator monitoring and control.

    Provides comprehensive real-time monitoring of:
    - Portfolio allocation and performance
    - Strategy performance attribution
    - Market regime analysis
    - Risk monitoring and alerts
    - Manual orchestration controls
    """

    # Qt signals
    portfolioUpdated = _DASHBOARD_SIGNAL(dict)
    rebalanceCompleted = _DASHBOARD_SIGNAL(str)

    def __init__(self, orchestrator: StrategyOrchestrator | None = None):
        super().__init__()

        self.orchestrator = orchestrator

        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)

        # Data models for tables
        self.strategy_model = None
        self.performance_model = None

        # Setup UI
        self.setup_ui()
        self.setup_monitoring()

        # Connect orchestrator if available
        if self.orchestrator:
            self.setup_orchestrator_integration()

    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout()

        # Header with control buttons
        self.create_header_section(main_layout)

        # Main content with tabs
        self.create_main_content(main_layout)

        # Status bar
        self.create_status_bar(main_layout)

        self.setLayout(main_layout)
        self.setMinimumSize(1200, 800)
        self.setWindowTitle("SPYDER - Strategy Orchestrator Dashboard")

    def create_header_section(self, layout):
        """Create header with controls"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("🎯 SPYDER Strategy Orchestrator")
        title_font = QFont()
        title_font.setPointSize(16)
        title_label.setFont(title_font)

        # Status indicator
        self.status_label = QLabel("🔄 Initializing...")
        status_font = QFont()
        status_font.setPointSize(14)
        self.status_label.setFont(status_font)

        # Control buttons
        self.start_btn = QPushButton("🚀 Start Orchestration")
        self.start_btn.clicked.connect(self.start_orchestration)

        self.stop_btn = QPushButton("🛑 Stop Orchestration")
        self.stop_btn.clicked.connect(self.stop_orchestration)

        self.rebalance_btn = QPushButton("⚖️ Rebalance Now")
        self.rebalance_btn.clicked.connect(self.manual_rebalance)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.start_btn)
        header_layout.addWidget(self.stop_btn)
        header_layout.addWidget(self.rebalance_btn)

        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)

    def create_main_content(self, layout):
        """Create main content with tabs"""
        self.tab_widget = QTabWidget()

        # Portfolio Overview
        self.create_portfolio_overview_tab()

        # Strategy Performance
        self.create_strategy_performance_tab()

        # Market Regime
        self.create_market_regime_tab()

        # Risk Management
        self.create_risk_management_tab()

        # Configuration
        self.create_configuration_tab()

        layout.addWidget(self.tab_widget)

    def create_portfolio_overview_tab(self):
        """Create portfolio overview tab"""
        overview_widget = QWidget()
        layout = QVBoxLayout()

        # Portfolio metrics
        metrics_group = QGroupBox("📊 Portfolio Metrics")
        metrics_layout = QHBoxLayout()

        # Left column metrics
        left_metrics = QVBoxLayout()
        self.total_capital_label = QLabel("Total Capital: $0")
        self.allocated_capital_label = QLabel("Allocated: $0")
        self.total_pnl_label = QLabel("Total P&L: $0")
        self.daily_pnl_label = QLabel("Daily P&L: $0")

        left_metrics.addWidget(self.total_capital_label)
        left_metrics.addWidget(self.allocated_capital_label)
        left_metrics.addWidget(self.total_pnl_label)
        left_metrics.addWidget(self.daily_pnl_label)

        # Right column metrics
        right_metrics = QVBoxLayout()
        self.sharpe_ratio_label = QLabel("Sharpe Ratio: 0.00")
        self.max_drawdown_label = QLabel("Max Drawdown: 0.0%")
        self.active_strategies_label = QLabel("Active Strategies: 0")
        self.win_rate_label = QLabel("Win Rate: 0.0%")

        right_metrics.addWidget(self.sharpe_ratio_label)
        right_metrics.addWidget(self.max_drawdown_label)
        right_metrics.addWidget(self.active_strategies_label)
        right_metrics.addWidget(self.win_rate_label)

        metrics_layout.addLayout(left_metrics)
        metrics_layout.addLayout(right_metrics)
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # Allocation chart placeholder
        allocation_group = QGroupBox("📈 Strategy Allocations")
        allocation_layout = QVBoxLayout()

        # Create matplotlib figure for allocation pie chart
        self.allocation_figure = Figure(figsize=(8, 6))
        self.allocation_canvas = FigureCanvas(self.allocation_figure)
        allocation_layout.addWidget(self.allocation_canvas)

        allocation_group.setLayout(allocation_layout)
        layout.addWidget(allocation_group)

        overview_widget.setLayout(layout)
        self.tab_widget.addTab(overview_widget, "Portfolio Overview")

    def create_strategy_performance_tab(self):
        """Create strategy performance tab"""
        performance_widget = QWidget()
        layout = QVBoxLayout()

        # Strategy table
        strategies_group = QGroupBox("📋 Active Strategies")
        strategies_layout = QVBoxLayout()

        self.strategies_table = QTableWidget()
        self.strategies_table.setColumnCount(8)
        self.strategies_table.setHorizontalHeaderLabels([
            'Strategy', 'Type', 'Allocation', 'Capital', 'P&L', 'Performance Score', 'Health', 'Status'  # noqa: E501
        ])

        header = self.strategies_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        strategies_layout.addWidget(self.strategies_table)

        # Strategy controls
        controls_layout = QHBoxLayout()

        self.pause_strategy_btn = QPushButton("⏸️ Pause Strategy")
        self.resume_strategy_btn = QPushButton("▶️ Resume Strategy")
        self.remove_strategy_btn = QPushButton("❌ Remove Strategy")

        controls_layout.addWidget(self.pause_strategy_btn)
        controls_layout.addWidget(self.resume_strategy_btn)
        controls_layout.addWidget(self.remove_strategy_btn)
        controls_layout.addStretch()

        strategies_layout.addLayout(controls_layout)
        strategies_group.setLayout(strategies_layout)
        layout.addWidget(strategies_group)

        # Performance chart
        performance_group = QGroupBox("📈 Performance Chart")
        performance_layout = QVBoxLayout()

        self.performance_figure = Figure(figsize=(12, 6))
        self.performance_canvas = FigureCanvas(self.performance_figure)
        performance_layout.addWidget(self.performance_canvas)

        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)

        performance_widget.setLayout(layout)
        self.tab_widget.addTab(performance_widget, "Strategy Performance")

    def create_market_regime_tab(self):
        """Create market regime analysis tab"""
        regime_widget = QWidget()
        layout = QVBoxLayout()

        # Current regime
        current_regime_group = QGroupBox("🌡️ Current Market Regime")
        regime_layout = QHBoxLayout()

        self.current_regime_label = QLabel("Regime: Unknown")
        self.regime_confidence_label = QLabel("Confidence: 0%")
        self.vix_level_label = QLabel("VIX: 0.0")
        self.trend_strength_label = QLabel("Trend: 0.0")

        regime_layout.addWidget(self.current_regime_label)
        regime_layout.addWidget(self.regime_confidence_label)
        regime_layout.addWidget(self.vix_level_label)
        regime_layout.addWidget(self.trend_strength_label)

        current_regime_group.setLayout(regime_layout)
        layout.addWidget(current_regime_group)

        # Regime strategy weights
        weights_group = QGroupBox("⚖️ Optimal Strategy Weights for Current Regime")
        weights_layout = QVBoxLayout()

        self.regime_weights_table = QTableWidget()
        self.regime_weights_table.setColumnCount(3)
        self.regime_weights_table.setHorizontalHeaderLabels(['Strategy Type', 'Optimal Weight', 'Current Weight'])  # noqa: E501

        weights_layout.addWidget(self.regime_weights_table)
        weights_group.setLayout(weights_layout)
        layout.addWidget(weights_group)

        regime_widget.setLayout(layout)
        self.tab_widget.addTab(regime_widget, "Market Regime")

    def create_risk_management_tab(self):
        """Create risk management tab"""
        risk_widget = QWidget()
        layout = QVBoxLayout()

        # Risk metrics
        risk_metrics_group = QGroupBox("⚠️ Risk Metrics")
        risk_layout = QHBoxLayout()

        self.portfolio_var_label = QLabel("Portfolio VaR: 0.0%")
        self.concentration_label = QLabel("Max Concentration: 0.0%")
        self.correlation_label = QLabel("Avg Correlation: 0.00")

        risk_layout.addWidget(self.portfolio_var_label)
        risk_layout.addWidget(self.concentration_label)
        risk_layout.addWidget(self.correlation_label)

        risk_metrics_group.setLayout(risk_layout)
        layout.addWidget(risk_metrics_group)

        # Strategy conflicts
        conflicts_group = QGroupBox("⚡ Strategy Conflicts")
        conflicts_layout = QVBoxLayout()

        self.conflicts_list = QListWidget()
        conflicts_layout.addWidget(self.conflicts_list)

        conflicts_group.setLayout(conflicts_layout)
        layout.addWidget(conflicts_group)

        risk_widget.setLayout(layout)
        self.tab_widget.addTab(risk_widget, "Risk Management")

    def create_configuration_tab(self):
        """Create configuration tab"""
        config_widget = QWidget()
        layout = QVBoxLayout()

        # Orchestration mode
        mode_group = QGroupBox("🎛️ Orchestration Configuration")
        mode_layout = QVBoxLayout()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([mode.value for mode in OrchestrationMode])
        mode_layout.addWidget(QLabel("Orchestration Mode:"))
        mode_layout.addWidget(self.mode_combo)

        self.allocation_combo = QComboBox()
        self.allocation_combo.addItems([method.value for method in AllocationMethod])
        mode_layout.addWidget(QLabel("Allocation Method:"))
        mode_layout.addWidget(self.allocation_combo)

        self.rebalance_freq_spin = QSpinBox()
        self.rebalance_freq_spin.setRange(5, 120)
        self.rebalance_freq_spin.setValue(30)
        self.rebalance_freq_spin.setSuffix(" minutes")
        mode_layout.addWidget(QLabel("Rebalance Frequency:"))
        mode_layout.addWidget(self.rebalance_freq_spin)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Risk limits
        limits_group = QGroupBox("🛡️ Risk Limits")
        limits_layout = QVBoxLayout()

        self.max_allocation_spin = QDoubleSpinBox()
        self.max_allocation_spin.setRange(0.1, 0.8)
        self.max_allocation_spin.setValue(0.4)
        self.max_allocation_spin.setSuffix("%")
        limits_layout.addWidget(QLabel("Max Strategy Allocation:"))
        limits_layout.addWidget(self.max_allocation_spin)

        self.var_limit_spin = QDoubleSpinBox()
        self.var_limit_spin.setRange(0.01, 0.1)
        self.var_limit_spin.setValue(0.02)
        self.var_limit_spin.setSuffix("%")
        limits_layout.addWidget(QLabel("Portfolio VaR Limit:"))
        limits_layout.addWidget(self.var_limit_spin)

        limits_group.setLayout(limits_layout)
        layout.addWidget(limits_group)

        config_widget.setLayout(layout)
        self.tab_widget.addTab(config_widget, "Configuration")

    def create_status_bar(self, layout):
        """Create status bar"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout()

        self.status_bar_label = QLabel("Ready")
        self.last_update_label = QLabel("")

        status_layout.addWidget(QLabel("Status:"))
        status_layout.addWidget(self.status_bar_label)
        status_layout.addStretch()
        status_layout.addWidget(self.last_update_label)

        status_frame.setLayout(status_layout)
        layout.addWidget(status_frame)

    def setup_monitoring(self):
        """Setup monitoring timer"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(2000)  # Update every 2 seconds

        # Initial update
        self.update_display()

    def setup_orchestrator_integration(self):
        """Setup integration with orchestrator"""
        # Connect signals and setup callbacks
        pass

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================

    def update_display(self):
        """Update all dashboard displays"""
        if not self.orchestrator:
            return

        try:
            # Get portfolio status
            status = self.orchestrator.get_portfolio_status()

            # Update status indicator
            if status.get('orchestration_active'):
                self.status_label.setText("✅ Running")
                self.status_label.setStyleSheet("color: green; font-weight: normal;")
            else:
                self.status_label.setText("⏸️ Stopped")
                self.status_label.setStyleSheet("color: red; font-weight: normal;")

            # Update portfolio metrics
            self.update_portfolio_metrics(status)

            # Update strategy table
            self.update_strategy_table()

            # Update market regime
            self.update_market_regime_display()

            # Update charts
            self.update_allocation_chart()

            # Update status bar
            self.last_update_label.setText(f"Updated: {datetime.now(UTC).strftime('%H:%M:%S')}")

        except Exception as e:
            self.logger.error("Error updating dashboard: %s", e, exc_info=True)

    def update_portfolio_metrics(self, status: dict[str, Any]):
        """Update portfolio metrics display"""
        try:
            self.total_capital_label.setText(f"Total Capital: ${status.get('total_capital', 0):,.2f}")  # noqa: E501
            self.allocated_capital_label.setText(f"Allocated: ${status.get('allocated_capital', 0):,.2f}")  # noqa: E501
            self.total_pnl_label.setText(f"Total P&L: ${status.get('total_pnl', 0):,.2f}")
            self.daily_pnl_label.setText(f"Daily P&L: ${status.get('daily_pnl', 0):,.2f}")

            self.sharpe_ratio_label.setText(f"Sharpe Ratio: {status.get('portfolio_sharpe', 0):.2f}")  # noqa: E501
            self.max_drawdown_label.setText(f"Max Drawdown: {status.get('max_drawdown', 0):.1%}")
            self.active_strategies_label.setText(f"Active Strategies: {status.get('active_strategies', 0)}")  # noqa: E501

        except Exception as e:
            self.logger.error("Error updating portfolio metrics: %s", e, exc_info=True)

    def update_strategy_table(self):
        """Update strategy performance table"""
        if not self.orchestrator:
            return

        try:
            performance_data = self.orchestrator.get_strategy_performance_attribution()

            if performance_data.empty:
                return

            # Update table
            self.strategies_table.setRowCount(len(performance_data))

            for row, (_, data) in enumerate(performance_data.iterrows()):
                self.strategies_table.setItem(row, 0, QTableWidgetItem(data['strategy_name']))
                self.strategies_table.setItem(row, 1, QTableWidgetItem(data['strategy_type']))
                self.strategies_table.setItem(row, 2, QTableWidgetItem(f"{data['allocation']:.1%}"))
                self.strategies_table.setItem(row, 3, QTableWidgetItem(f"${data['allocated_capital']:,.0f}"))  # noqa: E501
                self.strategies_table.setItem(row, 4, QTableWidgetItem(f"${data['strategy_pnl']:,.2f}"))  # noqa: E501
                self.strategies_table.setItem(row, 5, QTableWidgetItem(f"{data['performance_score']:.2f}"))  # noqa: E501
                self.strategies_table.setItem(row, 6, QTableWidgetItem(f"{data['health_score']:.2f}"))  # noqa: E501
                self.strategies_table.setItem(row, 7, QTableWidgetItem("Active"))

        except Exception as e:
            self.logger.error("Error updating strategy table: %s", e, exc_info=True)

    def update_market_regime_display(self):
        """Update market regime information"""
        if not self.orchestrator:
            return

        try:
            regime_data = self.orchestrator.market_regime

            self.current_regime_label.setText(f"Regime: {regime_data.current_regime.value}")
            self.regime_confidence_label.setText(f"Confidence: {regime_data.regime_confidence:.1%}")
            self.vix_level_label.setText(f"VIX: {regime_data.vix_level:.1f}")
            self.trend_strength_label.setText(f"Trend: {regime_data.trend_strength:.2f}")

        except Exception as e:
            self.logger.error("Error updating market regime display: %s", e, exc_info=True)

    def update_allocation_chart(self):
        """Update allocation pie chart"""
        if not self.orchestrator:
            return

        try:
            # Clear previous plot
            self.allocation_figure.clear()
            ax = self.allocation_figure.add_subplot(111)

            # Get allocation data
            allocations = {}
            for _strategy_id, allocation in self.orchestrator.strategy_allocations.items():
                allocations[allocation.strategy_name] = allocation.current_allocation

            if allocations:
                # Create pie chart
                labels = list(allocations.keys())
                sizes = list(allocations.values())

                ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
                ax.set_title('Strategy Allocations')

            self.allocation_canvas.draw()

        except Exception as e:
            self.logger.error("Error updating allocation chart: %s", e, exc_info=True)

    def start_orchestration(self):
        """Start orchestration"""
        if self.orchestrator:
            success = self.orchestrator.start_orchestration()
            if success:
                self.status_bar_label.setText("Orchestration started")
            else:
                self.status_bar_label.setText("Failed to start orchestration")

    def stop_orchestration(self):
        """Stop orchestration"""
        if self.orchestrator:
            success = self.orchestrator.stop_orchestration()
            if success:
                self.status_bar_label.setText("Orchestration stopped")
            else:
                self.status_bar_label.setText("Failed to stop orchestration")

    def manual_rebalance(self):
        """Trigger manual rebalancing"""
        if self.orchestrator:
            success = self.orchestrator.rebalance_portfolio()
            if success:
                self.status_bar_label.setText("Manual rebalancing completed")
            else:
                self.status_bar_label.setText("Manual rebalancing failed")

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_strategy_orchestrator(base_capital: float = DEFAULT_BASE_CAPITAL,
                                orchestration_mode: OrchestrationMode = OrchestrationMode.BALANCED,
                                allocation_method: AllocationMethod = AllocationMethod.PERFORMANCE_BASED,  # noqa: E501
                                connectivity_manager: Any | None = None) -> StrategyOrchestrator:  # noqa: E501
    """Factory function to create strategy orchestrator"""
    return StrategyOrchestrator(base_capital, orchestration_mode, allocation_method, connectivity_manager)  # noqa: E501

def create_orchestrator_dashboard(orchestrator: StrategyOrchestrator | None = None) -> StrategyOrchestratorDashboard:  # noqa: E501
    """Factory function to create orchestrator dashboard"""
    return StrategyOrchestratorDashboard(orchestrator)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function for testing and demonstration"""
    logging.info("🎯 SPYDER D12 - Strategy Orchestrator")
    logging.info("=" * 60)

    try:
        # Create orchestrator
        orchestrator = StrategyOrchestrator(
            base_capital=100000,
            orchestration_mode=OrchestrationMode.BALANCED,
            allocation_method=AllocationMethod.PERFORMANCE_BASED
        )

        logging.info("✅ Strategy Orchestrator initialized")
        logging.info("📊 Configuration:")
        logging.info(f"  Base Capital: ${orchestrator.base_capital:,.2f}")
        logging.info("  Orchestration Mode: %s", orchestrator.orchestration_mode.value)
        logging.info("  Allocation Method: %s", orchestrator.allocation_method.value)
        logging.info("  Available Strategies: %s", len(orchestrator.available_strategies))

        # Test portfolio status
        status = orchestrator.get_portfolio_status()
        logging.info("\n📈 Portfolio Status:")
        logging.info(f"  Total Capital: ${status['total_capital']:,.2f}")
        logging.info(f"  Available Capital: ${status['available_capital']:,.2f}")
        logging.info("  Active Strategies: %s", status['active_strategies'])
        logging.info("  Market Regime: %s", status['market_regime'])

        logging.info("\n✅ Strategy Orchestrator test completed!")

    except Exception as e:
        logging.info("❌ Error during testing: %s", e)
        return False

    return True

if __name__ == "__main__":
    main()
