#!/usr/bin/env python3
import asyncio
from ib_async import IB

async def test_client_id_2():
    print("Testing direct connection with Client ID 2...")
    
    ib = IB()
    
    try:
        await ib.connectAsync('127.0.0.1', 4002, clientId=2, timeout=15)
        
        if ib.isConnected():
            print("SUCCESS! Client ID 2 connected")
            
            # Test basic functionality
            if hasattr(ib, 'managedAccounts'):
                accounts = ib.managedAccounts()
                print(f"Managed accounts: {accounts}")
            
            return True
        else:
            print("Connection failed")
            return False
            
    except Exception as e:
        print(f"Connection error with Client ID 2: {e}")
        return False
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("Disconnected")

if __name__ == "__main__":
    success = asyncio.run(test_client_id_2())
    print(f"Client ID 2 available: {success}")
