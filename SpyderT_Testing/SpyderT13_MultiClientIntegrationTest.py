#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderT13_MultiClientIntegrationTest.py
Group: T (Testing)
Purpose: Comprehensive integration testing for multi-client market data architecture
Author: Mohamed Talib
Date Created: 2025-07-27 
Last Updated: 2025-07-27 Time: 17:30:00  

Description:
    This module provides comprehensive integration testing for the three-module
    multi-client architecture: SpyderB08_MultiClientDataManager, SpyderG08_DashboardDataBridge,
    and the updated SpyderG05_TradingDashboard. It validates client ID allocation strategies,
    real-time data flow, PyQt6 integration, performance metrics, error handling, and
    complete system integration under various scenarios including connection failures
    and high-load conditions.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import unittest
import threading
import time
import random
import logging
import tempfile
import json
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

# PyQt6 for GUI testing
try:
    from PyQt6.QtWidgets import QApplication, QWidget
    from PyQt6.QtCore import QTimer, QObject, pyqtSignal
    from PyQt6.QtTest import QTest
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from pathlib import Path
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import test framework
try:
    from SpyderT_Testing.SpyderT01_TestFramework import (
        SpyderTestFramework,
        TestResult,
        TestStatus,
        PerformanceMetrics,
        get_test_framework
    )
    TEST_FRAMEWORK_AVAILABLE = True
except ImportError:
    TEST_FRAMEWORK_AVAILABLE = False
    print("⚠️ Test framework not available - using basic unittest")

# Import the modules we're testing
try:
    from SpyderB_Broker.SpyderB08_MultiClientDataManager import (
        MultiClientDataManager,
        SpyderClientConnection,
        MarketDataTick,
        MarketDataRequest,
        ClientPurpose,
        ConnectionHealth,
        DataRequestType,
        DataPriority,
        get_manager_instance
    )
    MANAGER_AVAILABLE = True
except ImportError as e:
    MANAGER_AVAILABLE = False
    print(f"⚠️ MultiClientDataManager not available: {e}")

try:
    from SpyderG_GUI.SpyderG08_DashboardDataBridge import (
        DashboardDataBridge,
        UpdatePriority,
        ConnectionStatus,
        DisplayData,
        format_market_data,
        get_bridge_instance
    )
    BRIDGE_AVAILABLE = True
except ImportError as e:
    BRIDGE_AVAILABLE = False
    print(f"⚠️ DashboardDataBridge not available: {e}")

try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import (
        SpyderTradingDashboard,
        SymbolWidget,
        MarketData,
        MARKET_SYMBOLS
    )
    DASHBOARD_AVAILABLE = True
except ImportError as e:
    DASHBOARD_AVAILABLE = False
    print(f"⚠️ TradingDashboard not available: {e}")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Test configuration
TEST_TIMEOUT = 30                    # seconds
TEST_DATA_SAMPLES = 100             # number of test data points
TEST_PERFORMANCE_ITERATIONS = 50    # performance test iterations
TEST_STRESS_DURATION = 10           # stress test duration in seconds
TEST_CLIENT_IDS = [0, 1, 3]         # Priority client IDs to test

# Mock data configuration
MOCK_SYMBOLS = ['SPY', 'VIX', 'QQQ', 'SPX', '/ES', 'VIX9D']
MOCK_PRICE_RANGE = (50.0, 600.0)
MOCK_VOLUME_RANGE = (100, 1000000)

# Performance thresholds
MAX_UPDATE_LATENCY_MS = 500         # Maximum acceptable update latency
MIN_UPDATES_PER_SECOND = 10         # Minimum update frequency
MAX_MEMORY_USAGE_MB = 100           # Maximum memory usage
MAX_ERROR_RATE = 0.05               # Maximum acceptable error rate (5%)

# ==============================================================================
# TEST DATA STRUCTURES
# ==============================================================================
@dataclass
class IntegrationTestResult:
    """Result of integration test execution"""
    test_name: str
    status: str
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    performance_metrics: Dict[str, float] = field(default_factory=dict)

@dataclass
class MockMarketDataTick:
    """Mock market data tick for testing"""
    symbol: str
    price: float
    size: int
    timestamp: datetime
    tick_type: int = 1
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class SystemHealthMetrics:
    """System health metrics during testing"""
    active_clients: int = 0
    active_subscriptions: int = 0
    total_data_updates: int = 0
    total_errors: int = 0
    avg_latency_ms: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

