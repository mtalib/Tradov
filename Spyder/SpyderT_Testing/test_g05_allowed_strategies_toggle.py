#!/usr/bin/env python3
"""Focused regression for reversible in-session ALLOWED STRATEGIES filtering."""

from __future__ import annotations

from types import SimpleNamespace

import Spyder.SpyderG_GUI.SpyderG05_TradingDashboard as dashboard_module
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard


class _FakeStrategy:
    pass


class _FakeRunningStrategy:
    def __init__(
        self,
        *,
        name: str,
        strategy_type: str,
        state: str,
        open_positions: int,
        active_signals: int,
        tail_hedge_status: str | None = None,
        tail_hedge_detail: str = "",
        short_risk_status: str | None = None,
        short_risk_detail: str = "",
    ) -> None:
        self.name = name
        self.strategy_type = strategy_type
        self.state = state
        self.positions = {f"pos-{idx}": object() for idx in range(open_positions)}
        self.active_signals = {f"sig-{idx}": object() for idx in range(active_signals)}
        if tail_hedge_status is not None:
            self._tail_hedge_status = tail_hedge_status
            self._tail_hedge_detail = tail_hedge_detail
        if short_risk_status is not None:
            self._short_leg_risk_status = short_risk_status
            self._short_leg_risk_detail = short_risk_detail

    def get_state(self) -> dict[str, object]:
        return {
            "name": self.name,
            "state": self.state,
            "open_positions": len(self.positions),
            "active_signals": len(self.active_signals),
        }


class _FakeHtmlBody:
    def __init__(self) -> None:
        self.html: str | None = None

    def setHtml(self, html: str) -> None:
        self.html = html


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks: list[object] = []

    def connect(self, callback: object) -> None:
        self._callbacks.append(callback)

    def emit(self, *args: object) -> None:
        for callback in list(self._callbacks):
            callback(*args)


class _FakeDialog:
    instances: list[_FakeDialog] = []

    def __init__(self, parent: object = None) -> None:
        self.parent = parent
        self.window_title = ""
        self.minimum_size: tuple[int, int] | None = None
        self.finished = _FakeSignal()
        self._timers: list[_FakeTimer] = []
        self.accepted = False
        self.rejected = False
        self.__class__.instances.append(self)

    def setWindowTitle(self, title: str) -> None:
        self.window_title = title

    def setMinimumSize(self, width: int, height: int) -> None:
        self.minimum_size = (width, height)

    def accept(self) -> None:
        self.accepted = True

    def reject(self) -> None:
        self.rejected = True

    def isVisible(self) -> bool:
        return True

    def raise_(self) -> None:
        return None

    def activateWindow(self) -> None:
        return None

    def exec(self) -> int:
        for timer in list(self._timers):
            timer.timeout.emit()
        self.finished.emit(0)
        return 0


class _FakeLayout:
    def __init__(self, parent: object = None) -> None:
        self.parent = parent
        self.widgets: list[object] = []

    def addWidget(self, widget: object) -> None:
        self.widgets.append(widget)


class _FakeScrollBar:
    def __init__(self) -> None:
        self._value = 0
        self._maximum = 100

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        self._value = value

    def maximum(self) -> int:
        return self._maximum


class _FakeTextEdit:
    instances: list[_FakeTextEdit] = []

    def __init__(self) -> None:
        self.read_only = False
        self.html_history: list[str] = []
        self._scroll_bar = _FakeScrollBar()
        self.__class__.instances.append(self)

    def setReadOnly(self, value: bool) -> None:
        self.read_only = value

    def setHtml(self, html: str) -> None:
        self.html_history.append(html)

    def verticalScrollBar(self) -> _FakeScrollBar:
        return self._scroll_bar


class _FakeTimer:
    instances: list[_FakeTimer] = []

    def __init__(self, parent: object = None) -> None:
        self.parent = parent
        self.timeout = _FakeSignal()
        self.interval_ms: int | None = None
        self.stopped = False
        self.__class__.instances.append(self)
        if parent is not None and hasattr(parent, "_timers"):
            parent._timers.append(self)

    def start(self, interval_ms: int) -> None:
        self.interval_ms = interval_ms

    def stop(self, *_args: object) -> None:
        self.stopped = True


class _FakeDialogButtonBox:
    class StandardButton:
        Close = object()

    def __init__(self, _buttons: object) -> None:
        self.rejected = _FakeSignal()
        self.accepted = _FakeSignal()


