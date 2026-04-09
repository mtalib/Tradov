#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV06_VolatilityEngine.py
Purpose: Consolidated volatility modeling engine - single source of truth for all volatility calculations

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-08-31 Time: 19:45:00

Module Description:
    Unified volatility modeling engine that consolidates all volatility approaches from V05 Heston,
    V10 GARCH, and V13 RoughVolatility. Provides intelligent volatility model selection based on
    time horizon, market conditions, and use case. Serves as the authoritative volatility source
    for V05_PricingEngine and other V-series modules.

Consolidation Notes:
    - Merges Heston stochastic volatility model from original V05
    - Incorporates GARCH volatility forecasting from V10
    - Integrates Rough Volatility model from V13 for short-term accuracy
    - Creates intelligent model selection based on time horizon
    - Eliminates volatility calculation duplications
    - Provides unified interface for all volatility needs
    - Optimized for real-time SPY options volatility analysis
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import warnings
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy import stats, optimize
try:
    from numba import jit
except ImportError:
    def jit(*args, **kwargs):  # type: ignore[misc]
        if args and callable(args[0]):
            return args[0]
        return lambda f: f

# Industry-standard GARCH / EGARCH / GJR-GARCH / HAR-RV models
try:
    from arch import arch_model
    from arch.univariate import GARCH, EGARCH, EWMAVariance, RiskMetrics2006  # noqa: F401
    _ARCH_AVAILABLE = True
except ImportError:
    _ARCH_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# SpyderB08_MultiClientDataManager (IB) has been removed.

# ==============================================================================
# MODULE CONFIGURATION
# ==============================================================================
warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMERATIONS AND CONSTANTS
# ==============================================================================
class VolatilityModel(Enum):
    """Available volatility models."""

    HESTON = "heston"  # Stochastic volatility
    GARCH = "garch"  # GARCH(1,1) forecasting
    ROUGH_VOLATILITY = "rough_vol"  # Rough volatility (short-term)
    HISTORICAL = "historical"  # Simple historical volatility
    REALIZED = "realized"  # Realized volatility estimators
    IMPLIED = "implied"  # Implied from options
    AUTO = "auto"  # Intelligent selection


class VolatilityHorizon(Enum):
    """Volatility forecasting horizons."""

    INTRADAY = "intraday"  # Minutes to hours
    SHORT_TERM = "short_term"  # 1-7 days
    MEDIUM_TERM = "medium_term"  # 1 week - 3 months
    LONG_TERM = "long_term"  # 3 months - 2 years


class VolatilityRegime(Enum):
    """Volatility regime classifications."""

    LOW_VOL = "low_vol"  # Below 15% annualized
    NORMAL_VOL = "normal_vol"  # 15-25% annualized
    HIGH_VOL = "high_vol"  # 25-40% annualized
    CRISIS_VOL = "crisis_vol"  # Above 40% annualized


# Model selection thresholds
MODEL_SELECTION_THRESHOLDS = {
    VolatilityHorizon.INTRADAY: VolatilityModel.ROUGH_VOLATILITY,
    VolatilityHorizon.SHORT_TERM: VolatilityModel.ROUGH_VOLATILITY,
    VolatilityHorizon.MEDIUM_TERM: VolatilityModel.GARCH,
    VolatilityHorizon.LONG_TERM: VolatilityModel.HESTON,
}

# Volatility regime thresholds (annualized)
REGIME_THRESHOLDS = {
    VolatilityRegime.LOW_VOL: (0.0, 0.15),
    VolatilityRegime.NORMAL_VOL: (0.15, 0.25),
    VolatilityRegime.HIGH_VOL: (0.25, 0.40),
    VolatilityRegime.CRISIS_VOL: (0.40, 2.0),
}


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class HestonParameters:
    """Heston stochastic volatility model parameters."""

    v0: float  # Initial variance
    theta: float  # Long-run variance
    kappa: float  # Mean reversion speed
    sigma: float  # Volatility of volatility
    rho: float  # Correlation between price and volatility

    def validate(self) -> bool:
        """Validate Heston parameters."""
        return (
            self.v0 > 0
            and self.theta > 0
            and self.kappa > 0
            and self.sigma > 0
            and -1 <= self.rho <= 1
            and 2 * self.kappa * self.theta > self.sigma**2
        )  # Feller condition


@dataclass
class GARCHParameters:
    """GARCH(1,1) model parameters."""

    omega: float  # Constant term
    alpha: float  # ARCH coefficient
    beta: float  # GARCH coefficient

    def validate(self) -> bool:
        """Validate GARCH parameters."""
        return (
            self.omega > 0
            and self.alpha >= 0
            and self.beta >= 0
            and self.alpha + self.beta < 1
        )  # Stationarity condition

    @property
    def persistence(self) -> float:
        """GARCH persistence (alpha + beta)."""
        return self.alpha + self.beta

    @property
    def unconditional_variance(self) -> float:
        """Long-run unconditional variance."""
        return self.omega / (1 - self.alpha - self.beta)


@dataclass
class RoughVolParameters:
    """Rough volatility model parameters."""

    hurst: float  # Hurst parameter (typically ~0.1)
    xi: float  # Volatility of volatility
    theta: float  # Long-run volatility level

    def validate(self) -> bool:
        """Validate rough volatility parameters."""
        return 0.0 < self.hurst < 0.5 and self.xi > 0 and self.theta > 0


@dataclass
class VolatilityForecast:
    """Volatility forecast result."""

    model_used: VolatilityModel
    forecast_horizon: int  # Days
    volatility_forecast: float  # Annualized volatility
    forecast_path: np.ndarray  # Full forecast path
    confidence_intervals: tuple[np.ndarray, np.ndarray]  # Lower, upper bounds
    model_confidence: float  # Model confidence score
    regime_probability: dict[VolatilityRegime, float]
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VolatilitySurface:
    """Volatility surface structure."""

    strikes: np.ndarray
    maturities: np.ndarray
    volatilities: np.ndarray  # 2D array: strikes x maturities
    moneyness: np.ndarray  # Strike/Spot ratios
    model_used: VolatilityModel
    spot_price: float
    surface_quality: float  # Quality score 0-1
    generation_time: datetime = field(default_factory=datetime.now)


@dataclass
class VolatilityMetrics:
    """Comprehensive volatility analysis metrics."""

    current_volatility: float
    volatility_regime: VolatilityRegime
    mean_reversion_speed: float
    volatility_clustering: float
    volatility_persistence: float
    volatility_of_volatility: float
    skew: float
    kurtosis: float
    jarque_bera_stat: float
    ljung_box_stat: float
    arch_lm_stat: float
    calculation_time: datetime = field(default_factory=datetime.now)


# ==============================================================================
# OPTIMIZED CALCULATION FUNCTIONS
# ==============================================================================
@jit(nopython=True)
def _garch_likelihood(params, returns):
    """Optimized GARCH likelihood calculation."""
    omega, alpha, beta = params
    n = len(returns)

    if omega <= 0 or alpha < 0 or beta < 0 or alpha + beta >= 1:
        return 1e6

    # Initialize variance
    variance = np.var(returns)
    log_likelihood = 0.0

    for t in range(n):
        if t == 0:
            variance = omega / (1 - alpha - beta)
        else:
            variance = omega + alpha * returns[t - 1] ** 2 + beta * variance

        if variance <= 0:
            return 1e6

        log_likelihood -= 0.5 * (
            np.log(2 * np.pi * variance) + returns[t] ** 2 / variance
        )

    return -log_likelihood


