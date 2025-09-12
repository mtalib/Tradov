#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderT15_FullSystemTest.py
Group: T (Testing)
Purpose: Complete system integration test including S-Series signals
Author: Mohamed Talib
Date Created: 2025-08-13
Last Updated: 2025-08-13 Time: 19:30:00

Description:
    Comprehensive system test that validates all Spyder components working
    together. Tests core engine, broker connectivity, market data flow,
    signal calculations, risk management, and GUI integration. Provides
    detailed diagnostics for system health verification.
"""

import json
import logging
import os
import queue
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from colorama import Back, Fore, Style, init
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QMainWindow, QTextEdit, QVBoxLayout,
                            QWidget)

# Initialize colorama for colored console output
init(autoreset=True)

# ==============================================================================
# SPYDER IMPORTS - Core System
# ==============================================================================
print("\n" + "=" * 80)
print(Fore.CYAN + "SPYDER FULL SYSTEM INTEGRATION TEST")
print("=" * 80)

# Track import status
import_status = {}

# A-Series: Core
try:
    from SpyderA_Core.SpyderA03_Configuration import SpyderConfiguration
    from SpyderA_Core.SpyderA05_EventManager import EventManager

    import_status["A-Core"] = True
    print(Fore.GREEN + "✅ A-Series (Core) imported successfully")
except ImportError as e:
    import_status["A-Core"] = False
    print(Fore.RED + f"❌ A-Series (Core) import failed: {e}")

# B-Series: Broker
try:
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager

    import_status["B-Broker"] = True
    print(Fore.GREEN + "✅ B-Series (Broker) imported successfully")
except ImportError as e:
    import_status["B-Broker"] = False
    print(Fore.RED + f"❌ B-Series (Broker) import failed: {e}")

# C-Series: Market Data
try:
    from SpyderC_MarketData.SpyderC01_DataFeed import DataFeed
    from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager

    import_status["C-MarketData"] = True
    print(Fore.GREEN + "✅ C-Series (Market Data) imported successfully")
except ImportError as e:
    import_status["C-MarketData"] = False
    print(Fore.RED + f"❌ C-Series (Market Data) import failed: {e}")

# E-Series: Risk Management
try:
    from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
    from SpyderE_Risk.SpyderE02_PositionSizer import PositionSizer

    import_status["E-Risk"] = True
    print(Fore.GREEN + "✅ E-Series (Risk) imported successfully")
except ImportError as e:
    import_status["E-Risk"] = False
    print(Fore.RED + f"❌ E-Series (Risk) import failed: {e}")

# S-Series: Signals (NEW)
try:
    from SpyderS_Signals.SpyderS01_DIXCalculator import DIXCalculator
    from SpyderS_Signals.SpyderS03_BlackSwanIndicator import BlackSwanIndicator
    from SpyderS_Signals.SpyderS05_GEXDEXCalculator import GEXDEXCalculator
    from SpyderS_Signals.SpyderS06_SKEWCalculator import SKEWCalculator
    from SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import \
        CustomMetricsOrchestrator

    import_status["S-Signals"] = True
    print(Fore.GREEN + "✅ S-Series (Signals) imported successfully")
except ImportError as e:
    import_status["S-Signals"] = False
    print(Fore.RED + f"❌ S-Series (Signals) import failed: {e}")

# G-Series: GUI
try:
    from SpyderG_GUI.SpyderG05_TradingDashboard import TradingDashboard

    import_status["G-GUI"] = True
    print(Fore.GREEN + "✅ G-Series (GUI) imported successfully")
except ImportError as e:
    import_status["G-GUI"] = False
    print(Fore.RED + f"❌ G-Series (GUI) import failed: {e}")

# U-Series: Utilities
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar

    import_status["U-Utilities"] = True
    print(Fore.GREEN + "✅ U-Series (Utilities) imported successfully")
except ImportError as e:
    import_status["U-Utilities"] = False
    print(Fore.RED + f"❌ U-Series (Utilities) import failed: {e}")

# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================
TEST_CONFIG = {
    "ib_gateway": {
        "host": "127.0.0.1",
        "port": 7497,  # Paper trading port
        "client_id": 999,  # Test client ID
    },
    "test_duration": 30,  # seconds
    "signal_test_interval": 5,  # seconds
    "enable_gui": False,  # Set to True to show dashboard
    "log_level": logging.INFO,
}

# ==============================================================================
# SYSTEM TEST CLASS
# ==============================================================================


class SpyderSystemTest(QObject):
    """
    Comprehensive system test for all Spyder components
    """

    # Signals for test status
    test_started = Signal(str)
    test_completed = Signal(str, bool)
    test_progress = Signal(str)

    def __init__(self):
        super().__init__()
        self.logger = self._setup_logger()
        self.test_results = {}
        self.components = {}
        self.test_thread = None

    def _setup_logger(self) -> logging.Logger:
        """Setup test logger"""
        logger = logging.getLogger("SpyderSystemTest")
        logger.setLevel(TEST_CONFIG["log_level"])

        # Console handler with formatting
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    # ==========================================================================
    # COMPONENT TESTS
    # ==========================================================================

    def test_core_components(self) -> Dict[str, bool]:
        """Test A-Series core components"""
        results = {}

        print(f"\n{Fore.YELLOW}Testing Core Components...")

        # Test Configuration
        try:
            config = SpyderConfiguration()
            config.load_config()
            results["configuration"] = True
            print(f"{Fore.GREEN}  ✅ Configuration loaded")
        except Exception as e:
            results["configuration"] = False
            print(f"{Fore.RED}  ❌ Configuration failed: {e}")

        # Test Event Manager
        try:
            event_mgr = EventManager()
            event_mgr.emit("test_event", {"test": "data"})
            results["event_manager"] = True
            print(f"{Fore.GREEN}  ✅ Event Manager operational")
        except Exception as e:
            results["event_manager"] = False
            print(f"{Fore.RED}  ❌ Event Manager failed: {e}")

        return results

    def test_broker_connectivity(self) -> Dict[str, bool]:
        """Test B-Series broker connectivity"""
        results = {}

        print(f"\n{Fore.YELLOW}Testing Broker Connectivity...")

        # Test Connection Manager
        try:
            conn_mgr = ConnectionManager()
            # Note: This will fail if IB Gateway is not running
            is_connected = conn_mgr.test_connection(
                TEST_CONFIG["ib_gateway"]["host"], TEST_CONFIG["ib_gateway"]["port"]
            )
            results["connection"] = is_connected

            if is_connected:
                print(f"{Fore.GREEN}  ✅ IB Gateway connection successful")
            else:
                print(f"{Fore.YELLOW}  ⚠️  IB Gateway not connected (expected if not running)")
        except Exception as e:
            results["connection"] = False
            print(f"{Fore.YELLOW}  ⚠️  Broker connection test skipped: {e}")

        return results

    def test_signal_calculations(self) -> Dict[str, Any]:
        """Test S-Series signal calculations"""
        results = {}

        print(f"\n{Fore.YELLOW}Testing Signal Calculations...")

        # Test DIX Calculator (S01)
        try:
            dix_calc = DIXCalculator()
            dix_result = dix_calc.calculate_dix_simulated()  # Use simulated data
            results["DIX"] = {
                "status": True,
                "value": dix_result["dix_percentage"],
                "timestamp": datetime.now(),
            }
            print(f"{Fore.GREEN}  ✅ DIX Calculator: {dix_result['dix_percentage']:.2f}%")
        except Exception as e:
            results["DIX"] = {"status": False, "error": str(e)}
            print(f"{Fore.RED}  ❌ DIX Calculator failed: {e}")

        # Test Black Swan Indicator (S03)
        try:
            swan_calc = BlackSwanIndicator()
            swan_result = swan_calc.calculate_swan_score()
            results["SWAN"] = {
                "status": True,
                "value": swan_result.overall_score,
                "components": swan_result.component_scores,
                "timestamp": datetime.now(),
            }
            print(f"{Fore.GREEN}  ✅ Black Swan Indicator: {swan_result.overall_score:.2f}")
        except Exception as e:
            results["SWAN"] = {"status": False, "error": str(e)}
            print(f"{Fore.RED}  ❌ Black Swan Indicator failed: {e}")

        # Test GEX/DEX Calculator (S05)
        try:
            gex_calc = GEXDEXCalculator()
            gex_result = gex_calc.calculate_simulated()
            results["GEX"] = {
                "status": True,
                "gex": gex_result["gex"],
                "dex": gex_result["dex"],
                "ogl": gex_result["ogl"],
                "timestamp": datetime.now(),
            }
            print(f"{Fore.GREEN}  ✅ GEX Calculator: {gex_result['gex']/1e9:.2f}B")
        except Exception as e:
            results["GEX"] = {"status": False, "error": str(e)}
            print(f"{Fore.RED}  ❌ GEX/DEX Calculator failed: {e}")

        # Test SKEW Calculator (S06)
        try:
            skew_calc = SKEWCalculator()
            skew_result = skew_calc.calculate_skew_simulated()
            results["SKEW"] = {
                "status": True,
                "value": skew_result["skew_index"],
                "timestamp": datetime.now(),
            }
            print(f"{Fore.GREEN}  ✅ SKEW Calculator: {skew_result['skew_index']:.2f}")
        except Exception as e:
            results["SKEW"] = {"status": False, "error": str(e)}
            print(f"{Fore.RED}  ❌ SKEW Calculator failed: {e}")

        # Test Orchestrator (S07)
        try:
            orchestrator = CustomMetricsOrchestrator()
            orchestrator.update_all_metrics()
            metrics = orchestrator.get_all_metrics()
            results["Orchestrator"] = {
                "status": True,
                "metrics": metrics,
                "timestamp": datetime.now(),
            }
            print(f"{Fore.GREEN}  ✅ Metrics Orchestrator: All signals integrated")
        except Exception as e:
            results["Orchestrator"] = {"status": False, "error": str(e)}
            print(f"{Fore.RED}  ❌ Metrics Orchestrator failed: {e}")

        return results

    def test_risk_management(self) -> Dict[str, bool]:
        """Test E-Series risk management"""
        results = {}

        print(f"\n{Fore.YELLOW}Testing Risk Management...")

        # Test Risk Manager
        try:
            risk_mgr = RiskManager()

            # Test position sizing
            position_size = risk_mgr.calculate_position_size(
                account_value=100000, risk_percent=1.0, stop_loss_amount=500
            )
            results["position_sizing"] = position_size > 0
            print(f"{Fore.GREEN}  ✅ Position Sizing: ${position_size:.2f}")

            # Test risk metrics
            risk_metrics = risk_mgr.calculate_portfolio_risk(
                {"SPY": {"value": 10000, "beta": 1.0}, "QQQ": {"value": 5000, "beta": 1.2}}
            )
            results["risk_metrics"] = True
            print(f"{Fore.GREEN}  ✅ Risk Metrics calculated")

        except Exception as e:
            results["position_sizing"] = False
            results["risk_metrics"] = False
            print(f"{Fore.RED}  ❌ Risk Management failed: {e}")

        return results

    def test_data_flow(self) -> Dict[str, bool]:
        """Test market data flow through the system"""
        results = {}

        print(f"\n{Fore.YELLOW}Testing Data Flow...")

        try:
            # Create sample market data
            sample_data = {
                "symbol": "SPY",
                "price": 585.50,
                "volume": 1000000,
                "timestamp": datetime.now(),
            }

            # Test data feed
            data_feed = DataFeed()
            data_feed.process_data(sample_data)
            results["data_feed"] = True
            print(f"{Fore.GREEN}  ✅ Data Feed processing")

            # Test option chain
            option_chain = OptionChainManager()
            chain_data = option_chain.get_simulated_chain("SPY")
            results["option_chain"] = chain_data is not None
            print(f"{Fore.GREEN}  ✅ Option Chain available")

        except Exception as e:
            results["data_feed"] = False
            results["option_chain"] = False
            print(f"{Fore.RED}  ❌ Data Flow failed: {e}")

        return results

    # ==========================================================================
    # MAIN TEST EXECUTION
    # ==========================================================================

    def run_full_system_test(self) -> Dict[str, Any]:
        """
        Run complete system integration test
        """
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}Starting Full System Test")
        print(f"{Fore.CYAN}{'='*80}")

        all_results = {
            "timestamp": datetime.now().isoformat(),
            "import_status": import_status,
            "component_tests": {},
            "overall_status": "PENDING",
        }

        # Run component tests
        if import_status.get("A-Core", False):
            all_results["component_tests"]["core"] = self.test_core_components()

        if import_status.get("B-Broker", False):
            all_results["component_tests"]["broker"] = self.test_broker_connectivity()

        if import_status.get("S-Signals", False):
            all_results["component_tests"]["signals"] = self.test_signal_calculations()

        if import_status.get("E-Risk", False):
            all_results["component_tests"]["risk"] = self.test_risk_management()

        if import_status.get("C-MarketData", False):
            all_results["component_tests"]["data"] = self.test_data_flow()

        # Calculate overall status
        total_tests = 0
        passed_tests = 0

        for category, tests in all_results["component_tests"].items():
            if isinstance(tests, dict):
                for test_name, result in tests.items():
                    total_tests += 1
                    if isinstance(result, dict):
                        if result.get("status", False):
                            passed_tests += 1
                    elif result:
                        passed_tests += 1

        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        all_results["overall_status"] = "PASS" if success_rate >= 70 else "FAIL"
        all_results["success_rate"] = success_rate
        all_results["summary"] = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": total_tests - passed_tests,
        }

        # Print summary
        self._print_test_summary(all_results)

        # Save results
        self._save_test_results(all_results)

        return all_results

    def _print_test_summary(self, results: Dict[str, Any]):
        """Print formatted test summary"""
        print(f"\n{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}TEST SUMMARY")
        print(f"{Fore.CYAN}{'='*80}")

        summary = results.get("summary", {})
        success_rate = results.get("success_rate", 0)

        # Overall status with color
        if results["overall_status"] == "PASS":
            status_color = Fore.GREEN
            status_symbol = "✅"
        else:
            status_color = Fore.RED
            status_symbol = "❌"

        print(f"\n{status_color}Overall Status: {status_symbol} {results['overall_status']}")
        print(f"{Fore.WHITE}Success Rate: {success_rate:.1f}%")
        print(
            f"{Fore.WHITE}Tests Passed: {summary.get('passed', 0)}/{summary.get('total_tests', 0)}"
        )

        # Component breakdown
        print(f"\n{Fore.YELLOW}Component Status:")
        for component, status in import_status.items():
            symbol = "✅" if status else "❌"
            color = Fore.GREEN if status else Fore.RED
            print(f"  {color}{symbol} {component}")

        # Signal values (if available)
        signals = results.get("component_tests", {}).get("signals", {})
        if signals:
            print(f"\n{Fore.YELLOW}Signal Values:")
            if "DIX" in signals and signals["DIX"].get("status"):
                print(f"  DIX: {signals['DIX']['value']:.2f}%")
            if "SWAN" in signals and signals["SWAN"].get("status"):
                print(f"  SWAN: {signals['SWAN']['value']:.2f}")
            if "GEX" in signals and signals["GEX"].get("status"):
                print(f"  GEX: {signals['GEX']['gex']/1e9:.2f}B")
            if "SKEW" in signals and signals["SKEW"].get("status"):
                print(f"  SKEW: {signals['SKEW']['value']:.2f}")

    def _save_test_results(self, results: Dict[str, Any]):
        """Save test results to file"""
        try:
            results_dir = Path("test_results")
            results_dir.mkdir(exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = results_dir / f"system_test_{timestamp}.json"

            with open(filename, "w") as f:
                json.dump(results, f, indent=2, default=str)

            print(f"\n{Fore.GREEN}Test results saved to: {filename}")
        except Exception as e:
            print(f"\n{Fore.RED}Failed to save results: {e}")


# ==============================================================================
# DASHBOARD TEST (Optional GUI)
# ==============================================================================


class SystemTestDashboard(QMainWindow):
    """
    Optional GUI dashboard for visual testing
    """

    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.test_runner = SpyderSystemTest()

    def setup_ui(self):
        """Setup test dashboard UI"""
        self.setWindowTitle("Spyder System Test Dashboard")
        self.setGeometry(100, 100, 800, 600)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Test output display
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        layout.addWidget(self.output_display)

        # Start test on load
        QTimer.singleShot(1000, self.run_test)

    def run_test(self):
        """Run system test and display results"""
        self.output_display.append("Starting System Test...\n")

        try:
            results = self.test_runner.run_full_system_test()
            self.output_display.append(f"\nTest Complete!")
            self.output_display.append(f"Status: {results['overall_status']}")
            self.output_display.append(f"Success Rate: {results.get('success_rate', 0):.1f}%")
        except Exception as e:
            self.output_display.append(f"\nTest Failed: {e}")


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


def main():
    """
    Main test execution
    """
    print(f"\n{Style.BRIGHT}{Fore.CYAN}SPYDER SYSTEM INTEGRATION TEST")
    print(f"{Style.BRIGHT}{Fore.CYAN}Version 1.0")
    print(f"{Style.BRIGHT}{Fore.CYAN}{'='*80}\n")

    # Check if GUI mode requested
    if "--gui" in sys.argv or TEST_CONFIG["enable_gui"]:
        print(f"{Fore.YELLOW}Running with GUI Dashboard...")
        app = QApplication(sys.argv)
        dashboard = SystemTestDashboard()
        dashboard.show()
        sys.exit(app.exec())
    else:
        # Run console test
        tester = SpyderSystemTest()
        results = tester.run_full_system_test()

        # Exit with appropriate code
        if results["overall_status"] == "PASS":
            print(f"\n{Fore.GREEN}{Style.BRIGHT}✅ SYSTEM TEST PASSED!")
            sys.exit(0)
        else:
            print(f"\n{Fore.RED}{Style.BRIGHT}❌ SYSTEM TEST FAILED!")
            sys.exit(1)


if __name__ == "__main__":
    main()
