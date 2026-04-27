#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderL_ML
Module: SpyderL01_MLPredictor.py
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
from dataclasses import field
from datetime import datetime, timezone
from enum import Enum
import json
from collections import deque
from pathlib import Path
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd

# Optional deep learning imports
try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    HAS_TENSORFLOW = True
except ImportError:
    try:
        from keras.models import Sequential
        from keras.layers import LSTM, Dense, Dropout
        HAS_TENSORFLOW = True
    except ImportError:
        Sequential = None  # type: ignore
        LSTM = None  # type: ignore
        Dense = None  # type: ignore
        Dropout = None  # type: ignore
        HAS_TENSORFLOW = False

# Keras callbacks and model persistence
try:
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    from tensorflow.keras.models import load_model
except ImportError:
    try:
        from keras.callbacks import EarlyStopping, ModelCheckpoint
        from keras.models import load_model
    except ImportError:
        EarlyStopping = None  # type: ignore
        ModelCheckpoint = None  # type: ignore
        load_model = None  # type: ignore

# scikit-learn (optional)
try:
    import joblib
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.preprocessing import StandardScaler, RobustScaler
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import (
        accuracy_score,
        precision_score,
        recall_score,
        f1_score,
        mean_squared_error,
    )
    HAS_SKLEARN = True
except ImportError:
    joblib = None  # type: ignore
    RandomForestClassifier = None  # type: ignore
    RandomForestRegressor = None  # type: ignore
    StandardScaler = None  # type: ignore
    RobustScaler = None  # type: ignore
    TimeSeriesSplit = None  # type: ignore
    accuracy_score = None  # type: ignore
    precision_score = None  # type: ignore
    recall_score = None  # type: ignore
    f1_score = None  # type: ignore
    mean_squared_error = None  # type: ignore
    HAS_SKLEARN = False

# XGBoost (optional)
try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    xgb = None  # type: ignore
    HAS_XGBOOST = False

# LightGBM (optional)
try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    lgb = None  # type: ignore
    HAS_LIGHTGBM = False

# Optuna hyperparameter optimization (optional)
try:
    import optuna
    HAS_OPTUNA = True
except ImportError:
    optuna = None  # type: ignore
    HAS_OPTUNA = False
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

try:
    from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager
except ImportError:
    def get_config_manager():
        return None  # type: ignore

try:
    from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
except ImportError:
    def get_event_manager():
        return None  # type: ignore

try:
    from Spyder.SpyderC_MarketData.SpyderC01_DataFeed import get_data_feed_manager
except ImportError:
    def get_data_feed_manager():
        return None  # type: ignore

try:
    from Spyder.SpyderF_Analysis.SpyderF01_Indicators import get_indicators
except ImportError:
    def get_indicators():
        return None  # type: ignore

try:
    from Spyder.SpyderH_Storage.SpyderH02_DatabaseManager import get_database_manager
except ImportError:
    def get_database_manager():
        return None  # type: ignore

FEATURE_DIR = Path.home() / ".spyder" / "models" / "features"
CHECKPOINT_DIR = Path.home() / ".spyder" / "models" / "checkpoints"

# Model parameters
DEFAULT_LOOKBACK_PERIOD = 20
DEFAULT_PREDICTION_HORIZON = 5
MIN_TRAINING_SAMPLES = 1000
VALIDATION_SPLIT = 0.2
TEST_SPLIT = 0.1


# Feature engineering
TECHNICAL_INDICATORS = [
    "rsi",
    "macd",
    "bb_width",
    "atr",
    "adx",
    "obv",
    "momentum",
    "roc",
    "stochastic_k",
    "stochastic_d",
]

PRICE_FEATURES = [
    "returns",
    "log_returns",
    "volume_ratio",
    "high_low_ratio",
    "close_open_ratio",
    "price_position",
    "volume_ma_ratio",
]

TIME_FEATURES = [
    "hour",
    "day_of_week",
    "day_of_month",
    "month",
    "is_month_start",
    "is_month_end",
    "is_quarter_end",
]

