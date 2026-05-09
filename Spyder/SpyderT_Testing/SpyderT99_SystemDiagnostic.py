#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT99_SystemDiagnostic.py
Purpose: Comprehensive system diagnostic and debugging script
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-23 Time: 15:00:00

Module Description:
    This diagnostic script systematically tests each component of the Spyder
    trading system to identify initialization problems, missing dependencies,
    and configuration issues. Provides detailed error reporting and suggested
    fixes for a step-by-step system repair approach.

"""

import sys
import os
import importlib
import traceback
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Any
import json
# ==============================================================================
# SETUP AND CONFIGURATION
# ==============================================================================

# Add project root to path
SPYDER_ROOT = Path(__file__).parent.parent if Path(__file__).parent.name.startswith('SpyderT') else Path(__file__).parent
sys.path.insert(0, str(SPYDER_ROOT))

# Color codes for output
class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    WHITE = '\033[1;37m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

# Test results storage
class DiagnosticResult:
    def __init__(self, name: str, status: str, message: str = "", details: str = "", fix_suggestion: str = ""):
        self.name = name
        self.status = status  # PASS, FAIL, WARN, SKIP
        self.message = message
        self.details = details
        self.fix_suggestion = fix_suggestion
        self.timestamp = datetime.now()

class SpyderDiagnostic:
    """Comprehensive Spyder system diagnostic tool"""

    def __init__(self):
        self.results: list[DiagnosticResult] = []
        self.spyder_root = SPYDER_ROOT
        self.errors_found = []
        self.warnings_found = []
        self.modules_tested = 0
        self.modules_passed = 0

        print(f"{Colors.BOLD}{Colors.BLUE}")
        print("=" * 80)
        print("SPYDER SYSTEM DIAGNOSTIC & DEBUGGING TOOL")
        print("=" * 80)
        print(f"{Colors.NC}")
        print(f"Spyder Root: {self.spyder_root}")
        print(f"Python Version: {sys.version}")
        print(f"Diagnostic Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    def add_result(self, name: str, status: str, message: str = "", details: str = "", fix_suggestion: str = ""):
        """Add a diagnostic result"""
        result = DiagnosticResult(name, status, message, details, fix_suggestion)
        self.results.append(result)

        # Print immediate feedback
        status_color = {
            'PASS': Colors.GREEN,
            'FAIL': Colors.RED,
            'WARN': Colors.YELLOW,
            'SKIP': Colors.CYAN
        }.get(status, Colors.WHITE)

        status_symbol = {
            'PASS': '✓',
            'FAIL': '✗',
            'WARN': '⚠',
            'SKIP': '○'
        }.get(status, '?')

        print(f"{status_color}{status_symbol} {name}: {message}{Colors.NC}")
        if details:
            print(f"   Details: {details}")
        if fix_suggestion and status in ['FAIL', 'WARN']:
            print(f"   {Colors.YELLOW}Suggested Fix: {fix_suggestion}{Colors.NC}")

        if status == 'FAIL':
            self.errors_found.append(result)
        elif status == 'WARN':
            self.warnings_found.append(result)

    # ==========================================================================
    # BASIC SYSTEM CHECKS
    # ==========================================================================

    def test_python_environment(self):
        """Test Python environment and basic requirements"""
        print(f"\n{Colors.BOLD}1. PYTHON ENVIRONMENT CHECKS{Colors.NC}")
        print("-" * 40)

        # Python version
        self.add_result("Python Version", "PASS", f"{sys.version_info.major}.{sys.version_info.minor}")

        # Required packages
        required_packages = [
            ('sqlite3', 'Built-in SQLite support'),
            ('pathlib', 'Path handling'),
            ('json', 'JSON support'),
            ('datetime', 'Date/time handling'),
            ('threading', 'Threading support'),
            ('asyncio', 'Async support'),
            ('typing', 'Type hints'),
            ('uuid', 'UUID generation'),
            ('queue', 'Queue support'),
            ('collections', 'Collections'),
            ('enum', 'Enumerations'),
            ('dataclasses', 'Data classes'),
            ('weakref', 'Weak references')
        ]

        for package, description in required_packages:
            try:
                importlib.import_module(package)
                self.add_result(f"Package: {package}", "PASS", description)
            except ImportError:
                self.add_result(f"Package: {package}", "FAIL", "Not available",
                              fix_suggestion=f"Install or check {package} availability")

    def test_third_party_packages(self):
        """Test third-party package availability"""
        print(f"\n{Colors.BOLD}2. THIRD-PARTY PACKAGE CHECKS{Colors.NC}")
        print("-" * 40)

        third_party_packages = [
            ('PyQt6', 'GUI framework', 'pip install PyQt6'),
            ('PyQt6.QtWidgets', 'Qt Widgets', 'pip install PyQt6'),
            ('PyQt6.QtCore', 'Qt Core', 'pip install PyQt6'),
            ('PyQt6.QtGui', 'Qt GUI', 'pip install PyQt6'),
            ('pandas', 'Data analysis', 'pip install pandas'),
            ('numpy', 'Numerical computing', 'pip install numpy'),
            ('matplotlib', 'Plotting', 'pip install matplotlib'),
            ('requests', 'HTTP library', 'pip install requests'),
            ('websocket', 'WebSocket support', 'pip install websocket-client'),
            ('cryptography', 'Encryption', 'pip install cryptography'),
            ('yaml', 'YAML parsing', 'pip install PyYAML')
        ]

        for package, description, install_cmd in third_party_packages:
            try:
                importlib.import_module(package)
                self.add_result(f"Package: {package}", "PASS", description)
            except ImportError as e:
                self.add_result(f"Package: {package}", "FAIL", f"Import failed: {str(e)[:50]}",
                              fix_suggestion=install_cmd)

    def test_directory_structure(self):
        """Test Spyder directory structure"""
        print(f"\n{Colors.BOLD}3. DIRECTORY STRUCTURE CHECKS{Colors.NC}")
        print("-" * 40)

        expected_dirs = [
            ('SpyderA_Core', 'Core system modules'),
            ('SpyderB_Broker', 'Broker integration'),
            ('SpyderG_GUI', 'GUI components'),
            ('SpyderH_Storage', 'Data storage'),
            ('Spyder.SpyderU_Utilities', 'Utility modules'),
            ('SpyderE_Risk', 'Risk management'),
            ('logs', 'Log files'),
            ('.spyder', 'Configuration directory (in home)')
        ]

        for dir_name, description in expected_dirs:
            if dir_name == '.spyder':
                dir_path = Path.home() / dir_name
            else:
                dir_path = self.spyder_root / dir_name

            if dir_path.exists():
                self.add_result(f"Directory: {dir_name}", "PASS", description)
            else:
                self.add_result(f"Directory: {dir_name}", "FAIL", "Missing",
                              fix_suggestion=f"Create directory: {dir_path}")

    def test_configuration_files(self):
        """Test configuration file availability"""
        print(f"\n{Colors.BOLD}4. CONFIGURATION FILE CHECKS{Colors.NC}")
        print("-" * 40)

        config_files = [
            (Path.home() / '.spyder' / 'config.yaml', 'Main configuration'),
            (Path.home() / '.spyder' / 'data', 'Data directory'),
            (self.spyder_root / 'launch_spyder_wayland.sh', 'Launch script')
        ]

        for file_path, description in config_files:
            if file_path.exists():
                self.add_result(f"Config: {file_path.name}", "PASS", description)
            else:
                self.add_result(f"Config: {file_path.name}", "WARN", "Missing but will use defaults",
                              fix_suggestion=f"Create: {file_path}")

    # ==========================================================================
    # MODULE IMPORT CHECKS
    # ==========================================================================

    def test_core_modules(self):
        """Test core Spyder modules"""
        print(f"\n{Colors.BOLD}5. CORE MODULE IMPORT CHECKS{Colors.NC}")
        print("-" * 40)

        core_modules = [
            ('SpyderA_Core.SpyderA01_Main', 'Main application entry point'),
            ('SpyderA_Core.SpyderA03_Configuration', 'Configuration manager'),
            ('SpyderA_Core.SpyderA05_EventManager', 'Event management system'),
            ('Spyder.SpyderU_Utilities.SpyderU01_Logger', 'Logging system'),
            ('Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler', 'Error handling'),
            ('Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar', 'Trading calendar'),
            ('SpyderH_Storage.SpyderH01_DataAccessLayer', 'Database access'),
            ('SpyderE_Risk.SpyderE01_RiskManager', 'Risk management'),
            ('SpyderE_Risk.SpyderE02_PositionSizer', 'Position sizing')
        ]

        for module_name, description in core_modules:
            self.modules_tested += 1
            try:
                importlib.import_module(module_name)
                self.add_result(f"Module: {module_name.split('.')[-1]}", "PASS", description)
                self.modules_passed += 1
            except ImportError as e:
                self.add_result(f"Module: {module_name.split('.')[-1]}", "FAIL",
                              f"Import failed: {str(e)[:50]}",
                              details=str(e),
                              fix_suggestion=f"Check if {module_name.replace('.', '/')} exists and has correct imports")
            except Exception as e:
                self.add_result(f"Module: {module_name.split('.')[-1]}", "FAIL",
                              f"Error: {str(e)[:50]}",
                              details=str(e))

    def test_gui_modules(self):
        """Test GUI modules"""
        print(f"\n{Colors.BOLD}6. GUI MODULE IMPORT CHECKS{Colors.NC}")
        print("-" * 40)

        gui_modules = [
            ('SpyderG_GUI.SpyderG01_MainWindow', 'Main window'),
            ('SpyderG_GUI.SpyderG05_TradingDashboard', 'Trading dashboard'),
            ('SpyderG_GUI.SpyderG06_SignalInfoDialog', 'Signal info dialog'),
            ('SpyderG_GUI.SpyderG07_RiskParametersDialog', 'Risk parameters dialog')
        ]

        for module_name, description in gui_modules:
            self.modules_tested += 1
            try:
                importlib.import_module(module_name)
                self.add_result(f"GUI Module: {module_name.split('.')[-1]}", "PASS", description)
                self.modules_passed += 1
            except ImportError as e:
                self.add_result(f"GUI Module: {module_name.split('.')[-1]}", "FAIL",
                              f"Import failed: {str(e)[:50]}",
                              details=str(e),
                              fix_suggestion=f"Check GUI module {module_name}")
            except Exception as e:
                self.add_result(f"GUI Module: {module_name.split('.')[-1]}", "FAIL",
                              f"Error: {str(e)[:50]}",
                              details=str(e))

    def test_broker_modules(self):
        """Test broker modules"""
        print(f"\n{Colors.BOLD}7. BROKER MODULE IMPORT CHECKS{Colors.NC}")
        print("-" * 40)

        broker_modules = [
            ('SpyderB_Broker.SpyderB01_BrokerClient', 'Broker client'),
            ('SpyderB_Broker.SpyderB02_MarketData', 'Market data'),
            ('SpyderB_Broker.SpyderB03_OrderManagement', 'Order management'),
            ('SpyderB_Broker.SpyderB04_AccountManager', 'Account manager'),
            ('SpyderB_Broker.SpyderB05_PositionManager', 'Position manager')
        ]

        for module_name, description in broker_modules:
            self.modules_tested += 1
            try:
                importlib.import_module(module_name)
                self.add_result(f"Broker Module: {module_name.split('.')[-1]}", "PASS", description)
                self.modules_passed += 1
            except ImportError as e:
                self.add_result(f"Broker Module: {module_name.split('.')[-1]}", "WARN",
                              f"Import failed: {str(e)[:50]}",
                              details=str(e),
                              fix_suggestion=f"Check broker module {module_name} or run in simulation mode")
            except Exception as e:
                self.add_result(f"Broker Module: {module_name.split('.')[-1]}", "WARN",
                              f"Error: {str(e)[:50]}",
                              details=str(e))

    # ==========================================================================
    # COMPONENT INITIALIZATION TESTS
    # ==========================================================================

    def test_event_manager_initialization(self):
        """Test EventManager initialization"""
        print(f"\n{Colors.BOLD}8. EVENT MANAGER INITIALIZATION{Colors.NC}")
        print("-" * 40)

        try:
            from SpyderA_Core.SpyderA05_EventManager import EventManager, EventType

            # Test creation
            em = EventManager(persist_events=False)
            self.add_result("EventManager Creation", "PASS", "Created successfully")

            # Test start
            if hasattr(em, 'start') and callable(em.start):
                if em.start():
                    self.add_result("EventManager Start", "PASS", "Started successfully")

                    # Test event emission
                    if hasattr(em, 'emit') and callable(em.emit):
                        em.emit(EventType.SYSTEM, {"test": "data"})
                        self.add_result("EventManager Emit", "PASS", "Event emitted successfully")
                    else:
                        self.add_result("EventManager Emit", "FAIL", "emit method missing")

                    # Test stop
                    if hasattr(em, 'stop') and callable(em.stop):
                        if em.stop():
                            self.add_result("EventManager Stop", "PASS", "Stopped successfully")
                        else:
                            self.add_result("EventManager Stop", "WARN", "Stop returned False")
                    else:
                        self.add_result("EventManager Stop", "FAIL", "stop method missing")
                else:
                    self.add_result("EventManager Start", "FAIL", "Start returned False")
            else:
                self.add_result("EventManager Start", "FAIL", "start method missing",
                              fix_suggestion="Add start() method to EventManager class")

        except Exception as e:
            self.add_result("EventManager Initialization", "FAIL", f"Error: {str(e)[:50]}",
                          details=traceback.format_exc(),
                          fix_suggestion="Fix EventManager implementation")

    def test_database_initialization(self):
        """Test database initialization"""
        print(f"\n{Colors.BOLD}9. DATABASE INITIALIZATION{Colors.NC}")
        print("-" * 40)

        try:
            from SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer

            # Test database connection
            db_path = Path.home() / '.spyder' / 'data' / 'test_spyder.db'
            db_path.parent.mkdir(parents=True, exist_ok=True)

            DataAccessLayer(str(db_path))
            self.add_result("Database Connection", "PASS", f"Connected to {db_path.name}")

            # Test basic operations
            try:
                # Simple test query
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                conn.close()
                self.add_result("Database Query", "PASS", "Basic query successful")
            except Exception as e:
                self.add_result("Database Query", "FAIL", f"Query failed: {str(e)[:50]}")

        except Exception as e:
            self.add_result("Database Initialization", "FAIL", f"Error: {str(e)[:50]}",
                          details=traceback.format_exc(),
                          fix_suggestion="Check SpyderH01_DataAccessLayer implementation")

    def test_configuration_initialization(self):
        """Test configuration system"""
        print(f"\n{Colors.BOLD}10. CONFIGURATION SYSTEM{Colors.NC}")
        print("-" * 40)

        try:
            from SpyderA_Core.SpyderA03_Configuration import ConfigManager

            config = ConfigManager()
            self.add_result("ConfigManager Creation", "PASS", "Created successfully")

            # Test basic configuration access
            if hasattr(config, 'get'):
                config.get('test_key', 'default_value')
                self.add_result("Config Get Method", "PASS", "get() method works")
            else:
                self.add_result("Config Get Method", "FAIL", "get() method missing",
                              fix_suggestion="Add get() method to ConfigManager")

        except Exception as e:
            self.add_result("Configuration Initialization", "FAIL", f"Error: {str(e)[:50]}",
                          details=traceback.format_exc())

    def test_gui_component_creation(self):
        """Test GUI component creation"""
        print(f"\n{Colors.BOLD}11. GUI COMPONENT TESTING{Colors.NC}")
        print("-" * 40)

        try:
            from PySide6.QtWidgets import QApplication

            # Create QApplication if it doesn't exist
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
                self.add_result("QApplication Creation", "PASS", "Created successfully")
            else:
                self.add_result("QApplication Exists", "PASS", "Already exists")

            # Test main window import
            try:
                from SpyderG_GUI.SpyderG01_MainWindow import MainWindow
                self.add_result("MainWindow Import", "PASS", "Imported successfully")

                # Test MainWindow creation (without showing)
                try:
                    MainWindow()
                    self.add_result("MainWindow Creation", "PASS", "Created successfully")
                except Exception as e:
                    self.add_result("MainWindow Creation", "FAIL", f"Creation failed: {str(e)[:50]}",
                                  details=str(e))
            except ImportError as e:
                self.add_result("MainWindow Import", "FAIL", f"Import failed: {str(e)[:50]}")

            # Test trading dashboard import
            try:
                from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
                self.add_result("TradingDashboard Import", "PASS", "Imported successfully")

                # Test TradingDashboard creation (this is where the error occurs)
                try:
                    # Check constructor signature
                    import inspect
                    sig = inspect.signature(SpyderTradingDashboard.__init__)
                    params = list(sig.parameters.keys())
                    self.add_result("TradingDashboard Signature", "PASS",
                                  f"Parameters: {params}",
                                  details=f"Full signature: {sig}")

                    # Try creating with no arguments (besides self)
                    SpyderTradingDashboard()
                    self.add_result("TradingDashboard Creation", "PASS", "Created successfully")

                except TypeError as te:
                    self.add_result("TradingDashboard Creation", "FAIL",
                                  f"Constructor error: {str(te)}",
                                  details=str(te),
                                  fix_suggestion="Fix SpyderTradingDashboard.__init__() to accept correct parameters")
                except Exception as e:
                    self.add_result("TradingDashboard Creation", "FAIL",
                                  f"Creation failed: {str(e)[:50]}",
                                  details=str(e))

            except ImportError as e:
                self.add_result("TradingDashboard Import", "FAIL", f"Import failed: {str(e)[:50]}")

        except Exception as e:
            self.add_result("GUI Testing", "FAIL", f"Error: {str(e)[:50]}",
                          details=traceback.format_exc())

    # ==========================================================================
    # INTEGRATION TESTS
    # ==========================================================================

    def test_minimal_system_startup(self):
        """Test minimal system startup sequence"""
        print(f"\n{Colors.BOLD}12. MINIMAL SYSTEM STARTUP TEST{Colors.NC}")
        print("-" * 40)

        try:
            # Step 1: Create EventManager
            from SpyderA_Core.SpyderA05_EventManager import EventManager
            em = EventManager(persist_events=False)

            if hasattr(em, 'start') and em.start():
                self.add_result("Step 1: EventManager", "PASS", "Started successfully")
            else:
                self.add_result("Step 1: EventManager", "FAIL", "Failed to start")
                return

            # Step 2: Create Configuration
            from SpyderA_Core.SpyderA03_Configuration import ConfigManager
            ConfigManager()
            self.add_result("Step 2: Configuration", "PASS", "Created successfully")

            # Step 3: Create Database
            from SpyderH_Storage.SpyderH01_DataAccessLayer import DataAccessLayer
            db_path = Path.home() / '.spyder' / 'data' / 'test_spyder.db'
            db_path.parent.mkdir(parents=True, exist_ok=True)
            DataAccessLayer(str(db_path))
            self.add_result("Step 3: Database", "PASS", "Connected successfully")

            # Step 4: Test Trading Calendar
            try:
                from Spyder.SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar
                TradingCalendar()
                self.add_result("Step 4: TradingCalendar", "PASS", "Created successfully")
            except Exception as e:
                self.add_result("Step 4: TradingCalendar", "FAIL", f"Error: {str(e)[:50]}")

            # Step 5: Test Risk Manager
            try:
                from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
                RiskManager(event_manager=em, config={'portfolio_value': 100000})
                self.add_result("Step 5: RiskManager", "PASS", "Created successfully")
            except Exception as e:
                self.add_result("Step 5: RiskManager", "FAIL", f"Error: {str(e)[:50]}",
                              details=str(e))

            # Cleanup
            if hasattr(em, 'stop'):
                em.stop()

        except Exception as e:
            self.add_result("Minimal System Startup", "FAIL", f"Error: {str(e)[:50]}",
                          details=traceback.format_exc())

    # ==========================================================================
    # REPORTING
    # ==========================================================================

    def generate_report(self):
        """Generate comprehensive diagnostic report"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}")
        print("=" * 80)
        print("DIAGNOSTIC REPORT SUMMARY")
        print("=" * 80)
        print(f"{Colors.NC}")

        # Statistics
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.status == 'PASS'])
        failed_tests = len([r for r in self.results if r.status == 'FAIL'])
        warning_tests = len([r for r in self.results if r.status == 'WARN'])
        skipped_tests = len([r for r in self.results if r.status == 'SKIP'])

        print(f"Total Tests: {total_tests}")
        print(f"{Colors.GREEN}Passed: {passed_tests}{Colors.NC}")
        print(f"{Colors.RED}Failed: {failed_tests}{Colors.NC}")
        print(f"{Colors.YELLOW}Warnings: {warning_tests}{Colors.NC}")
        print(f"{Colors.CYAN}Skipped: {skipped_tests}{Colors.NC}")

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"Success Rate: {success_rate:.1f}%")

        if self.modules_tested > 0:
            module_success_rate = (self.modules_passed / self.modules_tested * 100)
            print(f"Module Import Success Rate: {module_success_rate:.1f}%")

        # Critical errors
        if self.errors_found:
            print(f"\n{Colors.RED}{Colors.BOLD}CRITICAL ERRORS TO FIX:{Colors.NC}")
            for i, error in enumerate(self.errors_found[:5], 1):  # Show top 5
                print(f"{i}. {error.name}: {error.message}")
                if error.fix_suggestion:
                    print(f"   → {error.fix_suggestion}")

        # Warnings
        if self.warnings_found:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}WARNINGS:{Colors.NC}")
            for i, warning in enumerate(self.warnings_found[:3], 1):  # Show top 3
                print(f"{i}. {warning.name}: {warning.message}")

        # Next steps
        print(f"\n{Colors.BOLD}RECOMMENDED NEXT STEPS:{Colors.NC}")
        if failed_tests == 0:
            print("🎉 All critical tests passed! System should be ready to launch.")
        else:
            print("1. Fix the critical errors listed above")
            print("2. Re-run this diagnostic script")
            print("3. Focus on EventManager, RiskManager, and GUI initialization issues")
            print("4. Check missing modules in SpyderH_Storage and SpyderB_Broker series")

        # Save report to file
        self.save_report_to_file()

        return failed_tests == 0

    def save_report_to_file(self):
        """Save diagnostic report to file"""
        try:
            report_file = self.spyder_root / "logs" / f"diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            report_file.parent.mkdir(exist_ok=True)

            report_data = {
                'timestamp': datetime.now().isoformat(),
                'spyder_root': str(self.spyder_root),
                'python_version': sys.version,
                'total_tests': len(self.results),
                'passed_tests': len([r for r in self.results if r.status == 'PASS']),
                'failed_tests': len([r for r in self.results if r.status == 'FAIL']),
                'warning_tests': len([r for r in self.results if r.status == 'WARN']),
                'results': [
                    {
                        'name': r.name,
                        'status': r.status,
                        'message': r.message,
                        'details': r.details,
                        'fix_suggestion': r.fix_suggestion,
                        'timestamp': r.timestamp.isoformat()
                    }
                    for r in self.results
                ]
            }

            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)

            print(f"\nDetailed report saved to: {report_file}")

        except Exception as e:
            print(f"Warning: Could not save report to file: {e}")

    # ==========================================================================
    # MAIN EXECUTION
    # ==========================================================================

    def run_full_diagnostic(self):
        """Run complete diagnostic suite"""
        try:
            self.test_python_environment()
            self.test_third_party_packages()
            self.test_directory_structure()
            self.test_configuration_files()
            self.test_core_modules()
            self.test_gui_modules()
            self.test_broker_modules()
            self.test_event_manager_initialization()
            self.test_database_initialization()
            self.test_configuration_initialization()
            self.test_gui_component_creation()
            self.test_minimal_system_startup()

            return self.generate_report()

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Diagnostic interrupted by user{Colors.NC}")
            return False
        except Exception as e:
            print(f"\n{Colors.RED}Diagnostic failed with error: {e}{Colors.NC}")
            print(traceback.format_exc())
            return False

