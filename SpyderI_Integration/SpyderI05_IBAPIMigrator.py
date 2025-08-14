#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderI05_IBAPIMigrator.py
Group: I (Integration)
Purpose: Migrate all IBAPI imports to ib_insync system-wide
Author: Mohamed Talib
Date Created: 2025-08-14
Last Updated: 2025-08-14 Time: 16:45:00

Description:
    This module provides a comprehensive migration tool to convert all IBAPI
    imports and usage to ib_insync throughout the Spyder codebase. It handles
    import statements, class references, method calls, and ensures compatibility
    with the ib_insync API structure.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import re
import sys
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
import json
import ast
import difflib

# ==============================================================================
# CONSTANTS
# ==============================================================================

# IBAPI to ib_insync mapping
IMPORT_MAPPINGS = {
    # Contract types
    'from ib_insync import Contract': 'from ib_insync import Contract',
    'from ib_insync import Stock': 'from ib_insync import Stock',
    'from ib_insync import Option': 'from ib_insync import Option',
    'from ib_insync import Future': 'from ib_insync import Future',
    'from ib_insync import Forex': 'from ib_insync import Forex',
    'from ib_insync import Bond': 'from ib_insync import Bond',
    'from ib_insync import Warrant': 'from ib_insync import Warrant',
    'from ib_insync import FuturesOption': 'from ib_insync import FuturesOption',
    'from ib_insync import Bag': 'from ib_insync import Bag',
    'from ib_insync import ComboLeg': 'from ib_insync import ComboLeg',
    
    # Order types
    'from ib_insync import Order, LimitOrder, MarketOrder, StopOrder': 'from ib_insync import Order, LimitOrder, MarketOrder, StopOrder',
    'from ib_insync import Order, LimitOrder, MarketOrder, StopOrderState': 'from ib_insync import OrderState',
    'from ib_insync import Order, LimitOrder, MarketOrder, StopOrderStatus': 'from ib_insync import OrderStatus',
    'from ib_insync import Order, LimitOrder, MarketOrder, StopOrderType': 'from ib_insync import Order',  # OrderType is implicit in ib_insync
    
    # Execution
    'from ib_insync import Execution': 'from ib_insync import Execution',
    'from ib_insync import ExecutionFilter': 'from ib_insync import ExecutionFilter',
    
    # Common types
    'from ib_insync import Ticker': 'from ib_insync import Ticker',
    '# TickerId not needed in ib_insync': '# TickerId not needed in ib_insync',
    '# OrderId is just int in ib_insync': '# OrderId is just int in ib_insync',
    'from ib_insync import TagValue': 'from ib_insync import TagValue',
    'from ib_insync import BarData': 'from ib_insync import BarData',
    
    # Tick types
    'from ib_insync import Ticker': 'from ib_insync import Ticker',
    'from ib_insync import TickerEnum': 'from ib_insync import Ticker',
    
    # Client and wrapper
    '# IB functionality is in IB class': '# IB functionality is in IB class',
    '# IB functionality is in IB class': '# IB functionality is in IB class',
    '# wrapper module not needed with ib_insync': '# wrapper module not needed with ib_insync',
    '# client module not needed with ib_insync': '# client module not needed with ib_insync',
    
    # Scanner
    'from ib_insync import ScannerSubscription': 'from ib_insync import ScannerSubscription',
    
    # Account
    'from ib_insync import AccountValue': 'from ib_insync import AccountValue',
    
    # Commission
    'from ib_insync import CommissionReport': 'from ib_insync import CommissionReport',
    
    # General ibapi imports
    'import ib_insync': 'import ib_insync',
    'from ib_insync import': 'from ib_insync import',
}

# Class name mappings
CLASS_MAPPINGS = {
    'IB': 'IB',
    'IB': 'IB',
    'TickerField.': 'TickerField.',
    'OrderType.': '',  # Remove OrderType references
}

