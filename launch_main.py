#!/usr/bin/env python3
"""
SPYDER Trading System - Main Launcher
Entry point for launching the main Spyder application with connection selector
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and launch the main application
from Spyder.SpyderA_Core.SpyderA01_Main import main

if __name__ == "__main__":
    main()
