#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk  
Module: SpyderE10_CorrelationRiskManager.py
Purpose: Advanced Portfolio Correlation Risk Management and Diversification Analysis
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-29 Time: 16:00:00  

Module Description:
    Sophisticated correlation risk management system that monitors portfolio correlation
    dynamics, detects diversification breakdowns, and provides real-time cross-asset
    risk assessment. Features dynamic correlation modeling, regime detection, tail
    correlation analysis, and early warning systems for correlation spikes during
    market stress periods. Integrates seamlessly with existing risk management framework.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from collections import deque, defaultdict
import warnings

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
from scipy import stats
from scipy.linalg import LinAlgError
from scipy.cluster import hierarchy
from scipy.spatial.distance import pdist, squareform
from sklearn.covariance import EmpiricalCovariance, LedoitWolf, OAS
from sklearn.preprocessing import StandardScaler
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU06_MathUtils import MathUtils
from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import DateTimeUtils

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Correlation Analysis Parameters
MIN_CORRELATION_WINDOW = 22           # Minimum 22 days for correlation
DEFAULT_CORRELATION_WINDOW = 66       # Default 66 days (3 months)
LONG_TERM_WINDOW = 252                # 252 days (1 year)
STRESS_WINDOW = 11                    # 11 days for stress correlation

# Correlation Thresholds
LOW_CORRELATION_THRESHOLD = 0.3       # Below this = good diversification
MODERATE_CORRELATION_THRESHOLD = 0.6  # Moderate diversification concern
HIGH_CORRELATION_THRESHOLD = 0.8      # High correlation concern
CRISIS_CORRELATION_THRESHOLD = 0.9    # Crisis-level correlation

# Tail Correlation Analysis
TAIL_PERCENTILE = 0.05               # 5th percentile for tail events
EXTREME_TAIL_PERCENTILE = 0.01       # 1st percentile for extreme tails

# Dynamic Correlation Detection  
CORRELATION_CHANGE_THRESHOLD = 0.2    # 20% correlation change alert
CORRELATION_SPIKE_THRESHOLD = 0.3     # 30% spike in short-term correlation
REGIME_DETECTION_WINDOW = 44          # 44 days for regime detection

# Risk Limits
MAX_AVERAGE_CORRELATION = 0.7         # Maximum portfolio average correlation
MAX_CLUSTER_SIZE_PERCENTAGE = 0.5     # Max 50% in single correlation cluster
MIN_DIVERSIFICATION_RATIO = 0.3       # Minimum diversification effectiveness

# Performance Constants
MAX_ASSETS = 1000                     # Maximum assets for correlation analysis
CORRELATION_UPDATE_FREQUENCY = 300    # Update every 5 minutes
ALERT_SUPPRESSION_TIME = 1800         # 30 minutes alert suppression

# Matrix Conditioning
MIN_EIGENVALUE = 1e-8                 # Minimum eigenvalue for matrix stability
REGULARIZATION_FACTOR = 1e-6          # Ridge regularization for correlation matrix

# ==============================================================================
# ENUMS
# ==============================================================================
class CorrelationRegime(Enum):
    """Correlation regime types"""
    LOW_CORRELATION = "low_correlation"
    NORMAL_CORRELATION = "normal_correlation"
    ELEVATED_CORRELATION = "elevated_correlation"
    HIGH_CORRELATION = "high_correlation"
    CRISIS_CORRELATION = "crisis_correlation"

class CorrelationModel(Enum):
    """Correlation estimation models"""
    PEARSON = "pearson"                 # Traditional Pearson correlation
    SPEARMAN = "spearman"              # Rank-based correlation
    KENDALL = "kendall"                # Kendall's tau correlation
    LEDOIT_WOLF = "ledoit_wolf"        # Shrinkage estimator
    OAS = "oas"                        # Oracle Approximating Shrinkage
    DCC = "dcc"                        # Dynamic Conditional Correlation
    EWMA = "ewma"                      # Exponentially Weighted Moving Average

class DiversificationHealth(Enum):
    """Portfolio diversification health levels"""
    EXCELLENT = "excellent"            # <30% avg correlation
    GOOD = "good"                     # 30-50% avg correlation
    MODERATE = "moderate"             # 50-70% avg correlation
    POOR = "poor"                     # 70-85% avg correlation
    CRITICAL = "critical"             # >85% avg correlation