def main():
    """Main execution function"""
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()

        diagnostic = SpyderDiagnostic()

        if test_type == "quick":
            print("Running quick diagnostic (core modules only)...")
            diagnostic.test_python_environment()
            diagnostic.test_core_modules()
            diagnostic.test_event_manager_initialization()
            return diagnostic.generate_report()

        elif test_type == "gui":
            print("Running GUI-specific diagnostic...")
            diagnostic.test_third_party_packages()
            diagnostic.test_gui_modules()
            diagnostic.test_gui_component_creation()
            return diagnostic.generate_report()

        elif test_type == "modules":
            print("Running module import diagnostic...")
            diagnostic.test_core_modules()
            diagnostic.test_gui_modules()
            diagnostic.test_broker_modules()
            return diagnostic.generate_report()

        else:
            print(f"Unknown test type: {test_type}")
            print("Available options: quick, gui, modules, or run without arguments for full diagnostic")
            return False
    else:
        # Full diagnostic
        diagnostic = SpyderDiagnostic()
        return diagnostic.run_full_diagnostic()

if __name__ == "__main__":
    print("Starting Spyder System Diagnostic...")
    success = main()

    if success:
        print(f"\n{Colors.GREEN}✅ Diagnostic completed successfully - System appears ready!{Colors.NC}")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}❌ Diagnostic found critical issues - Please fix before launching{Colors.NC}")
        sys.exit(1)
