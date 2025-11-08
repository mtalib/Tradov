#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: SpyderB_Broker/ClientPortalAPI/rate_limiter.py
Purpose: Rate limiting for Client Portal Web API requests
Author: Mohamed Talib
Last Updated: 2025-11-08

Module Description:
    Implements token bucket rate limiting with adaptive backoff for IBKR
    Client Portal Web API. Handles both OAuth (50 req/sec) and CP Gateway
    (10 req/sec) rate limits.
"""

import time
import asyncio
import logging
from collections import deque
from threading import Lock
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitStats:
    """Rate limiter statistics"""
    tokens_available: float
    max_tokens: int
    current_rate: float
    limit_rate: float
    requests_last_window: int
    total_requests: int
    total_throttled: int


class RateLimiter:
    """
    Token bucket rate limiter for IBKR Client Portal API

    Rate Limits:
        - OAuth 2.0: 50 requests/second
        - CP Gateway: 10 requests/second

    Example:
        >>> limiter = RateLimiter(rate_limit=10, per_seconds=1)
        >>> limiter.acquire()  # Blocks until token available
        >>> # Make API request
    """

    def __init__(self, rate_limit: int = 10, per_seconds: int = 1):
        """
        Initialize rate limiter

        Args:
            rate_limit: Maximum requests allowed
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

    def _refill_tokens(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens proportional to elapsed time
        tokens_to_add = (elapsed / self.per_seconds) * self.rate_limit
        self.tokens = min(self.rate_limit, self.tokens + tokens_to_add)
        self.last_refill = now

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
            time.sleep(min(wait_time, 0.1))  # Sleep in small increments

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
            await asyncio.sleep(min(wait_time, 0.1))

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

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (f"RateLimiter(rate={self.rate_limit}/{self.per_seconds}s, "
                f"tokens={stats.tokens_available:.2f}, "
                f"current_rate={stats.current_rate:.2f}/s)")


class AdaptiveRateLimiter(RateLimiter):
    """
    Rate limiter that adapts based on 429 (Too Many Requests) responses

    This limiter automatically reduces the rate limit when receiving 429 errors
    and gradually recovers after sustained successful requests.

    Example:
        >>> limiter = AdaptiveRateLimiter(initial_rate=10)
        >>> limiter.acquire()
        >>> try:
        >>>     response = make_api_request()
        >>>     limiter.handle_success()
        >>> except RateLimitError:
        >>>     limiter.handle_rate_limit_error()
    """

    def __init__(self, initial_rate: int = 10, per_seconds: int = 1,
                 backoff_factor: float = 0.8, recovery_factor: float = 1.05,
                 min_rate: int = 1, recovery_threshold: int = 100):
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


# Convenience functions
def create_cp_gateway_limiter() -> AdaptiveRateLimiter:
    """
    Create rate limiter for CP Gateway (10 req/sec)

    Returns:
        Configured AdaptiveRateLimiter for CP Gateway
    """
    return AdaptiveRateLimiter(
        initial_rate=10,
        per_seconds=1,
        backoff_factor=0.7,
        recovery_factor=1.05,
        min_rate=1,
        recovery_threshold=50
    )


def create_oauth_limiter() -> AdaptiveRateLimiter:
    """
    Create rate limiter for OAuth 2.0 (50 req/sec)

    Returns:
        Configured AdaptiveRateLimiter for OAuth 2.0
    """
    return AdaptiveRateLimiter(
        initial_rate=50,
        per_seconds=1,
        backoff_factor=0.8,
        recovery_factor=1.05,
        min_rate=5,
        recovery_threshold=100
    )


if __name__ == '__main__':
    # Test rate limiter
    limiter = RateLimiter(rate_limit=5, per_seconds=1)

    print(f"Testing rate limiter: {limiter}")

    # Make some requests
    for i in range(10):
        start = time.time()
        limiter.acquire()
        elapsed = time.time() - start
        print(f"Request {i+1}: waited {elapsed:.3f}s, stats: {limiter.get_stats()}")

    print(f"\nFinal stats: {limiter.get_stats()}")
