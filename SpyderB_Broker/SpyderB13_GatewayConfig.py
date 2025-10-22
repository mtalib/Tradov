#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB13_GatewayConfig.py
Purpose: Enhanced IB Gateway configuration and management (Merged with B19)
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-11 Time: 17:00:00

Module Description:
    Comprehensive IB Gateway configuration manager that merges the best
    features from SpyderB13_GatewayConfig and SpyderB19_GatewayConfiguration.
    Provides production-ready gateway configuration, automated setup, version
    validation, and advanced connection stability features for autonomous trading.
    IB Gateway 10.39 specific features have been removed.

Key Features (Merged from B13 + B19):
    - Complete client allocation strategy (Clients 1-10) from B13
    - Enhanced configuration validation and migration from B19
    - JVM optimization and memory management from B19
    - Environment variable management and automation from B19
    - Production-ready stability enhancements from B19
    - Comprehensive logging and error handling
    - Docker and systemd integration support
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import logging
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# ==============================================================================
# THIRD-PARTY IMPORTS WITH FALLBACKS
# ==============================================================================
try:
    import pytz

    HAS_PYTZ = True
except ImportError:
    print("WARNING: pytz not available - using basic timezone handling")
    HAS_PYTZ = False

# ==============================================================================
# LOCAL IMPORTS WITH FALLBACKS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

    HAS_LOGGER = True
except ImportError:
    print("WARNING: SpyderLogger not available - using basic logging")
    HAS_LOGGER = False

    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)


try:
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    HAS_ERROR_HANDLER = True
except ImportError:
    print("WARNING: SpyderErrorHandler not available - using basic error handling")
    HAS_ERROR_HANDLER = False

    class SpyderErrorHandler:
        def handle_error(self, error, context=""):
            print(f"ERROR in {context}: {error}")


# ==============================================================================
# CONSTANTS - ENHANCED FROM B19
# ==============================================================================
# IB Gateway Configuration
IB_GATEWAY_VERSION = "10.37"
TWS_MAJOR_VRSN = "1037"  # Internal version for 10.37
TWS_BUILD_VERSION = "10.37.1l"  # Latest stable build

# Directory Paths (B19 enhanced)
IB_GATEWAY_DIR = Path.home() / "Jts" / "ibgateway" / TWS_MAJOR_VRSN
IBC_DIR = Path.home() / "ibc"
LOG_DIR = Path.home() / "spyder_logs" / "gateway"

# Default configuration values (B13 + B19 merged)
DEFAULT_JAVA_MEMORY_MB = 8192  # 8GB for 10 clients (increased from B13)
DEFAULT_API_PORT_PAPER = 4002
DEFAULT_API_PORT_LIVE = 4001
DEFAULT_IBC_CONTROL_PORT = 4000
DEFAULT_MAX_CLIENT_ID = 10  # FIXED: Max client ID for 1-10 range
DEFAULT_GATEWAY_SERVER = "zdc1.ibllc.com"  # Zurich server

# Enhanced Connection Parameters from B19
CONNECTION_PARAMS = {
    "connection_timeout": 60,  # Increased from 4 seconds
    "request_timeout": 30,
    "message_timeout": 120,
    "reconnect_delay": 10,
    "max_reconnect_attempts": 5,
    "exponential_backoff": True,
    "initial_sync_timeout": 90,  # For reqExecutionsAsync issues
    "heartbeat_interval": 30,
    "health_check_interval": 60,
}

# JVM Configuration - OPTIMIZED FOR IB Gateway (from B19)
JVM_CONFIG = {
    "heap_min": "1024m",
    "heap_max": "4096m",  # 4GB recommended
    "permgen": "256m",
    "gc_type": "G1GC",
    "gc_options": [
        "-XX:+UseG1GC",
        "-XX:G1HeapRegionSize=32m",
        "-XX:+UnlockExperimentalVMOptions",
        "-XX:+UseCGroupMemoryLimitForHeap",
        "-XX:MaxGCPauseMillis=200",
        "-XX:+DisableExplicitGC",
    ],
    "jvm_options": [
        "-server",
        "-Djava.awt.headless=true",
        "-Dsun.java2d.noddraw=true",
        "-Dswing.aatext=true",
        "-Djava.net.preferIPv4Stack=true",
    ],
}

