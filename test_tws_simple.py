#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Simple TWS Connection Test
==================================

Simple, reliable test for TWS API connection without compatibility issues.
This script focuses on the essential connection test without advanced features
that might cause compatibility problems.

Usage:
    python test_tws_simple.py --windows-ip 192.168.1.244
    python test_tws_simple.py --windows-ip 192.168.1.244 --client-id 2

Author: Spyder Trading System
Date: 2025-01-02
"""

import asyncio
import sys
import time
import argparse
from datetime import datetime


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def print_success(text: str):
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def print_error(text: str):
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text: str):
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.END}")


def print_header(text: str):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{text}{Colors.END}")
    print("=" * len(text))


class SimpleTWSTest:
    """Simple TWS connection test"""

    def __init__(self, windows_ip: str, port: int = 7497, client_id: int = 1):
        self.windows_ip = windows_ip
        self.port = port
        self.client_id = client_id
        self.ib = None

    async def test_connection(self) -> bool:
        """Test basic TWS connection"""
        try:
            # Import ib_async
            from ib_async import IB

            print_info("Creating IB connection instance...")
            self.ib = IB()

            print_info(
                f"Connecting to {self.windows_ip}:{self.port} (Client ID: {self.client_id})..."
            )
            print_info("This may take 30-60 seconds for the handshake...")

            start_time = time.time()

            # Simple connect without setTimeout (which causes issues)
            await self.ib.connectAsync(
                host=self.windows_ip,
                port=self.port,
                clientId=self.client_id,
                timeout=60,  # Built-in timeout parameter
            )

            connection_time = time.time() - start_time

            if self.ib.isConnected():
                print_success(
                    f"Connected successfully! ({connection_time:.2f} seconds)"
                )

                # Test basic functionality
                try:
                    accounts = self.ib.managedAccounts()
                    print_success(f"Account info retrieved: {accounts}")

                    # Test a simple market data request
                    from ib_async import Stock

                    spy = Stock("SPY", "SMART", "USD")

                    print_info("Testing market data request...")
                    ticker = self.ib.reqMktData(spy, "", False, False)

                    # Wait a few seconds for data
                    print_info("Waiting for market data (5 seconds)...")
                    await asyncio.sleep(5)

                    if (
                        hasattr(ticker, "last")
                        and ticker.last
                        and float(ticker.last) > 0
                    ):
                        print_success(f"Market data working: SPY @ ${ticker.last}")
                    else:
                        print_warning(
                            "Connected but no market data received (may be normal after hours)"
                        )

                    # Cancel market data
                    self.ib.cancelMktData(spy)

                    return True

                except Exception as e:
                    print_warning(f"Connected but API test failed: {e}")
                    return True  # Still consider it a success if we connected

            else:
                print_error("Connection failed - not connected")
                return False

        except asyncio.TimeoutError:
            print_error("Connection timeout (60 seconds)")
            print_info("Possible causes:")
            print_info("  • TWS API not enabled (check API settings)")
            print_info("  • Firewall blocking connection")
            print_info("  • Wrong IP address or port")
            print_info("  • TWS not logged in properly")
            return False

        except ImportError:
            print_error("ib_async not installed")
            print_info("Install with: pip install ib_async")
            return False

        except ConnectionRefusedError:
            print_error("Connection refused")
            print_info("Possible causes:")
            print_info("  • TWS not running")
            print_info("  • Wrong port number")
            print_info("  • Firewall blocking connection")
            return False

        except Exception as e:
            print_error(f"Connection failed: {e}")
            print_info(f"Error type: {type(e).__name__}")
            return False

    async def disconnect(self):
        """Disconnect from TWS"""
        if self.ib and self.ib.isConnected():
            try:
                print_info("Disconnecting...")
                await self.ib.disconnectAsync()
                print_success("Disconnected successfully")
            except Exception as e:
                print_warning(f"Disconnect error: {e}")

    async def run_test(self) -> bool:
        """Run the complete test"""
        print_header(f"SIMPLE TWS CONNECTION TEST")
        print(f"Target: {self.windows_ip}:{self.port}")
        print(f"Client ID: {self.client_id}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("")

        try:
            success = await self.test_connection()

            # Always try to disconnect
            await self.disconnect()

            print_header("TEST RESULTS")
            if success:
                print_success("TWS connection test PASSED")
                print_info("Your remote TWS setup is working correctly!")
                print_info("Next steps:")
                print_info(
                    "  1. Run: ./setup_remote_tws.sh --windows-ip " + self.windows_ip
                )
                print_info("  2. Launch your Spyder dashboard")
            else:
                print_error("TWS connection test FAILED")
                print_info("Troubleshooting steps:")
                print_info("  1. Verify TWS is running and logged in on Windows")
                print_info(
                    "  2. Check TWS API settings (Enable ActiveX and Socket Clients)"
                )
                print_info("  3. Add this computer's IP to TWS Trusted IPs")
                print_info("  4. Check Windows Firewall settings")
                print_info("  5. Try a different client ID (--client-id 2)")

            return success

        except KeyboardInterrupt:
            print_warning("Test interrupted by user")
            await self.disconnect()
            return False

        except Exception as e:
            print_error(f"Test suite error: {e}")
            await self.disconnect()
            return False


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Simple TWS Connection Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python test_tws_simple.py --windows-ip 192.168.1.244
    python test_tws_simple.py --windows-ip 192.168.1.244 --client-id 2
    python test_tws_simple.py --windows-ip 192.168.1.244 --port 7496
        """,
    )

    parser.add_argument(
        "--windows-ip", required=True, help="IP address of Windows computer running TWS"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7497,
        help="TWS port (7497 for paper, 7496 for live, default: 7497)",
    )
    parser.add_argument(
        "--client-id", type=int, default=1, help="Client ID for connection (default: 1)"
    )

    args = parser.parse_args()

    # Validate IP format
    try:
        parts = args.windows_ip.split(".")
        if len(parts) != 4 or not all(0 <= int(part) <= 255 for part in parts):
            raise ValueError("Invalid IP format")
    except ValueError:
        print_error(f"Invalid IP address format: {args.windows_ip}")
        sys.exit(1)

    # Create and run test
    tester = SimpleTWSTest(
        windows_ip=args.windows_ip, port=args.port, client_id=args.client_id
    )

    try:
        success = await tester.run_test()
        sys.exit(0 if success else 1)

    except Exception as e:
        print_error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
