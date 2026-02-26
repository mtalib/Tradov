#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE01_RiskManager.py
Purpose: Risk management using Connect API

Author: SPYDER Trading System
Year Created: 2025
Last Updated: 2025-10-20 Time: 22:10:00

Module Description:
    This module provides risk management functionality using the Connect API.
    It monitors positions, exposure, and risk metrics, and enforces risk limits
    for all trading activities. This module replaces the IB Gateway/TWS API
    risk management components.

Module Constants:
    RISK_CHECK_INTERVAL (float): Risk check interval in seconds (default: 5.0)
    POSITION_UPDATE_INTERVAL (float): Position update interval in seconds (default: 10.0)
    DEFAULT_RISK_LIMITS (Dict): Default risk limits configuration

Change Log:
    2025-10-20 (v1.0.0):
        - Initial module creation
        - Implemented core risk management functionality
        - Added integration with Connect API
        - Implemented position monitoring and risk calculation

    2025-10-15 (v0.9.0):
        - Beta version for testing
        - Basic risk management structure
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

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import Connect API
try:
    from Spyder.SpyderB_Broker.SpyderB01_ConnectAPI import ConnectAPI, MessageType
except ImportError:
    ConnectAPI = None
    MessageType = None

try:
    from Spyder.SpyderB_Broker.SpyderB02_OrderManager import Order, OrderState
except ImportError:
    Order = None
    OrderState = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
RISK_CHECK_INTERVAL = 5.0  # seconds
POSITION_UPDATE_INTERVAL = 10.0  # seconds

DEFAULT_RISK_LIMITS = {
    'max_position_size': 1000,
    'max_total_exposure': 100000.0,
    'max_daily_loss': 10000.0,
    'max_single_order_size': 500,
    'max_orders_per_minute': 10,
    'max_concentration_ratio': 0.3,  # Max 30% in any single symbol
    'max_options_exposure': 50000.0,
    'max_margin_usage': 0.8  # Max 80% of available margin
}

# ==============================================================================
# ENUMS
# ==============================================================================
class RiskLevel(Enum):
    """Risk levels"""
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()

class RiskCheckResult(Enum):
    """Risk check results"""
    ALLOWED = auto()
    WARNING = auto()
    BLOCKED = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class RiskConfig:
    """Configuration for risk management"""
    risk_limits: Dict[str, Any] = field(default_factory=lambda: DEFAULT_RISK_LIMITS.copy())
    enable_real_time_monitoring: bool = True
    risk_check_interval: float = RISK_CHECK_INTERVAL
    position_update_interval: float = POSITION_UPDATE_INTERVAL
    enable_automatic_order_cancellation: bool = False
    notification_threshold: RiskLevel = RiskLevel.HIGH

@dataclass
class Position:
    """Position representation"""
    symbol: str
    quantity: int
    market_price: float
    market_value: float
    average_fill_price: float
    unrealized_pnl: float
    realized_pnl: float
    currency: str = "USD"
    security_type: str = "STK"
    expiry: Optional[str] = None
    strike: Optional[float] = None
    right: Optional[str] = None  # CALL/PUT
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class RiskMetrics:
    """Risk metrics representation"""
    timestamp: datetime
    total_exposure: float
    daily_pnl: float
    net_liquidation: float
    margin_used: float
    margin_available: float
    max_concentration: float
    concentration_symbol: str
    options_exposure: float
    risk_level: RiskLevel
    warnings: List[str] = field(default_factory=list)
    blocked_orders: List[str] = field(default_factory=list)

