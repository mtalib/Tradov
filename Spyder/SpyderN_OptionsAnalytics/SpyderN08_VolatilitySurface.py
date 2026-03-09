#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderN_OptionsAnalytics
Module: SpyderN08_VolatilitySurface.py
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
from typing import Any, Union
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import threading
import time
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy import interpolate, optimize
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from matplotlib import cm

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderC_MarketData.SpyderC03_OptionChain import OptionChainManager
from Spyder.SpyderN_OptionsAnalytics.SpyderN01_VolatilitySmile import VolatilitySmileAnalyzer
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

MIN_STRIKES_PER_EXPIRY = 5
MIN_EXPIRIES = 3
MONEYNESS_RANGE = (0.70, 1.30)  # 70% to 130% of spot
TIME_TO_EXPIRY_RANGE = (7, 365)  # 7 days to 1 year

# Surface fitting parameters
SMOOTHING_FACTOR = 0.1
INTERPOLATION_GRID_SIZE = 50
SVI_CALIBRATION_TOLERANCE = 1e-6

# Arbitrage detection thresholds
CALENDAR_ARB_THRESHOLD = 0.0001  # 0.01% violation
BUTTERFLY_ARB_THRESHOLD = 0.0001
SURFACE_QUALITY_THRESHOLD = 0.95  # R-squared threshold

# ==============================================================================
# ENUMS
# ==============================================================================
class SurfaceModel(Enum):
    """Volatility surface fitting models."""
    POLYNOMIAL = "polynomial"
    SPLINE = "spline"
    SVI = "svi"  # Stochastic Volatility Inspired
    SABR = "sabr"  # Stochastic Alpha Beta Rho
    LOCAL_VOL = "local_vol"
    VANNA_VOLGA = "vanna_volga"

class InterpolationMethod(Enum):
    """Surface interpolation methods."""
    LINEAR = "linear"
    CUBIC = "cubic"
    THIN_PLATE_SPLINE = "thin_plate_spline"
    RADIAL_BASIS = "radial_basis"

class ArbitrageType(Enum):
    """Types of arbitrage in volatility surface."""
    CALENDAR = "calendar"
    BUTTERFLY = "butterfly"
    VERTICAL = "vertical"
    NO_ARBITRAGE = "no_arbitrage"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SurfacePoint:
    """Single point on volatility surface."""
    strike: float
    expiry: datetime
    time_to_expiry: float  # In years
    moneyness: float  # Strike/Spot
    log_moneyness: float  # log(Strike/Spot)
    implied_vol: float
    bid_vol: float | None = None
    ask_vol: float | None = None
    volume: int = 0
    open_interest: int = 0

    @property
    def mid_vol(self) -> float:
        """Get mid volatility."""
        if self.bid_vol and self.ask_vol:
            return (self.bid_vol + self.ask_vol) / 2
        return self.implied_vol

@dataclass
class VolatilitySurface:
    """Complete volatility surface."""
    timestamp: datetime
    symbol: str
    spot_price: float

    # Surface data
    surface_points: list[SurfacePoint]

    # Grid representation
    moneyness_grid: np.ndarray
    time_grid: np.ndarray
    vol_grid: np.ndarray

    # Model information
    model: SurfaceModel
    model_params: dict[str, Any]
    interpolation_method: InterpolationMethod

    # Quality metrics
    fit_quality: float  # Overall R-squared
    smoothness: float  # Surface smoothness metric
    arbitrage_free: bool

    # Calibration info
    calibration_time: float
    num_points_used: int
    num_points_rejected: int

@dataclass
class SurfaceAnomaly:
    """Detected anomaly in volatility surface."""
    anomaly_type: ArbitrageType
    location: tuple[float, float]  # (moneyness, time_to_expiry)
    severity: float  # 0-1
    description: str
    affected_points: list[SurfacePoint]
    tradeable: bool
    suggested_trade: str | None = None

@dataclass
class LocalVolatility:
    """Local volatility surface derived from implied volatility."""
    timestamp: datetime
    spot_grid: np.ndarray
    time_grid: np.ndarray
    local_vol_grid: np.ndarray

    # Dupire formula components
    dvol_dT: np.ndarray  # ∂σ/∂T
    dvol_dK: np.ndarray  # ∂σ/∂K
    d2vol_dK2: np.ndarray  # ∂²σ/∂K²

