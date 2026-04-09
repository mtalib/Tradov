#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT92_EncryptionOptionStrategiesTests.py
Purpose: Tests for U04 Encryption and U14 OptionStrategies

Year Created: 2025
Last Updated: 2026-01-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import base64
import hashlib
import os
import sys
import types
from datetime import datetime, timedelta

from unittest.mock import MagicMock

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
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

# Stub SpyderLogger
_logger_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU01_Logger")


class _FakeSpyderLogger:
    @staticmethod
    def get_logger(name: str) -> MagicMock:
        return MagicMock()


_logger_mod.SpyderLogger = _FakeSpyderLogger
_logger_mod.get_logger = MagicMock(return_value=MagicMock())
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _logger_mod

# Stub SpyderErrorHandler
_err_mod = types.ModuleType("Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler")
_err_mod.SpyderErrorHandler = MagicMock
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _err_mod

# ==============================================================================
# IMPORT MODULES UNDER TEST
# ==============================================================================
import Spyder.SpyderU_Utilities.SpyderU04_Encryption as _u04
import Spyder.SpyderU_Utilities.SpyderU14_OptionStrategies as _u14

EncryptionManager = _u04.EncryptionManager
CredentialManager = _u04.CredentialManager

OptionStrategies = _u14.OptionStrategies
OptionType = _u14.OptionType
PositionType = _u14.PositionType
StrategyType = _u14.StrategyType
OptionLeg = _u14.OptionLeg
OptionStrategy = _u14.OptionStrategy
PayoffResult = _u14.PayoffResult


# ==============================================================================
# HELPERS
# ==============================================================================

def _expiry(days: int = 30) -> datetime:
    return datetime.now() + timedelta(days=days)


def _simple_bull_call(strats: OptionStrategies = None) -> OptionStrategy:
    """Return a simple bull call spread for reuse in tests."""
    s = strats or OptionStrategies()
    return s.create_bull_call_spread(
        long_strike=450.0,
        short_strike=460.0,
        expiry=_expiry(30),
        long_premium=8.0,
        short_premium=3.0,
        underlying_price=455.0,
    )


def _simple_iron_condor(strats: OptionStrategies = None) -> OptionStrategy:
    s = strats or OptionStrategies()
    return s.create_iron_condor(
        put_long_strike=440.0,
        put_short_strike=450.0,
        call_short_strike=470.0,
        call_long_strike=480.0,
        expiry=_expiry(30),
        premiums=[2.0, 6.0, 6.0, 2.0],
        underlying_price=460.0,
    )


# ==============================================================================
# ──────────────────────────────────────────────────────────────────────────────
# U04 Encryption
# ──────────────────────────────────────────────────────────────────────────────
# ==============================================================================


class TestEncryptionManagerInit:
    def test_init_not_initialized(self):
        em = EncryptionManager()
        assert em.is_initialized is True

    def test_encryption_alias(self):
        assert _u04.Encryption is EncryptionManager


class TestEncryptionManagerEncryptDecrypt:
    def setup_method(self):
        self.em = EncryptionManager()

    def test_encrypt_returns_string(self):
        result = self.em.encrypt("hello")
        assert isinstance(result, str)

    def test_encrypt_returns_fernet_token(self):
        result = self.em.encrypt("hello")
        # Fernet tokens are ciphertext, not raw base64 of plaintext
        assert self.em.decrypt(result) == "hello"

    def test_decrypt_round_trip(self):
        original = "secret data"
        encrypted = self.em.encrypt(original)
        decrypted = self.em.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_empty_string(self):
        result = self.em.encrypt("")
        assert isinstance(result, str)
        assert self.em.decrypt(result) == ""

    def test_encrypt_unicode(self):
        data = "hello 你好 мир"
        enc = self.em.encrypt(data)
        assert self.em.decrypt(enc) == data

    def test_decrypt_invalid_returns_input(self):
        # Invalid base64 should return the input unchanged
        result = self.em.decrypt("!!!invalid!!!")
        assert result == "!!!invalid!!!"

    def test_encrypt_produces_different_output_than_input(self):
        data = "plaintext"
        encrypted = self.em.encrypt(data)
        assert encrypted != data


