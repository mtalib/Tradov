#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Comprehensive Broker to Dashboard Integration Test

Test Name: test_comprehensive_broker_dashboard_flow.py
Purpose: End-to-end testing of data flow from broker system to trading dashboard
Author: Mohamed Talib  
Date Created: 2025-09-11
Last Updated: 2025-09-11 Time: 17:30:00

Description:
    Comprehensive test suite that validates the complete data flow from the
    SpyderB_Broker system through to the SpyderG_GUI trading dashboard.
    Tests all components in isolation and then validates end-to-end integration.

Test Coverage:
    1. Broker System Component Tests (B00-B28)
    2. Metrics Collection and Export Tests (B15)
    3. Multi-Client Health Monitoring Tests (B14)
    4. Gateway Configuration Tests (B13)
    5. Dashboard Integration Tests (G05, G07)
    6. Data Flow Validation Tests
    7. Real-time Updates and Performance Tests
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import os
import sys
import time
import threading
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import subprocess
import socket
import signal

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    print("WARNING: psutil not available - limited system monitoring")
    HAS_PSUTIL = False

try:
    from PyQt6.QtWidgets import QApplication, QWidget
    from PyQt6.QtCore import QTimer, QThread, pyqtSignal
    HAS_PYQT6 = True
except ImportError:
    print("WARNING: PyQt6 not available - GUI tests will be skipped")
    HAS_PYQT6 = False

# ==============================================================================
# PROJECT IMPORTS SETUP
# ==============================================================================
# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================
class TestConfig:
    """Test configuration and settings."""
    
    # Test timeouts
    COMPONENT_TEST_TIMEOUT = 30  # seconds
    INTEGRATION_TEST_TIMEOUT = 120  # seconds
    DASHBOARD_STARTUP_TIMEOUT = 60  # seconds
    
    # Data flow test settings
    TEST_DATA_POINTS = 100
    UPDATE_FREQUENCY = 1.0  # seconds
    METRICS_PORT = 9090
    
    # Mock data settings
    MOCK_PORTFOLIO_VALUE = 100000.0
    MOCK_DAILY_PNL = 2500.0
    MOCK_POSITIONS = 15
    MOCK_CLIENT_COUNT = 10
    
    # Validation thresholds
    MIN_SUCCESS_RATE = 0.8  # 80% success rate required
    MAX_LATENCY_MS = 100
    MAX_MEMORY_USAGE_MB = 2048

# ==============================================================================
# TEST RESULT TRACKING
# ==============================================================================
class TestResult:
    """Test result tracking."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.start_time = datetime.now()
        self.end_time = None
        self.success = False
        self.error_message = None
        self.details = {}
        self.metrics = {}
    
    def complete(self, success: bool, error_message: Optional[str] = None, **kwargs):
        """Mark test as complete."""
        self.end_time = datetime.now()
        self.success = success
        self.error_message = error_message
        self.details.update(kwargs)
    
    @property
    def duration(self) -> float:
        """Get test duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def __str__(self) -> str:
        status = "PASS" if self.success else "FAIL"
        return f"{self.test_name}: {status} ({self.duration:.2f}s)"

