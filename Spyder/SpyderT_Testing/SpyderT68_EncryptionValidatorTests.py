#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderT_Testing
Module: SpyderT68_EncryptionValidatorTests.py
Purpose: Tests for U04 Encryption and U08 Validators

Author: Spyder Test Suite
Year Created: 2026
Last Updated: 2026-03-04 Time: 14:00:00
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

_u01 = _load("Spyder/SpyderU_Utilities/SpyderU01_Logger.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU01_Logger"] = _u01

# U04 — no local imports
_u04 = _load("Spyder/SpyderU_Utilities/SpyderU04_Encryption.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU04_Encryption"] = _u04

# U08 — needs U01 already registered above
_u08 = _load("Spyder/SpyderU_Utilities/SpyderU08_Validators.py")
sys.modules["Spyder.SpyderU_Utilities.SpyderU08_Validators"] = _u08

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import base64
import hashlib
import pytest
from datetime import date, datetime, time

# ==============================================================================
# MODULE IMPORTS — U04
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
)

# ==============================================================================
# MODULE IMPORTS — U08
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
    validate_config_value,
    sanitize_string,
    DataValidators,
    VALID_ORDER_TYPES,
    VALID_TIME_IN_FORCE,
)


# ==============================================================================
# U04 — EncryptionManager TESTS
# ==============================================================================
class TestEncryptionManagerInit:
    """Tests for EncryptionManager construction."""

    def test_creates_instance(self):
        em = EncryptionManager()
        assert em is not None

    def test_is_initialized_false(self):
        em = EncryptionManager()
        assert em.is_initialized is False

    def test_is_encryption_alias(self):
        assert Encryption is EncryptionManager


class TestEncryptionManagerEncrypt:
    """Tests for EncryptionManager.encrypt."""

    def test_encrypt_returns_string(self):
        em = EncryptionManager()
        result = em.encrypt("hello")
        assert isinstance(result, str)

    def test_encrypt_is_base64(self):
        em = EncryptionManager()
        result = em.encrypt("hello")
        decoded = base64.b64decode(result.encode()).decode()
        assert decoded == "hello"

    def test_encrypt_empty_string(self):
        em = EncryptionManager()
        result = em.encrypt("")
        assert isinstance(result, str)

    def test_encrypt_unicode(self):
        em = EncryptionManager()
        result = em.encrypt("données")
        assert isinstance(result, str)


class TestEncryptionManagerDecrypt:
    """Tests for EncryptionManager.decrypt."""

    def test_decrypt_reverses_encrypt(self):
        em = EncryptionManager()
        original = "secret data"
        assert em.decrypt(em.encrypt(original)) == original

    def test_decrypt_bad_input_returns_input(self):
        em = EncryptionManager()
        bad = "!not-base64!!!"
        result = em.decrypt(bad)
        assert result == bad

    def test_decrypt_empty_string(self):
        em = EncryptionManager()
        result = em.decrypt(em.encrypt(""))
        assert result == ""


class TestEncryptionManagerGenerateKey:
    """Tests for EncryptionManager.generate_key."""

    def test_returns_bytes(self):
        em = EncryptionManager()
        key = em.generate_key()
        assert isinstance(key, bytes)

    def test_key_is_32_bytes(self):
        em = EncryptionManager()
        key = em.generate_key()
        assert len(key) == 32

    def test_keys_are_random(self):
        em = EncryptionManager()
        assert em.generate_key() != em.generate_key()


# ==============================================================================
# U04 — CredentialManager TESTS
# ==============================================================================
class TestCredentialManagerInit:
    """Tests for CredentialManager construction."""

    def test_creates_instance(self):
        cm = CredentialManager()
        assert cm is not None

    def test_starts_empty(self):
        cm = CredentialManager()
        assert cm.credentials == {}

    def test_has_encryption_manager(self):
        cm = CredentialManager()
        assert isinstance(cm.encryption_manager, EncryptionManager)

    def test_initialize_returns_true(self):
        cm = CredentialManager()
        assert cm.initialize() is True


