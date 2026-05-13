#!/usr/bin/env python3
"""Focused tests for G05 SessionSupervisor reuse."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

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