#!/usr/bin/env python3
"""
Quick verification script for Client 10 integration in SpyderB08
"""

def verify_client_10_integration():
    """Verify that Client 10 is properly integrated."""
    try:
        # Try to import the updated SpyderB08
        from SpyderB08_MultiClientDataManager import MultiClientDataManager, ClientPurpose
        
        print("🔍 VERIFYING CLIENT 10 INTEGRATION")
        print("=" * 50)
        
        # Check if INTERNATIONAL is in ClientPurpose
        if hasattr(ClientPurpose, 'INTERNATIONAL'):
            print("✅ ClientPurpose.INTERNATIONAL exists")
        else:
            print("❌ ClientPurpose.INTERNATIONAL missing")
        
        # Create manager instance
        manager = MultiClientDataManager()
        
        # Check if Client 10 exists
        if 10 in manager.clients:
            client_10 = manager.clients[10]
            print(f"✅ Client 10 exists: {client_10.purpose}")
            print(f"📊 Client 10 symbols: {len(client_10.symbols)} symbols")
            print(f"🔄 Update frequency: {client_10.update_frequency}s")
            
            # Show some symbols
            symbols = client_10.symbols[:5]
            print(f"📈 Sample symbols: {', '.join(symbols)}...")
            
        else:
            print("❌ Client 10 not found in manager.clients")
        
        # Check client range
        client_count = len(manager.clients)
        print(f"📊 Total clients configured: {client_count}")
        
        if client_count == 10:
            print("✅ All 10 clients (1-10) configured correctly")
        else:
            print(f"⚠️  Expected 10 clients, found {client_count}")
        
        print("\n🎉 CLIENT 10 INTEGRATION VERIFICATION COMPLETE")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Verification error: {e}")

if __name__ == "__main__":
    verify_client_10_integration()