# ==============================================================================
# VOLATILITY SURFACE ANALYZER CLASS
# ==============================================================================
class VolatilitySurfaceAnalyzer:
    """
    Creates and analyzes 3D volatility surfaces.

    This class builds volatility surfaces from option chains, fits various
    models, detects arbitrage opportunities, and provides visualization tools.
    """

    def __init__(self, symbol: str = "SPY"):
        """
        Initialize the volatility surface analyzer.

        Args:
            symbol: Underlying symbol to analyze
        """
        self.symbol = symbol
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Data sources
        self.option_chain_mgr = OptionChainManager()
        self.smile_analyzer = VolatilitySmileAnalyzer(symbol)
        self.event_manager = get_event_manager()

        # Surface storage
        self.current_surface: VolatilitySurface | None = None
        self.surface_history: list[VolatilitySurface] = []
        self.local_vol_surface: LocalVolatility | None = None

        # Interpolation functions
        self._interpolator: Any | None = None

        # Threading
        self._lock = threading.RLock()
        self._monitor_thread: threading.Thread | None = None
        self._running = False

        self.logger.info(f"VolatilitySurfaceAnalyzer initialized for {symbol}")

    # ==========================================================================
    # MAIN SURFACE BUILDING METHODS
    # ==========================================================================
    def build_surface(self,
                     option_data: pd.DataFrame,
                     model: SurfaceModel = SurfaceModel.SVI,
                     interpolation: InterpolationMethod = InterpolationMethod.CUBIC) -> VolatilitySurface:
        """
        Build volatility surface from option data.

        Args:
            option_data: DataFrame with option prices and IVs
            model: Surface fitting model
            interpolation: Interpolation method

        Returns:
            VolatilitySurface object
        """
        try:
            start_time = time.time()

            # Extract and validate surface points
            surface_points = self._extract_surface_points(option_data)

            if len(surface_points) < MIN_STRIKES_PER_EXPIRY * MIN_EXPIRIES:
                raise ValueError(f"Insufficient data for surface: {len(surface_points)} points")

            # Get spot price
            spot_price = option_data['underlying_price'].iloc[0]

            # Fit surface model
            if model == SurfaceModel.SVI:
                vol_grid, model_params, quality = self._fit_svi_surface(surface_points, spot_price)
            elif model == SurfaceModel.SPLINE:
                vol_grid, model_params, quality = self._fit_spline_surface(surface_points, spot_price)
            else:
                vol_grid, model_params, quality = self._fit_polynomial_surface(surface_points, spot_price)

            # Create interpolation grids
            moneyness_grid, time_grid = self._create_grids(surface_points, spot_price)

            # Check arbitrage conditions
            arbitrage_free = self._check_arbitrage_conditions(moneyness_grid, time_grid, vol_grid)

            # Calculate smoothness
            smoothness = self._calculate_smoothness(vol_grid)

            # Create surface object
            surface = VolatilitySurface(
                timestamp=datetime.now(),
                symbol=self.symbol,
                spot_price=spot_price,
                surface_points=surface_points,
                moneyness_grid=moneyness_grid,
                time_grid=time_grid,
                vol_grid=vol_grid,
                model=model,
                model_params=model_params,
                interpolation_method=interpolation,
                fit_quality=quality['r_squared'],
                smoothness=smoothness,
                arbitrage_free=arbitrage_free,
                calibration_time=time.time() - start_time,
                num_points_used=len(surface_points),
                num_points_rejected=quality.get('rejected', 0)
            )

            # Update storage
            with self._lock:
                self.current_surface = surface
                self.surface_history.append(surface)

                # Keep only recent history
                if len(self.surface_history) > 100:
                    self.surface_history = self.surface_history[-100:]

            # Create interpolator
            self._create_interpolator(surface, interpolation)

            # Emit surface update event
            self._emit_surface_update(surface)

            return surface

        except Exception as e:
            self.logger.error(f"Error building surface: {e}")
            self.error_handler.handle_error(e, {"method": "build_surface"})
            raise

    # ==========================================================================
    # SURFACE FITTING METHODS
    # ==========================================================================
    def _fit_svi_surface(self,
                        points: list[SurfacePoint],
                        spot: float) -> tuple[np.ndarray, dict[str, Any], dict[str, float]]:
        """
        Fit SVI model to entire surface.

        The SVI parameterization for each expiry slice:
        w(k) = a + b * (rho * (k - m) + sqrt((k - m)^2 + sigma^2))
        """
        # Group points by expiry
        expiry_groups = {}
        for point in points:
            if point.expiry not in expiry_groups:
                expiry_groups[point.expiry] = []
            expiry_groups[point.expiry].append(point)

        # Fit SVI to each expiry
        svi_params_by_expiry = {}
        quality_metrics = []

        for expiry, expiry_points in expiry_groups.items():
            # Extract data for this expiry
            k_values = np.array([p.log_moneyness for p in expiry_points])
            w_values = np.array([p.implied_vol**2 * p.time_to_expiry for p in expiry_points])

            # Fit SVI parameters
            params, rmse = self._fit_svi_slice(k_values, w_values)
            svi_params_by_expiry[expiry] = params
            quality_metrics.append(rmse)

        # Create surface grid
        moneyness_range = np.linspace(0.8, 1.2, INTERPOLATION_GRID_SIZE)
        time_range = np.linspace(7/365, 1.0, INTERPOLATION_GRID_SIZE)

        moneyness_grid, time_grid = np.meshgrid(moneyness_range, time_range)
        vol_grid = np.zeros_like(moneyness_grid)

        # Interpolate SVI parameters across time
        for i, t in enumerate(time_range):
            # Find bracketing expiries
            expiries = sorted(svi_params_by_expiry.keys())

            # Interpolate parameters
            interpolated_params = self._interpolate_svi_params(t, expiries, svi_params_by_expiry)

            # Calculate volatilities for this time slice
            for j, m in enumerate(moneyness_range):
                k = np.log(m)
                w = self._svi_variance(k, interpolated_params)
                vol_grid[i, j] = np.sqrt(max(w / t, 1e-6))

        # Calculate quality metrics
        avg_rmse = np.mean(quality_metrics)
        r_squared = 1 - avg_rmse / np.var([p.implied_vol for p in points])

        model_params = {
            'params_by_expiry': svi_params_by_expiry,
            'interpolation': 'linear'
        }

        quality = {'r_squared': r_squared, 'avg_rmse': avg_rmse}

        return vol_grid, model_params, quality

    def _fit_svi_slice(self, k: np.ndarray, w: np.ndarray) -> tuple[dict[str, float], float]:
        """Fit SVI to a single expiry slice."""
        # Initial parameter guess
        a0 = np.mean(w)
        b0 = 0.1
        rho0 = -0.5
        m0 = 0.0
        sigma0 = 0.1

        # Objective function
        def objective(params):
            a, b, rho, m, sigma = params

            # Constraints
            if b < 0 or sigma < 0 or abs(rho) > 1:
                return 1e10

            # Calculate model variance
            model_w = a + b * (rho * (k - m) + np.sqrt((k - m)**2 + sigma**2))

            # Check for negative variance
            if np.any(model_w < 0):
                return 1e10

            return np.sqrt(np.mean((model_w - w)**2))

        # Optimize
        result = optimize.minimize(
            objective,
            [a0, b0, rho0, m0, sigma0],
            method='Nelder-Mead',
            options={'maxiter': 1000}
        )

        a, b, rho, m, sigma = result.x
        rmse = result.fun

        return {'a': a, 'b': b, 'rho': rho, 'm': m, 'sigma': sigma}, rmse

    def _svi_variance(self, k: float, params: dict[str, float]) -> float:
        """Calculate SVI variance for log-moneyness k."""
        a = params['a']
        b = params['b']
        rho = params['rho']
        m = params['m']
        sigma = params['sigma']

        return a + b * (rho * (k - m) + np.sqrt((k - m)**2 + sigma**2))

    def _interpolate_svi_params(self,
                               target_time: float,
                               expiries: list[datetime],
                               params_by_expiry: dict[datetime, dict[str, float]]) -> dict[str, float]:
        """Interpolate SVI parameters across time."""
        # Convert expiries to time to expiry
        times = [(exp - datetime.now()).days / 365 for exp in expiries]

        # Find bracketing times
        idx = np.searchsorted(times, target_time)

        if idx == 0:
            return params_by_expiry[expiries[0]]
        elif idx >= len(times):
            return params_by_expiry[expiries[-1]]
        else:
            # Linear interpolation between parameters
            t1, t2 = times[idx-1], times[idx]
            w1 = (t2 - target_time) / (t2 - t1)
            w2 = (target_time - t1) / (t2 - t1)

            params1 = params_by_expiry[expiries[idx-1]]
            params2 = params_by_expiry[expiries[idx]]

            interpolated = {}
            for key in params1:
                interpolated[key] = w1 * params1[key] + w2 * params2[key]

            return interpolated

    def _fit_spline_surface(self,
                           points: list[SurfacePoint],
                           spot: float) -> tuple[np.ndarray, dict[str, Any], dict[str, float]]:
        """Fit spline surface to volatility data."""
        # Extract data
        moneyness = np.array([p.moneyness for p in points])
        times = np.array([p.time_to_expiry for p in points])
        vols = np.array([p.implied_vol for p in points])

        # Create regular grid
        moneyness_range = np.linspace(0.8, 1.2, INTERPOLATION_GRID_SIZE)
        time_range = np.linspace(7/365, 1.0, INTERPOLATION_GRID_SIZE)

        # Fit 2D spline
        spline = interpolate.Rbf(moneyness, times, vols,
                                function='cubic', smooth=SMOOTHING_FACTOR)

        # Evaluate on grid
        moneyness_grid, time_grid = np.meshgrid(moneyness_range, time_range)
        vol_grid = spline(moneyness_grid, time_grid)

        # Ensure positive volatilities
        vol_grid = np.maximum(vol_grid, 0.01)

        # Calculate quality
        fitted_vols = spline(moneyness, times)
        rmse = np.sqrt(np.mean((fitted_vols - vols)**2))
        r_squared = 1 - rmse**2 / np.var(vols)

        model_params = {
            'interpolation': 'cubic_spline',
            'smoothing': SMOOTHING_FACTOR
        }

        quality = {'r_squared': r_squared, 'rmse': rmse}

        return vol_grid, model_params, quality

    def _fit_polynomial_surface(self,
                               points: list[SurfacePoint],
                               spot: float) -> tuple[np.ndarray, dict[str, Any], dict[str, float]]:
        """Fit polynomial surface to volatility data."""
        # Extract data
        X = np.column_stack([
            [p.log_moneyness for p in points],
            [p.time_to_expiry for p in points]
        ])
        y = np.array([p.implied_vol for p in points])

        # Create polynomial features (up to degree 3)
        from sklearn.preprocessing import PolynomialFeatures
        poly = PolynomialFeatures(degree=3, include_bias=True)
        X_poly = poly.fit_transform(X)

        # Fit using least squares
        coeffs, _, _, _ = np.linalg.lstsq(X_poly, y, rcond=None)

        # Create regular grid
        moneyness_range = np.linspace(0.8, 1.2, INTERPOLATION_GRID_SIZE)
        time_range = np.linspace(7/365, 1.0, INTERPOLATION_GRID_SIZE)
        moneyness_grid, time_grid = np.meshgrid(moneyness_range, time_range)

        # Evaluate polynomial on grid
        X_grid = np.column_stack([
            np.log(moneyness_grid.ravel()),
            time_grid.ravel()
        ])
        X_grid_poly = poly.transform(X_grid)
        vol_grid = X_grid_poly @ coeffs
        vol_grid = vol_grid.reshape(moneyness_grid.shape)

        # Ensure positive volatilities
        vol_grid = np.maximum(vol_grid, 0.01)

        # Calculate quality
        y_pred = X_poly @ coeffs
        rmse = np.sqrt(np.mean((y_pred - y)**2))
        r_squared = 1 - rmse**2 / np.var(y)

        model_params = {
            'degree': 3,
            'coefficients': coeffs.tolist(),
            'feature_names': poly.get_feature_names_out(['log_moneyness', 'time'])
        }

        quality = {'r_squared': r_squared, 'rmse': rmse}

        return vol_grid, model_params, quality

    # ==========================================================================
    # ARBITRAGE DETECTION
    # ==========================================================================
    def detect_arbitrage(self,
                        surface: VolatilitySurface | None = None,
                        min_profit: float = 0.01) -> list[SurfaceAnomaly]:
        """
        Detect arbitrage opportunities in surface.

        Args:
            surface: Volatility surface (uses current if None)
            min_profit: Minimum profit threshold

        Returns:
            List of detected arbitrage opportunities
        """
        if surface is None:
            surface = self.current_surface

        if surface is None:
            return []

        anomalies = []

        # Check calendar arbitrage
        calendar_arbs = self._check_calendar_arbitrage(surface)
        anomalies.extend(calendar_arbs)

        # Check butterfly arbitrage
        butterfly_arbs = self._check_butterfly_arbitrage(surface)
        anomalies.extend(butterfly_arbs)

        # Check vertical spread arbitrage
        vertical_arbs = self._check_vertical_arbitrage(surface)
        anomalies.extend(vertical_arbs)

        return anomalies

    def _check_calendar_arbitrage(self, surface: VolatilitySurface) -> list[SurfaceAnomaly]:
        """Check for calendar arbitrage (volatility must increase with time)."""
        anomalies = []

        # Check along each moneyness level
        for j in range(surface.moneyness_grid.shape[1]):
            moneyness = surface.moneyness_grid[0, j]

            for i in range(1, surface.time_grid.shape[0]):
                t1 = surface.time_grid[i-1, 0]
                t2 = surface.time_grid[i, 0]
                vol1 = surface.vol_grid[i-1, j]
                vol2 = surface.vol_grid[i, j]

                # Total variance should be increasing
                var1 = vol1**2 * t1
                var2 = vol2**2 * t2

                if var2 < var1 - CALENDAR_ARB_THRESHOLD:
                    anomalies.append(SurfaceAnomaly(
                        anomaly_type=ArbitrageType.CALENDAR,
                        location=(moneyness, (t1 + t2) / 2),
                        severity=abs(var2 - var1) / var1,
                        description=f"Calendar arbitrage at moneyness {moneyness:.2f}",
                        affected_points=[],
                        tradeable=True,
                        suggested_trade=f"Buy {t1:.0f}d calendar, sell {t2:.0f}d calendar"
                    ))

        return anomalies

    def _check_butterfly_arbitrage(self, surface: VolatilitySurface) -> list[SurfaceAnomaly]:
        """Check for butterfly arbitrage (convexity condition)."""
        anomalies = []

        # Check along each time slice
        for i in range(surface.time_grid.shape[0]):
            time = surface.time_grid[i, 0]

            for j in range(1, surface.moneyness_grid.shape[1] - 1):
                k1 = surface.moneyness_grid[0, j-1]
                k2 = surface.moneyness_grid[0, j]
                k3 = surface.moneyness_grid[0, j+1]

                vol1 = surface.vol_grid[i, j-1]
                vol2 = surface.vol_grid[i, j]
                vol3 = surface.vol_grid[i, j+1]

                # Butterfly spread value should be positive
                butterfly = vol2 - (vol1 + vol3) / 2

                if butterfly < -BUTTERFLY_ARB_THRESHOLD:
                    anomalies.append(SurfaceAnomaly(
                        anomaly_type=ArbitrageType.BUTTERFLY,
                        location=(k2, time),
                        severity=abs(butterfly) / vol2,
                        description=f"Butterfly arbitrage at strike {k2:.2f}",
                        affected_points=[],
                        tradeable=True,
                        suggested_trade=f"Sell butterfly at strikes {k1:.2f}/{k2:.2f}/{k3:.2f}"
                    ))

        return anomalies

    def _check_vertical_arbitrage(self, surface: VolatilitySurface) -> list[SurfaceAnomaly]:
        """Check for vertical spread arbitrage."""
        anomalies = []

        # For puts: higher strike should have higher price (for same expiry)
        # This translates to specific conditions on implied volatility

        # Simplified check - would need full pricing in production

        return anomalies

    # ==========================================================================
    # LOCAL VOLATILITY CALCULATION
    # ==========================================================================
    def calculate_local_volatility(self,
                                 surface: VolatilitySurface | None = None) -> LocalVolatility:
        """
        Calculate local volatility using Dupire formula.

        The Dupire formula:
        σ_loc²(K,T) = (∂C/∂T) / (0.5 * K² * ∂²C/∂K²)

        Where we use the relationship between implied vol and option prices.
        """
        if surface is None:
            surface = self.current_surface

        if surface is None:
            raise ValueError("No surface available")

        # Create finer grid for local vol calculation
        spot_range = surface.spot_price * np.linspace(0.8, 1.2, 100)
        time_range = np.linspace(0.01, 1.0, 100)

        spot_grid, time_grid = np.meshgrid(spot_range, time_range)
        local_vol_grid = np.zeros_like(spot_grid)

        # Calculate derivatives of implied volatility
        dvol_dT = np.zeros_like(spot_grid)
        dvol_dK = np.zeros_like(spot_grid)
        d2vol_dK2 = np.zeros_like(spot_grid)

        # Numerical derivatives
        dt = 1/365  # 1 day
        dk = surface.spot_price * 0.01  # 1% of spot

        for i in range(time_grid.shape[0]):
            for j in range(spot_grid.shape[1]):
                T = time_grid[i, j]
                K = spot_grid[i, j]
                S = surface.spot_price

                # Get implied vol at this point
                K / S
                sigma = self.interpolate_volatility(surface, K, T)

                # Calculate derivatives numerically
                if i > 0 and i < time_grid.shape[0] - 1:
                    sigma_up = self.interpolate_volatility(surface, K, T + dt)
                    sigma_down = self.interpolate_volatility(surface, K, T - dt)
                    dvol_dT[i, j] = (sigma_up - sigma_down) / (2 * dt)

                if j > 0 and j < spot_grid.shape[1] - 1:
                    sigma_up = self.interpolate_volatility(surface, K + dk, T)
                    sigma_down = self.interpolate_volatility(surface, K - dk, T)
                    dvol_dK[i, j] = (sigma_up - sigma_down) / (2 * dk)

                    if j > 1 and j < spot_grid.shape[1] - 2:
                        sigma_up2 = self.interpolate_volatility(surface, K + 2*dk, T)
                        sigma_down2 = self.interpolate_volatility(surface, K - 2*dk, T)
                        d2vol_dK2[i, j] = (sigma_up2 - 2*sigma + sigma_down2) / (4 * dk**2)

                # Apply Dupire formula (simplified version)
                r = 0.05  # Risk-free rate
                q = 0.02  # Dividend yield

                d1 = (np.log(S/K) + (r - q + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))

                numerator = sigma**2 + 2*sigma*T*(dvol_dT[i, j] + (r-q)*K*dvol_dK[i, j])
                denominator = 1 + 2*d1*K*np.sqrt(T)*dvol_dK[i, j] + K**2*T*(d1**2*dvol_dK[i, j]**2 + sigma*d2vol_dK2[i, j])

                if denominator > 0:
                    local_vol_grid[i, j] = np.sqrt(max(numerator / denominator, 0.0001))
                else:
                    local_vol_grid[i, j] = sigma  # Fall back to implied vol

        local_vol = LocalVolatility(
            timestamp=datetime.now(),
            spot_grid=spot_grid,
            time_grid=time_grid,
            local_vol_grid=local_vol_grid,
            dvol_dT=dvol_dT,
            dvol_dK=dvol_dK,
            d2vol_dK2=d2vol_dK2
        )

        with self._lock:
            self.local_vol_surface = local_vol

        return local_vol

    # ==========================================================================
    # INTERPOLATION AND EXTRAPOLATION
    # ==========================================================================
    def interpolate_volatility(self,
                             surface: VolatilitySurface,
                             strike: float,
                             time_to_expiry: float) -> float:
        """
        Interpolate volatility for any strike/expiry.

        Args:
            surface: Volatility surface
            strike: Target strike price
            time_to_expiry: Target time to expiry (years)

        Returns:
            Interpolated implied volatility
        """
        moneyness = strike / surface.spot_price

        # Check bounds
        if moneyness < surface.moneyness_grid.min() or moneyness > surface.moneyness_grid.max():
            # Extrapolate using boundary behavior
            return self._extrapolate_volatility(surface, moneyness, time_to_expiry)

        if time_to_expiry < surface.time_grid.min() or time_to_expiry > surface.time_grid.max():
            # Extrapolate in time dimension
            return self._extrapolate_volatility(surface, moneyness, time_to_expiry)

        # Use interpolator if available
        if self._interpolator is not None:
            try:
                return float(self._interpolator(moneyness, time_to_expiry))
            except Exception:
                pass

        # Fall back to bilinear interpolation
        return self._bilinear_interpolation(surface, moneyness, time_to_expiry)

    def _create_interpolator(self,
                           surface: VolatilitySurface,
                           method: InterpolationMethod) -> None:
        """Create interpolation function for the surface."""
        if method == InterpolationMethod.LINEAR:
            self._interpolator = interpolate.RegularGridInterpolator(
                (surface.time_grid[:, 0], surface.moneyness_grid[0, :]),
                surface.vol_grid,
                method='linear',
                bounds_error=False,
                fill_value=None
            )
        elif method == InterpolationMethod.CUBIC:
            # Flatten the grid
            points = []
            values = []

            for i in range(surface.time_grid.shape[0]):
                for j in range(surface.moneyness_grid.shape[1]):
                    points.append([surface.moneyness_grid[i, j], surface.time_grid[i, j]])
                    values.append(surface.vol_grid[i, j])

            self._interpolator = interpolate.Rbf(
                [p[0] for p in points],
                [p[1] for p in points],
                values,
                function='cubic'
            )

    def _bilinear_interpolation(self,
                               surface: VolatilitySurface,
                               moneyness: float,
                               time: float) -> float:
        """Simple bilinear interpolation."""
        # Find surrounding points
        i_time = np.searchsorted(surface.time_grid[:, 0], time)
        j_money = np.searchsorted(surface.moneyness_grid[0, :], moneyness)

        # Boundary handling
        if i_time == 0:
            i_time = 1
        elif i_time >= surface.time_grid.shape[0]:
            i_time = surface.time_grid.shape[0] - 1

        if j_money == 0:
            j_money = 1
        elif j_money >= surface.moneyness_grid.shape[1]:
            j_money = surface.moneyness_grid.shape[1] - 1

        # Get corner points
        t1, t2 = surface.time_grid[i_time-1, 0], surface.time_grid[i_time, 0]
        m1, m2 = surface.moneyness_grid[0, j_money-1], surface.moneyness_grid[0, j_money]

        v11 = surface.vol_grid[i_time-1, j_money-1]
        v12 = surface.vol_grid[i_time-1, j_money]
        v21 = surface.vol_grid[i_time, j_money-1]
        v22 = surface.vol_grid[i_time, j_money]

        # Bilinear interpolation
        w_t = (time - t1) / (t2 - t1)
        w_m = (moneyness - m1) / (m2 - m1)

        v1 = v11 * (1 - w_m) + v12 * w_m
        v2 = v21 * (1 - w_m) + v22 * w_m

        return v1 * (1 - w_t) + v2 * w_t

    def _extrapolate_volatility(self,
                              surface: VolatilitySurface,
                              moneyness: float,
                              time: float) -> float:
        """Extrapolate volatility outside surface bounds."""
        # Use SVI asymptotic behavior for extrapolation
        if surface.model == SurfaceModel.SVI and 'params_by_expiry' in surface.model_params:
            # Find closest expiry
            expiries = list(surface.model_params['params_by_expiry'].keys())
            closest_expiry = min(expiries, key=lambda e: abs((e - datetime.now()).days/365 - time))

            params = surface.model_params['params_by_expiry'][closest_expiry]
            k = np.log(moneyness)
            w = self._svi_variance(k, params)

            return np.sqrt(max(w / time, 0.01))
        else:
            # Simple linear extrapolation
            if moneyness < surface.moneyness_grid.min():
                # Use put wing slope
                edge_vol = surface.vol_grid[:, 0].mean()
                slope = -0.5  # Typical put wing slope
            else:
                # Use call wing slope
                edge_vol = surface.vol_grid[:, -1].mean()
                slope = -0.2  # Typical call wing slope

            distance = abs(moneyness - 1.0)
            return edge_vol + slope * distance

    # ==========================================================================
    # VISUALIZATION
    # ==========================================================================
    def visualize_surface_3d(self,
                           surface: VolatilitySurface | None = None,
                           interactive: bool = True,
                           show_points: bool = True) -> Union[plt.Figure, go.Figure]:
        """
        Create 3D visualization of volatility surface.

        Args:
            surface: Volatility surface (uses current if None)
            interactive: Use plotly for interactive plot
            show_points: Show actual data points

        Returns:
            Matplotlib or Plotly figure
        """
        if surface is None:
            surface = self.current_surface

        if surface is None:
            raise ValueError("No surface available to visualize")

        if interactive:
            # Create interactive Plotly figure
            fig = go.Figure()

            # Add surface
            fig.add_trace(go.Surface(
                x=surface.moneyness_grid[0, :],
                y=surface.time_grid[:, 0] * 365,  # Convert to days
                z=surface.vol_grid * 100,  # Convert to percentage
                colorscale='Viridis',
                name='Implied Volatility Surface',
                showscale=True,
                colorbar=dict(title='IV (%)')
            ))

            # Add actual data points if requested
            if show_points:
                moneyness_points = [p.moneyness for p in surface.surface_points]
                time_points = [p.time_to_expiry * 365 for p in surface.surface_points]
                vol_points = [p.implied_vol * 100 for p in surface.surface_points]

                fig.add_trace(go.Scatter3d(
                    x=moneyness_points,
                    y=time_points,
                    z=vol_points,
                    mode='markers',
                    marker=dict(size=4, color='red'),
                    name='Market Data'
                ))

            # Update layout
            fig.update_layout(
                title=f'{surface.symbol} Implied Volatility Surface',
                scene=dict(
                    xaxis_title='Moneyness (K/S)',
                    yaxis_title='Days to Expiry',
                    zaxis_title='Implied Volatility (%)',
                    camera=dict(
                        eye=dict(x=1.5, y=1.5, z=1.5)
                    )
                ),
                width=900,
                height=700
            )

            return fig

        else:
            # Create static Matplotlib figure
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection='3d')

            # Create surface plot
            surf = ax.plot_surface(
                surface.moneyness_grid,
                surface.time_grid * 365,
                surface.vol_grid * 100,
                cmap=cm.viridis,
                linewidth=0,
                antialiased=True,
                alpha=0.8
            )

            # Add data points if requested
            if show_points:
                moneyness_points = [p.moneyness for p in surface.surface_points]
                time_points = [p.time_to_expiry * 365 for p in surface.surface_points]
                vol_points = [p.implied_vol * 100 for p in surface.surface_points]

                ax.scatter(moneyness_points, time_points, vol_points,
                          c='red', marker='o', s=20, label='Market Data')

            # Labels and title
            ax.set_xlabel('Moneyness (K/S)')
            ax.set_ylabel('Days to Expiry')
            ax.set_zlabel('Implied Volatility (%)')
            ax.set_title(f'{surface.symbol} Implied Volatility Surface')

            # Add colorbar
            fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)

            # Set viewing angle
            ax.view_init(elev=20, azim=45)

            plt.tight_layout()
            return fig

    def plot_smile_term_structure(self,
                                 surface: VolatilitySurface | None = None) -> plt.Figure:
        """Plot implied volatility smiles for different expiries."""
        if surface is None:
            surface = self.current_surface

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Plot smiles for different expiries
        expiry_days = [7, 30, 60, 90, 180]
        colors = plt.cm.viridis(np.linspace(0, 1, len(expiry_days)))

        for days, color in zip(expiry_days, colors, strict=False):
            time = days / 365
            if time <= surface.time_grid.max():
                moneyness = surface.moneyness_grid[0, :]
                vols = []

                for m in moneyness:
                    vol = self.interpolate_volatility(surface, m * surface.spot_price, time)
                    vols.append(vol * 100)

                ax1.plot(moneyness, vols, color=color,
                        label=f'{days}d', linewidth=2)

        ax1.set_xlabel('Moneyness (K/S)')
        ax1.set_ylabel('Implied Volatility (%)')
        ax1.set_title('Volatility Smiles by Expiry')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot term structure for different strikes
        strike_percentages = [0.90, 0.95, 1.00, 1.05, 1.10]

        for pct, color in zip(strike_percentages, colors, strict=False):
            strike = surface.spot_price * pct
            times = surface.time_grid[:, 0]
            vols = []

            for t in times:
                vol = self.interpolate_volatility(surface, strike, t)
                vols.append(vol * 100)

            ax2.plot(times * 365, vols, color=color,
                    label=f'{pct:.0%} Strike', linewidth=2)

        ax2.set_xlabel('Days to Expiry')
        ax2.set_ylabel('Implied Volatility (%)')
        ax2.set_title('Volatility Term Structure by Strike')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        fig.suptitle(f'{surface.symbol} Volatility Surface Analysis', fontsize=14)
        plt.tight_layout()

        return fig

    # ==========================================================================
    # UTILITIES AND HELPERS
    # ==========================================================================
    def _extract_surface_points(self, option_data: pd.DataFrame) -> list[SurfacePoint]:
        """Extract surface points from option data."""
        points = []

        # Get unique expiries
        expiries = option_data['expiry'].unique()
        spot = option_data['underlying_price'].iloc[0]

        for expiry in expiries:
            expiry_data = option_data[option_data['expiry'] == expiry]

            # Group by strike
            for strike, group in expiry_data.groupby('strike'):
                # Calculate moneyness
                moneyness = strike / spot

                # Skip if outside reasonable range
                if moneyness < MONEYNESS_RANGE[0] or moneyness > MONEYNESS_RANGE[1]:
                    continue

                # Average put and call IVs
                put_data = group[group['type'] == 'PUT']
                call_data = group[group['type'] == 'CALL']

                ivs = []
                volumes = []
                ois = []

                if not put_data.empty and 'implied_volatility' in put_data:
                    ivs.append(put_data['implied_volatility'].iloc[0])
                    volumes.append(put_data.get('volume', 0).iloc[0])
                    ois.append(put_data.get('open_interest', 0).iloc[0])

                if not call_data.empty and 'implied_volatility' in call_data:
                    ivs.append(call_data['implied_volatility'].iloc[0])
                    volumes.append(call_data.get('volume', 0).iloc[0])
                    ois.append(call_data.get('open_interest', 0).iloc[0])

                if ivs:
                    time_to_expiry = (expiry - datetime.now()).days / 365

                    if time_to_expiry > 0:
                        points.append(SurfacePoint(
                            strike=strike,
                            expiry=expiry,
                            time_to_expiry=time_to_expiry,
                            moneyness=moneyness,
                            log_moneyness=np.log(moneyness),
                            implied_vol=np.mean(ivs),
                            volume=sum(volumes),
                            open_interest=sum(ois)
                        ))

        return points

    def _create_grids(self,
                     points: list[SurfacePoint],
                     spot: float) -> tuple[np.ndarray, np.ndarray]:
        """Create regular grids for surface representation."""
        # Get unique values
        moneyness_values = sorted(list(set(p.moneyness for p in points)))
        time_values = sorted(list(set(p.time_to_expiry for p in points)))

        # Create regular grids
        moneyness_range = np.linspace(
            max(min(moneyness_values), MONEYNESS_RANGE[0]),
            min(max(moneyness_values), MONEYNESS_RANGE[1]),
            INTERPOLATION_GRID_SIZE
        )

        time_range = np.linspace(
            max(min(time_values), TIME_TO_EXPIRY_RANGE[0]/365),
            min(max(time_values), TIME_TO_EXPIRY_RANGE[1]/365),
            INTERPOLATION_GRID_SIZE
        )

        return np.meshgrid(moneyness_range, time_range)

    def _check_arbitrage_conditions(self,
                                   moneyness_grid: np.ndarray,
                                   time_grid: np.ndarray,
                                   vol_grid: np.ndarray) -> bool:
        """Check if surface satisfies no-arbitrage conditions."""
        # Simplified check - in production would be more comprehensive

        # Check for negative volatilities
        if np.any(vol_grid < 0):
            return False

        # Check for calendar arbitrage (variance should increase with time)
        for j in range(vol_grid.shape[1]):
            for i in range(1, vol_grid.shape[0]):
                var1 = vol_grid[i-1, j]**2 * time_grid[i-1, j]
                var2 = vol_grid[i, j]**2 * time_grid[i, j]

                if var2 < var1 - CALENDAR_ARB_THRESHOLD:
                    return False

        return True

    def _calculate_smoothness(self, vol_grid: np.ndarray) -> float:
        """Calculate surface smoothness metric."""
        # Use total variation as smoothness measure
        dx = np.diff(vol_grid, axis=1)
        dy = np.diff(vol_grid, axis=0)

        total_variation = np.sum(np.abs(dx)) + np.sum(np.abs(dy))

        # Normalize by surface area
        smoothness = 1.0 / (1.0 + total_variation / vol_grid.size)

        return smoothness

    def _emit_surface_update(self, surface: VolatilitySurface) -> None:
        """Emit surface update event."""
        event = Event(
            type=EventType.ANALYTICS,
            data={
                'type': 'volatility_surface_update',
                'symbol': surface.symbol,
                'timestamp': surface.timestamp.isoformat(),
                'model': surface.model.value,
                'fit_quality': surface.fit_quality,
                'arbitrage_free': surface.arbitrage_free,
                'num_points': surface.num_points_used
            }
        )
        self.event_manager.emit(event)

    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    def get_surface_metrics(self) -> dict[str, Any]:
        """Get current surface metrics."""
        if self.current_surface is None:
            return {
                'status': 'no_surface',
                'message': 'No surface currently built'
            }

        surface = self.current_surface

        return {
            'status': 'active',
            'timestamp': surface.timestamp.isoformat(),
            'symbol': surface.symbol,
            'spot_price': surface.spot_price,
            'model': surface.model.value,
            'fit_quality': surface.fit_quality,
            'smoothness': surface.smoothness,
            'arbitrage_free': surface.arbitrage_free,
            'num_points': surface.num_points_used,
            'moneyness_range': [
                float(surface.moneyness_grid.min()),
                float(surface.moneyness_grid.max())
            ],
            'time_range_days': [
                float(surface.time_grid.min() * 365),
                float(surface.time_grid.max() * 365)
            ],
            'calibration_time': surface.calibration_time
        }

    def export_surface_data(self,
                           surface: VolatilitySurface | None = None,
                           format: str = 'json') -> Union[str, pd.DataFrame]:
        """
        Export surface data for external use.

        Args:
            surface: Surface to export (uses current if None)
            format: 'json' or 'dataframe'

        Returns:
            Exported data
        """
        if surface is None:
            surface = self.current_surface

        if surface is None:
            raise ValueError("No surface available to export")

        # Create export data
        export_data = {
            'metadata': {
                'timestamp': surface.timestamp.isoformat(),
                'symbol': surface.symbol,
                'spot_price': surface.spot_price,
                'model': surface.model.value,
                'fit_quality': surface.fit_quality
            },
            'grid_data': {
                'moneyness': surface.moneyness_grid[0, :].tolist(),
                'time_days': (surface.time_grid[:, 0] * 365).tolist(),
                'volatilities': surface.vol_grid.tolist()
            },
            'raw_points': [
                {
                    'strike': p.strike,
                    'expiry': p.expiry.isoformat(),
                    'moneyness': p.moneyness,
                    'time_to_expiry_days': p.time_to_expiry * 365,
                    'implied_vol': p.implied_vol,
                    'volume': p.volume,
                    'open_interest': p.open_interest
                }
                for p in surface.surface_points
            ]
        }

        if format == 'json':
            return json.dumps(export_data, indent=2)
        else:
            # Convert to DataFrame
            rows = []
            for i in range(surface.time_grid.shape[0]):
                for j in range(surface.moneyness_grid.shape[1]):
                    rows.append({
                        'moneyness': surface.moneyness_grid[i, j],
                        'time_days': surface.time_grid[i, j] * 365,
                        'implied_vol': surface.vol_grid[i, j]
                    })

            return pd.DataFrame(rows)

