#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 2025-01-06 16:00:00
@author: Spyder Agent

SPYDER - Automated SPY Options Trading System
SpyderT02_BrokerTestSuite

This module provides comprehensive integration testing for all SpyderB_Broker
modules, ensuring they work correctly together in production scenarios.

Key Features:
    - Complete test coverage for all broker modules
    - Mock and real IB connection support
    - Performance benchmarking
    - Thread safety verification
    - Error recovery testing
    - End-to-end trading scenarios

Test Categories:
    1. Connection lifecycle tests
    2. Order management tests
    3. Position tracking tests
    4. Account management tests
    5. Contract building tests
    6. Integration scenario tests
    7. Error handling tests
    8. Performance tests

Usage:
    # Run all tests with mocks
    python SpyderT02_BrokerTestSuite.py
    
    # Run with real IB connection
    python SpyderT02_BrokerTestSuite.py --real
    
    # Run specific test class
    python SpyderT02_BrokerTestSuite.py --test TestOrderManagerIntegration
    
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

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytest
from unittest.mock import Mock, patch, MagicMock, call

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
    return logging.getLogger(__name__)

logger = setup_logging(TEST_CONFIG['log_level'])

# ==============================================================================
# BASE TEST CLASS
# ==============================================================================
class SpyderBrokerTestBase(unittest.TestCase):
    """
    Base class for broker integration tests with common setup.
    
    Provides:
        - Event manager initialization
        - Mock/real IB connection setup
        - Common test utilities
        - Cleanup procedures
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once for all tests."""
        logger.info(f"Setting up {cls.__name__} test environment")
        
        # Initialize event manager
        cls.event_manager = EventManager()
        cls.event_manager.start()
        
        # Track created resources for cleanup
        cls._created_orders = []
        cls._created_positions = []
        
        # Initialize IB connection
        if TEST_CONFIG['use_mock']:
            cls._setup_mocks()
            logger.info("Using MOCK IB connection")
        else:
            cls._setup_real_connection()
            logger.info("Using REAL IB connection")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        logger.info(f"Tearing down {cls.__name__} test environment")
        
        # Stop event manager
        cls.event_manager.stop()
        
        # Disconnect from IB
        if hasattr(cls, 'spyder_client') and cls.spyder_client.is_connected():
            cls.spyder_client.disconnect()
            logger.info("Disconnected from IB")
    
    @classmethod
    def _setup_mocks(cls):
        """Set up mock IB connection for testing."""
        with patch('SpyderB_Broker.SpyderB01_SpyderClient.IB'):
            cls.ib_config = IBConfig(
                host=TEST_CONFIG['host'],
                port=TEST_CONFIG['port'],
                client_id=TEST_CONFIG['client_id']
            )
            cls.spyder_client = SpyderClient(cls.ib_config, cls.event_manager)
            
            # Mock connection methods
            cls.spyder_client.connect = Mock(return_value=True)
            cls.spyder_client.is_connected = Mock(return_value=True)
            cls.spyder_client.get_buying_power = Mock(return_value=100000.0)
            cls.spyder_client.get_account_info = Mock(return_value={
                'account': TEST_CONFIG['account'],
                'net_liquidation': 100000.0,
                'buying_power': 100000.0,
                'total_cash': 50000.0,
                'maintenance_margin': 0.0,
                'excess_liquidity': 100000.0
            })
            
            # Mock order placement
            cls.spyder_client.place_order = Mock(side_effect=cls._mock_place_order)
            cls.spyder_client.cancel_order = Mock(return_value=True)
            
            # Track mock calls
            cls._mock_orders = {}
            cls._next_order_id = 1000
    
    @classmethod
    def _mock_place_order(cls, contract, order):
        """Mock order placement."""
        order_id = cls._next_order_id
        cls._next_order_id += 1
        
        cls._mock_orders[order_id] = {
            'contract': contract,
            'order': order,
            'status': OrderStatus.SUBMITTED
        }
        
        # Simulate order fill after delay
        def simulate_fill():
            time.sleep(0.1)
            if order_id in cls._mock_orders:
                cls._mock_orders[order_id]['status'] = OrderStatus.FILLED
                cls.event_manager.emit_event(
                    EventType.ORDER_FILLED,
                    {
                        'order_id': order_id,
                        'symbol': contract.symbol,
                        'fill_quantity': order.totalQuantity,
                        'avg_fill_price': order.lmtPrice or 100.0,
                        'commission': 1.0
                    }
                )
        
        threading.Thread(target=simulate_fill, daemon=True).start()
        return order_id
    
    @classmethod
    def _setup_real_connection(cls):
        """Set up real IB connection for integration testing."""
        cls.ib_config = IBConfig(
            host=TEST_CONFIG['host'],
            port=TEST_CONFIG['port'],
            client_id=TEST_CONFIG['client_id']
        )
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
# ORDER MANAGEMENT TESTS
# ==============================================================================
class TestOrderManagerIntegration(SpyderBrokerTestBase):
    """Test OrderManager functionality."""
    
    def setUp(self):
        """Set up OrderManager for each test."""
        super().setUp()
        
        config = {
            'max_order_threads': 2,
            'order_timeout': 60,
            'max_retries': 3
        }
        self.order_manager = OrderManager(config, self.spyder_client, self.event_manager)
        self.order_manager.initialize()
        self.order_manager.start()
    
    def tearDown(self):
        """Clean up OrderManager after each test."""
        self.order_manager.stop()
        super().tearDown()
    
    def test_order_submission_flow(self):
        """Test complete order submission flow."""
        # Create order request
        order_req = OrderRequest(
            symbol='SPY',
            action=OrderAction.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=450.00,
            strategy_id='test_strategy'
        )
        
        # Submit order
        result = self.order_manager.submit_order(order_req)
        self.assertTrue(result['success'])
        self.assertIn('order_id', result)
        
        # Track for cleanup
        self._created_orders.append(result['order_id'])
        
        # Check order status
        status = self.order_manager.get_order_status(order_req.order_id)
        self.assertIsNotNone(status)
        self.assertIn('state', status)
        
        logger.info(f"Order submitted: {result}")
    
    def test_order_validation(self):
        """Test order validation rules."""
        # Test invalid quantity
        invalid_order = OrderRequest(
            symbol='SPY',
            action=OrderAction.BUY,
            quantity=0,  # Invalid
            order_type=OrderType.MARKET
        )
        
        validation = self.order_manager.validate_order(invalid_order)
        self.assertFalse(validation.is_valid)
        self.assertIn('Quantity must be positive', validation.errors)
        
        # Test valid order
        valid_order = OrderRequest(
            symbol='SPY',
            action=OrderAction.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        validation = self.order_manager.validate_order(valid_order)
        self.assertTrue(validation.is_valid)
        self.assertEqual(len(validation.errors), 0)
    
    def test_order_cancellation(self):
        """Test order cancellation."""
        # Submit order
        order_req = OrderRequest(
            symbol='SPY',
            action=OrderAction.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=450.00
        )
        
        result = self.order_manager.submit_order(order_req)
        order_id = result['order_id']
        self._created_orders.append(order_id)
        
        # Cancel order
        cancel_result = self.order_manager.cancel_order(order_id)
        self.assertTrue(cancel_result['success'])
        
        # Verify status
        status = self.order_manager.get_order_status(order_req.order_id)
        self.assertEqual(status['state'], 'cancelled')
    
    def test_concurrent_orders(self):
        """Test concurrent order processing."""
        orders_submitted = []
        num_orders = 5
        
        # Submit multiple orders
        for i in range(num_orders):
            order_req = OrderRequest(
                symbol='SPY',
                action=OrderAction.BUY if i % 2 == 0 else OrderAction.SELL,
                quantity=100,
                order_type=OrderType.LIMIT,
                limit_price=450.00 + i
            )
            
            result = self.order_manager.submit_order(order_req)
            self.assertTrue(result['success'])
            orders_submitted.append(result['order_id'])
            self._created_orders.append(result['order_id'])
        
        # Check all orders
        for order_id in orders_submitted:
            status = self.order_manager.get_order_status(order_id)
            self.assertIsNotNone(status)
        
        logger.info(f"Successfully submitted {num_orders} concurrent orders")
    
    def test_order_modification(self):
        """Test order modification."""
        # Submit initial order
        order_req = OrderRequest(
            symbol='SPY',
            action=OrderAction.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=450.00
        )
        
        result = self.order_manager.submit_order(order_req)
        order_id = result['order_id']
        self._created_orders.append(order_id)
        
        # Modify order
        modifications = {
            'limit_price': 451.00,
            'quantity': 150
        }
        
        modify_result = self.order_manager.modify_order(order_id, modifications)
        self.assertTrue(modify_result['success'])

# ==============================================================================
# POSITION TRACKING TESTS
# ==============================================================================
class TestPositionTrackerIntegration(SpyderBrokerTestBase):
    """Test PositionTracker functionality."""
    
    def setUp(self):
        """Set up PositionTracker for each test."""
        super().setUp()
        
        self.position_tracker = PositionTracker(
            self.spyder_client,
            event_manager=self.event_manager
        )
        self.position_tracker.initialize()
        self.position_tracker.start()
    
    def tearDown(self):
        """Clean up PositionTracker after each test."""
        self.position_tracker.stop()
        super().tearDown()
    
    def test_position_lifecycle(self):
        """Test position creation, update, and closure."""
        # Add position
        position_data = {
            'symbol': 'SPY',
            'quantity': 100,
            'entry_price': 450.00,
            'strategy_id': 'test_strategy',
            'position_type': 'long'
        }
        
        position_id = self.position_tracker.add_position(position_data)
        self.assertIsNotNone(position_id)
        self._created_positions.append(position_id)
        
        # Get position
        position = self.position_tracker.get_position(position_id)
        self.assertIsNotNone(position)
        self.assertEqual(position.symbol, 'SPY')
        self.assertEqual(position.quantity, 100)
        self.assertEqual(position.entry_price, 450.00)
        
        # Update position
        updates = {
            'current_price': 451.00,
            'unrealized_pnl': 100.00
        }
        
        success = self.position_tracker.update_position(position_id, updates)
        self.assertTrue(success)
        
        # Verify update
        updated_position = self.position_tracker.get_position(position_id)
        self.assertEqual(updated_position.current_price, 451.00)
        self.assertEqual(updated_position.unrealized_pnl, 100.00)
        
        # Close position
        success = self.position_tracker.close_position(position_id, 451.00)
        self.assertTrue(success)
        
        # Verify closed
        position = self.position_tracker.get_position(position_id)
        self.assertIsNone(position)  # Should be moved to closed positions
        
        # Check closed positions
        closed = self.position_tracker.get_closed_positions(limit=1)
        self.assertEqual(len(closed), 1)
        self.assertEqual(closed[0].exit_price, 451.00)
    
    def test_portfolio_metrics(self):
        """Test portfolio metrics calculation."""
        # Add multiple positions
        positions = [
            {'symbol': 'SPY', 'quantity': 100, 'entry_price': 450.00, 'current_price': 451.00},
            {'symbol': 'SPY', 'quantity': -50, 'entry_price': 451.00, 'current_price': 451.00},  # Short
            {'symbol': 'SPY', 'quantity': 1, 'entry_price': 450.00, 'current_price': 451.00,
             'is_option': True, 'strike': 455.0, 'right': 'C', 'expiry': '20250620'}
        ]
        
        for pos_data in positions:
            pos_id = self.position_tracker.add_position(pos_data)
            self._created_positions.append(pos_id)
        
        # Get metrics
        metrics = self.position_tracker.get_portfolio_metrics()
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics.open_positions, 3)
        self.assertGreater(metrics.total_market_value, 0)
        self.assertEqual(metrics.long_positions, 2)
        self.assertEqual(metrics.short_positions, 1)
        
        logger.info(f"Portfolio metrics: {metrics}")
    
    def test_risk_alerts(self):
        """Test risk alert generation."""
        # Add large position
        position_data = {
            'symbol': 'SPY',
            'quantity': 1000,  # Large position
            'entry_price': 450.00,
            'current_price': 450.00,
            'market_value': 450000.00
        }
        
        pos_id = self.position_tracker.add_position(position_data)
        self._created_positions.append(pos_id)
        
        # Check for alerts
        alerts = self.position_tracker.check_risk_alerts()
        self.assertIsInstance(alerts, list)
        
        # Should have concentration risk alert
        concentration_alerts = [a for a in alerts if a['type'] == 'position_concentration']
        self.assertGreater(len(concentration_alerts), 0)
        
        logger.info(f"Risk alerts: {alerts}")
    
    def test_performance_tracking(self):
        """Test performance metrics calculation."""
        # Add winning position
        pos_id = self.position_tracker.add_position({
            'symbol': 'SPY',
            'quantity': 100,
            'entry_price': 450.00,
            'current_price': 451.00
        })
        self._created_positions.append(pos_id)
        
        # Close with profit
        self.position_tracker.close_position(pos_id, 452.00)
        
        # Add losing position
        pos_id2 = self.position_tracker.add_position({
            'symbol': 'SPY',
            'quantity': 100,
            'entry_price': 450.00,
            'current_price': 449.00
        })
        self._created_positions.append(pos_id2)
        
        # Close with loss
        self.position_tracker.close_position(pos_id2, 448.00)
        
        # Get performance metrics
        metrics = self.position_tracker.get_portfolio_metrics()
        performance = metrics.performance_metrics
        
        self.assertEqual(performance.total_trades, 2)
        self.assertEqual(performance.winning_trades, 1)
        self.assertEqual(performance.losing_trades, 1)
        self.assertEqual(performance.win_rate, 0.5)
        self.assertGreater(performance.average_win, 0)
        self.assertLess(performance.average_loss, 0)

