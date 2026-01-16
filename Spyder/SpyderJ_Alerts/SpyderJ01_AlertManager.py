#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderJ_Alerts
Module: SpyderJ01_AlertManager.py
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
import os
import json
import asyncio
import threading
import queue
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any, Callable, Union
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
import time

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import hashlib
import pickle
import math
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderA_Core.SpyderA03_Configuration import get_config_manager
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event
from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, NotificationError
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from Spyder.SpyderU_Utilities.SpyderU07_Constants import AlertLevel

try:
    from SpyderL_ML.SpyderL01_MLPredictor import MLPredictor
    from SpyderL_ML.SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine as RegimeClassifier
    from SpyderL_ML.SpyderL14_RealTimePredictor import RealTimePredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

# =============================================================================
# ENHANCED ENUMERATIONS
# =============================================================================
class AlertLevel(Enum):
    """Alert severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
    PREDICTIVE = "predictive"  # New: For ML predictions

class AlertCategory(Enum):
    """Alert categories."""
    SYSTEM = "system"
    TRADING = "trading"
    RISK = "risk"
    PERFORMANCE = "performance"
    PREDICTIVE = "predictive"  # New: ML predictions
    MARKET = "market"

class PredictionType(Enum):
    """Types of predictive alerts."""
    RISK_ZONE_BREACH = "risk_zone_breach"
    VOLATILITY_SPIKE = "volatility_spike"
    OPTIMAL_EXIT = "optimal_exit"
    GAMMA_RISK = "gamma_risk"
    MARKET_REGIME_CHANGE = "market_regime_change"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    IV_CRUSH = "iv_crush"
    CORRELATION_BREAKDOWN = "correlation_breakdown"

class PredictionConfidence(Enum):
    """Confidence levels for predictions."""
    LOW = "low"          # 60-70%
    MEDIUM = "medium"    # 70-85%
    HIGH = "high"        # 85-95%
    VERY_HIGH = "very_high"  # 95%+

# =============================================================================
# ENHANCED DATA STRUCTURES
# =============================================================================
@dataclass
class PredictiveAlert:
    """Enhanced alert with prediction capabilities."""
    id: str
    prediction_type: PredictionType
    confidence: PredictionConfidence
    time_horizon: int  # Minutes until predicted event
    probability: float  # 0.0 to 1.0
    impact_severity: str  # "low", "medium", "high", "critical"
    affected_strategies: List[str]
    affected_positions: List[str]
    recommended_actions: List[str]
    model_version: str
    features_used: Dict[str, float]
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    triggered: bool = False
    false_positive: Optional[bool] = None  # For model learning

@dataclass
class PredictionModel:
    """ML model for specific prediction type."""
    prediction_type: PredictionType
    model: Any  # sklearn model or similar
    scaler: StandardScaler
    feature_names: List[str]
    accuracy: float
    last_trained: datetime
    version: str
    training_samples: int

@dataclass
class AdaptiveThreshold:
    """Adaptive alert threshold that changes with market conditions."""
    base_threshold: float
    current_threshold: float
    adjustment_factor: float  # Multiplier based on market regime
    volatility_adjustment: float
    last_updated: datetime
    regime_adjustments: Dict[str, float]  # Regime -> adjustment factor

# =============================================================================
# ENHANCED ALERT MANAGER CLASS
# =============================================================================
class AlertManager:
    """
    Enhanced Alert Manager with ML-powered predictive capabilities.
    
    New Features:
    - Predictive alerts using machine learning models
    - Risk zone breach prediction before they happen
    - Optimal exit timing predictions
    - Adaptive thresholds based on market conditions
    - Model accuracy tracking and auto-retraining
    - False positive learning for model improvement
    
    Maintains all existing functionality while adding predictive layer.
    """
    
    def __init__(self):
        """Initialize enhanced alert manager with predictive capabilities."""
        # Core components
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.config = get_config_manager()
        self.event_manager = get_event_manager()
        self.data_access = get_data_access_layer()
        self.datetime_utils = DateTimeUtils()
        
        # Basic alert configuration
        self.enabled = self.config.get('alerts.enabled', True)
        self.rate_limit = self.config.get('alerts.rate_limit', 10)
        
        # Predictive alerts configuration
        self.predictive_enabled = self.config.get('alerts.predictive.enabled', True)
        self.prediction_horizon = self.config.get('alerts.predictive.horizon_minutes', 30)
        self.min_confidence = self.config.get('alerts.predictive.min_confidence', 0.7)
        
        # ML Components (if available)
        self.ml_available = ML_AVAILABLE
        self.prediction_models: Dict[PredictionType, PredictionModel] = {}
        self.ml_predictor = None
        self.regime_classifier = None
        self.realtime_predictor = None
        
        # Enhanced data structures
        self.predictive_alerts: Dict[str, PredictiveAlert] = {}
        self.adaptive_thresholds: Dict[str, AdaptiveThreshold] = {}
        self.prediction_history: deque = deque(maxlen=1000)
        
        # Alert queues
        self.alert_queue: queue.Queue = queue.Queue(maxsize=1000)
        self.predictive_queue: queue.Queue = queue.Queue(maxsize=500)
        
        # Strategy registrations
        self.registered_strategies: Dict[str, Dict[str, Any]] = {}
        self.strategy_contexts: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.prediction_stats = {
            'total_predictions': 0,
            'accurate_predictions': 0,
            'false_positives': 0,
            'missed_events': 0,
            'by_type': defaultdict(lambda: {'total': 0, 'accurate': 0}),
            'by_confidence': defaultdict(lambda: {'total': 0, 'accurate': 0})
        }
        
        # Threading
        self._stop_event = threading.Event()
        self._worker_thread = None
        self._prediction_thread = None
        
        # Initialize components
        self._initialize_ml_components()
        self._initialize_adaptive_thresholds()
        self._start_processing()
        
        self.logger.info("✅ Enhanced AlertManager with predictive capabilities initialized")
    
    # ==========================================================================
    # ML INTEGRATION METHODS
    # ==========================================================================
    def _initialize_ml_components(self) -> None:
        """Initialize ML components for predictive alerts."""
        try:
            if not self.ml_available:
                self.logger.warning("ML modules not available - predictive alerts disabled")
                self.predictive_enabled = False
                return
            
            # Initialize ML predictors
            if self.predictive_enabled:
                self.ml_predictor = MLPredictor(
                    model_type="ensemble",
                    prediction_horizon="short_term"
                )
                
                self.regime_classifier = RegimeClassifier()
                
                self.realtime_predictor = RealTimePredictor(
                    strategy_focus="alert_generation",
                    update_frequency="1min"
                )
                
                # Load or initialize prediction models
                self._load_prediction_models()
                
                self.logger.info("🤖 ML components initialized for predictive alerts")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_initialize_ml_components'
            })
            self.predictive_enabled = False
    
    def _load_prediction_models(self) -> None:
        """Load or create prediction models for different alert types."""
        try:
            model_dir = self.config.get('alerts.predictive.model_dir', 'models/alerts/')
            
            for prediction_type in PredictionType:
                model_path = f"{model_dir}/{prediction_type.value}_model.joblib"
                
                try:
                    # Try to load existing model
                    if os.path.exists(model_path):
                        model_data = joblib.load(model_path)
                        self.prediction_models[prediction_type] = model_data
                        self.logger.info(f"📊 Loaded prediction model for {prediction_type.value}")
                    else:
                        # Create new model
                        self._create_prediction_model(prediction_type)
                        
                except Exception as e:
                    self.logger.warning(f"Failed to load model for {prediction_type.value}: {e}")
                    self._create_prediction_model(prediction_type)
        
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_load_prediction_models'
            })
    
    def _create_prediction_model(self, prediction_type: PredictionType) -> None:
        """Create a new prediction model for specific alert type."""
        try:
            # Define features for each prediction type
            feature_sets = {
                PredictionType.RISK_ZONE_BREACH: [
                    'underlying_price_change', 'gamma_exposure', 'time_to_expiry',
                    'iv_change', 'delta_exposure', 'price_velocity'
                ],

except Exception as e:
    recommendations = ["Error generating recommendations"]
    print(f"Warning: Error generating recommendations: {e}")
                PredictionType.VOLATILITY_SPIKE: [
                    'vix_level', 'vix_change', 'iv_rank', 'volume_ratio',
                    'price_volatility', 'options_volume'
                ],

except Exception as e:
    recommendations = ["Error generating recommendations"]
    print(f"Warning: Error generating recommendations: {e}")
                PredictionType.OPTIMAL_EXIT: [
                    'current_pnl', 'theta_decay', 'time_to_expiry', 'iv_percentile',
                    'profit_velocity', 'risk_adjusted_return'
                ],

except Exception as e:
    recommendations = ["Error generating recommendations"]
    print(f"Warning: Error generating recommendations: {e}")
                PredictionType.GAMMA_RISK: [
                    'gamma_exposure', 'price_change', 'gamma_rate_change',
                    'underlying_velocity', 'position_concentration'
                ]

except Exception as e:
    recommendations = ["Error generating recommendations"]
    print(f"Warning: Error generating recommendations: {e}")
            }
            
            features = feature_sets.get(prediction_type, [
                'price_change', 'volume', 'volatility', 'time_factor'
            ])
            
            # Create simple model (would be trained with historical data)
            from sklearn.ensemble import RandomForestClassifier
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            scaler = StandardScaler()
            
            prediction_model = PredictionModel(
                prediction_type=prediction_type,
                model=model,
                scaler=scaler,
                feature_names=features,
                accuracy=0.0,  # Will be updated after training
                last_trained=datetime.now(),
                version="1.0",
                training_samples=0
            )
            
            self.prediction_models[prediction_type] = prediction_model
            
            self.logger.info(f"📈 Created new prediction model for {prediction_type.value}")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_create_prediction_model',
                'prediction_type': prediction_type.value
            })
    
    # ==========================================================================
    # ADAPTIVE THRESHOLDS
    # ==========================================================================
    def _initialize_adaptive_thresholds(self) -> None:
        """Initialize adaptive thresholds for different alert types."""
        try:
            default_thresholds = {
                'gamma_exposure': AdaptiveThreshold(
                    base_threshold=15.0,
                    current_threshold=15.0,
                    adjustment_factor=1.0,
                    volatility_adjustment=1.0,
                    last_updated=datetime.now(),
                    regime_adjustments={
                        'low_vol': 0.8,
                        'normal': 1.0,
                        'high_vol': 1.5,
                        'crisis': 2.0
                    }
                ),
                'delta_exposure': AdaptiveThreshold(
                    base_threshold=25.0,
                    current_threshold=25.0,
                    adjustment_factor=1.0,
                    volatility_adjustment=1.0,
                    last_updated=datetime.now(),
                    regime_adjustments={
                        'low_vol': 0.9,
                        'normal': 1.0,
                        'high_vol': 1.3,
                        'crisis': 1.8
                    }
                ),
                'pnl_change': AdaptiveThreshold(
                    base_threshold=0.02,  # 2%
                    current_threshold=0.02,
                    adjustment_factor=1.0,
                    volatility_adjustment=1.0,
                    last_updated=datetime.now(),
                    regime_adjustments={
                        'low_vol': 0.7,
                        'normal': 1.0,
                        'high_vol': 1.5,
                        'crisis': 2.5
                    }
                )
            }
            
            self.adaptive_thresholds.update(default_thresholds)
            
            self.logger.info("🎯 Adaptive thresholds initialized")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_initialize_adaptive_thresholds'
            })
    
    def update_adaptive_thresholds(self, market_regime: str, volatility_level: float) -> None:
        """Update adaptive thresholds based on market conditions."""
        try:
            for threshold_name, threshold in self.adaptive_thresholds.items():
                # Get regime adjustment
                regime_adj = threshold.regime_adjustments.get(market_regime, 1.0)
                
                # Calculate volatility adjustment (higher vol = higher thresholds)
                vol_adj = min(2.0, max(0.5, volatility_level / 20.0))  # Normalized to VIX ~20
                
                # Update threshold
                threshold.adjustment_factor = regime_adj
                threshold.volatility_adjustment = vol_adj
                threshold.current_threshold = (
                    threshold.base_threshold * 
                    threshold.adjustment_factor * 
                    threshold.volatility_adjustment
                )
                threshold.last_updated = datetime.now()
            
            self.logger.debug(f"📊 Updated adaptive thresholds for regime: {market_regime}")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'update_adaptive_thresholds'
            })
    
    # ==========================================================================
    # STRATEGY REGISTRATION METHODS
    # ==========================================================================
    def register_strategy_for_predictions(self, strategy_id: str, 
                                        prediction_config: Dict[str, Any]) -> None:
        """
        Register a strategy for predictive alerts.
        
        Args:
            strategy_id: Strategy identifier
            prediction_config: Configuration for predictions
        """
        try:
            self.registered_strategies[strategy_id] = {
                'config': prediction_config,
                'registered_at': datetime.now(),
                'active_predictions': [],
                'prediction_types': prediction_config.get('prediction_types', []),
                'min_confidence': prediction_config.get('min_confidence', self.min_confidence),
                'alert_channels': prediction_config.get('channels', ['telegram']),
                'context_callback': prediction_config.get('context_callback')
            }
            
            self.logger.info(f"📋 Registered strategy {strategy_id} for predictive alerts")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'register_strategy_for_predictions',
                'strategy_id': strategy_id
            })
    
    def update_strategy_context(self, strategy_id: str, context: Dict[str, Any]) -> None:
        """Update strategy context for better predictions."""
        try:
            self.strategy_contexts[strategy_id] = {
                **context,
                'updated_at': datetime.now()
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'update_strategy_context',
                'strategy_id': strategy_id
            })
    
    # ==========================================================================
    # PREDICTIVE ALERT GENERATION
    # ==========================================================================
    def generate_predictive_alerts(self, market_data: Dict[str, Any]) -> List[PredictiveAlert]:
        """
        Generate predictive alerts based on current market conditions.
        
        Args:
            market_data: Current market data
            
        Returns:
            List of predictive alerts
        """
        if not self.predictive_enabled:
            return []
        
        alerts = []
        
        try:
            # Update adaptive thresholds first
            market_regime = self._get_market_regime(market_data)
            volatility_level = market_data.get('vix', 20.0)
            self.update_adaptive_thresholds(market_regime, volatility_level)
            
            # Generate predictions for each registered strategy
            for strategy_id, registration in self.registered_strategies.items():
                strategy_context = self.strategy_contexts.get(strategy_id, {})
                
                # Get strategy-specific predictions
                strategy_alerts = self._generate_strategy_predictions(
                    strategy_id, market_data, strategy_context, registration
                )
                
                alerts.extend(strategy_alerts)
            
            # Generate market-wide predictions
            market_alerts = self._generate_market_predictions(market_data)
            alerts.extend(market_alerts)
            
            # Filter by confidence and relevance
            filtered_alerts = self._filter_predictions(alerts)
            
            # Store predictions
            for alert in filtered_alerts:
                self.predictive_alerts[alert.id] = alert
                self.prediction_history.append({
                    'timestamp': alert.created_at,
                    'type': alert.prediction_type.value,
                    'confidence': alert.confidence.value,
                    'probability': alert.probability
                })
            
            if filtered_alerts:
                self.logger.info(f"🔮 Generated {len(filtered_alerts)} predictive alerts")
            
            return filtered_alerts
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_predictive_alerts'
            })
            return []
    
    def _generate_strategy_predictions(self, strategy_id: str, market_data: Dict[str, Any],
                                     strategy_context: Dict[str, Any],
                                     registration: Dict[str, Any]) -> List[PredictiveAlert]:
        """Generate predictions specific to a strategy."""
        alerts = []
        
        try:
            prediction_types = registration['prediction_types']
            
            for pred_type_str in prediction_types:
                try:
                    pred_type = PredictionType(pred_type_str)
                    
                    if pred_type in self.prediction_models:
                        prediction = self._make_prediction(
                            pred_type, strategy_id, market_data, strategy_context
                        )
                        
                        if prediction:
                            alerts.append(prediction)
                            
                except ValueError:
                    self.logger.warning(f"Unknown prediction type: {pred_type_str}")
                except Exception as e:
                    self.logger.error(f"Error generating {pred_type_str} prediction: {e}")
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_generate_strategy_predictions',
                'strategy_id': strategy_id
            })
        
        return alerts
    
    def _make_prediction(self, prediction_type: PredictionType, strategy_id: str,
                        market_data: Dict[str, Any], 
                        strategy_context: Dict[str, Any]) -> Optional[PredictiveAlert]:
        """Make a specific prediction using ML model."""
        try:
            model_info = self.prediction_models.get(prediction_type)
            if not model_info:
                return None
            
            # Extract features
            features = self._extract_features(
                prediction_type, market_data, strategy_context
            )
            
            if not features:
                return None
            
            # Prepare feature vector
            feature_vector = np.array([
                features.get(name, 0.0) for name in model_info.feature_names
            ]).reshape(1, -1)
            
            # Scale features
            scaled_features = model_info.scaler.transform(feature_vector)
            
            # Make prediction
            if hasattr(model_info.model, 'predict_proba'):
                probabilities = model_info.model.predict_proba(scaled_features)[0]
                probability = max(probabilities)  # Highest class probability
                prediction = probability > 0.5
            else:
                prediction = model_info.model.predict(scaled_features)[0]
                probability = 0.7 if prediction else 0.3  # Default probabilities
            
            # Only create alert if prediction is positive and meets confidence threshold
            if prediction and probability >= self.min_confidence:
                confidence = self._probability_to_confidence(probability)
                
                # Calculate time horizon based on prediction type
                time_horizon = self._calculate_time_horizon(prediction_type, features)
                
                # Determine impact severity
                impact_severity = self._assess_impact_severity(
                    prediction_type, probability, features
                )
                
                # Generate recommended actions
                recommended_actions = self._generate_recommendations(
                    prediction_type, strategy_id, features
                )
                
                alert = PredictiveAlert(
                    id=f"{strategy_id}_{prediction_type.value}_{int(time.time())}",
                    prediction_type=prediction_type,
                    confidence=confidence,
                    time_horizon=time_horizon,
                    probability=probability,
                    impact_severity=impact_severity,
                    affected_strategies=[strategy_id],
                    affected_positions=strategy_context.get('position_ids', []),
                    recommended_actions=recommended_actions,
                    model_version=model_info.version,
                    features_used=features,
                    expires_at=datetime.now() + timedelta(minutes=time_horizon * 2)
                )
                
                return alert
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_make_prediction',
                'prediction_type': prediction_type.value,
                'strategy_id': strategy_id
            })
        
        return None
    
    def _extract_features(self, prediction_type: PredictionType,
                         market_data: Dict[str, Any],
                         strategy_context: Dict[str, Any]) -> Dict[str, float]:
        """Extract features for ML prediction."""
        try:
            features = {}
            
            # Common market features
            features['underlying_price'] = market_data.get('underlying_price', 0.0)
            features['iv_rank'] = market_data.get('iv_rank', 50.0)
            features['vix_level'] = market_data.get('vix', 20.0)
            features['volume_ratio'] = market_data.get('volume_ratio', 1.0)
            
            # Price change features
            current_price = market_data.get('underlying_price', 0.0)
            previous_price = market_data.get('previous_price', current_price)
            if previous_price > 0:
                features['price_change_pct'] = (current_price - previous_price) / previous_price
            
            # Strategy-specific features
            features['gamma_exposure'] = strategy_context.get('gamma_exposure', 0.0)
            features['delta_exposure'] = strategy_context.get('delta_exposure', 0.0)
            features['current_pnl'] = strategy_context.get('current_pnl', 0.0)
            features['days_held'] = strategy_context.get('days_held', 0)
            features['time_to_expiry'] = strategy_context.get('days_to_expiry', 30)
            
            # Prediction-type specific features
            if prediction_type == PredictionType.RISK_ZONE_BREACH:
                features['distance_to_danger'] = strategy_context.get('distance_to_danger', 1.0)
                features['price_velocity'] = market_data.get('price_velocity', 0.0)
                
            elif prediction_type == PredictionType.VOLATILITY_SPIKE:
                features['vix_change'] = market_data.get('vix_change', 0.0)
                features['iv_percentile'] = market_data.get('iv_percentile', 50.0)
                
            elif prediction_type == PredictionType.OPTIMAL_EXIT:
                features['profit_velocity'] = strategy_context.get('profit_velocity', 0.0)
                features['theta_decay'] = strategy_context.get('theta_decay', 0.0)
            
            return features
            
        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': '_extract_features',
                'prediction_type': prediction_type.value
            })
            return {}
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    def _get_market_regime(self, market_data: Dict[str, Any]) -> str:
        """Get current market regime."""
        try:
            if self.regime_classifier:
                return self.regime_classifier.classify(market_data)
            
            # Simple fallback based on VIX
            vix = market_data.get('vix', 20.0)
            if vix < 15:
                return 'low_vol'
            elif vix < 25:
                return 'normal'
            elif vix < 35:
                return 'high_vol'
            else:
                return 'crisis'
                
        except Exception:
            return 'normal'
    
    def _probability_to_confidence(self, probability: float) -> PredictionConfidence:
        """Convert probability to confidence enum."""
        if probability >= 0.95:
            return PredictionConfidence.VERY_HIGH
        elif probability >= 0.85:
            return PredictionConfidence.HIGH
        elif probability >= 0.70:
            return PredictionConfidence.MEDIUM
        else:
            return PredictionConfidence.LOW
    
    def _calculate_time_horizon(self, prediction_type: PredictionType, 
                               features: Dict[str, float]) -> int:
        """Calculate time horizon for prediction in minutes."""
        base_horizons = {
            PredictionType.RISK_ZONE_BREACH: 15,
            PredictionType.VOLATILITY_SPIKE: 30,
            PredictionType.OPTIMAL_EXIT: 60,
            PredictionType.GAMMA_RISK: 10,
            PredictionType.MARKET_REGIME_CHANGE: 120
        }
        
        base_horizon = base_horizons.get(prediction_type, 30)
        
        # Adjust based on features
        if 'price_velocity' in features:
            velocity_factor = min(2.0, max(0.5, abs(features['price_velocity']) * 10))
            base_horizon = int(base_horizon / velocity_factor)
        
        return max(5, min(240, base_horizon))  # 5 min to 4 hours
    
    def _assess_impact_severity(self, prediction_type: PredictionType,
                               probability: float, features: Dict[str, float]) -> str:
        """Assess the potential impact severity."""
        base_severity = "medium"
        
        if prediction_type in [PredictionType.RISK_ZONE_BREACH, PredictionType.GAMMA_RISK]:
            if probability > 0.9:
                base_severity = "critical"
            elif probability > 0.8:
                base_severity = "high"
        
        # Adjust based on exposure
        gamma_exposure = features.get('gamma_exposure', 0.0)
        if gamma_exposure > 20:
            if base_severity == "medium":
                base_severity = "high"
            elif base_severity == "low":
                base_severity = "medium"
        
        return base_severity
    
    def _generate_recommendations(self, prediction_type: PredictionType,
                                strategy_id: str, features: Dict[str, float]) -> List[str]:
        """Generate recommended actions for prediction."""
        recommendations = []
        
        try:
            if prediction_type == PredictionType.RISK_ZONE_BREACH:
                recommendations = [
                    "Consider reducing position size",
                    "Set tighter stop losses",
                    "Monitor price movements closely",
                ]

except Exception as e:
    recommendations = ["Error generating recommendations"]
    print(f"Warning: Error generating recommendations: {e}")
