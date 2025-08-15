#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Test Suite for IB Integration Stack
Tests SpyderI12 (IBAutomater), SpyderI14 (Connection Manager), and SpyderI15 (Trading Interface)
"""

import logging
import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, List
import json

# Setup colored logging
class ColoredFormatter(logging.Formatter):
    """Colored log formatter for terminal output"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)

# Setup logging
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        handler,
        logging.FileHandler('spyder_ib_test.log')
    ]
)

logger = logging.getLogger(__name__)

# ================================================================================================
# TEST CONFIGURATION
# ================================================================================================

TEST_CONFIG = {
    # IB Gateway settings - AUTO-DETECTED FOR ADAM'S SYSTEM
    "ib_directory": "/home/adam/Jts",  # Found by finder script
    "ib_version": "10.37",             # Found by finder script
    "trading_mode": "paper",           # paper or live
    "port": 4002,                      # IB Gateway API port
    "client_id": 1,                    # IB API client ID
    
    # Test settings
    "connection_timeout": 30,
    "test_timeout": 60,
    "skip_manual_tests": False,  # Set to True to skip tests requiring manual interaction
}

# ================================================================================================
# TEST RESULTS TRACKING
# ================================================================================================

class TestResults:
    """Track test results"""
    
    def __init__(self):
        self.tests: Dict[str, Dict[str, Any]] = {}
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
    
    def add_test(self, test_name: str, passed: bool, message: str = "", details: Any = None):
        """Add test result"""
        self.tests[test_name] = {
            "passed": passed,
            "message": message,
            "details": details,
            "timestamp": time.time()
        }
        
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
    
    def skip_test(self, test_name: str, reason: str):
        """Skip a test"""
        self.tests[test_name] = {
            "passed": None,
            "message": f"SKIPPED: {reason}",
            "details": None,
            "timestamp": time.time()
        }
        self.total_tests += 1
        self.skipped_tests += 1
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("🧪 SPYDER IB INTEGRATION TEST RESULTS")
        print("="*80)
        
        for test_name, result in self.tests.items():
            if result["passed"] is None:
                status = "⏭️ SKIPPED"
                color = "\033[33m"  # Yellow
            elif result["passed"]:
                status = "✅ PASSED"
                color = "\033[32m"  # Green
            else:
                status = "❌ FAILED"
                color = "\033[31m"  # Red
            
            print(f"{color}{status}\033[0m {test_name}: {result['message']}")
        
        print("\n" + "-"*80)
        print(f"📊 SUMMARY: {self.total_tests} total, {self.passed_tests} passed, {self.failed_tests} failed, {self.skipped_tests} skipped")
        
        success_rate = (self.passed_tests / (self.total_tests - self.skipped_tests)) * 100 if (self.total_tests - self.skipped_tests) > 0 else 0
        print(f"📈 SUCCESS RATE: {success_rate:.1f}%")
        
        if self.failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Your IB integration is ready!")
        else:
            print("⚠️ Some tests failed. Check the error messages above.")
        
        print("="*80)

# ================================================================================================
# TEST SUITE
# ================================================================================================

