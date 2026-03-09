#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderT_Testing
Purpose: Comprehensive testing framework and validation suite
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04

Package Description:
    The SpyderT_Testing package provides comprehensive testing capabilities
    including unit tests, integration tests, system validation, and specialized
    trading system tests. This package ensures system reliability, performance,
    and correctness across all Spyder components.

Modules Overview:
    • SpyderT01_UnitTestFramework: Core unit testing framework
    • SpyderT02_BrokerTestSuite: Broker integration testing
    • SpyderT03_BlackSwanValidator: Black swan event validation
    • SpyderT05_LiveIBConnectionTest: Live IB connection testing
    • SpyderT08_FixedSystemIntegration: System integration testing
    • SpyderT09_TestDashboard: Dashboard testing utilities
    • SpyderT12_FullSystemIntegration: Full system integration tests
    • SpyderT13_MultiClientIntegrationTest: Multi-client testing
    • SpyderT15_FullSystemTest: Complete system validation
    • SpyderT16_SystemHealthMonitor: Continuous health monitoring
    • SpyderT99_SystemDiagnostic: System diagnostic utilities

Key Features:
    • Comprehensive unit and integration testing
    • Live trading environment validation
    • Black swan event simulation and testing
    • Multi-client integration testing
    • System health monitoring and diagnostics
    • Performance and stress testing
    • Automated test suite execution
