#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System

Tradov Version: 1.0
Module: TradovD00_StrategyConstants.py
Group: D (Strategies)
Purpose: Strategy constants and configuration parameters
Author: Mohamed Talib
Date Created: 2025-08-14
Last Updated: 2026-06-26 Time: 13:25:07

Description:
    This module provides centralized constants for all trading strategies,
    including risk parameters, position limits, and trade thresholds. It
    resolves the missing constants issue identified in the dependency analysis
    and provides a single source of truth for strategy configuration.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from enum import Enum
from typing import Any
import logging

# ==============================================================================
# RISK MANAGEMENT CONSTANTS
# ==============================================================================

# Portfolio Risk Limits
MAX_PORTFOLIO_RISK = 0.02  # 2% maximum portfolio risk per trade
MAX_DAILY_LOSS = 0.05  # 5% maximum daily portfolio loss
MAX_WEEKLY_LOSS = 0.10  # 10% maximum weekly portfolio loss
MAX_MONTHLY_LOSS = 0.15  # 15% maximum monthly portfolio loss

# Position Risk Parameters
STOP_LOSS_PERCENTAGE = 0.015  # 1.5% stop loss per position
TAKE_PROFIT_PERCENTAGE = 0.03  # 3% take profit target
TRAILING_STOP_PERCENTAGE = 0.01  # 1% trailing stop

# ==============================================================================
# POSITION SIZING CONSTANTS
# ==============================================================================

# Position Limits
MAX_POSITIONS = 10  # Maximum concurrent positions
MAX_POSITION_SIZE = 0.10  # 10% max allocation per position
MIN_POSITION_SIZE = 0.01  # 1% minimum position size
MAX_LEVERAGE = 2.0  # Maximum leverage allowed

# ==============================================================================
# TRADING THRESHOLDS
# ==============================================================================

# Entry Conditions
MIN_PROBABILITY_OF_PROFIT = 0.60  # 60% minimum probability of profit
MIN_EXPECTED_VALUE = 50  # Minimum expected value in dollars
MIN_RISK_REWARD_RATIO = 1.5  # Minimum risk/reward ratio
MIN_VOLUME_THRESHOLD = 100  # Minimum volume for entry
MIN_OPEN_INTEREST = 50  # Minimum open interest

# Exit Conditions
PROFIT_TARGET_PERCENTAGE = 0.50  # Exit at 50% of max profit
TIME_STOP_PERCENTAGE = 0.30  # Exit if 30% time to expiry remaining
VOLATILITY_EXIT_THRESHOLD = 2.0  # Exit if volatility exceeds 2x normal

# ==============================================================================
# MARKET REGIME THRESHOLDS
# ==============================================================================

# Volatility Regimes
LOW_VOLATILITY_THRESHOLD = 10  # VIX < 10
NORMAL_VOLATILITY_RANGE = (10, 20)  # VIX 10-20
HIGH_VOLATILITY_THRESHOLD = 20  # VIX > 20
EXTREME_VOLATILITY_THRESHOLD = 30  # VIX > 30

# Trend Detection
TREND_STRENGTH_THRESHOLD = 0.7  # ADX threshold for trending
MOMENTUM_THRESHOLD = 70  # RSI overbought/oversold levels
VOLUME_SURGE_MULTIPLIER = 1.5  # Volume surge detection

# ==============================================================================
# TIMING CONSTANTS
# ==============================================================================

# Trading Hours (ET)
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# Trading Windows
NO_TRADE_FIRST_MINUTES = 15  # Avoid first 15 minutes
NO_TRADE_LAST_MINUTES = 30  # Avoid last 30 minutes
POWER_HOUR_START = 15  # 3 PM ET power hour

# ==============================================================================
# TECHNICAL INDICATOR PARAMETERS
# ==============================================================================

INDICATOR_PARAMS = {
    "sma_fast": 20,  # Fast SMA period
    "sma_slow": 50,  # Slow SMA period
    "ema_period": 21,  # EMA period
    "rsi_period": 14,  # RSI period
    "rsi_oversold": 30,  # RSI oversold level
    "rsi_overbought": 70,  # RSI overbought level
    "macd_fast": 12,  # MACD fast period
    "macd_slow": 26,  # MACD slow period
    "macd_signal": 9,  # MACD signal period
    "bollinger_period": 20,  # Bollinger Bands period
    "bollinger_std": 2,  # Bollinger Bands std dev
    "atr_period": 14,  # ATR period
    "adx_period": 14,  # ADX period
}

# ==============================================================================
# CIRCUIT BREAKER PARAMETERS
# ==============================================================================

CIRCUIT_BREAKER_CONFIG = {
    "max_consecutive_losses": 3,  # Stop after 3 consecutive losses
    "max_daily_trades": 20,  # Maximum trades per day
    "cooldown_period_minutes": 30,  # Cooldown after circuit breaker
    "loss_velocity_threshold": 0.03,  # 3% loss in 5 minutes triggers halt
    "error_rate_threshold": 0.10,  # 10% error rate triggers halt
}

# ==============================================================================
# COMMISSION AND SLIPPAGE
# ==============================================================================

COMMISSION_PER_CONTRACT = 0.65  # Tradier commission per contract
SLIPPAGE_FACTOR = 0.001  # 0.1% slippage assumption
MIN_PROFIT_AFTER_COSTS = 25  # Minimum profit after costs

# ==============================================================================
# STRATEGY SELECTION ENUMS
# ==============================================================================


