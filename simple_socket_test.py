#!/usr/bin/env python3
"""
Simple Socket Test for TWS API Debugging
========================================

This script performs a very basic socket test to see exactly what TWS
responds with when we send API handshake messages.
"""

import socket
import time
import sys
import struct


def log_info(message):
    print(f"ℹ️  {message}")


def log_success(message):
    print(f"✅ {message}")


def log_error(message):
    print(f"❌ {message}")


def log_debug(message):
    print(f"🔍 {message}")


def bytes_to_hex(data):
    """Convert bytes to hex string for debugging"""
    return " ".join(f"{b:02x}" for b in data)


def test_raw_socket_response(host, port):
    """Test raw socket response from TWS"""
    log_info(f"Testing raw socket response from {host}:{port}")

    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        # Connect
        log_debug("Connecting to socket...")
        sock.connect((host, port))
        log_success("Socket connected")

        # Send just the API prefix
        log_debug("Sending API prefix...")
        sock.send(b"API\0")

        # Try to read any response
        log_debug("Waiting for response...")
        sock.settimeout(2)

        try:
            response = sock.recv(1024)
            if response:
                log_success(f"Got response: {len(response)} bytes")
                log_debug(f"Raw bytes: {bytes_to_hex(response)}")
                log_debug(f"As string: {response}")
            else:
                log_error("No response received")
        except socket.timeout:
            log_error("Timeout waiting for response")
        except Exception as e:
            log_error(f"Error reading response: {e}")

        sock.close()
        log_debug("Socket closed")

    except Exception as e:
        log_error(f"Socket test failed: {e}")


def test_ib_handshake_manual(host, port, client_id=1):
    """Test manual IB API handshake"""
    log_info(f"Testing IB API handshake (Client ID: {client_id})")

    try:
        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)

        # Connect
        log_debug("Connecting...")
        sock.connect((host, port))
        log_success("Connected")

        # Send API prefix
        log_debug("Sending API prefix 'API\\0'...")
        sock.send(b"API\0")

        # Send version info (this is what ib_async does)
        version_msg = f"v{38}..{176}"  # API version 38, min version 176
        log_debug(f"Sending version: {version_msg}")

        # Encode the version message
        version_bytes = version_msg.encode("utf-8")
        version_length = len(version_bytes)

        # Send length header (4 bytes) + version message
        length_header = struct.pack(">I", version_length)
        sock.send(length_header + version_bytes)

        # Send client ID
        client_msg = str(client_id)
        client_bytes = client_msg.encode("utf-8")
        client_length = len(client_bytes)
        client_header = struct.pack(">I", client_length)

        log_debug(f"Sending client ID: {client_id}")
        sock.send(client_header + client_bytes)

        # Wait for response
        log_debug("Waiting for TWS response...")
        sock.settimeout(5)

        try:
            # Try to read response
            response = sock.recv(1024)
            if response:
                log_success(f"Got TWS response: {len(response)} bytes")
                log_debug(f"Raw bytes: {bytes_to_hex(response)}")

                # Try to parse as string
                try:
                    response_str = response.decode("utf-8", errors="ignore")
                    log_debug(f"As string: '{response_str}'")
                except:
                    log_debug("Could not decode as string")

                # Try to parse as IB message
                if len(response) >= 4:
                    msg_length = struct.unpack(">I", response[:4])[0]
                    log_debug(f"Message length: {msg_length}")
                    if len(response) > 4:
                        msg_content = response[4 : 4 + msg_length].decode(
                            "utf-8", errors="ignore"
                        )
                        log_debug(f"Message content: '{msg_content}'")

                return True
            else:
                log_error("No response from TWS")
                return False

        except socket.timeout:
            log_error("Timeout - TWS did not respond")
            return False
        except Exception as e:
            log_error(f"Error reading response: {e}")
            return False
        finally:
            sock.close()

    except Exception as e:
        log_error(f"Handshake failed: {e}")
        return False


def test_simple_connection(host, port):
    """Test if we can connect and immediately disconnect"""
    log_info(f"Testing simple connect/disconnect to {host}:{port}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)

        start_time = time.time()
        sock.connect((host, port))
        connect_time = time.time() - start_time

        log_success(f"Connection successful ({connect_time * 1000:.1f}ms)")

        # Immediately close
        sock.close()
        log_debug("Connection closed")
        return True

    except Exception as e:
        log_error(f"Connection failed: {e}")
        return False


def test_port_behavior(host, port):
    """Test what happens when we connect multiple times"""
    log_info(f"Testing port behavior on {host}:{port}")

    success_count = 0
    for i in range(5):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((host, port))
            sock.close()
            success_count += 1
            log_debug(f"Connection {i + 1}: OK")
        except Exception as e:
            log_debug(f"Connection {i + 1}: FAILED - {e}")

        time.sleep(0.5)

    log_info(f"Port behavior: {success_count}/5 connections successful")
    return success_count == 5


def main():
    if len(sys.argv) != 3:
        print("Usage: python simple_socket_test.py <host> <port>")
        print("Example: python simple_socket_test.py 192.168.1.244 7497")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    print("=" * 60)
    print("SIMPLE TWS SOCKET TEST")
    print(f"Target: {host}:{port}")
    print("=" * 60)

    # Test 1: Simple connection
    print("\n🧪 Test 1: Simple Connection Test")
    test_simple_connection(host, port)

    # Test 2: Port behavior
    print("\n🧪 Test 2: Port Behavior Test")
    test_port_behavior(host, port)

    # Test 3: Raw socket response
    print("\n🧪 Test 3: Raw Socket Response")
    test_raw_socket_response(host, port)

    # Test 4: Manual IB handshake
    print("\n🧪 Test 4: Manual IB API Handshake")
    success = test_ib_handshake_manual(host, port, client_id=1)

    if not success:
        print("\n🧪 Test 5: Try Different Client ID")
        test_ib_handshake_manual(host, port, client_id=999)

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    if success:
        print("✅ TWS is responding to API handshakes")
        print("   Your connection should work!")
    else:
        print("❌ TWS is NOT responding to API handshakes")
        print("   Check TWS API configuration:")
        print("   • 'Enable ActiveX and Socket Clients' must be ✅ checked")
        print("   • 'Read-Only API' must be ❌ UNCHECKED")
        print("   • Add your IP to 'Trusted IPs'")
        print("   • Restart TWS after changes")


if __name__ == "__main__":
    main()
