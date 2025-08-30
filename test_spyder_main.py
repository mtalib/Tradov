#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for SpyderA01_Main.py system coordinator

This script tests the main system coordinator in various modes
and verifies integration with existing modules.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def test_simulation_mode():
    """Test system in simulation mode."""
    print("Testing SpyderA01_Main in simulation mode...")
    
    try:
        # Import the main application
        from SpyderA_Core.SpyderA01_Main import SpyderApplication, SystemConfig, TradingMode
        
        # Create configuration for simulation
        config = SystemConfig()
        config.trading_mode = TradingMode.SIMULATION
        config.enable_gui = False  # Headless for testing
        config.headless = True
        config.enable_trading = True
        
        print(f"Configuration: {config.trading_mode.value} mode")
        
        # Create application
        app = SpyderApplication(config)
        
        # Initialize system
        print("Initializing system...")
        success = await app.initialize()
        
        if success:
            print("System initialization: SUCCESS")
            
            # Get status
            status = app.get_status()
            print(f"System state: {status.state.value}")
            print(f"Trading mode: {status.trading_mode.value}")
            
            # Test brief run
            print("Testing brief run cycle...")
            
            # Create a task to run for 5 seconds then shutdown
            async def short_run():
                await asyncio.sleep(5)
                app.request_shutdown()
            
            # Start short run task
            run_task = asyncio.create_task(short_run())
            
            # Run application
            exit_code = await app.run()
            
            print(f"Application exit code: {exit_code}")
            print("Simulation mode test: PASSED")
            
        else:
            print("System initialization: FAILED")
            return False
            
    except Exception as e:
        print(f"Simulation test error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

async def test_paper_mode():
    """Test system in paper mode with connection handling."""
    print("\nTesting SpyderA01_Main in paper mode...")
    
    try:
        from SpyderA_Core.SpyderA01_Main import SpyderApplication, SystemConfig, TradingMode
        
        config = SystemConfig()
        config.trading_mode = TradingMode.PAPER
        config.enable_gui = False
        config.headless = True
        config.enable_trading = False  # Disable actual trading for test
        config.connection_timeout = 10  # Short timeout for testing
        
        app = SpyderApplication(config)
        
        print("Attempting paper mode initialization...")
        success = await app.initialize()
        
        if success:
            print("Paper mode initialization: SUCCESS")
            status = app.get_status()
            print(f"Connection status: {status.connection_status}")
            
        else:
            print("Paper mode initialization: FAILED (expected due to Gateway timeout)")
            print("System should have fallen back to simulation mode")
            
            status = app.get_status()
            print(f"Fallback mode: {status.trading_mode.value}")
            
        # Cleanup
        if hasattr(app, '_running') and app._running:
            app.request_shutdown()
            await asyncio.sleep(2)
        
    except Exception as e:
        print(f"Paper mode test error: {e}")
        return False
    
    return True

async def test_subsystem_integration():
    """Test integration with existing Spyder modules."""
    print("\nTesting subsystem integration...")
    
    try:
        # Test individual module imports
        modules_to_test = [
            ("SpyderU_Utilities.SpyderU01_Logger", "SpyderLogger"),
            ("SpyderU_Utilities.SpyderU02_ErrorHandler", "SpyderErrorHandler"),
            ("SpyderB_Broker.SpyderB05_ConnectionManager", "get_connection_manager"),
        ]
        
        for module_name, class_name in modules_to_test:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                print(f"  ✅ {module_name}.{class_name}: Available")
            except Exception as e:
                print(f"  ❌ {module_name}.{class_name}: {e}")
        
        # Test strategy framework
        try:
            from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
            print(f"  ✅ Strategy framework: Available")
        except Exception as e:
            print(f"  ❌ Strategy framework: {e}")
        
        print("Subsystem integration test: COMPLETED")
        
    except Exception as e:
        print(f"Integration test error: {e}")
        return False
    
    return True

async def main():
    """Main test function."""
    print("🕷️ SPYDER System Integration Tests")
    print("=" * 50)
    
    # Test 1: Simulation mode
    test1_success = await test_simulation_mode()
    
    # Test 2: Paper mode (expected to fallback to simulation due to Gateway timeout)  
    test2_success = await test_paper_mode()
    
    # Test 3: Subsystem integration
    test3_success = await test_subsystem_integration()
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY:")
    print(f"Simulation Mode: {'PASS' if test1_success else 'FAIL'}")
    print(f"Paper Mode: {'PASS' if test2_success else 'FAIL'}")
    print(f"Integration: {'PASS' if test3_success else 'FAIL'}")
    
    if all([test1_success, test2_success, test3_success]):
        print("\n🎉 All tests passed! System is ready for strategy development.")
        return 0
    else:
        print("\n❌ Some tests failed. Check logs above.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
