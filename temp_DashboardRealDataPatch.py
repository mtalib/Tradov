#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: temp_DashboardRealDataPatch.py
Purpose: Patch the running dashboard to use real IB market data
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-18 Time: 16:35:00

Module Description:
    This module patches the Spyder Trading Dashboard to replace simulated
    data with real market data from IB Gateway. It creates a proper market
    data subscription and updates the dashboard displays with live prices.

USAGE:
    1. First launch your dashboard normally
    2. Then run this patch in a separate terminal:
       python temp_DashboardRealDataPatch.py
    3. The dashboard will start showing real market data
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import sys
import os
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import IB components
from ib_insync import IB, Stock, Index, Future, Contract, util

# ==============================================================================
# CONFIGURATION
# ==============================================================================
IB_HOST = "127.0.0.1"
IB_PORT = 4002  # Paper trading
CLIENT_ID = 888  # Different from dashboard to avoid conflicts

# Shared data file for inter-process communication
DATA_FILE = Path.home() / "Projects/Spyder/real_market_data.json"
CONFIG_FILE = Path.home() / "Projects/Spyder/market_data_config.json"

# Core symbols to monitor
CORE_SYMBOLS = {
    'SPY': Stock('SPY', 'SMART', 'USD'),
    'SPX': Index('SPX', 'CBOE'),
    '/ES': Future('ES', '202503', 'CME'),
    'VIX': Index('VIX', 'CBOE'),
    'QQQ': Stock('QQQ', 'SMART', 'USD'),
    'IWM': Stock('IWM', 'SMART', 'USD'),
    'DIA': Stock('DIA', 'SMART', 'USD'),
}

