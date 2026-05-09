#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderI_Integration
Module: SpyderI12_ModuleRegistry.py
Purpose: Central registry of all Spyder modules with series, class name, status,
         and dependency metadata.  Allows Q80, I04, R09, and any diagnostic tool
         to query the module landscape without hardcoding lists.

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-04-04

Module Description:
    Provides a single authoritative dictionary ``REGISTERED_MODULES`` mapping
    module IDs to metadata records.  The registry is statically defined here and
    can be supplemented at runtime by calling ``register_module()``.

    Consumers:
    - ``SpyderQ80_VerifyDashboardIntegration`` — confirms required modules load.
    - ``SpyderI04_DiagnosticsEngine_Core``     — queries module health status.
    - ``SpyderR09_ProductionDeploymentManager``— validates deployment readiness.
    - ``SpyderQ09_ValidateMissingExports``     — cross-checks disk vs registry.

    Module status values:
    - ``"production"``  — stable, deployed, fully tested.
    - ``"beta"``        — feature-complete but under active testing.
    - ``"stub"``        — placeholder with partial implementation.
    - ``"deprecated"``  — retained for back-compat; do not use for new code.
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import importlib
import logging
from dataclasses import dataclass, field
from typing import Any

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _logger = SpyderLogger.get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class ModuleRecord:
    """Metadata for a single Spyder module."""
    module_id: str            # e.g. "A01"
    package: str              # e.g. "SpyderA_Core"
    filename: str             # e.g. "SpyderA01_Main"
    primary_class: str        # e.g. "SpyderA01Main"
    description: str
    series: str               # single letter: "A"–"Z"
    status: str = "production"  # "production" | "beta" | "stub" | "deprecated"
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    @property
    def import_path(self) -> str:
        """Fully qualified dotted import path for the primary class."""
        return f"Spyder.{self.package}.{self.filename}.{self.primary_class}"

    def is_available(self) -> bool:
        """Attempt a runtime import and return True if the module loads."""
        try:
            mod = importlib.import_module(f"Spyder.{self.package}.{self.filename}")
            return hasattr(mod, self.primary_class)
        except Exception:
            return False


# ==============================================================================
# REGISTRY
# ==============================================================================