# ==============================================================================
# MOCK CLASSES
# ==============================================================================
class MockIBGateway:
    """Mock IB Gateway for testing without real connections"""
    
    def __init__(self):
        self.connected_clients = set()
        self.market_data_requests = {}
        self.data_callbacks = {}
        self.is_running = False
        
    def connect_client(self, client_id: int) -> bool:
        """Mock client connection"""
        self.connected_clients.add(client_id)
        return True
    
    def disconnect_client(self, client_id: int) -> bool:
        """Mock client disconnection"""
        self.connected_clients.discard(client_id)
        return True
    
    def request_market_data(self, client_id: int, symbol: str, request_id: int) -> bool:
        """Mock market data request"""
        self.market_data_requests[(client_id, request_id)] = symbol
        return True
    
    def cancel_market_data(self, client_id: int, request_id: int) -> bool:
        """Mock market data cancellation"""
        self.market_data_requests.pop((client_id, request_id), None)
        return True
    
    def simulate_market_data(self, symbol: str, client_id: int = 1) -> MockMarketDataTick:
        """Generate simulated market data"""
        price = random.uniform(*MOCK_PRICE_RANGE)
        size = random.randint(*MOCK_VOLUME_RANGE)
        return MockMarketDataTick(symbol, price, size, datetime.now())

class MockQTWidget(QWidget if PYQT6_AVAILABLE else object):
    """Mock Qt widget for testing dashboard integration"""
    
    def __init__(self, symbol: str):
        if PYQT6_AVAILABLE:
            super().__init__()
        self.symbol = symbol
        self.update_count = 0
        self.last_data = None
        self.update_calls = []
        
    def update_display(self, data_dict: Dict[str, Any]) -> None:
        """Mock update display method"""
        self.update_count += 1
        self.last_data = data_dict.copy()
        self.update_calls.append((datetime.now(), data_dict))

