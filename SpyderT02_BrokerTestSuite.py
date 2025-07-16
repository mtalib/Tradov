#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 2025-01-06 16:00:00
@author: Spyder Agent

SPYDER - Automated SPY Options Trading System
SpyderT02_BrokerTestSuite

This module provides comprehensive integration testing for all SpyderB_Broker
modules, ensuring they work correctly together in production scenarios.

UPDATED: Added comprehensive market data subscription testing to verify
all required symbols are available through current IBKR subscriptions.

NOTE: This test suite uses ib_insync directly for Index and Futures contracts
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

# For direct contract creation (Index, Future)
try:
    from ib_insync import Index, Future
    HAS_IB_INSYNC = True
except ImportError:
    HAS_IB_INSYNC = False
    print("Warning: ib_insync not available - some contract tests will use mocks")

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
from SpyderB_Broker.SpyderB05_ConnectionManager import ConnectionManager, ConnectionConfig
from SpyderB_Broker.SpyderB10_IBDataTypes import (
    IBContract, IBOrder, SecurityType, OrderStatus,
    create_stock_contract, create_option_contract
)
from SpyderB_Broker.SpyderB12_GatewayAutomation import GatewayAutomation, GatewayConfig, TradingMode
from SpyderA_Core.SpyderA05_EventManager import EventManager, EventType

# ==============================================================================
# MARKET DATA SYMBOLS CONFIGURATION
# ==============================================================================

# Visible Dashboard Symbols
VISIBLE_SYMBOLS = {
    'S&P CORE': {
        'SPY': {'type': 'STK', 'exchange': 'SMART', 'frequency': '1 second'},
        'SPX': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '1 second', 'symbol': 'SPX'},
        '/ES': {'type': 'FUT', 'exchange': 'CME', 'frequency': '1 second', 'symbol': 'ES', 'localSymbol': 'ESM5'},  # June 2025
    },
    'VOLATILITY': {
        'VIX': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '1 second', 'symbol': 'VIX'},
        'VIX9D': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '5 seconds', 'symbol': 'VIX9D'},
        'VXV': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '5 seconds', 'symbol': 'VXV'},
        'VXMT': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '5 seconds', 'symbol': 'VXMT'},
        'VVIX': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '5 seconds', 'symbol': 'VVIX'},
        'UVXY': {'type': 'STK', 'exchange': 'SMART', 'frequency': '5 seconds'},
    },
    'MARKET INTERNALS': {
        'TICK-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'TICK-NYSE', 'frequency': '1 second'},
        'TRIN-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'TRIN-NYSE', 'frequency': '5 seconds'},
        'ADD-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'ADD-NYSE', 'frequency': '5 seconds'},
        'CPC': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '5 seconds', 'symbol': 'CPC'},
        'PCALL': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '5 seconds', 'symbol': 'PCALL'},
        'SKEW': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '5 seconds', 'symbol': 'SKEW'},
    },
    'MAJOR INDICES': {
        'DIA': {'type': 'STK', 'exchange': 'SMART', 'frequency': '5 seconds'},
        'QQQ': {'type': 'STK', 'exchange': 'SMART', 'frequency': '5 seconds'},
        'IWM': {'type': 'STK', 'exchange': 'SMART', 'frequency': '5 seconds'},
    },
    'BONDS & CREDIT': {
        'TLT': {'type': 'STK', 'exchange': 'SMART', 'frequency': '15 seconds'},
        'LQD': {'type': 'STK', 'exchange': 'SMART', 'frequency': '15 seconds'},
    },
    'CORRELATIONS': {
        'DXY': {'type': 'IND', 'exchange': 'ICE', 'frequency': '15 seconds', 'symbol': 'DXY'},
        'GLD': {'type': 'STK', 'exchange': 'SMART', 'frequency': '15 seconds'},
    }
}