# ==============================================================================
# ACCOUNT MANAGEMENT TESTS
# ==============================================================================
class TestAccountManagerIntegration(SpyderBrokerTestBase):
    """Test AccountManager functionality."""
    
    def setUp(self):
        """Set up AccountManager for each test."""
        super().setUp()
        
        self.account_manager = AccountManager(
            self.spyder_client,
            self.event_manager
        )
        self.account_manager.initialize()
        self.account_manager.start()
    
    def tearDown(self):
        """Clean up AccountManager after each test."""
        self.account_manager.stop()
        super().tearDown()
    
    def test_account_sync(self):
        """Test account synchronization with broker."""
        # Get account info
        account_info = self.account_manager.get_account_info()
        self.assertIsNotNone(account_info)
        self.assertEqual(account_info.account_id, TEST_CONFIG['account'])
        
        # Check balance
        balance = self.account_manager.get_account_balance()
        self.assertIsNotNone(balance)
        self.assertGreater(balance.net_liquidation, 0)
        self.assertGreaterEqual(balance.buying_power, 0)
        
        # Check buying power
        buying_power = self.account_manager.get_buying_power()
        self.assertGreater(buying_power, 0)
        
        logger.info(f"Account balance: {balance}")
    
    def test_risk_assessment(self):
        """Test risk metrics calculation."""
        # Get risk metrics
        risk_metrics = self.account_manager.get_risk_metrics()
        self.assertIsNotNone(risk_metrics)
        self.assertIn(risk_metrics.risk_status.value, ['normal', 'warning', 'critical'])
        self.assertGreaterEqual(risk_metrics.margin_usage, 0)
        self.assertLessEqual(risk_metrics.margin_usage, 1)
        
        # Check trading allowed
        allowed, reason = self.account_manager.check_trading_allowed(order_value=1000.0)
        self.assertIsInstance(allowed, bool)
        self.assertIsInstance(reason, str)
        
        if allowed:
            self.assertEqual(reason, "Trading allowed")
        
        logger.info(f"Risk metrics: {risk_metrics}")
    
    def test_pdt_check(self):
        """Test pattern day trader checking."""
        pdt_status = self.account_manager.check_pattern_day_trader()
        
        self.assertIn('is_pdt', pdt_status)
        self.assertIn('day_trades_remaining', pdt_status)
        self.assertIn('meets_requirement', pdt_status)
        
        self.assertIsInstance(pdt_status['is_pdt'], bool)
        self.assertGreaterEqual(pdt_status['day_trades_remaining'], 0)
        
        logger.info(f"PDT status: {pdt_status}")
    
    def test_performance_metrics(self):
        """Test performance metrics calculation."""
        account_info = self.account_manager.get_account_info()
        
        if account_info:
            metrics = account_info.performance_metrics
            self.assertIsNotNone(metrics)
            
            # Metrics may be zero without history
            self.assertIsInstance(metrics.sharpe_ratio, float)
            self.assertIsInstance(metrics.sortino_ratio, float)
            self.assertIsInstance(metrics.max_drawdown, float)
            
            logger.info(f"Performance metrics: {metrics}")

