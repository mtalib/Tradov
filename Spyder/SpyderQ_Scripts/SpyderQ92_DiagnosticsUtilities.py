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
import re
import importlib
import platform
import pkg_resources
from collections import deque
from datetime import datetime, UTC
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from enum import Enum
from zoneinfo import ZoneInfo
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
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from Spyder.SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
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
MARKET_DATA_DIR = Path(SPYDER_HOME) / "market_data"
try:
    ET_ZONE = ZoneInfo("America/New_York")
except Exception:
    ET_ZONE = UTC
DEFAULT_SESSION_WINDOW = {
    "primary_start_et": "09:30",
    "primary_end_et": "16:15",
    "first_entry_not_before_et": "09:45",
    "zero_dte_no_new_risk_cutoff_et": "14:30",
    "broker_cutoff_et": "16:00",
}
DEFAULT_MAX_DAILY_TRADES = 100

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
    "Spyder.SpyderU_Utilities": "Utility modules",
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
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

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
            timestamp=datetime.now(UTC),
            system_info=system_info,
            test_results=self.results,
            summary=summary,
            recommendations=recommendations,
            total_duration_ms=total_duration
        )

        return report

    def collect_trading_health(
        self,
        *,
        run_mode: str | None = None,
        now_utc: datetime | None = None,
        recent_event_limit: int = 5,
        session_window: dict[str, Any] | None = None,
        max_daily_trades: int | None = None,
        decision_log_path: Path | None = None,
        launcher_log_path: Path | None = None,
        paper_state_path: Path | None = None,
        dashboard_snapshot_path: Path | None = None,
        session_db: Any | None = None,
    ) -> dict[str, Any]:
        """Collect a one-shot trading workflow health report from persisted artifacts."""
        report_time_utc = now_utc or datetime.now(UTC)
        config_payload = self._load_trading_health_config()

        resolved_session_window = dict(DEFAULT_SESSION_WINDOW)
        resolved_session_window.update(config_payload.get("session_window", {}))
        if isinstance(session_window, dict):
            resolved_session_window.update(session_window)

        resolved_run_mode = self._resolve_trading_health_run_mode(
            requested_run_mode=run_mode,
            dashboard_snapshot_path=dashboard_snapshot_path,
        )
        resolved_recent_event_limit = max(0, int(recent_event_limit))
        resolved_max_daily_trades = int(
            max_daily_trades
            if max_daily_trades is not None
            else config_payload.get("max_daily_trades", DEFAULT_MAX_DAILY_TRADES)
        )

        resolved_decision_log_path = (
            Path(decision_log_path)
            if decision_log_path is not None
            else self._resolve_trading_health_decision_log_path(
                run_mode=resolved_run_mode,
                now_utc=report_time_utc,
            )
        )
        resolved_launcher_log_path = (
            Path(launcher_log_path)
            if launcher_log_path is not None
            else LOGS_DIR / "launcher" / "spyder-desktop-launch.log"
        )
        resolved_paper_state_path = (
            Path(paper_state_path)
            if paper_state_path is not None
            else MARKET_DATA_DIR / "paper_trading_state.json"
        )

        last_dispatch_result = self._read_last_decision_event(
            resolved_decision_log_path,
            {"dispatch_submitted", "dispatch_rejected"},
        )
        last_drop_reason = self._read_last_decision_event(
            resolved_decision_log_path,
            {"signal_dropped"},
        )
        recent_decision_flow = self.collect_recent_decision_flow(
            run_mode=resolved_run_mode,
            now_utc=report_time_utc,
            limit=resolved_recent_event_limit,
            decision_log_path=resolved_decision_log_path,
        )
        engine_state = self._extract_engine_state(
            run_mode=resolved_run_mode,
            launcher_log_path=resolved_launcher_log_path,
        )

        trades_today: list[dict[str, Any]] = []
        latest_snapshot: dict[str, Any] | None = None
        resolved_session_db = session_db or self._open_trading_health_session_db(resolved_run_mode)
        if resolved_session_db is not None:
            try:
                trades_today = list(resolved_session_db.get_trades_today() or [])
            except Exception as exc:
                self.logger.debug("Trading-health: get_trades_today failed: %s", exc)
            try:
                latest_snapshot = resolved_session_db.get_latest_snapshot()
            except Exception as exc:
                self.logger.debug("Trading-health: get_latest_snapshot failed: %s", exc)

        paper_state = self._read_json_file(resolved_paper_state_path)
        latest_trade = trades_today[-1] if trades_today else None
        paper_state_total_executed = self._coerce_int(
            paper_state.get("_trades_executed") if isinstance(paper_state, dict) else None
        )
        latest_snapshot_total_trades = self._coerce_int(
            latest_snapshot.get("total_trades") if isinstance(latest_snapshot, dict) else None
        )

        return {
            "generated_at_utc": report_time_utc.isoformat(),
            "generated_at_et": report_time_utc.astimezone(ET_ZONE).isoformat(),
            "run_mode": resolved_run_mode,
            "market_window": self._evaluate_session_window(
                report_time_utc,
                resolved_session_window,
            ),
            "engine_state": engine_state,
            "daily_trades": {
                "count": len(trades_today),
                "max_daily_trades": resolved_max_daily_trades,
                "limit_reached": len(trades_today) >= resolved_max_daily_trades,
                "source": "TradingSessionDB.get_trades_today()",
                "latest_trade_ts_utc": latest_trade.get("timestamp") if isinstance(latest_trade, dict) else None,
                "account_snapshot_total_trades": latest_snapshot_total_trades,
                "paper_state_total_executed": paper_state_total_executed,
                "db_path": str(getattr(resolved_session_db, "db_path", "")) or None,
            },
            "last_dispatch_result": self._compact_decision_event(last_dispatch_result),
            "last_drop_reason": self._compact_decision_event(last_drop_reason),
            "recent_decision_flow": recent_decision_flow,
            "artifacts": {
                "decision_log": str(resolved_decision_log_path) if resolved_decision_log_path else None,
                "launcher_log": str(resolved_launcher_log_path) if resolved_launcher_log_path else None,
                "paper_state": str(resolved_paper_state_path) if resolved_paper_state_path else None,
            },
        }

    def _load_trading_health_config(self) -> dict[str, Any]:
        """Load session-window policy and trade-limit config with safe fallbacks."""
        config_payload = {
            "session_window": dict(DEFAULT_SESSION_WINDOW),
            "max_daily_trades": DEFAULT_MAX_DAILY_TRADES,
        }

        try:
            from Spyder.SpyderA_Core.SpyderA03_Configuration import ConfigManager  # noqa: PLC0415

            environment = str(os.environ.get("SPYDER_ENVIRONMENT", "production")).strip() or "production"
            config_manager = ConfigManager(environment=environment, auto_reload=False)
            session_window = config_manager.get("autonomous_readiness.session_window", {})
            if isinstance(session_window, dict):
                config_payload["session_window"].update(session_window)

            config_payload["max_daily_trades"] = int(
                config_manager.get("trading.max_daily_trades", DEFAULT_MAX_DAILY_TRADES)
            )
        except Exception as exc:
            self.logger.debug("Trading-health config fallback to defaults: %s", exc)

        return config_payload

    def _resolve_trading_health_run_mode(
        self,
        *,
        requested_run_mode: str | None,
        dashboard_snapshot_path: Path | None,
    ) -> str:
        """Resolve run mode for trading-health, preferring explicit input then dashboard snapshot."""
        if requested_run_mode in {"paper", "live"}:
            return str(requested_run_mode)

        snapshot_path = dashboard_snapshot_path or (MARKET_DATA_DIR / "dashboard_snapshot.json")
        snapshot = self._read_json_file(snapshot_path)
        if isinstance(snapshot, dict):
            trading_mode = str(snapshot.get("trading_mode", "")).strip().lower()
            if trading_mode in {"paper", "live"}:
                return trading_mode

        return "paper"

    def _resolve_trading_health_decision_log_path(
        self,
        *,
        run_mode: str,
        now_utc: datetime,
    ) -> Path | None:
        """Resolve the current decision log path, falling back to the latest available file."""
        day_key = now_utc.strftime("%Y-%m-%d")
        candidate_dirs = [LOGS_DIR / "decisions" / run_mode, LOGS_DIR / "decisions"]

        for directory in candidate_dirs:
            candidate = directory / f"{day_key}.jsonl"
            if candidate.exists():
                return candidate

        latest_match: Path | None = None
        latest_mtime = -1.0
        for directory in candidate_dirs:
            if not directory.exists():
                continue
            for entry in directory.glob("*.jsonl"):
                try:
                    mtime = entry.stat().st_mtime
                except OSError:
                    continue
                if mtime > latest_mtime:
                    latest_mtime = mtime
                    latest_match = entry

        return latest_match

    def collect_recent_decision_flow(
        self,
        *,
        run_mode: str | None = None,
        now_utc: datetime | None = None,
        limit: int = 5,
        decision_log_path: Path | None = None,
        dashboard_snapshot_path: Path | None = None,
    ) -> dict[str, Any]:
        """Collect the most recent D31 dispatch/drop events without full health scanning."""
        report_time_utc = now_utc or datetime.now(UTC)
        resolved_run_mode = self._resolve_trading_health_run_mode(
            requested_run_mode=run_mode,
            dashboard_snapshot_path=dashboard_snapshot_path,
        )
        resolved_limit = max(0, int(limit))
        resolved_decision_log_path = (
            Path(decision_log_path)
            if decision_log_path is not None
            else self._resolve_trading_health_decision_log_path(
                run_mode=resolved_run_mode,
                now_utc=report_time_utc,
            )
        )

        return {
            "limit": resolved_limit,
            "run_mode": resolved_run_mode,
            "dispatch": self._read_recent_decision_events(
                resolved_decision_log_path,
                {"dispatch_submitted", "dispatch_rejected"},
                limit=resolved_limit,
            ),
            "drops": self._read_recent_decision_events(
                resolved_decision_log_path,
                {"signal_dropped"},
                limit=resolved_limit,
            ),
            "decision_log": str(resolved_decision_log_path) if resolved_decision_log_path else None,
        }

    def _read_last_decision_event(
        self,
        decision_log_path: Path | None,
        event_names: set[str],
    ) -> dict[str, Any] | None:
        """Read the last matching decision-audit event from a JSONL file."""
        if decision_log_path is None or not decision_log_path.exists():
            return None

        last_match: dict[str, Any] | None = None
        try:
            with open(decision_log_path, encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("event") in event_names:
                        last_match = record
        except OSError as exc:
            self.logger.debug("Trading-health: failed reading %s: %s", decision_log_path, exc)

        return last_match

    def _read_recent_decision_events(
        self,
        decision_log_path: Path | None,
        event_names: set[str],
        *,
        limit: int,
    ) -> list[dict[str, Any]]:
        """Read the most recent matching decision-audit events from a JSONL file."""
        safe_limit = max(0, int(limit))
        if safe_limit == 0 or decision_log_path is None or not decision_log_path.exists():
            return []

        matches: deque[dict[str, Any]] = deque(maxlen=safe_limit)
        try:
            with open(decision_log_path, encoding="utf-8") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if record.get("event") in event_names:
                        compact = self._compact_decision_event(record)
                        if compact is not None:
                            matches.append(compact)
        except OSError as exc:
            self.logger.debug(
                "Trading-health: failed reading recent events from %s: %s",
                decision_log_path,
                exc,
            )
            return []

        return list(reversed(matches))

    def _compact_decision_event(self, record: dict[str, Any] | None) -> dict[str, Any] | None:
        """Reduce a decision-audit record to the fields used by diagnostics."""
        if not isinstance(record, dict):
            return None

        return {
            "ts_utc": record.get("ts_utc"),
            "event": record.get("event"),
            "stage": record.get("stage"),
            "reason": record.get("reason"),
            "detail": record.get("detail"),
            "symbol": record.get("symbol"),
            "strategy_id": record.get("strategy_id"),
            "session_id": record.get("session_id"),
        }

    def _extract_engine_state(self, run_mode: str, launcher_log_path: Path) -> dict[str, Any]:
        """Extract the latest observable engine state from the desktop launcher log."""
        result = {
            "state": "unknown",
            "detail": "No engine lifecycle line found",
            "observed_at": None,
            "last_rejection_reason": None,
            "last_rejection_at": None,
            "log_path": str(launcher_log_path),
        }
        if not launcher_log_path.exists():
            result["state"] = "missing_log"
            result["detail"] = "Launcher log not found"
            return result

        mode_label = "Paper" if run_mode == "paper" else "Live"
        lifecycle_patterns = [
            (
                re.compile(rf"{mode_label} trading deferred until market open \((?P<reason>[^)]+)\)"),
                lambda match: {
                    "state": "deferred_until_market_open",
                    "detail": match.group("reason"),
                },
            ),
            (
                re.compile(rf"{mode_label} trading started - Session: (?P<session>\S+)"),
                lambda match: {
                    "state": "trading",
                    "detail": match.group("session"),
                    "session_id": match.group("session"),
                },
            ),
            (
                re.compile(r"Trading not active: (?P<state>[A-Za-z_]+)"),
                lambda match: {
                    "state": match.group("state").lower(),
                    "detail": f"Trading not active: {match.group('state').lower()}",
                },
            ),
            (
                re.compile(rf"{mode_label} trading stopped"),
                lambda _match: {
                    "state": "stopped",
                    "detail": f"{mode_label.lower()} trading stopped",
                },
            ),
            (
                re.compile(r"SessionSupervisor autostart disabled in A01"),
                lambda _match: {
                    "state": "autostart_disabled",
                    "detail": "SessionSupervisor autostart disabled in A01",
                },
            ),
        ]
        rejection_pattern = re.compile(
            r"Market order rejected by live engine: .* reason=(?P<reason>[^|]+)"
        )

        try:
            with open(launcher_log_path, encoding="utf-8", errors="replace") as handle:
                for raw_line in handle:
                    parsed = self._parse_log_line(raw_line)
                    message = str(parsed["message"] or "")

                    rejection_match = rejection_pattern.search(message)
                    if rejection_match:
                        result["last_rejection_reason"] = rejection_match.group("reason").strip()
                        result["last_rejection_at"] = parsed["timestamp"]

                    for pattern, builder in lifecycle_patterns:
                        match = pattern.search(message)
                        if match:
                            result.update(builder(match))
                            result["observed_at"] = parsed["timestamp"]
                            break
        except OSError as exc:
            self.logger.debug(
                "Trading-health: failed scanning launcher log %s: %s",
                launcher_log_path,
                exc,
            )

        return result

    def _parse_log_line(self, raw_line: str) -> dict[str, str | None]:
        """Split a launcher log line into timestamp and message when possible."""
        text = str(raw_line).strip()
        match = re.match(
            r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d+)?) - .* - [A-Z]+ - (?P<message>.*)$",
            text,
        )
        if match:
            return {
                "timestamp": match.group("ts"),
                "message": match.group("message").strip(),
            }
        return {"timestamp": None, "message": text}

    def _open_trading_health_session_db(self, run_mode: str) -> Any | None:
        """Open the H05 trading-session DB for the requested mode."""
        try:
            from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB  # noqa: PLC0415

            return TradingSessionDB.for_live() if run_mode == "live" else TradingSessionDB.for_paper()
        except Exception as exc:
            self.logger.debug("Trading-health DB unavailable: %s", exc)
            return None

    def _read_json_file(self, file_path: Path | None) -> dict[str, Any] | None:
        """Read a JSON file into a dictionary, returning None on failure."""
        if file_path is None or not Path(file_path).exists():
            return None
        try:
            with open(file_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else None
        except (OSError, json.JSONDecodeError) as exc:
            self.logger.debug("Trading-health JSON read failed for %s: %s", file_path, exc)
            return None

    def _evaluate_session_window(
        self,
        now_utc: datetime,
        session_window: dict[str, Any],
    ) -> dict[str, Any]:
        """Evaluate the configured trading session window at the current ET time."""
        now_et = now_utc.astimezone(ET_ZONE)
        now_time = now_et.time().replace(tzinfo=None)

        start = datetime.strptime(
            str(session_window.get("primary_start_et", DEFAULT_SESSION_WINDOW["primary_start_et"])),
            "%H:%M",
        ).time()
        end = datetime.strptime(
            str(session_window.get("primary_end_et", DEFAULT_SESSION_WINDOW["primary_end_et"])),
            "%H:%M",
        ).time()
        first_entry = datetime.strptime(
            str(
                session_window.get(
                    "first_entry_not_before_et",
                    DEFAULT_SESSION_WINDOW["first_entry_not_before_et"],
                )
            ),
            "%H:%M",
        ).time()
        new_risk_cutoff = datetime.strptime(
            str(
                session_window.get(
                    "zero_dte_no_new_risk_cutoff_et",
                    DEFAULT_SESSION_WINDOW["zero_dte_no_new_risk_cutoff_et"],
                )
            ),
            "%H:%M",
        ).time()
        broker_cutoff = datetime.strptime(
            str(session_window.get("broker_cutoff_et", DEFAULT_SESSION_WINDOW["broker_cutoff_et"])),
            "%H:%M",
        ).time()

        weekend_block = now_et.weekday() >= 5
        within_primary_window = (not weekend_block) and start <= now_time <= end
        entries_allowed = within_primary_window and first_entry <= now_time < new_risk_cutoff
        before_broker_cutoff = (not weekend_block) and now_time < broker_cutoff

        if weekend_block:
            status = "closed"
            gate_reason = "session_window:weekend_block"
        elif not within_primary_window:
            status = "closed"
            gate_reason = "session_window:outside_primary_window"
        elif now_time < first_entry:
            status = "warmup"
            gate_reason = "session_window:first_entry_not_before"
        elif now_time >= broker_cutoff:
            status = "broker_cutoff"
            gate_reason = "session_window:broker_cutoff"
        elif now_time >= new_risk_cutoff:
            status = "no_new_risk"
            gate_reason = "session_window:zero_dte_no_new_risk_cutoff"
        else:
            status = "open"
            gate_reason = ""

        return {
            "status": status,
            "gate_reason": gate_reason,
            "now_et": now_et.isoformat(),
            "weekday": now_et.strftime("%A"),
            "within_primary_window": within_primary_window,
            "entries_allowed": entries_allowed,
            "before_broker_cutoff": before_broker_cutoff,
            "primary_start_et": start.strftime("%H:%M"),
            "primary_end_et": end.strftime("%H:%M"),
            "first_entry_not_before_et": first_entry.strftime("%H:%M"),
            "zero_dte_no_new_risk_cutoff_et": new_risk_cutoff.strftime("%H:%M"),
            "broker_cutoff_et": broker_cutoff.strftime("%H:%M"),
        }

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        """Best-effort integer conversion for optional diagnostic fields."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
            filename = f"diagnostic_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"

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
