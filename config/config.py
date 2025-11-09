#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - IBKR Web API Configuration
OAuth 2.0 authentication with private_key_jwt (RFC 7521/7523)
See: https://www.interactivebrokers.com/campus/ibkr-api-page/web-api/
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==============================================================================
# IBKR WEB API CONFIGURATION (OAuth 2.0)
# ==============================================================================
IBKR_WEB_API_CONFIG = {
    "connection_type": "web_api",  # REST + WebSocket
    "api_base_url": os.environ.get("IBKR_API_BASE_URL", "https://api.ibkr.com/v1/api"),
    "auth_method": os.environ.get("IBKR_AUTH_METHOD", "oauth2"),  # OAuth 2.0 only

    # OAuth 2.0 Configuration (private_key_jwt)
    "oauth": {
        "token_url": os.environ.get("IBKR_OAUTH_TOKEN_URL", "https://api.ibkr.com/v1/oauth2/token"),
        "consumer_key": os.environ.get("IBKR_OAUTH_CONSUMER_KEY", ""),
        "private_key_path": os.environ.get("IBKR_OAUTH_PRIVATE_KEY_PATH", ""),
        "algorithm": "RS256",  # JWT signing algorithm
        "token_expiry_buffer": 60,  # Refresh 60s before expiry
    },

    # Session Management
    "session": {
        "tickle_interval": 240,  # Tickle every 4 minutes
        "max_session_duration": 86400,  # 24 hours
        "auto_reconnect": True,
        "reconnect_delay": 5,
        "max_reconnect_attempts": 3,
    },

    # Rate Limiting
    "rate_limit": {
        "requests_per_second": 50,  # OAuth 2.0 limit
        "adaptive_backoff": True,
        "backoff_multiplier": 0.8,  # Reduce rate on 429 errors
        "recovery_multiplier": 1.05,  # Increase rate on success
    },

    # Connection Settings
    "connection": {
        "timeout": 30,
        "verify_ssl": True,
        "max_connections": 10,
        "max_connections_per_host": 20,
    },
}

# ==============================================================================
# TRADING MODE CONFIGURATION
# ==============================================================================
TRADING_MODE = os.environ.get("TRADING_MODE", "paper")  # Default: paper

# Explicit live trading confirmation (SAFETY FEATURE)
REQUIRE_LIVE_CONFIRMATION = os.environ.get("REQUIRE_LIVE_CONFIRMATION", "true").lower() == "true"

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
        "order_type": "LMT",
        "price_offset_ticks": 1,
        "max_slippage_percent": 0.5,
        "fill_wait_seconds": 30,
        "use_adaptive_orders": True,
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
        "alert_on_api_rate_limit": True,  # Web API specific
        "alert_on_session_expiry": True,  # Session management
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
    "log_file_path": "logs/spyder_webapi.log",
    "log_rotation": "daily",
    "log_retention_days": 30,
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - [WEB_API] %(message)s",
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
# HELPER FUNCTIONS FOR WEB API
# ==============================================================================
def get_active_config():
    """Get configuration for active trading mode with Web API settings"""
    mode = os.environ.get("TRADING_MODE", "paper")

    # Safety check for live trading
    if mode == "live" and REQUIRE_LIVE_CONFIRMATION:
        live_confirmed = os.environ.get("LIVE_TRADING_CONFIRMED", "false").lower() == "true"
        if not live_confirmed:
            raise ValueError(
                "LIVE TRADING BLOCKED: Set LIVE_TRADING_CONFIRMED=true in .env "
                "after verifying you want to trade with real money."
            )

    return {
        "mode": mode,
        "connection_type": "web_api",
        "api_base_url": IBKR_WEB_API_CONFIG["api_base_url"],
        "auth_method": "oauth2",
        "consumer_key": IBKR_WEB_API_CONFIG["oauth"]["consumer_key"],
        "requires_confirmation": REQUIRE_LIVE_CONFIRMATION if mode == "live" else False,
    }


def validate_web_api_config():
    """Validate Web API configuration"""
    config = IBKR_WEB_API_CONFIG["oauth"]

    errors = []

    # Check consumer key
    if not config["consumer_key"]:
        errors.append("IBKR_OAUTH_CONSUMER_KEY not set in .env")

    # Check private key path
    if not config["private_key_path"]:
        errors.append("IBKR_OAUTH_PRIVATE_KEY_PATH not set in .env")
    elif not Path(config["private_key_path"]).exists():
        errors.append(f"Private key file not found: {config['private_key_path']}")

    # Check trading mode
    mode = os.environ.get("TRADING_MODE", "")
    if mode not in ["paper", "live"]:
        errors.append(f"Invalid TRADING_MODE: {mode}. Must be 'paper' or 'live'")

    if errors:
        return False, "\n".join(["Configuration errors:"] + [f"  - {e}" for e in errors])

    return True, f"Web API configuration valid (mode: {mode})"


def check_api_authentication():
    """Check if API authentication is properly configured"""
    try:
        config = get_active_config()
        is_valid, message = validate_web_api_config()

        return {
            "authenticated": is_valid,
            "mode": config["mode"],
            "connection_type": "web_api",
            "status": "ready" if is_valid else "configuration_error",
            "message": message,
        }
    except Exception as e:
        return {
            "authenticated": False,
            "mode": "unknown",
            "connection_type": "web_api",
            "status": "error",
            "message": f"Configuration check failed: {str(e)}",
        }


# Print configuration status on import
if __name__ != "__main__":
    print("🌐 SPYDER IBKR Web API Configuration Loaded")
    print(f"   API URL: {IBKR_WEB_API_CONFIG['api_base_url']}")
    print(f"   Auth Method: OAuth 2.0 (private_key_jwt)")
    print(f"   Trading Mode: {TRADING_MODE}")

if __name__ == "__main__":
    # Test the configuration when run directly
    print("🔍 Testing Web API Configuration...")

    status = check_api_authentication()
    print(f"Authentication Status: {status['status']}")
    print(f"Mode: {status['mode']}")
    print(f"Message: {status['message']}")

    if status["authenticated"]:
        print("✅ Configuration is valid and ready for use")
    else:
        print("❌ Configuration errors found - check .env file")
