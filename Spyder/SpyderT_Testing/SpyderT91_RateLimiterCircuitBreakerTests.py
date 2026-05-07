#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT91_RateLimiterCircuitBreakerTests.py
Purpose: Tests for U40 RateLimiter and U41 CircuitBreaker

Year Created: 2025
Last Updated: 2026-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import os
import sys
import time
import types
from unittest.mock import AsyncMock, MagicMock, patch

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytest

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _ensure_pkg(name: str) -> None:
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("SpyderU_Utilities")
_ensure_pkg("Spyder.SpyderU_Utilities")

# Stub SpyderU01_Logger — U41 uses module-level `get_logger(__name__)`
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")
_logger_mod.get_logger = MagicMock(return_value=MagicMock())


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# ==============================================================================
# IMPORT MODULES UNDER TEST
# ==============================================================================
import Spyder.SpyderU_Utilities.SpyderU40_RateLimiter as _u40
import Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker as _u41

TokenBucket = _u40.TokenBucket
RateLimiter = _u40.RateLimiter
MultiRateLimiter = _u40.MultiRateLimiter

CircuitBreaker = _u41.CircuitBreaker
CircuitBreakerError = _u41.CircuitBreakerError
CircuitBreakerConfig = _u41.CircuitBreakerConfig
CircuitState = _u41.CircuitState


# ==============================================================================
# ──────────────────────────────────────────────────────────────────────────────
# U40 RateLimiter
# ──────────────────────────────────────────────────────────────────────────────
# ==============================================================================


