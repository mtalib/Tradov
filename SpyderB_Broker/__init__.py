#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker     
Module: __init__.py (CONSOLIDATED VERSION WITH B29)
Purpose: Package initialization with consolidated connection manager
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-13 Time: 20:00:00  

Module Description:
    Updated package initialization for SpyderB_Broker with the new consolidated
    SpyderB29_EnhancedConnectionManager and proper handling of renamed modules.
    This version resolves duplicate module numbers and provides a clean interface
    for all broker components.
    
    KEY CHANGES:
    - Added SpyderB29_EnhancedConnectionManager (consolidated connection manager)
    - Fixed duplicate module numbers (B26, B27)
    - Proper module renaming support
    - Backward compatibility maintained
    - Enhanced error handling and diagnostics
    - Timeout prevention integration
"""

# ==============================================================================
# PACKAGE METADATA
# ==============================================================================
__version__ = "2.2.0"
__author__ = "Mohamed Talib"
__description__ = "SPYDER Broker Package - Interactive Brokers Gateway Interface (Consolidated)"

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import sys
from typing import Dict, List, Optional, Any, Union

# ==============================================================================
# PACKAGE INITIALIZATION LOGGING
# ==============================================================================
_logger = logging.getLogger(__name__)
_module_status = {}

def _log_import_status(module_name: str, success: bool, error: str = None):
    """Log import status for debugging and validation."""
    _module_status[module_name] = success
    if success:
        _logger.debug(f"✅ {module_name} imported successfully")
    else:
        _logger.warning(f"❌ {module_name} import failed: {error}")

def get_module_status() -> Dict[str, bool]:
    """Get status of all module imports for diagnostics."""
    return _module_status.copy()

def get_package_status() -> Dict[str, Any]:
    """Get comprehensive package status for diagnostics."""
    return {
        'version': __version__,
        'modules_loaded': sum(_module_status.values()),
        'modules_total': len(_module_status),
        'success_rate': sum(_module_status.values()) / max(1, len(_module_status)),
        'module_details': _module_status.copy(),
        'connection_manager_version': 'B29_Enhanced',
        'timeout_prevention': True
    }

def print_package_status():
    """Print formatted package status."""
    status = get_package_status()
    print(f"SpyderB_Broker Package Status (v{status['version']}):")
    print(f"  Modules loaded: {status['modules_loaded']}/{status['modules_total']}")
    print(f"  Success rate: {status['success_rate']:.1%}")
    print(f"  Connection Manager: {status['connection_manager_version']}")
    print(f"  Timeout Prevention: {status['timeout_prevention']}")

# ==============================================================================
# CORE MODULE IMPORTS
# ==============================================================================

# Order Types (B00)
try:
    from .SpyderB00_OrderTypes import *
    _log_import_status("SpyderB00_OrderTypes", True)
except ImportError as e:
    _log_import_status("SpyderB00_OrderTypes", False, str(e))

# Main Spyder Client (B01)
try:
    from .SpyderB01_SpyderClient import SpyderClient, IBConfig, create_spyder_client
    _log_import_status("SpyderB01_SpyderClient", True)
except ImportError as e:
    _log_import_status("SpyderB01_SpyderClient", False, str(e))
    # Create fallback
    SpyderClient = None
    IBConfig = None
    create_spyder_client = None

# Order Manager (B02)
try:
    from .SpyderB02_OrderManager import OrderManager, OrderRequest, create_order_manager
    _log_import_status("SpyderB02_OrderManager", True)
except ImportError as e:
    _log_import_status("SpyderB02_OrderManager", False, str(e))
    OrderManager = None
    OrderRequest = None
    create_order_manager = None

# Position Tracker (B03)
try:
    from .SpyderB03_PositionTracker import PositionTracker, create_position_tracker
    _log_import_status("SpyderB03_PositionTracker", True)
except ImportError as e:
    _log_import_status("SpyderB03_PositionTracker", False, str(e))
    PositionTracker = None
    create_position_tracker = None

# Account Manager (B04)
try:
    from .SpyderB04_AccountManager import AccountManager, create_account_manager
    _log_import_status("SpyderB04_AccountManager", True)
except ImportError as e:
    _log_import_status("SpyderB04_AccountManager", False, str(e))
    AccountManager = None
    create_account_manager = None

# ==============================================================================
# CONNECTION MANAGERS - NEW CONSOLIDATED APPROACH
# ==============================================================================

# NEW: Enhanced Connection Manager (B29) - PRIMARY
try:
    from .SpyderB29_EnhancedConnectionManager import (
        EnhancedConnectionManager, 
        ConnectionConfig,
        ConnectionStatus,
        ConnectionState,
        ConnectivityState,
        TradingMode,
        get_connection_manager,
        reset_connection_manager
    )
    _log_import_status("SpyderB29_EnhancedConnectionManager", True)
    
    # Make the enhanced manager the default
    ConnectionManager = EnhancedConnectionManager
    
except ImportError as e:
    _log_import_status("SpyderB29_EnhancedConnectionManager", False, str(e))
    
    # Fallback to original Connection Manager (B05) for backward compatibility
    try:
        from .SpyderB05_ConnectionManager import ConnectionManager, ConnectivityState
        _log_import_status("SpyderB05_ConnectionManager", True)
        _log_import_status("SpyderB29_Fallback", True, "Using B05 as fallback")
    except ImportError as e2:
        _log_import_status("SpyderB05_ConnectionManager", False, str(e2))
        ConnectionManager = None
        ConnectivityState = None

# Legacy Connection Manager (B05) - kept for compatibility
try:
    from .SpyderB05_ConnectionManager import ConnectionManager as LegacyConnectionManager
    _log_import_status("SpyderB05_Legacy", True)
except ImportError as e:
    _log_import_status("SpyderB05_Legacy", False, str(e))
    LegacyConnectionManager = None

# Integrated Connectivity Manager (B20) - kept for compatibility  
try:
    from .SpyderB20_IntegratedConnectivityManager import IntegratedConnectivityManager
    _log_import_status("SpyderB20_IntegratedConnectivityManager", True)
except ImportError as e:
    _log_import_status("SpyderB20_IntegratedConnectivityManager", False, str(e))
    IntegratedConnectivityManager = None

# ==============================================================================
# CONTRACT AND DATA MODULES
# ==============================================================================

# Contract Builder (B06)
try:
    from .SpyderB06_ContractBuilder import ContractBuilder, get_contract_builder, create_contract_builder
    _log_import_status("SpyderB06_ContractBuilder", True)
except ImportError as e:
    _log_import_status("SpyderB06_ContractBuilder", False, str(e))
    ContractBuilder = None
    get_contract_builder = None
    create_contract_builder = None

# Market Data Manager (B07)
try:
    from .SpyderB07_MarketDataManager import MarketDataManager, create_market_data_manager
    _log_import_status("SpyderB07_MarketDataManager", True)
except ImportError as e:
    _log_import_status("SpyderB07_MarketDataManager", False, str(e))
    MarketDataManager = None
    create_market_data_manager = None

# Multi-Client Data Manager (B08)
try:
    from .SpyderB08_MultiClientDataManager import MultiClientDataManager
    _log_import_status("SpyderB08_MultiClientDataManager", True)
except ImportError as e:
    _log_import_status("SpyderB08_MultiClientDataManager", False, str(e))
    MultiClientDataManager = None

# IB Client Portal (B09)
try:
    from .SpyderB09_IBClientPortal import IBClientPortal
    _log_import_status("SpyderB09_IBClientPortal", True)
except ImportError as e:
    _log_import_status("SpyderB09_IBClientPortal", False, str(e))
    IBClientPortal = None

# IB Data Types (B10)
try:
    from .SpyderB10_IBDataTypes import IBDataTypeManager as IBDataTypes
    _log_import_status("SpyderB10_IBDataTypes", True)
except ImportError as e:
    _log_import_status("SpyderB10_IBDataTypes", False, str(e))
    IBDataTypes = None

# ==============================================================================
# INFRASTRUCTURE MODULES
# ==============================================================================

# AsyncIO Bridge (B11)
try:
    from .SpyderB11_AsyncIOBridge import AsyncIOBridge
    _log_import_status("SpyderB11_AsyncIOBridge", True)
except ImportError as e:
    _log_import_status("SpyderB11_AsyncIOBridge", False, str(e))
    AsyncIOBridge = None

# Gateway Automation (B12)
try:
    from .SpyderB12_GatewayAutomation import GatewayAutomation, create_gateway_automation
    _log_import_status("SpyderB12_GatewayAutomation", True)
except ImportError as e:
    _log_import_status("SpyderB12_GatewayAutomation", False, str(e))
    GatewayAutomation = None
    create_gateway_automation = None

# Gateway Config (B13)
try:
    from .SpyderB13_GatewayConfig import GatewayConfig
    _log_import_status("SpyderB13_GatewayConfig", True)
except ImportError as e:
    _log_import_status("SpyderB13_GatewayConfig", False, str(e))
    GatewayConfig = None

# Multi-Client Watchdog (B14)
try:
    from .SpyderB14_MultiClientWatchdog import MultiClientWatchdog
    _log_import_status("SpyderB14_MultiClientWatchdog", True)
except ImportError as e:
    _log_import_status("SpyderB14_MultiClientWatchdog", False, str(e))
    MultiClientWatchdog = None

# Prometheus Metrics (B15)
try:
    from .SpyderB15_PrometheusMetrics import PrometheusMetrics
    _log_import_status("SpyderB15_PrometheusMetrics", True)
except ImportError as e:
    _log_import_status("SpyderB15_PrometheusMetrics", False, str(e))
    PrometheusMetrics = None

# Gateway Integration (B16)
try:
    from .SpyderB16_GatewayIntegration import GatewayIntegrationManager
    _log_import_status("SpyderB16_GatewayIntegration", True)
except ImportError as e:
    _log_import_status("SpyderB16_GatewayIntegration", False, str(e))
    GatewayIntegrationManager = None

# Server Monitor (B17)
try:
    from .SpyderB17_ServerMonitor import ServerMonitor
    _log_import_status("SpyderB17_ServerMonitor", True)
except ImportError as e:
    _log_import_status("SpyderB17_ServerMonitor", False, str(e))
    ServerMonitor = None

# Zurich Connectivity Diagnostic (B18)
try:
    from .SpyderB18_ZurichConnectivityDiagnostic import ZurichConnectivityDiagnostic
    _log_import_status("SpyderB18_ZurichConnectivityDiagnostic", True)
except ImportError as e:
    _log_import_status("SpyderB18_ZurichConnectivityDiagnostic", False, str(e))
    ZurichConnectivityDiagnostic = None

# VPN Manager (B19)
try:
    from .SpyderB19_VPNManager import VPNManager
    _log_import_status("SpyderB19_VPNManager", True)
except ImportError as e:
    _log_import_status("SpyderB19_VPNManager", False, str(e))
    VPNManager = None

# ==============================================================================
# AUTOMATION AND TESTING MODULES
# ==============================================================================

# Gateway Startup Automation (B21)
try:
    from .SpyderB21_GatewayStartupAutomation import GatewayStartupAutomation
    _log_import_status("SpyderB21_GatewayStartupAutomation", True)
except ImportError as e:
    _log_import_status("SpyderB21_GatewayStartupAutomation", False, str(e))
    GatewayStartupAutomation = None

# Integration Test Suite (B22)
try:
    from .SpyderB22_IntegrationTestSuite import IntegrationTestSuite
    _log_import_status("SpyderB22_IntegrationTestSuite", True)
except ImportError as e:
    _log_import_status("SpyderB22_IntegrationTestSuite", False, str(e))
    IntegrationTestSuite = None

# Bashrc Configuration (B23)
try:
    from .SpyderB23_BashrcConfiguration import BashrcConfiguration
    _log_import_status("SpyderB23_BashrcConfiguration", True)
except ImportError as e:
    _log_import_status("SpyderB23_BashrcConfiguration", False, str(e))
    BashrcConfiguration = None

# Configuration Migration (B24)
try:
    from .SpyderB24_ConfigurationMigration import ConfigurationMigration
    _log_import_status("SpyderB24_ConfigurationMigration", True)
except ImportError as e:
    _log_import_status("SpyderB24_ConfigurationMigration", False, str(e))
    ConfigurationMigration = None

# Gateway Installer (B25)
try:
    from .SpyderB25_GatewayInstaller import GatewayInstaller
    _log_import_status("SpyderB25_GatewayInstaller", True)
except ImportError as e:
    _log_import_status("SpyderB25_GatewayInstaller", False, str(e))
    GatewayInstaller = None

# ==============================================================================
# BRIDGE AND CONNECTOR MODULES (HANDLING DUPLICATES)
# ==============================================================================

# PySide Async Bridge (B26) - KEEP ORIGINAL
try:
    from .SpyderB26_PySideAsyncBridge import PySideAsyncBridge
    _log_import_status("SpyderB26_PySideAsyncBridge", True)
except ImportError as e:
    _log_import_status("SpyderB26_PySideAsyncBridge", False, str(e))
    PySideAsyncBridge = None

# SPY Options Chain Manager (B30) - RENAMED FROM B26
try:
    from .SpyderB30_SPYOptionsChainManager import SPYOptionsChainManager
    _log_import_status("SpyderB30_SPYOptionsChainManager", True)
except ImportError as e:
    _log_import_status("SpyderB30_SPYOptionsChainManager", False, str(e))
    # Try old location for backward compatibility
    try:
        from .SpyderB26_SPYOptionsChainManager import SPYOptionsChainManager
        _log_import_status("SpyderB26_SPYOptionsChainManager_Legacy", True)
    except ImportError:
        _log_import_status("SpyderB30_SPYOptionsChainManager", False, str(e))
        SPYOptionsChainManager = None

# IB Data Connector (B27) - KEEP ORIGINAL
try:
    from .SpyderB27_IBDataConnector import IBDataConnector
    _log_import_status("SpyderB27_IBDataConnector", True)
except ImportError as e:
    _log_import_status("SpyderB27_IBDataConnector", False, str(e))
    IBDataConnector = None

# VPN Manager (B31) - RENAMED FROM B27
try:
    from .SpyderB31_VPNManager import VPNManager as VPNManagerAlt
    _log_import_status("SpyderB31_VPNManager", True)
except ImportError as e:
    _log_import_status("SpyderB31_VPNManager", False, str(e))
    # Try old location for backward compatibility
    try:
        from .SpyderB27_VPNManager import VPNManager as VPNManagerAlt
        _log_import_status("SpyderB27_VPNManager_Legacy", True)
    except ImportError:
        _log_import_status("SpyderB31_VPNManager", False, str(e))
        VPNManagerAlt = None

# IBKR Connection Tester (B28)
try:
    from .SpyderB28_IBKRConnectionTester import IBKRConnectionTester
    _log_import_status("SpyderB28_IBKRConnectionTester", True)
except ImportError as e:
    _log_import_status("SpyderB28_IBKRConnectionTester", False, str(e))
    IBKRConnectionTester = None

# ==============================================================================
# FACTORY FUNCTIONS AND CONVENIENCE METHODS
# ==============================================================================

def create_broker_client(config: Optional[Dict[str, Any]] = None):
    """
    Create a complete broker client with all components.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dictionary with all broker components
    """
    try:
        # Create connection manager (enhanced version)
        if ConnectionManager and hasattr(ConnectionManager, '__name__') and 'Enhanced' in ConnectionManager.__name__:
            conn_config = ConnectionConfig() if 'ConnectionConfig' in globals() else None
            connection_manager = get_connection_manager(conn_config)
        else:
            connection_manager = ConnectionManager() if ConnectionManager else None
        
        # Create other components
        spyder_client = create_spyder_client() if create_spyder_client else None
        order_manager = create_order_manager(spyder_client) if create_order_manager else None
        position_tracker = create_position_tracker(spyder_client) if create_position_tracker else None
        account_manager = create_account_manager(spyder_client) if create_account_manager else None
        contract_builder = get_contract_builder() if get_contract_builder else None
        market_data_manager = create_market_data_manager(spyder_client) if create_market_data_manager else None
        
        return {
            'connection_manager': connection_manager,
            'spyder_client': spyder_client,
            'order_manager': order_manager,
            'position_tracker': position_tracker,
            'account_manager': account_manager,
            'contract_builder': contract_builder,
            'market_data_manager': market_data_manager,
            'status': 'enhanced_broker_client' if connection_manager else 'basic_broker_client'
        }
        
    except Exception as e:
        _logger.error(f"Failed to create broker client: {e}")
        return None

def get_enhanced_connection_manager(config: Optional[Dict[str, Any]] = None):
    """
    Get the enhanced connection manager with timeout prevention.
    
    Args:
        config: Connection configuration
        
    Returns:
        Enhanced connection manager instance or None
    """
    try:
        if 'get_connection_manager' in globals():
            if config and 'ConnectionConfig' in globals():
                conn_config = ConnectionConfig(**config)
                return get_connection_manager(conn_config)
            else:
                return get_connection_manager()
        else:
            _logger.warning("Enhanced connection manager not available")
            return None
    except Exception as e:
        _logger.error(f"Failed to get enhanced connection manager: {e}")
        return None

def diagnose_broker_package():
    """Run comprehensive broker package diagnostics."""
    print("SpyderB_Broker Package Diagnostics")
    print("=" * 50)
    
    # Package status
    status = get_package_status()
    print(f"Package Version: {status['version']}")
    print(f"Modules Loaded: {status['modules_loaded']}/{status['modules_total']}")
    print(f"Success Rate: {status['success_rate']:.1%}")
    print(f"Connection Manager: {status.get('connection_manager_version', 'Unknown')}")
    print(f"Timeout Prevention: {status.get('timeout_prevention', False)}")
    print()
    
    # Connection manager status
    print("Connection Manager Analysis:")
    if ConnectionManager:
        if hasattr(ConnectionManager, '__name__') and 'Enhanced' in ConnectionManager.__name__:
            print("  ✅ Enhanced Connection Manager (B29) - Timeout prevention enabled")
        else:
            print("  ⚠️  Legacy Connection Manager (B05) - Consider upgrading to B29")
    else:
        print("  ❌ No connection manager available")
    print()
    
    # Module details
    print("Detailed Module Status:")
    for module, success in _module_status.items():
        status_icon = "✅" if success else "❌"
        print(f"  {status_icon} {module}")
    
    print()
    print("Recommendations:")
    if status['success_rate'] < 0.8:
        print("  - Some modules failed to load - check dependencies")
    if not status.get('timeout_prevention', False):
        print("  - Consider using SpyderB29_EnhancedConnectionManager for timeout prevention")
    if status['success_rate'] >= 0.9:
        print("  - Broker package is healthy and ready for production use")

# ==============================================================================
# EXPORTS
# ==============================================================================

# Core components (always exported if available)
__all__ = [
    # Package management
    'get_package_status',
    'get_module_status', 
    'print_package_status',
    'diagnose_broker_package',
    
    # Factory functions
    'create_broker_client',
    'get_enhanced_connection_manager',
    
    # Core classes (if available)
]

# Add available classes to exports
if SpyderClient:
    __all__.extend(['SpyderClient', 'IBConfig', 'create_spyder_client'])

if ConnectionManager:
    __all__.append('ConnectionManager')
    
if 'EnhancedConnectionManager' in globals():
    __all__.extend(['EnhancedConnectionManager', 'ConnectionConfig', 'ConnectionStatus', 
                   'ConnectionState', 'ConnectivityState', 'TradingMode',
                   'get_connection_manager', 'reset_connection_manager'])

if OrderManager:
    __all__.extend(['OrderManager', 'OrderRequest', 'create_order_manager'])
    
if PositionTracker:
    __all__.extend(['PositionTracker', 'create_position_tracker'])
    
if AccountManager:
    __all__.extend(['AccountManager', 'create_account_manager'])
    
if ContractBuilder:
    __all__.extend(['ContractBuilder', 'get_contract_builder', 'create_contract_builder'])
    
if MarketDataManager:
    __all__.extend(['MarketDataManager', 'create_market_data_manager'])

# Add other available components
for component_name in [
    'MultiClientDataManager', 'IBClientPortal', 'IBDataTypes',
    'AsyncIOBridge', 'GatewayAutomation', 'GatewayConfig', 
    'MultiClientWatchdog', 'PrometheusMetrics', 'GatewayIntegrationManager',
    'ServerMonitor', 'ZurichConnectivityDiagnostic', 'VPNManager',
    'IntegratedConnectivityManager', 'GatewayStartupAutomation',
    'IntegrationTestSuite', 'BashrcConfiguration', 'ConfigurationMigration',
    'GatewayInstaller', 'PySideAsyncBridge', 'SPYOptionsChainManager',
    'IBDataConnector', 'VPNManagerAlt', 'IBKRConnectionTester'
]:
    if globals().get(component_name) is not None:
        __all__.append(component_name)

# ==============================================================================
# PACKAGE INITIALIZATION COMPLETE
# ==============================================================================

_logger.info(f"SpyderB_Broker package initialized (v{__version__})")
_logger.info(f"Loaded {sum(_module_status.values())}/{len(_module_status)} modules")

# Print status on import if in debug mode
if _logger.isEnabledFor(logging.DEBUG):
    print_package_status()