# Environment Variables (from B19)
REQUIRED_ENV_VARS = {
    "TWS_MAJOR_VRSN": TWS_MAJOR_VRSN,
    "IB_GATEWAY_VERSION": IB_GATEWAY_VERSION,
    "DISPLAY": ":0",
    "TZ": "America/New_York",
}

# Auto-restart time (before IB maintenance window)
AUTO_RESTART_TIME = "03:45"  # 3:45 AM Eastern

# ==============================================================================
# ENUMS (FROM B13)
# ==============================================================================


class TradingMode(str, Enum):
    """Trading mode enumeration."""

    PAPER = "paper"
    LIVE = "live"


class ClientPurpose(str, Enum):
    """Purpose of each client connection - FIXED ALLOCATION (1-10)."""

    ORDER_EXECUTION = "Order Execution - HIGHEST PRIORITY"
    ADMINISTRATIVE = "Account Management"
    CORE_DATA = "Core Market Data"
    SPY_OPTIONS = "SPY Options Chains"
    VOLATILITY = "Volatility Indicators"
    MARKET_INTERNALS = "Market Internals"
    MAJOR_INDICES = "Major Index ETFs"
    EXTENDED_ASSETS = "Extended Market Data"
    SECTOR_ETFS = "Sector ETFs"
    INTERNATIONAL = "International Markets"


class ConfigurationStatus(Enum):
    """Configuration validation status (from B19)."""

    VALID = "valid"
    INVALID = "invalid"
    NEEDS_MIGRATION = "needs_migration"
    NEEDS_SETUP = "needs_setup"


# ==============================================================================
# ENHANCED DATA STRUCTURES (B13 + B19 MERGED)
# ==============================================================================


