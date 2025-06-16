#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD08_StrategyManager.py
Group: D (Trading Strategies)
Purpose: Strategy management and execution coordination

Description:
    This module provides centralized management for all trading strategies
    in the Spyder system. It handles strategy registration, activation,
    execution scheduling, performance tracking, and coordination between
    multiple strategies. The manager ensures proper resource allocation
    and prevents strategy conflicts while maintaining execution metrics.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from datetime import datetime, time as datetime_time
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Execution intervals (seconds)
DEFAULT_EXECUTION_INTERVAL = 60  # 1 minute
FAST_EXECUTION_INTERVAL = 5      # 5 seconds
SLOW_EXECUTION_INTERVAL = 300    # 5 minutes

# Performance tracking
MAX_PERFORMANCE_HISTORY = 1000   # Maximum records to keep
PERFORMANCE_SAVE_INTERVAL = 3600 # Save performance every hour

# Strategy limits
MAX_ACTIVE_STRATEGIES = 10       # Maximum concurrent strategies
MAX_SIGNALS_PER_MINUTE = 20      # Rate limiting

# ==============================================================================
# ENUMS
# ==============================================================================
class StrategyState(Enum):
    """Strategy execution states."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"

class ExecutionMode(Enum):
    """Strategy execution modes."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PRIORITY = "priority"

class StrategyPriority(Enum):
    """Strategy priority levels."""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class StrategyInfo:
    """Strategy information container."""
    name: str
    instance: Any
    state: StrategyState = StrategyState.INACTIVE
    priority: StrategyPriority = StrategyPriority.NORMAL
    enabled: bool = True
    last_execution: Optional[datetime] = None
    execution_count: int = 0
    error_count: int = 0

@dataclass
class StrategyPerformance:
    """Strategy performance metrics."""
    strategy_name: str
    trades: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    last_updated: Optional[datetime] = None

