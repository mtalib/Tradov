#!/bin/bash
# SPYDER Launcher Wrapper - Ensures proper startup

# Set environment
export SPYDER_HOME="/home/adam/Projects/Spyder"
export PATH="$SPYDER_HOME/SpyderQ_Scripts:$PATH"

# Log startup attempt
echo "[$(date)] Spyder launch attempted" >> "$SPYDER_HOME/logs/launcher.log"

# Change to Spyder directory
cd "$SPYDER_HOME" || exit 1

# Check if we have a terminal
if [ -t 0 ]; then
    # Running in terminal
    echo "Starting Spyder Trading System..."
    exec "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
else
    # Running from GUI (dock icon)
    # Open in a new terminal
    if command -v gnome-terminal &> /dev/null; then
        gnome-terminal --working-directory="$SPYDER_HOME" \
            --title="Spyder Trading System" \
            -- bash -c "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh; echo 'Press Enter to close...'; read"
    elif command -v xterm &> /dev/null; then
        xterm -T "Spyder Trading System" -e "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh"
    else
        # Fallback - try to run directly
        "$SPYDER_HOME/SpyderQ_Scripts/SpyderQ10_StartAll.sh" &
    fi
fi
