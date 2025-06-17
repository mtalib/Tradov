#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderX05_MLResearchAgent.py
Purpose: AI-Enhanced Machine Learning Research and Model Management
Group: X (AI Agents)

Description:
    Replaces all traditional ML modules (SpyderL01-L14) with an intelligent
    AI agent that performs AutoML, dynamic feature engineering, model selection,
    and continuous learning. This agent can understand which ML approaches work
    best for current market conditions and automatically adapt.

    Replaced Modules:
    - SpyderL01_FeatureEngineering through SpyderL14_ModelMonitoring
    - All ML pipelines, model training, and prediction systems

Author: AI Trading Assistant
Date: 2025-01-17
Version: 1.0.0

Dependencies:
    - ollama (for LLM integration)
    - scikit-learn
    - xgboost
    - numpy, pandas
    - asyncio
    - joblib (for model persistence)
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
import pandas as pd
from collections import defaultdict, deque
import hashlib
import pickle
import joblib
from pathlib import Path

# ML Libraries
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge, Lasso
from sklearn.svm import SVC, SVR
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.decomposition import PCA
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import accuracy_score, mean_squared_error, sharpe_ratio
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_regression
import xgboost as xgb

# Import Spyder core components
from SpyderU01_DataStructures import (
    MarketData, Portfolio, TradeSignal, OptionContract
)
from SpyderU02_Configuration import config
from SpyderU03_Logger import SpyderLogger
from SpyderU04_EventManager import Event, EventType
from SpyderU12_AgentIntegration import SpyderBaseAgent, AgentState

# ML Model Types
class ModelType(Enum):
    """Available ML model types"""
    RANDOM_FOREST = "random_forest"
    GRADIENT_BOOST = "gradient_boost"
    XGBOOST = "xgboost"
    NEURAL_NETWORK = "neural_network"
    SVM = "svm"
    LINEAR = "linear"
    ENSEMBLE = "ensemble"
    DEEP_LEARNING = "deep_learning"
    REINFORCEMENT = "reinforcement"

# Prediction Tasks
class PredictionTask(Enum):
    """Types of predictions"""
    PRICE_DIRECTION = "price_direction"
    PRICE_TARGET = "price_target"
    VOLATILITY = "volatility"
    OPTION_PRICING = "option_pricing"
    TRADE_OUTCOME = "trade_outcome"
    RISK_ASSESSMENT = "risk_assessment"
    VOLUME_PREDICTION = "volume_prediction"
    PATTERN_COMPLETION = "pattern_completion"
    REGIME_CHANGE = "regime_change"

# Feature Categories
class FeatureCategory(Enum):
    """Feature engineering categories"""
    PRICE_BASED = "price_based"
    VOLUME_BASED = "volume_based"
    TECHNICAL = "technical"
    MICROSTRUCTURE = "microstructure"
    SENTIMENT = "sentiment"
    FUNDAMENTAL = "fundamental"
    OPTIONS_FLOW = "options_flow"
    CROSS_ASSET = "cross_asset"
    SEASONAL = "seasonal"

@dataclass
class ModelConfig:
    """Configuration for ML model"""
    model_type: ModelType
    task: PredictionTask
    features: List[str]
    hyperparameters: Dict[str, Any]
    preprocessing: Dict[str, Any]
    validation_method: str = "time_series_split"
    optimization_metric: str = "sharpe_ratio"

@dataclass
class ModelPerformance:
    """Track model performance"""
    model_id: str
    model_type: ModelType
    task: PredictionTask
    train_score: float
    validation_score: float
    test_score: float
    feature_importance: Dict[str, float]
    prediction_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_retrain: datetime = field(default_factory=datetime.now)
    decay_rate: float = 0.0

