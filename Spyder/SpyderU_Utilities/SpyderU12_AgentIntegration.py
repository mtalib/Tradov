#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderU_Utilities
Module: SpyderU12_AgentIntegration.py
Purpose: Centralised agent registry, health aggregator, and lifecycle manager

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-01

Module Description:
    Provides a thread-safe registry that both X-series (on-demand) and
    Y-series (daemon) agents can register with at startup.  Consumers
    (dashboards, orchestrators, monitoring) use this module as the single
    source of truth for agent availability and health.

Key Features:
    • Agent registration with metadata (series, description, version)
    • Heartbeat tracking — agents call heartbeat() to signal liveness
    • Health polling — last-heartbeat age used to derive UP / DEGRADED / DOWN
    • Lifecycle events — start / stop callbacks per agent
    • Thread-safe reads and writes via RLock
    • Module-level singleton get_registry() for convenience

Dependencies:
    • Python standard library only
    • SpyderU01_Logger (graceful fallback to stdlib logging)
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import StrEnum
from typing import Any
from collections.abc import Callable

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    _log = SpyderLogger.get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

# ==============================================================================
# CONSTANTS
# ==============================================================================
# An agent is DEGRADED if its last heartbeat is older than this many seconds.
_HEARTBEAT_DEGRADED_SECS = 30
# An agent is DOWN if its last heartbeat is older than this many seconds.
_HEARTBEAT_DOWN_SECS = 120


# ==============================================================================
# ENUMS & DATA STRUCTURES
# ==============================================================================

class AgentSeries(StrEnum):
    """Which series the agent belongs to."""
    X = "X"        # on-demand agents
    Y = "Y"        # daemon agents
    OTHER = "OTHER"


