#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD06_BullPutSpread.py
Group: D (Trading Strategies)
Purpose: Directional bull put spread strategy

Description:
    This module implements a directional bull put spread strategy for SPY options.
    The strategy sells out-of-the-money put spreads when bullish market conditions
    are detected. It incorporates volatility regime analysis, optimal entry timing,
    and research-driven profit targets. The strategy is designed to collect premium
    while limiting risk through the protective long put.

Author: Mohamed Talib
Date: 2025-01-27
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
import uuid

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
from SpyderE_Risk.SpyderE01_RiskManager import get_risk_manager
from SpyderE_Risk.SpyderE02_PositionSizer import get_position_sizer
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from SpyderU_Utilities.SpyderU07_Constants import (
    BULL_PUT_SPREAD_PROFIT_TARGET,
    BULL_PUT_SPREAD_STOP_LOSS,
    MIN_IVR_FOR_SPREADS,
    MAX_SPREAD_WIDTH,
    MIN_CREDIT_RATIO,
    OPTIMAL_ENTRY_START,
    OPTIMAL_ENTRY_END,
    TIME_BASED_EXIT
)
from SpyderU_Utilities.SpyderU11_FeatureFlags import get_feature_flags
from SpyderB_Broker.SpyderB01_SpyderClient import get_ib_client
from SpyderB_Broker.SpyderB06_ContractBuilder import ContractBuilder
from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from SpyderU_Utilities.SpyderU13_TechnicalIndicators import TechnicalIndicators
from SpyderF_Analysis.SpyderF05_TrendDetection import TrendDetector
from SpyderF_Analysis.SpyderF08_VolatilityRegime import VolatilityRegimeAnalyzer
from SpyderF_Analysis.SpyderF09_EntryFilters import EntryFilters
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
STRATEGY_NAME = "BullPutSpread"
DEFAULT_DELTA_SHORT = -0.30  # Short put delta
DEFAULT_DELTA_LONG = -0.20   # Long put delta
MIN_DAYS_TO_EXPIRY = 0       # Allow 0DTE
MAX_DAYS_TO_EXPIRY = 7       # Max 7 DTE
MIN_PREMIUM_COLLECTED = 0.50  # Minimum $0.50 credit per spread
MAX_CONTRACTS = 10           # Maximum contracts per trade

# Bull market indicators
BULL_TREND_MA_DAYS = 10     # Moving average period
BULL_RSI_THRESHOLD = 40      # RSI above this for bull signal
BULL_VWAP_TOLERANCE = 0.002  # Price above VWAP - 0.2%

# Position management
MAX_POSITIONS = 5            # Maximum concurrent positions
ADJUSTMENT_THRESHOLD = 0.80  # Adjust if short strike touched
MIN_PROFIT_TO_CLOSE = 0.10  # Close if 10% profit available

# ==============================================================================
# ENUMS
# ==============================================================================
class MarketRegime(Enum):
    """Market regime classification for strategy selection."""
    STRONG_BULL = "strong_bull"
    BULL = "bull"
    NEUTRAL = "neutral"
    BEAR = "bear"
    STRONG_BEAR = "strong_bear"

class SpreadState(Enum):
    """Bull put spread position state"""
    PENDING = "pending"
    ACTIVE = "active"
    ADJUSTING = "adjusting"
    CLOSING = "closing"
    CLOSED = "closed"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class BullPutSpreadSignal:
    """Signal data for bull put spread entry."""
    signal_id: str
    timestamp: datetime
    underlying_price: float
    short_strike: float
    long_strike: float
    expiration: str
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

@dataclass
class BullPutSpreadPosition:
    """Active bull put spread position"""
    position_id: str
    signal: BullPutSpreadSignal
    entry_time: datetime
    state: SpreadState = SpreadState.PENDING
    current_value: float = 0.0
    pnl: float = 0.0
    days_held: int = 0
    order_ids: Dict[str, int] = field(default_factory=dict)

