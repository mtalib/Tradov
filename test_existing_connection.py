#!/usr/bin/env python3
import asyncio
from SpyderB_Broker.SpyderB05_ConnectionManager import get_connection_manager

async def test_connection():
    print("Testing existing SpyderB05_ConnectionManager...")
    
    manager = get_connection_manager()
    
    print("Starting manager...")
    manager.start()
    
    print("Attempting connection...")
    success = manager.connect()
    
    if success:
        print("Connection successful!")
        status = manager.get_status()
        print(f"Status: {status}")
    else:
        print("Connection failed")
    
    manager.stop()

if __name__ == "__main__":
    asyncio.run(test_connection())
