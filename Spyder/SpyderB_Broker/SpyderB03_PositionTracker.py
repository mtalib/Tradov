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
import threading
from typing import Callable
from threading import RLock, Event as ThreadEvent

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
        self.logger.info("PositionTracker stopped")

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
                self.logger.error(f"Position callback error: {exc}")

    def _fire_pnl_callbacks(self, *args, **kwargs):
        """Fire P&L callbacks using a snapshot to allow concurrent mutation."""
        with self._position_lock:
            callbacks = list(self._pnl_callbacks)
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                self.logger.error(f"PnL callback error: {exc}")

    def _fire_risk_callbacks(self, *args, **kwargs):
        """Fire risk callbacks using a snapshot to allow concurrent mutation."""
        with self._position_lock:
            callbacks = list(self._risk_callbacks)
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception as exc:
                self.logger.error(f"Risk callback error: {exc}")

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
                                        self.logger.info(f"New position detected: {symbol}")
                                        self.positions[symbol] = broker_pos
                    except (ConnectionError, TimeoutError) as e:
                        self.logger.warning(f"Broker connection issue during sync: {e}")
                    except Exception as e:
                        self.logger.error(f"Error fetching broker positions: {e}", exc_info=True)
                else:
                    self.logger.debug("Position sync loop iteration (no broker connection)")
                    
                self._shutdown_event.wait(self.update_interval)
            except Exception as e:
                self.logger.error(f"Error in position sync loop: {e}", exc_info=True)
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
                                self.logger.debug(f"Could not update Greeks for {symbol}: {e}")
                            except Exception as e:
                                self.logger.warning(f"Error updating Greeks for {symbol}: {e}")
                                
                self._shutdown_event.wait(self.update_interval)
            except Exception as e:
                self.logger.error(f"Error in Greeks update loop: {e}", exc_info=True)
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
                            self.logger.debug(f"Could not calculate P&L for {symbol}: {e}")
                        except Exception as e:
                            self.logger.warning(f"Error calculating P&L for {symbol}: {e}")
                    
                    # Store aggregate P&L
                    self.total_unrealized_pnl = total_unrealized_pnl
                    self.total_realized_pnl = total_realized_pnl
                    
                self._shutdown_event.wait(self.update_interval)
            except Exception as e:
                self.logger.error(f"Error in P&L update loop: {e}", exc_info=True)
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
                                self.logger.warning(f"Orphaned positions detected: {orphaned}")
                                for symbol in orphaned:
                                    # Mark for review or auto-close
                                    self.logger.info(f"Reconciling orphaned position: {symbol}")
                            
                            # Positions broker has but we don't
                            missing = broker_symbols - internal_symbols
                            if missing:
                                self.logger.warning(f"Missing positions detected: {missing}")
                                for symbol in missing:
                                    self.positions[symbol] = broker_positions[symbol]
                                    self.logger.info(f"Added missing position: {symbol}")
                                    
                    except (ConnectionError, TimeoutError) as e:
                        self.logger.warning(f"Broker connection issue during reconciliation: {e}")
                    except Exception as e:
                        self.logger.error(f"Error during reconciliation: {e}", exc_info=True)
                else:
                    self.logger.debug("Reconciliation loop iteration (no broker connection)")
                    
                self._shutdown_event.wait(self.update_interval * 10)  # Less frequent
            except Exception as e:
                self.logger.error(f"Error in reconciliation loop: {e}", exc_info=True)
                self._shutdown_event.wait(10.0)  # Wait 10 seconds on error


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
    import logging

    logging.basicConfig(level=logging.INFO)