"""

# ==============================================================================
# VERSION INFORMATION
# ==============================================================================
__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"
__status__ = "Production"

# ==============================================================================
# CORE MODULE IMPORTS
# ==============================================================================

# Unit Test Framework
try:
    from .SpyderT01_UnitTestFramework import (
        UnitTestFramework,
        # Add main classes from UnitTestFramework when inspected
    )

    UNIT_TEST_FRAMEWORK_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT01_UnitTestFramework not available: {e}")
    UNIT_TEST_FRAMEWORK_AVAILABLE = False

# Broker Test Suite
try:
    from .SpyderT02_BrokerTestSuite import (
        BrokerTestSuite,
        # Add main classes from BrokerTestSuite when inspected
    )

    BROKER_TEST_SUITE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT02_BrokerTestSuite not available: {e}")
    BROKER_TEST_SUITE_AVAILABLE = False

# Black Swan Validator
try:
    from .SpyderT03_BlackSwanValidator import (
        BlackSwanValidator,
        # Add main classes from BlackSwanValidator when inspected
    )

    BLACK_SWAN_VALIDATOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT03_BlackSwanValidator not available: {e}")
    BLACK_SWAN_VALIDATOR_AVAILABLE = False

# Live IB Connection Test
try:
    from .SpyderT05_LiveIBConnectionTest import (
        LiveIBConnectionTest,
        # Add main classes from LiveIBConnectionTest when inspected
    )

    LIVE_IB_CONNECTION_TEST_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT05_LiveIBConnectionTest not available: {e}")
    LIVE_IB_CONNECTION_TEST_AVAILABLE = False

# System Integration Test
try:
    from .SpyderT08_FixedSystemIntegration import (
        FixedSystemIntegration,
        # Add main classes from FixedSystemIntegration when inspected
    )

    SYSTEM_INTEGRATION_TEST_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT08_FixedSystemIntegration not available: {e}")
    SYSTEM_INTEGRATION_TEST_AVAILABLE = False

# Test Dashboard
try:
    from .SpyderT09_TestDashboard import (
        TestDashboard,
        # Add main classes from TestDashboard when inspected
    )

    TEST_DASHBOARD_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT09_TestDashboard not available: {e}")
    TEST_DASHBOARD_AVAILABLE = False

# Full System Integration
try:
    from .SpyderT12_FullSystemIntegration import (
        FullSystemIntegration,
        # Add main classes from FullSystemIntegration when inspected
    )

    FULL_SYSTEM_INTEGRATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT12_FullSystemIntegration not available: {e}")
    FULL_SYSTEM_INTEGRATION_AVAILABLE = False

# System Health Monitor
try:
    from .SpyderT16_SystemHealthMonitor import (
        SystemHealthMonitor,
        # Add main classes from SystemHealthMonitor when inspected
    )

    SYSTEM_HEALTH_MONITOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT16_SystemHealthMonitor not available: {e}")
    SYSTEM_HEALTH_MONITOR_AVAILABLE = False

# System Diagnostic
try:
    from .SpyderT99_SystemDiagnostic import (
        SystemDiagnostic,
        # Add main classes from SystemDiagnostic when inspected
    )

    SYSTEM_DIAGNOSTIC_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderT99_SystemDiagnostic not available: {e}")
    SYSTEM_DIAGNOSTIC_AVAILABLE = False

# ==============================================================================
# PACKAGE CONVENIENCE FUNCTIONS
# ==============================================================================


def get_available_modules():
    """
    Get a list of available modules in the SpyderT_Testing package.

    Returns:
        dict: Dictionary with module availability status
    """
    return {
        "SpyderT01_UnitTestFramework": UNIT_TEST_FRAMEWORK_AVAILABLE,
        "SpyderT02_BrokerTestSuite": BROKER_TEST_SUITE_AVAILABLE,
        "SpyderT03_BlackSwanValidator": BLACK_SWAN_VALIDATOR_AVAILABLE,
        "SpyderT05_LiveIBConnectionTest": LIVE_IB_CONNECTION_TEST_AVAILABLE,
        "SpyderT08_FixedSystemIntegration": SYSTEM_INTEGRATION_TEST_AVAILABLE,
        "SpyderT09_TestDashboard": TEST_DASHBOARD_AVAILABLE,
        "SpyderT12_FullSystemIntegration": FULL_SYSTEM_INTEGRATION_AVAILABLE,
        "SpyderT16_SystemHealthMonitor": SYSTEM_HEALTH_MONITOR_AVAILABLE,
        "SpyderT99_SystemDiagnostic": SYSTEM_DIAGNOSTIC_AVAILABLE,
    }


def get_package_info():
    """
    Get comprehensive package information.

    Returns:
        dict: Package information including version, modules, and capabilities
    """
    available_modules = get_available_modules()
    total_modules = len(available_modules)
    available_count = sum(available_modules.values())

    return {
        "package_name": "SpyderT_Testing",
        "version": __version__,
        "author": __author__,
        "status": __status__,
        "total_modules": total_modules,
        "available_modules": available_count,
        "module_status": available_modules,
        "capabilities": {
            "unit_testing": UNIT_TEST_FRAMEWORK_AVAILABLE,
            "broker_testing": BROKER_TEST_SUITE_AVAILABLE,
            "black_swan_testing": BLACK_SWAN_VALIDATOR_AVAILABLE,
            "live_ib_testing": LIVE_IB_CONNECTION_TEST_AVAILABLE,
            "system_integration_testing": SYSTEM_INTEGRATION_TEST_AVAILABLE,
            "dashboard_testing": TEST_DASHBOARD_AVAILABLE,
            "full_system_testing": FULL_SYSTEM_INTEGRATION_AVAILABLE,
            "health_monitoring": SYSTEM_HEALTH_MONITOR_AVAILABLE,
            "system_diagnostics": SYSTEM_DIAGNOSTIC_AVAILABLE,
        },
    }


def create_test_suite():
    """
    Factory function to create a comprehensive test suite.

    Returns:
        dict: Dictionary containing test instances

    Raises:
        ImportError: If required test modules are not available
    """
    suite = {}

    if UNIT_TEST_FRAMEWORK_AVAILABLE:
        suite["unit_test_framework"] = UnitTestFramework()

    if BROKER_TEST_SUITE_AVAILABLE:
        suite["broker_test_suite"] = BrokerTestSuite()

    if BLACK_SWAN_VALIDATOR_AVAILABLE:
        suite["black_swan_validator"] = BlackSwanValidator()

    if LIVE_IB_CONNECTION_TEST_AVAILABLE:
        suite["live_ib_connection_test"] = LiveIBConnectionTest()

    if SYSTEM_INTEGRATION_TEST_AVAILABLE:
        suite["system_integration_test"] = FixedSystemIntegration()

    if TEST_DASHBOARD_AVAILABLE:
        suite["test_dashboard"] = TestDashboard()

    if FULL_SYSTEM_INTEGRATION_AVAILABLE:
        suite["full_system_integration"] = FullSystemIntegration()

    if SYSTEM_HEALTH_MONITOR_AVAILABLE:
        suite["system_health_monitor"] = SystemHealthMonitor()

    if SYSTEM_DIAGNOSTIC_AVAILABLE:
        suite["system_diagnostic"] = SystemDiagnostic()

    if not suite:
        raise ImportError("No test modules are available")

    return suite


def run_comprehensive_tests():
    """
    Run a comprehensive test suite across all available test modules.

    Returns:
        dict: Test results summary
    """
    try:
        suite = create_test_suite()
        results = {
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0,
            "test_results": {},
        }

        for test_name, test_instance in suite.items():
            print(f"🧪 Running {test_name}...")
            # This would need to be implemented based on the actual test interface
            # test_result = test_instance.run_tests()
            # results["test_results"][test_name] = test_result

        return results

    except Exception as e:
        print(f"❌ Error running comprehensive tests: {e}")
        return {"error": str(e)}


def validate_package():
    """
    Validate the package installation and module availability.

    Returns:
        bool: True if package is fully functional, False otherwise
    """
    try:
        info = get_package_info()
        print(f"🧪 {info['package_name']} v{info['version']}")
        print(
            f"✅ {info['available_modules']}/{info['total_modules']} modules available"
        )

        if info["available_modules"] == info["total_modules"]:
            print("🚀 All testing modules loaded successfully")
            return True
        else:
            print("⚠️ Some testing modules are missing")
            for module, status in info["module_status"].items():
                status_icon = "✅" if status else "❌"
                print(f"   {status_icon} {module}")
            return False

    except Exception as e:
        print(f"❌ Testing package validation failed: {e}")
        return False


# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Utility functions
    "get_available_modules",
    "get_package_info",
    "create_test_suite",
    "run_comprehensive_tests",
    "validate_package",
]

# Conditionally add available classes to __all__
if UNIT_TEST_FRAMEWORK_AVAILABLE:
    __all__.extend(["UnitTestFramework"])

if BROKER_TEST_SUITE_AVAILABLE:
    __all__.extend(["BrokerTestSuite"])

if BLACK_SWAN_VALIDATOR_AVAILABLE:
    __all__.extend(["BlackSwanValidator"])

if LIVE_IB_CONNECTION_TEST_AVAILABLE:
    __all__.extend(["LiveIBConnectionTest"])

if SYSTEM_INTEGRATION_TEST_AVAILABLE:
    __all__.extend(["FixedSystemIntegration"])

if TEST_DASHBOARD_AVAILABLE:
    __all__.extend(["TestDashboard"])

if FULL_SYSTEM_INTEGRATION_AVAILABLE:
    __all__.extend(["FullSystemIntegration"])

if SYSTEM_HEALTH_MONITOR_AVAILABLE:
    __all__.extend(["SystemHealthMonitor"])

if SYSTEM_DIAGNOSTIC_AVAILABLE:
    __all__.extend(["SystemDiagnostic"])

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Perform package validation on import
if __name__ != "__main__":
    validate_package()
else:
    # If running as main, show detailed package info
    print("=" * 70)
    print("SPYDER T - TESTING PACKAGE")
    print("=" * 70)
    validate_package()
    info = get_package_info()
    print("\nPackage Details:")
    for key, value in info.items():
        if key != "module_status":
            print(f"  {key}: {value}")
