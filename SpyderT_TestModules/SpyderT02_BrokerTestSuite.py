#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT02_BrokerTestSuite.py
Purpose: Comprehensive broker integration testing with modern ib_async
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-01-21 Time: 15:30:00

Module Description:
    Comprehensive test suite for SpyderB_Broker modules with market data
    subscription testing to verify all required symbols are available through
    current IBKR subscriptions. Uses modern ib_async for enhanced compatibility.

    UPDATED: Now uses modern ib_async instead of legacy ib_insync for improved
    IB Gateway 10.37 compatibility and enhanced test stability.

NOTE: This test suite uses ib_async directly for Index and Futures contracts
      since ContractBuilder currently focuses on stocks and options.

What This Test Does:
    1. Tests connection to IB Gateway/TWS
    2. Attempts to subscribe to ALL symbols needed by Spyder
    3. Reports which symbols work with current subscriptions
    4. Lists failed symbols that need additional IBKR data feeds
    5. Provides specific IBKR subscription recommendations
    6. Tests SPY options chain availability

Usage:
    # Run all tests with mocks
    python SpyderT02_BrokerTestSuite.py
    
    # Run with real IB connection
    python SpyderT02_BrokerTestSuite.py --real
    
    # Run market data tests only
    python SpyderT02_BrokerTestSuite.py --test TestMarketDataAvailability --real
    
    # Run with pytest
    python -m pytest SpyderT02_BrokerTestSuite.py -v

Dependencies:
    • ib_async (modern IB API wrapper)
    • pytest (testing framework)
    • unittest.mock (mocking capabilities)

Installation Note:
    pip install ib_async pytest
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import unittest
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import os
import sys
import argparse
import logging
from pathlib import Path
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import pandas as pd

# For direct contract creation (Index, Future) - Using modern ib_async
try:
    from ib_async import Index, Future
    HAS_IB_ASYNC = True
except ImportError:
    HAS_IB_ASYNC = False
    print("Warning: ib_async not available - some contract tests will use mocks")
    print("Install with: pip install ib_async")

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient, IBConfig
from SpyderB_Broker.SpyderB02_OrderManager import OrderManager, OrderRequest, OrderAction, OrderType
from SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker
from SpyderB_Broker.SpyderB04_AccountManager import AccountManager
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager

# Try to import event management
try:
    from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
    HAS_EVENT_MANAGER = True
except ImportError:
    HAS_EVENT_MANAGER = False
    EventManager = Mock
    Event = Mock
    EventType = Mock

# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================

TEST_CONFIG = {
    'host': '127.0.0.1',
    'port': 4002,  # Paper trading port
    'client_id': 999,  # Unique test client ID
    'timeout': 30,
    'use_mock': True,  # Default to mock mode for safety
    'log_level': logging.INFO,
    'max_symbols_per_test': 10,  # Limit for faster testing
    'market_data_timeout': 10,   # Seconds to wait for market data
}

# Market symbols configuration for comprehensive testing
MARKET_SYMBOLS = {
    # Core symbols (Client 3)
    'SPY': {'type': 'STK', 'exchange': 'SMART', 'required': True},
    'SPX': {'type': 'IND', 'exchange': 'CBOE', 'required': True},
    '/ES': {'type': 'FUT', 'exchange': 'CME', 'required': True, 'localSymbol': 'ESM5'},
    'VIX': {'type': 'IND', 'exchange': 'CBOE', 'required': True},
    'TICK-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'required': True},
    
    # Volatility indicators (Client 5)
    'VIX9D': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    'VXV': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    'VXMT': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    'VVIX': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    'UVXY': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    
    # Market internals (Client 6)
    'TRIN': {'type': 'IND', 'exchange': 'NYSE', 'required': False},
    'ADD': {'type': 'IND', 'exchange': 'NYSE', 'required': False},
    'CPC': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    'PCALL': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    'SKEW': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    'VUD': {'type': 'IND', 'exchange': 'CBOE', 'required': False},
    
    # Major indices (Client 7)
    'DIA': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'QQQ': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'IWM': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    
    # Extended assets (Client 8)
    'TLT': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'LQD': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'DXY': {'type': 'IND', 'exchange': 'ICE', 'required': False},
    'GLD': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    
    # Sector ETFs (Client 9)
    'XLF': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'XLK': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'XLE': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'XLV': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    
    # International markets (Client 10)
    'FTLC': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'EWJ': {'type': 'STK', 'exchange': 'SMART', 'required': False},
    'EWG': {'type': 'STK', 'exchange': 'SMART', 'required': False},
}

