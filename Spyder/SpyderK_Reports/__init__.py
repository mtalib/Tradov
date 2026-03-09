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

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderK01_ReportGenerator import ReportGenerator
from .SpyderK05_RiskReport import RiskReportGenerator
from .SpyderK07_StrategyComparison import StrategyComparisonAnalyzer

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "ReportGenerator",
    "RiskReportGenerator",
    "StrategyComparisonAnalyzer",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
