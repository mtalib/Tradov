#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovR_Runtime
Module: TradovR05_LivenessMonitor.py
Purpose: Heartbeat file + /healthz loopback server + deadman trigger (v14 O1/O9/A13)

Module Description:
    The LivenessMonitor is a background thread that publishes a liveness
    heartbeat to two channels:

      1. A JSON heartbeat file (default: ~/.tradov_heartbeat) refreshed every
         HEARTBEAT_INTERVAL seconds. Q24 ProductionWatchdog consumes this file
         and alerts if it goes stale.

      2. A loopback HTTP server bound to 127.0.0.1:$TRADOV_HEALTHZ_PORT
         (default 9876) that returns the same JSON on GET /healthz. Bound to
         127.0.0.1 only — never reachable off-host.

    During market hours, the monitor also enforces a "deadman" timer: if the
    EventManager has not processed an event for DEADMAN_SECONDS (default 60),
    the monitor emits KILL_SWITCH with reason="deadman" to halt trading.

    The deadman timer is skipped outside market hours (weekends, overnight) so
    a parked paper session does not page oncall.

Usage::

    monitor = LivenessMonitor(event_manager=em, engine=engine)
    monitor.start()
    # ... runtime ...
    monitor.stop()
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, UTC
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from collections.abc import Callable

from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger


HEARTBEAT_INTERVAL_S = 2.0
DEADMAN_SECONDS_DEFAULT = 60.0
DEFAULT_HEARTBEAT_PATH = str(Path.home() / ".tradov_heartbeat")
DEFAULT_HEALTHZ_PORT = 9876


class _HealthzHandler(BaseHTTPRequestHandler):
    """Serve the current snapshot JSON at GET /healthz."""

    def do_GET(self):  # noqa: N802
        payload_provider: Callable[[], dict] = getattr(self.server, "payload_provider", dict)
        if self.path not in ("/healthz", "/"):
            self.send_response(404)
            self.end_headers()
            return
        try:
            body = json.dumps(payload_provider()).encode("utf-8")
        except Exception as exc:  # pragma: no cover
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(exc).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # noqa: A002
        return


