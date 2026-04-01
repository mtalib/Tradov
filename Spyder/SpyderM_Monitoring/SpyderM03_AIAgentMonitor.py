#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderM_Monitoring
Module: SpyderM03_AIAgentMonitor.py
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
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
from collections import defaultdict, deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import statistics

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

AGENT_CHECK_INTERVAL = 30  # seconds
METRICS_COLLECTION_INTERVAL = 60  # seconds
ALERT_CHECK_INTERVAL = 15  # seconds

# Performance thresholds
LATENCY_WARNING_MS = 1000  # 1 second
LATENCY_CRITICAL_MS = 5000  # 5 seconds
ERROR_RATE_WARNING = 0.05  # 5%
ERROR_RATE_CRITICAL = 0.10  # 10%
SUCCESS_RATE_WARNING = 0.90  # 90%
SUCCESS_RATE_CRITICAL = 0.80  # 80%

# Resource thresholds
MEMORY_WARNING_MB = 500
MEMORY_CRITICAL_MB = 1000
CPU_WARNING_PERCENT = 70
CPU_CRITICAL_PERCENT = 90

# ==============================================================================
# ENUMS
# ==============================================================================
class HealthStatus(Enum):
    """Agent health status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"
    OFFLINE = "offline"

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics to monitor"""
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    SUCCESS_RATE = "success_rate"
    THROUGHPUT = "throughput"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    QUEUE_SIZE = "queue_size"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class AgentHealth:
    """AI agent health information"""
    agent_name: str
    status: HealthStatus
    last_check: datetime
    uptime: timedelta
    metrics: dict[MetricType, float]
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

@dataclass
class PerformanceAlert:
    """Performance alert information"""
    alert_id: str
    agent_name: str
    level: AlertLevel
    metric_type: MetricType
    current_value: float
    threshold: float
    message: str
    timestamp: datetime
    resolved: bool = False
    resolution_time: datetime | None = None

@dataclass
class AgentMetricHistory:
    """Historical metrics for an agent"""
    agent_name: str
    metric_type: MetricType
    values: deque = field(default_factory=lambda: deque(maxlen=1440))  # 24 hours at 1-minute intervals
    timestamps: deque = field(default_factory=lambda: deque(maxlen=1440))

    def add_value(self, value: float, timestamp: datetime):
        """Add a new metric value"""
        self.values.append(value)
        self.timestamps.append(timestamp)

    def get_average(self, minutes: int = 60) -> float:
        """Get average over last N minutes"""
        if not self.values:
            return 0.0
        recent_values = list(self.values)[-minutes:]
        return statistics.mean(recent_values)

    def get_trend(self) -> str:
        """Get trend direction"""
        if len(self.values) < 10:
            return "stable"
        recent = list(self.values)[-10:]
        if recent[-1] > recent[0] * 1.1:
            return "increasing"
        elif recent[-1] < recent[0] * 0.9:
            return "decreasing"
        return "stable"

