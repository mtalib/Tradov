#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: test_SpyderT97_U04Encryption_U40RateLimiter_U41CircuitBreaker.py
Purpose: Tests for U04 Encryption, U40 RateLimiter, U41 CircuitBreaker

Author: GitHub Copilot
Year Created: 2025
Last Updated: 2026-01-16 Time: 22:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import importlib
import os
import sys
import threading
import time
import types
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# ==============================================================================
# BOOTSTRAP — path + package stubs
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

# Stub SpyderU01_Logger (provides both SpyderLogger class and get_logger function)
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# Stub SpyderU02_ErrorHandler
_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# IMPORT MODULES UNDER TEST
# ==============================================================================

# U04 — pure stdlib, no special handling needed
for _key in list(sys.modules.keys()):
    if "SpyderU04_Encryption" in _key:
        del sys.modules[_key]
u04_mod = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU04_Encryption")

EncryptionManager = u04_mod.EncryptionManager
CredentialManager = u04_mod.CredentialManager
Encryption = u04_mod.Encryption  # alias for EncryptionManager

# U40 — pure stdlib asyncio, no special handling needed
for _key in list(sys.modules.keys()):
    if "SpyderU40_RateLimiter" in _key:
        del sys.modules[_key]
u40_mod = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU40_RateLimiter")

TokenBucket = u40_mod.TokenBucket
RateLimiter = u40_mod.RateLimiter
MultiRateLimiter = u40_mod.MultiRateLimiter

# U41 — imports get_logger at module level; standard stub handles it
# Reset get_logger mock so each test gets a fresh MagicMock logger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
for _key in list(sys.modules.keys()):
    if "SpyderU41_CircuitBreaker" in _key:
        del sys.modules[_key]
u41_mod = importlib.import_module("Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker")

CircuitState = u41_mod.CircuitState
CircuitBreakerConfig = u41_mod.CircuitBreakerConfig
CircuitBreakerError = u41_mod.CircuitBreakerError
CircuitBreaker = u41_mod.CircuitBreaker
circuit_breaker = u41_mod.circuit_breaker
get_circuit_breaker = u41_mod.get_circuit_breaker


# ==============================================================================
# ── U04 ENCRYPTION ────────────────────────────────────────────────────────────
# ==============================================================================


class TestU04EncryptionManager:
    """Tests for EncryptionManager class."""

    def test_is_initialized_defaults_true(self):
        em = EncryptionManager()
        assert em.is_initialized is True

    def test_encrypt_returns_string(self):
        em = EncryptionManager()
        result = em.encrypt("hello world")
        assert isinstance(result, str)

    def test_encrypt_is_fernet_token(self):
        import base64
        em = EncryptionManager()
        result = em.encrypt("test data")
        # Fernet tokens are ciphertext, verify round-trip
        assert em.decrypt(result) == "test data"

    def test_encrypt_empty_string(self):
        em = EncryptionManager()
        result = em.encrypt("")
        assert isinstance(result, str)

    def test_decrypt_reverses_encrypt(self):
        em = EncryptionManager()
        original = "secret message"
        encrypted = em.encrypt(original)
        decrypted = em.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_invalid_returns_input(self):
        em = EncryptionManager()
        # Invalid base64 — decrypt should return the input on error
        result = em.decrypt("not-valid-base64!!!")
        assert result == "not-valid-base64!!!"

    def test_generate_key_returns_bytes(self):
        em = EncryptionManager()
        key = em.generate_key()
        assert isinstance(key, bytes)

    def test_generate_key_length(self):
        em = EncryptionManager()
        key = em.generate_key()
        assert len(key) == 44  # Fernet key = url-safe base64 of 32 bytes

    def test_generate_key_unique_each_call(self):
        em = EncryptionManager()
        k1 = em.generate_key()
        k2 = em.generate_key()
        assert k1 != k2

    def test_encrypt_roundtrip_various_data(self):
        em = EncryptionManager()
        for data in ["a", "A" * 100, "hello world"]:
            assert em.decrypt(em.encrypt(data)) == data


