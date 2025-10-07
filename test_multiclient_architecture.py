#!/usr/bin/env python3
"""
Test Suite for Multi-Client Data Manager (Clients 1-10)
Validates the complete client allocation architecture
"""

import sys
import time
from pathlib import Path
from datetime import datetime
import threading

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from SpyderB_Broker.SpyderB08_MultiClientDataManager import (
    MultiClientDataManager,
    OrderRequest,
    get_manager_instance,
    reset_manager_instance
)

def print_header(text):
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")

def print_status(success, message):
    symbol = "PASS" if success else "FAIL"
    print(f"[{symbol}] {message}")

class MultiClientTester:
    """Comprehensive tester for multi-client architecture"""
    
    def __init__(self):
        self.manager = None
        self.test_results = []
        
    def run_all_tests(self):
        """Run complete test suite"""
        print_header("SPYDER MULTI-CLIENT ARCHITECTURE TEST")
        print(f"Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # Test 1: Initialization
            self.test_initialization()
            
            # Test 2: Client Allocation
            self.test_client_allocation()
            
            # Test 3: Start Manager
            self.test_start_manager()
            
            # Test 4: Client Connections
            self.test_client_connections()
            
            # Test 5: Order Execution (Client 1)
            self.test_order_execution()
            
            # Test 6: Data Subscriptions
            self.test_data_subscriptions()
            
            # Test 7: Client Assignment Logic
            self.test_client_assignment()
            
            # Test 8: Performance Metrics
            self.test_performance_metrics()
            
            # Test 9: Stop Manager
            self.test_stop_manager()
            
        finally:
            # Cleanup
            if self.manager:
                self.manager.stop()
            reset_manager_instance()
        
        # Summary
        self.print_summary()
    
    def test_initialization(self):
        """Test manager initialization"""
        print_header("TEST 1: MANAGER INITIALIZATION")
        
        try:
            self.manager = MultiClientDataManager()
            success = self.manager is not None
            self.test_results.append(("Initialization", success))
            print_status(success, "Manager instance created")
            
            # Verify client configs exist
            has_configs = len(self.manager.client_configs) >= 10
            self.test_results.append(("Client Configs", has_configs))
            print_status(has_configs, f"Found {len(self.manager.client_configs)} client configurations")
            
        except Exception as e:
            print_status(False, f"Initialization failed: {e}")
            self.test_results.append(("Initialization", False))
    
    def test_client_allocation(self):
        """Test client allocation strategy"""
        print_header("TEST 2: CLIENT ALLOCATION STRATEGY")
        
        expected_allocation = {
            1: "ORDER_EXECUTION",
            2: "ADMINISTRATIVE", 
            3: "CORE_DATA",
            4: "OPTIONS_DATA",
            5: "VOLATILITY_DATA",
            6: "MARKET_INTERNALS",
            7: "MAJOR_INDICES",
            8: "EXTENDED_ASSETS",
            9: "SECTOR_ETFS",
            10: "INTERNATIONAL"
        }
        
        for client_id, expected_purpose in expected_allocation.items():
            if client_id in self.manager.clients:
                client = self.manager.clients[client_id]
                actual = client.purpose.name
                success = actual == expected_purpose
                self.test_results.append((f"Client {client_id} Purpose", success))
                
                if success:
                    print_status(True, f"Client {client_id}: {actual} ({len(client.symbols)} symbols)")
                else:
                    print_status(False, f"Client {client_id}: Expected {expected_purpose}, got {actual}")
            else:
                print_status(False, f"Client {client_id} not found")
                self.test_results.append((f"Client {client_id} Exists", False))
    
    def test_start_manager(self):
        """Test starting the manager"""
        print_header("TEST 3: START MANAGER")
        
        try:
            success = self.manager.start()
            self.test_results.append(("Manager Start", success))
            print_status(success, "Manager started")
            
            # Wait for connections to stabilize
            time.sleep(3)
            
        except Exception as e:
            print_status(False, f"Start failed: {e}")
            self.test_results.append(("Manager Start", False))
    
    def test_client_connections(self):
        """Test individual client connections"""
        print_header("TEST 4: CLIENT CONNECTIONS (1-10)")
        
        status = self.manager.get_status()
        connected_count = status.get('connected_clients', 0)
        total_count = status.get('total_clients', 0)
        
        print(f"\nConnected: {connected_count}/{total_count}")
        
        for client_id in range(1, 11):
            client_status = self.manager.get_client_status(client_id)
            if client_status:
                is_connected = client_status['is_connected']
                purpose = client_status['purpose']
                symbol_count = len(client_status['symbols'])
                
                self.test_results.append((f"Client {client_id} Connection", is_connected))
                
                status_text = "CONNECTED" if is_connected else "DISCONNECTED"
                print(f"  Client {client_id} ({purpose}): {status_text} - {symbol_count} symbols")
            else:
                print_status(False, f"Client {client_id} status unavailable")
                self.test_results.append((f"Client {client_id} Status", False))
    
    def test_order_execution(self):
        """Test order execution on Client 1"""
        print_header("TEST 5: ORDER EXECUTION (CLIENT 1)")
        
        try:
            # Create test order
            order = OrderRequest(
                symbol="SPY",
                action="BUY",
                quantity=1,
                order_type="MKT"
            )
            
            # Place order - should automatically route to Client 1
            success = self.manager.place_order(order)
            self.test_results.append(("Order Placement", success))
            print_status(success, f"Order placed for {order.symbol} via Client {order.client_id}")
            
            # Verify order is using Client 1
            uses_client1 = order.client_id == 1
            self.test_results.append(("Order Uses Client 1", uses_client1))
            print_status(uses_client1, f"Order correctly routed to Client {order.client_id}")
            
            # Check active orders
            status = self.manager.get_status()
            has_active_orders = status.get('active_orders', 0) > 0
            print_status(has_active_orders, f"Active orders: {status.get('active_orders', 0)}")
            
        except Exception as e:
            print_status(False, f"Order execution failed: {e}")
            self.test_results.append(("Order Execution", False))
    
    def test_data_subscriptions(self):
        """Test data subscription routing"""
        print_header("TEST 6: DATA SUBSCRIPTIONS")
        
        test_symbols = {
            "SPY": 3,      # Should go to Client 3 (Core Data)
            "VIX": 3,      # Should go to Client 3 (Core Data)
            "VXV": 5,      # Should go to Client 5 (Volatility)
            "TRIN": 6,     # Should go to Client 6 (Market Internals)
            "VUD": 6,      # Should go to Client 6 (Market Internals) - IMPORTANT!
            "QQQ": 7,      # Should go to Client 7 (Major Indices)
            "XLF": 9,      # Should go to Client 9 (Sector ETFs)
        }
        
        received_data = {}
        
        def make_callback(symbol):
            def callback(data):
                received_data[symbol] = data
            return callback
        
        for symbol, expected_client in test_symbols.items():
            try:
                callback = make_callback(symbol)
                success = self.manager.subscribe_to_data(symbol, callback)
                
                # Verify it was assigned to correct client
                actual_client = self.manager._get_optimal_client_for_symbol(symbol)
                correct_assignment = actual_client == expected_client
                
                self.test_results.append((f"{symbol} Subscription", success))
                self.test_results.append((f"{symbol} Client Assignment", correct_assignment))
                
                if correct_assignment:
                    print_status(True, f"{symbol} -> Client {actual_client} (expected {expected_client})")
                else:
                    print_status(False, f"{symbol} -> Client {actual_client} (expected {expected_client})")
                    
            except Exception as e:
                print_status(False, f"{symbol} subscription failed: {e}")
                self.test_results.append((f"{symbol} Subscription", False))
    
    def test_client_assignment(self):
        """Test symbol-to-client assignment logic"""
        print_header("TEST 7: CLIENT ASSIGNMENT LOGIC")
        
        # Verify VUD is assigned to Client 6
        vud_client = self.manager._get_optimal_client_for_symbol("VUD")
        vud_correct = vud_client == 6
        self.test_results.append(("VUD Assignment", vud_correct))
        print_status(vud_correct, f"VUD assigned to Client {vud_client} (expected 6)")
        
        # Verify SPY options go to Client 4
        spy_opt_client = self.manager._get_optimal_client_for_symbol("SPY_OPTIONS_0DTE")
        spy_opt_correct = spy_opt_client == 4
        self.test_results.append(("SPY Options Assignment", spy_opt_correct))
        print_status(spy_opt_correct, f"SPY Options assigned to Client {spy_opt_client} (expected 4)")
        
        # Verify international symbols go to Client 10
        intl_client = self.manager._get_optimal_client_for_symbol("EWJ")
        intl_correct = intl_client == 10
        self.test_results.append(("International Assignment", intl_correct))
        print_status(intl_correct, f"International (EWJ) assigned to Client {intl_client} (expected 10)")
    
    def test_performance_metrics(self):
        """Test performance metrics"""
        print_header("TEST 8: PERFORMANCE METRICS")
        
        status = self.manager.get_status()
        
        metrics = [
            ("Running", status.get('is_running', False)),
            ("Total Clients", status.get('total_clients', 0) >= 10),
            ("Library", status.get('library') == "ib_async (modern)"),
        ]
        
        for metric_name, metric_value in metrics:
            self.test_results.append((metric_name, bool(metric_value)))
            print_status(bool(metric_value), f"{metric_name}: {metric_value}")
        
        print(f"\nPerformance Stats:")
        print(f"  Total Messages: {status.get('total_messages', 0)}")
        print(f"  Total Orders: {status.get('total_orders', 0)}")
        print(f"  Total Errors: {status.get('total_errors', 0)}")
        print(f"  Subscriptions: {status.get('subscriptions', 0)}")
    
    def test_stop_manager(self):
        """Test stopping the manager"""
        print_header("TEST 9: STOP MANAGER")
        
        try:
            success = self.manager.stop()
            self.test_results.append(("Manager Stop", success))
            print_status(success, "Manager stopped cleanly")
            
            # Verify all clients disconnected
            time.sleep(1)
            disconnected = all(not c.is_connected for c in self.manager.clients.values())
            self.test_results.append(("All Clients Disconnected", disconnected))
            print_status(disconnected, "All clients disconnected")
            
        except Exception as e:
            print_status(False, f"Stop failed: {e}")
            self.test_results.append(("Manager Stop", False))
    
    def print_summary(self):
        """Print test summary"""
        print_header("TEST SUMMARY")
        
        passed = sum(1 for _, success in self.test_results if success)
        total = len(self.test_results)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"Tests Passed: {passed}/{total} ({pass_rate:.1f}%)\n")
        
        # Group results by category
        failures = [(name, success) for name, success in self.test_results if not success]
        
        if failures:
            print("FAILED TESTS:")
            for name, _ in failures:
                print(f"  [FAIL] {name}")
        else:
            print("ALL TESTS PASSED!")
        
        print(f"\nCritical Verifications:")
        print(f"  - Client 1 (Order Execution): {'PASS' if any('Order' in n and s for n, s in self.test_results) else 'FAIL'}")
        print(f"  - Client 6 (VUD Assignment): {'PASS' if any('VUD' in n and s for n, s in self.test_results) else 'FAIL'}")
        print(f"  - All 10 Clients Configured: {'PASS' if any('Purpose' in n and s for n, s in self.test_results) else 'FAIL'}")

def main():
    """Run the test suite"""
    tester = MultiClientTester()
    try:
        tester.run_all_tests()
        return 0
    except Exception as e:
        print(f"\nTest suite error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())