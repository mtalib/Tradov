#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF06_GreeksCalculator.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, Optional, Tuple, Union, List
from enum import Enum
from datetime import datetime, timedelta
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import math
import numpy as np
from scipy.stats import norm
from scipy.optimize import minimize_scalar, brentq
import pandas as pd
from numba import jit, prange
import cachetools

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager

class PricingModel(Enum):
    """Supported pricing models."""
    BLACK_SCHOLES = "black_scholes"
    BINOMIAL = "binomial"
    TRINOMIAL = "trinomial"
    MONTE_CARLO = "monte_carlo"
    AUTO = "auto"  # Automatically choose based on option type

class OptionStyle(Enum):
    """Option exercise style."""
    EUROPEAN = "european"
    AMERICAN = "american"

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class GreeksCalculator:
    """
    Advanced Greeks calculator supporting both European and American options.
    
    Features:
    - Black-Scholes for European options
    - Binomial/Trinomial trees for American options
    - Dividend support
    - Volatility smile interpolation
    - High-performance calculations with caching
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """Initialize the Greeks calculator."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager or ConfigManager()
        
        # Load configuration
        self._load_config()
        
        # Initialize caches
        self._init_caches()
        
        self.logger.info("GreeksCalculator initialized with American options support")
    
    def _load_config(self):
        """Load configuration from ConfigManager."""
        try:
            # Get config section for Greeks calculation
            config = self.config_manager.get_config('greeks_calculator', {})
            
            # Model parameters
            self.binomial_steps = config.get('binomial_steps', 100)
            self.trinomial_steps = config.get('trinomial_steps', 100)
            self.monte_carlo_simulations = config.get('monte_carlo_simulations', 10000)
            
            # Cache settings
            self.cache_ttl = config.get('cache_ttl_seconds', 60)
            self.cache_size = config.get('cache_size', 10000)
            
            # Numerical parameters
            self.epsilon = config.get('epsilon', 0.01)  # For numerical derivatives
            self.iv_tolerance = config.get('iv_tolerance', 1e-6)
            self.iv_max_iterations = config.get('iv_max_iterations', 100)
            
            # Volatility smile parameters
            self.use_volatility_smile = config.get('use_volatility_smile', False)
            self.smile_interpolation = config.get('smile_interpolation', 'cubic')
            
        except Exception as e:
            self.logger.warning(f"Could not load config, using defaults: {e}")
            # Use default values
            self.binomial_steps = 100
            self.trinomial_steps = 100
            self.monte_carlo_simulations = 10000
            self.cache_ttl = 60
            self.cache_size = 10000
            self.epsilon = 0.01
            self.iv_tolerance = 1e-6
            self.iv_max_iterations = 100
            self.use_volatility_smile = False
            self.smile_interpolation = 'cubic'
    
    def _init_caches(self):
        """Initialize caching mechanisms."""
        # TTL cache for Greeks calculations
        self._greeks_cache = cachetools.TTLCache(
            maxsize=self.cache_size,
            ttl=self.cache_ttl
        )
        
        # LRU cache for implied volatility
        self._iv_cache = cachetools.LRUCache(maxsize=self.cache_size // 2)
        
        # Cache for volatility smile
        self._smile_cache = cachetools.TTLCache(
            maxsize=100,
            ttl=self.cache_ttl * 5  # Longer TTL for smile
        )
    
    # ==========================================================================
    # PUBLIC METHODS - MAIN INTERFACE
    # ==========================================================================
    
    def calculate_option_price(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = 'call',
        style: Union[str, OptionStyle] = OptionStyle.EUROPEAN,
        dividends: Optional[List[Tuple[float, float]]] = None,
        model: Union[str, PricingModel] = PricingModel.AUTO
    ) -> float:
        """
        Calculate option price with support for American options.
        
        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Volatility
            option_type: 'call' or 'put'
            style: European or American
            dividends: List of (time, amount) tuples
            model: Pricing model to use
            
        Returns:
            Option price
        """
        try:
            # Validate inputs
            self._validate_inputs(S, K, T, r, sigma)
            
            # Convert string inputs to enums
            if isinstance(style, str):
                style = OptionStyle(style.lower())
            if isinstance(model, str):
                model = PricingModel(model.lower())
            
            # Auto-select model if needed
            if model == PricingModel.AUTO:
                model = self._select_model(style, dividends)
            
            # Check cache
            cache_key = (S, K, T, r, sigma, option_type, style.value, 
                        str(dividends), model.value)
            if cache_key in self._greeks_cache:
                return self._greeks_cache[cache_key]
            
            # Apply volatility smile if enabled
            if self.use_volatility_smile:
                sigma = self._adjust_for_smile(S, K, T, sigma)
            
            # Calculate price based on model
            if model == PricingModel.BLACK_SCHOLES:
                if style == OptionStyle.AMERICAN:
                    self.logger.warning(
                        "Black-Scholes used for American option - switching to Binomial"
                    )
                    price = self._binomial_tree(
                        S, K, T, r, sigma, option_type, True, dividends
                    )
                else:
                    price = self._black_scholes_price(S, K, T, r, sigma, option_type)
            
            elif model == PricingModel.BINOMIAL:
                is_american = (style == OptionStyle.AMERICAN)
                price = self._binomial_tree(
                    S, K, T, r, sigma, option_type, is_american, dividends
                )
            
            elif model == PricingModel.TRINOMIAL:
                is_american = (style == OptionStyle.AMERICAN)
                price = self._trinomial_tree(
                    S, K, T, r, sigma, option_type, is_american, dividends
                )
            
            elif model == PricingModel.MONTE_CARLO:
                # Monte Carlo for European only (for now)
                if style == OptionStyle.AMERICAN:
                    self.logger.warning(
                        "Monte Carlo doesn't support American - using Binomial"
                    )
                    price = self._binomial_tree(
                        S, K, T, r, sigma, option_type, True, dividends
                    )
                else:
                    price = self._monte_carlo_price(
                        S, K, T, r, sigma, option_type, dividends
                    )
            
            # Cache result
            self._greeks_cache[cache_key] = price
            
            return price
            
        except Exception as e:
            self.logger.error(f"Error calculating option price: {e}")
            return 0.0
    
    def calculate_all_greeks(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str = 'call',
        style: Union[str, OptionStyle] = OptionStyle.EUROPEAN,
        dividends: Optional[List[Tuple[float, float]]] = None,
        model: Union[str, PricingModel] = PricingModel.AUTO
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for an option.
        
        Returns:
            Dictionary with price, delta, gamma, theta, vega, rho
        """
        try:
            # Convert inputs
            if isinstance(style, str):
                style = OptionStyle(style.lower())
            if isinstance(model, str):
                model = PricingModel(model.lower())
            
            # For European options with no dividends, use analytical Greeks
            if (style == OptionStyle.EUROPEAN and not dividends and 
                model in [PricingModel.BLACK_SCHOLES, PricingModel.AUTO]):
                return self._analytical_greeks(S, K, T, r, sigma, option_type)
            
            # For American options or with dividends, use numerical Greeks
            greeks = {}
            
            # Base price
            greeks['price'] = self.calculate_option_price(
                S, K, T, r, sigma, option_type, style, dividends, model
            )
            
            # Delta: ∂V/∂S
            greeks['delta'] = self._numerical_delta(
                S, K, T, r, sigma, option_type, style, dividends, model
            )
            
            # Gamma: ∂²V/∂S²
            greeks['gamma'] = self._numerical_gamma(
                S, K, T, r, sigma, option_type, style, dividends, model
            )
            
            # Theta: ∂V/∂T (negative of derivative)
            greeks['theta'] = self._numerical_theta(
                S, K, T, r, sigma, option_type, style, dividends, model
            )
            
            # Vega: ∂V/∂σ
            greeks['vega'] = self._numerical_vega(
                S, K, T, r, sigma, option_type, style, dividends, model
            )
            
            # Rho: ∂V/∂r
            greeks['rho'] = self._numerical_rho(
                S, K, T, r, sigma, option_type, style, dividends, model
            )
            
            return greeks
            
        except Exception as e:
            self.logger.error(f"Error calculating Greeks: {e}")
            return {
                'price': 0.0,
                'delta': 0.0,
                'gamma': 0.0,
                'theta': 0.0,
                'vega': 0.0,
                'rho': 0.0
            }
    
    def calculate_implied_volatility(
        self,
        option_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str = 'call',
        style: Union[str, OptionStyle] = OptionStyle.EUROPEAN,
        dividends: Optional[List[Tuple[float, float]]] = None
    ) -> Optional[float]:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Returns:
            Implied volatility or None if not found
        """
        try:
            # Check cache
            cache_key = (option_price, S, K, T, r, option_type, str(style), str(dividends))
            if cache_key in self._iv_cache:
                return self._iv_cache[cache_key]
            
            # Convert style
            if isinstance(style, str):
                style = OptionStyle(style.lower())
            
            # Use Brent's method for robustness
            def objective(sigma):
                calc_price = self.calculate_option_price(
                    S, K, T, r, sigma, option_type, style, dividends
                )
                return calc_price - option_price
            
            # Initial guess using Brenner-Subrahmanyam approximation
            initial_sigma = math.sqrt(2 * math.pi / T) * (option_price / S)
            
            try:
                # Try to find a bracket
                if objective(0.001) * objective(5.0) < 0:
                    iv = brentq(objective, 0.001, 5.0, xtol=self.iv_tolerance)
                else:
                    # Fall back to minimize
                    result = minimize_scalar(
                        lambda sig: abs(objective(sig)),
                        bounds=(0.001, 5.0),
                        method='bounded'
                    )
                    iv = result.x if result.fun < 0.01 else None
                
                # Cache result
                if iv is not None:
                    self._iv_cache[cache_key] = iv
                
                return iv
                
            except Exception as e:
                self.logger.warning(f"IV calculation failed: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in implied volatility calculation: {e}")
            return None
    
    # ==========================================================================
    # PRIVATE METHODS - BLACK-SCHOLES
    # ==========================================================================
    
    def _black_scholes_price(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str
    ) -> float:
        """Calculate Black-Scholes price for European option."""
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        if option_type.lower() == 'call':
            price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        return price
    
    def _analytical_greeks(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str
    ) -> Dict[str, float]:
        """Calculate analytical Greeks for Black-Scholes."""
        sqrt_T = math.sqrt(T)
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
        d2 = d1 - sigma * sqrt_T
        
        # Common terms
        pdf_d1 = norm.pdf(d1)
        cdf_d1 = norm.cdf(d1)
        cdf_d2 = norm.cdf(d2)
        exp_rT = math.exp(-r * T)
        
        greeks = {}
        
        if option_type.lower() == 'call':
            greeks['price'] = S * cdf_d1 - K * exp_rT * cdf_d2
            greeks['delta'] = cdf_d1
            greeks['theta'] = (-S * pdf_d1 * sigma / (2 * sqrt_T) - 
                              r * K * exp_rT * cdf_d2) / 365
            greeks['rho'] = K * T * exp_rT * cdf_d2 / 100
        else:
            greeks['price'] = K * exp_rT * norm.cdf(-d2) - S * norm.cdf(-d1)
            greeks['delta'] = cdf_d1 - 1
            greeks['theta'] = (-S * pdf_d1 * sigma / (2 * sqrt_T) + 
                              r * K * exp_rT * norm.cdf(-d2)) / 365
            greeks['rho'] = -K * T * exp_rT * norm.cdf(-d2) / 100
        
        # Common Greeks
        greeks['gamma'] = pdf_d1 / (S * sigma * sqrt_T)
        greeks['vega'] = S * pdf_d1 * sqrt_T / 100
        
        return greeks
    
    # ==========================================================================
    # PRIVATE METHODS - BINOMIAL TREE
    # ==========================================================================
    
    @jit(nopython=True)
    def _binomial_tree_jit(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        is_call: bool,
        is_american: bool,
        steps: int
    ) -> float:
        """JIT-compiled binomial tree for performance."""
        dt = T / steps
        u = math.exp(sigma * math.sqrt(dt))
        d = 1 / u
        p = (math.exp(r * dt) - d) / (u - d)
        disc = math.exp(-r * dt)
        
        # Initialize asset prices at maturity
        asset_prices = np.zeros(steps + 1)
        for i in range(steps + 1):
            asset_prices[i] = S * (u ** (steps - i)) * (d ** i)
        
        # Initialize option values at maturity
        option_values = np.zeros(steps + 1)
        for i in range(steps + 1):
            if is_call:
                option_values[i] = max(0, asset_prices[i] - K)
            else:
                option_values[i] = max(0, K - asset_prices[i])
        
        # Step backwards through tree
        for j in range(steps - 1, -1, -1):
            for i in range(j + 1):
                asset_price = S * (u ** (j - i)) * (d ** i)
                
                # Continuation value
                option_values[i] = disc * (p * option_values[i] + 
                                         (1 - p) * option_values[i + 1])
                
                # Early exercise for American options
                if is_american:
                    if is_call:
                        exercise_value = max(0, asset_price - K)
                    else:
                        exercise_value = max(0, K - asset_price)
                    option_values[i] = max(option_values[i], exercise_value)
        
        return option_values[0]
    
    def _binomial_tree(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        is_american: bool,
        dividends: Optional[List[Tuple[float, float]]] = None
    ) -> float:
        """
        Binomial tree with dividend support.
        """
        is_call = option_type.lower() == 'call'
        
        # Handle dividends
        if dividends:
            # Convert to present value
            pv_dividends = sum(
                amount * math.exp(-r * time) 
                for time, amount in dividends 
                if time <= T
            )
            S_adjusted = S - pv_dividends
        else:
            S_adjusted = S
        
        # Use JIT-compiled function for performance
        return self._binomial_tree_jit(
            S_adjusted, K, T, r, sigma, is_call, is_american, self.binomial_steps
        )
    
    # ==========================================================================
    # PRIVATE METHODS - TRINOMIAL TREE
    # ==========================================================================
    
    def _trinomial_tree(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        is_american: bool,
        dividends: Optional[List[Tuple[float, float]]] = None
    ) -> float:
        """
        Trinomial tree implementation for American options.
        """
        steps = self.trinomial_steps
        dt = T / steps
        
        # Trinomial parameters
        u = math.exp(sigma * math.sqrt(2 * dt))
        d = 1 / u
        m = 1  # Middle move
        
        # Risk-neutral probabilities
        pu = ((math.exp(r * dt / 2) - math.exp(-sigma * math.sqrt(dt / 2))) / 
              (math.exp(sigma * math.sqrt(dt / 2)) - math.exp(-sigma * math.sqrt(dt / 2)))) ** 2
        pd = ((math.exp(sigma * math.sqrt(dt / 2)) - math.exp(r * dt / 2)) / 
              (math.exp(sigma * math.sqrt(dt / 2)) - math.exp(-sigma * math.sqrt(dt / 2)))) ** 2
        pm = 1 - pu - pd
        
        disc = math.exp(-r * dt)
        is_call = option_type.lower() == 'call'
        
        # Handle dividends
        if dividends:
            pv_dividends = sum(
                amount * math.exp(-r * time) 
                for time, amount in dividends 
                if time <= T
            )
            S = S - pv_dividends
        
        # Initialize asset prices at maturity
        asset_prices = np.zeros(2 * steps + 1)
        for i in range(2 * steps + 1):
            asset_prices[i] = S * (u ** max(0, i - steps)) * (d ** max(0, steps - i))
        
        # Initialize option values at maturity
        option_values = np.zeros(2 * steps + 1)
        for i in range(2 * steps + 1):
            if is_call:
                option_values[i] = max(0, asset_prices[i] - K)
            else:
                option_values[i] = max(0, K - asset_prices[i])
        
        # Step backwards through tree
        for j in range(steps - 1, -1, -1):
            for i in range(2 * j + 1):
                # Asset price at this node
                asset_price = S * (u ** max(0, i - j)) * (d ** max(0, j - i))
                
                # Continuation value
                cont_value = disc * (pu * option_values[i + 2] + 
                                   pm * option_values[i + 1] + 
                                   pd * option_values[i])
                
                # Early exercise for American options
                if is_american:
                    if is_call:
                        exercise_value = max(0, asset_price - K)
                    else:
                        exercise_value = max(0, K - asset_price)
                    option_values[i] = max(cont_value, exercise_value)
                else:
                    option_values[i] = cont_value
            
            # Trim the array for next iteration
            option_values = option_values[:2*j+1]
        
        return option_values[0]
    
    # ==========================================================================
    # PRIVATE METHODS - MONTE CARLO
    # ==========================================================================
    
    def _monte_carlo_price(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        dividends: Optional[List[Tuple[float, float]]] = None
    ) -> float:
        """
        Monte Carlo simulation for European options.
        """
        # Handle dividends
        if dividends:
            pv_dividends = sum(
                amount * math.exp(-r * time) 
                for time, amount in dividends 
                if time <= T
            )
            S = S - pv_dividends
        
        # Generate random paths
        np.random.seed(42)  # For reproducibility
        Z = np.random.standard_normal(self.monte_carlo_simulations)
        
        # Terminal stock prices
        ST = S * np.exp((r - 0.5 * sigma ** 2) * T + sigma * math.sqrt(T) * Z)
        
        # Payoffs
        if option_type.lower() == 'call':
            payoffs = np.maximum(ST - K, 0)
        else:
            payoffs = np.maximum(K - ST, 0)
        
        # Discounted expected payoff
        price = math.exp(-r * T) * np.mean(payoffs)
        
        return price
    
    # ==========================================================================
    # PRIVATE METHODS - NUMERICAL GREEKS
    # ==========================================================================
    
    def _numerical_delta(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        style: OptionStyle,
        dividends: Optional[List[Tuple[float, float]]],
        model: PricingModel
    ) -> float:
        """Calculate delta using finite differences."""
        h = S * self.epsilon
        
        price_up = self.calculate_option_price(
            S + h, K, T, r, sigma, option_type, style, dividends, model
        )
        price_down = self.calculate_option_price(
            S - h, K, T, r, sigma, option_type, style, dividends, model
        )
        
        return (price_up - price_down) / (2 * h)
    
    def _numerical_gamma(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        style: OptionStyle,
        dividends: Optional[List[Tuple[float, float]]],
        model: PricingModel
    ) -> float:
        """Calculate gamma using finite differences."""
        h = S * self.epsilon
        
        price_up = self.calculate_option_price(
            S + h, K, T, r, sigma, option_type, style, dividends, model
        )
        price_mid = self.calculate_option_price(
            S, K, T, r, sigma, option_type, style, dividends, model
        )
        price_down = self.calculate_option_price(
            S - h, K, T, r, sigma, option_type, style, dividends, model
        )
        
        return (price_up - 2 * price_mid + price_down) / (h ** 2)
    
    def _numerical_theta(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        style: OptionStyle,
        dividends: Optional[List[Tuple[float, float]]],
        model: PricingModel
    ) -> float:
        """Calculate theta using finite differences."""
        h = 1 / 365  # One day
        
        if T <= h:
            return 0.0
        
        price_now = self.calculate_option_price(
            S, K, T, r, sigma, option_type, style, dividends, model
        )
        price_later = self.calculate_option_price(
            S, K, T - h, r, sigma, option_type, style, dividends, model
        )
        
        return -(price_later - price_now) / h
    
    def _numerical_vega(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        style: OptionStyle,
        dividends: Optional[List[Tuple[float, float]]],
        model: PricingModel
    ) -> float:
        """Calculate vega using finite differences."""
        h = sigma * self.epsilon
        
        price_up = self.calculate_option_price(
            S, K, T, r, sigma + h, option_type, style, dividends, model
        )
        price_down = self.calculate_option_price(
            S, K, T, r, sigma - h, option_type, style, dividends, model
        )
        
        return (price_up - price_down) / (2 * h) / 100  # Divide by 100 for 1% vega
    
    def _numerical_rho(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
        option_type: str,
        style: OptionStyle,
        dividends: Optional[List[Tuple[float, float]]],
        model: PricingModel
    ) -> float:
        """Calculate rho using finite differences."""
        h = 0.0001  # 1 basis point
        
        price_up = self.calculate_option_price(
            S, K, T, r + h, sigma, option_type, style, dividends, model
        )
        price_down = self.calculate_option_price(
            S, K, T, r - h, sigma, option_type, style, dividends, model
        )
        
        return (price_up - price_down) / (2 * h) / 100  # Divide by 100 for 1% rho
    
    # ==========================================================================
    # PRIVATE METHODS - HELPERS
    # ==========================================================================
    
    def _validate_inputs(
        self,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float
    ) -> None:
        """Validate input parameters."""
        if S <= 0:
            raise ValueError("Stock price must be positive")
        if K <= 0:
            raise ValueError("Strike price must be positive")
        if T < 0:
            raise ValueError("Time to expiration cannot be negative")
        if sigma < 0:
            raise ValueError("Volatility cannot be negative")
        if T == 0:
            warnings.warn("Time to expiration is zero")
    
    def _select_model(
        self,
        style: OptionStyle,
        dividends: Optional[List[Tuple[float, float]]]
    ) -> PricingModel:
        """Automatically select appropriate pricing model."""
        if style == OptionStyle.AMERICAN or dividends:
            return PricingModel.BINOMIAL
        else:
            return PricingModel.BLACK_SCHOLES
    
    def _adjust_for_smile(
        self,
        S: float,
        K: float,
        T: float,
        base_sigma: float
    ) -> float:
        """
        Adjust volatility for smile/skew effect.
        
        This is a placeholder for volatility smile interpolation.
        In production, this would interpolate from a volatility surface.
        """
        # Simple skew adjustment based on moneyness
        moneyness = math.log(S / K) / (base_sigma * math.sqrt(T))
        
        # Quadratic smile approximation
        # In production, use actual market smile data
        smile_adjustment = 0.1 * moneyness ** 2 - 0.05 * moneyness
        
        adjusted_sigma = base_sigma * (1 + smile_adjustment)
        
        return max(0.01, adjusted_sigma)  # Ensure positive volatility
    
    # ==========================================================================
    # PUBLIC METHODS - PORTFOLIO GREEKS
    # ==========================================================================
    
    def calculate_portfolio_greeks(
        self,
        positions: List[Dict[str, Union[float, str]]]
    ) -> Dict[str, float]:
        """
        Calculate aggregate Greeks for a portfolio of options.
        
        Args:
            positions: List of position dictionaries with keys:
                - quantity: Number of contracts (negative for short)
                - S, K, T, r, sigma: Option parameters
                - option_type: 'call' or 'put'
                - style: 'european' or 'american'
                
        Returns:
            Dictionary of aggregate Greeks
        """
        portfolio_greeks = {
            'delta': 0.0,
            'gamma': 0.0,
            'theta': 0.0,
            'vega': 0.0,
            'rho': 0.0,
            'total_value': 0.0
        }
        
        for position in positions:
            quantity = position['quantity']
            
            # Calculate Greeks for this position
            greeks = self.calculate_all_greeks(
                S=position['S'],
                K=position['K'],
                T=position['T'],
                r=position['r'],
                sigma=position['sigma'],
                option_type=position['option_type'],
                style=position.get('style', 'european'),
                dividends=position.get('dividends')
            )
            
            # Aggregate
            contract_multiplier = 100  # Standard option contract
            for greek, value in greeks.items():
                if greek == 'price':
                    portfolio_greeks['total_value'] += value * quantity * contract_multiplier
                else:
                    portfolio_greeks[greek] += value * quantity * contract_multiplier
        
        return portfolio_greeks


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Initialize calculator
    calc = GreeksCalculator()
    
    # Example 1: European option
    print("=== European Call Option ===")
    euro_greeks = calc.calculate_all_greeks(
        S=100,
        K=105,
        T=0.25,
        r=0.05,
        sigma=0.2,
        option_type='call',
        style='european'
    )
    for greek, value in euro_greeks.items():
        print(f"{greek.capitalize()}: {value:.4f}")
    
    # Example 2: American put option
    print("\n=== American Put Option ===")
    amer_greeks = calc.calculate_all_greeks(
        S=100,
        K=105,
        T=0.25,
        r=0.05,
        sigma=0.2,
        option_type='put',
        style='american'
    )
    for greek, value in amer_greeks.items():
        print(f"{greek.capitalize()}: {value:.4f}")
    
    # Example 3: Option with dividends
    print("\n=== Call Option with Dividends ===")
    dividends = [(0.08, 2.0), (0.17, 2.0)]  # Two $2 dividends
    div_greeks = calc.calculate_all_greeks(
        S=100,
        K=105,
        T=0.25,
        r=0.05,
        sigma=0.2,
        option_type='call',
        style='american',
        dividends=dividends
    )
    for greek, value in div_greeks.items():
        print(f"{greek.capitalize()}: {value:.4f}")
    
    # Example 4: Implied volatility
    print("\n=== Implied Volatility ===")
    market_price = 3.5
    iv = calc.calculate_implied_volatility(
        option_price=market_price,
        S=100,
        K=105,
        T=0.25,
        r=0.05,
        option_type='call'
    )
    print(f"Market Price: ${market_price}")
    print(f"Implied Volatility: {iv:.2%}" if iv else "IV not found")
    
    # Example 5: Portfolio Greeks
    print("\n=== Portfolio Greeks ===")
    portfolio = [
        {
            'quantity': 10,  # Long 10 calls
            'S': 100, 'K': 105, 'T': 0.25, 'r': 0.05, 'sigma': 0.2,
            'option_type': 'call', 'style': 'european'
        },
        {
            'quantity': -5,  # Short 5 puts
            'S': 100, 'K': 95, 'T': 0.25, 'r': 0.05, 'sigma': 0.2,
            'option_type': 'put', 'style': 'american'
        }
    ]
    
    port_greeks = calc.calculate_portfolio_greeks(portfolio)
    for greek, value in port_greeks.items():
        print(f"{greek.capitalize()}: {value:.2f}")
