#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: SpyderB23_IBKRConnectionTester.py
Purpose: IBKR Connection Validation and Diagnostic Testing
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-30 Time: 21:45:00  

Module Description:
    Comprehensive IBKR connection testing module that validates connectivity to
    Interactive Brokers servers using both raw IBAPI and Spyder's ib-insync 
    infrastructure. Provides diagnostic tools for troubleshooting Zurich server
    routing issues and connection problems. Includes account verification and
    server connectivity tests as requested by IBKR support.

Dependencies:
    - ibapi (raw IBAPI for IBKR support tests)
    - ib_insync (Spyder's primary IB interface)
    - SpyderB_Broker components (SpyderClient, ConnectionManager)
    - SpyderU_Utilities (SpyderLogger)

Test Coverage:
    - Raw IBAPI connection test (IBKR support request)  
    - Spyder infrastructure connection test
    - Account summary validation
    - Multiple port testing (4001, 4002, 7496, 7497)
    - Server routing verification
    - Connection latency and stability testing
"""

import sys
import time
import socket
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import traceback

# Raw IBAPI imports (for IBKR support test)
try:
    from ibapi.client import EClient
    from ibapi.wrapper import EWrapper
    from ibapi.common import OrderId, TickerId
    from ibapi.account_summary_tags import AccountSummaryTags
    IBAPI_AVAILABLE = True
except ImportError:
    print("WARNING: IBAPI not available. Install with: pip install ibapi")
    IBAPI_AVAILABLE = False

# Spyder imports
try:
    from ib_async import IB, util
    IB_ASYNC_AVAILABLE = True
except ImportError:
    print("WARNING: ib_async not available. Install with: pip install ib-async")
    IB_ASYNC_AVAILABLE = False

# Spyder components
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    SPYDER_LOGGER_AVAILABLE = True
except ImportError:
    print("WARNING: SpyderLogger not available, using print statements")
    SPYDER_LOGGER_AVAILABLE = False

try:
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager, ConnectionConfig
    SPYDER_COMPONENTS_AVAILABLE = True
except ImportError:
    print("WARNING: Spyder broker components not available")
    SPYDER_COMPONENTS_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Connection constants
DEFAULT_HOST = '127.0.0.1'
TEST_TIMEOUT = 30  # seconds
ACCOUNT_SUMMARY_TIMEOUT = 10  # seconds

# Port configurations for testing
TEST_PORTS = {
    'paper_4002': 4002,      # Spyder default paper port
    'live_4001': 4001,       # Live trading port  
    'paper_7496': 7496,      # Standard TWS paper port (IBKR test)
    'live_7497': 7497        # Standard TWS live port
}

# ==============================================================================
# ENUMS
# ==============================================================================

class TestStatus(Enum):
    """Test execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"

class ConnectionMethod(Enum):
    """Connection test method"""
    RAW_IBAPI = "raw_ibapi"
    IB_INSYNC = "ib_insync"
    SPYDER_CLIENT = "spyder_client"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class TestResult:
    """Individual test result"""
    test_name: str
    method: ConnectionMethod
    port: int
    status: TestStatus
    duration: float = 0.0
    error_message: str = ""
    connection_time: Optional[datetime] = None
    account_data: Dict[str, Any] = field(default_factory=dict)
    server_info: Dict[str, str] = field(default_factory=dict)

@dataclass
class TestReport:
    """Comprehensive test report"""
    test_timestamp: datetime
    host: str
    results: List[TestResult] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate summary statistics"""
        self.summary = {
            'total_tests': len(self.results),
            'successful': len([r for r in self.results if r.status == TestStatus.SUCCESS]),
            'failed': len([r for r in self.results if r.status == TestStatus.FAILED]),
            'errors': len([r for r in self.results if r.status == TestStatus.ERROR]),
            'timeouts': len([r for r in self.results if r.status == TestStatus.TIMEOUT])
        }

# ==============================================================================
# RAW IBAPI TEST CLASS (IBKR SUPPORT REQUEST)
# ==============================================================================

class IBKRSupportTester(EClient, EWrapper):
    """
    Raw IBAPI test class as requested by IBKR support.
    Based on the reqAccountSummary.py script provided by IBKR.
    """
    
    def __init__(self, port: int = 7496):
        EClient.__init__(self, self)
        self.port = port
        self.account_data = {}
        self.connection_established = False
        self.test_complete = False
        self.error_occurred = False
        self.error_details = ""
        self.start_time = None
        
        # Setup logging
        if SPYDER_LOGGER_AVAILABLE:
            self.logger = SpyderLogger.get_logger(f"{__name__}.IBKRSupportTester")
        else:
            self.logger = None
    
    def _log(self, message: str, level: str = "info"):
        """Unified logging method"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_msg = f"[{timestamp}] IBKR_TEST: {message}"
        
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(formatted_msg)
    
    def nextValidId(self, orderId: OrderId):
        """Called when connection is established"""
        self._log(f"✅ Connection established. Next valid order ID: {orderId}")
        self.connection_established = True
        
        # Request account summary as per IBKR test script
        self._log("📊 Requesting account summary...")
        self.reqAccountSummary(
            reqId=1,
            groupName="All",
            tags=AccountSummaryTags.AllTags
        )
    
    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Handle account summary data"""
        self._log(f"📈 Account data - ReqID: {reqId}, Account: {account}, Tag: {tag}, Value: {value}, Currency: {currency}")
        
        # Store account data
        if account not in self.account_data:
            self.account_data[account] = {}
        self.account_data[account][tag] = {'value': value, 'currency': currency}
    
    def accountSummaryEnd(self, reqId: int):
        """Called when account summary is complete"""
        self._log(f"✅ Account summary complete for request {reqId}")
        self.test_complete = True
        
        # Disconnect gracefully
        self._log("🔌 Disconnecting...")
        self.disconnect()
    
    def error(self, reqId: TickerId, errorCode: int, errorString: str, advancedOrderRejectJson=""):
        """Handle connection errors"""
        error_msg = f"Error - ReqID: {reqId}, Code: {errorCode}, Message: {errorString}"
        if advancedOrderRejectJson:
            error_msg += f", Advanced: {advancedOrderRejectJson}"
        
        self._log(error_msg, "error")
        
        self.error_occurred = True
        self.error_details = f"Code {errorCode}: {errorString}"
        
        # For critical connection errors, mark test as complete
        if errorCode in [504, 502, 1100, 2104]:
            self.test_complete = True
    
    def run_test(self, timeout: int = TEST_TIMEOUT) -> TestResult:
        """
        Execute the IBKR connection test.
        
        Args:
            timeout: Maximum time to wait for test completion
            
        Returns:
            TestResult: Test execution results
        """
        result = TestResult(
            test_name=f"IBKR Support Test (Port {self.port})",
            method=ConnectionMethod.RAW_IBAPI,
            port=self.port,
            status=TestStatus.RUNNING,
            connection_time=datetime.now()
        )
        
        self.start_time = time.time()
        
        try:
            self._log(f"🔗 Connecting to {DEFAULT_HOST}:{self.port}...")
            
            # Attempt connection
            self.connect(DEFAULT_HOST, self.port, 0)
            
            # Start the message processing loop in a separate thread
            api_thread = threading.Thread(target=self.run, daemon=True)
            api_thread.start()
            
            # Wait for test completion or timeout
            elapsed = 0
            while elapsed < timeout and not self.test_complete:
                time.sleep(0.1)
                elapsed = time.time() - self.start_time
            
            # Calculate results
            result.duration = time.time() - self.start_time
            
            if self.test_complete and not self.error_occurred:
                result.status = TestStatus.SUCCESS
                result.account_data = self.account_data.copy()
                self._log("✅ Test completed successfully!")
                
            elif self.error_occurred:
                result.status = TestStatus.FAILED
                result.error_message = self.error_details
                self._log(f"❌ Test failed: {self.error_details}")
                
            else:
                result.status = TestStatus.TIMEOUT
                result.error_message = f"Test timed out after {timeout} seconds"
                self._log(f"⏰ Test timed out after {timeout} seconds")
            
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = f"Exception: {str(e)}"
            result.duration = time.time() - self.start_time if self.start_time else 0
            self._log(f"💥 Test exception: {str(e)}", "error")
        
        finally:
            try:
                self.disconnect()
            except:
                pass
        
        return result

# ==============================================================================
# IB-ASYNC TEST CLASS
# ==============================================================================

class IBAsyncTester:
    """Test connection using ib_async library"""
    
    def __init__(self, port: int = 4002):
        self.port = port
        self.ib = IB()
        
        # Setup logging
        if SPYDER_LOGGER_AVAILABLE:
            self.logger = SpyderLogger.get_logger(f"{__name__}.IBAsyncTester")
        else:
            self.logger = None
    
    def _log(self, message: str, level: str = "info"):
        """Unified logging method"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_msg = f"[{timestamp}] IB_ASYNC_TEST: {message}"
        
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(formatted_msg)
    
    def run_test(self, timeout: int = TEST_TIMEOUT) -> TestResult:
        """
        Execute ib_async connection test.
        
        Args:
            timeout: Maximum time to wait for connection
            
        Returns:
            TestResult: Test execution results
        """
        result = TestResult(
            test_name=f"IB-Async Test (Port {self.port})",
            method=ConnectionMethod.IB_INSYNC,
            port=self.port,
            status=TestStatus.RUNNING,
            connection_time=datetime.now()
        )
        
        start_time = time.time()
        
        try:
            self._log(f"Connecting via ib_async to {DEFAULT_HOST}:{self.port}...")
            
            # Attempt connection with timeout
            self.ib.connect(DEFAULT_HOST, self.port, clientId=1, timeout=timeout)
            
            if self.ib.isConnected():
                self._log("Connection established successfully!")
                
                # Get account summary
                account_summary = self.ib.accountSummary()
                self._log(f"Retrieved {len(account_summary)} account summary items")
                
                # Store account data
                result.account_data = {
                    item.tag: {'value': item.value, 'currency': item.currency}
                    for item in account_summary
                }
                
                # Get connection info
                result.server_info = {
                    'connected_at': str(datetime.now()),
                    'client_id': '1',
                    'account_count': len(set(item.account for item in account_summary))
                }
                
                result.status = TestStatus.SUCCESS
                self._log("Test completed successfully!")
                
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Connection failed - not connected after timeout"
                self._log("Connection failed", "error")
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = f"Exception: {str(e)}"
            self._log(f"Test exception: {str(e)}", "error")
            
        finally:
            result.duration = time.time() - start_time
            try:
                if self.ib.isConnected():
                    self.ib.disconnect()
                    self._log("Disconnected")
            except:
                pass
        
        return result

# ==============================================================================
# SPYDER CLIENT TEST CLASS
# ==============================================================================

class SpyderClientTester:
    """Test connection using Spyder's client infrastructure"""
    
    def __init__(self, port: int = 4002):
        self.port = port
        self.client = None
        
        # Setup logging
        if SPYDER_LOGGER_AVAILABLE:
            self.logger = SpyderLogger.get_logger(f"{__name__}.SpyderClientTester")
        else:
            self.logger = None
    
    def _log(self, message: str, level: str = "info"):
        """Unified logging method"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_msg = f"[{timestamp}] SPYDER_CLIENT_TEST: {message}"
        
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(formatted_msg)
    
    def run_test(self, timeout: int = TEST_TIMEOUT) -> TestResult:
        """
        Execute Spyder client connection test.
        
        Args:
            timeout: Maximum time to wait for connection
            
        Returns:
            TestResult: Test execution results
        """
        result = TestResult(
            test_name=f"Spyder Client Test (Port {self.port})",
            method=ConnectionMethod.SPYDER_CLIENT,
            port=self.port,
            status=TestStatus.RUNNING,
            connection_time=datetime.now()
        )
        
        start_time = time.time()
        
        if not SPYDER_COMPONENTS_AVAILABLE:
            result.status = TestStatus.ERROR
            result.error_message = "Spyder components not available"
            result.duration = 0
            return result
        
        try:
            self._log(f"🔗 Connecting via SpyderClient to {DEFAULT_HOST}:{self.port}...")
            
            # Create connection configuration
            config = ConnectionConfig(
                host=DEFAULT_HOST,
                paper_port=self.port if self.port in [4002, 7496] else 4002,
                live_port=self.port if self.port in [4001, 7497] else 4001,
                client_id=1,
                trading_mode="paper" if self.port in [4002, 7496] else "live"
            )
            
            # Initialize client
            self.client = SpyderClient(config)
            
            # Attempt connection
            connection_success = self.client.connect()
            
            if connection_success and self.client.is_connected():
                self._log("✅ Spyder client connected successfully!")
                
                # Get account information
                try:
                    account_info = self.client.get_account_summary()
                    result.account_data = account_info or {}
                    self._log(f"📊 Retrieved account information: {len(result.account_data)} items")
                except Exception as e:
                    self._log(f"⚠️ Could not retrieve account info: {e}", "warning")
                
                result.status = TestStatus.SUCCESS
                self._log("✅ Spyder client test completed successfully!")
                
            else:
                result.status = TestStatus.FAILED
                result.error_message = "Spyder client connection failed"
                self._log("❌ Spyder client connection failed", "error")
                
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = f"Exception: {str(e)}"
            self._log(f"💥 Spyder client test exception: {str(e)}", "error")
            
        finally:
            result.duration = time.time() - start_time
            try:
                if self.client and self.client.is_connected():
                    self.client.disconnect()
                    self._log("🔌 Spyder client disconnected")
            except:
                pass
        
        return result

# ==============================================================================
# MAIN TESTER CLASS
# ==============================================================================

class IBKRConnectionTester:
    """
    Comprehensive IBKR connection tester combining all test methods.
    """
    
    def __init__(self):
        # Setup logging
        if SPYDER_LOGGER_AVAILABLE:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = None
        
        self._log("🚀 IBKR Connection Tester initialized")
    
    def _log(self, message: str, level: str = "info"):
        """Unified logging method"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted_msg = f"[{timestamp}] IBKR_TESTER: {message}"
        
        if self.logger:
            getattr(self.logger, level)(message)
        else:
            print(formatted_msg)
    
    def test_port_connectivity(self, port: int, timeout: int = 5) -> bool:
        """
        Test basic socket connectivity to a port.
        
        Args:
            port: Port number to test
            timeout: Connection timeout in seconds
            
        Returns:
            bool: True if port is reachable
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((DEFAULT_HOST, port))
                return result == 0
        except Exception:
            return False
    
    def run_ibkr_support_test(self, port: int = 7496) -> TestResult:
        """
        Run the IBKR support test using raw IBAPI.
        This is the exact test requested by IBKR support.
        
        Args:
            port: Port to test (default 7496 as per IBKR)
            
        Returns:
            TestResult: Test results
        """
        if not IBAPI_AVAILABLE:
            return TestResult(
                test_name=f"IBKR Support Test (Port {port})",
                method=ConnectionMethod.RAW_IBAPI,
                port=port,
                status=TestStatus.ERROR,
                error_message="IBAPI library not available. Install with: pip install ibapi"
            )
        
        self._log(f"▶️ Running IBKR Support Test on port {port}")
        tester = IBKRSupportTester(port)
        result = tester.run_test()
        self._log(f"✅ IBKR Support Test completed: {result.status.value}")
        return result
    
    def run_ib_async_test(self, port: int = 4002) -> TestResult:
        """
        Run connection test using ib_async library.
        
        Args:
            port: Port to test
            
        Returns:
            TestResult: Test results
        """
        if not IB_ASYNC_AVAILABLE:
            return TestResult(
                test_name=f"IB-Async Test (Port {port})",
                method=ConnectionMethod.IB_INSYNC,
                port=port,
                status=TestStatus.ERROR,
                error_message="ib_async library not available. Install with: pip install ib-async"
            )
        
        self._log(f"Running IB-Async Test on port {port}")
        tester = IBAsyncTester(port)
        result = tester.run_test()
        self._log(f"IB-Async Test completed: {result.status.value}")
        return result
    
    def run_spyder_client_test(self, port: int = 4002) -> TestResult:
        """
        Run connection test using Spyder client infrastructure.
        
        Args:
            port: Port to test
            
        Returns:
            TestResult: Test results  
        """
        self._log(f"▶️ Running Spyder Client Test on port {port}")
        tester = SpyderClientTester(port)
        result = tester.run_test()
        self._log(f"✅ Spyder Client Test completed: {result.status.value}")
        return result
    
    def run_comprehensive_test(self) -> TestReport:
        """
        Run comprehensive connection tests across all methods and ports.
        
        Returns:
            TestReport: Complete test results
        """
        self._log("🎯 Starting comprehensive IBKR connection tests")
        
        report = TestReport(
            test_timestamp=datetime.now(),
            host=DEFAULT_HOST
        )
        
        # Test each port with available methods
        for port_name, port in TEST_PORTS.items():
            self._log(f"📡 Testing port {port} ({port_name})")
            
            # Check basic port connectivity first
            if not self.test_port_connectivity(port):
                self._log(f"❌ Port {port} not reachable - skipping tests")
                continue
            
            # IBKR Support Test (raw IBAPI) - prioritize standard TWS ports
            if port in [7496, 7497]:
                result = self.run_ibkr_support_test(port)
                report.results.append(result)
            
            # IB-Async Test
            result = self.run_ib_async_test(port)
            report.results.append(result)
            
            # Spyder Client Test
            result = self.run_spyder_client_test(port)
            report.results.append(result)
        
        # Generate recommendations
        self._generate_recommendations(report)
        
        self._log("✅ Comprehensive testing completed")
        return report
    
    def _generate_recommendations(self, report: TestReport):
        """Generate recommendations based on test results"""
        successful_tests = [r for r in report.results if r.status == TestStatus.SUCCESS]
        failed_tests = [r for r in report.results if r.status == TestStatus.FAILED]
        
        if not successful_tests:
            report.recommendations.extend([
                "❌ No successful connections detected",
                "🔧 Verify IB Gateway/TWS is running",
                "🔧 Check if ports are correctly configured",
                "🔧 Verify account credentials and permissions",
                "🔧 Contact IBKR support with these test results"
            ])
        else:
            working_ports = list(set(r.port for r in successful_tests))
            report.recommendations.append(f"✅ Working ports detected: {working_ports}")
            
            # Recommend best connection method
            if any(r.method == ConnectionMethod.SPYDER_CLIENT for r in successful_tests):
                report.recommendations.append("Spyder client infrastructure working - use for production")
            elif any(r.method == ConnectionMethod.IB_INSYNC for r in successful_tests):
                report.recommendations.append("IB-Async connection working - suitable for trading")
            elif any(r.method == ConnectionMethod.RAW_IBAPI for r in successful_tests):
                report.recommendations.append("Raw IBAPI connection working - basic connectivity confirmed")
        
        if failed_tests:
            error_patterns = [r.error_message for r in failed_tests if r.error_message]
            if error_patterns:
                report.recommendations.append(f"⚠️ Common errors detected: Check connectivity and authentication")
    
    def print_report(self, report: TestReport):
        """Print formatted test report"""
        print("\n" + "=" * 80)
        print("🔍 IBKR CONNECTION TEST REPORT")
        print("=" * 80)
        print(f"Test Timestamp: {report.test_timestamp}")
        print(f"Host: {report.host}")
        print(f"Total Tests: {report.summary['total_tests']}")
        print(f"Successful: {report.summary['successful']}")
        print(f"Failed: {report.summary['failed']}")
        print(f"Errors: {report.summary['errors']}")
        print(f"Timeouts: {report.summary['timeouts']}")
        
        print("\n📊 DETAILED RESULTS:")
        print("-" * 80)
        
        for result in report.results:
            status_emoji = {
                TestStatus.SUCCESS: "✅",
                TestStatus.FAILED: "❌", 
                TestStatus.ERROR: "💥",
                TestStatus.TIMEOUT: "⏰"
            }.get(result.status, "❓")
            
            print(f"{status_emoji} {result.test_name}")
            print(f"   Method: {result.method.value}")
            print(f"   Port: {result.port}")
            print(f"   Duration: {result.duration:.2f}s")
            print(f"   Status: {result.status.value}")
            
            if result.error_message:
                print(f"   Error: {result.error_message}")
                
            if result.account_data:
                print(f"   Account Items: {len(result.account_data)}")
            
            print()
        
        print("\n💡 RECOMMENDATIONS:")
        print("-" * 80)
        for rec in report.recommendations:
            print(f"   {rec}")
        
        print("\n" + "=" * 80)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function"""
    print("🚀 SPYDER IBKR Connection Tester v1.0")
    print("=====================================")
    
    # Initialize tester
    tester = IBKRConnectionTester()
    
    # Run comprehensive tests
    report = tester.run_comprehensive_test()
    
    # Display results
    tester.print_report(report)
    
    # Return success code based on results
    return 0 if report.summary['successful'] > 0 else 1

if __name__ == "__main__":
    sys.exit(main())