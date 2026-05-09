#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderQ_Scripts
Module: SpyderQ24_ProductionWatchdog.py
Purpose: Production environment watchdog — monitors system health and restarts
         failed services in live deployment.

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-03 Time: 00:00:00

"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from collections.abc import Callable

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _logger = SpyderLogger.get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

try:
    from SpyderJ_Alerts.SpyderJ01_AlertManager import AlertManager as _AlertManager
    _ALERT_MANAGER_AVAILABLE = True
except ImportError:
    _AlertManager = None  # type: ignore
    _ALERT_MANAGER_AVAILABLE = False

# PID file location — override via SPYDER_PID_FILE env var
_DEFAULT_PID_FILE = Path(os.getenv("SPYDER_PID_FILE", "/tmp/spyder_watchdog.pid"))

# Exponential backoff parameters
_BACKOFF_BASE_SECS: float = 2.0
_BACKOFF_MAX_SECS: float = 300.0  # cap at 5 minutes

# ==============================================================================
# ENUMS
# ==============================================================================


class WatchdogState(Enum):
    """Watchdog operational state."""
    IDLE = "idle"
    MONITORING = "monitoring"
    RECOVERING = "recovering"
    STOPPED = "stopped"


# ==============================================================================
# DATA CLASSES
# ==============================================================================


@dataclass
class ServiceHealth:
    """Health status for a monitored service."""

    service_name: str
    is_healthy: bool = True
    last_check: float = field(default_factory=time.monotonic)
    restart_count: int = 0
    last_error: str = ""
    next_retry_at: float = field(default_factory=time.monotonic)  # for backoff


# ==============================================================================
# MAIN CLASS
# ==============================================================================


