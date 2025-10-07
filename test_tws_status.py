#!/usr/bin/env python3
"""
SPYDER - Simple TWS Status Test
===============================

Simple script to test TWS connection status and check what's happening
on the TWS side when we attempt to connect.

This script makes minimal connection attempts and provides clear
feedback about what TWS is doing.
"""

import socket
import time
import sys
from datetime import datetime


def print_header():
    """Print test header"""
    print("🕷️ SPYDER - TWS Status Test")
    print("=" * 35)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🎯 TWS: 192.168.1.4:7497")
    print()


def test_basic_connectivity():
    """Test basic TCP connectivity"""
    print("🔌 Basic Connectivity Test")
    print("-" * 25)

    host = "192.168.1.4"
    port = 7497

    try:
        # Test socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        start_time = time.time()
        result = sock.connect_ex((host, port))
        connection_time = time.time() - start_time

        if result == 0:
            print(f"✅ TCP connection: SUCCESS ({connection_time:.3f}s)")

            # Try to detect if TWS is responsive
            print("🔍 Testing TWS responsiveness...")

            # Send a simple probe message
            try:
                sock.send(b"TEST\x00")
                sock.settimeout(2)

                # Try to receive any response
                try:
                    response = sock.recv(100)
                    if response:
                        print(f"✅ TWS responded: {len(response)} bytes")
                        print(f"   Response: {response.hex()}")
                    else:
                        print("❌ TWS did not respond")
                except socket.timeout:
                    print("⏰ TWS response timeout (2s)")
                except Exception as e:
                    print(f"❌ Response error: {e}")

            except Exception as e:
                print(f"❌ Send error: {e}")

            sock.close()
            print("🔌 Connection closed")

        else:
            print(f"❌ TCP connection: FAILED (error {result})")

    except Exception as e:
        print(f"❌ Connection test failed: {e}")

    print()


def test_tws_api_handshake():
    """Test TWS API handshake"""
    print("🤝 TWS API Handshake Test")
    print("-" * 25)

    host = "192.168.1.4"
    port = 7497

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)

        print(f"🔌 Connecting to {host}:{port}...")
        sock.connect((host, port))
        print("✅ Socket connected")

        # Send API handshake similar to what ib_async sends
        print("📤 Sending API handshake...")

        # Basic API version negotiation message
        # This is similar to what TWS expects
        api_message = b"API\x00\x00\x00\x09\x00\x00\x00\x47"  # API version negotiation
        sock.send(api_message)
        print("✅ Handshake message sent")

        # Wait for TWS response
        print("⏳ Waiting for TWS response (10s timeout)...")
        sock.settimeout(10)

        try:
            response = sock.recv(1024)
            if response:
                print(f"🎉 TWS RESPONDED!")
                print(f"   Response length: {len(response)} bytes")
                print(f"   Response (hex): {response.hex()}")
                print(f"   Response (ascii): {response}")

                # This indicates TWS API is working
                return True
            else:
                print("❌ Empty response from TWS")
                return False

        except socket.timeout:
            print("⏰ TWS handshake timeout - NO RESPONSE")
            print("   This suggests TWS API is not processing requests")
            return False

    except Exception as e:
        print(f"❌ Handshake test failed: {e}")
        return False
    finally:
        try:
            sock.close()
        except:
            pass

    print()


def check_multiple_ports():
    """Check multiple TWS ports"""
    print("🔍 Multi-Port Check")
    print("-" * 18)

    host = "192.168.1.4"
    ports = {
        7497: "Paper Trading",
        7496: "Live Trading",
        4001: "IB Gateway Paper",
        4002: "IB Gateway Live",
    }

    accessible_ports = []

    for port, description in ports.items():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                print(f"✅ Port {port} ({description}): ACCESSIBLE")
                accessible_ports.append((port, description))
            else:
                print(f"❌ Port {port} ({description}): BLOCKED")

        except Exception as e:
            print(f"❌ Port {port} ({description}): ERROR - {e}")

    print()
    if accessible_ports:
        print(f"📊 Found {len(accessible_ports)} accessible ports:")
        for port, desc in accessible_ports:
            print(f"   • {port} - {description}")
    else:
        print("❌ No TWS/Gateway ports accessible")

    print()


def print_tws_checklist():
    """Print TWS configuration checklist"""
    print("📋 TWS Configuration Checklist")
    print("-" * 30)
    print("On your Windows TWS computer (192.168.1.4):")
    print()
    print("1. ✅ TWS Status:")
    print("   • Is TWS running and showing 'Connected' (green)?")
    print("   • Is paper trading account logged in?")
    print("   • Any error messages or dialogs in TWS?")
    print()
    print("2. ✅ API Settings (File → Global Configuration → API):")
    print("   • 'Enable ActiveX and Socket Clients' - CHECKED")
    print("   • Socket Port: 7497")
    print("   • Trusted IPs: 192.168.1.9 (this Linux computer)")
    print()
    print("3. ✅ Connection Monitoring:")
    print("   • Go to: Data → API Connections")
    print("   • Check for connection attempts from 192.168.1.9")
    print("   • Look for any blocked/rejected connections")
    print()
    print("4. ✅ Order Settings:")
    print("   • Find and DISABLE any 'Download orders on connection'")
    print("   • This prevents startup timeout issues")
    print()
    print("5. ✅ Troubleshooting:")
    print("   • Try restarting TWS completely")
    print("   • Check for Windows firewall popups")
    print("   • Look for connection approval dialogs")
    print()


def main():
    """Main test function"""
    print_header()

    print("This script will test TWS connectivity and help identify")
    print("what's preventing the API handshake from completing.")
    print()

    # Run tests
    test_basic_connectivity()

    print("🎯 CRITICAL TEST:")
    handshake_ok = test_tws_api_handshake()

    check_multiple_ports()

    # Results
    print("📊 TEST RESULTS")
    print("=" * 15)

    if handshake_ok:
        print("🎉 SUCCESS: TWS API is responding!")
        print("✅ The handshake issue may be resolved")
        print("✅ Try running the full MAESTRO test now")
    else:
        print("❌ ISSUE: TWS API is not responding to handshake")
        print("❌ This confirms the problem is TWS configuration")
        print()
        print("🔧 NEXT STEPS:")
        print("1. Check TWS settings using checklist below")
        print("2. Restart TWS completely")
        print("3. Run this test again")
        print("4. If still failing, check TWS logs for errors")

    print()
    print_tws_checklist()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted")
    except Exception as e:
        print(f"\n💥 Error: {e}")
