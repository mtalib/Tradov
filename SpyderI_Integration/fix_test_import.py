#!/usr/bin/env python3
"""
Quick fix for test import issue
"""

print("🔧 Fixing import issue in test file...")

# Read the test file
try:
    with open("test_spyder_ib_integration.py", "r") as f:
        content = f.read()
    
    # Fix the import issue
    # Replace OptionContract with SpyderOptionContract
    content = content.replace(
        "from SpyderI15_IBTradingInterface import OptionContract, OptionType, get_spy_expiry_dates",
        "from SpyderI15_IBTradingInterface import SpyderOptionContract, OptionType, get_spy_expiry_dates"
    )
    
    # Replace usage of OptionContract with SpyderOptionContract
    content = content.replace(
        "test_option = OptionContract(",
        "test_option = SpyderOptionContract("
    )
    
    # Write back the fixed file
    with open("test_spyder_ib_integration.py", "w") as f:
        f.write(content)
    
    print("✅ Fixed import issue in test file")
    print("🚀 Now run: python3 test_spyder_ib_integration.py")
    
except Exception as e:
    print(f"❌ Error fixing test file: {e}")
