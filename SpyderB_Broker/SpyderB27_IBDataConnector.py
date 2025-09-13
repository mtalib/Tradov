#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB27_IBDataConnector.py
Purpose: Real-time IB Gateway market data integration for dashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-12 Time: 21:30:00
"""

import json
from pathlib import Path
from datetime import datetime
import logging
import random

from ib_async import IB, Stock
from PySide6.QtCore import QObject, Signal, QTimer

class IBDataConnector(QObject):
    """Handles real-time market data from IB Gateway"""
    
    data_received = Signal(dict)
    connection_status = Signal(bool, str)
    error_occurred = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.ib = None
        self.connected = False
        self.subscriptions = {}
        self.logger = logging.getLogger(__name__)
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        
    def connect_to_ib(self):
        """Connect to native IB Gateway with unique client ID"""
        try:
            # Use random client ID to avoid conflicts
            client_id = random.randint(10, 999)
            
            self.ib = IB()
            self.ib.connect('127.0.0.1', 4002, clientId=client_id)
            
            self.connected = True
            print(f"✅ Connected with client ID {client_id}! Server: {self.ib.client.serverVersion()}")
            
            # Subscribe immediately
            self.subscribe_symbols()
            
            # Setup timer for updates
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_prices)
            self.timer.start(1000)  # Update every second
            
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def subscribe_symbols(self):
        """Subscribe to market data"""
        symbols = {
            'SPY': Stock('SPY', 'SMART', 'USD'),
            'QQQ': Stock('QQQ', 'SMART', 'USD'),
            'IWM': Stock('IWM', 'SMART', 'USD'),
            'DIA': Stock('DIA', 'SMART', 'USD'),
            'TLT': Stock('TLT', 'SMART', 'USD'),
            'GLD': Stock('GLD', 'SMART', 'USD')
        }
        
        for symbol, contract in symbols.items():
            try:
                self.ib.qualifyContracts(contract)
                ticker = self.ib.reqMktData(contract, '', False, False)
                self.subscriptions[symbol] = ticker
                print(f"✅ Subscribed to {symbol}")
            except Exception as e:
                print(f"❌ Failed {symbol}: {e}")
    
    def update_prices(self):
        """Update prices from IB"""
        try:
            self.ib.sleep(0)  # Process IB events
            
            for symbol, ticker in self.subscriptions.items():
                if ticker.last:
                    data = {
                        symbol: {
                            'symbol': symbol,
                            'last': float(ticker.last),
                            'bid': float(ticker.bid) if ticker.bid else ticker.last,
                            'ask': float(ticker.ask) if ticker.ask else ticker.last,
                            'volume': int(ticker.volume) if ticker.volume else 0,
                            'change': 0.0,
                            'change_pct': 0.0,
                            'timestamp': datetime.now().isoformat()
                        }
                    }
                    
                    if ticker.close:
                        data[symbol]['change'] = ticker.last - ticker.close
                        data[symbol]['change_pct'] = ((ticker.last / ticker.close - 1) * 100)
                    
                    self.data_received.emit(data)
                    print(f"📊 {symbol}: ${ticker.last:.2f}")
                    
        except Exception as e:
            print(f"Update error: {e}")

def patch_dashboard_with_ib_data(dashboard):
    """Simple patch function"""
    print("🔥 Patching dashboard with IB data...")
    
    connector = IBDataConnector()
    
    def update_ui(data):
        for symbol, info in data.items():
            if symbol in dashboard.symbol_widgets:
                widget = dashboard.symbol_widgets[symbol]
                widget.price_label.setText(f"{info['last']:.2f}")
                
                change = info['change']
                pct = info['change_pct']
                
                color = "#00ff41" if change >= 0 else "#ff1744"
                widget.change_label.setText(f"{change:+.2f}")
                widget.change_label.setStyleSheet(f"color: {color};")
                widget.pct_label.setText(f"{pct:+.2f}%")
                widget.pct_label.setStyleSheet(f"color: {color};")
    
    connector.data_received.connect(update_ui)
    
    if connector.connect_to_ib():
        dashboard.add_system_log("✅ IB REAL DATA CONNECTED")
    
    return connector
