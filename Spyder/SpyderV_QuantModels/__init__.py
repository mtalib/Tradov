#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderV_QuantModels
Purpose: Quantitative models and mathematical engines
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-02

Package Description:
    The SpyderV_QuantModels package provides sophisticated quantitative models
    and mathematical engines for options pricing, risk modeling, portfolio
    optimization, and advanced trading strategies. This package implements
    cutting-edge financial mathematics and machine learning models.

Modules Overview:
    • SpyderV01_QuantEngine: Core quantitative analysis engine
    • SpyderV02_ModelManager: Model management and orchestration
    • SpyderV03_DataInterface: Quantitative data interface and processing
    • SpyderV04_RiskManager: Risk modeling and VaR calculations
    • SpyderV05_PricingEngine: Options pricing and Greeks calculations
    • SpyderV06_VolatilityEngine: Volatility surface and smile modeling
    • SpyderV07_AdvancedModels: Advanced models (Merton Jump-Diffusion, crisis detection)
    • SpyderV08_AIModels: AI models — Transformer pricing + RL trading agent
    • SpyderV09_IVEngine: BSM pricing, Greeks, volatility analysis and surface building
      (extracted from Z04_VolatilityEngine; used by Z04 as its pure-computation backend)

Key Features:
    • Advanced options pricing models (Black-Scholes, Heston, etc.)
    • Sophisticated volatility modeling and surface construction
    • AI/ML integration: Transformer neural network + RL trading agent
    • Risk modeling with VaR, CVaR, and stress testing
    • IV engine for ZMQ subprocess workers
    • High-performance numerical computation
