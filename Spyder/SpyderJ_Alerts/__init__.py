#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Package: SpyderJ_Alerts
Purpose: Notification Systems

This package provides notification systems functionality for the Spyder trading system.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS
# ==============================================================================
from .SpyderJ01_AlertManager import AlertManager
from .SpyderJ02_EmailNotifier import EmailNotifier
from .SpyderJ04_DesktopNotifier import DesktopNotifier

# Import TelegramBot with proper error handling
try:
    from .SpyderJ05_TelegramBot import TelegramBot

    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    # Create a dummy class for missing dependency

    class TelegramBot:
        def __init__(self, *args, **kwargs):
            raise ImportError("TelegramBot not available - install dependencies")


# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================
__all__ = [
    "AlertManager",
    "DesktopNotifier",
    "EmailNotifier",
    "TelegramBot",
]

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__package_name__ = "SpyderJ_Alerts"
__description__ = "Notification Systems"
__version__ = "1.4.0"