# ==============================================================================
# CONTRACT BUILDER TESTS
# ==============================================================================
class TestContractBuilderIntegration(SpyderBrokerTestBase):
    """Test ContractBuilder functionality."""
    
    def setUp(self):
        """Set up ContractBuilder for each test."""
        super().setUp()
        self.contract_builder = ContractBuilder()
    
    def test_stock_contracts(self):
        """Test stock contract creation."""
        # SPY stock
        spy = self.contract_builder.build_spy()
        self.assertEqual(spy.symbol, 'SPY')
        self.assertEqual(spy.secType, 'STK')
        self.assertEqual(spy.exchange, 'ARCA')
        self.assertEqual(spy.currency, 'USD')
        
        # Generic stock
        aapl = self.contract_builder.build_stock('AAPL')
        self.assertEqual(aapl.symbol, 'AAPL')
        self.assertEqual(aapl.secType, 'STK')
        self.assertEqual(aapl.exchange, 'SMART')
    
    def test_option_contracts(self):
        """Test option contract creation."""
        # Get next expiry
        next_expiry = self.contract_builder.get_next_expiry()
        self.assertEqual(len(next_expiry), 8)  # YYYYMMDD format
        
        # Build option
        spy_call = self.contract_builder.build_spy_option(next_expiry, 450.0, 'C')
        self.assertEqual(spy_call.symbol, 'SPY')
        self.assertEqual(spy_call.strike, 450.0)
        self.assertEqual(spy_call.right, 'C')
        self.assertEqual(spy_call.lastTradeDateOrContractMonth, next_expiry)
        
        # Build put
        spy_put = self.contract_builder.build_spy_option(next_expiry, 440.0, 'P')
        self.assertEqual(spy_put.right, 'P')
    
    def test_spread_contracts(self):
        """Test spread contract creation."""
        next_expiry = self.contract_builder.get_next_expiry()
        
        # Vertical spread
        spread = self.contract_builder.build_vertical_spread(
            'SPY', next_expiry, 445.0, 450.0, 'C'
        )
        self.assertEqual(spread.secType, 'BAG')
        self.assertEqual(len(spread.comboLegs), 2)
        
        # Verify legs
        self.assertEqual(spread.comboLegs[0].action, 'BUY')
        self.assertEqual(spread.comboLegs[1].action, 'SELL')
        
        # Iron condor
        condor = self.contract_builder.build_iron_condor(
            'SPY', next_expiry, 430.0, 425.0, 455.0, 460.0
        )
        self.assertEqual(len(condor.comboLegs), 4)
    
    def test_expiry_calculations(self):
        """Test expiration date calculations."""
        # Monthly expiry
        monthly = self.contract_builder.get_monthly_expiry(2025, 6)
        self.assertEqual(len(monthly), 8)  # YYYYMMDD
        
        # Parse date
        date = datetime.strptime(monthly, '%Y%m%d')
        self.assertEqual(date.year, 2025)
        self.assertEqual(date.month, 6)
        # Should be third Friday
        self.assertEqual(date.weekday(), 4)  # Friday
        
        # Weekly expiries
        weeklies = self.contract_builder.get_weekly_expiries(datetime.now().date(), 4)
        self.assertEqual(len(weeklies), 4)
        
        # All should be Fridays (or Thursday if Friday is holiday)
        for expiry in weeklies:
            date = datetime.strptime(expiry, '%Y%m%d')
            self.assertIn(date.weekday(), [3, 4])  # Thursday or Friday
        
        logger.info(f"Weekly expiries: {weeklies}")
    
    def test_atm_strike_calculation(self):
        """Test ATM strike calculation."""
        # Mock current price
        with patch.object(self.spyder_client, 'get_current_price', return_value=450.50):
            atm_strike = self.contract_builder.get_atm_strike('SPY')
            self.assertEqual(atm_strike, 451.0)  # Rounded to nearest strike

