#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Circuit Breaker

Module: SpyderU_Utilities/SpyderU41_CircuitBreaker.py
Purpose: Circuit breaker pattern for resilient API calls
Author: Spyder Development Team
Year Created: 2025
Last Updated: 2025-11-24

Module Description:
    Implements circuit breaker pattern to prevent cascading failures when
    external services (APIs) become unavailable. Automatically stops calling
    failing services and retries after cooldown period.

Features:
    - Three states: CLOSED (normal), OPEN (failing), HALF_OPEN (testing)
    - Configurable failure threshold
    - Automatic recovery testing
    - Async/await support
    - Decorator for easy integration
    - Per-service circuit breakers

Circuit Breaker States:
    CLOSED: Normal operation, requests pass through
    OPEN: Too many failures, requests fail immediately
    HALF_OPEN: Testing if service recovered, limited requests

Usage:
    # As decorator
    @circuit_breaker(failure_threshold=5, recovery_timeout=60)
    async def api_call():
        ...

    # Manual usage
    breaker = CircuitBreaker(failure_threshold=3)
    async with breaker:
        await risky_operation()
"""

import asyncio
import time
from typing import Optional, Callable, Any
from enum import Enum, auto
from dataclasses import dataclass, field
from functools import wraps
import threading
from SpyderU_Utilities.SpyderU01_Logger import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = auto()  # Normal operation
    OPEN = auto()  # Failing, reject requests
    HALF_OPEN = auto()  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: float = 60.0  # Seconds before testing recovery
    success_threshold: int = 2  # Successes in HALF_OPEN before closing
    timeout: Optional[float] = None  # Per-call timeout


class CircuitBreakerError(Exception):
    """Raised when circuit is open"""
    pass


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.

    Examples:
        # Create breaker
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)

        # Use with decorator
        @breaker.decorator
        async def api_call():
            ...

        # Use as context manager
        async with breaker:
            await make_api_call()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
        timeout: Optional[float] = None,
        name: Optional[str] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before testing recovery
            success_threshold: Successes needed to close circuit
            timeout: Per-call timeout in seconds
            name: Breaker name for logging
        """
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            success_threshold=success_threshold,
            timeout=timeout
        )

        self.name = name or "CircuitBreaker"
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.lock = threading.Lock()

        logger.info(f"{self.name} initialized (threshold={failure_threshold}, timeout={recovery_timeout}s)")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        # Check if circuit is open
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"{self.name} entering HALF_OPEN state")
                else:
                    raise CircuitBreakerError(
                        f"{self.name} is OPEN (too many failures, "
                        f"retry in {self._time_until_retry():.1f}s)"
                    )

        # Execute function
        try:
            # Apply timeout if configured
            if self.config.timeout:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout
                )
            else:
                result = await func(*args, **kwargs)

            # Success!
            self._on_success()
            return result

        except asyncio.TimeoutError as e:
            self._on_failure(e)
            raise
        except Exception as e:
            self._on_failure(e)
            raise

    def _on_success(self):
        """Handle successful call"""
        with self.lock:
            self.failure_count = 0

            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1

                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
                    logger.info(f"{self.name} recovered - circuit CLOSED")

    def _on_failure(self, exception: Exception):
        """Handle failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery test
                self.state = CircuitState.OPEN
                logger.warning(f"{self.name} recovery failed - circuit OPEN")

            elif self.failure_count >= self.config.failure_threshold:
                # Too many failures
                self.state = CircuitState.OPEN
                logger.error(
                    f"{self.name} opened after {self.failure_count} failures "
                    f"(last: {exception.__class__.__name__}: {exception})"
                )

    def _should_attempt_reset(self) -> bool:
        """Check if should attempt recovery"""
        if self.last_failure_time is None:
            return False

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.config.recovery_timeout

    def _time_until_retry(self) -> float:
        """Calculate time until retry attempt"""
        if self.last_failure_time is None:
            return 0.0

        elapsed = time.time() - self.last_failure_time
        remaining = self.config.recovery_timeout - elapsed
        return max(0.0, remaining)

    async def __aenter__(self):
        """Context manager entry"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise CircuitBreakerError(
                        f"{self.name} is OPEN (retry in {self._time_until_retry():.1f}s)"
                    )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is None:
            self._on_success()
        else:
            self._on_failure(exc_val)

    def decorator(self, func: Callable) -> Callable:
        """
        Decorator that wraps function with circuit breaker.

        Args:
            func: Async function to wrap

        Returns:
            Wrapped function
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.call(func, *args, **kwargs)

        return wrapper

    @property
    def is_open(self) -> bool:
        """Check if circuit is open"""
        return self.state == CircuitState.OPEN

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed"""
        return self.state == CircuitState.CLOSED

    def reset(self):
        """Manually reset circuit breaker"""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            logger.info(f"{self.name} manually reset")

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        with self.lock:
            return {
                "name": self.name,
                "state": self.state.name,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time,
                "is_open": self.is_open,
                "time_until_retry": self._time_until_retry() if self.is_open else 0.0
            }


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    success_threshold: int = 2,
    timeout: Optional[float] = None,
    name: Optional[str] = None
):
    """
    Decorator for creating circuit breaker.

    Args:
        failure_threshold: Failures before opening circuit
        recovery_timeout: Seconds before testing recovery
        success_threshold: Successes needed to close circuit
        timeout: Per-call timeout
        name: Breaker name

    Examples:
        @circuit_breaker(failure_threshold=5, recovery_timeout=60)
        async def api_call():
            # Protected API call
            ...
    """
    breaker = CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        success_threshold=success_threshold,
        timeout=timeout,
        name=name
    )

    def decorator(func: Callable) -> Callable:
        return breaker.decorator(func)

    return decorator


# Global circuit breakers for common services
_breakers = {}
_breakers_lock = threading.Lock()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get or create named circuit breaker.

    Args:
        name: Breaker name
        **kwargs: CircuitBreaker configuration

    Returns:
        CircuitBreaker instance
    """
    with _breakers_lock:
        if name not in _breakers:
            _breakers[name] = CircuitBreaker(name=name, **kwargs)
        return _breakers[name]


# Pre-configured breakers for known services
tradier_breaker = get_circuit_breaker(
    "tradier",
    failure_threshold=5,
    recovery_timeout=60.0,
    timeout=30.0
)

polygon_breaker = get_circuit_breaker(
    "polygon",
    failure_threshold=3,
    recovery_timeout=30.0,
    timeout=10.0
)


__all__ = [
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitState",
    "circuit_breaker",
    "get_circuit_breaker",
    "tradier_breaker",
    "polygon_breaker",
]
