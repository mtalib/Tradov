#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: Tradov.TradovU_Utilities
Module: TradovU08_Validators.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import re
from datetime import date, datetime, time
from typing import Any
from collections.abc import Callable

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================

EMAIL_PATTERN = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
PHONE_PATTERN = r"^\+?1?\d{10,15}$"
SYMBOL_PATTERN = r"^[A-Z]{1,5}$"
OPTION_SYMBOL_PATTERN = r"^[A-Z]{1,5}\d{6}[CP]\d{8}$"
IP_PATTERN = (
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)
URL_PATTERN = r"^https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)$"

# Trading constraints
MIN_PRICE = 0.01
MAX_PRICE = 999999.99
MIN_QUANTITY = 1
MAX_QUANTITY = 999999
MIN_ACCOUNT_BALANCE = 0.0
MAX_LEVERAGE = 4.0
VALID_ORDER_TYPES = ["MKT", "LMT", "STP", "STP_LMT", "TRAIL", "TRAIL_LMT"]
VALID_TIME_IN_FORCE = ["DAY", "GTC", "IOC", "FOK", "GTD", "OPG", "DTC"]

# ==============================================================================
# VALIDATION ERROR CLASS
# ==============================================================================


class ValidationError(Exception):
    """Custom validation error"""

    def __init__(self, field: str, value: Any, message: str):
        self.field = field
        self.value = value
        self.message = message
        super().__init__(f"Validation error for '{field}': {message}")


# ==============================================================================
# BASIC TYPE VALIDATORS
# ==============================================================================


def is_valid_string(
    value: Any, min_length: int = 0, max_length: int | None = None, allow_empty: bool = False
) -> bool:
    """
    Validate string value.

    Args:
        value: Value to validate
        min_length: Minimum length
        max_length: Maximum length
        allow_empty: Allow empty strings

    Returns:
        True if valid
    """
    if not isinstance(value, str):
        return False

    if not allow_empty and not value:
        return False

    if len(value) < min_length:
        return False

    return not (max_length is not None and len(value) > max_length)


def is_valid_number(
    value: Any,
    min_value: float | None = None,
    max_value: float | None = None,
    allow_negative: bool = True,
    allow_zero: bool = True,
) -> bool:
    """
    Validate numeric value.

    Args:
        value: Value to validate
        min_value: Minimum value
        max_value: Maximum value
        allow_negative: Allow negative values
        allow_zero: Allow zero

    Returns:
        True if valid
    """
    try:
        num = float(value)

        if not allow_negative and num < 0:
            return False

        if not allow_zero and num == 0:
            return False

        if min_value is not None and num < min_value:
            return False

        return not (max_value is not None and num > max_value)

    except (TypeError, ValueError):
        return False


def is_valid_integer(
    value: Any, min_value: int | None = None, max_value: int | None = None
) -> bool:
    """
    Validate integer value.

    Args:
        value: Value to validate
        min_value: Minimum value
        max_value: Maximum value

    Returns:
        True if valid
    """
    try:
        if isinstance(value, bool):
            return False

        num = int(value)

        if min_value is not None and num < min_value:
            return False

        return not (max_value is not None and num > max_value)

    except (TypeError, ValueError):
        return False


def is_valid_boolean(value: Any) -> bool:
    """
    Validate boolean value.

    Args:
        value: Value to validate

    Returns:
        True if valid
    """
    return isinstance(value, bool)


def is_valid_list(
    value: Any,
    min_length: int = 0,
    max_length: int | None = None,
    item_validator: Callable | None = None,
) -> bool:
    """
    Validate list value.

    Args:
        value: Value to validate
        min_length: Minimum length
        max_length: Maximum length
        item_validator: Optional validator for items

    Returns:
        True if valid
    """
    if not isinstance(value, list):
        return False

    if len(value) < min_length:
        return False

    if max_length is not None and len(value) > max_length:
        return False

    if item_validator:
        return all(item_validator(item) for item in value)

    return True


def is_valid_dict(
    value: Any, required_keys: list[str] | None = None, optional_keys: list[str] | None = None
) -> bool:
    """
    Validate dictionary value.

    Args:
        value: Value to validate
        required_keys: Required dictionary keys
        optional_keys: Optional dictionary keys

    Returns:
        True if valid
    """
    if not isinstance(value, dict):
        return False

    if required_keys:
        for key in required_keys:
            if key not in value:
                return False

    if required_keys is not None and optional_keys is not None:
        allowed_keys = set(required_keys) | set(optional_keys)
        for key in value:
            if key not in allowed_keys:
                return False

    return True


