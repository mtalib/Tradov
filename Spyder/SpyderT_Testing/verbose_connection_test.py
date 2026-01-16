#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: verbose_connection_test.py
Purpose: Minimal IBAPI Connection Test with Detailed Error Reporting

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Minimal IBAPI Connection Test with Detailed Error Reporting

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import time
import threading
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import OrderId, TickerId

class VerboseIBTest(EClient, EWrapper):
    """Minimal test with maximum logging"""

    def __init__(self):
        EClient.__init__(self, self)
        self.connected = False
        self.next_valid_id = None
        self.managed_accounts = None
        self.connection_time = None
        self.all_events = []

    def log_event(self, event_name, details=""):
        """Log all events with timestamps"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        event = f"[{timestamp}] {event_name}: {details}"
        self.all_events.append(event)
        print(f"📝 {event}")

    # Connection Events
    def connectAck(self):
        """Connection acknowledged"""
        self.connected = True
        self.connection_time = time.time()
        self.log_event("connectAck", "Connection acknowledged by IB Gateway")

    def connectionClosed(self):
        """Connection closed"""
        self.log_event("connectionClosed", "Connection closed")

    # Data Events
    def nextValidId(self, orderId: OrderId):
        """Next valid order ID received - indicates full handshake complete"""
        self.next_valid_id = orderId
        self.log_event("nextValidId", f"Order ID: {orderId} - HANDSHAKE COMPLETE!")

    def managedAccounts(self, accountsList: str):
        """Managed accounts received"""
        self.managed_accounts = accountsList
        self.log_event("managedAccounts", f"Accounts: {accountsList}")

    def currentTime(self, time_val):
        """Current server time"""
        self.log_event("currentTime", f"Server time: {time_val}")

    # Error Handling
    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderReject: str = "",
    ):
        """Handle all errors with detailed categorization"""
        error_type = self.categorize_error(errorCode)
        self.log_event("error", f"[{error_type}] Code {errorCode}: {errorString}")

        # Special handling for critical errors
        if errorCode in [502, 503, 504, 1100]:
            self.log_event("CRITICAL", f"Connection-related error: {errorCode}")

    def categorize_error(self, code):
        """Categorize error codes"""
        if code in [2104, 2106, 2158]:
            return "INFO-MarketData"
        elif code in [502, 503, 504]:
            return "ERROR-Connection"
        elif code in [1100, 1101, 1102]:
            return "WARN-ConnStatus"
        elif code < 1000:
            return "ERROR-System"
        elif code < 2000:
            return "WARN-System"
        else:
            return "INFO-General"


def test_connection_with_timeout(timeout_seconds=15):
    """Test connection with detailed timeout handling"""
    print(f"🚀 Starting Verbose IBAPI Connection Test")
    print(f"Target: 127.0.0.1:4002")
    print(f"Timeout: {timeout_seconds} seconds")
    print(f"Time: {datetime.now()}")
    print("=" * 60)

    app = VerboseIBTest()
    success = False

    try:
        # Phase 1: Initiate connection
        print(f"\n🔌 Phase 1: Initiating connection...")
        app.log_event("connect_start", "Calling app.connect()")

        start_time = time.time()
        app.connect("127.0.0.1", 4002, 1)

        connect_call_time = time.time() - start_time
        print(f"   app.connect() returned in {connect_call_time:.3f}s")

        # Phase 2: Start message loop
        print(f"\n🔄 Phase 2: Starting message loop...")

        def run_loop():
            try:
                app.log_event("message_loop_start", "Starting EClient.run()")
                app.run()
                app.log_event("message_loop_end", "EClient.run() ended")
            except Exception as e:
                app.log_event("message_loop_error", f"Exception in run(): {e}")

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

        # Phase 3: Wait for handshake completion
        print(f"\n⏳ Phase 3: Waiting for handshake...")

        loop_start = time.time()
        last_status_time = loop_start

        while time.time() - loop_start < timeout_seconds:
            current_time = time.time()

            # Print status every 2 seconds
            if current_time - last_status_time >= 2:
                elapsed = current_time - loop_start
                print(
                    f"   ⏱️  {elapsed:.1f}s - Connected: {app.connected}, NextValidId: {app.next_valid_id is not None}"
                )
                last_status_time = current_time

            # Check for completion
            if app.next_valid_id is not None:
                elapsed = time.time() - loop_start
                print(f"\n🎉 SUCCESS! Handshake completed in {elapsed:.3f}s")
                print(f"   Next Valid ID: {app.next_valid_id}")
                if app.managed_accounts:
                    print(f"   Managed Accounts: {app.managed_accounts}")
                success = True
                break

            time.sleep(0.1)

        # Timeout handling
        if not success:
            elapsed = time.time() - loop_start
            print(f"\n❌ TIMEOUT after {elapsed:.3f}s")
            print(f"   Connected: {app.connected}")
            print(f"   NextValidId received: {app.next_valid_id is not None}")
            print(f"   ManagedAccounts received: {app.managed_accounts is not None}")

    except Exception as e:
        print(f"\n💥 EXCEPTION during connection: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Cleanup
        try:
            app.disconnect()
            app.log_event("disconnect", "Called app.disconnect()")
        except:
            pass

    # Final Summary
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS:")
    print(f"   Success: {success}")
    print(f"   Total Events: {len(app.all_events)}")

    if app.all_events:
        print(f"\n📝 All Events ({len(app.all_events)}):")
        for event in app.all_events:
            print(f"     {event}")

    if not success:
        print(f"\n🔍 TROUBLESHOOTING ANALYSIS:")

        if not app.all_events:
            print("   ❌ No events received - connection likely blocked at TCP level")
        elif app.connected:
            print("   ✅ Connection acknowledged but handshake incomplete")
            print(
                "   💡 This suggests IB Gateway is responding but API may be restricted"
            )
        else:
            print("   ❌ No connection acknowledgment received")
            print("   💡 This suggests API protocol mismatch or restriction")

        print(f"\n🛠️  NEXT STEPS:")
        print("   1. Check IB Gateway connection status indicator")
        print("   2. Verify no other applications are using API connections")
        print("   3. Try restarting IB Gateway")
        print("   4. Check for any IB Gateway software updates")

    return success


if __name__ == "__main__":
    test_connection_with_timeout(15)
