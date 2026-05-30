#!/usr/bin/env python3
"""Focused tests for R12 paper ExitMonitor authoritative-position wiring."""

from __future__ import annotations

from datetime import datetime, timedelta
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from Spyder.SpyderA_Core.SpyderA05_EventManager import EventType
from Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor import create_exit_monitor
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor


def test_r12_start_exit_monitor_uses_engine_positions_for_paper(monkeypatch) -> None:
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    monkeypatch.setattr(
        "Spyder.SpyderP_PortfolioMgmt.get_global_portfolio_manager",
        lambda: None,
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor.ExitMonitor.start",
        lambda self: True,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = SimpleNamespace()
    supervisor.orchestrator = SimpleNamespace(active_strategies={"iron_condor": strategy})
    supervisor.engine = SimpleNamespace(
        portfolio_manager=None,
        active_positions={
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy": "iron_condor",
            }
        },
        _is_market_open=lambda: True,
        _active_positions_lock=threading.Lock(),
    )

    supervisor._start_exit_monitor()

    assert supervisor.exit_monitor is not None

    supervisor.exit_monitor._sweep_once()

    strategy.check_exit.assert_called_once()
    position_view = strategy.check_exit.call_args.args[0]
    assert position_view.strategy_id == "iron_condor"
    assert position_view.cost_basis == 3.50
    assert position_view.current_price == 3.60
    assert supervisor.exit_monitor.portfolio_manager is None


def test_r12_start_exit_monitor_suppresses_paper_positions_after_hours(monkeypatch) -> None:
    strategy = MagicMock()
    strategy.check_exit.return_value = None

    monkeypatch.setattr(
        "Spyder.SpyderP_PortfolioMgmt.get_global_portfolio_manager",
        lambda: None,
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor.ExitMonitor.start",
        lambda self: True,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = SimpleNamespace()
    supervisor.orchestrator = SimpleNamespace(active_strategies={"iron_condor": strategy})
    supervisor.engine = SimpleNamespace(
        portfolio_manager=None,
        active_positions={
            "SPY260620P00500000": {
                "symbol": "SPY260620P00500000",
                "quantity": -1,
                "entry_price": 3.50,
                "current_price": 3.60,
                "strategy": "iron_condor",
            }
        },
        _is_market_open=lambda: False,
        _active_positions_lock=threading.Lock(),
    )

    supervisor._start_exit_monitor()

    assert supervisor.exit_monitor is not None

    supervisor.exit_monitor._sweep_once()

    strategy.check_exit.assert_not_called()


def test_r12_start_exit_monitor_surfaces_zero_dte_positions_after_hours_for_force_close(
    monkeypatch,
) -> None:
    strategy = MagicMock()
    strategy.check_exit.return_value = None
    risk_alert_event_type = getattr(EventType, "RISK_ALERT", EventType.ALERT)

    monkeypatch.setattr(
        "Spyder.SpyderP_PortfolioMgmt.get_global_portfolio_manager",
        lambda: None,
    )
    monkeypatch.setattr(
        "Spyder.SpyderR_Runtime.SpyderR14_ExitMonitor.ExitMonitor.start",
        lambda self: True,
    )

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.em = _ExitEventManagerStub()
    supervisor.orchestrator = SimpleNamespace(active_strategies={"butterfly": strategy})
    supervisor._now_et = lambda: datetime(2026, 5, 28, 16, 15, 0, tzinfo=ZoneInfo("America/New_York"))
    supervisor.engine = SimpleNamespace(
        portfolio_manager=None,
        active_positions={
            "SPY260528C00754000": {
                "symbol": "SPY260528C00754000",
                "quantity": -9,
                "entry_price": 0.92,
                "current_price": 0.81,
                "unrealized_pnl": -301.05,
                "strategy": "butterfly",
            },
            "SPY260528C00756000": {
                "symbol": "SPY260528C00756000",
                "quantity": 3,
                "entry_price": 0.05,
                "current_price": 0.10,
                "unrealized_pnl": 7.50,
                "strategy": "butterfly",
            },
        },
        _is_market_open=lambda: False,
        _active_positions_lock=threading.Lock(),
    )

    supervisor._start_exit_monitor()

    assert supervisor.exit_monitor is not None
    supervisor.exit_monitor._now_et = lambda: datetime(
        2026,
        5,
        28,
        16,
        15,
        0,
        tzinfo=ZoneInfo("America/New_York"),
    )

    supervisor.exit_monitor._sweep_once()

    strategy.check_exit.assert_not_called()
    assert [event["event_type"] for event in supervisor.em.emitted] == [
        risk_alert_event_type,
        EventType.FLATTEN_REQUEST,
    ]
    assert supervisor.em.emitted[0]["data"] == {
        "severity": "warning",
        "reason": "zero_dte_eod_force_close",
        "message": "0DTE paper options still open after 15:55 ET (2)",
        "detail": "SPY260528C00754000, SPY260528C00756000",
        "symbols": [
            "SPY260528C00754000",
            "SPY260528C00756000",
        ],
        "cutoff_et": "15:55 ET",
    }
    assert supervisor.em.emitted[1]["data"] == {
        "type": "symbols_flatten",
        "reason": "zero_dte_eod_force_close",
        "symbols": [
            "SPY260528C00754000",
            "SPY260528C00756000",
        ],
    }


class _ExitEventManagerStub:
    def __init__(self) -> None:
        self.emitted: list[dict[str, object]] = []

    def emit(self, **kwargs) -> None:  # noqa: ANN003
        self.emitted.append(kwargs)


def test_exit_monitor_requests_group_flatten_for_orphaned_hydrated_paper_condor() -> None:
    event_manager = _ExitEventManagerStub()
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260618P00690000": {
                "symbol": "SPY260618P00690000",
                "quantity": 1,
                "entry_price": 4.22,
                "current_price": 4.22,
                "unrealized_pnl": -167.21,
                "strategy_id": "iron_condor",
                "position_source": "session_db_hydration",
            }
        },
    )

    monitor._sweep_once()

    assert len(event_manager.emitted) == 2
    orphan_event = event_manager.emitted[0]
    flatten_event = event_manager.emitted[1]
    assert orphan_event["event_type"] == EventType.RISK_VIOLATION
    assert orphan_event["data"]["type"] == "ORPHAN_POSITION"
    assert flatten_event["event_type"] == EventType.FLATTEN_REQUEST
    assert flatten_event["data"] == {
        "type": "strategy_group_flatten",
        "reason": "paper_orphan_carryover_strategy",
        "strategy_id": "iron_condor",
    }


