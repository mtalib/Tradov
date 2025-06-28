#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderZ04_VolatilityEngine.py
Group: Z (Communication Infrastructure)
Purpose: Real-time volatility surface modeling and Greeks calculation engine

Description:
    This module implements a high-performance volatility analysis engine that
    calculates real-time Greeks, models implied volatility surfaces, detects
    volatility regimes, and monitors volatility smile/skew patterns. It runs
    as a separate process and communicates via ZeroMQ with shared memory for
    tick data access.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-06-28
Last Updated: 2025-06-28 Time: 17:15:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import json
import math
import threading
import multiprocessing as mp
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import stats, optimize, interpolate
from scipy.stats import norm
import zmq

# Optional imports for advanced features
try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("Warning: scikit-learn not available. Anomaly detection disabled.")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderZ07_MultiProcessManager import SpyderEngineProcess, SharedTickData
from SpyderZ03_TradingCoordinator import EngineType, CommandType
from SpyderZ02_MessageProtocol import (
    MessageFactory, ProtocolManager, SerializationFormat,
    PortfolioGreeksMessage, OptionQuoteMessage, MessageCategory,
    RiskMessageType
)
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Calculation parameters
RISK_FREE_RATE = 0.05  # 5% annual risk-free rate (update based on current rates)
TRADING_DAYS_PER_YEAR = 252
SECONDS_PER_TRADING_DAY = 6.5 * 3600  # 6.5 hours

# Greeks calculation
MIN_TIME_TO_EXPIRY = 0.001  # Minimum 1 day to avoid division by zero
MAX_ITERATIONS = 100
IV_TOLERANCE = 0.0001
MIN_IV = 0.001
MAX_IV = 5.0

# Volatility surface parameters
STRIKE_RANGE_PERCENT = 0.20  # Look at strikes within 20% of spot
MIN_STRIKES_FOR_SURFACE = 10
MONEYNESS_GRID_POINTS = 50
TIME_GRID_POINTS = 20

# Regime detection
REGIME_LOOKBACK_DAYS = 60
REGIME_CHANGE_THRESHOLD = 0.15  # 15% change in volatility

# Performance
CALCULATION_INTERVAL = 0.1  # Calculate every 100ms
SURFACE_UPDATE_INTERVAL = 1.0  # Update surface every 1 second
BROADCAST_INTERVAL = 0.5  # Broadcast updates every 500ms

# ==============================================================================
# ENUMS
# ==============================================================================
class VolatilityRegime(Enum):
    """Market volatility regimes."""
    LOW = "LOW_VOLATILITY"
    NORMAL = "NORMAL_VOLATILITY"
    HIGH = "HIGH_VOLATILITY"
    EXTREME = "EXTREME_VOLATILITY"

class CalculationMode(Enum):
    """Calculation accuracy modes."""
    FAST = auto()      # Quick approximations
    STANDARD = auto()  # Normal accuracy
    PRECISE = auto()   # High precision

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionContract:
    """Option contract specification."""
    symbol: str
    underlying: str
    strike: float
    expiry: date
    option_type: str  # 'CALL' or 'PUT'
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    underlying_price: float = 0.0
    
    @property
    def mid_price(self) -> float:
        """Get mid price."""
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2
        return self.last
    
    @property
    def time_to_expiry(self) -> float:
        """Get time to expiry in years."""
        days_to_expiry = (self.expiry - date.today()).days
        return max(days_to_expiry / TRADING_DAYS_PER_YEAR, MIN_TIME_TO_EXPIRY)
    
    @property
    def moneyness(self) -> float:
        """Get moneyness (S/K)."""
        if self.strike > 0:
            return self.underlying_price / self.strike
        return 1.0

@dataclass
class Greeks:
    """Option Greeks."""
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0
    lambda_: float = 0.0  # Elasticity
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
            'lambda': self.lambda_
        }

@dataclass
class VolatilitySurface:
    """Implied volatility surface."""
    spot_price: float
    calculation_time: datetime
    strikes: np.ndarray
    expirations: np.ndarray
    ivs: np.ndarray  # 2D array [strikes x expirations]
    interpolator: Optional[Any] = None
    
    def get_iv(self, strike: float, time_to_expiry: float) -> float:
        """Interpolate IV for given strike and time."""
        if self.interpolator is None:
            return 0.0
        
        # Ensure within bounds
        strike = np.clip(strike, self.strikes.min(), self.strikes.max())
        time_to_expiry = np.clip(time_to_expiry, self.expirations.min(), self.expirations.max())
        
        return float(self.interpolator([strike], [time_to_expiry])[0])