# Hidden Backend Symbols
HIDDEN_SYMBOLS = {
    'VIX_FUTURES': {
        'VX': {'type': 'FUT', 'exchange': 'CFE', 'frequency': '5 seconds', 'symbol': 'VX', 'localSymbol': 'VXM5'},  # June 2025
    },
    'ADDITIONAL_INTERNALS': {
        'ADVN-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'ADVN-NYSE', 'frequency': '5 seconds'},
        'DECN-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'DECN-NYSE', 'frequency': '5 seconds'},
        'UVOL-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'UVOL-NYSE', 'frequency': '5 seconds'},
        'DVOL-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'DVOL-NYSE', 'frequency': '5 seconds'},
        'VOLD-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'VOLD-NYSE', 'frequency': '5 seconds'},
        'NYHL-NYSE': {'type': 'IND', 'exchange': 'NYSE', 'symbol': 'NYHL-NYSE', 'frequency': '60 seconds'},
    },
    'ADDITIONAL_VOLATILITY': {
        'VXST': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '30 seconds', 'symbol': 'VXST'},
        'VXN': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '30 seconds', 'symbol': 'VXN'},
        'RVX': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '30 seconds', 'symbol': 'RVX'},
    },
    'PUT_CALL_RATIOS': {
        'CPCE': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '30 seconds', 'symbol': 'CPCE'},
        'CPCI': {'type': 'IND', 'exchange': 'CBOE', 'frequency': '30 seconds', 'symbol': 'CPCI'},
    },
    'NASDAQ_INTERNALS': {
        'TICK-NASDAQ': {'type': 'IND', 'exchange': 'NASDAQ', 'symbol': 'TICK-NASDAQ', 'frequency': '5 seconds'},
        'TRIN-NASDAQ': {'type': 'IND', 'exchange': 'NASDAQ', 'symbol': 'TRIN-NASDAQ', 'frequency': '5 seconds'},
    },
    'SECTOR_ETFS': {
        'XLF': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLK': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLE': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLV': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLI': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLY': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLP': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLU': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLRE': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLC': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
        'XLB': {'type': 'STK', 'exchange': 'SMART', 'frequency': '30 seconds'},
    }
}

# Options chain requirements
OPTIONS_TEST_SPECS = {
    'SPY_OPTIONS': {
        '0DTE': {'days': 0, 'strikes': 10},
        '1DTE': {'days': 1, 'strikes': 10},
        'WEEKLY': {'days': 7, 'strikes': 20},
        'MONTHLY': {'days': 30, 'strikes': 30},
    }
}

