#!/usr/bin/env python3
"""
Quick IB Gateway API Configuration Checker
Helps identify common configuration issues
"""

import socket
import time
from datetime import datetime


def check_port_availability(host="127.0.0.1", port=4002):
    """Check if port is open and accepting connections"""
    print(f"🔌 Checking TCP connection to {host}:{port}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            print(f"✅ Port {port} is OPEN and accepting connections")
            return True
        else:
            print(f"❌ Port {port} is CLOSED or unreachable")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False


def test_api_handshake_basic(host="127.0.0.1", port=4002):
    """Test basic API handshake without full IBAPI"""
    print(f"\n🤝 Testing basic API handshake on {host}:{port}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        print("   Connecting...")
        sock.connect((host, port))

        print("   Sending minimal handshake...")
        # Send a minimal API handshake (simplified version)
        handshake = b"API\x00"
        sock.send(handshake)

        print("   Waiting for response...")
        response = sock.recv(1024)

        if response:
            print(f"✅ Received response: {len(response)} bytes")
            print("   This suggests API is configured correctly!")
            return True
        else:
            print("❌ No response received - API likely not configured")
            return False

    except socket.timeout:
        print("❌ TIMEOUT - IB Gateway is not responding to API requests")
        print("   This usually means API connections are not enabled")
        return False
    except Exception as e:
        print(f"❌ Error during handshake: {e}")
        return False
    finally:
        try:
            sock.close()
        except:
            pass


def main():
    print("🔍 IB Gateway API Configuration Checker")
    print(f"Time: {datetime.now()}")
    print("=" * 50)

    # Step 1: Check if port is open
    if not check_port_availability():
        print("\n❌ IB Gateway is not running or port 4002 is not open")
        print("   Please start IB Gateway first")
        return

    # Step 2: Test API handshake
    api_working = test_api_handshake_basic()

    print("\n" + "=" * 50)
    print("📋 DIAGNOSIS:")

    if api_working:
        print("✅ IB Gateway API is properly configured!")
        print("   Your Spyder system should be able to connect")
    else:
        print("❌ IB Gateway API is NOT configured properly")
        print("\n🔧 TO FIX THIS:")
        print("1. Open IB Gateway application window")
        print("2. Go to Configure → Settings → API → Settings")
        print("3. Check 'Enable ActiveX and Socket Clients'")
        print("4. Set 'Socket port' to 4002")
        print("5. Ensure 'Allow connections from: localhost' is checked")
        print("6. If you want to place orders, uncheck 'Read-Only API'")
        print("7. Click OK and restart IB Gateway")

        print("\n⚠️  SECURITY NOTE:")
        print("   Only allow connections from localhost (127.0.0.1)")
        print("   Never allow connections from 0.0.0.0 or external IPs")


if __name__ == "__main__":
    main()
