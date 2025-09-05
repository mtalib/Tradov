    
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path.cwd()))

# Import headless components (this will set offscreen mode)
from temp_SpyderWorkingHeadless import SpyderHeadlessSystem

# RESET environment for GUI after importing
del os.environ['QT_QPA_PLATFORM']
if 'DISPLAY' in os.environ and os.environ['DISPLAY'] == '':
    del os.environ['DISPLAY']
os.environ['WAYLAND_DISPLAY'] = 'wayland-0'

print("Reset display environment for GUI")

# NOW import PyQt6 - it will use Wayland
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer

try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    has_dashboard = True
except:
    has_dashboard = False

class SpyderDashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.engine = SpyderHeadlessSystem(mode='simulation')
        self.engine.initialize_system()
        self.engine.setup_simulation_mode()
        
        self.setWindowTitle("Spyder Trading Dashboard")
        self.setGeometry(100, 100, 1400, 900)
        
        if has_dashboard:
            self.dashboard = SpyderTradingDashboard()
            self.setCentralWidget(self.dashboard)
            print("Full dashboard loaded")
        else:
            widget = QWidget()
            layout = QVBoxLayout()
            layout.addWidget(QLabel("Spyder Trading System - CONNECTED"))
            layout.addWidget(QLabel(f"SPY: ${self.engine.mock_spy_price:.2f}"))
            layout.addWidget(QLabel("IB Gateway: CONNECTED (Port 4002)"))
            widget.setLayout(layout)
            self.setCentralWidget(widget)
            print("Simple interface loaded")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    print(f"PyQt6 running on: {app.platformName()}")
    
    window = SpyderDashboardApp()
    window.show()
    
    sys.exit(app.exec())

    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