class TestTokenBucket:
    def test_tokens_default_to_capacity(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        assert tb.tokens == 10.0

    def test_tokens_explicit(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0, tokens=3.0)
        assert tb.tokens == 3.0

    def test_consume_full_bucket_returns_true(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        assert tb.consume(1.0) is True

    def test_consume_reduces_tokens(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        tb.consume(3.0)
        assert tb.tokens == pytest.approx(7.0, abs=0.01)

    def test_consume_empty_returns_false(self):
        tb = TokenBucket(capacity=10.0, fill_rate=1.0, tokens=0.0)
        assert tb.consume(1.0) is False

    def test_consume_insufficient_tokens_returns_false(self):
        tb = TokenBucket(capacity=10.0, fill_rate=1.0, tokens=0.5)
        assert tb.consume(1.0) is False

    def test_consume_exact_amount_succeeds(self):
        tb = TokenBucket(capacity=5.0, fill_rate=1.0, tokens=5.0)
        assert tb.consume(5.0) is True

    def test_wait_time_full_bucket_is_zero(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        assert tb.wait_time(1.0) == pytest.approx(0.0, abs=0.01)

    def test_wait_time_empty_bucket(self):
        tb = TokenBucket(capacity=10.0, fill_rate=2.0, tokens=0.0)
        # Need 1 token at 2 tokens/sec → wait 0.5s
        wait = tb.wait_time(1.0)
        assert wait == pytest.approx(0.5, abs=0.01)

    def test_wait_time_partial_tokens(self):
        tb = TokenBucket(capacity=10.0, fill_rate=4.0, tokens=2.0)
        # Need 6 more (8-2=6) at 4/sec → 1.5s
        wait = tb.wait_time(8.0)
        assert wait == pytest.approx(1.5, abs=0.1)

    def test_refill_caps_at_capacity(self):
        tb = TokenBucket(capacity=5.0, fill_rate=10.0, tokens=5.0)
        # Artificially make time appear to have passed
        tb.last_update = time.time() - 10.0
        tb._refill()
        assert tb.tokens == pytest.approx(5.0)  # capped at capacity

    def test_refill_adds_tokens(self):
        tb = TokenBucket(capacity=100.0, fill_rate=10.0, tokens=0.0)
        tb.last_update = time.time() - 1.0  # 1 second ago
        tb._refill()
        assert tb.tokens == pytest.approx(10.0, abs=0.5)

    def test_lock_exists(self):
        import threading
        tb = TokenBucket(capacity=5.0, fill_rate=1.0)
        assert isinstance(tb.lock, type(threading.Lock()))

    def test_consume_after_refill(self):
        # Start empty, refill via time mock, then consume
        tb = TokenBucket(capacity=10.0, fill_rate=10.0, tokens=0.0)
        tb.last_update = time.time() - 1.0  # 1s elapsed → 10 tokens refilled
        assert tb.consume(5.0) is True


class TestRateLimiter:
    def test_init_rps(self):
        rl = RateLimiter(requests_per_second=10.0)
        assert rl.requests_per_second == 10.0

    def test_init_default_burst_equals_rps(self):
        rl = RateLimiter(requests_per_second=5.0)
        assert rl.burst_size == 5.0

    def test_init_custom_burst(self):
        rl = RateLimiter(requests_per_second=5.0, burst_size=20.0)
        assert rl.burst_size == 20.0

    def test_bucket_capacity_equals_burst(self):
        rl = RateLimiter(requests_per_second=5.0, burst_size=15.0)
        assert rl.bucket.capacity == 15.0

    def test_bucket_fill_rate_equals_rps(self):
        rl = RateLimiter(requests_per_second=8.0)
        assert rl.bucket.fill_rate == 8.0

    def test_from_per_minute(self):
        rl = RateLimiter.from_per_minute(60.0)
        assert rl.requests_per_second == pytest.approx(1.0)

    def test_from_per_minute_600(self):
        rl = RateLimiter.from_per_minute(600.0)
        assert rl.requests_per_second == pytest.approx(10.0)

    def test_from_per_minute_burst(self):
        rl = RateLimiter.from_per_minute(60.0, burst_size=30.0)
        assert rl.burst_size == 30.0

    async def test_acquire_available_tokens(self):
        rl = RateLimiter(requests_per_second=100.0)
        # Bucket is full → acquire should return immediately
        await asyncio.wait_for(rl.acquire(), timeout=1.0)

    async def test_acquire_multiple_succeeds_within_burst(self):
        rl = RateLimiter(requests_per_second=100.0, burst_size=10.0)
        for _ in range(5):
            await asyncio.wait_for(rl.acquire(), timeout=1.0)

    async def test_context_manager(self):
        rl = RateLimiter(requests_per_second=100.0)
        async with rl:
            pass  # Should not raise

    async def test_context_manager_aexit_returns_none(self):
        rl = RateLimiter(requests_per_second=100.0)
        result = await rl.__aexit__(None, None, None)
        assert result is None


class TestMultiRateLimiter:
    def test_init_empty(self):
        mrl = MultiRateLimiter()
        assert mrl._limiters == {}

    def test_add_limit(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("test", requests_per_second=5.0)
        assert "test" in mrl._limiters

    def test_add_limit_creates_rate_limiter(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("api", requests_per_second=10.0)
        assert isinstance(mrl._limiters["api"], RateLimiter)

    def test_add_limit_custom_burst(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("api", requests_per_second=5.0, burst_size=20.0)
        assert mrl._limiters["api"].burst_size == 20.0

    def test_register_default_stores_config(self):
        mrl = MultiRateLimiter()
        mrl.register_default("svc", requests_per_second=3.0, burst_size=10.0)
        assert "svc" in mrl._defaults
        assert mrl._defaults["svc"]["requests_per_second"] == 3.0

    async def test_acquire_known_limiter(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("fast", requests_per_second=1000.0)
        await asyncio.wait_for(mrl.acquire("fast"), timeout=1.0)

    async def test_acquire_from_default(self):
        mrl = MultiRateLimiter()
        mrl.register_default("lazy", requests_per_second=100.0)
        await asyncio.wait_for(mrl.acquire("lazy"), timeout=1.0)
        assert "lazy" in mrl._limiters  # lazy-initialized

    async def test_acquire_unknown_raises_value_error(self):
        mrl = MultiRateLimiter()
        with pytest.raises(ValueError, match="Unknown rate limit"):
            await mrl.acquire("nonexistent")

    def test_get_stats_empty(self):
        mrl = MultiRateLimiter()
        assert mrl.get_stats() == {}

    def test_get_stats_with_limiters(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("svc1", requests_per_second=5.0)
        mrl.add_limit("svc2", requests_per_second=10.0)
        stats = mrl.get_stats()
        assert "svc1" in stats
        assert "svc2" in stats

    def test_get_stats_keys(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("api", requests_per_second=5.0, burst_size=10.0)
        stats = mrl.get_stats()
        svc_stat = stats["api"]
        assert "tokens" in svc_stat
        assert "capacity" in svc_stat
        assert "fill_rate" in svc_stat


class TestRateLimitDecorator:
    async def test_with_rps_succeeds(self):
        @_u40.rate_limit(requests_per_second=100.0)
        async def my_func():
            return "ok"

        result = await my_func()
        assert result == "ok"

    async def test_with_service_succeeds(self):
        @_u40.rate_limit(service="tradier")
        async def tradier_call():
            return "tradier"

        result = await tradier_call()
        assert result == "tradier"

    def test_no_params_raises_value_error(self):
        with pytest.raises(ValueError):
            @_u40.rate_limit()
            async def bad_func():
                pass

    async def test_preserves_function_return(self):
        @_u40.rate_limit(requests_per_second=1000.0)
        async def compute(x, y):
            return x + y

        result = await compute(3, 4)
        assert result == 7

    async def test_with_burst_size(self):
        @_u40.rate_limit(requests_per_second=100.0, burst_size=50.0)
        async def my_func():
            return True

        assert await my_func() is True


class TestU40ConvenienceFunctions:
    async def test_acquire_tradier(self):
        # Should succeed without blocking (bucket starts full)
        await asyncio.wait_for(_u40.acquire_tradier(), timeout=2.0)

    def test_global_limiters_has_tradier(self):
        assert "tradier" in _u40._global_limiters._defaults

    def test_all_exports(self):
        for name in _u40.__all__:
            assert hasattr(_u40, name)


# ==============================================================================
# ──────────────────────────────────────────────────────────────────────────────
# U41 CircuitBreaker
# ──────────────────────────────────────────────────────────────────────────────
# ==============================================================================


class TestCircuitState:
    def test_closed_exists(self):
        assert CircuitState.CLOSED is not None

    def test_open_exists(self):
        assert CircuitState.OPEN is not None

    def test_half_open_exists(self):
        assert CircuitState.HALF_OPEN is not None

    def test_count(self):
        assert len(CircuitState) == 3


class TestCircuitBreakerConfig:
    def test_default_failure_threshold(self):
        c = CircuitBreakerConfig()
        assert c.failure_threshold == 5

    def test_default_recovery_timeout(self):
        c = CircuitBreakerConfig()
        assert c.recovery_timeout == 60.0

    def test_default_success_threshold(self):
        c = CircuitBreakerConfig()
        assert c.success_threshold == 1

    def test_default_timeout_is_none(self):
        c = CircuitBreakerConfig()
        assert c.timeout is None

    def test_custom_values(self):
        c = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        assert c.failure_threshold == 3
        assert c.recovery_timeout == 30.0


class TestCircuitBreakerError:
    def test_is_exception(self):
        assert issubclass(CircuitBreakerError, Exception)

    def test_can_raise(self):
        with pytest.raises(CircuitBreakerError):
            raise CircuitBreakerError("circuit open")

    def test_message(self):
        err = CircuitBreakerError("test msg")
        assert "test msg" in str(err)


class TestCircuitBreakerInit:
    def test_default_name(self):
        cb = CircuitBreaker()
        assert cb.name == "CircuitBreaker"

    def test_custom_name(self):
        cb = CircuitBreaker(name="MyBreaker")
        assert cb.name == "MyBreaker"

    def test_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_starts_failure_count_zero(self):
        cb = CircuitBreaker()
        assert cb.failure_count == 0

    def test_starts_success_count_zero(self):
        cb = CircuitBreaker()
        assert cb.success_count == 0

    def test_last_failure_time_none(self):
        cb = CircuitBreaker()
        assert cb.last_failure_time is None

    def test_config_set(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        assert cb.config.failure_threshold == 3
        assert cb.config.recovery_timeout == 30.0

    def test_expected_exception_defaults_to_exception(self):
        cb = CircuitBreaker()
        assert cb.expected_exception is Exception


class TestCircuitBreakerProperties:
    def test_is_closed_when_closed(self):
        cb = CircuitBreaker()
        assert cb.is_closed is True

    def test_is_open_when_closed(self):
        cb = CircuitBreaker()
        assert cb.is_open is False

    def test_is_open_when_open(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        assert cb.is_open is True

    def test_is_closed_when_open(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        assert cb.is_closed is False

    def test_failure_threshold_property(self):
        cb = CircuitBreaker(failure_threshold=7)
        assert cb.failure_threshold == 7

    def test_recovery_timeout_property(self):
        cb = CircuitBreaker(recovery_timeout=45.0)
        assert cb.recovery_timeout == 45.0


class TestCircuitBreakerOnFailure:
    def test_increments_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5)
        cb._on_failure(Exception("error"))
        assert cb.failure_count == 1

    def test_sets_last_failure_time(self):
        cb = CircuitBreaker()
        cb._on_failure(Exception("error"))
        assert cb.last_failure_time is not None

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb._on_failure(Exception("error"))
        assert cb.state == CircuitState.OPEN

    def test_no_open_before_threshold(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb._on_failure(Exception("error"))
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.HALF_OPEN
        cb._on_failure(Exception("error"))
        assert cb.state == CircuitState.OPEN


class TestCircuitBreakerOnSuccess:
    def test_resets_failure_count(self):
        cb = CircuitBreaker()
        cb.failure_count = 3
        cb._on_success()
        assert cb.failure_count == 0

    def test_closed_stays_closed(self):
        cb = CircuitBreaker()
        cb._on_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(success_threshold=1)
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0
        cb._on_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_insufficient_successes_stays_half_open(self):
        cb = CircuitBreaker(success_threshold=3)
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0
        cb._on_success()
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_increments_success_count(self):
        cb = CircuitBreaker(success_threshold=3)
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 1
        cb._on_success()
        assert cb.success_count == 2


class TestCircuitBreakerShouldAttemptReset:
    def test_no_failure_returns_false(self):
        cb = CircuitBreaker()
        assert cb._should_attempt_reset() is False

    def test_recent_failure_returns_false(self):
        cb = CircuitBreaker(recovery_timeout=60.0)
        cb.last_failure_time = time.time()
        assert cb._should_attempt_reset() is False

    def test_old_failure_returns_true(self):
        cb = CircuitBreaker(recovery_timeout=10.0)
        cb.last_failure_time = time.time() - 20.0  # 20s ago > 10s timeout
        assert cb._should_attempt_reset() is True


class TestCircuitBreakerTimeUntilRetry:
    def test_no_failure_returns_zero(self):
        cb = CircuitBreaker()
        assert cb._time_until_retry() == pytest.approx(0.0, abs=0.01)

    def test_recent_failure_returns_positive(self):
        cb = CircuitBreaker(recovery_timeout=60.0)
        cb.last_failure_time = time.time()
        remaining = cb._time_until_retry()
        assert remaining > 0.0

    def test_old_failure_returns_zero(self):
        cb = CircuitBreaker(recovery_timeout=10.0)
        cb.last_failure_time = time.time() - 20.0
        remaining = cb._time_until_retry()
        assert remaining == pytest.approx(0.0, abs=0.01)


class TestCircuitBreakerReset:
    def test_resets_state_to_closed(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_resets_failure_count(self):
        cb = CircuitBreaker()
        cb.failure_count = 10
        cb.reset()
        assert cb.failure_count == 0

    def test_resets_success_count(self):
        cb = CircuitBreaker()
        cb.success_count = 5
        cb.reset()
        assert cb.success_count == 0

    def test_resets_last_failure_time(self):
        cb = CircuitBreaker()
        cb.last_failure_time = time.time()
        cb.reset()
        assert cb.last_failure_time is None


class TestCircuitBreakerGetStats:
    def test_returns_dict(self):
        cb = CircuitBreaker(name="test")
        stats = cb.get_stats()
        assert isinstance(stats, dict)

    def test_contains_name(self):
        cb = CircuitBreaker(name="mybreaker")
        assert cb.get_stats()["name"] == "mybreaker"

    def test_contains_state(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert "state" in stats
        assert stats["state"] == "CLOSED"

    def test_contains_is_open(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert "is_open" in stats
        assert stats["is_open"] is False

    def test_contains_failure_count(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert stats["failure_count"] == 0

    def test_contains_thresholds(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        stats = cb.get_stats()
        assert stats["failure_threshold"] == 3
        assert stats["recovery_timeout"] == 30.0

    def test_open_circuit_stats(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        cb.failure_count = 5
        cb.last_failure_time = time.time()
        stats = cb.get_stats()
        assert stats["is_open"] is True
        assert stats["state"] == "OPEN"


class TestCircuitBreakerCall:
    async def test_call_success(self):
        cb = CircuitBreaker()

        async def good_func():
            return "result"

        result = await cb.call(good_func)
        assert result == "result"

    async def test_call_failure_opens_circuit(self):
        cb = CircuitBreaker(failure_threshold=1)

        async def bad_func():
            raise ValueError("error")

        with pytest.raises(ValueError):
            await cb.call(bad_func)

        assert cb.state == CircuitState.OPEN

    async def test_call_open_raises_circuit_breaker_error(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999.0)
        # Force open
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time()

        async def any_func():
            return "ok"

        with pytest.raises(CircuitBreakerError):
            await cb.call(any_func)

    async def test_call_success_resets_failure_count(self):
        cb = CircuitBreaker()
        cb.failure_count = 3

        async def good():
            return "ok"

        await cb.call(good)
        assert cb.failure_count == 0

    async def test_open_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        # Force open with old timestamp
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time() - 1.0  # 1s ago > 0.01s timeout

        async def good():
            return "ok"

        # Should transition to HALF_OPEN and attempt, then succeed → CLOSED
        result = await cb.call(good)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerContextManager:
    async def test_success_context_manager(self):
        cb = CircuitBreaker()
        async with cb:
            pass  # No exception → success
        assert cb.state == CircuitState.CLOSED

    async def test_failure_context_manager(self):
        cb = CircuitBreaker(failure_threshold=1)
        with pytest.raises(RuntimeError):
            async with cb:
                raise RuntimeError("test error")
        assert cb.failure_count == 1

    async def test_open_context_manager_raises(self):
        cb = CircuitBreaker(recovery_timeout=9999.0)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time()
        with pytest.raises(CircuitBreakerError):
            async with cb:
                pass

    async def test_aenter_half_open_when_timeout_elapsed(self):
        cb = CircuitBreaker(recovery_timeout=0.01)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time() - 1.0  # old enough
        returned = await cb.__aenter__()
        assert cb.state == CircuitState.HALF_OPEN
        assert returned is cb


class TestCircuitBreakerDecorator:
    async def test_decorator_success(self):
        cb = CircuitBreaker()

        @cb.decorator
        async def my_api():
            return 42

        assert await my_api() == 42

    async def test_decorator_failure_increments_count(self):
        cb = CircuitBreaker(failure_threshold=99)

        @cb.decorator
        async def failing():
            raise ValueError("api error")

        with pytest.raises(ValueError):
            await failing()

        assert cb.failure_count == 1

    async def test_decorator_preserves_args(self):
        cb = CircuitBreaker()

        @cb.decorator
        async def add(a, b):
            return a + b

        assert await add(3, 7) == 10


class TestCircuitBreakerFactory:
    async def test_circuit_breaker_decorator_factory(self):
        @_u41.circuit_breaker(failure_threshold=3, recovery_timeout=10.0)
        async def protected():
            return "value"

        assert await protected() == "value"

    def test_get_circuit_breaker_creates_instance(self):
        # Use unique name to avoid collision with module-level preconfigureds
        cb = _u41.get_circuit_breaker("test_unique_breaker_xyz", failure_threshold=3)
        assert isinstance(cb, CircuitBreaker)

    def test_get_circuit_breaker_is_cached(self):
        cb1 = _u41.get_circuit_breaker("cached_breaker_abc")
        cb2 = _u41.get_circuit_breaker("cached_breaker_abc")
        assert cb1 is cb2

    def test_tradier_breaker_is_circuit_breaker(self):
        assert isinstance(_u41.tradier_breaker, CircuitBreaker)

    def test_tradier_breaker_name(self):
        assert _u41.tradier_breaker.name == "tradier"


class TestU41ModuleExports:
    def test_all_exports_present(self):
        for name in _u41.__all__:
            assert hasattr(_u41, name)

    def test_circuit_breaker_error_in_all(self):
        assert "CircuitBreakerError" in _u41.__all__

    def test_circuit_breaker_in_all(self):
        assert "CircuitBreaker" in _u41.__all__
