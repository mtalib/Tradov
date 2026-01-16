#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderC_MarketData
Module: SpyderC01_DataFeed.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import threading
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable, Set, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict, deque
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
from Spyder.SpyderU_Utilities.SpyderU09_DataTypes import MarketDataType
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager, EventType, Event
from Spyder.SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
from Spyder.SpyderC_MarketData.SpyderC07_MarketDataHub import MarketDataHub, MarketDataUpdate
from Spyder.SpyderC_MarketData.SpyderC16_MarketDataCache import MarketDataCache, DataGranularity
from Spyder.SpyderC_MarketData.SpyderC06_DataValidator import DataValidator

DEFAULT_FEED_CONFIG = {
    'cache_enabled': True,
    'hub_enabled': True,
    'validation_enabled': True,
    'buffer_size': 1000,
    'update_interval': 0.1,  # 100ms
    'heartbeat_interval': 30,
    'error_threshold': 10,
    'custom_metrics': {
        'gex': {'enabled': True, 'module': 'SpyderC15_GEXDEXCalculator'},
        'dix': {'enabled': True, 'module': 'SpyderS01_DIXCalculator'},
        'swan': {'enabled': True, 'module': 'SpyderS06_BlackSwanDataCollector'}
    }
}

# Symbol Groups for Efficient Management
SYMBOL_GROUPS = {
    'CORE': ['SPY', 'SPX', '/ES'],
    'VOLATILITY': ['VIX', 'VIX9D', 'VXV', 'VXMT', 'VVIX', 'UVXY'],
    'INTERNALS': ['TICK-NYSE', 'TRIN-NYSE', 'ADD-NYSE', 'CPC', 'PCALL', 'SKEW'],
    'INDICES': ['DIA', 'QQQ', 'IWM'],
    'FIXED_INCOME': ['TLT', 'LQD'],
    'CORRELATIONS': ['DXY', 'GLD']
}