class TestEncryptionManagerGenerateKey:
    def test_key_is_bytes(self):
        em = EncryptionManager()
        key = em.generate_key()
        assert isinstance(key, bytes)

    def test_key_length_44(self):
        em = EncryptionManager()
        key = em.generate_key()
        assert len(key) == 44  # Fernet key = url-safe base64 of 32 bytes

    def test_key_uniqueness(self):
        em = EncryptionManager()
        k1 = em.generate_key()
        k2 = em.generate_key()
        assert k1 != k2  # Highly unlikely to be equal (random)


class TestCredentialManager:
    def setup_method(self):
        self.cm = CredentialManager()

    def test_init_empty_credentials(self):
        assert self.cm.credentials == {}

    def test_init_has_encryption_manager(self):
        assert isinstance(self.cm.encryption_manager, EncryptionManager)

    def test_initialize_returns_true(self):
        assert self.cm.initialize() is True

    def test_set_credential_returns_true(self):
        assert self.cm.set_credential("api_key", "abc123") is True

    def test_set_credential_stores_value(self):
        self.cm.set_credential("key1", "value1")
        # With Fernet, stored value is encrypted (not plaintext)
        assert "key1" in self.cm.credentials
        assert self.cm.get_credential("key1") == "value1"

    def test_get_credential_existing(self):
        self.cm.set_credential("test_key", "test_value")
        assert self.cm.get_credential("test_key") == "test_value"

    def test_get_credential_nonexistent_returns_none(self):
        assert self.cm.get_credential("missing") is None

    def test_get_credential_default_value(self):
        assert self.cm.get_credential("missing", default="fallback") == "fallback"

    def test_list_credentials_empty(self):
        assert self.cm.list_credentials() == []

    def test_list_credentials_with_entries(self):
        self.cm.set_credential("k1", "v1")
        self.cm.set_credential("k2", "v2")
        keys = self.cm.list_credentials()
        assert "k1" in keys
        assert "k2" in keys

    def test_delete_credential_existing(self):
        self.cm.set_credential("to_delete", "value")
        result = self.cm.delete_credential("to_delete")
        assert result is True
        assert "to_delete" not in self.cm.credentials

    def test_delete_credential_nonexistent_returns_false(self):
        assert self.cm.delete_credential("nonexistent") is False

    def test_overwrite_credential(self):
        self.cm.set_credential("key", "old")
        self.cm.set_credential("key", "new")
        assert self.cm.get_credential("key") == "new"


class TestU04ModuleFunctions:
    def test_encrypt_data(self):
        result = _u04.encrypt_data("hello world")
        assert _u04.decrypt_data(result) == "hello world"

    def test_decrypt_data(self):
        enc = _u04.encrypt_data("test")
        assert _u04.decrypt_data(enc) == "test"

    def test_encrypt_decrypt_roundtrip(self):
        data = "API_KEY=12345"
        assert _u04.decrypt_data(_u04.encrypt_data(data)) == data

    def test_encrypt_alias(self):
        # Fernet uses random IV, so outputs differ; verify both decrypt correctly
        assert _u04.decrypt(_u04.encrypt("hi")) == "hi"

    def test_decrypt_alias(self):
        enc = _u04.encrypt("hi")
        assert _u04.decrypt(enc) == "hi"

    def test_decrypt_invalid_returns_input(self):
        result = _u04.decrypt_data("not-valid-base64!!!")
        assert result == "not-valid-base64!!!"

    def test_generate_secure_password_is_string(self):
        result = _u04.generate_secure_password()
        assert isinstance(result, str)

    def test_generate_secure_password_non_empty(self):
        result = _u04.generate_secure_password()
        assert len(result) > 0

    def test_generate_secure_password_unique(self):
        p1 = _u04.generate_secure_password()
        p2 = _u04.generate_secure_password()
        assert p1 != p2

    def test_hash_password_is_string(self):
        result = _u04.hash_password("mypassword")
        assert isinstance(result, str)

    def test_hash_password_sha256_hex(self):
        pw = "testpwd"
        h = _u04.hash_password(pw)
        assert h.startswith("$argon2")  # Argon2id hash

    def test_hash_password_verifiable(self):
        h = _u04.hash_password("abc")
        assert _u04.verify_password("abc", h)

    def test_hash_password_length(self):
        result = _u04.hash_password("anything")
        assert len(result) > 64  # Argon2 hash is longer than SHA-256

    def test_all_exports(self):
        for name in _u04.__all__:
            assert hasattr(_u04, name)


