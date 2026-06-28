#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovX_Agents
Module: TradovX12_SystemHealthAgent.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import threading
import os
from datetime import datetime, timedelta, UTC
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
import platform
import numpy as np

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.info("Warning: Ollama not installed. AI features will be limited.")

# ==============================================================================
# CONSTANTS
# ==============================================================================

# System components
class SystemComponent(Enum):
    """System components to monitor."""
    DATA_FEED = "DATA_FEED"
    TRADING_ENGINE = "TRADING_ENGINE"
    RISK_MANAGER = "RISK_MANAGER"
    EXECUTION = "EXECUTION"
    DATABASE = "DATABASE"
    ML_MODELS = "ML_MODELS"
    API_GATEWAY = "API_GATEWAY"
    MESSAGING = "MESSAGING"
    OLLAMA = "OLLAMA"
    AGENTS = "AGENTS"

# Health status levels
class HealthStatus(Enum):
    """System health status levels."""
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    FAILED = "FAILED"

# Metric types
class MetricType(Enum):
    """Types of system metrics."""
    CPU_USAGE = "CPU_USAGE"
    MEMORY_USAGE = "MEMORY_USAGE"
    DISK_USAGE = "DISK_USAGE"
    NETWORK_IO = "NETWORK_IO"
    LATENCY = "LATENCY"
    ERROR_RATE = "ERROR_RATE"
    THROUGHPUT = "THROUGHPUT"
    QUEUE_DEPTH = "QUEUE_DEPTH"

# Thresholds for health monitoring
HEALTH_THRESHOLDS = {
    'cpu_warning': 70,          # %
    'cpu_critical': 90,         # %
    'memory_warning': 75,       # %
    'memory_critical': 90,      # %
    'disk_warning': 80,         # %
    'disk_critical': 95,        # %
    'latency_warning': 1000,    # ms
    'latency_critical': 5000,   # ms
    'error_rate_warning': 0.01, # 1%
    'error_rate_critical': 0.05 # 5%
}

# Component dependencies
COMPONENT_DEPENDENCIES = {
    SystemComponent.TRADING_ENGINE: [SystemComponent.DATA_FEED, SystemComponent.DATABASE],
    SystemComponent.RISK_MANAGER: [SystemComponent.DATABASE, SystemComponent.ML_MODELS],
    SystemComponent.EXECUTION: [SystemComponent.API_GATEWAY, SystemComponent.TRADING_ENGINE],
    SystemComponent.ML_MODELS: [SystemComponent.DATABASE],
    SystemComponent.AGENTS: [SystemComponent.OLLAMA, SystemComponent.DATABASE]
}

# Default configuration
DEFAULT_CONFIG = {
    'monitoring_interval': 60,      # seconds
    'metric_retention': 24 * 60,    # minutes (24 hours)
    'anomaly_lookback': 60,         # minutes
    'prediction_horizon': 30,       # minutes
    'alert_cooldown': 300          # seconds (5 minutes)
}

# Model configuration
DEFAULT_MODEL = os.getenv("OLLAMA_FAST_MODEL", "gemma4:e4b")
DEFAULT_TEMPERATURE = 0.3

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class SystemMetric:
    """System metric data point."""
    component: SystemComponent
    metric_type: MetricType
    timestamp: datetime
    value: float
    unit: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ComponentHealth:
    """Component health status."""
    component: SystemComponent
    status: HealthStatus
    health_score: float  # 0-100
    metrics: dict[MetricType, float]
    issues: list[str]
    dependencies_ok: bool
    last_check: datetime
    uptime_percentage: float

@dataclass
class SystemDiagnostic:
    """System diagnostic report."""
    timestamp: datetime
    overall_status: HealthStatus
    overall_health_score: float
    component_health: dict[SystemComponent, ComponentHealth]
    active_issues: list[dict[str, Any]]
    predictions: list[dict[str, Any]]
    recommendations: list[str]
    ai_analysis: dict[str, Any]

@dataclass
class HealthAlert:
    """System health alert."""
    timestamp: datetime
    component: SystemComponent
    severity: str  # 'low', 'medium', 'high', 'critical'
    title: str
    description: str
    metric_data: dict[str, Any]
    resolution_steps: list[str]
    auto_remediation_available: bool

@dataclass
class PerformancePrediction:
    """Performance prediction."""
    component: SystemComponent
    metric_type: MetricType
    prediction_time: datetime
    predicted_value: float
    confidence: float
    risk_level: str  # 'low', 'medium', 'high'
    recommended_action: str | None

