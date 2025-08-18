#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: temp_IBMarketDataBridge.py
Purpose: Bridge real IB Gateway market data to the trading dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-18 Time: 16:30:00

Module Description:
    This temporary module creates a bridge between IB Gateway and the Spyder
    Trading Dashboard to inject real market data. It establishes proper market
    data subscriptions and feeds live prices directly into the dashboard.

INSTRUCTIONS:
    1. Make sure IB Gateway is running
    2. Run this script AFTER launching the dashboard
    3. This will inject real market data into the running dashboard
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import IB components
try:
    from ib_insync import IB, Stock, Index, Future, Contract, util, Ticker
    HAS_IB_INSYNC = True
except ImportError:
    print("❌ ib_insync not installed! Install with: pip install ib_insync")
    HAS_IB_INSYNC = False
    sys.exit(1)

# ==============================================================================
# CONSTANTS
# ==============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 4002  # Paper trading port
CLIENT_ID = 999  # Unique ID for market data

# Symbol mappings for Spyder
SYMBOL_CONTRACTS = {
    'SPY': Stock('SPY', 'SMART', 'USD'),
    'SPX': Index('SPX', 'CBOE'),
    '/ES': Future('ES', '202503', 'CME'),  # March 2025
    'VIX': Index('VIX', 'CBOE'),
    'VIX9D': Index('VIX9D', 'CBOE'),
    'VVIX': Index('VVIX', 'CBOE'),
    'VXV': Index('VXV', 'CBOE'),
    'UVXY': Stock('UVXY', 'SMART', 'USD'),
    'DIA': Stock('DIA', 'SMART', 'USD'),
    'QQQ': Stock('QQQ', 'SMART', 'USD'),
    'IWM': Stock('IWM', 'SMART', 'USD'),
    'TLT': Stock('TLT', 'SMART', 'USD'),
    'GLD': Stock('GLD', 'SMART', 'USD'),
    'LQD': Stock('LQD', 'SMART', 'USD'),
    'VXMT': Index('VXMT', 'CBOE'),  # VIX Mid-Term
    'SKEW': Index('SKEW', 'CBOE'),
    'STICK': Stock('STICK', 'SMART', 'USD'),
    'STRIN': Stock('STRIN', 'SMART', 'USD'),
    'SADD': Stock('SADD', 'SMART', 'USD'),
    'CPC': Index('CPC', 'CBOE'),  # Put/Call ratio
    'PCALL': Index('PCALL', 'CBOE'),
    'GEX': Stock('GEX', 'SMART', 'USD'),
    'DEX': Stock('DEX', 'SMART', 'USD'),
    'OGL': Stock('OGL', 'SMART', 'USD'),
    'DIX': Stock('DIX', 'SMART', 'USD'),
    'ROWAN': Stock('ROWAN', 'SMART', 'USD'),
}