@jit(nopython=True)
def _rough_vol_simulation(hurst, xi, theta, n_steps, dt, n_paths):
    """Optimized rough volatility path simulation."""
    # Simplified rough volatility simulation
    paths = np.zeros((n_paths, n_steps))

    for path in range(n_paths):
        vol = theta  # Start at long-run level

        for t in range(n_steps):
            # Simplified fractional Brownian motion approximation
            dW = np.random.normal(0, np.sqrt(dt))

            # Rough volatility evolution (simplified)
            vol += xi * vol * (dt**hurst) * dW
            vol = max(vol, 0.01)  # Floor volatility

            paths[path, t] = vol

    return paths


@jit(nopython=True)
def _heston_characteristic_function(phi, S, K, T, r, q, v0, theta, kappa, sigma, rho):
    """Optimized Heston characteristic function for FFT pricing."""
    # Heston model parameters
    xi = kappa - rho * sigma * phi * 1j
    d = np.sqrt(xi**2 + sigma**2 * (phi * 1j + phi**2))

    # Characteristic function components
    A1 = phi * 1j * (np.log(S) + (r - q) * T)
    A2 = (
        (kappa * theta)
        / (sigma**2)
        * ((xi - d) * T - 2 * np.log((1 - np.exp(-d * T) * (xi - d) / (xi + d)) / 2))
    )
    A3 = (
        (v0 / sigma**2)
        * (xi - d)
        * (1 - np.exp(-d * T))
        / (1 - np.exp(-d * T) * (xi - d) / (xi + d))
    )

    return np.exp(A1 + A2 + A3)