# ==============================================================================
# ──────────────────────────────────────────────────────────────────────────────
# U14 OptionStrategies
# ──────────────────────────────────────────────────────────────────────────────
# ==============================================================================


class TestU14Constants:
    def test_risk_free_rate(self):
        assert pytest.approx(0.05) == _u14.RISK_FREE_RATE

    def test_contract_multiplier(self):
        assert _u14.CONTRACT_MULTIPLIER == 100

    def test_days_per_year(self):
        assert pytest.approx(365.25) == _u14.DAYS_PER_YEAR


class TestOptionType:
    def test_call(self):
        assert OptionType.CALL.value == "CALL"

    def test_put(self):
        assert OptionType.PUT.value == "PUT"


class TestPositionType:
    def test_long(self):
        assert PositionType.LONG.value == "LONG"

    def test_short(self):
        assert PositionType.SHORT.value == "SHORT"


class TestStrategyType:
    def test_iron_condor(self):
        assert StrategyType.IRON_CONDOR.value == "iron_condor"

    def test_bull_call_spread(self):
        assert StrategyType.BULL_CALL_SPREAD.value == "bull_call_spread"

    def test_straddle(self):
        assert StrategyType.STRADDLE.value == "straddle"

    def test_count(self):
        assert len(StrategyType) == 11


class TestOptionLeg:
    def _make_call_leg(self, pos=PositionType.LONG, premium=5.0, qty=1) -> OptionLeg:
        return OptionLeg(
            option_type=OptionType.CALL,
            position_type=pos,
            strike=460.0,
            expiry=_expiry(30),
            premium=premium,
            quantity=qty,
        )

    def test_is_call(self):
        leg = self._make_call_leg()
        assert leg.is_call is True
        assert leg.is_put is False

    def test_is_put(self):
        leg = OptionLeg(
            option_type=OptionType.PUT,
            position_type=PositionType.LONG,
            strike=460.0,
            expiry=_expiry(),
            premium=5.0,
        )
        assert leg.is_put is True
        assert leg.is_call is False

    def test_is_long(self):
        leg = self._make_call_leg(pos=PositionType.LONG)
        assert leg.is_long is True
        assert leg.is_short is False

    def test_is_short(self):
        leg = self._make_call_leg(pos=PositionType.SHORT)
        assert leg.is_short is True
        assert leg.is_long is False

    def test_net_premium_long_is_negative(self):
        # Long legs pay premium → net_premium is negative
        leg = self._make_call_leg(pos=PositionType.LONG, premium=8.0, qty=1)
        assert leg.net_premium == pytest.approx(-8.0)

    def test_net_premium_short_is_positive(self):
        # Short legs receive premium → net_premium is positive
        leg = self._make_call_leg(pos=PositionType.SHORT, premium=3.0, qty=1)
        assert leg.net_premium == pytest.approx(3.0)

    def test_net_premium_with_quantity(self):
        leg = self._make_call_leg(pos=PositionType.LONG, premium=5.0, qty=2)
        assert leg.net_premium == pytest.approx(-10.0)

    def test_default_quantity_one(self):
        leg = self._make_call_leg()
        assert leg.quantity == 1


class TestOptionStrategyDataclass:
    def test_net_premium_sum_of_legs(self):
        legs = [
            OptionLeg(OptionType.CALL, PositionType.LONG, 450, _expiry(), 8.0, 1),
            OptionLeg(OptionType.CALL, PositionType.SHORT, 460, _expiry(), 3.0, 1),
        ]
        strat = OptionStrategy("Test", StrategyType.BULL_CALL_SPREAD, legs, 455.0)
        # net: -8 + 3 = -5
        assert strat.net_premium == pytest.approx(-5.0)

    def test_is_credit_strategy(self):
        legs = [
            OptionLeg(OptionType.CALL, PositionType.SHORT, 460, _expiry(), 8.0, 1),
        ]
        strat = OptionStrategy("Test", StrategyType.NAKED_CALL, legs, 455.0)
        assert strat.is_credit_strategy is True

    def test_is_debit_strategy(self):
        legs = [
            OptionLeg(OptionType.CALL, PositionType.LONG, 460, _expiry(), 8.0, 1),
        ]
        strat = OptionStrategy("Test", StrategyType.NAKED_CALL, legs, 455.0)
        assert strat.is_debit_strategy is True


