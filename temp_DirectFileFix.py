#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_DirectFileFix.py
Purpose: Direct fix for MarketDataManager SecurityType issues
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:55:00  

Module Description:
    Direct fix that shows the problematic lines and fixes them explicitly.
    This should resolve the FUTUREURE issue once and for all.

"""

import sys
import os

def show_problematic_lines():
    """Show the exact lines causing the problem."""
    manager_file = "SpyderB_Broker/SpyderB07_MarketDataManager.py"
    
    print("🔍 EXAMINING PROBLEMATIC LINES")
    print("=" * 40)
    
    try:
        with open(manager_file, 'r') as f:
            lines = f.readlines()
        
        # Look for lines around line 80 and other problematic areas
        for i, line in enumerate(lines, 1):
            if any(x in line for x in ['FUTUREURE', 'SecurityType.FUT', 'SecurityType.IND']):
                print(f"Line {i}: {line.strip()}")
        
        return lines
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None

def fix_lines_directly(lines):
    """Fix the lines directly."""
    print("\n🔧 FIXING LINES DIRECTLY")
    print("=" * 30)
    
    fixed_lines = []
    changes_made = 0
    
    for i, line in enumerate(lines):
        original_line = line
        
        # Direct replacements
        if 'FUTUREURE' in line:
            line = line.replace('FUTUREURE', 'FUTURE')
            print(f"Line {i+1}: Fixed FUTUREURE → FUTURE")
            changes_made += 1
            
        if 'SecurityType.FUT' in line and 'FUTURE' not in line:
            line = line.replace('SecurityType.FUT', 'SecurityType.FUTURE')
            print(f"Line {i+1}: Fixed SecurityType.FUT → SecurityType.FUTURE")
            changes_made += 1
            
        if 'SecurityType.IND' in line and 'INDEX' not in line:
            line = line.replace('SecurityType.IND', 'SecurityType.INDEX')
            print(f"Line {i+1}: Fixed SecurityType.IND → SecurityType.INDEX")
            changes_made += 1
        
        fixed_lines.append(line)
    
    print(f"Total changes made: {changes_made}")
    return fixed_lines, changes_made

def write_fixed_file(lines):
    """Write the fixed lines back to the file."""
    manager_file = "SpyderB_Broker/SpyderB07_MarketDataManager.py"
    
    try:
        with open(manager_file, 'w') as f:
            f.writelines(lines)
        print(f"✅ File updated: {manager_file}")
        return True
    except Exception as e:
        print(f"❌ Error writing file: {e}")
        return False

def verify_fix():
    """Verify the fix worked."""
    print("\n🧪 VERIFYING FIX")
    print("=" * 20)
    
    try:
        # Clear any cached modules
        modules_to_clear = [k for k in sys.modules.keys() if 'SpyderB07' in k]
        for module in modules_to_clear:
            del sys.modules[module]
        
        # Try importing
        from SpyderB_Broker.SpyderB07_MarketDataManager import MarketDataManager, ETTimeDisplay
        print("✅ Import successful!")
        
        # Quick test
        et_display = ETTimeDisplay()
        time_str = et_display.get_et_time_string()
        print(f"✅ ET Time test: {time_str}")
        
        return True
        
    except Exception as e:
        print(f"❌ Import still failed: {e}")
        return False

def main():
    """Run the direct file fix."""
    print("🚀 DIRECT MARKETDATAMANAGER FIX")
    print("=" * 40)
    
    # Show problematic lines
    lines = show_problematic_lines()
    if not lines:
        return False
    
    # Fix the lines
    fixed_lines, changes = fix_lines_directly(lines)
    
    if changes == 0:
        print("ℹ️ No changes needed")
        return True
    
    # Write the fixed file
    if not write_fixed_file(fixed_lines):
        return False
    
    # Verify the fix
    if verify_fix():
        print("\n🎉 SUCCESS!")
        print("✅ MarketDataManager fixed and tested")
        print("\n📋 Now run:")
        print("   python temp_TestIntegratedSolution.py")
        return True
    else:
        print("\n❌ Fix verification failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)