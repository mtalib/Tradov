#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovI_Integration
Module: TradovI05_DiagnosticsEngine_Analyzers.py
Purpose: Performance analysis and advanced diagnostics for the DiagnosticsEngine

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-03-03 Time: 00:00:00

Module Description:
    Provides the AnalysisManager class used by TradovI04_DiagnosticsEngine_Core
    to perform performance analysis and advanced pattern-based diagnostics.

    analyze_performance() → Dict[str, Any]
        Collect recent system metrics and produce a structured performance
        summary suitable for consumption by DiagnosticUtils.

    run_advanced_analysis() → List[DiagnosticIssue]
        Detect cross-cutting issues (sustained high CPU, memory pressure,
        latency spikes, etc.) that health-check snapshots miss.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import uuid
from datetime import datetime, UTC
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
from Tradov.TradovI_Integration.TradovI10_DiagnosticsEngine_Types import (
    DiagnosticCategory,
    DiagnosticIssue,
    ProblemSeverity,
)

# ==============================================================================
# CONSTANTS
# ==============================================================================
CPU_HIGH_THRESHOLD = 85.0        # % sustained CPU that triggers an issue
MEMORY_HIGH_THRESHOLD = 85.0     # % memory usage that triggers an issue
DISK_HIGH_THRESHOLD = 90.0       # % disk usage that triggers an issue
THREAD_HIGH_THRESHOLD = 500      # thread count that triggers an issue


