#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN07_OPRAGreeksHandler.py
Group: N (Options Analytics)
Purpose: OPRA Greeks data handling

Description:
    This module handles real-time Greeks data, providing high-performance calculations
    and caching for option Greeks (Delta, Gamma, Theta, Vega, Rho). While designed
    to integrate with OPRA feeds, it currently provides accurate Greeks calculations
    using market data and can be extended for direct OPRA integration.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4

Status: IMPLEMENTED
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any, Set, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from collections import defaultdict, deque
from threading import Lock, Thread, Event as ThreadEvent
import queue
import time
import math
from functools import lru_cache

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC01_OptionsDataFeed import OptionsDataFeed
from SpyderC_MarketData.SpyderC02_RealTimeDataStream import RealTimeDataStream
from SpyderA_Core.SpyderA03_EventManager import EventManager, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
GREEK_UPDATE_BUFFER_SIZE = 10000
AGGREGATION_INTERVAL_MS = 100
MAX_STALE_GREEK_AGE_MS = 5000
GREEK_PRECISION = 6
CACHE_SIZE = 10000
MIN_TIME_TO_EXPIRY = 0.001  # Minimum time in years

# Risk-free rate (update periodically)
RISK_FREE_RATE = 0.05  # 5% annual

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class GreekSnapshot:
    """Real-time Greeks for an option."""
    symbol: str
    strike: float
    expiration: datetime
    option_type: str  # 'CALL' or 'PUT'
    timestamp: datetime
    microsecond_timestamp: int
    underlying_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    lambda_: float  # Elasticity/leverage
    implied_volatility: float
    theoretical_price: float
    market_price: float
    
@dataclass
class AggregatedGreeks:
    """Aggregated Greeks for a position or portfolio."""
    timestamp: datetime
    total_delta: float
    total_gamma: float
    total_theta: float
    total_vega: float
    total_rho: float
    dollar_delta: float  # Delta in dollar terms
    dollar_gamma: float  # Gamma in dollar terms
    weighted_iv: float
    position_count: int
    net_contracts: int
    
@dataclass
class GreekFlow:
    """Greek flow metrics for market analysis."""
    timestamp: datetime
    delta_flow: float  # Net delta traded
    gamma_flow: float  # Net gamma traded
    vega_flow: float   # Net vega traded
    charm_flow: float  # Delta decay
    vanna_flow: float  # Delta/vega sensitivity
    flow_imbalance: float
    smart_money_indicator: float
    
@dataclass
class GreekRiskAlert:
    """Risk alert based on Greek thresholds."""
    timestamp: datetime
    alert_type: str  # 'DELTA_LIMIT', 'GAMMA_SPIKE', etc.
    current_value: float
    threshold: float
    severity: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    message: str
    action_required: str