# One entry per key production module.  Extend as modules are added.
REGISTERED_MODULES: dict[str, ModuleRecord] = {
    # ── A-Series: Core ────────────────────────────────────────────────
    "A01": ModuleRecord("A01", "SpyderA_Core", "SpyderA01_Main", "main",
                        "Top-level entry point and bootstrap", "A",
                        tags=["entry_point"]),
    "A02": ModuleRecord("A02", "SpyderA_Core", "SpyderA02_TradingEngine", "TradingEngine",
                        "Core trading engine and main loop", "A",
                        dependencies=["E01", "B40", "C01"],
                        tags=["engine"]),
    "A03": ModuleRecord("A03", "SpyderA_Core", "SpyderA03_Configuration", "SpyderConfiguration",
                        "System-wide configuration management", "A",
                        tags=["config"]),
    "A04": ModuleRecord("A04", "SpyderA_Core", "SpyderA04_Scheduler", "SpyderScheduler",
                        "Task and cron scheduler", "A"),
    "A05": ModuleRecord("A05", "SpyderA_Core", "SpyderA05_EventManager", "EventManager",
                        "Central event bus", "A",
                        tags=["event_bus"]),
    "A06": ModuleRecord("A06", "SpyderA_Core", "SpyderA06_MasterController", "MasterController",
                        "Master controller — start/stop all subsystems", "A"),
    "A08": ModuleRecord("A08", "SpyderA_Core", "SpyderA08_FSeriesOrchestrator",
                        "SpyderA08FSeriesOrchestrator",
                        "Orchestrates F-Series analytics pipeline", "A",
                        tags=["orchestration", "analytics"]),
    # ── B-Series: Broker ──────────────────────────────────────────────
    "B00": ModuleRecord("B00", "SpyderB_Broker", "SpyderB00_OrderTypes", "OrderType",
                        "Order type enums and constants", "B",
                        tags=["types"]),
    "B02": ModuleRecord("B02", "SpyderB_Broker", "SpyderB02_OrderManager", "OrderManager",
                        "Full order lifecycle management", "B",
                        dependencies=["B40", "E01"],
                        tags=["orders"]),
    "B04": ModuleRecord("B04", "SpyderB_Broker", "SpyderB04_AccountManager", "AccountManager",
                        "Tradier account info: balances and margin", "B",
                        dependencies=["B40"]),
    "B40": ModuleRecord("B40", "SpyderB_Broker", "SpyderB40_TradierClient", "SpyderB40_TradierClient",  # noqa: E501
                        "Primary Tradier REST/WebSocket client", "B",
                        tags=["broker", "api_client"]),
    "B30": ModuleRecord("B30", "SpyderB_Broker", "SpyderB30_SPYOptionsChainManager",
                        "SPYOptionsChainManager",
                        "SPY options chain manager (deprecated — use SpyderN03_OptionsChainManager)", "B",  # noqa: E501
                        status="deprecated",
                        tags=["options", "chain"]),
    # ── C-Series: MarketData ──────────────────────────────────────────
    "C01": ModuleRecord("C01", "SpyderC_MarketData", "SpyderC01_DataFeed", "DataFeed",
                        "Primary real-time tick data feed", "C",
                        tags=["data_feed"]),
    "C06": ModuleRecord("C06", "SpyderC_MarketData", "SpyderC06_DataValidator", "DataValidator",
                        "Multi-layer market data validation", "C",
                        tags=["validation"]),
    "C22": ModuleRecord("C22", "SpyderC_MarketData", "SpyderC22_FactorDataProvider",
                        "FactorDataProvider",
                        "Factor data for ML feature pipelines", "C",
                        tags=["data_pipeline", "ml"]),
    "C23": ModuleRecord("C23", "SpyderC_MarketData", "SpyderC23_RealTimeDataOptimizer",
                        "RealTimeDataOptimizer",
                        "Real-time data throughput optimiser", "C",
                        tags=["data_pipeline", "performance"]),
    "C24": ModuleRecord("C24", "SpyderC_MarketData", "SpyderC24_ModelDataPipeline",
                        "ModelDataPipeline",
                        "End-to-end data pipeline for ML model consumption", "C",
                        dependencies=["C22"],
                        tags=["data_pipeline", "ml"]),
    # ── D-Series: Strategies ──────────────────────────────────────────
    "D01": ModuleRecord("D01", "SpyderD_Strategies", "SpyderD01_BaseStrategy", "BaseStrategy",
                        "Abstract base class for all strategies", "D",
                        tags=["base_class"]),
    "D02": ModuleRecord("D02", "SpyderD_Strategies", "SpyderD02_IronCondor", "IronCondorStrategy",
                        "Iron Condor premium-collection strategy", "D",
                        dependencies=["D01", "E01", "N04"]),
    "D04": ModuleRecord("D04", "SpyderD_Strategies", "SpyderD04_ZeroDTE", "ZeroDTEStrategy",
                        "Zero-days-to-expiry intraday strategy", "D",
                        dependencies=["D01", "E01"]),
    "D31": ModuleRecord("D31", "SpyderD_Strategies", "SpyderD31_StrategyOrchestrator",
                        "StrategyOrchestrator",
                        "Coordinates concurrent strategy execution", "D",
                        dependencies=["D01", "E01", "P01"],
                        tags=["orchestrator"]),
    # ── E-Series: Risk ────────────────────────────────────────────────
    "E01": ModuleRecord("E01", "SpyderE_Risk", "SpyderE01_RiskManager", "RiskManager",
                        "Core pre/post-trade risk validation", "E",
                        tags=["risk"]),
    "E02": ModuleRecord("E02", "SpyderE_Risk", "SpyderE02_PositionSizer", "PositionSizer",
                        "Dynamic position sizing", "E",
                        dependencies=["E01"]),
    "E16": ModuleRecord("E16", "SpyderE_Risk", "SpyderE16_CircuitBreakerProtocol",
                        "CircuitBreakerProtocol",
                        "Circuit breaker — halts new orders on trigger", "E",
                        tags=["circuit_breaker"]),
    "E18": ModuleRecord("E18", "SpyderE_Risk", "SpyderE18_FSeriesRiskIntegrator",
                        "FSeriesRiskIntegrator",
                        "Integrates F-Series analytics into risk validation pipeline", "E",
                        dependencies=["E01", "A08"],
                        tags=["risk", "analytics"]),
    "E19": ModuleRecord("E19", "SpyderE_Risk", "SpyderE19_UnifiedRiskCoordinator",
                        "UnifiedRiskCoordinator",
                        "Fans risk checks to all E-Series and aggregates verdicts", "E",
                        dependencies=["E01", "E02", "E15", "E16"]),
    # ── F-Series: Analysis ────────────────────────────────────────────
    "F01": ModuleRecord("F01", "SpyderF_Analysis", "SpyderF01_Indicators", "TechnicalIndicators",
                        "Core technical indicators", "F",
                        tags=["indicators"]),
    "F10": ModuleRecord("F10", "SpyderF_Analysis", "SpyderF10_MarketRegimeDetector",
                        "MarketRegimeDetector",
                        "Composite market regime detector", "F",
                        tags=["regime"]),
    "F12": ModuleRecord("F12", "SpyderF_Analysis", "SpyderF12_AdvancedBacktestingEngine",
                        "AdvancedBacktestingEngine",
                        "Vectorised backtesting engine", "F",
                        tags=["backtest"]),
    "F13": ModuleRecord("F13", "SpyderF_Analysis", "SpyderF13_ModelValidation",
                        "ModelValidator",
                        "Walk-forward validation and overfitting detection for ML models", "F",
                        tags=["ml", "validation"]),
    "F14": ModuleRecord("F14", "SpyderF_Analysis", "SpyderF14_MarketMicrostructure",
                        "MarketMicrostructureAnalyzer",
                        "Intraday microstructure: VPIN, trade clustering, order-flow imbalance", "F",  # noqa: E501
                        tags=["microstructure"]),
    "F16": ModuleRecord("F16", "SpyderF_Analysis", "SpyderF16_RealTimeAnalytics",
                        "RealTimeAnalytics",
                        "Streaming real-time analytics pipeline", "F",
                        tags=["real_time", "analytics"]),
    "F17": ModuleRecord("F17", "SpyderF_Analysis", "SpyderF17_UnifiedPerformanceEngine",
                        "UnifiedPerformanceEngine",
                        "Unified engine computing performance metrics", "F",
                        tags=["performance", "metrics"]),
        # ── G-Series: GUI ─────────────────────────────────────────────────
    "G05": ModuleRecord("G05", "SpyderG_GUI", "SpyderG05_TradingDashboard", "TradingDashboard",
                        "Main trading dashboard (PySide6)", "G",
                        tags=["gui", "dashboard"]),
    "G06": ModuleRecord("G06", "SpyderG_GUI", "SpyderG06_DashboardData", "DashboardData",
                        "Data model layer for the dashboard", "G",
                        tags=["gui", "data"]),
    "G09": ModuleRecord("G09", "SpyderG_GUI", "SpyderG09_RiskParametersDialog",
                        "RiskParametersDialog",
                        "Risk parameters configuration dialog", "G",
                        tags=["gui", "risk"]),
    "G10": ModuleRecord("G10", "SpyderG_GUI", "SpyderG10_CustomMetricsIntegration",
                        "CustomMetricsIntegration",
                        "Integrates DIX/GEX/SKEW custom metrics into dashboard", "G",
                        tags=["gui", "metrics"]),
    "G11": ModuleRecord("G11", "SpyderG_GUI", "SpyderG11_SkewMonitorDialog",
                        "SkewMonitorDialog",
                        "SKEW index monitor dialog with real-time chart", "G",
                        tags=["gui", "skew"]),
    # ── H-Series: Storage ─────────────────────────────────────────────
    "H01": ModuleRecord("H01", "SpyderH_Storage", "SpyderH01_DataAccessLayer", "DataAccessLayer",
                        "Parameterised SQL data access layer", "H",
                        tags=["database"]),
    "H02": ModuleRecord("H02", "SpyderH_Storage", "SpyderH02_DatabaseManager", "DatabaseManager",
                        "SQLite schema, migrations, and backup", "H",
                        dependencies=["H01"],
                        tags=["database"]),
    # ── I-Series: Integration ─────────────────────────────────────────
    "I02": ModuleRecord("I02", "SpyderI_Integration", "SpyderI02_EventRouter", "EventRouter",
                        "Publish-subscribe event routing", "I",
                        tags=["event_bus"]),
    "I06": ModuleRecord("I06", "SpyderI_Integration", "SpyderI06_AgentMessageBus",
                        "AgentMessageBus",
                        "Routes messages between X/Y AI agents", "I",
                        tags=["agents", "message_bus"]),
    "I12": ModuleRecord("I12", "SpyderI_Integration", "SpyderI12_ModuleRegistry",
                        "ModuleRegistry",
                        "Central module registry (this module)", "I",
                        tags=["registry", "meta"]),
    # ── J-Series: Alerts ──────────────────────────────────────────────
    "J01": ModuleRecord("J01", "SpyderJ_Alerts", "SpyderJ01_AlertManager", "AlertManager",
                        "Alert routing, deduplication, and escalation", "J",
                        tags=["alerts"]),
    # ── L-Series: ML ──────────────────────────────────────────────────
    "L01": ModuleRecord("L01", "SpyderL_ML", "SpyderL01_MLPredictor", "MLPredictor",
                        "Core ML prediction engine", "L",
                        tags=["ml"]),
    "L16": ModuleRecord("L16", "SpyderL_ML", "SpyderL16_OptionsAdjustmentRL",
                        "OptionsAdjustmentRL",
                        "RL agent for adaptive position adjustment", "L",
                        tags=["ml", "rl"]),
    # ── M-Series: Monitoring ──────────────────────────────────────────
    "M01": ModuleRecord("M01", "SpyderM_Monitoring", "SpyderM01_SystemMonitor", "SystemMonitor",
                        "System health: CPU, memory, disk via psutil", "M",
                        tags=["monitoring"]),
    "M08": ModuleRecord("M08", "SpyderM_Monitoring", "SpyderM08_HealthEndpoint", "HealthEndpoint",
                        "HTTP /health endpoint for readiness probes", "M",
                        tags=["monitoring", "health"]),
    # ── N-Series: OptionsAnalytics ────────────────────────────────────
    "N01": ModuleRecord("N01", "SpyderN_OptionsAnalytics", "SpyderN01_OptionsPricer",
                        "OptionsPricer",
                        "BSM and binomial options pricing", "N",
                        tags=["options", "pricing"]),
    "N04": ModuleRecord("N04", "SpyderN_OptionsAnalytics", "SpyderN04_OptionsGreeksCalculator",
                        "OptionsGreeksCalculator",
                        "High-precision Greeks (delta, gamma, theta, vega…)", "N",
                        tags=["options", "greeks"]),
    "N09": ModuleRecord("N09", "SpyderN_OptionsAnalytics", "SpyderN09_GammaExposure",
                        "GammaExposure",
                        "Net Gamma Exposure (GEX) and dealer positioning", "N",
                        tags=["options", "gex"]),
    # ── P-Series: PortfolioMgmt ───────────────────────────────────────
    "P01": ModuleRecord("P01", "SpyderP_PortfolioMgmt", "SpyderP01_PortfolioManager",
                        "PortfolioManager",
                        "Tracks all open positions and portfolio-level Greeks", "P",
                        dependencies=["E01", "N04"]),
    # ── R-Series: Runtime ─────────────────────────────────────────────
    "R02": ModuleRecord("R02", "SpyderR_Runtime", "SpyderR02_PaperEngine", "PaperEngine",
                        "Paper trading engine — simulates live execution", "R",
                        tags=["runtime", "paper"]),
    "R04": ModuleRecord("R04", "SpyderR_Runtime", "SpyderR04_LiveEngine", "LiveEngine",
                        "Live trading engine — routes signals to broker", "R",
                        dependencies=["B40", "E01"],
                        tags=["runtime", "live"]),
    "R09": ModuleRecord("R09", "SpyderR_Runtime", "SpyderR09_ProductionDeploymentManager",
                        "ProductionDeploymentManager",
                        "Production deployment: health checks and rollback", "R",
                        dependencies=["M01", "M08", "I12"],
                        tags=["deployment"]),
    # ── U-Series: Utilities ───────────────────────────────────────────
    "U01": ModuleRecord("U01", "Spyder.SpyderU_Utilities", "SpyderU01_Logger", "SpyderLogger",
                        "Thread-safe structured logging singleton", "U",
                        tags=["logging", "singleton"]),
    "U02": ModuleRecord("U02", "Spyder.SpyderU_Utilities", "SpyderU02_ErrorHandler",
                        "SpyderErrorHandler",
                        "Centralised exception handling with retry logic", "U",
                        tags=["error_handling"]),
    "U07": ModuleRecord("U07", "Spyder.SpyderU_Utilities", "SpyderU07_Constants", "CONSTANTS",
                        "System-wide constants — tick sizes, API endpoints, etc.", "U",
                        tags=["constants"]),
    "U10": ModuleRecord("U10", "Spyder.SpyderU_Utilities", "SpyderU10_TradingCalendar",
                        "TradingCalendar",
                        "NYSE trading calendar and holiday schedule", "U",
                        tags=["calendar"]),
    # ── X-Series: Agents ──────────────────────────────────────────────
    "X06": ModuleRecord("X06", "SpyderX_Agents", "SpyderX06_BacktestingAgent",
                        "SpyderX06_BacktestingAgent",
                        "On-demand LLM-assisted backtesting agent", "X",
                        dependencies=["F12", "R08", "K12", "K07"],
                        tags=["agent", "backtest"]),
    "X14": ModuleRecord("X14", "SpyderX_Agents", "SpyderX14_OrchestratorAgent",
                        "SpyderX14_OrchestratorAgent",
                        "Multi-agent workflow coordinator", "X",
                        tags=["agent", "orchestrator"]),
    # ── Y-Series: AutoAgents ──────────────────────────────────────────
    "Y03": ModuleRecord("Y03", "SpyderY_AutoAgents", "SpyderY03_RiskSentinelAgent",
                        "RiskSentinelAgent",
                        "24/7 autonomous risk sentinel", "Y",
                        dependencies=["E16", "J01"],
                        tags=["agent", "risk"]),
    "Y08": ModuleRecord("Y08", "SpyderY_AutoAgents", "SpyderY08_MetaOrchestratorAgent",
                        "MetaOrchestratorAgent",
                        "Meta-orchestrator: manages all Y-Series agents", "Y",
                        tags=["agent", "orchestrator"]),
}


