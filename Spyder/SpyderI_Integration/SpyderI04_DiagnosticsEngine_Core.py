#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderI_Integration
Module: SpyderI04_DiagnosticsEngine_Core.py
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
from datetime import datetime, timedelta, timezone
from typing import Any
from dataclasses import asdict
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
from Spyder.SpyderU_Utilities.SpyderU15_PerformanceMetrics import (

    PerformanceCalculator as PerformanceMetrics,
)
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType, Event

# Import diagnostic components
from Spyder.SpyderI_Integration.SpyderI10_DiagnosticsEngine_Types import (
    DiagnosticReport,
    DiagnosticIssue,
    HealthStatus,
)
from Spyder.SpyderI_Integration.SpyderI09_DiagnosticsEngine_HealthChecks import (
    HealthCheckManager,
)
from Spyder.SpyderI_Integration.SpyderI08_DiagnosticsEngine_DataCollector import DataCollector
from Spyder.SpyderI_Integration.SpyderI05_DiagnosticsEngine_Analyzers import AnalysisManager
from Spyder.SpyderI_Integration.SpyderI11_DiagnosticsEngine_Utils import DiagnosticUtils

# Integration components
try:
    from SpyderI_Integration.SpyderI01_IntegrationHub import get_integration_hub

    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
HEALTH_CHECK_INTERVAL = 30  # seconds
PERFORMANCE_ANALYSIS_INTERVAL = 60  # seconds
DEEP_ANALYSIS_INTERVAL = 300  # 5 minutes