@dataclass
class RiskCheckResponse:
    """Risk check response"""
    result: RiskCheckResult
    order_id: Optional[str] = None
    reason: Optional[str] = None
    risk_metrics: Optional[RiskMetrics] = None
    timestamp: datetime = field(default_factory=datetime.now)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class RiskManager:
    """
    Risk management using Connect API.

    This class provides risk management functionality using the Connect API.
    It monitors positions, exposure, and risk metrics, and enforces risk limits
    for all trading activities. This module replaces the IB Gateway/TWS API
    risk management components.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        config: Risk management configuration
        connect_api: Connect API instance
        order_manager: Order manager instance
        _positions: Dictionary of current positions
        _risk_metrics: Current risk metrics
        _risk_lock: Thread lock for risk operations
        _shutdown_event: Event for coordinated shutdown
    """

    def __init__(
        self,
        config: RiskConfig,
        connect_api: ConnectAPI,
        order_manager: Optional[Any] = None
    ):
        """
        Initialize the risk manager.

        Args:
            config: Risk management configuration
            connect_api: Connect API instance
            order_manager: Order manager instance
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config

        # Connect API
        self.connect_api = connect_api
        self.order_manager = order_manager

        # Risk management
        self._positions: Dict[str, Position] = {}
        self._risk_metrics: Optional[RiskMetrics] = None
        self._risk_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Monitoring
        self._risk_thread: Optional[threading.Thread] = None
        self._position_thread: Optional[threading.Thread] = None

        # Daily tracking
        self._daily_start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        self._daily_start_value = 0.0
        self._daily_high = 0.0
        self._daily_low = float('inf')

        # Metrics
        self.metrics = {
            'risk_checks': 0,
            'warnings': 0,
            'blocks': 0,
            'position_updates': 0,
            'start_time': datetime.now()
        }

        # Register message handlers
        self._register_handlers()

        self.logger.info("RiskManager initialized")

    def _register_handlers(self):
        """Register message handlers with the Connect API"""
        self.connect_api.register_handler(MessageType.POSITION_UPDATE, self._handle_position_update)
        self.connect_api.register_handler(MessageType.ACCOUNT_SUMMARY_UPDATE, self._handle_account_summary_update)

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================

    async def start(self) -> bool:
        """
        Start the risk manager.

        Returns:
            bool: True if start successful
        """
        try:
            self.logger.info("Starting RiskManager...")

            # Connect to Connect API if not already connected
            if self.connect_api.state != "AUTHENTICATED":
                if not await self.connect_api.connect():
                    return False

            # Request initial positions
            await self._request_positions()

            # Request initial account summary
            await self._request_account_summary()

            # Start monitoring threads
            if self.config.enable_real_time_monitoring:
                self._start_risk_monitoring()
                self._start_position_monitoring()

            self.logger.info("RiskManager started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start risk manager: {e}")
            self.error_handler.handle_error(e, "start")
            return False

    async def stop(self) -> bool:
        """
        Stop the risk manager.

        Returns:
            bool: True if stop successful
        """
        try:
            self.logger.info("Stopping RiskManager...")

            # Signal shutdown
            self._shutdown_event.set()

            # Stop monitoring threads
            self._stop_risk_monitoring()
            self._stop_position_monitoring()

            self.logger.info("RiskManager stopped successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to stop risk manager: {e}")
            self.error_handler.handle_error(e, "stop")
            return False

    # ==========================================================================
    # RISK CHECKING
    # ==========================================================================

    async def check_order_risk(self, order: Order) -> RiskCheckResponse:
        """
        Check if an order is within risk limits.

        Args:
            order: Order to check

        Returns:
            Risk check response
        """
        try:
            with self._risk_lock:
                self.metrics['risk_checks'] += 1

                # Get current risk metrics
                risk_metrics = self._calculate_risk_metrics()

                # Check order size
                if order.quantity > self.config.risk_limits['max_single_order_size']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"Order size {order.quantity} exceeds maximum {self.config.risk_limits['max_single_order_size']}",
                        risk_metrics=risk_metrics
                    )

                # Check position size
                current_position = self._positions.get(order.symbol, Position(
                    symbol=order.symbol,
                    quantity=0,
                    market_price=0.0,
                    market_value=0.0,
                    average_fill_price=0.0,
                    unrealized_pnl=0.0,
                    realized_pnl=0.0
                ))

                # Calculate new position size
                if order.side.lower() in ("buy", "buy_to_open", "buy_to_close"):
                    new_position_size = current_position.quantity + order.quantity
                else:
                    new_position_size = current_position.quantity - order.quantity

                if abs(new_position_size) > self.config.risk_limits['max_position_size']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"New position size {abs(new_position_size)} exceeds maximum {self.config.risk_limits['max_position_size']}",
                        risk_metrics=risk_metrics
                    )

                # Check total exposure
                order_value = order.quantity * (order.price or current_position.market_price)
                new_total_exposure = risk_metrics.total_exposure + order_value

                if new_total_exposure > self.config.risk_limits['max_total_exposure']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"New total exposure {new_total_exposure} exceeds maximum {self.config.risk_limits['max_total_exposure']}",
                        risk_metrics=risk_metrics
                    )

                # Check daily loss
                if risk_metrics.daily_pnl < -self.config.risk_limits['max_daily_loss']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.BLOCKED,
                        order_id=order.order_id,
                        reason=f"Daily loss {risk_metrics.daily_pnl} exceeds maximum {self.config.risk_limits['max_daily_loss']}",
                        risk_metrics=risk_metrics
                    )

                # Check concentration
                new_symbol_value = current_position.market_value + order_value
                new_concentration = new_symbol_value / new_total_exposure if new_total_exposure > 0 else 0

                if new_concentration > self.config.risk_limits['max_concentration_ratio']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.WARNING,
                        order_id=order.order_id,
                        reason=f"New concentration {new_concentration:.2%} exceeds maximum {self.config.risk_limits['max_concentration_ratio']:.2%}",
                        risk_metrics=risk_metrics
                    )

                # Check margin usage
                total_margin = risk_metrics.margin_used + risk_metrics.margin_available
                if total_margin > 0 and risk_metrics.margin_used / total_margin > self.config.risk_limits['max_margin_usage']:
                    return RiskCheckResponse(
                        result=RiskCheckResult.WARNING,
                        order_id=order.order_id,
                        reason=f"Margin usage {risk_metrics.margin_used / total_margin:.2%} exceeds maximum {self.config.risk_limits['max_margin_usage']:.2%}",
                        risk_metrics=risk_metrics
                    )

                # Order is allowed
                return RiskCheckResponse(
                    result=RiskCheckResult.ALLOWED,
                    order_id=order.order_id,
                    risk_metrics=risk_metrics
                )

        except Exception as e:
            self.logger.error(f"Error checking order risk: {e}")
            self.error_handler.handle_error(e, "check_order_risk")
            return RiskCheckResponse(
                result=RiskCheckResult.BLOCKED,
                order_id=order.order_id,
                reason=f"Error checking order risk: {str(e)}"
            )

    # ==========================================================================
    # POSITION MONITORING
    # ==========================================================================

    def get_positions(self) -> Dict[str, Position]:
        """
        Get current positions.

        Returns:
            Dictionary of current positions
        """
        with self._risk_lock:
            return dict(self._positions)

    def get_position(self, symbol: str) -> Optional[Position]:
        """
        Get position for a symbol.

        Returns:
            Position or None if not found
        """
        with self._risk_lock:
            return self._positions.get(symbol)

    def get_risk_metrics(self) -> Optional[RiskMetrics]:
        """
        Get current risk metrics.

        Returns:
            Current risk metrics or None if not available
        """
        with self._risk_lock:
            return self._risk_metrics

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    async def _request_positions(self):
        """Request position updates"""
        # Load account ID from environment variable (NEVER hardcode!)
        account_id = os.environ.get("TRADIER_ACCOUNT_ID")

        if not account_id:
            self.logger.error("TRADIER_ACCOUNT_ID not configured in environment")
            return

        message = {
            "MsgType": "PositionRequest",
            "Account": account_id
        }

        await self.connect_api.send_message(message)
        self.logger.debug(f"Requested position updates for account {account_id}")

    async def _request_account_summary(self):
        """Request account summary updates"""
        # Load account ID from environment variable (NEVER hardcode!)
        account_id = os.environ.get("TRADIER_ACCOUNT_ID")

        if not account_id:
            self.logger.error("TRADIER_ACCOUNT_ID not configured in environment")
            return

        message = {
            "MsgType": "AccountSummaryRequest",
            "Account": account_id,
            "Tags": "NetLiquidation,TotalCashValue,MarginUsed,MarginAvailable"
        }

        await self.connect_api.send_message(message)
        self.logger.debug(f"Requested account summary updates for account {account_id}")

    async def _handle_position_update(self, data: Dict[str, Any]):
        """
        Handle position update message.

        Args:
            data: Position update data
        """
        try:
            symbol = data.get("Symbol", "")
            if not symbol:
                self.logger.warning("Position update missing Symbol")
                return

            # Update position
            with self._risk_lock:
                position = Position(
                    symbol=symbol,
                    quantity=int(data.get("Position", 0)),
                    market_price=float(data.get("MarketPrice", 0.0)),
                    market_value=float(data.get("MarketValue", 0.0)),
                    average_fill_price=float(data.get("AverageCost", 0.0)),
                    unrealized_pnl=float(data.get("UnrealizedPNL", 0.0)),
                    realized_pnl=float(data.get("RealizedPNL", 0.0)),
                    currency=data.get("Currency", "USD"),
                    security_type=data.get("SecurityType", "STK"),
                    expiry=data.get("ExpirationDate"),
                    strike=float(data.get("Strike", 0.0)) if data.get("Strike") else None,
                    right=data.get("Right"),
                    last_updated=datetime.now()
                )

                self._positions[symbol] = position
                self.metrics['position_updates'] += 1

                # Update risk metrics
                self._risk_metrics = self._calculate_risk_metrics()

                # Log position update
                self.logger.debug(f"Position updated: {symbol} - {position.quantity} @ {position.market_price}")

        except Exception as e:
            self.logger.error(f"Error handling position update: {e}")
            self.error_handler.handle_error(e, "_handle_position_update")

    async def _handle_account_summary_update(self, data: Dict[str, Any]):
        """
        Handle account summary update message.

        Args:
            data: Account summary data
        """
        try:
            # Update account summary
            with self._risk_lock:
                # Update risk metrics
                self._risk_metrics = self._calculate_risk_metrics()

                # Log account summary update
                self.logger.debug("Account summary updated")

        except Exception as e:
            self.logger.error(f"Error handling account summary update: {e}")
            self.error_handler.handle_error(e, "_handle_account_summary_update")

    def _calculate_risk_metrics(self) -> RiskMetrics:
        """
        Calculate current risk metrics.

        Returns:
            Current risk metrics
        """
        try:
            # Calculate total exposure
            total_exposure = sum(abs(pos.market_value) for pos in self._positions.values())

            # Calculate daily PnL
            daily_pnl = sum(pos.unrealized_pnl + pos.realized_pnl for pos in self._positions.values())

            # Calculate concentration
            max_concentration = 0.0
            concentration_symbol = ""

            if total_exposure > 0:
                for symbol, position in self._positions.items():
                    concentration = abs(position.market_value) / total_exposure
                    if concentration > max_concentration:
                        max_concentration = concentration
                        concentration_symbol = symbol

            # Calculate options exposure
            options_exposure = sum(
                abs(pos.market_value) for pos in self._positions.values()
                if pos.security_type == "OPT"
            )

            # Determine risk level
            risk_level = RiskLevel.LOW
            warnings = []
            blocked_orders = []

            # Check daily loss
            if daily_pnl < -self.config.risk_limits['max_daily_loss']:
                risk_level = RiskLevel.CRITICAL
                warnings.append(f"Daily loss {daily_pnl} exceeds maximum {self.config.risk_limits['max_daily_loss']}")

            # Check total exposure
            if total_exposure > self.config.risk_limits['max_total_exposure']:
                risk_level = RiskLevel.HIGH
                warnings.append(f"Total exposure {total_exposure} exceeds maximum {self.config.risk_limits['max_total_exposure']}")

            # Check concentration
            if max_concentration > self.config.risk_limits['max_concentration_ratio']:
                if risk_level.value < RiskLevel.MEDIUM.value:
                    risk_level = RiskLevel.MEDIUM
                warnings.append(f"Concentration {max_concentration:.2%} in {concentration_symbol} exceeds maximum {self.config.risk_limits['max_concentration_ratio']:.2%}")

            # Check options exposure
            if options_exposure > self.config.risk_limits['max_options_exposure']:
                if risk_level.value < RiskLevel.MEDIUM.value:
                    risk_level = RiskLevel.MEDIUM
                warnings.append(f"Options exposure {options_exposure} exceeds maximum {self.config.risk_limits['max_options_exposure']}")

            # Create risk metrics
            risk_metrics = RiskMetrics(
                timestamp=datetime.now(),
                total_exposure=total_exposure,
                daily_pnl=daily_pnl,
                net_liquidation=0.0,  # TODO: Get from account summary
                margin_used=0.0,  # TODO: Get from account summary
                margin_available=0.0,  # TODO: Get from account summary
                max_concentration=max_concentration,
                concentration_symbol=concentration_symbol,
                options_exposure=options_exposure,
                risk_level=risk_level,
                warnings=warnings,
                blocked_orders=blocked_orders
            )

            return risk_metrics

        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {e}")
            self.error_handler.handle_error(e, "_calculate_risk_metrics")

            # Return default risk metrics
            return RiskMetrics(
                timestamp=datetime.now(),
                total_exposure=0.0,
                daily_pnl=0.0,
                net_liquidation=0.0,
                margin_used=0.0,
                margin_available=0.0,
                max_concentration=0.0,
                concentration_symbol="",
                options_exposure=0.0,
                risk_level=RiskLevel.LOW,
                warnings=[f"Error calculating risk metrics: {str(e)}"],
                blocked_orders=[]
            )

    def _start_risk_monitoring(self):
        """Start risk monitoring thread"""
        if not self._risk_thread:
            self._risk_thread = threading.Thread(
                target=self._risk_monitoring_loop,
                daemon=True,
                name="RiskMonitoring"
            )
            self._risk_thread.start()
            self.logger.info("Risk monitoring started")

    def _stop_risk_monitoring(self):
        """Stop risk monitoring thread"""
        if self._risk_thread:
            self._risk_thread.join(timeout=5.0)
            self._risk_thread = None
            self.logger.info("Risk monitoring stopped")

    def _risk_monitoring_loop(self):
        """Risk monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                # Update risk metrics
                with self._risk_lock:
                    self._risk_metrics = self._calculate_risk_metrics()

                # Check if risk level exceeds notification threshold
                if self._risk_metrics and self._risk_metrics.risk_level.value >= self.config.notification_threshold.value:
                    self.logger.warning(f"Risk level {self._risk_metrics.risk_level.name} exceeded threshold")

                    # Send notifications
                    self._send_risk_notifications(self._risk_metrics)

                # Wait for next check
                time.sleep(self.config.risk_check_interval)

            except Exception as e:
                self.logger.error(f"Error in risk monitoring loop: {e}")
                self.error_handler.handle_error(e, "_risk_monitoring_loop")
                time.sleep(1.0)  # Wait before retry

    def _start_position_monitoring(self):
        """Start position monitoring thread"""
        if not self._position_thread:
            self._position_thread = threading.Thread(
                target=self._position_monitoring_loop,
                daemon=True,
                name="PositionMonitoring"
            )
            self._position_thread.start()
            self.logger.info("Position monitoring started")

    def _stop_position_monitoring(self):
        """Stop position monitoring thread"""
        if self._position_thread:
            self._position_thread.join(timeout=5.0)
            self._position_thread = None
            self.logger.info("Position monitoring stopped")

    def _position_monitoring_loop(self):
        """Position monitoring loop"""
        while not self._shutdown_event.is_set():
            try:
                # Request position updates
                asyncio.create_task(self._request_positions())

                # Wait for next update
                time.sleep(self.config.position_update_interval)

            except Exception as e:
                self.logger.error(f"Error in position monitoring loop: {e}")
                self.error_handler.handle_error(e, "_position_monitoring_loop")
                time.sleep(1.0)  # Wait before retry

    def _send_risk_notifications(self, risk_metrics: RiskMetrics):
        """
        Send risk notifications.

        Args:
            risk_metrics: Risk metrics
        """
        try:
            # Log warnings
            for warning in risk_metrics.warnings:
                self.logger.warning(f"Risk warning: {warning}")

            # TODO: Send email/SMS notifications

        except Exception as e:
            self.logger.error(f"Error sending risk notifications: {e}")
            self.error_handler.handle_error(e, "_send_risk_notifications")

    # ==========================================================================
    # PUBLIC UTILITY METHODS
    # ==========================================================================

    def get_status(self) -> Dict[str, Any]:
        """
        Get current risk manager status.

        Returns:
            Dictionary containing status information
        """
        with self._risk_lock:
            # Calculate uptime
            uptime = datetime.now() - self.metrics['start_time']

            # Get risk metrics
            risk_metrics = self._risk_metrics

            return {
                'monitoring_enabled': self.config.enable_real_time_monitoring,
                'risk_level': risk_metrics.risk_level.name if risk_metrics else None,
                'total_exposure': risk_metrics.total_exposure if risk_metrics else 0.0,
                'daily_pnl': risk_metrics.daily_pnl if risk_metrics else 0.0,
                'positions_count': len(self._positions),
                'warnings_count': len(risk_metrics.warnings) if risk_metrics else 0,
                'blocked_orders_count': len(risk_metrics.blocked_orders) if risk_metrics else 0,
                'risk_checks': self.metrics['risk_checks'],
                'warnings': self.metrics['warnings'],
                'blocks': self.metrics['blocks'],
                'position_updates': self.metrics['position_updates'],
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat()
            }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get risk manager metrics.

        Returns:
            Dictionary containing metrics
        """
        with self._risk_lock:
            # Calculate uptime
            uptime = datetime.now() - self.metrics['start_time']

            # Calculate check rate
            check_rate = 0.0
            if uptime.total_seconds() > 0:
                check_rate = self.metrics['risk_checks'] / uptime.total_seconds()

            return {
                'risk_checks': self.metrics['risk_checks'],
                'warnings': self.metrics['warnings'],
                'blocks': self.metrics['blocks'],
                'position_updates': self.metrics['position_updates'],
                'check_rate': check_rate,
                'uptime_seconds': uptime.total_seconds(),
                'start_time': self.metrics['start_time'].isoformat()
            }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_risk_manager(
    config: RiskConfig,
    connect_api: ConnectAPI,
    order_manager: Optional[Any] = None
) -> RiskManager:
    """
    Factory function to create a risk manager instance.

    Args:
        config: Risk management configuration
        connect_api: Connect API instance
        order_manager: Order manager instance

    Returns:
        RiskManager instance
    """
    return RiskManager(config, connect_api, order_manager)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("="*80)
    print("SPYDER Risk Manager Test")
    print("="*80)

    # This would require actual Connect API to test
    print("Risk manager module loaded successfully")

    print("\n" + "="*80)
    print("Module testing completed.")
    print("="*80)