#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD03_CreditSpread.py
Group: D (Trading Strategies)
Purpose: Bull put/Bear call spread strategies

Description:
    This module implements credit spread strategies including bull put spreads
    and bear call spreads. These strategies profit from time decay and are
    suitable for moderately bullish or bearish market conditions.

Author: Mohamed Talib
Date: 2025-05-29
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
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

from SpyderD_Strategies.SpyderD01_BaseStrategy import (
    BaseStrategy, TradingSignal, SignalStrength, StrategyPosition
)
    
from SpyderB_Broker.SpyderB06_ContractBuilder import (
    OptionContract, OptionSearchCriteria
)
from SpyderF_Analysis.SpyderF01_Indicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator
from SpyderA_Core.SpyderA05_EventManager import EventManager
from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
MIN_PREMIUM_COLLECTED = 0.50  # Minimum credit to collect
MAX_SPREAD_WIDTH = 5.0  # Maximum spread width in dollars
MIN_PROBABILITY_PROFIT = 0.65  # Minimum probability of profit
MAX_DAYS_TO_EXPIRY = 45  # Maximum DTE
MIN_DAYS_TO_EXPIRY = 20  # Minimum DTE

# Delta targets
BULL_PUT_SHORT_DELTA = -0.30  # Short put delta target
BULL_PUT_LONG_DELTA = -0.15   # Long put delta target
BEAR_CALL_SHORT_DELTA = 0.30   # Short call delta target
BEAR_CALL_LONG_DELTA = 0.15    # Long call delta target

# Risk parameters
MAX_RISK_REWARD_RATIO = 3.0  # Maximum risk to reward ratio
MIN_CREDIT_TO_WIDTH_RATIO = 0.25  # Minimum credit/width ratio

# Technical indicators
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
VOLUME_THRESHOLD = 1.5  # Volume relative to average

# ==============================================================================
# ENUMS
# ==============================================================================
class SpreadType(Enum):
    """Credit spread types"""
    BULL_PUT = auto()
    BEAR_CALL = auto()

class MarketCondition(Enum):
    """Market condition classification"""
    STRONGLY_BULLISH = auto()
    MODERATELY_BULLISH = auto()
    NEUTRAL = auto()
    MODERATELY_BEARISH = auto()
    STRONGLY_BEARISH = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CreditSpread:
    """Credit spread structure"""
    spread_type: SpreadType
    short_strike: float
    long_strike: float
    expiration: datetime
    premium_collected: float
    max_loss: float
    max_profit: float
    probability_profit: float
    risk_reward_ratio: float
    delta_neutral: float
    theta: float
    breakeven: float

@dataclass
class SpreadAnalysis:
    """Spread analysis results"""
    recommended_spreads: List[CreditSpread]
    market_condition: MarketCondition
    trend_strength: float
    volatility_rank: float
    support_levels: List[float]
    resistance_levels: List[float]
    entry_score: float

