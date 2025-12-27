#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderP03_CorrelationAnalyzer.py
Group: P (Portfolio Management)
Purpose: Advanced correlation analysis and risk monitoring

Description:
    This module provides sophisticated correlation analysis for portfolio management,
    including real-time correlation monitoring, rolling correlation windows, regime-based
    correlation analysis, correlation clustering, and dynamic correlation forecasting.
    It integrates with machine learning models to predict correlation changes and
    provides early warning systems for correlation spikes and portfolio concentration risks.

Spyder Version: 1.0
Architect: Mohamed Talib
Date Created: 2025-07-01
Last 

from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import MarketRegime
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import UnifiedRegimeEngine as RegimeClassifier
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import RegimeType
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import create_unified_regime_engine as create_regime_classifier



# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import asyncio
import warnings
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import pickle

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats
from scipy.cluster.hierarchy import linkage, dendrogram, cut_tree
from scipy.spatial.distance import squareform
from sklearn.decomposition import PCA, FactorAnalysis
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
import networkx as nx
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import PerformanceMetrics
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager
from Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine import MarketRegime

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Correlation analysis parameters
DEFAULT_CORRELATION_WINDOW = 252  # 1 year of trading days
SHORT_CORRELATION_WINDOW = 60     # 3 months
LONG_CORRELATION_WINDOW = 504     # 2 years
ROLLING_WINDOW_STEP = 5           # Days between correlation calculations

# Correlation thresholds
HIGH_CORRELATION_THRESHOLD = 0.70
EXTREME_CORRELATION_THRESHOLD = 0.85
CORRELATION_SPIKE_THRESHOLD = 0.15  # Sudden correlation increase
DIVERSIFICATION_THRESHOLD = 0.30    # Below this = well diversified

# Risk monitoring parameters
MAX_CORRELATION_VIOLATIONS = 3
CORRELATION_BREACH_COOLDOWN = 300  # 5 minutes in seconds
VAR_CONFIDENCE_LEVEL = 0.05
CLUSTERING_THRESHOLD = 0.60

# ML model parameters
CORRELATION_FORECAST_HORIZON = 20  # Days to forecast
MODEL_RETRAIN_FREQUENCY = 5       # Days between model retraining
FEATURE_IMPORTANCE_THRESHOLD = 0.05

# ==============================================================================
# ENUMS
# ==============================================================================
class CorrelationRegime(Enum):
    """Market correlation regimes"""
    LOW_CORRELATION = "low_correlation"      # Average correlation < 0.3
    NORMAL_CORRELATION = "normal_correlation" # 0.3 <= correlation < 0.7
    HIGH_CORRELATION = "high_correlation"     # 0.7 <= correlation < 0.85
    CRISIS_CORRELATION = "crisis_correlation" # correlation >= 0.85

class CorrelationEvent(Enum):
    """Correlation-related events"""
    SPIKE_DETECTED = "spike_detected"
    REGIME_CHANGE = "regime_change"
    CLUSTERING_ALERT = "clustering_alert"
    DIVERSIFICATION_LOSS = "diversification_loss"
    CORRELATION_BREACH = "correlation_breach"
    FORECAST_ALERT = "forecast_alert"

class AnalysisType(Enum):
    """Types of correlation analysis"""
    PEARSON = "pearson"
    SPEARMAN = "spearman"
    KENDALL = "kendall"
    ROLLING = "rolling"
    DYNAMIC = "dynamic"
    FACTOR_BASED = "factor_based"

class ClusteringMethod(Enum):
    """Clustering methods for correlation analysis"""
    HIERARCHICAL = "hierarchical"
    KMEANS = "kmeans"
    NETWORK_BASED = "network_based"
    FACTOR_BASED = "factor_based"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CorrelationMetrics:
    """Comprehensive correlation metrics"""
    correlation_matrix: np.ndarray
    average_correlation: float
    max_correlation: float
    min_correlation: float
    correlation_dispersion: float
    eigenvalues: np.ndarray
    condition_number: float
    diversification_ratio: float
    concentration_index: float
    regime: CorrelationRegime
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RollingCorrelation:
    """Rolling correlation analysis result"""
    strategy_pair: Tuple[str, str]
    correlation_series: pd.Series
    mean_correlation: float
    correlation_volatility: float
    correlation_trend: float
    regime_transitions: List[Tuple[datetime, CorrelationRegime]]
    spike_events: List[Tuple[datetime, float]]

@dataclass
class CorrelationForecast:
    """Correlation forecast result"""
    strategy_pair: Tuple[str, str]
    forecast_horizon: int
    predicted_correlations: np.ndarray
    prediction_intervals: Tuple[np.ndarray, np.ndarray]
    model_confidence: float
    feature_importance: Dict[str, float]
    regime_probabilities: Dict[CorrelationRegime, float]

@dataclass
class ClusterAnalysis:
    """Correlation clustering analysis"""
    clusters: Dict[int, List[str]]
    cluster_correlations: Dict[int, float]
    silhouette_score: float
    dendrogram_data: Optional[Dict] = None
    network_graph: Optional[nx.Graph] = None
    stability_score: float = 0.0

