#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderE_Risk
Module: SpyderE24_DataFreshnessMonitor.py
Purpose: Watch MARKET_DATA tick timestamps and publish DATA_STALE / DATA_FRESH
         transitions so that E01 RiskManager._data_stale is always up-to-date
         (fixes audit finding H-05).

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-24 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import threading
import time
from typing import Any, Optional  # noqa: F401

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderA_Core.SpyderA05_EventManager import (
    Event,  # noqa: F401
    EventType,
    get_event_manager,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
_DEFAULT_RTH_THRESHOLD_S: float = 3.0    # seconds before DATA_STALE during RTH
_DEFAULT_OOH_THRESHOLD_S: float = 30.0   # seconds before DATA_STALE outside RTH
_POLL_INTERVAL_S: float = 0.5            # how often the monitor wakes up


# ==============================================================================
# MAIN CLASS
# ==============================================================================

class DataFreshnessMonitor:
    """
    Subscribes to ``MARKET_DATA`` events, records per-symbol last-tick time,
    and publishes ``DATA_STALE`` / ``DATA_FRESH`` transitions when ticks for
    any watched symbol are delayed beyond the configured threshold.

    Default thresholds (S-13 spec):
    - 3 s during Regular Trading Hours (RTH)
    - 30 s outside RTH (pre-market / after-hours)

    These can be overridden at construction time for testing.

    Usage::

        monitor = DataFreshnessMonitor(event_manager=em, symbols=["SPY","VIX"])
        monitor.start()
        # … trading session …
        monitor.stop()
    """

    def __init__(
        self,
        event_manager: Any = None,
        symbols: list[str] | None = None,
        rth_threshold_s: float = _DEFAULT_RTH_THRESHOLD_S,
        ooh_threshold_s: float = _DEFAULT_OOH_THRESHOLD_S,
        poll_interval_s: float = _POLL_INTERVAL_S,
        startup_grace_s: float = 0.0,
    ) -> None:
        """
        Initialise the DataFreshnessMonitor.

        Args:
            event_manager: Shared EventManager instance. Falls back to the
                singleton from ``get_event_manager()`` when ``None``.
            symbols: Explicit list of symbols to watch. When empty / ``None``
                all symbols that receive a tick are watched automatically.
            rth_threshold_s: Seconds without a tick before DATA_STALE during RTH.
            ooh_threshold_s: Seconds without a tick before DATA_STALE outside RTH.
            poll_interval_s: How often (in seconds) the background loop checks
                freshness.  Lower = more responsive, higher = less CPU.
            startup_grace_s: Seconds after ``start()`` during which stale
                declarations are suppressed.  Allows the data feed time to
                connect before the first DATA_STALE event can fire.
        """
        self.logger = SpyderLogger.get_logger(__name__)
        self._em = event_manager or get_event_manager()
        self._watched: set[str] = set(symbols) if symbols else set()
        self._rth_threshold_s = rth_threshold_s
        self._ooh_threshold_s = ooh_threshold_s
        self._poll_interval_s = poll_interval_s
        self._startup_grace_s = startup_grace_s
        self._start_monotonic: float = 0.0  # set in start()

        # Per-symbol state
        self._last_tick: dict[str, float] = {}   # symbol → epoch seconds
        self._stale_symbols: set[str] = set()    # currently declared stale

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._handler_ids: list[str] = []
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start the freshness-monitor background thread.

        Returns:
            True on success, False if already running.
        """
        if self._running:
            self.logger.warning("DataFreshnessMonitor already running")
            return True

        self._handler_ids = [
            self._em.subscribe(EventType.MARKET_DATA, self._on_market_data),
            self._em.subscribe(EventType.MARKET_DATA_TICK, self._on_market_data),
        ]

        self._start_monotonic = time.monotonic()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="DataFreshnessMonitor",
            daemon=True,
        )
        self._running = True
        self._thread.start()
        self.logger.info(
            "DataFreshnessMonitor started — RTH=%.1fs OOH=%.1fs grace=%.1fs",
            self._rth_threshold_s,
            self._ooh_threshold_s,
            self._startup_grace_s,
        )
        return True

    def stop(self) -> None:
        """Stop the background monitor thread gracefully."""
        self._stop_event.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        for handler_id in self._handler_ids:
            try:
                self._em.unsubscribe(handler_id)
            except Exception as exc:
                self.logger.warning("Failed to unsubscribe freshness handler %s: %s", handler_id, exc)  # noqa: E501
        self._handler_ids.clear()
        self.logger.info("DataFreshnessMonitor stopped")

    # ------------------------------------------------------------------
    # MARKET_DATA subscriber
    # ------------------------------------------------------------------

    def _on_market_data(self, event: Any) -> None:
        """Record receipt of a market-data tick for a symbol."""
        data = event.data or {}
        symbol: str = data.get("symbol", "")
        if not symbol:
            return

        now = time.monotonic()
        with self._lock:
            self._last_tick[symbol] = now
            if symbol not in self._watched:
                self._watched.add(symbol)

            # If this symbol was declared stale, it has just recovered — publish
            # DATA_FRESH immediately (don't wait for the next poll cycle).
            if symbol in self._stale_symbols:
                self._stale_symbols.discard(symbol)
                self._publish_fresh(symbol)

    # ------------------------------------------------------------------
    # Background poll loop
    # ------------------------------------------------------------------

    def _monitor_loop(self) -> None:
        """Periodically checks each watched symbol against the freshness threshold."""
        while not self._stop_event.wait(timeout=self._poll_interval_s):
            self._check_freshness()

    def _check_freshness(self) -> None:
        """Classify each watched symbol as fresh or stale and emit transitions."""
        # Suppress stale declarations during the startup grace window so the
        # data feed has time to connect before the first DATA_STALE can fire.
        if self._startup_grace_s > 0 and self._start_monotonic > 0:
            if time.monotonic() - self._start_monotonic < self._startup_grace_s:
                return

        threshold = self._current_threshold()
        now = time.monotonic()

        with self._lock:
            watched_snapshot = dict(self._last_tick)
            stale_snapshot = set(self._stale_symbols)
            watched_set = set(self._watched)

        for symbol in watched_set:
            last = watched_snapshot.get(symbol)

            if last is None:
                # Symbol is watched but no tick received yet — skip.
                continue

            age = now - last
            is_stale = age > threshold

            if is_stale and symbol not in stale_snapshot:
                # Transition: fresh → stale
                with self._lock:
                    self._stale_symbols.add(symbol)
                self._publish_stale(symbol, age)

            elif not is_stale and symbol in stale_snapshot:
                # Transition: stale → fresh  (should already be handled
                # by _on_market_data, but guard here too).
                with self._lock:
                    self._stale_symbols.discard(symbol)
                self._publish_fresh(symbol)

    # ------------------------------------------------------------------
    # Event publishers
    # ------------------------------------------------------------------

    def _publish_stale(self, symbol: str, age_seconds: float) -> None:
        self.logger.warning(
            "DATA_STALE: %s — no tick for %.1fs (threshold=%.1fs)",
            symbol, age_seconds, self._current_threshold(),
        )
        self._em.emit(
            EventType.DATA_STALE,
            {"symbol": symbol, "age_seconds": age_seconds},
            source="DataFreshnessMonitor",
        )

    def _publish_fresh(self, symbol: str) -> None:
        self.logger.info("DATA_FRESH: %s — tick received, gate re-evaluating", symbol)
        self._em.emit(
            EventType.DATA_FRESH,
            {"symbol": symbol, "age_seconds": 0.0},
            source="DataFreshnessMonitor",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current_threshold(self) -> float:
        """Return the active staleness threshold based on current market hours."""
        try:
            from Spyder.SpyderU_Utilities.SpyderU03_DateTimeUtils import TradingTimeUtils
            if TradingTimeUtils.is_market_hours():
                return self._rth_threshold_s
        except Exception:
            pass
        return self._ooh_threshold_s

    # ------------------------------------------------------------------
    # Properties (useful for testing / monitoring)
    # ------------------------------------------------------------------

    @property
    def stale_symbols(self) -> frozenset[str]:
        """Read-only snapshot of currently-stale symbols."""
        with self._lock:
            return frozenset(self._stale_symbols)

    @property
    def is_running(self) -> bool:
        """True if the monitor background thread is active."""
        return self._running


# ==============================================================================
# FACTORY
# ==============================================================================

def create_freshness_monitor(
    symbols: list[str] | None = None,
    event_manager: Any = None,
    rth_threshold_s: float = _DEFAULT_RTH_THRESHOLD_S,
    ooh_threshold_s: float = _DEFAULT_OOH_THRESHOLD_S,
    startup_grace_s: float = 0.0,
) -> DataFreshnessMonitor:
    """
    Factory convenience wrapper for ``DataFreshnessMonitor``.

    Args:
        symbols: List of symbols to watch (e.g. ``["SPY", "SPX", "VIX"]``).
        event_manager: Shared EventManager instance.
        rth_threshold_s: RTH staleness threshold in seconds.
        ooh_threshold_s: Out-of-hours staleness threshold in seconds.
        startup_grace_s: Seconds after start() during which DATA_STALE is
            suppressed, giving the data feed time to connect.

    Returns:
        A configured (but not yet started) ``DataFreshnessMonitor``.
    """
    return DataFreshnessMonitor(
        event_manager=event_manager,
        symbols=symbols,
        rth_threshold_s=rth_threshold_s,
        ooh_threshold_s=ooh_threshold_s,
        startup_grace_s=startup_grace_s,
    )
