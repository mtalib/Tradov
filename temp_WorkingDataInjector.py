#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Working Live Data Injector
Fixes client ID conflicts and properly injects real market data into dashboard
"""

import sys
import os
import time
import json
import threading
from pathlib import Path
from datetime import datetime
import signal

# Third-party imports
try:
    from ib_insync import IB, Stock, Index, Future
    print("✅ ib_insync imported successfully")
except ImportError as e:
    print(f"❌ ib_insync import failed: {e}")
    sys.exit(1)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 4002  # Paper trading port
CLIENT_ID = 777  # Different from dashboard (123) and previous attempts (555)

# Market data symbols to inject
SYMBOLS = {
    'SPY': Stock('SPY', 'SMART', 'USD'),
    'QQQ': Stock('QQQ', 'SMART', 'USD'), 
    'IWM': Stock('IWM', 'SMART', 'USD'),
    'VIX': Index('VIX', 'CBOE'),
    'DIA': Stock('DIA', 'SMART', 'USD'),
    'TLT': Stock('TLT', 'SMART', 'USD'),
    'GLD': Stock('GLD', 'SMART', 'USD')
}

# Base prices for change calculation
BASE_PRICES = {
    'SPY': 585.0,
    'QQQ': 485.0,
    'IWM': 225.0,
    'VIX': 15.0,
    'DIA': 425.0,
    'TLT': 92.0,
    'GLD': 195.0
}

# Data directory for dashboard integration
DATA_DIR = Path.home() / "Projects/Spyder/market_data"

# ==============================================================================
# WORKING DATA INJECTOR CLASS
# ==============================================================================
class WorkingDataInjector:
    """
    Working live data injector that properly connects to IB Gateway
    and feeds real market data to the Spyder dashboard
    """
    
    def __init__(self):
        self.ib = None
        self.connected = False
        self.tickers = {}
        self.running = False
        self.last_prices = {}
        self.update_count = 0
        
        # Setup data directory
        DATA_DIR.mkdir(exist_ok=True)
        
        # Setup signal handlers for clean shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("=" * 70)
        print("SPYDER WORKING LIVE DATA INJECTOR")
        print("=" * 70)
        print(f"Client ID: {CLIENT_ID}")
        print(f"Target: {IB_HOST}:{IB_PORT}")
        print(f"Data Directory: {DATA_DIR}")
        print("=" * 70)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\n🛑 Shutdown signal received...")
        self.stop()
        sys.exit(0)
    
    def connect(self) -> bool:
        """Connect to IB Gateway with proper error handling"""
        try:
            print(f"\n🔌 Connecting to IB Gateway...")
            print(f"   Host: {IB_HOST}")
            print(f"   Port: {IB_PORT}")
            print(f"   Client ID: {CLIENT_ID}")
            
            # Create IB instance
            self.ib = IB()
            
            # Set error callback
            self.ib.errorEvent += self._on_error
            
            # Connect with specific timeout and settings
            self.ib.connect(
                host=IB_HOST,
                port=IB_PORT,
                clientId=CLIENT_ID,
                timeout=15,
                readonly=False
            )
            
            # Verify connection
            if not self.ib.isConnected():
                raise Exception("Connection verification failed")
            
            self.connected = True
            
            # Get account information
            accounts = self.ib.managedAccounts()
            if accounts:
                print(f"✅ Connected to account: {accounts[0]}")
            else:
                print("✅ Connected (no account info available)")
            
            # Configure market data type
            self.ib.reqMarketDataType(3)  # 3 = delayed data (free)
            print("📊 Configured for delayed market data")
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self.connected = False
            return False
    
    def _on_error(self, reqId, errorCode, errorString, contract):
        """Handle IB errors"""
        # Only log significant errors, ignore info messages
        if errorCode < 2000:
            print(f"⚠️  IB Error {errorCode}: {errorString}")
    
    def subscribe_symbols(self) -> bool:
        """Subscribe to market data for all symbols"""
        if not self.connected:
            print("❌ Not connected to IB Gateway")
            return False
        
        print("\n📈 Subscribing to market data...")
        print("-" * 50)
        
        success_count = 0
        
        for symbol, contract in SYMBOLS.items():
            try:
                # Qualify the contract first
                qualified = self.ib.qualifyContracts(contract)
                if not qualified:
                    print(f"❌ {symbol:6} - Contract qualification failed")
                    continue
                
                # Request market data
                ticker = self.ib.reqMktData(
                    contract,
                    '',     # Generic tick list
                    False,  # Not snapshot
                    False   # Not regulatory snapshot
                )
                
                # Store ticker
                self.tickers[symbol] = ticker
                
                # Initialize base price for change calculation
                if symbol in BASE_PRICES:
                    self.last_prices[symbol] = BASE_PRICES[symbol]
                
                print(f"✅ {symbol:6} - Subscribed successfully")
                success_count += 1
                
                # Small delay to avoid overwhelming the API
                time.sleep(0.2)
                
            except Exception as e:
                print(f"❌ {symbol:6} - Subscription failed: {e}")
        
        print("-" * 50)
        print(f"📊 Successfully subscribed to {success_count}/{len(SYMBOLS)} symbols")
        
        return success_count > 0
    
    def start_data_feed(self):
        """Start the continuous data feed"""
        if not self.connected:
            print("❌ Cannot start data feed - not connected")
            return
        
        if not self.tickers:
            print("❌ Cannot start data feed - no subscriptions")
            return
        
        self.running = True
        
        print("\n🚀 Starting live data feed...")
        print("📊 Real market data will be saved to:", DATA_DIR / "live_data.json")
        print("🔄 Dashboard should now display real prices!")
        print("=" * 70)
        print("Press Ctrl+C to stop...")
        print("=" * 70)
        
        # Wait a moment for initial data
        time.sleep(2)
        
        # Start the main update loop
        try:
            while self.running:
                self._update_market_data()
                time.sleep(1)  # Update every second
                
        except KeyboardInterrupt:
            print("\n🛑 Keyboard interrupt received")
        except Exception as e:
            print(f"\n❌ Error in data feed: {e}")
        finally:
            self.stop()
    
    def _update_market_data(self):
        """Update market data and save to file"""
        if not self.running or not self.connected:
            return
        
        # Collect current market data
        market_data = {}
        status_line = "LIVE: "
        updates_found = 0
        
        for symbol, ticker in self.tickers.items():
            try:
                # Check if we have valid price data
                current_price = None
                bid = getattr(ticker, 'bid', None)
                ask = getattr(ticker, 'ask', None)
                last = getattr(ticker, 'last', None)
                volume = getattr(ticker, 'volume', None) or 0
                
                # Use last price if available, otherwise midpoint of bid/ask
                if last and last > 0:
                    current_price = last
                elif bid and ask and bid > 0 and ask > 0:
                    current_price = (bid + ask) / 2.0
                
                if current_price and current_price > 0:
                    # Calculate change
                    prev_price = self.last_prices.get(symbol, current_price)
                    change = current_price - prev_price
                    change_pct = (change / prev_price * 100) if prev_price > 0 else 0.0
                    
                    # Create market data entry
                    market_data[symbol] = {
                        'symbol': symbol,
                        'last': round(current_price, 2),
                        'bid': round(bid, 2) if bid and bid > 0 else 0,
                        'ask': round(ask, 2) if ask and ask > 0 else 0,
                        'volume': int(volume) if volume else 0,
                        'change': round(change, 2),
                        'change_pct': round(change_pct, 2),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # Update last price
                    self.last_prices[symbol] = current_price
                    updates_found += 1
                    
                    # Add to status line for SPY
                    if symbol == 'SPY':
                        change_sign = "+" if change >= 0 else ""
                        status_line += f"SPY: ${current_price:.2f} ({change_sign}{change_pct:.2f}%) "
                
            except Exception as e:
                # Silently continue on individual symbol errors
                pass
        
        # Save data if we have updates
        if market_data:
            try:
                # Save to file for dashboard consumption
                output_file = DATA_DIR / "live_data.json"
                with open(output_file, 'w') as f:
                    json.dump(market_data, f, indent=2)
                
                # Also save a backup
                backup_file = DATA_DIR / "live_data_backup.json"
                with open(backup_file, 'w') as f:
                    json.dump(market_data, f, indent=2)
                
                self.update_count += 1
                
                # Print status (every 10 updates to avoid spam)
                if self.update_count % 10 == 0:
                    print(f"#{self.update_count:4d} | {status_line}| Updates: {updates_found}")
                
            except Exception as e:
                print(f"❌ Error saving data: {e}")
    
    def stop(self):
        """Stop the data injector"""
        print("\n🛑 Stopping data injector...")
        
        self.running = False
        
        # Cancel market data subscriptions
        if self.ib and self.connected:
            for symbol, ticker in self.tickers.items():
                try:
                    self.ib.cancelMktData(ticker)
                except:
                    pass
            
            # Disconnect
            try:
                self.ib.disconnect()
                print("✅ Disconnected from IB Gateway")
            except:
                pass
        
        self.connected = False
        self.tickers.clear()
        
        print("✅ Data injector stopped")
    
    def get_status(self) -> dict:
        """Get current status"""
        return {
            'connected': self.connected,
            'running': self.running,
            'symbols_subscribed': len(self.tickers),
            'updates_sent': self.update_count,
            'client_id': CLIENT_ID
        }

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main entry point"""
    print("\n" + "=" * 70)
    print("SPYDER WORKING LIVE DATA INJECTOR")
    print("=" * 70)
    print("This will inject REAL market data into your dashboard")
    print("Make sure your dashboard is running first!")
    print("=" * 70)
    
    # Create injector
    injector = WorkingDataInjector()
    
    try:
        # Step 1: Connect to IB Gateway
        if not injector.connect():
            print("\n❌ Failed to connect to IB Gateway")
            print("\nTroubleshooting:")
            print("1. Ensure IB Gateway is running")
            print("2. Verify you're logged in")
            print("3. Check API settings are enabled")
            print("4. Try a different client ID if conflicts persist")
            return 1
        
        # Step 2: Subscribe to symbols
        if not injector.subscribe_symbols():
            print("\n❌ Failed to subscribe to any symbols")
            return 1
        
        # Step 3: Start data feed
        injector.start_data_feed()
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1
    
    finally:
        # Clean shutdown
        injector.stop()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())