@dataclass
class ClientConfig:
    """Configuration for a single client connection (from B13)."""

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
    """
    Enhanced IB Gateway configuration with stability enhancements.
    Merges features from B13 and B19 for comprehensive gateway management.
    """

    # Authentication (B13 + B19)
    ib_username: str = field(default_factory=lambda: os.getenv("IB_USERNAME", ""))
    ib_password: str = field(default_factory=lambda: os.getenv("IB_PASSWORD", ""))
    trading_mode: TradingMode = TradingMode.PAPER

    # Connection settings (B13 enhanced with B19)
    api_port_paper: int = DEFAULT_API_PORT_PAPER
    api_port_live: int = DEFAULT_API_PORT_LIVE
    ibc_control_port: int = DEFAULT_IBC_CONTROL_PORT
    gateway_server: str = DEFAULT_GATEWAY_SERVER

    # Client configuration (B13)
    min_client_id: int = 1  # FIXED: Start from 1
    max_client_id: int = DEFAULT_MAX_CLIENT_ID  # FIXED: 10 clients total
    master_client_id: int = 1  # Order execution client

    # Enhanced connection parameters (from B19)
    connection_timeout: int = CONNECTION_PARAMS["connection_timeout"]
    request_timeout: int = CONNECTION_PARAMS["request_timeout"]
    message_timeout: int = CONNECTION_PARAMS["message_timeout"]
    reconnect_delay: int = CONNECTION_PARAMS["reconnect_delay"]
    max_reconnect_attempts: int = CONNECTION_PARAMS["max_reconnect_attempts"]

    # JVM Configuration (from B19)
    java_memory_mb: int = DEFAULT_JAVA_MEMORY_MB
    java_heap_min: str = JVM_CONFIG["heap_min"]
    java_heap_max: str = JVM_CONFIG["heap_max"]
    gc_type: str = JVM_CONFIG["gc_type"]

    # Paths and directories (B19 enhanced)
    log_dir: Path = field(default_factory=lambda: LOG_DIR)
    ibc_path: str = str(IBC_DIR)
    gateway_dir: str = str(IB_GATEWAY_DIR)

    # Automation settings (B19)
    auto_restart_enabled: bool = True
    auto_restart_time: str = AUTO_RESTART_TIME
    enable_xvfb: bool = True
    xvfb_display: str = ":0"

    # Monitoring and logging (B19)
    log_level: str = "INFO"
    enable_detailed_logging: bool = True
    log_retention_days: int = 30
    enable_performance_monitoring: bool = True

    # Timezone (B13)
    timezone: str = "US/Eastern"
    tz: Optional[pytz.BaseTzInfo] = field(default=None, init=False)

    def __post_init__(self):
        """Initialize timezone and validate configuration."""
        if HAS_PYTZ:
            self.tz = pytz.timezone(self.timezone)

        # Ensure log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Validate client ID range
        if self.max_client_id < self.min_client_id:
            raise ValueError("max_client_id must be >= min_client_id")

        if (
            self.master_client_id < self.min_client_id
            or self.master_client_id > self.max_client_id
        ):
            raise ValueError("master_client_id must be within client ID range")

    def get_current_api_port(self) -> int:
        """Get the current API port based on trading mode."""
        return (
            self.api_port_paper
            if self.trading_mode == TradingMode.PAPER
            else self.api_port_live
        )

    def get_java_options(self) -> List[str]:
        """Get complete Java options for gateway startup (from B19)."""
        options = [
            f"-Xms{self.java_heap_min}",
            f"-Xmx{self.java_heap_max}",
            f"-XX:PermSize={JVM_CONFIG['permgen']}",
        ]

        # Add GC options
        options.extend(JVM_CONFIG["gc_options"])

        # Add JVM options
        options.extend(JVM_CONFIG["jvm_options"])

        return options

    def get_environment_variables(self) -> Dict[str, str]:
        """Get required environment variables (from B19)."""
        env_vars = REQUIRED_ENV_VARS.copy()
        env_vars.update(
            {
                "IB_USERNAME": self.ib_username,
                "IB_PASSWORD": self.ib_password,
                "TRADING_MODE": self.trading_mode.value.upper(),
                "API_PORT": str(self.get_current_api_port()),
                "JAVA_OPTS": " ".join(self.get_java_options()),
            }
        )
        return env_vars

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        config_dict = asdict(self)
        # Convert Path to string
        config_dict["log_dir"] = str(self.log_dir)
        # Convert enum to string
        config_dict["trading_mode"] = self.trading_mode.value
        return config_dict

    def save_to_file(self, filepath: Path):
        """Save configuration to JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: Path) -> "GatewayConfig":
        """Load configuration from JSON file."""
        with open(filepath, "r") as f:
            config_dict = json.load(f)

        # Convert strings back to proper types
        config_dict["trading_mode"] = TradingMode(config_dict["trading_mode"])
        config_dict["log_dir"] = Path(config_dict["log_dir"])
        # Remove tz string (will be recreated in __post_init__)
        config_dict.pop("tz", None)

        return cls(**config_dict)


@dataclass
class ValidationResult:
    """Configuration validation result (from B19)."""

    status: ConfigurationStatus
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return self.status == ConfigurationStatus.VALID

    @property
    def needs_action(self) -> bool:
        """Check if configuration needs action."""
        return self.status in [
            ConfigurationStatus.NEEDS_MIGRATION,
            ConfigurationStatus.NEEDS_SETUP,
        ]


# ==============================================================================
# CLIENT ALLOCATION CONFIGURATION (FROM B13)
# ==============================================================================


def get_client_allocation() -> Dict[int, ClientConfig]:
    """
    Get the complete 10-client allocation strategy.

    FIXED: Client IDs now range from 1-10 to match SpyderB08_MultiClientDataManager.py.
    """
    return {
        1: ClientConfig(
            client_id=1,
            purpose=ClientPurpose.ORDER_EXECUTION,
            symbols=["SPY"],  # Focus on primary trading instrument
            frequency=0.1,  # Ultra-fast updates
            description="Order execution - HIGHEST PRIORITY",
            priority="CRITICAL",
            update_interval=0.1,
            rate_limit=50,
        ),
        2: ClientConfig(
            client_id=2,
            purpose=ClientPurpose.ADMINISTRATIVE,
            symbols=[],  # No specific symbols - account management
            frequency=5.0,
            description="Account management and system control",
            priority="HIGH",
            update_interval=5.0,
            rate_limit=30,
        ),
        3: ClientConfig(
            client_id=3,
            purpose=ClientPurpose.CORE_DATA,
            symbols=["SPY", "SPX", "/ES", "VIX", "TICK-NYSE"],
            frequency=1.0,
            description="Core market data - real-time (1s)",
            priority="HIGH",
            update_interval=1.0,
            rate_limit=40,
        ),
        4: ClientConfig(
            client_id=4,
            purpose=ClientPurpose.SPY_OPTIONS,
            symbols=["SPY_OPTIONS_0DTE", "SPY_OPTIONS_1DTE"],
            frequency=1.0,
            description="SPY options chains - 0DTE/1DTE (1s)",
            priority="HIGH",
            update_interval=1.0,
            rate_limit=35,
        ),
        5: ClientConfig(
            client_id=5,
            purpose=ClientPurpose.VOLATILITY,
            symbols=["VIX9D", "VXV", "VXMT", "VVIX", "UVXY"],
            frequency=5.0,
            description="Volatility indicators - 5s updates",
            priority="MEDIUM",
            update_interval=5.0,
            rate_limit=30,
        ),
        6: ClientConfig(
            client_id=6,
            purpose=ClientPurpose.MARKET_INTERNALS,
            symbols=["TRIN-NYSE", "ADD-NYSE", "CPC-CBOE", "PCALL-CBOE", "SKEW", "VUD"],
            frequency=5.0,
            description="Market internals and breadth - 5s updates",
            priority="MEDIUM",
            update_interval=5.0,
            rate_limit=30,
        ),
        7: ClientConfig(
            client_id=7,
            purpose=ClientPurpose.MAJOR_INDICES,
            symbols=["DIA", "QQQ", "IWM", "DIA_OPTIONS_1DTE", "QQQ_OPTIONS_1DTE"],
            frequency=5.0,
            description="Major indices + 1DTE options - 5s updates",
            priority="MEDIUM",
            update_interval=5.0,
            rate_limit=30,
        ),
        8: ClientConfig(
            client_id=8,
            purpose=ClientPurpose.EXTENDED_ASSETS,
            symbols=["TLT", "LQD", "DXY", "GLD", "SPY_OPTIONS_WEEKLY"],
            frequency=15.0,
            description="Extended assets - 15-30s updates",
            priority="LOW",
            update_interval=15.0,
            rate_limit=20,
        ),
        9: ClientConfig(
            client_id=9,
            purpose=ClientPurpose.SECTOR_ETFS,
            symbols=[
                "XLF",
                "XLK",
                "XLE",
                "XLV",
                "XLI",
                "XLY",
                "XLP",
                "XLU",
                "XLRE",
                "XLC",
                "XLB",
            ],
            frequency=30.0,
            description="Sector ETFs - 30-60s updates",
            priority="LOW",
            update_interval=30.0,
            rate_limit=15,
        ),
        10: ClientConfig(
            client_id=10,
            purpose=ClientPurpose.INTERNATIONAL,
            symbols=["FTLC", "AUD.JPY", "DAX", "HSI", "EWJ", "EWG", "EWU", "EWC"],
            frequency=60.0,
            description="International markets - 60s updates",
            priority="BATCH",
            update_interval=60.0,
            rate_limit=10,
        ),
    }


# ==============================================================================
# ENHANCED GATEWAY MANAGER (B13 + B19 MERGED)
# ==============================================================================


class GatewayManager:
    """
    Enhanced Gateway configuration manager.
    Merges functionality from B13 and B19 for comprehensive gateway management.
    """

    def __init__(self, config: GatewayConfig):
        """Initialize gateway manager with enhanced configuration."""
        self.config = config
        self.logger = (
            SpyderLogger.get_logger(__name__)
            if HAS_LOGGER
            else logging.getLogger(__name__)
        )
        self.error_handler = SpyderErrorHandler() if HAS_ERROR_HANDLER else None

        # Client configurations
        self.client_configs = get_client_allocation()

        # Ensure directories exist (from B19)
        self._create_directories()

        self.logger.info(
            f"GatewayManager initialized for {config.trading_mode.value} mode"
        )

    def _create_directories(self):
        """Create required directories (from B19)."""
        dirs = [
            Path(self.config.log_dir),
            Path(self.config.ibc_path),
            Path(self.config.gateway_dir),
        ]

        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def get_client_config(self, client_id: int) -> Optional[ClientConfig]:
        """Get configuration for a specific client."""
        return self.client_configs.get(client_id)

    def get_critical_clients(self) -> List[int]:
        """Get list of critical client IDs."""
        return [
            client_id
            for client_id, config in self.client_configs.items()
            if config.priority in ["CRITICAL", "HIGH"]
        ]

    def validate_client_connections(
        self, connected_clients: List[int]
    ) -> Dict[str, Any]:
        """
        Validate client connection status.

        Args:
            connected_clients: List of currently connected client IDs

        Returns:
            Validation results dictionary
        """
        critical_clients = self.get_critical_clients()
        critical_connected = [c for c in connected_clients if c in critical_clients]
        critical_missing = [c for c in critical_clients if c not in connected_clients]

        total_required = len(self.client_configs)
        total_connected = len(connected_clients)
        health_percentage = (total_connected / total_required) * 100

        return {
            "total_connected": total_connected,
            "total_required": total_required,
            "critical_connected": len(critical_connected),
            "critical_required": len(critical_clients),
            "critical_missing": critical_missing,
            "health_percentage": health_percentage,
            "is_healthy": len(critical_missing) == 0 and health_percentage >= 70,
            "order_execution_connected": 1 in connected_clients,
            "administrative_connected": 2 in connected_clients,
        }

    def validate_installation(self) -> ValidationResult:
        """
        Validate IB Gateway installation (enhanced from B19).

        Returns:
            ValidationResult with detailed status
        """
        issues = []
        warnings = []
        recommendations = []

        # Check Gateway directory
        gateway_dir = Path(self.config.gateway_dir)
        if not gateway_dir.exists():
            issues.append(f"Gateway directory not found: {gateway_dir}")

        # Check IBC directory
        ibc_dir = Path(self.config.ibc_path)
        if not ibc_dir.exists():
            warnings.append(f"IBC directory not found: {ibc_dir}")
            recommendations.append("Install IBController for automated login")

        # Check Java installation
        try:
            result = subprocess.run(
                ["java", "-version"], capture_output=True, text=True
            )
            if result.returncode != 0:
                issues.append("Java not found or not working")
        except FileNotFoundError:
            issues.append("Java not installed")

        # Check environment variables
        for var, expected_value in REQUIRED_ENV_VARS.items():
            current_value = os.getenv(var)
            if current_value != expected_value:
                warnings.append(f"Environment variable {var} not set correctly")

        # Check credentials
        if not self.config.ib_username:
            warnings.append("IB username not configured")
        if not self.config.ib_password:
            warnings.append("IB password not configured")

        # Determine status
        if issues:
            status = ConfigurationStatus.NEEDS_SETUP
        elif warnings:
            status = ConfigurationStatus.NEEDS_MIGRATION
        else:
            status = ConfigurationStatus.VALID

        return ValidationResult(
            status=status,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
        )

    def apply_environment_variables(self) -> bool:
        """Apply required environment variables (from B19)."""
        try:
            env_vars = self.config.get_environment_variables()
            for var, value in env_vars.items():
                os.environ[var] = value
                self.logger.debug(f"Set environment variable: {var}={value}")

            return True
        except Exception as e:
            if self.error_handler:
                self.error_handler.handle_error(e, "apply_environment_variables")
            return False

    def generate_startup_command(self) -> List[str]:
        """Generate gateway startup command (from B19)."""
        java_opts = self.config.get_java_options()

        cmd = [
            "java",
            *java_opts,
            "-cp",
            f"{self.config.gateway_dir}/*",
            "ibgateway.GWClient",
        ]

        return cmd


# ==============================================================================
# FACTORY FUNCTIONS AND UTILITIES
# ==============================================================================


def get_default_config() -> GatewayConfig:
    """Create default gateway configuration for 10-client setup (1-10)."""
    return GatewayConfig()


def create_default_config() -> GatewayConfig:
    """Alias for get_default_config() for backward compatibility."""
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


def validate_environment() -> Dict[str, bool]:
    """
    Validate runtime environment (enhanced from B19).

    Returns:
        Dictionary of validation results
    """
    results = {}

    # Check Java
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        results["java_available"] = result.returncode == 0
    except FileNotFoundError:
        results["java_available"] = False

    # Check required directories
    results["gateway_dir_exists"] = IB_GATEWAY_DIR.exists()
    results["ibc_dir_exists"] = IBC_DIR.exists()
    results["log_dir_writable"] = LOG_DIR.parent.exists()

    # Check environment variables
    results["env_vars_set"] = all(
        os.getenv(var) is not None for var in REQUIRED_ENV_VARS.keys()
    )

    # Check system resources
    try:
        import psutil

        memory_gb = psutil.virtual_memory().total / (1024**3)
        results["sufficient_memory"] = memory_gb >= 8  # 8GB minimum
    except ImportError:
        results["sufficient_memory"] = True  # Assume sufficient if can't check

    return results


def print_client_allocation_summary():
    """Print summary of client allocation strategy (1-10)."""
    clients = get_client_allocation()

    print("\n" + "=" * 80)
    print("SPYDER CLIENT ALLOCATION STRATEGY (ENHANCED: CLIENTS 1-10)")
    print("=" * 80)

    print("PRIORITY ORDER:")
    priority_order = [
        (1, "ORDER EXECUTION", "CRITICAL - Fastest trading execution"),
        (2, "ADMINISTRATIVE", "SYSTEM - Account & control"),
        (3, "CORE DATA", "HIGH - SPY, VIX real-time (1s)"),
        (4, "SPY OPTIONS", "HIGH - 0DTE/1DTE options (1s)"),
        (5, "VOLATILITY", "NORMAL - Volatility surface (5s)"),
        (6, "MARKET INTERNALS", "NORMAL - Market breadth + VUD (5s)"),
        (7, "MAJOR INDICES", "NORMAL - DIA/QQQ/IWM (5s)"),
        (8, "EXTENDED ASSETS", "LOW - Bonds/FX/Commodities (15s)"),
        (9, "SECTOR ETFS", "LOW - Sector rotation (30s)"),
        (10, "INTERNATIONAL", "BATCH - Global markets (60s)"),
    ]

    for client_id, name, desc in priority_order:
        config = clients[client_id]
        symbols_count = len(config.symbols)
        print(
            f"  Client {client_id:2d}: {name:20s} | {desc:35s} | {symbols_count:2d} symbols"
        )

    print("\nTOTAL RATE LIMITS:")
    total_rate_limit = sum(config.rate_limit for config in clients.values())
    print(f"  Combined: {total_rate_limit} requests/second across all clients")

    print("\nCRITICAL CLIENTS (Must be connected):")
    critical = [c for c in clients.values() if c.priority in ["CRITICAL", "HIGH"]]
    for client in critical:
        print(f"  Client {client.client_id}: {client.purpose.value}")


# ==============================================================================
# MODULE TEST AND VALIDATION
# ==============================================================================

if __name__ == "__main__":
    """Enhanced configuration test and demonstration."""
    print("SPYDER B13 - Enhanced Gateway Configuration (Merged B13+B19)")
    print("=" * 70)

    try:
        # Create default configuration
        config = get_default_config()
        print(f"Configuration created:")
        print(f"   Trading Mode: {config.trading_mode.value}")
        print(f"   Client ID Range: {config.min_client_id}-{config.max_client_id}")
        print(f"   Master Client: {config.master_client_id} (Order Execution)")
        print(f"   Java Memory: {config.java_memory_mb}MB")
        print(f"   API Port: {config.get_current_api_port()}")
        print(f"   Gateway Version: {IB_GATEWAY_VERSION}")

        # Print client allocation
        print_client_allocation_summary()

        # Create enhanced gateway manager
        manager = GatewayManager(config)
        print(f"\nEnhanced Gateway Manager created")

        # Test validation
        print(f"\nInstallation Validation:")
        validation = manager.validate_installation()
        print(f"   Status: {validation.status.value}")
        if validation.issues:
            print(f"   Issues: {len(validation.issues)}")
            for issue in validation.issues:
                print(f"     - {issue}")
        if validation.warnings:
            print(f"   Warnings: {len(validation.warnings)}")
            for warning in validation.warnings:
                print(f"     - {warning}")

        # Test environment validation
        print(f"\nEnvironment Validation:")
        env_validation = validate_environment()
        for key, value in env_validation.items():
            status = "✅" if value else "❌"
            print(f"   {status} {key}: {value}")

        # Test client connection validation
        print(f"\nClient Connection Validation:")
        connected_clients = [1, 2, 3, 5, 7, 9, 10]  # Simulate some connected clients
        validation_results = manager.validate_client_connections(connected_clients)

        print(
            f"   Connected: {validation_results['total_connected']}/{validation_results['total_required']}"
        )
        print(
            f"   Critical: {validation_results['critical_connected']}/{validation_results['critical_required']}"
        )
        print(f"   Health: {validation_results['health_percentage']:.1f}%")
        print(
            f"   Status: {'HEALTHY' if validation_results['is_healthy'] else 'DEGRADED'}"
        )

        # Test Java options
        print(f"\nJava Configuration:")
        java_opts = config.get_java_options()
        print(f"   Java Options ({len(java_opts)}):")
        for opt in java_opts[:5]:  # Show first 5
            print(f"     {opt}")
        if len(java_opts) > 5:
            print(f"     ... and {len(java_opts) - 5} more")

        # Test environment variables
        print(f"\nEnvironment Variables:")
        env_vars = config.get_environment_variables()
        for key, value in list(env_vars.items())[:5]:  # Show first 5
            print(f"   {key}={value}")

        print(f"\nEnhanced configuration test completed successfully!")
        print(f"Ready to delete SpyderB19_GatewayConfiguration.py")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()

# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Enums
    "TradingMode",
    "ClientPurpose",
    "ConfigurationStatus",
    # Data structures
    "ClientConfig",
    "GatewayConfig",
    "ValidationResult",
    # Main class
    "GatewayManager",
    # Factory functions
    "get_default_config",
    "create_default_config",
    "load_config",
    "get_client_allocation",
    "validate_environment",
    # Utilities
    "print_client_allocation_summary",
]