@dataclass
class VolatilityMetrics:
    """Volatility analysis metrics."""
    current_regime: VolatilityRegime
    spot_volatility: float
    realized_volatility: float
    garch_forecast: float
    vix_proxy: float  # ATM IV as VIX proxy
    put_call_ratio: float
    term_structure_slope: float
    smile_slope: float
    smile_curvature: float
    regime_probability: Dict[VolatilityRegime, float]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class VolatilityEngine(SpyderEngineProcess):
    """
    Real-time volatility analysis and Greeks calculation engine.
    
    This engine processes market data to calculate option Greeks, model
    implied volatility surfaces, detect volatility regimes, and provide
    comprehensive volatility analytics for the SPYDER trading system.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        options: Dictionary of tracked option contracts
        surface: Current volatility surface
        metrics: Current volatility metrics
        
    Example:
        >>> engine = VolatilityEngine(engine_type, shutdown_event, shm_name)
        >>> engine.run()
    """
    
    def __init__(self, engine_type: EngineType, shutdown_event: mp.Event,
                 shared_memory_name: str):
        """Initialize the volatility engine."""
        super().__init__(engine_type, shutdown_event, shared_memory_name)
        
        self.error_handler = SpyderErrorHandler()
        
        # Protocol manager
        self.protocol = ProtocolManager(SerializationFormat.MSGPACK)
        
        # Market data storage
        self.spot_price = 0.0
        self.options: Dict[str, OptionContract] = {}
        self.option_chains: Dict[date, List[OptionContract]] = {}
        
        # Tick history for realized vol
        self.tick_history = []
        self.max_tick_history = 5000
        
        # Volatility surface
        self.surface: Optional[VolatilitySurface] = None
        self.surface_lock = threading.Lock()
        
        # Volatility metrics
        self.metrics: Optional[VolatilityMetrics] = None
        
        # Portfolio Greeks
        self.portfolio_greeks = PortfolioGreeksMessage(
            timestamp=time.time(),
            total_delta=0.0,
            total_gamma=0.0,
            total_theta=0.0,
            total_vega=0.0,
            total_rho=0.0,
            delta_dollars=0.0,
            gamma_dollars=0.0,
            theta_dollars=0.0,
            vega_dollars=0.0
        )
        
        # Calculation settings
        self.calculation_mode = CalculationMode.STANDARD
        
        # Timing
        self.last_calculation = 0.0
        self.last_surface_update = 0.0
        self.last_broadcast = 0.0
        
        # Threading
        self.calculation_thread = None
        self.broadcast_thread = None
        
        self.logger.info(f"{self.__class__.__name__} initialized")
        
    # ==========================================================================
    # PUBLIC METHODS - PROCESS INTERFACE
    # ==========================================================================
    def setup(self) -> None:
        """Set up engine resources."""
        super().setup()
        
        # Start calculation thread
        self.calculation_thread = threading.Thread(
            target=self._calculation_loop,
            name="VolCalcThread",
            daemon=True
        )
        self.calculation_thread.start()
        
        # Start broadcast thread
        self.broadcast_thread = threading.Thread(
            target=self._broadcast_loop,
            name="VolBroadcastThread",
            daemon=True
        )
        self.broadcast_thread.start()
        
        self.logger.info("Volatility engine setup complete")
        
    def process_work(self) -> None:
        """Process engine work - handle commands and data updates."""
        # Check for commands from coordinator
        if self.dealer_socket.poll(0):
            try:
                message = self.dealer_socket.recv_json()
                self._handle_command(message)
            except Exception as e:
                self.logger.error(f"Command processing error: {e}")
                
        # Read tick data from shared memory
        self._process_tick_data()
        
    def get_metrics(self) -> Dict[str, Any]:
        """Get engine-specific metrics."""
        base_metrics = super().get_metrics()
        
        base_metrics.update({
            'spot_price': self.spot_price,
            'option_count': len(self.options),
            'calculation_mode': self.calculation_mode.name,
            'surface_age': time.time() - self.last_surface_update if self.surface else None,
            'portfolio_delta': self.portfolio_greeks.total_delta,
            'portfolio_vega': self.portfolio_greeks.total_vega
        })
        
        if self.metrics:
            base_metrics['volatility_regime'] = self.metrics.current_regime.value
            base_metrics['spot_volatility'] = self.metrics.spot_volatility
            
        return base_metrics
        
    # ==========================================================================
    # PUBLIC METHODS - CALCULATIONS
    # ==========================================================================
    def calculate_greeks(self, option: OptionContract, iv: Optional[float] = None) -> Greeks:
        """
        Calculate Greeks for an option contract.
        
        Args:
            option: Option contract
            iv: Implied volatility (will calculate if not provided)
            
        Returns:
            Greeks object
        """
        S = option.underlying_price
        K = option.strike
        T = option.time_to_expiry
        r = RISK_FREE_RATE
        
        # Calculate IV if not provided
        if iv is None:
            iv = self.calculate_implied_volatility(option)
            
        if iv <= 0 or T <= 0:
            return Greeks()  # Return zero Greeks
            
        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r + 0.5 * iv ** 2) * T) / (iv * np.sqrt(T))
        d2 = d1 - iv * np.sqrt(T)
        
        # Standard normal CDF and PDF
        N = norm.cdf
        n = norm.pdf
        
        # Calculate Greeks based on option type
        if option.option_type == 'CALL':
            delta = N(d1)
            theta = (-S * n(d1) * iv / (2 * np.sqrt(T)) 
                    - r * K * np.exp(-r * T) * N(d2)) / TRADING_DAYS_PER_YEAR
        else:  # PUT
            delta = N(d1) - 1
            theta = (-S * n(d1) * iv / (2 * np.sqrt(T)) 
                    + r * K * np.exp(-r * T) * N(-d2)) / TRADING_DAYS_PER_YEAR
            
        # Common Greeks
        gamma = n(d1) / (S * iv * np.sqrt(T))
        vega = S * n(d1) * np.sqrt(T) / 100  # Divide by 100 for 1% vol change
        rho = K * T * np.exp(-r * T) * (N(d2) if option.option_type == 'CALL' else N(-d2)) / 100
        
        # Lambda (elasticity)
        option_price = option.mid_price
        if option_price > 0:
            lambda_ = delta * S / option_price
        else:
            lambda_ = 0.0
            
        return Greeks(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            lambda_=lambda_
        )
        
    def calculate_implied_volatility(self, option: OptionContract) -> float:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Args:
            option: Option contract
            
        Returns:
            Implied volatility
        """
        S = option.underlying_price
        K = option.strike
        T = option.time_to_expiry
        r = RISK_FREE_RATE
        market_price = option.mid_price
        
        if market_price <= 0 or S <= 0 or T <= 0:
            return 0.0
            
        # Initial guess using Brenner-Subrahmanyam approximation
        initial_iv = np.sqrt(2 * np.pi / T) * market_price / S
        
        # Bounds check
        initial_iv = np.clip(initial_iv, MIN_IV, MAX_IV)
        
        # Newton-Raphson iteration
        iv = initial_iv
        for i in range(MAX_ITERATIONS):
            # Calculate option price and vega
            bs_price = self._black_scholes_price(S, K, T, r, iv, option.option_type)
            vega = self._black_scholes_vega(S, K, T, r, iv)
            
            # Check convergence
            price_diff = market_price - bs_price
            if abs(price_diff) < IV_TOLERANCE:
                return iv
                
            # Avoid division by zero
            if vega < 0.0001:
                break
                
            # Newton step with dampening
            iv_new = iv + price_diff / vega * 0.8
            
            # Ensure within bounds
            iv_new = np.clip(iv_new, MIN_IV, MAX_IV)
            
            # Check for convergence
            if abs(iv_new - iv) < IV_TOLERANCE:
                return iv_new
                
            iv = iv_new
            
        # If didn't converge, try bisection method
        return self._bisection_iv(option, MIN_IV, MAX_IV)
        
    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _black_scholes_price(self, S: float, K: float, T: float, r: float,
                           sigma: float, option_type: str) -> float:
        """Calculate Black-Scholes option price."""
        if T <= 0 or sigma <= 0:
            return 0.0
            
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == 'CALL':
            return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:  # PUT
            return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
    def _black_scholes_vega(self, S: float, K: float, T: float, r: float,
                          sigma: float) -> float:
        """Calculate Black-Scholes vega."""
        if T <= 0 or sigma <= 0:
            return 0.0
            
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        return S * norm.pdf(d1) * np.sqrt(T)
        
    def _bisection_iv(self, option: OptionContract, low_iv: float, high_iv: float) -> float:
        """Fallback bisection method for IV calculation."""
        S = option.underlying_price
        K = option.strike
        T = option.time_to_expiry
        r = RISK_FREE_RATE
        market_price = option.mid_price
        
        for i in range(MAX_ITERATIONS):
            mid_iv = (low_iv + high_iv) / 2
            bs_price = self._black_scholes_price(S, K, T, r, mid_iv, option.option_type)
            
            if abs(bs_price - market_price) < IV_TOLERANCE:
                return mid_iv
                
            if bs_price < market_price:
                low_iv = mid_iv
            else:
                high_iv = mid_iv
                
            if high_iv - low_iv < IV_TOLERANCE:
                return mid_iv
                
        return (low_iv + high_iv) / 2
        
    # ==========================================================================
    # PRIVATE METHODS - VOLATILITY SURFACE
    # ==========================================================================
    def _build_volatility_surface(self) -> Optional[VolatilitySurface]:
        """Build implied volatility surface from option chains."""
        if not self.option_chains or self.spot_price <= 0:
            return None
            
        # Collect all valid IV points
        strikes = []
        times = []
        ivs = []
        
        for expiry, chain in self.option_chains.items():
            time_to_expiry = (expiry - date.today()).days / TRADING_DAYS_PER_YEAR
            
            if time_to_expiry <= 0:
                continue
                
            for option in chain:
                # Filter strikes within reasonable range
                if (abs(option.strike - self.spot_price) / self.spot_price > STRIKE_RANGE_PERCENT):
                    continue
                    
                # Calculate IV
                iv = self.calculate_implied_volatility(option)
                
                if MIN_IV < iv < MAX_IV:
                    strikes.append(option.strike)
                    times.append(time_to_expiry)
                    ivs.append(iv)
                    
        if len(strikes) < MIN_STRIKES_FOR_SURFACE:
            return None
            
        # Convert to numpy arrays
        strikes = np.array(strikes)
        times = np.array(times)
        ivs = np.array(ivs)
        
        # Create regular grid for interpolation
        strike_range = [strikes.min(), strikes.max()]
        time_range = [times.min(), times.max()]
        
        strike_grid = np.linspace(strike_range[0], strike_range[1], MONEYNESS_GRID_POINTS)
        time_grid = np.linspace(time_range[0], time_range[1], TIME_GRID_POINTS)
        
        # 2D interpolation
        try:
            # Use RBF interpolation for smooth surface
            from scipy.interpolate import Rbf
            interpolator = Rbf(strikes, times, ivs, function='thin_plate', smooth=0.1)
            
            # Evaluate on grid
            strike_mesh, time_mesh = np.meshgrid(strike_grid, time_grid)
            iv_surface = interpolator(strike_mesh.ravel(), time_mesh.ravel()).reshape(strike_mesh.shape)
            
            return VolatilitySurface(
                spot_price=self.spot_price,
                calculation_time=datetime.now(),
                strikes=strike_grid,
                expirations=time_grid,
                ivs=iv_surface,
                interpolator=interpolator
            )
            
        except Exception as e:
            self.logger.error(f"Surface interpolation error: {e}")
            return None
            
    def _analyze_volatility_smile(self) -> Tuple[float, float]:
        """Analyze volatility smile characteristics."""
        if not self.surface:
            return 0.0, 0.0
            
        # Get ATM slice (shortest expiry)
        atm_strike = self.spot_price
        shortest_expiry = self.surface.expirations.min()
        
        # Sample strikes around ATM
        strikes = np.linspace(
            atm_strike * 0.9,
            atm_strike * 1.1,
            21
        )
        
        # Get IVs for these strikes
        ivs = [self.surface.get_iv(k, shortest_expiry) for k in strikes]
        
        # Fit quadratic to get slope and curvature
        try:
            # Normalize strikes
            x = (strikes - atm_strike) / atm_strike
            coeffs = np.polyfit(x, ivs, 2)
            
            # Slope at ATM (first derivative at x=0)
            slope = coeffs[1]
            
            # Curvature (second derivative)
            curvature = 2 * coeffs[0]
            
            return slope, curvature
            
        except Exception:
            return 0.0, 0.0
            
    # ==========================================================================
    # PRIVATE METHODS - VOLATILITY REGIME
    # ==========================================================================
    def _detect_volatility_regime(self) -> VolatilityMetrics:
        """Detect current volatility regime."""
        # Calculate various volatility measures
        spot_vol = self._calculate_spot_volatility()
        realized_vol = self._calculate_realized_volatility()
        garch_vol = self._calculate_garch_forecast()
        
        # ATM IV as VIX proxy
        vix_proxy = self._calculate_vix_proxy()
        
        # Put-call ratio
        pc_ratio = self._calculate_put_call_ratio()
        
        # Term structure
        term_slope = self._calculate_term_structure_slope()
        
        # Smile characteristics
        smile_slope, smile_curve = self._analyze_volatility_smile()
        
        # Determine regime
        regime = self._classify_regime(spot_vol, realized_vol, vix_proxy)
        
        # Calculate regime probabilities
        regime_probs = self._calculate_regime_probabilities(
            spot_vol, realized_vol, vix_proxy, pc_ratio
        )
        
        return VolatilityMetrics(
            current_regime=regime,
            spot_volatility=spot_vol,
            realized_volatility=realized_vol,
            garch_forecast=garch_vol,
            vix_proxy=vix_proxy,
            put_call_ratio=pc_ratio,
            term_structure_slope=term_slope,
            smile_slope=smile_slope,
            smile_curvature=smile_curve,
            regime_probability=regime_probs
        )
        
    def _calculate_spot_volatility(self) -> float:
        """Calculate instantaneous volatility from recent ticks."""
        if len(self.tick_history) < 10:
            return 0.0
            
        # Get recent log returns
        prices = [tick.last for tick in self.tick_history[-100:]]
        if len(prices) < 2:
            return 0.0
            
        log_returns = np.diff(np.log(prices))
        
        # Annualize
        return np.std(log_returns) * np.sqrt(TRADING_DAYS_PER_YEAR * SECONDS_PER_TRADING_DAY)
        
    def _calculate_realized_volatility(self, lookback_days: int = 20) -> float:
        """Calculate realized volatility over lookback period."""
        # This is simplified - in production you'd use actual historical data
        # For now, use tick history
        return self._calculate_spot_volatility()  # Placeholder
        
    def _calculate_garch_forecast(self) -> float:
        """Calculate GARCH(1,1) volatility forecast."""
        if len(self.tick_history) < 100:
            return self._calculate_spot_volatility()
            
        # Simplified GARCH - in production use proper implementation
        spot_vol = self._calculate_spot_volatility()
        long_term_vol = 0.16  # Long-term average
        
        # Simple mean reversion
        return 0.7 * spot_vol + 0.3 * long_term_vol
        
    def _calculate_vix_proxy(self) -> float:
        """Calculate VIX-like measure from ATM options."""
        if not self.option_chains:
            return 0.0
            
        # Find nearest 30-day options
        target_days = 30
        best_chain = None
        best_diff = float('inf')
        
        for expiry, chain in self.option_chains.items():
            days_to_expiry = (expiry - date.today()).days
            if abs(days_to_expiry - target_days) < best_diff:
                best_diff = abs(days_to_expiry - target_days)
                best_chain = chain
                
        if not best_chain:
            return 0.0
            
        # Calculate ATM IV
        atm_calls = [opt for opt in best_chain 
                    if opt.option_type == 'CALL' 
                    and abs(opt.strike - self.spot_price) < 1.0]
        
        if atm_calls:
            return self.calculate_implied_volatility(atm_calls[0])
            
        return 0.0
        
    def _calculate_put_call_ratio(self) -> float:
        """Calculate put/call volume ratio."""
        put_volume = 0
        call_volume = 0
        
        for option in self.options.values():
            if option.option_type == 'PUT':
                put_volume += option.volume
            else:
                call_volume += option.volume
                
        if call_volume > 0:
            return put_volume / call_volume
        return 1.0
        
    def _calculate_term_structure_slope(self) -> float:
        """Calculate volatility term structure slope."""
        if not self.surface:
            return 0.0
            
        # Get ATM IVs at different expirations
        atm_strike = self.spot_price
        
        # Sample at 30 and 90 days
        if len(self.surface.expirations) < 2:
            return 0.0
            
        short_term = self.surface.expirations[0]
        long_term = self.surface.expirations[-1]
        
        short_iv = self.surface.get_iv(atm_strike, short_term)
        long_iv = self.surface.get_iv(atm_strike, long_term)
        
        # Slope
        return (long_iv - short_iv) / (long_term - short_term)
        
    def _classify_regime(self, spot_vol: float, realized_vol: float, 
                        vix_proxy: float) -> VolatilityRegime:
        """Classify volatility regime based on metrics."""
        # Use ensemble approach
        avg_vol = (spot_vol + realized_vol + vix_proxy) / 3
        
        if avg_vol < 0.10:
            return VolatilityRegime.LOW
        elif avg_vol < 0.20:
            return VolatilityRegime.NORMAL
        elif avg_vol < 0.35:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME
            
    def _calculate_regime_probabilities(self, spot_vol: float, realized_vol: float,
                                      vix_proxy: float, pc_ratio: float) -> Dict[VolatilityRegime, float]:
        """Calculate probability of each regime using Bayesian approach."""
        # Simplified probability calculation
        features = np.array([spot_vol, realized_vol, vix_proxy, pc_ratio])
        
        # Define regime centers (typical values)
        regime_centers = {
            VolatilityRegime.LOW: np.array([0.08, 0.08, 0.10, 0.8]),
            VolatilityRegime.NORMAL: np.array([0.15, 0.15, 0.16, 1.0]),
            VolatilityRegime.HIGH: np.array([0.25, 0.25, 0.28, 1.5]),
            VolatilityRegime.EXTREME: np.array([0.40, 0.40, 0.45, 2.0])
        }
        
        # Calculate distances
        probs = {}
        total = 0.0
        
        for regime, center in regime_centers.items():
            # Mahalanobis-like distance (simplified)
            distance = np.linalg.norm(features - center)
            prob = np.exp(-distance)
            probs[regime] = prob
            total += prob
            
        # Normalize
        if total > 0:
            for regime in probs:
                probs[regime] /= total
        else:
            # Equal probabilities
            for regime in VolatilityRegime:
                probs[regime] = 0.25
                
        return probs
        
    # ==========================================================================
    # PRIVATE METHODS - MAIN LOOPS
    # ==========================================================================
    def _calculation_loop(self) -> None:
        """Main calculation loop running in separate thread."""
        while not self.shutdown_event.is_set():
            try:
                now = time.time()
                
                # Regular Greeks calculation
                if now - self.last_calculation > CALCULATION_INTERVAL:
                    self._calculate_all_greeks()
                    self.last_calculation = now
                    
                # Surface update
                if now - self.last_surface_update > SURFACE_UPDATE_INTERVAL:
                    self._update_volatility_surface()
                    self.last_surface_update = now
                    
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"Calculation loop error: {e}")
                self.error_handler.handle_error(e, {"context": "calculation_loop"})
                
    def _broadcast_loop(self) -> None:
        """Broadcast updates to coordinator."""
        while not self.shutdown_event.is_set():
            try:
                now = time.time()
                
                if now - self.last_broadcast > BROADCAST_INTERVAL:
                    self._broadcast_updates()
                    self.last_broadcast = now
                    
                time.sleep(0.1)
                
            except Exception as e:
                self.logger.error(f"Broadcast loop error: {e}")
                
    def _calculate_all_greeks(self) -> None:
        """Calculate Greeks for all options and portfolio."""
        portfolio_delta = 0.0
        portfolio_gamma = 0.0
        portfolio_theta = 0.0
        portfolio_vega = 0.0
        portfolio_rho = 0.0
        
        for symbol, option in self.options.items():
            try:
                # Calculate Greeks
                greeks = self.calculate_greeks(option)
                
                # Aggregate portfolio Greeks (would need position sizes)
                # For now, just sum them
                portfolio_delta += greeks.delta
                portfolio_gamma += greeks.gamma
                portfolio_theta += greeks.theta
                portfolio_vega += greeks.vega
                portfolio_rho += greeks.rho
                
            except Exception as e:
                self.logger.error(f"Greeks calculation error for {symbol}: {e}")
                
        # Update portfolio Greeks
        self.portfolio_greeks.timestamp = time.time()
        self.portfolio_greeks.total_delta = portfolio_delta
        self.portfolio_greeks.total_gamma = portfolio_gamma
        self.portfolio_greeks.total_theta = portfolio_theta
        self.portfolio_greeks.total_vega = portfolio_vega
        self.portfolio_greeks.total_rho = portfolio_rho
        
        # Dollar Greeks (multiply by spot price)
        self.portfolio_greeks.delta_dollars = portfolio_delta * self.spot_price * 100
        self.portfolio_greeks.gamma_dollars = portfolio_gamma * self.spot_price * 100
        self.portfolio_greeks.theta_dollars = portfolio_theta  # Already in dollars
        self.portfolio_greeks.vega_dollars = portfolio_vega  # Already in dollars
        
    def _update_volatility_surface(self) -> None:
        """Update volatility surface and regime detection."""
        # Build new surface
        with self.surface_lock:
            self.surface = self._build_volatility_surface()
            
        # Detect regime
        self.metrics = self._detect_volatility_regime()
        
        # Check for anomalies
        if SKLEARN_AVAILABLE:
            self._detect_volatility_anomalies()
            
    def _detect_volatility_anomalies(self) -> None:
        """Detect anomalies in volatility patterns."""
        if not self.surface or not self.metrics:
            return
            
        # Use Isolation Forest for anomaly detection
        try:
            # Prepare features
            features = np.array([
                self.metrics.spot_volatility,
                self.metrics.vix_proxy,
                self.metrics.put_call_ratio,
                self.metrics.smile_slope,
                self.metrics.smile_curvature
            ]).reshape(1, -1)
            
            # Simple threshold-based detection for now
            # In production, train proper anomaly detector
            if self.metrics.spot_volatility > 0.5:  # 50% vol
                self._send_anomaly_alert("Extreme volatility detected", "HIGH")
            elif abs(self.metrics.smile_slope) > 0.5:
                self._send_anomaly_alert("Abnormal volatility skew", "MEDIUM")
            elif self.metrics.put_call_ratio > 3.0:
                self._send_anomaly_alert("Extreme put/call ratio", "MEDIUM")
                
        except Exception as e:
            self.logger.error(f"Anomaly detection error: {e}")
            
    # ==========================================================================
    # PRIVATE METHODS - COMMUNICATION
    # ==========================================================================
    def _handle_command(self, message: Dict) -> None:
        """Handle command from coordinator."""
        command_type = message.get('command_type')
        command_id = message.get('command_id')
        
        try:
            result = None
            
            if command_type == CommandType.CALCULATE.value:
                # Force recalculation
                self._calculate_all_greeks()
                self._update_volatility_surface()
                result = {'status': 'calculated'}
                
            elif command_type == CommandType.STATUS.value:
                # Return current status
                result = {
                    'spot_price': self.spot_price,
                    'portfolio_greeks': self.portfolio_greeks.get_risk_summary(),
                    'volatility_regime': self.metrics.current_regime.value if self.metrics else None,
                    'option_count': len(self.options)
                }
                
            elif command_type == CommandType.CONFIGURE.value:
                # Update configuration
                config = message.get('data', {})
                if 'calculation_mode' in config:
                    self.calculation_mode = CalculationMode[config['calculation_mode']]
                result = {'status': 'configured'}
                
            else:
                result = {'error': f'Unknown command: {command_type}'}
                
            # Send response
            response = {
                'type': 'RESPONSE',
                'command_id': command_id,
                'result': result
            }
            self.dealer_socket.send_json(response)
            
        except Exception as e:
            self.logger.error(f"Command handling error: {e}")
            error_response = {
                'type': 'RESPONSE',
                'command_id': command_id,
                'result': {'error': str(e)}
            }
            self.dealer_socket.send_json(error_response)
            
    def _broadcast_updates(self) -> None:
        """Broadcast volatility updates."""
        try:
            # Broadcast portfolio Greeks
            greeks_event = {
                'type': 'EVENT',
                'event_type': 'GREEK_UPDATE',
                'data': {
                    'timestamp': self.portfolio_greeks.timestamp,
                    'greeks': self.portfolio_greeks.get_risk_summary(),
                    'spot_price': self.spot_price
                }
            }
            self.dealer_socket.send_json(greeks_event)
            
            # Broadcast volatility metrics
            if self.metrics:
                vol_event = {
                    'type': 'EVENT',
                    'event_type': 'VOLATILITY_UPDATE',
                    'data': {
                        'regime': self.metrics.current_regime.value,
                        'spot_vol': self.metrics.spot_volatility,
                        'vix_proxy': self.metrics.vix_proxy,
                        'put_call_ratio': self.metrics.put_call_ratio,
                        'regime_probabilities': {
                            k.value: v for k, v in self.metrics.regime_probability.items()
                        }
                    }
                }
                self.dealer_socket.send_json(vol_event)
                
        except Exception as e:
            self.logger.error(f"Broadcast error: {e}")
            
    def _send_anomaly_alert(self, description: str, severity: str) -> None:
        """Send anomaly alert to coordinator."""
        alert = {
            'type': 'EVENT',
            'event_type': 'ANOMALY_DETECTED',
            'data': {
                'source': 'VOLATILITY_ENGINE',
                'description': description,
                'severity': severity,
                'timestamp': time.time(),
                'metrics': {
                    'spot_vol': self.metrics.spot_volatility if self.metrics else None,
                    'vix_proxy': self.metrics.vix_proxy if self.metrics else None,
                    'regime': self.metrics.current_regime.value if self.metrics else None
                }
            }
        }
        
        try:
            self.dealer_socket.send_json(alert)
            self.logger.warning(f"Anomaly alert sent: {description}")
        except Exception as e:
            self.logger.error(f"Failed to send anomaly alert: {e}")
            
    def _process_tick_data(self) -> None:
        """Process tick data from shared memory."""
        if not self.tick_buffer:
            return
            
        try:
            # Read recent ticks
            tick_count = min(100, self.tick_index.value)
            
            for i in range(tick_count):
                # Read tick from circular buffer
                # This is simplified - real implementation would be more efficient
                
                # Update spot price if SPY
                # Process option ticks
                pass
                
        except Exception as e:
            self.logger.error(f"Tick processing error: {e}")
            
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up engine resources."""
        # Wait for threads to finish
        if self.calculation_thread:
            self.calculation_thread.join(timeout=1.0)
        if self.broadcast_thread:
            self.broadcast_thread.join(timeout=1.0)
            
        super().cleanup()
        self.logger.info("Volatility engine cleanup completed")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_test_option_chain() -> List[OptionContract]:
    """Create test option chain for development."""
    spot = 450.0
    expiry = date.today() + timedelta(days=30)
    strikes = np.arange(420, 481, 5)
    
    chain = []
    for strike in strikes:
        for opt_type in ['CALL', 'PUT']:
            # Generate realistic prices
            moneyness = spot / strike
            if opt_type == 'CALL':
                intrinsic = max(spot - strike, 0)
            else:
                intrinsic = max(strike - spot, 0)
                
            # Add time value
            time_value = 2.0 * np.exp(-abs(spot - strike) / 20)
            mid_price = intrinsic + time_value
            
            option = OptionContract(
                symbol=f"SPY{expiry.strftime('%y%m%d')}{opt_type[0]}{int(strike)}",
                underlying="SPY",
                strike=strike,
                expiry=expiry,
                option_type=opt_type,
                bid=mid_price - 0.05,
                ask=mid_price + 0.05,
                last=mid_price,
                volume=np.random.randint(100, 10000),
                open_interest=np.random.randint(1000, 50000),
                underlying_price=spot
            )
            chain.append(option)
            
    return chain

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing code
    print("✅ Volatility Engine Module")
    print("-" * 60)
    
    # Test Greeks calculation
    test_option = OptionContract(
        symbol="SPY240730C450",
        underlying="SPY",
        strike=450.0,
        expiry=date.today() + timedelta(days=30),
        option_type="CALL",
        bid=5.20,
        ask=5.30,
        last=5.25,
        volume=1000,
        open_interest=5000,
        underlying_price=450.0
    )
    
    # Create mock engine for testing
    class MockEngine:
        def calculate_implied_volatility(self, option):
            return 0.16  # 16% IV
            
        def calculate_greeks(self, option, iv=None):
            engine = VolatilityEngine(EngineType.VOLATILITY, mp.Event(), "test")
            return engine.calculate_greeks(option, iv)
    
    engine = MockEngine()
    
    # Test IV calculation
    iv = engine.calculate_implied_volatility(test_option)
    print(f"Implied Volatility: {iv:.2%}")
    
    # Test Greeks
    greeks = engine.calculate_greeks(test_option, iv)
    print(f"\nGreeks for {test_option.symbol}:")
    print(f"  Delta: {greeks.delta:.4f}")
    print(f"  Gamma: {greeks.gamma:.4f}")
    print(f"  Theta: {greeks.theta:.4f}")
    print(f"  Vega: {greeks.vega:.4f}")
    print(f"  Rho: {greeks.rho:.4f}")
    print(f"  Lambda: {greeks.lambda_:.4f}")
    
    # Test chain
    print("\nGenerating test option chain...")
    chain = create_test_option_chain()
    print(f"Created {len(chain)} options")
    
    print("\n✅ All tests passed")