class TestCredentialManagerCRUD:
    """Tests for CredentialManager CRUD operations."""

    def test_set_credential_returns_true(self):
        cm = CredentialManager()
        assert cm.set_credential("api_key", "secret123") is True

    def test_get_credential_retrieves_value(self):
        cm = CredentialManager()
        cm.set_credential("key1", "value1")
        assert cm.get_credential("key1") == "value1"

    def test_get_credential_returns_default_when_missing(self):
        cm = CredentialManager()
        assert cm.get_credential("nonexistent", "default") == "default"

    def test_get_credential_returns_none_default(self):
        cm = CredentialManager()
        assert cm.get_credential("nonexistent") is None

    def test_list_credentials_returns_keys(self):
        cm = CredentialManager()
        cm.set_credential("k1", "v1")
        cm.set_credential("k2", "v2")
        keys = cm.list_credentials()
        assert "k1" in keys
        assert "k2" in keys

    def test_list_credentials_empty(self):
        cm = CredentialManager()
        assert cm.list_credentials() == []

    def test_delete_credential_returns_true(self):
        cm = CredentialManager()
        cm.set_credential("temp", "val")
        assert cm.delete_credential("temp") is True

    def test_delete_credential_removes_key(self):
        cm = CredentialManager()
        cm.set_credential("temp", "val")
        cm.delete_credential("temp")
        assert cm.get_credential("temp") is None

    def test_delete_missing_returns_false(self):
        cm = CredentialManager()
        assert cm.delete_credential("never_set") is False


# ==============================================================================
# U04 — Module-level functions TESTS
# ==============================================================================
class TestEncryptionModuleFunctions:
    """Tests for module-level encryption functions."""

    def test_encrypt_data_returns_string(self):
        assert isinstance(encrypt_data("test"), str)

    def test_encrypt_data_is_base64(self):
        result = encrypt_data("test")
        assert base64.b64decode(result.encode()).decode() == "test"

    def test_decrypt_data_reverses_encrypt(self):
        assert decrypt_data(encrypt_data("hello")) == "hello"

    def test_decrypt_data_bad_input_returns_input(self):
        bad = "!!not-valid-base64-@@"
        assert decrypt_data(bad) == bad

    def test_encrypt_alias_works(self):
        assert encrypt("hello") == encrypt_data("hello")

    def test_decrypt_alias_works(self):
        assert decrypt(encrypt_data("hello")) == "hello"

    def test_generate_secure_password_returns_string(self):
        assert isinstance(generate_secure_password(), str)

    def test_generate_secure_password_non_empty(self):
        assert len(generate_secure_password()) > 0

    def test_generate_passwords_are_unique(self):
        assert generate_secure_password() != generate_secure_password()

    def test_hash_password_returns_hex_string(self):
        h = hash_password("password123")
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 = 64 hex chars

    def test_hash_password_consistent(self):
        assert hash_password("same") == hash_password("same")

    def test_hash_password_different_inputs(self):
        assert hash_password("abc") != hash_password("xyz")

    def test_hash_uses_sha256(self):
        expected = hashlib.sha256(b"test").hexdigest()
        assert hash_password("test") == expected


# ==============================================================================
# U08 — ValidationError TESTS
# ==============================================================================
class TestValidationError:
    """Tests for ValidationError exception."""

    def test_is_exception_subclass(self):
        assert issubclass(ValidationError, Exception)

    def test_can_be_raised(self):
        with pytest.raises(ValidationError):
            raise ValidationError("price", -1, "must be positive")

    def test_field_stored(self):
        e = ValidationError("qty", 0, "must be > 0")
        assert e.field == "qty"

    def test_value_stored(self):
        e = ValidationError("price", -5, "negative")
        assert e.value == -5

    def test_message_stored(self):
        e = ValidationError("x", 1, "the message")
        assert e.message == "the message"

    def test_str_contains_field(self):
        e = ValidationError("symbol", "BAD", "invalid")
        assert "symbol" in str(e)