class TestCalculateOptionPayoff:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_long_call_itm(self):
        # spot=470, strike=460, premium=5, LONG CALL → (10-5)*100 = 500
        result = self.s.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 470.0)
        assert float(result) == pytest.approx(500.0)

    def test_long_call_otm(self):
        # spot=450, strike=460, premium=5. OTM call → intrinsic=0 → (0-5)*100 = -500
        result = self.s.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 450.0)
        assert float(result) == pytest.approx(-500.0)

    def test_long_call_at_money(self):
        # spot=460, strike=460, premium=5 → (0-5)*100 = -500
        result = self.s.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 460.0)
        assert float(result) == pytest.approx(-500.0)

    def test_short_call_itm(self):
        # spot=470, strike=460, premium=5, SHORT CALL → (5-10)*100 = -500
        result = self.s.calculate_option_payoff("CALL", "SHORT", 460.0, 5.0, 470.0)
        assert float(result) == pytest.approx(-500.0)

    def test_short_call_otm(self):
        # spot=450, strike=460, SHORT CALL → premium profit = (5-0)*100 = 500
        result = self.s.calculate_option_payoff("CALL", "SHORT", 460.0, 5.0, 450.0)
        assert float(result) == pytest.approx(500.0)

    def test_long_put_itm(self):
        # spot=450, strike=460, premium=5, LONG PUT → (10-5)*100 = 500
        result = self.s.calculate_option_payoff("PUT", "LONG", 460.0, 5.0, 450.0)
        assert float(result) == pytest.approx(500.0)

    def test_long_put_otm(self):
        # spot=470, strike=460, LONG PUT → (0-5)*100 = -500
        result = self.s.calculate_option_payoff("PUT", "LONG", 460.0, 5.0, 470.0)
        assert float(result) == pytest.approx(-500.0)

    def test_short_put_itm(self):
        # spot=450, strike=460, SHORT PUT → (5-10)*100 = -500
        result = self.s.calculate_option_payoff("PUT", "SHORT", 460.0, 5.0, 450.0)
        assert float(result) == pytest.approx(-500.0)

    def test_short_put_otm(self):
        # spot=470, strike=460, SHORT PUT → (5-0)*100 = 500
        result = self.s.calculate_option_payoff("PUT", "SHORT", 460.0, 5.0, 470.0)
        assert float(result) == pytest.approx(500.0)

    def test_vectorized_spot_prices(self):
        spots = np.array([450.0, 460.0, 470.0])
        result = self.s.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, spots)
        expected = np.array([-500.0, -500.0, 500.0])
        np.testing.assert_allclose(result, expected)

    def test_quantity_scaling(self):
        # quantity=2 → doubles payoff
        result = self.s.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 470.0, quantity=2)
        assert float(result) == pytest.approx(1000.0)

    def test_invalid_option_type_returns_zero(self):
        result = self.s.calculate_option_payoff("INVALID", "LONG", 460.0, 5.0, 470.0)
        assert result == 0.0

    def test_module_level_function(self):
        result = _u14.calculate_option_payoff("CALL", "LONG", 460.0, 5.0, 470.0)
        assert float(result) == pytest.approx(500.0)


class TestCreateBullCallSpread:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_returns_option_strategy(self):
        strat = _simple_bull_call(self.s)
        assert isinstance(strat, OptionStrategy)

    def test_strategy_type(self):
        strat = _simple_bull_call(self.s)
        assert strat.strategy_type == StrategyType.BULL_CALL_SPREAD

    def test_two_legs(self):
        strat = _simple_bull_call(self.s)
        assert len(strat.legs) == 2

    def test_first_leg_is_long_call(self):
        strat = _simple_bull_call(self.s)
        assert strat.legs[0].is_long and strat.legs[0].is_call

    def test_second_leg_is_short_call(self):
        strat = _simple_bull_call(self.s)
        assert strat.legs[1].is_short and strat.legs[1].is_call

    def test_is_debit_strategy(self):
        # Long 8, Short 3 → net = -8+3 = -5 → debit
        strat = _simple_bull_call(self.s)
        assert strat.is_debit_strategy is True

    def test_max_loss_calculated(self):
        strat = _simple_bull_call(self.s)
        assert strat.max_loss is not None and strat.max_loss > 0

    def test_max_profit_calculated(self):
        strat = _simple_bull_call(self.s)
        assert strat.max_profit is not None and strat.max_profit > 0

    def test_name_contains_strikes(self):
        strat = _simple_bull_call(self.s)
        assert "450" in strat.name and "460" in strat.name


