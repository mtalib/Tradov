#!/usr/bin/env python3
"""Focused tests for G05 SessionSupervisor reuse."""

from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

from Spyder.SpyderG_GUI import SpyderG05_TradingDashboard as g05
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import QMessageBox
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import TradingMode


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SimpleNamespace(debug=lambda *_args, **_kwargs: None)
    dash._log_lines = []
    dash.add_system_log = lambda message: dash._log_lines.append(str(message))
    dash._session_supervisor = None
    dash.trading_active = False
    dash.trading_mode = TradingMode.PAPER
    dash.connection_info = SimpleNamespace(trading_active=False)
    dash._sync_runtime_trading_mode_override = MagicMock()
    dash._refresh_positions_table = MagicMock()
    dash._start_live_pnl_poll = MagicMock()
    dash.start_btn = SimpleNamespace(
        setStyleSheet=MagicMock(),
        setText=MagicMock(),
        setEnabled=MagicMock(),
        setToolTip=MagicMock(),
    )
    return dash


def test_start_unified_session_supervisor_reuses_injected_instance() -> None:
    dash = _build_dashboard_stub()
    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=True))
    dash._session_supervisor = supervisor

    assert dash._start_unified_session_supervisor() is True

    supervisor.start.assert_called_once_with()
    assert dash._session_supervisor is supervisor
    assert dash._log_lines == []


def test_start_unified_session_supervisor_blocks_while_injected_autostart_is_running() -> None:
    dash = _build_dashboard_stub()
    supervisor = SimpleNamespace(
        is_running=False,
        start=MagicMock(return_value=True),
        _spyder_autostart_in_progress=True,
    )
    dash._session_supervisor = supervisor

    assert dash._start_unified_session_supervisor() is False

    supervisor.start.assert_not_called()
    assert dash._session_supervisor is supervisor
    assert dash._log_lines == ["⏳ Unified session autostart still in progress"]


def test_start_unified_session_supervisor_uses_helper_for_autostart_block(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    supervisor = SimpleNamespace(
        is_running=False,
        start=MagicMock(return_value=True),
        _spyder_autostart_in_progress=True,
    )
    dash._session_supervisor = supervisor

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_session_supervisor_start_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(action="block_autostart"),
    )

    assert dash._start_unified_session_supervisor() is False

    assert helper_calls == [
        {
            "has_supervisor": True,
            "autostart_in_progress": True,
            "supervisor_running": False,
        }
    ]
    supervisor.start.assert_not_called()
    assert dash._session_supervisor is supervisor
    assert dash._log_lines == ["⏳ Unified session autostart still in progress"]


def test_start_unified_session_supervisor_reuse_exception_fails_closed() -> None:
    dash = _build_dashboard_stub()
    supervisor = SimpleNamespace(
        is_running=False,
        start=MagicMock(side_effect=RuntimeError("boom")),
    )
    dash._session_supervisor = supervisor

    assert dash._start_unified_session_supervisor() is False

    supervisor.start.assert_called_once_with()
    assert dash._session_supervisor is None
    assert dash._log_lines == ["❌ Unified session start failed: boom"]


def test_start_unified_session_supervisor_uses_attempt_helper_for_reuse_failure(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=False))
    dash._session_supervisor = supervisor

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_session_supervisor_start_attempt_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(return_value=False, clear_supervisor=True, log_message=None),
    )

    assert dash._start_unified_session_supervisor() is False

    assert helper_calls == [{"started": False, "error_text": None}]
    supervisor.start.assert_called_once_with()
    assert dash._session_supervisor is None
    assert dash._log_lines == []


