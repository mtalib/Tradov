from ib_async import IB
import asyncio

async def test_connection():
    ib = IB()
    try:
        # Using Master Client ID 2
        await ib.connectAsync('127.0.0.1', 4002, clientId=2, timeout=60)
        print(f"Connected! Server version: {ib.serverVersion()}")
        print(f"Connection time: {ib.reqCurrentTime()}")
        ib.disconnect()
        print("Disconnected successfully")
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_connection())
