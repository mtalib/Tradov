#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovF_Analysis
Module: TradovF22_MLPrediction.py
Purpose: Machine Learning prediction engine for price direction and volatility

Author: Claude (Maestro)
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    This module provides machine learning capabilities for options trading:
    - Price direction prediction using LSTM/GRU neural networks
    - Volatility regime classification
    - Optimal strike selection recommendations
    - Feature engineering for options-specific signals

    Based on research showing:
    - End-to-end deep learning achieved 355% returns with 3.05 Sharpe ratio
    - LSTM networks show ~82% accuracy in market movement prediction
    - Neural networks outperform traditional models for stock forecasting

References:
    - Deep Learning for Options Trading (ACM ICAIF 2024)
    - LSTM for Option Price Movement (MDPI 2024)
    - Stock Forecasting Neural Networks Review (ScienceDirect 2024)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import json
import inspect
import warnings
from typing import Any
from enum import Enum
from datetime import datetime, UTC
from dataclasses import dataclass, field
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
import joblib

# Deep Learning (optional - graceful degradation)
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    warnings.warn("PyTorch not available - using sklearn fallback models", stacklevel=2)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
MODEL_CACHE_DIR = "models/ml_cache"
DEFAULT_SEQUENCE_LENGTH = 60  # 60 bars for LSTM input
DEFAULT_PREDICTION_HORIZON = 5  # Predict 5 bars ahead
RETRAIN_INTERVAL_HOURS = 24
MIN_TRAINING_SAMPLES = 1000

# ==============================================================================
# MODULE LOGGER
# ==============================================================================
logger = TradovLogger.get_logger(__name__)


def _secure_torch_load(
    model_path: str,
    *,
    map_location: Any = None,
) -> Any:
    """Load a PyTorch state dict with weights-only deserialization."""
    if not HAS_TORCH:
        raise RuntimeError("PyTorch is not available")

    if "weights_only" not in inspect.signature(torch.load).parameters:
        raise RuntimeError(
            "Secure model loading requires a PyTorch version with weights_only support"
        )

    load_kwargs: dict[str, Any] = {"weights_only": True}
    if map_location is not None:
        load_kwargs["map_location"] = map_location

    return torch.load(model_path, **load_kwargs)  # nosec B614


# ==============================================================================
# ENUMS
# ==============================================================================
class PredictionDirection(Enum):
    """Price direction prediction."""
    STRONG_UP = "strong_up"
    UP = "up"
    NEUTRAL = "neutral"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