def test_exit_monitor_ignores_expected_hydrated_butterfly_carryover_orphan() -> None:
    event_manager = _ExitEventManagerStub()
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260626C00748000": {
                "symbol": "SPY260626C00748000",
                "quantity": 8,
                "entry_price": 3.14,
                "current_price": 3.14,
                "unrealized_pnl": -1717.28,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "expiration": "2026-06-26",
            }
        },
    )

    monitor._sweep_once()

    assert event_manager.emitted == []


def test_exit_monitor_requests_group_flatten_for_expiring_hydrated_butterfly_carryover() -> None:
    event_manager = _ExitEventManagerStub()
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260528C00748000": {
                "symbol": "SPY260528C00748000",
                "quantity": 8,
                "entry_price": 3.14,
                "current_price": 3.14,
                "unrealized_pnl": 245.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "expiration": "2026-05-28",
            }
        },
    )
    monitor._now_et = lambda: datetime(2026, 5, 28, 15, 30, 0, tzinfo=ZoneInfo("America/New_York"))

    monitor._sweep_once()

    assert len(event_manager.emitted) == 2
    orphan_event = event_manager.emitted[0]
    flatten_event = event_manager.emitted[1]
    assert orphan_event["event_type"] == EventType.RISK_VIOLATION
    assert orphan_event["data"]["type"] == "ORPHAN_POSITION"
    assert flatten_event["event_type"] == EventType.FLATTEN_REQUEST
    assert flatten_event["data"] == {
        "type": "strategy_group_flatten",
        "reason": "paper_orphan_carryover_strategy",
        "strategy_id": "butterfly",
    }


def test_exit_monitor_ignores_active_session_hydrated_butterfly_restart_orphan() -> None:
    event_manager = _ExitEventManagerStub()
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260529C00756000": {
                "symbol": "SPY260529C00756000",
                "quantity": 8,
                "entry_price": 1.54,
                "current_price": 1.54,
                "unrealized_pnl": -8.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "_paper_open_origin": "active_session",
                "expiration": "2026-05-29",
            }
        },
    )
    monitor._now_et = lambda: datetime(2026, 5, 29, 12, 11, 52, tzinfo=ZoneInfo("America/New_York"))

    monitor._sweep_once()

    assert event_manager.emitted == []


