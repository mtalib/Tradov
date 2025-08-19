#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Super Simple Real Data Dashboard
Just run this instead of your normal dashboard - automatically uses real IB data!
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

# Add Spyder to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import the original dashboard
from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

class SuperSimpleRealDashboard(SpyderTradingDashboard):
    """Dashboard that automatically shows real market data"""
    
    def __init__(self):
        print("🔥 Initializing REAL DATA dashboard...")
        super().__init__()
        
        self.real_data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self.real_data_active = False
        
        # Setup real data immediately
        self.setup_real_data()
        
        print("✅ REAL DATA DASHBOARD READY!")
        print("✅ Will show real IB Gateway prices if available")
    
    def setup_real_data(self):
        """Setup real data override"""
        
        # Check if real data is available
        if self.real_data_file.exists():
            print("✅ Real data file found - activating real prices!")
            self.real_data_active = True
            
            # Stop the original simulation
            self.stop_simulation()
            
            # Start real data updates
            self.start_real_data_updates()
            
            # Immediate update
            self.update_with_real_data()
            
        else:
            print("⚠️  No real data file found")
            print("   Start injector: python temp_WorkingDataInjector.py")
            print("   Dashboard will use simulation until real data is available")
            
            # Check periodically for real data to become available
            self.check_timer = QTimer()
            self.check_timer.timeout.connect(self.check_for_real_data)
            self.check_timer.start(5000)  # Check every 5 seconds
    
    def stop_simulation(self):
        """Stop the original simulation"""
        try:
            # Stop market worker simulation
            if hasattr(self, 'market_worker'):
                worker = self.market_worker
                
                if hasattr(worker, 'update_timer') and worker.update_timer:
                    worker.update_timer.stop()
                    print("✅ Stopped simulation timer")
                
                if hasattr(worker, 'stale_data_timer') and worker.stale_data_timer:
                    worker.stale_data_timer.stop()
                    print("✅ Stopped stale data timer")
                    
                # Mark as using real data
                worker.ib_connected = True
                
            # Slow down automation messages
            if hasattr(self, 'automation_timer'):
                self.automation_timer.setInterval(15000)  # Every 15 seconds instead of 3
                
            print("✅ Simulation stopped")
            
        except Exception as e:
            print(f"⚠️  Could not fully stop simulation: {e}")
    
    def start_real_data_updates(self):
        """Start real data updates"""
        self.real_data_timer = QTimer()
        self.real_data_timer.timeout.connect(self.update_with_real_data)
        self.real_data_timer.start(1000)  # Update every second
        print("✅ Real data updates started")
    
    def check_for_real_data(self):
        """Check if real data becomes available"""
        if self.real_data_file.exists() and not self.real_data_active:
            print("🔥 Real data detected - switching from simulation!")
            self.check_timer.stop()
            self.setup_real_data()
    
    def update_with_real_data(self):
        """Update dashboard with real market data"""
        try:
            if not self.real_data_file.exists():
                return
            
            # Read real data
            with open(self.real_data_file, 'r') as f:
                live_data = json.load(f)
            
            if not live_data:
                return
            
            # Convert to dashboard format
            dashboard_data = {}
            for symbol, data in live_data.items():
                dashboard_data[symbol] = {
                    'symbol': data['symbol'],
                    'last': data['last'],
                    'change': data['change'],
                    'change_pct': data['change_pct'],
                    'timestamp': datetime.now(),
                    'bid': data.get('bid', 0),
                    'ask': data.get('ask', 0),
                    'volume': data.get('volume', 0)
                }
            
            # Update dashboard market data
            self.market_data.update(dashboard_data)
            
            # Update symbol widgets directly
            self.update_symbol_widgets(dashboard_data)
            
            # Update toolbar indices
            self.update_toolbar_indices(dashboard_data)
            
            # Update status
            self.update_status_for_real_data()
            
        except Exception as e:
            print(f"❌ Error updating real data: {e}")
    
    def update_symbol_widgets(self, data):
        """Update symbol widgets with real data"""
        try:
            for symbol, market_data in data.items():
                if symbol in self.symbol_widgets:
                    widget = self.symbol_widgets[symbol]
                    
                    # Update price
                    if hasattr(widget, 'price_label'):
                        widget.price_label.setText(f"{market_data['last']:.2f}")
                    
                    # Update change with color
                    if hasattr(widget, 'change_label'):
                        change = market_data['change']
                        sign = "+" if change >= 0 else ""
                        widget.change_label.setText(f"{sign}{change:.2f}")
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        widget.change_label.setStyleSheet(f"color: {color};")
                    
                    # Update percentage with color
                    if hasattr(widget, 'pct_label'):
                        pct = market_data['change_pct']
                        sign = "+" if pct >= 0 else ""
                        widget.pct_label.setText(f"{sign}{pct:.2f}%")
                        color = "#00ff41" if pct >= 0 else "#ff1744"
                        widget.pct_label.setStyleSheet(f"color: {color};")
        
        except Exception as e:
            print(f"⚠️  Error updating widgets: {e}")
    
    def update_toolbar_indices(self, data):
        """Update toolbar indices with real data"""
        try:
            # Update SPX from SPY (SPY * 10)
            if 'SPY' in data:
                spy_data = data['SPY']
                
                if hasattr(self, 'spx_value'):
                    self.spx_value.setText(f" {spy_data['last'] * 10:.0f}")
                
                if hasattr(self, 'spx_change'):
                    change = spy_data['change'] * 10
                    pct = spy_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    self.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.spx_change.setStyleSheet(f"color: {color};")
            
            # Update NDX from QQQ (QQQ * 35)
            if 'QQQ' in data:
                qqq_data = data['QQQ']
                
                if hasattr(self, 'ndx_value'):
                    self.ndx_value.setText(f" {qqq_data['last'] * 35:.0f}")
                
                if hasattr(self, 'ndx_change'):
                    change = qqq_data['change'] * 35
                    pct = qqq_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    self.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.ndx_change.setStyleSheet(f"color: {color};")
            
            # Update DJI from DIA (DIA * 98)
            if 'DIA' in data:
                dia_data = data['DIA']
                
                if hasattr(self, 'dji_value'):
                    self.dji_value.setText(f" {dia_data['last'] * 98:.0f}")
                
                if hasattr(self, 'dji_change'):
                    change = dia_data['change'] * 98
                    pct = dia_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    self.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    self.dji_change.setStyleSheet(f"color: {color};")
        
        except Exception as e:
            print(f"⚠️  Error updating toolbar: {e}")
    
    def update_status_for_real_data(self):
        """Update status indicators for real data"""
        try:
            # Update market data status
            if hasattr(self, 'market_data_status'):
                self.market_data_status.setText("LIVE - REAL")
                self.market_data_status.setStyleSheet("color: #00ff41;")
            
            # Update connection status
            if hasattr(self, 'connection_label'):
                self.connection_label.setText("IB CONNECTED - REAL DATA")
                self.connection_label.setStyleSheet("color: #00ff41;")
            
        except Exception as e:
            pass  # Not critical
    
    def add_system_log(self, message: str):
        """Override to add real data indicator"""
        super().add_system_log(message)
        
        # Add initial real data log
        if self.real_data_active and not hasattr(self, '_real_data_logged'):
            super().add_system_log("🔥 REAL MARKET DATA ACTIVE - IB Gateway prices")
            super().add_automation_log("Real-time market data from Interactive Brokers")
            self._real_data_logged = True

def main():
    """Main entry point"""
    
    print("=" * 70)
    print("🔥 SPYDER SUPER SIMPLE REAL DATA DASHBOARD")
    print("=" * 70)
    print("This dashboard automatically uses real IB Gateway data!")
    print("No console access needed - just run and go!")
    print("=" * 70)
    
    # Check if data injector is running
    data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
    if data_file.exists():
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
            spy_price = data.get('SPY', {}).get('last', 'N/A')
            print(f"✅ Real data detected - SPY: ${spy_price}")
        except:
            print("⚠️  Real data file exists but couldn't read it")
    else:
        print("⚠️  No real data detected")
        print("   Start injector: python temp_WorkingDataInjector.py")
        print("   Dashboard will start with simulation and switch to real data when available")
    
    print("=" * 70)
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Create and show dashboard
    dashboard = SuperSimpleRealDashboard()
    dashboard.show()
    
    # Run application
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