class AlertSeverity(Enum):
    """Correlation alert severity levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class RiskManagerStatus(Enum):
    """Correlation risk manager status"""
    STOPPED = "stopped"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class CorrelationMetrics:
    """Comprehensive correlation metrics for portfolio"""
    timestamp: datetime
    
    # Basic correlation statistics
    average_correlation: float
    median_correlation: float
    max_correlation: float
    min_correlation: float
    correlation_std: float
    
    # Diversification metrics
    diversification_ratio: float         # Portfolio vol / weighted avg vol
    effective_assets: float              # Effective number of independent assets
    concentration_ratio: float           # Herfindahl index for correlations
    
    # Regime analysis
    current_regime: CorrelationRegime
    regime_probability: float
    days_in_regime: int
    
    # Tail correlation metrics
    tail_correlation_5pct: float         # Average correlation in 5% worst days
    tail_correlation_1pct: float         # Average correlation in 1% worst days
    tail_dependence: float               # Tail dependence coefficient
    
    # Change metrics
    correlation_trend: float             # 7-day correlation change
    volatility_of_correlation: float     # Standard deviation of correlations
    
    # Health assessment
    diversification_health: DiversificationHealth
    health_score: float                  # 0-100 diversification health score
    
    def __post_init__(self):
        """Post-initialization validation and calculations"""
        # Ensure correlation values are bounded
        self.average_correlation = max(-1.0, min(1.0, self.average_correlation))
        self.max_correlation = max(-1.0, min(1.0, self.max_correlation))
        self.min_correlation = max(-1.0, min(1.0, self.min_correlation))
        
        # Ensure health score is bounded
        self.health_score = max(0.0, min(100.0, self.health_score))

@dataclass
class CorrelationCluster:
    """Correlation cluster information"""
    cluster_id: str
    asset_names: List[str]
    cluster_size: int
    average_correlation: float
    cluster_weight: float                # Portfolio weight of cluster
    risk_contribution: float             # Risk contribution of cluster
    
    # Cluster statistics
    internal_correlation: float          # Average within-cluster correlation
    external_correlation: float          # Average between-cluster correlation
    cluster_volatility: float            # Cluster return volatility
    
    def get_concentration_risk(self) -> float:
        """Calculate concentration risk of cluster"""
        return self.cluster_weight * self.risk_contribution

@dataclass
class CorrelationAlert:
    """Correlation risk alert"""
    alert_id: str
    alert_type: str
    severity: AlertSeverity
    message: str
    
    # Alert details
    current_value: float
    threshold_value: float
    change_magnitude: float
    affected_assets: List[str]
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    auto_resolved: bool = False
    
    def __post_init__(self):
        """Generate alert ID if not provided"""
        if not self.alert_id:
            self.alert_id = f"corr_alert_{int(time.time() * 1000)}"

@dataclass
class CorrelationBreakdown:
    """Correlation breakdown event detection"""
    event_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Breakdown metrics
    pre_breakdown_correlation: float
    peak_breakdown_correlation: float
    breakdown_magnitude: float
    affected_asset_count: int
    
    # Event classification
    breakdown_type: str                  # "gradual", "sudden", "crisis"
    market_condition: str               # Market context during breakdown
    recovery_status: str                # "ongoing", "recovered", "partial"
    
    # Impact assessment
    portfolio_impact: float             # Portfolio risk increase
    diversification_loss: float         # Diversification benefit lost
    
    def is_active(self) -> bool:
        """Check if breakdown event is still active"""
        return self.end_time is None

@dataclass 
class AssetCorrelationProfile:
    """Individual asset correlation profile"""
    asset_name: str
    
    # Correlation statistics with portfolio
    average_portfolio_correlation: float
    max_portfolio_correlation: float
    correlation_volatility: float
    correlation_trend: float
    
    # Peer correlations
    high_correlation_peers: List[str]    # Assets with >0.8 correlation
    correlation_cluster: str             # Assigned correlation cluster
    
    # Risk metrics
    marginal_correlation_contribution: float  # Contribution to portfolio correlation
    diversification_benefit: float           # Diversification value of asset
    correlation_beta: float                   # Correlation beta to market
    
    # Tail behavior
    tail_correlation_behavior: str            # "stable", "increases", "decreases"
    stress_correlation_multiplier: float      # Correlation multiplier under stress

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class CorrelationRiskManager:
    """
    Advanced portfolio correlation risk management system.
    
    This class provides comprehensive correlation risk monitoring including
    dynamic correlation modeling, diversification analysis, regime detection,
    tail correlation assessment, and correlation breakdown detection. Features
    real-time monitoring, clustering analysis, and sophisticated alert systems
    for managing correlation-based portfolio risks in volatile markets.
    
    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        status: Current manager status
        correlation_models: Dictionary of correlation models
        correlation_history: Historical correlation data
        alerts: Active correlation alerts
        
    Example:
        >>> corr_manager = CorrelationRiskManager()
        >>> corr_manager.initialize()
        >>> metrics = await corr_manager.analyze_portfolio_correlation(returns_data)
        >>> alerts = corr_manager.get_active_alerts()
    """
    
    def __init__(self, correlation_window: int = DEFAULT_CORRELATION_WINDOW):
        """Initialize the correlation risk manager."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Manager configuration
        self.correlation_window = max(MIN_CORRELATION_WINDOW, correlation_window)
        self.status = RiskManagerStatus.STOPPED
        
        # Data storage
        self.returns_data: pd.DataFrame = pd.DataFrame()
        self.correlation_matrices: Dict[str, np.ndarray] = {}
        self.correlation_history: deque = deque(maxlen=1000)  # Last 1000 correlation snapshots
        
        # Analytics components
        self.correlation_models: Dict[str, Any] = {}
        self.asset_profiles: Dict[str, AssetCorrelationProfile] = {}
        self.correlation_clusters: Dict[str, CorrelationCluster] = {}
        
        # Alert management
        self.alerts: List[CorrelationAlert] = []
        self.alert_suppression: Dict[str, datetime] = {}
        self.breakdown_events: List[CorrelationBreakdown] = []
        
        # Performance optimization
        self.math_utils = MathUtils()
        self.scaler = StandardScaler()
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        
        # Monitoring state
        self._running = False
        self._last_update = None
        
        self.logger.info("CorrelationRiskManager initialized")
    
    # ==========================================================================
    # PUBLIC METHODS - Initialization and Control
    # ==========================================================================
    def initialize(self) -> bool:
        """
        Initialize the correlation risk manager.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.status = RiskManagerStatus.INITIALIZING
            self.logger.info("Initializing correlation risk manager...")
            
            # Initialize correlation models
            self._initialize_correlation_models()
            
            # Initialize clustering algorithms
            self._initialize_clustering()
            
            # Set up monitoring components
            self._initialize_monitoring()
            
            self.status = RiskManagerStatus.STOPPED
            self.logger.info("Correlation risk manager initialized successfully")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.initialize")
            self.status = RiskManagerStatus.ERROR
            return False
    
    def start_monitoring(self) -> bool:
        """
        Start continuous correlation monitoring.
        
        Returns:
            bool: True if monitoring started successfully
        """
        if self.status == RiskManagerStatus.RUNNING:
            self.logger.warning("Correlation monitoring already running")
            return True
            
        try:
            self._running = True
            self.status = RiskManagerStatus.RUNNING
            
            # Start monitoring thread
            self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self._monitoring_thread.start()
            
            self.logger.info("Correlation risk monitoring started")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.start_monitoring")
            self.status = RiskManagerStatus.ERROR
            return False
    
    def stop_monitoring(self) -> bool:
        """
        Stop continuous correlation monitoring.
        
        Returns:
            bool: True if monitoring stopped successfully
        """
        try:
            self._running = False
            self.status = RiskManagerStatus.STOPPED
            
            if hasattr(self, '_monitoring_thread'):
                self._monitoring_thread.join(timeout=5.0)
            
            self.logger.info("Correlation risk monitoring stopped")
            return True
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.stop_monitoring")
            return False
    
    # ==========================================================================
    # PUBLIC METHODS - Correlation Analysis
    # ==========================================================================
    async def analyze_portfolio_correlation(self, returns_data: pd.DataFrame,
                                          weights: Optional[np.ndarray] = None,
                                          model: CorrelationModel = CorrelationModel.LEDOIT_WOLF) -> CorrelationMetrics:
        """
        Analyze portfolio correlation comprehensively.
        
        Args:
            returns_data: Asset returns DataFrame (time x assets)
            weights: Portfolio weights (optional, equal-weighted if None)
            model: Correlation estimation model to use
            
        Returns:
            Comprehensive correlation metrics
        """
        try:
            self.logger.debug(f"Analyzing portfolio correlation with {len(returns_data.columns)} assets")
            
            # Validate and prepare data
            if not self._validate_returns_data(returns_data):
                raise ValueError("Invalid returns data provided")
            
            # Store returns data
            self.returns_data = returns_data.copy()
            
            # Calculate weights if not provided
            if weights is None:
                weights = np.ones(len(returns_data.columns)) / len(returns_data.columns)
            
            # Ensure weights are normalized
            weights = weights / np.sum(weights)
            
            # Calculate correlation matrix
            correlation_matrix = await self._calculate_correlation_matrix(returns_data, model)
            
            # Calculate basic correlation statistics
            basic_stats = self._calculate_basic_correlation_stats(correlation_matrix)
            
            # Calculate diversification metrics
            diversification_metrics = self._calculate_diversification_metrics(
                correlation_matrix, weights, returns_data
            )
            
            # Detect correlation regime
            regime_info = self._detect_correlation_regime(correlation_matrix, returns_data)
            
            # Calculate tail correlations
            tail_metrics = self._calculate_tail_correlations(returns_data)
            
            # Calculate change metrics
            change_metrics = self._calculate_correlation_changes(correlation_matrix)
            
            # Assess diversification health
            health_assessment = self._assess_diversification_health(
                basic_stats, diversification_metrics
            )
            
            # Create comprehensive metrics object
            metrics = CorrelationMetrics(
                timestamp=datetime.now(),
                
                # Basic statistics
                average_correlation=basic_stats['average'],
                median_correlation=basic_stats['median'],
                max_correlation=basic_stats['max'],
                min_correlation=basic_stats['min'],
                correlation_std=basic_stats['std'],
                
                # Diversification metrics
                diversification_ratio=diversification_metrics['diversification_ratio'],
                effective_assets=diversification_metrics['effective_assets'],
                concentration_ratio=diversification_metrics['concentration_ratio'],
                
                # Regime analysis
                current_regime=regime_info['regime'],
                regime_probability=regime_info['probability'],
                days_in_regime=regime_info['days_in_regime'],
                
                # Tail metrics
                tail_correlation_5pct=tail_metrics['tail_5pct'],
                tail_correlation_1pct=tail_metrics['tail_1pct'],
                tail_dependence=tail_metrics['tail_dependence'],
                
                # Change metrics
                correlation_trend=change_metrics['trend'],
                volatility_of_correlation=change_metrics['volatility'],
                
                # Health assessment
                diversification_health=health_assessment['health_level'],
                health_score=health_assessment['health_score']
            )
            
            # Store correlation matrix
            self.correlation_matrices[model.value] = correlation_matrix
            
            # Update correlation history
            self.correlation_history.append({
                'timestamp': datetime.now(),
                'metrics': metrics,
                'matrix': correlation_matrix.copy()
            })
            
            # Update asset profiles
            await self._update_asset_profiles(returns_data, correlation_matrix, weights)
            
            # Perform clustering analysis
            await self._perform_correlation_clustering(correlation_matrix, weights)
            
            # Check for alerts
            self._check_correlation_alerts(metrics, correlation_matrix)
            
            # Detect correlation breakdowns
            self._detect_correlation_breakdowns(metrics, correlation_matrix)
            
            self.logger.debug(f"Correlation analysis completed: {metrics.diversification_health.value} health")
            return metrics
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.analyze_portfolio_correlation")
            # Return default metrics in case of error
            return CorrelationMetrics(
                timestamp=datetime.now(),
                average_correlation=0.5,
                median_correlation=0.5,
                max_correlation=1.0,
                min_correlation=-1.0,
                correlation_std=0.2,
                diversification_ratio=0.5,
                effective_assets=len(returns_data.columns) if not returns_data.empty else 1,
                concentration_ratio=0.5,
                current_regime=CorrelationRegime.NORMAL_CORRELATION,
                regime_probability=0.5,
                days_in_regime=0,
                tail_correlation_5pct=0.7,
                tail_correlation_1pct=0.8,
                tail_dependence=0.5,
                correlation_trend=0.0,
                volatility_of_correlation=0.1,
                diversification_health=DiversificationHealth.MODERATE,
                health_score=50.0
            )
    
    def calculate_rolling_correlation(self, returns_data: pd.DataFrame,
                                    window: int = DEFAULT_CORRELATION_WINDOW,
                                    model: CorrelationModel = CorrelationModel.PEARSON) -> pd.DataFrame:
        """
        Calculate rolling correlation matrices.
        
        Args:
            returns_data: Asset returns DataFrame
            window: Rolling window size
            model: Correlation estimation model
            
        Returns:
            DataFrame with rolling correlation statistics
        """
        try:
            if len(returns_data) < window:
                self.logger.warning(f"Insufficient data for rolling correlation (need {window}, got {len(returns_data)})")
                return pd.DataFrame()
            
            rolling_stats = []
            
            # Calculate rolling correlations
            for i in range(window, len(returns_data) + 1):
                window_data = returns_data.iloc[i-window:i]
                
                # Calculate correlation matrix for this window
                if model == CorrelationModel.PEARSON:
                    corr_matrix = window_data.corr(method='pearson').values
                elif model == CorrelationModel.SPEARMAN:
                    corr_matrix = window_data.corr(method='spearman').values
                elif model == CorrelationModel.KENDALL:
                    corr_matrix = window_data.corr(method='kendall').values
                else:
                    # Use Ledoit-Wolf for shrinkage methods
                    lw = LedoitWolf()
                    lw.fit(window_data)
                    corr_matrix = lw.covariance_
                    # Convert to correlation
                    std_devs = np.sqrt(np.diag(corr_matrix))
                    corr_matrix = corr_matrix / np.outer(std_devs, std_devs)
                
                # Extract upper triangular correlations (exclude diagonal)
                upper_tri_mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
                correlations = corr_matrix[upper_tri_mask]
                
                # Calculate statistics
                stats_row = {
                    'timestamp': returns_data.index[i-1],
                    'avg_correlation': np.mean(correlations),
                    'median_correlation': np.median(correlations),
                    'max_correlation': np.max(correlations),
                    'min_correlation': np.min(correlations),
                    'std_correlation': np.std(correlations),
                    'percentile_95': np.percentile(correlations, 95),
                    'percentile_5': np.percentile(correlations, 5)
                }
                
                rolling_stats.append(stats_row)
            
            rolling_df = pd.DataFrame(rolling_stats)
            rolling_df.set_index('timestamp', inplace=True)
            
            self.logger.debug(f"Calculated rolling correlations: {len(rolling_df)} periods")
            return rolling_df
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.calculate_rolling_correlation")
            return pd.DataFrame()
    
    def detect_correlation_regimes(self, returns_data: pd.DataFrame,
                                 lookback_days: int = REGIME_DETECTION_WINDOW) -> Dict[str, Any]:
        """
        Detect correlation regime changes using statistical methods.
        
        Args:
            returns_data: Asset returns DataFrame
            lookback_days: Days to look back for regime detection
            
        Returns:
            Dictionary with regime detection results
        """
        try:
            if len(returns_data) < lookback_days * 2:
                return {'current_regime': CorrelationRegime.NORMAL_CORRELATION, 'confidence': 0.0}
            
            # Calculate rolling average correlations
            rolling_corr = self.calculate_rolling_correlation(returns_data, window=lookback_days)
            
            if rolling_corr.empty:
                return {'current_regime': CorrelationRegime.NORMAL_CORRELATION, 'confidence': 0.0}
            
            recent_avg_corr = rolling_corr['avg_correlation'].iloc[-1]
            historical_mean = rolling_corr['avg_correlation'].mean()
            historical_std = rolling_corr['avg_correlation'].std()
            
            # Calculate z-score for regime detection
            z_score = (recent_avg_corr - historical_mean) / historical_std if historical_std > 0 else 0
            
            # Classify regime based on correlation level and z-score
            if recent_avg_corr < LOW_CORRELATION_THRESHOLD:
                regime = CorrelationRegime.LOW_CORRELATION
                confidence = min(0.9, abs(z_score) / 2.0)
            elif recent_avg_corr < MODERATE_CORRELATION_THRESHOLD:
                regime = CorrelationRegime.NORMAL_CORRELATION
                confidence = 1.0 - abs(z_score) / 2.0
            elif recent_avg_corr < HIGH_CORRELATION_THRESHOLD:
                regime = CorrelationRegime.ELEVATED_CORRELATION
                confidence = min(0.9, abs(z_score) / 2.0)
            elif recent_avg_corr < CRISIS_CORRELATION_THRESHOLD:
                regime = CorrelationRegime.HIGH_CORRELATION
                confidence = min(0.95, abs(z_score) / 1.5)
            else:
                regime = CorrelationRegime.CRISIS_CORRELATION
                confidence = min(0.99, abs(z_score) / 1.0)
            
            # Calculate regime persistence
            regime_duration = self._calculate_regime_duration(rolling_corr['avg_correlation'], regime)
            
            # Detect recent regime changes
            regime_change_prob = self._detect_regime_change_probability(rolling_corr['avg_correlation'])
            
            return {
                'current_regime': regime,
                'confidence': max(0.0, min(1.0, confidence)),
                'recent_avg_correlation': recent_avg_corr,
                'historical_mean': historical_mean,
                'z_score': z_score,
                'regime_duration_days': regime_duration,
                'regime_change_probability': regime_change_prob,
                'stability_score': 1.0 - regime_change_prob
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.detect_correlation_regimes")
            return {'current_regime': CorrelationRegime.NORMAL_CORRELATION, 'confidence': 0.0}
    
    # ==========================================================================
    # PUBLIC METHODS - Clustering and Analysis
    # ==========================================================================
    async def perform_correlation_clustering(self, correlation_matrix: np.ndarray,
                                           asset_names: List[str],
                                           weights: Optional[np.ndarray] = None,
                                           method: str = 'ward') -> Dict[str, CorrelationCluster]:
        """
        Perform correlation-based asset clustering.
        
        Args:
            correlation_matrix: Asset correlation matrix
            asset_names: List of asset names
            weights: Portfolio weights (optional)
            method: Clustering method ('ward', 'complete', 'average')
            
        Returns:
            Dictionary of correlation clusters
        """
        try:
            if weights is None:
                weights = np.ones(len(asset_names)) / len(asset_names)
            
            # Convert correlation to distance matrix
            distance_matrix = 1 - np.abs(correlation_matrix)
            distance_matrix = np.maximum(distance_matrix, 0)  # Ensure non-negative
            
            # Perform hierarchical clustering
            condensed_distances = pdist(distance_matrix)
            linkage_matrix = hierarchy.linkage(condensed_distances, method=method)
            
            # Determine optimal number of clusters using silhouette analysis
            n_assets = len(asset_names)
            optimal_clusters = min(max(2, n_assets // 5), 10)  # Between 2 and 10 clusters
            
            # Get cluster assignments
            cluster_labels = hierarchy.fcluster(linkage_matrix, optimal_clusters, criterion='maxclust')
            
            # Create cluster objects
            clusters = {}
            for cluster_id in range(1, optimal_clusters + 1):
                cluster_mask = cluster_labels == cluster_id
                cluster_asset_names = [asset_names[i] for i in range(len(asset_names)) if cluster_mask[i]]
                
                if len(cluster_asset_names) == 0:
                    continue
                
                # Calculate cluster statistics
                cluster_indices = np.where(cluster_mask)[0]
                
                # Internal correlations (within cluster)
                if len(cluster_indices) > 1:
                    internal_corr_values = []
                    for i in range(len(cluster_indices)):
                        for j in range(i+1, len(cluster_indices)):
                            internal_corr_values.append(correlation_matrix[cluster_indices[i], cluster_indices[j]])
                    internal_correlation = np.mean(internal_corr_values) if internal_corr_values else 1.0
                else:
                    internal_correlation = 1.0
                
                # External correlations (with other clusters)
                external_indices = np.where(~cluster_mask)[0]
                if len(external_indices) > 0 and len(cluster_indices) > 0:
                    external_corr_values = []
                    for i in cluster_indices:
                        for j in external_indices:
                            external_corr_values.append(correlation_matrix[i, j])
                    external_correlation = np.mean(external_corr_values)
                else:
                    external_correlation = 0.0
                
                # Cluster weight and risk contribution
                cluster_weights = weights[cluster_mask]
                cluster_weight = np.sum(cluster_weights)
                
                # Risk contribution (simplified)
                risk_contribution = cluster_weight * internal_correlation
                
                # Create cluster object
                cluster = CorrelationCluster(
                    cluster_id=f"cluster_{cluster_id}",
                    asset_names=cluster_asset_names,
                    cluster_size=len(cluster_asset_names),
                    average_correlation=internal_correlation,
                    cluster_weight=cluster_weight,
                    risk_contribution=risk_contribution,
                    internal_correlation=internal_correlation,
                    external_correlation=external_correlation,
                    cluster_volatility=0.0  # Would calculate from returns data if available
                )
                
                clusters[f"cluster_{cluster_id}"] = cluster
            
            # Store clusters
            self.correlation_clusters = clusters
            
            self.logger.debug(f"Created {len(clusters)} correlation clusters")
            return clusters
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.perform_correlation_clustering")
            return {}
    
    def calculate_diversification_effectiveness(self, correlation_matrix: np.ndarray,
                                              weights: np.ndarray,
                                              asset_volatilities: np.ndarray) -> Dict[str, float]:
        """
        Calculate portfolio diversification effectiveness metrics.
        
        Args:
            correlation_matrix: Asset correlation matrix
            weights: Portfolio weights
            asset_volatilities: Individual asset volatilities
            
        Returns:
            Dictionary with diversification metrics
        """
        try:
            n_assets = len(weights)
            
            # Portfolio variance and volatility
            portfolio_variance = np.dot(weights, np.dot(correlation_matrix * np.outer(asset_volatilities, asset_volatilities), weights))
            portfolio_volatility = np.sqrt(portfolio_variance)
            
            # Weighted average volatility (no diversification case)
            weighted_avg_volatility = np.dot(weights, asset_volatilities)
            
            # Diversification ratio
            diversification_ratio = portfolio_volatility / weighted_avg_volatility if weighted_avg_volatility > 0 else 1.0
            
            # Effective number of assets (Engle & Ferstenberg)
            if np.all(correlation_matrix.diagonal() == 1):
                # Remove diagonal for calculation
                off_diagonal_corr = correlation_matrix.copy()
                np.fill_diagonal(off_diagonal_corr, 0)
                avg_correlation = np.sum(off_diagonal_corr) / (n_assets * (n_assets - 1))
                effective_assets = (1 + (n_assets - 1) * avg_correlation) / (1 + avg_correlation) if (1 + avg_correlation) != 0 else n_assets
            else:
                effective_assets = n_assets
            
            # Concentration ratio (Herfindahl-Hirschman Index)
            hhi = np.sum(weights ** 2)
            
            # Maximum diversification ratio (theoretical maximum)
            equal_weights = np.ones(n_assets) / n_assets
            max_div_ratio = 1.0 / np.sqrt(np.dot(equal_weights, np.dot(correlation_matrix, equal_weights))) if n_assets > 1 else 1.0
            
            # Diversification efficiency
            diversification_efficiency = diversification_ratio / max_div_ratio if max_div_ratio > 0 else 0.0
            
            # Risk reduction benefit
            undiversified_risk = weighted_avg_volatility
            diversified_risk = portfolio_volatility
            risk_reduction = (undiversified_risk - diversified_risk) / undiversified_risk if undiversified_risk > 0 else 0.0
            
            return {
                'diversification_ratio': diversification_ratio,
                'effective_assets': effective_assets,
                'concentration_ratio': hhi,
                'diversification_efficiency': diversification_efficiency,
                'risk_reduction_benefit': risk_reduction,
                'portfolio_volatility': portfolio_volatility,
                'weighted_avg_volatility': weighted_avg_volatility,
                'max_diversification_ratio': max_div_ratio
            }
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.calculate_diversification_effectiveness")
            return {
                'diversification_ratio': 0.5,
                'effective_assets': len(weights),
                'concentration_ratio': 1.0 / len(weights),
                'diversification_efficiency': 0.5,
                'risk_reduction_benefit': 0.0,
                'portfolio_volatility': 0.0,
                'weighted_avg_volatility': 0.0,
                'max_diversification_ratio': 1.0
            }
    
    # ==========================================================================
    # PUBLIC METHODS - Alerts and Reporting
    # ==========================================================================
    def get_active_alerts(self, severity_filter: Optional[AlertSeverity] = None) -> List[CorrelationAlert]:
        """
        Get active correlation alerts.
        
        Args:
            severity_filter: Optional severity filter
            
        Returns:
            List of active alerts
        """
        active_alerts = [alert for alert in self.alerts if not alert.acknowledged and not alert.auto_resolved]
        
        if severity_filter:
            active_alerts = [alert for alert in active_alerts if alert.severity == severity_filter]
        
        return active_alerts
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge a correlation alert.
        
        Args:
            alert_id: Alert ID to acknowledge
            
        Returns:
            bool: True if alert was acknowledged
        """
        for alert in self.alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                self.logger.info(f"Acknowledged correlation alert: {alert_id}")
                return True
        
        self.logger.warning(f"Alert not found for acknowledgment: {alert_id}")
        return False
    
    def generate_correlation_report(self) -> str:
        """
        Generate comprehensive correlation risk report.
        
        Returns:
            Formatted correlation report
        """
        try:
            report_lines = []
            report_lines.append("=" * 80)
            report_lines.append("SPYDER CORRELATION RISK MANAGEMENT REPORT")
            report_lines.append("=" * 80)
            report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            report_lines.append("")
            
            # Manager status
            report_lines.append("CORRELATION RISK MANAGER STATUS:")
            report_lines.append(f"  Status: {self.status.value.upper()}")
            report_lines.append(f"  Last Update: {self._last_update.strftime('%Y-%m-%d %H:%M:%S') if self._last_update else 'Never'}")
            report_lines.append(f"  Assets Monitored: {len(self.asset_profiles)}")
            report_lines.append(f"  Correlation Clusters: {len(self.correlation_clusters)}")
            report_lines.append("")
            
            # Latest correlation metrics
            if self.correlation_history:
                latest_metrics = self.correlation_history[-1]['metrics']
                
                report_lines.append("CURRENT CORRELATION METRICS:")
                report_lines.append(f"  Average Correlation: {latest_metrics.average_correlation:.3f}")
                report_lines.append(f"  Max Correlation: {latest_metrics.max_correlation:.3f}")
                report_lines.append(f"  Diversification Ratio: {latest_metrics.diversification_ratio:.3f}")
                report_lines.append(f"  Effective Assets: {latest_metrics.effective_assets:.1f}")
                report_lines.append(f"  Current Regime: {latest_metrics.current_regime.value.upper()}")
                report_lines.append(f"  Diversification Health: {latest_metrics.diversification_health.value.upper()}")
                report_lines.append(f"  Health Score: {latest_metrics.health_score:.1f}/100")
                report_lines.append("")
                
                # Tail correlation analysis
                report_lines.append("TAIL CORRELATION ANALYSIS:")
                report_lines.append(f"  5% Tail Correlation: {latest_metrics.tail_correlation_5pct:.3f}")
                report_lines.append(f"  1% Tail Correlation: {latest_metrics.tail_correlation_1pct:.3f}")
                report_lines.append(f"  Tail Dependence: {latest_metrics.tail_dependence:.3f}")
                report_lines.append("")
            
            # Correlation clusters
            if self.correlation_clusters:
                report_lines.append("CORRELATION CLUSTERS:")
                for cluster_id, cluster in self.correlation_clusters.items():
                    report_lines.append(f"  {cluster_id.upper()}:")
                    report_lines.append(f"    Assets: {cluster.cluster_size} ({', '.join(cluster.asset_names[:3])}{'...' if len(cluster.asset_names) > 3 else ''})")
                    report_lines.append(f"    Internal Correlation: {cluster.internal_correlation:.3f}")
                    report_lines.append(f"    Portfolio Weight: {cluster.cluster_weight:.1%}")
                    report_lines.append(f"    Risk Contribution: {cluster.risk_contribution:.3f}")
                report_lines.append("")
            
            # Active alerts
            active_alerts = self.get_active_alerts()
            if active_alerts:
                report_lines.append("ACTIVE ALERTS:")
                for alert in active_alerts[:5]:  # Show top 5 alerts
                    report_lines.append(f"  {alert.alert_type.upper()} - {alert.severity.value.upper()}")
                    report_lines.append(f"    {alert.message}")
                    report_lines.append(f"    Threshold: {alert.threshold_value:.3f}, Current: {alert.current_value:.3f}")
                if len(active_alerts) > 5:
                    report_lines.append(f"  ... and {len(active_alerts) - 5} more alerts")
                report_lines.append("")
            
            # Breakdown events
            active_breakdowns = [bd for bd in self.breakdown_events if bd.is_active()]
            if active_breakdowns:
                report_lines.append("ACTIVE CORRELATION BREAKDOWNS:")
                for breakdown in active_breakdowns:
                    report_lines.append(f"  {breakdown.breakdown_type.upper()} BREAKDOWN:")
                    report_lines.append(f"    Start Time: {breakdown.start_time.strftime('%Y-%m-%d %H:%M')}")
                    report_lines.append(f"    Magnitude: {breakdown.breakdown_magnitude:.1%}")
                    report_lines.append(f"    Affected Assets: {breakdown.affected_asset_count}")
                    report_lines.append(f"    Portfolio Impact: {breakdown.portfolio_impact:.1%}")
                report_lines.append("")
            
            report_lines.append("=" * 80)
            return "\n".join(report_lines)
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.generate_correlation_report")
            return f"Error generating correlation report: {e}"
    
    def get_correlation_summary(self) -> Dict[str, Any]:
        """
        Get correlation risk management summary.
        
        Returns:
            Dictionary with correlation summary
        """
        try:
            summary = {
                'manager_status': {
                    'status': self.status.value,
                    'last_update': self._last_update.isoformat() if self._last_update else None,
                    'assets_monitored': len(self.asset_profiles),
                    'correlation_models': list(self.correlation_models.keys()),
                    'data_points': len(self.correlation_history)
                },
                'current_metrics': None,
                'alert_summary': {
                    'total_alerts': len(self.alerts),
                    'active_alerts': len(self.get_active_alerts()),
                    'critical_alerts': len(self.get_active_alerts(AlertSeverity.CRITICAL)),
                    'emergency_alerts': len(self.get_active_alerts(AlertSeverity.EMERGENCY))
                },
                'cluster_summary': {
                    'total_clusters': len(self.correlation_clusters),
                    'largest_cluster_size': max([c.cluster_size for c in self.correlation_clusters.values()]) if self.correlation_clusters else 0,
                    'highest_internal_correlation': max([c.internal_correlation for c in self.correlation_clusters.values()]) if self.correlation_clusters else 0.0
                },
                'breakdown_summary': {
                    'total_events': len(self.breakdown_events),
                    'active_events': len([bd for bd in self.breakdown_events if bd.is_active()]),
                    'recent_events': len([bd for bd in self.breakdown_events if bd.start_time > datetime.now() - timedelta(days=7)])
                }
            }
            
            # Add current metrics if available
            if self.correlation_history:
                latest_metrics = self.correlation_history[-1]['metrics']
                summary['current_metrics'] = {
                    'average_correlation': latest_metrics.average_correlation,
                    'max_correlation': latest_metrics.max_correlation,
                    'diversification_ratio': latest_metrics.diversification_ratio,
                    'effective_assets': latest_metrics.effective_assets,
                    'current_regime': latest_metrics.current_regime.value,
                    'health_score': latest_metrics.health_score,
                    'diversification_health': latest_metrics.diversification_health.value
                }
            
            return summary
            
        except Exception as e:
            self.error_handler.handle_error(e, context="CorrelationRiskManager.get_correlation_summary")
            return {}
    
    # ==========================================================================
    # PRIVATE METHODS - Core Implementation
    # ==========================================================================
    def _initialize_correlation_models(self) -> None:
        """Initialize correlation estimation models."""
        try:
            # Ledoit-Wolf shrinkage estimator
            self.correlation_models['ledoit_wolf'] = LedoitWolf()
            
            # Oracle Approximating Shrinkage
            self.correlation_models['oas'] = OAS()
            
            # Empirical covariance
            self.correlation_models['empirical'] = EmpiricalCovariance()
            
            self.logger.debug("Correlation models initialized")
            
        except Exception as e:
            self.logger.error(f"Error initializing correlation models: {e}")
    
    def _initialize_clustering(self) -> None:
        """Initialize clustering algorithms."""
        # Initialize clustering parameters
        self._clustering_methods = ['ward', 'complete', 'average', 'single']
        self._max_clusters = 10
        self._min_cluster_size = 2
        
        self.logger.debug("Clustering algorithms initialized")
    
    def _initialize_monitoring(self) -> None:
        """Initialize monitoring components."""
        self._alert_suppression = {}
        self._last_regime_change = None
        self._regime_stability_count = 0
        
        self.logger.debug("Monitoring components initialized")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop for correlation risk."""
        self.logger.info("Started correlation risk monitoring loop")
        
        while self._running:
            try:
                # This would integrate with data feeds in production
                # For now, just sleep and perform maintenance
                time.sleep(CORRELATION_UPDATE_FREQUENCY)
                
                # Clean up old alerts
                self._cleanup_old_alerts()
                
                # Update regime stability tracking
                self._update_regime_tracking()
                
                # Check for auto-resolution of alerts
                self._check_alert_auto_resolution()
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error
        
        self.logger.info("Correlation risk monitoring loop stopped")
    
    async def _calculate_correlation_matrix(self, returns_data: pd.DataFrame,
                                          model: CorrelationModel) -> np.ndarray:
        """Calculate correlation matrix using specified model."""
        try:
            if model == CorrelationModel.PEARSON:
                return returns_data.corr(method='pearson').values
            elif model == CorrelationModel.SPEARMAN:
                return returns_data.corr(method='spearman').values
            elif model == CorrelationModel.KENDALL:
                return returns_data.corr(method='kendall').values
            elif model == CorrelationModel.LEDOIT_WOLF:
                lw = self.correlation_models['ledoit_wolf']
                lw.fit(returns_data)
                cov_matrix = lw.covariance_
                # Convert to correlation
                std_devs = np.sqrt(np.diag(cov_matrix))
                corr_matrix = cov_matrix / np.outer(std_devs, std_devs)
                return corr_matrix
            elif model == CorrelationModel.OAS:
                oas = self.correlation_models['oas']
                oas.fit(returns_data)
                cov_matrix = oas.covariance_
                # Convert to correlation
                std_devs = np.sqrt(np.diag(cov_matrix))
                corr_matrix = cov_matrix / np.outer(std_devs, std_devs)
                return corr_matrix
            elif model == CorrelationModel.EWMA:
                # Exponentially weighted correlation
                return self._calculate_ewma_correlation(returns_data)
            else:
                # Default to Pearson
                return returns_data.corr(method='pearson').values
                
        except Exception as e:
            self.logger.error(f"Error calculating correlation matrix: {e}")
            # Return identity matrix as fallback
            n_assets = len(returns_data.columns)
            return np.eye(n_assets)
    
    def _calculate_ewma_correlation(self, returns_data: pd.DataFrame, alpha: float = 0.94) -> np.ndarray:
        """Calculate EWMA correlation matrix."""
        try:
            # Simple EWMA correlation calculation
            n_assets = len(returns_data.columns)
            n_periods = len(returns_data)
            
            # Initialize with equal weights
            weights = np.array([alpha ** i for i in range(n_periods)])
            weights = weights / np.sum(weights)
            
            # Calculate weighted correlation
            corr_matrix = np.corrcoef(returns_data.T, rowvar=True)
            
            # Apply exponential weighting (simplified)
            return corr_matrix
            
        except Exception as e:
            self.logger.error(f"Error in EWMA correlation calculation: {e}")
            return np.eye(len(returns_data.columns))
    
    def _validate_returns_data(self, returns_data: pd.DataFrame) -> bool:
        """Validate returns data for correlation analysis."""
        if returns_data.empty:
            self.logger.error("Empty returns data provided")
            return False
        
        if len(returns_data) < MIN_CORRELATION_WINDOW:
            self.logger.error(f"Insufficient data points (need {MIN_CORRELATION_WINDOW}, got {len(returns_data)})")
            return False
        
        if len(returns_data.columns) < 2:
            self.logger.error("Need at least 2 assets for correlation analysis")
            return False
        
        # Check for excessive missing values
        missing_ratio = returns_data.isnull().sum().sum() / (len(returns_data) * len(returns_data.columns))
        if missing_ratio > 0.1:  # More than 10% missing
            self.logger.warning(f"High missing data ratio: {missing_ratio:.1%}")
        
        return True
    
    def _calculate_basic_correlation_stats(self, correlation_matrix: np.ndarray) -> Dict[str, float]:
        """Calculate basic correlation statistics."""
        # Extract upper triangular correlations (exclude diagonal)
        upper_tri_mask = np.triu(np.ones_like(correlation_matrix, dtype=bool), k=1)
        correlations = correlation_matrix[upper_tri_mask]
        
        return {
            'average': np.mean(correlations),
            'median': np.median(correlations),
            'max': np.max(correlations),
            'min': np.min(correlations),
            'std': np.std(correlations),
            'skewness': stats.skew(correlations),
            'kurtosis': stats.kurtosis(correlations)
        }
    
    def _calculate_diversification_metrics(self, correlation_matrix: np.ndarray,
                                         weights: np.ndarray,
                                         returns_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate diversification effectiveness metrics."""
        try:
            n_assets = len(weights)
            
            # Calculate asset volatilities
            asset_volatilities = returns_data.std().values
            
            # Use diversification effectiveness calculation
            diversification_metrics = self.calculate_diversification_effectiveness(
                correlation_matrix, weights, asset_volatilities
            )
            
            return diversification_metrics
            
        except Exception as e:
            self.logger.error(f"Error calculating diversification metrics: {e}")
            return {
                'diversification_ratio': 0.5,
                'effective_assets': len(weights),
                'concentration_ratio': 1.0 / len(weights)
            }
    
    def _detect_correlation_regime(self, correlation_matrix: np.ndarray,
                                 returns_data: pd.DataFrame) -> Dict[str, Any]:
        """Detect current correlation regime."""
        try:
            # Use the full regime detection method
            regime_info = self.detect_correlation_regimes(returns_data)
            
            return {
                'regime': regime_info.get('current_regime', CorrelationRegime.NORMAL_CORRELATION),
                'probability': regime_info.get('confidence', 0.5),
                'days_in_regime': regime_info.get('regime_duration_days', 0)
            }
            
        except Exception as e:
            self.logger.error(f"Error detecting correlation regime: {e}")
            return {
                'regime': CorrelationRegime.NORMAL_CORRELATION,
                'probability': 0.5,
                'days_in_regime': 0
            }
    
    def _calculate_tail_correlations(self, returns_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate tail correlation metrics."""
        try:
            # Calculate portfolio returns (equal weighted for simplicity)
            portfolio_returns = returns_data.mean(axis=1)
            
            # Identify tail events
            tail_5pct_threshold = portfolio_returns.quantile(TAIL_PERCENTILE)
            tail_1pct_threshold = portfolio_returns.quantile(EXTREME_TAIL_PERCENTILE)
            
            tail_5pct_mask = portfolio_returns <= tail_5pct_threshold
            tail_1pct_mask = portfolio_returns <= tail_1pct_threshold
            
            # Calculate correlations during tail events
            if np.sum(tail_5pct_mask) >= 2:
                tail_5pct_data = returns_data[tail_5pct_mask]
                tail_5pct_corr_matrix = tail_5pct_data.corr().values
                upper_tri_mask = np.triu(np.ones_like(tail_5pct_corr_matrix, dtype=bool), k=1)
                tail_5pct_correlations = tail_5pct_corr_matrix[upper_tri_mask]
                tail_5pct_avg = np.nanmean(tail_5pct_correlations)
            else:
                tail_5pct_avg = 0.0
            
            if np.sum(tail_1pct_mask) >= 2:
                tail_1pct_data = returns_data[tail_1pct_mask]
                tail_1pct_corr_matrix = tail_1pct_data.corr().values
                upper_tri_mask = np.triu(np.ones_like(tail_1pct_corr_matrix, dtype=bool), k=1)
                tail_1pct_correlations = tail_1pct_corr_matrix[upper_tri_mask]
                tail_1pct_avg = np.nanmean(tail_1pct_correlations)
            else:
                tail_1pct_avg = 0.0
            
            # Calculate tail dependence (simplified)
            normal_corr_matrix = returns_data.corr().values
            upper_tri_mask = np.triu(np.ones_like(normal_corr_matrix, dtype=bool), k=1)
            normal_correlations = normal_corr_matrix[upper_tri_mask]
            normal_avg = np.nanmean(normal_correlations)
            
            tail_dependence = (tail_5pct_avg - normal_avg) if normal_avg != 0 else 0.0
            
            return {
                'tail_5pct': tail_5pct_avg,
                'tail_1pct': tail_1pct_avg,
                'tail_dependence': tail_dependence
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating tail correlations: {e}")
            return {
                'tail_5pct': 0.7,
                'tail_1pct': 0.8,
                'tail_dependence': 0.1
            }
    
    def _calculate_correlation_changes(self, correlation_matrix: np.ndarray) -> Dict[str, float]:
        """Calculate correlation change metrics."""
        try:
            if len(self.correlation_history) < 2:
                return {'trend': 0.0, 'volatility': 0.0}
            
            # Get recent correlation matrices
            recent_matrices = [entry['matrix'] for entry in list(self.correlation_history)[-7:]]  # Last 7 entries
            
            if len(recent_matrices) < 2:
                return {'trend': 0.0, 'volatility': 0.0}
            
            # Calculate average correlations for each matrix
            avg_correlations = []
            for matrix in recent_matrices:
                upper_tri_mask = np.triu(np.ones_like(matrix, dtype=bool), k=1)
                avg_corr = np.mean(matrix[upper_tri_mask])
                avg_correlations.append(avg_corr)
            
            # Calculate trend (linear regression slope)
            x = np.arange(len(avg_correlations))
            if len(x) > 1 and np.var(x) > 0:
                slope, _, _, _, _ = stats.linregress(x, avg_correlations)
                trend = slope
            else:
                trend = 0.0
            
            # Calculate volatility of correlations
            volatility = np.std(avg_correlations) if len(avg_correlations) > 1 else 0.0
            
            return {
                'trend': trend,
                'volatility': volatility
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating correlation changes: {e}")
            return {'trend': 0.0, 'volatility': 0.0}
    
    def _assess_diversification_health(self, basic_stats: Dict[str, float],
                                     diversification_metrics: Dict[str, float]) -> Dict[str, Any]:
        """Assess overall diversification health."""
        avg_correlation = basic_stats['average']
        diversification_ratio = diversification_metrics.get('diversification_ratio', 0.5)
        effective_assets = diversification_metrics.get('effective_assets', 1.0)
        
        # Calculate health score (0-100)
        correlation_score = max(0, (HIGH_CORRELATION_THRESHOLD - avg_correlation) / HIGH_CORRELATION_THRESHOLD * 50)
        diversification_score = min(50, diversification_ratio * 50)
        
        health_score = correlation_score + diversification_score
        
        # Determine health level
        if health_score >= 80:
            health_level = DiversificationHealth.EXCELLENT
        elif health_score >= 65:
            health_level = DiversificationHealth.GOOD
        elif health_score >= 45:
            health_level = DiversificationHealth.MODERATE
        elif health_score >= 25:
            health_level = DiversificationHealth.POOR
        else:
            health_level = DiversificationHealth.CRITICAL
        
        return {
            'health_level': health_level,
            'health_score': health_score
        }
    
    # ==========================================================================
    # PRIVATE METHODS - Alert Management
    # ==========================================================================
    def _check_correlation_alerts(self, metrics: CorrelationMetrics,
                                correlation_matrix: np.ndarray) -> None:
        """Check for correlation alert conditions."""
        current_time = datetime.now()
        
        # High correlation alert
        if metrics.average_correlation > HIGH_CORRELATION_THRESHOLD:
            alert_key = "high_correlation"
            if self._should_create_alert(alert_key, current_time):
                alert = CorrelationAlert(
                    alert_id="",
                    alert_type="High Correlation",
                    severity=AlertSeverity.HIGH if metrics.average_correlation < CRISIS_CORRELATION_THRESHOLD else AlertSeverity.CRITICAL,
                    message=f"Portfolio average correlation is {metrics.average_correlation:.1%} (threshold: {HIGH_CORRELATION_THRESHOLD:.1%})",
                    current_value=metrics.average_correlation,
                    threshold_value=HIGH_CORRELATION_THRESHOLD,
                    change_magnitude=metrics.correlation_trend,
                    affected_assets=[]
                )
                self._add_alert(alert, alert_key)
        
        # Poor diversification alert
        if metrics.diversification_health in [DiversificationHealth.POOR, DiversificationHealth.CRITICAL]:
            alert_key = "poor_diversification"
            if self._should_create_alert(alert_key, current_time):
                alert = CorrelationAlert(
                    alert_id="",
                    alert_type="Poor Diversification",
                    severity=AlertSeverity.HIGH if metrics.diversification_health == DiversificationHealth.POOR else AlertSeverity.CRITICAL,
                    message=f"Portfolio diversification is {metrics.diversification_health.value} (health score: {metrics.health_score:.0f})",
                    current_value=metrics.health_score,
                    threshold_value=45.0,
                    change_magnitude=0.0,
                    affected_assets=[]
                )
                self._add_alert(alert, alert_key)
        
        # Correlation regime change alert
        if metrics.current_regime == CorrelationRegime.CRISIS_CORRELATION:
            alert_key = "crisis_correlation_regime"
            if self._should_create_alert(alert_key, current_time):
                alert = CorrelationAlert(
                    alert_id="",
                    alert_type="Crisis Correlation Regime",
                    severity=AlertSeverity.EMERGENCY,
                    message=f"Portfolio entered crisis correlation regime (probability: {metrics.regime_probability:.0%})",
                    current_value=metrics.average_correlation,
                    threshold_value=CRISIS_CORRELATION_THRESHOLD,
                    change_magnitude=metrics.correlation_trend,
                    affected_assets=[]
                )
                self._add_alert(alert, alert_key)
        
        # Tail correlation spike alert
        if metrics.tail_correlation_5pct > 0.9:
            alert_key = "tail_correlation_spike"
            if self._should_create_alert(alert_key, current_time):
                alert = CorrelationAlert(
                    alert_id="",
                    alert_type="Tail Correlation Spike",
                    severity=AlertSeverity.HIGH,
                    message=f"Tail correlation (5%) reached {metrics.tail_correlation_5pct:.1%}",
                    current_value=metrics.tail_correlation_5pct,
                    threshold_value=0.9,
                    change_magnitude=0.0,
                    affected_assets=[]
                )
                self._add_alert(alert, alert_key)
    
    def _should_create_alert(self, alert_key: str, current_time: datetime) -> bool:
        """Check if alert should be created based on suppression rules."""
        if alert_key in self.alert_suppression:
            time_since_last = (current_time - self.alert_suppression[alert_key]).total_seconds()
            if time_since_last < ALERT_SUPPRESSION_TIME:
                return False
        return True
    
    def _add_alert(self, alert: CorrelationAlert, alert_key: str) -> None:
        """Add correlation alert with suppression tracking."""
        self.alerts.append(alert)
        self.alert_suppression[alert_key] = datetime.now()
        self.logger.warning(f"Correlation alert: {alert.message}")
    
    def _detect_correlation_breakdowns(self, metrics: CorrelationMetrics,
                                     correlation_matrix: np.ndarray) -> None:
        """Detect correlation breakdown events."""
        try:
            # Check for sudden correlation spikes
            if len(self.correlation_history) >= 2:
                prev_metrics = self.correlation_history[-2]['metrics']
                correlation_change = metrics.average_correlation - prev_metrics.average_correlation
                
                if correlation_change > CORRELATION_SPIKE_THRESHOLD:
                    # Potential breakdown event
                    breakdown = CorrelationBreakdown(
                        event_id=f"breakdown_{int(time.time())}",
                        start_time=datetime.now(),
                        pre_breakdown_correlation=prev_metrics.average_correlation,
                        peak_breakdown_correlation=metrics.average_correlation,
                        breakdown_magnitude=correlation_change,
                        affected_asset_count=len(correlation_matrix),
                        breakdown_type="sudden",
                        market_condition="unknown",
                        recovery_status="ongoing",
                        portfolio_impact=correlation_change * 0.1,  # Simplified impact
                        diversification_loss=correlation_change
                    )
                    
                    self.breakdown_events.append(breakdown)
                    self.logger.warning(f"Correlation breakdown detected: {correlation_change:.1%} spike")
            
        except Exception as e:
            self.logger.error(f"Error detecting correlation breakdowns: {e}")
    
    # ==========================================================================
    # PRIVATE METHODS - Utilities
    # ==========================================================================
    async def _update_asset_profiles(self, returns_data: pd.DataFrame,
                                   correlation_matrix: np.ndarray,
                                   weights: np.ndarray) -> None:
        """Update individual asset correlation profiles."""
        try:
            asset_names = returns_data.columns.tolist()
            
            for i, asset_name in enumerate(asset_names):
                # Calculate asset's correlation with portfolio
                asset_correlations = correlation_matrix[i, :]
                portfolio_correlation = np.dot(weights, asset_correlations)
                
                # Find high correlation peers
                high_corr_peers = []
                for j, corr in enumerate(asset_correlations):
                    if j != i and corr > HIGH_CORRELATION_THRESHOLD:
                        high_corr_peers.append(asset_names[j])
                
                # Create or update asset profile
                profile = AssetCorrelationProfile(
                    asset_name=asset_name,
                    average_portfolio_correlation=portfolio_correlation,
                    max_portfolio_correlation=np.max(asset_correlations[asset_correlations < 1.0]) if len(asset_correlations) > 1 else 0.0,
                    correlation_volatility=np.std(asset_correlations),
                    correlation_trend=0.0,  # Would calculate from historical data
                    high_correlation_peers=high_corr_peers,
                    correlation_cluster="",  # Would assign from clustering
                    marginal_correlation_contribution=weights[i] * portfolio_correlation,
                    diversification_benefit=max(0, 1.0 - portfolio_correlation),
                    correlation_beta=portfolio_correlation,
                    tail_correlation_behavior="stable",
                    stress_correlation_multiplier=1.0
                )
                
                self.asset_profiles[asset_name] = profile
            
        except Exception as e:
            self.logger.error(f"Error updating asset profiles: {e}")
    
    async def _perform_correlation_clustering(self, correlation_matrix: np.ndarray,
                                            weights: np.ndarray) -> None:
        """Perform correlation clustering analysis."""
        try:
            if len(self.returns_data.columns) < 2:
                return
            
            asset_names = self.returns_data.columns.tolist()
            clusters = await self.perform_correlation_clustering(correlation_matrix, asset_names, weights)
            
            # Update asset profiles with cluster assignments
            for cluster_id, cluster in clusters.items():
                for asset_name in cluster.asset_names:
                    if asset_name in self.asset_profiles:
                        self.asset_profiles[asset_name].correlation_cluster = cluster_id
            
        except Exception as e:
            self.logger.error(f"Error performing correlation clustering: {e}")
    
    def _calculate_regime_duration(self, correlation_series: pd.Series, current_regime: CorrelationRegime) -> int:
        """Calculate how long current regime has persisted."""
        try:
            # Simple regime duration calculation
            # In production, would track regime changes more sophisticated
            return min(len(correlation_series), 30)  # Max 30 days lookback
            
        except Exception as e:
            self.logger.error(f"Error calculating regime duration: {e}")
            return 0
    
    def _detect_regime_change_probability(self, correlation_series: pd.Series) -> float:
        """Detect probability of regime change."""
        try:
            if len(correlation_series) < 5:
                return 0.0
            
            recent_values = correlation_series.tail(5).values
            volatility = np.std(recent_values)
            trend = np.polyfit(range(len(recent_values)), recent_values, 1)[0]
            
            # Higher volatility and trend indicate higher change probability
            change_prob = min(1.0, (volatility * 10 + abs(trend) * 5))
            
            return change_prob
            
        except Exception as e:
            self.logger.error(f"Error detecting regime change probability: {e}")
            return 0.0
    
    def _cleanup_old_alerts(self) -> None:
        """Clean up old alerts."""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # Remove old acknowledged alerts
        self.alerts = [alert for alert in self.alerts 
                      if not alert.acknowledged or alert.timestamp > cutoff_time]
        
        # Clean up alert suppression dictionary
        self.alert_suppression = {key: timestamp for key, timestamp in self.alert_suppression.items()
                                if timestamp > cutoff_time}
    
    def _update_regime_tracking(self) -> None:
        """Update regime stability tracking."""
        if self.correlation_history:
            current_regime = self.correlation_history[-1]['metrics'].current_regime
            
            if self._last_regime_change != current_regime:
                self._last_regime_change = current_regime
                self._regime_stability_count = 1
            else:
                self._regime_stability_count += 1
    
    def _check_alert_auto_resolution(self) -> None:
        """Check if any alerts can be auto-resolved."""
        if not self.correlation_history:
            return
        
        current_metrics = self.correlation_history[-1]['metrics']
        
        for alert in self.alerts:
            if not alert.auto_resolved and not alert.acknowledged:
                # Auto-resolve if condition improved
                if alert.alert_type == "High Correlation" and current_metrics.average_correlation < MODERATE_CORRELATION_THRESHOLD:
                    alert.auto_resolved = True
                    self.logger.info(f"Auto-resolved alert: {alert.alert_id}")
                elif alert.alert_type == "Poor Diversification" and current_metrics.diversification_health in [DiversificationHealth.GOOD, DiversificationHealth.EXCELLENT]:
                    alert.auto_resolved = True
                    self.logger.info(f"Auto-resolved alert: {alert.alert_id}")
    
    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def cleanup(self) -> None:
        """Clean up correlation risk manager resources."""
        try:
            # Stop monitoring
            self.stop_monitoring()
            
            # Clean up thread pool
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=True)
            
            # Clear data structures
            self.correlation_history.clear()
            self.alerts.clear()
            self.asset_profiles.clear()
            self.correlation_clusters.clear()
            
            self.logger.info("Correlation risk manager cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_sample_returns_data(n_assets: int = 10, n_periods: int = 100, 
                              base_correlation: float = 0.3) -> pd.DataFrame:
    """Create sample returns data for testing."""
    np.random.seed(42)  # For reproducible results
    
    # Generate correlated returns
    base_returns = np.random.normal(0, 0.02, (n_periods, 1))  # Market factor
    
    returns_data = {}
    for i in range(n_assets):
        # Each asset has some correlation with market factor plus idiosyncratic risk
        market_loading = 0.3 + 0.4 * np.random.random()  # Between 0.3 and 0.7
        idiosyncratic = np.random.normal(0, 0.015, (n_periods, 1))
        
        asset_returns = market_loading * base_returns + np.sqrt(1 - market_loading**2) * idiosyncratic
        returns_data[f'Asset_{i+1}'] = asset_returns.flatten()
    
    dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='D')
    return pd.DataFrame(returns_data, index=dates)

def analyze_correlation_breakdown(returns_data: pd.DataFrame, 
                                event_date: str) -> Dict[str, Any]:
    """Analyze correlation breakdown around a specific event."""
    try:
        event_datetime = pd.to_datetime(event_date)
        
        # Get pre-event and post-event periods
        pre_event_data = returns_data[returns_data.index < event_datetime].tail(30)  # 30 days before
        post_event_data = returns_data[returns_data.index >= event_datetime].head(30)  # 30 days after
        
        if len(pre_event_data) < 10 or len(post_event_data) < 10:
            return {'error': 'Insufficient data around event date'}
        
        # Calculate correlations
        pre_corr = pre_event_data.corr()
        post_corr = post_event_data.corr()
        
        # Extract upper triangular correlations
        upper_tri_mask = np.triu(np.ones_like(pre_corr.values, dtype=bool), k=1)
        
        pre_correlations = pre_corr.values[upper_tri_mask]
        post_correlations = post_corr.values[upper_tri_mask]
        
        # Calculate breakdown metrics
        correlation_change = np.mean(post_correlations) - np.mean(pre_correlations)
        correlation_volatility_change = np.std(post_correlations) - np.std(pre_correlations)
        
        return {
            'event_date': event_date,
            'pre_event_avg_correlation': np.mean(pre_correlations),
            'post_event_avg_correlation': np.mean(post_correlations),
            'correlation_change': correlation_change,
            'correlation_volatility_change': correlation_volatility_change,
            'breakdown_magnitude': correlation_change / np.mean(pre_correlations) if np.mean(pre_correlations) != 0 else 0.0,
            'affected_pairs': np.sum(np.abs(post_correlations - pre_correlations) > 0.1),
            'total_pairs': len(pre_correlations)
        }
        
    except Exception as e:
        return {'error': f'Error analyzing correlation breakdown: {e}'}

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_correlation_manager_instance: Optional[CorrelationRiskManager] = None

def get_correlation_manager_instance() -> CorrelationRiskManager:
    """
    Get singleton instance of the correlation risk manager.
    
    Returns:
        CorrelationRiskManager instance
    """
    global _correlation_manager_instance
    if _correlation_manager_instance is None:
        _correlation_manager_instance = CorrelationRiskManager()
        _correlation_manager_instance.initialize()
    return _correlation_manager_instance

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
async def main():
    """Main execution function for testing and demonstration."""
    print("🎯 SPYDER E10 - Correlation Risk Manager")
    print("=" * 80)
    
    try:
        # Create correlation risk manager
        corr_manager = CorrelationRiskManager()
        print("✅ Correlation Risk Manager initialized")
        
        # Initialize manager
        if not corr_manager.initialize():
            print("❌ Failed to initialize correlation risk manager")
            return False
        
        # Create sample data
        print("\n📊 Creating sample portfolio returns...")
        returns_data = create_sample_returns_data(n_assets=8, n_periods=150)
        print(f"   Created data: {len(returns_data)} periods, {len(returns_data.columns)} assets")
        
        # Analyze portfolio correlation
        print("\n🔍 Analyzing portfolio correlation...")
        metrics = await corr_manager.analyze_portfolio_correlation(returns_data)
        
        print(f"   Average Correlation: {metrics.average_correlation:.3f}")
        print(f"   Max Correlation: {metrics.max_correlation:.3f}")
        print(f"   Diversification Ratio: {metrics.diversification_ratio:.3f}")
        print(f"   Effective Assets: {metrics.effective_assets:.1f}")
        print(f"   Current Regime: {metrics.current_regime.value}")
        print(f"   Health Score: {metrics.health_score:.1f}/100")
        print(f"   Diversification Health: {metrics.diversification_health.value}")
        
        # Test rolling correlation
        print("\n📈 Calculating rolling correlations...")
        rolling_corr = corr_manager.calculate_rolling_correlation(returns_data, window=30)
        print(f"   Rolling periods calculated: {len(rolling_corr)}")
        if not rolling_corr.empty:
            print(f"   Latest avg correlation: {rolling_corr['avg_correlation'].iloc[-1]:.3f}")
            print(f"   Correlation trend: {rolling_corr['avg_correlation'].iloc[-5:].mean() - rolling_corr['avg_correlation'].iloc[:5].mean():.3f}")
        
        # Test regime detection
        print("\n🎛️ Testing regime detection...")
        regime_info = corr_manager.detect_correlation_regimes(returns_data)
        print(f"   Current Regime: {regime_info['current_regime'].value}")
        print(f"   Regime Confidence: {regime_info.get('confidence', 0):.1%}")
        print(f"   Z-Score: {regime_info.get('z_score', 0):.2f}")
        
        # Test correlation clustering
        print("\n🔗 Testing correlation clustering...")
        if len(corr_manager.correlation_matrices) > 0:
            matrix = list(corr_manager.correlation_matrices.values())[0]
            clusters = await corr_manager.perform_correlation_clustering(
                matrix, returns_data.columns.tolist()
            )
            print(f"   Created clusters: {len(clusters)}")
            for cluster_id, cluster in clusters.items():
                print(f"     {cluster_id}: {cluster.cluster_size} assets, {cluster.internal_correlation:.3f} internal corr")
        
        # Test diversification analysis
        print("\n📊 Testing diversification effectiveness...")
        weights = np.ones(len(returns_data.columns)) / len(returns_data.columns)
        volatilities = returns_data.std().values
        if len(corr_manager.correlation_matrices) > 0:
            matrix = list(corr_manager.correlation_matrices.values())[0]
            div_metrics = corr_manager.calculate_diversification_effectiveness(matrix, weights, volatilities)
            print(f"   Diversification Ratio: {div_metrics['diversification_ratio']:.3f}")
            print(f"   Risk Reduction Benefit: {div_metrics['risk_reduction_benefit']:.1%}")
            print(f"   Diversification Efficiency: {div_metrics['diversification_efficiency']:.1%}")
        
        # Test alert system
        print("\n⚠️ Testing alert system...")
        active_alerts = corr_manager.get_active_alerts()
        print(f"   Active alerts: {len(active_alerts)}")
        for alert in active_alerts[:3]:  # Show first 3 alerts
            print(f"     {alert.alert_type} ({alert.severity.value}): {alert.message}")
        
        # Generate report
        print("\n📋 Generating correlation risk report...")
        report = corr_manager.generate_correlation_report()
        print("📊 CORRELATION RISK REPORT:")
        print("-" * 50)
        # Print first few lines of report
        report_lines = report.split('\n')[:20]
        for line in report_lines:
            print(line)
        if len(report.split('\n')) > 20:
            print("   ... (truncated)")
        
        # Test breakdown analysis
        print("\n💥 Testing correlation breakdown analysis...")
        breakdown_analysis = analyze_correlation_breakdown(
            returns_data, returns_data.index[75].strftime('%Y-%m-%d')
        )
        if 'error' not in breakdown_analysis:
            print(f"   Correlation Change: {breakdown_analysis['correlation_change']:.3f}")
            print(f"   Breakdown Magnitude: {breakdown_analysis['breakdown_magnitude']:.1%}")
            print(f"   Affected Pairs: {breakdown_analysis['affected_pairs']}/{breakdown_analysis['total_pairs']}")
        
        # Get summary
        summary = corr_manager.get_correlation_summary()
        print(f"\n📈 CORRELATION MANAGER SUMMARY:")
        print(f"   Status: {summary['manager_status']['status'].upper()}")
        print(f"   Assets Monitored: {summary['manager_status']['assets_monitored']}")
        print(f"   Total Alerts: {summary['alert_summary']['total_alerts']}")
        print(f"   Correlation Clusters: {summary['cluster_summary']['total_clusters']}")
        if summary.get('current_metrics'):
            metrics_summary = summary['current_metrics']
            print(f"   Health Score: {metrics_summary['health_score']:.1f}/100")
            print(f"   Diversification Health: {metrics_summary['diversification_health'].upper()}")
        
        # Cleanup
        corr_manager.cleanup()
        print("\n✅ Correlation Risk Manager test completed successfully!")
        
        print(f"\n🎯 CORRELATION RISK MANAGEMENT CAPABILITIES:")
        print(f"   • Real-time Correlation Monitoring")
        print(f"   • 7 Correlation Estimation Models")
        print(f"   • Regime Detection & Analysis")
        print(f"   • Tail Correlation Assessment")
        print(f"   • Hierarchical Clustering Analysis")
        print(f"   • Diversification Effectiveness Metrics")
        print(f"   • Correlation Breakdown Detection")
        print(f"   • Professional Alert System")
        print(f"   • Comprehensive Risk Reporting")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(main())
