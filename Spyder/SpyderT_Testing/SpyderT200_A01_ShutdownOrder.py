#!/usr/bin/env python3
"""Focused tests for A01 shutdown ordering around GUI and SessionSupervisor."""

import datetime
import logging
import time
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def test_a01_shutdown_closes_main_window_before_session_supervisor_stop():
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    a03_config = import_module("Spyder.SpyderA_Core.SpyderA03_Configuration")

    SpyderApplication = a01_main.SpyderApplication

    call_order: list[str] = []
    original_has_coordinator = getattr(a01_main, "_HAS_COORDINATOR")
    original_get_coordinator = getattr(a01_main, "_get_coordinator")

    setattr(a01_main, "_HAS_COORDINATOR", True)
    setattr(a01_main, "_get_coordinator", lambda: SimpleNamespace(
        shutdown=lambda timeout=1.0: call_order.append(
            f"shutdown_coordinator:{timeout}"
        )
    ))

    original_reset_config_manager = getattr(a03_config, "reset_config_manager")
    setattr(a03_config, "reset_config_manager", lambda: call_order.append("reset_config_manager"))

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
    )
    app.shutdown_requested = False
    app.running = True
    app.client = None
    app.telegram_bot = None
    app.main_window = SimpleNamespace(close=lambda: call_order.append("close_window"))
    app.session_supervisor = SimpleNamespace(
        stop=lambda flatten=False: call_order.append(f"stop_supervisor:{flatten}")
    )
    app.event_manager = SimpleNamespace(stop=lambda: call_order.append("stop_event_manager"))
    app.gui_app = SimpleNamespace(
        quit=lambda: call_order.append("quit_gui"),
        processEvents=lambda: call_order.append("process_events"),
    )

    try:
        app.shutdown()
    finally:
        setattr(a01_main, "_HAS_COORDINATOR", original_has_coordinator)
        setattr(a01_main, "_get_coordinator", original_get_coordinator)
        setattr(a03_config, "reset_config_manager", original_reset_config_manager)

    assert app.shutdown_requested is True
    assert app.running is False
    assert app.session_supervisor is None
    assert app.event_manager is None
    assert call_order == [
        "close_window",
        "process_events",
        "stop_supervisor:False",
        "stop_event_manager",
        "reset_config_manager",
        "shutdown_coordinator:1.0",
        "quit_gui",
        "process_events",
    ]


def test_a01_run_aborts_startup_after_shutdown_requested(monkeypatch) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    config_module = import_module("config.config")

    SpyderApplication = a01_main.SpyderApplication

    call_order: list[str] = []

    monkeypatch.setattr(
        config_module,
        "validate_startup_config",
        lambda: None,
        raising=False,
    )

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
        debug=lambda *_args, **_kwargs: None,
    )
    app.config = SimpleNamespace(enable_gui=True, headless_mode=False)
    app.shutdown_requested = False
    app.running = False
    app.client = None
    app.telegram_bot = None
    app.main_window = None
    app.session_supervisor = None
    app.event_manager = None
    app.gui_app = None

    def _initialize_core_systems() -> bool:
        call_order.append("initialize_core_systems")
        app.shutdown_requested = True
        return True

    app.initialize_core_systems = _initialize_core_systems
    app.start_gui = lambda: call_order.append("start_gui") or True
    app.shutdown = lambda: call_order.append("shutdown")

    assert app.run() == 0
    assert call_order == ["initialize_core_systems", "shutdown"]


def test_a01_finalize_process_exit_flushes_logs_then_exits(monkeypatch) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")

    call_order: list[str] = []

    monkeypatch.setattr(
        a01_main.logging,
        "shutdown",
        lambda: call_order.append("logging_shutdown"),
    )

    def _fake_exit(code: int) -> None:
        call_order.append(f"os_exit:{code}")
        raise SystemExit(code)

    monkeypatch.setattr(a01_main.os, "_exit", _fake_exit)

    with pytest.raises(SystemExit) as exc_info:
        getattr(a01_main, "_finalize_process_exit")(7)

    assert exc_info.value.code == 7
    assert call_order == ["logging_shutdown", "os_exit:7"]


