#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderU02_ErrorHandler.py
Group: U (Utilities)
Purpose: Centralized error handling and recovery

Description:
This module provides comprehensive error handling capabilities for the Spyder
trading system. It implements custom exception classes, error recovery strategies,
error tracking and reporting, and integration with the logging and alert systems.
The error handler ensures graceful degradation of functionality and prevents
cascading failures in critical trading operations.

Author: Mohamed Talib
Created: 2025-01-27
Version: 1.4
"""

# =============================================================================
# Standard Library Imports
# =============================================================================
from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Type, Callable, List
from dataclasses import dataclass, field
from collections import deque, defaultdict
import threading
import traceback
import functools
import time

# =============================================================================
# Local Imports
# =============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# =============================================================================
# Constants
# =============================================================================
MAX_ERROR_HISTORY = 1000
ERROR_RATE_WINDOW = 300  # 5 minutes
MAX_ERROR_RATE = 10  # Max errors per window
RETRY_DELAYS = [1, 5, 15, 60, 300]  # Seconds
CRITICAL_ERROR_THRESHOLD = 5  # Critical errors before shutdown


# =============================================================================
# Enumerations
# =============================================================================
class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()
    FATAL = auto()


class ErrorCategory(Enum):
    """Error categories."""

    CONNECTION = "connection"
    DATA = "data"
    TRADING = "trading"
    RISK = "risk"
    SYSTEM = "system"
    CONFIGURATION = "configuration"
    VALIDATION = "validation"
    EXTERNAL = "external"


class RecoveryAction(Enum):
    """Error recovery actions."""

    RETRY = "retry"
    RECONNECT = "reconnect"
    RESTART = "restart"
    FAILOVER = "failover"
    ALERT = "alert"
    IGNORE = "ignore"
    SHUTDOWN = "shutdown"


# =============================================================================
# Custom Exceptions
# =============================================================================
class SpyderError(Exception):
    """Base exception class for Spyder system."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.timestamp = datetime.now()


class ConnectionError(SpyderError):
    """Raised when connection issues occur."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.CONNECTION, ErrorSeverity.HIGH, details)


class TradingError(SpyderError):
    """Raised when trading operations fail."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.TRADING, ErrorSeverity.HIGH, details)


# Alias for backwards compatibility
TradingSystemError = TradingError


class RiskLimitExceeded(SpyderError):
    """Raised when risk limits are breached."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.RISK, ErrorSeverity.CRITICAL, details)


class DataError(SpyderError):
    """Raised when data issues occur."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.DATA, ErrorSeverity.MEDIUM, details)


class ConfigurationError(SpyderError):
    """Raised when configuration issues occur."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message, ErrorCategory.CONFIGURATION, ErrorSeverity.HIGH, details
        )


class ValidationError(SpyderError):
    """Raised when validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, ErrorCategory.VALIDATION, ErrorSeverity.LOW, details)


# =============================================================================
# Data Classes
# =============================================================================
@dataclass
class ErrorRecord:
    """Record of an error occurrence."""

    error_id: str
    timestamp: datetime
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    traceback: str
    context: Dict[str, Any] = field(default_factory=dict)
    recovery_attempted: bool = False
    recovery_successful: bool = False