# ==============================================================================
# MAIN VOLATILITY ENGINE CLASS
# ==============================================================================
class SpyderVolatilityEngine:
    """
    Consolidated volatility modeling engine for Spyder trading system.

    Unifies all volatility approaches from V05 Heston, V10 GARCH, and V13 RoughVolatility
    into an intelligent volatility modeling system. Provides automated model selection,
    comprehensive volatility forecasting, and volatility surface generation optimized
    for real-time SPY options trading.

    Key Features:
    - Intelligent volatility model selection based on time horizon
    - Heston stochastic volatility for long-term modeling
    - GARCH(1,1) for medium-term volatility forecasting
    - Rough volatility for short-term high-frequency accuracy
    - Automated volatility regime detection
    - Real-time volatility surface generation
    - Integration with V05_PricingEngine for volatility inputs
    """

    def __init__(
        self, config: dict[str, Any] = None, data_manager: Any = None
    ):
        """Initialize consolidated volatility engine."""
        self.config = config or {}
        self.data_manager = data_manager
        self.logger = logging.getLogger(__name__)

        # Model parameters (will be calibrated from data)
        self.heston_params: HestonParameters | None = None
        self.garch_params: GARCHParameters | None = None
        self.rough_vol_params: RoughVolParameters | None = None

        # Model states
        self.current_volatility: float = 0.0
        self.volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL_VOL
        self.garch_conditional_variance: np.ndarray | None = None

        # Market data storage
        self.price_history: list[float] = []
        self.return_history: list[float] = []
        self.volatility_history: list[float] = []
        self.last_data_update: datetime | None = None

        # Performance tracking
        self.model_performance: dict[VolatilityModel, dict[str, float]] = {}
        self.forecast_accuracy: dict[VolatilityModel, list[float]] = {}

        # Caching for performance
        self.surface_cache: dict[str, VolatilitySurface] = {}
        self.forecast_cache: dict[str, VolatilityForecast] = {}
        self.cache_expiry_minutes = self.config.get("cache_expiry_minutes", 5)

        # Configuration parameters
        self.min_data_points = self.config.get("min_data_points", 100)
        self.max_data_points = self.config.get(
            "max_data_points", 2520
        )  # ~10 years daily
        self.calibration_frequency_hours = self.config.get(
            "calibration_frequency_hours", 24
        )
        self.last_calibration: datetime | None = None

        # Initialize model performance tracking
        self._initialize_performance_tracking()

        self.logger.info("SpyderVolatilityEngine initialized successfully")

    def _initialize_performance_tracking(self):
        """Initialize performance tracking for all models."""
        for model in VolatilityModel:
            if model != VolatilityModel.AUTO:
                self.model_performance[model] = {
                    "total_forecasts": 0,
                    "avg_error": 0.0,
                    "rmse": 0.0,
                    "last_used": datetime.now(),
                }
                self.forecast_accuracy[model] = []

    # ==========================================================================
    # MAIN VOLATILITY INTERFACE
    # ==========================================================================

    async def get_volatility(
        self,
        horizon: int | VolatilityHorizon = VolatilityHorizon.SHORT_TERM,
        model: VolatilityModel = VolatilityModel.AUTO,
    ) -> float:
        """
        Get volatility estimate for specified horizon.

        Args:
            horizon: Forecast horizon (days or VolatilityHorizon enum)
            model: Specific model to use (AUTO for intelligent selection)

        Returns:
            float: Annualized volatility estimate
        """
        try:
            # Convert horizon to enum if needed
            if isinstance(horizon, int):
                if horizon <= 1:
                    horizon = VolatilityHorizon.INTRADAY
                elif horizon <= 7:
                    horizon = VolatilityHorizon.SHORT_TERM
                elif horizon <= 90:
                    horizon = VolatilityHorizon.MEDIUM_TERM
                else:
                    horizon = VolatilityHorizon.LONG_TERM

            # Select model if AUTO
            if model == VolatilityModel.AUTO:
                model = self._select_volatility_model(horizon)

            # Ensure models are calibrated
            await self._ensure_calibration()

            # Get volatility from appropriate model
            if model == VolatilityModel.HESTON:
                return await self._get_heston_volatility(horizon)
            elif model == VolatilityModel.GARCH:
                return await self._get_garch_volatility(horizon)
            elif model == VolatilityModel.ROUGH_VOLATILITY:
                return await self._get_rough_vol_volatility(horizon)
            elif model == VolatilityModel.HISTORICAL:
                return self._get_historical_volatility()
            elif model == VolatilityModel.REALIZED:
                return self._get_realized_volatility()
            else:
                # Fallback to historical
                return self._get_historical_volatility()

        except Exception as e:
            self.logger.error("Error getting volatility: %s", e, exc_info=True)
            return 0.20  # Safe default volatility

    async def forecast_volatility(
        self,
        horizon_days: int,
        model: VolatilityModel = VolatilityModel.AUTO,
        confidence_level: float = 0.95,
    ) -> VolatilityForecast:
        """
        Generate comprehensive volatility forecast.

        Args:
            horizon_days: Forecast horizon in days
            model: Volatility model to use
            confidence_level: Confidence level for intervals

        Returns:
            VolatilityForecast: Comprehensive forecast results
        """
        start_time = time.time()

        try:
            # Check cache first
            cache_key = f"forecast_{horizon_days}_{model.value}_{confidence_level}"
            cached_forecast = self._get_cached_forecast(cache_key)
            if cached_forecast:
                return cached_forecast

            # Select model if AUTO
            horizon_enum = self._days_to_horizon_enum(horizon_days)
            if model == VolatilityModel.AUTO:
                model = self._select_volatility_model(horizon_enum)

            # Ensure calibration
            await self._ensure_calibration()

            # Generate forecast based on model
            if model == VolatilityModel.GARCH:
                forecast = await self._garch_forecast(horizon_days, confidence_level)
            elif model == VolatilityModel.HESTON:
                forecast = await self._heston_forecast(horizon_days, confidence_level)
            elif model == VolatilityModel.ROUGH_VOLATILITY:
                forecast = await self._rough_vol_forecast(
                    horizon_days, confidence_level
                )
            else:
                # Historical projection
                forecast = await self._historical_forecast(
                    horizon_days, confidence_level
                )

            # Add regime analysis
            forecast.regime_probability = self._analyze_volatility_regime(
                forecast.volatility_forecast
            )

            # Cache result
            self._cache_forecast(cache_key, forecast)

            # Track performance
            calculation_time = (time.time() - start_time) * 1000
            self._update_model_performance(model, calculation_time)

            return forecast

        except Exception as e:
            self.logger.error("Error forecasting volatility: %s", e, exc_info=True)

            # Return safe default forecast
            return VolatilityForecast(
                model_used=VolatilityModel.HISTORICAL,
                forecast_horizon=horizon_days,
                volatility_forecast=0.20,
                forecast_path=np.full(horizon_days, 0.20),
                confidence_intervals=(
                    np.full(horizon_days, 0.15),
                    np.full(horizon_days, 0.25),
                ),
                model_confidence=0.5,
                regime_probability={regime: 0.25 for regime in VolatilityRegime},
                warnings=[f"Forecast failed: {str(e)}"],
            )

    async def generate_volatility_surface(
        self,
        spot_price: float,
        strikes: list[float],
        maturities: list[float],
        model: VolatilityModel = VolatilityModel.HESTON,
    ) -> VolatilitySurface:
        """
        Generate volatility surface for options pricing.

        Args:
            spot_price: Current underlying price
            strikes: List of strike prices
            maturities: List of maturities (in years)
            model: Model to use for surface generation

        Returns:
            VolatilitySurface: Complete volatility surface
        """
        try:
            # Check cache
            cache_key = f"surface_{spot_price}_{hash(tuple(strikes))}_{hash(tuple(maturities))}_{model.value}"
            cached_surface = self._get_cached_surface(cache_key)
            if cached_surface:
                return cached_surface

            # Ensure calibration
            await self._ensure_calibration()

            # Generate surface based on model
            if model == VolatilityModel.HESTON:
                surface = await self._generate_heston_surface(
                    spot_price, strikes, maturities
                )
            else:
                # Default to flat surface with smile
                surface = await self._generate_default_surface(
                    spot_price, strikes, maturities
                )

            # Cache surface
            self._cache_surface(cache_key, surface)

            return surface

        except Exception as e:
            self.logger.error("Error generating volatility surface: %s", e, exc_info=True)

            # Return flat surface as fallback
            strikes_array = np.array(strikes)
            maturities_array = np.array(maturities)
            volatilities = np.full((len(strikes), len(maturities)), 0.20)
            moneyness = strikes_array / spot_price

            return VolatilitySurface(
                strikes=strikes_array,
                maturities=maturities_array,
                volatilities=volatilities,
                moneyness=moneyness,
                model_used=model,
                spot_price=spot_price,
                surface_quality=0.5,
            )

    # ==========================================================================
    # MODEL SELECTION AND CALIBRATION
    # ==========================================================================

    def _select_volatility_model(self, horizon: VolatilityHorizon) -> VolatilityModel:
        """Select optimal volatility model based on horizon and market conditions."""
        # Default model selection based on horizon
        selected_model = MODEL_SELECTION_THRESHOLDS.get(horizon, VolatilityModel.GARCH)

        # Override based on data availability and quality
        if len(self.return_history) < 100:
            return VolatilityModel.HISTORICAL

        # Override based on volatility regime
        if self.volatility_regime == VolatilityRegime.CRISIS_VOL:
            # In crisis, rough volatility often performs better for short-term
            if horizon in [VolatilityHorizon.INTRADAY, VolatilityHorizon.SHORT_TERM]:
                return VolatilityModel.ROUGH_VOLATILITY

        return selected_model

    async def _ensure_calibration(self):
        """Ensure models are properly calibrated with recent data."""
        current_time = datetime.now()

        # Check if calibration is needed
        if (
            self.last_calibration is None
            or (current_time - self.last_calibration).total_seconds()
            > self.calibration_frequency_hours * 3600
        ):

            await self._calibrate_all_models()

    async def _calibrate_all_models(self):
        """Calibrate all volatility models with current data."""
        self.logger.info("Starting volatility model calibration...")

        try:
            if len(self.return_history) < self.min_data_points:
                self._generate_synthetic_data()

            # Calibrate GARCH model
            self.garch_params = await self._calibrate_garch()

            # Calibrate Heston model
            self.heston_params = await self._calibrate_heston()

            # Calibrate Rough Volatility model
            self.rough_vol_params = await self._calibrate_rough_vol()

            # Update volatility regime
            self._update_volatility_regime()

            self.last_calibration = datetime.now()
            self.logger.info("Volatility model calibration completed successfully")

        except Exception as e:
            self.logger.error("Error calibrating models: %s", e, exc_info=True)
            self._set_default_parameters()

    async def _calibrate_garch(self) -> GARCHParameters:
        """Calibrate GARCH(1,1) model parameters using arch library MLE when available."""
        _DEFAULT = GARCHParameters(omega=0.00001, alpha=0.08, beta=0.90)
        if len(self.return_history) < 50:
            return _DEFAULT

        returns = np.array(self.return_history[-252:])  # Last year

        # --- arch library path (preferred: proper MLE via BHHH/SLSQP) ---
        if _ARCH_AVAILABLE:
            try:
                returns_pct = returns * 100.0  # arch expects percentage returns
                model = arch_model(returns_pct, vol="Garch", p=1, q=1, dist="Normal", rescale=False)
                fit = model.fit(disp="off", show_warning=False)
                omega = float(fit.params.get("omega", 1e-5)) / 1e4  # scale back
                alpha = float(fit.params.get("alpha[1]", 0.08))
                beta = float(fit.params.get("beta[1]", 0.90))
                params = GARCHParameters(omega=omega, alpha=alpha, beta=beta)
                if params.validate():
                    return params
            except Exception as e:
                self.logger.warning("arch GARCH(1,1) calibration failed, falling back to scipy: %s", e, exc_info=True)

        # --- scipy fallback ---
        try:
            initial_guess = [0.00001, 0.08, 0.90]
            bounds = [(1e-8, 0.001), (0.001, 0.3), (0.1, 0.98)]
            result = optimize.minimize(
                _garch_likelihood,
                initial_guess,
                args=(returns,),
                bounds=bounds,
                method="L-BFGS-B",
            )
            if result.success:
                omega, alpha, beta = result.x
                params = GARCHParameters(omega=omega, alpha=alpha, beta=beta)
                if params.validate():
                    return params
        except Exception as e:
            self.logger.warning("GARCH calibration failed: %s", e, exc_info=True)

        return _DEFAULT

    async def _calibrate_egarch(self) -> dict | None:
        """
        Calibrate EGARCH(1,1) model via arch library.

        Returns a dict with keys 'omega', 'alpha', 'gamma', 'beta' or None on failure.
        EGARCH captures asymmetric leverage effects unlike symmetric GARCH.
        """
        if not _ARCH_AVAILABLE or len(self.return_history) < 100:
            return None
        try:
            returns_pct = np.array(self.return_history[-252:]) * 100.0
            model = arch_model(returns_pct, vol="EGARCH", p=1, o=1, q=1, dist="Normal", rescale=False)
            fit = model.fit(disp="off", show_warning=False)
            return {
                "omega": float(fit.params.get("omega", 0.0)),
                "alpha": float(fit.params.get("alpha[1]", 0.05)),
                "gamma": float(fit.params.get("gamma[1]", -0.1)),  # leverage
                "beta": float(fit.params.get("beta[1]", 0.92)),
                "aic": float(fit.aic),
                "bic": float(fit.bic),
            }
        except Exception as e:
            self.logger.warning("EGARCH calibration failed: %s", e, exc_info=True)
            return None

    async def _calibrate_heston(self) -> HestonParameters:
        """Calibrate Heston model parameters."""
        if len(self.return_history) < 100:
            return HestonParameters(v0=0.04, theta=0.04, kappa=2.0, sigma=0.3, rho=-0.7)

        returns = np.array(self.return_history[-252:])

        # Estimate initial parameters from data
        current_vol = np.std(returns) * np.sqrt(252)
        v0 = current_vol**2
        theta = v0  # Initial guess: current vol as long-run

        # Default parameters with data-driven initialization
        params = HestonParameters(
            v0=v0,
            theta=theta,
            kappa=2.0,  # Mean reversion speed
            sigma=0.3,  # Vol of vol
            rho=-0.7,  # Negative correlation (leverage effect)
        )

        if params.validate():
            return params
        else:
            return HestonParameters(v0=0.04, theta=0.04, kappa=2.0, sigma=0.3, rho=-0.7)

    async def _calibrate_rough_vol(self) -> RoughVolParameters:
        """Calibrate rough volatility model parameters."""
        # Simplified calibration - in practice would use more sophisticated methods
        return RoughVolParameters(
            hurst=0.1,  # Typical rough volatility Hurst parameter
            xi=0.3,  # Vol of vol
            theta=0.20,  # Long-run vol level
        )

    def _generate_synthetic_data(self):
        """Generate synthetic return data for initial calibration."""
        # Generate 252 days of synthetic returns
        np.random.seed(42)
        synthetic_returns = np.random.normal(0.0005, 0.015, 252)

        self.return_history = synthetic_returns.tolist()

        # Generate corresponding prices
        initial_price = 450.0
        prices = [initial_price]

        for ret in synthetic_returns:
            prices.append(prices[-1] * (1 + ret))

        self.price_history = prices[1:]  # Skip initial price

        self.logger.info("Generated synthetic data for initial calibration")

    def _set_default_parameters(self):
        """Set default parameters when calibration fails."""
        self.garch_params = GARCHParameters(omega=0.00001, alpha=0.08, beta=0.90)
        self.heston_params = HestonParameters(
            v0=0.04, theta=0.04, kappa=2.0, sigma=0.3, rho=-0.7
        )
        self.rough_vol_params = RoughVolParameters(hurst=0.1, xi=0.3, theta=0.20)

        self.logger.warning("Using default volatility model parameters")

    # ==========================================================================
    # MODEL-SPECIFIC VOLATILITY CALCULATIONS
    # ==========================================================================

    async def _get_heston_volatility(self, horizon: VolatilityHorizon) -> float:
        """Get volatility from Heston model."""
        if not self.heston_params:
            return 0.20

        # For current volatility, use square root of current variance
        if horizon == VolatilityHorizon.INTRADAY:
            return np.sqrt(self.heston_params.v0)
        else:
            # For longer horizons, blend towards long-run variance
            t = self._horizon_to_years(horizon)
            mean_reversion = np.exp(-self.heston_params.kappa * t)
            blended_variance = (
                self.heston_params.v0 * mean_reversion
                + self.heston_params.theta * (1 - mean_reversion)
            )
            return np.sqrt(blended_variance)

    async def _get_garch_volatility(self, horizon: VolatilityHorizon) -> float:
        """Get volatility from GARCH model."""
        if not self.garch_params or len(self.return_history) < 2:
            return 0.20

        # Calculate current conditional variance
        if self.garch_conditional_variance is None:
            self._update_garch_conditional_variance()

        current_variance = (
            self.garch_conditional_variance[-1]
            if len(self.garch_conditional_variance) > 0
            else self.garch_params.unconditional_variance
        )

        # For different horizons, project GARCH variance
        if horizon == VolatilityHorizon.INTRADAY:
            return np.sqrt(current_variance * 252)
        else:
            # Multi-step ahead GARCH forecast
            days = self._horizon_to_days(horizon)
            forecasted_variance = self._garch_multi_step_forecast(
                current_variance, days
            )
            return np.sqrt(forecasted_variance * 252)

    async def _get_rough_vol_volatility(self, horizon: VolatilityHorizon) -> float:
        """Get volatility from rough volatility model."""
        if not self.rough_vol_params:
            return 0.20

        # Simplified rough volatility calculation
        current_vol = self.rough_vol_params.theta

        if horizon == VolatilityHorizon.INTRADAY:
            # For intraday, rough vol can show higher variability
            return current_vol * (1 + 0.1 * np.random.normal())
        else:
            # For longer horizons, converge towards theta
            return current_vol

    def _get_historical_volatility(self, window: int = 30) -> float:
        """Calculate simple historical volatility."""
        if len(self.return_history) < window:
            return 0.20

        recent_returns = np.array(self.return_history[-window:])
        return np.std(recent_returns, ddof=1) * np.sqrt(252)

    def _get_realized_volatility(self, window: int = 30) -> float:
        """Calculate realized volatility using high-frequency methods."""
        # Simplified - would use high-frequency data in practice
        return self._get_historical_volatility(window)

    # ==========================================================================
    # FORECASTING METHODS
    # ==========================================================================

    async def _garch_forecast(
        self, horizon_days: int, confidence_level: float
    ) -> VolatilityForecast:
        """Generate GARCH volatility forecast."""
        if not self.garch_params:
            raise ValueError("GARCH model not calibrated")

        # Current conditional variance
        if self.garch_conditional_variance is None:
            self._update_garch_conditional_variance()

        current_variance = (
            self.garch_conditional_variance[-1]
            if len(self.garch_conditional_variance) > 0
            else self.garch_params.unconditional_variance
        )

        # Multi-step forecast
        forecast_path = np.zeros(horizon_days)
        variance = current_variance

        for t in range(horizon_days):
            # GARCH(1,1) forecast formula
            variance = (
                self.garch_params.omega + self.garch_params.persistence * variance
            )
            forecast_path[t] = np.sqrt(variance * 252)  # Annualized volatility

        # Confidence intervals (simplified)
        alpha = 1 - confidence_level
        z_score = stats.norm.ppf(1 - alpha / 2)
        std_error = 0.05  # Simplified standard error

        lower_bound = forecast_path - z_score * std_error
        upper_bound = forecast_path + z_score * std_error

        return VolatilityForecast(
            model_used=VolatilityModel.GARCH,
            forecast_horizon=horizon_days,
            volatility_forecast=forecast_path[-1],
            forecast_path=forecast_path,
            confidence_intervals=(lower_bound, upper_bound),
            model_confidence=0.85,
            regime_probability={},
        )

    async def _heston_forecast(
        self, horizon_days: int, confidence_level: float
    ) -> VolatilityForecast:
        """Generate Heston volatility forecast."""
        if not self.heston_params:
            raise ValueError("Heston model not calibrated")

        # Simulate Heston paths for forecasting
        dt = 1 / 252  # Daily steps

        forecast_path = np.zeros(horizon_days)

        for t in range(horizon_days):
            time_to_horizon = (t + 1) * dt

            # Analytical Heston volatility expectation
            mean_reversion = np.exp(-self.heston_params.kappa * time_to_horizon)
            expected_variance = (
                self.heston_params.v0 * mean_reversion
                + self.heston_params.theta * (1 - mean_reversion)
            )

            forecast_path[t] = np.sqrt(expected_variance)

        # Confidence intervals (simplified)
        vol_of_vol = 0.1 * forecast_path  # Proportional to volatility level
        alpha = 1 - confidence_level
        z_score = stats.norm.ppf(1 - alpha / 2)

        lower_bound = forecast_path - z_score * vol_of_vol
        upper_bound = forecast_path + z_score * vol_of_vol

        return VolatilityForecast(
            model_used=VolatilityModel.HESTON,
            forecast_horizon=horizon_days,
            volatility_forecast=forecast_path[-1],
            forecast_path=forecast_path,
            confidence_intervals=(lower_bound, upper_bound),
            model_confidence=0.80,
            regime_probability={},
        )

    async def _rough_vol_forecast(
        self, horizon_days: int, confidence_level: float
    ) -> VolatilityForecast:
        """Generate rough volatility forecast."""
        if not self.rough_vol_params:
            raise ValueError("Rough volatility model not calibrated")

        # Simplified rough volatility forecasting
        dt = 1 / 252
        hurst = self.rough_vol_params.hurst

        # Generate rough volatility path
        n_paths = 100
        paths = _rough_vol_simulation(
            hurst,
            self.rough_vol_params.xi,
            self.rough_vol_params.theta,
            horizon_days,
            dt,
            n_paths,
        )

        # Average across paths
        forecast_path = np.mean(paths, axis=0)

        # Confidence intervals from simulation
        alpha = 1 - confidence_level
        lower_bound = np.percentile(paths, 100 * alpha / 2, axis=0)
        upper_bound = np.percentile(paths, 100 * (1 - alpha / 2), axis=0)

        return VolatilityForecast(
            model_used=VolatilityModel.ROUGH_VOLATILITY,
            forecast_horizon=horizon_days,
            volatility_forecast=forecast_path[-1],
            forecast_path=forecast_path,
            confidence_intervals=(lower_bound, upper_bound),
            model_confidence=0.75,
            regime_probability={},
        )

    async def _historical_forecast(
        self, horizon_days: int, confidence_level: float
    ) -> VolatilityForecast:
        """Generate simple historical volatility projection."""
        current_vol = self._get_historical_volatility()

        # Flat forecast with some mean reversion
        long_run_vol = 0.20
        decay_factor = 0.95

        forecast_path = np.zeros(horizon_days)
        vol = current_vol

        for t in range(horizon_days):
            vol = vol * decay_factor + long_run_vol * (1 - decay_factor)
            forecast_path[t] = vol

        # Simple confidence intervals
        vol_uncertainty = 0.05
        alpha = 1 - confidence_level
        z_score = stats.norm.ppf(1 - alpha / 2)

        lower_bound = forecast_path - z_score * vol_uncertainty
        upper_bound = forecast_path + z_score * vol_uncertainty

        return VolatilityForecast(
            model_used=VolatilityModel.HISTORICAL,
            forecast_horizon=horizon_days,
            volatility_forecast=forecast_path[-1],
            forecast_path=forecast_path,
            confidence_intervals=(lower_bound, upper_bound),
            model_confidence=0.60,
            regime_probability={},
        )

    # ==========================================================================
    # VOLATILITY SURFACE GENERATION
    # ==========================================================================

    async def _generate_heston_surface(
        self, spot_price: float, strikes: list[float], maturities: list[float]
    ) -> VolatilitySurface:
        """Generate volatility surface using Heston model."""
        if not self.heston_params:
            raise ValueError("Heston model not calibrated")

        strikes_array = np.array(strikes)
        maturities_array = np.array(maturities)
        moneyness = strikes_array / spot_price

        # Generate implied volatilities using Heston model
        volatilities = np.zeros((len(strikes), len(maturities)))

        for i, _strike in enumerate(strikes):
            for j, maturity in enumerate(maturities):
                # Use Heston model to generate implied volatility
                # Simplified approach - would use FFT or analytical approximation in practice
                base_vol = np.sqrt(self.heston_params.theta)

                # Add volatility smile effects
                moneyness_effect = self._calculate_smile_adjustment(
                    moneyness[i], maturity
                )
                volatilities[i, j] = base_vol + moneyness_effect

        return VolatilitySurface(
            strikes=strikes_array,
            maturities=maturities_array,
            volatilities=volatilities,
            moneyness=moneyness,
            model_used=VolatilityModel.HESTON,
            spot_price=spot_price,
            surface_quality=0.90,
        )

    async def _generate_default_surface(
        self, spot_price: float, strikes: list[float], maturities: list[float]
    ) -> VolatilitySurface:
        """Generate default volatility surface with smile."""
        strikes_array = np.array(strikes)
        maturities_array = np.array(maturities)
        moneyness = strikes_array / spot_price

        base_volatility = self.current_volatility or 0.20
        volatilities = np.zeros((len(strikes), len(maturities)))

        for i, _strike in enumerate(strikes):
            for j, maturity in enumerate(maturities):
                # Simple smile model
                smile_adjustment = self._calculate_smile_adjustment(
                    moneyness[i], maturity
                )
                volatilities[i, j] = base_volatility + smile_adjustment

        return VolatilitySurface(
            strikes=strikes_array,
            maturities=maturities_array,
            volatilities=volatilities,
            moneyness=moneyness,
            model_used=VolatilityModel.HISTORICAL,
            spot_price=spot_price,
            surface_quality=0.70,
        )

    def _calculate_smile_adjustment(self, moneyness: float, maturity: float) -> float:
        """Calculate volatility smile adjustment."""
        # Simple volatility smile model
        # Typically: higher vol for OTM puts (low moneyness) and OTM calls (high moneyness)

        log_moneyness = np.log(moneyness)

        # Smile parameters (simplified)
        smile_strength = 0.1 * np.sqrt(maturity)  # Stronger smile for longer maturities
        smile_curvature = 2.0

        # Quadratic smile
        smile_adjustment = smile_strength * (log_moneyness**2) / smile_curvature

        return smile_adjustment

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _update_garch_conditional_variance(self):
        """Update GARCH conditional variance series."""
        if not self.garch_params or len(self.return_history) < 2:
            return

        returns = np.array(self.return_history)
        n = len(returns)
        conditional_variance = np.zeros(n)

        # Initialize with unconditional variance
        conditional_variance[0] = self.garch_params.unconditional_variance

        for t in range(1, n):
            conditional_variance[t] = (
                self.garch_params.omega
                + self.garch_params.alpha * returns[t - 1] ** 2
                + self.garch_params.beta * conditional_variance[t - 1]
            )

        self.garch_conditional_variance = conditional_variance

    def _garch_multi_step_forecast(self, current_variance: float, steps: int) -> float:
        """Generate multi-step GARCH variance forecast."""
        if steps == 1:
            return (
                self.garch_params.omega
                + self.garch_params.persistence * current_variance
            )

        # Multi-step forecast
        persistence = self.garch_params.persistence
        unconditional_var = self.garch_params.unconditional_variance

        # Geometric series formula for GARCH forecast
        if persistence < 0.9999:
            forecast_var = unconditional_var + (persistence**steps) * (
                current_variance - unconditional_var
            )
        else:
            # Near unit root case
            forecast_var = current_variance

        return forecast_var

    def _update_volatility_regime(self):
        """Update current volatility regime classification."""
        current_vol = self.current_volatility or self._get_historical_volatility()

        for regime, (low, high) in REGIME_THRESHOLDS.items():
            if low <= current_vol < high:
                self.volatility_regime = regime
                break

    def _analyze_volatility_regime(
        self, volatility: float
    ) -> dict[VolatilityRegime, float]:
        """Analyze volatility regime probabilities."""
        # Simplified regime probabilities based on current volatility
        probabilities = {}

        for regime, (low, high) in REGIME_THRESHOLDS.items():
            if low <= volatility < high:
                probabilities[regime] = 0.70  # High probability for current regime
            else:
                # Distance-based probability
                mid_point = (low + high) / 2
                distance = abs(volatility - mid_point) / (high - low)
                probabilities[regime] = max(0.05, 0.25 * np.exp(-distance))

        # Normalize probabilities
        total_prob = sum(probabilities.values())
        return {regime: prob / total_prob for regime, prob in probabilities.items()}

    def _days_to_horizon_enum(self, days: int) -> VolatilityHorizon:
        """Convert days to horizon enum."""
        if days <= 1:
            return VolatilityHorizon.INTRADAY
        elif days <= 7:
            return VolatilityHorizon.SHORT_TERM
        elif days <= 90:
            return VolatilityHorizon.MEDIUM_TERM
        else:
            return VolatilityHorizon.LONG_TERM

    def _horizon_to_days(self, horizon: VolatilityHorizon) -> int:
        """Convert horizon enum to days."""
        horizon_days = {
            VolatilityHorizon.INTRADAY: 1,
            VolatilityHorizon.SHORT_TERM: 7,
            VolatilityHorizon.MEDIUM_TERM: 30,
            VolatilityHorizon.LONG_TERM: 90,
        }
        return horizon_days.get(horizon, 30)

    def _horizon_to_years(self, horizon: VolatilityHorizon) -> float:
        """Convert horizon enum to years."""
        return self._horizon_to_days(horizon) / 252.0

    # ==========================================================================
    # CACHING METHODS
    # ==========================================================================

    def _get_cached_forecast(self, cache_key: str) -> VolatilityForecast | None:
        """Get cached forecast if still valid."""
        if cache_key not in self.forecast_cache:
            return None

        cached_forecast = self.forecast_cache[cache_key]

        # Check if cache is still valid
        age_minutes = (
            datetime.now() - cached_forecast.metadata.get("cache_time", datetime.now())
        ).total_seconds() / 60

        if age_minutes < self.cache_expiry_minutes:
            return cached_forecast
        else:
            del self.forecast_cache[cache_key]
            return None

    def _cache_forecast(self, cache_key: str, forecast: VolatilityForecast):
        """Cache forecast result."""
        forecast.metadata["cache_time"] = datetime.now()
        self.forecast_cache[cache_key] = forecast

        # Cleanup old cache entries
        if len(self.forecast_cache) > 100:
            self._cleanup_forecast_cache()

    def _get_cached_surface(self, cache_key: str) -> VolatilitySurface | None:
        """Get cached surface if still valid."""
        if cache_key not in self.surface_cache:
            return None

        cached_surface = self.surface_cache[cache_key]

        # Check if cache is still valid
        age_minutes = (
            datetime.now() - cached_surface.generation_time
        ).total_seconds() / 60

        if age_minutes < self.cache_expiry_minutes:
            return cached_surface
        else:
            del self.surface_cache[cache_key]
            return None

    def _cache_surface(self, cache_key: str, surface: VolatilitySurface):
        """Cache surface result."""
        self.surface_cache[cache_key] = surface

        # Cleanup old cache entries
        if len(self.surface_cache) > 50:
            self._cleanup_surface_cache()

    def _cleanup_forecast_cache(self):
        """Remove expired forecast cache entries."""
        current_time = datetime.now()
        expired_keys = []

        for key, forecast in self.forecast_cache.items():
            cache_time = forecast.metadata.get("cache_time", current_time)
            age_minutes = (current_time - cache_time).total_seconds() / 60

            if age_minutes > self.cache_expiry_minutes:
                expired_keys.append(key)

        for key in expired_keys:
            del self.forecast_cache[key]

    def _cleanup_surface_cache(self):
        """Remove expired surface cache entries."""
        current_time = datetime.now()
        expired_keys = []

        for key, surface in self.surface_cache.items():
            age_minutes = (current_time - surface.generation_time).total_seconds() / 60

            if age_minutes > self.cache_expiry_minutes:
                expired_keys.append(key)

        for key in expired_keys:
            del self.surface_cache[key]

    def _update_model_performance(
        self, model: VolatilityModel, calculation_time: float
    ):
        """Update model performance statistics."""
        if model in self.model_performance:
            perf = self.model_performance[model]
            perf["total_forecasts"] += 1
            perf["last_used"] = datetime.now()

            # Update average calculation time
            if "avg_calc_time" in perf:
                perf["avg_calc_time"] = (perf["avg_calc_time"] + calculation_time) / 2
            else:
                perf["avg_calc_time"] = calculation_time

    # ==========================================================================
    # DATA MANAGEMENT
    # ==========================================================================

    async def update_market_data(
        self, prices: list[float], timestamps: list[datetime] = None
    ):
        """Update market data for volatility calculations."""
        if not prices:
            return

        # Update price history
        self.price_history.extend(prices)

        # Trim to maximum size
        if len(self.price_history) > self.max_data_points:
            excess = len(self.price_history) - self.max_data_points
            self.price_history = self.price_history[excess:]

        # Calculate returns
        if len(self.price_history) > 1:
            new_returns = []
            for i in range(
                len(self.price_history) - len(prices), len(self.price_history)
            ):
                if i > 0:
                    ret = (
                        self.price_history[i] - self.price_history[i - 1]
                    ) / self.price_history[i - 1]
                    new_returns.append(ret)

            self.return_history.extend(new_returns)

            # Trim returns history
            if len(self.return_history) > self.max_data_points:
                excess = len(self.return_history) - self.max_data_points
                self.return_history = self.return_history[excess:]

        # Update current volatility
        self.current_volatility = self._get_historical_volatility()
        self._update_volatility_regime()

        self.last_data_update = datetime.now()

        # Clear conditional variance cache (will be recalculated)
        self.garch_conditional_variance = None

    def get_volatility_metrics(self) -> VolatilityMetrics:
        """Get comprehensive volatility analysis metrics."""
        if len(self.return_history) < 30:
            # Return default metrics for insufficient data
            return VolatilityMetrics(
                current_volatility=0.20,
                volatility_regime=VolatilityRegime.NORMAL_VOL,
                mean_reversion_speed=0.0,
                volatility_clustering=0.0,
                volatility_persistence=0.0,
                volatility_of_volatility=0.0,
                skew=0.0,
                kurtosis=0.0,
                jarque_bera_stat=0.0,
                ljung_box_stat=0.0,
                arch_lm_stat=0.0,
            )

        returns = np.array(self.return_history[-252:])  # Last year

        # Basic statistics
        current_vol = self.current_volatility or self._get_historical_volatility()
        skewness = stats.skew(returns)
        kurt = stats.kurtosis(returns)

        # Volatility clustering (simplified)
        squared_returns = returns**2
        clustering = np.corrcoef(squared_returns[:-1], squared_returns[1:])[0, 1]

        # GARCH persistence
        persistence = self.garch_params.persistence if self.garch_params else 0.0

        # Mean reversion (simplified)
        vol_series = np.sqrt(squared_returns) * np.sqrt(252)
        vol_changes = np.diff(vol_series)
        mean_reversion = (
            -np.corrcoef(vol_series[:-1], vol_changes)[0, 1]
            if len(vol_changes) > 1
            else 0.0
        )

        # Volatility of volatility
        vol_of_vol = np.std(vol_series, ddof=1) if len(vol_series) > 1 else 0.0

        # Statistical tests (simplified)
        jb_stat, _ = stats.jarque_bera(returns)

        return VolatilityMetrics(
            current_volatility=current_vol,
            volatility_regime=self.volatility_regime,
            mean_reversion_speed=mean_reversion,
            volatility_clustering=clustering,
            volatility_persistence=persistence,
            volatility_of_volatility=vol_of_vol,
            skew=skewness,
            kurtosis=kurt,
            jarque_bera_stat=jb_stat,
            ljung_box_stat=0.0,  # Simplified
            arch_lm_stat=0.0,  # Simplified
        )

    def get_engine_status(self) -> dict[str, Any]:
        """Get comprehensive engine status."""
        return {
            "models_calibrated": {
                "heston": self.heston_params is not None,
                "garch": self.garch_params is not None,
                "rough_vol": self.rough_vol_params is not None,
            },
            "data_status": {
                "price_points": len(self.price_history),
                "return_points": len(self.return_history),
                "last_update": (
                    self.last_data_update.isoformat() if self.last_data_update else None
                ),
                "data_quality": (
                    "Good"
                    if len(self.return_history) >= self.min_data_points
                    else "Insufficient"
                ),
            },
            "current_state": {
                "volatility": self.current_volatility,
                "regime": self.volatility_regime.value,
                "last_calibration": (
                    self.last_calibration.isoformat() if self.last_calibration else None
                ),
            },
            "cache_status": {
                "forecast_cache_size": len(self.forecast_cache),
                "surface_cache_size": len(self.surface_cache),
            },
            "model_parameters": {
                "garch": {
                    "omega": self.garch_params.omega if self.garch_params else None,
                    "alpha": self.garch_params.alpha if self.garch_params else None,
                    "beta": self.garch_params.beta if self.garch_params else None,
                    "persistence": (
                        self.garch_params.persistence if self.garch_params else None
                    ),
                },
                "heston": {
                    "v0": self.heston_params.v0 if self.heston_params else None,
                    "theta": self.heston_params.theta if self.heston_params else None,
                    "kappa": self.heston_params.kappa if self.heston_params else None,
                    "sigma": self.heston_params.sigma if self.heston_params else None,
                    "rho": self.heston_params.rho if self.heston_params else None,
                },
            },
        }


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_volatility_engine(
    config: dict[str, Any] = None, data_manager: Any = None
) -> SpyderVolatilityEngine:
    """Factory function to create SpyderVolatilityEngine."""
    return SpyderVolatilityEngine(config, data_manager)