def test_a01_initialize_core_systems_blocks_session_supervisor_autostart_for_gui_by_default(
    monkeypatch,
) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    r12 = import_module("Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor")

    SpyderApplication = a01_main.SpyderApplication

    monkeypatch.setenv("SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR", "1")
    monkeypatch.setenv("SPYDER_A01_AUTOSTART_MODE", "paper")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(a01_main, "has_qt", True, raising=False)
    monkeypatch.setattr(a01_main, "QTimer", SimpleNamespace(singleShot=lambda *_args, **_kwargs: None), raising=False)
    monkeypatch.setattr(a01_main, "has_event_manager", True, raising=False)
    monkeypatch.setattr(a01_main, "EventManager", object, raising=False)
    monkeypatch.setattr(a01_main, "get_event_manager", lambda: SimpleNamespace(), raising=False)

    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=True))
    monkeypatch.setattr(r12, "create_session_supervisor", lambda mode: supervisor)

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    app.config = SimpleNamespace(enable_gui=True, headless_mode=False)
    app.shutdown_requested = False
    app.event_manager = None
    app.connection_manager = None
    app.client = None
    app.telegram_bot = None
    app.session_supervisor = None
    app._session_supervisor_autostart_pending = False
    app._session_supervisor_autostart_mode = None
    app.main_window = None
    app.gui_app = None

    assert app.initialize_core_systems() is True
    assert app.session_supervisor is None
    assert app._session_supervisor_autostart_pending is False
    assert app._session_supervisor_autostart_mode is None
    supervisor.start.assert_not_called()


def test_a01_initialize_core_systems_defers_session_supervisor_autostart_when_gui_opted_in(
    monkeypatch,
) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    r12 = import_module("Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor")

    SpyderApplication = a01_main.SpyderApplication

    monkeypatch.setenv("SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR", "1")
    monkeypatch.setenv("SPYDER_A01_AUTOSTART_MODE", "paper")
    monkeypatch.setenv("SPYDER_A01_ALLOW_GUI_AUTOSTART", "1")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(a01_main, "has_qt", True, raising=False)
    monkeypatch.setattr(a01_main, "QTimer", SimpleNamespace(singleShot=lambda *_args, **_kwargs: None), raising=False)
    monkeypatch.setattr(a01_main, "has_event_manager", True, raising=False)
    monkeypatch.setattr(a01_main, "EventManager", object, raising=False)
    monkeypatch.setattr(a01_main, "get_event_manager", lambda: SimpleNamespace(), raising=False)

    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=True))
    monkeypatch.setattr(r12, "create_session_supervisor", lambda mode: supervisor)

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    app.config = SimpleNamespace(enable_gui=True, headless_mode=False)
    app.shutdown_requested = False
    app.event_manager = None
    app.connection_manager = None
    app.client = None
    app.telegram_bot = None
    app.session_supervisor = None
    app._session_supervisor_autostart_pending = False
    app._session_supervisor_autostart_mode = None
    app.main_window = None
    app.gui_app = None

    assert app.initialize_core_systems() is True
    assert app.session_supervisor is supervisor
    assert app._session_supervisor_autostart_pending is True
    assert app._session_supervisor_autostart_mode == "paper"
    supervisor.start.assert_not_called()


def test_a01_initialize_core_systems_never_autostarts_live_mode(
    monkeypatch,
) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    r12 = import_module("Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor")

    SpyderApplication = a01_main.SpyderApplication

    monkeypatch.setenv("SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR", "1")
    monkeypatch.setenv("SPYDER_A01_AUTOSTART_MODE", "live")
    monkeypatch.setenv("SPYDER_A01_ALLOW_GUI_AUTOSTART", "1")
    monkeypatch.setenv("SPYDER_A01_ALLOW_LIVE_AUTOSTART", "1")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(a01_main, "has_qt", True, raising=False)
    monkeypatch.setattr(a01_main, "QTimer", SimpleNamespace(singleShot=lambda *_args, **_kwargs: None), raising=False)
    monkeypatch.setattr(a01_main, "has_event_manager", True, raising=False)
    monkeypatch.setattr(a01_main, "EventManager", object, raising=False)
    monkeypatch.setattr(a01_main, "get_event_manager", lambda: SimpleNamespace(), raising=False)

    requested_modes: list[str] = []
    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=True))
    monkeypatch.setattr(
        r12,
        "create_session_supervisor",
        lambda mode: requested_modes.append(mode) or supervisor,
    )

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    app.config = SimpleNamespace(enable_gui=True, headless_mode=False)
    app.shutdown_requested = False
    app.event_manager = None
    app.connection_manager = None
    app.client = None
    app.telegram_bot = None
    app.session_supervisor = None
    app._session_supervisor_autostart_pending = False
    app._session_supervisor_autostart_mode = None
    app.main_window = None
    app.gui_app = None

    assert app.initialize_core_systems() is True
    assert requested_modes == ["paper"]
    assert app.session_supervisor is supervisor
    assert app._session_supervisor_autostart_pending is True
    assert app._session_supervisor_autostart_mode == "paper"
    supervisor.start.assert_not_called()


