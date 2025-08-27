#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMPLE IB GATEWAY CONNECTION TEST

SPYDER - Autonomous Options Trading System v1.0

Module: temp_simple_connection_test.py  
Purpose: Simple connection test to verify IB Gateway API access
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 16:00:00

"""

import asyncio
import sys

try:
    from ib_async import IB
except ImportError:
    print("❌ ib_async not available. Install with: pip install ib_async")
    sys.exit(1)

async def test_connection():
    """Test connection to IB Gateway."""
    print("🧪 Testing IB Gateway API Connection...")
    print("-" * 50)
    
    ib = IB()
    
    # Test different client IDs
    for client_id in [1, 2, 3, 4, 5]:
        print(f"🔗 Testing client ID {client_id}...", end=" ")
        
        try:
            await ib.connectAsync('127.0.0.1', 4002, clientId=client_id, timeout=15)
            
            if ib.isConnected():
                print("✅ SUCCESS!")
                print(f"📊 Server version: {ib.serverVersion()}")
                print(f"🕒 Connection time: {ib.reqCurrentTime()}")
                ib.disconnect()
                print(f"🎉 WORKING CLIENT ID: {client_id}")
                return client_id
            else:
                print("❌ Failed (no connection)")
                
        except asyncio.TimeoutError:
            print("❌ Timeout (API not enabled)")
        except Exception as e:
            if "already in use" in str(e):
                print("❌ Client ID in use")
            else:
                print(f"❌ Error: {e}")
        
        finally:
            if ib.isConnected():
                ib.disconnect()
    
    print("\n😞 No working client IDs found")
    print("💡 Gateway API is not enabled - follow configuration steps")
    return None

if __name__ == "__main__":
    result = asyncio.run(test_connection())
    sys.exit(0 if result else 1)
