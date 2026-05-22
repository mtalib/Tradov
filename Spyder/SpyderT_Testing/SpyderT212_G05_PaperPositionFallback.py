#!/usr/bin/env python3
"""Focused regression for paper-mode position fallback in G05."""

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTreeWidget

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _PaperSessionDB:
    def get_resume_eligible_open_positions(self):
        return self.get_open_positions()

    def get_open_positions(self):
        return [
            {
                "symbol": "SPY",
                "quantity": -4,
                "entry_price": 733.10,
                "current_price": 733.25,
                "unrealized_pnl": -60.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:30+00:00",
            }
        ]


class _PaperCondorSessionDB:
    def get_resume_eligible_open_positions(self):
        return self.get_open_positions()

    def get_open_positions(self):
        return [
            {
                "position_id": "paper:SPY260515P00565000",
                "symbol": "SPY260515P00565000",
                "quantity": 1,
                "entry_price": 0.45,
                "current_price": 0.40,
                "unrealized_pnl": -5.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:30+00:00",
                "expiration": "2026-05-15",
                "strike": 565.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260515P00570000",
                "symbol": "SPY260515P00570000",
                "quantity": -1,
                "entry_price": 1.25,
                "current_price": 1.10,
                "unrealized_pnl": 15.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:30+00:00",
                "expiration": "2026-05-15",
                "strike": 570.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260515C00580000",
                "symbol": "SPY260515C00580000",
                "quantity": -1,
                "entry_price": 1.30,
                "current_price": 1.45,
                "unrealized_pnl": -15.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:31+00:00",
                "expiration": "2026-05-15",
                "strike": 580.0,
                "option_type": "call",
            },
            {
                "position_id": "paper:SPY260515C00585000",
                "symbol": "SPY260515C00585000",
                "quantity": 1,
                "entry_price": 0.55,
                "current_price": 0.50,
                "unrealized_pnl": 5.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:31+00:00",
                "expiration": "2026-05-15",
                "strike": 585.0,
                "option_type": "call",
            },
        ]


class _UnsignedPaperCondorSessionDB:
    def get_resume_eligible_open_positions(self):
        return self.get_open_positions()

    def get_open_positions(self):
        return [
            {
                "position_id": "paper:SPY260515P00565000",
                "symbol": "SPY260515P00565000",
                "quantity": 1,
                "side": "buy_to_open",
                "entry_price": 0.45,
                "current_price": 0.40,
                "unrealized_pnl": -5.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:30+00:00",
                "expiration": "2026-05-15",
                "strike": 565.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260515P00570000",
                "symbol": "SPY260515P00570000",
                "quantity": 1,
                "side": "sell_to_open",
                "entry_price": 1.25,
                "current_price": 1.10,
                "unrealized_pnl": 15.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:30+00:00",
                "expiration": "2026-05-15",
                "strike": 570.0,
                "option_type": "put",
            },
            {
                "position_id": "paper:SPY260515C00580000",
                "symbol": "SPY260515C00580000",
                "quantity": 1,
                "side": "sell_to_open",
                "entry_price": 1.30,
                "current_price": 1.45,
                "unrealized_pnl": -15.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:31+00:00",
                "expiration": "2026-05-15",
                "strike": 580.0,
                "option_type": "call",
            },
            {
                "position_id": "paper:SPY260515C00585000",
                "symbol": "SPY260515C00585000",
                "quantity": 1,
                "side": "buy_to_open",
                "entry_price": 0.55,
                "current_price": 0.50,
                "unrealized_pnl": 5.0,
                "strategy": "iron_condor",
                "status": "OPEN",
                "opened_at": "2026-05-12T15:12:31+00:00",
                "expiration": "2026-05-15",
                "strike": 585.0,
                "option_type": "call",
            },
        ]


class _StalePaperSessionDB(_PaperCondorSessionDB):
    def get_resume_eligible_open_positions(self):
        return []


class _ActivePaperSessionDB(_PaperCondorSessionDB):
    def get_resume_eligible_open_positions(self):
        return []

    def get_active_paper_open_positions(self):
        rows = []
        for row in self.get_open_positions():
            row_copy = dict(row)
            row_copy["_paper_open_origin"] = "active_session"
            rows.append(row_copy)
        return rows


