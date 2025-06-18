#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderM_Monitoring
Purpose: System Monitoring

This package provides monitoring capabilities for the Spyder system including
system health, AI agents, and trading metrics.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderM01_SystemMonitor import SystemMonitor, get_system_monitor
from .SpyderM03_AIAgentMonitor import AIAgentMonitor
from .SpyderM04_TradingMetrics import TradingMetrics, MetricsCollector

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # System monitoring
    "SystemMonitor",
    "get_system_monitor",
    
    # AI monitoring
    "AIAgentMonitor",
    
    # Trading metrics
    "TradingMetrics",
    "MetricsCollector",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderM_Monitoring"
__description__ = "System Monitoring and Analytics"
__version__ = "1.4.0"