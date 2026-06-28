#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovX_Unknown
Module: config.py
Purpose: TRADOV - Tradier + Massive Configuration

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    TRADOV - Tradier + Massive Configuration

Change Log:
    2026-03-03:
        - Added ConfigurationError exception class
        - Added validate_startup_config() for fail-fast startup validation
        - Replaced print() calls with stdlib logging
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
from pathlib import Path


_LIVE_ONLY_TRADING_MODES = {"paper", "live"}
_LIVE_ONLY_TRADIER_ENVS = {"live", "production"}
_TRUTHY_ENV_TOKENS = {"1", "true", "yes", "on"}
_TRADIER_ENVIRONMENT_ERROR = (
    "Tradov runs Tradier in live-only mode; paper trading uses the internal "
    "TradovBox ledger, not Tradier sandbox."
)


def _read_tradier_live_token() -> str:
    return os.environ.get("TRADIER_LIVE_API_KEY", "")


def _read_tradier_live_account_id() -> str:
    return (
        os.environ.get("TRADIER_LIVE_ACCOUNT_ID")
        or os.environ.get("TRADIER_ACCOUNT_ID", "")
    )


def _is_truthy_env(raw_value: str | None) -> bool:
    """Return ``True`` when an env-var string is an enabled/true token."""
    return str(raw_value or "").strip().lower() in _TRUTHY_ENV_TOKENS

# ==============================================================================
# EXCEPTIONS
# ==============================================================================


class ConfigurationError(RuntimeError):
    """
    Raised when required configuration is missing or invalid at startup.

    Collects ALL missing/invalid items and reports them together so the
    operator can fix everything in one shot rather than discovering problems
    one-at-a-time.
    """

    pass

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local-dev convenience
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


def _load_env_file_fallback(dotenv_path: Path, override: bool = True) -> bool:
    """Load a simple ``.env`` file without depending on python-dotenv."""
    if not dotenv_path.exists():
        return False

    loaded = False
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if "#" in value:
            before_hash, _hash, after_hash = value.partition("#")
            if before_hash.rstrip() != value:
                value = before_hash.rstrip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value
        loaded = True

    return loaded


_DOTENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if not load_dotenv(dotenv_path=_DOTENV_PATH, override=True):
    _load_env_file_fallback(_DOTENV_PATH, override=True)

# ==============================================================================
# TRADIER API CONFIGURATION
# ==============================================================================
TRADIER_CONFIG = {
    # Canonical live Tradier credentials.
    "api_key": _read_tradier_live_token(),
    "account_id": _read_tradier_live_account_id(),

    # Live / production credentials (api.tradier.com)
    "live_api_key": _read_tradier_live_token(),
    "live_account_id": _read_tradier_live_account_id(),

    # Environment URLs
    "live_url": os.environ.get("TRADIER_LIVE_URL", "https://api.tradier.com/v1"),

    # Connection Settings
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0,

    # Rate Limiting (Tradier has no official limit but be reasonable)
    "requests_per_second": 10,
}

# ==============================================================================
# TRADING MODE CONFIGURATION
# ==============================================================================
TRADING_MODE = os.environ.get("TRADING_MODE", "paper")  # paper, live

# Explicit live trading confirmation (SAFETY FEATURE)
REQUIRE_LIVE_CONFIRMATION = os.environ.get("REQUIRE_LIVE_CONFIRMATION", "true").lower() == "true"

# Provider Selection
DATA_PROVIDER = os.environ.get("DATA_PROVIDER", "tradier")  # tradier
ACTIVE_DATA_PROVIDER = os.environ.get("ACTIVE_DATA_PROVIDER", DATA_PROVIDER)  # overrides DATA_PROVIDER
EXECUTION_PROVIDER = os.environ.get("EXECUTION_PROVIDER", "tradier")  # tradier

# Pair-trading cap used as the system-wide upper bound for open pair trades.
PAIR_TRADING_MAX_OPEN = 3

# Tradier API environment — always live/production. Paper mode uses live
# market data while keeping fills inside the local TradovBox paper ledger.
_trading_mode_norm = str(TRADING_MODE).strip().lower()
_tradier_env_default = "live"
TRADIER_ENVIRONMENT = os.environ.get("TRADIER_ENVIRONMENT", _tradier_env_default)
TRADIER_MARKET_DATA_ENVIRONMENT = os.environ.get(
    "TRADIER_MARKET_DATA_ENVIRONMENT",
    TRADIER_ENVIRONMENT,
)

