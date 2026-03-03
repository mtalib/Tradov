from enum import Enum
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities  
Module: SpyderU07_Constants.py
Purpose: System-wide constants and configuration values with research findings
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-27 Time: 17:00:00

Module Description:
    This module defines all system-wide constants used throughout the Spyder trading
    platform. It includes trading parameters, system limits, API configuration values,
    risk parameters, and research-driven constants for optimal trading performance.
    This is a clean, complete version with all missing constants properly defined.

"""

# =============================================================================
# STANDARD IMPORTS
# =============================================================================
from enum import Enum
from datetime import datetime

# =============================================================================
# SYSTEM INFORMATION
# =============================================================================
SYSTEM_NAME = "SPYDER"
SYSTEM_VERSION = "2.0.0"
SYSTEM_DESCRIPTION = "Autonomous SPY Options Trading System with Research Enhancements"

# =============================================================================
# TRADING CONSTANTS
# =============================================================================
# Symbols
PRIMARY_SYMBOL = "SPY"
OPTION_SYMBOLS = ["SPY"]
INDEX_SYMBOLS = ["SPX", "VIX"]

# Contract specifications
SPY_CONTRACT_MULTIPLIER = 100
SPX_CONTRACT_MULTIPLIER = 100
OPTIONS_TICK_SIZE = 0.01
OPTION_MULTIPLIER = 100  # Options contract multiplier
FUTURES_TICK_SIZE = 0.25

# Position limits
MAX_POSITIONS = 10
MAX_POSITIONS_PER_STRATEGY = 5
MAX_POSITION_SIZE = 100  # contracts
MIN_POSITION_SIZE = 1

# Order limits
MAX_ORDERS_PER_MINUTE = 50
MAX_PENDING_ORDERS = 20
ORDER_TIMEOUT_SECONDS = 30

# =============================================================================
# MARKET HOURS (EASTERN TIME)
# =============================================================================
MARKET_OPEN_TIME = "09:30:00"
MARKET_CLOSE_TIME = "16:00:00"
PRE_MARKET_OPEN = "04:00:00"
AFTER_HOURS_CLOSE = "20:00:00"
EARLY_CLOSE_TIME = "13:00:00"

# Trading session durations (minutes)
REGULAR_SESSION_MINUTES = 390  # 6.5 hours
EXTENDED_SESSION_MINUTES = 960  # 16 hours

# =============================================================================
# CALENDAR CONSTANTS
# =============================================================================
TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = 21
TRADING_HOURS_PER_DAY = 6.5

# Market holidays - major US holidays when markets are closed
MARKET_HOLIDAYS = [
    "New Year's Day",
    "Martin Luther King Jr. Day", 
    "Presidents Day",
    "Good Friday",
    "Memorial Day",
    "Independence Day",
    "Labor Day",
    "Thanksgiving Day",
    "Christmas Day"
]

# Options expiration
MONTHLY_EXPIRY_WEEK = 3  # Third week
WEEKLY_EXPIRY_DAY = 4  # Friday (0=Monday)

# =============================================================================
# CRITICAL CONSTANTS - STRATEGY FRAMEWORK REQUIREMENTS
# =============================================================================
# Daily trading limits - CRITICAL FOR STRATEGY FRAMEWORK
MAX_DAILY_TRADES = 5  # Maximum trades per day

# Portfolio risk management - NEEDED BY BASESTRATEGY  
MAX_PORTFOLIO_RISK = 0.06  # 6% maximum portfolio risk

# Profit/Loss targets - NEEDED BY STRATEGIES
STOP_LOSS_PERCENTAGE = 0.02  # 2% stop loss percentage
TAKE_PROFIT_PERCENTAGE = 0.15  # 15% take profit target

# Session management - CRITICAL FOR IMPORTS
SESSION_TIMEOUT = 3600  # 1 hour session timeout

# =============================================================================
# STRATEGY CONSTANTS - RESEARCH DRIVEN
# =============================================================================
# Day of Week Position Sizing (from research)
DAY_OF_WEEK_REDUCTION = 0.5  # 50% reduction for non-Monday

# Entry Time Windows (from research)
OPTIMAL_ENTRY_START = "10:15:00"  # Optimal entry start time
OPTIMAL_ENTRY_END = "11:40:00"    # Optimal entry end time
OPTIMAL_ENTRY_START_MINUTE = 15
OPTIMAL_ENTRY_END_MINUTE = 40
TIME_BASED_EXIT_MINUTE = 0

# Profit Targets (Updated based on research)
IRON_CONDOR_PROFIT_TARGET = 0.50    # 50% of credit
IRON_BUTTERFLY_PROFIT_TARGET = 0.15  # 15% of max profit
CREDIT_SPREAD_PROFIT_TARGET = 0.50   # 50% of credit
CREDIT_SPREAD_STOP_LOSS = 2.00       # 200% of credit (max loss 2x received premium)
IRON_CONDOR_STOP_LOSS = 1.25        # 125% of credit
IRON_BUTTERFLY_STOP_LOSS = 0.25     # 25% of max profit

# Entry Filters (from research)
MIN_IVP_THRESHOLD = 50              # Minimum IV percentile at 9:35 AM
MAX_OVERNIGHT_GAP = 0.003           # 0.3% maximum overnight gap
RSI_MIN = 30                        # Minimum RSI for entry
RSI_MAX = 70                        # Maximum RSI for entry
PRICE_TO_MA_TOLERANCE = 0.005       # 0.5% distance from 10-day MA
VIX_MIN = 15                        # Minimum VIX level
VIX_MAX = 30                        # Maximum VIX level

# Zero DTE Constants
ZERO_DTE_POSITION_REDUCTION = 0.7   # 30% size reduction
ZERO_DTE_PROFIT_TARGET = 0.10       # 10% quick profit
ZERO_DTE_MAX_TRADES = 3             # Maximum 0DTE trades per day
ZERO_DTE_TIME_DECAY_MULTIPLIER = 2.0 # Accelerated theta

# Strategy Selection
VOLATILITY_REGIME_THRESHOLDS = {
    'low': 15,
    'normal': 20,
    'high': 30,
    'extreme': 40
}

# Performance Thresholds
MIN_DAILY_TRADES_MONDAY = 1
MAX_DAILY_TRADES_MONDAY = 5
MIN_DAILY_TRADES_OTHER = 0
MAX_DAILY_TRADES_OTHER = 3

# =============================================================================
# STRATEGY NAMES
# =============================================================================
STRATEGY_IRON_CONDOR = "IronCondor"
STRATEGY_IRON_BUTTERFLY = "IronButterfly"
STRATEGY_BULL_PUT_SPREAD = "BullPutSpread"
STRATEGY_BEAR_CALL_SPREAD = "BearCallSpread"
STRATEGY_ZERO_DTE = "ZeroDTE"
STRATEGY_CALENDAR_SPREAD = "CalendarSpread"
STRATEGY_DIAGONAL_SPREAD = "DiagonalSpread"

# =============================================================================
# RISK MANAGEMENT CONSTANTS
# =============================================================================
# Risk limits (as decimal)
MAX_DAILY_LOSS_PERCENT = 0.03      # 3%
MAX_POSITION_SIZE_PERCENT = 0.02   # 2% per position
MAX_PORTFOLIO_HEAT = 0.06          # 6% total risk
MAX_LEVERAGE = 2.0                 # 2x leverage maximum

# Day-specific risk limits
MAX_PORTFOLIO_HEAT_MONDAY = 0.10   # 10% max portfolio risk on Monday
MAX_PORTFOLIO_HEAT_OTHER = 0.05    # 5% max portfolio risk other days

# Stop loss and profit targets
DEFAULT_STOP_LOSS = 0.02           # 2% default stop loss
DEFAULT_TAKE_PROFIT = 0.15         # 15% default take profit
MAX_LOSS_PER_TRADE = 0.005         # 0.5% max loss per trade
POSITION_SIZE_RISK_MULTIPLIER = 2.0 # Position sizing based on risk

# Greeks limits
MAX_DELTA_EXPOSURE = 100           # Max delta exposure
MAX_GAMMA_EXPOSURE = 50            # Max gamma exposure
MAX_VEGA_EXPOSURE = 1000          # Max vega exposure
MAX_THETA_DECAY = -50             # Max theta decay per day

# =============================================================================
# API CONFIGURATION CONSTANTS
# =============================================================================
# Connection settings
IB_GATEWAY_HOST = "127.0.0.1"
IB_GATEWAY_PORT = 4002
PAPER_TRADING_PORT = 7497
CLIENT_ID_MASTER = 2               # Master coordination client
CLIENT_ID_ORDER = 1                # Order execution client
CONNECTION_TIMEOUT = 30            # seconds

# Retry settings
MAX_CONNECTION_RETRIES = 5
RETRY_DELAY_SECONDS = 5
RECONNECT_DELAY_SECONDS = 10

# Data request limits
MAX_DATA_REQUESTS_PER_SECOND = 50
MAX_HISTORICAL_DATA_POINTS = 20000
DATA_REQUEST_TIMEOUT = 30          # seconds

# Order management
MAX_ORDER_ATTEMPTS = 3
ORDER_FILL_TIMEOUT = 60           # seconds
CANCEL_ORDER_TIMEOUT = 30         # seconds

# =============================================================================
# PERFORMANCE CONSTANTS
# =============================================================================
# Latency monitoring
LATENCY_SAMPLE_SIZE = 100           # Number of samples for latency calculation
CONNECTIVITY_CHECK_INTERVAL = 30   # Network connectivity check interval in seconds
MAX_LATENCY_MS = 1000              # Maximum acceptable latency in milliseconds
LATENCY_WARNING_MS = 500           # Warning threshold for latency
LATENCY_CRITICAL_MS = 2000         # Critical latency threshold

# Performance benchmarks (milliseconds) - CRITICAL FOR EXISTING CODE
MAX_ORDER_LATENCY = 100             # Maximum order latency
MAX_DATA_LATENCY = 50               # Maximum data latency
MAX_CALCULATION_TIME = 1000         # Maximum calculation time

# Machine Learning performance - NEEDED BY SpyderL_ML modules
MAX_PREDICTION_LATENCY_MS = 10      # Maximum ML prediction latency
FEATURE_CACHE_SIZE = 1000           # ML feature cache size
PREDICTION_BATCH_SIZE = 10          # ML prediction batch size

# Performance monitoring
PERFORMANCE_SAMPLE_WINDOW = 300    # 5 minutes in seconds
METRICS_UPDATE_INTERVAL = 30       # Update metrics every 30 seconds
HEALTH_CHECK_INTERVAL = 60         # Health check every minute

# =============================================================================
# OPTIONS STRATEGY CONSTANTS
# =============================================================================
# Iron Condor specific - NEEDED BY EXISTING STRATEGIES
IRON_CONDOR_MIN_WIDTH = 2.5        # Minimum spread width
IRON_CONDOR_MAX_WIDTH = 10.0       # Maximum spread width
IRON_CONDOR_MIN_PREMIUM = 0.25     # Minimum premium to collect
MIN_IV_RANK_THRESHOLD = 30         # Minimum IV rank for entry

# Strike selection
MIN_STRIKE_DISTANCE = 5.0          # Minimum distance from current price
MAX_STRIKE_DISTANCE = 50.0         # Maximum distance from current price
STRIKE_INTERVAL = 1.0              # Strike price intervals

# Time to expiration
MIN_DTE_FOR_ENTRY = 0              # Minimum days to expiration
MAX_DTE_FOR_ENTRY = 45             # Maximum days to expiration
OPTIMAL_DTE_RANGE = (21, 35)       # Optimal DTE range

# Greeks thresholds
DELTA_THRESHOLD = 0.01
GAMMA_THRESHOLD = 0.001
THETA_THRESHOLD = 0.01
VEGA_THRESHOLD = 0.01
RHO_THRESHOLD = 0.001

# =============================================================================
# MARKET REGIME CONSTANTS
# =============================================================================
# Volatility regimes
LOW_VOLATILITY_THRESHOLD = 0.10    # 10% annualized
HIGH_VOLATILITY_THRESHOLD = 0.30   # 30% annualized

# Trend definitions
TREND_THRESHOLD = 0.02             # 2% for trend identification
SIDEWAYS_THRESHOLD = 0.005         # 0.5% for ranging market

# Implied volatility
IV_RANK_LOW = 25                   # percentile
IV_RANK_HIGH = 75                  # percentile
IV_SKEW_THRESHOLD = 0.05           # 5% skew

# =============================================================================
# SYSTEM PERFORMANCE CONSTANTS
# =============================================================================
# Memory management
MAX_MEMORY_USAGE_MB = 2048
MEMORY_WARNING_THRESHOLD_MB = 1536
GARBAGE_COLLECTION_INTERVAL = 300  # seconds

# CPU management
MAX_CPU_USAGE_PERCENT = 80
CPU_WARNING_THRESHOLD_PERCENT = 60

# Disk management
MIN_FREE_DISK_SPACE_GB = 5
DISK_WARNING_THRESHOLD_GB = 10

# Threading
MAX_WORKER_THREADS = 10
THREAD_POOL_SIZE = 5
QUEUE_MAX_SIZE = 10000

# Processing
BATCH_PROCESSING_SIZE = 100
ASYNC_TIMEOUT = 60  # seconds

# =============================================================================
# NETWORK CONSTANTS
# =============================================================================
# Network connectivity
PING_TIMEOUT = 5                   # Ping timeout in seconds
HTTP_TIMEOUT = 10                  # HTTP request timeout
READ_TIMEOUT = 10                  # seconds
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = [1, 2, 4, 8, 16]  # exponential backoff

# Heartbeat
HEARTBEAT_INTERVAL = 30            # seconds
HEARTBEAT_TIMEOUT = 60             # seconds

# =============================================================================
# DATABASE CONSTANTS
# =============================================================================
# Connection settings
DATABASE_URL = "sqlite:///spyder.db"
MAX_DATABASE_SIZE = 1024 * 1024 * 1024  # 1GB
DATABASE_BACKUP_INTERVAL = 86400   # Daily
DATABASE_POOL_SIZE = 10
DATABASE_MAX_OVERFLOW = 20
DATABASE_TIMEOUT = 30              # seconds
DATABASE_RETRY_COUNT = 3

# Data retention
TRADE_RETENTION_DAYS = 730         # 2 years
TICK_DATA_RETENTION_DAYS = 30
LOG_RETENTION_DAYS = 90
REPORT_RETENTION_DAYS = 365

# Batch sizes
DATABASE_BATCH_SIZE = 1000
ARCHIVE_BATCH_SIZE = 10000

# =============================================================================
# LOGGING CONSTANTS
# =============================================================================
# Log levels
DEFAULT_LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log rotation
MAX_LOG_SIZE_MB = 100
MAX_LOG_FILES = 10
LOG_ROTATION_INTERVAL = "midnight"

# Performance logging
PERFORMANCE_LOG_INTERVAL = 60      # seconds
METRICS_BUFFER_SIZE = 1000

# =============================================================================
# FILE SYSTEM CONSTANTS
# =============================================================================
# Directory structure
BASE_DIR = "~/.spyder"
DATA_DIR = "data"
LOGS_DIR = "logs"
REPORTS_DIR = "reports"
MODELS_DIR = "models"
BACKUPS_DIR = "backups"
TEMP_DIR = "temp"

# File extensions
DATA_FILE_EXTENSION = ".parquet"
LOG_FILE_EXTENSION = ".log"
REPORT_FILE_EXTENSION = ".pdf"
MODEL_FILE_EXTENSION = ".pkl"

# =============================================================================
# MACHINE LEARNING CONSTANTS
# =============================================================================
# Model parameters
ML_LOOKBACK_PERIOD = 20
ML_PREDICTION_HORIZON = 5
ML_MIN_TRAINING_SAMPLES = 1000
ML_VALIDATION_SPLIT = 0.2
ML_TEST_SPLIT = 0.1

# Feature engineering
ML_MAX_FEATURES = 50
ML_FEATURE_IMPORTANCE_THRESHOLD = 0.01

# Model update frequency
ML_MODEL_UPDATE_FREQUENCY = 7      # days
ML_ONLINE_LEARNING_BATCH = 100

# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================
# Price validation
MIN_PRICE = 0.01
MAX_PRICE = 10000.0
MAX_PRICE_CHANGE_PERCENT = 0.20    # 20% max change

# Volume validation
MIN_VOLUME = 0
MAX_VOLUME = 1000000000

# Order validation
MIN_ORDER_SIZE = 1
MAX_ORDER_SIZE = 10000
MAX_ORDER_VALUE = 1000000.0

# =============================================================================
# BACKTESTING CONSTANTS
# =============================================================================
# Monte Carlo simulation
MONTE_CARLO_ITERATIONS = 1000
CONFIDENCE_INTERVALS = [0.95, 0.99]

# Walk-forward analysis
WALK_FORWARD_PERIODS = 12
IN_SAMPLE_RATIO = 0.70             # 70% in-sample

# Optimization
MAX_OPTIMIZATION_ITERATIONS = 1000
OPTIMIZATION_TOLERANCE = 0.0001

# =============================================================================
# ERROR HANDLING CONSTANTS
# =============================================================================
# Error thresholds
MAX_CONSECUTIVE_ERRORS = 5
ERROR_RATE_WINDOW = 300            # 5 minutes
MAX_ERROR_RATE = 10                # errors per window

# Retry settings
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 1            # seconds
MAX_RETRY_DELAY = 60               # seconds

# =============================================================================
# SECURITY CONSTANTS
# =============================================================================
# Session management
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = 900             # 15 minutes

# Encryption
ENCRYPTION_ALGORITHM = "AES-256"
KEY_DERIVATION_ITERATIONS = 100000

# =============================================================================
# NOTIFICATION CONSTANTS
# =============================================================================
# Alert levels
ALERT_LEVEL_DEBUG = 0
ALERT_LEVEL_INFO = 1
ALERT_LEVEL_WARNING = 2
ALERT_LEVEL_ERROR = 3
ALERT_LEVEL_CRITICAL = 4

# Rate limiting
MAX_ALERTS_PER_MINUTE = 10
MAX_SMS_PER_HOUR = 20
MAX_EMAILS_PER_HOUR = 50

# Notification delays
ALERT_COOLDOWN_SECONDS = 300       # 5 minutes
CRITICAL_ALERT_RETRY_COUNT = 3
ALERT_RETENTION_DAYS = 30

# =============================================================================
# FEATURE FLAGS
# =============================================================================
DEFAULT_FEATURE_FLAGS = {
    'enable_iron_condor': True,
    'enable_iron_butterfly': True,
    'enable_credit_spreads': True,
    'enable_zero_dte': True,
    'enable_calendar_spreads': False,
    'enable_diagonal_spreads': False,
    'enable_backtesting': True,
    'enable_paper_trading': True,
    'enable_live_trading': False,
    'enable_advanced_greeks': True,
    'enable_volatility_analysis': True,
    'enable_machine_learning': False,
    'enable_options_flow_analysis': False,
    'enable_dark_pool_analysis': False,
    'enable_sentiment_analysis': False,
    'day_of_week_sizing': True,
    'optimal_entry_window': True,
    'time_based_exit': True,
    'enhanced_entry_filters': True,
    'volatility_regime_filter': False,
}

# =============================================================================
# STRATEGY PERFORMANCE THRESHOLDS
# =============================================================================
# Minimum performance metrics
MIN_WIN_RATE = 0.40                # 40%
MIN_PROFIT_FACTOR = 1.2
MIN_SHARPE_RATIO = 0.5
MAX_DRAWDOWN = 0.20                # 20%

# Strategy evaluation period
MIN_EVALUATION_TRADES = 50
MIN_EVALUATION_DAYS = 30

# Performance ratios
SHARPE_RATIO_THRESHOLD = 1.0
SORTINO_RATIO_THRESHOLD = 1.5

# =============================================================================
# ENUMS - CRITICAL FOR STRATEGY FRAMEWORK
# =============================================================================
class SignalType(Enum):
    """Trading signal types"""
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"
    HOLD = "hold"
    ADJUST = "adjust"

class OptionType(Enum):
    """Option contract types"""
    CALL = "call"
    PUT = "put"

class PositionSide(Enum):
    """Position side indicators"""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"

# =============================================================================
# MISCELLANEOUS CONSTANTS
# =============================================================================
# Decimal precision
PRICE_DECIMAL_PLACES = 2
PERCENTAGE_DECIMAL_PLACES = 4
CURRENCY_DECIMAL_PLACES = 2

# Time zones
DEFAULT_TIMEZONE = "America/New_York"
DATA_TIMEZONE = "UTC"

# Currency
BASE_CURRENCY = "USD"
SUPPORTED_CURRENCIES = ["USD"]

# Event system
EVENT_QUEUE_SIZE = 10000
EVENT_BATCH_SIZE = 100
EVENT_PROCESSING_INTERVAL = 0.01   # 10ms

# Trading session
TRADING_SESSION_TIMEOUT = 300      # 5 minutes
SESSION_HEARTBEAT_INTERVAL = 30    # seconds

# Version control
API_VERSION = "v2"
PROTOCOL_VERSION = "2.0"
DATA_FORMAT_VERSION = "2.0"

# Debug settings
DEBUG_MODE = False
DEVELOPMENT_MODE = False
TESTING_MODE = False
SIMULATION_SPEED = 1.0             # 1.0 = real-time
PAPER_TRADING_MODE = True

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================
def validate_constants():
    """Validate that all constants are properly defined and within expected ranges."""
    
    # Validate percentage values are between 0 and 1
    percentage_constants = [
        ('MAX_DAILY_LOSS_PERCENT', MAX_DAILY_LOSS_PERCENT),
        ('MAX_POSITION_SIZE_PERCENT', MAX_POSITION_SIZE_PERCENT),
        ('MAX_PORTFOLIO_HEAT', MAX_PORTFOLIO_HEAT),
        ('STOP_LOSS_PERCENTAGE', STOP_LOSS_PERCENTAGE),
        ('TAKE_PROFIT_PERCENTAGE', TAKE_PROFIT_PERCENTAGE),
    ]
    
    for name, value in percentage_constants:
        if not (0 <= value <= 1):
            raise ValueError(f"{name} must be between 0 and 1, got {value}")
    
    # Validate positive integer constants
    positive_int_constants = [
        ('MAX_DAILY_TRADES', MAX_DAILY_TRADES),
        ('MAX_POSITIONS', MAX_POSITIONS),
        ('MAX_POSITION_SIZE', MAX_POSITION_SIZE),
        ('SPY_CONTRACT_MULTIPLIER', SPY_CONTRACT_MULTIPLIER),
        ('SESSION_TIMEOUT', SESSION_TIMEOUT),
    ]
    
    for name, value in positive_int_constants:
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer, got {value}")
    
    # Validate time strings are properly formatted
    time_constants = [
        ('MARKET_OPEN_TIME', MARKET_OPEN_TIME),
        ('MARKET_CLOSE_TIME', MARKET_CLOSE_TIME),
        ('OPTIMAL_ENTRY_START', OPTIMAL_ENTRY_START),
        ('OPTIMAL_ENTRY_END', OPTIMAL_ENTRY_END),
    ]
    
    for name, value in time_constants:
        try:
            datetime.strptime(value, '%H:%M:%S')
        except ValueError:
            raise ValueError(f"{name} must be in HH:MM:SS format, got {value}")
    
    # Validate logic relationships
    if MAX_DAILY_TRADES < 1:
        raise ValueError("MAX_DAILY_TRADES must be at least 1")
    
    if STOP_LOSS_PERCENTAGE >= TAKE_PROFIT_PERCENTAGE:
        raise ValueError("STOP_LOSS_PERCENTAGE must be less than TAKE_PROFIT_PERCENTAGE")
    
    return True

# =============================================================================
# MODULE EXPORTS
# =============================================================================
__all__ = [
    # System info
    "SYSTEM_NAME", "SYSTEM_VERSION", "SYSTEM_DESCRIPTION",
    
    # Trading constants
    "PRIMARY_SYMBOL", "OPTION_MULTIPLIER", "SPY_CONTRACT_MULTIPLIER", 
    "SPX_CONTRACT_MULTIPLIER", "OPTIONS_TICK_SIZE", "MAX_POSITIONS", "MAX_POSITION_SIZE",
    
    # CRITICAL CONSTANTS - STRATEGY FRAMEWORK REQUIREMENTS
    "MAX_DAILY_TRADES", "MAX_PORTFOLIO_RISK", "STOP_LOSS_PERCENTAGE", "TAKE_PROFIT_PERCENTAGE",
    "SESSION_TIMEOUT",
    
    # Calendar constants
    "TRADING_DAYS_PER_YEAR", "TRADING_DAYS_PER_MONTH", "TRADING_HOURS_PER_DAY",
    
    # Market hours
    "MARKET_OPEN_TIME", "MARKET_CLOSE_TIME", "PRE_MARKET_OPEN", "AFTER_HOURS_CLOSE",
    
    # Strategy constants
    "IRON_CONDOR_PROFIT_TARGET", "IRON_BUTTERFLY_PROFIT_TARGET", "CREDIT_SPREAD_PROFIT_TARGET",
    "CREDIT_SPREAD_STOP_LOSS", "IRON_CONDOR_STOP_LOSS", "IRON_BUTTERFLY_STOP_LOSS", "MIN_IVP_THRESHOLD",
    "OPTIMAL_ENTRY_START", "OPTIMAL_ENTRY_END", "RSI_MIN", "RSI_MAX", "VIX_MIN", "VIX_MAX",
    
    # Iron Condor parameters - NEEDED BY EXISTING STRATEGIES
    "IRON_CONDOR_MAX_WIDTH", "IRON_CONDOR_MIN_PREMIUM",
    
    # Zero DTE
    "ZERO_DTE_POSITION_REDUCTION", "ZERO_DTE_PROFIT_TARGET", "ZERO_DTE_MAX_TRADES",
    
    # Daily trading limits
    "MIN_DAILY_TRADES_MONDAY", "MAX_DAILY_TRADES_MONDAY", "MIN_DAILY_TRADES_OTHER", "MAX_DAILY_TRADES_OTHER",
    
    # Risk management
    "MAX_DAILY_LOSS_PERCENT", "MAX_POSITION_SIZE_PERCENT", "MAX_PORTFOLIO_HEAT",
    "MAX_PORTFOLIO_HEAT_MONDAY", "MAX_PORTFOLIO_HEAT_OTHER", "DEFAULT_STOP_LOSS", "DEFAULT_TAKE_PROFIT",
    
    # API configuration
    "IB_GATEWAY_HOST", "IB_GATEWAY_PORT", "PAPER_TRADING_PORT", "CLIENT_ID_MASTER", "CLIENT_ID_ORDER",
    "CONNECTION_TIMEOUT", "MAX_CONNECTION_RETRIES",
    
    # Performance constants
    "LATENCY_SAMPLE_SIZE", "MAX_ORDER_LATENCY", "MAX_DATA_LATENCY", "MAX_CALCULATION_TIME",
    "MAX_PREDICTION_LATENCY_MS", "FEATURE_CACHE_SIZE", "PREDICTION_BATCH_SIZE",
    
    # Options specific
    "MIN_STRIKE_DISTANCE", "MAX_STRIKE_DISTANCE", "STRIKE_INTERVAL", "MIN_DTE_FOR_ENTRY", 
    "MAX_DTE_FOR_ENTRY", "OPTIMAL_DTE_RANGE",
    
    # Greeks
    "DELTA_THRESHOLD", "GAMMA_THRESHOLD", "THETA_THRESHOLD", "VEGA_THRESHOLD", "RHO_THRESHOLD",
    "MAX_DELTA_EXPOSURE", "MAX_GAMMA_EXPOSURE", "MAX_VEGA_EXPOSURE",
    
    # Market regime
    "LOW_VOLATILITY_THRESHOLD", "HIGH_VOLATILITY_THRESHOLD", "TREND_THRESHOLD", "SIDEWAYS_THRESHOLD",
    "IV_RANK_LOW", "IV_RANK_HIGH", "IV_SKEW_THRESHOLD",
    
    # Performance thresholds
    "MIN_WIN_RATE", "MIN_PROFIT_FACTOR", "MIN_SHARPE_RATIO", "MAX_DRAWDOWN",
    "MIN_EVALUATION_TRADES", "MIN_EVALUATION_DAYS",
    
    # Enums - CRITICAL FOR STRATEGIES
    "SignalType", "OptionType", "PositionSide",
    
    # Strategy names
    "STRATEGY_IRON_CONDOR", "STRATEGY_IRON_BUTTERFLY", "STRATEGY_BULL_PUT_SPREAD",
    "STRATEGY_BEAR_CALL_SPREAD", "STRATEGY_ZERO_DTE", "STRATEGY_CALENDAR_SPREAD", "STRATEGY_DIAGONAL_SPREAD",
    
    # Feature flags
    "DEFAULT_FEATURE_FLAGS",
    
    # System performance
    "MAX_MEMORY_USAGE_MB", "MAX_CPU_USAGE_PERCENT", "MAX_WORKER_THREADS",
    
    # Database
    "DATABASE_URL", "DATABASE_BATCH_SIZE", "TRADE_RETENTION_DAYS",
    
    # Logging
    "DEFAULT_LOG_LEVEL", "LOG_FORMAT", "MAX_LOG_SIZE_MB",
    
    # Validation
    "validate_constants",
]

# =============================================================================
# MODULE INITIALIZATION
# =============================================================================
# Run validation when module is imported
if __name__ == "__main__":
    validate_constants()
    
    print(f"\n{SYSTEM_NAME} Constants Module v{SYSTEM_VERSION}")
    print("=" * 60)
    print(f"Constants loaded successfully: {len(__all__)} exports available")
    print(f"System: {SYSTEM_DESCRIPTION}")
    
    print("\nCritical Constants Defined:")
    print(f"  MAX_DAILY_TRADES: {MAX_DAILY_TRADES}")
    print(f"  MAX_PORTFOLIO_RISK: {MAX_PORTFOLIO_RISK:.1%}")
    print(f"  STOP_LOSS_PERCENTAGE: {STOP_LOSS_PERCENTAGE:.1%}")
    print(f"  TAKE_PROFIT_PERCENTAGE: {TAKE_PROFIT_PERCENTAGE:.1%}")
    print(f"  SESSION_TIMEOUT: {SESSION_TIMEOUT}s")
    
    print("\nStrategy Framework Ready!")

# Run validation automatically on import
try:
    validate_constants()
except Exception as e:
    print(f"Constants validation failed: {e}")
    raise

class TimeFrame(Enum):
    """Trading timeframe enumeration"""
    TICK = "tick"
    SECOND_1 = "1s"
    SECOND_5 = "5s" 
    SECOND_15 = "15s"
    SECOND_30 = "30s"
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"
    UNKNOWN = "unknown"
    
    def to_seconds(self) -> int:
        """Convert timeframe to seconds"""
        mapping = {
            TimeFrame.TICK: 0,
            TimeFrame.SECOND_1: 1,
            TimeFrame.SECOND_5: 5,
            TimeFrame.SECOND_15: 15,
            TimeFrame.SECOND_30: 30,
            TimeFrame.MINUTE_1: 60,
            TimeFrame.MINUTE_5: 300,
            TimeFrame.MINUTE_15: 900,
            TimeFrame.MINUTE_30: 1800,
            TimeFrame.HOUR_1: 3600,
            TimeFrame.HOUR_4: 14400,
            TimeFrame.DAY_1: 86400,
            TimeFrame.WEEK_1: 604800,
            TimeFrame.MONTH_1: 2592000,  # Approximate
        }
        return mapping.get(self, 0)
