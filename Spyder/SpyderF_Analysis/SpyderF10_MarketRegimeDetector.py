#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF10_MarketRegimeDetector.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-14

DEPRECATED (2026-04-14): L09 UnifiedRegimeEngine is the canonical regime
    detector for Spyder. This module is retained for legacy F-series callers
    only. New callers MUST use L09. See also: this module's F00 protocol
    implementation of calculate_all_indicators() currently returns empty
    snapshots — callers should set stub_mode=True explicitly to opt in.

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, timezone
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from collections import deque
import threading
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats
from arch import arch_model  # For GARCH modeling

try:
    import ruptures as rpt  # Change-point detection for regime shifts
    _RUPTURES_AVAILABLE = True
except ImportError:
    _RUPTURES_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils

VIX_LOW_THRESHOLD = 16.0
VIX_MEDIUM_THRESHOLD = 25.0
VIX_HIGH_THRESHOLD = 30.0
VIX_EXTREME_THRESHOLD = 40.0

# Trend detection parameters
TREND_LOOKBACK_PERIODS = 20
TREND_STRENGTH_THRESHOLD = 0.65

# Volatility clustering parameters
GARCH_P = 1  # GARCH(p,q) parameters
GARCH_Q = 1
CLUSTERING_WINDOW = 252  # 1 year

# Mean reversion parameters
MEAN_REVERSION_HALFLIFE = 20  # Days
MEAN_REVERSION_THRESHOLD = 2.0  # Standard deviations

# Monitoring intervals
REGIME_UPDATE_INTERVAL = 60  # Seconds
STRESS_CHECK_INTERVAL = 300  # 5 minutes

# Confidence thresholds
REGIME_CONFIDENCE_THRESHOLD = 0.75
TRANSITION_CONFIDENCE_THRESHOLD = 0.80

# Configuration management
CONFIG_UPDATE_INTERVAL = 3600  # 1 hour


# ==============================================================================
# ENUMS
# ==============================================================================
class MarketRegime(Enum):
    """Market volatility regimes"""

    LOW_VOLATILITY = "low_volatility"
    NORMAL = "normal"
    HIGH_VOLATILITY = "high_volatility"
    EXTREME_VOLATILITY = "extreme_volatility"


class TrendRegime(Enum):
    """Market trend regimes"""

    STRONG_BEARISH = "strong_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    STRONG_BULLISH = "strong_bullish"


class VolatilityCluster(Enum):
    """Volatility clustering states"""

    LOW_CLUSTER = "low_cluster"
    MODERATE_CLUSTER = "moderate_cluster"
    HIGH_CLUSTER = "high_cluster"
    EXTREME_CLUSTER = "extreme_cluster"


class LiquidityRegime(Enum):
    """Market liquidity conditions"""

    HIGH_LIQUIDITY = "high_liquidity"
    NORMAL_LIQUIDITY = "normal_liquidity"
    LOW_LIQUIDITY = "low_liquidity"
    ILLIQUID = "illiquid"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class RegimeMetrics:
    """Market regime metrics"""

    timestamp: datetime

    # VIX metrics
    vix_level: float
    vix_percentile: float
    vix_trend: float
    vix_term_structure: float

    # Price metrics
    spy_price: float
    price_trend: float
    trend_strength: float
    momentum: float

    # Volatility metrics
    realized_volatility: float
    implied_volatility: float
    volatility_ratio: float
    volatility_percentile: float

    # Volume metrics
    volume_ratio: float
    volume_trend: float

    # Internals
    advance_decline_ratio: float
    new_highs_lows_ratio: float

    # Stress indicators
    term_structure_stress: float
    volatility_skew: float
    correlation_stress: float
    liquidity_stress: float

    # Mean reversion
    mean_reversion_speed: float
    oversold_probability: float
    overbought_probability: float


@dataclass
class RegimeState:
    """Current market regime state"""

    timestamp: datetime

    # Primary regime classifications
    volatility_regime: MarketRegime
    trend_regime: TrendRegime
    clustering_regime: VolatilityCluster
    liquidity_regime: LiquidityRegime

    # Confidence levels
    regime_confidence: float
    transition_probability: float

    # Strategy implications
    optimal_strategies: list[str]
    risk_adjustment_factor: float

    # Regime stability
    regime_duration_days: int
    expected_duration_days: float

    # Supporting metrics
    metrics: RegimeMetrics


@dataclass
class RegimeTransition:
    """Regime transition event"""

    timestamp: datetime
    from_regime: MarketRegime
    to_regime: MarketRegime
    transition_probability: float
    trigger_factors: list[str]
    recommended_actions: list[str]


