#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderP_PortfolioMgmt
Purpose: Portfolio management and capital allocation optimization
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04

Package Description:
    The SpyderP_PortfolioMgmt package provides comprehensive portfolio management
    capabilities including position allocation, correlation analysis, capital
    optimization, multi-strategy allocation, and dynamic strategy rotation.
    This package ensures optimal capital utilization across trading strategies.

Modules Overview:
    • SpyderP01_PortfolioManager: Central portfolio management and coordination
    • SpyderP02_AllocationOptimizer: Mathematical allocation optimization
    • SpyderP03_CorrelationAnalyzer: Cross-strategy correlation analysis
    • SpyderP04_CapitalAllocator: Capital allocation and risk-based sizing
    • SpyderP05_MultiStrategyAllocator: Multi-strategy portfolio optimization
    • SpyderP06_StrategyRotation: Dynamic strategy rotation based on regime

Key Features:
    • Mathematical portfolio optimization using modern portfolio theory
    • Real-time correlation analysis between strategies
    • Risk-adjusted capital allocation
    • Dynamic strategy rotation based on market conditions
    • Multi-timeframe portfolio rebalancing
    • Performance attribution analysis
"""

import logging
from importlib import import_module
from importlib.util import find_spec

# ==============================================================================
# VERSION INFORMATION
# ==============================================================================
__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"
__status__ = "Production"

_MODULE_EXPORTS = {
    "SpyderP01_PortfolioManager": ["PortfolioManager"],
    "SpyderP02_AllocationOptimizer": ["AllocationOptimizer"],
    "SpyderP03_CorrelationAnalyzer": ["CorrelationAnalyzer"],
    "SpyderP04_CapitalAllocator": ["CapitalAllocator"],
    "SpyderP05_MultiStrategyAllocator": ["MultiStrategyAllocator"],
    "SpyderP06_StrategyRotation": ["StrategyRotation"],
    "SpyderP07_RenaissancePositionSizer": [
        "RenaissancePositionSizer",
        "PositionSizeMethod",
        "PositionSizeResult",
        "TradeRecord",
        "PerformanceMetrics",
        "create_position_sizer",
    ],
}
_LAZY_EXPORTS = {
    export_name: (module_name, export_name)
    for module_name, export_names in _MODULE_EXPORTS.items()
    for export_name in export_names
}
_MODULE_AVAILABILITY_CACHE: dict[str, bool] = {}


def _module_is_available(module_name: str) -> bool:
    cached = _MODULE_AVAILABILITY_CACHE.get(module_name)
    if cached is not None:
        return cached

    try:
        available = find_spec(f"{__name__}.{module_name}") is not None
    except Exception:
        available = False

    _MODULE_AVAILABILITY_CACHE[module_name] = available
    return available


def _load_export(export_name: str):
    module_name, attribute_name = _LAZY_EXPORTS[export_name]

    try:
        module = import_module(f".{module_name}", __name__)
        value = getattr(module, attribute_name)
    except ImportError as exc:
        logging.info("⚠️ %s.%s not available: %s", module_name, attribute_name, exc)
        raise AttributeError(f"module {__name__!r} has no attribute {export_name!r}") from exc

    globals()[export_name] = value
    return value

# ==============================================================================
# PACKAGE CONVENIENCE FUNCTIONS
# ==============================================================================


def get_available_modules():
    """
    Get a list of available modules in the SpyderP_PortfolioMgmt package.

    Returns:
        dict: Dictionary with module availability status
    """
    return {
        module_name: _module_is_available(module_name)
        for module_name in _MODULE_EXPORTS
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
        "package_name": "SpyderP_PortfolioMgmt",
        "version": __version__,
        "author": __author__,
        "status": __status__,
        "total_modules": total_modules,
        "available_modules": available_count,
        "module_status": available_modules,
        "capabilities": {
            "portfolio_management": available_modules.get("SpyderP01_PortfolioManager", False),
            "allocation_optimization": available_modules.get("SpyderP02_AllocationOptimizer", False),
            "correlation_analysis": available_modules.get("SpyderP03_CorrelationAnalyzer", False),
            "capital_allocation": available_modules.get("SpyderP04_CapitalAllocator", False),
            "multi_strategy_allocation": available_modules.get("SpyderP05_MultiStrategyAllocator", False),
            "strategy_rotation": available_modules.get("SpyderP06_StrategyRotation", False),
        },
    }


def get_global_portfolio_manager():
    """Get the shared portfolio manager instance without importing P01."""
    from .SpyderP00_GlobalPortfolioRegistry import get_global_portfolio_manager as _get_global

    return _get_global()


def get_portfolio_manager():
    """Backward-compatible alias for the shared portfolio manager accessor."""
    from .SpyderP00_GlobalPortfolioRegistry import get_portfolio_manager as _get_portfolio_manager

    return _get_portfolio_manager()


def set_global_portfolio_manager(portfolio_manager):
    """Publish the shared portfolio manager instance without importing P01."""
    from .SpyderP00_GlobalPortfolioRegistry import set_global_portfolio_manager as _set_global

    _set_global(portfolio_manager)


def reset_global_portfolio_manager():
    """Reset the shared portfolio manager instance without importing P01."""
    from .SpyderP00_GlobalPortfolioRegistry import reset_global_portfolio_manager as _reset_global

    _reset_global()


def create_portfolio_manager(initial_capital: float = 100000, config: dict | None = None):
    """
    Factory function to create a PortfolioManager instance.

    Returns:
        PortfolioManager: Configured portfolio manager

    Raises:
        ImportError: If PortfolioManager is not available
    """
    from .SpyderP00_GlobalPortfolioRegistry import create_portfolio_manager as _create_portfolio_manager

    return _create_portfolio_manager(initial_capital=initial_capital, config=config)


def create_optimization_suite():
    """
    Factory function to create a suite of optimization tools.

    Returns:
        dict: Dictionary containing optimizer instances

    Raises:
        ImportError: If required modules are not available
    """
    suite = {}

    if _module_is_available("SpyderP02_AllocationOptimizer"):
        suite["allocation_optimizer"] = _load_export("AllocationOptimizer")()

    if _module_is_available("SpyderP03_CorrelationAnalyzer"):
        suite["correlation_analyzer"] = _load_export("CorrelationAnalyzer")()

    if _module_is_available("SpyderP04_CapitalAllocator"):
        suite["capital_allocator"] = _load_export("CapitalAllocator")()

    if _module_is_available("SpyderP05_MultiStrategyAllocator"):
        suite["multi_strategy_allocator"] = _load_export("MultiStrategyAllocator")()

    if _module_is_available("SpyderP06_StrategyRotation"):
        suite["strategy_rotation"] = _load_export("StrategyRotation")()

    if not suite:
        raise ImportError("No optimization modules are available")

    return suite


def validate_package():
    """
    Validate the package installation and module availability.

    Returns:
        bool: True if package is fully functional, False otherwise
    """
    try:
        info = get_package_info()
        logging.info("💼 %s v%s", info['package_name'], info['version'])
        logging.info(
            "✅ %s/%s modules available", info['available_modules'], info['total_modules']
        )

        if info["available_modules"] == info["total_modules"]:
            logging.info("🚀 All portfolio management modules loaded successfully")
            return True
        else:
            logging.info("⚠️ Some portfolio management modules are missing")
            for module, status in info["module_status"].items():
                status_icon = "✅" if status else "❌"
                logging.info("   %s %s", status_icon, module)
            return False

    except Exception as e:
        logging.info("❌ Portfolio management package validation failed: %s", e)
        return False


def __getattr__(name):
    """Lazily expose heavyweight convenience exports on first access."""
    if name in _LAZY_EXPORTS:
        return _load_export(name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Expose lazy exports in dir() without importing them."""
    return sorted(set(globals()) | set(__all__) | set(_LAZY_EXPORTS))


# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Utility functions
    "get_available_modules",
    "get_package_info",
    "get_global_portfolio_manager",
    "get_portfolio_manager",
    "set_global_portfolio_manager",
    "reset_global_portfolio_manager",
    "create_portfolio_manager",
    "create_optimization_suite",
    "validate_package",
    "PortfolioManager",
    "AllocationOptimizer",
    "CorrelationAnalyzer",
    "CapitalAllocator",
    "MultiStrategyAllocator",
    "StrategyRotation",
    "RenaissancePositionSizer",
    "PositionSizeMethod",
    "PositionSizeResult",
    "TradeRecord",
    "PerformanceMetrics",
    "create_position_sizer",
]

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Keep validation available for manual checks, but do not run it on import.
if __name__ == "__main__":
    # If running as main, show detailed package info
    logging.info("=" * 70)
    logging.info("SPYDER P - PORTFOLIO MANAGEMENT PACKAGE")
    logging.info("=" * 70)
    validate_package()
    info = get_package_info()
    logging.info("\nPackage Details:")
    for key, value in info.items():
        if key != "module_status":
            logging.info("  %s: %s", key, value)
