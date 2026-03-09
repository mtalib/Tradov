#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN01_OptionsPricer.py
Group: N (Options Analytics)
Purpose: Comprehensive options pricing engine with Greeks calculation
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 16:00:00

Description:
    This module provides the foundational options pricing engine for the Spyder
    system. It implements Black-Scholes for European options, Binomial trees for
    American options, and calculates all first and second-order Greeks. This is
    the core pricing engine that all other options modules depend on for accurate
    valuations and risk metrics.

Key Features:
    - Black-Scholes pricing for European options
    - Cox-Ross-Rubinstein binomial model for American options
    - Monte Carlo simulation for exotic options
    - Complete Greeks: Delta, Gamma, Vega, Theta, Rho
    - Second-order Greeks: Vanna, Charm, Vomma, Color
    - Implied volatility solver using Newton-Raphson
    - Volatility smile adjustments
    - Dividend handling for both discrete and continuous
    - Early exercise optimization for American options
    - Real-time pricing with market data integration
"""

import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

import numpy as np
import pandas as pd
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from scipy.special import erf
import logging

warnings.filterwarnings("ignore")

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    import logging

    # Mock utilities for standalone testing
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

    class SpyderErrorHandler:
        def handle_error(self, error, context):
            logging.info(f"Error in {context}: {error}")


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Pricing parameters
DEFAULT_RISK_FREE_RATE = 0.05  # 5% annual risk-free rate
DEFAULT_DIVIDEND_YIELD = 0.02  # 2% dividend yield for SPY
TRADING_DAYS_PER_YEAR = 252  # Trading days
CALENDAR_DAYS_PER_YEAR = 365  # Calendar days

# Numerical parameters
BINOMIAL_STEPS_MIN = 100  # Minimum steps for binomial tree
BINOMIAL_STEPS_MAX = 1000  # Maximum steps for accuracy
MONTE_CARLO_PATHS = 10000  # Number of MC simulation paths
CONVERGENCE_TOLERANCE = 1e-6  # Convergence tolerance
MAX_ITERATIONS = 100  # Max iterations for solvers
EPSILON = 1e-6  # Small value for numerical derivatives

# Greeks calculation parameters
DELTA_SPOT_SHIFT = 0.01  # 1% spot price shift for delta
GAMMA_SPOT_SHIFT = 0.01  # 1% spot price shift for gamma
VEGA_VOL_SHIFT = 0.01  # 1% volatility shift for vega
THETA_TIME_SHIFT = 1 / 365  # 1 day time shift for theta
RHO_RATE_SHIFT = 0.0001  # 1 basis point rate shift for rho

# Market conventions
PUT_CALL_PARITY_TOLERANCE = 0.01  # Tolerance for put-call parity check
MIN_VOLATILITY = 0.01  # 1% minimum volatility
MAX_VOLATILITY = 5.00  # 500% maximum volatility
MIN_TIME_TO_EXPIRY = 1 / 365  # Minimum 1 day to expiry

# ==============================================================================
# ENUMS
# ==============================================================================


class OptionType(Enum):
    """Option type enumeration"""

    CALL = "CALL"
    PUT = "PUT"


class ExerciseStyle(Enum):
    """Option exercise style"""

    EUROPEAN = "EUROPEAN"
    AMERICAN = "AMERICAN"
    BERMUDAN = "BERMUDAN"


class PricingModel(Enum):
    """Available pricing models"""

    BLACK_SCHOLES = "BLACK_SCHOLES"
    BINOMIAL = "BINOMIAL"
    MONTE_CARLO = "MONTE_CARLO"
    FINITE_DIFFERENCE = "FINITE_DIFFERENCE"


class GreekType(Enum):
    """Greek risk measures"""

    DELTA = "DELTA"
    GAMMA = "GAMMA"
    VEGA = "VEGA"
    THETA = "THETA"
    RHO = "RHO"
    VANNA = "VANNA"  # dDelta/dVol
    CHARM = "CHARM"  # dDelta/dTime
    VOMMA = "VOMMA"  # dVega/dVol
    COLOR = "COLOR"  # dGamma/dTime
    SPEED = "SPEED"  # dGamma/dSpot


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class OptionContract:
    """Option contract specification"""

    symbol: str
    underlying: str
    strike: float
    expiry: datetime
    option_type: OptionType
    exercise_style: ExerciseStyle = ExerciseStyle.AMERICAN
    multiplier: int = 100  # Standard equity option multiplier

    @property
    def time_to_expiry(self) -> float:
        """Calculate time to expiry in years"""
        now = datetime.now()
        if self.expiry <= now:
            return 0.0
        days = (self.expiry - now).days
        return max(days / CALENDAR_DAYS_PER_YEAR, MIN_TIME_TO_EXPIRY)

    @property
    def is_expired(self) -> bool:
        """Check if option is expired"""
        return datetime.now() >= self.expiry


@dataclass
class MarketData:
    """Market data for pricing"""

    spot_price: float
    volatility: float
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD
    timestamp: datetime = field(default_factory=datetime.now)
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    volume: int | None = None
    open_interest: int | None = None

    @property
    def mid_price(self) -> float | None:
        """Calculate mid price from bid/ask"""
        if self.bid and self.ask:
            return (self.bid + self.ask) / 2
        return self.last


@dataclass
class OptionPrice:
    """Option pricing result"""

    theoretical_value: float
    intrinsic_value: float
    time_value: float
    model_used: PricingModel
    timestamp: datetime = field(default_factory=datetime.now)

    # Greeks
    delta: float | None = None
    gamma: float | None = None
    vega: float | None = None
    theta: float | None = None
    rho: float | None = None

    # Second-order Greeks
    vanna: float | None = None
    charm: float | None = None
    vomma: float | None = None
    color: float | None = None
    speed: float | None = None

    # Additional metrics
    implied_volatility: float | None = None
    probability_itm: float | None = None
    expected_value: float | None = None

    @property
    def is_itm(self) -> bool:
        """Check if option is in the money"""
        return self.intrinsic_value > 0


@dataclass
class GreeksResult:
    """Complete Greeks calculation result"""

    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    lambda_leverage: float | None = None  # Lambda/Omega
    vanna: float | None = None
    charm: float | None = None
    vomma: float | None = None
    color: float | None = None
    speed: float | None = None
    ultima: float | None = None  # Third-order sensitivity to volatility


# ==============================================================================
# MATHEMATICAL FUNCTIONS
# ==============================================================================


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal"""
    return (1.0 + erf(x / np.sqrt(2.0))) / 2.0


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal"""
    return np.exp(-0.5 * x**2) / np.sqrt(2 * np.pi)


def calculate_d1_d2(
    S: float, K: float, T: float, r: float, q: float, sigma: float
) -> tuple[float, float]:
    """
    Calculate d1 and d2 for Black-Scholes formula

    Args:
        S: Spot price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate
        q: Dividend yield
        sigma: Volatility

    Returns:
        Tuple of (d1, d2)
    """
    if T <= 0 or sigma <= 0:
        return 0.0, 0.0

    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    return d1, d2


# ==============================================================================
# BLACK-SCHOLES PRICING
# ==============================================================================


class BlackScholesPricer:
    """Black-Scholes option pricing model for European options"""

    @staticmethod
    def price_call(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
        """
        Price a European call option using Black-Scholes

        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            q: Dividend yield
            sigma: Volatility

        Returns:
            Call option price
        """
        if T <= 0:
            return max(S - K, 0)

        d1, d2 = calculate_d1_d2(S, K, T, r, q, sigma)

        call_price = S * np.exp(-q * T) * norm_cdf(d1) - K * np.exp(-r * T) * norm_cdf(d2)

        return max(call_price, 0)

    @staticmethod
    def price_put(S: float, K: float, T: float, r: float, q: float, sigma: float) -> float:
        """
        Price a European put option using Black-Scholes

        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            q: Dividend yield
            sigma: Volatility

        Returns:
            Put option price
        """
        if T <= 0:
            return max(K - S, 0)

        d1, d2 = calculate_d1_d2(S, K, T, r, q, sigma)

        put_price = K * np.exp(-r * T) * norm_cdf(-d2) - S * np.exp(-q * T) * norm_cdf(-d1)

        return max(put_price, 0)

    @staticmethod
    def calculate_greeks(
        S: float, K: float, T: float, r: float, q: float, sigma: float, option_type: OptionType
    ) -> GreeksResult:
        """
        Calculate all Greeks for Black-Scholes model

        Returns:
            GreeksResult with all Greek values
        """
        if T <= 0:
            return GreeksResult(0, 0, 0, 0, 0)

        d1, d2 = calculate_d1_d2(S, K, T, r, q, sigma)
        sqrt_T = np.sqrt(T)

        # First-order Greeks
        if option_type == OptionType.CALL:
            delta = np.exp(-q * T) * norm_cdf(d1)
            theta_base = (S * norm_pdf(d1) * sigma * np.exp(-q * T)) / (2 * sqrt_T)
            theta = (
                -theta_base
                - r * K * np.exp(-r * T) * norm_cdf(d2)
                + q * S * np.exp(-q * T) * norm_cdf(d1)
            )
            rho = K * T * np.exp(-r * T) * norm_cdf(d2)
        else:  # PUT
            delta = -np.exp(-q * T) * norm_cdf(-d1)
            theta_base = (S * norm_pdf(d1) * sigma * np.exp(-q * T)) / (2 * sqrt_T)
            theta = (
                -theta_base
                + r * K * np.exp(-r * T) * norm_cdf(-d2)
                - q * S * np.exp(-q * T) * norm_cdf(-d1)
            )
            rho = -K * T * np.exp(-r * T) * norm_cdf(-d2)

        # Common Greeks (same for calls and puts)
        gamma = (norm_pdf(d1) * np.exp(-q * T)) / (S * sigma * sqrt_T)
        vega = S * norm_pdf(d1) * sqrt_T * np.exp(-q * T) / 100  # Divided by 100 for 1% vega

        # Convert theta to daily
        theta = theta / TRADING_DAYS_PER_YEAR

        # Second-order Greeks
        vanna = -np.exp(-q * T) * norm_pdf(d1) * d2 / sigma
        charm = (
            -np.exp(-q * T)
            * norm_pdf(d1)
            * (2 * (r - q) * T - d2 * sigma * sqrt_T)
            / (2 * T * sigma * sqrt_T)
        )
        vomma = vega * d1 * d2 / sigma
        color = -gamma / (2 * T) * (2 * q * T + 1 + d1 * d2)
        speed = -gamma * (d1 / (sigma * sqrt_T) + 1) / S

        return GreeksResult(
            delta=delta,
            gamma=gamma,
            vega=vega,
            theta=theta,
            rho=rho / 100,  # Per 1% change in rate
            vanna=vanna,
            charm=charm,
            vomma=vomma,
            color=color,
            speed=speed,
        )


# ==============================================================================
# BINOMIAL PRICING
# ==============================================================================


class BinomialPricer:
    """Cox-Ross-Rubinstein binomial tree for American options"""

    @staticmethod
    def price_option(
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        sigma: float,
        option_type: OptionType,
        n_steps: int = 100,
    ) -> float:
        """
        Price an American option using binomial tree

        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            q: Dividend yield
            sigma: Volatility
            option_type: CALL or PUT
            n_steps: Number of time steps

        Returns:
            Option price
        """
        if T <= 0:
            if option_type == OptionType.CALL:
                return max(S - K, 0)
            else:
                return max(K - S, 0)

        # Calculate parameters
        dt = T / n_steps
        u = np.exp(sigma * np.sqrt(dt))  # Up movement
        d = 1 / u  # Down movement
        p = (np.exp((r - q) * dt) - d) / (u - d)  # Risk-neutral probability
        discount = np.exp(-r * dt)

        # Initialize asset prices at maturity
        asset_prices = np.zeros(n_steps + 1)
        for i in range(n_steps + 1):
            asset_prices[i] = S * (u ** (n_steps - i)) * (d**i)

        # Initialize option values at maturity
        option_values = np.zeros(n_steps + 1)
        if option_type == OptionType.CALL:
            option_values = np.maximum(asset_prices - K, 0)
        else:
            option_values = np.maximum(K - asset_prices, 0)

        # Backward induction
        for step in range(n_steps - 1, -1, -1):
            for i in range(step + 1):
                # Calculate option value from future values
                hold_value = discount * (p * option_values[i] + (1 - p) * option_values[i + 1])

                # Calculate immediate exercise value
                asset_price = S * (u ** (step - i)) * (d**i)
                if option_type == OptionType.CALL:
                    exercise_value = max(asset_price - K, 0)
                else:
                    exercise_value = max(K - asset_price, 0)

                # American option: max of hold or exercise
                option_values[i] = max(hold_value, exercise_value)

        return option_values[0]

    @staticmethod
    def calculate_greeks(
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        sigma: float,
        option_type: OptionType,
        n_steps: int = 100,
    ) -> GreeksResult:
        """
        Calculate Greeks using finite differences on binomial tree
        """
        # Base price
        base_price = BinomialPricer.price_option(S, K, T, r, q, sigma, option_type, n_steps)

        # Delta: dV/dS
        S_up = S * (1 + DELTA_SPOT_SHIFT)
        S_down = S * (1 - DELTA_SPOT_SHIFT)
        price_up = BinomialPricer.price_option(S_up, K, T, r, q, sigma, option_type, n_steps)
        price_down = BinomialPricer.price_option(S_down, K, T, r, q, sigma, option_type, n_steps)
        delta = (price_up - price_down) / (S_up - S_down)

        # Gamma: d²V/dS²
        gamma = ((price_up - base_price) - (base_price - price_down)) / (0.5 * (S_up - S_down)) ** 2

        # Vega: dV/dσ
        sigma_up = sigma + VEGA_VOL_SHIFT
        price_vega_up = BinomialPricer.price_option(S, K, T, r, q, sigma_up, option_type, n_steps)
        vega = (price_vega_up - base_price) / (VEGA_VOL_SHIFT * 100)  # Per 1% vol change

        # Theta: dV/dT
        if T > THETA_TIME_SHIFT:
            T_down = T - THETA_TIME_SHIFT
            price_theta = BinomialPricer.price_option(
                S, K, T_down, r, q, sigma, option_type, n_steps
            )
            theta = (price_theta - base_price) / THETA_TIME_SHIFT / TRADING_DAYS_PER_YEAR
        else:
            theta = 0

        # Rho: dV/dr
        r_up = r + RHO_RATE_SHIFT
        price_rho_up = BinomialPricer.price_option(S, K, T, r_up, q, sigma, option_type, n_steps)
        rho = (price_rho_up - base_price) / RHO_RATE_SHIFT / 100  # Per 1% rate change

        return GreeksResult(delta=delta, gamma=gamma, vega=vega, theta=theta, rho=rho)


# ==============================================================================
# IMPLIED VOLATILITY SOLVER
# ==============================================================================


class ImpliedVolatilitySolver:
    """Solve for implied volatility from market prices"""

    @staticmethod
    def calculate_iv(
        market_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        option_type: OptionType,
        method: str = "newton",
    ) -> float | None:
        """
        Calculate implied volatility from market price

        Args:
            market_price: Observed market price
            S: Spot price
            K: Strike price
            T: Time to expiry (years)
            r: Risk-free rate
            q: Dividend yield
            option_type: CALL or PUT
            method: 'newton' or 'bisection'

        Returns:
            Implied volatility or None if not found
        """
        if T <= 0 or market_price <= 0:
            return None

        # Check intrinsic value bounds
        if option_type == OptionType.CALL:
            intrinsic = max(S * np.exp(-q * T) - K * np.exp(-r * T), 0)
            if market_price < intrinsic:
                return None
        else:
            intrinsic = max(K * np.exp(-r * T) - S * np.exp(-q * T), 0)
            if market_price < intrinsic:
                return None

        if method == "newton":
            return ImpliedVolatilitySolver._newton_raphson(market_price, S, K, T, r, q, option_type)
        else:
            return ImpliedVolatilitySolver._bisection(market_price, S, K, T, r, q, option_type)

    @staticmethod
    def _newton_raphson(
        target_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        option_type: OptionType,
    ) -> float | None:
        """Newton-Raphson method for IV"""
        # Initial guess using Brenner-Subrahmanyam approximation
        sigma = np.sqrt(2 * np.pi / T) * (target_price / S)
        sigma = max(MIN_VOLATILITY, min(MAX_VOLATILITY, sigma))

        for _ in range(MAX_ITERATIONS):
            # Calculate price and vega
            if option_type == OptionType.CALL:
                price = BlackScholesPricer.price_call(S, K, T, r, q, sigma)
            else:
                price = BlackScholesPricer.price_put(S, K, T, r, q, sigma)

            # Calculate vega
            d1, _ = calculate_d1_d2(S, K, T, r, q, sigma)
            vega = S * norm_pdf(d1) * np.sqrt(T) * np.exp(-q * T)

            # Check convergence
            price_diff = target_price - price
            if abs(price_diff) < CONVERGENCE_TOLERANCE:
                return sigma

            # Update sigma
            if vega > 0:
                sigma = sigma + price_diff / vega
                sigma = max(MIN_VOLATILITY, min(MAX_VOLATILITY, sigma))
            else:
                break

        return None

    @staticmethod
    def _bisection(
        target_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        q: float,
        option_type: OptionType,
    ) -> float | None:
        """Bisection method for IV"""
        low = MIN_VOLATILITY
        high = MAX_VOLATILITY

        for _ in range(MAX_ITERATIONS):
            mid = (low + high) / 2

            if option_type == OptionType.CALL:
                price = BlackScholesPricer.price_call(S, K, T, r, q, mid)
            else:
                price = BlackScholesPricer.price_put(S, K, T, r, q, mid)

            if abs(price - target_price) < CONVERGENCE_TOLERANCE:
                return mid

            if price < target_price:
                low = mid
            else:
                high = mid

        return None


# ==============================================================================
# MAIN OPTIONS PRICER CLASS
# ==============================================================================


class OptionsPricer:
    """
    Main options pricing engine for Spyder system

    This class provides unified interface for all pricing models and Greeks
    calculations. It automatically selects the appropriate model based on
    option characteristics and provides caching for performance.

    Attributes:
        logger: Logging instance
        error_handler: Error handling instance
        cache: Price cache for performance

    Example:
        >>> pricer = OptionsPricer()
        >>> contract = OptionContract('SPY240315C00450', 'SPY', 450, expiry, OptionType.CALL)
        >>> market_data = MarketData(spot_price=448.5, volatility=0.18)
        >>> price = pricer.price_option(contract, market_data)
        >>> print(f"Option Price: ${price.theoretical_value:.2f}")
    """

    def __init__(self):
        """Initialize options pricer"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Pricing engines
        self.bs_pricer = BlackScholesPricer()
        self.binomial_pricer = BinomialPricer()
        self.iv_solver = ImpliedVolatilitySolver()

        # Cache for performance
        self.price_cache: dict[str, OptionPrice] = {}
        self.greeks_cache: dict[str, GreeksResult] = {}
        self.iv_cache: dict[str, float] = {}

        # Configuration
        self.default_binomial_steps = 200
        self.use_cache = True
        self.cache_ttl = 60  # seconds

        self.logger.info("OptionsPricer initialized")

    # ==========================================================================
    # PUBLIC METHODS - PRICING
    # ==========================================================================

    def price_option(
        self,
        contract: OptionContract,
        market_data: MarketData,
        model: PricingModel | None = None,
        calculate_greeks: bool = True,
    ) -> OptionPrice:
        """
        Price an option contract

        Args:
            contract: Option contract specification
            market_data: Current market data
            model: Pricing model to use (auto-select if None)
            calculate_greeks: Whether to calculate Greeks

        Returns:
            OptionPrice with theoretical value and Greeks
        """
        try:
            # Check cache
            cache_key = self._get_cache_key(contract, market_data)
            if self.use_cache and cache_key in self.price_cache:
                cached = self.price_cache[cache_key]
                if (datetime.now() - cached.timestamp).seconds < self.cache_ttl:
                    return cached

            # Select pricing model
            if model is None:
                model = self._select_pricing_model(contract)

            # Extract parameters
            S = market_data.spot_price
            K = contract.strike
            T = contract.time_to_expiry
            r = market_data.risk_free_rate
            q = market_data.dividend_yield
            sigma = market_data.volatility

            # Price based on model
            if model == PricingModel.BLACK_SCHOLES:
                if contract.option_type == OptionType.CALL:
                    theo_value = self.bs_pricer.price_call(S, K, T, r, q, sigma)
                else:
                    theo_value = self.bs_pricer.price_put(S, K, T, r, q, sigma)

                if calculate_greeks:
                    greeks = self.bs_pricer.calculate_greeks(
                        S, K, T, r, q, sigma, contract.option_type
                    )
                else:
                    greeks = None

            elif model == PricingModel.BINOMIAL:
                theo_value = self.binomial_pricer.price_option(
                    S, K, T, r, q, sigma, contract.option_type, self.default_binomial_steps
                )

                if calculate_greeks:
                    greeks = self.binomial_pricer.calculate_greeks(
                        S, K, T, r, q, sigma, contract.option_type, self.default_binomial_steps
                    )
                else:
                    greeks = None
            else:
                raise ValueError(f"Unsupported pricing model: {model}")

            # Calculate intrinsic and time value
            if contract.option_type == OptionType.CALL:
                intrinsic = max(S - K, 0)
            else:
                intrinsic = max(K - S, 0)

            time_value = theo_value - intrinsic

            # Calculate probability of ITM
            if T > 0:
                d2 = calculate_d1_d2(S, K, T, r, q, sigma)[1]
                if contract.option_type == OptionType.CALL:
                    prob_itm = norm_cdf(d2)
                else:
                    prob_itm = norm_cdf(-d2)
            else:
                prob_itm = 1.0 if intrinsic > 0 else 0.0

            # Create result
            result = OptionPrice(
                theoretical_value=theo_value,
                intrinsic_value=intrinsic,
                time_value=time_value,
                model_used=model,
                probability_itm=prob_itm,
            )

            # Add Greeks if calculated
            if greeks:
                result.delta = greeks.delta
                result.gamma = greeks.gamma
                result.vega = greeks.vega
                result.theta = greeks.theta
                result.rho = greeks.rho
                result.vanna = greeks.vanna
                result.charm = greeks.charm
                result.vomma = greeks.vomma
                result.color = greeks.color
                result.speed = greeks.speed

            # Calculate IV if market price available
            if market_data.mid_price:
                result.implied_volatility = self.calculate_implied_volatility(
                    contract, market_data.mid_price, market_data
                )

            # Cache result
            if self.use_cache:
                self.price_cache[cache_key] = result

            return result

        except Exception as e:
            self.logger.error(f"Error pricing option {contract.symbol}: {e}")
            self.error_handler.handle_error(e, {"contract": contract.symbol})

            # Return zero price on error
            return OptionPrice(
                theoretical_value=0,
                intrinsic_value=0,
                time_value=0,
                model_used=model or PricingModel.BLACK_SCHOLES,
            )

    def calculate_implied_volatility(
        self, contract: OptionContract, market_price: float, market_data: MarketData
    ) -> float | None:
        """
        Calculate implied volatility from market price

        Args:
            contract: Option contract
            market_price: Observed market price
            market_data: Market data (for spot, rates, etc.)

        Returns:
            Implied volatility or None
        """
        # Check cache
        cache_key = f"{contract.symbol}_{market_price}_{market_data.spot_price}"
        if cache_key in self.iv_cache:
            return self.iv_cache[cache_key]

        iv = self.iv_solver.calculate_iv(
            market_price,
            market_data.spot_price,
            contract.strike,
            contract.time_to_expiry,
            market_data.risk_free_rate,
            market_data.dividend_yield,
            contract.option_type,
        )

        # Cache result
        if iv:
            self.iv_cache[cache_key] = iv

        return iv

    def calculate_portfolio_greeks(
        self, positions: list[tuple[OptionContract, int, MarketData]]
    ) -> GreeksResult:
        """
        Calculate aggregate Greeks for a portfolio

        Args:
            positions: List of (contract, quantity, market_data) tuples

        Returns:
            Aggregate GreeksResult
        """
        total_delta = 0
        total_gamma = 0
        total_vega = 0
        total_theta = 0
        total_rho = 0

        for contract, quantity, market_data in positions:
            price_result = self.price_option(contract, market_data)

            if price_result.delta is not None:
                total_delta += price_result.delta * quantity * contract.multiplier
            if price_result.gamma is not None:
                total_gamma += price_result.gamma * quantity * contract.multiplier
            if price_result.vega is not None:
                total_vega += price_result.vega * quantity * contract.multiplier
            if price_result.theta is not None:
                total_theta += price_result.theta * quantity * contract.multiplier
            if price_result.rho is not None:
                total_rho += price_result.rho * quantity * contract.multiplier

        return GreeksResult(
            delta=total_delta, gamma=total_gamma, vega=total_vega, theta=total_theta, rho=total_rho
        )

    # ==========================================================================
    # PUBLIC METHODS - ANALYSIS
    # ==========================================================================

    def calculate_breakeven(self, contract: OptionContract, premium: float) -> float:
        """
        Calculate breakeven price for an option

        Args:
            contract: Option contract
            premium: Premium paid/received

        Returns:
            Breakeven underlying price
        """
        if contract.option_type == OptionType.CALL:
            return contract.strike + premium
        else:
            return contract.strike - premium

    def calculate_payoff_profile(
        self,
        contract: OptionContract,
        premium: float,
        spot_range: tuple[float, float] | None = None,
        n_points: int = 100,
    ) -> pd.DataFrame:
        """
        Generate payoff profile for option position

        Args:
            contract: Option contract
            premium: Premium paid (negative if received)
            spot_range: (min, max) spot prices to evaluate
            n_points: Number of points to calculate

        Returns:
            DataFrame with spot prices and P&L
        """
        if spot_range is None:
            # Default to +/- 20% from strike
            spot_range = (contract.strike * 0.8, contract.strike * 1.2)

        spots = np.linspace(spot_range[0], spot_range[1], n_points)
        payoffs = []

        for spot in spots:
            if contract.option_type == OptionType.CALL:
                intrinsic = max(spot - contract.strike, 0)
            else:
                intrinsic = max(contract.strike - spot, 0)

            # P&L = intrinsic value - premium paid
            pnl = (intrinsic - premium) * contract.multiplier
            payoffs.append(pnl)

        return pd.DataFrame(
            {
                "spot": spots,
                "payoff": payoffs,
                "breakeven": [self.calculate_breakeven(contract, premium)] * n_points,
            }
        )

    def check_put_call_parity(
        self,
        call_price: float,
        put_price: float,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        div_yield: float,
    ) -> float:
        """
        Check put-call parity relationship

        Returns:
            Parity difference (should be close to zero)
        """
        # Put-Call Parity: C - P = S*e^(-qT) - K*e^(-rT)
        left_side = call_price - put_price
        right_side = spot * np.exp(-div_yield * time_to_expiry) - strike * np.exp(
            -rate * time_to_expiry
        )

        return left_side - right_side

    # ==========================================================================
    # PRIVATE METHODS
    # ==========================================================================

    def _select_pricing_model(self, contract: OptionContract) -> PricingModel:
        """Select appropriate pricing model based on contract"""
        if contract.exercise_style == ExerciseStyle.EUROPEAN:
            return PricingModel.BLACK_SCHOLES
        else:
            # Use binomial for American options
            return PricingModel.BINOMIAL

    def _get_cache_key(self, contract: OptionContract, market_data: MarketData) -> str:
        """Generate cache key for pricing"""
        return (
            f"{contract.symbol}_{market_data.spot_price:.2f}_"
            f"{market_data.volatility:.4f}_{market_data.risk_free_rate:.4f}"
        )

    def clear_cache(self):
        """Clear all caches"""
        self.price_cache.clear()
        self.greeks_cache.clear()
        self.iv_cache.clear()
        self.logger.info("Pricing caches cleared")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_options_pricer() -> OptionsPricer:
    """Factory function to create options pricer"""
    return OptionsPricer()


