#!/usr/bin/env python3
"""
SPYDER Trading System - Dashboard Launcher
Entry point for launching the Spyder trading dashboard
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and launch the production dashboard
from Spyder.SpyderQ_Scripts.launch_dashboard_production import main

if __name__ == "__main__":
    main()
