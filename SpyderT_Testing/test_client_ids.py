#!/usr/bin/env python3
"""
Test multiple client IDs to identify connection conflicts
"""

import time
import threading
from datetime import datetime
from ibapi.client import EClient
from ibapi.wrapper import EWrapper


class ClientIDTester(EClient, EWrapper):
    """Test different client IDs for IB Gateway connection"""

    def __init__(self, client_id):
        EClient.__init__(self, self)
        self.client_id = client_id
        self.connected = False
        self.next_valid_id_received = False
        self.managed_accounts_received = False
        self.connection_time = None
        self.errors = []

    def connectAck(self):
        """Called when connection is acknowledged"""
        self.connected = True
        self.connection_time = time.time()
        print(f"  ✅ Client ID {self.client_id}: Connection ACK received")

    def nextValidId(self, orderId):
        """Called when next valid ID is received - indicates full handshake"""
        self.next_valid_id_received = True
        print(
            f"  🎉 Client ID {self.client_id}: Full handshake complete! Next valid ID: {orderId}"
        )

    def managedAccounts(self, accountsList):
        """Called when managed accounts are received"""
        self.managed_accounts_received = True
        print(f"  📊 Client ID {self.client_id}: Managed accounts: {accountsList}")

    def error(self, reqId, errorCode, errorString, advancedOrderReject=""):
        """Handle errors"""
        self.errors.append((errorCode, errorString))

        if errorCode in [2104, 2106, 2158]:  # Market data info
            print(f"  ℹ️  Client ID {self.client_id}: {errorString}")
        elif errorCode == 502:  # Already connected
            print(f"  ⚠️  Client ID {self.client_id}: Already connected error")
        elif errorCode in [1100, 1101, 1102]:  # Connection status
            print(f"  📡 Client ID {self.client_id}: {errorString}")
        else:
            print(f"  ❌ Client ID {self.client_id}: Error {errorCode}: {errorString}")


def test_client_id(client_id, timeout=8):
    """Test a specific client ID"""
    print(f"\n🔍 Testing Client ID: {client_id}")
    print(f"   Timeout: {timeout} seconds")

    app = ClientIDTester(client_id)

    try:
        # Connect
        print(f"   Connecting to 127.0.0.1:4002...")
        app.connect("127.0.0.1", 4002, client_id)

        # Start message loop in thread
        def run_loop():
            try:
                app.run()
            except Exception as e:
                print(f"   ❌ Message loop error: {e}")

        thread = threading.Thread(target=run_loop, daemon=True)
        thread.start()

        # Wait for connection
        start_time = time.time()
        while time.time() - start_time < timeout:
            if app.next_valid_id_received:
                elapsed = time.time() - start_time
                print(f"  ✅ SUCCESS in {elapsed:.2f}s - Client ID {client_id} works!")
                app.disconnect()
                return True
            time.sleep(0.1)

        # Timeout
        elapsed = time.time() - start_time
        print(f"  ❌ TIMEOUT after {elapsed:.2f}s")
        print(f"     Connected: {app.connected}")
        print(f"     Next Valid ID: {app.next_valid_id_received}")
        print(f"     Managed Accounts: {app.managed_accounts_received}")

        if app.errors:
            print(f"     Errors: {len(app.errors)}")
            for code, msg in app.errors[-3:]:  # Show last 3 errors
                print(f"       {code}: {msg}")

        try:
            app.disconnect()
        except:
            pass

        return False

    except Exception as e:
        print(f"  ❌ Connection error: {e}")
        return False


def main():
    """Test multiple client IDs"""
    print("🆔 IB Gateway Client ID Connection Tester")
    print(f"Time: {datetime.now()}")
    print("=" * 60)

    # Test various client IDs
    client_ids_to_test = [
        1,  # Default
        2,  # Alternative
        10,  # Higher number
        100,  # Much higher
        999,  # Very high
        0,  # Zero (sometimes special)
        42,  # Random
        123,  # Random
    ]

    successful_clients = []

    for client_id in client_ids_to_test:
        success = test_client_id(client_id)
        if success:
            successful_clients.append(client_id)
            print(f"\n🎉 FOUND WORKING CLIENT ID: {client_id}")

            # Test a few more to see if multiple work
            if len(successful_clients) >= 3:
                print("\n✅ Found enough working client IDs, stopping test")
                break

        time.sleep(1)  # Brief pause between tests

    print("\n" + "=" * 60)
    print("📋 FINAL RESULTS:")

    if successful_clients:
        print(f"✅ Working Client IDs: {successful_clients}")
        print(
            f"🎯 Recommendation: Use Client ID {successful_clients[0]} for your Spyder system"
        )

        # Update config recommendation
        print(f"\n📝 Update your config.py:")
        print(f'   "clientId": {successful_clients[0]},  # Use this working Client ID')

    else:
        print("❌ NO CLIENT IDs worked!")
        print("\n🔧 This suggests one of these issues:")
        print("1. IB Gateway may need to be restarted after API configuration")
        print("2. API settings may not have been applied correctly")
        print("3. There may be a firewall or permission issue")
        print("4. IB Gateway may not be fully logged in")

        print(f"\n🚀 Next steps:")
        print("1. Restart IB Gateway completely")
        print("2. Log in again and verify paper trading mode")
        print("3. Re-check API settings: Configure → Settings → API → Settings")
        print("4. Try this test again")


if __name__ == "__main__":
    main()