# ==============================================================================
# MAIN DIAGNOSTICS ENGINE
# ==============================================================================
class DiagnosticsEngine:
    """
    Core diagnostics engine for SPYDER ecosystem health monitoring.

    This engine coordinates all diagnostic activities including health checks,
    performance monitoring, issue detection, and report generation.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        event_manager: Event manager for notifications

    Example:
        >>> diagnostics = DiagnosticsEngine()
        >>> diagnostics.start_monitoring()
        >>> health_report = diagnostics.run_comprehensive_diagnosis()
        >>> issues = diagnostics.detect_issues()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize the Diagnostics Engine.

        Args:
            config: Configuration dictionary
        """
        # Core components
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        self.event_manager = get_event_manager()
        self.performance_metrics = PerformanceMetrics()

        # Configuration
        self.config = config or {}
        self.monitoring_enabled = self.config.get("monitoring_enabled", True)
        self.deep_analysis_enabled = self.config.get("deep_analysis_enabled", True)
        self.auto_healing_enabled = self.config.get("auto_healing_enabled", False)

        # Initialize components
        self.health_check_manager = HealthCheckManager(self.config)
        self.data_collector = DataCollector(self.config)
        self.analysis_manager = AnalysisManager(self.config)
        self.diagnostic_utils = DiagnosticUtils()

        # Monitoring control
        self.is_monitoring = False
        self._stop_event = threading.Event()
        self.monitoring_threads: dict[str, threading.Thread] = {}
        self.thread_pool = ThreadPoolExecutor(max_workers=5)

        # Issue tracking
        self.active_issues: dict[str, DiagnosticIssue] = {}

        # Register with integration hub
        if HUB_AVAILABLE:
            hub = get_integration_hub()
            if hub:
                hub.register_module(self, dependencies=["SpyderI01_IntegrationHub"])

        self.logger.info("DiagnosticsEngine initialized successfully")

    # ==========================================================================
    # PUBLIC METHODS - MONITORING CONTROL
    # ==========================================================================

    def start_monitoring(self) -> bool:
        """
        Start comprehensive health monitoring.

        Returns:
            Success status
        """
        try:
            if self.is_monitoring:
                self.logger.warning("Monitoring already active")
                return True

            self.is_monitoring = True
            self._stop_event.clear()

            # Start monitoring threads
            monitoring_tasks = {
                "health_monitor": self._health_monitoring_loop,
                "performance_monitor": self._performance_monitoring_loop,
                "analysis_monitor": self._analysis_monitoring_loop,
            }

            for task_name, task_func in monitoring_tasks.items():
                thread = threading.Thread(
                    target=task_func, daemon=True, name=f"Diagnostics_{task_name}"
                )
                thread.start()
                self.monitoring_threads[task_name] = thread

            self.logger.info("Started comprehensive health monitoring")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "start_monitoring")
            return False

    def stop_monitoring(self) -> bool:
        """
        Stop health monitoring.

        Returns:
            Success status
        """
        try:
            self.is_monitoring = False
            self._stop_event.set()

            # Wait for threads to complete
            for thread_name, thread in self.monitoring_threads.items():
                if thread.is_alive():
                    thread.join(timeout=5.0)
                    if thread.is_alive():
                        self.logger.warning(
                            "Thread %s did not stop gracefully", thread_name
                        )

            self.monitoring_threads.clear()
            self.thread_pool.shutdown(wait=True)

            self.logger.info("Stopped health monitoring")
            return True

        except Exception as e:
            self.error_handler.handle_error(e, "stop_monitoring")
            return False

    # ==========================================================================
    # PUBLIC METHODS - DIAGNOSTIC OPERATIONS
    # ==========================================================================

    def run_comprehensive_diagnosis(self) -> DiagnosticReport:
        """
        Run comprehensive system diagnosis.

        Returns:
            Detailed diagnostic report
        """
        try:
            report_id = f"diag_{int(time.time())}"

            # Collect current data
            system_metrics = self.data_collector.collect_system_metrics()
            module_health = self.data_collector.collect_module_health()
            integration_health = self.data_collector.collect_integration_health()

            # Run all diagnostic checks
            issues = self.detect_issues()

            # Analyze performance
            performance_summary = self.analysis_manager.analyze_performance()

            # Calculate overall health score
            health_score = self.diagnostic_utils.calculate_overall_health_score(
                system_metrics, module_health, integration_health, issues
            )

            # Generate recommendations
            recommendations = self.diagnostic_utils.generate_recommendations(
                issues, performance_summary
            )

            # Create executive summary
            executive_summary = self.diagnostic_utils.create_executive_summary(
                health_score, issues, performance_summary
            )

            # Create report
            report = DiagnosticReport(
                report_id=report_id,
                generated_at=datetime.now(timezone.utc),
                overall_health_score=health_score,
                system_metrics=system_metrics,
                module_health=module_health,
                integration_health=integration_health,
                identified_issues=issues,
                performance_summary=performance_summary,
                recommendations=recommendations,
                executive_summary=executive_summary,
            )

            # Store report
            self.data_collector.store_diagnostic_report(report)

            # Emit diagnostic event
            self.event_manager.emit_event(
                Event(
                    type=EventType.SYSTEM_DIAGNOSTIC,
                    source=self.__class__.__name__,
                    data={"report": asdict(report)},
                )
            )

            return report

        except Exception as e:
            self.error_handler.handle_error(e, "run_comprehensive_diagnosis")
            raise

    def detect_issues(self) -> list[DiagnosticIssue]:
        """
        Detect system issues across all categories.

        Returns:
            List of detected issues
        """
        try:
            # Run all health checks
            all_issues = self.health_check_manager.run_all_checks()

            # Run advanced analysis if enabled
            if self.deep_analysis_enabled:
                analysis_issues = self.analysis_manager.run_advanced_analysis()
                all_issues.extend(analysis_issues)

            # Update active issues
            self._update_active_issues(all_issues)

            return all_issues

        except Exception as e:
            self.error_handler.handle_error(e, "detect_issues")
            return []

    def get_health_summary(self) -> dict[str, Any]:
        """
        Get current health summary.

        Returns:
            Health summary dictionary
        """
        try:
            # Collect latest metrics
            system_metrics = self.data_collector.collect_system_metrics()

            # Get module count and health
            if HUB_AVAILABLE:
                hub = get_integration_hub()
                module_count = len(hub.get_registered_modules()) if hub else 0
                healthy_modules = len(
                    [
                        m
                        for m in self.data_collector.collect_module_health()
                        if m.status in [HealthStatus.EXCELLENT, HealthStatus.GOOD]
                    ]
                )
            else:
                module_count = 0
                healthy_modules = 0

            # Count active issues by severity
            issue_counts = defaultdict(int)
            for issue in self.active_issues.values():
                issue_counts[issue.severity.value] += 1

            # Calculate overall health
            overall_health = self.diagnostic_utils.calculate_overall_health_score(
                system_metrics,
                self.data_collector.collect_module_health(),
                self.data_collector.collect_integration_health(),
                list(self.active_issues.values()),
            )

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "overall_health": overall_health,
                "system_status": {
                    "cpu_usage": f"{system_metrics.cpu_percent:.1f}%",
                    "memory_usage": f"{system_metrics.memory_percent:.1f}%",
                    "disk_usage": f"{system_metrics.disk_usage_percent:.1f}%",
                },
                "modules": {
                    "total": module_count,
                    "healthy": healthy_modules,
                    "health_rate": (
                        f"{(healthy_modules/module_count*100):.1f}%"
                        if module_count > 0
                        else "0%"
                    ),
                },
                "issues": {
                    "total_active": len(self.active_issues),
                    "critical": issue_counts["critical"],
                    "high": issue_counts["high"],
                    "medium": issue_counts["medium"],
                    "low": issue_counts["low"],
                },
            }

        except Exception as e:
            self.error_handler.handle_error(e, "get_health_summary")
            return {"error": str(e)}

    def get_active_issues(self) -> list[DiagnosticIssue]:
        """
        Get list of currently active issues.

        Returns:
            List of active diagnostic issues
        """
        return list(self.active_issues.values())

    def resolve_issue(self, issue_id: str) -> bool:
        """
        Mark an issue as resolved.

        Args:
            issue_id: ID of the issue to resolve

        Returns:
            Success status
        """
        try:
            if issue_id in self.active_issues:
                issue = self.active_issues[issue_id]
                issue.resolution_status = "resolved"
                del self.active_issues[issue_id]

                self.logger.info("Issue %s marked as resolved", issue_id)
                return True

            return False

        except Exception as e:
            self.error_handler.handle_error(e, f"resolve_issue: {issue_id}")
            return False

    # ==========================================================================
    # PRIVATE METHODS - MONITORING LOOPS
    # ==========================================================================

    def _health_monitoring_loop(self) -> None:
        """Main health monitoring loop"""
        while self.is_monitoring:
            try:
                # Run basic health checks
                issues = self.health_check_manager.run_basic_checks()

                # Update active issues
                if issues:
                    self._update_active_issues(issues)

                if self._stop_event.wait(timeout=HEALTH_CHECK_INTERVAL):
                    break

            except Exception as e:
                self.error_handler.handle_error(e, "_health_monitoring_loop")
                if self._stop_event.wait(timeout=10):
                    break

    def _performance_monitoring_loop(self) -> None:
        """Performance monitoring loop"""
        while self.is_monitoring:
            try:
                # Collect performance data
                self.data_collector.update_performance_history()

                # Check for performance issues
                performance_issues = (
                    self.health_check_manager.check_performance_health()
                )
                if performance_issues:
                    self._update_active_issues(performance_issues)

                if self._stop_event.wait(timeout=PERFORMANCE_ANALYSIS_INTERVAL):
                    break

            except Exception as e:
                self.error_handler.handle_error(e, "_performance_monitoring_loop")
                if self._stop_event.wait(timeout=30):
                    break

    def _analysis_monitoring_loop(self) -> None:
        """Advanced analysis monitoring loop"""
        while self.is_monitoring:
            try:
                # Run deep analysis periodically
                if self.deep_analysis_enabled:
                    analysis_issues = self.analysis_manager.run_advanced_analysis()
                    if analysis_issues:
                        self._update_active_issues(analysis_issues)

                # Clean up resolved issues
                self._cleanup_resolved_issues()

                if self._stop_event.wait(timeout=DEEP_ANALYSIS_INTERVAL):
                    break

            except Exception as e:
                self.error_handler.handle_error(e, "_analysis_monitoring_loop")
                if self._stop_event.wait(timeout=60):
                    break

    # ==========================================================================
    # PRIVATE METHODS - UTILITY
    # ==========================================================================

    def _update_active_issues(self, new_issues: list[DiagnosticIssue]) -> None:
        """Update active issues list"""
        try:
            for issue in new_issues:
                # Check if similar issue already exists
                existing_issue = self._find_similar_issue(issue)

                if existing_issue:
                    # Update existing issue
                    existing_issue.detected_at = issue.detected_at
                    existing_issue.description = issue.description
                else:
                    # Add new issue
                    self.active_issues[issue.issue_id] = issue

                    # Emit issue event
                    self.event_manager.emit_event(
                        Event(
                            type=EventType.DIAGNOSTIC_ISSUE,
                            source=self.__class__.__name__,
                            data={"issue": asdict(issue)},
                        )
                    )

        except Exception as e:
            self.error_handler.handle_error(e, "_update_active_issues")

    def _find_similar_issue(self, issue: DiagnosticIssue) -> DiagnosticIssue | None:
        """Find similar existing issue"""
        for existing_issue in self.active_issues.values():
            if (
                existing_issue.category == issue.category
                and existing_issue.title == issue.title
                and set(existing_issue.affected_components)
                == set(issue.affected_components)
            ):
                return existing_issue
        return None

    def _cleanup_resolved_issues(self) -> None:
        """Clean up resolved issues"""
        try:
            current_time = datetime.now(timezone.utc)
            resolved_issues = []

            for issue_id, issue in list(self.active_issues.items()):
                # Check if issue is old and potentially resolved
                if current_time - issue.detected_at > timedelta(hours=1):
                    # Re-check if the issue still exists
                    if not self.health_check_manager.issue_still_exists(issue):
                        issue.resolution_status = "auto_resolved"
                        resolved_issues.append(issue)
                        del self.active_issues[issue_id]

            if resolved_issues:
                self.logger.info("Auto-resolved %s issues", len(resolved_issues))

        except Exception as e:
            self.error_handler.handle_error(e, "_cleanup_resolved_issues")


# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def get_diagnostics_engine(
    config: dict[str, Any] | None = None,
) -> DiagnosticsEngine:
    """
    Get or create the global diagnostics engine instance.

    Args:
        config: Configuration dictionary

    Returns:
        DiagnosticsEngine instance
    """
    global _diagnostics_engine

    if "_diagnostics_engine" not in globals():
        _diagnostics_engine = DiagnosticsEngine(config)

    return _diagnostics_engine


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================

# Module-level initialization
_diagnostics_engine = None

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code

    # Create diagnostics engine
    diagnostics = DiagnosticsEngine()

    # Start monitoring
    success = diagnostics.start_monitoring()

    # Wait a bit
    time.sleep(2)  # thread-safe: time.sleep() intentional

    # Get health summary
    summary = diagnostics.get_health_summary()
    for _key, _value in summary.items():
        pass

    # Run diagnosis
    report = diagnostics.run_comprehensive_diagnosis()

    # Stop monitoring
    success = diagnostics.stop_monitoring()