# ==============================================================================
# SYSTEM HEALTH AGENT CLASS
# ==============================================================================

class TradovX12_SystemHealthAgent:
    """
    AI-Enhanced System Health Monitoring Agent.

    This agent monitors system health, predicts failures, and provides
    AI-driven diagnostics and remediation recommendations.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 temperature: float = DEFAULT_TEMPERATURE):
        """
        Initialize the System Health Agent.

        Args:
            model_name: Ollama model to use
            temperature: Temperature for AI responses
        """
        self.model_name = model_name
        self.temperature = temperature
        self.logger = self._setup_logger()
        self.config = DEFAULT_CONFIG.copy()

        # Initialize Ollama if available
        self.ollama_client = None
        if OLLAMA_AVAILABLE:
            try:
                ollama.list()  # Test connection
                self.ollama_client = ollama
                self.logger.info("Ollama connection established")
            except Exception as e:
                self.logger.error("Failed to connect to Ollama: %s", e)

        # Metric storage
        self.metrics_history = defaultdict(lambda: deque(maxlen=1440))  # 24h at 1min
        self.component_status = {}

        # Alert management
        self.active_alerts = []
        self.alert_history = deque(maxlen=1000)
        self.last_alert_time = {}

        # Performance baselines
        self.performance_baselines = defaultdict(dict)
        self.anomaly_detectors = {}

        # System info
        self.system_info = self._get_system_info()

    def _setup_logger(self) -> logging.Logger:
        """Set up module logger."""
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    # ==========================================================================
    # MAIN MONITORING METHODS
    # ==========================================================================

    async def monitor_system_health(self) -> SystemDiagnostic:
        """
        Monitor overall system health.

        Returns:
            SystemDiagnostic report
        """
        self.logger.info("Monitoring system health")

        try:
            # Collect metrics
            metrics = await self._collect_system_metrics()

            # Update history
            self._update_metrics_history(metrics)

            # Check component health
            component_health = {}
            for component in SystemComponent:
                health = await self._check_component_health(component)
                component_health[component] = health

            # Detect anomalies
            anomalies = self._detect_anomalies()

            # Generate predictions
            predictions = await self._predict_issues()

            # Determine overall status
            overall_status, overall_score = self._calculate_overall_health(component_health)

            # Get AI analysis
            ai_analysis = await self._get_ai_system_analysis(
                component_health, anomalies, predictions
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                component_health, anomalies, ai_analysis
            )

            # Create active issues list
            active_issues = self._compile_active_issues(component_health, anomalies)

            return SystemDiagnostic(
                timestamp=datetime.now(UTC),
                overall_status=overall_status,
                overall_health_score=overall_score,
                component_health=component_health,
                active_issues=active_issues,
                predictions=predictions,
                recommendations=recommendations,
                ai_analysis=ai_analysis
            )

        except Exception as e:
            self.logger.error("System health monitoring failed: %s", e)
            return self._create_error_diagnostic(str(e))

    async def check_component_status(self,
                                   component: SystemComponent) -> ComponentHealth:
        """
        Check specific component status.

        Args:
            component: Component to check

        Returns:
            ComponentHealth status
        """
        return await self._check_component_health(component)

    async def predict_failures(self,
                             horizon_minutes: int = 30) -> list[PerformancePrediction]:
        """
        Predict potential system failures.

        Args:
            horizon_minutes: Prediction horizon

        Returns:
            List of performance predictions
        """
        self.logger.info("Predicting failures for next %s minutes", horizon_minutes)

        predictions = []

        for component in SystemComponent:
            # Get component metrics history
            component_metrics = self._get_component_metrics(component)

            if not component_metrics:
                continue

            # Predict each metric type
            for metric_type in MetricType:
                prediction = await self._predict_metric(
                    component, metric_type, horizon_minutes
                )
                if prediction and prediction.risk_level in ['medium', 'high']:
                    predictions.append(prediction)

        # Sort by risk level
        predictions.sort(key=lambda p: ['low', 'medium', 'high'].index(p.risk_level),
                        reverse=True)

        return predictions

    async def auto_remediate(self, alert: HealthAlert) -> dict[str, Any]:
        """
        Attempt automatic remediation of issues.

        Args:
            alert: Health alert to remediate

        Returns:
            Remediation result
        """
        self.logger.info("Attempting auto-remediation for %s", alert.component.value)

        if not alert.auto_remediation_available:
            return {
                'success': False,
                'reason': 'No automatic remediation available'
            }

        try:
            # Component-specific remediation
            if alert.component == SystemComponent.DATABASE:
                result = await self._remediate_database(alert)
            elif alert.component == SystemComponent.ML_MODELS:
                result = await self._remediate_ml_models(alert)
            elif alert.component == SystemComponent.DATA_FEED:
                result = await self._remediate_data_feed(alert)
            else:
                result = await self._generic_remediation(alert)

            # Log remediation attempt
            self._log_remediation(alert, result)

            return result

        except Exception as e:
            self.logger.error("Auto-remediation failed: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

    # ==========================================================================
    # AI INTEGRATION METHODS
    # ==========================================================================

    async def _get_ai_system_analysis(self, component_health: dict[SystemComponent, ComponentHealth],  # noqa: E501
                                    anomalies: list[dict[str, Any]],
                                    predictions: list[dict[str, Any]]) -> dict[str, Any]:
        """Get AI analysis of system health."""
        if not self.ollama_client:
            return {'analysis': 'No AI available'}

        # Prepare health summary
        health_summary = {
            comp.value: {
                'status': health.status.value,
                'score': health.health_score,
                'issues': health.issues[:2]
            }
            for comp, health in component_health.items()
        }

        prompt = f"""Analyze this system health data:

