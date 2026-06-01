#!/usr/bin/env python3
"""
SPYDER - Automated SPX Options Trading System

Package: SpyderR_Runtime
Purpose: Runtime Operations

This package contains runtime execution engines for paper trading
and live trading operations.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
# from .SpyderR02_PaperEngine import PaperTradingEngine
# from .SpyderR03_PaperMonitor import PaperTradingMonitor
# from .SpyderR04_LiveEngine import LiveTradingEngine

import logging

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
try:
    from .SpyderR06_PaperTradingHarness import PaperTradingHarness
except ImportError as e:
    logging.info("Warning: SpyderR06_PaperTradingHarness not available: %s", e)
    PaperTradingHarness = None  # type: ignore

try:
    from .SpyderR07_LiveDashboard import SpyderLiveDashboardLauncher
except ImportError as e:
    logging.info("Warning: SpyderR07_LiveDashboard not available: %s", e)
    SpyderLiveDashboardLauncher = None  # type: ignore

try:
    from .SpyderR09_ProductionDeploymentManager import ProductionDeploymentManager
except ImportError as e:
    logging.info("Warning: SpyderR09_ProductionDeploymentManager not available: %s", e)
    ProductionDeploymentManager = None  # type: ignore

try:
    from .SpyderR02_PaperEngine import PaperTradingEngine
except ImportError as e:
    logging.info("Warning: SpyderR02_PaperEngine not available: %s", e)
    PaperTradingEngine = None  # type: ignore

try:
    from .SpyderR03_PaperMonitor import PaperTradingMonitor
except ImportError as e:
    logging.info("Warning: SpyderR03_PaperMonitor not available: %s", e)
    PaperTradingMonitor = None  # type: ignore

try:
    from .SpyderR04_LiveEngine import LiveEngine
except ImportError as e:
    logging.info("Warning: SpyderR04_LiveEngine not available: %s", e)
    LiveEngine = None  # type: ignore

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__: list[str] = [
    "PaperTradingHarness",
    "SpyderLiveDashboardLauncher",
    "ProductionDeploymentManager",
    "PaperTradingEngine",
    "PaperTradingMonitor",
    "LiveEngine",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderR_Runtime"
__description__ = "Runtime Execution Engines"
__version__ = "1.4.0"
