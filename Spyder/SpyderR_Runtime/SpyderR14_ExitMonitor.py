#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR14_ExitMonitor.py
Purpose: Periodic sweep of open positions; emits close signals and orphan alerts

Author: SPYDER Trading System
Year Created: 2026
Last Updated: 2026-04-18 Time: 12:30:00

Module Description:
    ExitMonitor runs a 1-second background sweep over all positions held in
    P01 PortfolioManager.  For every open position it:

      1. Resolves the owning strategy from the registered strategy map.
      2. Calls ``strategy.check_exit(position)`` → ``ExitDecision | None``.
         - ``None``           → nothing to do
         - ``ExitDecision.CLOSE`` → emit STRATEGY_SIGNAL (action='close')
      3. If no owning strategy is found → emit RISK_VIOLATION (orphan alert).

    The monitor is started/stopped by SessionSupervisor and shares the
    singleton EventManager.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable  # noqa: F401

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderA_Core.SpyderA05_EventManager import get_event_manager, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
_DEFAULT_SWEEP_INTERVAL_S: float = 1.0


# ==============================================================================
# TYPES
# ==============================================================================

class ExitDecision(str, Enum):
    """Possible decisions returned by ``strategy.check_exit(position)``."""
    HOLD = "hold"
    CLOSE = "close"


@dataclass
class _PositionView:
    """Minimal position snapshot passed to ``check_exit``."""
    symbol: str
    strategy_id: str
    quantity: float
    cost_basis: float
    current_price: float
    unrealized_pnl: float
    raw: dict[str, Any]


# ==============================================================================
# EXIT MONITOR
# ==============================================================================

