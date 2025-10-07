#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - IB Gateway Configuration (Local)
Backup configuration for IB Gateway connection method
Compatible with IB Gateway 10.37+ with connection pooling optimizations
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ==============================================================================
# IB GATEWAY CONFIGURATION (LOCAL)
# ==============================================================================
IB_CONFIG = {
    "use_gateway": True,  # Using IB Gateway instead of TWS
    "connection_type": "local_gateway",  # Track connection type
    "gateway_computer": {
        "ip_address": "127.0.0.1",
        "hostname": "localhost",
        "setup_date": "Local Gateway Configuration",
    },
    "gateway": {
        "paper": {
            "host": "127.0.0.1",  # Local IB Gateway
            "port": 4002,  # IB Gateway Paper port (default 4002)
            "clientId": 1,
        },
        "live": {
            "host": "127.0.0.1",  # Local IB Gateway
            "port": 4001,  # IB Gateway Live port (default 4001)
            "clientId": 2,
        },
    },
}

# ==============================================================================
# GATEWAY CONNECTION SETTINGS (OPTIMIZED)
# ==============================================================================
LOCAL_CONNECTION_CONFIG = {
    "connection_timeout": 15,  # Shorter timeout for local connection
    "reconnection_attempts": 3,  # Fewer attempts needed locally
    "reconnection_delay": 5,  # Shorter delay between attempts
    "heartbeat_interval": 60,  # Monitor connection health
    "network_timeout": 20,  # Local network operation timeout
    "enable_connection_pooling": True,  # Your proven pooling system
    "gateway_startup_delay": 10,  # Wait for Gateway to fully initialize
}

# ==============================================================================
# GATEWAY STARTUP CONFIGURATION
# ==============================================================================
GATEWAY_STARTUP_CONFIG = {
    "auto_start_gateway": True,
    "gateway_executable_path": "/opt/ibc/scripts/ibgateway.sh",
    "jvm_max_heap": "768m",
    "jvm_gc_type": "G1GC",
    "startup_timeout": 60,
    "health_check_retries": 5,
}

# ==============================================================================
# CONNECTION RELIABILITY SETTINGS
# ==============================================================================
GATEWAY_RELIABILITY_CONFIG = {
    "first_connection_retry": True,  # Gateway startup connection retry
    "client_id_rotation": True,  # Use client ID rotation
    "client_id_pool_size": 10,  # Pool of client IDs
    "cleanup_delay_seconds": 2.0,  # Cleanup delay between connections
    "max_concurrent_connections": 3,  # Limit concurrent connections
    "connection_validation": True,  # Validate connection before use
}

# ==============================================================================
# TRADING CONFIGURATION (same as remote TWS)
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
        "alert_on_gateway_issues": True,  # Gateway-specific
        "alert_on_gateway_restart": True,  # Gateway restart notifications
    },
}

# ==============================================================================
# STRATEGY CONFIGURATIONS (same as remote TWS)
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
    "log_file_path": "logs/spyder_gateway.log",  # Gateway-specific log file
    "log_rotation": "daily",
    "log_retention_days": 30,
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - [GATEWAY] %(message)s",
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
    "auto_restart_on_error": True,  # Gateway can auto-restart
    "max_memory_usage_mb": 1024,  # Lower memory usage for Gateway
    "gateway_monitoring": True,  # Monitor Gateway process
}


# ==============================================================================
# HELPER FUNCTIONS FOR GATEWAY
# ==============================================================================
def get_active_config():
    """Get configuration for active trading mode with Gateway settings"""
    paper_config = IB_CONFIG["gateway"]["paper"]
    live_config = IB_CONFIG["gateway"]["live"]

    # Default to paper for initial setup
    mode = os.environ.get("TRADING_MODE", "paper")

    if mode == "paper":
        return {
            "host": paper_config["host"],
            "port": paper_config["port"],
            "clientId": paper_config["clientId"],
            "mode": "paper",
            "connection_type": "local_gateway",
            "local_host": "127.0.0.1",
        }
    else:
        return {
            "host": live_config["host"],
            "port": live_config["port"],
            "clientId": live_config["clientId"],
            "mode": "live",
            "connection_type": "local_gateway",
            "local_host": "127.0.0.1",
        }


def validate_gateway_connection():
    """Validate local Gateway connection"""
    import socket
    import subprocess

    config = get_active_config()
    host = config["host"]
    port = config["port"]

    try:
        # First check if IB Gateway process is running
        try:
            result = subprocess.run(
                ["pgrep", "-f", "ibgateway"], capture_output=True, text=True, timeout=5
            )
            gateway_running = bool(result.stdout.strip())
        except:
            gateway_running = False

        # Test TCP connectivity
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            status = "running" if gateway_running else "port accessible"
            return True, f"Gateway connection to {host}:{port} successful ({status})"
        else:
            if not gateway_running:
                return (
                    False,
                    f"IB Gateway not running - start with launch_spyder_with_gateway.sh",
                )
            else:
                return (
                    False,
                    f"Gateway running but port {port} not accessible (error: {result})",
                )

    except Exception as e:
        return False, f"Gateway connection test failed: {str(e)}"


def check_gateway_status():
    """Check if IB Gateway is running and healthy"""
    import subprocess
    import time

    try:
        # Check if Gateway process exists
        result = subprocess.run(
            ["pgrep", "-f", "ibgateway"], capture_output=True, text=True, timeout=5
        )

        if result.stdout.strip():
            # Process exists, check connection
            success, message = validate_gateway_connection()
            return {
                "process_running": True,
                "connection_available": success,
                "status": "healthy" if success else "process_running_no_connection",
                "message": message,
            }
        else:
            return {
                "process_running": False,
                "connection_available": False,
                "status": "not_running",
                "message": "IB Gateway process not found",
            }
    except Exception as e:
        return {
            "process_running": False,
            "connection_available": False,
            "status": "error",
            "message": f"Status check failed: {str(e)}",
        }


# Print configuration status on import
if __name__ != "__main__":
    print("🏪 SPYDER IB Gateway Configuration Loaded")
    print(f"   Local Gateway: 127.0.0.1")
    print(f"   Paper Port: 4002 | Live Port: 4001")
    print(f"   Connection Type: local_gateway")

if __name__ == "__main__":
    # Test the configuration when run directly
    print("🔍 Testing Gateway Configuration...")

    status = check_gateway_status()
    print(f"Gateway Status: {status['status']}")
    print(f"Message: {status['message']}")

    if status["process_running"]:
        success, message = validate_gateway_connection()
        print(f"Connection Test: {'✅' if success else '❌'} {message}")
    else:
        print("❌ Gateway not running - use launch_spyder_with_gateway.sh to start")