# ==============================================================================
# U08 — is_valid_string TESTS
# ==============================================================================
class TestIsValidString:
    """Tests for is_valid_string."""

    def test_simple_string(self):
        assert is_valid_string("hello") is True

    def test_non_string_rejected(self):
        assert is_valid_string(123) is False

    def test_empty_string_rejected_by_default(self):
        assert is_valid_string("") is False

    def test_empty_string_allowed(self):
        assert is_valid_string("", allow_empty=True) is True

    def test_min_length_pass(self):
        assert is_valid_string("abc", min_length=3) is True

    def test_min_length_fail(self):
        assert is_valid_string("ab", min_length=3) is False

    def test_max_length_pass(self):
        assert is_valid_string("abc", max_length=5) is True

    def test_max_length_fail(self):
        assert is_valid_string("abcdef", max_length=5) is False

    def test_none_rejected(self):
        assert is_valid_string(None) is False


# ==============================================================================
# U08 — is_valid_number TESTS
# ==============================================================================
class TestIsValidNumber:
    """Tests for is_valid_number."""

    def test_float_valid(self):
        assert is_valid_number(3.14) is True

    def test_int_valid(self):
        assert is_valid_number(42) is True

    def test_string_number_valid(self):
        assert is_valid_number("10.5") is True

    def test_non_numeric_rejected(self):
        assert is_valid_number("abc") is False

    def test_none_rejected(self):
        assert is_valid_number(None) is False

    def test_negative_disallowed(self):
        assert is_valid_number(-1, allow_negative=False) is False

    def test_zero_disallowed(self):
        assert is_valid_number(0, allow_zero=False) is False

    def test_min_value_pass(self):
        assert is_valid_number(5, min_value=5) is True

    def test_min_value_fail(self):
        assert is_valid_number(4, min_value=5) is False

    def test_max_value_pass(self):
        assert is_valid_number(99, max_value=100) is True

    def test_max_value_fail(self):
        assert is_valid_number(101, max_value=100) is False


# ==============================================================================
# U08 — is_valid_integer TESTS
# ==============================================================================
class TestIsValidInteger:
    """Tests for is_valid_integer."""

    def test_int_valid(self):
        assert is_valid_integer(5) is True

    def test_bool_rejected(self):
        assert is_valid_integer(True) is False

    def test_float_truncated_to_int_valid(self):
        # int(3.5) == 3 — implementation accepts floats via int() conversion
        assert is_valid_integer(3.5) is True

    def test_string_int_valid(self):
        assert is_valid_integer("42") is True

    def test_string_float_rejected(self):
        assert is_valid_integer("3.5") is False

    def test_min_bound_pass(self):
        assert is_valid_integer(1, min_value=1) is True

    def test_min_bound_fail(self):
        assert is_valid_integer(0, min_value=1) is False

    def test_max_bound_fail(self):
        assert is_valid_integer(10, max_value=5) is False


# ==============================================================================
# U08 — is_valid_boolean TESTS
# ==============================================================================
class TestIsValidBoolean:
    """Tests for is_valid_boolean."""

    def test_true_valid(self):
        assert is_valid_boolean(True) is True

    def test_false_valid(self):
        assert is_valid_boolean(False) is True

    def test_int_one_rejected(self):
        assert is_valid_boolean(1) is False

    def test_string_rejected(self):
        assert is_valid_boolean("true") is False

    def test_none_rejected(self):
        assert is_valid_boolean(None) is False


