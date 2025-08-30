#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Qt Wrapper with Dock Icon Fix - Fixed for PyQt6
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

def fix_qt_application_properties():
    """Set Qt application properties before any GUI creation"""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QCoreApplication
        
        # CRITICAL: Set these BEFORE creating QApplication instance
        QCoreApplication.setApplicationName("spyder-trading-system")
        QCoreApplication.setOrganizationName("SpyderTrading")
        QCoreApplication.setOrganizationDomain("spyder.local")
        QCoreApplication.setApplicationVersion("1.0.0")
        
        # Create application instance
        if QApplication.instance() is None:
            app = QApplication(sys.argv)
        else:
            app = QApplication.instance()
        
        # Set additional properties after creation
        app.setApplicationName("spyder-trading-system")
        app.setApplicationDisplayName("Spyder Options Trading System")
        
        # CRITICAL: Set the desktop file name to match our .desktop file
        app.setDesktopFileName("spyder-trading-system")
        
        print("✅ Qt6 application properties set for dock icon fix")
        return app
        
    except ImportError:
        try:
            # Fallback to PyQt5
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import QCoreApplication, Qt
            
            QCoreApplication.setApplicationName("spyder-trading-system")
            QCoreApplication.setOrganizationName("SpyderTrading")
            
            if QApplication.instance() is None:
                app = QApplication(sys.argv)
            else:
                app = QApplication.instance()
                
            app.setApplicationName("spyder-trading-system")
            
            # PyQt5 attributes (these work in PyQt5)
            app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
            app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
            
            print("✅ Qt5 application properties set")
            return app
            
        except ImportError:
            print("❌ No Qt libraries available")
            return None

def set_window_properties(window):
    """Set window properties to match desktop launcher"""
    if window is None:
        return
    
    try:
        # Set window class name (this is what appears in wmctrl)
        window.setWindowTitle("Spyder Options Trading System")
        
        # For Qt6/Qt5
        if hasattr(window, 'setWindowRole'):
            window.setWindowRole("spyder-main-window")
            
        # Set window class hints for X11/Wayland
        if hasattr(window, 'winId'):
            win_id = window.winId()
            print(f"✅ Window ID: {win_id}")
            
        print("✅ Window properties configured")
        
    except Exception as e:
        print(f"⚠️ Could not set window properties: {e}")

def launch_spyder_dashboard():
    """Launch Spyder dashboard with proper dock icon handling"""
    
    # STEP 1: Set up Qt application properties FIRST
    app = fix_qt_application_properties()
    if not app:
        return False
    
    # STEP 2: Import and create the dashboard
    try:
        from SpyderG_GUI.SpyderG05_TradingDashboard import TradingDashboard
        
        print("🚀 Creating Spyder Trading Dashboard...")
        dashboard = TradingDashboard()
        
        # STEP 3: Set window properties
        set_window_properties(dashboard)
        
        # STEP 4: Show the window
        dashboard.show()
        
        print("✅ Spyder Dashboard launched with dock icon fix")
        print("📌 Window should now appear as single icon in dock")
        
        # STEP 5: Run the application
        return app.exec()
        
    except ImportError as e:
        print(f"⚠️ TradingDashboard import failed: {e}")
        
        # Fallback to MainWindow
        try:
            from SpyderG_GUI.SpyderG01_MainWindow import MainWindow
            
            print("🚀 Creating Spyder Main Window (fallback)...")
            window = MainWindow()
            set_window_properties(window)
            window.show()
            
            print("✅ Spyder Main Window launched")
            return app.exec()
            
        except ImportError as e2:
            print(f"❌ MainWindow also failed: {e2}")
            return False
    
    except Exception as e:
        print(f"❌ Dashboard launch failed: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Starting Spyder with Dock Icon Fix...")
    print("=" * 50)
    
    success = launch_spyder_dashboard()
    
    if success:
        print("✅ Spyder launched successfully")
    else:
        print("❌ Spyder launch failed")
        
    sys.exit(0 if success else 1)
