#!/bin/bash
# ===============================================================================
# SPYDER - Dashboard Launcher Script
# Purpose: Launch the complete Spyder Dashboard with GUI
# This is what runs when you single-click the SPY icon
# ===============================================================================

# Configuration
SPYDER_HOME="/home/adam/Projects/Spyder"
VENV_PATH="$SPYDER_HOME/.venv"
LOG_DIR="$SPYDER_HOME/logs/system"
PID_DIR="$SPYDER_HOME/.pids"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Create necessary directories
mkdir -p "$LOG_DIR" "$PID_DIR"

# ===============================================================================
# STARTUP FUNCTIONS
# ===============================================================================

activate_venv() {
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        return 0
    else
        echo -e "${RED}Virtual environment not found${NC}"
        return 1
    fi
}

check_ib_gateway() {
    if pgrep -f "ibgateway" > /dev/null || netstat -tuln 2>/dev/null | grep -q ":7497"; then
        return 0
    else
        return 1
    fi
}

start_trading_engine() {
    # Check if already running
    if [ -f "$PID_DIR/engine.pid" ]; then
        local pid=$(cat "$PID_DIR/engine.pid")
        if kill -0 "$pid" 2>/dev/null; then
            echo "Trading Engine already running (PID: $pid)"
            return 0
        fi
    fi
    
    # Start the engine
    cd "$SPYDER_HOME"
    
    # Try main engine first
    if [ -f "SpyderA_Core/SpyderA01_Main.py" ]; then
        nohup python3 -u SpyderA_Core/SpyderA01_Main.py > "$LOG_DIR/engine.log" 2>&1 &
    elif [ -f "test_engine.py" ]; then
        nohup python3 -u test_engine.py > "$LOG_DIR/engine.log" 2>&1 &
    else
        # Create a minimal engine placeholder
        cat > /tmp/temp_engine.py << 'EOF'
import time
from datetime import datetime
print(f"[{datetime.now()}] Placeholder Trading Engine started")
while True:
    time.sleep(30)
    print(f"[{datetime.now()}] Engine heartbeat...")
EOF
        nohup python3 -u /tmp/temp_engine.py > "$LOG_DIR/engine.log" 2>&1 &
    fi
    
    local engine_pid=$!
    echo $engine_pid > "$PID_DIR/engine.pid"
    sleep 2
    
    if kill -0 $engine_pid 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

launch_dashboard_gui() {
    # Check if GUI is already running
    if pgrep -f "SpyderG05_TradingDashboard" > /dev/null; then
        echo "Dashboard already running"
        # Bring to front if possible
        wmctrl -a "Spyder Trading Dashboard" 2>/dev/null || true
        return 0
    fi
    
    cd "$SPYDER_HOME"
    
    # Try to launch the main dashboard
    if [ -f "SpyderG_GUI/SpyderG05_TradingDashboard.py" ]; then
        python3 SpyderG_GUI/SpyderG05_TradingDashboard.py > "$LOG_DIR/dashboard.log" 2>&1 &
    elif [ -f "SpyderG05_TradingDashboard.py" ]; then
        python3 SpyderG05_TradingDashboard.py > "$LOG_DIR/dashboard.log" 2>&1 &
    else
        # Create a simple PyQt6 dashboard placeholder
        cat > /tmp/temp_dashboard.py << 'EOF'
#!/usr/bin/env python3
"""Spyder Trading Dashboard - Placeholder"""

import sys
from datetime import datetime

try:
    from PyQt6.QtWidgets import *
    from PyQt6.QtCore import *
    from PyQt6.QtGui import *
    
    class SpyderDashboard(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Spyder Trading Dashboard")
            self.setGeometry(100, 100, 1200, 800)
            
            # Dark theme
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1a1a2e;
                }
                QLabel {
                    color: #ffffff;
                    font-size: 14px;
                }
                QPushButton {
                    background-color: #0f3460;
                    color: white;
                    border: 1px solid #4a90e2;
                    padding: 8px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #16213e;
                }
            """)
            
            # Central widget
            central = QWidget()
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            
            # Title
            title = QLabel("SPYDER TRADING SYSTEM")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet("font-size: 24px; font-weight: bold; color: #4a90e2; padding: 20px;")
            layout.addWidget(title)
            
            # Status
            status = QLabel(f"Dashboard Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            status.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(status)
            
            # Info panel
            info = QTextEdit()
            info.setReadOnly(True)
            info.setStyleSheet("""
                QTextEdit {
                    background-color: #0a0a0a;
                    color: #00ff00;
                    font-family: monospace;
                    font-size: 12px;
                    border: 2px solid #4a90e2;
                    padding: 10px;
                }
            """)
            info.append("═══════════════════════════════════════")
            info.append(" SPYDER TRADING DASHBOARD - PLACEHOLDER")
            info.append("═══════════════════════════════════════")
            info.append("")
            info.append("Status: Waiting for full implementation")
            info.append("IB Gateway: Checking...")
            info.append("Trading Engine: Checking...")
            info.append("")
            info.append("This is a placeholder dashboard.")
            info.append("The full dashboard modules are not loaded.")
            info.append("")
            info.append("Available Features:")
            info.append("  • System Status Display")
            info.append("  • Basic Controls")
            info.append("  • Log Viewer")
            layout.addWidget(info)
            
            # Buttons
            btn_layout = QHBoxLayout()
            
            refresh_btn = QPushButton("Refresh Status")
            refresh_btn.clicked.connect(lambda: info.append(f"[{datetime.now().strftime('%H:%M:%S')}] Status refreshed"))
            btn_layout.addWidget(refresh_btn)
            
            monitor_btn = QPushButton("Open Monitor")
            monitor_btn.clicked.connect(self.open_monitor)
            btn_layout.addWidget(monitor_btn)
            
            stop_btn = QPushButton("Stop System")
            stop_btn.clicked.connect(self.close)
            btn_layout.addWidget(stop_btn)
            
            layout.addLayout(btn_layout)
            
        def open_monitor(self):
            import subprocess
            subprocess.Popen(['gnome-terminal', '--', 
                            '/home/adam/Projects/Spyder/SpyderQ_Scripts/SpyderQ21_Monitor.sh'])
    
    app = QApplication(sys.argv)
    app.setApplicationName("Spyder Trading")
    
    # Set application icon if available
    icon_path = "/home/adam/Projects/Spyder/assets/spyder-icon.png"
    if QFile.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    dashboard = SpyderDashboard()
    dashboard.show()
    
    sys.exit(app.exec())
    
except ImportError as e:
    print(f"PyQt6 not installed: {e}")
    print("Install with: pip install PyQt6")
    
    # Fallback to terminal UI
    print("\n" + "="*60)
    print("    SPYDER TRADING SYSTEM - TERMINAL MODE")
    print("="*60)
    print(f"\nStarted: {datetime.now()}")
    print("\nPyQt6 is required for the GUI dashboard.")
    print("Running in terminal mode...")
    print("\nPress Ctrl+C to exit")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
EOF
        python3 /tmp/temp_dashboard.py > "$LOG_DIR/dashboard.log" 2>&1 &
    fi
    
    local gui_pid=$!
    echo $gui_pid > "$PID_DIR/gui.pid"
    
    return 0
}

# ===============================================================================
# MAIN STARTUP SEQUENCE
# ===============================================================================

main() {
    clear
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     SPYDER TRADING DASHBOARD LAUNCHER      ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Step 1: Activate virtual environment
    echo -e "${CYAN}[1/4]${NC} Activating environment..."
    if activate_venv; then
        echo -e "${GREEN}[✓]${NC} Virtual environment activated"
    else
        echo -e "${RED}[✗]${NC} Failed to activate virtual environment"
        exit 1
    fi
    
    # Step 2: Check IB Gateway
    echo -e "${CYAN}[2/4]${NC} Checking IB Gateway..."
    if check_ib_gateway; then
        echo -e "${GREEN}[✓]${NC} IB Gateway is running"
    else
        echo -e "${YELLOW}[!]${NC} IB Gateway not detected"
        echo "    Please ensure IB Gateway is running on port 7497"
    fi
    
    # Step 3: Start Trading Engine
    echo -e "${CYAN}[3/4]${NC} Starting Trading Engine..."
    if start_trading_engine; then
        echo -e "${GREEN}[✓]${NC} Trading Engine started"
    else
        echo -e "${YELLOW}[!]${NC} Trading Engine failed to start"
        echo "    Check logs: $LOG_DIR/engine.log"
    fi
    
    # Step 4: Launch Dashboard GUI
    echo -e "${CYAN}[4/4]${NC} Launching Dashboard GUI..."
    if launch_dashboard_gui; then
        echo -e "${GREEN}[✓]${NC} Dashboard launched successfully!"
        echo ""
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo -e "${GREEN}    SPYDER DASHBOARD IS RUNNING!${NC}"
        echo -e "${GREEN}════════════════════════════════════════${NC}"
        echo ""
        echo "Dashboard Log: $LOG_DIR/dashboard.log"
        echo "Engine Log: $LOG_DIR/engine.log"
        echo ""
        echo "To stop: Right-click SPY icon → Stop Trading System"
    else
        echo -e "${RED}[✗]${NC} Failed to launch dashboard"
        exit 1
    fi
}

# Run main function
main "$@"
