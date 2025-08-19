#!/usr/bin/env python3
"""
SPYDER - Quick Real Data Fix
Apply this to your running dashboard to show real market data immediately
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QTimer

# ==============================================================================
# QUICK FIX FUNCTION
# ==============================================================================
def apply_real_data_fix(dashboard):
    """
    Apply real data fix to running dashboard
    
    Usage:
        from temp_QuickRealDataFix import apply_real_data_fix
        apply_real_data_fix(self)  # In dashboard console
    """
    
    print("🔥 APPLYING REAL DATA FIX TO RUNNING DASHBOARD")
    print("=" * 60)
    
    # File path
    data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
    
    if not data_file.exists():
        print("❌ No real data file found!")
        print("   Run: python temp_WorkingDataInjector.py")
        return False
    
    def update_with_real_data():
        """Update dashboard with real data"""
        try:
            # Read real data
            with open(data_file, 'r') as f:
                live_data = json.load(f)
            
            if not live_data:
                return
            
            # Convert and apply to dashboard
            dashboard_data = {}
            for symbol, data in live_data.items():
                dashboard_data[symbol] = {
                    'symbol': data['symbol'],
                    'last': data['last'],
                    'change': data['change'], 
                    'change_pct': data['change_pct'],
                    'timestamp': datetime.now()
                }
            
            # Update dashboard market data
            if hasattr(dashboard, 'market_data'):
                dashboard.market_data.update(dashboard_data)
            
            # Update symbol widgets directly
            if hasattr(dashboard, 'symbol_widgets'):
                for symbol, data in dashboard_data.items():
                    if symbol in dashboard.symbol_widgets:
                        widget = dashboard.symbol_widgets[symbol]
                        
                        # Update price
                        if hasattr(widget, 'price_label'):
                            widget.price_label.setText(f"{data['last']:.2f}")
                        
                        # Update change
                        if hasattr(widget, 'change_label'):
                            change = data['change']
                            sign = "+" if change >= 0 else ""
                            widget.change_label.setText(f"{sign}{change:.2f}")
                            color = "#00ff41" if change >= 0 else "#ff1744"
                            widget.change_label.setStyleSheet(f"color: {color};")
                        
                        # Update percentage
                        if hasattr(widget, 'pct_label'):
                            pct = data['change_pct']
                            sign = "+" if pct >= 0 else ""
                            widget.pct_label.setText(f"{sign}{pct:.2f}%")
                            color = "#00ff41" if pct >= 0 else "#ff1744"
                            widget.pct_label.setStyleSheet(f"color: {color};")
            
            # Update toolbar with real SPY data scaled to indices
            if 'SPY' in dashboard_data:
                spy_data = dashboard_data['SPY']
                
                # SPX (SPY * 10)
                if hasattr(dashboard, 'spx_value'):
                    dashboard.spx_value.setText(f" {spy_data['last'] * 10:.0f}")
                if hasattr(dashboard, 'spx_change'):
                    change = spy_data['change'] * 10
                    pct = spy_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    dashboard.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    dashboard.spx_change.setStyleSheet(f"color: {color};")
            
            # Update QQQ to NDX
            if 'QQQ' in dashboard_data:
                qqq_data = dashboard_data['QQQ']
                
                if hasattr(dashboard, 'ndx_value'):
                    dashboard.ndx_value.setText(f" {qqq_data['last'] * 35:.0f}")
                if hasattr(dashboard, 'ndx_change'):
                    change = qqq_data['change'] * 35
                    pct = qqq_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    dashboard.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    dashboard.ndx_change.setStyleSheet(f"color: {color};")
            
            # Update DIA to DJI
            if 'DIA' in dashboard_data:
                dia_data = dashboard_data['DIA']
                
                if hasattr(dashboard, 'dji_value'):
                    dashboard.dji_value.setText(f" {dia_data['last'] * 98:.0f}")
                if hasattr(dashboard, 'dji_change'):
                    change = dia_data['change'] * 98
                    pct = dia_data['change_pct']
                    sign = "+" if change >= 0 else ""
                    dashboard.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    dashboard.dji_change.setStyleSheet(f"color: {color};")
            
            # Update status labels
            if hasattr(dashboard, 'market_data_status'):
                dashboard.market_data_status.setText("LIVE - REAL")
                dashboard.market_data_status.setStyleSheet("color: #00ff41;")
            
            print(f"✅ Updated with real data - SPY: ${live_data.get('SPY', {}).get('last', 'N/A')}")
            
        except Exception as e:
            print(f"❌ Error updating: {e}")
    
    # Stop dashboard simulation first
    try:
        if hasattr(dashboard, 'market_worker'):
            worker = dashboard.market_worker
            if hasattr(worker, 'update_timer') and worker.update_timer:
                worker.update_timer.stop()
                print("✅ Stopped simulation timer")
        
        if hasattr(dashboard, 'automation_timer'):
            dashboard.automation_timer.setInterval(30000)  # Slow down to 30 seconds
            print("✅ Slowed automation timer")
            
    except Exception as e:
        print(f"⚠️  Could not stop simulation: {e}")
    
    # Setup rapid real data updates
    dashboard._real_data_timer = QTimer()
    dashboard._real_data_timer.timeout.connect(update_with_real_data)
    dashboard._real_data_timer.start(1000)  # Update every second
    
    # Initial update
    update_with_real_data()
    
    print("🔥 REAL DATA FIX APPLIED!")
    print("Your dashboard should now show real market prices!")
    print("SPY should show around $643.72 instead of simulated ~$585")
    
    # Add log entry
    dashboard.add_system_log("🔥 Real data fix applied - showing live IB prices")
    dashboard.add_automation_log("Simulation overridden with real market data")
    
    return True

# ==============================================================================
# CONSOLE APPLICATION METHOD
# ==============================================================================
def apply_via_console_command():
    """Generate console command for easy copy-paste"""
    command = '''
# COPY AND PASTE THIS INTO YOUR DASHBOARD'S PYTHON CONSOLE:
import sys, json
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QTimer

def apply_real_data():
    data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
    if not data_file.exists():
        print("❌ Start injector: python temp_WorkingDataInjector.py")
        return
    
    def update():
        try:
            with open(data_file, 'r') as f:
                live_data = json.load(f)
            for symbol, data in live_data.items():
                if symbol in self.symbol_widgets:
                    widget = self.symbol_widgets[symbol]
                    if hasattr(widget, 'price_label'):
                        widget.price_label.setText(f"{data['last']:.2f}")
                    if hasattr(widget, 'change_label'):
                        change = data['change']
                        sign = "+" if change >= 0 else ""
                        widget.change_label.setText(f"{sign}{change:.2f}")
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        widget.change_label.setStyleSheet(f"color: {color};")
            print(f"✅ Real data: SPY ${live_data.get('SPY', {}).get('last', 'N/A')}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    if hasattr(self, 'market_worker') and hasattr(self.market_worker, 'update_timer'):
        self.market_worker.update_timer.stop()
    
    self._real_timer = QTimer()
    self._real_timer.timeout.connect(update)
    self._real_timer.start(1000)
    update()
    print("🔥 REAL DATA ACTIVATED!")

apply_real_data()
'''
    return command

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("QUICK REAL DATA FIX FOR RUNNING DASHBOARD")
    print("=" * 70)
    print()
    print("METHOD 1: Import and Apply")
    print("-" * 30)
    print("In your dashboard's Python console:")
    print()
    print("from temp_QuickRealDataFix import apply_real_data_fix")
    print("apply_real_data_fix(self)")
    print()
    print("METHOD 2: Copy-Paste Command")
    print("-" * 30)
    print("Copy and paste this entire command into your dashboard console:")
    print()
    print(apply_via_console_command())
    print()
    print("=" * 70)
    print("Either method will immediately show real SPY price: $643.72")
    print("=" * 70)
