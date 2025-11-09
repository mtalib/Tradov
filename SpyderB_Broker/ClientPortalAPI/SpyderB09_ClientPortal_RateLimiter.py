#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB09_ClientPortalAPI_RateLimiter.py
Purpose: Adaptive rate limiting for IBKR Client Portal Web API

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-11-08 Time: 22:10:00

Module Description:
    Implements token bucket rate limiting with adaptive backoff for IBKR
    Client Portal Web API requests. Provides both synchronous and asynchronous
    acquisition methods to accommodate different usage patterns.

    The rate limiter automatically adjusts to API response codes, reducing
    request rates when encountering 429 (Too Many Requests) errors and gradually
    recovering to optimal rates after sustained successful operation.

    Supports two different rate limits based on authentication method:
    - OAuth 2.0: 50 requests/second (institutional/production)
    - CP Gateway: 10 requests/second (development/paper trading)

    The adaptive behavior ensures API limits are respected while maximizing
    throughput during normal operation, with configurable backoff and recovery
    parameters for fine-tuning to specific use cases.

Module Constants:
    DEFAULT_CP_GATEWAY_RATE (int): Default rate limit for CP Gateway (10 req/sec)
    DEFAULT_OAUTH_RATE (int): Default rate limit for OAuth 2.0 (50 req/sec)
    DEFAULT_BACKOFF_FACTOR (float): Default rate reduction on 429 error (0.7-0.8)
    DEFAULT_RECOVERY_FACTOR (float): Default rate increase on success (1.05)
    DEFAULT_MIN_RATE (int): Minimum rate limit safety floor (1-5 req/sec)
    DEFAULT_CP_RECOVERY_THRESHOLD (int): Success count before CP Gateway recovery (50)
    DEFAULT_OAUTH_RECOVERY_THRESHOLD (int): Success count before OAuth recovery (100)
    SLEEP_INCREMENT (float): Maximum sleep time per iteration (0.1 seconds)

Change Log:
    2025-11-08 (v1.0.0):
        - Initial implementation with token bucket algorithm
        - Added adaptive rate limiting with backoff and recovery
        - Implemented both sync and async token acquisition
        - Added comprehensive statistics tracking
        - Created factory functions for OAuth and CP Gateway presets
        - Integrated with SpyderLogger for consistent logging

    2025-11-08 (v0.9.0):
        - Beta version for testing
        - Core rate limiting functionality implemented
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import time
import asyncio
from collections import deque
from threading import Lock
from typing import Optional
from dataclasses import dataclass

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CP_GATEWAY_RATE = 10  # requests per second
DEFAULT_OAUTH_RATE = 50  # requests per second
DEFAULT_BACKOFF_FACTOR = 0.8  # Rate reduction factor on 429 error
DEFAULT_RECOVERY_FACTOR = 1.05  # Rate increase factor on success
DEFAULT_MIN_RATE = 1  # Minimum rate limit (safety floor)
DEFAULT_CP_RECOVERY_THRESHOLD = 50  # Successful requests before recovery
DEFAULT_OAUTH_RECOVERY_THRESHOLD = 100  # Successful requests before recovery
SLEEP_INCREMENT = 0.1  # Maximum sleep time per iteration (seconds)

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = SpyderLogger.get_logger(__name__)

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class RateLimitStats:
    """
    Rate limiter statistics snapshot

    Attributes:
        tokens_available: Current available tokens in bucket
        max_tokens: Maximum bucket capacity
        current_rate: Current request rate (req/sec)
        limit_rate: Configured rate limit (req/sec)
        requests_last_window: Requests in current time window
        total_requests: Total requests processed
        total_throttled: Total times throttled (had to wait)
    """
    tokens_available: float
    max_tokens: int
    current_rate: float
    limit_rate: float
    requests_last_window: int
    total_requests: int
    total_throttled: int


# ==============================================================================
# BASE RATE LIMITER
# ==============================================================================

