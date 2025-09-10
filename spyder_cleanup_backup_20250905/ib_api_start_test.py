import logging
from ib_async import IB

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def test_ib_gateway_connection(host='127.0.0.1', port=4002, client_id=123):
    print("🔍 Starting IB Gateway diagnostic...")

    ib = IB()

    try:
        print(f"🔗 Connecting to {host}:{port} with client ID {client_id}...")
        ib.connect(host, port, client_id)

        if ib.is_connected():
            print("✅ Connection established!")
            print(f"📄 Account: {ib.account}")
            print(f"📦 Server Version: {ib.server_version}")
            print(f"🕒 Connection Time: {ib.connection_time}")
        else:
            print("❌ Connection failed: API not enabled or handshake incomplete.")

    except Exception as e:
        print(f"🚨 Unexpected error: {e}")

                
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected.")


# Run the diagnostic
if __name__ == "__main__":
    test_ib_gateway_connection()

