#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU02_ErrorHandler.py
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
import time
import threading
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
import functools

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import traceback
import weakref
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

MAX_ERROR_HISTORY = 1000
ERROR_RATE_WINDOW = 300  # 5 minutes
MAX_ERROR_RATE = 10  # errors per minute
STRATEGY_SHUTDOWN_THRESHOLD = 5  # errors before strategy shutdown
SYSTEM_SHUTDOWN_THRESHOLD = 20  # critical errors before system shutdown


def _to_utc_comparable(ts: datetime) -> datetime:
    """Normalize timestamps to UTC-aware for safe comparisons."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _is_after(left: datetime, right: datetime) -> bool:
    """Return True when left is after right, supporting mixed tz-awareness."""
    return _to_utc_comparable(left) > _to_utc_comparable(right)


# ==============================================================================
# ENUMS
# ==============================================================================
class ErrorCategory(Enum):
    """Error categories for classification"""

    CONNECTION = "connection"
    DATA = "data"
    EXECUTION = "execution"
    RISK = "risk"
    SYSTEM = "system"
    STRATEGY = "strategy"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class RecoveryAction(Enum):
    """Automated recovery actions"""

    NONE = "none"
    RETRY = "retry"
    RECONNECT = "reconnect"
    RESTART_COMPONENT = "restart_component"
    DISABLE_FEATURE = "disable_feature"
    SHUTDOWN_STRATEGY = "shutdown_strategy"
    EMERGENCY_SHUTDOWN = "emergency_shutdown"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class ErrorContext:
    """Context information for an error"""

    error_id: str = field(default_factory=lambda: f"ERR_{int(time.time() * 1000)}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    category: ErrorCategory = ErrorCategory.UNKNOWN
    severity: ErrorSeverity = ErrorSeverity.LOW
    error_type: str = ""
    error_message: str = ""
    stack_trace: str = ""
    component_name: str = ""
    strategy_name: str | None = None
    order_id: str | None = None
    symbol: str | None = None
    additional_data: dict[str, Any] = field(default_factory=dict)
    recovery_attempts: int = 0
    resolved: bool = False
    resolution_time: datetime | None = None
    module_name: str | None = None
    function_name: str | None = None


@dataclass
class RecoveryStrategy:
    """Recovery strategy for specific error types"""

    action: RecoveryAction
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_multiplier: float = 2.0
    timeout: float = 30.0
    callback: Callable | None = None
    conditions: dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# EXCEPTIONS
# ==============================================================================
class SpyderError(Exception):
    """Base exception for Spyder system"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        **kwargs,
    ):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.context = kwargs


class ConnectionError(SpyderError):
    """Connection-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message, ErrorCategory.CONNECTION, ErrorSeverity.HIGH, **kwargs
        )


class DataError(SpyderError):
    """Data-related errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.DATA, ErrorSeverity.MEDIUM, **kwargs)


class ExecutionError(SpyderError):
    """Trade execution errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.EXECUTION, ErrorSeverity.HIGH, **kwargs)


class RiskError(SpyderError):
    """Risk management errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.RISK, ErrorSeverity.CRITICAL, **kwargs)


