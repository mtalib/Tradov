#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovI_Integration
Module: TradovI09_DiagnosticsEngine_HealthChecks.py
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
import time
from typing import Any
from collections.abc import Callable

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import socket
import subprocess
import platform
import importlib

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovU_Utilities.TradovU02_ErrorHandler import TradovErrorHandler
from Tradov.TradovI_Integration.TradovI10_DiagnosticsEngine_Types import (

    DiagnosticIssue, DiagnosticCategory, ProblemSeverity, HealthStatus,
    CPU_USAGE_WARNING, CPU_USAGE_CRITICAL,
    MEMORY_USAGE_WARNING, MEMORY_USAGE_CRITICAL,
    DISK_USAGE_CRITICAL,
    NETWORK_LATENCY_CRITICAL,
    PACKET_LOSS_CRITICAL
)

# Integration components
try:
    from TradovI_Integration.TradovI01_IntegrationHub import get_integration_hub
    from TradovI_Integration.TradovI03_ConfigManager import get_global_config_manager
    HUB_AVAILABLE = True
except ImportError:
    HUB_AVAILABLE = False

# ==============================================================================
# HEALTH CHECK MANAGER
# ==============================================================================

class HealthCheckManager:
    """
    Manager for all health check operations.

    Coordinates different types of health checks and provides
    unified interface for running diagnostic checks.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """
        Initialize health check manager.

        Args:
            config: Configuration dictionary
        """
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()
        self.config = config or {}

        # Initialize check implementations
        self.system_checker = SystemHealthChecker(self.config)
        self.network_checker = NetworkHealthChecker(self.config)
        self.module_checker = ModuleHealthChecker(self.config)
        self.integration_checker = IntegrationHealthChecker(self.config)
        self.performance_checker = PerformanceHealthChecker(self.config)
        self.config_checker = ConfigurationHealthChecker(self.config)
        self.dependency_checker = DependencyHealthChecker(self.config)

        # Map categories to checkers
        self.health_checkers: dict[DiagnosticCategory, Callable] = {
            DiagnosticCategory.SYSTEM: self.system_checker.check_health,
            DiagnosticCategory.NETWORK: self.network_checker.check_health,
            DiagnosticCategory.MODULES: self.module_checker.check_health,
            DiagnosticCategory.INTEGRATION: self.integration_checker.check_health,
            DiagnosticCategory.PERFORMANCE: self.performance_checker.check_health,
            DiagnosticCategory.CONFIGURATION: self.config_checker.check_health,
            DiagnosticCategory.DEPENDENCIES: self.dependency_checker.check_health
        }

        self.logger.info("HealthCheckManager initialized")

    def run_all_checks(self) -> list[DiagnosticIssue]:
        """
        Run all health checks.

        Returns:
            List of all detected issues
        """
        all_issues = []

        for category, checker in self.health_checkers.items():
            try:
                category_issues = checker()
                all_issues.extend(category_issues)
            except Exception as e:
                self.error_handler.handle_error(e, f"run_all_checks: {category.value}")

        return all_issues

    def run_basic_checks(self) -> list[DiagnosticIssue]:
        """
        Run basic health checks (system and network only).

        Returns:
            List of detected issues
        """
        issues = []

        try:
            # System checks
            issues.extend(self.system_checker.check_health())

            # Network checks
            issues.extend(self.network_checker.check_health())

        except Exception as e:
            self.error_handler.handle_error(e, "run_basic_checks")

        return issues

    def check_performance_health(self) -> list[DiagnosticIssue]:
        """
        Run performance-specific health checks.

        Returns:
            List of performance-related issues
        """
        try:
            return self.performance_checker.check_health()
        except Exception as e:
            self.error_handler.handle_error(e, "check_performance_health")
            return []

    def issue_still_exists(self, issue: DiagnosticIssue) -> bool:
        """
        Check if an issue still exists by re-running relevant checks.

        Args:
            issue: DiagnosticIssue to check

        Returns:
            True if issue still exists
        """
        try:
            if issue.category in self.health_checkers:
                current_issues = self.health_checkers[issue.category]()

                # Check if similar issue is still present
                for current_issue in current_issues:
                    if (current_issue.category == issue.category and
                        current_issue.title == issue.title):
                        return True

            return False

        except Exception:
            return True  # Assume issue exists if check fails

# ==============================================================================
# SYSTEM HEALTH CHECKER
# ==============================================================================

class SystemHealthChecker:
    """System-level health checks."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

    def check_health(self) -> list[DiagnosticIssue]:
        """Check system-level health."""
        issues = []

        try:
            # Import here to avoid circular dependencies
            from TradovI_Integration.TradovI08_DiagnosticsEngine_DataCollector import DataCollector

            collector = DataCollector()
            metrics = collector.collect_system_metrics()

            # CPU usage check
            if metrics.cpu_percent > CPU_USAGE_CRITICAL:
                issues.append(DiagnosticIssue(
                    issue_id=f"cpu_critical_{int(time.time())}",
                    category=DiagnosticCategory.SYSTEM,
                    severity=ProblemSeverity.CRITICAL,
                    title="Critical CPU Usage",
                    description=f"CPU usage is at {metrics.cpu_percent:.1f}%, exceeding critical threshold",  # noqa: E501
                    affected_components=["system"],
                    symptoms=["High CPU usage", "System slowdown"],
                    recommendations=["Identify CPU-intensive processes", "Scale resources", "Optimize algorithms"],  # noqa: E501
                    impact_score=0.9
                ))
            elif metrics.cpu_percent > CPU_USAGE_WARNING:
                issues.append(DiagnosticIssue(
                    issue_id=f"cpu_warning_{int(time.time())}",
                    category=DiagnosticCategory.SYSTEM,
                    severity=ProblemSeverity.MEDIUM,
                    title="High CPU Usage",
                    description=f"CPU usage is at {metrics.cpu_percent:.1f}%, approaching critical levels",  # noqa: E501
                    affected_components=["system"],
                    symptoms=["Elevated CPU usage"],
                    recommendations=["Monitor CPU usage trends", "Consider optimization"],
                    impact_score=0.6
                ))

            # Memory usage check
            if metrics.memory_percent > MEMORY_USAGE_CRITICAL:
                issues.append(DiagnosticIssue(
                    issue_id=f"memory_critical_{int(time.time())}",
                    category=DiagnosticCategory.SYSTEM,
                    severity=ProblemSeverity.CRITICAL,
                    title="Critical Memory Usage",
                    description=f"Memory usage is at {metrics.memory_percent:.1f}%, system may become unstable",  # noqa: E501
                    affected_components=["system"],
                    symptoms=["High memory usage", "Potential OOM errors"],
                    recommendations=["Free memory", "Restart memory-intensive processes", "Add more RAM"],  # noqa: E501
                    impact_score=0.95
                ))
            elif metrics.memory_percent > MEMORY_USAGE_WARNING:
                issues.append(DiagnosticIssue(
                    issue_id=f"memory_warning_{int(time.time())}",
                    category=DiagnosticCategory.SYSTEM,
                    severity=ProblemSeverity.MEDIUM,
                    title="High Memory Usage",
                    description=f"Memory usage is at {metrics.memory_percent:.1f}%",
                    affected_components=["system"],
                    symptoms=["Elevated memory usage"],
                    recommendations=["Monitor memory trends", "Check for memory leaks"],
                    impact_score=0.5
                ))

            # Disk usage check
            if metrics.disk_usage_percent > DISK_USAGE_CRITICAL:
                issues.append(DiagnosticIssue(
                    issue_id=f"disk_critical_{int(time.time())}",
                    category=DiagnosticCategory.SYSTEM,
                    severity=ProblemSeverity.CRITICAL,
                    title="Critical Disk Usage",
                    description=f"Disk usage is at {metrics.disk_usage_percent:.1f}%, system may fail",  # noqa: E501
                    affected_components=["system"],
                    symptoms=["Very high disk usage", "Write failures possible"],
                    recommendations=["Free disk space immediately", "Clean logs", "Archive old data"],  # noqa: E501
                    impact_score=0.9
                ))

        except Exception as e:
            self.error_handler.handle_error(e, "SystemHealthChecker.check_health")

        return issues

