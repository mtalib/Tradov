"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB22_IntegrationTestSuite.py
Purpose: Integration Test Suite for IB Gateway 10.39 Setup
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-26 Time: 10:45:00

Module Description:
    Comprehensive integration test suite for validating the complete IB Gateway
    10.39 setup including configuration, startup automation, connection stability,
    and API functionality. Provides automated testing, performance benchmarking,
    and diagnostic reporting for the Spyder trading system integration.
"""

import os
import sys
import time
import asyncio
import socket
import psutil
import json
import statistics
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
import logging
import unittest
from unittest.mock import Mock, patch
import concurrent.futures
import threading
import subprocess

# Import our Gateway modules
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import (
        GatewayConfigurationManager,
        GatewayConfig,
        get_default_config
    )
    from SpyderB20_ConnectionManager_v1039 import (
        IBConnectionManager,
        ConnectionState,
        create_connection_manager
    )
    from SpyderB21_GatewayStartupAutomation import (
        GatewayStartupAutomation,
        GatewayCredentials,
        StartupState
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Gateway modules not available: {e}")
    MODULES_AVAILABLE = False

# IB API imports
try:
    from ib_async import IB, Contract, Stock, Option, util
    IB_ASYNC_AVAILABLE = True
except ImportError:
    print("⚠️ ib_async not available")
    IB_ASYNC_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Test Configuration
TEST_CONFIG = {
    "mode": "paper",
    "port": 4002,
    "timeout": 60,
    "max_retries": 3,
    "performance_iterations": 10,
    "stress_test_connections": 5
}

# Test Categories
TEST_CATEGORIES = [
    "PREREQUISITES",
    "CONFIGURATION",
    "STARTUP",
    "CONNECTION",
    "API_FUNCTIONALITY",
    "PERFORMANCE",
    "STRESS",
    "RECOVERY"
]

# Performance Benchmarks
BENCHMARKS = {
    "startup_time": 60,          # Maximum startup time in seconds
    "connection_time": 10,        # Maximum connection time
    "api_latency": 100,          # Maximum API latency in ms
    "reconnection_time": 30,      # Maximum reconnection time
    "memory_usage": 1024,        # Maximum memory in MB
    "cpu_usage": 50              # Maximum CPU percentage
}

# ==============================================================================
# TEST RESULT DATA CLASSES
# ==============================================================================

@dataclass
class TestResult:
    """Individual test result"""
    name: str
    category: str
    status: str  # PASS, FAIL, SKIP, ERROR
    duration: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def is_passed(self) -> bool:
        return self.status == "PASS"

@dataclass
class TestSuiteResult:
    """Complete test suite results"""
    start_time: datetime
    end_time: Optional[datetime] = None
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    results: List[TestResult] = field(default_factory=list)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_summary(self):
        """Calculate test summary statistics"""
        self.total_tests = len(self.results)
        self.passed = sum(1 for r in self.results if r.status == "PASS")
        self.failed = sum(1 for r in self.results if r.status == "FAIL")
        self.skipped = sum(1 for r in self.results if r.status == "SKIP")
        self.errors = sum(1 for r in self.results if r.status == "ERROR")
    
    def get_pass_rate(self) -> float:
        """Get test pass rate percentage"""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100

# ==============================================================================
# INTEGRATION TEST SUITE CLASS
# ==============================================================================

class IntegrationTestSuite:
    """
    Comprehensive integration test suite for IB Gateway 10.39.
    
    This suite validates:
    - System prerequisites and dependencies
    - Gateway configuration correctness
    - Startup automation functionality
    - Connection stability and recovery
    - API operations and data retrieval
    - Performance benchmarks
    - Stress testing and edge cases
    
    Attributes:
        config: Test configuration
        results: Test suite results
        logger: Test logger
        gateway_automation: Gateway startup instance
        connection_manager: Connection manager instance
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize test suite.
        
        Args:
            config: Test configuration override
        """
        self.logger = self._setup_logger()
        self.config = {**TEST_CONFIG, **(config or {})}
        
        # Test results
        self.results = TestSuiteResult(start_time=datetime.now())
        
        # Component instances
        self.gateway_automation: Optional[GatewayStartupAutomation] = None
        self.connection_manager: Optional[IBConnectionManager] = None
        self.config_manager: Optional[GatewayConfigurationManager] = None
        
        self.logger.info("Integration Test Suite initialized")
    
    def _setup_logger(self) -> logging.Logger:
        """Setup test logger"""
        logger = logging.getLogger("TestSuite")
        logger.setLevel(logging.INFO)
        
        # Console handler with color support
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Custom formatter
        formatter = logging.Formatter(
            '%(asctime)s - [%(levelname)s] - %(message)s',
            datefmt='%H:%M:%S'
        )
        ch.setFormatter(formatter)
        
        if not logger.handlers:
            logger.addHandler(ch)
        
        return logger
    
    # ==========================================================================
    # TEST EXECUTION FRAMEWORK
    # ==========================================================================
    
    def run_test(self, test_func, name: str, category: str) -> TestResult:
        """
        Run individual test with timing and error handling.
        
        Args:
            test_func: Test function to execute
            name: Test name
            category: Test category
            
        Returns:
            TestResult object
        """
        start_time = time.time()
        result = TestResult(name=name, category=category, status="ERROR", duration=0)
        
        try:
            self.logger.info(f"Running: {name}")
            
            # Execute test
            test_passed, message, details = test_func()
            
            # Set result
            result.status = "PASS" if test_passed else "FAIL"
            result.message = message
            result.details = details or {}
            
            # Log result
            if test_passed:
                self.logger.info(f"  ✅ PASS: {message}")
            else:
                self.logger.error(f"  ❌ FAIL: {message}")
                
        except Exception as e:
            result.status = "ERROR"
            result.message = str(e)
            self.logger.error(f"  💥 ERROR: {e}")
        
        finally:
            result.duration = time.time() - start_time
            self.results.results.append(result)
        
        return result
    
    async def run_async_test(self, test_func, name: str, category: str) -> TestResult:
        """Run async test"""
        start_time = time.time()
        result = TestResult(name=name, category=category, status="ERROR", duration=0)
        
        try:
            self.logger.info(f"Running: {name}")
            
            # Execute async test
            test_passed, message, details = await test_func()
            
            result.status = "PASS" if test_passed else "FAIL"
            result.message = message
            result.details = details or {}
            
            if test_passed:
                self.logger.info(f"  ✅ PASS: {message}")
            else:
                self.logger.error(f"  ❌ FAIL: {message}")
                
        except Exception as e:
            result.status = "ERROR"
            result.message = str(e)
            self.logger.error(f"  💥 ERROR: {e}")
        
        finally:
            result.duration = time.time() - start_time
            self.results.results.append(result)
        
        return result
    
    # ==========================================================================
    # PREREQUISITE TESTS
    # ==========================================================================
    
    def test_java_installation(self) -> Tuple[bool, str, Dict]:
        """Test Java installation and version"""
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version_info = result.stderr.split('\n')[0]
                return True, f"Java found: {version_info}", {"version": version_info}
            else:
                return False, "Java not found or not working", {}
                
        except Exception as e:
            return False, f"Java check failed: {e}", {}
    
    def test_python_version(self) -> Tuple[bool, str, Dict]:
        """Test Python version compatibility"""
        version = sys.version_info
        
        if version.major == 3 and version.minor >= 9:
            return True, f"Python {version.major}.{version.minor} compatible", {
                "version": f"{version.major}.{version.minor}.{version.micro}"
            }
        else:
            return False, f"Python {version.major}.{version.minor} may not be compatible", {}
    
    def test_xvfb_availability(self) -> Tuple[bool, str, Dict]:
        """Test Xvfb availability for headless operation"""
        try:
            result = subprocess.run(
                ["which", "xvfb-run"],
                capture_output=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, "Xvfb available for headless operation", {
                    "path": result.stdout.decode().strip()
                }
            else:
                return False, "Xvfb not installed", {}
                
        except Exception as e:
            return False, f"Xvfb check failed: {e}", {}
    
    def test_ib_gateway_installation(self) -> Tuple[bool, str, Dict]:
        """Test IB Gateway installation"""
        gateway_dir = Path.home() / "Jts" / "ibgateway" / "1039"
        
        if gateway_dir.exists():
            jar_files = list(gateway_dir.glob("jars/*.jar"))
            return True, f"IB Gateway 10.39 found with {len(jar_files)} JAR files", {
                "path": str(gateway_dir),
                "jar_count": len(jar_files)
            }
        else:
            return False, f"IB Gateway directory not found: {gateway_dir}", {}
    
    def test_ibc_installation(self) -> Tuple[bool, str, Dict]:
        """Test IBC installation"""
        ibc_jar = Path.home() / "ibc" / "IBC.jar"
        
        if ibc_jar.exists():
            size_mb = ibc_jar.stat().st_size / (1024 * 1024)
            return True, f"IBC found ({size_mb:.1f} MB)", {
                "path": str(ibc_jar),
                "size_mb": size_mb
            }
        else:
            return False, f"IBC not found at {ibc_jar}", {}
    
    def test_port_availability(self) -> Tuple[bool, str, Dict]:
        """Test if API port is available"""
        port = self.config["port"]
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True, f"Port {port} is available", {"port": port}
            except OSError:
                return False, f"Port {port} is already in use", {"port": port}
    
    # ==========================================================================
    # CONFIGURATION TESTS
    # ==========================================================================
    
    def test_configuration_manager(self) -> Tuple[bool, str, Dict]:
        """Test Gateway configuration manager"""
        try:
            config = get_default_config(self.config["mode"])
            self.config_manager = GatewayConfigurationManager(config)
            
            # Validate configuration
            is_valid, errors = self.config_manager.validate_installation()
            
            if is_valid:
                return True, "Configuration manager initialized successfully", {
                    "version": config.version,
                    "mode": config.mode,
                    "port": config.port
                }
            else:
                return False, f"Configuration validation failed: {', '.join(errors)}", {
                    "errors": errors
                }
                
        except Exception as e:
            return False, f"Configuration manager error: {e}", {}
    
    def test_environment_variables(self) -> Tuple[bool, str, Dict]:
        """Test environment variable setup"""
        required_vars = {
            "TWS_MAJOR_VRSN": "1039",
            "IB_GATEWAY_VERSION": "10.39"
        }
        
        missing = []
        incorrect = []
        
        for var, expected in required_vars.items():
            value = os.getenv(var)
            if not value:
                missing.append(var)
            elif value != expected:
                incorrect.append(f"{var}={value} (expected {expected})")
        
        if not missing and not incorrect:
            return True, "Environment variables configured correctly", required_vars
        else:
            message = ""
            if missing:
                message += f"Missing: {', '.join(missing)}. "
            if incorrect:
                message += f"Incorrect: {', '.join(incorrect)}"
            return False, message, {"missing": missing, "incorrect": incorrect}
    
    def test_jvm_configuration(self) -> Tuple[bool, str, Dict]:
        """Test JVM configuration settings"""
        if not self.config_manager:
            return False, "Configuration manager not initialized", {}
        
        jvm_args = self.config_manager.generate_jvm_args()
        
        # Check required JVM arguments
        required = ["-Xms", "-Xmx", "-XX:+UseG1GC"]
        found = []
        
        for arg in jvm_args:
            for req in required:
                if req in arg:
                    found.append(req)
        
        if len(found) == len(required):
            return True, f"JVM configured with {len(jvm_args)} arguments", {
                "args": jvm_args
            }
        else:
            missing = set(required) - set(found)
            return False, f"Missing JVM arguments: {missing}", {
                "args": jvm_args,
                "missing": list(missing)
            }
    
    # ==========================================================================
    # CONNECTION TESTS
    # ==========================================================================
    
    async def test_basic_connection(self) -> Tuple[bool, str, Dict]:
        """Test basic connection to Gateway"""
        try:
            self.connection_manager = create_connection_manager(
                mode=self.config["mode"],
                auto_connect=False
            )
            
            # Attempt connection
            start_time = time.time()
            connected = await self.connection_manager.connect_async()
            connection_time = time.time() - start_time
            
            if connected:
                # Get connection stats
                stats = self.connection_manager.get_stats()
                
                return True, f"Connected in {connection_time:.2f}s", {
                    "connection_time": connection_time,
                    "latency_ms": stats.current_latency_ms,
                    "client_id": self.connection_manager.client_id
                }
            else:
                return False, "Failed to connect to Gateway", {
                    "connection_time": connection_time
                }
                
        except Exception as e:
            return False, f"Connection error: {e}", {}
    
    async def test_reconnection(self) -> Tuple[bool, str, Dict]:
        """Test reconnection capability"""
        if not self.connection_manager:
            return False, "Connection manager not initialized", {}
        
        try:
            # Disconnect first
            await self.connection_manager.disconnect_async()
            
            # Wait a bit
            await asyncio.sleep(2)
            
            # Attempt reconnection
            start_time = time.time()
            reconnected = await self.connection_manager.reconnect_async()
            reconnect_time = time.time() - start_time
            
            if reconnected:
                return True, f"Reconnected in {reconnect_time:.2f}s", {
                    "reconnect_time": reconnect_time
                }
            else:
                return False, "Reconnection failed", {
                    "reconnect_time": reconnect_time
                }
                
        except Exception as e:
            return False, f"Reconnection error: {e}", {}
    
    async def test_connection_stability(self) -> Tuple[bool, str, Dict]:
        """Test connection stability over time"""
        if not self.connection_manager:
            return False, "Connection manager not initialized", {}
        
        duration = 30  # Test for 30 seconds
        check_interval = 5
        checks_performed = 0
        failures = 0
        latencies = []
        
        start_time = time.time()
        
        while time.time() - start_time < duration:
            if self.connection_manager.is_connected():
                checks_performed += 1
                stats = self.connection_manager.get_stats()
                latencies.append(stats.current_latency_ms)
            else:
                failures += 1
            
            await asyncio.sleep(check_interval)
        
        if failures == 0 and checks_performed > 0:
            avg_latency = statistics.mean(latencies) if latencies else 0
            return True, f"Connection stable for {duration}s", {
                "duration": duration,
                "checks": checks_performed,
                "avg_latency_ms": avg_latency
            }
        else:
            return False, f"Connection unstable: {failures} failures", {
                "duration": duration,
                "checks": checks_performed,
                "failures": failures
            }
    
    # ==========================================================================
    # API FUNCTIONALITY TESTS
    # ==========================================================================
    
    async def test_account_data(self) -> Tuple[bool, str, Dict]:
        """Test account data retrieval"""
        if not self.connection_manager or not self.connection_manager.is_connected():
            return False, "Not connected to Gateway", {}
        
        try:
            ib = self.connection_manager.get_ib()
            if not ib:
                return False, "IB instance not available", {}
            
            # Request account summary
            account_values = await asyncio.wait_for(
                ib.accountSummaryAsync(),
                timeout=10
            )
            
            if account_values:
                return True, f"Retrieved {len(account_values)} account values", {
                    "value_count": len(account_values)
                }
            else:
                return False, "No account data received", {}
                
        except asyncio.TimeoutError:
            return False, "Account data request timeout", {}
        except Exception as e:
            return False, f"Account data error: {e}", {}
    
    async def test_market_data(self) -> Tuple[bool, str, Dict]:
        """Test market data subscription"""
        if not self.connection_manager or not self.connection_manager.is_connected():
            return False, "Not connected to Gateway", {}
        
        try:
            ib = self.connection_manager.get_ib()
            if not ib:
                return False, "IB instance not available", {}
            
            # Create SPY contract
            contract = Stock("SPY", "SMART", "USD")
            
            # Request market data
            ticker = ib.reqMktData(contract, "", False, False)
            
            # Wait for data
            await asyncio.sleep(5)
            
            if ticker.last or ticker.bid or ticker.ask:
                ib.cancelMktData(contract)
                return True, f"Market data received for SPY", {
                    "last": ticker.last,
                    "bid": ticker.bid,
                    "ask": ticker.ask
                }
            else:
                ib.cancelMktData(contract)
                return False, "No market data received", {}
                
        except Exception as e:
            return False, f"Market data error: {e}", {}
    
    async def test_historical_data(self) -> Tuple[bool, str, Dict]:
        """Test historical data retrieval"""
        if not self.connection_manager or not self.connection_manager.is_connected():
            return False, "Not connected to Gateway", {}
        
        try:
            ib = self.connection_manager.get_ib()
            if not ib:
                return False, "IB instance not available", {}
            
            # Create SPY contract
            contract = Stock("SPY", "SMART", "USD")
            
            # Request historical data
            bars = await asyncio.wait_for(
                ib.reqHistoricalDataAsync(
                    contract,
                    endDateTime="",
                    durationStr="1 D",
                    barSizeSetting="1 hour",
                    whatToShow="TRADES",
                    useRTH=True
                ),
                timeout=15
            )
            
            if bars:
                return True, f"Retrieved {len(bars)} historical bars", {
                    "bar_count": len(bars)
                }
            else:
                return False, "No historical data received", {}
                
        except asyncio.TimeoutError:
            return False, "Historical data request timeout", {}
        except Exception as e:
            return False, f"Historical data error: {e}", {}
    
    # ==========================================================================
    # PERFORMANCE TESTS
    # ==========================================================================
    
    async def test_api_latency(self) -> Tuple[bool, str, Dict]:
        """Test API response latency"""
        if not self.connection_manager or not self.connection_manager.is_connected():
            return False, "Not connected to Gateway", {}
        
        try:
            ib = self.connection_manager.get_ib()
            if not ib:
                return False, "IB instance not available", {}
            
            latencies = []
            iterations = 10
            
            for _ in range(iterations):
                start = time.time()
                server_time = ib.reqCurrentTime()
                latency_ms = (time.time() - start) * 1000
                latencies.append(latency_ms)
                await asyncio.sleep(0.1)
            
            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)
            min_latency = min(latencies)
            
            if avg_latency < BENCHMARKS["api_latency"]:
                return True, f"API latency acceptable: {avg_latency:.1f}ms avg", {
                    "avg_latency_ms": avg_latency,
                    "max_latency_ms": max_latency,
                    "min_latency_ms": min_latency
                }
            else:
                return False, f"API latency too high: {avg_latency:.1f}ms", {
                    "avg_latency_ms": avg_latency,
                    "benchmark_ms": BENCHMARKS["api_latency"]
                }
                
        except Exception as e:
            return False, f"Latency test error: {e}", {}
    
    def test_memory_usage(self) -> Tuple[bool, str, Dict]:
        """Test Gateway memory usage"""
        try:
            # Find Gateway process
            gateway_proc = None
            for proc in psutil.process_iter(['name', 'cmdline']):
                if "java" in proc.info['name'].lower():
                    cmdline = proc.info['cmdline'] or []
                    if any("ibgateway" in str(arg).lower() for arg in cmdline):
                        gateway_proc = proc
                        break
            
            if not gateway_proc:
                return False, "Gateway process not found", {}
            
            # Get memory info
            mem_info = gateway_proc.memory_info()
            mem_mb = mem_info.rss / (1024 * 1024)
            
            if mem_mb < BENCHMARKS["memory_usage"]:
                return True, f"Memory usage acceptable: {mem_mb:.1f} MB", {
                    "memory_mb": mem_mb,
                    "benchmark_mb": BENCHMARKS["memory_usage"]
                }
            else:
                return False, f"Memory usage high: {mem_mb:.1f} MB", {
                    "memory_mb": mem_mb,
                    "benchmark_mb": BENCHMARKS["memory_usage"]
                }
                
        except Exception as e:
            return False, f"Memory test error: {e}", {}
    
    def test_cpu_usage(self) -> Tuple[bool, str, Dict]:
        """Test Gateway CPU usage"""
        try:
            # Find Gateway process
            gateway_proc = None
            for proc in psutil.process_iter(['name', 'cmdline']):
                if "java" in proc.info['name'].lower():
                    cmdline = proc.info['cmdline'] or []
                    if any("ibgateway" in str(arg).lower() for arg in cmdline):
                        gateway_proc = proc
                        break
            
            if not gateway_proc:
                return False, "Gateway process not found", {}
            
            # Sample CPU usage
            cpu_samples = []
            for _ in range(5):
                cpu_percent = gateway_proc.cpu_percent(interval=1)
                cpu_samples.append(cpu_percent)
            
            avg_cpu = statistics.mean(cpu_samples)
            
            if avg_cpu < BENCHMARKS["cpu_usage"]:
                return True, f"CPU usage acceptable: {avg_cpu:.1f}%", {
                    "cpu_percent": avg_cpu,
                    "benchmark_percent": BENCHMARKS["cpu_usage"]
                }
            else:
                return False, f"CPU usage high: {avg_cpu:.1f}%", {
                    "cpu_percent": avg_cpu,
                    "benchmark_percent": BENCHMARKS["cpu_usage"]
                }
                
        except Exception as e:
            return False, f"CPU test error: {e}", {}
    
    # ==========================================================================
    # STRESS TESTS
    # ==========================================================================
    
    async def test_concurrent_connections(self) -> Tuple[bool, str, Dict]:
        """Test multiple concurrent connections"""
        managers = []
        successful = 0
        
        try:
            # Create multiple connection managers
            for i in range(self.config["stress_test_connections"]):
                manager = IBConnectionManager(
                    mode=self.config["mode"],
                    client_id=i + 10
                )
                managers.append(manager)
            
            # Connect all simultaneously
            tasks = [m.connect_async() for m in managers]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Count successful connections
            for i, result in enumerate(results):
                if result is True:
                    successful += 1
                elif isinstance(result, Exception):
                    self.logger.warning(f"Connection {i} failed: {result}")
            
            # Disconnect all
            for manager in managers:
                try:
                    await manager.disconnect_async()
                except:
                    pass
            
            if successful == len(managers):
                return True, f"All {successful} concurrent connections successful", {
                    "total": len(managers),
                    "successful": successful
                }
            else:
                return False, f"Only {successful}/{len(managers)} connections successful", {
                    "total": len(managers),
                    "successful": successful
                }
                
        except Exception as e:
            return False, f"Concurrent connection error: {e}", {}
    
    # ==========================================================================
    # MAIN TEST EXECUTION
    # ==========================================================================
    
    async def run_all_tests_async(self):
        """Run all tests asynchronously"""
        self.logger.info("=" * 60)
        self.logger.info("Starting IB Gateway 10.39 Integration Tests")
        self.logger.info("=" * 60)
        
        # Prerequisites
        self.logger.info("\n📋 PREREQUISITES TESTS")
        self.logger.info("-" * 40)
        self.run_test(self.test_java_installation, "Java Installation", "PREREQUISITES")
        self.run_test(self.test_python_version, "Python Version", "PREREQUISITES")
        self.run_test(self.test_xvfb_availability, "Xvfb Availability", "PREREQUISITES")
        self.run_test(self.test_ib_gateway_installation, "IB Gateway Installation", "PREREQUISITES")
        self.run_test(self.test_ibc_installation, "IBC Installation", "PREREQUISITES")
        self.run_test(self.test_port_availability, "Port Availability", "PREREQUISITES")
        
        # Configuration
        self.logger.info("\n⚙️ CONFIGURATION TESTS")
        self.logger.info("-" * 40)
        self.run_test(self.test_configuration_manager, "Configuration Manager", "CONFIGURATION")
        self.run_test(self.test_environment_variables, "Environment Variables", "CONFIGURATION")
        self.run_test(self.test_jvm_configuration, "JVM Configuration", "CONFIGURATION")
        
        # Connection Tests (if Gateway is running)
        self.logger.info("\n🔌 CONNECTION TESTS")
        self.logger.info("-" * 40)
        
        # Check if Gateway is running
        gateway_running = self._is_gateway_running()
        if gateway_running:
            await self.run_async_test(self.test_basic_connection, "Basic Connection", "CONNECTION")
            
            if self.connection_manager and self.connection_manager.is_connected():
                await self.run_async_test(self.test_reconnection, "Reconnection", "CONNECTION")
                await self.run_async_test(self.test_connection_stability, "Connection Stability", "CONNECTION")
                
                # API Functionality
                self.logger.info("\n📊 API FUNCTIONALITY TESTS")
                self.logger.info("-" * 40)
                await self.run_async_test(self.test_account_data, "Account Data", "API_FUNCTIONALITY")
                await self.run_async_test(self.test_market_data, "Market Data", "API_FUNCTIONALITY")
                await self.run_async_test(self.test_historical_data, "Historical Data", "API_FUNCTIONALITY")
                
                # Performance
                self.logger.info("\n⚡ PERFORMANCE TESTS")
                self.logger.info("-" * 40)
                await self.run_async_test(self.test_api_latency, "API Latency", "PERFORMANCE")
                self.run_test(self.test_memory_usage, "Memory Usage", "PERFORMANCE")
                self.run_test(self.test_cpu_usage, "CPU Usage", "PERFORMANCE")
                
                # Stress Tests
                self.logger.info("\n💪 STRESS TESTS")
                self.logger.info("-" * 40)
                await self.run_async_test(self.test_concurrent_connections, "Concurrent Connections", "STRESS")
                
                # Cleanup
                if self.connection_manager:
                    await self.connection_manager.disconnect_async()
        else:
            self.logger.warning("⚠️ Gateway not running - skipping connection tests")
            self.logger.info("Start Gateway with SpyderB21_GatewayStartupAutomation.py")
        
        # Calculate summary
        self.results.end_time = datetime.now()
        self.results.calculate_summary()
    
    def run_all_tests(self):
        """Run all tests synchronously"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.run_all_tests_async())
    
    def _is_gateway_running(self) -> bool:
        """Check if Gateway is running"""
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if "java" in proc.info['name'].lower():
                    cmdline = proc.info['cmdline'] or []
                    if any("ibgateway" in str(arg).lower() for arg in cmdline):
                        return True
            except:
                pass
        return False
    
    def generate_report(self) -> str:
        """Generate test report"""
        report = []
        report.append("\n" + "=" * 60)
        report.append("📊 TEST RESULTS SUMMARY")
        report.append("=" * 60)
        
        duration = (self.results.end_time - self.results.start_time).total_seconds()
        report.append(f"Total Duration: {duration:.2f} seconds")
        report.append(f"Total Tests: {self.results.total_tests}")
        report.append(f"✅ Passed: {self.results.passed}")
        report.append(f"❌ Failed: {self.results.failed}")
        report.append(f"⏭️  Skipped: {self.results.skipped}")
        report.append(f"💥 Errors: {self.results.errors}")
        report.append(f"Pass Rate: {self.results.get_pass_rate():.1f}%")
        
        # Failed tests details
        if self.results.failed > 0:
            report.append("\n" + "=" * 60)
            report.append("❌ FAILED TESTS")
            report.append("-" * 60)
            for result in self.results.results:
                if result.status == "FAIL":
                    report.append(f"• {result.name}: {result.message}")
        
        # Error details
        if self.results.errors > 0:
            report.append("\n" + "=" * 60)
            report.append("💥 TEST ERRORS")
            report.append("-" * 60)
            for result in self.results.results:
                if result.status == "ERROR":
                    report.append(f"• {result.name}: {result.message}")
        
        # Performance metrics
        perf_results = [r for r in self.results.results if r.category == "PERFORMANCE"]
        if perf_results:
            report.append("\n" + "=" * 60)
            report.append("⚡ PERFORMANCE METRICS")
            report.append("-" * 60)
            for result in perf_results:
                if result.is_passed() and result.details:
                    for key, value in result.details.items():
                        if isinstance(value, (int, float)):
                            report.append(f"• {key}: {value:.2f}")
        
        return "\n".join(report)
    
    def save_results(self, filepath: Optional[Path] = None):
        """Save test results to JSON file"""
        filepath = filepath or Path(f"test_results_{datetime.now():%Y%m%d_%H%M%S}.json")
        
        results_dict = {
            "start_time": self.results.start_time.isoformat(),
            "end_time": self.results.end_time.isoformat() if self.results.end_time else None,
            "summary": {
                "total": self.results.total_tests,
                "passed": self.results.passed,
                "failed": self.results.failed,
                "skipped": self.results.skipped,
                "errors": self.results.errors,
                "pass_rate": self.results.get_pass_rate()
            },
            "tests": [asdict(r) for r in self.results.results]
        }
        
        with open(filepath, 'w') as f:
            json.dump(results_dict, f, indent=2, default=str)
        
        self.logger.info(f"Results saved to {filepath}")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    print("🧪 IB Gateway 10.39 Integration Test Suite")
    print("=" * 60)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Create and run test suite
    suite = IntegrationTestSuite()
    
    try:
        # Run all tests
        suite.run_all_tests()
        
        # Generate and print report
        report = suite.generate_report()
        print(report)
        
        # Save results
        suite.save_results()
        
        # Exit with appropriate code
        if suite.results.failed > 0 or suite.results.errors > 0:
            print("\n❌ Some tests failed - review results above")
            sys.exit(1)
        else:
            print("\n✅ All tests passed!")
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test suite error: {e}")
        sys.exit(1)
