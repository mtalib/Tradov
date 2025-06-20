#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderA_Core
Purpose: Core Trading Engine

This package contains the core components of the Spyder trading system,
including the main application, trading engine, configuration, scheduling,
and event management.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderA01_Main import SpyderApplication, main
from .SpyderA02_TradingEngine import TradingEngine, get_trading_engine
from .SpyderA03_Configuration import ConfigManager, get_config_manager
from .SpyderA04_Scheduler import TradingScheduler, get_scheduler
from .SpyderA05_EventManager import EventManager, Event, EventType, get_event_manager

# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    # Main application
    "SpyderApplication",
    "main",
    
    # Trading engine
    "TradingEngine",
    "get_trading_engine",
    
    # Configuration - Fixed class names
    "ConfigManager",
    "get_config_manager",
    
    # Scheduler - Fixed class names
    "TradingScheduler", 
    "get_scheduler",
    
    # Event management
    "EventManager",
    "Event",
    "EventType",
    "get_event_manager",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderA_Core"
__description__ = "Core Trading Engine Components"
__version__ = "1.4.0"