# Model types
MODEL_TYPES = ["classification", "regression", "time_series"]

# =============================================================================
# Enumerations
# =============================================================================


class ModelType(Enum):
    """Types of ML models."""

    DIRECTION = "direction"  # Predict price direction
    VOLATILITY = "volatility"  # Predict volatility
    PRICE = "price"  # Predict price level
    SIGNAL = "signal"  # Trading signal generation
    REGIME = "regime"  # Market regime detection


class Algorithm(Enum):
    """ML algorithms."""

    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    LSTM = "lstm"
    ENSEMBLE = "ensemble"


class PredictionTarget(Enum):
    """Prediction targets."""

    NEXT_CANDLE = "next_candle"
    FIVE_MINUTES = "5min"
    FIFTEEN_MINUTES = "15min"
    ONE_HOUR = "1h"
    END_OF_DAY = "eod"


# =============================================================================
# Data Classes
# =============================================================================


class ModelConfig:
    """
    ML model configuration.

    Attributes:
        model_type: Type of model
        algorithm: ML algorithm
        target: Prediction target
        lookback_period: Historical data period
        features: Feature list
        hyperparameters: Model hyperparameters
        retrain_frequency: Retraining frequency in days
    """

    model_type: ModelType
    algorithm: Algorithm
    target: PredictionTarget
    lookback_period: int = DEFAULT_LOOKBACK_PERIOD
    features: list[str] = field(default_factory=list)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    retrain_frequency: int = 7


