#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_DashboardDataBridge.py
Purpose: Fixed dashboard data bridge connecting MarketDataManager to TradingDashboard
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-19 Time: 15:20:00  

Module Description:
    Streamlined data bridge that connects the fixed MarketDataManager (with working
    FROZEN/DELAYED data) to the TradingDashboard. Solves the cached data issue by
    providing real-time data flow, proper percentage calculations, and thread-safe
    updates. Focuses on the essential data connection without over-engineering.

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import threading
import time
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum, auto
import queue
import weakref

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from PySide6.QtCore import QObject, QThread, QTimer, Signal, QMutex, QMutexLocker
    from PySide6.QtWidgets import QApplication
    PYSIDE6_AVAILABLE = True
except ImportError:
    print("⚠️ PyQt6 not available - running in headless mode")
    PYSIDE6_AVAILABLE = False
    # Mock classes for headless mode
    class QObject:
        pass
    class Signal:
        def __init__(self, *args):
            pass
        def emit(self, *args):
            pass
        def connect(self, *args):
            pass

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# Import our fixed MarketDataManager
try:
    from SpyderB_Broker.SpyderB07_MarketDataManager import (
        MarketDataManager, 
        MarketDataSnapshot,
        ETTimeDisplay,
        get_market_data_manager
    )
    MARKET_DATA_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ MarketDataManager not available: {e}")
    MARKET_DATA_MANAGER_AVAILABLE = False

try:
    from SpyderB_Broker.SpyderB01_SpyderClient import SpyderClient
    CLIENT_AVAILABLE = True
except ImportError:
    print("⚠️ SpyderClient not available")
    CLIENT_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update intervals (milliseconds)
UPDATE_INTERVAL_CRITICAL = 250   # SPY, VIX - most important
UPDATE_INTERVAL_HIGH = 1000      # QQQ, IWM - major indices  
UPDATE_INTERVAL_NORMAL = 2000    # Other symbols
UPDATE_INTERVAL_LOW = 5000       # Background symbols

# Data validation thresholds
MAX_PRICE_CHANGE_PERCENT = 10.0  # Maximum reasonable price change per update
MIN_VALID_PRICE = 0.01           # Minimum valid price
MAX_STALE_DATA_SECONDS = 30      # Maximum age for data to be considered fresh

# Symbols by priority
CRITICAL_SYMBOLS = {'SPY', 'VIX'}
HIGH_PRIORITY_SYMBOLS = {'QQQ', 'IWM', '/ES', '/NQ'}
NORMAL_SYMBOLS = {'UVXY', 'VXX', 'SQQQ', 'TQQQ'}

# JSON export path for dashboard compatibility
DASHBOARD_DATA_PATH = '/tmp/spyder_market_data.json'

# ==============================================================================
# ENUMS AND DATA CLASSES
# ==============================================================================
class UpdatePriority(Enum):
    """Update priority levels for different symbols"""
    CRITICAL = auto()   # 250ms updates
    HIGH = auto()       # 1s updates
    NORMAL = auto()     # 2s updates
    LOW = auto()        # 5s updates

class BridgeStatus(Enum):
    """Bridge connection status"""
    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    ERROR = auto()

@dataclass
class DashboardData:
    """Formatted data structure for dashboard consumption"""
    symbol: str
    price: float
    change: float
    change_percent: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'symbol': self.symbol,
            'price': round(self.price, 2),
            'change': round(self.change, 2),
            'change_pct': round(self.change_percent, 2),
            'bid': round(self.bid, 2),
            'ask': round(self.ask, 2),
            'volume': self.volume,
            'timestamp': self.timestamp.isoformat(),
            'formatted_price': f"${self.price:.2f}",
            'formatted_change': f"{self.change:+.2f}",
            'formatted_change_pct': f"{self.change_percent:+.2f}%"
        }

@dataclass 
class BridgeMetrics:
    """Performance metrics for the bridge"""
    total_updates: int = 0
    successful_updates: int = 0
    failed_updates: int = 0
    widgets_registered: int = 0
    last_update_time: Optional[datetime] = None
    updates_per_second: float = 0.0
    
    def update_rate(self) -> float:
        """Calculate success rate"""
        if self.total_updates == 0:
            return 0.0
        return (self.successful_updates / self.total_updates) * 100