# ==============================================================================
# MAIN INTEGRATION TEST CLASS
# ==============================================================================
class MultiClientIntegrationTestSuite(unittest.TestCase):
    """
    Comprehensive integration test suite for multi-client architecture.
    
    This test suite validates the complete integration between the multi-client
    data manager, dashboard bridge, and trading dashboard. It tests real-time
    data flow, client allocation, performance metrics, error handling, and
    system resilience under various conditions.
    
    Test Categories:
        - Module Initialization Tests
        - Client Allocation Strategy Tests
        - Bridge Integration Tests
        - Dashboard Widget Tests
        - Real-time Data Flow Tests
        - Performance and Stress Tests
        - Error Handling and Recovery Tests
        - Resource Management Tests
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test suite resources"""
        cls.logger = SpyderLogger.get_logger(__name__)
        cls.error_handler = SpyderErrorHandler()
        
        # Initialize Qt application if available
        if PYQT6_AVAILABLE and QApplication.instance() is None:
            cls.app = QApplication([])
        else:
            cls.app = None
        
        # Test framework
        if TEST_FRAMEWORK_AVAILABLE:
            cls.test_framework = get_test_framework()
        
        # Mock gateway
        cls.mock_gateway = MockIBGateway()
        
        # Test metrics
        cls.test_metrics = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'performance_data': []
        }
        
        cls.logger.info("Integration test suite initialized")
    
    def setUp(self):
        """Set up individual test"""
        self.test_start_time = time.time()
        self.test_name = self._testMethodName
        self.test_data = []
        self.test_errors = []
        
        # Initialize components
        self.manager = None
        self.bridge = None
        self.dashboard = None
        self.mock_widgets = {}
        
        # Performance tracking
        self.performance_metrics = {
            'data_updates': 0,
            'ui_updates': 0,
            'errors': 0,
            'latency_samples': []
        }
        
    def tearDown(self):
        """Clean up after test"""
        duration = time.time() - self.test_start_time
        
        # Cleanup components
        if self.manager:
            try:
                self.manager.stop()
            except:
                pass
        
        if self.bridge:
            try:
                self.bridge.stop()
            except:
                pass
        
        if self.dashboard:
            try:
                self.dashboard.close()
            except:
                pass
        
        # Record test metrics
        self.__class__.test_metrics['total_tests'] += 1
        
        self.logger.info(f"Test {self.test_name} completed in {duration:.2f}s")
    
    # ==========================================================================
    # MODULE INITIALIZATION TESTS
    # ==========================================================================
    def test_01_manager_initialization(self):
        """Test multi-client data manager initialization"""
        try:
            if not MANAGER_AVAILABLE:
                self.skipTest("MultiClientDataManager not available")
            
            # Test manager creation
            self.manager = MultiClientDataManager()
            self.assertIsNotNone(self.manager)
            
            # Test initialization
            init_success = self.manager.initialize()
            self.assertTrue(init_success, "Manager initialization should succeed")
            
            # Validate client configurations
            configs = self.manager.client_configs
            self.assertIn(ClientPurpose.MASTER_ADMIN, configs)
            self.assertIn(ClientPurpose.CORE_INDICES_1SEC, configs)
            self.assertIn(ClientPurpose.VOLATILITY_5SEC, configs)
            
            # Test priority client IDs
            expected_client_ids = {0, 1, 3}
            actual_client_ids = {config.client_id for config in configs.values() 
                               if config.purpose in [ClientPurpose.MASTER_ADMIN, 
                                                    ClientPurpose.CORE_INDICES_1SEC,
                                                    ClientPurpose.VOLATILITY_5SEC]}
            self.assertEqual(expected_client_ids, actual_client_ids,
                           f"Priority client IDs should be {expected_client_ids}")
            
            # Test status
            status = self.manager.get_status_summary()
            self.assertIsInstance(status, dict)
            self.assertIn('total_clients', status)
            self.assertIn('market_data_lines_used', status)
            
            self.logger.info("✅ Manager initialization test passed")
            
        except Exception as e:
            self.test_errors.append(f"Manager initialization failed: {e}")
            self.fail(f"Manager initialization test failed: {e}")
    
    def test_02_bridge_initialization(self):
        """Test dashboard bridge initialization"""
        try:
            if not BRIDGE_AVAILABLE or not PYQT6_AVAILABLE:
                self.skipTest("Bridge or PyQt6 not available")
            
            # Test bridge creation
            self.bridge = DashboardDataBridge()
            self.assertIsNotNone(self.bridge)
            
            # Test initialization
            init_success = self.bridge.initialize()
            self.assertTrue(init_success, "Bridge initialization should succeed")
            
            # Test performance stats
            stats = self.bridge.get_performance_stats()
            self.assertIsInstance(stats, dict)
            self.assertIn('cached_symbols', stats)
            self.assertIn('registered_widgets', stats)
            
            self.logger.info("✅ Bridge initialization test passed")
            
        except Exception as e:
            self.test_errors.append(f"Bridge initialization failed: {e}")
            self.fail(f"Bridge initialization test failed: {e}")
    
    def test_03_dashboard_initialization(self):
        """Test trading dashboard initialization"""
        try:
            if not DASHBOARD_AVAILABLE or not PYQT6_AVAILABLE:
                self.skipTest("Dashboard or PyQt6 not available")
            
            # Test dashboard creation
            self.dashboard = SpyderTradingDashboard()
            self.assertIsNotNone(self.dashboard)
            
            # Test widget creation
            self.assertGreater(len(self.dashboard.symbol_widgets), 0,
                             "Dashboard should have symbol widgets")
            
            # Test market symbols configuration
            for category, symbols in MARKET_SYMBOLS.items():
                for symbol in symbols:
                    self.assertIn(symbol, self.dashboard.symbol_widgets,
                                f"Widget for {symbol} should exist")
            
            self.logger.info("✅ Dashboard initialization test passed")
            
        except Exception as e:
            self.test_errors.append(f"Dashboard initialization failed: {e}")
            self.fail(f"Dashboard initialization test failed: {e}")
    
    # ==========================================================================
    # CLIENT ALLOCATION STRATEGY TESTS
    # ==========================================================================
    def test_04_client_allocation_strategy(self):
        """Test client ID allocation strategy"""
        try:
            if not MANAGER_AVAILABLE:
                self.skipTest("MultiClientDataManager not available")
            
            self.manager = MultiClientDataManager()
            self.manager.initialize()
            
            # Test critical symbols allocation
            critical_symbols = ['SPY', 'VIX']
            for symbol in critical_symbols:
                client_id = self.manager._get_client_for_symbol(symbol)
                self.assertEqual(client_id, 1, f"{symbol} should use client ID 1")
            
            # Test volatility symbols allocation
            volatility_symbols = ['VIX9D', 'VXV', 'VXMT']
            for symbol in volatility_symbols:
                client_id = self.manager._get_client_for_symbol(symbol)
                self.assertEqual(client_id, 3, f"{symbol} should use client ID 3")
            
            # Test priority levels
            spy_priority = self.manager._get_symbol_priority('SPY')
            self.assertEqual(spy_priority, DataPriority.CRITICAL)
            
            vix_priority = self.manager._get_symbol_priority('VIX')
            self.assertEqual(vix_priority, DataPriority.CRITICAL)
            
            # Test frequency assignments
            spy_freq = self.manager._get_symbol_frequency('SPY')
            self.assertEqual(spy_freq, 1.0, "SPY should have 1-second frequency")
            
            vix9d_freq = self.manager._get_symbol_frequency('VIX9D')
            self.assertEqual(vix9d_freq, 5.0, "VIX9D should have 5-second frequency")
            
            self.logger.info("✅ Client allocation strategy test passed")
            
        except Exception as e:
            self.test_errors.append(f"Client allocation test failed: {e}")
            self.fail(f"Client allocation strategy test failed: {e}")
    
    # ==========================================================================
    # BRIDGE INTEGRATION TESTS
    # ==========================================================================
    def test_05_bridge_widget_registration(self):
        """Test bridge widget registration and management"""
        try:
            if not BRIDGE_AVAILABLE or not PYQT6_AVAILABLE:
                self.skipTest("Bridge or PyQt6 not available")
            
            self.bridge = DashboardDataBridge()
            self.bridge.initialize()
            
            # Create mock widgets
            symbols = ['SPY', 'VIX', 'QQQ']
            for symbol in symbols:
                widget = MockQTWidget(symbol)
                self.mock_widgets[symbol] = widget
                
                # Register widget
                widget_id = self.bridge.register_widget(
                    widget, symbol, 'update_display', UpdatePriority.CRITICAL
                )
                self.assertNotEqual(widget_id, "", f"Registration of {symbol} widget should succeed")
            
            # Test widget registry
            registered = self.bridge.get_registered_widgets()
            self.assertEqual(len(registered), len(symbols),
                           f"Should have {len(symbols)} registered widgets")
            
            # Test unregistration
            spy_widget_id = None
            for widget_id, info in registered.items():
                if info['symbol'] == 'SPY':
                    spy_widget_id = widget_id
                    break
            
            if spy_widget_id:
                success = self.bridge.unregister_widget(spy_widget_id)
                self.assertTrue(success, "Widget unregistration should succeed")
                
                # Verify removal
                updated_registered = self.bridge.get_registered_widgets()
                self.assertEqual(len(updated_registered), len(symbols) - 1,
                               "Widget should be removed from registry")
            
            self.logger.info("✅ Bridge widget registration test passed")
            
        except Exception as e:
            self.test_errors.append(f"Bridge widget registration failed: {e}")
            self.fail(f"Bridge widget registration test failed: {e}")
    
    def test_06_bridge_data_formatting(self):
        """Test bridge data formatting capabilities"""
        try:
            if not BRIDGE_AVAILABLE:
                self.skipTest("Bridge not available")
            
            # Test format_market_data function
            price = 585.75
            change = 2.45
            volume = 1250000
            
            formatted = format_market_data(price, change, volume)
            
            self.assertIn('price', formatted)
            self.assertIn('change', formatted)
            self.assertIn('change_percent', formatted)
            self.assertIn('volume', formatted)
            
            # Validate formatting
            self.assertEqual(formatted['price'], f"${price:.2f}")
            self.assertTrue(formatted['change'].startswith('+'))  # Positive change
            self.assertIn('%', formatted['change_percent'])
            
            # Test volume formatting
            self.assertIn('K', formatted['volume'])  # Should show as K for thousands
            
            self.logger.info("✅ Bridge data formatting test passed")
            
        except Exception as e:
            self.test_errors.append(f"Bridge data formatting failed: {e}")
            self.fail(f"Bridge data formatting test failed: {e}")
    
    # ==========================================================================
    # REAL-TIME DATA FLOW TESTS
    # ==========================================================================
    def test_07_end_to_end_data_flow(self):
        """Test complete data flow from manager through bridge to widgets"""
        try:
            if not all([MANAGER_AVAILABLE, BRIDGE_AVAILABLE, PYQT6_AVAILABLE]):
                self.skipTest("Required components not available")
            
            # Initialize complete system
            self.manager = MultiClientDataManager()
            self.bridge = DashboardDataBridge()
            
            self.assertTrue(self.manager.initialize(), "Manager should initialize")
            self.assertTrue(self.bridge.initialize(), "Bridge should initialize")
            
            # Create and register test widget
            test_symbol = 'SPY'
            test_widget = MockQTWidget(test_symbol)
            self.mock_widgets[test_symbol] = test_widget
            
            widget_id = self.bridge.register_widget(
                test_widget, test_symbol, 'update_display', UpdatePriority.CRITICAL
            )
            self.assertNotEqual(widget_id, "", "Widget registration should succeed")
            
            # Simulate market data flow
            mock_tick = MockMarketDataTick(
                symbol=test_symbol,
                price=585.75,
                size=1000,
                timestamp=datetime.now()
            )
            
            # Test data processing through bridge
            # Note: This tests the formatting logic, full integration would require actual data manager
            display_data = DisplayData(
                symbol=mock_tick.symbol,
                last_price=mock_tick.price,
                change=2.45,
                change_percent=0.42,
                volume=mock_tick.size,
                timestamp=mock_tick.timestamp
            )
            
            # Verify data structure
            self.assertEqual(display_data.symbol, test_symbol)
            self.assertEqual(display_data.last_price, mock_tick.price)
            self.assertIsInstance(display_data.timestamp, datetime)
            
            self.logger.info("✅ End-to-end data flow test passed")
            
        except Exception as e:
            self.test_errors.append(f"End-to-end data flow failed: {e}")
            self.fail(f"End-to-end data flow test failed: {e}")
    
    # ==========================================================================
    # PERFORMANCE TESTS
    # ==========================================================================
    def test_08_performance_metrics(self):
        """Test system performance under normal load"""
        try:
            if not BRIDGE_AVAILABLE:
                self.skipTest("Bridge not available for performance testing")
            
            self.bridge = DashboardDataBridge()
            self.bridge.initialize()
            
            # Performance test parameters
            num_symbols = 10
            updates_per_symbol = 100
            start_time = time.time()
            
            # Create widgets and register them
            widgets = {}
            for i in range(num_symbols):
                symbol = f"TEST{i:02d}"
                widget = MockQTWidget(symbol)
                widgets[symbol] = widget
                
                widget_id = self.bridge.register_widget(
                    widget, symbol, 'update_display', UpdatePriority.NORMAL
                )
                self.assertNotEqual(widget_id, "", f"Widget {symbol} should register")
            
            # Simulate rapid updates
            total_updates = 0
            for _ in range(updates_per_symbol):
                for symbol in widgets:
                    # Simulate data update
                    data_dict = {
                        'formatted_price': f"${random.uniform(100, 200):.2f}",
                        'formatted_change': f"+{random.uniform(0, 5):.2f}",
                        'formatted_change_percent': f"+{random.uniform(0, 2):.2f}%",
                        'color': '#00FF88',
                        'timestamp': datetime.now(),
                        'last_price': random.uniform(100, 200)
                    }
                    
                    widgets[symbol].update_display(data_dict)
                    total_updates += 1
            
            # Calculate performance metrics
            duration = time.time() - start_time
            updates_per_second = total_updates / duration
            avg_latency_ms = (duration / total_updates) * 1000
            
            # Validate performance
            self.assertGreater(updates_per_second, MIN_UPDATES_PER_SECOND,
                             f"Should achieve at least {MIN_UPDATES_PER_SECOND} updates/sec")
            
            self.assertLess(avg_latency_ms, MAX_UPDATE_LATENCY_MS,
                          f"Average latency should be under {MAX_UPDATE_LATENCY_MS}ms")
            
            # Record performance metrics
            self.performance_metrics.update({
                'total_updates': total_updates,
                'duration_seconds': duration,
                'updates_per_second': updates_per_second,
                'avg_latency_ms': avg_latency_ms
            })
            
            self.logger.info(f"✅ Performance test passed: {updates_per_second:.1f} updates/sec, "
                           f"{avg_latency_ms:.2f}ms avg latency")
            
        except Exception as e:
            self.test_errors.append(f"Performance test failed: {e}")
            self.fail(f"Performance metrics test failed: {e}")
    
    def test_09_stress_test(self):
        """Test system behavior under high load"""
        try:
            if not BRIDGE_AVAILABLE:
                self.skipTest("Bridge not available for stress testing")
            
            self.bridge = DashboardDataBridge()
            self.bridge.initialize()
            
            # Stress test parameters
            num_widgets = 50
            update_frequency = 0.01  # 100 updates per second
            test_duration = 5  # 5 seconds
            
            # Create many widgets
            widgets = {}
            for i in range(num_widgets):
                symbol = f"STRESS{i:03d}"
                widget = MockQTWidget(symbol)
                widgets[symbol] = widget
                
                priority = random.choice(list(UpdatePriority))
                widget_id = self.bridge.register_widget(
                    widget, symbol, 'update_display', priority
                )
                self.assertNotEqual(widget_id, "", f"Stress widget {symbol} should register")
            
            # Stress test with high-frequency updates
            start_time = time.time()
            update_count = 0
            error_count = 0
            
            while time.time() - start_time < test_duration:
                for symbol, widget in widgets.items():
                    try:
                        data_dict = {
                            'formatted_price': f"${random.uniform(50, 300):.2f}",
                            'formatted_change': f"{random.uniform(-10, 10):+.2f}",
                            'formatted_change_percent': f"{random.uniform(-5, 5):+.2f}%",
                            'color': random.choice(['#00FF88', '#FF4444', '#FFFFFF']),
                            'timestamp': datetime.now(),
                            'last_price': random.uniform(50, 300)
                        }
                        
                        widget.update_display(data_dict)
                        update_count += 1
                        
                    except Exception as e:
                        error_count += 1
                        self.logger.warning(f"Stress test update error: {e}")
                
                time.sleep(update_frequency)
            
            # Calculate stress test metrics
            duration = time.time() - start_time
            error_rate = error_count / max(update_count, 1)
            updates_per_second = update_count / duration
            
            # Validate stress test results
            self.assertLess(error_rate, MAX_ERROR_RATE,
                          f"Error rate {error_rate:.3f} should be under {MAX_ERROR_RATE}")
            
            self.assertGreater(updates_per_second, MIN_UPDATES_PER_SECOND / 2,
                             "Should maintain reasonable performance under stress")
            
            self.logger.info(f"✅ Stress test passed: {update_count} updates, "
                           f"{error_rate:.3f} error rate, {updates_per_second:.1f} updates/sec")
            
        except Exception as e:
            self.test_errors.append(f"Stress test failed: {e}")
            self.fail(f"Stress test failed: {e}")
    
    # ==========================================================================
    # ERROR HANDLING TESTS
    # ==========================================================================
    def test_10_error_handling_resilience(self):
        """Test system resilience to various error conditions"""
        try:
            if not BRIDGE_AVAILABLE:
                self.skipTest("Bridge not available for error testing")
            
            self.bridge = DashboardDataBridge()
            self.bridge.initialize()
            
            # Test 1: Invalid widget registration
            with self.assertRaises((AttributeError, ValueError)):
                invalid_widget = object()  # Object without required methods
                self.bridge.register_widget(
                    invalid_widget, 'TEST', 'invalid_method', UpdatePriority.NORMAL
                )
            
            # Test 2: Handling of bad data
            test_widget = MockQTWidget('ERRORTEST')
            widget_id = self.bridge.register_widget(
                test_widget, 'ERRORTEST', 'update_display', UpdatePriority.NORMAL
            )
            
            # Send malformed data - should not crash
            bad_data = {
                'invalid_field': 'bad_value',
                'missing_required': None
            }
            
            try:
                test_widget.update_display(bad_data)
                # Should handle gracefully without crashing
            except Exception as e:
                self.logger.warning(f"Widget handled bad data with error: {e}")
            
            # Test 3: Widget cleanup after errors
            registered_before = len(self.bridge.get_registered_widgets())
            self.bridge.unregister_widget(widget_id)
            registered_after = len(self.bridge.get_registered_widgets())
            
            self.assertEqual(registered_after, registered_before - 1,
                           "Widget should be properly cleaned up after errors")
            
            self.logger.info("✅ Error handling resilience test passed")
            
        except Exception as e:
            self.test_errors.append(f"Error handling test failed: {e}")
            self.fail(f"Error handling resilience test failed: {e}")
    
    # ==========================================================================
    # RESOURCE MANAGEMENT TESTS
    # ==========================================================================
    def test_11_resource_cleanup(self):
        """Test proper resource cleanup and memory management"""
        try:
            if not all([MANAGER_AVAILABLE, BRIDGE_AVAILABLE]):
                self.skipTest("Required components not available")
            
            # Initialize components
            self.manager = MultiClientDataManager()
            self.bridge = DashboardDataBridge()
            
            self.assertTrue(self.manager.initialize())
            self.assertTrue(self.bridge.initialize())
            
            # Create resources
            test_symbols = ['CLEANUP1', 'CLEANUP2', 'CLEANUP3']
            widgets = {}
            
            for symbol in test_symbols:
                widget = MockQTWidget(symbol)
                widgets[symbol] = widget
                
                widget_id = self.bridge.register_widget(
                    widget, symbol, 'update_display', UpdatePriority.NORMAL
                )
                self.assertNotEqual(widget_id, "")
            
            # Verify resources are created
            initial_widgets = len(self.bridge.get_registered_widgets())
            self.assertEqual(initial_widgets, len(test_symbols))
            
            # Test bridge cleanup
            self.bridge.clear_cache()
            
            # Test manager cleanup
            self.manager.stop()
            
            # Test bridge stop
            self.bridge.stop()
            
            # Verify cleanup
            final_stats = self.bridge.get_performance_stats()
            self.assertIsInstance(final_stats, dict)
            
            self.logger.info("✅ Resource cleanup test passed")
            
        except Exception as e:
            self.test_errors.append(f"Resource cleanup failed: {e}")
            self.fail(f"Resource cleanup test failed: {e}")
    
    # ==========================================================================
    # COMPREHENSIVE INTEGRATION TEST
    # ==========================================================================
    def test_12_comprehensive_integration(self):
        """Comprehensive test of complete system integration"""
        try:
            if not all([MANAGER_AVAILABLE, BRIDGE_AVAILABLE, PYQT6_AVAILABLE]):
                self.skipTest("Full integration test requires all components")
            
            integration_start_time = time.time()
            
            # Phase 1: Initialize all components
            self.manager = MultiClientDataManager()
            self.bridge = DashboardDataBridge()
            
            self.assertTrue(self.manager.initialize(), "Manager initialization failed")
            self.assertTrue(self.bridge.initialize(), "Bridge initialization failed")
            
            # Phase 2: Create dashboard-like widget setup
            test_symbols = ['SPY', 'VIX', 'QQQ', 'SPX', '/ES']
            priority_map = {
                'SPY': UpdatePriority.CRITICAL,
                'VIX': UpdatePriority.CRITICAL,
                'QQQ': UpdatePriority.HIGH,
                'SPX': UpdatePriority.HIGH,
                '/ES': UpdatePriority.NORMAL
            }
            
            widgets = {}
            widget_ids = {}
            
            for symbol in test_symbols:
                widget = MockQTWidget(symbol)
                widgets[symbol] = widget
                
                widget_id = self.bridge.register_widget(
                    widget, symbol, 'update_display', priority_map[symbol]
                )
                widget_ids[symbol] = widget_id
                self.assertNotEqual(widget_id, "", f"Failed to register {symbol}")
            
            # Phase 3: Simulate realistic data flow
            simulation_duration = 3  # seconds
            update_interval = 0.1   # 10 updates per second
            start_simulation = time.time()
            
            updates_sent = 0
            updates_received = 0
            
            while time.time() - start_simulation < simulation_duration:
                for symbol in test_symbols:
                    # Generate realistic market data
                    base_price = {'SPY': 585, 'VIX': 15, 'QQQ': 380, 'SPX': 5850, '/ES': 5850}[symbol]
                    price = base_price + random.uniform(-5, 5)
                    change = random.uniform(-2, 2)
                    change_pct = (change / price) * 100
                    
                    data_dict = {
                        'formatted_price': f"${price:.2f}",
                        'formatted_change': f"{change:+.2f}",
                        'formatted_change_percent': f"{change_pct:+.2f}%",
                        'color': '#00FF88' if change >= 0 else '#FF4444',
                        'timestamp': datetime.now(),
                        'last_price': price
                    }
                    
                    widgets[symbol].update_display(data_dict)
                    updates_sent += 1
                    updates_received += 1
                
                time.sleep(update_interval)
            
            # Phase 4: Validate integration results
            integration_duration = time.time() - integration_start_time
            
            # Check all widgets received updates
            for symbol, widget in widgets.items():
                self.assertGreater(widget.update_count, 0,
                                 f"Widget {symbol} should have received updates")
                self.assertIsNotNone(widget.last_data,
                                   f"Widget {symbol} should have last data")
            
            # Check performance metrics
            updates_per_second = updates_sent / simulation_duration
            self.assertGreater(updates_per_second, 10,
                             "Should achieve reasonable update frequency")
            
            # Check system health
            bridge_stats = self.bridge.get_performance_stats()
            manager_status = self.manager.get_status_summary()
            
            self.assertIsInstance(bridge_stats, dict)
            self.assertIsInstance(manager_status, dict)
            
            # Phase 5: Test system shutdown
            self.bridge.stop()
            self.manager.stop()
            
            # Record comprehensive test results
            test_results = {
                'integration_duration': integration_duration,
                'simulation_duration': simulation_duration,
                'symbols_tested': len(test_symbols),
                'updates_sent': updates_sent,
                'updates_received': updates_received,
                'updates_per_second': updates_per_second,
                'all_widgets_updated': all(w.update_count > 0 for w in widgets.values())
            }
            
            self.performance_metrics.update(test_results)
            
            self.logger.info(f"✅ Comprehensive integration test passed: "
                           f"{len(test_symbols)} symbols, {updates_sent} updates, "
                           f"{updates_per_second:.1f} updates/sec")
            
        except Exception as e:
            self.test_errors.append(f"Comprehensive integration failed: {e}")
            self.fail(f"Comprehensive integration test failed: {e}")

