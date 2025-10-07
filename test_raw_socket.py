#!/usr/bin/env python3
"""
Raw Socket Test for IB Gateway API
==================================

Tests the lowest level socket connection and basic IB API handshake
to diagnose exactly what's happening with the Gateway connection.

This script performs:
1. Basic TCP connection test
2. Raw IB API handshake attempt
3. Protocol-level message analysis
4. Detailed connection state tracking
"""

import socket
import struct
import time
import sys
from datetime import datetime


def log_info(message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] ℹ️  {message}")


def log_success(message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] ✅ {message}")


def log_warning(message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] ⚠️  {message}")


def log_error(message):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] ❌ {message}")


def test_basic_socket_connection(host="127.0.0.1", port=4002):
    """Test basic TCP socket connection"""
    log_info(f"Testing basic TCP connection to {host}:{port}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)

        start_time = time.time()
        result = sock.connect_ex((host, port))
        connect_time = (time.time() - start_time) * 1000

        if result == 0:
            log_success(f"TCP connection successful ({connect_time:.1f}ms)")

            # Check if we can get socket info
            try:
                local_addr = sock.getsockname()
                remote_addr = sock.getpeername()
                log_info(f"Local address: {local_addr}")
                log_info(f"Remote address: {remote_addr}")
            except Exception as e:
                log_warning(f"Cannot get socket addresses: {e}")

            sock.close()
            return True
        else:
            log_error(f"TCP connection failed with error code: {result}")
            sock.close()
            return False

    except Exception as e:
        log_error(f"Socket connection error: {e}")
        return False


def create_ib_api_handshake_message(client_id=999):
    """Create IB API handshake message"""

    # IB API handshake format:
    # 1. API Version (as string) + null terminator
    # 2. Client ID (as string) + null terminator

    api_version = "100"  # Standard API version
    client_id_str = str(client_id)

    # Build message with proper null terminators
    message = (
        api_version.encode("utf-8") + b"\x00" + client_id_str.encode("utf-8") + b"\x00"
    )

    # Add message length prefix (4 bytes, big endian)
    message_length = len(message)
    length_prefix = struct.pack(">I", message_length)

    full_message = length_prefix + message

    log_info(f"Created handshake message:")
    log_info(f"  API Version: {api_version}")
    log_info(f"  Client ID: {client_id}")
    log_info(f"  Message length: {message_length} bytes")
    log_info(f"  Full message length: {len(full_message)} bytes")
    log_info(f"  Raw bytes: {full_message.hex()}")

    return full_message


def test_ib_api_handshake(host="127.0.0.1", port=4002, client_id=999, timeout=15):
    """Test IB API handshake protocol"""
    log_info(f"Testing IB API handshake to {host}:{port} with client ID {client_id}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        # Step 1: Connect
        log_info("Step 1: Establishing TCP connection...")
        start_time = time.time()
        sock.connect((host, port))
        connect_time = (time.time() - start_time) * 1000
        log_success(f"TCP connected ({connect_time:.1f}ms)")

        # Step 2: Send handshake
        log_info("Step 2: Sending IB API handshake...")
        handshake_msg = create_ib_api_handshake_message(client_id)

        send_start = time.time()
        bytes_sent = sock.send(handshake_msg)
        send_time = (time.time() - send_start) * 1000

        if bytes_sent == len(handshake_msg):
            log_success(f"Handshake sent successfully ({send_time:.1f}ms)")
        else:
            log_warning(f"Partial send: {bytes_sent}/{len(handshake_msg)} bytes")

        # Step 3: Wait for response
        log_info("Step 3: Waiting for Gateway response...")
        sock.settimeout(10.0)  # 10 second timeout for response

        try:
            response_start = time.time()
            response = sock.recv(4096)  # Read up to 4KB
            response_time = (time.time() - response_start) * 1000

            if response:
                log_success(
                    f"Received response ({response_time:.1f}ms): {len(response)} bytes"
                )
                log_info(f"Response hex: {response.hex()}")

                # Try to decode response
                try:
                    # First 4 bytes should be length
                    if len(response) >= 4:
                        msg_length = struct.unpack(">I", response[:4])[0]
                        log_info(f"Message length field: {msg_length}")

                        if len(response) > 4:
                            payload = response[4:]
                            log_info(f"Payload: {payload}")

                            # Try to decode as text
                            try:
                                decoded = payload.decode("utf-8", errors="replace")
                                log_info(f"Decoded text: '{decoded}'")
                            except:
                                log_info("Cannot decode payload as UTF-8")

                except Exception as decode_error:
                    log_warning(f"Cannot decode response: {decode_error}")

                sock.close()
                return True, response
            else:
                log_error("Empty response received")
                sock.close()
                return False, None

        except socket.timeout:
            log_error("Timeout waiting for Gateway response")
            sock.close()
            return False, None
        except Exception as recv_error:
            log_error(f"Error receiving response: {recv_error}")
            sock.close()
            return False, None

    except socket.timeout:
        log_error(f"Connection timeout ({timeout}s)")
        return False, None
    except Exception as e:
        log_error(f"Handshake error: {e}")
        return False, None


def test_connection_persistence(host="127.0.0.1", port=4002):
    """Test if connection stays open"""
    log_info("Testing connection persistence...")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        log_success("Connected")

        # Wait and see if connection stays open
        log_info("Waiting 5 seconds to test persistence...")
        time.sleep(5)

        # Try to send a small test
        try:
            sock.send(b"\x00\x00\x00\x01\x00")  # Minimal message
            log_info("Connection still active after 5 seconds")
        except:
            log_warning("Connection appears to have been closed by server")

        sock.close()
        return True

    except Exception as e:
        log_error(f"Persistence test failed: {e}")
        return False


def main():
    print("🔌 IB GATEWAY RAW SOCKET API TEST")
    print("=" * 60)
    print(f"Timestamp: {datetime.now()}")
    print("=" * 60)

    host = "127.0.0.1"
    port = 4002
    client_id = 999

    print(f"\n🎯 Target: {host}:{port}")
    print(f"🆔 Client ID: {client_id}")

    # Test 1: Basic TCP connection
    print(f"\n{'=' * 60}")
    print("TEST 1: BASIC TCP CONNECTION")
    print("=" * 60)
    tcp_ok = test_basic_socket_connection(host, port)

    if not tcp_ok:
        log_error("TCP connection failed - cannot proceed with API tests")
        return False

    # Test 2: Connection persistence
    print(f"\n{'=' * 60}")
    print("TEST 2: CONNECTION PERSISTENCE")
    print("=" * 60)
    persistence_ok = test_connection_persistence(host, port)

    # Test 3: IB API Handshake
    print(f"\n{'=' * 60}")
    print("TEST 3: IB API HANDSHAKE")
    print("=" * 60)
    handshake_ok, response = test_ib_api_handshake(host, port, client_id)

    # Summary
    print(f"\n{'=' * 60}")
    print("📊 TEST SUMMARY")
    print("=" * 60)

    results = {
        "TCP Connection": "✅ PASS" if tcp_ok else "❌ FAIL",
        "Connection Persistence": "✅ PASS" if persistence_ok else "❌ FAIL",
        "IB API Handshake": "✅ PASS" if handshake_ok else "❌ FAIL",
    }

    for test, result in results.items():
        print(f"  {test:<25}: {result}")

    print("\n💡 DIAGNOSIS:")
    if tcp_ok and not handshake_ok:
        print("  🔍 TCP connection works but API handshake fails")
        print("  🎯 This indicates Gateway API is NOT properly enabled")
        print("  📋 Required action: Enable API in Gateway GUI")
        print("     Configure → Settings → API → Settings")
        print("     ✅ Enable 'Enable ActiveX and Socket EClients'")
    elif tcp_ok and handshake_ok:
        print("  🎉 All tests PASSED! API connection is working!")
        print("  🚀 Gateway is ready for trading applications")
    else:
        print("  ❌ Basic connectivity issues detected")
        print("  🔧 Check Gateway process and network configuration")

    return handshake_ok


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