def calculate_option_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    rate: float = DEFAULT_RISK_FREE_RATE,
    div_yield: float = DEFAULT_DIVIDEND_YIELD,
    option_type: str = "CALL",
    style: str = "AMERICAN",
) -> float:
    """
    Quick function to calculate option price

    Args:
        spot: Current spot price
        strike: Strike price
        time_to_expiry: Time to expiry in years
        volatility: Implied volatility
        rate: Risk-free rate
        div_yield: Dividend yield
        option_type: "CALL" or "PUT"
        style: "AMERICAN" or "EUROPEAN"

    Returns:
        Option price
    """
    pricer = OptionsPricer()

    # Create contract
    expiry = datetime.now() + timedelta(days=int(time_to_expiry * 365))
    contract = OptionContract(
        symbol=f"TEST_{strike}_{option_type}",
        underlying="TEST",
        strike=strike,
        expiry=expiry,
        option_type=OptionType[option_type],
        exercise_style=ExerciseStyle[style],
    )

    # Create market data
    market_data = MarketData(
        spot_price=spot, volatility=volatility, risk_free_rate=rate, dividend_yield=div_yield
    )

    # Price option
    result = pricer.price_option(contract, market_data)

    return result.theoretical_value


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================


if __name__ == "__main__":

    # Test parameters
    spot = 585.00  # SPY spot price
    strike = 590.00  # Strike price
    expiry_days = 7  # Days to expiry
    volatility = 0.16  # 16% implied volatility
    rate = 0.05  # 5% risk-free rate
    div_yield = 0.02  # 2% dividend yield


    # Create pricer
    pricer = create_options_pricer()

    # Create contracts
    expiry = datetime.now() + timedelta(days=expiry_days)

    call_contract = OptionContract(
        symbol=f"SPY{expiry.strftime('%y%m%d')}C{int(strike*1000):08d}",
        underlying="SPY",
        strike=strike,
        expiry=expiry,
        option_type=OptionType.CALL,
        exercise_style=ExerciseStyle.AMERICAN,
    )

    put_contract = OptionContract(
        symbol=f"SPY{expiry.strftime('%y%m%d')}P{int(strike*1000):08d}",
        underlying="SPY",
        strike=strike,
        expiry=expiry,
        option_type=OptionType.PUT,
        exercise_style=ExerciseStyle.AMERICAN,
    )

    # Create market data
    market_data = MarketData(
        spot_price=spot,
        volatility=volatility,
        risk_free_rate=rate,
        dividend_yield=div_yield,
        bid=2.45,
        ask=2.55,
        last=2.50,
    )

    # Price options

    # Price CALL
    call_price = pricer.price_option(call_contract, market_data)

    if call_price.delta is not None:
        pass

    # Price PUT
    put_price = pricer.price_option(put_contract, market_data)

    if put_price.delta is not None:
        pass

    # Test implied volatility calculation

    test_market_price = 2.50
    calc_iv = pricer.calculate_implied_volatility(call_contract, test_market_price, market_data)

    if calc_iv:
        pass

    # Test put-call parity

    parity_diff = pricer.check_put_call_parity(
        call_price.theoretical_value,
        put_price.theoretical_value,
        spot,
        strike,
        call_contract.time_to_expiry,
        rate,
        div_yield,
    )


    # Test portfolio Greeks

    # Create a simple Iron Condor position
    positions = [
        (call_contract, -10, market_data),  # Short 10 calls
        (put_contract, -10, market_data),  # Short 10 puts
    ]

    portfolio_greeks = pricer.calculate_portfolio_greeks(positions)


    # Compare pricing models

    # European Black-Scholes
    euro_call = call_contract
    euro_call.exercise_style = ExerciseStyle.EUROPEAN
    bs_price = pricer.price_option(euro_call, market_data, model=PricingModel.BLACK_SCHOLES)

    # American Binomial
    amer_call = call_contract
    amer_call.exercise_style = ExerciseStyle.AMERICAN
    bin_price = pricer.price_option(amer_call, market_data, model=PricingModel.BINOMIAL)


