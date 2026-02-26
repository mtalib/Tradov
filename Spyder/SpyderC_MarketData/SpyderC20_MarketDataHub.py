#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC20_MarketDataHub.py
Purpose: Centralized market data subscription and distribution hub (Databento/Tradier)

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-22 Time: 14:30:00

⚠️ MIGRATION TO POLYGON.IO RECOMMENDED ⚠️
    This module is designed for IBKR market data subscriptions but should be
    updated to use Polygon.io WebSocket streams.

    Migration Status:
    - ❌ Currently references IBKR-specific infrastructure
    - ⚠️ Rate limiting logic specific to IBKR limits
    - 🎯 Should be replaced with Polygon.io WebSocket handler

    For New Development:
    - Use SpyderC25_PolygonDataHandler for WebSocket streaming
    - Polygon provides unified WebSocket API for stocks, options, and futures
    - Built-in rate limiting already implemented in PolygonDataHandler
    - Cleaner architecture without IBKR broker dependency

    Current Implementation: Hub designed for IBKR multi-client management
    Recommended: Polygon.io WebSocket with event distribution

Module Description:
    This module serves as the central hub for all Interactive Brokers market data
    subscriptions. It implements intelligent rate limiting, tiered update frequencies,
    connection pooling, and distributes data throughout the Spyder system via the
    event manager. Replaces the previous OPRAFeed module with enhanced capabilities.
    Updated to use ib_async for IB Gateway 10.37 compatibility.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import os
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventManager, EventType

# B01_SpyderClient removed (IB Gateway) — Databento via SpyderC26_DatabentoClient
SpyderClient = None  # type: ignore

# B06_ContractBuilder removed (IB Gateway)
ContractBuilder = None  # type: ignore

# B10_IBDataTypes removed (IB Gateway)
SecurityType = None  # type: ignore
TickType = None  # type: ignore

from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from Spyder.SpyderU_Utilities.SpyderU09_DataTypes import MarketDataType

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Rate Limiting Configuration
SUBSCRIPTION_TIERS = {
    "CRITICAL": {
        "symbols": ["SPY", "SPX", "VIX", "/ES"],
        "frequency": 0.1,  # 100ms updates
        "priority": 1,
        "method": "realtime",
    },
    "HIGH": {
        "symbols": ["QQQ", "IWM", "DIA", "TLT", "GLD", "VXX", "UVXY"],
        "frequency": 0.5,  # 500ms updates
        "priority": 2,
        "method": "realtime",
    },
    "MEDIUM": {
        "symbols": ["VIX9D", "VXV", "VXMT", "SKEW", "TICK-NYSE", "TRIN-NYSE"],
        "frequency": 2.0,  # 2 second updates
        "priority": 3,
        "method": "snapshot",
    },
    "LOW": {
        "symbols": ["LQD", "HYG", "XLF", "XLE", "XLI", "XLK", "XLP"],
        "frequency": 10.0,  # 10 second updates
        "priority": 4,
        "method": "snapshot",
    },
    "BACKGROUND": {
        "symbols": ["VX", "ADVN-NYSE", "DECN-NYSE", "UVOL-NYSE", "DVOL-NYSE", "VOLD-NYSE"],
        "frequency": 60,
        "priority": 5,
        "method": "snapshot",
    },
}

# IBKR Limits
MAX_CONCURRENT_SUBSCRIPTIONS = 100
MAX_SNAPSHOT_REQUESTS_PER_SECOND = 1
CONNECTION_TIMEOUT = 30
HEARTBEAT_INTERVAL = 30
RECONNECT_DELAY_BASE = 5
MAX_RECONNECT_ATTEMPTS = 5

# Market Data Configuration
MARKET_DATA_CONFIG = {
    "rate_limits": {
        "max_requests_per_second": 50,
        "max_subscriptions": 100,
        "snapshot_cooldown": 1.0,  # seconds between snapshots
    },
    "error_thresholds": {"max_consecutive_errors": 10, "error_window": 60},  # seconds
    "cache_settings": {"ttl_seconds": 5, "max_cache_size": 10000},
}

