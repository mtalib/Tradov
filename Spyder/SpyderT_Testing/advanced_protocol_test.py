#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: advanced_protocol_test.py
Purpose: Advanced IBAPI Connection Test

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    Advanced IBAPI Connection Test

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
from datetime import datetime

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import socket
import struct

class IBAPIProtocolTest:
    """Test IBAPI connection using exact protocol"""

    def __init__(self, host="127.0.0.1", port=4002):
        self.host = host
        self.port = port
        self.sock = None

    def connect_and_test(self):
        """Perform exact IBAPI handshake"""
        print(f"🔍 Advanced IBAPI Protocol Test")
        print(f"Target: {self.host}:{self.port}")
        print(f"Time: {datetime.now()}")
        print("=" * 50)

        try:
            # Step 1: Create socket
            print("1️⃣ Creating socket...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)

            # Step 2: Connect
            print("2️⃣ Connecting to IB Gateway...")
            start_time = time.time()
            self.sock.connect((self.host, self.port))
            connect_time = time.time() - start_time
            print(f"   ✅ TCP connection successful in {connect_time:.3f}s")

            # Step 3: Send API version handshake
            print("3️⃣ Sending API version handshake...")

            # IBAPI sends client version first
            # This is the exact protocol from ibapi/client.py
            msg = "API\0"  # Null-terminated API string
            version_msg = msg.encode("utf-8")

            print(f"   Sending: {repr(version_msg)}")
            self.sock.send(version_msg)

            # Step 4: Try to receive server version
            print("4️⃣ Waiting for server version response...")

            # Set a shorter timeout for this specific receive
            self.sock.settimeout(5)

            try:
                # Try to receive the first few bytes
                response = self.sock.recv(1024)

                if response:
                    print(f"   ✅ Received response: {len(response)} bytes")
                    print(f"   Raw data: {repr(response[:50])}")  # First 50 bytes

                    # Try to decode as IBAPI typically does
                    try:
                        decoded = response.decode("utf-8", errors="ignore")
                        print(f"   Decoded: {repr(decoded[:100])}")
                    except:
                        print("   Could not decode as UTF-8")

                    return True
                else:
                    print("   ❌ No response received")
                    return False

            except socket.timeout:
                print("   ❌ Timeout waiting for server response")
                print(
                    "   This suggests IB Gateway received our message but isn't responding"
                )
                return False

        except socket.timeout:
            print("❌ Connection timeout")
            return False
        except ConnectionRefused:
            print("❌ Connection refused - IB Gateway may not be running")
            return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
        finally:
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass

    def test_simple_socket(self):
        """Test basic socket connection without protocol"""
        print(f"\n🔌 Basic Socket Test")

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)

            result = sock.connect_ex((self.host, self.port))
            if result == 0:
                print("✅ Basic socket connection works")

                # Try to send some data and see what happens
                sock.send(b"TEST\n")
                sock.settimeout(2)

                try:
                    response = sock.recv(100)
                    print(f"✅ Received response to test data: {repr(response)}")
                except socket.timeout:
                    print("⚠️  No response to test data (expected)")

                sock.close()
                return True
            else:
                print(f"❌ Socket connection failed: {result}")
                return False

        except Exception as e:
            print(f"❌ Socket test failed: {e}")
            return False


def main():
    """Run comprehensive IBAPI protocol test"""
    tester = IBAPIProtocolTest()

    # Test 1: Basic socket connectivity
    socket_works = tester.test_simple_socket()

    # Test 2: IBAPI protocol handshake
    if socket_works:
        api_works = tester.connect_and_test()

        print(f"\n{'='*50}")
        print("📋 TEST RESULTS:")
        print(f"   Socket Connection: {'✅ Working' if socket_works else '❌ Failed'}")
        print(f"   IBAPI Protocol: {'✅ Working' if api_works else '❌ Failed'}")

        if socket_works and not api_works:
            print(f"\n🔍 ANALYSIS:")
            print("   • Port 4002 is open and accepting connections")
            print("   • IB Gateway is running and listening")
            print("   • BUT: IB Gateway is not responding to API protocol messages")
            print("   • This suggests API functionality is disabled or restricted")

            print(f"\n💡 POSSIBLE SOLUTIONS:")
            print("1. Check if you're fully logged into IB Gateway (not just launched)")
            print("2. Verify paper trading mode is active")
            print("3. Look for any popup dialogs or notifications in IB Gateway")
            print("4. Check IB Gateway logs for error messages")
            print("5. Try logging out and back into IB Gateway")
    else:
        print(f"\n❌ Basic connectivity failed - check if IB Gateway is running")


if __name__ == "__main__":
    main()
