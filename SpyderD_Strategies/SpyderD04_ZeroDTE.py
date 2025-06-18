#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD04_ZeroDTE.py
Group: D (Trading Strategies)
Purpose: 0DTE scalping strategy

Description:
    This module implements a 0DTE (zero days to expiration) options scalping
    strategy. It focuses on quick intraday trades using same-day expiring
    options to capture rapid price movements with high gamma exposure.

Author: Mohamed Talib
Date: 2024-12-07
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import math
import uuid
from enum import Enum, auto

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import (
    OptionType, OrderAction, SignalType, OptionRight
)
from SpyderU_Utilities.SpyderU10_TradingCalendar import TradingCalendar

from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Trading windows
MORNING_START = time(9, 45)
MORNING_END = time(11, 30)
AFTERNOON_START = time(13, 0)
CLOSING_START = time(15, 30)
MARKET_CLOSE = time(16, 0)

# Entry criteria
MIN_VOLUME_RATIO = 1.2
MIN_MOMENTUM_SCORE = 0.65
MIN_GAMMA_EXPOSURE = 0.5
MAX_SPREAD_WIDTH = 0.10

# Risk parameters
MAX_POSITION_HOLD_MINUTES = 30
STOP_LOSS_PERCENT = 0.20
PROFIT_TARGET_PERCENT = 0.30
MAX_DAILY_TRADES = 10
MAX_CONSECUTIVE_LOSSES = 3

# Technical parameters
SCALP_RSI_PERIOD = 5
MOMENTUM_LOOKBACK = 10
VWAP_BANDS_STD = 2.0
ATR_MULTIPLIER = 1.5

# Market internals thresholds
TICK_EXTREME_HIGH = 800
TICK_EXTREME_LOW = -800
ADD_BULLISH_THRESHOLD = 1000
ADD_BEARISH_THRESHOLD = -1000

# ==============================================================================
# ENUMERATIONS
# ==============================================================================
class ScalpDirection(Enum):
    """Scalp trade direction"""
    LONG = auto()
    SHORT = auto()
    NEUTRAL = auto()

class MarketPhase(Enum):
    """Market trading phase"""
    OPENING = auto()
    MORNING = auto()
    MIDDAY = auto()
    AFTERNOON = auto()
    CLOSING = auto()
    CLOSED = auto()

class MomentumState(Enum):
    """Momentum state"""
    STRONG_BULLISH = auto()
    BULLISH = auto()
    NEUTRAL = auto()
    BEARISH = auto()
    STRONG_BEARISH = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ScalpSetup:
    """Scalp trade setup"""
    direction: ScalpDirection
    entry_price: float
    stop_loss: float
    profit_target: float
    option_strike: float
    option_type: OptionRight
    gamma: float
    momentum_score: float
    volume_ratio: float
    risk_reward_ratio: float
    setup_quality: float
    expiration: str

@dataclass
class MarketContext:
    """Current market context"""
    phase: MarketPhase
    momentum_state: MomentumState
    tick_reading: float
    add_reading: float
    vix_level: float
    volume_profile: str
    trend_strength: float
    volatility: float
    support_levels: List[float]
    resistance_levels: List[float]

@dataclass
class DayStats:
    """Daily trading statistics"""
    trades_taken: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_hold_time: float = 0.0

@dataclass
class ZeroDTESignal:
    """0DTE trading signal"""
    signal_id: str
    timestamp: datetime
    setup: ScalpSetup
    confidence: float
    expires_at: datetime