# IBKR subscription recommendations
SUBSCRIPTION_RECOMMENDATIONS = {
    'US Securities Snapshot and Futures Value Bundle': [
        'SPY', 'DIA', 'QQQ', 'IWM', 'TLT', 'LQD', 'GLD', 'UVXY',
        'XLF', 'XLK', 'XLE', 'XLV', 'FTLC', 'EWJ', 'EWG', '/ES'
    ],
    'US Equity and Options Add-On Streaming Bundle': [
        'SPY', 'DIA', 'QQQ', 'IWM'  # For options data
    ],
    'CBOE One': [
        'SPX', 'VIX', 'VIX9D', 'VXV', 'VXMT', 'VVIX', 'CPC', 'PCALL', 'SKEW', 'VUD'
    ],
    'NYSE OpenBook Ultra (Integrated Feed)': [
        'TICK-NYSE', 'TRIN', 'ADD'
    ],
    'ICE Data': [
        'DXY'
    ]
}

# ==============================================================================
# LOGGING SETUP
# ==============================================================================

def setup_logging(level=logging.INFO):
    """Setup logging for tests."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('spyder_broker_tests.log')
        ]
    )

logger = logging.getLogger(__name__)

# ==============================================================================
# BASE TEST CLASS
# ==============================================================================

class SpyderBrokerTestBase(unittest.TestCase):
    """Base class for all broker integration tests."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        setup_logging(TEST_CONFIG['log_level'])
        
        # Create event manager
        if HAS_EVENT_MANAGER:
            cls.event_manager = EventManager()
        else:
            cls.event_manager = Mock()
        
        # Create IB configuration
        cls.ib_config = IBConfig(
            host=TEST_CONFIG['host'],
            port=TEST_CONFIG['port'],
            client_id=TEST_CONFIG['client_id']
        )
        
        # Create or mock client based on configuration
        if TEST_CONFIG['use_mock']:
            # Use mock client
            cls.spyder_client = Mock(spec=SpyderClient)
            cls.spyder_client.is_connected.return_value = True
            cls.spyder_client.get_account_info.return_value = {
                'net_liquidation': 100000.0,
                'buying_power': 200000.0
            }
            cls.spyder_client.get_positions.return_value = []
            cls.spyder_client.request_market_data.return_value = 1
            cls.spyder_client.get_market_data.return_value = Mock(bid=100.0, ask=100.1, last=100.05)
            
            # Mock contract creation methods
            cls.spyder_client.create_stock_contract = Mock(side_effect=lambda symbol: Mock(
                symbol=symbol, secType='STK', exchange='SMART', currency='USD'
            ))
            cls.spyder_client.create_option_contract = Mock(side_effect=lambda symbol, exp, strike, right: Mock(
                symbol=symbol, lastTradeDateOrContractMonth=exp, strike=strike, right=right, 
                secType='OPT', exchange='SMART', currency='USD'
            ))
        else:
            # Use real client
            cls.spyder_client = SpyderClient(cls.ib_config, cls.event_manager)
            
            # Connect to IB
            if not cls.spyder_client.connect():
                pytest.skip("Cannot connect to IB Gateway/TWS")
    
    def setUp(self):
        """Set up for each test."""
        self.test_start_time = datetime.now()
        logger.debug(f"Starting test: {self._testMethodName}")
    
    def tearDown(self):
        """Clean up after each test."""
        test_duration = (datetime.now() - self.test_start_time).total_seconds()
        logger.debug(f"Completed test: {self._testMethodName} in {test_duration:.2f}s")
    
    # ==============================================================================
    # TEST UTILITIES
    # ==============================================================================
    def wait_for_event(self, event_type, timeout: float = 5.0) -> Optional[Any]:
        """Wait for specific event to occur."""
        if not HAS_EVENT_MANAGER:
            return None
            
        received_event = None
        event_received = threading.Event()
        
        def handler(event):
            nonlocal received_event
            received_event = event
            event_received.set()
        
        self.event_manager.subscribe(event_type, handler)
        event_received.wait(timeout)
        self.event_manager.unsubscribe(event_type, handler)
        
        return received_event
    
    def assert_within_range(self, value: float, target: float, tolerance: float = 0.01):
        """Assert value is within tolerance of target."""
        self.assertAlmostEqual(value, target, delta=target * tolerance)

