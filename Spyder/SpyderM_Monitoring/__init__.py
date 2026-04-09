#!/usr/bin/env python3
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

import logging

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderM01_SystemMonitor import SystemMonitor, get_system_monitor
from .SpyderM03_AIAgentMonitor import AIAgentMonitor
from .SpyderM04_TradingMetrics import MetricsCollector, TradingMetrics

try:
    from .SpyderM05_TransactionCostAnalysis import TransactionCostAnalyzer
except ImportError as e:
    logging.info("Warning: SpyderM05_TransactionCostAnalysis not available: %s", e)
    TransactionCostAnalyzer = None  # type: ignore

try:
    from .SpyderM06_HMMRegimeDetector import SpyderM06_HMMRegimeDetector
except ImportError as e:
    logging.info("Warning: SpyderM06_HMMRegimeDetector not available: %s", e)
    SpyderM06_HMMRegimeDetector = None  # type: ignore

try:
    from .SpyderM07_MigrationMonitor import MigrationMonitor
except ImportError as e:
    logging.info("Warning: SpyderM07_MigrationMonitor not available: %s", e)
    MigrationMonitor = None  # type: ignore

try:
    from .SpyderM08_HealthEndpoint import HealthEndpoint, get_health_endpoint
except ImportError as e:
    logging.info("Warning: SpyderM08_HealthEndpoint not available: %s", e)
    HealthEndpoint = None  # type: ignore
    get_health_endpoint = None  # type: ignore

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
    # Additional M-series modules
    "TransactionCostAnalyzer",
    "SpyderM06_HMMRegimeDetector",
    "MigrationMonitor",
    # Health endpoint
    "HealthEndpoint",
    "get_health_endpoint",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderM_Monitoring"
__description__ = "System Monitoring and Analytics"
__version__ = "1.4.0"
