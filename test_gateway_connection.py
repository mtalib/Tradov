#!/usr/bin/env python3
"""
Quick test script to verify IB Gateway connection
Run this from the Spyder project directory with venv activated
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from ib_async import IB
    import time

    print("=" * 60)
    print("IB Gateway Connection Test")
    print("=" * 60)
    print()

    # Test configuration
    host = "127.0.0.1"
    port = 4002  # Paper trading port
    client_id = 999  # Test client ID
    timeout = 10

    print(f"Attempting to connect to Gateway...")
    print(f"  Host: {host}")
    print(f"  Port: {port}")
    print(f"  Client ID: {client_id}")
    print(f"  Timeout: {timeout}s")
    print()

    ib = IB()

    try:
        # Attempt connection
        print("Connecting...")
        ib.connect(host, port, clientId=client_id, timeout=timeout)

        print("✅ Successfully connected to IB Gateway!")
        print()

        # Get connection details
        print("Connection Details:")
        print(f"  Connected: {ib.isConnected()}")
        print(f"  Client ID: {client_id}")
        print()

        # Get account information
        accounts = ib.managedAccounts()
        print(f"Managed Accounts: {accounts}")
        print()

        # Request account summary
        if accounts:
            print("Account Summary:")
            account = accounts[0]

            # Request current positions
            positions = ib.positions()
            print(f"  Open Positions: {len(positions)}")

            # Request portfolio
            portfolio = ib.portfolio()
            print(f"  Portfolio Items: {len(portfolio)}")

        print()
        print("✅ All tests passed!")
        print()

        # Disconnect
        print("Disconnecting...")
        ib.disconnect()
        print("✅ Disconnected successfully")

        sys.exit(0)

    except TimeoutError:
        print("❌ Connection timeout!")
        print()
        print("Possible causes:")
        print("  1. Gateway is not running")
        print("  2. Gateway is still initializing (wait 30-60s after start)")
        print("  3. Gateway is on a different port")
        print("  4. Too many active connections")
        print()
        print("Try:")
        print("  • Check if Gateway is running: ps aux | grep ibgateway")
        print("  • Check if port is listening: ss -tln | grep 4002")
        print("  • Restart Gateway: pkill -f ibgateway && ~/ibgateway/ibgateway")
        sys.exit(1)

    except ConnectionRefusedError:
        print("❌ Connection refused!")
        print()
        print("Gateway is not accepting connections on port", port)
        print("Make sure the Gateway is running and configured correctly")
        sys.exit(1)

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print()
        print(f"Error type: {type(e).__name__}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

except ImportError as e:
    print("❌ Failed to import ib_async")
    print()
    print("Make sure you're running this script with the venv activated:")
    print("  source .venv/bin/activate")
    print("  python test_gateway_connection.py")
    print()
    print(f"Error: {e}")
    sys.exit(1)

except KeyboardInterrupt:
    print()
    print("❌ Test interrupted by user")
    sys.exit(1)
