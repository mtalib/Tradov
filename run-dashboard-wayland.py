#!/usr/bin/env python3
"""
Wayland-compatible Spyder Dashboard Launcher
"""
import os
import sys

# Set Wayland environment
os.environ['XDG_SESSION_TYPE'] = 'wayland'
os.environ['QT_QPA_PLATFORM'] = 'wayland'
os.environ['GDK_BACKEND'] = 'wayland'
os.environ['QT_WAYLAND_DECORATION'] = 'adwaita'

# Remove X11 display
if 'DISPLAY' in os.environ:
    del os.environ['DISPLAY']

# Disable PyAutoGUI fail-safe
os.environ['PYAUTOGUI_DISABLE_FAIL_SAFE'] = '1'

print("🚀 Starting Spyder Dashboard (Wayland Mode)")
print(f"🖥️ Session Type: {os.environ.get('XDG_SESSION_TYPE', 'unknown')}")
print(f"🎨 QT Platform: {os.environ.get('QT_QPA_PLATFORM', 'unknown')}")

# Add project to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    # Import and run the launcher
    from SpyderR_Runtime.SpyderR05_LiveDashboard import main
    sys.exit(main())
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Trying direct execution...")
    
    # Fallback: execute the file directly
    dashboard_path = os.path.join(project_root, 'SpyderR_Runtime', 'SpyderR05_LiveDashboard.py')
    exec(open(dashboard_path).read())
