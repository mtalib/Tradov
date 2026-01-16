#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderI_Integration
Module: SpyderI04_DiagnosticsEngine_Types.py
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
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

class HealthStatus(Enum):
    """System health status levels"""

    EXCELLENT = "excellent"  # 90-100%
    GOOD = "good"  # 70-89%
    WARNING = "warning"  # 50-69%
    CRITICAL = "critical"  # 30-49%
    FAILING = "failing"  # 0-29%


class DiagnosticCategory(Enum):
    """Diagnostic categories"""

    SYSTEM = "system"  # OS-level diagnostics
    NETWORK = "network"  # Network connectivity
    MODULES = "modules"  # Module health
    INTEGRATION = "integration"  # Inter-module communication
    PERFORMANCE = "performance"  # Performance metrics
    CONFIGURATION = "configuration"  # Configuration issues
    DEPENDENCIES = "dependencies"  # Dependency health
    SECURITY = "security"  # Security diagnostics


class ProblemSeverity(Enum):
    """Problem severity levels"""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiagnosticType(Enum):
    """Types of diagnostic checks"""

    HEALTH_CHECK = "health_check"
    PERFORMANCE_TEST = "performance_test"
    INTEGRATION_TEST = "integration_test"
    STRESS_TEST = "stress_test"
    DEPENDENCY_CHECK = "dependency_check"
    CONFIGURATION_AUDIT = "configuration_audit"
    SECURITY_SCAN = "security_scan"


# ==============================================================================
# SYSTEM METRICS
# ==============================================================================


@dataclass
class SystemMetrics:
    """System-level metrics"""

    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    network_sent_bytes: int
    network_recv_bytes: int
    active_connections: int
    process_count: int
    thread_count: int
    file_descriptors: int
    load_average: Optional[Tuple[float, float, float]] = None


@dataclass
class NetworkMetrics:
    """Network-specific metrics"""

    timestamp: datetime
    latency: float  # milliseconds
    packet_loss: float  # percentage
    bandwidth_utilization: float  # percentage
    connection_count: int
    error_rate: float  # percentage


# ==============================================================================
# MODULE HEALTH
# ==============================================================================


@dataclass
class ModuleHealth:
    """Individual module health status"""

    module_id: str
    module_name: str
    status: HealthStatus
    response_time: float  # milliseconds
    error_rate: float  # percentage
    memory_usage: int  # bytes
    cpu_usage: float  # percentage
    last_heartbeat: datetime
    active_connections: int
    processed_requests: int
    failed_requests: int
    uptime: timedelta
    dependencies_healthy: bool
    configuration_valid: bool


@dataclass
class IntegrationHealth:
    """Integration between modules health"""

    source_module: str
    target_module: str
    connection_status: HealthStatus
    latency: float  # milliseconds
    throughput: float  # messages/second
    error_rate: float  # percentage
    last_communication: datetime
    message_queue_size: int
    retry_count: int
    circuit_breaker_status: str


# ==============================================================================
# DIAGNOSTIC ISSUES
# ==============================================================================


@dataclass
class DiagnosticIssue:
    """Identified diagnostic issue"""

    issue_id: str
    category: DiagnosticCategory
    severity: ProblemSeverity
    title: str
    description: str
    affected_components: List[str]
    symptoms: List[str]
    root_cause: Optional[str] = None
    recommendations: List[str] = field(default_factory=list)
    auto_fixable: bool = False
    detected_at: datetime = field(default_factory=datetime.now)
    resolution_status: str = "open"  # open, investigating, resolved
    impact_score: float = 0.0  # 0-1 scale


@dataclass
class IssuePattern:
    """Pattern detected in diagnostic issues"""

    pattern_id: str
    pattern_type: str
    frequency: int
    components: List[str]
    description: str
    severity: float  # 0-1 scale
    first_seen: datetime
    last_seen: datetime


# ==============================================================================
# PERFORMANCE ANALYSIS
# ==============================================================================


@dataclass
class PerformanceBaseline:
    """Performance baseline for comparison"""

    component: str
    metric_name: str
    baseline_value: float
    standard_deviation: float
    sample_count: int
    confidence_interval: Tuple[float, float]
    established_at: datetime
    last_updated: datetime


@dataclass
class PerformanceTrend:
    """Performance trend analysis"""

    metric_name: str
    component: str
    trend_direction: str  # "increasing", "decreasing", "stable"
    trend_strength: float  # 0-1 scale
    percentage_change: float
    time_period: timedelta
    confidence: float  # 0-1 scale


@dataclass
class BottleneckInfo:
    """Information about a performance bottleneck"""

    component: str
    bottleneck_type: str  # "cpu", "memory", "disk", "network", "queue"
    severity: float  # 0-1 scale
    description: str
    symptoms: List[str]
    recommendations: List[str]
    estimated_impact: float  # 0-1 scale


# ==============================================================================
# ANOMALY DETECTION
# ==============================================================================


@dataclass
class AnomalyInfo:
    """Information about detected anomaly"""

    anomaly_id: str
    metric_name: str
    component: str
    anomaly_type: str  # "spike", "drop", "drift", "outlier"
    severity: float  # 0-1 scale
    detected_at: datetime
    value: float
    expected_value: float
    deviation: float
    confidence: float  # 0-1 scale


# ==============================================================================
# DIAGNOSTIC REPORTS
# ==============================================================================


