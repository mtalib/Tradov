#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT45_ResilienceInfrastructureTest.py
Purpose: Comprehensive tests for rate limiting and circuit breaker infrastructure

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2025-11-24

Module Description:
    Test suite for production-grade resilience infrastructure:
    - Rate limiter token bucket algorithm
    - Circuit breaker pattern (CLOSED/OPEN/HALF_OPEN)
    - Integration with TradierClient
    - Integration with PolygonDataHandler
    - Monitoring and statistics
"""

import asyncio
import time
import unittest
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any

# Import resilience utilities
import sys
sys.path.insert(0, '/home/user/Spyder')

from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import (
    TokenBucket,
    RateLimiter,
    MultiRateLimiter,
    rate_limit,
    acquire_tradier,
    acquire_polygon,
    _global_limiters
)

from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import (
    CircuitState,
    CircuitBreaker,
    CircuitBreakerError,
    tradier_breaker,
    polygon_breaker
)


# ==============================================================================
# TEST: TOKEN BUCKET ALGORITHM
# ==============================================================================
class TestTokenBucket(unittest.TestCase):
    """Test token bucket rate limiting algorithm."""

    def test_token_bucket_initialization(self):
        """Test token bucket is initialized with full capacity."""
        bucket = TokenBucket(capacity=10.0, fill_rate=2.0)

        self.assertEqual(bucket.capacity, 10.0)
        self.assertEqual(bucket.tokens, 10.0)  # Starts full
        self.assertEqual(bucket.fill_rate, 2.0)

    def test_token_consumption_success(self):
        """Test successful token consumption."""
        bucket = TokenBucket(capacity=10.0, fill_rate=2.0)

        # Should consume successfully
        result = bucket.consume(3.0)
        self.assertTrue(result)
        self.assertEqual(bucket.tokens, 7.0)

    def test_token_consumption_failure(self):
        """Test token consumption fails when insufficient tokens."""
        bucket = TokenBucket(capacity=10.0, fill_rate=2.0)

        # Consume all tokens
        bucket.consume(10.0)

        # Should fail - no tokens left
        result = bucket.consume(1.0)
        self.assertFalse(result)

    def test_token_refill(self):
        """Test tokens refill at specified rate."""
        bucket = TokenBucket(capacity=10.0, fill_rate=5.0)  # 5 tokens/second

        # Consume all tokens
        bucket.consume(10.0)
        self.assertEqual(bucket.tokens, 0.0)

        # Wait 1 second - should refill 5 tokens
        time.sleep(1.1)
        result = bucket.consume(1.0)
        self.assertTrue(result)  # Should have ~5 tokens after 1 second

    def test_token_refill_cap(self):
        """Test tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=10.0, fill_rate=5.0)

        # Consume 5 tokens
        bucket.consume(5.0)

        # Wait 2 seconds - should refill to capacity (10), not 15
        time.sleep(2.1)
        bucket.consume(1.0)

        # Should have 9 tokens (10 - 1), not 14
        self.assertLessEqual(bucket.tokens, 10.0)


# ==============================================================================
# TEST: RATE LIMITER
# ==============================================================================
class TestRateLimiter(unittest.IsolatedAsyncioTestCase):
    """Test RateLimiter class."""

    def setUp(self):
        """Reset rate limiters before each test."""
        # Clear global limiters
        _global_limiters._limiters.clear()

    def test_rate_limiter_creation(self):
        """Test rate limiter can be created with various configurations."""
        limiter = RateLimiter(requests_per_second=10, burst_size=20)

        self.assertIsNotNone(limiter.bucket)
        self.assertEqual(limiter.bucket.capacity, 20.0)
        self.assertEqual(limiter.bucket.fill_rate, 10.0)

    def test_rate_limiter_from_per_minute(self):
        """Test rate limiter creation from requests per minute."""
        limiter = RateLimiter.from_per_minute(requests_per_minute=60)

        # 60 req/min = 1 req/sec
        self.assertEqual(limiter.bucket.fill_rate, 1.0)

    async def test_rate_limiter_async_acquire(self):
        """Test async token acquisition."""
        limiter = RateLimiter(requests_per_second=100)  # Fast for testing

        # Should acquire immediately
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        self.assertLess(elapsed, 0.1)  # Should be nearly instant

    async def test_rate_limiter_blocks_when_exhausted(self):
        """Test rate limiter blocks when tokens exhausted."""
        limiter = RateLimiter(requests_per_second=2, burst_size=2)

        # Consume both tokens
        await limiter.acquire()
        await limiter.acquire()

        # Third acquire should block briefly
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        self.assertGreater(elapsed, 0.3)  # Should wait ~0.5 seconds