# ==============================================================================
# TRADING CONFIGURATION
# ==============================================================================
TRADING_CONFIG = {
    # Position Limits
    "risk_limits": {
        "max_position_size": 10000,
        "max_contracts_per_trade": 10,
        "max_daily_loss": 500,
        "max_daily_trades": 20,
        "max_open_positions": 5,
    },
    # Trading Hours (Eastern Time)
    "trading_hours": {
        "pre_market_start": "08:00",
        "market_open": "09:30",
        "market_close": "16:00",
        "after_hours_end": "17:00",
        "timezone": "US/Eastern",
    },
    # SPX/SPXW Options Settings
    "spx_options": {
        "default_option_root": "SPXW",
        "monthly_option_root": "SPX",
        "min_days_to_expiry": 0,
        "max_days_to_expiry": 45,
        "min_option_volume": 100,
        "min_open_interest": 50,
        "strike_range_percent": 2.0,
        "preferred_expiries": ["0DTE", "1DTE", "Weekly", "Monthly"],
    },
    # Strategy Selection
    "active_strategies": [
        "iron_condor",
        "credit_spread",
        "zero_dte_scalping",
    ],
    # Execution Settings
    "execution": {
        "order_type": "limit",
        "price_offset_ticks": 1,
        "max_slippage_percent": 0.5,
        "fill_wait_seconds": 30,
    },
    # Risk Management
    "risk_management": {
        "stop_loss_percent": 50,
        "profit_target_percent": 25,
        "trailing_stop_percent": 10,
        "max_loss_per_trade": 200,
        "use_portfolio_hedging": True,
    },
    # Notifications
    "notifications": {
        "telegram_alerts": bool(os.environ.get("TELEGRAM_BOT_TOKEN", "")),
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        "email_alerts": bool(os.environ.get("EMAIL_ADDRESS", "")),
        "email_address": os.environ.get("EMAIL_ADDRESS", ""),
        "email_password": os.environ.get("EMAIL_PASSWORD", ""),
        "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        # Standard alerts
        "alert_on_trade_fill": True,
        "alert_on_stop_loss": True,
        "alert_on_daily_summary": True,
        "alert_on_errors": True,
        "alert_on_large_moves": True,
    },
}

# Backward compatibility for modules still reading legacy key names.
TRADING_CONFIG["spy_options"] = TRADING_CONFIG["spx_options"]

# ==============================================================================
# STRATEGY CONFIGURATIONS
# ==============================================================================
STRATEGY_CONFIG = {
    "iron_condor": {
        "enabled": True,
        "delta_short": 0.15,
        "delta_long": 0.05,
        "min_credit": 0.30,
        "days_to_expiry": [0, 1, 2],
        "entry_time": "10:00",
        "exit_time": "15:30",
        "max_loss_percent": 200,
    },
    "credit_spread": {
        "enabled": True,
        "spread_width": 5,
        "delta_short": 0.20,
        "min_credit": 0.25,
        "trade_direction": "both",
        "entry_conditions": {
            "min_iv_rank": 30,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        },
    },
    "zero_dte_scalping": {
        "enabled": True,
        "entry_window": ["10:15", "11:30"],
        "scalp_target": 0.10,
        "max_contracts": 5,
        "momentum_period": 5,
        "min_volume": 500,
        "use_limit_orders": True,
    },
}

# ==============================================================================
# DATABASE AND LOGGING
# ==============================================================================
DATABASE_CONFIG = {
    "db_path": "data/tradov.db",
    "backup_enabled": True,
    "backup_interval_hours": 24,
    "backup_retention_days": 30,
}

