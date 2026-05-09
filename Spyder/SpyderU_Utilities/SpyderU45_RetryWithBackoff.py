#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: Spyder.SpyderU_Utilities
Module: SpyderU45_RetryWithBackoff.py
Purpose: Exponential-backoff retry decorator for sync and async callables

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-31

Module Description:
    Provides retry logic with configurable exponential back-off and jitter for
    transient failures in external API calls (Tradier, Massive, etc.).

    Works with both regular (sync) and async functions.  Designed to complement
    SpyderU41_CircuitBreaker — use retry for transient network errors and circuit
    breaker for sustained service failures.

    Usage:
        # Decorator form (async)
        @retry_async(max_attempts=3, base_delay=1.0, exceptions=(TradierAPIError,))
        async def fetch_quotes(symbol: str) -> dict:
            ...

        # Decorator form (sync)
        @retry_sync(max_attempts=3, base_delay=0.5)
        def fetch_historical(symbol: str) -> pd.DataFrame:
            ...

        # Inline (async)
        result = await retry_call_async(fetch_quotes, "SPY", max_attempts=3)

        # Inline (sync)
        result = retry_call_sync(fetch_historical, "SPY", max_attempts=3)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import functools
import random
import threading
import time
from typing import Any
from collections.abc import Callable

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import get_logger

logger = get_logger(__name__)


# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_MAX_ATTEMPTS: int = 3
DEFAULT_BASE_DELAY: float = 1.0   # seconds
DEFAULT_MAX_DELAY: float = 60.0   # seconds
DEFAULT_BACKOFF_FACTOR: float = 2.0
DEFAULT_JITTER: float = 0.1       # ±10 % random jitter


# ==============================================================================
# HELPERS
# ==============================================================================

def _compute_delay(
    attempt: int,
    base_delay: float,
    backoff_factor: float,
    max_delay: float,
    jitter: float,
) -> float:
    """Return delay (seconds) for *attempt* (0-indexed, so first retry = attempt 1)."""
    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
    if jitter > 0:
        delay *= 1.0 + random.uniform(-jitter, jitter)
    return max(0.0, delay)


def _should_retry(exc: BaseException, exceptions: tuple[type, ...]) -> bool:
    return isinstance(exc, exceptions)


# ==============================================================================
# ASYNC RETRY
# ==============================================================================

def retry_async(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    jitter: float = DEFAULT_JITTER,
    exceptions: tuple[type, ...] = (Exception,),
) -> Callable:
    """
    Decorator: retry an async function with exponential back-off.

    Args:
        max_attempts:   Total calls allowed (1 = no retry).
        base_delay:     Initial delay in seconds before first retry.
        max_delay:      Upper bound on delay (seconds).
        backoff_factor: Multiplicative factor applied after each attempt.
        jitter:         Fractional random noise added to delay (0 = none).
        exceptions:     Exception types that trigger a retry.

    Example::

        @retry_async(max_attempts=3, exceptions=(ConnectionError, TimeoutError))
        async def get_quote(symbol: str) -> dict:
            return await tradier.get_quote(symbol)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except BaseException as exc:
                    if not _should_retry(exc, exceptions):
                        raise
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        delay = _compute_delay(
                            attempt, base_delay, backoff_factor, max_delay, jitter
                        )
                        logger.warning(
                            f"{func.__qualname__}: attempt {attempt + 1}/{max_attempts} "
                            f"failed ({exc.__class__.__name__}: {exc}); "
                            f"retrying in {delay:.2f}s"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__qualname__}: all {max_attempts} attempts failed; "
                            f"last error: {exc.__class__.__name__}: {exc}"
                        )
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


async def retry_call_async(
    func: Callable,
    *args: Any,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    jitter: float = DEFAULT_JITTER,
    exceptions: tuple[type, ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    """
    Call an async *func* with exponential back-off retry.

    Inline alternative to the ``@retry_async`` decorator when you cannot
    annotate the function definition.
    """
    decorated = retry_async(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
        exceptions=exceptions,
    )(func)
    return await decorated(*args, **kwargs)


# ==============================================================================
# SYNC RETRY
# ==============================================================================

def retry_sync(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    jitter: float = DEFAULT_JITTER,
    exceptions: tuple[type, ...] = (Exception,),
    stop_event: threading.Event | None = None,
) -> Callable:
    """
    Decorator: retry a synchronous function with exponential back-off.

    Same parameters as :func:`retry_async` but for regular (blocking) functions.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except BaseException as exc:
                    if not _should_retry(exc, exceptions):
                        raise
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        delay = _compute_delay(
                            attempt, base_delay, backoff_factor, max_delay, jitter
                        )
                        logger.warning(
                            f"{func.__qualname__}: attempt {attempt + 1}/{max_attempts} "
                            f"failed ({exc.__class__.__name__}: {exc}); "
                            f"retrying in {delay:.2f}s"
                        )
                        time.sleep(delay) if stop_event is None else stop_event.wait(delay)
                    else:
                        logger.error(
                            f"{func.__qualname__}: all {max_attempts} attempts failed; "
                            f"last error: {exc.__class__.__name__}: {exc}"
                        )
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def retry_call_sync(
    func: Callable,
    *args: Any,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    jitter: float = DEFAULT_JITTER,
    exceptions: tuple[type, ...] = (Exception,),
    **kwargs: Any,
) -> Any:
    """
    Call a synchronous *func* with exponential back-off retry.

    Inline alternative to the ``@retry_sync`` decorator.
    """
    decorated = retry_sync(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=jitter,
        exceptions=exceptions,
    )(func)
    return decorated(*args, **kwargs)


# ==============================================================================
# CONVENIENCE PRE-CONFIGURED INSTANCES
# ==============================================================================

#: Retry policy for Tradier REST API calls: 3 attempts, 1-8s back-off.
tradier_retry = retry_async(
    max_attempts=3,
    base_delay=1.0,
    max_delay=8.0,
    exceptions=(Exception,),
)

#: Retry policy for market-data feed calls (Tradier / Massive).
datafeed_retry = retry_async(
    max_attempts=4,
    base_delay=2.0,
    max_delay=30.0,
    exceptions=(Exception,),
)

#: Retry policy for synchronous HTTP helpers.
http_retry = retry_sync(
    max_attempts=3,
    base_delay=1.0,
    max_delay=15.0,
    exceptions=(Exception,),
)


__all__ = [
    "retry_async",
    "retry_sync",
    "retry_call_async",
    "retry_call_sync",
    "tradier_retry",
    "datafeed_retry",
    "http_retry",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_BASE_DELAY",
    "DEFAULT_MAX_DELAY",
    "DEFAULT_BACKOFF_FACTOR",
    "DEFAULT_JITTER",
]
