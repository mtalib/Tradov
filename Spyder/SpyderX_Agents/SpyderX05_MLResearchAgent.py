#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderX_Agents
Module: SpyderX05_MLResearchAgent.py
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
import json
import asyncio
import logging
import os
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import accuracy_score

try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

# Ollama integration
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    logging.info("Warning: ollama package not installed. Install with: pip install ollama")
    OLLAMA_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Note: In standalone mode, we're not importing from other Spyder modules
# In production, these would be imported from the Spyder ecosystem

# ==============================================================================
# CONSTANTS
# ==============================================================================
# LLM Configuration
DEFAULT_LLM_MODEL = os.getenv("OLLAMA_CODE_MODEL", "gemma4:26b")
DEFAULT_TEMPERATURE = 0.3
MAX_TOKENS = 2000

# ML Configuration
MAX_MODELS = 10
RETRAIN_FREQUENCY_HOURS = 24
MODEL_DECAY_THRESHOLD = 0.7
FEATURE_IMPORTANCE_THRESHOLD = 0.01
CV_FOLDS = 5

# Model Performance Thresholds
MIN_ACCURACY = 0.55
MIN_SHARPE = 0.5
MAX_CORRELATION = 0.7

# ==============================================================================
# LOGGING SETUP
# ==============================================================================
logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================
class PredictionTask(Enum):
    """Types of prediction tasks"""
    PRICE_DIRECTION = "price_direction"
    VOLATILITY_FORECAST = "volatility_forecast"
    OPTIMAL_STRIKE = "optimal_strike"
    ENTRY_TIMING = "entry_timing"
    EXIT_TIMING = "exit_timing"
    STRATEGY_SELECTION = "strategy_selection"
    RISK_PREDICTION = "risk_prediction"

class ModelType(Enum):
    """Available model types"""
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOST = "gradient_boost"
    XGBOOST = "xgboost"
    SVM = "svm"
    NEURAL_NETWORK = "neural_network"
    LINEAR = "linear"
    ENSEMBLE = "ensemble"

