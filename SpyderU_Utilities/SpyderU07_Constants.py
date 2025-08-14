#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System
Module: SpyderU07_Constants.py
Group: U (Utilities)
Purpose: System-wide constants and configuration values with research findings

Description:
This module defines all system-wide constants used throughout the Spyder trading
platform. It includes trading parameters, system limits, API configuration values,
risk parameters, and research-driven constants for optimal trading performance.

Author: Mohamed Talib
Created: 2025-06-06
Version: 1.4
"""

# =============================================================================
# System Information
# =============================================================================
from enum import Enum

SYSTEM_NAME = "SPYDER"
SYSTEM_VERSION = "2.0.0"
SYSTEM_DESCRIPTION = "Automated SPY Options Trading System with Research Enhancements"

# =============================================================================
# Trading Constants
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
# Market Hours (Eastern Time)
# =============================================================================
MARKET_OPEN_TIME = "09:30:00"
MARKET_CLOSE_TIME = "16:00:00"
PRE_MARKET_OPEN = "04:00:00"
AFTER_HOURS_CLOSE = "20:00:00"

# Early close times
EARLY_CLOSE_TIME = "13:00:00"

# Trading session durations (minutes)
REGULAR_SESSION_MINUTES = 390  # 6.5 hours
EXTENDED_SESSION_MINUTES = 960  # 16 hours

# =============================================================================
# STRATEGY CONSTANTS - RESEARCH DRIVEN (NEW)
# =============================================================================
# Day of Week Position Sizing (from research)
# MONDAY_MIN_POSITION_PCT = 0.01      # 1% minimum on Monday
# MONDAY_MAX_POSITION_PCT = 0.05      # 5% maximum on Monday
# OTHER_DAY_MIN_POSITION_PCT = 0.005  # 0.5% minimum other days
# OTHER_DAY_MAX_POSITION_PCT = 0.025  # 2.5% maximum other days
DAY_OF_WEEK_REDUCTION = 0.5  # 50% reduction for non-Monday

# Entry Time Windows (from research)
# OPTIMAL_ENTRY_START_HOUR = 10
OPTIMAL_ENTRY_START_MINUTE = 15
# OPTIMAL_ENTRY_END_HOUR = 11
OPTIMAL_ENTRY_END_MINUTE = 40
# TIME_BASED_EXIT_HOUR = 12
TIME_BASED_EXIT_MINUTE = 0

# Profit Targets (Updated based on research)
IRON_CONDOR_PROFIT_TARGET = 0.50  # 50% of credit (was 0.25-0.50)
IRON_BUTTERFLY_PROFIT_TARGET = 0.15  # 15% of max profit
CREDIT_SPREAD_PROFIT_TARGET = 0.50  # 50% of credit
IRON_CONDOR_STOP_LOSS = 1.25  # 125% of credit
IRON_BUTTERFLY_STOP_LOSS = 0.25  # 25% of max profit

# Entry Filters (from research)
MIN_IVP_THRESHOLD = 50  # Minimum IV percentile at 9:35 AM
MAX_OVERNIGHT_GAP = 0.003  # 0.3% maximum overnight gap
RSI_MIN = 30  # Minimum RSI for entry
RSI_MAX = 70  # Maximum RSI for entry
PRICE_TO_MA_TOLERANCE = 0.005  # 0.5% distance from 10-day MA
VIX_MIN = 15  # Minimum VIX level
VIX_MAX = 30  # Maximum VIX level

# Zero DTE Constants
ZERO_DTE_POSITION_REDUCTION = 0.7  # 30% size reduction
ZERO_DTE_PROFIT_TARGET = 0.10  # 10% quick profit
ZERO_DTE_MAX_TRADES = 3  # Maximum 0DTE trades per day
ZERO_DTE_TIME_DECAY_MULTIPLIER = 2.0  # Accelerated theta

# Strategy Selection
VOLATILITY_REGIME_THRESHOLDS = {"low": 15, "normal": 20, "high": 30, "extreme": 40}

# Performance Thresholds
MIN_DAILY_TRADES_MONDAY = 1
MAX_DAILY_TRADES_MONDAY = 5
MIN_DAILY_TRADES_OTHER = 0
MAX_DAILY_TRADES_OTHER = 3

# =============================================================================
# STRATEGY NAMES - INCLUDING NEW STRATEGIES
# =============================================================================
STRATEGY_IRON_CONDOR = "IronCondor"
STRATEGY_IRON_BUTTERFLY = "IronButterfly"
STRATEGY_BULL_PUT_SPREAD = "BullPutSpread"
STRATEGY_BEAR_CALL_SPREAD = "BearCallSpread"
STRATEGY_ZERO_DTE = "ZeroDTE"
STRATEGY_CALENDAR_SPREAD = "CalendarSpread"
STRATEGY_DIAGONAL_SPREAD = "DiagonalSpread"

# =============================================================================

# ==============================================================================
# LATENCY AND PERFORMANCE CONSTANTS
# ==============================================================================
# Latency monitoring
LATENCY_SAMPLE_SIZE = 100  # Number of samples for latency calculation
CONNECTIVITY_CHECK_INTERVAL = 30  # Network connectivity check interval in seconds
MAX_LATENCY_MS = 1000  # Maximum acceptable latency in milliseconds
LATENCY_WARNING_MS = 500  # Warning threshold for latency
LATENCY_CRITICAL_MS = 2000  # Critical latency threshold

# Performance monitoring
PERFORMANCE_SAMPLE_WINDOW = 300  # 5 minutes in seconds
METRICS_UPDATE_INTERVAL = 30  # Update metrics every 30 seconds
HEALTH_CHECK_INTERVAL = 60  # Health check every minute

# Risk Management Constants - UPDATED WITH RESEARCH
# =============================================================================
# Risk limits (as decimal)
MAX_DAILY_LOSS_PERCENT = 0.03  # 3%
MAX_POSITION_SIZE_PERCENT = 0.02  # 2% per position
MAX_PORTFOLIO_HEAT = 0.06  # 6% total risk
MAX_LEVERAGE = 2.0  # 2x leverage maximum

# Day-specific risk limits (NEW)
MAX_PORTFOLIO_HEAT_MONDAY = 0.10  # 10% max portfolio risk on Monday
MAX_PORTFOLIO_HEAT_OTHER = 0.05  # 5% max portfolio risk other days

# Stop loss and profit targets
DEFAULT_STOP_LOSS = 0.02  # 2%
DEFAULT_PROFIT_TARGET = 0.04  # 4%
TRAILING_STOP_PERCENT = 0.01  # 1%

# Risk-free rate
RISK_FREE_RATE = 0.05  # 5% annual

# Circuit breakers
CIRCUIT_BREAKER_THRESHOLD = 0.05  # 5% drawdown
CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minutes

# =============================================================================
# Strategy-Specific Constants
# =============================================================================
# Iron Condor
IRON_CONDOR_DEFAULT_WIDTH = 5.0  # Strike width
IRON_CONDOR_DEFAULT_DELTA = 0.15  # Target delta
IRON_CONDOR_MAX_LOSS_MULTIPLIER = 3.0  # Max loss as multiple of credit
# IRON_CONDOR_PROFIT_TARGET = 0.5   # Already defined above
# IRON_CONDOR_STOP_LOSS = 2.0      # Already defined above

# Credit Spreads
CREDIT_SPREAD_DEFAULT_WIDTH = 5.0
CREDIT_SPREAD_DEFAULT_DELTA = 0.20
CREDIT_SPREAD_MIN_CREDIT = 0.30  # Minimum credit as % of width

# Zero DTE
ZERO_DTE_MAX_POSITIONS = 2
ZERO_DTE_ENTRY_TIME = "09:45:00"
ZERO_DTE_EXIT_TIME = "15:30:00"

# =============================================================================
# Technical Indicators
# =============================================================================
# Default periods
DEFAULT_PERIOD = 20
DEFAULT_SMA_PERIOD = 20
DEFAULT_EMA_PERIOD = 12
DEFAULT_RSI_PERIOD = 14
DEFAULT_MACD_FAST = 12
DEFAULT_MACD_SLOW = 26
DEFAULT_MACD_SIGNAL = 9
DEFAULT_BB_PERIOD = 20
DEFAULT_BB_STD = 2.0
DEFAULT_ATR_PERIOD = 14

# Indicator thresholds
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
STOCH_OVERSOLD = 20
STOCH_OVERBOUGHT = 80

# =============================================================================
# Data Feed Constants
# =============================================================================
# Data intervals
DATA_INTERVAL_1MIN = "1min"
DATA_INTERVAL_5MIN = "5min"
DATA_INTERVAL_15MIN = "15min"
DATA_INTERVAL_1HOUR = "1H"
DATA_INTERVAL_DAILY = "1D"

# Data limits
MAX_HISTORICAL_DAYS = 365
MAX_INTRADAY_DAYS = 60
MIN_DATA_POINTS = 100
DATA_CACHE_SIZE = 10000

# Market data
MARKET_DATA_TIMEOUT = 5  # seconds
MAX_CONCURRENT_SUBSCRIPTIONS = 100
SNAPSHOT_INTERVAL = 1  # seconds

# =============================================================================
# Backtesting Constants - WITH RESEARCH ENHANCEMENTS
# =============================================================================
BACKTEST_INITIAL_CAPITAL = 100000.0
BACKTEST_COMMISSION_RATE = 0.65  # per contract
BACKTEST_SLIPPAGE_RATE = 0.01  # $0.01 per contract
BACKTEST_MARGIN_REQUIREMENT = 0.20  # 20%

# New backtest flags
BACKTEST_DAY_OF_WEEK_ANALYSIS = True
BACKTEST_ENTRY_TIME_ANALYSIS = True
BACKTEST_PROFIT_TARGET_OPTIMIZATION = True

# Performance metrics
MIN_TRADES_FOR_STATS = 30
CONFIDENCE_INTERVAL = 0.95
SHARPE_RATIO_THRESHOLD = 1.0
SORTINO_RATIO_THRESHOLD = 1.5

# =============================================================================
# Database Constants
# =============================================================================
# Connection settings
DATABASE_POOL_SIZE = 10
DATABASE_MAX_OVERFLOW = 20
DATABASE_TIMEOUT = 30  # seconds
DATABASE_RETRY_COUNT = 3

# Data retention
TRADE_RETENTION_DAYS = 730  # 2 years
TICK_DATA_RETENTION_DAYS = 30
LOG_RETENTION_DAYS = 90
REPORT_RETENTION_DAYS = 365

# Batch sizes
DATABASE_BATCH_SIZE = 1000
ARCHIVE_BATCH_SIZE = 10000

# =============================================================================
# API Constants
# =============================================================================
# Interactive Brokers
IB_DEFAULT_HOST = "127.0.0.1"
IB_DEFAULT_PORT = 4002  # Paper trading port  # TWS Paper Trading
IB_LIVE_PORT = 7496  # TWS Live Trading
IB_GATEWAY_PORT = 4002  # IB Gateway
IB_CLIENT_ID = 1

# API limits
API_RATE_LIMIT = 50  # requests per second
API_TIMEOUT = 30  # seconds
API_MAX_RETRIES = 3

# Request IDs
MARKET_DATA_BASE_ID = 1000
HISTORICAL_DATA_BASE_ID = 2000
ORDER_BASE_ID = 3000
ACCOUNT_BASE_ID = 4000

# =============================================================================
# Machine Learning Constants
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
ML_MODEL_UPDATE_FREQUENCY = 7  # days
ML_ONLINE_LEARNING_BATCH = 100

# =============================================================================
# Notification Constants
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
ALERT_COOLDOWN_SECONDS = 300  # 5 minutes
CRITICAL_ALERT_RETRY_COUNT = 3
ALERT_RETENTION_DAYS = 30

# =============================================================================
# Logging Constants
# =============================================================================
# Log levels
LOG_LEVEL_TRACE = 5
LOG_LEVEL_DEBUG = 10
LOG_LEVEL_INFO = 20
LOG_LEVEL_WARNING = 30
LOG_LEVEL_ERROR = 40
LOG_LEVEL_CRITICAL = 50

# Log file settings
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT = 10
LOG_ROTATION_INTERVAL = 24  # hours

# Performance logging
PERFORMANCE_LOG_INTERVAL = 60  # seconds
METRICS_BUFFER_SIZE = 1000

# =============================================================================
# FEATURE FLAGS - DEFAULT STATES (NEW)
# =============================================================================
DEFAULT_FEATURE_FLAGS = {
    "day_of_week_sizing": True,
    "optimal_entry_window": True,
    "time_based_exit": True,
    "enhanced_entry_filters": True,
    "iron_butterfly_strategy": False,  # Start disabled
    "directional_spreads": False,  # Start disabled
    "zero_dte_trading": False,  # Start disabled
    "volatility_regime_filter": False,  # Start disabled
}

# =============================================================================
# ANALYTICS CONSTANTS (NEW)
# =============================================================================
PERFORMANCE_METRICS_BY_DAY = [
    "total_trades",
    "win_rate",
    "average_profit",
    "max_drawdown",
    "sharpe_ratio",
]

ENTRY_TIME_BUCKETS = [
    (9, 30, "09:30-10:00"),
    (10, 0, "10:00-10:15"),
    (10, 15, "10:15-10:30"),  # Optimal start
    (10, 30, "10:30-11:00"),  # Optimal
    (11, 0, "11:00-11:30"),  # Optimal
    (11, 30, "11:30-12:00"),  # Optimal end at 11:40
    (12, 0, "12:00-13:00"),
    (13, 0, "13:00-14:00"),
    (14, 0, "14:00-15:00"),
    (15, 0, "15:00-16:00"),
]

# =============================================================================
# System Performance Constants
# =============================================================================
# Threading
MAX_WORKER_THREADS = 10
THREAD_POOL_SIZE = 5
QUEUE_MAX_SIZE = 10000

# Memory limits
MAX_MEMORY_USAGE_PERCENT = 80
CACHE_MEMORY_LIMIT = 1024 * 1024 * 1024  # 1 GB

# Processing
BATCH_PROCESSING_SIZE = 100
ASYNC_TIMEOUT = 60  # seconds

# =============================================================================
# Network Constants
# =============================================================================
# Connection settings

# Network connectivity constants
PING_TIMEOUT = 5  # Ping timeout in seconds
HTTP_TIMEOUT = 10  # HTTP request timeout
IB_GATEWAY_HOSTS = ["127.0.0.1", "localhost"]  # IB Gateway hosts
IB_GATEWAY_PORTS = {"paper": 4002, "live": 4001}  # IB Gateway ports
MARKET_DATA_ENDPOINTS = ["https://api.example.com/status"]  # Market data endpoints

CONNECTION_TIMEOUT = 30  # seconds
READ_TIMEOUT = 10  # seconds
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = [1, 2, 4, 8, 16]  # exponential backoff

# Heartbeat
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_TIMEOUT = 60  # seconds

# =============================================================================
# File System Constants
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
# Reporting Constants
# =============================================================================
# Report types
REPORT_DAILY = "daily"
REPORT_WEEKLY = "weekly"
REPORT_MONTHLY = "monthly"
REPORT_QUARTERLY = "quarterly"
REPORT_ANNUAL = "annual"

# Report generation
REPORT_GENERATION_TIME = "16:30:00"  # After market close
REPORT_RETENTION_DAYS = 365
MAX_REPORT_SIZE = 50 * 1024 * 1024  # 50 MB

# =============================================================================
# User Interface Constants
# =============================================================================
# Update intervals (milliseconds)
UI_FAST_UPDATE_MS = 500
UI_NORMAL_UPDATE_MS = 1000
UI_SLOW_UPDATE_MS = 5000

# Chart settings
CHART_MAX_POINTS = 5000
CHART_DEFAULT_PERIOD = 100
CHART_COLORS = {
    "background": "#1e1e1e",
    "foreground": "#ffffff",
    "positive": "#00ff00",
    "negative": "#ff0000",
    "neutral": "#808080",
}

# Dashboard layout
DASHBOARD_GRID_COLUMNS = 12
DASHBOARD_GRID_ROWS = 8
SIDEBAR_WIDTH = 300
HEADER_HEIGHT = 80

# =============================================================================
# Validation Constants
# =============================================================================
# Price validation
MIN_PRICE = 0.01
MAX_PRICE = 10000.0
MAX_PRICE_CHANGE_PERCENT = 0.20  # 20% max change

# Volume validation
MIN_VOLUME = 0
MAX_VOLUME = 1000000000

# Order validation
MIN_ORDER_SIZE = 1
MAX_ORDER_SIZE = 10000
MAX_ORDER_VALUE = 1000000.0

# =============================================================================
# Greeks Constants
# =============================================================================
# Greeks calculation
DELTA_THRESHOLD = 0.01
GAMMA_THRESHOLD = 0.001
THETA_THRESHOLD = 0.01
VEGA_THRESHOLD = 0.01
RHO_THRESHOLD = 0.001

# Greeks limits for risk
MAX_PORTFOLIO_DELTA = 100
MAX_PORTFOLIO_GAMMA = 50
MAX_PORTFOLIO_VEGA = 1000

# =============================================================================
# Error Handling Constants
# =============================================================================
# Error thresholds
MAX_CONSECUTIVE_ERRORS = 5
ERROR_RATE_WINDOW = 300  # 5 minutes
MAX_ERROR_RATE = 10  # errors per window

# Retry settings
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 60  # seconds

# =============================================================================
# Security Constants
# =============================================================================
# Session management
SESSION_TIMEOUT = 3600  # 1 hour
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = 900  # 15 minutes

# Encryption
ENCRYPTION_ALGORITHM = "AES-256"
KEY_DERIVATION_ITERATIONS = 100000

# =============================================================================
# Performance Benchmarks
# =============================================================================
# Latency thresholds (milliseconds)
MAX_ORDER_LATENCY = 100
MAX_DATA_LATENCY = 50
MAX_CALCULATION_TIME = 1000

# Throughput
MIN_ORDERS_PER_SECOND = 10
MIN_TICKS_PER_SECOND = 1000

# =============================================================================
# Strategy Performance Thresholds
# =============================================================================
# Minimum performance metrics
MIN_WIN_RATE = 0.40  # 40%
MIN_PROFIT_FACTOR = 1.2
MIN_SHARPE_RATIO = 0.5
MAX_DRAWDOWN = 0.20  # 20%

# Strategy evaluation period
MIN_EVALUATION_TRADES = 50
MIN_EVALUATION_DAYS = 30

# =============================================================================
# Market Regime Constants
# =============================================================================
# Volatility regimes
LOW_VOLATILITY_THRESHOLD = 0.10  # 10% annualized
HIGH_VOLATILITY_THRESHOLD = 0.30  # 30% annualized

# Trend definitions
TREND_THRESHOLD = 0.02  # 2% for trend identification
SIDEWAYS_THRESHOLD = 0.005  # 0.5% for ranging market

# =============================================================================
# Options Specific Constants
# =============================================================================
# Strike selection
STRIKE_INTERVAL = 1.0  # $1 for SPY
MIN_STRIKE_DISTANCE = 5.0  # $5 from current price
MAX_STRIKE_DISTANCE = 50.0  # $50 from current price

# Time decay
THETA_DECAY_ACCELERATE_DTE = 30  # Days to expiration
MIN_DTE_FOR_ENTRY = 0  # Minimum days to expiration

# Implied volatility
IV_RANK_LOW = 25  # percentile
IV_RANK_HIGH = 75  # percentile
IV_SKEW_THRESHOLD = 0.05  # 5% skew

# =============================================================================
# Backtesting Specific Constants
# =============================================================================
# Monte Carlo simulation
MONTE_CARLO_ITERATIONS = 1000
CONFIDENCE_INTERVALS = [0.95, 0.99]

# Walk-forward analysis
WALK_FORWARD_PERIODS = 12
IN_SAMPLE_RATIO = 0.70  # 70% in-sample

# Optimization
MAX_OPTIMIZATION_ITERATIONS = 1000
OPTIMIZATION_TOLERANCE = 0.0001

# =============================================================================
# Calendar Constants
# =============================================================================
# Trading calendar
TRADING_DAYS_PER_YEAR = 252
TRADING_DAYS_PER_MONTH = 21
TRADING_HOURS_PER_DAY = 6.5

# Options expiration
MONTHLY_EXPIRY_WEEK = 3  # Third week
WEEKLY_EXPIRY_DAY = 4  # Friday (0=Monday)

# =============================================================================
# External API Keys (Placeholders)
# =============================================================================
# Note: Actual keys should be stored in secure configuration
ALPHA_VANTAGE_API_KEY = "YOUR_API_KEY"
QUANDL_API_KEY = "YOUR_API_KEY"
IEX_CLOUD_API_KEY = "YOUR_API_KEY"

# =============================================================================
# Debug and Development Constants
# =============================================================================
DEBUG_MODE = False
DEVELOPMENT_MODE = False
TESTING_MODE = False

# Simulation settings
SIMULATION_SPEED = 1.0  # 1.0 = real-time
PAPER_TRADING_MODE = True

# =============================================================================
# Version Control Constants
# =============================================================================
API_VERSION = "v2"
PROTOCOL_VERSION = "2.0"
DATA_FORMAT_VERSION = "2.0"

# Compatibility
MIN_PYTHON_VERSION = (3, 9)
MIN_PANDAS_VERSION = "1.3.0"
MIN_NUMPY_VERSION = "1.21.0"

# =============================================================================
# Miscellaneous Constants
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

# =============================================================================
# Archive and Compression Constants
# =============================================================================
ARCHIVE_COMPRESSION_LEVEL = 6  # Compression level (0-9, where 9 is max compression)
ARCHIVE_CHUNK_SIZE = 1024 * 1024  # 1MB chunks for archiving
ARCHIVE_RETENTION_DAYS = 365  # Keep archives for 1 year
ARCHIVE_FILE_FORMAT = ".tar.gz"  # Archive format

# =============================================================================
# Additional Constants
# =============================================================================
# Event system
EVENT_QUEUE_SIZE = 10000
EVENT_BATCH_SIZE = 100
EVENT_PROCESSING_INTERVAL = 0.01  # 10ms

# Trading session
TRADING_SESSION_TIMEOUT = 300  # 5 minutes
SESSION_HEARTBEAT_INTERVAL = 30  # 30 seconds

# Data validation
DATA_STALENESS_THRESHOLD = 5  # seconds
MAX_DATA_AGE = 60  # seconds

# Strategy evaluation
STRATEGY_WARMUP_PERIOD = 20  # bars
STRATEGY_COOLDOWN_PERIOD = 5  # minutes after error

# Paper trading
PAPER_FILL_DELAY_MS = 100  # Simulated fill delay
PAPER_SLIPPAGE_TICKS = 1  # Simulated slippage

# System monitoring
SYSTEM_CHECK_INTERVAL = 5  # seconds
MEMORY_WARNING_THRESHOLD = 0.7  # 70% memory usage
CPU_WARNING_THRESHOLD = 0.8  # 80% CPU usage

# Market data
TICK_BUFFER_SIZE = 10000
ORDERBOOK_DEPTH = 10
MAX_TICK_AGE_SECONDS = 2

# Position management
POSITION_CHECK_INTERVAL = 1  # seconds
MAX_POSITION_AGE_HOURS = 24  # Maximum time to hold a position

# Account settings
MIN_ACCOUNT_BALANCE = 25000  # PDT requirement
MARGIN_BUFFER = 0.1  # 10% margin buffer

# Notification settings
NOTIFICATION_QUEUE_SIZE = 1000
MAX_NOTIFICATION_RETRIES = 3

# Configuration
CONFIG_RELOAD_INTERVAL = 300  # 5 minutes
CONFIG_BACKUP_COUNT = 5

# GUI Settings
GUI_THEME = "dark"
GUI_FONT_SIZE = 10
GUI_TABLE_ROW_HEIGHT = 24

# Export settings
EXPORT_DATE_FORMAT = "%Y-%m-%d"
EXPORT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
EXPORT_CSV_DELIMITER = ","

# Scheduler settings
SCHEDULER_TICK_INTERVAL = 1  # seconds
MAX_SCHEDULED_TASKS = 100

# Connection manager
CONNECTION_POOL_SIZE = 5
MAX_CONNECTION_AGE = 3600  # 1 hour

# Market internals
MARKET_BREADTH_SYMBOLS = ["ADD", "TICK", "TRIN", "VIX"]
SECTOR_ETF_SYMBOLS = ["XLF", "XLK", "XLE", "XLV", "XLI", "XLY", "XLP", "XLU", "XLRE", "XLB", "XLC"]

# =============================================================================
# TradingConstants Class (for compatibility)
# =============================================================================


class TradingConstants:
    """Constants for trading operations"""

    # Position limits
    MAX_POSITIONS = 5
    MAX_POSITION_SIZE = 10  # Maximum contracts per position
    MAX_PORTFOLIO_RISK = 0.02  # 2% max risk per trade

    # Order types
    ORDER_TYPE_MARKET = "MKT"
    ORDER_TYPE_LIMIT = "LMT"
    ORDER_TYPE_STOP = "STP"
    ORDER_TYPE_STOP_LIMIT = "STP LMT"

    # Time in force
    TIF_DAY = "DAY"
    TIF_GTC = "GTC"
    TIF_IOC = "IOC"
    TIF_FOK = "FOK"

    # Options specific
    MIN_OPTION_PRICE = 0.05  # Minimum option price to trade
    MAX_OPTION_SPREAD = 0.10  # Maximum bid-ask spread

    # Risk parameters
    DEFAULT_STOP_LOSS = 0.50  # 50% stop loss
    DEFAULT_TAKE_PROFIT = 1.00  # 100% take profit

    # Fees and commissions
    OPTION_COMMISSION = 0.65  # Per contract
    REGULATORY_FEE = 0.0388  # Per contract

    # Market hours (duplicated from TradingHours for convenience)
    MARKET_OPEN_HOUR = 9
    MARKET_OPEN_MINUTE = 30
    MARKET_CLOSE_HOUR = 16
    MARKET_CLOSE_MINUTE = 0


# =============================================================================
# SignalType Enum (for compatibility)
# =============================================================================


class SignalType(Enum):
    """Trading signal types"""

    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    EXIT_ALL = "EXIT_ALL"
    HOLD = "HOLD"
    NONE = "NONE"


# =============================================================================
# OptionType Enum
# =============================================================================
class OptionType(Enum):
    """Option type enumeration"""

    CALL = "CALL"
    PUT = "PUT"


# =============================================================================
# PositionSide Enum (for compatibility)
# =============================================================================


class PositionSide(Enum):
    """Position side enumeration"""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


# =============================================================================
# End of Constants
# =============================================================================

# Validation function to ensure constants are properly defined

# =============================================================================
# TimeInForce Enum
# =============================================================================


class TimeInForce(Enum):
    """Time in force enumeration"""

    DAY = "DAY"
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


# =============================================================================
# OrderStatus Enum
# =============================================================================
class OrderStatus(Enum):
    """Order status enumeration"""

    PENDING_SUBMIT = "PendingSubmit"
    PENDING_CANCEL = "PendingCancel"
    PRE_SUBMITTED = "PreSubmitted"
    SUBMITTED = "Submitted"
    CANCELLED = "Cancelled"
    FILLED = "Filled"
    INACTIVE = "Inactive"


# =============================================================================
# OrderType Enum
# =============================================================================
class OrderType(Enum):
    """Order type enumeration"""

    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"


# =============================================================================
# OrderAction Enum
# =============================================================================
class OrderAction(Enum):
    """Order action enumeration"""

    BUY = "BUY"
    SELL = "SELL"


def validate_constants():
    """Simple constants validation."""
    return True


# Run validation when module is imported
if __name__ == "__main__":
    validate_constants()

    # Print summary of research-driven constants
    print("\nResearch-Driven Constants Summary:")
    print("=" * 60)

    print("\nDay-of-Week Position Sizing:")
    #     print(f"  Monday: {MONDAY_MIN_POSITION_PCT:.1%} - {MONDAY_MAX_POSITION_PCT:.1%}")
    #     print(f"  Other Days: {OTHER_DAY_MIN_POSITION_PCT:.1%} - {OTHER_DAY_MAX_POSITION_PCT:.1%}")
    print(f"  Reduction Factor: {DAY_OF_WEEK_REDUCTION:.0%}")

    print("\nOptimal Trading Windows:")
    #     print(f"  Entry Window: {OPTIMAL_ENTRY_START_HOUR}:{OPTIMAL_ENTRY_START_MINUTE:02d} - {OPTIMAL_ENTRY_END_HOUR}:{OPTIMAL_ENTRY_END_MINUTE:02d}")
    #     print(f"  Exit Time: {TIME_BASED_EXIT_HOUR}:{TIME_BASED_EXIT_MINUTE:02d}")

    print("\nProfit Targets:")
    print(f"  Iron Condor: {IRON_CONDOR_PROFIT_TARGET:.0%} of credit")
    print(f"  Credit Spread: {CREDIT_SPREAD_PROFIT_TARGET:.0%} of credit")
    print(f"  Iron Butterfly: {IRON_BUTTERFLY_PROFIT_TARGET:.0%} of max profit")

    print("\nEntry Filters:")
    print(f"  Min IV Percentile: {MIN_IVP_THRESHOLD}")
    print(f"  Max Overnight Gap: {MAX_OVERNIGHT_GAP:.1%}")
    print(f"  RSI Range: {RSI_MIN} - {RSI_MAX}")
    print(f"  VIX Range: {VIX_MIN} - {VIX_MAX}")

    print("\nDefault Feature Flags:")
    for flag, state in DEFAULT_FEATURE_FLAGS.items():
        print(f"  {flag}: {'Enabled' if state else 'Disabled'}")

    print(
        f"\nConstants module loaded successfully with {len([n for n in globals() if n.isupper()])} constants defined."
    )

# =============================================================================
# Module Exports
# =============================================================================
__all__ = [
    # Trading constants
    "PRIMARY_SYMBOL",
    "OPTION_MULTIPLIER",
    "SPY_CONTRACT_MULTIPLIER",
    "SPX_CONTRACT_MULTIPLIER",
    "OPTIONS_TICK_SIZE",
    "MAX_POSITIONS",
    "MAX_POSITION_SIZE",
    # Calendar constants
    "TRADING_DAYS_PER_YEAR",
    "TRADING_DAYS_PER_MONTH",
    "TRADING_HOURS_PER_DAY",
    # System constants
    "LATENCY_SAMPLE_SIZE",
    "MAX_ORDER_LATENCY",
    "MAX_DATA_LATENCY",
    "SESSION_TIMEOUT",
    # Enums
    "SignalType",
    "PositionSide",
    # Classes
    "TradingConstants",
]
