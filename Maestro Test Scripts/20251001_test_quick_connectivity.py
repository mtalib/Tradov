#!/usr/bin/env python3
"""
Quick IB Gateway Connection Test
Simple test to verify if we can connect to Gateway without hanging
"""

import socket
import time
import sys
from datetime import datetime


def test_basic_socket_connection():
    """Test basic socket connection to Gateway"""
    print("🔌 Testing basic socket connection to Gateway...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout

        print("⏳ Attempting connection to localhost:4002...")
        result = sock.connect_ex(("127.0.0.1", 4002))

        if result == 0:
            print("✅ Socket connection successful!")

            # Try to send a simple message to see if Gateway responds
            print("📡 Testing Gateway response...")

            # Send a simple ping (this might get a response or error)
            try:
                sock.send(b"API\0\0\0\0\x01")  # Simple API handshake attempt
                sock.settimeout(2)
                response = sock.recv(1024)
                print(f"📬 Gateway responded with {len(response)} bytes")
                return True
            except socket.timeout:
                print("⏱️  Gateway didn't respond (timeout) - but connection works")
                return True
            except Exception as e:
                print(f"📡 Gateway connection working, response handling: {e}")
                return True
        else:
            print(f"❌ Socket connection failed with error: {result}")
            return False

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False
    finally:
        try:
            sock.close()
        except:
            pass


def test_ibapi_import():
    """Test if IB API can be imported without issues"""
    print("\n🐍 Testing IB API imports...")

    try:
        sys.path.append("/home/adam/Projects/Spyder")
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        from ibapi.contract import Contract

        print("✅ IB API imports successful")
        return True
    except ImportError as e:
        print(f"❌ IB API import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ IB API import error: {e}")
        return False


def quick_connectivity_test():
    """Run quick tests to diagnose connectivity issues"""
    print("🚀 QUICK IB GATEWAY CONNECTIVITY TEST")
    print(f"📅 Started: {datetime.now()}")
    print("=" * 50)

    # Test 1: Basic socket connection
    socket_ok = test_basic_socket_connection()

    # Test 2: IB API imports
    api_ok = test_ibapi_import()

    # Test 3: Check if Gateway process is running
    print("\n🔍 Checking Gateway process...")
    try:
        import subprocess

        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            print(f"✅ Gateway processes found: {len(pids)} PID(s): {', '.join(pids)}")
        else:
            print("⚠️  No Gateway processes found with pgrep")
    except Exception as e:
        print(f"⚠️  Couldn't check Gateway process: {e}")

    # Summary
    print("\n" + "=" * 50)
    print("📊 CONNECTIVITY TEST SUMMARY")
    print("=" * 50)
    print(f"Socket Connection: {'✅ PASS' if socket_ok else '❌ FAIL'}")
    print(f"IB API Imports: {'✅ PASS' if api_ok else '❌ FAIL'}")

    if socket_ok and api_ok:
        print("\n🎉 Basic connectivity looks good!")
        print("💡 If IB API hangs, it might be waiting for user input in Gateway GUI")
        print("💡 Try checking if Gateway needs configuration or login")
        return True
    else:
        print("\n❌ Connectivity issues detected")
        print("🔧 Check Gateway status and configuration")
        return False


if __name__ == "__main__":
    success = quick_connectivity_test()

    print(f"\n📅 Test completed: {datetime.now()}")

    if success:
        print("\n🎯 Next steps:")
        print("• Gateway appears reachable")
        print("• Try accessing Gateway GUI to check status")
        print("• Ensure paper trading is configured")
    else:
        print("\n🔧 Troubleshooting steps:")
        print("• Check if Gateway is actually running")
        print("• Verify Gateway is listening on port 4002")
        print("• Check Gateway logs for errors")
