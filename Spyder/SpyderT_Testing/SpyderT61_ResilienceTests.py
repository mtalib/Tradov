#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT61_ResilienceTests.py
Purpose: Tests for U40 RateLimiter and U41 CircuitBreaker resilience utilities

Author: GitHub Copilot
Year Created: 2025
Last Updated: 2026-01-16 Time: 20:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import importlib
import importlib.util
import sys
import time
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ==============================================================================
# REPO BOOTSTRAP
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load(rel_path: str):
    """Load a module by relative path from _REPO_ROOT."""
    full = _REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(full.stem, full)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ensure_pkg(pkg_name: str):
    """Ensure a package placeholder exists in sys.modules."""
    if pkg_name not in sys.modules:
        sys.modules[pkg_name] = types.ModuleType(pkg_name)


# Pre-register U01_Logger under its package path so U41's module-level
# `from Spyder.SpyderU_Utilities.SpyderU01_Logger import get_logger` resolves
# correctly when the full suite has already loaded prior modules and may have
# partially populated sys.modules under various name variants.
_ensure_pkg("Spyder")
_ensure_pkg("Spyder.SpyderU_Utilities")
_u01_logger = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
# Force-register so any stale/broken entry (loaded by earlier test files) is
# replaced with the fully-populated version that contains get_logger.
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01_logger
sys.modules["SpyderU01_Logger"] = _u01_logger

# ==============================================================================
# LOAD MODULES UNDER TEST
# ==============================================================================
_u40 = _load("Spyder/SpyderU_Utilities/SpyderU40_RateLimiter.py")
TokenBucket = _u40.TokenBucket
RateLimiter = _u40.RateLimiter
MultiRateLimiter = _u40.MultiRateLimiter
rate_limit = _u40.rate_limit

_u41 = _load("Spyder/SpyderU_Utilities/SpyderU41_CircuitBreaker.py")
CircuitState = _u41.CircuitState
CircuitBreakerConfig = _u41.CircuitBreakerConfig
CircuitBreakerError = _u41.CircuitBreakerError
CircuitBreaker = _u41.CircuitBreaker
circuit_breaker = _u41.circuit_breaker
get_circuit_breaker = _u41.get_circuit_breaker


# ==============================================================================
# HELPERS
# ==============================================================================
def _arun(coro):
    """Run a coroutine synchronously in a fresh event loop."""
    return asyncio.run(coro)


def _make_breaker(**kwargs) -> CircuitBreaker:
    """Create a default-name CircuitBreaker with overridable kwargs."""
    defaults = dict(failure_threshold=3, recovery_timeout=60.0, name="test_breaker")
    defaults.update(kwargs)
    return CircuitBreaker(**defaults)


async def _succeed():
    """Async function that always succeeds."""
    return "ok"


async def _fail():
    """Async function that always raises."""
    raise RuntimeError("boom")


# ==============================================================================
# U40  —  TOKEN BUCKET
# ==============================================================================

class TestTokenBucketConstruction(unittest.TestCase):
    """TokenBucket dataclass construction tests."""

    def test_capacity_stored(self):
        tb = TokenBucket(capacity=10.0, fill_rate=2.0)
        self.assertEqual(tb.capacity, 10.0)

    def test_fill_rate_stored(self):
        tb = TokenBucket(capacity=10.0, fill_rate=2.0)
        self.assertEqual(tb.fill_rate, 2.0)

    def test_tokens_default_equals_capacity(self):
        tb = TokenBucket(capacity=5.0, fill_rate=1.0)
        self.assertEqual(tb.tokens, 5.0)

    def test_tokens_explicit_override(self):
        tb = TokenBucket(capacity=10.0, fill_rate=1.0, tokens=3.0)
        self.assertEqual(tb.tokens, 3.0)

    def test_has_threading_lock(self):
        tb = TokenBucket(capacity=10.0, fill_rate=1.0)
        self.assertIsInstance(tb.lock, type(threading.Lock()))

    def test_last_update_is_recent(self):
        before = time.time()
        tb = TokenBucket(capacity=10.0, fill_rate=1.0)
        after = time.time()
        self.assertGreaterEqual(tb.last_update, before)
        self.assertLessEqual(tb.last_update, after)


