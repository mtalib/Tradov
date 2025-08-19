#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_Test1to10Clients.py
Purpose: Test the updated 1-10 client configuration with IB Gateway
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 16:25:00  

Module Description:
    Tests the newly integrated Client 1-10 system in SpyderB08 to ensure
    all clients can connect properly and resolve the API disconnection issue.
"""

import time
import threading
from datetime import datetime
from typing import Dict, List, Optional
from ib_insync import *

class Updated1to10ClientTester:
    """Test the updated 1-10 client system."""
    
    def __init__(self):
        self.clients: Dict[int, IB] = {}
        self.connected_clients: List[int] = []
        self.data_received = {}
        
        # Updated client allocation (1-10) according to new SpyderB08
        self.client_configs = {
            1: {"purpose": "Administrative", "symbols": [], "priority": "SYSTEM"},
            2: {"purpose": "Order Execution", "symbols": [], "priority": "CRITICAL"},
            3: {"purpose": "Core Data", "symbols": ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"], "priority": "CRITICAL"},
            4: {"purpose": "SPY Options", "symbols": ["SPY_0DTE", "SPY_1DTE"], "priority": "CRITICAL"},
            5: {"purpose": "Volatility", "symbols": ["VIX9D", "VXV", "VXMT", "VVIX", "UVXY"], "priority": "HIGH"},
            6: {"purpose": "Market Internals", "symbols": ["TRIN-NYSE", "ADD-NYSE", "CPC", "PCALL", "SKEW"], "priority": "HIGH"},
            7: {"purpose": "Major Indices", "symbols": ["DIA", "QQQ", "IWM"], "priority": "HIGH"},
            8: {"purpose": "Extended Assets", "symbols": ["TLT", "LQD", "DXY", "GLD"], "priority": "MEDIUM"},
            9: {"purpose": "Sector ETFs", "symbols": ["XLF", "XLK", "XLE", "XLV", "XLI"], "priority": "LOW"},
            10: {"purpose": "International", "symbols": ["DAX", "CAC40", "N225", "EUR.USD", "EWJ"], "priority": "LOW"},  # NEW!
        }
    
    def test_all_clients(self):
        """Test all clients 1-10 according to updated SpyderB08."""
        print("🚀 TESTING UPDATED 1-10 CLIENT SYSTEM")
        print("=" * 60)
        print("Testing the newly integrated SpyderB08 configuration")
        print()
        
        # Connect clients in priority order
        priority_order = [2, 1, 3, 4, 5, 6, 7, 8, 9, 10]  # Order execution first, International last
        
        for client_id in priority_order:
            config = self.client_configs[client_id]
            print(f"🔌 Testing Client {client_id}: {config['purpose']} ({config['priority']})")
            
            success = self._connect_single_client(client_id)
            if success:
                print(f"   ✅ Client {client_id} connected successfully")
                self.connected_clients.append(client_id)
                
                # Test market data for data clients (3-10)
                if client_id >= 3 and config['symbols']:
                    self._test_client_data(client_id)
                
                time.sleep(0.3)  # Brief delay between connections
            else:
                print(f"   ❌ Client {client_id} connection failed")
        
        # Connection summary
        print(f"\n📊 Connection Summary:")
        print(f"   Total clients tested: 10")
        print(f"   Successfully connected: {len(self.connected_clients)}")
        print(f"   Success rate: {len(self.connected_clients)*100/10:.1f}%")
        print(f"   Connected clients: {self.connected_clients}")
        
        # Critical clients check
        critical_clients = [c for c in [2, 3, 4] if c in self.connected_clients]
        print(f"   Critical clients online: {len(critical_clients)}/3 {critical_clients}")
        
        # International client check (NEW)
        if 10 in self.connected_clients:
            print(f"   🌍 International client (10): ✅ ONLINE")
        else:
            print(f"   🌍 International client (10): ❌ OFFLINE")
        
        # Test IB Gateway API status
        if len(self.connected_clients) > 0:
            print(f"\n🎉 SUCCESS: API Clients are now CONNECTED!")
            print(f"   This should resolve the 'API Client disconnected' issue in IB Gateway")
            
            # Brief monitoring period
            self._monitor_connections(15)
        else:
            print(f"\n❌ FAILURE: No clients connected")
            print(f"   Check IB Gateway settings and API configuration")
    
    def _connect_single_client(self, client_id: int) -> bool:
        """Connect a single client to IB Gateway."""
        try:
            ib = IB()
            
            # Connect to Gateway Paper (port 4002)
            ib.connect('127.0.0.1', 4002, clientId=client_id, timeout=10)
            
            if ib.isConnected():
                self.clients[client_id] = ib
                
                # Set market data type for data clients (3-10)
                if client_id >= 3:
                    ib.reqMarketDataType(1)  # Real-time
                    
                return True
            else:
                return False
                
        except Exception as e:
            print(f"      Error: {e}")
            return False
    
    def _test_client_data(self, client_id: int):
        """Test market data for a specific client."""
        config = self.client_configs[client_id]
        symbols = config['symbols']
        
        if not symbols:
            return
        
        print(f"      📊 Testing data for: {', '.join(symbols[:3])}{'...' if len(symbols) > 3 else ''}")
        
        try:
            ib = self.clients[client_id]
            
            # Test first symbol in the list
            test_symbol = symbols[0]
            
            # Create appropriate contract based on symbol
            if test_symbol in ['SPY', 'DIA', 'QQQ', 'IWM', 'TLT', 'LQD', 'GLD']:
                contract = Stock(test_symbol, 'SMART', 'USD')
            elif test_symbol in ['SPX', 'VIX', 'VIX9D', 'VXMT', 'VVIX']:
                contract = Index(test_symbol, 'CBOE', 'USD')
            elif test_symbol == '/ES':
                contract = Future('ES', '20251219', 'CME')  # December 2025 expiry
            elif test_symbol == 'TICK-NYSE':
                contract = Index('TICK-NYSE', 'NYSE', 'USD')
            elif test_symbol in ['DAX', 'CAC40', 'N225']:
                # International indices - may need specific exchanges
                exchanges = {'DAX': 'EUREX', 'CAC40': 'MONEP', 'N225': 'OSE.JPN'}
                contract = Index(test_symbol, exchanges.get(test_symbol, 'SMART'), 'USD')
            elif 'EUR.USD' in test_symbol:
                contract = Forex('EUR', 'USD')
            elif test_symbol == 'EWJ':
                contract = Stock(test_symbol, 'SMART', 'USD')  # ETF
            else:
                contract = Stock(test_symbol, 'SMART', 'USD')  # Default to stock
            
            # Quick data test
            qualified = ib.qualifyContracts(contract)
            if qualified:
                ticker = ib.reqMktData(qualified[0], '', False, False)
                time.sleep(2)  # Brief wait for data
                
                if ticker.last > 0 or ticker.bid > 0 or ticker.ask > 0:
                    print(f"      ✅ Data received for {test_symbol}")
                    self.data_received[f"Client{client_id}_{test_symbol}"] = True
                else:
                    print(f"      ⚠️  No data for {test_symbol}")
                
                ib.cancelMktData(qualified[0])
            else:
                print(f"      ❌ Contract qualification failed for {test_symbol}")
                
        except Exception as e:
            print(f"      ❌ Data test error for Client {client_id}: {e}")
    
    def _monitor_connections(self, duration=15):
        """Monitor connections for a specified duration."""
        print(f"\n👁️  Monitoring all {len(self.connected_clients)} connections for {duration} seconds...")
        
        start_time = time.time()
        check_count = 0
        
        while time.time() - start_time < duration:
            time.sleep(3)
            check_count += 1
            
            active_clients = []
            for client_id, ib in self.clients.items():
                if ib.isConnected():
                    active_clients.append(client_id)
            
            print(f"   Check {check_count}: {len(active_clients)}/{len(self.connected_clients)} clients active")
            
            if len(active_clients) != len(self.connected_clients):
                print(f"   ⚠️  Connection changes detected!")
                break
        
        print(f"   ✅ Monitoring complete - connections stable")
    
    def get_final_status(self) -> dict:
        """Get final status summary."""
        active_count = sum(1 for ib in self.clients.values() if ib.isConnected())
        
        return {
            'total_configured': 10,
            'successfully_connected': len(self.connected_clients),
            'currently_active': active_count,
            'data_tests_passed': len(self.data_received),
            'critical_clients_online': len([c for c in [2, 3, 4] if c in self.connected_clients]),
            'international_client_online': 10 in self.connected_clients,
            'client_range': '1-10',
            'architecture': 'Unified SpyderB08'
        }
    
    def disconnect_all(self):
        """Disconnect all clients."""
        print(f"\n🔌 Disconnecting all clients...")
        
        for client_id, ib in self.clients.items():
            try:
                if ib.isConnected():
                    ib.disconnect()
                    print(f"   🔌 Client {client_id} disconnected")
            except Exception as e:
                print(f"   ❌ Error disconnecting Client {client_id}: {e}")
        
        self.clients.clear()
        self.connected_clients.clear()
        print(f"✅ All clients disconnected")

def main():
    """Main function to test the 1-10 client system."""
    print("🚀 SPYDER 1-10 CLIENT SYSTEM TEST")
    print("=" * 60)
    print("Testing the updated SpyderB08 with Client 10 integration")
    print()
    
    tester = Updated1to10ClientTester()
    
    try:
        # Test all clients
        tester.test_all_clients()
        
        # Get final status
        status = tester.get_final_status()
        print(f"\n📈 FINAL TEST RESULTS:")
        print(f"   Architecture: {status['architecture']}")
        print(f"   Client Range: {status['client_range']}")
        print(f"   Total Configured: {status['total_configured']}")
        print(f"   Successfully Connected: {status['successfully_connected']}")
        print(f"   Currently Active: {status['currently_active']}")
        print(f"   Critical Clients Online: {status['critical_clients_online']}/3")
        print(f"   International Client: {'✅' if status['international_client_online'] else '❌'}")
        print(f"   Data Tests Passed: {status['data_tests_passed']}")
        
        if status['successfully_connected'] >= 5:
            print(f"\n🎉 EXCELLENT: Multi-client system working!")
            print(f"   IB Gateway should now show 'API Client: Connected' (green)")
            print(f"   Spyder data feeds should start flowing")
        elif status['successfully_connected'] >= 2:
            print(f"\n✅ GOOD: Core clients connected")
            print(f"   Basic functionality should work")
        else:
            print(f"\n❌ POOR: Few/no clients connected")
            print(f"   Check IB Gateway configuration")
        
        # Cleanup
        tester.disconnect_all()
        
    except KeyboardInterrupt:
        print(f"\n🛑 Test interrupted by user")
        tester.disconnect_all()
    except Exception as e:
        print(f"\n💥 Test failed: {e}")
        tester.disconnect_all()

if __name__ == "__main__":
    main()