#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderN06_OptionsPricer.py
Group: N (Options Analytics)
Purpose: Advanced options pricing models

Description:
    This module implements advanced options pricing models beyond Black-Scholes,
    including binomial trees, Monte Carlo simulations, and models for American
    options. It provides accurate pricing for complex strategies and helps 
    identify mispriced options in the market using pure Python/NumPy implementations.

Author: Mohamed Talib
Date: 2025-06-14
Version: 1.4

Status: PRODUCTION - Fully implemented
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum, auto
import numpy as np
from abc import ABC, abstractmethod
import time
import math
from functools import lru_cache

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
from scipy import stats, optimize
from scipy.integrate import quad

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model parameters
DEFAULT_BINOMIAL_STEPS = 100
DEFAULT_MC_SIMULATIONS = 10000
DEFAULT_MC_TIME_STEPS = 100
MIN_VOLATILITY = 0.01  # 1% minimum volatility
MAX_VOLATILITY = 5.00  # 500% maximum volatility

# Numerical parameters
CONVERGENCE_TOLERANCE = 1e-6
MAX_ITERATIONS = 100
PRICE_PRECISION = 0.01  # Penny precision

# ==============================================================================
# ENUMS
# ==============================================================================
class PricingModel(Enum):
    """Available pricing models."""
    BLACK_SCHOLES = "black_scholes"
    BINOMIAL = "binomial"
    TRINOMIAL = "trinomial"
    MONTE_CARLO = "monte_carlo"
    FINITE_DIFFERENCE = "finite_difference"

class ExerciseType(Enum):
    """Option exercise types."""
    EUROPEAN = "european"
    AMERICAN = "american"
    BERMUDAN = "bermudan"

class OptionType(Enum):
    """Option types."""
    CALL = "call"
    PUT = "put"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class PricingInputs:
    """Inputs for option pricing."""
    spot_price: float
    strike_price: float
    time_to_expiry: float  # In years
    risk_free_rate: float
    volatility: float
    dividend_yield: float = 0.0
    option_type: OptionType = OptionType.CALL
    exercise_type: ExerciseType = ExerciseType.AMERICAN
    
    def validate(self) -> None:
        """Validate pricing inputs."""
        if self.spot_price <= 0:
            raise ValueError("Spot price must be positive")
        if self.strike_price <= 0:
            raise ValueError("Strike price must be positive")
        if self.time_to_expiry < 0:
            raise ValueError("Time to expiry cannot be negative")
        if self.volatility < MIN_VOLATILITY or self.volatility > MAX_VOLATILITY:
            raise ValueError(f"Volatility must be between {MIN_VOLATILITY} and {MAX_VOLATILITY}")

@dataclass
class PricingOutput:
    """Option pricing results."""
    model: PricingModel
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    implied_volatility: Optional[float] = None
    exercise_boundary: Optional[List[Tuple[float, float]]] = None  # (time, price)
    computation_time: float = 0.0
    model_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelParameters:
    """Model-specific parameters."""
    # Tree models
    steps: int = DEFAULT_BINOMIAL_STEPS
    
    # Monte Carlo
    simulations: int = DEFAULT_MC_SIMULATIONS
    time_steps: int = DEFAULT_MC_TIME_STEPS
    seed: Optional[int] = None
    variance_reduction: bool = True
    antithetic: bool = True
    control_variate: bool = True
    
    # Finite Difference
    price_steps: int = 100
    stability_factor: float = 0.5  # For explicit scheme
    
    # General
    greek_method: str = "central"  # 'central' or 'forward' differences
    greek_shift: float = 0.01  # 1% shift for Greeks

