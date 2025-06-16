"""
Configuration package for Spyder trading system.
"""

try:
    from .config import IB_CONFIG, TRADING_CONFIG
except ImportError:
    # Fallback to template if config.py doesn't exist
    from .config_template import IB_CONFIG, TRADING_CONFIG

    print(
        "Warning: Using template config. Copy config_template.py to config.py and update with your values."
    )

__all__ = ["IB_CONFIG", "TRADING_CONFIG"]

# Configuration file - fill in your actual values
IB_CONFIG = {
    "account": "DU123456",  # Replace with your paper trading account
    "username": "your_username",  # Replace with your IB username
    "password": "your_password",  # Replace with your IB password
    "port": 7497,  # TWS Paper Trading (use 7496 for live)
    "clientId": 1,
}

TRADING_CONFIG = {
    "max_position_size": 10000,
    "max_daily_loss": 500,
    "trading_hours": {"start": "09:30", "end": "16:00"},
}