def test_g05_allowed_strategies_toggle_restores_reenabled_strategy_without_restart() -> None:
    orchestrator = SimpleNamespace(
        lean_strategy_allowlist={
            "ZeroHFT",
            "ZeroHFTStrategy",
            "IronCondor",
            "IronCondorStrategy",
        },
        available_strategies={
            "ZeroHFT": _FakeStrategy,
            "IronCondor": _FakeStrategy,
        },
    )
    dashboard = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dashboard._session_supervisor = SimpleNamespace(orchestrator=orchestrator)

    applied_narrow = dashboard._apply_allowed_strategies_to_active_orchestrator(("ZeroHFT",))

    assert applied_narrow is True
    assert orchestrator.available_strategies == {"ZeroHFT": _FakeStrategy}

    applied_reenable = dashboard._apply_allowed_strategies_to_active_orchestrator(
        ("ZeroHFT", "IronCondor")
    )

    assert applied_reenable is True
    assert set(orchestrator.available_strategies.keys()) == {"ZeroHFT", "IronCondor"}


def test_g05_running_strategies_snapshot_reports_zero_hft_runtime_status() -> None:
    orchestrator = SimpleNamespace(
        active_strategies={
            "zerohft-1": _FakeRunningStrategy(
                name="ZeroHFT",
                strategy_type="zero_hft",
                state="active",
                open_positions=1,
                active_signals=2,
                tail_hedge_status="HEDGED",
                tail_hedge_detail="Tail hedge verified for current session",
                short_risk_status="ACTIVE",
                short_risk_detail="Monitoring 1 active short leg",
            ),
            "iron-1": _FakeRunningStrategy(
                name="IronCondor",
                strategy_type="iron_condor",
                state="paused",
                open_positions=0,
                active_signals=0,
            ),
        },
        paused_strategies={"iron-1"},
    )
    dashboard = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dashboard._session_supervisor = SimpleNamespace(orchestrator=orchestrator)

    html = dashboard._build_running_strategies_status_html()

    assert "Running Strategy Status" in html
    assert "ZeroHFT" in html
    assert "HEDGED" in html
    assert "Monitoring 1 active short leg" in html
    assert "IronCondor" in html
    assert "PAUSED" in html


def test_g05_running_strategies_snapshot_handles_no_active_strategies() -> None:
    dashboard = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dashboard._session_supervisor = SimpleNamespace(orchestrator=SimpleNamespace(active_strategies={}))

    html = dashboard._build_running_strategies_status_html()

    assert "No strategies are currently running." in html


def test_g05_refresh_running_strategies_dialog_body_renders_latest_snapshot() -> None:
    dashboard = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dashboard._running_strategies_dialog_body = _FakeHtmlBody()
    dashboard._build_running_strategies_status_html = lambda: "<p>fresh</p>"

    dashboard._refresh_running_strategies_dialog_body()

    assert dashboard._running_strategies_dialog_body.html == "<p>fresh</p>"


def test_g05_clear_running_strategies_dialog_state_stops_timer_and_resets_refs() -> None:
    dashboard = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    fake_timer = _FakeTimer()
    dashboard._running_strategies_dialog_timer = fake_timer
    dashboard._running_strategies_dialog_body = object()
    dashboard._running_strategies_dialog = object()

    dashboard._clear_running_strategies_dialog_state()

    assert fake_timer.stopped is True
    assert dashboard._running_strategies_dialog_timer is None
    assert dashboard._running_strategies_dialog_body is None
    assert dashboard._running_strategies_dialog is None


def test_g05_running_strategies_dialog_auto_refreshes_while_open(monkeypatch) -> None:
    html_values = iter(["<p>first</p>", "<p>second</p>"])
    dashboard = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dashboard._build_running_strategies_status_html = lambda: next(html_values, "<p>second</p>")

    _FakeDialog.instances.clear()
    _FakeTextEdit.instances.clear()
    _FakeTimer.instances.clear()
    monkeypatch.setattr(dashboard_module, "QDialog", _FakeDialog)
    monkeypatch.setattr(dashboard_module, "QVBoxLayout", _FakeLayout)
    monkeypatch.setattr(dashboard_module, "QTextEdit", _FakeTextEdit)
    monkeypatch.setattr(dashboard_module, "QTimer", _FakeTimer)
    monkeypatch.setattr(dashboard_module, "QDialogButtonBox", _FakeDialogButtonBox)

    dashboard._open_running_strategies_dialog()

    assert _FakeDialog.instances[-1].window_title == "STRATEGIES RUNNING"
    assert _FakeDialog.instances[-1].minimum_size == (620, 420)
    assert _FakeTextEdit.instances[-1].read_only is True
    assert _FakeTextEdit.instances[-1].html_history == ["<p>first</p>", "<p>second</p>"]
    assert _FakeTimer.instances[-1].interval_ms == 5000
    assert _FakeTimer.instances[-1].stopped is True
