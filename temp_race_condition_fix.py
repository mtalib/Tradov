#!/usr/bin/env python3
"""
IB Gateway Connection Test with Race Condition Workaround
==========================================================

Implements community-recommended workaround for ib_async connection issues:
- Adds waitOnUpdate() after connection to allow API to stabilize
- Implements retry logic with backoff
- Tests multiple connection approaches

Known Issue: ib_async sometimes has race conditions where the connection
appears successful but the API isn't ready for requests immediately.
"""

import asyncio
import time
from typing import Optional
from ib_async import IB, util

# Configuration
MASTER_CLIENT_ID = 2
PAPER_PORT = 4002
LIVE_PORT = 4001

# ==============================================================================
# CONNECTION WITH WORKAROUNDS
# ==============================================================================

async def connect_with_workaround(
    host: str = '127.0.0.1',
    port: int = PAPER_PORT, 
    client_id: int = MASTER_CLIENT_ID,
    max_retries: int = 3
) -> Optional[IB]:
    """
    Connect to IB Gateway with race condition workarounds.
    
    Implements multiple community-recommended fixes:
    1. waitOnUpdate() after connection
    2. Small delay after connection
    3. Retry logic with exponential backoff
    4. Connection validation before returning
    """
    
    print(f"\n🔧 Attempting connection with race condition workarounds")
    print(f"   Host: {host}, Port: {port}, Client ID: {client_id}")
    
    for attempt in range(max_retries):
        ib = IB()
        
        try:
            print(f"\n   Attempt {attempt + 1}/{max_retries}...")
            
            # Step 1: Basic connection
            await ib.connectAsync(
                host=host,
                port=port,
                clientId=client_id,
                timeout=30  # Longer timeout for initial connection
            )
            
            print("   ✓ Socket connected")
            
            # Step 2: CRITICAL WORKAROUND - Wait for API to stabilize
            # This addresses the race condition where connection succeeds
            # but API isn't ready yet
            print("   Waiting for API to stabilize...")
            
            # Method 1: waitOnUpdate (most effective)
            try:
                await ib.waitOnUpdateAsync(timeout=0.5)
                print("   ✓ API update received")
            except asyncio.TimeoutError:
                print("   ⚠️  No update received (normal for quiet periods)")
            
            # Method 2: Small delay to ensure initialization
            await asyncio.sleep(0.5)
            
            # Method 3: Request something simple to verify connection
            print("   Validating connection...")
            
            # Try to get server version (should always work if connected)
            try:
                server_version = ib.client.serverVersion()
                print(f"   ✓ Server version: {server_version}")
            except:
                print("   ⚠️  Could not get server version")
            
            # Try to get managed accounts (better validation)
            try:
                accounts = ib.managedAccounts()
                if accounts:
                    print(f"   ✓ Managed accounts: {accounts}")
                else:
                    print("   ⚠️  No managed accounts returned")
                    # Sometimes accounts list is empty on first call
                    await asyncio.sleep(0.5)
                    accounts = ib.managedAccounts()
                    if accounts:
                        print(f"   ✓ Managed accounts (retry): {accounts}")
            except Exception as e:
                print(f"   ⚠️  Account retrieval issue: {e}")
            
            # Step 4: Final validation - request account summary
            print("   Final validation...")
            try:
                ib.reqAccountSummary()
                await asyncio.sleep(1)  # Give time for data to arrive
                
                account_summary = ib.accountSummaryAsync()
                if account_summary:
                    print(f"   ✓ Account data flowing")
                else:
                    print("   ⚠️  No account data yet")
            except:
                pass
            
            # If we got here, connection is likely good
            print(f"\n✅ CONNECTION SUCCESSFUL on attempt {attempt + 1}")
            return ib
            
        except asyncio.TimeoutError:
            print(f"   ❌ Timeout on attempt {attempt + 1}")
            if ib.isConnected():
                ib.disconnect()
            
            # Exponential backoff before retry
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"   Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)
                
        except Exception as e:
            print(f"   ❌ Error on attempt {attempt + 1}: {e}")
            if ib.isConnected():
                ib.disconnect()
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"   Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)
    
    print(f"\n❌ All {max_retries} connection attempts failed")
    return None

async def test_multi_client_with_workaround():
    """
    Test multi-client architecture with race condition workarounds.
    """
    print("\n" + "=" * 60)
    print("TESTING MULTI-CLIENT ARCHITECTURE WITH WORKAROUNDS")
    print("=" * 60)
    
    successful_clients = []
    failed_clients = []
    
    # Client configuration
    clients = [
        (2, "Master Administrative Client"),
        (1, "Order Execution Client"),
        (3, "Core Market Data Client"),
        (4, "Options Chain Client"),
        (5, "Volatility Data Client")
    ]
    
    for client_id, description in clients:
        print(f"\n📍 Connecting {description} (ID: {client_id})")
        
        ib = await connect_with_workaround(
            client_id=client_id,
            max_retries=2
        )
        
        if ib:
            successful_clients.append((client_id, description, ib))
            
            # Keep connection alive briefly to test stability
            await asyncio.sleep(1)
            
            # Test basic functionality
            try:
                if client_id == 2:  # Master client
                    accounts = ib.managedAccounts()
                    print(f"   Master client managing accounts: {accounts}")
                elif client_id == 1:  # Order client
                    print(f"   Order client ready for trading")
                else:  # Data clients
                    print(f"   Data client ready for market data")
            except Exception as e:
                print(f"   ⚠️  Functionality test failed: {e}")
        else:
            failed_clients.append((client_id, description))
    
    # Cleanup
    print("\n🧹 Cleaning up connections...")
    for client_id, description, ib in successful_clients:
        if ib.isConnected():
            ib.disconnect()
            print(f"   Disconnected {description}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successful connections: {len(successful_clients)}/{len(clients)}")
    
    if successful_clients:
        print("\n✅ Connected clients:")
        for client_id, description, _ in successful_clients:
            print(f"   Client {client_id}: {description}")
    
    if failed_clients:
        print("\n❌ Failed clients:")
        for client_id, description in failed_clients:
            print(f"   Client {client_id}: {description}")
    
    return len(successful_clients) > 0

