#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: config.py
Purpose: SPYDER - Tradier + Databento Configuration

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    SPYDER - Tradier + Databento Configuration

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
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# TRADIER API CONFIGURATION
# ==============================================================================
TRADIER_CONFIG = {
    "api_key": os.environ.get("TRADIER_API_KEY", ""),
    "account_id": os.environ.get("TRADIER_ACCOUNT_ID", ""),

    # Environment URLs
    "live_url": os.environ.get("TRADIER_LIVE_URL", "https://api.tradier.com/v1"),
    "sandbox_url": os.environ.get("TRADIER_SANDBOX_URL", "https://sandbox.tradier.com/v1"),

    # Connection Settings
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0,

    # Rate Limiting (Tradier has no official limit but be reasonable)
    "requests_per_second": 10,
}

# ==============================================================================
# DATABENTO API CONFIGURATION
# ==============================================================================
DATABENTO_CONFIG = {
    "api_key": os.environ.get("DATABENTO_API_KEY", ""),

    # Dataset for options (OPRA.PILLAR for US equity options)
    "dataset": os.environ.get("DATABENTO_DATASET", "OPRA.PILLAR"),

    # Default schemas for different use cases
    "live_schema": os.environ.get("DATABENTO_LIVE_SCHEMA", "mbp-1"),
    "historical_schema": os.environ.get("DATABENTO_HIST_SCHEMA", "ohlcv-1m"),

    # Subscription Settings
    "subscribe_trades": os.environ.get("DATABENTO_SUBSCRIBE_TRADES", "true").lower() == "true",
    "subscribe_quotes": os.environ.get("DATABENTO_SUBSCRIBE_QUOTES", "true").lower() == "true",

    # Default underlyings (will subscribe to all options for these)
    "default_underlyings": os.environ.get("DATABENTO_UNDERLYINGS", "SPY").split(","),

    # Connection Settings
    "reconnect_delay": 5,
    "max_reconnect_attempts": 10,

    # Cost Controls (Databento charges per GB streamed)
    "max_daily_gb": float(os.environ.get("DATABENTO_MAX_DAILY_GB", "5.0")),
    "warn_gb_threshold": float(os.environ.get("DATABENTO_WARN_GB", "3.0")),
}

# ==============================================================================
# TRADING MODE CONFIGURATION
# ==============================================================================
TRADING_MODE = os.environ.get("TRADING_MODE", "sandbox")  # sandbox, paper, live

# Explicit live trading confirmation (SAFETY FEATURE)
REQUIRE_LIVE_CONFIRMATION = os.environ.get("REQUIRE_LIVE_CONFIRMATION", "true").lower() == "true"

# Provider Selection
DATA_PROVIDER = os.environ.get("DATA_PROVIDER", "databento")  # databento (Tradier quotes for testing)
EXECUTION_PROVIDER = os.environ.get("EXECUTION_PROVIDER", "tradier")  # tradier

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
    # SPY Options Specific Settings
    "spy_options": {
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
        "entry_window": ["09:45", "11:00"],
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
    "db_path": "data/spyder.db",
    "backup_enabled": True,
    "backup_interval_hours": 24,
    "backup_retention_days": 30,
}