class VolatilityRegime(Enum):
    """Volatility regime classification."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


class ModelType(Enum):
    """ML model types."""
    LSTM = "lstm"
    GRU = "gru"
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOSTING = "gradient_boosting"
    ENSEMBLE = "ensemble"


# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class PredictionResult:
    """Result of a price direction prediction."""
    symbol: str
    timestamp: datetime
    direction: PredictionDirection
    confidence: float  # 0-1
    predicted_return: float  # Expected % return
    prediction_horizon: int  # Bars ahead
    model_type: ModelType
    features_used: list[str] = field(default_factory=list)

    @property
    def is_actionable(self) -> bool:
        """Check if prediction confidence meets threshold."""
        return self.confidence >= 0.6 and self.direction != PredictionDirection.NEUTRAL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "direction": self.direction.value,
            "confidence": self.confidence,
            "predicted_return": self.predicted_return,
            "prediction_horizon": self.prediction_horizon,
            "model_type": self.model_type.value,
            "is_actionable": self.is_actionable,
        }


@dataclass
class VolatilityPrediction:
    """Volatility regime prediction."""
    symbol: str
    timestamp: datetime
    current_regime: VolatilityRegime
    predicted_regime: VolatilityRegime
    regime_probability: dict[str, float]
    predicted_iv: float  # Predicted implied volatility
    iv_percentile: float  # IV rank/percentile

    @property
    def regime_change_expected(self) -> bool:
        """Check if regime change is expected."""
        return self.current_regime != self.predicted_regime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_regime": self.current_regime.value,
            "predicted_regime": self.predicted_regime.value,
            "regime_probability": self.regime_probability,
            "predicted_iv": self.predicted_iv,
            "iv_percentile": self.iv_percentile,
            "regime_change_expected": self.regime_change_expected,
        }


@dataclass
class StrikeRecommendation:
    """Optimal strike selection recommendation."""
    symbol: str
    timestamp: datetime
    underlying_price: float
    recommended_strikes: dict[str, float]  # call/put -> strike
    recommended_expiry: str
    expected_probability_of_profit: float
    strategy_type: str  # credit_spread, iron_condor, etc.
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "underlying_price": self.underlying_price,
            "recommended_strikes": self.recommended_strikes,
            "recommended_expiry": self.recommended_expiry,
            "expected_pop": self.expected_probability_of_profit,
            "strategy_type": self.strategy_type,
            "rationale": self.rationale,
        }


@dataclass
class ModelMetrics:
    """Model performance metrics."""
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    training_date: datetime = field(default_factory=lambda: datetime.now(UTC))
    samples_used: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "training_date": self.training_date.isoformat(),
            "samples_used": self.samples_used,
        }


# ==============================================================================
# NEURAL NETWORK MODELS (PyTorch)
# ==============================================================================
if HAS_TORCH:
    class LSTMModel(nn.Module):
        """LSTM model for price direction prediction."""

        def __init__(
            self,
            input_size: int,
            hidden_size: int = 128,
            num_layers: int = 2,
            num_classes: int = 3,
            dropout: float = 0.2
        ):
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.lstm = nn.LSTM(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0
            )

            self.fc1 = nn.Linear(hidden_size, 64)
            self.fc2 = nn.Linear(64, num_classes)
            self.dropout = nn.Dropout(dropout)
            self.relu = nn.ReLU()

        def forward(self, x):
            # LSTM forward
            h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
            c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)

            out, _ = self.lstm(x, (h0, c0))

            # Take last timestep output
            out = out[:, -1, :]

            # Fully connected layers
            out = self.dropout(self.relu(self.fc1(out)))
            out = self.fc2(out)

            return out

    class GRUModel(nn.Module):
        """GRU model for price direction prediction."""

        def __init__(
            self,
            input_size: int,
            hidden_size: int = 128,
            num_layers: int = 2,
            num_classes: int = 3,
            dropout: float = 0.2
        ):
            super().__init__()
            self.hidden_size = hidden_size
            self.num_layers = num_layers

            self.gru = nn.GRU(
                input_size=input_size,
                hidden_size=hidden_size,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0
            )

            self.fc1 = nn.Linear(hidden_size, 64)
            self.fc2 = nn.Linear(64, num_classes)
            self.dropout = nn.Dropout(dropout)
            self.relu = nn.ReLU()

        def forward(self, x):
            h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
            out, _ = self.gru(x, h0)
            out = out[:, -1, :]
            out = self.dropout(self.relu(self.fc1(out)))
            out = self.fc2(out)
            return out

    class TimeSeriesDataset(Dataset):
        """PyTorch Dataset for time series data."""

        def __init__(self, X: np.ndarray, y: np.ndarray):
            self.X = torch.FloatTensor(X)
            self.y = torch.LongTensor(y)

        def __len__(self):
            return len(self.X)

        def __getitem__(self, idx):
            return self.X[idx], self.y[idx]


# ==============================================================================
# FEATURE ENGINEERING
# ==============================================================================
class FeatureEngineer:
    """Feature engineering for ML models."""

    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_names: list[str] = []

    def create_features(
        self,
        df: pd.DataFrame,
        include_technicals: bool = True,
        include_options: bool = True,
        include_sentiment: bool = False
    ) -> pd.DataFrame:
        """
        Create features for ML model input.

        Args:
            df: DataFrame with OHLCV data
            include_technicals: Include technical indicators
            include_options: Include options-specific features
            include_sentiment: Include sentiment features (if available)

        Returns:
            DataFrame with engineered features
        """
        features = df.copy()

        # Basic price features
        features['returns'] = features['close'].pct_change()
        features['log_returns'] = np.log(features['close'] / features['close'].shift(1))
        features['high_low_range'] = (features['high'] - features['low']) / features['close']
        features['close_open_range'] = (features['close'] - features['open']) / features['open']

        # Volume features
        if 'volume' in features.columns:
            features['volume_ma5'] = features['volume'].rolling(5).mean()
            features['volume_ma20'] = features['volume'].rolling(20).mean()
            features['volume_ratio'] = features['volume'] / features['volume_ma20']
            features['volume_change'] = features['volume'].pct_change()

        if include_technicals:
            features = self._add_technical_features(features)

        if include_options and 'iv' in features.columns:
            features = self._add_options_features(features)

        # Lagged features
        for lag in [1, 2, 3, 5, 10]:
            features[f'return_lag_{lag}'] = features['returns'].shift(lag)

        # Rolling statistics
        for window in [5, 10, 20]:
            features[f'return_mean_{window}'] = features['returns'].rolling(window).mean()
            features[f'return_std_{window}'] = features['returns'].rolling(window).std()
            features[f'return_skew_{window}'] = features['returns'].rolling(window).skew()

        # Drop NaN values
        features = features.dropna()

        # Store feature names
        self.feature_names = [c for c in features.columns if c not in
                             ['open', 'high', 'low', 'close', 'volume', 'date', 'datetime']]

        return features

    def _add_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicator features."""
        # Moving averages
        df['sma_5'] = df['close'].rolling(5).mean()
        df['sma_10'] = df['close'].rolling(10).mean()
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()

        # Price relative to MAs
        df['price_sma5_ratio'] = df['close'] / df['sma_5']
        df['price_sma20_ratio'] = df['close'] / df['sma_20']
        df['sma5_sma20_ratio'] = df['sma_5'] / df['sma_20']

        # RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # MACD
        ema_12 = df['close'].ewm(span=12).mean()
        ema_26 = df['close'].ewm(span=26).mean()
        df['macd'] = ema_12 - ema_26
        df['macd_signal'] = df['macd'].ewm(span=9).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']

        # Bollinger Bands
        df['bb_middle'] = df['close'].rolling(20).mean()
        bb_std = df['close'].rolling(20).std()
        df['bb_upper'] = df['bb_middle'] + 2 * bb_std
        df['bb_lower'] = df['bb_middle'] - 2 * bb_std
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])

        # ATR
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['atr'] = tr.rolling(14).mean()
        df['atr_ratio'] = df['atr'] / df['close']

        # Momentum
        df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
        df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
        df['momentum_20'] = df['close'] / df['close'].shift(20) - 1

        return df

    def _add_options_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add options-specific features."""
        # IV-based features
        if 'iv' in df.columns:
            df['iv_ma5'] = df['iv'].rolling(5).mean()
            df['iv_ma20'] = df['iv'].rolling(20).mean()
            df['iv_ratio'] = df['iv'] / df['iv_ma20']
            df['iv_change'] = df['iv'].pct_change()

            # IV percentile (rank over last 252 trading days)
            df['iv_percentile'] = df['iv'].rolling(252).apply(
                lambda x: (x.iloc[-1] > x[:-1]).sum() / len(x[:-1]) * 100
                if len(x) > 1 else 50
            )

        # Put/Call ratio features
        if 'put_call_ratio' in df.columns:
            df['pcr_ma5'] = df['put_call_ratio'].rolling(5).mean()
            df['pcr_change'] = df['put_call_ratio'].pct_change()

        # GEX features
        if 'gex' in df.columns:
            df['gex_normalized'] = df['gex'] / df['gex'].rolling(20).std()
            df['gex_positive'] = (df['gex'] > 0).astype(int)

        return df

    def prepare_sequences(
        self,
        features: pd.DataFrame,
        target_col: str = 'returns',
        sequence_length: int = DEFAULT_SEQUENCE_LENGTH,
        prediction_horizon: int = DEFAULT_PREDICTION_HORIZON
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Prepare sequences for LSTM/GRU input.

        Args:
            features: DataFrame with features
            target_col: Column to predict
            sequence_length: Number of time steps per sequence
            prediction_horizon: How many steps ahead to predict

        Returns:
            Tuple of (X sequences, y targets)
        """
        # Get feature columns
        feature_cols = [c for c in features.columns if c not in
                       ['open', 'high', 'low', 'close', 'volume', 'date', 'datetime']]

        # Scale features
        scaled_features = self.scaler.fit_transform(features[feature_cols])

        # Create target (direction)
        future_return = features[target_col].shift(-prediction_horizon)
        target = np.where(future_return > 0.001, 2,  # Up
                         np.where(future_return < -0.001, 0, 1))  # Down, Neutral

        X, y = [], []
        for i in range(sequence_length, len(scaled_features) - prediction_horizon):
            X.append(scaled_features[i - sequence_length:i])
            y.append(target[i])

        return np.array(X), np.array(y)

    def scale_features(self, df: pd.DataFrame) -> np.ndarray:
        """Scale features for prediction."""
        feature_cols = [c for c in df.columns if c in self.feature_names]
        return self.scaler.transform(df[feature_cols])


