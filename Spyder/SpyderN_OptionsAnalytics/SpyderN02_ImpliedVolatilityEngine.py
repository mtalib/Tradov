#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderN02_ImpliedVolatilityEngine.py
Group: N (Options Analytics)
Purpose: Comprehensive implied volatility analysis and term structure modeling
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2025-08-07 Time: 17:00:00

Description:
    This module provides advanced implied volatility analytics for the Spyder
    system. It calculates IV from market prices, tracks IV rank/percentile,
    analyzes term structure, models volatility smiles, and provides real-time
    IV updates. This engine is essential for volatility-based trading strategies
    and feeds critical data to the volatility surface and options flow analyzers.

Key Features:
    - Real-time IV calculation from option chains
    - IV rank and percentile calculations
    - Term structure analysis across expirations
    - Volatility smile/skew modeling
    - Historical IV tracking and storage
    - IV forecasting and mean reversion analysis
    - Volatility regime detection
    - Cross-sectional IV analysis
    - Put-call IV spread monitoring
    - Volatility arbitrage opportunity detection
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import bisect
import joblib
import threading
from datetime import datetime, timedelta
from typing import Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from scipy import interpolate
import warnings
import logging
warnings.filterwarnings('ignore')

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderN01_OptionsPricer import (
        OptionsPricer, OptionContract, MarketData, OptionType,  # noqa: F401
        ExerciseStyle, ImpliedVolatilitySolver
    )
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    LOCAL_IMPORTS = True
except ImportError:
    LOCAL_IMPORTS = False
    import logging

    # Mock imports for standalone testing
    class SpyderLogger:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

    class SpyderErrorHandler:
        def handle_error(self, error, context):
            logging.info("Error in %s: %s", context, error)

    class OptionType(Enum):
        CALL = "CALL"
        PUT = "PUT"

    class ExerciseStyle(Enum):
        EUROPEAN = "EUROPEAN"
        AMERICAN = "AMERICAN"

# ==============================================================================
# CONSTANTS
# ==============================================================================

# IV Parameters
DEFAULT_RISK_FREE_RATE = 0.05     # 5% risk-free rate
MIN_IV = 0.05                      # 5% minimum IV
MAX_IV = 3.00                      # 300% maximum IV
IV_CONVERGENCE_TOL = 0.0001       # 0.01% convergence tolerance

# Historical IV Parameters
IV_HISTORY_DAYS = 252              # 1 year of history
IV_RANK_PERIOD = 252               # 252 days for IV rank
IV_PERCENTILE_PERIOD = 252        # 252 days for IV percentile
HV_CALCULATION_PERIOD = 20         # 20 days for historical volatility

# Term Structure Parameters
MIN_DTE = 1                        # Minimum days to expiration
MAX_DTE = 730                      # Maximum days to expiration (2 years)
TERM_STRUCTURE_BUCKETS = [7, 14, 30, 45, 60, 90, 120, 180, 365]

# Smile Parameters
MONEYNESS_RANGE = [0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.15, 1.20]
SMILE_SMOOTHING_WINDOW = 5         # Points for smoothing
MIN_STRIKES_FOR_SMILE = 5          # Minimum strikes needed

# Volatility Regimes
LOW_VOL_THRESHOLD = 0.12           # 12% IV
NORMAL_VOL_RANGE = (0.12, 0.20)    # 12-20% IV
HIGH_VOL_THRESHOLD = 0.20          # 20% IV
EXTREME_VOL_THRESHOLD = 0.30       # 30% IV

# Greeks-based adjustments
VEGA_WEIGHT_THRESHOLD = 0.01       # Minimum vega weight
DELTA_NEUTRAL_RANGE = (0.45, 0.55) # Delta range for ATM

# Data persistence
IV_DATA_DIR = Path("data/iv_history")
CACHE_TTL_SECONDS = 60              # Cache time-to-live

# ==============================================================================
# ENUMS
# ==============================================================================

class IVMetric(Enum):
    """Implied volatility metrics"""
    SPOT_IV = "SPOT_IV"
    IV_RANK = "IV_RANK"
    IV_PERCENTILE = "IV_PERCENTILE"
    HV_RATIO = "HV_RATIO"
    PUT_CALL_SPREAD = "PUT_CALL_SPREAD"
    TERM_STRUCTURE = "TERM_STRUCTURE"
    VOLATILITY_SMILE = "VOLATILITY_SMILE"

class VolatilityRegime(Enum):
    """Market volatility regimes"""
    LOW = "LOW_VOLATILITY"
    NORMAL = "NORMAL_VOLATILITY"
    HIGH = "HIGH_VOLATILITY"
    EXTREME = "EXTREME_VOLATILITY"
    TRANSITIONING = "TRANSITIONING"

class TermStructureShape(Enum):
    """Term structure shapes"""
    CONTANGO = "CONTANGO"          # Upward sloping
    BACKWARDATION = "BACKWARDATION" # Downward sloping
    FLAT = "FLAT"                   # Flat structure
    HUMPED = "HUMPED"               # Peak in middle