# ==============================================================================
# DASHBOARD DATA BRIDGE CLASS
# ==============================================================================
class DashboardDataBridge(QObject if PYSIDE6_AVAILABLE else object):
    """
    Fixed Dashboard Data Bridge
    
    🔧 FIXES APPLIED:
    - Connects working MarketDataManager (FROZEN/DELAYED data) to TradingDashboard
    - Replaces cached dashboard data with live feeds
    - Proper percentage change calculations
    - Thread-safe updates via PyQt signals
    - JSON export for dashboard compatibility
    - Error handling and graceful fallbacks
    """
    
    # PyQt6 Signals for thread-safe communication
    if PYSIDE6_AVAILABLE:
        data_updated = Signal(str, dict)      # symbol, dashboard_data_dict
        status_changed = Signal(str)          # status string
        error_occurred = Signal(str)          # error message
        
    def __init__(self):
        """Initialize the Dashboard Data Bridge"""
        if PYSIDE6_AVAILABLE:
            super().__init__()
            
        # Core components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Market data components
        self.market_data_manager: Optional[MarketDataManager] = None
        self.spyder_client: Optional[SpyderClient] = None
        
        # Status and control
        self.status = BridgeStatus.DISCONNECTED
        self.is_running = False
        self._stop_event = threading.Event()
        
        # Thread safety
        self._mutex = QMutex() if PYSIDE6_AVAILABLE else threading.RLock()
        
        # Data management
        self.current_data: Dict[str, DashboardData] = {}
        self.previous_data: Dict[str, DashboardData] = {}
        self.data_queue = queue.Queue(maxsize=1000)
        
        # Update timers and threads
        self.update_timers: Dict[UpdatePriority, QTimer] = {}
        self.data_export_timer: Optional[QTimer] = None
        
        # Widget registry for dashboard widgets
        self.registered_widgets: Dict[str, Any] = {}
        self.widget_callbacks: Dict[str, List[Callable]] = {}
        
        # Performance metrics
        self.metrics = BridgeMetrics()
        
        self.logger.info("DashboardDataBridge initialized")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def initialize(self, spyder_client: Optional[SpyderClient] = None) -> bool:
        """
        Initialize the bridge with market data manager.
        
        Args:
            spyder_client: Optional SpyderClient instance
            
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("🚀 Initializing DashboardDataBridge...")
            
            if not MARKET_DATA_MANAGER_AVAILABLE:
                self.logger.error("❌ MarketDataManager not available")
                return False
            
            # Get or create market data manager
            if spyder_client:
                self.spyder_client = spyder_client
                self.market_data_manager = get_market_data_manager(spyder_client)
            else:
                # Try to get existing instance
                try:
                    self.market_data_manager = get_market_data_manager()
                except ValueError:
                    self.logger.error("❌ No SpyderClient provided and none exists")
                    return False
            
            # Setup update timers
            if PYSIDE6_AVAILABLE:
                self._setup_update_timers()
                self._setup_data_export_timer()
            
            self.status = BridgeStatus.DISCONNECTED
            self.logger.info("✅ DashboardDataBridge initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize bridge: {e}")
            self.error_handler.handle_error(e)
            return False
    
    def start(self) -> bool:
        """
        Start the data bridge.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("Bridge already running")
                return True
                
            self.logger.info("🔥 Starting DashboardDataBridge...")
            self.status = BridgeStatus.CONNECTING
            
            # Start market data manager if not already running
            if self.market_data_manager and not self.market_data_manager.is_running:
                if not self.market_data_manager.start():
                    self.logger.error("❌ Failed to start MarketDataManager")
                    return False
            
            # Subscribe to market data updates
            self._subscribe_to_market_data()
            
            # Start update timers
            if PYSIDE6_AVAILABLE:
                for timer in self.update_timers.values():
                    timer.start()
                    
                if self.data_export_timer:
                    self.data_export_timer.start()
            
            self.is_running = True
            self.status = BridgeStatus.CONNECTED
            
            if PYSIDE6_AVAILABLE:
                self.status_changed.emit("Connected")
            
            self.logger.info("✅ DashboardDataBridge started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start bridge: {e}")
            self.error_handler.handle_error(e)
            self.status = BridgeStatus.ERROR
            return False
    
    def stop(self) -> bool:
        """
        Stop the data bridge.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.is_running:
                self.logger.info("Bridge already stopped")
                return True
                
            self.logger.info("🛑 Stopping DashboardDataBridge...")
            
            # Stop timers
            if PYSIDE6_AVAILABLE:
                for timer in self.update_timers.values():
                    timer.stop()
                    
                if self.data_export_timer:
                    self.data_export_timer.stop()
            
            # Signal stop
            self._stop_event.set()
            self.is_running = False
            self.status = BridgeStatus.DISCONNECTED
            
            if PYSIDE6_AVAILABLE:
                self.status_changed.emit("Disconnected")
            
            self.logger.info("✅ DashboardDataBridge stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping bridge: {e}")
            return False
    
    # ==========================================================================
    # 🔧 CORE DATA BRIDGE METHODS (New Implementation)
    # ==========================================================================
    def _subscribe_to_market_data(self) -> None:
        """Subscribe to market data updates from MarketDataManager."""
        try:
            if not self.market_data_manager:
                return
                
            # Subscribe to all trading symbols with callbacks
            all_symbols = list(CRITICAL_SYMBOLS) + list(HIGH_PRIORITY_SYMBOLS) + list(NORMAL_SYMBOLS)
            
            for symbol in all_symbols:
                self.market_data_manager.subscribe_callback(symbol, self._on_market_data_update)
                
            self.logger.info(f"✅ Subscribed to {len(all_symbols)} symbols")
            
        except Exception as e:
            self.logger.error(f"❌ Error subscribing to market data: {e}")
    
    def _on_market_data_update(self, snapshot: MarketDataSnapshot) -> None:
        """
        Handle market data update from MarketDataManager.
        
        Args:
            snapshot: Market data snapshot
        """
        try:
            # Convert snapshot to dashboard format
            dashboard_data = self._convert_snapshot_to_dashboard_data(snapshot)
            
            # Update internal cache
            with (QMutexLocker(self._mutex) if PYSIDE6_AVAILABLE else self._mutex):
                self.previous_data[snapshot.symbol] = self.current_data.get(snapshot.symbol)
                self.current_data[snapshot.symbol] = dashboard_data
                
                # Update metrics
                self.metrics.total_updates += 1
                self.metrics.successful_updates += 1
                self.metrics.last_update_time = datetime.now()
            
            # Emit signal for PyQt widgets
            if PYSIDE6_AVAILABLE:
                self.data_updated.emit(snapshot.symbol, dashboard_data.to_dict())
            
            # Notify registered callbacks
            self._notify_widgets(snapshot.symbol, dashboard_data)
            
        except Exception as e:
            self.logger.error(f"❌ Error handling market data update for {snapshot.symbol}: {e}")
            self.metrics.failed_updates += 1
    
    def _convert_snapshot_to_dashboard_data(self, snapshot: MarketDataSnapshot) -> DashboardData:
        """
        Convert MarketDataSnapshot to DashboardData format.
        
        Args:
            snapshot: Market data snapshot
            
        Returns:
            DashboardData: Formatted data for dashboard
        """
        try:
            # Calculate change from previous data or use snapshot's calculation
            change = 0.0
            change_percent = snapshot.change_percent  # Use the fixed calculation from MarketDataManager
            
            # If MarketDataManager didn't calculate it, try ourselves
            if change_percent == 0.0 and snapshot.symbol in self.previous_data:
                prev_data = self.previous_data[snapshot.symbol]
                if prev_data and prev_data.price > 0:
                    change = snapshot.last - prev_data.price
                    change_percent = (change / prev_data.price) * 100
                    
            # Validate data
            price = max(snapshot.last, MIN_VALID_PRICE) if snapshot.last > 0 else snapshot.mid_price
            if price <= MIN_VALID_PRICE:
                price = snapshot.bid if snapshot.bid > 0 else snapshot.ask
                
            return DashboardData(
                symbol=snapshot.symbol,
                price=price,
                change=change,
                change_percent=change_percent,
                bid=snapshot.bid,
                ask=snapshot.ask,
                volume=snapshot.volume,
                timestamp=snapshot.timestamp
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error converting snapshot for {snapshot.symbol}: {e}")
            # Return minimal valid data
            return DashboardData(
                symbol=snapshot.symbol,
                price=snapshot.last or 0.0,
                change=0.0,
                change_percent=0.0,
                bid=snapshot.bid,
                ask=snapshot.ask,
                volume=snapshot.volume,
                timestamp=snapshot.timestamp
            )
    
    # ==========================================================================
    # TIMER SETUP METHODS
    # ==========================================================================
    def _setup_update_timers(self) -> None:
        """Setup update timers for different priority levels."""
        if not PYSIDE6_AVAILABLE:
            return
            
        timer_configs = {
            UpdatePriority.CRITICAL: UPDATE_INTERVAL_CRITICAL,
            UpdatePriority.HIGH: UPDATE_INTERVAL_HIGH,
            UpdatePriority.NORMAL: UPDATE_INTERVAL_NORMAL,
            UpdatePriority.LOW: UPDATE_INTERVAL_LOW
        }
        
        for priority, interval in timer_configs.items():
            timer = QTimer()
            timer.timeout.connect(lambda p=priority: self._priority_update(p))
            timer.setInterval(interval)
            self.update_timers[priority] = timer
            
        self.logger.info("✅ Update timers configured")
    
    def _setup_data_export_timer(self) -> None:
        """Setup timer for exporting data to JSON for dashboard compatibility."""
        if not PYSIDE6_AVAILABLE:
            return
            
        self.data_export_timer = QTimer()
        self.data_export_timer.timeout.connect(self._export_data_to_json)
        self.data_export_timer.setInterval(1000)  # Export every second
    
    def _priority_update(self, priority: UpdatePriority) -> None:
        """
        Handle priority-based updates.
        
        Args:
            priority: Update priority level
        """
        try:
            symbols_to_update = []
            
            if priority == UpdatePriority.CRITICAL:
                symbols_to_update = list(CRITICAL_SYMBOLS)
            elif priority == UpdatePriority.HIGH:
                symbols_to_update = list(HIGH_PRIORITY_SYMBOLS)
            elif priority == UpdatePriority.NORMAL:
                symbols_to_update = list(NORMAL_SYMBOLS)
                
            # Process updates for symbols in this priority
            for symbol in symbols_to_update:
                if symbol in self.current_data:
                    self._refresh_symbol_data(symbol)
                    
        except Exception as e:
            self.logger.error(f"❌ Error in priority update {priority}: {e}")
    
    def _refresh_symbol_data(self, symbol: str) -> None:
        """
        Refresh data for a specific symbol.
        
        Args:
            symbol: Symbol to refresh
        """
        try:
            if not self.market_data_manager:
                return
                
            # Get latest data from MarketDataManager
            snapshot = self.market_data_manager.get_market_data(symbol)
            if snapshot:
                self._on_market_data_update(snapshot)
                
        except Exception as e:
            self.logger.error(f"❌ Error refreshing data for {symbol}: {e}")
    
    # ==========================================================================
    # 🔧 JSON EXPORT FOR DASHBOARD COMPATIBILITY
    # ==========================================================================
    def _export_data_to_json(self) -> None:
        """Export current data to JSON file for dashboard compatibility."""
        try:
            with (QMutexLocker(self._mutex) if PYSIDE6_AVAILABLE else self._mutex):
                export_data = {}
                
                for symbol, data in self.current_data.items():
                    export_data[symbol] = {
                        'last': data.price,
                        'bid': data.bid,
                        'ask': data.ask,
                        'volume': data.volume,
                        'change': data.change,
                        'change_pct': data.change_percent,
                        'timestamp': data.timestamp.isoformat()
                    }
                
                # Write to JSON file
                with open(DASHBOARD_DATA_PATH, 'w') as f:
                    json.dump(export_data, f, indent=2)
                    
        except Exception as e:
            self.logger.error(f"❌ Error exporting data to JSON: {e}")
    
    # ==========================================================================
    # WIDGET REGISTRATION AND NOTIFICATION
    # ==========================================================================
    def register_widget(self, widget: Any, symbol: str, callback: Callable) -> str:
        """
        Register a dashboard widget for updates.
        
        Args:
            widget: Dashboard widget
            symbol: Symbol to monitor
            callback: Callback function
            
        Returns:
            str: Registration ID
        """
        try:
            widget_id = f"{symbol}_{id(widget)}"
            
            with (QMutexLocker(self._mutex) if PYSIDE6_AVAILABLE else self._mutex):
                self.registered_widgets[widget_id] = weakref.ref(widget)
                
                if symbol not in self.widget_callbacks:
                    self.widget_callbacks[symbol] = []
                self.widget_callbacks[symbol].append(callback)
                
                self.metrics.widgets_registered += 1
            
            self.logger.info(f"✅ Registered widget {widget_id} for {symbol}")
            return widget_id
            
        except Exception as e:
            self.logger.error(f"❌ Error registering widget: {e}")
            return ""
    
    def _notify_widgets(self, symbol: str, data: DashboardData) -> None:
        """
        Notify registered widgets of data updates.
        
        Args:
            symbol: Symbol that was updated
            data: Updated data
        """
        try:
            callbacks = self.widget_callbacks.get(symbol, [])
            
            for callback in callbacks:
                try:
                    callback(data.to_dict())
                except Exception as e:
                    self.logger.error(f"❌ Error in widget callback for {symbol}: {e}")
                    
        except Exception as e:
            self.logger.error(f"❌ Error notifying widgets for {symbol}: {e}")
    
    # ==========================================================================
    # STATUS AND MONITORING
    # ==========================================================================
    def get_status(self) -> Dict[str, Any]:
        """
        Get bridge status and metrics.
        
        Returns:
            Dict containing status information
        """
        try:
            with (QMutexLocker(self._mutex) if PYSIDE6_AVAILABLE else self._mutex):
                return {
                    'status': self.status.name,
                    'is_running': self.is_running,
                    'symbols_tracked': len(self.current_data),
                    'widgets_registered': self.metrics.widgets_registered,
                    'total_updates': self.metrics.total_updates,
                    'success_rate': self.metrics.update_rate(),
                    'last_update': self.metrics.last_update_time.isoformat() if self.metrics.last_update_time else None,
                    'market_data_manager_available': MARKET_DATA_MANAGER_AVAILABLE,
                    'market_data_manager_running': self.market_data_manager.is_running if self.market_data_manager else False
                }
        except Exception as e:
            self.logger.error(f"❌ Error getting status: {e}")
            return {'error': str(e)}
    
    def get_current_data(self, symbol: str = None) -> Dict[str, Any]:
        """
        Get current market data.
        
        Args:
            symbol: Specific symbol (optional)
            
        Returns:
            Dict containing current data
        """
        try:
            with (QMutexLocker(self._mutex) if PYSIDE6_AVAILABLE else self._mutex):
                if symbol:
                    data = self.current_data.get(symbol)
                    return data.to_dict() if data else {}
                else:
                    return {sym: data.to_dict() for sym, data in self.current_data.items()}
        except Exception as e:
            self.logger.error(f"❌ Error getting current data: {e}")
            return {}

# ==============================================================================
# GLOBAL BRIDGE INSTANCE
# ==============================================================================
_bridge_instance: Optional[DashboardDataBridge] = None
_bridge_lock = threading.Lock()

def get_dashboard_bridge(spyder_client: Optional[SpyderClient] = None) -> DashboardDataBridge:
    """
    Get or create the dashboard bridge instance.
    
    Args:
        spyder_client: Optional SpyderClient instance
        
    Returns:
        DashboardDataBridge instance
    """
    global _bridge_instance
    
    with _bridge_lock:
        if _bridge_instance is None:
            _bridge_instance = DashboardDataBridge()
            if not _bridge_instance.initialize(spyder_client):
                raise RuntimeError("Failed to initialize DashboardDataBridge")
        return _bridge_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the dashboard data bridge
    import logging
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    print("🚀 Testing DashboardDataBridge")
    print("=" * 50)
    
    try:
        # Create bridge
        bridge = DashboardDataBridge()
        
        if bridge.initialize():
            print("✅ Bridge initialized")
            
            if bridge.start():
                print("✅ Bridge started")
                
                # Let it run for a bit
                time.sleep(5)
                
                # Check status
                status = bridge.get_status()
                print(f"📊 Bridge Status: {status}")
                
                # Check data
                data = bridge.get_current_data()
                print(f"📈 Current Data: {len(data)} symbols")
                
                # Stop bridge
                bridge.stop()
                print("✅ Bridge stopped")
            else:
                print("❌ Failed to start bridge")
        else:
            print("❌ Failed to initialize bridge")
            
    except Exception as e:
        print(f"❌ Error testing bridge: {e}")
        import traceback
        traceback.print_exc()