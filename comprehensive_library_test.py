#!/usr/bin/env python3
"""
Comprehensive Gateway 10.39 Connection Test
Tests all three available libraries: ib_async, ib-insync, and ibapi
"""

import asyncio
import sys
import time
from datetime import datetime
from typing import Optional, Tuple

# Configuration
HOST = '127.0.0.1'
PORT = 4002
CLIENT_ID = 1
TIMEOUT = 60
RACE_CONDITION_DELAY = 1.0

# Test Results
results = {
    'ib_async': None,
    'ib-insync': None,
    'ibapi': None
}

# ============================================================================
# TEST 1: ib_async
# ============================================================================

async def test_ib_async() -> Tuple[bool, str, float]:
    """Test connection using ib_async library"""
    try:
        from ib_async import IB
    except ImportError:
        return False, "Library not installed", 0.0
    
    print("\n" + "=" * 70)
    print("TEST 1: ib_async (v2.0.1)")
    print("=" * 70)
    
    ib = IB()
    
    try:
        print("📡 Connecting with ib_async...")
        start = time.time()
        
        # Connect
        await asyncio.wait_for(
            ib.connectAsync(HOST, PORT, CLIENT_ID, timeout=TIMEOUT),
            timeout=TIMEOUT
        )
        
        print(f"✅ Socket connected in {time.time() - start:.3f}s")
        
        # Race condition fix
        print(f"⏱️  Applying {RACE_CONDITION_DELAY}s race condition delay...")
        await asyncio.sleep(RACE_CONDITION_DELAY)
        
        # Validate
        accounts = ib.managedAccounts()
        elapsed = time.time() - start
        
        if accounts:
            print(f"✅ SUCCESS! Accounts: {accounts}")
            print(f"✅ Total time: {elapsed:.3f}s")
            ib.disconnect()
            return True, f"Connected successfully - Accounts: {accounts}", elapsed
        else:
            print("❌ No accounts returned")
            ib.disconnect()
            return False, "Connected but no accounts", elapsed
            
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"❌ Timeout after {elapsed:.3f}s")
        if ib.isConnected():
            ib.disconnect()
        return False, "Connection timeout", elapsed
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ Error: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False, str(e), elapsed

# ============================================================================
# TEST 2: ib-insync
# ============================================================================

async def test_ib_insync() -> Tuple[bool, str, float]:
    """Test connection using ib-insync library"""
    try:
        from ib_insync import IB
    except ImportError:
        return False, "Library not installed", 0.0
    
    print("\n" + "=" * 70)
    print("TEST 2: ib-insync (v0.9.86)")
    print("=" * 70)
    
    ib = IB()
    
    try:
        print("📡 Connecting with ib-insync...")
        start = time.time()
        
        # Connect
        await asyncio.wait_for(
            ib.connectAsync(HOST, PORT, CLIENT_ID + 1, timeout=TIMEOUT),
            timeout=TIMEOUT
        )
        
        print(f"✅ Socket connected in {time.time() - start:.3f}s")
        
        # Race condition fix
        print(f"⏱️  Applying {RACE_CONDITION_DELAY}s race condition delay...")
        await asyncio.sleep(RACE_CONDITION_DELAY)
        
        # Validate
        accounts = ib.managedAccounts()
        elapsed = time.time() - start
        
        if accounts:
            print(f"✅ SUCCESS! Accounts: {accounts}")
            print(f"✅ Total time: {elapsed:.3f}s")
            ib.disconnect()
            return True, f"Connected successfully - Accounts: {accounts}", elapsed
        else:
            print("❌ No accounts returned")
            ib.disconnect()
            return False, "Connected but no accounts", elapsed
            
    except asyncio.TimeoutError:
        elapsed = time.time() - start
        print(f"❌ Timeout after {elapsed:.3f}s")
        if ib.isConnected():
            ib.disconnect()
        return False, "Connection timeout", elapsed
        
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ Error: {e}")
        if ib.isConnected():
            ib.disconnect()
        return False, str(e), elapsed

