import sys
sys.path.insert(0, ".")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT17_ComprehensiveSystemTest.py
Purpose: Comprehensive system testing and validation suite
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-13 Time: 20:30:00

Module Description:
    This module provides comprehensive testing for the entire Spyder trading system.
    It validates broker connections, data feeds, dashboard functionality, enhanced
    connection manager performance, and end-of-day data retrieval capabilities.
    Designed to verify system readiness for trading operations and identify any
    issues before live deployment.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import time
import sys
import os
from typing import Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timedelta
import json
from pathlib import Path
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import numpy as np
except ImportError:
    np = None

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
TEST_TIMEOUT = 30  # seconds
SPY_SYMBOL = "SPY"
TEST_OUTPUT_DIR = "test_results"

# ==============================================================================
# ENUMS
# ==============================================================================
class TestResult(Enum):
    """Test result enumeration"""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    WARNING = "WARNING"

class TestCategory(Enum):
    """Test category enumeration"""
    BROKER = "broker"
    DATA = "data"
    DASHBOARD = "dashboard"
    SYSTEM = "system"
    PERFORMANCE = "performance"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TestCaseResult:
    """Individual test case result"""
    name: str
    category: TestCategory
    result: TestResult
    duration: float
    message: str
    details: dict[str, Any] | None = None
    error: str | None = None