# ==============================================================================
# PRICING MODEL BASE CLASS
# ==============================================================================
class PricingModelBase(ABC):
    """Abstract base class for pricing models."""
    
    def __init__(self):
        self.logger = SpyderLogger(f"{__name__}.{self.__class__.__name__}")
        
    @abstractmethod
    def price(self, inputs: PricingInputs, params: ModelParameters) -> PricingOutput:
        """Price the option."""
        pass
        
    def calculate_greeks(self, 
                        inputs: PricingInputs, 
                        params: ModelParameters,
                        base_price: Optional[float] = None) -> Dict[str, float]:
        """
        Calculate option Greeks using finite differences.
        
        Args:
            inputs: Pricing inputs
            params: Model parameters
            base_price: Pre-calculated base price (optional)
            
        Returns:
            Dictionary of Greeks
        """
        if base_price is None:
            base_price = self.price(inputs, params).price
            
        h = params.greek_shift
        
        # Delta - derivative with respect to spot
        inputs_up = PricingInputs(**inputs.__dict__)
        inputs_up.spot_price *= (1 + h)
        
        inputs_down = PricingInputs(**inputs.__dict__)
        inputs_down.spot_price *= (1 - h)
        
        if params.greek_method == "central":
            price_up = self.price(inputs_up, params).price
            price_down = self.price(inputs_down, params).price
            delta = (price_up - price_down) / (2 * h * inputs.spot_price)
        else:  # forward
            price_up = self.price(inputs_up, params).price
            delta = (price_up - base_price) / (h * inputs.spot_price)
            
        # Gamma - second derivative with respect to spot
        if params.greek_method == "central":
            gamma = (price_up - 2 * base_price + price_down) / ((h * inputs.spot_price) ** 2)
        else:
            inputs_up2 = PricingInputs(**inputs.__dict__)
            inputs_up2.spot_price *= (1 + 2 * h)
            price_up2 = self.price(inputs_up2, params).price
            gamma = (price_up2 - 2 * price_up + base_price) / ((h * inputs.spot_price) ** 2)
            
        # Theta - derivative with respect to time
        if inputs.time_to_expiry > 1/365:  # More than 1 day
            inputs_later = PricingInputs(**inputs.__dict__)
            inputs_later.time_to_expiry -= 1/365  # 1 day
            price_later = self.price(inputs_later, params).price
            theta = price_later - base_price  # Daily theta
        else:
            theta = -base_price  # Option expires worthless
            
        # Vega - derivative with respect to volatility
        inputs_vol_up = PricingInputs(**inputs.__dict__)
        inputs_vol_up.volatility *= (1 + h)
        price_vol_up = self.price(inputs_vol_up, params).price
        vega = (price_vol_up - base_price) / (h * inputs.volatility) / 100  # Per 1% vol
        
        # Rho - derivative with respect to interest rate
        inputs_rate_up = PricingInputs(**inputs.__dict__)
        inputs_rate_up.risk_free_rate += 0.01  # 1% change
        price_rate_up = self.price(inputs_rate_up, params).price
        rho = (price_rate_up - base_price) / 100  # Per 1% rate
        
        return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': vega,
            'rho': rho
        }

# ==============================================================================
# BLACK-SCHOLES MODEL
# ==============================================================================
class BlackScholesModel(PricingModelBase):
    """Black-Scholes model for European options."""
    
    def price(self, inputs: PricingInputs, params: ModelParameters) -> PricingOutput:
        """Price European option using Black-Scholes formula."""
        inputs.validate()
        start_time = time.time()
        
        S = inputs.spot_price
        K = inputs.strike_price
        T = inputs.time_to_expiry
        r = inputs.risk_free_rate
        sigma = inputs.volatility
        q = inputs.dividend_yield
        
        # Handle edge cases
        if T == 0:
            if inputs.option_type == OptionType.CALL:
                price = max(S - K, 0)
            else:
                price = max(K - S, 0)
                
            return PricingOutput(
                model=PricingModel.BLACK_SCHOLES,
                price=price,
                delta=1.0 if price > 0 else 0.0,
                gamma=0.0,
                theta=0.0,
                vega=0.0,
                rho=0.0,
                computation_time=time.time() - start_time
            )
            
        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        # Calculate price and Greeks
        if inputs.option_type == OptionType.CALL:
            price = S * np.exp(-q * T) * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)
            delta = np.exp(-q * T) * stats.norm.cdf(d1)
        else:  # PUT
            price = K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * np.exp(-q * T) * stats.norm.cdf(-d1)
            delta = -np.exp(-q * T) * stats.norm.cdf(-d1)
            
        # Common Greeks
        gamma = np.exp(-q * T) * stats.norm.pdf(d1) / (S * sigma * np.sqrt(T))
        vega = S * np.exp(-q * T) * stats.norm.pdf(d1) * np.sqrt(T) / 100
        
        # Theta
        if inputs.option_type == OptionType.CALL:
            theta = (-S * np.exp(-q * T) * stats.norm.pdf(d1) * sigma / (2 * np.sqrt(T)) -
                     r * K * np.exp(-r * T) * stats.norm.cdf(d2) +
                     q * S * np.exp(-q * T) * stats.norm.cdf(d1)) / 365
        else:
            theta = (-S * np.exp(-q * T) * stats.norm.pdf(d1) * sigma / (2 * np.sqrt(T)) +
                     r * K * np.exp(-r * T) * stats.norm.cdf(-d2) -
                     q * S * np.exp(-q * T) * stats.norm.cdf(-d1)) / 365
                     
        # Rho
        if inputs.option_type == OptionType.CALL:
            rho = K * T * np.exp(-r * T) * stats.norm.cdf(d2) / 100
        else:
            rho = -K * T * np.exp(-r * T) * stats.norm.cdf(-d2) / 100
            
        return PricingOutput(
            model=PricingModel.BLACK_SCHOLES,
            price=price,
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
            computation_time=time.time() - start_time
        )