# ============================================================================
# TEST 3: ibapi (Raw IBKR API)
# ============================================================================

def test_ibapi_sync() -> Tuple[bool, str, float]:
    """Test connection using raw ibapi library"""
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        import threading
    except ImportError:
        return False, "Library not installed", 0.0
    
    print("\n" + "=" * 70)
    print("TEST 3: ibapi (Official IBKR - v9.81.1)")
    print("=" * 70)
    
    class TestWrapper(EWrapper):
        def __init__(self):
            super().__init__()
            self.accounts = []
            self.connected = False
            self.error_occurred = False
            self.error_msg = ""
            
        def managedAccounts(self, accountsList: str):
            self.accounts = accountsList.split(',')
            
        def connectAck(self):
            self.connected = True
            
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
            if errorCode not in [2104, 2106, 2158]:  # Ignore info messages
                print(f"⚠️  Error {errorCode}: {errorString}")
                self.error_msg = f"{errorCode}: {errorString}"
                if errorCode in [502, 504]:
                    self.error_occurred = True
    
    class TestClient(EClient):
        def __init__(self, wrapper):
            super().__init__(wrapper)
    
    wrapper = TestWrapper()
    client = TestClient(wrapper)
    
    try:
        print("📡 Connecting with raw ibapi...")
        start = time.time()
        
        # Connect
        client.connect(HOST, PORT, CLIENT_ID + 2)
        
        # Start message processing thread
        api_thread = threading.Thread(target=client.run, daemon=True)
        api_thread.start()
        
        print(f"✅ Socket connected in {time.time() - start:.3f}s")
        
        # Race condition fix
        print(f"⏱️  Applying {RACE_CONDITION_DELAY}s race condition delay...")
        time.sleep(RACE_CONDITION_DELAY)
        
        # Wait for connection to fully establish
        max_wait = 10
        waited = 0
        while not wrapper.connected and not wrapper.error_occurred and waited < max_wait:
            time.sleep(0.1)
            waited += 0.1
        
        elapsed = time.time() - start
        
        if wrapper.connected and wrapper.accounts:
            print(f"✅ SUCCESS! Accounts: {wrapper.accounts}")
            print(f"✅ Total time: {elapsed:.3f}s")
            client.disconnect()
            return True, f"Connected successfully - Accounts: {wrapper.accounts}", elapsed
        elif wrapper.error_occurred:
            print(f"❌ Error: {wrapper.error_msg}")
            client.disconnect()
            return False, wrapper.error_msg, elapsed
        else:
            print("❌ Connection timeout or no accounts")
            client.disconnect()
            return False, "Timeout or no accounts", elapsed
            
    except Exception as e:
        elapsed = time.time() - start
        print(f"❌ Error: {e}")
        try:
            client.disconnect()
        except:
            pass
        return False, str(e), elapsed

# ============================================================================
# COMPREHENSIVE TEST WITH VARIABLE DELAYS
# ============================================================================

async def test_with_delays(library: str, test_func, delays: list) -> Optional[float]:
    """Test a library with different race condition delays"""
    print(f"\n🔬 Testing {library} with different delays...")
    
    for delay in delays:
        global RACE_CONDITION_DELAY
        RACE_CONDITION_DELAY = delay
        
        print(f"\n  Trying {delay}s delay...")
        
        if library == 'ibapi':
            success, msg, elapsed = test_func()
        else:
            success, msg, elapsed = await test_func()
        
        if success:
            print(f"  ✅ {library} works with {delay}s delay!")
            return delay
        
        await asyncio.sleep(1)  # Wait before next attempt
    
    return None

# ============================================================================
# MAIN TEST SUITE
# ============================================================================