# ==============================================================================
# PATTERN VALIDATORS
# ==============================================================================


def is_valid_email(value: Any) -> bool:
    """
    Validate email address.

    Args:
        value: Email to validate

    Returns:
        True if valid
    """
    if not isinstance(value, str):
        return False

    return bool(re.match(EMAIL_PATTERN, value))


def is_valid_phone(value: Any) -> bool:
    """
    Validate phone number.

    Args:
        value: Phone number to validate

    Returns:
        True if valid
    """
    if not isinstance(value, str):
        return False

    # Remove common formatting characters
    cleaned = re.sub(r"[\s\-\(\)]", "", value)

    return bool(re.match(PHONE_PATTERN, cleaned))


def is_valid_ip_address(value: Any) -> bool:
    """
    Validate IP address.

    Args:
        value: IP address to validate

    Returns:
        True if valid
    """
    if not isinstance(value, str):
        return False

    return bool(re.match(IP_PATTERN, value))


def is_valid_url(value: Any) -> bool:
    """
    Validate URL.

    Args:
        value: URL to validate

    Returns:
        True if valid
    """
    if not isinstance(value, str):
        return False

    return bool(re.match(URL_PATTERN, value))


# ==============================================================================
# DATE/TIME VALIDATORS
# ==============================================================================


