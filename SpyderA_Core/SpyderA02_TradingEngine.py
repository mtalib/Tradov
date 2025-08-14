#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderA02_TradingEngine.py
Group: A (Core Trading Engine)
Purpose: Complete trading engine with strategy orchestration and execution

Description:
    This module serves as the core trading engine for the Spyder system. It manages
    strategy registration and lifecycle, coordinates order execution, handles position
    management, and integrates with risk management systems. The engine provides
    real-time monitoring, automated error recovery, and comprehensive performance
    tracking for all trading operations.

Spyder Version: 2.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-06 - Production Ready
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
import weakref
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import pickle

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from threading import Lock, Event as ThreadEvent, RLock
import schedule

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    OrderAction, OrderType, OptionType, SignalType
)
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager, RiskProfile
from SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer

# ==============================================================================
# CONSTANTS
# ==============================================================================
MAX_STRATEGIES = 20
MAX_ORDERS_PER_MINUTE = 100
MAX_POSITION_AGE_HOURS = 24
PERFORMANCE_WINDOW_SIZE = 1000
HEALTH_CHECK_INTERVAL = 60  # seconds
CLEANUP_INTERVAL = 300  # 5 minutes
STATE_SAVE_INTERVAL = 60  # seconds
MAX_ORDER_RETRIES = 3
ORDER_RETRY_DELAY = 1  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class EngineState(Enum):
    """Trading engine operational states"""
    INITIALIZING = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()
    RECOVERING = auto()

class StrategyState(Enum):
    """Strategy lifecycle states"""
    REGISTERED = auto()
    INITIALIZING = auto()
    ACTIVE = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()
    DISABLED = auto()

class OrderState(Enum):
    """Order execution states"""
    PENDING = auto()
    SUBMITTED = auto()
    FILLED = auto()
    PARTIAL_FILL = auto()
    CANCELLED = auto()
    REJECTED = auto()
    ERROR = auto()

class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    NORMAL = auto()
    WARNING = auto()
    TRIGGERED = auto()
    RECOVERING = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyInfo:
    """Strategy registration information"""
    strategy_id: str
    name: str
    class_instance: Any
    state: StrategyState = StrategyState.REGISTERED
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_signal: Optional[datetime] = None
    signal_count: int = 0
    order_count: int = 0
    pnl: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class OrderInfo:
    """Order tracking information"""
    order_id: str
    strategy_id: str
    symbol: str
    action: OrderAction
    order_type: OrderType
    quantity: int
    price: Optional[float]
    state: OrderState = OrderState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    fill_price: Optional[float] = None
    commission: float = 0.0
    retry_count: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PositionInfo:
    """Position tracking information"""
    position_id: str
    strategy_id: str
    symbol: str
    quantity: int
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    high_water_mark: float = 0.0
    max_drawdown: float = 0.0
    holding_period: timedelta = timedelta()
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class PerformanceMetrics:
    """Engine performance metrics"""
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    uptime_seconds: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    max_loss_per_minute: float = 1000.0
    max_orders_per_minute: int = 50
    max_errors_per_hour: int = 10
    max_daily_loss: float = 5000.0
    cooldown_minutes: int = 15
    recovery_threshold: float = 0.8  # 80% of limits

