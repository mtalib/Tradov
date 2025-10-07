#!/usr/bin/env python3
"""
SPYDER - Python Raw Socket Test
===============================

This test uses raw Python sockets to communicate with IB Gateway,
bypassing ib_async and ibapi libraries to isolate the communication issue.

Since Java can connect successfully but Python libraries fail,
this will help us understand what's different about the Python communication.
"""

import socket
import time
import struct
import threading
from datetime import datetime


def log(message):
    """Log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


def test_raw_socket_connection():
    """Test raw socket connection to Gateway"""

    print("🕷️ SPYDER - Python Raw Socket Test")
    print("=" * 50)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    host = "127.0.0.1"
    port = 4002
    client_id = 456

    log("🔍 STEP 1: Testing basic socket connection...")

    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)

        # Connect
        start_time = time.time()
        sock.connect((host, port))
        connect_time = time.time() - start_time

        log(f"✅ Socket connected in {connect_time:.3f}s")

        # Test 1: Just hold connection (like Java test)
        log("🔍 STEP 2: Holding connection for 3 seconds...")
        time.sleep(3)

        if sock.fileno() != -1:  # Socket still open
            log("✅ Connection held successfully (like Java)")
        else:
            log("❌ Connection was closed")
            return False

        # Test 2: Send simple data (what Java sent)
        log("🔍 STEP 3: Sending simple API marker...")
        try:
            sock.send(b"API\0")
            log("✅ Sent 'API\\0' marker")
            time.sleep(1)

            if sock.fileno() != -1:
                log("✅ Connection still alive after API marker")
            else:
                log("❌ Connection closed after API marker")
                return False

        except Exception as e:
            log(f"❌ Error sending API marker: {e}")
            return False

        # Test 3: Try to receive any response
        log("🔍 STEP 4: Checking for Gateway response...")
        try:
            sock.settimeout(2.0)
            data = sock.recv(1024)
            if data:
                log(f"✅ Received {len(data)} bytes: {data[:20]}...")
            else:
                log("ℹ️ No data received (normal for simple test)")
        except socket.timeout:
            log("ℹ️ No response within 2 seconds (normal)")
        except Exception as e:
            log(f"⚠️ Receive error: {e}")

        # Test 4: Send IBAPI-style handshake
        log("🔍 STEP 5: Sending IBAPI-style handshake...")
        try:
            # This mimics what ibapi does for initial handshake
            # Format: version + client_id
            handshake = f"API\0\0\0\0\tv100..176\0{client_id}\0"
            sock.send(handshake.encode("utf-8"))
            log("✅ Sent IBAPI-style handshake")

            time.sleep(2)

            if sock.fileno() != -1:
                log("✅ Connection survived IBAPI handshake")
            else:
                log("❌ IBAPI handshake caused connection closure")
                return False

        except Exception as e:
            log(f"❌ IBAPI handshake error: {e}")
            return False

        # Test 5: Check connection stability
        log("🔍 STEP 6: Final connection stability check...")
        time.sleep(2)

        if sock.fileno() != -1:
            log("✅ Connection remained stable throughout all tests")
            success = True
        else:
            log("❌ Connection was lost during testing")
            success = False

        # Clean close
        sock.close()
        log("🔧 Socket closed cleanly")

        return success

    except ConnectionRefusedError:
        log("❌ Connection refused - Gateway not listening")
        return False
    except socket.timeout:
        log("❌ Connection timeout")
        return False
    except Exception as e:
        log(f"❌ Unexpected error: {e}")
        return False


def test_python_vs_java_behavior():
    """Compare Python socket behavior to Java"""

    print("\n" + "=" * 60)
    print("🔬 PYTHON vs JAVA COMPARISON TEST")
    print("=" * 60)

    # Test multiple connection patterns
    tests = [
        ("Basic Connect & Hold", test_basic_connect_hold),
        ("Send API Marker", test_send_api_marker),
        ("IBAPI Protocol Start", test_ibapi_protocol_start),
        ("Multiple Rapid Connects", test_multiple_connects),
    ]

    results = {}

    for test_name, test_func in tests:
        log(f"🧪 Running: {test_name}")
        try:
            result = test_func()
            results[test_name] = result
            log(f"   {'✅ PASS' if result else '❌ FAIL'}")
        except Exception as e:
            log(f"   💥 ERROR: {e}")
            results[test_name] = False

        time.sleep(1)  # Brief pause between tests

    # Analyze results
    print("\n" + "=" * 60)
    print("📊 COMPARISON RESULTS")
    print("=" * 60)

    passing_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)

    print(f"📈 Tests Passed: {passing_tests}/{total_tests}")
    print()

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status}: {test_name}")

    if passing_tests == total_tests:
        print("\n🎉 ALL PYTHON SOCKET TESTS PASSED!")
        print("   • Python raw sockets work fine with Gateway")
        print("   • The issue is in ib_async/ibapi libraries specifically")
        print("   • Problem is likely in API protocol implementation")
    elif passing_tests > 0:
        print("\n⚠️ PARTIAL SUCCESS")
        print("   • Some Python socket operations work")
        print("   • Issue may be in specific API protocol steps")
    else:
        print("\n❌ ALL PYTHON SOCKET TESTS FAILED")
        print("   • Python socket behavior differs from Java")
        print("   • May be Python environment or OS-level issue")


def test_basic_connect_hold():
    """Test 1: Just connect and hold (like Java did)"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(("127.0.0.1", 4002))
        time.sleep(3)
        is_connected = sock.fileno() != -1
        sock.close()
        return is_connected
    except:
        return False