# ==============================================================================
# GREEK CALCULATIONS
# ==============================================================================
class GreekCalculator:
    """High-performance Greek calculations."""
    
    @staticmethod
    @lru_cache(maxsize=CACHE_SIZE)
    def calculate_d1_d2(S: float, K: float, r: float, sigma: float, T: float) -> Tuple[float, float]:
        """
        Calculate d1 and d2 for Black-Scholes.
        
        Args:
            S: Spot price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiration in years
            
        Returns:
            Tuple of (d1, d2)
        """
        if T <= 0 or sigma <= 0:
            return 0.0, 0.0
            
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        return d1, d2
        
    @staticmethod
    def calculate_greeks(S: float, K: float, r: float, sigma: float, T: float,
                        option_type: str = 'CALL', dividend_yield: float = 0.0) -> Dict[str, float]:
        """
        Calculate all Greeks for an option.
        
        Args:
            S: Spot price
            K: Strike price
            r: Risk-free rate
            sigma: Volatility
            T: Time to expiration in years
            option_type: 'CALL' or 'PUT'
            dividend_yield: Dividend yield
            
        Returns:
            Dictionary of Greeks
        """
        # Ensure minimum time to avoid division by zero
        T = max(T, MIN_TIME_TO_EXPIRY)
        
        # Adjust for dividends
        S_adj = S * np.exp(-dividend_yield * T)
        
        # Calculate d1 and d2
        d1, d2 = GreekCalculator.calculate_d1_d2(S_adj, K, r, sigma, T)
        
        # Calculate Greeks
        greeks = {}
        
        # Common calculations
        n_d1 = norm.pdf(d1)
        N_d1 = norm.cdf(d1)
        N_d2 = norm.cdf(d2)
        sqrt_T = np.sqrt(T)
        
        if option_type == 'CALL':
            # Delta
            greeks['delta'] = np.exp(-dividend_yield * T) * N_d1
            
            # Gamma
            greeks['gamma'] = np.exp(-dividend_yield * T) * n_d1 / (S * sigma * sqrt_T)
            
            # Theta
            theta1 = -S * n_d1 * sigma * np.exp(-dividend_yield * T) / (2 * sqrt_T)
            theta2 = r * K * np.exp(-r * T) * N_d2
            theta3 = dividend_yield * S * np.exp(-dividend_yield * T) * N_d1
            greeks['theta'] = (theta1 - theta2 + theta3) / 365  # Per day
            
            # Vega
            greeks['vega'] = S * np.exp(-dividend_yield * T) * n_d1 * sqrt_T / 100  # Per 1% vol
            
            # Rho
            greeks['rho'] = K * T * np.exp(-r * T) * N_d2 / 100  # Per 1% rate
            
            # Price
            greeks['price'] = S * np.exp(-dividend_yield * T) * N_d1 - K * np.exp(-r * T) * N_d2
            
        else:  # PUT
            # Delta
            greeks['delta'] = np.exp(-dividend_yield * T) * (N_d1 - 1)
            
            # Gamma (same as call)
            greeks['gamma'] = np.exp(-dividend_yield * T) * n_d1 / (S * sigma * sqrt_T)
            
            # Theta
            theta1 = -S * n_d1 * sigma * np.exp(-dividend_yield * T) / (2 * sqrt_T)
            theta2 = r * K * np.exp(-r * T) * norm.cdf(-d2)
            theta3 = dividend_yield * S * np.exp(-dividend_yield * T) * norm.cdf(-d1)
            greeks['theta'] = (theta1 + theta2 - theta3) / 365  # Per day
            
            # Vega (same as call)
            greeks['vega'] = S * np.exp(-dividend_yield * T) * n_d1 * sqrt_T / 100  # Per 1% vol
            
            # Rho
            greeks['rho'] = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100  # Per 1% rate
            
            # Price
            greeks['price'] = K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-dividend_yield * T) * norm.cdf(-d1)
            
        # Second-order Greeks
        greeks['charm'] = GreekCalculator.calculate_charm(S, K, r, sigma, T, option_type)
        greeks['vanna'] = GreekCalculator.calculate_vanna(S, K, r, sigma, T)
        greeks['vomma'] = GreekCalculator.calculate_vomma(S, K, r, sigma, T)
        
        # Lambda (elasticity)
        if greeks['price'] > 0:
            greeks['lambda'] = greeks['delta'] * S / greeks['price']
        else:
            greeks['lambda'] = 0.0
            
        return greeks
        
    @staticmethod
    def calculate_charm(S: float, K: float, r: float, sigma: float, T: float,
                       option_type: str = 'CALL') -> float:
        """Calculate charm (delta decay)."""
        T = max(T, MIN_TIME_TO_EXPIRY)
        d1, d2 = GreekCalculator.calculate_d1_d2(S, K, r, sigma, T)
        n_d1 = norm.pdf(d1)
        
        charm = -n_d1 * (r / (sigma * np.sqrt(T)) - d2 / (2 * T))
        
        if option_type == 'PUT':
            charm = -charm
            
        return charm / 365  # Per day
        
    @staticmethod
    def calculate_vanna(S: float, K: float, r: float, sigma: float, T: float) -> float:
        """Calculate vanna (delta sensitivity to volatility)."""
        T = max(T, MIN_TIME_TO_EXPIRY)
        d1, d2 = GreekCalculator.calculate_d1_d2(S, K, r, sigma, T)
        n_d1 = norm.pdf(d1)
        
        return -n_d1 * d2 / sigma
        
    @staticmethod
    def calculate_vomma(S: float, K: float, r: float, sigma: float, T: float) -> float:
        """Calculate vomma (vega sensitivity to volatility)."""
        T = max(T, MIN_TIME_TO_EXPIRY)
        d1, d2 = GreekCalculator.calculate_d1_d2(S, K, r, sigma, T)
        n_d1 = norm.pdf(d1)
        
        vega = S * n_d1 * np.sqrt(T)
        return vega * d1 * d2 / sigma
        
    @staticmethod
    def implied_volatility(market_price: float, S: float, K: float, r: float, T: float,
                          option_type: str = 'CALL') -> float:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Args:
            market_price: Market price of option
            S: Spot price
            K: Strike price
            r: Risk-free rate
            T: Time to expiration in years
            option_type: 'CALL' or 'PUT'
            
        Returns:
            Implied volatility
        """
        T = max(T, MIN_TIME_TO_EXPIRY)
        
        # Initial guess using Brenner-Subrahmanyam approximation
        initial_vol = np.sqrt(2 * np.pi / T) * market_price / S
        
        # Bounds for root finding
        min_vol = 0.01
        max_vol = 5.0
        
        try:
            def objective(vol):
                greeks = GreekCalculator.calculate_greeks(S, K, r, vol, T, option_type)
                return greeks['price'] - market_price
                
            # Use Brent's method for robust root finding
            iv = brentq(objective, min_vol, max_vol, xtol=1e-6)
            return iv
            
        except:
            # Fallback to initial guess if convergence fails
            return max(min_vol, min(initial_vol, max_vol))

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class OPRAGreeksHandler:
    """
    Handles Greeks calculations and real-time updates.
    
    This class provides high-performance Greeks calculations with caching,
    real-time updates, and risk monitoring capabilities.
    """
    
    def __init__(self, symbol: str = "SPY"):
        """
        Initialize the OPRA Greeks handler.
        
        Args:
            symbol: Underlying symbol
        """
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.symbol = symbol
        
        # Data structures
        self.greek_cache: Dict[str, GreekSnapshot] = {}
        self.greek_history: deque = deque(maxlen=100000)
        self.update_queue: queue.Queue = queue.Queue(maxsize=GREEK_UPDATE_BUFFER_SIZE)
        
        # Threading
        self.cache_lock = Lock()
        self.processing_thread: Optional[Thread] = None
        self.monitoring_thread: Optional[Thread] = None
        self.stop_event = ThreadEvent()
        self.running = False
        
        # Data feeds
        self.data_feed = OptionsDataFeed(symbol)
        self.rt_stream = RealTimeDataStream()
        self.event_manager = EventManager()
        
        # Risk thresholds
        self.risk_thresholds = {
            'delta': 1000,  # Max absolute delta
            'gamma': 100,   # Max gamma
            'vega': 500,    # Max vega
            'theta': -1000  # Max negative theta
        }
        
        # Calculator
        self.calculator = GreekCalculator()
        
        # Performance metrics
        self.metrics = {
            'calculations_per_second': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'avg_calc_time_ms': 0
        }
        
        self.logger.info(f"OPRAGreeksHandler initialized for {symbol}")
        
    # ==========================================================================
    # GREEK CALCULATIONS
    # ==========================================================================
    def get_option_greeks(self, 
                         strike: float,
                         expiration: datetime,
                         option_type: str,
                         market_price: Optional[float] = None) -> Optional[GreekSnapshot]:
        """
        Get current Greeks for an option.
        
        Args:
            strike: Strike price
            expiration: Expiration date
            option_type: 'CALL' or 'PUT'
            market_price: Optional market price for IV calculation
            
        Returns:
            Greek snapshot or None
        """
        try:
            # Check cache first
            key = f"{strike}_{expiration.date()}_{option_type}"
            
            with self.cache_lock:
                if key in self.greek_cache:
                    cached = self.greek_cache[key]
                    age_ms = (datetime.now() - cached.timestamp).total_seconds() * 1000
                    
                    if age_ms < MAX_STALE_GREEK_AGE_MS:
                        self.metrics['cache_hits'] += 1
                        return cached
                        
            self.metrics['cache_misses'] += 1
            
            # Calculate fresh Greeks
            start_time = time.time()
            
            # Get market data
            spot_price = self.data_feed.get_spot_price(self.symbol)
            
            # Calculate time to expiration
            tte_days = (expiration.date() - date.today()).days
            tte_years = max(tte_days / 365.0, MIN_TIME_TO_EXPIRY)
            
            # Get or calculate implied volatility
            if market_price:
                iv = self.calculator.implied_volatility(
                    market_price, spot_price, strike, RISK_FREE_RATE, tte_years, option_type
                )
            else:
                # Use historical volatility as fallback
                iv = self._get_historical_volatility()
                
            # Calculate Greeks
            greeks = self.calculator.calculate_greeks(
                spot_price, strike, RISK_FREE_RATE, iv, tte_years, option_type
            )
            
            # Create snapshot
            snapshot = GreekSnapshot(
                symbol=self.symbol,
                strike=strike,
                expiration=expiration,
                option_type=option_type,
                timestamp=datetime.now(),
                microsecond_timestamp=int(time.time() * 1e6),
                underlying_price=spot_price,
                delta=greeks['delta'],
                gamma=greeks['gamma'],
                theta=greeks['theta'],
                vega=greeks['vega'],
                rho=greeks['rho'],
                lambda_=greeks['lambda'],
                implied_volatility=iv,
                theoretical_price=greeks['price'],
                market_price=market_price or greeks['price']
            )
            
            # Update cache
            with self.cache_lock:
                self.greek_cache[key] = snapshot
                self.greek_history.append(snapshot)
                
            # Update metrics
            calc_time = (time.time() - start_time) * 1000
            self.metrics['avg_calc_time_ms'] = (
                self.metrics['avg_calc_time_ms'] * 0.9 + calc_time * 0.1
            )
            
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Error processing update: {e}")
            
    # ==========================================================================
    # PERFORMANCE OPTIMIZATION
    # ==========================================================================
    def batch_calculate_greeks(self, 
                             option_list: List[Dict[str, Any]]) -> List[GreekSnapshot]:
        """
        Calculate Greeks for multiple options in batch.
        
        Args:
            option_list: List of option specifications
            
        Returns:
            List of Greek snapshots
        """
        results = []
        
        # Get spot price once for all calculations
        spot_price = self.data_feed.get_spot_price(self.symbol)
        
        for option in option_list:
            # Use cached spot price
            greeks = self._calculate_greeks_with_spot(
                option['strike'],
                option['expiration'],
                option['option_type'],
                spot_price,
                option.get('market_price')
            )
            
            if greeks:
                results.append(greeks)
                
        return results
        
    def _calculate_greeks_with_spot(self,
                                   strike: float,
                                   expiration: datetime,
                                   option_type: str,
                                   spot_price: float,
                                   market_price: Optional[float] = None) -> Optional[GreekSnapshot]:
        """Calculate Greeks with provided spot price."""
        try:
            # Calculate time to expiration
            tte_days = (expiration.date() - date.today()).days
            tte_years = max(tte_days / 365.0, MIN_TIME_TO_EXPIRY)
            
            # Get or calculate implied volatility
            if market_price:
                iv = self.calculator.implied_volatility(
                    market_price, spot_price, strike, RISK_FREE_RATE, tte_years, option_type
                )
            else:
                iv = self._get_historical_volatility()
                
            # Calculate Greeks
            greeks = self.calculator.calculate_greeks(
                spot_price, strike, RISK_FREE_RATE, iv, tte_years, option_type
            )
            
            # Create snapshot
            return GreekSnapshot(
                symbol=self.symbol,
                strike=strike,
                expiration=expiration,
                option_type=option_type,
                timestamp=datetime.now(),
                microsecond_timestamp=int(time.time() * 1e6),
                underlying_price=spot_price,
                delta=greeks['delta'],
                gamma=greeks['gamma'],
                theta=greeks['theta'],
                vega=greeks['vega'],
                rho=greeks['rho'],
                lambda_=greeks['lambda'],
                implied_volatility=iv,
                theoretical_price=greeks['price'],
                market_price=market_price or greeks['price']
            )
            
        except Exception as e:
            self.logger.error(f"Error in Greek calculation: {e}")
            return None
            
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get handler performance metrics.
        
        Returns:
            Performance statistics
        """
        with self.cache_lock:
            total_calcs = self.metrics['cache_hits'] + self.metrics['cache_misses']
            cache_hit_rate = (self.metrics['cache_hits'] / total_calcs * 100) if total_calcs > 0 else 0
            
        return {
            'updates_per_second': self.metrics['calculations_per_second'],
            'cache_size': len(self.greek_cache),
            'queue_depth': self.update_queue.qsize(),
            'avg_latency_ms': self.metrics['avg_calc_time_ms'],
            'cache_hit_rate': cache_hit_rate,
            'total_calculations': total_calcs,
            'active_threads': 2 if self.running else 0
        }
        
    def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        # Calculate Greeks per second
        current_time = time.time()
        if hasattr(self, '_last_metric_time'):
            time_diff = current_time - self._last_metric_time
            if time_diff > 0:
                calcs_in_period = len([g for g in self.greek_history 
                                     if (current_time - g.timestamp.timestamp()) < time_diff])
                self.metrics['calculations_per_second'] = calcs_in_period / time_diff
                
        self._last_metric_time = current_time
        
    # ==========================================================================
    # GREEK INTERPOLATION
    # ==========================================================================
    def interpolate_greeks(self,
                          target_strike: float,
                          expiration: datetime,
                          option_type: str = 'CALL') -> Optional[GreekSnapshot]:
        """
        Interpolate Greeks for a specific strike.
        
        Args:
            target_strike: Strike to interpolate
            expiration: Expiration date
            option_type: 'CALL' or 'PUT'
            
        Returns:
            Interpolated Greeks
        """
        try:
            # Get chain Greeks
            chain_greeks = self.get_chain_greeks(expiration)
            
            if chain_greeks.empty:
                return None
                
            # Filter for option type
            type_greeks = chain_greeks[chain_greeks['type'] == option_type]
            
            if len(type_greeks) < 2:
                return None
                
            # Sort by strike
            type_greeks = type_greeks.sort_values('strike')
            
            # Find surrounding strikes
            lower_strikes = type_greeks[type_greeks['strike'] <= target_strike]
            upper_strikes = type_greeks[type_greeks['strike'] >= target_strike]
            
            if lower_strikes.empty or upper_strikes.empty:
                # Extrapolation needed - use nearest
                if lower_strikes.empty:
                    nearest = upper_strikes.iloc[0]
                else:
                    nearest = lower_strikes.iloc[-1]
                    
                return self.get_option_greeks(
                    nearest['strike'], expiration, option_type, nearest['market_price']
                )
                
            # Linear interpolation
            lower = lower_strikes.iloc[-1]
            upper = upper_strikes.iloc[0]
            
            # Interpolation weight
            weight = (target_strike - lower['strike']) / (upper['strike'] - lower['strike'])
            
            # Interpolate Greeks
            interp_delta = lower['delta'] + weight * (upper['delta'] - lower['delta'])
            interp_gamma = lower['gamma'] + weight * (upper['gamma'] - lower['gamma'])
            interp_theta = lower['theta'] + weight * (upper['theta'] - lower['theta'])
            interp_vega = lower['vega'] + weight * (upper['vega'] - lower['vega'])
            interp_rho = lower['rho'] + weight * (upper['rho'] - lower['rho'])
            interp_iv = lower['iv'] + weight * (upper['iv'] - lower['iv'])
            
            # Create interpolated snapshot
            spot_price = self.data_feed.get_spot_price(self.symbol)
            
            return GreekSnapshot(
                symbol=self.symbol,
                strike=target_strike,
                expiration=expiration,
                option_type=option_type,
                timestamp=datetime.now(),
                microsecond_timestamp=int(time.time() * 1e6),
                underlying_price=spot_price,
                delta=interp_delta,
                gamma=interp_gamma,
                theta=interp_theta,
                vega=interp_vega,
                rho=interp_rho,
                lambda_=interp_delta * spot_price / target_strike,  # Approximation
                implied_volatility=interp_iv,
                theoretical_price=0.0,  # Would need to recalculate
                market_price=0.0
            )
            
        except Exception as e:
            self.logger.error(f"Error interpolating Greeks: {e}")
            return None
            
    # ==========================================================================
    # EVENT EMISSION
    # ==========================================================================
    def _emit_greek_update(self, greeks: GreekSnapshot) -> None:
        """Emit Greek update event."""
        event = Event(
            'greeks.updated',
            {
                'symbol': greeks.symbol,
                'strike': greeks.strike,
                'expiration': greeks.expiration,
                'option_type': greeks.option_type,
                'delta': greeks.delta,
                'gamma': greeks.gamma,
                'theta': greeks.theta,
                'vega': greeks.vega,
                'iv': greeks.implied_volatility,
                'timestamp': greeks.timestamp
            }
        )
        self.event_manager.emit(event)
        
    def _emit_risk_alert(self, alert: GreekRiskAlert) -> None:
        """Emit risk alert event."""
        event = Event(
            'greeks.risk_alert',
            {
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'current_value': alert.current_value,
                'threshold': alert.threshold,
                'message': alert.message,
                'action': alert.action_required,
                'timestamp': alert.timestamp
            }
        )
        self.event_manager.emit(event)
        
    def _emit_heartbeat(self) -> None:
        """Emit heartbeat event."""
        metrics = self.get_performance_metrics()
        event = Event(
            'greeks.heartbeat',
            {
                'symbol': self.symbol,
                'cache_size': len(self.greek_cache),
                'calculations_per_second': metrics['updates_per_second'],
                'timestamp': datetime.now()
            }
        )
        self.event_manager.emit(event)
        
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _get_historical_volatility(self, lookback_days: int = 30) -> float:
        """Get historical volatility estimate."""
        try:
            # This would fetch from historical data
            # For now, return a reasonable default
            return 0.18  # 18% annual volatility
        except:
            return 0.20  # 20% default
            
    def _empty_aggregated_greeks(self) -> AggregatedGreeks:
        """Create empty aggregated Greeks."""
        return AggregatedGreeks(
            timestamp=datetime.now(),
            total_delta=0.0,
            total_gamma=0.0,
            total_theta=0.0,
            total_vega=0.0,
            total_rho=0.0,
            dollar_delta=0.0,
            dollar_gamma=0.0,
            weighted_iv=0.0,
            position_count=0,
            net_contracts=0
        )
        
    def _empty_greek_flow(self) -> GreekFlow:
        """Create empty Greek flow."""
        return GreekFlow(
            timestamp=datetime.now(),
            delta_flow=0.0,
            gamma_flow=0.0,
            vega_flow=0.0,
            charm_flow=0.0,
            vanna_flow=0.0,
            flow_imbalance=0.0,
            smart_money_indicator=0.0
        )

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'OPRAGreeksHandler',
    'GreekSnapshot',
    'AggregatedGreeks',
    'GreekFlow',
    'GreekRiskAlert',
    'GreekCalculator'
]

