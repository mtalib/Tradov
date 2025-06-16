#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderD14_GreeksBasedStrategy.py
Group: D (Trading Strategies)
Purpose: High-speed trading strategy leveraging OPRA Greeks

Description:
    This module implements trading strategies that leverage pre-calculated Greeks
    from OPRA feeds for ultra-fast decision making. It includes delta-neutral
    strategies, gamma scalping, and Greek-based arbitrage detection, all executing
    with minimal latency due to elimination of Greeks calculation overhead.

Author: Mohamed Talib
Date: 2025-06-13
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
import time
import numpy as np
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum, auto
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU07_Constants import OptionType, OrderType, OrderAction
from SpyderD_Strategies.SpyderD01_BaseStrategy import BaseStrategy, TradingSignal, SignalType
from SpyderN_OptionsAnalytics.SpyderN07_OPRAGreeksHandler import (
    OPRAGreeksHandler, ValidatedGreeks, PortfolioGreeks
)
from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
from SpyderB_Broker.SpyderB01_IBClient import IBClient

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Strategy parameters
DELTA_NEUTRAL_THRESHOLD = 10.0  # Delta threshold for rebalancing
GAMMA_SCALP_THRESHOLD = 100.0   # Minimum gamma for scalping
THETA_HARVEST_MIN = 50.0        # Minimum daily theta to harvest
VEGA_NEUTRAL_THRESHOLD = 50.0   # Vega threshold

# Greek limits
MAX_PORTFOLIO_DELTA = 100.0
MAX_PORTFOLIO_GAMMA = 500.0
MAX_PORTFOLIO_VEGA = 1000.0
MAX_DAILY_THETA = -2000.0  # Maximum theta burn

# Execution parameters
MIN_EDGE_REQUIRED = 0.05  # 5 cents minimum edge
GREEK_ARBITRAGE_THRESHOLD = 0.02  # 2% Greek mispricing
REBALANCE_FREQUENCY = 60  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class GreekStrategyType(Enum):
    """Types of Greek-based strategies"""
    DELTA_NEUTRAL = auto()
    GAMMA_SCALPING = auto()
    THETA_HARVESTING = auto()
    VEGA_TRADING = auto()
    GREEK_ARBITRAGE = auto()
    DISPERSION = auto()

class RebalanceReason(Enum):
    """Reasons for portfolio rebalancing"""
    DELTA_DRIFT = auto()
    GAMMA_OPPORTUNITY = auto()
    RISK_LIMIT = auto()
    MARKET_MOVE = auto()
    TIME_BASED = auto()
    GREEK_ARBITRAGE = auto()

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GreekExposure:
    """Current Greek exposures"""
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    
    delta_dollars: float
    gamma_dollars: float
    theta_dollars: float
    vega_dollars: float
    
    # By expiry
    delta_by_expiry: Dict[datetime.date, float]
    gamma_by_expiry: Dict[datetime.date, float]
    
    # Risk metrics
    gamma_risk: float  # 1% move impact
    vega_risk: float   # 1 vol point impact
    var_95: float      # 95% VaR

@dataclass
class GreekOpportunity:
    """Trading opportunity based on Greeks"""
    strategy_type: GreekStrategyType
    symbols: List[str]
    action: str  # 'buy', 'sell', 'spread'
    rationale: str
    expected_edge: float
    greek_edge: Dict[str, float]  # Edge from each Greek
    confidence: float
    urgency: float  # 0-1 scale

@dataclass
class GammaScalpSetup:
    """Gamma scalping setup"""
    symbol: str
    current_gamma: float
    hedge_ratio: float
    rebalance_threshold: float  # Price move to trigger rebalance
    last_hedge_price: float
    shares_to_trade: int
    expected_profit: float