Component Health:
{json.dumps(health_summary, indent=2)}

Detected Anomalies: {len(anomalies)}
{json.dumps(anomalies[:3], indent=2) if anomalies else 'None'}

Predictions:
{json.dumps([{'component': p.get('component'), 'risk': p.get('risk_level')}
            for p in predictions[:3]], indent=2)}

System Info:
- Platform: {self.system_info['platform']}
- CPU Count: {self.system_info['cpu_count']}
- Memory: {self.system_info['memory_gb']}GB

Provide a JSON response:
{{
    "system_assessment": "overall system health assessment",
    "critical_issues": ["issue1", "issue2"],
    "root_causes": ["likely root cause 1", "likely root cause 2"],
    "optimization_opportunities": ["opportunity1", "opportunity2"],
    "predicted_impact": "impact if issues not addressed",
    "priority_actions": ["action1", "action2"],
    "confidence": 0.0-1.0
}}"""

        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )

            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1

            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return {'analysis': 'Failed to parse AI response'}

        except Exception as e:
            self.logger.error("AI system analysis failed: %s", e)
            return {'error': str(e)}

    async def _predict_metric(self, component: SystemComponent,
                            metric_type: MetricType,
                            horizon_minutes: int) -> PerformancePrediction | None:
        """Predict future metric values using AI and statistics."""
        history = self._get_metric_history(component, metric_type)

        if len(history) < 10:
            return None

        # Statistical prediction
        values = [h['value'] for h in history[-30:]]
        trend = self._calculate_trend(values)

        # Simple linear projection
        predicted_value = values[-1] + trend * horizon_minutes

        # Get AI enhancement if available
        if self.ollama_client:
            ai_prediction = await self._get_ai_metric_prediction(
                component, metric_type, values, horizon_minutes
            )
            if ai_prediction:
                predicted_value = ai_prediction.get('predicted_value', predicted_value)
                confidence = ai_prediction.get('confidence', 0.5)
            else:
                confidence = 0.6
        else:
            confidence = 0.5

        # Determine risk level
        risk_level = self._assess_prediction_risk(metric_type, predicted_value)

        # Get recommended action
        action = self._get_recommended_action(component, metric_type, risk_level)

        return PerformancePrediction(
            component=component,
            metric_type=metric_type,
            prediction_time=datetime.now(UTC) + timedelta(minutes=horizon_minutes),
            predicted_value=predicted_value,
            confidence=confidence,
            risk_level=risk_level,
            recommended_action=action
        )

    async def _get_ai_metric_prediction(self, component: SystemComponent,
                                      metric_type: MetricType,
                                      values: list[float],
                                      horizon: int) -> dict[str, Any] | None:
        """Get AI prediction for metric."""
        if not self.ollama_client:
            return None

        prompt = f"""Predict future values for this system metric:

Component: {component.value}
Metric: {metric_type.value}
Recent Values (last 10): {values[-10:]}
Prediction Horizon: {horizon} minutes

Current trend: {'increasing' if values[-1] > values[-5] else 'decreasing'}
Average: {np.mean(values):.2f}
Std Dev: {np.std(values):.2f}

Consider:
- Typical patterns for this metric
- Time of day effects
- Component interactions