class TestU04CredentialManager:
    """Tests for CredentialManager class."""

    def test_init_empty_credentials(self):
        cm = CredentialManager()
        assert cm.list_credentials() == []

    def test_init_has_encryption_manager(self):
        cm = CredentialManager()
        assert isinstance(cm.encryption_manager, EncryptionManager)

    def test_initialize_returns_true(self):
        cm = CredentialManager()
        assert cm.initialize() is True

    def test_set_credential_returns_bool(self):
        cm = CredentialManager()
        result = cm.set_credential("api_key", "my_secret")
        assert isinstance(result, bool)

    def test_set_credential_stores_value(self):
        cm = CredentialManager()
        cm.set_credential("key1", "value1")
        assert cm.get_credential("key1") is not None

    def test_get_credential_returns_correct_value(self):
        cm = CredentialManager()
        cm.set_credential("token", "abc123")
        result = cm.get_credential("token")
        assert result == "abc123"

    def test_get_credential_missing_returns_default(self):
        cm = CredentialManager()
        result = cm.get_credential("nonexistent", default="fallback")
        assert result == "fallback"

    def test_get_credential_missing_default_none(self):
        cm = CredentialManager()
        result = cm.get_credential("missing")
        assert result is None

    def test_list_credentials_returns_keys(self):
        cm = CredentialManager()
        cm.set_credential("a", "1")
        cm.set_credential("b", "2")
        keys = cm.list_credentials()
        assert "a" in keys
        assert "b" in keys

    def test_delete_credential_returns_bool(self):
        cm = CredentialManager()
        cm.set_credential("del_me", "value")
        result = cm.delete_credential("del_me")
        assert isinstance(result, bool)

    def test_delete_credential_removes_it(self):
        cm = CredentialManager()
        cm.set_credential("temp", "val")
        cm.delete_credential("temp")
        assert cm.get_credential("temp") is None

    def test_delete_nonexistent_credential(self):
        cm = CredentialManager()
        result = cm.delete_credential("does_not_exist")
        # Should not raise; returns bool
        assert isinstance(result, bool)

    def test_multiple_credentials_independent(self):
        cm = CredentialManager()
        cm.set_credential("x", "1")
        cm.set_credential("y", "2")
        assert cm.get_credential("x") == "1"
        assert cm.get_credential("y") == "2"


class TestU04ModuleFunctions:
    """Tests for module-level functions in U04."""

    def test_encrypt_data_exists(self):
        assert callable(u04_mod.encrypt_data)

    def test_decrypt_data_exists(self):
        assert callable(u04_mod.decrypt_data)

    def test_encrypt_alias_exists(self):
        assert callable(u04_mod.encrypt)

    def test_decrypt_alias_exists(self):
        assert callable(u04_mod.decrypt)

    def test_encrypt_data_returns_string(self):
        result = u04_mod.encrypt_data("test")
        assert isinstance(result, str)

    def test_decrypt_data_reverses(self):
        enc = u04_mod.encrypt_data("hello")
        dec = u04_mod.decrypt_data(enc)
        assert dec == "hello"

    def test_encrypt_alias_matches_encrypt_data(self):
        data = "same result"
        # Fernet uses random IV, so outputs differ; verify both decrypt correctly
        assert u04_mod.decrypt(u04_mod.encrypt(data)) == data
        assert u04_mod.decrypt_data(u04_mod.encrypt_data(data)) == data

    def test_generate_secure_password_default_length(self):
        pw = u04_mod.generate_secure_password()
        assert isinstance(pw, str)
        assert len(pw) > 0

    def test_generate_secure_password_custom_length(self):
        pw = u04_mod.generate_secure_password(length=16)
        assert isinstance(pw, str)

    def test_generate_secure_password_unique(self):
        p1 = u04_mod.generate_secure_password()
        p2 = u04_mod.generate_secure_password()
        assert p1 != p2

    def test_hash_password_returns_argon2_string(self):
        result = u04_mod.hash_password("mypassword")
        assert isinstance(result, str)
        assert result.startswith("$argon2")  # Argon2id hash

    def test_hash_password_verifiable(self):
        h = u04_mod.hash_password("same")
        assert u04_mod.verify_password("same", h)

    def test_hash_password_different_inputs(self):
        r1 = u04_mod.hash_password("a")
        r2 = u04_mod.hash_password("b")
        assert r1 != r2

    def test_encryption_alias_is_encryption_manager(self):
        assert Encryption is EncryptionManager


# ==============================================================================
# ── U40 RATE LIMITER ──────────────────────────────────────────────────────────
# ==============================================================================