# ==============================================================================
# ENUMS
# ==============================================================================
class DataFeedStatus(Enum):
    """Data feed connection status."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    DEGRADED = "degraded"

class DataSource(Enum):
    """Available data sources."""
    IBKR = "ibkr"
    CACHE = "cache"
    CUSTOM = "custom"
    SYNTHETIC = "synthetic"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketTick:
    """Enhanced market tick data structure."""
    symbol: str
    timestamp: datetime
    price: float
    size: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    vwap: Optional[float] = None
    source: DataSource = DataSource.IBKR
    quality: str = "realtime"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'size': self.size,
            'bid': self.bid,
            'ask': self.ask,
            'bid_size': self.bid_size,
            'ask_size': self.ask_size,
            'volume': self.volume,
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'vwap': self.vwap,
            'source': self.source.value,
            'quality': self.quality
        }

@dataclass
class DataFeedConfig:
    """Enhanced data feed configuration."""
    hub_enabled: bool = True
    cache_enabled: bool = True
    validation_enabled: bool = True
    buffer_size: int = 1000
    update_interval: float = 0.1
    heartbeat_interval: int = 30
    error_threshold: int = 10
    custom_metrics_config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'DataFeedConfig':
        """Create from dictionary."""
        return cls(**config_dict)

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DataFeedManager:
    """
    Enhanced central data feed orchestrator.
    
    This class manages all market data operations by coordinating between:
    - MarketDataHub for IBKR connections
    - MarketDataCache for efficient storage
    - Custom metric calculators
    - Event-based distribution system
    """
    
    def __init__(self, ib_client: Optional[SpyderClient] = None,
                 event_manager: Optional[EventManager] = None,
                 config: Optional[Union[DataFeedConfig, Dict]] = None):
        """Initialize enhanced data feed manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        if isinstance(config, dict):
            self.config = DataFeedConfig.from_dict(config)
        else:
            self.config = config or DataFeedConfig()
        
        # Core components
        self.ib_client = ib_client
        self.event_manager = event_manager or EventManager()
        
        # Initialize sub-components
        self.market_hub: Optional[MarketDataHub] = None
        self.market_cache: Optional[MarketDataCache] = None
        self.data_validator = DataValidator()
        
        # State management
        self.status = DataFeedStatus.DISCONNECTED
        self.is_running = False
        self.last_update = None
        
        # Data storage
        self.data_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=self.config.buffer_size))
        self.current_data: Dict[str, MarketTick] = {}
        self.symbol_status: Dict[str, Dict[str, Any]] = {}
        
        # Subscribers
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.group_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Custom metric handlers
        self.custom_handlers: Dict[str, Any] = {}
        
        # Threading
        self._lock = threading.RLock()
        self._update_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # Error tracking
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.last_errors: Dict[str, str] = {}
        
        # Initialize components
        self._initialize_components()
        
        self.logger.info("Enhanced DataFeedManager initialized")
    
    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _initialize_components(self):
        """Initialize sub-components based on configuration."""
        try:
            # Initialize market data hub
            if self.config.hub_enabled and self.ib_client:
                self.market_hub = MarketDataHub(
                    self.ib_client,
                    self.event_manager
                )
                self.logger.info("MarketDataHub initialized")
            
            # Initialize market data cache
            if self.config.cache_enabled:
                self.market_cache = MarketDataCache(
                    event_manager=self.event_manager
                )
                self.logger.info("MarketDataCache initialized")
            
            # Subscribe to market data events
            self._setup_event_subscriptions()
            
            # Load custom metric handlers
            self._load_custom_handlers()
            
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            self.error_handler.handle_error(e, {"method": "_initialize_components"})
    
    def _setup_event_subscriptions(self):
        """Setup event subscriptions for market data updates."""
        # Subscribe to market data updates from hub
        @self.event_manager.subscribe(EventType.MARKET_DATA_TICK)
        def on_market_data_tick(event: Event):
            self._handle_market_data_update(event.data)
        
        # Subscribe to custom metric updates
        @self.event_manager.subscribe(EventType.CUSTOM_METRIC_UPDATE)
        def on_custom_metric(event: Event):
            self._handle_custom_metric_update(event.data)
        
        # Subscribe to system events
        @self.event_manager.subscribe(EventType.SYSTEM_ERROR)
        def on_system_error(event: Event):
            self._handle_system_error(event.data)
    
    def _load_custom_handlers(self):
        """Load custom metric calculation handlers."""
        for metric_name, config in self.config.custom_metrics_config.items():
            if config.get('enabled'):
                try:
                    # Dynamic import of custom metric module
                    module_name = config['module']
                    # This would be implemented based on actual module structure
                    self.logger.info(f"Loaded custom handler for {metric_name}")
                except Exception as e:
                    self.logger.error(f"Failed to load {metric_name} handler: {e}")
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the enhanced data feed system.
        
        Returns:
            Success status
        """
        try:
            if self.is_running:
                self.logger.warning("Data feed already running")
                return True
            
            self.is_running = True
            self.status = DataFeedStatus.CONNECTING
            
            # Start sub-components
            if self.market_hub:
                self.market_hub.start()
            
            if self.market_cache:
                self.market_cache.start()
            
            # Start update thread
            self._update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True
            )
            self._update_thread.start()
            
            # Start monitor thread
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            self._monitor_thread.start()
            
            # Wait for connection
            time.sleep(2)
            
            # Update status
            if self.market_hub and self.market_hub.is_connected:
                self.status = DataFeedStatus.CONNECTED
            else:
                self.status = DataFeedStatus.DEGRADED
            
            self.logger.info(f"Data feed started with status: {self.status.value}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start data feed: {e}")
            self.status = DataFeedStatus.ERROR
            return False
    
    def stop(self) -> bool:
        """
        Stop the data feed system.
        
        Returns:
            Success status
        """
        try:
            self.is_running = False
            
            # Stop sub-components
            if self.market_hub:
                self.market_hub.stop()
            
            if self.market_cache:
                self.market_cache.stop()
            
            # Wait for threads
            if self._update_thread:
                self._update_thread.join(timeout=5)
            
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5)
            
            # Shutdown executor
            self.executor.shutdown(wait=True)
            
            self.status = DataFeedStatus.DISCONNECTED
            self.logger.info("Data feed stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping data feed: {e}")
            return False
    
    def subscribe(self, symbol: str, callback: Callable[[MarketTick], None],
                  priority: Optional[str] = None) -> bool:
        """
        Subscribe to market data updates for a symbol.
        
        Args:
            symbol: Market symbol
            callback: Function to call on updates
            priority: Subscription priority (CRITICAL, HIGH, MEDIUM, LOW)
            
        Returns:
            Success status
        """
        with self._lock:
            # Add callback
            self.subscribers[symbol].append(callback)
            
            # Subscribe via hub if available
            if self.market_hub:
                tier = priority or self._get_symbol_tier(symbol)
                success = self.market_hub.subscribe(symbol, tier)
                
                if success:
                    self.symbol_status[symbol] = {
                        'subscribed': True,
                        'tier': tier,
                        'last_update': None
                    }
                
                return success
            
            return True
    
    def unsubscribe(self, symbol: str, callback: Optional[Callable] = None) -> bool:
        """
        Unsubscribe from market data updates.
        
        Args:
            symbol: Market symbol
            callback: Specific callback to remove (None for all)
            
        Returns:
            Success status
        """
        with self._lock:
            if symbol in self.subscribers:
                if callback and callback in self.subscribers[symbol]:
                    self.subscribers[symbol].remove(callback)
                elif not callback:
                    self.subscribers[symbol].clear()
                
                # Unsubscribe from hub if no more subscribers
                if not self.subscribers[symbol] and self.market_hub:
                    self.market_hub.unsubscribe(symbol)
                    del self.symbol_status[symbol]
                
                return True
            
            return False
    
    def subscribe_group(self, group_name: str, callback: Callable[[Dict[str, MarketTick]], None]) -> bool:
        """
        Subscribe to a group of symbols.
        
        Args:
            group_name: Name of symbol group (CORE, VOLATILITY, etc.)
            callback: Function to call with group updates
            
        Returns:
            Success status
        """
        if group_name not in SYMBOL_GROUPS:
            self.logger.error(f"Unknown symbol group: {group_name}")
            return False
        
        with self._lock:
            # Add group callback
            self.group_subscribers[group_name].append(callback)
            
            # Subscribe to all symbols in group
            for symbol in SYMBOL_GROUPS[group_name]:
                self.subscribe(symbol, self._create_group_callback(group_name))
            
            return True
    
    def get_market_data(self, symbol: str, use_cache: bool = True) -> Optional[MarketTick]:
        """
        Get latest market data for a symbol.
        
        Args:
            symbol: Market symbol
            use_cache: Whether to use cached data
            
        Returns:
            Latest market tick or None
        """
        # Check current data first
        with self._lock:
            if symbol in self.current_data:
                return self.current_data[symbol]
        
        # Check cache if enabled
        if use_cache and self.market_cache:
            cached_data = self.market_cache.get(symbol)
            if cached_data:
                return self._convert_cached_to_tick(symbol, cached_data)
        
        # Request from hub if available
        if self.market_hub:
            hub_data = self.market_hub.get_latest_data(symbol)
            if hub_data:
                return self._convert_hub_to_tick(symbol, hub_data)
        
        return None
    
    def get_historical_data(self, symbol: str, start_time: datetime,
                          end_time: datetime, granularity: str = "1min") -> pd.DataFrame:
        """
        Get historical market data.
        
        Args:
            symbol: Market symbol
            start_time: Start timestamp
            end_time: End timestamp
            granularity: Data granularity (tick, 1min, 5min, etc.)
            
        Returns:
            DataFrame with historical data
        """
        if self.market_cache:
            # Map granularity string to enum
            gran_map = {
                'tick': DataGranularity.TICK,
                '1min': DataGranularity.MINUTE,
                '5min': DataGranularity.MINUTE,  # Will be resampled
                '1hour': DataGranularity.HOUR,
                'daily': DataGranularity.DAILY
            }
            
            gran_enum = gran_map.get(granularity, DataGranularity.MINUTE)
            df = self.market_cache.get_range(symbol, start_time, end_time, gran_enum)
            
            # Resample if needed (e.g., for 5min)
            if granularity == '5min' and not df.empty:
                df = df.resample('5T').agg({
                    'bid': 'last',
                    'ask': 'last',
                    'last': 'last',
                    'volume': 'sum'
                })
            
            return df
        
        return pd.DataFrame()
    
    def get_snapshot(self, symbols: Optional[List[str]] = None) -> Dict[str, MarketTick]:
        """
        Get snapshot of current market data.
        
        Args:
            symbols: List of symbols (None for all)
            
        Returns:
            Dictionary of symbol -> MarketTick
        """
        with self._lock:
            if symbols:
                return {s: self.current_data[s] for s in symbols if s in self.current_data}
            else:
                return self.current_data.copy()
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the data feed system."""
        with self._lock:
            status = {
                'feed_status': self.status.value,
                'is_running': self.is_running,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'active_symbols': len(self.current_data),
                'subscribed_symbols': list(self.symbol_status.keys()),
                'error_symbols': [s for s, c in self.error_counts.items() if c > 0],
                'cache_stats': self.market_cache.get_stats() if self.market_cache else {},
                'hub_status': self.market_hub.get_subscription_status() if self.market_hub else {}
            }
            
            return status
    
    # ==========================================================================
    # DATA HANDLING
    # ==========================================================================
    def _handle_market_data_update(self, data: Dict[str, Any]):
        """Handle market data update from hub."""
        try:
            update: MarketDataUpdate = data['update']
            symbol = update.symbol
            
            # Convert to MarketTick
            tick = self._convert_update_to_tick(update)
            
            # Validate if enabled
            if self.config.validation_enabled:
                if not self.data_validator.validate_tick(tick.to_dict()):
                    self.logger.warning(f"Invalid tick data for {symbol}")
                    self.error_counts[symbol] += 1
                    return
            
            # Update storage
            with self._lock:
                self.current_data[symbol] = tick
                self.data_buffers[symbol].append(tick)
                self.last_update = datetime.now()
                
                # Update symbol status
                if symbol in self.symbol_status:
                    self.symbol_status[symbol]['last_update'] = datetime.now()
            
            # Store in cache
            if self.market_cache:
                self.market_cache.put(
                    symbol,
                    tick.to_dict(),
                    priority=self._get_symbol_priority(symbol)
                )
            
            # Notify subscribers
            self._notify_subscribers(symbol, tick)
            
            # Reset error count on successful update
            self.error_counts[symbol] = 0
            
        except Exception as e:
            self.logger.error(f"Error handling market data update: {e}")
            self.error_handler.handle_error(e, {"method": "_handle_market_data_update"})
    
    def _handle_custom_metric_update(self, data: Dict[str, Any]):
        """Handle custom metric update."""
        try:
            metric_name = data['metric']
            symbol = data['symbol']
            value = data['value']
            
            # Create synthetic tick
            tick = MarketTick(
                symbol=symbol,
                timestamp=datetime.now(),
                price=value,
                size=0,
                source=DataSource.CUSTOM
            )
            
            # Update storage
            with self._lock:
                self.current_data[symbol] = tick
            
            # Notify subscribers
            self._notify_subscribers(symbol, tick)
            
        except Exception as e:
            self.logger.error(f"Error handling custom metric: {e}")
    
    def _handle_system_error(self, data: Dict[str, Any]):
        """Handle system error event."""
        component = data.get('component', 'Unknown')
        error = data.get('error', 'Unknown error')
        severity = data.get('severity', 'warning')
        
        self.logger.error(f"System error from {component}: {error}")
        
        if severity == 'critical' and component == 'MarketDataHub':
            self.status = DataFeedStatus.ERROR
    
    # ==========================================================================
    # UPDATE LOOPS
    # ==========================================================================
    def _update_loop(self):
        """Main update loop for processing market data."""
        while self.is_running:
            try:
                # Process any pending updates
                self._process_pending_updates()
                
                # Update custom metrics
                self._update_custom_metrics()
                
                # Check for stale data
                self._check_stale_data()
                
            except Exception as e:
                self.logger.error(f"Error in update loop: {e}")
            
            time.sleep(self.config.update_interval)
    
    def _monitor_loop(self):
        """Monitor loop for system health."""
        while self.is_running:
            try:
                # Check component health
                self._check_component_health()
                
                # Publish status update
                self._publish_status_update()
                
                # Clean up old data
                self._cleanup_old_data()
                
            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}")
            
            time.sleep(self.config.heartbeat_interval)
    
    def _process_pending_updates(self):
        """Process any pending market data updates."""
        # This is handled via event callbacks
        pass
    
    def _update_custom_metrics(self):
        """Update custom calculated metrics."""
        # GEX, DEX, DIX, SWAN updates would be triggered here
        for metric_name, handler in self.custom_handlers.items():
            try:
                self.executor.submit(handler.update)
            except Exception as e:
                self.logger.error(f"Error updating {metric_name}: {e}")
    
    def _check_stale_data(self):
        """Check for stale market data."""
        now = datetime.now()
        stale_threshold = timedelta(seconds=30)
        
        with self._lock:
            for symbol, status in self.symbol_status.items():
                if status['last_update']:
                    age = now - status['last_update']
                    if age > stale_threshold:
                        self.logger.warning(f"Stale data for {symbol}: {age.total_seconds()}s old")
                        
                        # Mark data quality as stale
                        if symbol in self.current_data:
                            self.current_data[symbol].quality = "stale"
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _notify_subscribers(self, symbol: str, tick: MarketTick):
        """Notify all subscribers of a symbol update."""
        # Direct subscribers
        if symbol in self.subscribers:
            for callback in self.subscribers[symbol]:
                try:
                    self.executor.submit(callback, tick)
                except Exception as e:
                    self.logger.error(f"Error in subscriber callback: {e}")
        
        # Group subscribers
        for group_name, symbols in SYMBOL_GROUPS.items():
            if symbol in symbols and group_name in self.group_subscribers:
                # Collect group data
                group_data = self._get_group_snapshot(group_name)
                for callback in self.group_subscribers[group_name]:
                    try:
                        self.executor.submit(callback, group_data)
                    except Exception as e:
                        self.logger.error(f"Error in group callback: {e}")
    
    def _create_group_callback(self, group_name: str) -> Callable:
        """Create a callback for group subscriptions."""
        def group_callback(tick: MarketTick):
            # Group callbacks are handled in _notify_subscribers
            pass
        return group_callback
    
    def _get_group_snapshot(self, group_name: str) -> Dict[str, MarketTick]:
        """Get snapshot of all symbols in a group."""
        symbols = SYMBOL_GROUPS.get(group_name, [])
        with self._lock:
            return {s: self.current_data[s] for s in symbols if s in self.current_data}
    
    def _convert_update_to_tick(self, update: MarketDataUpdate) -> MarketTick:
        """Convert MarketDataUpdate to MarketTick."""
        data = update.data
        return MarketTick(
            symbol=update.symbol,
            timestamp=update.timestamp,
            price=data.get('last', 0.0),
            size=data.get('last_size', 0),
            bid=data.get('bid'),
            ask=data.get('ask'),
            bid_size=data.get('bid_size'),
            ask_size=data.get('ask_size'),
            volume=data.get('volume'),
            open=data.get('open'),
            high=data.get('high'),
            low=data.get('low'),
            close=data.get('close'),
            vwap=data.get('vwap'),
            source=DataSource.IBKR,
            quality=update.quality.value
        )
    
    def _convert_cached_to_tick(self, symbol: str, data: Dict[str, Any]) -> MarketTick:
        """Convert cached data to MarketTick."""
        return MarketTick(
            symbol=symbol,
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.now().isoformat())),
            price=data.get('last', data.get('price', 0.0)),
            size=data.get('last_size', data.get('size', 0)),
            bid=data.get('bid'),
            ask=data.get('ask'),
            bid_size=data.get('bid_size'),
            ask_size=data.get('ask_size'),
            volume=data.get('volume'),
            open=data.get('open'),
            high=data.get('high'),
            low=data.get('low'),
            close=data.get('close'),
            vwap=data.get('vwap'),
            source=DataSource.CACHE,
            quality="cached"
        )
    
    def _convert_hub_to_tick(self, symbol: str, data: Dict[str, Any]) -> MarketTick:
        """Convert hub data to MarketTick."""
        return self._convert_cached_to_tick(symbol, data)
    
    def _get_symbol_tier(self, symbol: str) -> str:
        """Determine tier for a symbol."""
        for group, symbols in SYMBOL_GROUPS.items():
            if symbol in symbols:
                if group == 'CORE':
                    return 'CRITICAL'
                elif group in ['VOLATILITY', 'INTERNALS']:
                    return 'HIGH'
                elif group == 'INDICES':
                    return 'MEDIUM'
                else:
                    return 'LOW'
        return 'MEDIUM'
    
    def _get_symbol_priority(self, symbol: str) -> int:
        """Get cache priority for a symbol."""
        tier = self._get_symbol_tier(symbol)
        priority_map = {
            'CRITICAL': 1,
            'HIGH': 2,
            'MEDIUM': 3,
            'LOW': 4
        }
        return priority_map.get(tier, 3)
    
    def _check_component_health(self):
        """Check health of all components."""
        # Check hub
        if self.market_hub:
            hub_status = self.market_hub.get_subscription_status()
            if hub_status['connection_status'] != 'connected':
                self.status = DataFeedStatus.DEGRADED
        
        # Check cache
        if self.market_cache:
            cache_stats = self.market_cache.get_stats()
            if cache_stats['hit_rate'] < 0.5:
                self.logger.warning(f"Low cache hit rate: {cache_stats['hit_rate']:.2%}")
        
        # Check error rates
        high_error_symbols = [s for s, c in self.error_counts.items() 
                            if c > self.config.error_threshold]
        if high_error_symbols:
            self.logger.warning(f"High error rates for: {high_error_symbols}")
    
    def _publish_status_update(self):
        """Publish system status update."""
        status = self.get_status()
        
        event = Event(
            EventType.SYSTEM_STATUS,
            {
                'component': 'DataFeedManager',
                'status': status,
                'timestamp': datetime.now()
            }
        )
        
        self.event_manager.publish(event)
    
    def _cleanup_old_data(self):
        """Clean up old data from buffers."""
        cutoff_time = datetime.now() - timedelta(minutes=30)
        
        with self._lock:
            for symbol, buffer in self.data_buffers.items():
                # Remove old entries
                while buffer and buffer[0].timestamp < cutoff_time:
                    buffer.popleft()
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def shutdown(self):
        """Shutdown the data feed manager."""
        try:
            self.stop()
            
            # Clear data
            with self._lock:
                self.data_buffers.clear()
                self.current_data.clear()
                self.subscribers.clear()
                self.group_subscribers.clear()
            
            self.logger.info("Data feed manager shut down")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def cleanup(self):
        """Clean up resources."""
        self.shutdown()


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Global instance
_data_feed_instance: Optional[DataFeedManager] = None