# Method mappings
METHOD_MAPPINGS = {
    # Connection methods
    'self.ib.connect(': 'self.ib.connect(',
    'self.ib.disconnect(': 'self.ib.disconnect(',
    'self.ib.isConnected(': 'self.ib.isConnected(',
    
    # Request methods
    'self.ib.reqMktData(': 'self.ib.reqMktData(',
    'self.ib.cancelMktData(': 'self.ib.cancelMktData(',
    'self.ib.reqHistoricalData(': 'self.ib.reqHistoricalData(',
    'self.ib.cancelHistoricalData(': 'self.ib.cancelHistoricalData(',
    'self.ib.reqRealTimeBars(': 'self.ib.reqRealTimeBars(',
    'self.ib.cancelRealTimeBars(': 'self.ib.cancelRealTimeBars(',
    'self.ib.reqContractDetails(': 'self.ib.reqContractDetails(',
    'self.ib.reqAccountUpdates(': 'self.ib.reqAccountUpdates(',
    'self.ib.reqAccountSummary(': 'self.ib.reqAccountSummary(',
    'self.ib.cancelAccountSummary(': 'self.ib.cancelAccountSummary(',
    'self.ib.reqPositions(': 'self.ib.reqPositions(',
    'self.ib.cancelPositions(': 'self.ib.cancelPositions(',
    'self.ib.reqOpenOrders(': 'self.ib.reqOpenOrders(',
    'self.ib.placeOrder(': 'self.ib.placeOrder(',
    'self.ib.cancelOrder(': 'self.ib.cancelOrder(',
    'self.ib.reqIds(': 'self.ib.reqIds(',
    
    # Callback methods (need different handling in ib_insync)
    '# Error handling via IB.errorEvent': '# Error handling via IB.errorEvent',
    '# Use IB.pendingTickersEvent': '# Use IB.pendingTickersEvent',
    '# Use IB.pendingTickersEvent': '# Use IB.pendingTickersEvent',
    '# Use IB.orderStatusEvent': '# Use IB.orderStatusEvent',
    '# Use IB.openOrderEvent': '# Use IB.openOrderEvent',
    '# Use IB.positionEvent': '# Use IB.positionEvent',
    '# Use IB.accountSummaryEvent': '# Use IB.accountSummaryEvent',
    '# Use IB.contractDetailsEvent': '# Use IB.contractDetailsEvent',
    '# Use IB.execDetailsEvent': '# Use IB.execDetailsEvent',
    '# Use IB.accountValueEvent': '# Use IB.accountValueEvent',
    '# Use IB.updatePortfolioEvent': '# Use IB.updatePortfolioEvent',
    '# Historical data is returned directly': '# Historical data is returned directly',
}

# Files to skip
SKIP_FILES = {
    '__pycache__',
    '.git',
    '.venv',
    'venv',
    '.env',
    '*.pyc',
    '*.pyo',
    '*.bak',
}

# ==============================================================================
# MIGRATION CLASS
# ==============================================================================

