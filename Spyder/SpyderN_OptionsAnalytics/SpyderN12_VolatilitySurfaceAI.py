#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderN_OptionsAnalytics
Module: SpyderN12_VolatilitySurfaceAI.py
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
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, field
from collections import deque
import asyncio
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import joblib

warnings.filterwarnings("ignore")

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
# Scientific computing
from scipy import interpolate  # noqa: E402
from scipy.optimize import minimize  # noqa: E402
from scipy.stats import norm  # noqa: E402
from scipy.signal import savgol_filter  # noqa: E402

# Machine Learning
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.optim as optim  # noqa: E402
from sklearn.ensemble import RandomForestRegressor  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

# Visualization
import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

# Quantitative Finance
try:
    import QuantLib as ql  # noqa: F401

    QUANTLIB_AVAILABLE = True
except ImportError:
    QUANTLIB_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger  # noqa: E402
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler  # noqa: E402
from Spyder.SpyderF_Analysis.SpyderF06_GreeksCalculator import GreeksCalculator  # noqa: E402
from Spyder.SpyderC_MarketData.SpyderC03_OptionChain import OptionChain  # noqa: E402
import logging  # noqa: E402

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Model parameters
SURFACE_GRID_SIZE = 50  # Strike x Expiry grid
MIN_MONEYNESS = 0.7  # 70% of spot
MAX_MONEYNESS = 1.3  # 130% of spot
MAX_TENOR_DAYS = 365  # Maximum expiry
SMOOTHING_FACTOR = 0.95

# SABR model parameters
SABR_ALPHA_INIT = 0.3
SABR_BETA = 0.5
SABR_RHO_INIT = -0.3
SABR_NU_INIT = 0.4

# ML parameters
LSTM_HIDDEN_SIZE = 128
LSTM_NUM_LAYERS = 3
RF_N_ESTIMATORS = 100
LOOKBACK_WINDOW = 20


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class VolatilityPoint:
    """Single point on volatility surface"""

    strike: float
    expiry: datetime
    moneyness: float
    time_to_maturity: float
    implied_vol: float
    bid_vol: float | None = None
    ask_vol: float | None = None
    volume: int = 0
    open_interest: int = 0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VolatilitySurface:
    """Complete volatility surface representation"""

    spot_price: float
    surface_time: datetime
    strikes: np.ndarray
    expiries: np.ndarray
    implied_vols: np.ndarray  # 2D array [strikes x expiries]
    moneyness_grid: np.ndarray
    time_grid: np.ndarray
    bid_vols: np.ndarray | None = None
    ask_vols: np.ndarray | None = None

    def get_vol(self, strike: float, expiry: float) -> float:
        """Interpolate volatility for given strike and expiry"""
        # Bilinear interpolation
        f = interpolate.interp2d(
            self.expiries, self.strikes, self.implied_vols, kind="linear"
        )
        return float(f(expiry, strike))

    def get_smile(self, expiry: float) -> tuple[np.ndarray, np.ndarray]:
        """Get volatility smile for given expiry"""
        idx = np.argmin(np.abs(self.expiries - expiry))
        return self.strikes, self.implied_vols[:, idx]

    def get_term_structure(self, strike: float) -> tuple[np.ndarray, np.ndarray]:
        """Get term structure for given strike"""
        idx = np.argmin(np.abs(self.strikes - strike))
        return self.expiries, self.implied_vols[idx, :]


@dataclass
class SurfaceMetrics:
    """Volatility surface analytics"""

    atm_vol: float
    skew: float  # 25-delta risk reversal
    kurtosis: float  # 25-delta butterfly
    term_structure_slope: float
    surface_smoothness: float
    arbitrage_violations: list[dict[str, Any]]
    smile_asymmetry: float


