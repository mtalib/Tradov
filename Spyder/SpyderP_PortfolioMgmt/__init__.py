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

# Portfolio Manager
try:
    from .SpyderP01_PortfolioManager import (
        PortfolioManager,
        # Add main classes from PortfolioManager when inspected
    )

    PORTFOLIO_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderP01_PortfolioManager not available: {e}")
    PORTFOLIO_MANAGER_AVAILABLE = False

# Allocation Optimizer
try:
    from .SpyderP02_AllocationOptimizer import (
        AllocationOptimizer,
        # Add main classes from AllocationOptimizer when inspected
    )

    ALLOCATION_OPTIMIZER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderP02_AllocationOptimizer not available: {e}")
    ALLOCATION_OPTIMIZER_AVAILABLE = False

# Correlation Analyzer
try:
    from .SpyderP03_CorrelationAnalyzer import (
        CorrelationAnalyzer,
        # Add main classes from CorrelationAnalyzer when inspected
    )

    CORRELATION_ANALYZER_AVAILABLE = True
except Exception as e:
    print(f"⚠️ SpyderP03_CorrelationAnalyzer not available: {e}")
    CORRELATION_ANALYZER_AVAILABLE = False

# Capital Allocator
try:
    from .SpyderP04_CapitalAllocator import (
        CapitalAllocator,
        # Add main classes from CapitalAllocator when inspected
    )

    CAPITAL_ALLOCATOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderP04_CapitalAllocator not available: {e}")
    CAPITAL_ALLOCATOR_AVAILABLE = False

# Multi-Strategy Allocator
try:
    from .SpyderP05_MultiStrategyAllocator import (
        MultiStrategyAllocator,
        # Add main classes from MultiStrategyAllocator when inspected
    )

    MULTI_STRATEGY_ALLOCATOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderP05_MultiStrategyAllocator not available: {e}")
    MULTI_STRATEGY_ALLOCATOR_AVAILABLE = False

# Strategy Rotation
try:
    from .SpyderP06_StrategyRotation import (
        StrategyRotation,
        # Add main classes from StrategyRotation when inspected
    )

    STRATEGY_ROTATION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderP06_StrategyRotation not available: {e}")
    STRATEGY_ROTATION_AVAILABLE = False

# Renaissance Position Sizer
try:
    from .SpyderP07_RenaissancePositionSizer import (
        RenaissancePositionSizer,
        PositionSizeMethod,
        PositionSizeResult,
        TradeRecord,
        PerformanceMetrics,
        create_position_sizer,
    )

    RENAISSANCE_POSITION_SIZER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderP07_RenaissancePositionSizer not available: {e}")
    RENAISSANCE_POSITION_SIZER_AVAILABLE = False

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
        "SpyderP01_PortfolioManager": PORTFOLIO_MANAGER_AVAILABLE,
        "SpyderP02_AllocationOptimizer": ALLOCATION_OPTIMIZER_AVAILABLE,
        "SpyderP03_CorrelationAnalyzer": CORRELATION_ANALYZER_AVAILABLE,
        "SpyderP04_CapitalAllocator": CAPITAL_ALLOCATOR_AVAILABLE,
        "SpyderP05_MultiStrategyAllocator": MULTI_STRATEGY_ALLOCATOR_AVAILABLE,
        "SpyderP06_StrategyRotation": STRATEGY_ROTATION_AVAILABLE,
        "SpyderP07_RenaissancePositionSizer": RENAISSANCE_POSITION_SIZER_AVAILABLE,
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
            "portfolio_management": PORTFOLIO_MANAGER_AVAILABLE,
            "allocation_optimization": ALLOCATION_OPTIMIZER_AVAILABLE,
            "correlation_analysis": CORRELATION_ANALYZER_AVAILABLE,
            "capital_allocation": CAPITAL_ALLOCATOR_AVAILABLE,
            "multi_strategy_allocation": MULTI_STRATEGY_ALLOCATOR_AVAILABLE,
            "strategy_rotation": STRATEGY_ROTATION_AVAILABLE,
        },
    }


def create_portfolio_manager():
    """
    Factory function to create a PortfolioManager instance.

    Returns:
        PortfolioManager: Configured portfolio manager

    Raises:
        ImportError: If PortfolioManager is not available
    """
    if not PORTFOLIO_MANAGER_AVAILABLE:
        raise ImportError("PortfolioManager module is not available")

    return PortfolioManager()


def create_optimization_suite():
    """
    Factory function to create a suite of optimization tools.

    Returns:
        dict: Dictionary containing optimizer instances

    Raises:
        ImportError: If required modules are not available
    """
    suite = {}

    if ALLOCATION_OPTIMIZER_AVAILABLE:
        suite["allocation_optimizer"] = AllocationOptimizer()

    if CORRELATION_ANALYZER_AVAILABLE:
        suite["correlation_analyzer"] = CorrelationAnalyzer()

    if CAPITAL_ALLOCATOR_AVAILABLE:
        suite["capital_allocator"] = CapitalAllocator()

    if MULTI_STRATEGY_ALLOCATOR_AVAILABLE:
        suite["multi_strategy_allocator"] = MultiStrategyAllocator()

    if STRATEGY_ROTATION_AVAILABLE:
        suite["strategy_rotation"] = StrategyRotation()

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
        print(f"💼 {info['package_name']} v{info['version']}")
        print(
            f"✅ {info['available_modules']}/{info['total_modules']} modules available"
        )

        if info["available_modules"] == info["total_modules"]:
            print("🚀 All portfolio management modules loaded successfully")
            return True
        else:
            print("⚠️ Some portfolio management modules are missing")
            for module, status in info["module_status"].items():
                status_icon = "✅" if status else "❌"
                print(f"   {status_icon} {module}")
            return False

    except Exception as e:
        print(f"❌ Portfolio management package validation failed: {e}")
        return False


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
    "create_portfolio_manager",
    "create_optimization_suite",
    "validate_package",
]

# Conditionally add available classes to __all__
if PORTFOLIO_MANAGER_AVAILABLE:
    __all__.extend(["PortfolioManager"])

if ALLOCATION_OPTIMIZER_AVAILABLE:
    __all__.extend(["AllocationOptimizer"])

if CORRELATION_ANALYZER_AVAILABLE:
    __all__.extend(["CorrelationAnalyzer"])

if CAPITAL_ALLOCATOR_AVAILABLE:
    __all__.extend(["CapitalAllocator"])

if MULTI_STRATEGY_ALLOCATOR_AVAILABLE:
    __all__.extend(["MultiStrategyAllocator"])

if STRATEGY_ROTATION_AVAILABLE:
    __all__.extend(["StrategyRotation"])

if RENAISSANCE_POSITION_SIZER_AVAILABLE:
    __all__.extend([
        "RenaissancePositionSizer",
        "PositionSizeMethod",
        "PositionSizeResult",
        "TradeRecord",
        "PerformanceMetrics",
        "create_position_sizer",
    ])

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Perform package validation on import
if __name__ != "__main__":
    validate_package()
else:
    # If running as main, show detailed package info
    print("=" * 70)
    print("SPYDER P - PORTFOLIO MANAGEMENT PACKAGE")
    print("=" * 70)
    validate_package()
    info = get_package_info()
    print("\nPackage Details:")
    for key, value in info.items():
        if key != "module_status":
            print(f"  {key}: {value}")
