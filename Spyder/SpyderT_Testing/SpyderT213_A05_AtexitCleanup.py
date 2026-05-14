#!/usr/bin/env python3
"""Focused regressions for quiet EventManager atexit cleanup."""

from __future__ import annotations

import queue
import threading
from unittest.mock import MagicMock


def test_event_manager_atexit_cleanup_uses_quiet_stop(monkeypatch) -> None:
    from Spyder.SpyderA_Core import SpyderA05_EventManager as a05

    instance = MagicMock()
    instance.is_running = True
    monkeypatch.setattr(a05, "_event_manager_instance", instance)

    a05._event_manager_atexit_cleanup()

    instance.stop.assert_called_once_with(quiet=True)


def test_event_manager_stop_quiet_skips_shutdown_emit_and_logging() -> None:
    from Spyder.SpyderA_Core.SpyderA05_EventManager import EventManager

    instance = EventManager.__new__(EventManager)
    instance.is_running = True
    instance.logger = MagicMock()
    instance.emit = MagicMock()
    instance._shutdown_event = threading.Event()
    instance.priority_queue = queue.Queue()
    instance.event_queue = queue.Queue()
    instance._persist_queue = queue.Queue()
    instance.persist_events = False
    instance.worker_threads = []
    instance._persistence_thread = None
    instance._metrics_thread = None
    instance.executor = MagicMock()
    instance.error_handler = MagicMock()

    ok = EventManager.stop(instance, quiet=True)

    assert ok is True
    assert instance.is_running is False
    instance.emit.assert_not_called()
    instance.logger.info.assert_not_called()
    instance.logger.warning.assert_not_called()
    instance.logger.error.assert_not_called()
    instance.executor.shutdown.assert_called_once()
