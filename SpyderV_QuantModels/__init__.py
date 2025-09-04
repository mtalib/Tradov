#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderV_QuantModels
Purpose: Quantitative models and mathematical engines
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04

Package Description:
    The SpyderV_QuantModels package provides sophisticated quantitative models
    and mathematical engines for options pricing, risk modeling, portfolio
    optimization, and advanced trading strategies. This package implements
    cutting-edge financial mathematics and machine learning models.

Modules Overview:
    • SpyderV01_QuantEngine: Core quantitative analysis engine
    • SpyderV02_ModelManager: Model management and orchestration
    • SpyderV03_DataInterface: Quantitative data interface and processing
    • SpyderV04_OptionsModels: Options pricing and Greeks calculations
    • SpyderV05_RiskModels: Risk modeling and VaR calculations
    • SpyderV06_VolatilityModels: Volatility surface and smile modeling
    • SpyderV07_CorrelationModels: Asset correlation and covariance models
    • SpyderV08_MachineLearning: ML models for trading signal generation
    • SpyderV09_StatisticalModels: Statistical analysis and testing
    • SpyderV10_OptimizationEngines: Portfolio and strategy optimization

Key Features:
    • Advanced options pricing models (Black-Scholes, Heston, etc.)
    • Sophisticated volatility modeling and surface construction
    • Machine learning integration for predictive analytics
    • Risk modeling with VaR, CVaR, and stress testing
    • Statistical arbitrage and mean reversion models
    • Portfolio optimization using modern portfolio theory
    • Real-time model validation and backtesting
    • High-performance numerical computation
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

# Quant Engine
try:
    from .SpyderV01_QuantEngine import (
        QuantEngine,
        # Add main classes from QuantEngine when inspected
    )

    QUANT_ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV01_QuantEngine not available: {e}")
    QUANT_ENGINE_AVAILABLE = False

# Model Manager
try:
    from .SpyderV02_ModelManager import (
        ModelManager,
        # Add main classes from ModelManager when inspected
    )

    MODEL_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV02_ModelManager not available: {e}")
    MODEL_MANAGER_AVAILABLE = False

# Data Interface
try:
    from .SpyderV03_DataInterface import (
        DataInterface,
        # Add main classes from DataInterface when inspected
    )

    DATA_INTERFACE_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV03_DataInterface not available: {e}")
    DATA_INTERFACE_AVAILABLE = False

# Options Models
try:
    from .SpyderV04_OptionsModels import (
        OptionsModels,
        BlackScholesModel,
        HestonModel,
        # Add main classes from OptionsModels when inspected
    )

    OPTIONS_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV04_OptionsModels not available: {e}")
    OPTIONS_MODELS_AVAILABLE = False

# Risk Models
try:
    from .SpyderV05_RiskModels import (
        RiskModels,
        VaRCalculator,
        StressTestEngine,
        # Add main classes from RiskModels when inspected
    )

    RISK_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV05_RiskModels not available: {e}")
    RISK_MODELS_AVAILABLE = False

# Volatility Models
try:
    from .SpyderV06_VolatilityModels import (
        VolatilityModels,
        VolatilitySurface,
        VolatilitySmile,
        # Add main classes from VolatilityModels when inspected
    )

    VOLATILITY_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV06_VolatilityModels not available: {e}")
    VOLATILITY_MODELS_AVAILABLE = False

# Correlation Models
try:
    from .SpyderV07_CorrelationModels import (
        CorrelationModels,
        CovarianceMatrix,
        # Add main classes from CorrelationModels when inspected
    )

    CORRELATION_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV07_CorrelationModels not available: {e}")
    CORRELATION_MODELS_AVAILABLE = False

# Machine Learning
try:
    from .SpyderV08_MachineLearning import (
        MachineLearning,
        TradingSignalML,
        PredictiveModels,
        # Add main classes from MachineLearning when inspected
    )

    MACHINE_LEARNING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV08_MachineLearning not available: {e}")
    MACHINE_LEARNING_AVAILABLE = False

# Statistical Models
try:
    from .SpyderV09_StatisticalModels import (
        StatisticalModels,
        MeanReversionModels,
        StatisticalArbitrage,
        # Add main classes from StatisticalModels when inspected
    )

    STATISTICAL_MODELS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV09_StatisticalModels not available: {e}")
    STATISTICAL_MODELS_AVAILABLE = False

