#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Unknown
Module: config_template.py
Purpose: Configuration template for Spyder trading system (Tradier).

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-02-26 Time: 12:00:00

Module Description:
    Template configuration for Spyder trading system.
    Copy config_template.py to config.py and fill in your API keys.
    Never commit real credentials — use environment variables via .env.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os

__all__ = ["TRADIER_CONFIG", "TRADING_CONFIG"]

# ==============================================================================
# TRADIER BROKER CONFIGURATION
# ==============================================================================
TRADIER_CONFIG = {
    "api_key": os.environ.get("TRADIER_API_KEY", ""),
    "account_id": os.environ.get("TRADIER_ACCOUNT_ID", ""),
    "environment": os.environ.get("TRADIER_ENVIRONMENT", "live"),  # live | production
    "live_url": "https://api.tradier.com/v1",
    "timeout": 30,
    "max_retries": 3,
    "retry_delay": 1.0,
    "requests_per_second": 10,
}

# ==============================================================================
# TRADING CONFIGURATION
# ==============================================================================
TRADING_CONFIG = {
    "risk_limits": {
        "max_position_size": 10000,
        "max_contracts_per_trade": 10,
        "max_daily_loss": 500,
        "max_daily_trades": 20,
        "max_open_positions": 5,
    },
    "trading_hours": {
        "pre_market_start": "08:00",
        "market_open": "09:30",
        "market_close": "16:00",
        "after_hours_end": "17:00",
        "timezone": "US/Eastern",
    },
    "spx_options": {
        "default_option_root": "SPXW",
        "monthly_option_root": "SPX",
        "min_days_to_expiry": 0,
        "max_days_to_expiry": 45,
        "min_option_volume": 100,
        "min_open_interest": 50,
        "strike_range_percent": 2.0,
    },
}

# Backward compatibility for modules still reading legacy key names.
TRADING_CONFIG["spy_options"] = TRADING_CONFIG["spx_options"]
