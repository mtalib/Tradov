#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Module: test_rate_limiter.py
Purpose: Unit tests for rate limiter
Author: Mohamed Talib
Last Updated: 2025-11-08
"""

import pytest
import time
import asyncio
from SpyderB_Broker.ClientPortalAPI.SpyderB09_ClientPortal_RateLimiter import (
    RateLimiter,
    AdaptiveRateLimiter,
    create_cp_gateway_limiter,
    create_oauth_limiter
)


class TestRateLimiter:
    """Test cases for RateLimiter class"""

    @pytest.mark.unit
    def test_rate_limiter_creation(self):
        """Test that rate limiter can be created"""
        limiter = RateLimiter(rate_limit=10, per_seconds=1)

        assert limiter.rate_limit == 10
        assert limiter.per_seconds == 1
        assert limiter.tokens == 10.0

    @pytest.mark.unit
    def test_acquire_token(self):
        """Test acquiring a single token"""
        limiter = RateLimiter(rate_limit=10, per_seconds=1)

        # Should acquire immediately
        start = time.time()
        result = limiter.acquire(tokens=1, blocking=True)
        elapsed = time.time() - start

        assert result is True
        assert elapsed < 0.1  # Should be instant
        assert limiter.tokens < 10  # Token consumed

    @pytest.mark.unit
    def test_rate_limiting_blocks(self):
        """Test that rate limiter blocks when limit exceeded"""
        limiter = RateLimiter(rate_limit=2, per_seconds=1)

        # Acquire all tokens
        limiter.acquire(tokens=2)

        # Next acquire should block
        start = time.time()
        limiter.acquire(tokens=1, blocking=True)
        elapsed = time.time() - start

        assert elapsed >= 0.4  # Should wait ~0.5 seconds

    @pytest.mark.unit
    def test_non_blocking_acquire(self):
        """Test non-blocking acquire returns False when no tokens"""
        limiter = RateLimiter(rate_limit=1, per_seconds=1)

        # Acquire the only token
        assert limiter.acquire(tokens=1, blocking=False) is True

        # Next acquire should return False immediately
        start = time.time()
        result = limiter.acquire(tokens=1, blocking=False)
        elapsed = time.time() - start

        assert result is False
        assert elapsed < 0.01  # Should be instant

    @pytest.mark.unit
    def test_timeout(self):
        """Test that acquire raises TimeoutError when timeout exceeded"""
        limiter = RateLimiter(rate_limit=1, per_seconds=1)

        # Consume token
        limiter.acquire(tokens=1)

        # Try to acquire with short timeout
        with pytest.raises(TimeoutError):
            limiter.acquire(tokens=1, blocking=True, timeout=0.1)

    @pytest.mark.unit
    def test_get_stats(self):
        """Test getting rate limiter statistics"""
        limiter = RateLimiter(rate_limit=10, per_seconds=1)

        stats = limiter.get_stats()

        assert stats.max_tokens == 10
        assert stats.tokens_available <= 10
        assert stats.limit_rate == 10.0
        assert stats.total_requests >= 0

    @pytest.mark.unit
    def test_reset(self):
        """Test resetting rate limiter"""
        limiter = RateLimiter(rate_limit=10, per_seconds=1)

        # Use some tokens
        limiter.acquire(tokens=5)

        # Reset
        limiter.reset()

        stats = limiter.get_stats()
        assert stats.tokens_available == 10.0
        assert stats.total_requests == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_async_acquire(self):
        """Test async token acquisition"""
        limiter = RateLimiter(rate_limit=10, per_seconds=1)

        # Should acquire immediately
        start = time.time()
        result = await limiter.acquire_async(tokens=1)
        elapsed = time.time() - start

        assert result is True
        assert elapsed < 0.1


class TestAdaptiveRateLimiter:
    """Test cases for AdaptiveRateLimiter class"""

    @pytest.mark.unit
    def test_adaptive_limiter_creation(self):
        """Test that adaptive rate limiter can be created"""
        limiter = AdaptiveRateLimiter(
            initial_rate=10,
            backoff_factor=0.8,
            recovery_factor=1.05
        )

        assert limiter.rate_limit == 10
        assert limiter.original_rate == 10
        assert limiter.backoff_factor == 0.8
        assert limiter.recovery_factor == 1.05

    @pytest.mark.unit
    def test_handle_rate_limit_error(self):
        """Test that rate limit error reduces the rate"""
        limiter = AdaptiveRateLimiter(initial_rate=10, backoff_factor=0.8)

        initial_rate = limiter.rate_limit

        # Handle rate limit error
        limiter.handle_rate_limit_error()

        # Rate should be reduced
        assert limiter.rate_limit < initial_rate
        assert limiter.rate_limit == int(initial_rate * 0.8)
        assert limiter.consecutive_successes == 0

    @pytest.mark.unit
    def test_handle_success_recovery(self):
        """Test that successful requests lead to rate recovery"""
        limiter = AdaptiveRateLimiter(
            initial_rate=10,
            recovery_factor=1.05,
            recovery_threshold=5
        )

        # Reduce rate first
        limiter.handle_rate_limit_error()
        reduced_rate = limiter.rate_limit

        # Simulate successful requests
        for _ in range(5):
            limiter.handle_success()

        # Rate should have recovered
        assert limiter.rate_limit > reduced_rate

    @pytest.mark.unit
    def test_backoff_multiple_times(self):
        """Test multiple rate limit errors cause progressive backoff"""
        limiter = AdaptiveRateLimiter(
            initial_rate=10,
            backoff_factor=0.8,
            min_rate=1
        )

        rates = [limiter.rate_limit]

        # Apply multiple backoffs
        for _ in range(3):
            limiter.handle_rate_limit_error()
            rates.append(limiter.rate_limit)

        # Each rate should be lower than previous
        for i in range(len(rates) - 1):
            assert rates[i+1] < rates[i]

        # Should not go below min_rate
        assert limiter.rate_limit >= limiter.min_rate

    @pytest.mark.unit
    def test_get_extended_stats(self):
        """Test getting extended statistics"""
        limiter = AdaptiveRateLimiter(initial_rate=10)

        # Trigger some events
        limiter.handle_rate_limit_error()
        limiter.handle_success()

        stats = limiter.get_stats()

        assert 'original_rate' in stats
        assert 'current_rate_limit' in stats
        assert 'consecutive_successes' in stats
        assert 'backoff_count' in stats
        assert stats['backoff_count'] == 1


class TestFactoryFunctions:
    """Test factory functions for creating limiters"""

    @pytest.mark.unit
    def test_create_cp_gateway_limiter(self):
        """Test creating CP Gateway limiter"""
        limiter = create_cp_gateway_limiter()

        assert isinstance(limiter, AdaptiveRateLimiter)
        assert limiter.rate_limit == 10
        assert limiter.original_rate == 10

    @pytest.mark.unit
    def test_create_oauth_limiter(self):
        """Test creating OAuth limiter"""
        limiter = create_oauth_limiter()

        assert isinstance(limiter, AdaptiveRateLimiter)
        assert limiter.rate_limit == 50
        assert limiter.original_rate == 50


class TestRateLimiterIntegration:
    """Integration tests for rate limiter"""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_realistic_rate_limiting(self):
        """Test rate limiting with realistic request pattern"""
        limiter = RateLimiter(rate_limit=5, per_seconds=1)

        request_times = []

        # Make 10 requests (should take ~2 seconds for rate of 5/sec)
        start = time.time()
        for i in range(10):
            limiter.acquire()
            request_times.append(time.time() - start)

        total_time = time.time() - start

        # Should take at least 1.8 seconds (allowing some tolerance)
        assert total_time >= 1.8
        assert total_time < 2.5

        # Verify first 5 were instant, next 5 were delayed
        assert request_times[0] < 0.1  # First request instant
        assert request_times[4] < 0.2  # Fifth request still quick
        assert request_times[5] > 0.9  # Sixth request delayed
        assert request_times[9] > 1.7  # Tenth request delayed more

    @pytest.mark.integration
    def test_adaptive_backoff_and_recovery_cycle(self):
        """Test full backoff and recovery cycle"""
        limiter = AdaptiveRateLimiter(
            initial_rate=10,
            backoff_factor=0.8,
            recovery_factor=1.1,
            recovery_threshold=3
        )

        original_rate = limiter.rate_limit

        # Simulate rate limit error
        limiter.handle_rate_limit_error()
        assert limiter.rate_limit < original_rate

        # Simulate recovery through successful requests
        reduced_rate = limiter.rate_limit
        for _ in range(3):
            limiter.handle_success()

        # Should have recovered somewhat
        assert limiter.rate_limit > reduced_rate

        # Continue recovery
        for _ in range(10):
            for _ in range(3):
                limiter.handle_success()

        # Should be back to original or close to it
        assert limiter.rate_limit >= original_rate * 0.9


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
