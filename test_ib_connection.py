#!/usr/bin/env python3
"""Test actual IB Gateway connection using SpyderClient"""

import sys
import asyncio
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient, IBConfig


async def test_connection():
    """Test connection to IB Gateway on port 4002"""
    print("🧪 Testing IB Gateway connection...")
    print(f"📍 Host: 127.0.0.1, Port: 4002, Client ID: 999")

    try:
        # Create config
        config = IBConfig()
        config.client_id = 999  # Test client ID
        config.host = "127.0.0.1"
        config.port = 4002
        config.timeout = 10.0

        print(f"⚙️  Config created with client_id={config.client_id}")

        # Create client
        client = SpyderClient(config=config)
        print(f"✅ SpyderClient created")

        # Try to connect
        print("🔌 Attempting connection...")
        result = await client.connect()

        print(f"📊 Connect result: {result}")
        print(f"📊 is_connected(): {client.is_connected()}")

        if client.is_connected():
            print("✅ CONNECTION SUCCESSFUL!")

            # Disconnect
            client.disconnect()
            print("🔌 Disconnected successfully")
            return True
        else:
            print("❌ Connection failed - is_connected() returned False")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)
