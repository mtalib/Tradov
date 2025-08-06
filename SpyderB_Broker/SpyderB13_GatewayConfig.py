#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB13_GatewayConfig.py
Group: B (Broker/Connection)
Purpose: IB Gateway configuration and IBC automation setup
Author: Mohamed Talib
Date Created: 2025-08-03
Last Updated: 2025-08-03 Time: 12:35:00

Description:
    Implements the IB Gateway configuration from the stability plan including
    memory allocation, port configuration, and multi-client support settings.
    Configured for US Eastern Time operations with Zurich gateway server.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field, asdict
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS  
# ==============================================================================
import pytz

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import Spyder utilities: {e}")
    # Fallback to standard logging
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Default configuration values
DEFAULT_JAVA_MEMORY_MB = 6144  # 6GB for 9 clients
DEFAULT_API_PORT_PAPER = 4002
DEFAULT_API_PORT_LIVE = 4001
DEFAULT_IBC_CONTROL_PORT = 4000
DEFAULT_MAX_CLIENT_ID = 10
DEFAULT_GATEWAY_SERVER = 'zdc1.ibllc.com'  # Zurich server

# Auto-restart time (before IB maintenance window)
AUTO_RESTART_TIME = '03:45'  # 3:45 AM Eastern

# ==============================================================================
# ENUMS
# ==============================================================================
class TradingMode(str, Enum):
    """Trading mode enumeration"""
    PAPER = 'paper'
    LIVE = 'live'

class ClientPurpose(str, Enum):
    """Purpose of each client connection - UPDATED ALLOCATION"""
    ADMINISTRATIVE = "Account Management"
    ORDER_EXECUTION = "Order Execution - HIGHEST PRIORITY"
    CORE_DATA = "Core Market Data"
    SPY_OPTIONS = "SPY Options Chains"
    VOLATILITY = "Volatility Indicators"
    MARKET_INTERNALS = "Market Internals"
    MAJOR_INDICES = "Major Index ETFs"
    EXTENDED_ASSETS = "Extended Market Data"
    SECTOR_ETFS = "Sector ETFs"

# ==============================================================================
# DATACLASSES
# ==============================================================================
@dataclass
class ClientConfig:
    """Configuration for a single client connection"""
    client_id: int
    purpose: ClientPurpose
    symbols: List[str] = field(default_factory=list)
    frequency: float = 0.0  # Update frequency in seconds
    description: str = ""
    priority: str = "MEDIUM"
    update_interval: Optional[float] = None
    rate_limit: int = 30  # Requests per second

