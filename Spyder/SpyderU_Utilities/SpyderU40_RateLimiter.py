#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU40_RateLimiter.py
Purpose: SPYDER - Rate Limiter

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Rate Limiter

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import time
from typing import Optional, Dict
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps
import threading

@dataclass
class TokenBucket:
    """
    Token bucket for rate limiting.

    Attributes:
        capacity: Maximum tokens in bucket
        fill_rate: Tokens added per second
        tokens: Current token count (defaults to capacity)
        last_update: Last time tokens were added
    """
    capacity: float
    fill_rate: float
    tokens: float = None
    last_update: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        """Set tokens to capacity if not specified."""
        if self.tokens is None:
            self.tokens = self.capacity

    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            bool: True if tokens consumed, False if insufficient tokens
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def wait_time(self, tokens: float = 1.0) -> float:
        """
        Calculate wait time for tokens.

        Args:
            tokens: Number of tokens needed

        Returns:
            float: Seconds to wait
        """
        with self.lock:
            self._refill()

            if self.tokens >= tokens:
                return 0.0

            # Calculate how long to wait
            tokens_needed = tokens - self.tokens
            wait_seconds = tokens_needed / self.fill_rate
            return wait_seconds

    def _refill(self):
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on fill rate
        self.tokens = min(
            self.capacity,
            self.tokens + (elapsed * self.fill_rate)
        )
        self.last_update = now


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.

    Examples:
        # Create limiter
        limiter = RateLimiter(requests_per_second=10)

        # Async usage
        await limiter.acquire()

        # As context manager
        async with limiter:
            await make_api_call()
    """

    def __init__(
        self,
        requests_per_second: float,
        burst_size: Optional[float] = None
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst size (defaults to requests_per_second)
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size or requests_per_second

        # Create token bucket
        self.bucket = TokenBucket(
            capacity=self.burst_size,
            fill_rate=requests_per_second,
            tokens=self.burst_size
        )

    @classmethod
    def from_per_minute(
        cls,
        requests_per_minute: float,
        burst_size: Optional[float] = None
    ) -> 'RateLimiter':
        """
        Create rate limiter from requests per minute.

        Args:
            requests_per_minute: Maximum requests per minute
            burst_size: Maximum burst size

        Returns:
            RateLimiter instance
        """
        return cls(
            requests_per_second=requests_per_minute / 60.0,
            burst_size=burst_size
        )

    async def acquire(self, tokens: float = 1.0):
        """
        Acquire tokens (wait if necessary).

        Args:
            tokens: Number of tokens to acquire
        """
        while not self.bucket.consume(tokens):
            wait_time = self.bucket.wait_time(tokens)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

    async def __aenter__(self):
        """Context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass


class MultiRateLimiter:
    """
    Rate limiter with multiple named limits.

    Useful for APIs with different limits per endpoint.

    Examples:
        limiter = MultiRateLimiter()
        limiter.add_limit("orders", requests_per_second=2)
        limiter.add_limit("quotes", requests_per_second=10)

        await limiter.acquire("orders")
    """

    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}
        self._defaults: Dict[str, dict] = {}
        self.lock = threading.Lock()

    def register_default(
        self,
        name: str,
        requests_per_second: float,
        burst_size: Optional[float] = None
    ):
        """
        Register a default configuration for lazy initialization.

        Args:
            name: Limit name
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst size
        """
        self._defaults[name] = {
            'requests_per_second': requests_per_second,
            'burst_size': burst_size
        }

    def add_limit(
        self,
        name: str,
        requests_per_second: float,
        burst_size: Optional[float] = None
    ):
        """
        Add a named rate limit.

        Args:
            name: Limit name
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst size
        """
        with self.lock:
            self._limiters[name] = RateLimiter(requests_per_second, burst_size)

    async def acquire(self, name: str, tokens: float = 1.0):
        """
        Acquire tokens from named limit.

        Lazily initializes from registered defaults if not yet created.

        Args:
            name: Limit name
            tokens: Number of tokens to acquire
        """
        if name not in self._limiters:
            if name in self._defaults:
                self.add_limit(name, **self._defaults[name])
            else:
                raise ValueError(f"Unknown rate limit: {name}")

        await self._limiters[name].acquire(tokens)

    def get_stats(self) -> Dict[str, dict]:
        """
        Get statistics for all rate limiters.

        Returns:
            Dictionary mapping service names to their stats.
        """
        stats = {}
        with self.lock:
            for name, limiter in self._limiters.items():
                stats[name] = {
                    'tokens': limiter.bucket.tokens,
                    'capacity': limiter.bucket.capacity,
                    'fill_rate': limiter.bucket.fill_rate
                }
        return stats


# Global rate limiters for common services
_global_limiters = MultiRateLimiter()

# Register default configurations (lazy-initialized on first use)
_global_limiters.register_default("tradier", requests_per_second=10, burst_size=20)
_global_limiters.register_default("databento", requests_per_second=10)


def rate_limit(
    requests_per_second: Optional[float] = None,
    burst_size: Optional[float] = None,
    service: Optional[str] = None
):
    """
    Decorator for rate-limited functions.

    Args:
        requests_per_second: Rate limit (creates new limiter)
        burst_size: Maximum burst size (defaults to requests_per_second)
        service: Use global limiter for service name

    Examples:
        @rate_limit(requests_per_second=10)
        async def api_call():
            ...

        @rate_limit(service="tradier")
        async def tradier_call():
            ...
    """
    def decorator(func):
        # Create limiter if needed
        if requests_per_second is not None:
            limiter = RateLimiter(requests_per_second, burst_size=burst_size)
        elif service:
            limiter = None  # Will use global
        else:
            raise ValueError("Must specify requests_per_second or service")

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Acquire tokens
            if limiter:
                await limiter.acquire()
            else:
                await _global_limiters.acquire(service)

            # Call function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


# Convenience functions
async def acquire_tradier():
    """Acquire token for Tradier API call."""
    await _global_limiters.acquire("tradier")


async def acquire_databento():
    """Acquire token for Databento API call."""
    await _global_limiters.acquire("databento")


__all__ = [
    "TokenBucket",
    "RateLimiter",
    "MultiRateLimiter",
    "rate_limit",
    "acquire_tradier",
    "acquire_databento",
]