# ==============================================================================
# DASHBOARD PATCHER
# ==============================================================================
class DashboardRealDataPatcher:
    """Patches dashboard to use real market data"""
    
    def __init__(self):
        self.ib = None
        self.connected = False
        self.tickers = {}
        self.running = False
        
        print("=" * 60)
        print("DASHBOARD REAL DATA PATCHER")
        print("=" * 60)
    
    def setup(self):
        """Setup the patcher"""
        # Create config file to signal dashboard to use real data
        config = {
            'mode': 'REAL',
            'source': 'IB_GATEWAY',
            'client_id': CLIENT_ID,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        
        print("✅ Configuration file created")
        
        # Connect to IB
        return self.connect_ib()
    
    def connect_ib(self) -> bool:
        """Connect to IB Gateway"""
        try:
            print(f"\n🔌 Connecting to IB Gateway...")
            
            self.ib = IB()
            self.ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=10)
            
            if not self.ib.isConnected():
                raise Exception("Connection failed")
            
            self.connected = True
            print(f"✅ Connected with Client ID {CLIENT_ID}")
            
            # Request delayed data
            self.ib.reqMarketDataType(3)
            print("📊 Using delayed market data (free)")
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def subscribe_symbols(self):
        """Subscribe to market data"""
        print("\n📈 Subscribing to symbols...")
        
        for symbol, contract in CORE_SYMBOLS.items():
            try:
                # Qualify contract
                self.ib.qualifyContracts(contract)
                
                # Request market data
                ticker = self.ib.reqMktData(contract, '', False, False)
                self.tickers[symbol] = ticker
                
                print(f"  ✅ {symbol}")
                time.sleep(0.1)
                
            except Exception as e:
                print(f"  ❌ {symbol}: {e}")
    
    def start_feed(self):
        """Start feeding data to dashboard"""
        self.running = True
        
        print("\n🚀 Starting real data feed...")
        print("=" * 60)
        print("Dashboard should now show REAL market data!")
        print("Press Ctrl+C to stop")
        
        while self.running:
            try:
                # Collect data
                market_data = {}
                
                for symbol, ticker in self.tickers.items():
                    if ticker.last and ticker.last > 0:
                        # Calculate changes
                        prev_close = ticker.close if ticker.close else ticker.last
                        change = ticker.last - prev_close
                        change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                        
                        market_data[symbol] = {
                            'last': float(ticker.last),
                            'bid': float(ticker.bid) if ticker.bid else 0,
                            'ask': float(ticker.ask) if ticker.ask else 0,
                            'high': float(ticker.high) if ticker.high else 0,
                            'low': float(ticker.low) if ticker.low else 0,
                            'close': float(ticker.close) if ticker.close else 0,
                            'volume': int(ticker.volume) if ticker.volume else 0,
                            'change': round(change, 2),
                            'change_pct': round(change_pct, 2),
                            'timestamp': datetime.now().isoformat()
                        }
                
                # Write to file
                with open(DATA_FILE, 'w') as f:
                    json.dump(market_data, f, indent=2)
                
                # Display status
                self.display_status(market_data)
                
                # Sleep
                time.sleep(1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(5)
    
    def display_status(self, data: dict):
        """Display current status"""
        # Clear line
        print('\r', end='')
        
        # Show key prices
        status = f"📊 REAL DATA: "
        
        if 'SPY' in data:
            spy = data['SPY']
            color = '🟢' if spy['change'] >= 0 else '🔴'
            status += f"SPY: ${spy['last']:.2f} {color} "
        
        if 'VIX' in data:
            vix = data['VIX']
            status += f"| VIX: {vix['last']:.2f} "
        
        if '/ES' in data:
            es = data['/ES']
            status += f"| /ES: {es['last']:.1f}"
        
        print(status, end='', flush=True)
    
    def stop(self):
        """Stop the patcher"""
        self.running = False
        
        print("\n\n🛑 Stopping...")
        
        # Cancel subscriptions
        for ticker in self.tickers.values():
            try:
                self.ib.cancelMktData(ticker)
            except:
                pass
        
        # Disconnect
        if self.ib and self.ib.isConnected():
            self.ib.disconnect()
        
        # Clean up files
        try:
            DATA_FILE.unlink()
            CONFIG_FILE.unlink()
        except:
            pass
        
        print("✅ Stopped")

# ==============================================================================
# DASHBOARD READER COMPONENT
# ==============================================================================
def create_dashboard_reader():
    """
    Create a component that the dashboard can use to read real data.
    Save this as a module the dashboard can import.
    """
    
    code = '''
# Real Market Data Reader for Dashboard
import json
from pathlib import Path
from datetime import datetime

class RealMarketDataReader:
    """Reads real market data from IB Gateway feed"""
    
    def __init__(self):
        self.data_file = Path.home() / "Projects/Spyder/real_market_data.json"
        self.config_file = Path.home() / "Projects/Spyder/market_data_config.json"
        self.last_data = {}
    
    def is_real_mode(self) -> bool:
        """Check if real mode is active"""
        try:
            if self.config_file.exists():
                with open(self.config_file) as f:
                    config = json.load(f)
                return config.get('mode') == 'REAL'
        except:
            pass
        return False
    
    def get_market_data(self) -> dict:
        """Get latest market data"""
        try:
            if self.data_file.exists():
                with open(self.data_file) as f:
                    self.last_data = json.load(f)
        except:
            pass
        return self.last_data
    
    def get_price(self, symbol: str) -> tuple:
        """Get price for symbol (price, change, change_pct)"""
        data = self.get_market_data()
        if symbol in data:
            sym_data = data[symbol]
            return (
                sym_data.get('last', 0),
                sym_data.get('change', 0),
                sym_data.get('change_pct', 0)
            )
        return (0, 0, 0)
'''
    
    # Save the reader module
    reader_file = Path.home() / "Projects/Spyder/SpyderG_GUI/temp_RealDataReader.py"
    with open(reader_file, 'w') as f:
        f.write(code)
    
    print(f"✅ Created reader module: {reader_file}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main execution"""
    print("\n" + "=" * 70)
    print("SPYDER DASHBOARD REAL DATA PATCHER")
    print("=" * 70)
    
    # Create reader component
    create_dashboard_reader()
    
    # Create patcher
    patcher = DashboardRealDataPatcher()
    
    # Setup
    if not patcher.setup():
        print("\n❌ Setup failed")
        return
    
    # Subscribe
    patcher.subscribe_symbols()
    
    try:
        # Start feed
        patcher.start_feed()
        
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        patcher.stop()

if __name__ == "__main__":
    main()
