#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: temp_SpyderQuickFix.py
Purpose: Quick fix script for specific launch errors
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-23 Time: 15:30:00

Module Description:
    This script specifically addresses the known errors from the launch log:
    1. EventManager 'get' attribute error
    2. SpyderTradingDashboard constructor issue
    3. Missing SpyderH modules
    4. Risk manager initialization problem
    
    Run this before the full diagnostic to quickly identify and suggest fixes.
"""

import sys
import os
import importlib
import traceback
import inspect
from pathlib import Path
from typing import Dict, List, Any, Optional

# ==============================================================================
# SETUP
# ==============================================================================

# Add project root to path
SPYDER_ROOT = Path(__file__).parent.parent if Path(__file__).parent.name.startswith('SpyderT') else Path(__file__).parent
sys.path.insert(0, str(SPYDER_ROOT))

class QuickFixTester:
    """Quick fix tester for known issues"""
    
    def __init__(self):
        self.fixes_needed = []
        self.fixes_applied = []
        self.spyder_root = SPYDER_ROOT
        
        print("🔧 SPYDER QUICK FIX - TARGETED ERROR RESOLUTION")
        print("=" * 60)
        print(f"Spyder Root: {self.spyder_root}")
        print()

    def print_status(self, test_name: str, status: str, message: str = "", fix: str = ""):
        """Print formatted status message"""
        symbols = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️", "FIX": "🔧"}
        symbol = symbols.get(status, "❓")
        print(f"{symbol} {test_name}: {message}")
        if fix:
            print(f"   🔧 Fix: {fix}")
        print()

    def test_eventmanager_get_method(self):
        """Test EventManager missing 'get' method issue"""
        print("1️⃣ TESTING: EventManager 'get' method issue")
        print("-" * 50)
        
        try:
            from SpyderA_Core.SpyderA05_EventManager import EventManager
            
            # Check if EventManager has 'get' method
            if hasattr(EventManager, 'get'):
                self.print_status("EventManager.get()", "PASS", "Method exists")
            else:
                self.print_status("EventManager.get()", "FAIL", "Method missing", 
                                "Add get() method to EventManager class or fix code that calls .get()")
                
                # Check what methods it actually has
                methods = [m for m in dir(EventManager) if not m.startswith('_') and callable(getattr(EventManager, m, None))]
                print(f"   Available methods: {', '.join(methods[:10])}")
                if len(methods) > 10:
                    print(f"   ... and {len(methods) - 10} more")
                
                self.fixes_needed.append({
                    'issue': 'EventManager missing get() method',
                    'file': 'SpyderA05_EventManager.py',
                    'fix': 'Add get() method or update RiskManager to use proper EventManager API'
                })
            
            # Test EventManager instantiation
            try:
                em = EventManager(persist_events=False)
                self.print_status("EventManager Creation", "PASS", "Instance created")
                
                # Test if it has the expected interface
                expected_methods = ['start', 'stop', 'emit', 'subscribe']
                missing_methods = []
                for method in expected_methods:
                    if not hasattr(em, method):
                        missing_methods.append(method)
                
                if missing_methods:
                    self.print_status("EventManager Interface", "WARN", 
                                    f"Missing methods: {', '.join(missing_methods)}")
                else:
                    self.print_status("EventManager Interface", "PASS", "All expected methods present")
                    
                # Test start/stop briefly (with timeout protection)
                try:
                    if hasattr(em, 'start') and em.start():
                        self.print_status("EventManager Start", "PASS", "Started successfully")
                        # Don't test stop here to avoid hanging
                    else:
                        self.print_status("EventManager Start", "FAIL", "Failed to start")
                except Exception as e:
                    self.print_status("EventManager Start", "FAIL", f"Start error: {str(e)[:50]}")
                    
            except Exception as e:
                self.print_status("EventManager Creation", "FAIL", str(e)[:100])
                
        except ImportError as e:
            self.print_status("EventManager Import", "FAIL", str(e), 
                            "Fix EventManager import issues")

    def test_trading_dashboard_constructor(self):
        """Test SpyderTradingDashboard constructor issue"""
        print("2️⃣ TESTING: SpyderTradingDashboard constructor issue")
        print("-" * 50)
        
        try:
            # First check if PyQt6 is available
            from PySide6.QtWidgets import QApplication, QWidget
            
            # Create QApplication if needed
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            # Test the actual TradingDashboard
            from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
            
            # Check constructor signature
            sig = inspect.signature(SpyderTradingDashboard.__init__)
            params = list(sig.parameters.keys())
            
            self.print_status("TradingDashboard Import", "PASS", "Successfully imported")
            print(f"   Constructor parameters: {params}")
            print(f"   Full signature: {sig}")
            
            # The issue from the log: "takes 1 positional argument but 2 were given"
            # This means __init__(self) but something is trying to pass __init__(self, something)
            
            # Try to create instance with different parameter combinations
            creation_attempts = [
                ("No arguments", lambda: SpyderTradingDashboard()),
                ("With parent=None", lambda: SpyderTradingDashboard(parent=None)),
                ("With None argument", lambda: SpyderTradingDashboard(None))
            ]
            
            for attempt_name, creation_func in creation_attempts:
                try:
                    dashboard = creation_func()
                    self.print_status("TradingDashboard Creation", "PASS", 
                                    f"Success with: {attempt_name}")
                    break
                except TypeError as te:
                    self.print_status("TradingDashboard Creation", "FAIL", 
                                    f"{attempt_name}: {str(te)[:100]}")
                    
                    if "takes 1 positional argument but 2 were given" in str(te):
                        self.fixes_needed.append({
                            'issue': 'SpyderA01_Main is passing arguments to SpyderTradingDashboard constructor',
                            'file': 'SpyderA01_Main.py',
                            'fix': 'Change SpyderTradingDashboard(parent) to SpyderTradingDashboard() - it takes no parameters'
                        })
                        
                        # Also check if it should accept parent parameter
                        self.fixes_needed.append({
                            'issue': 'SpyderTradingDashboard constructor should accept parent parameter',
                            'file': 'SpyderG05_TradingDashboard.py',
                            'fix': 'Change def __init__(self): to def __init__(self, parent=None):'
                        })
                except Exception as e:
                    self.print_status("TradingDashboard Creation", "FAIL", 
                                    f"{attempt_name}: {str(e)[:100]}")
                    
            # Also test the bridge
            try:
                from SpyderG_GUI.SpyderG01_MainWindow import MainWindow
                sig = inspect.signature(MainWindow.__init__)
                print(f"   MainWindow signature: {sig}")
                
                window = MainWindow()
                self.print_status("MainWindow (Bridge)", "PASS", "Bridge works")
            except Exception as e:
                self.print_status("MainWindow (Bridge)", "FAIL", f"Bridge issue: {str(e)[:50]}")
            
        except ImportError as e:
            self.print_status("TradingDashboard Import", "FAIL", str(e),
                            "Fix SpyderG05_TradingDashboard import or create missing file")

    def test_missing_spyderh_modules(self):
        """Test missing SpyderH storage modules"""
        print("3️⃣ TESTING: Missing SpyderH storage modules")
        print("-" * 50)
        
        missing_modules = [
            ('SpyderH_Storage.SpyderH02_TradeRepository', 'Trade data repository'),
            ('SpyderH_Storage.SpyderH03_MarketDataCache', 'Market data caching'),
            ('SpyderH_Storage.SpyderH07_PerformanceAnalytics', 'Performance analytics')
        ]
        
        for module_name, description in missing_modules:
            try:
                module = importlib.import_module(module_name)
                self.print_status(f"{module_name.split('.')[-1]}", "PASS", "Available")
            except ImportError:
                self.print_status(f"{module_name.split('.')[-1]}", "FAIL", "Missing", 
                                f"Create {module_name.replace('.', '/')} or create stub")
                
                self.fixes_needed.append({
                    'issue': f'Missing {module_name}',
                    'file': f'{module_name.replace(".", "/")}.py',
                    'fix': f'Create missing module for {description}'
                })

    def test_risk_manager_initialization(self):
        """Test RiskManager initialization issue"""
        print("4️⃣ TESTING: RiskManager initialization issue")  
        print("-" * 50)
        
        try:
            from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
            from SpyderA_Core.SpyderA05_EventManager import EventManager
            
            # Create EventManager first
            em = EventManager(persist_events=False)
            
            # The error from log: "'EventManager' object has no attribute 'get'"
            # This means RiskManager is trying to call em.get() but EventManager doesn't have that method
            
            # Check what RiskManager constructor expects
            sig = inspect.signature(RiskManager.__init__)
            print(f"   RiskManager constructor: {sig}")
            
            # Test different RiskManager initialization patterns
            init_attempts = [
                ("Basic config dict", lambda: RiskManager(event_manager=em, config={'portfolio_value': 100000})),
                ("No config", lambda: RiskManager(event_manager=em)),
                ("Just event manager", lambda: RiskManager(em))
            ]
            
            for attempt_name, init_func in init_attempts:
                try:
                    risk_manager = init_func()
                    self.print_status("RiskManager Creation", "PASS", 
                                    f"Success with: {attempt_name}")
                    break
                except Exception as e:
                    error_msg = str(e)
                    self.print_status("RiskManager Creation", "FAIL", 
                                    f"{attempt_name}: {error_msg[:100]}")
                    
                    if "'EventManager' object has no attribute 'get'" in error_msg:
                        self.fixes_needed.append({
                            'issue': 'RiskManager expects EventManager.get() method',
                            'file': 'SpyderE01_RiskManager.py',
                            'fix': 'Update RiskManager to use proper EventManager API (emit, subscribe) instead of get()'
                        })
                        
                        # Also suggest adding get() method to EventManager
                        self.fixes_needed.append({
                            'issue': 'EventManager missing get() method expected by RiskManager',
                            'file': 'SpyderA05_EventManager.py', 
                            'fix': 'Add get() method to EventManager or update RiskManager code'
                        })
                        
        except ImportError as e:
            self.print_status("RiskManager Import", "FAIL", str(e))

    def test_broker_client_config_issue(self):
        """Test broker client configuration issue"""
        print("5️⃣ TESTING: Broker client configuration issue")
        print("-" * 50)
        
        # The error from log: "'dict' object has no attribute 'market_data_type'"
        # This means BrokerClient expects a config object with attributes, not a dict
        
        try:
            from SpyderB_Broker.SpyderB04_AccountManager import AccountManager
            self.print_status("AccountManager Import", "PASS", "Available (only working broker module)")
            
            # Try to import the missing broker client
            try:
                from SpyderB_Broker.SpyderB01_BrokerClient import BrokerClient
                
                if hasattr(BrokerClient, '__init__'):
                    sig = inspect.signature(BrokerClient.__init__)
                    print(f"   BrokerClient signature: {sig}")
                
                self.print_status("BrokerClient Import", "PASS", "Available")
                
                self.fixes_needed.append({
                    'issue': 'BrokerClient expects config object with attributes, not dict',
                    'file': 'SpyderA01_Main.py',
                    'fix': 'Create proper config object instead of dict, or update BrokerClient to handle dict configs'
                })
                    
            except ImportError:
                self.print_status("BrokerClient Import", "FAIL", "Missing - will run in simulation mode")
            
        except ImportError as e:
            self.print_status("AccountManager Import", "FAIL", str(e))

    def generate_fix_suggestions(self):
        """Generate specific fix suggestions"""
        print("🔧 FIX SUGGESTIONS")
        print("=" * 60)
        
        if not self.fixes_needed:
            print("✅ No specific fixes needed based on quick tests!")
            return True
        
        print(f"Found {len(self.fixes_needed)} issues that need fixing:\n")
        
        for i, fix in enumerate(self.fixes_needed, 1):
            print(f"{i}. {fix['issue']}")
            print(f"   File: {fix['file']}")
            print(f"   Fix: {fix['fix']}")
            print()
        
        print("🎯 PRIORITY ORDER FOR FIXES:")
        print("1. Fix EventManager stop() method (prevents hanging)")
        print("2. Fix EventManager get() method or RiskManager usage")
        print("3. Fix SpyderTradingDashboard constructor call in SpyderA01_Main.py")
        print("4. Create missing SpyderH modules or stubs") 
        print("5. Fix BrokerClient configuration handling")
        
        return False

    def create_emergency_stubs(self):
        """Create emergency stub modules for missing components"""
        print("\n🚨 CREATING EMERGENCY STUBS")
        print("-" * 40)
        
        stub_modules = [
            ('SpyderH_Storage/SpyderH02_TradeRepository.py', '''#!/usr/bin/env python3
"""Emergency stub for SpyderH02_TradeRepository"""

class TradeRepository:
    def __init__(self, *args, **kwargs):
        pass
    
    def save_trade(self, *args, **kwargs):
        pass
    
    def get_trades(self, *args, **kwargs):
        return []
'''),
            ('SpyderH_Storage/SpyderH03_MarketDataCache.py', '''#!/usr/bin/env python3
"""Emergency stub for SpyderH03_MarketDataCache"""

class MarketDataCache:
    def __init__(self, *args, **kwargs):
        pass
    
    def get(self, *args, **kwargs):
        return None
    
    def set(self, *args, **kwargs):
        pass
'''),
            ('SpyderH_Storage/SpyderH07_PerformanceAnalytics.py', '''#!/usr/bin/env python3
"""Emergency stub for SpyderH07_PerformanceAnalytics"""

class PerformanceAnalytics:
    def __init__(self, *args, **kwargs):
        pass
    
    def calculate(self, *args, **kwargs):
        return {}
''')
        ]
        
        for file_path, content in stub_modules:
            full_path = self.spyder_root / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not full_path.exists():
                try:
                    with open(full_path, 'w') as f:
                        f.write(content)
                    self.print_status("Stub Created", "PASS", f"Created {file_path}")
                    self.fixes_applied.append(f"Created stub: {file_path}")
                except Exception as e:
                    self.print_status("Stub Creation", "FAIL", f"Failed to create {file_path}: {e}")
            else:
                self.print_status("Stub Exists", "INFO", f"{file_path} already exists")

    def run_quick_fix(self):
        """Run complete quick fix sequence"""
        try:
            self.test_eventmanager_get_method()
            self.test_trading_dashboard_constructor()
            self.test_missing_spyderh_modules()
            self.test_risk_manager_initialization()
            self.test_broker_client_config_issue()
            
            success = self.generate_fix_suggestions()
            
            # Offer to create stubs
            if not success and self.fixes_needed:
                print("\n" + "="*60)
                create_stubs = input("Create emergency stub modules? (y/N): ").lower().strip()
                if create_stubs == 'y':
                    self.create_emergency_stubs()
            
            return success
            
        except Exception as e:
            print(f"❌ Quick fix failed: {e}")
            print(traceback.format_exc())
            return False

def main():
    """Main execution"""
    if len(sys.argv) > 1 and sys.argv[1] == "--create-stubs":
        # Just create stubs and exit
        fixer = QuickFixTester()
        fixer.create_emergency_stubs()
        return True
    
    fixer = QuickFixTester()
    return fixer.run_quick_fix()

if __name__ == "__main__":
    print("🚀 Starting Spyder Quick Fix...")
    success = main()
    
    if success:
        print("\n✅ Quick fix completed - Ready for launch!")
    else:
        print("\n⚠️ Issues found - Please apply suggested fixes before launching")
        print("\nRun again with --create-stubs to create emergency stub modules")
    
    print("\n💡 Next step: Apply fixes and run the full diagnostic or try launching again")
    sys.exit(0 if success else 1)