class FeatureType(Enum):
    """Types of features"""
    PRICE = "price"
    VOLUME = "volume"
    TECHNICAL = "technical"
    GREEKS = "greeks"
    MARKET_STRUCTURE = "market_structure"
    SENTIMENT = "sentiment"
    MACRO = "macro"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketData:
    """Market data for ML processing"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    volatility: float
    additional_features: dict[str, float] = field(default_factory=dict)

@dataclass
class FeatureSet:
    """Engineered feature set"""
    timestamp: datetime
    features: pd.DataFrame
    feature_names: list[str]
    feature_importance: dict[str, float]
    engineering_method: str
    validation_score: float

@dataclass
class ModelConfig:
    """Model configuration"""
    model_type: ModelType
    task: PredictionTask
    hyperparameters: dict[str, Any]
    features: list[str]
    training_window: int  # days
    retrain_frequency: int  # hours
    performance_threshold: float

@dataclass
class ModelPerformance:
    """Model performance metrics"""
    model_id: str
    task: PredictionTask
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    sharpe_ratio: float
    max_drawdown: float
    last_updated: datetime
    decay_factor: float = 1.0

@dataclass
class Prediction:
    """ML prediction result"""
    timestamp: datetime
    task: PredictionTask
    prediction: Any
    probability: float | None
    confidence: float
    model_used: str
    features_used: list[str]
    explanation: str | None = None

@dataclass
class ResearchResult:
    """ML research experiment result"""
    experiment_id: str
    timestamp: datetime
    hypothesis: str
    models_tested: list[str]
    best_model: str
    performance_metrics: dict[str, float]
    insights: list[str]
    recommendations: list[str]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class SpyderX05_MLResearchAgent:
    """
    AI-Enhanced Machine Learning Research Agent.

    This agent performs AutoML, feature engineering, model selection, and
    continuous learning. It uses Ollama to understand which ML approaches
    work best for current market conditions and automatically adapts.

    Attributes:
        logger: Module logger instance
        config: Agent configuration
        ollama_client: Ollama LLM client
        active_models: Currently deployed models
        model_performance: Performance tracking for all models

    Example:
        >>> agent = SpyderX05_MLResearchAgent()
        >>> prediction = await agent.predict(PredictionTask.PRICE_DIRECTION, market_data)
        >>> research = await agent.conduct_research("volatility_prediction")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the ML Research Agent.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logger

        # LLM configuration
        self.model_name = self.config.get('llm_model', DEFAULT_LLM_MODEL)
        self.temperature = self.config.get('temperature', DEFAULT_TEMPERATURE)
        self.max_models = self.config.get('max_concurrent_models', MAX_MODELS)

        # Initialize Ollama client
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                # Test if Ollama is running
                ollama.list()
                self.ollama_client = ollama
                self.logger.info("Ollama initialized with model: %s", self.model_name)
            except Exception as e:
                self.logger.error("Failed to connect to Ollama: %s", e, exc_info=True)
                self.logger.info("Agent will work with reduced AI capabilities")

        # Model storage
        self.active_models: dict[str, Any] = {}
        self.model_configs: dict[str, ModelConfig] = {}
        self.model_performance: dict[str, ModelPerformance] = {}

        # Feature engineering
        self.feature_cache: dict[str, FeatureSet] = {}
        self.feature_importance_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.dynamic_features: set[str] = set()

        # Research tracking
        self.experiment_history: list[ResearchResult] = []
        self.current_research_tasks: dict[str, asyncio.Task] = {}

        # Data storage
        self.training_data: pd.DataFrame = pd.DataFrame()
        self.prediction_buffer: deque = deque(maxlen=10000)

        # Model paths
        self.model_dir = Path(self.config.get('model_directory', './models'))
        self.model_dir.mkdir(exist_ok=True)

        # Performance tracking
        self.prediction_accuracy: dict[PredictionTask, deque] = defaultdict(lambda: deque(maxlen=1000))  # noqa: E501
        self.model_selection_history: deque = deque(maxlen=1000)

        self.logger.info("%s initialized", self.__class__.__name__)

    # ==========================================================================
    # PUBLIC METHODS
    # ==========================================================================
    async def predict(
        self,
        task: PredictionTask,
        market_data: MarketData,
        context: dict[str, Any] | None = None
    ) -> Prediction:
        """
        Make a prediction for the specified task.

        Args:
            task: Type of prediction to make
            market_data: Current market data
            context: Optional additional context

        Returns:
            Prediction result with confidence and explanation
        """
        start_time = datetime.now()

        # Engineer features
        features = await self._engineer_features(market_data, task, context)

        # Select best model for task
        model_id = self._select_best_model(task)

        if not model_id or model_id not in self.active_models:
            # Train new model if needed
            model_id = await self._train_model(task, features)

        # Make prediction
        if model_id and model_id in self.active_models:
            model = self.active_models[model_id]
            prediction_value, probability = self._make_prediction(model, features)

            # Get AI explanation if available
            if self.ollama_client:
                explanation = await self._get_prediction_explanation(
                    task,
                    prediction_value,
                    features,
                    context
                )
            else:
                explanation = f"{task.value} prediction: {prediction_value}"

            # Calculate confidence
            confidence = self._calculate_confidence(
                model_id,
                probability,
                features
            )

            prediction = Prediction(
                timestamp=datetime.now(),
                task=task,
                prediction=prediction_value,
                probability=probability,
                confidence=confidence,
                model_used=model_id,
                features_used=features.feature_names[:10],  # Top 10 features
                explanation=explanation
            )
        else:
            # Fallback prediction
            prediction = self._get_fallback_prediction(task, market_data)

        # Store prediction for performance tracking
        self.prediction_buffer.append(prediction)

        # Log performance
        elapsed = (datetime.now() - start_time).total_seconds()
        self.logger.info(
            f"Prediction for {task.value} completed in {elapsed:.2f} seconds. "
            f"Confidence: {prediction.confidence:.2%}"
        )

        return prediction

    async def conduct_research(
        self,
        hypothesis: str,
        data: pd.DataFrame | None = None
    ) -> ResearchResult:
        """
        Conduct ML research experiment.

        Args:
            hypothesis: Research hypothesis to test
            data: Optional data for research

        Returns:
            Research results with insights and recommendations
        """
        experiment_id = hashlib.md5(
            f"{hypothesis}_{datetime.now()}".encode(), usedforsecurity=False
        ).hexdigest()[:8]

        self.logger.info("Starting research experiment %s: %s", experiment_id, hypothesis)

        # Use training data if no data provided
        if data is None:
            data = self.training_data

        if data.empty:
            return ResearchResult(
                experiment_id=experiment_id,
                timestamp=datetime.now(),
                hypothesis=hypothesis,
                models_tested=[],
                best_model="none",
                performance_metrics={},
                insights=["Insufficient data for research"],
                recommendations=["Collect more training data"]
            )

        # Get AI guidance on research approach
        if self.ollama_client:
            research_plan = await self._get_ai_research_plan(hypothesis, data)
            models_to_test = research_plan.get('models', list(ModelType))
            research_plan.get('features', [])
        else:
            models_to_test = list(ModelType)

        # Test different models
        results = {}
        for model_type in models_to_test:
            if model_type == ModelType.XGBOOST and not XGBOOST_AVAILABLE:
                continue

            try:
                performance = await self._test_model_approach(
                    model_type,
                    data,
                    hypothesis
                )
                results[model_type.value] = performance
            except Exception as e:
                self.logger.error("Error testing %s: %s", model_type.value, e, exc_info=True)

        # Find best model
        best_model = max(results.items(), key=lambda x: x[1]['score'])[0]
        best_performance = results[best_model]

        # Generate insights
        insights = self._generate_research_insights(results, hypothesis)

        # Get AI recommendations
        if self.ollama_client:
            ai_recommendations = await self._get_ai_research_recommendations(
                hypothesis,
                results,
                insights
            )
            recommendations = ai_recommendations
        else:
            recommendations = self._get_basic_recommendations(results)

        # Create research result
        research_result = ResearchResult(
            experiment_id=experiment_id,
            timestamp=datetime.now(),
            hypothesis=hypothesis,
            models_tested=list(results.keys()),
            best_model=best_model,
            performance_metrics=best_performance,
            insights=insights,
            recommendations=recommendations
        )

        # Store in history
        self.experiment_history.append(research_result)

        return research_result

    async def optimize_models(self) -> dict[str, Any]:
        """
        Optimize all active models.

        Returns:
            Optimization results and improvements
        """
        self.logger.info("Starting model optimization")

        optimization_results = {}

        for model_id, _model in self.active_models.items():
            if model_id not in self.model_configs:
                continue

            config = self.model_configs[model_id]

            # Check if model needs retraining
            if self._should_retrain(model_id):
                self.logger.info("Retraining model %s", model_id)

                # Get recent data
                recent_data = self._get_recent_training_data(config.training_window)

                # Retrain model
                new_performance = await self._retrain_model(
                    model_id,
                    recent_data,
                    config
                )

                optimization_results[model_id] = {
                    'action': 'retrained',
                    'improvement': new_performance
                }
            else:
                # Just update performance metrics
                self._update_model_performance(model_id)
                optimization_results[model_id] = {
                    'action': 'monitored',
                    'current_performance': self.model_performance[model_id].accuracy
                }

        # Remove underperforming models
        models_to_remove = self._identify_underperforming_models()
        for model_id in models_to_remove:
            self._remove_model(model_id)
            optimization_results[model_id] = {'action': 'removed'}

        return optimization_results

    def get_model_inventory(self) -> dict[str, Any]:
        """
        Get inventory of all models.

        Returns:
            Summary of active models and their performance
        """
        inventory = {
            'active_models': len(self.active_models),
            'models': {}
        }

        for model_id, _model in self.active_models.items():
            if model_id in self.model_performance:
                perf = self.model_performance[model_id]
                inventory['models'][model_id] = {
                    'task': perf.task.value,
                    'accuracy': perf.accuracy,
                    'sharpe_ratio': perf.sharpe_ratio,
                    'last_updated': perf.last_updated,
                    'decay_factor': perf.decay_factor
                }

        return inventory

    def get_feature_importance(self, task: PredictionTask) -> dict[str, float]:
        """
        Get feature importance for a specific task.

        Args:
            task: Prediction task

        Returns:
            Feature importance scores
        """
        # Find models for this task
        task_models = [
            model_id for model_id, config in self.model_configs.items()
            if config.task == task
        ]

        if not task_models:
            return {}

        # Aggregate feature importance across models
        aggregated_importance = defaultdict(float)
        count = 0

        for model_id in task_models:
            if model_id in self.feature_cache:
                feature_set = self.feature_cache[model_id]
                for feature, importance in feature_set.feature_importance.items():
                    aggregated_importance[feature] += importance
                count += 1

        # Average the importance scores
        if count > 0:
            for feature in aggregated_importance:
                aggregated_importance[feature] /= count

        # Sort by importance
        return dict(sorted(
            aggregated_importance.items(),
            key=lambda x: x[1],
            reverse=True
        ))

    # ==========================================================================
    # PRIVATE METHODS - FEATURE ENGINEERING
    # ==========================================================================
    async def _engineer_features(
        self,
        market_data: MarketData,
        task: PredictionTask,
        context: dict[str, Any] | None = None
    ) -> FeatureSet:
        """Engineer features for prediction."""
        features_dict = {}

        # Price features
        features_dict.update(self._calculate_price_features(market_data))

        # Technical indicators
        features_dict.update(self._calculate_technical_features(market_data))

        # Market structure features
        features_dict.update(self._calculate_market_structure_features(market_data))

        # Task-specific features
        if task == PredictionTask.VOLATILITY_FORECAST:
            features_dict.update(self._calculate_volatility_features(market_data))
        elif task == PredictionTask.PRICE_DIRECTION:
            features_dict.update(self._calculate_momentum_features(market_data))

        # Context features if available
        if context:
            features_dict.update(self._extract_context_features(context))

        # Add any additional features from market data
        features_dict.update(market_data.additional_features)

        # Create DataFrame
        features_df = pd.DataFrame([features_dict])
        feature_names = list(features_dict.keys())

        # Calculate feature importance (placeholder)
        feature_importance = {
            name: np.random.uniform(0, 1) for name in feature_names
        }

        return FeatureSet(
            timestamp=datetime.now(),
            features=features_df,
            feature_names=feature_names,
            feature_importance=feature_importance,
            engineering_method="standard",
            validation_score=0.0
        )

    def _calculate_price_features(self, market_data: MarketData) -> dict[str, float]:
        """Calculate price-based features."""
        features = {}

        # Basic price features
        features['price'] = market_data.close
        features['log_price'] = np.log(market_data.close)

        # Price ratios
        if market_data.open > 0:
            features['close_open_ratio'] = market_data.close / market_data.open

        # Range features
        if market_data.high > market_data.low:
            features['high_low_range'] = market_data.high - market_data.low
            features['close_range_position'] = (
                (market_data.close - market_data.low) /
                (market_data.high - market_data.low)
            )

        return features

    def _calculate_technical_features(self, market_data: MarketData) -> dict[str, float]:
        """Calculate technical indicator features."""
        features = {}

        # Simplified technical indicators
        # In production, would calculate from historical data
        features['rsi'] = 50.0  # Placeholder
        features['macd'] = 0.0  # Placeholder
        features['bb_position'] = 0.5  # Placeholder

        # Volume features
        features['volume'] = float(market_data.volume)
        features['log_volume'] = np.log(market_data.volume + 1)

        return features

    def _calculate_market_structure_features(self, market_data: MarketData) -> dict[str, float]:
        """Calculate market structure features."""
        features = {}

        # Time-based features
        now = datetime.now()
        features['hour'] = now.hour
        features['day_of_week'] = now.weekday()
        features['minutes_since_open'] = (now.hour - 9.5) * 60 + now.minute

        # Volatility features
        features['volatility'] = market_data.volatility
        features['volatility_squared'] = market_data.volatility ** 2

        return features

    def _calculate_volatility_features(self, market_data: MarketData) -> dict[str, float]:
        """Calculate volatility-specific features."""
        features = {}

        # Historical volatility ratios (placeholders)
        features['vol_5d_20d_ratio'] = 1.0
        features['vol_percentile'] = 0.5
        features['vol_trend'] = 0.0

        return features

    def _calculate_momentum_features(self, market_data: MarketData) -> dict[str, float]:
        """Calculate momentum features."""
        features = {}

        # Momentum indicators (placeholders)
        features['momentum_1d'] = 0.0
        features['momentum_5d'] = 0.0
        features['momentum_acceleration'] = 0.0

        return features

    def _extract_context_features(self, context: dict[str, Any]) -> dict[str, float]:
        """Extract features from context."""
        features = {}

        # Extract numeric features from context
        for key, value in context.items():
            if isinstance(value, (int, float)):
                features[f'context_{key}'] = float(value)

        return features

    # ==========================================================================
    # PRIVATE METHODS - MODEL MANAGEMENT
    # ==========================================================================
    def _select_best_model(self, task: PredictionTask) -> str | None:
        """Select best model for task."""
        candidate_models = [
            model_id for model_id, config in self.model_configs.items()
            if config.task == task
        ]

        if not candidate_models:
            return None

        # Select based on performance
        best_model = None
        best_score = -np.inf

        for model_id in candidate_models:
            if model_id in self.model_performance:
                perf = self.model_performance[model_id]
                # Combine accuracy and Sharpe ratio
                score = perf.accuracy * 0.5 + min(perf.sharpe_ratio, 2.0) * 0.5
                score *= perf.decay_factor  # Apply decay

                if score > best_score:
                    best_score = score
                    best_model = model_id

        return best_model

    async def _train_model(
        self,
        task: PredictionTask,
        features: FeatureSet
    ) -> str | None:
        """Train new model for task."""
        # Check if we have training data
        if self.training_data.empty:
            self.logger.warning("No training data available")
            return None

        # Select model type
        if self.ollama_client:
            model_type = await self._get_ai_model_recommendation(task, features)
        else:
            model_type = self._get_default_model_type(task)

        # Create model
        model = self._create_model(model_type)

        # Prepare training data (simplified)
        X_train = self.training_data[features.feature_names].fillna(0)
        y_train = self._create_labels(task, self.training_data)

        if len(X_train) < 100:
            self.logger.warning("Insufficient training data")
            return None

        # Train model
        try:
            model.fit(X_train, y_train)

            # Generate model ID
            model_id = f"{task.value}_{model_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Store model
            self.active_models[model_id] = model

            # Create config
            self.model_configs[model_id] = ModelConfig(
                model_type=model_type,
                task=task,
                hyperparameters={},
                features=features.feature_names,
                training_window=30,
                retrain_frequency=24,
                performance_threshold=MIN_ACCURACY
            )

            # Initialize performance
            self.model_performance[model_id] = ModelPerformance(
                model_id=model_id,
                task=task,
                accuracy=0.5,  # Will be updated
                precision=0.5,
                recall=0.5,
                f1_score=0.5,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                last_updated=datetime.now()
            )

            self.logger.info("Trained new model %s", model_id)
            return model_id

        except Exception as e:
            self.logger.error("Error training model: %s", e, exc_info=True)
            return None

    def _create_model(self, model_type: ModelType) -> Any:
        """Create ML model instance."""
        if model_type == ModelType.RANDOM_FOREST:
            return RandomForestClassifier(n_estimators=100, random_state=42)
        elif model_type == ModelType.GRADIENT_BOOST:
            return GradientBoostingRegressor(n_estimators=100, random_state=42)
        elif model_type == ModelType.XGBOOST and XGBOOST_AVAILABLE:
            return xgb.XGBClassifier(n_estimators=100, random_state=42)
        elif model_type == ModelType.SVM:
            return SVC(probability=True, random_state=42)
        elif model_type == ModelType.NEURAL_NETWORK:
            return MLPClassifier(hidden_layer_sizes=(100, 50), random_state=42)
        else:  # LINEAR
            return LogisticRegression(random_state=42)

    def _create_labels(self, task: PredictionTask, data: pd.DataFrame) -> np.ndarray:
        """Create labels for training."""
        # Simplified label creation
        if task == PredictionTask.PRICE_DIRECTION:
            # Binary classification: up/down
            return (data['close'].shift(-1) > data['close']).astype(int)
        elif task == PredictionTask.VOLATILITY_FORECAST:
            # Regression: next period volatility
            return data['volatility'].shift(-1)
        else:
            # Default: random labels for demonstration
            return np.random.randint(0, 2, size=len(data))

    def _get_default_model_type(self, task: PredictionTask) -> ModelType:
        """Get default model type for task."""
        if task in [PredictionTask.PRICE_DIRECTION, PredictionTask.STRATEGY_SELECTION]:
            return ModelType.RANDOM_FOREST
        elif task == PredictionTask.VOLATILITY_FORECAST:
            return ModelType.GRADIENT_BOOST
        else:
            return ModelType.LINEAR

    def _make_prediction(
        self,
        model: Any,
        features: FeatureSet
    ) -> tuple[Any, float | None]:
        """Make prediction with model."""
        try:
            X = features.features.fillna(0)

            # Make prediction
            prediction = model.predict(X)[0]

            # Get probability if available
            probability = None
            if hasattr(model, 'predict_proba'):
                probabilities = model.predict_proba(X)[0]
                probability = max(probabilities)

            return prediction, probability

        except Exception as e:
            self.logger.error("Error making prediction: %s", e, exc_info=True)
            return 0, None

    def _calculate_confidence(
        self,
        model_id: str,
        probability: float | None,
        features: FeatureSet
    ) -> float:
        """Calculate prediction confidence."""
        confidence = 0.5  # Base confidence

        # Factor in probability
        if probability is not None:
            confidence = probability

        # Factor in model performance
        if model_id in self.model_performance:
            perf = self.model_performance[model_id]
            confidence *= (perf.accuracy * perf.decay_factor)

        # Factor in feature quality
        if features.validation_score > 0:
            confidence *= features.validation_score

        return min(max(confidence, 0.0), 1.0)

    def _get_fallback_prediction(
        self,
        task: PredictionTask,
        market_data: MarketData
    ) -> Prediction:
        """Get fallback prediction when no model available."""
        if task == PredictionTask.PRICE_DIRECTION:
            # Simple trend following
            prediction = 1 if market_data.close > market_data.open else 0
        elif task == PredictionTask.VOLATILITY_FORECAST:
            # Use current volatility
            prediction = market_data.volatility
        else:
            prediction = 0

        return Prediction(
            timestamp=datetime.now(),
            task=task,
            prediction=prediction,
            probability=None,
            confidence=0.3,
            model_used="fallback",
            features_used=[],
            explanation="Fallback prediction - no trained model available"
        )

    # ==========================================================================
    # PRIVATE METHODS - MODEL OPTIMIZATION
    # ==========================================================================
    def _should_retrain(self, model_id: str) -> bool:
        """Check if model should be retrained."""
        if model_id not in self.model_performance:
            return True

        perf = self.model_performance[model_id]
        config = self.model_configs.get(model_id)

        if not config:
            return False

        # Check time since last update
        hours_since_update = (datetime.now() - perf.last_updated).total_seconds() / 3600
        if hours_since_update > config.retrain_frequency:
            return True

        # Check performance decay
        if perf.decay_factor < MODEL_DECAY_THRESHOLD:
            return True

        # Check accuracy threshold
        return perf.accuracy < config.performance_threshold

    def _get_recent_training_data(self, window_days: int) -> pd.DataFrame:
        """Get recent training data."""
        if self.training_data.empty:
            return pd.DataFrame()

        # Filter to recent data
        cutoff = datetime.now() - timedelta(days=window_days)

        # Assuming training_data has a timestamp column
        if 'timestamp' in self.training_data.columns:
            return self.training_data[self.training_data['timestamp'] > cutoff]
        else:
            # Return last N rows
            return self.training_data.tail(window_days * 390)  # ~390 minutes per day

    async def _retrain_model(
        self,
        model_id: str,
        data: pd.DataFrame,
        config: ModelConfig
    ) -> dict[str, float]:
        """Retrain existing model."""
        if model_id not in self.active_models:
            return {}

        try:
            # Get features
            X = data[config.features].fillna(0)
            y = self._create_labels(config.task, data)

            # Split data
            split_point = int(len(X) * 0.8)
            X_train, X_test = X[:split_point], X[split_point:]
            y_train, y_test = y[:split_point], y[split_point:]

            # Retrain model
            model = self.active_models[model_id]
            model.fit(X_train, y_train)

            # Evaluate
            predictions = model.predict(X_test)
            accuracy = accuracy_score(y_test, predictions)

            # Update performance
            self.model_performance[model_id].accuracy = accuracy
            self.model_performance[model_id].last_updated = datetime.now()
            self.model_performance[model_id].decay_factor = 1.0

            return {'accuracy': accuracy}

        except Exception as e:
            self.logger.error("Error retraining model %s: %s", model_id, e, exc_info=True)
            return {}

    def _update_model_performance(self, model_id: str):
        """Update model performance metrics."""
        if model_id in self.model_performance:
            perf = self.model_performance[model_id]

            # Apply time decay
            hours_since_update = (datetime.now() - perf.last_updated).total_seconds() / 3600
            decay_rate = 0.99  # 1% decay per hour
            perf.decay_factor *= (decay_rate ** hours_since_update)

            # Update timestamp
            perf.last_updated = datetime.now()

    def _identify_underperforming_models(self) -> list[str]:
        """Identify models that should be removed."""
        models_to_remove = []

        for model_id, perf in self.model_performance.items():
            # Remove if accuracy too low
            if perf.accuracy < MIN_ACCURACY or perf.decay_factor < 0.5 or perf.sharpe_ratio < 0 and perf.max_drawdown > 0.1:  # noqa: E501
                models_to_remove.append(model_id)

        return models_to_remove

    def _remove_model(self, model_id: str):
        """Remove model from active models."""
        if model_id in self.active_models:
            del self.active_models[model_id]
        if model_id in self.model_configs:
            del self.model_configs[model_id]
        if model_id in self.model_performance:
            del self.model_performance[model_id]

        self.logger.info("Removed model %s", model_id)

    # ==========================================================================
    # PRIVATE METHODS - RESEARCH
    # ==========================================================================
    async def _test_model_approach(
        self,
        model_type: ModelType,
        data: pd.DataFrame,
        hypothesis: str
    ) -> dict[str, float]:
        """Test a specific model approach."""
        try:
            # Create model
            model = self._create_model(model_type)

            # Prepare data (simplified)
            # In production, would use proper feature engineering
            feature_cols = [col for col in data.columns if col not in ['timestamp', 'target']]
            X = data[feature_cols].fillna(0)

            # Create target based on hypothesis
            if 'volatility' in hypothesis.lower():
                y = data['volatility'].shift(-1).fillna(data['volatility'].mean())
            elif 'direction' in hypothesis.lower():
                y = (data['close'].shift(-1) > data['close']).astype(int)
            else:
                y = np.random.randint(0, 2, size=len(data))

            # Time series cross-validation
            tscv = TimeSeriesSplit(n_splits=CV_FOLDS)
            scores = cross_val_score(model, X, y, cv=tscv, scoring='accuracy')

            return {
                'score': scores.mean(),
                'std': scores.std(),
                'scores': scores.tolist()
            }

        except Exception as e:
            self.logger.error("Error testing %s: %s", model_type.value, e, exc_info=True)
            return {'score': 0.0, 'std': 0.0, 'scores': []}

    def _generate_research_insights(
        self,
        results: dict[str, dict[str, float]],
        hypothesis: str
    ) -> list[str]:
        """Generate insights from research results."""
        insights = []

        # Find best and worst models
        if results:
            sorted_models = sorted(results.items(), key=lambda x: x[1]['score'], reverse=True)
            best_model = sorted_models[0]
            worst_model = sorted_models[-1]

            insights.append(
                f"Best model for {hypothesis}: {best_model[0]} "
                f"(score: {best_model[1]['score']:.3f})"
            )

            if len(sorted_models) > 1:
                insights.append(
                    f"Worst model: {worst_model[0]} "
                    f"(score: {worst_model[1]['score']:.3f})"
                )

            # Check if any model is significantly better
            scores = [r['score'] for r in results.values()]
            if max(scores) - min(scores) > 0.1:
                insights.append("Significant performance difference between models")
            else:
                insights.append("All models perform similarly - consider ensemble approach")

        return insights

    def _get_basic_recommendations(self, results: dict[str, dict[str, float]]) -> list[str]:
        """Get basic recommendations from research."""
        recommendations = []

        if results:
            # Get best model
            best_model = max(results.items(), key=lambda x: x[1]['score'])[0]
            recommendations.append(f"Deploy {best_model} model for production")

            # Check if ensemble would help
            scores = [r['score'] for r in results.values()]
            if len(scores) > 2 and min(scores) > 0.5:
                recommendations.append("Consider ensemble approach combining top models")

            # Feature engineering recommendation
            if max(scores) < 0.6:
                recommendations.append("Improve feature engineering for better performance")

        return recommendations

    # ==========================================================================
    # PRIVATE METHODS - AI INTEGRATION
    # ==========================================================================
    async def _get_prediction_explanation(
        self,
        task: PredictionTask,
        prediction: Any,
        features: FeatureSet,
        context: dict[str, Any] | None = None
    ) -> str:
        """Get AI explanation for prediction."""
        try:
            # Get top features
            top_features = sorted(
                features.feature_importance.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]

            features_str = "\n".join([f"- {k}: {v:.3f}" for k, v in top_features])

            prompt = f"""Explain this ML prediction for options trading:

Task: {task.value}
Prediction: {prediction}
Confidence: {features.validation_score:.2%}

Top Features:
{features_str}

Provide a brief, clear explanation of what this prediction means for a trader."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': 200
                }
            )

            return response['response'].strip()

        except Exception as e:
            self.logger.error("Error getting prediction explanation: %s", e, exc_info=True)
            return f"{task.value} prediction: {prediction}"

    async def _get_ai_research_plan(
        self,
        hypothesis: str,
        data: pd.DataFrame
    ) -> dict[str, Any]:
        """Get AI guidance on research approach."""
        try:
            data_summary = f"Data shape: {data.shape}, Columns: {list(data.columns)[:10]}"

            prompt = f"""You are an ML research expert for options trading.