def get_data_feed_manager(ib_client: Optional[SpyderClient] = None,
                         event_manager: Optional[EventManager] = None,
                         config: Optional[Dict] = None) -> DataFeedManager:
    """
    Get singleton data feed manager instance.
    
    Args:
        ib_client: IB client instance
        event_manager: Event manager instance
        config: Optional configuration
        
    Returns:
        DataFeedManager instance
    """
    global _data_feed_instance
    if _data_feed_instance is None:
        _data_feed_instance = DataFeedManager(ib_client, event_manager, config)
    return _data_feed_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the enhanced data feed
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient, IBConfig
    
    # Initialize components
    event_manager = EventManager()
    ib_config = IBConfig(host='127.0.0.1', port=7497, client_id=2)
    ib_client = SpyderClient(ib_config, event_manager)
    
    # Connect to IBKR
    if ib_client.connect():
        # Create data feed manager
        feed_config = {
            'hub_enabled': True,
            'cache_enabled': True,
            'validation_enabled': True
        }
        
        feed_manager = DataFeedManager(ib_client, event_manager, feed_config)
        
        # Define test callback
        def on_update(tick: MarketTick):
            print(f"📊 {tick.symbol}: ${tick.price:.2f} "
                  f"[{tick.bid:.2f} x {tick.ask:.2f}] "
                  f"Vol: {tick.volume}")
        
        # Start feed
        if feed_manager.start():
            print("✅ Data feed started")
            
            # Subscribe to symbols
            feed_manager.subscribe('SPY', on_update, 'CRITICAL')
            feed_manager.subscribe('VIX', on_update, 'CRITICAL')
            feed_manager.subscribe('QQQ', on_update, 'HIGH')
            
            # Test group subscription
            def on_group_update(group_data: Dict[str, MarketTick]):
                print(f"\n📈 CORE Group Update:")
                for symbol, tick in group_data.items():
                    print(f"  {symbol}: ${tick.price:.2f}")
            
            feed_manager.subscribe_group('CORE', on_group_update)
            
            # Run for a bit
            time.sleep(30)
            
            # Get status
            status = feed_manager.get_status()
            print(f"\n📊 Feed Status:\n{json.dumps(status, indent=2)}")
            
            # Get historical data
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)
            hist_data = feed_manager.get_historical_data('SPY', start_time, end_time)
            
            if not hist_data.empty:
                print(f"\n📈 Historical SPY data:\n{hist_data.tail()}")
            
            # Stop feed
            feed_manager.stop()
            print("✅ Data feed stopped")
            
        ib_client.disconnect()
    else:
        print("❌ Failed to connect to IBKR")