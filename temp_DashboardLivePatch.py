#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Dashboard Live Data Patch
Patches the running dashboard to use real market data from injector
"""

import sys
import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime, timedelta
from PyQt6.QtCore import QTimer, pyqtSignal, QObject

# ==============================================================================
# CONFIGURATION
# ==============================================================================
DATA_DIR = Path.home() / "Projects/Spyder/market_data"
LIVE_DATA_FILE = DATA_DIR / "live_data.json"
CHECK_INTERVAL = 1000  # Check for updates every 1 second

# ==============================================================================
# LIVE DATA PATCH CLASS
# ==============================================================================
class DashboardLivePatch(QObject):
    """
    Patches the dashboard to use real market data from the injector
    """
    
    # Signal to update dashboard with real data
    data_updated = pyqtSignal(dict)
    
    def __init__(self, dashboard):
        super().__init__()
        self.dashboard = dashboard
        self.active = False
        self.last_update = None
        self.update_count = 0
        
        # Setup timer for checking data file
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_for_updates)
        
        # Connect to dashboard's data update signal
        self.data_updated.connect(self._inject_real_data)
        
        print("=" * 60)
        print("DASHBOARD LIVE DATA PATCH")
        print("=" * 60)
        print(f"Monitoring: {LIVE_DATA_FILE}")
        
    def start(self):
        """Start monitoring for live data"""
        # Ensure data directory exists
        DATA_DIR.mkdir(exist_ok=True)
        
        # Check if live data file exists
        if LIVE_DATA_FILE.exists():
            print("✅ Live data file found - starting patch")
            self.active = True
            self.check_timer.start(CHECK_INTERVAL)
            
            # Immediately load data
            self._check_for_updates()
            
            # Update dashboard status
            self.dashboard.add_system_log("🔄 Live data patch activated")
            self.dashboard.add_automation_log("Real market data feed active")
            
        else:
            print("⚠️  Live data file not found")
            print("   Start the data injector first:")
            print("   python temp_WorkingDataInjector.py")
            
            # Check periodically for the file to appear
            self.check_timer.start(5000)  # Check every 5 seconds
    
    def stop(self):
        """Stop the patch"""
        self.active = False
        self.check_timer.stop()
        print("✅ Live data patch stopped")
    
    def _check_for_updates(self):
        """Check if live data file has been updated"""
        try:
            if not LIVE_DATA_FILE.exists():
                if self.active:
                    # File disappeared
                    self.active = False
                    self.dashboard.add_system_log("⚠️ Live data file disappeared")
                return
            
            # Check file modification time
            file_time = datetime.fromtimestamp(LIVE_DATA_FILE.stat().st_mtime)
            
            if self.last_update is None or file_time > self.last_update:
                self.last_update = file_time
                self._load_and_inject_data()
                
                # If we weren't active before, we are now
                if not self.active:
                    self.active = True
                    self.dashboard.add_system_log("✅ Live data feed detected")
                    print("✅ Live data feed active!")
        
        except Exception as e:
            if self.active:
                print(f"❌ Error checking live data: {e}")
    
    def _load_and_inject_data(self):
        """Load data from file and inject into dashboard"""
        try:
            with open(LIVE_DATA_FILE, 'r') as f:
                live_data = json.load(f)
            
            if live_data:
                # Convert to dashboard format
                dashboard_data = self._convert_to_dashboard_format(live_data)
                
                # Emit signal to update dashboard
                self.data_updated.emit(dashboard_data)
                
                self.update_count += 1
                
                # Log every 30 updates to avoid spam
                if self.update_count % 30 == 0:
                    spy_price = live_data.get('SPY', {}).get('last', 'N/A')
                    self.dashboard.add_system_log(f"📊 Live data update #{self.update_count} - SPY: ${spy_price}")
        
        except Exception as e:
            print(f"❌ Error loading live data: {e}")
    
    def _convert_to_dashboard_format(self, live_data):
        """Convert live data to dashboard format"""
        dashboard_data = {}
        
        for symbol, data in live_data.items():
            dashboard_data[symbol] = {
                'symbol': data['symbol'],
                'last': data['last'],
                'change': data['change'],
                'change_pct': data['change_pct'],
                'timestamp': datetime.fromisoformat(data['timestamp']),
                'bid': data.get('bid', 0),
                'ask': data.get('ask', 0),
                'volume': data.get('volume', 0)
            }
        
        return dashboard_data
    
    def _inject_real_data(self, real_data):
        """Inject real data into dashboard components"""
        try:
            # Update the dashboard's market data
            if hasattr(self.dashboard, 'market_data'):
                self.dashboard.market_data.update(real_data)
            
            # Update symbol widgets if they exist
            if hasattr(self.dashboard, 'symbol_widgets'):
                for symbol, data in real_data.items():
                    if symbol in self.dashboard.symbol_widgets:
                        widget = self.dashboard.symbol_widgets[symbol]
                        if hasattr(widget, 'update_data'):
                            widget.update_data(data)
            
            # Force chart update for SPY if it exists
            if 'SPY' in real_data and hasattr(self.dashboard, 'update_chart'):
                # Update chart with new SPY data
                try:
                    self.dashboard.update_chart()
                except:
                    pass  # Chart update might fail, that's ok
            
            # Update toolbar indices if they exist
            self._update_toolbar_indices(real_data)
            
        except Exception as e:
            print(f"❌ Error injecting real data: {e}")
    
    def _update_toolbar_indices(self, real_data):
        """Update toolbar index displays"""
        try:
            # Map symbols to toolbar labels
            symbol_mappings = {
                'SPY': ('spx_value', 'spx_change'),  # Use SPY for SPX display
                'DIA': ('dji_value', 'dji_change'),  # Use DIA for DJI display  
                'QQQ': ('ndx_value', 'ndx_change')   # Use QQQ for NDX display
            }
            
            for symbol, (value_attr, change_attr) in symbol_mappings.items():
                if symbol in real_data:
                    data = real_data[symbol]
                    
                    # Update value label
                    if hasattr(self.dashboard, value_attr):
                        value_label = getattr(self.dashboard, value_attr)
                        if symbol == 'SPY':
                            # Scale SPY to SPX (roughly SPY * 10)
                            scaled_value = data['last'] * 10
                            value_label.setText(f" {scaled_value:.2f}")
                        else:
                            value_label.setText(f" {data['last']:.2f}")
                    
                    # Update change label
                    if hasattr(self.dashboard, change_attr):
                        change_label = getattr(self.dashboard, change_attr)
                        change = data['change']
                        change_pct = data['change_pct']
                        sign = "+" if change >= 0 else ""
                        change_label.setText(f"  {sign}{change:.2f}  {sign}{change_pct:.1f}%")
                        
                        # Update color
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        change_label.setStyleSheet(f"color: {color};")
        
        except Exception as e:
            # Toolbar update is not critical
            pass

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def patch_dashboard(dashboard):
    """
    Convenience function to patch a dashboard instance
    
    Args:
        dashboard: Dashboard instance to patch
        
    Returns:
        DashboardLivePatch: Patch instance
    """
    patch = DashboardLivePatch(dashboard)
    patch.start()
    return patch

def check_live_data_status():
    """Check if live data is available"""
    print("\n" + "=" * 50)
    print("LIVE DATA STATUS CHECK")
    print("=" * 50)
    
    # Check if data file exists
    if LIVE_DATA_FILE.exists():
        # Check file age
        file_time = datetime.fromtimestamp(LIVE_DATA_FILE.stat().st_mtime)
        age = datetime.now() - file_time
        
        print(f"✅ Live data file found")
        print(f"📅 Last updated: {file_time.strftime('%H:%M:%S')}")
        print(f"⏰ Age: {age.total_seconds():.1f} seconds")
        
        # Try to read the data
        try:
            with open(LIVE_DATA_FILE, 'r') as f:
                data = json.load(f)
            
            print(f"📊 Symbols available: {len(data)}")
            
            # Show SPY data if available
            if 'SPY' in data:
                spy = data['SPY']
                print(f"📈 SPY: ${spy['last']:.2f} ({spy['change']:+.2f}, {spy['change_pct']:+.2f}%)")
            
            if age.total_seconds() < 10:
                print("✅ Data is FRESH - injector is working!")
            else:
                print("⚠️  Data is STALE - injector may have stopped")
        
        except Exception as e:
            print(f"❌ Error reading data file: {e}")
    
    else:
        print("❌ Live data file not found")
        print("   Start the data injector:")
        print("   python temp_WorkingDataInjector.py")
    
    print("=" * 50)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("DASHBOARD LIVE DATA PATCH")
    print("=" * 40)
    print("This module patches the dashboard to use real data.")
    print("Import this in your dashboard or run the injector separately.")
    print()
    
    # Show current status
    check_live_data_status()
    
    print("\nUsage:")
    print("1. Start dashboard")
    print("2. Run: python temp_WorkingDataInjector.py")
    print("3. Dashboard will automatically show real data!")