@dataclass
class ErrorStatistics:
    """Error statistics tracking."""

    total_errors: int = 0
    errors_by_category: Dict[ErrorCategory, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    errors_by_severity: Dict[ErrorSeverity, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    error_rate: float = 0.0
    last_error_time: Optional[datetime] = None
    critical_error_count: int = 0


# =============================================================================
# Main Class
# =============================================================================
class SpyderErrorHandler:
    """Centralized error handling system."""

    def __init__(self):
        """Initialize error handler."""
        self.logger = SpyderLogger.get_logger(__name__)

        # Error tracking
        self.error_history = deque(maxlen=MAX_ERROR_HISTORY)
        self.error_stats = ErrorStatistics()
        self.error_rate_window = deque()

        # Recovery strategies
        self.recovery_strategies = self._init_recovery_strategies()

        # Thread safety
        self._lock = threading.Lock()

        # Error handlers
        self.error_handlers: Dict[Type[Exception], Callable] = {}
        self._register_default_handlers()

        # Initialize event manager integration (safely)
        self.event_manager = None
        try:
            from SpyderA_Core.SpyderA05_EventManager import get_event_manager

            self.event_manager = get_event_manager()

            # Subscribe to system events with explicit positional arguments
            if hasattr(self.event_manager, "subscribe"):
                try:
                    # Use explicit positional arguments to avoid conflicts
                    success1 = self.event_manager.subscribe(
                        "SYSTEM_ERROR", self._handle_system_event
                    )
                    success2 = self.event_manager.subscribe(
                        "CRITICAL_ERROR", self._handle_system_event
                    )

                    if success1 and success2:
                        self.logger.debug("Event manager subscriptions successful")
                    else:
                        self.logger.debug("Some event subscriptions failed")

                except Exception as sub_error:
                    self.logger.debug(f"Event subscription failed: {sub_error}")

        except ImportError:
            self.logger.debug("Event manager not available")
        except Exception as e:
            self.logger.warning(f"Could not initialize event manager integration: {e}")

        self.logger.info("Error handler initialized")

    def _handle_system_event(self, event):
        """Handle system events."""
        try:
            # Handle the event data safely
            if hasattr(event, "type"):
                if hasattr(event.type, "value"):
                    event_type = event.type.value
                else:
                    event_type = str(event.type)
            else:
                event_type = str(event)

            if hasattr(event, "data"):
                event_data = event.data
            else:
                event_data = str(event)

            self.logger.debug(f"Received event: {event_type} - {event_data}")

            # Handle specific event types
            if "error" in event_type.lower():
                self.logger.debug(f"Received error event: {event_data}")
            elif "system" in event_type.lower():
                self.logger.debug(f"Received system event: {event_data}")

        except Exception as e:
            self.logger.error(f"Error handling system event: {e}")

    def _init_recovery_strategies(self) -> Dict[ErrorCategory, List[RecoveryAction]]:
        """Initialize recovery strategies by category."""
        return {
            ErrorCategory.CONNECTION: [
                RecoveryAction.RETRY,
                RecoveryAction.RECONNECT,
                RecoveryAction.ALERT,
            ],
            ErrorCategory.DATA: [
                RecoveryAction.RETRY,
                RecoveryAction.FAILOVER,
                RecoveryAction.ALERT,
            ],
            ErrorCategory.TRADING: [RecoveryAction.ALERT, RecoveryAction.RETRY],
            ErrorCategory.RISK: [RecoveryAction.ALERT, RecoveryAction.SHUTDOWN],
            ErrorCategory.SYSTEM: [RecoveryAction.RESTART, RecoveryAction.ALERT],
            ErrorCategory.CONFIGURATION: [RecoveryAction.ALERT],
            ErrorCategory.VALIDATION: [RecoveryAction.IGNORE, RecoveryAction.ALERT],
            ErrorCategory.EXTERNAL: [RecoveryAction.RETRY, RecoveryAction.FAILOVER],
        }

    def _register_default_handlers(self) -> None:
        """Register default error handlers."""
        self.register_handler(ConnectionError, self._handle_connection_error)
        self.register_handler(TradingError, self._handle_trading_error)
        self.register_handler(RiskLimitExceeded, self._handle_risk_error)
        self.register_handler(DataError, self._handle_data_error)

    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        critical: bool = False,
    ) -> bool:
        """Handle an error with appropriate recovery strategy."""
        with self._lock:
            try:                # Only process errors if system is still running
                if (
                    hasattr(self, "_shutdown_in_progress")
                    and self._shutdown_in_progress
                ):
                    return  # Skip error processing during shutdown

                # Create error record
                error_record = self._create_error_record(error, context)

                # Update statistics
                self._update_statistics(error_record)

                # Log error
                self._log_error(error_record)

                # Store in history
                self.error_history.append(error_record)

                # Determine recovery strategy
                recovery_actions = self._determine_recovery_actions(error_record)

                # Execute recovery
                recovery_successful = self._execute_recovery(
                    error_record, recovery_actions
                )

                # Update record
                error_record.recovery_attempted = True
                error_record.recovery_successful = recovery_successful

                return recovery_successful

            except Exception as e:
                # Don't let error handler errors crash the shutdown
                print(f"Error handler failed: {e}")
                return False

    def register_handler(self, error_type: Type[Exception], handler: Callable) -> None:
        """Register custom error handler."""
        self.error_handlers[error_type] = handler
        self.logger.debug(f"Registered handler for {error_type.__name__}")

    def get_error_statistics(self) -> ErrorStatistics:
        """Get current error statistics."""
        with self._lock:
            return self.error_stats

    def get_recent_errors(self, count: int = 10) -> List[ErrorRecord]:
        """Get recent errors."""
        with self._lock:
            return list(self.error_history)[-count:]

    def get_circuit_breaker(self, name: str):
        """Get circuit breaker instance (placeholder)."""

        # Simplified circuit breaker for the decorator
        class SimpleCircuitBreaker:
            def __init__(self):
                self.failure_threshold = 5
                self.recovery_timeout = 60

            def call(self, func, *args, **kwargs):
                return func(*args, **kwargs)

        return SimpleCircuitBreaker()

    def _create_error_record(
        self, error: Exception, context: Optional[Dict[str, Any]]
    ) -> ErrorRecord:
        """Create error record from exception."""
        # Determine category and severity
        if isinstance(error, SpyderError):
            category = error.category
            severity = error.severity
        else:
            category = ErrorCategory.SYSTEM
            severity = ErrorSeverity.MEDIUM

        # Generate error ID
        error_id = f"ERR_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        # Get traceback
        tb = traceback.format_exc()

        # Create record
        return ErrorRecord(
            error_id=error_id,
            timestamp=datetime.now(),
            category=category,
            severity=severity,
            message=str(error),
            traceback=tb,
            context=context or {},
        )

    def _update_statistics(self, error_record: ErrorRecord) -> None:
        """Update error statistics."""
        self.error_stats.total_errors += 1
        self.error_stats.errors_by_category[error_record.category] += 1
        self.error_stats.errors_by_severity[error_record.severity] += 1
        self.error_stats.last_error_time = error_record.timestamp

        if error_record.severity == ErrorSeverity.CRITICAL:
            self.error_stats.critical_error_count += 1

    def _log_error(self, error_record: ErrorRecord) -> None:
        """Log error with appropriate level."""
        log_message = f"Error {error_record.error_id}: {error_record.message} [{error_record.category.value}]"

        if error_record.severity == ErrorSeverity.LOW:
            self.logger.debug(log_message)
        elif error_record.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        elif error_record.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message)
        elif error_record.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.FATAL]:
            self.logger.critical(log_message)

    def _determine_recovery_actions(
        self, error_record: ErrorRecord
    ) -> List[RecoveryAction]:
        """Determine recovery actions for error."""
        return self.recovery_strategies.get(error_record.category, [])

    def _execute_recovery(
        self, error_record: ErrorRecord, actions: List[RecoveryAction]
    ) -> bool:
        """Execute recovery actions."""
        for action in actions:
            try:
                if action == RecoveryAction.ALERT:
                    self._send_alert(error_record)
                    return True
                elif action == RecoveryAction.IGNORE:
                    return True
            except Exception as e:
                self.logger.error(f"Recovery action {action} failed: {str(e)}")

        return False

    def _send_alert(self, error_record: ErrorRecord) -> None:
        """Send alert for error."""
        self.logger.info(f"Sending alert for error {error_record.error_id}")

    def _handle_connection_error(self, error: ConnectionError) -> bool:
        """Handle connection errors."""
        self.logger.error(f"Connection error: {error}")
        return False

    def _handle_trading_error(self, error: TradingError) -> bool:
        """Handle trading errors."""
        self.logger.error(f"Trading error: {error}")
        return False

    def _handle_risk_error(self, error: RiskLimitExceeded) -> bool:
        """Handle risk limit errors."""
        self.logger.critical(f"Risk limit exceeded: {error}")
        return False

    def _handle_data_error(self, error: DataError) -> bool:
        """Handle data errors."""
        self.logger.error(f"Data error: {error}")
        return False


