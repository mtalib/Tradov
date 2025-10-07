#!/usr/bin/env python3
"""Check IB Gateway status quickly"""

import socket
import subprocess
import sys
import time
from pathlib import Path

# Add Spyder to path for config import
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import configuration
try:
    from config.config import IB_CONFIG
except ImportError:
    # Fallback configuration
    IB_CONFIG = {
        "gateway": {
            "paper": {"host": "127.0.0.1", "port": 4002},
            "live": {"host": "127.0.0.1", "port": 4001},
        }
    }

# Get configured host and port
IB_HOST = IB_CONFIG.get("gateway", {}).get("paper", {}).get("host", "127.0.0.1")
IB_PORT = IB_CONFIG.get("gateway", {}).get("paper", {}).get("port", 4002)


def check_port():
    """Check if IB Gateway port is open"""
    print(f"1. Checking if port {IB_PORT} is open on {IB_HOST}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((IB_HOST, IB_PORT))
        sock.close()

        if result == 0:
            print(f"✅ Port {IB_PORT} is OPEN on {IB_HOST}")
            return True
        else:
            print(
                f"❌ Port {IB_PORT} is CLOSED on {IB_HOST} - IB Gateway not responding"
            )
            return False
    except Exception as e:
        print(f"❌ Error checking port: {e}")
        return False


def check_process():
    """Check if IB Gateway process is running"""
    print("\n2. Checking for IB Gateway process...")
    try:
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            print(f"✅ IB Gateway is running (PID: {', '.join(pids)})")

            # Check memory usage
            for pid in pids:
                try:
                    mem_result = subprocess.run(
                        ["ps", "-p", pid, "-o", "%mem,rss"],
                        capture_output=True,
                        text=True,
                    )
                    print(f"   Memory usage for PID {pid}:")
                    print(f"   {mem_result.stdout}")
                except BaseException:
                    pass
            return True
        else:
            print("❌ IB Gateway process NOT found")
            return False
    except Exception as e:
        print(f"❌ Error checking process: {e}")
        return False


def test_socket_response():
    """Test if socket responds to API handshake"""
    print(f"\n3. Testing API response on {IB_HOST}:{IB_PORT}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((IB_HOST, IB_PORT))

        # Send API handshake
        sock.send(b"API\0")

        # Try to receive response
        sock.settimeout(1)
        try:
            data = sock.recv(100)
            if data:
                print(f"✅ Got API response: {len(data)} bytes")
            else:
                print("❌ No API response")
        except socket.timeout:
            print("❌ API not responding (timeout)")

        sock.close()
    except Exception as e:
        print(f"❌ Socket test failed: {e}")


def main():
    print("=" * 50)
    print("IB GATEWAY STATUS CHECK")
    print(f"Target: {IB_HOST}:{IB_PORT}")
    print("=" * 50)

    port_ok = check_port()
    process_ok = check_process()

    if not port_ok and process_ok:
        print("\n⚠️  IB Gateway is running but port is not open!")
        print("   Try restarting IB Gateway")
    elif not process_ok:
        print("\n⚠️  IB Gateway is not running!")
        print("   Please start IB Gateway and login")
    else:
        test_socket_response()

    print("\n" + "=" * 50)
    print("RECOMMENDATIONS:")
    print("=" * 50)

    if port_ok and process_ok:
        print("1. IB Gateway seems to be in a bad state")
        print("2. Try: pkill -f ibgateway")
        print("3. Start IB Gateway fresh")
        print(f"4. Check the log for 'API server is listening on port {IB_PORT}'")
    else:
        print("1. Start IB Gateway")
        print("2. Login and wait for 'Logged in' status")
        print("3. Verify API is enabled in settings")


if __name__ == "__main__":
    main()