# ==============================================================================
# MARKET REGIME DETECTOR CLASS
# ==============================================================================
class MarketRegimeDetector:
    """
    Professional market regime detection system.

    Implements institutional-grade regime analysis including:
    - VIX-based volatility regime classification
    - Volatility clustering detection using GARCH models
    - Mean reversion analysis and trend detection
    - Market stress indicators and correlation breakdowns
    - Real-time regime monitoring with confidence levels
    - Strategy optimization based on regime state
    """

    def __init__(
        self,
        market_data_feed=None,
        volatility_analyzer=None,
        market_internals=None,
        config_manager=None,
    ):
        """Initialize market regime detector."""
        # Dependencies
        self.market_data_feed = market_data_feed
        self.volatility_analyzer = volatility_analyzer
        self.market_internals = market_internals
        self.config_manager = config_manager

        # Logging
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.time_utils = TradingTimeUtils()

        # Current state
        self.current_regime: RegimeState | None = None
        self.regime_history: deque = deque(maxlen=252)  # 1 year of regime history

        # Historical data for analysis
        self.vix_history: deque = deque(maxlen=252)
        self.spy_price_history: deque = deque(maxlen=252)
        self.volume_history: deque = deque(maxlen=252)

        # Volatility clustering model
        self.garch_model = None
        self.volatility_states = deque(maxlen=100)

        # Monitoring
        self.monitoring_active = False
        self._stop_event = threading.Event()
        self.monitor_thread: threading.Thread | None = None

        # Callbacks
        self.regime_change_callbacks: list[Callable] = []
        self.stress_alert_callbacks: list[Callable] = []

        # Performance tracking
        self.regime_accuracy_history = deque(maxlen=50)

        # Configuration
        self._load_configuration()

        # Strategy mapping
        self._initialize_strategy_mapping()

        self.logger.info("Market Regime Detector initialized with strategy selection")

    # ==========================================================================
    # PUBLIC METHODS - CORE FUNCTIONALITY
    # ==========================================================================
    def start_monitoring(self) -> None:
        """Start real-time regime monitoring."""
        if self.monitoring_active:
            self.logger.warning("Regime monitoring already active")
            return

        self.monitoring_active = True
        self._stop_event.clear()
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop, name="RegimeDetector", daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("Market regime monitoring started")

    def stop_monitoring(self) -> None:
        """Stop regime monitoring."""
        self.monitoring_active = False
        self._stop_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5.0)
        self.logger.info("Market regime monitoring stopped")

    def get_current_regime(self, symbol: str = "") -> RegimeState | None:
        """Get current market regime state.

        Args:
            symbol: Ticker symbol (unused — F10 tracks a single global regime).
                    Accepted for compatibility with AnalyticsProviderProtocol.
        """
        return self.current_regime

    # ------------------------------------------------------------------
    # AnalyticsProviderProtocol stubs
    # F10 is a regime detector; the two indicator-side methods below are
    # minimal stubs so that isinstance(detector, AnalyticsProviderProtocol)
    # passes.  Full indicator calculation lives in F01.
    # ------------------------------------------------------------------

    def calculate_all_indicators(self, symbol: str, data: Any = None) -> Any:
        """Protocol stub — indicator calculation lives in SpyderF01.

        F10 is a regime detector, not an indicator provider. Returning an
        empty `IndicatorSnapshot` used to satisfy the structural Protocol
        check while silently delivering no data — a footgun. Callers must
        now route indicator requests to F01 (IndicatorEngine). Returning
        None here makes the mismatch loud instead of silent.
        """
        return None

    def get_trading_signals(self, symbol: str = "") -> list:
        """Protocol stub — trading signal generation lives in SpyderF01."""
        return []

    def detect_regime_change(self) -> RegimeTransition | None:
        """Detect potential regime change."""
        try:
            # Calculate current metrics
            current_metrics = self._calculate_regime_metrics()
            if not current_metrics:
                return None

            # Classify new regime
            new_regime = self._classify_volatility_regime(current_metrics)

            # Check for regime change
            if (
                self.current_regime
                and new_regime != self.current_regime.volatility_regime
            ):

                # Calculate transition probability
                transition_prob = self._calculate_transition_probability(
                    self.current_regime.volatility_regime, new_regime, current_metrics
                )

                if transition_prob > REGIME_CONFIDENCE_THRESHOLD:
                    # Create transition event
                    transition = RegimeTransition(
                        timestamp=datetime.now(timezone.utc),
                        from_regime=self.current_regime.volatility_regime,
                        to_regime=new_regime,
                        transition_probability=transition_prob,
                        trigger_factors=self._identify_transition_triggers(
                            current_metrics
                        ),
                        recommended_actions=self._get_transition_recommendations(
                            self.current_regime.volatility_regime, new_regime
                        ),
                    )

                    return transition

            return None

        except Exception as e:
            self.error_handler.handle_error(e, "detect_regime_change")
            return None

    def get_optimal_strategies_for_regime(
        self, regime: MarketRegime | None = None
    ) -> list[str]:
        """Get optimal strategies for current or specified regime."""
        try:
            if regime is None:
                if not self.current_regime:
                    return ["D01_BaseStrategy"]  # Default
                regime = self.current_regime.volatility_regime

            # Map regimes to optimal strategies
            strategy_map = self.strategy_mappings.get(regime, ["D01_BaseStrategy"])

            # Consider additional factors
            if self.current_regime:
                # Adjust for trend
                if self.current_regime.trend_regime == TrendRegime.STRONG_BULLISH:
                    if "D13_DiagonalStrategy" not in strategy_map:
                        strategy_map.append("D13_DiagonalStrategy")
                elif self.current_regime.trend_regime == TrendRegime.STRONG_BEARISH:
                    if "D07_BearCallSpread" not in strategy_map:
                        strategy_map.append("D07_BearCallSpread")

                # Consider volatility clustering
                if (
                    self.current_regime.clustering_regime
                    == VolatilityCluster.HIGH_CLUSTER
                ):
                    if "D14_StraddleStrangle" not in strategy_map:
                        strategy_map.append("D14_StraddleStrangle")

            return strategy_map

        except Exception as e:
            self.error_handler.handle_error(e, "get_optimal_strategies_for_regime")
            return ["D01_BaseStrategy"]

    def get_risk_adjustment_factor(self) -> float:
        """Get risk adjustment factor for current regime."""
        try:
            if not self.current_regime:
                return 1.0

            # Base adjustment on volatility regime
            regime_factors = {
                MarketRegime.LOW_VOLATILITY: 0.8,
                MarketRegime.NORMAL: 1.0,
                MarketRegime.HIGH_VOLATILITY: 1.5,
                MarketRegime.EXTREME_VOLATILITY: 2.0,
            }

            base_factor = regime_factors.get(self.current_regime.volatility_regime, 1.0)

            # Adjust for trend strength
            trend_adjustment = 1.0
            if abs(self.current_regime.metrics.trend_strength) > 0.8:
                trend_adjustment = 1.2

            # Adjust for stress indicators
            stress_adjustment = 1.0
            stress_level = self._calculate_overall_stress(self.current_regime.metrics)
            if stress_level > 0.7:
                stress_adjustment = 1.3

            # Combine factors
            total_factor = base_factor * trend_adjustment * stress_adjustment

            # Cap adjustment
            return min(max(total_factor, 0.5), 3.0)

        except Exception as e:
            self.error_handler.handle_error(e, "get_risk_adjustment_factor")
            return 1.0

    def analyze_volatility_clustering(self) -> dict[str, float]:
        """Analyze volatility clustering using GARCH model."""
        try:
            if len(self.spy_price_history) < 100:
                return {
                    "clustering_strength": 0.5,
                    "persistence": 0.5,
                    "half_life": 20.0,
                }

            # Calculate returns
            prices = pd.Series([p for p in self.spy_price_history])
            returns = prices.pct_change().dropna() * 100  # Percentage returns

            # Fit GARCH model
            model = arch_model(returns, vol="Garch", p=GARCH_P, q=GARCH_Q)
            fitted = model.fit(disp="off")

            # Extract clustering metrics
            alpha = fitted.params.get("alpha[1]", 0.0)
            beta = fitted.params.get("beta[1]", 0.0)
            persistence = alpha + beta

            # Calculate half-life
            half_life = (
                -np.log(0.5) / np.log(persistence) if persistence < 1 else np.inf
            )

            # Determine clustering strength
            if persistence > 0.95:
                clustering_strength = 1.0
            elif persistence > 0.85:
                clustering_strength = 0.75
            elif persistence > 0.70:
                clustering_strength = 0.5
            else:
                clustering_strength = 0.25

            return {
                "clustering_strength": clustering_strength,
                "persistence": persistence,
                "half_life": half_life,
                "alpha": alpha,
                "beta": beta,
            }

        except Exception as e:
            self.error_handler.handle_error(e, "analyze_volatility_clustering")
            return {"clustering_strength": 0.5, "persistence": 0.5, "half_life": 20.0}

    def calculate_mean_reversion_metrics(self) -> dict[str, float]:
        """Calculate mean reversion metrics using Ornstein-Uhlenbeck process."""
        try:
            if len(self.vix_history) < 50:
                return {
                    "mean_reversion_speed": 0.1,
                    "long_term_mean": 20.0,
                    "current_deviation": 0.0,
                    "reversion_probability": 0.5,
                }

            # VIX series
            vix_series = pd.Series([v for v in self.vix_history])

            # Calculate parameters
            mean = vix_series.mean()
            current = vix_series.iloc[-1]
            deviation = (current - mean) / vix_series.std()

            # Estimate mean reversion speed (simplified)
            lagged = vix_series.shift(1).dropna()
            current_vals = vix_series.iloc[1:]

            # Linear regression: dx = theta * (mu - x) * dt
            X = mean - lagged
            y = current_vals - lagged

            if len(X) > 0:
                theta = np.dot(X, y) / np.dot(X, X)
                theta = max(0.01, min(theta, 1.0))  # Constrain theta
            else:
                theta = 0.1

            # Calculate reversion probability
            if abs(deviation) > 2:
                reversion_prob = 0.9
            elif abs(deviation) > 1:
                reversion_prob = 0.7
            else:
                reversion_prob = 0.5

            return {
                "mean_reversion_speed": theta,
                "long_term_mean": mean,
                "current_deviation": deviation,
                "reversion_probability": reversion_prob,
            }

        except Exception as e:
            self.error_handler.handle_error(e, "calculate_mean_reversion_metrics")
            return {
                "mean_reversion_speed": 0.1,
                "long_term_mean": 20.0,
                "current_deviation": 0.0,
                "reversion_probability": 0.5,
            }

    def assess_market_stress(self) -> dict[str, float]:
        """Assess market stress indicators."""
        try:
            stress_indicators = {}

            # VIX stress
            if len(self.vix_history) > 0:
                current_vix = self.vix_history[-1]
                vix_mean = np.mean(list(self.vix_history))
                vix_stress = min((current_vix - vix_mean) / 10.0, 1.0)
                stress_indicators["vix_stress"] = max(0, vix_stress)
            else:
                stress_indicators["vix_stress"] = 0.0

            # Volume stress
            if len(self.volume_history) > 20:
                recent_volume = np.mean(list(self.volume_history)[-5:])
                normal_volume = np.mean(list(self.volume_history)[-20:])
                volume_stress = recent_volume / normal_volume - 1.0
                stress_indicators["volume_stress"] = min(max(volume_stress, 0), 1.0)
            else:
                stress_indicators["volume_stress"] = 0.0

            # Price velocity stress
            if len(self.spy_price_history) > 10:
                prices = list(self.spy_price_history)
                recent_change = abs(prices[-1] - prices[-5]) / prices[-5]
                velocity_stress = min(recent_change / 0.05, 1.0)  # 5% move = max stress
                stress_indicators["velocity_stress"] = velocity_stress
            else:
                stress_indicators["velocity_stress"] = 0.0

            # Correlation stress (simplified)
            stress_indicators["correlation_stress"] = 0.0

            # Overall stress
            stress_indicators["overall_stress"] = np.mean(
                list(stress_indicators.values())
            )

            return stress_indicators

        except Exception as e:
            self.error_handler.handle_error(e, "assess_market_stress")
            return {"overall_stress": 0.0}

    def add_regime_change_callback(
        self, callback: Callable[[RegimeTransition], None]
    ) -> None:
        """Add callback for regime change events."""
        self.regime_change_callbacks.append(callback)

    def add_stress_alert_callback(
        self, callback: Callable[[dict[str, float]], None]
    ) -> None:
        """Add callback for market stress alerts."""
        self.stress_alert_callbacks.append(callback)

    def get_regime_analysis_report(self) -> dict[str, Any]:
        """Generate comprehensive regime analysis report."""
        try:
            current_metrics = self._calculate_regime_metrics()
            clustering_analysis = self.analyze_volatility_clustering()
            mean_reversion = self.calculate_mean_reversion_metrics()
            stress_assessment = self.assess_market_stress()

            return {
                "timestamp": datetime.now(timezone.utc),
                "current_regime": {
                    "volatility_regime": (
                        self.current_regime.volatility_regime.name
                        if self.current_regime
                        else None
                    ),
                    "trend_regime": (
                        self.current_regime.trend_regime.name
                        if self.current_regime
                        else None
                    ),
                    "confidence": (
                        self.current_regime.regime_confidence
                        if self.current_regime
                        else None
                    ),
                    "duration_days": (
                        self.current_regime.regime_duration_days
                        if self.current_regime
                        else None
                    ),
                },
                "market_metrics": {
                    "vix_level": current_metrics.vix_level if current_metrics else None,
                    "vix_percentile": (
                        current_metrics.vix_percentile if current_metrics else None
                    ),
                    "trend_strength": (
                        current_metrics.trend_strength if current_metrics else None
                    ),
                    "volatility_clustering": clustering_analysis["clustering_strength"],
                },
                "mean_reversion": mean_reversion,
                "stress_indicators": stress_assessment,
                "optimal_strategies": self.get_optimal_strategies_for_regime(),
                "risk_adjustment_factor": self.get_risk_adjustment_factor(),
                "regime_history_length": len(self.regime_history),
                "monitoring_status": self.monitoring_active,
            }

        except Exception as e:
            self.error_handler.handle_error(e, "get_regime_analysis_report")
            return {"error": "Failed to generate report"}

    # ==========================================================================
    # PRIVATE METHODS - REGIME DETECTION
    # ==========================================================================
    def _calculate_regime_metrics(self) -> RegimeMetrics | None:
        """Calculate current regime metrics."""
        try:
            # Get market data
            if self.market_data_feed:
                market_data = self.market_data_feed.get_latest_data()
            else:
                # Use mock data for testing
                market_data = self._get_mock_market_data()

            # Calculate VIX metrics
            vix_level = market_data.get("vix", 20.0)
            vix_percentile = self._calculate_vix_percentile(vix_level)

            # Calculate price metrics
            spy_price = market_data.get("spy_price", 400.0)
            price_trend = self._calculate_price_trend()
            trend_strength = self._calculate_trend_strength()

            # Calculate volatility metrics
            realized_vol = market_data.get("realized_volatility", 0.15)
            implied_vol = market_data.get("implied_volatility", 0.18)

            # Calculate volume metrics
            volume_ratio = market_data.get("volume_ratio", 1.0)

            # Calculate internals
            advance_decline = market_data.get("advance_decline_ratio", 1.0)

            # Calculate stress indicators
            stress_indicators = self.assess_market_stress()

            # Create metrics object
            metrics = RegimeMetrics(
                timestamp=datetime.now(timezone.utc),
                vix_level=vix_level,
                vix_percentile=vix_percentile,
                vix_trend=self._calculate_vix_trend(),
                vix_term_structure=market_data.get("vix_term_structure", 1.0),
                spy_price=spy_price,
                price_trend=price_trend,
                trend_strength=trend_strength,
                momentum=self._calculate_momentum(),
                realized_volatility=realized_vol,
                implied_volatility=implied_vol,
                volatility_ratio=(
                    implied_vol / realized_vol if realized_vol > 0 else 1.0
                ),
                volatility_percentile=self._calculate_volatility_percentile(
                    realized_vol
                ),
                volume_ratio=volume_ratio,
                volume_trend=self._calculate_volume_trend(),
                advance_decline_ratio=advance_decline,
                new_highs_lows_ratio=market_data.get("new_highs_lows_ratio", 1.0),
                term_structure_stress=stress_indicators.get("vix_stress", 0.0),
                volatility_skew=market_data.get("volatility_skew", 0.0),
                correlation_stress=stress_indicators.get("correlation_stress", 0.0),
                liquidity_stress=self._calculate_liquidity_stress(volume_ratio),
                mean_reversion_speed=0.1,
                oversold_probability=self._calculate_oversold_probability(),
                overbought_probability=self._calculate_overbought_probability(),
            )

            # Update history
            self.vix_history.append(vix_level)
            self.spy_price_history.append(spy_price)
            self.volume_history.append(market_data.get("volume", 100000000))

            return metrics

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_regime_metrics")
            return None

    def _classify_volatility_regime(self, metrics: RegimeMetrics) -> MarketRegime:
        """Classify market volatility regime."""
        try:
            vix = metrics.vix_level

            if vix < VIX_LOW_THRESHOLD:
                return MarketRegime.LOW_VOLATILITY
            elif vix < VIX_MEDIUM_THRESHOLD:
                return MarketRegime.NORMAL
            elif vix < VIX_HIGH_THRESHOLD:
                return MarketRegime.HIGH_VOLATILITY
            else:
                return MarketRegime.EXTREME_VOLATILITY

        except Exception as e:
            self.error_handler.handle_error(e, "_classify_volatility_regime")
            return MarketRegime.NORMAL

    def _classify_trend_regime(self, metrics: RegimeMetrics) -> TrendRegime:
        """Classify market trend regime."""
        try:
            strength = metrics.trend_strength

            if strength < -0.8:
                return TrendRegime.STRONG_BEARISH
            elif strength < -0.3:
                return TrendRegime.BEARISH
            elif strength < 0.3:
                return TrendRegime.NEUTRAL
            elif strength < 0.8:
                return TrendRegime.BULLISH
            else:
                return TrendRegime.STRONG_BULLISH

        except Exception as e:
            self.error_handler.handle_error(e, "_classify_trend_regime")
            return TrendRegime.NEUTRAL

    def _classify_clustering_regime(
        self, clustering_strength: float
    ) -> VolatilityCluster:
        """Classify volatility clustering regime."""
        try:
            if clustering_strength < 0.3:
                return VolatilityCluster.LOW_CLUSTER
            elif clustering_strength < 0.6:
                return VolatilityCluster.MODERATE_CLUSTER
            elif clustering_strength < 0.85:
                return VolatilityCluster.HIGH_CLUSTER
            else:
                return VolatilityCluster.EXTREME_CLUSTER

        except Exception as e:
            self.error_handler.handle_error(e, "_classify_clustering_regime")
            return VolatilityCluster.MODERATE_CLUSTER

    def _classify_liquidity_regime(self, metrics: RegimeMetrics) -> LiquidityRegime:
        """Classify market liquidity regime."""
        try:
            volume_ratio = metrics.volume_ratio
            liquidity_stress = metrics.liquidity_stress

            if liquidity_stress > 0.7 or volume_ratio < 0.5:
                return LiquidityRegime.ILLIQUID
            elif liquidity_stress > 0.5 or volume_ratio < 0.7:
                return LiquidityRegime.LOW_LIQUIDITY
            elif volume_ratio > 1.3:
                return LiquidityRegime.HIGH_LIQUIDITY
            else:
                return LiquidityRegime.NORMAL_LIQUIDITY

        except Exception as e:
            self.error_handler.handle_error(e, "_classify_liquidity_regime")
            return LiquidityRegime.NORMAL_LIQUIDITY

    # ==========================================================================
    # PRIVATE METHODS - MONITORING
    # ==========================================================================
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.monitoring_active:
            try:
                # Update regime
                self._update_regime_state()

                # Check for regime changes
                transition = self.detect_regime_change()
                if transition:
                    self._handle_regime_transition(transition)

                # Check market stress
                stress_indicators = self.assess_market_stress()
                if stress_indicators.get("overall_stress", 0) > 0.7:
                    self._handle_stress_alert(stress_indicators)

                # Update configuration if needed
                if hasattr(self, "_last_config_update"):
                    if (
                        datetime.now(timezone.utc) - self._last_config_update
                    ).seconds > CONFIG_UPDATE_INTERVAL:
                        self._load_configuration()

                # Sleep
                self._stop_event.wait(REGIME_UPDATE_INTERVAL)

            except Exception as e:
                self.error_handler.handle_error(e, "_monitoring_loop")
                self._stop_event.wait(REGIME_UPDATE_INTERVAL)

    def _update_regime_state(self) -> None:
        """Update current regime state."""
        try:
            # Calculate metrics
            metrics = self._calculate_regime_metrics()
            if not metrics:
                return

            # Classify regimes
            volatility_regime = self._classify_volatility_regime(metrics)
            trend_regime = self._classify_trend_regime(metrics)

            # Get clustering analysis
            clustering = self.analyze_volatility_clustering()
            clustering_regime = self._classify_clustering_regime(
                clustering["clustering_strength"]
            )

            # Classify liquidity
            liquidity_regime = self._classify_liquidity_regime(metrics)

            # Calculate confidence
            confidence = self._calculate_regime_confidence(metrics)

            # Get optimal strategies
            optimal_strategies = self.get_optimal_strategies_for_regime(
                volatility_regime
            )

            # Calculate risk adjustment
            risk_factor = self.get_risk_adjustment_factor()

            # Calculate duration
            duration = 0
            if self.current_regime:
                duration = (datetime.now(timezone.utc) - self.current_regime.timestamp).days

            # Create new regime state
            new_state = RegimeState(
                timestamp=datetime.now(timezone.utc),
                volatility_regime=volatility_regime,
                trend_regime=trend_regime,
                clustering_regime=clustering_regime,
                liquidity_regime=liquidity_regime,
                regime_confidence=confidence,
                transition_probability=0.0,
                optimal_strategies=optimal_strategies,
                risk_adjustment_factor=risk_factor,
                regime_duration_days=duration,
                expected_duration_days=self._estimate_regime_duration(
                    volatility_regime
                ),
                metrics=metrics,
            )

            # Update current regime
            self.current_regime = new_state
            self.regime_history.append(new_state)

        except Exception as e:
            self.error_handler.handle_error(e, "_update_regime_state")

    # ==========================================================================
    # PRIVATE METHODS - CALCULATIONS
    # ==========================================================================
    def _calculate_vix_percentile(self, vix_level: float) -> float:
        """Calculate VIX percentile."""
        try:
            if len(self.vix_history) < 20:
                return 0.5

            vix_array = np.array(list(self.vix_history))
            return stats.percentileofscore(vix_array, vix_level) / 100.0

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_vix_percentile")
            return 0.5

    def _calculate_vix_trend(self) -> float:
        """Calculate VIX trend."""
        try:
            if len(self.vix_history) < 10:
                return 0.0

            recent_vix = list(self.vix_history)[-10:]
            x = np.arange(len(recent_vix))
            slope, _ = np.polyfit(x, recent_vix, 1)

            return slope

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_vix_trend")
            return 0.0

    def _calculate_price_trend(self) -> float:
        """Calculate price trend."""
        try:
            if len(self.spy_price_history) < 20:
                return 0.0

            prices = list(self.spy_price_history)[-20:]
            returns = pd.Series(prices).pct_change().dropna()

            return returns.mean()

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_price_trend")
            return 0.0

    def _calculate_trend_strength(self) -> float:
        """Calculate trend strength using ADX-like metric."""
        try:
            if len(self.spy_price_history) < 20:
                return 0.0

            prices = np.array(list(self.spy_price_history)[-20:])

            # Simple trend strength: correlation with time
            x = np.arange(len(prices))
            correlation = np.corrcoef(x, prices)[0, 1]

            return correlation

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_trend_strength")
            return 0.0

    def _calculate_momentum(self) -> float:
        """Calculate price momentum."""
        try:
            if len(self.spy_price_history) < 10:
                return 0.0

            current = self.spy_price_history[-1]
            past = self.spy_price_history[-10]

            return (current - past) / past if past > 0 else 0.0

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_momentum")
            return 0.0

    def _calculate_volatility_percentile(self, volatility: float) -> float:
        """Calculate volatility percentile."""
        try:
            # Use historical volatility data if available
            # For now, use a simple mapping
            if volatility < 0.10:
                return 0.2
            elif volatility < 0.15:
                return 0.4
            elif volatility < 0.20:
                return 0.6
            elif volatility < 0.30:
                return 0.8
            else:
                return 0.95

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_volatility_percentile")
            return 0.5

    def _calculate_volume_trend(self) -> float:
        """Calculate volume trend."""
        try:
            if len(self.volume_history) < 10:
                return 0.0

            recent_volume = list(self.volume_history)[-10:]
            x = np.arange(len(recent_volume))
            slope, _ = np.polyfit(x, recent_volume, 1)

            # Normalize by average volume
            avg_volume = np.mean(recent_volume)

            return slope / avg_volume if avg_volume > 0 else 0.0

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_volume_trend")
            return 0.0

    def _calculate_liquidity_stress(self, volume_ratio: float) -> float:
        """Calculate liquidity stress indicator."""
        try:
            # Low volume = high stress
            if volume_ratio < 0.5:
                return 1.0
            elif volume_ratio < 0.7:
                return 0.7
            elif volume_ratio < 0.9:
                return 0.3
            else:
                return 0.0

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_liquidity_stress")
            return 0.0

    def _calculate_oversold_probability(self) -> float:
        """Calculate probability of oversold condition."""
        try:
            if not self.current_regime:
                return 0.5

            metrics = self.current_regime.metrics

            # Factors indicating oversold
            factors = []

            # VIX extreme
            if metrics.vix_level > VIX_HIGH_THRESHOLD:
                factors.append(0.3)

            # Price momentum negative
            if metrics.momentum < -0.05:
                factors.append(0.3)

            # Mean reversion metrics
            mean_rev = self.calculate_mean_reversion_metrics()
            if mean_rev["current_deviation"] < -2:
                factors.append(0.4)

            return min(sum(factors), 1.0)

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_oversold_probability")
            return 0.5

    def _calculate_overbought_probability(self) -> float:
        """Calculate probability of overbought condition."""
        try:
            if not self.current_regime:
                return 0.5

            metrics = self.current_regime.metrics

            # Factors indicating overbought
            factors = []

            # VIX extreme low
            if metrics.vix_level < VIX_LOW_THRESHOLD * 0.8:
                factors.append(0.3)

            # Price momentum positive
            if metrics.momentum > 0.05:
                factors.append(0.3)

            # Mean reversion metrics
            mean_rev = self.calculate_mean_reversion_metrics()
            if mean_rev["current_deviation"] > 2:
                factors.append(0.4)

            return min(sum(factors), 1.0)

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_overbought_probability")
            return 0.5

    def _calculate_overall_stress(self, metrics: RegimeMetrics) -> float:
        """Calculate overall market stress level."""
        try:
            stress_components = [
                metrics.term_structure_stress,
                metrics.volatility_skew,
                metrics.correlation_stress,
                metrics.liquidity_stress,
            ]

            return np.mean(stress_components)

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_overall_stress")
            return 0.0

    def _calculate_regime_confidence(self, metrics: RegimeMetrics) -> float:
        """Calculate regime classification confidence."""
        try:
            # Base confidence on consistency of indicators
            confidence_factors = []

            # VIX percentile alignment
            vix_confidence = abs(metrics.vix_percentile - 0.5) * 2
            confidence_factors.append(vix_confidence)

            # Trend strength
            trend_confidence = abs(metrics.trend_strength)
            confidence_factors.append(trend_confidence)

            # Volume consistency
            volume_confidence = 1.0 - abs(metrics.volume_ratio - 1.0)
            confidence_factors.append(volume_confidence)

            return np.mean(confidence_factors)

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_regime_confidence")
            return 0.5

    def _calculate_transition_probability(
        self, from_regime: MarketRegime, to_regime: MarketRegime, metrics: RegimeMetrics
    ) -> float:
        """Calculate regime transition probability."""
        try:
            # Base transition matrix (simplified)
            base_prob = 0.1  # Base 10% chance

            # Adjust for regime distance
            regime_order = [
                MarketRegime.LOW_VOLATILITY,
                MarketRegime.NORMAL,
                MarketRegime.HIGH_VOLATILITY,
                MarketRegime.EXTREME_VOLATILITY,
            ]

            from_idx = regime_order.index(from_regime)
            to_idx = regime_order.index(to_regime)
            distance = abs(to_idx - from_idx)

            # Closer regimes have higher transition probability
            distance_factor = 1.0 / (1.0 + distance)

            # Adjust for current metrics
            metric_factor = 1.0

            # VIX trend supports transition
            if metrics.vix_trend > 0 and to_idx > from_idx or metrics.vix_trend < 0 and to_idx < from_idx:  # noqa: E501
                metric_factor *= 1.5

            # Stress indicators
            stress = self._calculate_overall_stress(metrics)
            if stress > 0.7:
                metric_factor *= 1.3

            # Calculate final probability
            transition_prob = base_prob * distance_factor * metric_factor

            return min(transition_prob, 0.95)

        except Exception as e:
            self.error_handler.handle_error(e, "_calculate_transition_probability")
            return 0.5

    def _estimate_regime_duration(self, regime: MarketRegime) -> float:
        """Estimate expected regime duration in days."""
        try:
            # Historical average durations (simplified)
            average_durations = {
                MarketRegime.LOW_VOLATILITY: 45,
                MarketRegime.NORMAL: 60,
                MarketRegime.HIGH_VOLATILITY: 30,
                MarketRegime.EXTREME_VOLATILITY: 15,
            }

            return average_durations.get(regime, 30)

        except Exception as e:
            self.error_handler.handle_error(e, "_estimate_regime_duration")
            return 30

    # ==========================================================================
    # PRIVATE METHODS - EVENT HANDLING
    # ==========================================================================
    def _handle_regime_transition(self, transition: RegimeTransition) -> None:
        """Handle regime transition event."""
        try:
            self.logger.info(
                f"Regime transition detected: {transition.from_regime.value} -> "
                f"{transition.to_regime.value} (confidence: {transition.transition_probability:.2%})"  # noqa: E501
            )

            # Notify callbacks
            for callback in self.regime_change_callbacks:
                try:
                    callback(transition)
                except Exception as e:
                    self.logger.error("Error in regime change callback: %s", e)

            # Update strategy recommendations
            self._update_strategy_recommendations(transition)

        except Exception as e:
            self.error_handler.handle_error(e, "_handle_regime_transition")

    def _handle_stress_alert(self, stress_indicators: dict[str, float]) -> None:
        """Handle market stress alert."""
        try:
            self.logger.warning(
                f"Market stress alert: Overall stress = {stress_indicators['overall_stress']:.2%}"
            )

            # Notify callbacks
            for callback in self.stress_alert_callbacks:
                try:
                    callback(stress_indicators)
                except Exception as e:
                    self.logger.error("Error in stress alert callback: %s", e)

        except Exception as e:
            self.error_handler.handle_error(e, "_handle_stress_alert")

    # ==========================================================================
    # PRIVATE METHODS - HELPERS
    # ==========================================================================
    def _identify_transition_triggers(self, metrics: RegimeMetrics) -> list[str]:
        """Identify factors triggering regime transition."""
        triggers = []

        # VIX level change
        if metrics.vix_level > VIX_HIGH_THRESHOLD:
            triggers.append("VIX above high threshold")
        elif metrics.vix_level < VIX_LOW_THRESHOLD:
            triggers.append("VIX below low threshold")

        # Trend change
        if abs(metrics.trend_strength) > 0.8:
            triggers.append("Strong trend detected")

        # Volume spike
        if metrics.volume_ratio > 2.0:
            triggers.append("Abnormal volume spike")

        # Stress indicators
        if metrics.term_structure_stress > 0.7:
            triggers.append("Term structure stress")

        return triggers

    def _get_transition_recommendations(
        self, from_regime: MarketRegime, to_regime: MarketRegime
    ) -> list[str]:
        """Get recommended actions for regime transition."""
        recommendations = []

        # Volatility increase
        if from_regime in [
            MarketRegime.LOW_VOLATILITY,
            MarketRegime.NORMAL,
        ] and to_regime in [
            MarketRegime.HIGH_VOLATILITY,
            MarketRegime.EXTREME_VOLATILITY,
        ]:
            recommendations.extend(
                [
                    "Reduce position sizes",
                    "Consider hedging strategies",
                    "Tighten stop losses",
                    "Switch to defensive strategies",
                ]
            )

        # Volatility decrease
        elif from_regime in [
            MarketRegime.HIGH_VOLATILITY,
            MarketRegime.EXTREME_VOLATILITY,
        ] and to_regime in [MarketRegime.LOW_VOLATILITY, MarketRegime.NORMAL]:
            recommendations.extend(
                [
                    "Consider increasing position sizes",
                    "Explore income strategies",
                    "Reduce hedging",
                    "Look for mean reversion opportunities",
                ]
            )

        # Normal transitions
        else:
            recommendations.extend(
                [
                    "Monitor regime stability",
                    "Adjust strategy parameters",
                    "Review risk limits",
                ]
            )

        return recommendations

    def _initialize_strategy_mapping(self) -> None:
        """Initialize regime to strategy mapping."""
        self.strategy_mappings = {
            MarketRegime.LOW_VOLATILITY: [
                "D02_IronCondor",
                "D03_CreditSpread",
                "D12_Butterfly",
                "D15_JadeLizard",
            ],
            MarketRegime.NORMAL: [
                "D03_CreditSpread",
                "D04_IronButterfly",
                "D05_BullPutSpread",
                "D06_BullCallSpread",
            ],
            MarketRegime.HIGH_VOLATILITY: [
                "D14_StraddleStrangle",
                "D13_DiagonalStrategy",
                "D11_SpecializedZeroDTE",
                "D08_Calendar",
            ],
            MarketRegime.EXTREME_VOLATILITY: [
                "D14_StraddleStrangle",
                "D16_RatioSpreads",
                "D09_Backspread",
            ],
        }

    def _update_strategy_recommendations(self, transition: RegimeTransition) -> None:
        """Update strategy recommendations after regime change."""
        try:
            new_strategies = self.get_optimal_strategies_for_regime(
                transition.to_regime
            )

            self.logger.info(
                f"Updated strategy recommendations for {transition.to_regime.value}: "
                f"{', '.join(new_strategies)}"
            )

            # Could emit event here for strategy manager

        except Exception as e:
            self.error_handler.handle_error(e, "_update_strategy_recommendations")

    def _load_configuration(self) -> None:
        """Load configuration from ConfigManager."""
        try:
            if self.config_manager:
                config = self.config_manager.get_config("market_regime_detector")

                # Update thresholds
                global VIX_LOW_THRESHOLD, VIX_MEDIUM_THRESHOLD, VIX_HIGH_THRESHOLD
                VIX_LOW_THRESHOLD = config.get("vix_low_threshold", VIX_LOW_THRESHOLD)
                VIX_MEDIUM_THRESHOLD = config.get(
                    "vix_medium_threshold", VIX_MEDIUM_THRESHOLD
                )
                VIX_HIGH_THRESHOLD = config.get(
                    "vix_high_threshold", VIX_HIGH_THRESHOLD
                )

                # Update strategy mappings if provided
                if "strategy_mappings" in config:
                    self.strategy_mappings.update(config["strategy_mappings"])

            self._last_config_update = datetime.now(timezone.utc)

        except Exception as e:
            self.error_handler.handle_error(e, "_load_configuration")

    def _get_mock_market_data(self) -> dict[str, float]:
        """Get mock market data for testing."""
        return {
            "vix": 20.0 + np.random.randn() * 5,
            "spy_price": 400.0 + np.random.randn() * 10,
            "realized_volatility": 0.15 + np.random.randn() * 0.05,
            "implied_volatility": 0.18 + np.random.randn() * 0.05,
            "volume": 100000000 + np.random.randn() * 20000000,
            "volume_ratio": 1.0 + np.random.randn() * 0.3,
            "advance_decline_ratio": 1.0 + np.random.randn() * 0.5,
            "new_highs_lows_ratio": 1.0 + np.random.randn() * 0.5,
            "vix_term_structure": 1.0 + np.random.randn() * 0.1,
            "volatility_skew": np.random.randn() * 0.2,
        }


    # ==========================================================================
    # CHANGE-POINT DETECTION (ruptures)
    # ==========================================================================
    def detect_change_points(
        self,
        signal: np.ndarray,
        n_bkps: int = 5,
        model: str = "rbf",
        min_size: int = 10,
    ) -> list[int]:
        """
        Detect structural break-points in a price/volatility signal using the
        ruptures library (Pelt algorithm with RBF cost by default).

        Args:
            signal: 1-D numpy array of observations (returns, vola, etc.).
            n_bkps: Maximum number of break-points to search for.
            model: ruptures cost model — "rbf" (non-linear), "l2" (mean-shift),
                   "l1" (robust), "ar" (auto-regressive).
            min_size: Minimum segment length (samples).

        Returns:
            List of change-point indices (last index is len(signal)).
        """
        if not _RUPTURES_AVAILABLE:
            self.logger.warning("ruptures not available — skipping change-point detection")
            return []
        try:
            algo = rpt.Pelt(model=model, min_size=min_size).fit(signal)
            breakpoints = algo.predict(pen=np.log(len(signal)) * signal.var())
            return breakpoints
        except Exception as e:
            self.error_handler.handle_error(e, "detect_change_points")
            return []

    def detect_regime_change_points_from_history(self, n_bkps: int = 5) -> list[int]:
        """
        Run change-point detection on the internal VIX history buffer.

        Returns:
            List of change-point indices in the VIX history.
        """
        if len(self.vix_history) < 20:
            return []
        signal = np.array(list(self.vix_history), dtype=float)
        bkps = self.detect_change_points(signal, n_bkps=n_bkps)
        if bkps:
            self.logger.info(
                f"Ruptures found {len(bkps) - 1} regime break-points in VIX history "
                f"at indices: {bkps[:-1]}"
            )
        return bkps


# ==============================================================================
# MODULE TEST
# ==============================================================================
if __name__ == "__main__":

    # Create detector
    detector = MarketRegimeDetector()



    # Start monitoring
    detector.start_monitoring()

    # Simulate some data updates
    for _i in range(5):
        time.sleep(2)  # thread-safe: time.sleep() intentional

        # Get current regime
        regime = detector.get_current_regime()
        if regime:
            pass

    # Get analysis report
    report = detector.get_regime_analysis_report()

    for _key, value in report["market_metrics"].items():
        if value is not None:
            pass

    for _key, _ in report["stress_indicators"].items():
        pass

    for _strategy in report["optimal_strategies"]:
        pass

    # Stop monitoring
    detector.stop_monitoring()