@dataclass
class MonitoringReport:
    """Comprehensive monitoring report"""
    timestamp: datetime
    total_agents: int
    healthy_agents: int
    warning_agents: int
    critical_agents: int
    offline_agents: int
    active_alerts: list[PerformanceAlert]
    agent_details: dict[str, AgentHealth]
    recommendations: list[str]
    overall_health_score: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class AIAgentMonitor:
    """
    AI Agent monitoring system.

    This class monitors the health and performance of all AI agents,
    provides alerts, and generates monitoring reports.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        agent_manager: Reference to AI agent manager
        health_status: Current health status of each agent
        metric_history: Historical metrics for each agent
        active_alerts: Currently active performance alerts

    Example:
        >>> monitor = AIAgentMonitor(agent_manager)
        >>> monitor.start_monitoring()
        >>> report = monitor.get_monitoring_report()
    """

    def __init__(self, agent_manager):
        """Initialize the AI agent monitor."""
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()
        self.agent_manager = agent_manager

        # Health tracking
        self.health_status: dict[str, AgentHealth] = {}
        self.agent_start_times: dict[str, datetime] = {}

        # Metrics tracking
        self.metric_history: dict[str, dict[MetricType, AgentMetricHistory]] = defaultdict(dict)

        # Alert management
        self.active_alerts: list[PerformanceAlert] = []
        self.alert_history: deque = deque(maxlen=1000)
        self.alert_counter = 0

        # Monitoring threads
        self.monitoring_active = False
        self.monitor_thread = None
        self.metrics_thread = None
        self.alert_thread = None
        self.stop_event = threading.Event()

        # Performance baselines
        self.performance_baselines: dict[str, dict[MetricType, float]] = {}

        # Monitoring thresholds (mutable per-instance, overridable via update_thresholds)
        self.thresholds: dict[str, float] = {
            "LATENCY_WARNING_MS": LATENCY_WARNING_MS,
            "LATENCY_CRITICAL_MS": LATENCY_CRITICAL_MS,
            "ERROR_RATE_WARNING": ERROR_RATE_WARNING,
            "ERROR_RATE_CRITICAL": ERROR_RATE_CRITICAL,
            "SUCCESS_RATE_WARNING": SUCCESS_RATE_WARNING,
            "SUCCESS_RATE_CRITICAL": SUCCESS_RATE_CRITICAL,
            "MEMORY_WARNING_MB": MEMORY_WARNING_MB,
            "MEMORY_CRITICAL_MB": MEMORY_CRITICAL_MB,
            "CPU_WARNING_PERCENT": CPU_WARNING_PERCENT,
            "CPU_CRITICAL_PERCENT": CPU_CRITICAL_PERCENT,
        }

        self.logger.info("AI Agent Monitor initialized")

    # ==========================================================================
    # PUBLIC METHODS - LIFECYCLE
    # ==========================================================================
    def start_monitoring(self) -> bool:
        """
        Start monitoring all AI agents.

        Returns:
            bool: True if started successfully
        """
        try:
            if self.monitoring_active:
                self.logger.warning("Monitoring already active")
                return False

            self.monitoring_active = True
            self.stop_event.clear()

            # Initialize agent tracking
            self._initialize_agent_tracking()

            # Start monitoring threads
            self._start_monitoring_threads()

            self.logger.info("AI agent monitoring started")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
            return False

    def stop_monitoring(self) -> bool:
        """
        Stop monitoring AI agents.

        Returns:
            bool: True if stopped successfully
        """
        try:
            if not self.monitoring_active:
                return False

            self.monitoring_active = False
            self.stop_event.set()

            # Wait for threads to stop
            for thread in [self.monitor_thread, self.metrics_thread, self.alert_thread]:
                if thread and thread.is_alive():
                    thread.join(timeout=5)

            self.logger.info("AI agent monitoring stopped")
            return True

        except Exception as e:
            self.logger.error(f"Error stopping monitoring: {e}")
            return False

    # ==========================================================================
    # PUBLIC METHODS - MONITORING
    # ==========================================================================
    def get_agent_health(self, agent_name: str) -> AgentHealth | None:
        """
        Get health status for a specific agent.

        Args:
            agent_name: Name of the agent

        Returns:
            AgentHealth or None if not found
        """
        return self.health_status.get(agent_name)

    def get_monitoring_report(self) -> MonitoringReport:
        """
        Get comprehensive monitoring report.

        Returns:
            MonitoringReport with current status
        """
        # Count agents by status
        status_counts = defaultdict(int)
        for health in self.health_status.values():
            if health.status == HealthStatus.HEALTHY:
                status_counts['healthy'] += 1
            elif health.status == HealthStatus.WARNING:
                status_counts['warning'] += 1
            elif health.status == HealthStatus.CRITICAL:
                status_counts['critical'] += 1
            elif health.status == HealthStatus.OFFLINE:
                status_counts['offline'] += 1

        # Calculate overall health score
        total_agents = len(self.health_status)
        if total_agents > 0:
            health_score = (
                status_counts['healthy'] * 1.0 +
                status_counts['warning'] * 0.5 +
                status_counts['critical'] * 0.0
            ) / total_agents
        else:
            health_score = 0.0

        # Generate recommendations
        recommendations = self._generate_recommendations()

        return MonitoringReport(
            timestamp=datetime.now(),
            total_agents=total_agents,
            healthy_agents=status_counts['healthy'],
            warning_agents=status_counts['warning'],
            critical_agents=status_counts['critical'],
            offline_agents=status_counts['offline'],
            active_alerts=[a for a in self.active_alerts if not a.resolved],
            agent_details=dict(self.health_status),
            recommendations=recommendations,
            overall_health_score=health_score
        )

    def get_agent_metrics(
        self,
        agent_name: str,
        metric_type: MetricType,
        minutes: int = 60
    ) -> dict[str, Any]:
        """
        Get metrics for a specific agent.

        Args:
            agent_name: Name of the agent
            metric_type: Type of metric
            minutes: Number of minutes of history

        Returns:
            Dict with metric data
        """
        if agent_name not in self.metric_history:
            return {}

        if metric_type not in self.metric_history[agent_name]:
            return {}

        history = self.metric_history[agent_name][metric_type]

        return {
            'current': history.values[-1] if history.values else None,
            'average': history.get_average(minutes),
            'trend': history.get_trend(),
            'min': min(list(history.values)[-minutes:]) if history.values else None,
            'max': max(list(history.values)[-minutes:]) if history.values else None,
            'values': list(history.values)[-minutes:],
            'timestamps': [t.isoformat() for t in list(history.timestamps)[-minutes:]]
        }

    def get_active_alerts(self) -> list[PerformanceAlert]:
        """
        Get all active alerts.

        Returns:
            List of active alerts
        """
        return [a for a in self.active_alerts if not a.resolved]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert ID to acknowledge

        Returns:
            bool: True if acknowledged
        """
        for alert in self.active_alerts:
            if alert.alert_id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolution_time = datetime.now()
                self.logger.info(f"Alert {alert_id} acknowledged")
                return True
        return False

    # ==========================================================================
    # PUBLIC METHODS - CONFIGURATION
    # ==========================================================================
    def set_performance_baseline(
        self,
        agent_name: str,
        baselines: dict[MetricType, float]
    ):
        """
        Set performance baselines for an agent.

        Args:
            agent_name: Name of the agent
            baselines: Baseline values for each metric type
        """
        self.performance_baselines[agent_name] = baselines
        self.logger.info(f"Set baselines for {agent_name}: {baselines}")

    def update_thresholds(self, thresholds: dict[str, float]):
        """
        Update monitoring thresholds.

        Args:
            thresholds: New threshold values
        """
        # Update instance thresholds (only recognised keys are accepted)
        valid_keys = set(self.thresholds)
        updated = {k: v for k, v in thresholds.items() if k in valid_keys}
        self.thresholds.update(updated)
        self.logger.info(f"Updated monitoring thresholds: {updated}")

    # ==========================================================================
    # PRIVATE METHODS - INITIALIZATION
    # ==========================================================================
    def _initialize_agent_tracking(self):
        """Initialize tracking for all agents."""
        agent_status = self.agent_manager.get_agent_status()

        for agent_name in agent_status.get('agents', {}):
            # Initialize health status
            self.health_status[agent_name] = AgentHealth(
                agent_name=agent_name,
                status=HealthStatus.UNKNOWN,
                last_check=datetime.now(),
                uptime=timedelta(0),
                metrics={}
            )

            # Initialize metric history
            for metric_type in MetricType:
                if agent_name not in self.metric_history:
                    self.metric_history[agent_name] = {}
                self.metric_history[agent_name][metric_type] = AgentMetricHistory(
                    agent_name=agent_name,
                    metric_type=metric_type
                )

            # Track start time
            self.agent_start_times[agent_name] = datetime.now()

    def _start_monitoring_threads(self):
        """Start all monitoring threads."""
        # Health monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._health_monitoring_loop,
            name="AIAgentHealthMonitor"
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        # Metrics collection thread
        self.metrics_thread = threading.Thread(
            target=self._metrics_collection_loop,
            name="AIAgentMetricsCollector"
        )
        self.metrics_thread.daemon = True
        self.metrics_thread.start()

        # Alert checking thread
        self.alert_thread = threading.Thread(
            target=self._alert_checking_loop,
            name="AIAgentAlertChecker"
        )
        self.alert_thread.daemon = True
        self.alert_thread.start()

    # ==========================================================================
    # PRIVATE METHODS - MONITORING LOOPS
    # ==========================================================================
    def _health_monitoring_loop(self):
        """Main health monitoring loop."""
        while not self.stop_event.is_set():
            try:
                self._check_all_agents_health()
                self.stop_event.wait(AGENT_CHECK_INTERVAL)
            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")

    def _metrics_collection_loop(self):
        """Metrics collection loop."""
        while not self.stop_event.is_set():
            try:
                self._collect_all_metrics()
                self.stop_event.wait(METRICS_COLLECTION_INTERVAL)
            except Exception as e:
                self.logger.error(f"Metrics collection error: {e}")

    def _alert_checking_loop(self):
        """Alert checking loop."""
        while not self.stop_event.is_set():
            try:
                self._check_for_alerts()
                self.stop_event.wait(ALERT_CHECK_INTERVAL)
            except Exception as e:
                self.logger.error(f"Alert checking error: {e}")

    # ==========================================================================
    # PRIVATE METHODS - HEALTH CHECKING
    # ==========================================================================
    def _check_all_agents_health(self):
        """Check health of all agents."""
        agent_status = self.agent_manager.get_agent_status()

        for agent_name, status_info in agent_status.get('agents', {}).items():
            self._update_agent_health(agent_name, status_info)

    def _update_agent_health(self, agent_name: str, status_info: dict[str, Any]):
        """Update health status for an agent."""
        # Calculate uptime
        start_time = self.agent_start_times.get(agent_name, datetime.now())
        uptime = datetime.now() - start_time

        # Extract metrics
        metrics = {}
        agent_metrics = status_info.get('metrics', {})

        # Latency
        if 'avg_latency_ms' in agent_metrics:
            latency = float(agent_metrics['avg_latency_ms'].rstrip('ms'))
            metrics[MetricType.LATENCY] = latency

        # Success rate
        if 'success_rate' in agent_metrics:
            success_rate = float(agent_metrics['success_rate'].rstrip('%')) / 100
            metrics[MetricType.SUCCESS_RATE] = success_rate
            metrics[MetricType.ERROR_RATE] = 1 - success_rate

        # Determine health status
        issues = []
        status = HealthStatus.HEALTHY

        # Check agent status
        if status_info.get('status') == 'error':
            status = HealthStatus.CRITICAL
            issues.append("Agent in error state")
        elif status_info.get('status') == 'not_initialized':
            status = HealthStatus.OFFLINE
            issues.append("Agent not initialized")

        # Check metrics
        if MetricType.LATENCY in metrics:
            if metrics[MetricType.LATENCY] > self.thresholds["LATENCY_CRITICAL_MS"]:
                status = HealthStatus.CRITICAL
                issues.append(f"High latency: {metrics[MetricType.LATENCY]:.0f}ms")
            elif metrics[MetricType.LATENCY] > self.thresholds["LATENCY_WARNING_MS"]:
                if status != HealthStatus.CRITICAL:
                    status = HealthStatus.WARNING
                issues.append(f"Elevated latency: {metrics[MetricType.LATENCY]:.0f}ms")

        if MetricType.ERROR_RATE in metrics:
            if metrics[MetricType.ERROR_RATE] > self.thresholds["ERROR_RATE_CRITICAL"]:
                status = HealthStatus.CRITICAL
                issues.append(f"High error rate: {metrics[MetricType.ERROR_RATE]:.1%}")
            elif metrics[MetricType.ERROR_RATE] > self.thresholds["ERROR_RATE_WARNING"]:
                if status != HealthStatus.CRITICAL:
                    status = HealthStatus.WARNING
                issues.append(f"Elevated error rate: {metrics[MetricType.ERROR_RATE]:.1%}")

        # Generate recommendations
        recommendations = self._generate_agent_recommendations(agent_name, metrics, issues)

        # Update health status
        self.health_status[agent_name] = AgentHealth(
            agent_name=agent_name,
            status=status,
            last_check=datetime.now(),
            uptime=uptime,
            metrics=metrics,
            issues=issues,
            recommendations=recommendations
        )

    # ==========================================================================
    # PRIVATE METHODS - METRICS COLLECTION
    # ==========================================================================
    def _collect_all_metrics(self):
        """Collect metrics from all agents."""
        agent_status = self.agent_manager.get_agent_status()
        timestamp = datetime.now()

        for agent_name, status_info in agent_status.get('agents', {}).items():
            self._collect_agent_metrics(agent_name, status_info, timestamp)

    def _collect_agent_metrics(
        self,
        agent_name: str,
        status_info: dict[str, Any],
        timestamp: datetime
    ):
        """Collect metrics for a specific agent."""
        agent_metrics = status_info.get('metrics', {})

        # Latency
        if 'avg_latency_ms' in agent_metrics:
            latency = float(agent_metrics['avg_latency_ms'].rstrip('ms'))
            self.metric_history[agent_name][MetricType.LATENCY].add_value(latency, timestamp)

        # Success rate
        if 'success_rate' in agent_metrics:
            success_rate = float(agent_metrics['success_rate'].rstrip('%')) / 100
            self.metric_history[agent_name][MetricType.SUCCESS_RATE].add_value(success_rate, timestamp)
            self.metric_history[agent_name][MetricType.ERROR_RATE].add_value(1 - success_rate, timestamp)

        # Throughput (calls per minute)
        if 'total_calls' in agent_metrics and 'last_call' in agent_metrics:
            # Calculate approximate throughput
            # This is simplified - real implementation would track actual rate
            total_calls = agent_metrics['total_calls']
            if agent_name in self.agent_start_times:
                minutes = (timestamp - self.agent_start_times[agent_name]).total_seconds() / 60
                if minutes > 0:
                    throughput = total_calls / minutes
                    self.metric_history[agent_name][MetricType.THROUGHPUT].add_value(throughput, timestamp)

    # ==========================================================================
    # PRIVATE METHODS - ALERT MANAGEMENT
    # ==========================================================================
    def _check_for_alerts(self):
        """Check for performance alerts."""
        for agent_name, health in self.health_status.items():
            self._check_agent_alerts(agent_name, health)

    def _check_agent_alerts(self, agent_name: str, health: AgentHealth):
        """Check for alerts for a specific agent."""
        # Check each metric
        for metric_type, value in health.metrics.items():
            self._check_metric_alert(agent_name, metric_type, value)

        # Check health status
        if health.status == HealthStatus.CRITICAL:
            self._create_alert(
                agent_name=agent_name,
                level=AlertLevel.CRITICAL,
                metric_type=None,
                message=f"Agent {agent_name} is in critical state",
                current_value=None,
                threshold=None
            )
        elif health.status == HealthStatus.OFFLINE:
            self._create_alert(
                agent_name=agent_name,
                level=AlertLevel.ERROR,
                metric_type=None,
                message=f"Agent {agent_name} is offline",
                current_value=None,
                threshold=None
            )

    def _check_metric_alert(
        self,
        agent_name: str,
        metric_type: MetricType,
        value: float
    ):
        """Check if a metric should trigger an alert."""
        # Define thresholds
        thresholds = {
            MetricType.LATENCY: {
                AlertLevel.WARNING: self.thresholds["LATENCY_WARNING_MS"],
                AlertLevel.CRITICAL: self.thresholds["LATENCY_CRITICAL_MS"],
            },
            MetricType.ERROR_RATE: {
                AlertLevel.WARNING: self.thresholds["ERROR_RATE_WARNING"],
                AlertLevel.CRITICAL: self.thresholds["ERROR_RATE_CRITICAL"],
            },
            MetricType.SUCCESS_RATE: {
                AlertLevel.WARNING: self.thresholds["SUCCESS_RATE_WARNING"],
                AlertLevel.CRITICAL: self.thresholds["SUCCESS_RATE_CRITICAL"],
            },
        }

        if metric_type not in thresholds:
            return

        # Check against thresholds
        for level, threshold in thresholds[metric_type].items():
            should_alert = False

            if metric_type == MetricType.SUCCESS_RATE:
                # Lower is worse for success rate
                should_alert = value < threshold
            else:
                # Higher is worse for other metrics
                should_alert = value > threshold

            if should_alert:
                # Check if alert already exists
                existing = self._find_existing_alert(agent_name, metric_type)
                if not existing or existing.level != level:
                    self._create_alert(
                        agent_name=agent_name,
                        level=level,
                        metric_type=metric_type,
                        message=f"{metric_type.value} is {value:.2f} (threshold: {threshold})",
                        current_value=value,
                        threshold=threshold
                    )
                break

    def _create_alert(
        self,
        agent_name: str,
        level: AlertLevel,
        metric_type: MetricType | None,
        message: str,
        current_value: float | None,
        threshold: float | None
    ):
        """Create a new alert."""
        self.alert_counter += 1
        alert = PerformanceAlert(
            alert_id=f"ALERT_{self.alert_counter:04d}",
            agent_name=agent_name,
            level=level,
            metric_type=metric_type,
            current_value=current_value,
            threshold=threshold,
            message=message,
            timestamp=datetime.now()
        )

        self.active_alerts.append(alert)
        self.alert_history.append(alert)

        # Log alert
        if level == AlertLevel.CRITICAL:
            self.logger.critical(f"AI Agent Alert: {agent_name} - {message}")
        elif level == AlertLevel.ERROR:
            self.logger.error(f"AI Agent Alert: {agent_name} - {message}")
        elif level == AlertLevel.WARNING:
            self.logger.warning(f"AI Agent Alert: {agent_name} - {message}")
        else:
            self.logger.info(f"AI Agent Alert: {agent_name} - {message}")

        # Emit event
        self._emit_alert_event(alert)

    def _find_existing_alert(
        self,
        agent_name: str,
        metric_type: MetricType
    ) -> PerformanceAlert | None:
        """Find existing unresolved alert."""
        for alert in self.active_alerts:
            if (alert.agent_name == agent_name and
                alert.metric_type == metric_type and
                not alert.resolved):
                return alert
        return None

    def _emit_alert_event(self, alert: PerformanceAlert):
        """Emit alert event through event manager."""
        # Would integrate with event manager
        self.logger.debug(f"Alert event: {alert.alert_id}")

    # ==========================================================================
    # PRIVATE METHODS - RECOMMENDATIONS
    # ==========================================================================
    def _generate_recommendations(self) -> list[str]:
        """Generate overall system recommendations."""
        recommendations = []

        # Check overall health
        report = self.get_monitoring_report()

        if report.critical_agents > 0:
            recommendations.append(
                f"Address critical issues in {report.critical_agents} agents immediately"
            )

        if report.warning_agents > len(self.health_status) * 0.3:
            recommendations.append(
                "High number of agents with warnings - consider system optimization"
            )

        if report.overall_health_score < 0.7:
            recommendations.append(
                "Overall system health is below optimal - review agent configurations"
            )

        # Check for common issues
        common_issues = defaultdict(int)
        for health in self.health_status.values():
            for issue in health.issues:
                if "latency" in issue.lower():
                    common_issues["latency"] += 1
                elif "error" in issue.lower():
                    common_issues["errors"] += 1

        if common_issues["latency"] > len(self.health_status) * 0.5:
            recommendations.append(
                "System-wide latency issues detected - check LLM performance"
            )

        if common_issues["errors"] > len(self.health_status) * 0.3:
            recommendations.append(
                "High error rates across agents - review error logs"
            )

        return recommendations

    def _generate_agent_recommendations(
        self,
        agent_name: str,
        metrics: dict[MetricType, float],
        issues: list[str]
    ) -> list[str]:
        """Generate recommendations for a specific agent."""
        recommendations = []

        # Latency recommendations
        if MetricType.LATENCY in metrics:
            if metrics[MetricType.LATENCY] > self.thresholds["LATENCY_WARNING_MS"]:
                recommendations.append("Consider using a smaller/faster LLM model")
                recommendations.append("Enable response caching if not already active")

        # Error rate recommendations
        if MetricType.ERROR_RATE in metrics:
            if metrics[MetricType.ERROR_RATE] > self.thresholds["ERROR_RATE_WARNING"]:
                recommendations.append("Review recent error logs for patterns")
                recommendations.append("Check input validation and error handling")

        # General recommendations based on issues
        if any("offline" in issue.lower() for issue in issues):
            recommendations.append("Restart the agent or check initialization")

        return recommendations

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def create_ai_agent_monitor(agent_manager) -> AIAgentMonitor:
    """
    Factory function to create AI agent monitor.

    Args:
        agent_manager: AI agent manager instance

    Returns:
        Configured AIAgentMonitor instance
    """
    return AIAgentMonitor(agent_manager)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    # Module testing
    pass
