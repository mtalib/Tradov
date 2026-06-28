#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovI_Integration
Module: TradovI08_DiagnosticsEngine_DataCollector.py
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
import os
import threading
from datetime import datetime, timedelta, UTC
from typing import Any
from collections import deque, defaultdict

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovI_Integration.TradovI10_DiagnosticsEngine_Types import (

    SystemMetrics, ModuleHealth, IntegrationHealth, DiagnosticReport,
    HealthStatus, MAX_PERFORMANCE_SAMPLES, MAX_HEALTH_SNAPSHOTS, MAX_DIAGNOSTIC_HISTORY
)

# Integration components
try:
    from TradovI_Integration.TradovI01_IntegrationHub import get_integration_hub
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

# ==============================================================================
# DATA COLLECTOR CLASS
# ==============================================================================

class DataCollector:
    """
    Data collection manager for diagnostics engine.

    Handles collection of system metrics, module health data, integration
    status, and maintains historical data for analysis.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize data collector.

        Args:
            config: Configuration dictionary
        """
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()
        self.config = config or {}

        # Data storage
        self.system_metrics_history: deque = deque(maxlen=MAX_PERFORMANCE_SAMPLES)
        self.module_health_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=MAX_HEALTH_SNAPSHOTS)
        )
        self.integration_health_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=MAX_HEALTH_SNAPSHOTS)
        )
        self.diagnostic_history: deque = deque(maxlen=MAX_DIAGNOSTIC_HISTORY)

        # Data lock for thread safety
        self._data_lock = threading.RLock()

        self.logger.info("DataCollector initialized")

    # ==========================================================================
    # SYSTEM METRICS COLLECTION
    # ==========================================================================

    def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect current system metrics.

        Returns:
            SystemMetrics instance with current data
        """
        try:
            # Get system metrics using psutil
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            network = psutil.net_io_counters()

            # Get process information
            process_count = len(psutil.pids())

            # Get load average (Unix systems)
            load_avg = None
            try:
                load_avg = os.getloadavg()
            except (OSError, AttributeError):
                pass  # Not available on Windows

            # Get file descriptors count
            file_descriptors = 0
            try:
                file_descriptors = len(psutil.Process().open_files())
            except (psutil.Error, AttributeError):
                pass

            metrics = SystemMetrics(
                timestamp=datetime.now(UTC),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                disk_usage_percent=disk.percent,
                network_sent_bytes=network.bytes_sent,
                network_recv_bytes=network.bytes_recv,
                active_connections=len(psutil.net_connections()),
                process_count=process_count,
                thread_count=threading.active_count(),
                file_descriptors=file_descriptors,
                load_average=load_avg
            )

            # Store in history
            with self._data_lock:
                self.system_metrics_history.append(metrics)

            return metrics

        except Exception as e:
            self.error_handler.handle_error(e, "collect_system_metrics")
            # Return default metrics on error
            return SystemMetrics(
                timestamp=datetime.now(UTC),
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_usage_percent=0.0,
                network_sent_bytes=0,
                network_recv_bytes=0,
                active_connections=0,
                process_count=0,
                thread_count=0,
                file_descriptors=0
            )

    def get_system_metrics_history(self, duration: timedelta | None = None) -> list[SystemMetrics]:
        """
        Get historical system metrics.

        Args:
            duration: Time duration to retrieve (None for all)

        Returns:
            List of SystemMetrics
        """
        with self._data_lock:
            if duration is None:
                return list(self.system_metrics_history)

            cutoff_time = datetime.now(UTC) - duration
            return [
                metric for metric in self.system_metrics_history
                if metric.timestamp >= cutoff_time
            ]

    # ==========================================================================
    # MODULE HEALTH COLLECTION
    # ==========================================================================

    def collect_module_health(self) -> list[ModuleHealth]:
        """
        Collect health status of all modules.

        Returns:
            List of ModuleHealth instances
        """
        module_health_list = []

        try:
            if not HUB_AVAILABLE:
                return module_health_list

            hub = get_integration_hub()
            if not hub:
                return module_health_list

            modules = hub.get_registered_modules()

            for module_id, module_info in modules.items():
                health = self._assess_module_health(module_id, module_info)
                module_health_list.append(health)

                # Store in history
                with self._data_lock:
                    self.module_health_history[module_id].append(health)

        except Exception as e:
            self.error_handler.handle_error(e, "collect_module_health")

        return module_health_list

    def get_module_health_history(self, module_id: str,
                                 duration: timedelta | None = None) -> list[ModuleHealth]:
        """
        Get historical health data for a specific module.

        Args:
            module_id: Module identifier
            duration: Time duration to retrieve (None for all)

        Returns:
            List of ModuleHealth instances
        """
        with self._data_lock:
            if module_id not in self.module_health_history:
                return []

            history = self.module_health_history[module_id]

            if duration is None:
                return list(history)

            cutoff_time = datetime.now(UTC) - duration
            return [
                health for health in history
                if health.last_heartbeat >= cutoff_time
            ]

    def _assess_module_health(self, module_id: str, module_info: dict[str, Any]) -> ModuleHealth:
        """
        Assess health of a single module.

        Args:
            module_id: Module identifier
            module_info: Module information dictionary

        Returns:
            ModuleHealth instance
        """
        try:
            # In a real implementation, this would query actual module metrics
            # For now, we'll simulate some reasonable values

            # Simulate response time based on module type
            base_response_time = 50.0  # Base 50ms
            response_time = base_response_time + np.random.uniform(0, 50)

            # Simulate error rate (usually low)
            error_rate = max(0, np.random.normal(2.0, 1.0))  # Mean 2%, std 1%

            # Simulate memory usage (50-500MB)
            memory_usage = np.random.randint(50 * 1024 * 1024, 500 * 1024 * 1024)

            # Simulate CPU usage (1-25%)
            cpu_usage = max(0, np.random.normal(10.0, 5.0))

            # Determine status based on metrics
            if response_time > 5000 or error_rate > 15:
                status = HealthStatus.FAILING
            elif response_time > 1000 or error_rate > 5:
                status = HealthStatus.CRITICAL
            elif response_time > 500 or error_rate > 2:
                status = HealthStatus.WARNING
            elif response_time < 100 and error_rate < 1:
                status = HealthStatus.EXCELLENT
            else:
                status = HealthStatus.GOOD

            # Generate other metrics
            processed_requests = np.random.randint(1000, 50000)
            failed_requests = int(processed_requests * error_rate / 100)

            return ModuleHealth(
                module_id=module_id,
                module_name=module_info.get('name', module_id),
                status=status,
                response_time=response_time,
                error_rate=error_rate,
                memory_usage=memory_usage,
                cpu_usage=cpu_usage,
                last_heartbeat=datetime.now(UTC),
                active_connections=np.random.randint(0, 20),
                processed_requests=processed_requests,
                failed_requests=failed_requests,
                uptime=timedelta(seconds=np.random.randint(3600, 86400 * 7)),
                dependencies_healthy=True,
                configuration_valid=True
            )

        except Exception as e:
            self.error_handler.handle_error(e, f"_assess_module_health: {module_id}")
            # Return failing health on error
            return ModuleHealth(
                module_id=module_id,
                module_name=module_id,
                status=HealthStatus.FAILING,
                response_time=0.0,
                error_rate=100.0,
                memory_usage=0,
                cpu_usage=0.0,
                last_heartbeat=datetime.now(UTC),
                active_connections=0,
                processed_requests=0,
                failed_requests=0,
                uptime=timedelta(0),
                dependencies_healthy=False,
                configuration_valid=False
            )

    # ==========================================================================
    # INTEGRATION HEALTH COLLECTION
    # ==========================================================================

    def collect_integration_health(self) -> list[IntegrationHealth]:
        """
        Collect health status of module integrations.

        Returns:
            List of IntegrationHealth instances
        """
        integration_health_list = []

        try:
            if not HUB_AVAILABLE:
                return integration_health_list

            hub = get_integration_hub()
            if not hub:
                return integration_health_list

            # Get dependency graph
            dependency_graph = hub.get_dependency_graph()

            for source_module in dependency_graph.nodes():
                for target_module in dependency_graph.successors(source_module):
                    health = self._assess_integration_health(source_module, target_module)
                    integration_health_list.append(health)

                    # Store in history
                    integration_key = f"{source_module}_{target_module}"
                    with self._data_lock:
                        self.integration_health_history[integration_key].append(health)

        except Exception as e:
            self.error_handler.handle_error(e, "collect_integration_health")

        return integration_health_list

    def _assess_integration_health(self, source_module: str, target_module: str) -> IntegrationHealth:  # noqa: E501
        """
        Assess health of integration between two modules.

        Args:
            source_module: Source module identifier
            target_module: Target module identifier

        Returns:
            IntegrationHealth instance
        """
        try:
            # Simulate integration metrics
            latency = max(1.0, np.random.normal(25.0, 10.0))  # Mean 25ms, std 10ms
            throughput = max(1.0, np.random.normal(100.0, 30.0))  # Mean 100 msg/sec
            error_rate = max(0.0, np.random.normal(1.0, 0.5))  # Mean 1%, std 0.5%

            # Determine connection status
            if latency > 500 or error_rate > 10:
                status = HealthStatus.FAILING
            elif latency > 100 or error_rate > 5:
                status = HealthStatus.CRITICAL
            elif latency > 50 or error_rate > 2:
                status = HealthStatus.WARNING
            elif latency < 20 and error_rate < 0.5:
                status = HealthStatus.EXCELLENT
            else:
                status = HealthStatus.GOOD

            return IntegrationHealth(
                source_module=source_module,
                target_module=target_module,
                connection_status=status,
                latency=latency,
                throughput=throughput,
                error_rate=error_rate,
                last_communication=datetime.now(UTC),
                message_queue_size=np.random.randint(0, 100),
                retry_count=np.random.randint(0, 5),
                circuit_breaker_status="CLOSED" if status != HealthStatus.FAILING else "OPEN"
            )

        except Exception as e:
            self.error_handler.handle_error(e, f"_assess_integration_health: {source_module}->{target_module}")  # noqa: E501
            return IntegrationHealth(
                source_module=source_module,
                target_module=target_module,
                connection_status=HealthStatus.FAILING,
                latency=0.0,
                throughput=0.0,
                error_rate=100.0,
                last_communication=datetime.now(UTC),
                message_queue_size=0,
                retry_count=0,
                circuit_breaker_status="OPEN"
            )

    # ==========================================================================
    # DIAGNOSTIC REPORTS STORAGE
    # ==========================================================================

    def store_diagnostic_report(self, report: DiagnosticReport) -> None:
        """
        Store a diagnostic report in history.

        Args:
            report: DiagnosticReport to store
        """
        try:
            with self._data_lock:
                self.diagnostic_history.append(report)

            self.logger.debug("Stored diagnostic report %s", report.report_id)

        except Exception as e:
            self.error_handler.handle_error(e, "store_diagnostic_report")

    def get_diagnostic_reports(self, duration: timedelta | None = None) -> list[DiagnosticReport]:
        """
        Get historical diagnostic reports.

        Args:
            duration: Time duration to retrieve (None for all)

        Returns:
            List of DiagnosticReport instances
        """
        with self._data_lock:
            if duration is None:
                return list(self.diagnostic_history)

            cutoff_time = datetime.now(UTC) - duration
            return [
                report for report in self.diagnostic_history
                if report.generated_at >= cutoff_time
            ]

    # ==========================================================================
    # PERFORMANCE DATA UPDATES
    # ==========================================================================

    def update_performance_history(self) -> None:
        """Update performance history with current data."""
        try:
            # Collect current system metrics
            self.collect_system_metrics()

            # Collect current module health
            self.collect_module_health()

            # Collect current integration health
            self.collect_integration_health()

        except Exception as e:
            self.error_handler.handle_error(e, "update_performance_history")

    # ==========================================================================
    # DATA ANALYSIS HELPERS
    # ==========================================================================

    def get_average_cpu_usage(self, duration: timedelta | None = None) -> float:
        """
        Get average CPU usage over specified duration.

        Args:
            duration: Time duration to analyze

        Returns:
            Average CPU usage percentage
        """
        try:
            metrics = self.get_system_metrics_history(duration)
            if not metrics:
                return 0.0

            return sum(m.cpu_percent for m in metrics) / len(metrics)

        except Exception as e:
            self.error_handler.handle_error(e, "get_average_cpu_usage")
            return 0.0

    def get_average_memory_usage(self, duration: timedelta | None = None) -> float:
        """
        Get average memory usage over specified duration.

        Args:
            duration: Time duration to analyze

        Returns:
            Average memory usage percentage
        """
        try:
            metrics = self.get_system_metrics_history(duration)
            if not metrics:
                return 0.0

            return sum(m.memory_percent for m in metrics) / len(metrics)

        except Exception as e:
            self.error_handler.handle_error(e, "get_average_memory_usage")
            return 0.0

    def get_module_error_rate(self, module_id: str, duration: timedelta | None = None) -> float:
        """
        Get average error rate for a module over specified duration.

        Args:
            module_id: Module identifier
            duration: Time duration to analyze

        Returns:
            Average error rate percentage
        """
        try:
            health_data = self.get_module_health_history(module_id, duration)
            if not health_data:
                return 0.0

            return sum(h.error_rate for h in health_data) / len(health_data)

        except Exception as e:
            self.error_handler.handle_error(e, f"get_module_error_rate: {module_id}")
            return 0.0

    def get_system_health_trend(self, duration: timedelta = timedelta(hours=1)) -> str:
        """
        Get overall system health trend.

        Args:
            duration: Time duration to analyze

        Returns:
            Trend description ("improving", "degrading", "stable")
        """
        try:
            metrics = self.get_system_metrics_history(duration)
            if len(metrics) < 10:
                return "stable"

            # Analyze CPU trend
            cpu_values = [m.cpu_percent for m in metrics]
            cpu_trend = self._calculate_trend(cpu_values)

            # Analyze memory trend
            memory_values = [m.memory_percent for m in metrics]
            memory_trend = self._calculate_trend(memory_values)

            # Overall trend
            overall_trend = (cpu_trend + memory_trend) / 2

            if overall_trend > 5:
                return "degrading"
            elif overall_trend < -5:
                return "improving"
            else:
                return "stable"

        except Exception as e:
            self.error_handler.handle_error(e, "get_system_health_trend")
            return "stable"

    def _calculate_trend(self, values: list[float]) -> float:
        """
        Calculate trend in values (percentage change).

        Args:
            values: List of values to analyze

        Returns:
            Trend percentage (-100 to +100)
        """
        if len(values) < 2:
            return 0.0

        # Compare first half to second half
        mid_point = len(values) // 2
        first_half = values[:mid_point]
        second_half = values[mid_point:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if first_avg == 0:
            return 0.0

        return ((second_avg - first_avg) / first_avg) * 100

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================

def create_data_collector(config: dict[str, Any] | None = None) -> DataCollector:
    """
    Factory function to create data collector.

    Args:
        config: Configuration dictionary

    Returns:
        DataCollector instance
    """
    return DataCollector(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code

    # Create data collector
    collector = DataCollector()

    # Test system metrics collection
    metrics = collector.collect_system_metrics()

    # Test module health collection
    module_health = collector.collect_module_health()

    # Test integration health collection
    integration_health = collector.collect_integration_health()

    # Test trend analysis

