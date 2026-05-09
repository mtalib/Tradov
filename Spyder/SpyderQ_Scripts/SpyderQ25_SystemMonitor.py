#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ25_SystemMonitor.py
Purpose: Script-level system monitor for CLI/shell usage — wraps SpyderM01
         with a command-line friendly interface and periodic reporting.

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-03 Time: 00:00:00

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _logger = SpyderLogger.get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None  # type: ignore[assignment]

# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class SystemSnapshot:
    """Point-in-time snapshot of key system metrics."""

    timestamp: float = field(default_factory=time.monotonic)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_percent: float = 0.0
    open_file_handles: int = 0


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class SystemMonitor:
    """
    Script-level system resource monitor.

    Periodically samples CPU, memory, and disk utilisation and logs a summary.
    Designed as a lightweight CLI companion to the full ``SpyderM01_SystemMonitor``
    subsystem module.

    Args:
        interval: Sample interval in seconds (default: 60).
        warn_cpu: CPU percentage threshold for warning log (default: 85).
        warn_memory: Memory percentage threshold for warning log (default: 80).

    Note:
        This is a stub implementation. Requires ``psutil`` for live metrics.
    """

    def __init__(
        self,
        interval: float = 60.0,
        warn_cpu: float = 85.0,
        warn_memory: float = 80.0,
    ) -> None:
        self._interval = interval
        self._warn_cpu = warn_cpu
        self._warn_memory = warn_memory
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._snapshots: list[SystemSnapshot] = []
        _logger.debug("SystemMonitor initialised (interval=%.0fs)", interval)

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """True if the monitoring thread is active."""
        return self._running

    def start(self) -> None:
        """Start periodic monitoring."""
        if self._running:
            _logger.warning("SystemMonitor: already running")
            return
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(
            target=self._run, name="SystemMonitor", daemon=True
        )
        self._thread.start()
        _logger.info("SystemMonitor started (interval=%.0fs)", self._interval)

    def stop(self) -> None:
        """Stop periodic monitoring."""
        self._stop_event.set()
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        _logger.info("SystemMonitor stopped")

    def snapshot(self) -> SystemSnapshot:
        """Take a single system snapshot and return it."""
        snap = SystemSnapshot()
        if HAS_PSUTIL:
            snap.cpu_percent = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            snap.memory_percent = mem.percent
            snap.memory_used_mb = mem.used / (1024 ** 2)
            snap.disk_percent = psutil.disk_usage("/").percent
            try:
                proc = psutil.Process()
                snap.open_file_handles = proc.num_fds()
            except Exception as e:
                _logger.debug("Could not read open file handle count: %s", e)
        return snap

    def get_latest(self) -> SystemSnapshot | None:
        """Return the most recent snapshot, or None if no samples taken."""
        return self._snapshots[-1] if self._snapshots else None

    def get_summary(self) -> dict[str, Any]:
        """Return a summary dict suitable for logging or dashboard display."""
        snap = self.snapshot()
        return {
            "cpu_percent": snap.cpu_percent,
            "memory_percent": snap.memory_percent,
            "memory_used_mb": round(snap.memory_used_mb, 1),
            "disk_percent": snap.disk_percent,
            "psutil_available": HAS_PSUTIL,
        }

    # --------------------------------------------------------------------------
    # Internal
    # --------------------------------------------------------------------------

    def _run(self) -> None:
        """Monitoring loop."""
        while not self._stop_event.is_set():
            snap = self.snapshot()
            self._snapshots.append(snap)
            # Trim history to last 1 000 samples
            if len(self._snapshots) > 1000:
                self._snapshots = self._snapshots[-1000:]
            self._maybe_warn(snap)
            self._stop_event.wait(self._interval)

    def _maybe_warn(self, snap: SystemSnapshot) -> None:
        """Log a warning if any metric exceeds its threshold."""
        if snap.cpu_percent > self._warn_cpu:
            _logger.warning(
                "SystemMonitor: high CPU usage %.1f%% (threshold %.0f%%)",
                snap.cpu_percent,
                self._warn_cpu,
            )
        if snap.memory_percent > self._warn_memory:
            _logger.warning(
                "SystemMonitor: high memory usage %.1f%% (threshold %.0f%%)",
                snap.memory_percent,
                self._warn_memory,
            )
