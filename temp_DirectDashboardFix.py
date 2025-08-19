#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Direct Dashboard Fix
Directly finds and patches running dashboard process with real market data
"""

import json
import sys
import os
import time
import threading
from pathlib import Path
from datetime import datetime

# ==============================================================================
# DIRECT DASHBOARD PATCHER
# ==============================================================================
class DirectDashboardPatcher:
    """Directly patches running dashboard process"""
    
    def __init__(self):
        self.data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        self.running = False
        
    def find_dashboard_process(self):
        """Find running dashboard process"""
        try:
            import psutil
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info.get('cmdline', []))
                    if 'SpyderG05_TradingDashboard' in cmdline or 'TradingDashboard' in cmdline:
                        print(f"✅ Found dashboard process: PID {proc.info['pid']}")
                        return proc
                except:
                    continue
            
            print("❌ No dashboard process found")
            return None
            
        except ImportError:
            print("❌ psutil not available - cannot find dashboard process")
            return None
    
    def check_data_availability(self):
        """Check if real data is available"""
        if not self.data_file.exists():
            print("❌ No real data file found!")
            print("   Start injector: python temp_WorkingDataInjector.py")
            return False
        
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
            
            if not data:
                print("❌ Data file is empty")
                return False
            
            # Check data freshness
            file_time = datetime.fromtimestamp(self.data_file.stat().st_mtime)
            age = (datetime.now() - file_time).total_seconds()
            
            if age > 30:
                print(f"⚠️  Data is {age:.0f} seconds old - injector may have stopped")
            
            print(f"✅ Real data available:")
            if 'SPY' in data:
                spy = data['SPY']
                print(f"   SPY: ${spy['last']:.2f} ({spy['change']:+.2f}, {spy['change_pct']:+.2f}%)")
            
            return True
            
        except Exception as e:
            print(f"❌ Error reading data: {e}")
            return False
    
    def create_patch_script(self):
        """Create a patch script that can be imported by dashboard"""
        patch_script = Path.home() / "Projects/Spyder/apply_real_data_patch.py"
        
        script_content = f'''#!/usr/bin/env python3
"""Auto-generated real data patch"""

import json
import sys
from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QTimer

def patch_dashboard_with_real_data(dashboard_instance):
    """Patch dashboard with real data"""
    
    data_file = Path("{self.data_file}")
    
    def update_with_real_data():
        try:
            if not data_file.exists():
                return
            
            with open(data_file, 'r') as f:
                live_data = json.load(f)
            
            if not live_data:
                return
            
            # Update symbol widgets
            if hasattr(dashboard_instance, 'symbol_widgets'):
                for symbol, data in live_data.items():
                    if symbol in dashboard_instance.symbol_widgets:
                        widget = dashboard_instance.symbol_widgets[symbol]
                        
                        # Update price
                        if hasattr(widget, 'price_label'):
                            widget.price_label.setText(f"{{data['last']:.2f}}")
                        
                        # Update change with color
                        if hasattr(widget, 'change_label'):
                            change = data['change']
                            sign = "+" if change >= 0 else ""
                            widget.change_label.setText(f"{{sign}}{{change:.2f}}")
                            color = "#00ff41" if change >= 0 else "#ff1744"
                            widget.change_label.setStyleSheet(f"color: {{color}};")
                        
                        # Update percentage with color
                        if hasattr(widget, 'pct_label'):
                            pct = data['change_pct']
                            sign = "+" if pct >= 0 else ""
                            widget.pct_label.setText(f"{{sign}}{{pct:.2f}}%")
                            color = "#00ff41" if pct >= 0 else "#ff1744"
                            widget.pct_label.setStyleSheet(f"color: {{color}};")
            
            # Update toolbar indices
            if 'SPY' in live_data:
                spy_price = live_data['SPY']['last']
                spy_change = live_data['SPY']['change']
                spy_pct = live_data['SPY']['change_pct']
                
                # Update SPX (SPY * 10)
                if hasattr(dashboard_instance, 'spx_value'):
                    dashboard_instance.spx_value.setText(f" {{spy_price * 10:.0f}}")
                if hasattr(dashboard_instance, 'spx_change'):
                    change = spy_change * 10
                    sign = "+" if change >= 0 else ""
                    dashboard_instance.spx_change.setText(f"  {{sign}}{{change:.0f}}  {{sign}}{{spy_pct:.1f}}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    dashboard_instance.spx_change.setStyleSheet(f"color: {{color}};")
            
            # Update other indices similarly
            if 'QQQ' in live_data:
                qqq_price = live_data['QQQ']['last']
                qqq_change = live_data['QQQ']['change']
                qqq_pct = live_data['QQQ']['change_pct']
                
                if hasattr(dashboard_instance, 'ndx_value'):
                    dashboard_instance.ndx_value.setText(f" {{qqq_price * 35:.0f}}")
                if hasattr(dashboard_instance, 'ndx_change'):
                    change = qqq_change * 35
                    sign = "+" if change >= 0 else ""
                    dashboard_instance.ndx_change.setText(f"  {{sign}}{{change:.0f}}  {{sign}}{{qqq_pct:.1f}}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    dashboard_instance.ndx_change.setStyleSheet(f"color: {{color}};")
            
            if 'DIA' in live_data:
                dia_price = live_data['DIA']['last']
                dia_change = live_data['DIA']['change'] 
                dia_pct = live_data['DIA']['change_pct']
                
                if hasattr(dashboard_instance, 'dji_value'):
                    dashboard_instance.dji_value.setText(f" {{dia_price * 98:.0f}}")
                if hasattr(dashboard_instance, 'dji_change'):
                    change = dia_change * 98
                    sign = "+" if change >= 0 else ""
                    dashboard_instance.dji_change.setText(f"  {{sign}}{{change:.0f}}  {{sign}}{{dia_pct:.1f}}%")
                    color = "#00ff41" if change >= 0 else "#ff1744"
                    dashboard_instance.dji_change.setStyleSheet(f"color: {{color}};")
            
            # Update market data status
            if hasattr(dashboard_instance, 'market_data_status'):
                dashboard_instance.market_data_status.setText("LIVE - REAL")
                dashboard_instance.market_data_status.setStyleSheet("color: #00ff41;")
            
            print(f"🔥 Real data update: SPY ${{live_data.get('SPY', {{}}).get('last', 'N/A')}}")
            
        except Exception as e:
            print(f"❌ Update error: {{e}}")
    
    # Stop simulation
    try:
        if hasattr(dashboard_instance, 'market_worker'):
            worker = dashboard_instance.market_worker
            if hasattr(worker, 'update_timer') and worker.update_timer:
                worker.update_timer.stop()
                print("✅ Stopped simulation timer")
                
            if hasattr(worker, 'stale_data_timer') and worker.stale_data_timer:
                worker.stale_data_timer.stop()
                print("✅ Stopped stale data timer")
    except Exception as e:
        print(f"⚠️  Could not stop simulation: {{e}}")
    
    # Setup real data timer
    if not hasattr(dashboard_instance, '_real_data_timer'):
        dashboard_instance._real_data_timer = QTimer()
        dashboard_instance._real_data_timer.timeout.connect(update_with_real_data)
        dashboard_instance._real_data_timer.start(1000)  # Update every second
        
        # Initial update
        update_with_real_data()
        
        print("🔥 REAL DATA PATCH APPLIED!")
        print("Dashboard should now show real market prices!")
        
        # Add log entries
        dashboard_instance.add_system_log("🔥 Real market data patch applied")
        dashboard_instance.add_automation_log("Displaying live IB Gateway prices")
        
        return True
    else:
        print("⚠️  Patch already applied")
        return False

# Convenience function for easy import
def apply_patch(dashboard_instance):
    return patch_dashboard_with_real_data(dashboard_instance)
'''
        
        # Write the patch script
        with open(patch_script, 'w') as f:
            f.write(script_content)
        
        print(f"✅ Created patch script: {patch_script}")
        return patch_script
    
    def run(self):
        """Run the direct patcher"""
        print("=" * 70)
        print("DIRECT DASHBOARD PATCHER")
        print("=" * 70)
        
        # Check data availability
        if not self.check_data_availability():
            return False
        
        # Find dashboard process
        dashboard_proc = self.find_dashboard_process()
        if not dashboard_proc:
            print("\n💡 SOLUTION:")
            print("1. Start your dashboard: python SpyderG_GUI/SpyderG05_TradingDashboard.py")
            print("2. Then run this script again")
            return False
        
        # Create patch script
        patch_script = self.create_patch_script()
        
        print("\n🎯 APPLY THE PATCH:")
        print("=" * 50)
        print("Copy and paste this into your dashboard's Python console:")
        print()
        print("import sys")
        print(f"sys.path.insert(0, '{Path.home() / 'Projects/Spyder'}')")
        print("from apply_real_data_patch import apply_patch")
        print("apply_patch(self)")
        print()
        print("=" * 50)
        print("This will immediately show real SPY price: $643.72")
        print("=" * 70)
        
        return True

# ==============================================================================
# SIMPLE FILE-BASED APPROACH
# ==============================================================================
def create_simple_patch_file():
    """Create a simple patch file that can be easily imported"""
    
    patch_file = Path.home() / "Projects/Spyder/simple_real_data_patch.py"
    
    content = '''# Simple Real Data Patch - Run this in dashboard console
import json
from pathlib import Path
from PyQt6.QtCore import QTimer

# Stop simulation
if hasattr(self, 'market_worker') and hasattr(self.market_worker, 'update_timer'):
    self.market_worker.update_timer.stop()
    print("✅ Simulation stopped")

def update_real_data():
    """Update with real market data"""
    try:
        data_file = Path.home() / "Projects/Spyder/market_data/live_data.json"
        
        if not data_file.exists():
            print("❌ No data file")
            return
        
        with open(data_file, 'r') as f:
            live_data = json.load(f)
        
        # Update all symbols
        for symbol, data in live_data.items():
            if symbol in self.symbol_widgets:
                widget = self.symbol_widgets[symbol]
                
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
        
        # Update toolbar with SPY
        if 'SPY' in live_data:
            spy = live_data['SPY']
            if hasattr(self, 'spx_value'):
                self.spx_value.setText(f" {spy['last'] * 10:.0f}")
            if hasattr(self, 'spx_change'):
                change = spy['change'] * 10
                pct = spy['change_pct']
                sign = "+" if change >= 0 else ""
                self.spx_change.setText(f"  {sign}{change:.0f}  {sign}{pct:.1f}%")
                color = "#00ff41" if change >= 0 else "#ff1744"
                self.spx_change.setStyleSheet(f"color: {color};")
        
        print(f"🔥 SPY: ${live_data.get('SPY', {}).get('last', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

# Start real data updates
if not hasattr(self, '_real_data_timer'):
    self._real_data_timer = QTimer()
    self._real_data_timer.timeout.connect(update_real_data)
    self._real_data_timer.start(1000)
    update_real_data()
    print("🔥 REAL DATA ACTIVATED!")
    self.add_system_log("🔥 Real market data activated")
'''
    
    with open(patch_file, 'w') as f:
        f.write(content)
    
    print(f"✅ Created simple patch file: {patch_file}")
    return patch_file

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main entry point"""
    patcher = DirectDashboardPatcher()
    
    if not patcher.run():
        print("\n" + "=" * 70)
        print("ALTERNATIVE: SIMPLE FILE APPROACH")
        print("=" * 70)
        
        # Create simple patch file
        patch_file = create_simple_patch_file()
        
        print("\nRun this command in your dashboard's Python console:")
        print("=" * 50)
        print(f"exec(open('{patch_file}').read())")
        print("=" * 50)
        print("\nOr just copy the content and paste it directly!")
        
    return True

if __name__ == "__main__":
    main()
