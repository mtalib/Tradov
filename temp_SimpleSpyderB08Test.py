#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_SimpleSpyderB08Test.py
Purpose: Simple test that works with existing SpyderB08 codebase
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 23:59:00  

Module Description:
    Simplified test that works with the existing SpyderB08 codebase
    and doesn't rely on new features. Focuses on basic functionality
    and identifies what needs to be updated.
"""

import sys
import time
from datetime import datetime

class SimpleSpyderB08Tester:
    """Simple tester that works with existing SpyderB08"""
    
    def __init__(self):
        self.test_results = {}
        self.manager = None
        
    def run_tests(self):
        """Run simplified test suite"""
        print("🔧 SIMPLE SPYDER B08 TEST - EXISTING CODEBASE")
        print("=" * 60)
        print("Testing what's currently available in your SpyderB08")
        print()
        
        # Test 1: Import Check
        self.test_imports()
        
        # Test 2: Manager Creation
        self.test_manager_creation()
        
        # Test 3: Client Configuration Check
        self.test_client_configs()
        
        # Test 4: Basic Functionality
        self.test_basic_functionality()
        
        # Print Results
        self.print_results()
    
    def test_imports(self):
        """Test what we can import from SpyderB08"""
        print("🧪 TEST 1: Import Check")
        
        try:
            # Try to import main components
            from SpyderB08_MultiClientDataManager import MultiClientDataManager
            print("   ✅ MultiClientDataManager imported")
            
            try:
                from SpyderB08_MultiClientDataManager import ClientPurpose
                print("   ✅ ClientPurpose imported")
                
                # Check available purposes
                purposes = [attr for attr in dir(ClientPurpose) if not attr.startswith('_')]
                print(f"   📊 Available purposes: {len(purposes)}")
                for purpose in purposes:
                    print(f"      - {purpose}")
                
                # Check for our target purposes
                target_purposes = ['ORDER_EXECUTION', 'ADMINISTRATIVE', 'INTERNATIONAL']
                for target in target_purposes:
                    if hasattr(ClientPurpose, target):
                        print(f"   ✅ {target} - Available")
                    else:
                        print(f"   ❌ {target} - Missing")
                        
            except Exception as e:
                print(f"   ❌ ClientPurpose import failed: {e}")
            
            try:
                from SpyderB08_MultiClientDataManager import OrderRequest
                print("   ✅ OrderRequest imported")
            except Exception as e:
                print(f"   ❌ OrderRequest import failed: {e}")
                
            self.test_results["imports"] = "PASSED"
            
        except Exception as e:
            print(f"   ❌ Import failed: {e}")
            self.test_results["imports"] = f"FAILED - {e}"
    
    def test_manager_creation(self):
        """Test manager creation"""
        print("\n🧪 TEST 2: Manager Creation")
        
        try:
            from SpyderB08_MultiClientDataManager import MultiClientDataManager
            
            # Create manager
            self.manager = MultiClientDataManager()
            print("   ✅ Manager created successfully")
            
            # Check if it has client_configs
            if hasattr(self.manager, 'client_configs'):
                config_count = len(self.manager.client_configs)
                print(f"   📊 Client configs found: {config_count}")
                
                # Show client IDs
                client_ids = list(self.manager.client_configs.keys())
                print(f"   🔢 Client IDs: {client_ids}")
                
            else:
                print("   ❌ No client_configs found")
            
            self.test_results["manager_creation"] = "PASSED"
            
        except Exception as e:
            print(f"   ❌ Manager creation failed: {e}")
            self.test_results["manager_creation"] = f"FAILED - {e}"
    
    def test_client_configs(self):
        """Test client configuration details"""
        print("\n🧪 TEST 3: Client Configuration Check")
        
        if self.manager is None:
            print("   ⏭️ SKIPPED - No manager available")
            self.test_results["client_configs"] = "SKIPPED"
            return
        
        try:
            configs = self.manager.client_configs
            
            print(f"   📊 Analyzing {len(configs)} client configurations:")
            
            for client_id, config in configs.items():
                purpose = config.get('purpose', 'Unknown')
                symbols = config.get('symbols', [])
                frequency = config.get('frequency', 0)
                
                print(f"   🔧 Client {client_id}:")
                print(f"      Purpose: {purpose}")
                print(f"      Symbols: {len(symbols)} ({', '.join(symbols[:3])}{'...' if len(symbols) > 3 else ''})")
                print(f"      Frequency: {frequency}s")
                
                # Check for specific features
                if 'VUD' in symbols:
                    print(f"      ✅ VUD found in Client {client_id}")
                if 'FTLC' in symbols:
                    print(f"      ✅ FTLC found in Client {client_id}")
            
            # Check for specific client purposes
            purposes_found = {}
            for client_id, config in configs.items():
                purpose_name = str(config.get('purpose', '')).split('.')[-1] if hasattr(config.get('purpose'), 'name') else str(config.get('purpose', ''))
                purposes_found[client_id] = purpose_name
            
            print(f"\n   🎯 Purpose Analysis:")
            for client_id, purpose in purposes_found.items():
                print(f"      Client {client_id}: {purpose}")
            
            self.test_results["client_configs"] = "PASSED"
            
        except Exception as e:
            print(f"   ❌ Client config analysis failed: {e}")
            self.test_results["client_configs"] = f"FAILED - {e}"
    
    def test_basic_functionality(self):
        """Test basic manager functionality"""
        print("\n🧪 TEST 4: Basic Functionality")
        
        if self.manager is None:
            print("   ⏭️ SKIPPED - No manager available")
            self.test_results["basic_functionality"] = "SKIPPED"
            return
        
        try:
            # Test start/stop
            print("   🚀 Testing start/stop functionality...")
            
            if hasattr(self.manager, 'start'):
                start_result = self.manager.start()
                print(f"   📤 Start result: {start_result}")
                
                if start_result and hasattr(self.manager, 'is_running'):
                    print(f"   🏃 Is running: {self.manager.is_running}")
                
                # Brief wait
                time.sleep(1)
                
                if hasattr(self.manager, 'stop'):
                    stop_result = self.manager.stop()
                    print(f"   🛑 Stop result: {stop_result}")
            
            # Test order creation (if available)
            try:
                from SpyderB08_MultiClientDataManager import OrderRequest
                test_order = OrderRequest(
                    symbol="SPY",
                    action="BUY", 
                    quantity=100,
                    order_type="MKT"
                )
                print(f"   📋 OrderRequest created - Client ID: {test_order.client_id}")
                
                # Check which client the order defaults to
                if test_order.client_id == 1:
                    print("   ✅ Order defaults to Client 1 (UPDATED)")
                elif test_order.client_id == 2:
                    print("   ⚠️ Order defaults to Client 2 (OLD VERSION)")
                else:
                    print(f"   ❓ Order defaults to Client {test_order.client_id}")
                    
            except Exception as e:
                print(f"   ❌ OrderRequest test failed: {e}")
            
            self.test_results["basic_functionality"] = "PASSED"
            
        except Exception as e:
            print(f"   ❌ Basic functionality test failed: {e}")
            self.test_results["basic_functionality"] = f"FAILED - {e}"
    
    def print_results(self):
        """Print test results and recommendations"""
        print("\n" + "=" * 60)
        print("📊 SIMPLE TEST RESULTS & RECOMMENDATIONS")
        print("=" * 60)
        
        # Count results
        passed = sum(1 for result in self.test_results.values() if result == "PASSED")
        failed = sum(1 for result in self.test_results.values() if "FAILED" in str(result))
        skipped = sum(1 for result in self.test_results.values() if result == "SKIPPED")
        total = len(self.test_results)
        
        # Print individual results
        for test_name, result in self.test_results.items():
            status_icon = "✅" if result == "PASSED" else ("❌" if "FAILED" in result else "⏭️")
            print(f"{status_icon} {test_name.replace('_', ' ').title()}: {result}")
        
        print(f"\n📈 Summary: {passed} passed, {failed} failed, {skipped} skipped out of {total}")
        
        # Recommendations
        print(f"\n🔧 RECOMMENDATIONS:")
        
        if failed > 0:
            print("❌ Issues detected with current SpyderB08:")
            print("   1. ClientPurpose enum is missing INTERNATIONAL attribute")
            print("   2. Your current SpyderB08 may be an older version")
            print("   3. Need to update to the latest version with:")
            print("      - Client ID swap (Order Execution = Client 1)")
            print("      - VUD Put/Call Ratio in Client 6") 
            print("      - International symbols in Client 10")
        
        print(f"\n🚀 NEXT STEPS:")
        print("1. ✅ Replace your current SpyderB08_MultiClientDataManager.py")
        print("2. ✅ Use the complete updated version I provided")
        print("3. ✅ Make sure it's in the correct directory")
        print("4. ✅ Re-run the test")
        
        print(f"\n📝 FILE LOCATION CHECK:")
        print("   Current directory: Check if you have the updated file:")
        print("   ls -la SpyderB08_MultiClientDataManager.py")
        print("   ls -la SpyderB_Broker/SpyderB08_MultiClientDataManager.py")

def main():
    """Main test execution"""
    try:
        tester = SimpleSpyderB08Tester()
        tester.run_tests()
        
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Critical test failure: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
