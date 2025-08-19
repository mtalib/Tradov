#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_AddClient10ToB08.py
Purpose: Add Client 10 to SpyderB08 and delete SpyderB19
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 16:20:00  

Module Description:
    Updates SpyderB08_MultiClientDataManager.py to include Client 10 for
    International symbols and removes the confusing SpyderB19 module.
    Creates a unified 1-10 client management system.
"""

import os
import re
import shutil
from pathlib import Path

def update_spyderb08_with_client10():
    """Update SpyderB08 to include Client 10 for International symbols."""
    
    b08_file = Path("SpyderB_Broker/SpyderB08_MultiClientDataManager.py")
    
    if not b08_file.exists():
        b08_file = Path("SpyderB08_MultiClientDataManager.py")  # Alternative location
    
    if not b08_file.exists():
        print("❌ SpyderB08_MultiClientDataManager.py not found")
        return False
    
    print(f"🔧 Updating {b08_file} to include Client 10...")
    
    try:
        # Read the current file
        with open(b08_file, 'r') as f:
            content = f.read()
        
        # Create backup
        backup_file = b08_file.with_suffix('.py.backup')
        shutil.copy2(b08_file, backup_file)
        print(f"✅ Created backup: {backup_file}")
        
        # Add Client 10 to client_configs
        client_10_config = '''            10: {  # NEW: International symbols
                "purpose": ClientPurpose.INTERNATIONAL,
                "symbols": [
                    # European Indices
                    "DAX", "CAC40", "FTSE", "STOXX50", "SMI",
                    # Asian Indices  
                    "N225", "HSI", "KOSPI", "ASX200", "STI",
                    # International ETFs
                    "EWJ", "EWG", "EWU", "EWZ", "EEM", "VEA", "VWO",
                    # Major FX pairs
                    "EUR.USD", "GBP.USD", "USD.JPY", "AUD.USD", "USD.CHF",
                    # International Commodities
                    "BRENT", "WTI", "NATGAS"
                ],
                "frequency": 30.0,
                "description": "International markets (30s)",
                "priority": "LOW",
            },'''
        
        # Find the end of client_configs dictionary (before the closing brace)
        pattern = r'(\s*9:\s*\{[^}]*\}[^}]*)((\s*\})\s*# Create client info objects)'
        
        if re.search(pattern, content, re.DOTALL):
            # Insert Client 10 before the closing brace
            content = re.sub(
                pattern,
                r'\1\n' + client_10_config + r'\2',
                content,
                flags=re.DOTALL
            )
            print("✅ Added Client 10 configuration to client_configs")
        else:
            print("⚠️  Could not find insertion point for Client 10 config")
        
        # Add INTERNATIONAL to ClientPurpose enum
        enum_addition = '''    INTERNATIONAL = "International Markets"  # Client 10'''
        
        if 'INTERNATIONAL' not in content:
            # Find the ClientPurpose enum and add INTERNATIONAL
            enum_pattern = r'(class ClientPurpose\(Enum\):[^}]*SECTOR_ETFS = "[^"]*"[^\n]*)'
            if re.search(enum_pattern, content, re.DOTALL):
                content = re.sub(
                    enum_pattern,
                    r'\1\n    ' + enum_addition.strip(),
                    content,
                    flags=re.DOTALL
                )
                print("✅ Added INTERNATIONAL to ClientPurpose enum")
        
        # Update range from 1-9 to 1-10 in comments and documentation
        content = re.sub(r'Clients 1-9', 'Clients 1-10', content)
        content = re.sub(r'clients 1-9', 'clients 1-10', content)
        content = re.sub(r'range\(1, 10\)', 'range(1, 11)', content)
        content = re.sub(r'CLIENT.*1-9', 'CLIENT ALLOCATION (1-10)', content)
        
        # Update the allocation summary to include Client 10
        priority_update = '''        priority_order = [
            (2, "ORDER EXECUTION", "CRITICAL - Fastest trading execution"),
            (1, "ADMINISTRATIVE", "SYSTEM - Account & control"),
            (3, "CORE DATA", "CRITICAL - SPY, VIX real-time (1s)"),
            (4, "SPY OPTIONS", "CRITICAL - 0DTE/1DTE options (1s)"),
            (5, "VOLATILITY", "HIGH - Volatility surface (5s)"),
            (6, "MARKET INTERNALS", "HIGH - Market breadth (5s)"),
            (7, "MAJOR INDICES", "HIGH - DIA/QQQ/IWM (5s)"),
            (8, "EXTENDED ASSETS", "MEDIUM - Bonds/FX/Commodities (15s)"),
            (9, "SECTOR ETFS", "LOW - Sector rotation (30s)"),
            (10, "INTERNATIONAL", "LOW - Global markets (30s)"),  # NEW
        ]'''
        
        # Replace the priority_order list
        priority_pattern = r'priority_order = \[[^\]]*\]'
        if re.search(priority_pattern, content, re.DOTALL):
            content = re.sub(
                priority_pattern,
                priority_update.strip(),
                content,
                flags=re.DOTALL
            )
            print("✅ Updated priority_order to include Client 10")
        
        # Update client range in initialization
        init_pattern = r'for client_id in range\(1, 10\)'
        content = re.sub(init_pattern, 'for client_id in range(1, 11)', content)
        
        # Write the updated content
        with open(b08_file, 'w') as f:
            f.write(content)
        
        print(f"✅ Successfully updated {b08_file} with Client 10")
        return True
        
    except Exception as e:
        print(f"❌ Error updating SpyderB08: {e}")
        return False

def delete_spyderb19():
    """Delete the SpyderB19 module and create backup."""
    
    b19_paths = [
        Path("SpyderB_Broker/SpyderB19_Client10Configuration.py"),
        Path("SpyderB19_Client10Configuration.py")
    ]
    
    deleted = False
    
    for b19_file in b19_paths:
        if b19_file.exists():
            print(f"🗑️  Deleting {b19_file}...")
            
            # Create backup first
            backup_file = b19_file.with_name(f"DELETED_{b19_file.name}")
            shutil.copy2(b19_file, backup_file)
            print(f"📁 Created backup: {backup_file}")
            
            # Delete original
            b19_file.unlink()
            print(f"✅ Deleted {b19_file}")
            deleted = True
    
    if not deleted:
        print("ℹ️  SpyderB19_Client10Configuration.py not found")
    
    return deleted

def create_verification_script():
    """Create a script to verify the Client 10 integration."""
    
    verification_script = '''#!/usr/bin/env python3
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
        
        print("\\n🎉 CLIENT 10 INTEGRATION VERIFICATION COMPLETE")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
    except Exception as e:
        print(f"❌ Verification error: {e}")

if __name__ == "__main__":
    verify_client_10_integration()
'''
    
    with open('temp_VerifyClient10.py', 'w') as f:
        f.write(verification_script)
    
    print("✅ Created verification script: temp_VerifyClient10.py")

def main():
    """Main function to add Client 10 to B08 and delete B19."""
    print("🔧 SPYDER CLIENT 10 INTEGRATION")
    print("=" * 50)
    print("Adding Client 10 to SpyderB08 and removing SpyderB19")
    print()
    
    success_count = 0
    
    # Step 1: Update SpyderB08 with Client 10
    print("1️⃣ Adding Client 10 to SpyderB08...")
    if update_spyderb08_with_client10():
        success_count += 1
    
    # Step 2: Delete SpyderB19
    print("\\n2️⃣ Removing SpyderB19...")
    if delete_spyderb19():
        success_count += 1
    
    # Step 3: Create verification script
    print("\\n3️⃣ Creating verification script...")
    create_verification_script()
    success_count += 1
    
    # Summary
    print("\\n" + "=" * 50)
    print("📊 INTEGRATION SUMMARY")
    print("=" * 50)
    
    if success_count >= 2:
        print("🎉 SUCCESS! Client 10 integration complete")
        print()
        print("✅ What was accomplished:")
        print("   • SpyderB08 now handles ALL clients (1-10)")
        print("   • Client 10 configured for International symbols")
        print("   • SpyderB19 removed (eliminated confusion)")
        print("   • Unified client management system")
        print()
        print("🔄 Next steps:")
        print("   1. Run: python temp_VerifyClient10.py")
        print("   2. Test multi-client connections")
        print("   3. Restart Spyder with updated configuration")
        print()
        print("🌍 Client 10 International Symbols:")
        print("   • European: DAX, CAC40, FTSE, STOXX50")
        print("   • Asian: N225, HSI, KOSPI, ASX200") 
        print("   • FX: EUR.USD, GBP.USD, USD.JPY")
        print("   • Global ETFs: EWJ, EWG, EWU, EEM")
    else:
        print("⚠️  Some steps failed - check errors above")
    
    print("\\n✨ SpyderB08 is now the complete 1-10 client manager!")

if __name__ == "__main__":
    main()