class SmileShape(Enum):
    """Volatility smile shapes"""
    SYMMETRIC = "SYMMETRIC"
    SKEWED_PUT = "SKEWED_PUT"
    SKEWED_CALL = "SKEWED_CALL"
    SMIRK = "SMIRK"
    FROWN = "FROWN"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class IVPoint:
    """Single implied volatility data point"""
    timestamp: datetime
    symbol: str
    strike: float
    expiry: datetime
    option_type: OptionType
    spot_price: float
    market_price: float
    implied_volatility: float
    volume: int | None = None
    open_interest: int | None = None
    bid_ask_spread: float | None = None

    @property
    def moneyness(self) -> float:
        """Calculate moneyness (spot/strike)"""
        return self.spot_price / self.strike if self.strike > 0 else 0

    @property
    def days_to_expiry(self) -> int:
        """Calculate days to expiry"""
        return max(0, (self.expiry - self.timestamp).days)

@dataclass
class IVSnapshot:
    """Complete IV snapshot at a point in time"""
    timestamp: datetime
    underlying: str
    spot_price: float
    atm_iv: float
    iv_points: list[IVPoint]
    term_structure: dict[int, float]  # DTE -> IV
    smile_parameters: dict[str, float]
    regime: VolatilityRegime

    def get_iv_by_strike(self, strike: float, option_type: OptionType) -> float | None:
        """Get IV for specific strike"""
        for point in self.iv_points:
            if abs(point.strike - strike) < 0.01 and point.option_type == option_type:
                return point.implied_volatility
        return None

    def get_iv_by_moneyness(self, moneyness: float) -> float | None:
        """Get IV for specific moneyness level"""
        closest_point = None
        min_diff = float('inf')

        for point in self.iv_points:
            diff = abs(point.moneyness - moneyness)
            if diff < min_diff:
                min_diff = diff
                closest_point = point

        return closest_point.implied_volatility if closest_point else None

@dataclass
class IVTermStructure:
    """Implied volatility term structure"""
    timestamp: datetime
    underlying: str
    expirations: list[datetime]
    implied_vols: list[float]
    shape: TermStructureShape
    slope: float  # Annualized slope
    curvature: float

    def interpolate_iv(self, target_dte: int) -> float:
        """Interpolate IV for specific DTE"""
        if not self.expirations:
            return 0

        dtes = [(exp - self.timestamp).days for exp in self.expirations]

        if target_dte <= min(dtes):
            return self.implied_vols[0]
        if target_dte >= max(dtes):
            return self.implied_vols[-1]

        # Linear interpolation
        interp = interpolate.interp1d(dtes, self.implied_vols, kind='linear')
        return float(interp(target_dte))

@dataclass
class IVSmile:
    """Volatility smile/skew parameters"""
    timestamp: datetime
    expiry: datetime
    strikes: list[float]
    implied_vols: list[float]
    atm_strike: float
    atm_iv: float
    skew: float  # Slope at ATM
    convexity: float  # Curvature
    shape: SmileShape
    put_wing_slope: float
    call_wing_slope: float

    def fit_smile(self) -> callable:
        """Fit parametric smile model"""
        if len(self.strikes) < 3:
            return lambda k: self.atm_iv

        # Use quadratic fit for simplicity
        moneyness = [k/self.atm_strike for k in self.strikes]
        coeffs = np.polyfit(moneyness, self.implied_vols, 2)

        return lambda k: np.polyval(coeffs, k/self.atm_strike)

@dataclass
class IVAnalytics:
    """Comprehensive IV analytics"""
    timestamp: datetime
    underlying: str
    spot_price: float

    # Current metrics
    current_iv: float
    iv_rank: float
    iv_percentile: float

    # Historical metrics
    hv_20day: float
    hv_ratio: float  # IV/HV ratio

    # Term structure
    term_structure: IVTermStructure
    term_structure_slope: float

    # Smile metrics
    smile: IVSmile
    put_call_spread: float
    skew_ratio: float  # 90% Put IV / 110% Call IV

    # Regime analysis
    regime: VolatilityRegime
    regime_confidence: float
    regime_transition_prob: float

    # Forecasts
    mean_reversion_target: float
    forecast_1d: float
    forecast_5d: float
    forecast_confidence: float

@dataclass
class IVHistory:
    """Historical IV data storage"""
    underlying: str
    data: list[IVSnapshot]

    def get_series(self, metric: str = 'atm_iv') -> pd.Series:
        """Extract time series of specific metric"""
        timestamps = [d.timestamp for d in self.data]
        values = [getattr(d, metric) for d in self.data]
        return pd.Series(values, index=timestamps)

    def calculate_rank(self, current_iv: float, period_days: int = 252) -> float:
        """Calculate IV rank over period"""
        cutoff_date = datetime.now() - timedelta(days=period_days)
        period_data = [d for d in self.data if d.timestamp >= cutoff_date]

        if not period_data:
            return 50.0

        ivs = [d.atm_iv for d in period_data]
        min_iv = min(ivs)
        max_iv = max(ivs)

        if max_iv == min_iv:
            return 50.0

        return 100 * (current_iv - min_iv) / (max_iv - min_iv)

    def calculate_percentile(self, current_iv: float, period_days: int = 252) -> float:
        """Calculate IV percentile over period"""
        cutoff_date = datetime.now() - timedelta(days=period_days)
        period_data = [d for d in self.data if d.timestamp >= cutoff_date]

        if not period_data:
            return 50.0

        ivs = sorted([d.atm_iv for d in period_data])

        # Find position in sorted list
        pos = bisect.bisect_left(ivs, current_iv)
        return 100 * pos / len(ivs)