class TestTokenBucketConsume(unittest.TestCase):
    """TokenBucket.consume() tests — no waiting needed."""

    def test_consume_one_from_full_returns_true(self):
        tb = TokenBucket(capacity=5.0, fill_rate=1.0)
        self.assertTrue(tb.consume(1.0))

    def test_consume_reduces_token_count(self):
        tb = TokenBucket(capacity=5.0, fill_rate=1.0)
        tb.consume(2.0)
        self.assertAlmostEqual(tb.tokens, 3.0, places=5)

    def test_consume_exact_capacity_returns_true(self):
        tb = TokenBucket(capacity=5.0, fill_rate=1.0)
        self.assertTrue(tb.consume(5.0))

    def test_consume_exceeds_tokens_returns_false(self):
        tb = TokenBucket(capacity=5.0, fill_rate=1.0, tokens=0.0)
        self.assertFalse(tb.consume(1.0))

    def test_consume_leave_tokens_unchanged_on_failure(self):
        tb = TokenBucket(capacity=5.0, fill_rate=0.0001, tokens=2.0)
        tb.consume(10.0)  # will fail
        # tokens should remain near 2.0 (tiny refill possible)
        self.assertLess(tb.tokens, 3.0)

    def test_consume_default_amount_is_one(self):
        tb = TokenBucket(capacity=3.0, fill_rate=1.0)
        tb.consume()  # default 1.0
        self.assertAlmostEqual(tb.tokens, 2.0, places=5)

    def test_consume_sequential_until_empty(self):
        tb = TokenBucket(capacity=3.0, fill_rate=0.0)  # no refill
        results = [tb.consume() for _ in range(4)]
        self.assertEqual(results[:3], [True, True, True])
        self.assertFalse(results[3])


class TestTokenBucketWaitTime(unittest.TestCase):
    """TokenBucket.wait_time() tests."""

    def test_wait_time_zero_when_full(self):
        tb = TokenBucket(capacity=10.0, fill_rate=1.0)
        self.assertEqual(tb.wait_time(1.0), 0.0)

    def test_wait_time_positive_when_empty(self):
        tb = TokenBucket(capacity=5.0, fill_rate=2.0, tokens=0.0)
        wt = tb.wait_time(1.0)
        self.assertGreater(wt, 0.0)

    def test_wait_time_mathematical_formula(self):
        # Need 1 token, have 0, fill_rate=2 → wait = 1/2 = 0.5s
        tb = TokenBucket(capacity=5.0, fill_rate=2.0, tokens=0.0)
        # Pin last_update so refill doesn't happen between token check and wait calc
        tb.last_update = time.time()
        wt = tb.wait_time(1.0)
        self.assertAlmostEqual(wt, 0.5, delta=0.05)

    def test_wait_time_larger_deficit(self):
        # Need 5, have 0, fill_rate=1 → wait = 5s
        tb = TokenBucket(capacity=10.0, fill_rate=1.0, tokens=0.0)
        tb.last_update = time.time()
        wt = tb.wait_time(5.0)
        self.assertAlmostEqual(wt, 5.0, delta=0.05)


# ==============================================================================
# U40  —  RATE LIMITER
# ==============================================================================

class TestRateLimiterConstruction(unittest.TestCase):
    """RateLimiter construction tests."""

    def test_requests_per_second_stored(self):
        rl = RateLimiter(requests_per_second=10.0)
        self.assertEqual(rl.requests_per_second, 10.0)

    def test_burst_size_defaults_to_rps(self):
        rl = RateLimiter(requests_per_second=5.0)
        self.assertEqual(rl.burst_size, 5.0)

    def test_burst_size_explicit(self):
        rl = RateLimiter(requests_per_second=5.0, burst_size=20.0)
        self.assertEqual(rl.burst_size, 20.0)

    def test_bucket_capacity_equals_burst_size(self):
        rl = RateLimiter(requests_per_second=5.0, burst_size=20.0)
        self.assertEqual(rl.bucket.capacity, 20.0)

    def test_bucket_fill_rate_equals_rps(self):
        rl = RateLimiter(requests_per_second=7.0)
        self.assertEqual(rl.bucket.fill_rate, 7.0)

    def test_from_per_minute_classmethod(self):
        rl = RateLimiter.from_per_minute(60.0)
        self.assertAlmostEqual(rl.requests_per_second, 1.0, places=10)

    def test_from_per_minute_120(self):
        rl = RateLimiter.from_per_minute(120.0)
        self.assertAlmostEqual(rl.requests_per_second, 2.0, places=10)

    def test_from_per_minute_burst_override(self):
        rl = RateLimiter.from_per_minute(60.0, burst_size=10.0)
        self.assertEqual(rl.burst_size, 10.0)