Provide a JSON response:
{{
    "predicted_value": float,
    "confidence": 0.0-1.0,
    "reasoning": "explanation",
    "risk_factors": ["factor1", "factor2"]
}}"""

        try:
            response = await asyncio.to_thread(
                self.ollama_client.generate,
                model=self.model_name,
                prompt=prompt,
                options={'temperature': self.temperature}
            )

            # Extract JSON from response
            text = response['response']
            start = text.find('{')
            end = text.rfind('}') + 1

            if start >= 0 and end > start:
                return json.loads(text[start:end])
            else:
                return None

        except Exception as e:
            self.logger.error("AI metric prediction failed: %s", e)
            return None

    # ==========================================================================
    # MONITORING METHODS
    # ==========================================================================

    async def _collect_system_metrics(self) -> list[SystemMetric]:
        """Collect current system metrics."""
        metrics = []

        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        metrics.append(SystemMetric(
            component=SystemComponent.TRADING_ENGINE,
            metric_type=MetricType.CPU_USAGE,
            timestamp=datetime.now(UTC),
            value=cpu_percent,
            unit='%'
        ))

        # Memory metrics
        memory = psutil.virtual_memory()
        metrics.append(SystemMetric(
            component=SystemComponent.TRADING_ENGINE,
            metric_type=MetricType.MEMORY_USAGE,
            timestamp=datetime.now(UTC),
            value=memory.percent,
            unit='%'
        ))

        # Disk metrics
        disk = psutil.disk_usage('/')
        metrics.append(SystemMetric(
            component=SystemComponent.DATABASE,
            metric_type=MetricType.DISK_USAGE,
            timestamp=datetime.now(UTC),
            value=disk.percent,
            unit='%'
        ))

        # Network I/O (simplified)
        net_io = psutil.net_io_counters()
        metrics.append(SystemMetric(
            component=SystemComponent.API_GATEWAY,
            metric_type=MetricType.NETWORK_IO,
            timestamp=datetime.now(UTC),
            value=net_io.bytes_sent + net_io.bytes_recv,
            unit='bytes',
            metadata={'sent': net_io.bytes_sent, 'recv': net_io.bytes_recv}
        ))

        # Component-specific metrics (simulated)
        await self._collect_component_metrics(metrics)

        return metrics

    async def _collect_component_metrics(self, metrics: list[SystemMetric]):
        """Collect component-specific metrics."""
        # Simulate component metrics
        components_metrics = {
            SystemComponent.DATA_FEED: {
                MetricType.LATENCY: np.random.normal(50, 10),
                MetricType.THROUGHPUT: np.random.normal(1000, 100)
            },
            SystemComponent.ML_MODELS: {
                MetricType.LATENCY: np.random.normal(100, 20),
                MetricType.ERROR_RATE: np.random.uniform(0, 0.02)
            },
            SystemComponent.EXECUTION: {
                MetricType.LATENCY: np.random.normal(20, 5),
                MetricType.QUEUE_DEPTH: np.random.poisson(5)
            }
        }

        for component, component_metrics in components_metrics.items():
            for metric_type, value in component_metrics.items():
                metrics.append(SystemMetric(
                    component=component,
                    metric_type=metric_type,
                    timestamp=datetime.now(UTC),
                    value=max(0, value),  # Ensure non-negative
                    unit=self._get_metric_unit(metric_type)
                ))

    async def _check_component_health(self, component: SystemComponent) -> ComponentHealth:
        """Check health of a specific component."""
        # Get recent metrics
        metrics = self._get_recent_component_metrics(component)

        # Calculate health score
        health_score, issues = self._calculate_component_health_score(component, metrics)

        # Determine status
        status = self._score_to_status(health_score)

        # Check dependencies
        deps_ok = self._check_dependencies(component)

        # Calculate uptime
        uptime = self._calculate_uptime(component)

        return ComponentHealth(
            component=component,
            status=status,
            health_score=health_score,
            metrics=metrics,
            issues=issues,
            dependencies_ok=deps_ok,
            last_check=datetime.now(UTC),
            uptime_percentage=uptime
        )

    def _calculate_component_health_score(self, component: SystemComponent,
                                        metrics: dict[MetricType, float]) -> tuple[float, list[str]]:  # noqa: E501
        """Calculate health score for component."""
        issues = []
        scores = []

        # CPU check
        if MetricType.CPU_USAGE in metrics:
            cpu = metrics[MetricType.CPU_USAGE]
            if cpu > HEALTH_THRESHOLDS['cpu_critical']:
                scores.append(20)
                issues.append(f"Critical CPU usage: {cpu:.1f}%")
            elif cpu > HEALTH_THRESHOLDS['cpu_warning']:
                scores.append(60)
                issues.append(f"High CPU usage: {cpu:.1f}%")
            else:
                scores.append(100)

        # Memory check
        if MetricType.MEMORY_USAGE in metrics:
            memory = metrics[MetricType.MEMORY_USAGE]
            if memory > HEALTH_THRESHOLDS['memory_critical']:
                scores.append(20)
                issues.append(f"Critical memory usage: {memory:.1f}%")
            elif memory > HEALTH_THRESHOLDS['memory_warning']:
                scores.append(60)
                issues.append(f"High memory usage: {memory:.1f}%")
            else:
                scores.append(100)

        # Latency check
        if MetricType.LATENCY in metrics:
            latency = metrics[MetricType.LATENCY]
            if latency > HEALTH_THRESHOLDS['latency_critical']:
                scores.append(20)
                issues.append(f"Critical latency: {latency:.0f}ms")
            elif latency > HEALTH_THRESHOLDS['latency_warning']:
                scores.append(60)
                issues.append(f"High latency: {latency:.0f}ms")
            else:
                scores.append(100)

        # Error rate check
        if MetricType.ERROR_RATE in metrics:
            error_rate = metrics[MetricType.ERROR_RATE]
            if error_rate > HEALTH_THRESHOLDS['error_rate_critical']:
                scores.append(20)
                issues.append(f"Critical error rate: {error_rate:.1%}")
            elif error_rate > HEALTH_THRESHOLDS['error_rate_warning']:
                scores.append(60)
                issues.append(f"High error rate: {error_rate:.1%}")
            else:
                scores.append(100)

        # Calculate overall score
        health_score = np.mean(scores) if scores else 100

        return health_score, issues

    # ==========================================================================
    # ANOMALY DETECTION METHODS
    # ==========================================================================

    def _detect_anomalies(self) -> list[dict[str, Any]]:
        """Detect anomalies in system metrics."""
        anomalies = []

        for component in SystemComponent:
            for metric_type in MetricType:
                history = self._get_metric_history(component, metric_type)

                if len(history) < 20:
                    continue

                # Statistical anomaly detection
                values = [h['value'] for h in history]
                mean = np.mean(values[:-5])  # Exclude recent for baseline
                std = np.std(values[:-5])

                if std > 0:
                    recent_values = values[-5:]
                    for i, value in enumerate(recent_values):
                        z_score = abs((value - mean) / std)

                        if z_score > 3:  # 3 sigma rule
                            anomalies.append({
                                'component': component.value,
                                'metric': metric_type.value,
                                'value': value,
                                'z_score': z_score,
                                'baseline_mean': mean,
                                'timestamp': history[-(5-i)]['timestamp'].isoformat()
                            })

        return anomalies

    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================

    def _get_system_info(self) -> dict[str, Any]:
        """Get system information."""
        return {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'processor': platform.processor(),
            'cpu_count': psutil.cpu_count(),
            'memory_gb': round(psutil.virtual_memory().total / (1024**3), 1)
        }

    def _update_metrics_history(self, metrics: list[SystemMetric]):
        """Update metrics history."""
        for metric in metrics:
            key = f"{metric.component.value}_{metric.metric_type.value}"
            self.metrics_history[key].append({
                'timestamp': metric.timestamp,
                'value': metric.value,
                'metadata': metric.metadata
            })

    def _get_metric_history(self, component: SystemComponent,
                          metric_type: MetricType) -> list[dict[str, Any]]:
        """Get metric history for component."""
        key = f"{component.value}_{metric_type.value}"
        return list(self.metrics_history.get(key, []))

    def _get_recent_component_metrics(self, component: SystemComponent) -> dict[MetricType, float]:
        """Get recent metrics for component."""
        metrics = {}

        for metric_type in MetricType:
            history = self._get_metric_history(component, metric_type)
            if history:
                metrics[metric_type] = history[-1]['value']

        return metrics

    def _get_component_metrics(self, component: SystemComponent) -> dict[str, list[float]]:
        """Get all metrics for component."""
        metrics = {}

        for metric_type in MetricType:
            history = self._get_metric_history(component, metric_type)
            if history:
                metrics[metric_type.value] = [h['value'] for h in history]

        return metrics

    def _calculate_overall_health(self,
                                component_health: dict[SystemComponent, ComponentHealth]) -> tuple[HealthStatus, float]:  # noqa: E501
        """Calculate overall system health."""
        if not component_health:
            return HealthStatus.FAILED, 0.0

        # Get all health scores
        scores = [h.health_score for h in component_health.values()]
        overall_score = np.mean(scores)

        # Check for critical components
        critical_components = [SystemComponent.TRADING_ENGINE, SystemComponent.RISK_MANAGER]
        critical_scores = [component_health[c].health_score
                          for c in critical_components
                          if c in component_health]

        # If any critical component is failing, overall status is critical
        if any(score < 50 for score in critical_scores):
            return HealthStatus.CRITICAL, overall_score

        # Determine status based on overall score
        return self._score_to_status(overall_score), overall_score

    def _score_to_status(self, score: float) -> HealthStatus:
        """Convert health score to status."""
        if score >= 90:
            return HealthStatus.HEALTHY
        elif score >= 70:
            return HealthStatus.WARNING
        elif score >= 50:
            return HealthStatus.DEGRADED
        elif score >= 20:
            return HealthStatus.CRITICAL
        else:
            return HealthStatus.FAILED

    def _check_dependencies(self, component: SystemComponent) -> bool:
        """Check if component dependencies are healthy."""
        dependencies = COMPONENT_DEPENDENCIES.get(component, [])

        for dep in dependencies:
            dep_health = self.component_status.get(dep)
            if dep_health and dep_health.status in [HealthStatus.CRITICAL, HealthStatus.FAILED]:
                return False

        return True

    def _calculate_uptime(self, component: SystemComponent) -> float:
        """Calculate component uptime percentage."""
        # Simplified: based on recent health checks
        history_key = f"{component.value}_health"
        history = self.metrics_history.get(history_key, [])

        if not history:
            return 100.0

        # Count healthy periods
        healthy_count = sum(1 for h in history if h.get('status') != 'FAILED')
        return (healthy_count / len(history)) * 100 if history else 100.0

    def _compile_active_issues(self, component_health: dict[SystemComponent, ComponentHealth],
                             anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Compile list of active issues."""
        issues = []

        # Component issues
        for component, health in component_health.items():
            if health.issues:
                for issue in health.issues:
                    issues.append({
                        'type': 'component_health',
                        'component': component.value,
                        'severity': self._issue_severity(health.status),
                        'description': issue,
                        'timestamp': health.last_check.isoformat()
                    })

        # Anomaly issues
        for anomaly in anomalies[:5]:  # Top 5 anomalies
            issues.append({
                'type': 'anomaly',
                'component': anomaly['component'],
                'severity': 'medium' if anomaly['z_score'] < 4 else 'high',
                'description': f"Anomaly in {anomaly['metric']}: {anomaly['value']:.2f}",
                'timestamp': anomaly['timestamp']
            })

        return issues

    def _issue_severity(self, status: HealthStatus) -> str:
        """Get issue severity from health status."""
        severity_map = {
            HealthStatus.HEALTHY: 'low',
            HealthStatus.WARNING: 'medium',
            HealthStatus.DEGRADED: 'high',
            HealthStatus.CRITICAL: 'critical',
            HealthStatus.FAILED: 'critical'
        }
        return severity_map.get(status, 'medium')

    def _generate_recommendations(self, component_health: dict[SystemComponent, ComponentHealth],
                                anomalies: list[dict[str, Any]],
                                ai_analysis: dict[str, Any]) -> list[str]:
        """Generate system recommendations."""
        recommendations = []

        # Component-based recommendations
        for component, health in component_health.items():
            if health.status in [HealthStatus.CRITICAL, HealthStatus.FAILED]:
                recommendations.append(f"Immediate attention required for {component.value}")
            elif health.status == HealthStatus.DEGRADED:
                recommendations.append(f"Monitor and optimize {component.value}")

        # Resource-based recommendations
        cpu_issues = any('CPU' in issue for health in component_health.values()
                        for issue in health.issues)
        if cpu_issues:
            recommendations.append("Consider scaling compute resources or optimizing algorithms")

        memory_issues = any('memory' in issue.lower() for health in component_health.values()
                           for issue in health.issues)
        if memory_issues:
            recommendations.append("Review memory usage patterns and consider optimization")

        # AI recommendations
        ai_priority_actions = ai_analysis.get('priority_actions', [])
        recommendations.extend(ai_priority_actions[:2])

        return recommendations[:5]  # Top 5 recommendations

    def _calculate_trend(self, values: list[float]) -> float:
        """Calculate trend from values."""
        if len(values) < 2:
            return 0.0

        # Simple linear trend
        x = list(range(len(values)))
        n = len(x)

        if n < 2:
            return 0.0

        # Calculate slope
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(i * v for i, v in enumerate(values))
        sum_x2 = sum(i**2 for i in x)

        denominator = n * sum_x2 - sum_x**2
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope

    def _assess_prediction_risk(self, metric_type: MetricType,
                              predicted_value: float) -> str:
        """Assess risk level of prediction."""
        if metric_type == MetricType.CPU_USAGE:
            if predicted_value > HEALTH_THRESHOLDS['cpu_critical']:
                return 'high'
            elif predicted_value > HEALTH_THRESHOLDS['cpu_warning']:
                return 'medium'
        elif metric_type == MetricType.MEMORY_USAGE:
            if predicted_value > HEALTH_THRESHOLDS['memory_critical']:
                return 'high'
            elif predicted_value > HEALTH_THRESHOLDS['memory_warning']:
                return 'medium'
        elif metric_type == MetricType.ERROR_RATE:
            if predicted_value > HEALTH_THRESHOLDS['error_rate_critical']:
                return 'high'
            elif predicted_value > HEALTH_THRESHOLDS['error_rate_warning']:
                return 'medium'

        return 'low'

    def _get_recommended_action(self, component: SystemComponent,
                               metric_type: MetricType,
                               risk_level: str) -> str | None:
        """Get recommended action for prediction."""
        if risk_level == 'low':
            return None

        actions = {
            (SystemComponent.TRADING_ENGINE, MetricType.CPU_USAGE):
                "Scale trading engine resources or optimize algorithms",
            (SystemComponent.DATABASE, MetricType.DISK_USAGE):
                "Archive old data or expand storage capacity",
            (SystemComponent.ML_MODELS, MetricType.MEMORY_USAGE):
                "Optimize model memory usage or increase allocation",
            (SystemComponent.DATA_FEED, MetricType.LATENCY):
                "Check network connectivity and data provider status"
        }

        return actions.get((component, metric_type),
                          f"Monitor {component.value} {metric_type.value}")

    def _get_metric_unit(self, metric_type: MetricType) -> str:
        """Get unit for metric type."""
        units = {
            MetricType.CPU_USAGE: '%',
            MetricType.MEMORY_USAGE: '%',
            MetricType.DISK_USAGE: '%',
            MetricType.NETWORK_IO: 'bytes',
            MetricType.LATENCY: 'ms',
            MetricType.ERROR_RATE: 'ratio',
            MetricType.THROUGHPUT: 'ops/s',
            MetricType.QUEUE_DEPTH: 'count'
        }
        return units.get(metric_type, '')

    async def _remediate_database(self, alert: HealthAlert) -> dict[str, Any]:
        """Database-specific remediation."""
        # Simulated remediation
        await asyncio.sleep(1)
        return {
            'success': True,
            'action': 'Cleared query cache and optimized indexes',
            'duration': 1.2
        }

    async def _remediate_ml_models(self, alert: HealthAlert) -> dict[str, Any]:
        """ML model remediation."""
        # Simulated remediation
        await asyncio.sleep(0.5)
        return {
            'success': True,
            'action': 'Reloaded model weights and cleared prediction cache',
            'duration': 0.5
        }

    async def _remediate_data_feed(self, alert: HealthAlert) -> dict[str, Any]:
        """Data feed remediation."""
        # Simulated remediation
        await asyncio.sleep(0.8)
        return {
            'success': True,
            'action': 'Reconnected to data provider and synchronized feed',
            'duration': 0.8
        }

    async def _generic_remediation(self, alert: HealthAlert) -> dict[str, Any]:
        """Generic remediation."""
        # Simulated remediation
        await asyncio.sleep(0.5)
        return {
            'success': True,
            'action': f'Restarted {alert.component.value} component',
            'duration': 0.5
        }

    def _log_remediation(self, alert: HealthAlert, result: dict[str, Any]):
        """Log remediation attempt."""
        self.logger.info(f"Remediation for {alert.component.value}: "
                        f"{'Success' if result.get('success') else 'Failed'} - "
                        f"{result.get('action', 'Unknown action')}")

    def _create_error_diagnostic(self, error: str) -> SystemDiagnostic:
        """Create diagnostic report for error case."""
        return SystemDiagnostic(
            timestamp=datetime.now(UTC),
            overall_status=HealthStatus.FAILED,
            overall_health_score=0.0,
            component_health={},
            active_issues=[{
                'type': 'system_error',
                'severity': 'critical',
                'description': f"System monitoring error: {error}"
            }],
            predictions=[],
            recommendations=["Investigate system monitoring failure"],
            ai_analysis={'error': error}
        )

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_system_health_agent(model_name: str = DEFAULT_MODEL,
                             temperature: float = DEFAULT_TEMPERATURE) -> TradovX12_SystemHealthAgent:  # noqa: E501
    """
    Factory function to create System Health Agent instance.

    Args:
        model_name: Ollama model to use
        temperature: Temperature for AI responses

    Returns:
        TradovX12_SystemHealthAgent instance
    """
    return TradovX12_SystemHealthAgent(model_name, temperature)

