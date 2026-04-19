#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB03_PositionTracker.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock, Event as ThreadEvent

_DEFAULT_STATE_PATH = Path.home() / ".spyder" / "position_tracker_state.json"

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================

class PositionTracker:
    """
    Real-time position tracking with P&L and Greeks monitoring.

    This class provides comprehensive real-time position tracking with live P&L
    calculation, Greeks monitoring, and portfolio analytics. It maintains accurate
    position records synchronized with the broker API, handles partial fills,
    tracks cost basis, and provides real-time risk metrics calculation including
    all commissions and fees.
    """

    def __init__(self, spyder_client, event_manager=None, update_interval=1.0):
        """Initialize the PositionTracker."""
        self.spyder_client = spyder_client
        self.event_manager = event_manager
        self.update_interval = update_interval
        self.greeks_calculator = None  # Optional Greeks calculator

        # Logging
        from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

        self.logger = SpyderLogger.get_logger(__name__)

        # Thread management
        self._running = False
        self._sync_thread = None
        self._greeks_thread = None
        self._pnl_thread = None
        self._reconciliation_thread = None
        self._position_lock = RLock()
        self._shutdown_event = ThreadEvent()

        # Callbacks
        self._position_callbacks = []
        self._pnl_callbacks = []
        self._risk_callbacks = []
        # Called with (symbol: str) when a position exists internally but not on the broker.
        # Set via set_orphan_close_callback().  When None the tracker attempts a direct
        # market close order via self.spyder_client.
        self._orphan_close_callback: Callable | None = None

        # Backward-compatible aliases used throughout this module.
        self.lock = self._position_lock
        self.positions: dict[str, object] = {}
        self._state_path: Path = _DEFAULT_STATE_PATH

    # ==========================================================================
    # THREAD MANAGEMENT
    # ==========================================================================

    def _start_background_threads(self):
        """Start all background threads."""
        # Position sync thread
        self._sync_thread = threading.Thread(
            target=self._sync_positions_loop, name="PositionSync", daemon=True
        )
        self._sync_thread.start()

        # Greeks update thread
        if self.greeks_calculator:
            self._greeks_thread = threading.Thread(
                target=self._greeks_update_loop, name="GreeksUpdate", daemon=True
            )
            self._greeks_thread.start()

        # P&L update thread
        self._pnl_thread = threading.Thread(
            target=self._pnl_update_loop, name="PnLUpdate", daemon=True
        )
        self._pnl_thread.start()

        # Reconciliation thread
        self._reconciliation_thread = threading.Thread(
            target=self._reconciliation_loop, name="PositionReconciliation", daemon=True
        )
        self._reconciliation_thread.start()

        self.logger.info("Background threads started")

    def _stop_background_threads(self):
        """Stop all background threads."""
        self._shutdown_event.set()

        threads = [
            self._sync_thread,
            self._greeks_thread,
            self._pnl_thread,
            self._reconciliation_thread,
        ]

        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=5)

        self.logger.info("Background threads stopped")

    def start(self) -> None:
        """Start all background monitoring threads."""
        if self._running:
            self.logger.warning("PositionTracker already running")
            return
        self.load_state(self._state_path)
        self.reconcile_with_broker(tolerance=0.01)
        self._running = True
        self._shutdown_event.clear()
        self._start_background_threads()
        self.logger.info("PositionTracker started")

    def stop(self) -> None:
        """Stop all background monitoring threads gracefully."""
        if not self._running:
            return
        self._running = False
        self._stop_background_threads()
        self.save_state(self._state_path)
        self.logger.info("PositionTracker stopped")

    def get_positions(self) -> dict[str, dict[str, object]]:
        """Return a normalized copy of local positions."""
        with self._position_lock:
            out: dict[str, dict[str, object]] = {}
            for symbol, pos in self.positions.items():
                if isinstance(pos, dict):
                    out[symbol] = dict(pos)
                else:
                    out[symbol] = {
                        "symbol": symbol,
                        "quantity": getattr(pos, "quantity", 0),
                        "average_fill_price": getattr(pos, "average_fill_price", 0.0),
                    }
            return out

    def save_state(self, path: str | Path | None = None) -> bool:
        """Persist local positions to JSON for restart continuity."""
        target = Path(path) if path is not None else self._state_path
        try:
            snapshot = {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "positions": self.get_positions(),
            }
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
            return True
        except Exception as exc:
            self.logger.error("save_state failed for %s: %s", target, exc)
            return False

    def load_state(self, path: str | Path | None = None) -> bool:
        """Load persisted positions from JSON if available."""
        target = Path(path) if path is not None else self._state_path
        if not target.exists():
            return False
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
            restored = payload.get("positions") or {}
            if not isinstance(restored, dict):
                self.logger.warning("load_state ignored invalid payload at %s", target)
                return False
            with self._position_lock:
                self.positions = {
                    str(sym): {
                        "symbol": str(sym),
                        "quantity": int((pos or {}).get("quantity", 0)),
                        "average_fill_price": float((pos or {}).get("average_fill_price", 0.0)),
                    }
                    for sym, pos in restored.items()
                }
            self.logger.info("Loaded %d persisted positions from %s", len(self.positions), target)
            return True
        except Exception as exc:
            self.logger.error("load_state failed for %s: %s", target, exc)
            return False

    def _normalize_broker_positions(self, broker_positions: object) -> dict[str, float]:
        """Normalize broker get_positions() payload to symbol->quantity mapping."""
        normalized: dict[str, float] = {}
        if isinstance(broker_positions, dict):
            # Tradier-like shape: {"positions": {"position": [...]}}
            if "positions" in broker_positions:
                raw = (broker_positions.get("positions") or {}).get("position", [])
                if isinstance(raw, dict):
                    raw = [raw]
                if isinstance(raw, list):
                    for item in raw:
                        try:
                            symbol = str(item.get("symbol", ""))
                            if symbol:
                                normalized[symbol] = float(item.get("quantity", 0) or 0)
                        except Exception:
                            continue
                return normalized
            # Already symbol->position dict
            for symbol, pos in broker_positions.items():
                if isinstance(pos, dict):
                    qty = float(pos.get("quantity", 0) or 0)
                else:
                    qty = float(getattr(pos, "quantity", 0) or 0)
                normalized[str(symbol)] = qty
            return normalized
        if isinstance(broker_positions, list):
            for item in broker_positions:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol", ""))
                if symbol:
                    normalized[symbol] = float(item.get("quantity", 0) or 0)
        return normalized

    def reconcile_with_broker(self, tolerance: float = 0.01) -> bool:
        """Reconcile local positions against broker positions and warn on drift."""
        client = getattr(self, "spyder_client", None)
        if client is None or not hasattr(client, "get_positions"):
            self.logger.debug("reconcile_with_broker skipped: broker client unavailable")
            return False
        try:
            broker_positions = self._normalize_broker_positions(client.get_positions())
        except Exception as exc:
            self.logger.warning("reconcile_with_broker broker fetch failed: %s", exc)
            return False

        local_positions = self.get_positions()
        symbols = set(local_positions.keys()) | set(broker_positions.keys())
        divergence = False
        for symbol in sorted(symbols):
            local_qty = float((local_positions.get(symbol) or {}).get("quantity", 0) or 0)
            broker_qty = float(broker_positions.get(symbol, 0) or 0)
            if abs(local_qty - broker_qty) > tolerance:
                divergence = True
                self.logger.warning(
                    "Position divergence for %s: local=%s broker=%s (tol=%s)",
                    symbol,
                    local_qty,
                    broker_qty,
                    tolerance,
                )
        if not divergence:
            self.logger.info("PositionTracker reconciliation OK (symbols=%d)", len(symbols))
        return not divergence

    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================

    def add_position_callback(self, callback: Callable):
        """Add position update callback."""
        with self._position_lock:
            if callback not in self._position_callbacks:
                self._position_callbacks.append(callback)

    def add_pnl_callback(self, callback: Callable):
        """Add P&L update callback."""
        with self._position_lock:
            if callback not in self._pnl_callbacks:
                self._pnl_callbacks.append(callback)

    def add_risk_callback(self, callback: Callable):
        """Add risk alert callback."""
        with self._position_lock:
            if callback not in self._risk_callbacks:
                self._risk_callbacks.append(callback)

    def remove_position_callback(self, callback: Callable):
        """Remove position callback."""
        with self._position_lock:
            if callback in self._position_callbacks:
                self._position_callbacks.remove(callback)

    def remove_pnl_callback(self, callback: Callable):
        """Remove P&L callback."""
        with self._position_lock:
            if callback in self._pnl_callbacks:
                self._pnl_callbacks.remove(callback)

    def remove_risk_callback(self, callback: Callable):
        """Remove risk callback."""
        with self._position_lock:
            if callback in self._risk_callbacks:
                self._risk_callbacks.remove(callback)

    def _fire_position_callbacks(self, *args, **kwargs):
        """Fire position callbacks using a snapshot to allow concurrent mutation."""
        with self._position_lock:
            callbacks = list(self._position_callbacks)
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                self.logger.error("Position callback error: %s", exc)

    def _fire_pnl_callbacks(self, *args, **kwargs):
        """Fire P&L callbacks using a snapshot to allow concurrent mutation."""
        with self._position_lock:
            callbacks = list(self._pnl_callbacks)
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                self.logger.error("PnL callback error: %s", exc)

    def _fire_risk_callbacks(self, *args, **kwargs):
        """Fire risk callbacks using a snapshot to allow concurrent mutation."""
        with self._position_lock:
            callbacks = list(self._risk_callbacks)
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                self.logger.error("Risk callback error: %s", exc)

    def set_orphan_close_callback(self, callback: Callable | None) -> None:
        """
        Register a callback invoked whenever an orphaned position is detected.

        The callback receives the symbol string as its only argument.  The
        caller is responsible for submitting a closing order.  When no callback
        is registered the tracker falls back to a direct market-close attempt
        via self.spyder_client.

        Args:
            callback: callable(symbol: str) or None to clear.
        """
        with self._position_lock:
            self._orphan_close_callback = callback

    # ==========================================================================
    # FILL RECORDING (S-06)
    # ==========================================================================

    def record_fill(self, fill: dict) -> None:
        """
        Record a confirmed broker fill and publish POSITION_UPDATED.

        Called by R04._on_reconciler_fill every time FillReconciler confirms
        an ORDER_FILLED event.  Adjusts the in-memory position for the symbol,
        then emits POSITION_UPDATED on the shared EventManager so that E01
        RiskManager (and any dashboard subscriber) can react.

        Args:
            fill: Fill data dict with keys: symbol, side, quantity,
                  fill_price, order_id.  Missing keys are silently ignored.
        """
        symbol   = fill.get("symbol") or fill.get("instrument")
        side     = (fill.get("side") or "buy").lower()
        qty      = int(fill.get("quantity") or fill.get("exec_quantity") or 0)
        price    = float(fill.get("fill_price") or fill.get("avg_fill_price") or 0.0)
        order_id = fill.get("order_id", "")

        if not symbol or qty == 0:
            self.logger.warning("record_fill: incomplete fill data — %s", fill)
            return

        signed_qty = qty if side in ("buy", "long") else -qty

        with self._position_lock:
            if symbol in self.positions:
                existing = self.positions[symbol]
                if isinstance(existing, dict):
                    old_qty = existing.get("quantity", 0)
                else:
                    old_qty = getattr(existing, "quantity", 0)
                new_qty  = old_qty + signed_qty
                if new_qty == 0:
                    del self.positions[symbol]
                else:
                    try:
                        existing.quantity = new_qty
                    except (AttributeError, TypeError):
                        self.positions[symbol]["quantity"] = new_qty
            else:
                # New position entry
                self.positions[symbol] = {
                    "symbol":            symbol,
                    "quantity":          signed_qty,
                    "average_fill_price": price,
                }

            snapshot = dict(self.positions.get(symbol) or {"symbol": symbol, "quantity": 0})

        # Publish POSITION_UPDATED so E01 and dashboard can react.
        if self.event_manager is not None:
            try:
                from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
                self.event_manager.emit(
                    EventType.POSITION_UPDATED,
                    {
                        "symbol":   symbol,
                        "quantity": snapshot.get("quantity", 0),
                        "fill_price": price,
                        "order_id": order_id,
                        "position": snapshot,
                    },
                    source="PositionTracker",
                )
            except Exception as exc:
                self.logger.error("POSITION_UPDATED emit error: %s", exc)

        self.logger.info(
            "record_fill: %s qty=%+d @%.4f → net=%s",
            symbol, signed_qty, price, snapshot.get("quantity", 0),
        )
        self.save_state(self._state_path)

    # ==========================================================================
    # BACKGROUND LOOP METHODS
    # ==========================================================================


    def _sync_positions_loop(self):
        """Background loop for syncing positions with broker."""
        while not self._shutdown_event.is_set():
            try:
                # Sync positions with broker if broker interface is available
                if hasattr(self, 'broker_interface') and self.broker_interface:
                    try:
                        broker_positions = self.broker_interface.get_positions()
                        if broker_positions:
                            with self.lock:
                                # Update internal position tracking
                                for symbol, broker_pos in broker_positions.items():
                                    if symbol in self.positions:
                                        self.positions[symbol].update_from_broker(broker_pos)
                                    else:
                                        self.logger.info("New position detected: %s", symbol)
                                        self.positions[symbol] = broker_pos
                    except (ConnectionError, TimeoutError) as e:
                        self.logger.warning("Broker connection issue during sync: %s", e)
                    except Exception as e:
                        self.logger.error("Error fetching broker positions: %s", e, exc_info=True)
                else:
                    self.logger.debug("Position sync loop iteration (no broker connection)")

                self._shutdown_event.wait(self.update_interval)
            except Exception as e:
                self.logger.error("Error in position sync loop: %s", e, exc_info=True)
                self._shutdown_event.wait(5.0)  # Wait 5 seconds on error

    def _greeks_update_loop(self):
        """Background loop for updating Greeks."""
        while not self._shutdown_event.is_set():
            try:
                # Update Greeks for all option positions
                with self.lock:
                    for symbol, position in self.positions.items():
                        if hasattr(position, 'is_option') and position.is_option:
                            try:
                                # Calculate Greeks if position has underlying price
                                if hasattr(position, 'update_greeks'):
                                    position.update_greeks()
                            except (ValueError, AttributeError) as e:
                                self.logger.debug("Could not update Greeks for %s: %s", symbol, e)
                            except Exception as e:
                                self.logger.warning("Error updating Greeks for %s: %s", symbol, e)

                self._shutdown_event.wait(self.update_interval)
            except Exception as e:
                self.logger.error("Error in Greeks update loop: %s", e, exc_info=True)
                self._shutdown_event.wait(5.0)  # Wait 5 seconds on error

    def _pnl_update_loop(self):
        """Background loop for updating P&L."""
        while not self._shutdown_event.is_set():
            try:
                # Calculate P&L for all positions based on current market prices
                total_unrealized_pnl = 0.0
                total_realized_pnl = 0.0

                with self.lock:
                    for symbol, position in self.positions.items():
                        try:
                            if hasattr(position, 'calculate_pnl'):
                                unrealized, realized = position.calculate_pnl()
                                total_unrealized_pnl += unrealized
                                total_realized_pnl += realized
                        except (ValueError, AttributeError) as e:
                            self.logger.debug("Could not calculate P&L for %s: %s", symbol, e)
                        except Exception as e:
                            self.logger.warning("Error calculating P&L for %s: %s", symbol, e)

                    # Store aggregate P&L
                    self.total_unrealized_pnl = total_unrealized_pnl
                    self.total_realized_pnl = total_realized_pnl

                self._shutdown_event.wait(self.update_interval)
            except Exception as e:
                self.logger.error("Error in P&L update loop: %s", e, exc_info=True)
                self._shutdown_event.wait(5.0)  # Wait 5 seconds on error

    def _reconciliation_loop(self):
        """Background loop for position reconciliation."""
        while not self._shutdown_event.is_set():
            try:
                # Reconcile internal positions with broker positions
                if hasattr(self, 'broker_interface') and self.broker_interface:
                    try:
                        broker_positions = self.broker_interface.get_positions()

                        with self.lock:
                            # Find discrepancies
                            internal_symbols = set(self.positions.keys())
                            broker_symbols = set(broker_positions.keys()) if broker_positions else set()

                            # Positions we have but broker doesn't
                            orphaned = internal_symbols - broker_symbols
                            if orphaned:
                                self.logger.warning("Orphaned positions detected: %s", orphaned)
                                for symbol in orphaned:
                                    self.logger.warning(
                                        "Initiating auto-close for orphaned position: %s", symbol
                                    )
                                    self._handle_orphaned_position(symbol)

                            # Positions broker has but we don't
                            missing = broker_symbols - internal_symbols
                            if missing:
                                self.logger.warning("Missing positions detected: %s", missing)
                                for symbol in missing:
                                    self.positions[symbol] = broker_positions[symbol]
                                    self.logger.info("Added missing position: %s", symbol)

                    except (ConnectionError, TimeoutError) as e:
                        self.logger.warning("Broker connection issue during reconciliation: %s", e)
                    except Exception as e:
                        self.logger.error("Error during reconciliation: %s", e, exc_info=True)
                else:
                    self.logger.debug("Reconciliation loop iteration (no broker connection)")

                self._shutdown_event.wait(self.update_interval * 10)  # Less frequent
            except Exception as e:
                self.logger.error("Error in reconciliation loop: %s", e, exc_info=True)
                self._shutdown_event.wait(10.0)  # Wait 10 seconds on error

    def _handle_orphaned_position(self, symbol: str) -> None:
        """
        Attempt to close a position that exists locally but not on the broker.

        If an orphan-close callback is registered it is invoked (and the caller
        is responsible for the close order).  Otherwise this method attempts a
        direct market-sell/buy-to-close via self.spyder_client.
        """
        # Prefer registered callback — higher-level code knows the full context
        with self._position_lock:
            cb = self._orphan_close_callback
        if cb is not None:
            try:
                cb(symbol)
            except Exception as exc:
                self.logger.error("Orphan close callback raised for %s: %s", symbol, exc)
            return

        # Fallback: direct market close via the broker client
        client = getattr(self, "spyder_client", None)
        if client is None:
            self.logger.warning(
                "No broker client available — cannot auto-close orphan %s", symbol
            )
            return
        try:
            from Spyder.SpyderB_Broker.SpyderB00_OrderTypes import OrderSide, OrderType
            # Read position quantity from internal state if available (capture both qty
            # and signed qty inside the lock — reading from `pos` outside the lock would
            # race with concurrent updates/removals).
            qty = 0
            pos_qty = 0
            with self._position_lock:
                pos = getattr(self, "positions", {}).get(symbol)
                if pos is not None:
                    pos_qty = getattr(pos, "quantity", 0)
                    qty = abs(pos_qty)
            if qty <= 0:
                self.logger.warning(
                    "Orphan %s has zero/unknown quantity — skipping auto-close", symbol
                )
                return
            side = OrderSide.SELL if pos_qty >= 0 else OrderSide.BUY
            self.logger.warning(
                "Auto-close: submitting %s x%d market order for orphaned position %s",
                side.value, qty, symbol,
            )
            client.place_order(
                symbol=symbol,
                side=side,
                quantity=qty,
                order_type=OrderType.MARKET,
            )
            self.logger.info("Auto-close order submitted for orphaned position %s", symbol)
        except Exception as exc:
            self.logger.error(
                "Failed to auto-close orphaned position %s: %s", symbol, exc
            )
# ==============================================================================
# MODULE FUNCTIONS
# ==============================================================================


def create_position_tracker(
    spyder_client, greeks_calculator=None, event_manager=None
) -> PositionTracker:
    """
    Create PositionTracker instance.

    Args:
        spyder_client: SpyderClient instance
        greeks_calculator: Greeks calculator (optional)
        event_manager: Event manager (optional)

    Returns:
        PositionTracker instance
    """
    tracker = PositionTracker(spyder_client, event_manager)
    if greeks_calculator:
        tracker.greeks_calculator = greeks_calculator
    return tracker


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Example usage
    pass