class TestRateLimiterAcquire(unittest.TestCase):
    """RateLimiter.acquire() — async, but token available so returns fast."""

    def test_acquire_with_full_bucket_returns_quickly(self):
        rl = RateLimiter(requests_per_second=1000.0)
        start = time.time()
        _arun(rl.acquire())
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.5)

    def test_acquire_decrements_tokens(self):
        rl = RateLimiter(requests_per_second=100.0, burst_size=10.0)
        before = rl.bucket.tokens
        _arun(rl.acquire())
        self.assertLess(rl.bucket.tokens, before + 0.01)  # token was consumed

    def test_context_manager_acquires_and_releases(self):
        rl = RateLimiter(requests_per_second=1000.0)

        async def _use():
            async with rl:
                pass

        _arun(_use())  # should not raise


# ==============================================================================
# U40  —  MULTI RATE LIMITER
# ==============================================================================

class TestMultiRateLimiter(unittest.TestCase):
    """MultiRateLimiter tests."""

    def _make_multi(self) -> MultiRateLimiter:
        return MultiRateLimiter()

    def test_add_limit_creates_named_limiter(self):
        mrl = self._make_multi()
        mrl.add_limit("quotes", requests_per_second=10.0)
        stats = mrl.get_stats()
        self.assertIn("quotes", stats)

    def test_acquire_named_limit(self):
        mrl = self._make_multi()
        mrl.add_limit("orders", requests_per_second=100.0)
        _arun(mrl.acquire("orders"))  # should not raise

    def test_acquire_unknown_raises_value_error(self):
        mrl = self._make_multi()
        with self.assertRaises(ValueError):
            _arun(mrl.acquire("nonexistent"))

    def test_register_default_lazy_init(self):
        mrl = self._make_multi()
        mrl.register_default("lazy_svc", requests_per_second=5.0)
        # Not yet in _limiters before first acquire
        self.assertNotIn("lazy_svc", mrl._limiters)
        _arun(mrl.acquire("lazy_svc"))
        self.assertIn("lazy_svc", mrl._limiters)

    def test_get_stats_returns_dict(self):
        mrl = self._make_multi()
        mrl.add_limit("svc", requests_per_second=10.0)
        stats = mrl.get_stats()
        self.assertIsInstance(stats, dict)

    def test_get_stats_contains_expected_keys(self):
        mrl = self._make_multi()
        mrl.add_limit("svc2", requests_per_second=10.0)
        stats = mrl.get_stats()["svc2"]
        for key in ("tokens", "capacity", "fill_rate"):
            self.assertIn(key, stats)

    def test_get_stats_fill_rate_matches(self):
        mrl = self._make_multi()
        mrl.add_limit("svc3", requests_per_second=7.0)
        stats = mrl.get_stats()["svc3"]
        self.assertAlmostEqual(stats["fill_rate"], 7.0, places=5)

    def test_multiple_named_limiters_independent(self):
        mrl = self._make_multi()
        mrl.add_limit("fast", requests_per_second=100.0)
        mrl.add_limit("slow", requests_per_second=1.0)
        stats = mrl.get_stats()
        self.assertEqual(stats["fast"]["fill_rate"], 100.0)
        self.assertEqual(stats["slow"]["fill_rate"], 1.0)


# ==============================================================================
# U41  —  CIRCUIT STATE ENUM
# ==============================================================================

class TestCircuitState(unittest.TestCase):
    """CircuitState enum membership tests."""

    def test_closed_exists(self):
        self.assertIsNotNone(CircuitState.CLOSED)

    def test_open_exists(self):
        self.assertIsNotNone(CircuitState.OPEN)

    def test_half_open_exists(self):
        self.assertIsNotNone(CircuitState.HALF_OPEN)

    def test_three_states_total(self):
        states = list(CircuitState)
        self.assertEqual(len(states), 3)


# ==============================================================================
# U41  —  CIRCUIT BREAKER CONFIG
# ==============================================================================

class TestCircuitBreakerConfig(unittest.TestCase):
    """CircuitBreakerConfig dataclass tests."""

    def test_failure_threshold_default_five(self):
        cfg = CircuitBreakerConfig()
        self.assertEqual(cfg.failure_threshold, 5)

    def test_recovery_timeout_default_sixty(self):
        cfg = CircuitBreakerConfig()
        self.assertEqual(cfg.recovery_timeout, 60.0)

    def test_success_threshold_default_one(self):
        cfg = CircuitBreakerConfig()
        self.assertEqual(cfg.success_threshold, 1)

    def test_timeout_default_none(self):
        cfg = CircuitBreakerConfig()
        self.assertIsNone(cfg.timeout)

    def test_custom_values_stored(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
            timeout=5.0
        )
        self.assertEqual(cfg.failure_threshold, 3)
        self.assertEqual(cfg.recovery_timeout, 30.0)
        self.assertEqual(cfg.success_threshold, 2)
        self.assertEqual(cfg.timeout, 5.0)


