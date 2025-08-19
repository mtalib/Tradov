#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_RemoveProblemSymbols.py
Purpose: Remove symbols that don't exist from Spyder configuration
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:35:00  

Module Description:
    Removes symbols like VXV and ADD-NYSE that don't exist in IBKR from
    Spyder configuration files to prevent subscription errors.
"""

import os
import re

def remove_problem_symbols():
    """Remove non-existent symbols from Spyder configuration files."""
    
    print("🧹 REMOVING PROBLEM SYMBOLS FROM SPYDER CONFIG")
    print("=" * 60)
    
    # Symbols that don't exist in IBKR
    problem_symbols = ['VXV', 'ADD-NYSE']
    
    # Files that might contain these symbols
    config_files = [
        'SpyderC_MarketData/SpyderC07_MarketDataHub.py',
        'SpyderC_MarketData/SpyderC01_DataFeed.py',
        'SpyderC_MarketData/SpyderC17_MarketConfigManager.py',
    ]
    
    for file_path in config_files:
        if os.path.exists(file_path):
            fix_file(file_path, problem_symbols)
        else:
            print(f"⚠️  File not found: {file_path}")

def fix_file(file_path, problem_symbols):
    """Fix a single file by removing problem symbols."""
    
    print(f"\n🔧 Fixing {file_path}...")
    
    try:
        # Read file
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        changes_made = []
        
        # Remove from UPDATE_TIERS
        for symbol in problem_symbols:
            # Remove from symbol lists in various configurations
            patterns = [
                rf'"symbols": \[[^\]]*"{symbol}"[^\]]*\]',
                rf"'symbols': \[[^\]]*'{symbol}'[^\]]*\]",
                rf'"{symbol}",?\s*',
                rf"'{symbol}',?\s*",
                rf'"{symbol}":\s*\{{[^}}]*\}},?',
                rf"'{symbol}':\s*\{{[^}}]*\}},?",
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Replace the match, handling commas properly
                    original_match = match.group(0)
                    
                    # If it's a symbol list, remove just the symbol and comma
                    if '"symbols":' in original_match or "'symbols':" in original_match:
                        # Remove the symbol from the list
                        new_match = re.sub(rf'"{symbol}",?\s*', '', original_match)
                        new_match = re.sub(rf"'{symbol}',?\s*", '', new_match)
                        # Clean up any double commas
                        new_match = re.sub(r',\s*,', ',', new_match)
                        new_match = re.sub(r'\[\s*,', '[', new_match)
                        new_match = re.sub(r',\s*\]', ']', new_match)
                        content = content.replace(original_match, new_match)
                        changes_made.append(f"Removed {symbol} from symbol list")
                    
                    # If it's a symbol definition, remove the whole definition
                    elif f'"{symbol}":' in original_match or f"'{symbol}':" in original_match:
                        content = content.replace(original_match, '')
                        changes_made.append(f"Removed {symbol} definition")
        
        # Write back if changes were made
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            
            print(f"✅ Updated {file_path}")
            for change in changes_made:
                print(f"   • {change}")
        else:
            print(f"ℹ️  No changes needed in {file_path}")
            
    except Exception as e:
        print(f"❌ Error fixing {file_path}: {e}")

def create_clean_symbol_config():
    """Create a clean symbol configuration with only working symbols."""
    
    clean_config = '''
# WORKING SYMBOLS ONLY - Updated after testing
WORKING_SYMBOL_GROUPS = {
    'CORE': ['SPY', 'SPX', '/ES'],
    'VOLATILITY': ['VIX', 'VIX9D', 'VXMT', 'VVIX', 'UVXY'],  # Removed VXV (doesn't exist)
    'INTERNALS': ['TICK-NYSE', 'TRIN-NYSE', 'CPC', 'PCALL', 'SKEW'],  # Removed ADD-NYSE (doesn't exist)
    'INDICES': ['DIA', 'QQQ', 'IWM'],
    'FIXED_INCOME': ['TLT', 'LQD'],
    'CORRELATIONS': ['DXY', 'GLD']
}

# CLEAN UPDATE TIERS - Problem symbols removed
CLEAN_UPDATE_TIERS = {
    "CRITICAL": {
        "symbols": ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
        "frequency": 1,
        "priority": 1,
        "method": "streaming",
    },
    "HIGH": {
        "symbols": [
            "VIX9D", "VXMT", "VVIX", "UVXY",  # Removed VXV
            "TRIN-NYSE", "CPC", "PCALL", "SKEW",  # Removed ADD-NYSE
            "DIA", "QQQ", "IWM",
        ],
        "frequency": 5,
        "priority": 2,
        "method": "streaming",
    },
    "MEDIUM": {
        "symbols": [
            "VXST", "VXN", "RVX", "CPCE", "CPCI",
            "TICK-NASDAQ", "TRIN-NASDAQ",
            "XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLRE", "XLC", "XLB",
        ],
        "frequency": 30,
        "priority": 3,
        "method": "snapshot",
    },
    "LOW": {
        "symbols": ["TLT", "LQD", "DXY", "GLD"],
        "frequency": 15,
        "priority": 4,
        "method": "snapshot",
    },
}
'''
    
    # Write clean config to a reference file
    with open('temp_CleanSymbolConfig.py', 'w') as f:
        f.write(clean_config)
    
    print("📝 Created temp_CleanSymbolConfig.py with working symbols only")

def main():
    """Main function to clean up symbol configuration."""
    
    # Remove problem symbols from config files
    remove_problem_symbols()
    
    # Create clean configuration reference
    create_clean_symbol_config()
    
    print("\n🎉 CLEANUP COMPLETE!")
    print("\n🔄 Next Steps:")
    print("1. Wait 5-10 more minutes for CBOE subscriptions to activate")
    print("2. Restart IB Gateway completely")
    print("3. Restart Spyder")
    print("4. Check if data is now flowing")
    print("\n💡 The symbols VXV and ADD-NYSE don't exist in IBKR.")
    print("   Spyder will now focus on working symbols only.")

if __name__ == "__main__":
    main()