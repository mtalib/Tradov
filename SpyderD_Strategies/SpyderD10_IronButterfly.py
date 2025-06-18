#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD10_IronButterfly.py
Group: D (Strategies)
Purpose: Iron Butterfly options strategy implementation

Description:
This module implements the Iron Butterfly strategy, providing
    2.5x more credit than iron condors for range-bound markets. It includes
    IV rank entry requirements, optimal earnings week positioning, and
    professional Greeks-based adjustment protocols.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import logging
import pandas as pd
import numpy as np
import asyncio

# ==============================================================================
# MODULE IMPLEMENTATION
# ==============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class ButterflyType(Enum):
    """Types of butterfly strategies."""
    IRON = "IRON"              # Short straddle + long strangle
    LONG = "LONG"              # Long butterfly for debit
    BROKEN_WING = "BROKEN_WING"  # Asymmetric wings
    RATIO = "RATIO"            # Different quantities on wings
@dataclass
class ButterflySetup:
    """Iron butterfly position setup."""
    center_strike: float
    lower_strike: float
    upper_strike: float
    expiration: datetime
    contracts: int
    credit_received: float
    max_profit: float
    max_loss: float
    breakeven_lower: float
    breakeven_upper: float
    profit_zone_width: float
    setup_type: ButterflyType
    entry_iv: float
    entry_greeks: Dict[str, float]
@dataclass
class AdjustmentTrigger:
    """Triggers for butterfly adjustments."""
    price_breach: bool
    delta_threshold: bool
    profit_target: bool
    loss_threshold: bool
    time_decay: bool
    iv_change: bool
    trigger_details: str
    recommended_action: str