# ==============================================================================
# NETWORK HEALTH CHECKER
# ==============================================================================

class NetworkHealthChecker:
    """Network connectivity health checks."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

    def check_health(self) -> list[DiagnosticIssue]:
        """Check network health."""
        issues = []

        try:
            # Test network connectivity
            latency = self._test_network_latency()
            packet_loss = self._test_packet_loss()

            if latency > NETWORK_LATENCY_CRITICAL:
                issues.append(DiagnosticIssue(
                    issue_id=f"network_latency_{int(time.time())}",
                    category=DiagnosticCategory.NETWORK,
                    severity=ProblemSeverity.HIGH,
                    title="High Network Latency",
                    description=f"Network latency is {latency:.1f}ms, affecting performance",
                    affected_components=["network"],
                    symptoms=["Slow network responses", "Timeouts"],
                    recommendations=["Check network configuration", "Test connection quality"],
                    impact_score=0.7
                ))

            if packet_loss > PACKET_LOSS_CRITICAL:
                issues.append(DiagnosticIssue(
                    issue_id=f"packet_loss_{int(time.time())}",
                    category=DiagnosticCategory.NETWORK,
                    severity=ProblemSeverity.HIGH,
                    title="High Packet Loss",
                    description=f"Packet loss is {packet_loss:.1f}%, connections may be unstable",
                    affected_components=["network"],
                    symptoms=["Connection drops", "Data transmission errors"],
                    recommendations=["Check network hardware", "Investigate network path"],
                    impact_score=0.8
                ))

        except Exception as e:
            self.error_handler.handle_error(e, "NetworkHealthChecker.check_health")

        return issues

    def _test_network_latency(self) -> float:
        """Test network latency to external server."""
        try:
            # Test ping to Google DNS
            param = "-n" if platform.system().lower() == "windows" else "-c"
            command = ["ping", param, "1", "8.8.8.8"]

            result = subprocess.run(command, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                # Parse latency from ping output
                output = result.stdout
                if "time=" in output:
                    import re
                    match = re.search(r'time[=<](\d+(?:\.\d+)?)', output)
                    if match:
                        return float(match.group(1))

            return 1000.0  # High latency if ping fails

        except Exception:
            return 1000.0

    def _test_packet_loss(self) -> float:
        """Test packet loss percentage."""
        try:
            # Test ping with multiple packets
            param = "-n" if platform.system().lower() == "windows" else "-c"
            command = ["ping", param, "10", "8.8.8.8"]

            result = subprocess.run(command, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                output = result.stdout
                import re
                match = re.search(r'(\d+)% packet loss', output)
                if match:
                    return float(match.group(1))

            return 0.0

        except Exception:
            return 0.0

# ==============================================================================
# MODULE HEALTH CHECKER
# ==============================================================================

class ModuleHealthChecker:
    """Module-specific health checks."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

    def check_health(self) -> list[DiagnosticIssue]:
        """Check individual module health."""
        issues = []

        try:
            if not HUB_AVAILABLE:
                return issues

            hub = get_integration_hub()
            if not hub:
                return issues

            # Import here to avoid circular dependencies
            from TradovI_Integration.TradovI08_DiagnosticsEngine_DataCollector import DataCollector

            collector = DataCollector()
            module_health_list = collector.collect_module_health()

            for module_health in module_health_list:
                if module_health.status == HealthStatus.FAILING:
                    issues.append(DiagnosticIssue(
                        issue_id=f"module_failing_{module_health.module_id}_{int(time.time())}",
                        category=DiagnosticCategory.MODULES,
                        severity=ProblemSeverity.CRITICAL,
                        title=f"Module {module_health.module_name} Failing",
                        description=f"Module {module_health.module_name} is in failing state",
                        affected_components=[module_health.module_id],
                        symptoms=["Module not responding", "High error rate", "No heartbeat"],
                        recommendations=["Restart module", "Check module logs", "Verify dependencies"],  # noqa: E501
                        impact_score=0.8
                    ))
                elif module_health.status == HealthStatus.CRITICAL:
                    issues.append(DiagnosticIssue(
                        issue_id=f"module_critical_{module_health.module_id}_{int(time.time())}",
                        category=DiagnosticCategory.MODULES,
                        severity=ProblemSeverity.HIGH,
                        title=f"Module {module_health.module_name} Critical",
                        description=f"Module {module_health.module_name} performance is degraded",
                        affected_components=[module_health.module_id],
                        symptoms=["Slow responses", "Increased errors"],
                        recommendations=["Monitor module closely", "Check resource usage"],
                        impact_score=0.6
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, "ModuleHealthChecker.check_health")

        return issues

# ==============================================================================
# INTEGRATION HEALTH CHECKER
# ==============================================================================

class IntegrationHealthChecker:
    """Inter-module integration health checks."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

    def check_health(self) -> list[DiagnosticIssue]:
        """Check inter-module integration health."""
        issues = []

        try:
            if not HUB_AVAILABLE:
                return issues

            hub = get_integration_hub()
            if not hub:
                return issues

            # Import here to avoid circular dependencies
            from TradovI_Integration.TradovI08_DiagnosticsEngine_DataCollector import DataCollector

            collector = DataCollector()
            integration_health_list = collector.collect_integration_health()

            for integration_health in integration_health_list:
                if integration_health.connection_status == HealthStatus.FAILING:
                    issues.append(DiagnosticIssue(
                        issue_id=f"integration_failing_{integration_health.source_module}_{integration_health.target_module}_{int(time.time())}",
                        category=DiagnosticCategory.INTEGRATION,
                        severity=ProblemSeverity.HIGH,
                        title=f"Integration Failure: {integration_health.source_module} → {integration_health.target_module}",  # noqa: E501
                        description=f"Communication between {integration_health.source_module} and {integration_health.target_module} is failing",  # noqa: E501
                        affected_components=[integration_health.source_module, integration_health.target_module],  # noqa: E501
                        symptoms=["Connection failures", "Message delivery issues"],
                        recommendations=["Check network connectivity", "Verify module status", "Restart modules"],  # noqa: E501
                        impact_score=0.7
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, "IntegrationHealthChecker.check_health")

        return issues

# ==============================================================================
# PERFORMANCE HEALTH CHECKER
# ==============================================================================

class PerformanceHealthChecker:
    """Performance-related health checks."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

    def check_health(self) -> list[DiagnosticIssue]:
        """Check performance-related health."""
        issues = []

        try:
            # Import here to avoid circular dependencies
            from TradovI_Integration.TradovI08_DiagnosticsEngine_DataCollector import DataCollector

            collector = DataCollector()

            # Check for performance degradation trends
            cpu_trend = collector.get_system_health_trend()
            if cpu_trend == "degrading":
                issues.append(DiagnosticIssue(
                    issue_id=f"performance_degrading_{int(time.time())}",
                    category=DiagnosticCategory.PERFORMANCE,
                    severity=ProblemSeverity.MEDIUM,
                    title="Performance Degradation Detected",
                    description="System performance is showing degrading trends",
                    affected_components=["system"],
                    symptoms=["Increasing resource usage", "Slower response times"],
                    recommendations=["Investigate recent changes", "Monitor resource usage"],
                    impact_score=0.5
                ))

        except Exception as e:
            self.error_handler.handle_error(e, "PerformanceHealthChecker.check_health")

        return issues

# ==============================================================================
# CONFIGURATION HEALTH CHECKER
# ==============================================================================

class ConfigurationHealthChecker:
    """Configuration-related health checks."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

    def check_health(self) -> list[DiagnosticIssue]:
        """Check configuration-related health."""
        issues = []

        try:
            if not HUB_AVAILABLE:
                return issues

            config_manager = get_global_config_manager()
            if not config_manager:
                return issues

            # Check for configuration inconsistencies
            configs = config_manager.configs

            for config_name, config_data in configs.items():
                if not self._validate_configuration(config_name, config_data):
                    issues.append(DiagnosticIssue(
                        issue_id=f"config_invalid_{config_name}_{int(time.time())}",
                        category=DiagnosticCategory.CONFIGURATION,
                        severity=ProblemSeverity.MEDIUM,
                        title=f"Invalid Configuration: {config_name}",
                        description=f"Configuration {config_name} contains invalid or inconsistent values",  # noqa: E501
                        affected_components=[config_name],
                        symptoms=["Configuration warnings", "Module errors"],
                        recommendations=["Review configuration", "Fix invalid values"],
                        impact_score=0.4
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, "ConfigurationHealthChecker.check_health")

        return issues

    def _validate_configuration(self, config_name: str, config_data: dict[str, Any]) -> bool:
        """Validate configuration data."""
        try:
            if not isinstance(config_data, dict):
                return False

            # Check for required fields based on config type
            required_fields = {
                'trading_engine': ['enabled', 'max_positions'],
                'risk_manager': ['max_loss', 'position_limits'],
                'data_feed': ['provider', 'update_frequency']
            }

            if config_name in required_fields:
                for field in required_fields[config_name]:
                    if field not in config_data:
                        return False

            return True

        except Exception:
            return False

# ==============================================================================
# DEPENDENCY HEALTH CHECKER
# ==============================================================================

class DependencyHealthChecker:
    """Dependency health checks."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = TradovLogger.get_logger(self.__class__.__name__)
        self.error_handler = TradovErrorHandler()

    def check_health(self) -> list[DiagnosticIssue]:
        """Check dependency health."""
        issues = []

        try:
            # Check Python package dependencies
            missing_packages = self._check_python_dependencies()

            for package in missing_packages:
                issues.append(DiagnosticIssue(
                    issue_id=f"missing_dependency_{package}_{int(time.time())}",
                    category=DiagnosticCategory.DEPENDENCIES,
                    severity=ProblemSeverity.HIGH,
                    title=f"Missing Dependency: {package}",
                    description=f"Required Python package {package} is not installed",
                    affected_components=["system"],
                    symptoms=["Import errors", "Module failures"],
                    recommendations=[f"Install {package}", "Update requirements"],
                    impact_score=0.8
                ))

            # Check external service dependencies
            external_services = ['Database', 'Redis']  # Legacy broker removed

            for service in external_services:
                if not self._check_external_service(service):
                    issues.append(DiagnosticIssue(
                        issue_id=f"service_unavailable_{service}_{int(time.time())}",
                        category=DiagnosticCategory.DEPENDENCIES,
                        severity=ProblemSeverity.HIGH,
                        title=f"External Service Unavailable: {service}",
                        description=f"External service {service} is not accessible",
                        affected_components=["external_services"],
                        symptoms=["Connection failures", "Service timeouts"],
                        recommendations=[f"Check {service} status", "Verify network connectivity"],
                        impact_score=0.7
                    ))

        except Exception as e:
            self.error_handler.handle_error(e, "DependencyHealthChecker.check_health")

        return issues

    def _check_python_dependencies(self) -> list[str]:
        """Check for missing Python dependencies."""
        missing = []

        required_packages = [
            'numpy', 'pandas', 'psutil', 'networkx',
            'matplotlib', 'seaborn', 'scipy'
        ]

        for package in required_packages:
            try:
                importlib.import_module(package)
            except ImportError:
                missing.append(package)

        return missing

    def _check_external_service(self, service_name: str) -> bool:
        """Check if external service is available."""
        try:
            service_ports = {
                'Database': 5432,
                'Redis': 6379
            }

            if service_name in service_ports:
                port = service_ports[service_name]
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex(('localhost', port))
                sock.close()
                return result == 0

            return True  # Default to available for unknown services

        except Exception:
            return False

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Module testing code

    # Create health check manager
    health_manager = HealthCheckManager()

    # Run basic checks
    basic_issues = health_manager.run_basic_checks()

    # Run all checks
    all_issues = health_manager.run_all_checks()

    # Display issues
    if all_issues:
        for _issue in all_issues[:5]:  # Show first 5
            pass