@dataclass
class GatewayConfig:
    """IB Gateway configuration with stability enhancements"""
    
    # Authentication
    ib_username: str = field(default_factory=lambda: os.getenv('IB_USERNAME', ''))
    ib_password: str = field(default_factory=lambda: os.getenv('IB_PASSWORD', ''))
    trading_mode: TradingMode = TradingMode.PAPER
    
    # Port Configuration
    ibc_control_port: int = DEFAULT_IBC_CONTROL_PORT
    api_port_paper: int = DEFAULT_API_PORT_PAPER
    api_port_live: int = DEFAULT_API_PORT_LIVE
    
    # Memory Configuration (Critical for multi-client)
    java_memory_mb: int = DEFAULT_JAVA_MEMORY_MB
    
    # Timezone (US Eastern)
    timezone: str = 'US/Eastern'
    tz: pytz.timezone = field(default_factory=lambda: pytz.timezone('US/Eastern'))
    
    # Server Configuration  
    gateway_server: str = DEFAULT_GATEWAY_SERVER
    
    # Auto-restart Configuration
    auto_restart_time: str = AUTO_RESTART_TIME
    
    # Multi-client Support
    max_client_id: int = DEFAULT_MAX_CLIENT_ID
    master_client_id: int = 0
    
    # Logging
    log_level: str = 'INFO'
    log_dir: Path = field(default_factory=lambda: Path('logs'))
    
    # Performance Settings
    request_timeout: int = 30
    connection_timeout: int = 60
    heartbeat_interval: int = 30
    
    def __post_init__(self):
        """Post-initialization setup"""
        # Ensure timezone is properly set
        if isinstance(self.timezone, str):
            self.tz = pytz.timezone(self.timezone)
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration parameters"""
        if not self.ib_username or not self.ib_password:
            raise ValueError("IB credentials not configured. Set IB_USERNAME and IB_PASSWORD environment variables.")
        
        if self.java_memory_mb < 4096:
            raise ValueError(f"Java memory too low for 9 clients: {self.java_memory_mb}MB. Minimum: 4096MB")
        
        if self.max_client_id < 9:
            raise ValueError(f"max_client_id must be at least 9 for multi-client setup: {self.max_client_id}")
    
    def get_current_api_port(self) -> int:
        """Get API port based on trading mode"""
        return self.api_port_paper if self.trading_mode == TradingMode.PAPER else self.api_port_live
    
    def get_ibc_config(self) -> Dict[str, str]:
        """Generate IBC configuration dictionary"""
        return {
            'IbLoginId': self.ib_username,
            'IbPassword': self.ib_password,
            'TradingMode': self.trading_mode.value,
            'FIX': 'no',
            'OverrideTwsApiPort': str(self.ibc_control_port),
            'ApiPort': str(self.get_current_api_port()),
            'AcceptIncomingConnectionAction': 'accept',
            'ExistingSessionDetectedAction': 'primary',
            'AcceptNonBrokerageAccountWarning': 'yes',
            'JavaMemory': str(self.java_memory_mb),
            'AutoRestartTime': self.auto_restart_time,
            'AutoLogoffTime': 'no',
            'Gateway': self.gateway_server,
            'MaxClientId': str(self.max_client_id),
            'AllowBlindTrading': 'yes',
            'DismissPasswordExpiryWarning': 'yes',
            'DismissNSEComplianceNotice': 'yes',
            'ReadOnlyLogin': 'no',
            'StoreSettingsOnServer': 'yes'
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        config_dict = asdict(self)
        # Convert timezone to string for serialization
        config_dict['tz'] = str(self.tz)
        # Convert Path to string
        config_dict['log_dir'] = str(self.log_dir)
        # Convert enum to string
        config_dict['trading_mode'] = self.trading_mode.value
        return config_dict
    
    def save_to_file(self, filepath: Path):
        """Save configuration to JSON file"""
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: Path) -> 'GatewayConfig':
        """Load configuration from JSON file"""
        with open(filepath, 'r') as f:
            config_dict = json.load(f)
        
        # Convert strings back to proper types
        config_dict['trading_mode'] = TradingMode(config_dict['trading_mode'])
        config_dict['log_dir'] = Path(config_dict['log_dir'])
        # Remove tz string (will be recreated in __post_init__)
        config_dict.pop('tz', None)
        
        return cls(**config_dict)

# ==============================================================================
# CLIENT ALLOCATION CONFIGURATION
# ==============================================================================
def get_client_allocation() -> Dict[int, ClientConfig]:
    """
    Get the complete 9-client allocation strategy.
    
    Returns:
        Dictionary mapping client_id to ClientConfig
    """
    return {
        0: ClientConfig(
            client_id=0,
            purpose=ClientPurpose.ADMINISTRATIVE,
            symbols=[],
            frequency=0.0,
            description='Account management, system control',
            priority='CRITICAL',
            update_interval=None,
            rate_limit=10
        ),
        1: ClientConfig(
            client_id=1,
            purpose=ClientPurpose.ORDER_EXECUTION,
            symbols=[],
            frequency=0.0,
            description='Ultra-fast order execution - NO MARKET DATA',
            priority='CRITICAL',
            update_interval=None,
            rate_limit=50  # Highest rate limit for orders
        ),
        2: ClientConfig(
            client_id=2,
            purpose=ClientPurpose.CORE_DATA,
            symbols=['SPY', 'SPX', '/ES', 'VIX', 'TICK-NYSE'],
            frequency=1.0,  # 1 second updates
            description='Core market data for trading decisions',
            priority='CRITICAL',
            update_interval=1.0,
            rate_limit=45
        ),
        3: ClientConfig(
            client_id=3,
            purpose=ClientPurpose.SPY_OPTIONS,
            symbols=['SPY_OPTIONS_0DTE', 'SPY_OPTIONS_1DTE'],
            frequency=1.0,
            description='Real-time SPY options chains',
            priority='CRITICAL',
            update_interval=1.0,
            rate_limit=40
        ),
        4: ClientConfig(
            client_id=4,
            purpose=ClientPurpose.VOLATILITY,
            symbols=['VIX9D', 'VXV', 'VXMT', 'VVIX', 'UVXY', 'VXN', 'RVX'],
            frequency=5.0,
            description='Volatility indicators',
            priority='HIGH',
            update_interval=5.0,
            rate_limit=30
        ),
        5: ClientConfig(
            client_id=5,
            purpose=ClientPurpose.MARKET_INTERNALS,
            symbols=['$TRIN', '$ADD', '$DECL', 'CPC', 'PCALL', 'SKEW'],
            frequency=5.0,
            description='Market internals and breadth',
            priority='HIGH',
            update_interval=5.0,
            rate_limit=30
        ),
        6: ClientConfig(
            client_id=6,
            purpose=ClientPurpose.MAJOR_INDICES,
            symbols=['DIA', 'QQQ', 'IWM', 'NDX'],
            frequency=5.0,
            description='Major market indices',
            priority='HIGH',
            update_interval=5.0,
            rate_limit=25
        ),
        7: ClientConfig(
            client_id=7,
            purpose=ClientPurpose.EXTENDED_ASSETS,
            symbols=['TLT', 'LQD', 'DXY', 'GLD', 'USO', 'UNG'],
            frequency=15.0,
            description='Extended market assets',
            priority='MEDIUM',
            update_interval=15.0,
            rate_limit=20
        ),
        8: ClientConfig(
            client_id=8,
            purpose=ClientPurpose.SECTOR_ETFS,
            symbols=['XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLY',
                    'XLP', 'XLU', 'XLRE', 'XLC', 'XLB'],
            frequency=30.0,
            description='Sector rotation monitoring',
            priority='LOW',
            update_interval=30.0,
            rate_limit=10
        )
    }

# ==============================================================================
# GATEWAY MANAGER CLASS
# ==============================================================================
class GatewayManager:
    """Manages IB Gateway configuration and lifecycle"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        """
        Initialize Gateway Manager.
        
        Args:
            config: Gateway configuration (creates default if None)
        """
        self.config = config or GatewayConfig()
        self.client_configs = get_client_allocation()
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
        
        # Setup error handler
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None
        
        self.logger.info("GatewayManager initialized for %s trading", 
                        self.config.trading_mode.value)
    
    def get_client_config(self, client_id: int) -> Optional[ClientConfig]:
        """Get configuration for a specific client"""
        return self.client_configs.get(client_id)
    
    def get_rate_limit_for_client(self, client_id: int) -> int:
        """Get rate limit for a specific client"""
        client_config = self.get_client_config(client_id)
        return client_config.rate_limit if client_config else 30
    
    def get_client_purpose(self, client_id: int) -> str:
        """Get the purpose/description for a client"""
        client_config = self.get_client_config(client_id)
        return client_config.description if client_config else "Unknown"
    
    def is_maintenance_window(self) -> bool:
        """
        Check if in IB maintenance window (Eastern time).
        IB maintenance: 11:45 PM - 12:45 AM ET daily
        """
        current_time = datetime.now(self.config.tz)
        
        # Maintenance window in Eastern time
        maintenance_start = current_time.replace(hour=23, minute=45, second=0)
        maintenance_end = current_time.replace(hour=0, minute=45, second=0)
        
        # Handle day boundary
        if maintenance_end < maintenance_start:
            maintenance_end = maintenance_end.replace(day=current_time.day + 1)
        
        return maintenance_start <= current_time or current_time <= maintenance_end
    
    def is_trading_hours(self) -> bool:
        """
        Check if US markets are open (Eastern time).
        Regular trading hours: 9:30 AM - 4:00 PM ET
        """
        current_time = datetime.now(self.config.tz)
        weekday = current_time.weekday()
        
        # Weekend check
        if weekday >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Trading hours in Eastern time
        market_open = time(9, 30)  # 9:30 AM
        market_close = time(16, 0)  # 4:00 PM
        
        current_time_only = current_time.time()
        return market_open <= current_time_only <= market_close
    
    def is_extended_hours(self) -> bool:
        """
        Check if in extended trading hours (Eastern time).
        Pre-market: 4:00 AM - 9:30 AM ET
        After-hours: 4:00 PM - 8:00 PM ET
        """
        current_time = datetime.now(self.config.tz)
        weekday = current_time.weekday()
        
        # Weekend check
        if weekday >= 5:
            return False
        
        current_time_only = current_time.time()
        
        # Pre-market
        pre_market_start = time(4, 0)  # 4:00 AM
        pre_market_end = time(9, 30)  # 9:30 AM
        
        # After-hours
        after_hours_start = time(16, 0)  # 4:00 PM
        after_hours_end = time(20, 0)  # 8:00 PM
        
        return (pre_market_start <= current_time_only < pre_market_end or
                after_hours_start <= current_time_only <= after_hours_end)
    
    def generate_ibc_ini_file(self, output_path: Path):
        """
        Generate IBC configuration ini file.
        
        Args:
            output_path: Path where to save the ini file
        """
        ibc_config = self.config.get_ibc_config()
        
        ini_content = "[IBC]\n"
        for key, value in ibc_config.items():
            ini_content += f"{key}={value}\n"
        
        with open(output_path, 'w') as f:
            f.write(ini_content)
        
        self.logger.info(f"IBC configuration written to {output_path}")
    
    def validate_environment(self) -> bool:
        """
        Validate that the environment is properly configured.
        
        Returns:
            True if environment is valid, False otherwise
        """
        issues = []
        
        # Check credentials
        if not self.config.ib_username or not self.config.ib_password:
            issues.append("IB credentials not configured")
        
        # Check Java memory
        if self.config.java_memory_mb < 4096:
            issues.append(f"Java memory too low: {self.config.java_memory_mb}MB")
        
        # Check if in maintenance window
        if self.is_maintenance_window():
            issues.append("Currently in IB maintenance window")
        
        if issues:
            for issue in issues:
                self.logger.error(f"Environment validation failed: {issue}")
            return False
        
        self.logger.info("Environment validation passed")
        return True

# ==============================================================================
# MODULE TEST
# ==============================================================================
if __name__ == "__main__":
    print("Testing GatewayConfig module...")
    
    # Create default configuration
    config = GatewayConfig()
    
    # Create gateway manager
    manager = GatewayManager(config)
    
    # Display configuration
    print(f"\nGateway Configuration:")
    print(f"  Trading Mode: {config.trading_mode.value}")
    print(f"  API Port: {config.get_current_api_port()}")
    print(f"  Gateway Server: {config.gateway_server}")
    print(f"  Java Memory: {config.java_memory_mb}MB")
    print(f"  Timezone: {config.timezone}")
    
    # Check market status
    print(f"\nMarket Status:")
    print(f"  Trading Hours: {manager.is_trading_hours()}")
    print(f"  Extended Hours: {manager.is_extended_hours()}")
    print(f"  Maintenance Window: {manager.is_maintenance_window()}")
    
    # Display client allocation
    print(f"\nClient Allocation:")
    for client_id, client_config in manager.client_configs.items():
        print(f"  Client {client_id}: {client_config.purpose.value}")
        print(f"    Priority: {client_config.priority}")
        print(f"    Rate Limit: {client_config.rate_limit} req/s")
        if client_config.symbols:
            print(f"    Symbols: {', '.join(client_config.symbols[:3])}...")
    
    # Validate environment
    print(f"\nEnvironment Validation:")
    if manager.validate_environment():
        print("  ✓ Environment is properly configured")
    else:
        print("  ✗ Environment validation failed")
    
    print("\n✓ GatewayConfig module test completed")