def test_start_unified_session_supervisor_authorizes_explicit_paper_start(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    dash._paper_trading_armed = True
    dash._paper_trading_enabled_this_session = True
    dash._paper_start_authorized = True
    supervisor = SimpleNamespace(is_running=False, start=MagicMock(return_value=False))
    dash._session_supervisor = supervisor

    helper_calls: list[object] = []
    r12 = import_module("Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor")

    monkeypatch.setattr(
        r12,
        "authorize_paper_session_start",
        lambda current: helper_calls.append(current),
    )
    monkeypatch.setattr(
        g05,
        "build_session_supervisor_start_attempt_plan",
        lambda **_kwargs: SimpleNamespace(
            return_value=False,
            clear_supervisor=True,
            log_message=None,
        ),
    )

    assert dash._start_unified_session_supervisor() is False

    assert helper_calls == [supervisor]
    supervisor.start.assert_called_once_with()
    assert dash._session_supervisor is None


def test_emergency_close_stops_supervisor_with_flatten() -> None:
    dash = _build_dashboard_stub()
    dash.connection_info = SimpleNamespace(api_connected=True, trading_active=True)
    dash.trading_active = True
    dash.start_btn = SimpleNamespace(
        setStyleSheet=MagicMock(),
        setText=MagicMock(),
    )
    dash.market_worker = SimpleNamespace(force_disconnect=MagicMock())
    dash._stop_unified_session_supervisor = MagicMock()
    dash._stop_live_pnl_poll = MagicMock()

    with patch(
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QMessageBox.critical",
        return_value=QMessageBox.StandardButton.Yes,
    ):
        SpyderTradingDashboard.emergency_close(dash)

    dash._stop_unified_session_supervisor.assert_called_once_with(flatten=True)
    dash._stop_live_pnl_poll.assert_called_once_with()
    dash.market_worker.force_disconnect.assert_called_once_with()
    assert dash.trading_active is False
    assert dash.connection_info.trading_active is False
    assert dash.api_connected is False


def test_adopt_running_session_supervisor_ui_state_marks_paper_session_active() -> None:
    dash = _build_dashboard_stub()
    dash._session_supervisor = SimpleNamespace(is_running=True)

    with patch(
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.is_market_hours",
        return_value=True,
    ):
        SpyderTradingDashboard._adopt_running_session_supervisor_ui_state(dash)

    assert dash.trading_active is True
    assert dash.connection_info.trading_active is True
    dash._sync_runtime_trading_mode_override.assert_called_once_with()
    dash.start_btn.setText.assert_called_once_with("PAPER ACTIVE")
    dash._refresh_positions_table.assert_called_once_with()
    assert dash._log_lines == [
        "🚀 PAPER trading started — market data confirmed live",
        "TRADING ACTIVE [PAPER] - Unified session started",
    ]


def test_adopt_running_session_supervisor_ui_state_uses_helper_for_after_hours_paper(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    dash._session_supervisor = SimpleNamespace(is_running=True)
    dash._set_start_button_active_state = MagicMock()

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_session_supervisor_adoption_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            set_start_button_active=True,
            log_messages=(
                "custom start log",
                "custom after-hours log",
            ),
            follow_up_action="refresh_paper_positions",
        ),
    )
    monkeypatch.setattr(g05, "is_market_hours", lambda: False)

    SpyderTradingDashboard._adopt_running_session_supervisor_ui_state(dash)

    assert helper_calls == [
        {
            "trading_mode_value": "PAPER",
            "loading_timer_active": False,
            "was_active": False,
            "market_open": False,
        }
    ]
    dash._set_start_button_active_state.assert_called_once_with()
    dash._refresh_positions_table.assert_called_once_with()
    dash._start_live_pnl_poll.assert_not_called()
    assert dash._log_lines == ["custom start log", "custom after-hours log"]


def test_start_metrics_orchestrator_waits_for_first_live_snapshot() -> None:
    dash = _build_dashboard_stub()
    dash._on_custom_metrics_updated = MagicMock()
    dash._on_market_stress_changed = MagicMock()
    dash.symbol_widgets = {}
    dash.current_dialog = None
    dash.signal_panel = None

    orchestrator = SimpleNamespace(
        metrics_updated=SimpleNamespace(connect=MagicMock()),
        stress_level_changed=SimpleNamespace(connect=MagicMock()),
        has_published_metrics_snapshot=lambda: False,
        current_metrics={},
        _format_metrics=lambda payload: payload,
    )

    with patch(
        "SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator.get_metrics_orchestrator",
        return_value=orchestrator,
    ):
        SpyderTradingDashboard._start_metrics_orchestrator(dash)

    dash._on_custom_metrics_updated.assert_not_called()
    assert dash._metrics_orchestrator is orchestrator
    assert dash._log_lines == [
        "⏳ Custom metrics orchestrator started — awaiting first live snapshot",
    ]