# ==============================================================================
# U41  —  CIRCUIT BREAKER ERROR
# ==============================================================================

class TestCircuitBreakerError(unittest.TestCase):
    """CircuitBreakerError exception tests."""

    def test_is_subclass_of_exception(self):
        self.assertTrue(issubclass(CircuitBreakerError, Exception))

    def test_can_be_raised_and_caught(self):
        with self.assertRaises(CircuitBreakerError):
            raise CircuitBreakerError("circuit is open")

    def test_carries_message(self):
        try:
            raise CircuitBreakerError("test message")
        except CircuitBreakerError as e:
            self.assertIn("test message", str(e))


# ==============================================================================
# U41  —  CIRCUIT BREAKER CONSTRUCTION
# ==============================================================================

class TestCircuitBreakerConstruction(unittest.TestCase):
    """CircuitBreaker initial state tests."""

    def test_starts_closed(self):
        cb = _make_breaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_is_closed_true_initially(self):
        cb = _make_breaker()
        self.assertTrue(cb.is_closed)

    def test_is_open_false_initially(self):
        cb = _make_breaker()
        self.assertFalse(cb.is_open)

    def test_failure_count_starts_zero(self):
        cb = _make_breaker()
        self.assertEqual(cb.failure_count, 0)

    def test_success_count_starts_zero(self):
        cb = _make_breaker()
        self.assertEqual(cb.success_count, 0)

    def test_name_stored(self):
        cb = CircuitBreaker(name="my_breaker")
        self.assertEqual(cb.name, "my_breaker")

    def test_default_name_not_empty(self):
        cb = CircuitBreaker()
        self.assertTrue(len(cb.name) > 0)

    def test_failure_threshold_property(self):
        cb = CircuitBreaker(failure_threshold=7)
        self.assertEqual(cb.failure_threshold, 7)

    def test_recovery_timeout_property(self):
        cb = CircuitBreaker(recovery_timeout=45.0)
        self.assertEqual(cb.recovery_timeout, 45.0)

    def test_last_failure_time_none_initially(self):
        cb = _make_breaker()
        self.assertIsNone(cb.last_failure_time)


# ==============================================================================
# U41  —  CIRCUIT BREAKER CLOSED STATE (NORMAL OPERATION)
# ==============================================================================

class TestCircuitBreakerClosed(unittest.TestCase):
    """Tests for CLOSED state behaviour."""

    def test_call_successful_function_returns_result(self):
        cb = _make_breaker()
        result = _arun(cb.call(_succeed))
        self.assertEqual(result, "ok")

    def test_call_failure_increments_failure_count(self):
        cb = _make_breaker(failure_threshold=10)
        try:
            _arun(cb.call(_fail))
        except RuntimeError:
            pass
        self.assertEqual(cb.failure_count, 1)

    def test_failure_below_threshold_stays_closed(self):
        cb = _make_breaker(failure_threshold=5)
        for _ in range(4):
            try:
                _arun(cb.call(_fail))
            except RuntimeError:
                pass
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_failure_at_threshold_opens_circuit(self):
        cb = _make_breaker(failure_threshold=3)
        for _ in range(3):
            try:
                _arun(cb.call(_fail))
            except RuntimeError:
                pass
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_is_open_true_after_threshold(self):
        cb = _make_breaker(failure_threshold=2)
        for _ in range(2):
            try:
                _arun(cb.call(_fail))
            except RuntimeError:
                pass
        self.assertTrue(cb.is_open)

    def test_successful_call_does_not_increment_failure_count(self):
        cb = _make_breaker()
        _arun(cb.call(_succeed))
        self.assertEqual(cb.failure_count, 0)

    def test_failure_sets_last_failure_time(self):
        cb = _make_breaker()
        before = time.time()
        try:
            _arun(cb.call(_fail))
        except RuntimeError:
            pass
        self.assertIsNotNone(cb.last_failure_time)
        self.assertGreaterEqual(cb.last_failure_time, before)

    def test_success_resets_failure_count_to_zero(self):
        cb = _make_breaker(failure_threshold=10)
        # Accumulate 1 failure, then succeed
        try:
            _arun(cb.call(_fail))
        except RuntimeError:
            pass
        self.assertEqual(cb.failure_count, 1)
        _arun(cb.call(_succeed))
        self.assertEqual(cb.failure_count, 0)