def test_a01_start_pending_session_supervisor_autostart_runs_in_background_thread(
    monkeypatch,
) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    SpyderApplication = a01_main.SpyderApplication

    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=True))
    created_thread: dict[str, object] = {}

    class _ImmediateThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:
            self._target = target
            self._alive = False
            created_thread["name"] = name
            created_thread["daemon"] = daemon

        def start(self) -> None:
            self._alive = True
            self._target()
            self._alive = False

        def is_alive(self) -> bool:
            return self._alive

        def join(self, timeout: float | None = None) -> None:
            return None

    monkeypatch.setattr(a01_main.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(a01_main, "QThread", None, raising=False)
    monkeypatch.setattr(
        a01_main,
        "QTimer",
        SimpleNamespace(singleShot=lambda *_args, **_kwargs: None),
        raising=False,
    )

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    app.shutdown_requested = False
    app.session_supervisor = supervisor
    app.main_window = SimpleNamespace(_session_supervisor=supervisor)
    app._session_supervisor_autostart_pending = True
    app._session_supervisor_autostart_mode = "paper"
    app._session_supervisor_autostart_thread = None
    app._session_supervisor_autostart_active = False
    app._session_supervisor_autostart_result = None
    app._session_supervisor_autostart_exception = None

    app._start_pending_session_supervisor_autostart()

    supervisor.start.assert_called_once_with()
    assert created_thread == {
        "name": "A01-session-supervisor-autostart",
        "daemon": True,
    }
    assert app.session_supervisor is supervisor
    assert app.main_window._session_supervisor is supervisor
    assert app._session_supervisor_autostart_pending is False
    assert app._session_supervisor_autostart_mode is None
    assert app._session_supervisor_autostart_thread is None
    assert app._session_supervisor_autostart_active is False
    assert getattr(supervisor, "_spyder_autostart_in_progress", False) is False


def test_a01_start_pending_session_supervisor_autostart_hands_paper_to_dashboard_loading_window() -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    SpyderApplication = a01_main.SpyderApplication

    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=True))
    queue_paper_session_start = MagicMock()

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    app.shutdown_requested = False
    app.session_supervisor = supervisor
    app.main_window = SimpleNamespace(
        _session_supervisor=supervisor,
        _queue_paper_session_start=queue_paper_session_start,
    )
    app._session_supervisor_autostart_pending = True
    app._session_supervisor_autostart_mode = "paper"
    app._session_supervisor_autostart_thread = None
    app._session_supervisor_autostart_active = False
    app._session_supervisor_autostart_result = None
    app._session_supervisor_autostart_exception = None

    app._start_pending_session_supervisor_autostart()

    queue_paper_session_start.assert_called_once_with(show_failure_dialog=False)
    supervisor.start.assert_not_called()
    assert app._session_supervisor_autostart_pending is False
    assert app._session_supervisor_autostart_mode is None
    assert app._session_supervisor_autostart_thread is None
    assert app._session_supervisor_autostart_active is False
    assert getattr(supervisor, "_spyder_autostart_in_progress", False) is False