class TestU40TokenBucket:
    """Tests for TokenBucket dataclass."""

    def _make_bucket(self, capacity=10.0, fill_rate=10.0, tokens=None):
        if tokens is None:
            tokens = capacity
        return TokenBucket(capacity=capacity, fill_rate=fill_rate, tokens=tokens)

    def test_create_with_fields(self):
        tb = self._make_bucket(capacity=5.0, fill_rate=5.0)
        assert tb.capacity == 5.0
        assert tb.fill_rate == 5.0

    def test_tokens_initialized_to_capacity(self):
        tb = self._make_bucket(capacity=10.0)
        assert tb.tokens == 10.0

    def test_consume_returns_true_when_tokens_available(self):
        tb = self._make_bucket(capacity=10.0)
        assert tb.consume(1.0) is True

    def test_consume_decreases_tokens(self):
        tb = self._make_bucket(capacity=10.0)
        tb.consume(3.0)
        # Tokens should be < 10 (consumed 3, some may be added back by refill)
        assert tb.tokens < 10.0

    def test_consume_returns_false_when_empty(self):
        tb = self._make_bucket(capacity=2.0, fill_rate=0.01, tokens=0.0)
        result = tb.consume(5.0)
        assert result is False

    def test_consume_default_one_token(self):
        tb = self._make_bucket(capacity=5.0)
        tb.consume()  # default = 1.0
        assert tb.tokens < 5.0

    def test_wait_time_zero_when_tokens_available(self):
        tb = self._make_bucket(capacity=10.0)
        wt = tb.wait_time(1.0)
        assert wt == 0.0

    def test_wait_time_positive_when_empty(self):
        tb = self._make_bucket(capacity=1.0, fill_rate=1.0, tokens=0.0)
        wt = tb.wait_time(1.0)
        assert wt > 0.0

    def test_refill_adds_tokens(self):
        tb = self._make_bucket(capacity=10.0, fill_rate=100.0, tokens=0.0)
        # Set last_update to past
        tb.last_update = time.time() - 1.0
        tb._refill()
        assert tb.tokens > 0.0

    def test_refill_does_not_exceed_capacity(self):
        tb = self._make_bucket(capacity=5.0, fill_rate=100.0, tokens=5.0)
        tb.last_update = time.time() - 10.0
        tb._refill()
        assert tb.tokens <= 5.0

    def test_has_lock_attribute(self):
        tb = self._make_bucket()
        assert isinstance(tb.lock, threading.Lock)


class TestU40RateLimiter:
    """Tests for RateLimiter class."""

    def test_init_basic(self):
        rl = RateLimiter(requests_per_second=10.0)
        assert isinstance(rl.bucket, TokenBucket)

    def test_init_default_burst_size_equals_rps(self):
        rl = RateLimiter(requests_per_second=5.0)
        assert rl.bucket.capacity == 5.0

    def test_init_custom_burst_size(self):
        rl = RateLimiter(requests_per_second=5.0, burst_size=20)
        assert rl.bucket.capacity == 20

    def test_from_per_minute_classmethod(self):
        rl = RateLimiter.from_per_minute(requests_per_minute=60, burst_size=10)
        assert isinstance(rl, RateLimiter)
        # 60 rpm = 1 rps
        assert abs(rl.bucket.fill_rate - 1.0) < 0.01

    def test_from_per_minute_without_burst(self):
        rl = RateLimiter.from_per_minute(requests_per_minute=120)
        assert isinstance(rl, RateLimiter)

    @pytest.mark.asyncio
    async def test_acquire_returns_on_full_bucket(self):
        rl = RateLimiter(requests_per_second=1000.0)
        await rl.acquire()  # Should complete without significant delay

    @pytest.mark.asyncio
    async def test_acquire_context_manager(self):
        rl = RateLimiter(requests_per_second=1000.0)
        async with rl:
            pass  # Should not raise

    @pytest.mark.asyncio
    async def test_acquire_multiple_times(self):
        rl = RateLimiter(requests_per_second=1000.0, burst_size=100)
        for _ in range(5):
            await rl.acquire()