# ==============================================================================
# MODULE EXPORTS
# ==============================================================================
__all__ = [
    'VolatilitySurfaceAnalyzer',
    'VolatilitySurface',
    'SurfacePoint',
    'SurfaceAnomaly',
    'LocalVolatility',
    'SurfaceModel',
    'InterpolationMethod',
    'ArbitrageType'
]

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Test the volatility surface analyzer
    analyzer = VolatilitySurfaceAnalyzer("SPY")


    # Create sample data with multiple expiries
    np.random.seed(42)

    expiries = [
        datetime.now() + timedelta(days=7),
        datetime.now() + timedelta(days=30),
        datetime.now() + timedelta(days=60),
        datetime.now() + timedelta(days=90)
    ]

    strikes = np.arange(420, 461, 5)
    spot = 440

    # Generate sample option data
    option_data = []

    for expiry in expiries:
        tte = (expiry - datetime.now()).days / 365

        for strike in strikes:
            moneyness = strike / spot

            # Generate IV with smile
            base_vol = 0.16 + 0.1 * tte  # Term structure
            smile_adjustment = 0.05 * (np.log(moneyness))**2  # Smile
            iv = base_vol + smile_adjustment + np.random.normal(0, 0.005)

            # Add both put and call
            for opt_type in ['PUT', 'CALL']:
                option_data.append({
                    'strike': strike,
                    'type': opt_type,
                    'expiry': expiry,
                    'underlying_price': spot,
                    'implied_volatility': max(iv, 0.05),
                    'volume': np.random.randint(100, 5000),
                    'open_interest': np.random.randint(1000, 20000)
                })

    df = pd.DataFrame(option_data)

    # Build surface
    surface = analyzer.build_surface(df, model=SurfaceModel.SVI)

    # Print metrics
    metrics = analyzer.get_surface_metrics()

    # Detect arbitrage
    anomalies = analyzer.detect_arbitrage(surface)

    if anomalies:
        for anomaly in anomalies[:3]:  # Show first 3
            if anomaly.suggested_trade:
                pass
    else:
        pass

    # Test interpolation
    test_strikes = [430, 440, 450]
    test_expiry = 45/365  # 45 days

    for strike in test_strikes:
        vol = analyzer.interpolate_volatility(surface, strike, test_expiry)

    # Calculate local volatility
    local_vol = analyzer.calculate_local_volatility(surface)

    # Create visualizations

    # 3D surface plot
    fig_3d = analyzer.visualize_surface_3d(surface, interactive=False)

    # Smile term structure
    fig_smile = analyzer.plot_smile_term_structure(surface)

    # Export data
    json_data = analyzer.export_surface_data(surface, format='json')

    df_export = analyzer.export_surface_data(surface, format='dataframe')


    # Close plots if created
    plt.close('all')
