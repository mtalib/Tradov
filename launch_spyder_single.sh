#!/bin/bash
# Single Instance Launcher - Prevents multiple Spyder instances

LOCKFILE="/tmp/spyder_launcher.lock"
LOGFILE="/tmp/spyder_launcher_debug.log"

# Log the launch attempt
echo "=== LAUNCHER CALLED: $(date) ===" >> "$LOGFILE"
echo "Running processes:" >> "$LOGFILE"
pgrep -fa "python.*SpyderA01_Main.py" >> "$LOGFILE" 2>&1

# Check if already running
if pgrep -f "python.*SpyderA01_Main.py" > /dev/null; then
    # Already running - just focus the window if possible
    echo "Already running - attempting to focus window" >> "$LOGFILE"
    wmctrl -a "SPYDER" 2>/dev/null || notify-send "Spyder" "Already running"
    exit 0
fi

echo "No existing process - starting new instance" >> "$LOGFILE"

# Show immediate visual feedback
notify-send "Spyder Trading" "Starting dashboard..." -t 2000 -u low &

# Create lock file
touch "$LOCKFILE"

# Clean up on exit
trap "rm -f $LOCKFILE" EXIT

# Launch Spyder - use absolute path to avoid activation overhead
cd /home/adam/Projects/Spyder
echo "Executing: .venv/bin/python SpyderA_Core/SpyderA01_Main.py" >> "$LOGFILE"

# Use absolute Python path to skip activation
exec /home/adam/Projects/Spyder/.venv/bin/python SpyderA_Core/SpyderA01_Main.py