# ==============================================================================
# SABR MODEL
# ==============================================================================
class SABRModel:
    """SABR stochastic volatility model for baseline surface"""

    def __init__(self):
        self.alpha = SABR_ALPHA_INIT
        self.beta = SABR_BETA
        self.rho = SABR_RHO_INIT
        self.nu = SABR_NU_INIT
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)

    def implied_vol(self, F: float, K: float, T: float) -> float:
        """Calculate SABR implied volatility"""
        if K <= 0 or F <= 0 or T <= 0:
            return 0.0

        # Handle ATM case
        if abs(F - K) < 1e-6:
            return self.alpha * (F ** (self.beta - 1))

        # SABR formula
        FK = F * K
        z = (self.nu / self.alpha) * (FK ** ((1 - self.beta) / 2)) * np.log(F / K)
        x = np.log(
            (np.sqrt(1 - 2 * self.rho * z + z**2) + z - self.rho) / (1 - self.rho)
        )

        A = self.alpha / (
            (FK ** ((1 - self.beta) / 2))
            * (
                1
                + ((1 - self.beta) ** 2 / 24) * (np.log(F / K)) ** 2
                + ((1 - self.beta) ** 4 / 1920) * (np.log(F / K)) ** 4
            )
        )

        B = 1 + T * (
            (self.alpha**2 * (1 - self.beta) ** 2) / (24 * FK ** (1 - self.beta))
            + (self.rho * self.beta * self.nu * self.alpha)
            / (4 * FK ** ((1 - self.beta) / 2))
            + (self.nu**2 * (2 - 3 * self.rho**2)) / 24
        )

        if abs(x) < 1e-6:
            return self.alpha * (F ** (self.beta - 1)) * B

        return A * (z / x) * B

    def calibrate(
        self, market_data: list[VolatilityPoint], spot: float
    ) -> dict[str, float]:
        """Calibrate SABR parameters to market data"""

        def objective(params):
            self.alpha, self.rho, self.nu = params

            error = 0
            for point in market_data:
                F = spot  # Forward price (simplified)
                model_vol = self.implied_vol(F, point.strike, point.time_to_maturity)
                error += (model_vol - point.implied_vol) ** 2

            return error

        # Constraints
        bounds = [(0.01, 1.0), (-0.999, 0.999), (0.01, 2.0)]

        # Optimize
        result = minimize(
            objective,
            x0=[self.alpha, self.rho, self.nu],
            bounds=bounds,
            method="L-BFGS-B",
        )

        if result.success:
            self.alpha, self.rho, self.nu = result.x
            self.logger.info(
                f"SABR calibrated: α={self.alpha:.3f}, ρ={self.rho:.3f}, ν={self.nu:.3f}"
            )

        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "rho": self.rho,
            "nu": self.nu,
            "error": result.fun,
        }


# ==============================================================================
# NEURAL NETWORK MODELS
# ==============================================================================
class VolatilitySurfaceLSTM(nn.Module):
    """LSTM network for volatility surface dynamics"""

    def __init__(
        self,
        input_size: int,
        hidden_size: int = LSTM_HIDDEN_SIZE,
        num_layers: int = LSTM_NUM_LAYERS,
        output_size: int = SURFACE_GRID_SIZE,
    ):
        super().__init__()

        self.hidden_size = hidden_size
        self.num_layers = num_layers

        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2,
        )

        # Attention mechanism
        self.attention = nn.MultiheadAttention(hidden_size, num_heads=8)

        # Output layers
        self.fc1 = nn.Linear(hidden_size, hidden_size * 2)
        self.fc2 = nn.Linear(hidden_size * 2, output_size * output_size)

        # Activation functions
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.3)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x: torch.Tensor, hidden: tuple | None = None) -> torch.Tensor:
        # LSTM forward pass
        lstm_out, hidden = self.lstm(x, hidden)

        # Apply attention
        attended, _ = self.attention(lstm_out, lstm_out, lstm_out)

        # Combine LSTM output and attention
        combined = lstm_out + attended

        # Take last timestep
        last_hidden = combined[:, -1, :]

        # Dense layers
        out = self.fc1(last_hidden)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)

        # Reshape to surface grid
        batch_size = x.shape[0]
        out = out.view(batch_size, SURFACE_GRID_SIZE, SURFACE_GRID_SIZE)

        # Ensure positive volatilities
        out = self.sigmoid(out) * 0.8 + 0.05  # Between 5% and 85%

        return out


