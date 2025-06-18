#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD07_BearCallSpread.py
Group: D (Trading Strategies)
Purpose: Directional bear call spread strategy

Description:
    This module implements a directional bear call spread strategy for SPY options.
    The strategy sells out-of-the-money call spreads when bearish market conditions
    are detected. It mirrors the bull put spread logic but for bearish scenarios,
    incorporating volatility regime analysis, optimal entry timing, and research-driven
    profit targets. The strategy collects premium while limiting risk through the
    protective long call.

Author: Mohamed Talib
Date: 2025-06-01
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy
from SpyderC_MarketData.SpyderC04_MarketInternals import MarketInternals
from SpyderE_RiskMgmt.SpyderE01_RiskManager import get_risk_manager
from SpyderE_RiskMgmt.SpyderE02_PositionSizer import get_position_sizer
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderU_Utilities.SpyderU07_Constants import (
    BEAR_CALL_SPREAD_PROFIT_TARGET,
    BEAR_CALL_SPREAD_STOP_LOSS,
    MIN_IVR_FOR_SPREADS,
    MAX_SPREAD_WIDTH,
    MIN_CREDIT_RATIO,
    OPTIMAL_ENTRY_START,
    OPTIMAL_ENTRY_END,
    TIME_BASED_EXIT
)
from SpyderU_Utilities.SpyderU11_FeatureFlags import get_feature_flags

# ==============================================================================
# CONSTANTS
# ==============================================================================
STRATEGY_NAME = "BearCallSpread"
DEFAULT_DELTA_SHORT = 0.30   # Short call delta (positive for calls)
DEFAULT_DELTA_LONG = 0.20    # Long call delta
MIN_DAYS_TO_EXPIRY = 0       # Allow 0DTE
MAX_DAYS_TO_EXPIRY = 7       # Max 7 DTE
MIN_PREMIUM_COLLECTED = 0.50  # Minimum $0.50 credit per spread
MAX_CONTRACTS = 10           # Maximum contracts per trade

# Bear market indicators
BEAR_TREND_MA_DAYS = 10      # Moving average period
BEAR_RSI_THRESHOLD = 60      # RSI below this for bear signal
BEAR_VWAP_TOLERANCE = 0.002  # Price below VWAP + 0.2%

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class BearCallSpreadSignal:
    """Signal data for bear call spread entry."""
    timestamp: datetime
    underlying_price: float
    short_strike: float
    long_strike: float
    expiration: datetime
    credit_received: float
    spread_width: float
    probability_profit: float
    implied_volatility: float
    delta_short: float
    delta_long: float
    contracts: int
    max_profit: float
    max_loss: float
    breakeven: float
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

class MarketRegime(Enum):
    """Market regime classification for strategy selection."""
    STRONG_BULL = "strong_bull"
    BULL = "bull"
    NEUTRAL = "neutral"
    BEAR = "bear"
    STRONG_BEAR = "strong_bear"