def test_r12_stop_cancels_deferred_paper_l09_attach(monkeypatch) -> None:
    r12 = import_module("Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor")
    l09_module = import_module("Spyder.SpyderL_ML.SpyderL09_UnifiedRegimeEngine")

    created_configs: list[dict[str, object]] = []
    monkeypatch.setattr(
        l09_module,
        "create_unified_regime_engine",
        lambda config=None: created_configs.append(dict(config or {})) or SimpleNamespace(),
    )
    monkeypatch.setattr(r12, "_PAPER_ORCHESTRATOR_L09_DEFER_SECONDS", 5.0)

    supervisor = r12.SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
        debug=lambda *_args, **_kwargs: None,
    )
    supervisor._components = []
    supervisor._running = True
    orchestrator = SimpleNamespace(set_regime_engine=MagicMock())
    supervisor.orchestrator = orchestrator

    supervisor._start_deferred_orchestrator_regime_engine_initialization(orchestrator)
    supervisor.stop()

    assert created_configs == []
    orchestrator.set_regime_engine.assert_not_called()
    assert supervisor._deferred_l09_thread is None


def test_a01_resolve_gui_paper_autostart_delay_ms_defers_paper_until_opening_warmup_end() -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")

    now_et = datetime.datetime(2026, 5, 13, 8, 33, tzinfo=a01_main._A01_EASTERN_TZ)

    assert a01_main._resolve_gui_paper_autostart_delay_ms("paper", now_et) == 3_600_000
    assert a01_main._resolve_gui_paper_autostart_delay_ms(
        "paper",
        datetime.datetime(2026, 5, 13, 9, 31, tzinfo=a01_main._A01_EASTERN_TZ),
    ) == 250
    assert a01_main._resolve_gui_paper_autostart_delay_ms(
        "paper",
        datetime.datetime(2026, 5, 13, 10, 0, tzinfo=a01_main._A01_EASTERN_TZ),
    ) == 250
    assert a01_main._resolve_gui_paper_autostart_delay_ms(
        "paper",
        datetime.datetime(2026, 5, 13, 17, 23, tzinfo=a01_main._A01_EASTERN_TZ),
    ) == 250


def test_a01_finalize_session_supervisor_autostart_adopts_dashboard_ui_state_on_success() -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    SpyderApplication = a01_main.SpyderApplication

    adopt_ui = MagicMock()
    begin_loading_transition = MagicMock()
    supervisor = SimpleNamespace(is_running=True)

    app = SpyderApplication.__new__(SpyderApplication)
    app.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        error=lambda *_args, **_kwargs: None,
    )
    app.shutdown_requested = False
    app.session_supervisor = supervisor
    app.main_window = SimpleNamespace(
        _session_supervisor=supervisor,
        _adopt_running_session_supervisor_ui_state=adopt_ui,
        _begin_start_button_loading_transition=begin_loading_transition,
    )
    app._session_supervisor_autostart_thread = None
    app._session_supervisor_autostart_worker = None
    app._session_supervisor_autostart_active = True
    app._session_supervisor_autostart_mode = "paper"
    app._session_supervisor_autostart_result = True
    app._session_supervisor_autostart_exception = None

    app._finalize_session_supervisor_autostart()

    adopt_ui.assert_called_once_with()
    begin_loading_transition.assert_called_once_with()