# ==============================================================================
# CONNECTION MANAGER TESTS
# ==============================================================================
class ConnectionManagerIntegration(SpyderBrokerTestBase):
    """Test ConnectionManager functionality."""
    
    @pytest.mark.skipif(TEST_CONFIG['use_mock'], reason="Requires real IB connection")
    def test_connection_with_retry(self):
        """Test connection with retry logic."""
        config = ConnectionConfig(
            host=TEST_CONFIG['host'],
            port=TEST_CONFIG['port'],
            client_id=TEST_CONFIG['client_id'] + 1,  # Different client ID
            max_retries=2,
            initial_retry_delay=1
        )
        
        connection_manager = ConnectionManager(config)
        
        try:
            # Test connection
            success = connection_manager.connect_with_backoff()
            self.assertTrue(success)
            
            # Test status
            status = connection_manager.get_connection_status()
            self.assertTrue(status['connected'])
            self.assertIn('uptime', status)
            self.assertIn('connection_quality', status)
            
        finally:
            # Disconnect
            connection_manager.disconnect_gracefully()
    
    def test_scheduled_connection(self):
        """Test scheduled connection based on market hours."""
        config = ConnectionConfig(
            connect_time="09:30",
            disconnect_time="16:00",
            timezone="America/New_York"
        )
        
        connection_manager = ConnectionManager(config)
        
        # Check if should be connected (depends on current time)
        status = connection_manager.get_connection_status()
        self.assertIn('should_be_connected', status)
        self.assertIsInstance(status['should_be_connected'], bool)
        
        logger.info(f"Connection schedule status: {status}")

