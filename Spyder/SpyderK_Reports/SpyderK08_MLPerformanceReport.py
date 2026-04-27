#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderK_Reports
Module: SpyderK08_MLPerformanceReport.py
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
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import dataclass, asdict
from enum import Enum
import json
from collections import defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats
from sklearn.metrics import (

    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, mean_squared_error, mean_absolute_error, r2_score
)
from sklearn.inspection import permutation_importance

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderH_Storage.SpyderH01_DataAccessLayer import get_data_access_layer
from Spyder.SpyderL_ML.SpyderL01_MLPredictor import MLPredictor as MLFramework

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Performance thresholds
ACCURACY_THRESHOLD = 0.65
PRECISION_THRESHOLD = 0.60
RECALL_THRESHOLD = 0.60
F1_THRESHOLD = 0.60

# Drift detection thresholds
DRIFT_WARNING_THRESHOLD = 0.05  # p-value for statistical tests
DRIFT_CRITICAL_THRESHOLD = 0.01
PERFORMANCE_DROP_THRESHOLD = 0.10  # 10% drop triggers alert

# Model comparison
MIN_SAMPLE_SIZE_AB_TEST = 100
CONFIDENCE_LEVEL = 0.95

# Feature importance
TOP_FEATURES_TO_TRACK = 20
FEATURE_IMPORTANCE_CHANGE_THRESHOLD = 0.25  # 25% change

