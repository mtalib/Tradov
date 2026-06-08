#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovM_Monitoring
Module: TradovM08_HealthEndpoint.py
Purpose: Lightweight HTTP health-check endpoint exposing /health and /metrics
         for systemd/Kubernetes liveness probes and external monitoring.

Author: GitHub Copilot
Year Created: 2026
Last Updated: 2026-04-04

Module Description:
    Starts a minimal HTTP server (stdlib http.server) that exposes:

    GET /health
        JSON response::

            {
              "status": "healthy",          # "healthy" | "degraded" | "unhealthy"
              "uptime_seconds": 1234.5,
              "series": {
                "A_Core": "healthy",
                "B_Broker": "healthy",
                ...
              },
              "timestamp": "2026-04-04T12:00:00"
            }

    GET /metrics
        JSON response with numeric system metrics (CPU, memory, active threads).

    GET /ready
        Returns 200 OK when trading engine dependencies are satisfied,
        503 when still initialising.

    The server runs in a daemon background thread and imposes no dependency on
    the main trading loop.  Probe callbacks are registered by the caller so
    other series can report their own health state without importing this module.

Usage::

    from TradovM_Monitoring.TradovM08_HealthEndpoint import HealthEndpoint

    endpoint = HealthEndpoint(port=8888)
    endpoint.register_probe("B_Broker", lambda: broker_client.is_connected())
    endpoint.register_probe("C_MarketData", lambda: data_feed.is_running())
    endpoint.start()
    # … trading loop …
    endpoint.stop()

Environment variables:
    TRADOV_HEALTH_PORT   — override default port (default: 8888)
    TRADOV_HEALTH_HOST   — bind address (default: 127.0.0.1)
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, UTC
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    _logger = TradovLogger.get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

try:
    import psutil as _psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _psutil = None  # type: ignore
    _PSUTIL_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_HOST: str = os.getenv("TRADOV_HEALTH_HOST", "127.0.0.1")
DEFAULT_PORT: int = int(os.getenv("TRADOV_HEALTH_PORT", "8888"))

_STATUS_HEALTHY = "healthy"
_STATUS_DEGRADED = "degraded"
_STATUS_UNHEALTHY = "unhealthy"


# ==============================================================================
# REQUEST HANDLER
# ==============================================================================

