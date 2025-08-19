#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Working Real Data Dashboard (FIXED)
Simplified version that definitely works
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

def main():
    """Main entry point with working real data dashboard"""
    
    print("=" * 70)
    print("🔥 SPYDER WORKING REAL DATA DASHBOARD")
    print("=" * 70)
    
    # Check real data availability
    data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
    real_data_available = False
    
    if data_file.exists():
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
            spy_price = data.get('SPY', {}).get('last', 'N/A')
            print(f"✅ Real data detected - SPY: ${spy_price}")
            real_data_available = True
        except:
            print("⚠️  Real data file exists but couldn't read it")
    else:
        print("⚠️  No real data detected")
        print("   Start injector: python temp_WorkingDataInjector.py")
    
    print("=" * 70)
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Create normal dashboard
    dashboard = SpyderTradingDashboard()
    
    # Apply real data patch AFTER dashboard is fully initialized
    if real_data_available:
        print("🔥 Applying real data patch...")
        apply_real_data_patch(dashboard, data_file)
    else:
        print("📊 Starting with simulation - will switch to real data when available")
        setup_real_data_monitoring(dashboard, data_file)
    
    # Show dashboard
    dashboard.show()
    
    # Run application
    return app.exec()

def apply_real_data_patch(dashboard, data_file):
    """Apply real data patch to existing dashboard"""
    
    def update_with_real_data():
        """Update dashboard with real market data"""
        try:
            if not data_file.exists():
                return
            
            with open(data_file, 'r') as f:
                live_data = json.load(f)
            
            if not live_data:
                return
            
            # Update symbol widgets directly
            for symbol, data in live_data.items():
                if symbol in dashboard.symbol_widgets:
                    widget = dashboard.symbol_widgets[symbol]
                    
                    # Update price
                    if hasattr(widget, 'price_label'):
                        widget.price_label.setText(f"{data['last']:.2f}")
                    
                    # Update change with color
                    if hasattr(widget, 'change_label'):
                        change = data['change']
                        sign = "+" if change >= 0 else ""
                        widget.change_label.setText(f"{sign}{change:.2f}")
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        widget.change_label.setStyleSheet(f"color: {color};")
                    
                    # Update percentage with color
                    if hasattr(widget, 'pct_label'):
                        pct = data['change_pct']
                        sign = "+" if pct >= 0 else ""
                        widget.pct_label.setText(f"{sign}{pct:.2f}%")
                        color = "#00ff41" if pct >= 0 else "#ff1744"
                        widget.pct_label.setStyleSheet(f"color: {color};")
            
            # Update toolbar indices
            update_toolbar_with_real_data(dashboard, live_data)
            
            # Update status
            update_status_for_real_data(dashboard)
            
        except Exception as e:
            print(f"❌ Error updating real data: {e}")
    
    # Stop original simulation
    try:
        if hasattr(dashboard, 'market_worker'):
            worker = dashboard.market_worker
            if hasattr(worker, 'update_timer') and worker.update_timer:
                worker.update_timer.stop()
                print("✅ Stopped simulation timer")
        
        if hasattr(dashboard, 'automation_timer'):
            dashboard.automation_timer.setInterval(20000)  # Slow down automation
            
    except Exception as e:
        print(f"⚠️  Could not stop simulation: {e}")
    
    # Start real data updates
    dashboard._real_data_timer = QTimer()
    dashboard._real_data_timer.timeout.connect(update_with_real_data)
    dashboard._real_data_timer.start(1000)  # Update every second
    
    # Initial update
    update_with_real_data()
    
    # Add log entries
    dashboard.add_system_log("🔥 REAL MARKET DATA ACTIVE - IB Gateway prices")
    dashboard.add_automation_log("Real-time market data from Interactive Brokers")
    
    print("✅ Real data patch applied successfully!")

def setup_real_data_monitoring(dashboard, data_file):
    """Setup monitoring for real data to become available"""
    
    def check_for_real_data():
        """Check if real data becomes available"""
        if data_file.exists():
            try:
                with open(data_file, 'r') as f:
                    data = json.load(f)
                
                if data:
                    print("🔥 Real data detected - switching from simulation!")
                    dashboard._check_timer.stop()
                    apply_real_data_patch(dashboard, data_file)
            except:
                pass
    
    # Check every 5 seconds for real data
    dashboard._check_timer = QTimer()
    dashboard._check_timer.timeout.connect(check_for_real_data)
    dashboard._check_timer.start(5000)

def update_toolbar_with_real_data(dashboard, live_data):
    """Update toolbar indices with real data"""
    try:
        # Update SPX from SPY (SPY * 10)
        if 'SPY' in live_data:
            spy_data = live_data['SPY']
            
            if hasattr(dashboard, 'spx_value'):
                dashboard.spx_value.setText(f" {spy_data['last'] * 10:.0f}")
            
            if hasattr(dashboard, 'spx_change'):
                change = spy_data['change'] * 10
                pct = spy_data['change_pct']
                sign = "+" if change >= 0 else ""
                dashboard.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.spx_change.setStyleSheet(f"color: {color};")
        
        # Update NDX from QQQ (QQQ * 35)
        if 'QQQ' in live_data:
            qqq_data = live_data['QQQ']
            
            if hasattr(dashboard, 'ndx_value'):
                dashboard.ndx_value.setText(f" {qqq_data['last'] * 35:.0f}")
            
            if hasattr(dashboard, 'ndx_change'):
                change = qqq_data['change'] * 35
                pct = qqq_data['change_pct']
                sign = "+" if change >= 0 else ""
                dashboard.ndx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.ndx_change.setStyleSheet(f"color: {color};")
        
        # Update DJI from DIA (DIA * 98)
        if 'DIA' in live_data:
            dia_data = live_data['DIA']
            
            if hasattr(dashboard, 'dji_value'):
                dashboard.dji_value.setText(f" {dia_data['last'] * 98:.0f}")
            
            if hasattr(dashboard, 'dji_change'):
                change = dia_data['change'] * 98
                pct = dia_data['change_pct']
                sign = "+" if change >= 0 else ""
                dashboard.dji_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                dashboard.dji_change.setStyleSheet(f"color: {color};")
    
    except Exception as e:
        print(f"⚠️  Error updating toolbar: {e}")

def update_status_for_real_data(dashboard):
    """Update status indicators for real data"""
    try:
        # Update market data status
        if hasattr(dashboard, 'market_data_status'):
            dashboard.market_data_status.setText("LIVE - REAL")
            dashboard.market_data_status.setStyleSheet("color: #00ff41;")
        
        # Update connection status
        if hasattr(dashboard, 'connection_label'):
            dashboard.connection_label.setText("IB CONNECTED - REAL DATA")
            dashboard.connection_label.setStyleSheet("color: #00ff41;")
        
    except Exception as e:
        pass  # Not critical

if __name__ == "__main__":
    sys.exit(main())