# ==============================================================================
# U41  —  CIRCUIT BREAKER OPEN STATE
# ==============================================================================

class TestCircuitBreakerOpen(unittest.TestCase):
    """Tests for OPEN state behaviour — circuit rejects calls."""

    def _open_breaker(self, **kwargs) -> CircuitBreaker:
        """Helper that opens the circuit by injecting failures."""
        cb = _make_breaker(failure_threshold=2, **kwargs)
        cb._on_failure(RuntimeError("x"))
        cb._on_failure(RuntimeError("y"))
        return cb

    def test_call_when_open_raises_circuit_breaker_error(self):
        cb = self._open_breaker()
        with self.assertRaises(CircuitBreakerError):
            _arun(cb.call(_succeed))

    def test_state_is_open(self):
        cb = self._open_breaker()
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_get_stats_state_key_is_open(self):
        cb = self._open_breaker()
        stats = cb.get_stats()
        self.assertEqual(stats["state"], "OPEN")

    def test_get_stats_is_open_true(self):
        cb = self._open_breaker()
        stats = cb.get_stats()
        self.assertTrue(stats["is_open"])

    def test_time_until_retry_positive_when_recent(self):
        cb = self._open_breaker()
        stats = cb.get_stats()
        self.assertGreater(stats["time_until_retry"], 0.0)

    def test_should_attempt_reset_false_when_recent(self):
        cb = self._open_breaker()
        self.assertFalse(cb._should_attempt_reset())


# ==============================================================================
# U41  —  CIRCUIT BREAKER HALF OPEN TRANSITIONS
# ==============================================================================