class ExitMonitor:
    """Periodic position sweep that enforces exit rules and detects orphans.

    Args:
        portfolio_manager: P01 PortfolioManager (or compatible object with a
            ``portfolio_positions`` dict attribute).
        strategy_map: Dict mapping ``strategy_id → strategy`` instance.
            Each strategy must implement
            ``check_exit(position: _PositionView) -> ExitDecision | None``.
        event_manager: Shared EventManager.  If ``None``, the singleton is
            used.
        portfolio_manager_provider: Optional callable used to lazily resolve a
            PortfolioManager after startup if one was not available initially.
        sweep_interval_s: Seconds between sweeps.  Default 1.0.
    """

    def __init__(
        self,
        portfolio_manager: Any,
        strategy_map: dict[str, Any] | None = None,
        event_manager: Any = None,
        portfolio_manager_provider: Callable[[], Any | None] | None = None,
        sweep_interval_s: float = _DEFAULT_SWEEP_INTERVAL_S,
    ) -> None:
        self.portfolio_manager = portfolio_manager
        self.strategy_map: dict[str, Any] = strategy_map or {}
        self.em = event_manager or get_event_manager()
        self._portfolio_manager_provider = portfolio_manager_provider
        self.sweep_interval_s = sweep_interval_s

        self.logger = SpyderLogger.get_logger(__name__)
        self._running = False
        self._thread: threading.Thread | None = None

        # Track which orphan symbols we have already alerted on to avoid spam
        self._orphan_alerted: set[str] = set()
        # C5 (v18): protect _orphan_alerted against concurrent reads/writes
        # from the sweep thread vs. register_strategy/unregister_strategy.
        self._orphan_lock = threading.Lock()

        # Prometheus metrics — soft-import; silently disabled if unavailable.
        self._prom: Any = None
        try:
            from Spyder.SpyderB_Broker.SpyderB15_PrometheusMetrics import PrometheusMetrics
            self._prom = PrometheusMetrics.get_instance()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start the background sweep thread."""
        if self._running:
            return True
        self._running = True
        self._thread = threading.Thread(
            target=self._sweep_loop,
            name="ExitMonitor",
            daemon=True,
        )
        self._thread.start()
        self.logger.debug("ExitMonitor started (interval=%.1fs)", self.sweep_interval_s)
        return True

    def stop(self) -> None:
        """Stop the background sweep thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self.sweep_interval_s + 1.0)
        self._thread = None
        self.logger.info("ExitMonitor stopped")

    def register_strategy(self, strategy_id: str, strategy: Any) -> None:
        """Register (or update) a strategy so positions can be attributed."""
        self.strategy_map[strategy_id] = strategy

    def unregister_strategy(self, strategy_id: str) -> None:
        """Remove a strategy from the map (positions become orphans)."""
        self.strategy_map.pop(strategy_id, None)
        # Reset orphan alert cache so a fresh alert fires
        # C5 (v18): acquire lock before mutating the shared set.
        with self._orphan_lock:
            self._orphan_alerted.discard(strategy_id)

    # ------------------------------------------------------------------
    # Internal sweep
    # ------------------------------------------------------------------

    def _sweep_loop(self) -> None:
        """Background thread: sweep positions every ``sweep_interval_s``."""
        while self._running:
            try:
                self._sweep_once()
            except Exception as exc:  # noqa: BLE001
                self.logger.error("ExitMonitor sweep error: %s", exc, exc_info=True)
            time.sleep(self.sweep_interval_s)

    def _sweep_once(self) -> None:
        """Single sweep pass — called from the background thread."""
        if self.portfolio_manager is None and self._portfolio_manager_provider is not None:
            try:
                portfolio_manager = self._portfolio_manager_provider()
            except Exception as exc:
                self.logger.warning("ExitMonitor: could not resolve PortfolioManager lazily: %s", exc)
                return

            if portfolio_manager is None:
                return

            self.portfolio_manager = portfolio_manager

        try:
            positions: dict[str, Any] = getattr(
                self.portfolio_manager, "portfolio_positions", {}
            )
        except Exception as exc:
            self.logger.warning("Could not read portfolio_positions: %s", exc)
            return

        if not positions:
            return

        for symbol, raw_pos in list(positions.items()):
            try:
                self._check_position(symbol, raw_pos)
            except Exception as exc:
                self.logger.warning(
                    "ExitMonitor: error processing position %s: %s", symbol, exc
                )

    def _check_position(self, symbol: str, raw_pos: Any) -> None:
        """Evaluate a single position for exit conditions."""
        strategy_id: str = (
            getattr(raw_pos, "strategy_id", None)
            or (raw_pos.get("strategy_id") if isinstance(raw_pos, dict) else None)
            or ""
        )

        view = _PositionView(
            symbol=symbol,
            strategy_id=strategy_id,
            quantity=float(
                getattr(raw_pos, "quantity", None)
                or (raw_pos.get("quantity", 0) if isinstance(raw_pos, dict) else 0)
            ),
            cost_basis=float(
                getattr(raw_pos, "cost_basis", None)
                or (raw_pos.get("cost_basis", 0.0) if isinstance(raw_pos, dict) else 0.0)
            ),
            current_price=float(
                getattr(raw_pos, "current_price", None)
                or (raw_pos.get("current_price", 0.0) if isinstance(raw_pos, dict) else 0.0)
            ),
            unrealized_pnl=float(
                getattr(raw_pos, "unrealized_pnl", None)
                or (raw_pos.get("unrealized_pnl", 0.0) if isinstance(raw_pos, dict) else 0.0)
            ),
            raw=raw_pos if isinstance(raw_pos, dict) else {},
        )

        strategy = self.strategy_map.get(strategy_id) if strategy_id else None

        if strategy is None:
            self._handle_orphan(symbol, strategy_id, view)
            return

        # Reset orphan alert if the strategy reappeared
        # C5 (v18): acquire lock before mutating the shared set.
        with self._orphan_lock:
            self._orphan_alerted.discard(strategy_id)

        decision: ExitDecision | None = None
        try:
            raw_decision = strategy.check_exit(view)
            if raw_decision is not None:
                decision = ExitDecision(raw_decision) if not isinstance(raw_decision, ExitDecision) else raw_decision  # noqa: E501
        except AttributeError:
            # Strategy doesn't implement check_exit — skip silently
            return
        except Exception as exc:
            self.logger.warning(
                "strategy.check_exit(%s) raised: %s", symbol, exc
            )
            return

        if decision == ExitDecision.CLOSE:
            self._emit_close_signal(view, strategy_id)

    def _handle_orphan(self, symbol: str, strategy_id: str, view: _PositionView) -> None:
        """Alert once per strategy_id when a position has no owning strategy."""
        alert_key = strategy_id or symbol
        # C5 (v18): acquire lock for both the membership test and the add so
        # no two threads can race through the guard simultaneously.
        with self._orphan_lock:
            if alert_key in self._orphan_alerted:
                return
            self._orphan_alerted.add(alert_key)
        self.logger.warning(
            "ExitMonitor: ORPHAN position %s (strategy_id=%r, qty=%.0f)",
            symbol, strategy_id, view.quantity,
        )
        self._inc_counter("spyder_orphans_detected_total")
        self.em.emit(
            event_type=EventType.RISK_VIOLATION,
            data={
                "type": "ORPHAN_POSITION",
                "symbol": symbol,
                "strategy_id": strategy_id,
                "quantity": view.quantity,
                "unrealized_pnl": view.unrealized_pnl,
                "message": (
                    f"Position {symbol} has no registered owning strategy "
                    f"(strategy_id={strategy_id!r})"
                ),
            },
            source="ExitMonitor",
        )

    def _emit_close_signal(self, view: _PositionView, strategy_id: str) -> None:
        """Emit a STRATEGY_SIGNAL to close a position."""
        signal_id = f"exit-{view.symbol}-{uuid.uuid4().hex[:8]}"
        self.logger.info(
            "ExitMonitor: closing position %s (strategy=%s, pnl=%.2f)",
            view.symbol, strategy_id, view.unrealized_pnl,
        )
        # Resolve close direction from position sign so downstream consumers
        # (R04 _broker_submit) do not default to SELL unconditionally.
        # Long position (qty > 0) → sell-to-close; Short (qty < 0) → buy-to-close.
        close_side = "sell" if (view.quantity or 0) > 0 else "buy"
        self.em.emit(
            event_type=EventType.STRATEGY_SIGNAL,
            data={
                "signal_id": signal_id,
                "action": "close",
                "side": close_side,
                "symbol": view.symbol,
                "strategy_id": strategy_id,
                "quantity": abs(view.quantity),
                "reason": "exit_monitor",
                "unrealized_pnl": view.unrealized_pnl,
            },
            source="ExitMonitor",
        )
        self._inc_counter("spyder_exits_emitted_total")

    def _inc_counter(self, name: str) -> None:
        if self._prom:
            try:
                self._prom.increment(name)
            except Exception:
                pass


