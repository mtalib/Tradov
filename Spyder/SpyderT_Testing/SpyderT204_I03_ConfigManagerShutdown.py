#!/usr/bin/env python3
"""Focused tests for I03 ConfigManager shutdown cleanup."""

import sys
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

from Spyder.SpyderI_Integration.SpyderI03_ConfigManager import ConfigManager


def _build_manager_stub() -> ConfigManager:
    manager = ConfigManager.__new__(ConfigManager)
    manager.logger = MagicMock()
    manager.error_handler = SimpleNamespace(handle_error=MagicMock())
    manager.sync_lock = threading.RLock()
    manager._shutdown_lock = threading.Lock()
    manager._shutdown_event = threading.Event()
    manager._shutdown_registered = False
    manager._shutdown_complete = False
    manager.file_observer = None
    manager.sync_thread = None
    manager.pending_changes = {}
    manager._process_pending_changes = MagicMock()
    return manager


def test_i03_shutdown_stops_file_observer_and_sync_thread() -> None:
    manager = _build_manager_stub()
    manager.file_observer = MagicMock()
    manager.sync_thread = MagicMock()
    manager.sync_thread.is_alive.return_value = True
    manager.pending_changes = {"demo": [object()]}

    manager.shutdown()

    assert manager._shutdown_event.is_set() is True
    manager.file_observer.stop.assert_called_once_with()
    manager.file_observer.join.assert_called_once_with(timeout=2.0)
    manager.sync_thread.join.assert_called_once_with(timeout=2.0)
    manager._process_pending_changes.assert_called_once_with()


def test_i03_shutdown_is_idempotent() -> None:
    manager = _build_manager_stub()
    manager.file_observer = MagicMock()

    manager.shutdown()
    manager.shutdown()

    manager.file_observer.stop.assert_called_once_with()
    manager.file_observer.join.assert_called_once_with(timeout=2.0)


def test_i03_register_shutdown_cleanup_registers_once(monkeypatch) -> None:
    manager = _build_manager_stub()
    coordinator = SimpleNamespace(register_cleanup=MagicMock())
    fake_module = SimpleNamespace(get_shutdown_coordinator=lambda: coordinator)
    monkeypatch.setitem(
        sys.modules,
        "Spyder.SpyderU_Utilities.SpyderU44_ShutdownCoordinator",
        fake_module,
    )

    ConfigManager._register_shutdown_cleanup(manager)
    ConfigManager._register_shutdown_cleanup(manager)

    coordinator.register_cleanup.assert_called_once_with(manager.shutdown)
    assert manager._shutdown_registered is True
