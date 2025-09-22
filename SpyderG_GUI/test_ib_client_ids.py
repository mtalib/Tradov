#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test IB Gateway with Different Client IDs
Tests various client IDs to find one that works
"""

import time
from datetime import datetime

def test_client_id(client_id):
    """Test connection with a specific client ID"""
    try:
        from ib_async import IB
        
        print(f"Testing Client ID {client_id}...")
        
        ib = IB()
        ib.connect('127.0.0.1', 4002, clientId=client_id, timeout=10)
        
        print(f"✅ Client ID {client_id}: CONNECTED")
        
        # Test basic functionality
        account_summary = ib.accountSummary()
        print(f"   Account summary: {len(account_summary)} items")
        
        # Test market data request
        contract = ib.reqContractDetails(ib.stock('SPY'))[0].contract
        ticker = ib.reqMktData(contract)
        ib.sleep(2)  # Wait for data
        
        if ticker.last:
            print(f"   SPY Last Price: {ticker.last}")
        else:
            print("   No market data (expected when market closed)")
        
        ib.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Client ID {client_id}: FAILED - {e}")
        return False

def main():
    print("=" * 60)
    print("🔍 IB CLIENT ID CONNECTION TEST")
    print("=" * 60)
    
    # Test common client IDs
    client_ids_to_test = [0, 1, 2, 3, 10, 100, 999]
    
    successful_ids = []
    
    for client_id in client_ids_to_test:
        if test_client_id(client_id):
            successful_ids.append(client_id)
        time.sleep(1)  # Brief pause between tests
        print()
    
    print("=" * 60)
    if successful_ids:
        print(f"✅ SUCCESS: Client IDs that work: {successful_ids}")
        print(f"🎯 Recommended: Use Client ID {successful_ids[0]} in your dashboard")
    else:
        print("❌ FAILED: No client IDs worked")
        print("\n🔧 Troubleshooting:")
        print("   1. Restart IB Gateway")
        print("   2. Check API settings in IB Gateway")
        print("   3. Ensure 'Enable ActiveX and Socket Clients' is checked")
        print("   4. Add 127.0.0.1 to trusted IP addresses")
        print("   5. Try logging out and back into IB Gateway")

if __name__ == "__main__":
    main()
