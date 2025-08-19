#!/bin/bash
# Fixed Wayland-compatible Spyder Dashboard Launcher

cd "/home/adam/Projects/Spyder"
source .venv/bin/activate

# Wayland-specific environment setup
export QT_QPA_PLATFORM=wayland
export QT_WAYLAND_FORCE_DPI=96

# Launch with fixed PyQt6 settings (no problematic attributes)
python3 -c "
import sys
import os
sys.path.insert(0, '.')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Create Qt application
app = QApplication(sys.argv)

# Set application properties for dock integration (no problematic attributes)
app.setApplicationName('python3')
app.setApplicationDisplayName('SPYDER Trading System')  
app.setApplicationVersion('1.0')
app.setOrganizationName('Spyder')
app.setDesktopFileName('spyder-trading')

# Create dashboard
dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')

# Show dashboard
dashboard.show()
dashboard.raise_()
dashboard.activateWindow()

print('✅ Dashboard launched successfully with Wayland optimization')
print('Window is now visible and ready for WM_CLASS detection')

app.exec()
"