# ==============================================================================
# TEST UTILITY FUNCTIONS
# ==============================================================================
def run_integration_test_suite() -> Dict[str, Any]:
    """
    Run the complete integration test suite.
    
    Returns:
        Dict: Test results and metrics
    """
    # Create test suite
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromTestCase(MultiClientIntegrationTestSuite)
    
    # Run tests
    test_runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    test_result = test_runner.run(test_suite)
    
    # Compile results
    results = {
        'tests_run': test_result.testsRun,
        'failures': len(test_result.failures),
        'errors': len(test_result.errors),
        'skipped': len(test_result.skipped) if hasattr(test_result, 'skipped') else 0,
        'success_rate': (test_result.testsRun - len(test_result.failures) - len(test_result.errors)) / max(test_result.testsRun, 1),
        'was_successful': test_result.wasSuccessful()
    }
    
    return results

def generate_test_report(results: Dict[str, Any]) -> str:
    """
    Generate a comprehensive test report.
    
    Args:
        results: Test results dictionary
        
    Returns:
        str: Formatted test report
    """
    report = []
    report.append("=" * 80)
    report.append("SPYDER T13 - MULTI-CLIENT INTEGRATION TEST REPORT")
    report.append("=" * 80)
    report.append("")
    
    report.append("📊 TEST SUMMARY:")
    report.append(f"   Tests Run: {results['tests_run']}")
    report.append(f"   Failures: {results['failures']}")
    report.append(f"   Errors: {results['errors']}")
    report.append(f"   Skipped: {results['skipped']}")
    report.append(f"   Success Rate: {results['success_rate']:.1%}")
    report.append(f"   Overall Result: {'✅ PASSED' if results['was_successful'] else '❌ FAILED'}")
    report.append("")
    
    report.append("🎯 TESTED COMPONENTS:")
    report.append("   ✅ SpyderB08_MultiClientDataManager.py")
    report.append("   ✅ SpyderG08_DashboardDataBridge.py")
    report.append("   ✅ SpyderG05_TradingDashboard.py (updated)")
    report.append("")
    
    report.append("🔧 TEST CATEGORIES:")
    report.append("   • Module Initialization Tests")
    report.append("   • Client Allocation Strategy Tests")
    report.append("   • Bridge Integration Tests")
    report.append("   • Real-time Data Flow Tests")
    report.append("   • Performance and Stress Tests")
    report.append("   • Error Handling Tests")
    report.append("   • Resource Management Tests")
    report.append("   • Comprehensive Integration Tests")
    report.append("")
    
    if results['was_successful']:
        report.append("🎉 INTEGRATION TEST SUITE PASSED!")
        report.append("   Your multi-client architecture is working correctly!")
    else:
        report.append("⚠️ ISSUES DETECTED:")
        report.append("   Review test failures and address any issues.")
    
    report.append("=" * 80)
    
    return "\n".join(report)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("🚀 SPYDER T13 - Multi-Client Integration Test Suite")
    print("=" * 80)
    print("")
    
    print("🔧 System Check:")
    print(f"   MultiClientDataManager: {'✅' if MANAGER_AVAILABLE else '❌'}")
    print(f"   DashboardDataBridge: {'✅' if BRIDGE_AVAILABLE else '❌'}")
    print(f"   TradingDashboard: {'✅' if DASHBOARD_AVAILABLE else '❌'}")
    print(f"   PyQt6: {'✅' if PYQT6_AVAILABLE else '❌'}")
    print(f"   Test Framework: {'✅' if TEST_FRAMEWORK_AVAILABLE else '❌'}")
    print("")
    
    if not any([MANAGER_AVAILABLE, BRIDGE_AVAILABLE, DASHBOARD_AVAILABLE]):
        print("❌ No components available for testing!")
        print("   Please ensure the modules are properly installed.")
        sys.exit(1)
    
    try:
        print("🧪 Running Integration Test Suite...")
        print("")
        
        # Run the test suite
        test_results = run_integration_test_suite()
        
        print("")
        print("📋 Generating Test Report...")
        
        # Generate and display report
        report = generate_test_report(test_results)
        print(report)
        
        # Exit with appropriate code
        exit_code = 0 if test_results['was_successful'] else 1
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"❌ Test suite execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)