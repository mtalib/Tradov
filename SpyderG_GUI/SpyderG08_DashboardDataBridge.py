#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderG08_DashboardDataBridge.py
Group: G (GUI Components)
Purpose: Thread-Safe PyQt6 Integration Bridge for Multi-Client Market Data

Description:
    Professional PyQt6 integration layer that bridges the multi-client market data
    manager with dashboard widgets. Provides thread-safe signal/slot architecture
    for real-time market data updates with priority-based update frequencies.

Author: SPYDER Development Team
Date: 2025-07-28
Version: 1.0.0
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import queue
from concurrent.futures import ThreadPoolExecutor

# ================================================================================
# QT IMPORTS - Handle graceful fallbacks
# ================================================================================

try:
    from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QMutex, QMutexLocker
    from PyQt6.QtWidgets import QWidget
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    # Fallback classes for when PyQt6 is not available
    class QObject:
        def __init__(self):
            pass
    
    def pyqtSignal(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class QTimer:
        def __init__(self):
            pass
        def start(self, interval): pass
        def stop(self): pass
    
    class QMutex:
        def __init__(self): pass
        def lock(self): pass
        def unlock(self): pass
    
    class QMutexLocker:
        def __init__(self, mutex): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    
    class QWidget:
        def __init__(self): pass

# ================================================================================
# IBAPI IMPORTS - Handle graceful fallbacks
# ================================================================================

try:
    from ibapi.contract import Contract
    from ibapi.order import Order
    from ibapi.ticktype import TickType  # FIXED: Correct import location
    from ibapi.common import BarData
    IBAPI_AVAILABLE = True
except ImportError:
    IBAPI_AVAILABLE = False
    # Fallback classes for when IBAPI is not available
    class Contract:
        def __init__(self):
            self.symbol = ""
            self.secType = ""
            self.exchange = ""
            self.currency = "USD"
    
    class Order:
        def __init__(self):
            self.action = ""
            self.totalQuantity = 0
            self.orderType = ""
    
    class TickType:
        LAST = 4
        BID = 1
        ASK = 2
        VOLUME = 8
        HIGH = 6
        LOW = 7
        CLOSE = 9
    
    class BarData:
        def __init__(self):
            self.date = ""
            self.open = 0.0
            self.high = 0.0
            self.low = 0.0
            self.close = 0.0
            self.volume = 0

# ================================================================================
# MULTI-CLIENT MANAGER IMPORT
# ================================================================================

try:
    from SpyderB_Broker.SpyderB08_MultiClientDataManager import (
        MultiClientDataManager,
        MarketDataTick,
        ClientInfo,
        ClientPurpose
    )
    MULTI_CLIENT_AVAILABLE = True
except ImportError:
    MULTI_CLIENT_AVAILABLE = False
    # Fallback classes
    class MultiClientDataManager:
        def __init__(self): pass
        def start(self): return False
        def stop(self): return False
        def subscribe_to_data(self, symbol, callback): return False
        def get_latest_data(self, symbol): return None
    
    class MarketDataTick:
        def __init__(self, symbol="", price=0.0, size=0, timestamp=None, tick_type=0, request_id=0):
            self.symbol = symbol
            self.price = price
            self.size = size
            self.timestamp = timestamp or datetime.now()
            self.tick_type = tick_type
            self.request_id = request_id

# ================================================================================
# ENUMS AND DATACLASSES
# ================================================================================

class UpdatePriority(Enum):
    """Update priority levels for different symbols"""
    CRITICAL = "critical"    # 250ms - SPY, VIX
    HIGH = "high"           # 1s - Major indices
    NORMAL = "normal"       # 2-5s - Normal symbols
    LOW = "low"             # 5-15s - Sector ETFs

class BridgeStatus(Enum):
    """Bridge connection status"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class WidgetRegistration:
    """Widget registration information"""
    widget_id: str
    widget: Any
    symbol: str
    update_method: str
    priority: UpdatePriority
    last_update: Optional[datetime] = None
    update_count: int = 0
    error_count: int = 0

# ================================================================================
# MAIN DASHBOARD DATA BRIDGE CLASS
# ================================================================================

class DashboardDataBridge(QObject if PYQT6_AVAILABLE else object):
    """
    Thread-Safe PyQt6 Integration Bridge
    
    Bridges multi-client market data manager with PyQt6 dashboard widgets
    using proper signal/slot architecture for thread-safe updates.
    """
    
    # PyQt6 Signals for thread-safe communication
    if PYQT6_AVAILABLE:
        market_data_updated = pyqtSignal(str, dict)  # symbol, data_dict
        connection_status_changed = pyqtSignal(str)  # status
        error_occurred = pyqtSignal(str)  # error_message
    
    def __init__(self):
        """Initialize the Dashboard Data Bridge"""
        if PYQT6_AVAILABLE:
            super().__init__()
        
        # Core components
        self.logger = logging.getLogger('SpyderG08.DataBridge')
        self.multi_client_manager: Optional[MultiClientDataManager] = None
        self.status = BridgeStatus.DISCONNECTED
        
        # Threading and synchronization
        self._mutex = QMutex() if PYQT6_AVAILABLE else threading.RLock()
        self.is_running = False
        self._stop_event = threading.Event()
        
        # Widget management
        self.registered_widgets: Dict[str, WidgetRegistration] = {}
        self.widget_counter = 0
        
        # Update timers for different priorities
        self.update_timers: Dict[UpdatePriority, QTimer] = {}
        
        # Data cache with thread-safe access
        self.data_cache: Dict[str, dict] = {}
        
        # Performance metrics
        self.metrics = {
            'total_updates': 0,
            'failed_updates': 0,
            'widgets_registered': 0,
            'last_update_time': None
        }
        
        if PYQT6_AVAILABLE:
            # Connect internal signals
            self.market_data_updated.connect(self._handle_market_data_update)
        
        self.logger.info("✅ Dashboard Data Bridge initialized")

    # ================================================================================
    # CORE MANAGEMENT METHODS
    # ================================================================================

    def initialize(self) -> bool:
        """
        Initialize the bridge with multi-client manager
        
        Returns:
            bool: True if initialization successful
        """
        try:
            if not MULTI_CLIENT_AVAILABLE:
                self.logger.warning("Multi-Client Manager not available, using fallback mode")
                return True
            
            # Create multi-client manager instance
            self.multi_client_manager = MultiClientDataManager()
            
            if PYQT6_AVAILABLE:
                # Initialize update timers
                self._initialize_update_timers()
            
            self.status = BridgeStatus.DISCONNECTED
            self.logger.info("✅ Bridge initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error initializing bridge: {e}")
            self.status = BridgeStatus.ERROR
            return False

    def start(self) -> bool:
        """
        Start the bridge and underlying connections
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("Bridge already running")
                return True
            
            self.logger.info("🚀 Starting Dashboard Data Bridge...")
            self.status = BridgeStatus.CONNECTING
            
            # Start multi-client manager
            if self.multi_client_manager:
                if self.multi_client_manager.start():
                    self.logger.info("✅ Multi-client manager started")
                else:
                    self.logger.warning("⚠️ Multi-client manager failed to start")
            
            # Start update timers
            if PYQT6_AVAILABLE:
                for timer in self.update_timers.values():
                    timer.start()
            
            self.is_running = True
            self.status = BridgeStatus.CONNECTED
            
            if PYQT6_AVAILABLE:
                self.connection_status_changed.emit(self.status.value)
            
            self.logger.info("✅ Dashboard Data Bridge started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error starting bridge: {e}")
            self.status = BridgeStatus.ERROR
            if PYQT6_AVAILABLE:
                self.error_occurred.emit(str(e))
            return False

    def stop(self) -> bool:
        """
        Stop the bridge and cleanup resources
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.is_running:
                self.logger.info("Bridge already stopped")
                return True
            
            self.logger.info("🛑 Stopping Dashboard Data Bridge...")
            
            # Stop update timers
            if PYQT6_AVAILABLE:
                for timer in self.update_timers.values():
                    timer.stop()
            
            # Stop multi-client manager
            if self.multi_client_manager:
                self.multi_client_manager.stop()
            
            self.is_running = False
            self.status = BridgeStatus.DISCONNECTED
            
            if PYQT6_AVAILABLE:
                self.connection_status_changed.emit(self.status.value)
            
            self.logger.info("✅ Dashboard Data Bridge stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error stopping bridge: {e}")
            return False

    def _initialize_update_timers(self):
        """Initialize update timers for different priority levels"""
        try:
            timer_intervals = {
                UpdatePriority.CRITICAL: 250,   # 250ms for SPY, VIX
                UpdatePriority.HIGH: 1000,      # 1s for major indices
                UpdatePriority.NORMAL: 2000,    # 2s for normal symbols
                UpdatePriority.LOW: 5000        # 5s for sector ETFs
            }
            
            for priority, interval in timer_intervals.items():
                timer = QTimer()
                timer.timeout.connect(lambda p=priority: self._update_widgets_by_priority(p))
                timer.start(interval)
                self.update_timers[priority] = timer
                
            self.logger.info("✅ Update timers initialized")
            
        except Exception as e:
            self.logger.error(f"❌ Error initializing update timers: {e}")

    # ================================================================================
    # WIDGET REGISTRATION METHODS
    # ================================================================================

    def register_widget(self, widget: Any, symbol: str, update_method: str, 
                       priority: UpdatePriority = UpdatePriority.NORMAL) -> str:
        """
        Register a widget for market data updates
        
        Args:
            widget: Widget object to update
            symbol: Symbol to monitor
            update_method: Method name to call on widget
            priority: Update priority level
            
        Returns:
            Widget ID for tracking
        """
        try:
            with QMutexLocker(self._mutex) if PYQT6_AVAILABLE else self._mutex:
                # Generate unique widget ID
                self.widget_counter += 1
                widget_id = f"{symbol}_{self.widget_counter}_{id(widget)}"
                
                # Create registration
                registration = WidgetRegistration(
                    widget_id=widget_id,
                    widget=widget,
                    symbol=symbol,
                    update_method=update_method,
                    priority=priority
                )
                
                # Store registration
                self.registered_widgets[widget_id] = registration
                self.metrics['widgets_registered'] += 1
                
                # Subscribe to data if multi-client manager available
                if self.multi_client_manager:
                    self.multi_client_manager.subscribe_to_data(
                        symbol, 
                        lambda tick: self._on_market_data_received(symbol, tick)
                    )
                
                self.logger.info(f"✅ Registered widget for {symbol} with {priority.value} priority")
                return widget_id
                
        except Exception as e:
            self.logger.error(f"❌ Error registering widget for {symbol}: {e}")
            return ""

    def unregister_widget(self, widget_id: str) -> bool:
        """
        Unregister a widget from updates
        
        Args:
            widget_id: Widget ID to unregister
            
        Returns:
            bool: True if unregistered successfully
        """
        try:
            with QMutexLocker(self._mutex) if PYQT6_AVAILABLE else self._mutex:
                if widget_id in self.registered_widgets:
                    registration = self.registered_widgets.pop(widget_id)
                    self.logger.info(f"✅ Unregistered widget for {registration.symbol}")
                    return True
                    
        except Exception as e:
            self.logger.error(f"❌ Error unregistering widget {widget_id}: {e}")
            return False

    # ================================================================================
    # DATA UPDATE METHODS
    # ================================================================================

    def _on_market_data_received(self, symbol: str, tick: MarketDataTick):
        """
        Handle market data received from multi-client manager
        
        Args:
            symbol: Symbol that was updated
            tick: Market data tick
        """
        try:
            # Format data for display
            data_dict = self._format_data_for_display(tick)
            
            # Cache the data
            with QMutexLocker(self._mutex) if PYQT6_AVAILABLE else self._mutex:
                self.data_cache[symbol] = data_dict
            
            # Emit signal for thread-safe update
            if PYQT6_AVAILABLE:
                self.market_data_updated.emit(symbol, data_dict)
            else:
                # Direct update in non-PyQt6 mode
                self._handle_market_data_update(symbol, data_dict)
            
        except Exception as e:
            self.logger.error(f"❌ Error handling market data for {symbol}: {e}")

    def _format_data_for_display(self, tick: MarketDataTick) -> dict:
        """
        Format market data tick for display
        
        Args:
            tick: Market data tick
            
        Returns:
            Formatted data dictionary
        """
        try:
            # Calculate change (simplified - would need previous price)
            price_change = 0.0  # Would calculate from previous price
            price_change_percent = 0.0
            
            # Determine color based on change
            if price_change > 0:
                color = "green"
            elif price_change < 0:
                color = "red"
            else:
                color = "white"
            
            # Format volume
            volume_str = self._format_volume(tick.size)
            
            return {
                'symbol': tick.symbol,
                'price': tick.price,
                'formatted_price': f"${tick.price:.2f}",
                'change': price_change,
                'formatted_change': f"{price_change:+.2f}",
                'change_percent': price_change_percent,
                'formatted_change_percent': f"({price_change_percent:+.2f}%)",
                'volume': tick.size,
                'formatted_volume': volume_str,
                'color': color,
                'timestamp': tick.timestamp,
                'formatted_time': tick.timestamp.strftime("%H:%M:%S")
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error formatting data: {e}")
            return {
                'symbol': tick.symbol,
                'price': tick.price,
                'formatted_price': f"${tick.price:.2f}",
                'color': 'white'
            }

    def _format_volume(self, volume: int) -> str:
        """
        Format volume for display
        
        Args:
            volume: Raw volume
            
        Returns:
            Formatted volume string
        """
        if volume >= 1_000_000:
            return f"{volume / 1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"{volume / 1_000:.0f}K"
        else:
            return str(volume)

    def _handle_market_data_update(self, symbol: str, data_dict: dict):
        """
        Handle market data update (called by signal)
        
        Args:
            symbol: Symbol that was updated
            data_dict: Formatted data dictionary
        """
        try:
            # Update all widgets registered for this symbol
            widgets_updated = 0
            
            for widget_id, registration in self.registered_widgets.items():
                if registration.symbol == symbol:
                    try:
                        # Get update method from widget
                        update_method = getattr(registration.widget, registration.update_method, None)
                        
                        if update_method and callable(update_method):
                            # Call update method
                            update_method(data_dict)
                            
                            # Update registration stats
                            registration.last_update = datetime.now()
                            registration.update_count += 1
                            widgets_updated += 1
                        
                    except Exception as e:
                        registration.error_count += 1
                        self.logger.error(f"❌ Error updating widget {widget_id}: {e}")
            
            # Update metrics
            self.metrics['total_updates'] += widgets_updated
            self.metrics['last_update_time'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"❌ Error in market data update handler: {e}")
            self.metrics['failed_updates'] += 1

    def _update_widgets_by_priority(self, priority: UpdatePriority):
        """
        Update widgets with specific priority level
        
        Args:
            priority: Priority level to update
        """
        try:
            for widget_id, registration in self.registered_widgets.items():
                if registration.priority == priority:
                    symbol = registration.symbol
                    
                    # Get cached data
                    if symbol in self.data_cache:
                        data_dict = self.data_cache[symbol]
                        
                        # Update widget
                        try:
                            update_method = getattr(registration.widget, registration.update_method, None)
                            if update_method and callable(update_method):
                                update_method(data_dict)
                                registration.update_count += 1
                        
                        except Exception as e:
                            registration.error_count += 1
                            self.logger.error(f"❌ Priority update error for {widget_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"❌ Error in priority update: {e}")

    # ================================================================================
    # STATUS AND MONITORING METHODS
    # ================================================================================

    def get_status(self) -> dict:
        """
        Get comprehensive bridge status
        
        Returns:
            Status dictionary
        """
        try:
            with QMutexLocker(self._mutex) if PYQT6_AVAILABLE else self._mutex:
                return {
                    'is_running': self.is_running,
                    'status': self.status.value,
                    'widgets_registered': len(self.registered_widgets),
                    'symbols_monitored': len(set(r.symbol for r in self.registered_widgets.values())),
                    'data_cache_size': len(self.data_cache),
                    'metrics': self.metrics.copy(),
                    'multi_client_available': MULTI_CLIENT_AVAILABLE,
                    'pyqt6_available': PYQT6_AVAILABLE
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error getting status: {e}")
            return {'error': str(e)}

    def get_widget_performance(self) -> dict:
        """
        Get widget performance statistics
        
        Returns:
            Performance statistics
        """
        try:
            stats = {}
            
            for widget_id, registration in self.registered_widgets.items():
                stats[widget_id] = {
                    'symbol': registration.symbol,
                    'priority': registration.priority.value,
                    'update_count': registration.update_count,
                    'error_count': registration.error_count,
                    'last_update': registration.last_update,
                    'success_rate': (registration.update_count / 
                                   max(1, registration.update_count + registration.error_count)) * 100
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"❌ Error getting widget performance: {e}")
            return {}

# ================================================================================
# GLOBAL BRIDGE INSTANCE
# ================================================================================

_bridge_instance: Optional[DashboardDataBridge] = None

def get_bridge_instance() -> DashboardDataBridge:
    """
    Get singleton bridge instance
    
    Returns:
        DashboardDataBridge instance
    """
    global _bridge_instance
    
    if _bridge_instance is None:
        _bridge_instance = DashboardDataBridge()
    
    return _bridge_instance

# ================================================================================
# STANDALONE TESTING AND MAIN EXECUTION
# ================================================================================

def main():
    """Main execution for testing"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 SPYDER G08 - Dashboard Data Bridge")
    print("=" * 60)
    
    try:
        # Test bridge functionality
        print("🧪 Testing Dashboard Data Bridge...")
        
        # Get bridge instance
        bridge = get_bridge_instance()
        
        # Initialize and start
        if bridge.initialize():
            print("✅ Bridge initialized successfully")
            
            if bridge.start():
                print("✅ Bridge started successfully")
                
                # Test widget registration (mock widget)
                class MockWidget:
                    def __init__(self, name):
                        self.name = name
                        self.last_data = None
                    
                    def update_display(self, data_dict):
                        self.last_data = data_dict
                        print(f"📊 {self.name} updated: {data_dict.get('formatted_price', 'N/A')}")
                
                # Register mock widgets
                spy_widget = MockWidget("SPY Widget")
                widget_id = bridge.register_widget(
                    spy_widget, "SPY", "update_display", UpdatePriority.CRITICAL
                )
                
                print(f"✅ Registered widget: {widget_id}")
                
                # Let it run for a few seconds
                time.sleep(3)
                
                # Get status
                status = bridge.get_status()
                print(f"\n📈 Bridge Status:")
                print(f"   Running: {status['is_running']}")
                print(f"   Widgets: {status['widgets_registered']}")
                print(f"   Updates: {status['metrics']['total_updates']}")
                
                # Stop bridge
                if bridge.stop():
                    print("✅ Bridge stopped successfully")
        
        print("\n🎯 Dashboard Data Bridge test complete!")
        
    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