# ==============================================================================
# FACTORY
# ==============================================================================

def create_exit_monitor(
    portfolio_manager: Any,
    strategy_map: dict[str, Any] | None = None,
    event_manager: Any = None,
    portfolio_manager_provider: Callable[[], Any | None] | None = None,
    sweep_interval_s: float = _DEFAULT_SWEEP_INTERVAL_S,
) -> ExitMonitor:
    """Factory function for :class:`ExitMonitor`.

    Args:
        portfolio_manager: P01 PortfolioManager or compatible object.
        strategy_map: Optional pre-populated strategy map.
        event_manager: Shared EventManager (uses singleton if omitted).
        portfolio_manager_provider: Optional callable used to lazily resolve a
            PortfolioManager after startup.
        sweep_interval_s: Seconds between position sweeps.

    Returns:
        A new :class:`ExitMonitor` instance (not yet started).
    """
    monitor = ExitMonitor(
        portfolio_manager=portfolio_manager,
        strategy_map=strategy_map,
        event_manager=event_manager,
        portfolio_manager_provider=portfolio_manager_provider,
        sweep_interval_s=sweep_interval_s,
    )
    SpyderLogger.get_logger(__name__).info(
        "ExitMonitor created (interval=%.1fs)", sweep_interval_s
    )
    return monitor
