#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: temp_GatewayTroubleshooter.py
Purpose: Troubleshoot IB Gateway configuration issues preventing data flow
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 16:00:00  

Module Description:
    Since IBKR confirmed subscriptions are active, this troubleshoots
    IB Gateway/TWS configuration issues that prevent data flow.
"""

import time
from datetime import datetime
from ib_insync import *

class GatewayTroubleshooter:
    """Troubleshoot IB Gateway configuration issues."""
    
    def __init__(self):
        self.ib = None
        self.results = {}
        
    def run_full_diagnosis(self):
        """Run complete gateway troubleshooting."""
        print("🔧 IB GATEWAY TROUBLESHOOTER")
        print("=" * 50)
        print("Since IBKR confirmed subscriptions are active,")
        print("this will check configuration/permission issues.")
        print()
        
        # Test different connection methods
        self._test_all_connections()
        
        # Test API permissions  
        self._test_api_permissions()
        
        # Test market data settings
        self._test_market_data_settings()
        
        # Test account permissions
        self._test_account_settings()
        
        # Generate recommendations
        self._generate_recommendations()
    
    def _test_all_connections(self):
        """Test all possible IB connections."""
        print("🔌 TESTING ALL IB CONNECTIONS")
        print("-" * 40)
        
        # All possible connection configurations
        connections = [
            {'host': '127.0.0.1', 'port': 7497, 'clientId': 1, 'name': 'TWS Paper'},
            {'host': '127.0.0.1', 'port': 7496, 'clientId': 1, 'name': 'TWS Live'}, 
            {'host': '127.0.0.1', 'port': 4002, 'clientId': 1, 'name': 'Gateway Paper'},
            {'host': '127.0.0.1', 'port': 4001, 'clientId': 1, 'name': 'Gateway Live'},
            {'host': '127.0.0.1', 'port': 4002, 'clientId': 999, 'name': 'Gateway Paper (Alt Client)'},
        ]
        
        working_connections = []
        
        for config in connections:
            print(f"\n📡 Testing {config['name']} (Port {config['port']})...")
            
            try:
                ib = IB()
                ib.connect(
                    host=config['host'],
                    port=config['port'], 
                    clientId=config['clientId'],
                    timeout=5
                )
                
                if ib.isConnected():
                    print(f"   ✅ Connected!")
                    
                    # Test basic account info
                    accounts = ib.managedAccounts()
                    print(f"   📊 Accounts: {accounts}")
                    
                    # Test SPY data request
                    data_result = self._test_spy_data(ib, config['name'])
                    config['data_works'] = data_result
                    config['accounts'] = accounts
                    
                    working_connections.append(config)
                    ib.disconnect()
                else:
                    print(f"   ❌ Connection failed")
                    
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        self.results['connections'] = working_connections
        print(f"\n✅ Working connections: {len(working_connections)}")
    
    def _test_spy_data(self, ib, connection_name):
        """Test SPY data on a specific connection."""
        print(f"   📈 Testing SPY data...")
        
        try:
            # Test all market data types
            for data_type in [1, 2, 3, 4]:
                try:
                    ib.reqMarketDataType(data_type)
                    print(f"      Testing data type {data_type}...")
                    
                    spy = Stock('SPY', 'SMART', 'USD')
                    qualified = ib.qualifyContracts(spy)
                    
                    if qualified:
                        ticker = ib.reqMktData(spy, '', False, False)
                        time.sleep(5)  # Wait for data
                        
                        if ticker.last > 0 or ticker.bid > 0 or ticker.ask > 0:
                            print(f"      ✅ Data type {data_type} WORKS! Last={ticker.last}")
                            ib.cancelMktData(spy)
                            return f"Type {data_type}"
                        else:
                            print(f"      ❌ Data type {data_type}: No data")
                        
                        ib.cancelMktData(spy)
                    else:
                        print(f"      ❌ Data type {data_type}: Contract failed")
                        
                except Exception as e:
                    print(f"      ❌ Data type {data_type}: {e}")
            
            return "No data on any type"
            
        except Exception as e:
            print(f"   ❌ SPY test error: {e}")
            return f"Error: {e}"
    
    def _test_api_permissions(self):
        """Test API permissions and settings."""
        print(f"\n🔑 TESTING API PERMISSIONS")
        print("-" * 40)
        
        # Use the first working connection
        if not self.results.get('connections'):
            print("❌ No working connections to test permissions")
            return
        
        config = self.results['connections'][0]
        
        try:
            ib = IB()
            ib.connect(config['host'], config['port'], config['clientId'])
            
            # Test various API capabilities
            tests = {
                'Account Summary': self._test_account_summary,
                'Positions': self._test_positions,
                'Open Orders': self._test_open_orders,
                'Contract Details': self._test_contract_details,
                'Market Data Type': self._test_market_data_type_setting,
            }
            
            api_results = {}
            for test_name, test_func in tests.items():
                print(f"   Testing {test_name}...")
                try:
                    result = test_func(ib)
                    api_results[test_name] = result
                    print(f"   ✅ {test_name}: {result}")
                except Exception as e:
                    api_results[test_name] = f"Error: {e}"
                    print(f"   ❌ {test_name}: {e}")
            
            self.results['api_permissions'] = api_results
            ib.disconnect()
            
        except Exception as e:
            print(f"❌ API permission test failed: {e}")
    
    def _test_account_summary(self, ib):
        """Test account summary access."""
        summary = ib.accountSummary()
        return f"Retrieved {len(summary)} account values"
    
    def _test_positions(self, ib):
        """Test positions access.""" 
        positions = ib.positions()
        return f"Retrieved {len(positions)} positions"
    
    def _test_open_orders(self, ib):
        """Test open orders access."""
        orders = ib.openOrders()
        return f"Retrieved {len(orders)} open orders"
    
    def _test_contract_details(self, ib):
        """Test contract details access."""
        spy = Stock('SPY', 'SMART', 'USD')
        details = ib.reqContractDetails(spy)
        return f"Retrieved {len(details)} contract details"
    
    def _test_market_data_type_setting(self, ib):
        """Test market data type setting."""
        # Try setting to real-time
        ib.reqMarketDataType(1)
        time.sleep(1)
        return "Real-time data type set successfully"
    
    def _test_market_data_settings(self):
        """Test specific market data settings."""
        print(f"\n📊 TESTING MARKET DATA SETTINGS")
        print("-" * 40)
        
        if not self.results.get('connections'):
            print("❌ No working connections")
            return
        
        config = self.results['connections'][0]
        
        try:
            ib = IB()
            ib.connect(config['host'], config['port'], config['clientId'])
            
            # Test multiple symbols with different configurations
            test_symbols = [
                {'symbol': 'SPY', 'type': Stock, 'args': ('SPY', 'SMART', 'USD')},
                {'symbol': 'SPY', 'type': Stock, 'args': ('SPY', 'ARCA', 'USD')},  # Try specific exchange
                {'symbol': 'AAPL', 'type': Stock, 'args': ('AAPL', 'SMART', 'USD')},  # Try different stock
            ]
            
            for symbol_config in test_symbols:
                print(f"\n   Testing {symbol_config['symbol']} on {symbol_config['args'][1]}...")
                
                try:
                    contract = symbol_config['type'](*symbol_config['args'])
                    qualified = ib.qualifyContracts(contract)
                    
                    if qualified:
                        print(f"      ✅ Contract qualified: {qualified[0].primaryExchange}")
                        
                        # Test market data with generic tick types
                        ticker = ib.reqMktData(qualified[0], '', False, False)
                        time.sleep(3)
                        
                        if hasattr(ticker, 'last') and ticker.last > 0:
                            print(f"      ✅ Data received: Last={ticker.last}")
                        elif hasattr(ticker, 'bid') and ticker.bid > 0:
                            print(f"      ✅ Data received: Bid={ticker.bid}")
                        else:
                            print(f"      ❌ No data received")
                            print(f"         Last={getattr(ticker, 'last', 'N/A')}")
                            print(f"         Bid={getattr(ticker, 'bid', 'N/A')}")
                            print(f"         Ask={getattr(ticker, 'ask', 'N/A')}")
                        
                        ib.cancelMktData(qualified[0])
                    else:
                        print(f"      ❌ Contract qualification failed")
                        
                except Exception as e:
                    print(f"      ❌ Error: {e}")
            
            ib.disconnect()
            
        except Exception as e:
            print(f"❌ Market data settings test failed: {e}")
    
    def _test_account_settings(self):
        """Test account-specific settings."""
        print(f"\n👤 ACCOUNT SETTINGS CHECK")
        print("-" * 40)
        print("Manual checks required in IB Gateway/TWS:")
        print()
        print("1. 📊 Market Data Subscriptions:")
        print("   → File → Global Configuration → API → Settings")
        print("   → Enable 'Create API message for new market data'")
        print()
        print("2. 🔐 API Settings:")
        print("   → File → Global Configuration → API → Settings")  
        print("   → Enable 'Enable ActiveX and Socket Clients'")
        print("   → Check 'Read-Only API'")
        print()
        print("3. 💰 Market Data Permissions:")
        print("   → Account Management → Settings → Market Data Subscriptions")
        print("   → Verify all subscriptions show as 'Active'")
        print()
        print("4. 🕐 Session Settings:")
        print("   → Try logging out and back into IB Gateway")
        print("   → Try using TWS instead of IB Gateway")
    
    def _generate_recommendations(self):
        """Generate specific recommendations based on test results."""
        print(f"\n🎯 RECOMMENDATIONS")
        print("=" * 50)
        
        if not self.results.get('connections'):
            print("🚨 CRITICAL: No working connections found")
            print("1. Restart IB Gateway/TWS completely")
            print("2. Check if TWS vs Gateway makes a difference")
            print("3. Try different client IDs (1, 999, 1001)")
            return
        
        working_conn = self.results['connections'][0]
        
        if working_conn.get('data_works') == 'No data on any type':
            print("🚨 CRITICAL: Connection works but NO data on any type")
            print()
            print("Most likely causes:")
            print("1. 📊 IB Gateway API settings incorrect")
            print("2. 🔐 Market data streaming disabled in account")
            print("3. 🕐 Session/login issue requiring fresh restart")
            print("4. 💻 Paper trading data restrictions")
            print()
            print("IMMEDIATE ACTIONS:")
            print("1. In IB Gateway: File → Global Configuration → API → Settings")
            print("   → Enable 'Create API message for new market data'")
            print("2. Completely close and restart IB Gateway")
            print("3. Try TWS instead of IB Gateway")
            print("4. Call IBKR again - mention 'API not receiving market data'")
        
        elif 'Type' in str(working_conn.get('data_works', '')):
            print("✅ GOOD: Data works on some configurations")
            print(f"Working setup: {working_conn['name']} with {working_conn['data_works']}")
            print()
            print("ACTIONS:")
            print("1. Use this working configuration in Spyder")
            print("2. Update Spyder to connect to this specific setup")
        
        else:
            print("⚠️  Mixed results - needs manual investigation")
            print("Review the detailed test results above")

def main():
    """Run the gateway troubleshooter."""
    troubleshooter = GatewayTroubleshooter()
    troubleshooter.run_full_diagnosis()

if __name__ == "__main__":
    main()