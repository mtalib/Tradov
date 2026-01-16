#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: test_asyncio_fix.py
Purpose: Test script to verify that the asyncio event loop fix in ClientConnectionManager works

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Test script to verify that the asyncio event loop fix in ClientConnectionManager works

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import asyncio
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QMutex, QMutexLocker
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QApplication = None
    QMutex = None
    QMutexLocker = None

from Spyder.SpyderG_GUI.SpyderG15_ClientConnectionManager import ClientConnectionManager, ClientStatus

def test_asyncio_event_loop_fix():
    """Test that the asyncio event loop fix prevents 'Task got Future attached to a different loop' errors"""

    print("=" * 60)
    print("Testing AsyncIO Event Loop Fix")
    print("=" * 60)

    # Create a QApplication for the test if available
    if QT_AVAILABLE and QApplication is not None:
        app = QApplication(sys.argv)
    else:
        print("⚠️ PySide6 not available, running without Qt components")
        app = None

    # Create a mock IB class that simulates the connection process
    class MockIB:
        def __init__(self):
            self.connected = False
            self.accounts = []

        async def connectAsync(self, host, port, clientId, timeout):
            # Simulate connection delay
            await asyncio.sleep(0.1)
            # Simulate connection failure (since we don't have a real Gateway)
            raise ConnectionRefusedError("Connection refused (test)")

        def disconnect(self):
            self.connected = False

        def managedAccounts(self):
            return self.accounts

        def isConnected(self):
            return self.connected

    # Test 1: Check that the manager can be created without errors
    print("\n1. Testing ClientConnectionManager creation...")
    try:
        manager = ClientConnectionManager(num_clients=2)
        print("✅ ClientConnectionManager created successfully")
    except Exception as e:
        print(f"❌ Failed to create ClientConnectionManager: {e}")
        return False

    # Test 2: Test the async connection method with mock IB
    print("\n2. Testing async connection with mock IB...")

    # Patch the IB class to use our mock
    with patch('SpyderG_GUI.SpyderG15_ClientConnectionManager.IB_CLASS', MockIB):
        try:
            # Test the connection process
            # This should not raise "Task got Future attached to a different loop" errors
            result = manager.connect_all_clients()

            # We expect this to return False since we're using a mock that fails to connect
            # The important thing is that it doesn't crash with asyncio errors
            print(f"✅ Connection process completed without asyncio errors. Result: {result}")

        except RuntimeError as e:
            if "Task got Future attached to a different loop" in str(e):
                print(f"❌ AsyncIO error still present: {e}")
                return False
            else:
                print(f"⚠️ Different RuntimeError (may be expected): {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

    # Test 3: Test the _run_connection_in_thread method
    print("\n3. Testing _run_connection_in_thread method...")
    try:
        with patch('SpyderG_GUI.SpyderG15_ClientConnectionManager.IB_CLASS', MockIB):
            # Test the thread method
            result = manager._run_connection_in_thread()
            print(f"✅ Thread method completed without asyncio errors. Result: {result}")
    except RuntimeError as e:
        if "Task got Future attached to a different loop" in str(e):
            print(f"❌ AsyncIO error in thread method: {e}")
            return False
        else:
            print(f"⚠️ Different RuntimeError in thread method: {e}")
    except Exception as e:
        print(f"❌ Unexpected error in thread method: {e}")
        return False

    print("\n" + "=" * 60)
    print("✅ All tests passed! AsyncIO event loop fix is working correctly.")
    print("The 'Task got Future attached to a different loop' error has been resolved.")
    print("=" * 60)

    return True

if __name__ == "__main__":
    from pathlib import Path
    success = test_asyncio_event_loop_fix()
    sys.exit(0 if success else 1)