class TestU40MultiRateLimiter:
    """Tests for MultiRateLimiter class."""

    def test_init_creates_empty_dicts(self):
        ml = MultiRateLimiter()
        assert isinstance(ml._limiters, dict)
        assert isinstance(ml._defaults, dict)

    def test_register_default(self):
        ml = MultiRateLimiter()
        ml.register_default("svc", requests_per_second=10, burst_size=20)
        assert "svc" in ml._defaults

    def test_add_limit(self):
        ml = MultiRateLimiter()
        ml.add_limit("svc2", requests_per_second=5, burst_size=10)
        assert "svc2" in ml._limiters

    @pytest.mark.asyncio
    async def test_acquire_from_registered_default(self):
        ml = MultiRateLimiter()
        ml.register_default("fast", requests_per_second=1000, burst_size=100)
        await ml.acquire("fast")  # Should succeed

    @pytest.mark.asyncio
    async def test_acquire_from_added_limit(self):
        ml = MultiRateLimiter()
        ml.add_limit("explicit", requests_per_second=1000, burst_size=100)
        await ml.acquire("explicit")

    @pytest.mark.asyncio
    async def test_acquire_unknown_raises_value_error(self):
        ml = MultiRateLimiter()
        with pytest.raises((ValueError, KeyError)):
            await ml.acquire("completely_unknown_service")

    def test_get_stats_returns_dict(self):
        ml = MultiRateLimiter()
        stats = ml.get_stats()
        assert isinstance(stats, dict)

    def test_get_stats_includes_registered_limiters(self):
        ml = MultiRateLimiter()
        ml.add_limit("tracked", requests_per_second=10, burst_size=10)
        stats = ml.get_stats()
        assert "tracked" in stats

    def test_global_limiters_exist(self):
        assert hasattr(u40_mod, "_global_limiters")
        assert isinstance(u40_mod._global_limiters, MultiRateLimiter)

    @pytest.mark.asyncio
    async def test_acquire_tradier_convenience(self):
        # Must exist
        assert callable(u40_mod.acquire_tradier)
        # Should not raise (high rate in global defaults)


class TestU40RateLimitDecorator:
    """Tests for rate_limit decorator."""

    def test_rate_limit_exists(self):
        assert callable(u40_mod.rate_limit)

    @pytest.mark.asyncio
    async def test_rate_limit_with_rps(self):
        @u40_mod.rate_limit(requests_per_second=1000.0)
        async def fast_func():
            return 42

        result = await fast_func()
        assert result == 42

    @pytest.mark.asyncio
    async def test_rate_limit_preserves_return_value(self):
        @u40_mod.rate_limit(requests_per_second=500.0)
        async def return_string():
            return "done"

        assert await return_string() == "done"

    @pytest.mark.asyncio
    async def test_rate_limit_with_service(self):
        # Using 'service' param grabs from global limiters
        @u40_mod.rate_limit(service="tradier")
        async def tradier_func():
            return True

        assert await tradier_func() is True

    @pytest.mark.asyncio
    async def test_rate_limit_missing_params_raises(self):
        with pytest.raises((ValueError, TypeError)):
            @u40_mod.rate_limit()
            async def bad_func():
                pass
            await bad_func()


# ==============================================================================
# ── U41 CIRCUIT BREAKER ───────────────────────────────────────────────────────
# ==============================================================================


class TestU41CircuitState:
    """Tests for CircuitState enum."""

    def test_closed_exists(self):
        assert CircuitState.CLOSED is not None

    def test_open_exists(self):
        assert CircuitState.OPEN is not None

    def test_half_open_exists(self):
        assert CircuitState.HALF_OPEN is not None

    def test_all_three_members(self):
        states = list(CircuitState)
        assert len(states) == 3

    def test_state_names(self):
        names = {s.name for s in CircuitState}
        assert names == {"CLOSED", "OPEN", "HALF_OPEN"}