Research Hypothesis: {hypothesis}
{data_summary}

Suggest which ML models and features to test. Format as JSON:
{{"models": ["model_type1", "model_type2"], "features": ["feature1", "feature2"]}}"""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )

            return self._parse_json_response(response['response'])

        except Exception as e:
            self.logger.error("Error getting AI research plan: %s", e, exc_info=True)
            return {'models': list(ModelType), 'features': []}

    async def _get_ai_model_recommendation(
        self,
        task: PredictionTask,
        features: FeatureSet
    ) -> ModelType:
        """Get AI recommendation for model type."""
        try:
            feature_summary = f"Number of features: {len(features.feature_names)}"

            prompt = f"""Recommend the best ML model type for this prediction task:

Task: {task.value}
{feature_summary}
Features include: {', '.join(features.feature_names[:10])}

Choose from: random_forest, gradient_boost, xgboost, svm, neural_network, linear

Respond with just the model type name."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': 0.1,
                    'num_predict': 50
                }
            )

            model_name = response['response'].strip().lower()

            # Map to ModelType
            for model_type in ModelType:
                if model_type.value == model_name:
                    return model_type

            return ModelType.RANDOM_FOREST  # Default

        except Exception as e:
            self.logger.error("Error getting AI model recommendation: %s", e, exc_info=True)
            return ModelType.RANDOM_FOREST

    async def _get_ai_research_recommendations(
        self,
        hypothesis: str,
        results: dict[str, dict[str, float]],
        insights: list[str]
    ) -> list[str]:
        """Get AI recommendations from research results."""
        try:
            results_str = "\n".join([
                f"{model}: {perf['score']:.3f}"
                for model, perf in results.items()
            ])
            insights_str = "\n".join(insights)

            prompt = f"""Based on ML research results for options trading:

Hypothesis: {hypothesis}

Results:
{results_str}

Insights:
{insights_str}

Provide 3-5 actionable recommendations for implementing these findings in production trading."""

            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': self.temperature,
                    'num_predict': MAX_TOKENS
                }
            )

            # Parse recommendations
            text = response['response']
            recommendations = []

            # Simple parsing - split by newlines and bullets
            for line in text.split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # Clean up the line
                    clean_line = line.lstrip('0123456789.-•').strip()
                    if clean_line:
                        recommendations.append(clean_line)

            return recommendations[:5]  # Max 5 recommendations

        except Exception as e:
            self.logger.error("Error getting AI research recommendations: %s", e, exc_info=True)
            return self._get_basic_recommendations(results)

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response."""
        try:
            if '{' in response and '}' in response:
                start = response.find('{')
                end = response.rfind('}') + 1
                json_str = response[start:end]
                return json.loads(json_str)
        except Exception as e:
            self.logger.debug("Failed to parse JSON from LLM response: %s", e)

        return {}

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def add_training_data(self, data: pd.DataFrame):
        """Add new training data."""
        self.training_data = pd.concat([self.training_data, data], ignore_index=True)

        # Keep only recent data (e.g., last 6 months)
        if len(self.training_data) > 50000:
            self.training_data = self.training_data.tail(50000)

    def save_models(self):
        """Save all models to disk."""
        for model_id, model in self.active_models.items():
            model_path = self.model_dir / f"{model_id}.pkl"
            joblib.dump(model, model_path)
            self.logger.info("Saved model %s", model_id)

    def load_models(self):
        """Load models from disk."""
        for model_path in self.model_dir.glob("*.pkl"):
            try:
                model_id = model_path.stem
                model = joblib.load(model_path)
                self.active_models[model_id] = model
                self.logger.info("Loaded model %s", model_id)
            except Exception as e:
                self.logger.error("Error loading model %s: %s", model_path, e, exc_info=True)

    def clear_history(self):
        """Clear experiment history."""
        self.experiment_history.clear()
        self.prediction_buffer.clear()
        self.logger.info("ML research history cleared")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_ml_research_agent(config: dict[str, Any] | None = None) -> SpyderX05_MLResearchAgent:
    """
    Factory function to create ML Research Agent.

    Args:
        config: Optional configuration dictionary

    Returns:
        Configured SpyderX05_MLResearchAgent instance
    """
    return SpyderX05_MLResearchAgent(config)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
# Module-level initialization code
_module_instance: SpyderX05_MLResearchAgent | None = None

def get_module_instance(config: dict[str, Any] | None = None) -> SpyderX05_MLResearchAgent:
    """
    Get singleton instance of the module.

    Args:
        config: Configuration if creating new instance

    Returns:
        Module instance
    """
    global _module_instance
    if _module_instance is None:
        _module_instance = SpyderX05_MLResearchAgent(config)
    return _module_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    async def test_agent():
        """Test the ML Research Agent."""
        # Create agent
        config = {
            'llm_model': 'llama3.2:3b-instruct-q4_K_M',
            'temperature': 0.3,
            'max_concurrent_models': 10,
            'model_directory': './test_models'
        }

        agent = create_ml_research_agent(config)

        # Create sample market data
        market_data = MarketData(
            timestamp=datetime.now(),
            open=549.50,
            high=551.00,
            low=548.00,
            close=550.25,
            volume=85000000,
            volatility=16.5,
            additional_features={
                'vix': 15.8,
                'put_call_ratio': 0.85,
                'rsi': 55.2
            }
        )

        # Test prediction

        prediction = await agent.predict(
            PredictionTask.PRICE_DIRECTION,
            market_data,
            {'market_regime': 'bullish', 'trend_strength': 0.6}
        )

        if prediction.explanation:
            pass

        # Test research

        # Create sample training data
        dates = pd.date_range(end=datetime.now(), periods=1000, freq='5min')
        sample_data = pd.DataFrame({
            'timestamp': dates,
            'close': np.random.randn(1000).cumsum() + 550,
            'volume': np.random.randint(1000000, 5000000, 1000),
            'volatility': np.random.uniform(10, 25, 1000),
            'rsi': np.random.uniform(30, 70, 1000),
            'macd': np.random.randn(1000) * 0.5
        })

        agent.add_training_data(sample_data)

        research = await agent.conduct_research(
            "Can ML models predict short-term price direction using technical indicators?"
        )


        if research.insights:
            for _insight in research.insights:
                pass

        if research.recommendations:
            for _rec in research.recommendations:
                pass

        # Test model optimization

        await agent.optimize_models()

        # Show model inventory
        inventory = agent.get_model_inventory()
        for _model_id, _info in inventory['models'].items():
            pass

    # Run test
    asyncio.run(test_agent())
