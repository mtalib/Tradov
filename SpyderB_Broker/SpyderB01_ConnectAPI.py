#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB01_ConnectAPI.py
Purpose: Connect API integration for IBKR trading

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-10-20 Time: 22:00:00

Module Description:
    This module provides Connect API integration for IBKR trading through the
    Client Portal Web API. It replaces the IB Gateway/TWS API connection components with a
    REST API connection, providing real-time market data and order execution for
    equities, options, futures, and indices.

Module Constants:
    DEFAULT_RECONNECT_DELAY (float): Default reconnection delay in seconds (default: 5.0)
    MAX_RECONNECT_ATTEMPTS (int): Maximum reconnection attempts (default: 10)
    PING_INTERVAL (float): WebSocket ping interval in seconds (default: 30.0)

Change Log:
    2025-10-20 (v1.0.0):
        - Initial module creation
        - Implemented core Connect API functionality
        - Added WebSocket connection management
        - Implemented message routing and handling

    2025-10-15 (v0.9.0):
        - Beta version for testing
        - Basic connection structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import asyncio
import json
import uuid
import warnings
import websockets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable, Union, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum, auto
from pathlib import Path
import copy
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock
import websockets

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_RECONNECT_DELAY = 5.0
MAX_RECONNECT_ATTEMPTS = 10
PING_INTERVAL = 30.0  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class MessageType(Enum):
    """Message types for Connect API"""
    HEARTBEAT = "Heartbeat"
    LOGON = "Logon"
    LOGOUT = "Logout"
    MARKET_DATA_REQUEST = "MarketDataRequest"
    MARKET_DATA_UPDATE = "MarketDataUpdate"
    ORDER_SINGLE = "OrderSingle"
    ORDER_SINGLE_STATUS = "OrderSingleStatus"
    ORDER_CANCEL = "OrderCancel"
    ORDER_CANCEL_REJECT = "OrderCancelReject"
    EXECUTION_REPORT = "ExecutionReport"
    POSITION_UPDATE = "PositionUpdate"
    ACCOUNT_SUMMARY_UPDATE = "AccountSummaryUpdate"
    ERROR = "Error"
    HISTORICAL_DATA_REQUEST = "HistoricalDataRequest"
    HISTORICAL_DATA_RESPONSE = "HistoricalDataResponse"