class TestU41CircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_defaults(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout == 60.0
        assert cfg.success_threshold == 1
        assert cfg.timeout is None

    def test_custom_values(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2,
            timeout=10.0
        )
        assert cfg.failure_threshold == 3
        assert cfg.recovery_timeout == 30.0
        assert cfg.success_threshold == 2
        assert cfg.timeout == 10.0


class TestU41CircuitBreakerError:
    """Tests for CircuitBreakerError exception."""

    def test_is_exception(self):
        assert issubclass(CircuitBreakerError, Exception)

    def test_can_raise_and_catch(self):
        with pytest.raises(CircuitBreakerError):
            raise CircuitBreakerError("circuit open")

    def test_message_preserved(self):
        try:
            raise CircuitBreakerError("test msg")
        except CircuitBreakerError as e:
            assert "test msg" in str(e)


class TestU41CircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_default_state_closed(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_default_failure_count_zero(self):
        cb = CircuitBreaker()
        assert cb.failure_count == 0

    def test_default_success_count_zero(self):
        cb = CircuitBreaker()
        assert cb.success_count == 0

    def test_default_name(self):
        cb = CircuitBreaker()
        assert cb.name == "CircuitBreaker"

    def test_custom_name(self):
        cb = CircuitBreaker(name="my_breaker")
        assert cb.name == "my_breaker"

    def test_custom_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.failure_threshold == 3

    def test_custom_recovery_timeout(self):
        cb = CircuitBreaker(recovery_timeout=30.0)
        assert cb.recovery_timeout == 30.0

    def test_has_lock(self):
        cb = CircuitBreaker()
        assert isinstance(cb.lock, threading.Lock)

    def test_last_failure_time_none(self):
        cb = CircuitBreaker()
        assert cb.last_failure_time is None

    def test_config_is_circuit_breaker_config(self):
        cb = CircuitBreaker()
        assert isinstance(cb.config, CircuitBreakerConfig)


class TestU41CircuitBreakerProperties:
    """Tests for CircuitBreaker properties."""

    def test_is_closed_true_initially(self):
        cb = CircuitBreaker()
        assert cb.is_closed is True

    def test_is_open_false_initially(self):
        cb = CircuitBreaker()
        assert cb.is_open is False

    def test_is_open_true_when_open(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        assert cb.is_open is True

    def test_is_closed_false_when_open(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        assert cb.is_closed is False

    def test_failure_threshold_property(self):
        cb = CircuitBreaker(failure_threshold=7)
        assert cb.failure_threshold == 7

    def test_recovery_timeout_property(self):
        cb = CircuitBreaker(recovery_timeout=45.0)
        assert cb.recovery_timeout == 45.0


class TestU41CircuitBreakerCall:
    """Tests for CircuitBreaker.call() method."""

    @pytest.mark.asyncio
    async def test_call_success(self):
        cb = CircuitBreaker()

        async def success_func():
            return "ok"

        result = await cb.call(success_func)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_call_succeeds_resets_failure_count(self):
        cb = CircuitBreaker()
        cb.failure_count = 3

        async def ok():
            return True

        await cb.call(ok)
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_failure_increments_count(self):
        cb = CircuitBreaker(failure_threshold=10)

        async def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await cb.call(fail)

        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_call_opens_circuit_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)

        async def fail():
            raise RuntimeError("error")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_call_raises_circuit_breaker_error_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999)

        async def fail():
            raise Exception("failure")

        with pytest.raises(Exception):
            await cb.call(fail)  # Opens the circuit

        async def good():
            return True

        with pytest.raises(CircuitBreakerError):
            await cb.call(good)

    @pytest.mark.asyncio
    async def test_call_half_open_on_timeout_elapsed(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)

        async def fail():
            raise Exception("fail")

        with pytest.raises(Exception):
            await cb.call(fail)

        await asyncio.sleep(0.05)  # Let recovery timeout elapse

        async def good():
            return "recovered"

        result = await cb.call(good)
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_call_with_timeout_config(self):
        cb = CircuitBreaker(timeout=5.0)

        async def quick():
            return "fast"

        result = await cb.call(quick)
        assert result == "fast"

    @pytest.mark.asyncio
    async def test_call_passes_args_and_kwargs(self):
        cb = CircuitBreaker()

        async def add(a, b=0):
            return a + b

        result = await cb.call(add, 3, b=4)
        assert result == 7


class TestU41CircuitBreakerContextManager:
    """Tests for CircuitBreaker async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        cb = CircuitBreaker()
        async with cb:
            pass  # No raise → _on_success called

        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_context_manager_calls_on_failure(self):
        cb = CircuitBreaker(failure_threshold=10)
        with pytest.raises(ValueError):
            async with cb:
                raise ValueError("err")

        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_context_manager_open_raises_circuit_error(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=9999)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time()

        with pytest.raises(CircuitBreakerError):
            async with cb:
                pass

    @pytest.mark.asyncio
    async def test_context_manager_returns_self(self):
        cb = CircuitBreaker()
        async with cb as breaker:
            assert breaker is cb


class TestU41CircuitBreakerDecoratorMethod:
    """Tests for CircuitBreaker.decorator() instance method."""

    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self):
        cb = CircuitBreaker()

        @cb.decorator
        async def my_func():
            return "wrapped"

        result = await my_func()
        assert result == "wrapped"

    @pytest.mark.asyncio
    async def test_decorator_propagates_exceptions(self):
        cb = CircuitBreaker(failure_threshold=10)

        @cb.decorator
        async def failing():
            raise TypeError("oops")

        with pytest.raises(TypeError):
            await failing()

    @pytest.mark.asyncio
    async def test_decorator_opens_circuit_on_threshold(self):
        cb = CircuitBreaker(failure_threshold=2)

        @cb.decorator
        async def fail():
            raise RuntimeError("fail")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await fail()

        assert cb.is_open

    @pytest.mark.asyncio
    async def test_decorator_preserves_func_name(self):
        cb = CircuitBreaker()

        @cb.decorator
        async def named_func():
            return None

        assert named_func.__name__ == "named_func"


class TestU41CircuitBreakerReset:
    """Tests for CircuitBreaker.reset() method."""

    def test_reset_closes_circuit(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker()
        cb.failure_count = 10
        cb.reset()
        assert cb.failure_count == 0

    def test_reset_clears_success_count(self):
        cb = CircuitBreaker()
        cb.success_count = 5
        cb.reset()
        assert cb.success_count == 0

    def test_reset_clears_last_failure_time(self):
        cb = CircuitBreaker()
        cb.last_failure_time = time.time()
        cb.reset()
        assert cb.last_failure_time is None


class TestU41CircuitBreakerGetStats:
    """Tests for CircuitBreaker.get_stats() method."""

    def test_returns_dict(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert isinstance(stats, dict)

    def test_contains_state(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert "state" in stats
        assert stats["state"] == "CLOSED"

    def test_contains_name(self):
        cb = CircuitBreaker(name="test_cb")
        stats = cb.get_stats()
        assert stats["name"] == "test_cb"

    def test_contains_failure_count(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert "failure_count" in stats
        assert stats["failure_count"] == 0

    def test_contains_is_open(self):
        cb = CircuitBreaker()
        stats = cb.get_stats()
        assert "is_open" in stats
        assert stats["is_open"] is False

    def test_open_state_stats(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.time()
        stats = cb.get_stats()
        assert stats["state"] == "OPEN"
        assert stats["is_open"] is True

    def test_contains_thresholds(self):
        cb = CircuitBreaker(failure_threshold=7, recovery_timeout=45.0)
        stats = cb.get_stats()
        assert stats["failure_threshold"] == 7
        assert stats["recovery_timeout"] == 45.0


class TestU41CircuitBreakerDecoratorFunc:
    """Tests for module-level circuit_breaker() decorator factory."""

    @pytest.mark.asyncio
    async def test_decorator_wraps_async_function(self):
        @circuit_breaker(failure_threshold=5, recovery_timeout=60)
        async def protected():
            return "protected"

        result = await protected()
        assert result == "protected"

    @pytest.mark.asyncio
    async def test_decorator_default_params(self):
        @circuit_breaker()
        async def default_protected():
            return True

        assert await default_protected() is True

    @pytest.mark.asyncio
    async def test_decorator_opens_after_failures(self):
        @circuit_breaker(failure_threshold=2, recovery_timeout=9999)
        async def flaky():
            raise ValueError("fail")

        for _ in range(2):
            with pytest.raises(ValueError):
                await flaky()

        with pytest.raises(CircuitBreakerError):
            await flaky()

    def test_decorator_with_name(self):
        @circuit_breaker(name="named_cb")
        async def func():
            return None

        # Should not raise during decoration

    @pytest.mark.asyncio
    async def test_decorator_with_timeout(self):
        @circuit_breaker(timeout=5.0)
        async def fast():
            return "fast"

        result = await fast()
        assert result == "fast"


class TestU41GetCircuitBreaker:
    """Tests for get_circuit_breaker() factory function."""

    def test_returns_circuit_breaker_instance(self):
        cb = get_circuit_breaker("test_unique_name_t97")
        assert isinstance(cb, CircuitBreaker)

    def test_same_name_returns_same_instance(self):
        cb1 = get_circuit_breaker("shared_t97")
        cb2 = get_circuit_breaker("shared_t97")
        assert cb1 is cb2

    def test_different_names_return_different_instances(self):
        cb1 = get_circuit_breaker("t97_alpha")
        cb2 = get_circuit_breaker("t97_beta")
        assert cb1 is not cb2

    def test_name_is_set(self):
        cb = get_circuit_breaker("t97_named")
        assert cb.name == "t97_named"

    def test_kwargs_applied_on_creation(self):
        # Use unique name to avoid getting existing instance
        cb = get_circuit_breaker("t97_custom_thresh", failure_threshold=7)
        assert cb.failure_threshold == 7

    def test_predefined_tradier_breaker_exists(self):
        assert hasattr(u41_mod, "tradier_breaker")
        assert isinstance(u41_mod.tradier_breaker, CircuitBreaker)

    def test_tradier_breaker_config(self):
        tb = u41_mod.tradier_breaker
        assert tb.failure_threshold == 5
        assert tb.recovery_timeout == 60.0
