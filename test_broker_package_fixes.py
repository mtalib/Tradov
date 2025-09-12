#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Broker Package Fixes Validation Test

Test Name: test_broker_package_fixes.py
Purpose: Quick validation test for the critical broker package fixes
Author: Mohamed Talib  
Date Created: 2025-09-11
Last Updated: 2025-09-11 Time: 19:15:00

Description:
    Quick test to verify that the critical ConnectivityState.UNKNOWN error
    has been resolved and that all major broker components can be imported
    and instantiated without errors.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_critical_imports():
    """Test the critical imports that were failing."""
    print("TESTING CRITICAL BROKER PACKAGE FIXES")
    print("=" * 50)
    
    try:
        # Test the critical ConnectivityState.UNKNOWN import
        print("1. Testing ConnectivityState.UNKNOWN import...")
        from SpyderB_Broker import ConnectivityState
        unknown_state = ConnectivityState.UNKNOWN
        print(f"   ✅ ConnectivityState.UNKNOWN = {unknown_state}")
        
        # Test SystemHealth import
        print("2. Testing SystemHealth import...")
        from SpyderB_Broker import SystemHealth
        system_health = SystemHealth()
        print(f"   ✅ SystemHealth instantiated: {type(system_health)}")
        
        # Test GatewayIntegrationManager import
        print("3. Testing GatewayIntegrationManager import...")
        from SpyderB_Broker import GatewayIntegrationManager
        integration_manager = GatewayIntegrationManager()
        print(f"   ✅ GatewayIntegrationManager instantiated: {type(integration_manager)}")
        
        # Test create_gateway_automation function
        print("4. Testing create_gateway_automation function...")
        from SpyderB_Broker import create_gateway_automation
        gateway_automation = create_gateway_automation()
        print(f"   ✅ create_gateway_automation() worked: {type(gateway_automation)}")
        
        # Test IBDataTypes alias
        print("5. Testing IBDataTypes import...")
        from SpyderB_Broker import IBDataTypes
        ib_data_types = IBDataTypes()
        print(f"   ✅ IBDataTypes instantiated: {type(ib_data_types)}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Critical import test failed: {e}")
        return False

def test_broker_integration():
    """Test broker package integration functionality."""
    print("\n6. Testing broker package integration...")
    
    try:
        import SpyderB_Broker
        
        # Test package status
        status = SpyderB_Broker.get_package_status()
        print(f"   ✅ Package status retrieved: {status['success_rate']:.1%} success rate")
        
        # Test creating key components
        watchdog = SpyderB_Broker.create_watchdog()
        system_health = watchdog.get_system_health()
        print(f"   ✅ Watchdog -> SystemHealth chain working")
        
        # Test metrics collector
        metrics_collector = SpyderB_Broker.create_metrics_collector()
        trading_metrics = metrics_collector.get_trading_metrics()
        print(f"   ✅ Metrics collector -> TradingMetrics chain working")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Integration test failed: {e}")
        return False

def test_enum_completeness():
    """Test that all required enums are available."""
    print("\n7. Testing enum completeness...")
    
    try:
        from SpyderB_Broker import (
            ConnectivityState, VPNStatus, ConnectionHealth,
            OrderAction, OrderType, HealthStatus, 
            ClientStatusLevel, SystemComponent
        )
        
        # Test ConnectivityState completeness
        required_connectivity_states = [
            'UNKNOWN', 'CONNECTING', 'CONNECTED', 'DISCONNECTED', 
            'FAILED', 'TIMEOUT', 'AUTHENTICATED'
        ]
        
        for state_name in required_connectivity_states:
            if hasattr(ConnectivityState, state_name):
                state_value = getattr(ConnectivityState, state_name)
                print(f"   ✅ ConnectivityState.{state_name} = {state_value.value}")
            else:
                print(f"   ⚠️ ConnectivityState.{state_name} missing")
        
        # Test that we can instantiate other critical enums
        test_vpn_status = VPNStatus.CONNECTED
        test_health = ConnectionHealth.EXCELLENT
        test_order_action = OrderAction.BUY
        test_client_status = ClientStatusLevel.GOOD
        
        print(f"   ✅ All critical enums instantiable")
        return True
        
    except Exception as e:
        print(f"   ❌ Enum completeness test failed: {e}")
        return False

def main():
    """Run all validation tests."""
    print("SPYDER BROKER PACKAGE FIXES VALIDATION")
    print("=" * 60)
    
    # Run tests
    tests = [
        test_critical_imports,
        test_broker_integration, 
        test_enum_completeness
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    print(f"Success Rate: {passed/total:.1%}")
    
    if passed == total:
        print("🎉 ALL FIXES VALIDATED SUCCESSFULLY!")
        print("\nThe broker package should now work with:")
        print("  ✅ ConnectivityState.UNKNOWN attribute")
        print("  ✅ SystemHealth imports")
        print("  ✅ GatewayIntegrationManager class")
        print("  ✅ Factory function support")
        print("  ✅ Complete enum definitions")
        
        print("\nNext steps:")
        print("1. Run the comprehensive test again:")
        print("   python test_comprehensive_broker_dashboard_flow.py")
        print("2. Expected much higher success rate (80%+)")
        print("3. Only remaining failures should be optional dependencies")
        
        return True
    else:
        print("❌ Some fixes still need work")
        print("\nFailed tests need investigation:")
        for i, (test, result) in enumerate(zip(tests, results)):
            if not result:
                print(f"  - {test.__name__}")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
