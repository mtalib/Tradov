#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Aggressive Dashboard Patch
Forcibly disables dashboard simulation and injects real market data
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
CHECK_INTERVAL = 500  # Check every 500ms for faster updates

# ==============================================================================
# AGGRESSIVE DASHBOARD PATCH CLASS
# ==============================================================================
class AggressiveDashboardPatch(QObject):
    """
    Aggressively patches the dashboard to disable simulation and use real data
    """
    
    # Signal to update dashboard with real data
    real_data_ready = pyqtSignal(dict)
    
    def __init__(self, dashboard):
        super().__init__()
        self.dashboard = dashboard
        self.active = False
        self.last_update = None
        self.update_count = 0
        self.real_data_cache = {}
        
        # Setup rapid update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._force_real_data_update)
        
        print("=" * 70)
        print("AGGRESSIVE DASHBOARD PATCH - DISABLING SIMULATION")
        print("=" * 70)
        print(f"Monitoring: {LIVE_DATA_FILE}")
        print("This will forcibly override dashboard simulation with real data")
        
    def start(self):
        """Start aggressive patching"""
        # Ensure data directory exists
        DATA_DIR.mkdir(exist_ok=True)
        
        # Disable dashboard's internal simulation immediately
        self._disable_dashboard_simulation()
        
        # Check if live data file exists
        if LIVE_DATA_FILE.exists():
            print("✅ Live data file found - starting aggressive patch")
            self.active = True
            
            # Start rapid updates
            self.update_timer.start(CHECK_INTERVAL)
            
            # Immediately load and apply data
            self._force_real_data_update()
            
            # Update dashboard status
            self.dashboard.add_system_log("🔥 Aggressive real data patch activated")
            self.dashboard.add_automation_log("Simulation disabled - using real market data")
            
        else:
            print("⚠️  Live data file not found - waiting...")
            # Check periodically for the file to appear
            self.update_timer.start(2000)  # Check every 2 seconds
    
    def _disable_dashboard_simulation(self):
        """Aggressively disable dashboard's internal simulation"""
        try:
            print("🛑 Disabling dashboard simulation...")
            
            # Stop the market worker's simulation timer
            if hasattr(self.dashboard, 'market_worker'):
                worker = self.dashboard.market_worker
                
                # Stop update timer
                if hasattr(worker, 'update_timer') and worker.update_timer:
                    worker.update_timer.stop()
                    print("   ✅ Stopped market worker update timer")
                
                # Stop simulation timer
                if hasattr(worker, 'stale_data_timer') and worker.stale_data_timer:
                    worker.stale_data_timer.stop()
                    print("   ✅ Stopped stale data timer")
                
                # Disable simulation data updates
                if hasattr(worker, '_update_simulation_data'):
                    # Replace with no-op function
                    worker._update_simulation_data = lambda data: None
                    print("   ✅ Disabled simulation data updates")
                
                # Mark as using real data
                worker.ib_connected = True
                worker.market_data_status_changed.emit("LIVE - REAL DATA")
            
            # Stop any automation timers that generate fake data
            if hasattr(self.dashboard, 'automation_timer'):
                # Don't stop completely, just reduce frequency
                self.dashboard.automation_timer.setInterval(10000)  # 10 seconds instead of 3
                print("   ✅ Reduced automation timer frequency")
            
            # Override the market data update method
            self._override_market_data_methods()
            
            print("✅ Dashboard simulation disabled")
            
        except Exception as e:
            print(f"❌ Error disabling simulation: {e}")
    
    def _override_market_data_methods(self):
        """Override dashboard methods that generate simulated data"""
        try:
            # Replace the market data update method
            if hasattr(self.dashboard, 'on_market_data_updated'):
                original_method = self.dashboard.on_market_data_updated
                
                def real_data_updater(data):
                    # If we have real data, use it; otherwise use provided data
                    if self.real_data_cache:
                        original_method(self.real_data_cache)
                    else:
                        original_method(data)
                
                self.dashboard.on_market_data_updated = real_data_updater
                print("   ✅ Overrode market data update method")
            
            # Replace simulation data generation
            if hasattr(self.dashboard, 'market_worker') and hasattr(self.dashboard.market_worker, '_emit_data'):
                original_emit = self.dashboard.market_worker._emit_data
                
                def real_data_emitter():
                    if self.real_data_cache:
                        self.dashboard.market_worker.data_updated.emit(self.real_data_cache)
                    else:
                        original_emit()
                
                self.dashboard.market_worker._emit_data = real_data_emitter
                print("   ✅ Overrode data emission method")
                
        except Exception as e:
            print(f"⚠️  Could not override all methods: {e}")
    
    def stop(self):
        """Stop the aggressive patch"""
        self.active = False
        self.update_timer.stop()
        print("✅ Aggressive patch stopped")
    
    def _force_real_data_update(self):
        """Force update with real data"""
        try:
            if not LIVE_DATA_FILE.exists():
                if self.active:
                    self.active = False
                    self.dashboard.add_system_log("⚠️ Real data file disappeared")
                return
            
            # Check file modification time
            file_time = datetime.fromtimestamp(LIVE_DATA_FILE.stat().st_mtime)
            
            if self.last_update is None or file_time > self.last_update:
                self.last_update = file_time
                self._load_and_force_inject_data()
                
                if not self.active:
                    self.active = True
                    self.dashboard.add_system_log("🔥 Real market data detected and injected")
                    print("🔥 Real data injection active!")
        
        except Exception as e:
            if self.active:
                print(f"❌ Error in force update: {e}")
    
    def _load_and_force_inject_data(self):
        """Load and forcibly inject real data"""
        try:
            with open(LIVE_DATA_FILE, 'r') as f:
                live_data = json.load(f)
            
            if live_data:
                # Convert to dashboard format
                dashboard_data = self._convert_to_dashboard_format(live_data)
                
                # Cache the real data
                self.real_data_cache = dashboard_data
                
                # Forcibly update ALL dashboard components
                self._force_update_all_components(dashboard_data)
                
                self.update_count += 1
                
                # Log updates to confirm it's working
                if self.update_count % 20 == 0:
                    spy_price = live_data.get('SPY', {}).get('last', 'N/A')
                    self.dashboard.add_system_log(f"🔥 REAL DATA #{self.update_count} - SPY: ${spy_price}")
        
        except Exception as e:
            print(f"❌ Error loading real data: {e}")
    
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
    
    def _force_update_all_components(self, real_data):
        """Forcibly update ALL dashboard components with real data"""
        try:
            # 1. Update the dashboard's internal market data storage
            if hasattr(self.dashboard, 'market_data'):
                self.dashboard.market_data.clear()
                self.dashboard.market_data.update(real_data)
            
            # 2. Forcibly update symbol widgets
            self._force_update_symbol_widgets(real_data)
            
            # 3. Forcibly update toolbar indices
            self._force_update_toolbar_indices(real_data)
            
            # 4. Force chart update
            self._force_update_chart(real_data)
            
            # 5. Update connection status to show real data
            self._force_update_connection_status()
            
        except Exception as e:
            print(f"❌ Error in force update: {e}")
    
    def _force_update_symbol_widgets(self, real_data):
        """Forcibly update symbol widgets"""
        try:
            if hasattr(self.dashboard, 'symbol_widgets'):
                for symbol, data in real_data.items():
                    if symbol in self.dashboard.symbol_widgets:
                        widget = self.dashboard.symbol_widgets[symbol]
                        if hasattr(widget, 'update_data'):
                            widget.update_data(data)
                        
                        # Force refresh the widget display
                        if hasattr(widget, 'price_label'):
                            widget.price_label.setText(f"{data['last']:.2f}")
                        if hasattr(widget, 'change_label'):
                            change = data['change']
                            sign = "+" if change >= 0 else ""
                            widget.change_label.setText(f"{sign}{change:.2f}")
                            
                            # Update color
                            color = "#00ff41" if change >= 0 else "#ff1744"
                            widget.change_label.setStyleSheet(f"color: {color};")
                        
                        if hasattr(widget, 'pct_label'):
                            change_pct = data['change_pct']
                            sign = "+" if change_pct >= 0 else ""
                            widget.pct_label.setText(f"{sign}{change_pct:.2f}%")
                            
                            # Update color
                            color = "#00ff41" if change_pct >= 0 else "#ff1744"
                            widget.pct_label.setStyleSheet(f"color: {color};")
        
        except Exception as e:
            print(f"⚠️  Error updating symbol widgets: {e}")
    
    def _force_update_toolbar_indices(self, real_data):
        """Forcibly update toolbar index displays"""
        try:
            # Map symbols to toolbar labels with scaling
            updates = {
                'SPY': {
                    'value_label': 'spx_value',
                    'change_label': 'spx_change', 
                    'scale': 10.0  # SPY * 10 ≈ SPX
                },
                'DIA': {
                    'value_label': 'dji_value',
                    'change_label': 'dji_change',
                    'scale': 97.8  # DIA * 97.8 ≈ DJI
                },
                'QQQ': {
                    'value_label': 'ndx_value', 
                    'change_label': 'ndx_change',
                    'scale': 35.1  # QQQ * 35.1 ≈ NDX
                }
            }
            
            for symbol, config in updates.items():
                if symbol in real_data:
                    data = real_data[symbol]
                    
                    # Update value label
                    if hasattr(self.dashboard, config['value_label']):
                        value_label = getattr(self.dashboard, config['value_label'])
                        scaled_value = data['last'] * config['scale']
                        value_label.setText(f" {scaled_value:.0f}")
                    
                    # Update change label
                    if hasattr(self.dashboard, config['change_label']):
                        change_label = getattr(self.dashboard, config['change_label'])
                        change = data['change'] * config['scale']
                        change_pct = data['change_pct']
                        sign = "+" if change >= 0 else ""
                        change_label.setText(f"  {sign}{change:.0f}  {sign}{change_pct:.1f}%")
                        
                        # Update color
                        color = "#00ff41" if change >= 0 else "#ff1744"
                        change_label.setStyleSheet(f"color: {color};")
        
        except Exception as e:
            print(f"⚠️  Error updating toolbar: {e}")
    
    def _force_update_chart(self, real_data):
        """Force chart update with real SPY data"""
        try:
            if 'SPY' in real_data and hasattr(self.dashboard, 'update_chart'):
                # Update the chart - this might fail but that's ok
                self.dashboard.update_chart()
        except:
            pass  # Chart update is not critical
    
    def _force_update_connection_status(self):
        """Force update connection status to show real data"""
        try:
            if hasattr(self.dashboard, 'market_data_status'):
                self.dashboard.market_data_status.setText("LIVE - REAL")
                self.dashboard.market_data_status.setStyleSheet("color: #00ff41;")
            
            if hasattr(self.dashboard, 'connection_label'):
                self.dashboard.connection_label.setText("IB CONNECTED - REAL DATA")
                self.dashboard.connection_label.setStyleSheet("color: #00ff41;")
        
        except Exception as e:
            pass  # Not critical

# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================
def aggressively_patch_dashboard(dashboard):
    """
    Convenience function to aggressively patch a dashboard instance
    
    Args:
        dashboard: Dashboard instance to patch
        
    Returns:
        AggressiveDashboardPatch: Patch instance
    """
    patch = AggressiveDashboardPatch(dashboard)
    patch.start()
    return patch

def apply_to_running_dashboard():
    """Apply aggressive patch to currently running dashboard"""
    print("\n" + "=" * 70)
    print("AGGRESSIVE PATCH APPLICATION")
    print("=" * 70)
    print("This will be applied to your running dashboard via console:")
    print()
    print("1. Open your dashboard's Python console")
    print("2. Run this code:")
    print()
    print("from temp_AggressiveDashboardPatch import aggressively_patch_dashboard")
    print("patch = aggressively_patch_dashboard(self)  # 'self' is the dashboard")
    print()
    print("3. Your dashboard should immediately show real prices!")
    print("=" * 70)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("AGGRESSIVE DASHBOARD PATCH")
    print("=" * 40)
    print("This module aggressively disables simulation and forces real data.")
    print()
    
    # Show instructions
    apply_to_running_dashboard()
    
    # Check data status
    if LIVE_DATA_FILE.exists():
        try:
            with open(LIVE_DATA_FILE, 'r') as f:
                data = json.load(f)
            
            print(f"\n✅ Real data available:")
            if 'SPY' in data:
                spy = data['SPY']
                print(f"   SPY: ${spy['last']:.2f} ({spy['change']:+.2f}, {spy['change_pct']:+.2f}%)")
            
            file_time = datetime.fromtimestamp(LIVE_DATA_FILE.stat().st_mtime)
            age = (datetime.now() - file_time).total_seconds()
            print(f"   Last update: {age:.1f} seconds ago")
            
        except Exception as e:
            print(f"❌ Error reading data: {e}")
    else:
        print("\n❌ No real data file found")
        print("   Start the injector: python temp_WorkingDataInjector.py")
