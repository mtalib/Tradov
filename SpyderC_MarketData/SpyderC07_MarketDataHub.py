#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderC07_MarketDataHub.py
Group: C (Market Data)
Purpose: Centralized IBKR market data subscription and distribution hub

Description:
    This module serves as the central hub for all Interactive Brokers market data
    subscriptions. It implements intelligent rate limiting, tiered update frequencies,
    connection pooling, and distributes data throughout the Spyder system via the
    event manager. Replaces the previous OPRAFeed module with enhanced capabilities.

Author: Assistant
Date Created: 2025-01-23
Last Updated: 2025-01-23
"""

import asyncio
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

from SpyderA_Core.SpyderA05_EventManager import Event, EventManager, EventType
from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderB_Broker.SpyderB10_IBDataTypes import SecurityType, TickType
# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from SpyderU_Utilities.SpyderU09_DataTypes import MarketDataType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Subscription Tiers
UPDATE_TIERS = {
    "CRITICAL": {
        "symbols": ["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
        "frequency": 1,  # seconds
        "priority": 1,
        "method": "streaming",  # continuous updates
    },
    "HIGH": {
        "symbols": [
            "VIX9D",
            "VXV",
            "VXMT",
            "VVIX",
            "UVXY",
            "TRIN-NYSE",
            "ADD-NYSE",
            "CPC",
            "PCALL",
            "SKEW",
            "DIA",
            "QQQ",
            "IWM",
        ],
        "frequency": 5,
        "priority": 2,
        "method": "streaming",
    },
    "MEDIUM": {
        "symbols": [
            "VXST",
            "VXN",
            "RVX",
            "CPCE",
            "CPCI",
            "TICK-NASDAQ",
            "TRIN-NASDAQ",
            "XLF",
            "XLK",
            "XLE",
            "XLV",
            "XLI",
            "XLY",
            "XLP",
            "XLU",
            "XLRE",
            "XLC",
            "XLB",
        ],
        "frequency": 30,
        "priority": 3,
        "method": "snapshot",  # periodic snapshots
    },
    "LOW": {
        "symbols": ["TLT", "LQD", "DXY", "GLD", "NYHL-NYSE"],
        "frequency": 15,
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
        """Initialize Market Data Hub"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.ib_client = ib_client
        self.event_manager = event_manager
        self.contract_builder = ContractBuilder()

        # Configuration
        self.config = self._load_config(config_path)

        # Subscription management
        self.subscriptions: Dict[str, MarketDataSubscription] = {}
        self.req_id_to_symbol: Dict[int, str] = {}
        self.next_req_id = 10000
        self._subscription_lock = threading.RLock()

        # Update scheduling
        self.update_schedulers: Dict[str, threading.Timer] = {}
        self.snapshot_queue: deque = deque()
        self.last_snapshot_time = datetime.now()

        # Connection management
        self.is_connected = False
        self.reconnect_attempts = 0
        self.connection_monitor: Optional[threading.Thread] = None

        # Rate limiting
        self.request_timestamps: deque = deque(maxlen=50)
        self.subscription_count = 0

        # Data cache
        self.data_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}

        # Threading
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.running = False
        self._stop_event = threading.Event()

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
    def start(self):
        """Start the market data hub"""
        try:
            self.running = True
            self._stop_event.clear()

            # Start connection monitor
            self.connection_monitor = threading.Thread(target=self._monitor_connection, daemon=True)
            self.connection_monitor.start()

            # Subscribe to all configured symbols
            self._initialize_subscriptions()

            # Start snapshot processor
            self._start_snapshot_processor()

            self.logger.info("Market Data Hub started successfully")

        except Exception as e:
            self.logger.error(f"Failed to start Market Data Hub: {e}")
            self.error_handler.handle_error(e, {"method": "start"})
            raise

    def stop(self):
        """Stop the market data hub"""
        self.running = False
        self._stop_event.set()

        # Cancel all subscriptions
        with self._subscription_lock:
            for symbol, sub in self.subscriptions.items():
                if sub.status == SubscriptionStatus.ACTIVE:
                    self._cancel_subscription(sub)

        # Stop schedulers
        for scheduler in self.update_schedulers.values():
            scheduler.cancel()

        # Shutdown executor
        self.executor.shutdown(wait=True)

        self.logger.info("Market Data Hub stopped")

    def subscribe(self, symbol: str, tier: Optional[str] = None) -> bool:
        """
        Subscribe to market data for a symbol.

        Args:
            symbol: Symbol to subscribe to
            tier: Update tier (auto-detected if not specified)

        Returns:
            Success status
        """
        with self._subscription_lock:
            # Check if already subscribed
            if symbol in self.subscriptions:
                self.logger.debug(f"Already subscribed to {symbol}")
                return True

            # Check subscription limits
            if self.subscription_count >= MAX_CONCURRENT_SUBSCRIPTIONS:
                self.logger.warning(f"Subscription limit reached ({MAX_CONCURRENT_SUBSCRIPTIONS})")
                return False

            # Determine tier if not specified
            if not tier:
                tier = self._get_symbol_tier(symbol)

            # Create subscription
            try:
                subscription = self._create_subscription(symbol, tier)
                self.subscriptions[symbol] = subscription
                self.req_id_to_symbol[subscription.req_id] = symbol

                # Request market data
                self._request_market_data(subscription)

                self.subscription_count += 1
                self.logger.info(f"Subscribed to {symbol} (tier: {tier})")
                return True

            except Exception as e:
                self.logger.error(f"Failed to subscribe to {symbol}: {e}")
                return False

    def unsubscribe(self, symbol: str):
        """Unsubscribe from market data for a symbol"""
        with self._subscription_lock:
            if symbol not in self.subscriptions:
                return

            subscription = self.subscriptions[symbol]
            self._cancel_subscription(subscription)

            # Cleanup
            del self.subscriptions[symbol]
            del self.req_id_to_symbol[subscription.req_id]
            self.subscription_count -= 1

            self.logger.info(f"Unsubscribed from {symbol}")

    def get_latest_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get latest market data for a symbol"""
        # Check cache first
        if symbol in self.data_cache:
            cache_age = (datetime.now() - self.cache_timestamps[symbol]).total_seconds()
            if cache_age < self.config["cache_settings"]["ttl_seconds"]:
                return self.data_cache[symbol]

        # Check subscription data
        if symbol in self.subscriptions:
            return self.subscriptions[symbol].data

        return None

    def get_subscription_status(self) -> Dict[str, Any]:
        """Get current subscription status"""
        with self._subscription_lock:
            return {
                "active_subscriptions": self.subscription_count,
                "max_subscriptions": MAX_CONCURRENT_SUBSCRIPTIONS,
                "subscriptions_by_tier": self._count_subscriptions_by_tier(),
                "error_symbols": [s for s, c in self.error_counts.items() if c > 0],
                "connection_status": "connected" if self.is_connected else "disconnected",
            }

    # ==========================================================================
    # SUBSCRIPTION MANAGEMENT
    # ==========================================================================
    def _initialize_subscriptions(self):
        """Initialize all configured subscriptions"""
        all_symbols = []

        # Collect all symbols from tiers
        for tier_name, tier_config in UPDATE_TIERS.items():
            for symbol in tier_config["symbols"]:
                all_symbols.append((symbol, tier_name))

        # Sort by priority
        all_symbols.sort(key=lambda x: UPDATE_TIERS[x[1]]["priority"])

        # Subscribe with rate limiting
        for symbol, tier in all_symbols:
            if not self.running:
                break

            self.subscribe(symbol, tier)
            time.sleep(0.1)  # Rate limit subscriptions

    def _create_subscription(self, symbol: str, tier: str) -> MarketDataSubscription:
        """Create a new subscription object"""
        # Get contract specification
        spec = SYMBOL_SPECS.get(symbol, {})

        # Build contract
        if spec.get("type") == "STK":
            contract = self.contract_builder.build_stock(symbol)
        elif spec.get("type") == "IND":
            contract = self._build_index_contract(symbol, spec)
        elif spec.get("type") == "FUT":
            contract = self._build_future_contract(symbol, spec)
        else:
            # Default to stock
            contract = self.contract_builder.build_stock(symbol)

        # Create subscription
        subscription = MarketDataSubscription(
            symbol=symbol,
            req_id=self._get_next_req_id(),
            contract=contract,
            tier=tier,
            status=SubscriptionStatus.PENDING,
        )

        return subscription

    def _request_market_data(self, subscription: MarketDataSubscription):
        """Request market data from IBKR"""
        tier_config = UPDATE_TIERS[subscription.tier]

        if tier_config["method"] == "streaming":
            # Request streaming data
            self.ib_client.ib.reqMktData(
                subscription.req_id,
                subscription.contract,
                "",  # Generic tick list
                False,  # Snapshot
                False,  # Regulatory snapshot
                [],
            )
        else:
            # Add to snapshot queue
            self.snapshot_queue.append(subscription)

        subscription.status = SubscriptionStatus.ACTIVE

    def _cancel_subscription(self, subscription: MarketDataSubscription):
        """Cancel a market data subscription"""
        if subscription.status == SubscriptionStatus.ACTIVE:
            self.ib_client.ib.cancelMktData(subscription.req_id)
        subscription.status = SubscriptionStatus.CANCELLED

    # ==========================================================================
    # IBKR CALLBACKS
    # ==========================================================================
    def _on_tick_price(self, req_id: int, tick_type: int, price: float, size: float):
        """Handle price tick from IBKR"""
        if req_id not in self.req_id_to_symbol:
            return

        symbol = self.req_id_to_symbol[req_id]
        subscription = self.subscriptions[symbol]

        # Update data
        field_map = {1: "bid", 2: "ask", 4: "last", 6: "high", 7: "low", 9: "close", 14: "open"}

        if tick_type in field_map:
            field = field_map[tick_type]
            subscription.data[field] = price
            if size > 0:
                subscription.data[f"{field}_size"] = size

            subscription.last_update = datetime.now()

            # Publish update
            self._publish_update(symbol, subscription)

    def _on_tick_size(self, req_id: int, tick_type: int, size: int):
        """Handle size tick from IBKR"""
        if req_id not in self.req_id_to_symbol:
            return

        symbol = self.req_id_to_symbol[req_id]
        subscription = self.subscriptions[symbol]

        # Update size data
        size_map = {0: "bid_size", 3: "ask_size", 5: "last_size", 8: "volume"}

        if tick_type in size_map:
            field = size_map[tick_type]
            subscription.data[field] = size
            subscription.last_update = datetime.now()

    def _on_tick_string(self, req_id: int, tick_type: int, value: str):
        """Handle string tick from IBKR"""
        if req_id not in self.req_id_to_symbol:
            return

        symbol = self.req_id_to_symbol[req_id]
        subscription = self.subscriptions[symbol]

        # Handle specific string types
        if tick_type == 48:  # RT Volume
            subscription.data["rt_volume"] = value
        elif tick_type == 45:  # Last timestamp
            subscription.data["last_timestamp"] = value

    def _on_tick_generic(self, req_id: int, tick_type: int, value: float):
        """Handle generic tick from IBKR"""
        if req_id not in self.req_id_to_symbol:
            return

        symbol = self.req_id_to_symbol[req_id]
        subscription = self.subscriptions[symbol]

        # Handle specific generic types
        generic_map = {
            23: "option_implied_volatility",
            24: "option_volume",
            31: "index_future_premium",
            46: "shortable",
            49: "halted",
            54: "trade_count",
            55: "trade_rate",
            56: "volume_rate",
        }

        if tick_type in generic_map:
            field = generic_map[tick_type]
            subscription.data[field] = value
            subscription.last_update = datetime.now()

    def _on_tick_option(
        self,
        req_id: int,
        tick_type: int,
        tick_attrib: int,
        implied_vol: float,
        delta: float,
        opt_price: float,
        pv_dividend: float,
        gamma: float,
        vega: float,
        theta: float,
        und_price: float,
    ):
        """Handle option computation tick"""
        if req_id not in self.req_id_to_symbol:
            return

        symbol = self.req_id_to_symbol[req_id]
        subscription = self.subscriptions[symbol]

        # Store option data
        subscription.data["option"] = {
            "implied_volatility": implied_vol,
            "delta": delta,
            "option_price": opt_price,
            "dividend_pv": pv_dividend,
            "gamma": gamma,
            "vega": vega,
            "theta": theta,
            "underlying_price": und_price,
        }

        subscription.last_update = datetime.now()
        self._publish_update(symbol, subscription)

    def _on_market_depth(
        self, req_id: int, position: int, operation: int, side: int, price: float, size: int
    ):
        """Handle market depth updates"""
        # Implement if needed for order book analysis
        pass

    def _on_error(self, req_id: int, error_code: int, error_string: str):
        """Handle IBKR errors"""
        if req_id in self.req_id_to_symbol:
            symbol = self.req_id_to_symbol[req_id]
            subscription = self.subscriptions[symbol]

            # Track errors
            subscription.error_count += 1
            self.error_counts[symbol] += 1
            self.error_timestamps[symbol].append(datetime.now())

            # Log error
            self.logger.error(f"Market data error for {symbol}: [{error_code}] {error_string}")

            # Handle specific errors
            if error_code in [200, 162]:  # No security definition
                subscription.status = SubscriptionStatus.ERROR
            elif error_code == 354:  # Not subscribed
                subscription.status = SubscriptionStatus.ERROR

    # ==========================================================================
    # DATA DISTRIBUTION
    # ==========================================================================
    def _publish_update(self, symbol: str, subscription: MarketDataSubscription):
        """Publish market data update via event system"""
        # Update cache
        self.data_cache[symbol] = subscription.data.copy()
        self.cache_timestamps[symbol] = datetime.now()

        # Determine data quality
        quality = DataQuality.REALTIME
        if subscription.last_update:
            age = (datetime.now() - subscription.last_update).total_seconds()
            if age > 60:
                quality = DataQuality.STALE
            elif age > 5:
                quality = DataQuality.DELAYED

        # Create update event
        update = MarketDataUpdate(
            symbol=symbol,
            timestamp=datetime.now(),
            data=subscription.data.copy(),
            quality=quality,
            tier=subscription.tier,
        )

        # Publish event
        event = Event(
            EventType.MARKET_DATA_TICK,
            {"symbol": symbol, "update": update, "subscription": subscription},
        )

        self.event_manager.publish(event)

    # ==========================================================================
    # SNAPSHOT PROCESSING
    # ==========================================================================
    def _start_snapshot_processor(self):
        """Start the snapshot request processor"""

        def process_snapshots():
            while self.running:
                if self.snapshot_queue:
                    # Rate limit snapshots
                    time_since_last = (datetime.now() - self.last_snapshot_time).total_seconds()
                    if time_since_last >= 1.0 / MAX_SNAPSHOT_REQUESTS_PER_SECOND:
                        subscription = self.snapshot_queue.popleft()
                        self._request_snapshot(subscription)
                        self.last_snapshot_time = datetime.now()

                time.sleep(0.1)

        snapshot_thread = threading.Thread(target=process_snapshots, daemon=True)
        snapshot_thread.start()

    def _request_snapshot(self, subscription: MarketDataSubscription):
        """Request a snapshot of market data"""
        self.ib_client.ib.reqMktData(
            subscription.req_id, subscription.contract, "", True, False, []  # Snapshot
        )

        # Re-queue based on tier frequency
        tier_config = UPDATE_TIERS[subscription.tier]
        self.executor.submit(self._requeue_snapshot, subscription, tier_config["frequency"])

    def _requeue_snapshot(self, subscription: MarketDataSubscription, delay: float):
        """Re-queue a snapshot request after delay"""
        time.sleep(delay)
        if self.running and subscription.status == SubscriptionStatus.ACTIVE:
            self.snapshot_queue.append(subscription)

    # ==========================================================================
    # CONNECTION MANAGEMENT
    # ==========================================================================
    def _monitor_connection(self):
        """Monitor and maintain IBKR connection"""
        while self.running:
            try:
                # Check connection
                if not self.ib_client.is_connected():
                    self.is_connected = False
                    self.logger.warning("Lost connection to IBKR")
                    self._handle_disconnection()
                else:
                    self.is_connected = True
                    self.reconnect_attempts = 0

                # Send heartbeat
                if self.is_connected:
                    self.ib_client.ib.reqCurrentTime()

            except Exception as e:
                self.logger.error(f"Connection monitor error: {e}")

            self._stop_event.wait(HEARTBEAT_INTERVAL)

    def _handle_disconnection(self):
        """Handle disconnection from IBKR"""
        if self.reconnect_attempts >= MAX_RECONNECT_ATTEMPTS:
            self.logger.error("Max reconnection attempts reached")
            self._publish_connection_error()
            return

        self.reconnect_attempts += 1
        delay = RECONNECT_DELAY_BASE * (2 ** (self.reconnect_attempts - 1))

        self.logger.info(
            f"Attempting reconnection {
                self.reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS} in {delay}s"
        )
        time.sleep(delay)

        try:
            self.ib_client.connect()
            if self.ib_client.is_connected():
                self.logger.info("Reconnection successful")
                self._resubscribe_all()
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")

    def _resubscribe_all(self):
        """Resubscribe to all active subscriptions after reconnection"""
        with self._subscription_lock:
            for symbol, subscription in self.subscriptions.items():
                if subscription.status == SubscriptionStatus.ACTIVE:
                    self._request_market_data(subscription)

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _get_symbol_tier(self, symbol: str) -> str:
        """Determine the tier for a symbol"""
        for tier_name, tier_config in UPDATE_TIERS.items():
            if symbol in tier_config["symbols"]:
                return tier_name
        return "MEDIUM"  # Default tier

    def _get_next_req_id(self) -> int:
        """Get next available request ID"""
        req_id = self.next_req_id
        self.next_req_id += 1
        return req_id

    def _build_index_contract(self, symbol: str, spec: Dict[str, Any]) -> Any:
        """Build an index contract"""
        from ib_insync import Index

        return Index(
            symbol=spec.get("symbol", symbol),
            exchange=spec.get("exchange", "CBOE"),
            currency=spec.get("currency", "USD"),
        )

    def _build_future_contract(self, symbol: str, spec: Dict[str, Any]) -> Any:
        """Build a futures contract"""
        from ib_insync import Future

        return Future(
            symbol=spec.get("symbol", symbol.replace("/", "")),
            exchange=spec.get("exchange", "CME"),
            currency=spec.get("currency", "USD"),
            localSymbol=spec.get("localSymbol", ""),
        )

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