def test_exit_monitor_suppresses_close_after_group_flatten_request_for_same_hydrated_leg() -> None:
    event_manager = _ExitEventManagerStub()
    positions = {
        "SPY260618P00704000": {
            "symbol": "SPY260618P00704000",
            "quantity": -1,
            "entry_price": 4.24,
            "current_price": 3.99,
            "unrealized_pnl": 450.92,
            "strategy_id": "iron_condor",
            "position_source": "session_db_hydration",
        }
    }
    strategy = MagicMock()
    strategy.check_exit.return_value = "close"

    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={},
        event_manager=event_manager,
        positions_provider=lambda: positions,
    )

    monitor._sweep_once()

    monitor.register_strategy("iron_condor", strategy)
    monitor._sweep_once()

    strategy.check_exit.assert_not_called()
    assert [event["event_type"] for event in event_manager.emitted] == [
        EventType.RISK_VIOLATION,
        EventType.FLATTEN_REQUEST,
    ]


def test_exit_monitor_requests_symbols_flatten_for_profitable_active_butterfly_family() -> None:
    event_manager = _ExitEventManagerStub()
    strategy = MagicMock()
    strategy.should_close_butterfly.return_value = (False, "hold")
    strategy.check_exit.return_value = None

    expiration = "2026-05-28"
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"butterfly": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260528C00598000": {
                "symbol": "SPY260528C00598000",
                "quantity": 1,
                "entry_price": 1.54,
                "current_price": 1.90,
                "unrealized_pnl": 36.0,
                "strategy_id": "butterfly",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 598.0,
                "option_type": "call",
            },
            "SPY260528C00599000": {
                "symbol": "SPY260528C00599000",
                "quantity": -2,
                "entry_price": 0.94,
                "current_price": 0.70,
                "unrealized_pnl": 48.0,
                "strategy_id": "butterfly",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 599.0,
                "option_type": "call",
            },
            "SPY260528C00600000": {
                "symbol": "SPY260528C00600000",
                "quantity": 1,
                "entry_price": 0.69,
                "current_price": 0.82,
                "unrealized_pnl": 13.0,
                "strategy_id": "butterfly",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 600.0,
                "option_type": "call",
            },
        },
    )
    monitor._now_et = lambda: datetime(2026, 5, 28, 15, 30, 0, tzinfo=ZoneInfo("America/New_York"))

    monitor._sweep_once()

    strategy.should_close_butterfly.assert_called_once()
    assert event_manager.emitted == []


def test_exit_monitor_requests_symbols_flatten_for_profitable_hydrated_butterfly_family() -> None:
    event_manager = _ExitEventManagerStub()
    strategy = MagicMock()
    strategy.should_close_butterfly.return_value = (False, "hold")
    strategy.check_exit.return_value = None

    expiration = datetime.now().date().isoformat()
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"butterfly": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260528C00598000": {
                "symbol": "SPY260528C00598000",
                "quantity": 1,
                "entry_price": 1.54,
                "current_price": 1.90,
                "unrealized_pnl": 36.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 598.0,
                "option_type": "call",
            },
            "SPY260528C00599000": {
                "symbol": "SPY260528C00599000",
                "quantity": -2,
                "entry_price": 0.94,
                "current_price": 0.70,
                "unrealized_pnl": 48.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 599.0,
                "option_type": "call",
            },
            "SPY260528C00600000": {
                "symbol": "SPY260528C00600000",
                "quantity": 1,
                "entry_price": 0.69,
                "current_price": 0.82,
                "unrealized_pnl": 13.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 600.0,
                "option_type": "call",
            },
        },
    )
    monitor._now_et = lambda: datetime.fromisoformat(f"{expiration}T15:30:00").replace(
        tzinfo=ZoneInfo("America/New_York")
    )

    monitor._sweep_once()

    strategy.check_exit.assert_not_called()
    strategy.should_close_butterfly.assert_not_called()
    assert len(event_manager.emitted) == 1
    flatten_event = event_manager.emitted[0]
    assert flatten_event["event_type"] == EventType.FLATTEN_REQUEST
    assert flatten_event["data"] == {
        "type": "symbols_flatten",
        "reason": "pre_carryover_profit_take",
        "symbols": [
            "SPY260528C00598000",
            "SPY260528C00599000",
            "SPY260528C00600000",
        ],
    }