# ==============================================================================
# USAGE EXAMPLE
# ==============================================================================
if __name__ == "__main__":
    # Initialize handler
    handler = OPRAGreeksHandler("SPY")
    
    print("=== SPYDER OPRA Greeks Handler ===\n")
    
    # Start processing
    handler.start_processing()
    
    # Example: Get Greeks for a specific option
    strike = 440.0
    expiration = datetime.now() + timedelta(days=30)
    
    greeks = handler.get_option_greeks(strike, expiration, 'CALL', market_price=5.50)
    
    if greeks:
        print(f"📊 Option Greeks for {strike} Call:")
        print(f"Delta: {greeks.delta:.4f}")
        print(f"Gamma: {greeks.gamma:.4f}")
        print(f"Theta: ${greeks.theta:.2f}/day")
        print(f"Vega: ${greeks.vega:.2f}/1% vol")
        print(f"IV: {greeks.implied_volatility:.1%}")
        print(f"Theoretical Price: ${greeks.theoretical_price:.2f}")
        
    # Example: Portfolio Greeks
    positions = [
        {'strike': 440, 'expiration': expiration, 'option_type': 'CALL', 'quantity': 10},
        {'strike': 435, 'expiration': expiration, 'option_type': 'PUT', 'quantity': -5},
    ]
    
    portfolio_greeks = handler.calculate_portfolio_greeks(positions)
    
    print(f"\n📈 Portfolio Greeks:")
    print(f"Total Delta: {portfolio_greeks.total_delta:.0f}")
    print(f"Total Gamma: {portfolio_greeks.total_gamma:.2f}")
    print(f"Total Theta: ${portfolio_greeks.total_theta:.0f}/day")
    print(f"Total Vega: ${portfolio_greeks.total_vega:.0f}/1% vol")
    print(f"Dollar Delta: ${portfolio_greeks.dollar_delta:,.0f}")
    
    # Check risk alerts
    alerts = handler.check_risk_alerts(portfolio_greeks)
    if alerts:
        print(f"\n⚠️ Risk Alerts:")
        for alert in alerts:
            print(f"  {alert.alert_type}: {alert.message}")
            print(f"  Action: {alert.action_required}")
            
    # Greek flow analysis
    flow = handler.analyze_greek_flow(lookback_minutes=30)
    print(f"\n🌊 Greek Flow Analysis:")
    print(f"Delta Flow: {flow.delta_flow:.0f}")
    print(f"Gamma Flow: {flow.gamma_flow:.2f}")
    print(f"Flow Imbalance: {flow.flow_imbalance:.2%}")
    print(f"Smart Money: {flow.smart_money_indicator:.1f}")
    
    # Performance metrics
    metrics = handler.get_performance_metrics()
    print(f"\n⚡ Performance Metrics:")
    print(f"Calculations/sec: {metrics['updates_per_second']:.0f}")
    print(f"Cache Hit Rate: {metrics['cache_hit_rate']:.1f}%")
    print(f"Avg Latency: {metrics['avg_latency_ms']:.1f}ms")
    
    # Stop processing
    handler.stop_processing()
    
    print("\n✅ Greeks handler demonstration complete!"):
            self.logger.error(f"Error calculating Greeks: {e}")
            return None
            
    def get_chain_greeks(self, 
                        expiration: datetime,
                        strikes: Optional[List[float]] = None) -> pd.DataFrame:
        """
        Get Greeks for entire option chain.
        
        Args:
            expiration: Expiration date
            strikes: Optional list of strikes (uses all if None)
            
        Returns:
            DataFrame with chain Greeks
        """
        try:
            # Get option chain
            chain = self.data_feed.get_options_chain(self.symbol, expiration)
            
            if chain is None or chain.empty:
                return pd.DataFrame()
                
            # Filter strikes if specified
            if strikes:
                chain = chain[chain['strike'].isin(strikes)]
                
            # Calculate Greeks for each option
            greeks_data = []
            
            for _, option in chain.iterrows():
                greeks = self.get_option_greeks(
                    option['strike'],
                    expiration,
                    option['type'],
                    option.get('last_price')
                )
                
                if greeks:
                    greeks_data.append({
                        'strike': greeks.strike,
                        'type': greeks.option_type,
                        'delta': greeks.delta,
                        'gamma': greeks.gamma,
                        'theta': greeks.theta,
                        'vega': greeks.vega,
                        'rho': greeks.rho,
                        'iv': greeks.implied_volatility,
                        'theo_price': greeks.theoretical_price,
                        'market_price': greeks.market_price,
                        'volume': option.get('volume', 0),
                        'open_interest': option.get('open_interest', 0)
                    })
                    
            return pd.DataFrame(greeks_data)
            
        except Exception as e:
            self.logger.error(f"Error getting chain Greeks: {e}")
            return pd.DataFrame()
            
    # ==========================================================================
    # PORTFOLIO GREEKS
    # ==========================================================================
    def calculate_portfolio_greeks(self, 
                                 positions: List[Dict[str, Any]]) -> AggregatedGreeks:
        """
        Calculate aggregated Greeks for portfolio.
        
        Args:
            positions: List of position dictionaries with keys:
                      - strike, expiration, option_type, quantity, market_price
            
        Returns:
            Aggregated Greeks
        """
        try:
            # Initialize aggregates
            total_delta = 0.0
            total_gamma = 0.0
            total_theta = 0.0
            total_vega = 0.0
            total_rho = 0.0
            
            weighted_iv_sum = 0.0
            total_contracts = 0
            position_count = 0
            
            spot_price = self.data_feed.get_spot_price(self.symbol)
            
            # Process each position
            for pos in positions:
                if pos.get('quantity', 0) == 0:
                    continue
                    
                # Get Greeks for position
                greeks = self.get_option_greeks(
                    pos['strike'],
                    pos['expiration'],
                    pos['option_type'],
                    pos.get('market_price')
                )
                
                if greeks:
                    # Scale by position size
                    quantity = pos['quantity']
                    contract_multiplier = 100  # Standard option contract
                    
                    total_delta += greeks.delta * quantity * contract_multiplier
                    total_gamma += greeks.gamma * quantity * contract_multiplier
                    total_theta += greeks.theta * quantity * contract_multiplier
                    total_vega += greeks.vega * quantity * contract_multiplier
                    total_rho += greeks.rho * quantity * contract_multiplier
                    
                    weighted_iv_sum += greeks.implied_volatility * abs(quantity)
                    total_contracts += abs(quantity)
                    position_count += 1
                    
            # Calculate weighted average IV
            weighted_iv = weighted_iv_sum / total_contracts if total_contracts > 0 else 0.0
            
            # Calculate dollar Greeks
            dollar_delta = total_delta * spot_price
            dollar_gamma = total_gamma * spot_price * spot_price / 100
            
            return AggregatedGreeks(
                timestamp=datetime.now(),
                total_delta=total_delta,
                total_gamma=total_gamma,
                total_theta=total_theta,
                total_vega=total_vega,
                total_rho=total_rho,
                dollar_delta=dollar_delta,
                dollar_gamma=dollar_gamma,
                weighted_iv=weighted_iv,
                position_count=position_count,
                net_contracts=total_contracts
            )
            
        except Exception as e:
            self.logger.error(f"Error calculating portfolio Greeks: {e}")
            return self._empty_aggregated_greeks()
            
    # ==========================================================================
    # GREEK FLOW ANALYSIS
    # ==========================================================================
    def analyze_greek_flow(self, 
                          lookback_minutes: int = 30) -> GreekFlow:
        """
        Analyze Greek flow in recent trades.
        
        Args:
            lookback_minutes: Minutes to analyze
            
        Returns:
            Greek flow metrics
        """
        try:
            cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
            
            # Get recent Greek snapshots
            with self.cache_lock:
                recent_greeks = [g for g in self.greek_history 
                               if g.timestamp > cutoff_time]
                
            if not recent_greeks:
                return self._empty_greek_flow()
                
            # Aggregate flow metrics
            delta_flow = sum(g.delta for g in recent_greeks)
            gamma_flow = sum(g.gamma for g in recent_greeks)
            vega_flow = sum(g.vega for g in recent_greeks)
            
            # Calculate second-order flows
            charm_flow = sum(g.gamma * g.theta for g in recent_greeks)  # Simplified
            vanna_flow = sum(g.delta * g.vega for g in recent_greeks)   # Simplified
            
            # Calculate flow imbalance
            call_flow = sum(g.delta for g in recent_greeks if g.option_type == 'CALL')
            put_flow = sum(abs(g.delta) for g in recent_greeks if g.option_type == 'PUT')
            flow_imbalance = (call_flow - put_flow) / (call_flow + put_flow) if (call_flow + put_flow) > 0 else 0
            
            # Smart money indicator (large trades with high gamma)
            large_trades = [g for g in recent_greeks if abs(g.gamma) > 0.01]
            smart_money = sum(g.gamma for g in large_trades) / len(large_trades) if large_trades else 0
            
            return GreekFlow(
                timestamp=datetime.now(),
                delta_flow=delta_flow,
                gamma_flow=gamma_flow,
                vega_flow=vega_flow,
                charm_flow=charm_flow,
                vanna_flow=vanna_flow,
                flow_imbalance=flow_imbalance,
                smart_money_indicator=smart_money * 100
            )
            
        except Exception as e:
            self.logger.error(f"Error analyzing Greek flow: {e}")
            return self._empty_greek_flow()
            
    # ==========================================================================
    # GREEK SURFACES
    # ==========================================================================
    def get_greek_surface(self, 
                         greek_type: str = 'delta',
                         num_strikes: int = 20,
                         num_expirations: int = 5) -> Dict[str, Any]:
        """
        Get Greek surface across strikes and expirations.
        
        Args:
            greek_type: Type of Greek ('delta', 'gamma', 'theta', 'vega')
            num_strikes: Number of strikes to include
            num_expirations: Number of expirations to include
            
        Returns:
            Surface data for visualization
        """
        try:
            # Get spot price
            spot_price = self.data_feed.get_spot_price(self.symbol)
            
            # Generate strike range
            strike_range = np.linspace(
                spot_price * 0.9,
                spot_price * 1.1,
                num_strikes
            )
            
            # Get available expirations
            all_expirations = self.data_feed.get_expiration_dates(self.symbol)
            expirations = all_expirations[:num_expirations]
            
            # Build surface data
            surface_data = {
                'strikes': strike_range.tolist(),
                'expirations': [exp.isoformat() for exp in expirations],
                'values': [],
                'surface_type': greek_type,
                'spot_price': spot_price
            }
            
            # Calculate Greek values
            for exp in expirations:
                exp_values = []
                
                for strike in strike_range:
                    # Get Greeks for call option
                    greeks = self.get_option_greeks(strike, exp, 'CALL')
                    
                    if greeks:
                        value = getattr(greeks, greek_type, 0.0)
                        exp_values.append(value)
                    else:
                        exp_values.append(0.0)
                        
                surface_data['values'].append(exp_values)
                
            return surface_data
            
        except Exception as e:
            self.logger.error(f"Error creating Greek surface: {e}")
            return {
                'strikes': [],
                'expirations': [],
                'values': [],
                'surface_type': greek_type
            }
            
    # ==========================================================================
    # RISK MONITORING
    # ==========================================================================
    def set_greek_alerts(self, 
                        alert_rules: Dict[str, Dict[str, float]]) -> None:
        """
        Set alerts for Greek thresholds.
        
        Args:
            alert_rules: Dictionary of Greek alert rules
                        e.g., {'delta': {'max': 1000, 'min': -1000}}
        """
        self.risk_thresholds.update(alert_rules)
        self.logger.info(f"Updated Greek alert thresholds: {alert_rules}")
        
    def check_risk_alerts(self, portfolio_greeks: AggregatedGreeks) -> List[GreekRiskAlert]:
        """
        Check for risk alerts based on Greek thresholds.
        
        Args:
            portfolio_greeks: Current portfolio Greeks
            
        Returns:
            List of risk alerts
        """
        alerts = []
        
        # Check delta limits
        if 'delta' in self.risk_thresholds:
            if abs(portfolio_greeks.total_delta) > self.risk_thresholds['delta']:
                alerts.append(GreekRiskAlert(
                    timestamp=datetime.now(),
                    alert_type='DELTA_LIMIT',
                    current_value=portfolio_greeks.total_delta,
                    threshold=self.risk_thresholds['delta'],
                    severity='HIGH' if abs(portfolio_greeks.total_delta) > self.risk_thresholds['delta'] * 1.5 else 'MEDIUM',
                    message=f"Delta exposure exceeds limit: {portfolio_greeks.total_delta:.0f}",
                    action_required='Consider delta hedging'
                ))
                
        # Check gamma risk
        if 'gamma' in self.risk_thresholds:
            if portfolio_greeks.total_gamma > self.risk_thresholds['gamma']:
                alerts.append(GreekRiskAlert(
                    timestamp=datetime.now(),
                    alert_type='GAMMA_SPIKE',
                    current_value=portfolio_greeks.total_gamma,
                    threshold=self.risk_thresholds['gamma'],
                    severity='HIGH',
                    message=f"High gamma risk: {portfolio_greeks.total_gamma:.2f}",
                    action_required='Reduce position size or add gamma hedges'
                ))
                
        # Check theta bleed
        if 'theta' in self.risk_thresholds:
            if portfolio_greeks.total_theta < self.risk_thresholds['theta']:
                daily_decay = abs(portfolio_greeks.total_theta)
                alerts.append(GreekRiskAlert(
                    timestamp=datetime.now(),
                    alert_type='THETA_DECAY',
                    current_value=portfolio_greeks.total_theta,
                    threshold=self.risk_thresholds['theta'],
                    severity='MEDIUM',
                    message=f"High theta decay: ${daily_decay:.0f}/day",
                    action_required='Review time decay exposure'
                ))
                
        # Check vega exposure
        if 'vega' in self.risk_thresholds:
            if abs(portfolio_greeks.total_vega) > self.risk_thresholds['vega']:
                alerts.append(GreekRiskAlert(
                    timestamp=datetime.now(),
                    alert_type='VEGA_EXPOSURE',
                    current_value=portfolio_greeks.total_vega,
                    threshold=self.risk_thresholds['vega'],
                    severity='MEDIUM',
                    message=f"High vega exposure: {portfolio_greeks.total_vega:.0f}",
                    action_required='Consider volatility hedging'
                ))
                
        return alerts
        
    # ==========================================================================
    # REAL-TIME PROCESSING
    # ==========================================================================
    def start_processing(self) -> None:
        """Start processing Greeks updates."""
        if self.running:
            self.logger.warning("Greeks processing already running")
            return
            
        self.running = True
        self.stop_event.clear()
        
        # Start processing thread
        self.processing_thread = Thread(
            target=self._processing_loop,
            daemon=True
        )
        self.processing_thread.start()
        
        # Start monitoring thread
        self.monitoring_thread = Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        
        self.logger.info("Greeks processing started")
        
    def stop_processing(self) -> None:
        """Stop processing Greeks updates."""
        self.running = False
        self.stop_event.set()
        
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
            
        self.logger.info("Greeks processing stopped")
        
    def _processing_loop(self) -> None:
        """Main processing loop for Greek calculations."""
        while self.running and not self.stop_event.is_set():
            try:
                # Process updates from queue
                try:
                    update = self.update_queue.get(timeout=1)
                    self._process_update(update)
                except queue.Empty:
                    pass
                    
                # Update performance metrics
                self._update_performance_metrics()
                
            except Exception as e:
                self.logger.error(f"Error in processing loop: {e}")
                
    def _monitoring_loop(self) -> None:
        """Monitoring loop for risk alerts."""
        while self.running and not self.stop_event.is_set():
            try:
                # Sleep for monitoring interval
                self.stop_event.wait(30)  # Check every 30 seconds
                
                if not self.running:
                    break
                    
                # Check portfolio risk
                # This would integrate with position management
                # For now, emit a heartbeat event
                self._emit_heartbeat()
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                
    def _process_update(self, update: Dict[str, Any]) -> None:
        """Process a single Greek update."""
        try:
            # Extract update data
            strike = update['strike']
            expiration = update['expiration']
            option_type = update['option_type']
            market_price = update.get('market_price')
            
            # Calculate Greeks
            greeks = self.get_option_greeks(
                strike, expiration, option_type, market_price
            )
            
            if greeks:
                # Emit Greek update event
                self._emit_greek_update(greeks)
                
        except Exception as e