@dataclass
class ExecutionResult:
    """Strategy execution result."""
    strategy_name: str
    timestamp: datetime
    success: bool
    signals: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class StrategyManager:
    """
    Central strategy management system for coordinating all trading strategies.
    
    This class provides comprehensive strategy lifecycle management including
    registration, activation, execution scheduling, performance tracking, and
    conflict resolution between multiple strategies.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        strategies: Dictionary of registered strategies
        active_strategies: Set of currently active strategy names
        execution_mode: How strategies are executed
        performance_tracker: Performance metrics for each strategy
        
    Example:
        >>> manager = StrategyManager(config)
        >>> manager.register_strategy("IronCondor", iron_condor_instance)
        >>> manager.activate_strategy("IronCondor")
        >>> manager.start()
    """
    
    def __init__(self, config=None, event_manager=None):
        """Initialize the strategy manager."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.config = config or {}
        self.event_manager = event_manager
        
        # Strategy tracking
        self.strategies: Dict[str, StrategyInfo] = {}
        self.active_strategies: Set[str] = set()
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        
        # Execution control
        self.is_running = False
        self.state = StrategyState.INACTIVE
        self.execution_mode = ExecutionMode.SEQUENTIAL
        self.execution_interval = DEFAULT_EXECUTION_INTERVAL
        self.last_execution_time = None
        
        # Performance tracking
        self.execution_history: List[ExecutionResult] = []
        self.performance_history: Dict[str, List[Dict]] = defaultdict(list)
        
        # Threading and synchronization
        self._execution_lock = threading.Lock()
        self._worker_thread = None
        self._stop_event = threading.Event()
        
        # Rate limiting
        self._signal_timestamps = deque(maxlen=MAX_SIGNALS_PER_MINUTE)
        
        self.logger.info(f"{self.__class__.__name__} initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start(self) -> bool:
        """
        Start the strategy manager.
        
        Returns:
            bool: True if started successfully
        """
        try:
            if self.is_running:
                self.logger.warning("Strategy manager already running")
                return True
            
            self.is_running = True
            self.state = StrategyState.ACTIVE
            self._stop_event.clear()
            
            # Start worker thread
            self._start_worker()
            
            self.logger.info("Strategy manager started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start strategy manager: {e}")
            self.state = StrategyState.ERROR
            return False
    
    def stop(self) -> bool:
        """
        Stop the strategy manager.
        
        Returns:
            bool: True if stopped successfully
        """
        try:
            self.is_running = False
            self.state = StrategyState.INACTIVE
            self._stop_event.set()
            
            # Wait for worker thread
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=5)
            
            self.logger.info("Strategy manager stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop strategy manager: {e}")
            return False
    
    def shutdown(self) -> None:
        """Shutdown the strategy manager gracefully."""
        try:
            self.stop()
            
            # Deactivate all strategies
            for strategy_name in list(self.active_strategies):
                self.deactivate_strategy(strategy_name)
            
            # Clear data
            self.strategies.clear()
            self.active_strategies.clear()
            self.execution_history.clear()
            
            self.logger.info("Strategy manager shut down")
            
        except Exception as e:
            self.logger.error(f"Error during strategy manager shutdown: {e}")
    
    # ==========================================================================
    # PUBLIC METHODS - STRATEGY MANAGEMENT
    # ==========================================================================
    def register_strategy(
        self,
        strategy_name: str,
        strategy_instance: Any,
        priority: StrategyPriority = StrategyPriority.NORMAL
    ) -> bool:
        """
        Register a trading strategy.
        
        Args:
            strategy_name: Unique name of the strategy
            strategy_instance: Strategy object instance
            priority: Strategy execution priority
            
        Returns:
            bool: True if registered successfully
        """
        try:
            # Validate strategy
            if not self._validate_strategy(strategy_instance):
                return False
            
            with self._execution_lock:
                # Create strategy info
                strategy_info = StrategyInfo(
                    name=strategy_name,
                    instance=strategy_instance,
                    priority=priority
                )
                
                # Register strategy
                self.strategies[strategy_name] = strategy_info
                
                # Initialize performance tracking
                self.strategy_performance[strategy_name] = StrategyPerformance(
                    strategy_name=strategy_name
                )
            
            self.logger.info(f"Strategy '{strategy_name}' registered successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register strategy '{strategy_name}': {e}")
            return False
    
    def unregister_strategy(self, strategy_name: str) -> bool:
        """
        Unregister a strategy.
        
        Args:
            strategy_name: Name of the strategy to unregister
            
        Returns:
            bool: True if unregistered successfully
        """
        try:
            with self._execution_lock:
                if strategy_name not in self.strategies:
                    self.logger.warning(f"Strategy '{strategy_name}' not found")
                    return False
                
                # Deactivate if active
                if strategy_name in self.active_strategies:
                    self.deactivate_strategy(strategy_name)
                
                # Remove strategy
                del self.strategies[strategy_name]
                
            self.logger.info(f"Strategy '{strategy_name}' unregistered")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unregister strategy '{strategy_name}': {e}")
            return False
    
    def activate_strategy(self, strategy_name: str) -> bool:
        """
        Activate a strategy for execution.
        
        Args:
            strategy_name: Name of the strategy to activate
            
        Returns:
            bool: True if activated successfully
        """
        try:
            if strategy_name not in self.strategies:
                self.logger.error(f"Strategy '{strategy_name}' not found")
                return False
            
            with self._execution_lock:
                # Check limits
                if len(self.active_strategies) >= MAX_ACTIVE_STRATEGIES:
                    self.logger.error(f"Maximum active strategies limit reached ({MAX_ACTIVE_STRATEGIES})")
                    return False
                
                # Activate strategy
                self.active_strategies.add(strategy_name)
                self.strategies[strategy_name].state = StrategyState.ACTIVE
                
                # Initialize strategy if needed
                strategy = self.strategies[strategy_name].instance
                if hasattr(strategy, 'initialize'):
                    strategy.initialize()
            
            self.logger.info(f"Strategy '{strategy_name}' activated")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to activate strategy '{strategy_name}': {e}")
            return False
    
    def deactivate_strategy(self, strategy_name: str) -> bool:
        """
        Deactivate a strategy.
        
        Args:
            strategy_name: Name of the strategy to deactivate
            
        Returns:
            bool: True if deactivated successfully
        """
        try:
            with self._execution_lock:
                if strategy_name in self.active_strategies:
                    self.active_strategies.discard(strategy_name)
                    
                if strategy_name in self.strategies:
                    self.strategies[strategy_name].state = StrategyState.INACTIVE
                    
                    # Cleanup strategy if needed
                    strategy = self.strategies[strategy_name].instance
                    if hasattr(strategy, 'cleanup'):
                        strategy.cleanup()
            
            self.logger.info(f"Strategy '{strategy_name}' deactivated")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to deactivate strategy '{strategy_name}': {e}")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - EXECUTION
    # ==========================================================================
    def execute_strategies(self, market_data: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute all active strategies.
        
        Args:
            market_data: Current market data
            
        Returns:
            Dict with execution results
        """
        execution_summary = {
            'executed_strategies': [],
            'execution_time': datetime.now(),
            'total_signals': 0,
            'errors': [],
            'duration': 0.0
        }
        
        start_time = time.time()
        
        try:
            if not self.is_running:
                return execution_summary
            
            # Check rate limiting
            if not self._check_rate_limit():
                self.logger.warning("Rate limit exceeded, skipping execution")
                execution_summary['errors'].append("Rate limit exceeded")
                return execution_summary
            
            # Get active strategies
            with self._execution_lock:
                active_strategies = self._get_sorted_active_strategies()
            
            # Execute strategies based on mode
            if self.execution_mode == ExecutionMode.SEQUENTIAL:
                results = self._execute_sequential(active_strategies, market_data)
            elif self.execution_mode == ExecutionMode.PARALLEL:
                results = self._execute_parallel(active_strategies, market_data)
            else:  # PRIORITY
                results = self._execute_priority(active_strategies, market_data)
            
            # Process results
            for result in results:
                execution_summary['executed_strategies'].append({
                    'name': result.strategy_name,
                    'success': result.success,
                    'signals': len(result.signals),
                    'timestamp': result.timestamp
                })
                execution_summary['total_signals'] += len(result.signals)
                execution_summary['errors'].extend(result.errors)
                
                # Update performance
                self._update_performance(result)
            
            # Update execution time
            self.last_execution_time = datetime.now()
            execution_summary['duration'] = time.time() - start_time
            
        except Exception as e:
            self.logger.error(f"Error in strategy execution: {e}")
            execution_summary['errors'].append(str(e))
        
        return execution_summary
    
    # ==========================================================================
    # PUBLIC METHODS - STATUS AND PERFORMANCE
    # ==========================================================================
    def get_strategy_status(self) -> Dict[str, Any]:
        """Get status of all strategies."""
        try:
            with self._execution_lock:
                strategy_list = []
                for name, info in self.strategies.items():
                    strategy_list.append({
                        'name': name,
                        'state': info.state.value,
                        'priority': info.priority.value,
                        'enabled': info.enabled,
                        'last_execution': info.last_execution.isoformat() if info.last_execution else None,
                        'execution_count': info.execution_count,
                        'error_count': info.error_count
                    })
                
                return {
                    'manager_state': self.state.value,
                    'is_running': self.is_running,
                    'execution_mode': self.execution_mode.value,
                    'total_strategies': len(self.strategies),
                    'active_strategies': len(self.active_strategies),
                    'strategies': strategy_list,
                    'last_execution': self.last_execution_time.isoformat() if self.last_execution_time else None
                }
        except Exception as e:
            self.logger.error(f"Error getting strategy status: {e}")
            return {'error': str(e)}
    
    def get_strategy_performance(self, strategy_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance metrics for strategies.
        
        Args:
            strategy_name: Specific strategy name, or None for all
            
        Returns:
            Dict with performance data
        """
        try:
            if strategy_name:
                perf = self.strategy_performance.get(strategy_name)
                return vars(perf) if perf else {}
            else:
                return {
                    name: vars(perf) 
                    for name, perf in self.strategy_performance.items()
                }
        except Exception as e:
            self.logger.error(f"Error getting strategy performance: {e}")
            return {}
    
    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================
    def _validate_strategy(self, strategy_instance: Any) -> bool:
        """Validate strategy has required methods."""
        required_methods = ['execute']
        
        for method in required_methods:
            if not hasattr(strategy_instance, method):
                self.logger.error(f"Strategy missing required method: {method}")
                return False
        
        return True
    
    def _start_worker(self):
        """Start worker thread for strategy execution."""
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True
        )
        self._worker_thread.start()
    
    def _worker_loop(self):
        """Main worker loop for periodic strategy execution."""
        self.logger.info("Strategy execution worker started")
        
        while not self._stop_event.is_set():
            try:
                # Execute strategies
                if self.active_strategies:
                    self.execute_strategies()
                
                # Wait for next execution
                self._stop_event.wait(self.execution_interval)
                
            except Exception as e:
                self.logger.error(f"Error in strategy worker loop: {e}")
                time.sleep(1)  # Brief pause on error
    
    def _get_sorted_active_strategies(self) -> List[StrategyInfo]:
        """Get active strategies sorted by priority."""
        active = [
            self.strategies[name]
            for name in self.active_strategies
            if name in self.strategies and self.strategies[name].enabled
        ]
        
        # Sort by priority (highest first)
        return sorted(active, key=lambda s: s.priority.value, reverse=True)
    
    def _execute_sequential(
        self,
        strategies: List[StrategyInfo],
        market_data: Optional[Dict]
    ) -> List[ExecutionResult]:
        """Execute strategies sequentially."""
        results = []
        
        for strategy_info in strategies:
            result = self._execute_single_strategy(strategy_info, market_data)
            results.append(result)
        
        return results
    
    def _execute_parallel(
        self,
        strategies: List[StrategyInfo],
        market_data: Optional[Dict]
    ) -> List[ExecutionResult]:
        """Execute strategies in parallel (placeholder)."""
        # For now, fall back to sequential
        # Full parallel implementation would use ThreadPoolExecutor
        return self._execute_sequential(strategies, market_data)
    
    def _execute_priority(
        self,
        strategies: List[StrategyInfo],
        market_data: Optional[Dict]
    ) -> List[ExecutionResult]:
        """Execute strategies by priority groups."""
        # Group by priority
        priority_groups = defaultdict(list)
        for strategy in strategies:
            priority_groups[strategy.priority].append(strategy)
        
        results = []
        
        # Execute each priority group
        for priority in sorted(priority_groups.keys(), key=lambda p: p.value, reverse=True):
            group_results = self._execute_sequential(priority_groups[priority], market_data)
            results.extend(group_results)
        
        return results
    
    def _execute_single_strategy(
        self,
        strategy_info: StrategyInfo,
        market_data: Optional[Dict]
    ) -> ExecutionResult:
        """Execute a single strategy."""
        start_time = time.time()
        result = ExecutionResult(
            strategy_name=strategy_info.name,
            timestamp=datetime.now(),
            success=False
        )
        
        try:
            # Execute strategy
            strategy_result = strategy_info.instance.execute(market_data)
            
            # Process result
            if strategy_result:
                result.success = True
                if isinstance(strategy_result, dict):
                    result.signals = strategy_result.get('signals', [])
                elif isinstance(strategy_result, list):
                    result.signals = strategy_result
            
            # Update strategy info
            strategy_info.last_execution = datetime.now()
            strategy_info.execution_count += 1
            
        except Exception as e:
            error_msg = f"Error executing strategy '{strategy_info.name}': {e}"
            self.logger.error(error_msg)
            result.errors.append(error_msg)
            strategy_info.error_count += 1
            strategy_info.state = StrategyState.ERROR
        
        result.execution_time = time.time() - start_time
        return result
    
    def _update_performance(self, result: ExecutionResult):
        """Update strategy performance metrics."""
        if result.strategy_name not in self.strategy_performance:
            return
        
        perf = self.strategy_performance[result.strategy_name]
        
        # Update basic metrics
        if result.success and result.signals:
            perf.trades += len(result.signals)
        
        perf.last_updated = datetime.now()
        
        # Add to history
        self.execution_history.append(result)
        if len(self.execution_history) > MAX_PERFORMANCE_HISTORY:
            self.execution_history = self.execution_history[-MAX_PERFORMANCE_HISTORY:]
    
    def _check_rate_limit(self) -> bool:
        """Check if rate limit allows execution."""
        now = time.time()
        
        # Remove old timestamps
        cutoff = now - 60  # 1 minute window
        while self._signal_timestamps and self._signal_timestamps[0] < cutoff:
            self._signal_timestamps.popleft()
        
        # Check limit
        if len(self._signal_timestamps) >= MAX_SIGNALS_PER_MINUTE:
            return False
        
        # Add current timestamp
        self._signal_timestamps.append(now)
        return True
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up strategy manager resources."""
        self.shutdown()

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
# Global instance management
_strategy_manager_instance: Optional[StrategyManager] = None

def get_strategy_manager(config=None, event_manager=None) -> StrategyManager:
    """
    Get singleton strategy manager instance.
    
    Args:
        config: Configuration dictionary
        event_manager: Event manager instance
        
    Returns:
        StrategyManager instance
    """
    global _strategy_manager_instance
    if _strategy_manager_instance is None:
        _strategy_manager_instance = StrategyManager(config, event_manager)
    return _strategy_manager_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Import for type checking only
from collections import deque

__all__ = [
    'StrategyManager',
    'get_strategy_manager',
    'StrategyState',
    'ExecutionMode',
    'StrategyPriority',
    'StrategyInfo',
    'StrategyPerformance',
    'ExecutionResult'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    manager = StrategyManager()
    
    print("✅ StrategyManager created successfully")
    
    if manager.start():
        print("✅ StrategyManager started")
        
        # Test status
        status = manager.get_strategy_status()
        print(f"Status: {status}")
        
        # Test mock strategy
        class MockStrategy:
            def execute(self, market_data):
                return {'signals': [{'action': 'BUY', 'symbol': 'SPY'}]}
        
        # Register and activate
        if manager.register_strategy("MockStrategy", MockStrategy()):
            print("✅ Strategy registered")
            
            if manager.activate_strategy("MockStrategy"):
                print("✅ Strategy activated")
                
                # Execute strategies
                results = manager.execute_strategies()
                print(f"Execution results: {results}")
        
        # Cleanup
        manager.stop()
        manager.cleanup()
        print("✅ StrategyManager stopped")
    else:
        print("❌ Failed to start StrategyManager")