def test_exit_monitor_does_not_preflatten_active_session_hydrated_butterfly_family() -> None:
    event_manager = _ExitEventManagerStub()
    strategy = MagicMock()
    strategy.should_close_butterfly.return_value = (False, "hold")
    strategy.check_exit.return_value = None

    expiration = "2026-05-29"
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"butterfly": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260529C00756000": {
                "symbol": "SPY260529C00756000",
                "quantity": 8,
                "entry_price": 1.54,
                "current_price": 1.70,
                "unrealized_pnl": 128.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "_paper_open_origin": "active_session",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 756.0,
                "option_type": "call",
            },
            "SPY260529C00757000": {
                "symbol": "SPY260529C00757000",
                "quantity": -16,
                "entry_price": 0.94,
                "current_price": 0.80,
                "unrealized_pnl": 224.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "_paper_open_origin": "active_session",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 757.0,
                "option_type": "call",
            },
            "SPY260529C00758000": {
                "symbol": "SPY260529C00758000",
                "quantity": 8,
                "entry_price": 0.52,
                "current_price": 0.60,
                "unrealized_pnl": 64.0,
                "strategy_id": "butterfly",
                "position_source": "session_db_hydration",
                "_paper_open_origin": "active_session",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 758.0,
                "option_type": "call",
            },
        },
    )
    monitor._now_et = lambda: datetime(2026, 5, 29, 12, 11, 52, tzinfo=ZoneInfo("America/New_York"))

    monitor._sweep_once()

    strategy.should_close_butterfly.assert_called_once()
    assert event_manager.emitted == []


def test_exit_monitor_uses_butterfly_helper_for_future_dated_group_exit() -> None:
    event_manager = _ExitEventManagerStub()
    strategy = MagicMock()
    strategy.should_close_butterfly.return_value = (True, "profit_target")

    expiration_date = datetime.now().date() + timedelta(days=1)
    expiration = expiration_date.isoformat()
    expiry_code = expiration_date.strftime("%y%m%d")
    lower_symbol = f"SPY{expiry_code}C00598000"
    body_symbol = f"SPY{expiry_code}C00599000"
    upper_symbol = f"SPY{expiry_code}C00600000"

    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"butterfly": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            lower_symbol: {
                "symbol": lower_symbol,
                "quantity": 1,
                "entry_price": 1.54,
                "current_price": 1.92,
                "unrealized_pnl": 38.0,
                "strategy_id": "butterfly",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 598.0,
                "option_type": "call",
            },
            body_symbol: {
                "symbol": body_symbol,
                "quantity": -2,
                "entry_price": 0.94,
                "current_price": 0.68,
                "unrealized_pnl": 52.0,
                "strategy_id": "butterfly",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 599.0,
                "option_type": "call",
            },
            upper_symbol: {
                "symbol": upper_symbol,
                "quantity": 1,
                "entry_price": 0.69,
                "current_price": 0.84,
                "unrealized_pnl": 15.0,
                "strategy_id": "butterfly",
                "underlying_symbol": "SPY",
                "expiration": expiration,
                "strike": 600.0,
                "option_type": "call",
            },
        },
    )

    monitor._sweep_once()

    strategy.should_close_butterfly.assert_called_once()
    group_data = strategy.should_close_butterfly.call_args.args[0]
    assert group_data["entry_notional"] > 0.0
    assert group_data["quantity"] == 1
    assert group_data["days_to_expiry"] == 1
    assert group_data["pnl_percent"] > 0.0
    assert len(event_manager.emitted) == 1
    flatten_event = event_manager.emitted[0]
    assert flatten_event["event_type"] == EventType.FLATTEN_REQUEST
    assert flatten_event["data"] == {
        "type": "symbols_flatten",
        "reason": "profit_target",
        "symbols": [lower_symbol, body_symbol, upper_symbol],
    }