LOGGING_CONFIG = {
    "log_level": os.environ.get("LOG_LEVEL", "INFO"),
    "log_to_file": True,
    "log_file_path": "logs/tradov.log",
    "log_rotation": "daily",
    "log_retention_days": 30,
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

SYSTEM_CONFIG = {
    "mode": (
        "production"
        if os.environ.get("DEBUG_MODE", "False").lower() == "false"
        else "development"
    ),
    "debug": os.environ.get("DEBUG_MODE", "False").lower() == "true",
    "performance_monitoring": True,
    "health_check_interval": 300,
    "auto_restart_on_error": True,
    "max_memory_usage_mb": 1024,
}

# ==============================================================================
# SCHEDULER CONFIGURATION
# ==============================================================================
SCHEDULER_CONFIG = {
    # How often (minutes) to emit a data_update_request event during market hours.
    "data_update_interval_minutes": int(os.environ.get("SCHEDULER_DATA_UPDATE_INTERVAL", "5")),
    # How often (minutes) to emit a periodic_risk_check event during market hours.
    "risk_check_interval_minutes": int(os.environ.get("SCHEDULER_RISK_CHECK_INTERVAL", "15")),
}


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def get_active_config():
    """Get configuration for active trading mode"""
    mode = str(os.environ.get("TRADING_MODE", "paper")).strip().lower()

    if mode not in _LIVE_ONLY_TRADING_MODES:
        raise ConfigurationError(
            f"TRADING_MODE='{mode}' is invalid; must be 'paper' or 'live'. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    # Safety check for live trading
    if mode == "live" and REQUIRE_LIVE_CONFIRMATION:
        live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
        if not live_confirmed:
            raise ConfigurationError(
                "LIVE TRADING BLOCKED: Set LIVE_TRADING_CONFIRMED=true in .env "
                "after verifying you want to trade with real money."
            )

    tradier_env = str(os.environ.get("TRADIER_ENVIRONMENT", TRADIER_ENVIRONMENT)).strip().lower()
    if tradier_env not in _LIVE_ONLY_TRADIER_ENVS:
        raise ConfigurationError(
            f"TRADIER_ENVIRONMENT='{tradier_env}' is invalid; must be 'live' or "
            f"'production'. {_TRADIER_ENVIRONMENT_ERROR}"
        )

    market_data_env = str(
        os.environ.get(
            "TRADIER_MARKET_DATA_ENVIRONMENT",
            TRADIER_MARKET_DATA_ENVIRONMENT,
        )
    ).strip().lower()
    if market_data_env not in _LIVE_ONLY_TRADIER_ENVS:
        raise ConfigurationError(
            "TRADIER_MARKET_DATA_ENVIRONMENT must be 'live' or 'production'. "
            f"Got '{market_data_env}'. {_TRADIER_ENVIRONMENT_ERROR}"
        )
    if _is_truthy_env(os.environ.get("TRADOV_ALLOW_SANDBOX_MARKET_DATA")):
        raise ConfigurationError(
            "TRADOV_ALLOW_SANDBOX_MARKET_DATA is not permitted. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    tradier_url = TRADIER_CONFIG["live_url"]

    return {
        "mode": mode,
        "execution_provider": EXECUTION_PROVIDER,
        "data_provider": DATA_PROVIDER,
        "tradier_url": tradier_url,
        "tradier_account_id": TRADIER_CONFIG["account_id"],
        "market_data_dataset": "tradier-live",
        "market_data_schema": "tradier-quote",
        "requires_confirmation": REQUIRE_LIVE_CONFIRMATION if mode == "live" else False,
    }


def validate_config():
    """Validate Tradier configuration"""
    errors = []

    # Check Tradier configuration
    if not TRADIER_CONFIG["api_key"]:
        errors.append("TRADIER_LIVE_API_KEY not set in .env")
    if not TRADIER_CONFIG["account_id"]:
        errors.append("TRADIER_LIVE_ACCOUNT_ID or TRADIER_ACCOUNT_ID not set in .env")

    # Check trading mode
    mode = str(os.environ.get("TRADING_MODE", "")).strip().lower()
    if mode not in _LIVE_ONLY_TRADING_MODES:
        errors.append(
            f"Invalid TRADING_MODE: {mode}. Must be 'paper' or 'live'. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    tradier_env = str(os.environ.get("TRADIER_ENVIRONMENT", TRADIER_ENVIRONMENT)).strip().lower()
    if tradier_env not in _LIVE_ONLY_TRADIER_ENVS:
        errors.append(
            f"TRADIER_ENVIRONMENT='{tradier_env}' is invalid. Must be 'live' or "
            f"'production'. {_TRADIER_ENVIRONMENT_ERROR}"
        )

    market_data_env = str(
        os.environ.get(
            "TRADIER_MARKET_DATA_ENVIRONMENT",
            TRADIER_MARKET_DATA_ENVIRONMENT,
        )
    ).strip().lower()
    if market_data_env not in _LIVE_ONLY_TRADIER_ENVS:
        errors.append(
            "TRADIER_MARKET_DATA_ENVIRONMENT="
            f"'{market_data_env}' is invalid. Must be 'live' or 'production'. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    if _is_truthy_env(os.environ.get("TRADOV_ALLOW_SANDBOX_MARKET_DATA")):
        errors.append(
            "TRADOV_ALLOW_SANDBOX_MARKET_DATA must be unset or false. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    if errors:
        return False, "\n".join(["Configuration errors:"] + [f"  - {e}" for e in errors])

    return True, f"Configuration valid (mode: {mode})"


def validate_startup_config() -> None:
    """
    Fail-fast startup configuration validator.

    Checks every required environment variable in a single pass and raises
    :class:`ConfigurationError` with a complete list of all problems so the
    operator can fix them all at once.

    Required variables (always):
        - ``TRADIER_LIVE_API_KEY``  — broker authentication
        - ``TRADIER_ACCOUNT_ID``    — account to trade in
        - ``TRADING_MODE``          — must be ``paper`` or ``live``
        - ``TRADIER_ENVIRONMENT``   — ``live`` or ``production``
        - ``TRADIER_MARKET_DATA_ENVIRONMENT`` — ``live`` or ``production``
    Required variables (live mode only):
        - ``LIVE_TRADING_CONFIRMED=true`` — explicit opt-in to real-money trading

    Raises:
        ConfigurationError: If any required variable is absent or invalid.
            The exception message lists every problem found.
    """
    problems: list[str] = []

    # --- Broker credentials (always required) --------------------------------
    if not TRADIER_CONFIG["api_key"]:
        problems.append("TRADIER_LIVE_API_KEY is not set")
    if not TRADIER_CONFIG["account_id"]:
        problems.append("TRADIER_LIVE_ACCOUNT_ID or TRADIER_ACCOUNT_ID is not set")

    # --- Trading mode --------------------------------------------------------
    mode = str(os.environ.get("TRADING_MODE", "")).strip().lower()
    if mode not in _LIVE_ONLY_TRADING_MODES:
        problems.append(
            f"TRADING_MODE='{mode}' is invalid; must be 'paper' or 'live'. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    broker_env = str(os.environ.get("TRADIER_ENVIRONMENT", TRADIER_ENVIRONMENT)).strip().lower()
    if broker_env not in _LIVE_ONLY_TRADIER_ENVS:
        problems.append(
            f"TRADIER_ENVIRONMENT='{broker_env}' is invalid; must be 'live' or "
            f"'production'. {_TRADIER_ENVIRONMENT_ERROR}"
        )

    market_data_env = str(
        os.environ.get(
            "TRADIER_MARKET_DATA_ENVIRONMENT",
            TRADIER_MARKET_DATA_ENVIRONMENT,
        )
    ).strip().lower()
    if market_data_env not in _LIVE_ONLY_TRADIER_ENVS:
        problems.append(
            "TRADIER_MARKET_DATA_ENVIRONMENT="
            f"'{market_data_env}' is invalid; must be 'live' or 'production'. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    if _is_truthy_env(os.environ.get("TRADOV_ALLOW_SANDBOX_MARKET_DATA")):
        problems.append(
            "TRADOV_ALLOW_SANDBOX_MARKET_DATA must be unset or false. "
            f"{_TRADIER_ENVIRONMENT_ERROR}"
        )

    # --- Live-trading safety gate --------------------------------------------
    if mode == "live":
        confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
        if not confirmed:
            problems.append(
                "LIVE_TRADING_CONFIRMED is not 'true' — set it explicitly to enable "
                "real-money trading (TRADING_MODE=live)"
            )

    if problems:
        bullet_list = "\n".join(f"  • {p}" for p in problems)
        raise ConfigurationError(
            f"Tradov startup blocked — {len(problems)} configuration "
            f"problem(s) found:\n{bullet_list}\n"
            "Fix the issues above in your .env file and restart."
        )


def check_api_authentication():
    """Check if API authentication is properly configured"""
    try:
        config = get_active_config()
        is_valid, message = validate_config()

        return {
            "authenticated": is_valid,
            "mode": config["mode"],
            "execution_provider": config["execution_provider"],
            "data_provider": config["data_provider"],
            "status": "ready" if is_valid else "configuration_error",
            "message": message,
        }
    except Exception as e:
        return {
            "authenticated": False,
            "mode": "unknown",
            "execution_provider": EXECUTION_PROVIDER,
            "data_provider": DATA_PROVIDER,
            "status": "error",
            "message": f"Configuration check failed: {str(e)}",
        }


# Log configuration status on import (never use print() in production code)
_cfg_logger = logging.getLogger(__name__)
if __name__ != "__main__":
    _cfg_logger.debug(
        "TRADOV Configuration loaded — execution: Tradier, "
        "market data: %s, trading mode: %s",
        DATA_PROVIDER.capitalize(),
        TRADING_MODE,
    )

if __name__ == "__main__":
    # Test the configuration when run directly
    _cfg_logger.info("Testing Configuration...")

    status = check_api_authentication()
    _cfg_logger.info(f"Authentication Status: {status['status']}")
    _cfg_logger.info(f"Mode: {status['mode']}")
    _cfg_logger.info(f"Execution Provider: {status['execution_provider']}")
    _cfg_logger.info(f"Data Provider: {status['data_provider']}")
    _cfg_logger.info(f"Message: {status['message']}")

    if status["authenticated"]:
        _cfg_logger.info("[OK] Configuration is valid and ready for use")
    else:
        _cfg_logger.error("[FAIL] Configuration errors found - check .env file")