class IBAPIMigrator:
    """
    Comprehensive IBAPI to ib_insync migration tool.
    
    This class handles the complete migration of IBAPI imports and usage
    to ib_insync throughout the Spyder codebase.
    """
    
    def __init__(self, project_root: str = "."):
        """Initialize the migrator."""
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / f"backup_ibapi_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.files_processed = 0
        self.files_modified = 0
        self.total_changes = 0
        self.migration_log = []
        
    def migrate_all(self, dry_run: bool = False) -> Dict[str, any]:
        """
        Migrate all Python files from IBAPI to ib_insync.
        
        Args:
            dry_run: If True, show what would be changed without modifying files
            
        Returns:
            Migration report dictionary
        """
        print("=" * 80)
        print("🔄 IBAPI → ib_insync Migration Tool")
        print("=" * 80)
        
        if not dry_run:
            print(f"📁 Creating backup at: {self.backup_dir}")
            self.backup_dir.mkdir(exist_ok=True)
        
        # Find all Python files
        python_files = self._find_python_files()
        print(f"📊 Found {len(python_files)} Python files to check")
        
        # Process each file
        for file_path in python_files:
            self._process_file(file_path, dry_run)
        
        # Generate report
        report = self._generate_report()
        
        # Save migration log
        if not dry_run and self.files_modified > 0:
            log_file = self.project_root / "ibapi_migration_log.json"
            with open(log_file, 'w') as f:
                json.dump(self.migration_log, f, indent=2, default=str)
            print(f"\n📝 Migration log saved to: {log_file}")
        
        return report
    
    def _process_file(self, file_path: Path, dry_run: bool) -> None:
        """Process a single Python file."""
        self.files_processed += 1
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Check if file contains IBAPI references
            if not self._contains_ibapi(original_content):
                return
            
            print(f"\n📄 Processing: {file_path.relative_to(self.project_root)}")
            
            # Create backup if not dry run
            if not dry_run:
                backup_path = self.backup_dir / file_path.relative_to(self.project_root)
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, backup_path)
            
            # Migrate content
            modified_content = self._migrate_content(original_content, file_path)
            
            # Check if changes were made
            if modified_content != original_content:
                self.files_modified += 1
                changes = self._get_changes(original_content, modified_content)
                
                print(f"  ✏️  {len(changes)} changes found")
                
                if dry_run:
                    print("  🔍 Changes (dry run - not applied):")
                    for change in changes[:5]:  # Show first 5 changes
                        print(f"    - {change}")
                    if len(changes) > 5:
                        print(f"    ... and {len(changes) - 5} more")
                else:
                    # Write modified content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(modified_content)
                    print(f"  ✅ File updated successfully")
                
                # Log changes
                self.migration_log.append({
                    'file': str(file_path),
                    'changes': changes,
                    'timestamp': datetime.now().isoformat()
                })
                
                self.total_changes += len(changes)
        
        except Exception as e:
            print(f"  ❌ Error processing {file_path}: {e}")
    
    def _contains_ibapi(self, content: str) -> bool:
        """Check if content contains IBAPI references."""
        ibapi_patterns = [
            r'from\s+ibapi',
            r'import\s+ibapi',
            r'ibapi\.',
            r'IB',
            r'IB',
            r'TickType\.',
            r'OrderType\.',
        ]
        
        for pattern in ibapi_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    
    def _migrate_content(self, content: str, file_path: Path) -> str:
        """Migrate IBAPI content to ib_insync."""
        modified = content
        
        # Step 1: Replace import statements
        for old_import, new_import in IMPORT_MAPPINGS.items():
            if old_import in modified:
                modified = modified.replace(old_import, new_import)
        
        # Step 2: Handle wildcard imports
        modified = re.sub(
            r'from\s+ibapi\.(\w+)\s+import\s+\*',
            r'from ib_insync import *  # Migrated from ibapi.\1',
            modified
        )
        
        # Step 3: Replace class names
        for old_class, new_class in CLASS_MAPPINGS.items():
            modified = re.sub(r'\b' + re.escape(old_class) + r'\b', new_class, modified)
        
        # Step 4: Replace method calls
        for old_method, new_method in METHOD_MAPPINGS.items():
            modified = modified.replace(old_method, new_method)
        
        # Step 5: Fix Contract creation (IBAPI vs ib_insync style)
        modified = self._fix_contract_creation(modified)
        
        # Step 6: Fix Order creation
        modified = self._fix_order_creation(modified)
        
        # Step 7: Add IB instance if needed
        modified = self._add_ib_instance(modified, file_path)
        
        # Step 8: Fix specific ib_insync patterns
        modified = self._fix_ibinsync_patterns(modified)
        
        return modified
    
    def _fix_contract_creation(self, content: str) -> str:
        """Fix Contract creation patterns."""
        # IBAPI style: contract = Contract()  # Note: Set attributes or use Stock/Option/etc.
        # ib_insync style: contract = Stock('SPY', 'SMART', 'USD')
        
        # Fix basic Contract() instantiation
        content = re.sub(
            r'contract\s*=\s*Contract\(\)',
            'contract = Contract()  # Note: Set attributes or use Stock/Option/etc.  # Note: Set attributes or use Stock/Option/etc.',
            content
        )
        
        # Add helper comment for option contracts
        if 'contract.secType = "OPT"  # Consider using Option() class instead' in content:
            content = content.replace(
                'contract.secType = "OPT"  # Consider using Option() class instead',
                'contract.secType = "OPT"  # Consider using Option() class instead  # Consider using Option() class instead'
            )
        
        # Add helper comment for stock contracts
        if 'contract.secType = "STK"  # Consider using Stock() class instead' in content:
            content = content.replace(
                'contract.secType = "STK"  # Consider using Stock() class instead',
                'contract.secType = "STK"  # Consider using Stock() class instead  # Consider using Stock() class instead'
            )
        
        return content
    
    def _fix_order_creation(self, content: str) -> str:
        """Fix Order creation patterns."""
        # IBAPI style: order = Order()  # Consider using MarketOrder/LimitOrder/etc.
        # ib_insync style: order = MarketOrder('BUY', 100)
        
        # Fix basic Order() instantiation
        content = re.sub(
            r'order\s*=\s*Order\(\)',
            'order = Order()  # Consider using MarketOrder/LimitOrder/etc.  # Consider using MarketOrder/LimitOrder/etc.',
            content
        )
        
        # Fix order type assignments
        content = content.replace(
            'order.orderType = "MKT"  # Consider using MarketOrder() instead',
            'order.orderType = "MKT"  # Consider using MarketOrder() instead  # Consider using MarketOrder() instead'
        )
        
        content = content.replace(
            'order.orderType = "LMT"  # Consider using LimitOrder() instead',
            'order.orderType = "LMT"  # Consider using LimitOrder() instead  # Consider using LimitOrder() instead'
        )
        
        return content
    
    def _add_ib_instance(self, content: str, file_path: Path) -> str:
        """Add IB instance initialization if needed."""
        # Check if this is a broker module that needs IB instance
        if 'SpyderB_' in str(file_path) and 'class' in content:
            # Check if IB is imported but not initialized
            if 'from ib_insync import' in content and 'self.ib = IB()' not in content:
                # Find __init__ method and add IB initialization
                init_pattern = r'(def __init__\(self[^)]*\):\s*\n)'
                replacement = r'\1        self.ib = IB()  # IB connection instance\n'
                content = re.sub(init_pattern, replacement, content, count=1)
        
        return content
    
    def _fix_ibinsync_patterns(self, content: str) -> str:
        """Fix specific ib_insync patterns."""
        # Fix Ticker usage
        content = content.replace('TickerField.BID', 'TickerField.BID')
        content = content.replace('TickerField.ASK', 'TickerField.ASK')
        content = content.replace('TickerField.LAST', 'TickerField.LAST')
        content = content.replace('TickerField.VOLUME', 'TickerField.VOLUME')
        
        # Fix async patterns
        if 'async def' in content:
            # ib_insync uses asyncio natively
            content = content.replace('self.ib.connect(', 'await self.ib.connectAsync(')
            content = content.replace('self.ib.reqHistoricalData(', 'await self.ib.reqHistoricalDataAsync(')
        
        return content
    
    def _get_changes(self, original: str, modified: str) -> List[str]:
        """Get list of changes between original and modified content."""
        changes = []
        
        original_lines = original.splitlines()
        modified_lines = modified.splitlines()
        
        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            lineterm='',
            n=0
        )
        
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                changes.append(line[1:].strip())
            elif line.startswith('-') and not line.startswith('---'):
                changes.append(f"Removed: {line[1:].strip()}")
        
        return changes
    
    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the project."""
        python_files = []
        
        for pattern in ['Spyder*/**/*.py', 'spyder*/**/*.py']:
            python_files.extend(self.project_root.glob(pattern))
        
        # Filter out files to skip
        filtered_files = []
        for file_path in python_files:
            skip = False
            for skip_pattern in SKIP_FILES:
                if skip_pattern in str(file_path):
                    skip = True
                    break
            
            if not skip:
                filtered_files.append(file_path)
        
        return sorted(filtered_files)
    
    def _generate_report(self) -> Dict[str, any]:
        """Generate migration report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'files_processed': self.files_processed,
            'files_modified': self.files_modified,
            'total_changes': self.total_changes,
            'backup_location': str(self.backup_dir) if self.files_modified > 0 else None,
            'success_rate': (self.files_processed - self.files_modified) / max(self.files_processed, 1) * 100
        }
        
        print("\n" + "=" * 80)
        print("📊 MIGRATION REPORT")
        print("=" * 80)
        print(f"Files Processed: {report['files_processed']}")
        print(f"Files Modified: {report['files_modified']}")
        print(f"Total Changes: {report['total_changes']}")
        
        if report['backup_location']:
            print(f"Backup Location: {report['backup_location']}")
        
        if self.files_modified > 0:
            print(f"\n✅ Migration completed successfully!")
            print(f"   {self.files_modified} files were updated")
            print(f"   {self.total_changes} changes were made")
        else:
            print(f"\n✨ No IBAPI references found - system already using ib_insync!")
        
        return report
    
    def restore_backup(self) -> bool:
        """Restore files from the latest backup."""
        if not self.backup_dir.exists():
            print("❌ No backup found to restore")
            return False
        
        print(f"🔄 Restoring from backup: {self.backup_dir}")
        
        for backup_file in self.backup_dir.rglob("*.py"):
            original_path = self.project_root / backup_file.relative_to(self.backup_dir)
            shutil.copy2(backup_file, original_path)
            print(f"  ✅ Restored: {original_path}")
        
        print("✅ Backup restored successfully")
        return True

