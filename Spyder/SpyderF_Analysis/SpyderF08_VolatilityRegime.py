#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderF_Analysis
Module: SpyderF08_VolatilityRegime.py
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
from typing import Any
from enum import Enum
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import threading
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
import joblib
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from scipy import stats

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager
from Spyder.SpyderM_Monitoring.SpyderM01_SystemMonitor import SystemMonitor
from Spyder.SpyderF_Analysis.SpyderF04_VolatilityAnalysis import VolatilityAnalyzer

class VolatilityRegime(Enum):
    """Volatility regime classification."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    TRANSITIONING = "transitioning"

class RegimeStrength(Enum):
    """Strength/confidence of regime classification."""
    WEAK = 1
    MODERATE = 2
    STRONG = 3
    VERY_STRONG = 4

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class RegimeState:
    """Current volatility regime state."""
    regime: VolatilityRegime
    strength: RegimeStrength
    probability: float  # Confidence in classification
    volatility_level: float
    percentile: float  # Historical percentile
    trend: str  # 'increasing', 'decreasing', 'stable'
    duration_hours: float
    start_time: datetime
    features: dict[str, float] = field(default_factory=dict)

    @property
    def is_stable(self) -> bool:
        """Check if regime is stable."""
        return (self.strength.value >= 3 and
                self.duration_hours > 24 and
                self.trend == 'stable')

    @property
    def is_transitioning(self) -> bool:
        """Check if regime is transitioning."""
        return (self.regime == VolatilityRegime.TRANSITIONING or
                self.strength == RegimeStrength.WEAK or
                self.probability < 0.6)

@dataclass
class RegimeTransition:
    """Regime transition event."""
    from_regime: VolatilityRegime
    to_regime: VolatilityRegime
    transition_time: datetime
    confidence: float
    trigger: str  # What caused transition

@dataclass
class RegimeAnalysis:
    """Complete regime analysis results."""
    current_state: RegimeState
    regime_history: list[RegimeState]
    recent_transitions: list[RegimeTransition]
    regime_distribution: dict[VolatilityRegime, float]  # Time spent in each
    prediction: dict[str, Any] | None = None
    model_info: dict[str, Any] | None = None

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class VolatilityRegimeAnalyzer:
    """
    Volatility regime analyzer with automated ML retraining.

    Features:
    - Multiple regime detection methods
    - Gaussian Mixture Model for classification
    - Automated model retraining
    - Regime transition detection
    - Forward-looking regime prediction
    """

    def __init__(self,
                 config_manager: ConfigManager,
                 ml_model_manager: Any | None = None):
        """Initialize with ML model management."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config_manager = config_manager
        self.ml_model_manager = ml_model_manager
        self.monitor = SystemMonitor()

        # Load configuration
        self._load_config()

        # Initialize components
        self.volatility_analyzer = VolatilityAnalyzer(config_manager)
        self.scaler = StandardScaler()

        # Model components
        self.regime_model = None
        self.last_retrain_date = None
        self.model_version = 0
        self.training_data_buffer = []

        # Regime tracking
        self.current_regime = None
        self.regime_history = []
        self.transitions = []

        # Thread safety
        self._model_lock = threading.Lock()

        # Initialize or load model
        self._initialize_model()

        self.logger.info("VolatilityRegimeAnalyzer initialized with auto-retraining")

    def _load_config(self):
        """Load configuration."""
        config = self.config_manager.get_config('volatility_regime', {})

        # Model settings
        self.n_regimes = config.get('n_regimes', 4)
        self.retrain_interval_days = config.get('retrain_interval_days', 30)
        self.min_samples_for_retrain = config.get('min_samples_for_retrain', 1000)
        self.model_save_path = config.get('model_save_path', 'models/volatility_regime.pkl')

        # Feature settings
        self.lookback_periods = config.get('lookback_periods', [5, 10, 20, 60])
        self.use_advanced_features = config.get('use_advanced_features', True)

        # Regime thresholds (percentiles)
        self.regime_thresholds = config.get('regime_thresholds', {
            'low': 25,
            'normal': 75,
            'high': 90,
            'extreme': 98
        })

        # Retraining settings
        self.auto_retrain_enabled = config.get('auto_retrain_enabled', True)
        self.retrain_on_regime_shift = config.get('retrain_on_regime_shift', True)
        self.performance_threshold = config.get('performance_threshold', 0.7)

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================

    def analyze_regime(self, data: pd.DataFrame) -> RegimeAnalysis:
        """
        Analyze current volatility regime with auto-retraining.

        Args:
            data: OHLCV DataFrame

        Returns:
            Complete regime analysis
        """
        start_time = datetime.now()

        try:
            # Check if retraining needed
            if self._should_retrain():
                self._retrain_model(data)

            # Extract features
            features = self._extract_features(data)

            if features.empty:
                return self._create_default_analysis()

            # Detect current regime
            current_state = self._detect_regime(features.iloc[-1])

            # Update history
            self._update_regime_history(current_state)

            # Detect transitions
            transitions = self._detect_transitions()

            # Calculate regime distribution
            distribution = self._calculate_regime_distribution()

            # Make prediction if model available
            prediction = None
            if self.regime_model and len(features) > 1:
                prediction = self._predict_future_regime(features)

            # Create analysis
            analysis = RegimeAnalysis(
                current_state=current_state,
                regime_history=self.regime_history[-100:],  # Last 100 states
                recent_transitions=transitions[-10:],  # Last 10 transitions
                regime_distribution=distribution,
                prediction=prediction,
                model_info={
                    'version': self.model_version,
                    'last_retrain': self.last_retrain_date.isoformat() if self.last_retrain_date else None,  # noqa: E501
                    'performance_score': self._calculate_model_performance()
                }
            )

            # Record metrics
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            self.monitor.record_metric('regime_analysis.execution_ms', elapsed_ms)
            self.monitor.record_metric('regime_analysis.current_regime', self.current_regime.value if self.current_regime else 0)  # noqa: E501

            return analysis

        except Exception as e:
            self.error_handler.handle_error(e, "Regime analysis failed")
            return self._create_default_analysis()

    def force_retrain(self, training_data: pd.DataFrame) -> bool:
        """
        Force model retraining.

        Args:
            training_data: Historical data for training

        Returns:
            Success status
        """
        try:
            self._retrain_model(training_data)
            return True
        except Exception as e:
            self.logger.error("Force retrain failed: %s", e)
            return False

    def get_regime_recommendations(self, current_regime: VolatilityRegime) -> dict[str, Any]:
        """
        Get trading recommendations based on regime.

        Args:
            current_regime: Current volatility regime

        Returns:
            Recommendations dictionary
        """
        recommendations = {
            'suitable_strategies': [],
            'position_sizing': 1.0,
            'risk_adjustments': {},
            'warnings': []
        }

        if current_regime == VolatilityRegime.LOW:
            recommendations['suitable_strategies'] = [
                'iron_condor', 'butterfly', 'calendar_spread'
            ]
            recommendations['position_sizing'] = 1.2  # Can be slightly more aggressive
            recommendations['risk_adjustments'] = {
                'wider_strikes': True,
                'longer_duration': True
            }

        elif current_regime == VolatilityRegime.NORMAL:
            recommendations['suitable_strategies'] = [
                'iron_condor', 'credit_spread', 'covered_call'
            ]
            recommendations['position_sizing'] = 1.0

        elif current_regime == VolatilityRegime.HIGH:
            recommendations['suitable_strategies'] = [
                'straddle', 'strangle', 'debit_spread'
            ]
            recommendations['position_sizing'] = 0.7  # Reduce size
            recommendations['risk_adjustments'] = {
                'tighter_stops': True,
                'shorter_duration': True
            }
            recommendations['warnings'].append("High volatility - reduce position sizes")

        elif current_regime == VolatilityRegime.EXTREME:
            recommendations['suitable_strategies'] = []  # No new positions
            recommendations['position_sizing'] = 0.0
            recommendations['warnings'].append("EXTREME volatility - consider closing positions")

        elif current_regime == VolatilityRegime.TRANSITIONING:
            recommendations['suitable_strategies'] = ['calendar_spread', 'diagonal']
            recommendations['position_sizing'] = 0.5
            recommendations['warnings'].append("Regime transitioning - use caution")

        return recommendations

    # ==========================================================================
    # MODEL MANAGEMENT
    # ==========================================================================

    def _should_retrain(self) -> bool:
        """Check if model retraining is needed."""
        if not self.auto_retrain_enabled or not self.ml_model_manager:
            return False

        # No model exists
        if self.regime_model is None:
            return True

        # No previous training
        if self.last_retrain_date is None:
            return True

        # Check interval
        days_since_retrain = (datetime.now() - self.last_retrain_date).days
        if days_since_retrain >= self.retrain_interval_days:
            return True

        # Check performance degradation
        if self._calculate_model_performance() < self.performance_threshold:
            return True

        # Check for regime shifts
        return bool(self.retrain_on_regime_shift and self._detect_regime_shift())

    def _retrain_model(self, market_data: pd.DataFrame):
        """Retrain the regime detection model."""
        if len(market_data) < self.min_samples_for_retrain:
            self.logger.warning("Insufficient data for retraining")
            return

        try:
            with self._model_lock:
                self.logger.info("Starting model retraining...")

                # Extract features from historical data
                features = self._extract_features(market_data)

                if features.empty:
                    self.logger.error("No features extracted for training")
                    return

                # Prepare training data
                X = features.values
                X_scaled = self.scaler.fit_transform(X)

                # Train Gaussian Mixture Model
                self.regime_model = GaussianMixture(
                    n_components=self.n_regimes,
                    covariance_type='full',
                    max_iter=100,
                    random_state=42
                )

                self.regime_model.fit(X_scaled)

                # Update model metadata
                self.last_retrain_date = datetime.now()
                self.model_version += 1

                # Save model
                self._save_model()

                # If using ML model manager
                if self.ml_model_manager:
                    self.ml_model_manager.register_model(
                        model=self.regime_model,
                        name='volatility_regime_detector',
                        version=str(self.model_version),
                        config={'n_regimes': self.n_regimes},
                        performance_metrics={'log_likelihood': self.regime_model.score(X_scaled)}
                    )

                self.logger.info("Model retrained successfully (version %s)", self.model_version)

        except Exception as e:
            self.logger.error("Model retraining failed: %s", e)

    def _initialize_model(self):
        """Initialize or load existing model."""
        try:
            # Try to load existing model
            if self.ml_model_manager:
                model_data = self.ml_model_manager.get_model('volatility_regime_detector')
                if model_data:
                    self.regime_model = model_data['model']
                    self.model_version = int(model_data.get('version', 0))
                    self.last_retrain_date = model_data.get('trained_at')
                    self.logger.info("Loaded model version %s", self.model_version)
                    return

            # Try to load from file
            import os
            if os.path.exists(self.model_save_path):
                model_data = joblib.load(self.model_save_path)
                self.regime_model = model_data['model']
                self.scaler = model_data['scaler']
                self.model_version = model_data.get('version', 0)
                self.last_retrain_date = model_data.get('last_retrain_date')
                self.logger.info("Loaded model from file (version %s)", self.model_version)

        except Exception as e:
            self.logger.warning("Could not load existing model: %s", e)

    def _save_model(self):
        """Save model to file."""
        try:
            import os
            os.makedirs(os.path.dirname(self.model_save_path), exist_ok=True)

            model_data = {
                'model': self.regime_model,
                'scaler': self.scaler,
                'version': self.model_version,
                'last_retrain_date': self.last_retrain_date,
                'config': {
                    'n_regimes': self.n_regimes,
                    'lookback_periods': self.lookback_periods
                }
            }

            joblib.dump(model_data, self.model_save_path)

        except Exception as e:
            self.logger.error("Failed to save model: %s", e)

    # ==========================================================================
    # FEATURE EXTRACTION
    # ==========================================================================

    def _extract_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Extract features for regime detection."""
        features = pd.DataFrame(index=data.index)

        # Basic volatility measures
        returns = data['close'].pct_change()

        # Rolling volatilities
        for period in self.lookback_periods:
            features[f'volatility_{period}'] = returns.rolling(period).std() * np.sqrt(252)
            features[f'realized_vol_{period}'] = self._calculate_realized_volatility(data, period)

        # Volatility of volatility
        features['vol_of_vol'] = features['volatility_20'].rolling(20).std()

        # High-low range
        features['hl_range'] = (data['high'] - data['low']) / data['close']
        features['hl_range_ma'] = features['hl_range'].rolling(20).mean()

        if self.use_advanced_features:
            # Parkinson volatility
            features['parkinson_vol'] = self._calculate_parkinson_volatility(data)

            # Garman-Klass volatility
            features['gk_vol'] = self._calculate_garman_klass_volatility(data)

            # Volume-weighted volatility
            if 'volume' in data.columns:
                features['volume_weighted_vol'] = self._calculate_volume_weighted_volatility(data)

            # Volatility ratios
            features['short_long_vol_ratio'] = features['volatility_5'] / features['volatility_20']

            # Volatility trend
            features['vol_trend'] = features['volatility_20'].rolling(5).apply(
                lambda x: 1 if x[-1] > x[0] else -1
            )

        return features.dropna()

    def _calculate_realized_volatility(self, data: pd.DataFrame, period: int) -> pd.Series:
        """Calculate realized volatility."""
        returns = np.log(data['close'] / data['close'].shift(1))
        return returns.rolling(period).std() * np.sqrt(252)

    def _calculate_parkinson_volatility(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Parkinson volatility estimator."""
        hl_ratio = np.log(data['high'] / data['low'])
        return hl_ratio.rolling(period).apply(
            lambda x: np.sqrt(np.sum(x**2) / (4 * len(x) * np.log(2)))
        ) * np.sqrt(252)

    def _calculate_garman_klass_volatility(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate Garman-Klass volatility estimator."""
        log_hl = np.log(data['high'] / data['low'])
        log_co = np.log(data['close'] / data['open'])

        rs = 0.5 * log_hl**2 - (2*np.log(2)-1) * log_co**2

        return rs.rolling(period).apply(
            lambda x: np.sqrt(np.sum(x) / len(x))
        ) * np.sqrt(252)

    def _calculate_volume_weighted_volatility(self, data: pd.DataFrame, period: int = 20) -> pd.Series:  # noqa: E501
        """Calculate volume-weighted volatility."""
        returns = data['close'].pct_change()
        volume_weights = data['volume'] / data['volume'].rolling(period).sum()

        weighted_returns = returns * volume_weights
        return weighted_returns.rolling(period).std() * np.sqrt(252)

    # ==========================================================================
    # REGIME DETECTION
    # ==========================================================================

    def _detect_regime(self, features: pd.Series) -> RegimeState:
        """Detect current regime from features."""
        # Get current volatility
        current_vol = features.get('volatility_20', 0)

        # Statistical classification (fallback)
        if self.regime_model is None:
            return self._statistical_regime_detection(features)

        # ML-based classification
        try:
            # Prepare features
            X = features.values.reshape(1, -1)
            X_scaled = self.scaler.transform(X)

            # Predict regime
            probabilities = self.regime_model.predict_proba(X_scaled)[0]
            regime_idx = np.argmax(probabilities)
            confidence = probabilities[regime_idx]

            # Map to regime enum
            regime = self._map_cluster_to_regime(regime_idx, current_vol)

            # Determine strength
            if confidence > 0.8:
                strength = RegimeStrength.VERY_STRONG
            elif confidence > 0.6:
                strength = RegimeStrength.STRONG
            elif confidence > 0.4:
                strength = RegimeStrength.MODERATE
            else:
                strength = RegimeStrength.WEAK

            # Calculate percentile
            percentile = self._calculate_volatility_percentile(current_vol)

            # Determine trend
            trend = self._determine_volatility_trend(features)

            # Calculate duration
            duration_hours = self._calculate_regime_duration()

            return RegimeState(
                regime=regime,
                strength=strength,
                probability=confidence,
                volatility_level=current_vol,
                percentile=percentile,
                trend=trend,
                duration_hours=duration_hours,
                start_time=datetime.now() - timedelta(hours=duration_hours),
                features=dict(features)
            )

        except Exception as e:
            self.logger.error("ML regime detection failed: %s", e)
            return self._statistical_regime_detection(features)

    def _statistical_regime_detection(self, features: pd.Series) -> RegimeState:
        """Fallback statistical regime detection."""
        current_vol = features.get('volatility_20', 0)
        percentile = self._calculate_volatility_percentile(current_vol)

        # Classify based on percentile
        if percentile < self.regime_thresholds['low']:
            regime = VolatilityRegime.LOW
        elif percentile < self.regime_thresholds['normal']:
            regime = VolatilityRegime.NORMAL
        elif percentile < self.regime_thresholds['high']:
            regime = VolatilityRegime.HIGH
        elif percentile < self.regime_thresholds['extreme']:
            regime = VolatilityRegime.EXTREME
        else:
            regime = VolatilityRegime.EXTREME

        # Simple strength based on how far from thresholds
        strength = RegimeStrength.MODERATE

        return RegimeState(
            regime=regime,
            strength=strength,
            probability=0.7,  # Default confidence
            volatility_level=current_vol,
            percentile=percentile,
            trend=self._determine_volatility_trend(features),
            duration_hours=24,  # Default
            start_time=datetime.now() - timedelta(hours=24),
            features=dict(features)
        )

    def _map_cluster_to_regime(self, cluster_idx: int, current_vol: float) -> VolatilityRegime:
        """Map GMM cluster to volatility regime."""
        # This is a simplified mapping - in production, would use
        # cluster characteristics to determine mapping
        if self.n_regimes == 4:
            regime_map = {
                0: VolatilityRegime.LOW,
                1: VolatilityRegime.NORMAL,
                2: VolatilityRegime.HIGH,
                3: VolatilityRegime.EXTREME
            }
            return regime_map.get(cluster_idx, VolatilityRegime.NORMAL)
        else:
            # Dynamic mapping based on volatility level
            percentile = self._calculate_volatility_percentile(current_vol)

            if percentile < 25:
                return VolatilityRegime.LOW
            elif percentile < 75:
                return VolatilityRegime.NORMAL
            elif percentile < 90:
                return VolatilityRegime.HIGH
            else:
                return VolatilityRegime.EXTREME

    # ==========================================================================
    # REGIME TRACKING
    # ==========================================================================

    def _update_regime_history(self, current_state: RegimeState):
        """Update regime history and detect changes."""
        # Add to history
        self.regime_history.append(current_state)

        # Limit history size
        if len(self.regime_history) > 1000:
            self.regime_history = self.regime_history[-1000:]

        # Check for regime change
        if self.current_regime != current_state.regime:
            if self.current_regime is not None:
                # Record transition
                transition = RegimeTransition(
                    from_regime=self.current_regime,
                    to_regime=current_state.regime,
                    transition_time=datetime.now(),
                    confidence=current_state.probability,
                    trigger=self._identify_transition_trigger(current_state)
                )
                self.transitions.append(transition)

                # Log transition
                self.logger.info(
                    f"Regime transition: {self.current_regime.value} -> "
                    f"{current_state.regime.value} (confidence: {current_state.probability:.2f})"
                )

            self.current_regime = current_state.regime

    def _detect_transitions(self) -> list[RegimeTransition]:
        """Get recent regime transitions."""
        # Return last N transitions
        return self.transitions[-10:] if self.transitions else []

    def _calculate_regime_distribution(self) -> dict[VolatilityRegime, float]:
        """Calculate time spent in each regime."""
        if not self.regime_history:
            return {regime: 0.0 for regime in VolatilityRegime}

        regime_counts = defaultdict(int)
        for state in self.regime_history:
            regime_counts[state.regime] += 1

        total = len(self.regime_history)

        return {
            regime: count / total
            for regime, count in regime_counts.items()
        }

    # ==========================================================================
    # PREDICTION
    # ==========================================================================

    def _predict_future_regime(self, features: pd.DataFrame) -> dict[str, Any]:
        """Predict future regime transitions."""
        if not self.regime_model or len(features) < 10:
            return None

        try:
            # Use recent features to predict next regime
            recent_features = features.tail(10)

            # Calculate feature trends
            feature_trends = {}
            for col in recent_features.columns:
                if 'volatility' in col:
                    trend = (recent_features[col].iloc[-1] - recent_features[col].iloc[0]) / recent_features[col].iloc[0]  # noqa: E501
                    feature_trends[col] = trend

            # Simple prediction based on trends
            avg_vol_trend = np.mean([v for k, v in feature_trends.items() if 'volatility' in k])

            prediction = {
                'next_regime_probability': {},
                'expected_transition_hours': 24,
                'confidence': 0.7,
                'trend_direction': 'increasing' if avg_vol_trend > 0 else 'decreasing'
            }

            # Estimate next regime probabilities
            if avg_vol_trend > 0.1:
                # Volatility increasing
                prediction['next_regime_probability'] = {
                    VolatilityRegime.HIGH: 0.6,
                    VolatilityRegime.EXTREME: 0.3,
                    VolatilityRegime.NORMAL: 0.1
                }
            elif avg_vol_trend < -0.1:
                # Volatility decreasing
                prediction['next_regime_probability'] = {
                    VolatilityRegime.LOW: 0.5,
                    VolatilityRegime.NORMAL: 0.4,
                    VolatilityRegime.HIGH: 0.1
                }
            else:
                # Stable
                prediction['next_regime_probability'] = {
                    self.current_regime: 0.7,
                    VolatilityRegime.NORMAL: 0.3
                }

            return prediction

        except Exception as e:
            self.logger.error("Regime prediction failed: %s", e)
            return None

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _calculate_volatility_percentile(self, current_vol: float) -> float:
        """Calculate historical percentile of current volatility."""
        if not self.regime_history:
            return 50.0

        historical_vols = [s.volatility_level for s in self.regime_history]
        return stats.percentileofscore(historical_vols, current_vol)

    def _determine_volatility_trend(self, features: pd.Series) -> str:
        """Determine if volatility is trending up, down, or stable."""
        # Compare short vs long volatility
        short_vol = features.get('volatility_5', 0)
        long_vol = features.get('volatility_20', 0)

        if long_vol == 0:
            return 'stable'

        ratio = short_vol / long_vol

        if ratio > 1.2:
            return 'increasing'
        elif ratio < 0.8:
            return 'decreasing'
        else:
            return 'stable'

    def _calculate_regime_duration(self) -> float:
        """Calculate how long we've been in current regime."""
        if not self.regime_history or not self.current_regime:
            return 0.0

        # Find last regime change
        duration_hours = 0
        for state in reversed(self.regime_history):
            if state.regime == self.current_regime:
                duration_hours += 1  # Assuming hourly data
            else:
                break

        return duration_hours

    def _identify_transition_trigger(self, new_state: RegimeState) -> str:
        """Identify what triggered the regime transition."""
        if not self.regime_history:
            return 'initial'

        prev_state = self.regime_history[-1]

        # Check volatility spike
        vol_change = (new_state.volatility_level - prev_state.volatility_level) / prev_state.volatility_level  # noqa: E501
        if abs(vol_change) > 0.3:
            return f'volatility_{"spike" if vol_change > 0 else "drop"}'

        # Check trend change
        if prev_state.trend != new_state.trend:
            return f'trend_change_{new_state.trend}'

        # Gradual transition
        return 'gradual_shift'

    def _detect_regime_shift(self) -> bool:
        """Detect if a significant regime shift has occurred."""
        if len(self.transitions) < 2:
            return False

        # Check recent transitions
        recent_transitions = self.transitions[-5:]

        # Multiple transitions indicate instability
        if len(recent_transitions) >= 3:
            time_span = (recent_transitions[-1].transition_time -
                        recent_transitions[0].transition_time).total_seconds() / 3600

            # Many transitions in short time = regime shift
            if time_span < 48:  # Within 2 days
                return True

        return False

    def _calculate_model_performance(self) -> float:
        """Calculate model performance score."""
        if not self.regime_model or not self.regime_history:
            return 0.0

        # Simple performance metric based on regime stability
        # and prediction accuracy
        # In production, would track actual vs predicted regimes

        if len(self.regime_history) < 10:
            return 0.5

        # Check regime stability (fewer transitions = better)
        recent_regimes = [s.regime for s in self.regime_history[-20:]]
        unique_regimes = len(set(recent_regimes))
        stability_score = 1.0 - (unique_regimes - 1) / len(recent_regimes)

        # Check confidence levels
        avg_confidence = np.mean([s.probability for s in self.regime_history[-20:]])

        # Combined score
        performance = 0.7 * stability_score + 0.3 * avg_confidence

        return performance

    def _create_default_analysis(self) -> RegimeAnalysis:
        """Create default analysis when detection fails."""
        default_state = RegimeState(
            regime=VolatilityRegime.NORMAL,
            strength=RegimeStrength.WEAK,
            probability=0.5,
            volatility_level=0.15,
            percentile=50.0,
            trend='stable',
            duration_hours=0,
            start_time=datetime.now()
        )

        return RegimeAnalysis(
            current_state=default_state,
            regime_history=[],
            recent_transitions=[],
            regime_distribution={regime: 0.0 for regime in VolatilityRegime}
        )


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    # Create sample data with regime changes
    dates = pd.date_range('2024-01-01', periods=1000, freq='1h')

    # Generate data with different volatility regimes
    np.random.seed(42)
    prices = []
    price = 585.0

    for i in range(1000):
        # Create regime changes
        if i < 200:
            # Low volatility regime
            volatility = 0.0005
        elif i < 400:
            # Normal volatility
            volatility = 0.001
        elif i < 600:
            # High volatility
            volatility = 0.002
        elif i < 800:
            # Back to normal
            volatility = 0.001
        else:
            # Extreme volatility
            volatility = 0.003

        # Generate price with regime-specific volatility
        price *= (1 + np.random.normal(0, volatility))
        prices.append(price)

    # Create OHLCV data
    data = pd.DataFrame({
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.001))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.001))) for p in prices],
        'close': [p * (1 + np.random.normal(0, 0.0005)) for p in prices],
        'volume': np.random.randint(1000, 10000, 1000)
    }, index=dates)

    # Mock ML model manager
    class MockMLModelManager:
        def __init__(self):
            self.models = {}

        def register_model(self, model, name, version, config, performance_metrics):
            self.models[name] = {
                'model': model,
                'version': version,
                'config': config,
                'metrics': performance_metrics,
                'trained_at': datetime.now()
            }

        def get_model(self, name):
            return self.models.get(name)

    # Initialize analyzer
    config_manager = ConfigManager()
    ml_manager = MockMLModelManager()
    analyzer = VolatilityRegimeAnalyzer(config_manager, ml_manager)

    # Initial training
    analyzer.force_retrain(data[:500])

    # Analyze current regime
    analysis = analyzer.analyze_regime(data)


    # Show regime distribution
    for _regime, _pct in analysis.regime_distribution.items():
        pass

    # Show recent transitions
    for _transition in analysis.recent_transitions[-3:]:
        pass

    # Get recommendations
    recommendations = analyzer.get_regime_recommendations(analysis.current_state.regime)


    # Test prediction
    if analysis.prediction:
        for _regime, _prob in analysis.prediction['next_regime_probability'].items():
            pass

    # Model info
    if analysis.model_info:
        pass

    # Test auto-retraining
    # Simulate time passing
    analyzer.last_retrain_date = datetime.now() - timedelta(days=31)

    # This should trigger retrain
    analysis2 = analyzer.analyze_regime(data)