async def run_comprehensive_tests():
    """Run all tests and generate report"""
    
    print("=" * 70)
    print("🔬 GATEWAY 10.39 COMPREHENSIVE CONNECTION TEST")
    print("=" * 70)
    print(f"Timestamp: {datetime.now()}")
    print(f"Target: {HOST}:{PORT}")
    print(f"Python: {sys.version.split()[0]}")
    print()
    print("Testing all three libraries with race condition fix...")
    print("=" * 70)
    
    # Test 1: ib_async
    success, msg, elapsed = await test_ib_async()
    results['ib_async'] = {'success': success, 'message': msg, 'time': elapsed}
    
    await asyncio.sleep(2)  # Wait between tests
    
    # Test 2: ib-insync
    success, msg, elapsed = await test_ib_insync()
    results['ib-insync'] = {'success': success, 'message': msg, 'time': elapsed}
    
    await asyncio.sleep(2)  # Wait between tests
    
    # Test 3: ibapi (synchronous)
    success, msg, elapsed = test_ibapi_sync()
    results['ibapi'] = {'success': success, 'message': msg, 'time': elapsed}
    
    # Check if any succeeded
    successful_libs = [lib for lib, result in results.items() if result and result['success']]
    
    if successful_libs:
        print("\n" + "=" * 70)
        print("🎉 SUCCESS WITH STANDARD 1s DELAY!")
        print("=" * 70)
        
        for lib in successful_libs:
            result = results[lib]
            print(f"\n✅ {lib}")
            print(f"   Time: {result['time']:.3f}s")
            print(f"   Message: {result['message']}")
        
        # Recommend best option
        fastest = min(successful_libs, key=lambda x: results[x]['time'])
        print(f"\n🏆 RECOMMENDED: {fastest} (fastest at {results[fastest]['time']:.3f}s)")
        
        return True
    
    # No success with 1s delay, try different delays
    print("\n" + "=" * 70)
    print("⚠️  Standard 1s delay didn't work for any library")
    print("🔧 Testing with different delays...")
    print("=" * 70)
    
    delays_to_test = [0.5, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    
    # Try ib_async with different delays
    optimal_delay = await test_with_delays('ib_async', test_ib_async, delays_to_test)
    if optimal_delay:
        print(f"\n✅ ib_async works with {optimal_delay}s delay!")
        return True
    
    # Try ib-insync with different delays
    optimal_delay = await test_with_delays('ib-insync', test_ib_insync, delays_to_test)
    if optimal_delay:
        print(f"\n✅ ib-insync works with {optimal_delay}s delay!")
        return True
    
    # All failed
    print("\n" + "=" * 70)
    print("❌ ALL LIBRARIES FAILED WITH ALL DELAYS")
    print("=" * 70)
    print()
    print("This indicates a deeper issue than just the race condition.")
    print()
    print("🔍 Troubleshooting steps:")
    print()
    print("1. Check Gateway logs:")
    print("   tail -f ~/Jts/ibgateway/1039/logs/*.log")
    print()
    print("2. Verify Gateway is fully started and logged in")
    print()
    print("3. Check Gateway API configuration:")
    print("   - File → Global Configuration → API → Settings")
    print("   - Verify no popup dialogs are blocking")
    print()
    print("4. Try restarting Gateway completely")
    print()
    print("5. Check for Gateway error messages in GUI")
    print()
    print("6. Library version issues:")
    print("   pip install --upgrade ib_async ib-insync ibapi")
    print()
    
    return False

# ============================================================================
# GENERATE FINAL REPORT
# ============================================================================

def generate_report():
    """Generate final test report"""
    print("\n" + "=" * 70)
    print("📊 FINAL TEST REPORT")
    print("=" * 70)
    
    for lib, result in results.items():
        if result:
            status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
            print(f"\n{lib}: {status}")
            print(f"  Time: {result['time']:.3f}s")
            print(f"  Message: {result['message']}")
    
    print("\n" + "=" * 70)

# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution"""
    try:
        success = asyncio.run(run_comprehensive_tests())
        generate_report()
        return success
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
