#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV09_IVEngine.py
Purpose: **CANONICAL** synchronous BSM pricing, implied volatility, Greeks,
         and volatility surface/analytics computation engine

This is the primary BSM/Greeks engine for the system.  All new callers that
need synchronous (non-async) BSM calculations should import from this module:

    from SpyderV_QuantModels.SpyderV09_IVEngine import (
        BlackScholesCalculator,
        GreeksCalculator,
        VolatilityAnalyzer,
    )

Existing specialist modules that maintain separate BSM implementations for
performance or integration reasons:
    • SpyderF06_GreeksCalculator  — F-Series indicator pipeline integration
      (uses cachetools + F-Series context; delegates heavy lifting to V09 when
      possible)
    • SpyderN04_OptionsGreeksCalculator — numba @njit JIT kernel for
      high-throughput Greeks sweeps (kept separate for performance).  New
      non-throughput callers should use V09 instead.
    • SpyderV05_PricingEngine — async BSM engine for the V-Series quant stack
      (async overhead justified for batch pricing; V09 is preferred for
      synchronous single-contract queries).

Provides standalone, synchronous BSM computation classes that are consumed
by the Z-series ZMQ process workers (SpyderZ04_VolatilityEngine) and by any
other module that requires fast, dependency-light option maths without the
async overhead of SpyderV05_PricingEngine.

Defines:
    VolatilityModel          — volatility surface model enum
    GreekType                — Greek type enum
    OptionContract           — lightweight option contract dataclass
    Greeks                   — first and second-order Greeks dataclass
    VolatilitySurface        — vol surface with bivariate spline interpolation
    VolatilityMetrics        — full vol metrics snapshot dataclass
    CalculationCache         — thread-safe LRU cache with TTL eviction
    BlackScholesCalculator   — static BSM pricing, vega, and IV (Newton-Raphson)
    GreeksCalculator         — full first + second-order Greeks with caching
    VolatilityAnalyzer       — ATM IV, skew, term structure, and regime detection
    VolatilitySurfaceBuilder — build and interpolate 2-D IV surfaces

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-01 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import hashlib
import logging
import threading
import time
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy import interpolate
from scipy.ndimage import gaussian_filter
from scipy.stats import norm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
RISK_FREE_RATE: float = 0.05       # 5 % annual risk-free rate (dynamic in production)
DAYS_IN_YEAR: int = 252             # Trading days per year
VOLATILITY_WINDOW: int = 20         # Days for historical volatility window
MIN_VOLATILITY: float = 0.01        # 1 % minimum allowed IV
MAX_VOLATILITY: float = 5.0         # 500 % maximum allowed IV
IV_TOLERANCE: float = 1e-6          # Newton-Raphson convergence tolerance
MAX_ITERATIONS: int = 100           # Newton-Raphson max iterations

DELTA_SHIFT: float = 0.01           # 1 % price shift for numerical derivatives
TIME_SHIFT: float = 1 / 365        # 1 calendar-day time shift

CACHE_SIZE: int = 10_000            # Maximum LRU cache entries
CACHE_TTL: float = 60.0             # Cache TTL in seconds

BATCH_SIZE: int = 100               # Processing batch size
UPDATE_INTERVAL: float = 0.1       # Periodic-update interval in seconds

VOLATILITY_REGIMES: dict[str, tuple[float, float]] = {
    "VERY_LOW": (0.00, 0.10),
    "LOW": (0.10, 0.15),
    "NORMAL": (0.15, 0.25),
    "ELEVATED": (0.25, 0.35),
    "HIGH": (0.35, 0.50),
    "EXTREME": (0.50, float("inf")),
}

# ==============================================================================
# ENUMS
# ==============================================================================


class VolatilityModel(Enum):
    """Supported volatility surface model types."""

    BLACK_SCHOLES = "BLACK_SCHOLES"
    SABR = "SABR"
    SVI = "SVI"
    POLYNOMIAL = "POLYNOMIAL"