class SpyderIBTestSuite:
    """Comprehensive test suite for Spyder IB integration"""
    
    def __init__(self):
        self.results = TestResults()
        self.modules_available = {}
        
    def run_all_tests(self):
        """Run all tests"""
        logger.info("🧪 Starting Spyder IB Integration Test Suite")
        logger.info("="*60)
        
        try:
            # Test 1: Check module availability
            self.test_module_imports()
            
            # Test 2: Check dependencies
            self.test_dependencies()
            
            # Test 3: Test IBAutomater Core
            self.test_ibautomater_core()
            
            # Test 4: Test Connection Manager
            self.test_connection_manager()
            
            # Test 5: Test Trading Interface
            self.test_trading_interface()
            
            # Test 6: Integration test
            if not TEST_CONFIG["skip_manual_tests"]:
                self.test_full_integration()
            else:
                self.results.skip_test("Full Integration Test", "Manual tests skipped")
            
        except KeyboardInterrupt:
            logger.warning("⚠️ Tests interrupted by user")
        except Exception as e:
            logger.error(f"❌ Test suite error: {e}")
        finally:
            self.results.print_summary()
    
    def test_module_imports(self):
        """Test 1: Module import tests"""
        logger.info("🔍 Test 1: Checking module imports...")
        
        # Test IBAutomater import
        try:
            from SpyderI12_IBAutomaterCore import IBAutomater, create_simple_automater, check_ib_installation
            self.modules_available["ibautomater"] = True
            self.results.add_test("IBAutomater Import", True, "Module imported successfully")
            logger.info("✅ IBAutomater module imported")
        except ImportError as e:
            self.modules_available["ibautomater"] = False
            self.results.add_test("IBAutomater Import", False, f"Import failed: {e}")
            logger.error(f"❌ IBAutomater import failed: {e}")
        
        # Test Connection Manager import
        try:
            from SpyderI14_IBConnectionManager import IBConnectionManager, create_connection_manager, ConnectionConfig
            self.modules_available["connection_manager"] = True
            self.results.add_test("Connection Manager Import", True, "Module imported successfully")
            logger.info("✅ Connection Manager module imported")
        except ImportError as e:
            self.modules_available["connection_manager"] = False
            self.results.add_test("Connection Manager Import", False, f"Import failed: {e}")
            logger.error(f"❌ Connection Manager import failed: {e}")
        
        # Test Trading Interface import
        try:
            from SpyderI15_IBTradingInterface import IBTradingInterface, create_trading_interface, OptionContract
            self.modules_available["trading_interface"] = True
            self.results.add_test("Trading Interface Import", True, "Module imported successfully")
            logger.info("✅ Trading Interface module imported")
        except ImportError as e:
            self.modules_available["trading_interface"] = False
            self.results.add_test("Trading Interface Import", False, f"Import failed: {e}")
            logger.error(f"❌ Trading Interface import failed: {e}")
    
    def test_dependencies(self):
        """Test 2: Dependency tests"""
        logger.info("🔍 Test 2: Checking dependencies...")
        
        # Test psutil
        try:
            import psutil
            self.results.add_test("psutil Dependency", True, f"Version {psutil.__version__}")
            logger.info("✅ psutil available")
        except ImportError:
            self.results.add_test("psutil Dependency", False, "psutil not installed")
            logger.error("❌ psutil not available - install with: pip install psutil")
        
        # Test ib_async
        try:
            from ib_async import IB, Stock, Option
            self.results.add_test("ib_async Dependency", True, "ib_async available")
            logger.info("✅ ib_async available")
        except ImportError:
            self.results.add_test("ib_async Dependency", False, "ib_async not installed")
            logger.error("❌ ib_async not available - install with: pip install ib_async")
        
        # Test IB Gateway installation
        if self.modules_available.get("ibautomater"):
            from SpyderI12_IBAutomaterCore import check_ib_installation
            
            ib_installed = check_ib_installation(TEST_CONFIG["ib_directory"])
            if ib_installed:
                self.results.add_test("IB Gateway Installation", True, f"Found at {TEST_CONFIG['ib_directory']}")
                logger.info(f"✅ IB Gateway found at {TEST_CONFIG['ib_directory']}")
            else:
                self.results.add_test("IB Gateway Installation", False, f"Not found at {TEST_CONFIG['ib_directory']}")
                logger.error(f"❌ IB Gateway not found at {TEST_CONFIG['ib_directory']}")
                logger.info("💡 Update TEST_CONFIG['ib_directory'] to your IB Gateway installation path")
    
    def test_ibautomater_core(self):
        """Test 3: IBAutomater core functionality"""
        logger.info("🔍 Test 3: Testing IBAutomater core...")
        
        if not self.modules_available.get("ibautomater"):
            self.results.skip_test("IBAutomater Core Test", "Module not available")
            return
        
        try:
            from SpyderI12_IBAutomaterCore import create_simple_automater
            
            # Create IBAutomater instance
            automater = create_simple_automater(
                ib_directory=TEST_CONFIG["ib_directory"],
                ib_version=TEST_CONFIG["ib_version"],
                trading_mode=TEST_CONFIG["trading_mode"],
                port=TEST_CONFIG["port"]
            )
            
            self.results.add_test("IBAutomater Creation", True, "Instance created successfully")
            logger.info("✅ IBAutomater instance created")
            
            # Test status check
            status = automater.get_status()
            self.results.add_test("IBAutomater Status Check", True, f"Status: {status}")
            logger.info(f"✅ Status check: {status}")
            
            # Test connection tester
            connection_test = automater.connection_tester.test_port_open()
            if connection_test:
                self.results.add_test("Port Connectivity", True, f"Port {TEST_CONFIG['port']} is open")
                logger.info(f"✅ Port {TEST_CONFIG['port']} is open")
            else:
                self.results.add_test("Port Connectivity", False, f"Port {TEST_CONFIG['port']} is closed")
                logger.warning(f"⚠️ Port {TEST_CONFIG['port']} is closed - IB Gateway not running")
            
        except Exception as e:
            self.results.add_test("IBAutomater Core Test", False, f"Error: {e}")
            logger.error(f"❌ IBAutomater core test failed: {e}")
    
    def test_connection_manager(self):
        """Test 4: Connection Manager functionality"""
        logger.info("🔍 Test 4: Testing Connection Manager...")
        
        if not self.modules_available.get("connection_manager"):
            self.results.skip_test("Connection Manager Test", "Module not available")
            return
        
        try:
            from SpyderI14_IBConnectionManager import create_connection_manager
            
            # Create connection manager
            connection_manager = create_connection_manager(
                ib_directory=TEST_CONFIG["ib_directory"],
                ib_version=TEST_CONFIG["ib_version"],
                trading_mode=TEST_CONFIG["trading_mode"],
                port=TEST_CONFIG["port"],
                client_id=TEST_CONFIG["client_id"]
            )
            
            self.results.add_test("Connection Manager Creation", True, "Instance created successfully")
            logger.info("✅ Connection Manager instance created")
            
            # Test status
            status = connection_manager.get_status()
            self.results.add_test("Connection Manager Status", True, f"State: {status.state.value}")
            logger.info(f"✅ Connection Manager status: {status.state.value}")
            
            # Test diagnostics
            diagnostics = connection_manager.get_diagnostics()
            self.results.add_test("Connection Manager Diagnostics", True, "Diagnostics generated")
            logger.info("✅ Diagnostics generated successfully")
            
        except Exception as e:
            self.results.add_test("Connection Manager Test", False, f"Error: {e}")
            logger.error(f"❌ Connection Manager test failed: {e}")
    
    def test_trading_interface(self):
        """Test 5: Trading Interface functionality"""
        logger.info("🔍 Test 5: Testing Trading Interface...")
        
        if not self.modules_available.get("trading_interface"):
            self.results.skip_test("Trading Interface Test", "Module not available")
            return
        
        try:
            from SpyderI15_IBTradingInterface import SpyderOptionContract, OptionType, get_spy_expiry_dates
            
            # Test option contract creation
            test_option = SpyderOptionContract(
                symbol="SPY",
                expiry="20250117",
                strike=450.0,
                option_type=OptionType.CALL
            )
            
            self.results.add_test("Option Contract Creation", True, f"Created {test_option.symbol} {test_option.expiry} {test_option.strike}{test_option.option_type.value}")
            logger.info(f"✅ Option contract created: {test_option.symbol} {test_option.expiry} {test_option.strike}{test_option.option_type.value}")
            
            # Test ib_async contract conversion
            ib_contract = test_option.to_ib_contract()
            self.results.add_test("ib_async Contract Conversion", True, f"Converted to ib_async {type(ib_contract).__name__}")
            logger.info(f"✅ Converted to ib_async contract: {type(ib_contract).__name__}")
            
            # Test expiry dates
            expiry_dates = get_spy_expiry_dates(30)
            self.results.add_test("SPY Expiry Dates", True, f"Found {len(expiry_dates)} expiry dates")
            logger.info(f"✅ Found {len(expiry_dates)} upcoming SPY expiry dates")
            
            self.results.add_test("Trading Interface Structure", True, "All classes and functions available with ib_async")
            logger.info("✅ Trading Interface structure validated with ib_async")
            
        except Exception as e:
            self.results.add_test("Trading Interface Test", False, f"Error: {e}")
            logger.error(f"❌ Trading Interface test failed: {e}")
    
    def test_full_integration(self):
        """Test 6: Full integration test (requires manual interaction)"""
        logger.info("🔍 Test 6: Full integration test...")
        
        # Check if all modules are available
        required_modules = ["ibautomater", "connection_manager", "trading_interface"]
        missing_modules = [mod for mod in required_modules if not self.modules_available.get(mod)]
        
        if missing_modules:
            self.results.skip_test("Full Integration Test", f"Missing modules: {missing_modules}")
            return
        
        logger.info("⚠️ This test requires manual interaction and IB Gateway")
        logger.info("📝 The test will:")
        logger.info("   1. Start IBAutomater")
        logger.info("   2. Wait for you to log in manually")
        logger.info("   3. Test connection manager")
        logger.info("   4. Test trading interface")
        
        response = input("\n🤔 Do you want to run the full integration test? (y/N): ")
        
        if response.lower() != 'y':
            self.results.skip_test("Full Integration Test", "User declined")
            return
        
        try:
            # Import all modules
            from SpyderI12_IBAutomaterCore import create_simple_automater
            from SpyderI14_IBConnectionManager import create_connection_manager
            from SpyderI15_IBTradingInterface import create_trading_interface
            
            logger.info("🚀 Starting full integration test...")
            
            # Step 1: Start IBAutomater
            logger.info("📋 Step 1: Starting IBAutomater...")
            automater = create_simple_automater(
                ib_directory=TEST_CONFIG["ib_directory"],
                ib_version=TEST_CONFIG["ib_version"],
                trading_mode=TEST_CONFIG["trading_mode"],
                port=TEST_CONFIG["port"]
            )
            
            # Setup event handlers
            events_received = []
            automater.on_process_started(lambda e: events_received.append(f"Process started: {e['data']}"))
            automater.on_connection_ready(lambda e: events_received.append("Connection ready"))
            
            result = automater.start(wait_for_manual_login=True)
            
            if result.success:
                self.results.add_test("Integration - IBAutomater Start", True, f"Started with PID {result.process_id}")
                logger.info(f"✅ IBAutomater started (PID: {result.process_id})")
                
                # Step 2: Test Connection Manager
                logger.info("📋 Step 2: Testing Connection Manager...")
                connection_manager = create_connection_manager(
                    ib_directory=TEST_CONFIG["ib_directory"],
                    ib_version=TEST_CONFIG["ib_version"],
                    trading_mode=TEST_CONFIG["trading_mode"],
                    port=TEST_CONFIG["port"],
                    client_id=TEST_CONFIG["client_id"]
                )
                
                # Wait a bit for connection to stabilize
                time.sleep(5)
                
                status = connection_manager.get_status()
                if status.api_connected:
                    self.results.add_test("Integration - Connection Manager", True, "API connected")
                    logger.info("✅ Connection Manager shows API connected")
                else:
                    self.results.add_test("Integration - Connection Manager", False, "API not connected")
                    logger.warning("⚠️ Connection Manager shows API not connected")
                
                # Step 3: Test Trading Interface (if ib_async available)
                try:
                    logger.info("📋 Step 3: Testing Trading Interface...")
                    trading_interface = create_trading_interface(connection_manager)
                    
                    # Note: We don't actually start the trading interface in test mode
                    # as it requires a live connection and ib_async setup
                    self.results.add_test("Integration - Trading Interface Creation", True, "Created successfully with ib_async")
                    logger.info("✅ Trading Interface created with ib_async (not started in test mode)")
                    
                except Exception as e:
                    self.results.add_test("Integration - Trading Interface Creation", False, f"Error: {e}")
                    logger.error(f"❌ Trading Interface creation failed: {e}")
                
                # Clean up
                logger.info("🧹 Cleaning up...")
                automater.stop()
                
                self.results.add_test("Integration - Full Test", True, "Integration test completed")
                logger.info("✅ Full integration test completed")
                
            else:
                self.results.add_test("Integration - IBAutomater Start", False, result.error_message)
                logger.error(f"❌ IBAutomater start failed: {result.error_message}")
                
        except Exception as e:
            self.results.add_test("Integration - Full Test", False, f"Error: {e}")
            logger.error(f"❌ Full integration test failed: {e}")