class ConnectionState(Enum):
    """Connection states"""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    AUTHENTICATED = "AUTHENTICATED"
    ERROR = "ERROR"
    RECONNECTING = "RECONNECTING"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ConnectAPIConfig:
    """Configuration for Connect API"""
    api_key: str
    client_id: str
    account: str
    environment: str = "certification"  # certification/production
    reconnect_attempts: int = MAX_RECONNECT_ATTEMPTS
    reconnect_delay: float = DEFAULT_RECONNECT_DELAY
    ping_interval: float = PING_INTERVAL

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class ConnectAPI:
    """
    Connect API integration for IBKR trading.

    This class provides Connect API integration for IBKR trading through the
    Client Portal Web API. It replaces the IB Gateway/TWS API connection components with a
    REST API connection, providing real-time market data and order execution for
    equities, options, futures, and indices.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        config: Connect API configuration
        websocket: WebSocket connection
        state: Current connection state
        _message_handlers: Message handlers by message type
        _message_lock: Thread lock for message operations
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(self, config: ConnectAPIConfig):
        """
        Initialize the Connect API.

        Args:
            config: Connect API configuration
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config

        # Connection management
        self.websocket: Optional[Any] = None
        self.state = ConnectionState.DISCONNECTED
        self.session_id: Optional[str] = None
        self._message_handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        self._message_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Reconnection management
        self._reconnect_count = 0
        self._last_ping_time = 0.0
        self._ping_task: Optional[asyncio.Task] = None

        # Metrics
        self.metrics = {
            'messages_sent': 0,
            'messages_received': 0,
            'reconnections': 0,
            'last_connection_time': None,
            'start_time': datetime.now()
        }

        self.logger.info("ConnectAPI initialized")

    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================

    async def connect(self) -> bool:
        """
        Connect to the Connect API.

        Returns:
            bool: True if connection successful
        """
        try:
            self.logger.info("Connecting to Connect API...")
            self.state = ConnectionState.CONNECTING

            # Determine WebSocket URL based on environment
            if self.config.environment == "production":
                url = "wss://gateway.connecttrade.com:37197"
            else:
                url = "wss://onboarding.connecttrade.com:26553"

            # Connect to WebSocket
            self.websocket = await websockets.connect(
                url,
                ping_interval=self.config.ping_interval,
                ping_timeout=10.0
            )

            # Authenticate
            await self._authenticate()

            # Start message handler
            asyncio.create_task(self._message_handler_loop())

            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())

            self.state = ConnectionState.AUTHENTICATED
            self.metrics['last_connection_time'] = datetime.now()
            self._reconnect_count = 0

            self.logger.info(f"Connected to Connect API (Session ID: {self.session_id})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to connect to Connect API: {e}")
            self.error_handler.handle_error(e, "connect")
            self.state = ConnectionState.ERROR
            return False

    async def disconnect(self):
        """Disconnect from the Connect API"""
        try:
            self.logger.info("Disconnecting from Connect API...")
            self.state = ConnectionState.DISCONNECTED

            # Signal shutdown
            self._shutdown_event.set()

            # Cancel ping task
            if self._ping_task:
                self._ping_task.cancel()
                self._ping_task = None

            # Send logout if connected
            if self.websocket and self.state == ConnectionState.AUTHENTICATED:
                logout_message = {
                    "MsgType": MessageType.LOGOUT.value,
                    "SessionID": self.session_id
                }
                await self.send_message(logout_message)

            # Close WebSocket
            if self.websocket:
                await self.websocket.close()
                self.websocket = None

            self.logger.info("Disconnected from Connect API")

        except Exception as e:
            self.logger.error(f"Error disconnecting from Connect API: {e}")
            self.error_handler.handle_error(e, "disconnect")

    async def reconnect(self) -> bool:
        """
        Attempt to reconnect to the Connect API.

        Returns:
            bool: True if reconnection successful
        """
        if self._reconnect_count >= self.config.reconnect_attempts:
            self.logger.error(f"Maximum reconnection attempts ({self.config.reconnect_attempts}) reached")
            return False

        self._reconnect_count += 1
        self.metrics['reconnections'] += 1

        self.logger.info(f"Reconnection attempt {self._reconnect_count}/{self.config.reconnect_attempts}")
        self.state = ConnectionState.RECONNECTING

        # Wait before reconnecting
        await asyncio.sleep(self.config.reconnect_delay)

        # Disconnect if connected
        if self.websocket:
            await self.websocket.close()
            self.websocket = None

        # Attempt to connect
        return await self.connect()

    # ==========================================================================
    # MESSAGE OPERATIONS
    # ==========================================================================

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """
        Send a message to the Connect API.

        Args:
            message: Message to send

        Returns:
            bool: True if message sent successfully
        """
        try:
            if not self.websocket or self.state != ConnectionState.AUTHENTICATED:
                self.logger.warning("Cannot send message: not connected")
                return False

            # Add session ID if not present
            if "SessionID" not in message and self.session_id:
                message["SessionID"] = self.session_id

            # Send message
            await self.websocket.send(json.dumps(message))
            self.metrics['messages_sent'] += 1

            return True

        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            self.error_handler.handle_error(e, "send_message")
            return False

    def register_handler(self, message_type: MessageType, handler: Callable):
        """
        Register a message handler.

        Args:
            message_type: Message type to handle
            handler: Handler function
        """
        with self._message_lock:
            self._message_handlers[message_type].append(handler)
            self.logger.debug(f"Registered handler for {message_type.value}")

    def unregister_handler(self, message_type: MessageType, handler: Callable):
        """
        Unregister a message handler.

        Args:
            message_type: Message type to handle
            handler: Handler function
        """
        with self._message_lock:
            if handler in self._message_handlers[message_type]:
                self._message_handlers[message_type].remove(handler)
                self.logger.debug(f"Unregistered handler for {message_type.value}")

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    async def _authenticate(self):
        """Authenticate with the Connect API"""
        try:
            # Create logon message
            logon_message = {
                "MsgType": MessageType.LOGON.value,
                "APIKey": self.config.api_key,
                "ClientID": self.config.client_id,
                "Account": self.config.account,
                "Timestamp": datetime.now().strftime("%Y%m%d-%H:%M:%S")
            }

            # Send logon message
            await self.websocket.send(json.dumps(logon_message))
            self.metrics['messages_sent'] += 1

            # Wait for response
            response = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=10.0
            )

            # Parse response
            response_data = json.loads(response)
            if response_data.get("MsgType") == MessageType.LOGON.value:
                self.session_id = response_data.get("SessionID")
                self.state = ConnectionState.AUTHENTICATED
                self.logger.info(f"Authenticated successfully (Session ID: {self.session_id})")
            else:
                raise Exception(f"Unexpected response: {response_data}")

        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            self.error_handler.handle_error(e, "_authenticate")
            raise

    async def _message_handler_loop(self):
        """Message handler loop"""
        while not self._shutdown_event.is_set():
            try:
                if not self.websocket or self.state != ConnectionState.AUTHENTICATED:
                    await asyncio.sleep(1.0)
                    continue

                # Receive message
                message = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=60.0
                )

                # Parse message
                message_data = json.loads(message)
                self.metrics['messages_received'] += 1

                # Handle message
                await self._handle_message(message_data)

            except asyncio.TimeoutError:
                self.logger.warning("Message receive timeout")
                continue
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket connection closed")
                # Attempt to reconnect
                if await self.reconnect():
                    self.logger.info("Reconnected successfully")
                continue
            except Exception as e:
                self.logger.error(f"Error in message handler loop: {e}")
                self.error_handler.handle_error(e, "_message_handler_loop")
                await asyncio.sleep(1.0)

    async def _handle_message(self, message_data: Dict[str, Any]):
        """
        Handle a received message.

        Args:
            message_data: Message data
        """
        try:
            # Get message type
            msg_type = message_data.get("MsgType")
            if not msg_type:
                self.logger.warning("Message missing MsgType")
                return

            # Convert to enum
            try:
                message_type = MessageType(msg_type)
            except ValueError:
                self.logger.warning(f"Unknown message type: {msg_type}")
                return

            # Call handlers
            handlers = []
            with self._message_lock:
                handlers = self._message_handlers.get(message_type, [])

            for handler in handlers:
                try:
                    await handler(message_data)
                except Exception as e:
                    self.logger.error(f"Error in message handler: {e}")
                    self.error_handler.handle_error(e, "_handle_message")

        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            self.error_handler.handle_error(e, "_handle_message")

    async def _ping_loop(self):
        """Ping loop to keep connection alive"""
        while not self._shutdown_event.is_set():
            try:
                if not self.websocket or self.state != ConnectionState.AUTHENTICATED:
                    await asyncio.sleep(1.0)
                    continue

                # Send ping
                ping_message = {
                    "MsgType": MessageType.HEARTBEAT.value,
                    "SessionID": self.session_id,
                    "Timestamp": datetime.now().strftime("%Y%m%d-%H:%M:%S")
                }

                await self.send_message(ping_message)
                self._last_ping_time = time.time()

                # Wait for next ping
                await asyncio.sleep(self.config.ping_interval)

            except Exception as e:
                self.logger.error(f"Error in ping loop: {e}")
                self.error_handler.handle_error(e, "_ping_loop")
                await asyncio.sleep(1.0)

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Get current connection status.

        Returns:
            Dictionary containing status information
        """
        # Calculate uptime
        uptime = datetime.now() - self.metrics['start_time']

        # Calculate connection time
        connection_time = None
        if self.metrics['last_connection_time']:
            connection_time = datetime.now() - self.metrics['last_connection_time']

        return {
            'state': self.state.value,
            'session_id': self.session_id,
            'messages_sent': self.metrics['messages_sent'],
            'messages_received': self.metrics['messages_received'],
            'reconnections': self.metrics['reconnections'],
            'reconnect_count': self._reconnect_count,
            'uptime_seconds': uptime.total_seconds(),
            'connection_time_seconds': connection_time.total_seconds() if connection_time else None,
            'start_time': self.metrics['start_time'].isoformat(),
            'last_connection_time': self.metrics['last_connection_time'].isoformat() if self.metrics['last_connection_time'] else None
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get connection metrics.

        Returns:
            Dictionary containing metrics
        """
        # Calculate uptime
        uptime = datetime.now() - self.metrics['start_time']

        # Calculate message rate
        message_rate = 0.0
        if uptime.total_seconds() > 0:
            message_rate = (self.metrics['messages_sent'] + self.metrics['messages_received']) / uptime.total_seconds()

        return {
            'messages_sent': self.metrics['messages_sent'],
            'messages_received': self.metrics['messages_received'],
            'message_rate': message_rate,
            'reconnections': self.metrics['reconnections'],
            'reconnect_count': self._reconnect_count,
            'uptime_seconds': uptime.total_seconds(),
            'start_time': self.metrics['start_time'].isoformat()
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_connect_api(config: ConnectAPIConfig) -> ConnectAPI:
    """
    Factory function to create a Connect API instance.

    Args:
        config: Connect API configuration

    Returns:
        ConnectAPI instance
    """
    return ConnectAPI(config)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("="*80)
    print("SPYDER Connect API Test")
    print("="*80)

    # This would require actual API credentials to test
    print("Connect API module loaded successfully")

    print("\n" + "="*80)
    print("Module testing completed.")
    print("="*80)