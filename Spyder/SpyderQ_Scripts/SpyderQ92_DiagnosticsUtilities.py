#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ92_DiagnosticsUtilities.py
Purpose: Consolidated diagnostics and system verification utilities
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-05 Time: 17:00:00

Module Description:
    This module provides comprehensive diagnostic and verification capabilities
    for the Spyder system. It includes module import verification, dependency
    checking, configuration validation, connectivity testing, performance
    benchmarking, and troubleshooting tools. Replaces multiple diagnostic
    scripts with a unified Python implementation for better integration.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import socket
import json
import importlib
import platform
import pkg_resources
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
import configparser
import sqlite3

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import psutil
    import requests  # noqa: F401
    import pandas as pd  # noqa: F401
    import numpy as np  # noqa: F401
except ImportError as e:
    print(f"Warning: Some imports failed: {e}")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add Spyder home to path if not already present
_DEFAULT_SPYDER_HOME = str(Path(__file__).resolve().parents[2])
SPYDER_HOME = os.environ.get("SPYDER_HOME", _DEFAULT_SPYDER_HOME)
if SPYDER_HOME not in sys.path:
    sys.path.insert(0, SPYDER_HOME)

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import utilities: {e}")
    import logging
    SpyderLogger = logging
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# System paths
LOGS_DIR = Path(SPYDER_HOME) / "logs"
DATA_DIR = Path(SPYDER_HOME) / "data"
CONFIG_DIR = Path(SPYDER_HOME) / "config"

# Module groups to verify
MODULE_GROUPS = {
    "SpyderA_Core": "Core system modules",
    "SpyderB_Broker": "Broker integration modules",
    "SpyderC_MarketData": "Market data modules",
    "SpyderD_Strategies": "Trading strategy modules",
    "SpyderE_RiskManagement": "Risk management modules",
    "SpyderF_Analysis": "Analysis modules",
    "SpyderG_GUI": "GUI modules",
    "SpyderH_WebAPI": "Web API modules",
    "SpyderI_Integration": "Integration modules",
    "SpyderJ_Backtesting": "Backtesting modules",
    "SpyderK_OrderExecution": "Order execution modules",
    "SpyderL_DataStorage": "Data storage modules",
    "SpyderM_Monitoring": "Monitoring modules",
    "SpyderN_Notifications": "Notification modules",
    "SpyderO_Optimization": "Optimization modules",
    "SpyderP_PortfolioManagement": "Portfolio management modules",
    "SpyderQ_Scripts": "Script modules",
    "SpyderR_Reporting": "Reporting modules",
    "SpyderS_Security": "Security modules",
    "SpyderT_Testing": "Testing modules",
    "SpyderU_Utilities": "Utility modules",
    "SpyderV_QuantModels": "Quant model modules",
    "SpyderW_MachineLearning": "Machine learning modules",
    "SpyderX_Agents": "Agent modules",
    "SpyderY_CloudServices": "Cloud service modules",
    "SpyderZ_Communication": "Communication modules"
}

# Required Python packages
REQUIRED_PACKAGES = [
    "pandas",
    "numpy",
    "psutil",
    "requests",
    "PySide6",
    "prometheus_client",
    "asyncio",
    "websockets",
    "sqlalchemy",
    "aiohttp",
    "matplotlib",
    "scipy"
]

# Configuration files to check
CONFIG_FILES = [
    "config.ini",
    ".env",
    "trading_config.json",
    "risk_parameters.json",
    "strategies.json"
]

# Network endpoints to test
NETWORK_ENDPOINTS = {
    "Tradier API": ("api.tradier.com", 443),
    "Tradier Sandbox": ("sandbox.tradier.com", 443),
    "Massive API": ("api.polygon.io", 443),
    "Prometheus": ("localhost", 9090),
    "Grafana": ("localhost", 3000),
    "Web Dashboard": ("localhost", 8080),
    "API Server": ("localhost", 5000)
}

# ==============================================================================
# ENUMS
# ==============================================================================
class DiagnosticStatus(Enum):
    """Status of diagnostic checks"""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"

