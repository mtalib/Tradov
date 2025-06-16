#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderE_Risk
Purpose: Risk Management Systems

This package provides risk management systems functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderE01_RiskManager import RiskManager, get_risk_manager
from .SpyderE02_PositionSizer import PositionSizer, get_position_sizer
from .SpyderE03_StopLossManager import StopLossManager
from .SpyderE04_DrawdownControl import DrawdownController
from .SpyderE05_PortfolioAllocator import PortfolioAllocator
from .SpyderE06_RiskMetrics import RiskMetricsCalculator
from .SpyderE07_StrategyHealthMonitor import StrategyHealthMonitor

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "DrawdownController",
    "PortfolioAllocator",
    "PositionSizer",
    "RiskManager",
    "RiskMetricsCalculator",
    "StopLossManager",
    "StrategyHealthMonitor",
    "get_position_sizer",
    "get_risk_manager",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "{package_name}"
__description__ = "{description}"
__version__ = "1.4.0"