# ==============================================================================
# GREEKS-BASED STRATEGY CLASS
# ==============================================================================
class GreeksBasedStrategy(BaseStrategy):
    """
    High-speed trading strategy using OPRA Greeks.
    
    This strategy leverages pre-calculated Greeks for instant decision making,
    enabling delta-neutral trading, gamma scalping, and Greek arbitrage with
    minimal latency.
    """
    
    def __init__(
        self,
        opra_handler: OPRAGreeksHandler,
        risk_manager: RiskManager,
        ib_client: IBClient,
        logger: Optional[SpyderLogger] = None,
        error_handler: Optional[SpyderErrorHandler] = None
    ):
        """Initialize Greeks-based strategy"""
        super().__init__(logger, error_handler)
        
        self.opra_handler = opra_handler
        self.risk_manager = risk_manager
        self.ib_client = ib_client
        
        # Strategy configuration
        self.enabled_strategies = {
            GreekStrategyType.DELTA_NEUTRAL: True,
            GreekStrategyType.GAMMA_SCALPING: True,
            GreekStrategyType.THETA_HARVESTING: True,
            GreekStrategyType.VEGA_TRADING: False,
            GreekStrategyType.GREEK_ARBITRAGE: True,
            GreekStrategyType.DISPERSION: False
        }
        
        # Portfolio state
        self.current_positions: Dict[str, float] = {}
        self.portfolio_greeks: Optional[PortfolioGreeks] = None
        self.last_rebalance_time = time.time()
        
        # Gamma scalping state
        self.gamma_scalp_setups: Dict[str, GammaScalpSetup] = {}
        self.hedge_positions: Dict[str, float] = {}  # SPY shares for hedging
        
        # Performance tracking
        self.scalp_pnl = 0.0
        self.theta_collected = 0.0
        self.rebalance_count = 0
        
        # Real-time monitoring
        self.monitoring_thread = threading.Thread(target=self._monitor_greeks)
        self.monitoring_thread.daemon = True
        self.monitoring_active = True
        
        self.logger.info("Greeks-Based Strategy initialized")
    
    # ==========================================================================
    # MAIN STRATEGY METHODS
    # ==========================================================================
    def scan_opportunities(self) -> List[TradingSignal]:
        """Scan for Greek-based trading opportunities"""
        opportunities = []
        
        try:
            # Update portfolio Greeks
            self._update_portfolio_greeks()
            
            # Check each enabled strategy
            if self.enabled_strategies[GreekStrategyType.DELTA_NEUTRAL]:
                opportunities.extend(self._scan_delta_neutral())
            
            if self.enabled_strategies[GreekStrategyType.GAMMA_SCALPING]:
                opportunities.extend(self._scan_gamma_scalping())
            
            if self.enabled_strategies[GreekStrategyType.THETA_HARVESTING]:
                opportunities.extend(self._scan_theta_harvesting())
            
            if self.enabled_strategies[GreekStrategyType.GREEK_ARBITRAGE]:
                opportunities.extend(self._scan_greek_arbitrage())
            
            # Filter and rank opportunities
            valid_opportunities = self._filter_opportunities(opportunities)
            ranked_opportunities = self._rank_opportunities(valid_opportunities)
            
            return ranked_opportunities[:5]  # Top 5 opportunities
            
        except Exception as e:
            self.logger.error(f"Error scanning opportunities: {e}")
            self.error_handler.handle_error(e)
            return []
    
    def execute_strategy(self) -> List[Dict[str, Any]]:
        """Execute Greeks-based strategy"""
        execution_results = []
        
        # Check if rebalancing needed
        if self._needs_rebalancing():
            rebalance_orders = self._rebalance_portfolio()
            execution_results.extend(rebalance_orders)
        
        # Scan for new opportunities
        opportunities = self.scan_opportunities()
        
        for signal in opportunities:
            if self.should_execute(signal):
                result = self._execute_signal(signal)
                execution_results.append(result)
        
        # Update gamma scalping positions
        if self.gamma_scalp_setups:
            scalp_orders = self._update_gamma_scalps()
            execution_results.extend(scalp_orders)
        
        return execution_results
    
    # ==========================================================================
    # DELTA NEUTRAL STRATEGY
    # ==========================================================================
    def _scan_delta_neutral(self) -> List[TradingSignal]:
        """Scan for delta neutral opportunities"""
        signals = []
        
        if not self.portfolio_greeks:
            return signals
        
        # Check current delta exposure
        current_delta = self.portfolio_greeks.total_delta
        
        if abs(current_delta) > DELTA_NEUTRAL_THRESHOLD:
            # Need to neutralize delta
            hedge_signal = self._create_delta_hedge_signal(current_delta)
            if hedge_signal:
                signals.append(hedge_signal)
        
        # Look for delta-neutral spread opportunities
        spread_opportunities = self._find_delta_neutral_spreads()
        signals.extend(spread_opportunities)
        
        return signals
    
    def _create_delta_hedge_signal(self, delta_to_hedge: float) -> Optional[TradingSignal]:
        """Create signal to hedge delta exposure"""
        # Find best hedging instrument
        hedge_options = self._find_hedge_options(-delta_to_hedge)
        
        if not hedge_options:
            # Use SPY shares as hedge
            shares_needed = round(-delta_to_hedge)
            if abs(shares_needed) > 10:
                return TradingSignal(
                    signal_type=SignalType.HEDGE,
                    symbol="SPY",
                    action=OrderAction.BUY if shares_needed > 0 else OrderAction.SELL,
                    quantity=abs(shares_needed),
                    order_type=OrderType.MARKET,
                    reason=f"Delta hedge: {delta_to_hedge:.1f} delta exposure",
                    confidence=0.95,
                    urgency=0.8,
                    metadata={
                        'hedge_type': 'delta',
                        'current_delta': delta_to_hedge,
                        'strategy': 'delta_neutral'
                    }
                )
        
        # Use options for hedging
        best_option = hedge_options[0]
        contracts_needed = round(-delta_to_hedge / (best_option['delta'] * 100))
        
        if abs(contracts_needed) > 0:
            return TradingSignal(
                signal_type=SignalType.ENTRY,
                symbol=best_option['symbol'],
                action=OrderAction.BUY if contracts_needed > 0 else OrderAction.SELL,
                quantity=abs(contracts_needed),
                order_type=OrderType.LIMIT,
                limit_price=best_option['mid_price'],
                reason=f"Delta hedge via options: {delta_to_hedge:.1f} delta",
                confidence=0.85,
                urgency=0.7,
                metadata={
                    'hedge_type': 'delta_options',
                    'option_delta': best_option['delta'],
                    'contracts': contracts_needed
                }
            )
        
        return None
    
    # ==========================================================================
    # GAMMA SCALPING STRATEGY
    # ==========================================================================
    def _scan_gamma_scalping(self) -> List[TradingSignal]:
        """Scan for gamma scalping opportunities"""
        signals = []
        
        # Look for high gamma positions to establish
        high_gamma_options = self._find_high_gamma_options()
        
        for option in high_gamma_options:
            if option['gamma'] > GAMMA_SCALP_THRESHOLD / 100:  # Convert to per-share
                
                # Check if we should enter gamma scalp
                setup = self._analyze_gamma_scalp(option)
                if setup and setup.expected_profit > 50:  # $50 minimum expected profit
                    
                    signal = TradingSignal(
                        signal_type=SignalType.ENTRY,
                        symbol=option['symbol'],
                        action=OrderAction.BUY,
                        quantity=10,  # Start with 10 contracts
                        order_type=OrderType.LIMIT,
                        limit_price=option['ask'],
                        reason=f"Gamma scalp setup: {option['gamma']:.3f} gamma",
                        confidence=0.75,
                        urgency=0.6,
                        metadata={
                            'strategy': 'gamma_scalping',
                            'gamma': option['gamma'],
                            'expected_profit': setup.expected_profit,
                            'rebalance_threshold': setup.rebalance_threshold
                        }
                    )
                    signals.append(signal)
        
        return signals
    
    def _update_gamma_scalps(self) -> List[Dict[str, Any]]:
        """Update gamma scalping positions"""
        orders = []
        spot_price = self._get_spot_price()
        
        for symbol, setup in self.gamma_scalp_setups.items():
            # Check if rebalance needed
            price_move = abs(spot_price - setup.last_hedge_price)
            
            if price_move >= setup.rebalance_threshold:
                # Calculate hedge adjustment
                position_delta = self._get_position_delta(symbol)
                hedge_shares = round(-position_delta)
                
                if abs(hedge_shares) > 10:
                    order = {
                        'symbol': 'SPY',
                        'action': 'BUY' if hedge_shares > 0 else 'SELL',
                        'quantity': abs(hedge_shares),
                        'order_type': 'MARKET',
                        'reason': f'Gamma scalp rebalance for {symbol}',
                        'metadata': {
                            'parent_symbol': symbol,
                            'price_move': price_move,
                            'current_gamma': setup.current_gamma
                        }
                    }
                    orders.append(order)
                    
                    # Update setup
                    setup.last_hedge_price = spot_price
                    setup.shares_to_trade = hedge_shares
                    
                    # Track P&L
                    self.scalp_pnl += self._estimate_scalp_profit(setup, price_move)
        
        return orders
    
    # ==========================================================================
    # THETA HARVESTING STRATEGY
    # ==========================================================================
    def _scan_theta_harvesting(self) -> List[TradingSignal]:
        """Scan for theta harvesting opportunities"""
        signals = []
        
        # Find high theta options to sell
        high_theta_options = self._find_high_theta_options()
        
        for option in high_theta_options:
            # Check if theta is attractive
            daily_theta = option['theta'] * 100  # Per contract
            
            if daily_theta < -THETA_HARVEST_MIN:  # Negative theta for short positions
                
                # Analyze risk/reward
                if self._analyze_theta_risk_reward(option):
                    signal = TradingSignal(
                        signal_type=SignalType.ENTRY,
                        symbol=option['symbol'],
                        action=OrderAction.SELL,
                        quantity=5,  # Conservative position size
                        order_type=OrderType.LIMIT,
                        limit_price=option['bid'],
                        reason=f"Theta harvest: ${-daily_theta:.2f}/day",
                        confidence=0.70,
                        urgency=0.5,
                        metadata={
                            'strategy': 'theta_harvesting',
                            'daily_theta': daily_theta,
                            'days_to_expiry': option['days_to_expiry'],
                            'iv_rank': option.get('iv_rank', 0)
                        }
                    )
                    signals.append(signal)
        
        return signals
    
    # ==========================================================================
    # GREEK ARBITRAGE STRATEGY
    # ==========================================================================
    def _scan_greek_arbitrage(self) -> List[TradingSignal]:
        """Scan for Greek-based arbitrage opportunities"""
        signals = []
        
        # Get Greek anomalies from OPRA handler
        anomalies = self.opra_handler.find_greek_anomalies()
        
        for anomaly in anomalies:
            if anomaly['type'] == 'butterfly_gamma_violation':
                # Create butterfly arbitrage trade
                signal = self._create_butterfly_arbitrage_signal(anomaly)
                if signal:
                    signals.append(signal)
                    
            elif anomaly['type'] == 'negative_gamma':
                # This should never happen - investigate
                self.logger.warning(f"Negative gamma detected: {anomaly}")
                
            elif anomaly['type'] == 'greek_mismatch':
                # Greeks don't match theoretical values
                signal = self._create_greek_mismatch_signal(anomaly)
                if signal:
                    signals.append(signal)
        
        # Check for volatility arbitrage using vega
        vega_arb_signals = self._scan_vega_arbitrage()
        signals.extend(vega_arb_signals)
        
        return signals
    
    # ==========================================================================
    # PORTFOLIO MANAGEMENT
    # ==========================================================================
    def _needs_rebalancing(self) -> bool:
        """Check if portfolio needs rebalancing"""
        if not self.portfolio_greeks:
            return False
        
        # Time-based check
        time_since_rebalance = time.time() - self.last_rebalance_time
        if time_since_rebalance < REBALANCE_FREQUENCY:
            return False
        
        # Delta drift check
        if abs(self.portfolio_greeks.total_delta) > DELTA_NEUTRAL_THRESHOLD:
            return True
        
        # Risk limit checks
        if abs(self.portfolio_greeks.total_gamma) > MAX_PORTFOLIO_GAMMA:
            return True
        
        if abs(self.portfolio_greeks.total_vega) > MAX_PORTFOLIO_VEGA:
            return True
        
        if self.portfolio_greeks.total_theta < MAX_DAILY_THETA:
            return True
        
        return False
    
    def _rebalance_portfolio(self) -> List[Dict[str, Any]]:
        """Rebalance portfolio to maintain Greek targets"""
        orders = []
        
        self.logger.info(f"Rebalancing portfolio - Delta: {self.portfolio_greeks.total_delta:.1f}, "
                        f"Gamma: {self.portfolio_greeks.total_gamma:.1f}")
        
        # Delta rebalancing
        if abs(self.portfolio_greeks.total_delta) > DELTA_NEUTRAL_THRESHOLD:
            delta_orders = self._rebalance_delta()
            orders.extend(delta_orders)
        
        # Gamma rebalancing
        if abs(self.portfolio_greeks.total_gamma) > MAX_PORTFOLIO_GAMMA:
            gamma_orders = self._rebalance_gamma()
            orders.extend(gamma_orders)
        
        # Update rebalance time
        self.last_rebalance_time = time.time()
        self.rebalance_count += 1
        
        return orders
    
    def _update_portfolio_greeks(self):
        """Update portfolio Greeks from current positions"""
        if not self.current_positions:
            self.portfolio_greeks = None
            return
        
        self.portfolio_greeks = self.opra_handler.calculate_portfolio_greeks(
            self.current_positions
        )
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _find_high_gamma_options(self) -> List[Dict[str, Any]]:
        """Find options with high gamma for scalping"""
        high_gamma = []
        
        # Get ATM options for each expiry
        for expiry in self._get_active_expiries():
            surface = self.opra_handler.get_greek_surface(expiry, 'gamma')
            if surface.empty:
                continue
            
            # Find highest gamma strikes
            top_gamma = surface.nlargest(5, 'gamma')
            
            for _, row in top_gamma.iterrows():
                if row['gamma'] > 0.01:  # Minimum gamma threshold
                    high_gamma.append({
                        'symbol': self._construct_symbol(row['strike'], expiry, row['type']),
                        'strike': row['strike'],
                        'gamma': row['gamma'],
                        'delta': self._get_option_greek(row['strike'], expiry, row['type'], 'delta'),
                        'bid': row['bid'],
                        'ask': row['ask'],
                        'mid_price': (row['bid'] + row['ask']) / 2,
                        'days_to_expiry': (expiry - datetime.date.today()).days
                    })
        
        return sorted(high_gamma, key=lambda x: x['gamma'], reverse=True)
    
    def _find_high_theta_options(self) -> List[Dict[str, Any]]:
        """Find options with high theta for harvesting"""
        high_theta = []
        
        # Focus on near-term expiries
        for expiry in self._get_active_expiries():
            days_to_expiry = (expiry - datetime.date.today()).days
            if days_to_expiry > 45:  # Skip far-dated options
                continue
            
            surface = self.opra_handler.get_greek_surface(expiry, 'theta')
            if surface.empty:
                continue
            
            # Find OTM options with high theta
            spot_price = self._get_spot_price()
            otm_puts = surface[(surface['type'] == 'P') & (surface['strike'] < spot_price * 0.95)]
            otm_calls = surface[(surface['type'] == 'C') & (surface['strike'] > spot_price * 1.05)]
            
            for df in [otm_puts, otm_calls]:
                top_theta = df.nsmallest(3, 'theta')  # Most negative theta
                
                for _, row in top_theta.iterrows():
                    high_theta.append({
                        'symbol': self._construct_symbol(row['strike'], expiry, row['type']),
                        'strike': row['strike'],
                        'theta': row['theta'],
                        'delta': self._get_option_greek(row['strike'], expiry, row['type'], 'delta'),
                        'gamma': self._get_option_greek(row['strike'], expiry, row['type'], 'gamma'),
                        'bid': row['bid'],
                        'ask': row['ask'],
                        'iv': row['iv'],
                        'days_to_expiry': days_to_expiry
                    })
        
        return high_theta
    
    def _analyze_gamma_scalp(self, option: Dict[str, Any]) -> Optional[GammaScalpSetup]:
        """Analyze gamma scalping opportunity"""
        spot_price = self._get_spot_price()
        gamma_dollars = option['gamma'] * 100 * spot_price  # Per contract
        
        # Calculate rebalance threshold (when delta changes by ~50)
        rebalance_threshold = 50 / (option['gamma'] * 100) if option['gamma'] > 0 else 5.0
        
        # Estimate profit potential (simplified)
        daily_vol = self._get_realized_volatility() * spot_price / np.sqrt(252)
        expected_moves = 2  # Expect 2 rebalances per day
        expected_profit = 0.5 * gamma_dollars * (daily_vol ** 2) * expected_moves
        
        if expected_profit > 0:
            return GammaScalpSetup(
                symbol=option['symbol'],
                current_gamma=option['gamma'],
                hedge_ratio=option['delta'],
                rebalance_threshold=rebalance_threshold,
                last_hedge_price=spot_price,
                shares_to_trade=0,
                expected_profit=expected_profit
            )
        
        return None
    
    def _analyze_theta_risk_reward(self, option: Dict[str, Any]) -> bool:
        """Analyze risk/reward for theta harvesting"""
        # Check if IV is elevated
        if option.get('iv', 0) < 0.15:  # Below 15% IV
            return False
        
        # Check risk metrics
        max_loss = option['ask'] * 100 * 5  # 5 contracts
        daily_theta = -option['theta'] * 100 * 5
        days_to_expiry = option['days_to_expiry']
        
        # Need to collect at least 20% of max loss in theta
        total_theta = daily_theta * min(days_to_expiry, 10)  # 10 days max
        
        return total_theta >= max_loss * 0.20
    
    def _monitor_greeks(self):
        """Background thread to monitor Greeks"""
        while self.monitoring_active:
            try:
                # Update portfolio Greeks
                self._update_portfolio_greeks()
                
                if self.portfolio_greeks:
                    # Log current exposures
                    if abs(self.portfolio_greeks.total_delta) > 50:
                        self.logger.info(f"Delta exposure: {self.portfolio_greeks.total_delta:.1f}")
                    
                    if abs(self.portfolio_greeks.total_gamma) > 200:
                        self.logger.info(f"Gamma exposure: {self.portfolio_greeks.total_gamma:.1f}")
                    
                    # Check risk limits
                    self._check_greek_limits()
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in Greeks monitoring: {e}")
    
    def _check_greek_limits(self):
        """Check if Greek exposures exceed limits"""
        if abs(self.portfolio_greeks.total_delta) > MAX_PORTFOLIO_DELTA * 1.2:
            self.logger.warning(f"DELTA LIMIT EXCEEDED: {self.portfolio_greeks.total_delta:.1f}")
            self._emergency_hedge('delta')
        
        if abs(self.portfolio_greeks.total_gamma) > MAX_PORTFOLIO_GAMMA * 1.2:
            self.logger.warning(f"GAMMA LIMIT EXCEEDED: {self.portfolio_greeks.total_gamma:.1f}")
            self._emergency_hedge('gamma')
    
    def _get_spot_price(self) -> float:
        """Get current SPY price"""
        # This would get real price from market data
        return 450.0
    
    def _get_realized_volatility(self) -> float:
        """Get realized volatility"""
        # This would calculate from recent price moves
        return 0.15
    
    def _get_active_expiries(self) -> List[datetime.date]:
        """Get list of active expiration dates"""
        # This would come from market data
        today = datetime.date.today()
        return [
            today + datetime.timedelta(days=1),   # 0DTE
            today + datetime.timedelta(days=7),   # Weekly
            today + datetime.timedelta(days=30),  # Monthly
        ]
    
    def _construct_symbol(self, strike: float, expiry: datetime.date, 
                         option_type: str) -> str:
        """Construct option symbol from components"""
        # Format: SPYYYMMDDCP00000000
        expiry_str = expiry.strftime('%y%m%d')
        strike_str = f"{int(strike * 1000):08d}"
        return f"SPY{expiry_str}{option_type}{strike_str}"
    
    def _get_option_greek(self, strike: float, expiry: datetime.date, 
                         option_type: str, greek: str) -> float:
        """Get specific Greek for an option"""
        symbol = self._construct_symbol(strike, expiry, option_type)
        if symbol in self.opra_handler.validated_greeks:
            return getattr(self.opra_handler.validated_greeks[symbol], greek, 0.0)
        return 0.0
    
    def _get_position_delta(self, symbol: str) -> float:
        """Get delta exposure for a position"""
        if symbol not in self.current_positions:
            return 0.0
        
        position = self.current_positions[symbol]
        if symbol in self.opra_handler.validated_greeks:
            option_delta = self.opra_handler.validated_greeks[symbol].delta
            return position * option_delta * 100  # Position * delta * multiplier
        return 0.0
    
    def _estimate_scalp_profit(self, setup: GammaScalpSetup, price_move: float) -> float:
        """Estimate profit from gamma scalp rebalance"""
        # Profit ≈ 0.5 * Gamma * (Price Move)^2 * Position Size
        return 0.5 * setup.current_gamma * (price_move ** 2) * 100 * 10  # 10 contracts
    
    def _create_butterfly_arbitrage_signal(self, anomaly: Dict) -> Optional[TradingSignal]:
        """Create butterfly arbitrage signal"""
        strikes = anomaly['strikes']
        
        # Butterfly: Buy 1 low, Sell 2 middle, Buy 1 high
        # All same expiry and type
        
        return TradingSignal(
            signal_type=SignalType.ARBITRAGE,
            symbol=f"BUTTERFLY_{strikes[1]}",  # Middle strike identifier
            action=OrderAction.BUY,  # Butterfly spread
            quantity=1,  # 1 unit of spread
            order_type=OrderType.LIMIT,
            reason=f"Butterfly arbitrage: strikes {strikes}",
            confidence=0.85,
            urgency=0.9,  # High urgency for arbitrage
            metadata={
                'strategy': 'butterfly_arbitrage',
                'strikes': strikes,
                'legs': [
                    {'strike': strikes[0], 'action': 'buy', 'quantity': 1},
                    {'strike': strikes[1], 'action': 'sell', 'quantity': 2},
                    {'strike': strikes[2], 'action': 'buy', 'quantity': 1}
                ],
                'anomaly_type': anomaly['type']
            }
        )
    
    def _create_greek_mismatch_signal(self, anomaly: Dict) -> Optional[TradingSignal]:
        """Create signal for Greek mismatch opportunity"""
        if anomaly.get('mispricing_amount', 0) < MIN_EDGE_REQUIRED:
            return None
        
        return TradingSignal(
            signal_type=SignalType.ENTRY,
            symbol=anomaly['symbol'],
            action=OrderAction.BUY if anomaly['underpriced'] else OrderAction.SELL,
            quantity=5,
            order_type=OrderType.LIMIT,
            limit_price=anomaly['current_price'],
            reason=f"Greek mismatch: {anomaly.get('mispricing_amount', 0):.2f} edge",
            confidence=0.75,
            urgency=0.8,
            metadata={
                'strategy': 'greek_mismatch',
                'theoretical_value': anomaly.get('theoretical_value'),
                'current_greeks': anomaly.get('current_greeks'),
                'expected_greeks': anomaly.get('expected_greeks')
            }
        )
    
    def _scan_vega_arbitrage(self) -> List[TradingSignal]:
        """Scan for volatility arbitrage using vega"""
        signals = []
        
        # Compare implied vs realized volatility
        realized_vol = self._get_realized_volatility()
        
        # Get term structure of implied volatility
        for expiry in self._get_active_expiries():
            surface = self.opra_handler.get_greek_surface(expiry, 'vega')
            if surface.empty:
                continue
            
            # Find high IV options relative to realized
            atm_options = surface[abs(surface['strike'] / self._get_spot_price() - 1) < 0.02]
            
            for _, row in atm_options.iterrows():
                iv = row['iv']
                if iv > realized_vol * 1.3:  # IV 30% higher than realized
                    # Sell volatility
                    signal = TradingSignal(
                        signal_type=SignalType.ENTRY,
                        symbol=self._construct_symbol(row['strike'], expiry, row['type']),
                        action=OrderAction.SELL,
                        quantity=10,
                        order_type=OrderType.LIMIT,
                        limit_price=row['bid'],
                        reason=f"Vega arbitrage: IV {iv:.1%} vs RV {realized_vol:.1%}",
                        confidence=0.70,
                        urgency=0.6,
                        metadata={
                            'strategy': 'vega_arbitrage',
                            'implied_vol': iv,
                            'realized_vol': realized_vol,
                            'vega': row.get('vega', 0),
                            'edge': (iv - realized_vol) * row.get('vega', 0) * 100
                        }
                    )
                    signals.append(signal)
        
        return signals
    
    def _find_hedge_options(self, target_delta: float) -> List[Dict[str, Any]]:
        """Find options to hedge specific delta amount"""
        hedge_candidates = []
        
        for expiry in self._get_active_expiries()[:2]:  # Use near-term only
            # Get all options for this expiry
            calls = self.opra_handler.get_greek_surface(expiry, 'delta')
            
            if not calls.empty:
                # Filter by delta efficiency
                for _, row in calls.iterrows():
                    if row['delta'] * target_delta > 0:  # Same sign
                        contracts_needed = target_delta / (row['delta'] * 100)
                        if 1 <= abs(contracts_needed) <= 20:  # Reasonable size
                            hedge_candidates.append({
                                'symbol': self._construct_symbol(row['strike'], expiry, row['type']),
                                'delta': row['delta'],
                                'contracts_needed': contracts_needed,
                                'bid': row['bid'],
                                'ask': row['ask'],
                                'mid_price': (row['bid'] + row['ask']) / 2,
                                'cost': abs(contracts_needed) * row['ask'] * 100
                            })
        
        # Sort by cost efficiency
        return sorted(hedge_candidates, key=lambda x: x['cost'])
    
    def _rebalance_delta(self) -> List[Dict[str, Any]]:
        """Rebalance delta exposure"""
        orders = []
        target_delta = 0  # Delta neutral target
        current_delta = self.portfolio_greeks.total_delta
        delta_to_hedge = target_delta - current_delta
        
        if abs(delta_to_hedge) > DELTA_NEUTRAL_THRESHOLD:
            # Use SPY shares for precise hedging
            shares = round(delta_to_hedge)
            if shares != 0:
                orders.append({
                    'symbol': 'SPY',
                    'action': 'BUY' if shares > 0 else 'SELL',
                    'quantity': abs(shares),
                    'order_type': 'MARKET',
                    'reason': f'Delta rebalance: {current_delta:.1f} -> {target_delta}',
                    'metadata': {
                        'rebalance_type': 'delta',
                        'current_delta': current_delta,
                        'target_delta': target_delta
                    }
                })
        
        return orders
    
    def _rebalance_gamma(self) -> List[Dict[str, Any]]:
        """Rebalance gamma exposure"""
        orders = []
        current_gamma = self.portfolio_greeks.total_gamma
        
        if abs(current_gamma) > MAX_PORTFOLIO_GAMMA:
            # Reduce gamma by closing some positions
            positions_by_gamma = []
            
            for symbol, position in self.current_positions.items():
                if symbol in self.opra_handler.validated_greeks:
                    greeks = self.opra_handler.validated_greeks[symbol]
                    position_gamma = greeks.gamma * position * 100
                    positions_by_gamma.append({
                        'symbol': symbol,
                        'position': position,
                        'gamma': position_gamma,
                        'abs_gamma': abs(position_gamma)
                    })
            
            # Sort by absolute gamma contribution
            positions_by_gamma.sort(key=lambda x: x['abs_gamma'], reverse=True)
            
            # Close highest gamma positions until within limit
            remaining_gamma = current_gamma
            for pos in positions_by_gamma:
                if abs(remaining_gamma) <= MAX_PORTFOLIO_GAMMA:
                    break
                
                # Close position
                orders.append({
                    'symbol': pos['symbol'],
                    'action': 'SELL' if pos['position'] > 0 else 'BUY',
                    'quantity': abs(pos['position']),
                    'order_type': 'MARKET',
                    'reason': f'Gamma reduction: {pos["gamma"]:.1f} gamma',
                    'metadata': {
                        'rebalance_type': 'gamma',
                        'position_gamma': pos['gamma'],
                        'total_gamma': current_gamma
                    }
                })
                
                remaining_gamma -= pos['gamma']
        
        return orders
    
    def _emergency_hedge(self, greek_type: str):
        """Emergency hedge when limits exceeded"""
        self.logger.warning(f"EMERGENCY HEDGE TRIGGERED: {greek_type}")
        
        if greek_type == 'delta':
            # Immediate delta hedge with SPY
            shares = round(-self.portfolio_greeks.total_delta)
            if shares != 0:
                self.ib_client.place_order(
                    symbol='SPY',
                    action='BUY' if shares > 0 else 'SELL',
                    quantity=abs(shares),
                    order_type='MARKET'
                )
        
        elif greek_type == 'gamma':
            # Close largest gamma position
            max_gamma_symbol = None
            max_gamma = 0
            
            for symbol, position in self.current_positions.items():
                if symbol in self.opra_handler.validated_greeks:
                    pos_gamma = abs(self.opra_handler.validated_greeks[symbol].gamma * position * 100)
                    if pos_gamma > max_gamma:
                        max_gamma = pos_gamma
                        max_gamma_symbol = symbol
            
            if max_gamma_symbol:
                position = self.current_positions[max_gamma_symbol]
                self.ib_client.place_order(
                    symbol=max_gamma_symbol,
                    action='SELL' if position > 0 else 'BUY',
                    quantity=abs(position),
                    order_type='MARKET'
                )
    
    # ==========================================================================
    # PERFORMANCE TRACKING
    # ==========================================================================
    def get_strategy_metrics(self) -> Dict[str, Any]:
        """Get strategy performance metrics"""
        return {
            'strategy_type': 'Greeks-Based Multi-Strategy',
            'enabled_strategies': [s.name for s, enabled in self.enabled_strategies.items() if enabled],
            'positions': len(self.current_positions),
            'portfolio_greeks': {
                'delta': self.portfolio_greeks.total_delta if self.portfolio_greeks else 0,
                'gamma': self.portfolio_greeks.total_gamma if self.portfolio_greeks else 0,
                'theta': self.portfolio_greeks.total_theta if self.portfolio_greeks else 0,
                'vega': self.portfolio_greeks.total_vega if self.portfolio_greeks else 0
            },
            'greek_exposures': {
                'delta_dollars': self.portfolio_greeks.delta_dollars if self.portfolio_greeks else 0,
                'gamma_risk': self.portfolio_greeks.gamma_scalp_potential if self.portfolio_greeks else 0,
                'daily_theta': self.portfolio_greeks.daily_decay if self.portfolio_greeks else 0,
                'vega_exposure': self.portfolio_greeks.vega_exposure if self.portfolio_greeks else 0
            },
            'performance': {
                'gamma_scalp_pnl': self.scalp_pnl,
                'theta_collected': self.theta_collected,
                'rebalance_count': self.rebalance_count
            },
            'active_setups': {
                'gamma_scalps': len(self.gamma_scalp_setups),
                'hedge_positions': sum(abs(p) for p in self.hedge_positions.values())
            }
        }


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":
    from SpyderN_OptionsAnalytics.SpyderN07_OPRAGreeksHandler import OPRAGreeksHandler
    from SpyderE_Risk.SpyderE01_RiskManager import RiskManager
    from SpyderB_Broker.SpyderB01_IBClient import IBClient
    
    # Initialize components
    opra_handler = OPRAGreeksHandler()
    risk_manager = RiskManager()
    ib_client = IBClient()
    
    # Create strategy
    strategy = GreeksBasedStrategy(
        opra_handler=opra_handler,
        risk_manager=risk_manager,
        ib_client=ib_client
    )
    
    # Simulate some positions
    strategy.current_positions = {
        "SPY231215C450": 10,   # Long 10 ATM calls
        "SPY231215P445": -5,   # Short 5 OTM puts
        "SPY231222C455": -10   # Short 10 OTM calls (next week)
    }
    
    print("Greeks-Based Strategy Test")
    print("=" * 50)
    
    # Start monitoring
    strategy.monitoring_thread.start()
    
    # Execute strategy
    signals = strategy.scan_opportunities()
    
    print(f"\nFound {len(signals)} trading signals:")
    for signal in signals[:3]:  # Show top 3
        print(f"\n{signal.signal_type.name}: {signal.symbol}")
        print(f"  Action: {signal.action.name} {signal.quantity}")
        print(f"  Reason: {signal.reason}")
        print(f"  Confidence: {signal.confidence:.1%}")
        print(f"  Strategy: {signal.metadata.get('strategy', 'unknown')}")
    
    # Get metrics
    metrics = strategy.get_strategy_metrics()
    print(f"\nStrategy Metrics:")
    print(f"Portfolio Greeks:")
    for greek, value in metrics['portfolio_greeks'].items():
        print(f"  {greek}: {value:.2f}")
    
    print(f"\nGreek Exposures:")
    for exposure, value in metrics['greek_exposures'].items():
        print(f"  {exposure}: ${value:,.2f}")
    
    # Clean up
    strategy.monitoring_active = False