class TestCategory(Enum):
    """Categories of diagnostic tests"""
    SYSTEM = "system"
    MODULES = "modules"
    DEPENDENCIES = "dependencies"
    CONFIGURATION = "configuration"
    CONNECTIVITY = "connectivity"
    DATABASE = "database"
    PERFORMANCE = "performance"
    SECURITY = "security"

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class DiagnosticResult:
    """Result of a diagnostic test"""
    test_name: str
    category: TestCategory
    status: DiagnosticStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class SystemInfo:
    """System information"""
    os: str
    python_version: str
    platform: str
    processor: str
    memory_gb: float
    disk_gb: float
    network_interfaces: list[str]

@dataclass
class ModuleInfo:
    """Information about a Spyder module"""
    name: str
    group: str
    importable: bool
    has_init: bool
    version: str | None
    dependencies: list[str]
    error: str | None

@dataclass
class DiagnosticReport:
    """Complete diagnostic report"""
    timestamp: datetime
    system_info: SystemInfo
    test_results: list[DiagnosticResult]
    summary: dict[str, int]
    recommendations: list[str]
    total_duration_ms: float

# ==============================================================================
# MAIN CLASS
# ==============================================================================
class DiagnosticsUtilities:
    """
    Comprehensive diagnostics and verification utilities for Spyder.

    This class provides complete system diagnostics including module
    verification, dependency checking, configuration validation,
    connectivity testing, and performance benchmarking. It helps
    identify and troubleshoot system issues.

    Attributes:
        logger: Module logger instance
        error_handler: Error handling instance
        results: List of diagnostic results

    Example:
        >>> diag = DiagnosticsUtilities()
        >>> report = diag.run_full_diagnostics()
        >>> diag.print_report(report)
    """

    def __init__(self, verbose: bool = False):
        """Initialize diagnostics utilities."""
        self.logger = SpyderLogger.get_logger(__name__) if SpyderLogger else logging.getLogger(__name__)
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None
        self.verbose = verbose
        self.results: list[DiagnosticResult] = []

        self.logger.info("DiagnosticsUtilities initialized")

    # ==========================================================================
    # MAIN DIAGNOSTIC METHODS
    # ==========================================================================
    def run_full_diagnostics(self) -> DiagnosticReport:
        """
        Run complete system diagnostics.

        Returns:
            DiagnosticReport with all test results
        """
        start_time = time.time()
        self.results = []

        print("\n" + "=" * 60)
        print("SPYDER SYSTEM DIAGNOSTICS")
        print("=" * 60 + "\n")

        # Get system info
        system_info = self._get_system_info()

        # Run diagnostic categories
        print("Running diagnostic tests...")
        print("-" * 40)

        self._run_system_diagnostics()
        self._run_module_diagnostics()
        self._run_dependency_diagnostics()
        self._run_configuration_diagnostics()
        self._run_connectivity_diagnostics()
        self._run_database_diagnostics()
        self._run_performance_diagnostics()
        self._run_security_diagnostics()

        # Generate summary
        summary = self._generate_summary()
        recommendations = self._generate_recommendations()

        # Calculate total duration
        total_duration = (time.time() - start_time) * 1000

        report = DiagnosticReport(
            timestamp=datetime.now(timezone.utc),
            system_info=system_info,
            test_results=self.results,
            summary=summary,
            recommendations=recommendations,
            total_duration_ms=total_duration
        )

        return report

    # ==========================================================================
    # SYSTEM DIAGNOSTICS
    # ==========================================================================
    def _get_system_info(self) -> SystemInfo:
        """Get system information."""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        return SystemInfo(
            os=platform.system(),
            python_version=platform.python_version(),
            platform=platform.platform(),
            processor=platform.processor(),
            memory_gb=memory.total / (1024**3),
            disk_gb=disk.total / (1024**3),
            network_interfaces=[iface for iface in psutil.net_if_addrs()]
        )

    def _run_system_diagnostics(self) -> None:
        """Run system-level diagnostics."""
        print("\n[System Diagnostics]")

        # Check Python version
        self._check_python_version()

        # Check system resources
        self._check_system_resources()

        # Check environment variables
        self._check_environment_variables()

        # Check file permissions
        self._check_file_permissions()

    def _check_python_version(self) -> None:
        """Check Python version compatibility."""
        start = time.time()

        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            status = DiagnosticStatus.PASSED
            message = f"Python {version.major}.{version.minor}.{version.micro}"
        else:
            status = DiagnosticStatus.WARNING
            message = f"Python {version.major}.{version.minor} (3.8+ recommended)"

        self._add_result(
            "Python Version",
            TestCategory.SYSTEM,
            status,
            message,
            {"version": f"{version.major}.{version.minor}.{version.micro}"},
            time.time() - start
        )

    def _check_system_resources(self) -> None:
        """Check system resource availability."""
        start = time.time()

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(SPYDER_HOME)

        issues = []
        if memory.available < 1 * (1024**3):  # Less than 1GB available
            issues.append("Low memory available")
        if disk.free < 5 * (1024**3):  # Less than 5GB free
            issues.append("Low disk space")

        status = DiagnosticStatus.WARNING if issues else DiagnosticStatus.PASSED
        message = ", ".join(issues) if issues else "Adequate resources available"

        self._add_result(
            "System Resources",
            TestCategory.SYSTEM,
            status,
            message,
            {
                "cpu_percent": cpu_percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_free_gb": disk.free / (1024**3)
            },
            time.time() - start
        )

    def _check_environment_variables(self) -> None:
        """Check required environment variables."""
        start = time.time()

        required_vars = ["SPYDER_HOME", "PYTHONPATH"]
        missing = []

        for var in required_vars:
            if not os.environ.get(var):
                missing.append(var)

        if missing:
            status = DiagnosticStatus.WARNING
            message = f"Missing: {', '.join(missing)}"
        else:
            status = DiagnosticStatus.PASSED
            message = "All required variables set"

        self._add_result(
            "Environment Variables",
            TestCategory.SYSTEM,
            status,
            message,
            {"missing": missing},
            time.time() - start
        )

    def _check_file_permissions(self) -> None:
        """Check file and directory permissions."""
        start = time.time()

        issues = []

        # Check if directories are writable
        for dir_path in [LOGS_DIR, DATA_DIR]:
            if dir_path.exists() and not os.access(dir_path, os.W_OK):
                issues.append(f"{dir_path} not writable")

        status = DiagnosticStatus.FAILED if issues else DiagnosticStatus.PASSED
        message = ", ".join(issues) if issues else "Permissions OK"

        self._add_result(
            "File Permissions",
            TestCategory.SYSTEM,
            status,
            message,
            {"issues": issues},
            time.time() - start
        )

    # ==========================================================================
    # MODULE DIAGNOSTICS
    # ==========================================================================
    def _run_module_diagnostics(self) -> None:
        """Run module import diagnostics."""
        print("\n[Module Diagnostics]")

        total_modules = 0
        successful_imports = 0
        failed_imports = []

        for group_name in MODULE_GROUPS:
            group_path = Path(SPYDER_HOME) / group_name

            if not group_path.exists():
                continue

            # Check each Python file in the group
            for py_file in group_path.glob("*.py"):
                if py_file.name == "__init__.py":
                    continue

                module_name = py_file.stem
                full_module_name = f"{group_name}.{module_name}"
                total_modules += 1

                try:
                    importlib.import_module(full_module_name)
                    successful_imports += 1
                    if self.verbose:
                        print(f"  ✓ {full_module_name}")
                except Exception as e:
                    failed_imports.append((full_module_name, str(e)))
                    if self.verbose:
                        print(f"  ✗ {full_module_name}: {e}")

        # Add result
        if failed_imports:
            status = DiagnosticStatus.WARNING
            message = f"{successful_imports}/{total_modules} modules imported successfully"
        else:
            status = DiagnosticStatus.PASSED
            message = f"All {total_modules} modules imported successfully"

        self._add_result(
            "Module Imports",
            TestCategory.MODULES,
            status,
            message,
            {
                "total": total_modules,
                "successful": successful_imports,
                "failed": len(failed_imports),
                "failed_modules": failed_imports[:10]  # First 10 failures
            },
            0
        )

    # ==========================================================================
    # DEPENDENCY DIAGNOSTICS
    # ==========================================================================
    def _run_dependency_diagnostics(self) -> None:
        """Check Python package dependencies."""
        print("\n[Dependency Diagnostics]")

        missing_packages = []
        version_issues = []

        for package in REQUIRED_PACKAGES:
            try:
                pkg = pkg_resources.get_distribution(package)
                if self.verbose:
                    print(f"  ✓ {package} ({pkg.version})")
            except pkg_resources.DistributionNotFound:
                missing_packages.append(package)
                if self.verbose:
                    print(f"  ✗ {package} (not installed)")
            except Exception as e:
                version_issues.append((package, str(e)))

        if missing_packages:
            status = DiagnosticStatus.FAILED
            message = f"Missing packages: {', '.join(missing_packages[:5])}"
        elif version_issues:
            status = DiagnosticStatus.WARNING
            message = f"Version issues with {len(version_issues)} packages"
        else:
            status = DiagnosticStatus.PASSED
            message = "All required packages installed"

        self._add_result(
            "Python Dependencies",
            TestCategory.DEPENDENCIES,
            status,
            message,
            {
                "missing": missing_packages,
                "version_issues": version_issues
            },
            0
        )

    # ==========================================================================
    # CONFIGURATION DIAGNOSTICS
    # ==========================================================================
    def _run_configuration_diagnostics(self) -> None:
        """Check configuration files."""
        print("\n[Configuration Diagnostics]")

        missing_configs = []
        invalid_configs = []

        for config_file in CONFIG_FILES:
            config_path = CONFIG_DIR / config_file

            if not config_path.exists():
                config_path = Path(SPYDER_HOME) / config_file

            if not config_path.exists():
                missing_configs.append(config_file)
                continue

            # Try to validate config
            try:
                if config_file.endswith('.json'):
                    with open(config_path) as f:
                        json.load(f)
                elif config_file.endswith('.ini'):
                    parser = configparser.ConfigParser()
                    parser.read(config_path)

                if self.verbose:
                    print(f"  ✓ {config_file}")

            except Exception as e:
                invalid_configs.append((config_file, str(e)))
                if self.verbose:
                    print(f"  ✗ {config_file}: {e}")

        if missing_configs:
            status = DiagnosticStatus.WARNING
            message = f"Missing configs: {', '.join(missing_configs)}"
        elif invalid_configs:
            status = DiagnosticStatus.FAILED
            message = f"Invalid configs: {len(invalid_configs)}"
        else:
            status = DiagnosticStatus.PASSED
            message = "All configurations valid"

        self._add_result(
            "Configuration Files",
            TestCategory.CONFIGURATION,
            status,
            message,
            {
                "missing": missing_configs,
                "invalid": invalid_configs
            },
            0
        )

    # ==========================================================================
    # CONNECTIVITY DIAGNOSTICS
    # ==========================================================================
    def _run_connectivity_diagnostics(self) -> None:
        """Test network connectivity."""
        print("\n[Connectivity Diagnostics]")

        connection_failures = []

        for name, (host, port) in NETWORK_ENDPOINTS.items():
            if self._test_connection(host, port):
                if self.verbose:
                    print(f"  ✓ {name} ({host}:{port})")
            else:
                connection_failures.append(f"{name} ({host}:{port})")
                if self.verbose:
                    print(f"  ✗ {name} ({host}:{port})")

        if connection_failures:
            status = DiagnosticStatus.WARNING
            message = f"Failed connections: {', '.join(connection_failures[:3])}"
        else:
            status = DiagnosticStatus.PASSED
            message = "All endpoints reachable"

        self._add_result(
            "Network Connectivity",
            TestCategory.CONNECTIVITY,
            status,
            message,
            {"failures": connection_failures},
            0
        )

    def _test_connection(self, host: str, port: int) -> bool:
        """Test if a host:port is reachable."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    # ==========================================================================
    # DATABASE DIAGNOSTICS
    # ==========================================================================
    def _run_database_diagnostics(self) -> None:
        """Check database connectivity and integrity."""
        print("\n[Database Diagnostics]")

        db_issues = []

        # Check for database files
        db_files = list(DATA_DIR.glob("*.db")) if DATA_DIR.exists() else []

        for db_file in db_files:
            try:
                conn = sqlite3.connect(db_file)

                # Check integrity
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()

                if result[0] != "ok":
                    db_issues.append(f"{db_file.name}: integrity check failed")

                # Get table count
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]

                conn.close()

                if self.verbose:
                    print(f"  ✓ {db_file.name} ({table_count} tables)")

            except Exception as e:
                db_issues.append(f"{db_file.name}: {e}")
                if self.verbose:
                    print(f"  ✗ {db_file.name}: {e}")

        if not db_files:
            status = DiagnosticStatus.WARNING
            message = "No database files found"
        elif db_issues:
            status = DiagnosticStatus.FAILED
            message = f"Database issues: {len(db_issues)}"
        else:
            status = DiagnosticStatus.PASSED
            message = f"{len(db_files)} databases OK"

        self._add_result(
            "Database Integrity",
            TestCategory.DATABASE,
            status,
            message,
            {
                "databases": len(db_files),
                "issues": db_issues
            },
            0
        )

    # ==========================================================================
    # PERFORMANCE DIAGNOSTICS
    # ==========================================================================
    def _run_performance_diagnostics(self) -> None:
        """Run performance benchmark tests."""
        print("\n[Performance Diagnostics]")

        # CPU benchmark
        cpu_score = self._benchmark_cpu()

        # Memory benchmark
        memory_score = self._benchmark_memory()

        # Disk I/O benchmark
        disk_score = self._benchmark_disk()

        # Calculate overall score
        overall_score = (cpu_score + memory_score + disk_score) / 3

        if overall_score > 80:
            status = DiagnosticStatus.PASSED
            message = f"Performance score: {overall_score:.1f}/100"
        elif overall_score > 60:
            status = DiagnosticStatus.WARNING
            message = f"Performance score: {overall_score:.1f}/100 (suboptimal)"
        else:
            status = DiagnosticStatus.FAILED
            message = f"Performance score: {overall_score:.1f}/100 (poor)"

        self._add_result(
            "Performance Benchmark",
            TestCategory.PERFORMANCE,
            status,
            message,
            {
                "cpu_score": cpu_score,
                "memory_score": memory_score,
                "disk_score": disk_score,
                "overall_score": overall_score
            },
            0
        )

    def _benchmark_cpu(self) -> float:
        """Simple CPU benchmark."""
        start = time.time()

        # Simple computation benchmark
        result = 0
        for i in range(1000000):
            result += i * i

        duration = time.time() - start

        # Score based on duration (lower is better)
        if duration < 0.1:
            return 100
        elif duration < 0.5:
            return 80
        elif duration < 1.0:
            return 60
        else:
            return 40

    def _benchmark_memory(self) -> float:
        """Simple memory benchmark."""
        try:
            # Create and manipulate large arrays
            import numpy as np

            start = time.time()
            arr = np.random.rand(1000, 1000)
            np.dot(arr, arr.T)
            duration = time.time() - start

            if duration < 0.5:
                return 100
            elif duration < 1.0:
                return 80
            elif duration < 2.0:
                return 60
            else:
                return 40

        except Exception:
            return 50  # Default score if numpy not available

    def _benchmark_disk(self) -> float:
        """Simple disk I/O benchmark."""
        test_file = Path(SPYDER_HOME) / "benchmark_test.tmp"

        try:
            # Write test
            start = time.time()
            with open(test_file, 'wb') as f:
                f.write(os.urandom(10 * 1024 * 1024))  # 10MB
            write_duration = time.time() - start

            # Read test
            start = time.time()
            with open(test_file, 'rb') as f:
                f.read()
            read_duration = time.time() - start

            # Clean up
            test_file.unlink()

            # Score based on combined duration
            total_duration = write_duration + read_duration
            if total_duration < 0.5:
                return 100
            elif total_duration < 1.0:
                return 80
            elif total_duration < 2.0:
                return 60
            else:
                return 40

        except Exception:
            return 50  # Default score on error

    # ==========================================================================
    # SECURITY DIAGNOSTICS
    # ==========================================================================
    def _run_security_diagnostics(self) -> None:
        """Run security checks."""
        print("\n[Security Diagnostics]")

        security_issues = []

        # Check for sensitive files with wrong permissions
        sensitive_files = [
            Path(SPYDER_HOME) / ".env",
            CONFIG_DIR / "api_keys.json",
            CONFIG_DIR / "credentials.json"
        ]

        for file_path in sensitive_files:
            if file_path.exists():
                # Check if file is world-readable
                stat_info = os.stat(file_path)
                if stat_info.st_mode & 0o004:
                    security_issues.append(f"{file_path.name} is world-readable")

        # Check for default passwords in config
        if (CONFIG_DIR / "config.ini").exists():
            parser = configparser.ConfigParser()
            parser.read(CONFIG_DIR / "config.ini")

            for section in parser.sections():
                for key, value in parser.items(section):
                    if 'password' in key.lower() and value in ['password', '123456', 'admin']:
                        security_issues.append(f"Default password found in {section}.{key}")

        if security_issues:
            status = DiagnosticStatus.WARNING
            message = f"Security issues: {len(security_issues)}"
        else:
            status = DiagnosticStatus.PASSED
            message = "No security issues found"

        self._add_result(
            "Security Check",
            TestCategory.SECURITY,
            status,
            message,
            {"issues": security_issues},
            0
        )

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    def _add_result(
        self,
        test_name: str,
        category: TestCategory,
        status: DiagnosticStatus,
        message: str,
        details: dict[str, Any],
        duration: float
    ) -> None:
        """Add a diagnostic result."""
        result = DiagnosticResult(
            test_name=test_name,
            category=category,
            status=status,
            message=message,
            details=details,
            duration_ms=duration * 1000
        )

        self.results.append(result)

        # Print result
        symbol = "✓" if status == DiagnosticStatus.PASSED else "✗" if status == DiagnosticStatus.FAILED else "⚠"
        print(f"  {symbol} {test_name}: {message}")

    def _generate_summary(self) -> dict[str, int]:
        """Generate results summary."""
        summary = {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r.status == DiagnosticStatus.PASSED),
            "failed": sum(1 for r in self.results if r.status == DiagnosticStatus.FAILED),
            "warnings": sum(1 for r in self.results if r.status == DiagnosticStatus.WARNING),
            "skipped": sum(1 for r in self.results if r.status == DiagnosticStatus.SKIPPED)
        }
        return summary

    def _generate_recommendations(self) -> list[str]:
        """Generate recommendations based on results."""
        recommendations = []

        for result in self.results:
            if result.status == DiagnosticStatus.FAILED:
                if result.category == TestCategory.DEPENDENCIES:
                    recommendations.append("Install missing packages: pip install -r requirements.txt")
                elif result.category == TestCategory.CONFIGURATION:
                    recommendations.append(f"Check configuration files in {CONFIG_DIR}")
                elif result.category == TestCategory.CONNECTIVITY:
                    recommendations.append("Ensure required services are running")

            elif result.status == DiagnosticStatus.WARNING:
                if result.category == TestCategory.SYSTEM:
                    if "memory" in result.message.lower():
                        recommendations.append("Consider increasing system memory")
                    if "disk" in result.message.lower():
                        recommendations.append("Free up disk space")

        return list(set(recommendations))  # Remove duplicates

    # ==========================================================================
    # REPORTING METHODS
    # ==========================================================================
    def print_report(self, report: DiagnosticReport) -> None:
        """Print diagnostic report to console."""
        print("\n" + "=" * 60)
        print("DIAGNOSTIC REPORT")
        print("=" * 60)
        print(f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {report.total_duration_ms:.1f}ms")
        print()

        # System Info
        print("SYSTEM INFORMATION:")
        print(f"  OS: {report.system_info.os} ({report.system_info.platform})")
        print(f"  Python: {report.system_info.python_version}")
        print(f"  Memory: {report.system_info.memory_gb:.1f} GB")
        print(f"  Disk: {report.system_info.disk_gb:.1f} GB")
        print()

        # Summary
        print("TEST SUMMARY:")
        print(f"  Total Tests: {report.summary['total']}")
        print(f"  ✓ Passed: {report.summary['passed']}")
        print(f"  ✗ Failed: {report.summary['failed']}")
        print(f"  ⚠ Warnings: {report.summary['warnings']}")
        print()

        # Failed Tests
        failed_tests = [r for r in report.test_results if r.status == DiagnosticStatus.FAILED]
        if failed_tests:
            print("FAILED TESTS:")
            for test in failed_tests:
                print(f"  ✗ {test.test_name}: {test.message}")
            print()

        # Recommendations
        if report.recommendations:
            print("RECOMMENDATIONS:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
            print()

        print("=" * 60)

    def save_report(self, report: DiagnosticReport, filename: str | None = None) -> Path:
        """Save diagnostic report to file."""
        if not filename:
            filename = f"diagnostic_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"

        report_path = LOGS_DIR / filename

        # Convert report to dictionary
        report_dict = {
            "timestamp": report.timestamp.isoformat(),
            "system_info": {
                "os": report.system_info.os,
                "python_version": report.system_info.python_version,
                "platform": report.system_info.platform,
                "processor": report.system_info.processor,
                "memory_gb": report.system_info.memory_gb,
                "disk_gb": report.system_info.disk_gb
            },
            "summary": report.summary,
            "recommendations": report.recommendations,
            "total_duration_ms": report.total_duration_ms,
            "test_results": [
                {
                    "test_name": r.test_name,
                    "category": r.category.value,
                    "status": r.status.value,
                    "message": r.message,
                    "details": r.details,
                    "duration_ms": r.duration_ms
                }
                for r in report.test_results
            ]
        }

        with open(report_path, 'w') as f:
            json.dump(report_dict, f, indent=2, default=str)

        self.logger.info("Report saved to: %s", report_path)
        return report_path

# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================
def quick_check() -> bool:
    """Run quick diagnostic check."""
    diag = DiagnosticsUtilities()
    report = diag.run_full_diagnostics()
    return report.summary['failed'] == 0

def verify_installation() -> bool:
    """Verify Spyder installation."""
    diag = DiagnosticsUtilities(verbose=True)
    report = diag.run_full_diagnostics()
    diag.print_report(report)
    return report.summary['failed'] == 0

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================
def main():
    """Main entry point for command line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Spyder Diagnostics Utilities - System Verification and Testing"
    )

    parser.add_argument(
        "action",
        choices=["full", "quick", "modules", "dependencies", "config", "connectivity", "performance"],
        help="Diagnostic action to perform"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--save",
        action="store_true",
        help="Save report to file"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format"
    )

    args = parser.parse_args()

    # Initialize diagnostics
    diag = DiagnosticsUtilities(verbose=args.verbose)

    # Perform requested action
    if args.action == "full":
        report = diag.run_full_diagnostics()

        if args.json:
            # Output JSON
            print(json.dumps({
                "timestamp": report.timestamp.isoformat(),
                "summary": report.summary,
                "recommendations": report.recommendations
            }, indent=2))
        else:
            diag.print_report(report)

        if args.save:
            path = diag.save_report(report)
            print(f"\nReport saved to: {path}")

    elif args.action == "quick":
        # Run only critical tests
        diag._run_system_diagnostics()
        diag._run_connectivity_diagnostics()

        passed = sum(1 for r in diag.results if r.status == DiagnosticStatus.PASSED)
        total = len(diag.results)

        print(f"\nQuick Check: {passed}/{total} tests passed")

    elif args.action == "modules":
        diag._run_module_diagnostics()

    elif args.action == "dependencies":
        diag._run_dependency_diagnostics()

    elif args.action == "config":
        diag._run_configuration_diagnostics()

    elif args.action == "connectivity":
        diag._run_connectivity_diagnostics()

    elif args.action == "performance":
        diag._run_performance_diagnostics()

    # Return exit code based on results
    failed = sum(1 for r in diag.results if r.status == DiagnosticStatus.FAILED)
    sys.exit(1 if failed > 0 else 0)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":
    main()
