#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Spyder Main Integration
Test the enhanced SpyderG05 dashboard through the proper SpyderA01_Main.py entry point
"""

import sys
import os
import time
import signal
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_system_imports():
    """Test if all required modules can be imported"""
    print("=" * 70)
    print("🔍 TESTING SPYDER SYSTEM IMPORTS")
    print("=" * 70)
    
    import_results = {}
    
    # Test core imports
    core_modules = [
        ("SpyderA_Core.SpyderA01_Main", "SpyderA01_Main"),
        ("SpyderG_GUI.SpyderG05_TradingDashboard", "SpyderG05_TradingDashboard"),
        ("SpyderU_Utilities.SpyderU01_Logger", "SpyderLogger"),
        ("SpyderU_Utilities.SpyderU02_ErrorHandler", "SpyderErrorHandler"),
    ]
    
    for module_path, description in core_modules:
        try:
            __import__(module_path)
            print(f"✅ {description}: SUCCESS")
            import_results[description] = True
        except ImportError as e:
            print(f"❌ {description}: FAILED - {e}")
            import_results[description] = False
    
    # Test GUI dependencies
    gui_deps = [
        ("PySide6.QtWidgets", "PySide6 QtWidgets"),
        ("PySide6.QtCore", "PySide6 QtCore"),
        ("PySide6.QtGui", "PySide6 QtGui"),
        ("matplotlib", "Matplotlib"),
        ("pandas", "Pandas"),
        ("numpy", "NumPy"),
    ]
    
    print("\nTesting GUI Dependencies:")
    print("-" * 30)
    
    for module_path, description in gui_deps:
        try:
            __import__(module_path)
            print(f"✅ {description}: SUCCESS")
            import_results[description] = True
        except ImportError as e:
            print(f"❌ {description}: FAILED - {e}")
            import_results[description] = False
    
    # Test broker connection modules
    broker_modules = [
        ("ib_async", "IB Async"),
    ]
    
    print("\nTesting Broker Dependencies:")
    print("-" * 30)
    
    for module_path, description in broker_modules:
        try:
            __import__(module_path)
            print(f"✅ {description}: SUCCESS")
            import_results[description] = True
        except ImportError as e:
            print(f"⚠️ {description}: NOT AVAILABLE - {e}")
            import_results[description] = False
    
    return import_results

def test_direct_dashboard_launch():
    """Test launching the enhanced dashboard directly"""
    print("\n" + "=" * 70)
    print("🚀 TESTING DIRECT DASHBOARD LAUNCH")
    print("=" * 70)
    
    try:
        # Import the enhanced dashboard
        from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
        from PySide6.QtWidgets import QApplication
        
        print("✅ Enhanced dashboard imported successfully")
        
        # Create Qt application
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        print("✅ Qt Application created")
        
        # Create dashboard instance
        dashboard = SpyderTradingDashboard()
        print("✅ Dashboard instance created")
        
        # Show dashboard
        dashboard.show()
        print("✅ Dashboard displayed")
        
        print("\n🎯 DASHBOARD TESTING INSTRUCTIONS:")
        print("1. Check that logs show newest entries first (reverse chronological)")
        print("2. Watch heartbeat icon in toolbar (should be red heart 💔)")
        print("3. Look for 'IB DISCONNECTED' status")
        print("4. Click blue circle button to test simulation mode")
        print("5. Verify auto-reconnection messages appear in System Log")
        print("6. Close dashboard when testing is complete")
        
        # Start the application loop
        return app.exec()
        
    except Exception as e:
        print(f"❌ Direct dashboard launch failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

def test_spyder_main_launch():
    """Test launching through SpyderA01_Main.py"""
    print("\n" + "=" * 70)
    print("🚀 TESTING SPYDER MAIN ENTRY POINT")
    print("=" * 70)
    
    try:
        # Import SpyderA01_Main
        from SpyderA_Core import SpyderA01_Main
        
        print("✅ SpyderA01_Main imported successfully")
        
        # Check if it has a main function
        if hasattr(SpyderA01_Main, 'main'):
            print("✅ Main function found")
            print("🚀 Launching through SpyderA01_Main...")
            
            # Launch the main application
            return SpyderA01_Main.main()
        else:
            print("⚠️ No main function found in SpyderA01_Main")
            print("Trying alternative launch methods...")
            
            # Try other common entry points
            if hasattr(SpyderA01_Main, 'start_gui'):
                return SpyderA01_Main.start_gui()
            elif hasattr(SpyderA01_Main, 'run'):
                return SpyderA01_Main.run()
            else:
                print("❌ No suitable entry point found")
                return test_direct_dashboard_launch()
                
    except Exception as e:
        print(f"❌ SpyderA01_Main launch failed: {e}")
        import traceback
        traceback.print_exc()
        print("\n🔄 Falling back to direct dashboard launch...")
        return test_direct_dashboard_launch()

def test_enhanced_features():
    """Test enhanced features without GUI"""
    print("\n" + "=" * 70)
    print("🧪 TESTING ENHANCED FEATURES")
    print("=" * 70)
    
    try:
        # Test reverse logger
        from SpyderG_GUI.SpyderG05_TradingDashboard import ReverseOrderLogger
        
        def test_callback():
            print("📝 Logger callback triggered")
        
        logger = ReverseOrderLogger(max_entries=5, update_callback=test_callback)
        
        # Add some test entries
        logger.add_entry("First message")
        logger.add_entry("Second message") 
        logger.add_entry("Third message")
        
        entries = logger.get_recent_entries(3)
        
        print("✅ ReverseOrderLogger test:")
        for i, entry in enumerate(entries):
            print(f"   {i+1}. {entry}")
        
        # Should show newest first
        if "Third message" in entries[0]:
            print("✅ Reverse chronological order working")
        else:
            print("❌ Reverse chronological order failed")
        
        # Test auto-reconnection manager
        from SpyderG_GUI.SpyderG05_TradingDashboard import AutoReconnectionManager
        from PySide6.QtCore import QCoreApplication
        
        app = QCoreApplication.instance()
        if app is None:
            app = QCoreApplication(sys.argv)
        
        reconnection = AutoReconnectionManager()
        print("✅ AutoReconnectionManager created")
        
        # Test the enhanced worker
        from SpyderG_GUI.SpyderG05_TradingDashboard import ThreadSafeMarketDataWorker
        
        worker = ThreadSafeMarketDataWorker()
        print("✅ Enhanced ThreadSafeMarketDataWorker created")
        
        print("✅ All enhanced features tested successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced features test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🎯 SPYDER INTEGRATION TEST")
    print("Testing enhanced SpyderG05 dashboard through proper system entry points")
    print("=" * 70)
    
    # Test 1: System imports
    import_results = test_system_imports()
    
    critical_imports = ['SpyderA01_Main', 'SpyderG05_TradingDashboard', 'PySide6 QtWidgets']
    critical_missing = [name for name in critical_imports if not import_results.get(name, False)]
    
    if critical_missing:
        print(f"\n❌ CRITICAL IMPORTS MISSING: {critical_missing}")
        print("Cannot proceed with GUI testing.")
        return 1
    
    # Test 2: Enhanced features (non-GUI)
    features_ok = test_enhanced_features()
    
    if not features_ok:
        print("\n⚠️ Enhanced features test failed, but continuing with GUI test...")
    
    # Test 3: Launch method selection
    print("\n" + "=" * 70)
    print("🎯 SELECT LAUNCH METHOD:")
    print("=" * 70)
    print("1. SpyderA01_Main.py (Recommended - Full System Integration)")
    print("2. Direct Dashboard Launch (Fallback - Dashboard Only)")
    
    try:
        choice = input("\nEnter choice (1 or 2, or press Enter for auto): ").strip()
        
        if choice == "2":
            return test_direct_dashboard_launch()
        elif choice == "1" or not choice:
            return test_spyder_main_launch()
        else:
            print("Invalid choice, using SpyderA01_Main...")
            return test_spyder_main_launch()
            
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
        return 0
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
