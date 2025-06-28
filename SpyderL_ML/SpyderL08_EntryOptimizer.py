#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderL08_EntryOptimizer.py
Group: L (Machine Learning)
Purpose: ML-based entry timing optimization

Description:
    This module uses machine learning to optimize entry timing for options trades.
    It combines regime detection, feature engineering, and predictive models to
    identify optimal entry points with high probability of success. The module
    adapts to different market regimes and provides confidence scores for entries.

Author: Mohamed Talib
Date: 2024-12-20
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import json
import pickle
from pathlib import Path
from collections import deque
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import precision_recall_curve, roc_auc_score
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
import lightgbm as lgb
from scipy.optimize import minimize
import optuna

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingCalendar
from SpyderL_ML.SpyderL10_FeatureEngineering import FeatureEngineer, FeatureSet
from SpyderL_ML.SpyderL09_RegimeClassifier import RegimeClassifier, RegimeType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Entry windows (based on research)
OPTIMAL_ENTRY_WINDOWS = {
    'morning': (time(10, 15), time(11, 40)),  # Primary window
    'afternoon': (time(14, 0), time(15, 30))  # Secondary window
}

# Model parameters
MIN_TRAINING_SAMPLES = 500
LOOKBACK_WINDOW = 20  # Bars to consider for entry
PREDICTION_HORIZON = 5  # Bars ahead to predict
CONFIDENCE_THRESHOLD = 0.65  # Minimum confidence for entry

# Feature importance threshold
FEATURE_IMPORTANCE_THRESHOLD = 0.01

# Optimization parameters
MAX_DAILY_ENTRIES = 3
MIN_TIME_BETWEEN_ENTRIES = 30  # minutes

# ==============================================================================
# ENUMS
# ==============================================================================
class EntrySignal(Enum):
    """Entry signal types"""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    AVOID = "avoid"
    STRONG_AVOID = "strong_avoid"

class OptimizationObjective(Enum):
    """Optimization objectives"""
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    RISK_ADJUSTED_RETURN = "risk_adjusted_return"

class ModelType(Enum):
    """ML model types"""
    RANDOM_FOREST = "random_forest"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    NEURAL_NETWORK = "neural_network"
    ENSEMBLE = "ensemble"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class EntryOpportunity:
    """Entry opportunity assessment"""
    timestamp: datetime
    signal: EntrySignal
    confidence: float
    expected_return: float
    risk_score: float
    regime: RegimeType
    features: Dict[str, float]
    reasons: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EntryFilter:
    """Entry filter criteria"""
    min_confidence: float = CONFIDENCE_THRESHOLD
    allowed_regimes: List[RegimeType] = field(default_factory=list)
    required_features: Dict[str, Tuple[float, float]] = field(default_factory=dict)  # feature: (min, max)
    time_windows: List[Tuple[time, time]] = field(default_factory=list)
    max_risk_score: float = 0.7
    min_expected_return: float = 0.01  # 1%

@dataclass
class OptimizationResult:
    """Entry optimization result"""
    optimal_parameters: Dict[str, Any]
    expected_performance: Dict[str, float]
    feature_importance: Dict[str, float]
    regime_performance: Dict[RegimeType, Dict[str, float]]
    validation_metrics: Dict[str, float]
    optimization_history: List[Dict[str, Any]] = field(default_factory=list)