class RateLimiter:
    """
    Token bucket rate limiter for IBKR Client Portal API

    Implements the classic token bucket algorithm for smooth rate limiting.
    Tokens are refilled continuously based on elapsed time, allowing bursts
    up to the bucket capacity while maintaining the long-term average rate.

    The implementation is thread-safe and supports both blocking and non-blocking
    acquisition modes with optional timeout.

    Attributes:
        rate_limit: Maximum requests allowed per time window
        per_seconds: Time window in seconds
        tokens: Current available tokens
        last_refill: Last token refill timestamp
        lock: Thread lock for atomic operations
        request_history: Deque of recent request timestamps
        total_requests: Count of total requests processed
        total_throttled: Count of times had to wait for tokens

    Usage:
        >>> limiter = RateLimiter(rate_limit=10, per_seconds=1)
        >>> limiter.acquire()  # Blocks until token available
        >>> # Make API request
        >>> limiter.acquire(blocking=False)  # Returns False if no token
    """

    def __init__(self, rate_limit: int = DEFAULT_CP_GATEWAY_RATE, per_seconds: int = 1):
        """
        Initialize rate limiter

        Args:
            rate_limit: Maximum requests allowed per time window
            per_seconds: Time window in seconds
        """
        self.rate_limit = rate_limit
        self.per_seconds = per_seconds
        self.tokens = float(rate_limit)
        self.last_refill = time.time()
        self.lock = Lock()
        self.request_history = deque(maxlen=rate_limit * 10)
        self.total_requests = 0
        self.total_throttled = 0

        logger.debug(f"RateLimiter initialized: {rate_limit} req/{per_seconds}s")

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _refill_tokens(self):
        """
        Refill tokens based on elapsed time

        Tokens are added proportionally to elapsed time, up to the maximum
        bucket capacity (rate_limit).
        """
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens proportional to elapsed time
        tokens_to_add = (elapsed / self.per_seconds) * self.rate_limit
        self.tokens = min(self.rate_limit, self.tokens + tokens_to_add)
        self.last_refill = now

    # ==========================================================================
    # PUBLIC METHODS - SYNCHRONOUS
    # ==========================================================================

    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Acquire tokens for request

        Args:
            tokens: Number of tokens to acquire
            blocking: If True, wait until tokens available
            timeout: Maximum time to wait (seconds), None = wait forever

        Returns:
            True if tokens acquired, False if not available (non-blocking mode)

        Raises:
            TimeoutError: If timeout exceeded in blocking mode
        """
        start_time = time.time()

        while True:
            with self.lock:
                self._refill_tokens()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self.request_history.append(time.time())
                    self.total_requests += 1
                    return True

                if not blocking:
                    return False

                # Calculate wait time
                wait_time = (tokens - self.tokens) / (self.rate_limit / self.per_seconds)

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    raise TimeoutError(f"Rate limiter timeout after {elapsed:.2f}s")

            # Wait outside of lock
            self.total_throttled += 1
            time.sleep(min(wait_time, SLEEP_INCREMENT))  # Sleep in small increments

    # ==========================================================================
    # PUBLIC METHODS - ASYNCHRONOUS
    # ==========================================================================

    async def acquire_async(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        Async version of acquire

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait (seconds)

        Returns:
            True if tokens acquired

        Raises:
            TimeoutError: If timeout exceeded
        """
        start_time = time.time()

        while True:
            with self.lock:
                self._refill_tokens()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    self.request_history.append(time.time())
                    self.total_requests += 1
                    return True

                # Calculate wait time
                wait_time = (tokens - self.tokens) / (self.rate_limit / self.per_seconds)

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    raise TimeoutError(f"Rate limiter timeout after {elapsed:.2f}s")

            # Wait asynchronously
            self.total_throttled += 1
            await asyncio.sleep(min(wait_time, SLEEP_INCREMENT))

    # ==========================================================================
    # PUBLIC METHODS - STATISTICS
    # ==========================================================================

    def get_current_rate(self) -> float:
        """
        Get current request rate (requests/second)

        Returns:
            Current request rate
        """
        if len(self.request_history) < 2:
            return 0.0

        now = time.time()
        recent = [t for t in self.request_history if now - t < self.per_seconds]
        return len(recent) / self.per_seconds

    def get_stats(self) -> RateLimitStats:
        """
        Get rate limiter statistics

        Returns:
            RateLimitStats object with current statistics
        """
        with self.lock:
            self._refill_tokens()

            return RateLimitStats(
                tokens_available=self.tokens,
                max_tokens=self.rate_limit,
                current_rate=self.get_current_rate(),
                limit_rate=self.rate_limit / self.per_seconds,
                requests_last_window=len([
                    t for t in self.request_history
                    if time.time() - t < self.per_seconds
                ]),
                total_requests=self.total_requests,
                total_throttled=self.total_throttled
            )

    def reset(self):
        """Reset rate limiter to initial state"""
        with self.lock:
            self.tokens = float(self.rate_limit)
            self.last_refill = time.time()
            self.request_history.clear()
            self.total_requests = 0
            self.total_throttled = 0
            logger.debug("Rate limiter reset to initial state")

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (f"RateLimiter(rate={self.rate_limit}/{self.per_seconds}s, "
                f"tokens={stats.tokens_available:.2f}, "
                f"current_rate={stats.current_rate:.2f}/s)")