# ==============================================================================
# U08 — is_valid_list TESTS
# ==============================================================================
class TestIsValidList:
    """Tests for is_valid_list."""

    def test_list_valid(self):
        assert is_valid_list([1, 2, 3]) is True

    def test_non_list_rejected(self):
        assert is_valid_list((1, 2)) is False

    def test_empty_list_valid(self):
        assert is_valid_list([]) is True

    def test_min_length_fail(self):
        assert is_valid_list([1], min_length=2) is False

    def test_max_length_fail(self):
        assert is_valid_list([1, 2, 3], max_length=2) is False

    def test_item_validator_pass(self):
        assert is_valid_list([1, 2, 3], item_validator=lambda x: x > 0) is True

    def test_item_validator_fail(self):
        assert is_valid_list([1, -1, 3], item_validator=lambda x: x > 0) is False


# ==============================================================================
# U08 — is_valid_dict TESTS
# ==============================================================================
class TestIsValidDict:
    """Tests for is_valid_dict."""

    def test_dict_valid(self):
        assert is_valid_dict({"a": 1}) is True

    def test_non_dict_rejected(self):
        assert is_valid_dict([1, 2]) is False

    def test_required_keys_present(self):
        assert is_valid_dict({"a": 1, "b": 2}, required_keys=["a", "b"]) is True

    def test_required_keys_missing(self):
        assert is_valid_dict({"a": 1}, required_keys=["a", "b"]) is False

    def test_optional_keys_restrict_extras(self):
        d = {"a": 1, "c": 3}
        assert is_valid_dict(d, required_keys=["a"], optional_keys=["b"]) is False

    def test_no_schema_accepts_any(self):
        assert is_valid_dict({"x": 99}) is True


# ==============================================================================
# U08 — Pattern validators TESTS
# ==============================================================================
class TestEmailValidator:
    """Tests for is_valid_email."""

    def test_valid_email(self):
        assert is_valid_email("user@example.com") is True

    def test_invalid_no_at(self):
        assert is_valid_email("userexample.com") is False

    def test_invalid_no_domain(self):
        assert is_valid_email("user@") is False

    def test_non_string(self):
        assert is_valid_email(123) is False


class TestPhoneValidator:
    """Tests for is_valid_phone."""

    def test_valid_us_phone(self):
        assert is_valid_phone("5551234567") is True

    def test_valid_with_plus(self):
        assert is_valid_phone("+15551234567") is True

    def test_valid_with_dashes(self):
        assert is_valid_phone("555-123-4567") is True

    def test_too_short(self):
        assert is_valid_phone("123") is False

    def test_non_string(self):
        assert is_valid_phone(5551234567) is False


class TestIpAddressValidator:
    """Tests for is_valid_ip_address."""

    def test_valid_ip(self):
        assert is_valid_ip_address("192.168.1.1") is True

    def test_valid_loopback(self):
        assert is_valid_ip_address("127.0.0.1") is True

    def test_invalid_out_of_range(self):
        assert is_valid_ip_address("999.1.1.1") is False

    def test_invalid_format(self):
        assert is_valid_ip_address("not.an.ip.address.extra") is False

    def test_non_string(self):
        assert is_valid_ip_address(192168) is False


class TestUrlValidator:
    """Tests for is_valid_url."""

    def test_valid_http_url(self):
        assert is_valid_url("http://example.com") is True

    def test_valid_https_url(self):
        assert is_valid_url("https://www.example.com/path?q=1") is True

    def test_invalid_no_scheme(self):
        assert is_valid_url("example.com") is False

    def test_non_string(self):
        assert is_valid_url(None) is False


# ==============================================================================
# U08 — Date/time validators TESTS
# ==============================================================================
class TestDateValidator:
    """Tests for is_valid_date."""

    def test_date_object_valid(self):
        assert is_valid_date(date(2026, 1, 15)) is True

    def test_string_iso_format(self):
        assert is_valid_date("2026-01-15") is True

    def test_string_us_format(self):
        assert is_valid_date("01/15/2026") is True

    def test_invalid_string(self):
        assert is_valid_date("not-a-date") is False

    def test_min_date_pass(self):
        assert is_valid_date(date(2026, 6, 1), min_date=date(2026, 1, 1)) is True

    def test_min_date_fail(self):
        assert is_valid_date(date(2025, 1, 1), min_date=date(2026, 1, 1)) is False

    def test_max_date_fail(self):
        assert is_valid_date(date(2027, 1, 1), max_date=date(2026, 12, 31)) is False


