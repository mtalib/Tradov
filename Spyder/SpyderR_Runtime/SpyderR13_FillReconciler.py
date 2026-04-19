#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderR_Runtime
Module: SpyderR13_FillReconciler.py
Purpose: Background fill-reconciliation worker — polls Tradier for ground-truth
         order status and publishes lifecycle events to the shared EventManager.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-18 Time: 11:00:00

Module Description:
    Addresses C-11 (no broker-fill reconciliation thread).

    Once an order is *accepted* by Tradier (i.e. the REST response includes an
    order-id), R04 registers it here via ``track()``.  A daemon thread polls
    ``broker.get_order()`` at a configurable cadence and emits the appropriate
    EventType once a terminal state is observed:

        ORDER_FILLED         — Tradier status "filled"
        ORDER_PARTIALLY_FILLED — "partially_filled" (kept alive until terminal)
        ORDER_CANCELLED      — "canceled" / "cancelled"
        ORDER_EXPIRED        — "expired"
        ORDER_REJECTED       — "rejected"

    Poll cadence (configurable):
        - Market / Stop orders  : every 2 s  (default)
        - Limit / Stop-limit    : every 5 s  (default)

    Prometheus metrics (soft-imported; silently skipped if unavailable):
        fill_detection_latency_ms  — histogram: ms from registration to fill
        reconciler_poll_total      — counter: total poll attempts
        reconciler_fill_miss_total — counter: poll errors / unexpected statuses
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_POLL_CADENCE_MARKET: float = 1.0   # seconds (P1-5)
DEFAULT_POLL_CADENCE_LIMIT: float = 5.0    # seconds
MAX_CONSECUTIVE_ERRORS: int = 8            # after this, stop tracking the order
MAX_BACKOFF_SECONDS: float = 60.0
ORPHAN_DEAD_LETTER_PATH: Path = Path("logs/orphans.jsonl")


# ==============================================================================
# INTERNAL DATA TYPES
# ==============================================================================