class GreekType(Enum):
    """Option Greek identifiers."""

    DELTA = "DELTA"
    GAMMA = "GAMMA"
    THETA = "THETA"
    VEGA = "VEGA"
    RHO = "RHO"
    LAMBDA = "LAMBDA"
    VANNA = "VANNA"
    VOLGA = "VOLGA"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class OptionContract:
    """Lightweight option contract specification used across V09 computation.

    Attributes:
        symbol:           OCC-formatted options symbol.
        underlying:       Underlying ticker (e.g. ``"SPY"``).
        strike:           Strike price.
        expiry:           Expiration date.
        option_type:      ``"CALL"`` or ``"PUT"``.
        bid:              Current best bid.
        ask:              Current best ask.
        last:             Last trade price.
        volume:           Day volume.
        open_interest:    Open interest.
        underlying_price: Current spot price of the underlying.
        timestamp:        Unix epoch when this snapshot was captured.
    """

    symbol: str
    underlying: str
    strike: float
    expiry: date
    option_type: str          # "CALL" or "PUT"
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    underlying_price: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class Greeks:
    """First and second-order Black-Scholes Greeks.

    Attributes:
        delta:   Price sensitivity to underlying move (dV/dS).
        gamma:   Delta sensitivity to underlying move (d²V/dS²).
        theta:   Time decay per calendar day (dV/dt).
        vega:    Sensitivity to 1 % change in implied volatility (dV/dσ).
        rho:     Sensitivity to 1 % change in risk-free rate (dV/dr).
        lambda_: Leverage / omega (delta × S / V).
        vanna:   Cross-Greek dΔ/dσ, per 1 % vol change.
        volga:   dV/dσ² (vomma), per 1 % vol change squared.
        charm:   dΔ/dt per calendar day.
        veta:    dV/dt per calendar day per 1 % vol change.
        timestamp: Unix epoch of calculation.
    """

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    lambda_: float = 0.0
    vanna: float = 0.0
    volga: float = 0.0
    charm: float = 0.0
    veta: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class VolatilitySurface:
    """Two-dimensional implied volatility surface spanning expiries and strikes.

    Attributes:
        underlying:     Underlying ticker.
        spot_price:     Spot price at build time.
        risk_free_rate: Risk-free rate used during construction.
        dividend_yield: Continuous dividend yield used during construction.
        timestamp:      Unix epoch of build time.
        expiries:       Sorted list of time-to-expiry values in years.
        strikes:        Sorted list of strike prices.
        ivs:            2-D array of shape ``(len(expiries), len(strikes))``
                        containing implied volatility values.
        model_type:     Surface model used for construction.
    """

    underlying: str
    spot_price: float
    risk_free_rate: float
    dividend_yield: float
    timestamp: float
    expiries: list[float]
    strikes: list[float]
    ivs: np.ndarray
    model_type: VolatilityModel = VolatilityModel.BLACK_SCHOLES

    def get_iv(self, strike: float, expiry: float) -> float:
        """Interpolate IV for a given strike and time-to-expiry.

        Args:
            strike: Target strike price.
            expiry: Time to expiry in years.

        Returns:
            Interpolated implied volatility.
        """
        if len(self.strikes) == 1 or len(self.expiries) == 1:
            return float(self.ivs[0, 0])

        f = interpolate.RectBivariateSpline(
            self.expiries, self.strikes, self.ivs, kx=1, ky=1
        )
        return float(f(expiry, strike)[0, 0])


@dataclass
class VolatilityMetrics:
    """Comprehensive snapshot of volatility analytics.

    Attributes:
        current_iv:    ATM implied volatility.
        historical_vol: Annualised close-to-close historical volatility.
        iv_rank:       IV rank (0–100) relative to trailing-year range.
        iv_percentile: IV percentile (0–100) relative to trailing-year distribution.
        realized_vol:  Realised volatility over recent window.
        vol_of_vol:    Volatility-of-volatility estimate.
        skew:          25-delta put IV minus 25-delta call IV.
        term_structure: Mapping of monthly-bucketed expiry → ATM IV.
        regime:        Volatility regime label (e.g. ``"NORMAL"``, ``"HIGH"``).
        timestamp:     Unix epoch of calculation.
    """

    current_iv: float
    historical_vol: float
    iv_rank: float
    iv_percentile: float
    realized_vol: float
    vol_of_vol: float
    skew: float
    term_structure: dict[float, float]
    regime: str
    timestamp: float = field(default_factory=time.time)


# ==============================================================================
# CACHE IMPLEMENTATION
# ==============================================================================