class LivenessMonitor:
    """Heartbeat + /healthz + deadman. Fault-isolated from the main loop."""

    def __init__(
        self,
        event_manager: Any,
        engine: Any = None,
        runtime_context: Any = None,
        heartbeat_path: str = DEFAULT_HEARTBEAT_PATH,
        healthz_port: int | None = None,
        deadman_seconds: float = DEADMAN_SECONDS_DEFAULT,
    ) -> None:
        self.logger = TradovLogger.get_logger(__name__)
        self._em = event_manager
        self._engine = engine
        self._runtime_context = runtime_context
        self._heartbeat_path = heartbeat_path
        self._healthz_port = int(
            healthz_port
            if healthz_port is not None
            else os.environ.get("TRADOV_HEALTHZ_PORT", DEFAULT_HEALTHZ_PORT)
        )
        self._deadman_seconds = float(deadman_seconds)

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._httpd: HTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._deadman_fired = False
        self._last_event_ts: float = time.time()
        self._subscribed = False
        self._paper_deadman_logged = False

    def start(self) -> bool:
        if self._thread is not None and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._deadman_fired = False
        self._last_event_ts = time.time()
        self._subscribe_to_event_manager()
        self._start_healthz_server()
        self._thread = threading.Thread(
            target=self._run_loop, name="LivenessMonitor", daemon=True
        )
        self._thread.start()
        self.logger.debug(
            "LivenessMonitor started — heartbeat=%s healthz=127.0.0.1:%d",
            self._heartbeat_path,
            self._healthz_port,
        )
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
                self._httpd.server_close()
            except Exception as exc:
                self.logger.warning("healthz shutdown raised: %s", exc)
            self._httpd = None
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self.logger.info("LivenessMonitor stopped")

    def _subscribe_to_event_manager(self) -> None:
        if self._em is None or self._subscribed:
            return
        try:
            from Tradov.TradovA_Core.TradovA05_EventManager import EventType

            for et in (
                EventType.MARKET_DATA,
                EventType.ORDER_SUBMITTED,
                EventType.ORDER_FILLED,
                EventType.HEARTBEAT,
            ):
                self._em.subscribe(et, self._on_any_event, name="LivenessMonitor")
            self._subscribed = True
        except Exception as exc:
            self.logger.warning("liveness subscribe failed: %s", exc)

    def _on_any_event(self, event: Any) -> None:
        self._last_event_ts = time.time()

    def _start_healthz_server(self) -> None:
        try:
            self._httpd = HTTPServer(("127.0.0.1", self._healthz_port), _HealthzHandler)
            self._httpd.payload_provider = self._snapshot  # type: ignore[attr-defined]
            self._http_thread = threading.Thread(
                target=self._httpd.serve_forever,
                name="LivenessMonitor-healthz",
                daemon=True,
            )
            self._http_thread.start()
        except OSError as exc:
            self.logger.warning(
                "healthz port %d unavailable (%s); liveness file-only",
                self._healthz_port,
                exc,
            )
            self._httpd = None

    def _snapshot(self) -> dict:
        engine = self._engine
        kill = False
        broker_connected = None
        pending = None
        tracked = None
        try:
            if engine is not None:
                kill = bool(getattr(engine, "_kill_switch_event", None) and engine._kill_switch_event.is_set())  # noqa: E501
                broker_connected = bool(getattr(engine, "broker_connected", True))
                pending = len(getattr(engine, "pending_orders", {}) or {})
                rec = getattr(engine, "_reconciler", None)
                tracked = len(getattr(rec, "_tracked", {}) or {}) if rec is not None else None
        except Exception:
            pass
        return {
            "ts": datetime.now(UTC).isoformat(),
            "kill_switch": kill,
            "broker_connected": broker_connected,
            "pending_orders_count": pending,
            "tracked_orders_count": tracked,
            "last_event_processed_ts": self._last_event_ts,
            "deadman_fired": self._deadman_fired,
            "pid": os.getpid(),
        }

    def _write_heartbeat(self) -> None:
        snap = self._snapshot()
        tmp = self._heartbeat_path + ".tmp"
        try:
            with open(tmp, "w") as fh:
                json.dump(snap, fh)
            os.replace(tmp, self._heartbeat_path)
        except Exception as exc:
            self.logger.warning("heartbeat write failed: %s", exc)

    def _is_market_hours(self) -> bool:
        try:
            from Tradov.TradovU_Utilities.TradovU10_TradingCalendar import get_trading_calendar

            current = datetime.now(UTC).astimezone()
            return bool(get_trading_calendar().is_market_open(current))
        except Exception:
            now = datetime.now(UTC).astimezone()
            if now.weekday() >= 5:
                return False
            hhmm = now.hour * 60 + now.minute
            return 9 * 60 + 30 <= hhmm <= 16 * 60

    def _is_paper_mode(self) -> bool:
        """Best-effort paper-mode detection used for deadman gating."""
        try:
            runtime_context = self._runtime_context
            if runtime_context is not None:
                if bool(getattr(runtime_context, "is_paper", False)):
                    return True
                mode = str(getattr(runtime_context, "mode", "") or "").strip().lower()
                if mode == "paper":
                    return True

            engine = self._engine
            if engine is None:
                mode = str(
                    os.environ.get("TRADING_MODE", "")
                    or os.environ.get("TRADOV_TRADING_MODE", "")
                ).strip().lower()
                return mode == "paper"

            engine_mode = getattr(engine, "mode", None)
            if engine_mode is not None:
                mode_value = getattr(engine_mode, "value", engine_mode)
                mode_name = getattr(engine_mode, "name", engine_mode)
                if str(mode_value).strip().lower() == "paper" or str(mode_name).strip().lower() == "paper":
                    return True

            config = getattr(engine, "config", None)
            for attr_name in ("mode", "trading_mode"):
                config_mode = getattr(config, attr_name, None)
                if config_mode is None:
                    continue
                mode_value = getattr(config_mode, "value", config_mode)
                mode_name = getattr(config_mode, "name", config_mode)
                if str(mode_value).strip().lower() == "paper" or str(mode_name).strip().lower() == "paper":
                    return True

            account_id = str(getattr(config, "account_id", "") or "").upper()
            if account_id.startswith("PAPER"):
                return True

            broker = getattr(engine, "broker", None)
            broker_name = type(broker).__name__.lower() if broker is not None else ""
            if "paper" in broker_name:
                return True

            mode = str(
                os.environ.get("TRADING_MODE", "")
                or os.environ.get("TRADOV_TRADING_MODE", "")
            ).strip().lower()
            return mode == "paper"
        except Exception:
            return False

    def _maybe_fire_deadman(self) -> None:
        if self._deadman_fired or self._em is None:
            return
        lag = time.time() - self._last_event_ts
        if self._is_paper_mode():
            if (lag > self._deadman_seconds) and (not self._paper_deadman_logged):
                self.logger.debug(
                    "DEADMAN advisory (paper mode): no events for %.1fs (threshold=%.1fs); kill-switch emission suppressed",  # noqa: E501
                    lag,
                    self._deadman_seconds,
                )
                self._paper_deadman_logged = True
            return
        if not self._is_market_hours():
            return
        if lag <= self._deadman_seconds:
            return
        self.logger.error(
            "DEADMAN: no events for %.1fs (threshold=%.1fs) — emitting KILL_SWITCH",
            lag,
            self._deadman_seconds,
        )
        try:
            from Tradov.TradovA_Core.TradovA05_EventManager import EventType

            self._em.emit(
                EventType.KILL_SWITCH,
                {"reason": "deadman", "lag_seconds": lag},
                source="LivenessMonitor",
            )
            self._deadman_fired = True
        except Exception as exc:
            self.logger.error("deadman KILL_SWITCH emit failed: %s", exc)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._write_heartbeat()
                self._maybe_fire_deadman()
            except Exception as exc:
                self.logger.warning("liveness tick raised: %s", exc)
            self._stop_event.wait(HEARTBEAT_INTERVAL_S)


def create_liveness_monitor(
    event_manager: Any,
    engine: Any = None,
    runtime_context: Any = None,
    heartbeat_path: str | None = None,
    healthz_port: int | None = None,
    deadman_seconds: float = DEADMAN_SECONDS_DEFAULT,
) -> LivenessMonitor:
    return LivenessMonitor(
        event_manager=event_manager,
        engine=engine,
        runtime_context=runtime_context,
        heartbeat_path=heartbeat_path or DEFAULT_HEARTBEAT_PATH,
        healthz_port=healthz_port,
        deadman_seconds=deadman_seconds,
    )