# ==============================================================================
# MAIN ML PREDICTION ENGINE
# ==============================================================================
class MLPredictionEngine:
    """
    Machine Learning prediction engine for options trading.

    Provides:
    - Price direction prediction using LSTM/GRU or ensemble methods
    - Volatility regime classification
    - Optimal strike recommendations based on predicted moves

    Example:
        >>> engine = MLPredictionEngine()
        >>> engine.train(historical_data)
        >>> prediction = engine.predict_direction("TRAD", current_data)
        >>> print(f"Direction: {prediction.direction.value}")
        >>> print(f"Confidence: {prediction.confidence:.2%}")
    """

    def __init__(
        self,
        model_type: ModelType = ModelType.ENSEMBLE,
        use_gpu: bool = False,
        model_dir: str = MODEL_CACHE_DIR
    ):
        """
        Initialize ML Prediction Engine.

        Args:
            model_type: Type of model to use
            use_gpu: Use GPU acceleration if available
            model_dir: Directory for model storage
        """
        self.model_type = model_type
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Device selection
        if use_gpu and HAS_TORCH and torch.cuda.is_available():
            self.device = torch.device("cuda")
            logger.info("Using GPU for ML predictions")
        else:
            self.device = torch.device("cpu") if HAS_TORCH else None

        # Feature engineering
        self.feature_engineer = FeatureEngineer()

        # Models
        self.direction_model = None
        self.volatility_model = None
        self.strike_model = None

        # Metrics
        self.model_metrics: dict[str, ModelMetrics] = {}
        self._last_training: datetime | None = None

        # Ensemble models (sklearn fallback)
        self.rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.gb_model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )

        logger.info("MLPredictionEngine initialized with %s model", model_type.value)

    # ==========================================================================
    # TRAINING METHODS
    # ==========================================================================

    def train(
        self,
        data: pd.DataFrame,
        symbol: str = "TRAD",
        validation_split: float = 0.2,
        epochs: int = 50,
        batch_size: int = 32
    ) -> ModelMetrics:
        """
        Train the prediction model on historical data.

        Args:
            data: Historical OHLCV data
            symbol: Symbol being trained
            validation_split: Validation set ratio
            epochs: Training epochs (for neural networks)
            batch_size: Batch size for training

        Returns:
            ModelMetrics with training results
        """
        logger.info("Training %s model for %s...", self.model_type.value, symbol)

        # Feature engineering
        features = self.feature_engineer.create_features(data)

        if len(features) < MIN_TRAINING_SAMPLES:
            raise ValueError(f"Insufficient data: {len(features)} < {MIN_TRAINING_SAMPLES}")

        # Prepare data based on model type
        if self.model_type in [ModelType.LSTM, ModelType.GRU] and HAS_TORCH:
            metrics = self._train_neural_network(
                features, symbol, validation_split, epochs, batch_size
            )
        else:
            metrics = self._train_ensemble(features, symbol, validation_split)

        self._last_training = datetime.now(UTC)
        self.model_metrics[symbol] = metrics

        # Save model
        self._save_model(symbol)

        logger.info(f"Training complete. Accuracy: {metrics.accuracy:.2%}")
        return metrics

    def _train_neural_network(
        self,
        features: pd.DataFrame,
        symbol: str,
        validation_split: float,
        epochs: int,
        batch_size: int
    ) -> ModelMetrics:
        """Train LSTM/GRU neural network."""
        # Prepare sequences
        X, y = self.feature_engineer.prepare_sequences(features)

        # Train/validation split (time-based)
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # Create datasets
        train_dataset = TimeSeriesDataset(X_train, y_train)
        val_dataset = TimeSeriesDataset(X_val, y_val)

        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=batch_size)

        # Initialize model
        input_size = X.shape[2]
        if self.model_type == ModelType.LSTM:
            self.direction_model = LSTMModel(input_size=input_size).to(self.device)
        else:
            self.direction_model = GRUModel(input_size=input_size).to(self.device)

        # Training setup
        criterion = nn.CrossEntropyLoss()
        optimizer = torch.optim.Adam(self.direction_model.parameters(), lr=0.001)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5)

        best_val_acc = 0
        best_model_state = None

        # Training loop
        for epoch in range(epochs):
            self.direction_model.train()
            train_loss = 0

            for X_batch, y_batch in train_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                optimizer.zero_grad()
                outputs = self.direction_model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()

                train_loss += loss.item()

            # Validation
            self.direction_model.eval()
            val_preds = []
            val_true = []

            with torch.no_grad():
                for X_batch, y_batch in val_loader:
                    X_batch = X_batch.to(self.device)
                    outputs = self.direction_model(X_batch)
                    _, predicted = torch.max(outputs, 1)
                    val_preds.extend(predicted.cpu().numpy())
                    val_true.extend(y_batch.numpy())

            val_acc = accuracy_score(val_true, val_preds)
            scheduler.step(1 - val_acc)

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_model_state = self.direction_model.state_dict().copy()

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs}, Loss: {train_loss:.4f}, Val Acc: {val_acc:.4f}")  # noqa: E501

        # Load best model
        if best_model_state:
            self.direction_model.load_state_dict(best_model_state)

        # Calculate final metrics
        return ModelMetrics(
            model_name=f"{self.model_type.value}_{symbol}",
            accuracy=best_val_acc,
            precision=precision_score(val_true, val_preds, average='weighted', zero_division=0),
            recall=recall_score(val_true, val_preds, average='weighted', zero_division=0),
            f1=f1_score(val_true, val_preds, average='weighted', zero_division=0),
            samples_used=len(X)
        )

    def _train_ensemble(
        self,
        features: pd.DataFrame,
        symbol: str,
        validation_split: float
    ) -> ModelMetrics:
        """Train ensemble model (Random Forest + Gradient Boosting)."""
        # Prepare features (non-sequential)
        feature_cols = self.feature_engineer.feature_names
        X = features[feature_cols].values

        # Create target
        future_return = features['returns'].shift(-DEFAULT_PREDICTION_HORIZON)
        y = np.where(future_return > 0.001, 2,
                    np.where(future_return < -0.001, 0, 1))

        # Remove NaN
        valid_idx = ~np.isnan(y)
        X = X[valid_idx[:-DEFAULT_PREDICTION_HORIZON]]
        y = y[valid_idx][:-DEFAULT_PREDICTION_HORIZON]

        # Time-based split
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # Train models
        self.rf_model.fit(X_train, y_train)
        self.gb_model.fit(X_train, y_train)

        # Ensemble predictions
        rf_preds = self.rf_model.predict(X_val)
        gb_preds = self.gb_model.predict(X_val)

        # Simple voting ensemble
        ensemble_preds = np.round((rf_preds + gb_preds) / 2).astype(int)

        # Calculate metrics
        return ModelMetrics(
            model_name=f"ensemble_{symbol}",
            accuracy=accuracy_score(y_val, ensemble_preds),
            precision=precision_score(y_val, ensemble_preds, average='weighted', zero_division=0),
            recall=recall_score(y_val, ensemble_preds, average='weighted', zero_division=0),
            f1=f1_score(y_val, ensemble_preds, average='weighted', zero_division=0),
            samples_used=len(X)
        )

    def train_volatility_model(
        self,
        data: pd.DataFrame,
        symbol: str = "TRAD"
    ) -> ModelMetrics:
        """
        Train volatility regime classifier.

        Args:
            data: Historical data with IV column
            symbol: Symbol being trained

        Returns:
            ModelMetrics for volatility model
        """
        logger.info("Training volatility model for %s...", symbol)

        # Prepare features
        features = self.feature_engineer.create_features(data, include_options=True)

        if 'iv' not in features.columns:
            # Calculate realized volatility as proxy
            features['iv'] = features['returns'].rolling(20).std() * np.sqrt(252)

        # Create regime labels
        iv_percentile = features['iv'].rolling(252).apply(
            lambda x: (x.iloc[-1] > x[:-1]).sum() / len(x[:-1]) * 100
            if len(x) > 1 else 50
        )

        # Classify regimes
        regimes = np.where(iv_percentile < 25, 0,  # Low
                          np.where(iv_percentile < 50, 1,  # Normal
                          np.where(iv_percentile < 75, 2, 3)))  # High, Extreme

        # Train Random Forest for volatility
        feature_cols = [c for c in self.feature_engineer.feature_names
                       if c in features.columns]
        X = features[feature_cols].dropna().values
        y = regimes[features[feature_cols].dropna().index]

        # Remove any remaining NaN
        valid_mask = ~np.isnan(y)
        X = X[valid_mask]
        y = y[valid_mask].astype(int)

        # Split and train
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        self.volatility_model = RandomForestClassifier(
            n_estimators=50, max_depth=8, random_state=42
        )
        self.volatility_model.fit(X_train, y_train)

        val_preds = self.volatility_model.predict(X_val)

        metrics = ModelMetrics(
            model_name=f"volatility_{symbol}",
            accuracy=accuracy_score(y_val, val_preds),
            precision=precision_score(y_val, val_preds, average='weighted', zero_division=0),
            recall=recall_score(y_val, val_preds, average='weighted', zero_division=0),
            f1=f1_score(y_val, val_preds, average='weighted', zero_division=0),
            samples_used=len(X)
        )

        logger.info(f"Volatility model trained. Accuracy: {metrics.accuracy:.2%}")
        return metrics

    # ==========================================================================
    # PREDICTION METHODS
    # ==========================================================================

    def predict_direction(
        self,
        symbol: str,
        data: pd.DataFrame,
        prediction_horizon: int = DEFAULT_PREDICTION_HORIZON
    ) -> PredictionResult:
        """
        Predict price direction.

        Args:
            symbol: Stock symbol
            data: Recent OHLCV data (at least sequence_length bars)
            prediction_horizon: How many bars ahead to predict

        Returns:
            PredictionResult with direction and confidence
        """
        try:
            # Prepare features
            features = self.feature_engineer.create_features(data)

            if self.model_type in [ModelType.LSTM, ModelType.GRU] and HAS_TORCH:
                prediction = self._predict_neural_network(symbol, features)
            else:
                prediction = self._predict_ensemble(symbol, features)

            # Determine direction from class
            direction_map = {
                0: PredictionDirection.DOWN,
                1: PredictionDirection.NEUTRAL,
                2: PredictionDirection.UP
            }

            # Calculate confidence from probabilities
            confidence = max(prediction['probabilities'])

            # Estimate expected return
            expected_return = self._estimate_expected_return(
                prediction['class'], confidence, features
            )

            # Enhance with strong signals
            if confidence > 0.7:
                if prediction['class'] == 2:
                    direction = PredictionDirection.STRONG_UP
                elif prediction['class'] == 0:
                    direction = PredictionDirection.STRONG_DOWN
                else:
                    direction = direction_map[prediction['class']]
            else:
                direction = direction_map[prediction['class']]

            return PredictionResult(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                direction=direction,
                confidence=confidence,
                predicted_return=expected_return,
                prediction_horizon=prediction_horizon,
                model_type=self.model_type,
                features_used=self.feature_engineer.feature_names[:10]
            )

        except Exception as e:
            logger.error("Direction prediction failed: %s", e)
            return PredictionResult(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                direction=PredictionDirection.NEUTRAL,
                confidence=0.0,
                predicted_return=0.0,
                prediction_horizon=prediction_horizon,
                model_type=self.model_type
            )

    def _predict_neural_network(
        self,
        symbol: str,
        features: pd.DataFrame
    ) -> dict[str, Any]:
        """Make prediction using neural network."""
        if self.direction_model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Prepare sequence
        X, _ = self.feature_engineer.prepare_sequences(features)
        if len(X) == 0:
            raise ValueError("Insufficient data for prediction")

        # Use last sequence
        X_input = torch.FloatTensor(X[-1:]).to(self.device)

        self.direction_model.eval()
        with torch.no_grad():
            outputs = self.direction_model(X_input)
            probabilities = torch.softmax(outputs, dim=1).cpu().numpy()[0]
            predicted_class = int(np.argmax(probabilities))

        return {
            'class': predicted_class,
            'probabilities': probabilities.tolist()
        }

    def _predict_ensemble(
        self,
        symbol: str,
        features: pd.DataFrame
    ) -> dict[str, Any]:
        """Make prediction using ensemble model."""
        # Prepare features
        feature_cols = [c for c in self.feature_engineer.feature_names
                       if c in features.columns]
        X = features[feature_cols].iloc[-1:].values

        # Get predictions from both models
        rf_proba = self.rf_model.predict_proba(X)[0]
        gb_proba = self.gb_model.predict_proba(X)[0]

        # Average probabilities
        avg_proba = (rf_proba + gb_proba) / 2
        predicted_class = int(np.argmax(avg_proba))

        return {
            'class': predicted_class,
            'probabilities': avg_proba.tolist()
        }

    def _estimate_expected_return(
        self,
        predicted_class: int,
        confidence: float,
        features: pd.DataFrame
    ) -> float:
        """Estimate expected return based on prediction."""
        # Base expected return by class
        base_returns = {
            0: -0.005,  # Down
            1: 0.0,     # Neutral
            2: 0.005    # Up
        }

        base = base_returns.get(predicted_class, 0)

        # Scale by confidence and recent volatility
        recent_volatility = features['returns'].tail(20).std()
        scaled_return = base * confidence * (1 + recent_volatility * 10)

        return scaled_return

    def predict_volatility_regime(
        self,
        symbol: str,
        data: pd.DataFrame
    ) -> VolatilityPrediction:
        """
        Predict volatility regime.

        Args:
            symbol: Stock symbol
            data: Recent OHLCV data

        Returns:
            VolatilityPrediction with regime classification
        """
        try:
            features = self.feature_engineer.create_features(data, include_options=True)

            # Current regime from realized volatility
            current_rv = features['returns'].tail(20).std() * np.sqrt(252)
            rv_percentile = (features['returns'].rolling(20).std() * np.sqrt(252)).rank(pct=True).iloc[-1] * 100  # noqa: E501

            current_regime = self._classify_regime(rv_percentile)

            # Predict future regime
            if self.volatility_model is not None:
                feature_cols = [c for c in self.feature_engineer.feature_names
                               if c in features.columns]
                X = features[feature_cols].iloc[-1:].values

                predicted_class = self.volatility_model.predict(X)[0]
                probabilities = self.volatility_model.predict_proba(X)[0]

                regime_map = {0: VolatilityRegime.LOW, 1: VolatilityRegime.NORMAL,
                             2: VolatilityRegime.HIGH, 3: VolatilityRegime.EXTREME}
                predicted_regime = regime_map.get(predicted_class, VolatilityRegime.NORMAL)

                regime_probs = {
                    'low': probabilities[0] if len(probabilities) > 0 else 0,
                    'normal': probabilities[1] if len(probabilities) > 1 else 0,
                    'high': probabilities[2] if len(probabilities) > 2 else 0,
                    'extreme': probabilities[3] if len(probabilities) > 3 else 0,
                }
            else:
                # Fallback to simple extrapolation
                predicted_regime = current_regime
                regime_probs = {r.value: 0.25 for r in VolatilityRegime}
                regime_probs[current_regime.value] = 0.6

            return VolatilityPrediction(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                current_regime=current_regime,
                predicted_regime=predicted_regime,
                regime_probability=regime_probs,
                predicted_iv=current_rv,
                iv_percentile=rv_percentile
            )

        except Exception as e:
            logger.error("Volatility prediction failed: %s", e)
            return VolatilityPrediction(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                current_regime=VolatilityRegime.NORMAL,
                predicted_regime=VolatilityRegime.NORMAL,
                regime_probability={r.value: 0.25 for r in VolatilityRegime},
                predicted_iv=0.2,
                iv_percentile=50.0
            )

    def _classify_regime(self, percentile: float) -> VolatilityRegime:
        """Classify volatility regime from percentile."""
        if percentile < 25:
            return VolatilityRegime.LOW
        elif percentile < 50:
            return VolatilityRegime.NORMAL
        elif percentile < 75:
            return VolatilityRegime.HIGH
        else:
            return VolatilityRegime.EXTREME

    def recommend_strikes(
        self,
        symbol: str,
        data: pd.DataFrame,
        underlying_price: float,
        strategy_type: str = "iron_condor"
    ) -> StrikeRecommendation:
        """
        Recommend optimal strikes based on predictions.

        Args:
            symbol: Stock symbol
            data: Recent market data
            underlying_price: Current underlying price
            strategy_type: Type of strategy (iron_condor, credit_spread, etc.)

        Returns:
            StrikeRecommendation with optimal strikes
        """
        try:
            # Get predictions
            direction_pred = self.predict_direction(symbol, data)
            volatility_pred = self.predict_volatility_regime(symbol, data)

            # Calculate expected move
            expected_move = underlying_price * abs(direction_pred.predicted_return) * 5  # 5-day

            # Determine strikes based on strategy and predictions
            strikes = {}
            rationale = ""

            if strategy_type == "iron_condor":
                # Place wings outside expected move
                wing_distance = expected_move * 1.5

                if volatility_pred.current_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]:  # noqa: E501
                    wing_distance *= 1.3  # Wider wings in high vol

                strikes = {
                    "short_call": round(underlying_price + wing_distance, 0),
                    "long_call": round(underlying_price + wing_distance + 5, 0),
                    "short_put": round(underlying_price - wing_distance, 0),
                    "long_put": round(underlying_price - wing_distance - 5, 0),
                }

                rationale = (
                    f"Based on {direction_pred.direction.value} bias "
                    f"({direction_pred.confidence:.0%} confidence) and "
                    f"{volatility_pred.current_regime.value} volatility regime."
                )

            elif strategy_type == "credit_spread":
                # Directional spread based on prediction
                if direction_pred.direction in [PredictionDirection.UP, PredictionDirection.STRONG_UP]:  # noqa: E501
                    # Bull put spread
                    strikes = {
                        "short_put": round(underlying_price - expected_move, 0),
                        "long_put": round(underlying_price - expected_move - 5, 0),
                    }
                    rationale = f"Bull put spread for {direction_pred.direction.value} bias."
                else:
                    # Bear call spread
                    strikes = {
                        "short_call": round(underlying_price + expected_move, 0),
                        "long_call": round(underlying_price + expected_move + 5, 0),
                    }
                    rationale = f"Bear call spread for {direction_pred.direction.value} bias."

            # Calculate probability of profit
            pop = self._calculate_pop(strikes, underlying_price, volatility_pred.predicted_iv)

            return StrikeRecommendation(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                underlying_price=underlying_price,
                recommended_strikes=strikes,
                recommended_expiry="7_days" if volatility_pred.current_regime == VolatilityRegime.HIGH else "21_days",  # noqa: E501
                expected_probability_of_profit=pop,
                strategy_type=strategy_type,
                rationale=rationale
            )

        except Exception as e:
            logger.error("Strike recommendation failed: %s", e)
            return StrikeRecommendation(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                underlying_price=underlying_price,
                recommended_strikes={},
                recommended_expiry="21_days",
                expected_probability_of_profit=0.0,
                strategy_type=strategy_type,
                rationale=f"Error: {str(e)}"
            )

    def _calculate_pop(
        self,
        strikes: dict[str, float],
        underlying: float,
        iv: float
    ) -> float:
        """Calculate probability of profit for a position."""
        # Simplified POP calculation using standard normal distribution
        from scipy.stats import norm

        if not strikes:
            return 0.0

        # Get the relevant strike for POP
        if 'short_put' in strikes:
            strike = strikes['short_put']
            days = 21
            z_score = (np.log(underlying / strike)) / (iv * np.sqrt(days / 365))
            return norm.cdf(z_score)
        elif 'short_call' in strikes:
            strike = strikes['short_call']
            days = 21
            z_score = (np.log(strike / underlying)) / (iv * np.sqrt(days / 365))
            return norm.cdf(z_score)

        return 0.5  # Default

    # ==========================================================================
    # MODEL PERSISTENCE
    # ==========================================================================

    def _save_model(self, symbol: str):
        """Save trained model to disk."""
        try:
            model_path = self.model_dir / f"{symbol}_{self.model_type.value}"

            if HAS_TORCH and self.direction_model is not None:
                torch.save(
                    self.direction_model.state_dict(),
                    f"{model_path}_direction.pt"
                )

            # Save sklearn models
            joblib.dump(self.rf_model, f"{model_path}_rf.joblib")
            joblib.dump(self.gb_model, f"{model_path}_gb.joblib")

            # Save scaler
            joblib.dump(
                self.feature_engineer.scaler,
                f"{model_path}_scaler.joblib"
            )

            # Save feature names
            with open(f"{model_path}_features.json", 'w') as f:
                json.dump(self.feature_engineer.feature_names, f)

            logger.info("Model saved to %s", model_path)

        except Exception as e:
            logger.error("Model save failed: %s", e)

    def load_model(self, symbol: str) -> bool:
        """Load trained model from disk."""
        try:
            model_path = self.model_dir / f"{symbol}_{self.model_type.value}"

            # Load sklearn models
            rf_path = f"{model_path}_rf.joblib"
            gb_path = f"{model_path}_gb.joblib"

            if os.path.exists(rf_path) and os.path.exists(gb_path):
                self.rf_model = joblib.load(rf_path)
                self.gb_model = joblib.load(gb_path)

            # Load scaler
            scaler_path = f"{model_path}_scaler.joblib"
            if os.path.exists(scaler_path):
                self.feature_engineer.scaler = joblib.load(scaler_path)

            # Load feature names
            features_path = f"{model_path}_features.json"
            if os.path.exists(features_path):
                with open(features_path) as f:
                    self.feature_engineer.feature_names = json.load(f)

            # Load PyTorch model if exists
            if HAS_TORCH:
                pt_path = f"{model_path}_direction.pt"
                if os.path.exists(pt_path):
                    # Need to know input size - use saved feature count
                    input_size = len(self.feature_engineer.feature_names)
                    if self.model_type == ModelType.LSTM:
                        self.direction_model = LSTMModel(input_size=input_size)
                    else:
                        self.direction_model = GRUModel(input_size=input_size)
                    self.direction_model.load_state_dict(
                        _secure_torch_load(pt_path, map_location=self.device)
                    )
                    self.direction_model.to(self.device)

            logger.info("Model loaded from %s", model_path)
            return True

        except Exception as e:
            logger.error("Model load failed: %s", e)
            return False

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def needs_retraining(self, hours: int = RETRAIN_INTERVAL_HOURS) -> bool:
        """Check if model needs retraining."""
        if self._last_training is None:
            return True
        return (datetime.now(UTC) - self._last_training).total_seconds() > hours * 3600

    def get_model_metrics(self, symbol: str = "TRAD") -> ModelMetrics | None:
        """Get model performance metrics."""
        return self.model_metrics.get(symbol)

    def get_feature_importance(self, symbol: str = "TRAD") -> dict[str, float]:
        """Get feature importance from ensemble models."""
        if self.rf_model is None:
            return {}

        importance = dict(zip(
            self.feature_engineer.feature_names,
            self.rf_model.feature_importances_, strict=False
        ))

        # Sort by importance
        return dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))


