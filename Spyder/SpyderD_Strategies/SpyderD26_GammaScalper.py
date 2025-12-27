#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderD26_GammaScalper.py
Group: D (Strategies)
Purpose: Automated gamma scalping strategy with dynamic hedging
Author: Mohamed Talib
Date Created: 2025-01-27
Last Updated: 2025-01-27 Time: 17:00:00

Description:
    This module implements an automated gamma scalping strategy that dynamically
    hedges delta exposure while profiting from gamma. It uses sophisticated
    threshold-based rebalancing, volatility forecasting for optimal hedge timing,
    and integrates with the Greeks calculator for precise risk management. The
    strategy adapts hedge frequencies based on market conditions and P&L targets.

Key Features:
    - Automated delta-neutral portfolio management
    - Dynamic hedge threshold adjustment
    - Volatility-based hedge timing optimization
    - Transaction cost minimization
    - P&L attribution (theta vs gamma)
    - Multi-timeframe gamma analysis
    - Adaptive position sizing
    - Real-time Greeks monitoring
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from scipy import stats

# ==============================================================================
# SPYDER IMPORTS
# ==============================================================================
from Spyder.SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, Signal, StrategyState
from Spyder.SpyderN_Numerical.SpyderN04_OptionsGreeksCalculator import OptionsGreeksCalculator
from Spyder.SpyderN_Numerical.SpyderN05_VolatilityModeling import VolatilityModeling
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Delta thresholds
BASE_DELTA_THRESHOLD = 10  # Base delta threshold for rehedging
MIN_DELTA_THRESHOLD = 5  # Minimum delta threshold
MAX_DELTA_THRESHOLD = 50  # Maximum delta threshold
DELTA_BUFFER = 2  # Buffer to prevent excessive hedging

# Gamma targets
TARGET_GAMMA = 100  # Target portfolio gamma
MIN_GAMMA = 50  # Minimum gamma to maintain
MAX_GAMMA = 200  # Maximum gamma allowed

# Position limits
MAX_OPTION_POSITIONS = 10
MAX_HEDGE_SIZE = 100  # Maximum shares per hedge
MIN_HEDGE_SIZE = 10  # Minimum shares to hedge

# Volatility parameters
HIGH_VOL_THRESHOLD = 0.25  # 25% IV is high vol
LOW_VOL_THRESHOLD = 0.15  # 15% IV is low vol
VOL_EXPANSION_MULTIPLIER = 1.5  # Increase gamma in expanding vol
VOL_CONTRACTION_MULTIPLIER = 0.7  # Reduce gamma in contracting vol

# P&L targets
DAILY_PROFIT_TARGET = 500  # Daily profit target
DAILY_LOSS_LIMIT = 300  # Daily loss limit
GAMMA_PNL_TARGET = 0.6  # Target 60% of P&L from gamma

# Transaction costs
OPTION_COMMISSION = 0.65  # Per contract
STOCK_COMMISSION = 0.005  # Per share
SLIPPAGE_BPS = 2  # 2 basis points slippage

# ==============================================================================
# ENUMS
# ==============================================================================
class HedgeType(Enum):
    """Types of hedging actions"""
    BUY_STOCK = "buy_stock"
    SELL_STOCK = "sell_stock"
    BUY_CALLS = "buy_calls"
    SELL_CALLS = "sell_calls"
    BUY_PUTS = "buy_puts"
    SELL_PUTS = "sell_puts"
    NO_ACTION = "no_action"

class MarketCondition(Enum):
    """Market conditions for gamma scalping"""
    HIGH_VOLATILITY = "high_volatility"
    NORMAL_VOLATILITY = "normal_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    WHIPSAW = "whipsaw"

class ScalpingMode(Enum):
    """Gamma scalping modes"""
    AGGRESSIVE = "aggressive"  # Tight thresholds, frequent hedging
    NORMAL = "normal"  # Standard thresholds
    CONSERVATIVE = "conservative"  # Wide thresholds, less frequent
    ADAPTIVE = "adaptive"  # Dynamically adjust based on conditions

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GammaPosition:
    """Individual gamma position"""
    position_id: str
    option_type: str  # CALL or PUT
    strike: float
    expiration: datetime
    contracts: int
    entry_price: float
    current_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    days_to_expiry: int
    pnl: float = 0.0