@dataclass
class _TrackedOrder:
    """State for a single order being reconciled."""
    order_id: str          # internal Spyder order ID
    tradier_order_id: str  # broker-assigned ID (always str for dict key)
    order_type: str        # "market", "limit", "stop", "stop_limit"
    cadence: float         # base poll interval in seconds
    registered_at: float = field(default_factory=time.monotonic)
    next_poll_at: float = field(default_factory=time.monotonic)
    consecutive_errors: int = 0


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class FillReconciler:
    """Background service that polls Tradier for order fill status.

    Args:
        broker: Broker interface with ``get_order(tradier_order_id)`` method.
        event_manager: Shared A05 EventManager instance.
        poll_cadence_market: Poll interval (seconds) for market/stop orders.
        poll_cadence_limit: Poll interval (seconds) for limit/stop-limit orders.

    Usage::

        reconciler = FillReconciler(broker=b40_client, event_manager=em)
        reconciler.start()

        # After a Tradier acceptance:
        reconciler.track(order_id="my-001", tradier_order_id="8675309",
                         order_type="limit")

        # On shutdown:
        reconciler.stop()
    """

    def __init__(
        self,
        broker: Any,
        event_manager: Any,
        poll_cadence_market: float = DEFAULT_POLL_CADENCE_MARKET,
        poll_cadence_limit: float = DEFAULT_POLL_CADENCE_LIMIT,
    ) -> None:
        self.logger = SpyderLogger.get_logger(__name__)
        self._broker = broker
        self._em = event_manager
        self._poll_cadence_market = poll_cadence_market
        self._poll_cadence_limit = poll_cadence_limit

        self._tracked: dict[str, _TrackedOrder] = {}  # keyed by tradier_order_id
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Prometheus metrics — soft-import; silently disabled if unavailable.
        self._prom: Any = None
        try:
            from Spyder.SpyderB_Broker.SpyderB15_PrometheusMetrics import PrometheusMetrics
            self._prom = PrometheusMetrics.get_instance()
        except Exception:
            pass

        self.logger.info(
            "FillReconciler created (market=%.1fs limit=%.1fs)",
            poll_cadence_market,
            poll_cadence_limit,
        )

    # --------------------------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------------------------

    def track(
        self,
        order_id: str,
        tradier_order_id: "str | int",
        order_type: str = "market",
    ) -> None:
        """Register an accepted order for fill reconciliation.

        Args:
            order_id: Internal Spyder order ID.
            tradier_order_id: Broker-assigned Tradier order ID (int or str).
            order_type: One of "market", "stop", "limit", "stop_limit".
        """
        toid = str(tradier_order_id)
        is_limit = order_type.lower() in ("limit", "stop_limit")
        cadence = self._poll_cadence_limit if is_limit else self._poll_cadence_market
        now = time.monotonic()

        entry = _TrackedOrder(
            order_id=order_id,
            tradier_order_id=toid,
            order_type=order_type,
            cadence=cadence,
            registered_at=now,
            next_poll_at=now + cadence,
        )
        with self._lock:
            self._tracked[toid] = entry

        self._inc_counter("spyder_orders_submitted_total")
        self.logger.info(
            "Reconciler tracking: order_id=%s tradier_id=%s type=%s cadence=%.1fs",
            order_id,
            toid,
            order_type,
            cadence,
        )

    def start(self) -> bool:
        """Start the background polling thread.

        Returns:
            True if the thread started (or was already running).
        """
        if self._thread is not None and self._thread.is_alive():
            self.logger.debug("FillReconciler already running")
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="FillReconciler",
        )
        self._thread.start()
        self.logger.info("FillReconciler started")
        return True

    def stop(self) -> None:
        """Signal the thread to exit and wait up to 5 s for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        self.logger.info("FillReconciler stopped (%d orders still tracked)",
                         self.tracked_count)

    @property
    def tracked_count(self) -> int:
        """Number of orders currently being polled."""
        with self._lock:
            return len(self._tracked)

    # --------------------------------------------------------------------------
    # PRIVATE — POLL LOOP
    # --------------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Main loop: runs in daemon thread until ``stop()`` is called."""
        while not self._stop_event.is_set():
            now = time.monotonic()
            due: list[_TrackedOrder] = []
            with self._lock:
                for entry in list(self._tracked.values()):
                    if now >= entry.next_poll_at:
                        due.append(entry)

            for entry in due:
                self._poll_one(entry)

            # Sleep in small bursts so stop_event is noticed promptly.
            # Granularity of 50 ms is fine for 2–5 s real cadences and
            # still tight enough for test cadences of 0.1 s.
            self._stop_event.wait(timeout=0.05)

    def _poll_one(self, entry: _TrackedOrder) -> None:
        """Fetch order status from Tradier and act on it."""
        self._inc_counter("reconciler_poll_total")

        try:
            response = self._broker.get_order(entry.tradier_order_id)
            # Tradier wraps the order under "order" key; fall back to bare dict.
            order_data: dict[str, Any] = (response or {}).get("order", response or {})
            raw_status: str = (order_data.get("status") or "").lower().replace(" ", "_")
        except Exception as exc:
            self.logger.warning(
                "Reconciler poll error tradier_id=%s: %s",
                entry.tradier_order_id,
                exc,
            )
            self._inc_counter("reconciler_fill_miss_total")
            entry.consecutive_errors += 1
            if entry.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                self._emit_orphaned(entry, last_error=str(exc))
                self._drop(entry.tradier_order_id)
                return
            backoff = min(
                entry.cadence * (2 ** entry.consecutive_errors),
                MAX_BACKOFF_SECONDS,
            )
            self._reschedule(entry, next_in=backoff)
            return

        entry.consecutive_errors = 0

        # ------------------------------------------------------------------
        # Terminal states
        # ------------------------------------------------------------------
        if raw_status == "filled":
            latency_ms = (time.monotonic() - entry.registered_at) * 1000.0
            self._observe_latency(latency_ms)
            self._inc_counter("spyder_fills_detected_total")
            self._em.emit(
                EventType.ORDER_FILLED,
                {
                    "order_id": entry.order_id,
                    "tradier_order_id": entry.tradier_order_id,
                    "fill_price": order_data.get("avg_fill_price"),
                    "quantity": order_data.get("quantity"),
                    "timestamp": order_data.get("transaction_date"),
                    "raw": order_data,
                },
                source="FillReconciler",
            )
            self._drop(entry.tradier_order_id)

        elif raw_status in ("canceled", "cancelled"):
            self._em.emit(
                EventType.ORDER_CANCELLED,
                {
                    "order_id": entry.order_id,
                    "tradier_order_id": entry.tradier_order_id,
                    "raw": order_data,
                },
                source="FillReconciler",
            )
            self._drop(entry.tradier_order_id)

        elif raw_status == "expired":
            self._em.emit(
                EventType.ORDER_EXPIRED,
                {
                    "order_id": entry.order_id,
                    "tradier_order_id": entry.tradier_order_id,
                    "raw": order_data,
                },
                source="FillReconciler",
            )
            self._drop(entry.tradier_order_id)

        elif raw_status == "rejected":
            self._em.emit(
                EventType.ORDER_REJECTED,
                {
                    "order_id": entry.order_id,
                    "tradier_order_id": entry.tradier_order_id,
                    "raw": order_data,
                },
                source="FillReconciler",
            )
            self._drop(entry.tradier_order_id)

        # ------------------------------------------------------------------
        # Non-terminal states
        # ------------------------------------------------------------------
        elif raw_status == "partially_filled":
            self._em.emit(
                EventType.ORDER_PARTIALLY_FILLED,
                {
                    "order_id": entry.order_id,
                    "tradier_order_id": entry.tradier_order_id,
                    "exec_quantity": order_data.get("exec_quantity"),
                    "remaining_quantity": (
                        (order_data.get("quantity") or 0)
                        - (order_data.get("exec_quantity") or 0)
                    ),
                    "raw": order_data,
                },
                source="FillReconciler",
            )
            # Keep tracking — order not yet terminal.
            self._reschedule(entry)

        else:
            # pending / open / unknown transient status — poll again later.
            self._reschedule(entry)

    # --------------------------------------------------------------------------
    # PRIVATE — HELPERS
    # --------------------------------------------------------------------------

    def _reschedule(
        self, entry: _TrackedOrder, next_in: Optional[float] = None
    ) -> None:
        """Update the next-poll time for a still-live order."""
        with self._lock:
            if entry.tradier_order_id in self._tracked:
                self._tracked[entry.tradier_order_id].next_poll_at = (
                    time.monotonic() + (next_in if next_in is not None else entry.cadence)
                )

    def _drop(self, tradier_order_id: str) -> None:
        """Remove a terminal order from the tracking dict."""
        with self._lock:
            self._tracked.pop(tradier_order_id, None)

    def _emit_orphaned(self, entry: _TrackedOrder, last_error: str) -> None:
        """Emit ORDER_ORPHANED and append to dead-letter log exactly once."""
        payload = {
            "order_id": entry.order_id,
            "broker_order_id": entry.tradier_order_id,
            "last_error": last_error,
            "consecutive_errors": entry.consecutive_errors,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.logger.error(
            "Reconciler: orphaning order_id=%s tradier_id=%s after %d errors",
            entry.order_id,
            entry.tradier_order_id,
            entry.consecutive_errors,
        )
        try:
            self._em.emit(EventType.ORDER_ORPHANED, payload, source="FillReconciler")
        except Exception as exc:
            self.logger.error("Failed to emit ORDER_ORPHANED: %s", exc)
        self._append_orphan_dead_letter(payload)

    def _append_orphan_dead_letter(self, payload: dict[str, Any]) -> None:
        """Append orphaned order payload to logs/orphans.jsonl."""
        try:
            ORPHAN_DEAD_LETTER_PATH.parent.mkdir(parents=True, exist_ok=True)
            with ORPHAN_DEAD_LETTER_PATH.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, sort_keys=True) + "\n")
        except Exception as exc:
            self.logger.error("Failed writing orphan dead-letter file: %s", exc)

    def _inc_counter(self, name: str) -> None:
        if self._prom:
            try:
                self._prom.increment(name)
            except Exception:
                pass

    def _observe_latency(self, latency_ms: float) -> None:
        if self._prom:
            try:
                self._prom.observe("fill_detection_latency_ms", latency_ms)
            except Exception:
                pass
