#!/bin/bash
# Wayland-compatible Spyder Dashboard Launcher

cd "/home/adam/Projects/Spyder"
source .venv/bin/activate

# Wayland-specific environment setup
export QT_QPA_PLATFORM=wayland
export QT_WAYLAND_FORCE_DPI=96

# Launch with Wayland-optimized PyQt6 settings
python3 -c "
import sys
import os
sys.path.insert(0, '.')

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Wayland-specific Qt settings
app = QApplication(sys.argv)

# Set application properties for Wayland dock integration
app.setApplicationName('python3')
app.setApplicationDisplayName('SPYDER Trading System')  
app.setApplicationVersion('1.0')
app.setOrganizationName('Spyder')
app.setDesktopFileName('spyder-trading')

# Additional Wayland-specific properties
app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)

# Create dashboard
dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')

# Wayland window properties
dashboard.show()
dashboard.raise_()
dashboard.activateWindow()

# Set window class explicitly (Wayland method)
if hasattr(dashboard, 'winId'):
    dashboard.setProperty('_q_wayland_window_type', 'normal')

print('Dashboard launched with Wayland optimization')
app.exec()
"