class CalculationCache:
    """Thread-safe LRU cache with TTL eviction for expensive option calculations.

    Args:
        max_size: Maximum number of entries to hold in memory.
        ttl:      Time-to-live in seconds before an entry expires.
    """

    def __init__(self, max_size: int = CACHE_SIZE, ttl: float = CACHE_TTL) -> None:
        self.max_size = max_size
        self.ttl = ttl
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: dict[str, float] = {}
        self._lock = threading.Lock()

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        """Derive a deterministic cache key from the call arguments."""
        key_data = (args, tuple(sorted(kwargs.items())))
        return hashlib.md5(str(key_data).encode(), usedforsecurity=False).hexdigest()

    def get(self, key: str) -> Any | None:
        """Return the cached value for *key*, or ``None`` on miss/expiry."""
        with self._lock:
            if key not in self.cache:
                return None
            if time.time() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                return None
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key: str, value: Any) -> None:
        """Store *value* under *key*, evicting the oldest entry if at capacity."""
        with self._lock:
            if len(self.cache) >= self.max_size:
                oldest = next(iter(self.cache))
                del self.cache[oldest]
                del self.timestamps[oldest]
            self.cache[key] = value
            self.timestamps[key] = time.time()

    def clear(self) -> None:
        """Remove all entries from the cache."""
        with self._lock:
            self.cache.clear()
            self.timestamps.clear()


# ==============================================================================
# BLACK-SCHOLES CALCULATIONS
# ==============================================================================


class BlackScholesCalculator:
    """Stateless Black-Scholes pricing, vega, and implied volatility solver.

    All methods are static; no instance state is maintained.
    """

    @staticmethod
    def calculate_d1_d2(
        S: float, K: float, r: float, q: float, sigma: float, T: float
    ) -> tuple[float, float]:
        """Compute the BSM d1 and d2 intermediates.

        Args:
            S:     Spot price.
            K:     Strike price.
            r:     Continuous risk-free rate.
            q:     Continuous dividend yield.
            sigma: Annualised implied volatility.
            T:     Time to expiry in years.

        Returns:
            Tuple ``(d1, d2)``.
        """
        if T <= 0:
            return 0.0, 0.0
        sigma = max(sigma, 1e-9)
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return d1, d2

    @staticmethod
    def call_price(
        S: float, K: float, r: float, q: float, sigma: float, T: float
    ) -> float:
        """Black-Scholes European call price.

        Args:
            S: Spot price.
            K: Strike price.
            r: Continuous risk-free rate.
            q: Continuous dividend yield.
            sigma: Annualised implied volatility.
            T: Time to expiry in years.

        Returns:
            Theoretical call price (floored at intrinsic value).
        """
        if T <= 0:
            return max(S - K, 0.0)
        d1, d2 = BlackScholesCalculator.calculate_d1_d2(S, K, r, q, sigma, T)
        return max(S * np.exp(-q * T) * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2), 0.0)

    @staticmethod
    def put_price(
        S: float, K: float, r: float, q: float, sigma: float, T: float
    ) -> float:
        """Black-Scholes European put price.

        Args:
            S: Spot price.
            K: Strike price.
            r: Continuous risk-free rate.
            q: Continuous dividend yield.
            sigma: Annualised implied volatility.
            T: Time to expiry in years.

        Returns:
            Theoretical put price (floored at intrinsic value).
        """
        if T <= 0:
            return max(K - S, 0.0)
        d1, d2 = BlackScholesCalculator.calculate_d1_d2(S, K, r, q, sigma, T)
        return max(K * np.exp(-r * T) * norm.cdf(-d2) - S * np.exp(-q * T) * norm.cdf(-d1), 0.0)

    @staticmethod
    def calculate_vega(
        S: float, K: float, r: float, q: float, sigma: float, T: float
    ) -> float:
        """BSM vega (dV/dσ) per 1 % change in volatility.

        Args:
            S: Spot price.
            K: Strike price.
            r: Continuous risk-free rate.
            q: Continuous dividend yield.
            sigma: Annualised implied volatility.
            T: Time to expiry in years.

        Returns:
            Vega per 1 % vol change.
        """
        if T <= 0:
            return 0.0
        d1, _ = BlackScholesCalculator.calculate_d1_d2(S, K, r, q, sigma, T)
        return S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) / 100

    @staticmethod
    def implied_volatility(
        option_price: float,
        S: float,
        K: float,
        r: float,
        q: float,
        T: float,
        option_type: str = "CALL",
    ) -> float:
        """Solve for implied volatility via Newton-Raphson iteration.

        Args:
            option_price: Market mid-price of the option.
            S:            Spot price.
            K:            Strike price.
            r:            Continuous risk-free rate.
            q:            Continuous dividend yield.
            T:            Time to expiry in years.
            option_type:  ``"CALL"`` or ``"PUT"``.

        Returns:
            Solved implied volatility, or ``0.0`` on failure.
        """
        if T <= 0:
            return 0.0
        intrinsic = max(S - K, 0.0) if option_type == "CALL" else max(K - S, 0.0)
        if option_price < intrinsic:
            return 0.0

        # Brenner-Subrahmanyam initial guess
        sigma = np.sqrt(2 * np.pi / T) * option_price / S
        sigma = max(MIN_VOLATILITY, min(sigma, MAX_VOLATILITY))

        price_func = (
            BlackScholesCalculator.call_price
            if option_type == "CALL"
            else BlackScholesCalculator.put_price
        )

        for _ in range(MAX_ITERATIONS):
            price = price_func(S, K, r, q, sigma, T)
            vega = BlackScholesCalculator.calculate_vega(S, K, r, q, sigma, T) * 100
            if abs(vega) < 1e-10:
                break
            price_diff = option_price - price
            if abs(price_diff) < IV_TOLERANCE:
                break
            sigma = sigma + price_diff / vega
            sigma = max(MIN_VOLATILITY, min(sigma, MAX_VOLATILITY))

        return sigma