# ==============================================================================
# VOLATILITY SURFACE AI
# ==============================================================================
class VolatilitySurfaceAI:
    """
    AI-enhanced volatility surface modeling and prediction.

    Combines SABR model, LSTM networks, and Random Forests for
    comprehensive volatility surface analysis and prediction.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize volatility surface AI"""
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()

        # Configuration
        self.config = config or {}
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Models
        self.sabr_model = SABRModel()
        self.lstm_model = None
        self.rf_model = None
        self.greeks_calculator = GreeksCalculator()

        # Data storage
        self.surface_history = deque(maxlen=100)
        self.current_surface = None
        self.last_update = None

        # Scalers for ML
        self.input_scaler = StandardScaler()
        self.output_scaler = StandardScaler()

        # Initialize models
        self._initialize_models()

        self.logger.info("✅ Volatility Surface AI initialized")

    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================

    def _initialize_models(self):
        """Initialize ML models"""
        # LSTM model
        input_size = 10  # spot, volume, vix, skew, etc.
        self.lstm_model = VolatilitySurfaceLSTM(
            input_size=input_size, output_size=SURFACE_GRID_SIZE
        ).to(self.device)

        self.lstm_optimizer = optim.Adam(self.lstm_model.parameters(), lr=1e-3)
        self.lstm_criterion = nn.MSELoss()

        # Random Forest for surface characteristics
        self.rf_model = RandomForestRegressor(
            n_estimators=RF_N_ESTIMATORS, max_depth=10, random_state=42, n_jobs=-1
        )

        self.logger.info("Initialized LSTM and Random Forest models")

    # ==========================================================================
    # SURFACE CONSTRUCTION
    # ==========================================================================

    async def build_surface(
        self, option_chain: OptionChain, spot_price: float, risk_free_rate: float = 0.05
    ) -> VolatilitySurface:
        """
        Build volatility surface from option chain data.

        Args:
            option_chain: Options chain data
            spot_price: Current spot price
            risk_free_rate: Risk-free interest rate

        Returns:
            Complete volatility surface
        """
        try:
            self.logger.info(f"Building volatility surface for spot={spot_price:.2f}")

            # Extract market data points
            market_points = self._extract_market_points(option_chain, spot_price)

            # Calibrate SABR model
            if len(market_points) > 10:
                self.sabr_model.calibrate(market_points, spot_price)

            # Create surface grid
            strikes, expiries, moneyness_grid, time_grid = self._create_surface_grid(
                spot_price, market_points
            )

            # Build initial surface with SABR
            sabr_surface = self._build_sabr_surface(strikes, expiries, spot_price)

            # Enhance with ML if we have history
            if len(self.surface_history) >= LOOKBACK_WINDOW:
                ml_adjustment = await self._predict_surface_adjustment(
                    spot_price, market_points
                )
                enhanced_surface = sabr_surface + ml_adjustment
            else:
                enhanced_surface = sabr_surface

            # Apply market constraints
            final_surface = self._apply_market_constraints(
                enhanced_surface, market_points, strikes, expiries
            )

            # Create surface object
            surface = VolatilitySurface(
                spot_price=spot_price,
                surface_time=datetime.now(timezone.utc),
                strikes=strikes,
                expiries=expiries,
                implied_vols=final_surface,
                moneyness_grid=moneyness_grid,
                time_grid=time_grid,
            )

            # Update history
            self.current_surface = surface
            self.surface_history.append(surface)
            self.last_update = datetime.now(timezone.utc)

            # Calculate metrics
            metrics = self._calculate_surface_metrics(surface)

            self.logger.info(
                f"Surface built: ATM Vol={metrics.atm_vol:.1%}, "
                f"Skew={metrics.skew:.3f}, Smoothness={metrics.surface_smoothness:.3f}"
            )

            return surface

        except Exception as e:
            self.error_handler.handle_error(
                e, {"method": "build_surface", "spot": spot_price}
            )
            return None

    def _extract_market_points(
        self, option_chain: OptionChain, spot_price: float
    ) -> list[VolatilityPoint]:
        """Extract volatility points from option chain"""
        points = []

        for expiry, options in option_chain.expirations.items():
            time_to_maturity = (expiry - datetime.now(timezone.utc)).days / 365.0

            if time_to_maturity <= 0:
                continue

            for strike, option_data in options.items():
                # Use mid-market IV
                if "iv" in option_data:
                    iv = option_data["iv"]
                else:
                    # Calculate from prices if needed
                    call_price = (
                        option_data.get("call_bid", 0) + option_data.get("call_ask", 0)
                    ) / 2
                    if call_price > 0:
                        iv = self._implied_volatility_bs(
                            call_price,
                            spot_price,
                            strike,
                            time_to_maturity,
                            0.05,
                            "call",
                        )
                    else:
                        continue

                if iv > 0:
                    points.append(
                        VolatilityPoint(
                            strike=strike,
                            expiry=expiry,
                            moneyness=strike / spot_price,
                            time_to_maturity=time_to_maturity,
                            implied_vol=iv,
                            volume=option_data.get("volume", 0),
                            open_interest=option_data.get("open_interest", 0),
                        )
                    )

        return points

    def _create_surface_grid(
        self, spot_price: float, market_points: list[VolatilityPoint]
    ) -> tuple:
        """Create strike and expiry grid for surface"""
        # Strike grid (in terms of moneyness)
        min_strike = spot_price * MIN_MONEYNESS
        max_strike = spot_price * MAX_MONEYNESS
        strikes = np.linspace(min_strike, max_strike, SURFACE_GRID_SIZE)

        # Expiry grid (in years)
        max_expiry = min(
            MAX_TENOR_DAYS / 365.0, max(p.time_to_maturity for p in market_points) * 1.2
        )
        expiries = np.linspace(0.01, max_expiry, SURFACE_GRID_SIZE)

        # Create grids
        strike_grid, expiry_grid = np.meshgrid(strikes, expiries, indexing="ij")
        moneyness_grid = strike_grid / spot_price
        time_grid = expiry_grid

        return strikes, expiries, moneyness_grid, time_grid

    def _build_sabr_surface(
        self, strikes: np.ndarray, expiries: np.ndarray, spot_price: float
    ) -> np.ndarray:
        """Build surface using calibrated SABR model"""
        surface = np.zeros((len(strikes), len(expiries)))

        for i, strike in enumerate(strikes):
            for j, expiry in enumerate(expiries):
                surface[i, j] = self.sabr_model.implied_vol(spot_price, strike, expiry)

        # Apply smoothing
        surface = savgol_filter(surface, window_length=5, polyorder=3, axis=0)
        surface = savgol_filter(surface, window_length=5, polyorder=3, axis=1)

        return surface

    # ==========================================================================
    # MACHINE LEARNING PREDICTION
    # ==========================================================================

    async def _predict_surface_adjustment(
        self, spot_price: float, market_points: list[VolatilityPoint]
    ) -> np.ndarray:
        """Predict surface adjustment using LSTM"""
        try:
            # Prepare features
            features = self._prepare_ml_features(spot_price, market_points)

            # LSTM prediction
            with torch.no_grad():
                features_tensor = (
                    torch.tensor(features, dtype=torch.float32)
                    .unsqueeze(0)
                    .to(self.device)
                )

                adjustment = self.lstm_model(features_tensor)
                adjustment = adjustment.squeeze(0).cpu().numpy()

            # Scale adjustment
            adjustment = (adjustment - 0.5) * 0.1  # ±10% adjustment

            return adjustment

        except Exception as e:
            self.logger.error("ML prediction error: %s", e)
            return np.zeros((SURFACE_GRID_SIZE, SURFACE_GRID_SIZE))

    def _prepare_ml_features(
        self, spot_price: float, market_points: list[VolatilityPoint]
    ) -> np.ndarray:
        """Prepare features for ML models"""
        features = []

        # Recent surface history
        for surface in list(self.surface_history)[-LOOKBACK_WINDOW:]:
            surf_features = [
                surface.spot_price / spot_price,  # Relative spot change
                np.mean(surface.implied_vols),  # Average IV
                np.std(surface.implied_vols),  # IV dispersion
                self._calculate_skew(surface),  # Skew
                self._calculate_term_slope(surface),  # Term structure
            ]

            # Add market microstructure
            if market_points:
                surf_features.extend(
                    [
                        np.mean([p.volume for p in market_points]),
                        np.mean([p.open_interest for p in market_points]),
                        len(market_points),  # Number of active strikes
                    ]
                )
            else:
                surf_features.extend([0, 0, 0])

            # Pad to fixed size
            while len(surf_features) < 10:
                surf_features.append(0)

            features.append(surf_features[:10])

        # Pad if not enough history
        while len(features) < LOOKBACK_WINDOW:
            features.insert(0, features[0] if features else [0] * 10)

        return np.array(features[-LOOKBACK_WINDOW:])

    def _calculate_skew(self, surface: VolatilitySurface) -> float:
        """Calculate 25-delta risk reversal"""
        atm_idx = len(surface.strikes) // 2
        put_25d_idx = int(atm_idx * 0.75)
        call_25d_idx = int(atm_idx * 1.25)

        # Use 1-month expiry
        expiry_idx = min(
            int(30 / 365 * len(surface.expiries)), len(surface.expiries) - 1
        )

        put_vol = surface.implied_vols[put_25d_idx, expiry_idx]
        call_vol = surface.implied_vols[call_25d_idx, expiry_idx]

        return call_vol - put_vol

    def _calculate_term_slope(self, surface: VolatilitySurface) -> float:
        """Calculate term structure slope"""
        atm_idx = len(surface.strikes) // 2

        # 1-month vs 1-year
        one_month_idx = min(
            int(30 / 365 * len(surface.expiries)), len(surface.expiries) - 1
        )
        one_year_idx = len(surface.expiries) - 1

        short_vol = surface.implied_vols[atm_idx, one_month_idx]
        long_vol = surface.implied_vols[atm_idx, one_year_idx]

        return (long_vol - short_vol) / short_vol

    # ==========================================================================
    # SURFACE CONSTRAINTS AND ARBITRAGE
    # ==========================================================================

    def _apply_market_constraints(
        self,
        surface: np.ndarray,
        market_points: list[VolatilityPoint],
        strikes: np.ndarray,
        expiries: np.ndarray,
    ) -> np.ndarray:
        """Apply market constraints and remove arbitrage"""
        # Fit to market points
        for point in market_points:
            # Find nearest grid point
            strike_idx = np.argmin(np.abs(strikes - point.strike))
            expiry_idx = np.argmin(np.abs(expiries - point.time_to_maturity))

            # Blend with market data
            weight = 0.8  # 80% market, 20% model
            surface[strike_idx, expiry_idx] = (
                weight * point.implied_vol
                + (1 - weight) * surface[strike_idx, expiry_idx]
            )

        # Apply no-arbitrage constraints
        surface = self._enforce_no_arbitrage(surface, strikes, expiries)

        # Ensure positive volatilities
        surface = np.maximum(surface, 0.05)

        # Final smoothing
        surface = savgol_filter(surface, window_length=5, polyorder=3, axis=0)
        surface = savgol_filter(surface, window_length=5, polyorder=3, axis=1)

        return surface

    def _enforce_no_arbitrage(
        self, surface: np.ndarray, strikes: np.ndarray, expiries: np.ndarray
    ) -> np.ndarray:
        """Enforce no-arbitrage constraints"""
        # Calendar spread arbitrage: vol should increase with time
        for i in range(len(strikes)):
            for j in range(1, len(expiries)):
                if surface[i, j] < surface[i, j - 1]:
                    surface[i, j] = surface[i, j - 1] * 1.001

        # Butterfly arbitrage: convexity constraint
        for j in range(len(expiries)):
            for i in range(1, len(strikes) - 1):
                # Second derivative should be positive
                d2v = surface[i + 1, j] - 2 * surface[i, j] + surface[i - 1, j]
                if d2v < 0:
                    # Adjust middle point
                    surface[i, j] = (surface[i - 1, j] + surface[i + 1, j]) / 2

        return surface

    # ==========================================================================
    # SURFACE ANALYTICS
    # ==========================================================================

    def _calculate_surface_metrics(self, surface: VolatilitySurface) -> SurfaceMetrics:
        """Calculate comprehensive surface metrics"""
        # ATM volatility
        atm_idx = len(surface.strikes) // 2
        one_month_idx = min(
            int(30 / 365 * len(surface.expiries)), len(surface.expiries) - 1
        )
        atm_vol = surface.implied_vols[atm_idx, one_month_idx]

        # Skew (25-delta risk reversal)
        skew = self._calculate_skew(surface)

        # Kurtosis (25-delta butterfly)
        put_25d_idx = int(atm_idx * 0.75)
        call_25d_idx = int(atm_idx * 1.25)
        put_vol = surface.implied_vols[put_25d_idx, one_month_idx]
        call_vol = surface.implied_vols[call_25d_idx, one_month_idx]
        kurtosis = (put_vol + call_vol) / 2 - atm_vol

        # Term structure slope
        term_slope = self._calculate_term_slope(surface)

        # Surface smoothness (lower is smoother)
        smoothness = np.mean(np.abs(np.gradient(np.gradient(surface.implied_vols))))

        # Detect arbitrage violations
        violations = self._detect_arbitrage_violations(surface)

        # Smile asymmetry
        smile_left = surface.implied_vols[:atm_idx, one_month_idx]
        smile_right = surface.implied_vols[atm_idx:, one_month_idx]
        asymmetry = np.mean(smile_right) - np.mean(smile_left)

        return SurfaceMetrics(
            atm_vol=atm_vol,
            skew=skew,
            kurtosis=kurtosis,
            term_structure_slope=term_slope,
            surface_smoothness=smoothness,
            arbitrage_violations=violations,
            smile_asymmetry=asymmetry,
        )

    def _detect_arbitrage_violations(self, surface: VolatilitySurface) -> list[dict]:
        """Detect arbitrage opportunities in surface"""
        violations = []

        # Check calendar spreads
        for i in range(len(surface.strikes)):
            for j in range(1, len(surface.expiries)):
                if surface.implied_vols[i, j] < surface.implied_vols[i, j - 1]:
                    violations.append(
                        {
                            "type": "calendar_spread",
                            "strike": surface.strikes[i],
                            "near_expiry": surface.expiries[j - 1],
                            "far_expiry": surface.expiries[j],
                            "near_vol": surface.implied_vols[i, j - 1],
                            "far_vol": surface.implied_vols[i, j],
                        }
                    )

        # Check butterfly spreads
        for j in range(len(surface.expiries)):
            for i in range(1, len(surface.strikes) - 1):
                butterfly_value = (
                    surface.implied_vols[i - 1, j]
                    + surface.implied_vols[i + 1, j]
                    - 2 * surface.implied_vols[i, j]
                )
                if butterfly_value < -0.01:  # Threshold
                    violations.append(
                        {
                            "type": "butterfly_spread",
                            "expiry": surface.expiries[j],
                            "strikes": [
                                surface.strikes[i - 1],
                                surface.strikes[i],
                                surface.strikes[i + 1],
                            ],
                            "butterfly_value": butterfly_value,
                        }
                    )

        return violations

    # ==========================================================================
    # GREEKS SURFACES
    # ==========================================================================

    def calculate_greeks_surfaces(
        self,
        vol_surface: VolatilitySurface,
        spot_price: float,
        risk_free_rate: float = 0.05,
    ) -> dict[str, np.ndarray]:
        """Calculate Greeks surfaces (delta, gamma, vega, theta)"""
        greeks_surfaces = {
            "delta": np.zeros_like(vol_surface.implied_vols),
            "gamma": np.zeros_like(vol_surface.implied_vols),
            "vega": np.zeros_like(vol_surface.implied_vols),
            "theta": np.zeros_like(vol_surface.implied_vols),
        }

        for i, strike in enumerate(vol_surface.strikes):
            for j, expiry in enumerate(vol_surface.expiries):
                iv = vol_surface.implied_vols[i, j]

                # Calculate Greeks
                greeks = self.greeks_calculator.calculate_greeks(
                    spot=spot_price,
                    strike=strike,
                    time_to_expiry=expiry,
                    volatility=iv,
                    risk_free_rate=risk_free_rate,
                    option_type="call",
                )

                greeks_surfaces["delta"][i, j] = greeks["delta"]
                greeks_surfaces["gamma"][i, j] = greeks["gamma"]
                greeks_surfaces["vega"][i, j] = greeks["vega"]
                greeks_surfaces["theta"][i, j] = greeks["theta"]

        return greeks_surfaces

    # ==========================================================================
    # VISUALIZATION
    # ==========================================================================

    def plot_surface_3d(
        self, surface: VolatilitySurface, title: str = "Implied Volatility Surface"
    ) -> go.Figure:
        """Create interactive 3D surface plot"""
        fig = go.Figure(
            data=[
                go.Surface(
                    x=surface.expiries * 365,  # Convert to days
                    y=surface.strikes,
                    z=surface.implied_vols * 100,  # Convert to percentage
                    colorscale="Viridis",
                    contours={
                        "z": {
                            "show": True,
                            "usecolormap": True,
                            "highlightcolor": "limegreen",
                            "project": {"z": True},
                        }
                    },
                )
            ]
        )

        fig.update_layout(
            title=title,
            scene=dict(
                xaxis_title="Days to Expiry",
                yaxis_title="Strike Price",
                zaxis_title="Implied Volatility (%)",
                camera=dict(eye=dict(x=1.5, y=1.5, z=1.5)),
            ),
            width=900,
            height=700,
        )

        return fig

    def plot_volatility_smile(
        self, surface: VolatilitySurface, expiry_days: list[int] = None
    ) -> go.Figure:
        """Plot volatility smiles for different expiries"""
        if expiry_days is None:
            expiry_days = [7, 30, 60, 90]
        fig = go.Figure()

        for days in expiry_days:
            expiry = days / 365.0
            strikes, smile = surface.get_smile(expiry)

            fig.add_trace(
                go.Scatter(
                    x=strikes,
                    y=smile * 100,
                    mode="lines",
                    name=f"{days} days",
                    line=dict(width=2),
                )
            )

        # Add ATM line
        fig.add_vline(
            x=surface.spot_price,
            line_dash="dash",
            line_color="gray",
            annotation_text="ATM",
        )

        fig.update_layout(
            title="Volatility Smile",
            xaxis_title="Strike Price",
            yaxis_title="Implied Volatility (%)",
            hovermode="x unified",
            width=800,
            height=500,
        )

        return fig

    def plot_term_structure(
        self,
        surface: VolatilitySurface,
        moneyness_levels: list[float] = None,
    ) -> go.Figure:
        """Plot volatility term structure"""
        if moneyness_levels is None:
            moneyness_levels = [0.9, 0.95, 1.0, 1.05, 1.1]
        fig = go.Figure()

        for moneyness in moneyness_levels:
            strike = surface.spot_price * moneyness
            expiries, term_structure = surface.get_term_structure(strike)

            fig.add_trace(
                go.Scatter(
                    x=expiries * 365,
                    y=term_structure * 100,
                    mode="lines",
                    name=f"{moneyness:.0%} moneyness",
                    line=dict(width=2),
                )
            )

        fig.update_layout(
            title="Volatility Term Structure",
            xaxis_title="Days to Expiry",
            yaxis_title="Implied Volatility (%)",
            hovermode="x unified",
            width=800,
            height=500,
        )

        return fig

    def plot_greeks_surfaces(
        self, vol_surface: VolatilitySurface, spot_price: float
    ) -> go.Figure:
        """Plot all Greeks surfaces in subplots"""
        greeks = self.calculate_greeks_surfaces(vol_surface, spot_price)

        fig = make_subplots(
            rows=2,
            cols=2,
            subplot_titles=(
                "Delta Surface",
                "Gamma Surface",
                "Vega Surface",
                "Theta Surface",
            ),
            specs=[
                [{"type": "surface"}, {"type": "surface"}],
                [{"type": "surface"}, {"type": "surface"}],
            ],
        )

        # Delta
        fig.add_trace(
            go.Surface(
                x=vol_surface.expiries * 365, y=vol_surface.strikes, z=greeks["delta"]
            ),
            row=1,
            col=1,
        )

        # Gamma
        fig.add_trace(
            go.Surface(
                x=vol_surface.expiries * 365, y=vol_surface.strikes, z=greeks["gamma"]
            ),
            row=1,
            col=2,
        )

        # Vega
        fig.add_trace(
            go.Surface(
                x=vol_surface.expiries * 365, y=vol_surface.strikes, z=greeks["vega"]
            ),
            row=2,
            col=1,
        )

        # Theta
        fig.add_trace(
            go.Surface(
                x=vol_surface.expiries * 365, y=vol_surface.strikes, z=greeks["theta"]
            ),
            row=2,
            col=2,
        )

        fig.update_layout(title_text="Greeks Surfaces", height=1000, showlegend=False)

        return fig

    # ==========================================================================
    # REAL-TIME UPDATES
    # ==========================================================================

    async def update_surface_realtime(self, new_quote: dict[str, Any]) -> bool:
        """Update surface with real-time quote"""
        if not self.current_surface:
            return False

        try:
            # Extract quote details
            strike = new_quote["strike"]
            expiry = new_quote["expiry"]
            new_iv = new_quote["implied_vol"]

            # Find nearest grid point
            strike_idx = np.argmin(np.abs(self.current_surface.strikes - strike))
            time_to_expiry = (expiry - datetime.now(timezone.utc)).days / 365.0
            expiry_idx = np.argmin(
                np.abs(self.current_surface.expiries - time_to_expiry)
            )

            # Update with Kalman filter approach
            old_iv = self.current_surface.implied_vols[strike_idx, expiry_idx]
            measurement_noise = 0.01  # 1% measurement noise
            process_noise = 0.005  # 0.5% process noise

            # Kalman gain
            kalman_gain = process_noise / (process_noise + measurement_noise)

            # Update
            updated_iv = old_iv + kalman_gain * (new_iv - old_iv)
            self.current_surface.implied_vols[strike_idx, expiry_idx] = updated_iv

            # Smooth around updated point
            self._local_smoothing(
                self.current_surface.implied_vols, strike_idx, expiry_idx
            )

            self.last_update = datetime.now(timezone.utc)
            return True

        except Exception as e:
            self.logger.error("Real-time update error: %s", e)
            return False

    def _local_smoothing(self, surface: np.ndarray, i: int, j: int, radius: int = 2):
        """Apply local smoothing around updated point"""
        rows, cols = surface.shape

        for di in range(-radius, radius + 1):
            for dj in range(-radius, radius + 1):
                if di == 0 and dj == 0:
                    continue

                ni, nj = i + di, j + dj
                if 0 <= ni < rows and 0 <= nj < cols:
                    weight = 1.0 / (abs(di) + abs(dj))
                    surface[ni, nj] = (
                        weight * surface[i, j] + (1 - weight) * surface[ni, nj]
                    )

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _implied_volatility_bs(
        self,
        option_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str,
    ) -> float:
        """Calculate implied volatility using Black-Scholes"""
        try:
            # Newton-Raphson method
            sigma = 0.3  # Initial guess

            for _ in range(50):
                # Calculate option price and vega
                d1 = (np.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * np.sqrt(T))
                d2 = d1 - sigma * np.sqrt(T)

                if option_type.lower() == "call":
                    price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
                else:
                    price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

                vega = S * norm.pdf(d1) * np.sqrt(T)

                # Update sigma
                if abs(price - option_price) < 1e-6:
                    return sigma

                if vega > 1e-6:
                    sigma = sigma - (price - option_price) / vega
                    sigma = max(0.001, min(sigma, 5.0))  # Bounds
                else:
                    break

            return sigma

        except Exception:
            return 0.0

    def save_surface(self, filename: str):
        """Save current surface to file"""
        if self.current_surface:
            joblib.dump(self.current_surface, filename)
            self.logger.info("Saved surface to %s", filename)

    def load_surface(self, filename: str) -> VolatilitySurface:
        """Load surface from file"""
        surface = joblib.load(filename)
        self.current_surface = surface
        return surface

    def get_current_metrics(self) -> SurfaceMetrics | None:
        """Get metrics for current surface"""
        if self.current_surface:
            return self._calculate_surface_metrics(self.current_surface)
        return None


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_module_instance: VolatilitySurfaceAI | None = None