class TestTimeValidator:
    """Tests for is_valid_time."""

    def test_time_object_valid(self):
        assert is_valid_time(time(9, 30)) is True

    def test_string_hhmm(self):
        assert is_valid_time("09:30") is True

    def test_string_hhmmss(self):
        assert is_valid_time("09:30:00") is True

    def test_invalid_string(self):
        assert is_valid_time("not-a-time") is False

    def test_non_string_non_time(self):
        assert is_valid_time(1234) is False


class TestDatetimeValidator:
    """Tests for is_valid_datetime."""

    def test_datetime_object_valid(self):
        assert is_valid_datetime(datetime(2026, 1, 15, 9, 30)) is True

    def test_string_iso(self):
        assert is_valid_datetime("2026-01-15 09:30:00") is True

    def test_invalid_string(self):
        assert is_valid_datetime("not-datetime") is False

    def test_non_datetime_non_string_rejected(self):
        assert is_valid_datetime(date(2026, 1, 1)) is False


# ==============================================================================
# U08 — Trading validators TESTS
# ==============================================================================
class TestTradingSymbolValidator:
    """Tests for is_valid_symbol."""

    def test_spy_valid(self):
        assert is_valid_symbol("SPY") is True

    def test_lowercase_invalid(self):
        assert is_valid_symbol("spy") is False

    def test_too_long_invalid(self):
        assert is_valid_symbol("TOOLONG") is False

    def test_numbers_in_equity_symbol_invalid(self):
        assert is_valid_symbol("SP1") is False

    def test_option_symbol_valid(self):
        assert is_valid_symbol("SPY260117C00500000", option=True) is True

    def test_equity_symbol_fails_option_pattern(self):
        assert is_valid_symbol("SPY", option=True) is False

    def test_non_string(self):
        assert is_valid_symbol(123) is False


class TestPriceValidator:
    """Tests for is_valid_price."""

    def test_valid_price(self):
        assert is_valid_price(450.50) is True

    def test_zero_invalid(self):
        assert is_valid_price(0.0) is False

    def test_negative_invalid(self):
        assert is_valid_price(-10.0) is False

    def test_above_max_invalid(self):
        assert is_valid_price(9999999.99) is False

    def test_string_price_valid(self):
        assert is_valid_price("100.00") is True


class TestQuantityValidator:
    """Tests for is_valid_quantity."""

    def test_valid_integer_quantity(self):
        assert is_valid_quantity(100) is True

    def test_zero_invalid(self):
        assert is_valid_quantity(0) is False

    def test_negative_invalid(self):
        assert is_valid_quantity(-5) is False

    def test_fractional_string_rejected_by_default(self):
        # "1.5" raises ValueError in int() — rejected as non-integer
        assert is_valid_quantity("1.5") is False

    def test_fractional_allowed(self):
        assert is_valid_quantity(1.5, allow_fractional=True) is True


class TestOrderTypeValidator:
    """Tests for is_valid_order_type."""

    def test_mkt_valid(self):
        assert is_valid_order_type("MKT") is True

    def test_lmt_valid(self):
        assert is_valid_order_type("LMT") is True

    def test_invalid_type(self):
        assert is_valid_order_type("MARKET") is False

    def test_lowercase_invalid(self):
        assert is_valid_order_type("mkt") is False

    def test_all_valid_types(self):
        for ot in VALID_ORDER_TYPES:
            assert is_valid_order_type(ot) is True