# ==============================================================================
# GATEWAY AUTOMATION TESTS
# ==============================================================================
class TestGatewayAutomationIntegration(SpyderBrokerTestBase):
    """Test GatewayAutomation functionality."""
    
    @pytest.mark.skipif(
        TEST_CONFIG['use_mock'] or sys.platform == "win32",
        reason="Requires Linux/Mac with IB Gateway installed"
    )
    def test_gateway_lifecycle(self):
        """Test gateway startup and shutdown."""
        config = GatewayConfig(
            mode=TradingMode.PAPER,
            username="test_user",
            password="test_pass",
            auto_restart=False,
            health_check_enabled=False
        )
        
        automation = GatewayAutomation(config)
        
        # Check status (gateway might not be installed)
        status = automation.get_status()
        self.assertIsNotNone(status)
        self.assertIn('gateway_running', status)
        
        logger.info(f"Gateway status: {status}")

# ==============================================================================
# END-TO-END INTEGRATION TESTS
# ==============================================================================
class TestEndToEndTrading(SpyderBrokerTestBase):
    """Test end-to-end trading scenarios."""
    
    def setUp(self):
        """Set up all components for end-to-end test."""
        super().setUp()
        
        # Initialize all managers
        self.order_manager = OrderManager(
            {'max_order_threads': 2},
            self.spyder_client,
            self.event_manager
        )
        self.position_tracker = PositionTracker(
            self.spyder_client,
            event_manager=self.event_manager
        )
        self.account_manager = AccountManager(
            self.spyder_client,
            self.event_manager
        )
        
        # Initialize all
        for manager in [self.order_manager, self.position_tracker, self.account_manager]:
            manager.initialize()
            manager.start()
    
    def tearDown(self):
        """Clean up all components."""
        for manager in [self.order_manager, self.position_tracker, self.account_manager]:
            manager.stop()
        super().tearDown()
    
    def test_complete_trade_flow(self):
        """Test complete trade flow from order to position to P&L."""
        # Check initial state
        initial_buying_power = self.account_manager.get_buying_power()
        logger.info(f"Initial buying power: ${initial_buying_power:,.2f}")
        
        # Submit order
        order_req = OrderRequest(
            symbol='SPY',
            action=OrderAction.BUY,
            quantity=10,
            order_type=OrderType.LIMIT,
            limit_price=450.00,
            strategy_id='test_strategy'
        )
        
        result = self.order_manager.submit_order(order_req)
        self.assertTrue(result['success'])
        order_id = result['order_id']
        self._created_orders.append(order_id)
        
        # Wait for fill (simulated)
        if TEST_CONFIG['use_mock']:
            # Simulate order fill event
            self.event_manager.emit_event(
                EventType.ORDER_FILLED,
                {
                    'order_id': order_id,
                    'symbol': 'SPY',
                    'fill_quantity': 10,
                    'avg_fill_price': 450.00,
                    'commission': 1.00
                }
            )
        
        # Wait for processing
        time.sleep(0.5)
        
        # Check position created
        positions = self.position_tracker.get_positions_by_symbol('SPY')
        self.assertGreater(len(positions), 0)
        
        position = positions[0]
        self.assertEqual(position.quantity, 10)
        self.assertEqual(position.entry_price, 450.00)
        
        # Check account updated
        new_buying_power = self.account_manager.get_buying_power()
        # Buying power should decrease (in real scenario)
        
        # Get portfolio metrics
        metrics = self.position_tracker.get_portfolio_metrics()
        self.assertGreater(metrics.open_positions, 0)
        self.assertEqual(metrics.total_market_value, 10 * 450.00)
        
        logger.info(f"Trade flow completed - Position: {position}")
    
    def test_option_spread_flow(self):
        """Test option spread order flow."""
        contract_builder = ContractBuilder()
        next_expiry = contract_builder.get_next_expiry()
        
        # Create a bull put spread
        orders = [
            OrderRequest(
                symbol='SPY',
                action=OrderAction.SELL,
                quantity=1,
                order_type=OrderType.LIMIT,
                limit_price=2.00,
                is_option=True,
                expiry=next_expiry,
                strike=445.0,
                right='P',
                strategy_id='bull_put_spread'
            ),
            OrderRequest(
                symbol='SPY',
                action=OrderAction.BUY,
                quantity=1,
                order_type=OrderType.LIMIT,
                limit_price=1.00,
                is_option=True,
                expiry=next_expiry,
                strike=440.0,
                right='P',
                strategy_id='bull_put_spread'
            )
        ]
        
        # Submit both orders
        submitted_orders = []
        for order in orders:
            result = self.order_manager.submit_order(order)
            self.assertTrue(result['success'])
            submitted_orders.append(result['order_id'])
            self._created_orders.append(result['order_id'])
        
        logger.info(f"Bull put spread submitted: {submitted_orders}")