class Prediction:
    """
    Model prediction result.

    Attributes:
        timestamp: Prediction timestamp
        model_type: Type of model
        target: Prediction target
        value: Predicted value
        confidence: Prediction confidence
        feature_importance: Important features
        metadata: Additional metadata
    """

    timestamp: datetime
    model_type: ModelType
    target: PredictionTarget
    value: float | int | str
    confidence: float
    feature_importance: dict[str, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelPerformance:
    """
    Model performance metrics.

    Attributes:
        accuracy: Classification accuracy
        precision: Precision score
        recall: Recall score
        f1: F1 score
        mse: Mean squared error
        sharpe: Sharpe ratio of predictions
        feature_importance: Feature importance scores
        confusion_matrix: Confusion matrix
    """

    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    mse: float | None = None
    sharpe: float | None = None
    feature_importance: dict[str, float] = field(default_factory=dict)
    confusion_matrix: np.ndarray | None = None


# =============================================================================
# Class Definitions
# =============================================================================


class MLPredictor:
    """
    Machine learning prediction system for trading.

    This class implements various ML models for predicting market movements
    and generating trading signals. It includes feature engineering, model
    training, validation, and real-time prediction capabilities.

    Attributes:
        logger (Logger): Module logger
        config (ConfigManager): Configuration manager
        event_manager (EventManager): Event system
        data_feed (DataFeedManager): Market data access
        indicators (TechnicalIndicators): Technical analysis
        models (Dict): Trained models
        scalers (Dict): Feature scalers
        feature_cache (deque): Recent feature cache
        performance_history (Dict): Model performance tracking
    """

    def __init__(self):
        """Initialize ML predictor."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = get_config_manager()
        self.event_manager = get_event_manager()
        self.data_feed = get_data_feed_manager()
        self.indicators = get_indicators()
        self.database = get_database_manager()

        # Create directories
        self._create_directories()

        # Model storage
        self.models: dict[str, Any] = {}
        self.scalers: dict[str, StandardScaler] = {}
        self.model_configs: dict[str, ModelConfig] = {}

        # Feature engineering
        self.feature_cache = deque(maxlen=1000)
        self.feature_columns: dict[str, list[str]] = {}

        # Performance tracking
        self.performance_history: dict[str, list[ModelPerformance]] = {}
        self.prediction_history = deque(maxlen=10000)

        # Load existing models
        self._load_models()

        # Initialize default models
        self._initialize_default_models()

        # Subscribe to events
        self._subscribe_to_events()

        self.logger.info("ML predictor initialized")

    def _create_directories(self) -> None:
        """Create model directories."""
        directories = [
            Path.home() / ".spyder" / "models",
            FEATURE_DIR,
            CHECKPOINT_DIR,
            Path.home() / ".spyder" / "models" / "saved",
            Path.home() / ".spyder" / "models" / "reports",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _initialize_default_models(self) -> None:
        """Initialize default ML models."""
        # Direction prediction model
        self.model_configs["direction"] = ModelConfig(
            model_type=ModelType.DIRECTION,
            algorithm=Algorithm.XGBOOST,
            target=PredictionTarget.FIVE_MINUTES,
            lookback_period=20,
            features=TECHNICAL_INDICATORS + PRICE_FEATURES,
            hyperparameters={"n_estimators": 100, "max_depth": 5, "learning_rate": 0.1},
        )

        # Volatility prediction model
        self.model_configs["volatility"] = ModelConfig(
            model_type=ModelType.VOLATILITY,
            algorithm=Algorithm.LIGHTGBM,
            target=PredictionTarget.ONE_HOUR,
            lookback_period=30,
            features=TECHNICAL_INDICATORS + ["historical_volatility", "atr"],
            hyperparameters={"num_leaves": 31, "learning_rate": 0.05, "n_estimators": 200},
        )

        # Signal generation model
        self.model_configs["signal"] = ModelConfig(
            model_type=ModelType.SIGNAL,
            algorithm=Algorithm.ENSEMBLE,
            target=PredictionTarget.NEXT_CANDLE,
            lookback_period=15,
            features=TECHNICAL_INDICATORS + PRICE_FEATURES + TIME_FEATURES,
        )

    def _subscribe_to_events(self) -> None:
        """Subscribe to system events."""
        self.event_manager.subscribe("MARKET_DATA_UPDATE", self._on_market_update)
        self.event_manager.subscribe("RETRAIN_MODELS", self._on_retrain_request)

    # =========================================================================
    # Public Methods - Predictions
    # =========================================================================

    def predict(self, model_name: str, features: pd.DataFrame | None = None) -> Prediction:
        """
        Make prediction using specified model.

        Args:
            model_name: Name of model to use
            features: Feature data (optional, uses latest if not provided)

        Returns:
            Prediction result
        """
        try:
            if model_name not in self.models:
                raise ValueError(f"Model {model_name} not found")

            # Get features if not provided
            if features is None:
                features = self._get_latest_features(model_name)

            # Scale features
            if model_name in self.scalers:
                features_scaled = self.scalers[model_name].transform(features)
            else:
                features_scaled = features

            # Make prediction
            model = self.models[model_name]
            config = self.model_configs[model_name]

            if config.algorithm == Algorithm.LSTM:
                # Reshape for LSTM
                features_scaled = features_scaled.reshape(
                    (features_scaled.shape[0], 1, features_scaled.shape[1])
                )
                prediction = model.predict(features_scaled)
            else:
                prediction = model.predict(features_scaled)

            # Get prediction probability/confidence
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(features_scaled)
                confidence = np.max(proba)
            else:
                confidence = 0.5  # Default confidence for regressors

            # Get feature importance
            feature_importance = self._get_feature_importance(model_name)

            # Create prediction object
            pred = Prediction(
                timestamp=datetime.now(timezone.utc),
                model_type=config.model_type,
                target=config.target,
                value=prediction[0] if len(prediction) == 1 else prediction,
                confidence=confidence,
                feature_importance=feature_importance,
            )

            # Store prediction
            self.prediction_history.append(pred)

            # Emit prediction event
            self.event_manager.emit(
                "ML_PREDICTION",
                {"model": model_name, "prediction": pred.value, "confidence": pred.confidence},
            )

            return pred

        except Exception as e:
            self.logger.error("Prediction failed for %s: %s", model_name, str(e))
            raise

    def predict_ensemble(
        self, model_names: list[str], features: pd.DataFrame | None = None
    ) -> Prediction:
        """
        Make ensemble prediction using multiple models.

        Args:
            model_names: List of model names
            features: Feature data

        Returns:
            Ensemble prediction
        """
        predictions = []
        weights = []

        for model_name in model_names:
            try:
                pred = self.predict(model_name, features)
                predictions.append(pred.value)
                weights.append(pred.confidence)
            except Exception as e:
                self.logger.warning("Failed to get prediction from %s: %s", model_name, str(e))

        if not predictions:
            raise ValueError("No successful predictions from ensemble")

        # Weighted average for regression, majority vote for classification
        if isinstance(predictions[0], (int, np.integer)):
            # Classification - weighted majority vote
            unique_preds, counts = np.unique(predictions, return_counts=True)
            ensemble_pred = unique_preds[np.argmax(counts)]
        else:
            # Regression - weighted average
            ensemble_pred = np.average(predictions, weights=weights)

        return Prediction(
            timestamp=datetime.now(timezone.utc),
            model_type=ModelType.SIGNAL,
            target=PredictionTarget.NEXT_CANDLE,
            value=ensemble_pred,
            confidence=np.mean(weights),
        )

    # =========================================================================
    # Public Methods - Training
    # =========================================================================

    def train_model(
        self, model_name: str, data: pd.DataFrame, optimize_hyperparameters: bool = False
    ) -> ModelPerformance:
        """
        Train or retrain a model.

        Args:
            model_name: Name of model
            data: Training data with features and target
            optimize_hyperparameters: Whether to optimize hyperparameters

        Returns:
            Model performance metrics
        """
        try:
            config = self.model_configs.get(model_name)
            if not config:
                raise ValueError(f"No configuration for model {model_name}")

            self.logger.info("Training model: %s", model_name)

            # Prepare features and target
            X, y = self._prepare_training_data(data, config)

            # Split data
            X_train, X_test, y_train, y_test = self._split_data(X, y, config)

            # Scale features
            scaler = RobustScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # Store scaler
            self.scalers[model_name] = scaler

            # Optimize hyperparameters if requested
            if optimize_hyperparameters:
                best_params = self._optimize_hyperparameters(config, X_train_scaled, y_train)
                config.hyperparameters.update(best_params)

            # Train model
            model = self._create_model(config)

            if config.algorithm == Algorithm.LSTM:
                # LSTM training
                model.fit(
                    X_train_scaled.reshape((X_train_scaled.shape[0], 1, X_train_scaled.shape[1])),
                    y_train,
                    epochs=50,
                    batch_size=32,
                    validation_split=0.2,
                    callbacks=[
                        EarlyStopping(patience=10, restore_best_weights=True),
                        ModelCheckpoint(
                            str(CHECKPOINT_DIR / f"{model_name}_best.h5"), save_best_only=True
                        ),
                    ],
                    verbose=0,
                )
            else:
                # Sklearn/XGBoost/LightGBM training
                model.fit(X_train_scaled, y_train)

            # Store model
            self.models[model_name] = model

            # Evaluate performance
            performance = self._evaluate_model(model, X_test_scaled, y_test, config)

            # Store performance
            if model_name not in self.performance_history:
                self.performance_history[model_name] = []
            self.performance_history[model_name].append(performance)

            # Save model
            self._save_model(model_name)

            self.logger.info(
                f"Model {model_name} trained successfully. "
                f"Performance: {performance.accuracy or performance.mse}"
            )

            return performance

        except Exception as e:
            self.logger.error("Failed to train model %s: %s", model_name, str(e))
            raise

    def retrain_all_models(self, data: pd.DataFrame) -> dict[str, ModelPerformance]:
        """
        Retrain all models.

        Args:
            data: Training data

        Returns:
            Performance metrics for all models
        """
        results = {}

        for model_name in self.model_configs:
            try:
                performance = self.train_model(model_name, data)
                results[model_name] = performance
            except Exception as e:
                self.logger.error("Failed to retrain %s: %s", model_name, str(e))

        return results

    # =========================================================================
    # Public Methods - Feature Engineering
    # =========================================================================

    def engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features from raw market data.

        Args:
            data: Raw OHLCV data

        Returns:
            DataFrame with engineered features
        """
        features = data.copy()

        # Price features
        features["returns"] = features["close"].pct_change()
        features["log_returns"] = np.log(features["close"] / features["close"].shift(1))
        features["volume_ratio"] = features["volume"] / features["volume"].rolling(20).mean()
        features["high_low_ratio"] = features["high"] / features["low"]
        features["close_open_ratio"] = features["close"] / features["open"]

        # Price position in range
        features["price_position"] = (features["close"] - features["low"]) / (
            features["high"] - features["low"]
        )

        # Technical indicators
        features["rsi"] = self.indicators.rsi(features["close"])

        macd_data = self.indicators.macd(features["close"])
        features["macd"] = macd_data["macd"]
        features["macd_signal"] = macd_data["signal"]
        features["macd_hist"] = macd_data["histogram"]

        bb_data = self.indicators.bollinger_bands(features["close"])
        features["bb_width"] = (bb_data["upper"] - bb_data["lower"]) / bb_data["middle"]
        features["bb_position"] = (features["close"] - bb_data["lower"]) / (
            bb_data["upper"] - bb_data["lower"]
        )

        features["atr"] = self.indicators.atr(features["high"], features["low"], features["close"])
        features["obv"] = self.indicators.on_balance_volume(features["close"], features["volume"])
        features["momentum"] = self.indicators.momentum(features["close"])
        features["roc"] = self.indicators.rate_of_change(features["close"])

        # Stochastic
        stoch_data = self.indicators.stochastic(
            features["high"], features["low"], features["close"]
        )
        features["stochastic_k"] = stoch_data["k"]
        features["stochastic_d"] = stoch_data["d"]

        # Volatility
        features["historical_volatility"] = self.indicators.historical_volatility(features["close"])

        # Time features
        if "timestamp" in features.columns:
            features["hour"] = features["timestamp"].dt.hour
            features["day_of_week"] = features["timestamp"].dt.dayofweek
            features["day_of_month"] = features["timestamp"].dt.day
            features["month"] = features["timestamp"].dt.month
            features["is_month_start"] = features["timestamp"].dt.is_month_start.astype(int)
            features["is_month_end"] = features["timestamp"].dt.is_month_end.astype(int)
            features["is_quarter_end"] = features["timestamp"].dt.is_quarter_end.astype(int)

        # Drop NaN values
        features = features.dropna()

        return features

    def get_feature_importance(self, model_name: str) -> dict[str, float]:
        """
        Get feature importance for a model.

        Args:
            model_name: Model name

        Returns:
            Feature importance scores
        """
        return self._get_feature_importance(model_name)

    # =========================================================================
    # Private Methods - Model Management
    # =========================================================================

    def _create_model(self, config: ModelConfig):
        """Create model based on configuration."""
        if config.algorithm == Algorithm.RANDOM_FOREST:
            if config.model_type in [ModelType.DIRECTION, ModelType.SIGNAL]:
                return RandomForestClassifier(**config.hyperparameters)
            else:
                return RandomForestRegressor(**config.hyperparameters)

        elif config.algorithm == Algorithm.XGBOOST:
            if config.model_type in [ModelType.DIRECTION, ModelType.SIGNAL]:
                return xgb.XGBClassifier(**config.hyperparameters)
            else:
                return xgb.XGBRegressor(**config.hyperparameters)

        elif config.algorithm == Algorithm.LIGHTGBM:
            if config.model_type in [ModelType.DIRECTION, ModelType.SIGNAL]:
                return lgb.LGBMClassifier(**config.hyperparameters)
            else:
                return lgb.LGBMRegressor(**config.hyperparameters)

        elif config.algorithm == Algorithm.LSTM:
            return self._create_lstm_model(config)

        else:
            raise ValueError(f"Unknown algorithm: {config.algorithm}")

    def _create_lstm_model(self, config: ModelConfig) -> Sequential:
        """Create LSTM model."""
        model = Sequential(
            [
                LSTM(
                    50,
                    activation="relu",
                    return_sequences=True,
                    input_shape=(1, len(config.features)),
                ),
                Dropout(0.2),
                LSTM(50, activation="relu"),
                Dropout(0.2),
                Dense(25, activation="relu"),
                Dense(1),
            ]
        )

        model.compile(optimizer="adam", loss="mse", metrics=["mae"])
        return model

    def _prepare_training_data(
        self, data: pd.DataFrame, config: ModelConfig
    ) -> tuple[pd.DataFrame, pd.Series]:
        """Prepare features and target for training."""
        # Engineer features if not already done
        if "returns" not in data.columns:
            data = self.engineer_features(data)

        # Select features
        feature_cols = config.features
        if not feature_cols:
            # Use all numeric columns except target
            feature_cols = [col for col in data.columns if col not in ["target", "timestamp"]]

        X = data[feature_cols]

        # Create target based on model type
        if config.model_type == ModelType.DIRECTION:
            # Binary classification: 1 if price goes up, 0 if down
            future_returns = data["returns"].shift(-config.lookback_period)
            y = (future_returns > 0).astype(int)

        elif config.model_type == ModelType.VOLATILITY:
            # Predict future volatility
            y = data["historical_volatility"].shift(-config.lookback_period)

        elif config.model_type == ModelType.PRICE:
            # Predict future price
            y = data["close"].shift(-config.lookback_period)

        elif config.model_type == ModelType.SIGNAL:
            # Trading signal: Buy (1), Hold (0), Sell (-1)
            future_returns = data["returns"].shift(-config.lookback_period)
            y = pd.cut(future_returns, bins=[-np.inf, -0.001, 0.001, np.inf], labels=[-1, 0, 1])

        else:
            y = data.get("target", data["returns"].shift(-1))

        # Remove NaN values
        valid_idx = ~(X.isnull().any(axis=1) | y.isnull())
        X = X[valid_idx]
        y = y[valid_idx]

        return X, y

    def _split_data(
        self, X: pd.DataFrame, y: pd.Series, config: ModelConfig
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Split data for time series."""
        # Use time series split for financial data
        n_samples = len(X)
        train_size = int(n_samples * (1 - TEST_SPLIT))

        X_train = X.iloc[:train_size]
        X_test = X.iloc[train_size:]
        y_train = y.iloc[:train_size]
        y_test = y.iloc[train_size:]

        return X_train.values, X_test.values, y_train.values, y_test.values

    def _optimize_hyperparameters(
        self, config: ModelConfig, X_train: np.ndarray, y_train: np.ndarray
    ) -> dict[str, Any]:
        """Optimize hyperparameters using Optuna."""

        def objective(trial):
            if config.algorithm == Algorithm.XGBOOST:
                params = {
                    "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                    "max_depth": trial.suggest_int("max_depth", 3, 10),
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                    "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                    "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                }
                model = (
                    xgb.XGBClassifier(**params)
                    if config.model_type in [ModelType.DIRECTION, ModelType.SIGNAL]
                    else xgb.XGBRegressor(**params)
                )

            elif config.algorithm == Algorithm.LIGHTGBM:
                params = {
                    "num_leaves": trial.suggest_int("num_leaves", 20, 300),
                    "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3),
                    "n_estimators": trial.suggest_int("n_estimators", 50, 300),
                    "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                }
                model = (
                    lgb.LGBMClassifier(**params)
                    if config.model_type in [ModelType.DIRECTION, ModelType.SIGNAL]
                    else lgb.LGBMRegressor(**params)
                )

            else:
                return 0

            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=3)
            scores = []

            for train_idx, val_idx in tscv.split(X_train):
                X_fold_train, X_fold_val = X_train[train_idx], X_train[val_idx]
                y_fold_train, y_fold_val = y_train[train_idx], y_train[val_idx]

                model.fit(X_fold_train, y_fold_train)

                if config.model_type in [ModelType.DIRECTION, ModelType.SIGNAL]:
                    score = accuracy_score(y_fold_val, model.predict(X_fold_val))
                else:
                    score = -mean_squared_error(y_fold_val, model.predict(X_fold_val))

                scores.append(score)

            return np.mean(scores)

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=50, n_jobs=-1)

        return study.best_params

    def _evaluate_model(
        self, model, X_test: np.ndarray, y_test: np.ndarray, config: ModelConfig
    ) -> ModelPerformance:
        """Evaluate model performance."""
        performance = ModelPerformance()

        # Make predictions
        if config.algorithm == Algorithm.LSTM:
            X_test_reshaped = X_test.reshape((X_test.shape[0], 1, X_test.shape[1]))
            y_pred = model.predict(X_test_reshaped)
            y_pred = y_pred.flatten()
        else:
            y_pred = model.predict(X_test)

        # Calculate metrics based on model type
        if config.model_type in [ModelType.DIRECTION, ModelType.SIGNAL]:
            # Classification metrics
            performance.accuracy = accuracy_score(y_test, y_pred)
            performance.precision = precision_score(y_test, y_pred, average="weighted")
            performance.recall = recall_score(y_test, y_pred, average="weighted")
            performance.f1 = f1_score(y_test, y_pred, average="weighted")
        else:
            # Regression metrics
            performance.mse = mean_squared_error(y_test, y_pred)

        # Feature importance
        if hasattr(model, "feature_importances_"):
            feature_names = self.model_configs[config.model_type.value].features
            performance.feature_importance = dict(zip(feature_names, model.feature_importances_, strict=False))  # noqa: E501

        return performance

    def _get_feature_importance(self, model_name: str) -> dict[str, float]:
        """Get feature importance for a model."""
        if model_name not in self.models:
            return {}

        model = self.models[model_name]

        if hasattr(model, "feature_importances_"):
            feature_names = self.model_configs[model_name].features
            return dict(zip(feature_names, model.feature_importances_, strict=False))

        # Use SHAP for models without built-in importance
        try:
            # This is simplified - would need proper implementation
            return {}
        except Exception:
            return {}

    def _get_latest_features(self, model_name: str) -> pd.DataFrame:
        """Get latest features for prediction."""
        # Get recent market data
        # This would get from data feed
        # Simplified for example

        if self.feature_cache:
            return pd.DataFrame([self.feature_cache[-1]])
        else:
            # Return dummy features
            config = self.model_configs[model_name]
            return pd.DataFrame(np.random.randn(1, len(config.features)), columns=config.features)

    # =========================================================================
    # Private Methods - Model Persistence
    # =========================================================================

    def _save_model(self, model_name: str) -> None:
        """Save model to disk."""
        try:
            model = self.models.get(model_name)
            if not model:
                return

            # Save model
            model_path = Path.home() / ".spyder" / "models" / "saved" / f"{model_name}_model.pkl"

            if isinstance(model, Sequential):
                # Keras model
                model.save(str(model_path.with_suffix(".h5")))
            else:
                # Sklearn/XGBoost/LightGBM
                joblib.dump(model, model_path)

            # Save scaler
            if model_name in self.scalers:
                scaler_path = (
                    Path.home() / ".spyder" / "models" / "saved" / f"{model_name}_scaler.pkl"
                )
                joblib.dump(self.scalers[model_name], scaler_path)

            # Save config
            config_path = Path.home() / ".spyder" / "models" / "saved" / f"{model_name}_config.json"
            config_dict = {
                "model_type": self.model_configs[model_name].model_type.value,
                "algorithm": self.model_configs[model_name].algorithm.value,
                "target": self.model_configs[model_name].target.value,
                "lookback_period": self.model_configs[model_name].lookback_period,
                "features": self.model_configs[model_name].features,
                "hyperparameters": self.model_configs[model_name].hyperparameters,
            }

            with open(config_path, "w") as f:
                json.dump(config_dict, f, indent=2)

            self.logger.info("Model %s saved successfully", model_name)

        except Exception as e:
            self.logger.error("Failed to save model %s: %s", model_name, str(e))

    def _load_models(self) -> None:
        """Load models from disk."""
        saved_dir = Path.home() / ".spyder" / "models" / "saved"
        if not saved_dir.exists():
            return

        for model_file in saved_dir.glob("*_model.*"):
            try:
                model_name = model_file.stem.replace("_model", "")

                # Load config
                config_path = saved_dir / f"{model_name}_config.json"
                if config_path.exists():
                    with open(config_path) as f:
                        config_dict = json.load(f)

                    config = ModelConfig(
                        model_type=ModelType(config_dict["model_type"]),
                        algorithm=Algorithm(config_dict["algorithm"]),
                        target=PredictionTarget(config_dict["target"]),
                        lookback_period=config_dict["lookback_period"],
                        features=config_dict["features"],
                        hyperparameters=config_dict["hyperparameters"],
                    )
                    self.model_configs[model_name] = config

                # Load model
                if model_file.suffix == ".h5":
                    # Keras model
                    model = load_model(str(model_file))
                else:
                    # Sklearn/XGBoost/LightGBM
                    model = joblib.load(model_file)

                self.models[model_name] = model

                # Load scaler
                scaler_path = saved_dir / f"{model_name}_scaler.pkl"
                if scaler_path.exists():
                    self.scalers[model_name] = joblib.load(scaler_path)

                self.logger.info("Loaded model: %s", model_name)

            except Exception as e:
                self.logger.error("Failed to load model %s: %s", model_file, str(e))

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def _on_market_update(self, event_data: dict[str, Any]) -> None:
        """Handle market data update."""
        try:
            # Extract features from market data
            market_data = pd.DataFrame([event_data])
            features = self.engineer_features(market_data)

            if not features.empty:
                # Cache features
                self.feature_cache.append(features.iloc[-1].to_dict())

                # Make predictions for active models
                for model_name in self.models:
                    try:
                        prediction = self.predict(model_name, features.iloc[-1:])

                        # Emit prediction event
                        self.event_manager.emit(
                            "ML_PREDICTION_UPDATE", {"model": model_name, "prediction": prediction}
                        )
                    except Exception as e:
                        self.logger.error("Prediction failed for %s: %s", model_name, str(e))

        except Exception as e:
            self.logger.error("Failed to process market update: %s", str(e))

    def _on_retrain_request(self, event_data: dict[str, Any]) -> None:
        """Handle model retrain request."""
        model_name = event_data.get("model_name")
        data = event_data.get("data")

        if model_name and data is not None:
            try:
                performance = self.train_model(model_name, data)

                self.event_manager.emit(
                    "MODEL_RETRAINED", {"model": model_name, "performance": performance}
                )
            except Exception as e:
                self.logger.error("Failed to retrain %s: %s", model_name, str(e))


# =============================================================================
# Module Functions
# =============================================================================


def get_ml_predictor() -> MLPredictor:
    """
    Get singleton instance of ML predictor.

    Returns:
        MLPredictor instance
    """
    global _ML_PREDICTOR_INSTANCE
    if _ML_PREDICTOR_INSTANCE is None:
        _ML_PREDICTOR_INSTANCE = MLPredictor()
    return _ML_PREDICTOR_INSTANCE


def generate_trading_signals(data: pd.DataFrame) -> pd.DataFrame:
    """
    Generate trading signals using ML models.

    Args:
        data: Market data

    Returns:
        DataFrame with signals
    """
    predictor = get_ml_predictor()

    # Get predictions from multiple models
    signals = pd.DataFrame(index=data.index)

    for model_name in ["direction", "volatility", "signal"]:
        try:
            features = predictor.engineer_features(data)
            predictions = []

            for i in range(len(features)):
                pred = predictor.predict(model_name, features.iloc[i : i + 1])
                predictions.append(pred.value)

            signals[f"{model_name}_prediction"] = predictions

        except Exception as e:
            logger = SpyderLogger.get_logger(__name__)
            logger.error("Failed to generate signals from %s: %s", model_name, str(e))

    return signals


# =============================================================================
# Module Initialization
# =============================================================================
_ML_PREDICTOR_INSTANCE: MLPredictor | None = None
