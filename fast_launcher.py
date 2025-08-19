#!/usr/bin/env python3
"""
SPYDER Fast Launcher - Direct to Dashboard
Bypasses splash screen and startup checks for maximum speed
"""

import sys
import os
from pathlib import Path

def fast_launch():
    """Launch dashboard directly with minimal overhead"""
    
    # Set working directory
    spyder_home = Path.home() / "Projects/Spyder"
    os.chdir(spyder_home)
    
    # Add to Python path
    sys.path.insert(0, str(spyder_home))
    
    # Import and launch directly
    try:
        from PyQt6.QtWidgets import QApplication
        from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
        
        # Create Qt application
        app = QApplication(sys.argv)
        app.setApplicationName("Spyder Enhanced Trading")
        
        # Create and show dashboard directly
        dashboard = SpyderTradingDashboard()
        dashboard.show()
        
        # Add fast launch log entry
        dashboard.add_system_log("🚀 Fast launcher - Direct dashboard launch")
        dashboard.add_automation_log("Lightning-fast startup completed")
        
        # Run application
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"❌ Fast launch failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    fast_launch()
