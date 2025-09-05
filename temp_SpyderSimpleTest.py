#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Simple Test Script
Purpose: Test core components one by one
"""

import os
import sys
from pathlib import Path

# Setup environment
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['SPYDER_HEADLESS'] = 'true'

# Add project root
project_root = Path.cwd()
sys.path.insert(0, str(project_root))

print("=" * 60)
print("SPYDER COMPONENT TEST")
print("=" * 60)

# Test 1: Logger
print("\n1. Testing Logger...")
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger()  # No arguments
    print("   ✅ Logger works")
    
    # Try to log something
    if hasattr(logger, 'info'):
        logger.info("Test message")
        print("   ✅ Logger.info() works")
    elif hasattr(logger, 'log'):
        logger.log("Test message")
        print("   ✅ Logger.log() works")
    else:
        print("   ⚠️  Logger methods unclear:", dir(logger))
        
except Exception as e:
    print(f"   ❌ Logger failed: {e}")

# Test 2: Error Handler
print("\n2. Testing Error Handler...")
try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    error_handler = SpyderErrorHandler()
    print("   ✅ ErrorHandler works")
except Exception as e:
    print(f"   ❌ ErrorHandler failed: {e}")

# Test 3: Constants
print("\n3. Testing Constants...")
try:
    from SpyderU_Utilities.SpyderU07_Constants import OrderAction, OrderType
    print(f"   ✅ Constants work - OrderAction.BUY = {OrderAction.BUY}")
except Exception as e:
    print(f"   ❌ Constants failed: {e}")

# Test 4: Event Manager
print("\n4. Testing Event Manager...")
try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    event_mgr = EventManager()
    print("   ✅ EventManager works")
    
    # Check if it's actually working
    if hasattr(event_mgr, 'publish'):
        print("   ✅ EventManager has publish method")
    
except Exception as e:
    print(f"   ❌ EventManager failed: {e}")

# Test 5: Configuration
print("\n5. Testing Configuration...")
try:
    from SpyderA_Core.SpyderA03_Configuration import ConfigManager
    
    # Try different initialization approaches
    config = None
    
    # Try 1: No arguments
    try:
        config = ConfigManager()
        print("   ✅ ConfigManager() works (no args)")
    except:
        pass
    
    # Try 2: With environment
    if not config:
        try:
            config = ConfigManager(environment='production')
            print("   ✅ ConfigManager(environment='production') works")
        except:
            pass
    
    # Try 3: With all args
    if not config:
        try:
            config = ConfigManager(environment='production', auto_reload=False)
            print("   ✅ ConfigManager(full args) works")
        except:
            pass
            
    if not config:
        print("   ❌ Could not initialize ConfigManager")
    else:
        print("   ✅ ConfigManager initialized successfully")
        
except Exception as e:
    print(f"   ❌ ConfigManager import failed: {e}")

# Test 6: Trading Calendar
print("\n6. Testing Trading Calendar...")
try:
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
    
    calendar = None
    
    # Try 1: No arguments
    try:
        calendar = TradingCalendar()
        print("   ✅ TradingCalendar() works (no args)")
    except:
        pass
    
    # Try 2: With exchange
    if not calendar:
        try:
            calendar = TradingCalendar(exchange='NYSE')
            print("   ✅ TradingCalendar(exchange='NYSE') works")
        except:
            pass
            
    if calendar:
        # Test methods
        try:
            is_open = calendar.is_market_open()
            print(f"   ✅ Market open: {is_open}")
        except Exception as e:
            print(f"   ⚠️  is_market_open() error: {e}")
            
except Exception as e:
    print(f"   ❌ TradingCalendar failed: {e}")

# Test 7: Check for circular imports
print("\n7. Checking B-Series (Broker) modules...")
try:
    # Try to import the problematic module
    from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager
    print("   ✅ ConnectionManager imports correctly")
except ImportError as e:
    if "circular import" in str(e):
        print(f"   ❌ Circular import detected: {e}")
        print("\n   💡 Fix: Edit SpyderB05_ConnectionManager.py")
        print("      Move imports from module level to function level")
    else:
        print(f"   ❌ Import error: {e}")
except Exception as e:
    print(f"   ❌ Unexpected error: {e}")

# Summary
print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
print("\nBased on the results above, we can determine:")
print("1. Which components are working")
print("2. What initialization parameters are needed")
print("3. Which modules need fixes")
print("\nNow you can run the appropriate script or fix the issues.")