"""

import logging

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

# Quant Engine
try:
    from .SpyderV01_QuantEngine import (
        QuantEngine,
        # Add main classes from QuantEngine when inspected
    )

    QUANT_ENGINE_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV01_QuantEngine not available: %s", e)
    QUANT_ENGINE_AVAILABLE = False

# Model Manager
try:
    from .SpyderV02_ModelManager import (
        ModelManager,
        # Add main classes from ModelManager when inspected
    )

    MODEL_MANAGER_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV02_ModelManager not available: %s", e)
    MODEL_MANAGER_AVAILABLE = False

# Data Interface
try:
    from .SpyderV03_DataInterface import (
        DataInterface,
        # Add main classes from DataInterface when inspected
    )

    DATA_INTERFACE_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV03_DataInterface not available: %s", e)
    DATA_INTERFACE_AVAILABLE = False

# Risk Manager
try:
    from .SpyderV04_RiskManager import (
        RiskManager,
        RiskMetrics,
        PortfolioRisk,
        # Add main classes from RiskManager when inspected
    )

    RISK_MANAGER_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV04_RiskManager not available: %s", e)
    RISK_MANAGER_AVAILABLE = False

# Pricing Engine
try:
    from .SpyderV05_PricingEngine import (
        SpyderPricingEngine,
        OptionContract,
        Greeks,
        PricingParameters,
        PricingModel,
        OptionType,
        ExerciseStyle,
        ModelSelector,
        # Add main classes from PricingEngine when inspected
    )

    PRICING_ENGINE_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV05_PricingEngine not available: %s", e)
    PRICING_ENGINE_AVAILABLE = False

# Volatility Engine
try:
    from .SpyderV06_VolatilityEngine import (
        VolatilityEngine,
        VolatilitySurface,
        VolatilityForecast,
        # Add main classes from VolatilityEngine when inspected
    )

    VOLATILITY_ENGINE_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV06_VolatilityEngine not available: %s", e)
    VOLATILITY_ENGINE_AVAILABLE = False

# Advanced Models
try:
    from .SpyderV07_AdvancedModels import (
        AdvancedModels,
        HestonModel,
        StochasticVolatilityModel,
        # Add main classes from AdvancedModels when inspected
    )

    ADVANCED_MODELS_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV07_AdvancedModels not available: %s", e)
    ADVANCED_MODELS_AVAILABLE = False

# AI Models (Transformer pricing + RL trading agent)
try:
    from .SpyderV08_AIModels import (
        SpyderAIModels,
        AIModelType,
        ModelMode,
        ActionType,
        TransformerConfig,
        RLConfig,
        AIModelsConfig,
        PricingRequest,
        PricingResult,
        TradingSignal,
        ModelPerformance,
        create_ai_models_engine,
    )

    AI_MODELS_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV08_AIModels not available: %s", e)
    AI_MODELS_AVAILABLE = False

# IV Engine (BSM pricing, Greeks, volatility surface — Z04 computation backend)
try:
    from .SpyderV09_IVEngine import (
        VolatilityModel,
        GreekType,
        BlackScholesCalculator,
        GreeksCalculator,
        VolatilityAnalyzer,
        VolatilitySurfaceBuilder,
        CalculationCache,
    )

    IV_ENGINE_AVAILABLE = True
except ImportError as e:
    logging.info("⚠️ SpyderV09_IVEngine not available: %s", e)
    IV_ENGINE_AVAILABLE = False

# Map legacy/expected variable names to the actual ones defined above
OPTIONS_MODELS_AVAILABLE = PRICING_ENGINE_AVAILABLE
RISK_MODELS_AVAILABLE = RISK_MANAGER_AVAILABLE
VOLATILITY_MODELS_AVAILABLE = VOLATILITY_ENGINE_AVAILABLE
CORRELATION_MODELS_AVAILABLE = ADVANCED_MODELS_AVAILABLE
MACHINE_LEARNING_AVAILABLE = AI_MODELS_AVAILABLE

# ==============================================================================
# CONVENIENCE ALIASES (map legacy/expected names to actual classes)
# ==============================================================================
if OPTIONS_MODELS_AVAILABLE:
    OptionsModels = SpyderPricingEngine
    BlackScholesModel = SpyderPricingEngine

if RISK_MODELS_AVAILABLE:
    RiskModels = RiskManager
    VaRCalculator = RiskManager
    StressTestEngine = RiskManager

if VOLATILITY_MODELS_AVAILABLE:
    VolatilityModels = VolatilityEngine
    VolatilitySmile = VolatilitySurface

if CORRELATION_MODELS_AVAILABLE:
    CorrelationModels = AdvancedModels
    CovarianceMatrix = AdvancedModels

# ==============================================================================
# PACKAGE CONVENIENCE FUNCTIONS
# ==============================================================================


def get_available_modules():
    """
    Get a list of available modules in the SpyderV_QuantModels package.

    Returns:
        dict: Dictionary with module availability status
    """
    return {
        "SpyderV01_QuantEngine": QUANT_ENGINE_AVAILABLE,
        "SpyderV02_ModelManager": MODEL_MANAGER_AVAILABLE,
        "SpyderV03_DataInterface": DATA_INTERFACE_AVAILABLE,
        "SpyderV04_RiskManager": RISK_MODELS_AVAILABLE,
        "SpyderV05_PricingEngine": OPTIONS_MODELS_AVAILABLE,
        "SpyderV06_VolatilityEngine": VOLATILITY_MODELS_AVAILABLE,
        "SpyderV07_AdvancedModels": CORRELATION_MODELS_AVAILABLE,
        "SpyderV08_AIModels": AI_MODELS_AVAILABLE,
        "SpyderV09_IVEngine": IV_ENGINE_AVAILABLE,
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
        "package_name": "SpyderV_QuantModels",
        "version": __version__,
        "author": __author__,
        "status": __status__,
        "total_modules": total_modules,
        "available_modules": available_count,
        "module_status": available_modules,
        "capabilities": {
            "quantitative_engine": QUANT_ENGINE_AVAILABLE,
            "model_management": MODEL_MANAGER_AVAILABLE,
            "data_interface": DATA_INTERFACE_AVAILABLE,
            "options_pricing": OPTIONS_MODELS_AVAILABLE,
            "risk_modeling": RISK_MODELS_AVAILABLE,
            "volatility_modeling": VOLATILITY_MODELS_AVAILABLE,
            "advanced_models": CORRELATION_MODELS_AVAILABLE,
            "ai_models": AI_MODELS_AVAILABLE,
            "iv_engine": IV_ENGINE_AVAILABLE,
        },
    }


def create_quantitative_suite():
    """
    Factory function to create a comprehensive quantitative modeling suite.

    Returns:
        dict: Dictionary containing quantitative model instances

    Raises:
        ImportError: If required quantitative modules are not available
    """
    suite = {}

    if QUANT_ENGINE_AVAILABLE:
        suite["quant_engine"] = QuantEngine()

    if MODEL_MANAGER_AVAILABLE:
        suite["model_manager"] = ModelManager()

    if DATA_INTERFACE_AVAILABLE:
        suite["data_interface"] = DataInterface()

    if OPTIONS_MODELS_AVAILABLE:
        suite["options_models"] = OptionsModels()
        suite["black_scholes"] = BlackScholesModel()
        suite["heston_model"] = HestonModel()

    if RISK_MODELS_AVAILABLE:
        suite["risk_models"] = RiskModels()
        suite["var_calculator"] = VaRCalculator()
        suite["stress_test_engine"] = StressTestEngine()

    if VOLATILITY_MODELS_AVAILABLE:
        suite["volatility_models"] = VolatilityModels()
        suite["volatility_surface"] = VolatilitySurface()
        suite["volatility_smile"] = VolatilitySmile()

    if CORRELATION_MODELS_AVAILABLE:
        suite["correlation_models"] = CorrelationModels()
        suite["covariance_matrix"] = CovarianceMatrix()

    if AI_MODELS_AVAILABLE:
        suite["ai_models"] = SpyderAIModels()

    if IV_ENGINE_AVAILABLE:
        suite["iv_engine"] = BlackScholesCalculator()
        suite["greeks_calculator"] = GreeksCalculator()
        suite["volatility_analyzer"] = VolatilityAnalyzer()

    if not suite:
        raise ImportError("No quantitative model modules are available")

    return suite


def create_options_pricing_engine():
    """
    Factory function to create an options pricing engine.

    Returns:
        dict: Options pricing components

    Raises:
        ImportError: If options models are not available
    """
    if not OPTIONS_MODELS_AVAILABLE:
        raise ImportError("Options models are not available")

    return {
        "options_models": OptionsModels(),
        "black_scholes": BlackScholesModel(),
        "heston_model": HestonModel(),
    }


def create_risk_engine():
    """
    Factory function to create a comprehensive risk modeling engine.

    Returns:
        dict: Risk modeling components

    Raises:
        ImportError: If risk models are not available
    """
    if not RISK_MODELS_AVAILABLE:
        raise ImportError("Risk models are not available")

    return {
        "risk_models": RiskModels(),
        "var_calculator": VaRCalculator(),
        "stress_test_engine": StressTestEngine(),
    }


def create_ml_engine():
    """
    Factory function to create a machine learning trading engine.

    Returns:
        dict: Machine learning components

    Raises:
        ImportError: If machine learning models are not available
    """
    if not AI_MODELS_AVAILABLE:
        raise ImportError("AI models (SpyderV08_AIModels) are not available")

    return {
        "ai_models": SpyderAIModels(),
    }


def validate_package():
    """
    Validate the package installation and module availability.

    Returns:
        bool: True if package is fully functional, False otherwise
    """
    try:
        info = get_package_info()
        logging.info("🧮 %s v%s", info['package_name'], info['version'])
        logging.info(
            "✅ %s/%s modules available", info['available_modules'], info['total_modules']
        )

        if info["available_modules"] == info["total_modules"]:
            logging.info("🚀 All quantitative model modules loaded successfully")
            return True
        else:
            logging.info("⚠️ Some quantitative model modules are missing")
            for module, status in info["module_status"].items():
                status_icon = "✅" if status else "❌"
                logging.info("   %s %s", status_icon, module)
            return False

    except Exception as e:
        logging.info("❌ Quantitative models package validation failed: %s", e)
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
    "create_quantitative_suite",
    "create_options_pricing_engine",
    "create_risk_engine",
    "create_ml_engine",
    "validate_package",
]

# Conditionally add available classes to __all__
if QUANT_ENGINE_AVAILABLE:
    __all__.extend(["QuantEngine"])

if MODEL_MANAGER_AVAILABLE:
    __all__.extend(["ModelManager"])

if DATA_INTERFACE_AVAILABLE:
    __all__.extend(["DataInterface"])

if OPTIONS_MODELS_AVAILABLE:
    __all__.extend(["OptionsModels", "BlackScholesModel"])

if ADVANCED_MODELS_AVAILABLE:
    __all__.extend(["HestonModel"])

if RISK_MODELS_AVAILABLE:
    __all__.extend(["RiskModels", "VaRCalculator", "StressTestEngine"])

if VOLATILITY_MODELS_AVAILABLE:
    __all__.extend(["VolatilityModels", "VolatilitySurface", "VolatilitySmile"])

if CORRELATION_MODELS_AVAILABLE:
    __all__.extend(["CorrelationModels", "CovarianceMatrix"])

if AI_MODELS_AVAILABLE:
    __all__.extend([
        "SpyderAIModels", "AIModelType", "ModelMode", "ActionType",
        "TransformerConfig", "RLConfig", "AIModelsConfig",
        "PricingRequest", "PricingResult", "TradingSignal", "ModelPerformance",
        "create_ai_models_engine",
    ])

if IV_ENGINE_AVAILABLE:
    __all__.extend([
        "VolatilityModel", "GreekType", "BlackScholesCalculator",
        "GreeksCalculator", "VolatilityAnalyzer", "VolatilitySurfaceBuilder",
        "CalculationCache",
    ])

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Perform package validation on import
if __name__ != "__main__":
    validate_package()
else:
    # If running as main, show detailed package info
    logging.info("=" * 70)
    logging.info("SPYDER V - QUANTITATIVE MODELS PACKAGE")
    logging.info("=" * 70)
    validate_package()
    info = get_package_info()
    logging.info("\nPackage Details:")
    for key, value in info.items():
        if key != "module_status":
            logging.info("  %s: %s", key, value)
