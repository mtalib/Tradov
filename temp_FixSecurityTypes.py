#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_FixSecurityTypes.py
Purpose: Quick fix for SecurityType enum attribute names in MarketDataManager
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:45:00  

Module Description:
    Temporary fix to update the TRADING_SYMBOLS configuration in MarketDataManager
    to use the correct SecurityType enum attributes from SpyderB10_IBDataTypes.

"""

import sys
import os

def fix_security_types():
    """Fix SecurityType attributes in MarketDataManager."""
    
    print("🔧 FIXING SECURITY TYPE ATTRIBUTES")
    print("=" * 50)
    
    # Path to the MarketDataManager file
    manager_file = "SpyderB_Broker/SpyderB07_MarketDataManager.py"
    
    if not os.path.exists(manager_file):
        print(f"❌ File not found: {manager_file}")
        return False
    
    try:
        # Read the file
        with open(manager_file, 'r') as f:
            content = f.read()
        
        print(f"📄 Reading {manager_file}")
        
        # Apply fixes
        replacements = [
            ("SecurityType.STOCK", "SecurityType.STOCK"),  # Already correct
            ("SecurityType.FUT", "SecurityType.FUTURE"),   # Fix FUT -> FUTURE
            ("SecurityType.IND", "SecurityType.INDEX"),    # Fix IND -> INDEX
        ]
        
        original_content = content
        
        for old, new in replacements:
            if old in content:
                content = content.replace(old, new)
                print(f"   ✅ Fixed: {old} → {new}")
        
        # Also fix the string references in TRADING_SYMBOLS
        string_fixes = [
            ("'type': SecurityType.FUT", "'type': SecurityType.FUTURE"),
            ("'type': SecurityType.IND", "'type': SecurityType.INDEX"),
        ]
        
        for old, new in string_fixes:
            if old in content:
                content = content.replace(old, new)
                print(f"   ✅ Fixed: {old} → {new}")
        
        # Write the fixed content back
        if content != original_content:
            with open(manager_file, 'w') as f:
                f.write(content)
            print(f"   💾 Updated {manager_file}")
            print("   ✅ SecurityType fixes applied!")
        else:
            print("   ℹ️ No changes needed")
            
        return True
        
    except Exception as e:
        print(f"❌ Error fixing file: {e}")
        return False

def verify_import():
    """Verify that imports work after the fix."""
    print("\n🧪 VERIFYING IMPORTS")
    print("-" * 30)
    
    try:
        # Test import of SecurityType
        from SpyderB_Broker.SpyderB10_IBDataTypes import SecurityType
        print("   ✅ SecurityType imported successfully")
        
        # Check available attributes
        attrs = [attr for attr in dir(SecurityType) if not attr.startswith('_')]
        print(f"   📋 Available attributes: {attrs}")
        
        # Test specific attributes
        test_attrs = ['STOCK', 'FUTURE', 'INDEX', 'OPTION']
        for attr in test_attrs:
            if hasattr(SecurityType, attr):
                value = getattr(SecurityType, attr).value
                print(f"   ✅ SecurityType.{attr} = '{value}'")
            else:
                print(f"   ❌ SecurityType.{attr} not found")
        
        # Try importing MarketDataManager
        print("\n   🧪 Testing MarketDataManager import...")
        try:
            from SpyderB_Broker.SpyderB07_MarketDataManager import MarketDataManager
            print("   ✅ MarketDataManager imported successfully!")
            return True
        except Exception as e:
            print(f"   ❌ MarketDataManager import failed: {e}")
            return False
            
    except Exception as e:
        print(f"   ❌ SecurityType import failed: {e}")
        return False

def main():
    """Run the security type fix."""
    print("🚀 SPYDER SECURITY TYPE FIX")
    print("=" * 40)
    
    # Apply the fix
    if fix_security_types():
        # Verify it worked
        if verify_import():
            print("\n🎉 SUCCESS!")
            print("✅ SecurityType fix completed")
            print("✅ MarketDataManager imports working")
            print("\n📋 Now you can run:")
            print("   python temp_TestIntegratedSolution.py")
            return True
        else:
            print("\n❌ Import verification failed")
            return False
    else:
        print("\n❌ Fix application failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)