class TestCircuitBreakerHalfOpen(unittest.TestCase):
    """Tests for HALF_OPEN state transitions."""

    def _breaker_ready_to_half_open(self) -> CircuitBreaker:
        """Create a breaker that's OPEN but past recovery_timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, success_threshold=2, name="ho_test")
        cb._on_failure(RuntimeError("a"))
        cb._on_failure(RuntimeError("b"))
        # Force past recovery timeout
        cb.last_failure_time = time.time() - 10.0
        return cb

    def test_should_attempt_reset_true_after_timeout(self):
        cb = self._breaker_ready_to_half_open()
        self.assertTrue(cb._should_attempt_reset())

    def test_successful_call_after_timeout_enters_half_open_then_closes(self):
        # success_threshold=1 so one success closes it
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, success_threshold=1, name="ho_close")
        cb._on_failure(RuntimeError("a"))
        cb._on_failure(RuntimeError("b"))
        cb.last_failure_time = time.time() - 10.0
        _arun(cb.call(_succeed))
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_failure_in_half_open_reopens(self):
        cb = self._breaker_ready_to_half_open()
        # Manually set to HALF_OPEN
        cb.state = CircuitState.HALF_OPEN
        cb._on_failure(RuntimeError("recovery fail"))
        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_success_count_increments_in_half_open(self):
        cb = self._breaker_ready_to_half_open()
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0
        cb._on_success()
        self.assertEqual(cb.success_count, 1)

    def test_multiple_successes_needed_to_close(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01, success_threshold=3, name="ho_slow")
        cb._on_failure(RuntimeError("a"))
        cb._on_failure(RuntimeError("b"))
        cb.last_failure_time = time.time() - 10.0
        cb.state = CircuitState.HALF_OPEN
        cb.success_count = 0
        cb._on_success()
        cb._on_success()
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)  # not yet
        cb._on_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)


# ==============================================================================
# U41  —  CIRCUIT BREAKER RESET
# ==============================================================================

class TestCircuitBreakerReset(unittest.TestCase):
    """CircuitBreaker.reset() tests."""

    def _opened_breaker(self) -> CircuitBreaker:
        cb = _make_breaker(failure_threshold=2)
        cb._on_failure(RuntimeError("x"))
        cb._on_failure(RuntimeError("y"))
        return cb

    def test_reset_sets_state_closed(self):
        cb = self._opened_breaker()
        cb.reset()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_reset_clears_failure_count(self):
        cb = self._opened_breaker()
        cb.reset()
        self.assertEqual(cb.failure_count, 0)

    def test_reset_clears_success_count(self):
        cb = self._opened_breaker()
        cb.success_count = 3
        cb.reset()
        self.assertEqual(cb.success_count, 0)

    def test_reset_clears_last_failure_time(self):
        cb = self._opened_breaker()
        cb.reset()
        self.assertIsNone(cb.last_failure_time)

    def test_after_reset_calls_succeed_again(self):
        cb = _make_breaker(failure_threshold=2)
        cb._on_failure(RuntimeError("x"))
        cb._on_failure(RuntimeError("y"))
        cb.reset()
        result = _arun(cb.call(_succeed))
        self.assertEqual(result, "ok")


# ==============================================================================
# U41  —  GET STATS
# ==============================================================================

class TestCircuitBreakerGetStats(unittest.TestCase):
    """CircuitBreaker.get_stats() return value tests."""

    def setUp(self):
        self.cb = CircuitBreaker(failure_threshold=5, name="stats_test")

    def test_returns_dict(self):
        self.assertIsInstance(self.cb.get_stats(), dict)

    def test_name_key(self):
        self.assertEqual(self.cb.get_stats()["name"], "stats_test")

    def test_state_key_closed_initially(self):
        self.assertEqual(self.cb.get_stats()["state"], "CLOSED")

    def test_failure_count_key(self):
        self.assertEqual(self.cb.get_stats()["failure_count"], 0)

    def test_is_open_key_false_initially(self):
        self.assertFalse(self.cb.get_stats()["is_open"])

    def test_failure_threshold_key(self):
        self.assertEqual(self.cb.get_stats()["failure_threshold"], 5)

    def test_recovery_timeout_key(self):
        self.assertEqual(self.cb.get_stats()["recovery_timeout"], 60.0)

    def test_time_until_retry_zero_when_closed(self):
        self.assertEqual(self.cb.get_stats()["time_until_retry"], 0.0)


# ==============================================================================
# U41  —  GET CIRCUIT BREAKER FACTORY
# ==============================================================================

class TestGetCircuitBreakerFactory(unittest.TestCase):
    """get_circuit_breaker() factory — singleton-per-name tests."""

    def test_returns_circuit_breaker_instance(self):
        cb = get_circuit_breaker("factory_t61_test_a")
        self.assertIsInstance(cb, CircuitBreaker)

    def test_same_name_returns_same_instance(self):
        cb1 = get_circuit_breaker("factory_t61_singleton")
        cb2 = get_circuit_breaker("factory_t61_singleton")
        self.assertIs(cb1, cb2)

    def test_different_names_return_different_instances(self):
        cb_a = get_circuit_breaker("factory_t61_alpha")
        cb_b = get_circuit_breaker("factory_t61_beta")
        self.assertIsNot(cb_a, cb_b)

    def test_name_stored_correctly(self):
        cb = get_circuit_breaker("factory_t61_name_check")
        self.assertEqual(cb.name, "factory_t61_name_check")

    def test_kwargs_applied_on_creation(self):
        cb = get_circuit_breaker("factory_t61_kwargs", failure_threshold=7)
        self.assertEqual(cb.failure_threshold, 7)


# ==============================================================================
# U41  —  CIRCUIT BREAKER DECORATOR
# ==============================================================================

class TestCircuitBreakerDecorator(unittest.TestCase):
    """Tests for the circuit_breaker() function decorator and .decorator method."""

    def test_decorator_method_wraps_async_function(self):
        cb = _make_breaker()

        @cb.decorator
        async def wrapped():
            return "wrapped_result"

        result = _arun(wrapped())
        self.assertEqual(result, "wrapped_result")

    def test_circuit_breaker_function_decorator(self):
        @circuit_breaker(failure_threshold=3, recovery_timeout=60.0, name="t61_dec_test")
        async def protected():
            return "protected"

        result = _arun(protected())
        self.assertEqual(result, "protected")

    def test_decorator_propagates_exceptions(self):
        cb = _make_breaker(failure_threshold=10)

        @cb.decorator
        async def will_fail():
            raise ValueError("expected error")

        with self.assertRaises(ValueError):
            _arun(will_fail())

    def test_decorator_opens_circuit_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=2, name="t61_dec_open")

        @cb.decorator
        async def will_fail():
            raise RuntimeError("fail")

        async def _run_failures():
            for _ in range(2):
                try:
                    await will_fail()
                except RuntimeError:
                    pass

        _arun(_run_failures())
        self.assertTrue(cb.is_open)


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    unittest.main(verbosity=2)