def test_exit_monitor_requests_symbols_flatten_for_partial_zero_dte_option_group_after_1555_et() -> None:
    event_manager = _ExitEventManagerStub()
    strategy = MagicMock()
    strategy.check_exit.return_value = None
    risk_alert_event_type = getattr(EventType, "RISK_ALERT", EventType.ALERT)

    cutoff_time = datetime(2026, 5, 28, 15, 55, 1, tzinfo=ZoneInfo("America/New_York"))
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"butterfly": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260528C00754000": {
                "symbol": "SPY260528C00754000",
                "quantity": -9,
                "entry_price": 0.92,
                "current_price": 0.81,
                "unrealized_pnl": 94.95,
                "strategy_id": "butterfly",
            },
            "SPY260528C00756000": {
                "symbol": "SPY260528C00756000",
                "quantity": 3,
                "entry_price": 0.05,
                "current_price": 0.10,
                "unrealized_pnl": -1.50,
                "strategy_id": "butterfly",
            },
        },
    )
    monitor._now_et = lambda: cutoff_time

    monitor._sweep_once()

    strategy.check_exit.assert_not_called()
    assert len(event_manager.emitted) == 2
    risk_alert_event = event_manager.emitted[0]
    flatten_event = event_manager.emitted[1]
    assert risk_alert_event["event_type"] == risk_alert_event_type
    assert risk_alert_event["data"] == {
        "severity": "warning",
        "reason": "zero_dte_eod_force_close",
        "message": "0DTE paper options still open after 15:55 ET (2)",
        "detail": "SPY260528C00754000, SPY260528C00756000",
        "symbols": [
            "SPY260528C00754000",
            "SPY260528C00756000",
        ],
        "cutoff_et": "15:55 ET",
    }
    assert flatten_event["event_type"] == EventType.FLATTEN_REQUEST
    assert flatten_event["data"] == {
        "type": "symbols_flatten",
        "reason": "zero_dte_eod_force_close",
        "symbols": [
            "SPY260528C00754000",
            "SPY260528C00756000",
        ],
    }


def test_exit_monitor_suppresses_duplicate_zero_dte_force_flatten_requests_while_in_flight() -> None:
    event_manager = _ExitEventManagerStub()
    strategy = MagicMock()
    strategy.check_exit.return_value = None
    risk_alert_event_type = getattr(EventType, "RISK_ALERT", EventType.ALERT)

    cutoff_time = datetime(2026, 5, 28, 15, 55, 1, tzinfo=ZoneInfo("America/New_York"))
    monitor = create_exit_monitor(
        portfolio_manager=None,
        strategy_map={"butterfly": strategy},
        event_manager=event_manager,
        positions_provider=lambda: {
            "SPY260528C00754000": {
                "symbol": "SPY260528C00754000",
                "quantity": -9,
                "entry_price": 0.92,
                "current_price": 0.81,
                "unrealized_pnl": 94.95,
                "strategy_id": "butterfly",
            },
            "SPY260528C00756000": {
                "symbol": "SPY260528C00756000",
                "quantity": 3,
                "entry_price": 0.05,
                "current_price": 0.10,
                "unrealized_pnl": -1.50,
                "strategy_id": "butterfly",
            },
        },
    )
    monitor._now_et = lambda: cutoff_time

    monitor._sweep_once()
    monitor._sweep_once()

    strategy.check_exit.assert_not_called()
    assert len(event_manager.emitted) == 2
    assert event_manager.emitted[0]["event_type"] == risk_alert_event_type
    assert event_manager.emitted[1]["event_type"] == EventType.FLATTEN_REQUEST


def test_r12_flatten_positions_evicts_verified_symbol_from_engine_active_positions() -> None:
    """R12 _flatten_positions must evict each verified close from engine.active_positions.

    Without this eviction, ExitMonitor reads stale data (FillReconciler is never
    called for the flatten path) and re-dispatches duplicate close signals.
    """
    symbol = "SPY260618P00704000"

    # Minimal broker stub that returns a verified close result.
    class _VerifiedBroker:
        def close_position(self, sym, **_kw):
            return {"order": {"order": {"id": "PAPER-000042"}}}

        def close_position_verified(self, sym, **_kw):
            return {
                "status": "verified",
                "order": {"order": {"id": "PAPER-000042"}},
            }

        def get_positions(self):
            return [{"symbol": symbol, "quantity": -1, "strategy_id": "iron_condor"}]

    lock = threading.Lock()
    active_positions = {
        symbol: {
            "symbol": symbol,
            "quantity": -1,
            "entry_price": 4.24,
            "strategy": "iron_condor",
        }
    }

    supervisor = SessionSupervisor(mode="paper", dry_run=True, skip_orphan_sweep=True)
    supervisor.broker = _VerifiedBroker()
    supervisor.engine = SimpleNamespace(
        _active_positions_lock=lock,
        active_positions=active_positions,
        get_active_positions_snapshot=lambda: [
            {"symbol": symbol, "quantity": -1, "strategy_id": "iron_condor"}
        ],
    )

    closed = supervisor._flatten_positions(reason="test_flatten")

    assert closed == 1, "expected one verified close"
    assert symbol not in active_positions, (
        "engine.active_positions must be cleared after a verified flatten so "
        "ExitMonitor does not re-fire a duplicate close"
    )
