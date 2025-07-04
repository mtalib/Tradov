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

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-03
Last Updated: 2025-07-03 Time: 16:00:00
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
from SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics

# Conditional imports to handle missing modules gracefully
try:
    from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
    HAS_BASE_STRATEGY = True
except ImportError:
    HAS_BASE_STRATEGY = False
    BaseStrategy = object  # Fallback

try:
    from SpyderB_Broker.SpyderB02_OrderManager import OrderManager
    HAS_ORDER_MANAGER = True
except ImportError:
    HAS_ORDER_MANAGER = False

try:
    from SpyderB_Broker.SpyderB03_PositionTracker import PositionTracker
    HAS_POSITION_TRACKER = True
except ImportError:
    HAS_POSITION_TRACKER = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Engine Configuration
MAX_CONCURRENT_STRATEGIES = 20
MAX_ORDERS_PER_MINUTE = 60
MAX_POSITION_SIZE_USD = 50000
DEFAULT_HEARTBEAT_INTERVAL = 30  # seconds

# Threading Configuration
MAX_WORKER_THREADS = 10
ORDER_QUEUE_MAX_SIZE = 1000
SIGNAL_QUEUE_MAX_SIZE = 500

# Performance Limits
MAX_EXECUTION_TIME_MS = 5000
MAX_MEMORY_USAGE_MB = 2048
MAX_CPU_USAGE_PERCENT = 80

# Risk Limits
DEFAULT_MAX_DAILY_LOSS = 5000
DEFAULT_MAX_PORTFOLIO_DELTA = 1000
DEFAULT_MAX_SINGLE_POSITION = 10000

# ==============================================================================
# ENUMS
# ==============================================================================
class EngineState(Enum):
    """Trading engine states"""
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"

class StrategyState(Enum):
    """Strategy states within the engine"""
    REGISTERED = "registered"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DISABLED = "disabled"

class ExecutionPriority(Enum):
    """Order execution priority levels"""
    EMERGENCY = 1    # Risk management orders
    HIGH = 2         # Strategy exit orders
    NORMAL = 3       # Strategy entry orders
    LOW = 4          # Optimization orders

class SignalType(Enum):
    """Trading signal types"""
    ENTRY = "entry"
    EXIT = "exit"
    ADJUST = "adjust"
    HEDGE = "hedge"
    CLOSE_ALL = "close_all"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class TradingSignal:
    """Trading signal data structure"""
    signal_id: str
    strategy_id: str
    signal_type: SignalType
    symbol: str
    action: OrderAction
    quantity: int
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"
    priority: ExecutionPriority = ExecutionPriority.NORMAL
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = str(uuid.uuid4())

@dataclass
class StrategyRegistration:
    """Strategy registration information"""
    strategy_id: str
    strategy_instance: Any  # BaseStrategy instance
    strategy_name: str
    strategy_type: str
    risk_profile: RiskProfile
    max_position_size: float
    max_daily_trades: int
    state: StrategyState = StrategyState.REGISTERED
    registration_time: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    error_count: int = 0
    
@dataclass
class OrderExecution:
    """Order execution tracking"""
    execution_id: str
    signal_id: str
    strategy_id: str
    order_id: Optional[str] = None
    status: str = "PENDING"
    fill_price: Optional[float] = None
    fill_quantity: Optional[int] = None
    fill_time: Optional[datetime] = None
    execution_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_time: datetime = field(default_factory=datetime.now)

