#!/bin/bash
#
# Spyder Trading Dashboard - Production Launcher
# This script properly activates the virtual environment and launches the main application
#

# Navigate to the Spyder directory
cd /home/adam/Projects/Spyder || exit 1

# Activate the virtual environment
source .venv/bin/activate

# Set the display for GUI
export DISPLAY=:0

# Launch the main application
exec python SpyderA_Core/SpyderA01_Main.py
