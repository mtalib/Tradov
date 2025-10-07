#!/usr/bin/env python3
"""
Minimal TWS Handshake Debug Test
===============================

This is a stripped-down handshake test that mirrors the exact protocol
that worked with IB Gateway. We'll test the TWS API step-by-step.

Based on the IB Gateway success patterns from the conversation history.
"""

import socket
import time
import struct
import sys


def log(msg, color=""):
    timestamp = time.strftime("%H:%M:%S")
    reset = "\033[0m" if color else ""
    print(f"[{timestamp}] {color}{msg}{reset}")


def log_info(msg):
    log(f"ℹ️  {msg}", "\033[94m")


def log_success(msg):
    log(f"✅ {msg}", "\033[92m")


def log_error(msg):
    log(f"❌ {msg}", "\033[91m")


def log_debug(msg):
    log(f"🔍 {msg}", "\033[95m")


def test_tws_handshake_minimal(host, port, client_id=1):
    """
    Test the exact TWS handshake protocol that should work
    Based on successful IB Gateway patterns
    """
    log_info(f"Testing minimal TWS handshake to {host}:{port} (Client ID: {client_id})")

    sock = None
    try:
        # Step 1: Connect
        log_debug("Creating socket connection...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)

        start_time = time.time()
        sock.connect((host, port))
        connect_time = (time.time() - start_time) * 1000
        log_success(f"Socket connected ({connect_time:.1f}ms)")

        # Step 2: Send "API\0" prefix
        log_debug("Sending API prefix...")
        sock.send(b"API\0")
        time.sleep(0.1)  # Small delay like in successful Gateway tests

        # Step 3: Send version range (this is critical)
        log_debug("Sending version range...")
        version_msg = "v100..176\0"  # Standard version range
        sock.send(version_msg.encode("ascii"))
        time.sleep(0.1)

        # Step 4: Wait for server version response
        log_debug("Waiting for server version...")
        sock.settimeout(5)

        response = sock.recv(1024)
        if response:
            log_success(f"Got server response: {len(response)} bytes")
            log_debug(f"Raw response: {response}")

            # Try to parse server version
            try:
                response_str = response.decode("ascii", errors="ignore")
                log_debug(f"Response as string: '{response_str}'")

                # Server version should be first part before \0
                if "\0" in response_str:
                    server_version = response_str.split("\0")[0]
                    if server_version.isdigit():
                        log_success(f"Server version: {server_version}")

                        # Step 5: Send client ID
                        log_debug(f"Sending client ID: {client_id}")
                        client_msg = f"{client_id}\0"
                        sock.send(client_msg.encode("ascii"))
                        time.sleep(0.1)

                        # Step 6: Final response
                        try:
                            final_response = sock.recv(512)
                            if final_response:
                                log_success("Final handshake response received!")
                                log_debug(f"Final response: {final_response}")
                            else:
                                log_success(
                                    "Handshake completed (no final response expected)"
                                )

                            return True

                        except socket.timeout:
                            log_success(
                                "Handshake completed (timeout on final response is normal)"
                            )
                            return True

                    else:
                        log_error(f"Invalid server version format: '{server_version}'")
                else:
                    log_error("No null terminator in server response")

            except Exception as e:
                log_error(f"Error parsing server response: {e}")

        else:
            log_error("No response from TWS API server")
            return False

    except socket.timeout:
        log_error("Timeout during handshake - TWS API not responding")
        return False

    except ConnectionRefusedError:
        log_error("Connection refused - TWS not listening on port")
        return False

    except Exception as e:
        log_error(f"Handshake failed: {e}")
        return False

    finally:
        if sock:
            try:
                sock.close()
                log_debug("Socket closed")
            except:
                pass

    return False


def test_raw_api_prefix(host, port):
    """Test if TWS responds to just the API prefix"""
    log_info(f"Testing raw API prefix response from {host}:{port}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((host, port))

        log_debug("Sending just 'API\\0'...")
        sock.send(b"API\0")

        sock.settimeout(2)
        response = sock.recv(100)

        if response:
            log_success(f"TWS responded to API prefix: {response}")
            return True
        else:
            log_error("No response to API prefix")
            return False

    except Exception as e:
        log_error(f"API prefix test failed: {e}")
        return False
    finally:
        sock.close()


def test_tws_api_listening(host, port):
    """Test if TWS API server is actually listening and configured"""
    log_info("=== TWS API Configuration Test ===")

    # Test 1: Basic connection
    log_debug("Test 1: Basic socket connection")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((host, port))
        sock.close()
        log_success("Port is open and accepting connections")
    except Exception as e:
        log_error(f"Cannot connect to port: {e}")
        return False

    # Test 2: API prefix response
    log_debug("Test 2: API prefix response")
    if not test_raw_api_prefix(host, port):
        log_error("TWS is not responding to API messages")
        log_error("This usually means:")
        log_error("  • 'Read-Only API' is CHECKED (should be UNCHECKED)")
        log_error("  • 'Enable ActiveX and Socket Clients' is not checked")
        log_error("  • API server is not running in TWS")
        return False

    # Test 3: Full handshake
    log_debug("Test 3: Full handshake protocol")
    return test_tws_handshake_minimal(host, port)


def main():
    if len(sys.argv) != 3:
        print("Usage: python test_tws_handshake_debug.py <host> <port>")
        print("Example: python test_tws_handshake_debug.py 192.168.1.244 7497")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    print("=" * 60)
    print("TWS HANDSHAKE DEBUG TEST")
    print(f"Target: {host}:{port}")
    print("=" * 60)

    success = test_tws_api_listening(host, port)

    print("\n" + "=" * 60)
    if success:
        log_success("TWS API handshake is working!")
        log_info("Your connection should work with ib_async and other clients")
    else:
        log_error("TWS API handshake is NOT working")
        log_info("\nTo fix this, in TWS go to:")
        log_info("File → Global Configuration → API → Settings")
        log_info("\nMake sure:")
        log_info("  ✅ 'Enable ActiveX and Socket Clients' is CHECKED")
        log_info("  ❌ 'Read-Only API' is UNCHECKED")
        log_info("  📝 Socket port is 7497")
        log_info("  🌐 Your IP (192.168.1.9) is in Trusted IPs")
        log_info("\nThen restart TWS completely and test again.")
    print("=" * 60)


if __name__ == "__main__":
    main()