# ==============================================================================
# GREEKS CALCULATOR
# ==============================================================================


class GreeksCalculator:
    """Compute all first and second-order Black-Scholes Greeks with LRU caching.

    Maintains a :class:`CalculationCache` keyed on ``(symbol, spot, iv, r, q)``
    to avoid redundant recalculations within the same ZMQ processing loop.
    """

    def __init__(self) -> None:
        self.bs = BlackScholesCalculator()
        self.cache = CalculationCache()

    def calculate_all_greeks(
        self,
        option: OptionContract,
        iv: float | None = None,
        r: float = RISK_FREE_RATE,
        q: float = 0.0,
    ) -> Greeks:
        """Calculate all Greeks for an option.

        Args:
            option: Option contract to evaluate.
            iv:     Implied volatility; calculated from mid-price when ``None``.
            r:      Continuous risk-free rate.
            q:      Continuous dividend yield.

        Returns:
            :class:`Greeks` populated with first and second-order values.
        """
        cache_key = self.cache._make_key(option.symbol, option.underlying_price, iv, r, q)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        T = max((option.expiry - date.today()).days / DAYS_IN_YEAR, 1 / DAYS_IN_YEAR)

        if iv is None:
            mid_price = (option.bid + option.ask) / 2
            iv = self.bs.implied_volatility(
                mid_price, option.underlying_price, option.strike,
                r, q, T, option.option_type,
            )

        S, K = option.underlying_price, option.strike
        d1, d2 = self.bs.calculate_d1_d2(S, K, r, q, iv, T)

        if option.option_type == "CALL":
            delta = np.exp(-q * T) * norm.cdf(d1)
            theta = self._calculate_call_theta(S, K, r, q, iv, T, d1, d2)
        else:
            delta = -np.exp(-q * T) * norm.cdf(-d1)
            theta = self._calculate_put_theta(S, K, r, q, iv, T, d1, d2)

        gamma = self._calculate_gamma(S, K, r, q, iv, T, d1)
        vega = self.bs.calculate_vega(S, K, r, q, iv, T)
        rho = self._calculate_rho(S, K, r, q, iv, T, d2, option.option_type)

        option_price = (option.bid + option.ask) / 2
        lambda_ = delta * S / option_price if option_price > 0 else 0.0

        vanna = self._calculate_vanna(S, K, r, q, iv, T, d1, d2)
        volga = self._calculate_volga(S, K, r, q, iv, T, d1)
        charm = self._calculate_charm(S, K, r, q, iv, T, d1, d2, option.option_type)
        veta = self._calculate_veta(S, K, r, q, iv, T, d1)

        result = Greeks(
            delta=delta, gamma=gamma, theta=theta, vega=vega, rho=rho,
            lambda_=lambda_, vanna=vanna, volga=volga, charm=charm, veta=veta,
        )
        self.cache.put(cache_key, result)
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _calculate_gamma(
        self, S: float, K: float, r: float, q: float, sigma: float, T: float, d1: float
    ) -> float:
        if T <= 0:
            return 0.0
        return np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))

    def _calculate_call_theta(
        self, S: float, K: float, r: float, q: float,
        sigma: float, T: float, d1: float, d2: float,
    ) -> float:
        if T <= 0:
            return 0.0
        t1 = -S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
        t2 = q * S * np.exp(-q * T) * norm.cdf(d1)
        t3 = -r * K * np.exp(-r * T) * norm.cdf(d2)
        return (t1 + t2 + t3) / DAYS_IN_YEAR

    def _calculate_put_theta(
        self, S: float, K: float, r: float, q: float,
        sigma: float, T: float, d1: float, d2: float,
    ) -> float:
        if T <= 0:
            return 0.0
        t1 = -S * np.exp(-q * T) * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
        t2 = -q * S * np.exp(-q * T) * norm.cdf(-d1)
        t3 = r * K * np.exp(-r * T) * norm.cdf(-d2)
        return (t1 + t2 + t3) / DAYS_IN_YEAR

    def _calculate_rho(
        self, S: float, K: float, r: float, q: float,
        sigma: float, T: float, d2: float, option_type: str,
    ) -> float:
        if T <= 0:
            return 0.0
        if option_type == "CALL":
            return K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        return -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100

    def _calculate_vanna(
        self, S: float, K: float, r: float, q: float,
        sigma: float, T: float, d1: float, d2: float,
    ) -> float:
        if T <= 0:
            return 0.0
        return -np.exp(-q * T) * norm.pdf(d1) * d2 / sigma / 100

    def _calculate_volga(
        self, S: float, K: float, r: float, q: float, sigma: float, T: float, d1: float
    ) -> float:
        if T <= 0:
            return 0.0
        d2 = d1 - sigma * np.sqrt(T)
        return S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T) * d1 * d2 / sigma / 10_000

    def _calculate_charm(
        self, S: float, K: float, r: float, q: float,
        sigma: float, T: float, d1: float, d2: float, option_type: str,
    ) -> float:
        if T <= 0:
            return 0.0
        t1 = -np.exp(-q * T) * norm.pdf(d1) * (2 * (r - q) * T - d2 * sigma * np.sqrt(T))
        t2 = 2 * sigma * T * np.sqrt(T)
        if option_type == "CALL":
            return (q * np.exp(-q * T) * norm.cdf(d1) - t1 / t2) / DAYS_IN_YEAR
        return (-q * np.exp(-q * T) * norm.cdf(-d1) - t1 / t2) / DAYS_IN_YEAR

    def _calculate_veta(
        self, S: float, K: float, r: float, q: float, sigma: float, T: float, d1: float
    ) -> float:
        if T <= 0:
            return 0.0
        d2 = d1 - sigma * np.sqrt(T)
        t1 = S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)
        t2 = q + (r - q) * d1 / (sigma * np.sqrt(T))
        t3 = (1 + d1 * d2) / (2 * T)
        return t1 * (t2 - t3) / DAYS_IN_YEAR / 100


