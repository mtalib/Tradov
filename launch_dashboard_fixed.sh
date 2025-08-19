#!/bin/bash
cd "/home/adam/Projects/Spyder"
source .venv/bin/activate

python3 -c "
import sys
sys.path.insert(0, '.')
from PyQt6.QtWidgets import QApplication
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

# Set application name for dock integration
app = QApplication(sys.argv)
app.setApplicationName('Python3')
app.setApplicationDisplayName('SPYDER Trading System')
app.setDesktopFileName('spyder-trading')

dashboard = SpyderTradingDashboard()
dashboard.setWindowTitle('SPYDER - Autonomous Options Trading System v1.0')
dashboard.show()
dashboard.raise_()
app.exec()
"