@dataclass
class HealthSnapshot:
    """Point-in-time health snapshot"""

    timestamp: datetime
    overall_score: float
    system_metrics: SystemMetrics
    module_health: List[ModuleHealth]
    integration_health: List[IntegrationHealth]
    active_issues: List[DiagnosticIssue]


@dataclass
class PerformanceSummary:
    """Performance analysis summary"""

    trends: List[PerformanceTrend]
    bottlenecks: List[BottleneckInfo]
    anomalies: List[AnomalyInfo]
    baselines: Dict[str, PerformanceBaseline]
    overall_performance_score: float


@dataclass
class DiagnosticReport:
    """Comprehensive diagnostic report"""

    report_id: str
    generated_at: datetime
    overall_health_score: float
    system_metrics: SystemMetrics
    module_health: List[ModuleHealth]
    integration_health: List[IntegrationHealth]
    identified_issues: List[DiagnosticIssue]
    performance_summary: Dict[str, Any]
    recommendations: List[str]
    executive_summary: str


# ==============================================================================
# CONFIGURATION
# ==============================================================================


@dataclass
class DiagnosticConfig:
    """Configuration for diagnostic operations"""

    monitoring_enabled: bool = True
    deep_analysis_enabled: bool = True
    auto_healing_enabled: bool = False
    health_check_interval: int = 30  # seconds
    performance_analysis_interval: int = 60  # seconds
    deep_analysis_interval: int = 300  # seconds
    max_diagnostic_history: int = 10000
    max_performance_samples: int = 1000
    max_health_snapshots: int = 500
    cpu_warning_threshold: float = 70.0
    cpu_critical_threshold: float = 90.0
    memory_warning_threshold: float = 75.0
    memory_critical_threshold: float = 90.0
    disk_warning_threshold: float = 80.0
    disk_critical_threshold: float = 95.0
    network_latency_warning: float = 100.0  # ms
    network_latency_critical: float = 500.0  # ms


# ==============================================================================
# THRESHOLDS AND CONSTANTS
# ==============================================================================


# Performance thresholds
CPU_USAGE_WARNING = 70  # percent
CPU_USAGE_CRITICAL = 90  # percent
MEMORY_USAGE_WARNING = 75  # percent
MEMORY_USAGE_CRITICAL = 90  # percent
DISK_USAGE_WARNING = 80  # percent
DISK_USAGE_CRITICAL = 95  # percent

# Network thresholds
NETWORK_LATENCY_WARNING = 100  # milliseconds
NETWORK_LATENCY_CRITICAL = 500  # milliseconds
PACKET_LOSS_WARNING = 1  # percent
PACKET_LOSS_CRITICAL = 5  # percent

# Module health thresholds
MODULE_RESPONSE_TIME_WARNING = 1000  # milliseconds
MODULE_RESPONSE_TIME_CRITICAL = 5000  # milliseconds
MODULE_ERROR_RATE_WARNING = 5  # percent
MODULE_ERROR_RATE_CRITICAL = 15  # percent

# Diagnostic history limits
MAX_DIAGNOSTIC_HISTORY = 10000
MAX_PERFORMANCE_SAMPLES = 1000
MAX_HEALTH_SNAPSHOTS = 500

# Health score weights
HEALTH_SCORE_WEIGHTS = {
    "system": 0.4,  # System metrics weight
    "modules": 0.3,  # Module health weight
    "integration": 0.2,  # Integration health weight
    "issues": 0.1,  # Issues impact weight
}

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================


def create_diagnostic_config(**kwargs) -> DiagnosticConfig:
    """
    Create diagnostic configuration with optional overrides.

    Args:
        **kwargs: Configuration overrides

    Returns:
        DiagnosticConfig instance
    """
    return DiagnosticConfig(**kwargs)


def severity_to_score(severity: ProblemSeverity) -> float:
    """
    Convert problem severity to numeric score.

    Args:
        severity: Problem severity

    Returns:
        Numeric score (0-1 scale)
    """
    severity_scores = {
        ProblemSeverity.INFO: 0.1,
        ProblemSeverity.LOW: 0.3,
        ProblemSeverity.MEDIUM: 0.5,
        ProblemSeverity.HIGH: 0.8,
        ProblemSeverity.CRITICAL: 1.0,
    }
    return severity_scores.get(severity, 0.5)


def health_status_to_score(status: HealthStatus) -> float:
    """
    Convert health status to numeric score.

    Args:
        status: Health status

    Returns:
        Numeric score (0-1 scale)
    """
    status_scores = {
        HealthStatus.EXCELLENT: 1.0,
        HealthStatus.GOOD: 0.8,
        HealthStatus.WARNING: 0.6,
        HealthStatus.CRITICAL: 0.3,
        HealthStatus.FAILING: 0.0,
    }
    return status_scores.get(status, 0.5)


def score_to_health_status(score: float) -> HealthStatus:
    """
    Convert numeric score to health status.

    Args:
        score: Numeric score (0-1 scale)

    Returns:
        HealthStatus enum
    """
    if score >= 0.9:
        return HealthStatus.EXCELLENT
    elif score >= 0.7:
        return HealthStatus.GOOD
    elif score >= 0.5:
        return HealthStatus.WARNING
    elif score >= 0.3:
        return HealthStatus.CRITICAL
    else:
        return HealthStatus.FAILING
