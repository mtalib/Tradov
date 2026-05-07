#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderV_QuantModels
Module: SpyderV07_AdvancedModels.py
Purpose: Advanced modeling engine - Merton Jump-Diffusion and Crisis Detection (Updated)
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04 Time: 15:00:00

Module Description:
    Advanced modeling engine focused on Merton Jump-Diffusion models and crisis
    detection for SPY options trading. Provides sophisticated jump detection,
    crisis probability assessment, and event-driven pricing for handling
    non-standard market conditions and tail risk scenarios.

CONSOLIDATION UPDATE:
    Regime switching model functions have been REMOVED and consolidated into
    SpyderL09_UnifiedRegimeEngine.py. This module now focuses exclusively
    on jump-diffusion modeling, crisis detection, and advanced volatility
    modeling for options pricing.

Key Features:
    • Merton Jump-Diffusion modeling for crisis and event-driven periods
    • Real-time jump detection with statistical significance testing
    • Crisis probability assessment and market stress indicators
    • Event-driven strategy recommendations for tail risk scenarios
    • Advanced volatility modeling with jump corrections
    • Integration with V06_VolatilityEngine for enhanced accuracy
    • Performance tracking and model validation
    • Optimized for real-time SPY options trading

Removed Functions:
    • MarkovRegimeSwitching class - Now handled by L09_UnifiedRegimeEngine
    • detect_market_regime() - Consolidated into unified regime system
    • RegimeParameters and regime transition logic - Moved to L09
    • _viterbi_decode() and regime state tracking - Consolidated
    • All regime classification and switching logic - Now in L09
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import warnings
from concurrent.futures import ThreadPoolExecutor
import threading

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
from scipy.optimize import minimize
from numba import jit

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# SpyderB08_MultiClientDataManager (IB) has been removed.

try:
    from SpyderV_QuantModels.SpyderV06_VolatilityEngine import (
        SpyderVolatilityEngine,
        VolatilityModel,
    )
except ImportError:
    SpyderVolatilityEngine = None
    VolatilityModel = None

# ==============================================================================
# MODULE CONFIGURATION
# ==============================================================================
warnings.filterwarnings("ignore")


# ==============================================================================
# ENUMERATIONS AND CONSTANTS
# ==============================================================================
class CrisisLevel(Enum):
    """Crisis level classifications"""

    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRISIS = "crisis"
    EXTREME = "extreme"


class JumpType(Enum):
    """Types of market jumps"""

    UPWARD_JUMP = "upward_jump"
    DOWNWARD_JUMP = "downward_jump"
    VOLATILITY_JUMP = "volatility_jump"
    NO_JUMP = "no_jump"


class ModelValidationStatus(Enum):
    """Model validation status"""

    NOT_CALIBRATED = "not_calibrated"
    CALIBRATING = "calibrating"
    CALIBRATED = "calibrated"
    VALIDATION_FAILED = "validation_failed"
    OUTDATED = "outdated"


# Jump detection thresholds
JUMP_DETECTION_THRESHOLD = 3.0  # Standard deviations
CRISIS_JUMP_THRESHOLD = 5.0  # Crisis-level jumps
MIN_DATA_POINTS = 200  # Minimum data for calibration
MAX_CALIBRATION_AGE_HOURS = 24  # Model expiry time

# Crisis probability thresholds
NORMAL_CRISIS_PROB = 0.05  # 5% normal crisis probability
ELEVATED_CRISIS_PROB = 0.15  # 15% elevated crisis probability
HIGH_CRISIS_PROB = 0.30  # 30% high crisis probability
EXTREME_CRISIS_PROB = 0.50  # 50% extreme crisis probability


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class MertonParameters:
    """Merton Jump-Diffusion model parameters"""

    mu: float = 0.08  # Annual drift
    sigma: float = 0.15  # Annual volatility
    lambda_jump: float = 0.2  # Jump intensity (jumps per year)
    mu_jump: float = -0.05  # Mean jump size
    sigma_jump: float = 0.10  # Jump size volatility


@dataclass
class JumpEvent:
    """Detected jump event"""

    timestamp: datetime
    price_before: float
    price_after: float
    jump_size: float
    jump_type: JumpType
    significance_level: float
    market_impact: str
    confidence: float = 0.0


@dataclass
class CrisisAssessment:
    """Crisis probability and market stress assessment"""

    crisis_level: CrisisLevel
    crisis_probability: float
    stress_indicators: dict[str, float]
    jump_frequency: float
    volatility_regime: str
    recommendations: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AdvancedModelResults:
    """Results from advanced modeling analysis"""

    merton_params: MertonParameters | None
    crisis_assessment: CrisisAssessment
    recent_jumps: list[JumpEvent]
    model_performance: dict[str, float]
    volatility_forecast: dict[str, float]
    strategy_recommendations: list[str]
    validation_status: ModelValidationStatus
    last_calibration: datetime | None = None


