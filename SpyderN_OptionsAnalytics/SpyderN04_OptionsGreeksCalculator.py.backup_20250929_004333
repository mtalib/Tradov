#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN04_OptionsGreeksCalculator.py
Group: N (Options Analytics)
Purpose: Advanced Greeks calculations, scenarios, and portfolio risk metrics
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 20:00:00

Description:
    This module provides comprehensive Greeks calculations including second-order
    Greeks, scenario analysis, stress testing, and portfolio-level risk metrics.
    It goes beyond basic Greeks to provide advanced risk analytics, hedging
    recommendations, and real-time portfolio Greeks monitoring. Different from
    N11 which tracks Greeks flow, this module focuses on calculation and analysis.
"""

import json
import os
import sys
import threading
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
from scipy import stats
from scipy.optimize import minimize, minimize_scalar

from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

warnings.filterwarnings("ignore")

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))


# Import pricing engine if available
try:
    from SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import OptionsPricer

    PRICER_AVAILABLE = True
except ImportError:
    PRICER_AVAILABLE = False
    print("⚠️ OptionsPricer not available - using internal calculations")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Greeks calculation parameters
EPSILON = 0.01  # For finite difference calculations
SPOT_BUMP = 0.01  # 1% spot price bump
VOL_BUMP = 0.01  # 1% volatility bump
TIME_BUMP = 1 / 365  # 1 day time bump
RATE_BUMP = 0.0001  # 1 basis point rate bump

# Risk thresholds
MAX_PORTFOLIO_DELTA = 1000
MAX_PORTFOLIO_GAMMA = 100
MAX_PORTFOLIO_VEGA = 10000
MAX_PORTFOLIO_THETA = -5000

# Scenario parameters
SPOT_SCENARIOS = [-10, -5, -2, -1, 0, 1, 2, 5, 10]  # Percentage moves
VOL_SCENARIOS = [-30, -20, -10, 0, 10, 20, 30]  # Percentage vol changes
TIME_SCENARIOS = [0, 1, 2, 5, 10, 20]  # Days forward

# ==============================================================================
# ENUMS
# ==============================================================================


class GreekType(Enum):
    """Greek type enumeration"""

    # First-order Greeks
    DELTA = "Delta"
    GAMMA = "Gamma"
    THETA = "Theta"
    VEGA = "Vega"
    RHO = "Rho"

    # Second-order Greeks
    VANNA = "Vanna"  # ∂²V/∂S∂σ
    CHARM = "Charm"  # ∂²V/∂S∂t
    VOMMA = "Vomma"  # ∂²V/∂σ²
    VETA = "Veta"  # ∂²V/∂σ∂t
    COLOR = "Color"  # ∂³V/∂S²∂t
    SPEED = "Speed"  # ∂³V/∂S³
    ZOMMA = "Zomma"  # ∂³V/∂S²∂σ
    ULTIMA = "Ultima"  # ∂³V/∂σ³


class ScenarioType(Enum):
    """Scenario type enumeration"""

    SPOT_MOVE = "Spot Move"
    VOL_CHANGE = "Volatility Change"
    TIME_DECAY = "Time Decay"
    COMBINED = "Combined"
    STRESS_TEST = "Stress Test"


class HedgeType(Enum):
    """Hedge type enumeration"""

    DELTA_HEDGE = "Delta Hedge"
    GAMMA_HEDGE = "Gamma Hedge"
    VEGA_HEDGE = "Vega Hedge"
    DELTA_GAMMA = "Delta-Gamma Hedge"
    FULL_HEDGE = "Full Hedge"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class PositionGreeks:
    """Greeks for a single position"""

    symbol: str
    strike: float
    expiry: datetime
    option_type: str  # 'CALL' or 'PUT'
    quantity: int

    # First-order Greeks
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    # Second-order Greeks
    vanna: float = 0.0
    charm: float = 0.0
    vomma: float = 0.0
    veta: float = 0.0
    color: float = 0.0
    speed: float = 0.0
    zomma: float = 0.0
    ultima: float = 0.0

    # Position-level Greeks (quantity-adjusted)
    position_delta: float = 0.0
    position_gamma: float = 0.0
    position_theta: float = 0.0
    position_vega: float = 0.0
    position_rho: float = 0.0


@dataclass
class PortfolioGreeks:
    """Aggregated portfolio Greeks"""

    timestamp: datetime = field(default_factory=datetime.now)

    # Aggregated first-order Greeks
    total_delta: float = 0.0
    total_gamma: float = 0.0
    total_theta: float = 0.0
    total_vega: float = 0.0
    total_rho: float = 0.0

    # Aggregated second-order Greeks
    total_vanna: float = 0.0
    total_charm: float = 0.0
    total_vomma: float = 0.0
    total_veta: float = 0.0

    # Greeks by expiry
    greeks_by_expiry: Dict[datetime, Dict[str, float]] = field(default_factory=dict)

    # Greeks by strike
    greeks_by_strike: Dict[float, Dict[str, float]] = field(default_factory=dict)

    # Risk metrics
    delta_dollars: float = 0.0  # Dollar delta exposure
    gamma_dollars: float = 0.0  # Dollar gamma exposure
    theta_dollars: float = 0.0  # Daily theta decay in dollars
    vega_dollars: float = 0.0  # Vega exposure in dollars

    # Speed metrics
    gamma_speed: float = 0.0  # Rate of gamma change
    delta_decay: float = 0.0  # Delta decay rate


@dataclass
class ScenarioResult:
    """Result of scenario analysis"""

    scenario_type: ScenarioType
    parameters: Dict[str, Any]
    pnl: float
    new_delta: float
    new_gamma: float
    new_vega: float
    new_theta: float
    max_loss: float
    max_gain: float
    probability: float = 0.0


@dataclass
class HedgeRecommendation:
    """Hedging recommendation"""

    hedge_type: HedgeType
    current_exposure: Dict[str, float]
    target_exposure: Dict[str, float]
    hedge_trades: List[Dict[str, Any]]
    cost_estimate: float
    effectiveness: float  # 0-100%


# ==============================================================================
# OPTIONS GREEKS CALCULATOR CLASS
# ==============================================================================


class OptionsGreeksCalculator:
    """
    Advanced Greeks calculator with scenario analysis and portfolio risk metrics.

    Features:
        - First and second-order Greeks
        - Scenario analysis and stress testing
        - Portfolio Greeks aggregation
        - Real-time Greeks monitoring
        - Hedging recommendations
        - Greeks surfaces visualization
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize the Greeks Calculator

        Args:
            config: Configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.use_analytical = self.config.get("use_analytical", True)
        self.cache_results = self.config.get("cache_results", True)

        # Pricing engine
        self.pricer = OptionsPricer() if PRICER_AVAILABLE else None

        # Portfolio storage
        self.positions: List[PositionGreeks] = []
        self.portfolio_greeks = PortfolioGreeks()

        # Market data
        self.spot_prices: Dict[str, float] = {}
        self.volatilities: Dict[str, float] = {}
        self.risk_free_rate: float = 0.05

        # Cache
        self.cache: Dict[str, Any] = {}
        self.cache_timestamp: Dict[str, datetime] = {}

        # Threading
        self.lock = threading.Lock()

        # Monitoring
        self.monitoring_active = False
        self.monitoring_thread = None
        self.update_callbacks: List[Callable] = []

        self.logger.info("OptionsGreeksCalculator initialized")

    # ==========================================================================
    # FIRST-ORDER GREEKS
    # ==========================================================================

    def calculate_greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: float,
        option_type: str = "CALL",
        dividend_yield: float = 0.0,
    ) -> Dict[str, float]:
        """
        Calculate all Greeks for an option

        Args:
            spot: Current spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            risk_free_rate: Risk-free rate
            option_type: 'CALL' or 'PUT'
            dividend_yield: Dividend yield

        Returns:
            Dictionary of Greeks
        """
        # Use external pricer if available
        if self.pricer and self.use_analytical:
            greeks = self.pricer.calculate_greeks(
                spot,
                strike,
                time_to_expiry,
                volatility,
                risk_free_rate,
                option_type,
                dividend_yield,
            )
        else:
            # Internal Black-Scholes calculation
            greeks = self._calculate_bs_greeks(
                spot,
                strike,
                time_to_expiry,
                volatility,
                risk_free_rate,
                option_type,
                dividend_yield,
            )

        # Add second-order Greeks
        second_order = self.calculate_second_order_greeks(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )
        greeks.update(second_order)

        return greeks

    def _calculate_bs_greeks(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> Dict[str, float]:
        """
        Internal Black-Scholes Greeks calculation

        Args:
            S: Spot price
            K: Strike price
            T: Time to expiry
            sigma: Volatility
            r: Risk-free rate
            option_type: 'CALL' or 'PUT'
            q: Dividend yield

        Returns:
            Dictionary of first-order Greeks
        """
        # Handle edge cases
        if T <= 0:
            return {
                "delta": 1.0 if S > K and option_type == "CALL" else 0.0,
                "gamma": 0.0,
                "theta": 0.0,
                "vega": 0.0,
                "rho": 0.0,
            }

        # Calculate d1 and d2
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        # Standard normal CDF and PDF
        N = stats.norm.cdf
        n = stats.norm.pdf

        # Calculate Greeks
        if option_type == "CALL":
            delta = np.exp(-q * T) * N(d1)
            theta = (
                -S * n(d1) * sigma * np.exp(-q * T) / (2 * np.sqrt(T))
                - r * K * np.exp(-r * T) * N(d2)
                + q * S * np.exp(-q * T) * N(d1)
            )
            rho = K * T * np.exp(-r * T) * N(d2)
        else:  # PUT
            delta = -np.exp(-q * T) * N(-d1)
            theta = (
                -S * n(d1) * sigma * np.exp(-q * T) / (2 * np.sqrt(T))
                + r * K * np.exp(-r * T) * N(-d2)
                - q * S * np.exp(-q * T) * N(-d1)
            )
            rho = -K * T * np.exp(-r * T) * N(-d2)

        # Greeks same for both calls and puts
        gamma = n(d1) * np.exp(-q * T) / (S * sigma * np.sqrt(T))
        vega = S * n(d1) * np.exp(-q * T) * np.sqrt(T) / 100  # Divided by 100 for 1% change

        # Theta is per day
        theta = theta / 365

        return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}

    # ==========================================================================
    # SECOND-ORDER GREEKS
    # ==========================================================================

    def calculate_second_order_greeks(
        self,
        spot: float,
        strike: float,
        time_to_expiry: float,
        volatility: float,
        risk_free_rate: float,
        option_type: str,
        dividend_yield: float = 0.0,
    ) -> Dict[str, float]:
        """
        Calculate second-order Greeks using finite differences

        Args:
            spot: Current spot price
            strike: Strike price
            time_to_expiry: Time to expiry in years
            volatility: Implied volatility
            risk_free_rate: Risk-free rate
            option_type: 'CALL' or 'PUT'
            dividend_yield: Dividend yield

        Returns:
            Dictionary of second-order Greeks
        """
        # Use analytical formulas where available
        second_order = {}

        # Vanna (∂²V/∂S∂σ) - cross-sensitivity of delta to volatility
        second_order["vanna"] = self._calculate_vanna(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        # Charm (∂²V/∂S∂t) - delta decay
        second_order["charm"] = self._calculate_charm(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        # Vomma (∂²V/∂σ²) - vega convexity
        second_order["vomma"] = self._calculate_vomma(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        # Veta (∂²V/∂σ∂t) - vega decay
        second_order["veta"] = self._calculate_veta(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        # Color (∂³V/∂S²∂t) - gamma decay
        second_order["color"] = self._calculate_color(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        # Speed (∂³V/∂S³) - gamma sensitivity to spot
        second_order["speed"] = self._calculate_speed(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        # Zomma (∂³V/∂S²∂σ) - gamma sensitivity to volatility
        second_order["zomma"] = self._calculate_zomma(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        # Ultima (∂³V/∂σ³) - vomma sensitivity to volatility
        second_order["ultima"] = self._calculate_ultima(
            spot, strike, time_to_expiry, volatility, risk_free_rate, option_type, dividend_yield
        )

        return second_order

    def _calculate_vanna(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Vanna (∂²V/∂S∂σ)"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        vanna = -stats.norm.pdf(d1) * d2 / sigma
        return vanna

    def _calculate_charm(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Charm (∂²V/∂S∂t) - delta decay"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        n = stats.norm.pdf
        N = stats.norm.cdf

        if option_type == "CALL":
            charm = q * np.exp(-q * T) * N(d1) - np.exp(-q * T) * n(d1) * (
                2 * (r - q) * T - d2 * sigma * np.sqrt(T)
            ) / (2 * T * sigma * np.sqrt(T))
        else:
            charm = -q * np.exp(-q * T) * N(-d1) - np.exp(-q * T) * n(d1) * (
                2 * (r - q) * T - d2 * sigma * np.sqrt(T)
            ) / (2 * T * sigma * np.sqrt(T))

        return charm / 365  # Per day

    def _calculate_vomma(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Vomma (∂²V/∂σ²) - vega convexity"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        vega = S * stats.norm.pdf(d1) * np.exp(-q * T) * np.sqrt(T)
        vomma = vega * d1 * d2 / sigma

        return vomma / 100  # For 1% vol change

    def _calculate_veta(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Veta (∂²V/∂σ∂t) - vega decay"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        n = stats.norm.pdf

        veta = (
            S
            * np.exp(-q * T)
            * n(d1)
            * np.sqrt(T)
            * (q + ((r - q) * d1) / (sigma * np.sqrt(T)) - (1 + d1 * d2) / (2 * T))
        )

        return veta / 365 / 100  # Per day per 1% vol

    def _calculate_color(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Color (∂³V/∂S²∂t) - gamma decay"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        n = stats.norm.pdf

        color = (
            -np.exp(-q * T)
            * n(d1)
            / (2 * S * T * sigma * np.sqrt(T))
            * (
                2 * q * T
                + 1
                + (2 * (r - q) * T - d2 * sigma * np.sqrt(T)) * d1 / (sigma * np.sqrt(T))
            )
        )

        return color / 365  # Per day

    def _calculate_speed(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Speed (∂³V/∂S³) - gamma sensitivity"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        gamma = stats.norm.pdf(d1) * np.exp(-q * T) / (S * sigma * np.sqrt(T))

        speed = -gamma * (d1 / (sigma * np.sqrt(T)) + 1) / S

        return speed

    def _calculate_zomma(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Zomma (∂³V/∂S²∂σ) - gamma sensitivity to vol"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        gamma = stats.norm.pdf(d1) * np.exp(-q * T) / (S * sigma * np.sqrt(T))

        zomma = gamma * (d1 * d2 - 1) / sigma

        return zomma / 100  # For 1% vol change

    def _calculate_ultima(
        self, S: float, K: float, T: float, sigma: float, r: float, option_type: str, q: float = 0.0
    ) -> float:
        """Calculate Ultima (∂³V/∂σ³) - vomma sensitivity to vol"""
        if T <= 0:
            return 0.0

        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        vega = S * stats.norm.pdf(d1) * np.exp(-q * T) * np.sqrt(T)
        ultima = -vega / sigma**2 * (d1 * d2 * (1 - d1 * d2) + d1**2 + d2**2)

        return ultima / 1000  # For 1% vol change cubed

    # ==========================================================================
    # PORTFOLIO GREEKS
    # ==========================================================================

    def add_position(
        self,
        symbol: str,
        strike: float,
        expiry: datetime,
        option_type: str,
        quantity: int,
        spot: Optional[float] = None,
        volatility: Optional[float] = None,
    ) -> PositionGreeks:
        """
        Add position to portfolio and calculate Greeks

        Args:
            symbol: Asset symbol
            strike: Strike price
            expiry: Expiration date
            option_type: 'CALL' or 'PUT'
            quantity: Number of contracts (negative for short)
            spot: Current spot price
            volatility: Implied volatility

        Returns:
            PositionGreeks object
        """
        with self.lock:
            # Get market data
            spot = spot or self.spot_prices.get(symbol, 100.0)
            volatility = volatility or self.volatilities.get(symbol, 0.20)

            # Calculate time to expiry
            time_to_expiry = max(0, (expiry - datetime.now()).days / 365.0)

            # Calculate Greeks
            greeks = self.calculate_greeks(
                spot, strike, time_to_expiry, volatility, self.risk_free_rate, option_type
            )

            # Create position
            position = PositionGreeks(
                symbol=symbol,
                strike=strike,
                expiry=expiry,
                option_type=option_type,
                quantity=quantity,
                delta=greeks["delta"],
                gamma=greeks["gamma"],
                theta=greeks["theta"],
                vega=greeks["vega"],
                rho=greeks["rho"],
                vanna=greeks.get("vanna", 0),
                charm=greeks.get("charm", 0),
                vomma=greeks.get("vomma", 0),
                veta=greeks.get("veta", 0),
                color=greeks.get("color", 0),
                speed=greeks.get("speed", 0),
                zomma=greeks.get("zomma", 0),
                ultima=greeks.get("ultima", 0),
            )

            # Calculate position-level Greeks
            position.position_delta = position.delta * quantity * 100
            position.position_gamma = position.gamma * quantity * 100
            position.position_theta = position.theta * quantity * 100
            position.position_vega = position.vega * quantity * 100
            position.position_rho = position.rho * quantity * 100

            # Add to portfolio
            self.positions.append(position)

            # Update portfolio Greeks
            self._update_portfolio_greeks()

            return position

    def _update_portfolio_greeks(self) -> None:
        """Update aggregated portfolio Greeks"""
        # Reset totals
        self.portfolio_greeks = PortfolioGreeks()

        # Aggregate by position
        for position in self.positions:
            self.portfolio_greeks.total_delta += position.position_delta
            self.portfolio_greeks.total_gamma += position.position_gamma
            self.portfolio_greeks.total_theta += position.position_theta
            self.portfolio_greeks.total_vega += position.position_vega
            self.portfolio_greeks.total_rho += position.position_rho

            self.portfolio_greeks.total_vanna += position.vanna * position.quantity * 100
            self.portfolio_greeks.total_charm += position.charm * position.quantity * 100
            self.portfolio_greeks.total_vomma += position.vomma * position.quantity * 100
            self.portfolio_greeks.total_veta += position.veta * position.quantity * 100

            # Aggregate by expiry
            if position.expiry not in self.portfolio_greeks.greeks_by_expiry:
                self.portfolio_greeks.greeks_by_expiry[position.expiry] = {
                    "delta": 0,
                    "gamma": 0,
                    "theta": 0,
                    "vega": 0,
                }

            self.portfolio_greeks.greeks_by_expiry[position.expiry][
                "delta"
            ] += position.position_delta
            self.portfolio_greeks.greeks_by_expiry[position.expiry][
                "gamma"
            ] += position.position_gamma
            self.portfolio_greeks.greeks_by_expiry[position.expiry][
                "theta"
            ] += position.position_theta
            self.portfolio_greeks.greeks_by_expiry[position.expiry][
                "vega"
            ] += position.position_vega

            # Aggregate by strike
            if position.strike not in self.portfolio_greeks.greeks_by_strike:
                self.portfolio_greeks.greeks_by_strike[position.strike] = {
                    "delta": 0,
                    "gamma": 0,
                    "theta": 0,
                    "vega": 0,
                }

            self.portfolio_greeks.greeks_by_strike[position.strike][
                "delta"
            ] += position.position_delta
            self.portfolio_greeks.greeks_by_strike[position.strike][
                "gamma"
            ] += position.position_gamma
            self.portfolio_greeks.greeks_by_strike[position.strike][
                "theta"
            ] += position.position_theta
            self.portfolio_greeks.greeks_by_strike[position.strike][
                "vega"
            ] += position.position_vega

        # Calculate dollar exposures
        if self.positions:
            avg_spot = np.mean([self.spot_prices.get(p.symbol, 100) for p in self.positions])
            self.portfolio_greeks.delta_dollars = self.portfolio_greeks.total_delta * avg_spot
            self.portfolio_greeks.gamma_dollars = (
                self.portfolio_greeks.total_gamma * avg_spot**2 / 100
            )
            self.portfolio_greeks.theta_dollars = self.portfolio_greeks.total_theta
            self.portfolio_greeks.vega_dollars = self.portfolio_greeks.total_vega

        # Update timestamp
        self.portfolio_greeks.timestamp = datetime.now()

    # ==========================================================================
    # SCENARIO ANALYSIS
    # ==========================================================================

    def run_scenario_analysis(
        self, scenario_type: ScenarioType, parameters: Optional[Dict] = None
    ) -> List[ScenarioResult]:
        """
        Run scenario analysis on portfolio

        Args:
            scenario_type: Type of scenario to run
            parameters: Scenario parameters

        Returns:
            List of scenario results
        """
        results = []

        if scenario_type == ScenarioType.SPOT_MOVE:
            results = self._run_spot_scenarios(parameters)

        elif scenario_type == ScenarioType.VOL_CHANGE:
            results = self._run_vol_scenarios(parameters)

        elif scenario_type == ScenarioType.TIME_DECAY:
            results = self._run_time_scenarios(parameters)

        elif scenario_type == ScenarioType.COMBINED:
            results = self._run_combined_scenarios(parameters)

        elif scenario_type == ScenarioType.STRESS_TEST:
            results = self._run_stress_test(parameters)

        return results

    def _run_spot_scenarios(self, parameters: Optional[Dict] = None) -> List[ScenarioResult]:
        """Run spot price scenarios"""
        results = []
        spot_moves = parameters.get("spot_moves", SPOT_SCENARIOS) if parameters else SPOT_SCENARIOS

        for move_pct in spot_moves:
            # Calculate P&L for spot move
            pnl = 0.0
            new_delta = 0.0
            new_gamma = 0.0
            new_vega = 0.0
            new_theta = 0.0

            for position in self.positions:
                spot = self.spot_prices.get(position.symbol, 100.0)
                new_spot = spot * (1 + move_pct / 100)

                # Approximate P&L using Greeks
                position_pnl = (
                    position.position_delta * (new_spot - spot)
                    + 0.5 * position.position_gamma * (new_spot - spot) ** 2
                )
                pnl += position_pnl

                # Recalculate Greeks at new spot
                time_to_expiry = max(0, (position.expiry - datetime.now()).days / 365.0)
                volatility = self.volatilities.get(position.symbol, 0.20)

                new_greeks = self.calculate_greeks(
                    new_spot,
                    position.strike,
                    time_to_expiry,
                    volatility,
                    self.risk_free_rate,
                    position.option_type,
                )

                new_delta += new_greeks["delta"] * position.quantity * 100
                new_gamma += new_greeks["gamma"] * position.quantity * 100
                new_vega += new_greeks["vega"] * position.quantity * 100
                new_theta += new_greeks["theta"] * position.quantity * 100

            result = ScenarioResult(
                scenario_type=ScenarioType.SPOT_MOVE,
                parameters={"spot_move": move_pct},
                pnl=pnl,
                new_delta=new_delta,
                new_gamma=new_gamma,
                new_vega=new_vega,
                new_theta=new_theta,
                max_loss=min(0, pnl),
                max_gain=max(0, pnl),
                probability=self._calculate_move_probability(move_pct),
            )
            results.append(result)

        return results

    def _run_vol_scenarios(self, parameters: Optional[Dict] = None) -> List[ScenarioResult]:
        """Run volatility scenarios"""
        results = []
        vol_changes = parameters.get("vol_changes", VOL_SCENARIOS) if parameters else VOL_SCENARIOS

        for vol_change_pct in vol_changes:
            pnl = 0.0
            new_delta = 0.0
            new_gamma = 0.0
            new_vega = 0.0
            new_theta = 0.0

            for position in self.positions:
                volatility = self.volatilities.get(position.symbol, 0.20)
                new_vol = volatility * (1 + vol_change_pct / 100)

                # Approximate P&L using vega and vomma
                vol_change = new_vol - volatility
                position_pnl = (
                    position.position_vega * vol_change * 100
                    + 0.5 * position.vomma * position.quantity * 100 * (vol_change * 100) ** 2
                )
                pnl += position_pnl

                # Recalculate Greeks at new vol
                spot = self.spot_prices.get(position.symbol, 100.0)
                time_to_expiry = max(0, (position.expiry - datetime.now()).days / 365.0)

                new_greeks = self.calculate_greeks(
                    spot,
                    position.strike,
                    time_to_expiry,
                    new_vol,
                    self.risk_free_rate,
                    position.option_type,
                )

                new_delta += new_greeks["delta"] * position.quantity * 100
                new_gamma += new_greeks["gamma"] * position.quantity * 100
                new_vega += new_greeks["vega"] * position.quantity * 100
                new_theta += new_greeks["theta"] * position.quantity * 100

            result = ScenarioResult(
                scenario_type=ScenarioType.VOL_CHANGE,
                parameters={"vol_change": vol_change_pct},
                pnl=pnl,
                new_delta=new_delta,
                new_gamma=new_gamma,
                new_vega=new_vega,
                new_theta=new_theta,
                max_loss=min(0, pnl),
                max_gain=max(0, pnl),
            )
            results.append(result)

        return results

    def _run_time_scenarios(self, parameters: Optional[Dict] = None) -> List[ScenarioResult]:
        """Run time decay scenarios"""
        results = []
        days_forward = (
            parameters.get("days_forward", TIME_SCENARIOS) if parameters else TIME_SCENARIOS
        )

        for days in days_forward:
            pnl = 0.0
            new_delta = 0.0
            new_gamma = 0.0
            new_vega = 0.0
            new_theta = 0.0

            for position in self.positions:
                # Calculate theta decay
                position_pnl = position.position_theta * days
                pnl += position_pnl

                # Recalculate Greeks with reduced time
                spot = self.spot_prices.get(position.symbol, 100.0)
                volatility = self.volatilities.get(position.symbol, 0.20)
                time_to_expiry = max(
                    0, (position.expiry - datetime.now()).days / 365.0 - days / 365.0
                )

                if time_to_expiry > 0:
                    new_greeks = self.calculate_greeks(
                        spot,
                        position.strike,
                        time_to_expiry,
                        volatility,
                        self.risk_free_rate,
                        position.option_type,
                    )

                    new_delta += new_greeks["delta"] * position.quantity * 100
                    new_gamma += new_greeks["gamma"] * position.quantity * 100
                    new_vega += new_greeks["vega"] * position.quantity * 100
                    new_theta += new_greeks["theta"] * position.quantity * 100

            result = ScenarioResult(
                scenario_type=ScenarioType.TIME_DECAY,
                parameters={"days_forward": days},
                pnl=pnl,
                new_delta=new_delta,
                new_gamma=new_gamma,
                new_vega=new_vega,
                new_theta=new_theta,
                max_loss=min(0, pnl),
                max_gain=max(0, pnl),
            )
            results.append(result)

        return results

    def _run_stress_test(self, parameters: Optional[Dict] = None) -> List[ScenarioResult]:
        """Run stress test scenarios"""
        results = []

        # Define stress scenarios
        stress_scenarios = [
            {"name": "Market Crash", "spot": -20, "vol": 50, "days": 1},
            {"name": "Flash Crash", "spot": -10, "vol": 100, "days": 0},
            {"name": "Squeeze", "spot": 15, "vol": 30, "days": 1},
            {"name": "Vol Collapse", "spot": 0, "vol": -50, "days": 5},
            {"name": "Black Swan", "spot": -30, "vol": 200, "days": 0},
        ]

        for scenario in stress_scenarios:
            pnl = 0.0

            for position in self.positions:
                spot = self.spot_prices.get(position.symbol, 100.0)
                volatility = self.volatilities.get(position.symbol, 0.20)

                # Apply stress
                new_spot = spot * (1 + scenario["spot"] / 100)
                new_vol = volatility * (1 + scenario["vol"] / 100)
                time_decay = scenario["days"]

                # Calculate stressed P&L
                position_pnl = (
                    position.position_delta * (new_spot - spot)
                    + 0.5 * position.position_gamma * (new_spot - spot) ** 2
                    + position.position_vega * (new_vol - volatility) * 100
                    + position.position_theta * time_decay
                )
                pnl += position_pnl

            result = ScenarioResult(
                scenario_type=ScenarioType.STRESS_TEST,
                parameters=scenario,
                pnl=pnl,
                new_delta=0,  # Would need full recalc
                new_gamma=0,
                new_vega=0,
                new_theta=0,
                max_loss=min(0, pnl),
                max_gain=max(0, pnl),
            )
            results.append(result)

        return results

    def _calculate_move_probability(self, move_pct: float) -> float:
        """Calculate probability of spot move"""
        # Use normal distribution assumption
        # Assume daily vol of 1% (annual vol ~16%)
        daily_vol = 0.01
        z_score = move_pct / (daily_vol * 100)
        probability = 1 - stats.norm.cdf(abs(z_score))
        return probability

    def _run_combined_scenarios(self, parameters: Optional[Dict] = None) -> List[ScenarioResult]:
        """Run combined scenarios"""
        results = []

        # Define combined scenarios
        combined = [
            {"spot": -5, "vol": 10, "days": 1},
            {"spot": -2, "vol": 5, "days": 1},
            {"spot": 0, "vol": 0, "days": 1},
            {"spot": 2, "vol": -5, "days": 1},
            {"spot": 5, "vol": -10, "days": 1},
        ]

        for combo in combined:
            pnl = 0.0

            for position in self.positions:
                spot = self.spot_prices.get(position.symbol, 100.0)
                volatility = self.volatilities.get(position.symbol, 0.20)

                new_spot = spot * (1 + combo["spot"] / 100)
                new_vol = volatility * (1 + combo["vol"] / 100)

                position_pnl = (
                    position.position_delta * (new_spot - spot)
                    + 0.5 * position.position_gamma * (new_spot - spot) ** 2
                    + position.position_vega * (new_vol - volatility) * 100
                    + position.position_theta * combo["days"]
                )
                pnl += position_pnl

            result = ScenarioResult(
                scenario_type=ScenarioType.COMBINED,
                parameters=combo,
                pnl=pnl,
                new_delta=0,
                new_gamma=0,
                new_vega=0,
                new_theta=0,
                max_loss=min(0, pnl),
                max_gain=max(0, pnl),
            )
            results.append(result)

        return results

    # ==========================================================================
    # HEDGING RECOMMENDATIONS
    # ==========================================================================

    def get_hedge_recommendation(
        self, hedge_type: HedgeType, target_greeks: Optional[Dict[str, float]] = None
    ) -> HedgeRecommendation:
        """
        Get hedging recommendation

        Args:
            hedge_type: Type of hedge required
            target_greeks: Target Greek values (default: neutral)

        Returns:
            HedgeRecommendation object
        """
        # Default target is neutral (zero) Greeks
        if target_greeks is None:
            target_greeks = {
                "delta": 0.0,
                "gamma": 0.0,
                "vega": 0.0,
                "theta": None,  # Don't target theta
            }

        current_exposure = {
            "delta": self.portfolio_greeks.total_delta,
            "gamma": self.portfolio_greeks.total_gamma,
            "vega": self.portfolio_greeks.total_vega,
            "theta": self.portfolio_greeks.total_theta,
        }

        hedge_trades = []

        if hedge_type == HedgeType.DELTA_HEDGE:
            hedge_trades = self._calculate_delta_hedge(
                current_exposure["delta"], target_greeks.get("delta", 0.0)
            )

        elif hedge_type == HedgeType.GAMMA_HEDGE:
            hedge_trades = self._calculate_gamma_hedge(
                current_exposure["gamma"], target_greeks.get("gamma", 0.0)
            )

        elif hedge_type == HedgeType.VEGA_HEDGE:
            hedge_trades = self._calculate_vega_hedge(
                current_exposure["vega"], target_greeks.get("vega", 0.0)
            )

        elif hedge_type == HedgeType.DELTA_GAMMA:
            hedge_trades = self._calculate_delta_gamma_hedge(current_exposure, target_greeks)

        elif hedge_type == HedgeType.FULL_HEDGE:
            hedge_trades = self._calculate_full_hedge(current_exposure, target_greeks)

        # Calculate cost estimate
        cost_estimate = sum(trade.get("cost", 0) for trade in hedge_trades)

        # Calculate effectiveness (how close to target)
        effectiveness = 100.0
        if hedge_trades:
            for greek in ["delta", "gamma", "vega"]:
                if target_greeks.get(greek) is not None:
                    hedge_greek = sum(trade.get(greek, 0) for trade in hedge_trades)
                    residual = abs(current_exposure[greek] + hedge_greek - target_greeks[greek])
                    effectiveness *= 1 - min(residual / max(abs(current_exposure[greek]), 1), 1)

        recommendation = HedgeRecommendation(
            hedge_type=hedge_type,
            current_exposure=current_exposure,
            target_exposure=target_greeks,
            hedge_trades=hedge_trades,
            cost_estimate=cost_estimate,
            effectiveness=effectiveness * 100,
        )

        return recommendation

    def _calculate_delta_hedge(self, current_delta: float, target_delta: float) -> List[Dict]:
        """Calculate delta hedge trades"""
        hedge_trades = []
        delta_to_hedge = target_delta - current_delta

        if abs(delta_to_hedge) > 0.1:
            # Simple stock hedge
            hedge_trades.append(
                {
                    "instrument": "STOCK",
                    "symbol": "SPY",  # Default to SPY
                    "quantity": int(delta_to_hedge),
                    "delta": delta_to_hedge,
                    "cost": abs(delta_to_hedge) * self.spot_prices.get("SPY", 585.0),
                }
            )

        return hedge_trades

    def _calculate_gamma_hedge(self, current_gamma: float, target_gamma: float) -> List[Dict]:
        """Calculate gamma hedge trades"""
        hedge_trades = []
        gamma_to_hedge = target_gamma - current_gamma

        if abs(gamma_to_hedge) > 0.01:
            # Use ATM options for gamma
            # Simplified - would need actual option chain
            atm_gamma = 0.01  # Approximate ATM gamma
            contracts_needed = int(gamma_to_hedge / atm_gamma)

            hedge_trades.append(
                {
                    "instrument": "OPTION",
                    "symbol": "SPY",
                    "strike": 585.0,  # ATM
                    "option_type": "CALL" if gamma_to_hedge > 0 else "PUT",
                    "quantity": abs(contracts_needed),
                    "gamma": gamma_to_hedge,
                    "cost": abs(contracts_needed) * 100 * 2.0,  # Approximate premium
                }
            )

        return hedge_trades

    def _calculate_vega_hedge(self, current_vega: float, target_vega: float) -> List[Dict]:
        """Calculate vega hedge trades"""
        hedge_trades = []
        vega_to_hedge = target_vega - current_vega

        if abs(vega_to_hedge) > 1.0:
            # Use ATM options for vega
            atm_vega = 0.20  # Approximate ATM vega
            contracts_needed = int(vega_to_hedge / atm_vega)

            hedge_trades.append(
                {
                    "instrument": "OPTION",
                    "symbol": "SPY",
                    "strike": 585.0,
                    "option_type": "CALL",
                    "quantity": contracts_needed,
                    "vega": vega_to_hedge,
                    "cost": abs(contracts_needed) * 100 * 2.0,
                }
            )

        return hedge_trades

    def _calculate_delta_gamma_hedge(
        self, current_exposure: Dict, target_greeks: Dict
    ) -> List[Dict]:
        """Calculate delta-gamma hedge using two instruments"""
        hedge_trades = []

        # Need two instruments to hedge both delta and gamma
        # Use ATM option for gamma, stock for residual delta

        gamma_to_hedge = target_greeks.get("gamma", 0) - current_exposure["gamma"]

        if abs(gamma_to_hedge) > 0.01:
            # First, hedge gamma with options
            atm_gamma = 0.01
            atm_delta = 0.5
            option_contracts = int(gamma_to_hedge / atm_gamma)

            hedge_trades.append(
                {
                    "instrument": "OPTION",
                    "symbol": "SPY",
                    "strike": 585.0,
                    "option_type": "CALL" if gamma_to_hedge > 0 else "PUT",
                    "quantity": abs(option_contracts),
                    "delta": option_contracts * atm_delta * 100,
                    "gamma": option_contracts * atm_gamma * 100,
                    "cost": abs(option_contracts) * 100 * 2.0,
                }
            )

            # Then hedge residual delta with stock
            residual_delta = (
                target_greeks.get("delta", 0)
                - current_exposure["delta"]
                - option_contracts * atm_delta * 100
            )

            if abs(residual_delta) > 1:
                hedge_trades.append(
                    {
                        "instrument": "STOCK",
                        "symbol": "SPY",
                        "quantity": int(residual_delta),
                        "delta": residual_delta,
                        "cost": abs(residual_delta) * self.spot_prices.get("SPY", 585.0),
                    }
                )

        return hedge_trades

    def _calculate_full_hedge(self, current_exposure: Dict, target_greeks: Dict) -> List[Dict]:
        """Calculate full hedge for all Greeks"""
        # This would use optimization to find best combination
        # Simplified version combines individual hedges
        hedge_trades = []

        # Add individual hedges
        hedge_trades.extend(
            self._calculate_delta_hedge(current_exposure["delta"], target_greeks.get("delta", 0))
        )

        hedge_trades.extend(
            self._calculate_gamma_hedge(current_exposure["gamma"], target_greeks.get("gamma", 0))
        )

        hedge_trades.extend(
            self._calculate_vega_hedge(current_exposure["vega"], target_greeks.get("vega", 0))
        )

        return hedge_trades

    # ==========================================================================
    # VISUALIZATION
    # ==========================================================================

    def plot_greeks_surface(
        self,
        greek_type: GreekType = GreekType.DELTA,
        spot_range: Optional[Tuple[float, float]] = None,
        vol_range: Optional[Tuple[float, float]] = None,
    ) -> None:
        """
        Plot 3D surface of Greek values

        Args:
            greek_type: Type of Greek to plot
            spot_range: Range of spot prices
            vol_range: Range of volatilities
        """
        if not self.positions:
            self.logger.warning("No positions to plot")
            return

        # Get first position for reference
        position = self.positions[0]
        strike = position.strike
        time_to_expiry = max(0, (position.expiry - datetime.now()).days / 365.0)

        # Define ranges
        current_spot = self.spot_prices.get(position.symbol, 100.0)
        current_vol = self.volatilities.get(position.symbol, 0.20)

        if spot_range is None:
            spot_range = (current_spot * 0.8, current_spot * 1.2)
        if vol_range is None:
            vol_range = (current_vol * 0.5, current_vol * 1.5)

        # Create mesh
        spots = np.linspace(spot_range[0], spot_range[1], 50)
        vols = np.linspace(vol_range[0], vol_range[1], 50)
        SPOTS, VOLS = np.meshgrid(spots, vols)

        # Calculate Greek values
        GREEKS = np.zeros_like(SPOTS)

        for i in range(len(spots)):
            for j in range(len(vols)):
                greeks = self.calculate_greeks(
                    SPOTS[j, i],
                    strike,
                    time_to_expiry,
                    VOLS[j, i],
                    self.risk_free_rate,
                    position.option_type,
                )
                GREEKS[j, i] = greeks[greek_type.value.lower()]

        # Plot surface
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        surf = ax.plot_surface(SPOTS, VOLS, GREEKS, cmap=cm.RdYlGn_r, alpha=0.8)

        ax.set_xlabel("Spot Price")
        ax.set_ylabel("Volatility")
        ax.set_zlabel(greek_type.value)
        ax.set_title(f"{greek_type.value} Surface")

        fig.colorbar(surf)
        plt.show()

    def plot_scenario_results(self, results: List[ScenarioResult]) -> None:
        """
        Plot scenario analysis results

        Args:
            results: List of scenario results
        """
        if not results:
            return

        # Extract data
        params = [r.parameters.get("spot_move", 0) for r in results]
        pnls = [r.pnl for r in results]

        # Create plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # P&L plot
        ax1.plot(params, pnls, "b-", linewidth=2)
        ax1.axhline(y=0, color="r", linestyle="--", alpha=0.5)
        ax1.fill_between(params, pnls, 0, where=(np.array(pnls) >= 0), color="green", alpha=0.3)
        ax1.fill_between(params, pnls, 0, where=(np.array(pnls) < 0), color="red", alpha=0.3)
        ax1.set_xlabel("Spot Move (%)")
        ax1.set_ylabel("P&L ($)")
        ax1.set_title("Scenario P&L Analysis")
        ax1.grid(True, alpha=0.3)

        # Greeks plot
        deltas = [r.new_delta for r in results]
        gammas = [r.new_gamma for r in results]

        ax2.plot(params, deltas, "b-", label="Delta", linewidth=2)
        ax2.plot(params, gammas, "g-", label="Gamma", linewidth=2)
        ax2.axhline(y=0, color="r", linestyle="--", alpha=0.5)
        ax2.set_xlabel("Spot Move (%)")
        ax2.set_ylabel("Greek Value")
        ax2.set_title("Greeks Under Scenarios")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show()

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive portfolio summary

        Returns:
            Dictionary with portfolio metrics
        """
        summary = {
            "num_positions": len(self.positions),
            "portfolio_greeks": {
                "delta": self.portfolio_greeks.total_delta,
                "gamma": self.portfolio_greeks.total_gamma,
                "theta": self.portfolio_greeks.total_theta,
                "vega": self.portfolio_greeks.total_vega,
                "rho": self.portfolio_greeks.total_rho,
                "vanna": self.portfolio_greeks.total_vanna,
                "charm": self.portfolio_greeks.total_charm,
                "vomma": self.portfolio_greeks.total_vomma,
            },
            "dollar_exposures": {
                "delta_dollars": self.portfolio_greeks.delta_dollars,
                "gamma_dollars": self.portfolio_greeks.gamma_dollars,
                "theta_dollars": self.portfolio_greeks.theta_dollars,
                "vega_dollars": self.portfolio_greeks.vega_dollars,
            },
            "risk_metrics": {
                "max_loss_1std": self._calculate_var(0.84),
                "max_loss_2std": self._calculate_var(0.98),
                "theta_per_day": self.portfolio_greeks.total_theta,
            },
            "positions_by_expiry": len(self.portfolio_greeks.greeks_by_expiry),
            "positions_by_strike": len(self.portfolio_greeks.greeks_by_strike),
            "last_update": self.portfolio_greeks.timestamp,
        }

        return summary

    def _calculate_var(self, confidence: float) -> float:
        """Calculate Value at Risk"""
        # Simplified VaR using delta-gamma approximation
        if not self.positions:
            return 0.0

        # Assume 1-day move
        daily_vol = 0.01  # 1% daily volatility
        z_score = stats.norm.ppf(confidence)

        # Get average spot
        avg_spot = np.mean([self.spot_prices.get(p.symbol, 100) for p in self.positions])
        spot_move = avg_spot * daily_vol * z_score

        # Calculate potential loss
        var = (
            self.portfolio_greeks.total_delta * spot_move
            + 0.5 * self.portfolio_greeks.total_gamma * spot_move**2
        )

        return var

    def clear_positions(self) -> None:
        """Clear all positions"""
        with self.lock:
            self.positions = []
            self.portfolio_greeks = PortfolioGreeks()
            self.logger.info("All positions cleared")

    def update_market_data(self, symbol: str, spot: float, volatility: float) -> None:
        """
        Update market data for symbol

        Args:
            symbol: Asset symbol
            spot: Current spot price
            volatility: Implied volatility
        """
        with self.lock:
            self.spot_prices[symbol] = spot
            self.volatilities[symbol] = volatility

            # Recalculate Greeks for affected positions
            for position in self.positions:
                if position.symbol == symbol:
                    time_to_expiry = max(0, (position.expiry - datetime.now()).days / 365.0)

                    greeks = self.calculate_greeks(
                        spot,
                        position.strike,
                        time_to_expiry,
                        volatility,
                        self.risk_free_rate,
                        position.option_type,
                    )

                    # Update position Greeks
                    position.delta = greeks["delta"]
                    position.gamma = greeks["gamma"]
                    position.theta = greeks["theta"]
                    position.vega = greeks["vega"]
                    position.rho = greeks["rho"]

                    # Update position-level Greeks
                    position.position_delta = position.delta * position.quantity * 100
                    position.position_gamma = position.gamma * position.quantity * 100
                    position.position_theta = position.theta * position.quantity * 100
                    position.position_vega = position.vega * position.quantity * 100
                    position.position_rho = position.rho * position.quantity * 100

            # Update portfolio Greeks
            self._update_portfolio_greeks()


# ==============================================================================
# TEST/DEMO CODE
# ==============================================================================
if __name__ == "__main__":
    print("=" * 80)
    print(" SPYDER OPTIONS GREEKS CALCULATOR TEST")
    print("=" * 80)

    # Create calculator
    calculator = OptionsGreeksCalculator()

    # Set market data
    calculator.update_market_data("SPY", 585.0, 0.15)
    calculator.risk_free_rate = 0.05

    # Test 1: Calculate Greeks for single option
    print("\n1. Single Option Greeks Calculation...")
    greeks = calculator.calculate_greeks(
        spot=585.0,
        strike=590.0,
        time_to_expiry=30 / 365,
        volatility=0.15,
        risk_free_rate=0.05,
        option_type="CALL",
    )

    print("\nFirst-Order Greeks:")
    for greek in ["delta", "gamma", "theta", "vega", "rho"]:
        print(f"  {greek.capitalize()}: {greeks[greek]:.4f}")

    print("\nSecond-Order Greeks:")
    for greek in ["vanna", "charm", "vomma", "veta", "color", "speed"]:
        print(f"  {greek.capitalize()}: {greeks[greek]:.6f}")

    # Test 2: Portfolio Greeks
    print("\n2. Building Options Portfolio...")

    # Add iron condor position
    expiry = datetime.now() + timedelta(days=30)

    # Short put spread
    calculator.add_position("SPY", 575, expiry, "PUT", -1)  # Short put
    calculator.add_position("SPY", 570, expiry, "PUT", 1)  # Long put

    # Short call spread
    calculator.add_position("SPY", 595, expiry, "CALL", -1)  # Short call
    calculator.add_position("SPY", 600, expiry, "CALL", 1)  # Long call

    print(f"Added Iron Condor with {len(calculator.positions)} legs")

    # Get portfolio Greeks
    print("\n3. Portfolio Greeks:")
    portfolio = calculator.get_portfolio_summary()
    for greek, value in portfolio["portfolio_greeks"].items():
        print(f"  Total {greek}: {value:.2f}")

    print("\n4. Dollar Exposures:")
    for exposure, value in portfolio["dollar_exposures"].items():
        print(f"  {exposure}: ${value:.2f}")

    # Test 3: Scenario Analysis
    print("\n5. Running Scenario Analysis...")

    # Spot scenarios
    spot_results = calculator.run_scenario_analysis(ScenarioType.SPOT_MOVE)
    print("\nSpot Move Scenarios:")
    for result in spot_results[::2]:  # Show every other result
        move = result.parameters["spot_move"]
        print(f"  {move:+3.0f}% move: P&L=${result.pnl:,.0f}, " f"New Delta={result.new_delta:.0f}")

    # Volatility scenarios
    vol_results = calculator.run_scenario_analysis(ScenarioType.VOL_CHANGE)
    print("\nVolatility Scenarios:")
    for result in vol_results[::2]:
        vol_change = result.parameters["vol_change"]
        print(
            f"  {vol_change:+3.0f}% vol: P&L=${result.pnl:,.0f}, " f"New Vega={result.new_vega:.0f}"
        )

    # Stress test
    stress_results = calculator.run_scenario_analysis(ScenarioType.STRESS_TEST)
    print("\nStress Test Results:")
    for result in stress_results:
        scenario = result.parameters["name"]
        print(f"  {scenario}: P&L=${result.pnl:,.0f}")

    # Test 4: Hedging Recommendations
    print("\n6. Hedging Recommendations...")

    # Delta hedge
    delta_hedge = calculator.get_hedge_recommendation(HedgeType.DELTA_HEDGE)
    print(f"\nDelta Hedge:")
    print(f"  Current Delta: {delta_hedge.current_exposure['delta']:.0f}")
    print(f"  Target Delta: {delta_hedge.target_exposure['delta']:.0f}")
    if delta_hedge.hedge_trades:
        for trade in delta_hedge.hedge_trades:
            print(f"  Trade: {trade['instrument']} {trade['quantity']} units")
    print(f"  Cost Estimate: ${delta_hedge.cost_estimate:,.0f}")
    print(f"  Effectiveness: {delta_hedge.effectiveness:.0f}%")

    # Delta-Gamma hedge
    dg_hedge = calculator.get_hedge_recommendation(HedgeType.DELTA_GAMMA)
    print(f"\nDelta-Gamma Hedge:")
    print(f"  Current Gamma: {dg_hedge.current_exposure['gamma']:.2f}")
    print(f"  Trades Required: {len(dg_hedge.hedge_trades)}")

    # Test 5: Risk Metrics
    print("\n7. Risk Metrics:")
    print(f"  1-Std VaR: ${portfolio['risk_metrics']['max_loss_1std']:,.0f}")
    print(f"  2-Std VaR: ${portfolio['risk_metrics']['max_loss_2std']:,.0f}")
    print(f"  Daily Theta: ${portfolio['risk_metrics']['theta_per_day']:,.0f}")

    # Test visualization (commented out for non-interactive environment)
    # print("\n8. Generating Greeks Surface Plot...")
    # calculator.plot_greeks_surface(GreekType.DELTA)
    # calculator.plot_scenario_results(spot_results)

    print("\n" + "=" * 80)
    print(" ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 80)