# ==============================================================================
# ENTRY OPTIMIZER CLASS
# ==============================================================================
class EntryOptimizer:
    """
    ML-based entry timing optimization system.
    
    Combines multiple models and techniques to identify optimal entry points
    for options trades, adapting to market regimes and conditions.
    """
    
    def __init__(
        self,
        feature_engineer: FeatureEngineer,
        regime_classifier: RegimeClassifier,
        objective: OptimizationObjective = OptimizationObjective.RISK_ADJUSTED_RETURN
    ):
        """Initialize entry optimizer"""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # ML components
        self.feature_engineer = feature_engineer
        self.regime_classifier = regime_classifier
        self.objective = objective
        
        # Initialize models
        self.models = {}
        self._initialize_models()
        
        # Scalers
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()
        
        # Model state
        self.fitted = False
        self.feature_names = []
        self.selected_features = []
        
        # Performance tracking
        self.model_performance = {}
        self.regime_models = {}  # Regime-specific models
        
        # Entry history
        self.entry_history = deque(maxlen=1000)
        self.prediction_cache = {}
        
        # Calendar for time filtering
        self.calendar = TradingCalendar()
        
        self.logger.info("EntryOptimizer initialized")
    
    def _initialize_models(self) -> None:
        """Initialize ML models"""
        # Random Forest
        self.models['rf'] = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=50,
            class_weight='balanced',
            random_state=42
        )
        
        # XGBoost
        self.models['xgb'] = xgb.XGBClassifier(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )
        
        # LightGBM
        self.models['lgb'] = lgb.LGBMClassifier(
            n_estimators=200,
            num_leaves=31,
            learning_rate=0.1,
            feature_fraction=0.8,
            bagging_fraction=0.8,
            random_state=42
        )
        
        # Neural Network
        self.models['nn'] = MLPClassifier(
            hidden_layer_sizes=(100, 50, 25),
            activation='relu',
            solver='adam',
            alpha=0.001,
            batch_size=32,
            learning_rate='adaptive',
            max_iter=500,
            early_stopping=True,
            random_state=42
        )
    
    # ==========================================================================
    # PUBLIC METHODS - PREDICTION
    # ==========================================================================
    def predict_entry(
        self,
        current_features: FeatureSet,
        entry_filter: Optional[EntryFilter] = None
    ) -> EntryOpportunity:
        """
        Predict entry opportunity for current market conditions.
        
        Args:
            current_features: Current market features
            entry_filter: Optional entry criteria
            
        Returns:
            Entry opportunity assessment
        """
        try:
            if not self.fitted:
                self.logger.warning("Models not fitted, returning neutral signal")
                return self._get_neutral_opportunity(current_features.timestamp)
            
            # Get current regime
            regime = self.regime_classifier.classify_regime(current_features)
            
            # Apply time filter
            if entry_filter and entry_filter.time_windows:
                current_time = current_features.timestamp.time()
                in_window = any(
                    start <= current_time <= end 
                    for start, end in entry_filter.time_windows
                )
                if not in_window:
                    return self._get_avoid_opportunity(
                        current_features.timestamp,
                        "Outside trading window"
                    )
            
            # Check regime filter
            if entry_filter and entry_filter.allowed_regimes:
                if regime.regime_type not in entry_filter.allowed_regimes:
                    return self._get_avoid_opportunity(
                        current_features.timestamp,
                        f"Regime {regime.regime_type.value} not allowed"
                    )
            
            # Prepare features
            feature_array = self._prepare_features(current_features)
            
            # Get predictions from all models
            predictions = self._get_ensemble_predictions(feature_array, regime.regime_type)
            
            # Calculate entry signal
            signal, confidence = self._calculate_entry_signal(predictions)
            
            # Apply confidence filter
            if entry_filter and confidence < entry_filter.min_confidence:
                return self._get_neutral_opportunity(current_features.timestamp)
            
            # Calculate expected return and risk
            expected_return = self._calculate_expected_return(
                feature_array, 
                regime.regime_type
            )
            risk_score = self._calculate_risk_score(current_features, regime)
            
            # Apply filters
            if entry_filter:
                if risk_score > entry_filter.max_risk_score:
                    signal = EntrySignal.AVOID
                if expected_return < entry_filter.min_expected_return:
                    signal = EntrySignal.NEUTRAL
            
            # Generate reasons
            reasons = self._generate_entry_reasons(
                current_features,
                regime,
                predictions,
                signal
            )
            
            # Create opportunity
            opportunity = EntryOpportunity(
                timestamp=current_features.timestamp,
                signal=signal,
                confidence=float(confidence),
                expected_return=float(expected_return),
                risk_score=float(risk_score),
                regime=regime.regime_type,
                features=self._get_key_features(current_features),
                reasons=reasons,
                metadata={
                    'model_predictions': predictions,
                    'regime_confidence': regime.confidence
                }
            )
            
            # Cache prediction
            self._cache_prediction(opportunity)
            
            return opportunity
            
        except Exception as e:
            self.logger.error(f"Error predicting entry: {e}")
            self.error_handler.handle_error(e, "predict_entry")
            return self._get_neutral_opportunity(current_features.timestamp)
    
    def optimize_parameters(
        self,
        historical_data: pd.DataFrame,
        target_data: pd.Series,
        n_trials: int = 100
    ) -> OptimizationResult:
        """
        Optimize entry parameters using historical data.
        
        Args:
            historical_data: Historical feature data
            target_data: Target outcomes (1 for successful entry, 0 for unsuccessful)
            n_trials: Number of optimization trials
            
        Returns:
            Optimization results
        """
        try:
            self.logger.info("Starting entry parameter optimization...")
            
            # Define objective function for Optuna
            def objective(trial):
                # Suggest hyperparameters
                params = {
                    'confidence_threshold': trial.suggest_float('confidence_threshold', 0.5, 0.9),
                    'min_expected_return': trial.suggest_float('min_expected_return', 0.005, 0.03),
                    'max_risk_score': trial.suggest_float('max_risk_score', 0.5, 0.9),
                    'lookback_window': trial.suggest_int('lookback_window', 10, 50),
                    'feature_selection_k': trial.suggest_int('feature_selection_k', 20, 100)
                }
                
                # Train models with suggested parameters
                self._train_with_params(historical_data, target_data, params)
                
                # Evaluate performance
                score = self._evaluate_objective(historical_data, target_data)
                
                return score
            
            # Run optimization
            study = optuna.create_study(direction='maximize')
            study.optimize(objective, n_trials=n_trials)
            
            # Get best parameters
            best_params = study.best_params
            
            # Train final models with best parameters
            self._train_with_params(historical_data, target_data, best_params)
            
            # Calculate expected performance
            expected_performance = self._calculate_expected_performance(
                historical_data,
                target_data
            )
            
            # Get feature importance
            feature_importance = self._get_feature_importance()
            
            # Analyze regime performance
            regime_performance = self._analyze_regime_performance(
                historical_data,
                target_data
            )
            
            # Create result
            result = OptimizationResult(
                optimal_parameters=best_params,
                expected_performance=expected_performance,
                feature_importance=feature_importance,
                regime_performance=regime_performance,
                validation_metrics=self._get_validation_metrics(),
                optimization_history=[{
                    'trial': i,
                    'value': trial.value,
                    'params': trial.params
                } for i, trial in enumerate(study.trials)]
            )
            
            self.logger.info(f"Optimization complete. Best score: {study.best_value:.4f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in parameter optimization: {e}")
            self.error_handler.handle_error(e, "optimize_parameters")
            return self._get_default_optimization_result()
    
    def train(
        self,
        historical_features: pd.DataFrame,
        outcomes: pd.Series,
        validation_split: float = 0.2
    ) -> Dict[str, float]:
        """
        Train entry prediction models.
        
        Args:
            historical_features: Historical feature data
            outcomes: Entry outcomes (1 for success, 0 for failure)
            validation_split: Validation data percentage
            
        Returns:
            Training metrics
        """
        try:
            self.logger.info("Training entry prediction models...")
            
            # Prepare data
            X, y = self._prepare_training_data(historical_features, outcomes)
            
            # Feature selection
            self._select_features(X, y)
            X_selected = X[self.selected_features]
            
            # Scale features
            X_scaled = self.feature_scaler.fit_transform(X_selected)
            
            # Time series split
            tscv = TimeSeriesSplit(n_splits=5)
            
            # Train each model
            metrics = {}
            
            for model_name, model in self.models.items():
                self.logger.info(f"Training {model_name}...")
                
                # Cross-validation
                scores = cross_val_score(
                    model, X_scaled, y,
                    cv=tscv,
                    scoring='roc_auc'
                )
                
                # Fit final model
                model.fit(X_scaled, y)
                
                # Store metrics
                metrics[model_name] = {
                    'cv_score': float(np.mean(scores)),
                    'cv_std': float(np.std(scores))
                }
                
                self.logger.info(f"{model_name} CV score: {metrics[model_name]['cv_score']:.4f}")
            
            # Train regime-specific models
            self._train_regime_models(X, y, historical_features)
            
            # Update state
            self.fitted = True
            self.feature_names = list(X_selected.columns)
            
            # Calculate feature importance
           self._calculate_feature_importance(X_scaled, y)
           
            # Store performance metrics
           self.model_performance = metrics
           
           return metrics
           
       except Exception as e:
           self.logger.error(f"Error training models: {e}")
           self.error_handler.handle_error(e, "train")
           return {}
   
   # ==========================================================================
   # PUBLIC METHODS - ANALYSIS
   # ==========================================================================
   def analyze_entry_patterns(
       self,
       lookback_days: int = 30
   ) -> Dict[str, Any]:
       """
       Analyze historical entry patterns.
       
       Args:
           lookback_days: Days to analyze
           
       Returns:
           Pattern analysis results
       """
       try:
           recent_entries = [
               entry for entry in self.entry_history
               if entry.timestamp >= datetime.now() - timedelta(days=lookback_days)
           ]
           
           if not recent_entries:
               return {}
           
           # Analyze by signal type
           signal_performance = {}
           for signal in EntrySignal:
               signal_entries = [e for e in recent_entries if e.signal == signal]
               if signal_entries:
                   signal_performance[signal.value] = {
                       'count': len(signal_entries),
                       'avg_confidence': np.mean([e.confidence for e in signal_entries]),
                       'avg_return': np.mean([e.expected_return for e in signal_entries]),
                       'avg_risk': np.mean([e.risk_score for e in signal_entries])
                   }
           
           # Analyze by regime
           regime_performance = {}
           for regime in RegimeType:
               regime_entries = [e for e in recent_entries if e.regime == regime]
               if regime_entries:
                   regime_performance[regime.value] = {
                       'count': len(regime_entries),
                       'avg_confidence': np.mean([e.confidence for e in regime_entries]),
                       'signal_distribution': self._get_signal_distribution(regime_entries)
                   }
           
           # Time-based analysis
           hourly_performance = self._analyze_hourly_patterns(recent_entries)
           
           # Feature analysis
           important_features = self._analyze_feature_patterns(recent_entries)
           
           return {
               'total_entries': len(recent_entries),
               'signal_performance': signal_performance,
               'regime_performance': regime_performance,
               'hourly_performance': hourly_performance,
               'important_features': important_features,
               'best_entry_times': self._identify_best_entry_times(recent_entries)
           }
           
       except Exception as e:
           self.logger.error(f"Error analyzing entry patterns: {e}")
           return {}
   
   def get_feature_importance(self) -> Dict[str, float]:
       """Get current feature importance scores"""
       if hasattr(self, 'feature_importance'):
           return self.feature_importance.copy()
       return {}
   
   def get_regime_specific_parameters(
       self,
       regime: RegimeType
   ) -> Dict[str, Any]:
       """
       Get optimized parameters for specific regime.
       
       Args:
           regime: Market regime
           
       Returns:
           Regime-specific parameters
       """
       default_params = {
           'confidence_threshold': CONFIDENCE_THRESHOLD,
           'min_expected_return': 0.01,
           'max_risk_score': 0.7,
           'max_positions': 3
       }
       
       # Regime-specific adjustments
       regime_params = {
           RegimeType.TRENDING_UP: {
               'confidence_threshold': 0.6,
               'min_expected_return': 0.008,
               'max_risk_score': 0.75,
               'max_positions': 5
           },
           RegimeType.TRENDING_DOWN: {
               'confidence_threshold': 0.7,
               'min_expected_return': 0.012,
               'max_risk_score': 0.65,
               'max_positions': 3
           },
           RegimeType.HIGH_VOLATILITY: {
               'confidence_threshold': 0.75,
               'min_expected_return': 0.015,
               'max_risk_score': 0.6,
               'max_positions': 2
           },
           RegimeType.LOW_VOLATILITY: {
               'confidence_threshold': 0.65,
               'min_expected_return': 0.007,
               'max_risk_score': 0.8,
               'max_positions': 4
           },
           RegimeType.RANGING: {
               'confidence_threshold': 0.65,
               'min_expected_return': 0.01,
               'max_risk_score': 0.7,
               'max_positions': 3
           }
       }
       
       return regime_params.get(regime, default_params)
   
   # ==========================================================================
   # PRIVATE METHODS - PREDICTION
   # ==========================================================================
   def _prepare_features(self, feature_set: FeatureSet) -> np.ndarray:
       """Prepare features for model input"""
       # Extract selected features
       features = []
       for feature_name in self.selected_features:
           value = feature_set.features.get(feature_name, 0)
           features.append(value)
       
       feature_array = np.array(features).reshape(1, -1)
       
       # Scale features
       if self.fitted:
           feature_array = self.feature_scaler.transform(feature_array)
       
       return feature_array
   
   def _get_ensemble_predictions(
       self,
       features: np.ndarray,
       regime: RegimeType
   ) -> Dict[str, float]:
       """Get predictions from all models"""
       predictions = {}
       
       # Base models
       for model_name, model in self.models.items():
           if hasattr(model, 'predict_proba'):
               prob = model.predict_proba(features)[0, 1]  # Probability of success
               predictions[model_name] = float(prob)
       
       # Regime-specific model if available
       if regime in self.regime_models:
           regime_model = self.regime_models[regime]
           if hasattr(regime_model, 'predict_proba'):
               prob = regime_model.predict_proba(features)[0, 1]
               predictions[f'regime_{regime.value}'] = float(prob)
       
       return predictions
   
   def _calculate_entry_signal(
       self,
       predictions: Dict[str, float]
   ) -> Tuple[EntrySignal, float]:
       """Calculate entry signal from predictions"""
       # Weighted average of predictions
       weights = {
           'rf': 0.25,
           'xgb': 0.3,
           'lgb': 0.3,
           'nn': 0.15
       }
       
       weighted_prob = 0
       total_weight = 0
       
       for model, prob in predictions.items():
           if model in weights:
               weighted_prob += prob * weights[model]
               total_weight += weights[model]
           elif model.startswith('regime_'):
               # Give extra weight to regime-specific model
               weighted_prob += prob * 0.2
               total_weight += 0.2
       
       if total_weight > 0:
           confidence = weighted_prob / total_weight
       else:
           confidence = 0.5
       
       # Map to signal
       if confidence >= 0.8:
           signal = EntrySignal.STRONG_BUY
       elif confidence >= 0.65:
           signal = EntrySignal.BUY
       elif confidence >= 0.35:
           signal = EntrySignal.NEUTRAL
       elif confidence >= 0.2:
           signal = EntrySignal.AVOID
       else:
           signal = EntrySignal.STRONG_AVOID
       
       return signal, confidence
   
   def _calculate_expected_return(
       self,
       features: np.ndarray,
       regime: RegimeType
   ) -> float:
       """Calculate expected return for entry"""
       # Use historical data for regime
       base_returns = {
           RegimeType.TRENDING_UP: 0.015,
           RegimeType.TRENDING_DOWN: 0.012,
           RegimeType.RANGING: 0.008,
           RegimeType.HIGH_VOLATILITY: 0.02,
           RegimeType.LOW_VOLATILITY: 0.006
       }
       
       base_return = base_returns.get(regime, 0.01)
       
       # Adjust based on model predictions
       predictions = self._get_ensemble_predictions(features, regime)
       avg_confidence = np.mean(list(predictions.values()))
       
       # Scale return by confidence
       expected_return = base_return * (0.5 + avg_confidence)
       
       return float(expected_return)
   
   def _calculate_risk_score(
       self,
       features: FeatureSet,
       regime: MarketRegime
   ) -> float:
       """Calculate risk score for entry"""
       risk_factors = []
       
       # Volatility risk
       vol = features.features.get('volatility_30m', 0.15)
       vol_risk = min(vol / 0.3, 1.0)  # Normalize to [0, 1]
       risk_factors.append(vol_risk * 0.3)
       
       # Spread risk
       spread = features.features.get('bid_ask_spread', 0.001)
       spread_risk = min(spread / 0.005, 1.0)
       risk_factors.append(spread_risk * 0.2)
       
       # Regime risk
       regime_risks = {
           RegimeType.HIGH_VOLATILITY: 0.8,
           RegimeType.TRANSITIONAL: 0.7,
           RegimeType.TRENDING_DOWN: 0.6,
           RegimeType.RANGING: 0.4,
           RegimeType.TRENDING_UP: 0.3,
           RegimeType.LOW_VOLATILITY: 0.2
       }
       regime_risk = regime_risks.get(regime.regime_type, 0.5)
       risk_factors.append(regime_risk * 0.3)
       
       # Time risk (distance from optimal window)
       time_risk = self._calculate_time_risk(features.timestamp)
       risk_factors.append(time_risk * 0.2)
       
       # Calculate weighted risk score
       risk_score = sum(risk_factors)
       
       return float(min(risk_score, 1.0))
   
   def _calculate_time_risk(self, timestamp: datetime) -> float:
       """Calculate time-based risk"""
       current_time = timestamp.time()
       
       # Check if in optimal windows
       for window_name, (start, end) in OPTIMAL_ENTRY_WINDOWS.items():
           if start <= current_time <= end:
               # In optimal window
               if window_name == 'morning':
                   return 0.1
               else:
                   return 0.2
       
       # Outside optimal windows
       market_open = time(9, 30)
       market_close = time(16, 0)
       
       if current_time < time(10, 0):
           return 0.8  # Early morning risk
       elif current_time > time(15, 30):
           return 0.7  # Late day risk
       elif time(12, 0) <= current_time <= time(13, 0):
           return 0.5  # Lunch hour
       else:
           return 0.4  # Other times
   
   def _generate_entry_reasons(
       self,
       features: FeatureSet,
       regime: MarketRegime,
       predictions: Dict[str, float],
       signal: EntrySignal
   ) -> List[str]:
       """Generate human-readable entry reasons"""
       reasons = []
       
       # Signal strength
       if signal in [EntrySignal.STRONG_BUY, EntrySignal.BUY]:
           avg_confidence = np.mean(list(predictions.values()))
           reasons.append(f"High model confidence: {avg_confidence:.1%}")
       
       # Regime alignment
       if regime.regime_type in [RegimeType.TRENDING_UP, RegimeType.LOW_VOLATILITY]:
           reasons.append(f"Favorable regime: {regime.regime_type.value}")
       
       # Technical indicators
       rsi = features.features.get('rsi_14', 50)
       if 30 < rsi < 70:
           reasons.append("RSI in neutral zone")
       
       # Volatility
       vol = features.features.get('volatility_30m', 0.15)
       if vol < 0.15:
           reasons.append("Low volatility environment")
       elif vol > 0.25:
           reasons.append("High volatility - larger moves expected")
       
       # Time window
       if self._is_in_optimal_window(features.timestamp):
           reasons.append("Within optimal entry window")
       
       # Market structure
       if features.features.get('trend_strength', 0) > 0.7:
           reasons.append("Strong trend detected")
       
       return reasons
   
   def _is_in_optimal_window(self, timestamp: datetime) -> bool:
       """Check if timestamp is in optimal entry window"""
       current_time = timestamp.time()
       
       for start, end in OPTIMAL_ENTRY_WINDOWS.values():
           if start <= current_time <= end:
               return True
       
       return False
   
   # ==========================================================================
   # PRIVATE METHODS - TRAINING
   # ==========================================================================
   def _prepare_training_data(
       self,
       features_df: pd.DataFrame,
       outcomes: pd.Series
   ) -> Tuple[pd.DataFrame, pd.Series]:
       """Prepare data for training"""
       # Ensure alignment
       common_index = features_df.index.intersection(outcomes.index)
       
       X = features_df.loc[common_index]
       y = outcomes.loc[common_index]
       
       # Remove any remaining NaN values
       mask = ~(X.isna().any(axis=1) | y.isna())
       
       return X[mask], y[mask]
   
   def _select_features(self, X: pd.DataFrame, y: pd.Series) -> None:
       """Select most important features"""
       # Use Random Forest for initial feature importance
       rf = RandomForestClassifier(n_estimators=100, random_state=42)
       rf.fit(X, y)
       
       # Get feature importances
       importances = pd.Series(rf.feature_importances_, index=X.columns)
       importances = importances.sort_values(ascending=False)
       
       # Select features above threshold
       self.selected_features = importances[
           importances > FEATURE_IMPORTANCE_THRESHOLD
       ].index.tolist()
       
       # Ensure minimum features
       if len(self.selected_features) < 20:
           self.selected_features = importances.head(20).index.tolist()
       
       self.logger.info(f"Selected {len(self.selected_features)} features")
   
   def _train_regime_models(
       self,
       X: pd.DataFrame,
       y: pd.Series,
       features_df: pd.DataFrame
   ) -> None:
       """Train regime-specific models"""
       # Get regime for each sample
       regimes = []
       for idx in X.index:
           if idx in features_df.index:
               # Simplified - would use actual regime classification
               vol = features_df.loc[idx].get('volatility_30m', 0.15)
               if vol > 0.25:
                   regime = RegimeType.HIGH_VOLATILITY
               elif vol < 0.10:
                   regime = RegimeType.LOW_VOLATILITY
               else:
                   trend = features_df.loc[idx].get('trend_strength', 0)
                   if trend > 0.7:
                       regime = RegimeType.TRENDING_UP
                   else:
                       regime = RegimeType.RANGING
               regimes.append(regime)
           else:
               regimes.append(RegimeType.UNKNOWN)
       
       # Train model for each regime with sufficient data
       regime_series = pd.Series(regimes, index=X.index)
       
       for regime in RegimeType:
           if regime == RegimeType.UNKNOWN:
               continue
           
           regime_mask = regime_series == regime
           if regime_mask.sum() >= 100:  # Minimum samples
               X_regime = X[regime_mask]
               y_regime = y[regime_mask]
               
               # Scale features
               X_scaled = self.feature_scaler.transform(X_regime[self.selected_features])
               
               # Train regime-specific model
               regime_model = GradientBoostingClassifier(
                   n_estimators=100,
                   max_depth=5,
                   random_state=42
               )
               regime_model.fit(X_scaled, y_regime)
               
               self.regime_models[regime] = regime_model
               
               self.logger.info(f"Trained model for {regime.value} regime ({len(X_regime)} samples)")
   
   def _calculate_feature_importance(self, X: np.ndarray, y: np.ndarray) -> None:
       """Calculate and store feature importance"""
       # Use permutation importance for ensemble
       feature_importance = {}
       
       for model_name, model in self.models.items():
           if hasattr(model, 'feature_importances_'):
               importances = model.feature_importances_
           else:
               # Use permutation importance
               from sklearn.inspection import permutation_importance
               result = permutation_importance(model, X, y, n_repeats=10, random_state=42)
               importances = result.importances_mean
           
           for i, importance in enumerate(importances):
               feature_name = self.selected_features[i]
               if feature_name not in feature_importance:
                   feature_importance[feature_name] = []
               feature_importance[feature_name].append(importance)
       
       # Average across models
       self.feature_importance = {
           feature: float(np.mean(scores))
           for feature, scores in feature_importance.items()
       }
       
       # Sort by importance
       self.feature_importance = dict(
           sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)
       )
   
   # ==========================================================================
   # PRIVATE METHODS - OPTIMIZATION
   # ==========================================================================
   def _train_with_params(
       self,
       X: pd.DataFrame,
       y: pd.Series,
       params: Dict[str, Any]
   ) -> None:
       """Train models with specific parameters"""
       # Update feature selection
       if 'feature_selection_k' in params:
           k = params['feature_selection_k']
           rf = RandomForestClassifier(n_estimators=50, random_state=42)
           rf.fit(X, y)
           importances = pd.Series(rf.feature_importances_, index=X.columns)
           self.selected_features = importances.nlargest(k).index.tolist()
       
       # Update model parameters
       if 'lookback_window' in params:
           self.lookback_window = params['lookback_window']
       
       # Retrain models
       X_selected = X[self.selected_features]
       X_scaled = self.feature_scaler.fit_transform(X_selected)
       
       for model in self.models.values():
           model.fit(X_scaled, y)
   
   def _evaluate_objective(self, X: pd.DataFrame, y: pd.Series) -> float:
       """Evaluate optimization objective"""
       # Time series cross-validation
       tscv = TimeSeriesSplit(n_splits=3)
       scores = []
       
       for train_idx, val_idx in tscv.split(X):
           X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
           y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
           
           # Scale features
           X_train_scaled = self.feature_scaler.fit_transform(X_train[self.selected_features])
           X_val_scaled = self.feature_scaler.transform(X_val[self.selected_features])
           
           # Get predictions
           predictions = []
           for model in self.models.values():
               model.fit(X_train_scaled, y_train)
               pred = model.predict_proba(X_val_scaled)[:, 1]
               predictions.append(pred)
           
           # Ensemble prediction
           ensemble_pred = np.mean(predictions, axis=0)
           
           # Calculate objective score
           if self.objective == OptimizationObjective.WIN_RATE:
               score = np.mean((ensemble_pred > 0.5) == y_val)
           elif self.objective == OptimizationObjective.PROFIT_FACTOR:
               # Simplified profit factor calculation
               wins = ensemble_pred[y_val == 1].sum()
               losses = ensemble_pred[y_val == 0].sum()
               score = wins / (losses + 1e-6)
           elif self.objective == OptimizationObjective.SHARPE_RATIO:
               # Simplified Sharpe ratio
               returns = ensemble_pred * y_val - 0.5
               score = returns.mean() / (returns.std() + 1e-6)
           else:  # RISK_ADJUSTED_RETURN
               score = roc_auc_score(y_val, ensemble_pred)
           
           scores.append(score)
       
       return float(np.mean(scores))
   
   def _calculate_expected_performance(
       self,
       X: pd.DataFrame,
       y: pd.Series
   ) -> Dict[str, float]:
       """Calculate expected performance metrics"""
       # Get predictions on full dataset
       X_scaled = self.feature_scaler.transform(X[self.selected_features])
       
       predictions = []
       for model in self.models.values():
           pred = model.predict_proba(X_scaled)[:, 1]
           predictions.append(pred)
       
       ensemble_pred = np.mean(predictions, axis=0)
       
       # Calculate metrics
       from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
       
       threshold = 0.5
       y_pred = ensemble_pred > threshold
       
       return {
           'accuracy': float(accuracy_score(y, y_pred)),
           'precision': float(precision_score(y, y_pred)),
           'recall': float(recall_score(y, y_pred)),
           'f1_score': float(f1_score(y, y_pred)),
           'auc': float(roc_auc_score(y, ensemble_pred))
       }
   
   def _analyze_regime_performance(
       self,
       X: pd.DataFrame,
       y: pd.Series
   ) -> Dict[RegimeType, Dict[str, float]]:
       """Analyze performance by regime"""
       regime_performance = {}
       
       # Simplified regime classification
       for regime in [RegimeType.TRENDING_UP, RegimeType.TRENDING_DOWN, 
                     RegimeType.RANGING, RegimeType.HIGH_VOLATILITY]:
           # Would use actual regime classification here
           regime_mask = np.random.choice([True, False], size=len(X), p=[0.25, 0.75])
           
           if regime_mask.sum() >= 50:
               X_regime = X[regime_mask]
               y_regime = y[regime_mask]
               
               # Get predictions
               X_scaled = self.feature_scaler.transform(X_regime[self.selected_features])
               predictions = []
               
               for model in self.models.values():
                   pred = model.predict_proba(X_scaled)[:, 1]
                   predictions.append(pred)
               
               ensemble_pred = np.mean(predictions, axis=0)
               
               # Calculate metrics
               regime_performance[regime] = {
                   'samples': int(regime_mask.sum()),
                   'win_rate': float(np.mean(y_regime)),
                   'model_accuracy': float(np.mean((ensemble_pred > 0.5) == y_regime)),
                   'auc': float(roc_auc_score(y_regime, ensemble_pred)) if len(np.unique(y_regime)) > 1 else 0.5
               }
       
       return regime_performance
   
   def _get_validation_metrics(self) -> Dict[str, float]:
       """Get validation metrics from training"""
       return self.model_performance.copy()
   
   # ==========================================================================
   # PRIVATE METHODS - UTILITIES
   # ==========================================================================
   def _get_key_features(self, feature_set: FeatureSet) -> Dict[str, float]:
       """Extract key features for display"""
       key_features = [
           'volatility_30m', 'trend_strength', 'rsi_14', 
           'vix_level', 'bid_ask_spread', 'volume_ratio_5m'
       ]
       
       return {
           feature: feature_set.features.get(feature, 0)
           for feature in key_features
           if feature in self.selected_features
       }
   
   def _cache_prediction(self, opportunity: EntryOpportunity) -> None:
       """Cache prediction for analysis"""
       self.entry_history.append(opportunity)
       
       # Time-based cache key
       cache_key = opportunity.timestamp.strftime("%Y%m%d_%H%M")
       self.prediction_cache[cache_key] = opportunity
       
       # Clean old cache entries
       cutoff_time = datetime.now() - timedelta(hours=24)
       old_keys = [
           key for key, opp in self.prediction_cache.items()
           if opp.timestamp < cutoff_time
       ]
       for key in old_keys:
           del self.prediction_cache[key]
   
   def _get_signal_distribution(self, entries: List[EntryOpportunity]) -> Dict[str, float]:
       """Get distribution of signals"""
       signal_counts = {}
       total = len(entries)
       
       for signal in EntrySignal:
           count = sum(1 for e in entries if e.signal == signal)
           signal_counts[signal.value] = count / total if total > 0 else 0
       
       return signal_counts
   
   def _analyze_hourly_patterns(
       self,
       entries: List[EntryOpportunity]
   ) -> Dict[int, Dict[str, float]]:
       """Analyze entry patterns by hour"""
       hourly_data = {}
       
       for hour in range(9, 17):  # Market hours
           hour_entries = [
               e for e in entries 
               if e.timestamp.hour == hour
           ]
           
           if hour_entries:
               hourly_data[hour] = {
                   'count': len(hour_entries),
                   'avg_confidence': np.mean([e.confidence for e in hour_entries]),
                   'success_rate': np.mean([
                       1 if e.signal in [EntrySignal.BUY, EntrySignal.STRONG_BUY] else 0
                       for e in hour_entries
                   ])
               }
       
       return hourly_data
   
   def _analyze_feature_patterns(
       self,
       entries: List[EntryOpportunity]
   ) -> Dict[str, Dict[str, float]]:
       """Analyze feature patterns in successful entries"""
       successful_entries = [
           e for e in entries 
           if e.signal in [EntrySignal.BUY, EntrySignal.STRONG_BUY]
           and e.confidence > 0.7
       ]
       
       if not successful_entries:
           return {}
       
       feature_stats = {}
       
       # Analyze each feature
       all_features = set()
       for entry in successful_entries:
           all_features.update(entry.features.keys())
       
       for feature in all_features:
           values = [
               e.features.get(feature, 0) 
               for e in successful_entries 
               if feature in e.features
           ]
           
           if values:
               feature_stats[feature] = {
                   'mean': float(np.mean(values)),
                   'std': float(np.std(values)),
                   'min': float(np.min(values)),
                   'max': float(np.max(values)),
                   'median': float(np.median(values))
               }
       
       return feature_stats
   
   def _identify_best_entry_times(
       self,
       entries: List[EntryOpportunity]
   ) -> List[Dict[str, Any]]:
       """Identify best entry times from historical data"""
       # Group by 15-minute intervals
       time_performance = {}
       
       for entry in entries:
           if entry.signal in [EntrySignal.BUY, EntrySignal.STRONG_BUY]:
               time_key = (entry.timestamp.hour, entry.timestamp.minute // 15 * 15)
               
               if time_key not in time_performance:
                   time_performance[time_key] = {
                       'count': 0,
                       'total_confidence': 0,
                       'total_return': 0
                   }
               
               time_performance[time_key]['count'] += 1
               time_performance[time_key]['total_confidence'] += entry.confidence
               time_performance[time_key]['total_return'] += entry.expected_return
       
       # Calculate averages and sort
       best_times = []
       for (hour, minute), stats in time_performance.items():
           if stats['count'] >= 5:  # Minimum sample size
               best_times.append({
                   'time': f"{hour:02d}:{minute:02d}",
                   'avg_confidence': stats['total_confidence'] / stats['count'],
                   'avg_return': stats['total_return'] / stats['count'],
                   'count': stats['count']
               })
       
       # Sort by average return
       best_times.sort(key=lambda x: x['avg_return'], reverse=True)
       
       return best_times[:10]  # Top 10 times
   
   def _get_neutral_opportunity(self, timestamp: datetime) -> EntryOpportunity:
       """Get neutral opportunity for default cases"""
       return EntryOpportunity(
           timestamp=timestamp,
           signal=EntrySignal.NEUTRAL,
           confidence=0.5,
           expected_return=0.0,
           risk_score=0.5,
           regime=RegimeType.UNKNOWN,
           features={},
           reasons=["Insufficient data for prediction"]
       )
   
   def _get_avoid_opportunity(self, timestamp: datetime, reason: str) -> EntryOpportunity:
       """Get avoid opportunity with reason"""
       return EntryOpportunity(
           timestamp=timestamp,
           signal=EntrySignal.AVOID,
           confidence=0.8,
           expected_return=0.0,
           risk_score=0.8,
           regime=RegimeType.UNKNOWN,
           features={},
           reasons=[reason]
       )
   
   def _get_default_optimization_result(self) -> OptimizationResult:
       """Get default optimization result for error cases"""
       return OptimizationResult(
           optimal_parameters={
               'confidence_threshold': CONFIDENCE_THRESHOLD,
               'min_expected_return': 0.01,
               'max_risk_score': 0.7
           },
           expected_performance={
               'accuracy': 0.5,
               'precision': 0.5,
               'recall': 0.5
           },
           feature_importance={},
           regime_performance={},
           validation_metrics={}
       )
   
   # ==========================================================================
   # PUBLIC METHODS - PERSISTENCE
   # ==========================================================================
   def save_model(self, filepath: Path) -> None:
       """Save trained models and configuration"""
       model_data = {
           'fitted': self.fitted,
           'feature_names': self.feature_names,
           'selected_features': self.selected_features,
           'model_performance': self.model_performance,
           'feature_importance': getattr(self, 'feature_importance', {}),
           'objective': self.objective.value
       }
       
       # Save configuration
       with open(filepath.with_suffix('.json'), 'w') as f:
           json.dump(model_data, f, indent=2)
       
       # Save models and scalers
       if self.fitted:
           model_dict = {
               'models': self.models,
               'regime_models': self.regime_models,
               'feature_scaler': self.feature_scaler,
               'target_scaler': self.target_scaler
           }
           with open(filepath.with_suffix('.pkl'), 'wb') as f:
               pickle.dump(model_dict, f)
   
   def load_model(self, filepath: Path) -> None:
       """Load trained models and configuration"""
       # Load configuration
       with open(filepath.with_suffix('.json'), 'r') as f:
           model_data = json.load(f)
       
       self.fitted = model_data['fitted']
       self.feature_names = model_data['feature_names']
       self.selected_features = model_data['selected_features']
       self.model_performance = model_data['model_performance']
       self.feature_importance = model_data.get('feature_importance', {})
       
       # Load models
       if self.fitted:
           with open(filepath.with_suffix('.pkl'), 'rb') as f:
               model_dict = pickle.load(f)
           
           self.models = model_dict['models']
           self.regime_models = model_dict.get('regime_models', {})
           self.feature_scaler = model_dict['feature_scaler']
           self.target_scaler = model_dict['target_scaler']

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_entry_optimizer(
   feature_engineer: FeatureEngineer,
   regime_classifier: RegimeClassifier,
   objective: OptimizationObjective = OptimizationObjective.RISK_ADJUSTED_RETURN
) -> EntryOptimizer:
   """Create entry optimizer instance"""
   return EntryOptimizer(feature_engineer, regime_classifier, objective)

def get_default_entry_filter() -> EntryFilter:
   """Get default entry filter"""
   return EntryFilter(
       min_confidence=CONFIDENCE_THRESHOLD,
       allowed_regimes=[
           RegimeType.TRENDING_UP,
           RegimeType.TRENDING_DOWN,
           RegimeType.RANGING,
           RegimeType.LOW_VOLATILITY
       ],
       time_windows=list(OPTIMAL_ENTRY_WINDOWS.values()),
       max_risk_score=0.7,
       min_expected_return=0.01
   )

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
   # Test entry optimizer
   from SpyderL_ML.SpyderL10_FeatureEngineering import create_feature_engineer
   from SpyderL_ML.SpyderL09_RegimeClassifier import create_regime_classifier
   
   # Initialize components
   feature_engineer = create_feature_engineer()
   regime_classifier = create_regime_classifier()
   optimizer = create_entry_optimizer(feature_engineer, regime_classifier)
   
   # Create sample training data
   n_samples = 1000
   feature_names = ['volatility_30m', 'trend_strength', 'rsi_14', 'vix_level', 'bid_ask_spread']
   
   historical_features = pd.DataFrame({
       name: np.random.randn(n_samples) * 0.1 + 0.5
       for name in feature_names
   })
   
   # Create synthetic outcomes (1 for successful entry)
   outcomes = pd.Series(
       np.random.choice([0, 1], size=n_samples, p=[0.6, 0.4])
   )
   
   # Train models
   print("Training entry optimization models...")
   metrics = optimizer.train(historical_features, outcomes)
   
   print("\nModel Performance:")
   for model, perf in metrics.items():
       print(f"  {model}: CV Score = {perf['cv_score']:.4f} (±{perf['cv_std']:.4f})")
   
   # Test prediction
   from SpyderL_ML.SpyderL10_FeatureEngineering import FeatureSet
   
   test_features = FeatureSet(
       timestamp=datetime.now(),
       symbol='SPY',
       features={name: np.random.randn() * 0.1 + 0.5 for name in feature_names}
   )
   
   # Get entry prediction
   opportunity = optimizer.predict_entry(test_features)
   
   print(f"\nEntry Prediction:")
   print(f"  Signal: {opportunity.signal.value}")
   print(f"  Confidence: {opportunity.confidence:.2%}")
   print(f"  Expected Return: {opportunity.expected_return:.2%}")
   print(f"  Risk Score: {opportunity.risk_score:.2f}")
   print(f"  Regime: {opportunity.regime.value}")
   
   print("\nReasons:")
   for reason in opportunity.reasons:
       print(f"  - {reason}")
   
   # Analyze patterns
   print("\nAnalyzing entry patterns...")
   patterns = optimizer.analyze_entry_patterns(lookback_days=30)
   
   if patterns:
       print(f"\nTotal entries analyzed: {patterns.get('total_entries', 0)}")
       
       if 'best_entry_times' in patterns:
           print("\nBest entry times:")
           for entry_time in patterns['best_entry_times'][:5]:
               print(f"  {entry_time['time']}: "
                     f"Return = {entry_time['avg_return']:.2%}, "
                     f"Confidence = {entry_time['avg_confidence']:.2%}")