@dataclass
class HedgeAction:
    """Hedge action details"""
    timestamp: datetime
    hedge_type: HedgeType
    quantity: int
    price: float
    portfolio_delta_before: float
    portfolio_delta_after: float
    cost: float
    reason: str

@dataclass
class ScalpingMetrics:
    """Gamma scalping performance metrics"""
    total_hedges: int
    profitable_hedges: int
    total_hedge_pnl: float
    total_gamma_pnl: float
    total_theta_decay: float
    net_pnl: float
    max_delta_exposure: float
    avg_hedge_frequency: float  # Hedges per day
    transaction_costs: float
    sharpe_ratio: float

@dataclass
class PortfolioGreeks:
    """Aggregate portfolio Greeks"""
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    weighted_avg_iv: float
    gamma_concentration: float  # Concentration risk metric

# ==============================================================================
# MAIN STRATEGY CLASS
# ==============================================================================
class GammaScalperStrategy(BaseStrategy):
    """
    Automated gamma scalping strategy.
    
    Maintains delta-neutral portfolio while profiting from gamma through
    dynamic hedging based on market movements.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Gamma Scalper Strategy"""
        super().__init__(config)
        
        self.strategy_name = "GammaScalper"
        self.version = "1.0.0"
        
        # Components
        self.greeks_calculator = OptionsGreeksCalculator()
        self.volatility_model = VolatilityModeling()
        
        # Strategy parameters
        self.scalping_mode = ScalpingMode(config.get('scalping_mode', 'adaptive'))
        self.base_delta_threshold = config.get('delta_threshold', BASE_DELTA_THRESHOLD)
        self.target_gamma = config.get('target_gamma', TARGET_GAMMA)
        
        # Dynamic thresholds
        self.current_delta_threshold = self.base_delta_threshold
        self.hedge_frequency_modifier = 1.0
        
        # Position tracking
        self.gamma_positions: Dict[str, GammaPosition] = {}
        self.stock_position = 0  # Current stock hedge position
        self.hedge_history: List[HedgeAction] = []
        
        # Greeks tracking
        self.portfolio_greeks = PortfolioGreeks(0, 0, 0, 0, 0, 0)
        self.greeks_history = []
        
        # Market analysis
        self.market_condition = MarketCondition.NORMAL_VOLATILITY
        self.realized_volatility = 0.0
        self.implied_volatility = 0.0
        self.price_path = []
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.gamma_pnl = 0.0
        self.theta_decay = 0.0
        self.hedge_pnl = 0.0
        self.transaction_costs = 0.0
        
        # Scalping metrics
        self.metrics = ScalpingMetrics(
            total_hedges=0,
            profitable_hedges=0,
            total_hedge_pnl=0,
            total_gamma_pnl=0,
            total_theta_decay=0,
            net_pnl=0,
            max_delta_exposure=0,
            avg_hedge_frequency=0,
            transaction_costs=0,
            sharpe_ratio=0
        )
        
        self.logger.info(f"{self.strategy_name} initialized in {self.scalping_mode} mode")
    
    def analyze_market_conditions(self, market_data: Dict[str, Any]) -> Signal:
        """
        Analyze market for gamma scalping opportunities.
        
        Args:
            market_data: Current market data
            
        Returns:
            Trading signal for gamma scalping
        """
        try:
            # Update market analysis
            self._update_market_condition(market_data)
            self._update_portfolio_greeks(market_data)
            
            # Track price for realized vol calculation
            spot_price = market_data['SPY']['last']
            self.price_path.append(spot_price)
            
            # Check if we need to establish gamma position
            if self._should_establish_gamma(market_data):
                return self._create_gamma_position_signal(market_data)
            
            # Check if we need to hedge delta
            hedge_signal = self._check_delta_hedge(market_data)
            if hedge_signal:
                return hedge_signal
            
            # Check if we need to adjust gamma exposure
            adjustment_signal = self._check_gamma_adjustment(market_data)
            if adjustment_signal:
                return adjustment_signal
            
            # Check P&L targets and stops
            risk_signal = self._check_risk_limits()
            if risk_signal:
                return risk_signal
            
            return Signal(action="HOLD")
            
        except Exception as e:
            self.logger.error(f"Error in gamma scalping analysis: {e}")
            self.error_handler.handle_error(e, {"method": "analyze_market_conditions"})
            return Signal(action="HOLD")
    
    def _update_market_condition(self, market_data: Dict[str, Any]):
        """Update market condition assessment"""
        try:
            # Get volatility metrics
            self.implied_volatility = market_data.get('implied_volatility', 0.20)
            
            # Calculate realized volatility from price path
            if len(self.price_path) > 20:
                returns = np.diff(np.log(self.price_path[-21:]))
                self.realized_volatility = np.std(returns) * np.sqrt(252)
            
            # Determine market condition
            if self.implied_volatility > HIGH_VOL_THRESHOLD:
                self.market_condition = MarketCondition.HIGH_VOLATILITY
            elif self.implied_volatility < LOW_VOL_THRESHOLD:
                self.market_condition = MarketCondition.LOW_VOLATILITY
            else:
                # Check for trending vs range-bound
                if len(self.price_path) > 10:
                    recent_prices = self.price_path[-10:]
                    price_change = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
                    
                    if price_change > 0.02:  # 2% up move
                        self.market_condition = MarketCondition.TRENDING_UP
                    elif price_change < -0.02:  # 2% down move
                        self.market_condition = MarketCondition.TRENDING_DOWN
                    else:
                        # Check for whipsaw
                        price_std = np.std(recent_prices) / np.mean(recent_prices)
                        if price_std > 0.015:  # High volatility without trend
                            self.market_condition = MarketCondition.WHIPSAW
                        else:
                            self.market_condition = MarketCondition.RANGE_BOUND
                else:
                    self.market_condition = MarketCondition.NORMAL_VOLATILITY
            
            # Adjust delta threshold based on market condition
            self._adjust_delta_threshold()
            
        except Exception as e:
            self.logger.error(f"Error updating market condition: {e}")
            self.market_condition = MarketCondition.NORMAL_VOLATILITY
    
    def _adjust_delta_threshold(self):
        """Dynamically adjust delta threshold based on conditions"""
        if self.scalping_mode != ScalpingMode.ADAPTIVE:
            # Fixed thresholds for non-adaptive modes
            mode_thresholds = {
                ScalpingMode.AGGRESSIVE: BASE_DELTA_THRESHOLD * 0.5,
                ScalpingMode.NORMAL: BASE_DELTA_THRESHOLD,
                ScalpingMode.CONSERVATIVE: BASE_DELTA_THRESHOLD * 2.0
            }
            self.current_delta_threshold = mode_thresholds.get(
                self.scalping_mode, BASE_DELTA_THRESHOLD
            )
            return
        
        # Adaptive threshold adjustment
        base = self.base_delta_threshold
        
        # Adjust for market condition
        condition_multipliers = {
            MarketCondition.HIGH_VOLATILITY: 0.7,  # Tighter threshold in high vol
            MarketCondition.NORMAL_VOLATILITY: 1.0,
            MarketCondition.LOW_VOLATILITY: 1.5,  # Wider threshold in low vol
            MarketCondition.TRENDING_UP: 1.2,
            MarketCondition.TRENDING_DOWN: 1.2,
            MarketCondition.RANGE_BOUND: 0.8,  # Tighter in range-bound
            MarketCondition.WHIPSAW: 1.5  # Wider to avoid overtrading
        }
        
        multiplier = condition_multipliers.get(self.market_condition, 1.0)
        
        # Adjust for P&L
        if self.daily_pnl > DAILY_PROFIT_TARGET * 0.8:
            multiplier *= 1.3  # Widen threshold when near profit target
        elif self.daily_pnl < -DAILY_LOSS_LIMIT * 0.5:
            multiplier *= 1.5  # Widen threshold when losing
        
        # Adjust for transaction costs
        if self.metrics.total_hedges > 0:
            cost_ratio = self.transaction_costs / max(1, abs(self.gamma_pnl))
            if cost_ratio > 0.3:  # Costs eating too much profit
                multiplier *= 1.5
        
        self.current_delta_threshold = np.clip(
            base * multiplier,
            MIN_DELTA_THRESHOLD,
            MAX_DELTA_THRESHOLD
        )
    
    def _update_portfolio_greeks(self, market_data: Dict[str, Any]):
        """Update aggregate portfolio Greeks"""
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_iv = 0.0
        total_weight = 0.0
        
        # Update Greeks for each position
        for pos_id, position in self.gamma_positions.items():
            # Get current Greeks from market data or calculate
            option_data = self._get_option_data(
                market_data, position.strike, position.option_type, position.expiration
            )
            
            if option_data:
                position.delta = option_data.get('delta', position.delta)
                position.gamma = option_data.get('gamma', position.gamma)
                position.theta = option_data.get('theta', position.theta)
                position.vega = option_data.get('vega', position.vega)
                position.current_price = option_data.get('price', position.current_price)
            
            # Aggregate Greeks
            contract_multiplier = position.contracts * 100
            total_delta += position.delta * contract_multiplier
            total_gamma += position.gamma * contract_multiplier
            total_theta += position.theta * contract_multiplier
            total_vega += position.vega * contract_multiplier
            
            # Weighted IV
            weight = abs(position.vega * contract_multiplier)
            total_iv += self.implied_volatility * weight
            total_weight += weight
        
        # Add stock hedge delta
        total_delta += self.stock_position
        
        # Calculate weighted average IV
        weighted_iv = total_iv / max(1, total_weight) if total_weight > 0 else self.implied_volatility
        
        # Calculate gamma concentration (Herfindahl index)
        if total_gamma > 0:
            gamma_concentration = sum(
                (pos.gamma * pos.contracts * 100 / total_gamma) ** 2
                for pos in self.gamma_positions.values()
            )
        else:
            gamma_concentration = 0
        
        self.portfolio_greeks = PortfolioGreeks(
            total_delta=total_delta,
            total_gamma=total_gamma,
            total_theta=total_theta,
            total_vega=total_vega,
            weighted_avg_iv=weighted_iv,
            gamma_concentration=gamma_concentration
        )
        
        # Track maximum delta exposure
        self.metrics.max_delta_exposure = max(
            self.metrics.max_delta_exposure,
            abs(total_delta)
        )
    
    def _get_option_data(
        self,
        market_data: Dict,
        strike: float,
        option_type: str,
        expiration: datetime
    ) -> Optional[Dict]:
        """Get option data from market data"""
        try:
            chain = market_data.get('options_chain', {})
            options = chain.get('calls' if option_type == 'CALL' else 'puts', {})
            
            if strike in options:
                return options[strike]
            
            # If exact strike not found, interpolate or return None
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting option data: {e}")
            return None
    
    def _should_establish_gamma(self, market_data: Dict[str, Any]) -> bool:
        """Check if we should establish new gamma position"""
        # Don't add if already at max positions
        if len(self.gamma_positions) >= MAX_OPTION_POSITIONS:
            return False
        
        # Check if current gamma is below target
        if self.portfolio_greeks.total_gamma < self.target_gamma * 0.8:
            # Good conditions for gamma scalping
            if self.market_condition in [
                MarketCondition.HIGH_VOLATILITY,
                MarketCondition.RANGE_BOUND,
                MarketCondition.NORMAL_VOLATILITY
            ]:
                return True
        
        # Check for specific opportunities
        if self._identify_gamma_opportunity(market_data):
            return True
        
        return False
    
    def _identify_gamma_opportunity(self, market_data: Dict[str, Any]) -> bool:
        """Identify specific gamma scalping opportunities"""
        # Look for high gamma options with reasonable theta
        chain = market_data.get('options_chain', {})
        
        for option_type in ['calls', 'puts']:
            options = chain.get(option_type, {})
            for strike, data in options.items():
                gamma = data.get('gamma', 0)
                theta = data.get('theta', 0)
                price = data.get('price', 0)
                
                # High gamma relative to theta decay
                if gamma > 0.05 and abs(theta/gamma) < 10 and price > 0.50:
                    return True
        
        return False
    
    def _create_gamma_position_signal(self, market_data: Dict[str, Any]) -> Signal:
        """Create signal to establish gamma position"""
        spot = market_data['SPY']['last']
        
        # Find optimal strike for gamma
        optimal_strike, option_type = self._find_optimal_gamma_strike(market_data)
        
        if not optimal_strike:
            return Signal(action="HOLD")
        
        # Calculate position size
        contracts = self._calculate_gamma_position_size(market_data, optimal_strike)
        
        return Signal(
            action="BUY",
            option_type=option_type,
            strike=optimal_strike,
            contracts=contracts,
            reason="Establish gamma position",
            metadata={
                'target_gamma': self.target_gamma,
                'current_gamma': self.portfolio_greeks.total_gamma,
                'market_condition': self.market_condition.value
            }
        )
    
    def _find_optimal_gamma_strike(
        self,
        market_data: Dict[str, Any]
    ) -> Tuple[Optional[float], Optional[str]]:
        """Find optimal strike for gamma scalping"""
        spot = market_data['SPY']['last']
        chain = market_data.get('options_chain', {})
        
        best_score = -float('inf')
        best_strike = None
        best_type = None
        
        # Analyze both calls and puts
        for option_type in ['calls', 'puts']:
            options = chain.get(option_type, {})
            
            for strike, data in options.items():
                # Focus on near-the-money options
                if abs(strike - spot) / spot > 0.05:  # Skip if more than 5% away
                    continue
                
                gamma = data.get('gamma', 0)
                theta = data.get('theta', 0)
                vega = data.get('vega', 0)
                price = data.get('price', 0)
                volume = data.get('volume', 0)
                
                # Score based on gamma efficiency
                if gamma > 0 and price > 0:
                    # Gamma per dollar spent
                    gamma_efficiency = gamma / price
                    
                    # Theta drag penalty
                    theta_penalty = abs(theta) / price if price > 0 else 0
                    
                    # Liquidity bonus
                    liquidity_bonus = min(1.0, volume / 1000)
                    
                    # Calculate score
                    score = gamma_efficiency - theta_penalty * 0.5 + liquidity_bonus * 0.2
                    
                    # Adjust for market condition
                    if self.market_condition == MarketCondition.HIGH_VOLATILITY:
                        score *= 1.2  # Prefer gamma in high vol
                    elif self.market_condition == MarketCondition.LOW_VOLATILITY:
                        score *= 0.8  # Less attractive in low vol
                    
                    if score > best_score:
                        best_score = score
                        best_strike = strike
                        best_type = option_type.upper()[:-1]  # 'calls' -> 'CALL'
        
        return best_strike, best_type
    
    def _calculate_gamma_position_size(self, market_data: Dict, strike: float) -> int:
        """Calculate optimal position size for gamma"""
        # Get option data
        chain = market_data.get('options_chain', {})
        option_data = None
        
        for option_type in ['calls', 'puts']:
            if strike in chain.get(option_type, {}):
                option_data = chain[option_type][strike]
                break
        
        if not option_data:
            return 1
        
        gamma_per_contract = option_data.get('gamma', 0.01) * 100
        
        # Calculate contracts needed for target gamma
        gamma_needed = self.target_gamma - self.portfolio_greeks.total_gamma
        contracts = int(gamma_needed / gamma_per_contract)
        
        # Apply limits
        contracts = max(1, min(contracts, 10))
        
        # Adjust for market condition
        if self.market_condition == MarketCondition.HIGH_VOLATILITY:
            contracts = int(contracts * VOL_EXPANSION_MULTIPLIER)
        elif self.market_condition == MarketCondition.LOW_VOLATILITY:
            contracts = int(contracts * VOL_CONTRACTION_MULTIPLIER)
        
        return contracts
    
    def _check_delta_hedge(self, market_data: Dict[str, Any]) -> Optional[Signal]:
        """Check if delta hedge is needed"""
        current_delta = self.portfolio_greeks.total_delta
        
        # Check if delta exceeds threshold
        if abs(current_delta) > self.current_delta_threshold:
            return self._create_hedge_signal(current_delta, market_data)
        
        # Check for opportunistic hedging in trending markets
        if self.market_condition in [MarketCondition.TRENDING_UP, MarketCondition.TRENDING_DOWN]:
            if abs(current_delta) > self.current_delta_threshold * 0.7:
                # Hedge earlier in trending markets
                return self._create_hedge_signal(current_delta, market_data)
        
        return None
    
    def _create_hedge_signal(self, delta_to_hedge: float, market_data: Dict) -> Signal:
        """Create hedge signal"""
        spot = market_data['SPY']['last']
        
        # Calculate hedge size (negative delta needs buy, positive needs sell)
        hedge_shares = -int(delta_to_hedge)
        
        # Apply minimum size filter
        if abs(hedge_shares) < MIN_HEDGE_SIZE:
            return Signal(action="HOLD")
        
        # Limit hedge size
        hedge_shares = np.clip(hedge_shares, -MAX_HEDGE_SIZE, MAX_HEDGE_SIZE)
        
        # Record hedge action
        hedge_action = HedgeAction(
            timestamp=datetime.now(),
            hedge_type=HedgeType.BUY_STOCK if hedge_shares > 0 else HedgeType.SELL_STOCK,
            quantity=abs(hedge_shares),
            price=spot,
            portfolio_delta_before=delta_to_hedge,
            portfolio_delta_after=delta_to_hedge + hedge_shares,
            cost=abs(hedge_shares) * STOCK_COMMISSION + abs(hedge_shares) * spot * SLIPPAGE_BPS / 10000,
            reason=f"Delta hedge: {delta_to_hedge:.1f} -> {delta_to_hedge + hedge_shares:.1f}"
        )
        
        self.hedge_history.append(hedge_action)
        self.metrics.total_hedges += 1
        self.transaction_costs += hedge_action.cost
        
        # Update stock position
        self.stock_position += hedge_shares
        
        return Signal(
            action="HEDGE",
            hedge_type="BUY" if hedge_shares > 0 else "SELL",
            quantity=abs(hedge_shares),
            price=spot,
            metadata={
                'delta_before': delta_to_hedge,
                'delta_after': delta_to_hedge + hedge_shares,
                'threshold': self.current_delta_threshold,
                'total_hedges': self.metrics.total_hedges
            }
        )
    
    def _check_gamma_adjustment(self, market_data: Dict[str, Any]) -> Optional[Signal]:
        """Check if gamma exposure needs adjustment"""
        current_gamma = self.portfolio_greeks.total_gamma
        
        # Check if gamma is too low
        if current_gamma < MIN_GAMMA:
            return self._create_gamma_position_signal(market_data)
        
        # Check if gamma is too high
        if current_gamma > MAX_GAMMA:
            return self._reduce_gamma_signal(market_data)
        
        # Check gamma concentration
        if self.portfolio_greeks.gamma_concentration > 0.5:  # Too concentrated
            return self._diversify_gamma_signal(market_data)
        
        return None
    
    def _reduce_gamma_signal(self, market_data: Dict) -> Signal:
        """Create signal to reduce gamma exposure"""
        # Find position with highest gamma to reduce
        if not self.gamma_positions:
            return Signal(action="HOLD")
        
        highest_gamma_position = max(
            self.gamma_positions.values(),
            key=lambda p: p.gamma * p.contracts
        )
        
        # Reduce by half
        contracts_to_close = max(1, highest_gamma_position.contracts // 2)
        
        return Signal(
            action="REDUCE",
            position_id=highest_gamma_position.position_id,
            contracts=contracts_to_close,
            reason="Reduce gamma exposure",
            metadata={
                'current_gamma': self.portfolio_greeks.total_gamma,
                'target_gamma': self.target_gamma
            }
        )
    
    def _diversify_gamma_signal(self, market_data: Dict) -> Signal:
        """Create signal to diversify gamma concentration"""
        # This would add gamma at different strikes
        return self._create_gamma_position_signal(market_data)
    
    def _check_risk_limits(self) -> Optional[Signal]:
        """Check P&L targets and risk limits"""
        # Check daily profit target
        if self.daily_pnl >= DAILY_PROFIT_TARGET:
            return Signal(
                action="CLOSE_ALL",
                reason="Daily profit target reached",
                metadata={'daily_pnl': self.daily_pnl}
            )
        
        # Check daily loss limit
        if self.daily_pnl <= -DAILY_LOSS_LIMIT:
            return Signal(
                action="CLOSE_ALL",
                reason="Daily loss limit reached",
                metadata={'daily_pnl': self.daily_pnl}
            )
        
        # Check gamma P&L ratio
        if self.metrics.total_hedges > 10:  # After sufficient hedges
            gamma_ratio = self.gamma_pnl / max(1, abs(self.daily_pnl))
            if gamma_ratio < GAMMA_PNL_TARGET * 0.5:  # Not enough gamma P&L
                return Signal(
                    action="ADJUST",
                    reason="Insufficient gamma P&L",
                    metadata={'gamma_ratio': gamma_ratio}
                )
        
        return None
    
    def calculate_pnl_attribution(self, market_data: Dict[str, Any]):
        """Calculate P&L attribution between gamma and theta"""
        spot = market_data['SPY']['last']
        
        if len(self.price_path) > 1:
            price_move = spot - self.price_path[-2]
            
            # Gamma P&L = 0.5 * Gamma * (price_move)^2
            self.gamma_pnl = 0.5 * self.portfolio_greeks.total_gamma * (price_move ** 2)
            
            # Theta decay (negative)
            self.theta_decay = self.portfolio_greeks.total_theta / 252  # Daily theta
            
            # Hedge P&L from stock position
            self.hedge_pnl = self.stock_position * price_move
            
            # Total P&L
            self.daily_pnl = self.gamma_pnl + self.theta_decay + self.hedge_pnl - self.transaction_costs
            
            # Update metrics
            self.metrics.total_gamma_pnl += self.gamma_pnl
            self.metrics.total_theta_decay += self.theta_decay
            self.metrics.total_hedge_pnl += self.hedge_pnl
            self.metrics.net_pnl = self.metrics.total_gamma_pnl + self.metrics.total_theta_decay + self.metrics.total_hedge_pnl - self.metrics.transaction_costs
    
    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get strategy performance statistics"""
        return {
            'strategy': self.strategy_name,
            'scalping_mode': self.scalping_mode.value,
            'total_hedges': self.metrics.total_hedges,
            'current_delta': self.portfolio_greeks.total_delta,
            'current_gamma': self.portfolio_greeks.total_gamma,
            'current_theta': self.portfolio_greeks.total_theta,
            'delta_threshold': self.current_delta_threshold,
            'daily_pnl': self.daily_pnl,
            'gamma_pnl': self.gamma_pnl,
            'theta_decay': self.theta_decay,
            'net_pnl': self.metrics.net_pnl,
            'transaction_costs': self.metrics.transaction_costs,
            'positions': len(self.gamma_positions),
            'stock_hedge': self.stock_position,
            'market_condition': self.market_condition.value
        }


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_gamma_scalper_strategy(config: Optional[Dict[str, Any]] = None) -> GammaScalperStrategy:
    """Factory function to create GammaScalperStrategy instance"""
    return GammaScalperStrategy(config)


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    # Test configuration
    test_config = {
        'scalping_mode': 'adaptive',
        'delta_threshold': 10,
        'target_gamma': 100
    }
    
    # Create strategy
    strategy = create_gamma_scalper_strategy(test_config)
    
    print("\n" + "="*60)
    print("GAMMA SCALPER STRATEGY TEST")
    print("="*60)
    
    # Test market data
    test_market_data = {
        'SPY': {'last': 450.00},
        'implied_volatility': 0.18,
        'options_chain': {
            'calls': {
                450: {'delta': 0.50, 'gamma': 0.05, 'theta': -0.15, 'vega': 0.20, 'price': 3.50, 'volume': 1000},
                451: {'delta': 0.45, 'gamma': 0.048, 'theta': -0.14, 'vega': 0.19, 'price': 3.00, 'volume': 800},
                449: {'delta': 0.55, 'gamma': 0.048, 'theta': -0.14, 'vega': 0.19, 'price': 4.00, 'volume': 900}
            },
            'puts': {
                450: {'delta': -0.50, 'gamma': 0.05, 'theta': -0.15, 'vega': 0.20, 'price': 3.50, 'volume': 1100},
                449: {'delta': -0.45, 'gamma': 0.048, 'theta': -0.14, 'vega': 0.19, 'price': 3.00, 'volume': 750}
            }
        }
    }
    
    # Test signal generation
    signal = strategy.analyze_market_conditions(test_market_data)
    
    print(f"\nSignal: {signal.action}")
    if signal.metadata:
        print("\nSignal Details:")
        for key, value in signal.metadata.items():
            print(f"  {key}: {value}")
    
    # Simulate some price movement
    print("\n" + "-"*40)
    print("Simulating price movements...")
    print("-"*40)
    
    price_moves = [450.50, 449.80, 451.20, 450.30, 452.00]
    
    for price in price_moves:
        test_market_data['SPY']['last'] = price
        signal = strategy.analyze_market_conditions(test_market_data)
        
        # Calculate P&L attribution
        strategy.calculate_pnl_attribution(test_market_data)
        
        print(f"\nPrice: ${price:.2f}")
        print(f"  Action: {signal.action}")
        print(f"  Portfolio Delta: {strategy.portfolio_greeks.total_delta:.1f}")
        print(f"  Portfolio Gamma: {strategy.portfolio_greeks.total_gamma:.1f}")
        print(f"  Daily P&L: ${strategy.daily_pnl:.2f}")
        
        if signal.action == "HEDGE":
            print(f"  Hedge: {signal.metadata.get('hedge_type')} {signal.metadata.get('quantity')} shares")
    
    # Get final stats
    stats = strategy.get_strategy_stats()
    print("\n" + "="*60)
    print("STRATEGY STATISTICS")
    print("="*60)
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
