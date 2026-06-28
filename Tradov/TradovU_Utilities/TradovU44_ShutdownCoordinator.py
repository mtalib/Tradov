#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: Tradov.TradovU_Utilities
Module: TradovU44_ShutdownCoordinator.py
Purpose: Graceful shutdown coordination for daemon threads and background tasks

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Provides a process-wide ShutdownCoordinator that replaces raw daemon=True
    threads with managed threads that stop cleanly when the system exits.

    Usage pattern:
        coordinator = get_shutdown_coordinator()

        # In background worker loops:
        stop_event = coordinator.make_stop_event()
        def _worker():
            while not stop_event.is_set():
                do_work()
                stop_event.wait(timeout=POLL_INTERVAL)

        t = coordinator.register_thread(
            threading.Thread(target=_worker, daemon=True),
            name="my-worker"
        )
        t.start()

        # On application exit:
        coordinator.shutdown(timeout=10.0)
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import atexit
import threading
import weakref
from collections.abc import Callable

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Tradov.TradovU_Utilities.TradovU01_Logger import get_logger

logger = get_logger(__name__)


# ==============================================================================
# SHUTDOWN COORDINATOR
# ==============================================================================

class ShutdownCoordinator:
    """
    Process-wide coordinator for graceful daemon-thread shutdown.

    All background worker loops should poll `stop_event.is_set()` (or call
    `stop_event.wait(timeout=...)`) instead of sleeping unconditionally.
    Calling `shutdown()` sets the global stop event and waits for every
    registered thread to finish (up to `timeout` seconds each).
    """

    def __init__(self) -> None:
        self._global_stop = threading.Event()
        self._lock = threading.Lock()
        # WeakSet so that finished threads are automatically garbage-collected
        self._threads: weakref.WeakSet[threading.Thread] = weakref.WeakSet()
        self._cleanup_callbacks: list[Callable[[], None]] = []
        self._shutdown_called = False
        atexit.register(self.shutdown)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def stop_event(self) -> threading.Event:
        """The global stop event.  Set when shutdown() is called."""
        return self._global_stop

    def make_stop_event(self) -> threading.Event:
        """
        Return the global stop event so worker loops can poll it.

        Use `stop_event.wait(timeout=N)` instead of `time.sleep(N)` — it
        returns immediately when shutdown is requested.
        """
        return self._global_stop

    def register_thread(
        self,
        thread: threading.Thread,
        name: str | None = None,
    ) -> threading.Thread:
        """
        Track a thread so that shutdown() waits for it.

        The thread must already be configured (target, daemon flag, etc.) but
        should NOT have been started yet — caller starts it after registration.

        Returns the same thread object for easy chaining::

            t = coordinator.register_thread(threading.Thread(...), "my-worker")
            t.start()
        """
        if name:
            thread.name = name
        with self._lock:
            self._threads.add(thread)
        return thread

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        """Register a zero-argument callable invoked during shutdown()."""
        with self._lock:
            self._cleanup_callbacks.append(callback)

    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Signal all workers to stop and wait for registered threads to finish.

        Safe to call multiple times; only the first call does real work.
        Automatically registered with atexit so it runs on interpreter exit.

        Args:
            timeout: Seconds to wait for each thread before giving up.
        """
        with self._lock:
            if self._shutdown_called:
                return
            self._shutdown_called = True
            callbacks = list(self._cleanup_callbacks)

        logger.info("ShutdownCoordinator: initiating graceful shutdown")
        self._global_stop.set()

        # Run cleanup callbacks first (flush queues, close connections, etc.)
        for cb in callbacks:
            try:
                cb()
            except Exception:
                logger.exception("ShutdownCoordinator: cleanup callback raised")

        # Wait for all tracked live threads
        with self._lock:
            live_threads = [t for t in self._threads if t.is_alive()]

        for thread in live_threads:
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.warning(
                    f"ShutdownCoordinator: thread '{thread.name}' did not stop "
                    f"within {timeout}s — may be blocked"
                )

        logger.info("ShutdownCoordinator: shutdown complete")

    def is_stopping(self) -> bool:
        """Return True once shutdown() has been called."""
        return self._global_stop.is_set()


# ==============================================================================
# PROCESS-WIDE SINGLETON
# ==============================================================================

_coordinator: ShutdownCoordinator | None = None
_coordinator_lock = threading.Lock()


def get_shutdown_coordinator() -> ShutdownCoordinator:
    """Return the process-wide ShutdownCoordinator (created on first call)."""
    global _coordinator
    if _coordinator is None:
        with _coordinator_lock:
            if _coordinator is None:
                _coordinator = ShutdownCoordinator()
    return _coordinator