# ==============================================================================
# ZERO DTE STRATEGY CLASS
# ==============================================================================
class ZeroDTEStrategy(BaseStrategy):
    """
    Zero DTE options scalping strategy.
    
    Focuses on:
    - Quick intraday momentum trades
    - High gamma exposure for rapid profits
    - Strict risk management
    - Market internals confirmation
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize 0DTE strategy."""
        super().__init__("ZeroDTE", config)
        
        # Initialize components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.risk_manager = get_risk_manager()
        
        # Strategy configuration
        self.max_trades_per_day = config.get('max_trades_per_day', MAX_DAILY_TRADES)
        self.use_market_internals = config.get('use_market_internals', True)
        self.trade_morning = config.get('trade_morning', True)
        self.trade_afternoon = config.get('trade_afternoon', True)
        self.min_option_volume = config.get('min_option_volume', 100)
        
        # Components
        self.indicators = TechnicalIndicators()
        self.greeks_calculator = GreeksCalculator()
        self.market_internals = MarketInternals()
        self.trading_calendar = TradingCalendar()
        
        # State tracking
        self.day_stats = DayStats()
        self.market_context = None
        self.last_trade_time = None
        self.active_setups: List[ScalpSetup] = []
        self.active_positions = {}
        
        # Performance tracking
        self.trade_history: List[Dict[str, Any]] = []
        
        self.logger.info("ZeroDTEStrategy initialized")
    
    # ==========================================================================
    # MARKET ANALYSIS
    # ==========================================================================
    
    def analyze_market(self, market_data: Dict[str, Any]) -> List[ZeroDTESignal]:
        """Analyze market for 0DTE opportunities."""
        signals = []
        
        # Check if we can trade
        if not self._can_trade():
            return signals
        
        # Update market context
        self._update_market_context(market_data)
        
        if self.market_context is None:
            return signals
        
        try:
            # Convert market data to DataFrame for analysis
            df = self._prepare_market_data(market_data)
            
            # Look for scalp setups
            setups = self._find_scalp_setups(df)
            
            # Convert best setups to signals
            for setup in setups[:2]:  # Maximum 2 signals at once
                signal = self._create_signal_from_setup(setup)
                if signal:
                    signals.append(signal)
            
        except Exception as e:
            self.logger.error(f"Error generating signals: {e}")
            self.error_handler.handle_error(e)
        
        return signals
    
    def _can_trade(self) -> bool:
        """Check if trading is allowed"""
        current_time = datetime.now().time()
        
        # Check market hours
        if current_time < MORNING_START or current_time > CLOSING_START:
            return False
        
        # Check if it's a trading day
        if not self.trading_calendar.is_trading_day(datetime.now().date()):
            return False
        
        # Check if 0DTE options are available today
        if not self.trading_calendar.has_options_expiring(datetime.now().date()):
            self.logger.debug("No 0DTE options available today")
            return False
        
        # Check daily limits
        if self.day_stats.trades_taken >= self.max_trades_per_day:
            self.logger.info("Daily trade limit reached")
            return False
        
        # Check consecutive losses
        if self.day_stats.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            self.logger.warning("Maximum consecutive losses reached")
            return False
        
        # Check time since last trade
        if self.last_trade_time:
            time_since_last = (datetime.now() - self.last_trade_time).seconds
            if time_since_last < 300:  # 5 minute cooldown
                return False
        
        return True
    
    def _update_market_context(self, market_data: Dict[str, Any]) -> None:
        """Update current market context"""
        current_price = market_data.get('last_price', 0)
        current_time = datetime.now().time()
        
        # Determine market phase
        phase = self._get_market_phase(current_time)
        
        # Get price history
        price_history = market_data.get('price_history', pd.DataFrame())
        if price_history.empty:
            return
        
        # Calculate momentum state
        momentum_state = self._calculate_momentum_state(price_history)
        
        # Get market internals
        tick_reading = 0
        add_reading = 0
        vix_level = market_data.get('vix', 15)
        
        if self.use_market_internals:
            internals = self.market_internals.get_current_snapshot()
            if internals:
                tick_reading = internals.nyse_tick or 0
                add_reading = internals.nyse_add_line or 0
        
        # Calculate support/resistance
        support_levels = self._calculate_support_levels(price_history, current_price)
        resistance_levels = self._calculate_resistance_levels(price_history, current_price)
        
        # Volume profile
        current_volume = market_data.get('volume', 0)
        avg_volume = market_data.get('avg_volume', current_volume)
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        volume_profile = "high" if volume_ratio > 1.5 else "normal" if volume_ratio > 0.8 else "low"
        
        # Trend and volatility
        returns = price_history['close'].pct_change()
        volatility = returns.rolling(10).std().iloc[-1] * math.sqrt(252 * 78)
        
        sma_20 = price_history['close'].rolling(20).mean().iloc[-1]
        trend_strength = abs(current_price - sma_20) / sma_20 if sma_20 > 0 else 0
        
        self.market_context = MarketContext(
            phase=phase,
            momentum_state=momentum_state,
            tick_reading=tick_reading,
            add_reading=add_reading,
            vix_level=vix_level,
            volume_profile=volume_profile,
            trend_strength=trend_strength,
            volatility=volatility,
            support_levels=support_levels,
            resistance_levels=resistance_levels
        )
    
    def _prepare_market_data(self, market_data: Dict[str, Any]) -> pd.DataFrame:
        """Prepare market data for analysis."""
        # Get price history or create from current data
        if 'price_history' in market_data and not market_data['price_history'].empty:
            return market_data['price_history']
        
        # Create minimal DataFrame from current data
        current_time = datetime.now()
        times = [current_time - timedelta(minutes=i) for i in range(20, -1, -1)]
        
        # Generate synthetic OHLCV data
        base_price = market_data.get('last_price', 450)
        data = {
            'timestamp': times,
            'open': [base_price] * 21,
            'high': [base_price + 0.1] * 21,
            'low': [base_price - 0.1] * 21,
            'close': [base_price] * 21,
            'volume': [market_data.get('volume', 1000000)] * 21
        }
        
        return pd.DataFrame(data)
    
    # ==========================================================================
    # SETUP IDENTIFICATION
    # ==========================================================================
    
    def _find_scalp_setups(self, market_data: pd.DataFrame) -> List[ScalpSetup]:
        """Find potential scalp setups"""
        setups = []
        current_price = market_data['close'].iloc[-1]
        
        # Check for momentum breakout setups
        momentum_setup = self._check_momentum_breakout(market_data)
        if momentum_setup:
            setups.append(momentum_setup)
        
        # Check for reversal setups at extremes
        reversal_setup = self._check_reversal_setup(market_data)
        if reversal_setup:
            setups.append(reversal_setup)
        
        # Check for continuation setups
        continuation_setup = self._check_continuation_setup(market_data)
        if continuation_setup:
            setups.append(continuation_setup)
        
        # Score and sort setups
        setups.sort(key=lambda x: x.setup_quality, reverse=True)
        
        return setups
    
    def _check_momentum_breakout(self, market_data: pd.DataFrame) -> Optional[ScalpSetup]:
        """Check for momentum breakout setup"""
        if len(market_data) < 20:
            return None
        
        current_price = market_data['close'].iloc[-1]
        
        # Calculate momentum indicators
        rsi = self.indicators.calculate_rsi(market_data['close'], period=SCALP_RSI_PERIOD)
        
        # Price momentum
        momentum = (current_price - market_data['close'].iloc[-MOMENTUM_LOOKBACK]) / \
                  market_data['close'].iloc[-MOMENTUM_LOOKBACK]
        
        # Volume confirmation
        volume_ratio = market_data['volume'].iloc[-1] / \
                      market_data['volume'].rolling(20).mean().iloc[-1]
        
        # VWAP calculation
        vwap = self._calculate_vwap(market_data)
        vwap_std = market_data['close'].rolling(20).std().iloc[-1]
        upper_band = vwap + VWAP_BANDS_STD * vwap_std
        lower_band = vwap - VWAP_BANDS_STD * vwap_std
        
        # Momentum score
        momentum_score = self._calculate_momentum_score(
            momentum, rsi.iloc[-1], volume_ratio,
            self.market_context.tick_reading if self.market_context else 0
        )
        
        # Determine direction and setup
        setup = None
        
        # Bullish breakout
        if (momentum > 0.002 and 60 < rsi.iloc[-1] < 80 and
            volume_ratio > MIN_VOLUME_RATIO and
            current_price > vwap and
            momentum_score > MIN_MOMENTUM_SCORE):
            
            # Find appropriate strike
            strike = self._find_optimal_strike(current_price, ScalpDirection.LONG)
            
            # Calculate targets
            atr = self._calculate_atr(market_data, period=10)
            stop_loss = current_price - atr * ATR_MULTIPLIER
            profit_target = current_price + atr * ATR_MULTIPLIER * 2
            
            # Calculate gamma
            gamma = self._estimate_gamma(current_price, strike, OptionRight.CALL)
            
            if gamma > MIN_GAMMA_EXPOSURE:
                setup = ScalpSetup(
                    direction=ScalpDirection.LONG,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    profit_target=profit_target,
                    option_strike=strike,
                    option_type=OptionRight.CALL,
                    gamma=gamma,
                    momentum_score=momentum_score,
                    volume_ratio=volume_ratio,
                    risk_reward_ratio=(profit_target - current_price) / (current_price - stop_loss),
                    setup_quality=momentum_score * gamma,
                    expiration=datetime.now().strftime("%Y%m%d")
                )
        
        # Bearish breakout
        elif (momentum < -0.002 and 20 < rsi.iloc[-1] < 40 and
              volume_ratio > MIN_VOLUME_RATIO and
              current_price < vwap and
              momentum_score > MIN_MOMENTUM_SCORE):
            
            strike = self._find_optimal_strike(current_price, ScalpDirection.SHORT)
            
            atr = self._calculate_atr(market_data, period=10)
            stop_loss = current_price + atr * ATR_MULTIPLIER
            profit_target = current_price - atr * ATR_MULTIPLIER * 2
            
            gamma = self._estimate_gamma(current_price, strike, OptionRight.PUT)
            
            if gamma > MIN_GAMMA_EXPOSURE:
                setup = ScalpSetup(
                    direction=ScalpDirection.SHORT,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    profit_target=profit_target,
                    option_strike=strike,
                    option_type=OptionRight.PUT,
                    gamma=gamma,
                    momentum_score=momentum_score,
                    volume_ratio=volume_ratio,
                    risk_reward_ratio=(current_price - profit_target) / (stop_loss - current_price),
                    setup_quality=momentum_score * gamma,
                    expiration=datetime.now().strftime("%Y%m%d")
                )
        
        return setup
    
    def _check_reversal_setup(self, market_data: pd.DataFrame) -> Optional[ScalpSetup]:
        """Check for reversal setup at extremes"""
        if not self.market_context:
            return None
        
        current_price = market_data['close'].iloc[-1]
        
        # Check for extreme conditions
        tick_extreme = (self.market_context.tick_reading > TICK_EXTREME_HIGH or
                       self.market_context.tick_reading < TICK_EXTREME_LOW)
        
        if not tick_extreme:
            return None
        
        # RSI divergence
        rsi = self.indicators.calculate_rsi(market_data['close'], period=SCALP_RSI_PERIOD)
        
        # Look for reversal patterns
        setup = None
        
        # Bearish reversal at resistance
        if (self.market_context.tick_reading > TICK_EXTREME_HIGH and
            rsi.iloc[-1] > 70):
            
            # Check if near resistance
            for resistance in self.market_context.resistance_levels:
                if abs(current_price - resistance) / current_price < 0.001:
                    
                    strike = self._find_optimal_strike(current_price, ScalpDirection.SHORT)
                    atr = self._calculate_atr(market_data, period=10)
                    
                    stop_loss = resistance + atr * 0.5
                    profit_target = current_price - atr * 1.5
                    
                    gamma = self._estimate_gamma(current_price, strike, OptionRight.PUT)
                    momentum_score = 0.7
                    
                    if gamma > MIN_GAMMA_EXPOSURE:
                        setup = ScalpSetup(
                            direction=ScalpDirection.SHORT,
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            profit_target=profit_target,
                            option_strike=strike,
                            option_type=OptionRight.PUT,
                            gamma=gamma,
                            momentum_score=momentum_score,
                            volume_ratio=1.0,
                            risk_reward_ratio=(current_price - profit_target) / (stop_loss - current_price),
                            setup_quality=momentum_score * gamma * 0.8,
                            expiration=datetime.now().strftime("%Y%m%d")
                        )
                    break
        
        # Bullish reversal at support
        elif (self.market_context.tick_reading < TICK_EXTREME_LOW and
              rsi.iloc[-1] < 30):
            
            for support in self.market_context.support_levels:
                if abs(current_price - support) / current_price < 0.001:
                    
                    strike = self._find_optimal_strike(current_price, ScalpDirection.LONG)
                    atr = self._calculate_atr(market_data, period=10)
                    
                    stop_loss = support - atr * 0.5
                    profit_target = current_price + atr * 1.5
                    
                    gamma = self._estimate_gamma(current_price, strike, OptionRight.CALL)
                    momentum_score = 0.7
                    
                    if gamma > MIN_GAMMA_EXPOSURE:
                        setup = ScalpSetup(
                            direction=ScalpDirection.LONG,
                            entry_price=current_price,
                            stop_loss=stop_loss,
                            profit_target=profit_target,
                            option_strike=strike,
                            option_type=OptionRight.CALL,
                            gamma=gamma,
                            momentum_score=momentum_score,
                            volume_ratio=1.0,
                            risk_reward_ratio=(profit_target - current_price) / (current_price - stop_loss),
                            setup_quality=momentum_score * gamma * 0.8,
                            expiration=datetime.now().strftime("%Y%m%d")
                        )
                    break
        
        return setup
    
    def _check_continuation_setup(self, market_data: pd.DataFrame) -> Optional[ScalpSetup]:
        """Check for trend continuation setup"""
        if not self.market_context or len(market_data) < 50:
            return None
        
        current_price = market_data['close'].iloc[-1]
        
        # Trend analysis
        sma_9 = market_data['close'].rolling(9).mean()
        sma_20 = market_data['close'].rolling(20).mean()
        
        # Pullback to moving average
        pullback_to_ma = abs(current_price - sma_9.iloc[-1]) / current_price < 0.001
        
        if not pullback_to_ma:
            return None
        
        # Trend direction
        trend_up = sma_9.iloc[-1] > sma_20.iloc[-1] and sma_9.iloc[-5] < sma_9.iloc[-1]
        trend_down = sma_9.iloc[-1] < sma_20.iloc[-1] and sma_9.iloc[-5] > sma_9.iloc[-1]
        
        setup = None
        
        # Bullish continuation
        if trend_up and self.market_context.momentum_state in [MomentumState.BULLISH, MomentumState.STRONG_BULLISH]:
            
            strike = self._find_optimal_strike(current_price, ScalpDirection.LONG)
            atr = self._calculate_atr(market_data, period=10)
            
            stop_loss = sma_20.iloc[-1]
            profit_target = current_price + atr * 2
            
            gamma = self._estimate_gamma(current_price, strike, OptionRight.CALL)
            momentum_score = 0.75
            
            if gamma > MIN_GAMMA_EXPOSURE:
                setup = ScalpSetup(
                    direction=ScalpDirection.LONG,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    profit_target=profit_target,
                    option_strike=strike,
                    option_type=OptionRight.CALL,
                    gamma=gamma,
                    momentum_score=momentum_score,
                    volume_ratio=1.0,
                    risk_reward_ratio=(profit_target - current_price) / (current_price - stop_loss),
                    setup_quality=momentum_score * gamma * 0.9,
                    expiration=datetime.now().strftime("%Y%m%d")
                )
        
        # Bearish continuation
        elif trend_down and self.market_context.momentum_state in [MomentumState.BEARISH, MomentumState.STRONG_BEARISH]:
            
            strike = self._find_optimal_strike(current_price, ScalpDirection.SHORT)
            atr = self._calculate_atr(market_data, period=10)
            
            stop_loss = sma_20.iloc[-1]
            profit_target = current_price - atr * 2
            
            gamma = self._estimate_gamma(current_price, strike, OptionRight.PUT)
            momentum_score = 0.75
            
            if gamma > MIN_GAMMA_EXPOSURE:
                setup = ScalpSetup(
                    direction=ScalpDirection.SHORT,
                    entry_price=current_price,
                    stop_loss=stop_loss,
                    profit_target=profit_target,
                    option_strike=strike,
                    option_type=OptionRight.PUT,
                    gamma=gamma,
                    momentum_score=momentum_score,
                    volume_ratio=1.0,
                    risk_reward_ratio=(current_price - profit_target) / (stop_loss - current_price),
                    setup_quality=momentum_score * gamma * 0.9,
                    expiration=datetime.now().strftime("%Y%m%d")
                )
        
        return setup
    
    def _create_signal_from_setup(self, setup: ScalpSetup) -> Optional[ZeroDTESignal]:
        """Create trading signal from setup"""
        # Verify 0DTE expiration exists
        if not self._verify_zero_dte_expiration():
            return None
        
        # Create signal
        signal = ZeroDTESignal(
            signal_id=f"0DTE_{uuid.uuid4().hex[:8]}",
            timestamp=datetime.now(),
            setup=setup,
            confidence=setup.momentum_score,
            expires_at=datetime.now() + timedelta(minutes=5)  # Signal expires quickly
        )
        
        return signal
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    
    def execute_signal(self, signal: ZeroDTESignal) -> bool:
        """Execute 0DTE signal."""
        try:
            # Verify we can still trade
            if not self._can_trade():
                return False
            
            # Check signal is still valid
            if datetime.now() > signal.expires_at:
                self.logger.info("Signal expired")
                return False
            
            # Verify market hasn't moved too much
            current_price = self._get_current_price()
            price_change = abs(current_price - signal.setup.entry_price) / signal.setup.entry_price
            if price_change > 0.002:  # 0.2% maximum slippage
                self.logger.info(f"Price moved too much since signal: {price_change:.2%}")
                return False
            
            # Calculate position size
            position_size = self._calculate_position_size(signal.setup)
            
            # Create option contract
            contract = ContractBuilder.create_option_contract(
                symbol='SPY',
                expiration=signal.setup.expiration,
                strike=signal.setup.option_strike,
                right='C' if signal.setup.option_type == OptionRight.CALL else 'P'
            )
            
            # Place order
            order = self._create_order(signal.setup, position_size)
            order_id = self.ib_client.place_order(contract, order)
            
            if order_id:
                # Track position
                position_id = f"0DTE_{order_id}"
                self.active_positions[position_id] = {
                    'signal': signal,
                    'order_id': order_id,
                    'entry_time': datetime.now(),
                    'position_size': position_size,
                    'status': 'pending'
                }
                
                # Update day stats
                self.day_stats.trades_taken += 1
                self.last_trade_time = datetime.now()
                
                # Emit event
                self.event_manager.create_event(
                    EventType.POSITION,
                    {
                        'action': 'opened',
                        'strategy': 'ZeroDTE',
                        'position_id': position_id,
                        'setup': signal.setup
                    },
                    source='ZeroDTEStrategy'
                )
                
                self.logger.info(f"0DTE position opened: {position_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            self.error_handler.handle_error(e)
            
        return False
    
    def manage_positions(self) -> None:
        """Manage active 0DTE positions."""
        for position_id, position in list(self.active_positions.items()):
            try:
                if position['status'] == 'closed':
                    continue
                
                # Get position details
                signal = position['signal']
                setup = signal.setup
                hold_time = (datetime.now() - position['entry_time']).seconds / 60.0
                
                # Get current position value
                current_price = self._get_current_price()
                position_pnl = self._calculate_position_pnl(position, current_price)
                
                # Check exit conditions
                should_exit = False
                exit_reason = ""
                
                # Time-based exit
                if hold_time >= MAX_POSITION_HOLD_MINUTES:
                    should_exit = True
                    exit_reason = "max_hold_time"
                
                # Profit target
                elif position_pnl >= setup.entry_price * PROFIT_TARGET_PERCENT * position['position_size'] * 100:
                    should_exit = True
                    exit_reason = "profit_target"
                
                # Stop loss
                elif position_pnl <= -setup.entry_price * STOP_LOSS_PERCENT * position['position_size'] * 100:
                    should_exit = True
                    exit_reason = "stop_loss"
                
                # Market conditions changed
                elif self._check_adverse_conditions(setup, current_price):
                    should_exit = True
                    exit_reason = "adverse_conditions"
                
                # Approaching close
                elif datetime.now().time() > time(15, 45):
                    should_exit = True
                    exit_reason = "market_close"
                
                if should_exit:
                    self._close_position(position_id, position, exit_reason)
                    
            except Exception as e:
                self.logger.error(f"Error managing position {position_id}: {e}")
                self.error_handler.handle_error(e)
    
    def _close_position(self, position_id: str, position: Dict, reason: str) -> None:
        """Close a 0DTE position."""
        try:
            # Create closing order
            signal = position['signal']
            setup = signal.setup
            
            contract = ContractBuilder.create_option_contract(
                symbol='SPY',
                expiration=setup.expiration,
                strike=setup.option_strike,
                right='C' if setup.option_type == OptionRight.CALL else 'P'
            )
            
            closing_order = self.ib_client.create_market_order(
                action='SELL' if setup.direction == ScalpDirection.LONG else 'BUY',
                quantity=position['position_size']
            )
            
            close_order_id = self.ib_client.place_order(contract, closing_order)
            
            if close_order_id:
                # Calculate final P&L
                final_pnl = self._calculate_position_pnl(position, self._get_current_price())
                
                # Update position
                position['status'] = 'closed'
                position['close_time'] = datetime.now()
                position['close_reason'] = reason
                position['pnl'] = final_pnl
                
                # Update day stats
                self._update_day_stats({
                    'pnl': final_pnl,
                    'hold_time': (datetime.now() - position['entry_time']).seconds / 60.0
                })
                
                # Record trade
                self.trade_history.append({
                    'position_id': position_id,
                    'signal_id': signal.signal_id,
                    'entry_time': position['entry_time'],
                    'close_time': datetime.now(),
                    'close_reason': reason,
                    'setup': setup,
                    'pnl': final_pnl,
                    'hold_time': (datetime.now() - position['entry_time']).seconds / 60.0
                })
                
                # Emit event
                self.event_manager.create_event(
                    EventType.POSITION,
                    {
                        'action': 'closed',
                        'strategy': 'ZeroDTE',
                        'position_id': position_id,
                        'reason': reason,
                        'pnl': final_pnl
                    },
                    source='ZeroDTEStrategy'
                )
                
                self.logger.info(f"0DTE position closed: {position_id}, Reason: {reason}, P&L: ${final_pnl:.2f}")
                
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            self.error_handler.handle_error(e)
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    
    def _get_market_phase(self, current_time: time) -> MarketPhase:
        """Determine current market phase"""
        if current_time < time(9, 30):
            return MarketPhase.CLOSED
        elif current_time < time(10, 0):
            return MarketPhase.OPENING
        elif current_time < time(11, 30):
            return MarketPhase.MORNING
        elif current_time < time(13, 0):
            return MarketPhase.MIDDAY
        elif current_time < time(15, 30):
            return MarketPhase.AFTERNOON
        elif current_time < time(16, 0):
            return MarketPhase.CLOSING
        else:
            return MarketPhase.CLOSED
    
    def _calculate_momentum_state(self, market_data: pd.DataFrame) -> MomentumState:
        """Calculate current momentum state"""
        if len(market_data) < 20:
            return MomentumState.NEUTRAL
        
        # Price momentum
        returns = market_data['close'].pct_change()
        momentum_5 = returns.rolling(5).sum().iloc[-1]
        momentum_10 = returns.rolling(10).sum().iloc[-1]
        
        # Moving average alignment
        sma_5 = market_data['close'].rolling(5).mean().iloc[-1]
        sma_10 = market_data['close'].rolling(10).mean().iloc[-1]
        sma_20 = market_data['close'].rolling(20).mean().iloc[-1]
        
        # RSI
        rsi = self.indicators.calculate_rsi(market_data['close'], period=SCALP_RSI_PERIOD)
        rsi_value = rsi.iloc[-1]
        
        # Determine state
        if momentum_5 > 0.01 and momentum_10 > 0.015 and sma_5 > sma_10 > sma_20 and rsi_value > 70:
            return MomentumState.STRONG_BULLISH
        elif momentum_5 > 0.005 and sma_5 > sma_10 and rsi_value > 50:
            return MomentumState.BULLISH
        elif momentum_5 < -0.01 and momentum_10 < -0.015 and sma_5 < sma_10 < sma_20 and rsi_value < 30:
            return MomentumState.STRONG_BEARISH
        elif momentum_5 < -0.005 and sma_5 < sma_10 and rsi_value < 50:
            return MomentumState.BEARISH
        else:
            return MomentumState.NEUTRAL
    
    def _calculate_momentum_score(self, momentum: float, rsi: float, 
                                volume_ratio: float, tick_reading: float) -> float:
        """Calculate momentum score"""
        score = 0.0
        
        # Price momentum (0-0.3)
        if abs(momentum) > 0.005:
            score += 0.3
        elif abs(momentum) > 0.003:
            score += 0.2
        elif abs(momentum) > 0.001:
            score += 0.1
        
        # RSI (0-0.2)
        if (momentum > 0 and 60 < rsi < 80) or (momentum < 0 and 20 < rsi < 40):
            score += 0.2
        elif (momentum > 0 and 50 < rsi < 60) or (momentum < 0 and 40 < rsi < 50):
            score += 0.1
        
        # Volume (0-0.2)
        if volume_ratio > 2.0:
            score += 0.2
        elif volume_ratio > 1.5:
            score += 0.15
        elif volume_ratio > 1.2:
            score += 0.1
        
        # Market internals (0-0.3)
        if abs(tick_reading) > 600:
            score += 0.3
        elif abs(tick_reading) > 400:
            score += 0.2
        elif abs(tick_reading) > 200:
            score += 0.1
        
        return min(score, 1.0)
    
    def _find_optimal_strike(self, current_price: float, direction: ScalpDirection) -> float:
        """Find optimal strike for maximum gamma"""
        # For 0DTE, ATM or slightly OTM provides best gamma
        if direction == ScalpDirection.LONG:
            # Slightly OTM call
            strike = math.ceil(current_price)
        else:
            # Slightly OTM put
            strike = math.floor(current_price)
        
        return strike
    
    def _estimate_gamma(self, spot: float, strike: float, option_type: OptionRight) -> float:
        """Estimate gamma for 0DTE option"""
        # Simplified gamma estimation
        moneyness = abs(spot - strike) / spot
        time_to_expiry = 0.02  # Fraction of year for 0DTE
        volatility = 0.15  # Assumed volatility
        
        # Maximum gamma is ATM
        if moneyness < 0.01:  # ATM
            gamma = 1.0
        elif moneyness < 0.02:  # Slightly OTM
            gamma = 0.8
        elif moneyness < 0.03:
            gamma = 0.5
        else:
            gamma = 0.3
        
        # Adjust for time decay
        gamma *= (1 / math.sqrt(time_to_expiry))
        
        return min(gamma, 2.0)
    
    def _calculate_vwap(self, market_data: pd.DataFrame) -> float:
        """Calculate VWAP"""
        typical_price = (market_data['high'] + market_data['low'] + market_data['close']) / 3
        cumulative_tpv = (typical_price * market_data['volume']).cumsum()
        cumulative_volume = market_data['volume'].cumsum()
        
        vwap = cumulative_tpv.iloc[-1] / cumulative_volume.iloc[-1]
        return vwap
    
    def _calculate_atr(self, market_data: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = market_data['high'] - market_data['low']
        high_close = abs(market_data['high'] - market_data['close'].shift())
        low_close = abs(market_data['low'] - market_data['close'].shift())
        
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(period).mean().iloc[-1]
        
        return atr
    
    def _calculate_support_levels(self, market_data: pd.DataFrame, current_price: float) -> List[float]:
        """Calculate nearby support levels"""
        supports = []
        
        # Previous day low
        if len(market_data) > 78:
            prev_low = market_data['low'].iloc[-78:].min()
            if prev_low < current_price:
                supports.append(prev_low)
        
        # Intraday lows
        recent_lows = []
        for i in range(10, min(len(market_data), 50), 10):
            window_low = market_data['low'].iloc[-i:].min()
            if window_low < current_price * 0.995:
                recent_lows.append(window_low)
        
        # Keep unique levels
        supports.extend(recent_lows)
        supports = sorted(list(set(supports)), reverse=True)[:3]
        
        return supports
    
    def _calculate_resistance_levels(self, market_data: pd.DataFrame, current_price: float) -> List[float]:
        """Calculate nearby resistance levels"""
        resistances = []
        
        # Previous day high
        if len(market_data) > 78:
            prev_high = market_data['high'].iloc[-78:].max()
            if prev_high > current_price:
                resistances.append(prev_high)
        
        # Intraday highs
        recent_highs = []
        for i in range(10, min(len(market_data), 50), 10):
            window_high = market_data['high'].iloc[-i:].max()
            if window_high > current_price * 1.005:
                recent_highs.append(window_high)
        
        # Keep unique levels
        resistances.extend(recent_highs)
        resistances = sorted(list(set(resistances)))[:3]
        
        return resistances
    
    def _verify_zero_dte_expiration(self) -> bool:
        """Verify today has 0DTE options"""
        return self.trading_calendar.has_options_expiring(datetime.now().date())
    
    def _calculate_position_size(self, setup: ScalpSetup) -> int:
        """Calculate position size for scalp"""
        # Risk 0.5% of account per trade
        account_size = self.risk_manager.get_account_size()
        risk_per_trade = account_size * 0.005
        
        # Estimate option price
        option_price = abs(setup.entry_price - setup.option_strike) * 0.5
        if option_price < 0.50:
            option_price = 0.50
        
        contracts = int(risk_per_trade / (option_price * 100))
        
        # Limit position size
        return max(1, min(contracts, 20))
    
    def _create_order(self, setup: ScalpSetup, quantity: int):
        """Create order for 0DTE position"""
        action = 'BUY' if setup.direction == ScalpDirection.LONG else 'BUY'
        
        # Use limit order with aggressive pricing for quick fill
        limit_price = self._get_aggressive_limit_price(setup)
        
        return self.ib_client.create_limit_order(action, quantity, limit_price)
    
    def _get_aggressive_limit_price(self, setup: ScalpSetup) -> float:
        """Get aggressive limit price for quick fill"""
        # Would get actual bid/ask and cross spread slightly
        return 0.0  # Placeholder - use market order
    
    def _get_current_price(self) -> float:
        """Get current SPY price"""
        # Would get from real-time data feed
        return 450.0  # Placeholder
    
    def _calculate_position_pnl(self, position: Dict, current_price: float) -> float:
        """Calculate position P&L"""
        # Simplified P&L calculation
        signal = position['signal']
        setup = signal.setup
        
        # Estimate option price change
        price_move = current_price - setup.entry_price
        
        if setup.direction == ScalpDirection.LONG:
            option_pnl = price_move * setup.gamma
        else:
            option_pnl = -price_move * setup.gamma
        
        return option_pnl * position['position_size'] * 100
    
    def _check_adverse_conditions(self, setup: ScalpSetup, current_price: float) -> bool:
        """Check for adverse market conditions"""
        if not self.market_context:
            return False
        
        # Check momentum reversal
        if setup.direction == ScalpDirection.LONG:
            if self.market_context.momentum_state in [MomentumState.BEARISH, MomentumState.STRONG_BEARISH]:
                return True
        else:
            if self.market_context.momentum_state in [MomentumState.BULLISH, MomentumState.STRONG_BULLISH]:
                return True
        
        return False
    
    def _update_day_stats(self, trade_result: Dict[str, Any]) -> None:
        """Update daily statistics"""
        pnl = trade_result.get('pnl', 0)
        self.day_stats.daily_pnl += pnl
        
        if pnl > 0:
            self.day_stats.winning_trades += 1
            self.day_stats.consecutive_losses = 0
            self.day_stats.best_trade = max(self.day_stats.best_trade, pnl)
        else:
            self.day_stats.losing_trades += 1
            self.day_stats.consecutive_losses += 1
            self.day_stats.worst_trade = min(self.day_stats.worst_trade, pnl)
        
        # Update average hold time
        hold_time = trade_result.get('hold_time', 0)
        self.day_stats.avg_hold_time = (
            (self.day_stats.avg_hold_time * (self.day_stats.trades_taken - 1) + hold_time) /
            self.day_stats.trades_taken
        )
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        self.day_stats = DayStats()
        self.last_trade_time = None
        self.logger.info("Daily statistics reset")
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy performance statistics"""
        return {
            'strategy': 'ZeroDTE',
            'daily_stats': {
                'trades': self.day_stats.trades_taken,
                'wins': self.day_stats.winning_trades,
                'losses': self.day_stats.losing_trades,
                'win_rate': self.day_stats.winning_trades / self.day_stats.trades_taken if self.day_stats.trades_taken > 0 else 0,
                'daily_pnl': self.day_stats.daily_pnl,
                'best_trade': self.day_stats.best_trade,
                'worst_trade': self.day_stats.worst_trade,
                'avg_hold_time': self.day_stats.avg_hold_time
            },
            'active_positions': len([p for p in self.active_positions.values() if p['status'] != 'closed']),
            'market_context': {
                'phase': self.market_context.phase.name if self.market_context else 'UNKNOWN',
                'momentum': self.market_context.momentum_state.name if self.market_context else 'UNKNOWN'
            }
        }

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_zero_dte_strategy(config: Dict[str, Any]) -> ZeroDTEStrategy:
    """Factory function to create ZeroDTE strategy instance."""
    return ZeroDTEStrategy(config)