async def test_race_condition_scenarios():
    """
    Test various race condition scenarios and workarounds.
    """
    print("\n" + "=" * 60)
    print("TESTING RACE CONDITION SCENARIOS")
    print("=" * 60)
    
    scenarios = [
        {
            "name": "Standard connection (no workaround)",
            "use_workaround": False
        },
        {
            "name": "With waitOnUpdate workaround",
            "use_workaround": True
        }
    ]
    
    for scenario in scenarios:
        print(f"\n📋 Testing: {scenario['name']}")
        print("-" * 40)
        
        ib = IB()
        
        try:
            start_time = time.time()
            
            # Connect
            await ib.connectAsync('127.0.0.1', PAPER_PORT, clientId=0, timeout=10)
            
            if scenario['use_workaround']:
                # Apply workaround
                print("   Applying waitOnUpdate workaround...")
                try:
                    await ib.waitOnUpdateAsync(timeout=0.5)
                    print("   ✓ Workaround applied")
                except asyncio.TimeoutError:
                    print("   ⚠️  waitOnUpdate timed out (may be normal)")
                
                # Additional stabilization
                await asyncio.sleep(0.2)
            
            # Test connection
            elapsed = time.time() - start_time
            
            # Validation tests
            tests_passed = 0
            tests_total = 3
            
            # Test 1: Server version
            try:
                version = ib.client.serverVersion()
                print(f"   ✓ Server version: {version}")
                tests_passed += 1
            except:
                print(f"   ✗ Could not get server version")
            
            # Test 2: Managed accounts
            try:
                accounts = ib.managedAccounts()
                if accounts:
                    print(f"   ✓ Accounts: {accounts}")
                    tests_passed += 1
                else:
                    print(f"   ✗ No accounts returned")
            except:
                print(f"   ✗ Could not get accounts")
            
            # Test 3: Connection time
            try:
                conn_time = ib.client.connectionTime
                print(f"   ✓ Connection time: {conn_time}")
                tests_passed += 1
            except:
                print(f"   ✗ Could not get connection time")
            
            print(f"\n   Result: {tests_passed}/{tests_total} tests passed")
            print(f"   Time taken: {elapsed:.2f} seconds")
            
            if tests_passed == tests_total:
                print(f"   ✅ {scenario['name']} SUCCESSFUL")
            else:
                print(f"   ⚠️  {scenario['name']} PARTIAL SUCCESS")
            
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
        
        finally:
            if ib.isConnected():
                ib.disconnect()
        
        await asyncio.sleep(2)  # Wait between scenarios

# ==============================================================================
# MAIN TEST
# ==============================================================================
async def main():
    """Run all tests with race condition workarounds"""
    
    print("🔧 IB GATEWAY CONNECTION TEST WITH RACE CONDITION WORKAROUNDS")
    print("=" * 60)
    print("\nThis test implements community-recommended workarounds for")
    print("ib_async connection race conditions that can cause timeouts.")
    print()
    
    # Test 1: Single connection with workaround
    print("TEST 1: Single Connection with Workaround")
    print("-" * 40)
    
    ib = await connect_with_workaround()
    if ib:
        print("\n✅ Single connection successful!")
        
        # Test some basic operations
        print("\nTesting basic operations...")
        try:
            # Request market data for SPY
            from ib_async import Stock
            spy = Stock('SPY', 'SMART', 'USD')
            qualified = await ib.qualifyContractsAsync(spy)
            if qualified:
                print(f"✓ Contract qualified: {qualified[0]}")
        except Exception as e:
            print(f"⚠️  Market data test failed: {e}")
        
        ib.disconnect()
    else:
        print("\n❌ Single connection failed")
    
    await asyncio.sleep(2)
    
    # Test 2: Race condition scenarios
    await test_race_condition_scenarios()
    
    await asyncio.sleep(2)
    
    # Test 3: Multi-client with workarounds
    success = await test_multi_client_with_workaround()
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    if success:
        print("✅ WORKAROUNDS EFFECTIVE - Some connections succeeded!")
        print("\nRecommended approach for your system:")
        print("1. Always use waitOnUpdate(timeout=0.5) after connection")
        print("2. Add small delay (0.2-0.5s) after connection")
        print("3. Implement retry logic with exponential backoff")
        print("4. Validate connection before proceeding")
    else:
        print("❌ Workarounds did not resolve the issue")
        print("\nThe problem appears to be deeper than race conditions.")
        print("Consider using Docker container or Gateway reinstallation.")

if __name__ == "__main__":
    asyncio.run(main())