class ProductionWatchdog:
    """
    Production environment watchdog.

    Monitors registered services, detects failures via health-check callbacks,
    and optionally triggers restart handlers. Designed for 24/7 live trading
    deployments.

    Supports:
    - PID file tracking for systemd / supervisord integration.
    - Exponential backoff between restart attempts (2s → 300s cap).
    - Alert escalation via SpyderJ01_AlertManager when max_restarts is exceeded.

    Args:
        check_interval: Seconds between health checks (default: 30).
        max_restarts: Maximum restart attempts per service before escalating.
        pid_file: Path to PID file. Defaults to $SPYDER_PID_FILE env var or
            /tmp/spyder_watchdog.pid.  Pass None to disable PID file.
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        max_restarts: int = 3,
        pid_file: Path | str | None = _DEFAULT_PID_FILE,
    ) -> None:
        self._check_interval = check_interval
        self._max_restarts = max_restarts
        self._pid_file: Path | None = Path(pid_file) if pid_file else None
        self._state = WatchdogState.IDLE
        self._services: dict[str, ServiceHealth] = {}
        self._health_checks: dict[str, Callable[[], bool]] = {}
        self._restart_handlers: dict[str, Callable[[], None]] = {}
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # Alert manager (optional)
        self._alert_manager: Any | None = (
            _AlertManager() if _ALERT_MANAGER_AVAILABLE and _AlertManager else None
        )
        _logger.debug("ProductionWatchdog initialised (check_interval=%.0fs)", check_interval)

    # --------------------------------------------------------------------------
    # Public API
    # --------------------------------------------------------------------------

    @property
    def state(self) -> WatchdogState:
        """Current watchdog state."""
        return self._state

    def register_heartbeat_service(
        self,
        name: str = "spyder_liveness",
        heartbeat_path: str | Path | None = None,
        max_age_seconds: float = 30.0,
        restart_handler: Callable[[], None] | None = None,
    ) -> None:
        """v14 A13/O9: register a health check against the R05 heartbeat file.

        The check reads the JSON file written by SpyderR05_LivenessMonitor and
        verifies that (a) the file exists, (b) it parses as JSON, and (c) the
        embedded timestamp is within ``max_age_seconds`` of now. The watchdog
        treats a stale or unreadable heartbeat as an unhealthy service and
        escalates via the registered restart handler / alert path.
        """
        path = Path(heartbeat_path) if heartbeat_path else Path.home() / ".spyder_heartbeat"

        def _check() -> bool:
            try:
                if not path.exists():
                    return False
                with open(path, "r") as fh:
                    payload = json.load(fh)
                ts_str = payload.get("ts")
                if not ts_str:
                    return False
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - ts).total_seconds()
                return age <= max_age_seconds
            except Exception:
                return False

        self.register_service(name=name, health_check=_check, restart_handler=restart_handler)

    def register_service(
        self,
        name: str,
        health_check: Callable[[], bool],
        restart_handler: Callable[[], None] | None = None,
    ) -> None:
        """
        Register a service for watchdog monitoring.

        Args:
            name: Unique service identifier.
            health_check: Zero-argument callable returning True when healthy.
            restart_handler: Optional callable to invoke on failure.
        """
        self._services[name] = ServiceHealth(service_name=name)
        self._health_checks[name] = health_check
        if restart_handler:
            self._restart_handlers[name] = restart_handler
        _logger.info("ProductionWatchdog: registered service '%s'", name)

    def start(self) -> None:
        """Start the watchdog monitoring thread and write PID file."""
        if self._state == WatchdogState.MONITORING:
            _logger.warning("ProductionWatchdog: already running")
            return
        self._stop_event.clear()
        self._state = WatchdogState.MONITORING
        self._write_pid_file()
        self._thread = threading.Thread(
            target=self._run, name="ProductionWatchdog", daemon=True
        )
        self._thread.start()
        _logger.info("ProductionWatchdog started (pid=%d)", os.getpid())

    def stop(self) -> None:
        """Stop the watchdog monitoring thread and remove the PID file."""
        self._stop_event.set()
        self._state = WatchdogState.STOPPED
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._remove_pid_file()
        _logger.info("ProductionWatchdog stopped")

    def get_status(self) -> dict[str, Any]:
        """Return a snapshot of all monitored service health states."""
        return {
            name: {
                "is_healthy": svc.is_healthy,
                "restart_count": svc.restart_count,
                "last_error": svc.last_error,
            }
            for name, svc in self._services.items()
        }

    # --------------------------------------------------------------------------
    # Internal
    # --------------------------------------------------------------------------

    def _run(self) -> None:
        """Watchdog monitoring loop."""
        while not self._stop_event.is_set():
            self._do_check()
            self._stop_event.wait(self._check_interval)

    def _do_check(self) -> None:
        """Perform one health-check cycle across all registered services."""
        now = time.monotonic()
        for name, check_fn in self._health_checks.items():
            svc = self._services[name]
            # Honour backoff window — skip check until backoff expires
            if not svc.is_healthy and now < svc.next_retry_at:
                continue
            try:
                healthy = check_fn()
            except Exception as exc:
                healthy = False
                svc.last_error = str(exc)

            if not healthy:
                svc.is_healthy = False
                svc.restart_count += 1
                _logger.warning(
                    "ProductionWatchdog: service '%s' unhealthy (restarts=%d)",
                    name,
                    svc.restart_count,
                )
                if svc.restart_count <= self._max_restarts:
                    # Exponential backoff: 2^(restart_count-1) seconds, capped
                    backoff = min(
                        _BACKOFF_BASE_SECS ** (svc.restart_count - 1),
                        _BACKOFF_MAX_SECS,
                    )
                    svc.next_retry_at = now + backoff
                    handler = self._restart_handlers.get(name)
                    if handler:
                        try:
                            self._state = WatchdogState.RECOVERING
                            handler()
                            svc.is_healthy = True
                            svc.restart_count = 0  # reset on successful recovery
                            _logger.info(
                                "ProductionWatchdog: service '%s' restarted", name
                            )
                        except Exception as exc2:
                            _logger.error(
                                "ProductionWatchdog: restart of '%s' failed: %s",
                                name,
                                exc2,
                            )
                        finally:
                            self._state = WatchdogState.MONITORING
                else:
                    _logger.error(
                        "ProductionWatchdog: service '%s' exceeded max restarts (%d)",
                        name,
                        self._max_restarts,
                    )
                    self._send_alert(
                        f"Service '{name}' failed {svc.restart_count} times. "
                        f"Last error: {svc.last_error or 'unknown'}"
                    )
            else:
                svc.is_healthy = True
                svc.restart_count = 0
                svc.last_check = now

    # --------------------------------------------------------------------------
    # PID file helpers
    # --------------------------------------------------------------------------

    def _write_pid_file(self) -> None:
        """Write the current process PID to the configured PID file."""
        if self._pid_file is None:
            return
        try:
            self._pid_file.parent.mkdir(parents=True, exist_ok=True)
            self._pid_file.write_text(str(os.getpid()), encoding="utf-8")
            _logger.debug("ProductionWatchdog: PID file written: %s", self._pid_file)
        except OSError as exc:
            _logger.warning("ProductionWatchdog: could not write PID file: %s", exc)

    def _remove_pid_file(self) -> None:
        """Remove the PID file on clean shutdown."""
        if self._pid_file is None:
            return
        try:
            self._pid_file.unlink(missing_ok=True)
            _logger.debug("ProductionWatchdog: PID file removed: %s", self._pid_file)
        except OSError as exc:
            _logger.debug("ProductionWatchdog: could not remove PID file: %s", exc)

    # --------------------------------------------------------------------------
    # Alert helpers
    # --------------------------------------------------------------------------

    def _send_alert(self, message: str) -> None:
        """Send an escalation alert via SpyderJ01_AlertManager when available."""
        _logger.error("ProductionWatchdog ALERT: %s", message)
        if self._alert_manager is not None:
            try:
                self._alert_manager.send_alert(
                    title="ProductionWatchdog: service failure",
                    message=message,
                    severity="critical",
                )
            except Exception as exc:
                _logger.debug("ProductionWatchdog: alert send failed: %s", exc)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    import signal as _signal

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    watchdog = ProductionWatchdog(
        check_interval=float(os.getenv("WATCHDOG_CHECK_INTERVAL", "30")),
        max_restarts=int(os.getenv("WATCHDOG_MAX_RESTARTS", "3")),
    )

    def _on_signal(signum, frame):
        _logger.info("Watchdog received signal %s — stopping", signum)
        watchdog.stop()
        raise SystemExit(0)

    _signal.signal(_signal.SIGTERM, _on_signal)
    _signal.signal(_signal.SIGINT, _on_signal)

    watchdog.start()
    _logger.info("ProductionWatchdog running — waiting for stop signal")

    # Block main thread; the monitoring loop runs on the daemon thread.
    try:
        watchdog._stop_event.wait()
    except SystemExit:
        pass
