#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL18_EnhancedMLIntegration.py
Purpose: SPYDER - Autonomous Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Autonomous Options Trading System

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
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import deque
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import joblib

warnings.filterwarnings('ignore')

# Machine Learning Libraries
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor, VotingRegressor  # noqa: E402
from sklearn.preprocessing import StandardScaler, RobustScaler  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
import torch.optim as optim  # noqa: E402
from torch.utils.data import DataLoader, TensorDataset  # noqa: E402

# ==================================================================================
# LOGGING CONFIGURATION
# ==================================================================================


logger = logging.getLogger(__name__)

# ==================================================================================
# ENUMS AND CONSTANTS
# ==================================================================================

class ModelType(Enum):
    """Types of ML models"""
    PRICE_PREDICTOR = "price_predictor"
    VOLATILITY_FORECASTER = "volatility_forecaster"
    REGIME_CLASSIFIER = "regime_classifier"
    RISK_ESTIMATOR = "risk_estimator"
    STRATEGY_SELECTOR = "strategy_selector"
    ENTRY_OPTIMIZER = "entry_optimizer"

class PredictionHorizon(Enum):
    """Prediction time horizons"""
    TICK = "tick"  # Next tick
    MINUTE_5 = "5min"
    MINUTE_15 = "15min"
    HOUR = "1hour"
    DAY = "1day"
    WEEK = "1week"

class LearningMode(Enum):
    """Learning modes"""
    BATCH = "batch"
    ONLINE = "online"
    REINFORCEMENT = "reinforcement"
    TRANSFER = "transfer"

# ==================================================================================
# DATA CLASSES
# ==================================================================================

@dataclass
class MLPrediction:
    """ML model prediction"""
    model_type: ModelType
    timestamp: datetime
    prediction: float | str | dict
    confidence: float
    feature_importance: dict[str, float]
    horizon: PredictionHorizon
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ModelPerformance:
    """Model performance metrics"""
    model_id: str
    timestamp: datetime
    mse: float
    mae: float
    accuracy: float
    sharpe_improvement: float
    risk_reduction: float
    trades_improved: int

@dataclass
class FeatureSet:
    """Feature set for ML models"""
    timestamp: datetime
    price_features: np.ndarray
    volume_features: np.ndarray
    technical_features: np.ndarray
    greek_features: np.ndarray
    market_microstructure: np.ndarray
    sentiment_features: np.ndarray | None = None
    custom_features: dict[str, float] | None = None

# ==================================================================================
# NEURAL NETWORK ARCHITECTURES
# ==================================================================================

class LSTMPricePredictor(nn.Module):
    """LSTM network for price prediction"""

    def __init__(self, input_dim: int, hidden_dim: int = 128, num_layers: int = 3):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.lstm = nn.LSTM(input_dim, hidden_dim, num_layers,
                           batch_first=True, dropout=0.2)
        self.attention = nn.MultiheadAttention(hidden_dim, num_heads=4)
        self.fc1 = nn.Linear(hidden_dim, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 1)
        self.dropout = nn.Dropout(0.2)
        self.relu = nn.ReLU()

    def forward(self, x):
        # LSTM layers
        lstm_out, (h_n, c_n) = self.lstm(x)

        # Attention mechanism
        attn_out, _ = self.attention(lstm_out, lstm_out, lstm_out)

        # Combine LSTM and attention
        combined = lstm_out + attn_out

        # Take last timestep
        out = combined[:, -1, :]

        # Fully connected layers
        out = self.relu(self.fc1(out))
        out = self.dropout(out)
        out = self.relu(self.fc2(out))
        out = self.fc3(out)

        return out

class TransformerVolatilityModel(nn.Module):
    """Transformer model for volatility forecasting"""

    def __init__(self, input_dim: int, d_model: int = 256, nhead: int = 8,
                 num_layers: int = 4):
        super().__init__()

        self.input_projection = nn.Linear(input_dim, d_model)
        self.positional_encoding = nn.Parameter(torch.randn(1, 100, d_model))

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=512, dropout=0.1
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        self.fc1 = nn.Linear(d_model, 128)
        self.fc2 = nn.Linear(128, 64)
        self.fc3 = nn.Linear(64, 1)
        self.dropout = nn.Dropout(0.1)
        self.relu = nn.ReLU()

    def forward(self, x):
        # Project input to model dimension
        x = self.input_projection(x)

        # Add positional encoding
        seq_len = x.size(1)
        x = x + self.positional_encoding[:, :seq_len, :]

        # Transformer encoding
        x = x.transpose(0, 1)  # Transformer expects seq_len first
        transformer_out = self.transformer(x)
        transformer_out = transformer_out.transpose(0, 1)

        # Global pooling
        out = transformer_out.mean(dim=1)

        # Fully connected layers
        out = self.relu(self.fc1(out))
        out = self.dropout(out)
        out = self.relu(self.fc2(out))
        out = self.fc3(out)

        return out

