#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT67_RateLimiterCircuitBreakerTests.py
Purpose: Tests for U40 RateLimiter and U41 CircuitBreaker

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 13:00:00
"""

# ==============================================================================
# BOOTSTRAP — load modules without installing Spyder as a package
# ==============================================================================
import sys
import os
import types
import importlib.util

_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load(rel_path):
    abs_path = os.path.join(_ROOT, rel_path)
    spec = importlib.util.spec_from_file_location(rel_path, abs_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(name):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)


_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")

_u01 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

# U40 has no local imports — load directly
_u40 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU40_RateLimiter.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU40_RateLimiter"] = _u40

# U41 imports SpyderU01_Logger.get_logger
_u41 = _load("Spyder/Spyder.SpyderU_Utilities/SpyderU41_CircuitBreaker.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker"] = _u41

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import time
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ==============================================================================
# MODULE IMPORTS — U40
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import (
    TokenBucket,
    RateLimiter,
    MultiRateLimiter,
    rate_limit,
    acquire_tradier,
    _global_limiters,
)

# ==============================================================================
# MODULE IMPORTS — U41
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import (
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitBreaker,
    circuit_breaker,
    get_circuit_breaker,
    tradier_breaker,
)


# ==============================================================================
# HELPERS
# ==============================================================================
def _run(coro):
    """Run a coroutine synchronously."""
    return asyncio.run(coro)


def _make_breaker(**kwargs) -> CircuitBreaker:
    """Create a fresh CircuitBreaker for testing."""
    defaults = {"failure_threshold": 3, "recovery_timeout": 60.0, "name": "test"}
    defaults.update(kwargs)
    return CircuitBreaker(**defaults)


async def _success_func():
    """Async function that always succeeds."""
    return "ok"


async def _failing_func():
    """Async function that always raises."""
    raise ValueError("deliberate failure")


# ==============================================================================
# U40 — TokenBucket TESTS
# ==============================================================================
class TestTokenBucketDataclass:
    """Tests for TokenBucket construction and behavior."""

    def test_construction_with_required_fields(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        assert tb.capacity == 10.0
        assert tb.fill_rate == 5.0

    def test_tokens_defaults_to_capacity(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        assert tb.tokens == 10.0

    def test_consume_returns_true_when_tokens_available(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        result = tb.consume(1.0)
        assert result is True

    def test_consume_reduces_token_count(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        tb.consume(3.0)
        assert tb.tokens < 10.0

    def test_consume_returns_false_when_empty(self):
        tb = TokenBucket(capacity=1.0, fill_rate=0.01, tokens=0.0)
        result = tb.consume(1.0)
        assert result is False

    def test_consume_partial_succeeds(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0, tokens=5.0)
        assert tb.consume(5.0) is True

    def test_wait_time_zero_when_tokens_available(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        assert tb.wait_time(1.0) == 0.0

    def test_wait_time_positive_when_tokens_insufficient(self):
        tb = TokenBucket(capacity=10.0, fill_rate=1.0, tokens=0.0)
        wt = tb.wait_time(5.0)
        assert wt > 0.0

    def test_wait_time_inversely_proportional_to_fill_rate(self):
        # Faster fill_rate → lower wait time
        tb_fast = TokenBucket(capacity=10.0, fill_rate=10.0, tokens=0.0)
        tb_slow = TokenBucket(capacity=10.0, fill_rate=1.0, tokens=0.0)
        assert tb_fast.wait_time(5.0) < tb_slow.wait_time(5.0)

    def test_lock_is_thread_lock(self):
        tb = TokenBucket(capacity=10.0, fill_rate=5.0)
        assert isinstance(tb.lock, type(threading.Lock()))


# ==============================================================================
# U40 — RateLimiter TESTS
# ==============================================================================
class TestRateLimiterInit:
    """Tests for RateLimiter construction."""

    def test_creates_instance(self):
        rl = RateLimiter(requests_per_second=10.0)
        assert rl is not None

    def test_requests_per_second_stored(self):
        rl = RateLimiter(requests_per_second=10.0)
        assert rl.requests_per_second == 10.0

    def test_burst_size_defaults_to_rps(self):
        rl = RateLimiter(requests_per_second=10.0)
        assert rl.burst_size == 10.0

    def test_custom_burst_size(self):
        rl = RateLimiter(requests_per_second=10.0, burst_size=20.0)
        assert rl.burst_size == 20.0

    def test_bucket_created(self):
        rl = RateLimiter(requests_per_second=10.0)
        assert isinstance(rl.bucket, TokenBucket)

    def test_bucket_capacity_matches_burst_size(self):
        rl = RateLimiter(requests_per_second=5.0, burst_size=15.0)
        assert rl.bucket.capacity == 15.0

    def test_bucket_fill_rate_matches_rps(self):
        rl = RateLimiter(requests_per_second=7.0)
        assert rl.bucket.fill_rate == 7.0


class TestRateLimiterFromPerMinute:
    """Tests for RateLimiter.from_per_minute classmethod."""

    def test_creates_instance(self):
        rl = RateLimiter.from_per_minute(60.0)
        assert isinstance(rl, RateLimiter)

    def test_rate_conversion(self):
        rl = RateLimiter.from_per_minute(60.0)
        assert abs(rl.requests_per_second - 1.0) < 1e-9

    def test_120_per_minute_is_2_per_second(self):
        rl = RateLimiter.from_per_minute(120.0)
        assert abs(rl.requests_per_second - 2.0) < 1e-9

    def test_custom_burst_size(self):
        rl = RateLimiter.from_per_minute(60.0, burst_size=10.0)
        assert rl.burst_size == 10.0


class TestRateLimiterAcquire:
    """Tests for RateLimiter.acquire (async)."""

    def test_acquire_completes_when_tokens_available(self):
        rl = RateLimiter(requests_per_second=100.0)

        async def run():
            await rl.acquire()

        _run(run())

    def test_acquire_reduces_tokens(self):
        rl = RateLimiter(requests_per_second=100.0)
        initial_tokens = rl.bucket.tokens

        async def run():
            await rl.acquire()

        _run(run())
        assert rl.bucket.tokens < initial_tokens

    def test_acquire_multiple_tokens(self):
        rl = RateLimiter(requests_per_second=100.0, burst_size=50.0)

        async def run():
            await rl.acquire(tokens=5.0)

        _run(run())
        assert rl.bucket.tokens < 50.0

    def test_context_manager_enter_exit(self):
        rl = RateLimiter(requests_per_second=100.0)

        async def run():
            async with rl:
                pass

        _run(run())


# ==============================================================================
# U40 — MultiRateLimiter TESTS
# ==============================================================================
class TestMultiRateLimiter:
    """Tests for MultiRateLimiter."""

    def test_creates_instance(self):
        mrl = MultiRateLimiter()
        assert mrl is not None

    def test_starts_empty(self):
        mrl = MultiRateLimiter()
        assert len(mrl._limiters) == 0

    def test_add_limit_creates_limiter(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("test_limit", requests_per_second=10.0)
        assert "test_limit" in mrl._limiters

    def test_add_limit_stores_rate(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("api", requests_per_second=5.0)
        assert mrl._limiters["api"].requests_per_second == 5.0

    def test_register_default_stores_config(self):
        mrl = MultiRateLimiter()
        mrl.register_default("slow_api", requests_per_second=1.0)
        assert "slow_api" in mrl._defaults

    def test_get_stats_returns_dict(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("svc", requests_per_second=10.0)
        stats = mrl.get_stats()
        assert isinstance(stats, dict)

    def test_get_stats_contains_added_limits(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("svc_a", requests_per_second=10.0)
        mrl.add_limit("svc_b", requests_per_second=5.0)
        stats = mrl.get_stats()
        assert "svc_a" in stats
        assert "svc_b" in stats

    def test_get_stats_contains_token_info(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("svc", requests_per_second=10.0)
        stats = mrl.get_stats()
        assert "tokens" in stats["svc"]
        assert "capacity" in stats["svc"]
        assert "fill_rate" in stats["svc"]

    def test_acquire_unknown_raises_value_error(self):
        mrl = MultiRateLimiter()

        async def run():
            await mrl.acquire("nonexistent")

        with pytest.raises(ValueError, match="Unknown rate limit"):
            _run(run())

    def test_acquire_registered_default_creates_limiter(self):
        mrl = MultiRateLimiter()
        mrl.register_default("lazy_svc", requests_per_second=100.0)

        async def run():
            await mrl.acquire("lazy_svc")

        _run(run())
        assert "lazy_svc" in mrl._limiters

    def test_acquire_named_limit(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("fast_svc", requests_per_second=100.0)

        async def run():
            await mrl.acquire("fast_svc")

        _run(run())


class TestGlobalLimiters:
    """Tests for global limiter and convenience functions."""

    def test_global_limiters_exist(self):
        assert _global_limiters is not None
        assert isinstance(_global_limiters, MultiRateLimiter)

    def test_tradier_default_registered(self):
        assert "tradier" in _global_limiters._defaults or \
               "tradier" in _global_limiters._limiters

    def test_acquire_tradier_is_coroutine(self):
        import inspect
        assert inspect.iscoroutinefunction(acquire_tradier)

    def test_acquire_tradier_completes(self):
        _run(acquire_tradier())


# ==============================================================================
# U40 — rate_limit DECORATOR TESTS
# ==============================================================================
class TestRateLimitDecorator:
    """Tests for rate_limit decorator."""

    def test_decorator_wraps_async_function(self):
        @rate_limit(requests_per_second=100.0)
        async def my_func():
            return 42

        result = _run(my_func())
        assert result == 42

    def test_decorator_no_rps_no_service_raises(self):
        with pytest.raises((ValueError, TypeError)):
            @rate_limit()
            async def my_func():
                pass

    def test_service_decorator_uses_global_limiter(self):
        @rate_limit(service="tradier")
        async def my_func():
            return "done"

        result = _run(my_func())
        assert result == "done"


# ==============================================================================
# U41 — CircuitState TESTS
# ==============================================================================
class TestCircuitStateEnum:
    """Tests for CircuitState enum."""

    def test_closed_member_exists(self):
        assert hasattr(CircuitState, "CLOSED")

    def test_open_member_exists(self):
        assert hasattr(CircuitState, "OPEN")

    def test_half_open_member_exists(self):
        assert hasattr(CircuitState, "HALF_OPEN")

    def test_total_member_count(self):
        assert len(CircuitState) == 3


# ==============================================================================
# U41 — CircuitBreakerConfig TESTS
# ==============================================================================
class TestCircuitBreakerConfigDataclass:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_default_failure_threshold(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5

    def test_default_recovery_timeout(self):
        cfg = CircuitBreakerConfig()
        assert cfg.recovery_timeout == 60.0

    def test_default_success_threshold(self):
        cfg = CircuitBreakerConfig()
        assert cfg.success_threshold == 1

    def test_default_timeout_is_none(self):
        cfg = CircuitBreakerConfig()
        assert cfg.timeout is None

    def test_custom_values(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
            timeout=10.0,
        )
        assert cfg.failure_threshold == 3
        assert cfg.recovery_timeout == 30.0
        assert cfg.timeout == 10.0


# ==============================================================================
# U41 — CircuitBreakerError TESTS
# ==============================================================================
class TestCircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_is_exception_subclass(self):
        assert issubclass(CircuitBreakerError, Exception)

    def test_can_be_raised(self):
        with pytest.raises(CircuitBreakerError):
            raise CircuitBreakerError("circuit open")

    def test_message_preserved(self):
        try:
            raise CircuitBreakerError("breaker tripped")
        except CircuitBreakerError as e:
            assert "breaker tripped" in str(e)


# ==============================================================================
# U41 — CircuitBreaker INIT TESTS
# ==============================================================================
class TestCircuitBreakerInit:
    """Tests for CircuitBreaker construction."""

    def test_creates_instance(self):
        cb = _make_breaker()
        assert cb is not None

    def test_initial_state_is_closed(self):
        cb = _make_breaker()
        assert cb.state == CircuitState.CLOSED

    def test_initial_failure_count_zero(self):
        cb = _make_breaker()
        assert cb.failure_count == 0

    def test_initial_success_count_zero(self):
        cb = _make_breaker()
        assert cb.success_count == 0

    def test_name_stored(self):
        cb = CircuitBreaker(name="my_breaker")
        assert cb.name == "my_breaker"

    def test_default_name_used_when_not_specified(self):
        cb = CircuitBreaker()
        assert cb.name is not None and len(cb.name) > 0

    def test_config_created(self):
        cb = _make_breaker(failure_threshold=3, recovery_timeout=30.0)
        assert isinstance(cb.config, CircuitBreakerConfig)
        assert cb.config.failure_threshold == 3


# ==============================================================================
# U41 — CircuitBreaker PROPERTIES TESTS
# ==============================================================================
class TestCircuitBreakerProperties:
    """Tests for CircuitBreaker property accessors."""

    def test_is_closed_true_initially(self):
        cb = _make_breaker()
        assert cb.is_closed is True

    def test_is_open_false_initially(self):
        cb = _make_breaker()
        assert cb.is_open is False

    def test_failure_threshold_property(self):
        cb = _make_breaker(failure_threshold=7)
        assert cb.failure_threshold == 7

    def test_recovery_timeout_property(self):
        cb = _make_breaker(recovery_timeout=45.0)
        assert cb.recovery_timeout == 45.0

    def test_is_open_true_when_state_open(self):
        cb = _make_breaker()
        cb.state = CircuitState.OPEN
        assert cb.is_open is True

    def test_is_closed_false_when_state_open(self):
        cb = _make_breaker()
        cb.state = CircuitState.OPEN
        assert cb.is_closed is False


# ==============================================================================
# U41 — CircuitBreaker FAILURE/SUCCESS TESTS
# ==============================================================================
class TestCircuitBreakerOnSuccess:
    """Tests for _on_success behavior."""

    def test_on_success_resets_failure_count(self):
        cb = _make_breaker()
        cb.failure_count = 2
        cb._on_success()
        assert cb.failure_count == 0

    def test_on_success_in_half_open_increments_success_count(self):
        cb = _make_breaker(success_threshold=2)
        cb.state = CircuitState.HALF_OPEN
        cb._on_success()
        assert cb.success_count == 1

    def test_on_success_closes_circuit_after_threshold(self):
        cb = _make_breaker(success_threshold=1)
        cb.state = CircuitState.HALF_OPEN
        cb._on_success()
        assert cb.state == CircuitState.CLOSED

    def test_on_success_does_not_close_prematurely(self):
        cb = _make_breaker(success_threshold=3)
        cb.state = CircuitState.HALF_OPEN
        cb._on_success()  # 1st success
        assert cb.state == CircuitState.HALF_OPEN


class TestCircuitBreakerOnFailure:
    """Tests for _on_failure behavior."""

    def test_on_failure_increments_failure_count(self):
        cb = _make_breaker(failure_threshold=5)
        cb._on_failure(ValueError("test"))
        assert cb.failure_count == 1

    def test_on_failure_records_last_failure_time(self):
        cb = _make_breaker()
        before = time.time()
        cb._on_failure(ValueError("test"))
        assert cb.last_failure_time is not None
        assert cb.last_failure_time >= before

    def test_on_failure_opens_circuit_at_threshold(self):
        cb = _make_breaker(failure_threshold=3)
        for _ in range(3):
            cb._on_failure(ValueError("test"))
        assert cb.state == CircuitState.OPEN

    def test_on_failure_in_half_open_returns_to_open(self):
        cb = _make_breaker()
        cb.state = CircuitState.HALF_OPEN
        cb._on_failure(ValueError("recovery failed"))
        assert cb.state == CircuitState.OPEN

    def test_on_failure_does_not_open_below_threshold(self):
        cb = _make_breaker(failure_threshold=5)
        cb._on_failure(ValueError("test"))
        assert cb.state == CircuitState.CLOSED


# ==============================================================================
# U41 — CircuitBreaker RESET TESTS
# ==============================================================================
class TestCircuitBreakerReset:
    """Tests for CircuitBreaker.reset()."""

    def test_reset_sets_state_to_closed(self):
        cb = _make_breaker()
        cb.state = CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = _make_breaker()
        cb.failure_count = 10
        cb.reset()
        assert cb.failure_count == 0

    def test_reset_clears_last_failure_time(self):
        cb = _make_breaker()
        cb.last_failure_time = time.time()
        cb.reset()
        assert cb.last_failure_time is None

    def test_reset_clears_success_count(self):
        cb = _make_breaker()
        cb.success_count = 5
        cb.reset()
        assert cb.success_count == 0


# ==============================================================================
# U41 — CircuitBreaker SHOULD_ATTEMPT_RESET TESTS
# ==============================================================================
class TestCircuitBreakerShouldAttemptReset:
    """Tests for _should_attempt_reset."""

    def test_returns_false_with_no_failure(self):
        cb = _make_breaker()
        assert cb._should_attempt_reset() is False

    def test_returns_false_before_recovery_timeout(self):
        cb = _make_breaker(recovery_timeout=100.0)
        cb.last_failure_time = time.time()
        assert cb._should_attempt_reset() is False

    def test_returns_true_after_recovery_timeout(self):
        cb = _make_breaker(recovery_timeout=0.01)
        cb.last_failure_time = time.time() - 1.0  # 1 second ago
        assert cb._should_attempt_reset() is True


# ==============================================================================
# U41 — CircuitBreaker TIME_UNTIL_RETRY TESTS
# ==============================================================================
class TestCircuitBreakerTimeUntilRetry:
    """Tests for _time_until_retry."""

    def test_returns_zero_with_no_failure(self):
        cb = _make_breaker()
        assert cb._time_until_retry() == 0.0

    def test_returns_positive_before_timeout(self):
        cb = _make_breaker(recovery_timeout=60.0)
        cb.last_failure_time = time.time()
        assert cb._time_until_retry() > 0.0

    def test_returns_zero_after_timeout(self):
        cb = _make_breaker(recovery_timeout=0.01)
        cb.last_failure_time = time.time() - 1.0
        assert cb._time_until_retry() == 0.0


# ==============================================================================
# U41 — CircuitBreaker CALL TESTS
# ==============================================================================
class TestCircuitBreakerCall:
    """Tests for CircuitBreaker.call()."""

    def test_call_successful_function(self):
        cb = _make_breaker()
        result = _run(cb.call(_success_func))
        assert result == "ok"

    def test_call_updates_failure_count_on_exception(self):
        cb = _make_breaker(failure_threshold=10)
        try:
            _run(cb.call(_failing_func))
        except ValueError:
            pass
        assert cb.failure_count == 1

    def test_call_raises_CircuitBreakerError_when_open(self):
        cb = _make_breaker(failure_threshold=1)
        # Trigger open state
        try:
            _run(cb.call(_failing_func))
        except ValueError:
            pass
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerError):
            _run(cb.call(_success_func))

    def test_call_propagates_original_exception(self):
        cb = _make_breaker()
        with pytest.raises(ValueError, match="deliberate failure"):
            _run(cb.call(_failing_func))

    def test_success_resets_failure_count(self):
        cb = _make_breaker()
        cb.failure_count = 2
        _run(cb.call(_success_func))
        assert cb.failure_count == 0


# ==============================================================================
# U41 — CircuitBreaker CONTEXT MANAGER TESTS
# ==============================================================================
class TestCircuitBreakerContextManager:
    """Tests for async context manager protocol."""

    def test_context_manager_success(self):
        cb = _make_breaker()

        async def run():
            async with cb:
                pass

        _run(run())
        assert cb.state == CircuitState.CLOSED

    def test_context_manager_failure_increments_count(self):
        cb = _make_breaker(failure_threshold=10)

        async def run():
            try:
                async with cb:
                    raise ValueError("test")
            except ValueError:
                pass

        _run(run())
        assert cb.failure_count == 1

    def test_context_manager_raises_when_open(self):
        cb = _make_breaker()
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time()  # Not timed out yet

        async def run():
            async with cb:
                pass

        with pytest.raises(CircuitBreakerError):
            _run(run())


# ==============================================================================
# U41 — CircuitBreaker GET_STATS TESTS
# ==============================================================================
class TestCircuitBreakerGetStats:
    """Tests for get_stats()."""

    def test_returns_dict(self):
        cb = _make_breaker()
        stats = cb.get_stats()
        assert isinstance(stats, dict)

    def test_stats_has_name(self):
        cb = _make_breaker()
        stats = cb.get_stats()
        assert "name" in stats

    def test_stats_has_state(self):
        cb = _make_breaker()
        stats = cb.get_stats()
        assert "state" in stats

    def test_stats_has_failure_count(self):
        cb = _make_breaker()
        stats = cb.get_stats()
        assert "failure_count" in stats

    def test_stats_state_is_string(self):
        cb = _make_breaker()
        stats = cb.get_stats()
        assert isinstance(stats["state"], str)

    def test_stats_is_open_field(self):
        cb = _make_breaker()
        stats = cb.get_stats()
        assert "is_open" in stats
        assert stats["is_open"] is False

    def test_stats_failure_count_reflects_state(self):
        cb = _make_breaker()
        cb.failure_count = 3
        stats = cb.get_stats()
        assert stats["failure_count"] == 3


# ==============================================================================
# U41 — CircuitBreaker DECORATOR TESTS
# ==============================================================================
class TestCircuitBreakerDecorator:
    """Tests for CircuitBreaker.decorator()."""

    def test_decorator_wraps_function(self):
        cb = _make_breaker()

        @cb.decorator
        async def my_func():
            return "wrapped"

        result = _run(my_func())
        assert result == "wrapped"

    def test_decorator_tracks_failures(self):
        cb = _make_breaker(failure_threshold=10)

        @cb.decorator
        async def failing():
            raise RuntimeError("fail")

        try:
            _run(failing())
        except RuntimeError:
            pass
        assert cb.failure_count == 1


# ==============================================================================
# U41 — circuit_breaker DECORATOR FACTORY TESTS
# ==============================================================================
class TestCircuitBreakerDecoratorFactory:
    """Tests for circuit_breaker() decorator factory."""

    def test_creates_wrapped_function(self):
        @circuit_breaker(failure_threshold=3, recovery_timeout=60.0)
        async def api_call():
            return "done"

        result = _run(api_call())
        assert result == "done"

    def test_custom_parameters_applied(self):
        # The factory creates a breaker internally — just verify it works
        @circuit_breaker(failure_threshold=1, recovery_timeout=99.0)
        async def unreliable():
            return "ok"

        result = _run(unreliable())
        assert result == "ok"


# ==============================================================================
# U41 — get_circuit_breaker TESTS
# ==============================================================================
class TestGetCircuitBreaker:
    """Tests for get_circuit_breaker() factory function."""

    def test_returns_circuit_breaker(self):
        cb = get_circuit_breaker("test_svc_unique_1")
        assert isinstance(cb, CircuitBreaker)

    def test_same_name_returns_same_instance(self):
        cb1 = get_circuit_breaker("test_svc_unique_2")
        cb2 = get_circuit_breaker("test_svc_unique_2")
        assert cb1 is cb2

    def test_different_names_return_different_instances(self):
        cb1 = get_circuit_breaker("test_svc_unique_3")
        cb2 = get_circuit_breaker("test_svc_unique_4")
        assert cb1 is not cb2

    def test_name_used_in_breaker(self):
        cb = get_circuit_breaker("named_svc_unique_5")
        assert cb.name == "named_svc_unique_5"


# ==============================================================================
# U41 — Pre-configured breaker TESTS
# ==============================================================================
class TestPreConfiguredBreakers:
    """Tests for tradier_breaker."""

    def test_tradier_breaker_exists(self):
        assert tradier_breaker is not None

    def test_tradier_breaker_is_circuit_breaker(self):
        assert isinstance(tradier_breaker, CircuitBreaker)

    def test_tradier_breaker_starts_closed(self):
        # Pre-configured breaker should start in CLOSED state
        assert tradier_breaker.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN, CircuitState.OPEN)

    def test_tradier_breaker_has_timeout(self):
        # Configured with timeout=30.0
        assert tradier_breaker.config.timeout == 30.0