class TestCreateBearPutSpread:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_returns_option_strategy(self):
        strat = self.s.create_bear_put_spread(
            long_strike=460.0,
            short_strike=450.0,
            expiry=_expiry(30),
            long_premium=8.0,
            short_premium=3.0,
            underlying_price=455.0,
        )
        assert isinstance(strat, OptionStrategy)

    def test_strategy_type(self):
        strat = self.s.create_bear_put_spread(460.0, 450.0, _expiry(), 8.0, 3.0, 455.0)
        assert strat.strategy_type == StrategyType.BEAR_PUT_SPREAD

    def test_two_put_legs(self):
        strat = self.s.create_bear_put_spread(460.0, 450.0, _expiry(), 8.0, 3.0, 455.0)
        assert len(strat.legs) == 2
        assert all(leg.is_put for leg in strat.legs)

    def test_first_leg_is_long(self):
        strat = self.s.create_bear_put_spread(460.0, 450.0, _expiry(), 8.0, 3.0, 455.0)
        assert strat.legs[0].is_long

    def test_is_debit_strategy(self):
        strat = self.s.create_bear_put_spread(460.0, 450.0, _expiry(), 8.0, 3.0, 455.0)
        assert strat.is_debit_strategy is True


class TestCreateIronCondor:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_returns_option_strategy(self):
        assert isinstance(_simple_iron_condor(self.s), OptionStrategy)

    def test_strategy_type(self):
        strat = _simple_iron_condor(self.s)
        assert strat.strategy_type == StrategyType.IRON_CONDOR

    def test_four_legs(self):
        strat = _simple_iron_condor(self.s)
        assert len(strat.legs) == 4

    def test_is_credit_strategy(self):
        # premiums [2, 6, 6, 2]: short_put(+6)+ short_call(+6) − long_put(−2) − long_call(−2) = 8 > 0
        strat = _simple_iron_condor(self.s)
        assert strat.is_credit_strategy is True

    def test_net_premium(self):
        strat = _simple_iron_condor(self.s)
        assert strat.net_premium == pytest.approx(8.0)

    def test_max_profit_equals_net_premium(self):
        strat = _simple_iron_condor(self.s)
        assert strat.max_profit == pytest.approx(8.0)

    def test_max_loss_calculated(self):
        strat = _simple_iron_condor(self.s)
        # put_wing = (450-440)*100=1000, max_loss = 1000 - 8 = 992
        assert strat.max_loss == pytest.approx(992.0)


class TestCreateStraddle:
    def setup_method(self):
        self.s = OptionStrategies()

    def _long_straddle(self) -> OptionStrategy:
        return self.s.create_straddle(
            strike=460.0,
            expiry=_expiry(30),
            call_premium=8.0,
            put_premium=8.0,
            underlying_price=460.0,
            position_type="LONG",
        )

    def test_returns_option_strategy(self):
        assert isinstance(self._long_straddle(), OptionStrategy)

    def test_strategy_type(self):
        strat = self._long_straddle()
        assert strat.strategy_type == StrategyType.STRADDLE

    def test_two_legs(self):
        strat = self._long_straddle()
        assert len(strat.legs) == 2

    def test_one_call_one_put(self):
        strat = self._long_straddle()
        types = {leg.option_type for leg in strat.legs}
        assert OptionType.CALL in types and OptionType.PUT in types

    def test_long_straddle_is_debit(self):
        strat = self._long_straddle()
        assert strat.is_debit_strategy is True

    def test_long_straddle_max_loss(self):
        strat = self._long_straddle()
        # net_premium = -8 + -8 = -16; max_loss = abs(-16) = 16
        assert strat.max_loss == pytest.approx(16.0)

    def test_long_straddle_max_profit_is_inf(self):
        strat = self._long_straddle()
        assert strat.max_profit == float("inf")

    def test_short_straddle(self):
        strat = self.s.create_straddle(460.0, _expiry(), 8.0, 8.0, 460.0, "SHORT")
        assert strat.is_credit_strategy is True
        assert strat.max_profit == pytest.approx(16.0)
        assert strat.max_loss == float("inf")