def is_valid_date(
    value: Any, min_date: date | None = None, max_date: date | None = None
) -> bool:
    """
    Validate date value.

    Args:
        value: Date to validate
        min_date: Minimum date
        max_date: Maximum date

    Returns:
        True if valid
    """
    if isinstance(value, str):
        try:
            # Try common date formats
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    value = datetime.strptime(value, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                return False
        except Exception:
            return False

    if not isinstance(value, date):
        return False

    if min_date and value < min_date:
        return False

    return not (max_date and value > max_date)


def is_valid_time(value: Any) -> bool:
    """
    Validate time value.

    Args:
        value: Time to validate

    Returns:
        True if valid
    """
    if isinstance(value, str):
        try:
            # Try common time formats
            for fmt in ["%H:%M:%S", "%H:%M", "%I:%M %p"]:
                try:
                    datetime.strptime(value, fmt).time()
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False

    return isinstance(value, time)


def is_valid_datetime(
    value: Any, min_dt: datetime | None = None, max_dt: datetime | None = None
) -> bool:
    """
    Validate datetime value.

    Args:
        value: Datetime to validate
        min_dt: Minimum datetime
        max_dt: Maximum datetime

    Returns:
        True if valid
    """
    if isinstance(value, str):
        try:
            value = pd.to_datetime(value)
        except Exception:
            return False

    if not isinstance(value, datetime):
        return False

    if min_dt and value < min_dt:
        return False

    return not (max_dt and value > max_dt)


# ==============================================================================
# TRADING-SPECIFIC VALIDATORS
# ==============================================================================


def is_valid_symbol(value: Any, option: bool = False) -> bool:
    """
    Validate trading symbol.

    Args:
        value: Symbol to validate
        option: True for option symbols

    Returns:
        True if valid
    """
    if not isinstance(value, str):
        return False

    if option:
        return bool(re.match(OPTION_SYMBOL_PATTERN, value))
    else:
        return bool(re.match(SYMBOL_PATTERN, value))


def is_valid_price(value: Any, min_price: float = MIN_PRICE, max_price: float = MAX_PRICE) -> bool:
    """
    Validate price value.

    Args:
        value: Price to validate
        min_price: Minimum price
        max_price: Maximum price

    Returns:
        True if valid
    """
    return is_valid_number(value, min_price, max_price, allow_negative=False)


def is_valid_quantity(value: Any, allow_fractional: bool = False) -> bool:
    """
    Validate quantity value.

    Args:
        value: Quantity to validate
        allow_fractional: Allow fractional quantities

    Returns:
        True if valid
    """
    if allow_fractional:
        return is_valid_number(
            value, MIN_QUANTITY, MAX_QUANTITY, allow_negative=False, allow_zero=False
        )
    else:
        return is_valid_integer(value, MIN_QUANTITY, MAX_QUANTITY)


def is_valid_order_type(value: Any) -> bool:
    """
    Validate order type.

    Args:
        value: Order type to validate

    Returns:
        True if valid
    """
    return value in VALID_ORDER_TYPES


def is_valid_time_in_force(value: Any) -> bool:
    """
    Validate time in force.

    Args:
        value: Time in force to validate

    Returns:
        True if valid
    """
    return value in VALID_TIME_IN_FORCE


def is_valid_account_balance(value: Any) -> bool:
    """
    Validate account balance.

    Args:
        value: Balance to validate

    Returns:
        True if valid
    """
    return is_valid_number(value, MIN_ACCOUNT_BALANCE, allow_negative=False)


def is_valid_percentage(value: Any, min_pct: float = 0.0, max_pct: float = 100.0) -> bool:
    """
    Validate percentage value.

    Args:
        value: Percentage to validate
        min_pct: Minimum percentage
        max_pct: Maximum percentage

    Returns:
        True if valid
    """
    return is_valid_number(value, min_pct, max_pct)


# ==============================================================================
# COMPLEX VALIDATORS
# ==============================================================================


def validate_order_data(order_data: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate complete order data.

    Args:
        order_data: Order data dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["symbol", "action", "quantity", "order_type"]

    # Check required fields
    for field in required_fields:
        if field not in order_data:
            return False, f"Missing required field: {field}"

    # Validate symbol
    if not is_valid_symbol(order_data["symbol"]):
        return False, "Invalid symbol"

    # Validate action
    if order_data["action"] not in ["BUY", "SELL"]:
        return False, "Invalid action (must be BUY or SELL)"

    # Validate quantity
    if not is_valid_quantity(order_data["quantity"]):
        return False, "Invalid quantity"

    # Validate order type
    if not is_valid_order_type(order_data["order_type"]):
        return False, f"Invalid order type: {order_data['order_type']}"

    # Validate limit price if present
    if order_data["order_type"] in ["LMT", "STP_LMT", "TRAIL_LMT"]:
        if "limit_price" not in order_data:
            return False, f"Limit price required for {order_data['order_type']} orders"
        if not is_valid_price(order_data["limit_price"]):
            return False, "Invalid limit price"

    # Validate stop price if present
    if order_data["order_type"] in ["STP", "STP_LMT"]:
        if "stop_price" not in order_data:
            return False, f"Stop price required for {order_data['order_type']} orders"
        if not is_valid_price(order_data["stop_price"]):
            return False, "Invalid stop price"

    # Validate time in force if present
    if "time_in_force" in order_data:
        if not is_valid_time_in_force(order_data["time_in_force"]):
            return False, "Invalid time in force"

    return True, None


def validate_position_data(position_data: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate position data.

    Args:
        position_data: Position data dictionary

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["symbol", "quantity", "entry_price"]

    # Check required fields
    for field in required_fields:
        if field not in position_data:
            return False, f"Missing required field: {field}"

    # Validate symbol
    if not is_valid_symbol(position_data["symbol"]):
        return False, "Invalid symbol"

    # Validate quantity
    if not is_valid_integer(position_data["quantity"]):
        return False, "Invalid quantity"

    # Validate entry price
    if not is_valid_price(position_data["entry_price"]):
        return False, "Invalid entry price"

    # Validate current price if present
    if "current_price" in position_data:
        if not is_valid_price(position_data["current_price"]):
            return False, "Invalid current price"

    # Validate P&L if present
    if "unrealized_pnl" in position_data:
        if not is_valid_number(position_data["unrealized_pnl"]):
            return False, "Invalid unrealized P&L"

    return True, None


def validate_config_value(
    key: str, value: Any, schema: dict[str, Any]
) -> tuple[bool, str | None]:
    """
    Validate configuration value against schema.

    Args:
        key: Configuration key
        value: Configuration value
        schema: Validation schema

    Returns:
        Tuple of (is_valid, error_message)
    """
    if key not in schema:
        return True, None  # No schema, assume valid

    rules = schema[key]

    # Check type
    expected_type = rules.get("type")
    if expected_type:
        if expected_type == "string" and not isinstance(value, str):
            return False, f"{key} must be a string"
        elif expected_type == "number" and not isinstance(value, (int, float)):
            return False, f"{key} must be a number"
        elif expected_type == "integer" and not isinstance(value, int):
            return False, f"{key} must be an integer"
        elif expected_type == "boolean" and not isinstance(value, bool):
            return False, f"{key} must be a boolean"
        elif expected_type == "list" and not isinstance(value, list):
            return False, f"{key} must be a list"
        elif expected_type == "dict" and not isinstance(value, dict):
            return False, f"{key} must be a dictionary"

    # Check constraints
    if "min" in rules and value < rules["min"]:
        return False, f"{key} must be at least {rules['min']}"

    if "max" in rules and value > rules["max"]:
        return False, f"{key} must be at most {rules['max']}"

    if "enum" in rules and value not in rules["enum"]:
        return False, f"{key} must be one of: {rules['enum']}"

    if "pattern" in rules and isinstance(value, str):
        if not re.match(rules["pattern"], value):
            return False, f"{key} does not match required pattern"

    return True, None


# ==============================================================================
# SANITIZATION FUNCTIONS
# ==============================================================================


def sanitize_string(
    value: str, max_length: int | None = None, allowed_chars: str | None = None
) -> str:
    """
    Sanitize string input.

    Args:
        value: String to sanitize
        max_length: Maximum length
        allowed_chars: Allowed characters pattern

    Returns:
        Sanitized string
    """
    # Strip whitespace
    value = value.strip()

    # Limit length
    if max_length:
        value = value[:max_length]

    # Filter characters
    if allowed_chars:
        value = "".join(c for c in value if re.match(allowed_chars, c))

    return value


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename.

    Args:
        filename: Filename to sanitize

    Returns:
        Sanitized filename
    """
    # Remove path components
    filename = os.path.basename(filename)

    # Replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > 200:
        name = name[:200]

    return name + ext


# ==============================================================================
# VALIDATION DECORATORS
# ==============================================================================


def validate_input(**validators):
    """
    Decorator for input validation.

    Usage:
        @validate_input(price=is_valid_price, quantity=is_valid_quantity)
        def place_order(price, quantity):
            ...
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get function signature
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each parameter
            for param, validator in validators.items():
                if param in bound.arguments:
                    value = bound.arguments[param]
                    if not validator(value):
                        raise ValidationError(param, value, f"Invalid {param}: {value}")

            return func(*args, **kwargs)

        return wrapper

    return decorator


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================


# ==============================================================================
# DATA VALIDATORS CLASS
# ==============================================================================
class DataValidators:
    """
    Data validation utilities class.

    This class provides various data validation methods for the trading system.
    """

    @staticmethod
    def validate_price(price: float) -> bool:
        """Validate a price value."""
        return isinstance(price, (int, float)) and price > 0

    @staticmethod
    def validate_quantity(quantity: int) -> bool:
        """Validate a quantity value."""
        return isinstance(quantity, int) and quantity > 0

    @staticmethod
    def validate_symbol(symbol: str) -> bool:
        """Validate a trading symbol."""
        return isinstance(symbol, str) and len(symbol) > 0 and symbol.isalpha()

    @staticmethod
    def validate_date(date_str: str) -> bool:
        """Validate a date string."""
        try:
            from datetime import datetime

            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except Exception:
            return False

    @staticmethod
    def validate_percentage(value: float) -> bool:
        """Validate a percentage value (0-100)."""
        return isinstance(value, (int, float)) and 0 <= value <= 100


__all__ = ["DataValidators"]
if __name__ == "__main__":
    # Test validators

    # Test basic validators

    # Test pattern validators

    # Test complex validators
    order = {
        "symbol": "TRAD",
        "action": "BUY",
        "quantity": 100,
        "order_type": "LMT",
        "limit_price": 450.50,
    }

    valid, error = validate_order_data(order)
    if error:
        pass

    # Test sanitization

# ==============================================================================
# BACKWARDS COMPATIBILITY ALIASES
# ==============================================================================
# Alias for modules expecting 'Validators' class name
Validators = DataValidators

# Additional exports for compatibility
__all__ = [
    "DataValidators",
    "Validators",  # Alias
    "validate_order_data",
    "validate_position_data",
    "is_valid_string",
    "is_valid_integer",
    "is_valid_boolean",
    "is_valid_date",
    "is_valid_time",
    "is_valid_datetime",
    "is_valid_email",
    "is_valid_phone",
    "is_valid_url",
    "is_valid_ip_address",
    "is_valid_symbol",
    "is_valid_number",
    "is_valid_price",
    "is_valid_quantity",
    "is_valid_percentage",
    "is_valid_order_type",
    "is_valid_time_in_force",
    "sanitize_string",
    "sanitize_filename",
    "validate_input",
    "ValidationError",
]
