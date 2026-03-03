import logging
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderE_Risk
Purpose: Comprehensive risk management and position protection
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-29

Package Description:
    The SpyderE_Risk package provides comprehensive risk management capabilities
    including position sizing, Greek limits management, circuit breakers,
    automatic rebalancing, drawdown control, and real-time stress testing.
    This package ensures trading operations stay within defined risk parameters.

Modules Overview:
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
    • Real-time risk monitoring and alerts
    • Automated position sizing and limits
    • Greek limits enforcement
    • Circuit breaker protection
    • Portfolio stress testing
"""

# Module imports with error handling
try:
    from .SpyderE01_RiskManager import RiskManager, RiskProfile
except ImportError:
    logging.info("Warning: Could not import RiskManager")

try:
    from .SpyderE03_GreekLimitsManager import GreekLimitsManager
except ImportError:
    logging.info("Warning: Could not import GreekLimitsManager")

try:
    from .SpyderE04_CircuitBreakerProtocol import CircuitBreaker
except ImportError:
    logging.info("Warning: Could not import CircuitBreaker")

try:
    from .SpyderE05_AutomaticRebalancer import AutomaticRebalancer
except ImportError:
    logging.info("Warning: Could not import AutomaticRebalancer")

# Package exports
__all__ = [
    "RiskManager",
    "RiskProfile",
    "GreekLimitsManager",
    "CircuitBreaker",
    "AutomaticRebalancer",
]

__version__ = "1.0.0"