# ==============================================================================
# ERROR HANDLING TESTS
# ==============================================================================
class TestErrorHandlingIntegration(SpyderBrokerTestBase):
    """Test error handling across modules."""
    
    def test_connection_failure_handling(self):
        """Test handling of connection failures."""
        # Create client with bad connection params
        bad_config = IBConfig(
            host='invalid_host',
            port=9999,
            client_id=TEST_CONFIG['client_id']
        )
        
        bad_client = SpyderClient(bad_config, self.event_manager)
        
        # Should handle connection failure gracefully
        success = bad_client.connect()
        self.assertFalse(success)
        
        # Operations should fail gracefully
        account_info = bad_client.get_account_info()
        self.assertEqual(account_info, {})
    
    def test_invalid_order_handling(self):
        """Test handling of invalid orders."""
        order_manager = OrderManager(
            {'max_order_threads': 2},
            self.spyder_client,
            self.event_manager
        )
        order_manager.initialize()
        order_manager.start()
        
        try:
            # Invalid order (negative quantity)
            invalid_order = OrderRequest(
                symbol='SPY',
                action=OrderAction.BUY,
                quantity=-100,
                order_type=OrderType.MARKET
            )
            
            result = order_manager.submit_order(invalid_order)
            self.assertFalse(result['success'])
            self.assertIn('error', result)
            self.assertIn('Quantity must be positive', result['error'])
            
        finally:
            order_manager.stop()
    
    def test_event_propagation(self):
        """Test error event propagation through EventManager."""
        error_events = []
        
        def error_handler(event):
            error_events.append(event)
        
        # Subscribe to errors
        self.event_manager.subscribe(EventType.BROKER_ERROR, error_handler)
        
        try:
            # Trigger an error
            self.event_manager.emit_event(
                EventType.BROKER_ERROR,
                {
                    'error_code': 504,
                    'error_string': 'Not connected',
                    'timestamp': datetime.now()
                }
            )
            
            # Wait for event processing
            time.sleep(0.1)
            
            # Check event received
            self.assertEqual(len(error_events), 1)
            self.assertEqual(error_events[0].data['error_code'], 504)
            
        finally:
            self.event_manager.unsubscribe(EventType.BROKER_ERROR, error_handler)

