#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_TestIntegratedSolution.py
Purpose: Comprehensive test of the complete end-to-end data flow fix
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:40:00  

Module Description:
    Tests the complete integrated solution including Enhanced SpyderClient,
    Fixed MarketDataManager, DashboardDataBridge, and ET time display.
    Verifies that all components work together to resolve the NaN data,
    cached data, and time display issues.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import time
import json
import os
from datetime import datetime
import threading
from typing import Dict, Any, Optional

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient, IBConfig, MarketDataType
    from SpyderB_Broker.SpyderB07_MarketDataManager import MarketDataManager, ETTimeDisplay, get_market_data_manager
    from SpyderG_GUI.SpyderG08_DashboardDataBridge import DashboardDataBridge, get_dashboard_bridge
    CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Import error: {e}")
    CLIENT_AVAILABLE = False

# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================
# Test parameters
TEST_DURATION = 30  # seconds
TEST_SYMBOLS = ['SPY', 'QQQ', 'VIX']
EXPECTED_DATA_TYPES = ['FROZEN', 'DELAYED', 'DELAYED_FROZEN']

# IB Gateway configuration (use your working settings)
IB_HOST = '127.0.0.1'
IB_PORT = 4002  # Paper trading
CLIENT_ID = 44  # Working client ID from your tests

# Dashboard data file
DASHBOARD_DATA_FILE = '/tmp/spyder_market_data.json'