class _HealthHandler(BaseHTTPRequestHandler):
    """Internal HTTP request handler — delegates to the owning HealthEndpoint."""

    # Silence default request log (endpoint uses TradovLogger)
    def log_message(self, fmt: str, *args: Any) -> None:
        _logger.debug("HealthEndpoint: %s", fmt % args)

    def _send_json(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        endpoint: HealthEndpoint = self.server.health_endpoint  # type: ignore[attr-defined]

        if self.path == "/health":
            body, status_code = endpoint._build_health_response()
            self._send_json(status_code, body)

        elif self.path == "/metrics":
            self._send_json(200, endpoint._build_metrics_response())

        elif self.path == "/ready":
            body, status_code = endpoint._build_ready_response()
            self._send_json(status_code, body)

        else:
            self._send_json(404, {"error": "Not found", "path": self.path})


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class HealthEndpoint:
    """
    Lightweight HTTP health-check endpoint.

    Runs a daemon HTTP server on the configured host:port.  Exposes /health,
    /metrics, and /ready routes.  Probe callbacks are supplied by the caller
    so each subsystem can inject its own health signal.

    Args:
        host: Bind address (default: ``TRADOV_HEALTH_HOST`` env or ``127.0.0.1``).
        port: TCP port (default: ``TRADOV_HEALTH_PORT`` env or ``8888``).
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._host = host
        self._port = port
        self._start_time = time.monotonic()
        self._probes: dict[str, Callable[[], bool]] = {}
        self._ready_gates: dict[str, Callable[[], bool]] = {}
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        _logger.info(
            "HealthEndpoint configured on %s:%d", host, port
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register_probe(
        self,
        series_name: str,
        probe: Callable[[], bool],
    ) -> None:
        """
        Register a health probe for a named series / component.

        Args:
            series_name: Human-readable key (e.g. ``"B_Broker"``).
            probe: Zero-argument callable returning True when healthy.
        """
        self._probes[series_name] = probe
        _logger.debug("HealthEndpoint: registered probe '%s'", series_name)

    def register_ready_gate(
        self,
        gate_name: str,
        gate: Callable[[], bool],
    ) -> None:
        """
        Register a readiness gate that must return True for /ready to pass.

        Args:
            gate_name: Human-readable key.
            gate: Zero-argument callable returning True when ready.
        """
        self._ready_gates[gate_name] = gate
        _logger.debug("HealthEndpoint: registered ready gate '%s'", gate_name)

    def start(self) -> None:
        """Start the HTTP health endpoint in a daemon background thread."""
        if self._thread and self._thread.is_alive():
            _logger.warning("HealthEndpoint: already running")
            return

        server = HTTPServer((self._host, self._port), _HealthHandler)
        server.health_endpoint = self  # type: ignore[attr-defined]
        self._server = server

        self._thread = threading.Thread(
            target=server.serve_forever,
            name="TradovM08-HealthEndpoint",
            daemon=True,
        )
        self._thread.start()
        _logger.info(
            "HealthEndpoint started → http://%s:%d/health", self._host, self._port
        )

    def stop(self) -> None:
        """Shut down the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        _logger.info("HealthEndpoint stopped")

    @property
    def url(self) -> str:
        """Base URL for the health endpoint."""
        return f"http://{self._host}:{self._port}"

    # ------------------------------------------------------------------
    # Internal response builders
    # ------------------------------------------------------------------

    def _run_probes(self) -> dict[str, str]:
        """
        Execute all registered probes and return a name→status mapping.

        Each probe is called in a try/except; exceptions count as unhealthy.
        """
        results: dict[str, str] = {}
        for name, probe in self._probes.items():
            try:
                results[name] = _STATUS_HEALTHY if probe() else _STATUS_UNHEALTHY
            except Exception as exc:
                _logger.debug("HealthEndpoint probe '%s' raised: %s", name, exc)
                results[name] = _STATUS_UNHEALTHY
        return results

    def _aggregate_status(self, series_statuses: dict[str, str]) -> str:
        """Derive overall status from individual series statuses."""
        if not series_statuses:
            return _STATUS_HEALTHY  # No probes registered → assume healthy
        statuses = set(series_statuses.values())
        if _STATUS_UNHEALTHY in statuses:
            return _STATUS_UNHEALTHY
        if _STATUS_DEGRADED in statuses:
            return _STATUS_DEGRADED
        return _STATUS_HEALTHY

    def _build_health_response(self) -> tuple[dict[str, Any], int]:
        """
        Build the /health response body and HTTP status code.

        Returns:
            (response_dict, http_status_code) — 200 for healthy/degraded,
            503 for unhealthy.
        """
        series_statuses = self._run_probes()
        overall = self._aggregate_status(series_statuses)
        uptime = time.monotonic() - self._start_time

        body: dict[str, Any] = {
            "status": overall,
            "uptime_seconds": round(uptime, 1),
            "series": series_statuses,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        http_code = 503 if overall == _STATUS_UNHEALTHY else 200
        return body, http_code

    def _build_ready_response(self) -> tuple[dict[str, Any], int]:
        """
        Build the /ready response.

        Returns 200 when all readiness gates pass, 503 otherwise.
        """
        gates: dict[str, bool] = {}
        for name, gate in self._ready_gates.items():
            try:
                gates[name] = gate()
            except Exception:
                gates[name] = False

        all_ready = all(gates.values()) if gates else True
        body: dict[str, Any] = {
            "ready": all_ready,
            "gates": {k: ("ready" if v else "not_ready") for k, v in gates.items()},
            "timestamp": datetime.now(UTC).isoformat(),
        }
        return body, 200 if all_ready else 503

    def _build_metrics_response(self) -> dict[str, Any]:
        """Build the /metrics response with system resource utilisation."""
        metrics: dict[str, Any] = {
            "uptime_seconds": round(time.monotonic() - self._start_time, 1),
            "active_threads": threading.active_count(),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if _PSUTIL_AVAILABLE:
            try:
                proc = _psutil.Process()
                metrics["cpu_percent"] = proc.cpu_percent(interval=None)
                mem = proc.memory_info()
                metrics["memory_rss_mb"] = round(mem.rss / 1_048_576, 1)
                metrics["memory_vms_mb"] = round(mem.vms / 1_048_576, 1)
            except Exception as exc:
                _logger.debug("HealthEndpoint metrics psutil error: %s", exc)
        return metrics


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_endpoint_instance: HealthEndpoint | None = None


def get_health_endpoint(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> HealthEndpoint:
    """Return (or create) a module-level singleton HealthEndpoint."""
    global _endpoint_instance
    if _endpoint_instance is None:
        _endpoint_instance = HealthEndpoint(host=host, port=port)
    return _endpoint_instance