# ==============================================================================
# REGISTRY CLASS
# ==============================================================================

class ModuleRegistry:
    """
    Query interface over ``REGISTERED_MODULES``.

    Supports lookup by series, status, tag, and availability check.

    Args:
        registry: Backing dict of module records (defaults to REGISTERED_MODULES).
    """

    def __init__(
        self, registry: dict[str, ModuleRecord] | None = None
    ) -> None:
        self._registry = registry if registry is not None else REGISTERED_MODULES

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_module(self, record: ModuleRecord) -> None:
        """
        Add or update a module record at runtime.

        Args:
            record: ModuleRecord to register.
        """
        self._registry[record.module_id] = record
        _logger.debug("ModuleRegistry: registered '%s'", record.module_id)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get(self, module_id: str) -> ModuleRecord | None:
        """Return the record for *module_id*, or None if not registered."""
        return self._registry.get(module_id)

    def by_series(self, series_letter: str) -> list[ModuleRecord]:
        """Return all records for a given series letter (e.g. ``"A"``).."""
        return [r for r in self._registry.values()
                if r.series.upper() == series_letter.upper()]

    def by_status(self, status: str) -> list[ModuleRecord]:
        """Return all records with the given status string."""
        return [r for r in self._registry.values() if r.status == status]

    def by_tag(self, tag: str) -> list[ModuleRecord]:
        """Return all records that include *tag* in their tag list."""
        return [r for r in self._registry.values() if tag in r.tags]

    def all_modules(self) -> list[ModuleRecord]:
        """Return every registered module record."""
        return list(self._registry.values())

    def available_modules(self) -> list[ModuleRecord]:
        """
        Return records whose primary class can be imported successfully.

        Note: This performs a real import for each record; use sparingly.
        """
        return [r for r in self._registry.values() if r.is_available()]

    def missing_modules(self) -> list[ModuleRecord]:
        """Return records whose primary class cannot be imported."""
        return [r for r in self._registry.values() if not r.is_available()]

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary dict suitable for JSON serialisation."""
        by_series: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for rec in self._registry.values():
            by_series[rec.series] = by_series.get(rec.series, 0) + 1
            by_status[rec.status] = by_status.get(rec.status, 0) + 1
        return {
            "total_registered": len(self._registry),
            "by_series": by_series,
            "by_status": by_status,
        }

    def __len__(self) -> int:
        return len(self._registry)

    def __contains__(self, module_id: str) -> bool:
        return module_id in self._registry


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_registry_instance: ModuleRegistry | None = None


def get_module_registry() -> ModuleRegistry:
    """Return the module-level singleton ModuleRegistry."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ModuleRegistry()
    return _registry_instance


def register_module(record: ModuleRecord) -> None:
    """Convenience wrapper: register a module in the singleton registry."""
    get_module_registry().register_module(record)