# ==============================================================================
# PERFORMANCE TESTS
# ==============================================================================
class TestPerformanceIntegration(SpyderBrokerTestBase):
    """Test performance and stress scenarios."""
    
    def test_high_frequency_orders(self):
        """Test system under high order load."""
        order_manager = OrderManager(
            {'max_order_threads': 4},
            self.spyder_client,
            self.event_manager
        )
        order_manager.initialize()
        order_manager.start()
        
        try:
            start_time = time.time()
            num_orders = 100
            
            # Submit many orders rapidly
            for i in range(num_orders):
                order = OrderRequest(
                    symbol='SPY',
                    action=OrderAction.BUY if i % 2 == 0 else OrderAction.SELL,
                    quantity=100,
                    order_type=OrderType.LIMIT,
                    limit_price=450.00 + (i * 0.01)
                )
                
                result = order_manager.submit_order(order)
                if result['success']:
                    self._created_orders.append(result['order_id'])
            
            elapsed = time.time() - start_time
            orders_per_second = num_orders / elapsed
            
            logger.info(f"Submitted {num_orders} orders in {elapsed:.2f}s "
                       f"({orders_per_second:.1f} orders/second)")
            
            # Should handle at least 10 orders/second
            self.assertGreater(orders_per_second, 10)
            
        finally:
            order_manager.stop()
    
    def test_concurrent_position_updates(self):
        """Test concurrent position updates."""
        position_tracker = PositionTracker(
            self.spyder_client,
            event_manager=self.event_manager
        )
        position_tracker.initialize()
        position_tracker.start()
        
        try:
            # Create positions
            position_ids = []
            for i in range(10):
                pos_id = position_tracker.add_position({
                    'symbol': f'TEST{i}',
                    'quantity': 100,
                    'entry_price': 100.0 + i
                })
                position_ids.append(pos_id)
                self._created_positions.append(pos_id)
            
            # Concurrent updates
            def update_position(pos_id, price):
                position_tracker.update_position(
                    pos_id,
                    {
                        'current_price': price,
                        'unrealized_pnl': (price - 100.0) * 100
                    }
                )
            
            threads = []
            for i, pos_id in enumerate(position_ids):
                for j in range(10):  # 10 updates per position
                    thread = threading.Thread(
                        target=update_position,
                        args=(pos_id, 100.0 + j)
                    )
                    threads.append(thread)
                    thread.start()
            
            # Wait for all updates
            for thread in threads:
                thread.join()
            
            # Verify all positions updated
            for pos_id in position_ids:
                pos = position_tracker.get_position(pos_id)
                self.assertIsNotNone(pos)
                self.assertGreater(pos.last_update, datetime.now() - timedelta(seconds=5))
            
            logger.info(f"Successfully processed {len(threads)} concurrent updates")
                
        finally:
            position_tracker.stop()