# ==================================================================================
# ENHANCED ML ENGINE
# ==================================================================================

class EnhancedMLEngine:
    """
    Enhanced machine learning engine with risk integration
    """

    def __init__(self, config: dict[str, Any]):
        """Initialize ML engine"""
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Model registry
        self.models = {}
        self.scalers = {}
        self.performance_history = deque(maxlen=1000)

        # Feature engineering
        self.feature_cache = deque(maxlen=10000)
        self.feature_importance = {}

        # Online learning
        self.online_buffer = deque(maxlen=1000)
        self.update_frequency = config.get('update_frequency', 100)

        # Initialize models
        self._initialize_models()

        logger.info("Enhanced ML Engine initialized on %s", self.device)

    def _initialize_models(self):
        """Initialize all ML models"""

        # Price prediction ensemble
        self.models['price_ensemble'] = self._create_price_ensemble()

        # LSTM price predictor
        self.models['lstm_price'] = LSTMPricePredictor(
            input_dim=50, hidden_dim=128, num_layers=3
        ).to(self.device)

        # Transformer volatility model
        self.models['transformer_vol'] = TransformerVolatilityModel(
            input_dim=30, d_model=256, nhead=8
        ).to(self.device)

        # Regime classifier
        self.models['regime_classifier'] = self._create_regime_classifier()

        # Strategy selector (RL agent)
        self.models['strategy_selector'] = self._create_strategy_selector()

        # Risk estimator
        self.models['risk_estimator'] = self._create_risk_estimator()

        # Initialize scalers
        self.scalers['standard'] = StandardScaler()
        self.scalers['robust'] = RobustScaler()

    def _create_price_ensemble(self) -> VotingRegressor:
        """Create ensemble model for price prediction"""

        rf = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )

        gb = GradientBoostingRegressor(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            random_state=42
        )

        ensemble = VotingRegressor([
            ('rf', rf),
            ('gb', gb)
        ])

        return ensemble

    def _create_regime_classifier(self):
        """Create market regime classifier"""
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            min_samples_split=10,
            random_state=42,
            n_jobs=-1
        )

    def _create_strategy_selector(self):
        """Create reinforcement learning strategy selector"""
        # Simplified DQN for strategy selection
        class StrategyDQN(nn.Module):
            def __init__(self, state_dim: int = 100, action_dim: int = 26):
                super().__init__()
                self.fc1 = nn.Linear(state_dim, 256)
                self.fc2 = nn.Linear(256, 128)
                self.fc3 = nn.Linear(128, 64)
                self.fc4 = nn.Linear(64, action_dim)
                self.dropout = nn.Dropout(0.2)

            def forward(self, x):
                x = torch.relu(self.fc1(x))
                x = self.dropout(x)
                x = torch.relu(self.fc2(x))
                x = self.dropout(x)
                x = torch.relu(self.fc3(x))
                x = self.fc4(x)
                return x

        return StrategyDQN().to(self.device)

    def _create_risk_estimator(self):
        """Create risk estimation model"""
        return GradientBoostingRegressor(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=6,
            random_state=42
        )

    # ==================================================================================
    # PREDICTION METHODS
    # ==================================================================================

    def predict_price(self, features: FeatureSet,
                     horizon: PredictionHorizon = PredictionHorizon.MINUTE_5) -> MLPrediction:
        """Predict future price movement"""

        # Prepare features
        X = self._prepare_price_features(features)

        # Ensemble prediction
        if 'price_ensemble' in self.models and hasattr(self.models['price_ensemble'], 'predict'):
            ensemble_pred = self.models['price_ensemble'].predict(X.reshape(1, -1))[0]
        else:
            ensemble_pred = 0

        # LSTM prediction
        lstm_pred = self._predict_with_lstm(X)

        # Combine predictions (weighted average)
        final_prediction = 0.6 * lstm_pred + 0.4 * ensemble_pred

        # Calculate confidence
        confidence = self._calculate_prediction_confidence(
            [lstm_pred, ensemble_pred], final_prediction
        )

        # Get feature importance
        feature_importance = self._get_feature_importance('price')

        return MLPrediction(
            model_type=ModelType.PRICE_PREDICTOR,
            timestamp=datetime.now(timezone.utc),
            prediction=final_prediction,
            confidence=confidence,
            feature_importance=feature_importance,
            horizon=horizon,
            metadata={'ensemble_pred': ensemble_pred, 'lstm_pred': lstm_pred}
        )

    def predict_volatility(self, features: FeatureSet,
                          horizon: PredictionHorizon = PredictionHorizon.DAY) -> MLPrediction:
        """Predict future volatility"""

        # Prepare features
        X = self._prepare_volatility_features(features)

        # Transformer prediction
        vol_pred = self._predict_with_transformer(X)

        # Calculate realized volatility for comparison
        realized_vol = self._calculate_realized_volatility(features)

        # Adjust prediction based on current regime
        regime = self._get_current_regime(features)
        if regime == "CRISIS":
            vol_pred *= 1.5  # Increase volatility prediction in crisis
        elif regime == "LOW_VOL":
            vol_pred *= 0.8  # Decrease in low vol regime

        confidence = self._calculate_volatility_confidence(vol_pred, realized_vol)

        return MLPrediction(
            model_type=ModelType.VOLATILITY_FORECASTER,
            timestamp=datetime.now(timezone.utc),
            prediction=vol_pred,
            confidence=confidence,
            feature_importance=self._get_feature_importance('volatility'),
            horizon=horizon,
            metadata={'realized_vol': realized_vol, 'regime': regime}
        )

    def classify_regime(self, features: FeatureSet) -> MLPrediction:
        """Classify current market regime"""

        # Prepare features
        X = self._prepare_regime_features(features)

        # Get regime probabilities
        if hasattr(self.models['regime_classifier'], 'predict_proba'):
            regime_probs = self.models['regime_classifier'].predict_proba(X.reshape(1, -1))[0]
            regime_classes = self.models['regime_classifier'].classes_

            # Get most likely regime
            regime_idx = np.argmax(regime_probs)
            regime = regime_classes[regime_idx] if regime_idx < len(regime_classes) else "UNKNOWN"
            confidence = regime_probs[regime_idx]

            # Create probability distribution
            regime_dist = {str(cls): float(prob) for cls, prob in zip(regime_classes, regime_probs, strict=False)}  # noqa: E501
        else:
            regime = "NORMAL"
            confidence = 0.5
            regime_dist = {"NORMAL": 0.5}

        return MLPrediction(
            model_type=ModelType.REGIME_CLASSIFIER,
            timestamp=datetime.now(timezone.utc),
            prediction=regime,
            confidence=confidence,
            feature_importance=self._get_feature_importance('regime'),
            horizon=PredictionHorizon.HOUR,
            metadata={'probabilities': regime_dist}
        )

    def select_optimal_strategies(self, state: dict[str, Any],
                                 available_strategies: list[str]) -> MLPrediction:
        """Select optimal strategies using reinforcement learning"""

        # Prepare state features
        state_tensor = self._prepare_state_features(state)

        # Get Q-values for all strategies
        with torch.no_grad():
            q_values = self.models['strategy_selector'](state_tensor)

        # Convert to numpy for processing
        q_values_np = q_values.cpu().numpy()[0]

        # Get top strategies
        strategy_scores = {}
        for i, strategy in enumerate(available_strategies[:len(q_values_np)]):
            strategy_scores[strategy] = float(q_values_np[i])

        # Sort by score
        sorted_strategies = sorted(strategy_scores.items(), key=lambda x: x[1], reverse=True)

        # Select top N strategies based on risk tolerance
        risk_tolerance = state.get('risk_tolerance', 'moderate')
        if risk_tolerance == 'conservative':
            n_strategies = 3
        elif risk_tolerance == 'moderate':
            n_strategies = 5
        else:  # aggressive
            n_strategies = 8

        selected = [s[0] for s in sorted_strategies[:n_strategies]]

        # Calculate confidence based on Q-value spread
        confidence = self._calculate_strategy_confidence(q_values_np)

        return MLPrediction(
            model_type=ModelType.STRATEGY_SELECTOR,
            timestamp=datetime.now(timezone.utc),
            prediction=selected,
            confidence=confidence,
            feature_importance={},
            horizon=PredictionHorizon.DAY,
            metadata={'all_scores': strategy_scores, 'risk_tolerance': risk_tolerance}
        )

    def estimate_risk(self, portfolio: dict[str, Any],
                     market_conditions: dict[str, Any]) -> MLPrediction:
        """Estimate portfolio risk using ML"""

        # Prepare risk features
        X = self._prepare_risk_features(portfolio, market_conditions)

        # Predict risk metrics
        if hasattr(self.models['risk_estimator'], 'predict'):
            var_estimate = self.models['risk_estimator'].predict(X.reshape(1, -1))[0]
        else:
            var_estimate = 0.05  # Default 5% VaR

        # Adjust for tail risk
        tail_risk_score = market_conditions.get('tail_risk_score', 0)
        if tail_risk_score > 70:
            var_estimate *= 1.3  # Increase risk estimate

        # Calculate additional risk metrics
        risk_metrics = {
            'var_99': var_estimate,
            'expected_shortfall': var_estimate * 1.5,
            'max_drawdown_estimate': var_estimate * 2.5,
            'correlation_risk': self._estimate_correlation_risk(portfolio),
            'concentration_risk': self._estimate_concentration_risk(portfolio)
        }

        confidence = self._calculate_risk_confidence(risk_metrics, market_conditions)

        return MLPrediction(
            model_type=ModelType.RISK_ESTIMATOR,
            timestamp=datetime.now(timezone.utc),
            prediction=risk_metrics,
            confidence=confidence,
            feature_importance=self._get_feature_importance('risk'),
            horizon=PredictionHorizon.DAY,
            metadata={'tail_risk_adjusted': tail_risk_score > 70}
        )

    def optimize_entry_timing(self, strategy: str, market_data: dict[str, Any]) -> MLPrediction:
        """Optimize entry timing for a strategy"""

        # Analyze multiple timeframes
        short_term = self._analyze_short_term_entry(market_data)
        medium_term = self._analyze_medium_term_entry(market_data)

        # Calculate entry score
        entry_score = 0.6 * short_term['score'] + 0.4 * medium_term['score']

        # Determine entry signal
        if entry_score > 0.7:
            signal = "STRONG_ENTRY"
        elif entry_score > 0.5:
            signal = "ENTRY"
        elif entry_score > 0.3:
            signal = "WEAK_ENTRY"
        else:
            signal = "NO_ENTRY"

        # Calculate optimal position size
        position_size = self._calculate_optimal_position_size(
            strategy, entry_score, market_data
        )

        entry_details = {
            'signal': signal,
            'score': entry_score,
            'position_size': position_size,
            'stop_loss': self._calculate_stop_loss(strategy, market_data),
            'take_profit': self._calculate_take_profit(strategy, market_data),
            'timeframe_analysis': {
                'short_term': short_term,
                'medium_term': medium_term
            }
        }

        return MLPrediction(
            model_type=ModelType.ENTRY_OPTIMIZER,
            timestamp=datetime.now(timezone.utc),
            prediction=entry_details,
            confidence=entry_score,
            feature_importance={},
            horizon=PredictionHorizon.MINUTE_5,
            metadata={'strategy': strategy}
        )

    # ==================================================================================
    # ONLINE LEARNING
    # ==================================================================================

    def update_online(self, features: FeatureSet, actual_outcome: float,
                     model_type: ModelType):
        """Update models with new data (online learning)"""

        # Add to buffer
        self.online_buffer.append({
            'features': features,
            'outcome': actual_outcome,
            'model_type': model_type,
            'timestamp': datetime.now(timezone.utc)
        })

        # Check if update needed
        if len(self.online_buffer) >= self.update_frequency:
            self._perform_online_update(model_type)

    def _perform_online_update(self, model_type: ModelType):
        """Perform online model update"""

        # Get relevant data from buffer
        relevant_data = [d for d in self.online_buffer if d['model_type'] == model_type]

        if len(relevant_data) < 10:
            return

        # Prepare training data
        X = np.array([self._extract_features(d['features'], model_type)
                     for d in relevant_data])
        y = np.array([d['outcome'] for d in relevant_data])

        # Update appropriate model
        if model_type == ModelType.PRICE_PREDICTOR:
            self._update_price_model(X, y)
        elif model_type == ModelType.VOLATILITY_FORECASTER:
            self._update_volatility_model(X, y)
        elif model_type == ModelType.RISK_ESTIMATOR:
            self._update_risk_model(X, y)

        logger.info("Online update completed for %s", model_type.value)

    def _update_price_model(self, X: np.ndarray, y: np.ndarray):
        """Update price prediction model"""

        # Partial fit for ensemble components (if they support it)
        if hasattr(self.models['price_ensemble'], 'partial_fit'):
            self.models['price_ensemble'].partial_fit(X, y)

        # Fine-tune LSTM with new data
        self._finetune_lstm(X, y)

    def _update_volatility_model(self, X: np.ndarray, y: np.ndarray):
        """Update volatility model"""

        # Fine-tune transformer
        self._finetune_transformer(X, y)

    def _update_risk_model(self, X: np.ndarray, y: np.ndarray):
        """Update risk estimation model"""

        if hasattr(self.models['risk_estimator'], 'partial_fit'):
            self.models['risk_estimator'].partial_fit(X, y)

    # ==================================================================================
    # REINFORCEMENT LEARNING
    # ==================================================================================

    def train_strategy_selector(self, episodes: int = 100):
        """Train the strategy selector using reinforcement learning"""

        optimizer = optim.Adam(self.models['strategy_selector'].parameters(), lr=0.001)
        memory = deque(maxlen=10000)

        for episode in range(episodes):
            # Simulate episode
            state = self._get_initial_state()
            total_reward = 0

            for _step in range(100):  # Max steps per episode
                # Select action (strategy)
                action = self._select_action(state)

                # Execute and get reward
                next_state, reward, done = self._step_environment(state, action)

                # Store transition
                memory.append((state, action, reward, next_state, done))

                # Update model
                if len(memory) > 32:
                    self._update_dqn(memory, optimizer)

                total_reward += reward
                state = next_state

                if done:
                    break

            if episode % 10 == 0:
                logger.info(f"Episode {episode}, Total Reward: {total_reward:.2f}")

    def _select_action(self, state: np.ndarray, epsilon: float = 0.1) -> int:
        """Select action using epsilon-greedy policy"""

        if np.random.random() < epsilon:
            return np.random.randint(0, 26)  # Random strategy
        else:
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.models['strategy_selector'](state_tensor)
            return q_values.argmax().item()

    def _update_dqn(self, memory: deque, optimizer: optim.Optimizer):
        """Update DQN using experience replay"""

        batch_size = 32
        batch = np.random.choice(len(memory), batch_size, replace=False)

        states = []
        actions = []
        rewards = []
        next_states = []
        dones = []

        for idx in batch:
            s, a, r, ns, d = memory[idx]
            states.append(s)
            actions.append(a)
            rewards.append(r)
            next_states.append(ns)
            dones.append(d)

        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        rewards = torch.FloatTensor(rewards).to(self.device)
        next_states = torch.FloatTensor(next_states).to(self.device)
        dones = torch.FloatTensor(dones).to(self.device)

        current_q = self.models['strategy_selector'](states).gather(1, actions.unsqueeze(1))
        next_q = self.models['strategy_selector'](next_states).max(1)[0].detach()
        target_q = rewards + 0.99 * next_q * (1 - dones)

        loss = nn.MSELoss()(current_q.squeeze(), target_q)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

    # ==================================================================================
    # HELPER METHODS
    # ==================================================================================

    def _prepare_price_features(self, features: FeatureSet) -> np.ndarray:
        """Prepare features for price prediction"""

        all_features = []

        if features.price_features is not None:
            all_features.append(features.price_features.flatten())
        if features.volume_features is not None:
            all_features.append(features.volume_features.flatten())
        if features.technical_features is not None:
            all_features.append(features.technical_features.flatten())

        return np.concatenate(all_features)

    def _prepare_volatility_features(self, features: FeatureSet) -> np.ndarray:
        """Prepare features for volatility prediction"""

        all_features = []

        if features.price_features is not None:
            # Calculate returns
            returns = np.diff(features.price_features) / features.price_features[:-1]
            all_features.append(returns.flatten())
        if features.volume_features is not None:
            all_features.append(features.volume_features.flatten())
        if features.greek_features is not None:
            all_features.append(features.greek_features.flatten())

        return np.concatenate(all_features)

    def _prepare_regime_features(self, features: FeatureSet) -> np.ndarray:
        """Prepare features for regime classification"""

        all_features = []

        # Add all available features
        for feat_array in [features.price_features, features.volume_features,
                          features.technical_features, features.market_microstructure]:
            if feat_array is not None:
                all_features.append(feat_array.flatten())

        return np.concatenate(all_features)

    def _prepare_state_features(self, state: dict[str, Any]) -> torch.Tensor:
        """Prepare state features for RL"""

        features = []

        # Market conditions
        features.append(state.get('spy_price', 450))
        features.append(state.get('vix', 20))
        features.append(state.get('volume', 100000000))

        # Portfolio state
        features.append(state.get('portfolio_value', 1000000))
        features.append(state.get('current_pnl', 0))
        features.append(state.get('positions_count', 0))

        # Risk metrics
        features.append(state.get('current_var', 0.05))
        features.append(state.get('tail_risk_score', 30))

        # Pad to expected dimension
        while len(features) < 100:
            features.append(0)

        return torch.FloatTensor(features[:100]).unsqueeze(0).to(self.device)

    def _prepare_risk_features(self, portfolio: dict[str, Any],
                              market_conditions: dict[str, Any]) -> np.ndarray:
        """Prepare features for risk estimation"""

        features = []

        # Portfolio features
        features.append(portfolio.get('total_value', 0))
        features.append(portfolio.get('positions_count', 0))
        features.append(portfolio.get('leverage', 1.0))
        features.append(portfolio.get('concentration', 0))

        # Market features
        features.append(market_conditions.get('volatility', 0.15))
        features.append(market_conditions.get('correlation', 0.5))
        features.append(market_conditions.get('volume', 100000000))

        return np.array(features)

    def _predict_with_lstm(self, features: np.ndarray) -> float:
        """Make prediction with LSTM model"""

        # Reshape for LSTM (batch, seq_len, features)
        seq_len = 20
        if len(features) < seq_len * 10:
            # Pad if necessary
            features = np.pad(features, (0, seq_len * 10 - len(features)))

        features_reshaped = features[:seq_len * 10].reshape(1, seq_len, -1)

        # Convert to tensor
        x = torch.FloatTensor(features_reshaped).to(self.device)

        # Predict
        with torch.no_grad():
            prediction = self.models['lstm_price'](x)

        return prediction.cpu().numpy()[0, 0]

    def _predict_with_transformer(self, features: np.ndarray) -> float:
        """Make prediction with Transformer model"""

        # Reshape for Transformer
        seq_len = 20
        if len(features) < seq_len * 10:
            features = np.pad(features, (0, seq_len * 10 - len(features)))

        features_reshaped = features[:seq_len * 10].reshape(1, seq_len, -1)

        # Convert to tensor
        x = torch.FloatTensor(features_reshaped).to(self.device)

        # Predict
        with torch.no_grad():
            prediction = self.models['transformer_vol'](x)

        return prediction.cpu().numpy()[0, 0]

    def _calculate_prediction_confidence(self, predictions: list[float],
                                        final_pred: float) -> float:
        """Calculate confidence score for prediction"""

        if not predictions:
            return 0.5

        # Calculate standard deviation of predictions
        std = np.std(predictions)

        # Lower std = higher confidence
        confidence = np.exp(-std * 2)

        return min(max(confidence, 0.1), 0.95)

    def _calculate_volatility_confidence(self, predicted: float, realized: float) -> float:
        """Calculate confidence for volatility prediction"""

        # Compare with realized volatility
        error = abs(predicted - realized) / realized if realized > 0 else 0.5

        confidence = np.exp(-error * 3)

        return min(max(confidence, 0.1), 0.95)

    def _calculate_strategy_confidence(self, q_values: np.ndarray) -> float:
        """Calculate confidence for strategy selection"""

        # Softmax to get probabilities
        exp_q = np.exp(q_values - np.max(q_values))
        probs = exp_q / exp_q.sum()

        # Entropy as measure of confidence
        entropy = -np.sum(probs * np.log(probs + 1e-10))

        # Lower entropy = higher confidence
        confidence = np.exp(-entropy)

        return min(max(confidence, 0.1), 0.95)

    def _calculate_risk_confidence(self, risk_metrics: dict[str, float],
                                  market_conditions: dict[str, Any]) -> float:
        """Calculate confidence for risk estimation"""

        # Base confidence on market regime
        regime = market_conditions.get('regime', 'NORMAL')

        if regime == 'NORMAL':
            base_confidence = 0.8
        elif regime in ['TRENDING', 'RANGE_BOUND']:
            base_confidence = 0.7
        else:  # HIGH_VOL, CRISIS
            base_confidence = 0.5

        # Adjust based on data quality
        data_quality = market_conditions.get('data_quality', 1.0)

        return base_confidence * data_quality

    def _get_feature_importance(self, model_type: str) -> dict[str, float]:
        """Get feature importance for model"""

        # Placeholder - would extract from trained models
        if model_type == 'price':
            return {
                'price_lag1': 0.25,
                'volume': 0.15,
                'rsi': 0.10,
                'macd': 0.08,
                'volatility': 0.12
            }
        elif model_type == 'volatility':
            return {
                'realized_vol': 0.30,
                'vix': 0.25,
                'gamma': 0.15,
                'volume': 0.10
            }
        else:
            return {}

    def _calculate_realized_volatility(self, features: FeatureSet) -> float:
        """Calculate realized volatility from features"""

        if features.price_features is None or len(features.price_features) < 2:
            return 0.15  # Default

        returns = np.diff(features.price_features) / features.price_features[:-1]
        return np.std(returns) * np.sqrt(252)

    def _get_current_regime(self, features: FeatureSet) -> str:
        """Get current market regime"""

        # Use regime classifier
        regime_pred = self.classify_regime(features)
        return regime_pred.prediction

    def _analyze_short_term_entry(self, market_data: dict[str, Any]) -> dict[str, float]:
        """Analyze short-term entry conditions"""

        score = 0.5

        # Check momentum
        if market_data.get('momentum', 0) > 0:
            score += 0.2

        # Check RSI
        rsi = market_data.get('rsi', 50)
        if 30 < rsi < 70:
            score += 0.1

        return {'score': score, 'timeframe': '5min'}

    def _analyze_medium_term_entry(self, market_data: dict[str, Any]) -> dict[str, float]:
        """Analyze medium-term entry conditions"""

        score = 0.5

        # Check trend
        if market_data.get('trend', 'neutral') == 'up':
            score += 0.2

        # Check support/resistance
        if market_data.get('near_support', False):
            score += 0.15

        return {'score': score, 'timeframe': '1hour'}

    def _calculate_optimal_position_size(self, strategy: str, entry_score: float,
                                        market_data: dict[str, Any]) -> float:
        """Calculate optimal position size"""

        base_size = 0.02  # 2% of portfolio

        # Adjust for entry score
        size_multiplier = entry_score * 1.5

        # Adjust for volatility
        volatility = market_data.get('volatility', 0.15)
        if volatility > 0.25:
            size_multiplier *= 0.5
        elif volatility < 0.10:
            size_multiplier *= 1.2

        return base_size * size_multiplier

    def _calculate_stop_loss(self, strategy: str, market_data: dict[str, Any]) -> float:
        """Calculate stop loss level"""

        atr = market_data.get('atr', 2.0)
        return market_data.get('current_price', 450) - 2 * atr

    def _calculate_take_profit(self, strategy: str, market_data: dict[str, Any]) -> float:
        """Calculate take profit level"""

        atr = market_data.get('atr', 2.0)
        return market_data.get('current_price', 450) + 3 * atr

    def _estimate_correlation_risk(self, portfolio: dict[str, Any]) -> float:
        """Estimate portfolio correlation risk"""

        # Simplified - would use actual correlation matrix
        positions = portfolio.get('positions', [])
        if len(positions) < 2:
            return 0

        # Assume higher correlation with more positions in same sector
        return min(len(positions) * 0.1, 0.9)

    def _estimate_concentration_risk(self, portfolio: dict[str, Any]) -> float:
        """Estimate portfolio concentration risk"""

        positions = portfolio.get('positions', [])
        if not positions:
            return 0

        # Calculate Herfindahl index
        total_value = sum(p.get('value', 0) for p in positions)
        if total_value == 0:
            return 0

        hhi = sum((p.get('value', 0) / total_value) ** 2 for p in positions)

        return hhi

    def _extract_features(self, feature_set: FeatureSet, model_type: ModelType) -> np.ndarray:
        """Extract features for specific model type"""

        if model_type == ModelType.PRICE_PREDICTOR:
            return self._prepare_price_features(feature_set)
        elif model_type == ModelType.VOLATILITY_FORECASTER:
            return self._prepare_volatility_features(feature_set)
        elif model_type == ModelType.RISK_ESTIMATOR:
            # Need to extract risk features differently
            return np.random.randn(10)  # Placeholder
        else:
            return np.array([])

    def _finetune_lstm(self, X: np.ndarray, y: np.ndarray):
        """Fine-tune LSTM model with new data"""

        # Create dataset
        dataset = TensorDataset(
            torch.FloatTensor(X.reshape(-1, 20, X.shape[1]//20)),
            torch.FloatTensor(y)
        )
        dataloader = DataLoader(dataset, batch_size=16, shuffle=True)

        # Fine-tune for a few epochs
        optimizer = optim.Adam(self.models['lstm_price'].parameters(), lr=0.0001)
        criterion = nn.MSELoss()

        self.models['lstm_price'].train()
        for _epoch in range(3):
            for batch_x, batch_y in dataloader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)

                optimizer.zero_grad()
                outputs = self.models['lstm_price'](batch_x)
                loss = criterion(outputs.squeeze(), batch_y)
                loss.backward()
                optimizer.step()

        self.models['lstm_price'].eval()

    def _finetune_transformer(self, X: np.ndarray, y: np.ndarray):
        """Fine-tune Transformer model with new data"""

        # Similar to LSTM fine-tuning
        dataset = TensorDataset(
            torch.FloatTensor(X.reshape(-1, 20, X.shape[1]//20)),
            torch.FloatTensor(y)
        )
        dataloader = DataLoader(dataset, batch_size=16, shuffle=True)

        optimizer = optim.Adam(self.models['transformer_vol'].parameters(), lr=0.0001)
        criterion = nn.MSELoss()

        self.models['transformer_vol'].train()
        for _epoch in range(3):
            for batch_x, batch_y in dataloader:
                batch_x, batch_y = batch_x.to(self.device), batch_y.to(self.device)

                optimizer.zero_grad()
                outputs = self.models['transformer_vol'](batch_x)
                loss = criterion(outputs.squeeze(), batch_y)
                loss.backward()
                optimizer.step()

        self.models['transformer_vol'].eval()

    def _get_initial_state(self) -> np.ndarray:
        """Get initial state for RL training"""
        return np.random.randn(100)

    def _step_environment(self, state: np.ndarray, action: int) -> tuple[np.ndarray, float, bool]:
        """Step the environment for RL training"""

        # Simulate environment step
        next_state = state + np.random.randn(100) * 0.1

        # Calculate reward (simplified)
        reward = np.random.randn() * 10

        # Check if done
        done = np.random.random() < 0.01

        return next_state, reward, done

    # ==================================================================================
    # MODEL PERSISTENCE
    # ==================================================================================

    def save_models(self, path: str):
        """Save all models to disk"""

        # Save PyTorch models
        torch.save(self.models['lstm_price'].state_dict(), f"{path}/lstm_price.pt")
        torch.save(self.models['transformer_vol'].state_dict(), f"{path}/transformer_vol.pt")
        torch.save(self.models['strategy_selector'].state_dict(), f"{path}/strategy_selector.pt")

        # Save sklearn models
        joblib.dump(self.models['price_ensemble'], f"{path}/price_ensemble.pkl")
        joblib.dump(self.models['regime_classifier'], f"{path}/regime_classifier.pkl")
        joblib.dump(self.models['risk_estimator'], f"{path}/risk_estimator.pkl")

        # Save scalers
        joblib.dump(self.scalers, f"{path}/scalers.pkl")

        logger.info("Models saved to %s", path)

    def load_models(self, path: str):
        """Load models from disk"""

        # Load PyTorch models
        self.models['lstm_price'].load_state_dict(torch.load(f"{path}/lstm_price.pt"))
        self.models['transformer_vol'].load_state_dict(torch.load(f"{path}/transformer_vol.pt"))
        self.models['strategy_selector'].load_state_dict(torch.load(f"{path}/strategy_selector.pt"))

        # Load sklearn models
        self.models['price_ensemble'] = joblib.load(f"{path}/price_ensemble.pkl")
        self.models['regime_classifier'] = joblib.load(f"{path}/regime_classifier.pkl")
        self.models['risk_estimator'] = joblib.load(f"{path}/risk_estimator.pkl")

        # Load scalers
        self.scalers = joblib.load(f"{path}/scalers.pkl")

        logger.info("Models loaded from %s", path)

# ==================================================================================
# FACTORY FUNCTION
# ==================================================================================

def create_enhanced_ml_engine(config: dict[str, Any]) -> EnhancedMLEngine:
    """Factory function to create enhanced ML engine"""
    return EnhancedMLEngine(config)

# ==================================================================================
# MAIN EXECUTION
# ==================================================================================

if __name__ == "__main__":
    # Example usage
    config = {
        'update_frequency': 100,
        'device': 'cuda' if torch.cuda.is_available() else 'cpu'
    }

    # Create ML engine
    ml_engine = create_enhanced_ml_engine(config)

    # Create sample features
    sample_features = FeatureSet(
        timestamp=datetime.now(timezone.utc),
        price_features=np.random.randn(100),
        volume_features=np.random.randn(50),
        technical_features=np.random.randn(30),
        greek_features=np.random.randn(20),
        market_microstructure=np.random.randn(25)
    )

    # Make predictions
    price_pred = ml_engine.predict_price(sample_features)

    vol_pred = ml_engine.predict_volatility(sample_features)

    regime_pred = ml_engine.classify_regime(sample_features)

    # Select strategies
    state = {
        'spy_price': 450,
        'vix': 20,
        'portfolio_value': 1000000,
        'risk_tolerance': 'moderate'
    }

    strategies = ml_engine.select_optimal_strategies(
        state,
        [f"D{i:02d}" for i in range(1, 27)]
    )

    # Save models
    # ml_engine.save_models("./models")