class TestTimeInForceValidator:
    """Tests for is_valid_time_in_force."""

    def test_day_valid(self):
        assert is_valid_time_in_force("DAY") is True

    def test_gtc_valid(self):
        assert is_valid_time_in_force("GTC") is True

    def test_invalid(self):
        assert is_valid_time_in_force("FOREVER") is False

    def test_all_valid_tifs(self):
        for tif in VALID_TIME_IN_FORCE:
            assert is_valid_time_in_force(tif) is True


class TestAccountBalanceValidator:
    """Tests for is_valid_account_balance."""

    def test_positive_valid(self):
        assert is_valid_account_balance(10000.0) is True

    def test_zero_valid(self):
        assert is_valid_account_balance(0.0) is True

    def test_negative_invalid(self):
        assert is_valid_account_balance(-100.0) is False


class TestPercentageValidator:
    """Tests for is_valid_percentage."""

    def test_fifty_valid(self):
        assert is_valid_percentage(50.0) is True

    def test_zero_valid(self):
        assert is_valid_percentage(0.0) is True

    def test_hundred_valid(self):
        assert is_valid_percentage(100.0) is True

    def test_above_hundred_invalid_default(self):
        assert is_valid_percentage(101.0) is False

    def test_custom_min_max(self):
        assert is_valid_percentage(50, min_pct=0.0, max_pct=1.0) is False


# ==============================================================================
# U08 — validate_order_data TESTS
# ==============================================================================
class TestValidateOrderData:
    """Tests for validate_order_data complex validator."""

    def _valid_order(self):
        return {
            "symbol": "SPY",
            "action": "BUY",
            "quantity": 100,
            "order_type": "MKT",
        }

    def test_valid_market_order(self):
        valid, err = validate_order_data(self._valid_order())
        assert valid is True
        assert err is None

    def test_missing_required_field(self):
        order = self._valid_order()
        del order["symbol"]
        valid, err = validate_order_data(order)
        assert valid is False
        assert "Missing" in err

    def test_invalid_symbol(self):
        order = self._valid_order()
        order["symbol"] = "spy"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_invalid_action(self):
        order = self._valid_order()
        order["action"] = "HOLD"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_invalid_quantity(self):
        order = self._valid_order()
        order["quantity"] = -5
        valid, err = validate_order_data(order)
        assert valid is False

    def test_lmt_order_requires_limit_price(self):
        order = self._valid_order()
        order["order_type"] = "LMT"
        valid, err = validate_order_data(order)
        assert valid is False
        assert "limit" in err.lower()

    def test_lmt_order_with_valid_limit_price(self):
        order = self._valid_order()
        order["order_type"] = "LMT"
        order["limit_price"] = 450.0
        valid, err = validate_order_data(order)
        assert valid is True

    def test_stp_order_requires_stop_price(self):
        order = self._valid_order()
        order["order_type"] = "STP"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_invalid_time_in_force(self):
        order = self._valid_order()
        order["time_in_force"] = "FOREVER"
        valid, err = validate_order_data(order)
        assert valid is False

    def test_valid_gtc_time_in_force(self):
        order = self._valid_order()
        order["time_in_force"] = "GTC"
        valid, err = validate_order_data(order)
        assert valid is True


# ==============================================================================
# U08 — validate_position_data TESTS
# ==============================================================================
class TestValidatePositionData:
    """Tests for validate_position_data."""

    def _valid_pos(self):
        return {"symbol": "SPY", "quantity": 100, "entry_price": 450.0}

    def test_valid_position(self):
        valid, err = validate_position_data(self._valid_pos())
        assert valid is True

    def test_missing_symbol(self):
        pos = self._valid_pos()
        del pos["symbol"]
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_invalid_symbol(self):
        pos = self._valid_pos()
        pos["symbol"] = "invalid!"
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_invalid_entry_price(self):
        pos = self._valid_pos()
        pos["entry_price"] = -100.0
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_optional_current_price_valid(self):
        pos = self._valid_pos()
        pos["current_price"] = 460.0
        valid, err = validate_position_data(pos)
        assert valid is True

    def test_optional_current_price_invalid(self):
        pos = self._valid_pos()
        pos["current_price"] = -5.0
        valid, err = validate_position_data(pos)
        assert valid is False

    def test_optional_pnl_valid(self):
        pos = self._valid_pos()
        pos["unrealized_pnl"] = -200.0
        valid, err = validate_position_data(pos)
        assert valid is True