# Optimization Engines
try:
    from .SpyderV10_OptimizationEngines import (
        OptimizationEngines,
        PortfolioOptimizer,
        StrategyOptimizer,
        # Add main classes from OptimizationEngines when inspected
    )

    OPTIMIZATION_ENGINES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderV10_OptimizationEngines not available: {e}")
    OPTIMIZATION_ENGINES_AVAILABLE = False

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
        "SpyderV04_OptionsModels": OPTIONS_MODELS_AVAILABLE,
        "SpyderV05_RiskModels": RISK_MODELS_AVAILABLE,
        "SpyderV06_VolatilityModels": VOLATILITY_MODELS_AVAILABLE,
        "SpyderV07_CorrelationModels": CORRELATION_MODELS_AVAILABLE,
        "SpyderV08_MachineLearning": MACHINE_LEARNING_AVAILABLE,
        "SpyderV09_StatisticalModels": STATISTICAL_MODELS_AVAILABLE,
        "SpyderV10_OptimizationEngines": OPTIMIZATION_ENGINES_AVAILABLE,
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
            "correlation_modeling": CORRELATION_MODELS_AVAILABLE,
            "machine_learning": MACHINE_LEARNING_AVAILABLE,
            "statistical_models": STATISTICAL_MODELS_AVAILABLE,
            "optimization_engines": OPTIMIZATION_ENGINES_AVAILABLE,
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

    if MACHINE_LEARNING_AVAILABLE:
        suite["machine_learning"] = MachineLearning()
        suite["trading_signal_ml"] = TradingSignalML()
        suite["predictive_models"] = PredictiveModels()

    if STATISTICAL_MODELS_AVAILABLE:
        suite["statistical_models"] = StatisticalModels()
        suite["mean_reversion_models"] = MeanReversionModels()
        suite["statistical_arbitrage"] = StatisticalArbitrage()

    if OPTIMIZATION_ENGINES_AVAILABLE:
        suite["optimization_engines"] = OptimizationEngines()
        suite["portfolio_optimizer"] = PortfolioOptimizer()
        suite["strategy_optimizer"] = StrategyOptimizer()

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
    if not MACHINE_LEARNING_AVAILABLE:
        raise ImportError("Machine learning models are not available")

    return {
        "machine_learning": MachineLearning(),
        "trading_signal_ml": TradingSignalML(),
        "predictive_models": PredictiveModels(),
    }


def validate_package():
    """
    Validate the package installation and module availability.

    Returns:
        bool: True if package is fully functional, False otherwise
    """
    try:
        info = get_package_info()
        print(f"🧮 {info['package_name']} v{info['version']}")
        print(
            f"✅ {info['available_modules']}/{info['total_modules']} modules available"
        )

        if info["available_modules"] == info["total_modules"]:
            print("🚀 All quantitative model modules loaded successfully")
            return True
        else:
            print("⚠️ Some quantitative model modules are missing")
            for module, status in info["module_status"].items():
                status_icon = "✅" if status else "❌"
                print(f"   {status_icon} {module}")
            return False

    except Exception as e:
        print(f"❌ Quantitative models package validation failed: {e}")
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
    __all__.extend(["OptionsModels", "BlackScholesModel", "HestonModel"])

if RISK_MODELS_AVAILABLE:
    __all__.extend(["RiskModels", "VaRCalculator", "StressTestEngine"])

if VOLATILITY_MODELS_AVAILABLE:
    __all__.extend(["VolatilityModels", "VolatilitySurface", "VolatilitySmile"])

if CORRELATION_MODELS_AVAILABLE:
    __all__.extend(["CorrelationModels", "CovarianceMatrix"])

if MACHINE_LEARNING_AVAILABLE:
    __all__.extend(["MachineLearning", "TradingSignalML", "PredictiveModels"])

if STATISTICAL_MODELS_AVAILABLE:
    __all__.extend(["StatisticalModels", "MeanReversionModels", "StatisticalArbitrage"])

if OPTIMIZATION_ENGINES_AVAILABLE:
    __all__.extend(["OptimizationEngines", "PortfolioOptimizer", "StrategyOptimizer"])

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Perform package validation on import
if __name__ != "__main__":
    validate_package()
else:
    # If running as main, show detailed package info
    print("=" * 70)
    print("SPYDER V - QUANTITATIVE MODELS PACKAGE")
    print("=" * 70)
    validate_package()
    info = get_package_info()
    print("\nPackage Details:")
    for key, value in info.items():
        if key != "module_status":
            print(f"  {key}: {value}")
