#!/usr/bin/env python3
"""
MAESTRO Enhanced TWS Connection Test
Based on 6 AI research reports
"""

import asyncio
import socket
import time
from ib_async import IB, util

async def maestro_connection_test():
    """Test with all research-backed optimizations"""
    print("🕷️ MAESTRO Enhanced TWS Connection Test")
    print("=" * 50)

    # Apply TCP optimizations (Copilot solution)
    original_create_connection = asyncio.get_event_loop().create_connection

    async def optimized_connection(*args, **kwargs):
        transport, protocol = await original_create_connection(*args, **kwargs)
        sock = transport.get_extra_info('socket')
        if sock:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        return transport, protocol

    asyncio.get_event_loop().create_connection = optimized_connection

    # Initialize ib_async (Claude's working pattern)
    util.startLoop()
    util.logToConsole('DEBUG')

    ib = IB()
    ib.RequestTimeout = 30.0  # All reports recommend extended timeout

    try:
        print("🔌 Connecting with MAESTRO optimizations...")

        # SOLUTION 1: Read-only mode (ChatGPT/Perplexity fix)
        await ib.connectAsync(
            host='192.168.1.4',
            port=7497,
            clientId=1,
            timeout=15.0,
            readonly=True  # Bypasses reqExecutions timeout
        )

        print("✅ Phase 1: Connection established")

        # SOLUTION 2: Race condition delay (Claude's proven solution)
        print("⏳ Phase 2: Applying race condition delay (1.0s)...")
        await asyncio.sleep(1.0)

        # SOLUTION 3: Validate connection
        if ib.isConnected():
            accounts = ib.managedAccounts()
            print(f"✅ Phase 3: Connected to accounts: {accounts}")

            # Test server time
            server_time = await ib.reqCurrentTimeAsync()
            print(f"✅ Server time: {server_time}")

            print("\n🎉 MAESTRO CONNECTION TEST SUCCESS!")
            print("✅ All research-backed solutions working")

        else:
            print("❌ Connection validation failed")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print(f"Error type: {type(e).__name__}")

    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected cleanly")

if __name__ == "__main__":
    asyncio.run(maestro_connection_test())
