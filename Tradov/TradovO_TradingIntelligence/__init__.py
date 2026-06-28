#!/usr/bin/env python3
import logging
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Package: TradovO_TradingIntelligence
Purpose: Advanced trading intelligence and optimization modules
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Package Description:
    The TradovO_TradingIntelligence package provides sophisticated trading intelligence
    capabilities that go beyond basic technical analysis. This package includes advanced
    technical indicators, trading opportunity scanning, and strategy optimization tools
    specifically designed for options trading and market microstructure analysis.

Modules Overview:
    • TradovO01_CoreTechnicalIndicators: Pure Python technical indicators with signal generation
    • TradovO02_TradingOpportunityScanner: Multi-strategy opportunity ranking and scanning
    • TradovO03_StrategyOptimizers: Specialized optimization calculators for options strategies

Key Features:
    • Pure Python implementations (no TA-Lib dependency)
    • Options-specific indicators and calculations
    • Multi-strategy opportunity ranking
    • Pin risk analysis and liquidity scoring
    • Real-time skew anomaly detection
    • Strategy efficiency optimization
    • Regime-aware signal generation
"""

# ==============================================================================
# VERSION INFORMATION
# ==============================================================================
__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mtalib4@gmail.com"
__status__ = "Production"

# ==============================================================================
# CORE MODULE IMPORTS
# ==============================================================================

# Core Technical Indicators
try:
    from .TradovO01_CoreTechnicalIndicators import (
        # Main class
        CoreTechnicalIndicators,
        # Enums and data classes
        SignalType,
        IndicatorStrength,
        TrendDirection,
        VolatilityRegime,
        IndicatorSignal,
        SupportResistanceLevel,
        VolumeProfile,
    )

    CORE_INDICATORS_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ TradovO01_CoreTechnicalIndicators not available: %s", e)
    CORE_INDICATORS_AVAILABLE = False

# Trading Opportunity Scanner
try:
    from .TradovO02_TradingOpportunityScanner import (
        # Main class
        TradingOpportunityScanner,
        # Enums and data classes
        OpportunityType,
        OpportunityPriority,
        MarketBias,
        VolatilityEnvironment,
        TradingOpportunity,
        OpportunityContext,
        StrategyComparison,
    )

    OPPORTUNITY_SCANNER_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ TradovO02_TradingOpportunityScanner not available: %s", e)
    OPPORTUNITY_SCANNER_AVAILABLE = False

# Strategy Optimizers
try:
    from .TradovO03_StrategyOptimizers import (
        # Main classes
        PinRiskCalculator,
        OptionsLiquidityScorer,
        SkewAnomalyDetector,
        StrategyEfficiencyOptimizer,
        # Enums and data classes
        PinRiskLevel,
        LiquidityTier,
        SkewAnomalyType,
        OptimizationObjective,
        PinRiskAnalysis,
        LiquidityScore,
        SkewAnomalyDetection,
        StrategyOptimization,
    )

    STRATEGY_OPTIMIZERS_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ TradovO03_StrategyOptimizers not available: %s", e)
    STRATEGY_OPTIMIZERS_AVAILABLE = False

# ==============================================================================
# PACKAGE CONVENIENCE FUNCTIONS
# ==============================================================================


def get_available_modules():
    """
    Get a list of available modules in the TradovO_TradingIntelligence package.

    Returns:
        dict: Dictionary with module availability status
    """
    return {
        "TradovO01_CoreTechnicalIndicators": CORE_INDICATORS_AVAILABLE,
        "TradovO02_TradingOpportunityScanner": OPPORTUNITY_SCANNER_AVAILABLE,
        "TradovO03_StrategyOptimizers": STRATEGY_OPTIMIZERS_AVAILABLE,
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
        "package_name": "TradovO_TradingIntelligence",
        "version": __version__,
        "author": __author__,
        "status": __status__,
        "total_modules": total_modules,
        "available_modules": available_count,
        "module_status": available_modules,
        "capabilities": {
            "technical_indicators": CORE_INDICATORS_AVAILABLE,
            "opportunity_scanning": OPPORTUNITY_SCANNER_AVAILABLE,
            "strategy_optimization": STRATEGY_OPTIMIZERS_AVAILABLE,
        },
    }


def create_indicators_engine():
    """
    Factory function to create a CoreTechnicalIndicators instance.

    Returns:
        CoreTechnicalIndicators: Configured indicators engine

    Raises:
        ImportError: If CoreTechnicalIndicators is not available
    """
    if not CORE_INDICATORS_AVAILABLE:
        raise ImportError("CoreTechnicalIndicators module is not available")

    return CoreTechnicalIndicators()


def create_opportunity_scanner():
    """
    Factory function to create a TradingOpportunityScanner instance.

    Returns:
        TradingOpportunityScanner: Configured opportunity scanner

    Raises:
        ImportError: If TradingOpportunityScanner is not available
    """
    if not OPPORTUNITY_SCANNER_AVAILABLE:
        raise ImportError("TradingOpportunityScanner module is not available")

    return TradingOpportunityScanner()


def create_strategy_optimizers():
    """
    Factory function to create strategy optimizer instances.

    Returns:
        dict: Dictionary containing optimizer instances

    Raises:
        ImportError: If StrategyOptimizers modules are not available
    """
    if not STRATEGY_OPTIMIZERS_AVAILABLE:
        raise ImportError("StrategyOptimizers modules are not available")

    return {
        "pin_risk_calculator": PinRiskCalculator(),
        "liquidity_scorer": OptionsLiquidityScorer(),
        "skew_anomaly_detector": SkewAnomalyDetector(),
    }


# ==============================================================================
# MODULE VALIDATION
# ==============================================================================


def validate_package():
    """
    Validate the package installation and module availability.

    Returns:
        bool: True if package is fully functional, False otherwise
    """
    try:
        info = get_package_info()
        logging.info("📊 %s v%s", info['package_name'], info['version'])
        logging.info(
            "✅ %s/%s modules available", info['available_modules'], info['total_modules']
        )

        if info["available_modules"] == info["total_modules"]:
            logging.info("🚀 All modules loaded successfully")
            return True
        else:
            logging.info("⚠️ Some modules are missing - package partially functional")
            for module, status in info["module_status"].items():
                status_icon = "✅" if status else "❌"
                logging.info("   %s %s", status_icon, module)
            return False

    except Exception as e:
        logging.info("❌ Package validation failed: %s", e)
        return False


# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================

# Core exports for easy importing
__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Core classes (if available)
    "CoreTechnicalIndicators",
    "TradingOpportunityScanner",
    "PinRiskCalculator",
    "OptionsLiquidityScorer",
    "SkewAnomalyDetector",
    # Enums and data classes
    "SignalType",
    "IndicatorStrength",
    "TrendDirection",
    "VolatilityRegime",
    "IndicatorSignal",
    "SupportResistanceLevel",
    "VolumeProfile",
    "OpportunityType",
    "OpportunityPriority",
    "MarketBias",
    "VolatilityEnvironment",
    "TradingOpportunity",
    "OpportunityContext",
    "StrategyComparison",
    "PinRiskLevel",
    "LiquidityTier",
    "SkewAnomalyType",
    "OptimizationObjective",
    "PinRiskAnalysis",
    "LiquidityScore",
    "SkewAnomalyDetection",
    "StrategyOptimization",
    # Utility functions
    "get_available_modules",
    "get_package_info",
    "create_indicators_engine",
    "create_opportunity_scanner",
    "create_strategy_optimizers",
    "validate_package",
]

# Remove unavailable items from __all__
if not CORE_INDICATORS_AVAILABLE:
    items_to_remove = [
        "CoreTechnicalIndicators",
        "SignalType",
        "IndicatorStrength",
        "TrendDirection",
        "VolatilityRegime",
        "IndicatorSignal",
        "SupportResistanceLevel",
        "VolumeProfile",
    ]
    __all__ = [item for item in __all__ if item not in items_to_remove]

if not OPPORTUNITY_SCANNER_AVAILABLE:
    items_to_remove = [
        "TradingOpportunityScanner",
        "OpportunityType",
        "OpportunityPriority",
        "MarketBias",
        "VolatilityEnvironment",
        "TradingOpportunity",
        "OpportunityContext",
        "StrategyComparison",
    ]
    __all__ = [item for item in __all__ if item not in items_to_remove]

if not STRATEGY_OPTIMIZERS_AVAILABLE:
    items_to_remove = [
        "PinRiskCalculator",
        "OptionsLiquidityScorer",
        "SkewAnomalyDetector",
        "PinRiskLevel",
        "LiquidityTier",
        "SkewAnomalyType",
        "OptimizationObjective",
        "PinRiskAnalysis",
        "LiquidityScore",
        "SkewAnomalyDetection",
        "StrategyOptimization",
    ]
    __all__ = [item for item in __all__ if item not in items_to_remove]

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Perform package validation on import
validate_package()