# ==============================================================================
# VOLATILITY ANALYSIS
# ==============================================================================


class VolatilityAnalyzer:
    """Compute ATM IV, volatility skew, term structure, and regime classification
    from a list of :class:`OptionContract` objects.
    """

    def __init__(self) -> None:
        self.historical_data: dict[str, deque] = defaultdict(deque)
        self.max_history: int = DAYS_IN_YEAR * 2   # 2 years of daily observations

    def calculate_historical_volatility(
        self, prices: np.ndarray, window: int = VOLATILITY_WINDOW
    ) -> float:
        """Annualised close-to-close historical volatility.

        Args:
            prices: Array of closing prices (at least ``window + 1`` elements).
            window: Look-back window in trading days.

        Returns:
            Annualised historical volatility, or ``0.0`` when insufficient data.
        """
        if len(prices) < window + 1:
            return 0.0
        returns = np.diff(np.log(prices))[-window:]
        return float(np.std(returns) * np.sqrt(DAYS_IN_YEAR))

    def calculate_realized_volatility(
        self, prices: np.ndarray, timestamps: np.ndarray
    ) -> float:
        """Annualised realised volatility from high-frequency intraday data.

        Args:
            prices:     Array of tick or bar prices.
            timestamps: Corresponding Unix epoch timestamps.

        Returns:
            Annualised realised volatility, or ``0.0`` when insufficient data.
        """
        if len(prices) < 2:
            return 0.0
        returns = np.diff(np.log(prices))
        time_diffs = np.diff(timestamps)
        daily_factor = 86_400 / np.mean(time_diffs) if np.mean(time_diffs) > 0 else 1.0
        return float(np.sqrt(np.sum(returns**2) * daily_factor * DAYS_IN_YEAR))

    def calculate_volatility_metrics(
        self, option_chain: list[OptionContract], spot_price: float
    ) -> VolatilityMetrics:
        """Derive comprehensive volatility metrics from an options chain snapshot.

        Args:
            option_chain: List of options covering multiple strikes and expiries.
            spot_price:   Current spot price of the underlying.

        Returns:
            :class:`VolatilityMetrics` populated from the chain.
        """
        atm_options = self._find_atm_options(option_chain, spot_price)
        current_iv = self._calculate_atm_iv(atm_options)
        historical_vol = 0.20           # placeholder — production wires to price history
        iv_rank, iv_percentile = self._calculate_iv_statistics(current_iv)
        skew = self._calculate_skew(option_chain, spot_price)
        term_structure = self._calculate_term_structure(option_chain, spot_price)
        regime = self._classify_volatility_regime(current_iv)

        return VolatilityMetrics(
            current_iv=current_iv,
            historical_vol=historical_vol,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            realized_vol=historical_vol * 0.9,   # placeholder
            vol_of_vol=0.30,                      # placeholder
            skew=skew,
            term_structure=term_structure,
            regime=regime,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_atm_options(
        self, option_chain: list[OptionContract], spot_price: float
    ) -> list[OptionContract]:
        return [
            opt for opt in option_chain
            if 0.95 <= opt.strike / spot_price <= 1.05
        ]

    def _calculate_atm_iv(self, atm_options: list[OptionContract]) -> float:
        if not atm_options:
            return 0.20
        bs = BlackScholesCalculator()
        ivs = []
        for opt in atm_options:
            mid_price = (opt.bid + opt.ask) / 2
            T = (opt.expiry - date.today()).days / DAYS_IN_YEAR
            if T > 0 and mid_price > 0:
                iv = bs.implied_volatility(
                    mid_price, opt.underlying_price, opt.strike,
                    RISK_FREE_RATE, 0.0, T, opt.option_type,
                )
                if MIN_VOLATILITY <= iv <= MAX_VOLATILITY:
                    ivs.append(iv)
        return float(np.mean(ivs)) if ivs else 0.20

    def _calculate_skew(
        self, option_chain: list[OptionContract], spot_price: float
    ) -> float:
        put_ivs, call_ivs = [], []
        for opt in option_chain:
            moneyness = opt.strike / spot_price
            iv = self._get_option_iv(opt)
            if 0.90 <= moneyness <= 0.95 and opt.option_type == "PUT" and iv > 0:
                put_ivs.append(iv)
            elif 1.05 <= moneyness <= 1.10 and opt.option_type == "CALL" and iv > 0:
                call_ivs.append(iv)
        if put_ivs and call_ivs:
            return float(np.mean(put_ivs) - np.mean(call_ivs))
        return 0.0

    def _calculate_term_structure(
        self, option_chain: list[OptionContract], spot_price: float
    ) -> dict[float, float]:
        buckets: dict[float, list[float]] = defaultdict(list)
        for opt in option_chain:
            if not (0.95 <= opt.strike / spot_price <= 1.05):
                continue
            T = (opt.expiry - date.today()).days / DAYS_IN_YEAR
            iv = self._get_option_iv(opt)
            if T > 0 and iv > 0:
                bucket = round(T * 12) / 12      # monthly buckets
                buckets[bucket].append(iv)
        return {exp: float(np.mean(ivs)) for exp, ivs in sorted(buckets.items()) if ivs}

    def _get_option_iv(self, option: OptionContract) -> float:
        bs = BlackScholesCalculator()
        mid_price = (option.bid + option.ask) / 2
        T = (option.expiry - date.today()).days / DAYS_IN_YEAR
        if T > 0 and mid_price > 0:
            return bs.implied_volatility(
                mid_price, option.underlying_price, option.strike,
                RISK_FREE_RATE, 0.0, T, option.option_type,
            )
        return 0.0

    def _calculate_iv_statistics(self, current_iv: float) -> tuple[float, float]:
        # Placeholder — production wires to a trailing-year IV history store
        iv_rank = min(100.0, max(0.0, (current_iv - 0.10) / (0.40 - 0.10) * 100))
        return iv_rank, 50.0

    def _classify_volatility_regime(self, iv: float) -> str:
        for regime, (low, high) in VOLATILITY_REGIMES.items():
            if low <= iv < high:
                return regime
        return "UNKNOWN"


# ==============================================================================
# VOLATILITY SURFACE BUILDER
# ==============================================================================


class VolatilitySurfaceBuilder:
    """Build and smooth a 2-D implied volatility surface from an options chain.

    Uses cubic spline (or linear) interpolation to fill in missing strikes, then
    applies mild Gaussian smoothing to remove arbitrage artefacts.
    """

    def __init__(self) -> None:
        self.model = VolatilityModel.BLACK_SCHOLES
        self.bs = BlackScholesCalculator()

    def build_surface(
        self,
        option_chain: list[OptionContract],
        spot_price: float,
        risk_free_rate: float = RISK_FREE_RATE,
        dividend_yield: float = 0.0,
    ) -> VolatilitySurface:
        """Construct a :class:`VolatilitySurface` from an options chain.

        Args:
            option_chain:   List of :class:`OptionContract` objects.
            spot_price:     Current spot price of the underlying.
            risk_free_rate: Annual risk-free rate to use for IV inversion.
            dividend_yield: Continuous dividend yield for IV inversion.

        Returns:
            Smoothed :class:`VolatilitySurface` with interpolated IV grid.
        """
        surface_data: dict[float, dict[float, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for opt in option_chain:
            T = (opt.expiry - date.today()).days / DAYS_IN_YEAR
            if T <= 0:
                continue
            mid_price = (opt.bid + opt.ask) / 2
            if mid_price <= 0:
                continue
            iv = self.bs.implied_volatility(
                mid_price, spot_price, opt.strike,
                risk_free_rate, dividend_yield, T, opt.option_type,
            )
            if MIN_VOLATILITY <= iv <= MAX_VOLATILITY:
                surface_data[T][opt.strike].append(iv)

        expiries = sorted(surface_data)
        all_strikes: set[float] = set()
        for sd in surface_data.values():
            all_strikes.update(sd)
        strikes = sorted(all_strikes)

        ivs = np.zeros((len(expiries), len(strikes)))
        for i, T in enumerate(expiries):
            for j, K in enumerate(strikes):
                if K in surface_data[T]:
                    ivs[i, j] = np.mean(surface_data[T][K])
                else:
                    ivs[i, j] = self._interpolate_iv(surface_data[T], K, spot_price, T)

        ivs = self._smooth_surface(ivs)

        return VolatilitySurface(
            underlying="SPY",
            spot_price=spot_price,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            timestamp=time.time(),
            expiries=expiries,
            strikes=strikes,
            ivs=ivs,
            model_type=self.model,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _interpolate_iv(
        self,
        strike_iv_dict: dict[float, list[float]],
        target_strike: float,
        spot_price: float,
        T: float,
    ) -> float:
        if not strike_iv_dict:
            return 0.20
        sorted_strikes = sorted(strike_iv_dict)
        ivs = [float(np.mean(strike_iv_dict[K])) for K in sorted_strikes]
        if len(sorted_strikes) == 1:
            return ivs[0]
        if len(sorted_strikes) >= 4:
            f = interpolate.CubicSpline(sorted_strikes, ivs, extrapolate=True)
        else:
            f = interpolate.interp1d(sorted_strikes, ivs, kind="linear", fill_value="extrapolate")
        return float(np.clip(f(target_strike), MIN_VOLATILITY, MAX_VOLATILITY))

    def _smooth_surface(self, ivs: np.ndarray) -> np.ndarray:
        smoothed = gaussian_filter(ivs.copy(), sigma=0.5)
        return np.maximum(smoothed, MIN_VOLATILITY)