class TestGetPayoffDiagram:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_returns_payoff_result(self):
        strat = _simple_bull_call(self.s)
        result = self.s.get_payoff_diagram(strat)
        assert isinstance(result, PayoffResult)

    def test_payoff_result_arrays_same_length(self):
        strat = _simple_bull_call(self.s)
        result = self.s.get_payoff_diagram(strat)
        assert len(result.spot_prices) == len(result.payoffs)

    def test_custom_num_points(self):
        strat = _simple_bull_call(self.s)
        result = self.s.get_payoff_diagram(strat, num_points=50)
        assert len(result.spot_prices) == 50

    def test_custom_price_range(self):
        strat = _simple_bull_call(self.s)
        result = self.s.get_payoff_diagram(strat, price_range=(400.0, 500.0))
        assert result.spot_prices[0] == pytest.approx(400.0)
        assert result.spot_prices[-1] == pytest.approx(500.0)

    def test_max_profit_and_loss_are_finite(self):
        strat = _simple_bull_call(self.s)
        result = self.s.get_payoff_diagram(strat)
        assert result.max_profit > result.max_loss


class TestStrategyPayoff:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_strategy_payoff_single_spot(self):
        strat = _simple_bull_call(self.s)
        # At spot=440 (both OTM): net = -8+3 = -5 → payoff = -5*100 = -500
        result = self.s.calculate_strategy_payoff(strat, 440.0)
        assert float(result) == pytest.approx(-500.0)

    def test_strategy_payoff_array(self):
        strat = _simple_bull_call(self.s)
        spots = np.array([430.0, 455.0, 470.0])
        result = self.s.calculate_strategy_payoff(strat, spots)
        assert len(result) == 3


class TestCalculateMaxProfitLoss:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_max_profit_positive(self):
        strat = _simple_bull_call(self.s)
        assert self.s.calculate_max_profit(strat) > 0

    def test_max_loss_negative(self):
        strat = _simple_bull_call(self.s)
        assert self.s.calculate_max_loss(strat) < 0

    def test_breakeven_points_list(self):
        strat = _simple_bull_call(self.s)
        bps = self.s.calculate_breakeven_points(strat)
        assert isinstance(bps, list)


class TestCalculateProfitProbability:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_returns_float_between_0_and_1(self):
        strat = _simple_bull_call(self.s)
        prob = self.s.calculate_profit_probability(strat, 0.15, 30)
        assert 0.0 <= prob <= 1.0

    def test_iron_condor_probability_in_range(self):
        strat = _simple_iron_condor(self.s)
        prob = self.s.calculate_profit_probability(strat, 0.10, 30)
        assert 0.0 <= prob <= 1.0


class TestFindBreakevenPoints:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_finds_zero_crossing(self):
        prices = np.array([100.0, 105.0, 110.0])
        payoffs = np.array([-100.0, 50.0, 100.0])
        bps = self.s._find_breakeven_points(prices, payoffs)
        assert len(bps) == 1
        assert bps[0] == pytest.approx(100 + 5 * (100 / 150), abs=0.1)

    def test_no_crossing(self):
        prices = np.array([100.0, 105.0])
        payoffs = np.array([100.0, 200.0])  # Always profitable
        bps = self.s._find_breakeven_points(prices, payoffs)
        assert bps == []


class TestNormalCDF:
    def setup_method(self):
        self.s = OptionStrategies()

    def test_at_zero(self):
        assert self.s._normal_cdf(0.0) == pytest.approx(0.5)

    def test_large_positive(self):
        assert self.s._normal_cdf(10.0) > 0.99

    def test_large_negative(self):
        assert self.s._normal_cdf(-10.0) < 0.01

    def test_symmetry(self):
        assert self.s._normal_cdf(-1.0) == pytest.approx(1.0 - self.s._normal_cdf(1.0), abs=1e-6)


class TestU14ModuleFunctions:
    def test_get_option_strategies_singleton(self):
        a = _u14.get_option_strategies()
        b = _u14.get_option_strategies()
        assert a is b

    def test_get_option_strategies_instance(self):
        assert isinstance(_u14.get_option_strategies(), OptionStrategies)

    def test_singleton_matches_module_var(self):
        inst = _u14.get_option_strategies()
        assert _u14._option_strategies is inst
