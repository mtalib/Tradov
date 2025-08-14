#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
SpyderB_Broker Package

This package handles all broker interactions with Interactive Brokers Gateway.
Version 2.0: Multi-client architecture with watchdog monitoring and Prometheus metrics.
Uses ib-insync library (NO IBAPI dependencies).
"""

# Version - Updated to 2.0 for multi-client architecture
__version__ = '2.0.0'


# Order Types
try:
    from .SpyderB00_OrderTypes import OrderRequest, OrderAction, OrderType, OrderStatus
    HAS_ORDER_TYPES = True
except ImportError:
    print('WARNING: OrderTypes not available')
    HAS_ORDER_TYPES = False

# ==============================================================================
# CORE CLIENT MODULES (B01-B07)
# ==============================================================================

# Main SpyderClient
try:
    from .SpyderB01_SpyderClient import SpyderClient, get_spyder_client
    HAS_SPYDER_CLIENT = True
except ImportError:
    print("WARNING: SpyderClient not available")
    HAS_SPYDER_CLIENT = False

# Order Manager
try:
    from .SpyderB02_OrderManager import OrderManager, create_order_manager
    HAS_ORDER_MANAGER = True
except ImportError:
    print("WARNING: OrderManager not available")
    HAS_ORDER_MANAGER = False

# Position Tracker
try:
    from .SpyderB03_PositionTracker import PositionTracker
    HAS_POSITION_TRACKER = True
except ImportError:
    print("WARNING: PositionTracker not available")
    HAS_POSITION_TRACKER = False

# Account Manager
try:
    from .SpyderB04_AccountManager import AccountManager, create_account_manager
    HAS_ACCOUNT_MANAGER = True
except ImportError:
    print("WARNING: AccountManager not available")
    HAS_ACCOUNT_MANAGER = False

# Connection Manager
try:
    from .SpyderB05_ConnectionManager import ConnectionManager, get_connection_manager, ConnectionConfig
    HAS_CONNECTION_MANAGER = True
except ImportError:
    print("WARNING: ConnectionManager not available")
    HAS_CONNECTION_MANAGER = False

# Contract Builder
try:
    from .SpyderB06_ContractBuilder import ContractBuilder
    HAS_CONTRACT_BUILDER = True
except ImportError:
    print("WARNING: ContractBuilder not available")
    HAS_CONTRACT_BUILDER = False

# Market Data Manager
try:
    # from .SpyderB07_MarketDataManager import MarketDataManager  # Temporarily disabled
    HAS_MARKET_DATA_MANAGER = False  # Temporarily disabled
except ImportError:
    print("WARNING: MarketDataManager not available")
    HAS_MARKET_DATA_MANAGER = False

# ==============================================================================
# MULTI-CLIENT ARCHITECTURE (B08-B12)
# ==============================================================================

# Multi-Client Data Manager
try:
    from .SpyderB08_MultiClientDataManager import (
        MultiClientDataManager, 
        get_manager_instance,
        ClientPurpose,
        ClientInfo
    )
    HAS_MULTI_CLIENT = True
except ImportError:
    print("WARNING: MultiClientDataManager not available")
    HAS_MULTI_CLIENT = False

# IB Client Portal
try:
    from .SpyderB09_IBClientPortal import IBClientPortal
    HAS_CLIENT_PORTAL = True
except ImportError:
    print("WARNING: IBClientPortal not available")
    HAS_CLIENT_PORTAL = False

# IB Data Types
try:
    from .SpyderB10_IBDataTypes import IBDataTypes
    HAS_IB_DATA_TYPES = True
except ImportError:
    print("WARNING: IBDataTypes not available")
    HAS_IB_DATA_TYPES = False

# AsyncIO Bridge
try:
    from .SpyderB11_AsyncIOBridge import AsyncIOBridge
    HAS_ASYNC_BRIDGE = True
except ImportError:
    print("WARNING: AsyncIOBridge not available")
    HAS_ASYNC_BRIDGE = False

# Gateway Automation
try:
    from .SpyderB12_GatewayAutomation import GatewayAutomation, create_gateway_automation
    HAS_GATEWAY_AUTOMATION = True
except ImportError:
    print("WARNING: GatewayAutomation not available")
    HAS_GATEWAY_AUTOMATION = False

# ==============================================================================
# STABILITY & MONITORING (B13-B16)
# ==============================================================================

# Gateway Configuration (B13)
try:
    from .SpyderB13_GatewayConfig import (
        GatewayConfig,
        GatewayConfigManager,
        TradingMode,
        ClientConfig,
        create_default_config,
        load_config
    )
    HAS_GATEWAY_CONFIG = True
except ImportError:
    print("WARNING: GatewayConfig not available")
    HAS_GATEWAY_CONFIG = False

# Multi-Client Watchdog (B14)
try:
    from .SpyderB14_MultiClientWatchdog import (
        MultiClientWatchdog,
        HealthStatus,
        ClientHealth,
        HealthMetrics,
        create_watchdog
    )
    HAS_WATCHDOG = True
except ImportError:
    print("WARNING: MultiClientWatchdog not available")
    HAS_WATCHDOG = False

# Prometheus Metrics (B15)
try:
    from .SpyderB15_PrometheusMetrics import (
        PrometheusMetricsCollector,
        MetricsConfig,
        ClientMetrics,
        create_metrics_collector
    )
    HAS_PROMETHEUS = True
except ImportError:
    print("WARNING: PrometheusMetrics not available")
    HAS_PROMETHEUS = False

# Gateway Integration (B16)
try:
    from .SpyderB16_GatewayIntegration import (
        GatewayIntegrationOrchestrator,
        IntegrationStatus,
        StartupOptions
    )
    HAS_INTEGRATION = True
except ImportError:
    print("WARNING: GatewayIntegration not available")
    HAS_INTEGRATION = False

# ==============================================================================
# SPECIALIZED MODULES (B17+)
# ==============================================================================

# SPY Options Chain Manager (B17)
try:
    from .SpyderB17_SPYOptionsChainManager import SPYOptionsChainManager
    HAS_OPTIONS_CHAIN = True
except ImportError:
    print("WARNING: SPYOptionsChainManager not available")
    HAS_OPTIONS_CHAIN = False

# ==============================================================================
# TYPE ALIASES
# ==============================================================================
TickerId = int

# ==============================================================================
# PUBLIC API
# ==============================================================================
__all__ = [
    # Version
    '__version__',
    
    # Core Client Modules
    'SpyderClient',
    'get_spyder_client',
    'OrderManager',
    'create_order_manager',
    'PositionTracker',
    'AccountManager',
    'create_account_manager',
    'ConnectionManager',
    'get_connection_manager',
    'ConnectionConfig',
    'ContractBuilder',
    'MarketDataManager',
    
    # Multi-Client Architecture
    'MultiClientDataManager',
    'get_manager_instance',
    'ClientPurpose',
    'ClientInfo',
    'IBClientPortal',
    'IBDataTypes',
    'AsyncIOBridge',
    'GatewayAutomation',
    'create_gateway_automation',
    
    # Stability & Monitoring
    'GatewayConfig',
    'GatewayConfigManager',
    'TradingMode',
    'ClientConfig',
    'create_default_config',
    'load_config',
    'MultiClientWatchdog',
    'HealthStatus',
    'ClientHealth',
    'HealthMetrics',
    'create_watchdog',
    'PrometheusMetricsCollector',
    'MetricsConfig',
    'ClientMetrics',
    'create_metrics_collector',
    'GatewayIntegrationOrchestrator',
    'IntegrationStatus',
    'StartupOptions',
    
    # Specialized Modules
    'SPYOptionsChainManager',
    
    # Type Aliases
    'TickerId',
]

# ==============================================================================
# CONDITIONAL EXPORTS (Feature Flags)
# ==============================================================================

# Core modules
if HAS_SPYDER_CLIENT:
    __all__.append('HAS_SPYDER_CLIENT')
if HAS_ORDER_MANAGER:
    __all__.append('HAS_ORDER_MANAGER')
if HAS_POSITION_TRACKER:
    __all__.append('HAS_POSITION_TRACKER')
if HAS_ACCOUNT_MANAGER:
    __all__.append('HAS_ACCOUNT_MANAGER')
if HAS_CONNECTION_MANAGER:
    __all__.append('HAS_CONNECTION_MANAGER')
if HAS_CONTRACT_BUILDER:
    __all__.append('HAS_CONTRACT_BUILDER')
if HAS_MARKET_DATA_MANAGER:
    __all__.append('HAS_MARKET_DATA_MANAGER')

# Multi-client modules
if HAS_MULTI_CLIENT:
    __all__.append('HAS_MULTI_CLIENT')
if HAS_CLIENT_PORTAL:
    __all__.append('HAS_CLIENT_PORTAL')
if HAS_IB_DATA_TYPES:
    __all__.append('HAS_IB_DATA_TYPES')
if HAS_ASYNC_BRIDGE:
    __all__.append('HAS_ASYNC_BRIDGE')
if HAS_GATEWAY_AUTOMATION:
    __all__.append('HAS_GATEWAY_AUTOMATION')

# Stability modules
if HAS_GATEWAY_CONFIG:
    __all__.append('HAS_GATEWAY_CONFIG')
if HAS_WATCHDOG:
    __all__.append('HAS_WATCHDOG')
if HAS_PROMETHEUS:
    __all__.append('HAS_PROMETHEUS')
if HAS_INTEGRATION:
    __all__.append('HAS_INTEGRATION')

# Specialized modules
if HAS_OPTIONS_CHAIN:
    __all__.append('HAS_OPTIONS_CHAIN')

# ==============================================================================
# PACKAGE INFO
# ==============================================================================

def get_package_info():
    """Get package information and module availability"""
    info = {
        'version': __version__,
        'modules': {
            'core': {
                'SpyderClient': HAS_SPYDER_CLIENT,
                'OrderManager': HAS_ORDER_MANAGER,
                'PositionTracker': HAS_POSITION_TRACKER,
                'AccountManager': HAS_ACCOUNT_MANAGER,
                'ConnectionManager': HAS_CONNECTION_MANAGER,
                'ContractBuilder': HAS_CONTRACT_BUILDER,
                'MarketDataManager': HAS_MARKET_DATA_MANAGER,
            },
            'multi_client': {
                'MultiClientDataManager': HAS_MULTI_CLIENT,
                'IBClientPortal': HAS_CLIENT_PORTAL,
                'IBDataTypes': HAS_IB_DATA_TYPES,
                'AsyncIOBridge': HAS_ASYNC_BRIDGE,
                'GatewayAutomation': HAS_GATEWAY_AUTOMATION,
            },
            'stability': {
                'GatewayConfig': HAS_GATEWAY_CONFIG,
                'MultiClientWatchdog': HAS_WATCHDOG,
                'PrometheusMetrics': HAS_PROMETHEUS,
                'GatewayIntegration': HAS_INTEGRATION,
            },
            'specialized': {
                'SPYOptionsChainManager': HAS_OPTIONS_CHAIN,
            }
        }
    }
    return info

# Print module availability on import
if __name__ != '__main__':
    available = sum([
        HAS_SPYDER_CLIENT, HAS_ORDER_MANAGER, HAS_POSITION_TRACKER,
        HAS_ACCOUNT_MANAGER, HAS_CONNECTION_MANAGER, HAS_CONTRACT_BUILDER,
        HAS_MARKET_DATA_MANAGER, HAS_MULTI_CLIENT, HAS_CLIENT_PORTAL,
        HAS_IB_DATA_TYPES, HAS_ASYNC_BRIDGE, HAS_GATEWAY_AUTOMATION,
        HAS_GATEWAY_CONFIG, HAS_WATCHDOG, HAS_PROMETHEUS, HAS_INTEGRATION,
        HAS_OPTIONS_CHAIN
    ])
    print(f"SpyderB_Broker v{__version__}: {available}/17 modules loaded")
