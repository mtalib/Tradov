#!/usr/bin/env python3
"""
Verification Script: Check if CLIENT_ID = 2 change was applied correctly
"""

def verify_client_id_change():
    """Verify the CLIENT_ID change in SpyderG05_TradingDashboard.py"""
    
    print("🔍 VERIFYING CLIENT_ID CHANGE")
    print("=" * 50)
    
    try:
        # Check if file exists
        filename = "SpyderG05_TradingDashboard.py"
        with open(filename, "r") as f:
            content = f.read()
        
        print(f"✅ Found {filename}")
        
        # Check for CLIENT_ID = 2
        if "CLIENT_ID = 2" in content:
            print("✅ CLIENT_ID = 2 found - CHANGE APPLIED CORRECTLY!")
            client_id_2_found = True
        else:
            print("❌ CLIENT_ID = 2 not found")
            client_id_2_found = False
        
        # Check for old CLIENT_ID = 123 
        if "CLIENT_ID = 123" in content:
            print("⚠️ CLIENT_ID = 123 still present - CHANGE NOT COMPLETE")
            client_id_123_found = True
        else:
            print("✅ CLIENT_ID = 123 removed - Good!")
            client_id_123_found = False
        
        # Show context around CLIENT_ID
        lines = content.split('\n')
        print("\n📝 CLIENT_ID Context:")
        for i, line in enumerate(lines):
            if "CLIENT_ID" in line and "=" in line:
                print(f"   Line {i+1:4d}: {line.strip()}")
        
        # Final assessment
        print("\n" + "=" * 50)
        if client_id_2_found and not client_id_123_found:
            print("✅ VERIFICATION PASSED - Change applied correctly!")
            print("🎯 Dashboard will use CLIENT_ID = 2 (Administrative)")
            return True
        elif client_id_2_found and client_id_123_found:
            print("⚠️ PARTIAL CHANGE - Both CLIENT_ID = 2 and 123 found")
            print("💡 Remove CLIENT_ID = 123 line manually")
            return False  
        elif not client_id_2_found and client_id_123_found:
            print("❌ CHANGE NOT APPLIED - Still using CLIENT_ID = 123")
            print("💡 Please change CLIENT_ID = 123 to CLIENT_ID = 2")
            return False
        else:
            print("❓ UNCERTAIN STATE - Check CLIENT_ID configuration")
            return False
            
    except FileNotFoundError:
        print(f"❌ {filename} not found in current directory")
        print("💡 Make sure you're in the SpyderG_GUI directory")
        return False
    except Exception as e:
        print(f"❌ Error checking file: {e}")
        return False

def show_next_steps(verification_passed):
    """Show next steps based on verification result"""
    
    print("\n🚀 NEXT STEPS:")
    print("=" * 30)
    
    if verification_passed:
        print("✅ Ready to test dashboard connection!")
        print("\n1. Test the connection:")
        print("   python temp_test_client_2.py")
        print("\n2. If connection works, launch dashboard:")
        print("   python SpyderG05_TradingDashboard.py")
        print("\n3. Optional: Use professional launcher:")
        print("   python SpyderR07_LiveDashboard.py")
        
    else:
        print("🔧 Fix CLIENT_ID configuration first:")
        print("\n1. Open Gedit:")
        print("   gedit SpyderG05_TradingDashboard.py")
        print("\n2. Find and replace:")
        print("   CLIENT_ID = 123  →  CLIENT_ID = 2")
        print("\n3. Save and run this verification again")

def main():
    """Main verification"""
    verification_passed = verify_client_id_change()
    show_next_steps(verification_passed)
    
    print("\n" + "=" * 50)
    if verification_passed:
        print("🎯 SPYDER DASHBOARD IS READY!")
    else:
        print("🔧 PLEASE COMPLETE CLIENT_ID CHANGE")
    print("=" * 50)

if __name__ == "__main__":
    main()