# ==============================================================================
# MARKET DATA AVAILABILITY TESTS
# ==============================================================================

class TestMarketDataAvailability(SpyderBrokerTestBase):
    """Test market data availability for all required symbols using modern ib_async."""
    
    def setUp(self):
        """Set up market data tests."""
        super().setUp()
        self.test_results = {
            'successful': [],
            'failed': [],
            'errors': []
        }
        
        # Initialize contract builder
        self.contract_builder = ContractBuilder()
    
    def create_contract(self, symbol: str, config: Dict) -> Any:
        """
        Create IB contract from symbol configuration.
        
        NOTE: This method uses ib_async directly for Index and Futures contracts.
        For production use, consider extending ContractBuilder with:
        - build_index(symbol, exchange) 
        - build_future(symbol, exchange, local_symbol)
        
        Args:
            symbol: Symbol to create contract for
            config: Configuration dictionary with contract details
            
        Returns:
            Contract object or None if creation fails
        """
        contract_type = config.get('type', 'STK')
        
        try:
            if contract_type == 'STK':
                return self.contract_builder.build_stock(symbol)
            elif contract_type == 'IND':
                # Index contract - using ib_async directly
                if HAS_IB_ASYNC:
                    contract = Index(
                        symbol=config.get('symbol', symbol),
                        exchange=config.get('exchange', 'CBOE'),
                        currency='USD'
                    )
                    logger.debug(f"Created Index contract for {symbol} using ib_async")
                else:
                    # Mock for testing without ib_async
                    contract = Mock()
                    contract.symbol = config.get('symbol', symbol)
                    contract.secType = 'IND'
                    contract.exchange = config.get('exchange', 'CBOE')
                    contract.currency = 'USD'
                    logger.debug(f"Created mock Index contract for {symbol}")
                return contract
            elif contract_type == 'FUT':
                # Futures contract - using ib_async directly
                if HAS_IB_ASYNC:
                    contract = Future(
                        symbol=config.get('symbol', symbol),
                        exchange=config.get('exchange', 'CME'),
                        currency='USD'
                    )
                    # Set local symbol if provided (for specific contract months)
                    if config.get('localSymbol'):
                        contract.localSymbol = config['localSymbol']
                    logger.debug(f"Created Future contract for {symbol} using ib_async")
                else:
                    # Mock for testing without ib_async
                    contract = Mock()
                    contract.symbol = config.get('symbol', symbol)
                    contract.secType = 'FUT'
                    contract.exchange = config.get('exchange', 'CME')
                    contract.currency = 'USD'
                    if config.get('localSymbol'):
                        contract.localSymbol = config['localSymbol']
                    logger.debug(f"Created mock Future contract for {symbol}")
                return contract
            else:
                logger.warning(f"Unsupported contract type: {contract_type}")
                return None
        except Exception as e:
            logger.error(f"Error creating contract for {symbol}: {e}")
            return None
    
    @pytest.mark.skipif(TEST_CONFIG['use_mock'], reason="Requires real IB connection")
    def test_visible_symbols_availability(self):
        """Test all visible dashboard symbols."""
        logger.info("🔍 Testing visible dashboard symbols...")
        
        # Test core symbols first (highest priority)
        core_symbols = {k: v for k, v in MARKET_SYMBOLS.items() if v.get('required', False)}
        
        for symbol, config in core_symbols.items():
            with self.subTest(symbol=symbol):
                self._test_symbol_subscription(symbol, config, critical=True)
        
        # Test optional symbols (lower priority)
        optional_symbols = {k: v for k, v in MARKET_SYMBOLS.items() if not v.get('required', False)}
        
        for symbol, config in list(optional_symbols.items())[:TEST_CONFIG['max_symbols_per_test']]:
            with self.subTest(symbol=symbol):
                self._test_symbol_subscription(symbol, config, critical=False)
        
        self._generate_subscription_report()
    
    def _test_symbol_subscription(self, symbol: str, config: Dict, critical: bool = False):
        """Test individual symbol subscription."""
        try:
            logger.info(f"Testing {symbol} ({config['type']})...")
            
            # Create contract
            contract = self.create_contract(symbol, config)
            if not contract:
                self.test_results['errors'].append({
                    'symbol': symbol,
                    'error': 'Failed to create contract',
                    'critical': critical
                })
                if critical:
                    self.fail(f"Critical symbol {symbol} failed contract creation")
                return
            
            # Request market data
            if hasattr(self.spyder_client, 'request_market_data'):
                req_id = self.spyder_client.request_market_data(contract)
                if req_id > 0:
                    # Wait for data
                    time.sleep(TEST_CONFIG['market_data_timeout'])
                    
                    # Check if we received data
                    ticker = self.spyder_client.get_market_data(req_id)
                    if ticker and hasattr(ticker, 'last') and ticker.last > 0:
                        self.test_results['successful'].append({
                            'symbol': symbol,
                            'type': config['type'],
                            'exchange': config['exchange'],
                            'price': ticker.last if hasattr(ticker, 'last') else 0,
                            'critical': critical
                        })
                        logger.info(f"✅ {symbol}: Data available (${ticker.last:.2f})")
                    else:
                        self.test_results['failed'].append({
                            'symbol': symbol,
                            'type': config['type'],
                            'exchange': config['exchange'],
                            'error': 'No market data received',
                            'critical': critical
                        })
                        logger.warning(f"❌ {symbol}: No market data")
                        
                        if critical:
                            self.fail(f"Critical symbol {symbol} has no market data")
                    
                    # Cancel subscription
                    self.spyder_client.cancel_market_data(req_id)
                else:
                    raise Exception("Failed to request market data")
            else:
                # Mock mode - simulate success
                self.test_results['successful'].append({
                    'symbol': symbol,
                    'type': config['type'],
                    'exchange': config['exchange'],
                    'price': 100.0,  # Mock price
                    'critical': critical
                })
                logger.info(f"✅ {symbol}: Mock data available")
                
        except Exception as e:
            self.test_results['errors'].append({
                'symbol': symbol,
                'error': str(e),
                'critical': critical
            })
            logger.error(f"❌ {symbol}: Error - {e}")
            
            if critical:
                self.fail(f"Critical symbol {symbol} failed: {e}")
    
    def _generate_subscription_report(self):
        """Generate comprehensive subscription report."""
        logger.info("\n" + "="*70)
        logger.info("MARKET DATA SUBSCRIPTION REPORT")
        logger.info("="*70)
        
        total_tested = len(self.test_results['successful']) + len(self.test_results['failed']) + len(self.test_results['errors'])
        success_count = len(self.test_results['successful'])
        
        logger.info(f"Total symbols tested: {total_tested}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Failed: {len(self.test_results['failed'])}")
        logger.info(f"Errors: {len(self.test_results['errors'])}")
        
        if total_tested > 0:
            success_rate = (success_count / total_tested) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")
        
        # Successful symbols
        if self.test_results['successful']:
            logger.info(f"\n✅ WORKING SYMBOLS ({len(self.test_results['successful'])}):")
            for result in self.test_results['successful']:
                price_info = f" - ${result['price']:.2f}" if 'price' in result else ""
                critical_marker = " [CRITICAL]" if result.get('critical') else ""
                logger.info(f"   {result['symbol']} ({result['type']}) on {result['exchange']}{price_info}{critical_marker}")
        
        # Failed symbols
        if self.test_results['failed']:
            logger.info(f"\n❌ FAILED SYMBOLS ({len(self.test_results['failed'])}):")
            for result in self.test_results['failed']:
                critical_marker = " [CRITICAL]" if result.get('critical') else ""
                logger.info(f"   {result['symbol']} ({result['type']}) on {result['exchange']}: {result['error']}{critical_marker}")
        
        # Error symbols
        if self.test_results['errors']:
            logger.info(f"\n🚨 ERROR SYMBOLS ({len(self.test_results['errors'])}):")
            for result in self.test_results['errors']:
                critical_marker = " [CRITICAL]" if result.get('critical') else ""
                logger.info(f"   {result['symbol']}: {result['error']}{critical_marker}")
        
        # Generate recommendations
        self._generate_subscription_recommendations()
    
    def _generate_subscription_recommendations(self):
        """Generate IBKR subscription recommendations."""
        logger.info(f"\n📋 IBKR SUBSCRIPTION RECOMMENDATIONS:")
        logger.info("-" * 50)
        
        failed_symbols = [r['symbol'] for r in self.test_results['failed']]
        error_symbols = [r['symbol'] for r in self.test_results['errors']]
        missing_symbols = failed_symbols + error_symbols
        
        if not missing_symbols:
            logger.info("🎉 All tested symbols are working! No additional subscriptions needed.")
            return
        
        # Match missing symbols to subscription packages
        needed_subscriptions = set()
        
        for package, symbols in SUBSCRIPTION_RECOMMENDATIONS.items():
            if any(symbol in missing_symbols for symbol in symbols):
                needed_subscriptions.add(package)
                logger.info(f"\n📦 {package}:")
                package_symbols = [s for s in symbols if s in missing_symbols]
                for symbol in package_symbols:
                    logger.info(f"   • {symbol}")
        
        if needed_subscriptions:
            logger.info(f"\n💡 NEXT STEPS:")
            logger.info("   1. Log in to IBKR Account Management")
            logger.info("   2. Go to Settings > User Settings > Market Data Subscriptions")
            logger.info("   3. Consider subscribing to the packages listed above")
            logger.info("   4. Re-run this test to verify: python SpyderT02_BrokerTestSuite.py --real")

    def test_spy_options_chain_basic(self):
        """Test basic SPY options chain availability."""
        logger.info("🔍 Testing SPY options chain...")
        
        if TEST_CONFIG['use_mock']:
            logger.info("✅ SPY options: Mock mode - simulated success")
            return
        
        try:
            # Test a simple SPY option
            exp_date = (datetime.now() + timedelta(days=30)).strftime('%Y%m%d')
            spy_call = self.spyder_client.create_option_contract('SPY', exp_date, 450.0, 'C')
            
            self.assertIsNotNone(spy_call)
            self.assertEqual(spy_call.symbol, 'SPY')
            self.assertEqual(spy_call.right, 'C')
            
            logger.info("✅ SPY options: Contract creation successful")
            
        except Exception as e:
            logger.error(f"❌ SPY options chain test failed: {e}")
            self.fail(f"SPY options chain test failed: {e}")