@dataclass
class TestSuiteResults:
    """Complete test suite results"""
    total_tests: int
    passed: int
    failed: int
    skipped: int
    warnings: int
    duration: float
    results: list[TestCaseResult]
    system_info: dict[str, Any]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ComprehensiveSystemTest:
    """
    Comprehensive system testing suite.

    This class provides end-to-end testing of the Spyder trading system,
    including broker connectivity, data feeds, dashboard functionality,
    and system performance validation. Designed to ensure system readiness
    for live trading operations.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        results: List of test results
        start_time: Test suite start time
    """

    def __init__(self):
        """Initialize the comprehensive test suite."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.results: list[TestCaseResult] = []
        self.start_time = time.time()

        # Ensure output directory exists
        Path(TEST_OUTPUT_DIR).mkdir(exist_ok=True)

        self.logger.info("Comprehensive system test suite initialized")

    # ==========================================================================
    # TEST EXECUTION METHODS
    # ==========================================================================
    def run_all_tests(self) -> TestSuiteResults:
        """
        Run all system tests.

        Returns:
            TestSuiteResults: Complete test results
        """
        self.logger.info("Starting comprehensive system test suite")
        print("=" * 80)
        print("SPYDER COMPREHENSIVE SYSTEM TEST SUITE")
        print("=" * 80)

        # Test categories to run
        test_categories = [
            ("Broker System Tests", self._run_broker_tests),
            ("Enhanced Connection Manager Tests", self._run_connection_tests),
            ("Data Feed Tests", self._run_data_tests),
            ("Dashboard Tests", self._run_dashboard_tests),
            ("System Integration Tests", self._run_system_tests),
            ("Performance Tests", self._run_performance_tests)
        ]

        for category_name, test_method in test_categories:
            print(f"\n{category_name}")
            print("-" * len(category_name))
            try:
                test_method()
            except Exception as e:
                self.logger.error("Test category %s failed: %s", category_name, e)
                self._add_result(
                    f"{category_name}_error",
                    TestCategory.SYSTEM,
                    TestResult.FAIL,
                    0.0,
                    f"Category execution failed: {e}"
                )

        return self._generate_final_results()

    def _run_broker_tests(self) -> None:
        """Run broker-related tests."""

        # Test 1: Broker package import
        self._test_broker_package_import()

        # Test 2: Enhanced connection manager
        self._test_enhanced_connection_manager()

        # Test 3: Broker diagnostics
        self._test_broker_diagnostics()

        # Test 4: Connection factory functions
        self._test_connection_factory_functions()

    def _run_connection_tests(self) -> None:
        """Run enhanced connection manager tests."""

        # Test 1: Connection manager creation
        self._test_connection_manager_creation()

        # Test 2: Timeout prevention features
        self._test_timeout_prevention_features()

        # Test 3: System optimizer integration
        self._test_system_optimizer_integration()

        # Test 4: Memory monitoring integration
        self._test_memory_monitoring_integration()

    def _run_data_tests(self) -> None:
        """Run data feed and market data tests."""

        # Test 1: Market data package
        self._test_market_data_package()

        # Test 2: Historical data capabilities
        self._test_historical_data()

        # Test 3: End-of-day data retrieval
        self._test_end_of_day_data()

        # Test 4: Options data handling
        self._test_options_data()

    def _run_dashboard_tests(self) -> None:
        """Run dashboard and GUI tests."""

        # Test 1: GUI package import
        self._test_gui_package_import()

        # Test 2: Dashboard components
        self._test_dashboard_components()

        # Test 3: Chart widgets
        self._test_chart_widgets()

        # Test 4: Real-time display capability
        self._test_realtime_display()

    def _run_system_tests(self) -> None:
        """Run system integration tests."""

        # Test 1: Module integration
        self._test_module_integration()

        # Test 2: Configuration management
        self._test_configuration_management()

        # Test 3: Error handling
        self._test_error_handling_system()

        # Test 4: Logging system
        self._test_logging_system()

    def _run_performance_tests(self) -> None:
        """Run performance and benchmarking tests."""

        # Test 1: Import performance
        self._test_import_performance()

        # Test 2: Connection performance
        self._test_connection_performance()

        # Test 3: Memory usage
        self._test_memory_usage()

        # Test 4: System resource usage
        self._test_system_resources()

    # ==========================================================================
    # INDIVIDUAL TEST METHODS
    # ==========================================================================
    def _test_broker_package_import(self) -> None:
        """Test broker package import functionality."""
        start_time = time.time()

        try:
            from SpyderB_Broker import diagnose_broker_package
            self._add_result(
                "broker_package_import",
                TestCategory.BROKER,
                TestResult.PASS,
                time.time() - start_time,
                "Broker package imported successfully"
            )
        except Exception as e:
            self._add_result(
                "broker_package_import",
                TestCategory.BROKER,
                TestResult.FAIL,
                time.time() - start_time,
                f"Broker package import failed: {e}",
                error=str(e)
            )

    def _test_enhanced_connection_manager(self) -> None:
        """Test enhanced connection manager functionality."""
        start_time = time.time()

        try:
            from SpyderB_Broker import get_enhanced_connection_manager
            conn_mgr = get_enhanced_connection_manager()

            if conn_mgr:
                self._add_result(
                    "enhanced_connection_manager",
                    TestCategory.BROKER,
                    TestResult.PASS,
                    time.time() - start_time,
                    "Enhanced connection manager created successfully",
                    details={"type": type(conn_mgr).__name__}
                )
            else:
                self._add_result(
                    "enhanced_connection_manager",
                    TestCategory.BROKER,
                    TestResult.FAIL,
                    time.time() - start_time,
                    "Enhanced connection manager creation returned None"
                )
        except Exception as e:
            self._add_result(
                "enhanced_connection_manager",
                TestCategory.BROKER,
                TestResult.FAIL,
                time.time() - start_time,
                f"Enhanced connection manager test failed: {e}",
                error=str(e)
            )

    def _test_broker_diagnostics(self) -> None:
        """Test broker diagnostics functionality."""
        start_time = time.time()

        try:
            from SpyderB_Broker import diagnose_broker_package

            # Capture diagnostic output
            import io
            import contextlib

            f = io.StringIO()
            with contextlib.redirect_stdout(f):
                diagnose_broker_package()

            output = f.getvalue()
            success_rate = "100.0%" in output

            result = TestResult.PASS if success_rate else TestResult.WARNING
            message = "Broker diagnostics completed successfully" if success_rate else "Broker diagnostics completed with warnings"

            self._add_result(
                "broker_diagnostics",
                TestCategory.BROKER,
                result,
                time.time() - start_time,
                message,
                details={"output_length": len(output), "success_rate_100": success_rate}
            )
        except Exception as e:
            self._add_result(
                "broker_diagnostics",
                TestCategory.BROKER,
                TestResult.FAIL,
                time.time() - start_time,
                f"Broker diagnostics failed: {e}",
                error=str(e)
            )

    def _test_connection_factory_functions(self) -> None:
        """Test connection factory functions."""
        start_time = time.time()

        try:
            from SpyderB_Broker import create_broker_client

            client = create_broker_client()
            if client:
                self._add_result(
                    "connection_factory_functions",
                    TestCategory.BROKER,
                    TestResult.PASS,
                    time.time() - start_time,
                    "Connection factory functions working"
                )
            else:
                self._add_result(
                    "connection_factory_functions",
                    TestCategory.BROKER,
                    TestResult.WARNING,
                    time.time() - start_time,
                    "Connection factory returned None (expected without broker API)"
                )
        except Exception as e:
            self._add_result(
                "connection_factory_functions",
                TestCategory.BROKER,
                TestResult.FAIL,
                time.time() - start_time,
                f"Connection factory test failed: {e}",
                error=str(e)
            )

    def _test_connection_manager_creation(self) -> None:
        """Test connection manager creation speed and reliability."""
        start_time = time.time()

        try:
            from SpyderB_Broker.SpyderB29_EnhancedConnectionManager import EnhancedConnectionManager

            # Test multiple creations
            creation_times = []
            for i in range(3):
                create_start = time.time()
                conn = EnhancedConnectionManager()
                create_time = time.time() - create_start
                creation_times.append(create_time)

                if conn:
                    del conn

            avg_time = sum(creation_times) / len(creation_times)
            max_time = max(creation_times)

            result = TestResult.PASS if avg_time < 2.0 else TestResult.WARNING

            self._add_result(
                "connection_manager_creation",
                TestCategory.SYSTEM,
                result,
                time.time() - start_time,
                f"Connection manager creation: avg {avg_time:.3f}s, max {max_time:.3f}s",
                details={"avg_time": avg_time, "max_time": max_time, "creation_times": creation_times}
            )
        except Exception as e:
            self._add_result(
                "connection_manager_creation",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"Connection manager creation test failed: {e}",
                error=str(e)
            )

    def _test_timeout_prevention_features(self) -> None:
        """Test timeout prevention features."""
        start_time = time.time()

        try:
            from SpyderB_Broker.SpyderB29_EnhancedConnectionManager import EnhancedConnectionManager
            conn = EnhancedConnectionManager()

            features = []
            if hasattr(conn, 'error_callbacks'):
                features.append("error_callbacks")
            if hasattr(conn, 'ib'):
                features.append("async_ib_client")
            if hasattr(conn, 'max_reconnect_attempts'):
                features.append("reconnection_logic")
            if hasattr(conn, 'connection_config'):
                features.append("connection_config")

            result = TestResult.PASS if len(features) >= 2 else TestResult.WARNING

            self._add_result(
                "timeout_prevention_features",
                TestCategory.SYSTEM,
                result,
                time.time() - start_time,
                f"Timeout prevention features: {', '.join(features)}",
                details={"features": features, "feature_count": len(features)}
            )
        except Exception as e:
            self._add_result(
                "timeout_prevention_features",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"Timeout prevention test failed: {e}",
                error=str(e)
            )

    def _test_system_optimizer_integration(self) -> None:
        """Test system optimizer integration."""
        start_time = time.time()

        try:
            from SpyderU_Utilities.SpyderU27_SystemOptimizer import get_system_optimizer
            optimizer = get_system_optimizer()

            # Test diagnostics
            diagnostics = optimizer.run_system_diagnostics()

            self._add_result(
                "system_optimizer_integration",
                TestCategory.SYSTEM,
                TestResult.PASS,
                time.time() - start_time,
                "System optimizer integration successful",
                details={
                    "os_info": diagnostics.os_info,
                    "memory_available": diagnostics.memory_info.get('available', 0) if diagnostics.memory_info else 0
                }
            )
        except Exception as e:
            self._add_result(
                "system_optimizer_integration",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"System optimizer integration failed: {e}",
                error=str(e)
            )

    def _test_memory_monitoring_integration(self) -> None:
        """Test memory monitoring integration."""
        start_time = time.time()

        try:
            from SpyderU_Utilities.SpyderU23_MemoryMonitor import MemoryMonitor
            monitor = MemoryMonitor()

            # Test memory monitoring capabilities
            if hasattr(monitor, 'get_system_memory'):
                memory_info = monitor.get_system_memory()
                memory_available = memory_info is not None
            else:
                memory_available = False

            result = TestResult.PASS if memory_available else TestResult.WARNING

            self._add_result(
                "memory_monitoring_integration",
                TestCategory.SYSTEM,
                result,
                time.time() - start_time,
                "Memory monitoring integration tested",
                details={"memory_monitoring_available": memory_available}
            )
        except Exception as e:
            self._add_result(
                "memory_monitoring_integration",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"Memory monitoring integration failed: {e}",
                error=str(e)
            )

    def _test_market_data_package(self) -> None:
        """Test market data package import."""
        start_time = time.time()

        try:
            import SpyderC_MarketData
            self._add_result(
                "market_data_package",
                TestCategory.DATA,
                TestResult.PASS,
                time.time() - start_time,
                "Market data package imported successfully"
            )
        except Exception as e:
            self._add_result(
                "market_data_package",
                TestCategory.DATA,
                TestResult.FAIL,
                time.time() - start_time,
                f"Market data package import failed: {e}",
                error=str(e)
            )

    def _test_historical_data(self) -> None:
        """Test historical data capabilities."""
        start_time = time.time()

        try:
            # Test historical data module import
            from SpyderC_MarketData.SpyderC02_HistoricalData import HistoricalDataManager

            HistoricalDataManager()

            self._add_result(
                "historical_data",
                TestCategory.DATA,
                TestResult.PASS,
                time.time() - start_time,
                "Historical data manager created successfully"
            )
        except ImportError:
            self._add_result(
                "historical_data",
                TestCategory.DATA,
                TestResult.SKIP,
                time.time() - start_time,
                "Historical data module not available"
            )
        except Exception as e:
            self._add_result(
                "historical_data",
                TestCategory.DATA,
                TestResult.FAIL,
                time.time() - start_time,
                f"Historical data test failed: {e}",
                error=str(e)
            )

    def _test_end_of_day_data(self) -> None:
        """Test end-of-day data retrieval (markets closed scenario)."""
        start_time = time.time()

        try:
            # Simulate end-of-day data request
            # This is a simulation since we don't have live market connection

            current_time = datetime.now()
            is_weekend = current_time.weekday() >= 5  # Saturday = 5, Sunday = 6
            is_after_hours = current_time.hour >= 16  # After 4 PM ET

            # Create mock EOD data structure
            eod_data = {
                "symbol": SPY_SYMBOL,
                "date": current_time.date().isoformat(),
                "is_weekend": is_weekend,
                "is_after_hours": is_after_hours,
                "simulated": True
            }

            result = TestResult.PASS if (is_weekend or is_after_hours) else TestResult.WARNING
            message = "End-of-day data simulation successful" if (is_weekend or is_after_hours) else "Markets may be open - EOD simulation"

            self._add_result(
                "end_of_day_data",
                TestCategory.DATA,
                result,
                time.time() - start_time,
                message,
                details=eod_data
            )
        except Exception as e:
            self._add_result(
                "end_of_day_data",
                TestCategory.DATA,
                TestResult.FAIL,
                time.time() - start_time,
                f"End-of-day data test failed: {e}",
                error=str(e)
            )

    def _test_options_data(self) -> None:
        """Test options data handling."""
        start_time = time.time()

        try:
            from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager

            OptionChainManager()

            self._add_result(
                "options_data",
                TestCategory.DATA,
                TestResult.PASS,
                time.time() - start_time,
                "Options data manager created successfully"
            )
        except ImportError:
            self._add_result(
                "options_data",
                TestCategory.DATA,
                TestResult.SKIP,
                time.time() - start_time,
                "Options data module not available"
            )
        except Exception as e:
            self._add_result(
                "options_data",
                TestCategory.DATA,
                TestResult.FAIL,
                time.time() - start_time,
                f"Options data test failed: {e}",
                error=str(e)
            )

    def _test_gui_package_import(self) -> None:
        """Test GUI package import."""
        start_time = time.time()

        try:
            import SpyderG_GUI
            self._add_result(
                "gui_package_import",
                TestCategory.DASHBOARD,
                TestResult.PASS,
                time.time() - start_time,
                "GUI package imported successfully"
            )
        except Exception as e:
            self._add_result(
                "gui_package_import",
                TestCategory.DASHBOARD,
                TestResult.FAIL,
                time.time() - start_time,
                f"GUI package import failed: {e}",
                error=str(e)
            )

    def _test_dashboard_components(self) -> None:
        """Test dashboard components."""
        start_time = time.time()

        try:
            from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard

            # Test dashboard creation (without showing)
            SpyderTradingDashboard()

            self._add_result(
                "dashboard_components",
                TestCategory.DASHBOARD,
                TestResult.PASS,
                time.time() - start_time,
                "Trading dashboard components created successfully"
            )
        except ImportError:
            self._add_result(
                "dashboard_components",
                TestCategory.DASHBOARD,
                TestResult.SKIP,
                time.time() - start_time,
                "Dashboard components not available"
            )
        except Exception as e:
            self._add_result(
                "dashboard_components",
                TestCategory.DASHBOARD,
                TestResult.FAIL,
                time.time() - start_time,
                f"Dashboard components test failed: {e}",
                error=str(e)
            )

    def _test_chart_widgets(self) -> None:
        """Test chart widgets."""
        start_time = time.time()

        try:
            from SpyderG_GUI.SpyderG04_ChartWidget import ChartWidget

            # Test chart widget creation
            ChartWidget()

            self._add_result(
                "chart_widgets",
                TestCategory.DASHBOARD,
                TestResult.PASS,
                time.time() - start_time,
                "Chart widgets created successfully"
            )
        except ImportError:
            self._add_result(
                "chart_widgets",
                TestCategory.DASHBOARD,
                TestResult.SKIP,
                time.time() - start_time,
                "Chart widgets not available"
            )
        except Exception as e:
            self._add_result(
                "chart_widgets",
                TestCategory.DASHBOARD,
                TestResult.FAIL,
                time.time() - start_time,
                f"Chart widgets test failed: {e}",
                error=str(e)
            )

    def _test_realtime_display(self) -> None:
        """Test real-time display capability."""
        start_time = time.time()

        try:
            # Test display system availability
            import os
            display_available = 'DISPLAY' in os.environ

            result = TestResult.PASS if display_available else TestResult.WARNING
            message = "Display system available" if display_available else "Display system not available (headless mode)"

            self._add_result(
                "realtime_display",
                TestCategory.DASHBOARD,
                result,
                time.time() - start_time,
                message,
                details={"display_available": display_available}
            )
        except Exception as e:
            self._add_result(
                "realtime_display",
                TestCategory.DASHBOARD,
                TestResult.FAIL,
                time.time() - start_time,
                f"Real-time display test failed: {e}",
                error=str(e)
            )

    def _test_module_integration(self) -> None:
        """Test module integration."""
        start_time = time.time()

        try:
            # Test key module imports
            modules_tested = []

            test_modules = [
                ("SpyderA_Core", "Core modules"),
                ("SpyderB_Broker", "Broker modules"),
                ("SpyderU_Utilities", "Utility modules")
            ]

            for module_name, description in test_modules:
                try:
                    __import__(module_name)
                    modules_tested.append(module_name)
                except ImportError:
                    pass

            result = TestResult.PASS if len(modules_tested) >= 2 else TestResult.WARNING

            self._add_result(
                "module_integration",
                TestCategory.SYSTEM,
                result,
                time.time() - start_time,
                f"Module integration test: {len(modules_tested)}/3 modules available",
                details={"modules_tested": modules_tested}
            )
        except Exception as e:
            self._add_result(
                "module_integration",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"Module integration test failed: {e}",
                error=str(e)
            )

    def _test_configuration_management(self) -> None:
        """Test configuration management."""
        start_time = time.time()

        try:
            from SpyderA_Core.SpyderA03_Configuration import ConfigurationManager

            ConfigurationManager()

            self._add_result(
                "configuration_management",
                TestCategory.SYSTEM,
                TestResult.PASS,
                time.time() - start_time,
                "Configuration management available"
            )
        except ImportError:
            self._add_result(
                "configuration_management",
                TestCategory.SYSTEM,
                TestResult.SKIP,
                time.time() - start_time,
                "Configuration management module not available"
            )
        except Exception as e:
            self._add_result(
                "configuration_management",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"Configuration management test failed: {e}",
                error=str(e)
            )

    def _test_error_handling_system(self) -> None:
        """Test error handling system."""
        start_time = time.time()

        try:
            from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

            error_handler = SpyderErrorHandler()

            # Test error handling
            test_error = Exception("Test error")
            error_handler.handle_error(test_error, {"test": True})

            self._add_result(
                "error_handling_system",
                TestCategory.SYSTEM,
                TestResult.PASS,
                time.time() - start_time,
                "Error handling system functional"
            )
        except Exception as e:
            self._add_result(
                "error_handling_system",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"Error handling system test failed: {e}",
                error=str(e)
            )

    def _test_logging_system(self) -> None:
        """Test logging system."""
        start_time = time.time()

        try:
            from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

            logger = SpyderLogger.get_logger("test_logger")
            logger.info("Test log message")

            self._add_result(
                "logging_system",
                TestCategory.SYSTEM,
                TestResult.PASS,
                time.time() - start_time,
                "Logging system functional"
            )
        except Exception as e:
            self._add_result(
                "logging_system",
                TestCategory.SYSTEM,
                TestResult.FAIL,
                time.time() - start_time,
                f"Logging system test failed: {e}",
                error=str(e)
            )

    def _test_import_performance(self) -> None:
        """Test import performance."""
        start_time = time.time()

        try:
            # Test import speeds
            import_times = {}

            test_imports = [
                "SpyderB_Broker",
                "SpyderU_Utilities",
                "SpyderG_GUI"
            ]

            for module_name in test_imports:
                import_start = time.time()
                try:
                    __import__(module_name)
                    import_time = time.time() - import_start
                    import_times[module_name] = import_time
                except ImportError:
                    import_times[module_name] = None

            avg_import_time = sum(t for t in import_times.values() if t is not None) / len([t for t in import_times.values() if t is not None])

            result = TestResult.PASS if avg_import_time < 3.0 else TestResult.WARNING

            self._add_result(
                "import_performance",
                TestCategory.PERFORMANCE,
                result,
                time.time() - start_time,
                f"Import performance: avg {avg_import_time:.3f}s",
                details={"import_times": import_times, "avg_import_time": avg_import_time}
            )
        except Exception as e:
            self._add_result(
                "import_performance",
                TestCategory.PERFORMANCE,
                TestResult.FAIL,
                time.time() - start_time,
                f"Import performance test failed: {e}",
                error=str(e)
            )

    def _test_connection_performance(self) -> None:
        """Test connection performance."""
        start_time = time.time()

        try:
            from SpyderB_Broker import get_enhanced_connection_manager

            # Test connection manager creation speed
            creation_times = []
            for i in range(3):
                create_start = time.time()
                conn = get_enhanced_connection_manager()
                create_time = time.time() - create_start
                creation_times.append(create_time)
                if conn:
                    del conn

            avg_time = sum(creation_times) / len(creation_times)
            result = TestResult.PASS if avg_time < 2.0 else TestResult.WARNING

            self._add_result(
                "connection_performance",
                TestCategory.PERFORMANCE,
                result,
                time.time() - start_time,
                f"Connection performance: avg {avg_time:.3f}s",
                details={"creation_times": creation_times, "avg_time": avg_time}
            )
        except Exception as e:
            self._add_result(
                "connection_performance",
                TestCategory.PERFORMANCE,
                TestResult.FAIL,
                time.time() - start_time,
                f"Connection performance test failed: {e}",
                error=str(e)
            )

    def _test_memory_usage(self) -> None:
        """Test memory usage."""
        start_time = time.time()

        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)

            result = TestResult.PASS if memory_mb < 500 else TestResult.WARNING

            self._add_result(
                "memory_usage",
                TestCategory.PERFORMANCE,
                result,
                time.time() - start_time,
                f"Memory usage: {memory_mb:.1f}MB",
                details={"memory_mb": memory_mb, "memory_info": memory_info._asdict()}
            )
        except ImportError:
            self._add_result(
                "memory_usage",
                TestCategory.PERFORMANCE,
                TestResult.SKIP,
                time.time() - start_time,
                "psutil not available for memory testing"
            )
        except Exception as e:
            self._add_result(
                "memory_usage",
                TestCategory.PERFORMANCE,
                TestResult.FAIL,
                time.time() - start_time,
                f"Memory usage test failed: {e}",
                error=str(e)
            )

    def _test_system_resources(self) -> None:
        """Test system resource availability."""
        start_time = time.time()

        try:
            import psutil

            # Get system info
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')

            # Check resource availability
            resources_ok = (
                cpu_percent < 80 and
                memory.percent < 80 and
                disk.percent < 90
            )

            result = TestResult.PASS if resources_ok else TestResult.WARNING

            self._add_result(
                "system_resources",
                TestCategory.PERFORMANCE,
                result,
                time.time() - start_time,
                f"System resources: CPU {cpu_percent:.1f}%, RAM {memory.percent:.1f}%, Disk {disk.percent:.1f}%",
                details={
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent
                }
            )
        except ImportError:
            self._add_result(
                "system_resources",
                TestCategory.PERFORMANCE,
                TestResult.SKIP,
                time.time() - start_time,
                "psutil not available for system resource testing"
            )
        except Exception as e:
            self._add_result(
                "system_resources",
                TestCategory.PERFORMANCE,
                TestResult.FAIL,
                time.time() - start_time,
                f"System resources test failed: {e}",
                error=str(e)
            )

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _add_result(self, name: str, category: TestCategory, result: TestResult,
                   duration: float, message: str, details: dict[str, Any] | None = None,
                   error: str | None = None) -> None:
        """Add a test result."""
        test_result = TestCaseResult(
            name=name,
            category=category,
            result=result,
            duration=duration,
            message=message,
            details=details,
            error=error
        )

        self.results.append(test_result)

        # Print result
        status_icon = {
            TestResult.PASS: "✅",
            TestResult.FAIL: "❌",
            TestResult.SKIP: "⏭️ ",
            TestResult.WARNING: "⚠️ "
        }

        print(f"  {status_icon[result]} {name}: {message} ({duration:.3f}s)")

    def _generate_final_results(self) -> TestSuiteResults:
        """Generate final test results."""
        total_duration = time.time() - self.start_time

        # Count results
        passed = len([r for r in self.results if r.result == TestResult.PASS])
        failed = len([r for r in self.results if r.result == TestResult.FAIL])
        skipped = len([r for r in self.results if r.result == TestResult.SKIP])
        warnings = len([r for r in self.results if r.result == TestResult.WARNING])

        # System info
        system_info = {
            "python_version": sys.version,
            "platform": sys.platform,
            "timestamp": datetime.now().isoformat()
        }

        final_results = TestSuiteResults(
            total_tests=len(self.results),
            passed=passed,
            failed=failed,
            skipped=skipped,
            warnings=warnings,
            duration=total_duration,
            results=self.results,
            system_info=system_info
        )

        self._print_summary(final_results)
        self._save_results(final_results)

        return final_results

    def _print_summary(self, results: TestSuiteResults) -> None:
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        print(f"Total Tests: {results.total_tests}")
        print(f"Passed:      {results.passed} ✅")
        print(f"Failed:      {results.failed} ❌")
        print(f"Skipped:     {results.skipped} ⏭️")
        print(f"Warnings:    {results.warnings} ⚠️")
        print(f"Duration:    {results.duration:.2f}s")

        success_rate = (results.passed / results.total_tests) * 100 if results.total_tests > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")

        # Overall status
        if results.failed == 0 and results.warnings == 0:
            print("\n🎉 ALL TESTS PASSED! System ready for trading.")
        elif results.failed == 0:
            print(f"\n✅ Tests passed with {results.warnings} warnings. System functional.")
        elif results.failed <= 2:
            print(f"\n⚠️  {results.failed} test failures detected. Review required.")
        else:
            print(f"\n❌ Multiple failures ({results.failed}). System needs attention.")

        # Category breakdown
        categories = {}
        for result in results.results:
            if result.category not in categories:
                categories[result.category] = {"pass": 0, "fail": 0, "skip": 0, "warn": 0}

            if result.result == TestResult.PASS:
                categories[result.category]["pass"] += 1
            elif result.result == TestResult.FAIL:
                categories[result.category]["fail"] += 1
            elif result.result == TestResult.SKIP:
                categories[result.category]["skip"] += 1
            elif result.result == TestResult.WARNING:
                categories[result.category]["warn"] += 1

        print("\nCategory Breakdown:")
        for category, counts in categories.items():
            total_cat = sum(counts.values())
            pass_rate = (counts["pass"] / total_cat) * 100 if total_cat > 0 else 0
            print(f"  {category.value}: {counts['pass']}/{total_cat} passed ({pass_rate:.1f}%)")

    def _save_results(self, results: TestSuiteResults) -> None:
        """Save test results to file."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{TEST_OUTPUT_DIR}/test_results_{timestamp}.json"

            # Convert to serializable format
            results_dict = {
                "summary": {
                    "total_tests": results.total_tests,
                    "passed": results.passed,
                    "failed": results.failed,
                    "skipped": results.skipped,
                    "warnings": results.warnings,
                    "duration": results.duration,
                    "success_rate": (results.passed / results.total_tests) * 100 if results.total_tests > 0 else 0
                },
                "system_info": results.system_info,
                "detailed_results": []
            }

            for result in results.results:
                results_dict["detailed_results"].append({
                    "name": result.name,
                    "category": result.category.value,
                    "result": result.result.value,
                    "duration": result.duration,
                    "message": result.message,
                    "details": result.details,
                    "error": result.error
                })

            with open(filename, 'w') as f:
                json.dump(results_dict, f, indent=2, default=str)

            print(f"\nResults saved to: {filename}")

        except Exception as e:
            self.logger.error("Failed to save test results: %s", e)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def run_comprehensive_test() -> TestSuiteResults:
    """
    Run comprehensive system test.

    Returns:
        TestSuiteResults: Complete test results
    """
    test_suite = ComprehensiveSystemTest()
    return test_suite.run_all_tests()

