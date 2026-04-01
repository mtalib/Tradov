#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderM_Monitoring
Module: SpyderM01_SystemMonitor.py
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
import time
import threading
import datetime
import os
import sys
from typing import Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import uuid

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
import gc
import traceback
import statistics

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

METRICS_WINDOW = 300  # 5 minutes
MONITOR_INTERVAL = 5  # seconds
CPU_WARNING_THRESHOLD = 70.0
CPU_CRITICAL_THRESHOLD = 90.0
MEMORY_WARNING_THRESHOLD = 80.0
MEMORY_CRITICAL_THRESHOLD = 95.0
DISK_WARNING_THRESHOLD = 85.0
DISK_CRITICAL_THRESHOLD = 95.0
LATENCY_WARNING_MS = 100
LATENCY_CRITICAL_MS = 500
ERROR_RATE_WARNING = 0.01
ERROR_RATE_CRITICAL = 0.05
ALERT_COOLDOWN = 300  # 5 minutes

# ==============================================================================
# ENUMS
# ==============================================================================
class HealthStatus(Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class MetricType(Enum):
    """Types of metrics being monitored"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    COMPONENT = "component"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class SystemMetrics:
    """System resource metrics"""
    timestamp: datetime.datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_free_gb: float
    network_sent_mb: float
    network_recv_mb: float
    open_files: int
    thread_count: int
    process_count: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_used_mb': self.memory_used_mb,
            'memory_available_mb': self.memory_available_mb,
            'disk_percent': self.disk_percent,
            'disk_used_gb': self.disk_used_gb,
            'disk_free_gb': self.disk_free_gb,
            'network_sent_mb': self.network_sent_mb,
            'network_recv_mb': self.network_recv_mb,
            'open_files': self.open_files,
            'thread_count': self.thread_count,
            'process_count': self.process_count
        }

@dataclass
class PerformanceMetrics:
    """Application performance metrics"""
    timestamp: datetime.datetime
    event_latency_ms: float
    order_latency_ms: float
    data_latency_ms: float
    events_per_second: float
    orders_per_second: float
    error_count: int
    error_rate: float
    active_strategies: int
    open_positions: int
    pending_orders: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'event_latency_ms': self.event_latency_ms,
            'order_latency_ms': self.order_latency_ms,
            'data_latency_ms': self.data_latency_ms,
            'events_per_second': self.events_per_second,
            'orders_per_second': self.orders_per_second,
            'error_count': self.error_count,
            'error_rate': self.error_rate,
            'active_strategies': self.active_strategies,
            'open_positions': self.open_positions,
            'pending_orders': self.pending_orders
        }

@dataclass
class SystemAlert:
    """System alert information"""
    alert_id: str
    timestamp: datetime.datetime
    level: AlertLevel
    metric_type: MetricType
    message: str
    value: float
    threshold: float
    resolved: bool = False
    resolution_time: datetime.datetime | None = None

@dataclass
class HealthCheck:
    """Component health check result"""
    component: str
    timestamp: datetime.datetime
    status: HealthStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

# ==============================================================================
# SYSTEM MONITOR CLASS
# ==============================================================================
class SystemMonitor:
    """
    System health and performance monitor.

    Features:
    - Resource usage monitoring (CPU, memory, disk)
    - Performance metrics tracking
    - Component health checks
    - Alert generation and management
    - Historical metrics storage
    - Diagnostic reporting
    """

    def __init__(self, event_manager=None):
        """
        Initialize system monitor.

        Args:
            event_manager: Optional event manager instance
        """
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)
        self.error_handler = SpyderErrorHandler()

        # Process info
        self.process = psutil.Process(os.getpid())
        self.start_time = datetime.datetime.now()

        # Metrics storage
        self.system_metrics: deque = deque(maxlen=METRICS_WINDOW // MONITOR_INTERVAL)
        self.performance_metrics: deque = deque(maxlen=METRICS_WINDOW // MONITOR_INTERVAL)
        self.health_checks: dict[str, HealthCheck] = {}

        # Alerts
        self.active_alerts: dict[str, SystemAlert] = {}
        self.alert_history: deque = deque(maxlen=1000)
        self.alert_cooldowns: dict[str, datetime.datetime] = {}

        # Performance tracking
        self.latency_tracker: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.error_tracker: deque = deque(maxlen=1000)
        self.event_counter = 0
        self.order_counter = 0

        # Component monitors
        self.component_monitors: dict[str, Callable] = {}

        # Monitoring thread
        self._monitor_thread: threading.Thread | None = None
        self._running = False
        self._stop_event = threading.Event()
        self._monitor_lock = threading.RLock()

        # Network baseline
        net_io = psutil.net_io_counters()
        self._network_baseline = {
            'sent': net_io.bytes_sent,
            'recv': net_io.bytes_recv
        }

        # Register event handlers if event manager provided
        if self.event_manager:
            self._register_event_handlers()

        self.logger.info("SystemMonitor initialized")

    # ==========================================================================
    # LIFECYCLE METHODS
    # ==========================================================================
    def start(self) -> None:
        """Start system monitoring"""
        if self._running:
            return

        self._running = True

        # Start monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="SystemMonitor"
        )
        self._monitor_thread.start()

        self.logger.info("System monitoring started")

    def stop(self) -> None:
        """Stop system monitoring"""
        self._running = False
        self._stop_event.set()

        if self._monitor_thread:
            self._monitor_thread.join(timeout=10.0)

        self.logger.info("System monitoring stopped")

    # ==========================================================================
    # MONITORING
    # ==========================================================================
    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._running:
            try:
                # Collect metrics
                system_metrics = self._collect_system_metrics()
                performance_metrics = self._collect_performance_metrics()

                # Store metrics
                with self._monitor_lock:
                    self.system_metrics.append(system_metrics)
                    self.performance_metrics.append(performance_metrics)

                # Check thresholds
                self._check_thresholds(system_metrics, performance_metrics)

                # Run component health checks
                self._run_health_checks()

                # Clean up old data
                self._cleanup_old_data()

                # Sleep
                if self._stop_event.wait(timeout=MONITOR_INTERVAL):
                    break

            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}", exc_info=True)
                self.error_tracker.append({
                    'timestamp': datetime.datetime.now(),
                    'error': str(e),
                    'traceback': traceback.format_exc()
                })

    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system resource metrics"""
        # CPU
        cpu_percent = self.process.cpu_percent(interval=0.1)

        # Memory
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        system_memory = psutil.virtual_memory()

        # Disk
        disk_usage = psutil.disk_usage('/')

        # Network
        net_io = psutil.net_io_counters()
        network_sent_mb = (net_io.bytes_sent - self._network_baseline['sent']) / 1024 / 1024
        network_recv_mb = (net_io.bytes_recv - self._network_baseline['recv']) / 1024 / 1024

        # Process info
        try:
            open_files = len(self.process.open_files())
        except Exception:
            open_files = 0

        thread_count = self.process.num_threads()
        process_count = len(psutil.pids())

        return SystemMetrics(
            timestamp=datetime.datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used_mb=memory_info.rss / 1024 / 1024,
            memory_available_mb=system_memory.available / 1024 / 1024,
            disk_percent=disk_usage.percent,
            disk_used_gb=disk_usage.used / 1024 / 1024 / 1024,
            disk_free_gb=disk_usage.free / 1024 / 1024 / 1024,
            network_sent_mb=network_sent_mb,
            network_recv_mb=network_recv_mb,
            open_files=open_files,
            thread_count=thread_count,
            process_count=process_count
        )

    def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect application performance metrics"""
        # Calculate latencies
        event_latency = self._calculate_average_latency('event')
        order_latency = self._calculate_average_latency('order')
        data_latency = self._calculate_average_latency('data')

        # Calculate rates
        events_per_second = self.event_counter / MONITOR_INTERVAL
        orders_per_second = self.order_counter / MONITOR_INTERVAL

        # Calculate error rate
        recent_errors = sum(1 for e in self.error_tracker
                          if (datetime.datetime.now() - e['timestamp']).seconds < 60)
        error_rate = recent_errors / max(self.event_counter, 1)

        # Reset counters
        self.event_counter = 0
        self.order_counter = 0

        # Get active components (placeholder - would get from actual components)
        active_strategies = 0
        open_positions = 0
        pending_orders = 0

        return PerformanceMetrics(
            timestamp=datetime.datetime.now(),
            event_latency_ms=event_latency,
            order_latency_ms=order_latency,
            data_latency_ms=data_latency,
            events_per_second=events_per_second,
            orders_per_second=orders_per_second,
            error_count=len(self.error_tracker),
            error_rate=error_rate,
            active_strategies=active_strategies,
            open_positions=open_positions,
            pending_orders=pending_orders
        )

    def _calculate_average_latency(self, metric_type: str) -> float:
        """Calculate average latency for a metric type"""
        latencies = self.latency_tracker.get(metric_type, [])
        if latencies:
            return statistics.mean(latencies)
        return 0.0

    # ==========================================================================
    # THRESHOLD CHECKING
    # ==========================================================================
    def _check_thresholds(
        self,
        system_metrics: SystemMetrics,
        performance_metrics: PerformanceMetrics
    ) -> None:
        """Check metrics against thresholds and generate alerts"""
        # CPU
        if system_metrics.cpu_percent >= CPU_CRITICAL_THRESHOLD:
            self._create_alert(
                MetricType.CPU,
                AlertLevel.CRITICAL,
                f"CPU usage critical: {system_metrics.cpu_percent:.1f}%",
                system_metrics.cpu_percent,
                CPU_CRITICAL_THRESHOLD
            )
        elif system_metrics.cpu_percent >= CPU_WARNING_THRESHOLD:
            self._create_alert(
                MetricType.CPU,
                AlertLevel.WARNING,
                f"CPU usage high: {system_metrics.cpu_percent:.1f}%",
                system_metrics.cpu_percent,
                CPU_WARNING_THRESHOLD
            )
        else:
            self._resolve_alert(MetricType.CPU)

        # Memory
        if system_metrics.memory_percent >= MEMORY_CRITICAL_THRESHOLD:
            self._create_alert(
                MetricType.MEMORY,
                AlertLevel.CRITICAL,
                f"Memory usage critical: {system_metrics.memory_percent:.1f}%",
                system_metrics.memory_percent,
                MEMORY_CRITICAL_THRESHOLD
            )
        elif system_metrics.memory_percent >= MEMORY_WARNING_THRESHOLD:
            self._create_alert(
                MetricType.MEMORY,
                AlertLevel.WARNING,
                f"Memory usage high: {system_metrics.memory_percent:.1f}%",
                system_metrics.memory_percent,
                MEMORY_WARNING_THRESHOLD
            )
        else:
            self._resolve_alert(MetricType.MEMORY)

        # Disk
        if system_metrics.disk_percent >= DISK_CRITICAL_THRESHOLD:
            self._create_alert(
                MetricType.DISK,
                AlertLevel.CRITICAL,
                f"Disk usage critical: {system_metrics.disk_percent:.1f}%",
                system_metrics.disk_percent,
                DISK_CRITICAL_THRESHOLD
            )
        elif system_metrics.disk_percent >= DISK_WARNING_THRESHOLD:
            self._create_alert(
                MetricType.DISK,
                AlertLevel.WARNING,
                f"Disk usage high: {system_metrics.disk_percent:.1f}%",
                system_metrics.disk_percent,
                DISK_WARNING_THRESHOLD
            )
        else:
            self._resolve_alert(MetricType.DISK)

        # Latency
        if performance_metrics.event_latency_ms >= LATENCY_CRITICAL_MS:
            self._create_alert(
                MetricType.LATENCY,
                AlertLevel.CRITICAL,
                f"Event latency critical: {performance_metrics.event_latency_ms:.1f}ms",
                performance_metrics.event_latency_ms,
                LATENCY_CRITICAL_MS
            )
        elif performance_metrics.event_latency_ms >= LATENCY_WARNING_MS:
            self._create_alert(
                MetricType.LATENCY,
                AlertLevel.WARNING,
                f"Event latency high: {performance_metrics.event_latency_ms:.1f}ms",
                performance_metrics.event_latency_ms,
                LATENCY_WARNING_MS
            )
        else:
            self._resolve_alert(MetricType.LATENCY)

        # Error rate
        if performance_metrics.error_rate >= ERROR_RATE_CRITICAL:
            self._create_alert(
                MetricType.ERROR_RATE,
                AlertLevel.CRITICAL,
                f"Error rate critical: {performance_metrics.error_rate:.2%}",
                performance_metrics.error_rate,
                ERROR_RATE_CRITICAL
            )
        elif performance_metrics.error_rate >= ERROR_RATE_WARNING:
            self._create_alert(
                MetricType.ERROR_RATE,
                AlertLevel.WARNING,
                f"Error rate high: {performance_metrics.error_rate:.2%}",
                performance_metrics.error_rate,
                ERROR_RATE_WARNING
            )
        else:
            self._resolve_alert(MetricType.ERROR_RATE)

    def _create_alert(
        self,
        metric_type: MetricType,
        level: AlertLevel,
        message: str,
        value: float,
        threshold: float
    ) -> None:
        """Create or update an alert"""
        alert_key = metric_type.value

        # Check cooldown
        if alert_key in self.alert_cooldowns:
            if datetime.datetime.now() < self.alert_cooldowns[alert_key]:
                return

        # Create or update alert
        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.level = level
            alert.message = message
            alert.value = value
            alert.timestamp = datetime.datetime.now()
        else:
            alert = SystemAlert(
                alert_id=f"alert_{uuid.uuid4().hex[:8]}",
                timestamp=datetime.datetime.now(),
                level=level,
                metric_type=metric_type,
                message=message,
                value=value,
                threshold=threshold
            )
            self.active_alerts[alert_key] = alert
            self.alert_history.append(alert)

            # Emit alert event
            if self.event_manager:
                self._emit_alert_event(alert)

        # Set cooldown
        self.alert_cooldowns[alert_key] = datetime.datetime.now() + datetime.timedelta(seconds=ALERT_COOLDOWN)

    def _resolve_alert(self, metric_type: MetricType) -> None:
        """Resolve an active alert"""
        alert_key = metric_type.value

        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.resolved = True
            alert.resolution_time = datetime.datetime.now()

            del self.active_alerts[alert_key]

            # Clear cooldown
            if alert_key in self.alert_cooldowns:
                del self.alert_cooldowns[alert_key]

            self.logger.info(f"Alert resolved: {metric_type.value}")

    # ==========================================================================
    # HEALTH CHECKS
    # ==========================================================================
    def _run_health_checks(self) -> None:
        """Run component health checks"""
        for component, check_func in self.component_monitors.items():
            try:
                status, message, details = check_func()

                self.health_checks[component] = HealthCheck(
                    component=component,
                    timestamp=datetime.datetime.now(),
                    status=status,
                    message=message,
                    details=details
                )

                # Create alert if unhealthy
                if status == HealthStatus.CRITICAL:
                    self._create_alert(
                        MetricType.COMPONENT,
                        AlertLevel.CRITICAL,
                        f"Component {component}: {message}",
                        0,
                        0
                    )
                elif status == HealthStatus.WARNING:
                    self._create_alert(
                        MetricType.COMPONENT,
                        AlertLevel.WARNING,
                        f"Component {component}: {message}",
                        0,
                        0
                    )

            except Exception as e:
                self.logger.error(f"Error running health check for {component}: {e}", exc_info=True)

                self.health_checks[component] = HealthCheck(
                    component=component,
                    timestamp=datetime.datetime.now(),
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check failed: {str(e)}",
                    details={}
                )

    def register_component_monitor(
        self,
        component: str,
        check_func: Callable[[], tuple[HealthStatus, str, dict[str, Any]]]
    ) -> None:
        """
        Register a component health check function.

        Args:
            component: Component name
            check_func: Function that returns (status, message, details)
        """
        self.component_monitors[component] = check_func
        self.logger.info(f"Registered health monitor for {component}")

    # ==========================================================================
    # PUBLIC API
    # ==========================================================================
    def record_latency(self, metric_type: str, latency_ms: float) -> None:
        """
        Record a latency measurement.

        Args:
            metric_type: Type of metric (e.g., 'event', 'order', 'data')
            latency_ms: Latency in milliseconds
        """
        with self._monitor_lock:
            self.latency_tracker[metric_type].append(latency_ms)

    def record_error(self, error: str, source: str | None = None) -> None:
        """
        Record an error.

        Args:
            error: Error message
            source: Error source
        """
        with self._monitor_lock:
            self.error_tracker.append({
                'timestamp': datetime.datetime.now(),
                'error': error,
                'source': source,
                'traceback': traceback.format_exc()
            })

    # ==========================================================================
    # DIAGNOSTICS
    # ==========================================================================
    def get_system_status(self) -> dict[str, Any]:
        """
        Get comprehensive system status.

        Returns:
            System status dictionary
        """
        with self._monitor_lock:
            # Current metrics
            current_system = self.system_metrics[-1] if self.system_metrics else None
            current_performance = self.performance_metrics[-1] if self.performance_metrics else None

            # Calculate uptime
            uptime = datetime.datetime.now() - self.start_time

            # Overall health
            overall_health = self._calculate_overall_health()

            status = {
                'health': overall_health.value,
                'uptime_seconds': uptime.total_seconds(),
                'active_alerts': len(self.active_alerts),
                'current_metrics': {
                    'system': current_system.to_dict() if current_system else None,
                    'performance': current_performance.to_dict() if current_performance else None
                },
                'alerts': [
                    {
                        'id': alert.alert_id,
                        'level': alert.level.value,
                        'metric': alert.metric_type.value,
                        'message': alert.message,
                        'timestamp': alert.timestamp.isoformat()
                    }
                    for alert in self.active_alerts.values()
                ],
                'component_health': {
                    comp: {
                        'status': check.status.value,
                        'message': check.message,
                        'timestamp': check.timestamp.isoformat()
                    }
                    for comp, check in self.health_checks.items()
                }
            }

            return status

    def get_metrics_summary(self, window_minutes: int = 5) -> dict[str, Any]:
        """
        Get metrics summary for a time window.

        Args:
            window_minutes: Time window in minutes

        Returns:
            Metrics summary
        """
        with self._monitor_lock:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=window_minutes)

            # Filter metrics
            system_metrics = [m for m in self.system_metrics if m.timestamp > cutoff_time]
            performance_metrics = [m for m in self.performance_metrics if m.timestamp > cutoff_time]

            if not system_metrics:
                return {}

            # Calculate summaries
            summary = {
                'window_minutes': window_minutes,
                'data_points': len(system_metrics),
                'cpu': {
                    'avg': statistics.mean(m.cpu_percent for m in system_metrics),
                    'max': max(m.cpu_percent for m in system_metrics),
                    'min': min(m.cpu_percent for m in system_metrics)
                },
                'memory': {
                    'avg': statistics.mean(m.memory_percent for m in system_metrics),
                    'max': max(m.memory_percent for m in system_metrics),
                    'min': min(m.memory_percent for m in system_metrics)
                },
                'disk': {
                    'current': system_metrics[-1].disk_percent if system_metrics else 0
                }
            }

            if performance_metrics:
                summary['performance'] = {
                    'avg_event_latency_ms': statistics.mean(m.event_latency_ms for m in performance_metrics),
                    'avg_error_rate': statistics.mean(m.error_rate for m in performance_metrics),
                    'total_errors': sum(m.error_count for m in performance_metrics)
                }

            return summary

    def generate_diagnostic_report(self) -> str:
        """
        Generate a detailed diagnostic report.

        Returns:
            Diagnostic report text
        """
        report = []
        report.append("=" * 60)
        report.append("SPYDER SYSTEM DIAGNOSTIC REPORT")
        report.append(f"Generated: {datetime.datetime.now()}")
        report.append("=" * 60)

        # System info
        report.append("\nSYSTEM INFORMATION:")
        report.append(f"  Python: {sys.version}")
        report.append(f"  Platform: {sys.platform}")
        report.append(f"  Process ID: {os.getpid()}")
        report.append(f"  Uptime: {datetime.datetime.now() - self.start_time}")

        # Current status
        status = self.get_system_status()
        report.append(f"\nOVERALL HEALTH: {status['health']}")
        report.append(f"Active Alerts: {status['active_alerts']}")

        # Resource usage
        if status['current_metrics']['system']:
            metrics = status['current_metrics']['system']
            report.append("\nRESOURCE USAGE:")
            report.append(f"  CPU: {metrics['cpu_percent']:.1f}%")
            report.append(f"  Memory: {metrics['memory_percent']:.1f}% ({metrics['memory_used_mb']:.0f} MB)")
            report.append(f"  Disk: {metrics['disk_percent']:.1f}%")
            report.append(f"  Threads: {metrics['thread_count']}")

        # Performance
        if status['current_metrics']['performance']:
            metrics = status['current_metrics']['performance']
            report.append("\nPERFORMANCE:")
            report.append(f"  Event Latency: {metrics['event_latency_ms']:.1f} ms")
            report.append(f"  Error Rate: {metrics['error_rate']:.2%}")
            report.append(f"  Events/sec: {metrics['events_per_second']:.1f}")

        # Component health
        report.append("\nCOMPONENT HEALTH:")
        for comp, health in status['component_health'].items():
            report.append(f"  {comp}: {health['status']} - {health['message']}")

        # Active alerts
        if status['alerts']:
            report.append("\nACTIVE ALERTS:")
            for alert in status['alerts']:
                report.append(f"  [{alert['level']}] {alert['metric']}: {alert['message']}")

        # Recent errors
        recent_errors = [e for e in self.error_tracker if
                        (datetime.datetime.now() - e['timestamp']).seconds < 300]
        if recent_errors:
            report.append(f"\nRECENT ERRORS (last 5 min): {len(recent_errors)}")
            for error in recent_errors[-5:]:  # Last 5 errors
                report.append(f"  {error['timestamp']}: {error['error'][:100]}")

        report.append("\n" + "=" * 60)

        return "\n".join(report)

    # ==========================================================================
    # UTILITIES
    # ==========================================================================
    def _calculate_overall_health(self) -> HealthStatus:
        """Calculate overall system health"""
        # Check active alerts
        critical_alerts = sum(1 for a in self.active_alerts.values()
                            if a.level == AlertLevel.CRITICAL)
        warning_alerts = sum(1 for a in self.active_alerts.values()
                           if a.level == AlertLevel.WARNING)

        if critical_alerts > 0:
            return HealthStatus.CRITICAL
        elif warning_alerts > 0:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY

    def _cleanup_old_data(self) -> None:
        """Clean up old monitoring data"""
        # Metrics are automatically cleaned by deque maxlen

        # Clean old errors
        cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=1)
        self.error_tracker = deque(
            (e for e in self.error_tracker if e['timestamp'] > cutoff_time),
            maxlen=1000
        )

    def force_garbage_collection(self) -> dict[str, Any]:
        """
        Force garbage collection and return stats.

        Returns:
            GC statistics
        """
        before = self.process.memory_info().rss
        collected = gc.collect()
        after = self.process.memory_info().rss

        freed_mb = (before - after) / 1024 / 1024

        stats = {
            'objects_collected': collected,
            'memory_freed_mb': freed_mb,
            'memory_before_mb': before / 1024 / 1024,
            'memory_after_mb': after / 1024 / 1024
        }

        self.logger.info(f"Garbage collection: {collected} objects, {freed_mb:.1f} MB freed")

        return stats

    def _register_event_handlers(self) -> None:
        """Register event handlers with event manager"""
        try:
            # Import here to avoid circular dependency
            from SpyderA_Core.SpyderA05_EventManager import EventType

            # Subscribe to relevant events
            self.event_manager.subscribe(
                EventType.TRADE_EXECUTED,
                lambda e: self.order_counter.__add__(1)
            )

            self.event_manager.subscribe(
                EventType.MARKET_DATA,
                lambda e: self.event_counter.__add__(1)
            )

        except Exception as e:
            self.logger.warning(f"Could not register event handlers: {e}", exc_info=True)

    def _emit_alert_event(self, alert: SystemAlert) -> None:
        """Emit alert event to event manager"""
        if self.event_manager:
            try:
                # Import here to avoid circular dependency
                from SpyderA_Core.SpyderA05_EventManager import EventType

                self.event_manager.publish(
                    EventType.SYSTEM_ALERT,
                    {
                        'alert_id': alert.alert_id,
                        'level': alert.level.value,
                        'metric': alert.metric_type.value,
                        'message': alert.message,
                        'value': alert.value,
                        'threshold': alert.threshold
                    }
                )
            except Exception as e:
                self.logger.error(f"Failed to emit alert event: {e}", exc_info=True)

# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test system monitor
    monitor = SystemMonitor()

    # Start monitoring
    monitor.start()

    # Simulate some activity
    for i in range(10):
        monitor.record_latency('event', 50 + i * 10)
        monitor.record_latency('order', 100 + i * 5)

        if i % 3 == 0:
            monitor.record_error(f"Test error {i}")

    # Wait a bit
    time.sleep(10)  # thread-safe: time.sleep() intentional

    # Get status
    status = monitor.get_system_status()

    # Get metrics summary
    summary = monitor.get_metrics_summary(5)

    # Generate report
    report = monitor.generate_diagnostic_report()

    # Stop
    monitor.stop()



def get_system_monitor(*args, **kwargs):
    """Factory function to get SystemMonitor instance"""
    return SystemMonitor(*args, **kwargs)

