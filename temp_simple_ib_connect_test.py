#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIMPLE IB CONNECT ASYNC TEST

SPYDER - Autonomous Options Trading System v1.0

Module: temp_simple_ib_connect_test.py
Purpose: Direct ib.connectAsync test as suggested by user
Author: Mohamed Talib
Date Created: 2025-08-27
Last Updated: 2025-08-27 Time: 17:00:00

"""

import asyncio
from ib_async import IB

async def test_port(port, description):
    """Test connection to specific port."""
    print(f"\n🧪 Testing {description} (Port {port})")
    print("-" * 50)
    
    ib = IB()
    
    for client_id in [1, 2, 3, 4, 5]:
        try:
            print(f"🔗 Client ID {client_id}: ", end="")
            
            await ib.connectAsync('127.0.0.1', port, clientId=client_id, timeout=10)
            
            if ib.isConnected():
                print("✅ SUCCESS!")
                print(f"📊 Server version: {ib.serverVersion()}")
                print(f"🕒 Connection time: {ib.reqCurrentTime()}")
                
                # Test basic API call
                try:
                    accounts = ib.managedAccounts()
                    print(f"👤 Managed accounts: {accounts}")
                except Exception as e:
                    print(f"⚠️ Account info error: {e}")
                
                ib.disconnect()
                return client_id
            else:
                print("❌ Failed - not connected")
                
        except Exception as e:
            error_str = str(e)
            if "already in use" in error_str:
                print("❌ Client ID in use")
            elif "timeout" in error_str.lower() or "TimeoutError" in error_str:
                print("❌ Timeout")
            else:
                print(f"❌ Error: {e}")
        
        finally:
            if ib.isConnected():
                ib.disconnect()
    
    print(f"😞 No working client IDs found for port {port}")
    return None

async def comprehensive_port_test():
    """Test both common IB ports."""
    print("🕷️ SPYDER Simple IB Connect Test")
    print("🔧 Testing direct ib.connectAsync as suggested")
    print("=" * 60)
    
    # Test paper trading port (4002)
    paper_result = await test_port(4002, "Paper Trading")
    
    # Test live trading port (4001) 
    live_result = await test_port(4001, "Live Trading")
    
    print("\n" + "=" * 60)
    print("📊 RESULTS SUMMARY")
    print("=" * 60)
    
    if paper_result:
        print(f"✅ PAPER TRADING (4002): Client ID {paper_result} works!")
        print("🎯 Use this for Spyder paper trading")
        return 4002, paper_result
        
    elif live_result:
        print(f"✅ LIVE TRADING (4001): Client ID {live_result} works!")
        print("⚠️ WARNING: This is LIVE trading - real money!")
        print("🎯 Use this for Spyder live trading")
        return 4001, live_result
        
    else:
        print("❌ Both ports failed")
        print("\n💡 Troubleshooting suggestions:")
        print("1. Gateway may still be initializing (just logged in)")
        print("2. Wait 2-3 minutes after login")
        print("3. Check Gateway shows 'Connected' status")
        print("4. Verify API settings are applied")
        return None, None

async def quick_single_test(port=4001, client_id=1):
    """Quick single test as user suggested."""
    print(f"⚡ Quick Test: Port {port}, Client ID {client_id}")
    print("-" * 40)
    
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', port, clientId=client_id, timeout=10)
        print("✅ Connected successfully")
        print(f"📊 Server version: {ib.serverVersion()}")
        print(f"🕒 Connection time: {ib.reqCurrentTime()}")
        
        # Test managed accounts
        accounts = ib.managedAccounts()
        print(f"👤 Managed accounts: {accounts}")
        
        return True
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
        
    finally:
        if ib.isConnected():
            ib.disconnect()
            print("🔌 Disconnected")

def generate_working_code(port, client_id):
    """Generate working connection code for Spyder."""
    return f"""
# WORKING IB GATEWAY CONNECTION FOR SPYDER
# Generated: {asyncio.get_event_loop().time()}

import asyncio
from ib_async import IB

async def spyder_connect():
    \"\"\"Connect to IB Gateway for Spyder trading system.\"\"\"
    ib = IB()
    
    try:
        # Use working port and client ID
        await ib.connectAsync('127.0.0.1', {port}, clientId={client_id}, timeout=30)
        
        if ib.isConnected():
            print("✅ Spyder connected to IB Gateway")
            print(f"📊 Server: {{ib.serverVersion()}}")
            print(f"👤 Accounts: {{ib.managedAccounts()}}")
            return ib
        else:
            print("❌ Connection failed")
            return None
            
    except Exception as e:
        print(f"❌ Spyder connection error: {{e}}")
        return None

# Usage
if __name__ == "__main__":
    ib = asyncio.run(spyder_connect())
    
    if ib:
        # Your Spyder trading logic here
        print("🕷️ Ready for Spyder autonomous trading!")
        
        # Always disconnect when done
        ib.disconnect()
"""

async def main():
    """Main test function."""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--quick":
            # Quick test port 4001 as user suggested
            port = 4001 if len(sys.argv) < 3 else int(sys.argv[2])
            client_id = 1 if len(sys.argv) < 4 else int(sys.argv[3])
            success = await quick_single_test(port, client_id)
            
            if success:
                print(f"\n🎉 SUCCESS! Use port {port}, client ID {client_id}")
                print(generate_working_code(port, client_id))
                
        elif sys.argv[1] == "--port":
            port = int(sys.argv[2])
            result = await test_port(port, f"Custom Port {port}")
            if result:
                print(generate_working_code(port, result))
    else:
        # Comprehensive test
        port, client_id = await comprehensive_port_test()
        
        if port and client_id:
            print(f"\n🎉 CONNECTION WORKING!")
            print(generate_working_code(port, client_id))
            print(f"\n🚀 Next: Start building Spyder modules!")

if __name__ == "__main__":
    asyncio.run(main())
