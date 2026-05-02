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
from collections import deque, defaultdict  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from enum import Enum  # noqa: E402
from typing import Any  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

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

    def _optional_strategy(import_path: str, symbol: str) -> Any:
        try:
            module = __import__(import_path, fromlist=[symbol])
            return getattr(module, symbol)
        except Exception as err:
            logging.warning("D31 optional strategy unavailable: %s (%s)", symbol, err)
            return None

    IronCondorStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD02_IronCondor", "IronCondorStrategy"
    )
    CreditSpreadStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD03_CreditSpread", "CreditSpreadStrategy"
    )
    ZeroDTEStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD04_ZeroDTE", "ZeroDTEStrategy"
    )
    StraddleStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD05_Straddle", "StraddleStrategy"
    )
    BullPutSpreadStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD06_BullPutSpread", "BullPutSpreadStrategy"
    )
    BearCallSpreadStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD07_BearCallSpread", "BearCallSpreadStrategy"
    )
    OpeningRangeBreakoutStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD08_OpeningRangeBreakout", "OpeningRangeBreakoutStrategy"
    )
    GreeksBasedStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD09_GreeksBasedStrategy", "GreeksBasedStrategy"
    )
    SpecializedZeroDTEStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD11_SpecializedZeroDTE", "SpecializedZeroDTEStrategy"
    )
    # Phase 3: strategies referenced in regime weights but previously unregistered
    IronButterflyStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD10_IronButterfly", "IronButterflyStrategy"
    )
    CalendarSpreadStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD14_CalendarSpread", "CalendarSpreadStrategy"
    )
    StraddleStrangleStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD15_StraddleStrangle", "StraddleStrangleStrategy"
    )
    RatioSpreadsStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD16_RatioSpreads", "RatioSpreadsStrategy"
    )
    DiagonalSpreadStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD17_DiagonalSpread", "DiagonalSpreadStrategy"
    )
    JadeLizardStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD19_JadeLizard", "JadeLizardStrategy"
    )
    VerticalSpreadOptimizer = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD20_VerticalSpreadOptimizer", "VerticalSpreadOptimizer"
    )
    DoubleCalendarStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD21_DoubleCalendar", "DoubleCalendarStrategy"
    )
    AdaptiveVolatilityStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD22_AdaptiveVolatility", "AdaptiveVolatilityStrategy"
    )
    GammaScalperStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD26_GammaScalper", "GammaScalperStrategy"
    )
    RSIMeanReversionStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD12_RSIMeanReversion", "RSIMeanReversionStrategy"
    )
    MACrossoverStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD13_MACrossover", "MACrossoverStrategy"
    )
    RenaissanceMeanReversionStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD33_RenaissanceMeanReversion", "RenaissanceMeanReversionStrategy"  # noqa: E501
    )
    PivotMeanReversionStrategy = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD34_PivotMeanReversion", "PivotMeanReversionStrategy"
    )
    EvolvedCreditSpreadCore = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD18_EvolvedCreditSpread", "EvolvedCreditSpreadStrategy"
    )
    VIXHedgingCore = _optional_strategy(
        "Spyder.SpyderD_Strategies.SpyderD28_VIXHedging", "VIXHedgingStrategy"
    )

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
            self._core = EvolvedCreditSpreadCore(config=config or {}) if EvolvedCreditSpreadCore else None

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

            timestamp = getattr(native_signal, "timestamp", None) or datetime.now(timezone.utc)

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
            self._core = VIXHedgingCore() if VIXHedgingCore else None

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
            timestamp = datetime.now(timezone.utc)
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
    from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType, get_event_manager  # noqa: E501

    # Connectivity integration
    from Spyder.SpyderB_Broker.SpyderB20_IntegratedConnectivityManager import IntegratedConnectivityManager, ConnectivityState  # noqa: E501

    # Prometheus rejection telemetry
    from Spyder.SpyderB_Broker.SpyderB15_PrometheusMetrics import record_risk_rejection as _record_risk_rejection  # noqa: E501

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
    IntegratedConnectivityManager = None  # type: ignore[assignment]
    EventManager = None  # type: ignore[assignment]
    Event = None  # type: ignore[assignment]
    EventType = None  # type: ignore[assignment]
    get_event_manager = None  # type: ignore[assignment]

    # Fallback enums
    class StrategyState(Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"
        PAUSED = "paused"
        ERROR = "error"

    class ConnectivityState(Enum):
        OPTIMAL = "optimal"
        GOOD = "good"
        DEGRADED = "degraded"
        FAILED = "failed"

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Portfolio management
MAX_CONCURRENT_STRATEGIES = 2
MAX_ACTIVE_HORIZON_BUCKETS = 1
DEFAULT_BASE_CAPITAL = 100000  # $100K base allocation
REBALANCE_FREQUENCY_MINUTES = 30  # Rebalance every 30 minutes
STRATEGY_HEALTH_CHECK_INTERVAL = 60  # Check health every minute

# Performance thresholds
MIN_SHARPE_RATIO = 0.5  # Minimum Sharpe for active strategies
MAX_DRAWDOWN_THRESHOLD = 0.15  # 15% maximum drawdown
CORRELATION_THRESHOLD = 0.7  # Maximum strategy correlation
PERFORMANCE_LOOKBACK_DAYS = 30  # Days for performance analysis

# Market regime detection
VOLATILITY_REGIME_LOOKBACK = 20  # Days for volatility regime
TREND_DETECTION_PERIODS = [5, 10, 20]  # Moving average periods
VIX_REGIME_THRESHOLDS = {'low': 15, 'normal': 20, 'high': 30, 'extreme': 40}

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
                 connectivity_manager: IntegratedConnectivityManager | None = None,
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
        self.connectivity_manager = connectivity_manager
        self.event_manager = event_manager
        self._l09_engine: Any | None = regime_engine          # L09 UnifiedRegimeEngine (optional)
        self._last_l09_confidence: float = 0.0               # confidence from last L09 call
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
            "IronCondor",
            "IronCondorStrategy",
            "IronButterfly",
            "IronButterflyStrategy",
        }

        # Portfolio state
        self.active_strategies: dict[str, BaseStrategy] = {}
        self.strategy_allocations: dict[str, StrategyAllocation] = {}
        self.available_strategies: dict[str, type] = {}
        self.paused_strategies: set[str] = set()
        # B3 (v15): lock protecting active_strategies and paused_strategies.
        # Both the orchestration thread and external callers (add/remove/pause/resume)
        # mutate these sets; without a lock the dicts can be corrupted under
        # concurrent access.
        self._strategies_lock = threading.RLock()

        # Market analysis
        self.market_regime = MarketRegimeData(
            current_regime=MarketRegime.SIDEWAYS_LOW_VOL,
            regime_confidence=0.0,
            volatility_percentile=50.0,
            trend_strength=0.0,
            vix_level=20.0,
            regime_duration_days=0,
            last_regime_change=datetime.now(timezone.utc)
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
        self.last_rebalance = datetime.now(timezone.utc)
        self.rebalance_history: list[RebalanceEvent] = []
        self.strategy_conflicts: list[StrategyConflict] = []

        # Threading
        self.orchestration_thread = None
        self.monitoring_thread = None
        self.shutdown_event = threading.Event()

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
        self._regime_policy: dict[str, Any] | None = None

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
        self._signal_drop_audit_enabled: bool = str(
            os.getenv("SPYDER_D31_SIGNAL_DROP_AUDIT", "1")
        ).strip().lower() not in {"0", "false", "no", "off"}
        self._signal_drop_audit_dir: str = str(
            os.getenv("SPYDER_D31_SIGNAL_DROP_AUDIT_DIR", os.path.join("logs", "decisions"))
        )

        # Y02 StrategyPilotAgent advisory: tracks the last time each strategy type
        # received an LLM-validated approval on the agent bus.  Updated by
        # _on_y02_validated_signal(); consulted (advisory-only) in the signal
        # dispatch path to surface patterns of Y02 disapproval in the logs.
        self._y02_advisory: dict[str, Any] = {}  # strategy_type → last approval datetime

        # Market data cache (replaced entirely each update, not appended)
        self.market_data_cache = {}
        self.last_market_update = None

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

        self.logger.debug(f"🎯 Strategy Orchestrator initialized - Mode: {orchestration_mode.value}, Capital: ${base_capital:,.2f}")  # noqa: E501

    def _record_signal_drop(
        self,
        stage: str,
        reason: str,
        signal: Any | None = None,
        detail: str | None = None,
    ) -> None:
        """Track and expose why strategy signals are dropped."""
        _count_drop(stage, reason)
        self._signal_flow_counts["dropped"] += 1
        self._signal_drop_reasons[f"{stage}:{reason}"] += 1
        self._persist_signal_drop_audit(
            stage=stage,
            reason=reason,
            signal=signal,
            detail=detail,
        )
        self._log_signal_flow_summary_if_due()

    @staticmethod
    def _signal_value(signal: Any, key: str, default: Any = None) -> Any:
        """Read a field from dict/object signal payloads."""
        if isinstance(signal, dict):
            return signal.get(key, default)
        return getattr(signal, key, default)

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
            now_utc = datetime.now(timezone.utc)
            day_key = now_utc.strftime("%Y-%m-%d")
            os.makedirs(self._signal_drop_audit_dir, exist_ok=True)
            file_path = os.path.join(self._signal_drop_audit_dir, f"{day_key}.jsonl")

            payload = signal if isinstance(signal, dict) else {}
            pivot_payload = self._extract_pivot_signal_payload(payload) if payload else None
            strategy_id = self._signal_value(payload, "strategy_id") or self._signal_value(payload, "strategy_name")

            record = {
                "ts_utc": now_utc.isoformat(),
                "component": "D31",
                "event": "signal_dropped",
                "stage": stage,
                "reason": reason,
                "detail": detail or "",
                "symbol": self._signal_value(payload, "symbol", ""),
                "strategy_id": strategy_id or "",
                "action": self._signal_value(payload, "action", self._signal_value(payload, "side", "")),
                "quantity": self._signal_value(payload, "quantity", 0),
                "signal_id": self._signal_value(payload, "signal_id", self._signal_value(payload, "id", "")),
                "regime": self._signal_value(payload, "regime", ""),
                "pivot": {
                    "fired": pivot_payload.get("fired") if isinstance(pivot_payload, dict) else None,
                    "direction": pivot_payload.get("direction") if isinstance(pivot_payload, dict) else None,
                    "score": pivot_payload.get("score") if isinstance(pivot_payload, dict) else None,
                    "nearest_level_name": pivot_payload.get("nearest_level_name") if isinstance(pivot_payload, dict) else None,
                    "atr_distance": pivot_payload.get("atr_distance") if isinstance(pivot_payload, dict) else None,
                },
            }

            with open(file_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=True) + "\n")
        except Exception as exc:
            self.logger.debug("D31: failed to persist signal-drop audit: %s", exc)

    def _record_signal_dispatch_outcome(self, outcome: str) -> None:
        """Track order-routing outcomes for approved signals."""
        if outcome in self._signal_flow_counts:
            self._signal_flow_counts[outcome] += 1
        self._log_signal_flow_summary_if_due()

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

    def start_orchestration(self) -> bool:
        """
        Start strategy orchestration.

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
                if connectivity_report.overall_state == ConnectivityState.FAILED:
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

            # Load optimal strategy configuration for current regime
            self._configure_strategies_for_regime()
            self.shutdown_event.clear()

            self.orchestration_thread = threading.Thread(target=self._orchestration_loop, daemon=True)  # noqa: E501
            self.orchestration_thread.start()

            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()

            # Initial portfolio allocation
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
            if self.lean_mode and strategy_name not in self.lean_strategy_allowlist:
                raise ValueError(
                    f"Lean mode blocks strategy registration: {strategy_name}"
                )
            horizon_bucket = self._resolve_horizon_bucket(strategy_name, config)

            with self._strategies_lock:
                current_active = len(self.active_strategies)
                if current_active >= self.max_concurrent_strategies:
                    raise ValueError(
                        f"Concurrent strategy limit reached: {current_active}/{self.max_concurrent_strategies}"  # noqa: E501
                    )

                active_buckets = self._get_active_horizon_buckets_locked()
                would_add_new_bucket = horizon_bucket not in active_buckets
                if (
                    would_add_new_bucket
                    and len(active_buckets) >= self.max_active_horizon_buckets
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
                strategy_type=self._get_strategy_type(strategy_class),
                horizon_bucket=horizon_bucket,
                allocated_capital=allocated_capital,
                target_allocation=initial_allocation,
                current_allocation=initial_allocation,
                performance_score=0.5,  # Neutral starting score
                risk_score=0.5,
                health_score=1.0,
                last_rebalance=datetime.now(timezone.utc)
            )

            # Add to active strategies AND allocation map under the same lock (B3/v15 + C1/v18).
            with self._strategies_lock:
                self.active_strategies[strategy_id] = strategy
                self.strategy_allocations[strategy_id] = _new_alloc

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
                # Update market regime
                self._update_market_regime()

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

    def _monitoring_loop(self):
        """Strategy health monitoring loop"""
        while self.orchestration_active and not self.shutdown_event.is_set():
            try:
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
                        allocation.last_rebalance = datetime.now(timezone.utc)
                        allocation.allocation_history.append((datetime.now(timezone.utc), new_allocation))

            # Record rebalance event
            rebalance_event = RebalanceEvent(
                timestamp=datetime.now(timezone.utc),
                reason=reason,
                previous_allocations=previous_allocations,
                new_allocations=new_allocations,
                capital_movements=capital_movements,
                expected_impact={},  # Could calculate expected impact
                execution_status="completed" if rebalance_successful else "failed"
            )

            self.rebalance_history.append(rebalance_event)
            self.last_rebalance = datetime.now(timezone.utc)

            # Update portfolio metrics
            self._update_portfolio_metrics()

            status = "✅ completed" if rebalance_successful else "❌ failed"
            self.logger.info("Portfolio rebalancing %s", status)

            return rebalance_successful

        except Exception as e:
            self.logger.error("❌ Rebalancing execution failed: %s", e, exc_info=True)
            return False

    def _get_risk_profile_for_strategy(self, strategy_class: type) -> "RiskProfile":  # noqa: F821
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
                    if isinstance(_vix_entry, list) and _vix_entry:
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
                self.market_regime.last_regime_change = datetime.now(timezone.utc)
                self.market_regime.regime_duration_days = 0
                self.market_regime.regime_history.append((datetime.now(timezone.utc), new_regime))
            else:
                # Update duration
                days_since_change = (datetime.now(timezone.utc) - self.market_regime.last_regime_change).days
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
    ) -> "MarketRegime":
        """Classify regime via L09 UnifiedRegimeEngine when injected; else inline heuristic."""
        self._last_l09_confidence = 0.0

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
                            if isinstance(value, (int, float)):
                                return float(value)
                    return float("nan")
                # Build MarketConditions from cached SPY + VIX ticks
                spy_ticks = self.market_data_cache.get("SPY", [])
                spy_price, spy_change_pct = 500.0, 0.0
                closes = [
                    t.get("close", t.get("price", 0.0))
                    for t in spy_ticks if isinstance(t, dict)
                ]
                closes = [float(c) for c in closes if isinstance(c, (int, float))]
                if len(closes) >= 2:
                    spy_price = closes[-1]
                    spy_change_pct = (closes[-1] - closes[0]) / closes[0] * 100.0

                spy_ema50 = _ema(closes, 50)

                atr = float("nan")
                atr_pct = float("nan")
                if len(spy_ticks) >= 2:
                    highs = [t.get("high") for t in spy_ticks if isinstance(t, dict)]
                    lows = [t.get("low") for t in spy_ticks if isinstance(t, dict)]
                    highs = [float(v) for v in highs if isinstance(v, (int, float))]
                    lows = [float(v) for v in lows if isinstance(v, (int, float))]
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
                    t.get("close", t.get("price", 0.0))
                    for t in vix_ticks if isinstance(t, dict)
                ]
                vix_values = [float(v) for v in vix_values if isinstance(v, (int, float))]
                vix_ema50 = _ema(vix_values, 50)

                vix9d = _last_close(self.market_data_cache.get("VIX9D", []) or self.market_data_cache.get("^VIX9D", []))
                vxv = _last_close(self.market_data_cache.get("VXV", []) or self.market_data_cache.get("^VXV", []))

                event_clock = self.market_data_cache.get("event_clock_state")
                event_state = "clear"
                if isinstance(event_clock, dict):
                    event_state = str(event_clock.get("state", "clear"))

                conditions = _L09Cond(
                    timestamp=datetime.now(timezone.utc),
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
                self.logger.debug(
                    "📊 L09 regime: %s (conf=%.2f)", consensus.regime.value, consensus.confidence
                )

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
        # Simplified regime classification
        is_high_vol = vix_level > VIX_REGIME_THRESHOLDS['high']
        is_crisis = vix_level > VIX_REGIME_THRESHOLDS['extreme']
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
        Uses a simple price-momentum heuristic from whatever SPY ticks are cached.
        """
        try:
            spy_ticks = self.market_data_cache.get("SPY", [])
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

    def _get_regime_strategy_weights(self) -> dict[str, float]:
        """Get optimal strategy weights for current regime"""
        regime = self.market_regime.current_regime

        if self.lean_mode:
            if regime in {MarketRegime.CRISIS, MarketRegime.EVENT_TRANSITION}:
                return {}
            if regime in {MarketRegime.BULL_LOW_VOL, MarketRegime.BULL_HIGH_VOL}:
                return {"BullPutSpread": 1.0}
            if regime in {MarketRegime.BEAR_LOW_VOL, MarketRegime.BEAR_HIGH_VOL}:
                return {"BearCallSpread": 1.0}
            if regime == MarketRegime.SIDEWAYS_LOW_VOL:
                return {"IronCondor": 1.0}
            if regime == MarketRegime.SIDEWAYS_HIGH_VOL:
                return {"IronButterfly": 1.0}
            return {}

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
                strategy_class = self.available_strategies[strategy_name]
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

            self.last_rebalance = datetime.now(timezone.utc)
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
                        allocation = weight / max(sum(regime_weights.values()), 1.0)
                        config: dict[str, Any] = {
                            "symbol": "SPY",
                            "allocated_capital": self.base_capital * allocation,
                        }
                        try:
                            self.add_strategy(
                                self.available_strategies[strategy_name],
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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

    def _initialize_strategy_registry(self) -> None:
        """Initialize available strategy registry"""
        if SPYDER_MODULES_AVAILABLE:
            candidate_strategies = {
                'IronCondor': IronCondorStrategy,
                'CreditSpread': CreditSpreadStrategy,
                'ZeroDTE': ZeroDTEStrategy,
                'Straddle': StraddleStrategy,
                'BullPutSpread': BullPutSpreadStrategy,
                'BearCallSpread': BearCallSpreadStrategy,
                'OpeningRangeBreakout': OpeningRangeBreakoutStrategy,
                'GreeksBased': GreeksBasedStrategy,
                'SpecializedZeroDTE': SpecializedZeroDTEStrategy,
                # Phase 3: strategies referenced in regime weights but previously unregistered
                'IronButterfly': IronButterflyStrategy,
                'CalendarSpread': CalendarSpreadStrategy,
                'StraddleStrangle': StraddleStrangleStrategy,
                'RatioSpreads': RatioSpreadsStrategy,
                'DiagonalSpread': DiagonalSpreadStrategy,
                'JadeLizard': JadeLizardStrategy,
                'VerticalSpreadOptimizer': VerticalSpreadOptimizer,
                'DoubleCalendar': DoubleCalendarStrategy,
                'AdaptiveVolatility': AdaptiveVolatilityStrategy,
                'GammaScalper': GammaScalperStrategy,
                'RSIMeanReversion': RSIMeanReversionStrategy,
                'MACrossover': MACrossoverStrategy,
                'RenaissanceMeanReversion': RenaissanceMeanReversionStrategy,
                'PivotMeanReversion': PivotMeanReversionStrategy,
                'EvolvedCreditSpread': EvolvedCreditSpreadAdapter,
                'VIXHedging': VIXHedgingAdapter,
            }

            if self.lean_mode:
                candidate_strategies = {
                    name: cls
                    for name, cls in candidate_strategies.items()
                    if name in self.lean_strategy_allowlist
                }

            self.available_strategies = {
                name: cls
                for name, cls in candidate_strategies.items()
                if _is_strategy_class(cls)
            }
        else:
            self.available_strategies = {}

        self.logger.info("📋 Registered %s strategy types", len(self.available_strategies))

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
                # P1-1: Pause signal emission when the engine is halted or data
                # becomes stale — strategies must not fire into a silenced engine.
                self.event_manager.subscribe(EventType.KILL_SWITCH, self._on_kill_switch)
                self.event_manager.subscribe(EventType.DATA_STALE, self._on_data_stale)
                # B5: Subscribe to DATA_FRESH so a data-stale pause auto-recovers.
                self.event_manager.subscribe(EventType.DATA_FRESH, self._on_data_fresh)
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
                        detected_at=datetime.now(timezone.utc),
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
                    detected_at=datetime.now(timezone.utc),
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
                    detected_at=datetime.now(timezone.utc),
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
          advisory: tracks approval patterns but does not hard-block signals
          because Y02's LLM inference is asynchronous relative to the hot-path)

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
                name="StrategyOrchestrator_Y02Advisory",
            )
            self.logger.info("📡 D31: Subscribed to agent bus 'signals.validated' topic (Y02)")
        except Exception as e:
            self.logger.warning("D31: Could not subscribe to 'signals.validated': %s", e)

    def _on_y02_validated_signal(self, message: Any) -> None:
        """Handle Y02 StrategyPilotAgent validated-signal advisory from the agent bus.

        Y02 publishes ``signals.validated`` payloads only for *approved* signals.
        We record the strategy type and timestamp so the orchestrator can surface
        patterns where Y02 has stopped approving a particular strategy.

        Args:
            message: AgentOutput or dict with payload containing ``original_signal``
                     and ``validation`` keys.
        """
        try:
            if isinstance(message, dict):
                payload = message.get("payload") or message.get("data") or {}
            else:
                payload = getattr(message, "payload", None) or getattr(message, "data", {}) or {}

            original_signal = payload.get("original_signal") or {}
            validation = payload.get("validation") or {}
            approved = bool(validation.get("approved", True))  # only published when True

            strategy_type = str(
                original_signal.get("strategy_type")
                or original_signal.get("strategy")
                or original_signal.get("type")
                or "unknown"
            )
            now = datetime.now(timezone.utc)

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

    def _on_agent_regime_update(self, message: Any) -> None:
        """Handle regime updates from Y01 MarketSenseAgent via the agent bus.

        Y01 publishes ``{regime: str, confidence: float}`` under the
        ``market.regime`` topic.  The bus wrapper envelopes this as
        ``{data: <payload>, confidence: float}``.
        """
        try:
            # Unwrap the bus envelope
            if isinstance(message, dict):
                data = message.get("data", {}) or {}
            else:
                data = getattr(message, "data", {}) or {}

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
                self.market_regime.last_regime_change = datetime.now(timezone.utc)
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
            # Preserve non-market feed fields (e.g., event_clock_state) while updating ticks.
            existing = self.market_data_cache if isinstance(self.market_data_cache, dict) else {}
            merged = dict(existing)
            merged.update(data)
            self.market_data_cache = merged
        else:
            self.market_data_cache = data
        self.last_market_update = datetime.now(timezone.utc)

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
                    row.setdefault("symbol", data.get("symbol", row.get("symbol", "")))
                    market_df = pd.DataFrame([row])
                else:
                    market_df = pd.DataFrame([data])
        except Exception:
            pass

        if market_df is None or (hasattr(market_df, "empty") and market_df.empty):
            return

        for strategy_id, strategy in list(self.active_strategies.items()):
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

        market_gate_ok, market_gate_reason = self._passes_entry_trust_gate(signal)
        pivot_context = self._format_pivot_log_context(
            self._extract_pivot_signal_payload(signal)
        )
        if not market_gate_ok:
            self._record_signal_drop(
                "pre_risk",
                "entry_trust_gate",
                signal=signal,
                detail=market_gate_reason,
            )
            self.logger.warning(
                "Strategy signal rejected by entry trust gate: %s | %s",
                market_gate_reason,
                pivot_context,
            )
            if self.event_manager:
                try:
                    self.event_manager.publish(
                        EventType.RISK_ALERT,
                        {
                            "severity": "warning",
                            "reason": "entry_trust_gate_rejected",
                            "message": market_gate_reason,
                            "signal": signal,
                        },
                    )
                except Exception:
                    pass
            return

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
            if _record_risk_rejection is not None:
                try:
                    _record_risk_rejection(strategy=strategy_id, rejection_reason=reason)
                except Exception:
                    pass
            try:
                self.event_manager.publish(
                    EventType.RISK_ALERT,
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

        if approved:
            self._signal_flow_counts["approved"] += 1
            self.logger.info("Strategy signal approved for dispatch | %s", pivot_context)
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
            self._entry_filter_gate = EntryFilters(config_manager)
        except Exception as exc:
            self.logger.debug("D31: failed to initialize EntryFilters gate: %s", exc)
            self._entry_filter_gate = None
        return self._entry_filter_gate

    def _get_current_market_conditions(self) -> dict[str, Any]:
        """Fetch the latest S07 market conditions for trust-policy gating."""
        if self._metrics_orchestrator is None:
            try:
                from Spyder.SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import get_metrics_orchestrator  # noqa: E501
            except ImportError:
                try:
                    from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import get_metrics_orchestrator  # type: ignore[no-redef]  # noqa: E501
                except ImportError:
                    self.logger.debug("D31: S07 metrics orchestrator unavailable")
                    return {}

            try:
                self._metrics_orchestrator = get_metrics_orchestrator()
            except Exception as exc:
                self.logger.debug("D31: failed to get S07 metrics orchestrator: %s", exc)
                return {}

        try:
            conditions = self._metrics_orchestrator.get_current_market_conditions()
        except Exception as exc:
            self.logger.debug("D31: failed to read S07 market conditions: %s", exc)
            return {}

        return conditions if isinstance(conditions, dict) else {}

    @staticmethod
    def _extract_pivot_signal_payload(signal: Any, market_conditions: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Extract SpyderS08 pivot payload from signal/metadata/market context."""
        if not isinstance(signal, dict):
            return None

        metadata = signal.get("metadata") if isinstance(signal.get("metadata"), dict) else {}
        market_conditions = market_conditions if isinstance(market_conditions, dict) else {}

        candidates = (
            signal.get("pivot_mr_signal"),
            signal.get("s08_pivot_signal"),
            metadata.get("pivot_mr_signal"),
            metadata.get("s08_pivot_signal"),
            market_conditions.get("pivot_mr_signal"),
            market_conditions.get("s08_pivot_signal"),
            market_conditions.get("pivot_signal"),
        )

        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate
        return None

    @staticmethod
    def _normalise_strategy_type_for_entry_gate(value: Any) -> str:
        """Normalize strategy labels/IDs into F09 strategy_type names."""
        text = str(value or "").strip().lower()
        if not text:
            return ""

        if "bull_put_spread" in text or "spyderd06" in text or text == "d06":
            return "bull_put_spread"
        if "bull_call_spread" in text or "spyderd15" in text or text == "d15":
            return "bull_call_spread"
        if "bear_call_spread" in text or "spyderd07" in text or text == "d07":
            return "bear_call_spread"
        if "bear_put_spread" in text or "spyderd16" in text or text == "d16":
            return "bear_put_spread"
        if "iron_condor" in text or "spyderd02" in text or text == "d02":
            return "iron_condor"
        if "iron_butterfly" in text or "spyderd10" in text or text == "d10":
            return "iron_butterfly"
        return text

    @staticmethod
    def _strategy_policy_match_tokens(value: Any) -> set[str]:
        """Generate robust strategy tokens for regime-policy allow/block matching."""
        base = str(value or "").strip().lower()
        if not base:
            return set()

        text = base.replace("-", "_").replace(" ", "_")
        tokens: set[str] = {text}

        # Include D31/F09 normalized names for stable comparisons.
        normalized = StrategyOrchestrator._normalise_strategy_type_for_entry_gate(text)
        if normalized:
            tokens.add(normalized)

        # Common strategy naming drifts across config/runtime modules.
        rewrites = (
            ("_credit_spread", "_spread"),
            ("_debit_spread", "_spread"),
            ("_defined_risk", ""),
            ("_overlay", ""),
            ("_engine", ""),
            ("_strategy", ""),
        )
        for token in list(tokens):
            for old, new in rewrites:
                if old in token:
                    tokens.add(token.replace(old, new))

        aliases = {
            "bull_put_spread": {"bull_put_credit_spread", "credit_spread_bull_put", "bull_put"},
            "bull_call_spread": {"bull_call", "call_debit_spread", "debit_spread_bull_call"},
            "bear_call_spread": {"bear_call_credit_spread", "credit_spread_bear_call", "bear_call"},
            "bear_put_spread": {"bear_put", "put_debit_spread", "debit_spread_bear_put"},
            "iron_condor": {"iron_condor_defined_risk"},
            "iron_butterfly": {"short_duration_defined_risk"},
            "rsi_mean_reversion": {"mean_reversion_spreads", "mean_reversion"},
            "renaissance_mean_reversion": {"mean_reversion_spreads", "mean_reversion"},
            "opening_range_breakout": {"trend_breakout_calls", "breakout_calls"},
            "vix_hedging": {"protective_put_overlay", "protective_put"},
        }

        for token in list(tokens):
            tokens.update(aliases.get(token, set()))

        return {tok for tok in tokens if tok}

    @staticmethod
    def _format_pivot_log_context(pivot_signal: dict[str, Any] | None) -> str:
        """Format concise S08 pivot context for D31 decision logs."""
        if not isinstance(pivot_signal, dict):
            return "pivot=n/a"

        direction = str(pivot_signal.get("direction", "none"))
        score = int(pivot_signal.get("score", 0) or 0)
        fired = bool(pivot_signal.get("fired", False))
        level_name = str(pivot_signal.get("nearest_level_name", "") or "-")
        atr_distance = pivot_signal.get("atr_distance")
        penalties = pivot_signal.get("penalties") or []
        penalty_excerpt = str(penalties[0]) if penalties else ""

        return (
            f"pivot=fired:{fired} direction:{direction} score:{score} "
            f"level:{level_name} atr_distance:{atr_distance} penalty:{penalty_excerpt}"
        )

    def _passes_entry_trust_gate(self, signal: Any) -> tuple[bool, str]:
        """Apply F09's trust-policy checks to the live D31 signal path."""
        if not isinstance(signal, dict):
            return True, ""

        entry_gate = self._get_entry_filter_gate()
        if entry_gate is None:
            return True, ""

        market_conditions = self._get_current_market_conditions()
        if not market_conditions:
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
            self.logger.debug("D31: entry trust gate failed open: %s", exc, exc_info=True)
            return True, ""

        failures = []
        for check in checks:
            result = getattr(check, "result", None)
            if getattr(result, "value", result) == "fail":
                failures.append(check)
        if not failures:
            return self._passes_regime_policy_gate(signal, market_conditions)

        return False, "; ".join(str(check.message) for check in failures)

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

        regime_aliases = {
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
            "recovery": "event_transition",
            # Gap fixes: previously unmapped — fail-safe to nearest policy key
            "low_volatility": "bull_trend",  # L09 ML path; D30 maps to BULL bucket
            "unknown": "crisis_turbulent",   # data-unavailable state; hard-block for safety
        }
        regime_key = raw_regime if raw_regime in regimes else regime_aliases.get(raw_regime, "")
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
        self.logger.info(
            "RiskManager wired to StrategyOrchestrator for signal pre-validation"
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

            pivot_context = self._format_pivot_log_context(
                self._extract_pivot_signal_payload(raw if isinstance(raw, dict) else signal)
            )

            def _get(key: str, default: Any = None) -> Any:
                if isinstance(raw, dict):
                    return raw.get(key, default)
                return getattr(raw, key, default)

            symbol = _get("symbol", "")
            quantity = int(_get("quantity", 0))

            if not symbol or not quantity:
                self.logger.warning(
                    "Cannot dispatch approved signal — missing symbol or quantity: %s | %s",
                    pivot_context,
                    signal,
                )
                self._record_signal_drop("dispatch", "invalid_signal_payload", signal=signal)
                return

            side = str(_get("action", _get("side", "buy"))).lower()
            strategy_id = _get("strategy_id", _get("strategy_name", ""))
            bid = float(_get("bid", 0.0) or 0.0)
            ask = float(_get("ask", 0.0) or 0.0)
            option_symbol = str(_get("option_symbol", "") or "")

            # ── Path 1: mid-price walk ────────────────────────────────────────
            if bid > 0.0 and ask > 0.0 and self._order_manager is not None:
                walk_result = self._order_manager.submit_limit_with_walk(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    bid=bid,
                    ask=ask,
                    option_symbol=option_symbol or None,
                    strategy_name=strategy_id or None,
                )
                if walk_result.success:
                    self.logger.info(
                        "MidWalk filled: symbol=%s qty=%d %s | %s",
                        symbol,
                        quantity,
                        walk_result.message,
                        pivot_context,
                    )
                    self._record_signal_dispatch_outcome("dispatch_submitted")
                else:
                    self.logger.warning(
                        "MidWalk did not fill: symbol=%s reason=%s error=%s | %s",
                        symbol,
                        walk_result.message,
                        walk_result.error_code,
                        pivot_context,
                    )
                    self._record_signal_dispatch_outcome("dispatch_rejected")
                return  # Mid-price path handled — do not send a market order

            # ── Path 2: market order via live engine ─────────────────────────
            if self._live_engine is None:
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
                reason = result.get("reason", "") if isinstance(result, dict) else ""
                self.logger.warning(
                    "Market order rejected by live engine: symbol=%s reason=%s | %s",
                    symbol,
                    reason,
                    pivot_context,
                )
                self._record_signal_dispatch_outcome("dispatch_rejected")
            else:
                self.logger.info(
                    "Market order dispatched: symbol=%s qty=%d status=%s | %s",
                    symbol,
                    quantity,
                    status,
                    pivot_context,
                )
                self._record_signal_dispatch_outcome("dispatch_submitted")

        except Exception as exc:
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
        # Time-based rebalancing
        time_since_rebalance = datetime.now(timezone.utc) - self.last_rebalance
        # Performance-driven rebalancing
        # (Implementation would check allocation drift, performance changes, etc.)
        return time_since_rebalance > timedelta(minutes=REBALANCE_FREQUENCY_MINUTES)

    def _determine_rebalance_reason(self) -> RebalanceReason:
        """Determine the reason for rebalancing"""
        # Simplified logic - would be more sophisticated in practice
        time_since_rebalance = datetime.now(timezone.utc) - self.last_rebalance
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
            self.last_update_label.setText(f"Updated: {datetime.now(timezone.utc).strftime('%H:%M:%S')}")

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
                                connectivity_manager: IntegratedConnectivityManager | None = None) -> StrategyOrchestrator:  # noqa: E501
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
