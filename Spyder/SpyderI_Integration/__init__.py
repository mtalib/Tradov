import logging
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderI_Integration
Purpose: System integration and interconnectivity management
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04

Package Description:
    The SpyderI_Integration package provides comprehensive system integration
    capabilities including broker API automation, event routing, configuration
    management, diagnostic engines, and agent message bus functionality.
    This package ensures seamless coordination between all Spyder modules.

Modules Overview:
    • SpyderI01_IntegrationHub: Central integration hub with module coordination
    • SpyderI02_EventRouter: Event-driven communication system
    • SpyderI03_ConfigManager: Configuration management and validation
    • SpyderI04_DiagnosticsEngine_*: Comprehensive diagnostic and health checking
    • SpyderI06_AgentMessageBus: Inter-agent communication infrastructure

Key Features:
    • Centralized module integration and coordination
    • Real-time system health monitoring and diagnostics
    • Event-driven inter-module communication
    • Configuration validation and management
"""

# ==============================================================================
# VERSION INFORMATION
# ==============================================================================
__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"
__status__ = "Production"

# ==============================================================================
# CORE MODULE IMPORTS
# ==============================================================================

# Integration Hub
try:
    from .SpyderI01_IntegrationHub import (
        IntegrationHub,
        ModuleState,
        IntegrationLevel,
        HealthStatus,
    )

    INTEGRATION_HUB_AVAILABLE = True
except ImportError as e:
    logging.info(f"⚠️ SpyderI01_IntegrationHub not available: {e}")
    INTEGRATION_HUB_AVAILABLE = False

# Event Router
try:
    from .SpyderI02_EventRouter import (
        EventRouter,
        # Add main classes from EventRouter when inspected
    )

    EVENT_ROUTER_AVAILABLE = True
except ImportError as e:
    logging.info(f"⚠️ SpyderI02_EventRouter not available: {e}")
    EVENT_ROUTER_AVAILABLE = False

# Config Manager
try:
    from .SpyderI03_ConfigManager import (
        ConfigManager,
        # Add main classes from ConfigManager when inspected
    )

    CONFIG_MANAGER_AVAILABLE = True
except ImportError as e:
    logging.info(f"⚠️ SpyderI03_ConfigManager not available: {e}")
    CONFIG_MANAGER_AVAILABLE = False

# Diagnostics Engine
try:
    from .SpyderI04_DiagnosticsEngine_Core import (
        DiagnosticsEngine,
        # Add main classes from DiagnosticsEngine when inspected
    )

    DIAGNOSTICS_ENGINE_AVAILABLE = True
except ImportError as e:
    logging.info(f"⚠️ SpyderI04_DiagnosticsEngine not available: {e}")
    DIAGNOSTICS_ENGINE_AVAILABLE = False

# Agent Message Bus
try:
    from .SpyderI06_AgentMessageBus import (
        AgentMessageBus,
        # Add main classes from AgentMessageBus when inspected
    )

    AGENT_MESSAGE_BUS_AVAILABLE = True
except ImportError as e:
    logging.info(f"⚠️ SpyderI06_AgentMessageBus not available: {e}")
    AGENT_MESSAGE_BUS_AVAILABLE = False

# ==============================================================================
# PACKAGE CONVENIENCE FUNCTIONS
# ==============================================================================


def get_available_modules():
    """
    Get a list of available modules in the SpyderI_Integration package.

    Returns:
        dict: Dictionary with module availability status
    """
    return {
        "SpyderI01_IntegrationHub": INTEGRATION_HUB_AVAILABLE,
        "SpyderI02_EventRouter": EVENT_ROUTER_AVAILABLE,
        "SpyderI03_ConfigManager": CONFIG_MANAGER_AVAILABLE,
        "SpyderI04_DiagnosticsEngine": DIAGNOSTICS_ENGINE_AVAILABLE,
        "SpyderI06_AgentMessageBus": AGENT_MESSAGE_BUS_AVAILABLE,
    }


def get_package_info():
    """
    Get comprehensive package information.

    Returns:
        dict: Package information including version, modules, and capabilities
    """
    available_modules = get_available_modules()
    total_modules = len(available_modules)
    available_count = sum(available_modules.values())

    return {
        "package_name": "SpyderI_Integration",
        "version": __version__,
        "author": __author__,
        "status": __status__,
        "total_modules": total_modules,
        "available_modules": available_count,
        "module_status": available_modules,
        "capabilities": {
            "integration_hub": INTEGRATION_HUB_AVAILABLE,
            "event_routing": EVENT_ROUTER_AVAILABLE,
            "config_management": CONFIG_MANAGER_AVAILABLE,
            "diagnostics": DIAGNOSTICS_ENGINE_AVAILABLE,
            "agent_messaging": AGENT_MESSAGE_BUS_AVAILABLE,
        },
    }


def create_integration_hub():
    """
    Factory function to create an IntegrationHub instance.

    Returns:
        IntegrationHub: Configured integration hub

    Raises:
        ImportError: If IntegrationHub is not available
    """
    if not INTEGRATION_HUB_AVAILABLE:
        raise ImportError("IntegrationHub module is not available")

    return IntegrationHub()


def validate_package():
    """
    Validate the package installation and module availability.

    Returns:
        bool: True if package is fully functional, False otherwise
    """
    try:
        info = get_package_info()
        logging.info(f"🔌 {info['package_name']} v{info['version']}")
        logging.info(
            f"✅ {info['available_modules']}/{info['total_modules']} modules available"
        )

        if info["available_modules"] == info["total_modules"]:
            logging.info("🚀 All integration modules loaded successfully")
            return True
        else:
            logging.info("⚠️ Some integration modules are missing")
            for module, status in info["module_status"].items():
                status_icon = "✅" if status else "❌"
                logging.info(f"   {status_icon} {module}")
            return False

    except Exception as e:
        logging.info(f"❌ Integration package validation failed: {e}")
        return False


# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Core classes (conditionally added based on availability)
    "get_available_modules",
    "get_package_info",
    "create_integration_hub",
    "validate_package",
]

# Conditionally add available classes to __all__
if INTEGRATION_HUB_AVAILABLE:
    __all__.extend(
        ["IntegrationHub", "ModuleState", "IntegrationLevel", "HealthStatus"]
    )

if EVENT_ROUTER_AVAILABLE:
    __all__.extend(["EventRouter"])

if CONFIG_MANAGER_AVAILABLE:
    __all__.extend(["ConfigManager"])

if DIAGNOSTICS_ENGINE_AVAILABLE:
    __all__.extend(["DiagnosticsEngine"])

if AGENT_MESSAGE_BUS_AVAILABLE:
    __all__.extend(["AgentMessageBus"])

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Perform package validation on import
if __name__ != "__main__":
    validate_package()
else:
    # If running as main, show detailed package info
    logging.info("=" * 70)
    logging.info("SPYDER I - INTEGRATION PACKAGE")
    logging.info("=" * 70)
    validate_package()
    info = get_package_info()
    logging.info("\nPackage Details:")
    for key, value in info.items():
        if key != "module_status":
            logging.info(f"  {key}: {value}")