# Symbol Specifications
SYMBOL_SPECS = {
    "SPY": {"type": "STK", "exchange": "SMART", "currency": "USD"},
    "SPX": {"type": "IND", "exchange": "CBOE", "currency": "USD"},
    "/ES": {"type": "FUT", "exchange": "CME", "currency": "USD", "localSymbol": "ESZ5"},
    "VIX": {"type": "IND", "exchange": "CBOE", "currency": "USD"},
    "VX": {"type": "FUT", "exchange": "CFE", "currency": "USD", "localSymbol": "VXZ5"},
    "DXY": {"type": "IND", "exchange": "ICE", "currency": "USD"},
    # Market internals use special symbols
    "TICK-NYSE": {"type": "IND", "exchange": "NYSE", "symbol": "TICK-NYSE"},
    "TRIN-NYSE": {"type": "IND", "exchange": "NYSE", "symbol": "TRIN-NYSE"},
    "ADD-NYSE": {"type": "IND", "exchange": "NYSE", "symbol": "ADD-NYSE"},
}

# ==============================================================================
# ENUMS
# ==============================================================================

class SubscriptionStatus(Enum):
    """Status of a market data subscription"""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    CANCELLED = "cancelled"

class DataQuality(Enum):
    """Quality of market data"""
    REALTIME = "realtime"
    DELAYED = "delayed"
    CACHED = "cached"
    STALE = "stale"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class MarketDataSubscription:
    """Represents a single market data subscription"""
    symbol: str
    req_id: int
    contract: Any
    tier: str
    status: SubscriptionStatus = SubscriptionStatus.PENDING
    last_update: Optional[datetime] = None
    error_count: int = 0
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class MarketDataUpdate:
    """Market data update event"""
    symbol: str
    timestamp: datetime
    data: Dict[str, float]
    quality: DataQuality
    tier: str

# ==============================================================================
# MAIN CLASS
# ==============================================================================

