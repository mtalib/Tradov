#!/usr/bin/env python3
"""Focused regression for paper-mode position fallback in G05."""

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QTreeWidget

from Spyder.SpyderA_Core.SpyderA05_EventManager import Event, EventType
from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


class _PaperSessionDB:
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


def _build_dashboard_stub(session_db=None) -> SpyderTradingDashboard:
    QApplication.instance() or QApplication([])
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash.positions_table = QTreeWidget()
    dash.positions_table.setColumnCount(6)
    dash.orders_title_label = QLabel("Orders")
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

    assert "RESTORED PAPER POSITION : IRON CONDOR" in summary.text(0)
    assert "STATUS: OPEN" in summary.text(0)
    assert detail.text(0).strip() == "SPY"
    assert detail.text(1) == "--"
    assert detail.text(2) == "-4"
    assert detail.text(3) == "--"
    assert detail.text(4) == "$733.10"
    assert detail.text(5) == "-$60.00"


def test_render_paper_spreads_in_tree_groups_restored_condor_legs() -> None:
    dash = _build_dashboard_stub(session_db=_PaperCondorSessionDB())

    dash._render_paper_spreads_in_tree([], armed_candidate=None)

    assert dash.positions_table.topLevelItemCount() == 5

    summary = dash.positions_table.topLevelItem(0)
    summary_widget = dash.positions_table.itemWidget(summary, 0)
    assert summary_widget is not None
    label_texts = [label.text() for label in summary_widget.findChildren(QLabel)]
    assert any("STRATEGY RESTORED : IRON CONDOR" in text for text in label_texts)

    leg_labels = [dash.positions_table.topLevelItem(i).text(0).strip() for i in range(1, 5)]
    assert leg_labels == ["Sell Put", "Buy Put", "Sell Call", "Buy Call"]
    assert dash.positions_table.topLevelItem(1).text(1) == "$570P"
    assert dash.positions_table.topLevelItem(2).text(1) == "$565P"
    assert dash.positions_table.topLevelItem(3).text(1) == "$580C"
    assert dash.positions_table.topLevelItem(4).text(1) == "$585C"


def test_position_updated_event_schedules_paper_positions_refresh() -> None:
    dash = _build_dashboard_stub()
    dash._refresh_positions_table = MagicMock()
    event = Event(
        event_type=EventType.POSITION_UPDATED,
        source="PositionTracker",
        data={"symbol": "SPY", "quantity": -1, "fill_price": 733.8771},
    )

    with patch(
        "Spyder.SpyderG_GUI.SpyderG05_TradingDashboard.QTimer.singleShot",
        side_effect=lambda _ms, cb: cb(),
    ):
        dash._handle_position_updated_event(event)

    dash._refresh_positions_table.assert_called_once_with()