def test_on_custom_metrics_updated_announces_active_once() -> None:
    dash = _build_dashboard_stub()
    dash.symbol_widgets = {}
    dash.current_dialog = None
    dash.signal_panel = None
    dash.update_regime_pills = MagicMock()
    dash._update_liquidity_diagnostics_panel = MagicMock()
    dash._custom_metrics_live_announced = False

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {})
    SpyderTradingDashboard._on_custom_metrics_updated(dash, {})

    assert dash._log_lines == [
        "✅ Custom metrics orchestrator started (DIX + Black Swan schedulers active)",
        "AUTONOMOUS METRICS ACTIVE - DIX/SWAN stress monitor online",
    ]


def test_on_custom_metrics_updated_uses_start_plan_helper(monkeypatch) -> None:
    dash = _build_dashboard_stub()
    dash.symbol_widgets = {}
    dash.current_dialog = None
    dash.signal_panel = None
    dash.update_regime_pills = MagicMock()
    dash._update_liquidity_diagnostics_panel = MagicMock()
    dash._custom_metrics_live_announced = False
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_metrics_orchestrator_start_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            live_announced_after_start=True,
            log_messages=("custom active log", "custom autonomous log"),
        ),
    )

    SpyderTradingDashboard._on_custom_metrics_updated(dash, {})

    assert helper_calls == [{"hydrated_snapshot": True}]
    assert dash._log_lines == ["custom active log", "custom autonomous log"]


def test_complete_start_button_loading_transition_cancels_after_shutdown_begins() -> None:
    dash = _build_dashboard_stub()
    dash._shutdown_in_progress = True
    dash._start_button_loading_generation = 3
    dash._start_button_loading_timer_active = True
    dash._paper_session_start_pending = True
    dash._paper_session_start_show_failure_dialog = True
    dash._start_unified_session_supervisor = MagicMock(return_value=True)
    dash._set_start_button_active_state = MagicMock()

    SpyderTradingDashboard._complete_start_button_loading_transition(dash, 3)

    dash._start_unified_session_supervisor.assert_not_called()
    dash._set_start_button_active_state.assert_not_called()
    assert dash._paper_session_start_pending is False
    assert dash._paper_session_start_show_failure_dialog is False
    assert dash._start_button_loading_timer_active is False
    assert dash._start_button_loading_generation == 4


def test_complete_start_button_loading_transition_uses_helper_to_activate_after_finalize(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    dash._start_button_loading_generation = 4
    dash._start_button_loading_timer_active = True
    dash._paper_session_start_pending = True
    dash._session_supervisor = SimpleNamespace(is_running=False)
    dash._finalize_queued_paper_session_start = MagicMock(
        side_effect=lambda: setattr(dash, "trading_active", True)
    )
    dash._set_start_button_active_state = MagicMock()
    dash._cancel_start_button_loading_transition = MagicMock()

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_loading_transition_completion_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            action="complete",
            finalize_pending_start=True,
            set_timer_inactive=True,
            activate_button=True,
        ),
    )

    SpyderTradingDashboard._complete_start_button_loading_transition(dash, 4)

    assert helper_calls == [
        {
            "expected_generation": 4,
            "current_generation": 4,
            "shutdown_in_progress": False,
            "session_start_pending": True,
            "trading_active": False,
            "supervisor_running": False,
        }
    ]
    assert dash._start_button_loading_timer_active is False
    dash._finalize_queued_paper_session_start.assert_called_once_with()
    dash._set_start_button_active_state.assert_called_once_with()
    dash._cancel_start_button_loading_transition.assert_not_called()


