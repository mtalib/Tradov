#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Launch Dashboard with Real Market Data
Complete solution to launch dashboard with live IB Gateway data
"""

import sys
import os
import time
import subprocess
import threading
from pathlib import Path
from PyQt6.QtWidgets import QApplication

# Add Spyder directory to path
SPYDER_HOME = Path(__file__).parent
sys.path.insert(0, str(SPYDER_HOME))

# ==============================================================================
# CONFIGURATION
# ==============================================================================
INJECTOR_SCRIPT = SPYDER_HOME / "temp_WorkingDataInjector.py"
DASHBOARD_MODULE = "SpyderG_GUI.SpyderG05_TradingDashboard"

# ==============================================================================
# ENHANCED DASHBOARD WITH LIVE DATA
# ==============================================================================
class EnhancedDashboard:
    """Dashboard wrapper that automatically enables live data"""
    
    def __init__(self):
        self.dashboard = None
        self.injector_process = None
        self.patch = None
        
        print("=" * 70)
        print("SPYDER DASHBOARD WITH REAL MARKET DATA")
        print("=" * 70)
    
    def start_injector(self):
        """Start the data injector in background"""
        try:
            print("🚀 Starting market data injector...")
            
            # Start injector process
            self.injector_process = subprocess.Popen([
                sys.executable, str(INJECTOR_SCRIPT)
            ], cwd=str(SPYDER_HOME))
            
            print(f"✅ Data injector started (PID: {self.injector_process.pid})")
            
            # Wait a moment for it to establish connection
            time.sleep(3)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to start injector: {e}")
            return False
    
    def start_dashboard(self):
        """Start the dashboard with live data patch"""
        try:
            print("🖥️  Starting Spyder dashboard...")
            
            # Import dashboard
            from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
            
            # Create Qt application
            app = QApplication(sys.argv)
            app.setStyle("Fusion")
            
            # Create dashboard
            self.dashboard = SpyderTradingDashboard()
            
            # Apply live data patch
            self._apply_live_data_patch()
            
            # Show dashboard
            self.dashboard.show()
            
            print("✅ Dashboard started with live data patch")
            print("\n" + "=" * 70)
            print("🎯 DASHBOARD IS NOW RUNNING WITH REAL MARKET DATA!")
            print("=" * 70)
            print("📊 You should see real prices updating in the dashboard")
            print("🔄 Market data updates every second")
            print("⚠️  Press Ctrl+C in this terminal to stop everything")
            print("=" * 70)
            
            # Run the application
            return app.exec()
            
        except Exception as e:
            print(f"❌ Failed to start dashboard: {e}")
            return 1
    
    def _apply_live_data_patch(self):
        """Apply live data patch to dashboard"""
        try:
            # Import the patch
            from temp_DashboardLivePatch import DashboardLivePatch
            
            # Create and start patch
            self.patch = DashboardLivePatch(self.dashboard)
            self.patch.start()
            
            print("✅ Live data patch applied")
            
        except Exception as e:
            print(f"⚠️  Could not apply live data patch: {e}")
            print("   Dashboard will run with simulated data")
    
    def stop(self):
        """Stop everything"""
        print("\n🛑 Shutting down...")
        
        # Stop patch
        if self.patch:
            self.patch.stop()
        
        # Stop injector
        if self.injector_process:
            try:
                self.injector_process.terminate()
                self.injector_process.wait(timeout=5)
                print("✅ Data injector stopped")
            except:
                try:
                    self.injector_process.kill()
                except:
                    pass
        
        print("✅ Shutdown complete")

# ==============================================================================
# QUICK PATCH FOR EXISTING DASHBOARD
# ==============================================================================
def patch_existing_dashboard():
    """Patch an already running dashboard"""
    print("=" * 60)
    print("PATCHING EXISTING DASHBOARD")
    print("=" * 60)
    
    try:
        # This would be called from within a running dashboard
        import temp_DashboardLivePatch
        temp_DashboardLivePatch.check_live_data_status()
        
        print("\nTo patch your running dashboard:")
        print("1. Import this module in your dashboard console")
        print("2. Or restart with this launcher")
        
    except ImportError:
        print("❌ Patch module not available")

# ==============================================================================
# MAIN EXECUTION MODES
# ==============================================================================
def launch_complete_solution():
    """Launch dashboard with injector - complete solution"""
    enhanced = EnhancedDashboard()
    
    try:
        # Start injector first
        if not enhanced.start_injector():
            print("❌ Failed to start data injector")
            return 1
        
        # Start dashboard
        result = enhanced.start_dashboard()
        
        return result
        
    except KeyboardInterrupt:
        print("\n🛑 Keyboard interrupt received")
        enhanced.stop()
        return 0
    
    except Exception as e:
        print(f"❌ Error: {e}")
        enhanced.stop()
        return 1
    
    finally:
        enhanced.stop()

def launch_injector_only():
    """Launch just the data injector"""
    print("=" * 60)
    print("LAUNCHING DATA INJECTOR ONLY")
    print("=" * 60)
    print("Start your dashboard separately to see real data")
    print("=" * 60)
    
    try:
        os.system(f"python {INJECTOR_SCRIPT}")
    except KeyboardInterrupt:
        print("\n✅ Injector stopped")

def check_status():
    """Check current status"""
    try:
        from temp_DashboardLivePatch import check_live_data_status
        check_live_data_status()
    except ImportError:
        print("❌ Status check module not available")

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point with menu"""
    print("\n" + "=" * 70)
    print("SPYDER DASHBOARD REAL DATA LAUNCHER")
    print("=" * 70)
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    else:
        print("Choose an option:")
        print("1. Launch dashboard with real data (recommended)")
        print("2. Launch data injector only")
        print("3. Check live data status")
        print("4. Patch existing dashboard")
        print()
        
        try:
            choice = input("Enter choice (1-4): ").strip()
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return 0
        
        mode = {'1': 'full', '2': 'injector', '3': 'status', '4': 'patch'}.get(choice, 'full')
    
    if mode == 'full':
        return launch_complete_solution()
    elif mode == 'injector':
        launch_injector_only()
        return 0
    elif mode == 'status':
        check_status()
        return 0
    elif mode == 'patch':
        patch_existing_dashboard()
        return 0
    else:
        print(f"❌ Unknown mode: {mode}")
        return 1

if __name__ == "__main__":
    sys.exit(main())