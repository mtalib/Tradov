#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB35_IBKRMessageTranslator.py
Purpose: IBKR Client Portal Web API message translation services

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-01-24 Time: 12:00:00

Module Description:
    This module provides translation services between IBKR API format and SPYDER format.
    It handles conversion of market data, orders, positions, and account information
    to ensure compatibility with existing SPYDER components. The module implements
    robust translation mechanisms with proper error handling and statistics tracking.

Module Constants:
    DEFAULT_EXCHANGE_CODE (str): Default exchange code for unknown exchanges (default: "SMART")
    MAX_TRANSLATION_ERRORS (int): Maximum translation errors before logging warning (default: 10)
    TIMESTAMP_FORMAT (str): Default timestamp format for parsing (default: "%Y-%m-%dT%H:%M:%S%z")

Change Log:
    2025-01-24 (v1.0.0):
        - Initial module creation following Spyder template standards
        - Implemented comprehensive message translation
        - Added market data format translation
        - Implemented order status translation
        - Added position information translation
        - Implemented account summary translation
        - Added timestamp normalization
        - Implemented symbol and exchange mapping
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import uuid
import warnings
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from threading import Lock, Event as ThreadEvent, RLock

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Safe imports with fallbacks
try:
    from SpyderU_Utilities.SpyderU07_Constants import BaseConstants
except ImportError:
    BaseConstants = None

# Import SPYDER data structures if available
try:
    from SpyderU_Utilities.SpyderU09_DataTypes import (
        MarketDataTick, Order, Position, AccountSummary
    )
    HAS_SPYDER_TYPES = True
except ImportError:
    # Fallback data structures for testing
    HAS_SPYDER_TYPES = False

    @dataclass
    class MarketDataTick:
        symbol: str
        last_price: float
        bid: float
        ask: float
        volume: int
        timestamp: datetime

    @dataclass
    class Order:
        order_id: str
        symbol: str
        side: str
        order_type: str
        quantity: float
        price: Optional[float]
        status: str
        filled_quantity: float

    @dataclass
    class Position:
        symbol: str
        quantity: float
        avg_price: float
        market_value: float
        unrealized_pnl: float

    @dataclass
    class AccountSummary:
        account_id: str
        net_liquidation: float
        total_cash: float
        buying_power: float


# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_EXCHANGE_CODE = "SMART"
MAX_TRANSLATION_ERRORS = 10
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

# ==============================================================================
# ENUMS
# ==============================================================================
class ModuleState(Enum):
    """Module operational states"""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()

class TranslationType(Enum):
    """Translation type enumeration."""
    MARKET_DATA = "market_data"
    ORDER = "order"
    POSITION = "position"
    ACCOUNT = "account"
    ORDER_REQUEST = "order_request"

    @classmethod
    def to_standard(cls, ibkr_exchange: str) -> str:
        """Convert IBKR exchange code to standard name."""
        return cls.IBKR_TO_STANDARD.get(ibkr_exchange, ibkr_exchange)

    @classmethod
    def to_ibkr(cls, standard_exchange: str) -> str:
        """Convert standard exchange name to IBKR code."""
        for ibkr, standard in cls.IBKR_TO_STANDARD.items():
            if standard == standard_exchange:
                return ibkr
        return 'SMART'  # Default to SMART routing


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
class ExchangeMap:
    """Maps IBKR exchange codes to standard exchange names."""

    IBKR_TO_STANDARD = {
        'SMART': 'SMART',
        'NYSE': 'NYSE',
        'NASDAQ': 'NASDAQ',
        'ARCA': 'NYSE ARCA',
        'BATS': 'BATS',
        'ISLAND': 'NASDAQ',
        'CBOE': 'CBOE',
        'AMEX': 'AMEX',
        'PSE': 'PACIFIC',
        'PHLX': 'PHILADELPHIA'
    }

    @classmethod
    def to_standard(cls, ibkr_exchange: str) -> str:
        """Convert IBKR exchange code to standard name."""
        return cls.IBKR_TO_STANDARD.get(ibkr_exchange, ibkr_exchange)

    @classmethod
    def to_ibkr(cls, standard_exchange: str) -> str:
        """Convert standard exchange name to IBKR code."""
        for ibkr, standard in cls.IBKR_TO_STANDARD.items():
            if standard == standard_exchange:
                return ibkr
        return DEFAULT_EXCHANGE_CODE  # Default to SMART routing


