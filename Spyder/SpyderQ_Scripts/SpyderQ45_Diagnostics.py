#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ45_Diagnostics.py
Purpose: Python-based diagnostic runner — collects and reports system,
         module, and connectivity diagnostics for troubleshooting.

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-03 Time: 00:00:00

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _logger = SpyderLogger.get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ==============================================================================
# ENUMS
# ==============================================================================


class DiagnosticStatus(Enum):
    """Result status for a single diagnostic check."""
    PASS = "pass"  # noqa: S105
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class DiagnosticResult:
    """Result of a single named diagnostic check."""

    name: str
    status: DiagnosticStatus
    message: str = ""
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """True if the check passed."""
        return self.status == DiagnosticStatus.PASS

    def __str__(self) -> str:
        return f"[{self.status.value.upper():4s}] {self.name}: {self.message}"


@dataclass
class DiagnosticsReport:
    """Aggregated diagnostics report."""

    results: list[DiagnosticResult] = field(default_factory=list)
    generated_at: float = field(default_factory=time.time)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == DiagnosticStatus.PASS)

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == DiagnosticStatus.WARN)

    @property
    def failures(self) -> int:
        return sum(1 for r in self.results if r.status == DiagnosticStatus.FAIL)

    @property
    def is_healthy(self) -> bool:
        return self.failures == 0

    def summary(self) -> str:
        return (
            f"Diagnostics: {self.passed} passed, {self.warnings} warnings, "
            f"{self.failures} failures"
        )


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class DiagnosticsRunner:
    """
    Diagnostic runner for Spyder system health checks.

    Runs a configurable set of named checks and produces a ``DiagnosticsReport``.
    Checks cover Python environment, required packages, environment variables,
    and (optionally) network connectivity.

    Args:
        skip_network: Skip network connectivity checks (default: False).
        timeout: Per-check timeout in seconds (default: 5).

    Usage::

        runner = DiagnosticsRunner()
        report = runner.run()
        print(report.summary())
        for result in report.results:
            print(result)
    """

    def __init__(
        self,
        skip_network: bool = False,
        timeout: float = 5.0,
    ) -> None:
        self._skip_network = skip_network
        self._timeout = timeout
        _logger.debug("DiagnosticsRunner initialised (skip_network=%s)", skip_network)

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    def run(self) -> DiagnosticsReport:
        """
        Execute all diagnostic checks and return a report.

        Returns:
            DiagnosticsReport with pass/warn/fail results for every check.
        """
        report = DiagnosticsReport()
        checks = [
            ("python_version", self._check_python_version),
            ("required_packages", self._check_required_packages),
            ("env_vars", self._check_env_vars),
        ]
        if not self._skip_network:
            checks.append(("network_dns", self._check_network_dns))

        for name, check_fn in checks:
            t0 = time.monotonic()
            try:
                result = check_fn()
                result.name = name
                result.duration_ms = (time.monotonic() - t0) * 1000
            except Exception as exc:
                result = DiagnosticResult(
                    name=name,
                    status=DiagnosticStatus.FAIL,
                    message=f"Unhandled exception: {exc}",
                    duration_ms=(time.monotonic() - t0) * 1000,
                )
            report.results.append(result)
            _logger.debug("Diagnostic '%s': %s", name, result.status.value)

        if report.is_healthy:
            _logger.info(report.summary())
        else:
            _logger.warning(report.summary())
        return report

    # --------------------------------------------------------------------------
    # Individual checks
    # --------------------------------------------------------------------------

    def _check_python_version(self) -> DiagnosticResult:
        """Verify Python >= 3.11."""
        major, minor = sys.version_info[:2]
        version_str = f"{major}.{minor}.{sys.version_info[2]}"
        if major >= 3 and minor >= 11:
            return DiagnosticResult(
                name="",
                status=DiagnosticStatus.PASS,
                message=f"Python {version_str}",
            )
        return DiagnosticResult(
            name="",
            status=DiagnosticStatus.WARN,
            message=f"Python {version_str} — Spyder requires >= 3.11",
        )

    def _check_required_packages(self) -> DiagnosticResult:
        """Check that key runtime packages are importable."""
        required = ["numpy", "pandas", "requests", "PySide6"]
        missing = []
        for pkg in required:
            try:
                __import__(pkg)
            except ImportError:
                missing.append(pkg)

        if not missing:
            return DiagnosticResult(
                name="",
                status=DiagnosticStatus.PASS,
                message=f"All {len(required)} required packages available",
            )
        return DiagnosticResult(
            name="",
            status=DiagnosticStatus.WARN,
            message=f"Missing packages: {', '.join(missing)}",
            details={"missing": missing},
        )

    def _check_env_vars(self) -> DiagnosticResult:
        """Check that critical environment variables are set."""
        import os
        required_vars = ["MASSIVE_API_KEY", "TRADIER_API_KEY", "TRADIER_ACCOUNT_ID"]
        missing = [v for v in required_vars if not os.environ.get(v)]
        if not missing:
            return DiagnosticResult(
                name="",
                status=DiagnosticStatus.PASS,
                message="All required env vars present",
            )
        return DiagnosticResult(
            name="",
            status=DiagnosticStatus.WARN,
            message=f"Missing env vars: {', '.join(missing)}",
            details={"missing": missing},
        )

    def _check_network_dns(self) -> DiagnosticResult:
        """Verify DNS resolution for critical hostnames."""
        import socket
        hosts = ["api.tradier.com", "api.polygon.io"]
        failed = []
        for host in hosts:
            try:
                socket.gethostbyname(host)
            except OSError:
                failed.append(host)
        if not failed:
            return DiagnosticResult(
                name="",
                status=DiagnosticStatus.PASS,
                message=f"DNS resolution OK for {', '.join(hosts)}",
            )
        return DiagnosticResult(
            name="",
            status=DiagnosticStatus.FAIL,
            message=f"DNS resolution failed: {', '.join(failed)}",
            details={"failed_hosts": failed},
        )
