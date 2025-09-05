import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path.cwd()))

# DON'T force any display mode - let PyQt6 auto-detect
print("Using native display detection")

# Import PyQt6 first to test
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtCore import QTimer

# Import Spyder components
from temp_SpyderWorkingHeadless import SpyderHeadlessSystem

# Try to import dashboard
try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    has_dashboard = True
except:
    has_dashboard = False

class SpyderDashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize engine
        self.engine = SpyderHeadlessSystem(mode='simulation')
        self.engine.initialize_system()
        self.engine.setup_simulation_mode()
        
        # Setup window
        self.setWindowTitle("Spyder Trading Dashboard")
        self.setGeometry(100, 100, 1400, 900)
        
        if has_dashboard:
            self.dashboard = SpyderTradingDashboard()
            self.setCentralWidget(self.dashboard)
        else:
            widget = QWidget()
            layout = QVBoxLayout()
            layout.addWidget(QLabel("Spyder Trading System"))
            layout.addWidget(QLabel(f"SPY: ${self.engine.mock_spy_price:.2f}"))
            widget.setLayout(layout)
            self.setCentralWidget(widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    print(f"PyQt6 platform: {app.platformName()}")
    
    window = SpyderDashboardApp()
    window.show()
    
    sys.exit(app.exec())
