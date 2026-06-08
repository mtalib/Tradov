#!/usr/bin/env python3
"""
TRADOV - Automated TRAD Options Trading System

Series: TradovE_Risk
Module: TradovE21_HMMRegimeDetector.py
Purpose: Hidden Markov Model (HMM) for Market Regime Detection
Author: TRADOV Team
Date Created: 2025-01-04
Last Updated: 2026-04-14

DEPRECATED (2026-04-14): L09 UnifiedRegimeEngine is the canonical regime
    detector for Tradov. This module is retained for research / legacy
    compatibility only. New callers MUST use L09.

Description:
    Implements Hidden Markov Models (HMM) for market regime detection,
    inspired by Renaissance Technologies' quantitative framework.

    HMMs identify hidden market states (Bull, Chop, Crisis) from
    observable data (returns, volatility, VIX). This enables
    regime-gated strategy selection, avoiding "strategy mismatch" errors
    where wrong strategies are deployed during inappropriate market conditions.

    Based on Renaissance research, HMMs provide probabilistic
    "weather forecast" for markets, allowing traders to dress portfolios
    appropriately for expected conditions.

Key Features:
    - 3-state HMM (Bull/Chop/Crisis)
    - Baum-Welch algorithm for training
    - Regime probability outputs
    - Regime-gated strategy selection
    - Integration with existing Tradov strategies
    - Real-time regime prediction

Dependencies:
    - hmmlearn>=0.2.8
    - numpy, pandas for data processing
    - scipy for statistical operations
    - TradovE20_FrustrationAnalyzer for market state assessment

References:
    - Baum, L. et al. (1970) "A Maximization Technique Occurring in the
      Statistical Analysis of Probabilistic Functions of Markov Type"
    - Renaissance Technologies research on HMM applications
    - Quantitative finance literature on regime detection
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, UTC
import warnings
from collections import deque  # v27 SPEC-18: bounded histories

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
except ImportError:
    # Fallback logging if custom modules not available
    import logging
    TradovLogger = logging.getLogger
    TradovErrorHandler = type('TradovErrorHandler', (), {
        'handle_error': lambda self, e, context: logging.error("[%s] %s", context, e)
    })

# ==============================================================================
# HMM IMPORTS
# ==============================================================================
try:
    from hmmlearn import hmm
    from hmmlearn.hmm import GaussianHMM, GMMHMM  # noqa: F401
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    warnings.warn(
        "hmmlearn not installed. HMM regime detection disabled. "
        "Install with: pip install hmmlearn", stacklevel=2
    )

# ==============================================================================
# CONSTANTS
# ==============================================================================

# HMM Configuration
HMM_N_STATES = 3  # Bull, Chop, Crisis
HMM_N_ITERATIONS = 100  # Maximum EM iterations
HMM_CONVERGENCE_THRESHOLD = 1e-6  # Convergence threshold
HMM_MIN_OBSERVATIONS = 100  # Minimum observations for training

# Market State Definitions
class MarketRegime(Enum):
    """Market regime classification based on HMM state."""
    BULL = "bull"          # Low volatility, positive drift
    CHOP = "chop"          # High volatility, mean-reverting
    CRISIS = "crisis"       # Extreme volatility, negative drift
    UNKNOWN = "unknown"      # Insufficient data

# Regime Characteristics
REGIME_CHARACTERISTICS = {
    MarketRegime.BULL: {
        "volatility": "low",
        "drift": "positive",
        "optimal_strategy": "calendar_spreads",
        "greek_profile": "positive_delta",
        "description": "Calm market with upward bias"
    },
    MarketRegime.CHOP: {
        "volatility": "high",
        "drift": "neutral",
        "optimal_strategy": "iron_condors",
        "greek_profile": "neutral_delta",
        "description": "Volatile, range-bound market"
    },
    MarketRegime.CRISIS: {
        "volatility": "extreme",
        "drift": "negative",
        "optimal_strategy": "long_straddles",
        "greek_profile": "negative_delta",
        "description": "Market crash or panic conditions"
    }
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class HMMTrainingResult:
    """Results from HMM training."""
    model: Any  # Trained HMM model
    converged: bool  # Whether training converged
    log_likelihood: float  # Final log-likelihood
    bic: float  # Bayesian Information Criterion
    aic: float  # Akaike Information Criterion
    n_states: int  # Number of states
    n_params: int  # Number of parameters
    training_time: float  # Training time in seconds
    transition_matrix: np.ndarray | None = None  # State transition probabilities
    stationary_distribution: Any | None = None  # Stationary distribution

@dataclass
class RegimePrediction:
    """Real-time regime prediction."""
    timestamp: datetime
    current_regime: MarketRegime
    regime_probabilities: dict[MarketRegime, float]  # Probability of each regime
    confidence: float  # Confidence in prediction
    transition_probability: float  # Probability of regime change
    expected_duration: float | None  # Expected days in current regime
    recommended_strategy: str = "neutral"  # Optimal strategy for current regime
    reason: str = ""  # Explanation for prediction

@dataclass
class RegimeGatedStrategySignal:
    """Strategy signal based on regime detection."""
    timestamp: datetime
    current_regime: MarketRegime
    recommended_strategy: str  # Optimal strategy for current regime
    confidence: float  # Confidence in recommendation
    regime_threshold: float  # Minimum probability to switch strategies
    avoid_regimes: list[MarketRegime]  # Regimes to avoid
    reason: str  # Explanation for recommendation

@dataclass
class HMMModelMetrics:
    """HMM model performance metrics."""
    timestamp: datetime
    model_type: str  # "3-state HMM"
    n_states: int
    n_params: int  # Number of parameters
    log_likelihood: float
    bic: float
    aic: float
    transition_matrix: np.ndarray | None  # State transition probabilities
    stationary_distribution: Any | None  # Stationary distribution
    prediction_accuracy: float | None  # Backtest accuracy
    persistence: float = 0.0  # State persistence
    entropy: float = 0.0  # Distribution entropy

# ==============================================================================
# MAIN CLASS
# ==============================================================================

class HMMRegimeDetector:
    """
    Hidden Markov Model (HMM) Regime Detector for Market Analysis.

    Inspired by Renaissance Technologies' quantitative framework, this module
    implements HMMs to identify hidden market states (Bull, Chop, Crisis)
    from observable data (returns, volatility, VIX). This enables
    regime-gated strategy selection, avoiding "strategy mismatch" errors
    where wrong strategies are deployed during inappropriate market conditions.

    Key Concepts:
        - Hidden Markov Model: Observable data generated by latent (hidden) states
        - Baum-Welch Algorithm: Specialized EM algorithm for HMM training
        - Regime Stickiness: Markets exhibit inertia (high probability of staying in state)
        - Regime Transitions: Sudden shifts in volatility dynamics
        - Probabilistic Forecast: HMM provides "weather forecast" for markets

    Example:
        >>> detector = HMMRegimeDetector()
        >>> detector.initialize(historical_returns)
        >>> prediction = detector.predict(current_returns)
        >>> print(f"Regime: {prediction.current_regime}, Confidence: {prediction.confidence:.2%}")
    """

    def __init__(self, n_states: int = HMM_N_STATES,
                 min_observations: int = HMM_MIN_OBSERVATIONS,
                 use_hmm: bool = True):
        """
        Initialize HMM Regime Detector.

        Args:
            n_states: Number of hidden states (default 3)
            min_observations: Minimum observations for training (default 100)
            use_hmm: Whether to use HMM (if hmmlearn available)
        """
        self.logger = TradovLogger.get_logger(__name__)
        self.error_handler = TradovErrorHandler()

        # Configuration
        self.n_states = n_states
        self.min_observations = min_observations
        self.use_hmm = use_hmm and HMM_AVAILABLE

        # Model storage
        self.model: Any | None = None
        self.is_trained: bool = False
        self.training_result: HMMTrainingResult | None = None

        # Historical tracking
        # v27 SPEC-18: bounded histories — prediction_history grows ~390/day
        # during market hours; an unbounded list would OOM on multi-week soak.
        # 2000 entries ≈ 5 trading days of context at 1/min cadence.
        self.regime_history: deque = deque(maxlen=2000)
        self.prediction_history: deque = deque(maxlen=2000)

        # State tracking
        self.current_regime: MarketRegime = MarketRegime.UNKNOWN
        self.days_in_current_regime: int = 0

        # Performance metrics
        self.model_metrics: HMMModelMetrics | None = None

        # Thresholds for regime switching
        self.regime_switch_threshold: float = 0.70  # 70% confidence required
        self.regime_duration_min: int = 5  # Minimum days before considering switch

        self.logger.debug(
            f"HMMRegimeDetector initialized: n_states={n_states}, "
            f"use_hmm={use_hmm}"
        )

        if not self.use_hmm:
            self.logger.warning("HMM not available - using fallback classifier")

    def initialize(self,
                 historical_returns: pd.DataFrame,
                 volatility_data: pd.DataFrame | None = None,
                 vix_data: pd.DataFrame | None = None) -> bool:
        """
        Initialize and train HMM model on historical data.

        Args:
            historical_returns: DataFrame of historical returns (time x assets)
            volatility_data: Optional DataFrame of volatility metrics
            vix_data: Optional DataFrame of VIX levels

        Returns:
            True if initialization successful, False otherwise
        """
        try:
            self.logger.info("Initializing HMM Regime Detector...")

            # Validate input data
            if historical_returns is None or len(historical_returns) < self.min_observations:
                self.logger.error(
                    "Insufficient data: need at least %s observations", self.min_observations
                )
                return False

            # Prepare features for HMM
            features = self._prepare_features(
                historical_returns,
                volatility_data,
                vix_data
            )

            # Train HMM model
            if self.use_hmm:
                self.model, self.training_result = self._train_hmm(features)
            else:
                self.logger.warning("HMM not available - using fallback classifier")
                self._train_fallback_classifier(features)

            # Calculate model metrics
            if self.training_result:
                self.model_metrics = self._calculate_model_metrics(
                    self.training_result,
                    features
                )

            self.is_trained = self.model is not None

            # Initialize regime tracking (v27 SPEC-18: bounded — see __init__)
            self.regime_history = deque(maxlen=2000)
            self.prediction_history = deque(maxlen=2000)

            self.logger.info("HMM Regime Detector initialized successfully")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "HMMRegimeDetector.initialize")
            return False

    def _prepare_features(self,
                     historical_returns: pd.DataFrame,
                     volatility_data: pd.DataFrame | None,
                     vix_data: pd.DataFrame | None) -> np.ndarray:
        """
        Prepare features for HMM training.

        Returns:
            Feature matrix (observations x features)
        """
        self.logger.debug("Preparing HMM features...")

        # Calculate portfolio returns
        if len(historical_returns.columns) > 1:
            portfolio_returns = historical_returns.mean(axis=1)
        else:
            portfolio_returns = historical_returns.iloc[:, 0]

        # Calculate rolling volatility
        rolling_vol = portfolio_returns.rolling(window=20).std()
        rolling_vol = rolling_vol.ffill().values

        # Calculate VIX features if available
        if vix_data is not None and len(vix_data) > 0:
            vix = vix_data.iloc[:, 0].values.flatten()
            vix_ma = pd.Series(vix).rolling(window=20).mean().values.flatten()
        else:
            vix = np.zeros_like(portfolio_returns)
            vix_ma = np.zeros_like(portfolio_returns)

        # Calculate returns features
        returns_1d = portfolio_returns.shift(1).values.flatten()
        returns_5d = portfolio_returns.shift(5).values.flatten()

        # Calculate momentum
        momentum = (portfolio_returns - portfolio_returns.shift(5)).values.flatten()

        # Combine features
        # Features: [returns_1d, returns_5d, rolling_vol, momentum, vix, vix_ma]
        features = np.column_stack([
            returns_1d,
            returns_5d,
            rolling_vol,
            momentum,
            vix,
            vix_ma
        ])
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

        self.logger.debug("Features prepared: shape=%s", features.shape)
        return features

    def _train_hmm(self, features: np.ndarray) -> tuple[Any, HMMTrainingResult]:
        """
        Train Hidden Markov Model using Baum-Welch algorithm with multiple
        random restarts to avoid local optima.

        Args:
            features: Feature matrix (observations x features)

        Returns:
            Trained HMM model and training results
        """
        self.logger.info("Training HMM model with Baum-Welch algorithm (multi-restart)...")

        try:
            best_model = None
            best_ll = -np.inf
            N_RESTARTS = 5  # Multiple restarts for global optimum

            for seed in range(N_RESTARTS):
                try:
                    candidate = hmm.GaussianHMM(
                        n_components=self.n_states,
                        covariance_type="full",
                        n_iter=HMM_N_ITERATIONS,
                        tol=HMM_CONVERGENCE_THRESHOLD,
                        random_state=seed,
                        verbose=False,
                        init_params="stmc",
                    )
                    candidate.fit(features)
                    ll = candidate.score(features)
                    if ll > best_ll:
                        best_ll = ll
                        best_model = candidate
                except Exception:
                    continue

            if best_model is None:
                raise RuntimeError("All HMM restarts failed")

            model = best_model

            # Train model
            start_time = datetime.now(UTC)
            training_time = (datetime.now(UTC) - start_time).total_seconds()

            # Calculate model metrics
            log_likelihood = model.score(features)
            bic = model.bic(features)
            aic = model.aic(features)
            n_params = self.n_states * (self.n_states - 1) + self.n_states  # For Gaussian HMM

            # Check convergence
            converged = model.monitor_.converged

            # Get transition matrix
            transmat = model.transmat_

            # Get stationary distribution
            stationary_dist = self._build_stationary_distribution(model)

            training_result = HMMTrainingResult(
                model=model,
                converged=converged,
                log_likelihood=log_likelihood,
                bic=bic,
                aic=aic,
                n_states=self.n_states,
                n_params=n_params,
                training_time=training_time,
                transition_matrix=transmat,
                stationary_distribution=stationary_dist
            )

            self.logger.info(
                f"HMM trained: log_likelihood={log_likelihood:.2f}, "
                f"BIC={bic:.2f}, AIC={aic:.2f}, converged={converged}, "
                f"best_restart_seed={list(range(N_RESTARTS))[list(range(N_RESTARTS)).index(model.random_state) if hasattr(model, 'random_state') else 0]}"  # noqa: E501
            )

            return model, training_result

        except Exception as e:
            self.error_handler.handle_error(e, "HMMRegimeDetector._train_hmm")
            return None, HMMTrainingResult(
                model=None, converged=False, log_likelihood=0.0, bic=0.0, aic=0.0,
                n_states=self.n_states, n_params=0, training_time=0.0,
                transition_matrix=None, stationary_distribution=None
            )

    def _build_stationary_distribution(self, model: Any) -> tuple[np.ndarray, Any] | None:
        """Build a compatibility stationary-distribution tuple from the fitted model."""
        transmat = getattr(model, "transmat_", None)
        if transmat is None:
            return None

        eigenvalues, eigenvectors = np.linalg.eig(transmat.T)
        idx = int(np.argmin(np.abs(eigenvalues - 1.0)))
        weights = np.real(eigenvectors[:, idx])
        weights = np.clip(weights, a_min=0.0, a_max=None)

        if not np.any(weights):
            weights = np.full(transmat.shape[0], 1.0 / transmat.shape[0])
        else:
            weights = weights / weights.sum()

        return weights, getattr(model, "means_", None)

    def _train_fallback_classifier(self, features: np.ndarray) -> tuple[Any, HMMTrainingResult]:
        """
        Fallback classifier when HMM not available.

        Uses simple threshold-based regime classification.
        """
        self.logger.warning("Using fallback classifier (threshold-based)")

        # Simple regime classification based on volatility
        rolling_vol = features[:, 2]  # Rolling volatility is at index 2
        vix = features[:, 4]  # VIX is at index 4

        # Classify regimes
        regimes = []
        for i in range(len(rolling_vol)):
            vol = rolling_vol[i]
            v = vix[i]

            if vol < 0.015:  # Low volatility
                if v < 15:
                    regimes.append(MarketRegime.BULL)
                else:
                    regimes.append(MarketRegime.CHOP)
            elif vol < 0.030:  # Medium volatility
                if v < 25:
                    regimes.append(MarketRegime.CHOP)
                else:
                    regimes.append(MarketRegime.CRISIS)
            elif vol >= 0.030:  # High volatility
                if v > 30:
                    regimes.append(MarketRegime.CRISIS)
                else:
                    regimes.append(MarketRegime.CHOP)

        # Calculate simple metrics
        log_likelihood = -1000.0  # Arbitrary low value
        bic = 10000.0  # Arbitrary high value
        aic = 5000.0  # Arbitrary high value

        training_result = HMMTrainingResult(
                model=None,
                converged=True,
                log_likelihood=log_likelihood,
                bic=bic,
                aic=aic,
                n_states=self.n_states,
                n_params=0,
                training_time=0.0,
                transition_matrix=None,
                stationary_distribution=None
        )

        self.logger.warning("Fallback classifier used: %s regimes classified", len(regimes))
        return None, training_result

    def _calculate_model_metrics(self,
                           training_result: HMMTrainingResult,
                           features: np.ndarray) -> HMMModelMetrics:
        """
        Calculate HMM model performance metrics.
        """
        if training_result.transition_matrix is not None:
            # Calculate state persistence (diagonal dominance)
            transmat = training_result.transition_matrix
            persistence = np.trace(transmat) / self.n_states

            # Calculate entropy of stationary distribution
            if training_result.stationary_distribution is not None:
                # For GaussianHMM, stationary_dist is a tuple
                if len(training_result.stationary_distribution) == 2:
                    weights = training_result.stationary_distribution[0]
                    entropy = -np.sum(weights * np.log(weights + 1e-10))
                else:
                    entropy = 0.0
            else:
                entropy = 0.0
        else:
            persistence = 0.0
            entropy = 0.0

        # Calculate prediction accuracy (simplified)
        # In production, this would use walk-forward validation
        prediction_accuracy = None

        return HMMModelMetrics(
            timestamp=datetime.now(UTC),
            model_type=f"{self.n_states}-state HMM",
            n_states=self.n_states,
            n_params=training_result.n_params,
            log_likelihood=training_result.log_likelihood,
            bic=training_result.bic,
            aic=training_result.aic,
            transition_matrix=training_result.transition_matrix,
            stationary_distribution=training_result.stationary_distribution,
            prediction_accuracy=prediction_accuracy,
            persistence=persistence,
            entropy=entropy
        )

    def predict(self,
               current_returns: pd.DataFrame,
               volatility_data: pd.DataFrame | None = None,
               vix_data: pd.DataFrame | None = None,
               n_lookback: int = 20) -> RegimePrediction:
        """
        Predict current market regime.

        Args:
            current_returns: DataFrame of current returns (time x assets)
            volatility_data: Optional DataFrame of volatility metrics
            vix_data: Optional DataFrame of VIX levels
            n_lookback: Number of periods to look back (default 20)

        Returns:
            Regime prediction with probabilities and recommendations
        """
        if not self.is_trained:
            self.logger.warning("Model not trained - returning unknown prediction")
            return RegimePrediction(
                timestamp=datetime.now(UTC),
                current_regime=MarketRegime.UNKNOWN,
                regime_probabilities={},
                confidence=0.0,
                transition_probability=0.0,
                expected_duration=None,
                reason="Model not trained"
            )

        try:
            self.logger.debug("Predicting market regime...")

            # Prepare current features
            features = self._prepare_features(
                current_returns,
                volatility_data,
                vix_data
            )

            # Get most recent observation
            if features.shape[0] >= n_lookback:
                recent_features = features[-n_lookback:]
            else:
                recent_features = features

            # Predict regime
            if self.model is None:
                # Use fallback classifier
                regime_idx = self._classify_regime_fallback(recent_features)
                probabilities = self._get_fallback_probabilities()
            else:
                # Use HMM model
                regime_idx = int(self.model.predict(recent_features)[-1])
                probabilities = self._get_hmm_probabilities(regime_idx)

            # Map to regime enum
            regime = self._regime_from_index(regime_idx)

            # Calculate confidence
            max_prob = max(probabilities.values())
            confidence = max_prob

            # Update regime tracking
            if regime != self.current_regime:
                self.days_in_current_regime = 1
                self.current_regime = regime
            else:
                self.days_in_current_regime += 1

            # Generate regime-gated strategy signal
            strategy_signal = self._generate_strategy_signal(
                regime,
                probabilities,
                confidence
            )

            # Calculate transition probability
            transition_prob = self._calculate_transition_probability()

            # Expected duration in current regime
            expected_duration = self._calculate_expected_duration(regime)

            prediction = RegimePrediction(
                timestamp=datetime.now(UTC),
                current_regime=regime,
                regime_probabilities=probabilities,
                confidence=confidence,
                transition_probability=transition_prob,
                expected_duration=expected_duration,
                reason=strategy_signal.reason
            )

            # Store prediction history
            self.prediction_history.append(prediction)

            self.logger.info(
                f"Regime prediction: {regime.value}, "
                f"confidence={confidence:.2%}, "
                f"probabilities={probabilities}"
            )

            return prediction

        except Exception as e:
            self.error_handler.handle_error(e, "HMMRegimeDetector.predict")
            return RegimePrediction(
                timestamp=datetime.now(UTC),
                current_regime=MarketRegime.UNKNOWN,
                regime_probabilities={},
                confidence=0.0,
                transition_probability=0.0,
                expected_duration=None,
                reason=f"Prediction error: {str(e)}"
            )

    def _regime_from_index(self, regime_idx: int) -> MarketRegime:
        """Map a model state index to the legacy regime enum."""
        regimes = [MarketRegime.BULL, MarketRegime.CHOP, MarketRegime.CRISIS]
        if 0 <= regime_idx < len(regimes):
            return regimes[regime_idx]
        return MarketRegime.UNKNOWN

    def _classify_regime_fallback(self, features: np.ndarray) -> int:
        """Fallback regime classification based on thresholds."""
        # Use last observation
        last_vol = features[-1, 2]  # Rolling volatility
        last_vix = features[-1, 4]  # VIX

        if last_vol < 0.015:  # Low volatility
            if last_vix < 15:
                return 0  # BULL
            else:
                return 1  # CHOP
        elif last_vol < 0.030:  # Medium volatility
            if last_vix < 25:
                return 1  # CHOP
            else:
                return 2  # CRISIS
        else:  # High volatility
            if last_vix > 30:
                return 2  # CRISIS
            else:
                return 1  # CHOP

    def _get_fallback_probabilities(self) -> dict[MarketRegime, float]:
        """Get probabilities for fallback classifier."""
        return {
            MarketRegime.BULL: 0.33,
            MarketRegime.CHOP: 0.50,
            MarketRegime.CRISIS: 0.17,
            MarketRegime.UNKNOWN: 0.0
        }

    def _get_hmm_probabilities(self, regime_idx: int) -> dict[MarketRegime, float]:
        """Get regime probabilities from HMM transition matrix."""
        if self.training_result is None or self.training_result.transition_matrix is None:
            return {MarketRegime.UNKNOWN: 1.0}

        # Get stationary distribution (if available)
        stationary_dist = self.training_result.stationary_distribution

        if stationary_dist is not None and len(stationary_dist) == 2:
            # For GaussianHMM, stationary_dist is (weights, means)
            weights = stationary_dist[0]
            means = stationary_dist[1]

            # Create probability distribution
            probs = {}
            for i, regime in enumerate([MarketRegime.BULL, MarketRegime.CHOP, MarketRegime.CRISIS]):
                if i < len(means):
                    prob = weights[i]  # Weight for this state
                else:
                    prob = 0.0
                probs[regime] = prob
        else:
            # Uniform distribution
            probs = {
                MarketRegime.BULL: 0.33,
                MarketRegime.CHOP: 0.33,
                MarketRegime.CRISIS: 0.33,
                MarketRegime.UNKNOWN: 0.01
            }

        return probs

    def _generate_strategy_signal(self,
                           regime: MarketRegime,
                           probabilities: dict[MarketRegime, float],
                           confidence: float) -> RegimeGatedStrategySignal:
        """
        Generate regime-gated strategy signal.

        Based on Renaissance research, this enables "strategy mismatch" avoidance
        by only recommending strategies optimal for the detected regime.
        """
        # Get regime characteristics
        regime_info = REGIME_CHARACTERISTICS.get(regime, {})

        if not regime_info:
            return RegimeGatedStrategySignal(
                timestamp=datetime.now(UTC),
                current_regime=regime,
                recommended_strategy="neutral",
                confidence=confidence,
                regime_threshold=0.70,
                avoid_regimes=[],
                reason="Unknown regime - neutral strategy"
            )

        # Check if confidence meets threshold
        if confidence < self.regime_switch_threshold:
            # Not confident enough - recommend neutral
            return RegimeGatedStrategySignal(
                timestamp=datetime.now(UTC),
                current_regime=regime,
                recommended_strategy="neutral",
                confidence=confidence,
                regime_threshold=self.regime_switch_threshold,
                avoid_regimes=[],
                reason=f"Low confidence ({confidence:.2%}) - maintain neutral strategy"
            )

        # Get optimal strategy
        optimal_strategy = regime_info.get("optimal_strategy", "neutral")

        # Determine regimes to avoid
        if regime == MarketRegime.BULL:
            avoid_regimes = [MarketRegime.CHOP, MarketRegime.CRISIS]
            reason = f"Bull regime detected - use {optimal_strategy}"
        elif regime == MarketRegime.CHOP:
            avoid_regimes = [MarketRegime.BULL, MarketRegime.CRISIS]
            reason = f"Chop regime detected - use {optimal_strategy}"
        elif regime == MarketRegime.CRISIS:
            avoid_regimes = [MarketRegime.BULL, MarketRegime.CHOP]
            reason = f"Crisis regime detected - use {optimal_strategy}"
        else:
            avoid_regimes = []
            reason = f"Regime {regime.value} detected - use {optimal_strategy}"

        return RegimeGatedStrategySignal(
                timestamp=datetime.now(UTC),
                current_regime=regime,
                recommended_strategy=optimal_strategy,
                confidence=confidence,
                regime_threshold=self.regime_switch_threshold,
                avoid_regimes=avoid_regimes,
                reason=reason
        )

    def _calculate_transition_probability(self) -> float:
        """
        Calculate probability of regime transition.

        Based on regime history, estimate likelihood of transition.
        """
        if len(self.regime_history) < 2:
            return 0.0

        # Count recent transitions
        recent_transitions = 0
        for i in range(min(10, len(self.regime_history) - 1)):
            if self.regime_history[i].current_regime != self.regime_history[i + 1].current_regime:
                recent_transitions += 1

        # Estimate transition probability (simplified)
        if recent_transitions > 0:
            transition_prob = min(0.3, recent_transitions / 10.0)
        else:
            transition_prob = 0.0

        return transition_prob

    def _calculate_expected_duration(self, regime: MarketRegime) -> float | None:
        """
        Calculate expected duration of current regime.

        Based on regime persistence from transition matrix.
        """
        if self.training_result is None or self.training_result.transition_matrix is None:
            return None

        transmat = self.training_result.transition_matrix

        # Get persistence (diagonal dominance)
        persistence = np.trace(transmat) / self.n_states

        # Expected duration = 1 / (1 - persistence)
        if persistence > 0.95:
            return 10.0  # Highly persistent (10 days average)
        elif persistence > 0.80:
            return 5.0  # Persistent (5 days average)
        elif persistence > 0.60:
            return 3.0  # Moderately persistent (3 days average)
        else:
            return 1.0  # Not persistent (1 day average)

    def get_regime_history(self, periods: int = 30) -> pd.DataFrame:
        """
        Get historical regime predictions.

        Args:
            periods: Number of periods to retrieve

        Returns:
            DataFrame with regime history
        """
        if not self.prediction_history:
            return pd.DataFrame()

        history = self.prediction_history[-periods:]

        return pd.DataFrame([
            {
                'timestamp': pred.timestamp,
                'regime': pred.current_regime.value,
                'confidence': pred.confidence,
                'bull_probability': pred.regime_probabilities.get(MarketRegime.BULL, 0.0),
                'chop_probability': pred.regime_probabilities.get(MarketRegime.CHOP, 0.0),
                'crisis_probability': pred.regime_probabilities.get(MarketRegime.CRISIS, 0.0)
            }
            for pred in history
        ])

    def get_model_metrics(self) -> HMMModelMetrics | None:
        """
        Get current model metrics.

        Returns:
            Model metrics if available, None otherwise
        """
        return self.model_metrics

    def get_regime_statistics(self) -> dict[str, Any]:
        """
        Get statistics on regime predictions.

        Returns:
            Dictionary with regime statistics
        """
        if not self.prediction_history:
            return {}

        regimes = [pred.current_regime.value for pred in self.prediction_history]
        regime_counts = {regime: regimes.count(regime) for regime in regimes}

        # Calculate persistence
        if len(self.regime_history) >= 2:
            transitions = 0
            for i in range(min(10, len(self.regime_history) - 1)):
                if self.regime_history[i].current_regime != self.regime_history[i + 1].current_regime:  # noqa: E501
                    transitions += 1

            persistence = transitions / len(self.prediction_history)
        else:
            persistence = 0.0

        return {
            'total_predictions': len(self.prediction_history),
            'regime_distribution': regime_counts,
            'current_regime': self.current_regime.value,
            'days_in_current_regime': self.days_in_current_regime,
            'persistence': persistence,
            'model_trained': self.is_trained
        }


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_sample_data(n_periods: int = 252,
                     n_assets: int = 1) -> pd.DataFrame:
    """
    Create sample market data for HMM training.

    NOTE: Test/training data generator — do not call from production code.
    Uses a fixed random seed (42) for reproducibility.

    Args:
        n_periods: Number of periods to generate
        n_assets: Number of assets (default 1)

    Returns:
        DataFrame with sample returns and volatility
    """
    np.random.seed(42)

    # Generate returns with regime-dependent characteristics
    dates = pd.date_range(end=datetime.now(UTC), periods=n_periods, freq='D')

    # Simulate regime changes
    regimes = []
    current_regime = MarketRegime.BULL
    regime_length = 0

    for _i in range(n_periods):
        # Random regime transition (stickiness)
        if np.random.random() < 0.05:  # 5% chance of regime change
            # Switch regime
            possible_regimes = [MarketRegime.BULL, MarketRegime.CHOP, MarketRegime.CRISIS]
            new_regime = np.random.choice(possible_regimes)
            regimes.append(new_regime)
            regime_length = 1
            current_regime = new_regime
        else:
            # Stay in current regime
            regimes.append(current_regime)
            regime_length += 1

    # Generate returns based on regime
    returns = []
    vols = []

    for _i, regime in enumerate(regimes):
        if regime == MarketRegime.BULL:
            # Low volatility, positive drift
            daily_return = np.random.normal(0.0008, 0.008)
            daily_vol = 0.008
        elif regime == MarketRegime.CHOP:
            # High volatility, mean-reverting
            daily_return = np.random.normal(0.0002, 0.015)
            daily_vol = 0.015
        elif regime == MarketRegime.CRISIS:
            # Extreme volatility, negative drift
            daily_return = np.random.normal(-0.0015, 0.025)
            daily_vol = 0.025
        else:
            daily_return = np.random.normal(0.0005, 0.012)
            daily_vol = 0.012

        returns.append(daily_return)
        vols.append(daily_vol)

    # Create DataFrame
    returns_df = pd.DataFrame(returns, index=dates, columns=['TRAD'])
    vols_df = pd.DataFrame(vols, index=dates, columns=['Volatility'])

    return returns_df, vols_df


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":

    # Create detector
    detector = HMMRegimeDetector(n_states=3, use_hmm=True)

    # Create sample data
    returns_df, vols_df = create_sample_data(n_periods=252)

    # Initialize detector
    if not detector.initialize(returns_df, vols_df):
        sys.exit(1)

    # Train model
    if detector.training_result is not None and detector.training_result.converged:
        pass
    else:
        pass

    # Get model metrics
    if detector.model_metrics is not None:
        pass

    # Make predictions
    predictions = []
    for i in range(10):
        # Use last 20 days for prediction
        if i < 20:
            pred = detector.predict(returns_df.iloc[:i+1], vols_df.iloc[:i+1])
        else:
            pred = detector.predict(returns_df.iloc[i-19:i+1], vols_df.iloc[i-19:i+1])
        predictions.append(pred)

        # Display predictions
    for _, _ in enumerate(predictions[-5:]):
        pass

    # Get regime statistics
    stats = detector.get_regime_statistics()
    for _key, _value in stats.items():
        pass

