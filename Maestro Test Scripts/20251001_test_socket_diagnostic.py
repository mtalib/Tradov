#!/usr/bin/env python3
"""
API Client Service Diagnostic
Check if the issue is the same as before - API Client disconnected
"""

import sys
import socket
import time
from datetime import datetime


def test_socket_connection():
    """Test raw socket connection to port 4002"""
    print("🔌 SOCKET CONNECTION TEST")
    print(f"📅 {datetime.now()}")
    print("=" * 40)

    try:
        # Test raw socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)

        print("📡 Attempting raw socket connection to 127.0.0.1:4002...")
        result = sock.connect_ex(("127.0.0.1", 4002))

        if result == 0:
            print("✅ Socket connection successful!")
            print("   Port 4002 is accessible")

            # Try to send a simple message
            try:
                sock.send(b"test")
                print("✅ Data send successful")
            except Exception as e:
                print(f"⚠️  Data send failed: {e}")

        else:
            print(f"❌ Socket connection failed: {result}")

        sock.close()

    except Exception as e:
        print(f"❌ Socket test failed: {e}")

    print("\n🔍 DIAGNOSIS:")
    print("If socket connects but ib_async times out:")
    print("→ API Client service is DISCONNECTED in Gateway GUI")
    print("→ Need to manually re-enable API Client")
    print("→ This is the same issue we fixed before!")


if __name__ == "__main__":
    test_socket_connection()