class _PartialActivePaperSessionDB(_ActivePaperSessionDB):
    def get_open_positions(self):
        return super().get_open_positions()[:3]


def _build_dashboard_stub(session_db=None, *, trading_active: bool = False) -> SpyderTradingDashboard:
    QApplication.instance() or QApplication([])
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash.trading_active = trading_active
    dash.positions_table = QTreeWidget()
    dash.positions_table.setColumnCount(9)
    dash.orders_title_label = QLabel("Orders")
    dash._portfolio_summary_cache = None
    dash._paper_session_db = None
    dash._live_session_db = None
    dash._session_db_init_failed_by_mode = {}
    dash.add_system_log = lambda _msg: None
    dash._get_mode_session_db = lambda: session_db or _PaperSessionDB()
    return dash


def test_render_paper_spreads_in_tree_falls_back_to_session_positions() -> None:
    dash = _build_dashboard_stub()

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 2
    summary = dash.positions_table.topLevelItem(0)
    detail = dash.positions_table.topLevelItem(1)

    assert "ACTIVE PAPER POSITION (CARRIED OVER) : IRON CONDOR" in summary.text(0)
    assert "STATUS: OPEN" in summary.text(0)
    assert detail.text(0) == "SELL"
    assert detail.text(1) == "SPY"
    assert detail.text(2) == "--"
    assert detail.text(3) == "4"
    assert detail.text(4) == "$733.10"
    assert detail.text(5) == "-$2,932.40"
    assert detail.text(6) == "--"
    assert detail.text(7) == "-$60.00"


def test_render_paper_spreads_in_tree_groups_restored_condor_legs() -> None:
    dash = _build_dashboard_stub(session_db=_PaperCondorSessionDB())

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 5

    summary = dash.positions_table.topLevelItem(0)
    summary_widget = dash.positions_table.itemWidget(summary, 0)
    assert summary_widget is not None
    assert summary_widget.minimumHeight() == 22
    label_texts = [label.text() for label in summary_widget.findChildren(QLabel)]
    assert any("ACTIVE TRADE CARRIED OVER : IRON CONDOR" in text for text in label_texts)
    close_buttons = summary_widget.findChildren(QPushButton)
    assert len(close_buttons) == 1
    assert close_buttons[0].width() == 20
    assert close_buttons[0].height() == 20

    action_labels = [dash.positions_table.topLevelItem(i).text(0) for i in range(1, 5)]
    assert action_labels == ["SELL PUT", "BUY PUT", "SELL CALL", "BUY CALL"]
    assert dash.positions_table.topLevelItem(1).text(1) == "SPY260515P00570000"
    assert dash.positions_table.topLevelItem(1).text(2) == "$570P"
    assert dash.positions_table.topLevelItem(1).text(4) == "$1.25"
    assert dash.positions_table.topLevelItem(1).text(5) == "-$125"
    assert dash.positions_table.topLevelItem(2).text(1) == "SPY260515P00565000"
    assert dash.positions_table.topLevelItem(3).text(1) == "SPY260515C00580000"
    assert dash.positions_table.topLevelItem(4).text(1) == "SPY260515C00585000"


def test_render_paper_spreads_in_tree_rebuilds_unsigned_condor_legs_from_side_data() -> None:
    dash = _build_dashboard_stub(session_db=_UnsignedPaperCondorSessionDB())

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 5

    summary = dash.positions_table.topLevelItem(0)
    summary_widget = dash.positions_table.itemWidget(summary, 0)
    assert summary_widget is not None
    label_texts = [label.text() for label in summary_widget.findChildren(QLabel)]
    assert any("ACTIVE TRADE CARRIED OVER : IRON CONDOR" in text for text in label_texts)
    assert any("NET P&L" in text for text in label_texts)

    action_labels = [dash.positions_table.topLevelItem(i).text(0) for i in range(1, 5)]
    assert action_labels == ["SELL PUT", "BUY PUT", "SELL CALL", "BUY CALL"]