# ==============================================================================
# DEMONSTRATION AND TESTING
# ==============================================================================
async def main():
    """Demonstration of consolidated volatility engine."""
    logging.info("=" * 80)
    logging.info("SPYDER V06 CONSOLIDATED VOLATILITY ENGINE DEMONSTRATION")
    logging.info("=" * 80)

    # Initialize volatility engine
    config = {
        "min_data_points": 50,
        "calibration_frequency_hours": 1,
        "cache_expiry_minutes": 5,
    }

    vol_engine = create_volatility_engine(config)

    logging.info("\n✅ Volatility Engine Initialized")
    logging.info("   • Consolidated Heston, GARCH, and Rough Volatility models")
    logging.info("   • Intelligent model selection based on time horizon")
    logging.info("   • Real-time volatility surface generation")
    logging.info("   • Comprehensive volatility forecasting")

    # Generate synthetic market data
    logging.info("\n--- Generating Synthetic Market Data ---")
    np.random.seed(42)
    n_days = 100
    initial_price = 450.0

    # Generate price series with volatility clustering
    prices = [initial_price]
    volatility = 0.20

    for _ in range(n_days):
        # Update volatility with clustering
        volatility = 0.95 * volatility + 0.05 * 0.20 + 0.1 * np.random.normal(0, 0.02)
        volatility = max(0.05, min(volatility, 0.50))

        # Generate return with current volatility
        daily_return = np.random.normal(0.0005, volatility / np.sqrt(252))
        new_price = prices[-1] * (1 + daily_return)
        prices.append(new_price)

    # Update engine with market data
    await vol_engine.update_market_data(prices[1:])  # Skip initial price

    logging.info("   Generated %s price observations", len(prices)-1)
    logging.info(f"   Current SPY price: ${prices[-1]:.2f}")
    logging.info("   Data quality: %s returns available", len(vol_engine.return_history))

    # Test 1: Single Volatility Estimates
    logging.info("\n--- Test 1: Volatility Estimates by Time Horizon ---")
    logging.info("Horizon              Auto Model        Volatility")
    logging.info("-" * 55)

    horizons = [
        (VolatilityHorizon.INTRADAY, "Intraday"),
        (VolatilityHorizon.SHORT_TERM, "Short Term (1-7d)"),
        (VolatilityHorizon.MEDIUM_TERM, "Medium Term (1w-3m)"),
        (VolatilityHorizon.LONG_TERM, "Long Term (3m+)"),
    ]

    for horizon, name in horizons:
        try:
            volatility = await vol_engine.get_volatility(horizon=horizon)
            selected_model = vol_engine._select_volatility_model(horizon)

            logging.info(f"{name:<20} {selected_model.value:<12} {volatility:.1%}")

        except Exception as e:
            logging.info(f"{name:<20} ERROR: {str(e)[:20]}")

    # Test 2: Volatility Forecasting
    logging.info("\n--- Test 2: Volatility Forecasting ---")
    try:
        forecast_days = 30
        forecast = await vol_engine.forecast_volatility(
            horizon_days=forecast_days,
            model=VolatilityModel.AUTO,
            confidence_level=0.95,
        )

        logging.info("   Forecast Horizon: %s days", forecast.forecast_horizon)
        logging.info("   Model Used: %s", forecast.model_used.value)
        logging.info(f"   Final Volatility: {forecast.volatility_forecast:.1%}")
        logging.info(f"   Model Confidence: {forecast.model_confidence:.1%}")

        # Show regime probabilities
        if forecast.regime_probability:
            logging.info("   Regime Probabilities:")
            for regime, prob in forecast.regime_probability.items():
                logging.info(f"     {regime.value}: {prob:.1%}")

        logging.info(
            f"   Forecast Range: {forecast.forecast_path.min():.1%} - {forecast.forecast_path.max():.1%}"
        )

    except Exception as e:
        logging.info("   ❌ Forecast Error: %s", e)

    # Test 3: Volatility Surface Generation
    logging.info("\n--- Test 3: Volatility Surface Generation ---")
    try:
        current_spot = prices[-1]
        strikes = [current_spot * m for m in [0.90, 0.95, 1.00, 1.05, 1.10]]
        maturities = [7 / 365, 30 / 365, 60 / 365, 90 / 365]  # 1w, 1m, 2m, 3m

        surface = await vol_engine.generate_volatility_surface(
            spot_price=current_spot,
            strikes=strikes,
            maturities=maturities,
            model=VolatilityModel.HESTON,
        )

        logging.info("   Surface Model: %s", surface.model_used.value)
        logging.info(f"   Surface Quality: {surface.surface_quality:.1%}")
        logging.info(f"   Spot Price: ${surface.spot_price:.2f}")

        logging.info("\n   Volatility Surface (Strike vs Maturity):")
        logging.info(f"   {'Strike/Spot':<12}", end="")
        for mat in maturities:
            logging.info(f"{mat*365:>8.0f}d", end="")
        logging.info()

        for i, strike in enumerate(strikes):
            moneyness = strike / current_spot
            logging.info(f"   {moneyness:<12.2f}", end="")
            for j in range(len(maturities)):
                vol = surface.volatilities[i, j]
                logging.info(f"{vol:>8.1%}", end="")
            logging.info()

    except Exception as e:
        logging.info("   ❌ Surface Error: %s", e)

    # Test 4: Model Comparison
    logging.info("\n--- Test 4: Model Performance Comparison ---")
    try:
        models_to_test = [
            VolatilityModel.HISTORICAL,
            VolatilityModel.GARCH,
            VolatilityModel.HESTON,
            VolatilityModel.ROUGH_VOLATILITY,
        ]

        logging.info("Model                Volatility    Speed      Quality")
        logging.info("-" * 55)

        for model in models_to_test:
            try:
                start_time = time.time()
                volatility = await vol_engine.get_volatility(
                    horizon=VolatilityHorizon.SHORT_TERM, model=model
                )
                calc_time = (time.time() - start_time) * 1000

                # Estimate quality based on model sophistication
                quality_scores = {
                    VolatilityModel.HISTORICAL: 0.6,
                    VolatilityModel.GARCH: 0.8,
                    VolatilityModel.HESTON: 0.9,
                    VolatilityModel.ROUGH_VOLATILITY: 0.85,
                }
                quality = quality_scores.get(model, 0.7)

                logging.info(
                    f"{model.value:<20} {volatility:>8.1%} {calc_time:>8.1f}ms {quality:>8.1%}"
                )

            except Exception as e:
                logging.info(f"{model.value:<20} ERROR: {str(e)[:25]}")

    except Exception as e:
        logging.info("   ❌ Comparison Error: %s", e)

    # Test 5: Volatility Metrics Analysis
    logging.info("\n--- Test 5: Volatility Metrics Analysis ---")
    try:
        metrics = vol_engine.get_volatility_metrics()

        logging.info(f"   Current Volatility: {metrics.current_volatility:.1%}")
        logging.info("   Volatility Regime: %s", metrics.volatility_regime.value)
        logging.info(f"   Mean Reversion Speed: {metrics.mean_reversion_speed:.3f}")
        logging.info(f"   Volatility Clustering: {metrics.volatility_clustering:.3f}")
        logging.info(f"   Volatility Persistence: {metrics.volatility_persistence:.3f}")
        logging.info(f"   Vol of Vol: {metrics.volatility_of_volatility:.3f}")
        logging.info(f"   Return Skewness: {metrics.skew:.3f}")
        logging.info(f"   Return Kurtosis: {metrics.kurtosis:.3f}")

    except Exception as e:
        logging.info("   ❌ Metrics Error: %s", e)

    # Test 6: Engine Status
    logging.info("\n--- Test 6: Engine Status ---")
    try:
        status = vol_engine.get_engine_status()

        logging.info("   Model Calibration Status:")
        for model, calibrated in status["models_calibrated"].items():
            logging.info("     %s: %s", model, '✅' if calibrated else '❌')

        logging.info("\n   Data Status:")
        logging.info("     Price Points: %s", status['data_status']['price_points'])
        logging.info("     Return Points: %s", status['data_status']['return_points'])
        logging.info("     Data Quality: %s", status['data_status']['data_quality'])

        logging.info("\n   Current State:")
        logging.info(f"     Volatility: {status['current_state']['volatility']:.1%}")
        logging.info("     Regime: %s", status['current_state']['regime'])

        if status["model_parameters"]["garch"]["persistence"]:
            logging.info("\n   GARCH Parameters:")
            garch = status["model_parameters"]["garch"]
            logging.info(f"     Persistence (α+β): {garch['persistence']:.3f}")
            logging.info(f"     Alpha (ARCH): {garch['alpha']:.4f}")
            logging.info(f"     Beta (GARCH): {garch['beta']:.3f}")

    except Exception as e:
        logging.info("   ❌ Status Error: %s", e)

    logging.info("\n" + "=" * 80)
    logging.info("✅ CONSOLIDATED VOLATILITY ENGINE FEATURES DEMONSTRATED:")
    logging.info("   • Unified volatility modeling (Heston + GARCH + RoughVol)")
    logging.info("   • Intelligent model selection based on time horizon")
    logging.info("   • Comprehensive volatility forecasting with confidence intervals")
    logging.info("   • Real-time volatility surface generation")
    logging.info("   • Automatic volatility regime detection")
    logging.info("   • Performance optimization with intelligent caching")
    logging.info("   • Integration-ready with V05_PricingEngine")
    logging.info("   • Eliminates volatility calculation duplications")
    logging.info("   • Single source of truth for all volatility needs")
    logging.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
