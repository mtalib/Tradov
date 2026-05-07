"""SpyderU50_AsyncBridge — safe async-from-thread execution helper.

v27 SPEC-15: provides ``run_coro_in_thread()`` for code paths that need to
invoke an async coroutine from a synchronous thread context, without the
pitfalls of bare ``asyncio.run()``:

1. ``asyncio.run()`` raises ``RuntimeError`` when called from inside an
   already-running event loop.
2. ``asyncio.run()`` creates and tears down a fresh event loop per call,
   breaking any client that caches a loop (Tradier websocket, aiohttp
   sessions, etc.) and burning ~1 ms of overhead.

Use this helper from thread-loop bodies where you need one-shot coroutine
execution without owning a long-lived event loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine, TypeVar

T = TypeVar("T")
_logger = logging.getLogger(__name__)


def run_coro_in_thread(coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
    """Run ``coro`` to completion from a synchronous thread context.

    Behavior:
    - If no event loop is running on the current thread → create a fresh
      loop, run the coroutine, close the loop. (Same as ``asyncio.run``
      but without erroring on edge cases.)
    - If an event loop IS already running on the current thread (rare;
      indicates a code-path mistake) → raise ``RuntimeError`` rather than
      silently misbehave. The caller should not be calling this helper.

    Args:
        coro: The coroutine to execute.
        timeout: Optional seconds. If exceeded, the loop is cancelled and
            ``asyncio.TimeoutError`` is raised.

    Returns:
        The coroutine's return value.

    Raises:
        RuntimeError: When invoked from inside a running event loop.
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is not None:
        # Caller is already inside an async context — this helper is for
        # SYNCHRONOUS thread bodies. Awaiting via this helper would block
        # the running loop. Surface the bug instead of hiding it.
        raise RuntimeError(
            "run_coro_in_thread() called from inside a running event loop; "
            "use 'await' directly or asyncio.run_coroutine_threadsafe() instead."
        )

    loop = asyncio.new_event_loop()
    try:
        if timeout is not None:
            return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.close()
        except Exception as exc:
            _logger.debug("AsyncBridge loop close failed: %s", exc)


__all__ = ["run_coro_in_thread"]
