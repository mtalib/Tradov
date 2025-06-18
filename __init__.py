#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Main package initialization.

Author: Mohamed Talib
Date: 2025-06-18
Version: 1.4
"""

__version__ = "1.4.0"
__author__ = "Mohamed Talib"
__description__ = "Automated SPY Options Trading System"

# Core imports for easy access
try:
    from SpyderA_Core.SpyderA01_Main import SpyderApplication
    from SpyderA_Core.SpyderA03_Configuration import get_config
    from SpyderA_Core.SpyderA05_EventManager import get_event_manager
    from SpyderB_Broker.SpyderB01_IBClient import get_ib_client
    from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    
    __all__ = [
        "SpyderApplication",
        "get_config",
        "get_event_manager",
        "get_ib_client",
        "get_risk_manager",
        "SpyderLogger",
    ]
    
except ImportError as e:
    # Handle missing modules gracefully during development
    print(f"Warning: Some Spyder modules not available: {e}")
    __all__ = []