# ==============================================================================
# ADAPTIVE RATE LIMITER
# ==============================================================================

class AdaptiveRateLimiter(RateLimiter):
    """
    Rate limiter that adapts based on API responses (429 errors)

    This limiter automatically adjusts the rate limit based on API feedback:
    - On 429 (Too Many Requests): Reduces rate by backoff_factor
    - On sustained success: Gradually increases rate by recovery_factor

    The adaptive behavior helps maximize throughput while respecting API limits,
    especially useful when the actual limit is unknown or variable.

    Attributes:
        original_rate: Initial rate limit (recovery target)
        backoff_factor: Factor to reduce rate on 429 error
        recovery_factor: Factor to increase rate on success
        min_rate: Minimum rate limit (safety floor)
        recovery_threshold: Successful requests before attempting recovery
        consecutive_successes: Count of consecutive successful requests
        backoff_count: Count of times backed off
        recovery_count: Count of times recovered

    Usage:
        >>> limiter = AdaptiveRateLimiter(initial_rate=10)
        >>> limiter.acquire()
        >>> try:
        >>>     response = make_api_request()
        >>>     limiter.handle_success()
        >>> except RateLimitError:
        >>>     limiter.handle_rate_limit_error()
    """

    def __init__(self, initial_rate: int = DEFAULT_CP_GATEWAY_RATE, per_seconds: int = 1,
                 backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
                 recovery_factor: float = DEFAULT_RECOVERY_FACTOR,
                 min_rate: int = DEFAULT_MIN_RATE,
                 recovery_threshold: int = DEFAULT_CP_RECOVERY_THRESHOLD):
        """
        Initialize adaptive rate limiter

        Args:
            initial_rate: Initial request rate limit
            per_seconds: Time window in seconds
            backoff_factor: Factor to reduce rate on 429 error (0.0-1.0)
            recovery_factor: Factor to increase rate on success (1.0+)
            min_rate: Minimum rate limit (safety floor)
            recovery_threshold: Successful requests before attempting recovery
        """
        super().__init__(initial_rate, per_seconds)
        self.original_rate = initial_rate
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.min_rate = min_rate
        self.recovery_threshold = recovery_threshold
        self.consecutive_successes = 0
        self.backoff_count = 0
        self.recovery_count = 0

        logger.info(
            f"AdaptiveRateLimiter initialized: {initial_rate} req/s, "
            f"backoff={backoff_factor}, recovery={recovery_factor}, "
            f"threshold={recovery_threshold}"
        )

    # ==========================================================================
    # PUBLIC METHODS - ADAPTIVE BEHAVIOR
    # ==========================================================================

    def handle_rate_limit_error(self):
        """
        Handle 429 (Too Many Requests) error

        Reduces rate limit by backoff factor to prevent further rate limiting.
        Should be called when API returns 429 status code.
        """
        with self.lock:
            # Reduce rate by backoff factor
            new_rate = max(self.min_rate, int(self.rate_limit * self.backoff_factor))

            logger.warning(
                f"Rate limit exceeded (429). Reducing from {self.rate_limit} to {new_rate} req/sec. "
                f"Backoff #{self.backoff_count + 1}"
            )

            self.rate_limit = new_rate
            self.tokens = min(self.tokens, new_rate)
            self.consecutive_successes = 0
            self.backoff_count += 1

    def handle_success(self):
        """
        Handle successful request

        Tracks consecutive successes and gradually increases rate limit
        after sustained success. Call this after each successful API request.
        """
        self.consecutive_successes += 1

        # Gradually increase rate after sustained success
        if self.consecutive_successes >= self.recovery_threshold:
            with self.lock:
                if self.rate_limit < self.original_rate:
                    new_rate = min(
                        self.original_rate,
                        int(self.rate_limit * self.recovery_factor)
                    )

                    logger.info(
                        f"Rate limit recovery: {self.rate_limit} -> {new_rate} req/sec "
                        f"(after {self.consecutive_successes} successful requests)"
                    )

                    self.rate_limit = new_rate
                    self.consecutive_successes = 0
                    self.recovery_count += 1

    # ==========================================================================
    # PUBLIC METHODS - STATISTICS
    # ==========================================================================

    def get_stats(self) -> dict:
        """
        Get extended statistics including adaptive behavior

        Returns:
            Dict with rate limiter statistics
        """
        base_stats = super().get_stats()

        return {
            **vars(base_stats),
            'original_rate': self.original_rate,
            'current_rate_limit': self.rate_limit,
            'consecutive_successes': self.consecutive_successes,
            'backoff_count': self.backoff_count,
            'recovery_count': self.recovery_count,
            'recovery_progress': f"{self.consecutive_successes}/{self.recovery_threshold}"
        }

    def __repr__(self) -> str:
        return (f"AdaptiveRateLimiter(rate={self.rate_limit}/{self.per_seconds}s, "
                f"original={self.original_rate}, successes={self.consecutive_successes})")


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_cp_gateway_limiter() -> AdaptiveRateLimiter:
    """
    Create rate limiter for CP Gateway (10 req/sec)

    Returns:
        Configured AdaptiveRateLimiter for CP Gateway

    Usage:
        >>> limiter = create_cp_gateway_limiter()
        >>> limiter.acquire()
    """
    logger.debug("Creating CP Gateway rate limiter (10 req/sec)")
    return AdaptiveRateLimiter(
        initial_rate=DEFAULT_CP_GATEWAY_RATE,
        per_seconds=1,
        backoff_factor=0.7,  # More aggressive backoff for slower rate
        recovery_factor=DEFAULT_RECOVERY_FACTOR,
        min_rate=1,
        recovery_threshold=DEFAULT_CP_RECOVERY_THRESHOLD
    )