class SymbolMap:
    """Maps symbols between different formats."""

    # Common symbol mappings
    SYMBOL_MAPPINGS = {
        # IBKR uses .O for options, SPYDER might use different format
    }

    @classmethod
    def normalize_symbol(cls, symbol: str) -> str:
        """Normalize symbol format."""
        # Remove whitespace and convert to uppercase
        return symbol.strip().upper()

    @classmethod
    def format_option_symbol(cls, symbol: str, strike: float,
                           right: str, expiration: str) -> str:
        """Format option symbol in SPYDER format."""
        # Example: SPY_20231215_450_C
        return f"{symbol}_{expiration}_{int(strike)}_{right[0]}"


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MessageTranslator:
    """
    Translates messages between IBKR API format and SPYDER format.

    This class provides methods to convert various data types between the
    IBKR Client Portal API format and the format expected by SPYDER components.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        state: Current module state
        exchange_map: Exchange mapping utility
        symbol_map: Symbol mapping utility
        _state_lock: Thread lock for state management
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(self):
        """Initialize Message Translator."""
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # State management
        self.state = ModuleState.INITIALIZING
        self._state_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Translation utilities
        self.exchange_map = ExchangeMap()
        self.symbol_map = SymbolMap()

        # Translation statistics
        self._stats = {
            'market_data_translated': 0,
            'orders_translated': 0,
            'positions_translated': 0,
            'accounts_translated': 0,
            'translation_errors': 0
        }

        self.state = ModuleState.READY
        self.logger.info("MessageTranslator initialized")

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    def initialize(self) -> bool:
        """
        Initialize the message translator with all necessary setup.

        Returns:
            bool: True if initialization successful
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.INITIALIZING:
                    self.logger.warning(f"Cannot initialize from state: {self.state}")
                    return False

                self.logger.info(f"Initializing {self.__class__.__name__}...")

                # Perform initialization tasks
                if not self._validate_configuration():
                    return False

                if not self._setup_resources():
                    return False

                self.state = ModuleState.READY
                self.logger.info(f"{self.__class__.__name__} initialization completed")
                return True

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            self.error_handler.handle_error(e, "initialize")
            self.state = ModuleState.ERROR
            return False

    def start(self) -> bool:
        """
        Start the message translator.

        Returns:
            bool: True if start successful
        """
        try:
            with self._state_lock:
                if self.state != ModuleState.READY:
                    self.logger.warning(f"Cannot start from state: {self.state}")
                    return False

                self.logger.info(f"Starting {self.__class__.__name__}...")

                # Clear shutdown event
                self._shutdown_event.clear()

                self.state = ModuleState.RUNNING
                self.logger.info(f"{self.__class__.__name__} started successfully")
                return True

        except Exception as e:
            self.logger.error(f"Failed to start {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "start")
            self.state = ModuleState.ERROR
            return False

    def stop(self) -> bool:
        """
        Stop the message translator gracefully.

        Returns:
            bool: True if stop successful
        """
        try:
            with self._state_lock:
                if self.state not in [ModuleState.RUNNING, ModuleState.PAUSED]:
                    self.logger.warning(f"Cannot stop from state: {self.state}")
                    return False

                self.logger.info(f"Stopping {self.__class__.__name__}...")

                # Signal shutdown
                self._shutdown_event.set()

                # Clean up resources
                self._cleanup_resources()

                self.state = ModuleState.STOPPED
                self.logger.info(f"{self.__class__.__name__} stopped successfully")
                return True

        except Exception as e:
            self.logger.error(f"Error stopping {self.__class__.__name__}: {e}")
            self.error_handler.handle_error(e, "stop")
            return False

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _validate_configuration(self) -> bool:
        """Validate module configuration."""
        try:
            # Validate exchange mappings
            if not self.exchange_map.IBKR_TO_STANDARD:
                self.logger.error("Exchange mappings not available")
                return False

            return True

        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def _setup_resources(self) -> bool:
        """Set up required resources."""
        try:
            # Setup any required resources
            self.logger.debug("Resources setup completed")
            return True

        except Exception as e:
            self.logger.error(f"Resource setup failed: {e}")
            return False

    def _cleanup_resources(self):
        """Clean up allocated resources."""
        try:
            # Clean up any resources
            self.reset_statistics()
            self.logger.debug("Resources cleaned up")

        except Exception as e:
            self.logger.error(f"Resource cleanup failed: {e}")

    # ==========================================================================
    # CORE OPERATIONS
    # ==========================================================================

    def translate_market_data(self, ibkr_data: Dict, symbol: str) -> Optional[MarketDataTick]:
        """
        Translate IBKR market data to SPYDER format.

        Args:
            ibkr_data: Market data from IBKR API
            symbol: Symbol name

        Returns:
            MarketDataTick in SPYDER format
        """
        try:
            # Extract price data
            last_price = self._parse_float(ibkr_data.get('31'))  # Last price
            bid = self._parse_float(ibkr_data.get('84'))         # Bid
            ask = self._parse_float(ibkr_data.get('86'))         # Ask
            volume = self._parse_int(ibkr_data.get('7059'))     # Volume

            if last_price is None:
                self.logger.warning(f"No last price for {symbol}")
                return None

            # Create SPYDER format tick
            if HAS_SPYDER_TYPES:
                tick = MarketDataTick(
                    symbol=self.symbol_map.normalize_symbol(symbol),
                    last_price=last_price,
                    bid=bid or 0.0,
                    ask=ask or 0.0,
                    volume=volume or 0,
                    timestamp=self._parse_timestamp(ibkr_data.get('time'))
                )
            else:
                # Fallback format
                tick = MarketDataTick(
                    symbol=self.symbol_map.normalize_symbol(symbol),
                    last_price=last_price,
                    bid=bid or 0.0,
                    ask=ask or 0.0,
                    volume=volume or 0,
                    timestamp=datetime.now()
                )

            # Update statistics
            self._stats['market_data_translated'] += 1

            return tick

        except Exception as e:
            self.logger.error(f"Error translating market data for {symbol}: {e}")
            self._stats['translation_errors'] += 1
            return None

    def translate_order(self, ibkr_order: Dict) -> Optional[Order]:
        """
        Translate IBKR order to SPYDER format.

        Args:
            ibkr_order: Order data from IBKR API

        Returns:
            Order in SPYDER format
        """
        try:
            order_id = ibkr_order.get('orderId')
            if not order_id:
                self.logger.warning("No order ID in order data")
                return None

            # Extract order details
            symbol = ibkr_order.get('ticker', '')
            side = ibkr_order.get('side', '').upper()
            order_type = ibkr_order.get('orderType', '').upper()
            quantity = self._parse_float(ibkr_order.get('totalSize', 0))
            price = self._parse_float(ibkr_order.get('price'))
            status = self._translate_order_status(ibkr_order.get('status', ''))
            filled_quantity = self._parse_float(ibkr_order.get('filledQuantity', 0))

            # Create SPYDER format order
            if HAS_SPYDER_TYPES:
                order = Order(
                    order_id=str(order_id),
                    symbol=self.symbol_map.normalize_symbol(symbol),
                    side=side,
                    order_type=order_type,
                    quantity=quantity or 0.0,
                    price=price,
                    status=status,
                    filled_quantity=filled_quantity or 0.0
                )
            else:
                # Fallback format
                order = Order(
                    order_id=str(order_id),
                    symbol=self.symbol_map.normalize_symbol(symbol),
                    side=side,
                    order_type=order_type,
                    quantity=quantity or 0.0,
                    price=price,
                    status=status,
                    filled_quantity=filled_quantity or 0.0
                )

            # Update statistics
            self._stats['orders_translated'] += 1

            return order

        except Exception as e:
            self.logger.error(f"Error translating order: {e}")
            self._stats['translation_errors'] += 1
            return None

    def translate_position(self, ibkr_position: Dict) -> Optional[Position]:
        """
        Translate IBKR position to SPYDER format.

        Args:
            ibkr_position: Position data from IBKR API

        Returns:
            Position in SPYDER format
        """
        try:
            symbol = ibkr_position.get('ticker', '')
            position_qty = self._parse_float(ibkr_position.get('position', 0))
            avg_cost = self._parse_float(ibkr_position.get('avgCost', 0))
            market_price = self._parse_float(ibkr_position.get('mktPrice', 0))
            market_value = self._parse_float(ibkr_position.get('mktValue', 0))
            unrealized_pnl = self._parse_float(ibkr_position.get('unrealizedPnl', 0))

            # Create SPYDER format position
            if HAS_SPYDER_TYPES:
                position = Position(
                    symbol=self.symbol_map.normalize_symbol(symbol),
                    quantity=position_qty or 0.0,
                    avg_price=avg_cost or 0.0,
                    market_value=market_value or 0.0,
                    unrealized_pnl=unrealized_pnl or 0.0
                )
            else:
                # Fallback format
                position = Position(
                    symbol=self.symbol_map.normalize_symbol(symbol),
                    quantity=position_qty or 0.0,
                    avg_price=avg_cost or 0.0,
                    market_value=market_value or 0.0,
                    unrealized_pnl=unrealized_pnl or 0.0
                )

            # Update statistics
            self._stats['positions_translated'] += 1

            return position

        except Exception as e:
            self.logger.error(f"Error translating position: {e}")
            self._stats['translation_errors'] += 1
            return None

    def translate_account_summary(self, ibkr_account: Dict, account_id: str) -> Optional[AccountSummary]:
        """
        Translate IBKR account summary to SPYDER format.

        Args:
            ibkr_account: Account data from IBKR API
            account_id: Account ID

        Returns:
            AccountSummary in SPYDER format
        """
        try:
            # Extract account values
            net_liquidation = self._parse_float(ibkr_account.get('netliquidation', 0))
            total_cash = self._parse_float(ibkr_account.get('totalcash', 0))
            buying_power = self._parse_float(ibkr_account.get('buyingpower', 0))

            # Create SPYDER format account summary
            if HAS_SPYDER_TYPES:
                account = AccountSummary(
                    account_id=account_id,
                    net_liquidation=net_liquidation or 0.0,
                    total_cash=total_cash or 0.0,
                    buying_power=buying_power or 0.0
                )
            else:
                # Fallback format
                account = AccountSummary(
                    account_id=account_id,
                    net_liquidation=net_liquidation or 0.0,
                    total_cash=total_cash or 0.0,
                    buying_power=buying_power or 0.0
                )

            # Update statistics
            self._stats['accounts_translated'] += 1

            return account

        except Exception as e:
            self.logger.error(f"Error translating account summary: {e}")
            self._stats['translation_errors'] += 1
            return None

    def translate_order_request_to_ibkr(self, spyder_order: Dict) -> Dict:
        """
        Translate SPYDER order request to IBKR format.

        Args:
            spyder_order: Order request in SPYDER format

        Returns:
            Order request in IBKR format
        """
        try:
            # Map order type
            order_type_map = {
                'MARKET': 'MKT',
                'LIMIT': 'LMT',
                'STOP': 'STP',
                'STOP_LIMIT': 'STPLMT'
            }

            # Map time in force
            tif_map = {
                'DAY': 'DAY',
                'GTC': 'GOOD_TILL_CANCEL',
                'IOC': 'IMMEDIATE_OR_CANCEL',
                'FOK': 'FILL_OR_KILL'
            }

            # Create IBKR format order
            ibkr_order = {
                'conid': spyder_order.get('conid'),
                'orderType': order_type_map.get(
                    spyder_order.get('order_type', 'LIMIT'), 'LMT'
                ),
                'side': spyder_order.get('side', 'BUY').upper(),
                'quantity': spyder_order.get('quantity'),
                'tif': tif_map.get(
                    spyder_order.get('time_in_force', 'DAY'), 'DAY'
                )
            }

            # Add optional fields
            if spyder_order.get('limit_price'):
                ibkr_order['price'] = spyder_order['limit_price']

            if spyder_order.get('stop_price'):
                ibkr_order['auxPrice'] = spyder_order['stop_price']

            if spyder_order.get('outside_rth'):
                ibkr_order['outsideRTH'] = True

            if spyder_order.get('order_ref'):
                ibkr_order['orderRef'] = spyder_order['order_ref']

            return ibkr_order

        except Exception as e:
            self.logger.error(f"Error translating order request to IBKR: {e}")
            self._stats['translation_errors'] += 1
            return {}

    def get_translation_statistics(self) -> Dict[str, Any]:
        """Get translation statistics."""
        return {
            'market_data_translated': self._stats['market_data_translated'],
            'orders_translated': self._stats['orders_translated'],
            'positions_translated': self._stats['positions_translated'],
            'accounts_translated': self._stats['accounts_translated'],
            'translation_errors': self._stats['translation_errors'],
            'total_translations': sum([
                self._stats['market_data_translated'],
                self._stats['orders_translated'],
                self._stats['positions_translated'],
                self._stats['accounts_translated']
            ]),
            'error_rate': self._stats['translation_errors'] / max(1, sum([
                self._stats['market_data_translated'],
                self._stats['orders_translated'],
                self._stats['positions_translated'],
                self._stats['accounts_translated']
            ]))
        }

    def reset_statistics(self):
        """Reset translation statistics."""
        for key in self._stats:
            self._stats[key] = 0
        self.logger.info("Translation statistics reset")

    def _parse_float(self, value: Any) -> Optional[float]:
        """Parse float value from IBKR response."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_int(self, value: Any) -> Optional[int]:
        """Parse integer value from IBKR response."""
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def _parse_timestamp(self, timestamp: Any) -> datetime:
        """Parse timestamp from IBKR response."""
        if timestamp is None:
            return datetime.now()

        try:
            # Handle different timestamp formats
            if isinstance(timestamp, (int, float)):
                # Unix timestamp
                return datetime.fromtimestamp(timestamp, tz=timezone.utc)
            elif isinstance(timestamp, str):
                # ISO format or other string format
                try:
                    return datetime.fromisoformat(timestamp)
                except ValueError:
                    # Try Unix timestamp as string
                    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            else:
                return datetime.now()
        except Exception:
            return datetime.now()

    def _translate_order_status(self, ibkr_status: str) -> str:
        """Translate IBKR order status to SPYDER format."""
        status_map = {
            'PendingSubmit': 'PENDING',
            'PendingCancel': 'PENDING_CANCEL',
            'PreSubmitted': 'PRESUBMITTED',
            'Submitted': 'SUBMITTED',
            'ApiPending': 'API_PENDING',
            'ApiCancelled': 'API_CANCELLED',
            'Cancelled': 'CANCELLED',
            'Filled': 'FILLED',
            'Inactive': 'INACTIVE',
            'Rejected': 'REJECTED'
        }

        return status_map.get(ibkr_status, ibkr_status.upper())


    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Get current module status.

        Returns:
            Dictionary containing status information
        """
        return {
            'name': self.__class__.__name__,
            'state': self.state.name,
            'has_spyder_types': HAS_SPYDER_TYPES,
            'translation_statistics': self.get_translation_statistics()
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


if __name__ == "__main__":
    # Example usage
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Create translator
    translator = MessageTranslator()

    # Example IBKR market data
    ibkr_market_data = {
        '31': '450.25',  # Last price
        '84': '450.20',  # Bid
        '86': '450.30',  # Ask
        '7059': '1000000',  # Volume
        'time': '2023-10-21T14:30:00Z'
    }

    # Translate market data
    tick = translator.translate_market_data(ibkr_market_data, 'SPY')
    if tick:
        print(f"Translated market data: {tick.symbol} - {tick.last_price}")

    # Example IBKR order
    ibkr_order = {
        'orderId': '123456',
        'ticker': 'SPY',
        'side': 'BUY',
        'orderType': 'LMT',
        'totalSize': 100,
        'price': 450.0,
        'status': 'Submitted',
        'filledQuantity': 0
    }

    # Translate order
    order = translator.translate_order(ibkr_order)
    if order:
        print(f"Translated order: {order.order_id} - {order.status}")

    # Example SPYDER order request
    spyder_order_request = {
        'conid': 756733,
        'symbol': 'SPY',
        'side': 'BUY',
        'order_type': 'LIMIT',
        'quantity': 100,
        'limit_price': 450.0,
        'time_in_force': 'DAY'
    }

    # Translate order request to IBKR
    ibkr_order_request = translator.translate_order_request_to_ibkr(spyder_order_request)
    print(f"Translated order request: {ibkr_order_request}")

    # Print statistics
    stats = translator.get_translation_statistics()
    print(f"Translation statistics: {stats}")