def test_begin_start_button_loading_transition_uses_helper_to_schedule_loading(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    dash._start_button_loading_generation = 5
    dash._start_button_loading_timer_active = False
    dash._remaining_paper_start_loading_delay_ms = MagicMock(return_value=4321)
    dash._set_start_button_loading_live_data_state = MagicMock()
    dash._complete_start_button_loading_transition = MagicMock()

    timer_calls: list[tuple[int, object]] = []
    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "QTimer",
        SimpleNamespace(singleShot=lambda ms, cb: timer_calls.append((ms, cb))),
    )
    monkeypatch.setattr(
        g05,
        "build_loading_transition_begin_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            action="begin",
            next_generation=6,
            delay_ms=4321,
            set_timer_active=True,
            schedule_with_qtimer=True,
        ),
    )

    SpyderTradingDashboard._begin_start_button_loading_transition(dash)

    assert helper_calls == [
        {
            "is_paper_mode": True,
            "current_generation": 5,
            "delay_ms": 4321,
            "qtimer_available": True,
        }
    ]
    assert dash._start_button_loading_generation == 6
    assert dash._start_button_loading_timer_active is True
    dash._remaining_paper_start_loading_delay_ms.assert_called_once_with()
    dash._set_start_button_loading_live_data_state.assert_called_once_with()
    assert len(timer_calls) == 1
    assert timer_calls[0][0] == 4321
    dash._complete_start_button_loading_transition.assert_not_called()


def test_restore_start_button_ready_state_uses_helper_for_paper_mode(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    dash._cancel_start_button_loading_transition = MagicMock()

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_start_button_ready_state_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            action="restore",
            style_sheet="background-color: #11aa22; color: black;",
            text="START TRADING",
            enabled=True,
            tooltip="paper ready tooltip",
        ),
    )

    SpyderTradingDashboard._restore_start_button_ready_state(dash)

    assert helper_calls == [
        {
            "has_start_button": True,
            "trading_active": False,
            "is_paper_mode": True,
            "positive_color": g05.COLORS["positive"],
        }
    ]
    dash._cancel_start_button_loading_transition.assert_called_once_with()
    dash.start_btn.setStyleSheet.assert_called_once_with(
        "background-color: #11aa22; color: black;"
    )
    dash.start_btn.setText.assert_called_once_with("START TRADING")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with("paper ready tooltip")


def test_set_start_button_active_state_uses_helper_for_live_mode(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    dash.trading_mode = TradingMode.LIVE

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        g05,
        "build_start_button_active_state_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            action="render",
            style_sheet="background-color: #004466; color: white;",
            text="TRADING ACTIVE",
            enabled=True,
            tooltip="live active tooltip",
        ),
    )

    SpyderTradingDashboard._set_start_button_active_state(dash)

    assert helper_calls == [
        {
            "has_start_button": True,
            "is_paper_mode": False,
            "market_open": True,
            "automation_active_color": g05.COLORS["automation_active"],
        }
    ]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        "background-color: #004466; color: white;"
    )
    dash.start_btn.setText.assert_called_once_with("TRADING ACTIVE")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with("live active tooltip")


def test_set_start_button_active_state_uses_helper_for_after_hours_paper(
    monkeypatch,
) -> None:
    dash = _build_dashboard_stub()
    dash.trading_mode = TradingMode.PAPER

    helper_calls: list[dict[str, object]] = []

    monkeypatch.setattr(g05, "is_market_hours", lambda: False)
    monkeypatch.setattr(
        g05,
        "build_start_button_active_state_plan",
        lambda **kwargs: helper_calls.append(dict(kwargs))
        or SimpleNamespace(
            action="render",
            style_sheet="background-color: #004466; color: white;",
            text="PAPER STANDBY",
            enabled=True,
            tooltip="after-hours paper tooltip",
        ),
    )

    SpyderTradingDashboard._set_start_button_active_state(dash)

    assert helper_calls == [
        {
            "has_start_button": True,
            "is_paper_mode": True,
            "market_open": False,
            "automation_active_color": g05.COLORS["automation_active"],
        }
    ]
    dash.start_btn.setStyleSheet.assert_called_once_with(
        "background-color: #004466; color: white;"
    )
    dash.start_btn.setText.assert_called_once_with("PAPER STANDBY")
    dash.start_btn.setEnabled.assert_called_once_with(True)
    dash.start_btn.setToolTip.assert_called_once_with("after-hours paper tooltip")