def test_render_paper_spreads_in_tree_ignores_stale_session_rows_without_manifest_match() -> None:
    dash = _build_dashboard_stub(session_db=_StalePaperSessionDB())

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 1
    assert dash.positions_table.topLevelItem(0).text(0) == "Paper trading - no open spreads"


def test_render_paper_spreads_in_tree_uses_active_session_rows_while_paper_session_active() -> None:
    dash = _build_dashboard_stub(session_db=_ActivePaperSessionDB(), trading_active=True)

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 5

    summary = dash.positions_table.topLevelItem(0)
    summary_widget = dash.positions_table.itemWidget(summary, 0)
    assert summary_widget is not None
    label_texts = [label.text() for label in summary_widget.findChildren(QLabel)]
    assert any("STRATEGY EXECUTING : IRON CONDOR" in text for text in label_texts)


def test_render_paper_spreads_in_tree_falls_back_to_open_rows_without_manifest_api() -> None:
    class _LegacyPaperSessionDB(_PaperCondorSessionDB):
        get_resume_eligible_open_positions = None

    dash = _build_dashboard_stub(session_db=_LegacyPaperSessionDB(), trading_active=True)

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 5

    summary = dash.positions_table.topLevelItem(0)
    summary_widget = dash.positions_table.itemWidget(summary, 0)
    assert summary_widget is not None
    label_texts = [label.text() for label in summary_widget.findChildren(QLabel)]
    assert any("STRATEGY EXECUTING : IRON CONDOR" in text for text in label_texts)


def test_render_paper_spreads_in_tree_groups_partial_active_rows_under_one_header() -> None:
    dash = _build_dashboard_stub(session_db=_PartialActivePaperSessionDB(), trading_active=True)

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 4

    summary = dash.positions_table.topLevelItem(0)
    assert "ACTIVE PAPER POSITION (EXECUTING) : IRON CONDOR" in summary.text(0)
    assert "TRADES: 3" in summary.text(0)

    labels = [dash.positions_table.topLevelItem(i).text(1) for i in range(1, 4)]
    assert labels == [
        "SPY260515P00565000",
        "SPY260515P00570000",
        "SPY260515C00580000",
    ]


def test_refresh_positions_table_prefers_saved_state_over_placeholder_cache() -> None:
    dash = _build_dashboard_stub()
    dash._portfolio_summary_cache = {
        "open_spreads_detail": [],
        "spreads_unrealized_pnl": 0.0,
        "closed_trades": [],
        "equity": 0.0,
        "cash": 0.0,
        "unrealized_pnl": 0.0,
        "realized_pnl": 0.0,
    }
    hydrated = {
        "open_spreads_detail": [{"id": 1, "structure": "iron_condor"}],
        "spreads_unrealized_pnl": 54.0,
        "closed_trades": [],
        "equity": 100054.0,
        "cash": 100000.0,
        "unrealized_pnl": 54.0,
        "realized_pnl": 0.0,
    }
    dash._load_cached_paper_state_payload = MagicMock(return_value=hydrated)
    dash._refresh_spreads_panel = MagicMock()
    dash._set_spyderbox_account_panel_values = MagicMock()
    dash.add_system_log = MagicMock()

    dash._refresh_positions_table()

    dash._load_cached_paper_state_payload.assert_called_once_with()
    dash._refresh_spreads_panel.assert_called_once_with(hydrated)
    dash._set_spyderbox_account_panel_values.assert_called_once_with(
        settled=100054.0,
        buying=100000.0,
        unrealized=54.0,
        realized=0.0,
    )
    dash.add_system_log.assert_called_once_with("♻️ Loaded paper positions from saved session state")


def test_position_updated_event_schedules_paper_positions_refresh() -> None:
    dash = _build_dashboard_stub()
    dash._refresh_positions_table = MagicMock()
    event = Event(
        event_type=EventType.POSITION_UPDATED,
        source="PositionTracker",
        data={"symbol": "SPY", "quantity": -1, "fill_price": 733.8771},
    )

    with patch(
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QMetaObject.invokeMethod",
        side_effect=lambda obj, method_name, _conn: getattr(obj, method_name)(),
    ):
        dash._handle_position_updated_event(event)

    dash._refresh_positions_table.assert_called_once_with()