LOGGING_CONFIG = {
    "log_level": os.environ.get("LOG_LEVEL", "INFO"),
    "log_to_file": True,
    "log_file_path": "logs/spyder.log",
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
# HELPER FUNCTIONS
# ==============================================================================
def get_active_config():
    """Get configuration for active trading mode"""
    mode = os.environ.get("TRADING_MODE", "sandbox")

    # Safety check for live trading
    if mode == "live" and REQUIRE_LIVE_CONFIRMATION:
        live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
        if not live_confirmed:
            raise ValueError(
                "LIVE TRADING BLOCKED: Set LIVE_TRADING_CONFIRMED=true in .env "
                "after verifying you want to trade with real money."
            )

    # Determine Tradier URL based on mode
    if mode == "live":
        tradier_url = TRADIER_CONFIG["live_url"]
    else:
        tradier_url = TRADIER_CONFIG["sandbox_url"]

    return {
        "mode": mode,
        "execution_provider": EXECUTION_PROVIDER,
        "data_provider": DATA_PROVIDER,
        "tradier_url": tradier_url,
        "tradier_account_id": TRADIER_CONFIG["account_id"],
        "databento_dataset": DATABENTO_CONFIG["dataset"],
        "databento_live_schema": DATABENTO_CONFIG["live_schema"],
        "requires_confirmation": REQUIRE_LIVE_CONFIRMATION if mode == "live" else False,
    }


def validate_config():
    """Validate Tradier + Databento configuration"""
    errors = []

    # Check Tradier configuration
    if not TRADIER_CONFIG["api_key"]:
        errors.append("TRADIER_API_KEY not set in .env")
    if not TRADIER_CONFIG["account_id"]:
        errors.append("TRADIER_ACCOUNT_ID not set in .env")

    # Check market data configuration (Databento)
    if DATA_PROVIDER == "databento":
        if not DATABENTO_CONFIG["api_key"]:
            errors.append("DATABENTO_API_KEY not set in .env")

    # Check trading mode
    mode = os.environ.get("TRADING_MODE", "")
    if mode not in ["sandbox", "paper", "live"]:
        errors.append(f"Invalid TRADING_MODE: {mode}. Must be 'sandbox', 'paper', or 'live'")

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
        - ``TRADIER_API_KEY``  — broker authentication
        - ``TRADIER_ACCOUNT_ID`` — account to trade in
        - ``TRADING_MODE``     — must be ``sandbox``, ``paper``, or ``live``
        - ``DATABENTO_API_KEY`` — market data (required when DATA_PROVIDER=databento)

    Required variables (live mode only):
        - ``LIVE_TRADING_CONFIRMED=true`` — explicit opt-in to real-money trading

    Raises:
        ConfigurationError: If any required variable is absent or invalid.
            The exception message lists every problem found.
    """
    problems: list[str] = []

    # --- Broker credentials (always required) --------------------------------
    if not TRADIER_CONFIG["api_key"]:
        problems.append("TRADIER_API_KEY is not set")
    if not TRADIER_CONFIG["account_id"]:
        problems.append("TRADIER_ACCOUNT_ID is not set")

    # --- Trading mode --------------------------------------------------------
    mode = os.environ.get("TRADING_MODE", "")
    if mode not in ("sandbox", "paper", "live"):
        problems.append(
            f"TRADING_MODE='{mode}' is invalid; must be 'sandbox', 'paper', or 'live'"
        )

    # --- Data-provider credentials -------------------------------------------
    provider = DATA_PROVIDER.lower()
    if provider == "databento":
        if not DATABENTO_CONFIG["api_key"]:
            problems.append("DATABENTO_API_KEY is not set (required when DATA_PROVIDER=databento)")
    else:
        problems.append(
            f"DATA_PROVIDER='{DATA_PROVIDER}' is invalid; must be 'databento'"
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
            f"Spyder startup blocked — {len(problems)} configuration "
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
        "SPYDER Configuration loaded — execution: Tradier, "
        "market data: %s, trading mode: %s",
        DATA_PROVIDER.capitalize(),
        TRADING_MODE,
    )

if __name__ == "__main__":
    # Test the configuration when run directly
    print("Testing Configuration...")

    status = check_api_authentication()
    print(f"Authentication Status: {status['status']}")
    print(f"Mode: {status['mode']}")
    print(f"Execution Provider: {status['execution_provider']}")
    print(f"Data Provider: {status['data_provider']}")
    print(f"Message: {status['message']}")

    if status["authenticated"]:
        print("[OK] Configuration is valid and ready for use")
    else:
        print("[FAIL] Configuration errors found - check .env file")
