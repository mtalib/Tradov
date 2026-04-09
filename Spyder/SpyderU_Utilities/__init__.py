#!/usr/bin/env python3
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderU_Utilities/__init__.py
Purpose: Utility functions and classes package initialization

Description:
    This package provides various utility modules for the Spyder trading system,
    including logging, error handling, date/time utilities, validation, and more.

Author: Mohamed Talib
Date: 2025-06-24
Version: 1.4
"""

# ==============================================================================
# MODULE IMPORTS (DEFENSIVE - ACTUAL EXISTING MODULES)
# ==============================================================================
import logging

__all__ = []

# SpyderU01_Logger - ALWAYS AVAILABLE
try:
    from .SpyderU01_Logger import SpyderLogger, get_logger

    __all__.extend(["SpyderLogger", "get_logger"])
except ImportError as e:
    logging.info("Critical: SpyderU01_Logger import failed: %s", e)

# SpyderU02_ErrorHandler - COMPREHENSIVE LEAN VERSION
try:
    from .SpyderU02_ErrorHandler import (ErrorCategory, ErrorSeverity,
                                        SpyderErrorHandler)

    __all__.extend(["SpyderErrorHandler", "ErrorCategory", "ErrorSeverity"])
except ImportError as e:
    logging.info("Warning: SpyderU02_ErrorHandler import failed: %s", e)

# SpyderU03_DateTimeUtils - DATE/TIME UTILITIES
try:
    from .SpyderU03_DateTimeUtils import DateTimeUtils, TradingCalendar

    __all__.extend(["DateTimeUtils", "TradingCalendar"])
except ImportError as e:
    logging.info("Warning: SpyderU03_DateTimeUtils import failed: %s", e)

# SpyderU04_Encryption - SECURITY UTILITIES
try:
    from .SpyderU04_Encryption import (EncryptionManager, decrypt_data,
                                    encrypt_data)

    __all__.extend(["EncryptionManager", "encrypt_data", "decrypt_data"])
except ImportError as e:
    logging.info("Warning: SpyderU04_Encryption import failed: %s", e)

# SpyderU05_NetworkUtils - NETWORK UTILITIES
try:
    from .SpyderU05_NetworkUtils import NetworkUtils, check_internet_connection

    __all__.extend(["NetworkUtils", "check_internet_connection"])
except ImportError as e:
    logging.info("Warning: SpyderU05_NetworkUtils import failed: %s", e)

# SpyderU06_MathUtils - MATHEMATICAL UTILITIES
# NOTE: Deferred from eager load — imports scipy which adds 300ms to startup.
# Import SpyderU06_MathUtils directly when MathUtils is needed.
# try:
#     from .SpyderU06_MathUtils import MathUtils, calculate_sharpe_ratio

# SpyderU07_Constants - SYSTEM CONSTANTS
try:
    from .SpyderU07_Constants import (
        # System info
        SYSTEM_NAME, SYSTEM_VERSION, SYSTEM_DESCRIPTION,
        # Trading constants
        PRIMARY_SYMBOL, OPTION_MULTIPLIER, SPY_CONTRACT_MULTIPLIER,
        SPX_CONTRACT_MULTIPLIER, OPTIONS_TICK_SIZE, MAX_POSITIONS, MAX_POSITION_SIZE,
        # Strategy framework requirements
        MAX_DAILY_TRADES, MAX_PORTFOLIO_RISK, STOP_LOSS_PERCENTAGE, TAKE_PROFIT_PERCENTAGE,
        SESSION_TIMEOUT,
        # Calendar constants
        TRADING_DAYS_PER_YEAR, TRADING_DAYS_PER_MONTH, TRADING_HOURS_PER_DAY,
        # Market hours
        MARKET_OPEN_TIME, MARKET_CLOSE_TIME, PRE_MARKET_OPEN, AFTER_HOURS_CLOSE,
        # Strategy constants
        IRON_CONDOR_PROFIT_TARGET, IRON_BUTTERFLY_PROFIT_TARGET, CREDIT_SPREAD_PROFIT_TARGET,
        CREDIT_SPREAD_STOP_LOSS, IRON_CONDOR_STOP_LOSS, IRON_BUTTERFLY_STOP_LOSS,
        MIN_IVP_THRESHOLD, OPTIMAL_ENTRY_START, OPTIMAL_ENTRY_END,
        RSI_MIN, RSI_MAX, VIX_MIN, VIX_MAX,
        # Iron Condor parameters
        IRON_CONDOR_MAX_WIDTH, IRON_CONDOR_MIN_PREMIUM,
        # Zero DTE
        ZERO_DTE_POSITION_REDUCTION, ZERO_DTE_PROFIT_TARGET, ZERO_DTE_MAX_TRADES,
        # Daily trading limits
        MIN_DAILY_TRADES_MONDAY, MAX_DAILY_TRADES_MONDAY,
        MIN_DAILY_TRADES_OTHER, MAX_DAILY_TRADES_OTHER,
        # Risk management
        MAX_DAILY_LOSS_PERCENT, MAX_POSITION_SIZE_PERCENT, MAX_PORTFOLIO_HEAT,
        MAX_PORTFOLIO_HEAT_MONDAY, MAX_PORTFOLIO_HEAT_OTHER,
        DEFAULT_STOP_LOSS, DEFAULT_TAKE_PROFIT,
        # API / connection
        CONNECTION_TIMEOUT, MAX_CONNECTION_RETRIES,
        # Performance constants
        LATENCY_SAMPLE_SIZE, MAX_ORDER_LATENCY, MAX_DATA_LATENCY, MAX_CALCULATION_TIME,
        MAX_PREDICTION_LATENCY_MS, FEATURE_CACHE_SIZE, PREDICTION_BATCH_SIZE,
        # Options specific
        MIN_STRIKE_DISTANCE, MAX_STRIKE_DISTANCE, STRIKE_INTERVAL,
        MIN_DTE_FOR_ENTRY, MAX_DTE_FOR_ENTRY, OPTIMAL_DTE_RANGE,
        # Greeks
        DELTA_THRESHOLD, GAMMA_THRESHOLD, THETA_THRESHOLD, VEGA_THRESHOLD, RHO_THRESHOLD,
        MAX_DELTA_EXPOSURE, MAX_GAMMA_EXPOSURE, MAX_VEGA_EXPOSURE,
        # Market regime
        LOW_VOLATILITY_THRESHOLD, HIGH_VOLATILITY_THRESHOLD,
        TREND_THRESHOLD, SIDEWAYS_THRESHOLD,
        IV_RANK_LOW, IV_RANK_HIGH, IV_SKEW_THRESHOLD,
        # Performance thresholds
        MIN_WIN_RATE, MIN_PROFIT_FACTOR, MIN_SHARPE_RATIO, MAX_DRAWDOWN,
        MIN_EVALUATION_TRADES, MIN_EVALUATION_DAYS,
        # Enums
        SignalType, OptionType, PositionSide,
        # Strategy names
        STRATEGY_IRON_CONDOR, STRATEGY_IRON_BUTTERFLY, STRATEGY_BULL_PUT_SPREAD,
        STRATEGY_BEAR_CALL_SPREAD, STRATEGY_ZERO_DTE, STRATEGY_CALENDAR_SPREAD,
        STRATEGY_DIAGONAL_SPREAD,
        # Feature flags
        DEFAULT_FEATURE_FLAGS,
        # System performance
        MAX_MEMORY_USAGE_MB, MAX_CPU_USAGE_PERCENT, MAX_WORKER_THREADS,
        # Database
        DATABASE_URL, DATABASE_BATCH_SIZE, TRADE_RETENTION_DAYS,
        # Logging
        DEFAULT_LOG_LEVEL, LOG_FORMAT, MAX_LOG_SIZE_MB,
        # Validation
        validate_constants,
    )
    __all__.extend([
        "SYSTEM_NAME", "SYSTEM_VERSION", "SYSTEM_DESCRIPTION",
        "PRIMARY_SYMBOL", "OPTION_MULTIPLIER", "SPY_CONTRACT_MULTIPLIER",
        "SPX_CONTRACT_MULTIPLIER", "OPTIONS_TICK_SIZE", "MAX_POSITIONS", "MAX_POSITION_SIZE",
        "MAX_DAILY_TRADES", "MAX_PORTFOLIO_RISK", "STOP_LOSS_PERCENTAGE", "TAKE_PROFIT_PERCENTAGE",
        "SESSION_TIMEOUT", "TRADING_DAYS_PER_YEAR", "TRADING_DAYS_PER_MONTH", "TRADING_HOURS_PER_DAY",
        "MARKET_OPEN_TIME", "MARKET_CLOSE_TIME", "PRE_MARKET_OPEN", "AFTER_HOURS_CLOSE",
        "IRON_CONDOR_PROFIT_TARGET", "IRON_BUTTERFLY_PROFIT_TARGET", "CREDIT_SPREAD_PROFIT_TARGET",
        "CREDIT_SPREAD_STOP_LOSS", "IRON_CONDOR_STOP_LOSS", "IRON_BUTTERFLY_STOP_LOSS",
        "MIN_IVP_THRESHOLD", "OPTIMAL_ENTRY_START", "OPTIMAL_ENTRY_END",
        "RSI_MIN", "RSI_MAX", "VIX_MIN", "VIX_MAX",
        "IRON_CONDOR_MAX_WIDTH", "IRON_CONDOR_MIN_PREMIUM",
        "ZERO_DTE_POSITION_REDUCTION", "ZERO_DTE_PROFIT_TARGET", "ZERO_DTE_MAX_TRADES",
        "MIN_DAILY_TRADES_MONDAY", "MAX_DAILY_TRADES_MONDAY",
        "MIN_DAILY_TRADES_OTHER", "MAX_DAILY_TRADES_OTHER",
        "MAX_DAILY_LOSS_PERCENT", "MAX_POSITION_SIZE_PERCENT", "MAX_PORTFOLIO_HEAT",
        "MAX_PORTFOLIO_HEAT_MONDAY", "MAX_PORTFOLIO_HEAT_OTHER",
        "DEFAULT_STOP_LOSS", "DEFAULT_TAKE_PROFIT",
        "CONNECTION_TIMEOUT", "MAX_CONNECTION_RETRIES",
        "LATENCY_SAMPLE_SIZE", "MAX_ORDER_LATENCY", "MAX_DATA_LATENCY", "MAX_CALCULATION_TIME",
        "MAX_PREDICTION_LATENCY_MS", "FEATURE_CACHE_SIZE", "PREDICTION_BATCH_SIZE",
        "MIN_STRIKE_DISTANCE", "MAX_STRIKE_DISTANCE", "STRIKE_INTERVAL",
        "MIN_DTE_FOR_ENTRY", "MAX_DTE_FOR_ENTRY", "OPTIMAL_DTE_RANGE",
        "DELTA_THRESHOLD", "GAMMA_THRESHOLD", "THETA_THRESHOLD", "VEGA_THRESHOLD", "RHO_THRESHOLD",
        "MAX_DELTA_EXPOSURE", "MAX_GAMMA_EXPOSURE", "MAX_VEGA_EXPOSURE",
        "LOW_VOLATILITY_THRESHOLD", "HIGH_VOLATILITY_THRESHOLD",
        "TREND_THRESHOLD", "SIDEWAYS_THRESHOLD",
        "IV_RANK_LOW", "IV_RANK_HIGH", "IV_SKEW_THRESHOLD",
        "MIN_WIN_RATE", "MIN_PROFIT_FACTOR", "MIN_SHARPE_RATIO", "MAX_DRAWDOWN",
        "MIN_EVALUATION_TRADES", "MIN_EVALUATION_DAYS",
        "SignalType", "OptionType", "PositionSide",
        "STRATEGY_IRON_CONDOR", "STRATEGY_IRON_BUTTERFLY", "STRATEGY_BULL_PUT_SPREAD",
        "STRATEGY_BEAR_CALL_SPREAD", "STRATEGY_ZERO_DTE", "STRATEGY_CALENDAR_SPREAD",
        "STRATEGY_DIAGONAL_SPREAD",
        "DEFAULT_FEATURE_FLAGS",
        "MAX_MEMORY_USAGE_MB", "MAX_CPU_USAGE_PERCENT", "MAX_WORKER_THREADS",
        "DATABASE_URL", "DATABASE_BATCH_SIZE", "TRADE_RETENTION_DAYS",
        "DEFAULT_LOG_LEVEL", "LOG_FORMAT", "MAX_LOG_SIZE_MB",
        "validate_constants",
    ])
except ImportError as e:
    logging.info("Warning: SpyderU07_Constants import failed: %s", e)

# SpyderU08_Validators - DATA VALIDATION
try:
    from .SpyderU08_Validators import DataValidators, validate_order_data

    __all__.extend(["DataValidators", "validate_order_data"])
except ImportError as e:
    logging.info("Warning: SpyderU08_Validators import failed: %s", e)

# SpyderU09_DataTypes - DATA TYPE DEFINITIONS
try:
    from .SpyderU09_DataTypes import MarketData, OrderData, PositionData

    __all__.extend(["MarketData", "OrderData", "PositionData"])
except ImportError as e:
    logging.info("Warning: SpyderU09_DataTypes import failed: %s", e)

# SpyderU10_TradingCalendar - TRADING CALENDAR
try:
    from .SpyderU10_TradingCalendar import TradingCalendar as Calendar
    from .SpyderU10_TradingCalendar import get_trading_calendar

    __all__.extend(["Calendar", "get_trading_calendar"])
except ImportError as e:
    logging.info("Warning: SpyderU10_TradingCalendar import failed: %s", e)

# SpyderU11_FeatureFlags - FEATURE FLAG MANAGEMENT
try:
    from .SpyderU11_FeatureFlags import FeatureFlags, check_feature_enabled

    __all__.extend(["FeatureFlags", "check_feature_enabled"])
except ImportError as e:
    logging.info("Warning: SpyderU11_FeatureFlags import failed: %s", e)

# SpyderU13_TechnicalIndicators - TECHNICAL ANALYSIS INDICATORS
try:
    from .SpyderU13_TechnicalIndicators import (TechnicalIndicators,
                                                calculate_macd, calculate_rsi)

    __all__.extend(["TechnicalIndicators", "calculate_rsi", "calculate_macd"])
except ImportError as e:
    logging.info("Warning: SpyderU13_TechnicalIndicators import failed: %s", e)

# SpyderU14_OptionStrategies - OPTION STRATEGY UTILITIES
try:
    from .SpyderU14_OptionStrategies import (OptionStrategy,
                                            calculate_option_payoff)

    __all__.extend(["OptionStrategy", "calculate_option_payoff"])
except ImportError as e:
    logging.info("Warning: SpyderU14_OptionStrategies import failed: %s", e)

# SpyderU15_PerformanceMetrics - PERFORMANCE CALCULATION
try:
    from .SpyderU15_PerformanceMetrics import (PerformanceCalculator,
                                            calculate_metrics)

    __all__.extend(["PerformanceCalculator", "calculate_metrics"])
except ImportError as e:
    logging.info("Warning: SpyderU15_PerformanceMetrics import failed: %s", e)

# SpyderU16_TechnicalAnalysis - ADVANCED TECHNICAL ANALYSIS
# NOTE: Deferred from eager load — its module-level import of SpyderU_Utilities
# (short form) triggers a full second load of this __init__, adding ~340ms.
# Import SpyderU16_TechnicalAnalysis directly when TechnicalAnalysis is needed.
# try:
#     from .SpyderU16_TechnicalAnalysis import TechnicalAnalysis
#     __all__.extend(["TechnicalAnalysis"])
# except ImportError as e:
#     logging.info("Warning: SpyderU16_TechnicalAnalysis import failed: %s", e)

# SpyderU18_DependencyAnalyzer - DEPENDENCY ANALYSIS
# NOTE: Deferred from eager load — imports networkx which adds 80ms to startup.
# Import SpyderU18_DependencyAnalyzer directly when DependencyAnalyzer is needed.
# try:
#     from .SpyderU18_DependencyAnalyzer import DependencyAnalyzer

# SpyderU19_InteractionMatrix - MODULE INTERACTION MATRIX
try:
    from .SpyderU19_InteractionMatrix import InteractionMatrix

    __all__.extend(["InteractionMatrix"])
except ImportError as e:
    logging.info("Warning: SpyderU19_InteractionMatrix import failed: %s", e)

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def get_version():
    """Get utilities package version."""
    return "1.4.0"


def list_available_utilities():
    """List all available utility modules."""
    available = []
    for module in __all__:
        try:
            # Check if the module/class is actually available
            if module in globals():
                available.append(module)
        except Exception:
            pass
    return available


# ==============================================================================
# INITIALIZATION
# ==============================================================================
# Count successfully loaded modules
loaded_modules = len([m for m in __all__ if m in globals()])
logging.info("✅ SpyderU_Utilities: %s modules loaded successfully", loaded_modules)

# ==============================================================================
# BACKWARDS COMPATIBILITY ALIASES
# ==============================================================================
# Add aliases for commonly used but renamed classes
try:
    # Alias for Validators -> DataValidators
    from .SpyderU08_Validators import DataValidators as Validators

    __all__.append("Validators")
except Exception as e:
    logging.debug("Optional alias Validators not available: %s", e)

try:
    # Alias for validate_order -> validate_order_data
    from .SpyderU08_Validators import validate_order_data as validate_order

    __all__.append("validate_order")
except Exception as e:
    logging.debug("Optional alias validate_order not available: %s", e)

try:
    # Other common aliases
    from .SpyderU04_Encryption import EncryptionManager as Encryption

    __all__.append("Encryption")

    from .SpyderU04_Encryption import encrypt_data as encrypt

    __all__.append("encrypt")

    from .SpyderU04_Encryption import decrypt_data as decrypt

    __all__.append("decrypt")
except Exception as e:
    logging.debug("Optional encryption aliases not available: %s", e)

try:
    from .SpyderU05_NetworkUtils import \
        check_internet_connection as check_connection

    __all__.append("check_connection")
except Exception as e:
    logging.debug("Optional alias check_connection not available: %s", e)

# Alias deferred: SpyderU06_MathUtils (scipy) is not eagerly loaded.
# Import calculate_sharpe_ratio directly from SpyderU06_MathUtils when needed.

try:
    from .SpyderU09_DataTypes import MarketData as SpyderDataTypes

    __all__.append("SpyderDataTypes")
except Exception as e:
    logging.debug("Optional alias SpyderDataTypes not available: %s", e)

try:
    from .SpyderU11_FeatureFlags import \
        check_feature_enabled as is_feature_enabled

    __all__.append("is_feature_enabled")
except Exception as e:
    logging.debug("Optional alias is_feature_enabled not available: %s", e)

try:
    from .SpyderU14_OptionStrategies import OptionStrategy as OptionStrategies

    __all__.append("OptionStrategies")
except Exception as e:
    logging.debug("Optional alias OptionStrategies not available: %s", e)

try:
    from .SpyderU15_PerformanceMetrics import \
        PerformanceCalculator as PerformanceMetrics

    __all__.append("PerformanceMetrics")
except Exception as e:
    logging.debug("Optional alias PerformanceMetrics not available: %s", e)

# SpyderU44_ShutdownCoordinator - GRACEFUL SHUTDOWN
try:
    from .SpyderU44_ShutdownCoordinator import ShutdownCoordinator, get_shutdown_coordinator

    __all__.extend(["ShutdownCoordinator", "get_shutdown_coordinator"])
except ImportError as e:
    logging.info("Warning: SpyderU44_ShutdownCoordinator import failed: %s", e)

# SpyderU45_RetryWithBackoff - EXPONENTIAL BACKOFF RETRY
try:
    from .SpyderU45_RetryWithBackoff import (
        retry_async, retry_sync, retry_call_async, retry_call_sync,
        tradier_retry, datafeed_retry, http_retry,
    )

    __all__.extend([
        "retry_async", "retry_sync", "retry_call_async", "retry_call_sync",
        "tradier_retry", "datafeed_retry", "http_retry",
    ])
except ImportError as e:
    logging.info("Warning: SpyderU45_RetryWithBackoff import failed: %s", e)

# SpyderU12_AgentIntegration - AGENT REGISTRY
try:
    from .SpyderU12_AgentIntegration import (
        AgentRegistry,
        AgentSeries,
        AgentStatus,
        AgentMetrics,
        AgentRecord,
        get_registry,
    )
    __all__.extend([
        "AgentRegistry", "AgentSeries", "AgentStatus",
        "AgentMetrics", "AgentRecord", "get_registry",
    ])
except ImportError as e:
    logging.info("Warning: SpyderU12_AgentIntegration import failed: %s", e)

# SpyderU46_SecretsManager - CENTRALISED SECRETS MANAGEMENT
try:
    from .SpyderU46_SecretsManager import SecretsManager, get_secrets
    __all__.extend(["SecretsManager", "get_secrets"])
except ImportError as e:
    logging.info("Warning: SpyderU46_SecretsManager import failed: %s", e)

# U20, U22–U24, U27, U40, U41 — additional utility modules
# NOTE: U20 is deferred — imports scipy.stats which adds ~270ms to startup.
# Import SpyderU20_InstitutionalLibraries directly when InstitutionalLibraries is needed.
# try:
#     from .SpyderU20_InstitutionalLibraries import InstitutionalLibraries
#     __all__.extend(["InstitutionalLibraries"])
# except ImportError as e:
#     logging.info("Warning: SpyderU20_InstitutionalLibraries import failed: %s", e)

try:
    from .SpyderU22_ETTimeDisplay import SimpleETDisplay
    __all__.extend(["SimpleETDisplay"])
except ImportError as e:
    logging.info("Warning: SpyderU22_ETTimeDisplay import failed: %s", e)

try:
    from .SpyderU23_MemoryMonitor import SpyderMemoryMonitor
    __all__.extend(["SpyderMemoryMonitor"])
except ImportError as e:
    logging.info("Warning: SpyderU23_MemoryMonitor import failed: %s", e)

# SpyderU24_StyleManager
# NOTE: Deferred from eager load — imports PySide6.QtWidgets which adds ~60ms to startup.
# This module is only needed for GUI components; import SpyderU24_StyleManager directly.
# try:
#     from .SpyderU24_StyleManager import SpyderStyleManager
#     __all__.extend(["SpyderStyleManager"])
# except ImportError as e:
#     logging.info("Warning: SpyderU24_StyleManager import failed: %s", e)

try:
    from .SpyderU27_SystemOptimizer import SystemOptimizer
    __all__.extend(["SystemOptimizer"])
except ImportError as e:
    logging.info("Warning: SpyderU27_SystemOptimizer import failed: %s", e)

try:
    from .SpyderU40_RateLimiter import TokenBucket, RateLimiter, MultiRateLimiter
    __all__.extend(["TokenBucket", "RateLimiter", "MultiRateLimiter"])
except ImportError as e:
    logging.info("Warning: SpyderU40_RateLimiter import failed: %s", e)

try:
    from .SpyderU41_CircuitBreaker import CircuitBreaker
    __all__.extend(["CircuitBreaker"])
except ImportError as e:
    logging.info("Warning: SpyderU41_CircuitBreaker import failed: %s", e)

try:
    from .SpyderU17_LLMUtils import (
        get_primary_model, get_fast_model, get_code_model, get_finance_model,
    )
    __all__.extend(["get_primary_model", "get_fast_model",
                    "get_code_model", "get_finance_model"])
except ImportError as e:
    logging.info("Warning: SpyderU17_LLMUtils not available: %s", e)

try:
    from .SpyderU42_StrategyCircuitBreaker import StrategyCircuitBreaker
    __all__.extend(["StrategyCircuitBreaker"])
except ImportError as e:
    logging.info("Warning: SpyderU42_StrategyCircuitBreaker not available: %s", e)

try:
    from .SpyderU43_CorrelationLogger import CorrelationFilter, StructuredFormatter
    __all__.extend(["CorrelationFilter", "StructuredFormatter"])
except ImportError as e:
    logging.info("Warning: SpyderU43_CorrelationLogger not available: %s", e)

# ==============================================================================
# PACKAGE INFO
# ==============================================================================
__version__ = "1.4.1"
__author__ = "Mohamed Talib"
__description__ = "Utility functions and classes for Spyder trading system"
