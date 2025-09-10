#!/usr/bin/env python3
"""
Working IB Gateway Connection for ib_async 2.0.1
================================================

Based on the test results showing partial success, this implements
the correct connection approach for your system.
"""

import asyncio
import time
from typing import Optional
from ib_async import IB, Stock

# Configuration
MASTER_CLIENT_ID = 2
PAPER_PORT = 4002

async def reliable_connect(
    client_id: int = 0,
    max_retries: int = 5,
    retry_delay: float = 2.0
) -> Optional[IB]:
    """
    Reliable connection method that works with ib_async 2.0.1
    
    The key is that the API DOES work (we saw it connect and get account DU5361048)
    but it needs proper timing and retry logic.
    """
    
    print(f"\n🔌 Connecting Client {client_id}...")
    
    for attempt in range(max_retries):
        ib = IB()
        
        try:
            print(f"   Attempt {attempt + 1}/{max_retries}...")
            
            # Connect with a good timeout
            await ib.connectAsync(
                '127.0.0.1',
                PAPER_PORT,
                clientId=client_id,
                timeout=20  # Generous timeout
            )
            
            print("   ✓ Socket connected")
            
            # CRITICAL: Give the API time to fully initialize
            # This replaces waitOnUpdateAsync which doesn't exist
            await asyncio.sleep(1.0)  # Full second for stability
            
            # Validate connection by requesting data
            print("   Validating connection...")
            
            # Test 1: Get server version (basic test)
            try:
                server_version = ib.client.serverVersion()
                print(f"   ✓ Server version: {server_version}")
            except:
                pass  # Some versions don't have this attribute
            
            # Test 2: Get managed accounts (critical test)
            accounts = ib.managedAccounts()
            if accounts:
                print(f"   ✓ Accounts retrieved: {accounts}")
                
                # SUCCESS! Connection is working
                print(f"\n✅ CLIENT {client_id} CONNECTED SUCCESSFULLY!")
                return ib
            else:
                print("   ⚠️  No accounts returned, retrying...")
                ib.disconnect()
                
        except asyncio.TimeoutError:
            print(f"   ⏱️  Timeout on attempt {attempt + 1}")
            if ib.isConnected():
                ib.disconnect()
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:50]}")
            if ib.isConnected():
                ib.disconnect()
        
        # Wait before retry
        if attempt < max_retries - 1:
            print(f"   Waiting {retry_delay} seconds before retry...")
            await asyncio.sleep(retry_delay)
    
    print(f"   ❌ Failed after {max_retries} attempts")
    return None

async def test_all_clients():
    """Test all clients in your architecture"""
    
    print("=" * 60)
    print("TESTING SPYDER MULTI-CLIENT ARCHITECTURE")
    print("=" * 60)
    print("\nYour test showed the API IS working (got account DU5361048)")
    print("Now testing with proper connection method...")
    
    clients = [
        (2, "Master Administrative"),
        (1, "Order Execution"),
        (3, "Core Market Data"),
        (4, "Options Chain"),
        (5, "Volatility Data"),
        (0, "Test Client (Any)")  # Client 0 accepts any ID
    ]
    
    connections = []
    
    for client_id, description in clients:
        print(f"\n{'='*60}")
        print(f"Testing {description} (Client {client_id})")
        print('='*60)
        
        ib = await reliable_connect(client_id=client_id, max_retries=3)
        
        if ib:
            connections.append((client_id, description, ib))
            
            # Test basic functionality
            try:
                if client_id == 2:  # Master
                    summary = ib.accountSummary()
                    if summary:
                        print(f"   Master client has account access")
                        
                # Test market data
                spy = Stock('SPY', 'SMART', 'USD')
                qualified = await ib.qualifyContractsAsync(spy)
                if qualified:
                    print(f"   Can qualify contracts: {qualified[0].symbol}")
                    
            except Exception as e:
                print(f"   Function test error: {e}")
            
            # Keep first successful connection, disconnect others
            if len(connections) > 1:
                ib.disconnect()
                print(f"   Disconnected (keeping first connection alive)")
        
        await asyncio.sleep(2)  # Wait between clients
    
    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    if connections:
        print(f"\n✅ SUCCESS! {len(connections)} clients connected:")
        for client_id, desc, ib in connections:
            status = "Connected" if ib.isConnected() else "Disconnected"
            print(f"   Client {client_id}: {desc} - {status}")
        
        # Cleanup
        print("\n🧹 Cleaning up...")
        for _, _, ib in connections:
            if ib.isConnected():
                ib.disconnect()
                
        print("\n🎉 YOUR IB GATEWAY API IS WORKING!")
        print("\nThe issue was timing/retry logic, not a broken API.")
        print("Use the reliable_connect() function in your production code.")
        
    else:
        print("\n❌ No clients connected successfully")
        print("\nBut we KNOW it can work (previous test got account DU5361048)")
        print("Try:")
        print("1. Restart Gateway")
        print("2. Wait 30 seconds after login")
        print("3. Run this test again")

async def simple_test():
    """Ultra-simple connection test"""
    print("\n" + "=" * 60)
    print("SIMPLE CONNECTION TEST")
    print("=" * 60)
    
    ib = IB()
    
    print("\nAttempting basic connection...")
    
    try:
        # Just try to connect with generous timeout
        await ib.connectAsync('127.0.0.1', 4002, clientId=0, timeout=30)
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Check if we got data
        accounts = ib.managedAccounts()
        
        if accounts:
            print(f"✅ SUCCESS! Connected to account: {accounts}")
            print("\nYOUR API IS WORKING!")
            ib.disconnect()
            return True
        else:
            print("❌ Connected but no account data")
            ib.disconnect()
            return False
            
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

# Main execution
async def main():
    print("🔧 IB GATEWAY CONNECTION TEST (CORRECTED)")
    print("=" * 60)
    print("\nYour previous test proved the API works sometimes.")
    print("It connected and retrieved account DU5361048!")
    print("This test uses proper timing to make it reliable.\n")
    
    # Start with simple test
    if await simple_test():
        print("\nSimple test worked! Now testing multi-client...")
        await asyncio.sleep(3)
        await test_all_clients()
    else:
        print("\nSimple test failed. Trying with retries...")
        await test_all_clients()

if __name__ == "__main__":
    asyncio.run(main())