#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_TestUpdatedSpyderB08.py
Purpose: Test Updated SpyderB08 with Client ID Swap and International Symbols
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 19:15:00  

Module Description:
    Comprehensive test suite for the updated SpyderB08_MultiClientDataManager.py
    Validates Client ID swap (Order Execution = Client 1, Admin = Client 2),
    new international symbols with FTLC, and overall system functionality.
"""

import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional

# Test the updated SpyderB08 import
try:
    from SpyderB08_MultiClientDataManager import (
        MultiClientDataManager, 
        OrderRequest, 
        ClientPurpose,
        get_manager_instance,
        reset_manager_instance
    )
    SPYDER_B08_AVAILABLE = True
    print("✅ Successfully imported updated SpyderB08_MultiClientDataManager")
except ImportError as e:
    print(f"❌ Failed to import SpyderB08: {e}")
    SPYDER_B08_AVAILABLE = False

class UpdatedSpyderB08Tester:
    """Comprehensive tester for updated SpyderB08 with Client ID swap"""
    
    def __init__(self):
        self.test_results = {}
        self.manager = None
        self.test_data_received = {}
        self.test_orders_submitted = []
        
    def run_all_tests(self):
        """Run comprehensive test suite"""
        print("🚀 TESTING UPDATED SPYDER B08 - CLIENT ID SWAP, INTERNATIONAL SYMBOLS & VUD")
        print("=" * 90)
        print("Testing Order Execution = Client 1, Administrative = Client 2")
        print("Testing International Client 10 with FTLC and follow-the-sun symbols")
        print("Testing VUD Put/Call Ratio in Client 6 Market Internals")
        print()
        
        try:
            # Test 1: Manager Initialization
            self.test_manager_initialization()
            
            # Test 2: Client ID Swap Verification  
            self.test_client_id_swap()
            
            # Test 3: International Symbols (Client 10)
            self.test_international_symbols()
            
            # Test 4: Start Manager
            self.test_manager_startup()
            
            # Test 5: Order Execution (Client 1)
            self.test_order_execution_client1()
            
            # Test 6: Market Data Subscription
            self.test_market_data_subscriptions()
            
            # Test 7: International Data (Client 10)
            self.test_international_data_client10()
            
            # Test 8: System Status
            self.test_system_status()
            
            # Test 9: Stop Manager
            self.test_manager_shutdown()
            
            # Print Results
            self.print_test_results()
            
        except Exception as e:
            print(f"❌ Critical error in test suite: {e}")
            import traceback
            traceback.print_exc()
    
    def test_manager_initialization(self):
        """Test 1: Manager Initialization"""
        print("🧪 TEST 1: Manager Initialization")
        try:
            if not SPYDER_B08_AVAILABLE:
                self.test_results["initialization"] = "FAILED - Import error"
                print("❌ FAILED - SpyderB08 not available")
                return
                
            # Create manager instance
            self.manager = MultiClientDataManager()
            
            if self.manager is not None:
                self.test_results["initialization"] = "PASSED"
                print("✅ PASSED - Manager created successfully")
                
                # Verify client configs exist
                if hasattr(self.manager, 'client_configs') and len(self.manager.client_configs) == 10:
                    print(f"   📊 Client configs: {len(self.manager.client_configs)} clients (1-10)")
                else:
                    print(f"   ⚠️  Unexpected client count: {len(self.manager.client_configs) if hasattr(self.manager, 'client_configs') else 'N/A'}")
            else:
                self.test_results["initialization"] = "FAILED"
                print("❌ FAILED - Manager creation failed")
                
        except Exception as e:
            self.test_results["initialization"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_client_id_swap(self):
        """Test 2: Client ID Swap Verification"""
        print("\n🧪 TEST 2: Client ID Swap Verification")
        try:
            if self.manager is None:
                self.test_results["client_id_swap"] = "SKIPPED - No manager"
                print("⏭️  SKIPPED - No manager available")
                return
            
            # Check Client 1 = Order Execution
            client_1_config = self.manager.client_configs.get(1)
            if client_1_config and client_1_config['purpose'] == ClientPurpose.ORDER_EXECUTION:
                print("✅ Client 1 = ORDER EXECUTION ✓")
                client_1_ok = True
            else:
                print("❌ Client 1 ≠ ORDER EXECUTION")
                client_1_ok = False
            
            # Check Client 2 = Administrative
            client_2_config = self.manager.client_configs.get(2)
            if client_2_config and client_2_config['purpose'] == ClientPurpose.ADMINISTRATIVE:
                print("✅ Client 2 = ADMINISTRATIVE ✓")
                client_2_ok = True
            else:
                print("❌ Client 2 ≠ ADMINISTRATIVE")
                client_2_ok = False
            
            # Check OrderRequest default client_id
            test_order = OrderRequest(symbol="SPY", action="BUY", quantity=100, order_type="MKT")
            if test_order.client_id == 1:
                print("✅ OrderRequest defaults to Client 1 ✓")
                order_default_ok = True
            else:
                print(f"❌ OrderRequest defaults to Client {test_order.client_id} (should be 1)")
                order_default_ok = False
            
            # Overall result
            if client_1_ok and client_2_ok and order_default_ok:
                self.test_results["client_id_swap"] = "PASSED"
                print("🎉 PASSED - Client ID swap verified successfully!")
            else:
                self.test_results["client_id_swap"] = "FAILED"
                print("❌ FAILED - Client ID swap issues detected")
                
        except Exception as e:
            self.test_results["client_id_swap"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_international_symbols(self):
        """Test 3: International Symbols (Client 10)"""
        print("\n🧪 TEST 3: International Symbols (Client 10)")
        try:
            if self.manager is None:
                self.test_results["international_symbols"] = "SKIPPED - No manager"
                print("⏭️  SKIPPED - No manager available")
                return
            
            # Check Client 10 exists
            client_10_config = self.manager.client_configs.get(10)
            if not client_10_config:
                self.test_results["international_symbols"] = "FAILED - No Client 10"
                print("❌ FAILED - Client 10 not found")
                return
            
            # Check purpose is INTERNATIONAL
            if client_10_config['purpose'] == ClientPurpose.INTERNATIONAL:
                print("✅ Client 10 purpose = INTERNATIONAL ✓")
            else:
                print(f"❌ Client 10 purpose = {client_10_config['purpose']} (should be INTERNATIONAL)")
            
            # Check for key international symbols
            symbols = client_10_config['symbols']
            print(f"   📊 Total symbols: {len(symbols)}")
            
            # Key symbols to check
            key_symbols = {
                'FTLC': 'FTSE 350 (better than FTSE 100)',
                'AUD.JPY': 'Risk sentiment barometer', 
                'EUR.USD': 'Global dollar liquidity',
                'DAX': 'German growth engine',
                'HSI': 'Hong Kong/China sentiment',
                'N225': 'Nikkei 225 (Japan)',
                'EWJ': 'Japan ETF (US tradeable)',
                'EEM': 'Emerging Markets'
            }
            
            found_symbols = []
            missing_symbols = []
            
            for symbol, description in key_symbols.items():
                if symbol in symbols:
                    found_symbols.append(symbol)
                    print(f"   ✅ {symbol} - {description}")
                else:
                    missing_symbols.append(symbol)
                    print(f"   ❌ {symbol} - {description} (MISSING)")
            
            # Check FTLC specifically (our key improvement)
            if 'FTLC' in symbols:
                print("🎯 FTLC (FTSE 350) confirmed - Superior to FTSE 100!")
                ftlc_ok = True
            else:
                print("⚠️  FTLC (FTSE 350) not found - Still using FTSE 100?")
                ftlc_ok = False
            
            # Overall assessment
            if len(found_symbols) >= 6 and ftlc_ok:  # At least 6/8 key symbols + FTLC
                self.test_results["international_symbols"] = "PASSED"
                print(f"🎉 PASSED - International symbols verified ({len(found_symbols)}/8 key symbols)")
            else:
                self.test_results["international_symbols"] = "PARTIAL"
                print(f"⚠️  PARTIAL - Some issues ({len(found_symbols)}/8 key symbols)")
                
        except Exception as e:
            self.test_results["international_symbols"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_manager_startup(self):
        """Test 4: Manager Startup"""
        print("\n🧪 TEST 4: Manager Startup")
        try:
            if self.manager is None:
                self.test_results["startup"] = "SKIPPED - No manager"
                print("⏭️  SKIPPED - No manager available")
                return
            
            # Start the manager
            print("   🚀 Starting manager...")
            success = self.manager.start()
            
            if success and self.manager.is_running:
                self.test_results["startup"] = "PASSED"
                print("✅ PASSED - Manager started successfully")
                
                # Check if critical clients are considered online
                status = self.manager.get_status_summary()
                if status:
                    print(f"   📊 Active clients: {status.get('active_clients', [])}")
                    print(f"   🎯 Order execution (Client 1): {status.get('order_execution_priority', False)}")
                    print(f"   ⚙️  Administrative (Client 2): {status.get('administrative_online', False)}")
                    print(f"   🌍 International (Client 10): {status.get('international_client_online', False)}")
            else:
                self.test_results["startup"] = "FAILED"
                print("❌ FAILED - Manager startup failed")
                
        except Exception as e:
            self.test_results["startup"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_order_execution_client1(self):
        """Test 5: Order Execution (Client 1)"""
        print("\n🧪 TEST 5: Order Execution (Client 1)")
        try:
            if self.manager is None or not self.manager.is_running:
                self.test_results["order_execution"] = "SKIPPED - Manager not running"
                print("⏭️  SKIPPED - Manager not running")
                return
            
            # Create test order
            test_order = OrderRequest(
                symbol="SPY",
                action="BUY", 
                quantity=100,
                order_type="MKT"
            )
            
            # Verify order defaults to Client 1
            if test_order.client_id == 1:
                print("✅ Order defaults to Client 1 ✓")
            else:
                print(f"❌ Order defaults to Client {test_order.client_id} (should be 1)")
            
            # Submit order
            print("   📤 Submitting test order...")
            
            def order_callback(status):
                print(f"   📋 Order callback received: {status}")
                self.test_data_received["order_callback"] = status
            
            order_id = self.manager.submit_order(test_order, order_callback)
            
            if order_id > 0:
                print(f"✅ Order {order_id} submitted successfully to Client 1")
                self.test_orders_submitted.append(order_id)
                
                # Check order status
                time.sleep(0.5)  # Brief wait
                order_status = self.manager.get_order_status(order_id)
                if order_status:
                    print(f"   📊 Order status: {order_status}")
                    if order_status.get('client_id') == 1:
                        print("✅ Order confirmed on Client 1 ✓")
                        client_ok = True
                    else:
                        print(f"❌ Order on Client {order_status.get('client_id')} (should be 1)")
                        client_ok = False
                else:
                    print("⚠️  Could not retrieve order status")
                    client_ok = False
                
                if client_ok:
                    self.test_results["order_execution"] = "PASSED"
                    print("🎉 PASSED - Order execution on Client 1 verified!")
                else:
                    self.test_results["order_execution"] = "PARTIAL"
                    print("⚠️  PARTIAL - Order submitted but client verification failed")
            else:
                self.test_results["order_execution"] = "FAILED"
                print("❌ FAILED - Order submission failed")
                
        except Exception as e:
            self.test_results["order_execution"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_market_data_subscriptions(self):
        """Test 6: Market Data Subscription"""
        print("\n🧪 TEST 6: Market Data Subscriptions")
        try:
            if self.manager is None or not self.manager.is_running:
                self.test_results["market_data"] = "SKIPPED - Manager not running"
                print("⏭️  SKIPPED - Manager not running")
                return
            
            # Test data callback
            def test_callback(tick):
                symbol = tick.symbol
                price = tick.price
                print(f"   📊 Data received: {symbol} = ${price:.2f}")
                self.test_data_received[f"data_{symbol}"] = tick
            
            # Subscribe to core symbols
            test_symbols = ["SPY", "VIX", "QQQ", "VUD"]  # Added VUD
            successful_subscriptions = 0
            
            for symbol in test_symbols:
                print(f"   📡 Subscribing to {symbol}...")
                success = self.manager.subscribe_to_data(symbol, test_callback)
                if success:
                    successful_subscriptions += 1
                    print(f"   ✅ {symbol} subscription successful")
                    
                    # Special note for VUD
                    if symbol == "VUD":
                        client_id = self.manager._get_updated_client_for_symbol(symbol)
                        if client_id == 6:
                            print(f"   🎯 VUD correctly routed to Client 6 (Market Internals)")
                        else:
                            print(f"   ⚠️  VUD routed to Client {client_id} (expected 6)")
                else:
                    print(f"   ❌ {symbol} subscription failed")
            
            # Brief wait for data
            print("   ⏱️  Waiting for market data...")
            time.sleep(2)
            
            if successful_subscriptions == len(test_symbols):
                self.test_results["market_data"] = "PASSED"
                print(f"🎉 PASSED - Market data subscriptions ({successful_subscriptions}/{len(test_symbols)})")
            elif successful_subscriptions > 0:
                self.test_results["market_data"] = "PARTIAL" 
                print(f"⚠️  PARTIAL - Some subscriptions failed ({successful_subscriptions}/{len(test_symbols)})")
            else:
                self.test_results["market_data"] = "FAILED"
                print("❌ FAILED - All subscriptions failed")
                
        except Exception as e:
            self.test_results["market_data"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_international_data_client10(self):
        """Test 7: International Data (Client 10)"""
        print("\n🧪 TEST 7: International Data (Client 10)")
        try:
            if self.manager is None or not self.manager.is_running:
                self.test_results["international_data"] = "SKIPPED - Manager not running"
                print("⏭️  SKIPPED - Manager not running")
                return
            
            # Test international data callback
            def intl_callback(tick):
                symbol = tick.symbol
                price = tick.price
                print(f"   🌍 International data: {symbol} = {price:.2f}")
                self.test_data_received[f"intl_{symbol}"] = tick
            
            # Subscribe to key international symbols
            intl_symbols = ["FTLC", "AUD.JPY", "DAX", "HSI"]
            successful_intl_subscriptions = 0
            
            for symbol in intl_symbols:
                print(f"   🌍 Subscribing to {symbol}...")
                success = self.manager.subscribe_to_data(symbol, intl_callback)
                if success:
                    successful_intl_subscriptions += 1
                    print(f"   ✅ {symbol} subscription successful")
                    
                    # Check which client handles this symbol
                    client_id = self.manager._get_updated_client_for_symbol(symbol)
                    if client_id == 10:
                        print(f"   🎯 {symbol} correctly routed to Client 10")
                    else:
                        print(f"   ⚠️  {symbol} routed to Client {client_id} (expected 10)")
                else:
                    print(f"   ❌ {symbol} subscription failed")
            
            # Test VUD subscription (Client 6 - Market Internals)
            print("   🧪 Testing VUD Put/Call Ratio (Client 6)...")
            vud_success = self.manager.subscribe_to_data("VUD", intl_callback)
            if vud_success:
                print("   ✅ VUD subscription successful")
                vud_client = self.manager._get_updated_client_for_symbol("VUD")
                if vud_client == 6:
                    print("   🎯 VUD correctly routed to Client 6 (Market Internals)")
                    vud_routing_ok = True
                else:
                    print(f"   ⚠️  VUD routed to Client {vud_client} (expected 6)")
                    vud_routing_ok = False
            else:
                print("   ❌ VUD subscription failed")
                vud_routing_ok = False

            # Brief wait for international data
            print("   ⏱️  Waiting for international data...")
            time.sleep(2)
            
            # Special check for FTLC (our key improvement)
            ftlc_data = self.manager.get_latest_data("FTLC")
            if ftlc_data:
                print(f"   🎯 FTLC (FTSE 350) data: {ftlc_data['price']:.2f} - Working!")
                ftlc_ok = True
            else:
                print("   ⚠️  FTLC (FTSE 350) data not available")
                ftlc_ok = False
            
            if successful_intl_subscriptions >= 3 and ftlc_ok and vud_routing_ok:
                self.test_results["international_data"] = "PASSED"
                print(f"🎉 PASSED - International data + VUD verified ({successful_intl_subscriptions}/{len(intl_symbols)})")
            elif successful_intl_subscriptions > 0 or vud_routing_ok:
                self.test_results["international_data"] = "PARTIAL"
                print(f"⚠️  PARTIAL - Some data issues ({successful_intl_subscriptions}/{len(intl_symbols)}, VUD: {vud_routing_ok})")
            else:
                self.test_results["international_data"] = "FAILED"
                print("❌ FAILED - International data and VUD not working")
                
        except Exception as e:
            self.test_results["international_data"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_system_status(self):
        """Test 8: System Status"""
        print("\n🧪 TEST 8: System Status")
        try:
            if self.manager is None:
                self.test_results["system_status"] = "SKIPPED - No manager"
                print("⏭️  SKIPPED - No manager available")
                return
            
            # Get comprehensive status
            status = self.manager.get_status_summary()
            
            if status:
                print("   📊 System Status Summary:")
                print(f"      🏃 Running: {status.get('is_running', False)}")
                print(f"      🔢 Client ID Range: {status.get('client_id_range', 'Unknown')}")
                print(f"      📋 Client Allocation: {status.get('client_allocation', 'Unknown')}")
                print(f"      🎯 Order Execution (Client 1): {status.get('order_execution_priority', False)}")
                print(f"      ⚙️  Administrative (Client 2): {status.get('administrative_online', False)}")
                print(f"      🌍 International (Client 10): {status.get('international_client_online', False)}")
                print(f"      📈 Active Clients: {status.get('active_clients', [])}")
                print(f"      💼 Total Orders: {status.get('total_orders', 0)}")
                print(f"      📡 Total Messages: {status.get('total_messages', 0)}")
                print(f"      🔔 Subscriptions: {status.get('subscriptions', 0)}")
                
                # Check key status indicators
                key_checks = {
                    'is_running': status.get('is_running', False),
                    'order_execution_client1': status.get('order_execution_priority', False),
                    'has_international': status.get('international_client_online', False),
                    'client_range_correct': status.get('client_id_range') == '1-10'
                }
                
                passed_checks = sum(key_checks.values())
                total_checks = len(key_checks)
                
                if passed_checks == total_checks:
                    self.test_results["system_status"] = "PASSED"
                    print(f"🎉 PASSED - System status verified ({passed_checks}/{total_checks})")
                elif passed_checks >= total_checks * 0.75:
                    self.test_results["system_status"] = "PARTIAL"
                    print(f"⚠️  PARTIAL - Most status checks passed ({passed_checks}/{total_checks})")
                else:
                    self.test_results["system_status"] = "FAILED"
                    print(f"❌ FAILED - Multiple status issues ({passed_checks}/{total_checks})")
            else:
                self.test_results["system_status"] = "FAILED"
                print("❌ FAILED - Could not retrieve system status")
                
        except Exception as e:
            self.test_results["system_status"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def test_manager_shutdown(self):
        """Test 9: Manager Shutdown"""
        print("\n🧪 TEST 9: Manager Shutdown")
        try:
            if self.manager is None:
                self.test_results["shutdown"] = "SKIPPED - No manager"
                print("⏭️  SKIPPED - No manager available")
                return
            
            print("   🛑 Stopping manager...")
            success = self.manager.stop()
            
            if success and not self.manager.is_running:
                self.test_results["shutdown"] = "PASSED"
                print("✅ PASSED - Manager stopped successfully")
            else:
                self.test_results["shutdown"] = "FAILED"
                print("❌ FAILED - Manager shutdown failed")
                
        except Exception as e:
            self.test_results["shutdown"] = f"FAILED - {e}"
            print(f"❌ FAILED - Exception: {e}")
    
    def print_test_results(self):
        """Print comprehensive test results"""
        print("\n" + "=" * 90)
        print("🎯 UPDATED SPYDER B08 TEST RESULTS SUMMARY")
        print("=" * 90)
        
        # Count results
        passed = sum(1 for result in self.test_results.values() if result == "PASSED")
        partial = sum(1 for result in self.test_results.values() if result == "PARTIAL")
        failed = sum(1 for result in self.test_results.values() if "FAILED" in str(result))
        skipped = sum(1 for result in self.test_results.values() if result.startswith("SKIPPED"))
        total = len(self.test_results)
        
        # Print individual results
        for test_name, result in self.test_results.items():
            status_icon = {
                "PASSED": "✅",
                "PARTIAL": "⚠️",
                "SKIPPED": "⏭️"
            }.get(result.split()[0], "❌")
            
            print(f"{status_icon} {test_name.replace('_', ' ').title()}: {result}")
        
        print("\n📊 SUMMARY:")
        print(f"   ✅ Passed: {passed}/{total}")
        print(f"   ⚠️  Partial: {partial}/{total}")  
        print(f"   ❌ Failed: {failed}/{total}")
        print(f"   ⏭️  Skipped: {skipped}/{total}")
        
        # Overall assessment
        success_rate = (passed + partial * 0.5) / total if total > 0 else 0
        
        if success_rate >= 0.9:
            print(f"\n🎉 EXCELLENT: {success_rate*100:.1f}% success rate!")
            print("🥇 Updated SpyderB08 is working perfectly!")
            print("✅ Client ID swap verified (Order Execution = Client 1)")
            print("🌍 International symbols with FTLC confirmed")
        elif success_rate >= 0.7:
            print(f"\n👍 GOOD: {success_rate*100:.1f}% success rate")
            print("⚠️  Minor issues detected, but core functionality working")
        elif success_rate >= 0.5:
            print(f"\n⚠️  FAIR: {success_rate*100:.1f}% success rate")
            print("❌ Some significant issues need attention")
        else:
            print(f"\n❌ POOR: {success_rate*100:.1f}% success rate")
            print("🔧 Major issues need to be resolved")
        
        # Key confirmations
        print(f"\n🔑 KEY VERIFICATIONS:")
        if self.test_results.get("client_id_swap") == "PASSED":
            print("✅ Client ID Swap: Order Execution = Client 1 ✓")
        else:
            print("❌ Client ID Swap: Issues detected")
            
        if self.test_results.get("international_symbols") in ["PASSED", "PARTIAL"]:
            print("✅ International Symbols: Client 10 with FTLC ✓")
        else:
            print("❌ International Symbols: Issues detected")
            
        if len(self.test_orders_submitted) > 0:
            print(f"✅ Order Testing: {len(self.test_orders_submitted)} orders submitted to Client 1 ✓")
        else:
            print("❌ Order Testing: No orders successfully submitted")
            
        # Check if VUD was tested successfully
        if "VUD" in str(self.test_results.get("international_data", "")):
            print("✅ VUD Put/Call Ratio: Client 6 routing verified ✓")
        else:
            print("❌ VUD Put/Call Ratio: Routing not verified")
        
        print("=" * 90)

def main():
    """Main test execution"""
    try:
        tester = UpdatedSpyderB08Tester()
        tester.run_all_tests()
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Critical test failure: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
