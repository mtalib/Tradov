# ==============================================================================
# IMPORT AND TYPE ANNOTATION FIXES
# Apply these changes to SpyderG05_TradingDashboard.py and SpyderB08_MultiClientDataManager.py
# ==============================================================================

# ==============================================================================
# BEFORE (Deprecated/Problematic Imports)
# ==============================================================================
"""
# ❌ OLD DEPRECATED STYLE - REMOVE THESE:
from typing import Dict, List, Optional, Tuple, Any
from datetime import timedelta
import os  # If unused
import traceback  # If unused
"""

# ==============================================================================
# AFTER (Modern Python 3.10+ Style)
# ==============================================================================

# Standard library imports (keep only what you actually use)
from datetime import datetime, date  # Not timedelta unless you use it
from decimal import Decimal
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable  # Keep these as they don't have built-in equivalents

# PyQt6 imports (correct)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QLabel, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

# Third-party imports
import numpy as np
import pandas as pd

# Local imports (correct)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler


# ==============================================================================
# TYPE ANNOTATIONS - MODERN STYLE
# ==============================================================================

# ✅ CORRECT: Use built-in types directly (Python 3.9+)
def process_market_data(
    symbols: list[str],              # ✅ Not List[str]
    prices: dict[str, float],        # ✅ Not Dict[str, float]
    metadata: dict[str, Any]         # ✅ Any still from typing
) -> tuple[bool, str, float | None]:  # ✅ Use | for Optional, not Optional[float]
    """Process market data with modern type hints."""
    return True, "Success", 150.25


# Class with proper type annotations
@dataclass
class MarketDataTick:
    """Market data tick with proper annotations."""
    
    symbol: str
    timestamp: datetime
    bid: float | None = None         # ✅ Use | None instead of Optional
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    client_id: int = 0
    tick_type: str = "market_data"
    metadata: dict[str, Any] = field(default_factory=dict)  # ✅ dict not Dict


# Class with instance attributes properly typed
class TradingDashboard:
    """Trading dashboard with proper initialization."""
    
    def __init__(self) -> None:
        """Initialize dashboard - ALL attributes must be initialized here."""
        
        # ✅ CORRECT: Initialize ALL QWidget attributes
        self.status_label: QLabel = QLabel("Status: Initializing")
        self.connection_button: QPushButton = QPushButton("Connect")
        self.price_label: QLabel = QLabel("Price: --")
        
        # ✅ CORRECT: Initialize data structures
        self.market_data: dict[str, float] = {}
        self.active_symbols: list[str] = []
        self.callbacks: list[Callable] = []
        
        # ✅ CORRECT: Initialize state flags
        self.is_connected: bool = False
        self.is_running: bool = False
        
        # ✅ CORRECT: Initialize timers (can be None initially)
        self.update_timer: QTimer | None = None
        
        # ⚠️ IMPORTANT: Never do this:
        # self.some_widget  # ❌ Declared but not initialized - causes "None" errors!
        
    def setup_ui(self) -> None:
        """Setup UI - widget attributes already initialized in __init__."""
        # ✅ Now safe to use these widgets
        self.status_label.setText("Ready")
        self.connection_button.clicked.connect(self.connect_to_ib)
        
    def update_price(self, symbol: str, price: float) -> None:
        """Update price display."""
        # ✅ Safe - price_label was initialized in __init__
        self.price_label.setText(f"Price: ${price:.2f}")


# ==============================================================================
# COMMON PITFALLS TO AVOID
# ==============================================================================

class BadExample:
    """Example of what NOT to do."""
    
    def __init__(self) -> None:
        # ❌ BAD: Widget declared but not initialized
        self.some_label: QLabel
        
        # ❌ BAD: Using deprecated Optional
        self.data: Optional[dict] = None  # Use dict | None instead
        
        # ❌ BAD: Using old-style type hints
        self.prices: Dict[str, float] = {}  # Use dict[str, float]
        
    def update_display(self) -> None:
        # ❌ THIS WILL CRASH: some_label is None!
        self.some_label.setText("Update")  # AttributeError!


class GoodExample:
    """Example of correct implementation."""
    
    def __init__(self) -> None:
        # ✅ GOOD: Widget initialized immediately
        self.some_label: QLabel = QLabel("Initial Text")
        
        # ✅ GOOD: Using modern type hints
        self.data: dict | None = None
        
        # ✅ GOOD: Using built-in types
        self.prices: dict[str, float] = {}
        
    def update_display(self) -> None:
        # ✅ THIS WORKS: some_label is a QLabel instance
        self.some_label.setText("Update")


# ==============================================================================
# FUNCTION WITH COMPLEX RETURN TYPE
# ==============================================================================

def analyze_trading_opportunity(
    symbol: str,
    current_price: float,
    historical_data: list[dict[str, Any]]
) -> tuple[bool, str, dict[str, float] | None]:
    """
    Analyze trading opportunity.
    
    Returns:
        Tuple of (success, message, analysis_data or None)
    """
    try:
        # Analysis logic here
        analysis = {
            'entry_price': 150.0,
            'stop_loss': 145.0,
            'target': 160.0
        }
        return True, "Opportunity found", analysis
        
    except Exception as e:
        return False, f"Analysis failed: {e}", None


# ==============================================================================
# CALLABLE TYPE ANNOTATIONS
# ==============================================================================

def register_callback(
    callback: Callable[[str, float], None]  # Function taking (str, float) returning None
) -> bool:
    """Register a callback function."""
    try:
        # Store callback
        return True
    except Exception:
        return False


# Callback function matching the signature above
def price_update_callback(symbol: str, price: float) -> None:
    """Callback for price updates."""
    print(f"{symbol}: ${price:.2f}")


# ==============================================================================
# ASYNC FUNCTIONS (if using asyncio)
# ==============================================================================

import asyncio

async def fetch_market_data_async(
    symbol: str,
    timeout: float = 30.0
) -> dict[str, float] | None:
    """Fetch market data asynchronously."""
    try:
        await asyncio.sleep(1)  # Simulate API call
        return {
            'bid': 150.0,
            'ask': 150.1,
            'last': 150.05
        }
    except Exception as e:
        print(f"Error: {e}")
        return None


# ==============================================================================
# TYPE ALIASES FOR COMPLEX TYPES
# ==============================================================================

# Define type aliases for readability
MarketDataDict = dict[str, float]
SymbolList = list[str]
PriceHistoryCallback = Callable[[str, list[float]], None]

def process_with_aliases(
    data: MarketDataDict,
    symbols: SymbolList,
    callback: PriceHistoryCallback
) -> bool:
    """Process data using type aliases."""
    return True