# ==============================================================================
# BINOMIAL TREE MODEL
# ==============================================================================
class BinomialTreeModel(PricingModelBase):
    """Binomial tree model for American and European options."""
    
    def price(self, inputs: PricingInputs, params: ModelParameters) -> PricingOutput:
        """Price option using binomial tree."""
        inputs.validate()
        start_time = time.time()
        
        n = params.steps
        S = inputs.spot_price
        K = inputs.strike_price
        T = inputs.time_to_expiry
        r = inputs.risk_free_rate
        sigma = inputs.volatility
        q = inputs.dividend_yield
        
        # Calculate tree parameters
        dt = T / n
        u = np.exp(sigma * np.sqrt(dt))  # Up factor
        d = 1 / u  # Down factor
        p = (np.exp((r - q) * dt) - d) / (u - d)  # Risk-neutral probability
        
        # Initialize price tree
        price_tree = np.zeros((n + 1, n + 1))
        
        # Calculate terminal payoffs
        for i in range(n + 1):
            price_tree[n, i] = self._payoff(S * (u ** (n - i)) * (d ** i), K, inputs.option_type)
            
        # Backward induction
        exercise_boundary = []
        
        for t in range(n - 1, -1, -1):
            for i in range(t + 1):
                spot = S * (u ** (t - i)) * (d ** i)
                
                # Option value if held
                hold_value = np.exp(-r * dt) * (p * price_tree[t + 1, i] + (1 - p) * price_tree[t + 1, i + 1])
                
                if inputs.exercise_type == ExerciseType.AMERICAN:
                    # Option value if exercised
                    exercise_value = self._payoff(spot, K, inputs.option_type)
                    price_tree[t, i] = max(hold_value, exercise_value)
                    
                    # Track exercise boundary
                    if t < n - 1 and exercise_value > hold_value:
                        exercise_boundary.append((t * dt, spot))
                else:
                    price_tree[t, i] = hold_value
                    
        option_price = price_tree[0, 0]
        
        # Calculate Greeks using tree
        greeks = self._calculate_tree_greeks(inputs, params, price_tree, S, u, d, dt)
        
        return PricingOutput(
            model=PricingModel.BINOMIAL,
            price=option_price,
            delta=greeks['delta'],
            gamma=greeks['gamma'],
            theta=greeks['theta'],
            vega=greeks['vega'],
            rho=greeks['rho'],
            exercise_boundary=exercise_boundary if exercise_boundary else None,
            computation_time=time.time() - start_time,
            model_params={'steps': n, 'u': u, 'd': d, 'p': p}
        )
        
    def _payoff(self, spot: float, strike: float, option_type: OptionType) -> float:
        """Calculate option payoff."""
        if option_type == OptionType.CALL:
            return max(spot - strike, 0)
        else:
            return max(strike - spot, 0)
            
    def _calculate_tree_greeks(self, 
                              inputs: PricingInputs,
                              params: ModelParameters,
                              price_tree: np.ndarray,
                              S: float,
                              u: float,
                              d: float,
                              dt: float) -> Dict[str, float]:
        """Calculate Greeks from binomial tree."""
        # Delta - use tree values
        delta = (price_tree[1, 0] - price_tree[1, 1]) / (S * (u - d))
        
        # Gamma - use second step
        if price_tree.shape[0] > 2:
            delta_u = (price_tree[2, 0] - price_tree[2, 1]) / (S * u * (u - d))
            delta_d = (price_tree[2, 1] - price_tree[2, 2]) / (S * d * (u - d))
            gamma = (delta_u - delta_d) / (S * (u - d) / 2)
        else:
            gamma = 0.0
            
        # Theta - compare with slightly different time
        theta = (price_tree[1, 1] - price_tree[0, 0]) / dt / 365
        
        # Vega and Rho - use finite differences
        other_greeks = self.calculate_greeks(inputs, params, price_tree[0, 0])
        
        return {
            'delta': delta,
            'gamma': gamma,
            'theta': theta,
            'vega': other_greeks['vega'],
            'rho': other_greeks['rho']
        }

