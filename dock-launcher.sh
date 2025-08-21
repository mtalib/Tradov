#!/bin/bash
# Spyder Dashboard Dock Launcher
# Handles all environment setup for desktop launcher

# Set working directory
cd "$(dirname "$0")"

# Debug logging (optional - remove after testing)
echo "$(date): Dock launcher started" >> /tmp/spyder-dock.log
echo "Working dir: $(pwd)" >> /tmp/spyder-dock.log
echo "User: $USER" >> /tmp/spyder-dock.log
echo "Home: $HOME" >> /tmp/spyder-dock.log

# Set up environment variables
export HOME="/home/adam"
export USER="adam"
export XDG_SESSION_TYPE=wayland
export QT_QPA_PLATFORM=wayland
export GDK_BACKEND=wayland
export QT_WAYLAND_DECORATION=adwaita

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "$(date): Virtual env activated" >> /tmp/spyder-dock.log
else
    echo "$(date): Virtual env not found!" >> /tmp/spyder-dock.log
fi

# Set Python path
export PYTHONPATH="$PWD:$PYTHONPATH"

# Launch the advanced launcher
echo "$(date): Launching advanced launcher" >> /tmp/spyder-dock.log
python3 advanced-wayland-launcher.py

# Log exit status
echo "$(date): Exit code: $?" >> /tmp/spyder-dock.log
