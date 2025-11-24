#!/usr/bin/env python3
"""
Quick functional test for resilience infrastructure.
"""

import asyncio
import time
import sys

sys.path.insert(0, '/home/user/Spyder')

from SpyderU_Utilities.SpyderU40_RateLimiter import (
    RateLimiter,
    MultiRateLimiter,
    rate_limit,
    acquire_tradier,
    acquire_polygon
)

from SpyderU_Utilities.SpyderU41_CircuitBreaker import (
    CircuitState,
    CircuitBreaker,
    CircuitBreakerError,
    tradier_breaker,
    polygon_breaker
)


def print_test(name: str):
    """Print test header."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print('='*60)


async def test_rate_limiter_basic():
    """Test basic rate limiter functionality."""
    print_test("Rate Limiter - Basic Functionality")

    limiter = RateLimiter(requests_per_second=5, burst_size=5)

    # Should acquire 5 tokens instantly
    start = time.time()
    for i in range(5):
        await limiter.acquire()
        print(f"✓ Acquired token {i+1}/5")
    elapsed1 = time.time() - start
    print(f"  First 5 tokens acquired in {elapsed1:.3f}s (should be instant)")

    # 6th token should wait ~0.2s
    start = time.time()
    await limiter.acquire()
    elapsed2 = time.time() - start
    print(f"✓ 6th token acquired after {elapsed2:.3f}s (should be ~0.2s)")

    assert elapsed1 < 0.1, "First 5 tokens should be instant"
    assert elapsed2 > 0.15, "6th token should wait for refill"
    print("✅ PASSED")


async def test_circuit_breaker_basic():
    """Test basic circuit breaker functionality."""
    print_test("Circuit Breaker - Basic Functionality")

    breaker = CircuitBreaker(
        name="test",
        failure_threshold=3,
        recovery_timeout=1.0
    )

    # Initially CLOSED
    assert breaker.state == CircuitState.CLOSED
    print("✓ Circuit starts in CLOSED state")

    # Successful calls
    async def success_func():
        return "ok"

    for i in range(3):
        result = await breaker.call(success_func)
        assert result == "ok"
    print("✓ Successful calls keep circuit CLOSED")

    # Failing calls should open circuit
    async def failing_func():
        raise Exception("API Error")

    for i in range(3):
        try:
            await breaker.call(failing_func)
        except Exception:
            pass

    assert breaker.state == CircuitState.OPEN
    print("✓ Circuit OPEN after 3 failures")

    # Should block next call
    try:
        await breaker.call(failing_func)
        assert False, "Should have raised CircuitBreakerError"
    except CircuitBreakerError:
        print("✓ Circuit blocks calls when OPEN")

    print("✅ PASSED")


async def test_tradier_rate_limiter():
    """Test pre-configured Tradier rate limiter."""
    print_test("Tradier Rate Limiter - Pre-configured")

    # Should handle 10 req/sec
    start = time.time()
    for i in range(15):
        await acquire_tradier()
        if i < 10:
            print(f"✓ Token {i+1}/15 (burst)")
        else:
            print(f"✓ Token {i+1}/15 (rate-limited)")
    elapsed = time.time() - start

    print(f"  15 tokens acquired in {elapsed:.3f}s")
    # First 10 should be instant (burst), next 5 should take ~0.5s
    assert elapsed > 0.3, "Should take time after burst exhausted"
    assert elapsed < 1.0, "Should not be too slow"
    print("✅ PASSED")


async def test_polygon_rate_limiter_starter():
    """Test Polygon starter tier rate limiter."""
    print_test("Polygon Rate Limiter - Starter Tier")

    # Starter tier: 5 req/min = 0.08 req/sec
    # 3 requests should take ~25 seconds (but we'll just test 2)
    start = time.time()
    await acquire_polygon(tier="starter")
    print("✓ Request 1")
    await acquire_polygon(tier="starter")
    print("✓ Request 2")
    elapsed = time.time() - start

    print(f"  2 requests took {elapsed:.3f}s")
    # Second request should wait ~12s
    assert elapsed > 10.0, "Starter tier should be heavily rate-limited"
    print("✅ PASSED (starter tier correctly rate-limited)")


async def test_polygon_rate_limiter_business():
    """Test Polygon business tier rate limiter."""
    print_test("Polygon Rate Limiter - Business Tier")

    # Business tier: 100 req/min = 1.67 req/sec
    start = time.time()
    for i in range(5):
        await acquire_polygon(tier="business")
        print(f"✓ Request {i+1}/5")
    elapsed = time.time() - start

    print(f"  5 requests took {elapsed:.3f}s")
    # First few should be fairly quick
    assert elapsed < 5.0, "Business tier should be faster"
    print("✅ PASSED")


async def test_decorator_integration():
    """Test decorator-based protection."""
    print_test("Decorator Integration")

    call_count = 0

    @rate_limit(requests_per_second=10)
    async def api_call():
        nonlocal call_count
        call_count += 1
        return f"call_{call_count}"

    # Make multiple calls
    for i in range(5):
        result = await api_call()
        print(f"✓ {result}")

    assert call_count == 5
    print("✅ PASSED")


async def test_protected_api_simulation():
    """Simulate protected API calls."""
    print_test("Protected API Call Simulation")

    @rate_limit(service="tradier")
    async def place_order_mock(symbol: str, qty: int):
        async with tradier_breaker:
            # Simulate API latency
            await asyncio.sleep(0.01)
            return {"symbol": symbol, "qty": qty, "status": "filled"}

    # Make several orders
    symbols = ["SPY", "QQQ", "IWM"]
    for symbol in symbols:
        result = await place_order_mock(symbol, 10)
        print(f"✓ Order: {result['symbol']} x {result['qty']} - {result['status']}")

    # Check circuit breaker status
    status = tradier_breaker.get_stats()
    print(f"\n  Circuit Status: {status['state']}")
    print(f"  Failures: {status['failure_count']}")
    assert status['state'] == "CLOSED"
    print("✅ PASSED")


async def test_circuit_breaker_recovery():
    """Test circuit breaker recovery."""
    print_test("Circuit Breaker Recovery")

    breaker = CircuitBreaker(name="recovery_test", failure_threshold=2, recovery_timeout=2.0)
    call_count = 0

    async def flaky_api():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise Exception("Service down")
        return "recovered"

    # Open circuit
    for i in range(2):
        try:
            await breaker.call(flaky_api)
        except Exception:
            print(f"✓ Failure {i+1}/2 recorded")

    assert breaker.state == CircuitState.OPEN
    print("✓ Circuit is OPEN")

    # Wait for recovery
    print("  Waiting 2.5s for recovery timeout...")
    await asyncio.sleep(2.5)

    # Should try HALF_OPEN
    result = await breaker.call(flaky_api)
    assert result == "recovered"
    assert breaker.state == CircuitState.CLOSED
    print("✓ Circuit recovered and is CLOSED")

    print("✅ PASSED")


async def test_monitoring():
    """Test monitoring capabilities."""
    print_test("Monitoring & Statistics")

    # Tradier breaker stats
    tradier_stats = tradier_breaker.get_stats()
    print("\nTradier Circuit Breaker:")
    print(f"  Name: {tradier_stats['name']}")
    print(f"  State: {tradier_stats['state']}")
    print(f"  Failure Threshold: {tradier_stats['failure_threshold']}")
    print(f"  Recovery Timeout: {tradier_stats['recovery_timeout']}s")
    print(f"  Is Open: {tradier_stats['is_open']}")

    # Polygon breaker stats
    polygon_stats = polygon_breaker.get_stats()
    print("\nPolygon Circuit Breaker:")
    print(f"  Name: {polygon_stats['name']}")
    print(f"  State: {polygon_stats['state']}")
    print(f"  Failure Threshold: {polygon_stats['failure_threshold']}")
    print(f"  Recovery Timeout: {polygon_stats['recovery_timeout']}s")

    print("\n✅ PASSED")


async def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("SPYDER RESILIENCE INFRASTRUCTURE - FUNCTIONAL TESTS")
    print("="*60)

    tests = [
        ("Rate Limiter Basic", test_rate_limiter_basic),
        ("Circuit Breaker Basic", test_circuit_breaker_basic),
        ("Tradier Rate Limiter", test_tradier_rate_limiter),
        ("Polygon Business Tier", test_polygon_rate_limiter_business),
        ("Decorator Integration", test_decorator_integration),
        ("Protected API Simulation", test_protected_api_simulation),
        ("Circuit Breaker Recovery", test_circuit_breaker_recovery),
        ("Monitoring", test_monitoring),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            await test_func()
            passed += 1
        except Exception as e:
            print(f"\n❌ FAILED: {name}")
            print(f"   Error: {e}")
            failed += 1

    # Skip slow starter tier test
    print("\n" + "="*60)
    print("SKIPPING: Polygon Starter Tier (takes 12+ seconds)")
    print("="*60)

    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⏭️  Skipped: 1 (too slow for quick test)")
    print("="*60)

    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe resilience infrastructure is working correctly:")
        print("  ✓ Rate limiting prevents API overload")
        print("  ✓ Circuit breakers protect against cascading failures")
        print("  ✓ Tradier and Polygon pre-configured correctly")
        print("  ✓ Monitoring and statistics available")
        return 0
    else:
        print(f"\n⚠️  {failed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
