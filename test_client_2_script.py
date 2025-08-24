#!/usr/bin/env python3
"""
Test Script: Verify Client ID 2 Works for Dashboard

Run this AFTER making the CLIENT_ID = 2 change in SpyderG05_TradingDashboard.py
"""

def test_client_id_2_connection():
    """Test if Client ID 2 can connect to IB Gateway"""
    import socket
    import time
    
    print("🔧 TESTING CLIENT ID 2 FOR SPYDER DASHBOARD")
    print("=" * 60)
    
    # Step 1: Check if IB Gateway is running
    print("1. 🌐 Checking IB Gateway availability...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("127.0.0.1", 4002))
        sock.close()
        
        if result != 0:
            print("   ❌ IB Gateway NOT available on port 4002")
            print("   💡 Please start IB Gateway first")
            print("   💡 Make sure it's configured for Paper Trading (port 4002)")
            return False
        else:
            print("   ✅ IB Gateway is running on port 4002")
            
    except Exception as e:
        print(f"   ❌ Gateway check failed: {e}")
        return False
    
    # Step 2: Test Client ID 2 connection
    print("\n2. 🔗 Testing Client ID 2 connection...")
    try:
        from ib_async import IB
        print("   ✅ ib_async library available")
        
        # Connect with Client ID 2
        ib = IB()
        print("   🔄 Connecting with Client ID 2...")
        
        ib.connect("127.0.0.1", 4002, clientId=2, timeout=10)
        
        if ib.isConnected():
            print("   ✅ Client ID 2 connected successfully!")
            
            # Test basic functionality
            try:
                server_time = ib.reqCurrentTime()
                print(f"   🕐 Server time: {server_time}")
                print("   ✅ API communication working")
            except Exception as e:
                print(f"   ⚠️ API test failed: {e}")
                
            # Disconnect cleanly
            ib.disconnect()
            print("   🔌 Disconnected cleanly")
            
            return True
        else:
            print("   ❌ Failed to connect with Client ID 2")
            return False
            
    except ImportError:
        print("   ❌ ib_async not installed")
        print("   💡 Install with: pip install ib-async")
        return False
    except Exception as e:
        print(f"   ❌ Connection test failed: {e}")
        print(f"   💡 Error details: {str(e)}")
        return False

def show_integration_status():
    """Show the integration status and next steps"""
    print("\n" + "=" * 60)
    print("🎯 SPYDER DASHBOARD INTEGRATION STATUS")
    print("=" * 60)
    
    # Check if the change was made
    try:
        with open("SpyderG05_TradingDashboard.py", "r") as f:
            content = f.read()
            
        if "CLIENT_ID = 2" in content:
            print("✅ SpyderG05_TradingDashboard.py updated with CLIENT_ID = 2")
            dashboard_updated = True
        elif "CLIENT_ID = 123" in content:
            print("⚠️ SpyderG05_TradingDashboard.py still has CLIENT_ID = 123")
            print("💡 Please update it to CLIENT_ID = 2")
            dashboard_updated = False
        else:
            print("❓ Could not determine CLIENT_ID status")
            dashboard_updated = False
            
    except FileNotFoundError:
        print("❌ SpyderG05_TradingDashboard.py not found in current directory")
        dashboard_updated = False
    except Exception as e:
        print(f"❌ Could not check file: {e}")
        dashboard_updated = False
    
    return dashboard_updated

def main():
    """Main test execution"""
    # Test Client ID 2 connection
    connection_works = test_client_id_2_connection()
    
    # Show integration status  
    dashboard_updated = show_integration_status()
    
    # Final recommendations
    print("\n🚀 NEXT STEPS:")
    print("=" * 30)
    
    if connection_works and dashboard_updated:
        print("✅ Ready to run SpyderG05 Dashboard!")
        print("🎯 Run: python SpyderG05_TradingDashboard.py")
        print("🎯 Dashboard will now connect using Client ID 2 (Administrative)")
        
    elif connection_works and not dashboard_updated:
        print("🔧 Update SpyderG05_TradingDashboard.py first:")
        print("   1. Open: gedit SpyderG05_TradingDashboard.py")  
        print("   2. Find: CLIENT_ID = 123")
        print("   3. Change to: CLIENT_ID = 2")
        print("   4. Save and run dashboard")
        
    elif not connection_works:
        print("🔧 Fix IB Gateway connection first:")
        print("   1. Start IB Gateway")
        print("   2. Ensure API is enabled") 
        print("   3. Check port 4002 is configured")
        print("   4. Run this test again")
        
    else:
        print("🔧 Check both IB Gateway and dashboard configuration")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