class StrategyType(Enum):
    """Available strategy types"""

    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    BROKEN_WING_BUTTERFLY = "broken_wing_butterfly"
    CREDIT_SPREAD = "credit_spread"
    DEBIT_SPREAD = "debit_spread"
    CALENDAR_SPREAD = "calendar_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    STRADDLE = "straddle"
    STRANGLE = "strangle"
    BUTTERFLY = "butterfly"
    CONDOR = "condor"
    RATIO_SPREAD = "ratio_spread"
    COVERED_CALL = "covered_call"
    CASH_SECURED_PUT = "cash_secured_put"
    PROTECTIVE_PUT = "protective_put"
    COLLAR = "collar"
    CUSTOM = "custom"


class MarketRegime(Enum):
    """Market regime classifications"""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRANSITIONING = "transitioning"


class RiskLevel(Enum):
    """Risk level classifications"""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


class StrategyLifecycleState(Enum):
    """Strategy position lifecycle state shown in the Orders & Positions panel.

    Tracks where a multi-leg strategy sits in its full lifecycle — from AI
    selection through active management to the final close event and its
    initiator.

    States:
        ARMED_BY_AI:    AI selected strategy; awaiting entry conditions to be met.
        ENTERED_BY_AI:  All legs filled; position is live.
        MANAGED_BY_AI:  Position open; AI is actively monitoring / adjusting.
        CLOSED_BY_AI:   AI exited (profit target, DTE expiry, thesis change, roll).
        CLOSED_BY_USER: Operator manually closed via the dashboard.
        CLOSED_BY_RISK: Automated exit by stop-loss, max-loss, or circuit breaker.
    """

    ARMED_BY_AI = "ARMED BY AI"
    ENTERED_BY_AI = "ENTERED BY AI"
    MANAGED_BY_AI = "EXECUTING"
    CLOSED_BY_AI = "CLOSED BY AI"
    CLOSED_BY_USER = "CLOSED BY USER"
    CLOSED_BY_RISK = "CLOSED BY RISK"


# ==============================================================================
# VALIDATION RANGES
# ==============================================================================


VALIDATION_RANGES = {
    "stop_loss": (0.001, 0.10),  # 0.1% to 10%
    "take_profit": (0.001, 0.50),  # 0.1% to 50%
    "position_size": (0.001, 0.20),  # 0.1% to 20%
    "max_positions": (1, 20),  # 1 to 20 positions
    "days_to_expiry": (0, 365),  # 0 to 365 days
    "delta": (-1.0, 1.0),  # -1 to 1
    "implied_volatility": (0, 5.0),  # 0 to 500%
}

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================


def get_strategy_constants() -> dict[str, Any]:
    """
    Get all strategy constants as a dictionary.

    Returns:
        Dictionary containing all strategy constants
    """
    return {
        # Risk Management
        "MAX_PORTFOLIO_RISK": MAX_PORTFOLIO_RISK,
        "STOP_LOSS_PERCENTAGE": STOP_LOSS_PERCENTAGE,
        "TAKE_PROFIT_PERCENTAGE": TAKE_PROFIT_PERCENTAGE,
        "TRAILING_STOP_PERCENTAGE": TRAILING_STOP_PERCENTAGE,
        # Position Sizing
        "MAX_POSITIONS": MAX_POSITIONS,
        "MAX_POSITION_SIZE": MAX_POSITION_SIZE,
        "MIN_POSITION_SIZE": MIN_POSITION_SIZE,
        # Options Limits
        "MAX_OPTIONS_CONTRACTS": MAX_OPTIONS_CONTRACTS,
        "MAX_DELTA_EXPOSURE": MAX_DELTA_EXPOSURE,
        "MAX_GAMMA_EXPOSURE": MAX_GAMMA_EXPOSURE,
        # Trading Thresholds
        "MIN_PROBABILITY_OF_PROFIT": MIN_PROBABILITY_OF_PROFIT,
        "MIN_RISK_REWARD_RATIO": MIN_RISK_REWARD_RATIO,
        # Strategy Configs
        "IRON_CONDOR_CONFIG": IRON_CONDOR_CONFIG,
        "CREDIT_SPREAD_CONFIG": CREDIT_SPREAD_CONFIG,
        "NEUTRAL_STRATEGY_CONFIG": NEUTRAL_STRATEGY_CONFIG,
        # Circuit Breakers
        "CIRCUIT_BREAKER_CONFIG": CIRCUIT_BREAKER_CONFIG,
    }


def validate_constant(name: str, value: Any) -> bool:
    """
    Validate a strategy constant is within acceptable range.

    Args:
        name: Constant name
        value: Constant value

    Returns:
        True if valid, False otherwise
    """
    if name in VALIDATION_RANGES:
        min_val, max_val = VALIDATION_RANGES[name]
        return min_val <= value <= max_val
    return True


# ==============================================================================
# MODULE EXPORTS
# ==============================================================================


__all__ = [
    # Risk Constants
    "MAX_PORTFOLIO_RISK",
    "STOP_LOSS_PERCENTAGE",
    "TAKE_PROFIT_PERCENTAGE",
    "TRAILING_STOP_PERCENTAGE",
    # Position Constants
    "MAX_POSITIONS",
    "MAX_POSITION_SIZE",
    "MIN_POSITION_SIZE",
    # Trading Thresholds
    "MIN_PROBABILITY_OF_PROFIT",
    "MIN_RISK_REWARD_RATIO",
    "MIN_EXPECTED_VALUE",
    # Enums
    "StrategyType",
    "MarketRegime",
    "RiskLevel",
    # Functions
    "get_strategy_constants",
    "validate_constant",
]

# Log module initialization
logging.info("✅ Strategy Constants Module Loaded - %s exports available", len(__all__))
