#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderE_Risk
Purpose: Comprehensive risk management and position protection
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-02

Package Description:
    The SpyderE_Risk package provides comprehensive risk management capabilities
    including position sizing, Greek limits management, circuit breakers,
    automatic rebalancing, drawdown control, and real-time stress testing.
    This package ensures trading operations stay within defined risk parameters.

Modules Overview:
    • SpyderE00_RiskProtocol: Typed Protocol contracts for E↔D series boundary
    • SpyderE01_RiskManager: Core risk management engine
    • SpyderE02_PositionSizer: Dynamic position sizing algorithms
    • SpyderE03_StopLossManager: Automated stop loss management
    • SpyderE04_DrawdownControl: Portfolio drawdown protection
    • SpyderE05_AutomaticRebalancer: Portfolio rebalancing automation
    • SpyderE06_RiskMetrics: Risk calculation and reporting
    • SpyderE13_DayProfitTarget: Daily profit target management
    • SpyderE15_GreekLimitsManager: Options Greeks risk limits
    • SpyderE16_CircuitBreakerProtocol: Emergency trading halt system

Key Features:
    • Typed Protocol contracts for cross-series API safety
    • Real-time risk monitoring and alerts
    • Automated position sizing and limits
    • Greek limits enforcement
    • Circuit breaker protection
    • Portfolio stress testing
"""

import logging

# Module imports with error handling

# E00 — Protocol contracts (E↔D boundary)
try:
    from .SpyderE00_RiskProtocol import (
        OverlayPretradeVerdict,
        RiskValidationRequest,
        RiskValidationResult,
        RiskManagerProtocol,
        StrategyStateProvider,
    )
except ImportError:
    logging.info("Warning: Could not import SpyderE00_RiskProtocol")

try:
    from .SpyderE01_RiskManager import RiskManager, RiskProfile
except ImportError:
    logging.info("Warning: Could not import RiskManager")

try:
    from .SpyderE15_GreekLimitsManager import GreekLimitsManager
except ImportError:
    logging.info("Warning: Could not import GreekLimitsManager")

try:
    from .SpyderE16_CircuitBreakerProtocol import CircuitBreaker
except ImportError:
    logging.info("Warning: Could not import CircuitBreaker")

try:
    from .SpyderE05_AutomaticRebalancer import AutomaticRebalancer
except ImportError:
    logging.info("Warning: Could not import AutomaticRebalancer")

try:
    from .SpyderE02_PositionSizer import PositionSizer
except ImportError:
    logging.info("Warning: Could not import PositionSizer")

try:
    from .SpyderE03_StopLossManager import StopLossManager
except ImportError:
    logging.info("Warning: Could not import StopLossManager")

try:
    from .SpyderE04_DrawdownControl import DrawdownController
except ImportError:
    logging.info("Warning: Could not import DrawdownController")

try:
    from .SpyderE06_RiskMetrics import RiskMetricsCalculator
except ImportError:
    logging.info("Warning: Could not import RiskMetricsCalculator")

try:
    from .SpyderE07_ProbabilisticSharpe import ProbabilisticSharpeCalculator
except ImportError:
    logging.info("Warning: Could not import ProbabilisticSharpeCalculator")

try:
    from .SpyderE08_PositionGroupValidator import PositionGroupValidator
except ImportError:
    logging.info("Warning: Could not import PositionGroupValidator")

try:
    from .SpyderE09_VolatilityRiskManager import VolatilityRiskManager
except ImportError:
    logging.info("Warning: Could not import VolatilityRiskManager")

try:
    from .SpyderE10_CorrelationRiskManager import CorrelationRiskManager
except ImportError:
    logging.info("Warning: Could not import CorrelationRiskManager")

try:
    from .SpyderE11_MaxLossProtection import MaxLossProtection
except ImportError:
    logging.info("Warning: Could not import MaxLossProtection")

try:
    from .SpyderE12_PortfolioVaR import PortfolioVaR
except ImportError:
    logging.info("Warning: Could not import PortfolioVaR")

try:
    from .SpyderE13_DayProfitTarget import DayProfitTargetWidget
except ImportError:
    logging.info("Warning: Could not import DayProfitTargetWidget")

try:
    from .SpyderE14_KellyPositionSizer import KellyPositionSizer
except ImportError:
    logging.info("Warning: Could not import KellyPositionSizer")

try:
    from .SpyderE17_RealTimeStressTesting import RealTimeStressTesting
except ImportError:
    logging.info("Warning: Could not import RealTimeStressTesting")

try:
    from .SpyderE18_FSeriesRiskIntegrator import FSeriesRiskIntegrator
except ImportError:
    logging.info("Warning: Could not import FSeriesRiskIntegrator")

try:
    from .SpyderE19_UnifiedRiskCoordinator import UnifiedRiskCoordinator
except ImportError:
    logging.info("Warning: Could not import UnifiedRiskCoordinator")

try:
    from .SpyderE20_FrustrationAnalyzer import FrustrationAnalyzer
except ImportError:
    logging.info("Warning: Could not import FrustrationAnalyzer")

try:
    from .SpyderE21_HMMRegimeDetector import HMMRegimeDetector
except ImportError:
    logging.info("Warning: Could not import HMMRegimeDetector")

try:
    from .SpyderE22_KernelRegression import KernelRegression
except ImportError:
    logging.info("Warning: Could not import KernelRegression")

try:
    from .SpyderE23_PortfolioOptimizer import PortfolioOptimizer
except ImportError:
    logging.info("Warning: Could not import PortfolioOptimizer")

# Package exports
__all__ = [
    # E00 — Protocol contracts
    "OverlayPretradeVerdict",
    "RiskValidationRequest",
    "RiskValidationResult",
    "RiskManagerProtocol",
    "StrategyStateProvider",
    # Core risk management
    "RiskManager",
    "RiskProfile",
    "GreekLimitsManager",
    "CircuitBreaker",
    "AutomaticRebalancer",
    # Extended E-series risk modules
    "RiskMetricsCalculator",
    "DrawdownController",
    "StopLossManager",
    "PositionSizer",
    "ProbabilisticSharpeCalculator",
    "PositionGroupValidator",
    "VolatilityRiskManager",
    "CorrelationRiskManager",
    "MaxLossProtection",
    "PortfolioVaR",
    "DayProfitTargetWidget",
    "KellyPositionSizer",
    "RealTimeStressTesting",
    "FSeriesRiskIntegrator",
    "UnifiedRiskCoordinator",
    "FrustrationAnalyzer",
    "HMMRegimeDetector",
    "KernelRegression",
    "PortfolioOptimizer",
]

__version__ = "1.0.1"