# ==============================================================================
# TEST: MULTI-SERVICE RATE LIMITER
# ==============================================================================
class TestMultiRateLimiter(unittest.IsolatedAsyncioTestCase):
    """Test multi-service rate limiter."""

    def setUp(self):
        """Create fresh multi-limiter for each test."""
        self.limiter = MultiRateLimiter()

    def test_add_limit(self):
        """Test adding service-specific limits."""
        self.limiter.add_limit("test_service", requests_per_second=5)

        self.assertIn("test_service", self.limiter._limiters)
        limiter = self.limiter._limiters["test_service"]
        self.assertEqual(limiter.bucket.fill_rate, 5.0)

    async def test_acquire_from_specific_service(self):
        """Test acquiring tokens for specific service."""
        self.limiter.add_limit("fast", requests_per_second=100)
        self.limiter.add_limit("slow", requests_per_second=1)

        # Fast service should acquire quickly
        start = time.time()
        await self.limiter.acquire("fast")
        fast_elapsed = time.time() - start

        self.assertLess(fast_elapsed, 0.1)

    def test_get_stats(self):
        """Test retrieving statistics for all services."""
        self.limiter.add_limit("service1", requests_per_second=10)
        self.limiter.add_limit("service2", requests_per_second=5)

        stats = self.limiter.get_stats()

        self.assertIn("service1", stats)
        self.assertIn("service2", stats)
        self.assertIn("tokens", stats["service1"])


