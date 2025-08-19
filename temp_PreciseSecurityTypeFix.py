#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_PreciseSecurityTypeFix.py
Purpose: Precise fix for SecurityType enum attributes without double-replacement
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:50:00  

Module Description:
    More precise fix that avoids the double-replacement issue that was creating
    "FUTUREURE" instead of "FUTURE". Uses exact pattern matching.

"""

import sys
import os
import re

def fix_security_types_precise():
    """Fix SecurityType attributes with precise pattern matching."""
    
    print("🔧 PRECISE SECURITY TYPE FIX")
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
        
        original_content = content
        changes_made = []
        
        # Define precise patterns to avoid double replacement
        patterns = [
            # Pattern for SecurityType.FUT (but not SecurityType.FUTURE)
            (r'SecurityType\.FUT(?!URE)', 'SecurityType.FUTURE'),
            # Pattern for SecurityType.IND (but not SecurityType.INDEX)  
            (r'SecurityType\.IND(?!EX)', 'SecurityType.INDEX'),
            # Pattern in dictionary values
            (r"'type': SecurityType\.FUT(?!URE)", "'type': SecurityType.FUTURE"),
            (r"'type': SecurityType\.IND(?!EX)", "'type': SecurityType.INDEX"),
        ]
        
        for pattern, replacement in patterns:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                changes_made.append(f"{pattern} → {replacement} ({len(matches)} occurrences)")
        
        # Show what was changed
        for change in changes_made:
            print(f"   ✅ Fixed: {change}")
        
        # Write the fixed content back
        if content != original_content:
            with open(manager_file, 'w') as f:
                f.write(content)
            print(f"   💾 Updated {manager_file}")
        else:
            print("   ℹ️ No changes needed")
            
        return True
        
    except Exception as e:
        print(f"❌ Error fixing file: {e}")
        return False

def verify_file_content():
    """Verify the file content is correct."""
    print("\n🔍 VERIFYING FILE CONTENT")
    print("-" * 30)
    
    manager_file = "SpyderB_Broker/SpyderB07_MarketDataManager.py"
    
    try:
        with open(manager_file, 'r') as f:
            content = f.read()
        
        # Check for problematic patterns
        issues = []
        
        if 'FUTUREURE' in content:
            issues.append("Found 'FUTUREURE' (double replacement error)")
        if 'INDEXDEX' in content:
            issues.append("Found 'INDEXDEX' (double replacement error)")
        if 'SecurityType.FUT' in content and 'SecurityType.FUTURE' not in content.replace('SecurityType.FUT', ''):
            issues.append("Found unreplaced 'SecurityType.FUT'")
        if 'SecurityType.IND' in content and 'SecurityType.INDEX' not in content.replace('SecurityType.IND', ''):
            issues.append("Found unreplaced 'SecurityType.IND'")
        
        if issues:
            print("   ❌ Issues found:")
            for issue in issues:
                print(f"      - {issue}")
            return False
        else:
            print("   ✅ File content looks correct")
            
            # Count correct patterns
            future_count = content.count('SecurityType.FUTURE')
            index_count = content.count('SecurityType.INDEX')
            stock_count = content.count('SecurityType.STOCK')
            
            print(f"   📊 Found patterns:")
            print(f"      SecurityType.FUTURE: {future_count}")
            print(f"      SecurityType.INDEX: {index_count}")
            print(f"      SecurityType.STOCK: {stock_count}")
            
            return True
        
    except Exception as e:
        print(f"   ❌ Error reading file: {e}")
        return False

def test_import():
    """Test importing the fixed module."""
    print("\n🧪 TESTING IMPORT")
    print("-" * 20)
    
    try:
        # Clear any cached imports
        import sys
        modules_to_clear = [k for k in sys.modules.keys() if 'SpyderB07_MarketDataManager' in k]
        for module in modules_to_clear:
            del sys.modules[module]
        
        # Try importing
        from SpyderB_Broker.SpyderB07_MarketDataManager import MarketDataManager, ETTimeDisplay
        print("   ✅ MarketDataManager imported successfully!")
        print("   ✅ ETTimeDisplay imported successfully!")
        
        # Test ETTimeDisplay quickly
        et_display = ETTimeDisplay()
        time_str = et_display.get_et_time_string()
        print(f"   ✅ ET Time test: {time_str}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False

def main():
    """Run the precise security type fix."""
    print("🚀 SPYDER PRECISE SECURITY TYPE FIX")
    print("=" * 45)
    
    # Apply the precise fix
    if not fix_security_types_precise():
        return False
        
    # Verify file content
    if not verify_file_content():
        return False
        
    # Test import
    if not test_import():
        return False
        
    print("\n🎉 SUCCESS!")
    print("✅ Precise SecurityType fix completed")
    print("✅ File content verified")
    print("✅ Import test passed")
    print("\n📋 Now you can run:")
    print("   python temp_TestIntegratedSolution.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)