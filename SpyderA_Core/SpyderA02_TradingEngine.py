#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderA02_TradingEngine.py
Group: A (Core Trading Engine)
Purpose: Core trading engine and orchestration

Description:
This module implements the core trading engine that orchestrates all trading
operations including strategy execution, order management, position tracking,
and risk monitoring. It integrates all system components to provide automated
trading capabilities for SPY options strategies.

Author: Mohamed Talib
Created: 2025-01-27
Version: 1.6
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
import threading
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

# =============================================================================
# Local Application Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
# Add this import to ensure TRADING_DAYS_PER_YEAR is available
from SpyderU_Utilities.SpyderU07_Constants import TRADING_DAYS_PER_YEAR


# =============================================================================
# Enumerations
# =============================================================================
class EngineState(Enum):
    """Trading engine states."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ComponentStatus(Enum):
    """Component status types."""
    NOT_INITIALIZED = "not_initialized"
    INITIALIZING = "initializing"
    READY = "ready"
    ERROR = "error"
    SHUTDOWN = "shutdown"


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class EngineStats:
    """Trading engine statistics."""
    start_time: Optional[datetime] = None
    trade_count: int = 0
    error_count: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.now)
    uptime_seconds: float = 0.0
    performance_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ComponentInfo:
    """Component information."""
    name: str
    status: ComponentStatus = ComponentStatus.NOT_INITIALIZED
    last_update: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None


# =============================================================================
# Trading Engine Class
# =============================================================================
class TradingEngine:
    """
    Core trading engine for the Spyder system.

    This class orchestrates all trading operations including strategy execution,
    order management, position tracking, and risk monitoring. It integrates
    all system components to provide automated trading capabilities.
    """

    def __init__(self, config, ib_client, event_manager):
        """
        Initialize trading engine.

        Args:
            config: Configuration manager instance
            ib_client: Interactive Brokers client
            event_manager: Event manager instance
        """
        self.config = config
        self.ib_client = ib_client
        self.event_manager = event_manager

        # Initialize logger and error handler
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Initialize components (will be set up later)
        self.strategy_manager = None
        self.risk_manager = None
        self.data_feed_manager = None
        self.order_manager = None
        self.position_manager = None

        # Component tracking
        self.components: Dict[str, ComponentInfo] = {
            'strategy_manager': ComponentInfo('StrategyManager'),
            'risk_manager': ComponentInfo('RiskManager'),
            'data_feed_manager': ComponentInfo('DataFeedManager'),
            'order_manager': ComponentInfo('OrderManager'),
            'position_manager': ComponentInfo('PositionManager')
        }

        # State management
        self.state = EngineState.STOPPED
        self.is_running = False
        self.is_initialized = False
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()

        # Statistics
        self.stats = EngineStats()

        # Heartbeat thread
        self._heartbeat_thread = None
        self._heartbeat_interval = 60  # seconds

        self.logger.info("Trading engine initialized")

    def start(self) -> bool:
        """
        Start the trading engine.

        Returns:
            bool: True if started successfully
        """
        try:
            self.logger.info("Starting trading engine...")
            
            with self._state_lock:
                if self.state != EngineState.STOPPED:
                    self.logger.warning(f"Cannot start engine from state: {self.state.value}")
                    return False
                
                self.state = EngineState.STARTING

            # Initialize components
            if not self._initialize_components():
                self.logger.error("Failed to initialize components")
                self.state = EngineState.ERROR
                return False

            # Setup event subscriptions
            self._setup_event_subscriptions()

            # Start heartbeat
            self._start_heartbeat()

            # Update state
            with self._state_lock:
                self.is_running = True
                self.state = EngineState.RUNNING
                self.stats.start_time = datetime.now()

            self.logger.info("Trading engine started successfully")
            self._publish_engine_event("ENGINE_STARTED", {"time": datetime.now().isoformat()})
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to start trading engine: {e}")
            self.error_handler.handle_error(e, "ENGINE_START")
            self.state = EngineState.ERROR
            self.stats.error_count += 1
            return False

    def stop(self) -> bool:
        """
        Stop the trading engine.

        Returns:
            bool: True if stopped successfully
        """
        try:
            self.logger.info("Stopping trading engine...")
            
            with self._state_lock:
                if self.state not in [EngineState.RUNNING, EngineState.ERROR]:
                    self.logger.warning(f"Cannot stop engine from state: {self.state.value}")
                    return False
                
                self.state = EngineState.STOPPING

            # Signal stop
            self._stop_event.set()
            self.is_running = False

            # Stop heartbeat
            if self._heartbeat_thread and self._heartbeat_thread.is_alive():
                self._heartbeat_thread.join(timeout=5)

            # Shutdown components
            self._shutdown_components()

            # Update state
            with self._state_lock:
                self.state = EngineState.STOPPED
                if self.stats.start_time:
                    self.stats.uptime_seconds = (datetime.now() - self.stats.start_time).total_seconds()

            self.logger.info("Trading engine stopped successfully")
            self._publish_engine_event("ENGINE_STOPPED", {"time": datetime.now().isoformat()})
            
            return True

        except Exception as e:
            self.logger.error(f"Error stopping trading engine: {e}")
            self.error_handler.handle_error(e, "ENGINE_STOP")
            return False

    def get_status(self) -> Dict[str, Any]:
        """
        Get engine status.

        Returns:
            Dict containing engine status information
        """
        with self._state_lock:
            uptime = (
                (datetime.now() - self.stats.start_time).total_seconds() 
                if self.stats.start_time else 0
            )

            # Get component statuses
            component_statuses = {}
            for name, info in self.components.items():
                component_statuses[name] = {
                    'status': info.status.value,
                    'last_update': info.last_update.isoformat(),
                    'error': info.error_message
                }

            return {
                "state": self.state.value,
                "is_running": self.is_running,
                "is_initialized": self.is_initialized,
                "uptime_seconds": uptime,
                "trade_count": self.stats.trade_count,
                "error_count": self.stats.error_count,
                "last_heartbeat": self.stats.last_heartbeat.isoformat(),
                "components": component_statuses,
                "performance": self.stats.performance_metrics
            }

    def process_trade_signal(self, signal: Dict[str, Any]) -> bool:
        """
        Process a trade signal.

        Args:
            signal: Trade signal data

        Returns:
            bool: True if processed successfully
        """
        try:
            if not self.is_running:
                self.logger.warning("Engine not running, ignoring trade signal")
                return False

            # Validate signal
            if not self._validate_trade_signal(signal):
                self.logger.error("Invalid trade signal")
                return False

            # Check risk if risk manager available
            if self.risk_manager:
                try:
                    risk_check = self.risk_manager.check_trade_risk(
                        symbol=signal.get('symbol'),
                        trade_type=signal.get('trade_type'),
                        quantity=signal.get('quantity'),
                        price=signal.get('price')
                    )
                    
                    if hasattr(risk_check, 'approved') and not risk_check.approved:
                        self.logger.warning(f"Trade rejected by risk manager")
                        return False
                except Exception as e:
                    self.logger.warning(f"Risk check failed: {e}")
                    # Continue if risk check fails

            # Execute trade through order manager if available
            if self.order_manager:
                try:
                    order_result = self.order_manager.submit_order(signal)
                    if order_result.get('success'):
                        self.stats.trade_count += 1
                        self._publish_engine_event("TRADE_EXECUTED", signal)
                        return True
                except Exception as e:
                    self.logger.error(f"Order submission failed: {e}")

            # If no order manager, just log the signal
            self.logger.info(f"Trade signal processed: {signal}")
            self.stats.trade_count += 1
            return True

        except Exception as e:
            self.logger.error(f"Error processing trade signal: {e}")
            self.error_handler.handle_error(e, "PROCESS_TRADE")
            self.stats.error_count += 1
            return False

    # ==========================================================================
    # Private Methods
    # ==========================================================================
    def _initialize_components(self) -> bool:
        """
        Initialize all trading components.

        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing trading components...")
            
            # Track initialization success
            init_success = True

            # Components to initialize - ORDER MATTERS!
            # Try to initialize components that don't depend on QuantLib first
            components_config = [
                ('data_feed_manager', 'SpyderC_MarketData.SpyderC01_DataFeed', 'get_data_feed_manager', False),
                ('risk_manager', 'SpyderE_Risk.SpyderE01_RiskManager', 'get_risk_manager', True),
                ('order_manager', 'SpyderB_Broker.SpyderB02_OrderManager', 'get_order_manager', False),
                ('position_manager', 'SpyderB_Broker.SpyderB03_PositionTracker', 'get_position_tracker', False),
                # Strategy manager might depend on Greeks calculator, so try it last
                ('strategy_manager', 'SpyderD_Strategies.SpyderD08_StrategyManager', 'get_strategy_manager', False),
            ]

            for comp_name, module_path, factory_func, is_critical in components_config:
                success = self._initialize_component(comp_name, module_path, factory_func)
                if not success and is_critical:
                    self.logger.error(f"Critical component {comp_name} failed to initialize")
                    init_success = False

            # Set initialized even if some non-critical components failed
            self.is_initialized = init_success
            return init_success

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            self.error_handler.handle_error(e, "COMPONENT_INIT")
            return False

    def _initialize_component(self, component_name: str, module_path: str, 
                            factory_function: str) -> bool:
        """
        Initialize a single component.

        Args:
            component_name: Name of the component
            module_path: Module import path
            factory_function: Factory function name

        Returns:
            bool: True if initialized successfully
        """
        try:
            self.components[component_name].status = ComponentStatus.INITIALIZING
            
            # Dynamic import with error handling
            try:
                module = __import__(module_path, fromlist=[factory_function])
                factory = getattr(module, factory_function)
            except ImportError as e:
                # Check if it's a QuantLib-related import error
                if 'QuantLib' in str(e):
                    self.logger.warning(f"{component_name} requires QuantLib which is not available")
                    self.components[component_name].status = ComponentStatus.ERROR
                    self.components[component_name].error_message = "QuantLib not available"
                    return False
                else:
                    raise
            
            # Get instance (pass dependencies if needed)
            if component_name in ['order_manager', 'position_manager']:
                instance = factory(self.ib_client)
            else:
                instance = factory()
            
            # Store instance
            setattr(self, component_name, instance)
            
            # Update status
            self.components[component_name].status = ComponentStatus.READY
            self.components[component_name].last_update = datetime.now()
            self.components[component_name].error_message = None
            
            self.logger.info(f"{component_name} initialized successfully")
            return True

        except Exception as e:
            self.logger.warning(f"Could not initialize {component_name}: {e}")
            self.components[component_name].status = ComponentStatus.ERROR
            self.components[component_name].error_message = str(e)
            return False

    def _get_component_instance(self, component_name: str) -> Optional[Any]:
        """Get component instance if available."""
        return getattr(self, component_name, None)

    def _shutdown_components(self) -> None:
        """Shutdown all components gracefully."""
        try:
            components_to_shutdown = [
                ('strategy_manager', self.strategy_manager),
                ('order_manager', self.order_manager),
                ('position_manager', self.position_manager),
                ('risk_manager', self.risk_manager),
                ('data_feed_manager', self.data_feed_manager)
            ]

            for name, component in components_to_shutdown:
                if component and hasattr(component, 'shutdown'):
                    try:
                        component.shutdown()
                        self.components[name].status = ComponentStatus.SHUTDOWN
                        self.logger.info(f"{name} shut down successfully")
                    except Exception as e:
                        self.logger.error(f"Error shutting down {name}: {e}")

        except Exception as e:
            self.logger.error(f"Error shutting down components: {e}")

    def _setup_event_subscriptions(self):
        """Subscribe to relevant events."""
        try:
            if self.event_manager:
                # Subscribe to critical events
                event_subscriptions = [
                    ("MARKET_DATA", self._handle_market_data),
                    ("ORDER_FILLED", self._handle_order_filled),
                    ("POSITION_UPDATED", self._handle_position_update),
                    ("RISK_ALERT", self._handle_risk_alert),
                    ("STRATEGY_SIGNAL", self._handle_strategy_signal),
                    ("CONNECTION_LOST", self._handle_connection_lost)
                ]

                for event_type, handler in event_subscriptions:
                    try:
                        self.event_manager.subscribe(event_type, handler)
                    except Exception as e:
                        self.logger.warning(f"Could not subscribe to {event_type}: {e}")

                self.logger.debug("Trading engine event subscriptions completed")

        except Exception as e:
            self.logger.error(f"Failed to subscribe to events: {str(e)}")

    def _start_heartbeat(self):
        """Start heartbeat monitoring thread."""
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True
        )
        self._heartbeat_thread.start()

    def _heartbeat_loop(self):
        """Heartbeat monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self.stats.last_heartbeat = datetime.now()
                
                # Check component health
                self._check_component_health()
                
                # Update performance metrics
                self._update_performance_metrics()
                
                # Publish heartbeat event
                self._publish_engine_event("ENGINE_HEARTBEAT", {
                    "timestamp": datetime.now().isoformat(),
                    "trade_count": self.stats.trade_count,
                    "error_count": self.stats.error_count
                })
                
            except Exception as e:
                self.logger.error(f"Error in heartbeat: {e}")
            
            self._stop_event.wait(self._heartbeat_interval)

    def _check_component_health(self):
        """Check health of all components."""
        for name, component in [
            ('strategy_manager', self.strategy_manager),
            ('risk_manager', self.risk_manager),
            ('data_feed_manager', self.data_feed_manager),
            ('order_manager', self.order_manager),
            ('position_manager', self.position_manager)
        ]:
            if component and hasattr(component, 'is_healthy'):
                try:
                    if not component.is_healthy():
                        self.logger.warning(f"{name} health check failed")
                        self.components[name].status = ComponentStatus.ERROR
                except Exception as e:
                    self.logger.debug(f"Error checking {name} health: {e}")

    def _update_performance_metrics(self):
        """Update performance metrics."""
        try:
            # Calculate metrics
            if self.stats.start_time:
                uptime_hours = (datetime.now() - self.stats.start_time).total_seconds() / 3600
                if uptime_hours > 0:
                    trades_per_hour = self.stats.trade_count / uptime_hours
                    self.stats.performance_metrics['trades_per_hour'] = round(trades_per_hour, 2)
                
                # Error rate
                total_operations = self.stats.trade_count + self.stats.error_count
                if total_operations > 0:
                    error_rate = self.stats.error_count / total_operations
                    self.stats.performance_metrics['error_rate'] = round(error_rate, 4)

        except Exception as e:
            self.logger.error(f"Error updating performance metrics: {e}")

    def _validate_trade_signal(self, signal: Dict[str, Any]) -> bool:
        """Validate trade signal format."""
        required_fields = ['symbol', 'trade_type', 'quantity', 'price']
        return all(field in signal for field in required_fields)

    def _publish_engine_event(self, event_type: str, data: Dict[str, Any]):
        """Publish engine event."""
        try:
            if self.event_manager:
                self.event_manager.publish(event_type, {
                    'source': 'TradingEngine',
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                })
        except Exception as e:
            self.logger.debug(f"Failed to publish engine event: {e}")

    # ==========================================================================
    # Event Handlers
    # ==========================================================================
    def _handle_market_data(self, event_data: Dict[str, Any]):
        """Handle market data events."""
        # Process market data updates
        pass

    def _handle_order_filled(self, event_data: Dict[str, Any]):
        """Handle order filled events."""
        try:
            self.stats.trade_count += 1
            self.logger.info(f"Order filled: {event_data}")
        except Exception as e:
            self.logger.error(f"Error handling order filled: {e}")

    def _handle_position_update(self, event_data: Dict[str, Any]):
        """Handle position update events."""
        # Update position tracking
        pass

    def _handle_risk_alert(self, event_data: Dict[str, Any]):
        """Handle risk alert events."""
        try:
            alert_level = event_data.get('level', 'WARNING')
            message = event_data.get('message', 'Unknown risk alert')
            
            self.logger.warning(f"Risk alert [{alert_level}]: {message}")
            
            # Take action based on alert level
            if alert_level == 'CRITICAL':
                self.logger.error("Critical risk alert - considering engine shutdown")
                # Could trigger controlled shutdown if needed
                
        except Exception as e:
            self.logger.error(f"Error handling risk alert: {e}")

    def _handle_strategy_signal(self, event_data: Dict[str, Any]):
        """Handle strategy signal events."""
        try:
            signal = event_data.get('signal', {})
            if signal:
                self.process_trade_signal(signal)
        except Exception as e:
            self.logger.error(f"Error handling strategy signal: {e}")

    def _handle_connection_lost(self, event_data: Dict[str, Any]):
        """Handle connection lost events."""
        try:
            self.logger.error("Connection lost to broker")
            # Could pause trading or attempt reconnection
        except Exception as e:
            self.logger.error(f"Error handling connection lost: {e}")

    # ==========================================================================
    # Public Methods - Additional
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up resources and prepare for shutdown."""
        try:
            self.logger.info("Cleaning up trading engine resources...")

            # Stop the engine if still running
            if self.is_running:
                self.stop()

            # Clear references
            self.strategy_manager = None
            self.risk_manager = None
            self.data_feed_manager = None
            self.order_manager = None
            self.position_manager = None

            self.logger.info("Trading engine cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during trading engine cleanup: {e}")

    def get_component_status(self, component_name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific component.

        Args:
            component_name: Name of the component

        Returns:
            Component status information or None
        """
        if component_name in self.components:
            info = self.components[component_name]
            return {
                'name': info.name,
                'status': info.status.value,
                'last_update': info.last_update.isoformat(),
                'error': info.error_message
            }
        return None

    def check_risk_limits(self) -> Dict[str, Any]:
        """
        Check current risk limits.

        Returns:
            Risk limit status
        """
        if self.risk_manager:
            try:
                return self.risk_manager.check_risk_limits()
            except Exception as e:
                self.logger.error(f"Error checking risk limits: {e}")
                return {"status": "error", "message": str(e)}
        return {"status": "risk_manager_not_available"}

    def get_active_strategies(self) -> List[Dict[str, Any]]:
        """
        Get list of active strategies.

        Returns:
            List of active strategy information
        """
        if self.strategy_manager:
            try:
                return self.strategy_manager.get_active_strategies()
            except Exception as e:
                self.logger.error(f"Error getting active strategies: {e}")
                return []
        return []


# =============================================================================
# Module Functions
# =============================================================================
def get_trading_engine(config=None, ib_client=None, event_manager=None):
    """
    Get trading engine instance.

    Args:
        config: Configuration manager
        ib_client: IB client
        event_manager: Event manager

    Returns:
        TradingEngine instance
    """
    global _TRADING_ENGINE_INSTANCE
    if _TRADING_ENGINE_INSTANCE is None and all([config, ib_client, event_manager]):
        _TRADING_ENGINE_INSTANCE = TradingEngine(config, ib_client, event_manager)
    return _TRADING_ENGINE_INSTANCE


# =============================================================================
# Module Initialization
# =============================================================================
_TRADING_ENGINE_INSTANCE: Optional[TradingEngine] = None


# =============================================================================
# Main - Testing
# =============================================================================
if __name__ == "__main__":
    # Test basic engine functionality
    print("Testing TradingEngine module...")
    
    # Create mock dependencies
    class MockConfig:
        def get(self, key, default=None):
            return default
    
    class MockIBClient:
        def is_connected(self):
            return True
    
    class MockEventManager:
        def subscribe(self, event_type, handler):
            pass
        
        def publish(self, event_type, data):
            pass
    
    # Create engine
    config = MockConfig()
    ib_client = MockIBClient()
    event_manager = MockEventManager()
    
    engine = TradingEngine(config, ib_client, event_manager)
    
    # Test status
    status = engine.get_status()
    print(f"Engine status: {status['state']}")
    print(f"Components: {len(status['components'])}")
    
    # Test signal validation
    valid_signal = {
        'symbol': 'SPY',
        'trade_type': 'BUY',
        'quantity': 10,
        'price': 450.0
    }
    
    is_valid = engine._validate_trade_signal(valid_signal)
    print(f"Signal validation: {is_valid}")
    
    # Test startup
    if engine.start():
        print("Engine started successfully")
        
        # Check component status
        for comp_name in engine.components:
            comp_status = engine.get_component_status(comp_name)
            print(f"{comp_name}: {comp_status['status']}")
        
        # Process a test signal
        result = engine.process_trade_signal(valid_signal)
        print(f"Signal processing result: {result}")
        
        # Get final status
        final_status = engine.get_status()
        print(f"Trade count: {final_status['trade_count']}")
        print(f"Error count: {final_status['error_count']}")
        
        # Stop engine
        engine.stop()
    
    print("✅ TradingEngine module test completed")
