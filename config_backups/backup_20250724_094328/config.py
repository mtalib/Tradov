#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Configuration file for Interactive Brokers API Gateway
2025-06-08
This file is SAFE TO COMMIT - all sensitive data comes from environment variables
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==============================================================================
# INTERACTIVE BROKERS CLIENT PORTAL WEB API CONFIGURATION
# ==============================================================================
IB_CONFIG = {
    "use_gateway": True,  # Add this line
    "gateway": {
        "paper": {
            "host": "127.0.0.1",
            "port": 4002,  # Gateway paper trading port
            "clientId": 1,
        },
        "live": {
            "host": "127.0.0.1",
            "port": 4001,  # Gateway live trading port
            "clientId": 2,
        },
    },
}

# ==============================================================================
# TRADING CONFIGURATION
# ==============================================================================
TRADING_CONFIG = {
    # Position Limits
    "risk_limits": {
        "max_position_size": 10000,  # Maximum position value in USD
        "max_contracts_per_trade": 10,  # Maximum option contracts per trade
        "max_daily_loss": 500,  # Maximum daily loss in USD
        "max_daily_trades": 20,  # Maximum number of trades per day
        "max_open_positions": 5,  # Maximum concurrent open positions
    },
    # Trading Hours (Eastern Time)
    "trading_hours": {
        "pre_market_start": "08:00",  # Pre-market analysis start
        "market_open": "09:30",  # Regular market open
        "market_close": "16:00",  # Regular market close
        "after_hours_end": "17:00",  # After-hours monitoring end
        "timezone": "US/Eastern",  # Trading timezone
    },
    # SPY Options Specific Settings
    "spy_options": {
        "min_days_to_expiry": 0,  # Allow 0DTE trading
        "max_days_to_expiry": 45,  # Maximum DTE to consider
        "min_option_volume": 100,  # Minimum volume filter
        "min_open_interest": 50,  # Minimum open interest filter
        "strike_range_percent": 2.0,  # % from ATM to consider (2% = ~9 strikes)
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
        "order_type": "LMT",  # Default order type (LMT, MKT)
        "price_offset_ticks": 1,  # Ticks from mid for limit orders
        "max_slippage_percent": 0.5,  # Maximum acceptable slippage
        "fill_wait_seconds": 30,  # Time to wait for fill
        "use_adaptive_orders": True,  # Use IB's adaptive algo
    },
    # Risk Management
    "risk_management": {
        "stop_loss_percent": 50,  # Stop loss at 50% loss
        "profit_target_percent": 25,  # Take profit at 25% gain
        "trailing_stop_percent": 10,  # Trailing stop percentage
        "max_loss_per_trade": 200,  # Maximum loss per trade in USD
        "use_portfolio_hedging": True,  # Enable portfolio hedging
    },
    # Notifications
    "notifications": {
        # Telegram notifications (recommended over SMS - free and reliable)
        "telegram_alerts": bool(os.environ.get("TELEGRAM_BOT_TOKEN", "")),
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
        # Email notifications
        "email_alerts": bool(os.environ.get("EMAIL_ADDRESS", "")),
        "email_address": os.environ.get("EMAIL_ADDRESS", ""),
        "email_password": os.environ.get("EMAIL_PASSWORD", ""),  # App-specific password
        "smtp_server": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        "smtp_port": int(os.environ.get("SMTP_PORT", "587")),
        # Notification triggers
        "alert_on_trade_fill": True,  # Alert when trades are filled
        "alert_on_stop_loss": True,  # Alert when stop loss triggered
        "alert_on_daily_summary": True,  # Daily P&L summary
        "alert_on_errors": True,  # System errors/issues
        "alert_on_large_moves": True,  # Large SPY price movements
    },
}

# ==============================================================================
# STRATEGY SPECIFIC CONFIGURATIONS
# ==============================================================================
STRATEGY_CONFIG = {
    "iron_condor": {
        "enabled": True,
        "delta_short": 0.15,  # Delta for short strikes
        "delta_long": 0.05,  # Delta for long strikes
        "min_credit": 0.30,  # Minimum credit to receive
        "days_to_expiry": [0, 1, 2],  # Preferred DTEs
        "entry_time": "10:00",  # Entry time
        "exit_time": "15:30",  # Exit time
        "max_loss_percent": 200,  # Max loss as % of credit
    },
    "credit_spread": {
        "enabled": True,
        "spread_width": 5,  # Strike width in dollars
        "delta_short": 0.20,  # Delta for short strike
        "min_credit": 0.25,  # Minimum credit
        "trade_direction": "both",  # "bullish", "bearish", or "both"
        "entry_conditions": {
            "min_iv_rank": 30,  # Minimum IV rank
            "rsi_oversold": 30,  # RSI oversold level
            "rsi_overbought": 70,  # RSI overbought level
        },
    },
    "zero_dte_scalping": {
        "enabled": True,
        "entry_window": ["09:45", "11:00"],  # Trading window
        "scalp_target": 0.10,  # Target profit per contract
        "max_contracts": 5,  # Maximum contracts
        "momentum_period": 5,  # Momentum calculation period
        "min_volume": 500,  # Minimum volume for entry
        "use_limit_orders": True,  # Use limit orders
    },
}