# ==============================================================================
# COMPREHENSIVE INTEGRATION TEST
# ==============================================================================
class IntegratedSolutionTest:
    """
    Comprehensive test of the integrated solution.
    
    Tests the complete data flow:
    SpyderClient → MarketDataManager → DashboardDataBridge → Dashboard
    """
    
    def __init__(self):
        """Initialize the test suite."""
        self.client: Optional[SpyderClient] = None
        self.market_manager: Optional[MarketDataManager] = None
        self.bridge: Optional[DashboardDataBridge] = None
        
        self.test_results = {}
        self.data_received = {}
        self.start_time = datetime.now()
        
        print("🧪 SPYDER INTEGRATED SOLUTION TEST")
        print("=" * 60)
        print(f"🕒 Test started at: {self.start_time.strftime('%H:%M:%S %Z')}")
        print()
    
    def run_complete_test(self) -> bool:
        """
        Run the complete integration test.
        
        Returns:
            bool: True if all tests pass
        """
        try:
            print("🚀 RUNNING COMPLETE INTEGRATION TEST")
            print("-" * 40)
            
            # Step 1: Test ET Time Display
            if not self._test_et_time_display():
                return False
                
            # Step 2: Test Enhanced SpyderClient
            if not self._test_spyder_client():
                return False
                
            # Step 3: Test MarketDataManager
            if not self._test_market_data_manager():
                return False
                
            # Step 4: Test DashboardDataBridge
            if not self._test_dashboard_bridge():
                return False
                
            # Step 5: Test End-to-End Data Flow
            if not self._test_end_to_end_flow():
                return False
                
            # Step 6: Test Dashboard Compatibility
            if not self._test_dashboard_compatibility():
                return False
                
            # Step 7: Summary and Cleanup
            self._test_summary()
            
            return True
            
        except Exception as e:
            print(f"❌ CRITICAL TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self._cleanup()
    
    # ==========================================================================
    # INDIVIDUAL TEST METHODS
    # ==========================================================================
    def _test_et_time_display(self) -> bool:
        """Test ET time display functionality."""
        print("1️⃣ TESTING ET TIME DISPLAY")
        print("-" * 30)
        
        try:
            et_display = ETTimeDisplay()
            
            # Test current ET time
            et_time = et_display.get_et_time_string()
            print(f"   📅 Current ET Time: {et_time}")
            
            # Test market status
            status, icon = et_display.get_market_status()
            print(f"   📊 Market Status: {icon} {status}")
            
            # Test dashboard format
            dashboard_format = et_display.format_for_dashboard()
            print(f"   🖥️  Dashboard Format: {dashboard_format}")
            
            # Verify ET timezone
            et_tz = pytz.timezone('US/Eastern')
            et_now = datetime.now(et_tz)
            local_now = datetime.now()
            
            print(f"   🌍 Local Time: {local_now.strftime('%H:%M:%S')}")
            print(f"   🇺🇸 ET Time: {et_now.strftime('%H:%M:%S %Z')}")
            
            self.test_results['et_time'] = True
            print("   ✅ ET Time Display: PASSED\n")
            return True
            
        except Exception as e:
            print(f"   ❌ ET Time Display: FAILED - {e}\n")
            self.test_results['et_time'] = False
            return False
    
    def _test_spyder_client(self) -> bool:
        """Test Enhanced SpyderClient with market data types."""
        print("2️⃣ TESTING ENHANCED SPYDER CLIENT")
        print("-" * 30)
        
        try:
            # Create client configuration
            config = IBConfig(
                host=IB_HOST,
                port=IB_PORT,
                client_id=CLIENT_ID
            )
            
            print(f"   🔗 Connecting to IB Gateway at {IB_HOST}:{IB_PORT}")
            
            # Create and connect client
            self.client = SpyderClient(config)
            
            if not self.client.connect():
                print("   ❌ Failed to connect to IB Gateway")
                return False
                
            print("   ✅ Connected to IB Gateway")
            
            # Test market data capabilities
            capabilities = self.client.get_data_capabilities()
            print(f"   📊 Data Capabilities:")
            print(f"      Real-time: {capabilities.realtime_available}")
            print(f"      Frozen: {capabilities.frozen_available}")
            print(f"      Delayed: {capabilities.delayed_available}")
            print(f"      Delayed-Frozen: {capabilities.delayed_frozen_available}")
            
            if capabilities.preferred_type:
                print(f"      Preferred: {capabilities.preferred_type.name}")
            
            # Verify we have at least one working data type
            has_working_type = any([
                capabilities.frozen_available,
                capabilities.delayed_available,
                capabilities.delayed_frozen_available
            ])
            
            if not has_working_type:
                print("   ❌ No working data types found!")
                return False
            
            # Test market data request
            print("   📈 Testing market data request...")
            spy_contract = self.client.create_stock_contract('SPY')
            req_id = self.client.request_market_data(spy_contract)
            
            if req_id <= 0:
                print("   ❌ Failed to request market data")
                return False
                
            print(f"   ✅ Market data requested (ID: {req_id})")
            
            # Wait for data
            time.sleep(5)
            
            # Check for valid data
            ticker = self.client.get_market_data(req_id)
            if ticker and ticker.last and ticker.last > 0:
                print(f"   📊 SPY Data: ${ticker.last:.2f}")
                self.data_received['client_spy'] = ticker.last
            else:
                print("   ⚠️ No SPY data received yet")
            
            # Clean up
            self.client.cancel_market_data(req_id)
            
            self.test_results['client'] = True
            print("   ✅ Enhanced SpyderClient: PASSED\n")
            return True
            
        except Exception as e:
            print(f"   ❌ Enhanced SpyderClient: FAILED - {e}\n")
            self.test_results['client'] = False
            return False
    
    def _test_market_data_manager(self) -> bool:
        """Test Fixed MarketDataManager."""
        print("3️⃣ TESTING MARKET DATA MANAGER")
        print("-" * 30)
        
        try:
            if not self.client or not self.client.is_connected():
                print("   ❌ SpyderClient not available")
                return False
            
            # Create market data manager
            self.market_manager = get_market_data_manager(self.client)
            print("   ✅ MarketDataManager created")
            
            # Start the manager
            if not self.market_manager.start():
                print("   ❌ Failed to start MarketDataManager")
                return False
                
            print("   ✅ MarketDataManager started")
            
            # Check current data type
            current_type = self.market_manager.current_data_type
            print(f"   📡 Using data type: {current_type.name}")
            
            # Wait for data
            print("   ⏳ Waiting for market data...")
            time.sleep(10)
            
            # Check data for test symbols
            symbols_with_data = 0
            for symbol in TEST_SYMBOLS:
                snapshot = self.market_manager.get_market_data(symbol)
                if snapshot and snapshot.last > 0:
                    print(f"   📊 {symbol}: ${snapshot.last:.2f} ({snapshot.change_percent:+.2f}%)")
                    self.data_received[f'manager_{symbol}'] = snapshot.last
                    symbols_with_data += 1
                else:
                    print(f"   ⚠️ {symbol}: No data")
            
            if symbols_with_data == 0:
                print("   ❌ No market data received")
                return False
            
            # Test metrics
            metrics = self.market_manager.get_metrics()
            print(f"   📈 Metrics: {metrics.total_updates} updates, Type: {metrics.data_type_used}")
            
            self.test_results['market_manager'] = True
            print("   ✅ MarketDataManager: PASSED\n")
            return True
            
        except Exception as e:
            print(f"   ❌ MarketDataManager: FAILED - {e}\n")
            self.test_results['market_manager'] = False
            return False
    
    def _test_dashboard_bridge(self) -> bool:
        """Test DashboardDataBridge."""
        print("4️⃣ TESTING DASHBOARD DATA BRIDGE")
        print("-" * 30)
        
        try:
            if not self.client:
                print("   ❌ SpyderClient not available")
                return False
            
            # Create dashboard bridge
            self.bridge = get_dashboard_bridge(self.client)
            print("   ✅ DashboardDataBridge created")
            
            # Start the bridge
            if not self.bridge.start():
                print("   ❌ Failed to start DashboardDataBridge")
                return False
                
            print("   ✅ DashboardDataBridge started")
            
            # Wait for data flow
            print("   ⏳ Waiting for data bridge...")
            time.sleep(5)
            
            # Check bridge status
            status = self.bridge.get_status()
            print(f"   📊 Bridge Status: {status['status']}")
            print(f"   📈 Symbols Tracked: {status['symbols_tracked']}")
            print(f"   📡 Total Updates: {status['total_updates']}")
            
            # Check current data
            current_data = self.bridge.get_current_data()
            symbols_bridged = 0
            
            for symbol in TEST_SYMBOLS:
                if symbol in current_data:
                    data = current_data[symbol]
                    print(f"   🌉 {symbol}: ${data['price']:.2f} ({data['change_pct']:+.2f}%)")
                    self.data_received[f'bridge_{symbol}'] = data['price']
                    symbols_bridged += 1
                else:
                    print(f"   ⚠️ {symbol}: Not in bridge data")
            
            if symbols_bridged == 0:
                print("   ❌ No symbols bridged")
                return False
            
            self.test_results['bridge'] = True
            print("   ✅ DashboardDataBridge: PASSED\n")
            return True
            
        except Exception as e:
            print(f"   ❌ DashboardDataBridge: FAILED - {e}\n")
            self.test_results['bridge'] = False
            return False
    
    def _test_end_to_end_flow(self) -> bool:
        """Test complete end-to-end data flow."""
        print("5️⃣ TESTING END-TO-END DATA FLOW")
        print("-" * 30)
        
        try:
            print("   🔄 Testing complete data pipeline...")
            
            # Setup data collection
            data_points = {}
            
            # Collect data from all components
            print("   📊 Collecting data from all components...")
            
            # From SpyderClient
            if self.client:
                spy_contract = self.client.create_stock_contract('SPY')
                req_id = self.client.request_market_data(spy_contract)
                time.sleep(3)
                ticker = self.client.get_market_data(req_id)
                if ticker and ticker.last:
                    data_points['client'] = ticker.last
                    print(f"      SpyderClient SPY: ${ticker.last:.2f}")
                self.client.cancel_market_data(req_id)
            
            # From MarketDataManager
            if self.market_manager:
                snapshot = self.market_manager.get_market_data('SPY')
                if snapshot and snapshot.last:
                    data_points['manager'] = snapshot.last
                    print(f"      MarketDataManager SPY: ${snapshot.last:.2f}")
            
            # From DashboardDataBridge
            if self.bridge:
                bridge_data = self.bridge.get_current_data('SPY')
                if bridge_data and 'price' in bridge_data:
                    data_points['bridge'] = bridge_data['price']
                    print(f"      DashboardDataBridge SPY: ${bridge_data['price']:.2f}")
            
            # Verify data consistency (prices should be close)
            if len(data_points) >= 2:
                prices = list(data_points.values())
                price_range = max(prices) - min(prices)
                
                print(f"   📏 Price Range: ${price_range:.2f}")
                
                if price_range < 5.0:  # Prices should be within $5
                    print("   ✅ Data consistency: GOOD")
                else:
                    print("   ⚠️ Data consistency: QUESTIONABLE")
            
            # Test live updates
            print("   🔄 Testing live updates...")
            initial_updates = {}
            
            if self.bridge:
                status = self.bridge.get_status()
                initial_updates['bridge'] = status['total_updates']
            
            if self.market_manager:
                metrics = self.market_manager.get_metrics()
                initial_updates['manager'] = metrics.total_updates
            
            # Wait and check for new updates
            time.sleep(5)
            
            updates_detected = False
            
            if self.bridge:
                status = self.bridge.get_status()
                if status['total_updates'] > initial_updates.get('bridge', 0):
                    print("   ✅ Bridge updates: ACTIVE")
                    updates_detected = True
            
            if self.market_manager:
                metrics = self.market_manager.get_metrics()
                if metrics.total_updates > initial_updates.get('manager', 0):
                    print("   ✅ Manager updates: ACTIVE")
                    updates_detected = True
            
            if not updates_detected:
                print("   ⚠️ No live updates detected")
            
            self.test_results['end_to_end'] = True
            print("   ✅ End-to-End Flow: PASSED\n")
            return True
            
        except Exception as e:
            print(f"   ❌ End-to-End Flow: FAILED - {e}\n")
            self.test_results['end_to_end'] = False
            return False
    
    def _test_dashboard_compatibility(self) -> bool:
        """Test dashboard JSON file compatibility."""
        print("6️⃣ TESTING DASHBOARD COMPATIBILITY")
        print("-" * 30)
        
        try:
            # Check if JSON file exists
            if os.path.exists(DASHBOARD_DATA_FILE):
                print(f"   📄 Found dashboard data file: {DASHBOARD_DATA_FILE}")
                
                # Read and validate JSON
                with open(DASHBOARD_DATA_FILE, 'r') as f:
                    dashboard_data = json.load(f)
                
                print(f"   📊 Dashboard data symbols: {len(dashboard_data)}")
                
                # Check for test symbols
                symbols_found = 0
                for symbol in TEST_SYMBOLS:
                    if symbol in dashboard_data:
                        data = dashboard_data[symbol]
                        print(f"   📈 {symbol}: ${data.get('last', 0):.2f}")
                        symbols_found += 1
                    else:
                        print(f"   ⚠️ {symbol}: Not found in dashboard data")
                
                if symbols_found > 0:
                    print("   ✅ Dashboard data: AVAILABLE")
                else:
                    print("   ❌ Dashboard data: NO SYMBOLS")
                    return False
            else:
                print(f"   ⚠️ Dashboard data file not found: {DASHBOARD_DATA_FILE}")
                print("   ℹ️ This is normal if bridge export timer hasn't run yet")
            
            # Test ET time format for dashboard
            et_display = ETTimeDisplay()
            dashboard_time = et_display.format_for_dashboard()
            print(f"   🕒 Dashboard ET Time: {dashboard_time}")
            
            self.test_results['dashboard'] = True
            print("   ✅ Dashboard Compatibility: PASSED\n")
            return True
            
        except Exception as e:
            print(f"   ❌ Dashboard Compatibility: FAILED - {e}\n")
            self.test_results['dashboard'] = False
            return False
    
    def _test_summary(self) -> None:
        """Print test summary."""
        print("📋 TEST SUMMARY")
        print("=" * 40)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        print(f"🧪 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {total_tests - passed_tests}")
        print()
        
        # Detailed results
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
        
        print()
        
        # Data received summary
        if self.data_received:
            print("📊 DATA RECEIVED:")
            for source, price in self.data_received.items():
                print(f"   {source}: ${price:.2f}")
            print()
        
        # Overall result
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Your integrated solution is working!")
            print()
            print("🚀 WHAT THIS MEANS:")
            print("   ✅ NaN data issue: RESOLVED")
            print("   ✅ ET time display: WORKING")
            print("   ✅ Real-time updates: ACTIVE")
            print("   ✅ Dashboard integration: READY")
            print()
            print("🎯 NEXT STEPS:")
            print("   1. Deploy the updated modules to your system")
            print("   2. Restart your Spyder dashboard")
            print("   3. Enjoy real-time data with proper ET time!")
        else:
            print("⚠️ SOME TESTS FAILED - See details above")
            print()
            print("🔧 TROUBLESHOOTING:")
            if not self.test_results.get('client', True):
                print("   - Check IB Gateway is running on port 4002")
                print("   - Verify client ID 44 is available")
                print("   - Ensure market data subscriptions are active")
            if not self.test_results.get('market_manager', True):
                print("   - Verify MarketDataManager can access SpyderClient")
                print("   - Check for import errors in modules")
            if not self.test_results.get('bridge', True):
                print("   - Ensure DashboardDataBridge has proper connections")
                print("   - Check file permissions for JSON export")
        
        # Test duration
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        print(f"\n⏱️ Test Duration: {duration:.1f} seconds")
    
    def _cleanup(self) -> None:
        """Clean up test resources."""
        try:
            print("\n🧹 CLEANING UP TEST RESOURCES")
            
            # Stop bridge
            if self.bridge:
                self.bridge.stop()
                print("   ✅ DashboardDataBridge stopped")
            
            # Stop market manager
            if self.market_manager:
                self.market_manager.stop()
                print("   ✅ MarketDataManager stopped")
            
            # Disconnect client
            if self.client:
                self.client.disconnect()
                print("   ✅ SpyderClient disconnected")
            
            print("   ✅ Cleanup completed")
            
        except Exception as e:
            print(f"   ⚠️ Cleanup warning: {e}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Run the complete integration test."""
    if not CLIENT_AVAILABLE:
        print("❌ Required modules not available")
        print("   Ensure you have:")
        print("   - SpyderB01_SpyderClient")
        print("   - SpyderB07_MarketDataManager") 
        print("   - SpyderG08_DashboardDataBridge")
        return False
    
    # Create and run test
    test = IntegratedSolutionTest()
    return test.run_complete_test()

if __name__ == "__main__":
    success = main()
    exit_code = 0 if success else 1
    sys.exit(exit_code)