# ==============================================================================
# IMPLIED VOLATILITY ENGINE
# ==============================================================================

class ImpliedVolatilityEngine:
    """
    Comprehensive implied volatility analysis engine

    This class provides real-time IV calculations, historical tracking,
    term structure analysis, smile modeling, and volatility regime detection.
    It integrates with the options pricer for accurate IV calculations and
    provides essential data for volatility-based trading strategies.

    Attributes:
        pricer: Options pricing engine
        iv_history: Historical IV data by underlying
        current_snapshots: Current IV snapshots

    Example:
        >>> iv_engine = ImpliedVolatilityEngine()
        >>> chain_data = get_option_chain('SPY')
        >>> snapshot = iv_engine.calculate_iv_snapshot('SPY', chain_data)
        >>> print(f"ATM IV: {snapshot.atm_iv:.1%}")
        >>> print(f"IV Rank: {iv_engine.get_iv_rank('SPY'):.1f}")
    """

    def __init__(self, data_dir: Path | None = None):
        """
        Initialize IV engine

        Args:
            data_dir: Directory for IV data persistence
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Initialize options pricer
        if LOCAL_IMPORTS:
            self.pricer = OptionsPricer()
            self.iv_solver = ImpliedVolatilitySolver()
        else:
            self.pricer = None
            self.iv_solver = None

        # Data storage
        self.data_dir = data_dir or IV_DATA_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Historical data
        self.iv_history: dict[str, IVHistory] = {}
        self.load_historical_data()

        # Current data
        self.current_snapshots: dict[str, IVSnapshot] = {}
        self.current_analytics: dict[str, IVAnalytics] = {}

        # Caching
        self.cache: dict[str, tuple[Any, datetime]] = {}
        self.cache_lock = threading.Lock()

        # Configuration
        self.min_volume = 10  # Minimum volume for IV calculation
        self.min_open_interest = 100  # Minimum OI
        self.max_bid_ask_spread = 0.50  # Maximum spread

        self.logger.debug("ImpliedVolatilityEngine initialized")

    # ==========================================================================
    # PUBLIC METHODS - IV CALCULATION
    # ==========================================================================

    def calculate_iv_snapshot(self, underlying: str, chain_data: list[dict],
                             spot_price: float, risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> IVSnapshot:
        """
        Calculate complete IV snapshot from option chain

        Args:
            underlying: Underlying symbol
            chain_data: List of option chain data
            spot_price: Current spot price
            risk_free_rate: Risk-free rate

        Returns:
            IVSnapshot with all IV metrics
        """
        try:
            timestamp = datetime.now()
            iv_points = []

            # Calculate IV for each option
            for option in chain_data:
                iv_point = self._calculate_single_iv(option, spot_price, risk_free_rate)
                if iv_point and self._is_valid_iv_point(iv_point):
                    iv_points.append(iv_point)

            if not iv_points:
                self.logger.warning("No valid IV points for %s", underlying)
                return self._create_empty_snapshot(underlying, spot_price)

            # Calculate ATM IV
            atm_iv = self._calculate_atm_iv(iv_points, spot_price)

            # Build term structure
            term_structure = self._build_term_structure(iv_points)

            # Calculate smile parameters
            smile_params = self._calculate_smile_parameters(iv_points, spot_price)

            # Detect regime
            regime = self._detect_volatility_regime(atm_iv, term_structure)

            # Create snapshot
            snapshot = IVSnapshot(
                timestamp=timestamp,
                underlying=underlying,
                spot_price=spot_price,
                atm_iv=atm_iv,
                iv_points=iv_points,
                term_structure=term_structure,
                smile_parameters=smile_params,
                regime=regime
            )

            # Store snapshot
            self.current_snapshots[underlying] = snapshot
            self._add_to_history(underlying, snapshot)

            return snapshot

        except Exception as e:
            self.logger.error("Error calculating IV snapshot: %s", e)
            self.error_handler.handle_error(e, {"underlying": underlying})
            return self._create_empty_snapshot(underlying, spot_price)

    def calculate_iv_analytics(self, underlying: str, snapshot: IVSnapshot | None = None) -> IVAnalytics:
        """
        Calculate comprehensive IV analytics

        Args:
            underlying: Underlying symbol
            snapshot: IV snapshot (uses current if None)

        Returns:
            IVAnalytics with all metrics
        """
        if snapshot is None:
            snapshot = self.current_snapshots.get(underlying)
            if not snapshot:
                raise ValueError(f"No snapshot available for {underlying}")

        # Get historical data
        history = self.iv_history.get(underlying)

        # Calculate IV rank and percentile
        iv_rank = history.calculate_rank(snapshot.atm_iv) if history else 50.0
        iv_percentile = history.calculate_percentile(snapshot.atm_iv) if history else 50.0

        # Calculate historical volatility
        hv_20day = self._calculate_historical_volatility(underlying, 20)
        hv_ratio = snapshot.atm_iv / hv_20day if hv_20day > 0 else 1.0

        # Build term structure object
        term_structure = self._analyze_term_structure(snapshot)

        # Build smile object
        smile = self._analyze_smile(snapshot)

        # Calculate put-call spread
        put_call_spread = self._calculate_put_call_spread(snapshot)

        # Calculate skew ratio
        skew_ratio = self._calculate_skew_ratio(snapshot)

        # Mean reversion analysis
        mean_reversion_target = self._calculate_mean_reversion_target(underlying, snapshot.atm_iv)

        # Volatility forecasts
        forecast_1d, forecast_5d, confidence = self._forecast_volatility(underlying, snapshot.atm_iv)

        # Regime analysis
        regime_confidence = self._calculate_regime_confidence(snapshot.regime, snapshot.atm_iv)
        transition_prob = self._calculate_regime_transition_probability(snapshot.regime, history)

        analytics = IVAnalytics(
            timestamp=snapshot.timestamp,
            underlying=underlying,
            spot_price=snapshot.spot_price,
            current_iv=snapshot.atm_iv,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            hv_20day=hv_20day,
            hv_ratio=hv_ratio,
            term_structure=term_structure,
            term_structure_slope=term_structure.slope if term_structure else 0,
            smile=smile,
            put_call_spread=put_call_spread,
            skew_ratio=skew_ratio,
            regime=snapshot.regime,
            regime_confidence=regime_confidence,
            regime_transition_prob=transition_prob,
            mean_reversion_target=mean_reversion_target,
            forecast_1d=forecast_1d,
            forecast_5d=forecast_5d,
            forecast_confidence=confidence
        )

        # Store analytics
        self.current_analytics[underlying] = analytics

        return analytics

    # ==========================================================================
    # PUBLIC METHODS - QUERIES
    # ==========================================================================

    def get_current_iv(self, underlying: str) -> float | None:
        """Get current ATM IV"""
        snapshot = self.current_snapshots.get(underlying)
        return snapshot.atm_iv if snapshot else None

    def get_iv_rank(self, underlying: str, period_days: int = IV_RANK_PERIOD) -> float:
        """Get current IV rank"""
        current_iv = self.get_current_iv(underlying)
        if not current_iv:
            return 50.0

        history = self.iv_history.get(underlying)
        if not history:
            return 50.0

        return history.calculate_rank(current_iv, period_days)

    def get_iv_percentile(self, underlying: str, period_days: int = IV_PERCENTILE_PERIOD) -> float:
        """Get current IV percentile"""
        current_iv = self.get_current_iv(underlying)
        if not current_iv:
            return 50.0

        history = self.iv_history.get(underlying)
        if not history:
            return 50.0

        return history.calculate_percentile(current_iv, period_days)

    def get_term_structure(self, underlying: str) -> IVTermStructure | None:
        """Get current term structure"""
        analytics = self.current_analytics.get(underlying)
        return analytics.term_structure if analytics else None

    def get_volatility_smile(self, underlying: str, expiry: datetime) -> IVSmile | None:
        """Get volatility smile for specific expiry"""
        snapshot = self.current_snapshots.get(underlying)
        if not snapshot:
            return None

        # Filter points for specific expiry
        expiry_points = [p for p in snapshot.iv_points
                        if abs((p.expiry - expiry).days) < 1]

        if len(expiry_points) < MIN_STRIKES_FOR_SMILE:
            return None

        return self._build_smile_from_points(expiry_points, snapshot.spot_price)

    def get_volatility_regime(self, underlying: str) -> VolatilityRegime:
        """Get current volatility regime"""
        snapshot = self.current_snapshots.get(underlying)
        return snapshot.regime if snapshot else VolatilityRegime.NORMAL

    def get_iv_forecast(self, underlying: str, horizon_days: int = 5) -> tuple[float, float]:
        """
        Get IV forecast

        Returns:
            Tuple of (forecast_iv, confidence)
        """
        analytics = self.current_analytics.get(underlying)
        if not analytics:
            current_iv = self.get_current_iv(underlying) or 0.16
            return current_iv, 0.5

        if horizon_days <= 1:
            return analytics.forecast_1d, analytics.forecast_confidence
        elif horizon_days <= 5:
            return analytics.forecast_5d, analytics.forecast_confidence
        else:
            # Longer horizon - use mean reversion
            return analytics.mean_reversion_target, max(0.3, analytics.forecast_confidence * 0.7)

    # ==========================================================================
    # PRIVATE METHODS - IV CALCULATION
    # ==========================================================================

    def _calculate_single_iv(self, option_data: dict, spot_price: float,
                           risk_free_rate: float) -> IVPoint | None:
        """Calculate IV for single option"""
        try:
            strike = option_data['strike']
            expiry = option_data['expiry']
            option_type = OptionType[option_data['type']]
            market_price = option_data.get('mid_price') or option_data.get('last', 0)

            if market_price <= 0:
                return None

            # Calculate time to expiry
            tte = (expiry - datetime.now()).days / 365.0
            if tte <= 0:
                return None

            # Calculate IV
            if self.iv_solver:
                iv = self.iv_solver.calculate_iv(
                    market_price, spot_price, strike, tte,
                    risk_free_rate, DEFAULT_RISK_FREE_RATE,  # Using default div yield
                    option_type
                )
            else:
                # Fallback calculation
                iv = self._estimate_iv(market_price, spot_price, strike, tte, option_type)

            if not iv or iv < MIN_IV or iv > MAX_IV:
                return None

            return IVPoint(
                timestamp=datetime.now(),
                symbol=option_data.get('symbol', ''),
                strike=strike,
                expiry=expiry,
                option_type=option_type,
                spot_price=spot_price,
                market_price=market_price,
                implied_volatility=iv,
                volume=option_data.get('volume'),
                open_interest=option_data.get('open_interest'),
                bid_ask_spread=option_data.get('ask', 0) - option_data.get('bid', 0)
            )

        except Exception as e:
            self.logger.debug("Error calculating IV for option: %s", e)
            return None

    def _estimate_iv(self, market_price: float, spot: float, strike: float,
                    tte: float, option_type: OptionType) -> float:
        """Estimate IV using approximation (fallback)"""
        # Brenner-Subrahmanyam approximation
        spot / strike

        if option_type == OptionType.CALL:
            intrinsic = max(spot - strike, 0)
        else:
            intrinsic = max(strike - spot, 0)

        if market_price <= intrinsic:
            return MIN_IV

        # Simple approximation
        time_value = market_price - intrinsic
        iv_estimate = np.sqrt(2 * np.pi / tte) * (time_value / spot)

        return max(MIN_IV, min(MAX_IV, iv_estimate))

    def _is_valid_iv_point(self, iv_point: IVPoint) -> bool:
        """Check if IV point meets quality criteria"""
        # Check volume/OI requirements
        if iv_point.volume is not None and iv_point.volume < self.min_volume:
            return False

        if iv_point.open_interest is not None and iv_point.open_interest < self.min_open_interest:
            return False

        # Check bid-ask spread
        if iv_point.bid_ask_spread is not None and iv_point.bid_ask_spread > self.max_bid_ask_spread:
            return False

        # Check IV bounds
        return not (iv_point.implied_volatility < MIN_IV or iv_point.implied_volatility > MAX_IV)

    def _calculate_atm_iv(self, iv_points: list[IVPoint], spot_price: float) -> float:
        """Calculate ATM implied volatility"""
        # Find options closest to ATM
        atm_points = []

        for point in iv_points:
            moneyness = point.moneyness
            if 0.95 <= moneyness <= 1.05:  # Within 5% of ATM
                atm_points.append(point)

        if not atm_points:
            # Use all points weighted by moneyness distance
            weights = [1.0 / (1.0 + abs(p.moneyness - 1.0)) for p in iv_points]
            total_weight = sum(weights)
            weighted_iv = sum(p.implied_volatility * w for p, w in zip(iv_points, weights, strict=False))
            return weighted_iv / total_weight

        # Average ATM points
        return np.mean([p.implied_volatility for p in atm_points])

    # ==========================================================================
    # PRIVATE METHODS - TERM STRUCTURE
    # ==========================================================================

    def _build_term_structure(self, iv_points: list[IVPoint]) -> dict[int, float]:
        """Build term structure from IV points"""
        term_structure = defaultdict(list)

        # Group by DTE
        for point in iv_points:
            dte = point.days_to_expiry
            if MIN_DTE <= dte <= MAX_DTE:
                term_structure[dte].append(point.implied_volatility)

        # Average IVs for each DTE
        result = {}
        for dte, ivs in term_structure.items():
            result[dte] = np.mean(ivs)

        return dict(sorted(result.items()))

    def _analyze_term_structure(self, snapshot: IVSnapshot) -> IVTermStructure | None:
        """Analyze term structure shape and characteristics"""
        if not snapshot.term_structure or len(snapshot.term_structure) < 2:
            return None

        dtes = list(snapshot.term_structure.keys())
        ivs = list(snapshot.term_structure.values())

        # Calculate slope (annualized)
        if len(dtes) >= 2:
            # Use linear regression
            slope, intercept = np.polyfit(dtes, ivs, 1)
            slope_annual = slope * 365  # Convert to annual
        else:
            slope_annual = 0

        # Calculate curvature
        if len(dtes) >= 3:
            # Fit quadratic
            coeffs = np.polyfit(dtes, ivs, 2)
            curvature = coeffs[0] * 2  # Second derivative
        else:
            curvature = 0

        # Determine shape
        if abs(slope_annual) < 0.01:  # Less than 1% per year
            shape = TermStructureShape.FLAT
        elif slope_annual > 0:
            shape = TermStructureShape.CONTANGO
        else:
            shape = TermStructureShape.BACKWARDATION

        # Check for hump
        if len(ivs) >= 5:
            max_iv = max(ivs)
            max_idx = ivs.index(max_iv)
            if 0 < max_idx < len(ivs) - 1:
                if ivs[0] < max_iv > ivs[-1]:
                    shape = TermStructureShape.HUMPED

        return IVTermStructure(
            timestamp=snapshot.timestamp,
            underlying=snapshot.underlying,
            expirations=[snapshot.timestamp + timedelta(days=d) for d in dtes],
            implied_vols=ivs,
            shape=shape,
            slope=slope_annual,
            curvature=curvature
        )

    # ==========================================================================
    # PRIVATE METHODS - SMILE ANALYSIS
    # ==========================================================================

    def _calculate_smile_parameters(self, iv_points: list[IVPoint], spot_price: float) -> dict[str, float]:
        """Calculate volatility smile parameters"""
        params = {
            'skew': 0,
            'convexity': 0,
            'put_wing': 0,
            'call_wing': 0
        }

        # Group by expiry
        by_expiry = defaultdict(list)
        for point in iv_points:
            key = point.expiry.date()
            by_expiry[key].append(point)

        # Find expiry with most strikes
        best_expiry = max(by_expiry.items(), key=lambda x: len(x[1])) if by_expiry else None

        if not best_expiry or len(best_expiry[1]) < MIN_STRIKES_FOR_SMILE:
            return params

        points = best_expiry[1]

        # Sort by strike
        points.sort(key=lambda p: p.strike)

        strikes = [p.strike for p in points]
        ivs = [p.implied_volatility for p in points]

        # Fit polynomial
        if len(strikes) >= 3:
            moneyness = [s/spot_price for s in strikes]
            coeffs = np.polyfit(moneyness, ivs, 2)

            params['convexity'] = coeffs[0] * 2  # Second derivative
            params['skew'] = coeffs[1]  # First derivative at ATM

            # Calculate wing slopes
            put_points = [p for p in points if p.moneyness < 0.95]
            call_points = [p for p in points if p.moneyness > 1.05]

            if len(put_points) >= 2:
                put_slope, _ = np.polyfit([p.moneyness for p in put_points],
                                         [p.implied_volatility for p in put_points], 1)
                params['put_wing'] = put_slope

            if len(call_points) >= 2:
                call_slope, _ = np.polyfit([p.moneyness for p in call_points],
                                          [p.implied_volatility for p in call_points], 1)
                params['call_wing'] = call_slope

        return params

    def _build_smile_from_points(self, points: list[IVPoint], spot_price: float) -> IVSmile:
        """Build smile object from IV points"""
        # Sort by strike
        points.sort(key=lambda p: p.strike)

        strikes = [p.strike for p in points]
        ivs = [p.implied_volatility for p in points]

        # Find ATM
        atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot_price))
        atm_strike = strikes[atm_idx]
        atm_iv = ivs[atm_idx]

        # Calculate metrics
        moneyness = [s/atm_strike for s in strikes]

        # Fit polynomial for smooth curve
        if len(strikes) >= 3:
            coeffs = np.polyfit(moneyness, ivs, 2)
            skew = coeffs[1]
            convexity = coeffs[0] * 2
        else:
            skew = 0
            convexity = 0

        # Determine shape
        if abs(skew) < 0.01:
            shape = SmileShape.SYMMETRIC
        elif skew < -0.01:
            shape = SmileShape.SKEWED_PUT
        else:
            shape = SmileShape.SKEWED_CALL

        # Calculate wing slopes
        put_wing = 0
        call_wing = 0

        if len(strikes) >= 5:
            put_idx = [i for i in range(len(strikes)) if strikes[i] < atm_strike * 0.95]
            call_idx = [i for i in range(len(strikes)) if strikes[i] > atm_strike * 1.05]

            if len(put_idx) >= 2:
                put_slope, _ = np.polyfit([moneyness[i] for i in put_idx],
                                         [ivs[i] for i in put_idx], 1)
                put_wing = put_slope

            if len(call_idx) >= 2:
                call_slope, _ = np.polyfit([moneyness[i] for i in call_idx],
                                          [ivs[i] for i in call_idx], 1)
                call_wing = call_slope

        return IVSmile(
            timestamp=datetime.now(),
            expiry=points[0].expiry if points else datetime.now(),
            strikes=strikes,
            implied_vols=ivs,
            atm_strike=atm_strike,
            atm_iv=atm_iv,
            skew=skew,
            convexity=convexity,
            shape=shape,
            put_wing_slope=put_wing,
            call_wing_slope=call_wing
        )

    def _calculate_put_call_spread(self, snapshot: IVSnapshot) -> float:
        """Calculate put-call IV spread"""
        atm_puts = []
        atm_calls = []

        for point in snapshot.iv_points:
            if 0.95 <= point.moneyness <= 1.05:
                if point.option_type == OptionType.PUT:
                    atm_puts.append(point.implied_volatility)
                else:
                    atm_calls.append(point.implied_volatility)

        if atm_puts and atm_calls:
            return np.mean(atm_puts) - np.mean(atm_calls)

        return 0

    def _calculate_skew_ratio(self, snapshot: IVSnapshot) -> float:
        """Calculate 90% Put IV / 110% Call IV ratio"""
        put_90 = None
        call_110 = None

        for point in snapshot.iv_points:
            if point.option_type == OptionType.PUT and 0.88 <= point.moneyness <= 0.92:
                put_90 = point.implied_volatility
            elif point.option_type == OptionType.CALL and 1.08 <= point.moneyness <= 1.12:
                call_110 = point.implied_volatility

        if put_90 and call_110 and call_110 > 0:
            return put_90 / call_110

        return 1.0

    # ==========================================================================
    # PRIVATE METHODS - REGIME DETECTION
    # ==========================================================================

    def _detect_volatility_regime(self, current_iv: float, term_structure: dict[int, float]) -> VolatilityRegime:
        """Detect current volatility regime"""
        if current_iv < LOW_VOL_THRESHOLD:
            return VolatilityRegime.LOW
        elif current_iv > EXTREME_VOL_THRESHOLD:
            return VolatilityRegime.EXTREME
        elif current_iv > HIGH_VOL_THRESHOLD:
            return VolatilityRegime.HIGH
        elif NORMAL_VOL_RANGE[0] <= current_iv <= NORMAL_VOL_RANGE[1]:
            return VolatilityRegime.NORMAL
        else:
            return VolatilityRegime.TRANSITIONING

    def _calculate_regime_confidence(self, regime: VolatilityRegime, current_iv: float) -> float:
        """Calculate confidence in regime classification"""
        if regime == VolatilityRegime.LOW:
            distance = LOW_VOL_THRESHOLD - current_iv
        elif regime == VolatilityRegime.HIGH:
            distance = current_iv - HIGH_VOL_THRESHOLD
        elif regime == VolatilityRegime.EXTREME:
            distance = current_iv - EXTREME_VOL_THRESHOLD
        elif regime == VolatilityRegime.NORMAL:
            mid = (NORMAL_VOL_RANGE[0] + NORMAL_VOL_RANGE[1]) / 2
            distance = abs(current_iv - mid)
            distance = (NORMAL_VOL_RANGE[1] - NORMAL_VOL_RANGE[0]) / 2 - distance
        else:
            return 0.5

        # Convert distance to confidence (0-1)
        confidence = min(1.0, max(0.0, abs(distance) / 0.05))
        return confidence

    def _calculate_regime_transition_probability(self, current_regime: VolatilityRegime,
                                                history: IVHistory | None) -> float:
        """Calculate probability of regime transition"""
        if not history or len(history.data) < 30:
            return 0.5

        # Look at recent regime changes
        recent_regimes = [d.regime for d in history.data[-30:]]

        if not recent_regimes:
            return 0.5

        # Count transitions
        transitions = 0
        for i in range(1, len(recent_regimes)):
            if recent_regimes[i] != recent_regimes[i-1]:
                transitions += 1

        # Calculate transition probability
        transition_rate = transitions / len(recent_regimes)

        # Adjust based on current regime duration
        current_duration = 0
        for regime in reversed(recent_regimes):
            if regime == current_regime:
                current_duration += 1
            else:
                break

        # Longer duration = lower transition probability
        duration_factor = 1.0 / (1.0 + current_duration / 10)

        return min(1.0, transition_rate * duration_factor)

    # ==========================================================================
    # PRIVATE METHODS - FORECASTING
    # ==========================================================================

    def _calculate_mean_reversion_target(self, underlying: str, current_iv: float) -> float:
        """Calculate mean reversion target"""
        history = self.iv_history.get(underlying)

        if not history or len(history.data) < 30:
            return current_iv

        # Use exponentially weighted average
        ivs = [d.atm_iv for d in history.data[-60:]]
        weights = np.exp(-np.arange(len(ivs))[::-1] / 30)
        weights /= weights.sum()

        return np.average(ivs, weights=weights)

    def _forecast_volatility(self, underlying: str, current_iv: float) -> tuple[float, float, float]:
        """
        Forecast future volatility

        Returns:
            Tuple of (1d_forecast, 5d_forecast, confidence)
        """
        history = self.iv_history.get(underlying)

        if not history or len(history.data) < 10:
            return current_iv, current_iv, 0.3

        # Get recent IVs
        recent_ivs = [d.atm_iv for d in history.data[-20:]]

        # Calculate trend
        x = np.arange(len(recent_ivs))
        slope, intercept = np.polyfit(x, recent_ivs, 1)

        # Mean reversion force
        mean_target = self._calculate_mean_reversion_target(underlying, current_iv)
        reversion_force = (mean_target - current_iv) * 0.1  # 10% mean reversion per day

        # Combine trend and mean reversion
        forecast_1d = current_iv + slope + reversion_force
        forecast_5d = current_iv + 5*slope + 5*reversion_force

        # Bound forecasts
        forecast_1d = max(MIN_IV, min(MAX_IV, forecast_1d))
        forecast_5d = max(MIN_IV, min(MAX_IV, forecast_5d))

        # Calculate confidence based on recent stability
        recent_std = np.std(recent_ivs)
        confidence = max(0.3, min(0.9, 1.0 - recent_std / 0.1))

        return forecast_1d, forecast_5d, confidence

    def _calculate_historical_volatility(self, underlying: str, period: int = 20) -> float:
        """Calculate historical volatility from price data"""
        # This would need actual price history
        # For now, return a reasonable estimate
        current_iv = self.get_current_iv(underlying)
        if current_iv:
            # HV is typically lower than IV
            return current_iv * 0.8
        return 0.15

    # ==========================================================================
    # PRIVATE METHODS - DATA MANAGEMENT
    # ==========================================================================

    def _add_to_history(self, underlying: str, snapshot: IVSnapshot):
        """Add snapshot to historical data"""
        if underlying not in self.iv_history:
            self.iv_history[underlying] = IVHistory(underlying=underlying, data=[])

        history = self.iv_history[underlying]
        history.data.append(snapshot)

        # Trim old data
        cutoff = datetime.now() - timedelta(days=IV_HISTORY_DAYS)
        history.data = [d for d in history.data if d.timestamp >= cutoff]

    def _create_empty_snapshot(self, underlying: str, spot_price: float) -> IVSnapshot:
        """Create empty snapshot when no data available"""
        return IVSnapshot(
            timestamp=datetime.now(),
            underlying=underlying,
            spot_price=spot_price,
            atm_iv=0.16,  # Default 16% IV
            iv_points=[],
            term_structure={},
            smile_parameters={},
            regime=VolatilityRegime.NORMAL
        )

    def load_historical_data(self):
        """Load historical IV data from disk"""
        try:
            for file_path in self.data_dir.glob("*_iv_history.pkl"):
                underlying = file_path.stem.replace("_iv_history", "")
                with open(file_path, 'rb') as f:
                    self.iv_history[underlying] = joblib.load(f)
                self.logger.info("Loaded IV history for %s", underlying)
        except Exception as e:
            self.logger.error("Error loading historical data: %s", e)

    def save_historical_data(self):
        """Save historical IV data to disk"""
        try:
            for underlying, history in self.iv_history.items():
                file_path = self.data_dir / f"{underlying}_iv_history.pkl"
                with open(file_path, 'wb') as f:
                    joblib.dump(history, f)
                self.logger.info("Saved IV history for %s", underlying)
        except Exception as e:
            self.logger.error("Error saving historical data: %s", e)

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_iv_engine(data_dir: Path | None = None) -> ImpliedVolatilityEngine:
    """Factory function to create IV engine"""
    return ImpliedVolatilityEngine(data_dir)

def generate_test_chain_data(underlying: str = "SPY", spot: float = 585.0) -> list[dict]:
    """Generate test option chain data"""
    chain_data = []

    # Generate options for multiple expiries
    expiries = [7, 14, 30, 45, 60, 90]

    for days_to_expiry in expiries:
        expiry = datetime.now() + timedelta(days=days_to_expiry)

        # Generate strikes around ATM
        strikes = np.arange(spot * 0.85, spot * 1.15, 5)

        for strike in strikes:
            moneyness = spot / strike

            # Generate realistic IVs with smile
            base_iv = 0.16 + (days_to_expiry / 365) * 0.02  # Term structure

            # Add smile effect
            smile_adjustment = 0.02 * (abs(moneyness - 1.0) ** 1.5)

            # Skew effect (puts have higher IV)
            if moneyness < 1.0:
                skew_adjustment = 0.01 * (1.0 - moneyness)
            else:
                skew_adjustment = -0.005 * (moneyness - 1.0)

            iv = base_iv + smile_adjustment + skew_adjustment

            # Generate prices (simplified Black-Scholes approximation)
            for option_type in ['CALL', 'PUT']:
                if option_type == 'CALL':
                    intrinsic = max(spot - strike, 0)
                else:
                    intrinsic = max(strike - spot, 0)

                # Simplified pricing
                time_value = spot * iv * np.sqrt(days_to_expiry/365) * 0.4
                price = intrinsic + time_value

                chain_data.append({
                    'symbol': f"{underlying}{expiry.strftime('%y%m%d')}{option_type[0]}{int(strike*1000):08d}",
                    'strike': strike,
                    'expiry': expiry,
                    'type': option_type,
                    'bid': price * 0.98,
                    'ask': price * 1.02,
                    'mid_price': price,
                    'last': price,
                    'volume': np.random.randint(10, 1000),
                    'open_interest': np.random.randint(100, 5000)
                })

    return chain_data

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":

    # Create IV engine
    iv_engine = create_iv_engine()

    # Generate test data
    underlying = "SPY"
    spot_price = 585.00
    chain_data = generate_test_chain_data(underlying, spot_price)


    # Calculate IV snapshot
    snapshot = iv_engine.calculate_iv_snapshot(underlying, chain_data, spot_price)


    # Display term structure
    if snapshot.term_structure:
        for _dte, _iv in list(snapshot.term_structure.items())[:5]:
            pass

    # Display smile parameters
    if snapshot.smile_parameters:
        for _param, _value in snapshot.smile_parameters.items():
            pass

    # Calculate analytics
    analytics = iv_engine.calculate_iv_analytics(underlying)


    # Term structure analysis
    if analytics.term_structure:
        pass

    # Smile analysis
    if analytics.smile:
        pass

    # Regime analysis

    # Forecasts

    # Additional metrics

    # Test specific queries

    # Test forecasting
    for horizon in [1, 5, 10, 30]:
        forecast, confidence = iv_engine.get_iv_forecast(underlying, horizon)