# ==============================================================================
# TEST CONFIGURATION
# ==============================================================================
TEST_CONFIG = {
    'host': '127.0.0.1',
    'port': 4002,  # Paper trading port
    'client_id': 999,  # Test client ID
    'account': 'DU123456',  # Demo account
    'use_mock': True,  # Set to False for real IB connection
    'log_level': logging.INFO
}

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
def setup_logging(level=logging.INFO):
    """Set up logging configuration for tests."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('spyder_broker_tests.log')
        ]
    )

# Create logger after function definition
logger = logging.getLogger(__name__)

# ==============================================================================
# MOCK IB CLIENT FOR TESTING
# ==============================================================================
class MockIBClient:
    """Mock IB client for testing without real connection."""
    
    def __init__(self):
        self.connected = False
        self.positions = []
        self.orders = []
        self.account_values = {
            'NetLiquidation': 100000.0,
            'BuyingPower': 200000.0,
            'AvailableFunds': 150000.0
        }
        self.market_data_callbacks = defaultdict(list)
        self.next_order_id = 1000
    
    def connect(self, host, port, clientId):
        """Mock connection."""
        self.connected = True
        return True
    
    def disconnect(self):
        """Mock disconnection."""
        self.connected = False
    
    def isConnected(self):
        """Check connection status."""
        return self.connected
    
    def reqMktData(self, contract, genericTickList="", snapshot=False):
        """Mock market data request."""
        from collections import namedtuple
        Ticker = namedtuple('Ticker', ['reqId', 'contract'])
        ticker = Ticker(reqId=len(self.market_data_callbacks) + 1, contract=contract)
        
        # Simulate some market data
        if hasattr(self, 'callbacks'):
            for cb in self.callbacks.get('tickPrice', []):
                # Simulate bid/ask/last
                cb(ticker.reqId, 1, 100.0, None)  # Bid
                cb(ticker.reqId, 2, 100.1, None)  # Ask
                cb(ticker.reqId, 4, 100.05, None) # Last
        
        return ticker
    
    def cancelMktData(self, ticker):
        """Mock cancel market data."""
        pass

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
        cls.event_manager = EventManager()
        
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
    def wait_for_event(self, event_type: EventType, timeout: float = 5.0) -> Optional[Any]:
        """Wait for specific event to occur."""
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
    """Test market data availability for all required symbols."""
    
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
        """Create IB contract from symbol configuration.
        
        NOTE: This method uses ib_insync directly for Index and Futures contracts.
        For production use, consider extending ContractBuilder with:
        - build_index(symbol, exchange) 
        - build_future(symbol, exchange, local_symbol)
        """
        contract_type = config.get('type', 'STK')
        
        try:
            if contract_type == 'STK':
                return self.contract_builder.build_stock(symbol)
            elif contract_type == 'IND':
                # Index contract - using ib_insync directly
                if HAS_IB_INSYNC:
                    contract = Index(
                        symbol=config.get('symbol', symbol),
                        exchange=config.get('exchange', 'CBOE'),
                        currency='USD'
                    )
                else:
                    # Mock for testing without ib_insync
                    contract = Mock()
                    contract.symbol = config.get('symbol', symbol)
                    contract.secType = 'IND'
                    contract.exchange = config.get('exchange', 'CBOE')
                    contract.currency = 'USD'
                return contract
            elif contract_type == 'FUT':
                # Futures contract - using ib_insync directly
                if HAS_IB_INSYNC:
                    contract = Future(
                        symbol=config.get('symbol', symbol),
                        exchange=config.get('exchange', 'CME'),
                        currency='USD'
                    )
                    # Set local symbol if provided (for specific contract months)
                    if config.get('localSymbol'):
                        contract.localSymbol = config['localSymbol']
                else:
                    # Mock for testing without ib_insync
                    contract = Mock()
                    contract.symbol = config.get('symbol', symbol)
                    contract.secType = 'FUT'
                    contract.exchange = config.get('exchange', 'CME')
                    contract.currency = 'USD'
                    if config.get('localSymbol'):
                        contract.localSymbol = config['localSymbol']
                return contract
            else:
                return None
        except Exception as e:
            logger.error(f"Error creating contract for {symbol}: {e}")
            return None
    
    @pytest.mark.skipif(TEST_CONFIG['use_mock'], reason="Requires real IB connection")
    def test_visible_symbols_availability(self):
        """Test all visible dashboard symbols."""
        logger.info("\n" + "="*70)
        logger.info("TESTING VISIBLE DASHBOARD SYMBOLS")
        logger.info("="*70)
        
        for category, symbols in VISIBLE_SYMBOLS.items():
            logger.info(f"\n{category}:")
            logger.info("-" * 40)
            
            for symbol, config in symbols.items():
                self._test_single_symbol(symbol, config, category)
                time.sleep(0.5)  # Rate limiting
    
    @pytest.mark.skipif(TEST_CONFIG['use_mock'], reason="Requires real IB connection")
    def test_hidden_symbols_availability(self):
        """Test all hidden backend symbols."""
        logger.info("\n" + "="*70)
        logger.info("TESTING HIDDEN BACKEND SYMBOLS")
        logger.info("="*70)
        
        for category, symbols in HIDDEN_SYMBOLS.items():
            logger.info(f"\n{category}:")
            logger.info("-" * 40)
            
            for symbol, config in symbols.items():
                self._test_single_symbol(symbol, config, category)
                time.sleep(0.5)  # Rate limiting
    
    @pytest.mark.skipif(TEST_CONFIG['use_mock'], reason="Requires real IB connection")
    def test_options_chain_availability(self):
        """Test SPY options chain data availability."""
        logger.info("\n" + "="*70)
        logger.info("TESTING SPY OPTIONS CHAINS")
        logger.info("="*70)
        
        for chain_type, spec in OPTIONS_TEST_SPECS['SPY_OPTIONS'].items():
            logger.info(f"\n{chain_type} Options:")
            logger.info("-" * 40)
            
            # Calculate expiration
            days_ahead = spec['days']
            expiration = datetime.now() + timedelta(days=days_ahead)
            
            # Test a few strikes around ATM
            spy_price = self._get_spy_price()
            if spy_price:
                strikes = self._generate_strikes(spy_price, spec['strikes'])
                
                success_count = 0
                for strike in strikes[:5]:  # Test first 5 strikes
                    # Test call
                    if self._test_option_contract('SPY', expiration, strike, 'C'):
                        success_count += 1
                    
                    # Test put
                    if self._test_option_contract('SPY', expiration, strike, 'P'):
                        success_count += 1
                    
                    time.sleep(0.3)  # Rate limiting
                
                logger.info(f"  Successfully tested {success_count}/10 contracts")
    
    def _test_single_symbol(self, symbol: str, config: Dict, category: str):
        """Test a single symbol subscription."""
        try:
            # Create contract
            contract = self.create_contract(symbol, config)
            if not contract:
                self.test_results['errors'].append({
                    'symbol': symbol,
                    'category': category,
                    'error': 'Failed to create contract'
                })
                logger.error(f"  {symbol}: Failed to create contract")
                return
            
            # Request market data
            req_id = self.spyder_client.request_market_data(contract)
            
            if req_id > 0:
                # Wait for data
                time.sleep(2)
                
                # Check if we received data
                ticker = self.spyder_client.get_market_data(req_id)
                
                if ticker and (ticker.bid or ticker.ask or ticker.last):
                    self.test_results['successful'].append({
                        'symbol': symbol,
                        'category': category,
                        'data': {
                            'bid': ticker.bid,
                            'ask': ticker.ask,
                            'last': ticker.last
                        }
                    })
                    logger.info(f"  ✅ {symbol}: Bid={ticker.bid}, Ask={ticker.ask}, Last={ticker.last}")
                else:
                    self.test_results['failed'].append({
                        'symbol': symbol,
                        'category': category,
                        'reason': 'No data received'
                    })
                    logger.warning(f"  ❌ {symbol}: No data received")
                
                # Cancel subscription
                self.spyder_client.cancel_market_data(req_id)
            else:
                self.test_results['failed'].append({
                    'symbol': symbol,
                    'category': category,
                    'reason': 'Subscription failed'
                })
                logger.warning(f"  ❌ {symbol}: Subscription failed")
                
        except Exception as e:
            self.test_results['errors'].append({
                'symbol': symbol,
                'category': category,
                'error': str(e)
            })
            logger.error(f"  ❌ {symbol}: Error - {e}")
    
    def _test_option_contract(self, symbol: str, expiration: datetime, strike: float, right: str) -> bool:
        """Test a single option contract."""
        try:
            # Create option contract
            exp_str = expiration.strftime('%Y%m%d')
            contract = self.spyder_client.create_option_contract(symbol, exp_str, strike, right)
            
            # Request market data
            req_id = self.spyder_client.request_market_data(contract)
            
            if req_id > 0:
                time.sleep(1)
                ticker = self.spyder_client.get_market_data(req_id)
                self.spyder_client.cancel_market_data(req_id)
                
                if ticker and (ticker.bid or ticker.ask):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"    Option test error: {e}")
            return False
    
    def _get_spy_price(self) -> Optional[float]:
        """Get current SPY price for options testing."""
        try:
            spy = self.contract_builder.build_stock('SPY')
            req_id = self.spyder_client.request_market_data(spy)
            
            if req_id > 0:
                time.sleep(2)
                ticker = self.spyder_client.get_market_data(req_id)
                self.spyder_client.cancel_market_data(req_id)
                
                if ticker and ticker.last:
                    return ticker.last
            
            return 450.0  # Default fallback
            
        except Exception:
            return 450.0
    
    def _generate_strikes(self, atm_price: float, count: int) -> List[float]:
        """Generate strike prices around ATM."""
        strikes = []
        
        # Round to nearest dollar
        atm_strike = round(atm_price)
        
        # Generate strikes
        for i in range(-count//2, count//2 + 1):
            strike = atm_strike + i
            if strike > 0:
                strikes.append(float(strike))
        
        return strikes
    
    def tearDown(self):
        """Generate summary report after tests."""
        super().tearDown()
        
        # Only generate report if we ran actual tests
        if self.test_results['successful'] or self.test_results['failed'] or self.test_results['errors']:
            self._generate_availability_report()
    
    def _generate_availability_report(self):
        """Generate comprehensive availability report."""
        logger.info("\n" + "="*70)
        logger.info("MARKET DATA AVAILABILITY REPORT")
        logger.info("="*70)
        
        total_tested = (len(self.test_results['successful']) + 
                       len(self.test_results['failed']) + 
                       len(self.test_results['errors']))
        
        logger.info(f"\nTotal Symbols Tested: {total_tested}")
        logger.info(f"Successful: {len(self.test_results['successful'])}")
        logger.info(f"Failed: {len(self.test_results['failed'])}")
        logger.info(f"Errors: {len(self.test_results['errors'])}")
        
        if self.test_results['failed']:
            logger.info("\n❌ FAILED SUBSCRIPTIONS (May need additional IBKR data subscriptions):")
            for item in self.test_results['failed']:
                logger.info(f"  - {item['symbol']} ({item['category']}): {item['reason']}")
        
        if self.test_results['errors']:
            logger.info("\n⚠️  ERRORS:")
            for item in self.test_results['errors']:
                logger.info(f"  - {item['symbol']} ({item['category']}): {item['error']}")
        
        # Generate subscription recommendations
        self._generate_subscription_recommendations()
    
    def _generate_subscription_recommendations(self):
        """Generate IBKR subscription recommendations based on failures."""
        logger.info("\n" + "="*70)
        logger.info("IBKR SUBSCRIPTION RECOMMENDATIONS")
        logger.info("="*70)
        
        failed_categories = defaultdict(list)
        for item in self.test_results['failed']:
            failed_categories[item['category']].append(item['symbol'])
        
        if 'S&P CORE' in failed_categories:
            if 'SPX' in failed_categories['S&P CORE']:
                logger.info("\n📊 For SPX Index:")
                logger.info("   - Subscribe to: CBOE Indexes (real-time)")
                logger.info("   - OR use delayed data if available")
            if '/ES' in failed_categories['S&P CORE']:
                logger.info("\n📊 For E-mini S&P Futures:")
                logger.info("   - Subscribe to: CME E-mini Futures")
        
        if 'VOLATILITY' in failed_categories:
            logger.info("\n📊 For Volatility Indices (VIX family):")
            logger.info("   - Subscribe to: CBOE Indexes")
            logger.info("   - This covers: VIX, VIX9D, VXV, VXMT, VVIX, SKEW")
        
        if 'MARKET INTERNALS' in failed_categories:
            logger.info("\n📈 For Market Internals:")
            logger.info("   - NYSE Internals: NYSE Market Data (Network A)")
            logger.info("   - This covers: TICK-NYSE, TRIN-NYSE, ADD-NYSE, VOLD-NYSE, etc.")
            logger.info("   - CBOE Put/Call: CBOE Indexes")
        
        if any(cat in failed_categories for cat in ['VIX_FUTURES', 'ADDITIONAL_VOLATILITY']):
            logger.info("\n📉 For VIX Futures:")
            logger.info("   - Subscribe to: CFE (CBOE Futures Exchange)")
        
        if 'NASDAQ_INTERNALS' in failed_categories:
            logger.info("\n📊 For NASDAQ Internals:")
            logger.info("   - Subscribe to: NASDAQ TotalView or Basic")
        
        if 'CORRELATIONS' in failed_categories and 'DXY' in failed_categories['CORRELATIONS']:
            logger.info("\n💱 For Currency Indices:")
            logger.info("   - DXY requires: ICE Data Services")
        
        logger.info("\n💡 Notes:")
        logger.info("   - Custom metrics (GEX, DEX, OGL, DIX, SWAN) are calculated internally")
        logger.info("   - Some indices may be available with delayed data (15-20 min)")
        logger.info("   - SPY options require: OPRA (US Options Add-on)")
        logger.info("   - Consider bundled packages for cost savings")
        
        logger.info("\n📝 To check your current subscriptions:")
        logger.info("   1. Log in to IBKR Account Management")
        logger.info("   2. Go to Settings > User Settings > Market Data Subscriptions")
        logger.info("   3. Compare with the recommendations above")

# ==============================================================================
# CONNECTION TESTS
# ==============================================================================
class TestSpyderClientIntegration(SpyderBrokerTestBase):
    """Test SpyderClient core functionality."""
    
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
    
    def test_error_handling(self):
        """Test error handling in client operations."""
        # Test invalid contract
        with self.assertRaises(ValueError):
            self.spyder_client.create_option_contract(
                'SPY', 'invalid_date', 450.0, 'X'  # Invalid right
            )

# ==============================================================================
# TEST RUNNER FUNCTION
# ==============================================================================
def run_tests(specific_test=None, use_real_connection=False):
    """
    Run integration tests.
    
    Args:
        specific_test: Specific test class to run (optional)
        use_real_connection: Use real IB connection instead of mocks
    """
    # Update configuration
    if use_real_connection:
        TEST_CONFIG['use_mock'] = False
        logger.info("Running with REAL IB connection")
    else:
        logger.info("Running with MOCK IB connection")
    
    # Create test suite
    if specific_test:
        # Handle string test class names
        if isinstance(specific_test, str):
            test_class = globals().get(specific_test)
            if test_class:
                suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
            else:
                logger.error(f"Test class '{specific_test}' not found")
                return False
        else:
            suite = unittest.TestLoader().loadTestsFromTestCase(specific_test)
    else:
        # Run all tests
        test_classes = [
            TestSpyderClientIntegration,
            TestMarketDataAvailability,  # Added market data tests
            # Add other test classes here
        ]
        
        suite = unittest.TestSuite()
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
    
    return result.wasSuccessful()

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run SpyderB_Broker integration tests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all tests with mocks
    python SpyderT02_BrokerTestSuite.py
    
    # Run with real IB connection
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