# Singleton instance
_module_instance = None
_module_instance_lock = threading.Lock()


def get_module_instance() -> TradovX12_SystemHealthAgent:
    """Get or create singleton instance of the agent."""
    global _module_instance
    if _module_instance is None:
        with _module_instance_lock:
            if _module_instance is None:
                _module_instance = create_system_health_agent()
    return _module_instance

# ==============================================================================
# TEST EXECUTION
# ==============================================================================

async def test_system_health():
    """Test the System Health Agent functionality."""
    logging.info("="*80)
    logging.info("Testing TradovX12_SystemHealthAgent")
    logging.info("="*80)

    agent = create_system_health_agent()

    # Test 1: System Health Monitoring
    logging.info("\nTest 1: System Health Monitoring")
    logging.info("-"*40)

    diagnostic = await agent.monitor_system_health()

    logging.info("Overall Status: %s", diagnostic.overall_status.value)
    logging.info(f"Overall Health Score: {diagnostic.overall_health_score:.1f}/100")

    logging.info("\nComponent Health:")
    for component, health in list(diagnostic.component_health.items())[:5]:
        logging.info("  %s:", component.value)
        logging.info("    Status: %s", health.status.value)
        logging.info(f"    Score: {health.health_score:.1f}")
        if health.issues:
            logging.info("    Issues: %s", ', '.join(health.issues[:2]))

    logging.info("\nActive Issues: %s", len(diagnostic.active_issues))
    for issue in diagnostic.active_issues[:3]:
        logging.info("  [%s] %s", issue['severity'], issue['description'])

    # Test 2: Failure Predictions
    logging.info("\n\nTest 2: Failure Predictions")
    logging.info("-"*40)

    predictions = await agent.predict_failures(horizon_minutes=30)

    logging.info("Predicted Issues: %s", len(predictions))
    for pred in predictions[:3]:
        logging.info("\n%s - %s:", pred.component.value, pred.metric_type.value)
        logging.info(f"  Predicted Value: {pred.predicted_value:.2f}")
        logging.info("  Risk Level: %s", pred.risk_level)
        logging.info(f"  Confidence: {pred.confidence:.1%}")
        if pred.recommended_action:
            logging.info("  Action: %s", pred.recommended_action)

    # Test 3: Component Status Check
    logging.info("\n\nTest 3: Component Status Check")
    logging.info("-"*40)

    trading_health = await agent.check_component_status(SystemComponent.TRADING_ENGINE)

    logging.info("Component: %s", trading_health.component.value)
    logging.info("Status: %s", trading_health.status.value)
    logging.info(f"Health Score: {trading_health.health_score:.1f}")
    logging.info(f"Uptime: {trading_health.uptime_percentage:.1f}%")
    logging.info("Dependencies OK: %s", trading_health.dependencies_ok)

    logging.info("\nMetrics:")
    for metric, value in list(trading_health.metrics.items())[:3]:
        logging.info(f"  {metric.value}: {value:.2f}")

    # Test 4: Auto-remediation
    logging.info("\n\nTest 4: Auto-remediation Test")
    logging.info("-"*40)

    # Create a test alert
    test_alert = HealthAlert(
        timestamp=datetime.now(UTC),
        component=SystemComponent.DATABASE,
        severity='high',
        title='High Disk Usage',
        description='Database disk usage exceeds 85%',
        metric_data={'disk_usage': 85.5},
        resolution_steps=['Clear temp files', 'Archive old data'],
        auto_remediation_available=True
    )

    remediation_result = await agent.auto_remediate(test_alert)

    logging.info("Remediation Result:")
    logging.info("  Success: %s", remediation_result.get('success', False))
    logging.info("  Action: %s", remediation_result.get('action', 'N/A'))
    logging.info(f"  Duration: {remediation_result.get('duration', 0):.1f}s")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":

    # Run async tests
    asyncio.run(test_system_health())

