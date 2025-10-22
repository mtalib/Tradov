#!/usr/bin/env python3
"""
Test script for the SPYDER Authentication Launcher
"""

import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_launcher():
    """Test the authentication launcher"""
    print("Testing SPYDER Authentication Launcher...")

    try:
        # Import the launcher
        from SpyderG_GUI.SpyderG08_UserAuthenticationLauncher import main

        # Run the launcher
        print("Starting launcher...")
        main()

    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure all dependencies are installed")
        return False
    except Exception as e:
        print(f"Error running launcher: {e}")
        return False

    return True

if __name__ == "__main__":
    success = test_launcher()
    if success:
        print("Test completed successfully")
    else:
        print("Test failed")
        sys.exit(1)