def test_send_api_marker():
    """Test 2: Send API marker (like Java did)"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(("127.0.0.1", 4002))
        sock.send(b"API\0")
        time.sleep(2)
        is_connected = sock.fileno() != -1
        sock.close()
        return is_connected
    except:
        return False


def test_ibapi_protocol_start():
    """Test 3: Start IBAPI protocol handshake"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect(("127.0.0.1", 4002))

        # Send version info (simplified IBAPI handshake)
        handshake = "API\0\0\0\0\tv100..176\0456\0"
        sock.send(handshake.encode("utf-8"))
        time.sleep(2)

        is_connected = sock.fileno() != -1
        sock.close()
        return is_connected
    except:
        return False


def test_multiple_connects():
    """Test 4: Multiple rapid connections (test for rate limiting)"""
    success_count = 0

    for i in range(3):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3.0)
            sock.connect(("127.0.0.1", 4002))
            time.sleep(1)
            sock.close()
            success_count += 1
        except:
            pass

        time.sleep(0.5)  # Brief pause between connections

    return success_count >= 2  # At least 2/3 should succeed


def main():
    """Main test function"""

    try:
        # Run primary raw socket test
        primary_success = test_raw_socket_connection()

        # Run comparison tests
        test_python_vs_java_behavior()

        print("\n" + "=" * 70)
        print("🏁 FINAL ANALYSIS")
        print("=" * 70)

        if primary_success:
            print("🎯 CONCLUSION: Python raw sockets work with IB Gateway!")
            print()
            print("💡 This means:")
            print("   • Gateway configuration is correct")
            print("   • Python networking is working")
            print("   • The issue is in ib_async/ibapi libraries")
            print()
            print("🔧 NEXT STEPS:")
            print("   1. Update ib_async and ibapi to latest versions")
            print("   2. Check for Python version compatibility issues")
            print("   3. Try alternative IB API libraries")
            print("   4. Implement custom raw socket API client")
            print("   5. Check library configuration/initialization")

        else:
            print("🚨 CONCLUSION: Python socket communication is problematic")
            print()
            print("💡 This suggests:")
            print("   • Python environment issue")
            print("   • OS-level networking problem")
            print("   • Python vs Java socket behavior difference")
            print()
            print("🔧 NEXT STEPS:")
            print("   1. Check Python socket library version")
            print("   2. Test with different Python version")
            print("   3. Check OS networking configuration")
            print("   4. Compare Python/Java socket options")
            print("   5. Consider Docker container for clean environment")

        return primary_success

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