# ==============================================================================
# BEAR CALL SPREAD STRATEGY
# ==============================================================================
class BearCallSpreadStrategy(BaseStrategy):
    """
    Bear call spread strategy implementation.
    
    This strategy sells out-of-the-money call spreads when:
    - Market shows bearish characteristics
    - Volatility regime is favorable
    - Entry timing is optimal (10:15-11:40 AM)
    - Risk/reward meets minimum thresholds
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize bear call spread strategy."""
        super().__init__(config)
        
        # Strategy configuration
        self.strategy_name = STRATEGY_NAME
        self.delta_short = config.get('delta_short', DEFAULT_DELTA_SHORT)
        self.delta_long = config.get('delta_long', DEFAULT_DELTA_LONG)
        self.min_credit_ratio = config.get('min_credit_ratio', MIN_CREDIT_RATIO)
        self.profit_target = config.get('profit_target', BEAR_CALL_SPREAD_PROFIT_TARGET)
        self.stop_loss = config.get('stop_loss', BEAR_CALL_SPREAD_STOP_LOSS)
        
        # Risk management
        self.risk_manager = get_risk_manager()
        self.position_sizer = get_position_sizer()
        
        # Market analysis
        self.market_internals = MarketInternals()
        
        # Feature flags
        self.feature_flags = get_feature_flags()
        
        # Performance tracking
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.open_positions = {}
        
        self.logger.info(f"Bear call spread strategy initialized with delta {self.delta_short}/{self.delta_long}")
    
    def analyze_market_regime(self, market_data: Dict[str, Any]) -> MarketRegime:
        """
        Analyze current market regime for bear call spread suitability.
        
        Args:
            market_data: Current market data
            
        Returns:
            MarketRegime classification
        """
        try:
            price = market_data.get('last_price', 0)
            
            # Get technical indicators
            sma_10 = market_data.get('sma_10', price)
            sma_20 = market_data.get('sma_20', price)
            rsi = market_data.get('rsi', 50)
            vwap = market_data.get('vwap', price)
            
            # Bear market scoring (inverse of bull scoring)
            bear_score = 0
            
            # Price below moving averages
            if price < sma_10:
                bear_score += 2
            if price < sma_20:
                bear_score += 1
            
            # RSI not overbought
            if rsi < BEAR_RSI_THRESHOLD:
                bear_score += 2
            if rsi < 40:
                bear_score += 1
            
            # Price near or below VWAP
            vwap_diff = (price - vwap) / vwap
            if vwap_diff < BEAR_VWAP_TOLERANCE:
                bear_score += 2
            
            # Negative trend strength
            trend_strength = (sma_10 - sma_20) / sma_20
            if trend_strength < -0.002:  # 0.2% below
                bear_score += 2
            
            # Classify regime (inverse of bull classification)
            if bear_score >= 7:
                return MarketRegime.STRONG_BEAR
            elif bear_score >= 5:
                return MarketRegime.BEAR
            elif bear_score >= 3:
                return MarketRegime.NEUTRAL
            elif bear_score >= 1:
                return MarketRegime.BULL
            else:
                return MarketRegime.STRONG_BULL
                
        except Exception as e:
            self.logger.error(f"Error analyzing market regime: {e}")
            return MarketRegime.NEUTRAL
    
    def find_optimal_strikes(self, 
                           options_chain: pd.DataFrame,
                           underlying_price: float,
                           expiration: datetime) -> Optional[Tuple[float, float]]:
        """
        Find optimal strike prices for bear call spread.
        
        Args:
            options_chain: Available options
            underlying_price: Current SPY price
            expiration: Target expiration
            
        Returns:
            Tuple of (short_strike, long_strike) or None
        """
        try:
            # Filter for calls at target expiration
            calls = options_chain[
                (options_chain['type'] == 'CALL') &
                (options_chain['expiration'] == expiration) &
                (options_chain['strike'] > underlying_price)
            ].sort_values('strike', ascending=True)
            
            if len(calls) < 2:
                return None
            
            # Find strikes near target deltas
            short_strike = None
            long_strike = None
            
            for _, option in calls.iterrows():
                delta = option.get('delta', 0)
                
                # Find short strike near target delta
                if short_strike is None and abs(delta - self.delta_short) < 0.05:
                    short_strike = option['strike']
                
                # Find long strike near target delta
                elif short_strike and abs(delta - self.delta_long) < 0.05:
                    long_strike = option['strike']
                    break
            
            if not short_strike or not long_strike:
                return None
            
            # Validate spread width
            spread_width = long_strike - short_strike
            if spread_width > MAX_SPREAD_WIDTH or spread_width < 1:
                return None
            
            return (short_strike, long_strike)
            
        except Exception as e:
            self.logger.error(f"Error finding optimal strikes: {e}")
            return None
    
    def calculate_spread_metrics(self,
                               short_strike: float,
                               long_strike: float,
                               credit: float,
                               contracts: int = 1) -> Dict[str, float]:
        """
        Calculate key metrics for bear call spread.
        
        Args:
            short_strike: Short call strike price
            long_strike: Long call strike price
            credit: Net credit received
            contracts: Number of contracts
            
        Returns:
            Dict with spread metrics
        """
        spread_width = long_strike - short_strike
        
        # Calculate P&L metrics
        max_profit = credit * contracts * 100
        max_loss = (spread_width - credit) * contracts * 100
        breakeven = short_strike + credit
        
        # Risk/reward ratios
        risk_reward_ratio = max_loss / max_profit if max_profit > 0 else float('inf')
        credit_ratio = credit / spread_width if spread_width > 0 else 0
        
        # Probability calculations (simplified)
        # In production, use proper options math
        probability_profit = 0.65  # Placeholder
        
        return {
            'max_profit': max_profit,
            'max_loss': max_loss,
            'breakeven': breakeven,
            'risk_reward_ratio': risk_reward_ratio,
            'credit_ratio': credit_ratio,
            'probability_profit': probability_profit,
            'spread_width': spread_width
        }
    
    def generate_entry_signal(self, market_data: Dict[str, Any]) -> Optional[BearCallSpreadSignal]:
        """
        Generate entry signal for bear call spread.
        
        Args:
            market_data: Current market data including options chain
            
        Returns:
            BearCallSpreadSignal if conditions met, None otherwise
        """
        try:
            # Check if strategy is enabled
            if not self.feature_flags.is_enabled('directional_spreads'):
                return None
            
            # Check optimal entry window
            if not DateTimeUtils.is_optimal_entry_time():
                self.logger.debug("Outside optimal entry window for bear call spread")
                return None
            
            # Analyze market regime
            regime = self.analyze_market_regime(market_data)
            if regime not in [MarketRegime.BEAR, MarketRegime.STRONG_BEAR]:
                self.logger.debug(f"Market regime {regime.value} not suitable for bear call spread")
                return None
            
            # Check volatility conditions
            iv_rank = market_data.get('iv_rank', 0)
            if iv_rank < MIN_IVR_FOR_SPREADS:
                self.logger.debug(f"IV rank {iv_rank} too low for spread entry")
                return None
            
            # Get options chain
            options_chain = market_data.get('options_chain')
            if options_chain is None or options_chain.empty:
                return None
            
            underlying_price = market_data.get('last_price', 0)
            
            # Find best expiration (prefer 2-5 DTE)
            best_signal = None
            best_score = 0
            
            expirations = options_chain['expiration'].unique()
            for expiry in expirations:
                dte = (expiry - datetime.now()).days
                
                if dte < MIN_DAYS_TO_EXPIRY or dte > MAX_DAYS_TO_EXPIRY:
                    continue
                
                # Find strikes
                strikes = self.find_optimal_strikes(options_chain, underlying_price, expiry)
                if not strikes:
                    continue
                
                short_strike, long_strike = strikes
                
                # Get option prices
                short_call = options_chain[
                    (options_chain['strike'] == short_strike) &
                    (options_chain['expiration'] == expiry) &
                    (options_chain['type'] == 'CALL')
                ].iloc[0]
                
                long_call = options_chain[
                    (options_chain['strike'] == long_strike) &
                    (options_chain['expiration'] == expiry) &
                    (options_chain['type'] == 'CALL')
                ].iloc[0]
                
                # Calculate net credit
                credit = short_call['bid'] - long_call['ask']
                
                if credit < MIN_PREMIUM_COLLECTED:
                    continue
                
                # Calculate metrics
                metrics = self.calculate_spread_metrics(short_strike, long_strike, credit)
                
                # Check credit ratio
                if metrics['credit_ratio'] < self.min_credit_ratio:
                    continue
                
                # Score this opportunity
                score = self._score_spread_opportunity(market_data, metrics, regime, dte)
                
                if score > best_score:
                    # Determine position size
                    position_size = self.position_sizer.calculate_position_size(
                        strategy=self.strategy_name,
                        signal_strength=min(score / 100, 1.0),
                        market_conditions={'volatility': iv_rank}
                    )
                    
                    contracts = min(position_size.contracts, MAX_CONTRACTS)
                    
                    if contracts > 0:
                        best_signal = BearCallSpreadSignal(
                            timestamp=datetime.now(),
                            underlying_price=underlying_price,
                            short_strike=short_strike,
                            long_strike=long_strike,
                            expiration=expiry,
                            credit_received=credit,
                            spread_width=long_strike - short_strike,
                            probability_profit=metrics['probability_profit'],
                            implied_volatility=short_call.get('implied_volatility', 0),
                            delta_short=short_call.get('delta', self.delta_short),
                            delta_long=long_call.get('delta', self.delta_long),
                            contracts=contracts,
                            max_profit=metrics['max_profit'] * contracts,
                            max_loss=metrics['max_loss'] * contracts,
                            breakeven=metrics['breakeven'],
                            score=score,
                            metadata={
                                'regime': regime.value,
                                'iv_rank': iv_rank,
                                'credit_ratio': metrics['credit_ratio'],
                                'dte': dte
                            }
                        )
                        best_score = score
            
            if best_signal:
                self.logger.info(
                    f"Bear call spread signal: {best_signal.short_strike}/{best_signal.long_strike} "
                    f"for ${best_signal.credit_received:.2f} credit, score: {best_signal.score:.1f}"
                )
            
            return best_signal
            
        except Exception as e:
            self.logger.error(f"Error generating bear call spread signal: {e}")
            self.error_handler.handle_error(e)
            return None
    
    def _score_spread_opportunity(self,
                                market_data: Dict[str, Any],
                                metrics: Dict[str, float],
                                regime: MarketRegime,
                                dte: int) -> float:
        """
        Score a spread opportunity (0-100).
        
        Args:
            market_data: Current market data
            metrics: Spread metrics
            regime: Current market regime
            dte: Days to expiration
            
        Returns:
            float: Score 0-100
        """
        score = 50.0  # Base score
        
        # Market regime bonus
        if regime == MarketRegime.STRONG_BEAR:
            score += 15
        elif regime == MarketRegime.BEAR:
            score += 10
        
        # Credit ratio bonus
        credit_ratio = metrics['credit_ratio']
        if credit_ratio > 0.35:
            score += 15
        elif credit_ratio > 0.30:
            score += 10
        elif credit_ratio > 0.25:
            score += 5
        
        # Probability of profit bonus
        if metrics['probability_profit'] > 0.70:
            score += 10
        elif metrics['probability_profit'] > 0.65:
            score += 5
        
        # IV rank bonus
        iv_rank = market_data.get('iv_rank', 50)
        if iv_rank > 70:
            score += 10
        elif iv_rank > 50:
            score += 5
        
        # DTE preference (2-5 days optimal)
        if 2 <= dte <= 5:
            score += 10
        elif dte == 1:
            score += 5
        
        # Time of day bonus (closer to 10:15 is better)
        current_time = datetime.now().time()
        if time(10, 15) <= current_time <= time(10, 45):
            score += 10
        elif time(10, 45) <= current_time <= time(11, 15):
            score += 5
        
        # Risk/reward penalty
        if metrics['risk_reward_ratio'] > 3:
            score -= 10
        elif metrics['risk_reward_ratio'] > 2:
            score -= 5
        
        # Additional bear market indicators
        vix = market_data.get('vix', 20)
        if vix > 25:  # Higher VIX favors bear strategies
            score += 5
        
        return max(0, min(100, score))
    
    def should_exit_position(self,
                           position: Dict[str, Any],
                           market_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if position should be exited.
        
        Args:
            position: Current position details
            market_data: Current market data
            
        Returns:
            Tuple of (should_exit, reason)
        """
        try:
            # Time-based exit at 12:00 PM
            if DateTimeUtils.should_exit_by_time():
                return True, "time_based_exit"
            
            # Get current spread value
            current_value = self._get_spread_value(position, market_data)
            entry_credit = position['entry_credit']
            
            # Calculate P&L
            pnl = entry_credit - current_value
            pnl_percent = pnl / entry_credit if entry_credit > 0 else 0
            
            # Profit target hit
            if pnl_percent >= self.profit_target:
                return True, f"profit_target_hit_{pnl_percent:.1%}"
            
            # Stop loss hit
            if pnl_percent <= -self.stop_loss:
                return True, f"stop_loss_hit_{pnl_percent:.1%}"
            
            # Check if spread is threatened
            underlying_price = market_data.get('last_price', 0)
            short_strike = position['short_strike']
            
            # Exit if underlying approaches short strike
            if underlying_price >= short_strike * 0.98:  # Within 2% of short strike
                return True, "defensive_exit_strike_threatened"
            
            # DTE-based management
            dte = (position['expiration'] - datetime.now()).days
            if dte == 0 and pnl_percent > 0.25:  # Take 25% profit on expiration day
                return True, "expiration_day_profit"
            
            # Market regime change
            current_regime = self.analyze_market_regime(market_data)
            if current_regime in [MarketRegime.BULL, MarketRegime.STRONG_BULL]:
                if pnl_percent > 0:  # Exit with any profit if regime changes
                    return True, "regime_change_exit"
            
            return False, ""
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            return False, ""
    
    def _get_spread_value(self,
                        position: Dict[str, Any],
                        market_data: Dict[str, Any]) -> float:
        """Calculate current value of spread position."""
        try:
            options_chain = market_data.get('options_chain')
            if options_chain is None:
                return position['entry_credit']  # Return entry value if no data
            
            # Get current prices for the spread
            short_call = options_chain[
                (options_chain['strike'] == position['short_strike']) &
                (options_chain['expiration'] == position['expiration']) &
                (options_chain['type'] == 'CALL')
            ]
            
            long_call = options_chain[
                (options_chain['strike'] == position['long_strike']) &
                (options_chain['expiration'] == position['expiration']) &
                (options_chain['type'] == 'CALL')
            ]
            
            if short_call.empty or long_call.empty:
                return position['entry_credit']
            
            # Calculate current spread value (cost to close)
            current_value = short_call.iloc[0]['ask'] - long_call.iloc[0]['bid']
            return current_value
            
        except Exception as e:
            self.logger.error(f"Error calculating spread value: {e}")
            return position['entry_credit']
    
    def execute(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute bear call spread strategy.
        
        Args:
            market_data: Current market data
            
        Returns:
            Execution results
        """
        results = {
            'signals': [],
            'exits': [],
            'timestamp': datetime.now(),
            'status': 'success'
        }
        
        try:
            # Check existing positions for exits
            for position_id, position in self.open_positions.items():
                should_exit, reason = self.should_exit_position(position, market_data)
                if should_exit:
                    results['exits'].append({
                        'position_id': position_id,
                        'reason': reason,
                        'position': position
                    })
            
            # Check for new entry signals
            if self.trades_today < self._get_max_daily_trades():
                signal = self.generate_entry_signal(market_data)
                if signal:
                    results['signals'].append(signal)
                    self.trades_today += 1
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error executing bear call spread strategy: {e}")
            results['status'] = 'error'
            results['error'] = str(e)
            return results
    
    def _get_max_daily_trades(self) -> int:
        """Get maximum daily trades based on day of week."""
        if DateTimeUtils.is_monday():
            return 3  # More trades on Monday
        else:
            return 2  # Fewer trades other days
    
    def get_strategy_parameters(self) -> Dict[str, Any]:
        """Get current strategy parameters."""
        return {
            'strategy_name': self.strategy_name,
            'delta_short': self.delta_short,
            'delta_long': self.delta_long,
            'min_credit_ratio': self.min_credit_ratio,
            'profit_target': self.profit_target,
            'stop_loss': self.stop_loss,
            'max_daily_trades': self._get_max_daily_trades(),
            'trades_today': self.trades_today,
            'open_positions': len(self.open_positions),
            'feature_enabled': self.feature_flags.is_enabled('directional_spreads')
        }
