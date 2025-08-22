#!/bin/bash
# ==============================================================================
# SPYDER LAUNCHER - WAYLAND COMPATIBLE (FIXED)
# Corrected version that uses proper arguments
# ==============================================================================

SPYDER_HOME="/home/adam/Projects/Spyder"
VENV_PATH="$SPYDER_HOME/.venv"
LOG_FILE="$SPYDER_HOME/logs/launcher.log"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Create log directory
mkdir -p "$SPYDER_HOME/logs"

# Log function
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo -e "$1"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  SPYDER TRADING SYSTEM${NC}"
echo -e "${BLUE}  Wayland Compatible Launcher${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Change to Spyder directory
cd "$SPYDER_HOME" || {
    log_message "${RED}✗ Cannot change to Spyder directory${NC}"
    exit 1
}

# Activate virtual environment
if [ -f "$VENV_PATH/bin/activate" ]; then
    log_message "${GREEN}✓ Activating virtual environment${NC}"
    source "$VENV_PATH/bin/activate"
else
    log_message "${YELLOW}⚠ No virtual environment found${NC}"
fi

# Set display variables for Wayland/XWayland compatibility
export GDK_BACKEND=wayland,x11
export QT_QPA_PLATFORM=wayland
export DISPLAY=:0
export WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-wayland-0}

# Allow local X connections (for XWayland)
xhost +local: 2>/dev/null || true

# Disable pyautogui automation on Wayland
export SPYDER_NO_AUTOMATION=1

# Check if IB Gateway is running
log_message "${YELLOW}Checking IB Gateway...${NC}"
if pgrep -f "ibgateway" > /dev/null 2>&1; then
    log_message "${GREEN}✓ IB Gateway is running${NC}"
else
    log_message "${YELLOW}⚠ IB Gateway not detected${NC}"
    echo -e "${YELLOW}IB Gateway doesn't appear to be running.${NC}"
    echo -n "Continue anyway? (y/n): "
    read -r response
    if [ "$response" != "y" ]; then
        exit 0
    fi
fi

# Launch Spyder (WITHOUT --gui flag since it's not recognized)
log_message "${GREEN}Launching Spyder Trading System...${NC}"
echo ""

# Try different launch methods
# Method 1: Direct Python launch (no arguments = GUI mode by default)
if [ -f "$SPYDER_HOME/SpyderA_Core/SpyderA01_Main.py" ]; then
    log_message "Starting via SpyderA01_Main.py (GUI mode)..."
    python "$SPYDER_HOME/SpyderA_Core/SpyderA01_Main.py" 2>&1 | tee -a "$LOG_FILE"
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        log_message "${GREEN}✓ Spyder exited normally${NC}"
    else
        log_message "${RED}✗ Spyder exited with code $exit_code${NC}"
        
        # Try alternative launch
        log_message "${YELLOW}Trying alternative launch method...${NC}"
        python -c "
import sys
import os
sys.path.insert(0, '$SPYDER_HOME')
os.environ['SPYDER_NO_AUTOMATION'] = '1'

try:
    # Import the GUI components
    from PyQt6.QtWidgets import QApplication
    from SpyderG_GUI.SpyderG01_MainWindow import MainWindow
    
    # Create the application
    app = QApplication(sys.argv)
    app.setApplicationName('Spyder Trading System')
    
    # Create and show the main window
    window = MainWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())
    
except Exception as e:
    print(f'Error launching GUI: {e}')
    print('Trying headless mode...')
    
    # Fallback to headless mode
    from SpyderA_Core import SpyderA01_Main
    import asyncio
    asyncio.run(SpyderA01_Main.main(['--headless']))
"
    fi
else
    log_message "${RED}✗ SpyderA01_Main.py not found${NC}"
    exit 1
fi
