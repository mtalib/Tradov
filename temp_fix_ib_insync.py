#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUTO-GENERATED: IB_INSYNC to IB_ASYNC Conversion Script

Generated: 2025-08-21 18:45:03
Root Path: /home/adam/Projects/Spyder
Files Found: 19
Total Occurrences: 204

USAGE:
    python temp_fix_ib_insync.py --preview    # Show what would be changed
    python temp_fix_ib_insync.py --apply      # Apply the changes
    python temp_fix_ib_insync.py --backup     # Create backups first
"""

import re
import shutil
from pathlib import Path

# Root directory
ROOT_PATH = Path("/home/adam/Projects/Spyder")

# Files to process
AFFECTED_FILES = ['SpyderQ_Scripts/SpyderQ45_Diagnostics.py', 'SpyderR_Runtime/SpyderR02_PaperEngine.py', 'SpyderR_Runtime/SpyderR05_IBDataBridge.py', 'SpyderR_Runtime/SpyderR05_WorkingBridge.py', 'SpyderT_TestModules/SpyderT02_BrokerTestSuite.py', 'SpyderI_Integration/SpyderI05_IBAPIMigrator.py', 'SpyderB_Broker/SpyderB07_MarketDataManager.py', 'SpyderB_Broker/SpyderB06_ContractBuilder.py', 'SpyderB_Broker/SpyderB14_MultiClientWatchdog.py', 'SpyderB_Broker/SpyderB02_OrderManager.py', 'SpyderB_Broker/SpyderB01_SpyderClient.py', 'SpyderB_Broker/SpyderB15_PrometheusMetrics.py', 'SpyderB_Broker/SpyderB17_SPYOptionsChainManager.py', 'SpyderB_Broker/SpyderB10_IBDataTypes.py', 'SpyderC_MarketData/SpyderC14_UltraLowLatencyFeed.py', 'SpyderC_MarketData/SpyderC03_OptionChain.py', 'SpyderC_MarketData/SpyderC07_MarketDataHub.py', 'SpyderC_MarketData/SpyderC07_OPRAFeed.py', 'SpyderC_MarketData/SpyderC02_HistoricalData.py']

# Replacement patterns
REPLACEMENTS = {'from ib_insync import': 'from ib_async import', 'import ib_insync': 'import ib_async', 'ib_insync.': 'ib_async.', 'HAS_IB_INSYNC': 'HAS_IB_ASYNC', 'ib_insync_AVAILABLE': 'ib_async_AVAILABLE', 'IB_INSYNC_AVAILABLE': 'IB_ASYNC_AVAILABLE', '"ib_insync': '"ib_async', "'ib_insync": "'ib_async", 'ib_insync not available': 'ib_async not available', 'install ib_insync': 'install ib_async', 'pip install ib_insync': 'pip install ib_async'}

def preview_changes():
    """Preview what would be changed"""
    print("🔍 PREVIEW: Changes that would be made:")
    print("=" * 60)
    
    for file_path in AFFECTED_FILES:
        full_path = ROOT_PATH / file_path
        print(f"\n📄 {file_path}")
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            changes = 0
            for old, new in REPLACEMENTS.items():
                if old in content:
                    count = content.count(old)
                    changes += count
                    print(f"   • '{old}' → '{new}' ({count} times)")
                    
            if changes == 0:
                print("   ✅ No changes needed")
                
        except Exception as e:
            print(f"   ❌ Error reading file: {e}")

def apply_changes(create_backup=True):
    """Apply the changes to files"""
    print("🔧 APPLYING: Changes to files...")
    print("=" * 60)
    
    success_count = 0
    error_count = 0
    
    for file_path in AFFECTED_FILES:
        full_path = ROOT_PATH / file_path
        
        try:
            # Create backup if requested
            if create_backup:
                backup_path = full_path.with_suffix(full_path.suffix + '.backup')
                shutil.copy2(full_path, backup_path)
                print(f"💾 Backup created: {backup_path}")
            
            # Read file
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Apply replacements
            original_content = content
            for old, new in REPLACEMENTS.items():
                content = content.replace(old, new)
            
            # Write back if changed
            if content != original_content:
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Updated: {file_path}")
                success_count += 1
            else:
                print(f"📋 No changes: {file_path}")
                
        except Exception as e:
            print(f"❌ Error processing {file_path}: {e}")
            error_count += 1
    
    print(f"\n📊 SUMMARY:")
    print(f"   ✅ Successfully updated: {success_count} files")
    print(f"   ❌ Errors: {error_count} files")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python temp_fix_ib_insync.py [--preview|--apply|--backup]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "--preview":
        preview_changes()
    elif action == "--apply":
        apply_changes(create_backup=False)
    elif action == "--backup":
        apply_changes(create_backup=True)
    else:
        print("Invalid action. Use --preview, --apply, or --backup")
        sys.exit(1)