def create_oauth_limiter() -> AdaptiveRateLimiter:
    """
    Create rate limiter for OAuth 2.0 (50 req/sec)

    Returns:
        Configured AdaptiveRateLimiter for OAuth 2.0

    Usage:
        >>> limiter = create_oauth_limiter()
        >>> limiter.acquire()
    """
    logger.debug("Creating OAuth 2.0 rate limiter (50 req/sec)")
    return AdaptiveRateLimiter(
        initial_rate=DEFAULT_OAUTH_RATE,
        per_seconds=1,
        backoff_factor=DEFAULT_BACKOFF_FACTOR,
        recovery_factor=DEFAULT_RECOVERY_FACTOR,
        min_rate=5,  # Higher floor for OAuth
        recovery_threshold=DEFAULT_OAUTH_RECOVERY_THRESHOLD
    )


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

__all__ = [
    'RateLimiter',
    'AdaptiveRateLimiter',
    'RateLimitStats',
    'create_cp_gateway_limiter',
    'create_oauth_limiter',
]


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == '__main__':
    """Test rate limiter functionality"""

    # Initialize logging
    SpyderLogger.initialize_logging(log_level="INFO")

    print("=" * 80)
    print("SPYDER - Rate Limiter Test")
    print("=" * 80)

    # Test basic rate limiter
    print("\n1. Testing Basic Rate Limiter (5 req/sec)")
    print("-" * 80)

    limiter = RateLimiter(rate_limit=5, per_seconds=1)
    print(f"Initial state: {limiter}")

    # Make some requests
    for i in range(10):
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start
        stats = limiter.get_stats()
        print(f"Request {i+1}: waited {elapsed:.3f}s, "
              f"tokens={stats.tokens_available:.2f}, "
              f"rate={stats.current_rate:.2f}/s")

    print(f"\nFinal stats: {limiter.get_stats()}")

    # Test adaptive limiter
    print("\n2. Testing Adaptive Rate Limiter")
    print("-" * 80)

    adaptive = AdaptiveRateLimiter(initial_rate=10, recovery_threshold=5)
    print(f"Initial state: {adaptive}")

    # Simulate some successes
    print("\nSimulating 5 successful requests...")
    for i in range(5):
        adaptive.acquire()
        adaptive.handle_success()
        print(f"Success {i+1}: {adaptive.consecutive_successes} consecutive")

    # Simulate rate limit error
    print("\nSimulating rate limit error (429)...")
    adaptive.handle_rate_limit_error()
    print(f"After backoff: rate={adaptive.rate_limit} req/sec")

    print("\n" + "=" * 80)
    print("Rate limiter testing completed.")
    print("=" * 80)
