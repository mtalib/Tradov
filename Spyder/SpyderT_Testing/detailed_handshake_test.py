#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: detailed_handshake_test.py
Purpose: SPYDER - IB Gateway Handshake Diagnostic Test

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - IB Gateway Handshake Diagnostic Test

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import threading
import sys
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import socket
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import OrderId, TickerId

class DetailedHandshakeTest(EClient, EWrapper):
    """Comprehensive IB Gateway handshake diagnostic test"""

    def __init__(self, host: str = "127.0.0.1", port: int = 4002, client_id: int = 1):
        EClient.__init__(self, self)
        self.host = host
        self.port = port
        self.client_id = client_id

        # Connection state tracking
        self.tcp_connected = False
        self.api_connected = False
        self.handshake_complete = False
        self.managed_accounts_received = False
        self.next_valid_id_received = False

        # Timing tracking
        self.tcp_connect_time = None
        self.api_connect_time = None
        self.handshake_complete_time = None

        # Error tracking
        self.errors = []
        self.messages = []

        print(f"🔍 Starting detailed handshake test...")
        print(f"📍 Target: {host}:{port} with client ID {client_id}")
        print(f"⏰ Test started at: {datetime.now()}")
        print("=" * 60)

    # ============================
    # CONNECTION CALLBACKS
    # ============================

    def connectAck(self):
        """Called when API connection is acknowledged"""
        self.api_connected = True
        self.api_connect_time = time.time()
        print(f"✅ API CONNECTION ACK received at {datetime.now()}")
        print(f"   Client ID: {self.client_id}")

    def connectionClosed(self):
        """Called when connection is closed"""
        print(f"❌ CONNECTION CLOSED at {datetime.now()}")

    def managedAccounts(self, accountsList: str):
        """Called when managed accounts are received"""
        self.managed_accounts_received = True
        print(f"📊 MANAGED ACCOUNTS received: {accountsList}")
        print(f"   Time: {datetime.now()}")

    def nextValidId(self, orderId: OrderId):
        """Called when next valid order ID is received"""
        self.next_valid_id_received = True
        print(f"🆔 NEXT VALID ID received: {orderId}")
        print(f"   Time: {datetime.now()}")

        # Mark handshake as complete when we get next valid ID
        if not self.handshake_complete:
            self.handshake_complete = True
            self.handshake_complete_time = time.time()
            print(f"🎉 HANDSHAKE COMPLETE at {datetime.now()}")

    def error(
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderReject: str = "",
    ):
        """Handle errors"""
        error_msg = f"Error {errorCode}: {errorString}"
        if reqId != -1:
            error_msg = f"[Req {reqId}] {error_msg}"

        self.errors.append((errorCode, errorString, datetime.now()))

        # Categorize errors
        if errorCode in [2104, 2106, 2158]:  # Market data farm connections
            print(f"ℹ️  {error_msg} (Market data info)")
        elif errorCode in [502, 503, 504]:  # Connection errors
            print(f"❌ {error_msg} (Connection error)")
        elif errorCode in [1100, 1101, 1102]:  # Connection lost/restored
            print(f"⚠️  {error_msg} (Connection status)")
        else:
            print(f"⚠️  {error_msg}")

    # ============================
    # TEST METHODS
    # ============================

    def test_tcp_connection(self) -> bool:
        """Test basic TCP connection to the port"""
        print(f"\n🔌 Testing TCP connection to {self.host}:{self.port}")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 second timeout

            start_time = time.time()
            result = sock.connect_ex((self.host, self.port))
            connect_time = time.time() - start_time

            if result == 0:
                self.tcp_connected = True
                self.tcp_connect_time = connect_time
                print(f"✅ TCP connection successful in {connect_time:.3f}s")
                sock.close()
                return True
            else:
                print(f"❌ TCP connection failed with error code: {result}")
                return False

        except socket.timeout:
            print(f"❌ TCP connection timed out after 5 seconds")
            return False
        except Exception as e:
            print(f"❌ TCP connection error: {e}")
            return False
        finally:
            try:
                sock.close()
            except:
                pass

    def test_api_handshake(self, timeout: int = 10) -> bool:
        """Test API handshake with timeout"""
        print(f"\n🤝 Testing API handshake (timeout: {timeout}s)")

        # Start the connection
        try:
            self.connect(self.host, self.port, self.client_id)
        except Exception as e:
            print(f"❌ Connection initiation failed: {e}")
            return False

        # Start the message loop in a separate thread
        def run_loop():
            try:
                self.run()
            except Exception as e:
                print(f"❌ Message loop error: {e}")

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

        # Wait for handshake completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.handshake_complete:
                elapsed = time.time() - start_time
                print(f"✅ API handshake completed in {elapsed:.3f}s")
                return True
            time.sleep(0.1)

        # Timeout occurred
        elapsed = time.time() - start_time
        print(f"❌ API handshake timed out after {elapsed:.3f}s")
        self._print_connection_status()
        return False

    def _print_connection_status(self):
        """Print detailed connection status"""
        print(f"\n📊 Connection Status Summary:")
        print(f"   TCP Connected: {self.tcp_connected}")
        print(f"   API Connected: {self.api_connected}")
        print(f"   Handshake Complete: {self.handshake_complete}")
        print(f"   Managed Accounts: {self.managed_accounts_received}")
        print(f"   Next Valid ID: {self.next_valid_id_received}")

        if self.tcp_connect_time:
            print(f"   TCP Connect Time: {self.tcp_connect_time:.3f}s")
        if self.api_connect_time:
            print(f"   API Connect Time: {self.api_connect_time:.3f}s")
        if self.handshake_complete_time:
            print(f"   Handshake Time: {self.handshake_complete_time:.3f}s")

    def test_multiple_client_ids(self, client_ids: list = [1, 2, 3, 999]) -> bool:
        """Test with multiple client IDs to find one that works"""
        print(f"\n🆔 Testing multiple client IDs: {client_ids}")

        for client_id in client_ids:
            print(f"\n--- Testing Client ID: {client_id} ---")

            # Reset state
            self.api_connected = False
            self.handshake_complete = False
            self.managed_accounts_received = False
            self.next_valid_id_received = False

            # Try this client ID
            test_client = DetailedHandshakeTest(self.host, self.port, client_id)
            success = test_client.test_api_handshake(timeout=8)

            if success:
                print(f"✅ SUCCESS with Client ID {client_id}!")
                test_client.disconnect()
                return True
            else:
                print(f"❌ Failed with Client ID {client_id}")
                test_client.disconnect()
                time.sleep(1)  # Brief pause between attempts

        return False

    def run_comprehensive_test(self):
        """Run all diagnostic tests"""
        print(f"🚀 Starting Comprehensive IB Gateway Diagnostic Test")
        print(f"{'='*60}")

        # Step 1: TCP Connection
        tcp_success = self.test_tcp_connection()
        if not tcp_success:
            print(f"\n❌ FAILED: Cannot establish TCP connection")
            print(f"   Check if IB Gateway is running on port {self.port}")
            return False

        # Step 2: API Handshake
        handshake_success = self.test_api_handshake()
        if not handshake_success:
            print(f"\n⚠️  Primary handshake failed, trying alternative client IDs...")
            alt_success = self.test_multiple_client_ids()
            if not alt_success:
                print(f"\n❌ FAILED: All handshake attempts failed")
                self._print_troubleshooting_tips()
                return False

        # Success!
        print(f"\n🎉 SUCCESS: All tests passed!")
        self.disconnect()
        return True

    def _print_troubleshooting_tips(self):
        """Print troubleshooting suggestions"""
        print(f"\n🔧 TROUBLESHOOTING SUGGESTIONS:")
        print(f"1. Check IB Gateway Configuration:")
        print(f"   - Enable API connections")
        print(f"   - Check port {self.port} is configured")
        print(f"   - Verify 'Read-Only API' is disabled if needed")
        print(f"2. Check Authentication:")
        print(f"   - Ensure you're logged into IB Gateway")
        print(f"   - Verify paper trading mode is active")
        print(f"3. Check Firewall:")
        print(f"   - Ensure port {self.port} is not blocked")
        print(f"4. Check Client ID conflicts:")
        print(f"   - Other applications may be using client IDs")

        if self.errors:
            print(f"\n📝 Error Summary ({len(self.errors)} errors):")
            for code, message, timestamp in self.errors[-5:]:  # Last 5 errors
                print(f"   {timestamp.strftime('%H:%M:%S')} - {code}: {message}")


def main():
    """Main test function"""
    # Test configuration
    HOST = "127.0.0.1"
    PORTS_TO_TEST = [4002, 4001, 7496, 7497]  # Common IB ports

    print(f"🔍 IB Gateway Handshake Diagnostic Tool")
    print(f"Time: {datetime.now()}")
    print(f"=" * 60)

    success = False
    for port in PORTS_TO_TEST:
        print(f"\n🔍 Testing port {port}...")

        tester = DetailedHandshakeTest(HOST, port, 1)
        if tester.test_tcp_connection():
            print(f"✅ Port {port} is open, testing API handshake...")
            if tester.run_comprehensive_test():
                success = True
                print(f"🎉 SUCCESS: Port {port} is working correctly!")
                break
        else:
            print(f"❌ Port {port} is not accessible")

    if not success:
        print(f"\n❌ FINAL RESULT: No working IB Gateway connection found")
        print(f"   Please check IB Gateway configuration and try again")
        return 1
    else:
        print(f"\n✅ FINAL RESULT: IB Gateway connection working!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
