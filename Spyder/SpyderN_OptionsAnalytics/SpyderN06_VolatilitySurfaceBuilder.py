#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN06_VolatilitySurfaceBuilder.py
Group: N (Options Analytics)
Purpose: 3D volatility surface construction, analysis, and arbitrage detection
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 21:30:00

Description:
    This module builds and analyzes 3D implied volatility surfaces across
    strikes and expirations. It provides surface fitting, interpolation,
    arbitrage detection, term structure analysis, smile/skew patterns,
    and real-time surface updates for trading decisions.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import threading
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import optimize  # noqa: E402
from scipy.interpolate import RBFInterpolator, griddata  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from pathlib import Path  # noqa: E402
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

import logging  # noqa: E402

try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError:
    try:
        from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
        from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    except ImportError:
        class SpyderLogger:  # type: ignore[no-redef]
            """Fallback logger adapter for standalone usage."""

            @staticmethod
            def get_logger(name: str):
                return logging.getLogger(name)

        class SpyderErrorHandler:  # type: ignore[no-redef]
            """Fallback error handler for standalone usage."""

            def handle_error(self, error: Exception, context: str | None = None) -> None:
                logging.getLogger(__name__).error(
                    "Error in %s: %s", context or "unknown", error
                )

# Import other options modules if available
try:
    from Spyder.SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import OptionsPricer
    from Spyder.SpyderN_OptionsAnalytics.SpyderN02_ImpliedVolatilityEngine import ImpliedVolatilityEngine  # noqa: E501
    from Spyder.SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager import OptionsChainManager
    ANALYTICS_AVAILABLE = True
