import logging
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderA_Core
Purpose: Core system functionality and orchestration
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-29

Package Description:
    The SpyderA_Core package provides the fundamental system components including
    the main application, trading engine, configuration management, scheduling,
    event management, and master controller. This is the heart of the Spyder
    trading system that coordinates all other modules.

Modules Overview:
    • SpyderA01_Main: Main application entry point and GUI coordination
    • SpyderA02_TradingEngine: Core trading engine and execution logic
    • SpyderA03_Configuration: System configuration management
    • SpyderA04_Scheduler: Task scheduling and timing coordination
    • SpyderA05_EventManager: System-wide event management
    • SpyderA06_MasterController: Master system controller and coordination
    • SpyderA08_FSeriesOrchestrator: F-Series strategy orchestration

Key Features:
    • Centralized system control and coordination
    • Event-driven architecture support
    • Configuration management and validation
    • Automated task scheduling
    • Master/slave controller architecture
"""

# ==============================================================================
# VERSION INFORMATION
# ==============================================================================
__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"
__status__ = "Production"

# ==============================================================================
# CORE MODULE IMPORTS
# ==============================================================================
# NOTE: SpyderA01_Main is intentionally NOT imported here.
# It is the application entry point and loads the full GUI (matplotlib, plotly,
# PySide6) at module level, adding 2+ seconds whenever any A-series module is
# imported. Import SpyderA01_Main directly only where the application is
# actually being launched: python SpyderA_Core/SpyderA01_Main.py

# Trading Engine
# NOTE: SpyderA02_TradingEngine is also deferred from eager loading.
# It transitively imports SpyderE_Risk → SpyderC_MarketData → transformers
# which adds 2.5+ seconds to any import of an A-series module.
# Import SpyderA02_TradingEngine directly where TradingEngine is required.

# Configuration
try:
    from . import SpyderA03_Configuration
except ImportError as e:
    logging.info("Warning: Could not import Configuration: %s", e)

# Scheduler
try:
    from . import SpyderA04_Scheduler
except ImportError as e:
    logging.info("Warning: Could not import Scheduler: %s", e)

# Event Manager
try:
    from . import SpyderA05_EventManager
except ImportError as e:
    logging.info("Warning: Could not import EventManager: %s", e)

# Master Controller
try:
    from . import SpyderA06_MasterController
except ImportError as e:
    logging.info("Warning: Could not import MasterController: %s", e)

# F-Series Orchestrator
try:
    from . import SpyderA08_FSeriesOrchestrator
except ImportError as e:
    logging.info("Warning: Could not import FSeriesOrchestrator: %s", e)

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Note: SpyderApplication/SpyderMainWindow/SpyderConfig not exported (see A01_Main comment).
    # Note: TradingEngine/EngineState/StrategyInfo not exported (see A02 comment).
    # Module references
    "SpyderA03_Configuration",
    "SpyderA04_Scheduler",
    "SpyderA05_EventManager",
    "SpyderA06_MasterController",
    "SpyderA08_FSeriesOrchestrator",
]

# ==============================================================================
# PACKAGE CONFIGURATION
# ==============================================================================
CORE_CONFIG = {
    "max_concurrent_tasks": 10,
    "event_queue_size": 1000,
    "heartbeat_interval": 30,  # seconds
    "system_timeout": 300,  # seconds
}


def get_package_info():
    """Get package information"""
    return {
        "name": "SpyderA_Core",
        "version": __version__,
        "author": __author__,
        "description": "Core system functionality and orchestration",
        "modules": len(__all__),
        "config": CORE_CONFIG,
    }