@dataclass
class CorrelationAlert:
    """Correlation monitoring alert"""
    alert_type: CorrelationEvent
    severity: str  # low, medium, high, critical
    message: str
    affected_strategies: List[str]
    correlation_value: float
    threshold_breached: float
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class FactorExposure:
    """Factor-based correlation analysis"""
    factor_loadings: Dict[str, np.ndarray]
    explained_variance: np.ndarray
    factor_correlations: np.ndarray
    idiosyncratic_risks: Dict[str, float]
    common_factor_risk: float
    diversification_benefit: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class CorrelationAnalyzer:
    """
    Advanced correlation analysis and risk monitoring system.
    
    This analyzer provides comprehensive correlation analysis including real-time
    monitoring, rolling correlation windows, regime detection, clustering analysis,
    and ML-based correlation forecasting. It serves as an early warning system
    for portfolio concentration risks and correlation spikes.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        performance_metrics: Performance calculation utilities
        datetime_utils: Date/time utility functions
        
    Example:
        >>> analyzer = CorrelationAnalyzer()
        >>> analyzer.initialize()
        >>> metrics = await analyzer.analyze_portfolio_correlations(returns_data)
        >>> forecast = await analyzer.forecast_correlations(strategy_pair, horizon=20)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the correlation analyzer.
        
        Args:
            config: Configuration parameters for correlation analysis
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.performance_metrics = PerformanceMetrics()
        self.datetime_utils = DateTimeUtils()
        
        # Configuration
        self.config = config or {}
        self._load_configuration()
        
        # Data storage
        self.strategy_returns: Dict[str, pd.Series] = {}
        self.correlation_history: deque = deque(maxlen=1000)
        self.rolling_correlations: Dict[Tuple[str, str], RollingCorrelation] = {}
        self.correlation_forecasts: Dict[Tuple[str, str], CorrelationForecast] = {}
        self.cluster_history: deque = deque(maxlen=100)
        self.alert_history: deque = deque(maxlen=500)
        
        # ML models
        self.correlation_models: Dict[Tuple[str, str], RandomForestRegressor] = {}
        self.regime_model: Optional[RandomForestRegressor] = None
        self.anomaly_detector: Optional[IsolationForest] = None
        
        # Analysis state
        self.current_regime = CorrelationRegime.NORMAL_CORRELATION
        self.last_correlation_matrix: Optional[np.ndarray] = None
        self.last_analysis_time: Optional[datetime] = None
        self.model_last_trained: Optional[datetime] = None
        
        # Factor analysis components
        self.factor_model: Optional[FactorAnalysis] = None
        self.pca_model: Optional[PCA] = None
        self.scaler: StandardScaler = StandardScaler()
        
        # Alert management
        self.alert_cooldowns: Dict[str, datetime] = {}
        self.correlation_violations: defaultdict = defaultdict(int)
        
        # Initialize components
        self._initialize_models()
        
        self.logger.info("CorrelationAnalyzer initialized successfully")

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    
    def _load_configuration(self) -> None:
        """Load configuration parameters"""
        try:
            # Correlation windows
            self.correlation_window = self.config.get('correlation_window', DEFAULT_CORRELATION_WINDOW)
            self.short_window = self.config.get('short_window', SHORT_CORRELATION_WINDOW)
            self.long_window = self.config.get('long_window', LONG_CORRELATION_WINDOW)
            
            # Thresholds
            self.high_corr_threshold = self.config.get('high_correlation_threshold', HIGH_CORRELATION_THRESHOLD)
            self.extreme_corr_threshold = self.config.get('extreme_correlation_threshold', EXTREME_CORRELATION_THRESHOLD)
            self.spike_threshold = self.config.get('spike_threshold', CORRELATION_SPIKE_THRESHOLD)
            
            # ML parameters
            self.forecast_horizon = self.config.get('forecast_horizon', CORRELATION_FORECAST_HORIZON)
            self.retrain_frequency = self.config.get('retrain_frequency', MODEL_RETRAIN_FREQUENCY)
            
            self.logger.info("Configuration loaded successfully")
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to load configuration")
            # Use defaults on error
            self.correlation_window = DEFAULT_CORRELATION_WINDOW
            self.high_corr_threshold = HIGH_CORRELATION_THRESHOLD

    def _initialize_models(self) -> None:
        """Initialize machine learning models"""
        try:
            # Regime classification model
            self.regime_model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            # Anomaly detection for correlation spikes
            self.anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42
            )
            
            # Factor models
            self.factor_model = FactorAnalysis(n_components=3, random_state=42)
            self.pca_model = PCA(n_components=5)
            
            self.logger.info("ML models initialized successfully")
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to initialize ML models")

    # ==========================================================================
    # PUBLIC METHODS - MAIN ANALYSIS
    # ==========================================================================
    
    async def analyze_portfolio_correlations(self, returns_data: Dict[str, pd.Series],
                                           analysis_type: AnalysisType = AnalysisType.PEARSON) -> CorrelationMetrics:
        """
        Perform comprehensive correlation analysis on portfolio strategies.
        
        Args:
            returns_data: Dictionary of strategy returns time series
            analysis_type: Type of correlation analysis to perform
            
        Returns:
            CorrelationMetrics object with comprehensive correlation analysis
        """
        try:
            self.logger.info(f"Starting correlation analysis for {len(returns_data)} strategies")
            
            # Store returns data
            self.strategy_returns = returns_data.copy()
            
            # Align time series
            aligned_returns = self._align_returns_data(returns_data)
            
            if len(aligned_returns.columns) < 2:
                raise ValueError("Need at least 2 strategies for correlation analysis")
            
            # Calculate correlation matrix
            correlation_matrix = self._calculate_correlation_matrix(aligned_returns, analysis_type)
            
            # Calculate correlation metrics
            metrics = self._calculate_correlation_metrics(correlation_matrix)
            
            # Detect regime
            current_regime = self._detect_correlation_regime(correlation_matrix)
            metrics.regime = current_regime
            
            # Check for regime change
            if current_regime != self.current_regime:
                await self._handle_regime_change(self.current_regime, current_regime)
                self.current_regime = current_regime
            
            # Store in history
            self.correlation_history.append(metrics)
            self.last_correlation_matrix = correlation_matrix
            self.last_analysis_time = datetime.now()
            
            # Check for alerts
            await self._check_correlation_alerts(metrics, aligned_returns.columns.tolist())
            
            # Emit analysis event
            if self.event_manager:
                await self.event_manager.emit('correlation_analysis_complete', {
                    'strategy_count': len(returns_data),
                    'average_correlation': metrics.average_correlation,
                    'regime': current_regime.value,
                    'diversification_ratio': metrics.diversification_ratio
                })
            
            self.logger.info(f"Correlation analysis complete. Regime: {current_regime.value}, "
                           f"Avg correlation: {metrics.average_correlation:.3f}")
            
            return metrics
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to analyze portfolio correlations")
            # Return basic metrics on error
            n_strategies = len(returns_data)
            return CorrelationMetrics(
                correlation_matrix=np.eye(n_strategies),
                average_correlation=0.0,
                max_correlation=1.0,
                min_correlation=0.0,
                correlation_dispersion=0.0,
                eigenvalues=np.ones(n_strategies),
                condition_number=1.0,
                diversification_ratio=1.0,
                concentration_index=0.0,
                regime=CorrelationRegime.NORMAL_CORRELATION
            )

    async def calculate_rolling_correlations(self, window: int = None) -> Dict[Tuple[str, str], RollingCorrelation]:
        """
        Calculate rolling correlations for all strategy pairs.
        
        Args:
            window: Rolling window size (defaults to configured window)
            
        Returns:
            Dictionary of rolling correlation results for each strategy pair
        """
        try:
            if not self.strategy_returns:
                raise ValueError("No strategy returns data available")
            
            window = window or self.correlation_window
            self.logger.info(f"Calculating rolling correlations with window={window}")
            
            # Align returns data
            aligned_returns = self._align_returns_data(self.strategy_returns)
            strategies = aligned_returns.columns.tolist()
            
            rolling_results = {}
            
            # Calculate for all unique pairs
            for i, strategy1 in enumerate(strategies):
                for j, strategy2 in enumerate(strategies[i+1:], i+1):
                    pair = (strategy1, strategy2)
                    
                    # Calculate rolling correlation
                    rolling_corr = aligned_returns[strategy1].rolling(window).corr(aligned_returns[strategy2])
                    rolling_corr = rolling_corr.dropna()
                    
                    if len(rolling_corr) < 10:  # Need minimum data points
                        continue
                    
                    # Analyze rolling correlation
                    mean_corr = rolling_corr.mean()
                    corr_volatility = rolling_corr.std()
                    
                    # Calculate trend
                    x = np.arange(len(rolling_corr))
                    slope, _, _, _, _ = stats.linregress(x, rolling_corr.values)
                    
                    # Detect regime transitions
                    regime_transitions = self._detect_regime_transitions(rolling_corr)
                    
                    # Detect spike events
                    spike_events = self._detect_correlation_spikes(rolling_corr)
                    
                    # Create rolling correlation object
                    rolling_result = RollingCorrelation(
                        strategy_pair=pair,
                        correlation_series=rolling_corr,
                        mean_correlation=mean_corr,
                        correlation_volatility=corr_volatility,
                        correlation_trend=slope,
                        regime_transitions=regime_transitions,
                        spike_events=spike_events
                    )
                    
                    rolling_results[pair] = rolling_result
                    self.rolling_correlations[pair] = rolling_result
            
            self.logger.info(f"Rolling correlations calculated for {len(rolling_results)} strategy pairs")
            return rolling_results
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to calculate rolling correlations")
            return {}

    async def forecast_correlations(self, strategy_pair: Tuple[str, str],
                                  horizon: int = None) -> Optional[CorrelationForecast]:
        """
        Forecast correlation for a specific strategy pair using ML models.
        
        Args:
            strategy_pair: Tuple of two strategy names
            horizon: Forecast horizon in days
            
        Returns:
            CorrelationForecast object with predictions and confidence intervals
        """
        try:
            horizon = horizon or self.forecast_horizon
            self.logger.info(f"Forecasting correlations for {strategy_pair} over {horizon} days")
            
            if strategy_pair not in self.rolling_correlations:
                self.logger.warning(f"No rolling correlation data for {strategy_pair}")
                return None
            
            rolling_data = self.rolling_correlations[strategy_pair]
            correlation_series = rolling_data.correlation_series
            
            if len(correlation_series) < 50:  # Need minimum history
                self.logger.warning(f"Insufficient data for forecasting {strategy_pair}")
                return None
            
            # Prepare features and targets
            features, targets = self._prepare_forecast_features(correlation_series)
            
            if len(features) < 20:  # Need minimum training data
                return None
            
            # Train or retrain model if needed
            if (strategy_pair not in self.correlation_models or 
                self._should_retrain_model()):
                await self._train_correlation_model(strategy_pair, features, targets)
            
            model = self.correlation_models.get(strategy_pair)
            if model is None:
                return None
            
            # Generate forecast
            last_features = features[-1:].reshape(1, -1)
            predicted_correlations = []
            prediction_intervals = ([], [])
            
            # Multi-step forecast
            current_features = last_features.copy()
            for step in range(horizon):
                # Predict next correlation
                pred = model.predict(current_features)[0]
                predicted_correlations.append(pred)
                
                # Calculate prediction intervals (simplified)
                std_error = 0.05  # Simplified - would use model uncertainty
                lower_bound = pred - 1.96 * std_error
                upper_bound = pred + 1.96 * std_error
                
                prediction_intervals[0].append(lower_bound)
                prediction_intervals[1].append(upper_bound)
                
                # Update features for next step (simplified approach)
                current_features = np.roll(current_features, -1)
                current_features[0, -1] = pred
            
            # Calculate model confidence
            model_confidence = self._calculate_model_confidence(model, features, targets)
            
            # Get feature importance
            feature_importance = dict(zip(
                [f'lag_{i}' for i in range(len(features[0]))],
                model.feature_importances_
            ))
            
            # Predict regime probabilities (simplified)
            regime_probabilities = self._predict_regime_probabilities(predicted_correlations)
            
            # Create forecast object
            forecast = CorrelationForecast(
                strategy_pair=strategy_pair,
                forecast_horizon=horizon,
                predicted_correlations=np.array(predicted_correlations),
                prediction_intervals=prediction_intervals,
                model_confidence=model_confidence,
                feature_importance=feature_importance,
                regime_probabilities=regime_probabilities
            )
            
            self.correlation_forecasts[strategy_pair] = forecast
            
            self.logger.info(f"Correlation forecast complete for {strategy_pair}")
            return forecast
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to forecast correlations for {strategy_pair}")
            return None

    async def perform_cluster_analysis(self, method: ClusteringMethod = ClusteringMethod.HIERARCHICAL) -> Optional[ClusterAnalysis]:
        """
        Perform correlation clustering analysis to identify strategy groups.
        
        Args:
            method: Clustering method to use
            
        Returns:
            ClusterAnalysis object with clustering results
        """
        try:
            if self.last_correlation_matrix is None:
                self.logger.warning("No correlation matrix available for clustering")
                return None
            
            self.logger.info(f"Performing cluster analysis using {method.value}")
            
            correlation_matrix = self.last_correlation_matrix
            strategy_names = list(self.strategy_returns.keys())
            
            # Convert correlation to distance matrix
            distance_matrix = 1 - np.abs(correlation_matrix)
            
            if method == ClusteringMethod.HIERARCHICAL:
                cluster_result = self._hierarchical_clustering(distance_matrix, strategy_names)
            elif method == ClusteringMethod.NETWORK_BASED:
                cluster_result = self._network_clustering(correlation_matrix, strategy_names)
            else:
                self.logger.warning(f"Clustering method {method.value} not implemented")
                return None
            
            # Calculate cluster stability
            stability_score = self._calculate_cluster_stability(cluster_result)
            cluster_result.stability_score = stability_score
            
            # Store in history
            self.cluster_history.append(cluster_result)
            
            self.logger.info(f"Cluster analysis complete. Found {len(cluster_result.clusters)} clusters")
            return cluster_result
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to perform cluster analysis")
            return None

    # ==========================================================================
    # PRIVATE METHODS - DATA PROCESSING
    # ==========================================================================
    
    def _align_returns_data(self, returns_data: Dict[str, pd.Series]) -> pd.DataFrame:
        """Align time series data for correlation analysis"""
        try:
            # Convert to DataFrame
            df = pd.DataFrame(returns_data)
            
            # Remove rows with any NaN values
            df = df.dropna()
            
            # Ensure minimum data points
            if len(df) < self.correlation_window:
                self.logger.warning(f"Limited data: {len(df)} points, window: {self.correlation_window}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to align returns data: {e}")
            return pd.DataFrame()

    def _calculate_correlation_matrix(self, returns_df: pd.DataFrame, 
                                    analysis_type: AnalysisType) -> np.ndarray:
        """Calculate correlation matrix using specified method"""
        try:
            if analysis_type == AnalysisType.PEARSON:
                return returns_df.corr(method='pearson').values
            elif analysis_type == AnalysisType.SPEARMAN:
                return returns_df.corr(method='spearman').values
            elif analysis_type == AnalysisType.KENDALL:
                return returns_df.corr(method='kendall').values
            else:
                # Default to Pearson
                return returns_df.corr(method='pearson').values
                
        except Exception as e:
            self.logger.error(f"Failed to calculate correlation matrix: {e}")
            n = len(returns_df.columns)
            return np.eye(n)

    def _calculate_correlation_metrics(self, correlation_matrix: np.ndarray) -> CorrelationMetrics:
        """Calculate comprehensive correlation metrics"""
        try:
            # Mask diagonal elements
            mask = ~np.eye(correlation_matrix.shape[0], dtype=bool)
            correlations = correlation_matrix[mask]
            
            # Basic statistics
            avg_correlation = np.mean(correlations)
            max_correlation = np.max(correlations)
            min_correlation = np.min(correlations)
            correlation_dispersion = np.std(correlations)
            
            # Eigenvalue analysis
            eigenvalues = np.linalg.eigvals(correlation_matrix)
            eigenvalues = np.real(eigenvalues[eigenvalues > 1e-8])  # Remove near-zero eigenvalues
            condition_number = np.max(eigenvalues) / np.min(eigenvalues) if len(eigenvalues) > 0 else 1.0
            
            # Diversification ratio
            n_assets = correlation_matrix.shape[0]
            equal_weights = np.ones(n_assets) / n_assets
            portfolio_variance = np.dot(equal_weights.T, np.dot(correlation_matrix, equal_weights))
            diversification_ratio = 1.0 / np.sqrt(portfolio_variance * n_assets)
            
            # Concentration index (based on eigenvalues)
            if len(eigenvalues) > 0:
                eigenvalue_weights = eigenvalues / np.sum(eigenvalues)
                concentration_index = np.sum(eigenvalue_weights ** 2)
            else:
                concentration_index = 1.0 / n_assets
            
            return CorrelationMetrics(
                correlation_matrix=correlation_matrix,
                average_correlation=avg_correlation,
                max_correlation=max_correlation,
                min_correlation=min_correlation,
                correlation_dispersion=correlation_dispersion,
                eigenvalues=eigenvalues,
                condition_number=condition_number,
                diversification_ratio=diversification_ratio,
                concentration_index=concentration_index,
                regime=CorrelationRegime.NORMAL_CORRELATION  # Will be updated
            )
            
        except Exception as e:
            self.logger.error(f"Failed to calculate correlation metrics: {e}")
            n = correlation_matrix.shape[0] if correlation_matrix.size > 0 else 1
            return CorrelationMetrics(
                correlation_matrix=np.eye(n),
                average_correlation=0.0,
                max_correlation=1.0,
                min_correlation=0.0,
                correlation_dispersion=0.0,
                eigenvalues=np.ones(n),
                condition_number=1.0,
                diversification_ratio=1.0,
                concentration_index=1.0 / n,
                regime=CorrelationRegime.NORMAL_CORRELATION
            )

    # ==========================================================================
    # PRIVATE METHODS - REGIME DETECTION
    # ==========================================================================
    
    def _detect_correlation_regime(self, correlation_matrix: np.ndarray) -> CorrelationRegime:
        """Detect current correlation regime"""
        try:
            # Calculate average off-diagonal correlation
            mask = ~np.eye(correlation_matrix.shape[0], dtype=bool)
            avg_correlation = np.mean(np.abs(correlation_matrix[mask]))
            
            # Classify regime based on thresholds
            if avg_correlation >= self.extreme_corr_threshold:
                return CorrelationRegime.CRISIS_CORRELATION
            elif avg_correlation >= self.high_corr_threshold:
                return CorrelationRegime.HIGH_CORRELATION
            elif avg_correlation >= DIVERSIFICATION_THRESHOLD:
                return CorrelationRegime.NORMAL_CORRELATION
            else:
                return CorrelationRegime.LOW_CORRELATION
                
        except Exception as e:
            self.logger.error(f"Failed to detect correlation regime: {e}")
            return CorrelationRegime.NORMAL_CORRELATION

    async def _handle_regime_change(self, old_regime: CorrelationRegime, 
                                  new_regime: CorrelationRegime) -> None:
        """Handle correlation regime changes"""
        try:
            self.logger.info(f"Correlation regime change: {old_regime.value} → {new_regime.value}")
            
            # Create regime change alert
            alert = CorrelationAlert(
                alert_type=CorrelationEvent.REGIME_CHANGE,
                severity="high" if new_regime in [CorrelationRegime.HIGH_CORRELATION, CorrelationRegime.CRISIS_CORRELATION] else "medium",
                message=f"Correlation regime changed from {old_regime.value} to {new_regime.value}",
                affected_strategies=list(self.strategy_returns.keys()),
                correlation_value=0.0,  # Will be updated with actual value
                threshold_breached=0.0,
                recommendation=self._get_regime_recommendation(new_regime)
            )
            
            self.alert_history.append(alert)
            
            # Emit regime change event
            if self.event_manager:
                await self.event_manager.emit('correlation_regime_change', {
                    'old_regime': old_regime.value,
                    'new_regime': new_regime.value,
                    'severity': alert.severity,
                    'recommendation': alert.recommendation
                })
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to handle regime change")

    def _get_regime_recommendation(self, regime: CorrelationRegime) -> str:
        """Get recommendation based on correlation regime"""
        recommendations = {
            CorrelationRegime.LOW_CORRELATION: "Consider increasing position sizes - diversification is high",
            CorrelationRegime.NORMAL_CORRELATION: "Normal correlation levels - maintain current allocations",
            CorrelationRegime.HIGH_CORRELATION: "Reduce position sizes - diversification is compromised",
            CorrelationRegime.CRISIS_CORRELATION: "URGENT: Implement risk reduction - extreme correlation detected"
        }
        return recommendations.get(regime, "Monitor correlation levels closely")

    # ==========================================================================
    # PRIVATE METHODS - ALERT MANAGEMENT
    # ==========================================================================
    
    async def _check_correlation_alerts(self, metrics: CorrelationMetrics, strategies: List[str]) -> None:
        """Check for correlation-based alerts"""
        try:
            current_time = datetime.now()
            
            # Check for high correlation
            if metrics.average_correlation > self.high_corr_threshold:
                await self._trigger_correlation_alert(
                    CorrelationEvent.CORRELATION_BREACH,
                    "High average correlation detected",
                    strategies,
                    metrics.average_correlation,
                    self.high_corr_threshold,
                    "critical" if metrics.average_correlation > self.extreme_corr_threshold else "high"
                )
            
            # Check for poor diversification
            if metrics.diversification_ratio < DIVERSIFICATION_THRESHOLD:
                await self._trigger_correlation_alert(
                    CorrelationEvent.DIVERSIFICATION_LOSS,
                    "Portfolio diversification compromised",
                    strategies,
                    metrics.diversification_ratio,
                    DIVERSIFICATION_THRESHOLD,
                    "high"
                )
            
            # Check for concentration risk
            if metrics.concentration_index > 0.8:
                await self._trigger_correlation_alert(
                    CorrelationEvent.CLUSTERING_ALERT,
                    "High concentration risk detected",
                    strategies,
                    metrics.concentration_index,
                    0.8,
                    "medium"
                )
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to check correlation alerts")

    async def _trigger_correlation_alert(self, alert_type: CorrelationEvent, 
                                       message: str, strategies: List[str],
                                       value: float, threshold: float, 
                                       severity: str) -> None:
        """Trigger a correlation alert with cooldown management"""
        try:
            alert_key = f"{alert_type.value}_{severity}"
            current_time = datetime.now()
            
            # Check cooldown
            if alert_key in self.alert_cooldowns:
                time_since_last = (current_time - self.alert_cooldowns[alert_key]).total_seconds()
                if time_since_last < CORRELATION_BREACH_COOLDOWN:
                    return
            
            # Create alert
            alert = CorrelationAlert(
                alert_type=alert_type,
                severity=severity,
                message=message,
                affected_strategies=strategies,
                correlation_value=value,
                threshold_breached=threshold,
                recommendation=self._get_alert_recommendation(alert_type, severity)
            )
            
            self.alert_history.append(alert)
            self.alert_cooldowns[alert_key] = current_time
            
            # Emit alert event
            if self.event_manager:
                await self.event_manager.emit('correlation_alert', {
                    'alert_type': alert_type.value,
                    'severity': severity,
                    'message': message,
                    'value': value,
                    'threshold': threshold
                })
            
            self.logger.warning(f"Correlation alert: {alert_type.value} - {message}")
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to trigger correlation alert")

    def _get_alert_recommendation(self, alert_type: CorrelationEvent, severity: str) -> str:
        """Get recommendation for correlation alert"""
        recommendations = {
            CorrelationEvent.CORRELATION_BREACH: {
                "medium": "Monitor correlations closely and consider position adjustments",
                "high": "Reduce position sizes to manage correlation risk",
                "critical": "IMMEDIATE ACTION: Reduce positions and implement hedging"
            },
            CorrelationEvent.DIVERSIFICATION_LOSS: {
                "medium": "Review strategy mix for better diversification",
                "high": "Add uncorrelated strategies or reduce correlated positions",
                "critical": "Emergency diversification measures required"
            },
            CorrelationEvent.CLUSTERING_ALERT: {
                "medium": "Monitor for strategy clustering effects",
                "high": "Rebalance to reduce strategy concentration",
                "critical": "Urgent rebalancing required"
            }
        }
        
        return recommendations.get(alert_type, {}).get(severity, "Monitor situation closely")

    # ==========================================================================
    # PRIVATE METHODS - SPIKE DETECTION
    # ==========================================================================
    
    def _detect_regime_transitions(self, correlation_series: pd.Series) -> List[Tuple[datetime, CorrelationRegime]]:
        """Detect regime transitions in correlation series"""
        try:
            transitions = []
            current_regime = None
            
            for timestamp, correlation in correlation_series.items():
                # Determine regime for this correlation value
                if abs(correlation) >= self.extreme_corr_threshold:
                    regime = CorrelationRegime.CRISIS_CORRELATION
                elif abs(correlation) >= self.high_corr_threshold:
                    regime = CorrelationRegime.HIGH_CORRELATION
                elif abs(correlation) >= DIVERSIFICATION_THRESHOLD:
                    regime = CorrelationRegime.NORMAL_CORRELATION
                else:
                    regime = CorrelationRegime.LOW_CORRELATION
                
                # Check for regime change
                if regime != current_regime:
                    transitions.append((timestamp, regime))
                    current_regime = regime
            
            return transitions
            
        except Exception as e:
            self.logger.error(f"Failed to detect regime transitions: {e}")
            return []

    def _detect_correlation_spikes(self, correlation_series: pd.Series) -> List[Tuple[datetime, float]]:
        """Detect sudden correlation spikes"""
        try:
            spikes = []
            
            # Calculate rolling changes
            correlation_changes = correlation_series.diff().abs()
            
            # Detect spikes above threshold
            spike_mask = correlation_changes > self.spike_threshold
            
            for timestamp, is_spike in spike_mask.items():
                if is_spike and not pd.isna(correlation_changes[timestamp]):
                    spike_value = correlation_changes[timestamp]
                    spikes.append((timestamp, spike_value))
            
            return spikes
            
        except Exception as e:
            self.logger.error(f"Failed to detect correlation spikes: {e}")
            return []

    # ==========================================================================
    # PRIVATE METHODS - ML FORECASTING
    # ==========================================================================
    
    def _prepare_forecast_features(self, correlation_series: pd.Series) -> Tuple[np.ndarray, np.ndarray]:
        """Prepare features for correlation forecasting"""
        try:
            # Use lagged values as features
            n_lags = min(10, len(correlation_series) // 5)
            
            features = []
            targets = []
            
            for i in range(n_lags, len(correlation_series)):
                # Features: lagged correlations
                feature_vector = correlation_series.iloc[i-n_lags:i].values
                target = correlation_series.iloc[i]
                
                features.append(feature_vector)
                targets.append(target)
            
            return np.array(features), np.array(targets)
            
        except Exception as e:
            self.logger.error(f"Failed to prepare forecast features: {e}")
            return np.array([]), np.array([])

    async def _train_correlation_model(self, strategy_pair: Tuple[str, str], 
                                     features: np.ndarray, targets: np.ndarray) -> None:
        """Train ML model for correlation forecasting"""
        try:
            if len(features) < 20:  # Need minimum training data
                return
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                features, targets, test_size=0.2, random_state=42
            )
            
            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            
            model.fit(X_train, y_train)
            
            # Validate model
            y_pred = model.predict(X_test)
            r2 = r2_score(y_test, y_pred)
            mse = mean_squared_error(y_test, y_pred)
            
            self.logger.info(f"Model trained for {strategy_pair}: R²={r2:.3f}, MSE={mse:.6f}")
            
            # Store model
            self.correlation_models[strategy_pair] = model
            self.model_last_trained = datetime.now()
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to train model for {strategy_pair}")

    def _should_retrain_model(self) -> bool:
        """Check if models should be retrained"""
        if self.model_last_trained is None:
            return True
        
        days_since_training = (datetime.now() - self.model_last_trained).days
        return days_since_training >= self.retrain_frequency

    def _calculate_model_confidence(self, model: RandomForestRegressor, 
                                  features: np.ndarray, targets: np.ndarray) -> float:
        """Calculate model confidence score"""
        try:
            if len(features) < 10:
                return 0.0
            
            # Use out-of-bag score if available
            if hasattr(model, 'oob_score_') and model.oob_score_ is not None:
                return max(0.0, min(1.0, model.oob_score_))
            
            # Fallback to simple validation
            predictions = model.predict(features)
            r2 = r2_score(targets, predictions)
            return max(0.0, min(1.0, r2))
            
        except Exception as e:
            self.logger.error(f"Failed to calculate model confidence: {e}")
            return 0.5

    def _predict_regime_probabilities(self, predicted_correlations: List[float]) -> Dict[CorrelationRegime, float]:
        """Predict regime probabilities from correlation forecasts"""
        try:
            regime_counts = {regime: 0 for regime in CorrelationRegime}
            
            for corr in predicted_correlations:
                abs_corr = abs(corr)
                if abs_corr >= self.extreme_corr_threshold:
                    regime_counts[CorrelationRegime.CRISIS_CORRELATION] += 1
                elif abs_corr >= self.high_corr_threshold:
                    regime_counts[CorrelationRegime.HIGH_CORRELATION] += 1
                elif abs_corr >= DIVERSIFICATION_THRESHOLD:
                    regime_counts[CorrelationRegime.NORMAL_CORRELATION] += 1
                else:
                    regime_counts[CorrelationRegime.LOW_CORRELATION] += 1
            
            total_predictions = len(predicted_correlations)
            regime_probabilities = {
                regime: count / total_predictions 
                for regime, count in regime_counts.items()
            }
            
            return regime_probabilities
            
        except Exception as e:
            self.logger.error(f"Failed to predict regime probabilities: {e}")
            return {regime: 0.25 for regime in CorrelationRegime}

    # ==========================================================================
    # PRIVATE METHODS - CLUSTERING
    # ==========================================================================
    
    def _hierarchical_clustering(self, distance_matrix: np.ndarray, 
                               strategy_names: List[str]) -> ClusterAnalysis:
        """Perform hierarchical clustering analysis"""
        try:
            # Convert to condensed distance matrix
            condensed_distances = squareform(distance_matrix)
            
            # Perform hierarchical clustering
            linkage_matrix = linkage(condensed_distances, method='ward')
            
            # Determine number of clusters
            n_clusters = min(max(2, len(strategy_names) // 3), 5)
            cluster_labels = cut_tree(linkage_matrix, n_clusters=n_clusters).flatten()
            
            # Create clusters dictionary
            clusters = defaultdict(list)
            for i, label in enumerate(cluster_labels):
                clusters[label].append(strategy_names[i])
            
            clusters = dict(clusters)
            
            # Calculate cluster correlations
            cluster_correlations = {}
            original_corr_matrix = 1 - distance_matrix
            
            for cluster_id, strategies in clusters.items():
                if len(strategies) > 1:
                    # Get indices for strategies in this cluster
                    indices = [strategy_names.index(s) for s in strategies]
                    cluster_corr_submatrix = original_corr_matrix[np.ix_(indices, indices)]
                    
                    # Calculate average correlation within cluster
                    mask = ~np.eye(len(indices), dtype=bool)
                    avg_corr = np.mean(cluster_corr_submatrix[mask])
                    cluster_correlations[cluster_id] = avg_corr
                else:
                    cluster_correlations[cluster_id] = 0.0
            
            # Calculate silhouette score (simplified)
            silhouette_score = self._calculate_silhouette_score(
                distance_matrix, cluster_labels
            )
            
            return ClusterAnalysis(
                clusters=clusters,
                cluster_correlations=cluster_correlations,
                silhouette_score=silhouette_score,
                dendrogram_data={'linkage_matrix': linkage_matrix}
            )
            
        except Exception as e:
            self.logger.error(f"Failed to perform hierarchical clustering: {e}")
            # Return single cluster fallback
            return ClusterAnalysis(
                clusters={0: strategy_names},
                cluster_correlations={0: 0.0},
                silhouette_score=0.0
            )

    def _network_clustering(self, correlation_matrix: np.ndarray,
                          strategy_names: List[str]) -> ClusterAnalysis:
        """Perform network-based clustering analysis"""
        try:
            # Create network graph
            G = nx.Graph()
            
            # Add nodes
            for strategy in strategy_names:
                G.add_node(strategy)
            
            # Add edges for high correlations
            for i, strategy1 in enumerate(strategy_names):
                for j, strategy2 in enumerate(strategy_names[i+1:], i+1):
                    correlation = abs(correlation_matrix[i, j])
                    if correlation > CLUSTERING_THRESHOLD:
                        G.add_edge(strategy1, strategy2, weight=correlation)
            
            # Find communities using greedy modularity optimization
            try:
                communities = nx.algorithms.community.greedy_modularity_communities(G)
                
                # Convert to clusters dictionary
                clusters = {}
                for i, community in enumerate(communities):
                    clusters[i] = list(community)
                
                # Calculate cluster correlations
                cluster_correlations = {}
                for cluster_id, strategies in clusters.items():
                    if len(strategies) > 1:
                        indices = [strategy_names.index(s) for s in strategies]
                        cluster_corr_submatrix = correlation_matrix[np.ix_(indices, indices)]
                        mask = ~np.eye(len(indices), dtype=bool)
                        avg_corr = np.mean(np.abs(cluster_corr_submatrix[mask]))
                        cluster_correlations[cluster_id] = avg_corr
                    else:
                        cluster_correlations[cluster_id] = 0.0
                
                # Simple silhouette score approximation
                silhouette_score = 0.5  # Simplified for network clustering
                
                return ClusterAnalysis(
                    clusters=clusters,
                    cluster_correlations=cluster_correlations,
                    silhouette_score=silhouette_score,
                    network_graph=G
                )
                
            except:
                # Fallback to single cluster
                return ClusterAnalysis(
                    clusters={0: strategy_names},
                    cluster_correlations={0: 0.0},
                    silhouette_score=0.0,
                    network_graph=G
                )
            
        except Exception as e:
            self.logger.error(f"Failed to perform network clustering: {e}")
            return ClusterAnalysis(
                clusters={0: strategy_names},
                cluster_correlations={0: 0.0},
                silhouette_score=0.0
            )

    def _calculate_silhouette_score(self, distance_matrix: np.ndarray,
                                  cluster_labels: np.ndarray) -> float:
        """Calculate simplified silhouette score"""
        try:
            n_points = len(cluster_labels)
            if n_points < 2:
                return 0.0
            
            scores = []
            
            for i in range(n_points):
                # Calculate average distance to points in same cluster
                same_cluster = cluster_labels == cluster_labels[i]
                same_cluster[i] = False  # Exclude self
                
                if np.sum(same_cluster) > 0:
                    a = np.mean(distance_matrix[i, same_cluster])
                else:
                    a = 0.0
                
                # Calculate average distance to points in nearest other cluster
                other_clusters = np.unique(cluster_labels[cluster_labels != cluster_labels[i]])
                
                if len(other_clusters) > 0:
                    min_dist = float('inf')
                    for other_cluster in other_clusters:
                        other_cluster_mask = cluster_labels == other_cluster
                        if np.sum(other_cluster_mask) > 0:
                            avg_dist = np.mean(distance_matrix[i, other_cluster_mask])
                            min_dist = min(min_dist, avg_dist)
                    b = min_dist if min_dist != float('inf') else 0.0
                else:
                    b = 0.0
                
                # Calculate silhouette score
                if max(a, b) > 0:
                    score = (b - a) / max(a, b)
                else:
                    score = 0.0
                
                scores.append(score)
            
            return np.mean(scores)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate silhouette score: {e}")
            return 0.0

    def _calculate_cluster_stability(self, cluster_result: ClusterAnalysis) -> float:
        """Calculate cluster stability score"""
        try:
            # Simple stability metric based on cluster sizes and correlations
            if not cluster_result.clusters:
                return 0.0
            
            total_strategies = sum(len(strategies) for strategies in cluster_result.clusters.values())
            
            stability_scores = []
            for cluster_id, strategies in cluster_result.clusters.items():
                cluster_size = len(strategies)
                cluster_correlation = cluster_result.cluster_correlations.get(cluster_id, 0.0)
                
                # Higher correlation and balanced size contribute to stability
                size_score = min(1.0, cluster_size / (total_strategies / len(cluster_result.clusters)))
                correlation_score = min(1.0, abs(cluster_correlation))
                
                cluster_stability = (size_score + correlation_score) / 2
                stability_scores.append(cluster_stability)
            
            return np.mean(stability_scores)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate cluster stability: {e}")
            return 0.0

    # ==========================================================================
    # PUBLIC METHODS - UTILITIES AND REPORTING
    # ==========================================================================
    
    def get_correlation_summary(self) -> Dict[str, Any]:
        """Get comprehensive correlation analysis summary"""
        try:
            if not self.correlation_history:
                return {}
            
            latest_metrics = self.correlation_history[-1]
            
            summary = {
                'current_regime': self.current_regime.value,
                'average_correlation': latest_metrics.average_correlation,
                'max_correlation': latest_metrics.max_correlation,
                'diversification_ratio': latest_metrics.diversification_ratio,
                'concentration_index': latest_metrics.concentration_index,
                'condition_number': latest_metrics.condition_number,
                'strategy_count': len(self.strategy_returns),
                'last_analysis': self.last_analysis_time.isoformat() if self.last_analysis_time else None,
                'rolling_correlations_count': len(self.rolling_correlations),
                'forecasts_available': len(self.correlation_forecasts),
                'recent_alerts': len([a for a in self.alert_history if (datetime.now() - a.timestamp).days < 1])
            }
            
            return summary
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to get correlation summary")
            return {}

    def get_strategy_correlation_profile(self, strategy_name: str) -> Dict[str, Any]:
        """Get correlation profile for a specific strategy"""
        try:
            if strategy_name not in self.strategy_returns:
                return {}
            
            profile = {
                'strategy_name': strategy_name,
                'correlations_with_others': {},
                'average_correlation': 0.0,
                'max_correlation': 0.0,
                'correlation_rank': 0,  # How correlated compared to other strategies
                'diversification_contribution': 0.0
            }
            
            # Get correlations with other strategies
            correlations = []
            for pair, rolling_corr in self.rolling_correlations.items():
                if strategy_name in pair:
                    other_strategy = pair[1] if pair[0] == strategy_name else pair[0]
                    correlation = rolling_corr.mean_correlation
                    profile['correlations_with_others'][other_strategy] = correlation
                    correlations.append(abs(correlation))
            
            if correlations:
                profile['average_correlation'] = np.mean(correlations)
                profile['max_correlation'] = np.max(correlations)
                
                # Calculate rank (lower correlation = better diversification = higher rank)
                all_avg_correlations = []
                for strategy in self.strategy_returns.keys():
                    strategy_correlations = []
                    for pair, rolling_corr in self.rolling_correlations.items():
                        if strategy in pair:
                            strategy_correlations.append(abs(rolling_corr.mean_correlation))
                    if strategy_correlations:
                        all_avg_correlations.append((strategy, np.mean(strategy_correlations)))
                
                # Sort by correlation (ascending = better diversification)
                all_avg_correlations.sort(key=lambda x: x[1])
                for rank, (strat, _) in enumerate(all_avg_correlations, 1):
                    if strat == strategy_name:
                        profile['correlation_rank'] = rank
                        break
                
                # Diversification contribution (inverse of correlation)
                profile['diversification_contribution'] = 1.0 - profile['average_correlation']
            
            return profile
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to get correlation profile for {strategy_name}")
            return {}

    async def generate_correlation_report(self) -> Dict[str, Any]:
        """Generate comprehensive correlation analysis report"""
        try:
            self.logger.info("Generating correlation analysis report")
            
            report = {
                'timestamp': datetime.now().isoformat(),
                'summary': self.get_correlation_summary(),
                'current_metrics': None,
                'regime_analysis': {},
                'strategy_profiles': {},
                'cluster_analysis': None,
                'alerts_summary': {},
                'forecasts_summary': {},
                'recommendations': []
            }
            
            # Current metrics
            if self.correlation_history:
                latest_metrics = self.correlation_history[-1]
                report['current_metrics'] = {
                    'average_correlation': latest_metrics.average_correlation,
                    'max_correlation': latest_metrics.max_correlation,
                    'min_correlation': latest_metrics.min_correlation,
                    'diversification_ratio': latest_metrics.diversification_ratio,
                    'concentration_index': latest_metrics.concentration_index,
                    'regime': latest_metrics.regime.value
                }
            
            # Regime analysis
            regime_counts = defaultdict(int)
            for metrics in list(self.correlation_history)[-30:]:  # Last 30 analyses
                regime_counts[metrics.regime] += 1
            
            report['regime_analysis'] = {
                'current_regime': self.current_regime.value,
                'recent_regime_distribution': {regime.value: count for regime, count in regime_counts.items()},
                'regime_stability': max(regime_counts.values()) / len(self.correlation_history[-30:]) if self.correlation_history else 0.0
            }
            
            # Strategy profiles
            for strategy_name in self.strategy_returns.keys():
                report['strategy_profiles'][strategy_name] = self.get_strategy_correlation_profile(strategy_name)
            
            # Cluster analysis
            if self.cluster_history:
                latest_cluster = self.cluster_history[-1]
                report['cluster_analysis'] = {
                    'clusters': latest_cluster.clusters,
                    'cluster_correlations': latest_cluster.cluster_correlations,
                    'silhouette_score': latest_cluster.silhouette_score,
                    'stability_score': latest_cluster.stability_score
                }
            
            # Alerts summary
            recent_alerts = [a for a in self.alert_history if (datetime.now() - a.timestamp).days < 7]
            alert_counts = defaultdict(int)
            for alert in recent_alerts:
                alert_counts[alert.alert_type] += 1
            
            report['alerts_summary'] = {
                'total_recent_alerts': len(recent_alerts),
                'alert_breakdown': {alert_type.value: count for alert_type, count in alert_counts.items()},
                'critical_alerts': len([a for a in recent_alerts if a.severity == 'critical']),
                'latest_alerts': [
                    {
                        'type': alert.alert_type.value,
                        'severity': alert.severity,
                        'message': alert.message,
                        'timestamp': alert.timestamp.isoformat()
                    }
                    for alert in list(self.alert_history)[-5:]
                ]
            }
            
            # Forecasts summary
            report['forecasts_summary'] = {
                'available_forecasts': len(self.correlation_forecasts),
                'forecast_horizon': self.forecast_horizon,
                'average_model_confidence': np.mean([f.model_confidence for f in self.correlation_forecasts.values()]) if self.correlation_forecasts else 0.0
            }
            
            # Generate recommendations
            report['recommendations'] = self._generate_recommendations(report)
            
            self.logger.info("Correlation analysis report generated successfully")
            return report
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to generate correlation report")
            return {'error': 'Failed to generate report', 'timestamp': datetime.now().isoformat()}

    def _generate_recommendations(self, report: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on correlation analysis"""
        try:
            recommendations = []
            
            # Current metrics recommendations
            current_metrics = report.get('current_metrics', {})
            if current_metrics:
                avg_corr = current_metrics.get('average_correlation', 0.0)
                diversification_ratio = current_metrics.get('diversification_ratio', 1.0)
                
                if avg_corr > self.extreme_corr_threshold:
                    recommendations.append("URGENT: Extremely high correlations detected. Implement immediate risk reduction measures.")
                elif avg_corr > self.high_corr_threshold:
                    recommendations.append("High correlations detected. Consider reducing position sizes and adding uncorrelated strategies.")
                
                if diversification_ratio < DIVERSIFICATION_THRESHOLD:
                    recommendations.append("Poor portfolio diversification. Review strategy mix and consider adding diverse strategies.")
            
            # Regime-based recommendations
            current_regime = self.current_regime
            if current_regime == CorrelationRegime.CRISIS_CORRELATION:
                recommendations.append("Crisis correlation regime detected. Activate defensive protocols and reduce leverage.")
            elif current_regime == CorrelationRegime.HIGH_CORRELATION:
                recommendations.append("High correlation regime. Monitor positions closely and prepare for potential regime change.")
            
            # Alert-based recommendations
            alerts_summary = report.get('alerts_summary', {})
            critical_alerts = alerts_summary.get('critical_alerts', 0)
            if critical_alerts > 0:
                recommendations.append(f"Multiple critical alerts ({critical_alerts}) in past week. Review risk management protocols.")
            
            # Cluster-based recommendations
            cluster_analysis = report.get('cluster_analysis')
            if cluster_analysis:
                n_clusters = len(cluster_analysis.get('clusters', {}))
                n_strategies = len(self.strategy_returns)
                if n_clusters < max(2, n_strategies // 4):
                    recommendations.append("Few distinct strategy clusters detected. Consider adding strategies from different market segments.")
            
            # Model confidence recommendations
            forecasts_summary = report.get('forecasts_summary', {})
            avg_confidence = forecasts_summary.get('average_model_confidence', 0.0)
            if avg_confidence < 0.5:
                recommendations.append("Low model confidence for correlation forecasts. Increase data collection period.")
            
            # General recommendations
            if not recommendations:
                recommendations.append("Correlation metrics appear healthy. Continue monitoring and maintain current diversification strategy.")
            
            return recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to generate recommendations: {e}")
            return ["Unable to generate recommendations due to analysis error."]

    # ==========================================================================
    # PUBLIC METHODS - ADVANCED ANALYSIS
    # ==========================================================================
    
    async def perform_factor_analysis(self, n_factors: int = 3) -> Optional[FactorExposure]:
        """
        Perform factor analysis to identify common risk factors.
        
        Args:
            n_factors: Number of factors to extract
            
        Returns:
            FactorExposure object with factor analysis results
        """
        try:
            if not self.strategy_returns:
                self.logger.warning("No strategy returns data available for factor analysis")
                return None
            
            self.logger.info(f"Performing factor analysis with {n_factors} factors")
            
            # Prepare data
            aligned_returns = self._align_returns_data(self.strategy_returns)
            if len(aligned_returns) < 50:  # Need sufficient data
                self.logger.warning("Insufficient data for factor analysis")
                return None
            
            # Standardize returns
            scaled_returns = self.scaler.fit_transform(aligned_returns)
            strategy_names = aligned_returns.columns.tolist()
            
            # Fit factor model
            self.factor_model = FactorAnalysis(n_components=n_factors, random_state=42)
            factor_scores = self.factor_model.fit_transform(scaled_returns)
            
            # Get factor loadings
            factor_loadings = {}
            loadings_matrix = self.factor_model.components_.T
            
            for i, strategy in enumerate(strategy_names):
                factor_loadings[strategy] = loadings_matrix[i, :]
            
            # Calculate explained variance (approximation)
            # Transform data to factor space and back
            reconstructed = self.factor_model.inverse_transform(factor_scores)
            reconstruction_errors = np.mean((scaled_returns - reconstructed) ** 2, axis=0)
            total_variance = np.var(scaled_returns, axis=0)
            explained_variance_ratio = 1 - (reconstruction_errors / total_variance)
            
            # Calculate factor correlations
            factor_correlations = np.corrcoef(factor_scores.T)
            
            # Calculate idiosyncratic risks
            idiosyncratic_risks = {}
            for i, strategy in enumerate(strategy_names):
                idiosyncratic_risks[strategy] = reconstruction_errors[i]
            
            # Calculate common factor risk vs idiosyncratic risk
            common_factor_variance = np.mean(1 - reconstruction_errors / total_variance)
            common_factor_risk = np.sqrt(common_factor_variance)
            
            # Calculate diversification benefit
            portfolio_variance = np.mean(total_variance)
            diversification_benefit = 1 - (common_factor_risk / np.sqrt(portfolio_variance))
            
            factor_exposure = FactorExposure(
                factor_loadings=factor_loadings,
                explained_variance=explained_variance_ratio,
                factor_correlations=factor_correlations,
                idiosyncratic_risks=idiosyncratic_risks,
                common_factor_risk=common_factor_risk,
                diversification_benefit=diversification_benefit
            )
            
            self.logger.info(f"Factor analysis complete. Common factor risk: {common_factor_risk:.3f}")
            return factor_exposure
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to perform factor analysis")
            return None

    async def detect_correlation_anomalies(self) -> List[Dict[str, Any]]:
        """
        Detect anomalous correlation patterns using isolation forest.
        
        Returns:
            List of detected anomalies with details
        """
        try:
            if not self.correlation_history:
                return []
            
            self.logger.info("Detecting correlation anomalies")
            
            # Prepare feature matrix from correlation history
            features = []
            timestamps = []
            
            for metrics in self.correlation_history:
                # Flatten correlation matrix (upper triangle only)
                corr_matrix = metrics.correlation_matrix
                upper_triangle = corr_matrix[np.triu_indices_from(corr_matrix, k=1)]
                
                feature_vector = [
                    metrics.average_correlation,
                    metrics.max_correlation,
                    metrics.min_correlation,
                    metrics.correlation_dispersion,
                    metrics.diversification_ratio,
                    metrics.concentration_index,
                    np.log(metrics.condition_number + 1e-8),
                    *upper_triangle[:10]  # First 10 correlations to limit dimensionality
                ]
                
                features.append(feature_vector)
                timestamps.append(metrics.timestamp)
            
            if len(features) < 20:  # Need minimum data for anomaly detection
                return []
            
            features_array = np.array(features)
            
            # Handle any infinite or NaN values
            features_array = np.nan_to_num(features_array, nan=0.0, posinf=1.0, neginf=-1.0)
            
            # Fit isolation forest
            self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
            anomaly_labels = self.anomaly_detector.fit_predict(features_array)
            anomaly_scores = self.anomaly_detector.score_samples(features_array)
            
            # Identify anomalies
            anomalies = []
            for i, (label, score, timestamp) in enumerate(zip(anomaly_labels, anomaly_scores, timestamps)):
                if label == -1:  # Anomaly detected
                    metrics = list(self.correlation_history)[i]
                    
                    anomaly = {
                        'timestamp': timestamp.isoformat(),
                        'anomaly_score': float(score),
                        'average_correlation': metrics.average_correlation,
                        'max_correlation': metrics.max_correlation,
                        'diversification_ratio': metrics.diversification_ratio,
                        'regime': metrics.regime.value,
                        'description': self._describe_anomaly(metrics, score)
                    }
                    
                    anomalies.append(anomaly)
            
            # Sort by anomaly score (most anomalous first)
            anomalies.sort(key=lambda x: x['anomaly_score'])
            
            self.logger.info(f"Detected {len(anomalies)} correlation anomalies")
            return anomalies
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to detect correlation anomalies")
            return []

    def _describe_anomaly(self, metrics: CorrelationMetrics, anomaly_score: float) -> str:
        """Generate description for detected anomaly"""
        try:
            descriptions = []
            
            if metrics.average_correlation > self.extreme_corr_threshold:
                descriptions.append("extremely high average correlation")
            elif metrics.average_correlation > self.high_corr_threshold:
                descriptions.append("high average correlation")
            
            if metrics.diversification_ratio < 0.3:
                descriptions.append("very poor diversification")
            elif metrics.diversification_ratio < 0.5:
                descriptions.append("poor diversification")
            
            if metrics.condition_number > 100:
                descriptions.append("high condition number indicating numerical instability")
            
            if metrics.concentration_index > 0.8:
                descriptions.append("high concentration risk")
            
            if not descriptions:
                descriptions.append("unusual correlation pattern")
            
            severity = "high" if anomaly_score < -0.5 else "medium" if anomaly_score < -0.2 else "low"
            
            return f"Anomaly detected ({severity} severity): {', '.join(descriptions)}"
            
        except Exception as e:
            return f"Anomaly detected (score: {anomaly_score:.3f})"

    # ==========================================================================
    # PUBLIC METHODS - INTEGRATION AND MONITORING
    # ==========================================================================
    
    async def start_real_time_monitoring(self, update_frequency: int = 300) -> None:
        """
        Start real-time correlation monitoring.
        
        Args:
            update_frequency: Update frequency in seconds
        """
        try:
            self.logger.info(f"Starting real-time correlation monitoring (frequency: {update_frequency}s)")
            
            while True:
                # Perform correlation analysis if we have data
                if self.strategy_returns:
                    await self.analyze_portfolio_correlations(self.strategy_returns)
                    
                    # Check for anomalies periodically
                    if len(self.correlation_history) % 10 == 0:
                        await self.detect_correlation_anomalies()
                    
                    # Update rolling correlations
                    await self.calculate_rolling_correlations()
                    
                    # Generate forecasts for key pairs
                    for pair in list(self.rolling_correlations.keys())[:5]:  # Limit to top 5 pairs
                        await self.forecast_correlations(pair)
                
                # Wait for next update
                await asyncio.sleep(update_frequency)
                
        except asyncio.CancelledError:
            self.logger.info("Real-time correlation monitoring stopped")
        except Exception as e:
            self.error_handler.handle_error(e, "Error in real-time correlation monitoring")

    def update_strategy_returns(self, strategy_name: str, returns_data: pd.Series) -> None:
        """
        Update returns data for a specific strategy.
        
        Args:
            strategy_name: Name of the strategy
            returns_data: New returns time series
        """
        try:
            self.strategy_returns[strategy_name] = returns_data
            self.logger.debug(f"Updated returns data for strategy: {strategy_name}")
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to update returns for {strategy_name}")

    def get_active_alerts(self, max_age_hours: int = 24) -> List[CorrelationAlert]:
        """
        Get active correlation alerts within specified time window.
        
        Args:
            max_age_hours: Maximum age of alerts in hours
            
        Returns:
            List of active alerts
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            active_alerts = [
                alert for alert in self.alert_history
                if alert.timestamp > cutoff_time
            ]
            
            return active_alerts
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to get active alerts")
            return []

    def clear_old_data(self, days_to_keep: int = 30) -> None:
        """
        Clear old data to manage memory usage.
        
        Args:
            days_to_keep: Number of days of data to retain
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Clear old correlation history
            self.correlation_history = deque(
                [metrics for metrics in self.correlation_history 
                 if metrics.timestamp > cutoff_date],
                maxlen=1000
            )
            
            # Clear old alerts
            self.alert_history = deque(
                [alert for alert in self.alert_history 
                 if alert.timestamp > cutoff_date],
                maxlen=500
            )
            
            # Clear old alert cooldowns
            self.alert_cooldowns = {
                key: timestamp for key, timestamp in self.alert_cooldowns.items()
                if timestamp > cutoff_date
            }
            
            self.logger.info(f"Cleared data older than {days_to_keep} days")
            
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to clear old data")

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def export_correlation_data(self, file_path: str, format: str = 'json') -> bool:
        """
        Export correlation analysis data to file.
        
        Args:
            file_path: Path to save the data
            format: Export format ('json', 'pickle', 'csv')
            
        Returns:
            Success status
        """
        try:
            export_data = {
                'correlation_history': [
                    {
                        'timestamp': metrics.timestamp.isoformat(),
                        'average_correlation': metrics.average_correlation,
                        'max_correlation': metrics.max_correlation,
                        'diversification_ratio': metrics.diversification_ratio,
                        'regime': metrics.regime.value,
                        'correlation_matrix': metrics.correlation_matrix.tolist()
                    }
                    for metrics in self.correlation_history
                ],
                'rolling_correlations': {
                    f"{pair[0]}_{pair[1]}": {
                        'mean_correlation': rolling.mean_correlation,
                        'correlation_volatility': rolling.correlation_volatility,
                        'correlation_trend': rolling.correlation_trend,
                        'correlation_series': rolling.correlation_series.to_dict()
                    }
                    for pair, rolling in self.rolling_correlations.items()
                },
                'alerts': [
                    {
                        'timestamp': alert.timestamp.isoformat(),
                        'alert_type': alert.alert_type.value,
                        'severity': alert.severity,
                        'message': alert.message,
                        'correlation_value': alert.correlation_value
                    }
                    for alert in self.alert_history
                ]
            }
            
            if format.lower() == 'json':
                import json
                with open(file_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
            elif format.lower() == 'pickle':
                with open(file_path, 'wb') as f:
                    pickle.dump(export_data, f)
            elif format.lower() == 'csv':
                # Export correlation history as CSV
                df = pd.DataFrame([
                    {
                        'timestamp': metrics.timestamp,
                        'average_correlation': metrics.average_correlation,
                        'max_correlation': metrics.max_correlation,
                        'diversification_ratio': metrics.diversification_ratio,
                        'regime': metrics.regime.value
                    }
                    for metrics in self.correlation_history
                ])
                df.to_csv(file_path, index=False)
            else:
                raise ValueError(f"Unsupported export format: {format}")
            
            self.logger.info(f"Correlation data exported to {file_path}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to export correlation data to {file_path}")
            return False

    def import_correlation_data(self, file_path: str, format: str = 'json') -> bool:
        """
        Import correlation analysis data from file.
        
        Args:
            file_path: Path to the data file
            format: Import format ('json', 'pickle')
            
        Returns:
            Success status
        """
        try:
            if format.lower() == 'json':
                import json
                with open(file_path, 'r') as f:
                    import_data = json.load(f)
            elif format.lower() == 'pickle':
                with open(file_path, 'rb') as f:
                    import_data = pickle.load(f)
            else:
                raise ValueError(f"Unsupported import format: {format}")
            
            # Reconstruct correlation history
            for hist_data in import_data.get('correlation_history', []):
                metrics = CorrelationMetrics(
                    correlation_matrix=np.array(hist_data['correlation_matrix']),
                    average_correlation=hist_data['average_correlation'],
                    max_correlation=hist_data['max_correlation'],
                    min_correlation=hist_data.get('min_correlation', 0.0),
                    correlation_dispersion=hist_data.get('correlation_dispersion', 0.0),
                    eigenvalues=np.array(hist_data.get('eigenvalues', [])),
                    condition_number=hist_data.get('condition_number', 1.0),
                    diversification_ratio=hist_data['diversification_ratio'],
                    concentration_index=hist_data.get('concentration_index', 0.0),
                    regime=CorrelationRegime(hist_data['regime']),
                    timestamp=datetime.fromisoformat(hist_data['timestamp'])
                )
                self.correlation_history.append(metrics)
            
            self.logger.info(f"Correlation data imported from {file_path}")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, f"Failed to import correlation data from {file_path}")
            return False

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def create_correlation_analyzer(config: Optional[Dict[str, Any]] = None) -> CorrelationAnalyzer:
    """
    Factory function to create a CorrelationAnalyzer instance.
    
    Args:
        config: Configuration parameters
        
    Returns:
        Configured CorrelationAnalyzer instance
    """
    return CorrelationAnalyzer(config)

def calculate_pairwise_correlation(returns1: pd.Series, returns2: pd.Series,
                                 method: str = 'pearson') -> float:
    """
    Calculate correlation between two return series.
    
    Args:
        returns1: First return series
        returns2: Second return series
        method: Correlation method ('pearson', 'spearman', 'kendall')
        
    Returns:
        Correlation coefficient
    """
    try:
        # Align series
        aligned_data = pd.DataFrame({'series1': returns1, 'series2': returns2}).dropna()
        
        if len(aligned_data) < 2:
            return 0.0
        
        return aligned_data['series1'].corr(aligned_data['series2'], method=method)
        
    except Exception:
        return 0.0

def detect_correlation_regime_simple(correlation_matrix: np.ndarray) -> CorrelationRegime:
    """
    Simple correlation regime detection utility.
    
    Args:
        correlation_matrix: Correlation matrix
        
    Returns:
        Detected correlation regime
    """
    try:
        # Calculate average off-diagonal correlation
        mask = ~np.eye(correlation_matrix.shape[0], dtype=bool)
        avg_correlation = np.mean(np.abs(correlation_matrix[mask]))
        
        if avg_correlation >= EXTREME_CORRELATION_THRESHOLD:
            return CorrelationRegime.CRISIS_CORRELATION
        elif avg_correlation >= HIGH_CORRELATION_THRESHOLD:
            return CorrelationRegime.HIGH_CORRELATION
        elif avg_correlation >= DIVERSIFICATION_THRESHOLD:
            return CorrelationRegime.NORMAL_CORRELATION
        else:
            return CorrelationRegime.LOW_CORRELATION
            
    except Exception:
        return CorrelationRegime.NORMAL_CORRELATION

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Global correlation analyzer instance
_global_correlation_analyzer: Optional[CorrelationAnalyzer] = None

def get_global_correlation_analyzer() -> Optional[CorrelationAnalyzer]:
    """Get global correlation analyzer instance"""
    return _global_correlation_analyzer

def set_global_correlation_analyzer(analyzer: CorrelationAnalyzer) -> None:
    """Set global correlation analyzer instance"""
    global _global_correlation_analyzer
    _global_correlation_analyzer = analyzer

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code
    print("=" * 80)
    print("SPYDER P03 - Correlation Analyzer Test")
    print("=" * 80)
    
    # Create analyzer
    analyzer = CorrelationAnalyzer()
    
    # Test data generation
    print("\n1. Generating Test Data...")
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    
    # Generate correlated strategy returns
    base_returns = np.random.normal(0.0005, 0.02, 252)
    
    strategy_returns = {
        'strategy_1': pd.Series(base_returns + np.random.normal(0, 0.01, 252), index=dates),
        'strategy_2': pd.Series(0.8 * base_returns + np.random.normal(0, 0.01, 252), index=dates),
        'strategy_3': pd.Series(0.3 * base_returns + np.random.normal(0, 0.015, 252), index=dates),
        'strategy_4': pd.Series(-0.2 * base_returns + np.random.normal(0, 0.012, 252), index=dates)
    }
    
    print(f"Generated returns for {len(strategy_returns)} strategies over {len(dates)} days")
    
    # Test correlation analysis
    print("\n2. Testing Correlation Analysis...")
    
    async def run_tests():
        # Basic correlation analysis
        metrics = await analyzer.analyze_portfolio_correlations(strategy_returns)
        print(f"Average correlation: {metrics.average_correlation:.3f}")
        print(f"Diversification ratio: {metrics.diversification_ratio:.3f}")
        print(f"Current regime: {metrics.regime.value}")
        
        # Rolling correlation analysis
        rolling_results = await analyzer.calculate_rolling_correlations(60)
        print(f"Rolling correlations calculated for {len(rolling_results)} pairs")
        
        # Correlation forecasting
        if rolling_results:
            first_pair = list(rolling_results.keys())[0]
            forecast = await analyzer.forecast_correlations(first_pair, horizon=10)
            if forecast:
                print(f"Forecast generated for {first_pair}: confidence={forecast.model_confidence:.3f}")
        
        # Cluster analysis
        cluster_result = await analyzer.perform_cluster_analysis()
        if cluster_result:
            print(f"Cluster analysis: {len(cluster_result.clusters)} clusters found")
            print(f"Silhouette score: {cluster_result.silhouette_score:.3f}")
        
        # Factor analysis
        factor_result = await analyzer.perform_factor_analysis(n_factors=2)
        if factor_result:
            print(f"Factor analysis: common factor risk={factor_result.common_factor_risk:.3f}")
        
        # Anomaly detection
        anomalies = await analyzer.detect_correlation_anomalies()
        print(f"Anomaly detection: {len(anomalies)} anomalies found")
        
        # Generate comprehensive report
        report = await analyzer.generate_correlation_report()
        print(f"Report generated with {len(report.get('recommendations', []))} recommendations")
    
    # Run async tests
    import asyncio
    asyncio.run(run_tests())
    
    # Test utility functions
    print("\n3. Testing Utility Functions...")
    
    # Test pairwise correlation
    corr = calculate_pairwise_correlation(
        strategy_returns['strategy_1'], 
        strategy_returns['strategy_2']
    )
    print(f"Pairwise correlation: {corr:.3f}")
    
    # Test simple regime detection
    test_matrix = np.array([[1.0, 0.8, 0.6], [0.8, 1.0, 0.7], [0.6, 0.7, 1.0]])
    regime = detect_correlation_regime_simple(test_matrix)
    print(f"Simple regime detection: {regime.value}")
    
    # Test data export/import
    print("\n4. Testing Data Export/Import...")
    export_success = analyzer.export_correlation_data("test_correlation_data.json", "json")
    print(f"Export successful: {export_success}")
    
    if export_success:
        # Clear data and reimport
        analyzer.correlation_history.clear()
        import_success = analyzer.import_correlation_data("test_correlation_data.json", "json")
        print(f"Import successful: {import_success}")
        print(f"Correlation history restored: {len(analyzer.correlation_history)} entries")
        
        # Clean up test file
        import os
        try:
            os.remove("test_correlation_data.json")
            print("Test file cleaned up")
        except:
            pass
    
    # Test summary functions
    print("\n5. Testing Summary Functions...")
    summary = analyzer.get_correlation_summary()
    print(f"Summary generated with {len(summary)} fields")
    
    if strategy_returns:
        profile = analyzer.get_strategy_correlation_profile('strategy_1')
        print(f"Strategy profile: avg_correlation={profile.get('average_correlation', 0):.3f}")
    
    print("\n✅ Correlation Analyzer test completed successfully")
    
    # Demonstrate integration examples
    print("\n" + "=" * 80)
    print("INTEGRATION EXAMPLES")
    print("=" * 80)
    
    print("\n1. Real-time Monitoring Setup...")
    print("# To start real-time monitoring:")
    print("# await analyzer.start_real_time_monitoring(update_frequency=300)")
    print("# This will continuously monitor correlations every 5 minutes")
    
    print("\n2. Integration with Portfolio Manager...")
    print("# Update strategy returns from portfolio:")
    print("# analyzer.update_strategy_returns('new_strategy', returns_series)")
    print("# Get active correlation alerts:")
    print(f"# Active alerts: {len(analyzer.get_active_alerts(24))}")
    
    print("\n3. Risk Management Integration...")
    print("# Check current correlation regime for risk decisions:")
    print(f"# Current regime: {analyzer.current_regime.value}")
    print("# Get correlation-based recommendations:")
    
    example_recommendations = [
        "Monitor correlation spikes during market stress",
        "Implement dynamic position sizing based on correlation regime", 
        "Use correlation forecasts for proactive risk management",
        "Set up automated alerts for correlation threshold breaches",
        "Integrate cluster analysis for strategy grouping"
    ]
    
    print("Risk management recommendations:")
    for rec in example_recommendations:
        print(f"  • {rec}")
    
    print("\n✅ All integration examples completed successfully")