except ImportError:
    try:
        from SpyderN_OptionsAnalytics.SpyderN01_OptionsPricer import OptionsPricer
        from SpyderN_OptionsAnalytics.SpyderN02_ImpliedVolatilityEngine import ImpliedVolatilityEngine  # noqa: E501
        from SpyderN_OptionsAnalytics.SpyderN03_OptionsChainManager import OptionsChainManager
        ANALYTICS_AVAILABLE = True
    except ImportError:
        ANALYTICS_AVAILABLE = False
        logging.info("⚠️ Options analytics modules not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Surface parameters
MIN_STRIKES = 5  # Minimum strikes for surface
MIN_EXPIRIES = 3  # Minimum expiries for surface
MAX_MONEYNESS = 2.0  # Maximum moneyness range (0.5 to 2.0)
SMOOTHING_FACTOR = 0.5  # Surface smoothing

# Interpolation methods
INTERPOLATION_METHODS = ['linear', 'cubic', 'rbf', 'svi', 'sabr']

# Arbitrage thresholds
MIN_IV = 0.01  # 1% minimum IV
MAX_IV = 3.00  # 300% maximum IV
CALENDAR_SPREAD_THRESHOLD = 0.001  # 0.1% for calendar arbitrage
BUTTERFLY_THRESHOLD = 0.001  # 0.1% for butterfly arbitrage

# Surface update
UPDATE_INTERVAL = 30  # seconds
CACHE_DURATION = 60  # seconds

# ==============================================================================
# ENUMS
# ==============================================================================
class SurfaceType(Enum):
    """Volatility surface type"""
    IMPLIED_VOLATILITY = "IV"
    LOCAL_VOLATILITY = "LV"
    STOCHASTIC_VOLATILITY = "SV"
    VARIANCE = "VAR"

class InterpolationMethod(Enum):
    """Surface interpolation methods"""
    LINEAR = "linear"
    CUBIC = "cubic"
    RBF = "rbf"  # Radial Basis Function
    SVI = "svi"  # Stochastic Volatility Inspired
    SABR = "sabr"  # SABR model
    SPLINE = "spline"

class ArbitrageType(Enum):
    """Arbitrage opportunity types"""
    CALENDAR = "Calendar Spread"
    BUTTERFLY = "Butterfly"
    VERTICAL = "Vertical Spread"
    BOX = "Box Spread"
    CONVERSION = "Conversion/Reversal"

class SkewPattern(Enum):
    """Volatility skew patterns"""
    NORMAL = "Normal Skew"
    REVERSE = "Reverse Skew"
    SMILE = "Volatility Smile"
    SMIRK = "Volatility Smirk"
    FLAT = "Flat"

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class SurfacePoint:
    """Single point on volatility surface"""
    strike: float
    expiry: datetime
    moneyness: float
    time_to_expiry: float
    implied_volatility: float
    bid_iv: float
    ask_iv: float
    volume: int
    open_interest: int
    underlying_price: float

@dataclass
class VolatilitySurface:
    """Complete volatility surface"""
    symbol: str
    surface_type: SurfaceType
    timestamp: datetime
    underlying_price: float
    risk_free_rate: float
    dividend_yield: float

    # Surface data
    strikes: np.ndarray
    expiries: np.ndarray
    moneyness_grid: np.ndarray
    time_grid: np.ndarray
    iv_surface: np.ndarray

    # Interpolation
    interpolation_method: InterpolationMethod
    interpolator: Any | None = None

    # Analytics
    atm_term_structure: np.ndarray = field(default_factory=lambda: np.array([]))
    skew_parameters: dict[datetime, float] = field(default_factory=dict)
    smile_parameters: dict[datetime, dict] = field(default_factory=dict)

    # Quality metrics
    data_points: int = 0
    interpolation_error: float = 0.0
    arbitrage_violations: int = 0

@dataclass
class ArbitrageOpportunity:
    """Arbitrage opportunity in volatility surface"""
    arbitrage_type: ArbitrageType
    strikes: list[float]
    expiries: list[datetime]
    current_ivs: list[float]
    theoretical_bound: float
    violation_amount: float
    profit_potential: float
    confidence: float
    trade_setup: dict[str, Any]

@dataclass
class SurfaceAnalytics:
    """Volatility surface analytics"""
    # Term structure
    term_structure_shape: str  # 'contango', 'backwardation', 'flat'
    term_structure_slope: float

    # Skew analysis
    skew_pattern: SkewPattern
    skew_steepness: float
    put_wing_slope: float
    call_wing_slope: float

    # Smile metrics
    smile_curvature: float
    atm_volatility: float
    risk_reversal_25d: float
    butterfly_25d: float

    # Surface quality
    smoothness_score: float
    data_coverage: float
    interpolation_quality: float

    # Trading signals
    rich_strikes: list[tuple[float, datetime]]
    cheap_strikes: list[tuple[float, datetime]]
    arbitrage_opportunities: list[ArbitrageOpportunity]


def _coerce_datetime(value: Any) -> datetime | None:
    """Best-effort conversion of timestamps to datetime."""
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return None

# ==============================================================================
# VOLATILITY SURFACE BUILDER CLASS
# ==============================================================================
class VolatilitySurfaceBuilder:
    """
    3D Volatility surface construction and analysis.

    Features:
        - Multi-dimensional surface fitting
        - Advanced interpolation methods (RBF, SVI, SABR)
        - Arbitrage detection and validation
        - Term structure and skew analysis
        - Real-time surface updates
        - Interactive 3D visualization
        - Surface quality metrics
    """

    def __init__(self, config: dict | None = None):
        """
        Initialize the Volatility Surface Builder

        Args:
            config: Configuration dictionary
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.interpolation_method = InterpolationMethod(
            self.config.get('interpolation', 'rbf')
        )
        self.smoothing = self.config.get('smoothing', SMOOTHING_FACTOR)

        # Data storage
        self.surfaces: dict[str, VolatilitySurface] = {}
        self.surface_history: dict[str, list[VolatilitySurface]] = {}
        self.arbitrage_opportunities: list[ArbitrageOpportunity] = []

        # Analytics modules
        self.pricer = OptionsPricer() if ANALYTICS_AVAILABLE else None
        self.iv_engine = ImpliedVolatilityEngine() if ANALYTICS_AVAILABLE else None
        self.chain_manager = OptionsChainManager() if ANALYTICS_AVAILABLE else None

        # Threading
        self.lock = threading.Lock()
        self.update_thread = None
        self.monitoring = False

        # Cache
        self.cache = {}
        self.cache_timestamp = {}

        self.logger.debug("VolatilitySurfaceBuilder initialized")

    # ==========================================================================
    # SURFACE CONSTRUCTION
    # ==========================================================================

    def build_surface(self, symbol: str, options_data: pd.DataFrame,
                     underlying_price: float,
                     risk_free_rate: float = 0.05,
                     dividend_yield: float = 0.0) -> VolatilitySurface:
        """
        Build volatility surface from options data

        Args:
            symbol: Underlying symbol
            options_data: DataFrame with options data
            underlying_price: Current underlying price
            risk_free_rate: Risk-free rate
            dividend_yield: Dividend yield

        Returns:
            VolatilitySurface object
        """
        with self.lock:
            try:
                # Prepare data
                surface_points = self._prepare_surface_data(
                    options_data, underlying_price
                )

                if len(surface_points) < MIN_STRIKES * MIN_EXPIRIES:
                    raise ValueError(f"Insufficient data points: {len(surface_points)}")

                # Create grids
                strikes, expiries, moneyness_grid, time_grid = self._create_grids(
                    surface_points, underlying_price
                )

                # Build IV surface
                iv_surface = self._interpolate_surface(
                    surface_points, moneyness_grid, time_grid
                )

                # Apply smoothing
                if self.smoothing > 0:
                    iv_surface = self._smooth_surface(iv_surface)

                # Create surface object
                surface = VolatilitySurface(
                    symbol=symbol,
                    surface_type=SurfaceType.IMPLIED_VOLATILITY,
                    timestamp=datetime.now(UTC),
                    underlying_price=underlying_price,
                    risk_free_rate=risk_free_rate,
                    dividend_yield=dividend_yield,
                    strikes=strikes,
                    expiries=expiries,
                    moneyness_grid=moneyness_grid,
                    time_grid=time_grid,
                    iv_surface=iv_surface,
                    interpolation_method=self.interpolation_method,
                    data_points=len(surface_points)
                )

                # Add analytics
                surface = self._add_surface_analytics(surface)

                # Check for arbitrage
                surface.arbitrage_violations = self._detect_arbitrage(surface)

                # Store surface
                self.surfaces[symbol] = surface

                # Add to history
                if symbol not in self.surface_history:
                    self.surface_history[symbol] = []
                self.surface_history[symbol].append(surface)

                # Limit history size
                if len(self.surface_history[symbol]) > 100:
                    self.surface_history[symbol].pop(0)

                self.logger.info("Built volatility surface for %s", symbol)

                return surface

            except Exception as e:
                self.logger.error("Failed to build surface: %s", e, exc_info=True)
                raise

    def _prepare_surface_data(self, options_data: pd.DataFrame,
                             underlying_price: float) -> list[SurfacePoint]:
        """Prepare surface data points from options data"""
        surface_points = []

        for _, row in options_data.iterrows():
            # Calculate moneyness and time
            moneyness = row['strike'] / underlying_price
            time_to_expiry = (row['expiry'] - datetime.now(UTC)).days / 365.0

            # Skip if outside reasonable bounds
            if (moneyness < 1/MAX_MONEYNESS or moneyness > MAX_MONEYNESS or
                time_to_expiry <= 0):
                continue

            # Create surface point
            point = SurfacePoint(
                strike=row['strike'],
                expiry=row['expiry'],
                moneyness=moneyness,
                time_to_expiry=time_to_expiry,
                implied_volatility=row.get('implied_volatility', 0.20),
                bid_iv=row.get('bid_iv', row.get('implied_volatility', 0.20) - 0.01),
                ask_iv=row.get('ask_iv', row.get('implied_volatility', 0.20) + 0.01),
                volume=row.get('volume', 0),
                open_interest=row.get('open_interest', 0),
                underlying_price=underlying_price
            )

            surface_points.append(point)

        return surface_points

    def _create_grids(self, surface_points: list[SurfacePoint],
                     underlying_price: float) -> tuple[np.ndarray, ...]:
        """Create moneyness and time grids for surface"""
        # Extract unique values
        strikes = sorted(list({p.strike for p in surface_points}))
        expiries = sorted(list({p.expiry for p in surface_points}))

        # Create moneyness grid
        min_moneyness = min(p.moneyness for p in surface_points)
        max_moneyness = max(p.moneyness for p in surface_points)
        moneyness_range = np.linspace(min_moneyness, max_moneyness, 50)

        # Create time grid
        min_time = min(p.time_to_expiry for p in surface_points)
        max_time = max(p.time_to_expiry for p in surface_points)
        time_range = np.linspace(min_time, max_time, 30)

        # Create 2D grids
        moneyness_grid, time_grid = np.meshgrid(moneyness_range, time_range)

        return np.array(strikes), np.array(expiries), moneyness_grid, time_grid

    def _interpolate_surface(self, surface_points: list[SurfacePoint],
                            moneyness_grid: np.ndarray,
                            time_grid: np.ndarray) -> np.ndarray:
        """Interpolate volatility surface"""
        # Prepare data for interpolation
        points = np.array([[p.moneyness, p.time_to_expiry] for p in surface_points])
        values = np.array([p.implied_volatility for p in surface_points])

        # Choose interpolation method
        if self.interpolation_method == InterpolationMethod.RBF:
            surface = self._rbf_interpolation(points, values, moneyness_grid, time_grid)
        elif self.interpolation_method == InterpolationMethod.SVI:
            surface = self._svi_interpolation(points, values, moneyness_grid, time_grid)
        elif self.interpolation_method == InterpolationMethod.CUBIC:
            surface = self._cubic_interpolation(points, values, moneyness_grid, time_grid)
        else:
            # Default to linear
            surface = self._linear_interpolation(points, values, moneyness_grid, time_grid)

        # Ensure reasonable bounds
        surface = np.clip(surface, MIN_IV, MAX_IV)

        return surface

    def _rbf_interpolation(self, points: np.ndarray, values: np.ndarray,
                          moneyness_grid: np.ndarray,
                          time_grid: np.ndarray) -> np.ndarray:
        """Radial Basis Function interpolation"""
        # Create RBF interpolator
        rbf = RBFInterpolator(points, values, kernel='thin_plate_spline')

        # Interpolate on grid
        grid_points = np.column_stack([moneyness_grid.ravel(), time_grid.ravel()])
        surface = rbf(grid_points).reshape(moneyness_grid.shape)

        return surface

    def _svi_interpolation(self, points: np.ndarray, values: np.ndarray,
                          moneyness_grid: np.ndarray,
                          time_grid: np.ndarray) -> np.ndarray:
        """SVI (Stochastic Volatility Inspired) parameterization"""
        # SVI parameterization: w(k) = a + b(ρ(k-m) + sqrt((k-m)² + σ²))
        # where w is total variance, k is log-moneyness

        surface = np.zeros_like(moneyness_grid)

        # Fit SVI for each time slice
        unique_times = np.unique(points[:, 1])

        for _t_idx, t in enumerate(unique_times):
            # Get data for this time slice
            mask = points[:, 1] == t
            moneyness = points[mask, 0]
            ivs = values[mask]

            if len(moneyness) < 5:
                continue

            # Convert to log-moneyness
            log_moneyness = np.log(moneyness)

            # Fit SVI parameters (simplified)
            # Bind loop variables explicitly via default arguments to avoid
            # the closure-over-loop-variable bug.
            def svi_objective(params, _lm=log_moneyness, _t=t, _ivs=ivs):
                a, b, rho, m, sigma = params
                k = _lm - m
                w_model = a + b * (rho * k + np.sqrt(k**2 + sigma**2))
                iv_model = np.sqrt(w_model / _t) if _t > 0 else 0
                return np.sum((iv_model - _ivs)**2)

            # Initial guess
            x0 = [np.mean(ivs)**2 * t, 0.1, 0.0, 0.0, 0.1]

            # Bounds
            bounds = [
                (0, None),  # a >= 0
                (0, None),  # b >= 0
                (-1, 1),    # -1 <= ρ <= 1
                (-1, 1),    # m
                (0.01, 1)   # σ
            ]

            try:
                result = optimize.minimize(svi_objective, x0, bounds=bounds, method='L-BFGS-B')
                a, b, rho, m, sigma = result.x

                # Apply to grid
                time_mask = np.abs(time_grid - t) < 0.01
                if np.any(time_mask):
                    k_grid = np.log(moneyness_grid[time_mask]) - m
                    w_grid = a + b * (rho * k_grid + np.sqrt(k_grid**2 + sigma**2))
                    surface[time_mask] = np.sqrt(np.maximum(0, w_grid / t))
            except Exception:
                # Fallback to linear interpolation for this slice
                pass

        # Fill any missing values
        mask = surface == 0
        if np.any(mask):
            surface[mask] = griddata(points, values,
                                    np.column_stack([moneyness_grid[mask], time_grid[mask]]),
                                    method='linear')

        return surface

    def _cubic_interpolation(self, points: np.ndarray, values: np.ndarray,
                            moneyness_grid: np.ndarray,
                            time_grid: np.ndarray) -> np.ndarray:
        """Cubic spline interpolation"""
        grid_points = np.column_stack([moneyness_grid.ravel(), time_grid.ravel()])
        surface = griddata(points, values, grid_points, method='cubic')
        surface = surface.reshape(moneyness_grid.shape)

        # Fill NaN values with linear interpolation
        mask = np.isnan(surface)
        if np.any(mask):
            surface[mask] = griddata(points, values,
                                   np.column_stack([moneyness_grid[mask], time_grid[mask]]),
                                   method='linear')

        return surface

    def _linear_interpolation(self, points: np.ndarray, values: np.ndarray,
                             moneyness_grid: np.ndarray,
                             time_grid: np.ndarray) -> np.ndarray:
        """Linear interpolation"""
        grid_points = np.column_stack([moneyness_grid.ravel(), time_grid.ravel()])
        surface = griddata(points, values, grid_points, method='linear')
        surface = surface.reshape(moneyness_grid.shape)

        # Fill NaN values with nearest neighbor
        mask = np.isnan(surface)
        if np.any(mask):
            surface[mask] = griddata(points, values,
                                   np.column_stack([moneyness_grid[mask], time_grid[mask]]),
                                   method='nearest')

        return surface

    def _smooth_surface(self, surface: np.ndarray) -> np.ndarray:
        """Apply smoothing to surface"""
        # Use Gaussian filter for smoothing
        smoothed = gaussian_filter(surface, sigma=self.smoothing)

        # Preserve original values at data points (optional)
        # This would require keeping track of original point locations

        return smoothed

    # ==========================================================================
    # SURFACE ANALYTICS
    # ==========================================================================

    def _add_surface_analytics(self, surface: VolatilitySurface) -> VolatilitySurface:
        """Add analytics to surface"""
        # Calculate ATM term structure
        surface.atm_term_structure = self._calculate_atm_term_structure(surface)

        # Calculate skew parameters
        surface.skew_parameters = self._calculate_skew_parameters(surface)

        # Calculate smile parameters
        surface.smile_parameters = self._calculate_smile_parameters(surface)

        # Calculate interpolation error
        surface.interpolation_error = self._calculate_interpolation_error(surface)

        return surface

    def _calculate_atm_term_structure(self, surface: VolatilitySurface) -> np.ndarray:
        """Calculate ATM volatility term structure"""
        atm_vols = []

        # For each time slice, find ATM volatility
        for t_idx in range(surface.time_grid.shape[0]):
            # Find moneyness closest to 1.0 (ATM)
            moneyness_slice = surface.moneyness_grid[t_idx, :]
            atm_idx = np.argmin(np.abs(moneyness_slice - 1.0))
            atm_vol = surface.iv_surface[t_idx, atm_idx]
            atm_vols.append(atm_vol)

        return np.array(atm_vols)

    def _calculate_skew_parameters(self, surface: VolatilitySurface) -> dict[datetime, float]:
        """Calculate skew for each expiry"""
        skew_params = {}

        unique_times = np.unique(surface.time_grid)

        for t in unique_times:
            # Get slice for this time
            t_idx = np.where(np.abs(surface.time_grid[:, 0] - t) < 0.001)[0]

            if len(t_idx) == 0:
                continue

            t_idx = t_idx[0]
            moneyness = surface.moneyness_grid[t_idx, :]
            ivs = surface.iv_surface[t_idx, :]

            # Calculate 25-delta skew (simplified)
            otm_put_idx = np.argmin(np.abs(moneyness - 0.95))
            otm_call_idx = np.argmin(np.abs(moneyness - 1.05))

            skew = ivs[otm_put_idx] - ivs[otm_call_idx]

            # Convert time to expiry date (approximate)
            expiry = datetime.now(UTC) + timedelta(days=int(t * 365))
            skew_params[expiry] = skew

        return skew_params

    def _calculate_smile_parameters(self, surface: VolatilitySurface) -> dict[datetime, dict]:
        """Calculate smile parameters for each expiry"""
        smile_params = {}

        unique_times = np.unique(surface.time_grid)

        for t in unique_times:
            # Get slice for this time
            t_idx = np.where(np.abs(surface.time_grid[:, 0] - t) < 0.001)[0]

            if len(t_idx) == 0:
                continue

            t_idx = t_idx[0]
            moneyness = surface.moneyness_grid[t_idx, :]
            ivs = surface.iv_surface[t_idx, :]

            # Fit quadratic to get smile parameters
            try:
                # Use log-moneyness for fitting
                log_moneyness = np.log(moneyness)
                coeffs = np.polyfit(log_moneyness, ivs, 2)

                params = {
                    'curvature': coeffs[0],  # Smile curvature
                    'slope': coeffs[1],      # Skew
                    'level': coeffs[2]       # ATM level
                }

                expiry = datetime.now(UTC) + timedelta(days=int(t * 365))
                smile_params[expiry] = params
            except Exception as e:
                self.logger.debug(f"Smile parameter fit failed for expiry {t:.4f}: {e}")

        return smile_params

    def _calculate_interpolation_error(self, surface: VolatilitySurface) -> float:
        """Calculate interpolation error metric"""
        # This would compare interpolated values with actual data points
        # For now, return a placeholder
        return 0.01

    # ==========================================================================
    # ARBITRAGE DETECTION
    # ==========================================================================

    def _detect_arbitrage(self, surface: VolatilitySurface) -> int:
        """Detect arbitrage opportunities in surface"""
        violations = 0
        self.arbitrage_opportunities = []

        # Check calendar spread arbitrage
        violations += self._check_calendar_arbitrage(surface)

        # Check butterfly arbitrage
        violations += self._check_butterfly_arbitrage(surface)

        # Check vertical spread arbitrage
        violations += self._check_vertical_arbitrage(surface)

        return violations

    def _check_calendar_arbitrage(self, surface: VolatilitySurface) -> int:
        """Check for calendar spread arbitrage"""
        violations = 0

        # Total variance should be increasing with time
        for m_idx in range(surface.moneyness_grid.shape[1]):
            total_variance = surface.iv_surface[:, m_idx]**2 * surface.time_grid[:, 0]

            # Check if variance is increasing
            for t_idx in range(1, len(total_variance)):
                if total_variance[t_idx] < total_variance[t_idx-1] - CALENDAR_SPREAD_THRESHOLD:
                    violations += 1

                    # Create arbitrage opportunity
                    opp = ArbitrageOpportunity(
                        arbitrage_type=ArbitrageType.CALENDAR,
                        strikes=[surface.strikes[m_idx] if m_idx < len(surface.strikes) else surface.underlying_price],  # noqa: E501
                        expiries=[datetime.now(UTC) + timedelta(days=int(surface.time_grid[t_idx-1, 0] * 365)),  # noqa: E501
                                 datetime.now(UTC) + timedelta(days=int(surface.time_grid[t_idx, 0] * 365))],  # noqa: E501
                        current_ivs=[surface.iv_surface[t_idx-1, m_idx], surface.iv_surface[t_idx, m_idx]],  # noqa: E501
                        theoretical_bound=total_variance[t_idx-1],
                        violation_amount=total_variance[t_idx-1] - total_variance[t_idx],
                        profit_potential=100 * (total_variance[t_idx-1] - total_variance[t_idx]),
                        confidence=0.8,
                        trade_setup={'action': 'Buy near, sell far calendar spread'}
                    )
                    self.arbitrage_opportunities.append(opp)

        return violations

    def _check_butterfly_arbitrage(self, surface: VolatilitySurface) -> int:
        """Check for butterfly spread arbitrage"""
        violations = 0

        # Convexity condition: d²σ/dK² >= 0
        for t_idx in range(surface.time_grid.shape[0]):
            moneyness = surface.moneyness_grid[t_idx, :]
            ivs = surface.iv_surface[t_idx, :]

            # Check convexity (simplified using finite differences)
            for m_idx in range(1, len(moneyness)-1):
                butterfly = ivs[m_idx-1] - 2*ivs[m_idx] + ivs[m_idx+1]

                if butterfly < -BUTTERFLY_THRESHOLD:
                    violations += 1

                    # Create arbitrage opportunity
                    strikes = [surface.underlying_price * moneyness[i] for i in [m_idx-1, m_idx, m_idx+1]]  # noqa: E501

                    opp = ArbitrageOpportunity(
                        arbitrage_type=ArbitrageType.BUTTERFLY,
                        strikes=strikes,
                        expiries=[datetime.now(UTC) + timedelta(days=int(surface.time_grid[t_idx, 0] * 365))],  # noqa: E501
                        current_ivs=[ivs[m_idx-1], ivs[m_idx], ivs[m_idx+1]],
                        theoretical_bound=0,
                        violation_amount=abs(butterfly),
                        profit_potential=100 * abs(butterfly),
                        confidence=0.7,
                        trade_setup={'action': 'Buy butterfly spread'}
                    )
                    self.arbitrage_opportunities.append(opp)

        return violations

    def _check_vertical_arbitrage(self, surface: VolatilitySurface) -> int:
        """Check for vertical spread arbitrage"""
        violations = 0

        # IV should be positive and reasonable
        mask = (surface.iv_surface < MIN_IV) | (surface.iv_surface > MAX_IV)
        violations = np.sum(mask)

        return violations

    # ==========================================================================
    # ANALYSIS METHODS
    # ==========================================================================

    def analyze_surface(self, symbol: str) -> SurfaceAnalytics:
        """
        Comprehensive surface analysis

        Args:
            symbol: Symbol to analyze

        Returns:
            SurfaceAnalytics object
        """
        if symbol not in self.surfaces:
            raise ValueError(f"No surface available for {symbol}")

        surface = self.surfaces[symbol]

        # Analyze term structure
        term_shape, term_slope = self._analyze_term_structure(surface)

        # Analyze skew
        skew_pattern, skew_metrics = self._analyze_skew(surface)

        # Analyze smile
        smile_metrics = self._analyze_smile(surface)

        # Calculate surface quality
        quality_metrics = self._calculate_surface_quality(surface)

        # Find rich/cheap strikes
        rich_strikes, cheap_strikes = self._find_mispricings(surface)

        analytics = SurfaceAnalytics(
            term_structure_shape=term_shape,
            term_structure_slope=term_slope,
            skew_pattern=skew_pattern,
            skew_steepness=skew_metrics['steepness'],
            put_wing_slope=skew_metrics['put_wing'],
            call_wing_slope=skew_metrics['call_wing'],
            smile_curvature=smile_metrics['curvature'],
            atm_volatility=smile_metrics['atm_vol'],
            risk_reversal_25d=smile_metrics['risk_reversal'],
            butterfly_25d=smile_metrics['butterfly'],
            smoothness_score=quality_metrics['smoothness'],
            data_coverage=quality_metrics['coverage'],
            interpolation_quality=quality_metrics['interpolation'],
            rich_strikes=rich_strikes,
            cheap_strikes=cheap_strikes,
            arbitrage_opportunities=self.arbitrage_opportunities
        )

        return analytics

    def get_term_structure_snapshot(self, symbol: str = "SPY") -> dict[str, Any]:
        """Return a compact term-structure snapshot for downstream gating."""
        surface = self.surfaces.get(symbol)
        if surface is None:
            raise ValueError(f"No surface available for {symbol}")

        if surface.atm_term_structure.size == 0:
            surface.atm_term_structure = self._calculate_atm_term_structure(surface)

        analytics = self.analyze_surface(symbol)
        unique_times = np.unique(surface.time_grid[:, 0])
        if unique_times.size == 0 or surface.atm_term_structure.size == 0:
            raise ValueError(f"Term structure unavailable for {symbol}")

        node_0 = self._sample_atm_node(surface, unique_times, target_days=0.0)
        node_1 = self._sample_atm_node(surface, unique_times, target_days=1.0)
        node_7 = self._sample_atm_node(surface, unique_times, target_days=7.0)
        node_30 = self._sample_atm_node(surface, unique_times, target_days=30.0)

        surface_ts = surface.timestamp
        if surface_ts.tzinfo is None:
            # Preserve historical naive-datetime behavior used by existing snapshots/tests.
            age_ms = max(0, int((datetime.now() - surface_ts).total_seconds() * 1000))  # spyder: naive-ok
        else:
            age_ms = max(0, int((datetime.now(UTC) - surface_ts.astimezone(UTC)).total_seconds() * 1000))
        coverage = float(np.count_nonzero(np.isfinite(surface.iv_surface)) / surface.iv_surface.size)  # noqa: E501
        age_penalty = 1.0 if age_ms <= 60000 else max(0.0, 1.0 - min(age_ms - 60000, 240000) / 240000.0)  # noqa: E501
        surface_confidence = max(0.0, min(1.0, coverage * age_penalty))

        return {
            "underlying": symbol,
            "atm_iv_0dte": node_0,
            "atm_iv_1dte": node_1,
            "atm_iv_7dte": node_7,
            "atm_iv_30dte": node_30,
            "term_slope_0_7": self._annualized_slope(node_0, node_7, 0.0, 7.0),
            "term_slope_7_30": self._annualized_slope(node_7, node_30, 7.0, 30.0),
            "rr_25d": analytics.risk_reversal_25d,
            "fly_25d": analytics.butterfly_25d,
            "surface_confidence": surface_confidence,
            "surface_age_ms": age_ms,
            "snapshot_ts": surface.timestamp.isoformat(),
        }

    def _sample_atm_node(
        self,
        surface: VolatilitySurface,
        unique_times: np.ndarray,
        target_days: float,
    ) -> float:
        """Sample the ATM term structure at the nearest requested DTE node."""
        target_years = max(0.0, target_days) / 365.0
        index = int(np.argmin(np.abs(unique_times - target_years)))
        return float(surface.atm_term_structure[index])

    def _annualized_slope(
        self,
        start_value: float,
        end_value: float,
        start_days: float,
        end_days: float,
    ) -> float:
        """Compute annualized slope between two DTE nodes."""
        delta_days = end_days - start_days
        if delta_days <= 0:
            return 0.0
        return float((end_value - start_value) / (delta_days / 365.0))

    def _analyze_term_structure(self, surface: VolatilitySurface) -> tuple[str, float]:
        """Analyze term structure shape"""
        atm_vols = surface.atm_term_structure

        if len(atm_vols) < 2:
            return 'flat', 0.0

        # Calculate slope
        times = np.unique(surface.time_grid[:, 0])
        slope = np.polyfit(times, atm_vols, 1)[0]

        # Determine shape
        if slope > 0.05:
            shape = 'contango'
        elif slope < -0.05:
            shape = 'backwardation'
        else:
            shape = 'flat'

        return shape, slope

    def _analyze_skew(self, surface: VolatilitySurface) -> tuple[SkewPattern, dict]:
        """Analyze volatility skew"""
        # Average skew across time
        avg_skew = np.mean(list(surface.skew_parameters.values()))

        # Determine pattern
        if avg_skew > 0.02:
            pattern = SkewPattern.NORMAL
        elif avg_skew < -0.02:
            pattern = SkewPattern.REVERSE
        else:
            pattern = SkewPattern.FLAT

        # Calculate wing slopes
        metrics = {
            'steepness': abs(avg_skew),
            'put_wing': 0.0,  # Would calculate from surface
            'call_wing': 0.0  # Would calculate from surface
        }

        return pattern, metrics

    def _analyze_smile(self, surface: VolatilitySurface) -> dict:
        """Analyze volatility smile"""
        # Average smile parameters
        if surface.smile_parameters:
            avg_curvature = np.mean([p['curvature'] for p in surface.smile_parameters.values()])
            avg_level = np.mean([p['level'] for p in surface.smile_parameters.values()])
        else:
            avg_curvature = 0.0
            avg_level = 0.20

        metrics = {
            'curvature': avg_curvature,
            'atm_vol': avg_level,
            'risk_reversal': 0.0,  # Would calculate 25-delta risk reversal
            'butterfly': 0.0       # Would calculate 25-delta butterfly
        }

        return metrics

    def _calculate_surface_quality(self, surface: VolatilitySurface) -> dict:
        """Calculate surface quality metrics"""
        # Smoothness: measure of second derivatives
        dx = np.gradient(surface.iv_surface, axis=1)
        dy = np.gradient(surface.iv_surface, axis=0)
        smoothness = 1.0 / (1.0 + np.std(dx) + np.std(dy))

        # Coverage: percentage of grid with data
        coverage = surface.data_points / (surface.iv_surface.size * 0.1)
        coverage = min(1.0, coverage)

        # Interpolation quality
        interp_quality = 1.0 / (1.0 + surface.interpolation_error)

        return {
            'smoothness': smoothness,
            'coverage': coverage,
            'interpolation': interp_quality
        }

    def _find_mispricings(self, surface: VolatilitySurface) -> tuple[list, list]:
        """Find rich and cheap strikes"""
        rich_strikes = []
        cheap_strikes = []

        # This would compare surface with theoretical values
        # For now, return empty lists

        return rich_strikes, cheap_strikes

    # ==========================================================================
    # VISUALIZATION
    # ==========================================================================

    def plot_surface_3d(self, symbol: str, interactive: bool = True) -> None:
        """
        Plot 3D volatility surface

        Args:
            symbol: Symbol to plot
            interactive: Use interactive plotly (True) or static matplotlib (False)
        """
        if symbol not in self.surfaces:
            raise ValueError(f"No surface available for {symbol}")

        surface = self.surfaces[symbol]

        if interactive:
            self._plot_interactive_surface(surface)
        else:
            self._plot_static_surface(surface)

    def _plot_interactive_surface(self, surface: VolatilitySurface) -> None:
        """Create interactive 3D surface plot using plotly"""
        fig = go.Figure(data=[go.Surface(
            x=surface.moneyness_grid,
            y=surface.time_grid,
            z=surface.iv_surface,
            colorscale='Viridis',
            name='IV Surface'
        )])

        fig.update_layout(
            title=f'{surface.symbol} Implied Volatility Surface',
            scene=dict(
                xaxis_title='Moneyness (K/S)',
                yaxis_title='Time to Expiry (Years)',
                zaxis_title='Implied Volatility',
                camera=dict(
                    eye=dict(x=1.5, y=1.5, z=1.5)
                )
            ),
            width=1000,
            height=800
        )

        fig.show()

    def _plot_static_surface(self, surface: VolatilitySurface) -> None:
        """Create static 3D surface plot using matplotlib"""
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')

        # Plot surface
        surf = ax.plot_surface(
            surface.moneyness_grid,
            surface.time_grid,
            surface.iv_surface,
            cmap='viridis',
            alpha=0.8
        )

        # Labels and title
        ax.set_xlabel('Moneyness (K/S)')
        ax.set_ylabel('Time to Expiry (Years)')
        ax.set_zlabel('Implied Volatility')
        ax.set_title(f'{surface.symbol} Implied Volatility Surface')

        # Add colorbar
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5)

        plt.show()

    def plot_term_structure(self, symbol: str) -> None:
        """Plot ATM term structure"""
        if symbol not in self.surfaces:
            raise ValueError(f"No surface available for {symbol}")

        surface = self.surfaces[symbol]
        times = np.unique(surface.time_grid[:, 0])

        plt.figure(figsize=(10, 6))
        plt.plot(times * 365, surface.atm_term_structure, 'b-', linewidth=2)
        plt.xlabel('Days to Expiry')
        plt.ylabel('ATM Implied Volatility')
        plt.title(f'{symbol} ATM Volatility Term Structure')
        plt.grid(True, alpha=0.3)
        plt.show()

    def plot_smile(self, symbol: str, time_to_expiry: float) -> None:
        """Plot volatility smile for specific expiry"""
        if symbol not in self.surfaces:
            raise ValueError(f"No surface available for {symbol}")

        surface = self.surfaces[symbol]

        # Find closest time slice
        t_idx = np.argmin(np.abs(surface.time_grid[:, 0] - time_to_expiry))

        moneyness = surface.moneyness_grid[t_idx, :]
        ivs = surface.iv_surface[t_idx, :]

        plt.figure(figsize=(10, 6))
        plt.plot(moneyness, ivs, 'b-', linewidth=2)
        plt.xlabel('Moneyness (K/S)')
        plt.ylabel('Implied Volatility')
        plt.title(f'{symbol} Volatility Smile (T={time_to_expiry:.2f} years)')
        plt.grid(True, alpha=0.3)
        plt.axvline(x=1.0, color='r', linestyle='--', alpha=0.5, label='ATM')
        plt.legend()
        plt.show()

# ==============================================================================
# TEST/DEMO CODE
# ==============================================================================
def _demo() -> None:
    """Run a standalone demo with synthetic options data."""
    builder = VolatilitySurfaceBuilder()

    sample_strikes = np.arange(550, 621, 5)
    sample_expiries = [
        datetime.now(UTC) + timedelta(days=7),
        datetime.now(UTC) + timedelta(days=14),
        datetime.now(UTC) + timedelta(days=30),
        datetime.now(UTC) + timedelta(days=60),
        datetime.now(UTC) + timedelta(days=90),
    ]

    sample_rows: list[dict[str, Any]] = []
    sample_underlying = 585.0

    for sample_expiry in sample_expiries:
        time_to_exp = (sample_expiry - datetime.now(UTC)).days / 365.0

        for sample_strike in sample_strikes:
            sample_moneyness = sample_strike / sample_underlying
            base_iv = 0.15 + 0.05 * time_to_exp
            smile = 0.02 * (np.log(sample_moneyness)) ** 2
            skew = -0.05 * (sample_moneyness - 1.0)

            sample_iv = base_iv + smile + skew + np.random.normal(0, 0.005)
            sample_iv = max(0.05, min(0.50, sample_iv))

            sample_rows.append(
                {
                    'strike': sample_strike,
                    'expiry': sample_expiry,
                    'option_type': 'CALL',
                    'implied_volatility': sample_iv,
                    'volume': np.random.randint(100, 5000),
                    'open_interest': np.random.randint(1000, 10000),
                }
            )

    sample_df = pd.DataFrame(sample_rows)
    builder.build_surface(
        symbol='SPY',
        options_data=sample_df,
        underlying_price=sample_underlying,
        risk_free_rate=0.05,
    )
    analytics = builder.analyze_surface('SPY')
    for _opp in analytics.arbitrage_opportunities[:3]:
        pass


if __name__ == "__main__":
    _demo()

