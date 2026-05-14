#!/usr/bin/env python3
"""Focused tests for non-blocking S07 DIX startup behavior."""

import importlib.util as _ilu
import os
import sys
from types import SimpleNamespace

from apscheduler.schedulers.base import SchedulerNotRunningError

from Spyder.SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator import CustomMetricsOrchestrator


_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _load_real_dix_scheduler_class():
    module_name = "_t205_real_s02_module"
    module_path = os.path.join(_ROOT, "Spyder", "SpyderS_Signals", "SpyderS02_DIXScheduler.py")
    spec = _ilu.spec_from_file_location(module_name, module_path)
    module = _ilu.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules[module_name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module.SpyderDIXScheduler


class _CallSpy:
    def __init__(self, *, side_effect: Exception | None = None) -> None:
        self.calls: list[tuple[tuple, dict]] = []
        self._side_effect = side_effect

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._side_effect is not None:
            raise self._side_effect

    def assert_called_once_with(self, *args, **kwargs) -> None:
        assert self.calls == [((args), kwargs)]

    def assert_not_called(self) -> None:
        assert self.calls == []


def test_s02_start_can_skip_initial_calculation() -> None:
    scheduler_cls = _load_real_dix_scheduler_class()
    scheduler = scheduler_cls.__new__(scheduler_cls)
    scheduler.scheduler = SimpleNamespace(start=_CallSpy())
    scheduler.logger = SimpleNamespace(
        debug=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    scheduler.error_handler = SimpleNamespace(handle_error=_CallSpy())
    scheduler.run_scheduled_calculation = _CallSpy()

    scheduler_cls.start(scheduler, run_initial_calculation=False)

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
    orchestrator.dix_scheduler = SimpleNamespace(stop=_CallSpy())
    orchestrator.swan_scheduler = None
    orchestrator.tv_client = None
    orchestrator.update_timer = SimpleNamespace(stop=_CallSpy())
    orchestrator.ib_connected = True
    orchestrator.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    orchestrator.connection_status_changed = SimpleNamespace(emit=_CallSpy())

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
    orchestrator.dix_scheduler = SimpleNamespace(stop=_CallSpy())
    orchestrator.swan_scheduler = None
    orchestrator.tv_client = None
    orchestrator.update_timer = SimpleNamespace(stop=_CallSpy())
    orchestrator.ib_connected = True
    orchestrator.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    orchestrator.connection_status_changed = SimpleNamespace(emit=_CallSpy())

    CustomMetricsOrchestrator.stop(orchestrator)

    assert join_calls == [12.0]
    assert orchestrator._startup_thread is None


def test_s02_stop_ignores_scheduler_not_running() -> None:
    scheduler_cls = _load_real_dix_scheduler_class()
    scheduler = scheduler_cls.__new__(scheduler_cls)
    scheduler.scheduler = SimpleNamespace(
        shutdown=_CallSpy(side_effect=SchedulerNotRunningError()),
    )
    scheduler.logger = SimpleNamespace(
        info=_CallSpy(),
        debug=_CallSpy(),
        error=_CallSpy(),
    )

    scheduler_cls.stop(scheduler)

    scheduler.logger.error.assert_not_called()
    scheduler.logger.debug.assert_called_once_with(
        "DIX Scheduler stop skipped; scheduler not running"
    )
