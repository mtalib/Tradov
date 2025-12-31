#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderM06_HMMRegimeDetector.py
Group: M (Machine Learning)
Purpose: Hidden Markov Model for Market Regime Detection
Author: Mohamed Talib
Date Created: 2025-08-12
Last Updated: 2025-08-12 Time: 14:30:00

Description:
    This module implements a Hidden Markov Model (HMM) for detecting market
    regimes in SPY options trading. It identifies three distinct market states:
    Low Volatility Trending, High Volatility Mean-Reverting, and Transitional
    Neutral. The module provides real-time regime detection, confidence scoring,
    and regime-based signal generation for adaptive trading strategies.
"""

# ==============================================================================
# IMPORTS
# ==============================================================================

# Standard library imports
import json
import logging
import hashlib
import pickle
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor

# Third-party imports
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import TimeSeriesSplit
from statsmodels.tsa.stattools import adfuller

# HMM specific imports
try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    warnings.warn("hmmlearn not installed. HMM functionality will be limited.")

# Suppress warnings
warnings.filterwarnings('ignore', category=RuntimeWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

# Model Configuration
DEFAULT_N_STATES = 3
DEFAULT_COVARIANCE_TYPE = "diag"
DEFAULT_N_ITER = 100
DEFAULT_RANDOM_STATE = 42
MIN_TRAINING_SAMPLES = 250
MAX_TRAINING_SAMPLES = 2000

# Feature Configuration
FEATURE_WINDOW = 20
MOMENTUM_PERIODS = [5, 10, 20]
VOLATILITY_WINDOW = 20
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# Performance Configuration
CACHE_TTL = 60  # seconds
UPDATE_INTERVAL = 60  # seconds
CONFIDENCE_THRESHOLD = 0.65
REGIME_PERSISTENCE_MIN = 3  # bars

# Rolling Window Configuration (from Markov-Chains2.md best practices)
ROLLING_WINDOW_DAYS = 63  # ~3 months of trading days
RETRAIN_INTERVAL_HOURS = 24  # Hours between retraining
PERFORMANCE_DEGRADATION_THRESHOLD = 0.15  # Trigger retrain if accuracy drops

# Risk Configuration
REGIME_RISK_LIMITS = {
    "LOW_VOLATILITY_TRENDING": 1.0,
    "HIGH_VOLATILITY_MEAN_REVERTING": 0.5,
    "TRANSITIONAL_NEUTRAL": 0.3
}

# ==============================================================================
# LOGGER SETUP
# ==============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ==============================================================================
# DATA CLASSES
# ==============================================================================

class MarketRegime(Enum):
    """Market regime enumeration"""
    LOW_VOLATILITY_TRENDING = "LOW_VOLATILITY_TRENDING"
    HIGH_VOLATILITY_MEAN_REVERTING = "HIGH_VOLATILITY_MEAN_REVERTING"
    TRANSITIONAL_NEUTRAL = "TRANSITIONAL_NEUTRAL"

@dataclass
class RegimeData:
    """Container for regime detection data"""
    regime: MarketRegime
    confidence: float
    state_probabilities: np.ndarray
    timestamp: datetime = field(default_factory=datetime.now)
    persistence: int = 0
    transition_probability: float = 0.0
    features: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RegimeSignal:
    """Trading signal based on regime"""
    symbol: str
    regime: MarketRegime
    signal_type: str  # "BUY", "SELL", "HOLD"
    confidence: float
    strategy_hint: str
    position_size_multiplier: float
    risk_parameters: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RegimeTransition:
    """Regime transition event"""
    from_regime: MarketRegime
    to_regime: MarketRegime
    confidence: float
    transition_probability: float
    timestamp: datetime = field(default_factory=datetime.now)
    expected_duration: Optional[int] = None

# ==============================================================================
# MAIN HMM REGIME DETECTOR CLASS
# ==============================================================================

class SpyderM06_HMMRegimeDetector:
    """
    Hidden Markov Model for Market Regime Detection.
    
    This class implements a sophisticated HMM-based regime detection system
    specifically optimized for SPY options trading. It identifies market
    regimes and provides actionable trading signals.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize HMM Regime Detector.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = self._build_config(config)
        
        # Model components
        self.hmm_model = None
        self.scaler = StandardScaler()
        self.regime_models = {}  # Regime-specific ML models
        
        # State tracking
        self.current_regime = None
        self.previous_regime = None
        self.regime_confidence = 0.0
        self.regime_persistence = 0
        self.state_probabilities = None
        
        # Data storage
        self.market_data = pd.DataFrame()
        self.feature_data = pd.DataFrame()
        self.regime_history = deque(maxlen=1000)
        self.transition_history = deque(maxlen=100)
        self.signal_history = deque(maxlen=500)
        
        # Performance tracking
        self.metrics = {
            'detections': 0,
            'transitions': 0,
            'accuracy': 0.0,
            'avg_confidence': 0.0,
            'regime_durations': defaultdict(list)
        }
        
        # Cache management
        self.cache = {}
        self.cache_timestamps = {}
        
        # Threading
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Initialize model if data available
        if HMM_AVAILABLE:
            self._initialize_model()
        else:
            logger.error("HMM library not available. Please install hmmlearn.")
    
    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    
    def _build_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build configuration with defaults"""
        default_config = {
            'n_states': DEFAULT_N_STATES,
            'covariance_type': DEFAULT_COVARIANCE_TYPE,
            'n_iter': DEFAULT_N_ITER,
            'random_state': DEFAULT_RANDOM_STATE,
            'min_samples': MIN_TRAINING_SAMPLES,
            'max_samples': MAX_TRAINING_SAMPLES,
            'update_interval': UPDATE_INTERVAL,
            'confidence_threshold': CONFIDENCE_THRESHOLD,
            'enable_caching': True,
            'enable_ml_models': True
        }
        
        if config:
            default_config.update(config)
        
        return default_config
    
    def _initialize_model(self) -> None:
        """Initialize HMM model"""
        try:
            self.hmm_model = hmm.GaussianHMM(
                n_components=self.config['n_states'],
                covariance_type=self.config['covariance_type'],
                n_iter=self.config['n_iter'],
                random_state=self.config['random_state']
            )
            logger.info("HMM model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize HMM model: {e}")
            self.hmm_model = None
    
    # ==========================================================================
    # DATA PROCESSING METHODS
    # ==========================================================================
    
    def update_market_data(self, data: pd.DataFrame) -> None:
        """
        Update market data and trigger regime detection.
        
        Args:
            data: DataFrame with OHLCV data
        """
        with self.lock:
            try:
                # Validate data
                required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
                if not all(col in data.columns for col in required_columns):
                    logger.error("Missing required columns in market data")
                    return
                
                # Update market data
                self.market_data = data.copy()
                
                # Engineer features
                self.feature_data = self._engineer_features(data)
                
                # Detect regime if enough data
                if len(self.feature_data) >= self.config['min_samples']:
                    self._detect_regime()
                
            except Exception as e:
                logger.error(f"Error updating market data: {e}")
    
    def _engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features for HMM model.
        
        Args:
            data: Raw market data
            
        Returns:
            DataFrame with engineered features
        """
        try:
            features = pd.DataFrame(index=data.index)
            
            # Returns
            features['returns'] = data['Close'].pct_change()
            features['log_returns'] = np.log(data['Close'] / data['Close'].shift(1))
            
            # Volatility measures
            features['volatility'] = features['returns'].rolling(VOLATILITY_WINDOW).std()
            features['volatility_ratio'] = features['volatility'] / features['volatility'].rolling(60).mean()
            
            # Volume features
            features['volume_ratio'] = data['Volume'] / data['Volume'].rolling(20).mean()
            features['dollar_volume'] = data['Close'] * data['Volume']
            
            # Price features
            features['hl_ratio'] = (data['High'] - data['Low']) / data['Close']
            features['co_ratio'] = (data['Close'] - data['Open']) / data['Open']
            
            # Technical indicators
            features = self._add_technical_indicators(features, data)
            
            # Microstructure features
            features = self._add_microstructure_features(features, data)
            
            # Statistical features
            features = self._add_statistical_features(features)
            
            # Clean data
            features = features.replace([np.inf, -np.inf], np.nan)
            features = features.fillna(method='ffill').fillna(0)
            
            return features
            
        except Exception as e:
            logger.error(f"Error engineering features: {e}")
            return pd.DataFrame()
    
    def _add_technical_indicators(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to features"""
        try:
            # RSI
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(RSI_PERIOD).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(RSI_PERIOD).mean()
            rs = gain / loss
            features['rsi'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp1 = data['Close'].ewm(span=MACD_FAST, adjust=False).mean()
            exp2 = data['Close'].ewm(span=MACD_SLOW, adjust=False).mean()
            features['macd'] = exp1 - exp2
            features['macd_signal'] = features['macd'].ewm(span=MACD_SIGNAL, adjust=False).mean()
            features['macd_histogram'] = features['macd'] - features['macd_signal']
            
            # Bollinger Bands
            sma = data['Close'].rolling(20).mean()
            std = data['Close'].rolling(20).std()
            features['bb_upper'] = sma + (std * 2)
            features['bb_lower'] = sma - (std * 2)
            features['bb_width'] = (features['bb_upper'] - features['bb_lower']) / sma
            features['bb_position'] = (data['Close'] - features['bb_lower']) / (features['bb_upper'] - features['bb_lower'])
            
            # Momentum
            for period in MOMENTUM_PERIODS:
                features[f'momentum_{period}'] = data['Close'].pct_change(period)
            
            return features
            
        except Exception as e:
            logger.error(f"Error adding technical indicators: {e}")
            return features
    
    def _add_microstructure_features(self, features: pd.DataFrame, data: pd.DataFrame) -> pd.DataFrame:
        """Add market microstructure features"""
        try:
            # Spread proxy
            features['spread_proxy'] = 2 * np.sqrt(np.abs(
                np.log(data['High'] / data['Close']) * 
                np.log(data['High'] / data['Open'])
            ))
            
            # Amihud illiquidity
            features['illiquidity'] = np.abs(features['returns']) / features['dollar_volume']
            
            # Kyle's lambda (simplified)
            features['kyle_lambda'] = np.abs(features['returns']) / np.sqrt(data['Volume'])
            
            # Realized volatility
            features['realized_vol'] = np.sqrt(
                features['returns'].rolling(5).apply(lambda x: np.sum(x**2))
            )
            
            return features
            
        except Exception as e:
            logger.error(f"Error adding microstructure features: {e}")
            return features
    
    def _add_statistical_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Add statistical features"""
        try:
            # Rolling statistics
            for window in [5, 10, 20]:
                # Skewness
                features[f'skew_{window}'] = features['returns'].rolling(window).skew()
                
                # Kurtosis
                features[f'kurtosis_{window}'] = features['returns'].rolling(window).kurt()
                
                # Autocorrelation
                features[f'autocorr_{window}'] = features['returns'].rolling(window).apply(
                    lambda x: x.autocorr() if len(x) > 1 else 0
                )
            
            # Hurst exponent (simplified)
            features['hurst'] = features['returns'].rolling(20).apply(
                lambda x: self._calculate_hurst(x) if len(x) > 10 else 0.5
            )
            
            return features
            
        except Exception as e:
            logger.error(f"Error adding statistical features: {e}")
            return features
    
    def _calculate_hurst(self, series: pd.Series) -> float:
        """Calculate simplified Hurst exponent"""
        try:
            # Simplified R/S analysis
            lags = range(2, min(20, len(series) // 2))
            tau = []
            
            for lag in lags:
                # Calculate R/S statistic
                chunks = [series[i:i+lag] for i in range(0, len(series), lag)]
                rs_values = []
                
                for chunk in chunks:
                    if len(chunk) < 2:
                        continue
                    mean = chunk.mean()
                    std = chunk.std()
                    if std == 0:
                        continue
                    cumsum = (chunk - mean).cumsum()
                    R = cumsum.max() - cumsum.min()
                    S = std
                    rs_values.append(R / S)
                
                if rs_values:
                    tau.append(np.mean(rs_values))
            
            if len(tau) > 2:
                # Fit line to log-log plot
                poly = np.polyfit(np.log(lags[:len(tau)]), np.log(tau), 1)
                return poly[0]
            
            return 0.5  # Random walk
            
        except:
            return 0.5
    
    # ==========================================================================
    # REGIME DETECTION METHODS
    # ==========================================================================
    
    def _detect_regime(self) -> None:
        """Perform regime detection using HMM"""
        try:
            if self.hmm_model is None:
                return
            
            # Prepare features
            features = self._prepare_hmm_features()
            if features is None or len(features) < self.config['min_samples']:
                return
            
            # Train or update model
            if self._should_retrain():
                self._train_model(features)
            
            # Predict current regime
            regime_data = self._predict_regime(features)
            
            if regime_data:
                # Update state
                self._update_regime_state(regime_data)
                
                # Generate signals
                signals = self._generate_regime_signals(regime_data)
                for signal in signals:
                    self.signal_history.append(signal)
                
                # Update metrics
                self._update_metrics(regime_data)
                
        except Exception as e:
            logger.error(f"Error in regime detection: {e}")
    
    def _prepare_hmm_features(self) -> Optional[np.ndarray]:
        """Prepare features for HMM model"""
        try:
            # Select key features for HMM
            feature_columns = [
                'returns', 'volatility', 'volume_ratio',
                'rsi', 'macd_histogram', 'bb_width',
                'momentum_5', 'momentum_10', 'momentum_20',
                'spread_proxy', 'illiquidity', 'hurst'
            ]
            
            # Filter available features
            available_features = [
                col for col in feature_columns 
                if col in self.feature_data.columns
            ]
            
            if not available_features:
                logger.warning("No features available for HMM")
                return None
            
            # Extract and clean features
            features = self.feature_data[available_features].copy()
            features = features.dropna()
            
            # Apply stationarity transformation if needed
            features = self._ensure_stationarity(features)
            
            # Limit samples
            if len(features) > self.config['max_samples']:
                features = features.iloc[-self.config['max_samples']:]
            
            return features.values
            
        except Exception as e:
            logger.error(f"Error preparing HMM features: {e}")
            return None
    
    def _ensure_stationarity(self, features: pd.DataFrame) -> pd.DataFrame:
        """Ensure feature stationarity using ADF test"""
        try:
            stationary_features = features.copy()
            
            for col in features.columns:
                # Test for stationarity
                series = features[col].dropna()
                if len(series) < 20:
                    continue
                
                adf_result = adfuller(series, autolag='AIC')
                p_value = adf_result[1]
                
                # If non-stationary, apply differencing
                if p_value > 0.05:
                    stationary_features[col] = series.diff()
                    logger.debug(f"Applied differencing to {col} (p-value: {p_value:.4f})")
            
            return stationary_features.fillna(method='ffill').fillna(0)
            
        except Exception as e:
            logger.error(f"Error ensuring stationarity: {e}")
            return features
    
    def _should_retrain(self) -> bool:
        """
        Determine if model should be retrained.

        Enhanced with rolling window logic from Markov-Chains2.md:
        "You must re-train the model frequently (e.g., rolling window of 3 months)."
        """
        # Retrain if no regime history
        if len(self.regime_history) == 0:
            return True

        # Check time-based retraining (rolling window policy)
        last_retrain = getattr(self, '_last_retrain_time', None)
        if last_retrain is not None:
            hours_since_retrain = (datetime.now() - last_retrain).total_seconds() / 3600
            if hours_since_retrain >= RETRAIN_INTERVAL_HOURS:
                logger.info(f"Rolling window retrain triggered: {hours_since_retrain:.1f} hours since last retrain")
                return True

        # Retrain periodically by sample count
        if len(self.regime_history) % 100 == 0:
            return True

        # Retrain if confidence consistently low (performance degradation)
        recent_confidence = [r.confidence for r in list(self.regime_history)[-10:]]
        if recent_confidence and np.mean(recent_confidence) < (CONFIDENCE_THRESHOLD - PERFORMANCE_DEGRADATION_THRESHOLD):
            logger.info(f"Performance degradation detected: avg confidence {np.mean(recent_confidence):.2f}")
            return True

        return False

    def _use_rolling_window_data(self, features: np.ndarray) -> np.ndarray:
        """
        Apply rolling window to training data to handle non-stationarity.

        From Markov-Chains2.md: Markets change over time, so we use only
        the most recent ~3 months of data.
        """
        if len(features) > ROLLING_WINDOW_DAYS:
            logger.debug(f"Applying rolling window: using last {ROLLING_WINDOW_DAYS} of {len(features)} samples")
            return features[-ROLLING_WINDOW_DAYS:]
        return features
    
    def _train_model(self, features: np.ndarray) -> None:
        """
        Train HMM model with rolling window support.

        Enhanced to use rolling window data to handle non-stationarity
        as recommended in Markov-Chains2.md documentation.
        """
        try:
            # Apply rolling window to handle non-stationarity
            features_windowed = self._use_rolling_window_data(features)

            # Scale features
            features_scaled = self.scaler.fit_transform(features_windowed)

            # Train HMM
            self.hmm_model.fit(features_scaled)

            # Train regime-specific models if enabled
            if self.config['enable_ml_models']:
                self._train_regime_models(features_scaled)

            # Track retrain time for rolling window policy
            self._last_retrain_time = datetime.now()

            logger.info(f"HMM model trained with {len(features_windowed)} samples "
                       f"(rolling window from {len(features)} total)")

        except Exception as e:
            logger.error(f"Error training model: {e}")
    
    def _train_regime_models(self, features: np.ndarray) -> None:
        """Train regime-specific ML models"""
        try:
            # Get regime labels
            states = self.hmm_model.predict(features)
            
            # Create target (next period return sign)
            returns = self.feature_data['returns'].iloc[-len(features):].values
            targets = np.sign(np.roll(returns, -1))[:-1]
            features_train = features[:-1]
            states_train = states[:-1]
            
            # Train model for each regime
            for state in range(self.config['n_states']):
                # Get samples for this regime
                mask = states_train == state
                if np.sum(mask) < 20:
                    continue
                
                X = features_train[mask]
                y = targets[mask]
                
                # Train Random Forest
                model = RandomForestClassifier(
                    n_estimators=50,
                    max_depth=5,
                    random_state=self.config['random_state']
                )
                model.fit(X, y)
                
                # Map state to regime
                regime = self._map_state_to_regime(state, features[mask])
                self.regime_models[regime] = model
                
                logger.debug(f"Trained model for {regime.value} with {len(X)} samples")
                
        except Exception as e:
            logger.error(f"Error training regime models: {e}")
    
    def _predict_regime(self, features: np.ndarray) -> Optional[RegimeData]:
        """Predict current market regime"""
        try:
            # Scale features
            features_scaled = self.scaler.transform(features)
            
            # Get state sequence
            states = self.hmm_model.predict(features_scaled)
            current_state = states[-1]
            
            # Get state probabilities
            log_prob, state_probs = self.hmm_model.score_samples(features_scaled)
            current_probs = state_probs[-1]
            
            # Calculate confidence (1 - entropy)
            entropy = -np.sum(current_probs * np.log(current_probs + 1e-10))
            max_entropy = np.log(self.config['n_states'])
            confidence = 1 - (entropy / max_entropy)
            
            # Map state to regime
            regime = self._map_state_to_regime(current_state, features_scaled)
            
            # Calculate transition probability
            trans_prob = self._calculate_transition_probability(states)
            
            # Extract current feature values
            feature_dict = self._extract_current_features()
            
            # Create regime data
            regime_data = RegimeData(
                regime=regime,
                confidence=confidence,
                state_probabilities=current_probs,
                transition_probability=trans_prob,
                features=feature_dict,
                metadata={'state': current_state, 'log_prob': log_prob}
            )
            
            return regime_data
            
        except Exception as e:
            logger.error(f"Error predicting regime: {e}")
            return None
    
    def _map_state_to_regime(self, state: int, features: np.ndarray) -> MarketRegime:
        """Map HMM state to market regime"""
        try:
            # Analyze feature characteristics for this state
            if len(features.shape) == 1:
                features = features.reshape(1, -1)
            
            # Get volatility and momentum indices
            vol_idx = 1  # volatility feature index
            mom_idx = 6  # momentum_5 feature index
            
            # Calculate state characteristics
            avg_volatility = np.mean(features[:, vol_idx]) if features.shape[1] > vol_idx else 0
            avg_momentum = np.mean(features[:, mom_idx]) if features.shape[1] > mom_idx else 0
            
            # Map based on characteristics
            if avg_volatility < -0.5:  # Low volatility (standardized)
                return MarketRegime.LOW_VOLATILITY_TRENDING
            elif avg_volatility > 0.5:  # High volatility
                return MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING
            else:
                return MarketRegime.TRANSITIONAL_NEUTRAL
                
        except Exception as e:
            logger.error(f"Error mapping state to regime: {e}")
            return MarketRegime.TRANSITIONAL_NEUTRAL
    
    def _calculate_transition_probability(self, states: np.ndarray) -> float:
        """Calculate probability of regime transition"""
        try:
            if len(states) < 2:
                return 0.0
            
            current_state = states[-1]
            prev_state = states[-2]
            
            # Get transition matrix
            trans_matrix = self.hmm_model.transmat_
            
            # Probability of staying in current state
            stay_prob = trans_matrix[current_state, current_state]
            
            # Transition probability is 1 - stay probability
            trans_prob = 1 - stay_prob
            
            return float(trans_prob)
            
        except Exception as e:
            logger.error(f"Error calculating transition probability: {e}")
            return 0.0
    
    def _extract_current_features(self) -> Dict[str, float]:
        """Extract current feature values"""
        try:
            if self.feature_data.empty:
                return {}
            
            current_features = {}
            latest = self.feature_data.iloc[-1]
            
            key_features = [
                'returns', 'volatility', 'volume_ratio',
                'rsi', 'macd_histogram', 'bb_width',
                'momentum_5', 'momentum_10', 'momentum_20'
            ]
            
            for feature in key_features:
                if feature in latest.index:
                    current_features[feature] = float(latest[feature])
            
            return current_features
            
        except Exception as e:
            logger.error(f"Error extracting features: {e}")
            return {}
    
    # ==========================================================================
    # STATE MANAGEMENT METHODS
    # ==========================================================================
    
    def _update_regime_state(self, regime_data: RegimeData) -> None:
        """Update internal regime state"""
        try:
            # Check for regime change
            if self.current_regime != regime_data.regime:
                # Record transition
                if self.current_regime is not None:
                    transition = RegimeTransition(
                        from_regime=self.current_regime,
                        to_regime=regime_data.regime,
                        confidence=regime_data.confidence,
                        transition_probability=regime_data.transition_probability
                    )
                    self.transition_history.append(transition)
                    
                    # Log transition
                    logger.info(
                        f"Regime transition: {self.current_regime.value} -> "
                        f"{regime_data.regime.value} (confidence: {regime_data.confidence:.2%})"
                    )
                
                # Reset persistence
                self.regime_persistence = 1
                self.previous_regime = self.current_regime
            else:
                # Increment persistence
                self.regime_persistence += 1
            
            # Update current state
            self.current_regime = regime_data.regime
            self.regime_confidence = regime_data.confidence
            self.state_probabilities = regime_data.state_probabilities
            
            # Update regime data with persistence
            regime_data.persistence = self.regime_persistence
            
            # Add to history
            self.regime_history.append(regime_data)
            
        except Exception as e:
            logger.error(f"Error updating regime state: {e}")
    
    # ==========================================================================
    # SIGNAL GENERATION METHODS
    # ==========================================================================
    
    def _generate_regime_signals(self, regime_data: RegimeData) -> List[RegimeSignal]:
        """Generate trading signals based on regime"""
        signals = []
        
        try:
            # Only generate signals if confidence is high enough
            if regime_data.confidence < self.config['confidence_threshold']:
                return signals
            
            # Only generate signals if regime is persistent
            if self.regime_persistence < REGIME_PERSISTENCE_MIN:
                return signals
            
            # Generate regime-specific signals
            if regime_data.regime == MarketRegime.LOW_VOLATILITY_TRENDING:
                signals.extend(self._generate_trending_signals(regime_data))
            elif regime_data.regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING:
                signals.extend(self._generate_mean_reversion_signals(regime_data))
            else:
                signals.extend(self._generate_neutral_signals(regime_data))
            
        except Exception as e:
            logger.error(f"Error generating signals: {e}")
        
        return signals
    
    def _generate_trending_signals(self, regime_data: RegimeData) -> List[RegimeSignal]:
        """Generate signals for trending regime"""
        signals = []
        
        try:
            # Momentum-based signal
            momentum = regime_data.features.get('momentum_10', 0)
            rsi = regime_data.features.get('rsi', 50)
            
            signal_type = "HOLD"
            if momentum > 0.01 and rsi < 70:
                signal_type = "BUY"
            elif momentum < -0.01 or rsi > 70:
                signal_type = "SELL"
            
            signal = RegimeSignal(
                symbol="SPY",
                regime=regime_data.regime,
                signal_type=signal_type,
                confidence=regime_data.confidence,
                strategy_hint="MOMENTUM",
                position_size_multiplier=1.0,
                risk_parameters={
                    'stop_loss': 0.02,
                    'take_profit': 0.04,
                    'max_holding_period': 10
                }
            )
            signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error generating trending signals: {e}")
        
        return signals
    
    def _generate_mean_reversion_signals(self, regime_data: RegimeData) -> List[RegimeSignal]:
        """Generate signals for mean-reverting regime"""
        signals = []
        
        try:
            # Mean reversion signal
            bb_position = regime_data.features.get('bb_position', 0.5)
            rsi = regime_data.features.get('rsi', 50)
            
            signal_type = "HOLD"
            if bb_position < 0.2 and rsi < 30:
                signal_type = "BUY"
            elif bb_position > 0.8 and rsi > 70:
                signal_type = "SELL"
            
            signal = RegimeSignal(
                symbol="SPY",
                regime=regime_data.regime,
                signal_type=signal_type,
                confidence=regime_data.confidence * 0.8,  # Lower confidence in volatile regime
                strategy_hint="MEAN_REVERSION",
                position_size_multiplier=0.5,  # Smaller position in volatile regime
                risk_parameters={
                    'stop_loss': 0.015,
                    'take_profit': 0.02,
                    'max_holding_period': 5
                }
            )
            signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error generating mean reversion signals: {e}")
        
        return signals
    
    def _generate_neutral_signals(self, regime_data: RegimeData) -> List[RegimeSignal]:
        """Generate signals for neutral regime"""
        signals = []
        
        try:
            # Conservative signal in neutral regime
            signal = RegimeSignal(
                symbol="SPY",
                regime=regime_data.regime,
                signal_type="HOLD",
                confidence=regime_data.confidence * 0.5,
                strategy_hint="NEUTRAL",
                position_size_multiplier=0.3,
                risk_parameters={
                    'stop_loss': 0.01,
                    'take_profit': 0.015,
                    'max_holding_period': 3
                }
            )
            signals.append(signal)
            
        except Exception as e:
            logger.error(f"Error generating neutral signals: {e}")
        
        return signals
    
    # ==========================================================================
    # INTEGRATION METHODS
    # ==========================================================================
    
    def get_regime_context(self) -> Dict[str, Any]:
        """
        Get comprehensive regime context for AI agents.
        
        Returns:
            Dict containing regime information for other agents
        """
        with self.lock:
            if self.current_regime is None:
                return {
                    'status': 'no_regime_detected',
                    'regime': None,
                    'confidence': 0.0
                }
            
            return {
                'status': 'active',
                'regime': self.current_regime.value,
                'confidence': self.regime_confidence,
                'persistence': self.regime_persistence,
                'state_probabilities': self.state_probabilities.tolist() if self.state_probabilities is not None else [],
                'transition_probability': self._get_current_transition_probability(),
                'features': self._extract_current_features(),
                'risk_parameters': REGIME_RISK_LIMITS.get(self.current_regime.value, 0.5),
                'strategy_hints': self._get_strategy_hints(),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_strategy_hints(self) -> Dict[str, Any]:
        """
        Get strategy hints for X03_StrategyDirectorAgent.
        
        Returns:
            Dict with strategy recommendations based on regime
        """
        if self.current_regime == MarketRegime.LOW_VOLATILITY_TRENDING:
            return {
                'preferred_strategies': ['iron_condor', 'credit_spread', 'diagonal'],
                'avoid_strategies': ['straddle', 'strangle'],
                'position_sizing': 'aggressive',
                'option_selection': {
                    'delta_range': (0.2, 0.4),
                    'dte_range': (7, 30),
                    'iv_preference': 'sell_high_iv'
                },
                'stop_loss': 'wider',
                'take_profit': 'let_profits_run'
            }
        elif self.current_regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING:
            return {
                'preferred_strategies': ['straddle', 'strangle', 'butterfly'],
                'avoid_strategies': ['naked_puts', 'naked_calls'],
                'position_sizing': 'conservative',
                'option_selection': {
                    'delta_range': (0.4, 0.6),
                    'dte_range': (1, 7),
                    'iv_preference': 'buy_low_iv'
                },
                'stop_loss': 'tight',
                'take_profit': 'quick_profits'
            }
        else:  # TRANSITIONAL_NEUTRAL
            return {
                'preferred_strategies': ['iron_butterfly', 'calendar_spread'],
                'avoid_strategies': ['directional_plays'],
                'position_sizing': 'minimal',
                'option_selection': {
                    'delta_range': (0.3, 0.5),
                    'dte_range': (14, 30),
                    'iv_preference': 'neutral'
                },
                'stop_loss': 'moderate',
                'take_profit': 'moderate'
            }
    
    def get_risk_parameters(self) -> Dict[str, Any]:
        """
        Get risk parameters for X04_RiskGuardianAgent.
        
        Returns:
            Dict with risk management parameters based on regime
        """
        base_params = {
            'regime': self.current_regime.value if self.current_regime else 'UNKNOWN',
            'confidence': self.regime_confidence,
            'max_position_size': REGIME_RISK_LIMITS.get(
                self.current_regime.value if self.current_regime else 'TRANSITIONAL_NEUTRAL',
                0.3
            ),
            'volatility_scalar': self._calculate_volatility_scalar(),
            'correlation_matrix': self._get_regime_correlations(),
            'var_multiplier': self._get_var_multiplier(),
            'stress_test_scenarios': self._get_stress_scenarios()
        }
        
        return base_params
    
    def get_market_insights(self) -> Dict[str, Any]:
        """
        Get market insights for X13_MarketAnalysisAgent.
        
        Returns:
            Dict with market analysis based on regime
        """
        return {
            'regime': self.current_regime.value if self.current_regime else 'UNKNOWN',
            'regime_description': self._get_regime_description(),
            'market_conditions': self._analyze_market_conditions(),
            'regime_duration': self.regime_persistence,
            'transition_risk': self._assess_transition_risk(),
            'historical_context': self._get_historical_context(),
            'forecast': self._generate_regime_forecast()
        }
    
    # ==========================================================================
    # ANALYTICS METHODS
    # ==========================================================================
    
    def _update_metrics(self, regime_data: RegimeData) -> None:
        """Update performance metrics"""
        try:
            self.metrics['detections'] += 1
            
            # Update average confidence
            n = self.metrics['detections']
            avg_conf = self.metrics['avg_confidence']
            self.metrics['avg_confidence'] = (avg_conf * (n - 1) + regime_data.confidence) / n
            
            # Track regime durations
            if self.previous_regime and self.previous_regime != regime_data.regime:
                self.metrics['transitions'] += 1
                self.metrics['regime_durations'][self.previous_regime.value].append(
                    self.regime_persistence
                )
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        with self.lock:
            metrics = self.metrics.copy()
            
            # Add current regime info
            metrics['current_regime'] = self.current_regime.value if self.current_regime else None
            metrics['current_confidence'] = self.regime_confidence
            metrics['regime_persistence'] = self.regime_persistence
            
            # Calculate regime statistics
            if self.metrics['regime_durations']:
                avg_durations = {}
                for regime, durations in self.metrics['regime_durations'].items():
                    if durations:
                        avg_durations[regime] = {
                            'mean': np.mean(durations),
                            'std': np.std(durations),
                            'min': np.min(durations),
                            'max': np.max(durations)
                        }
                metrics['regime_statistics'] = avg_durations
            
            return metrics
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _get_current_transition_probability(self) -> float:
        """Get current transition probability"""
        if not self.transition_history:
            return 0.0
        return self.transition_history[-1].transition_probability
    
    def _get_strategy_hints(self) -> List[str]:
        """Get list of strategy hints"""
        hints = self.get_strategy_hints()
        return hints.get('preferred_strategies', [])
    
    def _calculate_volatility_scalar(self) -> float:
        """Calculate volatility scalar for position sizing"""
        if self.current_regime == MarketRegime.LOW_VOLATILITY_TRENDING:
            return 1.2
        elif self.current_regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING:
            return 0.6
        else:
            return 0.8
    
    def _get_regime_correlations(self) -> Dict[str, float]:
        """Get regime-specific correlations"""
        # Placeholder - would calculate from historical data
        return {
            'spy_vix': -0.8 if self.current_regime == MarketRegime.LOW_VOLATILITY_TRENDING else -0.3,
            'spy_bonds': -0.4 if self.current_regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING else -0.2,
            'spy_gold': 0.1 if self.current_regime == MarketRegime.TRANSITIONAL_NEUTRAL else -0.1
        }
    
    def _get_var_multiplier(self) -> float:
        """Get Value at Risk multiplier"""
        if self.current_regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING:
            return 2.0
        elif self.current_regime == MarketRegime.TRANSITIONAL_NEUTRAL:
            return 1.5
        else:
            return 1.0
    
    def _get_stress_scenarios(self) -> List[Dict[str, Any]]:
        """Get regime-specific stress test scenarios"""
        if self.current_regime == MarketRegime.LOW_VOLATILITY_TRENDING:
            return [
                {'name': 'sudden_volatility_spike', 'probability': 0.15, 'impact': -0.05},
                {'name': 'trend_reversal', 'probability': 0.10, 'impact': -0.03}
            ]
        elif self.current_regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING:
            return [
                {'name': 'volatility_expansion', 'probability': 0.25, 'impact': -0.08},
                {'name': 'liquidity_crisis', 'probability': 0.05, 'impact': -0.15}
            ]
        else:
            return [
                {'name': 'regime_shift', 'probability': 0.30, 'impact': -0.04},
                {'name': 'directional_breakout', 'probability': 0.20, 'impact': -0.02}
            ]
    
    def _get_regime_description(self) -> str:
        """Get human-readable regime description"""
        descriptions = {
            MarketRegime.LOW_VOLATILITY_TRENDING: (
                "Market is in a low volatility trending regime. "
                "Expect persistent directional movement with contained risk."
            ),
            MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: (
                "Market is in a high volatility mean-reverting regime. "
                "Expect sharp reversals and increased uncertainty."
            ),
            MarketRegime.TRANSITIONAL_NEUTRAL: (
                "Market is in a transitional/neutral regime. "
                "Direction uncertain, awaiting clearer signals."
            )
        }
        return descriptions.get(self.current_regime, "Regime unknown")
    
    def _analyze_market_conditions(self) -> Dict[str, Any]:
        """Analyze current market conditions"""
        return {
            'volatility_level': 'low' if self.current_regime == MarketRegime.LOW_VOLATILITY_TRENDING else 'high',
            'trend_strength': 'strong' if self.regime_persistence > 10 else 'weak',
            'mean_reversion_tendency': 'high' if self.current_regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING else 'low',
            'regime_stability': 'stable' if self.regime_persistence > 5 else 'unstable'
        }
    
    def _assess_transition_risk(self) -> str:
        """Assess risk of regime transition"""
        trans_prob = self._get_current_transition_probability()
        if trans_prob > 0.7:
            return 'high'
        elif trans_prob > 0.3:
            return 'moderate'
        else:
            return 'low'
    
    def _get_historical_context(self) -> Dict[str, Any]:
        """Get historical regime context"""
        if len(self.regime_history) < 10:
            return {'status': 'insufficient_history'}
        
        recent_regimes = list(self.regime_history)[-50:]
        regime_counts = defaultdict(int)
        for r in recent_regimes:
            regime_counts[r.regime.value] += 1
        
        return {
            'dominant_regime': max(regime_counts, key=regime_counts.get),
            'regime_distribution': dict(regime_counts),
            'avg_confidence': np.mean([r.confidence for r in recent_regimes]),
            'transitions_count': len(self.transition_history)
        }
    
    def _generate_regime_forecast(self) -> Dict[str, Any]:
        """Generate regime forecast"""
        if self.hmm_model is None or self.current_regime is None:
            return {'status': 'unavailable'}
        
        # Simple forecast based on transition matrix
        trans_matrix = self.hmm_model.transmat_
        current_state = self.metrics.get('state', 0)
        
        # Next period probabilities
        next_probs = trans_matrix[current_state]
        
        return {
            'next_period_probabilities': next_probs.tolist(),
            'expected_persistence': int(1 / (1 - trans_matrix[current_state, current_state])),
            'confidence': self.regime_confidence
        }
    
    # ==========================================================================
    # PERSISTENCE METHODS
    # ==========================================================================
    
    def save_model(self, filepath: str) -> None:
        """Save model to disk"""
        try:
            model_data = {
                'hmm_model': self.hmm_model,
                'scaler': self.scaler,
                'regime_models': self.regime_models,
                'config': self.config,
                'metrics': self.metrics
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"Model saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
    
    def load_model(self, filepath: str) -> None:
        """Load model from disk"""
        try:
            with open(filepath, 'rb') as f:
                model_data = pickle.load(f)
            
            self.hmm_model = model_data['hmm_model']
            self.scaler = model_data['scaler']
            self.regime_models = model_data['regime_models']
            self.config.update(model_data['config'])
            self.metrics = model_data['metrics']
            
            logger.info(f"Model loaded from {filepath}")
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
    
    def cleanup(self) -> None:
        """Cleanup resources"""
        try:
            self.executor.shutdown(wait=True)
            logger.info("HMM Regime Detector cleaned up")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_hmm_detector(config: Optional[Dict[str, Any]] = None) -> SpyderM06_HMMRegimeDetector:
    """
    Factory function to create HMM Regime Detector instance.
    
    Args:
        config: Optional configuration dictionary
        
    Returns:
        SpyderM06_HMMRegimeDetector instance
    """
    return SpyderM06_HMMRegimeDetector(config)

# Singleton instance
_module_instance = None

def get_module_instance() -> SpyderM06_HMMRegimeDetector:
    """Get or create singleton instance of the detector."""
    global _module_instance
    if _module_instance is None:
        _module_instance = create_hmm_detector()
    return _module_instance

# ==============================================================================
# TEST SECTION
# ==============================================================================

if __name__ == "__main__":
    """Test the HMM Regime Detector"""
    
    print("="*60)
    print("SPYDER M06 - HMM REGIME DETECTOR TEST")
    print("="*60)
    
    # Create detector
    detector = create_hmm_detector()
    
    # Generate sample data
    print("\n📊 Generating sample market data...")
    dates = pd.date_range(end=datetime.now(), periods=500, freq='D')
    np.random.seed(42)
    
    # Simulate regime-switching data
    prices = [100]
    regimes = []
    
    for i in range(499):
        if i < 150:  # Low volatility trending
            change = np.random.normal(0.001, 0.005)
            regimes.append('LVT')
        elif i < 300:  # High volatility mean-reverting
            change = np.random.normal(0, 0.02) * (-1 if prices[-1] > 100 else 1)
            regimes.append('HVMR')
        else:  # Transitional
            change = np.random.normal(0, 0.01)
            regimes.append('TN')
        
        prices.append(prices[-1] * (1 + change))
    
    # Create DataFrame
    data = pd.DataFrame({
        'Open': prices,
        'High': [p * 1.01 for p in prices],
        'Low': [p * 0.99 for p in prices],
        'Close': prices,
        'Volume': np.random.randint(1000000, 5000000, 500)
    }, index=dates)
    
    print(f"✅ Generated {len(data)} days of market data")
    
    # Update detector with data
    print("\n🔍 Detecting market regimes...")
    detector.update_market_data(data)
    
    # Get regime context
    context = detector.get_regime_context()
    print("\n📈 Current Regime Context:")
    print(f"  Regime: {context.get('regime', 'Unknown')}")
    print(f"  Confidence: {context.get('confidence', 0):.2%}")
    print(f"  Persistence: {context.get('persistence', 0)} periods")
    
    # Get strategy hints
    hints = detector.get_strategy_hints()
    print("\n💡 Strategy Hints:")
    print(f"  Preferred: {hints.get('preferred_strategies', [])}")
    print(f"  Position Sizing: {hints.get('position_sizing', 'unknown')}")
    
    # Get risk parameters
    risk = detector.get_risk_parameters()
    print("\n⚠️ Risk Parameters:")
    print(f"  Max Position Size: {risk.get('max_position_size', 0):.1%}")
    print(f"  Volatility Scalar: {risk.get('volatility_scalar', 1):.2f}")
    
    # Get performance metrics
    metrics = detector.get_performance_metrics()
    print("\n📊 Performance Metrics:")
    print(f"  Detections: {metrics.get('detections', 0)}")
    print(f"  Average Confidence: {metrics.get('avg_confidence', 0):.2%}")
    print(f"  Transitions: {metrics.get('transitions', 0)}")
    
    print("\n✅ HMM Regime Detector test completed successfully!")
