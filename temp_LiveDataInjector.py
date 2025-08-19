#!/usr/bin/env python3
"""SPYDER - Live Data Injector"""

import sys
import os
import time
import json
from pathlib import Path
from datetime import datetime
from ib_insync import IB, Stock, Index, Future

# Configuration
IB_HOST = "127.0.0.1"
IB_PORT = 4002
CLIENT_ID = 555

# Symbols
SYMBOLS = {
    'SPY': Stock('SPY', 'SMART', 'USD'),
    'QQQ': Stock('QQQ', 'SMART', 'USD'),
    'IWM': Stock('IWM', 'SMART', 'USD'),
    'VIX': Index('VIX', 'CBOE'),
}

class LiveDataInjector:
    def __init__(self):
        self.ib = IB()
        self.tickers = {}
        self.last_prices = {}
        
    def connect(self):
        print("Connecting to IB Gateway...")
        self.ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID, timeout=10)
        if self.ib.isConnected():
            print(f"Connected! Account: {self.ib.managedAccounts()[0]}")
            self.ib.reqMarketDataType(3)  # Delayed data
            return True
        return False
    
    def subscribe(self):
        print("\nSubscribing to symbols...")
        for symbol, contract in SYMBOLS.items():
            try:
                self.ib.qualifyContracts(contract)
                ticker = self.ib.reqMktData(contract, '', False, False)
                self.tickers[symbol] = ticker
                print(f"  ✓ {symbol}")
                time.sleep(0.1)
            except Exception as e:
                print(f"  ✗ {symbol}: {e}")
    
    def run(self):
        print("\n🚀 INJECTING REAL DATA")
        print("=" * 60)
        
        # Create data directory
        data_dir = Path.home() / "Projects/Spyder/market_data"
        data_dir.mkdir(exist_ok=True)
        
        while True:
            try:
                market_data = {}
                status = "LIVE: "
                
                for symbol, ticker in self.tickers.items():
                    if ticker.last and ticker.last > 0:
                        prev = self.last_prices.get(symbol, ticker.last)
                        change = ticker.last - prev
                        change_pct = (change / prev * 100) if prev > 0 else 0
                        self.last_prices[symbol] = ticker.last
                        
                        market_data[symbol] = {
                            'symbol': symbol,
                            'last': ticker.last,
                            'bid': ticker.bid or 0,
                            'ask': ticker.ask or 0,
                            'volume': ticker.volume or 0,
                            'change': round(change, 2),
                            'change_pct': round(change_pct, 2),
                            'timestamp': datetime.now().isoformat()
                        }
                        
                        if symbol == 'SPY':
                            status += f"SPY: ${ticker.last:.2f} "
                
                # Save data
                with open(data_dir / "live_data.json", 'w') as f:
                    json.dump(market_data, f, indent=2)
                
                print(f'\r{status}', end='', flush=True)
                time.sleep(1)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}")
                time.sleep(5)
    
    def stop(self):
        print("\n\nStopping...")
        for ticker in self.tickers.values():
            try:
                self.ib.cancelMktData(ticker)
            except:
                pass
        if self.ib.isConnected():
            self.ib.disconnect()
        print("Stopped")

def main():
    print("\n" + "=" * 60)
    print("SPYDER LIVE DATA INJECTOR")
    print("=" * 60)
    
    injector = LiveDataInjector()
    
    if not injector.connect():
        print("Failed to connect to IB Gateway")
        return
    
    injector.subscribe()
    
    print("\nPress Ctrl+C to stop")
    
    try:
        injector.run()
    except KeyboardInterrupt:
        injector.stop()

if __name__ == "__main__":
    main()