# ==============================================================================
# CREDIT SPREAD STRATEGY CLASS
# ==============================================================================
class CreditSpreadStrategy(BaseStrategy):
    """
    Credit spread strategy implementation.
    
    Implements bull put spreads and bear call spreads based on:
    - Market trend and momentum
    - Support/resistance levels
    - Volatility conditions
    - Technical indicators
    """
    
    def __init__(
        self,
        event_manager: EventManager,
        risk_profile: RiskProfile,
        config: Dict[str, Any]
    ):
        """
        Initialize credit spread strategy.
        
        Args:
            event_manager: Event manager instance
            risk_profile: Risk profile
            config: Strategy configuration
        """
        super().__init__(
            name="CreditSpread",
            event_manager=event_manager,
            risk_profile=risk_profile,
            config=config
        )
        
        # Strategy specific configuration
        self.max_spreads = config.get('max_spreads', 3)
        self.spread_width = config.get('spread_width', 5.0)
        self.target_premium = config.get('target_premium', 1.0)
        self.use_bull_puts = config.get('use_bull_puts', True)
        self.use_bear_calls = config.get('use_bear_calls', True)
        
        # Greeks calculator
        self.greeks_calculator = GreeksCalculator()
        
        # Market analysis
        self.market_condition = MarketCondition.NEUTRAL
        self.support_levels = []
        self.resistance_levels = []
        self.volatility_rank = 0.5
        
        self.logger.info("CreditSpreadStrategy initialized")
    
    # ==========================================================================
    # SIGNAL GENERATION
    # ==========================================================================
    def generate_signals(self, market_data: pd.DataFrame) -> List[TradingSignal]:
        """
        Generate credit spread signals.
        
        Args:
            market_data: Market data DataFrame
            
        Returns:
            List of trading signals
        """
        signals = []
        
        if len(market_data) < 100:
            return signals
        
        try:
            # Analyze market conditions
            analysis = self._analyze_market(market_data)
            
            # Check for bull put spread opportunities
            if self.use_bull_puts and self._should_enter_bull_put(analysis):
                bull_put_signal = self._create_bull_put_signal(
                    market_data,
                    analysis
                )
                if bull_put_signal:
                    signals.append(bull_put_signal)
            
            # Check for bear call spread opportunities
            if self.use_bear_calls and self._should_enter_bear_call(analysis):
                bear_call_signal = self._create_bear_call_signal(
                    market_data,
                    analysis
                )
                if bear_call_signal:
                    signals.append(bear_call_signal)
            
        except Exception as e:
            self.logger.error(f"Error generating signals: {e}")
            self.error_handler.handle_error(e, self.name)
        
        return signals
    
    def _analyze_market(self, market_data: pd.DataFrame) -> SpreadAnalysis:
        """Analyze market conditions"""
        current_price = market_data['close'].iloc[-1]
        
        # Calculate technical indicators
        rsi = self.indicators.rsi(market_data['close'], period=14).iloc[-1]
        macd_line, signal_line, _ = self.indicators.macd(market_data['close'])
        
        # Calculate trend
        sma_20 = market_data['close'].rolling(20).mean().iloc[-1]
        sma_50 = market_data['close'].rolling(50).mean().iloc[-1]
        ema_9 = market_data['close'].ewm(span=9).mean().iloc[-1]
        
        # Determine market condition
        if current_price > sma_20 > sma_50 and rsi > 50:
            if rsi > 70:
                self.market_condition = MarketCondition.STRONGLY_BULLISH
            else:
                self.market_condition = MarketCondition.MODERATELY_BULLISH
        elif current_price < sma_20 < sma_50 and rsi < 50:
            if rsi < 30:
                self.market_condition = MarketCondition.STRONGLY_BEARISH
            else:
                self.market_condition = MarketCondition.MODERATELY_BEARISH
        else:
            self.market_condition = MarketCondition.NEUTRAL
        
        # Calculate support and resistance
        self.support_levels = self._calculate_support_levels(market_data)
        self.resistance_levels = self._calculate_resistance_levels(market_data)
        
        # Calculate volatility rank
        returns = market_data['close'].pct_change()
        current_vol = returns.rolling(20).std().iloc[-1]
        vol_series = returns.rolling(20).std().dropna()
        self.volatility_rank = (vol_series < current_vol).sum() / len(vol_series)
        
        # Calculate trend strength
        adx = self.indicators.adx(
            market_data['high'],
            market_data['low'],
            market_data['close']
        ).iloc[-1]
        trend_strength = adx / 100.0
        
        # Calculate entry score
        entry_score = self._calculate_entry_score(
            rsi, macd_line.iloc[-1], signal_line.iloc[-1],
            trend_strength, self.volatility_rank
        )
        
        return SpreadAnalysis(
            recommended_spreads=[],
            market_condition=self.market_condition,
            trend_strength=trend_strength,
            volatility_rank=self.volatility_rank,
            support_levels=self.support_levels,
            resistance_levels=self.resistance_levels,
            entry_score=entry_score
        )
    
    def _should_enter_bull_put(self, analysis: SpreadAnalysis) -> bool:
        """Check if should enter bull put spread"""
        # Good for moderately bullish conditions
        if analysis.market_condition in [
            MarketCondition.MODERATELY_BULLISH,
            MarketCondition.NEUTRAL
        ]:
            # Check if near support
            current_price = self.current_price
            for support in analysis.support_levels:
                if abs(current_price - support) / current_price < 0.02:
                    return True
            
            # Check entry score
            return analysis.entry_score > 0.6
        
        return False
    
    def _should_enter_bear_call(self, analysis: SpreadAnalysis) -> bool:
        """Check if should enter bear call spread"""
        # Good for moderately bearish conditions
        if analysis.market_condition in [
            MarketCondition.MODERATELY_BEARISH,
            MarketCondition.NEUTRAL
        ]:
            # Check if near resistance
            current_price = self.current_price
            for resistance in analysis.resistance_levels:
                if abs(current_price - resistance) / current_price < 0.02:
                    return True
            
            # Check entry score
            return analysis.entry_score > 0.6
        
        return False
    
    # ==========================================================================
    # SPREAD CREATION
    # ==========================================================================
    def _create_bull_put_signal(
        self,
        market_data: pd.DataFrame,
        analysis: SpreadAnalysis
    ) -> Optional[TradingSignal]:
        """Create bull put spread signal"""
        current_price = market_data['close'].iloc[-1]
        
        # Find suitable strikes
        short_strike = self._find_strike_by_delta(
            current_price,
            BULL_PUT_SHORT_DELTA,
            OptionRight.PUT
        )
        
        long_strike = short_strike - self.spread_width
        
        # Validate spread
        spread = self._create_spread(
            SpreadType.BULL_PUT,
            short_strike,
            long_strike,
            current_price
        )
        
        if not self._validate_spread(spread):
            return None
        
        # Create contracts
        expiration = datetime.now() + timedelta(days=30)
        
        short_contract = OptionContract(
            symbol="SPY",
            strike=short_strike,
            expiration=expiration,
            right=OptionRight.PUT,
            multiplier=100
        )
        
        long_contract = OptionContract(
            symbol="SPY",
            strike=long_strike,
            expiration=expiration,
            right=OptionRight.PUT,
            multiplier=100
        )
        
        # Create signal
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            strategy_name=self.name,
            signal_type=SignalType.CREDIT_SPREAD,
            strength=self._calculate_signal_strength(analysis, spread),
            contracts=[short_contract, long_contract],
            entry_price=current_price,
            stop_loss=short_strike,  # Max loss at short strike
            confidence=spread.probability_profit,
            metadata={
                'spread_type': 'bull_put',
                'premium': spread.premium_collected,
                'max_loss': spread.max_loss,
                'probability_profit': spread.probability_profit,
                'breakeven': spread.breakeven
            }
        )
        
        return signal
    
    def _create_bear_call_signal(
        self,
        market_data: pd.DataFrame,
        analysis: SpreadAnalysis
    ) -> Optional[TradingSignal]:
        """Create bear call spread signal"""
        current_price = market_data['close'].iloc[-1]
        
        # Find suitable strikes
        short_strike = self._find_strike_by_delta(
            current_price,
            BEAR_CALL_SHORT_DELTA,
            OptionRight.CALL
        )
        
        long_strike = short_strike + self.spread_width
        
        # Validate spread
        spread = self._create_spread(
            SpreadType.BEAR_CALL,
            short_strike,
            long_strike,
            current_price
        )
        
        if not self._validate_spread(spread):
            return None
        
        # Create contracts
        expiration = datetime.now() + timedelta(days=30)
        
        short_contract = OptionContract(
            symbol="SPY",
            strike=short_strike,
            expiration=expiration,
            right=OptionRight.CALL,
            multiplier=100
        )
        
        long_contract = OptionContract(
            symbol="SPY",
            strike=long_strike,
            expiration=expiration,
            right=OptionRight.CALL,
            multiplier=100
        )
        
        # Create signal
        signal = TradingSignal(
            signal_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            strategy_name=self.name,
            signal_type=SignalType.CREDIT_SPREAD,
            strength=self._calculate_signal_strength(analysis, spread),
            contracts=[short_contract, long_contract],
            entry_price=current_price,
            stop_loss=short_strike,  # Max loss at short strike
            confidence=spread.probability_profit,
            metadata={
                'spread_type': 'bear_call',
                'premium': spread.premium_collected,
                'max_loss': spread.max_loss,
                'probability_profit': spread.probability_profit,
                'breakeven': spread.breakeven
            }
        )
        
        return signal
    
    def _create_spread(
        self,
        spread_type: SpreadType,
        short_strike: float,
        long_strike: float,
        current_price: float
    ) -> CreditSpread:
        """Create credit spread structure"""
        # Calculate premium (simplified - would use actual option prices)
        volatility = 0.15  # Would get from market
        time_to_expiry = 30 / 365.0
        risk_free_rate = 0.05
        
        # Calculate option prices
        if spread_type == SpreadType.BULL_PUT:
            short_price = self.greeks_calculator.black_scholes_price(
                current_price, short_strike, time_to_expiry,
                risk_free_rate, volatility, OptionType.PUT
            )
            long_price = self.greeks_calculator.black_scholes_price(
                current_price, long_strike, time_to_expiry,
                risk_free_rate, volatility, OptionType.PUT
            )
        else:
            short_price = self.greeks_calculator.black_scholes_price(
                current_price, short_strike, time_to_expiry,
                risk_free_rate, volatility, OptionType.CALL
            )
            long_price = self.greeks_calculator.black_scholes_price(
                current_price, long_strike, time_to_expiry,
                risk_free_rate, volatility, OptionType.CALL
            )
        
        premium_collected = short_price - long_price
        spread_width = abs(short_strike - long_strike)
        max_loss = (spread_width - premium_collected) * 100
        max_profit = premium_collected * 100
        
        # Calculate probability of profit
        if spread_type == SpreadType.BULL_PUT:
            breakeven = short_strike - premium_collected
            probability_profit = self._calculate_probability_above(
                breakeven, current_price, volatility, time_to_expiry
            )
        else:
            breakeven = short_strike + premium_collected
            probability_profit = self._calculate_probability_below(
                breakeven, current_price, volatility, time_to_expiry
            )
        
        # Calculate Greeks
        delta_neutral = self._calculate_spread_delta(
            spread_type, short_strike, long_strike,
            current_price, volatility, time_to_expiry
        )
        
        theta = self._calculate_spread_theta(
            spread_type, short_strike, long_strike,
            current_price, volatility, time_to_expiry
        )
        
        return CreditSpread(
            spread_type=spread_type,
            short_strike=short_strike,
            long_strike=long_strike,
            expiration=datetime.now() + timedelta(days=30),
            premium_collected=premium_collected,
            max_loss=max_loss,
            max_profit=max_profit,
            probability_profit=probability_profit,
            risk_reward_ratio=max_loss / max_profit if max_profit > 0 else float('inf'),
            delta_neutral=delta_neutral,
            theta=theta,
            breakeven=breakeven
        )
    
    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================
    def should_enter_position(self, signal: TradingSignal) -> bool:
        """Check if position should be entered"""
        # Check existing positions
        current_spreads = sum(
            1 for p in self.positions.values()
            if p.metadata.get('strategy_type') == 'credit_spread'
        )
        
        if current_spreads >= self.max_spreads:
            return False
        
        # Check market conditions haven't changed significantly
        if signal.confidence < MIN_PROBABILITY_PROFIT:
            return False
        
        # Check risk/reward
        max_loss = signal.metadata.get('max_loss', 0)
        max_profit = signal.metadata.get('premium', 0) * 100
        
        if max_profit > 0:
            risk_reward = max_loss / max_profit
            if risk_reward > MAX_RISK_REWARD_RATIO:
                return False
        
        return True
    
    def should_exit_position(self, position: StrategyPosition) -> bool:
        """Check if position should be exited"""
        # Get position details
        entry_time = position.entry_time
        time_held = (datetime.now() - entry_time).days
        
        # Exit if approaching expiration
        if time_held > 25:  # Exit 5 days before expiry
            return True
        
        # Exit if profit target reached (50% of max profit)
        max_profit = position.metadata.get('premium', 0) * 100
        if position.unrealized_pnl >= max_profit * 0.5:
            return True
        
        # Exit if loss exceeds 2x premium collected
        if position.unrealized_pnl <= -max_profit * 2:
            return True
        
        # Check if spread is being tested
        spread_type = position.metadata.get('spread_type')
        if spread_type == 'bull_put':
            short_strike = position.metadata.get('short_strike')
            if self.current_price < short_strike * 1.01:
                return True
        elif spread_type == 'bear_call':
            short_strike = position.metadata.get('short_strike')
            if self.current_price > short_strike * 0.99:
                return True
        
        return False
    
    def calculate_position_size(self, signal: TradingSignal) -> int:
        """Calculate position size for spread"""
        # Risk per spread
        max_loss = signal.metadata.get('max_loss', 0)
        
        if max_loss <= 0:
            return 0
        
        # Calculate based on risk allocation
        max_risk_per_trade = self.risk_profile.max_loss_per_trade * self.risk_profile.account_size
        position_size = int(max_risk_per_trade / max_loss)
        
        # Apply limits
        return max(1, min(position_size, 10))
    
    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _find_strike_by_delta(
        self,
        current_price: float,
        target_delta: float,
        option_type: OptionRight
    ) -> float:
        """Find strike price for target delta"""
        # Simplified - would use actual option chain
        volatility = 0.15
        time_to_expiry = 30 / 365.0
        
        # Use approximation
        if option_type == OptionRight.PUT:
            strike = current_price * (1 + target_delta * volatility * math.sqrt(time_to_expiry))
        else:
            strike = current_price * (1 - target_delta * volatility * math.sqrt(time_to_expiry))
        
        # Round to nearest dollar
        return round(strike)
    
    def _validate_spread(self, spread: CreditSpread) -> bool:
        """Validate credit spread"""
        # Check minimum premium
        if spread.premium_collected < MIN_PREMIUM_COLLECTED:
            return False
        
        # Check probability of profit
        if spread.probability_profit < MIN_PROBABILITY_PROFIT:
            return False
        
        # Check risk/reward ratio
        if spread.risk_reward_ratio > MAX_RISK_REWARD_RATIO:
            return False
        
        # Check credit to width ratio
        spread_width = abs(spread.short_strike - spread.long_strike)
        credit_ratio = spread.premium_collected / spread_width
        if credit_ratio < MIN_CREDIT_TO_WIDTH_RATIO:
            return False
        
        return True
    
    def _calculate_signal_strength(
        self,
        analysis: SpreadAnalysis,
        spread: CreditSpread
    ) -> SignalStrength:
        """Calculate signal strength"""
        score = 0.0
        
        # Probability of profit
        if spread.probability_profit > 0.8:
            score += 0.3
        elif spread.probability_profit > 0.7:
            score += 0.2
        else:
            score += 0.1
        
        # Risk/reward ratio
        if spread.risk_reward_ratio < 1.5:
            score += 0.3
        elif spread.risk_reward_ratio < 2.0:
            score += 0.2
        else:
            score += 0.1
        
        # Market condition alignment
        if (spread.spread_type == SpreadType.BULL_PUT and 
            analysis.market_condition == MarketCondition.MODERATELY_BULLISH):
            score += 0.2
        elif (spread.spread_type == SpreadType.BEAR_CALL and 
              analysis.market_condition == MarketCondition.MODERATELY_BEARISH):
            score += 0.2
        else:
            score += 0.1
        
        # Volatility rank
        if analysis.volatility_rank > 0.5:
            score += 0.2
        else:
            score += 0.1
        
        # Convert to signal strength
        if score >= 0.8:
            return SignalStrength.VERY_STRONG
        elif score >= 0.6:
            return SignalStrength.STRONG
        elif score >= 0.4:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK
    
    def _calculate_support_levels(self, market_data: pd.DataFrame) -> List[float]:
        """Calculate support levels"""
        lows = market_data['low'].rolling(20).min()
        supports = []
        
        for i in range(20, len(lows) - 20):
            if lows.iloc[i] == min(lows.iloc[i-20:i+20]):
                supports.append(lows.iloc[i])
        
        # Remove duplicates and sort
        supports = sorted(list(set(supports)))[-3:]  # Keep top 3
        
        return supports
    
    def _calculate_resistance_levels(self, market_data: pd.DataFrame) -> List[float]:
        """Calculate resistance levels"""
        highs = market_data['high'].rolling(20).max()
        resistances = []
        
        for i in range(20, len(highs) - 20):
            if highs.iloc[i] == max(highs.iloc[i-20:i+20]):
                resistances.append(highs.iloc[i])
        
        # Remove duplicates and sort
        resistances = sorted(list(set(resistances)))[:3]  # Keep bottom 3
        
        return resistances
    
    def _calculate_entry_score(
        self,
        rsi: float,
        macd_line: float,
        signal_line: float,
        trend_strength: float,
        volatility_rank: float
    ) -> float:
        """Calculate entry score"""
        score = 0.0
        
        # RSI conditions
        if 30 < rsi < 70:
            score += 0.25
        
        # MACD conditions
        if macd_line > signal_line:
            score += 0.25
        
        # Trend strength
        score += trend_strength * 0.25
        
        # Volatility rank
        score += volatility_rank * 0.25
        
        return score
    
    def _calculate_probability_above(
        self,
        target_price: float,
        current_price: float,
        volatility: float,
        time: float
    ) -> float:
        """Calculate probability price stays above target"""
        from scipy.stats import norm
        
        drift = 0.0  # Assume no drift
        std_dev = volatility * math.sqrt(time)
        z_score = (math.log(target_price / current_price) - drift * time) / std_dev
        
        return norm.cdf(-z_score)
    
    def _calculate_probability_below(
        self,
        target_price: float,
        current_price: float,
        volatility: float,
        time: float
    ) -> float:
        """Calculate probability price stays below target"""
        from scipy.stats import norm
        
        drift = 0.0  # Assume no drift
        std_dev = volatility * math.sqrt(time)
        z_score = (math.log(target_price / current_price) - drift * time) / std_dev
        
        return norm.cdf(z_score)
    
    def _calculate_spread_delta(
        self,
        spread_type: SpreadType,
        short_strike: float,
        long_strike: float,
        current_price: float,
        volatility: float,
        time: float
    ) -> float:
        """Calculate net delta of spread"""
        risk_free_rate = 0.05
        
        if spread_type == SpreadType.BULL_PUT:
            short_delta = self.greeks_calculator.delta(
                current_price, short_strike, time,
                risk_free_rate, volatility, OptionType.PUT
            )
            long_delta = self.greeks_calculator.delta(
                current_price, long_strike, time,
                risk_free_rate, volatility, OptionType.PUT
            )
        else:
            short_delta = self.greeks_calculator.delta(
                current_price, short_strike, time,
                risk_free_rate, volatility, OptionType.CALL
            )
            long_delta = self.greeks_calculator.delta(
                current_price, long_strike, time,
                risk_free_rate, volatility, OptionType.CALL
            )
        
        # Net delta (short - long)
        return short_delta - long_delta
    
    def _calculate_spread_theta(
        self,
        spread_type: SpreadType,
        short_strike: float,
        long_strike: float,
        current_price: float,
        volatility: float,
        time: float
    ) -> float:
        """Calculate net theta of spread"""
        risk_free_rate = 0.05
        
        if spread_type == SpreadType.BULL_PUT:
            short_theta = self.greeks_calculator.theta(
                current_price, short_strike, time,
                risk_free_rate, volatility, OptionType.PUT
            )
            long_theta = self.greeks_calculator.theta(
                current_price, long_strike, time,
                risk_free_rate, volatility, OptionType.PUT
            )
        else:
            short_theta = self.greeks_calculator.theta(
                current_price, short_strike, time,
                risk_free_rate, volatility, OptionType.CALL
            )
            long_theta = self.greeks_calculator.theta(
                current_price, long_strike, time,
                risk_free_rate, volatility, OptionType.CALL
            )
        
        # Net theta (short - long)
        return short_theta - long_theta

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test credit spread strategy
    from SpyderA_Core.SpyderA05_EventManager import EventManager
    from SpyderE_Risk.SpyderE01_RiskManager import RiskProfile
    
    # Initialize components
    event_manager = EventManager()
    risk_profile = RiskProfile(
        account_size=100000,
        max_position_size=0.02,
        max_portfolio_risk=0.06,
        max_loss_per_trade=0.01
    )
    
    # Create strategy
    strategy = CreditSpreadStrategy(
        event_manager=event_manager,
        risk_profile=risk_profile,
        config={
            'max_spreads': 3,
            'spread_width': 5.0,
            'target_premium': 1.0,
            'use_bull_puts': True,
            'use_bear_calls': True
        }
    )
    
    # Start strategy
    strategy.start()
    
    # Create sample market data
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    base_price = 450  # SPY price
    trend = np.linspace(0, 5, 100)  # Slight uptrend
    noise = np.random.randn(100) * 2
    prices = base_price + trend + noise
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': prices + np.random.randn(100) * 0.5,
        'high': prices + abs(np.random.randn(100)),
        'low': prices - abs(np.random.randn(100)),
        'close': prices,
        'volume': np.random.randint(50000000, 150000000, 100)
    })
    
    # Process market data
    signals = strategy.generate_signals(market_data)
    
    # Print results
    print(f"Strategy: {strategy.name}")
    print(f"Market Condition: {strategy.market_condition}")
    print(f"Volatility Rank: {strategy.volatility_rank:.2f}")
    print(f"Signals Generated: {len(signals)}")
    
    for signal in signals:
        print(f"\nSignal Type: {signal.metadata.get('spread_type')}")
        print(f"Strength: {signal.strength}")
        print(f"Premium: ${signal.metadata.get('premium', 0):.2f}")
        print(f"Max Loss: ${signal.metadata.get('max_loss', 0):.2f}")
        print(f"Probability of Profit: {signal.metadata.get('probability_profit', 0):.2%}")
        print(f"Breakeven: ${signal.metadata.get('breakeven', 0):.2f}")
    
    # Stop strategy
    strategy.stop()