# ==============================================================================
# DATABASE CONFIGURATION
# ==============================================================================
DATABASE_CONFIG = {
    "db_path": "data/spyder.db",  # SQLite database path
    "backup_enabled": True,  # Enable automatic backups
    "backup_interval_hours": 24,  # Backup frequency
    "backup_retention_days": 30,  # Keep backups for 30 days
}

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================
LOGGING_CONFIG = {
    "log_level": os.environ.get("LOG_LEVEL", "INFO"),  # DEBUG, INFO, WARNING, ERROR
    "log_to_file": True,
    "log_file_path": "logs/spyder.log",
    "log_rotation": "daily",  # daily, weekly, size
    "log_retention_days": 30,
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# ==============================================================================
# SYSTEM CONFIGURATION
# ==============================================================================
SYSTEM_CONFIG = {
    "mode": (
        "production"
        if os.environ.get("DEBUG_MODE", "False").lower() == "false"
        else "development"
    ),
    "debug": os.environ.get("DEBUG_MODE", "False").lower() == "true",
    "performance_monitoring": True,  # Enable performance tracking
    "health_check_interval": 300,  # Health check every 5 minutes
    "auto_restart_on_error": False,  # Auto-restart on critical errors
    "max_memory_usage_mb": 2048,  # Maximum memory usage
}


# ==============================================================================
# VALIDATION FUNCTION
# ==============================================================================
def validate_config():
    """Validate configuration settings"""
    errors = []
    warnings = []

    # Check IB configuration for both paper and live
    mode = IB_CONFIG["auth"]["trading_mode"]

    # Check if any credentials are set
    paper_user = IB_CONFIG["auth"]["paper"]["username"]
    live_user = IB_CONFIG["auth"]["live"]["username"]

    if not paper_user and not live_user:
        errors.append(
            "No IB credentials found. Please set environment variables or create .env file"
        )

    # Check current mode credentials
    if mode == "paper" and not paper_user:
        errors.append(
            "Paper trading credentials not set (IB_PAPER_USER, IB_PAPER_PASS, IB_PAPER_ACCOUNT)"
        )
    elif mode == "live" and not live_user:
        errors.append(
            "Live trading credentials not set (IB_LIVE_USER, IB_LIVE_PASS, IB_LIVE_ACCOUNT)"
        )

    # Check Telegram configuration
    if os.environ.get("TELEGRAM_BOT_TOKEN") and not os.environ.get("TELEGRAM_CHAT_ID"):
        warnings.append("Telegram bot token set but chat ID missing")

    # Check email configuration
    if os.environ.get("EMAIL_ADDRESS") and not os.environ.get("EMAIL_PASSWORD"):
        warnings.append("Email address set but password missing")

    return errors, warnings


# ==============================================================================
# GET ACTIVE CONFIGURATION
# ==============================================================================
def get_active_config():
    """Get configuration for active trading mode"""
    mode = IB_CONFIG["auth"]["trading_mode"]

    return {
        "username": IB_CONFIG["auth"][mode]["username"],
        "password": IB_CONFIG["auth"][mode]["password"],
        "account": IB_CONFIG["auth"][mode]["account"],
        "host": IB_CONFIG["gateway"][mode]["host"],
        "port": IB_CONFIG["gateway"][mode]["port"],
        "clientId": IB_CONFIG["gateway"][mode]["clientId"],
        "mode": mode,
    }


# Validate on import
if __name__ != "__main__":
    errors, warnings = validate_config()

    if errors:
        print("\n❌ CONFIGURATION ERRORS:")
        for error in errors:
            print(f"  - {error}")
        print("\n📋 Setup Instructions:")
        print("  1. Copy .env.example to .env")
        print("  2. Fill in your IB credentials")
        print("  3. Never commit .env to git!")

    if warnings:
        print("\n⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  - {warning}")

# ==============================================================================
# PRINT CONFIGURATION STATUS (for debugging)
# ==============================================================================
if __name__ == "__main__":
    print("SPYDER Configuration Status")
    print("=" * 50)

    # Check environment
    print(f"Environment file exists: {os.path.exists('.env')}")
    print(f"Trading mode: {IB_CONFIG['auth']['trading_mode']}")

    # Check credentials (masked)
    for mode in ["paper", "live"]:
        user = IB_CONFIG["auth"][mode]["username"]
        if user:
            print(f"{mode.title()} credentials: ✅ (user: {user[:3]}...)")
        else:
            print(f"{mode.title()} credentials: ❌ Not set")

    # Check notifications
    if TRADING_CONFIG["notifications"]["telegram_alerts"]:
        print("Telegram notifications: ✅ Enabled")
    else:
        print("Telegram notifications: ❌ Disabled")

    # Validate
    errors, warnings = validate_config()
    print(f"\nValidation: {len(errors)} errors, {len(warnings)} warnings")
