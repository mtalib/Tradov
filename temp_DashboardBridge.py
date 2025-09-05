# temp_DashboardBridge.py
import os
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path.cwd()))

# Configure display based on environment
if os.environ.get('SSH_CONNECTION'):
    print("SSH detected - using virtual display")
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
else:
    # Clear bad display settings
    if os.environ.get('DISPLAY') == ':99':
        del os.environ['DISPLAY']
    
    # Let PyQt6 auto-detect
    print("Local session - using native display")

# Now import PyQt6
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer

# Import your GUI components
try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    has_dashboard = True
except:
    has_dashboard = False
    print("Warning: Could not import TradingDashboard")

# Import the working components from headless
from temp_SpyderWorkingHeadless import SpyderHeadlessSystem

class SpyderDashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize headless engine
        self.engine = SpyderHeadlessSystem(mode='simulation')
        self.engine.initialize_system()
        self.engine.setup_simulation_mode()
        
        # Setup GUI
        self.setWindowTitle("Spyder Trading Dashboard")
        self.setGeometry(100, 100, 1400, 900)
        
        if has_dashboard:
            # Use actual dashboard
            self.dashboard = SpyderTradingDashboard()
            self.setCentralWidget(self.dashboard)
        else:
            # Simple fallback GUI
            from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
            widget = QWidget()
            layout = QVBoxLayout()
            
            self.status_label = QLabel("Spyder Trading System - Connected")
            self.spy_label = QLabel(f"SPY: ${self.engine.mock_spy_price:.2f}")
            
            layout.addWidget(self.status_label)
            layout.addWidget(self.spy_label)
            
            widget.setLayout(layout)
            self.setCentralWidget(widget)
        
        # Update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # Update every second
        
    def update_dashboard(self):
        """Update dashboard with engine data"""
        if hasattr(self, 'spy_label'):
            self.spy_label.setText(f"SPY: ${self.engine.mock_spy_price:.2f}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Check platform
    print(f"PyQt6 platform: {app.platformName()}")
    
    # Create and show dashboard
    window = SpyderDashboardApp()
    window.show()
    
    sys.exit(app.exec())