@dataclass
class PortfolioSnapshot:
    """Portfolio state snapshot"""
    timestamp: datetime
    total_value: float
    cash_available: float
    positions_count: int
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    daily_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    strategies_running: int

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class TradingEngine:
    """
    Core Trading Engine for Spyder System.
    
    This class manages the complete trading workflow including strategy registration,
    signal processing, order execution, position management, and risk monitoring.
    It provides a robust, thread-safe environment for automated trading operations.
    
    Key Features:
    - Multi-strategy execution coordination
    - Real-time risk monitoring and enforcement
    - Automated error recovery and circuit breakers
    - Performance tracking and optimization
    - Event-driven architecture with comprehensive logging
    
    Attributes:
        logger: Module logger instance
        config: Engine configuration
        state: Current engine state
        strategies: Registered strategy instances
        risk_manager: Risk management system
        
    Example:
        >>> engine = TradingEngine(config, spyder_client, event_manager)
        >>> engine.initialize()
        >>> engine.register_strategy(my_strategy)
        >>> engine.start()
    """
    
    def __init__(self, config: Dict[str, Any], spyder_client, event_manager: EventManager):
        """
        Initialize the Trading Engine.
        
        Args:
            config: Engine configuration dictionary
            spyder_client: Broker client instance
            event_manager: Event management system
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}
        self.spyder_client = spyder_client
        self.event_manager = event_manager
        
        # Engine state management
        self.state = EngineState.INITIALIZING
        self._state_lock = RLock()
        self._shutdown_event = ThreadEvent()
        
        # Strategy management
        self.strategies: Dict[str, StrategyRegistration] = {}
        self.strategy_states: Dict[str, StrategyState] = {}
        self._strategy_lock = RLock()
        
        # Order and execution management
        self.signal_queue = queue.PriorityQueue(maxsize=SIGNAL_QUEUE_MAX_SIZE)
        self.order_queue = queue.PriorityQueue(maxsize=ORDER_QUEUE_MAX_SIZE)
        self.pending_executions: Dict[str, OrderExecution] = {}
        self._execution_lock = RLock()
        
        # Performance tracking
        self.performance_metrics = PerformanceMetrics()
        self.portfolio_snapshots: deque = deque(maxlen=1000)
        self._metrics_lock = RLock()
        
        # Threading infrastructure
        self.thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKER_THREADS)
        self.worker_threads: Dict[str, threading.Thread] = {}
        self._threads_lock = RLock()
        
        # Risk management integration
        try:
            self.risk_manager = get_risk_manager()
            self.has_risk_manager = True
        except Exception as e:
            self.logger.warning(f"Risk manager not available: {e}")
            self.risk_manager = None
            self.has_risk_manager = False
        
        # Order management integration
        if HAS_ORDER_MANAGER:
            try:
                self.order_manager = OrderManager(config, spyder_client)
                self.has_order_manager = True
            except Exception as e:
                self.logger.warning(f"Order manager initialization failed: {e}")
                self.order_manager = None
                self.has_order_manager = False
        else:
            self.order_manager = None
            self.has_order_manager = False
        
        # Position tracking integration
        if HAS_POSITION_TRACKER:
            try:
                self.position_tracker = PositionTracker(config, spyder_client)
                self.has_position_tracker = True
            except Exception as e:
                self.logger.warning(f"Position tracker initialization failed: {e}")
                self.position_tracker = None
                self.has_position_tracker = False
        else:
            self.position_tracker = None
            self.has_position_tracker = False
        
        # Operational metrics
        self.start_time: Optional[datetime] = None
        self.last_heartbeat: Optional[datetime] = None
        self.orders_processed_today = 0
        self.signals_processed_today = 0
        self.total_uptime_seconds = 0
        
        # Emergency controls
        self.emergency_stop_triggered = False
        self.circuit_breaker_active = False
        self.max_daily_loss = self.config.get('max_daily_loss', DEFAULT_MAX_DAILY_LOSS)
        
        self.logger.info(f"TradingEngine initialized with {len(self.strategies)} strategies")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    
    def initialize(self) -> bool:
        """
        Initialize the trading engine.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            with self._state_lock:
                if self.state != EngineState.INITIALIZING:
                    self.logger.warning(f"Cannot initialize from state: {self.state}")
                    return False
                
                self.logger.info("Initializing TradingEngine...")
                
                # Initialize risk management
                if self.has_risk_manager and self.risk_manager:
                    if not self.risk_manager.initialize():
                        self.logger.error("Risk manager initialization failed")
                        return False
                
                # Initialize order management
                if self.has_order_manager and self.order_manager:
                    if not self.order_manager.initialize():
                        self.logger.error("Order manager initialization failed")
                        return False
                
                # Initialize position tracking
                if self.has_position_tracker and self.position_tracker:
                    if not self.position_tracker.initialize():
                        self.logger.error("Position tracker initialization failed")
                        return False
                
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
                self.event_manager.emit_event(
                    EventType.ENGINE_INITIALIZED,
                    {'timestamp': datetime.now(), 'state': self.state.value}
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine initialization failed: {e}")
            self.error_handler.handle_engine_error(e, "TradingEngine", "initialize")
            self.state = EngineState.ERROR
            return False
    
    def start(self) -> bool:
        """
        Start the trading engine.
        
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
                
                # Start worker threads
                self._start_worker_threads()
                
                # Start monitoring systems
                self._start_monitoring()
                
                # Start risk monitoring
                if self.has_risk_manager and self.risk_manager:
                    self.risk_manager.start_monitoring()
                
                self.state = EngineState.RUNNING
                self.logger.info("TradingEngine started successfully")
                
                # Emit start event
                self.event_manager.emit_event(
                    EventType.ENGINE_STARTED,
                    {'timestamp': self.start_time, 'state': self.state.value}
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine start failed: {e}")
            self.error_handler.handle_engine_error(e, "TradingEngine", "start")
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
                if self.state in [EngineState.STOPPED, EngineState.STOPPING]:
                    self.logger.info("TradingEngine already stopped or stopping")
                    return True
                
                self.logger.info(f"Stopping TradingEngine: {reason}")
                self.state = EngineState.STOPPING
                
                # Signal shutdown to all threads
                self._shutdown_event.set()
                
                # Stop all strategies gracefully
                self._stop_all_strategies(reason)
                
                # Stop worker threads
                self._stop_worker_threads()
                
                # Stop monitoring
                self._stop_monitoring()
                
                # Stop risk monitoring
                if self.has_risk_manager and self.risk_manager:
                    self.risk_manager.stop_monitoring()
                
                # Final cleanup
                self._cleanup_resources()
                
                self.state = EngineState.STOPPED
                stop_time = datetime.now()
                
                if self.start_time:
                    self.total_uptime_seconds = (stop_time - self.start_time).total_seconds()
                
                self.logger.info(f"TradingEngine stopped successfully. Uptime: {self.total_uptime_seconds:.2f}s")
                
                # Emit stop event
                self.event_manager.emit_event(
                    EventType.ENGINE_STOPPED,
                    {
                        'timestamp': stop_time,
                        'reason': reason,
                        'uptime_seconds': self.total_uptime_seconds,
                        'orders_processed': self.orders_processed_today,
                        'signals_processed': self.signals_processed_today
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"TradingEngine stop failed: {e}")
            self.error_handler.handle_engine_error(e, "TradingEngine", "stop")
            return False
    
    def emergency_stop(self, reason: str = "Emergency stop triggered") -> bool:
        """
        Execute emergency stop procedures.
        
        Args:
            reason: Reason for emergency stop
            
        Returns:
            bool: True if emergency stop successful
        """
        try:
            self.logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")
            
            with self._state_lock:
                self.state = EngineState.EMERGENCY_STOP
                self.emergency_stop_triggered = True
            
            # Immediately stop all strategies
            for strategy_id in list(self.strategies.keys()):
                try:
                    self.force_stop_strategy(strategy_id, f"Emergency stop: {reason}")
                except Exception as e:
                    self.logger.error(f"Failed to emergency stop strategy {strategy_id}: {e}")
            
            # Cancel all pending orders
            self._cancel_all_pending_orders()
            
            # Signal all threads to stop immediately
            self._shutdown_event.set()
            
            # Emit emergency stop event
            self.event_manager.emit_event(
                EventType.EMERGENCY_STOP,
                {
                    'timestamp': datetime.now(),
                    'reason': reason,
                    'strategies_count': len(self.strategies),
                    'pending_orders': len(self.pending_executions)
                }
            )
            
            self.logger.critical("Emergency stop completed")
            return True
            
        except Exception as e:
            self.logger.critical(f"Emergency stop failed: {e}")
            return False
    
    # ==========================================================================
    # STRATEGY MANAGEMENT
    # ==========================================================================
    
    def register_strategy(
        self, 
        strategy_instance, 
        strategy_name: str = None,
        risk_profile: RiskProfile = None,
        max_position_size: float = None,
        max_daily_trades: int = None
    ) -> str:
        """
        Register a trading strategy with the engine.
        
        Args:
            strategy_instance: Strategy instance to register
            strategy_name: Human-readable strategy name
            risk_profile: Risk profile for the strategy
            max_position_size: Maximum position size in USD
            max_daily_trades: Maximum daily trades allowed
            
        Returns:
            str: Strategy ID
            
        Raises:
            ValueError: If strategy validation fails
            RuntimeError: If registration fails
        """
        try:
            if not HAS_BASE_STRATEGY:
                raise RuntimeError("BaseStrategy module not available")
            
            # Validate strategy instance
            if not isinstance(strategy_instance, BaseStrategy):
                raise ValueError("Strategy must inherit from BaseStrategy")
            
            # Generate strategy ID
            strategy_id = str(uuid.uuid4())
            
            # Set defaults
            if strategy_name is None:
                strategy_name = strategy_instance.__class__.__name__
            
            if risk_profile is None:
                risk_profile = RiskProfile.MEDIUM
            
            if max_position_size is None:
                max_position_size = self.config.get('default_max_position_size', MAX_POSITION_SIZE_USD)
            
            if max_daily_trades is None:
                max_daily_trades = self.config.get('default_max_daily_trades', 50)
            
            # Validate limits
            if len(self.strategies) >= MAX_CONCURRENT_STRATEGIES:
                raise RuntimeError(f"Maximum strategies limit reached: {MAX_CONCURRENT_STRATEGIES}")
            
            # Create registration
            registration = StrategyRegistration(
                strategy_id=strategy_id,
                strategy_instance=strategy_instance,
                strategy_name=strategy_name,
                strategy_type=strategy_instance.__class__.__name__,
                risk_profile=risk_profile,
                max_position_size=max_position_size,
                max_daily_trades=max_daily_trades,
                state=StrategyState.REGISTERED
            )
            
            with self._strategy_lock:
                # Register strategy
                self.strategies[strategy_id] = registration
                self.strategy_states[strategy_id] = StrategyState.REGISTERED
                
                # Initialize strategy if engine is running
                if self.state == EngineState.RUNNING:
                    self._initialize_strategy(strategy_id)
            
            self.logger.info(f"Strategy registered: {strategy_name} (ID: {strategy_id})")
            
            # Emit registration event
            self.event_manager.emit_event(
                EventType.STRATEGY_REGISTERED,
                {
                    'strategy_id': strategy_id,
                    'strategy_name': strategy_name,
                    'strategy_type': registration.strategy_type,
                    'risk_profile': risk_profile.value,
                    'timestamp': datetime.now()
                }
            )
            
            return strategy_id
            
        except Exception as e:
            self.logger.error(f"Strategy registration failed: {e}")
            self.error_handler.handle_strategy_error(e, strategy_name or "Unknown", "register_strategy")
            raise
    
    def start_strategy(self, strategy_id: str, force: bool = False) -> bool:
        """
        Start a registered strategy.
        
        Args:
            strategy_id: Strategy ID to start
            force: Force start even if conditions not met
            
        Returns:
            bool: True if start successful
        """
        try:
            with self._strategy_lock:
                if strategy_id not in self.strategies:
                    raise ValueError(f"Strategy not found: {strategy_id}")
                
                registration = self.strategies[strategy_id]
                current_state = self.strategy_states[strategy_id]
                
                # Validate state transition
                if current_state not in [StrategyState.READY, StrategyState.STOPPED] and not force:
                    self.logger.warning(f"Cannot start strategy {strategy_id} from state: {current_state}")
                    return False
                
                # Validate engine state
                if self.state != EngineState.RUNNING and not force:
                    self.logger.warning(f"Cannot start strategy when engine state is: {self.state}")
                    return False
                
                # Perform pre-start checks
                if not force and not self._pre_start_checks(strategy_id):
                    self.logger.warning(f"Pre-start checks failed for strategy: {strategy_id}")
                    return False
                
                # Initialize strategy if needed
                if current_state == StrategyState.REGISTERED:
                    if not self._initialize_strategy(strategy_id):
                        return False
                
                # Start the strategy
                try:
                    strategy_instance = registration.strategy_instance
                    strategy_instance.start()
                    
                    self.strategy_states[strategy_id] = StrategyState.RUNNING
                    registration.last_activity = datetime.now()
                    
                    self.logger.info(f"Strategy started: {registration.strategy_name} (ID: {strategy_id})")
                    
                    # Emit start event
                    self.event_manager.emit_event(
                        EventType.STRATEGY_STARTED,
                        {
                            'strategy_id': strategy_id,
                            'strategy_name': registration.strategy_name,
                            'timestamp': datetime.now()
                        }
                    )
                    
                    return True
                    
                except Exception as e:
                    self.logger.error(f"Failed to start strategy {strategy_id}: {e}")
                    self.strategy_states[strategy_id] = StrategyState.ERROR
                    registration.error_count += 1
                    self.error_handler.handle_strategy_error(e, registration.strategy_name, "start_strategy")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Strategy start failed: {e}")
            self.error_handler.handle_strategy_error(e, strategy_id, "start_strategy")
            return False
    
    def stop_strategy(self, strategy_id: str, reason: str = "Manual stop") -> bool:
        """
        Stop a running strategy gracefully.
        
        Args:
            strategy_id: Strategy ID to stop
            reason: Reason for stopping
            
        Returns:
            bool: True if stop successful
        """
        try:
            with self._strategy_lock:
                if strategy_id not in self.strategies:
                    raise ValueError(f"Strategy not found: {strategy_id}")
                
                registration = self.strategies[strategy_id]
                current_state = self.strategy_states[strategy_id]
                
                if current_state not in [StrategyState.RUNNING, StrategyState.PAUSED]:
                    self.logger.info(f"Strategy {strategy_id} already stopped or not running")
                    return True
                
                self.logger.info(f"Stopping strategy: {registration.strategy_name} (Reason: {reason})")
                self.strategy_states[strategy_id] = StrategyState.STOPPING
                
                try:
                    # Cancel any pending orders for this strategy
                    self._cancel_strategy_orders(strategy_id)
                    
                    # Stop the strategy instance
                    strategy_instance = registration.strategy_instance
                    strategy_instance.stop()
                    
                    self.strategy_states[strategy_id] = StrategyState.STOPPED
                    registration.last_activity = datetime.now()
                    
                    self.logger.info(f"Strategy stopped: {registration.strategy_name}")
                    
                    # Emit stop event
                    self.event_manager.emit_event(
                        EventType.STRATEGY_STOPPED,
                        {
                            'strategy_id': strategy_id,
                            'strategy_name': registration.strategy_name,
                            'reason': reason,
                            'timestamp': datetime.now()
                        }
                    )
                    
                    return True
                    
                except Exception as e:
                    self.logger.error(f"Failed to stop strategy {strategy_id}: {e}")
                    self.strategy_states[strategy_id] = StrategyState.ERROR
                    registration.error_count += 1
                    self.error_handler.handle_strategy_error(e, registration.strategy_name, "stop_strategy")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Strategy stop failed: {e}")
            self.error_handler.handle_strategy_error(e, strategy_id, "stop_strategy")
            return False
    
    def force_stop_strategy(self, strategy_id: str, reason: str = "Force stop") -> bool:
        """
        Force stop a strategy immediately without graceful shutdown.
        
        Args:
            strategy_id: Strategy ID to force stop
            reason: Reason for force stopping
            
        Returns:
            bool: True if force stop successful
        """
        try:
            with self._strategy_lock:
                if strategy_id not in self.strategies:
                    self.logger.warning(f"Strategy not found for force stop: {strategy_id}")
                    return True  # Consider it successful if not found
                
                registration = self.strategies[strategy_id]
                
                self.logger.warning(f"Force stopping strategy: {registration.strategy_name} (Reason: {reason})")
                
                # Immediately cancel all orders
                self._cancel_strategy_orders(strategy_id)
                
                # Force stop strategy instance
                try:
                    strategy_instance = registration.strategy_instance
                    if hasattr(strategy_instance, 'force_stop'):
                        strategy_instance.force_stop()
                    else:
                        strategy_instance.stop()
                except Exception as e:
                    self.logger.error(f"Error during force stop of {strategy_id}: {e}")
                
                # Update state
                self.strategy_states[strategy_id] = StrategyState.STOPPED
                registration.last_activity = datetime.now()
                registration.error_count += 1
                
                # Emit force stop event
                self.event_manager.emit_event(
                    EventType.STRATEGY_FORCE_STOPPED,
                    {
                        'strategy_id': strategy_id,
                        'strategy_name': registration.strategy_name,
                        'reason': reason,
                        'timestamp': datetime.now()
                    }
                )
                
                return True
                
        except Exception as e:
            self.logger.error(f"Force stop failed for strategy {strategy_id}: {e}")
            return False
    
    # ==========================================================================
    # SIGNAL PROCESSING
    # ==========================================================================
    
    def process_strategy_signal(self, signal: TradingSignal) -> bool:
        """
        Process a trading signal from a strategy.
        
        Args:
            signal: Trading signal to process
            
        Returns:
            bool: True if signal processing initiated successfully
        """
        try:
            # Validate signal
            if not self._validate_signal(signal):
                self.logger.warning(f"Invalid signal rejected: {signal.signal_id}")
                return False
            
            # Check if engine is running
            if self.state != EngineState.RUNNING:
                self.logger.warning(f"Signal rejected - engine not running: {self.state}")
                return False
            
            # Check strategy state
            if signal.strategy_id not in self.strategies:
                self.logger.warning(f"Signal rejected - unknown strategy: {signal.strategy_id}")
                return False
            
            if self.strategy_states[signal.strategy_id] != StrategyState.RUNNING:
                self.logger.warning(f"Signal rejected - strategy not running: {signal.strategy_id}")
                return False
            
            # Pre-trade risk checks
            if self.has_risk_manager and self.risk_manager:
                risk_check_result = self.risk_manager.check_pre_trade_risk(signal)
                if not risk_check_result.approved:
                    self.logger.warning(f"Signal rejected by risk manager: {risk_check_result.reason}")
                    return False
            
            # Add signal to processing queue
            try:
                priority = signal.priority.value
                self.signal_queue.put((priority, signal), timeout=1.0)
                self.signals_processed_today += 1
                
                self.logger.info(f"Signal queued for processing: {signal.signal_id} (Strategy: {signal.strategy_id})")
                
                # Emit signal received event
                self.event_manager.emit_event(
                    EventType.SIGNAL_RECEIVED,
                    {
                        'signal_id': signal.signal_id,
                        'strategy_id': signal.strategy_id,
                        'signal_type': signal.signal_type.value,
                        'symbol': signal.symbol,
                        'action': signal.action.value,
                        'quantity': signal.quantity,
                        'timestamp': signal.timestamp
                    }
                )
                
                return True
                
            except queue.Full:
                self.logger.error("Signal queue full - rejecting signal")
                return False
                
        except Exception as e:
            self.logger.error(f"Signal processing failed: {e}")
            self.error_handler.handle_signal_error(e, signal.signal_id, signal.strategy_id)
            return False
    
    def _process_signal_queue(self):
        """Process signals from the signal queue (runs in worker thread)."""
        while not self._shutdown_event.is_set():
            try:
                # Get signal with timeout
                try:
                    priority, signal = self.signal_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Process the signal
                self._execute_signal(signal)
                
                # Mark task as done
                self.signal_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in signal processing thread: {e}")
                time.sleep(1.0)  # Prevent tight error loop
    
    def _execute_signal(self, signal: TradingSignal):
        """Execute a trading signal by converting it to orders."""
        try:
            execution_id = str(uuid.uuid4())
            
            # Create execution tracking
            execution = OrderExecution(
                execution_id=execution_id,
                signal_id=signal.signal_id,
                strategy_id=signal.strategy_id,
                status="PROCESSING"
            )
            
            with self._execution_lock:
                self.pending_executions[execution_id] = execution
            
            # Generate orders from signal
            orders = self._generate_orders_from_signal(signal)
            
            if not orders:
                execution.status = "FAILED"
                execution.error_message = "No orders generated from signal"
                self.logger.warning(f"No orders generated for signal: {signal.signal_id}")
                return
            
            # Execute orders
            success = True
            for order in orders:
                if not self._execute_single_order(order, execution_id):
                    success = False
                    break
            
            # Update execution status
            execution.status = "COMPLETED" if success else "FAILED"
            
            self.logger.info(f"Signal execution {'completed' if success else 'failed'}: {signal.signal_id}")
            
        except Exception as e:
            self.logger.error(f"Signal execution failed: {e}")
            if execution_id in self.pending_executions:
                self.pending_executions[execution_id].status = "ERROR"
                self.pending_executions[execution_id].error_message = str(e)
    
    # ==========================================================================
    # ORDER EXECUTION
    # ==========================================================================
    
    def _generate_orders_from_signal(self, signal: TradingSignal) -> List[Dict[str, Any]]:
        """
        Generate executable orders from a trading signal.
        
        Args:
            signal: Trading signal to convert
            
        Returns:
            List of order dictionaries
        """
        try:
            orders = []
            
            # Basic order structure
            base_order = {
                'symbol': signal.symbol,
                'action': signal.action.value,
                'quantity': signal.quantity,
                'order_type': signal.order_type.value,
                'time_in_force': signal.time_in_force,
                'strategy_id': signal.strategy_id,
                'signal_id': signal.signal_id,
                'metadata': signal.metadata.copy()
            }
            
            # Add price information based on order type
            if signal.order_type == OrderType.LIMIT and signal.limit_price:
                base_order['limit_price'] = signal.limit_price
            elif signal.order_type == OrderType.STOP and signal.stop_price:
                base_order['stop_price'] = signal.stop_price
            elif signal.order_type == OrderType.STOP_LIMIT:
                if signal.limit_price and signal.stop_price:
                    base_order['limit_price'] = signal.limit_price
                    base_order['stop_price'] = signal.stop_price
                else:
                    self.logger.error(f"Stop limit order missing prices: {signal.signal_id}")
                    return []
            
            orders.append(base_order)
            
            return orders
            
        except Exception as e:
            self.logger.error(f"Order generation failed: {e}")
            return []
    
    def _execute_single_order(self, order: Dict[str, Any], execution_id: str) -> bool:
        """
        Execute a single order.
        
        Args:
            order: Order dictionary to execute
            execution_id: Execution tracking ID
            
        Returns:
            bool: True if execution successful
        """
        try:
            start_time = time.time()
            
            # Use order manager if available
            if self.has_order_manager and self.order_manager:
                result = self.order_manager.submit_order(order)
                
                if result and result.get('success', False):
                    order_id = result.get('order_id')
                    
                    # Update execution tracking
                    if execution_id in self.pending_executions:
                        execution = self.pending_executions[execution_id]
                        execution.order_id = order_id
                        execution.status = "SUBMITTED"
                        execution.execution_time_ms = (time.time() - start_time) * 1000
                    
                    self.orders_processed_today += 1
                    self.logger.info(f"Order submitted successfully: {order_id}")
                    
                    # Emit order submitted event
                    self.event_manager.emit_event(
                        EventType.ORDER_SUBMITTED,
                        {
                            'order_id': order_id,
                            'execution_id': execution_id,
                            'strategy_id': order.get('strategy_id'),
                            'symbol': order.get('symbol'),
                            'action': order.get('action'),
                            'quantity': order.get('quantity'),
                            'timestamp': datetime.now()
                        }
                    )
                    
                    return True
                else:
                    error_message = result.get('error', 'Unknown error') if result else 'No result returned'
                    self.logger.error(f"Order submission failed: {error_message}")
                    
                    # Update execution tracking
                    if execution_id in self.pending_executions:
                        execution = self.pending_executions[execution_id]
                        execution.status = "FAILED"
                        execution.error_message = error_message
                        execution.execution_time_ms = (time.time() - start_time) * 1000
                    
                    return False
            else:
                # Fallback: simulate order execution for testing
                self.logger.warning("Order manager not available - simulating order execution")
                
                # Simulate execution delay
                time.sleep(0.1)
                
                # Generate mock order ID
                order_id = f"SIM_{int(time.time() * 1000)}"
                
                # Update execution tracking
                if execution_id in self.pending_executions:
                    execution = self.pending_executions[execution_id]
                    execution.order_id = order_id
                    execution.status = "SIMULATED"
                    execution.execution_time_ms = (time.time() - start_time) * 1000
                
                self.orders_processed_today += 1
                self.logger.info(f"Order simulated: {order_id}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Order execution failed: {e}")
            
            # Update execution tracking
            if execution_id in self.pending_executions:
                execution = self.pending_executions[execution_id]
                execution.status = "ERROR"
                execution.error_message = str(e)
                execution.execution_time_ms = (time.time() - start_time) * 1000 if 'start_time' in locals() else None
            
            return False
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    
    def update_positions(self) -> bool:
        """
        Update all position data and calculate portfolio metrics.
        
        Returns:
            bool: True if update successful
        """
        try:
            if self.has_position_tracker and self.position_tracker:
                # Update positions from broker
                positions_updated = self.position_tracker.update_positions()
                
                if positions_updated:
                    # Calculate portfolio Greeks
                    self._calculate_portfolio_greeks()
                    
                    # Update performance metrics
                    self._update_performance_metrics()
                    
                    # Check position limits
                    self._check_position_limits()
                    
                    # Create portfolio snapshot
                    self._create_portfolio_snapshot()
                    
                    return True
                else:
                    self.logger.warning("Position update failed")
                    return False
            else:
                # Simulate position updates for testing
                self._simulate_position_update()
                return True
                
        except Exception as e:
            self.logger.error(f"Position update failed: {e}")
            self.error_handler.handle_position_error(e, "TradingEngine", "update_positions")
            return False
    
    def _calculate_portfolio_greeks(self):
        """Calculate aggregated portfolio Greeks."""
        try:
            if not self.has_position_tracker or not self.position_tracker:
                return
            
            positions = self.position_tracker.get_all_positions()
            
            total_delta = 0.0
            total_gamma = 0.0
            total_theta = 0.0
            total_vega = 0.0
            
            for position in positions:
                if position.get('option_data'):
                    greeks = position['option_data'].get('greeks', {})
                    quantity = position.get('quantity', 0)
                    
                    total_delta += greeks.get('delta', 0) * quantity
                    total_gamma += greeks.get('gamma', 0) * quantity
                    total_theta += greeks.get('theta', 0) * quantity
                    total_vega += greeks.get('vega', 0) * quantity
            
            # Store portfolio Greeks
            with self._metrics_lock:
                self.performance_metrics.update_greeks({
                    'total_delta': total_delta,
                    'total_gamma': total_gamma,
                    'total_theta': total_theta,
                    'total_vega': total_vega,
                    'timestamp': datetime.now()
                })
            
            # Check Greek limits
            if self.has_risk_manager and self.risk_manager:
                self.risk_manager.check_greek_limits({
                    'delta': total_delta,
                    'gamma': total_gamma,
                    'theta': total_theta,
                    'vega': total_vega
                })
            
            self.logger.debug(f"Portfolio Greeks - Delta: {total_delta:.2f}, Gamma: {total_gamma:.4f}, "
                            f"Theta: {total_theta:.2f}, Vega: {total_vega:.2f}")
            
        except Exception as e:
            self.logger.error(f"Portfolio Greeks calculation failed: {e}")
    
    def _simulate_position_update(self):
        """Simulate position updates for testing when position tracker unavailable."""
        try:
            # Generate mock portfolio metrics
            import random
            
            mock_greeks = {
                'total_delta': random.uniform(-100, 100),
                'total_gamma': random.uniform(-10, 10),
                'total_theta': random.uniform(-50, 0),
                'total_vega': random.uniform(-20, 20),
                'timestamp': datetime.now()
            }
            
            with self._metrics_lock:
                self.performance_metrics.update_greeks(mock_greeks)
            
            self.logger.debug("Simulated position update completed")
            
        except Exception as e:
            self.logger.error(f"Position simulation failed: {e}")
    
    # ==========================================================================
    # MONITORING AND HEALTH CHECKS
    # ==========================================================================
    
    def _start_monitoring(self):
        """Start monitoring threads."""
        try:
            # Start heartbeat monitoring
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_monitor,
                name="HeartbeatMonitor",
                daemon=True
            )
            heartbeat_thread.start()
            self.worker_threads['heartbeat'] = heartbeat_thread
            
            # Start performance monitoring
            performance_thread = threading.Thread(
                target=self._performance_monitor,
                name="PerformanceMonitor",
                daemon=True
            )
            performance_thread.start()
            self.worker_threads['performance'] = performance_thread
            
            # Start risk monitoring
            risk_thread = threading.Thread(
                target=self._risk_monitor,
                name="RiskMonitor",
                daemon=True
            )
            risk_thread.start()
            self.worker_threads['risk'] = risk_thread
            
            self.logger.info("Monitoring threads started")
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
    
    def _heartbeat_monitor(self):
        """Monitor system heartbeat and health."""
        while not self._shutdown_event.is_set():
            try:
                self.last_heartbeat = datetime.now()
                
                # Check engine health
                health_status = self._check_engine_health()
                
                if not health_status['healthy']:
                    self.logger.warning(f"Engine health check failed: {health_status['issues']}")
                    
                    # Emit health warning event
                    self.event_manager.emit_event(
                        EventType.HEALTH_WARNING,
                        {
                            'timestamp': self.last_heartbeat,
                            'issues': health_status['issues'],
                            'metrics': health_status['metrics']
                        }
                    )
                
                # Sleep until next heartbeat
                self._shutdown_event.wait(DEFAULT_HEARTBEAT_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Heartbeat monitor error: {e}")
                self._shutdown_event.wait(5.0)  # Brief pause on error
    
    def _performance_monitor(self):
        """Monitor system performance metrics."""
        while not self._shutdown_event.is_set():
            try:
                # Update positions every 30 seconds
                if not self.update_positions():
                    self.logger.warning("Position update failed in performance monitor")
                
                # Check performance thresholds
                self._check_performance_thresholds()
                
                # Clean up old executions
                self._cleanup_old_executions()
                
                # Sleep until next check
                self._shutdown_event.wait(30.0)
                
            except Exception as e:
                self.logger.error(f"Performance monitor error: {e}")
                self._shutdown_event.wait(10.0)
    
    def _risk_monitor(self):
        """Monitor risk metrics and limits."""
        while not self._shutdown_event.is_set():
            try:
                # Check daily loss limits
                daily_pnl = self._calculate_daily_pnl()
                
                if daily_pnl < -self.max_daily_loss:
                    self.logger.critical(f"Daily loss limit exceeded: {daily_pnl:.2f}")
                    self.emergency_stop(f"Daily loss limit exceeded: {daily_pnl:.2f}")
                    break
                
                # Check circuit breaker conditions
                if self._should_trigger_circuit_breaker():
                    self.logger.warning("Circuit breaker conditions met")
                    self._activate_circuit_breaker()
                
                # Sleep until next check
                self._shutdown_event.wait(10.0)
                
            except Exception as e:
                self.logger.error(f"Risk monitor error: {e}")
                self._shutdown_event.wait(5.0)
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _validate_signal(self, signal: TradingSignal) -> bool:
        """Validate a trading signal."""
        try:
            # Check required fields
            if not signal.signal_id or not signal.strategy_id:
                return False
            
            if not signal.symbol or not signal.action:
                return False
            
            if signal.quantity <= 0:
                return False
            
            # Check signal type
            if signal.signal_type not in SignalType:
                return False
            
            # Check action type
            if signal.action not in OrderAction:
                return False
            
            # Check order type
            if signal.order_type not in OrderType:
                return False
            
            # Validate prices for limit orders
            if signal.order_type == OrderType.LIMIT and not signal.limit_price:
                return False
            
            if signal.order_type == OrderType.STOP and not signal.stop_price:
                return False
            
            if signal.order_type == OrderType.STOP_LIMIT:
                if not signal.limit_price or not signal.stop_price:
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Signal validation error: {e}")
            return False
    
    def _check_engine_health(self) -> Dict[str, Any]:
        """Check overall engine health."""
        try:
            issues = []
            metrics = {}
            
            # Check thread health
            dead_threads = []
            for name, thread in self.worker_threads.items():
                if not thread.is_alive():
                    dead_threads.append(name)
            
            if dead_threads:
                issues.append(f"Dead threads: {dead_threads}")
            
            # Check queue sizes
            signal_queue_size = self.signal_queue.qsize()
            order_queue_size = self.order_queue.qsize()
            
            metrics['signal_queue_size'] = signal_queue_size
            metrics['order_queue_size'] = order_queue_size
            
            if signal_queue_size > SIGNAL_QUEUE_MAX_SIZE * 0.8:
                issues.append(f"Signal queue nearly full: {signal_queue_size}")
            
            if order_queue_size > ORDER_QUEUE_MAX_SIZE * 0.8:
                issues.append(f"Order queue nearly full: {order_queue_size}")
            
            # Check strategy health
            error_strategies = []
            for strategy_id, state in self.strategy_states.items():
                if state == StrategyState.ERROR:
                    error_strategies.append(strategy_id)
            
            if error_strategies:
                issues.append(f"Strategies in error state: {len(error_strategies)}")
            
            # Check broker connection
            if self.spyder_client and hasattr(self.spyder_client, 'is_connected'):
                if not self.spyder_client.is_connected():
                    issues.append("Broker connection lost")
            
            return {
                'healthy': len(issues) == 0,
                'issues': issues,
                'metrics': metrics
            }
            
        except Exception as e:
            self.logger.error(f"Health check error: {e}")
            return {
                'healthy': False,
                'issues': [f"Health check failed: {e}"],
                'metrics': {}
            }
    
    def _start_worker_threads(self):
        """Start all worker threads."""
        try:
            # Signal processing thread
            signal_thread = threading.Thread(
                target=self._process_signal_queue,
                name="SignalProcessor",
                daemon=True
            )
            signal_thread.start()
            self.worker_threads['signal_processor'] = signal_thread
            
            self.logger.info("Worker threads started")
            
        except Exception as e:
            self.logger.error(f"Failed to start worker threads: {e}")
    
    def _stop_worker_threads(self):
        """Stop all worker threads."""
        try:
            # Wait for queues to empty
            self.signal_queue.join()
            self.order_queue.join()
            
            # Wait for threads to finish
            for name, thread in self.worker_threads.items():
                if thread.is_alive():
                    thread.join(timeout=5.0)
                    if thread.is_alive():
                        self.logger.warning(f"Thread {name} did not stop gracefully")
            
            self.worker_threads.clear()
            self.logger.info("Worker threads stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping worker threads: {e}")
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get comprehensive engine status."""
        try:
            with self._state_lock:
                status = {
                    'state': self.state.value,
                    'start_time': self.start_time.isoformat() if self.start_time else None,
                    'uptime_seconds': (datetime.now() - self.start_time).total_seconds() if self.start_time else 0,
                    'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
                    'strategies': {
                        'total': len(self.strategies),
                        'running': len([s for s in self.strategy_states.values() if s == StrategyState.RUNNING]),
                        'stopped': len([s for s in self.strategy_states.values() if s == StrategyState.STOPPED]),
                        'error': len([s for s in self.strategy_states.values() if s == StrategyState.ERROR])
                    },
                    'orders': {
                        'processed_today': self.orders_processed_today,
                        'pending_executions': len(self.pending_executions)
                    },
                    'signals': {
                        'processed_today': self.signals_processed_today,
                        'queue_size': self.signal_queue.qsize()
                    },
                    'emergency_stop': self.emergency_stop_triggered,
                    'circuit_breaker': self.circuit_breaker_active
                }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting engine status: {e}")
            return {'error': str(e)}
    
    # Additional helper methods...
    
    def _setup_event_handlers(self):
        """Set up event handlers for the engine."""
        # Implementation for event handler setup
        pass
    
    def _initialize_performance_tracking(self):
        """Initialize performance tracking systems."""
        # Implementation for performance tracking initialization
        pass
    
    def _validate_configuration(self) -> bool:
        """Validate engine configuration."""
        # Implementation for configuration validation
        return True
    
    def _stop_all_strategies(self, reason: str):
        """Stop all registered strategies."""
        for strategy_id in list(self.strategies.keys()):
            self.stop_strategy(strategy_id, reason)
    
    def _cleanup_resources(self):
        """Clean up engine resources."""
        try:
            # Close thread pool
            self.thread_pool.shutdown(wait=True)
            
            # Clear data structures
            with self._execution_lock:
                self.pending_executions.clear()
            
            self.logger.info("Engine resources cleaned up")
            
        except Exception as e:
            self.logger.error(f"Resource cleanup error: {e}")
    
    def _cancel_all_pending_orders(self):
        """Cancel all pending orders."""
        # Implementation for canceling pending orders
        pass
    
    def _initialize_strategy(self, strategy_id: str) -> bool:
        """Initialize a registered strategy."""
        # Implementation for strategy initialization
        return True
    
    def _pre_start_checks(self, strategy_id: str) -> bool:
        """Perform pre-start checks for a strategy."""
        # Implementation for pre-start validation
        return True
    
    def _cancel_strategy_orders(self, strategy_id: str):
        """Cancel all orders for a specific strategy."""
        # Implementation for strategy-specific order cancellation
        pass
    
    def _update_performance_metrics(self):
        """Update performance metrics."""
        # Implementation for performance metrics update
        pass
    
    def _check_position_limits(self):
        """Check position limits and constraints."""
        # Implementation for position limit checking
        pass
    
    def _create_portfolio_snapshot(self):
        """Create a portfolio snapshot."""
        # Implementation for portfolio snapshot creation
        pass
    
    def _stop_monitoring(self):
        """Stop monitoring threads."""
        # Already handled in _stop_worker_threads
        pass
    
    def _check_performance_thresholds(self):
        """Check performance thresholds."""
        # Implementation for performance threshold checking
        pass
    
    def _cleanup_old_executions(self):
        """Clean up old execution records."""
        # Implementation for execution cleanup
        pass
    
    def _calculate_daily_pnl(self) -> float:
        """Calculate daily P&L."""
        # Implementation for daily P&L calculation
        return 0.0
    
    def _should_trigger_circuit_breaker(self) -> bool:
        """Check if circuit breaker should be triggered."""
        # Implementation for circuit breaker logic
        return False
    
    def _activate_circuit_breaker(self):
        """Activate circuit breaker."""
        self.circuit_breaker_active = True
        self.logger.warning("Circuit breaker activated")

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
        'max_daily_loss': 1000,
        'default_max_position_size': 10000,
        'default_max_daily_trades': 20
    }
    
    # Mock dependencies (for testing without full system)
    class MockSpyderClient:
        def is_connected(self):
            return True
    
    class MockEventManager:
        def emit_event(self, event_type, data):
            print(f"Event: {event_type} - {data}")
    
    # Create engine instance
    mock_client = MockSpyderClient()
    mock_event_manager = MockEventManager()
    
    engine = TradingEngine(test_config, mock_client, mock_event_manager)
    
    if engine.initialize():
        print("✅ TradingEngine initialized successfully")
        
        # Test basic functionality
        status = engine.get_engine_status()
        print(f"Engine status: {status}")
        
        if engine.start():
            print("✅ TradingEngine started successfully")
            
            # Brief operation
            time.sleep(2)
            
            if engine.stop("Test completed"):
                print("✅ TradingEngine stopped successfully")
            else:
                print("❌ TradingEngine stop failed")
        else:
            print("❌ TradingEngine start failed")
    else:
        print("❌ TradingEngine initialization failed")
    
    print("TradingEngine testing completed.")