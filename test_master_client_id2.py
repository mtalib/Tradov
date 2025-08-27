#!/usr/bin/env python3
import asyncio
from SpyderB_Broker.SpyderB05_ConnectionManager import get_connection_manager, ConnectionConfig

async def test_master_connection():
    print("Testing SpyderB05_ConnectionManager with Master Client ID 2...")
    
    # Create configuration with client ID 2 for master coordination
    config = ConnectionConfig()
    config.client_id = 2  # Master client ID for system coordination
    config.host = "127.0.0.1"
    config.port = 4002
    config.timeout = 30.0
    config.readonly = False  # Allow trading operations
    
    print(f"Configuration: {config.host}:{config.port}, Client ID: {config.client_id}")
    
    # Get connection manager with custom config
    manager = get_connection_manager(config)
    
    print("Starting manager...")
    manager.start()
    
    print("Attempting connection with Master Client ID 2...")
    success = manager.connect()
    
    if success:
        print("Connection successful!")
        status = manager.get_status()
        print(f"Status: {status}")
        
        # Test getting IB instance
        ib = manager.get_ib_instance()
        if ib:
            print("IB instance available for system coordination")
        else:
            print("IB instance not available")
    else:
        print("Connection failed")
    
    manager.stop()

if __name__ == "__main__":
    asyncio.run(test_master_connection())
