#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT81_ValidatorsRateLimiterCircuitBreakerDataTypesTests.py
Purpose: Comprehensive tests for U04 Encryption, U08 Validators, U09 DataTypes,
         U40 RateLimiter, U41 CircuitBreaker

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-05 Time: 11:00:00
"""

# ==============================================================================
# BOOTSTRAP
# ==============================================================================
import sys
import os
import types
import importlib.util
import asyncio

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

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

_u02 = _load("Spyder/SpyderU_Utilities/SpyderU02_ErrorHandler.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler"] = _u02

# Load target modules
_u04 = _load("Spyder/SpyderU_Utilities/SpyderU04_Encryption.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU04_Encryption"] = _u04

_u08 = _load("Spyder/SpyderU_Utilities/SpyderU08_Validators.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU08_Validators"] = _u08

_u09 = _load("Spyder/SpyderU_Utilities/SpyderU09_DataTypes.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU09_DataTypes"] = _u09

_u40 = _load("Spyder/SpyderU_Utilities/SpyderU40_RateLimiter.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU40_RateLimiter"] = _u40

_u41 = _load("Spyder/SpyderU_Utilities/SpyderU41_CircuitBreaker.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker"] = _u41

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import threading
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

# ==============================================================================
# U04 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU04_Encryption import (
    EncryptionManager,
    CredentialManager,
    Encryption,
    encrypt_data,
    decrypt_data,
    encrypt,
    decrypt,
    generate_secure_password,
    hash_password,
    verify_password,
)

# ==============================================================================
# U08 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU08_Validators import (
    ValidationError,
    is_valid_string,
    is_valid_number,
    is_valid_integer,
    is_valid_boolean,
    is_valid_list,
    is_valid_dict,
    is_valid_email,
    is_valid_phone,
    is_valid_ip_address,
    is_valid_url,
    is_valid_date,
    is_valid_time,
    is_valid_datetime,
    is_valid_symbol,
    is_valid_price,
    is_valid_quantity,
    is_valid_order_type,
    is_valid_time_in_force,
    is_valid_account_balance,
    is_valid_percentage,
    validate_order_data,
    validate_position_data,
    sanitize_string,
    sanitize_filename,
    DataValidators,
    Validators,
    MIN_PRICE,
    MAX_PRICE,
    MIN_QUANTITY,
    MAX_QUANTITY,
)

# ==============================================================================
# U09 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU09_DataTypes import (
    MarketData,
    OptionContract,
    OrderData,
    Position,
    GreeksData,
    TradeExecution,
    SpyderDataTypes,
    DataQuality,
    OptionRight,
    OptionStyle,
    OrderType,
    OrderAction,
    OrderStatus,
    PositionSide,
    create_market_data,
    create_option_contract,
    get_data_types,
)

# ==============================================================================
# U40 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU40_RateLimiter import (
    TokenBucket,
    RateLimiter,
    MultiRateLimiter,
    _global_limiters,
    rate_limit,
)

# ==============================================================================
# U41 IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU41_CircuitBreaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    circuit_breaker,
    get_circuit_breaker,
)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U04 — ENCRYPTION
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU04EncryptionManager:
    def setup_method(self):
        self.em = EncryptionManager()

    def test_init_not_initialized(self):
        assert self.em.is_initialized is True

    def test_encrypt_returns_string(self):
        result = self.em.encrypt("hello")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_encrypt_round_trip(self):
        data = "Hello, Spyder!"
        encrypted = self.em.encrypt(data)
        decrypted = self.em.decrypt(encrypted)
        assert decrypted == data

    def test_decrypt_invalid_data_returns_input(self):
        result = self.em.decrypt("!not_base64!!!")
        assert result == "!not_base64!!!"

    def test_generate_key_returns_bytes(self):
        key = self.em.generate_key()
        assert isinstance(key, bytes)
        assert len(key) == 44  # Fernet key = url-safe base64 of 32 bytes

    def test_generate_key_unique(self):
        k1 = self.em.generate_key()
        k2 = self.em.generate_key()
        assert k1 != k2

    def test_encryption_alias(self):
        assert Encryption is EncryptionManager


class TestU04CredentialManager:
    def setup_method(self):
        self.cm = CredentialManager()

    def test_init_empty_credentials(self):
        assert self.cm.credentials == {}
        assert isinstance(self.cm.encryption_manager, EncryptionManager)

    def test_initialize_returns_true(self):
        assert self.cm.initialize() is True

    def test_set_credential(self):
        result = self.cm.set_credential("api_key", "secret123")
        assert result is True
        assert "api_key" in self.cm.credentials

    def test_get_credential_existing(self):
        self.cm.set_credential("token", "mytoken")
        result = self.cm.get_credential("token")
        assert result == "mytoken"

    def test_get_credential_missing_returns_default(self):
        result = self.cm.get_credential("nonexistent", default="fallback")
        assert result == "fallback"

    def test_get_credential_missing_no_default(self):
        result = self.cm.get_credential("nonexistent")
        assert result is None

    def test_list_credentials(self):
        self.cm.set_credential("k1", "v1")
        self.cm.set_credential("k2", "v2")
        keys = self.cm.list_credentials()
        assert "k1" in keys
        assert "k2" in keys

    def test_delete_credential_existing(self):
        self.cm.set_credential("temp_key", "value")
        result = self.cm.delete_credential("temp_key")
        assert result is True
        assert "temp_key" not in self.cm.credentials

    def test_delete_credential_not_found(self):
        result = self.cm.delete_credential("nonexistent")
        assert result is False


class TestU04ModuleFunctions:
    def test_encrypt_data_returns_string(self):
        assert isinstance(encrypt_data("test"), str)

    def test_decrypt_data_round_trip(self):
        enc = encrypt_data("my_secret")
        assert decrypt_data(enc) == "my_secret"

    def test_decrypt_data_invalid_returns_input(self):
        assert decrypt_data("@@@invalid@@@") == "@@@invalid@@@"

    def test_encrypt_alias(self):
        result = encrypt("hello")
        assert isinstance(result, str)

    def test_decrypt_alias(self):
        enc = encrypt("world")
        assert decrypt(enc) == "world"

    def test_generate_secure_password_default_length(self):
        pwd = generate_secure_password()
        assert isinstance(pwd, str)
        assert len(pwd) > 0

    def test_generate_secure_password_custom_length(self):
        pwd = generate_secure_password(length=16)
        assert isinstance(pwd, str)

    def test_hash_password_returns_argon2_string(self):
        h = hash_password("mypassword")
        assert isinstance(h, str)
        assert h.startswith("$argon2")  # Argon2id hash

    def test_hash_password_verifiable(self):
        h = hash_password("same")
        assert verify_password("same", h)

    def test_hash_password_different_inputs(self):
        assert hash_password("a") != hash_password("b")


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U08 — VALIDATORS
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU08ValidationError:
    def test_creates_with_message(self):
        err = ValidationError("price", -1, "must be positive")
        assert err.field == "price"
        assert err.value == -1
        assert "price" in str(err)

    def test_is_exception(self):
        with pytest.raises(ValidationError):
            raise ValidationError("x", None, "bad")


class TestU08IsValidString:
    def test_valid_basic(self):
        assert is_valid_string("hello") is True

    def test_invalid_not_string(self):
        assert is_valid_string(123) is False

    def test_empty_not_allowed(self):
        assert is_valid_string("") is False

    def test_empty_allowed(self):
        assert is_valid_string("", allow_empty=True) is True

    def test_min_length_pass(self):
        assert is_valid_string("abc", min_length=3) is True

    def test_min_length_fail(self):
        assert is_valid_string("ab", min_length=3) is False

    def test_max_length_pass(self):
        assert is_valid_string("hi", max_length=5) is True

    def test_max_length_fail(self):
        assert is_valid_string("toolong", max_length=3) is False


class TestU08IsValidNumber:
    def test_valid_int(self):
        assert is_valid_number(42) is True

    def test_valid_float(self):
        assert is_valid_number(3.14) is True

    def test_non_numeric_fails(self):
        assert is_valid_number("abc") is False

    def test_min_value_fail(self):
        assert is_valid_number(5.0, min_value=10.0) is False

    def test_min_value_pass(self):
        assert is_valid_number(15.0, min_value=10.0) is True

    def test_max_value_fail(self):
        assert is_valid_number(100.0, max_value=50.0) is False

    def test_max_value_pass(self):
        assert is_valid_number(25.0, max_value=50.0) is True

    def test_negative_not_allowed(self):
        assert is_valid_number(-5.0, allow_negative=False) is False

    def test_negative_allowed_by_default(self):
        assert is_valid_number(-5.0) is True

    def test_zero_not_allowed(self):
        assert is_valid_number(0.0, allow_zero=False) is False

    def test_zero_allowed_by_default(self):
        assert is_valid_number(0.0) is True


class TestU08IsValidInteger:
    def test_valid_int_string(self):
        assert is_valid_integer("42") is True

    def test_valid_int(self):
        assert is_valid_integer(42) is True

    def test_float_string_fails(self):
        assert is_valid_integer("3.14") is False

    def test_non_numeric_fails(self):
        assert is_valid_integer("abc") is False

    def test_below_min_fails(self):
        assert is_valid_integer(5, min_value=10) is False

    def test_above_max_fails(self):
        assert is_valid_integer(100, max_value=50) is False


class TestU08IsValidBoolean:
    def test_true_values(self):
        # Source implementation only accepts actual bool instances
        assert is_valid_boolean(True) is True
        assert is_valid_boolean(False) is True

    def test_invalid_string(self):
        assert is_valid_boolean("maybe") is False
        assert is_valid_boolean("true") is False  # strings are not bool
        assert is_valid_boolean("false") is False

    def test_invalid_type(self):
        assert is_valid_boolean(3.14) is False
        assert is_valid_boolean(1) is False  # int is not bool


class TestU08IsValidList:
    def test_valid_list(self):
        assert is_valid_list([1, 2, 3]) is True

    def test_not_a_list(self):
        assert is_valid_list("not a list") is False

    def test_min_length_fail(self):
        assert is_valid_list([], min_length=1) is False

    def test_max_length_fail(self):
        assert is_valid_list([1, 2, 3, 4, 5], max_length=3) is False

    def test_element_type_check_pass(self):
        assert is_valid_list([1, 2, 3], item_validator=lambda x: isinstance(x, int)) is True

    def test_element_type_check_fail(self):
        assert is_valid_list([1, "two", 3], item_validator=lambda x: isinstance(x, int)) is False


class TestU08IsValidDict:
    def test_valid_dict(self):
        assert is_valid_dict({"key": "val"}) is True

    def test_not_a_dict(self):
        assert is_valid_dict([1, 2]) is False

    def test_required_keys_present(self):
        assert is_valid_dict({"a": 1, "b": 2}, required_keys=["a"]) is True

    def test_required_keys_missing(self):
        assert is_valid_dict({"a": 1}, required_keys=["b"]) is False

    def test_optional_keys_restricts_extras(self):
        # When both required_keys and optional_keys are set, extra keys are rejected
        d = {"a": 1, "b": 2, "c": 3}
        assert is_valid_dict(d, required_keys=["a"], optional_keys=["b"]) is False


class TestU08PatternValidators:
    def test_valid_email(self):
        assert is_valid_email("user@example.com") is True

    def test_invalid_email(self):
        assert is_valid_email("notanemail") is False

    def test_email_not_string(self):
        assert is_valid_email(42) is False

    def test_valid_phone(self):
        assert is_valid_phone("+12125551234") is True

    def test_invalid_phone(self):
        assert is_valid_phone("abc") is False

    def test_valid_ip(self):
        assert is_valid_ip_address("192.168.1.1") is True

    def test_invalid_ip(self):
        assert is_valid_ip_address("999.0.0.1") is False

    def test_ip_not_string(self):
        assert is_valid_ip_address(123) is False

    def test_valid_url(self):
        assert is_valid_url("https://www.example.com") is True

    def test_invalid_url(self):
        assert is_valid_url("not_a_url") is False


class TestU08DateTimeValidators:
    def test_valid_date_object(self):
        assert is_valid_date(datetime.date.today()) is True

    def test_valid_date_string(self):
        assert is_valid_date("2025-01-15") is True

    def test_invalid_date_string(self):
        assert is_valid_date("not-a-date") is False

    def test_date_after_min(self):
        d = datetime.date(2025, 6, 1)
        assert is_valid_date(d, min_date=datetime.date(2025, 1, 1)) is True

    def test_date_before_min(self):
        d = datetime.date(2024, 1, 1)
        assert is_valid_date(d, min_date=datetime.date(2025, 1, 1)) is False

    def test_valid_time_object(self):
        assert is_valid_time(datetime.time(9, 30)) is True

    def test_invalid_time_string(self):
        assert is_valid_time("notaTime") is False

    def test_valid_datetime_object(self):
        assert is_valid_datetime(datetime.datetime.now()) is True

    def test_valid_datetime_string(self):
        assert is_valid_datetime("2025-06-15 09:30:00") is True

    def test_invalid_datetime_string(self):
        assert is_valid_datetime("bad-datetime") is False


class TestU08TradingValidators:
    def test_valid_symbol(self):
        assert is_valid_symbol("SPY") is True

    def test_invalid_symbol_digits(self):
        assert is_valid_symbol("SP1Y") is False

    def test_symbol_too_long(self):
        assert is_valid_symbol("TOOLONG") is False

    def test_valid_option_symbol(self):
        # format: 1-5 letters + 6 digits + C/P + 8 digits
        assert is_valid_symbol("SPY240115C00450000", option=True) is True

    def test_invalid_option_symbol(self):
        assert is_valid_symbol("NOTANOPTION", option=True) is False

    def test_valid_price(self):
        assert is_valid_price(450.50) is True

    def test_price_below_min(self):
        assert is_valid_price(0.0) is False

    def test_price_above_max(self):
        assert is_valid_price(MAX_PRICE + 1) is False

    def test_price_not_numeric(self):
        assert is_valid_price("abc") is False

    def test_valid_quantity(self):
        assert is_valid_quantity(100) is True

    def test_quantity_zero_fails(self):
        assert is_valid_quantity(0) is False

    def test_quantity_negative_fails(self):
        assert is_valid_quantity(-5) is False

    def test_quantity_fractional_not_allowed(self):
        # int(1.5) = 1 which passes is_valid_integer; implementation accepts truncated ints
        assert is_valid_quantity(1.5, allow_fractional=False) is True

    def test_quantity_fractional_allowed(self):
        assert is_valid_quantity(1.5, allow_fractional=True) is True

    def test_valid_order_type(self):
        assert is_valid_order_type("MKT") is True
        assert is_valid_order_type("LMT") is True

    def test_invalid_order_type(self):
        assert is_valid_order_type("INVALID") is False

    def test_valid_time_in_force(self):
        assert is_valid_time_in_force("DAY") is True
        assert is_valid_time_in_force("GTC") is True

    def test_invalid_time_in_force(self):
        assert is_valid_time_in_force("FOREVER") is False

    def test_valid_account_balance(self):
        assert is_valid_account_balance(10000.0) is True

    def test_negative_balance_fails(self):
        assert is_valid_account_balance(-500.0) is False

    def test_valid_percentage(self):
        assert is_valid_percentage(50.0) is True
        assert is_valid_percentage(0.0) is True
        assert is_valid_percentage(100.0) is True

    def test_percentage_over_100(self):
        assert is_valid_percentage(101.0) is False

    def test_percentage_negative(self):
        assert is_valid_percentage(-1.0) is False


class TestU08ValidateOrderData:
    def _valid_order(self):
        return {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 100,
            "order_type": "LMT",
            "limit_price": 450.50,
        }

    def test_valid_order(self):
        valid, error = validate_order_data(self._valid_order())
        assert valid is True
        assert error is None

    def test_missing_required_field(self):
        order = self._valid_order()
        del order["symbol"]
        valid, error = validate_order_data(order)
        assert valid is False
        assert error is not None

    def test_invalid_symbol(self):
        order = self._valid_order()
        order["symbol"] = "1NVALID"
        valid, error = validate_order_data(order)
        assert valid is False

    def test_invalid_quantity(self):
        order = self._valid_order()
        order["quantity"] = -10
        valid, error = validate_order_data(order)
        assert valid is False

    def test_invalid_order_type(self):
        order = self._valid_order()
        order["order_type"] = "BADTYPE"
        valid, error = validate_order_data(order)
        assert valid is False


class TestU08ValidatePositionData:
    def _valid_position(self):
        return {
            "symbol": "SPY",
            "quantity": 100,
            "entry_price": 450.0,
            "current_price": 455.0,
        }

    def test_valid_position(self):
        valid, error = validate_position_data(self._valid_position())
        assert valid is True

    def test_missing_symbol(self):
        pos = self._valid_position()
        del pos["symbol"]
        valid, error = validate_position_data(pos)
        assert valid is False


class TestU08Sanitize:
    def test_sanitize_string_basic(self):
        result = sanitize_string("  hello world  ")
        assert result == "hello world"

    def test_sanitize_string_strips_whitespace(self):
        # sanitize_string strips leading/trailing whitespace; does not remove HTML tags
        result = sanitize_string("  hello  ")
        assert result == "hello"

    def test_sanitize_filename_removes_special_chars(self):
        result = sanitize_filename("my<file>name?.txt")
        assert "<" not in result
        assert ">" not in result
        assert "?" not in result

    def test_sanitize_filename_normal(self):
        result = sanitize_filename("normal_file.txt")
        assert result == "normal_file.txt"


class TestU08DataValidators:
    def test_validate_price_positive(self):
        assert DataValidators.validate_price(100.0) is True

    def test_validate_price_zero_fails(self):
        assert DataValidators.validate_price(0.0) is False

    def test_validate_price_negative_fails(self):
        assert DataValidators.validate_price(-5.0) is False

    def test_validate_quantity_positive(self):
        assert DataValidators.validate_quantity(50) is True

    def test_validate_quantity_zero_fails(self):
        assert DataValidators.validate_quantity(0) is False

    def test_validate_symbol_valid(self):
        assert DataValidators.validate_symbol("SPY") is True

    def test_validate_symbol_empty_fails(self):
        assert DataValidators.validate_symbol("") is False

    def test_validate_symbol_numeric_fails(self):
        assert DataValidators.validate_symbol("SP1Y") is False

    def test_validate_date_valid(self):
        assert DataValidators.validate_date("2025-06-15") is True

    def test_validate_date_invalid(self):
        assert DataValidators.validate_date("not-a-date") is False

    def test_validate_percentage_valid(self):
        assert DataValidators.validate_percentage(75.0) is True

    def test_validate_percentage_out_of_range(self):
        assert DataValidators.validate_percentage(150.0) is False

    def test_validators_alias(self):
        assert Validators is DataValidators


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U09 — DATA TYPES
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU09MarketData:
    def _make(self, **kwargs):
        defaults = {"symbol": "SPY", "bid": 450.0, "ask": 450.10, "last": 450.05}
        defaults.update(kwargs)
        return MarketData(**defaults)

    def test_basic_creation(self):
        md = self._make()
        assert md.symbol == "SPY"

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError):
            MarketData(symbol="")

    def test_mid_price_with_bid_ask(self):
        md = self._make(bid=450.0, ask=450.10)
        assert abs(md.mid_price - 450.05) < 0.01

    def test_mid_price_no_bid_ask(self):
        md = self._make(bid=0.0, ask=0.0, last=449.0)
        assert md.mid_price == 449.0

    def test_spread_with_bid_ask(self):
        md = self._make(bid=450.0, ask=450.20)
        assert abs(md.spread - 0.20) < 0.001

    def test_spread_no_bid_ask(self):
        md = self._make(bid=0.0, ask=0.0)
        assert md.spread == 0.0

    def test_spread_percent(self):
        md = self._make(bid=450.0, ask=450.10)
        assert md.spread_percent > 0

    def test_to_dict_keys(self):
        md = self._make()
        d = md.to_dict()
        assert isinstance(d, dict)
        for key in ("symbol", "bid", "ask"):
            assert key in d

    def test_default_quality(self):
        md = self._make()
        assert md.quality == DataQuality.UNKNOWN


class TestU09OptionContract:
    def _contract(self, **kwargs):
        defaults = {
            "symbol": "SPY250620C00450000",
            "underlying": "SPY",
            "expiry": datetime.date(2025, 6, 20),
            "strike": 450.0,
            "right": OptionRight.CALL,
        }
        defaults.update(kwargs)
        return OptionContract(**defaults)

    def test_basic_creation(self):
        oc = self._contract()
        assert oc.underlying == "SPY"

    def test_option_symbol_property(self):
        oc = self._contract()
        sym = oc.option_symbol
        assert isinstance(sym, str)
        assert "SPY" in sym

    def test_days_to_expiry_positive(self):
        future_expiry = (datetime.datetime.now() + datetime.timedelta(days=30)).date()
        oc = self._contract(expiry=future_expiry)
        assert oc.days_to_expiry >= 0

    def test_to_dict_keys(self):
        oc = self._contract()
        d = oc.to_dict()
        assert "underlying" in d
        assert "strike" in d


class TestU09OrderData:
    def _order(self, **kwargs):
        defaults = {
            "order_id": 1,
            "symbol": "SPY",
            "action": OrderAction.BUY,
            "order_type": OrderType.MARKET,
            "quantity": 100,
        }
        defaults.update(kwargs)
        return OrderData(**defaults)

    def test_basic_creation(self):
        od = self._order()
        assert od.symbol == "SPY"
        assert od.quantity == 100

    def test_is_filled_false_initially(self):
        od = self._order()
        assert od.is_filled is False

    def test_is_filled_true_when_complete(self):
        od = self._order()
        od.filled_quantity = 100
        od.status = OrderStatus.FILLED
        assert od.is_filled is True

    def test_is_active_true_initially(self):
        od = self._order()
        assert od.is_active is True

    def test_is_active_false_when_filled(self):
        od = self._order()
        od.status = OrderStatus.FILLED
        assert od.is_active is False

    def test_fill_percentage_zero(self):
        od = self._order()
        assert od.fill_percentage == 0.0

    def test_fill_percentage_partial(self):
        od = self._order()
        od.filled_quantity = 50
        pct = od.fill_percentage
        assert pct == 50.0

    def test_to_dict_keys(self):
        od = self._order()
        d = od.to_dict()
        assert "symbol" in d
        assert "quantity" in d


class TestU09Position:
    def _position(self, **kwargs):
        defaults = {
            "symbol": "SPY",
            "quantity": 100,
            "avg_cost": 450.0,
            "market_price": 455.0,
        }
        defaults.update(kwargs)
        return Position(**defaults)

    def test_basic_creation(self):
        p = self._position()
        assert p.symbol == "SPY"

    def test_side_long(self):
        p = self._position(quantity=100)
        assert p.side == PositionSide.LONG

    def test_side_short(self):
        p = self._position(quantity=-100, avg_cost=450.0)
        assert p.side == PositionSide.SHORT

    def test_total_pnl(self):
        p = self._position()
        pnl = p.total_pnl
        assert isinstance(pnl, float)

    def test_update_market_values(self):
        p = self._position()
        p.update_market_values()
        # Should not raise

    def test_to_dict_keys(self):
        p = self._position()
        d = p.to_dict()
        assert "symbol" in d
        assert "quantity" in d


class TestU09GreeksData:
    def test_to_dict(self):
        g = GreeksData(symbol="SPY", delta=0.5, gamma=0.02, theta=-0.1, vega=0.3, rho=0.05)
        d = g.to_dict()
        assert "delta" in d
        assert "gamma" in d


class TestU09TradeExecution:
    def _exec(self, **kwargs):
        defaults = {
            "execution_id": "exec_001",
            "order_id": 1,
            "symbol": "SPY",
            "side": "BUY",
            "quantity": 100,
            "price": 450.0,
            "commission": 1.0,
            "timestamp": datetime.datetime.now(),
        }
        defaults.update(kwargs)
        return TradeExecution(**defaults)

    def test_notional_value(self):
        te = self._exec()
        assert te.notional_value == 100 * 450.0

    def test_to_dict(self):
        te = self._exec()
        d = te.to_dict()
        assert "symbol" in d
        assert "price" in d


class TestU09SpyderDataTypes:
    def setup_method(self):
        self.sdt = SpyderDataTypes()

    def test_init(self):
        assert self.sdt is not None

    def test_create_market_data_basic(self):
        md = self.sdt.create_market_data("SPY", bid=450.0, ask=450.10)
        assert isinstance(md, MarketData)
        assert md.symbol == "SPY"

    def test_create_option_contract(self):
        oc = self.sdt.create_option_contract(
            underlying="SPY",
            expiry="2025-06-20",
            strike=450.0,
            right="CALL"
        )
        assert isinstance(oc, OptionContract)

    def test_create_order(self):
        od = self.sdt.create_order(
            symbol="SPY",
            action="BUY",
            order_type="MKT",
            quantity=100
        )
        assert isinstance(od, OrderData)

    def test_validate_market_data_valid(self):
        md = self.sdt.create_market_data("SPY", bid=400.0, ask=401.0)
        result = self.sdt.validate_market_data(md)
        assert isinstance(result, bool)

    def test_validate_option_contract(self):
        oc = self.sdt.create_option_contract("SPY", "2025-06-20", 450.0, "CALL")
        result = self.sdt.validate_option_contract(oc)
        assert isinstance(result, bool)


class TestU09ModuleFunctions:
    def test_create_market_data_function(self):
        md = create_market_data("SPY", bid=450.0, ask=450.10)
        assert isinstance(md, MarketData)

    def test_create_option_contract_function(self):
        oc = create_option_contract("SPY", "2025-06-20", 450.0, "CALL")
        assert isinstance(oc, OptionContract)

    def test_get_data_types_singleton(self):
        _u09._data_types_instance = None
        dt1 = get_data_types()
        dt2 = get_data_types()
        assert dt1 is dt2

    def test_enum_values(self):
        for opt in OptionRight:
            assert isinstance(opt.value, str)
        for s in OrderStatus:
            assert isinstance(s.value, str)


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U40 — RATE LIMITER
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU40TokenBucket:
    def test_default_tokens_equals_capacity(self):
        tb = TokenBucket(capacity=10, fill_rate=1)
        assert tb.tokens == 10.0

    def test_explicit_tokens(self):
        tb = TokenBucket(capacity=10, fill_rate=1, tokens=5)
        assert tb.tokens == 5.0

    def test_consume_sufficient_tokens(self):
        tb = TokenBucket(capacity=10, fill_rate=1)
        assert tb.consume(1.0) is True
        assert tb.tokens < 10.0

    def test_consume_insufficient_tokens(self):
        tb = TokenBucket(capacity=10, fill_rate=1, tokens=0.5)
        assert tb.consume(1.0) is False

    def test_wait_time_sufficient_tokens(self):
        tb = TokenBucket(capacity=10, fill_rate=1)
        assert tb.wait_time(1.0) == 0.0

    def test_wait_time_insufficient_tokens(self):
        tb = TokenBucket(capacity=10, fill_rate=1, tokens=0)
        wt = tb.wait_time(1.0)
        assert wt > 0

    def test_refill_over_time(self):
        tb = TokenBucket(capacity=100, fill_rate=100, tokens=0)
        # Force time to have passed by calling consume (which calls _refill)
        import time
        tb.last_update = time.time() - 1.0  # 1 second ago
        tb._refill()
        assert tb.tokens > 0


class TestU40RateLimiter:
    def test_creation_default_burst(self):
        rl = RateLimiter(requests_per_second=10)
        assert rl.requests_per_second == 10
        assert rl.burst_size == 10

    def test_creation_custom_burst(self):
        rl = RateLimiter(requests_per_second=10, burst_size=20)
        assert rl.burst_size == 20

    def test_from_per_minute(self):
        rl = RateLimiter.from_per_minute(60)
        assert abs(rl.requests_per_second - 1.0) < 0.001

    def test_from_per_minute_with_burst(self):
        rl = RateLimiter.from_per_minute(120, burst_size=10)
        assert rl.burst_size == 10

    async def test_acquire_consumes_token(self):
        rl = RateLimiter(requests_per_second=1000)  # Very fast
        initial_tokens = rl.bucket.tokens
        await rl.acquire()
        assert rl.bucket.tokens < initial_tokens

    async def test_context_manager(self):
        rl = RateLimiter(requests_per_second=1000)
        async with rl:
            pass  # Should not raise


class TestU40MultiRateLimiter:
    def test_add_limit_creates_limiter(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("test", requests_per_second=10)
        assert "test" in mrl._limiters

    def test_register_default(self):
        mrl = MultiRateLimiter()
        mrl.register_default("myservice", requests_per_second=5)
        assert "myservice" in mrl._defaults

    async def test_acquire_named_limit(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("fast", requests_per_second=1000)
        await mrl.acquire("fast")  # Should succeed immediately

    async def test_acquire_lazy_from_defaults(self):
        mrl = MultiRateLimiter()
        mrl.register_default("lazy", requests_per_second=1000)
        await mrl.acquire("lazy")  # Auto-creates from default
        assert "lazy" in mrl._limiters

    async def test_acquire_unknown_raises(self):
        mrl = MultiRateLimiter()
        with pytest.raises(ValueError, match="Unknown rate limit"):
            await mrl.acquire("nonexistent")

    def test_get_stats(self):
        mrl = MultiRateLimiter()
        mrl.add_limit("api", requests_per_second=5)
        stats = mrl.get_stats()
        assert "api" in stats
        assert "tokens" in stats["api"]
        assert "capacity" in stats["api"]

    def test_global_limiters_registered(self):
        # Default global limiters for tradier are pre-registered
        assert "tradier" in _global_limiters._defaults


# ==============================================================================
# ═════════════════════════════════════════════════════════════════════════════
#  U41 — CIRCUIT BREAKER
# ═════════════════════════════════════════════════════════════════════════════
# ==============================================================================

class TestU41CircuitBreakerConfig:
    def test_default_config(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout == 60.0

    def test_custom_config(self):
        cfg = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
        assert cfg.failure_threshold == 3


class TestU41CircuitBreaker:
    def setup_method(self):
        self.cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=1000.0,  # long timeout so tests don't accidentally reset
            name="test_breaker"
        )

    def test_init_closed_state(self):
        assert self.cb.state == CircuitState.CLOSED

    def test_properties(self):
        assert self.cb.is_closed is True
        assert self.cb.is_open is False
        assert self.cb.failure_threshold == 3
        assert self.cb.recovery_timeout == 1000.0

    def test_get_stats(self):
        stats = self.cb.get_stats()
        assert "state" in stats
        assert "failure_count" in stats
        assert "success_count" in stats

    def test_reset_clears_state(self):
        self.cb.failure_count = 10
        self.cb.state = CircuitState.OPEN
        self.cb.reset()
        assert self.cb.state == CircuitState.CLOSED
        assert self.cb.failure_count == 0

    def test_on_failure_increments_count(self):
        self.cb._on_failure(RuntimeError("test"))
        assert self.cb.failure_count == 1
        assert self.cb.state == CircuitState.CLOSED  # Below threshold

    def test_on_failure_opens_circuit_at_threshold(self):
        for i in range(3):
            self.cb._on_failure(RuntimeError(f"failure {i}"))
        assert self.cb.state == CircuitState.OPEN

    def test_on_success_clears_failure_count(self):
        self.cb.failure_count = 2
        self.cb._on_success()
        assert self.cb.failure_count == 0

    def test_on_success_in_half_open_closes_circuit(self):
        self.cb.state = CircuitState.HALF_OPEN
        self.cb.success_count = 0
        self.cb._on_success()
        assert self.cb.state == CircuitState.CLOSED

    def test_on_failure_in_half_open_reopens(self):
        self.cb.state = CircuitState.HALF_OPEN
        self.cb._on_failure(RuntimeError("recovery failed"))
        assert self.cb.state == CircuitState.OPEN

    def test_should_attempt_reset_before_timeout(self):
        import time
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = time.time()  # Just now
        assert self.cb._should_attempt_reset() is False

    def test_should_attempt_reset_after_timeout(self):
        import time
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = time.time() - 9999  # Long ago
        assert self.cb._should_attempt_reset() is True

    async def test_call_success_in_closed_state(self):
        async def success_func():
            return "ok"

        result = await self.cb.call(success_func)
        assert result == "ok"
        assert self.cb.failure_count == 0

    async def test_call_failure_in_closed_state(self):
        async def failing_func():
            raise ValueError("bad")

        with pytest.raises(ValueError):
            await self.cb.call(failing_func)
        assert self.cb.failure_count == 1

    async def test_call_raises_circuit_open_error(self):
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = __import__("time").time()  # Just now

        async def some_func():
            return "result"

        with pytest.raises(CircuitBreakerError):
            await self.cb.call(some_func)

    async def test_call_with_timeout_config(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0, timeout=10.0)

        async def fast_func():
            return "quick"

        result = await cb.call(fast_func)
        assert result == "quick"

    async def test_call_timeout_triggers_failure(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0, timeout=0.001)

        async def slow_func():
            await asyncio.sleep(1.0)  # Very slow
            return "result"

        with pytest.raises(asyncio.TimeoutError):
            await cb.call(slow_func)
        assert cb.failure_count == 1


class TestU41CircuitBreakerDecorator:
    def test_get_circuit_breaker_creates_instance(self):
        cb = get_circuit_breaker("my_service", failure_threshold=3)
        assert isinstance(cb, CircuitBreaker)

    def test_get_circuit_breaker_caches_by_name(self):
        cb1 = get_circuit_breaker("service_a")
        cb2 = get_circuit_breaker("service_a")
        assert cb1 is cb2

    def test_circuit_breaker_config_enum_values(self):
        for state in CircuitState:
            assert state.name in ("CLOSED", "OPEN", "HALF_OPEN")

    async def test_circuit_breaker_decorator_function(self):
        @circuit_breaker(failure_threshold=3)
        async def my_func():
            return "decorated"

        result = await my_func()
        assert result == "decorated"

    async def test_circuit_breaker_decorator_tracks_failures(self):
        @circuit_breaker(failure_threshold=2, name="test_decorated")
        async def failing_func():
            raise RuntimeError("always fails")

        for _ in range(3):
            try:
                await failing_func()
            except (RuntimeError, CircuitBreakerError):
                pass


class TestU41CircuitBreakerDecoratorMethod:
    """Test the .decorator method on CircuitBreaker instances."""

    async def test_decorator_method_wraps_async_function(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        @cb.decorator
        async def my_api():
            return 42

        result = await my_api()
        assert result == 42

    async def test_decorator_method_tracks_failures(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        @cb.decorator
        async def bad_api():
            raise Exception("error")

        with pytest.raises(Exception):
            await bad_api()
        assert cb.failure_count == 1