# =============================================================================
# Decorators
# =============================================================================
def error_handler(
    category: ErrorCategory = ErrorCategory.SYSTEM,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    retry_count: int = 0,
    retry_delay: int = 1,
):
    """
    Decorator for automatic error handling.

    Args:
        category: Error category
        severity: Error severity
        retry_count: Number of retries
        retry_delay: Delay between retries in seconds
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            handler = get_error_handler()
            last_error = None

            for attempt in range(retry_count + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # Create custom error if needed
                    if not isinstance(e, SpyderError):
                        e = SpyderError(
                            str(e),
                            category=category,
                            severity=severity,
                            details={"function": func.__name__, "attempt": attempt + 1},
                        )

                    # Handle error
                    if handler.handle_error(e, {"attempt": attempt + 1}):
                        # Error handled, retry if attempts remain
                        if attempt < retry_count:
                            import time

                            time.sleep(retry_delay * (attempt + 1))
                            continue

                    # Re-raise if no more attempts
                    raise

            # Should not reach here
            if last_error:
                raise last_error

        return wrapper

    return decorator


def circuit_breaker(failure_threshold: int = 5, recovery_timeout: int = 60):
    """
    Decorator for circuit breaker pattern.

    Args:
        failure_threshold: Failures before opening
        recovery_timeout: Seconds before attempting reset
    """

    def decorator(func):
        breaker_name = f"{func.__module__}.{func.__name__}"
        handler = get_error_handler()
        breaker = handler.get_circuit_breaker(breaker_name)
        breaker.failure_threshold = failure_threshold
        breaker.recovery_timeout = recovery_timeout

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# Module Functions
# =============================================================================
def get_error_handler() -> SpyderErrorHandler:
    """
    Get singleton error handler instance.

    Returns:
        SpyderErrorHandler: Error handler instance
    """
    global _ERROR_HANDLER_INSTANCE
    if _ERROR_HANDLER_INSTANCE is None:
        _ERROR_HANDLER_INSTANCE = SpyderErrorHandler()
    return _ERROR_HANDLER_INSTANCE


# =============================================================================
# Module Initialization
# =============================================================================
_ERROR_HANDLER_INSTANCE: Optional[SpyderErrorHandler] = None