# ==============================================================================
# COMPREHENSIVE TEST SUITE
# ==============================================================================
class ComprehensiveBrokerDashboardTest:
    """
    Comprehensive test suite for broker to dashboard integration.
    """
    
    def __init__(self):
        """Initialize test suite."""
        self.logger = self._setup_logging()
        self.config = TestConfig()
        self.results: List[TestResult] = []
        self.components_available = {}
        self.test_data = {}
        
        # GUI components
        self.app = None
        self.dashboard = None
        
        self.logger.info("Comprehensive Broker Dashboard Test Suite Initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup comprehensive logging."""
        logger = logging.getLogger("BrokerDashboardTest")
        logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        log_file = Path("broker_dashboard_test.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    # ==========================================================================
    # COMPONENT AVAILABILITY TESTS
    # ==========================================================================
    
    def test_broker_components_availability(self) -> TestResult:
        """Test availability of all broker components."""
        result = TestResult("Broker Components Availability")
        
        try:
            # Test core broker modules
            broker_modules = [
                "SpyderB_Broker.SpyderB00_OrderTypes",
                "SpyderB_Broker.SpyderB01_SpyderClient", 
                "SpyderB_Broker.SpyderB02_OrderManager",
                "SpyderB_Broker.SpyderB03_PositionTracker",
                "SpyderB_Broker.SpyderB04_AccountManager",
                "SpyderB_Broker.SpyderB05_ConnectionManager",
                "SpyderB_Broker.SpyderB06_ContractBuilder",
                "SpyderB_Broker.SpyderB07_MarketDataManager",
                "SpyderB_Broker.SpyderB08_MultiClientDataManager",
                "SpyderB_Broker.SpyderB10_IBDataTypes",
                "SpyderB_Broker.SpyderB11_AsyncIOBridge",
                "SpyderB_Broker.SpyderB12_GatewayAutomation",
                "SpyderB_Broker.SpyderB13_GatewayConfig",
                "SpyderB_Broker.SpyderB14_MultiClientWatchdog",
                "SpyderB_Broker.SpyderB15_PrometheusMetrics",
                "SpyderB_Broker.SpyderB16_GatewayIntegration",
            ]
            
            available_modules = []
            failed_modules = []
            
            for module_name in broker_modules:
                try:
                    __import__(module_name)
                    available_modules.append(module_name)
                    self.components_available[module_name] = True
                    self.logger.info(f"✅ {module_name} - Available")
                except ImportError as e:
                    failed_modules.append((module_name, str(e)))
                    self.components_available[module_name] = False
                    self.logger.warning(f"❌ {module_name} - Failed: {e}")
            
            # Test package import
            try:
                import SpyderB_Broker
                package_available = True
                self.logger.info("✅ SpyderB_Broker package - Available")
            except ImportError as e:
                package_available = False
                self.logger.error(f"❌ SpyderB_Broker package - Failed: {e}")
            
            success_rate = len(available_modules) / len(broker_modules)
            
            result.complete(
                success=success_rate >= self.config.MIN_SUCCESS_RATE and package_available,
                available_modules=len(available_modules),
                total_modules=len(broker_modules),
                success_rate=success_rate,
                failed_modules=failed_modules,
                package_available=package_available
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Broker component test failed: {e}")
        
        return result
    
    def test_dashboard_components_availability(self) -> TestResult:
        """Test availability of dashboard components."""
        result = TestResult("Dashboard Components Availability")
        
        try:
            dashboard_modules = [
                "SpyderG_GUI.SpyderG05_TradingDashboard",
                "SpyderG_GUI.SpyderG07_PrometheusMetricsDisplay",
            ]
            
            available_modules = []
            failed_modules = []
            
            for module_name in dashboard_modules:
                try:
                    __import__(module_name)
                    available_modules.append(module_name)
                    self.components_available[module_name] = True
                    self.logger.info(f"✅ {module_name} - Available")
                except ImportError as e:
                    failed_modules.append((module_name, str(e)))
                    self.components_available[module_name] = False
                    self.logger.warning(f"❌ {module_name} - Failed: {e}")
            
            success_rate = len(available_modules) / len(dashboard_modules)
            
            result.complete(
                success=success_rate >= self.config.MIN_SUCCESS_RATE and HAS_PYQT6,
                available_modules=len(available_modules),
                total_modules=len(dashboard_modules),
                success_rate=success_rate,
                failed_modules=failed_modules,
                pyqt6_available=HAS_PYQT6
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Dashboard component test failed: {e}")
        
        return result
    
    # ==========================================================================
    # CORE FUNCTIONALITY TESTS
    # ==========================================================================
    
    def test_order_types_functionality(self) -> TestResult:
        """Test SpyderB00_OrderTypes functionality."""
        result = TestResult("Order Types Functionality")
        
        try:
            from SpyderB_Broker.SpyderB00_OrderTypes import (
                OrderAction, OrderType, OrderRequest, ContractDetails,
                SecType, OptionRight, create_market_order, create_spy_option_contract
            )
            
            # Test enum creation
            action = OrderAction.BUY
            order_type = OrderType.MARKET
            
            # Test contract creation
            spy_contract = ContractDetails(
                symbol="SPY",
                sec_type=SecType.STOCK,
                exchange="SMART",
                currency="USD"
            )
            
            # Test option contract
            spy_option = create_spy_option_contract("20250321", 580.0, OptionRight.CALL)
            
            # Test order creation
            market_order = create_market_order(spy_contract, OrderAction.BUY, 100)
            
            # Validate order
            validation_passed = market_order.total_quantity == 100
            validation_passed &= market_order.action == OrderAction.BUY
            validation_passed &= market_order.order_type == OrderType.MARKET
            
            result.complete(
                success=validation_passed,
                contract_created=True,
                option_contract_created=True,
                order_created=True,
                validation_passed=validation_passed
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Order types test failed: {e}")
        
        return result
    
    def test_gateway_config_functionality(self) -> TestResult:
        """Test SpyderB13_GatewayConfig functionality."""
        result = TestResult("Gateway Config Functionality")
        
        try:
            from SpyderB_Broker.SpyderB13_GatewayConfig import (
                GatewayConfig, GatewayManager, get_default_config,
                get_client_allocation, ClientPurpose, TradingMode
            )
            
            # Test default config creation
            config = get_default_config()
            
            # Test client allocation
            clients = get_client_allocation()
            
            # Validate client allocation
            client_count = len(clients)
            has_critical_clients = any(
                client.priority == "CRITICAL" for client in clients.values()
            )
            
            # Test gateway manager
            manager = GatewayManager(config)
            
            # Test client validation
            connected_clients = [1, 2, 3, 5, 7, 9, 10]
            validation_results = manager.validate_client_connections(connected_clients)
            
            result.complete(
                success=client_count == 10 and has_critical_clients,
                client_count=client_count,
                has_critical_clients=has_critical_clients,
                config_created=True,
                manager_created=True,
                validation_health=validation_results.get('health_percentage', 0)
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Gateway config test failed: {e}")
        
        return result
    
    def test_multi_client_watchdog_functionality(self) -> TestResult:
        """Test SpyderB14_MultiClientWatchdog functionality."""
        result = TestResult("Multi-Client Watchdog Functionality")
        
        try:
            from SpyderB_Broker.SpyderB14_MultiClientWatchdog import (
                MultiClientWatchdog, SystemHealth, ClientHealth,
                HealthStatus, create_watchdog
            )
            
            # Test watchdog creation
            watchdog = create_watchdog()
            
            # Test system health
            system_health = watchdog.get_system_health()
            
            # Test client health retrieval
            client_health = watchdog.get_client_health(1)
            
            # Test status summary
            status_summary = watchdog.get_status_summary()
            
            # Validate SystemHealth class (critical for imports)
            system_health_score = system_health.get_health_score()
            component_status = system_health.get_component_status()
            
            result.complete(
                success=True,
                watchdog_created=True,
                system_health_available=system_health is not None,
                client_health_available=client_health is not None,
                health_score=system_health_score,
                component_count=len(component_status)
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Multi-client watchdog test failed: {e}")
        
        return result
    
    def test_prometheus_metrics_functionality(self) -> TestResult:
        """Test SpyderB15_PrometheusMetrics functionality."""
        result = TestResult("Prometheus Metrics Functionality")
        
        try:
            from SpyderB_Broker.SpyderB15_PrometheusMetrics import (
                PrometheusMetricsCollector, TradingMetrics, MetricsConfig,
                TradeMetrics, TradeStatus, create_metrics_collector
            )
            
            # Test metrics collector creation
            collector = create_metrics_collector()
            
            # Test trading metrics
            trading_metrics = collector.get_trading_metrics()
            
            # Test sample trade recording
            sample_trade = TradeMetrics(
                trade_id="TEST_001",
                symbol="SPY",
                strategy="test_strategy",
                entry_time=datetime.now(),
                quantity=10,
                entry_price=580.0,
                realized_pnl=100.0,
                status=TradeStatus.EXECUTED
            )
            
            trading_metrics.record_trade(sample_trade)
            
            # Test performance summary
            performance_summary = trading_metrics.get_performance_summary()
            
            # Test metrics snapshot
            snapshot = trading_metrics.get_current_snapshot()
            
            result.complete(
                success=True,
                collector_created=True,
                trading_metrics_available=trading_metrics is not None,
                trade_recorded=True,
                performance_summary_generated=True,
                total_value=performance_summary.get('total_value', 0),
                total_trades=performance_summary.get('total_trades', 0)
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Prometheus metrics test failed: {e}")
        
        return result
    
    # ==========================================================================
    # INTEGRATION TESTS
    # ==========================================================================
    
    def test_broker_package_integration(self) -> TestResult:
        """Test complete broker package integration."""
        result = TestResult("Broker Package Integration")
        
        try:
            # Test complete package import
            import SpyderB_Broker
            
            # Test critical exports
            from SpyderB_Broker import (
                OrderAction, OrderRequest, GatewayConfig, SystemHealth,
                MultiClientWatchdog, PrometheusMetricsCollector, TradingMetrics
            )
            
            # Test integrated functionality
            config = GatewayConfig()
            watchdog = MultiClientWatchdog()
            system_health = watchdog.get_system_health()
            
            # Test metrics integration
            metrics_collector = PrometheusMetricsCollector()
            trading_metrics = metrics_collector.get_trading_metrics()
            
            result.complete(
                success=True,
                package_imported=True,
                critical_exports_available=True,
                integration_functional=True
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Broker package integration test failed: {e}")
        
        return result
    
    def test_metrics_dashboard_integration(self) -> TestResult:
        """Test metrics to dashboard integration."""
        result = TestResult("Metrics Dashboard Integration")
        
        try:
            if not HAS_PYQT6:
                result.complete(False, "PyQt6 not available")
                return result
            
            # Initialize QApplication if needed
            if not QApplication.instance():
                self.app = QApplication([])
            
            # Test metrics collector
            from SpyderB_Broker.SpyderB15_PrometheusMetrics import PrometheusMetricsCollector
            metrics_collector = PrometheusMetricsCollector()
            
            # Generate test data
            self._generate_test_metrics_data(metrics_collector)
            
            # Test dashboard widget
            from SpyderG_GUI.SpyderG07_PrometheusMetricsDisplay import PrometheusMetricsDisplay
            
            # Create dashboard widget
            dashboard_widget = PrometheusMetricsDisplay()
            
            # Test data update
            dashboard_widget.show()
            
            # Process events
            if self.app:
                self.app.processEvents()
            
            result.complete(
                success=True,
                metrics_collector_created=True,
                dashboard_widget_created=True,
                data_integration_tested=True
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Metrics dashboard integration test failed: {e}")
        
        return result
    
    def test_full_dashboard_integration(self) -> TestResult:
        """Test full trading dashboard integration."""
        result = TestResult("Full Dashboard Integration")
        
        try:
            if not HAS_PYQT6:
                result.complete(False, "PyQt6 not available")
                return result
            
            # Initialize QApplication if needed
            if not QApplication.instance():
                self.app = QApplication([])
            
            # Test full dashboard
            from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
            
            # Create dashboard
            self.dashboard = SpyderTradingDashboard()
            
            # Test dashboard initialization
            self.dashboard.show()
            
            # Process events
            if self.app:
                self.app.processEvents()
            
            # Test dashboard components
            dashboard_components = {
                'metrics_display': hasattr(self.dashboard, 'prometheus_widget'),
                'signal_monitor': hasattr(self.dashboard, 'signal_monitor'),
                'portfolio_display': hasattr(self.dashboard, 'portfolio_display'),
            }
            
            result.complete(
                success=True,
                dashboard_created=True,
                dashboard_shown=True,
                components_available=dashboard_components
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Full dashboard integration test failed: {e}")
        
        return result
    
    # ==========================================================================
    # DATA FLOW TESTS
    # ==========================================================================
    
    def test_real_time_data_flow(self) -> TestResult:
        """Test real-time data flow from broker to dashboard."""
        result = TestResult("Real-Time Data Flow")
        
        try:
            # Create broker components
            from SpyderB_Broker.SpyderB15_PrometheusMetrics import PrometheusMetricsCollector
            from SpyderB_Broker.SpyderB14_MultiClientWatchdog import MultiClientWatchdog
            
            metrics_collector = PrometheusMetricsCollector()
            watchdog = MultiClientWatchdog()
            
            # Generate real-time test data
            data_points_generated = 0
            update_successful = True
            
            for i in range(10):  # Test 10 data points
                try:
                    # Update metrics
                    self._update_test_metrics(metrics_collector, i)
                    
                    # Update watchdog
                    system_health = watchdog.get_system_health()
                    
                    data_points_generated += 1
                    time.sleep(0.1)  # Brief pause
                    
                except Exception as e:
                    update_successful = False
                    self.logger.warning(f"Data update {i} failed: {e}")
            
            # Test data retrieval
            performance_summary = metrics_collector.get_trading_metrics().get_performance_summary()
            status_summary = watchdog.get_status_summary()
            
            result.complete(
                success=update_successful and data_points_generated >= 8,
                data_points_generated=data_points_generated,
                update_successful=update_successful,
                performance_data_available=bool(performance_summary),
                status_data_available=bool(status_summary)
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Real-time data flow test failed: {e}")
        
        return result
    
    def test_metrics_export_functionality(self) -> TestResult:
        """Test Prometheus metrics export functionality."""
        result = TestResult("Metrics Export Functionality")
        
        try:
            from SpyderB_Broker.SpyderB15_PrometheusMetrics import PrometheusMetricsCollector
            
            # Create collector
            metrics_collector = PrometheusMetricsCollector()
            
            # Generate test data
            self._generate_test_metrics_data(metrics_collector)
            
            # Test if metrics would be exportable (don't actually start server)
            try:
                # Test configuration
                config = metrics_collector.config
                export_ready = config.port == self.config.METRICS_PORT
                
                # Test trading metrics
                trading_metrics = metrics_collector.get_trading_metrics()
                snapshot = trading_metrics.get_current_snapshot()
                
                result.complete(
                    success=export_ready,
                    config_valid=True,
                    port_configured=config.port,
                    snapshot_available=snapshot is not None,
                    portfolio_value=snapshot.portfolio.total_value if snapshot else 0
                )
                
            except Exception as e:
                result.complete(False, f"Metrics export test failed: {e}")
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"Metrics export test failed: {e}")
        
        return result
    
    # ==========================================================================
    # PERFORMANCE TESTS
    # ==========================================================================
    
    def test_system_performance(self) -> TestResult:
        """Test system performance under load."""
        result = TestResult("System Performance")
        
        try:
            if not HAS_PSUTIL:
                result.complete(False, "psutil not available for performance testing")
                return result
            
            # Measure initial system state
            initial_memory = psutil.virtual_memory().percent
            initial_cpu = psutil.cpu_percent(interval=1)
            
            # Run performance test
            start_time = time.time()
            
            # Create multiple broker components
            from SpyderB_Broker.SpyderB15_PrometheusMetrics import PrometheusMetricsCollector
            from SpyderB_Broker.SpyderB14_MultiClientWatchdog import MultiClientWatchdog
            
            collectors = [PrometheusMetricsCollector() for _ in range(3)]
            watchdogs = [MultiClientWatchdog() for _ in range(3)]
            
            # Generate load
            for i in range(50):
                for collector in collectors:
                    self._update_test_metrics(collector, i)
                
                for watchdog in watchdogs:
                    watchdog.get_system_health()
            
            end_time = time.time()
            
            # Measure final system state
            final_memory = psutil.virtual_memory().percent
            final_cpu = psutil.cpu_percent(interval=1)
            
            # Calculate performance metrics
            duration = end_time - start_time
            memory_increase = final_memory - initial_memory
            cpu_avg = (initial_cpu + final_cpu) / 2
            
            performance_acceptable = (
                duration < 30 and  # Should complete in under 30 seconds
                memory_increase < 10 and  # Memory increase should be minimal
                cpu_avg < 80  # CPU usage should be reasonable
            )
            
            result.complete(
                success=performance_acceptable,
                duration=duration,
                initial_memory=initial_memory,
                final_memory=final_memory,
                memory_increase=memory_increase,
                cpu_average=cpu_avg,
                components_created=len(collectors) + len(watchdogs)
            )
            
        except Exception as e:
            result.complete(False, str(e))
            self.logger.error(f"System performance test failed: {e}")
        
        return result
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _generate_test_metrics_data(self, metrics_collector):
        """Generate test metrics data."""
        trading_metrics = metrics_collector.get_trading_metrics()
        
        # Update portfolio value
        trading_metrics.update_portfolio_value(
            self.config.MOCK_PORTFOLIO_VALUE,
            self.config.MOCK_PORTFOLIO_VALUE * 0.1
        )
        
        # Update daily P&L
        trading_metrics.update_daily_pnl(self.config.MOCK_DAILY_PNL)
        
        # Generate mock positions
        mock_positions = [
            {
                'symbol': 'SPY',
                'quantity': 100,
                'unrealized_pnl': 150.0,
                'delta': 50.0,
                'gamma': 0.1,
                'theta': -5.0,
                'vega': 2.0
            }
        ]
        trading_metrics.update_positions(mock_positions)
    
    def _update_test_metrics(self, metrics_collector, iteration: int):
        """Update test metrics for iteration."""
        trading_metrics = metrics_collector.get_trading_metrics()
        
        # Simulate portfolio value changes
        portfolio_value = self.config.MOCK_PORTFOLIO_VALUE + (iteration * 100)
        trading_metrics.update_portfolio_value(portfolio_value, portfolio_value * 0.1)
        
        # Simulate P&L changes
        daily_pnl = self.config.MOCK_DAILY_PNL + (iteration * 10)
        trading_metrics.update_daily_pnl(daily_pnl)
        
        # Simulate execution metrics
        trading_metrics.update_execution_metrics(
            fill_time_ms=50.0 + iteration,
            slippage_bps=2.5 + (iteration * 0.1)
        )
    
    # ==========================================================================
    # TEST EXECUTION AND REPORTING
    # ==========================================================================
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests and return comprehensive results."""
        self.logger.info("Starting Comprehensive Broker Dashboard Test Suite")
        start_time = datetime.now()
        
        # Component availability tests
        self.logger.info("Phase 1: Component Availability Tests")
        self.results.append(self.test_broker_components_availability())
        self.results.append(self.test_dashboard_components_availability())
        
        # Core functionality tests
        self.logger.info("Phase 2: Core Functionality Tests")
        self.results.append(self.test_order_types_functionality())
        self.results.append(self.test_gateway_config_functionality())
        self.results.append(self.test_multi_client_watchdog_functionality())
        self.results.append(self.test_prometheus_metrics_functionality())
        
        # Integration tests
        self.logger.info("Phase 3: Integration Tests")
        self.results.append(self.test_broker_package_integration())
        self.results.append(self.test_metrics_dashboard_integration())
        self.results.append(self.test_full_dashboard_integration())
        
        # Data flow tests
        self.logger.info("Phase 4: Data Flow Tests")
        self.results.append(self.test_real_time_data_flow())
        self.results.append(self.test_metrics_export_functionality())
        
        # Performance tests
        self.logger.info("Phase 5: Performance Tests")
        self.results.append(self.test_system_performance())
        
        end_time = datetime.now()
        
        # Generate comprehensive report
        return self._generate_test_report(start_time, end_time)
    
    def _generate_test_report(self, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Generate comprehensive test report."""
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results if result.success)
        failed_tests = total_tests - passed_tests
        success_rate = passed_tests / total_tests if total_tests > 0 else 0
        
        report = {
            'test_suite': 'Comprehensive Broker Dashboard Integration',
            'execution_time': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'duration_seconds': (end_time - start_time).total_seconds()
            },
            'summary': {
                'total_tests': total_tests,
                'passed': passed_tests,
                'failed': failed_tests,
                'success_rate': success_rate,
                'overall_status': 'PASS' if success_rate >= self.config.MIN_SUCCESS_RATE else 'FAIL'
            },
            'test_results': [
                {
                    'name': result.test_name,
                    'status': 'PASS' if result.success else 'FAIL',
                    'duration': result.duration,
                    'error': result.error_message,
                    'details': result.details
                }
                for result in self.results
            ],
            'component_availability': self.components_available,
            'recommendations': self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check for failed components
        failed_components = [
            name for name, available in self.components_available.items()
            if not available
        ]
        
        if failed_components:
            recommendations.append(
                f"Install missing components: {', '.join(failed_components)}"
            )
        
        # Check for GUI availability
        if not HAS_PYQT6:
            recommendations.append("Install PyQt6 for GUI testing: pip install PyQt6")
        
        # Check for monitoring tools
        if not HAS_PSUTIL:
            recommendations.append("Install psutil for performance monitoring: pip install psutil")
        
        # Check test results
        failed_tests = [result for result in self.results if not result.success]
        if failed_tests:
            recommendations.append(
                f"Address failed tests: {', '.join(test.test_name for test in failed_tests)}"
            )
        
        return recommendations
    
    def cleanup(self):
        """Cleanup test resources."""
        if self.dashboard:
            self.dashboard.close()
        
        if self.app:
            self.app.quit()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main test execution function."""
    print("SPYDER - Comprehensive Broker Dashboard Integration Test")
    print("=" * 70)
    
    # Create test suite
    test_suite = ComprehensiveBrokerDashboardTest()
    
    try:
        # Run all tests
        results = test_suite.run_all_tests()
        
        # Print summary report
        print("\nTEST EXECUTION SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {results['summary']['total_tests']}")
        print(f"Passed: {results['summary']['passed']}")
        print(f"Failed: {results['summary']['failed']}")
        print(f"Success Rate: {results['summary']['success_rate']:.1%}")
        print(f"Overall Status: {results['summary']['overall_status']}")
        print(f"Duration: {results['execution_time']['duration_seconds']:.2f} seconds")
        
        # Print individual test results
        print("\nINDIVIDUAL TEST RESULTS")
        print("=" * 50)
        for test_result in results['test_results']:
            status_icon = "✅" if test_result['status'] == 'PASS' else "❌"
            print(f"{status_icon} {test_result['name']}: {test_result['status']} ({test_result['duration']:.2f}s)")
            if test_result['error']:
                print(f"    Error: {test_result['error']}")
        
        # Print recommendations
        if results['recommendations']:
            print("\nRECOMMENDATIONS")
            print("=" * 50)
            for i, recommendation in enumerate(results['recommendations'], 1):
                print(f"{i}. {recommendation}")
        
        # Save detailed report
        report_file = Path("broker_dashboard_test_report.json")
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed report saved to: {report_file}")
        
        # Exit with appropriate code
        exit_code = 0 if results['summary']['overall_status'] == 'PASS' else 1
        
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        exit_code = 2
    except Exception as e:
        print(f"\nTest execution failed: {e}")
        traceback.print_exc()
        exit_code = 3
    finally:
        test_suite.cleanup()
    
    print(f"\nTest suite completed with exit code: {exit_code}")
    return exit_code

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