def test_a01_offscreen_deferred_paper_autostart_hands_off_running_supervisor(
    monkeypatch,
    tmp_path,
) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    g05 = import_module("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard")
    h05 = import_module("Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB")
    r04 = import_module("Spyder.SpyderR_Runtime.SpyderR04_LiveEngine")
    r12 = import_module("Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SPYDER_TRADING_MODE", "paper")
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")
    monkeypatch.setenv("SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR", "1")
    monkeypatch.setenv("SPYDER_A01_ALLOW_GUI_AUTOSTART", "1")
    monkeypatch.setenv("SPYDER_A01_AUTOSTART_MODE", "paper")
    monkeypatch.setenv("SPYDER_D31_SIGNAL_DROP_AUDIT_DIR", str(tmp_path))
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    monkeypatch.setattr(a01_main, "_HAS_COORDINATOR", False, raising=False)
    monkeypatch.setattr(a01_main, "QThread", None, raising=False)
    monkeypatch.setattr(a01_main, "_SessionSupervisorAutostartWorker", None, raising=False)
    monkeypatch.setattr(r12.SessionSupervisor, "_start_data_feed", lambda self: True)
    monkeypatch.setattr(r12.SessionSupervisor, "_start_freshness_monitor", lambda self: True)
    monkeypatch.setattr(r12.SessionSupervisor, "_start_exit_monitor", lambda self: None)
    monkeypatch.setattr(r12.SessionSupervisor, "_start_liveness_monitor", lambda self: None)
    monkeypatch.setattr(r12.SessionSupervisor, "_boot_orphan_sweep", lambda self: None)
    monkeypatch.setattr(
        r12.SessionSupervisor,
        "_run_boot_self_test",
        lambda self, timeout_seconds=3.0: True,
    )

    paper_db_path = tmp_path / "data" / "spyder_paper_a01_smoke.db"
    paper_db_path.parent.mkdir(parents=True, exist_ok=True)
    paper_db = h05.TradingSessionDB(paper_db_path)
    leg_orders = [
        {
            "symbol": "SPY260515P00565000",
            "side": "buy_to_open",
            "quantity": 1,
            "order_type": "limit",
            "price": 0.45,
            "strategy_id": "iron_condor",
            "multileg_leg_execution": True,
            "multileg_parent_symbol": "SPY",
            "expiration": "2026-05-15",
            "strike": 565.0,
            "option_type": "put",
        },
        {
            "symbol": "SPY260515P00570000",
            "side": "sell_to_open",
            "quantity": 1,
            "order_type": "limit",
            "price": 1.25,
            "strategy_id": "iron_condor",
            "multileg_leg_execution": True,
            "multileg_parent_symbol": "SPY",
            "expiration": "2026-05-15",
            "strike": 570.0,
            "option_type": "put",
        },
        {
            "symbol": "SPY260515C00580000",
            "side": "sell_to_open",
            "quantity": 1,
            "order_type": "limit",
            "price": 1.30,
            "strategy_id": "iron_condor",
            "multileg_leg_execution": True,
            "multileg_parent_symbol": "SPY",
            "expiration": "2026-05-15",
            "strike": 580.0,
            "option_type": "call",
        },
        {
            "symbol": "SPY260515C00585000",
            "side": "buy_to_open",
            "quantity": 1,
            "order_type": "limit",
            "price": 0.55,
            "strategy_id": "iron_condor",
            "multileg_leg_execution": True,
            "multileg_parent_symbol": "SPY",
            "expiration": "2026-05-15",
            "strike": 585.0,
            "option_type": "call",
        },
    ]

    with patch(
        "Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB.TradingSessionDB.for_paper",
        return_value=paper_db,
    ), patch.object(
        g05.SpyderTradingDashboard,
        "start_market_worker",
        lambda self, quiet_startup=False, announce=True: None,
    ), patch.object(
        g05.SpyderTradingDashboard,
        "_schedule_runtime_followup_startup_tasks",
        lambda self: None,
    ), patch.object(
        g05.SpyderTradingDashboard,
        "_start_optional_signal_refresh_timer",
        lambda self: None,
    ), patch.object(
        g05.SpyderTradingDashboard,
        "_init_h07_performance_analytics",
        lambda self: None,
    ), patch.object(
        g05.SpyderTradingDashboard,
        "_start_decision_flow_timer",
        lambda self: None,
    ), patch.object(
        g05,
        "START_BUTTON_LOADING_DELAY_MS",
        0,
    ), patch.object(
        g05,
        "is_market_hours",
        lambda *_args, **_kwargs: True,
    ), patch.object(
        r04.LiveEngine,
        "_is_market_open",
        lambda self: True,
    ):
        app = a01_main.SpyderApplication()
        try:
            assert app.initialize_core_systems() is True
            assert app._session_supervisor_autostart_pending is True
            assert app.start_gui() is True

            app._start_pending_session_supervisor_autostart()
            assert app._wait_for_session_supervisor_autostart_thread(20.0) is True
            if getattr(app.main_window, "_paper_session_start_pending", False):
                app.main_window._complete_start_button_loading_transition(
                    app.main_window._start_button_loading_generation
                )
            app._finalize_session_supervisor_autostart()

            assert app.session_supervisor is not None
            assert app.session_supervisor.is_running is True
            assert getattr(app.main_window, "_session_supervisor", None) is app.session_supervisor

            app.session_supervisor.engine._is_trading_allowed = lambda: True
            app.session_supervisor.orchestrator._build_paper_iron_condor_leg_orders = (
                lambda *args, **kwargs: list(leg_orders)
            )
            app.session_supervisor.orchestrator._dispatch_approved_signal(
                {
                    "strategy_id": "iron_condor",
                    "strategy_type": "iron_condor",
                    "symbol": "SPY",
                    "action": "sell",
                    "quantity": 1,
                    "price": 2.15,
                    "confidence": 0.8,
                }
            )

            session_db = h05.TradingSessionDB(paper_db_path)
            deadline = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=6)
            trades = []
            while datetime.datetime.now(datetime.UTC) < deadline:
                trades = list(session_db.get_trades_today() or [])
                if len(trades) >= 4:
                    break
                a01_main.time.sleep(0.1)

            assert len(trades) == 4
        finally:
            app.shutdown()


