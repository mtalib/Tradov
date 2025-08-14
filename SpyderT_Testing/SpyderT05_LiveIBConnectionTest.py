#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Spyder Version: 1.0
Module: SpyderT05_LiveIBConnectionTest.py
Group: T (Testing)
Purpose: Live IB Connection and Market Data Subscription Testing
Author: Mohamed Talib
Date Created: 2025-01-15
Last Updated: 2025-01-15 Time: 13:00:00

Description:
    This module provides comprehensive testing for Interactive Brokers (IB)
    market data subscriptions and connectivity. It validates that all required
    symbols have proper market data access, identifies missing subscriptions,
    and tests SPY options chain availability. The test covers both visible
    dashboard symbols and hidden backend symbols used by the trading system.

"""

import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

from SpyderB_Broker.SpyderB01_SpyderClient import IBConfig, SpyderClient
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ==============================================================================
# CONSTANTS
# ==============================================================================
# Test configuration
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4002  # IB Gateway Paper Trading port
DEFAULT_CLIENT_ID = 999
CONNECTION_TIMEOUT = 30
DATA_WAIT_TIMEOUT = 10
REQUEST_DELAY = 0.5  # Delay between symbol requests

# Symbol categories - includes ALL dashboard AND hidden backend symbols
VISIBLE_SYMBOLS = {
    "S&P CORE": ["SPY", "SPX", "/ES"],
    "VOLATILITY": ["VIX", "VIX9D", "VXV", "VXMT", "VVIX", "UVXY"],
    "MARKET INTERNALS": ["TICK-NYSE", "TRIN-NYSE", "ADD-NYSE", "CPC", "PCALL", "SKEW"],
    "MAJOR INDICES": ["DIA", "QQQ", "IWM"],
    "BONDS & CREDIT": ["TLT", "LQD"],
    "CORRELATIONS": ["DXY", "GLD"],
}

HIDDEN_SYMBOLS = {
    "VIX_FUTURES": ["VX"],
    "ADDITIONAL_INTERNALS": [
        "ADVN-NYSE",
        "DECN-NYSE",
        "UVOL-NYSE",
        "DVOL-NYSE",
        "VOLD-NYSE",
        "NYHL-NYSE",
    ],
    "ADDITIONAL_VOLATILITY": ["VXST", "VXN", "RVX"],
    "PUT_CALL_RATIOS": ["CPCE", "CPCI"],
    "NASDAQ_INTERNALS": ["TICK-NASDAQ", "TRIN-NASDAQ"],
    "SECTOR_ETFS": ["XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLRE", "XLC", "XLB"],
}

# Custom/Calculated metrics (not from IB, but calculated internally)
CUSTOM_METRICS = {"CALCULATED_INTERNALLY": ["GEX", "DEX", "OGL", "DIX", "SWAN"]}

# Subscription mappings
SUBSCRIPTION_MAPPINGS = {
    "NYSE (Network A)": ["SPY", "DIA", "QQQ", "IWM", "XL*"],
    "CME Futures": ["/ES", "/VX"],
    "CBOE Indices": ["VIX", "VIX9D", "VXV", "VXMT", "VVIX", "VXST", "VXN", "RVX"],
    "NYSE Market Data": ["TICK-NYSE", "TRIN-NYSE", "ADD-NYSE", "ADVN-NYSE", "DECN-NYSE"],
    "NASDAQ Market Data": ["TICK-NASDAQ", "TRIN-NASDAQ"],
    "OPRA (US Options)": ["SPY Options"],
}

# ==============================================================================
# ENUMS
# ==============================================================================


class TestStatus(Enum):
    """Test result status enumeration"""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"
    NO_SUBSCRIPTION = "no_subscription"


class SymbolType(Enum):
    """Symbol type enumeration"""

    STOCK = "stock"
    INDEX = "index"
    FUTURE = "future"
    OPTION = "option"
    INTERNAL = "internal"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class SymbolTestResult:
    """Results for individual symbol test"""

    symbol: str
    category: str
    symbol_type: SymbolType
    status: TestStatus
    has_data: bool = False
    subscription_required: Optional[str] = None
    error_message: Optional[str] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class OptionsTestResult:
    """Results for options chain test"""

    expiry_type: str  # 0DTE, 1DTE, Weekly
    expiry_date: str
    tested_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    success_rate: float = 0.0
    test_details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TestReport:
    """Comprehensive test report"""

    test_id: str
    test_time: datetime
    connection_info: Dict[str, Any]
    total_symbols_tested: int
    successful_tests: int
    failed_tests: int
    error_tests: int
    success_rate: float
    symbol_results: List[SymbolTestResult]
    options_results: Dict[str, OptionsTestResult]
    subscription_recommendations: Dict[str, List[str]]
    report_file: Optional[str] = None


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class LiveIBConnectionTester:
    """
    Live IB Connection and Market Data Subscription Tester.

    This class provides comprehensive testing capabilities for Interactive Brokers
    connectivity and market data subscriptions. It validates access to all required
    symbols and generates detailed reports with subscription recommendations.

    Attributes:
        logger: Module logger instance
        client: IB client connection
        contract_builder: Contract builder for creating IB contracts
        symbol_results: List of symbol test results
        options_results: Dictionary of options test results

    Example:
        >>> tester = LiveIBConnectionTester()
        >>> tester.initialize()
        >>> report = tester.run_comprehensive_test()
        >>> tester.save_report(report)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the tester.

        Args:
            config: Optional configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.client: Optional[SpyderClient] = None
        self.contract_builder = ContractBuilder()

        # Test configuration
        self.config = config or {
            "host": DEFAULT_HOST,
            "port": DEFAULT_PORT,
            "client_id": DEFAULT_CLIENT_ID,
            "timeout": CONNECTION_TIMEOUT,
        }

        # Results storage
        self.symbol_results: List[SymbolTestResult] = []
        self.options_results: Dict[str, OptionsTestResult] = {}

        self.logger.info(f"{self.__class__.__name__} initialized")

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize connection to IB Gateway/TWS.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info(
                f"Initializing IB connection at {
                    self.config['host']}:{
                    self.config['port']}"
            )

            ib_config = IBConfig(
                host=self.config["host"],
                port=self.config["port"],
                client_id=self.config["client_id"],
            )

            self.client = SpyderClient(ib_config)

            if self.client.connect():
                self.logger.info("✅ Successfully connected to IB")
                time.sleep(2)  # Let connection stabilize
                return True
            else:
                self.logger.error("❌ Failed to connect to IB")
                return False

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            return False

    def run_comprehensive_test(self) -> TestReport:
        """
        Run comprehensive market data subscription test.

        Returns:
            TestReport: Comprehensive test results
        """
        self.logger.info("Starting comprehensive IB market data test")

        test_id = f"IB_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()

        # Clear previous results
        self.symbol_results.clear()
        self.options_results.clear()

        # Print test summary
        self._print_test_summary()

        # Test all symbols
        self._test_all_symbols()

        # Test SPY options
        self._test_spy_options()

        # Generate report
        report = self._generate_report(test_id, start_time)

        # Print results
        self._print_results(report)

        return report

    def test_symbol(self, symbol: str, category: str) -> SymbolTestResult:
        """
        Test market data for a single symbol.

        Args:
            symbol: Symbol to test
            category: Symbol category

        Returns:
            SymbolTestResult: Test results for the symbol
        """
        # Determine symbol type
        symbol_type = self._get_symbol_type(symbol)

        result = SymbolTestResult(
            symbol=symbol, category=category, symbol_type=symbol_type, status=TestStatus.FAILED
        )

        try:
            # Build appropriate contract
            contract = self._build_contract(symbol, symbol_type)

            # Request market data
            self.logger.info(f"Requesting market data for {symbol}...")
            ticker = self.client.ib.reqMktData(contract, "", False, False)

            # Wait for data
            timeout = DATA_WAIT_TIMEOUT
            start_time = time.time()

            while time.time() - start_time < timeout:
                self.client.ib.sleep(0.1)

                if ticker.bid is not None or ticker.ask is not None or ticker.last is not None:
                    result.status = TestStatus.SUCCESS
                    result.has_data = True
                    result.bid = ticker.bid
                    result.ask = ticker.ask
                    result.last = ticker.last

                    self.logger.info(
                        f"✅ {symbol}: Bid={
                            ticker.bid}, Ask={
                            ticker.ask}, Last={
                            ticker.last}"
                    )
                    break

                # Check for errors
                if hasattr(ticker, "error") and ticker.error:
                    result.error_message = str(ticker.error)
                    if "No market data permissions" in result.error_message:
                        result.status = TestStatus.NO_SUBSCRIPTION
                        result.subscription_required = self._identify_subscription(symbol)
                    else:
                        result.status = TestStatus.ERROR
                    break

            if result.status == TestStatus.FAILED:
                result.status = TestStatus.TIMEOUT
                result.error_message = "Timeout - no data received"
                self.logger.warning(f"⏱️ {symbol}: Timeout waiting for data")

            # Cancel market data request
            self.client.ib.cancelMktData(ticker)

        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            self.logger.error(f"❌ {symbol}: {e}")

        self.symbol_results.append(result)
        return result

    def save_report(self, report: TestReport, filename: Optional[str] = None) -> str:
        """
        Save test report to CSV file.

        Args:
            report: Test report to save
            filename: Optional custom filename

        Returns:
            str: Path to saved report file
        """
        if filename is None:
            filename = f"ib_subscription_test_{report.test_time.strftime('%Y%m%d_%H%M%S')}.csv"

        try:
            # Convert results to DataFrame
            data = []
            for result in report.symbol_results:
                data.append(
                    {
                        "symbol": result.symbol,
                        "category": result.category,
                        "symbol_type": result.symbol_type.value,
                        "status": result.status.value,
                        "has_data": result.has_data,
                        "subscription_required": result.subscription_required,
                        "error": result.error_message,
                        "bid": result.bid,
                        "ask": result.ask,
                        "last": result.last,
                        "timestamp": result.timestamp,
                    }
                )

            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)

            self.logger.info(f"Report saved to: {filename}")
            return filename

        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")
            return ""

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _get_symbol_type(self, symbol: str) -> SymbolType:
        """Determine symbol type from symbol string."""
        if symbol.startswith("/"):
            return SymbolType.FUTURE
        elif symbol in ["SPX", "VIX", "DXY"] or "-" in symbol:
            return SymbolType.INDEX
        elif "TICK" in symbol or "TRIN" in symbol or "ADD" in symbol:
            return SymbolType.INTERNAL
        else:
            return SymbolType.STOCK

    def _build_contract(self, symbol: str, symbol_type: SymbolType):
        """Build appropriate contract based on symbol type."""
        if symbol_type == SymbolType.FUTURE:
            # Futures need special handling - using Stock for now
            # TODO: Add proper futures support
            return self.contract_builder.build_stock(symbol.replace("/", ""))
        elif symbol_type in [SymbolType.INDEX, SymbolType.INTERNAL]:
            # Indices also use stock type in IB API
            return self.contract_builder.build_stock(symbol.replace("-", "."))
        else:
            return self.contract_builder.build_stock(symbol)

    def _identify_subscription(self, symbol: str) -> str:
        """Identify which subscription is needed for a symbol."""
        for subscription, symbols in SUBSCRIPTION_MAPPINGS.items():
            for pattern in symbols:
                if pattern.endswith("*"):
                    if symbol.startswith(pattern[:-1]):
                        return subscription
                elif symbol == pattern:
                    return subscription
        return "Unknown - check IB subscription page"

    def _print_test_summary(self):
        """Print test summary information."""
        visible_count = sum(len(symbols) for symbols in VISIBLE_SYMBOLS.values())
        hidden_count = sum(len(symbols) for symbols in HIDDEN_SYMBOLS.values())
        total_symbols = visible_count + hidden_count

        self.logger.info("\n" + "=" * 70)
        self.logger.info("LIVE IB MARKET DATA SUBSCRIPTION TEST")
        self.logger.info("=" * 70)
        self.logger.info(f"\nTesting Summary:")
        self.logger.info(f"  📊 Visible Dashboard Symbols: {visible_count}")
        self.logger.info(f"  🔧 Hidden Backend Symbols: {hidden_count}")
        self.logger.info(f"  📈 Total Symbols: {total_symbols}")
        self.logger.info(f"  ⚙️  Custom Metrics (GEX, DEX, etc): Calculated internally, not from IB")

    def _test_all_symbols(self):
        """Test all configured symbols."""
        # Combine all symbols for testing
        all_categories = {**VISIBLE_SYMBOLS, **HIDDEN_SYMBOLS}
        total_symbols = sum(len(symbols) for symbols in all_categories.values())
        tested = 0

        # Test visible symbols
        self.logger.info("\n" + "=" * 50)
        self.logger.info("VISIBLE DASHBOARD SYMBOLS")
        self.logger.info("=" * 50)

        for category, symbols in VISIBLE_SYMBOLS.items():
            self.logger.info(f"\n{category}:")
            self.logger.info("-" * 40)

            for symbol in symbols:
                tested += 1
                self.logger.info(f"[{tested}/{total_symbols}] Testing {symbol}...")
                self.test_symbol(symbol, category)
                time.sleep(REQUEST_DELAY)

        # Test hidden symbols
        self.logger.info("\n" + "=" * 50)
        self.logger.info("HIDDEN BACKEND SYMBOLS")
        self.logger.info("=" * 50)

        for category, symbols in HIDDEN_SYMBOLS.items():
            self.logger.info(f"\n{category}:")
            self.logger.info("-" * 40)

            for symbol in symbols:
                tested += 1
                self.logger.info(f"[{tested}/{total_symbols}] Testing {symbol}...")
                self.test_symbol(symbol, category)
                time.sleep(REQUEST_DELAY)

    def _test_spy_options(self):
        """Test SPY options chain data availability."""
        self.logger.info("\n" + "=" * 70)
        self.logger.info("TESTING SPY OPTIONS CHAINS")
        self.logger.info("=" * 70)

        try:
            # Get current SPY price
            spy_contract = self.contract_builder.build_spy()
            spy_ticker = self.client.ib.reqMktData(spy_contract, "", False, False)
            time.sleep(2)
            spy_price = spy_ticker.last or 585.0  # Use default if no data
            self.client.ib.cancelMktData(spy_ticker)

            # Test different expiration types
            today = datetime.now().date()

            # 0DTE
            expiry_0dte = today.strftime("%Y%m%d")
            self._test_options_expiry("0DTE", expiry_0dte, spy_price)

            # 1DTE
            tomorrow = today + timedelta(days=1)
            expiry_1dte = tomorrow.strftime("%Y%m%d")
            self._test_options_expiry("1DTE", expiry_1dte, spy_price)

            # Weekly (next Friday)
            days_until_friday = (4 - today.weekday()) % 7
            if days_until_friday == 0:
                days_until_friday = 7
            next_friday = today + timedelta(days=days_until_friday)
            expiry_weekly = next_friday.strftime("%Y%m%d")
            self._test_options_expiry("Weekly", expiry_weekly, spy_price)

        except Exception as e:
            self.logger.error(f"Options test error: {e}")

    def _test_options_expiry(self, expiry_type: str, expiry: str, spy_price: float):
        """Test options for specific expiry."""
        result = OptionsTestResult(expiry_type=expiry_type, expiry_date=expiry)

        strikes = [int(spy_price - 2), int(spy_price), int(spy_price + 2)]

        self.logger.info(f"\nTesting {expiry_type} options (expiry: {expiry}):")

        for strike in strikes:
            for right in ["C", "P"]:
                result.tested_count += 1

                try:
                    contract = self.contract_builder.create_spy_option(
                        strike=strike, expiry=expiry, right=right
                    )

                    ticker = self.client.ib.reqMktData(contract, "", False, False)
                    time.sleep(1)

                    test_detail = {
                        "strike": strike,
                        "right": right,
                        "success": False,
                        "bid": None,
                        "ask": None,
                    }

                    if ticker.bid is not None or ticker.ask is not None:
                        result.success_count += 1
                        test_detail["success"] = True
                        test_detail["bid"] = ticker.bid
                        test_detail["ask"] = ticker.ask
                        self.logger.info(
                            f"✅ SPY {expiry} {strike}{right}: Bid={
                                ticker.bid}, Ask={
                                ticker.ask}"
                        )
                    else:
                        result.failed_count += 1
                        self.logger.warning(f"❌ SPY {expiry} {strike}{right}: No data")

                    result.test_details.append(test_detail)
                    self.client.ib.cancelMktData(ticker)

                except Exception as e:
                    result.failed_count += 1
                    self.logger.error(f"❌ SPY {expiry} {strike}{right}: {e}")

                time.sleep(REQUEST_DELAY)

        result.success_rate = (
            (result.success_count / result.tested_count) if result.tested_count > 0 else 0.0
        )
        self.options_results[expiry_type] = result

        self.logger.info(f"{expiry_type}: {result.success_count}/{result.tested_count} successful")

    def _generate_report(self, test_id: str, start_time: datetime) -> TestReport:
        """Generate comprehensive test report."""
        # Calculate statistics
        total_tests = len(self.symbol_results)
        successful = sum(1 for r in self.symbol_results if r.status == TestStatus.SUCCESS)
        failed = sum(1 for r in self.symbol_results if r.status != TestStatus.SUCCESS)
        errors = sum(1 for r in self.symbol_results if r.status == TestStatus.ERROR)

        # Group failed symbols by subscription
        subscription_recommendations = {}
        for result in self.symbol_results:
            if result.subscription_required:
                if result.subscription_required not in subscription_recommendations:
                    subscription_recommendations[result.subscription_required] = []
                subscription_recommendations[result.subscription_required].append(result.symbol)

        report = TestReport(
            test_id=test_id,
            test_time=start_time,
            connection_info={
                "host": self.config["host"],
                "port": self.config["port"],
                "client_id": self.config["client_id"],
            },
            total_symbols_tested=total_tests,
            successful_tests=successful,
            failed_tests=failed,
            error_tests=errors,
            success_rate=(successful / total_tests * 100) if total_tests > 0 else 0.0,
            symbol_results=self.symbol_results.copy(),
            options_results=self.options_results.copy(),
            subscription_recommendations=subscription_recommendations,
        )

        return report

    def _print_results(self, report: TestReport):
        """Print comprehensive test results."""
        print("\n" + "=" * 70)
        print("MARKET DATA SUBSCRIPTION TEST RESULTS")
        print("=" * 70)
        print(f"\nTest Time: {report.test_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Symbols Tested: {report.total_symbols_tested}")
        print(f"✅ Successful (have data): {report.successful_tests}")
        print(f"❌ Failed (no data): {report.failed_tests}")
        print(f"⚠️  Errors: {report.error_tests}")
        print(f"Success Rate: {report.success_rate:.1f}%")

        # Failed symbols detail
        if report.failed_tests > 0:
            print("\n" + "=" * 70)
            print("FAILED SYMBOLS (Need Subscription)")
            print("=" * 70)

            for result in report.symbol_results:
                if result.status != TestStatus.SUCCESS:
                    print(f"\n❌ {result.symbol} ({result.category})")
                    print(f"   Status: {result.status.value}")
                    if result.error_message:
                        print(f"   Error: {result.error_message}")
                    if result.subscription_required:
                        print(f"   Required Subscription: {result.subscription_required}")

        # Subscription recommendations
        if report.subscription_recommendations:
            print("\n" + "=" * 70)
            print("SUBSCRIPTION RECOMMENDATIONS")
            print("=" * 70)

            for subscription, symbols in report.subscription_recommendations.items():
                print(f"\n📦 {subscription}:")
                print(f"   Needed for: {', '.join(symbols)}")

        # Options results
        print("\n" + "=" * 70)
        print("SPY OPTIONS TEST SUMMARY")
        print("=" * 70)
        for expiry_type, result in report.options_results.items():
            print(
                f"{expiry_type}: {result.success_count}/{result.tested_count} ({result.success_rate:.1f}%)"
            )

        if any(r.success_rate < 100 for r in report.options_results.values()):
            print("\n⚠️  Missing SPY options data - ensure you have OPRA subscription")

        # Next steps
        print("\n" + "=" * 70)
        print("NEXT STEPS")
        print("=" * 70)
        print("\n1. Log into IBKR Account Management")
        print("2. Go to Settings > User Settings > Market Data Subscriptions")
        print("3. Compare your current subscriptions with the recommendations above")
        print("4. For SPY options, ensure you have OPRA (US Options) subscription")
        print("\n💡 Tip: Consider bundled packages for cost savings")

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start the tester (initialize if needed)."""
        if not self.client:
            self.initialize()

    def stop(self) -> None:
        """Stop the tester and cleanup resources."""
        if self.client:
            self.client.disconnect()
            self.logger.info("Disconnected from IB")
            self.client = None

    def cleanup(self) -> None:
        """Clean up module resources."""
        self.stop()
        self.symbol_results.clear()
        self.options_results.clear()
        self.logger.info("Tester cleanup completed")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_test_config(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, client_id: int = DEFAULT_CLIENT_ID
) -> Dict[str, Any]:
    """
    Create test configuration.

    Args:
        host: IB Gateway/TWS host
        port: IB Gateway/TWS port
        client_id: Client ID for connection

    Returns:
        Configuration dictionary
    """
    return {"host": host, "port": port, "client_id": client_id, "timeout": CONNECTION_TIMEOUT}


def print_welcome_banner():
    """Print welcome banner for the test."""
    print("\n🔍 SPYDER Live IB Market Data Test")
    print("=" * 50)
    print("⚠️  Prerequisites:")
    print("   1. IB Gateway or TWS must be running")
    print("   2. Market should be open for best results")
    print("   3. Check your port settings in TEST_CONFIG")
    print("=" * 50)


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level instance for singleton pattern
_tester_instance: Optional[LiveIBConnectionTester] = None


def get_tester_instance(config: Optional[Dict[str, Any]] = None) -> LiveIBConnectionTester:
    """
    Get singleton instance of the tester.

    Args:
        config: Optional configuration

    Returns:
        Tester instance
    """
    global _tester_instance
    if _tester_instance is None:
        _tester_instance = LiveIBConnectionTester(config)
    return _tester_instance


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Print welcome banner
    print_welcome_banner()

    response = input("\nReady to start? (y/n): ")
    if response.lower() != "y":
        print("Test cancelled.")
        sys.exit(0)

    # Create tester instance
    tester = LiveIBConnectionTester()

    try:
        # Initialize connection
        if not tester.initialize():
            print("\n❌ Failed to connect. Please check:")
            print("   - IB Gateway/TWS is running")
            print("   - Port settings are correct")
            print("   - API connections are enabled")
            sys.exit(1)

        # Run comprehensive test
        report = tester.run_comprehensive_test()

        # Save report
        report_file = tester.save_report(report)
        if report_file:
            print(f"\n💾 Detailed report saved to: {report_file}")

        # Success exit
        sys.exit(0 if report.success_rate > 80 else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup
        tester.cleanup()
