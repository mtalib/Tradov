#!/usr/bin/env python3
"""
Spyder Startup Wrapper - Handles display issues
"""
import os
import sys
import subprocess

# Set environment for Wayland compatibility
os.environ['GDK_BACKEND'] = 'wayland,x11'
os.environ['QT_QPA_PLATFORM'] = 'wayland'
os.environ['SPYDER_NO_AUTOMATION'] = '1'  # Disable pyautogui

# Add Spyder to path
sys.path.insert(0, os.path.dirname(__file__))

# Import and run Spyder
try:
    from SpyderA_Core import SpyderA01_Main
    SpyderA01_Main.main()
except ImportError as e:
    print(f"Error importing Spyder: {e}")
    # Try alternative launch
    subprocess.run([sys.executable, "SpyderA_Core/SpyderA01_Main.py", "--gui"])