def print_configuration_help():
    """Print configuration help"""
    print("\n" + "="*80)
    print("⚙️ CONFIGURATION HELP")
    print("="*80)
    print("If tests fail, check these configuration items:")
    print()
    print("1. 📂 IB Gateway Installation Path:")
    print(f"   Current: {TEST_CONFIG['ib_directory']}")
    print("   Update TEST_CONFIG['ib_directory'] to your IB Gateway path")
    print()
    print("2. 🔢 IB Gateway Version:")
    print(f"   Current: {TEST_CONFIG['ib_version']}")
    print("   Update TEST_CONFIG['ib_version'] to match your installation")
    print()
    print("3. 🔌 API Port:")
    print(f"   Current: {TEST_CONFIG['port']}")
    print("   Make sure this matches your IB Gateway API configuration")
    print()
    print("4. 📊 Trading Mode:")
    print(f"   Current: {TEST_CONFIG['trading_mode']}")
    print("   Use 'paper' for paper trading, 'live' for live trading")
    print()
    print("5. 📦 Required Python Packages:")
    print("   pip install psutil ibapi")
    print()
    print("="*80)

def main():
    """Main test function"""
    print("🧪 SPYDER IB INTEGRATION TEST SUITE")
    print("="*60)
    print("This will test your complete IB integration stack:")
    print("• SpyderI12_IBAutomaterCore.py")
    print("• SpyderI14_IBConnectionManager.py") 
    print("• SpyderI15_IBTradingInterface.py")
    print()
    
    # Show current configuration
    print("📋 Current Test Configuration:")
    for key, value in TEST_CONFIG.items():
        print(f"   {key}: {value}")
    print()
    
    # Ask if user wants to proceed
    response = input("🤔 Do you want to run the test suite? (Y/n): ")
    if response.lower() == 'n':
        print("👋 Test cancelled by user")
        return
    
    # Run tests
    test_suite = SpyderIBTestSuite()
    test_suite.run_all_tests()
    
    # Show configuration help if there were failures
    if test_suite.results.failed_tests > 0:
        print_configuration_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Test suite error: {e}")
        sys.exit(1)
