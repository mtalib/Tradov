#!/bin/bash
# ==============================================================================
# SPYDER LAUNCHER SCRIPT
# Generated on: Fri Aug 22 02:28:42 PM WEST 2025
# ==============================================================================

# Configuration
export SPYDER_HOME="/home/adam/Projects/Spyder"
VENV_PATH="/home/adam/Projects/Spyder/.venv"
LOG_FILE="$SPYDER_HOME/logs/launcher.log"

# Create log directory if needed
mkdir -p "$SPYDER_HOME/logs"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

# Start logging
log_message "========================================="
log_message "Starting Spyder Trading System"
log_message "SPYDER_HOME: $SPYDER_HOME"
log_message "VENV_PATH: $VENV_PATH"

# Change to Spyder directory
cd "$SPYDER_HOME" || {
    log_message "ERROR: Cannot change to Spyder directory"
    exit 1
}

# Activate virtual environment if it exists
if [ -n "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/activate" ]; then
    log_message "Activating virtual environment..."
    source "$VENV_PATH/bin/activate"
else
    log_message "WARNING: No virtual environment, using system Python"
fi

# Check if IB Gateway is running (optional)
if pgrep -x "java" > /dev/null && pgrep -f "ibgateway" > /dev/null; then
    log_message "IB Gateway is running"
else
    log_message "WARNING: IB Gateway may not be running"
    echo "IB Gateway doesn't appear to be running."
    echo "Would you like to continue anyway? (y/n)"
    read -p "> " continue_anyway
    if [ "$continue_anyway" != "y" ]; then
        exit 0
    fi
fi

# Launch Spyder based on available method
log_message "Launching Spyder..."

# Method 1: Try the main Python script
if [ -f "$SPYDER_HOME/SpyderA_Core/SpyderA01_Main.py" ]; then
    log_message "Starting via SpyderA01_Main.py..."
    python "$SPYDER_HOME/SpyderA_Core/SpyderA01_Main.py" --gui 2>&1 | tee -a "$LOG_FILE"
    
# Method 2: Try the Q-Script
elif [ -f "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh" ]; then
    log_message "Starting via SpyderQ10_StartAll.sh..."
    bash "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh" 2>&1 | tee -a "$LOG_FILE"
    
# Method 3: Try the launcher Python script
elif [ -f "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ14_MainLauncher.py" ]; then
    log_message "Starting via SpyderQ14_MainLauncher.py..."
    python "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ14_MainLauncher.py" --gui 2>&1 | tee -a "$LOG_FILE"
    
else
    log_message "ERROR: No suitable startup method found!"
    echo "ERROR: Could not find a way to start Spyder"
    echo "Please check your installation"
    exit 1
fi

log_message "Spyder launcher finished"
