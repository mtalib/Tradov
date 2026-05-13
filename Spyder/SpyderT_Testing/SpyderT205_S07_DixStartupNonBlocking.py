#!/usr/bin/env python3
"""Focused tests for non-blocking S07 DIX startup behavior."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from apscheduler.schedulers.base import SchedulerNotRunningError

from Spyder.SpyderS_Signals.SpyderS02_DIXScheduler import SpyderDIXScheduler
from Spyder.SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import CustomMetricsOrchestrator


def test_s02_start_can_skip_initial_calculation() -> None:
    scheduler = SpyderDIXScheduler.__new__(SpyderDIXScheduler)
    scheduler.scheduler = SimpleNamespace(start=MagicMock())
    scheduler.logger = SimpleNamespace(
        debug=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    scheduler.error_handler = SimpleNamespace(handle_error=MagicMock())
    scheduler.run_scheduled_calculation = MagicMock()

    SpyderDIXScheduler.start(scheduler, run_initial_calculation=False)

    scheduler.scheduler.start.assert_called_once_with()
    scheduler.run_scheduled_calculation.assert_not_called()


def test_s07_startup_fetch_starts_dix_scheduler_without_initial_run() -> None:
    orchestrator = CustomMetricsOrchestrator.__new__(CustomMetricsOrchestrator)
    orchestrator._shutdown_requested = False
    orchestrator._startup_thread = None
    orchestrator._calculators_initialized = True
    orchestrator.logger = SimpleNamespace(
        debug=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    orchestrator.swan_scheduler = None
    start_calls: list[bool] = []
    orchestrator.dix_scheduler = SimpleNamespace(
        initialize=lambda: True,
        start=lambda run_initial_calculation=True: start_calls.append(run_initial_calculation),
    )

    CustomMetricsOrchestrator._startup_fetch(orchestrator)

    assert start_calls == [False]


def test_s07_stop_waits_for_active_update_thread() -> None:
    join_calls: list[float] = []

    class _Thread:
        def __init__(self) -> None:
            self._alive = True

        def is_alive(self) -> bool:
            return self._alive

        def join(self, timeout: float | None = None) -> None:
            join_calls.append(timeout)
            self._alive = False

    orchestrator = CustomMetricsOrchestrator.__new__(CustomMetricsOrchestrator)
    orchestrator._shutdown_requested = False
    orchestrator._startup_thread = None
    orchestrator._update_thread = _Thread()
    orchestrator._update_running = True
    orchestrator.dix_scheduler = SimpleNamespace(stop=MagicMock())
    orchestrator.swan_scheduler = None
    orchestrator.tv_client = None
    orchestrator.update_timer = SimpleNamespace(stop=MagicMock())
    orchestrator.ib_connected = True
    orchestrator.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    orchestrator.connection_status_changed = SimpleNamespace(emit=MagicMock())

    CustomMetricsOrchestrator.stop(orchestrator)

    assert join_calls == [2.0]
    assert orchestrator._update_thread is None
    assert orchestrator._update_running is False


def test_s07_stop_waits_for_active_startup_thread_before_clearing_handle() -> None:
    join_calls: list[float] = []

    class _Thread:
        def __init__(self) -> None:
            self._alive = True

        def is_alive(self) -> bool:
            return self._alive

        def join(self, timeout: float | None = None) -> None:
            join_calls.append(timeout)
            self._alive = False

    orchestrator = CustomMetricsOrchestrator.__new__(CustomMetricsOrchestrator)
    orchestrator._shutdown_requested = False
    orchestrator._startup_thread = _Thread()
    orchestrator._startup_join_timeout_seconds = 12.0
    orchestrator._update_thread = None
    orchestrator._update_running = False
    orchestrator.dix_scheduler = SimpleNamespace(stop=MagicMock())
    orchestrator.swan_scheduler = None
    orchestrator.tv_client = None
    orchestrator.update_timer = SimpleNamespace(stop=MagicMock())
    orchestrator.ib_connected = True
    orchestrator.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    orchestrator.connection_status_changed = SimpleNamespace(emit=MagicMock())

    CustomMetricsOrchestrator.stop(orchestrator)

    assert join_calls == [12.0]
    assert orchestrator._startup_thread is None


def test_s02_stop_ignores_scheduler_not_running() -> None:
    scheduler = SpyderDIXScheduler.__new__(SpyderDIXScheduler)
    scheduler.scheduler = SimpleNamespace(
        shutdown=MagicMock(side_effect=SchedulerNotRunningError()),
    )
    scheduler.logger = SimpleNamespace(
        info=MagicMock(),
        debug=MagicMock(),
        error=MagicMock(),
    )

    SpyderDIXScheduler.stop(scheduler)

    scheduler.logger.error.assert_not_called()
    scheduler.logger.debug.assert_called_once_with(
        "DIX Scheduler stop skipped; scheduler not running"
    )