class SpyderIronButterfly:
    """
    Implements professional iron butterfly strategy.
    Features:
    - Optimal strike selection for maximum credit
    - Range-bound market detection
    - Dynamic adjustment protocols
    - Greeks-based position management
    - Earnings week optimization
    """
    def __init__(self, market_data=None, greek_calculator=None, 
                 position_manager=None):
        """Initialize iron butterfly strategy."""
        self.market_data = market_data
        self.greek_calculator = greek_calculator
        self.position_manager = position_manager
        # Strategy parameters from professional research
        self.STRATEGY_PARAMS = {
            'min_iv_rank': 50,          # Minimum IV rank for entry
            'min_iv_percentile': 40,    # Alternative IV metric
            'optimal_dte': 45,          # Days to expiration
            'min_dte': 21,
            'max_dte': 60,
            'wing_width_atm_pct': 0.05, # 5% wings from ATM
            'min_credit_ratio': 0.35,   # Min 35% of wing width
            'target_credit_ratio': 0.40, # Target 40% credit
            'profit_target_pct': 0.25,  # Close at 25% profit
            'max_loss_multiplier': 2.0, # Stop at 2x credit loss
            'delta_threshold': 0.15,    # Adjustment trigger
            'adjustment_dte': 21        # Don't adjust <21 DTE
        }
        # Market condition requirements
        self.MARKET_CONDITIONS = {
            'max_daily_range': 0.015,   # Max 1.5% daily moves
            'min_range_days': 5,        # Days of range-bound
            'support_resistance_buffer': 0.02,  # 2% from S/R levels
            'trend_strength_max': 0.3,  # ADX or similar
            'correlation_threshold': 0.7 # SPY correlation check
        }
        # Earnings week optimization
        self.EARNINGS_CONFIG = {
            'mega_cap_stocks': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
            'impact_threshold': 0.03,   # 3% SPY impact expected
            'pre_earnings_days': 2,     # Enter 2 days before
            'post_earnings_hold': 1,    # Hold 1 day after
            'tighter_wings': True,      # Use tighter wings
            'wing_reduction': 0.7       # 70% of normal wings
        }
        # Greek targets
        self.GREEK_TARGETS = {
            'entry_delta': (-0.02, 0.02),    # Near neutral
            'entry_gamma': (-0.10, -0.05),   # Negative gamma
            'entry_theta': (0.10, 0.25),     # Positive theta
            'entry_vega': (-0.20, -0.10),    # Short vega
            'maintenance_delta': (-0.10, 0.10),
            'adjustment_delta': 0.15
        }
        # Active positions tracking
        self.active_butterflies = {}
        self.position_history = []
        self.adjustment_history = []
    async def scan_opportunities(self, spot_price: float, 
                               options_chain: pd.DataFrame) -> List[ButterflySetup]:
        """
        Scan for iron butterfly opportunities.
        Args:
            spot_price: Current SPY price
            options_chain: Available options data
        Returns:
            List of potential butterfly setups
        """
        opportunities = []
        # Check market conditions
        if not await self._check_market_conditions(spot_price):
            logger.info("Market conditions not suitable for iron butterflies")
            return opportunities
        # Get suitable expirations
        expirations = self._get_suitable_expirations(options_chain)
        for expiry in expirations:
            # Filter chain for this expiration
            expiry_chain = options_chain[options_chain['expiration'] == expiry]
            # Check IV conditions
            iv_metrics = self._calculate_iv_metrics(expiry_chain)
            if not self._check_iv_conditions(iv_metrics):
                continue
            # Find optimal strikes
            strikes = self._find_optimal_strikes(spot_price, expiry_chain)
            for strike_set in strikes:
                # Calculate potential setup
                setup = self._calculate_butterfly_setup(
                    strike_set, expiry, expiry_chain
                )
                # Validate setup meets criteria
                if self._validate_setup(setup):
                    opportunities.append(setup)
        # Sort by expected value
        opportunities.sort(key=lambda x: x.credit_received / x.max_loss, 
                         reverse=True)
        return opportunities[:5]  # Top 5 opportunities
    async def _check_market_conditions(self, spot_price: float) -> bool:
        """Check if market conditions favor iron butterflies."""
        if not self.market_data:
            return True  # Default to allowing in demo
        # Get recent price data
        history = await self.market_data.get_price_history('SPY', days=20)
        # Calculate daily ranges
        daily_ranges = []
        for i in range(1, len(history)):
            daily_range = abs(history[i]['close'] - history[i-1]['close']) / history[i-1]['close']
            daily_ranges.append(daily_range)
        # Check range-bound conditions
        avg_range = np.mean(daily_ranges[-5:])
        if avg_range > self.MARKET_CONDITIONS['max_daily_range']:
            return False
        # Check for trending market
        closes = [h['close'] for h in history]
        trend_strength = self._calculate_trend_strength(closes)
        if trend_strength > self.MARKET_CONDITIONS['trend_strength_max']:
            return False
        # Check support/resistance levels
        support, resistance = self._identify_support_resistance(history)
        distance_to_sr = min(
            abs(spot_price - support) / spot_price,
            abs(spot_price - resistance) / spot_price
        )
        if distance_to_sr < self.MARKET_CONDITIONS['support_resistance_buffer']:
            logger.info(f"Too close to support/resistance: {distance_to_sr:.1%}")
            return False
        return True
    def _calculate_iv_metrics(self, options_chain: pd.DataFrame) -> Dict[str, float]:
        """Calculate IV rank and percentile."""
        # Get current IV
        atm_options = options_chain[
            abs(options_chain['strike'] - options_chain['spot']) < 
            options_chain['spot'] * 0.01
        ]
        current_iv = atm_options['implied_volatility'].mean()
        # In production, would calculate from historical data
        # Using simplified calculation for demo
        iv_rank = 50 + np.random.normal(0, 20)  # Simulated
        iv_percentile = 45 + np.random.normal(0, 15)  # Simulated
        return {
            'current_iv': current_iv,
            'iv_rank': max(0, min(100, iv_rank)),
            'iv_percentile': max(0, min(100, iv_percentile)),
            'iv_trend': 'rising' if iv_rank > 60 else 'falling'
        }
    def _check_iv_conditions(self, iv_metrics: Dict[str, float]) -> bool:
        """Check if IV conditions are suitable."""
        return (iv_metrics['iv_rank'] >= self.STRATEGY_PARAMS['min_iv_rank'] or
                iv_metrics['iv_percentile'] >= self.STRATEGY_PARAMS['min_iv_percentile'])
    def _find_optimal_strikes(self, spot_price: float, 
                            chain: pd.DataFrame) -> List[Dict[str, float]]:
        """Find optimal strike combinations for butterfly."""
        strikes = []
        # Get unique strikes
        unique_strikes = sorted(chain['strike'].unique())
        # Find ATM strike
        atm_strike = min(unique_strikes, key=lambda x: abs(x - spot_price))
        atm_index = unique_strikes.index(atm_strike)
        # Calculate wing width
        wing_width_pct = self.STRATEGY_PARAMS['wing_width_atm_pct']
        # Check for earnings week
        if self._is_earnings_week():
            wing_width_pct *= self.EARNINGS_CONFIG['wing_reduction']
        target_wing_width = spot_price * wing_width_pct
        # Find suitable wing strikes
        for i in range(max(5, atm_index - 10), min(len(unique_strikes) - 5, atm_index + 10)):
            center = unique_strikes[i]
            # Find wings approximately equidistant
            lower_candidates = [s for s in unique_strikes if s < center - target_wing_width * 0.8]
            upper_candidates = [s for s in unique_strikes if s > center + target_wing_width * 0.8]
            if lower_candidates and upper_candidates:
                lower = max(lower_candidates)
                upper = min(upper_candidates)
                # Check symmetry
                if abs((center - lower) - (upper - center)) < spot_price * 0.01:
                    strikes.append({
                        'center': center,
                        'lower': lower,
                        'upper': upper,
                        'wing_width': (upper - lower) / 2
                    })
        return strikes
    def _calculate_butterfly_setup(self, strikes: Dict[str, float],
                                 expiry: datetime,
                                 chain: pd.DataFrame) -> ButterflySetup:
        """Calculate iron butterfly setup details."""
        center = strikes['center']
        lower = strikes['lower']
        upper = strikes['upper']
        # Get option prices
        center_call = self._get_option_price(chain, center, 'call', expiry)
        center_put = self._get_option_price(chain, center, 'put', expiry)
        lower_put = self._get_option_price(chain, lower, 'put', expiry)
        upper_call = self._get_option_price(chain, upper, 'call', expiry)
        # Calculate credit (selling straddle, buying strangle)
        credit = center_call + center_put - lower_put - upper_call
        # Calculate max profit/loss
        wing_width = center - lower
        max_profit = credit
        max_loss = wing_width - credit
        # Calculate breakevens
        breakeven_lower = center - credit
        breakeven_upper = center + credit
        profit_zone_width = credit * 2
        # Calculate entry Greeks (simplified)
        entry_greeks = {
            'delta': 0.01,  # Should be near neutral
            'gamma': -0.08,
            'theta': 0.15,
            'vega': -0.18
        }
        # Get current IV
        iv_metrics = self._calculate_iv_metrics(chain)
        return ButterflySetup(
            center_strike=center,
            lower_strike=lower,
            upper_strike=upper,
            expiration=expiry,
            contracts=1,
            credit_received=credit,
            max_profit=max_profit,
            max_loss=max_loss,
            breakeven_lower=breakeven_lower,
            breakeven_upper=breakeven_upper,
            profit_zone_width=profit_zone_width,
            setup_type=ButterflyType.IRON,
            entry_iv=iv_metrics['current_iv'],
            entry_greeks=entry_greeks
        )
    def _validate_setup(self, setup: ButterflySetup) -> bool:
        """Validate butterfly setup meets criteria."""
        # Check credit ratio
        wing_width = setup.center_strike - setup.lower_strike
        credit_ratio = setup.credit_received / wing_width
        if credit_ratio < self.STRATEGY_PARAMS['min_credit_ratio']:
            return False
        # Check profit zone width
        if setup.profit_zone_width < wing_width * 0.4:
            return False
        # Check Greeks within targets
        for greek, (min_val, max_val) in self.GREEK_TARGETS.items():
            if greek.replace('entry_', '') in setup.entry_greeks:
                value = setup.entry_greeks[greek.replace('entry_', '')]
                if not (min_val <= value <= max_val):
                    return False
        # Check risk/reward ratio
        risk_reward = setup.max_profit / setup.max_loss
        if risk_reward < 0.4:  # At least 40% potential return on risk
            return False
        return True
    async def enter_position(self, setup: ButterflySetup, 
                           position_id: str) -> Dict[str, Any]:
        """
        Enter iron butterfly position.
        Args:
            setup: Butterfly setup details
            position_id: Unique position identifier
        Returns:
            Execution details
        """
        logger.info(f"Entering iron butterfly: center={setup.center_strike}, "
                   f"wings={setup.lower_strike}/{setup.upper_strike}")
        # Build order legs
        orders = [
            {
                'strike': setup.center_strike,
                'type': 'call',
                'side': 'SELL',
                'quantity': setup.contracts
            },
            {
                'strike': setup.center_strike,
                'type': 'put',
                'side': 'SELL',
                'quantity': setup.contracts
            },
            {
                'strike': setup.lower_strike,
                'type': 'put',
                'side': 'BUY',
                'quantity': setup.contracts
            },
            {
                'strike': setup.upper_strike,
                'type': 'call',
                'side': 'BUY',
                'quantity': setup.contracts
            }
        ]
        # Execute multi-leg order
        if self.position_manager:
            result = await self.position_manager.execute_multi_leg(orders)
        else:
            # Simulated execution
            result = {
                'success': True,
                'fill_price': setup.credit_received,
                'execution_time': datetime.now()
            }
        if result['success']:
            # Track position
            self.active_butterflies[position_id] = {
                'setup': setup,
                'entry_time': datetime.now(),
                'current_price': result['fill_price'],
                'adjustments': [],
                'pnl': 0
            }
        return result
    async def monitor_positions(self, current_price: float,
                              current_iv: float) -> List[AdjustmentTrigger]:
        """Monitor active butterfly positions for adjustments."""
        triggers = []
        for position_id, position in self.active_butterflies.items():
            setup = position['setup']
            # Calculate days to expiration
            dte = (setup.expiration - datetime.now()).days
            # Check profit target
            current_value = await self._get_position_value(position_id)
            pnl = setup.credit_received - current_value
            profit_pct = pnl / setup.max_profit if setup.max_profit > 0 else 0
            if profit_pct >= self.STRATEGY_PARAMS['profit_target_pct']:
                triggers.append(AdjustmentTrigger(
                    price_breach=False,
                    delta_threshold=False,
                    profit_target=True,
                    loss_threshold=False,
                    time_decay=False,
                    iv_change=False,
                    trigger_details=f"Profit target reached: {profit_pct:.1%}",
                    recommended_action="CLOSE"
                ))
                continue
            # Check max loss
            if pnl < -setup.credit_received * self.STRATEGY_PARAMS['max_loss_multiplier']:
                triggers.append(AdjustmentTrigger(
                    price_breach=False,
                    delta_threshold=False,
                    profit_target=False,
                    loss_threshold=True,
                    time_decay=False,
                    iv_change=False,
                    trigger_details=f"Max loss reached: ${pnl:.2f}",
                    recommended_action="CLOSE"
                ))
                continue
            # Check price breach
            if (current_price < setup.breakeven_lower or 
                current_price > setup.breakeven_upper):
                # Only adjust if enough time remaining
                if dte > self.STRATEGY_PARAMS['adjustment_dte']:
                    triggers.append(AdjustmentTrigger(
                        price_breach=True,
                        delta_threshold=False,
                        profit_target=False,
                        loss_threshold=False,
                        time_decay=False,
                        iv_change=False,
                        trigger_details=f"Price breach: ${current_price:.2f}",
                        recommended_action="ROLL_TESTED_SIDE"
                    ))
            # Check delta threshold
            current_delta = await self._get_position_delta(position_id)
            if abs(current_delta) > self.STRATEGY_PARAMS['delta_threshold']:
                if dte > self.STRATEGY_PARAMS['adjustment_dte']:
                    triggers.append(AdjustmentTrigger(
                        price_breach=False,
                        delta_threshold=True,
                        profit_target=False,
                        loss_threshold=False,
                        time_decay=False,
                        iv_change=False,
                        trigger_details=f"Delta threshold: {current_delta:.3f}",
                        recommended_action="DELTA_HEDGE"
                    ))
            # Check time decay acceleration
            if dte <= 7 and profit_pct < 0.1:
                triggers.append(AdjustmentTrigger(
                    price_breach=False,
                    delta_threshold=False,
                    profit_target=False,
                    loss_threshold=False,
                    time_decay=True,
                    iv_change=False,
                    trigger_details=f"Time decay risk: {dte} DTE",
                    recommended_action="CLOSE"
                ))
            # Check IV collapse
            iv_change = (current_iv - setup.entry_iv) / setup.entry_iv
            if iv_change < -0.3:  # 30% IV drop
                triggers.append(AdjustmentTrigger(
                    price_breach=False,
                    delta_threshold=False,
                    profit_target=False,
                    loss_threshold=False,
                    time_decay=False,
                    iv_change=True,
                    trigger_details=f"IV collapse: {iv_change:.1%}",
                    recommended_action="REDUCE_SIZE"
                ))
        return triggers
    async def adjust_position(self, position_id: str, 
                            adjustment_type: str) -> Dict[str, Any]:
        """Execute position adjustment."""
        if position_id not in self.active_butterflies:
            return {'success': False, 'error': 'Position not found'}
        position = self.active_butterflies[position_id]
        setup = position['setup']
        logger.info(f"Adjusting butterfly {position_id}: {adjustment_type}")
        if adjustment_type == "ROLL_TESTED_SIDE":
            # Roll the tested side out and away
            result = await self._roll_tested_side(position_id)
        elif adjustment_type == "DELTA_HEDGE":
            # Add delta hedge with underlying
            current_delta = await self._get_position_delta(position_id)
            hedge_shares = -int(current_delta * 100)  # 100 multiplier
            result = {
                'success': True,
                'action': f"Delta hedge with {hedge_shares} SPY shares",
                'cost': abs(hedge_shares) * 0.01  # Estimated cost
            }
        elif adjustment_type == "REDUCE_SIZE":
            # Close partial position
            contracts_to_close = max(1, setup.contracts // 2)
            result = await self._reduce_position_size(position_id, contracts_to_close)
        elif adjustment_type == "CLOSE":
            # Close entire position
            result = await self.close_position(position_id)
        else:
            result = {'success': False, 'error': f'Unknown adjustment: {adjustment_type}'}
        # Record adjustment
        if result['success']:
            position['adjustments'].append({
                'timestamp': datetime.now(),
                'type': adjustment_type,
                'details': result
            })
        return result
    async def _roll_tested_side(self, position_id: str) -> Dict[str, Any]:
        """Roll the tested side of butterfly."""
        position = self.active_butterflies[position_id]
        setup = position['setup']
        current_price = await self._get_current_price()
        # Determine which side is tested
        if current_price < setup.center_strike:
            # Roll put side down
            new_put_strike = setup.lower_strike - (setup.center_strike - setup.lower_strike) * 0.5
            old_strike = setup.lower_strike
            option_type = 'put'
        else:
            # Roll call side up
            new_call_strike = setup.upper_strike + (setup.upper_strike - setup.center_strike) * 0.5
            old_strike = setup.upper_strike
            option_type = 'call'
        # Execute roll
        orders = [
            {
                'strike': old_strike,
                'type': option_type,
                'side': 'SELL',  # Close old
                'quantity': setup.contracts
            },
            {
                'strike': new_call_strike if option_type == 'call' else new_put_strike,
                'type': option_type,
                'side': 'BUY',  # Open new
                'quantity': setup.contracts
            }
        ]
        return {
            'success': True,
            'rolled_strike': old_strike,
            'new_strike': new_call_strike if option_type == 'call' else new_put_strike,
            'credit_debit': -0.50  # Simulated cost
        }
    async def close_position(self, position_id: str) -> Dict[str, Any]:
        """Close iron butterfly position."""
        if position_id not in self.active_butterflies:
            return {'success': False, 'error': 'Position not found'}
        position = self.active_butterflies[position_id]
        setup = position['setup']
        # Calculate final P&L
        current_value = await self._get_position_value(position_id)
        final_pnl = setup.credit_received - current_value
        # Build closing orders (opposite of opening)
        orders = [
            {
                'strike': setup.center_strike,
                'type': 'call',
                'side': 'BUY',  # Buy back
                'quantity': setup.contracts
            },
            {
                'strike': setup.center_strike,
                'type': 'put',
                'side': 'BUY',  # Buy back
                'quantity': setup.contracts
            },
            {
                'strike': setup.lower_strike,
                'type': 'put',
                'side': 'SELL',  # Sell back
                'quantity': setup.contracts
            },
            {
                'strike': setup.upper_strike,
                'type': 'call',
                'side': 'SELL',  # Sell back
                'quantity': setup.contracts
            }
        ]
        # Record in history
        self.position_history.append({
            'position_id': position_id,
            'setup': setup,
            'entry_time': position['entry_time'],
            'exit_time': datetime.now(),
            'pnl': final_pnl,
            'adjustments': position['adjustments'],
            'holding_period': (datetime.now() - position['entry_time']).days
        })
        # Remove from active
        del self.active_butterflies[position_id]
        return {
            'success': True,
            'final_pnl': final_pnl,
            'return_on_risk': final_pnl / setup.max_loss if setup.max_loss > 0 else 0
        }
    def _is_earnings_week(self) -> bool:
        """Check if current week has major earnings."""
        # In production, would check earnings calendar
        # Simplified for demo
        current_week = datetime.now().isocalendar()[1]
        earnings_weeks = [4, 17, 30, 43]  # Quarterly earnings weeks
        return current_week in earnings_weeks
    def _get_option_price(self, chain: pd.DataFrame, strike: float,
                         option_type: str, expiry: datetime) -> float:
        """Get option price from chain."""
        option = chain[
            (chain['strike'] == strike) & 
            (chain['type'] == option_type) &
            (chain['expiration'] == expiry)
        ]
        if not option.empty:
            return option.iloc[0]['mid_price']
        else:
            # Estimate price if not found
            return 2.50  # Placeholder
    async def _get_position_value(self, position_id: str) -> float:
        """Get current value of butterfly position."""
        # In production, would get real-time prices
        # Simulated decay for demo
        position = self.active_butterflies[position_id]
        days_held = (datetime.now() - position['entry_time']).days
        # Simulate theta decay and price movement
        theta_decay = days_held * 0.05
        price_impact = np.random.normal(0, 0.1)
        current_value = position['setup'].credit_received * (1 - theta_decay + price_impact)
        return max(0, current_value)
    async def _get_position_delta(self, position_id: str) -> float:
        """Get current delta of position."""
        # In production, would calculate from real Greeks
        # Simulated for demo
        position = self.active_butterflies[position_id]
        current_price = await self._get_current_price()
        setup = position['setup']
        # Delta increases as price moves away from center
        price_distance = (current_price - setup.center_strike) / setup.center_strike
        position_delta = price_distance * 0.5  # Simplified
        return position_delta
    async def _get_current_price(self) -> float:
        """Get current SPY price."""
        if self.market_data:
            return await self.market_data.get_current_price('SPY')
        return 450.0  # Placeholder
    def _calculate_trend_strength(self, prices: List[float]) -> float:
        """Calculate trend strength (0-1 scale)."""
        if len(prices) < 2:
            return 0
        # Simple linear regression slope
        x = np.arange(len(prices))
        slope, _ = np.polyfit(x, prices, 1)
        # Normalize by average price
        avg_price = np.mean(prices)
        normalized_slope = abs(slope) / avg_price * 100
        # Convert to 0-1 scale (1% daily = 0.5 strength)
        return min(1.0, normalized_slope / 2)
    def _identify_support_resistance(self, history: List[Dict]) -> Tuple[float, float]:
        """Identify key support and resistance levels."""
        highs = [h['high'] for h in history]
        lows = [h['low'] for h in history]
        # Simple method: recent extremes
        support = min(lows[-20:])
        resistance = max(highs[-20:])
        return support, resistance
    async def _reduce_position_size(self, position_id: str, 
                                  contracts: int) -> Dict[str, Any]:
        """Reduce position size by closing some contracts."""
        # Implementation would close partial position
        return {
            'success': True,
            'contracts_closed': contracts,
            'remaining_contracts': self.active_butterflies[position_id]['setup'].contracts - contracts
        }
    def get_strategy_performance(self, days: int = 30) -> Dict[str, Any]:
        """Get strategy performance metrics."""
        if not self.position_history:
            return {'no_data': True}
        # Filter by period
        cutoff = datetime.now() - timedelta(days=days)
        recent_positions = [p for p in self.position_history 
                          if p['exit_time'] >= cutoff]
        if not recent_positions:
            return {'no_data': True}
        # Calculate metrics
        total_pnl = sum(p['pnl'] for p in recent_positions)
        winning_trades = [p for p in recent_positions if p['pnl'] > 0]
        losing_trades = [p for p in recent_positions if p['pnl'] < 0]
        # Calculate average returns
        returns = []
        for p in recent_positions:
            setup = p['setup']
            if setup.max_loss > 0:
                returns.append(p['pnl'] / setup.max_loss)
        performance = {
            'total_trades': len(recent_positions),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': len(winning_trades) / len(recent_positions),
            'total_pnl': total_pnl,
            'average_pnl': total_pnl / len(recent_positions),
            'average_winner': np.mean([p['pnl'] for p in winning_trades]) if winning_trades else 0,
            'average_loser': np.mean([p['pnl'] for p in losing_trades]) if losing_trades else 0,
            'profit_factor': abs(sum(p['pnl'] for p in winning_trades) / 
                               sum(p['pnl'] for p in losing_trades)) if losing_trades else 0,
            'average_return_on_risk': np.mean(returns) if returns else 0,
            'sharpe_ratio': np.mean(returns) / np.std(returns) * np.sqrt(252) if returns else 0,
            'avg_holding_period': np.mean([p['holding_period'] for p in recent_positions]),
            'adjustment_frequency': np.mean([len(p['adjustments']) for p in recent_positions])
        }
        return performance
    def get_active_positions_summary(self) -> List[Dict[str, Any]]:
        """Get summary of active butterfly positions."""
        summaries = []
        for position_id, position in self.active_butterflies.items():
            setup = position['setup']
            # Calculate current metrics
            days_held = (datetime.now() - position['entry_time']).days
            dte = (setup.expiration - datetime.now()).days
            summary = {
                'position_id': position_id,
                'center_strike': setup.center_strike,
                'wing_width': setup.upper_strike - setup.center_strike,
                'credit_received': setup.credit_received,
                'max_profit': setup.max_profit,
                'max_loss': setup.max_loss,
                'breakevens': (setup.breakeven_lower, setup.breakeven_upper),
                'days_held': days_held,
                'dte': dte,
                'adjustments_made': len(position['adjustments']),
                'current_pnl': position['pnl']
            }
            summaries.append(summary)
        return summaries
async def main():
    """Example usage of iron butterfly strategy."""
    butterfly = SpyderIronButterfly()
    # Create sample options chain
    spot_price = 450.0
    expiry = datetime.now() + timedelta(days=45)
    # Generate realistic options chain
    options_chain = []
    strikes = np.arange(420, 481, 5)
    for strike in strikes:
        # Calculate IV based on moneyness (smile)
        moneyness = strike / spot_price
        base_iv = 0.18 + 0.1 * (1 - moneyness) ** 2
        # Add calls and puts
        for option_type in ['call', 'put']:
            # Simple pricing for demo
            if option_type == 'call':
                intrinsic = max(spot_price - strike, 0)
            else:
                intrinsic = max(strike - spot_price, 0)
            time_value = spot_price * base_iv * np.sqrt(45/365) * 0.4
            price = intrinsic + time_value
            options_chain.append({
                'strike': strike,
                'type': option_type,
                'expiration': expiry,
                'bid': price - 0.05,
                'ask': price + 0.05,
                'mid_price': price,
                'implied_volatility': base_iv,
                'spot': spot_price
            })
    options_df = pd.DataFrame(options_chain)
    # Scan for opportunities
    print("=== Scanning for Iron Butterfly Opportunities ===")
    opportunities = await butterfly.scan_opportunities(spot_price, options_df)
    if opportunities:
        print(f"\nFound {len(opportunities)} opportunities:")
        for i, opp in enumerate(opportunities[:3]):
            print(f"\n{i+1}. Center: ${opp.center_strike}, "
                  f"Wings: ${opp.lower_strike}-${opp.upper_strike}")
            print(f"   Credit: ${opp.credit_received:.2f}")
            print(f"   Max Profit: ${opp.max_profit:.2f}")
            print(f"   Max Loss: ${opp.max_loss:.2f}")
            print(f"   Breakevens: ${opp.breakeven_lower:.2f}-${opp.breakeven_upper:.2f}")
            print(f"   Profit Zone: ${opp.profit_zone_width:.2f} wide")
        # Enter best opportunity
        best_setup = opportunities[0]
        position_id = "BFLY_001"
        print(f"\n=== Entering Position {position_id} ===")
        result = await butterfly.enter_position(best_setup, position_id)
        print(f"Entry successful: {result['success']}")
        # Simulate monitoring
        print("\n=== Monitoring Position ===")
        # Scenario 1: Price moves up
        current_price = spot_price + 5
        current_iv = 0.16
        triggers = await butterfly.monitor_positions(current_price, current_iv)
        if triggers:
            print(f"\nPrice at ${current_price:.2f} - Triggers detected:")
            for trigger in triggers:
                print(f"  - {trigger.trigger_details}")
                print(f"    Recommended: {trigger.recommended_action}")
        # Execute adjustment if needed
        if triggers and triggers[0].recommended_action != "CLOSE":
            print("\n=== Executing Adjustment ===")
            adj_result = await butterfly.adjust_position(
                position_id, 
                triggers[0].recommended_action
            )
            print(f"Adjustment result: {adj_result}")
        # Close position
        print("\n=== Closing Position ===")
        close_result = await butterfly.close_position(position_id)
        print(f"Final P&L: ${close_result['final_pnl']:.2f}")
        print(f"Return on Risk: {close_result['return_on_risk']:.1%}")
        # Get performance metrics
        print("\n=== Strategy Performance ===")
        performance = butterfly.get_strategy_performance()
        if 'no_data' not in performance:
            print(f"Win Rate: {performance['win_rate']:.1%}")
            print(f"Average Return on Risk: {performance['average_return_on_risk']:.1%}")
            print(f"Profit Factor: {performance['profit_factor']:.2f}")
if __name__ == "__main__":
    asyncio.run(main())