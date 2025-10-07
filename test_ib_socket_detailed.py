#!/usr/bin/env python3
"""
Detailed IB Gateway Socket Connection Test
==========================================

This script performs a detailed analysis of socket connection behavior with IB Gateway
to understand exactly what happens during the connection attempt and why it might be
getting rejected.

The test will:
1. Establish TCP connection
2. Send proper IB API handshake
3. Monitor socket state changes
4. Capture any data received
5. Provide detailed timing and error information

Usage:
    python test_ib_socket_detailed.py
    python test_ib_socket_detailed.py --port 4001
    python test_ib_socket_detailed.py --verbose
"""

import socket
import time
import struct
import sys
import threading
from datetime import datetime
import argparse


class IBSocketDetailedTest:
    """Detailed socket connection test for IB Gateway"""

    def __init__(self, host="localhost", port=4002, verbose=False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.connection_log = []

    def log_event(self, event, details=""):
        """Log connection events with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = {"timestamp": timestamp, "event": event, "details": details}
        self.connection_log.append(log_entry)

        if self.verbose:
            print(f"[{timestamp}] {event}: {details}")

    def create_ib_handshake_message(self, client_id=1):
        """Create proper IB API handshake message"""
        # IB API handshake format:
        # 1. API version (4 bytes)
        # 2. Client ID (4 bytes)
        # 3. Optional client version string

        api_version = 100  # Standard API version
        message = struct.pack(">I", api_version)  # Big endian 4-byte integer
        message += struct.pack(">I", client_id)  # Big endian 4-byte integer

        # Add client version string (optional but recommended)
        client_version = "Python Test Client v1.0"
        version_bytes = client_version.encode("utf-8")
        message += struct.pack(">I", len(version_bytes))  # Length prefix
        message += version_bytes

        return message

    def test_basic_socket_connection(self):
        """Test basic socket connection without IB protocol"""
        print("🔍 BASIC SOCKET CONNECTION TEST")
        print("-" * 50)

        self.log_event("TEST_START", "Basic socket connection test")

        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)
            self.log_event("SOCKET_CREATED", f"Socket created, timeout=10s")

            # Record connection attempt time
            connect_start = time.time()
            self.log_event("CONNECT_ATTEMPT", f"Connecting to {self.host}:{self.port}")

            # Attempt connection
            result = sock.connect_ex((self.host, self.port))
            connect_end = time.time()
            connect_time = (connect_end - connect_start) * 1000

            if result == 0:
                self.log_event("CONNECT_SUCCESS", f"Connected in {connect_time:.2f}ms")

                # Try to receive any initial data
                try:
                    sock.settimeout(2.0)
                    data = sock.recv(1024)
                    if data:
                        self.log_event(
                            "DATA_RECEIVED", f"Received {len(data)} bytes: {data[:50]}"
                        )
                    else:
                        self.log_event("NO_DATA", "No initial data received")
                except socket.timeout:
                    self.log_event(
                        "RECEIVE_TIMEOUT", "Timeout waiting for initial data"
                    )
                except Exception as e:
                    self.log_event("RECEIVE_ERROR", f"Error receiving data: {e}")

                # Check if socket is still connected
                try:
                    error = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                    if error:
                        self.log_event("SOCKET_ERROR", f"Socket error code: {error}")
                    else:
                        self.log_event("SOCKET_OK", "Socket appears healthy")
                except:
                    self.log_event(
                        "SOCKET_CHECK_FAILED", "Could not check socket status"
                    )

            else:
                self.log_event(
                    "CONNECT_FAILED", f"Connection failed with error: {result}"
                )

            sock.close()
            self.log_event("SOCKET_CLOSED", "Socket closed")

        except Exception as e:
            self.log_event("EXCEPTION", f"Exception during basic test: {e}")

        return result == 0

    def test_ib_protocol_handshake(self, client_id=1):
        """Test IB API protocol handshake"""
        print(f"\n🤝 IB API PROTOCOL HANDSHAKE TEST (Client ID: {client_id})")
        print("-" * 50)

        self.log_event(
            "HANDSHAKE_START", f"Starting IB API handshake with client ID {client_id}"
        )

        try:
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10.0)

            # Connect
            connect_start = time.time()
            result = sock.connect_ex((self.host, self.port))
            connect_time = (time.time() - connect_start) * 1000

            if result != 0:
                self.log_event(
                    "HANDSHAKE_CONNECT_FAILED", f"Failed to connect: {result}"
                )
                return False

            self.log_event("HANDSHAKE_CONNECTED", f"Connected in {connect_time:.2f}ms")

            # Create and send IB handshake message
            handshake_msg = self.create_ib_handshake_message(client_id)
            self.log_event(
                "HANDSHAKE_CREATED",
                f"Handshake message created, {len(handshake_msg)} bytes",
            )

            if self.verbose:
                hex_msg = handshake_msg.hex()
                self.log_event("HANDSHAKE_HEX", f"Message hex: {hex_msg}")

            # Send handshake
            send_start = time.time()
            try:
                bytes_sent = sock.send(handshake_msg)
                send_time = (time.time() - send_start) * 1000
                self.log_event(
                    "HANDSHAKE_SENT", f"Sent {bytes_sent} bytes in {send_time:.2f}ms"
                )
            except Exception as e:
                self.log_event(
                    "HANDSHAKE_SEND_FAILED", f"Failed to send handshake: {e}"
                )
                sock.close()
                return False

            # Wait for response
            self.log_event("WAITING_RESPONSE", "Waiting for handshake response...")

            try:
                sock.settimeout(5.0)
                response_data = b""
                receive_start = time.time()

                # Try to read response in chunks
                while time.time() - receive_start < 5.0:
                    try:
                        chunk = sock.recv(1024)
                        if chunk:
                            response_data += chunk
                            self.log_event(
                                "RESPONSE_CHUNK", f"Received {len(chunk)} bytes"
                            )
                        else:
                            self.log_event(
                                "CONNECTION_CLOSED", "Server closed connection"
                            )
                            break
                    except socket.timeout:
                        break
                    except Exception as e:
                        self.log_event(
                            "RECEIVE_ERROR", f"Error receiving response: {e}"
                        )
                        break

                if response_data:
                    self.log_event(
                        "HANDSHAKE_RESPONSE",
                        f"Total response: {len(response_data)} bytes",
                    )
                    if self.verbose:
                        self.log_event(
                            "RESPONSE_HEX", f"Response hex: {response_data.hex()}"
                        )
                        if len(response_data) >= 4:
                            server_version = struct.unpack(">I", response_data[:4])[0]
                            self.log_event(
                                "SERVER_VERSION", f"Server version: {server_version}"
                            )
                else:
                    self.log_event("NO_RESPONSE", "No response received from server")

            except Exception as e:
                self.log_event(
                    "RESPONSE_EXCEPTION", f"Exception waiting for response: {e}"
                )

            # Check final socket state
            try:
                error = sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                self.log_event("FINAL_SOCKET_STATE", f"Socket error code: {error}")
            except:
                pass

            sock.close()
            self.log_event("HANDSHAKE_COMPLETE", "Handshake test completed")

            return len(response_data) > 0

        except Exception as e:
            self.log_event("HANDSHAKE_EXCEPTION", f"Exception during handshake: {e}")
            return False

    def test_multiple_client_ids(self):
        """Test with multiple client IDs to check for conflicts"""
        print(f"\n🔢 MULTIPLE CLIENT ID TEST")
        print("-" * 50)

        client_ids = [1, 2, 10, 100, 999]
        results = {}

        for client_id in client_ids:
            print(f"\n  Testing Client ID: {client_id}")
            success = self.test_ib_protocol_handshake(client_id)
            results[client_id] = success

            # Wait between tests
            time.sleep(1)

        print(f"\n📊 Client ID Test Results:")
        for client_id, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   Client ID {client_id}: {status}")

        return results

    def test_connection_persistence(self):
        """Test how long a connection stays open"""
        print(f"\n⏱️  CONNECTION PERSISTENCE TEST")
        print("-" * 50)

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)

            result = sock.connect_ex((self.host, self.port))
            if result != 0:
                self.log_event(
                    "PERSISTENCE_CONNECT_FAILED", f"Failed to connect: {result}"
                )
                return False

            self.log_event("PERSISTENCE_START", "Testing connection persistence...")

            # Monitor connection for 30 seconds
            start_time = time.time()
            while time.time() - start_time < 30:
                try:
                    # Try to send a small keepalive
                    sock.send(b"\x00")
                    self.log_event(
                        "KEEPALIVE_SENT",
                        f"Keepalive sent at {time.time() - start_time:.1f}s",
                    )
                except Exception as e:
                    self.log_event(
                        "CONNECTION_LOST",
                        f"Connection lost after {time.time() - start_time:.1f}s: {e}",
                    )
                    break

                time.sleep(5)

            sock.close()

        except Exception as e:
            self.log_event(
                "PERSISTENCE_EXCEPTION", f"Exception during persistence test: {e}"
            )

    def generate_report(self):
        """Generate detailed test report"""
        print(f"\n" + "=" * 60)
        print("📋 DETAILED CONNECTION TEST REPORT")
        print("=" * 60)
        print(f"Target: {self.host}:{self.port}")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Events: {len(self.connection_log)}")

        # Categorize events
        categories = {
            "Connection Events": ["CONNECT_", "SOCKET_"],
            "Handshake Events": ["HANDSHAKE_", "RESPONSE_"],
            "Data Events": ["DATA_", "SEND_", "RECEIVE_"],
            "Errors": ["FAILED", "ERROR", "EXCEPTION"],
            "Success": ["SUCCESS", "SENT", "RECEIVED"],
        }

        print(f"\n📊 Event Summary:")
        for category, keywords in categories.items():
            count = sum(
                1
                for log in self.connection_log
                if any(keyword in log["event"] for keyword in keywords)
            )
            print(f"   {category}: {count} events")

        print(f"\n🕒 Chronological Event Log:")
        for i, log in enumerate(self.connection_log[-20:], 1):  # Show last 20 events
            print(f"   {i:2d}. [{log['timestamp']}] {log['event']}: {log['details']}")

        # Analysis
        connect_success = any(
            "CONNECT_SUCCESS" in log["event"] for log in self.connection_log
        )
        handshake_response = any(
            "HANDSHAKE_RESPONSE" in log["event"] for log in self.connection_log
        )

        print(f"\n🎯 Analysis:")
        print(f"   TCP Connection: {'✅ SUCCESS' if connect_success else '❌ FAILED'}")
        print(
            f"   IB API Handshake: {'✅ SUCCESS' if handshake_response else '❌ FAILED'}"
        )

        if connect_success and not handshake_response:
            print(f"   🔍 Diagnosis: TCP connects but IB API handshake fails")
            print(f"      This suggests IB Gateway is not accepting API connections")
            print(f"      Check: API settings, authentication, client conflicts")
        elif not connect_success:
            print(f"   🔍 Diagnosis: TCP connection fails")
            print(f"      Check: IB Gateway running, port configuration, firewall")
        elif handshake_response:
            print(f"   🔍 Diagnosis: Connection successful!")
            print(f"      IB Gateway is properly accepting API connections")

    def run_comprehensive_test(self):
        """Run comprehensive socket connection test suite"""
        print("🔍 IB GATEWAY DETAILED SOCKET CONNECTION TEST")
        print("=" * 60)
        print(f"Target: {self.host}:{self.port}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Test 1: Basic socket connection
        basic_success = self.test_basic_socket_connection()

        if basic_success:
            # Test 2: IB API handshake
            handshake_success = self.test_ib_protocol_handshake()

            if not handshake_success:
                # Test 3: Try different client IDs
                self.test_multiple_client_ids()

        # Always generate report
        self.generate_report()

        return basic_success


def main():
    parser = argparse.ArgumentParser(
        description="Detailed IB Gateway Socket Connection Test"
    )
    parser.add_argument("--host", default="localhost", help="IB Gateway host")
    parser.add_argument("--port", type=int, default=4002, help="IB Gateway port")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    try:
        tester = IBSocketDetailedTest(args.host, args.port, args.verbose)
        success = tester.run_comprehensive_test()

        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
