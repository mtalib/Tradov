#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG01_MainWindow.py
Purpose: Bridge module that redirects to the comprehensive SpyderG05 Dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-01-24 Time: 11:00:00

Module Description:
    This is a bridge module that imports and exports the comprehensive
    SpyderG05_TradingDashboard as SpyderMainWindow for backward compatibility
    with modules expecting SpyderG01_MainWindow. This allows us to use the
    full-featured SpyderG05 dashboard without modifying other modules that
    expect SpyderG01_MainWindow to exist.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import logging

# Import the comprehensive dashboard from SpyderG05
try:
    from .SpyderG05_TradingDashboard import SpyderTradingDashboard as SpyderMainWindow
    logging.info("✅ SpyderG01_MainWindow: Successfully bridged to SpyderG05_TradingDashboard")
    BRIDGE_SUCCESSFUL = True
except ImportError as e:
    logging.info(f"⚠️ SpyderG01_MainWindow: Could not import SpyderG05_TradingDashboard: {e}")
    # Try alternative import path
    try:
        from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard as SpyderMainWindow
        logging.info("✅ SpyderG01_MainWindow: Successfully bridged via alternative path")
        BRIDGE_SUCCESSFUL = True
    except ImportError as e2:
        logging.info(f"❌ SpyderG01_MainWindow: Failed to bridge to SpyderG05: {e2}")
        BRIDGE_SUCCESSFUL = False
        
        # Create a minimal fallback class
        from PySide6.QtWidgets import QMainWindow, QLabel
        from PySide6.QtCore import Qt
        
        class SpyderMainWindow(QMainWindow):
            """Minimal fallback if SpyderG05 is not available"""
            def __init__(self, *args, **kwargs):
                super().__init__()
                self.setWindowTitle("SPYDER - Bridge Error")
                self.setGeometry(100, 100, 600, 400)
                
                error_label = QLabel(
                    "Error: Could not load SpyderG05_TradingDashboard\n\n"
                    "Please ensure SpyderG05_TradingDashboard.py is in the SpyderG_GUI folder."
                )
                error_label.setAlignment(Qt.AlignCenter)
                error_label.setStyleSheet("color: red; font-size: 14px;")
                self.setCentralWidget(error_label)
                
                logging.info("❌ Using minimal fallback window - SpyderG05 not available")

# ==============================================================================
# COMPATIBILITY WRAPPER (Optional)
# ==============================================================================
class MainWindow(SpyderMainWindow):
    """
    Compatibility wrapper that ensures the MainWindow name is available.
    This inherits from SpyderMainWindow (which is actually SpyderG05_TradingDashboard).
    """
    def __init__(self, *args, **kwargs):
        # SpyderG05_TradingDashboard doesn't need the extra parameters
        # that SpyderA01_Main might try to pass, so we filter them out
        super().__init__()
        
        # Log that we're using the bridge
        logger = logging.getLogger(__name__)
        logger.info("SpyderG01_MainWindow bridge activated - using SpyderG05_TradingDashboard")
        
        # Add startup message if the dashboard supports it
        if hasattr(self, 'add_system_log'):
            self.add_system_log("✅ GUI initialized via SpyderG01 bridge to SpyderG05")

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = ['SpyderMainWindow', 'MainWindow']

# ==============================================================================
# MODULE INFO
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("SpyderG01_MainWindow - Bridge Module")
    print("=" * 60)
    print("This module bridges to SpyderG05_TradingDashboard")
    print(f"Bridge Status: {'✅ ACTIVE' if BRIDGE_SUCCESSFUL else '❌ FAILED'}")
    print("=" * 60)
    
    if BRIDGE_SUCCESSFUL:
        print("\nThe following features are available via SpyderG05:")
        print("  • Full market data display (30+ symbols)")
        print("  • Signal monitoring panel (12 indicators)")
        print("  • Position and order tracking")
        print("  • Risk management displays")
        print("  • Prometheus metrics monitoring")
        print("  • Real-time data integration")
        print("  • Professional dark theme")
        print("  • Tradier broker connectivity")
        print("  • Automated trading controls")
        print("\nNo functionality has been lost!")
    else:
        print("\n⚠️ Please ensure SpyderG05_TradingDashboard.py is available")
        print("   in the SpyderG_GUI folder for full functionality.")