class AnalysisManager:
    """
    Cross-cutting performance analyser for the DiagnosticsEngine.

    Aggregates system metrics over time and surfaces patterns that single-
    point health checks cannot reliably detect (sustained load, gradual
    memory growth, thread-count creep).

    Args:
        config: Configuration dictionary forwarded from DiagnosticsEngine.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.logger = TradovLogger.get_logger(self.__class__.__name__)

        # Rolling buffer: last N metric snapshots used for trend detection.
        self._history: list[dict[str, Any]] = []
        self._max_history: int = int(self.config.get("analysis_history_size", 60))

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def analyze_performance(self) -> dict[str, Any]:
        """
        Collect a current metrics snapshot and return a performance summary.

        The summary dict is consumed by DiagnosticUtils.generate_recommendations
        and DiagnosticUtils.create_executive_summary.

        Returns:
            Dict with keys: cpu_percent, memory_percent, disk_percent,
            thread_count, open_files, status, timestamp.
        """
        snapshot = self._snapshot()
        self._store(snapshot)
        return snapshot

    def run_advanced_analysis(self) -> list[DiagnosticIssue]:
        """
        Analyse collected history for sustained or trending problems.

        Returns:
            List of DiagnosticIssue objects; empty list when system is healthy.
        """
        issues: list[DiagnosticIssue] = []

        if not self._history:
            return issues

        # Evaluate the most recent snapshot against hard thresholds.
        latest = self._history[-1]
        issues.extend(self._check_cpu(latest))
        issues.extend(self._check_memory(latest))
        issues.extend(self._check_disk(latest))
        issues.extend(self._check_threads(latest))

        # Evaluate trends over the full history window.
        if len(self._history) >= 5:
            issues.extend(self._detect_memory_growth())

        return issues

    # -------------------------------------------------------------------------
    # PRIVATE HELPERS
    # -------------------------------------------------------------------------

    def _snapshot(self) -> dict[str, Any]:
        """Return current system metrics as a flat dict."""
        if not _PSUTIL_AVAILABLE:
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_percent": 0.0,
                "thread_count": 0,
                "open_files": 0,
                "status": "psutil_unavailable",
                "timestamp": datetime.now(UTC).isoformat(),
            }

        try:
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            proc = psutil.Process()
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": mem.percent,
                "memory_available_mb": mem.available / (1024 * 1024),
                "disk_percent": disk.percent,
                "thread_count": proc.num_threads(),
                "open_files": len(proc.open_files()),
                "status": "ok",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            self.logger.warning("Could not collect performance snapshot: %s", exc)
            return {
                "cpu_percent": 0.0,
                "memory_percent": 0.0,
                "disk_percent": 0.0,
                "thread_count": 0,
                "open_files": 0,
                "status": f"error:{exc}",
                "timestamp": datetime.now(UTC).isoformat(),
            }

    def _store(self, snapshot: dict[str, Any]) -> None:
        """Append a snapshot to the rolling history, evicting the oldest."""
        self._history.append(snapshot)
        if len(self._history) > self._max_history:
            self._history.pop(0)

    # ------------------------------------------------------------------
    # Single-point threshold checks
    # ------------------------------------------------------------------

    def _check_cpu(self, snap: dict[str, Any]) -> list[DiagnosticIssue]:
        cpu = snap.get("cpu_percent", 0.0)
        if cpu < CPU_HIGH_THRESHOLD:
            return []
        return [self._make_issue(
            category=DiagnosticCategory.PERFORMANCE,
            severity=ProblemSeverity.HIGH if cpu >= 95.0 else ProblemSeverity.MEDIUM,
            title="High CPU utilisation",
            description=f"CPU usage is {cpu:.1f}%, exceeding the {CPU_HIGH_THRESHOLD}% threshold.",
            components=["system"],
            symptoms=[f"CPU at {cpu:.1f}%"],
            root_cause="Sustained compute load — possible tight loop or blocking operation.",
            recommendations=[
                "Profile the process with cProfile or py-spy.",
                "Check for synchronous I/O on event-loop threads.",
                "Consider offloading heavy computation to a ThreadPoolExecutor.",
            ],
        )]

    def _check_memory(self, snap: dict[str, Any]) -> list[DiagnosticIssue]:
        mem = snap.get("memory_percent", 0.0)
        if mem < MEMORY_HIGH_THRESHOLD:
            return []
        avail_mb = snap.get("memory_available_mb", 0.0)
        return [self._make_issue(
            category=DiagnosticCategory.PERFORMANCE,
            severity=ProblemSeverity.HIGH if mem >= 95.0 else ProblemSeverity.MEDIUM,
            title="High memory utilisation",
            description=f"System memory usage is {mem:.1f}% ({avail_mb:.0f} MB available).",
            components=["system"],
            symptoms=[f"Memory at {mem:.1f}%"],
            root_cause="Possible memory leak or large in-memory data structures.",
            recommendations=[
                "Review DataFrame caches and historical data buffers.",
                "Enable tracemalloc to locate allocation hotspots.",
                "Restart non-critical background workers to reclaim memory.",
            ],
        )]

    def _check_disk(self, snap: dict[str, Any]) -> list[DiagnosticIssue]:
        disk = snap.get("disk_percent", 0.0)
        if disk < DISK_HIGH_THRESHOLD:
            return []
        return [self._make_issue(
            category=DiagnosticCategory.SYSTEM,
            severity=ProblemSeverity.HIGH,
            title="Disk space critically low",
            description=f"Disk usage is {disk:.1f}%, exceeding the {DISK_HIGH_THRESHOLD}% threshold.",  # noqa: E501
            components=["storage"],
            symptoms=[f"Disk at {disk:.1f}%"],
            root_cause="Log files, historical data, or SQLite databases consuming disk space.",
            recommendations=[
                "Archive or compress logs older than 30 days.",
                "Run VACUUM on SQLite databases.",
                "Remove stale market-data cache files.",
            ],
        )]

    def _check_threads(self, snap: dict[str, Any]) -> list[DiagnosticIssue]:
        threads = snap.get("thread_count", 0)
        if threads < THREAD_HIGH_THRESHOLD:
            return []
        return [self._make_issue(
            category=DiagnosticCategory.PERFORMANCE,
            severity=ProblemSeverity.MEDIUM,
            title="High thread count",
            description=f"Process thread count is {threads}, exceeding the {THREAD_HIGH_THRESHOLD} threshold.",  # noqa: E501
            components=["system"],
            symptoms=[f"Thread count: {threads}"],
            root_cause="Thread leak from unclosed executors or background workers.",
            recommendations=[
                "Audit ThreadPoolExecutor / asyncio task lifecycle.",
                "Ensure background threads exit cleanly on shutdown.",
            ],
        )]

    # ------------------------------------------------------------------
    # Trend detection
    # ------------------------------------------------------------------

    def _detect_memory_growth(self) -> list[DiagnosticIssue]:
        """Flag a steadily growing memory trend over the history window."""
        mem_series = [s.get("memory_percent", 0.0) for s in self._history]
        if not mem_series:
            return []
        first_half = sum(mem_series[: len(mem_series) // 2]) / max(len(mem_series) // 2, 1)
        second_half = sum(mem_series[len(mem_series) // 2:]) / max(len(mem_series) - len(mem_series) // 2, 1)  # noqa: E501
        growth = second_half - first_half
        if growth < 5.0:  # less than 5 pp growth over the window → not a concern
            return []
        return [self._make_issue(
            category=DiagnosticCategory.PERFORMANCE,
            severity=ProblemSeverity.MEDIUM,
            title="Memory growth trend detected",
            description=(
                f"Memory usage grew by {growth:.1f} percentage points over the "
                f"last {len(self._history)} monitoring cycles, suggesting a slow leak."
            ),
            components=["system"],
            symptoms=[f"Memory trend: +{growth:.1f}pp over {len(self._history)} cycles"],
            root_cause="Gradual memory accumulation — possible unbounded cache or event queue.",
            recommendations=[
                "Review LRU caches and historical data ring-buffers for unbounded growth.",
                "Check that completed asyncio tasks are being awaited and discarded.",
            ],
            auto_fixable=False,
        )]

    # ------------------------------------------------------------------
    # Factory helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_issue(
        *,
        category: DiagnosticCategory,
        severity: ProblemSeverity,
        title: str,
        description: str,
        components: list[str],
        symptoms: list[str],
        root_cause: str | None = None,
        recommendations: list[str] | None = None,
        auto_fixable: bool = False,
    ) -> DiagnosticIssue:
        """Construct a DiagnosticIssue with a generated UUID."""
        return DiagnosticIssue(
            issue_id=str(uuid.uuid4()),
            category=category,
            severity=severity,
            title=title,
            description=description,
            affected_components=components,
            symptoms=symptoms,
            root_cause=root_cause,
            recommendations=recommendations or [],
            auto_fixable=auto_fixable,
            detected_at=datetime.now(UTC),
        )