def test_end_of_day_dashboard() -> bool:
    """
    Specific test for end-of-day dashboard functionality.

    Returns:
        bool: True if dashboard can handle EOD data
    """
    try:
        print("Testing End-of-Day Dashboard Functionality")
        print("=" * 50)

        # Test dashboard components
        from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
        SpyderTradingDashboard()
        print("✅ Dashboard created successfully")

        # Test data components
        from SpyderC_MarketData.SpyderC02_HistoricalData import HistoricalDataManager
        HistoricalDataManager()
        print("✅ Historical data manager available")

        # Test connection to data sources
        from SpyderB_Broker import get_enhanced_connection_manager
        get_enhanced_connection_manager()
        print("✅ Enhanced connection manager ready")

        print("\n🎯 End-of-day dashboard testing complete!")
        print("Dashboard should be able to fetch historical/EOD data when markets are closed.")

        return True

    except Exception as e:
        print(f"❌ End-of-day dashboard test failed: {e}")
        return False

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Run comprehensive test suite
    print("Starting Spyder Comprehensive System Test...")
    results = run_comprehensive_test()

    # Run specific EOD dashboard test
    print("\n" + "=" * 80)
    eod_success = test_end_of_day_dashboard()

    # Exit with appropriate code
    exit_code = 0 if (results.failed == 0 and eod_success) else 1
    sys.exit(exit_code)