# ==============================================================================
# TEST RUNNER
# ==============================================================================
def run_integration_tests(specific_test=None, use_real_connection=False):
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
        suite = unittest.TestLoader().loadTestsFromTestCase(specific_test)
    else:
        # Run all tests
        test_classes = [
            TestSpyderClientIntegration,
            TestOrderManagerIntegration,
            TestPositionTrackerIntegration,
            TestAccountManagerIntegration,
            TestContractBuilderIntegration,
            TestConnectionManagerIntegration,
            TestEndToEndTrading,
            TestErrorHandlingIntegration,
            TestPerformanceIntegration
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
    logger.info(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
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
    
    # Run specific test class
    python SpyderT02_BrokerTestSuite.py --test TestOrderManagerIntegration
    
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
    
    # Set logging level
    if args.verbose:
        TEST_CONFIG['log_level'] = logging.DEBUG
        logger.setLevel(logging.DEBUG)
    
    # Run tests
    if args.test:
        # Run specific test
        test_class = globals().get(args.test)
        if test_class:
            success = run_integration_tests(test_class, args.real)
        else:
            logger.error(f"Test class '{args.test}' not found")
            logger.info("Available test classes:")
            for name, obj in globals().items():
                if name.startswith('Test') and isinstance(obj, type):
                    logger.info(f"  - {name}")
            success = False
    else:
        # Run all tests
        success = run_integration_tests(use_real_connection=args.real)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
