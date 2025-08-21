#!/bin/bash
# Spyder Dashboard Launcher for Ubuntu Wayland

# Set Wayland environment variables
export XDG_SESSION_TYPE=wayland
export QT_QPA_PLATFORM=wayland
export GDK_BACKEND=wayland

# For Qt applications on Wayland
export QT_WAYLAND_DECORATION=adwaita

# Remove X11 display issues
unset DISPLAY

# Navigate to project directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo "✅ Virtual environment activated (Wayland mode)"
fi

# Set Python path
export PYTHONPATH="$PWD:$PYTHONPATH"

# Disable PyAutoGUI fail-safe for Wayland (this causes the X11 error)
export PYAUTOGUI_DISABLE_FAIL_SAFE=1

echo "🚀 Starting Spyder Enhanced Dashboard (Wayland mode)..."
echo "🖥️ Session Type: $XDG_SESSION_TYPE"
echo "🎨 QT Platform: $QT_QPA_PLATFORM"

# Launch with error handling
python3 SpyderR_Runtime/SpyderR05_LiveDashboard.py "$@"

exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo "❌ Dashboard failed to start (exit code: $exit_code)"
    if [ -t 1 ]; then
        echo "Press Enter to close..."
        read
    fi
fi

exit $exit_code
