#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# Add project root
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

def main():
    # Import Qt FIRST and set properties IMMEDIATELY
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QCoreApplication
    
    # Set application properties BEFORE creating QApplication
    QCoreApplication.setApplicationName("spyder-trading-system")
    
    # Create app instance
    app = QApplication(sys.argv)
    app.setApplicationName("spyder-trading-system")
    app.setDesktopFileName("spyder-trading-system")
    
    # Import and launch Spyder GUI components directly
    try:
        from SpyderG_GUI.SpyderG05_TradingDashboard import TradingDashboard
        dashboard = TradingDashboard()
        
        # Set window properties
        dashboard.setWindowTitle("Spyder Options Trading System")
        dashboard.show()
        
        print("✅ Minimal Qt launcher started")
        return app.exec()
        
    except ImportError:
        print("❌ Could not import TradingDashboard")
        return 1

if __name__ == "__main__":
    sys.exit(main())