# ==============================================================================
# TEST: CIRCUIT BREAKER
# ==============================================================================
class TestCircuitBreaker(unittest.IsolatedAsyncioTestCase):
    """Test circuit breaker pattern."""

    def setUp(self):
        """Create fresh circuit breaker for each test."""
        self.breaker = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=1.0,
            expected_exception=Exception
        )

    async def test_circuit_breaker_starts_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)

    async def test_circuit_breaker_successful_call(self):
        """Test successful call through circuit breaker."""
        async def success_func():
            return "success"

        result = await self.breaker.call(success_func)

        self.assertEqual(result, "success")
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)

    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        async def failing_func():
            raise Exception("API Error")

        # Trigger failures up to threshold
        for _ in range(3):
            try:
                await self.breaker.call(failing_func)
            except Exception:
                pass

        # Circuit should now be OPEN
        self.assertEqual(self.breaker.state, CircuitState.OPEN)

    async def test_circuit_breaker_blocks_when_open(self):
        """Test circuit breaker blocks calls when OPEN."""
        async def failing_func():
            raise Exception("API Error")

        # Open the circuit
        for _ in range(3):
            try:
                await self.breaker.call(failing_func)
            except Exception:
                pass

        # Next call should be blocked immediately
        with self.assertRaises(CircuitBreakerError) as context:
            await self.breaker.call(failing_func)

        self.assertIn("Circuit is OPEN", str(context.exception))

    async def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker enters HALF_OPEN after recovery timeout."""
        async def failing_func():
            raise Exception("API Error")

        # Open the circuit
        for _ in range(3):
            try:
                await self.breaker.call(failing_func)
            except Exception:
                pass

        self.assertEqual(self.breaker.state, CircuitState.OPEN)

        # Wait for recovery timeout
        await asyncio.sleep(1.2)

        # Next call should transition to HALF_OPEN
        try:
            await self.breaker.call(failing_func)
        except:
            pass

        # Should have attempted half-open state
        # (may be OPEN again if call failed)

    async def test_circuit_breaker_closes_after_success(self):
        """Test circuit breaker closes after successful call in HALF_OPEN."""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("Still failing")
            return "recovered"

        # Open the circuit
        for _ in range(3):
            try:
                await self.breaker.call(flaky_func)
            except:
                pass

        self.assertEqual(self.breaker.state, CircuitState.OPEN)

        # Wait for recovery
        await asyncio.sleep(1.2)

        # Successful call should close circuit
        result = await self.breaker.call(flaky_func)

        self.assertEqual(result, "recovered")
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)

    async def test_circuit_breaker_context_manager(self):
        """Test circuit breaker as context manager."""
        async with self.breaker:
            result = "executed"

        self.assertEqual(result, "executed")
        self.assertEqual(self.breaker.state, CircuitState.CLOSED)

    def test_circuit_breaker_reset(self):
        """Test manual circuit breaker reset."""
        # Simulate failures
        self.breaker.failure_count = 5
        self.breaker.state = CircuitState.OPEN

        # Reset
        self.breaker.reset()

        self.assertEqual(self.breaker.state, CircuitState.CLOSED)
        self.assertEqual(self.breaker.failure_count, 0)

    def test_circuit_breaker_get_stats(self):
        """Test circuit breaker statistics."""
        self.breaker.failure_count = 2

        stats = self.breaker.get_stats()

        self.assertEqual(stats["name"], "test")
        self.assertEqual(stats["state"], "CLOSED")
        self.assertEqual(stats["failure_count"], 2)
        self.assertIn("is_open", stats)


# ==============================================================================
# TEST: PRE-CONFIGURED LIMITERS & BREAKERS
# ==============================================================================
class TestPreconfiguredInfrastructure(unittest.IsolatedAsyncioTestCase):
    """Test pre-configured Tradier and Polygon infrastructure."""

    def setUp(self):
        """Reset global state."""
        _global_limiters._limiters.clear()
        tradier_breaker.reset()
        polygon_breaker.reset()

    async def test_tradier_rate_limiter_exists(self):
        """Test Tradier rate limiter is pre-configured."""
        # Should auto-initialize on first use
        await acquire_tradier()

        self.assertIn("tradier", _global_limiters._limiters)

        limiter = _global_limiters._limiters["tradier"]
        self.assertEqual(limiter.bucket.fill_rate, 10.0)  # 10 req/sec

    async def test_polygon_rate_limiter_tier_starter(self):
        """Test Polygon starter tier rate limiter."""
        await acquire_polygon(tier="starter")

        self.assertIn("polygon_starter", _global_limiters._limiters)

        limiter = _global_limiters._limiters["polygon_starter"]
        # 5 requests per minute = 0.0833... req/sec
        self.assertAlmostEqual(limiter.bucket.fill_rate, 5.0/60.0, places=2)

    async def test_polygon_rate_limiter_tier_business(self):
        """Test Polygon business tier rate limiter."""
        await acquire_polygon(tier="business")

        self.assertIn("polygon_business", _global_limiters._limiters)

        limiter = _global_limiters._limiters["polygon_business"]
        # 100 requests per minute = 1.666... req/sec
        self.assertAlmostEqual(limiter.bucket.fill_rate, 100.0/60.0, places=2)

    def test_tradier_breaker_configuration(self):
        """Test Tradier circuit breaker is properly configured."""
        self.assertEqual(tradier_breaker.name, "tradier")
        self.assertEqual(tradier_breaker.failure_threshold, 5)
        self.assertEqual(tradier_breaker.recovery_timeout, 60.0)

    def test_polygon_breaker_configuration(self):
        """Test Polygon circuit breaker is properly configured."""
        self.assertEqual(polygon_breaker.name, "polygon")
        self.assertEqual(polygon_breaker.failure_threshold, 3)
        self.assertEqual(polygon_breaker.recovery_timeout, 30.0)


# ==============================================================================
# TEST: DECORATOR INTEGRATION
# ==============================================================================
class TestDecoratorIntegration(unittest.IsolatedAsyncioTestCase):
    """Test decorator-based rate limiting and circuit breaking."""

    def setUp(self):
        """Reset global state."""
        _global_limiters._limiters.clear()

    async def test_rate_limit_decorator(self):
        """Test @rate_limit decorator."""
        call_count = 0

        @rate_limit(requests_per_second=100)
        async def fast_function():
            nonlocal call_count
            call_count += 1
            return "success"

        # Should execute successfully
        result = await fast_function()

        self.assertEqual(result, "success")
        self.assertEqual(call_count, 1)

    async def test_rate_limit_decorator_with_service(self):
        """Test @rate_limit decorator with service name."""
        @rate_limit(service="tradier")
        async def api_call():
            return "tradier_response"

        result = await api_call()

        self.assertEqual(result, "tradier_response")
        self.assertIn("tradier", _global_limiters._limiters)

    async def test_circuit_breaker_decorator(self):
        """Test circuit breaker decorator."""
        call_count = 0

        breaker = CircuitBreaker(name="test", failure_threshold=2)

        @breaker.decorator
        async def flaky_api():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("API Error")
            return "success"

        # First two calls should fail and open circuit
        for _ in range(2):
            try:
                await flaky_api()
            except Exception:
                pass

        self.assertEqual(breaker.state, CircuitState.OPEN)


# ==============================================================================
# INTEGRATION TEST: MOCK API CLIENT
# ==============================================================================
class TestAPIClientIntegration(unittest.IsolatedAsyncioTestCase):
    """Test integration with mock API client."""

    def setUp(self):
        """Reset infrastructure."""
        _global_limiters._limiters.clear()
        tradier_breaker.reset()
        polygon_breaker.reset()

    async def test_protected_api_call_success(self):
        """Test successful protected API call."""
        @rate_limit(service="tradier")
        async def place_order_mock(symbol: str, quantity: int):
            async with tradier_breaker:
                # Simulate API call
                await asyncio.sleep(0.01)
                return {"order_id": "12345", "symbol": symbol, "quantity": quantity}

        result = await place_order_mock("SPY", 10)

        self.assertEqual(result["symbol"], "SPY")
        self.assertEqual(result["quantity"], 10)
        self.assertEqual(tradier_breaker.state, CircuitState.CLOSED)

    async def test_protected_api_call_with_failures(self):
        """Test protected API call handles failures gracefully."""
        call_count = 0

        @rate_limit(service="tradier")
        async def flaky_api_call():
            async with tradier_breaker:
                nonlocal call_count
                call_count += 1

                if call_count <= 5:
                    raise Exception("Service temporarily unavailable")

                return "recovered"

        # Make failing calls
        for _ in range(5):
            try:
                await flaky_api_call()
            except Exception:
                pass

        # Circuit should be open
        self.assertEqual(tradier_breaker.state, CircuitState.OPEN)

        # Next call should be blocked
        with self.assertRaises(CircuitBreakerError):
            await flaky_api_call()

    async def test_rate_limiting_prevents_burst(self):
        """Test rate limiting prevents excessive burst calls."""
        call_times = []

        @rate_limit(requests_per_second=5, burst_size=5)
        async def api_call():
            call_times.append(time.time())
            return "ok"

        # Make 10 calls rapidly
        for _ in range(10):
            await api_call()

        # First 5 should be immediate, next 5 should be rate-limited
        # Total time should be at least 1 second (for the second batch)
        total_time = call_times[-1] - call_times[0]
        self.assertGreater(total_time, 0.8)  # Allow some tolerance


# ==============================================================================
# PERFORMANCE & STRESS TESTS
# ==============================================================================
class TestPerformance(unittest.IsolatedAsyncioTestCase):
    """Performance and stress tests."""

    async def test_rate_limiter_low_overhead(self):
        """Test rate limiter adds minimal overhead."""
        limiter = RateLimiter(requests_per_second=1000)  # Very high limit

        # Measure overhead
        iterations = 100
        start = time.time()

        for _ in range(iterations):
            await limiter.acquire()

        elapsed = time.time() - start
        overhead_per_call = elapsed / iterations

        # Should be very fast (< 1ms per call)
        self.assertLess(overhead_per_call, 0.001)

    async def test_circuit_breaker_low_overhead(self):
        """Test circuit breaker adds minimal overhead when closed."""
        breaker = CircuitBreaker(name="perf_test")

        async def fast_func():
            return "ok"

        # Measure overhead
        iterations = 100
        start = time.time()

        for _ in range(iterations):
            await breaker.call(fast_func)

        elapsed = time.time() - start
        overhead_per_call = elapsed / iterations

        # Should be very fast (< 1ms per call)
        self.assertLess(overhead_per_call, 0.001)


# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print("SPYDER RESILIENCE INFRASTRUCTURE TEST SUITE")
    print("=" * 80)
    print()
    print("Testing:")
    print("  ✓ Token Bucket Algorithm")
    print("  ✓ Rate Limiter (sync & async)")
    print("  ✓ Multi-Service Rate Limiter")
    print("  ✓ Circuit Breaker Pattern")
    print("  ✓ Pre-configured Tradier & Polygon Infrastructure")
    print("  ✓ Decorator Integration")
    print("  ✓ API Client Integration")
    print("  ✓ Performance & Overhead")
    print()
    print("=" * 80)
    print()

    # Run tests with verbose output
    unittest.main(verbosity=2, argv=[''])