# ==============================================================================
# BULL PUT SPREAD STRATEGY
# ==============================================================================
class BullPutSpreadStrategy(BaseStrategy):
    """
    Bull put spread strategy implementation.
    
    This strategy sells out-of-the-money put spreads when:
    - Market shows bullish characteristics
    - Volatility regime is favorable
    - Entry timing is optimal (10:15-11:40 AM)
    - Risk/reward meets minimum thresholds
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize bull put spread strategy."""
        super().__init__(STRATEGY_NAME, config)
        
        # Initialize components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.ib_client = get_ib_client()
        
        # Strategy configuration
        self.delta_short = config.get('delta_short', DEFAULT_DELTA_SHORT)
        self.delta_long = config.get('delta_long', DEFAULT_DELTA_LONG)
        self.min_credit_ratio = config.get('min_credit_ratio', MIN_CREDIT_RATIO)
        self.profit_target = config.get('profit_target', BULL_PUT_SPREAD_PROFIT_TARGET)
        self.stop_loss = config.get('stop_loss', BULL_PUT_SPREAD_STOP_LOSS)
        self.max_positions = config.get('max_positions', MAX_POSITIONS)
        
        # Risk management
        self.risk_manager = get_risk_manager()
        self.position_sizer = get_position_sizer()
        
        # Market analysis
        self.market_internals = MarketInternals()
        self.indicators = TechnicalIndicators()
        self.trend_detector = TrendDetector()
        self.vol_analyzer = VolatilityRegimeAnalyzer()
        self.entry_filters = EntryFilters()
        self.option_chain_manager = OptionChainManager()
        
        # Feature flags
        self.feature_flags = get_feature_flags()
        
        # Performance tracking
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.open_positions: Dict[str, BullPutSpreadPosition] = {}
        self.win_count = 0
        self.loss_count = 0
        
        self.logger.info(f"Bull put spread strategy initialized with delta {self.delta_short}/{self.delta_long}")
    
    def analyze_market_regime(self, market_data: Dict[str, Any]) -> MarketRegime:
        """
        Analyze current market regime for bull put spread suitability.
        
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
            
            # Bull market scoring
            bull_score = 0
            
            # Price above moving averages
            if price > sma_10:
                bull_score += 2
            if price > sma_20:
                bull_score += 1
            
            # RSI not oversold
            if rsi > BULL_RSI_THRESHOLD:
                bull_score += 2
            if rsi > 60:
                bull_score += 1
            
            # Price near or above VWAP
            vwap_diff = (price - vwap) / vwap
            if vwap_diff > -BULL_VWAP_TOLERANCE:
                bull_score += 2
            
            # Trend strength
            trend_strength = (sma_10 - sma_20) / sma_20
            if trend_strength > 0.002:  # 0.2% above
                bull_score += 2
            
            # Market internals
            internals = self.market_internals.get_current_snapshot()
            if internals and internals.nyse_tick > 0:
                bull_score += 1
            
            # Classify regime
            if bull_score >= 8:
                return MarketRegime.STRONG_BULL
            elif bull_score >= 6:
                return MarketRegime.BULL
            elif bull_score >= 4:
                return MarketRegime.NEUTRAL
            elif bull_score >= 2:
                return MarketRegime.BEAR
            else:
                return MarketRegime.STRONG_BEAR
                
        except Exception as e:
            self.logger.error(f"Error analyzing market regime: {e}")
            return MarketRegime.NEUTRAL
    
    def find_optimal_strikes(self, 
                           options_chain: pd.DataFrame,
                           underlying_price: float,
                           expiration: str) -> Optional[Tuple[float, float]]:
        """
        Find optimal strike prices for bull put spread.
        
        Args:
            options_chain: Available options
            underlying_price: Current SPY price
            expiration: Target expiration
            
        Returns:
            Tuple of (short_strike, long_strike) or None
        """
        try:
            # Filter for puts at target expiration
            puts = options_chain[
                (options_chain['type'] == 'PUT') &
                (options_chain['expiration'] == expiration) &
                (options_chain['strike'] < underlying_price)
            ].sort_values('strike', ascending=False)
            
            if len(puts) < 2:
                return None
            
            # Find strikes near target deltas
            short_strike = None
            long_strike = None
            
            for _, option in puts.iterrows():
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
            spread_width = short_strike - long_strike
            if spread_width > MAX_SPREAD_WIDTH or spread_width < 1:
                return None
            
            # Check liquidity
            short_liquidity = self._check_option_liquidity(puts, short_strike)
            long_liquidity = self._check_option_liquidity(puts, long_strike)
            
            if not (short_liquidity and long_liquidity):
                return None
            
            return (short_strike, long_strike)
            
        except Exception as e:
            self.logger.error(f"Error finding optimal strikes: {e}")
            return None
    
    def _check_option_liquidity(self, options: pd.DataFrame, strike: float) -> bool:
        """Check if option has sufficient liquidity"""
        option = options[options['strike'] == strike]
        if option.empty:
            return False
        
        volume = option['volume'].iloc[0]
        open_interest = option['open_interest'].iloc[0]
        bid_ask_spread = option['ask'].iloc[0] - option['bid'].iloc[0]
        
        return (volume >= 100 and 
                open_interest >= 500 and 
                bid_ask_spread <= 0.10)
    
    def calculate_spread_metrics(self,
                               short_strike: float,
                               long_strike: float,
                               credit: float,
                               contracts: int = 1) -> Dict[str, float]:
        """
        Calculate key metrics for bull put spread.
        
        Args:
            short_strike: Short put strike price
            long_strike: Long put strike price
            credit: Net credit received
            contracts: Number of contracts
            
        Returns:
            Dict with spread metrics
        """
        spread_width = short_strike - long_strike
        
        # Calculate P&L metrics
        max_profit = credit * contracts * 100
        max_loss = (spread_width - credit) * contracts * 100
        breakeven = short_strike - credit
        
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
    
    def generate_entry_signal(self, market_data: Dict[str, Any]) -> Optional[BullPutSpreadSignal]:
        """
        Generate entry signal for bull put spread.
        
        Args:
            market_data: Current market data including options chain
            
        Returns:
            BullPutSpreadSignal if conditions met, None otherwise
        """
        try:
            # Check if strategy is enabled
            if not self.feature_flags.is_enabled('directional_spreads'):
                return None
            
            # Check maximum positions
            if len(self.open_positions) >= self.max_positions:
                return None
            
            # Check optimal entry window
            if not DateTimeUtils.is_within_time_range(OPTIMAL_ENTRY_START, OPTIMAL_ENTRY_END):
                self.logger.debug("Outside optimal entry window for bull put spread")
                return None
            
            # Analyze market regime
            regime = self.analyze_market_regime(market_data)
            if regime not in [MarketRegime.BULL, MarketRegime.STRONG_BULL]:
                self.logger.debug(f"Market regime {regime.value} not suitable for bull put spread")
                return None
            
            # Run entry filters
            filter_results = self.entry_filters.check_all_filters(
                symbol='SPY',
                strategy='BullPutSpread',
                market_data=market_data
            )
            
            if not filter_results['passed']:
                self.logger.debug(f"Entry filters failed: {filter_results['failed_filters']}")
                return None
            
            # Check volatility conditions
            vol_regime = self.vol_analyzer.analyze_regime(market_data)
            iv_rank = vol_regime.get('iv_rank', 0)
            
            if iv_rank < MIN_IVR_FOR_SPREADS:
                self.logger.debug(f"IV rank {iv_rank} too low for spread entry")
                return None
            
            # Get options chain
            options_chain = self.option_chain_manager.get_options_data('SPY')
            if options_chain is None or options_chain.empty:
                return None
            
            underlying_price = market_data.get('last_price', 0)
            
            # Find best expiration (prefer 2-5 DTE)
            best_signal = None
            best_score = 0
            
            expirations = options_chain['expiration'].unique()
            for expiry in expirations:
                dte = self._calculate_dte(expiry)
                
                if dte < MIN_DAYS_TO_EXPIRY or dte > MAX_DAYS_TO_EXPIRY:
                    continue
                
                # Find strikes
                strikes = self.find_optimal_strikes(options_chain, underlying_price, expiry)
                if not strikes:
                    continue
                
                short_strike, long_strike = strikes
                
                # Get option prices
                short_put = options_chain[
                    (options_chain['strike'] == short_strike) &
                    (options_chain['expiration'] == expiry) &
                    (options_chain['type'] == 'PUT')
                ].iloc[0]
                
                long_put = options_chain[
                    (options_chain['strike'] == long_strike) &
                    (options_chain['expiration'] == expiry) &
                    (options_chain['type'] == 'PUT')
                ].iloc[0]
                
                # Calculate net credit
                credit = short_put['bid'] - long_put['ask']
                
                if credit < MIN_PREMIUM_COLLECTED:
                    continue
                
                # Calculate metrics
                metrics = self.calculate_spread_metrics(short_strike, long_strike, credit)
                
                # Check credit ratio
                if metrics['credit_ratio'] < self.min_credit_ratio:
                    continue
                
                # Score this opportunity
                score = self._score_spread_opportunity(market_data, metrics, regime, dte, vol_regime)
                
                if score > best_score:
                    # Determine position size
                    position_size = self._calculate_position_size(metrics['max_loss'])
                    
                    contracts = min(position_size, MAX_CONTRACTS)
                    
                    if contracts > 0:
                        signal_id = f"BPS_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
                        
                        best_signal = BullPutSpreadSignal(
                            signal_id=signal_id,
                            timestamp=datetime.now(),
                            underlying_price=underlying_price,
                            short_strike=short_strike,
                            long_strike=long_strike,
                            expiration=expiry,
                            credit_received=credit,
                            spread_width=short_strike - long_strike,
                            probability_profit=metrics['probability_profit'],
                            implied_volatility=short_put.get('implied_volatility', 0),
                            delta_short=short_put.get('delta', self.delta_short),
                            delta_long=long_put.get('delta', self.delta_long),
                            contracts=contracts,
                            max_profit=metrics['max_profit'] * contracts,
                            max_loss=metrics['max_loss'] * contracts,
                            breakeven=metrics['breakeven'],
                            score=score,
                            metadata={
                                'regime': regime.value,
                                'iv_rank': iv_rank,
                                'credit_ratio': metrics['credit_ratio'],
                                'dte': dte,
                                'filter_results': filter_results
                            }
                        )
                        best_score = score
            
            if best_signal:
                self.logger.info(
                    f"Bull put spread signal: {best_signal.short_strike}/{best_signal.long_strike} "
                    f"for ${best_signal.credit_received:.2f} credit, score: {best_signal.score:.1f}"
                )
            
            return best_signal
            
        except Exception as e:
            self.logger.error(f"Error generating bull put spread signal: {e}")
            self.error_handler.handle_error(e)
            return None
    
    def _calculate_dte(self, expiration: str) -> int:
        """Calculate days to expiration"""
        exp_date = datetime.strptime(expiration, "%Y%m%d")
        return (exp_date.date() - datetime.now().date()).days
    
    def _score_spread_opportunity(self,
                                market_data: Dict[str, Any],
                                metrics: Dict[str, float],
                                regime: MarketRegime,
                                dte: int,
                                vol_regime: Dict) -> float:
        """
        Score a spread opportunity (0-100).
        
        Args:
            market_data: Current market data
            metrics: Spread metrics
            regime: Current market regime
            dte: Days to expiration
            vol_regime: Volatility regime data
            
        Returns:
            float: Score 0-100
        """
        score = 50.0  # Base score
        
        # Market regime bonus
        if regime == MarketRegime.STRONG_BULL:
            score += 15
        elif regime == MarketRegime.BULL:
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
        iv_rank = vol_regime.get('iv_rank', 50)
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
        
        # Trend confirmation
        trend_data = self.trend_detector.analyze_trend(market_data)
        if trend_data.get('trend_direction') == 'up':
            score += 5
        
        return max(0, min(100, score))
    
    def _calculate_position_size(self, max_loss_per_contract: float) -> int:
        """Calculate position size based on risk management"""
        max_risk = self.risk_manager.get_max_position_risk()
        
        # Position size based on max loss
        contracts = int(max_risk / max_loss_per_contract)
        
        # Apply position sizing rules
        size_params = {
            'strategy': 'BullPutSpread',
            'max_loss': max_loss_per_contract,
            'confidence': 0.7
        }
        
        recommended_size = self.position_sizer.calculate_position_size(size_params)
        
        return min(contracts, recommended_size, MAX_CONTRACTS)
    
    def should_exit_position(self,
                           position: BullPutSpreadPosition,
                           market_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Check if position should be exited.
        
        Args:
            position: Current position
            market_data: Current market data
            
        Returns:
            Tuple of (should_exit, reason)
        """
        try:
            signal = position.signal
            
            # Time-based exit at 12:00 PM
            if DateTimeUtils.get_current_time() >= TIME_BASED_EXIT:
                return True, "time_based_exit"
            
            # Get current spread value
            current_value = self._get_spread_value(position, market_data)
            entry_credit = signal.credit_received
            
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
            
            # Exit if underlying approaches short strike
            if underlying_price <= signal.short_strike * 1.02:  # Within 2% of short strike
                return True, "defensive_exit_strike_threatened"
            
            # DTE-based management
            dte = self._calculate_dte(signal.expiration)
            if dte == 0 and pnl_percent > MIN_PROFIT_TO_CLOSE:  # Take small profit on expiration day
                return True, "expiration_day_profit"
            
            # Market regime change
            current_regime = self.analyze_market_regime(market_data)
            if current_regime in [MarketRegime.BEAR, MarketRegime.STRONG_BEAR]:
                return True, "market_regime_bearish"
            
            return False, ""
            
        except Exception as e:
            self.logger.error(f"Error checking exit conditions: {e}")
            return False, ""
    
    def _get_spread_value(self,
                        position: BullPutSpreadPosition,
                        market_data: Dict[str, Any]) -> float:
        """Calculate current value of spread position"""
        try:
            signal = position.signal
            options_chain = self.option_chain_manager.get_options_data('SPY')
            
            if options_chain is None:
                return signal.credit_received  # Return entry value if no data
            
            # Get current prices for the spread
            short_put = options_chain[
                (options_chain['strike'] == signal.short_strike) &
                (options_chain['expiration'] == signal.expiration) &
                (options_chain['type'] == 'PUT')
            ]
            
            long_put = options_chain[
                (options_chain['strike'] == signal.long_strike) &
                (options_chain['expiration'] == signal.expiration) &
                (options_chain['type'] == 'PUT')
            ]
            
            if short_put.empty or long_put.empty:
                return signal.credit_received
            
            # Calculate current spread value (cost to close)
            current_value = short_put.iloc[0]['ask'] - long_put.iloc[0]['bid']
            return current_value
            
        except Exception as e:
            self.logger.error(f"Error calculating spread value: {e}")
            return position.signal.credit_received
    
    def execute_signal(self, signal: BullPutSpreadSignal) -> bool:
        """Execute bull put spread signal"""
        try:
            # Create position object
            position = BullPutSpreadPosition(
                position_id=signal.signal_id,
                signal=signal,
                entry_time=datetime.now(),
                state=SpreadState.PENDING
            )
            
            # Create option contracts
            short_put = ContractBuilder.create_option_contract(
                'SPY', signal.expiration, signal.short_strike, 'P'
            )
            long_put = ContractBuilder.create_option_contract(
                'SPY', signal.expiration, signal.long_strike, 'P'
            )
            
            # Place spread order
            spread_order = self.ib_client.create_spread_order(
                [(short_put, 'SELL', signal.contracts),
                 (long_put, 'BUY', signal.contracts)],
                'LMT',
                signal.credit_received
            )
            
            order_id = self.ib_client.place_order(spread_order)
            
            if order_id:
                position.order_ids['entry'] = order_id
                position.state = SpreadState.ACTIVE
                
                # Add to open positions
                self.open_positions[position.position_id] = position
                
                # Update daily stats
                self.trades_today += 1
                
                # Emit event
                self.event_manager.create_event(
                    EventType.POSITION,
                    {
                        'action': 'opened',
                        'strategy': 'BullPutSpread',
                        'position_id': position.position_id,
                        'details': {
                            'short_strike': signal.short_strike,
                            'long_strike': signal.long_strike,
                            'credit': signal.credit_received,
                            'contracts': signal.contracts,
                            'expiration': signal.expiration
                        }
                    },
                    source='BullPutSpreadStrategy'
                )
                
                self.logger.info(f"Bull put spread position opened: {position.position_id}")
                return True
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            self.error_handler.handle_error(e)
        
        return False
    
    def manage_positions(self) -> None:
        """Manage active bull put spread positions"""
        market_data = self._get_current_market_data()
        
        for position_id, position in list(self.open_positions.items()):
            try:
                if position.state == SpreadState.CLOSED:
                    continue
                
                # Update position metrics
                self._update_position_metrics(position, market_data)
                
                # Check exit conditions
                should_exit, reason = self.should_exit_position(position, market_data)
                
                if should_exit:
                    self._close_position(position, reason)
                
            except Exception as e:
                self.logger.error(f"Error managing position {position_id}: {e}")
                self.error_handler.handle_error(e)
    
    def _update_position_metrics(self, position: BullPutSpreadPosition, 
                                market_data: Dict[str, Any]) -> None:
        """Update position metrics"""
        try:
            # Update current value and P&L
            position.current_value = self._get_spread_value(position, market_data)
            position.pnl = (position.signal.credit_received - position.current_value) * \
                          position.signal.contracts * 100
            
            # Update days held
            position.days_held = (datetime.now() - position.entry_time).days
            
        except Exception as e:
            self.logger.error(f"Error updating position metrics: {e}")
    
    def _close_position(self, position: BullPutSpreadPosition, reason: str) -> None:
        """Close bull put spread position"""
        try:
            position.state = SpreadState.CLOSING
            signal = position.signal
            
            # Create closing order
            short_put = ContractBuilder.create_option_contract(
                'SPY', signal.expiration, signal.short_strike, 'P'
            )
            long_put = ContractBuilder.create_option_contract(
                'SPY', signal.expiration, signal.long_strike, 'P'
            )
            
            # Place closing spread order (opposite of opening)
            closing_order = self.ib_client.create_spread_order(
                [(short_put, 'BUY', signal.contracts),
                 (long_put, 'SELL', signal.contracts)],
                'MKT',
                0  # Market order for closing
            )
            
            order_id = self.ib_client.place_order(closing_order)
            
            if order_id:
                position.order_ids['exit'] = order_id
                position.state = SpreadState.CLOSED
                
                # Update performance stats
                self.daily_pnl += position.pnl
                if position.pnl > 0:
                    self.win_count += 1
                else:
                    self.loss_count += 1
                
                # Emit event
                self.event_manager.create_event(
                    EventType.POSITION,
                    {
                        'action': 'closed',
                        'strategy': 'BullPutSpread',
                        'position_id': position.position_id,
                        'reason': reason,
                        'pnl': position.pnl,
                        'days_held': position.days_held
                    },
                    source='BullPutSpreadStrategy'
                )
                
                self.logger.info(
                    f"Bull put spread position closed: {position.position_id}, "
                    f"Reason: {reason}, P&L: ${position.pnl:.2f}"
                )
                
                # Remove from open positions
                del self.open_positions[position.position_id]
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            self.error_handler.handle_error(e)
            position.state = SpreadState.ACTIVE
    
    def _get_current_market_data(self) -> Dict[str, Any]:
        """Get current market data"""
        try:
            # Get SPY quote
            spy_quote = self.ib_client.get_quote('SPY')
            
            # Calculate technical indicators
            price_data = self.ib_client.get_historical_data('SPY', '1 day', '20 D')
            
            sma_10 = price_data['close'].rolling(10).mean().iloc[-1]
            sma_20 = price_data['close'].rolling(20).mean().iloc[-1]
            rsi = self.indicators.calculate_rsi(price_data['close']).iloc[-1]
            
            # Get VWAP
            vwap = self.indicators.calculate_vwap(price_data).iloc[-1]
            
            return {
                'last_price': spy_quote['last'],
                'bid': spy_quote['bid'],
                'ask': spy_quote['ask'],
                'volume': spy_quote['volume'],
                'sma_10': sma_10,
                'sma_20': sma_20,
                'rsi': rsi,
                'vwap': vwap,
                'vix': self.ib_client.get_quote('VIX')['last']
            }
            
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            return {}
    
    def get_strategy_metrics(self) -> Dict[str, Any]:
        """Get bull put spread strategy metrics"""
        total_trades = self.win_count + self.loss_count
        win_rate = self.win_count / total_trades if total_trades > 0 else 0
        
        active_positions = [p for p in self.open_positions.values() 
                           if p.state == SpreadState.ACTIVE]
        
        total_credit = sum(p.signal.credit_received * p.signal.contracts * 100 
                          for p in active_positions)
        total_risk = sum(p.signal.max_loss for p in active_positions)
        
        return {
            'strategy': 'BullPutSpread',
            'active_positions': len(active_positions),
            'daily_trades': self.trades_today,
            'daily_pnl': self.daily_pnl,
            'win_rate': win_rate,
            'total_trades': total_trades,
            'total_credit': total_credit,
            'total_risk': total_risk,
            'avg_credit': total_credit / len(active_positions) if active_positions else 0,
            'profit_target': self.profit_target,
            'stop_loss': self.stop_loss
        }
    
    def reset_daily_stats(self) -> None:
        """Reset daily statistics"""
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.logger.info("Daily stats reset for Bull Put Spread strategy")
    
    def shutdown(self) -> None:
        """Cleanup strategy resources"""
        try:
            # Close all positions
            for position in list(self.open_positions.values()):
                if position.state != SpreadState.CLOSED:
                    self._close_position(position, "strategy_shutdown")
            
            self.logger.info("Bull Put Spread strategy shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_bull_put_spread_strategy(config: Dict[str, Any]) -> BullPutSpreadStrategy:
    """
    Factory function to create Bull Put Spread strategy instance.
    
    Args:
        config: Strategy configuration
        
    Returns:
        BullPutSpreadStrategy instance
    """
    return BullPutSpreadStrategy(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the strategy
    test_config = {
        'delta_short': -0.30,
        'delta_long': -0.20,
        'min_credit_ratio': 0.25,
        'profit_target': 0.50,
        'stop_loss': 1.00,
        'max_positions': 5
    }
    
    strategy = create_bull_put_spread_strategy(test_config)
    
    # Create test market data
    test_market_data = {
        'last_price': 455.00,
        'bid': 454.95,
        'ask': 455.05,
        'volume': 75000000,
        'sma_10': 453.50,
        'sma_20': 452.00,
        'rsi': 58,
        'vwap': 454.80,
        'vix': 16.5,
        'iv_rank': 65
    }
    
    # Generate signal
    signal = strategy.generate_entry_signal(test_market_data)
    
    if signal:
        print(f"\nBull Put Spread Signal Generated:")
        print(f"  Signal ID: {signal.signal_id}")
        print(f"  Strikes: {signal.short_strike}/{signal.long_strike}")
        print(f"  Credit: ${signal.credit_received:.2f}")
        print(f"  Contracts: {signal.contracts}")
        print(f"  Max Profit: ${signal.max_profit:.2f}")
        print(f"  Max Loss: ${signal.max_loss:.2f}")
        print(f"  Breakeven: ${signal.breakeven:.2f}")
        print(f"  Score: {signal.score:.1f}")
        print(f"  Market Regime: {signal.metadata['regime']}")
    else:
        print("No signal generated")
    
    # Get metrics
    metrics = strategy.get_strategy_metrics()
    print(f"\nStrategy Metrics:")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    
    strategy.shutdown()