class MarketDataHub:
    """
    Centralized market data subscription and distribution hub.

    Manages all IBKR market data subscriptions with intelligent rate limiting,
    tiered updates, and event-based distribution.
    """

    def __init__(
        self,
        ib_client: SpyderClient,
        event_manager: EventManager,
        config_path: Optional[str] = None,
    ):
        """
        Initialize Market Data Hub.

        Args:
            ib_client: Connected SpyderClient instance
            event_manager: Event manager for publishing updates
            config_path: Optional path to configuration file
        """
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = self._load_config(config_path)

        # Subscription management
        self.subscriptions: Dict[str, MarketDataSubscription] = {}
        self.symbol_to_req_id: Dict[str, int] = {}
        self.req_id_to_symbol: Dict[int, str] = {}
        self.next_req_id = 1000

        # Threading and concurrency
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="MDH")
        self.lock = threading.RLock()

        # Rate limiting
        self.last_request_time = defaultdict(float)
        self.request_counts = defaultdict(int)
        self.tier_last_update = defaultdict(float)

        # Error tracking
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_timestamps: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))

        # Initialize
        self._setup_callbacks()
        self.logger.info("Market Data Hub initialized")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        if config_path and os.path.exists(config_path):
            with open(config_path, "r") as f:
                return json.load(f)
        return MARKET_DATA_CONFIG

    def _setup_callbacks(self):
        """Setup IBKR callbacks for market data"""
        # Price updates
        self.ib_client.ib.tickPrice = self._on_tick_price
        self.ib_client.ib.tickSize = self._on_tick_size
        self.ib_client.ib.tickString = self._on_tick_string
        self.ib_client.ib.tickGeneric = self._on_tick_generic

        # Options specific
        self.ib_client.ib.tickOptionComputation = self._on_tick_option

        # Market depth
        self.ib_client.ib.updateMktDepth = self._on_market_depth

        # Errors
        self.ib_client.ib.error = self._on_error

        self.logger.debug("IBKR callbacks configured")

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the market data hub.

        Returns:
            True if started successfully
        """
        try:
            if self.running:
                self.logger.warning("Market Data Hub already running")
                return True

            if not self.ib_client.is_connected():
                self.logger.error("IB client not connected")
                return False

            self.running = True

            # Start worker thread
            self.worker_thread = threading.Thread(
                target=self._worker_loop, name="MarketDataHubWorker", daemon=True
            )
            self.worker_thread.start()

            self.logger.info("Market Data Hub started")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start Market Data Hub: {e}")
            return False

    def stop(self):
        """Stop the market data hub and clean up resources"""
        try:
            self.running = False

            # Cancel all subscriptions
            self._cancel_all_subscriptions()

            # Stop worker thread
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=5.0)

            # Shutdown executor
            self.executor.shutdown(wait=True, timeout=10.0)

            self.logger.info("Market Data Hub stopped")

        except Exception as e:
            self.logger.error(f"Error stopping Market Data Hub: {e}")

    def subscribe(self, symbol: str, tier: str = "MEDIUM") -> bool:
        """
        Subscribe to market data for a symbol.

        Args:
            symbol: Market symbol to subscribe to
            tier: Subscription tier (CRITICAL, HIGH, MEDIUM, LOW, BACKGROUND)

        Returns:
            True if subscription initiated successfully
        """
        try:
            with self.lock:
                # Check if already subscribed
                if symbol in self.subscriptions:
                    self.logger.debug(f"Already subscribed to {symbol}")
                    return True

                # Check subscription limits
                active_subs = sum(
                    1
                    for sub in self.subscriptions.values()
                    if sub.status == SubscriptionStatus.ACTIVE
                )

                if active_subs >= MAX_CONCURRENT_SUBSCRIPTIONS:
                    self.logger.warning(
                        f"Subscription limit reached ({MAX_CONCURRENT_SUBSCRIPTIONS})"
                    )
                    return False

                # Create contract
                contract = self._create_contract(symbol)
                if not contract:
                    self.logger.error(f"Failed to create contract for {symbol}")
                    return False

                # Create subscription
                req_id = self._get_next_req_id()
                subscription = MarketDataSubscription(
                    symbol=symbol,
                    req_id=req_id,
                    contract=contract,
                    tier=tier,
                    status=SubscriptionStatus.PENDING,
                )

                # Store subscription
                self.subscriptions[symbol] = subscription
                self.symbol_to_req_id[symbol] = req_id
                self.req_id_to_symbol[req_id] = symbol

                # Submit to IBKR
                self._submit_subscription(subscription)

                self.logger.info(f"Initiated subscription to {symbol} (tier: {tier})")
                return True

        except Exception as e:
            self.logger.error(f"Error subscribing to {symbol}: {e}")
            return False

    def unsubscribe(self, symbol: str) -> bool:
        """
        Unsubscribe from market data for a symbol.

        Args:
            symbol: Symbol to unsubscribe from

        Returns:
            True if unsubscribed successfully
        """
        try:
            with self.lock:
                if symbol not in self.subscriptions:
                    self.logger.debug(f"Not subscribed to {symbol}")
                    return True

                subscription = self.subscriptions[symbol]

                # Cancel with IBKR
                self.ib_client.ib.cancelMktData(subscription.req_id)

                # Clean up
                del self.subscriptions[symbol]
                del self.symbol_to_req_id[symbol]
                del self.req_id_to_symbol[subscription.req_id]

                self.logger.info(f"Unsubscribed from {symbol}")
                return True

        except Exception as e:
            self.logger.error(f"Error unsubscribing from {symbol}: {e}")
            return False

    def get_latest_data(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get the latest market data for a symbol.

        Args:
            symbol: Symbol to get data for

        Returns:
            Latest market data or None if not available
        """
        with self.lock:
            if symbol in self.subscriptions:
                subscription = self.subscriptions[symbol]
                if subscription.data and subscription.status == SubscriptionStatus.ACTIVE:
                    return subscription.data.copy()
        return None

    def get_subscription_status(self) -> Dict[str, Any]:
        """
        Get comprehensive subscription status.

        Returns:
            Dictionary with subscription statistics and status
        """
        with self.lock:
            status_counts = defaultdict(int)
            tier_counts = defaultdict(int)

            for sub in self.subscriptions.values():
                status_counts[sub.status.value] += 1
                tier_counts[sub.tier] += 1

            return {
                "total_subscriptions": len(self.subscriptions),
                "status_breakdown": dict(status_counts),
                "tier_breakdown": dict(tier_counts),
                "error_counts": dict(self.error_counts),
                "rate_limits": {
                    "max_subscriptions": MAX_CONCURRENT_SUBSCRIPTIONS,
                    "current_subscriptions": len(self.subscriptions),
                },
                "last_update": datetime.now().isoformat(),
            }

    # ==========================================================================
    # PRIVATE METHODS - CONTRACT CREATION
    # ==========================================================================
    def _create_contract(self, symbol: str) -> Optional[Any]:
        """Create IBKR contract for symbol"""
        try:
            spec = SYMBOL_SPECS.get(symbol)
            if not spec:
                self.logger.warning(f"No specification found for {symbol}")
                return None

            contract_type = spec.get("type", "STK")

            if contract_type == "STK":
                return self._build_stock_contract(symbol, spec)
            elif contract_type == "IND":
                return self._build_index_contract(symbol, spec)
            elif contract_type == "FUT":
                return self._build_future_contract(symbol, spec)
            else:
                self.logger.error(f"Unsupported contract type: {contract_type}")
                return None

        except Exception as e:
            self.logger.error(f"Error creating contract for {symbol}: {e}")
            return None

    def _build_stock_contract(self, symbol: str, spec: Dict[str, Any]) -> Any:
        """Build a stock contract (legacy IB method — not used after IB Gateway removal)"""
        self.logger.warning("_build_stock_contract: ib_async removed, returning None")
        return None

    def _build_index_contract(self, symbol: str, spec: Dict[str, Any]) -> Any:
        """Build an index contract (legacy IB method — not used after IB Gateway removal)"""
        self.logger.warning("_build_index_contract: ib_async removed, returning None")
        return None

    def _build_future_contract(self, symbol: str, spec: Dict[str, Any]) -> Any:
        """Build a futures contract (legacy IB method — not used after IB Gateway removal)"""
        self.logger.warning("_build_future_contract: ib_async removed, returning None")
        return None

    # ==========================================================================
    # PRIVATE METHODS - SUBSCRIPTION MANAGEMENT
    # ==========================================================================
    def _get_next_req_id(self) -> int:
        """Get next available request ID"""
        req_id = self.next_req_id
        self.next_req_id += 1
        return req_id

    def _submit_subscription(self, subscription: MarketDataSubscription):
        """Submit subscription to IBKR"""
        try:
            # Determine subscription method based on tier
            tier_config = SUBSCRIPTION_TIERS.get(subscription.tier, SUBSCRIPTION_TIERS["MEDIUM"])
            method = tier_config.get("method", "realtime")

            if method == "realtime":
                # Real-time streaming subscription
                self.ib_client.ib.reqMktData(
                    subscription.req_id,
                    subscription.contract,
                    "",  # Generic tick list
                    False,  # Snapshot
                    False,  # Regulatory snapshot
                    []  # Options
                )
            else:
                # Snapshot subscription
                self.ib_client.ib.reqMktData(
                    subscription.req_id,
                    subscription.contract,
                    "",  # Generic tick list
                    True,  # Snapshot
                    False,  # Regulatory snapshot
                    []  # Options
                )

            subscription.status = SubscriptionStatus.ACTIVE
            self.logger.debug(f"Submitted {method} subscription for {subscription.symbol}")

        except Exception as e:
            subscription.status = SubscriptionStatus.ERROR
            subscription.error_count += 1
            self.logger.error(f"Error submitting subscription for {subscription.symbol}: {e}")

    def _cancel_all_subscriptions(self):
        """Cancel all active subscriptions"""
        with self.lock:
            for subscription in list(self.subscriptions.values()):
                try:
                    self.ib_client.ib.cancelMktData(subscription.req_id)
                except Exception as e:
                    self.logger.error(f"Error canceling subscription for {subscription.symbol}: {e}")

            self.subscriptions.clear()
            self.symbol_to_req_id.clear()
            self.req_id_to_symbol.clear()

    # ==========================================================================
    # PRIVATE METHODS - WORKER THREAD
    # ==========================================================================
    def _worker_loop(self):
        """Main worker thread loop"""
        self.logger.info("Market Data Hub worker started")

        while self.running:
            try:
                # Monitor subscriptions
                self._check_subscription_health()

                # Process tier-based updates
                self._process_tier_updates()

                # Clean up stale data
                self._cleanup_stale_data()

                # Brief pause
                time.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Worker loop error: {e}")
                time.sleep(1.0)

        self.logger.info("Market Data Hub worker stopped")

    def _check_subscription_health(self):
        """Check health of active subscriptions"""
        current_time = time.time()

        with self.lock:
            for subscription in list(self.subscriptions.values()):
                # Check for stale subscriptions
                if (
                    subscription.last_update
                    and (datetime.now() - subscription.last_update).total_seconds() > 60
                ):
                    self.logger.warning(f"Stale subscription detected: {subscription.symbol}")
                    # Could implement auto-resubscription logic here

    def _process_tier_updates(self):
        """Process tier-based update frequencies"""
        current_time = time.time()

        for tier, config in SUBSCRIPTION_TIERS.items():
            frequency = config.get("frequency", 1.0)
            last_update = self.tier_last_update.get(tier, 0)

            if current_time - last_update >= frequency:
                self._process_tier_subscriptions(tier)
                self.tier_last_update[tier] = current_time

    def _process_tier_subscriptions(self, tier: str):
        """Process subscriptions for a specific tier"""
        with self.lock:
            tier_subscriptions = [
                sub for sub in self.subscriptions.values()
                if sub.tier == tier and sub.status == SubscriptionStatus.ACTIVE
            ]

            for subscription in tier_subscriptions:
                # Update subscription timestamp
                subscription.last_update = datetime.now()

    def _cleanup_stale_data(self):
        """Clean up stale data and error tracking"""
        current_time = time.time()
        error_window = self.config.get("error_thresholds", {}).get("error_window", 60)

        # Clean up old error timestamps
        for symbol, timestamps in self.error_timestamps.items():
            while timestamps and current_time - timestamps[0] > error_window:
                timestamps.popleft()

    # ==========================================================================
    # PRIVATE METHODS - CALLBACKS
    # ==========================================================================
    def _on_tick_price(self, req_id: int, tick_type: int, price: float, attrib: Any):
        """Handle tick price updates"""
        symbol = self.req_id_to_symbol.get(req_id)
        if not symbol:
            return

        try:
            with self.lock:
                subscription = self.subscriptions.get(symbol)
                if subscription:
                    # Update subscription data
                    if "price" not in subscription.data:
                        subscription.data["price"] = {}
                    subscription.data["price"][tick_type] = price
                    subscription.last_update = datetime.now()

                    # Publish event
                    self._publish_market_update(subscription, {"tick_price": {tick_type: price}})

        except Exception as e:
            self.logger.error(f"Error processing tick price for {symbol}: {e}")

    def _on_tick_size(self, req_id: int, tick_type: int, size: int):
        """Handle tick size updates"""
        symbol = self.req_id_to_symbol.get(req_id)
        if not symbol:
            return

        try:
            with self.lock:
                subscription = self.subscriptions.get(symbol)
                if subscription:
                    # Update subscription data
                    if "size" not in subscription.data:
                        subscription.data["size"] = {}
                    subscription.data["size"][tick_type] = size
                    subscription.last_update = datetime.now()

                    # Publish event
                    self._publish_market_update(subscription, {"tick_size": {tick_type: size}})

        except Exception as e:
            self.logger.error(f"Error processing tick size for {symbol}: {e}")

    def _on_tick_string(self, req_id: int, tick_type: int, value: str):
        """Handle tick string updates"""
        symbol = self.req_id_to_symbol.get(req_id)
        if not symbol:
            return

        try:
            with self.lock:
                subscription = self.subscriptions.get(symbol)
                if subscription:
                    # Update subscription data
                    if "string" not in subscription.data:
                        subscription.data["string"] = {}
                    subscription.data["string"][tick_type] = value
                    subscription.last_update = datetime.now()

        except Exception as e:
            self.logger.error(f"Error processing tick string for {symbol}: {e}")

    def _on_tick_generic(self, req_id: int, tick_type: int, value: float):
        """Handle generic tick updates"""
        symbol = self.req_id_to_symbol.get(req_id)
        if not symbol:
            return

        try:
            with self.lock:
                subscription = self.subscriptions.get(symbol)
                if subscription:
                    # Update subscription data
                    if "generic" not in subscription.data:
                        subscription.data["generic"] = {}
                    subscription.data["generic"][tick_type] = value
                    subscription.last_update = datetime.now()

        except Exception as e:
            self.logger.error(f"Error processing generic tick for {symbol}: {e}")

    def _on_tick_option(self, req_id: int, tick_type: int, impl_vol: float,
                       delta: float, opt_price: float, pv_dividend: float,
                       gamma: float, vega: float, theta: float, und_price: float):
        """Handle option computation updates"""
        symbol = self.req_id_to_symbol.get(req_id)
        if not symbol:
            return

        try:
            with self.lock:
                subscription = self.subscriptions.get(symbol)
                if subscription:
                    # Update subscription data
                    option_data = {
                        "impl_vol": impl_vol,
                        "delta": delta,
                        "opt_price": opt_price,
                        "pv_dividend": pv_dividend,
                        "gamma": gamma,
                        "vega": vega,
                        "theta": theta,
                        "und_price": und_price,
                    }
                    subscription.data["option_computation"] = option_data
                    subscription.last_update = datetime.now()

                    # Publish event
                    self._publish_market_update(subscription, {"option_computation": option_data})

        except Exception as e:
            self.logger.error(f"Error processing option computation for {symbol}: {e}")

    def _on_market_depth(self, req_id: int, position: int, operation: int,
                        side: int, price: float, size: int):
        """Handle market depth updates"""
        symbol = self.req_id_to_symbol.get(req_id)
        if not symbol:
            return

        try:
            with self.lock:
                subscription = self.subscriptions.get(symbol)
                if subscription:
                    # Update subscription data
                    if "market_depth" not in subscription.data:
                        subscription.data["market_depth"] = []

                    depth_update = {
                        "position": position,
                        "operation": operation,
                        "side": side,
                        "price": price,
                        "size": size,
                        "timestamp": datetime.now().isoformat(),
                    }

                    subscription.data["market_depth"].append(depth_update)
                    # Keep only last 50 depth updates
                    subscription.data["market_depth"] = subscription.data["market_depth"][-50:]
                    subscription.last_update = datetime.now()

        except Exception as e:
            self.logger.error(f"Error processing market depth for {symbol}: {e}")

    def _on_error(self, req_id: int, error_code: int, error_string: str, contract: Any = None):
        """Handle IBKR errors"""
        symbol = self.req_id_to_symbol.get(req_id, "UNKNOWN")

        # Track error
        self.error_counts[symbol] += 1
        self.error_timestamps[symbol].append(time.time())

        # Log error
        self.logger.error(f"IBKR Error [{symbol}]: {error_code} - {error_string}")

        # Update subscription status
        if symbol in self.subscriptions:
            subscription = self.subscriptions[symbol]
            subscription.error_count += 1

            # Mark as error if too many failures
            if subscription.error_count >= self.config.get("error_thresholds", {}).get("max_consecutive_errors", 10):
                subscription.status = SubscriptionStatus.ERROR

    # ==========================================================================
    # PRIVATE METHODS - EVENT PUBLISHING
    # ==========================================================================
    def _publish_market_update(self, subscription: MarketDataSubscription, data: Dict[str, Any]):
        """Publish market data update event"""
        try:
            update = MarketDataUpdate(
                symbol=subscription.symbol,
                timestamp=datetime.now(),
                data=data,
                quality=DataQuality.REALTIME,
                tier=subscription.tier,
            )

            event = Event(
                EventType.MARKET_DATA_TICK,
                {
                    "update": update,
                    "symbol": subscription.symbol,
                    "timestamp": update.timestamp.isoformat(),
                    "tier": subscription.tier,
                },
            )

            self.event_manager.publish(event)

        except Exception as e:
            self.logger.error(f"Error publishing market update for {subscription.symbol}: {e}")

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _count_subscriptions_by_tier(self) -> Dict[str, int]:
        """Count active subscriptions by tier"""
        counts = defaultdict(int)
        for sub in self.subscriptions.values():
            if sub.status == SubscriptionStatus.ACTIVE:
                counts[sub.tier] += 1
        return dict(counts)

    def _publish_connection_error(self):
        """Publish connection error event"""
        event = Event(
            EventType.SYSTEM_ERROR,
            {"component": "MarketDataHub", "error": "Connection lost", "severity": "critical"},
        )
        self.event_manager.publish(event)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the Market Data Hub
    from SpyderB_Broker.SpyderB01_SpyderClient import IBConfig, SpyderClient

    # Initialize components
    event_manager = EventManager()
    ib_config = IBConfig(host="127.0.0.1", port=7497, client_id=1)  # Paper trading port

    ib_client = SpyderClient(ib_config, event_manager)

    # Connect to IBKR
    if ib_client.connect():
        # Create and start hub
        hub = MarketDataHub(ib_client, event_manager)

        # Subscribe to events
        @event_manager.subscribe(EventType.MARKET_DATA_TICK)
        def on_market_data(event: Event):
            update = event.data["update"]
            print(f"📊 {update.symbol}: {update.data}")

        # Start hub
        hub.start()

        # Test subscriptions
        hub.subscribe("SPY", "CRITICAL")
        hub.subscribe("VIX", "CRITICAL")
        hub.subscribe("TLT", "LOW")

        # Monitor for a bit
        time.sleep(30)

        # Check status
        status = hub.get_subscription_status()
        print(f"\n📈 Subscription Status: {json.dumps(status, indent=2)}")

        # Stop hub
        hub.stop()
        ib_client.disconnect()
    else:
        print("Failed to connect to IBKR")