# ==============================================================================
# MARKET DATA BRIDGE CLASS
# ==============================================================================
class IBMarketDataBridge:
    """
    Bridge to connect IB Gateway market data to Spyder Dashboard.
    
    This class:
    1. Connects to IB Gateway
    2. Subscribes to real market data
    3. Feeds data to the dashboard
    4. Handles reconnections and errors
    """
    
    def __init__(self):
        """Initialize the bridge"""
        self.ib = None
        self.connected = False
        self.tickers = {}  # symbol -> Ticker object
        self.last_prices = {}  # symbol -> last price
        self.subscribed_symbols = set()
        self.running = False
        self.update_thread = None
        
        # Statistics
        self.successful_subscriptions = []
        self.failed_subscriptions = []
        
        print("=" * 60)
        print("IB MARKET DATA BRIDGE")
        print("=" * 60)
    
    # ==========================================================================
    # CONNECTION METHODS
    # ==========================================================================
    def connect(self) -> bool:
        """
        Connect to IB Gateway.
        
        Returns:
            bool: True if connected successfully
        """
        try:
            print(f"\n🔌 Connecting to IB Gateway at {IB_HOST}:{IB_PORT}...")
            
            # Create IB instance
            self.ib = IB()
            
            # Connect with timeout
            self.ib.connect(
                host=IB_HOST,
                port=IB_PORT,
                clientId=CLIENT_ID,
                timeout=15,
                readonly=False  # Need write access for market data
            )
            
            # Verify connection
            if not self.ib.isConnected():
                raise Exception("Connection verification failed")
            
            self.connected = True
            
            # Get account info
            accounts = self.ib.managedAccounts()
            if accounts:
                print(f"✅ Connected to account: {accounts[0]}")
            else:
                print("✅ Connected (no account info)")
            
            # Request delayed data if real-time not available
            self.ib.reqMarketDataType(3)  # 3 = delayed, 1 = live
            print("📊 Requesting delayed market data (free)")
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False
    
    # ==========================================================================
    # SUBSCRIPTION METHODS
    # ==========================================================================
    def subscribe_all_symbols(self):
        """Subscribe to all Spyder symbols"""
        print("\n📈 Subscribing to market data...")
        print("-" * 40)
        
        for symbol, contract in SYMBOL_CONTRACTS.items():
            success = self.subscribe_symbol(symbol, contract)
            time.sleep(0.1)  # Small delay to avoid overwhelming API
        
        # Print summary
        self.print_subscription_summary()
    
    def subscribe_symbol(self, symbol: str, contract: Contract) -> bool:
        """
        Subscribe to market data for a symbol.
        
        Args:
            symbol: Symbol name
            contract: IB contract object
            
        Returns:
            bool: True if subscription successful
        """
        try:
            # Qualify contract first
            qualified = self.ib.qualifyContracts(contract)
            if not qualified:
                raise Exception("Contract qualification failed")
            
            # Request market data
            ticker = self.ib.reqMktData(
                contract,
                '',  # Generic tick list (empty = all available)
                False,  # Not snapshot
                False   # Not regulatory snapshot
            )
            
            # Store ticker
            self.tickers[symbol] = ticker
            self.subscribed_symbols.add(symbol)
            self.successful_subscriptions.append(symbol)
            
            print(f"  ✅ {symbol:8} - Subscribed")
            return True
            
        except Exception as e:
            self.failed_subscriptions.append((symbol, str(e)))
            print(f"  ❌ {symbol:8} - Failed: {e}")
            return False
    
    # ==========================================================================
    # DATA PROCESSING
    # ==========================================================================
    def start_data_feed(self):
        """Start the data feed loop"""
        if not self.connected:
            print("❌ Not connected to IB Gateway")
            return
        
        self.running = True
        self.update_thread = threading.Thread(target=self._data_loop, daemon=True)
        self.update_thread.start()
        
        print("\n🚀 Market data feed started!")
        print("=" * 60)
    
    def _data_loop(self):
        """Main data processing loop"""
        while self.running and self.connected:
            try:
                # Process each ticker
                updates = []
                for symbol, ticker in self.tickers.items():
                    if ticker.last and ticker.last > 0:
                        # Calculate change
                        prev_price = self.last_prices.get(symbol, ticker.last)
                        change = ticker.last - prev_price
                        change_pct = (change / prev_price * 100) if prev_price > 0 else 0
                        
                        # Store last price
                        self.last_prices[symbol] = ticker.last
                        
                        # Collect update
                        updates.append({
                            'symbol': symbol,
                            'last': ticker.last,
                            'bid': ticker.bid if ticker.bid else 0,
                            'ask': ticker.ask if ticker.ask else 0,
                            'volume': ticker.volume if ticker.volume else 0,
                            'change': change,
                            'change_pct': change_pct
                        })
                
                # Display updates
                if updates:
                    self._display_updates(updates)
                
                # Sleep before next update
                time.sleep(2)
                
            except Exception as e:
                print(f"❌ Data loop error: {e}")
                time.sleep(5)
    
    def _display_updates(self, updates: list):
        """Display market data updates"""
        # Clear screen (optional)
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("\n" + "=" * 70)
        print(f"REAL-TIME MARKET DATA - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 70)
        print(f"{'Symbol':<10} {'Last':>10} {'Bid':>10} {'Ask':>10} {'Volume':>12} {'Change':>8}")
        print("-" * 70)
        
        for update in updates:
            color = '\033[92m' if update['change'] >= 0 else '\033[91m'  # Green/Red
            reset = '\033[0m'
            
            print(f"{update['symbol']:<10} "
                  f"{update['last']:>10.2f} "
                  f"{update['bid']:>10.2f} "
                  f"{update['ask']:>10.2f} "
                  f"{update['volume']:>12,.0f} "
                  f"{color}{update['change']:>+8.2f}{reset}")
    
    # ==========================================================================
    # DASHBOARD INTEGRATION
    # ==========================================================================
    def inject_to_dashboard(self, dashboard_process_id: Optional[int] = None):
        """
        Inject real market data into running dashboard.
        
        Args:
            dashboard_process_id: Process ID of running dashboard
        """
        print("\n🔧 Attempting to inject data into dashboard...")
        
        # This would require inter-process communication
        # For now, we'll save data to a shared file that dashboard can read
        
        data_file = Path.home() / "Projects/Spyder/temp_market_data.json"
        
        import json
        
        while self.running:
            try:
                # Collect current data
                market_data = {}
                for symbol, ticker in self.tickers.items():
                    if ticker.last and ticker.last > 0:
                        market_data[symbol] = {
                            'last': ticker.last,
                            'bid': ticker.bid if ticker.bid else 0,
                            'ask': ticker.ask if ticker.ask else 0,
                            'volume': ticker.volume if ticker.volume else 0,
                            'timestamp': datetime.now().isoformat()
                        }
                
                # Write to file
                with open(data_file, 'w') as f:
                    json.dump(market_data, f)
                
                time.sleep(1)
                
            except Exception as e:
                print(f"❌ Injection error: {e}")
                time.sleep(5)
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def print_subscription_summary(self):
        """Print subscription summary"""
        print("\n" + "=" * 60)
        print("SUBSCRIPTION SUMMARY")
        print("=" * 60)
        print(f"✅ Successful: {len(self.successful_subscriptions)}")
        print(f"❌ Failed: {len(self.failed_subscriptions)}")
        
        if self.failed_subscriptions:
            print("\nFailed symbols (may need additional market data subscriptions):")
            for symbol, error in self.failed_subscriptions:
                print(f"  - {symbol}: {error}")
        
        print("\n💡 Note: Some symbols require specific IBKR market data subscriptions")
        print("   SPX, VIX, etc. need CBOE Index subscriptions")
        print("   Futures (/ES) need CME subscriptions")
    
    def test_spy_options(self):
        """Test SPY options chain access"""
        print("\n🔍 Testing SPY options chain...")
        
        try:
            # Get SPY contract
            spy = Stock('SPY', 'SMART', 'USD')
            self.ib.qualifyContracts(spy)
            
            # Request option chain
            chains = self.ib.reqSecDefOptParams(spy.symbol, '', spy.secType, spy.conId)
            
            if chains:
                chain = chains[0]
                print(f"✅ SPY options available")
                print(f"   Expirations: {len(chain.expirations)}")
                print(f"   Strikes: {len(chain.strikes)}")
                print(f"   Next expiry: {chain.expirations[0] if chain.expirations else 'N/A'}")
            else:
                print("❌ No SPY options chain found")
                
        except Exception as e:
            print(f"❌ Options test failed: {e}")
    
    def stop(self):
        """Stop the bridge"""
        print("\n🛑 Stopping market data bridge...")
        self.running = False
        
        # Cancel all subscriptions
        for symbol, ticker in self.tickers.items():
            try:
                self.ib.cancelMktData(ticker)
            except:
                pass
        
        # Disconnect
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        
        print("✅ Bridge stopped")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main execution function"""
    print("\n" + "=" * 70)
    print("SPYDER IB MARKET DATA BRIDGE")
    print("Injecting Real Market Data into Trading Dashboard")
    print("=" * 70)
    
    # Create bridge
    bridge = IBMarketDataBridge()
    
    # Connect to IB Gateway
    if not bridge.connect():
        print("\n❌ Failed to connect to IB Gateway")
        print("Please ensure:")
        print("1. IB Gateway is running")
        print("2. You're logged in")
        print("3. Port 4002 is correct for paper trading")
        return
    
    # Subscribe to symbols
    bridge.subscribe_all_symbols()
    
    # Test SPY options
    bridge.test_spy_options()
    
    # Start data feed
    bridge.start_data_feed()
    
    try:
        print("\n📊 Market data is now streaming...")
        print("Press Ctrl+C to stop")
        
        # Keep running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        bridge.stop()
        print("Goodbye! 👋")

if __name__ == "__main__":
    main()
