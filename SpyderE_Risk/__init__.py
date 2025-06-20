#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderE_Risk
Purpose: Risk Management

This package provides comprehensive risk management functionality including
position sizing, stop loss management, and drawdown control.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderE01_RiskManager import RiskManager, get_risk_manager
from .SpyderE02_PositionSizer import PositionSizer, SizingMethod
from .SpyderE03_StopLossManager import StopLossManager, StopType  # Changed from StopLossType
from .SpyderE04_DrawdownControl import DrawdownController
from .SpyderE06_RiskMetrics import RiskMetrics, PortfolioRisk

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Risk management
    "RiskManager",
    "get_risk_manager",
    
    # Position sizing
    "PositionSizer",
    "SizingMethod",
    
    # Stop loss
    "StopLossManager",
    "StopType",  # Changed from StopLossType
    
    # Drawdown control
    "DrawdownController",
    
    # Risk metrics
    "RiskMetrics",
    "PortfolioRisk",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderE_Risk"
__description__ = "Risk Management Systems"
__version__ = "1.4.0"