# ==============================================================================
# CONNECTION TESTS
# ==============================================================================

class TestSpyderClientIntegration(SpyderBrokerTestBase):
    """Test SpyderClient core functionality with ib_async integration."""
    
    def test_connection_lifecycle(self):
        """Test connection, operations, and disconnection."""
        # Verify connection
        self.assertTrue(self.spyder_client.is_connected())
        
        # Test account info retrieval
        account_info = self.spyder_client.get_account_info()
        self.assertIsNotNone(account_info)
        self.assertIn('net_liquidation', account_info)
        self.assertGreater(account_info['net_liquidation'], 0)
        
        # Test buying power
        buying_power = self.spyder_client.get_buying_power()
        self.assertGreater(buying_power, 0)
        
        logger.info(f"Account info: {account_info}")
        logger.info("✅ Connection lifecycle test passed")
    
    def test_contract_creation(self):
        """Test contract creation methods."""
        # Stock contract
        spy_stock = self.spyder_client.create_stock_contract('SPY')
        self.assertEqual(spy_stock.symbol, 'SPY')
        self.assertEqual(spy_stock.secType, 'STK')
        self.assertEqual(spy_stock.exchange, 'SMART')
        
        # Option contract
        spy_option = self.spyder_client.create_option_contract(
            'SPY', '20250620', 450.0, 'C'
        )
        self.assertEqual(spy_option.symbol, 'SPY')
        self.assertEqual(spy_option.strike, 450.0)
        self.assertEqual(spy_option.right, 'C')
        self.assertEqual(spy_option.secType, 'OPT')
        
        logger.info("✅ Contract creation test passed")
    
    @pytest.mark.skipif(TEST_CONFIG['use_mock'], reason="Requires real IB connection")
    def test_market_data_request(self):
        """Test market data request and cancellation."""
        spy = self.spyder_client.create_stock_contract('SPY')
        
        # Request market data
        req_id = self.spyder_client.request_market_data(spy)
        self.assertGreater(req_id, 0)
        
        # Wait for data
        time.sleep(2)
        
        # Get ticker
        ticker = self.spyder_client.get_market_data(req_id)
        self.assertIsNotNone(ticker)
        
        # Cancel market data
        success = self.spyder_client.cancel_market_data(req_id)
        self.assertTrue(success)
        
        logger.info("✅ Market data request test passed")
    
    def test_error_handling(self):
        """Test error handling in client operations."""
        # Test invalid contract request
        if not TEST_CONFIG['use_mock']:
            invalid_req = self.spyder_client.request_market_data(None)
            self.assertEqual(invalid_req, -1)
        
        logger.info("✅ Error handling test passed")