def create_volatility_surface_ai(
    config: dict[str, Any] | None = None,
) -> VolatilitySurfaceAI:
    """Factory function to create volatility surface AI"""
    global _module_instance
    if _module_instance is None:
        _module_instance = VolatilitySurfaceAI(config)
    return _module_instance


def get_volatility_surface_ai() -> VolatilitySurfaceAI | None:
    """Get existing instance"""
    return _module_instance


# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
async def main():
    """Test volatility surface AI functionality"""
    import argparse

    parser = argparse.ArgumentParser(description="Volatility Surface AI Testing")
    parser.add_argument("--build", action="store_true", help="Build test surface")
    parser.add_argument("--plot", action="store_true", help="Plot surface")
    parser.add_argument("--metrics", action="store_true", help="Show surface metrics")
    parser.add_argument(
        "--greeks", action="store_true", help="Calculate Greeks surfaces"
    )
    args = parser.parse_args()

    # Create instance
    surface_ai = create_volatility_surface_ai()

    if args.build:
        logging.info("\n=== Building Test Volatility Surface ===")

        # Create test option chain
        from SpyderC_MarketData.SpyderC03_OptionChain import OptionChain

        option_chain = OptionChain()

        # Add test data
        spot = 450.0
        for days in [7, 14, 30, 45, 60, 90]:
            expiry = datetime.now(timezone.utc) + timedelta(days=days)

            for moneyness in np.linspace(0.9, 1.1, 21):
                strike = spot * moneyness

                # Simulate IV with smile
                base_iv = 0.15 + 0.05 * (days / 90)  # Term structure
                smile_adj = 0.02 * (abs(moneyness - 1.0) ** 1.5)  # Smile
                iv = base_iv + smile_adj

                option_chain.add_option(
                    strike=strike,
                    expiry=expiry,
                    option_type="CALL",
                    bid=10.0,
                    ask=10.5,
                    iv=iv,
                    volume=1000,
                    open_interest=5000,
                )

        # Build surface
        surface = await surface_ai.build_surface(option_chain, spot)

        if surface:
            logging.info("Surface built successfully!")
            logging.info("Strikes: %s", len(surface.strikes))
            logging.info("Expiries: %s", len(surface.expiries))
            logging.info(f"ATM Vol: {surface.implied_vols[25, 5]:.1%}")

    if args.plot and surface_ai.current_surface:
        logging.info("\n=== Plotting Volatility Surface ===")

        # 3D surface
        fig = surface_ai.plot_surface_3d(surface_ai.current_surface)
        fig.show()

        # Smile
        fig = surface_ai.plot_volatility_smile(surface_ai.current_surface)
        fig.show()

        # Term structure
        fig = surface_ai.plot_term_structure(surface_ai.current_surface)
        fig.show()

    if args.metrics and surface_ai.current_surface:
        logging.info("\n=== Surface Metrics ===")
        metrics = surface_ai.get_current_metrics()

        logging.info(f"ATM Volatility: {metrics.atm_vol:.1%}")
        logging.info(f"Skew (RR): {metrics.skew:.3f}")
        logging.info(f"Kurtosis (BF): {metrics.kurtosis:.3f}")
        logging.info(f"Term Slope: {metrics.term_structure_slope:.3f}")
        logging.info(f"Smoothness: {metrics.surface_smoothness:.4f}")
        logging.info(f"Smile Asymmetry: {metrics.smile_asymmetry:.3f}")

        if metrics.arbitrage_violations:
            logging.info("\nArbitrage Violations: %s", len(metrics.arbitrage_violations))
            for v in metrics.arbitrage_violations[:3]:
                logging.info("  %s: %s", v['type'], v)

    if args.greeks and surface_ai.current_surface:
        logging.info("\n=== Calculating Greeks Surfaces ===")

        greeks = surface_ai.calculate_greeks_surfaces(
            surface_ai.current_surface, spot_price=450.0
        )

        logging.info("Greeks at ATM (1-month):")
        atm_idx = 25
        one_month_idx = 5

        for greek, values in greeks.items():
            logging.info(f"  {greek.title()}: {values[atm_idx, one_month_idx]:.4f}")

        # Plot Greeks
        fig = surface_ai.plot_greeks_surfaces(surface_ai.current_surface, 450.0)
        fig.show()


if __name__ == "__main__":
    asyncio.run(main())