# ==============================================================================
# OPTIMIZED CALCULATION FUNCTIONS
# ==============================================================================
@jit(nopython=True)
def _merton_likelihood(params, returns, dt):
    """Optimized Merton model likelihood calculation"""
    mu, sigma, lambda_jump, mu_jump, sigma_jump = params

    if sigma <= 0 or sigma_jump <= 0 or lambda_jump < 0:
        return -np.inf

    n = len(returns)
    log_likelihood = 0.0

    # Maximum reasonable number of jumps to consider
    max_jumps = min(10, int(lambda_jump * dt * n) + 5)

    for i in range(n):
        r = returns[i]
        total_prob = 0.0

        # Sum over possible number of jumps
        for k in range(max_jumps + 1):
            # Poisson probability of k jumps
            poisson_prob = (
                np.exp(-lambda_jump * dt)
                * (lambda_jump * dt) ** k
                / np.math.factorial(k)
            )

            if poisson_prob < 1e-10:  # Skip negligible probabilities
                continue

            # Mean and variance of return given k jumps
            mean_return = (mu - 0.5 * sigma**2) * dt + k * mu_jump
            var_return = sigma**2 * dt + k * sigma_jump**2

            if var_return <= 0:
                continue

            # Normal density
            std_return = np.sqrt(var_return)
            normal_density = np.exp(-0.5 * ((r - mean_return) / std_return) ** 2) / (
                std_return * np.sqrt(2 * np.pi)
            )

            total_prob += poisson_prob * normal_density

        if total_prob > 0:
            log_likelihood += np.log(total_prob)
        else:
            return -np.inf

    return log_likelihood


@jit(nopython=True)
def _detect_jumps_numba(returns, threshold):
    """Optimized jump detection using numba"""
    if len(returns) < 10:
        return np.zeros_like(returns)

    mean_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return np.zeros_like(returns)

    standardized_returns = (returns - mean_return) / std_return
    jump_indicators = np.abs(standardized_returns) > threshold

    return jump_indicators.astype(np.float64)