def test_a01_offscreen_market_hours_launch_keeps_runtime_logs_quiet_until_release(
    monkeypatch,
    tmp_path,
    caplog,
) -> None:
    a01_main = import_module("Spyder.SpyderA_Core.SpyderA01_Main")
    g05 = import_module("Spyder.SpyderG_GUI.SpyderG05_TradingDashboard")

    class _FakeDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 5, 13, 14, 0, tzinfo=tz)

    def _mark_market_worker_started(self, quiet_startup=False, announce=True) -> None:
        self._market_worker_started = True

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SPYDER_TRADING_MODE", "paper")
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")
    monkeypatch.delenv("SPYDER_A01_AUTOSTART_SESSION_SUPERVISOR", raising=False)
    monkeypatch.delenv("SPYDER_A01_ALLOW_GUI_AUTOSTART", raising=False)
    monkeypatch.delenv("SPYDER_A01_AUTOSTART_MODE", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    monkeypatch.setattr(a01_main, "_HAS_COORDINATOR", False, raising=False)
    monkeypatch.setattr(g05, "datetime", _FakeDateTime)
    monkeypatch.setattr(g05, "is_market_hours", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(g05, "START_BUTTON_LOADING_DELAY_MS", 3000)
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "start_market_worker",
        _mark_market_worker_started,
    )
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "_init_h07_performance_analytics",
        lambda self: None,
    )
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "_start_decision_flow_timer",
        lambda self: None,
    )
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "_schedule_runtime_followup_startup_tasks",
        lambda self: None,
    )
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "_start_optional_signal_refresh_timer",
        lambda self: None,
    )
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "_restore_snapshot",
        lambda self: None,
    )
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "_init_account_display",
        lambda self: None,
    )
    monkeypatch.setattr(
        g05.SpyderTradingDashboard,
        "_refresh_startup_readiness_state",
        lambda self: None,
    )

    caplog.set_level(logging.INFO)
    app = a01_main.SpyderApplication()
    runtime_release_markers = (
        "Subscribed to RISK events for event-clock display",
        "Subscribed to TRADE events for execution-health display",
        "Subscribed to POSITION_UPDATED events for paper position refresh",
        "Subscribed to alert events for entry-block visibility",
    )

    try:
        assert app.initialize_core_systems() is True
        assert app._session_supervisor_autostart_pending is False
        assert app.start_gui() is True
        assert getattr(app.main_window, "_market_hours_launch_loading_hold_active", False) is True

        caplog.clear()

        pre_release_deadline = time.monotonic() + 0.2
        while time.monotonic() < pre_release_deadline:
            app.gui_app.processEvents()
            time.sleep(0.01)

        pre_release_messages = [record.getMessage() for record in caplog.records]
        assert getattr(app.main_window, "_opening_runtime_warmup_completed", False) is False
        assert not any(
            marker in message
            for message in pre_release_messages
            for marker in runtime_release_markers
        )

        release_deadline = time.monotonic() + 4.0
        while time.monotonic() < release_deadline:
            app.gui_app.processEvents()
            time.sleep(0.01)
            if any(
                marker in record.getMessage()
                for record in caplog.records
                for marker in runtime_release_markers
            ):
                break

        post_release_messages = [record.getMessage() for record in caplog.records]
        assert getattr(app.main_window, "_opening_runtime_warmup_completed", False) is True
        assert getattr(app.main_window, "_market_hours_launch_loading_hold_active", True) is False
        assert any(
            "Subscribed to RISK events for event-clock display" in message
            for message in post_release_messages
        )
    finally:
        app.shutdown()
