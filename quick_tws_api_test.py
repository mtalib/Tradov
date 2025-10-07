#!/usr/bin/env python3
"""
Quick TWS API Availability Test
==============================

A simple, fast test to check if TWS API is responding to handshake requests.
This script runs continuously until TWS API is properly configured.

Usage:
    python quick_tws_api_test.py --windows-ip 192.168.1.250

Author: Spyder Trading System
Version: 1.0
Date: 2025-10-04
"""

import socket
import time
import argparse
import sys
from datetime import datetime


def test_tws_api_handshake(ip: str, port: int = 7497) -> bool:
    """
    Test if TWS API responds to a handshake request.

    Args:
        ip: IP address of TWS computer
        port: TWS port (default 7497 for paper trading)

    Returns:
        True if TWS API responds, False otherwise
    """
    try:
        # Create socket connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)  # 5 second timeout

        # Connect to TWS
        sock.connect((ip, port))

        # Send TWS API handshake message
        # Format: "API" + null + version + null + client_id
        handshake_msg = b"API\x00\x00\x00\x02\x00\x00\x00\x01"
        sock.send(handshake_msg)

        # Wait for response
        response = sock.recv(1024)
        sock.close()

        # If we get any response, TWS API is working
        return len(response) > 0

    except socket.timeout:
        # Timeout means TWS API is not responding (not configured)
        return False
    except ConnectionRefusedError:
        # Connection refused means TWS is not running
        return False
    except Exception as e:
        # Any other error
        print(f"   ❌ Error: {e}")
        return False


def continuous_test(ip: str, port: int = 7497, interval: int = 10):
    """
    Continuously test TWS API until it becomes available.

    Args:
        ip: IP address of TWS computer
        port: TWS port
        interval: Test interval in seconds
    """
    print("🔄 CONTINUOUS TWS API AVAILABILITY TEST")
    print("=" * 50)
    print(f"🖥️ Target: {ip}:{port}")
    print(f"⏱️ Test interval: {interval} seconds")
    print("🛑 Press Ctrl+C to stop")
    print("=" * 50)
    print()

    test_count = 0
    start_time = datetime.now()

    try:
        while True:
            test_count += 1
            current_time = datetime.now()
            elapsed = (current_time - start_time).total_seconds()

            print(
                f"🧪 Test #{test_count} at {current_time.strftime('%H:%M:%S')} (elapsed: {elapsed:.0f}s)"
            )

            # Test basic connectivity first
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((ip, port))
                sock.close()

                if result == 0:
                    print(f"   ✅ Port {port} accessible")

                    # Test TWS API handshake
                    if test_tws_api_handshake(ip, port):
                        print("   🎉 TWS API RESPONDING!")
                        print("   ✅ API handshake successful")
                        print()
                        print("🎯 SUCCESS: TWS API is now configured and working!")
                        print("🚀 You can now run your Spyder trading system")
                        print()
                        print("Next steps:")
                        print(
                            "1. Run: python test_remote_tws_connection.py --windows-ip",
                            ip,
                        )
                        print("2. If successful, integrate with your trading system")
                        return True
                    else:
                        print("   ❌ TWS API not responding (API not enabled)")
                        print("   💡 Configure TWS API settings and restart TWS")
                else:
                    print(f"   ❌ Port {port} not accessible (TWS not running?)")

            except Exception as e:
                print(f"   ❌ Network error: {e}")

            print(f"   ⏳ Waiting {interval} seconds...")
            print()

            # Wait for next test
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n⏹️ Test stopped by user")
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"📊 Ran {test_count} tests over {elapsed:.0f} seconds")
        print("🔧 Configure TWS API settings on Windows computer to enable API")
        return False


def single_test(ip: str, port: int = 7497):
    """
    Run a single TWS API test.

    Args:
        ip: IP address of TWS computer
        port: TWS port
    """
    print("🧪 SINGLE TWS API TEST")
    print("=" * 30)
    print(f"🖥️ Target: {ip}:{port}")
    print(f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Test port accessibility
    print("🌐 Testing port accessibility...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            print(f"   ✅ Port {port} is accessible")
        else:
            print(f"   ❌ Port {port} not accessible")
            print("   💡 Make sure TWS is running on Windows computer")
            return False

    except Exception as e:
        print(f"   ❌ Port test error: {e}")
        return False

    # Test TWS API handshake
    print("🤝 Testing TWS API handshake...")
    if test_tws_api_handshake(ip, port):
        print("   ✅ TWS API is responding!")
        print("   🎉 SUCCESS: API is configured correctly")
        return True
    else:
        print("   ❌ TWS API not responding")
        print("   💡 TWS API settings need to be configured")
        print()
        print("🔧 TO FIX THIS:")
        print("1. On Windows computer, open TWS")
        print("2. Go to: File → Global Configuration → API → Settings")
        print("3. Enable 'ActiveX and Socket Clients'")
        print("4. Uncheck 'Allow connections from localhost only'")
        print("5. Add '192.168.1.9' to Trusted IPs")
        print("6. Set port to 7497")
        print("7. Click OK and restart TWS")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Quick TWS API Availability Test")
    parser.add_argument(
        "--windows-ip", required=True, help="IP address of Windows computer running TWS"
    )
    parser.add_argument(
        "--port", type=int, default=7497, help="TWS port (default: 7497)"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous tests until API is available",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Test interval for continuous mode (seconds)",
    )

    args = parser.parse_args()

    if args.continuous:
        continuous_test(args.windows_ip, args.port, args.interval)
    else:
        success = single_test(args.windows_ip, args.port)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
