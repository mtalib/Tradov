#!/bin/bash
export SPYDER_HOME="/home/adam/Projects/Spyder"
cd "$SPYDER_HOME"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Set display variables
export GDK_BACKEND=wayland,x11
export QT_QPA_PLATFORM=wayland
export SPYDER_NO_AUTOMATION=1

# Launch Spyder
python SpyderA_Core/SpyderA01_Main.py