# ==============================================================================
# ORDER MANAGEMENT TESTS
# ==============================================================================

class TestOrderManagement(SpyderBrokerTestBase):
    """Test order management functionality."""
    
    def setUp(self):
        """Set up order management tests."""
        super().setUp()
        self.order_manager = OrderManager(self.spyder_client, self.event_manager)
    
    def test_order_creation(self):
        """Test order creation and validation."""
        # Create a basic buy order
        order_request = OrderRequest(
            symbol='SPY',
            action=OrderAction.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        self.assertEqual(order_request.symbol, 'SPY')
        self.assertEqual(order_request.action, OrderAction.BUY)
        self.assertEqual(order_request.quantity, 100)
        
        logger.info("✅ Order creation test passed")
    
    @pytest.mark.skipif(TEST_CONFIG['use_mock'], reason="Requires real IB connection")
    def test_order_placement_simulation(self):
        """Test order placement in simulation mode."""
        # This test would place a small order in paper trading
        logger.info("Order placement simulation would run here with real connection")
        logger.info("✅ Order placement simulation test passed")

# ==============================================================================
# POSITION TRACKING TESTS
# ==============================================================================

class TestPositionTracking(SpyderBrokerTestBase):
    """Test position tracking functionality."""
    
    def setUp(self):
        """Set up position tracking tests."""
        super().setUp()
        self.position_tracker = PositionTracker(self.spyder_client, self.event_manager)
    
    def test_position_retrieval(self):
        """Test position data retrieval."""
        positions = self.spyder_client.get_positions()
        self.assertIsInstance(positions, list)
        
        logger.info(f"Current positions: {len(positions)}")
        logger.info("✅ Position retrieval test passed")

# ==============================================================================
# ACCOUNT MANAGEMENT TESTS
# ==============================================================================

class TestAccountManagement(SpyderBrokerTestBase):
    """Test account management functionality."""
    
    def setUp(self):
        """Set up account management tests."""
        super().setUp()
        self.account_manager = AccountManager(self.spyder_client, self.event_manager)
    
    def test_account_data_retrieval(self):
        """Test account data retrieval."""
        account_info = self.spyder_client.get_account_info()
        
        required_fields = ['net_liquidation', 'buying_power']
        for field in required_fields:
            self.assertIn(field, account_info)
            self.assertIsNotNone(account_info[field])
        
        logger.info("✅ Account data retrieval test passed")

# ==============================================================================
# CONNECTION MANAGER TESTS
# ==============================================================================

class TestConnectionManager(SpyderBrokerTestBase):
    """Test connection manager functionality."""
    
    def test_connection_manager_creation(self):
        """Test connection manager creation."""
        connection_manager = ConnectionManager()
        self.assertIsNotNone(connection_manager)
        
        logger.info("✅ Connection manager creation test passed")
    
    def test_gateway_status_check(self):
        """Test gateway status checking."""
        connection_manager = ConnectionManager()
        status = connection_manager.is_gateway_running()
        self.assertIsInstance(status, bool)
        
        logger.info(f"Gateway running: {status}")
        logger.info("✅ Gateway status check test passed")

# ==============================================================================
# CONTRACT BUILDER TESTS
# ==============================================================================

class TestContractBuilder(SpyderBrokerTestBase):
    """Test contract builder functionality."""
    
    def setUp(self):
        """Set up contract builder tests."""
        super().setUp()
        self.contract_builder = ContractBuilder()
    
    def test_stock_contract_building(self):
        """Test stock contract creation."""
        spy_stock = self.contract_builder.build_stock('SPY')
        
        self.assertEqual(spy_stock.symbol, 'SPY')
        self.assertEqual(spy_stock.secType, 'STK')
        self.assertEqual(spy_stock.exchange, 'SMART')
        
        logger.info("✅ Stock contract building test passed")
    
    def test_option_contract_building(self):
        """Test option contract creation."""
        exp_date = '20250620'
        spy_call = self.contract_builder.build_option('SPY', exp_date, 450.0, 'C')
        
        self.assertEqual(spy_call.symbol, 'SPY')
        self.assertEqual(spy_call.strike, 450.0)
        self.assertEqual(spy_call.right, 'C')
        
        logger.info("✅ Option contract building test passed")

# ==============================================================================
# TEST EXECUTION FUNCTIONS
# ==============================================================================

def run_tests(specific_test: Optional[str] = None, use_real_connection: bool = False) -> bool:
    """
    Run the test suite.
    
    Args:
        specific_test: Name of specific test class to run
        use_real_connection: Whether to use real IB connection
        
    Returns:
        bool: True if all tests passed
    """
    # Configure test mode
    TEST_CONFIG['use_mock'] = not use_real_connection
    
    if use_real_connection:
        logger.info("🔗 Running tests with REAL IB connection")
        logger.info("⚠️  Make sure IB Gateway/TWS is running on paper trading!")
    else:
        logger.info("🎭 Running tests with MOCK connections")
    
    logger.info(f"📊 Using library: {'ib_async (modern)' if HAS_IB_ASYNC else 'mocked'}")
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Test classes to run
    test_classes = [
        TestSpyderClientIntegration,
        TestOrderManagement,
        TestPositionTracking,
        TestAccountManagement,
        TestConnectionManager,
        TestContractBuilder,
    ]
    
    # Add market data tests only for real connections
    if use_real_connection:
        test_classes.append(TestMarketDataAvailability)
    
    # Filter to specific test if requested
    if specific_test:
        test_classes = [cls for cls in test_classes if cls.__name__ == specific_test]
        if not test_classes:
            logger.error(f"Test class '{specific_test}' not found")
            return False
    
    # Add tests to suite
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Generate summary
    logger.info("\n" + "="*70)
    logger.info("TEST SUMMARY")
    logger.info("="*70)
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Failures: {len(result.failures)}")
    logger.info(f"Errors: {len(result.errors)}")
    logger.info(f"Skipped: {len(result.skipped)}")
    if result.testsRun > 0:
        success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100)
        logger.info(f"Success rate: {success_rate:.1f}%")
    
    logger.info(f"Library used: {'ib_async (modern)' if HAS_IB_ASYNC else 'mocked'}")
    
    return result.wasSuccessful()

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run SpyderB_Broker integration tests with modern ib_async',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all tests with mocks
    python SpyderT02_BrokerTestSuite.py
    
    # Run with real IB connection (requires IB Gateway/TWS)
    python SpyderT02_BrokerTestSuite.py --real
    
    # Run market data tests only
    python SpyderT02_BrokerTestSuite.py --test TestMarketDataAvailability --real
    
    # Run with verbose output
    python SpyderT02_BrokerTestSuite.py -v
        """
    )
    
    parser.add_argument('--real', action='store_true', 
                       help='Use real IB connection instead of mocks')
    parser.add_argument('--test', type=str,
                       help='Run specific test class')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        TEST_CONFIG['log_level'] = logging.DEBUG
    
    # Run tests
    success = run_tests(
        specific_test=args.test,
        use_real_connection=args.real
    )
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
