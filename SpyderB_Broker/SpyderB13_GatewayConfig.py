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
Last Updated: 2025-08-12 Time: 17:00:00

Description:
    Implements the IB Gateway configuration from the stability plan including
    memory allocation, port configuration, and multi-client support settings.
    Configured for US Eastern Time operations with Zurich gateway server.

    UPDATED: Client IDs now range from 1-9 instead of 0-8 to match dashboard display.
    Order execution moved to Client 2 for highest priority trading operations.
"""

import json
import logging
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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
DEFAULT_MAX_CLIENT_ID = 10  # UPDATED: Max client ID for 1-9 range
DEFAULT_GATEWAY_SERVER = "zdc1.ibllc.com"  # Zurich server

# Auto-restart time (before IB maintenance window)
AUTO_RESTART_TIME = "03:45"  # 3:45 AM Eastern

# ==============================================================================
# ENUMS
# ==============================================================================


class TradingMode(str, Enum):
    """Trading mode enumeration"""

    PAPER = "paper"
    LIVE = "live"


class ClientPurpose(str, Enum):
    """Purpose of each client connection - UPDATED ALLOCATION (1-9)"""

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
    ib_username: str = field(default_factory=lambda: os.getenv("IB_USERNAME", ""))
    ib_password: str = field(default_factory=lambda: os.getenv("IB_PASSWORD", ""))
    trading_mode: TradingMode = TradingMode.PAPER

    # Port Configuration
    ibc_control_port: int = DEFAULT_IBC_CONTROL_PORT
    api_port_paper: int = DEFAULT_API_PORT_PAPER
    api_port_live: int = DEFAULT_API_PORT_LIVE

    # Memory Configuration (Critical for multi-client)
    java_memory_mb: int = DEFAULT_JAVA_MEMORY_MB

    # Timezone (US Eastern)
    timezone: str = "US/Eastern"
    tz: pytz.timezone = field(default_factory=lambda: pytz.timezone("US/Eastern"))

    # Server Configuration
    gateway_server: str = DEFAULT_GATEWAY_SERVER

    # Auto-restart Configuration
    auto_restart_time: str = AUTO_RESTART_TIME

    # Multi-client Support - UPDATED FOR 1-9 RANGE
    max_client_id: int = DEFAULT_MAX_CLIENT_ID
    min_client_id: int = 1  # NEW: Minimum client ID (no more Client 0)
    master_client_id: int = 1  # UPDATED: Master client is now Client 1 (was 0)

    # Logging
    log_level: str = "INFO"
    log_dir: Path = field(default_factory=lambda: Path("logs"))

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
            raise ValueError(
                "IB credentials not configured. "
                "Set IB_USERNAME and IB_PASSWORD environment variables."
            )

        if self.java_memory_mb < 4096:
            raise ValueError(
                f"Java memory too low for 9 clients: {
                    self.java_memory_mb}MB. Minimum: 4096MB"
            )

        # UPDATED: Validation for 1-9 client range
        if self.max_client_id < 9:
            raise ValueError(
                f"max_client_id must be at least 9 for multi-client setup: {self.max_client_id}"
            )

        if self.min_client_id < 1:
            raise ValueError(f"min_client_id must be at least 1: {self.min_client_id}")

        if self.master_client_id < self.min_client_id or self.master_client_id > 9:
            raise ValueError(
                f"master_client_id must be in range {self.min_client_id}-9: {self.master_client_id}"
            )

    def get_current_api_port(self) -> int:
        """Get API port based on trading mode"""
        return self.api_port_paper if self.trading_mode == TradingMode.PAPER else self.api_port_live

    def get_ibc_config(self) -> Dict[str, str]:
        """Generate IBC configuration dictionary"""
        return {
            "IbLoginId": self.ib_username,
            "IbPassword": self.ib_password,
            "TradingMode": self.trading_mode.value,
            "FIX": "no",
            "OverrideTwsApiPort": str(self.ibc_control_port),
            "ApiPort": str(self.get_current_api_port()),
            "AcceptIncomingConnectionAction": "accept",
            "ExistingSessionDetectedAction": "primary",
            "AcceptNonBrokerageAccountWarning": "yes",
            "JavaMemory": str(self.java_memory_mb),
            "AutoRestartTime": self.auto_restart_time,
            "AutoLogoffTime": "no",
            "Gateway": self.gateway_server,
            "MaxClientId": str(self.max_client_id),
            "MinClientId": str(self.min_client_id),  # NEW: Minimum client ID
            "AllowBlindTrading": "yes",
            "DismissPasswordExpiryWarning": "yes",
            "DismissNSEComplianceNotice": "yes",
            "ReadOnlyLogin": "no",
            "StoreSettingsOnServer": "yes",
        }

    def get_client_id_range(self) -> range:
        """Get the valid client ID range (1-9)"""
        return range(self.min_client_id, 10)  # 1-9 inclusive

    def is_valid_client_id(self, client_id: int) -> bool:
        """Check if client ID is in valid range (1-9)"""
        return client_id in self.get_client_id_range()

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        config_dict = asdict(self)
        # Convert timezone to string for serialization
        config_dict["tz"] = str(self.tz)
        # Convert Path to string
        config_dict["log_dir"] = str(self.log_dir)
        # Convert enum to string
        config_dict["trading_mode"] = self.trading_mode.value
        return config_dict

    def save_to_file(self, filepath: Path):
        """Save configuration to JSON file"""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: Path) -> "GatewayConfig":
        """Load configuration from JSON file"""
        with open(filepath, "r") as f:
            config_dict = json.load(f)

        # Convert strings back to proper types
        config_dict["trading_mode"] = TradingMode(config_dict["trading_mode"])
        config_dict["log_dir"] = Path(config_dict["log_dir"])
        # Remove tz string (will be recreated in __post_init__)
        config_dict.pop("tz", None)

        return cls(**config_dict)


# ==============================================================================
# CLIENT ALLOCATION CONFIGURATION - UPDATED FOR CLIENT IDs 1-9
# ==============================================================================


def get_client_allocation() -> Dict[int, ClientConfig]:
    """
    Get the complete 9-client allocation strategy.

    UPDATED: Client IDs now range from 1-9 instead of 0-8 to match dashboard display.

    Client Allocation Strategy:
    - Client 1: Administrative Operations (Account, System Control)
    - Client 2: Order Execution (HIGHEST PRIORITY - Trading operations)
    - Client 3: Core Market Data (SPY, SPX, /ES, VIX, TICK-NYSE) - 1-second updates
    - Client 4: SPY Options Chains (0DTE, 1DTE) - 1-second updates
    - Client 5: Volatility Indicators (VIX9D, VXV, VXMT, VVIX, UVXY) - 5-second updates
    - Client 6: Market Internals (TRIN, ADD, CPC, PCALL, SKEW) - 5-second updates
    - Client 7: Major Indices (DIA, QQQ, IWM, 1DTE Options) - 5-second updates
    - Client 8: Extended Assets (TLT, LQD, DXY, GLD, WEEKLY Options) - 15-30s updates
    - Client 9: Sector ETFs (XLF, XLK, XLE, XLV, XLI, XLY, XLP, XLU, XLRE, XLC, XLB) - 30-60s

    Returns:
        Dictionary mapping client_id to ClientConfig
    """
    return {
        1: ClientConfig(  # UPDATED: Was Client 0
            client_id=1,
            purpose=ClientPurpose.ADMINISTRATIVE,
            symbols=[],
            frequency=0.0,
            description="Account management, system control",
            priority="CRITICAL",
            update_interval=None,
            rate_limit=10,
        ),
        2: ClientConfig(  # UPDATED: Order execution moved to Client 2 (was Client 1)
            client_id=2,
            purpose=ClientPurpose.ORDER_EXECUTION,
            symbols=[],
            frequency=0.0,
            description="Ultra-fast order execution - NO MARKET DATA",
            priority="CRITICAL",
            update_interval=None,
            rate_limit=50,  # Highest rate limit for orders
        ),
        3: ClientConfig(  # UPDATED: Was Client 2
            client_id=3,
            purpose=ClientPurpose.CORE_DATA,
            symbols=["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
            frequency=1.0,  # 1 second updates
            description="Core market data for trading decisions",
            priority="CRITICAL",
            update_interval=1.0,
            rate_limit=45,
        ),
        4: ClientConfig(  # UPDATED: Was Client 3
            client_id=4,
            purpose=ClientPurpose.SPY_OPTIONS,
            symbols=["SPY_OPTIONS_0DTE", "SPY_OPTIONS_1DTE"],
            frequency=1.0,
            description="Real-time SPY options chains",
            priority="CRITICAL",
            update_interval=1.0,
            rate_limit=40,
        ),
        5: ClientConfig(  # UPDATED: Was Client 4
            client_id=5,
            purpose=ClientPurpose.VOLATILITY,
            symbols=["VIX9D", "VXV", "VXMT", "VVIX", "UVXY", "VXN", "RVX"],
            frequency=5.0,
            description="Volatility indicators",
            priority="HIGH",
            update_interval=5.0,
            rate_limit=30,
        ),
        6: ClientConfig(  # UPDATED: Was Client 5
            client_id=6,
            purpose=ClientPurpose.MARKET_INTERNALS,
            symbols=["$TRIN", "$ADD", "$DECL", "CPC", "PCALL", "SKEW"],
            frequency=5.0,
            description="Market internals and breadth",
            priority="HIGH",
            update_interval=5.0,
            rate_limit=30,
        ),
        7: ClientConfig(  # UPDATED: Was Client 6
            client_id=7,
            purpose=ClientPurpose.MAJOR_INDICES,
            symbols=["DIA", "QQQ", "IWM", "NDX"],
            frequency=5.0,
            description="Major market indices",
            priority="HIGH",
            update_interval=5.0,
            rate_limit=25,
        ),
        8: ClientConfig(  # UPDATED: Was Client 7
            client_id=8,
            purpose=ClientPurpose.EXTENDED_ASSETS,
            symbols=["TLT", "LQD", "DXY", "GLD", "USO", "UNG"],
            frequency=15.0,
            description="Extended market assets",
            priority="MEDIUM",
            update_interval=15.0,
            rate_limit=20,
        ),
        9: ClientConfig(  # UPDATED: Was Client 8
            client_id=9,
            purpose=ClientPurpose.SECTOR_ETFS,
            symbols=["XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLRE", "XLC", "XLB"],
            frequency=30.0,
            description="Sector rotation monitoring",
            priority="LOW",
            update_interval=30.0,
            rate_limit=10,
        ),
    }


def get_default_config() -> GatewayConfig:
    """
    Create default gateway configuration for 9-client setup (1-9).

    Returns:
        Default GatewayConfig instance
    """
    return GatewayConfig()


def create_default_config() -> GatewayConfig:
    """Alias for get_default_config() for backward compatibility"""
    return get_default_config()


def load_config(config_path: Optional[Path] = None) -> GatewayConfig:
    """
    Load configuration from file or create default.

    Args:
        config_path: Path to configuration file

    Returns:
        GatewayConfig instance
    """
    if config_path and config_path.exists():
        return GatewayConfig.load_from_file(config_path)
    return get_default_config()


def print_client_allocation_summary():
    """Print summary of client allocation strategy (1-9)"""
    clients = get_client_allocation()

    print("\n" + "=" * 80)
    print("📊 SPYDER CLIENT ALLOCATION STRATEGY (UPDATED: CLIENTS 1-9)")
    print("=" * 80)

    print("🏆 PRIORITY ORDER:")
    priority_order = [
        (2, "ORDER EXECUTION", "CRITICAL - Fastest trading execution"),
        (1, "ADMINISTRATIVE", "CRITICAL - Account & control"),
        (3, "CORE DATA", "CRITICAL - SPY, VIX real-time (1s)"),
        (4, "SPY OPTIONS", "CRITICAL - 0DTE/1DTE options (1s)"),
        (5, "VOLATILITY", "HIGH - Volatility surface (5s)"),
        (6, "MARKET INTERNALS", "HIGH - Market breadth (5s)"),
        (7, "MAJOR INDICES", "HIGH - DIA/QQQ/IWM (5s)"),
        (8, "EXTENDED ASSETS", "MEDIUM - Bonds/FX/Commodities (15s)"),
        (9, "SECTOR ETFS", "LOW - Sector rotation (30s)"),
    ]

    for client_id, name, description in priority_order:
        client = clients[client_id]
        symbol_count = len(client.symbols)

        # Format display
        if client_id == 2:  # Order execution gets special treatment
            print(f"🚀 Client {client_id}: {name} - {description}")
            print(f"   🎯 PURPOSE: Ultra-fast order execution and trade management")
            print(f"   ⚡ RATE LIMIT: {client.rate_limit} req/sec (highest)")
        elif symbol_count > 0:
            print(f"📊 Client {client_id}: {name} - {description}")
            print(
                f"   📈 Symbols ({symbol_count}): {', '.join(client.symbols[:5])}{'...' if symbol_count > 5 else ''}"
            )
            print(f"   🔄 Update frequency: {client.frequency}s")
            print(f"   📊 Rate limit: {client.rate_limit} req/sec")
        else:
            print(f"⚙️ Client {client_id}: {name} - {description}")
            print(f"   📊 Rate limit: {client.rate_limit} req/sec")
        print()

    print("🎯 KEY ADVANTAGES:")
    print("   • Order Execution (Client 2) gets highest priority and rate limit")
    print("   • Administrative (Client 1) for account management and control")
    print("   • Critical market data (Clients 3-4) on fast 1s updates")
    print("   • Load distribution prevents API rate limiting")
    print("   • Fault isolation - if one client fails, others continue")
    print("   • Client IDs 1-9 (eliminates Client 0 complexity)")
    print("   • Matches dashboard display numbering")
    print("=" * 80)


# ==============================================================================
# GATEWAY MANAGER CLASS - UPDATED FOR 1-9 RANGE
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

        self.logger.info(
            "GatewayManager initialized for %s trading (Clients 1-9)",
            self.config.trading_mode.value,
        )

    def get_client_config(self, client_id: int) -> Optional[ClientConfig]:
        """Get configuration for a specific client (1-9 range)"""
        if not self.config.is_valid_client_id(client_id):
            self.logger.warning(f"Invalid client ID {client_id}. Valid range: 1-9")
            return None
        return self.client_configs.get(client_id)

    def get_rate_limit_for_client(self, client_id: int) -> int:
        """Get rate limit for a specific client"""
        client_config = self.get_client_config(client_id)
        return client_config.rate_limit if client_config else 30

    def get_client_purpose(self, client_id: int) -> str:
        """Get the purpose/description for a client"""
        client_config = self.get_client_config(client_id)
        return client_config.description if client_config else "Unknown"

    def get_all_client_ids(self) -> List[int]:
        """Get list of all valid client IDs (1-9)"""
        return list(self.config.get_client_id_range())

    def get_critical_client_ids(self) -> List[int]:
        """Get list of critical client IDs that must be connected"""
        # UPDATED: Critical clients are now 1, 2, 3, 4 (was 0, 1, 2, 3)
        return [1, 2, 3, 4]

    def get_order_execution_client_id(self) -> int:
        """Get the client ID used for order execution"""
        return 2  # UPDATED: Order execution is now Client 2 (was Client 1)

    def get_administrative_client_id(self) -> int:
        """Get the client ID used for administrative tasks"""
        return 1  # UPDATED: Administrative is now Client 1 (was Client 0)

    def is_maintenance_window(self) -> bool:
        """
        Check if in IB maintenance window (Eastern time).

        IB typically performs maintenance from 11:45 PM to 12:15 AM ET.

        Returns:
            True if in maintenance window
        """
        eastern = self.config.tz
        now_et = datetime.now(eastern).time()

        # Maintenance window: 11:45 PM - 12:15 AM ET
        maintenance_start = time(23, 45)  # 11:45 PM
        maintenance_end = time(0, 15)  # 12:15 AM

        if maintenance_start <= maintenance_end:
            # Same day
            return maintenance_start <= now_et <= maintenance_end
        else:
            # Crosses midnight
            return now_et >= maintenance_start or now_et <= maintenance_end

    def should_auto_restart(self) -> bool:
        """
        Check if auto-restart should occur.

        Returns:
            True if should restart
        """
        eastern = self.config.tz
        now_et = datetime.now(eastern).time()

        # Parse auto-restart time
        restart_hour, restart_minute = map(int, self.config.auto_restart_time.split(":"))
        restart_time = time(restart_hour, restart_minute)

        # Check if within 5 minutes of restart time
        restart_datetime = datetime.combine(datetime.now(eastern).date(), restart_time)
        restart_datetime = eastern.localize(restart_datetime)
        now_datetime = datetime.now(eastern)

        time_diff = abs((now_datetime - restart_datetime).total_seconds())

        return time_diff <= 300  # Within 5 minutes

    def validate_client_connections(self, connected_clients: List[int]) -> Dict[str, Any]:
        """
        Validate client connections against requirements.

        Args:
            connected_clients: List of connected client IDs

        Returns:
            Validation results dictionary
        """
        critical_clients = self.get_critical_client_ids()
        all_clients = self.get_all_client_ids()

        critical_connected = [c for c in connected_clients if c in critical_clients]
        critical_missing = [c for c in critical_clients if c not in connected_clients]

        return {
            "total_connected": len(connected_clients),
            "total_required": len(all_clients),
            "critical_connected": len(critical_connected),
            "critical_required": len(critical_clients),
            "critical_missing": critical_missing,
            "order_execution_connected": self.get_order_execution_client_id() in connected_clients,
            "administrative_connected": self.get_administrative_client_id() in connected_clients,
            "is_healthy": len(critical_missing) == 0,
            "health_percentage": (len(connected_clients) / len(all_clients)) * 100,
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_gateway_manager(config_path: Optional[Path] = None) -> GatewayManager:
    """
    Create gateway manager with configuration.

    Args:
        config_path: Optional path to configuration file

    Returns:
        GatewayManager instance
    """
    config = load_config(config_path)
    return GatewayManager(config)


def validate_environment() -> Dict[str, Any]:
    """
    Validate environment for gateway operation.

    Returns:
        Validation results
    """
    results = {
        "ib_credentials": bool(os.getenv("IB_USERNAME") and os.getenv("IB_PASSWORD")),
        "java_available": False,
        "memory_sufficient": False,
        "ports_available": [],
        "timezone_valid": False,
    }

    # Check Java availability
    try:
        import subprocess

        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        results["java_available"] = result.returncode == 0
    except Exception:
        results["java_available"] = False

    # Check memory
    try:
        import psutil

        available_mb = psutil.virtual_memory().available // (1024 * 1024)
        results["memory_sufficient"] = available_mb >= DEFAULT_JAVA_MEMORY_MB
        results["available_memory_mb"] = available_mb
    except Exception:
        results["memory_sufficient"] = None

    # Check timezone
    try:
        eastern = pytz.timezone("US/Eastern")
        results["timezone_valid"] = True
        results["current_time_et"] = datetime.now(eastern).isoformat()
    except Exception:
        results["timezone_valid"] = False

    return results


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


def main():
    """Main execution for testing and demonstration"""
    print("🚀 SPYDER B13 - Gateway Configuration (UPDATED: CLIENTS 1-9)")
    print("=" * 70)

    try:
        # Create default configuration
        config = get_default_config()
        print(f"✅ Configuration created:")
        print(f"   Trading Mode: {config.trading_mode.value}")
        print(f"   Client ID Range: {config.min_client_id}-9")
        print(f"   Master Client: {config.master_client_id}")
        print(f"   Java Memory: {config.java_memory_mb}MB")
        print(f"   API Port: {config.get_current_api_port()}")

        # Print client allocation
        print_client_allocation_summary()

        # Create gateway manager
        manager = GatewayManager(config)
        print(f"\n✅ Gateway Manager created")

        # Test client configuration access
        print(f"\n🔧 Testing client configuration access:")
        for client_id in [1, 2, 3, 9]:
            client_config = manager.get_client_config(client_id)
            if client_config:
                print(
                    f"   Client {client_id}: {client_config.purpose.value} - {client_config.description}"
                )
            else:
                print(f"   Client {client_id}: Not found")

        # Test validation
        print(f"\n🔍 Environment validation:")
        validation = validate_environment()
        for key, value in validation.items():
            status = "✅" if value else "❌"
            print(f"   {status} {key}: {value}")

        # Test client connection validation
        print(f"\n📊 Testing client connection validation:")
        connected_clients = [1, 2, 3, 5, 7, 9]  # Simulate some connected clients
        validation_results = manager.validate_client_connections(connected_clients)

        print(
            f"   Connected: {validation_results['total_connected']}/{validation_results['total_required']}"
        )
        print(
            f"   Critical: {validation_results['critical_connected']}/{validation_results['critical_required']}"
        )
        print(
            f"   Order Execution: {
                '✅' if validation_results['order_execution_connected'] else '❌'}"
        )
        print(
            f"   Administrative: {
                '✅' if validation_results['administrative_connected'] else '❌'}"
        )
        print(f"   Health: {validation_results['health_percentage']:.1f}%")
        print(f"   Status: {'✅ HEALTHY' if validation_results['is_healthy'] else '⚠️ DEGRADED'}")

        if validation_results["critical_missing"]:
            print(f"   Missing Critical: {validation_results['critical_missing']}")

        print(f"\n🎯 Configuration test completed successfully!")

    except Exception as e:
        print(f"❌ Error in main: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