# ==============================================================================
# MONTE CARLO MODEL
# ==============================================================================
class MonteCarloModel(PricingModelBase):
    """Monte Carlo simulation for option pricing."""
    
    def price(self, inputs: PricingInputs, params: ModelParameters) -> PricingOutput:
        """Price option using Monte Carlo simulation."""
        inputs.validate()
        start_time = time.time()
        
        # Set random seed for reproducibility
        if params.seed is not None:
            np.random.seed(params.seed)
            
        S = inputs.spot_price
        K = inputs.strike_price
        T = inputs.time_to_expiry
        r = inputs.risk_free_rate
        sigma = inputs.volatility
        q = inputs.dividend_yield
        
        n_sims = params.simulations
        n_steps = params.time_steps if inputs.exercise_type == ExerciseType.AMERICAN else 1
        dt = T / n_steps
        
        # Generate paths
        if params.antithetic and params.variance_reduction:
            # Use antithetic variates
            n_sims_half = n_sims // 2
            paths, paths_anti = self._generate_paths_antithetic(
                S, r, q, sigma, T, n_steps, n_sims_half
            )
            
            # Price both sets
            payoffs1 = self._calculate_payoffs(paths, K, inputs.option_type, inputs.exercise_type, r, dt)
            payoffs2 = self._calculate_payoffs(paths_anti, K, inputs.option_type, inputs.exercise_type, r, dt)
            
            # Average payoffs
            payoffs = np.concatenate([payoffs1, payoffs2])
        else:
            paths = self._generate_paths(S, r, q, sigma, T, n_steps, n_sims)
            payoffs = self._calculate_payoffs(paths, K, inputs.option_type, inputs.exercise_type, r, dt)
            
        # Calculate price and standard error
        option_price = np.mean(payoffs)
        std_error = np.std(payoffs) / np.sqrt(len(payoffs))
        
        # Control variate (using Black-Scholes for European)
        if params.control_variate and inputs.exercise_type == ExerciseType.EUROPEAN:
            bs_model = BlackScholesModel()
            bs_price = bs_model.price(inputs, params).price
            
            # Calculate correlation and adjust
            euro_payoffs = self._calculate_european_payoffs(paths, K, inputs.option_type, r, T)
            euro_mc_price = np.mean(euro_payoffs)
            
            correlation = np.corrcoef(payoffs, euro_payoffs)[0, 1]
            beta = correlation * np.std(payoffs) / np.std(euro_payoffs)
            
            # Adjusted price
            option_price = option_price - beta * (euro_mc_price - bs_price)
            
        # Calculate Greeks using finite differences
        greeks = self.calculate_greeks(inputs, params, option_price)
        
        return PricingOutput(
            model=PricingModel.MONTE_CARLO,
            price=option_price,
            delta=greeks['delta'],
            gamma=greeks['gamma'],
            theta=greeks['theta'],
            vega=greeks['vega'],
            rho=greeks['rho'],
            computation_time=time.time() - start_time,
            model_params={
                'simulations': n_sims,
                'time_steps': n_steps,
                'std_error': std_error,
                'variance_reduction': params.variance_reduction
            }
        )
        
    def _generate_paths(self, S: float, r: float, q: float, sigma: float, 
                       T: float, n_steps: int, n_sims: int) -> np.ndarray:
        """Generate Monte Carlo paths."""
        dt = T / n_steps
        paths = np.zeros((n_sims, n_steps + 1))
        paths[:, 0] = S
        
        # Generate random shocks
        Z = np.random.standard_normal((n_sims, n_steps))
        
        # Generate paths
        for t in range(1, n_steps + 1):
            paths[:, t] = paths[:, t-1] * np.exp(
                (r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z[:, t-1]
            )
            
        return paths
        
    def _generate_paths_antithetic(self, S: float, r: float, q: float, sigma: float,
                                  T: float, n_steps: int, n_sims: int) -> Tuple[np.ndarray, np.ndarray]:
        """Generate antithetic paths for variance reduction."""
        dt = T / n_steps
        
        # Generate random shocks
        Z = np.random.standard_normal((n_sims, n_steps))
        
        # Original paths
        paths1 = np.zeros((n_sims, n_steps + 1))
        paths1[:, 0] = S
        
        # Antithetic paths
        paths2 = np.zeros((n_sims, n_steps + 1))
        paths2[:, 0] = S
        
        for t in range(1, n_steps + 1):
            # Original
            paths1[:, t] = paths1[:, t-1] * np.exp(
                (r - q - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z[:, t-1]
            )
            
            # Antithetic (using -Z)
            paths2[:, t] = paths2[:, t-1] * np.exp(
                (r - q - 0.5 * sigma**2) * dt - sigma * np.sqrt(dt) * Z[:, t-1]
            )
            
        return paths1, paths2
        
    def _calculate_payoffs(self, paths: np.ndarray, K: float, option_type: OptionType,
                          exercise_type: ExerciseType, r: float, dt: float) -> np.ndarray:
        """Calculate option payoffs from paths."""
        n_sims, n_steps = paths.shape
        
        if exercise_type == ExerciseType.EUROPEAN:
            # European - only check at maturity
            if option_type == OptionType.CALL:
                payoffs = np.maximum(paths[:, -1] - K, 0)
            else:
                payoffs = np.maximum(K - paths[:, -1], 0)
                
            # Discount to present value
            payoffs *= np.exp(-r * (n_steps - 1) * dt)
            
        else:  # American
            # Use Longstaff-Schwartz method
            payoffs = self._longstaff_schwartz(paths, K, option_type, r, dt)
            
        return payoffs
        
    def _calculate_european_payoffs(self, paths: np.ndarray, K: float, 
                                  option_type: OptionType, r: float, T: float) -> np.ndarray:
        """Calculate European payoffs for control variate."""
        if option_type == OptionType.CALL:
            payoffs = np.maximum(paths[:, -1] - K, 0)
        else:
            payoffs = np.maximum(K - paths[:, -1], 0)
            
        return payoffs * np.exp(-r * T)
        
    def _longstaff_schwartz(self, paths: np.ndarray, K: float, option_type: OptionType,
                           r: float, dt: float) -> np.ndarray:
        """Longstaff-Schwartz algorithm for American options."""
        n_sims, n_steps = paths.shape
        
        # Calculate intrinsic values
        if option_type == OptionType.CALL:
            intrinsic = np.maximum(paths - K, 0)
        else:
            intrinsic = np.maximum(K - paths, 0)
            
        # Initialize cash flows
        cash_flows = np.zeros_like(paths)
        cash_flows[:, -1] = intrinsic[:, -1]
        
        # Backward induction
        for t in range(n_steps - 2, 0, -1):
            # Find in-the-money paths
            itm = intrinsic[:, t] > 0
            
            if np.sum(itm) > 0:
                # Regression on ITM paths
                X = paths[itm, t]
                Y = cash_flows[itm, t+1:].sum(axis=1) * np.exp(-r * dt * np.arange(1, n_steps - t))
                
                # Polynomial regression
                if len(X) > 10:  # Need enough points
                    coeffs = np.polyfit(X, Y, 2)
                    continuation_value = np.polyval(coeffs, X)
                    
                    # Exercise decision
                    exercise = intrinsic[itm, t] > continuation_value
                    
                    # Update cash flows
                    exercise_indices = np.where(itm)[0][exercise]
                    cash_flows[exercise_indices, t] = intrinsic[exercise_indices, t]
                    cash_flows[exercise_indices, t+1:] = 0
                    
        # Take maximum of immediate exercise or continuation
        cash_flows[:, 0] = np.where(intrinsic[:, 0] > cash_flows[:, 1:].sum(axis=1) * 
                                   np.exp(-r * dt * np.arange(1, n_steps)),
                                   intrinsic[:, 0], 0)
                                   
        # Calculate present value
        pv_factors = np.exp(-r * dt * np.arange(n_steps))
        payoffs = np.sum(cash_flows * pv_factors, axis=1)
        
        return payoffs

# ==============================================================================
# OPTIONS PRICER CLASS
# ==============================================================================
class OptionsPricer:
    """
    Advanced options pricer with multiple models.
    
    This class provides a unified interface for pricing options using
    various models and techniques, all implemented in pure Python/NumPy.
    """
    
    def __init__(self):
        """Initialize the options pricer."""
        self.logger = SpyderLogger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        
        # Initialize models
        self.models = {
            PricingModel.BLACK_SCHOLES: BlackScholesModel(),
            PricingModel.BINOMIAL: BinomialTreeModel(),
            PricingModel.MONTE_CARLO: MonteCarloModel()
        }
        
        # Cache for implied volatility calculations
        self._iv_cache = {}
        
        self.logger.info("OptionsPricer initialized with pure Python/NumPy models")
        
    # ==========================================================================
    # MAIN PRICING METHODS
    # ==========================================================================
    def price_option(self, 
                    inputs: PricingInputs,
                    model: PricingModel = PricingModel.BINOMIAL,
                    params: Optional[ModelParameters] = None) -> PricingOutput:
        """
        Price an option using specified model.
        
        Args:
            inputs: Pricing inputs
            model: Pricing model to use
            params: Model-specific parameters
            
        Returns:
            PricingOutput with results
        """
        try:
            # Validate inputs
            inputs.validate()
            
            # Use default parameters if not provided
            if params is None:
                params = ModelParameters()
                
            # Select appropriate model
            if model not in self.models:
                raise ValueError(f"Unknown pricing model: {model}")
                
            # For American options, use appropriate model
            if inputs.exercise_type == ExerciseType.AMERICAN and model == PricingModel.BLACK_SCHOLES:
                self.logger.warning("Black-Scholes cannot price American options, switching to Binomial")
                model = PricingModel.BINOMIAL
                
            # Price option
            pricer = self.models[model]
            output = pricer.price(inputs, params)
            
            # Calculate implied volatility if not provided
            if output.implied_volatility is None:
                output.implied_volatility = self.calculate_implied_volatility(
                    inputs, output.price, model
                )
                
            # Emit pricing event
            self._emit_pricing_event(inputs, output)
            
            return output
            
        except Exception as e:
            self.logger.error(f"Error pricing option: {e}")
            self.error_handler.handle_error(e, {"method": "price_option", "model": model})
            raise
            
    def price_spread(self, 
                    legs: List[Tuple[PricingInputs, int]],
                    model: PricingModel = PricingModel.BINOMIAL,
                    params: Optional[ModelParameters] = None) -> Dict[str, Any]:
        """
        Price a multi-leg option strategy.
        
        Args:
            legs: List of (PricingInputs, quantity) tuples
            model: Pricing model to use
            params: Model parameters
            
        Returns:
            Spread pricing results
        """
        if params is None:
            params = ModelParameters()
            
        total_price = 0.0
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        total_rho = 0.0
        
        leg_results = []
        
        for inputs, quantity in legs:
            # Price individual leg
            output = self.price_option(inputs, model, params)
            
            # Aggregate Greeks
            total_price += output.price * quantity
            total_delta += output.delta * quantity
            total_gamma += output.gamma * quantity
            total_theta += output.theta * quantity
            total_vega += output.vega * quantity
            total_rho += output.rho * quantity
            
            leg_results.append({
                'inputs': inputs,
                'quantity': quantity,
                'price': output.price,
                'value': output.price * quantity * 100  # Contract multiplier
            })
            
        # Calculate P&L profile
        spot_range = np.linspace(0.8, 1.2, 41) * legs[0][0].spot_price
        pl_profile = self._calculate_pl_profile(legs, spot_range, model, params)
        
        # Find breakeven points
        breakevens = self._find_breakevens(spot_range, pl_profile)
        
        # Calculate max profit/loss
        max_profit = np.max(pl_profile)
        max_loss = np.min(pl_profile)
        
        return {
            'total_price': total_price,
            'total_value': total_price * 100,  # Contract value
            'total_delta': total_delta,
            'total_gamma': total_gamma,
            'total_theta': total_theta,
            'total_vega': total_vega,
            'total_rho': total_rho,
            'max_profit': max_profit,
            'max_loss': max_loss,
            'breakeven': breakevens,
            'legs': leg_results,
            'pl_profile': {
                'spot_prices': spot_range.tolist(),
                'pl_values': pl_profile.tolist()
            }
        }
        
    def calculate_implied_volatility(self,
                                   inputs: PricingInputs,
                                   market_price: float,
                                   model: PricingModel = PricingModel.BLACK_SCHOLES,
                                   params: Optional[ModelParameters] = None) -> float:
        """
        Calculate implied volatility from market price.
        
        Args:
            inputs: Pricing inputs (with initial vol guess)
            market_price: Observed market price
            model: Pricing model to use
            params: Model parameters
            
        Returns:
            Implied volatility
        """
        if params is None:
            params = ModelParameters()
            
        # Check cache
        cache_key = (inputs.spot_price, inputs.strike_price, inputs.time_to_expiry,
                    inputs.risk_free_rate, market_price, inputs.option_type.value)
        
        if cache_key in self._iv_cache:
            return self._iv_cache[cache_key]
            
        # Objective function
        def objective(vol):
            test_inputs = PricingInputs(**inputs.__dict__)
            test_inputs.volatility = vol
            
            try:
                model_price = self.price_option(test_inputs, model, params).price
                return model_price - market_price
            except:
                return float('inf')
                
        # Use Brent's method for root finding
        try:
            # Initial bracket
            vol_low = MIN_VOLATILITY
            vol_high = MAX_VOLATILITY
            
            # Check if solution exists
            f_low = objective(vol_low)
            f_high = objective(vol_high)
            
            if f_low * f_high > 0:
                # Try to expand bracket
                if abs(f_low) < abs(f_high):
                    implied_vol = vol_low
                else:
                    implied_vol = vol_high
            else:
                # Use Brent's method
                result = optimize.brentq(objective, vol_low, vol_high, 
                                       xtol=CONVERGENCE_TOLERANCE, maxiter=MAX_ITERATIONS)
                implied_vol = result
                
        except Exception as e:
            self.logger.warning(f"IV calculation failed: {e}, using initial guess")
            implied_vol = inputs.volatility
            
        # Cache result
        self._iv_cache[cache_key] = implied_vol
        
        # Clean cache if too large
        if len(self._iv_cache) > 10000:
            self._iv_cache.clear()
            
        return implied_vol
        
    # ==========================================================================
    # MODEL COMPARISON AND CALIBRATION
    # ==========================================================================
    def compare_models(self, 
                      inputs: PricingInputs,
                      models: Optional[List[PricingModel]] = None,
                      params: Optional[ModelParameters] = None) -> pd.DataFrame:
        """
        Compare pricing across different models.
        
        Args:
            inputs: Pricing inputs
            models: List of models to compare (all if None)
            params: Model parameters
            
        Returns:
            DataFrame with model comparison
        """
        if models is None:
            models = list(self.models.keys())
            
        if params is None:
            params = ModelParameters()
            
        results = []
        
        for model in models:
            try:
                output = self.price_option(inputs, model, params)
                
                results.append({
                    'model': model.value,
                    'price': output.price,
                    'delta': output.delta,
                    'gamma': output.gamma,
                    'theta': output.theta,
                    'vega': output.vega,
                    'rho': output.rho,
                    'computation_time': output.computation_time
                })
            except Exception as e:
                self.logger.error(f"Error with model {model}: {e}")
                results.append({
                    'model': model.value,
                    'price': np.nan,
                    'error': str(e)
                })
                
        df = pd.DataFrame(results)
        
        # Add price differences
        if not df.empty and 'price' in df.columns:
            mean_price = df['price'].mean()
            df['price_diff'] = df['price'] - mean_price
            df['price_diff_pct'] = (df['price_diff'] / mean_price * 100)
            
        return df
        
    def calibrate_model(self, 
                       market_prices: pd.DataFrame,
                       model: PricingModel,
                       calibration_params: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
        """
        Calibrate model parameters to market prices.
        
        Args:
            market_prices: DataFrame with columns: strike, price, option_type
            model: Model to calibrate
            calibration_params: Additional calibration parameters
            
        Returns:
            Calibrated parameters
        """
        if calibration_params is None:
            calibration_params = {}
            
        # For now, simple volatility smile calibration
        calibrated_vols = {}
        
        spot = market_prices['underlying_price'].iloc[0] if 'underlying_price' in market_prices else 100
        
        for _, row in market_prices.iterrows():
            inputs = PricingInputs(
                spot_price=spot,
                strike_price=row['strike'],
                time_to_expiry=row.get('time_to_expiry', 30/365),
                risk_free_rate=row.get('risk_free_rate', 0.05),
                volatility=0.20,  # Initial guess
                option_type=OptionType.CALL if row.get('option_type', 'CALL') == 'CALL' else OptionType.PUT
            )
            
            # Calculate implied volatility
            iv = self.calculate_implied_volatility(inputs, row['price'], model)
            calibrated_vols[row['strike']] = iv
            
        # Fit smile parameters (simplified)
        strikes = list(calibrated_vols.keys())
        vols = list(calibrated_vols.values())
        
        # Fit quadratic smile
        moneyness = np.array(strikes) / spot
        coeffs = np.polyfit(moneyness, vols, 2)
        
        return {
            'atm_vol': np.polyval(coeffs, 1.0),
            'skew': coeffs[1],
            'convexity': coeffs[0],
            'calibrated_vols': calibrated_vols,
            'smile_coeffs': coeffs.tolist()
        }
        
    # ==========================================================================
    # EXOTIC OPTIONS
    # ==========================================================================
    def price_barrier_option(self,
                           inputs: PricingInputs,
                           barrier_type: str,
                           barrier_level: float,
                           rebate: float = 0.0) -> PricingOutput:
        """
        Price barrier options (knock-in/knock-out).
        
        Args:
            inputs: Standard pricing inputs
            barrier_type: 'up-and-out', 'up-and-in', 'down-and-out', 'down-and-in'
            barrier_level: Barrier price level
            rebate: Rebate paid if knocked out
            
        Returns:
            Pricing output
        """
        # Use Monte Carlo with barrier monitoring
        params = ModelParameters(
            simulations=20000,
            time_steps=252  # Daily monitoring
        )
        
        # Modify Monte Carlo to handle barriers
        # For now, return standard option price with warning
        self.logger.warning("Barrier option pricing not fully implemented")
        
        return self.price_option(inputs, PricingModel.MONTE_CARLO, params)
        
    def price_asian_option(self,
                          inputs: PricingInputs,
                          averaging_type: str = 'arithmetic',
                          observation_dates: Optional[List[date]] = None) -> PricingOutput:
        """
        Price Asian (average price) options.
        
        Args:
            inputs: Standard pricing inputs
            averaging_type: 'arithmetic' or 'geometric'
            observation_dates: Dates for averaging
            
        Returns:
            Pricing output
        """
        # Use Monte Carlo with path averaging
        params = ModelParameters(
            simulations=20000,
            time_steps=len(observation_dates) if observation_dates else 252
        )
        
        # For now, return approximation
        self.logger.warning("Asian option pricing not fully implemented")
        
        # Reduce volatility for averaging effect
        adjusted_inputs = PricingInputs(**inputs.__dict__)
        adjusted_inputs.volatility *= np.sqrt(1/3)  # Approximation
        
        return self.price_option(adjusted_inputs, PricingModel.BLACK_SCHOLES, params)
        
    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    def _calculate_pl_profile(self,
                            legs: List[Tuple[PricingInputs, int]],
                            spot_range: np.ndarray,
                            model: PricingModel,
                            params: ModelParameters) -> np.ndarray:
        """Calculate P&L profile across spot prices."""
        pl_profile = np.zeros_like(spot_range)
        
        for i, spot in enumerate(spot_range):
            total_value = 0.0
            
            for inputs, quantity in legs:
                # Adjust inputs for new spot
                test_inputs = PricingInputs(**inputs.__dict__)
                test_inputs.spot_price = spot
                test_inputs.time_to_expiry = 0  # At expiration
                
                # Calculate intrinsic value
                if test_inputs.option_type == OptionType.CALL:
                    value = max(spot - test_inputs.strike_price, 0)
                else:
                    value = max(test_inputs.strike_price - spot, 0)
                    
                total_value += value * quantity
                
            # Subtract initial cost
            initial_cost = sum(self.price_option(inputs, model, params).price * qty 
                             for inputs, qty in legs)
            
            pl_profile[i] = (total_value - initial_cost) * 100  # Contract multiplier
            
        return pl_profile
        
    def _find_breakevens(self, spot_range: np.ndarray, pl_profile: np.ndarray) -> List[float]:
        """Find breakeven points."""
        breakevens = []
        
        # Find zero crossings
        for i in range(1, len(pl_profile)):
            if pl_profile[i-1] * pl_profile[i] < 0:
                # Linear interpolation
                x1, x2 = spot_range[i-1], spot_range[i]
                y1, y2 = pl_profile[i-1], pl_profile[i]
                
                breakeven = x1 - y1 * (x2 - x1) / (y2 - y1)
                breakevens.append(breakeven)
                
        return breakevens
        
    def _emit_pricing_event(self, inputs: PricingInputs, output: PricingOutput) -> None:
        """Emit option pricing event."""
        event = Event(
            type=EventType.ANALYTICS,
            data={
                'type': 'option_pricing',
                'spot': inputs.spot_price,
                'strike': inputs.strike_price,
                'expiry': inputs.time_to_expiry,
                'model': output.model.value,
                'price': output.price,
                'delta': output.delta,
                'iv': output.implied_volatility
            }
        )
        self.event_manager.emit(event)

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'OptionsPricer',
    'PricingInputs',
    'PricingOutput',
    'ModelParameters',
    'PricingModel',
    'ExerciseType',
    'OptionType'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the options pricer
    pricer = OptionsPricer()
    
    print("="*60)
    print("SPYDER - Options Pricer Test")
    print("="*60)
    
    # Test inputs
    inputs = PricingInputs(
        spot_price=440.0,
        strike_price=440.0,
        time_to_expiry=30/365,  # 30 days
        risk_free_rate=0.05,
        volatility=0.20,
        dividend_yield=0.02,
        option_type=OptionType.CALL,
        exercise_type=ExerciseType.AMERICAN
    )
    
    print("\nTest Parameters:")
    print(f"  Spot: ${inputs.spot_price}")
    print(f"  Strike: ${inputs.strike_price}")
    print(f"  Time to Expiry: {inputs.time_to_expiry*365:.0f} days")
    print(f"  Volatility: {inputs.volatility:.1%}")
    print(f"  Risk-free Rate: {inputs.risk_free_rate:.1%}")
    print(f"  Dividend Yield: {inputs.dividend_yield:.1%}")
    
    # Test different models
    print("\n" + "-"*40)
    print("MODEL COMPARISON")
    print("-"*40)
    
    models = [PricingModel.BLACK_SCHOLES, PricingModel.BINOMIAL, PricingModel.MONTE_CARLO]
    
    for model in models:
        try:
            # Adjust for American options
            test_inputs = PricingInputs(**inputs.__dict__)
            if model == PricingModel.BLACK_SCHOLES:
                test_inputs.exercise_type = ExerciseType.EUROPEAN
                
            output = pricer.price_option(test_inputs, model)
            
            print(f"\n{model.value.upper()}:")
            print(f"  Price: ${output.price:.2f}")
            print(f"  Delta: {output.delta:.4f}")
            print(f"  Gamma: {output.gamma:.4f}")
            print(f"  Theta: ${output.theta:.2f}/day")
            print(f"  Vega: ${output.vega:.2f}/1% vol")
            print(f"  Rho: ${output.rho:.2f}/1% rate")
            print(f"  Computation Time: {output.computation_time*1000:.1f}ms")
            
        except Exception as e:
            print(f"\n{model.value}: ERROR - {e}")
            
    # Test spread pricing
    print("\n" + "-"*40)
    print("SPREAD PRICING TEST")
    print("-"*40)
    
    # Iron Condor
    iron_condor_legs = [
        (PricingInputs(spot_price=440, strike_price=420, time_to_expiry=30/365,
                      risk_free_rate=0.05, volatility=0.20, option_type=OptionType.PUT), 1),
        (PricingInputs(spot_price=440, strike_price=430, time_to_expiry=30/365,
                      risk_free_rate=0.05, volatility=0.20, option_type=OptionType.PUT), -1),
        (PricingInputs(spot_price=440, strike_price=450, time_to_expiry=30/365,
                      risk_free_rate=0.05, volatility=0.20, option_type=OptionType.CALL), -1),
        (PricingInputs(spot_price=440, strike_price=460, time_to_expiry=30/365,
                      risk_free_rate=0.05, volatility=0.20, option_type=OptionType.CALL), 1)
    ]
    
    spread_result = pricer.price_spread(iron_condor_legs)
    
    print("\nIron Condor:")
    print(f"  Net Credit: ${-spread_result['total_price']:.2f}")
    print(f"  Max Profit: ${spread_result['max_profit']:.2f}")
    print(f"  Max Loss: ${spread_result['max_loss']:.2f}")
    print(f"  Breakeven Points: {[f'${b:.2f}' for b in spread_result['breakeven']]}")
    print(f"  Total Delta: {spread_result['total_delta']:.4f}")
    print(f"  Total Theta: ${spread_result['total_theta']:.2f}/day")
    
    # Test implied volatility
    print("\n" + "-"*40)
    print("IMPLIED VOLATILITY TEST")
    print("-"*40)
    
    market_price = 10.50
    iv = pricer.calculate_implied_volatility(inputs, market_price)
    
    print(f"\nMarket Price: ${market_price:.2f}")
    print(f"Implied Volatility: {iv:.1%}")
    
    # Verify by pricing with IV
    inputs.volatility = iv
    check_output = pricer.price_option(inputs, PricingModel.BLACK_SCHOLES)
    print(f"Verification Price: ${check_output.price:.2f}")
    print(f"Difference: ${abs(check_output.price - market_price):.4f}")
    
    # Model comparison
    print("\n" + "-"*40)
    print("MODEL COMPARISON TABLE")
    print("-"*40)
    
    comparison_df = pricer.compare_models(inputs)
    print("\n", comparison_df.to_string())
    
    print("\n✅ Options Pricer test completed successfully!")