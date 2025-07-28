#!/bin/bash
# ==============================================================================
# SPYDER TRADING SYSTEM LAUNCHER
# ==============================================================================
# This script launches the Spyder automated trading system with the GUI dashboard

# Configuration
SPYDER_HOME="/home/adam/Projects/Spyder"
PYTHON_VENV="$SPYDER_HOME/venv"              # Virtual environment path
LOG_DIR="$SPYDER_HOME/logs"
PID_FILE="$SPYDER_HOME/.spyder.pid"

# ==============================================================================
# FUNCTIONS
# ==============================================================================

# Check if Spyder is already running
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            if command -v zenity &> /dev/null; then
                zenity --info --text="Spyder is already running (PID: $PID)" 2>/dev/null
            else
                echo "Spyder is already running (PID: $PID)"
            fi
            exit 1
        else
            # Remove stale PID file
            rm -f "$PID_FILE"
        fi
    fi
}

# Create required directories
setup_directories() {
    mkdir -p "$LOG_DIR"
    mkdir -p "$SPYDER_HOME/data"
    mkdir -p "$SPYDER_HOME/reports"
    mkdir -p "$SPYDER_HOME/backups"
    mkdir -p "$SPYDER_HOME/config"
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

# Change to Spyder directory
cd "$SPYDER_HOME" || exit 1

# Check if already running
check_running

# Setup directories
setup_directories

# Activate virtual environment if it exists
# Activate virtual environment
if [ -d "$SPYDER_HOME/.venv" ]; then
    echo "Activating .venv environment..."
    source "$SPYDER_HOME/.venv/bin/activate"
elif [ -d "$PYTHON_VENV" ]; then
    echo "Activating Python virtual environment..."
    source "$PYTHON_VENV/bin/activate"
else
    echo "WARNING: No virtual environment found!"
    echo "PyQt6 may not be available in system Python"
fi

# Verify we're using the right Python
echo "Using Python: $(which python3)"
# Default to paper mode - IB Gateway check will happen when user clicks START
DEFAULT_MODE="paper"

# Parse command line arguments or use defaults
MODE="--mode $DEFAULT_MODE"
DASHBOARD="--dashboard"
DEBUG=""
CONFIG="--config $SPYDER_HOME/config"

# Log startup
LOG_FILE="$LOG_DIR/spyder_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOG_DIR"  # Ensure log directory exists

{
    echo "==============================================="
    echo "SPYDER TRADING SYSTEM"
    echo "==============================================="
    echo "Time: $(date)"
    echo "Mode: $DEFAULT_MODE"
    echo "PID: $$"
    echo "Python: $(which python3)"
    echo "Working Directory: $SPYDER_HOME"
    echo "==============================================="
} | tee "$LOG_FILE"

# Save PID
echo $$ > "$PID_FILE"

# Launch Spyder with GUI
echo "Launching Spyder Trading Dashboard..." | tee -a "$LOG_FILE"

# Run the dashboard directly, suppressing import warnings
export PYTHONWARNINGS="ignore::UserWarning"

# Launch the dashboard module directly
python3 -m SpyderG_GUI.SpyderG05_TradingDashboard 2>&1 | \
    grep -v "SpyderG_GUI.*not available" | \
    grep -v "✅ SpyderG_GUI: 0 modules loaded" | \
    tee -a "$LOG_FILE"

# Cleanup
rm -f "$PID_FILE"
echo "Spyder Trading System stopped." | tee -a "$LOG_FILE"