# ==============================================================================
# FACTORY FUNCTION
# ==============================================================================
def create_ml_engine_from_env() -> MLPredictionEngine:
    """Create MLPredictionEngine from environment variables."""
    model_type = os.getenv("ML_MODEL_TYPE", "ensemble")
    use_gpu = os.getenv("USE_GPU", "false").lower() == "true"

    type_map = {
        "lstm": ModelType.LSTM,
        "gru": ModelType.GRU,
        "random_forest": ModelType.RANDOM_FOREST,
        "ensemble": ModelType.ENSEMBLE
    }

    return MLPredictionEngine(
        model_type=type_map.get(model_type, ModelType.ENSEMBLE),
        use_gpu=use_gpu
    )


# ==============================================================================
# MODULE TESTING
# ==============================================================================
if __name__ == "__main__":

    # Create sample data
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=500, freq="1h")
    data = pd.DataFrame({
        "open": np.random.randn(500).cumsum() + 450,
        "high": np.random.randn(500).cumsum() + 451,
        "low": np.random.randn(500).cumsum() + 449,
        "close": np.random.randn(500).cumsum() + 450,
        "volume": np.random.randint(1000000, 5000000, 500),
    }, index=dates)

    # Ensure high > low
    data["high"] = data[["open", "high", "close"]].max(axis=1)
    data["low"] = data[["open", "low", "close"]].min(axis=1)

    # Initialize engine
    engine = MLPredictionEngine(model_type=ModelType.ENSEMBLE)

    # Train
    metrics = engine.train(data, symbol="TRAD")

    # Predict
    prediction = engine.predict_direction("TRAD", data.tail(100))

    # Volatility
    vol_pred = engine.predict_volatility_regime("TRAD", data)

    # Strike Recommendation
    strikes = engine.recommend_strikes("TRAD", data, 450.0, "iron_condor")

    # Feature Importance
    importance = engine.get_feature_importance()
    for _feat, _imp in list(importance.items())[:10]:
        pass
