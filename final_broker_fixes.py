#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Final fixes for the remaining two broker package issues:
1. Add get_gateway_automation function to SpyderB12_GatewayAutomation.py
2. Fix ContractBuilder import issue in SpyderB06_ContractBuilder.py
"""

import os
import sys
from pathlib import Path

def fix_gateway_automation():
    """Add missing get_gateway_automation function."""
    file_path = Path("SpyderB_Broker/SpyderB12_GatewayAutomation.py")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    try:
        # Read existing content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if function already exists
        if "def get_gateway_automation" in content:
            print("✅ get_gateway_automation already exists")
            return True
        
        # Add the missing function
        additional_code = '''

def get_gateway_automation(config=None):
    """
    Get GatewayAutomation instance (compatibility function).
    
    Args:
        config: Optional gateway configuration
        
    Returns:
        GatewayAutomation: Gateway automation instance
    """
    return create_gateway_automation(config)
'''
        
        content += additional_code
        
        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Added get_gateway_automation function to SpyderB12_GatewayAutomation.py")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing gateway automation: {e}")
        return False

def fix_contract_builder():
    """Fix ContractBuilder import by ensuring class is properly exported."""
    file_path = Path("SpyderB_Broker/SpyderB06_ContractBuilder.py")
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    try:
        # Read existing content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if __all__ exists and includes ContractBuilder
        if "__all__" in content and "ContractBuilder" in content:
            print("✅ ContractBuilder export looks correct")
            return True
        
        # Add proper export at the end if missing
        if "__all__" not in content:
            additional_code = '''

# Export list for proper module imports
__all__ = [
    'ContractBuilder',
    'get_contract_builder', 
    'create_contract_builder',
    'build_spy_stock',
    'build_spy_option'
]
'''
            content += additional_code
            
            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Added __all__ export list to SpyderB06_ContractBuilder.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing contract builder: {e}")
        return False

def main():
    """Apply final fixes."""
    print("APPLYING FINAL BROKER PACKAGE FIXES")
    print("=" * 50)
    
    # Check we're in the right directory
    if not Path("SpyderB_Broker").exists():
        print("❌ Please run from Spyder project root directory")
        return False
    
    print("1. Fixing GatewayAutomation get_gateway_automation function...")
    fix1 = fix_gateway_automation()
    
    print("\n2. Fixing ContractBuilder export...")
    fix2 = fix_contract_builder()
    
    if fix1 and fix2:
        print("\n✅ All fixes applied successfully!")
        print("\nNow run the test again:")
        print("python test_broker_package_fixes.py")
        print("\nExpected: 100% success rate!")
        return True
    else:
        print("\n⚠️ Some fixes failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