# ==============================================================================
# U08 — validate_config_value TESTS
# ==============================================================================
class TestValidateConfigValue:
    """Tests for validate_config_value."""

    def test_unknown_key_always_valid(self):
        valid, err = validate_config_value("unknown", "any", {})
        assert valid is True

    def test_type_string_pass(self):
        schema = {"key": {"type": "string"}}
        valid, err = validate_config_value("key", "hello", schema)
        assert valid is True

    def test_type_string_fail(self):
        schema = {"key": {"type": "string"}}
        valid, err = validate_config_value("key", 123, schema)
        assert valid is False

    def test_min_constraint(self):
        schema = {"timeout": {"min": 1}}
        valid, err = validate_config_value("timeout", 0, schema)
        assert valid is False

    def test_max_constraint(self):
        schema = {"retries": {"max": 3}}
        valid, err = validate_config_value("retries", 5, schema)
        assert valid is False

    def test_enum_constraint_pass(self):
        schema = {"mode": {"enum": ["live", "paper"]}}
        valid, err = validate_config_value("mode", "live", schema)
        assert valid is True

    def test_enum_constraint_fail(self):
        schema = {"mode": {"enum": ["live", "paper"]}}
        valid, err = validate_config_value("mode", "simulation", schema)
        assert valid is False

    def test_pattern_constraint_pass(self):
        schema = {"symbol": {"pattern": r"^[A-Z]+$"}}
        valid, err = validate_config_value("symbol", "SPY", schema)
        assert valid is True

    def test_pattern_constraint_fail(self):
        schema = {"symbol": {"pattern": r"^[A-Z]+$"}}
        valid, err = validate_config_value("symbol", "spy123", schema)
        assert valid is False


# ==============================================================================
# U08 — sanitize_string TESTS
# ==============================================================================
class TestSanitizeString:
    """Tests for sanitize_string."""

    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"

    def test_max_length_truncates(self):
        assert sanitize_string("hello world", max_length=5) == "hello"

    def test_allowed_chars_filters(self):
        result = sanitize_string("abc123", allowed_chars=r"[a-z]")
        assert result == "abc"

    def test_basic_string_unchanged(self):
        assert sanitize_string("clean") == "clean"


# ==============================================================================
# U08 — DataValidators class TESTS
# ==============================================================================
class TestDataValidators:
    """Tests for DataValidators static class."""

    def test_validate_price_positive(self):
        assert DataValidators.validate_price(100.0) is True

    def test_validate_price_negative(self):
        assert DataValidators.validate_price(-5.0) is False

    def test_validate_quantity_positive(self):
        assert DataValidators.validate_quantity(10) is True

    def test_validate_quantity_zero(self):
        assert DataValidators.validate_quantity(0) is False

    def test_validate_symbol_valid(self):
        assert DataValidators.validate_symbol("SPY") is True

    def test_validate_symbol_empty(self):
        assert DataValidators.validate_symbol("") is False

    def test_validate_date_valid(self):
        assert DataValidators.validate_date("2026-01-15") is True

    def test_validate_date_invalid(self):
        assert DataValidators.validate_date("not-a-date") is False

    def test_validate_percentage_fifty(self):
        assert DataValidators.validate_percentage(50.0) is True

    def test_validate_percentage_over_100(self):
        assert DataValidators.validate_percentage(150.0) is False