# ==============================================================================
# ENUMS
# ==============================================================================
class ModelType(Enum):
    """Types of ML models"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    CLUSTERING = "clustering"
    ANOMALY_DETECTION = "anomaly_detection"

class DriftType(Enum):
    """Types of model drift"""
    CONCEPT_DRIFT = "concept_drift"  # P(y|X) changes
    DATA_DRIFT = "data_drift"  # P(X) changes
    PREDICTION_DRIFT = "prediction_drift"  # P(y_hat) changes
    PERFORMANCE_DRIFT = "performance_drift"  # Accuracy drops

class ABTestStatus(Enum):
    """A/B test status"""
    RUNNING = "running"
    COMPLETED = "completed"
    STOPPED_EARLY = "stopped_early"
    INCONCLUSIVE = "inconclusive"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ModelPerformanceMetrics:
    """Performance metrics for a model"""
    model_id: str
    timestamp: datetime
    model_type: ModelType
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    auc_roc: float | None = None
    mse: float | None = None
    mae: float | None = None
    r2: float | None = None
    sample_size: int = 0
    prediction_distribution: dict[str, float] | None = None

@dataclass
class FeatureImportance:
    """Feature importance tracking"""
    feature_name: str
    importance_score: float
    rank: int
    importance_type: str  # 'gain', 'permutation', 'shap'
    std_deviation: float | None = None

@dataclass
class ModelDriftReport:
    """Model drift detection report"""
    model_id: str
    drift_type: DriftType
    detection_date: datetime
    p_value: float
    test_statistic: float
    test_name: str
    severity: str  # 'warning', 'critical'
    affected_features: list[str]
    recommendation: str

@dataclass
class ABTestResult:
    """A/B test results between models"""
    test_id: str
    model_a_id: str
    model_b_id: str
    start_date: datetime
    end_date: datetime | None
    status: ABTestStatus
    metric_tested: str
    model_a_performance: float
    model_b_performance: float
    sample_size_a: int
    sample_size_b: int
    p_value: float
    confidence_interval: tuple[float, float]
    winner: str | None = None
    improvement: float | None = None

@dataclass
class ModelComparisonReport:
    """Comprehensive model comparison"""
    models: list[str]
    comparison_date: datetime
    best_model: str
    metrics_comparison: pd.DataFrame
    ranking: dict[str, int]
    recommendations: list[str]
    visualizations: dict[str, Any]

@dataclass
class PerformanceTrend:
    """Performance trend analysis"""
    model_id: str
    metric: str
    trend_direction: str  # 'improving', 'stable', 'degrading'
    trend_slope: float
    trend_significance: float
    forecast_7_days: float
    forecast_30_days: float

@dataclass
class MLPerformanceSummary:
    """Overall ML performance summary"""
    total_models: int
    active_models: int
    models_in_production: list[str]
    average_accuracy: float
    models_with_drift: list[str]
    recent_ab_tests: list[ABTestResult]
    feature_importance_changes: dict[str, list[str]]
    recommendations: list[str]

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class MLPerformanceReport:
    """
    Machine Learning model performance tracking and reporting engine.

    This class provides comprehensive ML model performance analysis including
    accuracy tracking, drift detection, feature importance monitoring, A/B testing,
    and comparative analysis across multiple models.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        dal: Data access layer for ML data
        ml_framework: ML framework for model access

    Example:
        >>> ml_report = MLPerformanceReport()
        >>> performance = ml_report.track_model_performance('model_001')
        >>> drift_report = ml_report.detect_model_drift('model_001')
        >>> ml_report.generate_ml_report('ml_performance_report.html')
    """

    def __init__(self):
        """Initialize the ML performance report module."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.dal = get_data_access_layer()
        self.ml_framework = MLFramework()

        # Performance tracking
        self.performance_history: dict[str, list[ModelPerformanceMetrics]] = defaultdict(list)
        self.feature_importance_history: dict[str, list[dict[str, FeatureImportance]]] = defaultdict(list)  # noqa: E501
        self.drift_reports: list[ModelDriftReport] = []
        self.ab_tests: dict[str, ABTestResult] = {}

        # Configuration
        self.tracking_window = 90  # days
        self.evaluation_frequency = 'daily'

        self.logger.info("MLPerformanceReport initialized")

    # ==========================================================================
    # PERFORMANCE TRACKING METHODS
    # ==========================================================================
    def track_model_performance(self, model_id: str,
                              evaluation_data: pd.DataFrame | None = None) -> ModelPerformanceMetrics:  # noqa: E501
        """
        Track performance metrics for a model.

        Args:
            model_id: Unique model identifier
            evaluation_data: Data to evaluate model on (if None, uses recent data)

        Returns:
            ModelPerformanceMetrics object
        """
        try:
            # Get model
            model_info = self.ml_framework.get_model(model_id)

            if not model_info:
                self.logger.error("Model %s not found", model_id)
                return None

            # Get evaluation data if not provided
            if evaluation_data is None:
                evaluation_data = self._get_recent_evaluation_data(model_id)

            if evaluation_data.empty:
                self.logger.warning("No evaluation data available for %s", model_id)
                return None

            # Make predictions
            X = evaluation_data.drop(columns=['target'], errors='ignore')
            y_true = evaluation_data.get('target')

            model = model_info['model']
            y_pred = model.predict(X)

            # Calculate metrics based on model type
            model_type = ModelType(model_info.get('model_type', 'classification'))
            metrics = ModelPerformanceMetrics(
                model_id=model_id,
                timestamp=datetime.now(timezone.utc),
                model_type=model_type,
                sample_size=len(y_true)
            )

            if model_type == ModelType.CLASSIFICATION:
                metrics.accuracy = accuracy_score(y_true, y_pred)
                metrics.precision = precision_score(y_true, y_pred, average='weighted')
                metrics.recall = recall_score(y_true, y_pred, average='weighted')
                metrics.f1_score = f1_score(y_true, y_pred, average='weighted')

                # ROC-AUC for binary classification
                if len(np.unique(y_true)) == 2:
                    if hasattr(model, 'predict_proba'):
                        y_proba = model.predict_proba(X)[:, 1]
                        metrics.auc_roc = roc_auc_score(y_true, y_proba)

                # Prediction distribution
                unique, counts = np.unique(y_pred, return_counts=True)
                metrics.prediction_distribution = dict(zip(unique, counts / len(y_pred), strict=False))  # noqa: E501

            elif model_type == ModelType.REGRESSION:
                metrics.mse = mean_squared_error(y_true, y_pred)
                metrics.mae = mean_absolute_error(y_true, y_pred)
                metrics.r2 = r2_score(y_true, y_pred)

            # Store in history
            self.performance_history[model_id].append(metrics)

            # Trim old history
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.tracking_window)
            self.performance_history[model_id] = [
                m for m in self.performance_history[model_id]
                if m.timestamp > cutoff_date
            ]

            # Save to database
            self._save_performance_metrics(metrics)

            return metrics

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'track_model_performance',
                'model_id': model_id
            })
            return None

    def track_feature_importance(self, model_id: str,
                               method: str = 'permutation') -> list[FeatureImportance]:
        """
        Track feature importance for a model.

        Args:
            model_id: Model identifier
            method: Method to calculate importance ('permutation', 'native', 'shap')

        Returns:
            List of FeatureImportance objects
        """
        try:
            # Get model and data
            model_info = self.ml_framework.get_model(model_id)
            if not model_info:
                return []

            model = model_info['model']
            feature_names = model_info.get('feature_names', [])

            # Get evaluation data
            eval_data = self._get_recent_evaluation_data(model_id)
            if eval_data.empty:
                return []

            X = eval_data.drop(columns=['target'], errors='ignore')
            y = eval_data.get('target')

            importance_scores = {}

            if method == 'permutation':
                # Permutation importance
                perm_importance = permutation_importance(
                    model, X, y, n_repeats=10, random_state=42
                )

                for idx, feature in enumerate(feature_names[:len(perm_importance.importances_mean)]):  # noqa: E501
                    importance_scores[feature] = {
                        'score': perm_importance.importances_mean[idx],
                        'std': perm_importance.importances_std[idx]
                    }

            elif method == 'native' and hasattr(model, 'feature_importances_'):
                # Native feature importance (e.g., tree-based models)
                for idx, feature in enumerate(feature_names[:len(model.feature_importances_)]):
                    importance_scores[feature] = {
                        'score': model.feature_importances_[idx],
                        'std': None
                    }

            # Create FeatureImportance objects
            sorted_features = sorted(
                importance_scores.items(),
                key=lambda x: x[1]['score'],
                reverse=True
            )

            feature_importance_list = []
            for rank, (feature, scores) in enumerate(sorted_features[:TOP_FEATURES_TO_TRACK], 1):
                fi = FeatureImportance(
                    feature_name=feature,
                    importance_score=scores['score'],
                    rank=rank,
                    importance_type=method,
                    std_deviation=scores.get('std')
                )
                feature_importance_list.append(fi)

            # Store in history
            timestamp = datetime.now(timezone.utc)
            self.feature_importance_history[model_id].append({
                'timestamp': timestamp,
                'features': feature_importance_list
            })

            # Detect significant changes
            self._detect_feature_importance_changes(model_id)

            return feature_importance_list

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'track_feature_importance',
                'model_id': model_id
            })
            return []

    # ==========================================================================
    # DRIFT DETECTION METHODS
    # ==========================================================================
    def detect_model_drift(self, model_id: str) -> ModelDriftReport | None:
        """
        Detect various types of model drift.

        Args:
            model_id: Model identifier

        Returns:
            ModelDriftReport if drift detected, None otherwise
        """
        try:
            # Get historical data
            history = self.performance_history.get(model_id, [])

            if len(history) < 10:  # Need sufficient history
                self.logger.warning("Insufficient history for drift detection: %s", model_id)
                return None

            # Split into reference and recent periods
            mid_point = len(history) // 2
            reference_metrics = history[:mid_point]
            recent_metrics = history[mid_point:]

            # Check performance drift
            perf_drift = self._detect_performance_drift(reference_metrics, recent_metrics)
            if perf_drift:
                return perf_drift

            # Check prediction drift
            pred_drift = self._detect_prediction_drift(reference_metrics, recent_metrics)
            if pred_drift:
                return pred_drift

            # Check data drift (requires access to input features)
            data_drift = self._detect_data_drift(model_id)
            if data_drift:
                return data_drift

            return None

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'detect_model_drift',
                'model_id': model_id
            })
            return None

    def _detect_performance_drift(self, reference: list[ModelPerformanceMetrics],
                                 recent: list[ModelPerformanceMetrics]) -> ModelDriftReport | None:
        """Detect performance-based drift."""
        try:
            # Get primary metric based on model type
            if reference[0].model_type == ModelType.CLASSIFICATION:
                ref_scores = [m.f1_score for m in reference if m.f1_score is not None]
                rec_scores = [m.f1_score for m in recent if m.f1_score is not None]
                metric_name = 'f1_score'
            else:
                ref_scores = [m.r2 for m in reference if m.r2 is not None]
                rec_scores = [m.r2 for m in recent if m.r2 is not None]
                metric_name = 'r2_score'

            if not ref_scores or not rec_scores:
                return None

            # Statistical test for performance difference
            t_stat, p_value = stats.ttest_ind(ref_scores, rec_scores)

            # Check if performance dropped significantly
            ref_mean = np.mean(ref_scores)
            rec_mean = np.mean(rec_scores)
            performance_drop = (ref_mean - rec_mean) / ref_mean

            if p_value < DRIFT_WARNING_THRESHOLD and performance_drop > PERFORMANCE_DROP_THRESHOLD:
                severity = 'critical' if p_value < DRIFT_CRITICAL_THRESHOLD else 'warning'

                return ModelDriftReport(
                    model_id=reference[0].model_id,
                    drift_type=DriftType.PERFORMANCE_DRIFT,
                    detection_date=datetime.now(timezone.utc),
                    p_value=p_value,
                    test_statistic=t_stat,
                    test_name='t-test',
                    severity=severity,
                    affected_features=[metric_name],
                    recommendation=f"Performance degraded by {performance_drop:.1%}. Consider retraining or investigating data quality."  # noqa: E501
                )

            return None

        except Exception:
            return None

    def _detect_prediction_drift(self, reference: list[ModelPerformanceMetrics],
                               recent: list[ModelPerformanceMetrics]) -> ModelDriftReport | None:
        """Detect drift in prediction distributions."""
        try:
            # Get prediction distributions
            ref_dists = [m.prediction_distribution for m in reference if m.prediction_distribution]
            rec_dists = [m.prediction_distribution for m in recent if m.prediction_distribution]

            if not ref_dists or not rec_dists:
                return None

            # Aggregate distributions
            ref_agg = defaultdict(float)
            rec_agg = defaultdict(float)

            for dist in ref_dists:
                for key, value in dist.items():
                    ref_agg[key] += value / len(ref_dists)

            for dist in rec_dists:
                for key, value in dist.items():
                    rec_agg[key] += value / len(rec_dists)

            # Chi-square test for distribution difference
            all_keys = sorted(set(ref_agg.keys()) | set(rec_agg.keys()))
            ref_values = [ref_agg.get(k, 0) for k in all_keys]
            rec_values = [rec_agg.get(k, 0) for k in all_keys]

            # Scale to counts for chi-square
            total_samples = 1000
            ref_counts = [int(v * total_samples) for v in ref_values]
            rec_counts = [int(v * total_samples) for v in rec_values]

            chi2, p_value = stats.chisquare(rec_counts, ref_counts)

            if p_value < DRIFT_WARNING_THRESHOLD:
                severity = 'critical' if p_value < DRIFT_CRITICAL_THRESHOLD else 'warning'

                return ModelDriftReport(
                    model_id=reference[0].model_id,
                    drift_type=DriftType.PREDICTION_DRIFT,
                    detection_date=datetime.now(timezone.utc),
                    p_value=p_value,
                    test_statistic=chi2,
                    test_name='chi-square',
                    severity=severity,
                    affected_features=['prediction_distribution'],
                    recommendation="Prediction distribution has shifted. Investigate feature changes or concept drift."  # noqa: E501
                )

            return None

        except Exception:
            return None

    def _detect_data_drift(self, model_id: str) -> ModelDriftReport | None:
        """Detect drift in input data distributions."""
        # This would require access to historical feature distributions
        # Placeholder for now
        return None

    # ==========================================================================
    # A/B TESTING METHODS
    # ==========================================================================
    def start_ab_test(self, model_a_id: str, model_b_id: str,
                     metric: str = 'f1_score', test_id: str | None = None) -> str:
        """
        Start an A/B test between two models.

        Args:
            model_a_id: First model ID
            model_b_id: Second model ID
            metric: Metric to compare
            test_id: Optional test ID (generated if not provided)

        Returns:
            Test ID
        """
        try:
            if test_id is None:
                test_id = f"ab_test_{model_a_id}_{model_b_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"  # noqa: E501

            ab_test = ABTestResult(
                test_id=test_id,
                model_a_id=model_a_id,
                model_b_id=model_b_id,
                start_date=datetime.now(timezone.utc),
                end_date=None,
                status=ABTestStatus.RUNNING,
                metric_tested=metric,
                model_a_performance=0.0,
                model_b_performance=0.0,
                sample_size_a=0,
                sample_size_b=0,
                p_value=1.0,
                confidence_interval=(0.0, 0.0)
            )

            self.ab_tests[test_id] = ab_test
            self.logger.info("Started A/B test: %s", test_id)

            return test_id

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'start_ab_test',
                'model_a': model_a_id,
                'model_b': model_b_id
            })
            return ""

    def update_ab_test(self, test_id: str) -> ABTestResult:
        """
        Update A/B test results with latest data.

        Args:
            test_id: Test identifier

        Returns:
            Updated ABTestResult
        """
        try:
            if test_id not in self.ab_tests:
                self.logger.error("Test %s not found", test_id)
                return None

            ab_test = self.ab_tests[test_id]

            if ab_test.status != ABTestStatus.RUNNING:
                return ab_test

            # Get performance metrics for both models
            model_a_metrics = [
                m for m in self.performance_history[ab_test.model_a_id]
                if m.timestamp >= ab_test.start_date
            ]

            model_b_metrics = [
                m for m in self.performance_history[ab_test.model_b_id]
                if m.timestamp >= ab_test.start_date
            ]

            if not model_a_metrics or not model_b_metrics:
                return ab_test

            # Extract metric values
            metric_name = ab_test.metric_tested
            a_values = [getattr(m, metric_name) for m in model_a_metrics if getattr(m, metric_name) is not None]  # noqa: E501
            b_values = [getattr(m, metric_name) for m in model_b_metrics if getattr(m, metric_name) is not None]  # noqa: E501

            if len(a_values) < MIN_SAMPLE_SIZE_AB_TEST or len(b_values) < MIN_SAMPLE_SIZE_AB_TEST:
                return ab_test

            # Update performance
            ab_test.model_a_performance = np.mean(a_values)
            ab_test.model_b_performance = np.mean(b_values)
            ab_test.sample_size_a = len(a_values)
            ab_test.sample_size_b = len(b_values)

            # Statistical test
            t_stat, p_value = stats.ttest_ind(a_values, b_values)
            ab_test.p_value = p_value

            # Confidence interval for difference
            diff = ab_test.model_b_performance - ab_test.model_a_performance
            se = np.sqrt(np.var(a_values)/len(a_values) + np.var(b_values)/len(b_values))
            ci_margin = 1.96 * se  # 95% confidence
            ab_test.confidence_interval = (diff - ci_margin, diff + ci_margin)

            # Determine winner if significant
            if p_value < 0.05:
                if ab_test.model_b_performance > ab_test.model_a_performance:
                    ab_test.winner = ab_test.model_b_id
                    ab_test.improvement = (ab_test.model_b_performance - ab_test.model_a_performance) / ab_test.model_a_performance  # noqa: E501
                else:
                    ab_test.winner = ab_test.model_a_id
                    ab_test.improvement = (ab_test.model_a_performance - ab_test.model_b_performance) / ab_test.model_b_performance  # noqa: E501

                ab_test.status = ABTestStatus.COMPLETED
                ab_test.end_date = datetime.now(timezone.utc)

            return ab_test

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'update_ab_test',
                'test_id': test_id
            })
            return None

    # ==========================================================================
    # MODEL COMPARISON METHODS
    # ==========================================================================
    def compare_models(self, model_ids: list[str]) -> ModelComparisonReport:
        """
        Compare multiple models across various metrics.

        Args:
            model_ids: List of model IDs to compare

        Returns:
            ModelComparisonReport with comprehensive comparison
        """
        try:
            # Collect metrics for all models
            comparison_data = []

            for model_id in model_ids:
                # Get latest metrics
                history = self.performance_history.get(model_id, [])
                if not history:
                    continue

                latest = history[-1]
                avg_metrics = self._calculate_average_metrics(history[-30:])  # Last 30 days

                model_data = {
                    'model_id': model_id,
                    'latest_accuracy': latest.accuracy,
                    'latest_f1': latest.f1_score,
                    'latest_precision': latest.precision,
                    'latest_recall': latest.recall,
                    'avg_accuracy': avg_metrics.get('accuracy', 0),
                    'avg_f1': avg_metrics.get('f1_score', 0),
                    'stability': self._calculate_stability(history[-30:]),
                    'trend': self._calculate_trend(history[-30:])
                }

                comparison_data.append(model_data)

            if not comparison_data:
                return self._empty_comparison_report(model_ids)

            # Create comparison DataFrame
            comparison_df = pd.DataFrame(comparison_data)

            # Rank models
            ranking_metrics = ['avg_f1', 'avg_accuracy', 'stability']
            rankings = {}

            for metric in ranking_metrics:
                sorted_models = comparison_df.sort_values(metric, ascending=False)['model_id'].tolist()  # noqa: E501
                for rank, model_id in enumerate(sorted_models, 1):
                    if model_id not in rankings:
                        rankings[model_id] = 0
                    rankings[model_id] += rank

            # Overall ranking (lower is better)
            final_ranking = sorted(rankings.items(), key=lambda x: x[1])
            best_model = final_ranking[0][0] if final_ranking else None

            # Generate visualizations
            visualizations = self._generate_comparison_charts(comparison_df)

            # Generate recommendations
            recommendations = self._generate_model_recommendations(comparison_df, rankings)

            return ModelComparisonReport(
                models=model_ids,
                comparison_date=datetime.now(timezone.utc),
                best_model=best_model,
                metrics_comparison=comparison_df,
                ranking={model: rank for rank, (model, _) in enumerate(final_ranking, 1)},
                recommendations=recommendations,
                visualizations=visualizations
            )

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'compare_models',
                'model_ids': model_ids
            })
            return self._empty_comparison_report(model_ids)

    # ==========================================================================
    # REPORTING METHODS
    # ==========================================================================
    def generate_ml_report(self, output_path: str, format: str = 'html',
                         include_models: list[str] | None = None) -> bool:
        """
        Generate comprehensive ML performance report.

        Args:
            output_path: Path for output file
            format: Output format ('html', 'pdf', 'json')
            include_models: Specific models to include (None for all)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get models to report on
            if include_models is None:
                include_models = list(self.performance_history.keys())

            # Gather data for each model
            model_reports = []

            for model_id in include_models:
                # Get performance history
                perf_history = self.performance_history.get(model_id, [])
                if not perf_history:
                    continue

                # Get feature importance
                feature_history = self.feature_importance_history.get(model_id, [])

                # Get drift reports
                model_drift_reports = [
                    d for d in self.drift_reports
                    if d.model_id == model_id
                ]

                # Get A/B tests
                model_ab_tests = [
                    test for test in self.ab_tests.values()
                    if model_id in [test.model_a_id, test.model_b_id]
                ]

                # Calculate trends
                trends = self._analyze_performance_trends(perf_history)

                model_report = {
                    'model_id': model_id,
                    'latest_performance': asdict(perf_history[-1]) if perf_history else None,
                    'performance_history': [asdict(p) for p in perf_history[-30:]],  # Last 30 days
                    'trends': trends,
                    'feature_importance': self._format_feature_importance(feature_history),
                    'drift_reports': [asdict(d) for d in model_drift_reports],
                    'ab_tests': [asdict(t) for t in model_ab_tests],
                    'recommendations': self._generate_model_specific_recommendations(
                        model_id, perf_history, model_drift_reports
                    )
                }

                model_reports.append(model_report)

            # Generate summary
            summary = self._generate_ml_summary(model_reports)

            # Generate visualizations
            charts = self._generate_ml_charts(model_reports)

            # Compile report
            report_data = {
                'report_date': datetime.now(timezone.utc).isoformat(),
                'summary': asdict(summary),
                'model_reports': model_reports,
                'charts': charts,
                'generated_by': 'SpyderK08_MLPerformanceReport'
            }

            # Export report
            if format == 'html':
                return self._export_html_ml_report(report_data, output_path)
            elif format == 'pdf':
                return self._export_pdf_ml_report(report_data, output_path)
            elif format == 'json':
                return self._export_json_ml_report(report_data, output_path)
            else:
                self.logger.error("Unsupported format: %s", format)
                return False

        except Exception as e:
            self.error_handler.handle_error(e, {
                'method': 'generate_ml_report',
                'output_path': output_path,
                'format': format
            })
            return False

    # ==========================================================================
    # PRIVATE HELPER METHODS
    # ==========================================================================
    def _get_recent_evaluation_data(self, model_id: str) -> pd.DataFrame:
        """Get recent data for model evaluation."""
        try:
            # This would typically fetch from your data pipeline
            # For now, returning empty DataFrame
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def _save_performance_metrics(self, metrics: ModelPerformanceMetrics) -> None:
        """Save performance metrics to database."""
        try:
            self.dal.save_ml_performance(asdict(metrics))
        except Exception as e:
            self.logger.error("Error saving metrics: %s", e)

    def _detect_feature_importance_changes(self, model_id: str) -> None:
        """Detect significant changes in feature importance."""
        try:
            history = self.feature_importance_history.get(model_id, [])

            if len(history) < 2:
                return

            # Compare recent to previous
            recent = history[-1]['features']
            previous = history[-2]['features']

            recent_dict = {f.feature_name: f for f in recent}
            previous_dict = {f.feature_name: f for f in previous}

            # Check for significant changes
            for feature_name, recent_fi in recent_dict.items():
                if feature_name in previous_dict:
                    prev_fi = previous_dict[feature_name]

                    # Check rank change
                    rank_change = abs(recent_fi.rank - prev_fi.rank)

                    # Check importance change
                    if prev_fi.importance_score > 0:
                        importance_change = abs(
                            (recent_fi.importance_score - prev_fi.importance_score) /
                            prev_fi.importance_score
                        )
                    else:
                        importance_change = 1.0

                    if importance_change > FEATURE_IMPORTANCE_CHANGE_THRESHOLD or rank_change > 5:
                        self.logger.warning(
                            f"Significant feature importance change for {feature_name} in {model_id}: "  # noqa: E501
                            f"Rank {prev_fi.rank} -> {recent_fi.rank}, "
                            f"Importance {prev_fi.importance_score:.3f} -> {recent_fi.importance_score:.3f}"  # noqa: E501
                        )

        except Exception as e:
            self.logger.error("Error detecting feature changes: %s", e)

    def _calculate_average_metrics(self, metrics_list: list[ModelPerformanceMetrics]) -> dict[str, float]:  # noqa: E501
        """Calculate average metrics from a list."""
        if not metrics_list:
            return {}

        avg_metrics = {}

        # Define metrics to average
        metric_names = ['accuracy', 'precision', 'recall', 'f1_score', 'auc_roc', 'mse', 'mae', 'r2']  # noqa: E501

        for metric in metric_names:
            values = [getattr(m, metric) for m in metrics_list if getattr(m, metric) is not None]
            if values:
                avg_metrics[metric] = np.mean(values)

        return avg_metrics

    def _calculate_stability(self, metrics_list: list[ModelPerformanceMetrics]) -> float:
        """Calculate stability score (lower std dev = higher stability)."""
        if not metrics_list:
            return 0.0

        # Use primary metric
        if metrics_list[0].model_type == ModelType.CLASSIFICATION:
            values = [m.f1_score for m in metrics_list if m.f1_score is not None]
        else:
            values = [m.r2 for m in metrics_list if m.r2 is not None]

        if len(values) < 2:
            return 1.0

        # Convert std dev to stability score (0-1, higher is better)
        std_dev = np.std(values)
        stability = 1.0 / (1.0 + std_dev * 10)  # Scale factor

        return stability

    def _calculate_trend(self, metrics_list: list[ModelPerformanceMetrics]) -> str:
        """Calculate performance trend."""
        if len(metrics_list) < 3:
            return 'stable'

        # Use primary metric
        if metrics_list[0].model_type == ModelType.CLASSIFICATION:
            values = [m.f1_score for m in metrics_list if m.f1_score is not None]
        else:
            values = [m.r2 for m in metrics_list if m.r2 is not None]

        if len(values) < 3:
            return 'stable'

        # Simple linear regression for trend
        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)

        if slope > 0.001:
            return 'improving'
        elif slope < -0.001:
            return 'degrading'
        else:
            return 'stable'

    def _analyze_performance_trends(self, history: list[ModelPerformanceMetrics]) -> dict[str, PerformanceTrend]:  # noqa: E501
        """Analyze performance trends for various metrics."""
        trends = {}

        if len(history) < 7:
            return trends

        # Analyze each metric
        metrics_to_analyze = ['accuracy', 'f1_score', 'precision', 'recall']

        for metric_name in metrics_to_analyze:
            values = [getattr(m, metric_name) for m in history if getattr(m, metric_name) is not None]  # noqa: E501

            if len(values) < 7:
                continue

            # Calculate trend
            x = np.arange(len(values))
            slope, intercept = np.polyfit(x, values, 1)

            # Determine direction
            if slope > 0.001:
                direction = 'improving'
            elif slope < -0.001:
                direction = 'degrading'
            else:
                direction = 'stable'

            # Simple forecast
            forecast_7 = intercept + slope * (len(values) + 7)
            forecast_30 = intercept + slope * (len(values) + 30)

            # Calculate significance (R-squared)
            y_pred = slope * x + intercept
            ss_res = np.sum((values - y_pred) ** 2)
            ss_tot = np.sum((values - np.mean(values)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            trends[metric_name] = PerformanceTrend(
                model_id=history[0].model_id,
                metric=metric_name,
                trend_direction=direction,
                trend_slope=slope,
                trend_significance=r_squared,
                forecast_7_days=max(0, min(1, forecast_7)),  # Bound between 0 and 1
                forecast_30_days=max(0, min(1, forecast_30))
            )

        return trends

    def _format_feature_importance(self, feature_history: list[dict]) -> dict[str, Any]:
        """Format feature importance history for reporting."""
        if not feature_history:
            return {}

        # Get latest
        latest = feature_history[-1]

        # Track changes over time
        feature_trends = defaultdict(list)

        for entry in feature_history[-10:]:  # Last 10 entries
            for fi in entry['features']:
                feature_trends[fi.feature_name].append({
                    'timestamp': entry['timestamp'],
                    'rank': fi.rank,
                    'importance': fi.importance_score
                })

        return {
            'latest': [asdict(f) for f in latest['features'][:10]],  # Top 10
            'trends': dict(feature_trends)
        }

    def _generate_model_specific_recommendations(self, model_id: str,
                                               perf_history: list[ModelPerformanceMetrics],
                                               drift_reports: list[ModelDriftReport]) -> list[str]:
        """Generate recommendations for a specific model."""
        recommendations = []

        # Check performance
        if perf_history:
            latest = perf_history[-1]

            if latest.model_type == ModelType.CLASSIFICATION:
                if latest.accuracy and latest.accuracy < ACCURACY_THRESHOLD:
                    recommendations.append(
                        f"Accuracy ({latest.accuracy:.2f}) below threshold ({ACCURACY_THRESHOLD}). "
                        "Consider feature engineering or model architecture changes."
                    )

                if latest.f1_score and latest.f1_score < F1_THRESHOLD:
                    recommendations.append(
                        f"F1 score ({latest.f1_score:.2f}) below threshold ({F1_THRESHOLD}). "
                        "Check class imbalance or adjust classification threshold."
                    )

        # Check for drift
        if drift_reports:
            recent_drift = [d for d in drift_reports if (datetime.now(timezone.utc) - d.detection_date).days < 7]  # noqa: E501
            if recent_drift:
                recommendations.append(
                    f"Recent drift detected ({recent_drift[0].drift_type.value}). "
                    "Immediate retraining recommended."
                )

        # Check stability
        if len(perf_history) > 10:
            stability = self._calculate_stability(perf_history[-10:])
            if stability < 0.7:
                recommendations.append(
                    "Model showing high variance in performance. "
                    "Consider ensemble methods or regularization."
                )

        return recommendations

    def _generate_ml_summary(self, model_reports: list[dict]) -> MLPerformanceSummary:
        """Generate overall ML performance summary."""
        total_models = len(model_reports)

        # Active models (with recent data)
        active_models = sum(
            1 for report in model_reports
            if report.get('performance_history')
        )

        # Models in production (placeholder logic)
        models_in_production = [
            report['model_id'] for report in model_reports
            if report.get('latest_performance')
        ]

        # Average accuracy
        accuracies = []
        for report in model_reports:
            if report.get('latest_performance', {}).get('accuracy'):
                accuracies.append(report['latest_performance']['accuracy'])

        avg_accuracy = np.mean(accuracies) if accuracies else 0.0

        # Models with drift
        models_with_drift = list({
            report['model_id'] for report in model_reports
            if report.get('drift_reports')
        })

        # Recent A/B tests
        all_ab_tests = []
        for report in model_reports:
            all_ab_tests.extend(report.get('ab_tests', []))

        recent_ab_tests = sorted(
            all_ab_tests,
            key=lambda x: x.get('start_date', ''),
            reverse=True
        )[:5]

        # Feature importance changes
        feature_changes = {}
        for report in model_reports:
            if report.get('feature_importance', {}).get('trends'):
                feature_changes[report['model_id']] = list(
                    report['feature_importance']['trends'].keys()
                )[:5]

        # Overall recommendations
        recommendations = []

        if avg_accuracy < 0.7:
            recommendations.append(
                "Overall model accuracy below 70%. Review data quality and feature engineering."
            )

        if len(models_with_drift) > total_models * 0.3:
            recommendations.append(
                f"{len(models_with_drift)} models showing drift. "
                "Consider implementing automated retraining pipeline."
            )

        if active_models < total_models * 0.8:
            recommendations.append(
                "Several models inactive. Review model lifecycle management."
            )

        return MLPerformanceSummary(
            total_models=total_models,
            active_models=active_models,
            models_in_production=models_in_production,
            average_accuracy=avg_accuracy,
            models_with_drift=models_with_drift,
            recent_ab_tests=[ABTestResult(**test) for test in recent_ab_tests],
            feature_importance_changes=feature_changes,
            recommendations=recommendations
        )

    def _generate_comparison_charts(self, comparison_df: pd.DataFrame) -> dict[str, Any]:
        """Generate model comparison charts."""
        charts = {}

        try:
            # Model performance radar chart
            metrics = ['avg_accuracy', 'avg_f1', 'stability']

            fig_radar = go.Figure()

            for _, row in comparison_df.iterrows():
                values = [row.get(m, 0) for m in metrics]
                fig_radar.add_trace(go.Scatterpolar(
                    r=values,
                    theta=metrics,
                    fill='toself',
                    name=row['model_id']
                ))

            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 1]
                    )
                ),
                title='Model Performance Comparison',
                showlegend=True
            )

            charts['performance_radar'] = fig_radar.to_json()

            # Performance over time (if we have history)
            # This would show line charts of metrics over time

        except Exception as e:
            self.logger.error("Error generating comparison charts: %s", e)

        return charts

    def _generate_model_recommendations(self, comparison_df: pd.DataFrame,
                                      rankings: dict[str, int]) -> list[str]:
        """Generate recommendations based on model comparison."""
        recommendations = []

        # Find underperforming models
        low_performers = comparison_df[comparison_df['avg_f1'] < 0.6]['model_id'].tolist()
        if low_performers:
            recommendations.append(
                f"Models {', '.join(low_performers)} showing poor performance. "
                "Consider deprecation or significant improvements."
            )

        # Check for similar models
        # This would require more sophisticated similarity analysis

        # Suggest best model for production
        if rankings:
            best_model = min(rankings, key=rankings.get)
            recommendations.append(
                f"Model {best_model} shows best overall performance. "
                "Consider promoting to primary production model."
            )

        return recommendations

    def _generate_ml_charts(self, model_reports: list[dict]) -> dict[str, Any]:
        """Generate ML performance charts."""
        charts = {}

        try:
            # Overall accuracy distribution
            accuracies = []
            model_names = []

            for report in model_reports:
                if report.get('latest_performance', {}).get('accuracy'):
                    accuracies.append(report['latest_performance']['accuracy'])
                    model_names.append(report['model_id'])

            if accuracies:
                fig_acc = go.Figure(data=[go.Bar(
                    x=model_names,
                    y=accuracies,
                    text=[f'{a:.2f}' for a in accuracies],
                    textposition='auto'
                )])

                fig_acc.update_layout(
                    title='Model Accuracy Comparison',
                    xaxis_title='Model',
                    yaxis_title='Accuracy',
                    yaxis=dict(range=[0, 1])
                )

                charts['accuracy_comparison'] = fig_acc.to_json()

            # Drift timeline
            drift_data = []
            for report in model_reports:
                for drift in report.get('drift_reports', []):
                    drift_data.append({
                        'model': report['model_id'],
                        'date': drift['detection_date'],
                        'type': drift['drift_type'],
                        'severity': drift['severity']
                    })

            if drift_data:
                df_drift = pd.DataFrame(drift_data)

                fig_drift = px.scatter(
                    df_drift,
                    x='date',
                    y='model',
                    color='severity',
                    symbol='type',
                    title='Model Drift Detection Timeline'
                )

                charts['drift_timeline'] = fig_drift.to_json()

        except Exception as e:
            self.logger.error("Error generating ML charts: %s", e)

        return charts

    def _empty_comparison_report(self, model_ids: list[str]) -> ModelComparisonReport:
        """Return empty comparison report."""
        return ModelComparisonReport(
            models=model_ids,
            comparison_date=datetime.now(timezone.utc),
            best_model=None,
            metrics_comparison=pd.DataFrame(),
            ranking={},
            recommendations=["Insufficient data for model comparison"],
            visualizations={}
        )

    def _export_html_ml_report(self, report_data: dict[str, Any], output_path: str) -> bool:
        """Export ML report as HTML."""
        try:
            # HTML template
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>ML Performance Report - {report_date}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
                    .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                    h1, h2, h3 {{ color: #333; }}
                    .summary {{ background: #e8f4f8; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                    .metric-card {{ display: inline-block; background: white; padding: 15px; margin: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .metric-value {{ font-size: 32px; font-weight: bold; color: #0066cc; }}
                    .metric-label {{ font-size: 14px; color: #666; margin-top: 5px; }}
                    .model-section {{ background: #f9f9f9; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 4px solid #0066cc; }}
                    .performance-good {{ color: #28a745; }}
                    .performance-warning {{ color: #ffc107; }}
                    .performance-bad {{ color: #dc3545; }}
                    .drift-alert {{ background: #fff3cd; padding: 10px; border-radius: 4px; margin: 10px 0; border-left: 4px solid #ffc107; }}
                    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                    th {{ background-color: #f2f2f2; font-weight: bold; }}
                    .recommendation {{ background: #d4edda; padding: 15px; margin: 10px 0; border-radius: 4px; border-left: 4px solid #28a745; }}
                    .chart-container {{ margin: 20px 0; text-align: center; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Machine Learning Performance Report</h1>
                    <p>Generated: {report_date}</p>

                    <div class="summary">
                        <h2>Executive Summary</h2>
                        <div class="metric-card">
                            <div class="metric-value">{total_models}</div>
                            <div class="metric-label">Total Models</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{active_models}</div>
                            <div class="metric-label">Active Models</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{avg_accuracy:.1%}</div>
                            <div class="metric-label">Average Accuracy</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-value">{models_with_drift}</div>
                            <div class="metric-label">Models with Drift</div>
                        </div>
                    </div>

                    <h2>Overall Recommendations</h2>
                    {overall_recommendations}

                    <h2>Model Performance Details</h2>
                    {model_details}

                    <h2>Recent A/B Tests</h2>
                    {ab_tests}

                    <div class="chart-container">
                        <h3>Performance Visualizations</h3>
                        <p>Interactive charts are available in the full dashboard.</p>
                    </div>
                </div>
            </body>
            </html>
            """  # noqa: E501

            # Extract summary data
            summary = report_data['summary']

            # Format recommendations
            overall_recommendations = '\n'.join([
                f'<div class="recommendation">{rec}</div>'
                for rec in summary.get('recommendations', [])
            ])

            # Format model details
            model_details = self._format_model_details_html(report_data.get('model_reports', []))

            # Format A/B tests
            ab_tests = self._format_ab_tests_html(summary.get('recent_ab_tests', []))

            # Fill template
            html_content = html_template.format(
                report_date=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                total_models=summary['total_models'],
                active_models=summary['active_models'],
                avg_accuracy=summary['average_accuracy'],
                models_with_drift=len(summary['models_with_drift']),
                overall_recommendations=overall_recommendations,
                model_details=model_details,
                ab_tests=ab_tests
            )

            # Write to file
            with open(output_path, 'w') as f:
                f.write(html_content)

            self.logger.info("ML report exported to %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Error exporting HTML report: %s", e)
            return False

    def _export_pdf_ml_report(self, report_data: dict[str, Any], output_path: str) -> bool:
        """Export ML report as PDF."""
        self.logger.warning("PDF export not yet implemented")
        return False

    def _export_json_ml_report(self, report_data: dict[str, Any], output_path: str) -> bool:
        """Export ML report as JSON."""
        try:
            with open(output_path, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

            self.logger.info("JSON report exported to %s", output_path)
            return True

        except Exception as e:
            self.logger.error("Error exporting JSON report: %s", e)
            return False

    def _format_model_details_html(self, model_reports: list[dict]) -> str:
        """Format model details as HTML."""
        if not model_reports:
            return "<p>No model data available.</p>"

        html = ""

        for report in model_reports:
            model_id = report['model_id']
            latest_perf = report.get('latest_performance', {})

            # Determine performance class
            accuracy = latest_perf.get('accuracy', 0)
            if accuracy >= 0.8:
                perf_class = 'performance-good'
            elif accuracy >= 0.65:
                perf_class = 'performance-warning'
            else:
                perf_class = 'performance-bad'

            html += f"""
            <div class="model-section">
                <h3>{model_id}</h3>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Trend</th>
                    </tr>
                    <tr>
                        <td>Accuracy</td>
                        <td class="{perf_class}">{accuracy:.3f}</td>
                        <td>{report.get('trends', {}).get('accuracy', {}).get('trend_direction', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>F1 Score</td>
                        <td>{latest_perf.get('f1_score', 'N/A'):.3f if latest_perf.get('f1_score') else 'N/A'}</td>
                        <td>{report.get('trends', {}).get('f1_score', {}).get('trend_direction', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td>Sample Size</td>
                        <td>{latest_perf.get('sample_size', 0)}</td>
                        <td>-</td>
                    </tr>
                </table>
            """  # noqa: E501

            # Add drift alerts
            drift_reports = report.get('drift_reports', [])
            if drift_reports:
                html += '<div class="drift-alert"><strong>⚠️ Drift Detected:</strong> '
                for drift in drift_reports[:3]:  # Show max 3
                    html += f"{drift['drift_type']} (p={drift['p_value']:.3f}) "
                html += '</div>'

            # Add recommendations
            recommendations = report.get('recommendations', [])
            if recommendations:
                html += '<h4>Recommendations:</h4><ul>'
                for rec in recommendations[:3]:  # Show max 3
                    html += f'<li>{rec}</li>'
                html += '</ul>'

            html += '</div>'

        return html

    def _format_ab_tests_html(self, ab_tests: list[dict]) -> str:
        """Format A/B test results as HTML."""
        if not ab_tests:
            return "<p>No recent A/B tests.</p>"

        html = """
        <table>
            <tr>
                <th>Test ID</th>
                <th>Model A</th>
                <th>Model B</th>
                <th>Metric</th>
                <th>Winner</th>
                <th>Improvement</th>
                <th>p-value</th>
                <th>Status</th>
            </tr>
        """

        for test in ab_tests:
            winner = test.get('winner', 'N/A')
            improvement = test.get('improvement', 0)

            # Format improvement
            if improvement:
                improvement_str = f"{improvement*100:+.1f}%"
            else:
                improvement_str = "-"

            html += f"""
            <tr>
                <td>{test['test_id'][:20]}...</td>
                <td>{test['model_a_id']}</td>
                <td>{test['model_b_id']}</td>
                <td>{test['metric_tested']}</td>
                <td><strong>{winner}</strong></td>
                <td>{improvement_str}</td>
                <td>{test['p_value']:.3f}</td>
                <td>{test['status']}</td>
            </tr>
            """

        html += "</table>"
        return html

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def get_ml_performance_report() -> MLPerformanceReport:
    """
    Get singleton instance of MLPerformanceReport.

    Returns:
        MLPerformanceReport instance
    """
    global _ml_report_instance
    if _ml_report_instance is None:
        _ml_report_instance = MLPerformanceReport()
    return _ml_report_instance

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
_ml_report_instance: MLPerformanceReport | None = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Example usage
    ml_report = get_ml_performance_report()

    # Track performance for a model
    model_id = "price_predictor_v2"
    performance = ml_report.track_model_performance(model_id)

    if performance:
        pass

    # Check for drift
    drift_report = ml_report.detect_model_drift(model_id)

    if drift_report:
        pass

    # Generate report
    success = ml_report.generate_ml_report("ml_performance_report.html", format='html')

    if success:
        pass
