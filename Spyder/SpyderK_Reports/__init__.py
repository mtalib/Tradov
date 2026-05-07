#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderK_Reports
Purpose: Analytics & Reporting

This package provides analytics & reporting functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""
import logging

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderK01_ReportGenerator import (
    ReportFormat,
    ReportType,
    ReportMetadata,
    ReportRequest,
    ReportResult,
    ReportGeneratorProtocol,
    BaseReportGenerator,
    ReportGenerator,          # backward-compat alias
)
from .SpyderK05_RiskReport import RiskReportGenerator
from .SpyderK07_StrategyComparison import StrategyComparisonAnalyzer

# K13 — live per-strategy P&L attribution ladder
try:
    from .SpyderK13_StrategyPnLLadder import (
        StrategyPnLLadder,
        StrategyRow,
        PnLLadderSnapshot,
        get_ladder,
    )
    K13_AVAILABLE = True
except ImportError:
    K13_AVAILABLE = False

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # K01 — base interface
    "ReportFormat",
    "ReportType",
    "ReportMetadata",
    "ReportRequest",
    "ReportResult",
    "ReportGeneratorProtocol",
    "BaseReportGenerator",
    "ReportGenerator",
    # K05, K07
    "RiskReportGenerator",
    "StrategyComparisonAnalyzer",
    # K13 — P&L ladder
    "StrategyPnLLadder",
    "StrategyRow",
    "PnLLadderSnapshot",
    "get_ladder",
]

# ==============================================================================
# K02–K04, K06, K08–K12 — additional report modules
try:
    from .SpyderK02_DailyTradingReport import DailyTradingReport
    __all__.extend(["DailyTradingReport"])
except ImportError as e:
    logging.debug("Optional module SpyderK02_DailyTradingReport not available: %s", e)

try:
    from .SpyderK03_PerformanceDashboard import PerformanceDashboard
    __all__.extend(["PerformanceDashboard"])
except ImportError as e:
    logging.debug("Optional module SpyderK03_PerformanceDashboard not available: %s", e)

try:
    from .SpyderK04_ExecutionAnalytics import ExecutionAnalytics
    __all__.extend(["ExecutionAnalytics"])
except ImportError as e:
    logging.debug("Optional module SpyderK04_ExecutionAnalytics not available: %s", e)

try:
    from .SpyderK06_PortfolioAnalytics import PortfolioAnalytics
    __all__.extend(["PortfolioAnalytics"])
except ImportError as e:
    logging.debug("Optional module SpyderK06_PortfolioAnalytics not available: %s", e)

try:
    from .SpyderK08_MLPerformanceReport import MLPerformanceReport
    __all__.extend(["MLPerformanceReport"])
except ImportError as e:
    logging.debug("Optional module SpyderK08_MLPerformanceReport not available: %s", e)

try:
    from .SpyderK09_RegulatoryReports import RegulatoryReports
    __all__.extend(["RegulatoryReports"])
except ImportError as e:
    logging.debug("Optional module SpyderK09_RegulatoryReports not available: %s", e)

try:
    from .SpyderK10_RealTimePerformanceAnalytics import RealTimePerformanceMonitor
    __all__.extend(["RealTimePerformanceMonitor"])
except ImportError as e:
    logging.debug("Optional module SpyderK10_RealTimePerformanceAnalytics not available: %s", e)

try:
    from .SpyderK11_UnifiedSharpeDashboard import UnifiedSharpeDashboard
    __all__.extend(["UnifiedSharpeDashboard"])
except ImportError as e:
    logging.debug("Optional module SpyderK11_UnifiedSharpeDashboard not available: %s", e)

try:
    from .SpyderK12_InstitutionalTearSheet import InstitutionalTearSheet
    __all__.extend(["InstitutionalTearSheet"])
except ImportError as e:
    logging.debug("Optional module SpyderK12_InstitutionalTearSheet not available: %s", e)

# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderK_Reports"
__description__ = "Analytics & Reporting"
__version__ = "1.4.1"