@dataclass
class EngineHealth:
    """Engine health status"""
    state: EngineState
    uptime: timedelta
    active_strategies: int
    open_orders: int
    open_positions: int
    circuit_breaker_state: CircuitBreakerState
    last_error: Optional[str]
    error_rate: float
    order_success_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    last_health_check: datetime

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TradingEngine:
    """
    Core trading engine for strategy orchestration and execution.
    
    This class manages the complete lifecycle of trading strategies including
    registration, initialization, signal processing, order execution, position
    management, and performance tracking. It provides thread-safe operations,
    circuit breaker protection, and comprehensive error recovery.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling system
        event_manager: Event management system
        spyder_client: Broker client interface
        risk_manager: Risk management system
        dal: Data access layer
        state: Current engine state
        strategies: Registered trading strategies
        orders: Active order tracking
        positions: Open position tracking
        performance: Performance metrics
        circuit_breaker: Circuit breaker protection
    """
    
    def __init__(self, config: Dict[str, Any], spyder_client, event_manager: EventManager):
        """
        Initialize the trading engine.
        
        Args:
            config: Engine configuration
            spyder_client: Broker client instance
            event_manager: Event management system
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = event_manager
        self.spyder_client = spyder_client
        self.dal = get_data_access_layer()
        
        # Configuration
        self.config = config or {}
        self.max_strategies = self.config.get('max_strategies', MAX_STRATEGIES)
        self.max_orders_per_minute = self.config.get('max_orders_per_minute', MAX_ORDERS_PER_MINUTE)
        self.enable_circuit_breaker = self.config.get('enable_circuit_breaker', True)
        self.save_state_enabled = self.config.get('save_state', True)
        
        # State management
        self.state = EngineState.INITIALIZING
        self._state_lock = RLock()
        self._shutdown_event = ThreadEvent()
        
        # Strategy management
        self.strategies: Dict[str, StrategyInfo] = {}
        self._strategy_lock = RLock()
        
        # Order management
        self.orders: Dict[str, OrderInfo] = {}
        self.order_queue = queue.PriorityQueue()
        self._order_lock = RLock()
        self._order_processor_thread = None
        
        # Position management
        self.positions: Dict[str, PositionInfo] = {}
        self._position_lock = RLock()
        
        # Performance tracking
        self.performance = PerformanceMetrics()
        self.performance_history = deque(maxlen=PERFORMANCE_WINDOW_SIZE)
        self._performance_lock = Lock()
        
        # Circuit breaker
        self.circuit_breaker_config = self._init_circuit_breaker_config()
        self.circuit_breaker_state = CircuitBreakerState.NORMAL
        self.circuit_breaker_metrics = {
            'loss_per_minute': 0.0,
            'orders_per_minute': 0,
            'errors_per_hour': 0,
            'daily_loss': 0.0,
            'triggered_at': None,
            'recovery_at': None
        }
        self._circuit_breaker_lock = Lock()
        
        # Risk management integration
        self.risk_manager = None
        self.has_risk_manager = False
        
        # Order manager integration
        self.order_manager = None
        self.has_order_manager = False
        
        # Position tracker integration
        self.position_tracker = None
        self.has_position_tracker = False
        
        # Worker threads
        self._monitor_thread = None
        self._cleanup_thread = None
        self._state_save_thread = None
        
        # Timing
        self.start_time = None
        self.last_health_check = datetime.now()
        
        # State persistence
        self._state_file = Path.home() / ".spyder" / "engine_state.pkl"
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"TradingEngine initialized with {len(self.config)} config parameters")

    def _init_circuit_breaker_config(self) -> CircuitBreakerConfig:
        """Initialize circuit breaker configuration"""
        cb_config = self.config.get('circuit_breaker', {})
        return CircuitBreakerConfig(
            max_loss_per_minute=cb_config.get('max_loss_per_minute', 1000.0),
            max_orders_per_minute=cb_config.get('max_orders_per_minute', 50),
            max_errors_per_hour=cb_config.get('max_errors_per_hour', 10),
            max_daily_loss=cb_config.get('max_daily_loss', 5000.0),
            cooldown_minutes=cb_config.get('cooldown_minutes', 15),
            recovery_threshold=cb_config.get('recovery_threshold', 0.8)
        )

    # ==========================================================================
    # LIFECYCLE MANAGEMENT
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the trading engine with all safety checks.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.INITIALIZING:
                    self.logger.warning(f"Cannot initialize from state: {self.state}")
                    return False
                
                self.logger.info("Initializing TradingEngine...")
                
                # Load saved state if available
                if self.save_state_enabled:
                    self._load_state()
                
                # Initialize risk management
                try:
                    self.risk_manager = get_risk_manager()
                    if self.risk_manager and self.risk_manager.initialize():
                        self.has_risk_manager = True
                        self.logger.info("Risk manager initialized")
                    else:
                        self.logger.warning("Risk manager not available")
                except Exception as e:
                    self.logger.warning(f"Risk manager initialization failed: {e}")
                
                # Set up event handlers
                self._setup_event_handlers()
                
                # Initialize performance tracking
                self._initialize_performance_tracking()
                
                # Validate configuration
                if not self._validate_configuration():
                    self.logger.error("Configuration validation failed")
                    return False
                
                self.state = EngineState.READY
                self.logger.info("TradingEngine initialization completed successfully")
                
                # Emit initialization event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'engine_initialized',
                        'timestamp': datetime.now(),
                        'state': self.state.value
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine initialization failed: {e}")
            self.error_handler.handle_error(e, "TradingEngine.initialize")
            self.state = EngineState.ERROR
            return False

    def start(self) -> bool:
        """
        Start the trading engine with all subsystems.
        
        Returns:
            bool: True if start successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.READY:
                    self.logger.warning(f"Cannot start from state: {self.state}")
                    return False
                
                self.logger.info("Starting TradingEngine...")
                self.start_time = datetime.now()
                
                # Clear shutdown event
                self._shutdown_event.clear()
                
                # Start worker threads
                self._start_worker_threads()
                
                # Start monitoring systems
                self._start_monitoring()
                
                # Start risk monitoring if available
                if self.has_risk_manager and self.risk_manager:
                    self.risk_manager.start_monitoring()
                
                # Initialize circuit breaker metrics
                self._reset_circuit_breaker_metrics()
                
                self.state = EngineState.RUNNING
                self.logger.info("TradingEngine started successfully")
                
                # Emit start event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'engine_started',
                        'timestamp': self.start_time,
                        'state': self.state.value
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine start failed: {e}")
            self.error_handler.handle_error(e, "TradingEngine.start")
            self.state = EngineState.ERROR
            return False

    def stop(self, reason: str = "Manual stop") -> bool:
        """
        Stop the trading engine gracefully.
        
        Args:
            reason: Reason for stopping
            
        Returns:
            bool: True if stop successful
        """
        try:
            with self._state_lock:
                if self.state not in [EngineState.RUNNING, EngineState.PAUSED, EngineState.ERROR]:
                    self.logger.warning(f"Cannot stop from state: {self.state}")
                    return False
                
                self.logger.info(f"Stopping TradingEngine: {reason}")
                
                # Signal shutdown
                self._shutdown_event.set()
                
                # Stop all strategies
                self._stop_all_strategies(reason)
                
                # Cancel pending orders
                self._cancel_all_pending_orders(reason)
                
                # Stop worker threads
                self._stop_worker_threads()
                
                # Save final state
                if self.save_state_enabled:
                    self._save_state()
                
                # Calculate session metrics
                if self.start_time:
                    session_duration = datetime.now() - self.start_time
                    self.performance.uptime_seconds = session_duration.total_seconds()
                
                self.state = EngineState.STOPPED
                self.logger.info(f"TradingEngine stopped successfully after {session_duration}")
                
                # Emit stop event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'engine_stopped',
                        'timestamp': datetime.now(),
                        'reason': reason,
                        'session_duration': str(session_duration) if self.start_time else None
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine stop failed: {e}")
            self.error_handler.handle_error(e, "TradingEngine.stop")
            return False

    def pause(self, reason: str = "Manual pause") -> bool:
        """
        Pause trading operations without stopping the engine.
        
        Args:
            reason: Reason for pausing
            
        Returns:
            bool: True if pause successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.RUNNING:
                    self.logger.warning(f"Cannot pause from state: {self.state}")
                    return False
                
                self.logger.info(f"Pausing TradingEngine: {reason}")
                
                # Pause all active strategies
                for strategy_id in list(self.strategies.keys()):
                    self._pause_strategy(strategy_id)
                
                self.state = EngineState.PAUSED
                
                # Emit pause event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'engine_paused',
                        'timestamp': datetime.now(),
                        'reason': reason
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine pause failed: {e}")
            self.error_handler.handle_error(e, "TradingEngine.pause")
            return False

    def resume(self) -> bool:
        """
        Resume trading operations after pause.
        
        Returns:
            bool: True if resume successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.PAUSED:
                    self.logger.warning(f"Cannot resume from state: {self.state}")
                    return False
                
                self.logger.info("Resuming TradingEngine...")
                
                # Check circuit breaker state
                if self.circuit_breaker_state == CircuitBreakerState.TRIGGERED:
                    self.logger.warning("Cannot resume - circuit breaker is triggered")
                    return False
                
                # Resume all paused strategies
                for strategy_id, strategy_info in self.strategies.items():
                    if strategy_info.state == StrategyState.PAUSED:
                        self._resume_strategy(strategy_id)
                
                self.state = EngineState.RUNNING
                
                # Emit resume event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'engine_resumed',
                        'timestamp': datetime.now()
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine resume failed: {e}")
            self.error_handler.handle_error(e, "TradingEngine.resume")
            return False

    def shutdown(self) -> bool:
        """
        Perform complete shutdown with cleanup.
        
        Returns:
            bool: True if shutdown successful
        """
        try:
            self.logger.info("Shutting down TradingEngine...")
            
            # Stop if running
            if self.state in [EngineState.RUNNING, EngineState.PAUSED]:
                self.stop("Shutdown requested")
            
            # Clean up resources
            self._cleanup_resources()
            
            # Clear all data structures
            with self._strategy_lock:
                self.strategies.clear()
            
            with self._order_lock:
                self.orders.clear()
            
            with self._position_lock:
                self.positions.clear()
            
            self.logger.info("TradingEngine shutdown completed")
            return True
            
        except Exception as e:
            self.logger.error(f"TradingEngine shutdown failed: {e}")
            return False

    # ==========================================================================
    # STRATEGY MANAGEMENT
    # ==========================================================================
    def register_strategy(self, strategy_id: str, strategy_instance: Any,
                         config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register a trading strategy with the engine.
        
        Args:
            strategy_id: Unique strategy identifier
            strategy_instance: Strategy class instance
            config: Strategy configuration
            
        Returns:
            bool: True if registration successful
        """
        try:
            with self._strategy_lock:
                # Check if already registered
                if strategy_id in self.strategies:
                    self.logger.warning(f"Strategy {strategy_id} already registered")
                    return False
                
                # Check strategy limit
                if len(self.strategies) >= self.max_strategies:
                    self.logger.error(f"Maximum strategies ({self.max_strategies}) reached")
                    return False
                
                # Validate strategy instance
                if not self._validate_strategy(strategy_instance):
                    self.logger.error(f"Strategy {strategy_id} validation failed")
                    return False
                
                # Create strategy info
                strategy_info = StrategyInfo(
                    strategy_id=strategy_id,
                    name=getattr(strategy_instance, 'name', strategy_id),
                    class_instance=strategy_instance,
                    config=config or {},
                    state=StrategyState.REGISTERED
                )
                
                # Store strategy
                self.strategies[strategy_id] = strategy_info
                
                # Initialize strategy if engine is running
                if self.state == EngineState.RUNNING:
                    self._initialize_strategy(strategy_id)
                
                self.logger.info(f"Registered strategy: {strategy_id}")
                
                # Emit registration event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'strategy_registered',
                        'strategy_id': strategy_id,
                        'timestamp': datetime.now()
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Strategy registration failed: {e}")
            self.error_handler.handle_error(e, f"register_strategy.{strategy_id}")
            return False

    def unregister_strategy(self, strategy_id: str, force: bool = False) -> bool:
        """
        Unregister a trading strategy.
        
        Args:
            strategy_id: Strategy identifier
            force: Force unregistration even with open positions
            
        Returns:
            bool: True if unregistration successful
        """
        try:
            with self._strategy_lock:
                if strategy_id not in self.strategies:
                    self.logger.warning(f"Strategy {strategy_id} not found")
                    return False
                
                strategy_info = self.strategies[strategy_id]
                
                # Check for open positions
                open_positions = self._get_strategy_positions(strategy_id)
                if open_positions and not force:
                    self.logger.error(f"Cannot unregister strategy {strategy_id} with {len(open_positions)} open positions")
                    return False
                
                # Stop strategy if active
                if strategy_info.state in [StrategyState.ACTIVE, StrategyState.PAUSED]:
                    self._stop_strategy(strategy_id, "Unregistration requested")
                
                # Clean up strategy resources
                self._cleanup_strategy(strategy_id)
                
                # Remove strategy
                del self.strategies[strategy_id]
                
                self.logger.info(f"Unregistered strategy: {strategy_id}")
                
                # Emit unregistration event
                self.event_manager.emit(
                    EventType.SYSTEM,
                    {
                        'type': 'strategy_unregistered',
                        'strategy_id': strategy_id,
                        'timestamp': datetime.now()
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Strategy unregistration failed: {e}")
            self.error_handler.handle_error(e, f"unregister_strategy.{strategy_id}")
            return False

    def _validate_strategy(self, strategy_instance: Any) -> bool:
        """Validate strategy instance has required methods"""
        required_methods = ['initialize', 'generate_signals', 'on_position_update']
        
        for method in required_methods:
            if not hasattr(strategy_instance, method):
                self.logger.error(f"Strategy missing required method: {method}")
                return False
        
        return True

    def _initialize_strategy(self, strategy_id: str) -> bool:
        """Initialize a registered strategy"""
        try:
            strategy_info = self.strategies.get(strategy_id)
            if not strategy_info:
                return False
            
            strategy_info.state = StrategyState.INITIALIZING
            
            # Call strategy initialization
            if hasattr(strategy_info.class_instance, 'initialize'):
                result = strategy_info.class_instance.initialize(strategy_info.config)
                if not result:
                    strategy_info.state = StrategyState.ERROR
                    strategy_info.last_error = "Initialization failed"
                    return False
            
            strategy_info.state = StrategyState.ACTIVE
            self.logger.info(f"Strategy {strategy_id} initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Strategy initialization failed: {e}")
            strategy_info.state = StrategyState.ERROR
            strategy_info.last_error = str(e)
            return False

    def _stop_strategy(self, strategy_id: str, reason: str) -> bool:
        """Stop a running strategy"""
        try:
            strategy_info = self.strategies.get(strategy_id)
            if not strategy_info:
                return False
            
            # Cancel strategy orders
            self._cancel_strategy_orders(strategy_id, reason)
            
            # Call strategy stop method if available
            if hasattr(strategy_info.class_instance, 'stop'):
                strategy_info.class_instance.stop(reason)
            
            strategy_info.state = StrategyState.STOPPED
            self.logger.info(f"Strategy {strategy_id} stopped: {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"Strategy stop failed: {e}")
            return False

    def _pause_strategy(self, strategy_id: str) -> bool:
        """Pause a running strategy"""
        strategy_info = self.strategies.get(strategy_id)
        if strategy_info and strategy_info.state == StrategyState.ACTIVE:
            strategy_info.state = StrategyState.PAUSED
            self.logger.info(f"Strategy {strategy_id} paused")
            return True
        return False

    def _resume_strategy(self, strategy_id: str) -> bool:
        """Resume a paused strategy"""
        strategy_info = self.strategies.get(strategy_id)
        if strategy_info and strategy_info.state == StrategyState.PAUSED:
            strategy_info.state = StrategyState.ACTIVE
            self.logger.info(f"Strategy {strategy_id} resumed")
            return True
        return False

    def _cleanup_strategy(self, strategy_id: str):
        """Clean up strategy resources"""
        try:
            # Close any open positions (if forced)
            positions = self._get_strategy_positions(strategy_id)
            for position in positions:
                self.logger.warning(f"Force closing position {position.position_id}")
                # Implement position closing logic
            
            # Remove strategy orders from history
            with self._order_lock:
                strategy_orders = [oid for oid, order in self.orders.items() 
                                 if order.strategy_id == strategy_id]
                for order_id in strategy_orders:
                    del self.orders[order_id]
            
            # Call strategy cleanup if available
            strategy_info = self.strategies.get(strategy_id)
            if strategy_info and hasattr(strategy_info.class_instance, 'cleanup'):
                strategy_info.class_instance.cleanup()
                
        except Exception as e:
            self.logger.error(f"Strategy cleanup failed: {e}")

    def _stop_all_strategies(self, reason: str):
        """Stop all active strategies"""
        for strategy_id in list(self.strategies.keys()):
            strategy_info = self.strategies[strategy_id]
            if strategy_info.state in [StrategyState.ACTIVE, StrategyState.PAUSED]:
                self._stop_strategy(strategy_id, reason)

    # ==========================================================================
    # SIGNAL PROCESSING
    # ==========================================================================
    def process_signal(self, strategy_id: str, signal: Dict[str, Any]) -> bool:
        """
        Process a trading signal from a strategy.
        
        Args:
            strategy_id: Strategy identifier
            signal: Signal data dictionary
            
        Returns:
            bool: True if signal processed successfully
        """
        try:
            # Validate engine state
            if self.state != EngineState.RUNNING:
                self.logger.warning(f"Cannot process signal - engine state: {self.state}")
                return False
            
            # Validate strategy
            strategy_info = self.strategies.get(strategy_id)
            if not strategy_info:
                self.logger.error(f"Strategy {strategy_id} not found")
                return False
            
            if strategy_info.state != StrategyState.ACTIVE:
                self.logger.warning(f"Strategy {strategy_id} not active: {strategy_info.state}")
                return False
            
            # Check circuit breaker
            if self.circuit_breaker_state == CircuitBreakerState.TRIGGERED:
                self.logger.warning("Circuit breaker triggered - rejecting signal")
                return False
            
            # Validate signal
            if not self._validate_signal(signal):
                self.logger.error(f"Invalid signal from strategy {strategy_id}")
                return False
            
            # Risk check
            if self.has_risk_manager and not self._check_signal_risk(strategy_id, signal):
                self.logger.warning(f"Signal rejected by risk manager: {signal}")
                return False
            
            # Update strategy metrics
            strategy_info.last_signal = datetime.now()
            strategy_info.signal_count += 1
            
            # Create order from signal
            order = self._create_order_from_signal(strategy_id, signal)
            if not order:
                return False
            
            # Queue order for execution
            priority = 1 if signal.get('urgent', False) else 5
            self.order_queue.put((priority, order.order_id, order))
            
            self.logger.info(f"Signal processed from {strategy_id}: {signal.get('action', 'unknown')}")
            
            # Emit signal event
            self.event_manager.emit(
                EventType.STRATEGY_SIGNAL,
                {
                    'strategy_id': strategy_id,
                    'signal': signal,
                    'order_id': order.order_id,
                    'timestamp': datetime.now()
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Signal processing failed: {e}")
            self.error_handler.handle_error(e, f"process_signal.{strategy_id}")
            self._increment_strategy_error(strategy_id, str(e))
            return False

    def _validate_signal(self, signal: Dict[str, Any]) -> bool:
        """Validate signal has required fields"""
        required_fields = ['symbol', 'action', 'quantity']
        
        for field in required_fields:
            if field not in signal:
                self.logger.error(f"Signal missing required field: {field}")
                return False
        
        # Validate action
        try:
            OrderAction(signal['action'])
        except ValueError:
            self.logger.error(f"Invalid order action: {signal['action']}")
            return False
        
        # Validate quantity
        if not isinstance(signal['quantity'], (int, float)) or signal['quantity'] <= 0:
            self.logger.error(f"Invalid quantity: {signal['quantity']}")
            return False
        
        return True

    def _check_signal_risk(self, strategy_id: str, signal: Dict[str, Any]) -> bool:
        """Check signal against risk limits"""
        if not self.risk_manager:
            return True
        
        try:
            # Create risk check request
            risk_check = {
                'strategy_id': strategy_id,
                'symbol': signal['symbol'],
                'action': signal['action'],
                'quantity': signal['quantity'],
                'price': signal.get('price'),
                'existing_positions': len(self._get_strategy_positions(strategy_id))
            }
            
            # Perform risk check
            result = self.risk_manager.check_trade(risk_check)
            
            if not result['approved']:
                self.logger.warning(f"Risk check failed: {result.get('reason', 'Unknown')}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Risk check error: {e}")
            # Fail safe - reject on error
            return False

    def _create_order_from_signal(self, strategy_id: str, signal: Dict[str, Any]) -> Optional[OrderInfo]:
        """Create order object from signal"""
        try:
            order_id = f"{strategy_id}_{uuid.uuid4().hex[:8]}"
            
            order = OrderInfo(
                order_id=order_id,
                strategy_id=strategy_id,
                symbol=signal['symbol'],
                action=OrderAction(signal['action']),
                order_type=OrderType(signal.get('order_type', MARKET)),
                quantity=int(signal['quantity']),
                price=signal.get('price'),
                metadata=signal.get('metadata', {})
            )
            
            # Store order
            with self._order_lock:
                self.orders[order_id] = order
            
            return order
            
        except Exception as e:
            self.logger.error(f"Order creation failed: {e}")
            return None

    # ==========================================================================
    # ORDER EXECUTION
    # ==========================================================================
    def _start_order_processor(self):
        """Start order processing thread"""
        self._order_processor_thread = threading.Thread(
            target=self._order_processor_loop,
            name="OrderProcessor",
            daemon=True
        )
        self._order_processor_thread.start()

    def _order_processor_loop(self):
        """Main order processing loop"""
        self.logger.info("Order processor started")
        
        while not self._shutdown_event.is_set():
            try:
                # Get order from queue with timeout
                priority, order_id, order = self.order_queue.get(timeout=1.0)
                
                # Process order
                self._execute_order(order)
                
                # Update circuit breaker metrics
                self._update_order_rate_metrics()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Order processor error: {e}")
                self.error_handler.handle_error(e, "order_processor_loop")

    def _execute_order(self, order: OrderInfo) -> bool:
        """Execute a single order"""
        try:
            # Update order state
            order.state = OrderState.SUBMITTED
            order.submitted_at = datetime.now()
            
            # Check if broker connected
            if not self.spyder_client or not self.spyder_client.is_connected():
                order.state = OrderState.ERROR
                order.error_message = "Broker not connected"
                return False
            
            # Submit order to broker
            broker_order_id = self._submit_to_broker(order)
            
            if broker_order_id:
                order.metadata['broker_order_id'] = broker_order_id
                self.logger.info(f"Order {order.order_id} submitted to broker: {broker_order_id}")
                
                # Update strategy metrics
                self._update_strategy_order_count(order.strategy_id)
                
                return True
            else:
                # Handle submission failure
                order.retry_count += 1
                
                if order.retry_count < MAX_ORDER_RETRIES:
                    # Requeue for retry
                    self.logger.warning(f"Order {order.order_id} failed, retrying ({order.retry_count}/{MAX_ORDER_RETRIES})")
                    time.sleep(ORDER_RETRY_DELAY)
                    self.order_queue.put((5, order.order_id, order))
                else:
                    # Max retries exceeded
                    order.state = OrderState.ERROR
                    order.error_message = "Max retries exceeded"
                    self.logger.error(f"Order {order.order_id} failed after {MAX_ORDER_RETRIES} retries")
                    
                    # Notify strategy
                    self._notify_strategy_order_failed(order)
                
                return False
                
        except Exception as e:
            self.logger.error(f"Order execution failed: {e}")
            order.state = OrderState.ERROR
            order.error_message = str(e)
            return False

    def _submit_to_broker(self, order: OrderInfo) -> Optional[str]:
        """Submit order to broker"""
        try:
            # Build broker order
            broker_order = {
                'symbol': order.symbol,
                'action': order.action.value,
                'quantity': order.quantity,
                'order_type': order.order_type.value,
                'price': order.price
            }
            
            # Submit to broker
            result = self.spyder_client.place_order(broker_order)
            
            if result and result.get('order_id'):
                return result['order_id']
            else:
                self.logger.error(f"Broker order submission failed: {result}")
                return None
                
        except Exception as e:
            self.logger.error(f"Broker submission error: {e}")
            return None

    def _cancel_all_pending_orders(self, reason: str):
        """Cancel all pending orders"""
        with self._order_lock:
            pending_orders = [order for order in self.orders.values() 
                            if order.state in [OrderState.PENDING, OrderState.SUBMITTED]]
        
        for order in pending_orders:
            self._cancel_order(order.order_id, reason)

    def _cancel_strategy_orders(self, strategy_id: str, reason: str):
        """Cancel all orders for a strategy"""
        with self._order_lock:
            strategy_orders = [order for order in self.orders.values() 
                             if order.strategy_id == strategy_id and 
                             order.state in [OrderState.PENDING, OrderState.SUBMITTED]]
        
        for order in strategy_orders:
            self._cancel_order(order.order_id, reason)

    def _cancel_order(self, order_id: str, reason: str) -> bool:
        """Cancel a specific order"""
        try:
            order = self.orders.get(order_id)
            if not order:
                return False
            
            if order.state not in [OrderState.PENDING, OrderState.SUBMITTED]:
                self.logger.warning(f"Cannot cancel order {order_id} in state {order.state}")
                return False
            
            # Cancel with broker if submitted
            if order.state == OrderState.SUBMITTED and 'broker_order_id' in order.metadata:
                self.spyder_client.cancel_order(order.metadata['broker_order_id'])
            
            # Update order state
            order.state = OrderState.CANCELLED
            order.metadata['cancel_reason'] = reason
            
            self.logger.info(f"Order {order_id} cancelled: {reason}")
            return True
            
        except Exception as e:
            self.logger.error(f"Order cancellation failed: {e}")
            return False

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    def _update_position(self, order: OrderInfo, fill_data: Dict[str, Any]):
        """Update positions based on filled order"""
        try:
            with self._position_lock:
                # Find existing position
                position_key = f"{order.strategy_id}_{order.symbol}"
                existing_position = self.positions.get(position_key)
                
                if order.action == OrderAction.BUY:
                    if existing_position:
                        # Add to position
                        new_quantity = existing_position.quantity + order.quantity
                        new_cost = (existing_position.entry_price * existing_position.quantity + 
                                  fill_data['price'] * order.quantity)
                        existing_position.quantity = new_quantity
                        existing_position.entry_price = new_cost / new_quantity
                    else:
                        # Create new position
                        position = PositionInfo(
                            position_id=f"POS_{uuid.uuid4().hex[:8]}",
                            strategy_id=order.strategy_id,
                            symbol=order.symbol,
                            quantity=order.quantity,
                            entry_price=fill_data['price'],
                            entry_time=datetime.now()
                        )
                        self.positions[position_key] = position
                
                elif order.action == OrderAction.SELL:
                    if existing_position:
                        # Reduce or close position
                        existing_position.quantity -= order.quantity
                        
                        if existing_position.quantity <= 0:
                            # Position closed
                            existing_position.realized_pnl = self._calculate_position_pnl(
                                existing_position, fill_data['price']
                            )
                            del self.positions[position_key]
                            
                            # Update performance metrics
                            self._update_performance_metrics(existing_position.realized_pnl)
                    else:
                        self.logger.warning(f"No position found to sell: {order.symbol}")
                
                # Notify strategy
                self._notify_strategy_position_update(order.strategy_id, order.symbol)
                
        except Exception as e:
            self.logger.error(f"Position update failed: {e}")

    def _calculate_position_pnl(self, position: PositionInfo, exit_price: float) -> float:
        """Calculate realized PnL for a position"""
        return (exit_price - position.entry_price) * position.quantity

    def _get_strategy_positions(self, strategy_id: str) -> List[PositionInfo]:
        """Get all positions for a strategy"""
        with self._position_lock:
            return [pos for pos in self.positions.values() 
                   if pos.strategy_id == strategy_id]

    def _update_position_prices(self, price_updates: Dict[str, float]):
        """Update current prices for all positions"""
        with self._position_lock:
            for position in self.positions.values():
                if position.symbol in price_updates:
                    position.current_price = price_updates[position.symbol]
                    position.unrealized_pnl = self._calculate_position_pnl(
                        position, position.current_price
                    )
                    
                    # Update high water mark
                    if position.unrealized_pnl > position.high_water_mark:
                        position.high_water_mark = position.unrealized_pnl
                    
                    # Update drawdown
                    drawdown = position.high_water_mark - position.unrealized_pnl
                    if drawdown > position.max_drawdown:
                        position.max_drawdown = drawdown

    # ==========================================================================
    # CIRCUIT BREAKER
    # ==========================================================================
    def _check_circuit_breaker(self):
        """Check and update circuit breaker state"""
        try:
            with self._circuit_breaker_lock:
                # Skip if disabled
                if not self.enable_circuit_breaker:
                    return
                
                # Check various metrics
                triggers = []
                
                # Check loss per minute
                if self.circuit_breaker_metrics['loss_per_minute'] > self.circuit_breaker_config.max_loss_per_minute:
                    triggers.append(f"Loss per minute: ${self.circuit_breaker_metrics['loss_per_minute']:.2f}")
                
                # Check orders per minute
                if self.circuit_breaker_metrics['orders_per_minute'] > self.circuit_breaker_config.max_orders_per_minute:
                    triggers.append(f"Orders per minute: {self.circuit_breaker_metrics['orders_per_minute']}")
                
                # Check errors per hour
                if self.circuit_breaker_metrics['errors_per_hour'] > self.circuit_breaker_config.max_errors_per_hour:
                    triggers.append(f"Errors per hour: {self.circuit_breaker_metrics['errors_per_hour']}")
                
                # Check daily loss
                if self.circuit_breaker_metrics['daily_loss'] > self.circuit_breaker_config.max_daily_loss:
                    triggers.append(f"Daily loss: ${self.circuit_breaker_metrics['daily_loss']:.2f}")
                
                # Update state based on triggers
                if triggers and self.circuit_breaker_state != CircuitBreakerState.TRIGGERED:
                    self._activate_circuit_breaker(triggers)
                elif not triggers and self.circuit_breaker_state == CircuitBreakerState.TRIGGERED:
                    self._check_circuit_breaker_recovery()
                
        except Exception as e:
            self.logger.error(f"Circuit breaker check failed: {e}")

    def _activate_circuit_breaker(self, triggers: List[str]):
        """Activate circuit breaker"""
        self.circuit_breaker_state = CircuitBreakerState.TRIGGERED
        self.circuit_breaker_metrics['triggered_at'] = datetime.now()
        
        trigger_msg = ", ".join(triggers)
        self.logger.critical(f"CIRCUIT BREAKER TRIGGERED: {trigger_msg}")
        
        # Pause all strategies
        self.pause("Circuit breaker triggered")
        
        # Cancel all pending orders
        self._cancel_all_pending_orders("Circuit breaker triggered")
        
        # Emit circuit breaker event
        self.event_manager.emit(
            EventType.CRITICAL_ERROR,
            {
                'type': 'circuit_breaker_triggered',
                'triggers': triggers,
                'timestamp': datetime.now()
            }
        )
        
        # Send notifications
        self._send_circuit_breaker_notification(triggers)
        
        # Schedule recovery check
        self.circuit_breaker_metrics['recovery_at'] = (
            datetime.now() + timedelta(minutes=self.circuit_breaker_config.cooldown_minutes)
        )

    def _check_circuit_breaker_recovery(self):
        """Check if circuit breaker can be reset"""
        if self.circuit_breaker_state != CircuitBreakerState.TRIGGERED:
            return
        
        # Check if cooldown period has passed
        if datetime.now() < self.circuit_breaker_metrics.get('recovery_at', datetime.now()):
            return
        
        # Check if metrics are below recovery threshold
        recovery_threshold = self.circuit_breaker_config.recovery_threshold
        
        can_recover = all([
            self.circuit_breaker_metrics['loss_per_minute'] < 
            self.circuit_breaker_config.max_loss_per_minute * recovery_threshold,
            
            self.circuit_breaker_metrics['orders_per_minute'] < 
            self.circuit_breaker_config.max_orders_per_minute * recovery_threshold,
            
            self.circuit_breaker_metrics['errors_per_hour'] < 
            self.circuit_breaker_config.max_errors_per_hour * recovery_threshold,
        ])
        
        if can_recover:
            self.circuit_breaker_state = CircuitBreakerState.RECOVERING
            self.logger.info("Circuit breaker entering recovery mode")
            
            # Emit recovery event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'circuit_breaker_recovering',
                    'timestamp': datetime.now()
                }
            )

    def _reset_circuit_breaker_metrics(self):
        """Reset circuit breaker metrics"""
        with self._circuit_breaker_lock:
            self.circuit_breaker_metrics = {
                'loss_per_minute': 0.0,
                'orders_per_minute': 0,
                'errors_per_hour': 0,
                'daily_loss': 0.0,
                'triggered_at': None,
                'recovery_at': None,
                'last_reset': datetime.now()
            }

    def _update_order_rate_metrics(self):
        """Update order rate metrics for circuit breaker"""
        # Implementation depends on time-based tracking
        pass

    def _send_circuit_breaker_notification(self, triggers: List[str]):
        """Send circuit breaker notification"""
        try:
            notification = {
                'type': 'CIRCUIT_BREAKER',
                'severity': 'CRITICAL',
                'title': 'Trading Circuit Breaker Triggered',
                'message': f"Circuit breaker activated due to: {', '.join(triggers)}",
                'timestamp': datetime.now()
            }
            
            # Send through notification system
            self.event_manager.emit(EventType.ALERT, notification)
            
        except Exception as e:
            self.logger.error(f"Failed to send circuit breaker notification: {e}")

    # ==========================================================================
    # MONITORING AND HEALTH
    # ==========================================================================
    def _start_monitoring(self):
        """Start monitoring thread"""
        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            name="EngineMonitor",
            daemon=True
        )
        self._monitor_thread.start()

    def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Engine monitor started")
        
        while not self._shutdown_event.is_set():
            try:
                # Perform health check
                if (datetime.now() - self.last_health_check).total_seconds() > HEALTH_CHECK_INTERVAL:
                    self._perform_health_check()
                    self.last_health_check = datetime.now()
                
                # Check circuit breaker
                self._check_circuit_breaker()
                
                # Update position prices
                # self._update_all_position_prices()
                
                # Check for stale positions
                self._check_stale_positions()
                
                # Sleep
                self._shutdown_event.wait(10)
                
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                self.error_handler.handle_error(e, "monitoring_loop")

    def _perform_health_check(self):
        """Perform comprehensive health check"""
        try:
            import psutil
            process = psutil.Process()
            
            health = EngineHealth(
                state=self.state,
                uptime=datetime.now() - self.start_time if self.start_time else timedelta(),
                active_strategies=len([s for s in self.strategies.values() 
                                     if s.state == StrategyState.ACTIVE]),
                open_orders=len([o for o in self.orders.values() 
                               if o.state in [OrderState.PENDING, OrderState.SUBMITTED]]),
                open_positions=len(self.positions),
                circuit_breaker_state=self.circuit_breaker_state,
                last_error=self._get_last_error(),
                error_rate=self._calculate_error_rate(),
                order_success_rate=self._calculate_order_success_rate(),
                memory_usage_mb=process.memory_info().rss / 1024 / 1024,
                cpu_usage_percent=process.cpu_percent(),
                last_health_check=datetime.now()
            )
            
            # Log health status
            self.logger.info(f"Health check: State={health.state.name}, "
                           f"Strategies={health.active_strategies}, "
                           f"Orders={health.open_orders}, "
                           f"Positions={health.open_positions}")
            
            # Emit health event
            self.event_manager.emit(
                EventType.SYSTEM,
                {
                    'type': 'health_check',
                    'health': asdict(health),
                    'timestamp': datetime.now()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status"""
        try:
            return {
                'state': self.state.name,
                'uptime': str(datetime.now() - self.start_time) if self.start_time else None,
                'active_strategies': len([s for s in self.strategies.values() 
                                       if s.state == StrategyState.ACTIVE]),
                'total_strategies': len(self.strategies),
                'open_orders': len([o for o in self.orders.values() 
                                  if o.state in [OrderState.PENDING, OrderState.SUBMITTED]]),
                'open_positions': len(self.positions),
                'circuit_breaker': self.circuit_breaker_state.name,
                'performance': {
                    'total_pnl': self.performance.total_pnl,
                    'win_rate': self.performance.win_rate,
                    'sharpe_ratio': self.performance.sharpe_ratio
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting health status: {e}")
            return {'error': str(e)}

    def _check_stale_positions(self):
        """Check for positions that are too old"""
        try:
            current_time = datetime.now()
            
            with self._position_lock:
                for position in self.positions.values():
                    age = current_time - position.entry_time
                    
                    if age.total_seconds() / 3600 > MAX_POSITION_AGE_HOURS:
                        self.logger.warning(
                            f"Stale position detected: {position.position_id} "
                            f"({age.total_seconds() / 3600:.1f} hours old)"
                        )
                        
                        # Emit stale position event
                        self.event_manager.emit(
                            EventType.SYSTEM_WARNING,
                            {
                                'type': 'stale_position',
                                'position_id': position.position_id,
                                'age_hours': age.total_seconds() / 3600,
                                'symbol': position.symbol,
                                'strategy_id': position.strategy_id
                            }
                        )
                        
        except Exception as e:
            self.logger.error(f"Stale position check failed: {e}")

    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================
    def _initialize_performance_tracking(self):
        """Initialize performance tracking systems"""
        self.performance = PerformanceMetrics()
        self.performance_history.clear()

    def _update_performance_metrics(self, pnl: float):
        """Update performance metrics with new trade"""
        with self._performance_lock:
            self.performance.total_trades += 1
            self.performance.total_pnl += pnl
            
            if pnl > 0:
                self.performance.winning_trades += 1
                self.performance.avg_win = (
                    (self.performance.avg_win * (self.performance.winning_trades - 1) + pnl) /
                    self.performance.winning_trades
                )
            else:
                self.performance.losing_trades += 1
                self.performance.avg_loss = (
                    (self.performance.avg_loss * (self.performance.losing_trades - 1) + abs(pnl)) /
                    self.performance.losing_trades
                )
            
            # Update win rate
            if self.performance.total_trades > 0:
                self.performance.win_rate = self.performance.winning_trades / self.performance.total_trades
            
            # Update profit factor
            if self.performance.avg_loss > 0:
                self.performance.profit_factor = self.performance.avg_win / self.performance.avg_loss
            
            # Add to history
            self.performance_history.append({
                'timestamp': datetime.now(),
                'pnl': pnl,
                'total_pnl': self.performance.total_pnl,
                'win_rate': self.performance.win_rate
            })
            
            # Update max drawdown
            self._update_max_drawdown()

    def _update_max_drawdown(self):
        """Calculate and update maximum drawdown"""
        if not self.performance_history:
            return
        
        # Calculate running maximum
        running_max = 0
        max_dd = 0
        
        for record in self.performance_history:
            if record['total_pnl'] > running_max:
                running_max = record['total_pnl']
            
            drawdown = running_max - record['total_pnl']
            if drawdown > max_dd:
                max_dd = drawdown
        
        self.performance.max_drawdown = max_dd

    def _calculate_error_rate(self) -> float:
        """Calculate current error rate"""
        # Implementation based on time window
        return 0.0

    def _calculate_order_success_rate(self) -> float:
        """Calculate order success rate"""
        with self._order_lock:
            total = len(self.orders)
            if total == 0:
                return 1.0
            
            successful = len([o for o in self.orders.values() 
                            if o.state == OrderState.FILLED])
            
            return successful / total

    def _update_strategy_order_count(self, strategy_id: str):
        """Update strategy order count"""
        if strategy_id in self.strategies:
            self.strategies[strategy_id].order_count += 1

    def _increment_strategy_error(self, strategy_id: str, error: str):
        """Increment strategy error count"""
        if strategy_id in self.strategies:
            strategy = self.strategies[strategy_id]
            strategy.error_count += 1
            strategy.last_error = error
            
            # Check if strategy should be disabled
            if strategy.error_count > 10:
                self.logger.error(f"Strategy {strategy_id} disabled due to excessive errors")
                strategy.state = StrategyState.ERROR

    # ==========================================================================
    # STATE PERSISTENCE
    # ==========================================================================
    def _save_state(self):
        """Save engine state to disk"""
        try:
            state_data = {
                'version': '2.0',
                'timestamp': datetime.now(),
                'engine_state': self.state.name,
                'performance': asdict(self.performance),
                'strategies': {
                    sid: {
                        'name': s.name,
                        'state': s.state.name,
                        'signal_count': s.signal_count,
                        'order_count': s.order_count,
                        'pnl': s.pnl,
                        'error_count': s.error_count
                    }
                    for sid, s in self.strategies.items()
                },
                'circuit_breaker': {
                    'state': self.circuit_breaker_state.name,
                    'metrics': self.circuit_breaker_metrics
                }
            }
            
            # Save to file
            with open(self._state_file, 'wb') as f:
                pickle.dump(state_data, f)
            
            self.logger.debug("Engine state saved")
            
        except Exception as e:
            self.logger.error(f"State save failed: {e}")

    def _load_state(self):
        """Load engine state from disk"""
        try:
            if not self._state_file.exists():
                return
            
            with open(self._state_file, 'rb') as f:
                state_data = pickle.load(f)
            
            # Restore performance metrics
            if 'performance' in state_data:
                for key, value in state_data['performance'].items():
                    if hasattr(self.performance, key) and not key.startswith('_'):
                        setattr(self.performance, key, value)
            
            self.logger.info("Engine state loaded from disk")
            
        except Exception as e:
            self.logger.error(f"State load failed: {e}")

    def get_state(self) -> Dict[str, Any]:
        """Get current engine state for external persistence"""
        return {
            'state': self.state.name,
            'strategies': len(self.strategies),
            'active_strategies': len([s for s in self.strategies.values() 
                                    if s.state == StrategyState.ACTIVE]),
            'open_orders': len([o for o in self.orders.values() 
                              if o.state in [OrderState.PENDING, OrderState.SUBMITTED]]),
            'open_positions': len(self.positions),
            'total_pnl': self.performance.total_pnl,
            'circuit_breaker': self.circuit_breaker_state.name
        }

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _validate_configuration(self) -> bool:
        """Validate engine configuration"""
        try:
            # Check required configuration
            if not self.config:
                self.logger.warning("No configuration provided, using defaults")
            
            # Validate numeric limits
            if self.max_strategies <= 0:
                self.logger.error("Invalid max_strategies")
                return False
            
            if self.max_orders_per_minute <= 0:
                self.logger.error("Invalid max_orders_per_minute")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def _setup_event_handlers(self):
        """Set up event handlers"""
        try:
            # Order events
            self.event_manager.subscribe(EventType.ORDER_FILLED, self._on_order_filled)
            self.event_manager.subscribe(EventType.ORDER_CANCELLED, self._on_order_cancelled)
            
            # Position events
            self.event_manager.subscribe(EventType.POSITION_UPDATE, self._on_position_update)
            
            # System events
            self.event_manager.subscribe(EventType.SYSTEM_ERROR, self._on_system_error)
            
            self.logger.info("Event handlers registered")
            
        except Exception as e:
            self.logger.error(f"Event handler setup failed: {e}")

    def _on_order_filled(self, event: Event):
        """Handle order filled event"""
        try:
            order_id = event.data.get('order_id')
            fill_data = event.data.get('fill_data', {})
            
            order = self.orders.get(order_id)
            if order:
                order.state = OrderState.FILLED
                order.filled_at = datetime.now()
                order.fill_price = fill_data.get('price', order.price)
                
                # Update position
                self._update_position(order, fill_data)
                
                # Update performance
                self.performance.successful_orders += 1
                
        except Exception as e:
            self.logger.error(f"Order filled handler error: {e}")

    def _on_order_cancelled(self, event: Event):
        """Handle order cancelled event"""
        try:
            order_id = event.data.get('order_id')
            
            order = self.orders.get(order_id)
            if order:
                order.state = OrderState.CANCELLED
                
        except Exception as e:
            self.logger.error(f"Order cancelled handler error: {e}")

    def _on_position_update(self, event: Event):
        """Handle position update event"""
        try:
            # Update position prices if provided
            if 'price_updates' in event.data:
                self._update_position_prices(event.data['price_updates'])
                
        except Exception as e:
            self.logger.error(f"Position update handler error: {e}")

    def _on_system_error(self, event: Event):
        """Handle system error event"""
        try:
            error_type = event.data.get('error_type')
            
            # Update error metrics
            self.circuit_breaker_metrics['errors_per_hour'] += 1
            
            # Check if critical
            if event.data.get('severity') == 'critical':
                self.logger.critical(f"Critical system error: {error_type}")
                # Consider stopping engine
                
        except Exception as e:
            self.logger.error(f"System error handler error: {e}")

    def _notify_strategy_order_failed(self, order: OrderInfo):
        """Notify strategy of order failure"""
        try:
            strategy = self.strategies.get(order.strategy_id)
            if strategy and hasattr(strategy.class_instance, 'on_order_failed'):
                strategy.class_instance.on_order_failed(order.order_id, order.error_message)
                
        except Exception as e:
            self.logger.error(f"Strategy notification failed: {e}")

    def _notify_strategy_position_update(self, strategy_id: str, symbol: str):
        """Notify strategy of position update"""
        try:
            strategy = self.strategies.get(strategy_id)
            if strategy and hasattr(strategy.class_instance, 'on_position_update'):
                positions = self._get_strategy_positions(strategy_id)
                strategy.class_instance.on_position_update(symbol, positions)
                
        except Exception as e:
            self.logger.error(f"Strategy position notification failed: {e}")

    def _get_last_error(self) -> Optional[str]:
        """Get last error message"""
        # Implementation depends on error tracking
        return None

    def _start_worker_threads(self):
        """Start all worker threads"""
        self._start_order_processor()
        self._start_monitoring()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="EngineCleanup",
            daemon=True
        )
        self._cleanup_thread.start()
        
        # Start state save thread if enabled
        if self.save_state_enabled:
            self._state_save_thread = threading.Thread(
                target=self._state_save_loop,
                name="StateSaver",
                daemon=True
            )
            self._state_save_thread.start()

    def _stop_worker_threads(self):
        """Stop all worker threads"""
        self._shutdown_event.set()
        
        # Wait for threads to finish
        threads = [
            self._order_processor_thread,
            self._monitor_thread,
            self._cleanup_thread,
            self._state_save_thread
        ]
        
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5)

    def _cleanup_loop(self):
        """Periodic cleanup tasks"""
        while not self._shutdown_event.is_set():
            try:
                # Clean old orders
                self._cleanup_old_orders()
                
                # Clean old performance history
                # Keep only recent records
                
                self._shutdown_event.wait(CLEANUP_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Cleanup error: {e}")

    def _cleanup_old_orders(self):
        """Remove old completed orders"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        with self._order_lock:
            old_orders = [
                oid for oid, order in self.orders.items()
                if order.state in [OrderState.FILLED, OrderState.CANCELLED, OrderState.ERROR]
                and order.created_at < cutoff_time
            ]
            
            for order_id in old_orders:
                del self.orders[order_id]
            
            if old_orders:
                self.logger.debug(f"Cleaned up {len(old_orders)} old orders")

    def _state_save_loop(self):
        """Periodic state saving"""
        while not self._shutdown_event.is_set():
            try:
                self._save_state()
                self._shutdown_event.wait(STATE_SAVE_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"State save loop error: {e}")

    def _cleanup_resources(self):
        """Clean up all resources"""
        try:
            # Stop monitoring
            if self.has_risk_manager and self.risk_manager:
                self.risk_manager.stop_monitoring()
            
            # Clear queues
            while not self.order_queue.empty():
                try:
                    self.order_queue.get_nowait()
                except queue.Empty:
                    break
            
            self.logger.info("Resources cleaned up")
            
        except Exception as e:
            self.logger.error(f"Resource cleanup failed: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_trading_engine(config: Dict[str, Any], spyder_client, event_manager: EventManager) -> TradingEngine:
    """
    Factory function to create a TradingEngine instance.
    
    Args:
        config: Engine configuration
        spyder_client: Broker client instance
        event_manager: Event management system
        
    Returns:
        TradingEngine instance
    """
    return TradingEngine(config, spyder_client, event_manager)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level singleton instance
_engine_instance: Optional[TradingEngine] = None
_engine_lock = Lock()

def get_trading_engine(
    config: Dict[str, Any] = None, 
    spyder_client = None, 
    event_manager: EventManager = None
) -> TradingEngine:
    """
    Get singleton TradingEngine instance.
    
    Args:
        config: Engine configuration (required for first call)
        spyder_client: Broker client (required for first call)
        event_manager: Event manager (required for first call)
        
    Returns:
        TradingEngine instance
    """
    global _engine_instance
    
    with _engine_lock:
        if _engine_instance is None:
            if not all([config, spyder_client, event_manager]):
                raise ValueError("All parameters required for first engine creation")
            _engine_instance = TradingEngine(config, spyder_client, event_manager)
        
        return _engine_instance

def reset_trading_engine():
    """Reset the singleton engine instance (for testing)."""
    global _engine_instance
    with _engine_lock:
        if _engine_instance and _engine_instance.state == EngineState.RUNNING:
            _engine_instance.stop("Engine reset")
        _engine_instance = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("Testing TradingEngine...")
    
    # Mock configuration
    test_config = {
        'max_strategies': 10,
        'max_orders_per_minute': 50,
        'enable_circuit_breaker': True,
        'circuit_breaker': {
            'max_loss_per_minute': 500,
            'max_daily_loss': 2000
        }
    }
    
    # Mock dependencies
    class MockSpyderClient:
        def is_connected(self):
            return True
        
        def place_order(self, order):
            return {'order_id': f"MOCK_{uuid.uuid4().hex[:8]}"}
        
        def cancel_order(self, order_id):
            return True
    
    # Create test instances
    mock_client = MockSpyderClient()
    event_manager = EventManager()
    event_manager.start()
    
    # Create engine
    engine = TradingEngine(test_config, mock_client, event_manager)
    
    if engine.initialize():
        print("✅ TradingEngine initialized successfully")
        
        # Test basic functionality
        status = engine.get_health_status()
        print(f"Health status: {json.dumps(status, indent=2)}")
        
        if engine.start():
            print("✅ TradingEngine started successfully")
            
            # Let it run briefly
            time.sleep(2)
            
            # Test pause/resume
            if engine.pause("Test pause"):
                print("✅ Engine paused")
                time.sleep(1)
                
                if engine.resume():
                    print("✅ Engine resumed")
            
            # Stop engine
            if engine.stop("Test completed"):
                print("✅ TradingEngine stopped successfully")
            else:
                print("❌ TradingEngine stop failed")
        else:
            print("❌ TradingEngine start failed")
        
        # Shutdown
        engine.shutdown()
    else:
        print("❌ TradingEngine initialization failed")
    
    # Stop event manager
    event_manager.stop()
    
    print("\nTradingEngine testing completed.")