class TradingError(SpyderError):
    """General trading errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.STRATEGY, ErrorSeverity.HIGH, **kwargs)


# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderErrorHandler:
    """
    Centralized error handling system for Spyder.

    Features:
    - Error categorization and severity assessment
    - Automated recovery strategies
    - Error rate monitoring
    - Strategy and system shutdown triggers
    - Comprehensive error logging
    - Integration with monitoring systems
    """

    def __init__(self, event_manager=None):
        """
        Initialize error handler.

        Args:
            event_manager: Optional EventManager for event emission (dependency injection)
        """
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

        # Dependency injection for event manager to avoid circular imports
        self.event_manager = event_manager

        # Error tracking
        self.error_history: deque = deque(maxlen=MAX_ERROR_HISTORY)
        self.error_counts: dict[str, int] = defaultdict(int)
        self.strategy_errors: dict[str, list[ErrorContext]] = defaultdict(list)
        self.critical_error_count = 0

        # Recovery strategies
        self.recovery_strategies: dict[str, RecoveryStrategy] = (
            self._init_recovery_strategies()
        )

        # Thread safety
        self._lock = threading.RLock()

        # Callbacks
        self.error_callbacks: list[Callable] = []
        self.shutdown_callbacks: list[Callable] = []

        # Component references (weak to avoid circular refs)
        self.components: dict[str, weakref.ref] = {}

        self.logger.debug("SpyderErrorHandler initialized")

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _init_recovery_strategies(self) -> dict[str, RecoveryStrategy]:
        """Initialize default recovery strategies"""
        return {
            # Connection errors
            "ConnectionError": RecoveryStrategy(
                action=RecoveryAction.RECONNECT,
                max_retries=5,
                retry_delay=2.0,
                backoff_multiplier=2.0,
            ),
            # Data errors
            "DataError": RecoveryStrategy(
                action=RecoveryAction.RETRY, max_retries=3, retry_delay=1.0
            ),
            # Execution errors
            "ExecutionError": RecoveryStrategy(
                action=RecoveryAction.RETRY, max_retries=2, retry_delay=0.5
            ),
            # Risk errors
            "RiskError": RecoveryStrategy(
                action=RecoveryAction.SHUTDOWN_STRATEGY, max_retries=0
            ),
            # System errors
            "SystemError": RecoveryStrategy(
                action=RecoveryAction.RESTART_COMPONENT, max_retries=1, retry_delay=5.0
            ),
        }

    # ==========================================================================
    # EVENT MANAGER INJECTION
    # ==========================================================================
    def set_event_manager(self, event_manager):
        """
        Set event manager for event emission (dependency injection).

        Args:
            event_manager: EventManager instance
        """
        self.event_manager = event_manager
        self.logger.debug("Event manager set for error handler")

    # ==========================================================================
    # ERROR HANDLING
    # ==========================================================================
    def handle_error(
        self,
        error: Exception | str,
        component_name: str,
        strategy_name: str | None = None,
        order_id: str | None = None,
        symbol: str | None = None,
        additional_data: dict[str, Any] | None = None,
    ) -> ErrorContext:
        """
        Handle an error with appropriate recovery strategy.

        Args:
            error: The exception that occurred
            component_name: Name of the component where error occurred
            strategy_name: Optional strategy name if error is strategy-specific
            order_id: Optional order ID if error is order-specific
            symbol: Optional symbol if error is symbol-specific
            additional_data: Additional context data

        Returns:
            ErrorContext with error details and recovery status
        """
        with self._lock:
            # Create error context
            error_context = self._create_error_context(
                error, component_name, strategy_name, order_id, symbol, additional_data
            )

            # Log error
            self._log_error(error_context)

            # Update error tracking
            self._update_error_tracking(error_context)

            # Check for shutdown conditions
            if self._check_shutdown_conditions(error_context):
                self._initiate_shutdown(error_context)

            # Attempt recovery
            self._attempt_recovery(error_context)

            # Emit error event if event manager is available
            if self.event_manager:
                self._emit_error_event(error_context)

            # Execute callbacks
            self._execute_error_callbacks(error_context)

            return error_context

    def _create_error_context(
        self,
        error: Exception | str,
        component_name: str,
        strategy_name: str | None = None,
        order_id: str | None = None,
        symbol: str | None = None,
        additional_data: dict[str, Any] | None = None,
    ) -> ErrorContext:
        """Create error context from exception or error string"""
        # Handle string errors (convert to a generic error message)
        if isinstance(error, str):
            category = ErrorCategory.UNKNOWN
            severity = ErrorSeverity.MEDIUM
            module_name = None
            function_name = None
        else:
            # Determine category and severity for Exception objects
            if isinstance(error, SpyderError):
                category = error.category
                severity = error.severity
            else:
                category = self._categorize_error(error)
                severity = self._assess_severity(error, category)

            # Get module and function info from traceback
            str(error)
            if hasattr(error, "__traceback__") and error.__traceback__ is not None:
                tb = traceback.extract_tb(error.__traceback__)
                if tb:
                    last_frame = tb[-1]
                    module_name = last_frame.filename.split("/")[-1].replace(".py", "")
                    function_name = last_frame.name
                else:
                    module_name = None
                    function_name = None
            else:
                module_name = None
                function_name = None

        return ErrorContext(
            category=category,
            severity=severity,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            component_name=component_name,
            strategy_name=strategy_name,
            order_id=order_id,
            symbol=symbol,
            additional_data=additional_data or {},
            module_name=module_name,
            function_name=function_name,
        )

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error based on type and content"""
        error_msg = str(error).lower()

        # Connection errors
        if any(
            keyword in error_msg
            for keyword in ["connection", "network", "timeout", "socket"]
        ):
            return ErrorCategory.CONNECTION

        # Data errors
        elif any(
            keyword in error_msg for keyword in ["data", "parsing", "format", "invalid"]
        ):
            return ErrorCategory.DATA

        # Execution errors
        elif any(
            keyword in error_msg for keyword in ["order", "execution", "fill", "trade"]
        ):
            return ErrorCategory.EXECUTION

        # Risk errors
        elif any(
            keyword in error_msg for keyword in ["risk", "margin", "exposure", "limit"]
        ):
            return ErrorCategory.RISK

        # System errors
        elif any(
            keyword in error_msg
            for keyword in ["system", "memory", "process", "thread"]
        ):
            return ErrorCategory.SYSTEM

        # Strategy errors
        elif any(
            keyword in error_msg for keyword in ["strategy", "signal", "indicator"]
        ):
            return ErrorCategory.STRATEGY

        else:
            return ErrorCategory.UNKNOWN

    def _assess_severity(
        self, error: Exception, category: ErrorCategory
    ) -> ErrorSeverity:
        """Assess error severity"""
        # Critical categories
        if category in [ErrorCategory.RISK, ErrorCategory.SYSTEM]:
            return ErrorSeverity.CRITICAL

        # High severity categories
        elif category in [ErrorCategory.CONNECTION, ErrorCategory.EXECUTION]:
            return ErrorSeverity.HIGH

        # Check for specific error types
        elif isinstance(error, (MemoryError, SystemError)):
            return ErrorSeverity.CRITICAL

        elif isinstance(error, (ValueError, TypeError, KeyError)):
            return ErrorSeverity.MEDIUM

        else:
            return ErrorSeverity.LOW

    # ==========================================================================
    # ERROR TRACKING
    # ==========================================================================
    def _update_error_tracking(self, error_context: ErrorContext):
        """Update error tracking metrics"""
        # Add to history
        self.error_history.append(error_context)

        # Update counts
        self.error_counts[error_context.error_type] += 1

        # Track strategy-specific errors
        if error_context.strategy_name:
            self.strategy_errors[error_context.strategy_name].append(error_context)

        # Update critical error count
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.critical_error_count += 1

    def get_error_rate(self, window_seconds: int = ERROR_RATE_WINDOW) -> float:
        """Calculate current error rate (errors per minute)"""
        with self._lock:
            cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
            recent_errors = [
                e for e in self.error_history if _is_after(e.timestamp, cutoff_time)
            ]

            if window_seconds > 0:
                return len(recent_errors) * 60 / window_seconds
            return 0.0

    # ==========================================================================
    # SHUTDOWN CONDITIONS
    # ==========================================================================
    def _check_shutdown_conditions(self, error_context: ErrorContext) -> bool:
        """Check if shutdown conditions are met"""
        # System shutdown for critical errors
        if self.critical_error_count >= SYSTEM_SHUTDOWN_THRESHOLD:
            return True

        # Strategy shutdown for repeated errors
        if error_context.strategy_name:
            strategy_errors = self.strategy_errors[error_context.strategy_name]
            recent_errors = [
                e
                for e in strategy_errors
                if _is_after(
                    e.timestamp, datetime.now(timezone.utc) - timedelta(minutes=5)
                )
            ]

            if len(recent_errors) >= STRATEGY_SHUTDOWN_THRESHOLD:
                return True

        # High error rate
        return self.get_error_rate() > MAX_ERROR_RATE

    def _initiate_shutdown(self, error_context: ErrorContext):
        """Initiate shutdown based on error context"""
        if error_context.strategy_name:
            self.logger.critical(
                "Initiating strategy shutdown: %s", error_context.strategy_name
            )
            self._shutdown_strategy(error_context.strategy_name, error_context)
        else:
            self.logger.critical("Initiating system shutdown due to critical errors")
            self._shutdown_system(error_context)

    def _shutdown_strategy(self, strategy_name: str, error_context: ErrorContext):
        """Shutdown a specific strategy"""
        # Emit event if event manager is available
        if self.event_manager:
            self._emit_strategy_shutdown_event(
                strategy_name, "Critical errors", error_context
            )

        # Execute shutdown callbacks
        for callback in self.shutdown_callbacks:
            try:
                callback("strategy", strategy_name, error_context)
            except Exception as e:
                self.logger.error("Error in shutdown callback: %s", e)

    def _shutdown_system(self, error_context: ErrorContext):
        """Shutdown the entire system"""
        # Emit event if event manager is available
        if self.event_manager:
            self._emit_system_shutdown_event("Critical system errors", error_context)

        # Execute shutdown callbacks
        for callback in self.shutdown_callbacks:
            try:
                callback("system", None, error_context)
            except Exception as e:
                self.logger.error("Error in shutdown callback: %s", e)

    # ==========================================================================
    # RECOVERY
    # ==========================================================================
    def _attempt_recovery(self, error_context: ErrorContext) -> bool:
        """Attempt to recover from error"""
        strategy_key = error_context.error_type

        if strategy_key not in self.recovery_strategies:
            strategy_key = error_context.category.value

        if strategy_key in self.recovery_strategies:
            recovery_strategy = self.recovery_strategies[strategy_key]

            if error_context.recovery_attempts < recovery_strategy.max_retries:
                error_context.recovery_attempts += 1

                # Calculate delay with backoff
                recovery_strategy.retry_delay * (
                    recovery_strategy.backoff_multiplier
                    ** (error_context.recovery_attempts - 1)
                )

                self.logger.info(
                    f"Attempting recovery for {error_context.error_type} "
                    f"(attempt {error_context.recovery_attempts}/{recovery_strategy.max_retries})"
                )

                # Execute recovery action
                success = self._execute_recovery_action(
                    recovery_strategy, error_context
                )

                if success:
                    error_context.resolved = True
                    error_context.resolution_time = datetime.now(timezone.utc)
                    self.logger.info(
                        "Recovery successful for %s", error_context.error_type
                    )

                return success

        return False

    def _execute_recovery_action(
        self, strategy: RecoveryStrategy, error_context: ErrorContext
    ) -> bool:
        """Execute specific recovery action"""
        try:
            if strategy.callback:
                return strategy.callback(error_context)

            # Default recovery actions
            if strategy.action == RecoveryAction.RETRY:
                time.sleep(strategy.retry_delay)  # thread-safe: time.sleep() intentional
                return True

            elif strategy.action == RecoveryAction.RECONNECT:
                # Attempt to reconnect component
                if error_context.component_name in self.components:
                    component_ref = self.components[error_context.component_name]
                    component = component_ref()
                    if component and hasattr(component, "reconnect"):
                        return component.reconnect()

            elif strategy.action == RecoveryAction.RESTART_COMPONENT:
                # Restart component
                if error_context.component_name in self.components:
                    component_ref = self.components[error_context.component_name]
                    component = component_ref()
                    if component and hasattr(component, "restart"):
                        return component.restart()

            return False

        except Exception as e:
            self.logger.error("Error during recovery action: %s", e)
            return False

    # ==========================================================================
    # LOGGING
    # ==========================================================================
    def _log_error(self, error_context: ErrorContext):
        """Log error with appropriate level"""
        log_message = (
            f"[{error_context.category.value.upper()}] "
            f"{error_context.error_type}: {error_context.error_message}"
        )

        if error_context.strategy_name:
            log_message += f" (Strategy: {error_context.strategy_name})"

        if error_context.module_name and error_context.function_name:
            log_message += f" (Location: {error_context.module_name}::{error_context.function_name})"  # noqa: E501

        # Log based on severity
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message)
        elif error_context.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)

        # Log stack trace for high severity errors
        if (
            error_context.severity.value >= ErrorSeverity.HIGH.value
            and error_context.stack_trace
        ):
            self.logger.debug(
                "Stack trace for %s:\n%s", error_context.error_id, error_context.stack_trace
            )

    # ==========================================================================
    # EVENT EMISSION (ONLY IF EVENT MANAGER IS AVAILABLE)
    # ==========================================================================
    def _emit_error_event(self, error_context: ErrorContext):
        """Emit error event for monitoring systems"""
        if not self.event_manager:
            return

        try:
            from SpyderA_Core.SpyderA05_EventManager import EventType

            event_data = {
                "error_id": error_context.error_id,
                "category": error_context.category.value,
                "severity": error_context.severity.value,
                "error_type": error_context.error_type,
                "strategy_name": error_context.strategy_name,
                "module_name": error_context.module_name,
                "function_name": error_context.function_name,
                "timestamp": error_context.timestamp.isoformat(),
            }

            self.event_manager.emit_event(EventType.ERROR_OCCURRED, event_data)

        except Exception as e:
            self.logger.warning("Failed to emit error event: %s", e)

    def _emit_strategy_shutdown_event(
        self, strategy_name: str, reason: str, error_context: ErrorContext
    ):
        """Emit strategy shutdown event"""
        if not self.event_manager:
            return

        try:
            from SpyderA_Core.SpyderA05_EventManager import EventType

            event_data = {
                "strategy_name": strategy_name,
                "shutdown_reason": reason,
                "trigger_error_id": error_context.error_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.event_manager.emit_event(EventType.STRATEGY_SHUTDOWN, event_data)

        except Exception as e:
            self.logger.warning("Failed to emit strategy shutdown event: %s", e)

    def _emit_system_shutdown_event(self, reason: str, error_context: ErrorContext):
        """Emit system shutdown event"""
        if not self.event_manager:
            return

        try:
            from SpyderA_Core.SpyderA05_EventManager import EventType

            event_data = {
                "shutdown_reason": reason,
                "trigger_error_id": error_context.error_id,
                "critical_error_count": self.critical_error_count,
                "error_rate": self.get_error_rate(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.event_manager.emit_event(EventType.SYSTEM_SHUTDOWN, event_data)

        except Exception as e:
            self.logger.warning("Failed to emit system shutdown event: %s", e)

    # ==========================================================================
    # CALLBACKS
    # ==========================================================================
    def _execute_error_callbacks(self, error_context: ErrorContext):
        """Execute registered error callbacks"""
        for callback in self.error_callbacks:
            try:
                callback(error_context)
            except Exception as e:
                self.logger.error("Error in callback execution: %s", e)

    def register_error_callback(self, callback: Callable[[ErrorContext], None]):
        """Register error callback"""
        self.error_callbacks.append(callback)

    def register_shutdown_callback(
        self, callback: Callable[[str, str | None, ErrorContext], None]
    ):
        """Register shutdown callback"""
        self.shutdown_callbacks.append(callback)

    def register_component(self, name: str, component: Any):
        """Register component for recovery operations"""
        self.components[name] = weakref.ref(component)

    # ==========================================================================
    # REPORTING
    # ==========================================================================
    def get_error_summary(self) -> dict[str, Any]:
        """Get error summary statistics"""
        with self._lock:
            return {
                "total_errors": len(self.error_history),
                "critical_errors": self.critical_error_count,
                "error_rate": self.get_error_rate(),
                "error_types": dict(self.error_counts),
                "strategies_with_errors": list(self.strategy_errors.keys()),
                "recent_errors": [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "type": e.error_type,
                        "category": e.category.value,
                        "severity": e.severity.value,
                        "resolved": e.resolved,
                    }
                    for e in list(self.error_history)[-10:]
                ],
            }

    def get_strategy_error_report(self, strategy_name: str) -> dict[str, Any]:
        """Get error report for specific strategy"""
        with self._lock:
            if strategy_name not in self.strategy_errors:
                return {"error_count": 0, "errors": []}

            errors = self.strategy_errors[strategy_name]
            return {
                "error_count": len(errors),
                "critical_count": sum(
                    1 for e in errors if e.severity == ErrorSeverity.CRITICAL
                ),
                "resolved_count": sum(1 for e in errors if e.resolved),
                "error_types": pd.Series([e.error_type for e in errors])
                .value_counts()
                .to_dict(),
                "recent_errors": [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "type": e.error_type,
                        "message": e.error_message,
                        "resolved": e.resolved,
                    }
                    for e in errors[-5:]
                ],
            }

    # ==========================================================================
    # DECORATORS
    # ==========================================================================
    @staticmethod
    def error_handler(component_name: str, strategy_name: str | None = None):
        """
        Decorator for automatic error handling.

        Usage:
            @SpyderErrorHandler.error_handler("OrderManager", "IronCondor")
            def place_order(self, order):
                # function code
        """

        def decorator(func):
            @functools.wraps(func)
            def wrapper(self, *args, **kwargs):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    # Get error handler instance
                    if hasattr(self, "error_handler"):
                        error_handler = self.error_handler
                    else:
                        # Use singleton if available
                        error_handler = get_error_handler()

                    # Handle error
                    error_context = error_handler.handle_error(
                        e, component_name, strategy_name
                    )

                    # Re-raise if not resolved
                    if not error_context.resolved:
                        raise

                    return None

            return wrapper

        return decorator


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
_error_handler_instance: SpyderErrorHandler | None = None
_error_handler_lock = threading.Lock()


def get_error_handler() -> SpyderErrorHandler:
    """Get singleton error handler instance"""
    global _error_handler_instance

    with _error_handler_lock:
        if _error_handler_instance is None:
            _error_handler_instance = SpyderErrorHandler()

        return _error_handler_instance


def reset_error_handler():
    """Reset singleton instance (for testing)"""
    global _error_handler_instance
    with _error_handler_lock:
        _error_handler_instance = None


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing

    # Create error handler
    handler = SpyderErrorHandler()

    # Test different error types
    try:
        raise ConnectionError("Failed to connect to broker")
    except Exception as e:
        context = handler.handle_error(e, "BrokerConnection")

    try:
        raise RiskError("Position limit exceeded", symbol="SPY")
    except Exception as e:
        context = handler.handle_error(
            e, "RiskManager", strategy_name="IronCondor", symbol="SPY"
        )

    summary = handler.get_error_summary()