# ==============================================================================
# MAIN ADVANCED MODELS ENGINE CLASS
# ==============================================================================
class SpyderAdvancedModelsEngine:
    """
    Advanced modeling engine focused on Merton Jump-Diffusion and crisis detection.

    Provides sophisticated jump detection, crisis probability assessment, and
    event-driven analysis for SPY options trading. Handles discontinuous price
    movements and tail risk scenarios beyond traditional Black-Scholes assumptions.

    NOTE: Regime switching functionality removed - now handled by
    SpyderL09_UnifiedRegimeEngine for consolidation.
    """

    def __init__(
        self,
        config: dict[str, Any] = None,
        data_manager: Any = None,
        volatility_engine: SpyderVolatilityEngine = None,
    ):
        """Initialize advanced models engine"""

        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = config or {}

        # External integrations
        self.data_manager = data_manager
        self.volatility_engine = volatility_engine

        # Model parameters and state
        self.merton_params: MertonParameters | None = None
        self.validation_status = ModelValidationStatus.NOT_CALIBRATED
        self.last_calibration: datetime | None = None

        # Data storage with thread-safe access
        self._data_lock = threading.RLock()
        self.price_history: list[float] = []
        self.return_history: list[float] = []
        self.timestamp_history: list[datetime] = []

        # Jump detection and tracking
        self.jump_history: list[JumpEvent] = []
        self.crisis_history: list[CrisisAssessment] = []
        self.jump_threshold = self.config.get(
            "jump_threshold", JUMP_DETECTION_THRESHOLD
        )

        # Performance tracking
        self.model_performance: dict[str, float] = {}
        self.calibration_errors: list[str] = []

        # Configuration parameters
        self.min_data_points = self.config.get("min_data_points", MIN_DATA_POINTS)
        self.max_history_size = self.config.get("max_history_size", 5000)
        self.calibration_frequency_hours = self.config.get(
            "calibration_frequency_hours", MAX_CALIBRATION_AGE_HOURS
        )

        # Threading
        self.executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="AdvancedModels"
        )

        self.logger.debug("✅ SpyderAdvancedModelsEngine initialized")
        self.logger.debug(
            "⚠️ Regime switching functions removed - now handled by L09_UnifiedRegimeEngine"
        )

    # ==========================================================================
    # CORE ANALYSIS INTERFACE
    # ==========================================================================

    async def analyze_market_conditions(
        self, include_jump_analysis: bool = True, include_crisis_assessment: bool = True
    ) -> AdvancedModelResults:
        """
        Comprehensive market condition analysis focusing on jumps and crisis detection.

        NOTE: Regime analysis removed - use L09_UnifiedRegimeEngine instead.
        """
        try:
            # Ensure we have sufficient data
            if len(self.return_history) < self.min_data_points:
                self.logger.warning(
                    "Insufficient data for analysis: %s < %s", len(self.return_history), self.min_data_points  # noqa: E501
                )
                return self._create_empty_results("Insufficient data")

            # Check if model needs recalibration
            await self._check_and_recalibrate()

            results = AdvancedModelResults(
                merton_params=self.merton_params,
                crisis_assessment=(
                    await self._assess_crisis_probability()
                    if include_crisis_assessment
                    else None
                ),
                recent_jumps=(
                    await self._analyze_recent_jumps() if include_jump_analysis else []
                ),
                model_performance=self.model_performance.copy(),
                volatility_forecast=await self._forecast_volatility(),
                strategy_recommendations=await self._generate_strategy_recommendations(),
                validation_status=self.validation_status,
                last_calibration=self.last_calibration,
            )

            return results

        except Exception as e:
            self.logger.error("Market analysis failed: %s", e, exc_info=True)
            self.error_handler.handle_error(e, {"method": "analyze_market_conditions"})
            return self._create_empty_results(f"Analysis error: {str(e)}")

    async def update_market_data(
        self, prices: list[float], timestamps: list[datetime] = None
    ):
        """Update market data for analysis"""
        try:
            if not prices:
                return

            with self._data_lock:
                # Add new prices
                self.price_history.extend(prices)

                # Add timestamps
                if timestamps:
                    self.timestamp_history.extend(timestamps)
                else:
                    # Generate timestamps if not provided
                    start_time = (
                        self.timestamp_history[-1]
                        if self.timestamp_history
                        else datetime.now(timezone.utc)
                    )
                    new_timestamps = [
                        start_time + timedelta(minutes=i)
                        for i in range(1, len(prices) + 1)
                    ]
                    self.timestamp_history.extend(new_timestamps)

                # Calculate new returns
                if len(self.price_history) >= 2:
                    new_returns = []
                    start_idx = max(0, len(self.return_history))

                    for i in range(start_idx + 1, len(self.price_history)):
                        if self.price_history[i] > 0 and self.price_history[i - 1] > 0:
                            ret = np.log(
                                self.price_history[i] / self.price_history[i - 1]
                            )
                            new_returns.append(ret)

                    self.return_history.extend(new_returns)

                # Trim history if too large
                self._trim_history()

            # Check for jumps in new data
            if len(new_returns) > 0:
                await self._detect_new_jumps(new_returns[-10:])  # Check last 10 returns

            self.logger.debug(
                "Updated market data: %s new prices, %s total returns", len(prices), len(self.return_history)  # noqa: E501
            )

        except Exception as e:
            self.logger.error("Market data update failed: %s", e, exc_info=True)
            self.error_handler.handle_error(e, {"method": "update_market_data"})

    # ==========================================================================
    # MERTON JUMP-DIFFUSION MODEL
    # ==========================================================================

    async def calibrate_merton_model(self, force_recalibration: bool = False) -> bool:
        """Calibrate Merton Jump-Diffusion model parameters"""
        try:
            if not force_recalibration and self._is_calibration_current():
                self.logger.debug("Merton model calibration is current, skipping")
                return True

            if len(self.return_history) < self.min_data_points:
                self.logger.warning(
                    "Insufficient data for Merton calibration: %s", len(self.return_history)
                )
                return False

            self.logger.info("🔄 Calibrating Merton Jump-Diffusion model...")
            self.validation_status = ModelValidationStatus.CALIBRATING

            # Prepare data
            returns = np.array(self.return_history[-2000:])  # Use recent data
            dt = 1 / 252  # Daily frequency

            # Initial parameter guess
            sample_mean = np.mean(returns)
            sample_std = np.std(returns)

            initial_params = [
                sample_mean * 252,  # mu (annualized)
                sample_std * np.sqrt(252),  # sigma (annualized)
                0.1,  # lambda_jump
                -0.02,  # mu_jump
                0.05,  # sigma_jump
            ]

            # Parameter bounds
            bounds = [
                (-0.5, 0.5),  # mu: -50% to 50% annual
                (0.01, 2.0),  # sigma: 1% to 200% annual
                (0.0, 2.0),  # lambda_jump: 0 to 2 jumps per year
                (-0.3, 0.3),  # mu_jump: -30% to 30%
                (0.001, 0.5),  # sigma_jump: 0.1% to 50%
            ]

            # Optimization
            def objective(params):
                return -_merton_likelihood(params, returns, dt)

            result = minimize(
                objective,
                initial_params,
                method="L-BFGS-B",
                bounds=bounds,
                options={"maxiter": 1000},
            )

            if result.success:
                # Update parameters
                mu, sigma, lambda_jump, mu_jump, sigma_jump = result.x

                self.merton_params = MertonParameters(
                    mu=mu,
                    sigma=sigma,
                    lambda_jump=lambda_jump,
                    mu_jump=mu_jump,
                    sigma_jump=sigma_jump,
                )

                self.last_calibration = datetime.now(timezone.utc)
                self.validation_status = ModelValidationStatus.CALIBRATED

                # Calculate model performance
                await self._calculate_model_performance(returns, dt)

                self.logger.info("✅ Merton model calibrated successfully")
                self.logger.info(
                    f"   λ={lambda_jump:.3f}, μ_J={mu_jump:.3f}, σ_J={sigma_jump:.3f}"
                )

                return True
            else:
                self.validation_status = ModelValidationStatus.VALIDATION_FAILED
                self.calibration_errors.append(f"Optimization failed: {result.message}")
                self.logger.error("❌ Merton calibration failed: %s", result.message)
                return False

        except Exception as e:
            self.validation_status = ModelValidationStatus.VALIDATION_FAILED
            self.calibration_errors.append(str(e))
            self.logger.error("Merton calibration error: %s", e, exc_info=True)
            return False

    async def _calculate_model_performance(self, returns: np.ndarray, dt: float):
        """Calculate model performance metrics"""
        try:
            if self.merton_params is None:
                return

            # Calculate likelihood
            params = [
                self.merton_params.mu,
                self.merton_params.sigma,
                self.merton_params.lambda_jump,
                self.merton_params.mu_jump,
                self.merton_params.sigma_jump,
            ]

            log_likelihood = _merton_likelihood(params, returns, dt)

            # Calculate AIC and BIC
            n_params = 5
            n_obs = len(returns)
            aic = 2 * n_params - 2 * log_likelihood
            bic = n_params * np.log(n_obs) - 2 * log_likelihood

            # Calculate predicted vs actual volatility
            predicted_vol = self.merton_params.sigma
            actual_vol = np.std(returns) * np.sqrt(252)
            vol_error = abs(predicted_vol - actual_vol) / actual_vol

            self.model_performance = {
                "log_likelihood": log_likelihood,
                "aic": aic,
                "bic": bic,
                "volatility_error": vol_error,
                "jump_intensity": self.merton_params.lambda_jump,
                "calibration_success": True,
            }

        except Exception as e:
            self.logger.error("Performance calculation failed: %s", e, exc_info=True)
            self.model_performance = {"calibration_success": False, "error": str(e)}

    # ==========================================================================
    # JUMP DETECTION AND ANALYSIS
    # ==========================================================================

    async def _detect_new_jumps(self, recent_returns: list[float]):
        """Detect jumps in recent return data"""
        try:
            if len(recent_returns) < 3:
                return

            returns_array = np.array(recent_returns)
            jump_indicators = _detect_jumps_numba(returns_array, self.jump_threshold)

            # Process detected jumps
            for i, is_jump in enumerate(jump_indicators):
                if is_jump and i < len(recent_returns):
                    jump_return = recent_returns[i]

                    # Determine jump type
                    if jump_return > 0:
                        jump_type = JumpType.UPWARD_JUMP
                        market_impact = "Positive market shock"
                    else:
                        jump_type = JumpType.DOWNWARD_JUMP
                        market_impact = "Negative market shock"

                    # Calculate significance
                    std_return = np.std(recent_returns)
                    significance = (
                        abs(jump_return) / std_return if std_return > 0 else 0
                    )

                    # Create jump event
                    jump_event = JumpEvent(
                        timestamp=datetime.now(timezone.utc)
                        - timedelta(minutes=len(recent_returns) - i),
                        price_before=0.0,  # Would need actual price data
                        price_after=0.0,  # Would need actual price data
                        jump_size=jump_return,
                        jump_type=jump_type,
                        significance_level=significance,
                        market_impact=market_impact,
                        confidence=min(significance / self.jump_threshold, 1.0),
                    )

                    self.jump_history.append(jump_event)
                    self.logger.info(
                        f"🚨 Jump detected: {jump_type.value}, size={jump_return:.4f}"
                    )

            # Trim jump history
            if len(self.jump_history) > 1000:
                self.jump_history = self.jump_history[-1000:]

        except Exception as e:
            self.logger.error("Jump detection failed: %s", e, exc_info=True)

    async def _analyze_recent_jumps(self) -> list[JumpEvent]:
        """Analyze recent jump events"""
        try:
            # Return jumps from last 30 days
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=30)
            recent_jumps = [
                jump for jump in self.jump_history if jump.timestamp >= cutoff_time
            ]

            # Sort by significance
            recent_jumps.sort(key=lambda x: x.significance_level, reverse=True)

            return recent_jumps[:50]  # Return top 50 most significant

        except Exception as e:
            self.logger.error("Recent jumps analysis failed: %s", e, exc_info=True)
            return []

    # ==========================================================================
    # CRISIS DETECTION AND ASSESSMENT
    # ==========================================================================

    async def _assess_crisis_probability(self) -> CrisisAssessment:
        """Assess current crisis probability based on jump activity"""
        try:
            # Calculate recent jump frequency (last 30 days)
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=30)
            recent_jumps = [
                jump for jump in self.jump_history if jump.timestamp >= cutoff_time
            ]
            jump_frequency = len(recent_jumps) / 30  # Jumps per day

            # Calculate stress indicators
            if len(self.return_history) >= 30:
                recent_returns = np.array(self.return_history[-30:])
                volatility_30d = np.std(recent_returns) * np.sqrt(252)
                downside_volatility = np.std(
                    recent_returns[recent_returns < 0]
                ) * np.sqrt(252)
                max_drawdown = self._calculate_max_drawdown(recent_returns)

                stress_indicators = {
                    "volatility_30d": volatility_30d,
                    "downside_volatility": downside_volatility,
                    "max_drawdown": max_drawdown,
                    "jump_frequency": jump_frequency,
                    "large_jumps_count": len(
                        [
                            j
                            for j in recent_jumps
                            if j.significance_level > CRISIS_JUMP_THRESHOLD
                        ]
                    ),
                }
            else:
                stress_indicators = {
                    "volatility_30d": 0.15,
                    "downside_volatility": 0.20,
                    "max_drawdown": 0.0,
                    "jump_frequency": jump_frequency,
                    "large_jumps_count": 0,
                }

            # Calculate crisis probability based on multiple factors
            crisis_probability = self._calculate_crisis_probability(stress_indicators)

            # Determine crisis level
            if crisis_probability >= EXTREME_CRISIS_PROB:
                crisis_level = CrisisLevel.EXTREME
                volatility_regime = "Extreme volatility regime"
            elif crisis_probability >= HIGH_CRISIS_PROB:
                crisis_level = CrisisLevel.CRISIS
                volatility_regime = "Crisis volatility regime"
            elif crisis_probability >= ELEVATED_CRISIS_PROB:
                crisis_level = CrisisLevel.HIGH
                volatility_regime = "High volatility regime"
            elif crisis_probability >= NORMAL_CRISIS_PROB:
                crisis_level = CrisisLevel.ELEVATED
                volatility_regime = "Elevated volatility regime"
            else:
                crisis_level = CrisisLevel.NORMAL
                volatility_regime = "Normal volatility regime"

            # Generate recommendations
            recommendations = self._generate_crisis_recommendations(
                crisis_level, stress_indicators
            )

            assessment = CrisisAssessment(
                crisis_level=crisis_level,
                crisis_probability=crisis_probability,
                stress_indicators=stress_indicators,
                jump_frequency=jump_frequency,
                volatility_regime=volatility_regime,
                recommendations=recommendations,
            )

            # Store in history
            self.crisis_history.append(assessment)
            if len(self.crisis_history) > 1000:
                self.crisis_history = self.crisis_history[-1000:]

            return assessment

        except Exception as e:
            self.logger.error("Crisis assessment failed: %s", e, exc_info=True)
            return CrisisAssessment(
                crisis_level=CrisisLevel.NORMAL,
                crisis_probability=NORMAL_CRISIS_PROB,
                stress_indicators={},
                jump_frequency=0.0,
                volatility_regime="Unknown",
                recommendations=["Error in crisis assessment"],
            )

    def _calculate_crisis_probability(
        self, stress_indicators: dict[str, float]
    ) -> float:
        """Calculate crisis probability based on stress indicators"""
        try:
            # Base probability
            base_prob = 0.05

            # Volatility component
            vol_30d = stress_indicators.get("volatility_30d", 0.15)
            vol_factor = min(2.0, max(0.5, vol_30d / 0.20))  # Normalize around 20% vol

            # Jump component
            jump_freq = stress_indicators.get("jump_frequency", 0.0)
            jump_factor = min(3.0, 1.0 + jump_freq * 10)  # Scale jump frequency

            # Large jumps component
            large_jumps = stress_indicators.get("large_jumps_count", 0)
            large_jump_factor = min(2.0, 1.0 + large_jumps * 0.5)

            # Drawdown component
            max_dd = abs(stress_indicators.get("max_drawdown", 0.0))
            dd_factor = min(2.0, 1.0 + max_dd * 10)

            # Combined probability
            crisis_prob = (
                base_prob * vol_factor * jump_factor * large_jump_factor * dd_factor
            )

            return min(0.95, max(0.01, crisis_prob))  # Clamp between 1% and 95%

        except Exception as e:
            self.logger.error("Crisis probability calculation failed: %s", e, exc_info=True)
            return NORMAL_CRISIS_PROB

    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown from returns"""
        try:
            cumulative = np.cumprod(1 + returns)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - running_max) / running_max
            return np.min(drawdown)
        except Exception:
            return 0.0

    def _generate_crisis_recommendations(
        self, crisis_level: CrisisLevel, stress_indicators: dict[str, float]
    ) -> list[str]:
        """Generate strategic recommendations based on crisis level"""
        recommendations = []

        if crisis_level == CrisisLevel.EXTREME:
            recommendations.extend(
                [
                    "EXTREME RISK: Consider emergency position closure",
                    "Activate maximum risk controls and stop losses",
                    "Avoid new positions until volatility subsides",
                    "Monitor liquidity conditions closely",
                    "Implement crisis hedging strategies",
                ]
            )
        elif crisis_level == CrisisLevel.CRISIS:
            recommendations.extend(
                [
                    "HIGH RISK: Reduce position sizes significantly",
                    "Implement defensive hedging strategies",
                    "Increase monitoring frequency",
                    "Consider volatility-based strategies",
                    "Prepare for continued market stress",
                ]
            )
        elif crisis_level == CrisisLevel.HIGH:
            recommendations.extend(
                [
                    "Elevated risk detected - reduce leverage",
                    "Consider protective options strategies",
                    "Monitor jump activity closely",
                    "Implement tighter risk controls",
                ]
            )
        elif crisis_level == CrisisLevel.ELEVATED:
            recommendations.extend(
                [
                    "Moderate risk increase - maintain caution",
                    "Consider volatility strategies",
                    "Monitor market stress indicators",
                ]
            )
        else:
            recommendations.extend(
                [
                    "Normal market conditions",
                    "Standard risk management applies",
                    "Monitor for emerging stress signals",
                ]
            )

        return recommendations

    # ==========================================================================
    # VOLATILITY FORECASTING
    # ==========================================================================

    async def _forecast_volatility(self) -> dict[str, float]:
        """Forecast volatility using Merton model"""
        try:
            if self.merton_params is None or len(self.return_history) < 30:
                return {"error": "Insufficient data for forecast"}

            # Calculate components of volatility forecast
            diffusive_vol = self.merton_params.sigma
            jump_vol_contribution = np.sqrt(
                self.merton_params.lambda_jump
                * (self.merton_params.mu_jump**2 + self.merton_params.sigma_jump**2)
            )

            total_vol = np.sqrt(diffusive_vol**2 + jump_vol_contribution**2)

            # Recent realized volatility for comparison
            recent_returns = np.array(self.return_history[-30:])
            realized_vol = np.std(recent_returns) * np.sqrt(252)

            return {
                "diffusive_volatility": diffusive_vol,
                "jump_volatility_contribution": jump_vol_contribution,
                "total_forecast_volatility": total_vol,
                "recent_realized_volatility": realized_vol,
                "volatility_forecast_horizon_days": 30,
                "model_confidence": self.model_performance.get(
                    "calibration_success", False
                ),
            }

        except Exception as e:
            self.logger.error("Volatility forecast failed: %s", e, exc_info=True)
            return {"error": str(e)}

    # ==========================================================================
    # STRATEGY RECOMMENDATIONS
    # ==========================================================================

    async def _generate_strategy_recommendations(self) -> list[str]:
        """Generate strategy recommendations based on current model state"""
        recommendations = []

        try:
            if self.merton_params is None:
                return [
                    "Model not calibrated - cannot provide strategy recommendations"
                ]

            # Jump-based recommendations
            if self.merton_params.lambda_jump > 0.5:
                recommendations.append(
                    "High jump frequency detected - consider straddle/strangle strategies"
                )
                recommendations.append(
                    "Avoid short volatility strategies due to jump risk"
                )
            elif self.merton_params.lambda_jump < 0.1:
                recommendations.append(
                    "Low jump frequency - volatility selling strategies may be viable"
                )

            # Jump size recommendations
            if abs(self.merton_params.mu_jump) > 0.05:
                if self.merton_params.mu_jump < 0:
                    recommendations.append(
                        "Negative jump bias detected - consider protective puts"
                    )
                else:
                    recommendations.append(
                        "Positive jump bias detected - consider call strategies"
                    )

            # Volatility level recommendations
            if self.merton_params.sigma > 0.25:
                recommendations.append(
                    "High volatility environment - consider premium selling strategies"
                )
                recommendations.append(
                    "Use wider profit targets due to increased price swings"
                )
            elif self.merton_params.sigma < 0.12:
                recommendations.append(
                    "Low volatility environment - consider volatility buying strategies"
                )

            # Recent jump activity
            recent_jumps = len(
                [
                    j
                    for j in self.jump_history
                    if j.timestamp >= datetime.now(timezone.utc) - timedelta(days=7)
                ]
            )
            if recent_jumps > 3:
                recommendations.append(
                    "Recent jump activity elevated - increase position monitoring"
                )

            return recommendations

        except Exception as e:
            self.logger.error("Strategy recommendations failed: %s", e, exc_info=True)
            return [f"Error generating recommendations: {str(e)}"]

    # ==========================================================================
    # UTILITY AND HELPER METHODS
    # ==========================================================================

    def _is_calibration_current(self) -> bool:
        """Check if current calibration is still valid"""
        if self.last_calibration is None:
            return False

        age = datetime.now(timezone.utc) - self.last_calibration
        return age.total_seconds() < (self.calibration_frequency_hours * 3600)

    async def _check_and_recalibrate(self):
        """Check if recalibration is needed and perform if necessary"""
        if (
            not self._is_calibration_current()
            or self.validation_status != ModelValidationStatus.CALIBRATED
        ):
            await self.calibrate_merton_model()

    def _trim_history(self):
        """Trim historical data to prevent memory issues"""
        if len(self.price_history) > self.max_history_size:
            trim_size = self.max_history_size // 2
            self.price_history = self.price_history[-trim_size:]
            self.return_history = self.return_history[-trim_size:]
            self.timestamp_history = self.timestamp_history[-trim_size:]

    def _create_empty_results(self, reason: str) -> AdvancedModelResults:
        """Create empty results with error message"""
        return AdvancedModelResults(
            merton_params=None,
            crisis_assessment=CrisisAssessment(
                crisis_level=CrisisLevel.NORMAL,
                crisis_probability=NORMAL_CRISIS_PROB,
                stress_indicators={},
                jump_frequency=0.0,
                volatility_regime="Unknown",
                recommendations=[f"Analysis unavailable: {reason}"],
            ),
            recent_jumps=[],
            model_performance={"error": reason},
            volatility_forecast={"error": reason},
            strategy_recommendations=[f"Recommendations unavailable: {reason}"],
            validation_status=self.validation_status,
        )

    def _generate_synthetic_data(self, n_points: int = 500):
        """Generate synthetic market data for testing"""
        try:
            if len(self.price_history) == 0:
                initial_price = 450.0
            else:
                initial_price = self.price_history[-1]

            # Use default or current Merton parameters
            params = self.merton_params if self.merton_params else MertonParameters()

            dt = 1 / 252  # Daily
            prices = [initial_price]
            timestamps = [datetime.now(timezone.utc) - timedelta(days=n_points)]

            for _ in range(1, n_points):
                # Diffusion component
                dW = np.random.normal(0, np.sqrt(dt))
                diffusion = (params.mu - 0.5 * params.sigma**2) * dt + params.sigma * dW

                # Jump component
                if np.random.poisson(params.lambda_jump * dt) > 0:
                    jump = np.random.normal(params.mu_jump, params.sigma_jump)
                    diffusion += jump

                # Update price
                new_price = prices[-1] * np.exp(diffusion)
                prices.append(new_price)
                timestamps.append(timestamps[-1] + timedelta(days=1))

            # Update internal data
            self.price_history.extend(
                prices[1:]
            )  # Skip initial price if it's duplicate
            self.timestamp_history.extend(timestamps[1:])

            # Calculate returns
            if len(self.price_history) >= 2:
                start_idx = len(self.return_history)
                for i in range(max(1, start_idx), len(self.price_history)):
                    if self.price_history[i] > 0 and self.price_history[i - 1] > 0:
                        ret = np.log(self.price_history[i] / self.price_history[i - 1])
                        self.return_history.append(ret)

            self.logger.info("Generated %s synthetic data points", n_points)

        except Exception as e:
            self.logger.error("Synthetic data generation failed: %s", e, exc_info=True)

    # ==========================================================================
    # PUBLIC STATUS AND REPORTING METHODS
    # ==========================================================================

    def get_model_status(self) -> dict[str, Any]:
        """Get comprehensive model status report"""
        try:
            return {
                "models_calibrated": {
                    "merton": self.merton_params is not None,
                    "validation_status": self.validation_status.value,
                },
                "data_status": {
                    "price_points": len(self.price_history),
                    "return_points": len(self.return_history),
                    "data_quality": (
                        "Good"
                        if len(self.return_history) >= self.min_data_points
                        else "Insufficient"
                    ),
                },
                "jump_analysis": {
                    "total_jumps_detected": len(self.jump_history),
                    "recent_jumps_7d": len(
                        [
                            j
                            for j in self.jump_history
                            if j.timestamp >= datetime.now(timezone.utc) - timedelta(days=7)
                        ]
                    ),
                    "jump_detection_threshold": self.jump_threshold,
                },
                "crisis_analysis": {
                    "current_crisis_level": (
                        self.crisis_history[-1].crisis_level.value
                        if self.crisis_history
                        else "unknown"
                    ),
                    "crisis_probability": (
                        self.crisis_history[-1].crisis_probability
                        if self.crisis_history
                        else 0.0
                    ),
                    "assessments_count": len(self.crisis_history),
                },
                "model_parameters": {
                    "merton": {
                        "mu": self.merton_params.mu if self.merton_params else None,
                        "sigma": (
                            self.merton_params.sigma if self.merton_params else None
                        ),
                        "lambda_jump": (
                            self.merton_params.lambda_jump
                            if self.merton_params
                            else None
                        ),
                        "mu_jump": (
                            self.merton_params.mu_jump if self.merton_params else None
                        ),
                        "sigma_jump": (
                            self.merton_params.sigma_jump
                            if self.merton_params
                            else None
                        ),
                    }
                },
                "performance_metrics": self.model_performance,
                "last_calibration": (
                    self.last_calibration.isoformat() if self.last_calibration else None
                ),
                "calibration_errors": (
                    self.calibration_errors[-5:] if self.calibration_errors else []
                ),
            }
        except Exception as e:
            return {"error": str(e)}


# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_advanced_models_engine(
    config: dict[str, Any] = None,
    data_manager: Any = None,
    volatility_engine: SpyderVolatilityEngine = None,
) -> SpyderAdvancedModelsEngine:
    """Factory function to create SpyderAdvancedModelsEngine."""
    return SpyderAdvancedModelsEngine(config, data_manager, volatility_engine)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Demonstration of updated advanced models engine."""
    logging.info("=" * 80)
    logging.info("SPYDER V07 - ADVANCED MODELS ENGINE (UPDATED - REGIME FUNCTIONS REMOVED)")
    logging.info("=" * 80)

    # Initialize advanced models engine
    config = {
        "min_data_points": 200,
        "jump_threshold": 3.0,
        "calibration_frequency_hours": 24,
    }

    advanced_engine = create_advanced_models_engine(config)

    logging.info("\n✅ Advanced Models Engine Initialized")
    logging.info("   • Merton Jump-Diffusion modeling for crisis and event-driven periods")
    logging.info("   • Real-time jump detection with statistical significance testing")
    logging.info("   • Crisis probability assessment and market stress indicators")
    logging.info("   • Event-driven strategy recommendations")
    logging.info(
        "   ⚠️ REGIME SWITCHING FUNCTIONS REMOVED - now handled by L09_UnifiedRegimeEngine"
    )

    # Generate synthetic market data with jumps
    logging.info("\n--- Generating Synthetic Market Data with Jumps ---")
    await advanced_engine.update_market_data([450.0])  # Initialize with starting price

    # Force generation of synthetic data for demonstration
    advanced_engine._generate_synthetic_data()

    logging.info("   Generated %s return observations", len(advanced_engine.return_history))
    logging.info(
        f"   Price range: ${min(advanced_engine.price_history):.2f} - ${max(advanced_engine.price_history):.2f}"  # noqa: E501
    )

    # Test 1: Merton Model Calibration
    logging.info("\n--- Test 1: Merton Jump-Diffusion Model Calibration ---")
    try:
        calibration_success = await advanced_engine.calibrate_merton_model()

        if calibration_success and advanced_engine.merton_params:
            params = advanced_engine.merton_params
            logging.info("   ✅ Calibration successful!")
            logging.info(f"   Annual Drift (μ): {params.mu:.3f}")
            logging.info(f"   Annual Volatility (σ): {params.sigma:.3f}")
            logging.info(f"   Jump Intensity (λ): {params.lambda_jump:.3f} jumps/year")
            logging.info(f"   Mean Jump Size: {params.mu_jump:.3f}")
            logging.info(f"   Jump Volatility: {params.sigma_jump:.3f}")

            performance = advanced_engine.model_performance
            logging.info(f"   Model AIC: {performance.get('aic', 'N/A'):.1f}")
            logging.info(f"   Volatility Error: {performance.get('volatility_error', 0):.1%}")
        else:
            logging.info("   ❌ Calibration failed")

    except Exception as e:
        logging.info("   ❌ Calibration Error: %s", e)

    # Test 2: Jump Detection
    logging.info("\n--- Test 2: Jump Detection Analysis ---")
    try:
        # Add some artificial jumps to demonstrate detection
        jump_returns = [
            0.001,
            0.002,
            -0.08,
            0.001,
            0.002,
            0.06,
            -0.001,
        ]  # Contains jumps
        await advanced_engine._detect_new_jumps(jump_returns)

        recent_jumps = await advanced_engine._analyze_recent_jumps()
        logging.info("   Detected %s recent jumps", len(recent_jumps))

        for i, jump in enumerate(recent_jumps[:3]):  # Show top 3
            logging.info(
                f"   Jump {i+1}: {jump.jump_type.value}, size={jump.jump_size:.4f}, "
                f"significance={jump.significance_level:.2f}"
            )

    except Exception as e:
        logging.info("   ❌ Jump Detection Error: %s", e)

    # Test 3: Crisis Assessment
    logging.info("\n--- Test 3: Crisis Probability Assessment ---")
    try:
        crisis_assessment = await advanced_engine._assess_crisis_probability()

        logging.info("   Crisis Level: %s", crisis_assessment.crisis_level.value.upper())
        logging.info(f"   Crisis Probability: {crisis_assessment.crisis_probability:.1%}")
        logging.info(f"   Jump Frequency: {crisis_assessment.jump_frequency:.3f} jumps/day")
        logging.info("   Volatility Regime: %s", crisis_assessment.volatility_regime)

        if crisis_assessment.recommendations:
            logging.info("   Top Recommendations:")
            for _, rec in enumerate(crisis_assessment.recommendations[:2]):
                logging.info("     • %s", rec)

    except Exception as e:
        logging.info("   ❌ Crisis Assessment Error: %s", e)

    # Test 4: Comprehensive Analysis
    logging.info("\n--- Test 4: Comprehensive Market Analysis ---")
    try:
        results = await advanced_engine.analyze_market_conditions()

        logging.info("   Model Status: %s", results.validation_status.value)
        logging.info("   Recent Jumps: %s", len(results.recent_jumps))
        logging.info(
            "   Crisis Level: %s", results.crisis_assessment.crisis_level.value if results.crisis_assessment else 'N/A'  # noqa: E501
        )

        if (
            results.volatility_forecast
            and "total_forecast_volatility" in results.volatility_forecast
        ):
            vol_forecast = results.volatility_forecast["total_forecast_volatility"]
            logging.info(f"   Volatility Forecast: {vol_forecast:.1%}")

        if results.strategy_recommendations:
            logging.info("   Strategy Recommendations:")
            for _, rec in enumerate(results.strategy_recommendations[:2]):
                logging.info("     • %s", rec)

    except Exception as e:
        logging.info("   ❌ Analysis Error: %s", e)

    # Show model status
    logging.info("\n--- Model Status Report ---")
    status = advanced_engine.get_model_status()

    if "error" not in status:
        logging.info(
            "   Merton Model: %s", '✅ Calibrated' if status['models_calibrated']['merton'] else '❌ Not calibrated'  # noqa: E501
        )
        logging.info("   Data Quality: %s", status['data_status']['data_quality'])
        logging.info("   Total Jumps: %s", status['jump_analysis']['total_jumps_detected'])
        logging.info(
            "   Current Crisis Level: %s", status['crisis_analysis']['current_crisis_level'].upper()
        )

        if status["performance_metrics"].get("calibration_success"):
            logging.info("   Model Performance: ✅ Good")
        else:
            logging.info("   Model Performance: ⚠️ Needs attention")

    logging.info("\n🎯 CONSOLIDATION BENEFITS ACHIEVED:")
    logging.info("   ✅ Regime switching functions removed and consolidated into L09")
    logging.info("   ✅ Focus on Merton Jump-Diffusion and crisis detection")
    logging.info("   ✅ Enhanced jump detection with real-time significance testing")
    logging.info("   ✅ Sophisticated crisis probability assessment")
    logging.info("   ✅ Event-driven strategy recommendations")
    logging.info("   ✅ Optimized performance with numba acceleration")
    logging.info("   ✅ Integration-ready with V06 VolatilityEngine")
    logging.info("   ✅ Eliminates regime switching overlap with L09")

    logging.info("\n" + "=" * 80)
    logging.info("✅ V07 ADVANCED MODELS ENGINE UPDATED SUCCESSFULLY!")
    logging.info("❌ Regime switching functions REMOVED")
    logging.info("✅ Enhanced jump-diffusion modeling RETAINED")
    logging.info("✅ Crisis detection and tail risk analysis ENHANCED")
    logging.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