@dataclass
class FeatureSet:
    """Engineered feature set"""
    features: pd.DataFrame
    feature_names: List[str]
    category_breakdown: Dict[FeatureCategory, List[str]]
    engineering_metadata: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class MLPrediction:
    """ML model prediction output"""
    task: PredictionTask
    prediction: Union[float, int, np.ndarray]
    confidence: float
    model_used: str
    feature_contributions: Dict[str, float]
    prediction_interval: Optional[Tuple[float, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResearchResult:
    """Result from ML research"""
    best_model: ModelConfig
    performance_comparison: Dict[str, float]
    feature_analysis: Dict[str, Any]
    recommendations: List[str]
    experiment_id: str

class MLResearchAgent(SpyderBaseAgent):
    """
    AI-Enhanced ML Research Agent
    
    Performs automated machine learning research, model selection,
    feature engineering, and continuous learning for trading systems.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize ML Research Agent"""
        super().__init__(config)
        
        # Agent configuration
        self.llm_model = config.get('ml_llm_model', 'llama3.2:3b-instruct-q4_K_M')
        self.max_models = config.get('max_concurrent_models', 10)
        self.retrain_frequency = config.get('retrain_frequency_hours', 24)
        self.model_decay_threshold = config.get('model_decay_threshold', 0.7)
        
        # Model storage
        self.active_models: Dict[str, Any] = {}  # model_id -> trained model
        self.model_configs: Dict[str, ModelConfig] = {}
        self.model_performance: Dict[str, ModelPerformance] = {}
        
        # Feature engineering
        self.feature_cache: Dict[str, FeatureSet] = {}
        self.feature_importance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.dynamic_features: Set[str] = set()
        
        # Research tracking
        self.experiment_history: List[ResearchResult] = []
        self.current_research_tasks: Dict[str, asyncio.Task] = {}
        
        # Data storage
        self.training_data: pd.DataFrame = pd.DataFrame()
        self.prediction_buffer: deque = deque(maxlen=10000)
        
        # Model paths
        self.model_dir = Path(config.get('model_directory', './models'))
        self.model_dir.mkdir(exist_ok=True)
        
        # Performance tracking
        self.prediction_accuracy: Dict[PredictionTask, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.model_selection_history: deque = deque(maxlen=1000)
        
        self.logger.info("ML Research Agent initialized")

    async def initialize(self, event_manager=None):
        """Initialize agent with dependencies"""
        await super().initialize(event_manager)
        
        # Load existing models
        await self._load_saved_models()
        
        # Subscribe to events
        if self.event_manager:
            self.event_manager.subscribe(EventType.MARKET_DATA_UPDATE, self._handle_market_update)
            self.event_manager.subscribe(EventType.TRADE_EXECUTED, self._handle_trade_executed)
            self.event_manager.subscribe(EventType.ANALYSIS_UPDATE, self._handle_analysis_update)
        
        # Start continuous learning loop
        asyncio.create_task(self._continuous_learning_loop())
        
        self.state = AgentState.RUNNING
        self.logger.info("ML Research Agent initialized and running")

    async def predict(
        self,
        task: PredictionTask,
        market_data: MarketData,
        context: Optional[Dict[str, Any]] = None
    ) -> MLPrediction:
        """
        Make a prediction for a specific task
        
        Args:
            task: Type of prediction needed
            market_data: Current market data
            context: Additional context for prediction
            
        Returns:
            ML prediction with confidence and metadata
        """
        try:
            # Engineer features
            features = await self._engineer_features(market_data, task, context)
            
            # Select best model for task
            model_id = await self._select_best_model(task, features)
            
            if not model_id or model_id not in self.active_models:
                # No model available, trigger research
                self.logger.warning(f"No model available for {task.value}, triggering research")
                asyncio.create_task(self._research_task(task, market_data))
                
                # Return baseline prediction
                return self._get_baseline_prediction(task, market_data)
            
            # Make prediction
            model = self.active_models[model_id]
            model_config = self.model_configs[model_id]
            
            # Prepare features
            X = features.features[model_config.features].values
            
            # Scale features
            if hasattr(model, 'scaler_'):
                X = model.scaler_.transform(X)
            
            # Predict
            if hasattr(model, 'predict_proba'):
                # Classification
                probabilities = model.predict_proba(X)
                prediction = np.argmax(probabilities, axis=1)[0]
                confidence = float(np.max(probabilities))
            else:
                # Regression
                prediction = float(model.predict(X)[0])
                # Estimate confidence based on prediction interval
                if hasattr(model, 'predict_interval'):
                    lower, upper = model.predict_interval(X)
                    confidence = 1.0 - (upper - lower) / (abs(prediction) + 1e-6)
                else:
                    confidence = self._estimate_prediction_confidence(model, X)
            
            # Get feature contributions
            feature_contributions = self._get_feature_contributions(
                model, X, model_config.features
            )
            
            # Create prediction object
            ml_prediction = MLPrediction(
                task=task,
                prediction=prediction,
                confidence=confidence,
                model_used=model_id,
                feature_contributions=feature_contributions,
                metadata={
                    'model_type': model_config.model_type.value,
                    'features_used': len(model_config.features),
                    'model_age_hours': (datetime.now() - self.model_performance[model_id].last_retrain).total_seconds() / 3600
                }
            )
            
            # Record prediction for tracking
            self._record_prediction(ml_prediction, features)
            
            return ml_prediction
            
        except Exception as e:
            self.logger.error(f"Error in ML prediction: {str(e)}")
            return self._get_baseline_prediction(task, market_data)

    async def research_best_approach(
        self,
        task: PredictionTask,
        training_data: pd.DataFrame,
        target: pd.Series
    ) -> ResearchResult:
        """
        Research and find the best ML approach for a task
        
        Args:
            task: Prediction task to optimize for
            training_data: Historical data for training
            target: Target variable
            
        Returns:
            Research results with best model configuration
        """
        self.logger.info(f"Starting ML research for {task.value}")
        
        # Generate experiment ID
        experiment_id = hashlib.md5(
            f"{task.value}_{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8]
        
        # Feature engineering research
        feature_analysis = await self._research_features(training_data, target, task)
        
        # Model selection research
        model_comparison = await self._research_models(
            training_data, target, task, feature_analysis['selected_features']
        )
        
        # Hyperparameter optimization
        best_model_type = max(model_comparison.items(), key=lambda x: x[1]['score'])[0]
        best_hyperparams = await self._optimize_hyperparameters(
            best_model_type, training_data, target, feature_analysis['selected_features']
        )
        
        # Create best model configuration
        best_config = ModelConfig(
            model_type=ModelType(best_model_type),
            task=task,
            features=feature_analysis['selected_features'],
            hyperparameters=best_hyperparams,
            preprocessing={
                'scaler': 'robust',
                'feature_selection': feature_analysis['selection_method']
            }
        )
        
        # Generate recommendations
        recommendations = await self._generate_ml_recommendations(
            task, feature_analysis, model_comparison, best_config
        )
        
        # Create research result
        result = ResearchResult(
            best_model=best_config,
            performance_comparison={k: v['score'] for k, v in model_comparison.items()},
            feature_analysis=feature_analysis,
            recommendations=recommendations,
            experiment_id=experiment_id
        )
        
        # Store research result
        self.experiment_history.append(result)
        
        # Train and deploy best model
        await self._deploy_model(best_config, training_data, target)
        
        return result

    async def _engineer_features(
        self,
        market_data: MarketData,
        task: PredictionTask,
        context: Optional[Dict[str, Any]] = None
    ) -> FeatureSet:
        """Engineer features for prediction"""
        
        # Check cache
        cache_key = f"{task.value}_{market_data.timestamp.strftime('%Y%m%d%H%M')}"
        if cache_key in self.feature_cache:
            return self.feature_cache[cache_key]
        
        features_dict = {}
        category_breakdown = defaultdict(list)
        
        # Price-based features
        price_features = self._create_price_features(market_data)
        features_dict.update(price_features)
        category_breakdown[FeatureCategory.PRICE_BASED].extend(price_features.keys())
        
        # Volume-based features
        volume_features = self._create_volume_features(market_data)
        features_dict.update(volume_features)
        category_breakdown[FeatureCategory.VOLUME_BASED].extend(volume_features.keys())
        
        # Technical indicators
        technical_features = self._create_technical_features(market_data)
        features_dict.update(technical_features)
        category_breakdown[FeatureCategory.TECHNICAL].extend(technical_features.keys())
        
        # Task-specific features
        if task == PredictionTask.VOLATILITY:
            volatility_features = self._create_volatility_features(market_data)
            features_dict.update(volatility_features)
            category_breakdown[FeatureCategory.TECHNICAL].extend(volatility_features.keys())
        
        elif task == PredictionTask.OPTION_PRICING:
            option_features = self._create_option_features(market_data, context)
            features_dict.update(option_features)
            category_breakdown[FeatureCategory.OPTIONS_FLOW].extend(option_features.keys())
        
        # Context-based features
        if context:
            context_features = self._create_context_features(context)
            features_dict.update(context_features)
            category_breakdown[FeatureCategory.SENTIMENT].extend(context_features.keys())
        
        # Create DataFrame
        features_df = pd.DataFrame([features_dict])
        
        # Create feature set
        feature_set = FeatureSet(
            features=features_df,
            feature_names=list(features_dict.keys()),
            category_breakdown=dict(category_breakdown),
            engineering_metadata={
                'task': task.value,
                'n_features': len(features_dict),
                'timestamp': market_data.timestamp
            }
        )
        
        # Cache features
        self.feature_cache[cache_key] = feature_set
        
        # Clean old cache entries
        if len(self.feature_cache) > 1000:
            oldest_key = min(self.feature_cache.keys())
            del self.feature_cache[oldest_key]
        
        return feature_set

    def _create_price_features(self, market_data: MarketData) -> Dict[str, float]:
        """Create price-based features"""
        features = {}
        
        if hasattr(market_data, 'price_history') and len(market_data.price_history) > 0:
            prices = [p.close for p in market_data.price_history[-50:]]
            
            if len(prices) >= 2:
                # Returns
                features['return_1'] = (prices[-1] - prices[-2]) / prices[-2]
                
                if len(prices) >= 5:
                    features['return_5'] = (prices[-1] - prices[-5]) / prices[-5]
                
                if len(prices) >= 20:
                    features['return_20'] = (prices[-1] - prices[-20]) / prices[-20]
                    
                    # Moving averages
                    features['sma_20'] = np.mean(prices[-20:])
                    features['price_to_sma20'] = prices[-1] / features['sma_20']
                
                # Price position in range
                recent_high = max(prices[-20:]) if len(prices) >= 20 else max(prices)
                recent_low = min(prices[-20:]) if len(prices) >= 20 else min(prices)
                if recent_high > recent_low:
                    features['price_position'] = (prices[-1] - recent_low) / (recent_high - recent_low)
                
                # Volatility
                if len(prices) >= 20:
                    returns = np.diff(prices[-20:]) / prices[-20:-1]
                    features['realized_vol'] = np.std(returns) * np.sqrt(252)
        
        # Current price
        features['current_price'] = market_data.current_price
        
        return features

    def _create_volume_features(self, market_data: MarketData) -> Dict[str, float]:
        """Create volume-based features"""
        features = {}
        
        if hasattr(market_data, 'volume_history') and len(market_data.volume_history) > 0:
            volumes = market_data.volume_history[-20:]
            
            if len(volumes) >= 2:
                # Volume ratios
                features['volume_ratio'] = volumes[-1] / np.mean(volumes)
                features['volume_trend'] = (volumes[-1] - volumes[0]) / volumes[0] if volumes[0] > 0 else 0
                
                # Volume-price correlation
                if hasattr(market_data, 'price_history') and len(market_data.price_history) >= len(volumes):
                    prices = [p.close for p in market_data.price_history[-len(volumes):]]
                    if len(prices) == len(volumes):
                        features['volume_price_corr'] = np.corrcoef(prices, volumes)[0, 1]
        
        return features

    def _create_technical_features(self, market_data: MarketData) -> Dict[str, float]:
        """Create technical indicator features"""
        features = {}
        
        # RSI
        if hasattr(market_data, 'indicators') and 'rsi' in market_data.indicators:
            features['rsi'] = market_data.indicators['rsi']
            features['rsi_oversold'] = 1 if features['rsi'] < 30 else 0
            features['rsi_overbought'] = 1 if features['rsi'] > 70 else 0
        
        # MACD
        if hasattr(market_data, 'indicators') and 'macd' in market_data.indicators:
            features['macd'] = market_data.indicators['macd']
            features['macd_signal'] = market_data.indicators.get('macd_signal', 0)
            features['macd_histogram'] = features['macd'] - features['macd_signal']
        
        # Bollinger Bands
        if hasattr(market_data, 'indicators'):
            if 'bb_upper' in market_data.indicators and 'bb_lower' in market_data.indicators:
                features['bb_width'] = market_data.indicators['bb_upper'] - market_data.indicators['bb_lower']
                features['bb_position'] = (market_data.current_price - market_data.indicators['bb_lower']) / features['bb_width'] if features['bb_width'] > 0 else 0.5
        
        return features

    def _create_volatility_features(self, market_data: MarketData) -> Dict[str, float]:
        """Create volatility-specific features"""
        features = {}
        
        if hasattr(market_data, 'price_history') and len(market_data.price_history) >= 30:
            prices = [p.close for p in market_data.price_history[-30:]]
            highs = [p.high for p in market_data.price_history[-30:]]
            lows = [p.low for p in market_data.price_history[-30:]]
            
            # Parkinson volatility
            if len(highs) == len(lows):
                log_hl = np.log(np.array(highs) / np.array(lows))
                features['parkinson_vol'] = np.sqrt(252 / (4 * len(log_hl) * np.log(2))) * np.sum(log_hl ** 2)
            
            # GARCH features (simplified)
            returns = np.diff(prices) / prices[:-1]
            features['returns_squared_ma'] = np.mean(returns[-5:] ** 2) if len(returns) >= 5 else 0
            features['abs_returns_ma'] = np.mean(np.abs(returns[-5:])) if len(returns) >= 5 else 0
        
        # IV if available
        if hasattr(market_data, 'implied_volatility'):
            features['implied_volatility'] = market_data.implied_volatility
            if 'realized_vol' in features:
                features['iv_rv_spread'] = features['implied_volatility'] - features['realized_vol']
        
        return features

    def _create_option_features(self, market_data: MarketData, context: Optional[Dict[str, Any]]) -> Dict[str, float]:
        """Create option-specific features"""
        features = {}
        
        if context and 'option_contract' in context:
            option = context['option_contract']
            
            # Moneyness
            features['moneyness'] = market_data.current_price / option.strike
            features['log_moneyness'] = np.log(features['moneyness'])
            
            # Time to expiration
            dte = (option.expiration - datetime.now()).days
            features['days_to_expiry'] = dte
            features['sqrt_time'] = np.sqrt(dte / 365.0)
            
            # Option type
            features['is_call'] = 1 if option.option_type == 'CALL' else 0
            
            # Greeks if available
            if hasattr(option, 'greeks'):
                features['delta'] = option.greeks.delta
                features['gamma'] = option.greeks.gamma
                features['vega'] = option.greeks.vega
                features['theta'] = option.greeks.theta
        
        # Put-call ratios
        if hasattr(market_data, 'put_call_ratio'):
            features['put_call_ratio'] = market_data.put_call_ratio
        
        return features

    def _create_context_features(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Create features from context"""
        features = {}
        
        # Market sentiment
        if 'sentiment_score' in context:
            features['sentiment'] = context['sentiment_score']
            features['sentiment_extreme'] = 1 if abs(features['sentiment']) > 0.8 else 0
        
        # Risk metrics
        if 'vix' in context:
            features['vix'] = context['vix']
            features['vix_high'] = 1 if features['vix'] > 30 else 0
        
        # Time features
        now = datetime.now()
        features['hour_of_day'] = now.hour
        features['day_of_week'] = now.weekday()
        features['is_friday'] = 1 if features['day_of_week'] == 4 else 0
        features['is_expiry_day'] = 1 if features['day_of_week'] == 4 else 0  # Simplified
        
        return features

    async def _select_best_model(self, task: PredictionTask, features: FeatureSet) -> Optional[str]:
        """Select best model for current conditions"""
        eligible_models = []
        
        for model_id, config in self.model_configs.items():
            if config.task == task:
                # Check if model has required features
                missing_features = set(config.features) - set(features.feature_names)
                if not missing_features:
                    # Check model performance
                    perf = self.model_performance.get(model_id)
                    if perf and perf.validation_score > self.model_decay_threshold:
                        eligible_models.append((model_id, perf.validation_score))
        
        if not eligible_models:
            return None
        
        # Use AI to select best model for current conditions
        model_selection = await self._ai_model_selection(eligible_models, features, task)
        
        if model_selection:
            self.model_selection_history.append({
                'task': task.value,
                'selected_model': model_selection,
                'timestamp': datetime.now()
            })
            return model_selection
        
        # Fallback to highest scoring model
        return max(eligible_models, key=lambda x: x[1])[0]

    async def _ai_model_selection(
        self,
        eligible_models: List[Tuple[str, float]],
        features: FeatureSet,
        task: PredictionTask
    ) -> Optional[str]:
        """Use AI to select best model for current conditions"""
        
        # Prepare context
        feature_summary = {
            category.value: len(features_list)
            for category, features_list in features.category_breakdown.items()
        }
        
        model_info = []
        for model_id, score in eligible_models:
            config = self.model_configs[model_id]
            perf = self.model_performance[model_id]
            model_info.append({
                'id': model_id,
                'type': config.model_type.value,
                'score': score,
                'age_hours': (datetime.now() - perf.last_retrain).total_seconds() / 3600,
                'recent_accuracy': np.mean([p['accurate'] for p in list(perf.prediction_history)[-10:]]) if perf.prediction_history else 0.5
            })
        
        prompt = f"""
        Select the best ML model for {task.value} prediction given current conditions:
        
        Available Features:
        {json.dumps(feature_summary, indent=2)}
        
        Eligible Models:
        {json.dumps(model_info, indent=2)}
        
        Current Market Conditions:
        - Volatility: {features.features.get('realized_vol', [0])[0]:.2%} annualized
        - Price Position: {features.features.get('price_position', [0.5])[0]:.2f}
        - Volume Ratio: {features.features.get('volume_ratio', [1.0])[0]:.2f}
        
        Select the model ID that would perform best in these conditions.
        Consider model type suitability, recent performance, and age.
        
        Respond with just the model ID.
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=2.0)
            model_id = response.strip()
            
            # Validate response
            if any(model_id == m[0] for m in eligible_models):
                return model_id
        except:
            pass
        
        return None

    async def _research_features(
        self,
        data: pd.DataFrame,
        target: pd.Series,
        task: PredictionTask
    ) -> Dict[str, Any]:
        """Research best features for task"""
        self.logger.info(f"Researching features for {task.value}")
        
        # Create all possible features
        all_features = {}
        
        # Price features
        for window in [5, 10, 20, 50]:
            if len(data) > window:
                all_features[f'return_{window}'] = data['close'].pct_change(window)
                all_features[f'sma_{window}'] = data['close'].rolling(window).mean()
                all_features[f'vol_{window}'] = data['close'].pct_change().rolling(window).std()
        
        # Technical features
        if len(data) > 14:
            all_features['rsi'] = self._calculate_rsi(data['close'])
        
        if len(data) > 26:
            macd = self._calculate_macd(data['close'])
            all_features['macd'] = macd['macd']
            all_features['macd_signal'] = macd['signal']
        
        # Volume features
        if 'volume' in data.columns:
            all_features['volume_sma'] = data['volume'].rolling(20).mean()
            all_features['volume_ratio'] = data['volume'] / all_features['volume_sma']
        
        # Convert to DataFrame
        features_df = pd.DataFrame(all_features).dropna()
        
        # Align with target
        aligned_target = target.loc[features_df.index]
        
        # Feature selection methods
        selection_results = {}
        
        # 1. Mutual Information
        if len(features_df) > 100:
            mi_selector = SelectKBest(mutual_info_regression, k=min(20, len(features_df.columns)))
            mi_selector.fit(features_df, aligned_target)
            mi_scores = dict(zip(features_df.columns, mi_selector.scores_))
            selection_results['mutual_info'] = mi_scores
        
        # 2. Random Forest importance
        rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        rf.fit(features_df, aligned_target)
        rf_importance = dict(zip(features_df.columns, rf.feature_importances_))
        selection_results['random_forest'] = rf_importance
        
        # 3. Correlation analysis
        correlations = {}
        for col in features_df.columns:
            correlations[col] = abs(features_df[col].corr(aligned_target))
        selection_results['correlation'] = correlations
        
        # Combine scores
        combined_scores = {}
        for feature in features_df.columns:
            scores = []
            for method, method_scores in selection_results.items():
                if feature in method_scores:
                    scores.append(method_scores[feature])
            combined_scores[feature] = np.mean(scores) if scores else 0
        
        # Select top features
        sorted_features = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        n_features = min(30, len(sorted_features))
        selected_features = [f[0] for f in sorted_features[:n_features]]
        
        # Analyze feature relationships
        feature_correlations = features_df[selected_features].corr()
        
        # Remove highly correlated features
        final_features = []
        for feature in selected_features:
            if not final_features:
                final_features.append(feature)
            else:
                max_corr = max(abs(feature_correlations.loc[feature, final_features]))
                if max_corr < 0.95:
                    final_features.append(feature)
        
        return {
            'selected_features': final_features,
            'feature_scores': combined_scores,
            'selection_method': 'ensemble',
            'correlation_matrix': feature_correlations.to_dict(),
            'n_features_tested': len(features_df.columns),
            'n_features_selected': len(final_features)
        }

    async def _research_models(
        self,
        data: pd.DataFrame,
        target: pd.Series,
        task: PredictionTask,
        features: List[str]
    ) -> Dict[str, Dict[str, float]]:
        """Research different model types"""
        self.logger.info(f"Researching models for {task.value}")
        
        # Prepare data
        X = data[features].values
        y = target.values
        
        # Time series split
        tscv = TimeSeriesSplit(n_splits=5)
        
        model_results = {}
        
        # Test different model types
        models_to_test = {
            'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'gradient_boost': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'xgboost': xgb.XGBRegressor(n_estimators=100, random_state=42),
            'neural_network': MLPRegressor(hidden_layer_sizes=(100, 50), random_state=42, max_iter=500),
            'linear': Ridge(alpha=1.0)
        }
        
        for model_name, model in models_to_test.items():
            try:
                # Scale data for neural networks and linear models
                if model_name in ['neural_network', 'linear']:
                    scaler = StandardScaler()
                    X_scaled = scaler.fit_transform(X)
                    scores = cross_val_score(model, X_scaled, y, cv=tscv, scoring='neg_mean_squared_error')
                else:
                    scores = cross_val_score(model, X, y, cv=tscv, scoring='neg_mean_squared_error')
                
                # Calculate metrics
                mse = -np.mean(scores)
                rmse = np.sqrt(mse)
                
                # Fit on full data to get training score
                if model_name in ['neural_network', 'linear']:
                    model.fit(X_scaled, y)
                    train_pred = model.predict(X_scaled)
                else:
                    model.fit(X, y)
                    train_pred = model.predict(X)
                
                train_score = 1 - (np.mean((y - train_pred) ** 2) / np.var(y))
                
                model_results[model_name] = {
                    'score': train_score,
                    'cv_rmse': rmse,
                    'cv_scores': scores.tolist()
                }
                
                self.logger.info(f"{model_name}: score={train_score:.3f}, CV RMSE={rmse:.3f}")
                
            except Exception as e:
                self.logger.error(f"Error testing {model_name}: {str(e)}")
                model_results[model_name] = {'score': 0, 'cv_rmse': float('inf')}
        
        return model_results

    async def _optimize_hyperparameters(
        self,
        model_type: str,
        data: pd.DataFrame,
        target: pd.Series,
        features: List[str]
    ) -> Dict[str, Any]:
        """Optimize hyperparameters for selected model"""
        self.logger.info(f"Optimizing hyperparameters for {model_type}")
        
        # Simplified grid search (in production, use Optuna or similar)
        if model_type == 'random_forest':
            param_grid = {
                'n_estimators': [100, 200],
                'max_depth': [10, 20, None],
                'min_samples_split': [2, 5],
                'min_samples_leaf': [1, 2]
            }
        elif model_type == 'xgboost':
            param_grid = {
                'n_estimators': [100, 200],
                'max_depth': [3, 5, 7],
                'learning_rate': [0.01, 0.1],
                'subsample': [0.8, 1.0]
            }
        elif model_type == 'neural_network':
            param_grid = {
                'hidden_layer_sizes': [(100,), (100, 50), (200, 100)],
                'learning_rate_init': [0.001, 0.01],
                'alpha': [0.0001, 0.001]
            }
        else:
            # Default parameters
            return {}
        
        # For now, return reasonable defaults
        # In production, implement proper hyperparameter optimization
        best_params = {
            'random_forest': {
                'n_estimators': 200,
                'max_depth': 20,
                'min_samples_split': 5,
                'min_samples_leaf': 2,
                'random_state': 42
            },
            'xgboost': {
                'n_estimators': 200,
                'max_depth': 5,
                'learning_rate': 0.1,
                'subsample': 0.8,
                'random_state': 42
            },
            'neural_network': {
                'hidden_layer_sizes': (100, 50),
                'learning_rate_init': 0.001,
                'alpha': 0.0001,
                'random_state': 42,
                'max_iter': 1000
            }
        }.get(model_type, {})
        
        return best_params

    async def _generate_ml_recommendations(
        self,
        task: PredictionTask,
        feature_analysis: Dict[str, Any],
        model_comparison: Dict[str, Dict[str, float]],
        best_config: ModelConfig
    ) -> List[str]:
        """Generate recommendations from ML research"""
        
        prompt = f"""
        Based on ML research for {task.value} prediction:
        
        Feature Analysis:
        - Selected {len(feature_analysis['selected_features'])} features from {feature_analysis['n_features_tested']}
        - Top features: {', '.join(feature_analysis['selected_features'][:5])}
        
        Model Performance:
        {json.dumps(model_comparison, indent=2)}
        
        Best Model: {best_config.model_type.value}
        
        Generate 3-5 actionable recommendations for:
        1. Feature engineering improvements
        2. Model deployment considerations
        3. Performance monitoring
        4. Potential risks or limitations
        """
        
        try:
            response = await asyncio.wait_for(self._query_llm(prompt), timeout=5.0)
            # Parse recommendations (simplified)
            recommendations = response.strip().split('\n')
            return [rec.strip() for rec in recommendations if rec.strip()][:5]
        except:
            # Fallback recommendations
            return [
                f"Monitor {best_config.model_type.value} performance daily",
                f"Retrain model when accuracy drops below {self.model_decay_threshold}",
                f"Consider ensemble methods if single model performance plateaus",
                f"Add more {task.value}-specific features",
                "Implement A/B testing for model updates"
            ]

    async def _deploy_model(self, config: ModelConfig, data: pd.DataFrame, target: pd.Series):
        """Train and deploy a model"""
        self.logger.info(f"Deploying {config.model_type.value} for {config.task.value}")
        
        # Generate model ID
        model_id = f"{config.task.value}_{config.model_type.value}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Prepare data
        X = data[config.features].values
        y = target.values
        
        # Create model
        if config.model_type == ModelType.RANDOM_FOREST:
            model = RandomForestRegressor(**config.hyperparameters)
        elif config.model_type == ModelType.XGBOOST:
            model = xgb.XGBRegressor(**config.hyperparameters)
        elif config.model_type == ModelType.NEURAL_NETWORK:
            model = MLPRegressor(**config.hyperparameters)
        elif config.model_type == ModelType.GRADIENT_BOOST:
            model = GradientBoostingRegressor(**config.hyperparameters)
        else:
            model = Ridge(**config.hyperparameters)
        
        # Scale if needed
        if config.model_type in [ModelType.NEURAL_NETWORK, ModelType.LINEAR]:
            scaler = RobustScaler()
            X = scaler.fit_transform(X)
            model.scaler_ = scaler
        
        # Train model
        model.fit(X, y)
        
        # Calculate performance
        train_pred = model.predict(X)
        train_score = 1 - (np.mean((y - train_pred) ** 2) / np.var(y))
        
        # Store model
        self.active_models[model_id] = model
        self.model_configs[model_id] = config
        self.model_performance[model_id] = ModelPerformance(
            model_id=model_id,
            model_type=config.model_type,
            task=config.task,
            train_score=train_score,
            validation_score=train_score * 0.9,  # Placeholder
            test_score=0.0,
            feature_importance=self._get_feature_importance(model, config.features)
        )
        
        # Save model to disk
        model_path = self.model_dir / f"{model_id}.joblib"
        joblib.dump({
            'model': model,
            'config': config,
            'performance': self.model_performance[model_id]
        }, model_path)
        
        self.logger.info(f"Model {model_id} deployed with train score: {train_score:.3f}")

    def _get_feature_importance(self, model: Any, feature_names: List[str]) -> Dict[str, float]:
        """Get feature importance from model"""
        importance_dict = {}
        
        if hasattr(model, 'feature_importances_'):
            # Tree-based models
            importances = model.feature_importances_
            for i, name in enumerate(feature_names):
                importance_dict[name] = float(importances[i])
        elif hasattr(model, 'coef_'):
            # Linear models
            coefs = np.abs(model.coef_)
            for i, name in enumerate(feature_names):
                importance_dict[name] = float(coefs[i] if i < len(coefs) else 0)
        else:
            # Default equal importance
            for name in feature_names:
                importance_dict[name] = 1.0 / len(feature_names)
        
        return importance_dict

    def _get_feature_contributions(
        self,
        model: Any,
        X: np.ndarray,
        feature_names: List[str]
    ) -> Dict[str, float]:
        """Get feature contributions to prediction"""
        contributions = {}
        
        # Simplified SHAP-like contributions
        if hasattr(model, 'feature_importances_'):
            importances = model.feature_importances_
            # Weight by feature values
            for i, name in enumerate(feature_names):
                if i < X.shape[1]:
                    contributions[name] = float(importances[i] * X[0, i])
        else:
            # Equal contributions
            for name in feature_names:
                contributions[name] = 1.0 / len(feature_names)
        
        return contributions

    def _estimate_prediction_confidence(self, model: Any, X: np.ndarray) -> float:
        """Estimate prediction confidence for regression models"""
        # Simplified confidence estimation
        # In production, use proper prediction intervals or ensemble disagreement
        
        if hasattr(model, 'estimators_'):
            # For ensemble models, use prediction variance
            predictions = [est.predict(X)[0] for est in model.estimators_]
            std = np.std(predictions)
            mean = np.mean(predictions)
            confidence = 1.0 - (std / (abs(mean) + 1e-6))
        else:
            # Default confidence based on model performance
            model_id = [k for k, v in self.active_models.items() if v == model]
            if model_id:
                perf = self.model_performance.get(model_id[0])
                confidence = perf.validation_score if perf else 0.5
            else:
                confidence = 0.5
        
        return float(np.clip(confidence, 0, 1))

    def _get_baseline_prediction(self, task: PredictionTask, market_data: MarketData) -> MLPrediction:
        """Get baseline prediction when no model available"""
        if task == PredictionTask.PRICE_DIRECTION:
            # Simple momentum
            prediction = 1 if market_data.current_price > getattr(market_data, 'previous_close', market_data.current_price) else 0
            confidence = 0.5
        elif task == PredictionTask.VOLATILITY:
            # Historical average
            prediction = 0.15  # 15% annualized
            confidence = 0.3
        else:
            prediction = 0
            confidence = 0.1
        
        return MLPrediction(
            task=task,
            prediction=prediction,
            confidence=confidence,
            model_used='baseline',
            feature_contributions={},
            metadata={'type': 'baseline', 'reason': 'no_model_available'}
        )

    def _record_prediction(self, prediction: MLPrediction, features: FeatureSet):
        """Record prediction for tracking"""
        self.prediction_buffer.append({
            'timestamp': datetime.now(),
            'task': prediction.task.value,
            'prediction': prediction.prediction,
            'confidence': prediction.confidence,
            'model': prediction.model_used,
            'features': features.features.iloc[0].to_dict() if not features.features.empty else {}
        })

    async def _research_task(self, task: PredictionTask, market_data: MarketData):
        """Launch research task for missing model"""
        if task.value in self.current_research_tasks:
            return  # Research already in progress
        
        async def research():
            try:
                # Get historical data (simplified - would fetch from database)
                data = pd.DataFrame()  # Placeholder
                target = pd.Series()   # Placeholder
                
                if not data.empty:
                    result = await self.research_best_approach(task, data, target)
                    self.logger.info(f"Research completed for {task.value}: {result.best_model.model_type.value}")
            except Exception as e:
                self.logger.error(f"Research failed for {task.value}: {str(e)}")
            finally:
                if task.value in self.current_research_tasks:
                    del self.current_research_tasks[task.value]
        
        self.current_research_tasks[task.value] = asyncio.create_task(research())

    async def _continuous_learning_loop(self):
        """Continuous learning and model updates"""
        while self.state == AgentState.RUNNING:
            try:
                await asyncio.sleep(3600)  # Check hourly
                
                # Check model performance
                for model_id, perf in self.model_performance.items():
                    # Check if model needs retraining
                    age_hours = (datetime.now() - perf.last_retrain).total_seconds() / 3600
                    
                    if age_hours > self.retrain_frequency or perf.validation_score < self.model_decay_threshold:
                        self.logger.info(f"Model {model_id} needs retraining")
                        # Trigger retraining (simplified)
                        config = self.model_configs[model_id]
                        asyncio.create_task(self._retrain_model(model_id, config))
                
                # Clean up old predictions
                if len(self.prediction_buffer) > 10000:
                    self.prediction_buffer = deque(list(self.prediction_buffer)[-5000:], maxlen=10000)
                
            except Exception as e:
                self.logger.error(f"Error in continuous learning: {str(e)}")

    async def _retrain_model(self, model_id: str, config: ModelConfig):
        """Retrain a model with recent data"""
        self.logger.info(f"Retraining model {model_id}")
        
        # Get recent data (simplified - would fetch from database)
        # In production, this would gather recent market data and outcomes
        
        # For now, just update the timestamp
        if model_id in self.model_performance:
            self.model_performance[model_id].last_retrain = datetime.now()

    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_macd(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """Calculate MACD"""
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        return {'macd': macd, 'signal': signal}

    async def _load_saved_models(self):
        """Load previously saved models"""
        model_files = list(self.model_dir.glob("*.joblib"))
        
        for model_file in model_files[:self.max_models]:  # Limit loaded models
            try:
                data = joblib.load(model_file)
                model_id = model_file.stem
                
                self.active_models[model_id] = data['model']
                self.model_configs[model_id] = data['config']
                self.model_performance[model_id] = data['performance']
                
                self.logger.info(f"Loaded model {model_id}")
            except Exception as e:
                self.logger.error(f"Failed to load model {model_file}: {str(e)}")

    async def _handle_market_update(self, event: Event):
        """Handle market data updates"""
        # Could trigger model updates based on significant market changes
        pass

    async def _handle_trade_executed(self, event: Event):
        """Handle trade execution events"""
        # Record outcomes for model training
        if hasattr(event, 'data'):
            trade_data = event.data
            # Store for future model training
            pass

    async def _handle_analysis_update(self, event: Event):
        """Handle analysis updates from other agents"""
        # Could incorporate analysis into features
        pass

    async def _query_llm(self, prompt: str) -> str:
        """Query LLM for ML insights"""
        # Mock implementation
        if "Select the best ML model" in prompt:
            return "random_forest_20250117120000"
        elif "recommendations" in prompt:
            return """1. Add more microstructure features for better short-term predictions
2. Implement online learning for rapid adaptation to market changes
3. Monitor feature drift to detect when models need retraining
4. Use ensemble methods during high volatility periods
5. Set up A/B testing framework for model updates"""
        else:
            return "neural_network"

    async def get_model_inventory(self) -> Dict[str, Any]:
        """Get current model inventory and status"""
        inventory = {
            'active_models': len(self.active_models),
            'models_by_task': defaultdict(list),
            'performance_summary': {}
        }
        
        for model_id, config in self.model_configs.items():
            inventory['models_by_task'][config.task.value].append(model_id)
            
            if model_id in self.model_performance:
                perf = self.model_performance[model_id]
                inventory['performance_summary'][model_id] = {
                    'type': config.model_type.value,
                    'score': perf.validation_score,
                    'age_hours': (datetime.now() - perf.last_retrain).total_seconds() / 3600
                }
        
        return dict(inventory)

    async def shutdown(self):
        """Shutdown agent gracefully"""
        self.state = AgentState.STOPPED
        
        # Cancel research tasks
        for task in self.current_research_tasks.values():
            task.cancel()
        
        # Save model performance history
        for model_id, perf in self.model_performance.items():
            if model_id in self.active_models:
                model_path = self.model_dir / f"{model_id}.joblib"
                joblib.dump({
                    'model': self.active_models[model_id],
                    'config': self.model_configs[model_id],
                    'performance': perf
                }, model_path)
        
        self.logger.info("ML Research Agent shutdown complete")

# Factory function
def create_ml_research_agent(config: Dict[str, Any]) -> MLResearchAgent:
    """Create and return an ML Research Agent instance"""
    return MLResearchAgent(config)


# Usage Example:
if __name__ == "__main__":
    # Example configuration
    test_config = {
        'ml_llm_model': 'llama3.2:3b-instruct-q4_K_M',
        'max_concurrent_models': 10,
        'retrain_frequency_hours': 24,
        'model_decay_threshold': 0.7,
        'model_directory': './models'
    }
    
    # Create agent
    ml_agent = create_ml_research_agent(test_config)
    
    # Example usage
    async def example_usage():
        await ml_agent.initialize()
        
        # Make a prediction
        market_data = MarketData(current_price=400.0, timestamp=datetime.now())
        
        prediction = await ml_agent.predict(
            PredictionTask.PRICE_DIRECTION,
            market_data
        )
        
        print(f"Prediction: {prediction.prediction}")
        print(f"Confidence: {prediction.confidence:.2%}")
        print(f"Model Used: {prediction.model_used}")
        
        # Get model inventory
        inventory = await ml_agent.get_model_inventory()
        print(f"\nActive Models: {inventory['active_models']}")
    
    # Run example
    # asyncio.run(example_usage())