class AgentStatus(StrEnum):
    """Derived health status based on heartbeat age."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    STARTING = "starting"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


# Backward-compatible aliases used by older call-sites.
AgentStatus.UP = AgentStatus.ACTIVE
AgentStatus.DEGRADED = AgentStatus.INACTIVE
AgentStatus.DOWN = AgentStatus.ERROR


@dataclass
class AgentMetrics:
    """Per-agent runtime metrics populated by the agent itself.

    Includes backward-compatible fields expected by older utility tests.
    """
    # Legacy/general fields
    agent_id: str = "unknown"
    status: AgentStatus = AgentStatus.UNKNOWN
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    uptime_seconds: float = 0.0
    requests_processed: int = 0
    errors_count: int = 0
    last_activity: datetime | None = None
    metadata: dict[str, Any] | None = None

    # Current dashboard-focused fields
    decisions_made: int = 0
    decisions_failed: int = 0
    avg_latency_ms: float = 0.0
    last_error: str = ""
    custom: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}
        # Keep legacy metadata and current custom map in sync by default.
        if not self.custom and self.metadata:
            self.custom = dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "status": self.status.value if isinstance(self.status, AgentStatus) else str(self.status),  # noqa: E501
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "uptime_seconds": self.uptime_seconds,
            "requests_processed": self.requests_processed,
            "errors_count": self.errors_count,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "metadata": self.metadata or {},
            "decisions_made": self.decisions_made,
            "decisions_failed": self.decisions_failed,
            "avg_latency_ms": self.avg_latency_ms,
            "last_error": self.last_error,
            "custom": self.custom,
        }


@dataclass
class AgentRecord:
    """Full registration record for one agent."""
    agent_id:      str
    series:        AgentSeries
    description:   str
    version:       str = "1.0.0"
    registered_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_heartbeat: datetime | None = None
    metrics:       AgentMetrics = field(default_factory=AgentMetrics)
    _running:      bool = False
    _callbacks_start: list[Callable] = field(default_factory=list, repr=False)
    _callbacks_stop:  list[Callable] = field(default_factory=list, repr=False)

    @property
    def status(self) -> AgentStatus:
        if self.last_heartbeat is None:
            return AgentStatus.UNKNOWN
        age = (datetime.now(UTC) - self.last_heartbeat).total_seconds()
        if age <= _HEARTBEAT_DEGRADED_SECS:
            return AgentStatus.ACTIVE
        if age <= _HEARTBEAT_DOWN_SECS:
            return AgentStatus.INACTIVE
        return AgentStatus.ERROR

    @property
    def is_running(self) -> bool:
        return self._running

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id":       self.agent_id,
            "series":         self.series.value,
            "description":    self.description,
            "version":        self.version,
            "registered_at":  self.registered_at.isoformat(),
            "last_heartbeat": self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            "status":         self.status.value,
            "running":        self._running,
            "metrics": {
                "decisions_made":   self.metrics.decisions_made,
                "decisions_failed": self.metrics.decisions_failed,
                "avg_latency_ms":   self.metrics.avg_latency_ms,
                "last_error":       self.metrics.last_error,
                "custom":           self.metrics.custom,
            },
        }


# ==============================================================================
# REGISTRY
# ==============================================================================

class AgentRegistry:
    """
    Thread-safe registry for all Spyder X- and Y-series agents.

    Example usage (from any agent module)::

        from SpyderU_Utilities.SpyderU12_AgentIntegration import get_registry, AgentSeries

        _reg = get_registry()
        _reg.register("X01_Greeks", AgentSeries.X, "Real-time Greeks calculation")

        # In the agent's main loop:
        _reg.heartbeat("X01_Greeks")

        # When the agent starts / stops:
        _reg.mark_started("X01_Greeks")
        _reg.mark_stopped("X01_Greeks")

        # Update runtime metrics:
        _reg.update_metrics("X01_Greeks", decisions_made=42, avg_latency_ms=3.2)
    """

    def __init__(self) -> None:
        self._lock: threading.RLock = threading.RLock()
        self._agents: dict[str, AgentRecord] = {}
        self._log = _log

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        agent_id:    str,
        series:      AgentSeries | str = AgentSeries.OTHER,
        description: str = "",
        version:     str = "1.0.0",
    ) -> AgentRecord:
        """Register an agent.  Safe to call multiple times (idempotent)."""
        if isinstance(series, str):
            try:
                series = AgentSeries(series.upper())
            except ValueError:
                series = AgentSeries.OTHER
        with self._lock:
            if agent_id not in self._agents:
                record = AgentRecord(
                    agent_id=agent_id,
                    series=series,
                    description=description,
                    version=version,
                )
                self._agents[agent_id] = record
                self._log.info("Agent registered: %s (%s)", agent_id, series.value)
            return self._agents[agent_id]

    def unregister(self, agent_id: str) -> bool:
        """Remove an agent from the registry.  Returns True if it existed."""
        with self._lock:
            existed = agent_id in self._agents
            self._agents.pop(agent_id, None)
            if existed:
                self._log.info("Agent unregistered: %s", agent_id)
            return existed

    # ------------------------------------------------------------------
    # Heartbeat & lifecycle
    # ------------------------------------------------------------------

    def heartbeat(self, agent_id: str) -> None:
        """Record a liveness heartbeat for agent_id."""
        with self._lock:
            record = self._agents.get(agent_id)
            if record is None:
                self._log.warning("heartbeat() called for unknown agent: %s", agent_id)
                return
            record.last_heartbeat = datetime.now(UTC)

    def mark_started(self, agent_id: str) -> None:
        """Signal that an agent has started its main loop."""
        with self._lock:
            record = self._agents.get(agent_id)
            if record is None:
                return
            record._running = True
            record.last_heartbeat = datetime.now(UTC)
            callbacks = list(record._callbacks_start)
        for cb in callbacks:
            try:
                cb(agent_id)
            except Exception as exc:
                self._log.error("Start callback error for %s: %s", agent_id, exc)
        self._log.info("Agent started: %s", agent_id)

    def mark_stopped(self, agent_id: str) -> None:
        """Signal that an agent has stopped its main loop."""
        with self._lock:
            record = self._agents.get(agent_id)
            if record is None:
                return
            record._running = False
            callbacks = list(record._callbacks_stop)
        for cb in callbacks:
            try:
                cb(agent_id)
            except Exception as exc:
                self._log.error("Stop callback error for %s: %s", agent_id, exc)
        self._log.info("Agent stopped: %s", agent_id)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def update_metrics(
        self,
        agent_id: str,
        *,
        decisions_made:   int   | None = None,
        decisions_failed: int   | None = None,
        avg_latency_ms:   float | None = None,
        last_error:       str   | None = None,
        custom:           dict[str, Any] | None = None,
    ) -> None:
        """Update runtime metrics for an agent (partial update; None fields ignored)."""
        with self._lock:
            record = self._agents.get(agent_id)
            if record is None:
                return
            m = record.metrics
            if decisions_made is not None:
                m.decisions_made = decisions_made
            if decisions_failed is not None:
                m.decisions_failed = decisions_failed
            if avg_latency_ms is not None:
                m.avg_latency_ms = avg_latency_ms
            if last_error is not None:
                m.last_error = last_error
            if custom is not None:
                m.custom.update(custom)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_start(self, agent_id: str, callback: Callable[[str], None]) -> None:
        """Register a callback invoked when agent_id calls mark_started()."""
        with self._lock:
            record = self._agents.get(agent_id)
            if record and callback not in record._callbacks_start:
                record._callbacks_start.append(callback)

    def on_stop(self, agent_id: str, callback: Callable[[str], None]) -> None:
        """Register a callback invoked when agent_id calls mark_stopped()."""
        with self._lock:
            record = self._agents.get(agent_id)
            if record and callback not in record._callbacks_stop:
                record._callbacks_stop.append(callback)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, agent_id: str) -> AgentRecord | None:
        """Return the AgentRecord for agent_id, or None."""
        with self._lock:
            return self._agents.get(agent_id)

    def all_agents(self) -> list[AgentRecord]:
        """Return a snapshot of all registered agents."""
        with self._lock:
            return list(self._agents.values())

    def agents_by_series(self, series: AgentSeries | str) -> list[AgentRecord]:
        """Return agents belonging to series."""
        if isinstance(series, str):
            try:
                series = AgentSeries(series.upper())
            except ValueError:
                series = AgentSeries.OTHER
        with self._lock:
            return [r for r in self._agents.values() if r.series == series]

    def agents_by_status(self, status: AgentStatus | str) -> list[AgentRecord]:
        """Return agents with the given health status."""
        if isinstance(status, str):
            status = AgentStatus(status.upper())
        with self._lock:
            return [r for r in self._agents.values() if r.status == status]

    def health_summary(self) -> dict[str, Any]:
        """Return an aggregate health snapshot for dashboards / monitoring."""
        with self._lock:
            records = list(self._agents.values())

        by_status: dict[str, int] = {s.value: 0 for s in AgentStatus}
        by_series: dict[str, int] = {s.value: 0 for s in AgentSeries}
        running = 0

        for r in records:
            by_status[r.status.value] += 1
            by_series[r.series.value] += 1
            if r.is_running:
                running += 1

        return {
            "total":     len(records),
            "running":   running,
            "by_status": by_status,
            "by_series": by_series,
            "agents":    [r.to_dict() for r in records],
        }

    def __len__(self) -> int:
        with self._lock:
            return len(self._agents)

    def __contains__(self, agent_id: str) -> bool:
        with self._lock:
            return agent_id in self._agents


# ==============================================================================
# MODULE-LEVEL SINGLETON
# ==============================================================================

_registry: AgentRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> AgentRegistry:
    """Return the module-level AgentRegistry singleton."""
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = AgentRegistry()
    return _registry