# ==============================================================================
# QUICK FIX FUNCTIONS
# ==============================================================================

def create_ibinsync_adapter() -> str:
    """
    Create an adapter module for ib_insync compatibility.
    
    Returns:
        Adapter module content as string
    """
    return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - IB_INSYNC Adapter Module

This module provides compatibility layer between IBAPI-style code and ib_insync.
"""

from ib_insync import *

# Re-export common types with IBAPI names for compatibility
# TickType handling updated for ib_insync

# Provide IBAPI-style Contract creation
def create_contract(symbol: str, sec_type: str = 'STK', exchange: str = 'SMART', 
                    currency: str = 'USD', **kwargs):
    """Create contract in IBAPI style but return ib_insync object."""
    if sec_type == 'STK':
        return Stock(symbol, exchange, currency, **kwargs)
    elif sec_type == 'OPT':
        return Option(symbol, kwargs.get('lastTradeDateOrContractMonth', ''),
                     kwargs.get('strike', 0), kwargs.get('right', 'C'),
                     exchange, **kwargs)
    elif sec_type == 'FUT':
        return Future(symbol, kwargs.get('lastTradeDateOrContractMonth', ''),
                     exchange, **kwargs)
    else:
        contract = Contract()  # Note: Set attributes or use Stock/Option/etc.
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
        for key, value in kwargs.items():
            setattr(contract, key, value)
        return contract

# Provide IBAPI-style Order creation
def create_order(action: str, quantity: float, order_type: str = 'MKT', **kwargs):
    """Create order in IBAPI style but return ib_insync object."""
    if order_type == 'MKT':
        return MarketOrder(action, quantity, **kwargs)
    elif order_type == 'LMT':
        return LimitOrder(action, quantity, kwargs.get('lmtPrice', 0), **kwargs)
    elif order_type == 'STP':
        return StopOrder(action, quantity, kwargs.get('stopPrice', 0), **kwargs)
    else:
        order = Order()  # Consider using MarketOrder/LimitOrder/etc.
        order.action = action
        order.totalQuantity = quantity
        order.orderType = order_type
        for key, value in kwargs.items():
            setattr(order, key, value)
        return order

print("✅ IB_INSYNC Adapter loaded - IBAPI compatibility enabled")
'''

# ==============================================================================
# COMMAND-LINE INTERFACE
# ==============================================================================

def main():
    """Main entry point for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="IBAPI to ib_insync Migration Tool"
    )
    parser.add_argument(
        'path',
        nargs='?',
        default='.',
        help='Path to Spyder project root (default: current directory)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be changed without modifying files'
    )
    parser.add_argument(
        '--restore',
        action='store_true',
        help='Restore from the latest backup'
    )
    parser.add_argument(
        '--create-adapter',
        help='Create compatibility adapter module at specified path'
    )
    
    args = parser.parse_args()
    
    if args.create_adapter:
        # Create adapter module
        adapter_content = create_ibinsync_adapter()
        with open(args.create_adapter, 'w') as f:
            f.write(adapter_content)
        print(f"✅ Adapter module created: {args.create_adapter}")
        return
    
    # Create migrator
    migrator = IBAPIMigrator(args.path)
    
    if args.restore:
        # Restore from backup
        migrator.restore_backup()
    else:
        # Run migration
        report = migrator.migrate_all(dry_run=args.dry_run)
        
        if args.dry_run:
            print("\n⚠️  This was a DRY RUN - no files were modified")
            print("   Remove --dry-run flag to apply changes")

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

if __name__ == "__main__":
    main()
else:
    print("✅ IBAPI → ib_insync Migration Tool loaded")