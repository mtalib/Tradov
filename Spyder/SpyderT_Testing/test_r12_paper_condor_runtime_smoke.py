"""Focused runtime smoke for paper iron-condor persistence and rendering."""

from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6.QtWidgets", reason="PySide6 required for paper carryover GUI smoke")

from PySide6.QtWidgets import QApplication, QLabel, QTreeWidget

# Ensure canonical Spyder imports resolve to this repository in CI.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_ROOT = _REPO_ROOT / "Spyder"
for _path in (_REPO_ROOT, _PACKAGE_ROOT):
    _path_str = str(_path)
    if _path_str not in sys.path:
        sys.path.insert(0, _path_str)


def _is_local_spyder_package(module: object) -> bool:
    if not hasattr(module, "__path__"):
        return False
    package_root = str(_PACKAGE_ROOT)
    module_file = str(getattr(module, "__file__", "") or "")
    if module_file.startswith(package_root):
        return True
    module_paths = [str(path) for path in getattr(module, "__path__", [])]
    return any(path.startswith(package_root) for path in module_paths)


def _ensure_local_spyder_package() -> None:
    existing_spyder = sys.modules.get("Spyder")
    if existing_spyder is not None and _is_local_spyder_package(existing_spyder):
        return

    sys.modules.pop("Spyder", None)
    importlib.invalidate_caches()

    spec = importlib.util.spec_from_file_location(
        "Spyder",
        _PACKAGE_ROOT / "__init__.py",
        submodule_search_locations=[str(_PACKAGE_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load Spyder package from {_PACKAGE_ROOT}")

    module = importlib.util.module_from_spec(spec)
    sys.modules["Spyder"] = module
    spec.loader.exec_module(module)


_ensure_local_spyder_package()

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import TradingMode
from Spyder.SpyderH_Storage.SpyderH05_TradingSessionDB import TradingSessionDB
from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import LiveEngine
from Spyder.SpyderR_Runtime.SpyderR04_LiveEngine import ExecutionState
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import SessionSupervisor
from Spyder.SpyderR_Runtime.SpyderR12_SessionSupervisor import authorize_paper_session_start
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


@pytest.fixture(autouse=True)
def _sandbox_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SPYDER_TRADING_MODE", "paper")
    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("TRADIER_ENVIRONMENT", "live")
    monkeypatch.setenv("TRADIER_MARKET_DATA_ENVIRONMENT", "live")
    monkeypatch.delenv("SPYDER_ALLOW_SANDBOX_MARKET_DATA", raising=False)
    monkeypatch.setenv("SPYDER_D31_SIGNAL_DROP_AUDIT_DIR", str(tmp_path))
    (tmp_path / ".spyder").mkdir(parents=True, exist_ok=True)
    yield


def _build_dashboard_stub(session_db: TradingSessionDB) -> SpyderTradingDashboard:
    QApplication.instance() or QApplication([])
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash.trading_mode = TradingMode.PAPER
    dash.positions_table = QTreeWidget()
    dash.positions_table.setColumnCount(8)
    dash.orders_title_label = QLabel("Orders")
    dash._paper_session_db = session_db
    dash._live_session_db = None
    dash._session_db_init_failed_by_mode = {}
    dash.add_system_log = lambda _msg: None
    dash._get_mode_session_db = lambda: session_db
    return dash


def test_r12_paper_condor_dispatch_persists_and_renders_restored_group(tmp_path, monkeypatch):
    paper_db_path = tmp_path / "data" / "spyder_paper_smoke.db"
    paper_db_path.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(SessionSupervisor, "_start_data_feed", lambda self: True)
    monkeypatch.setattr(SessionSupervisor, "_start_freshness_monitor", lambda self: True)
    monkeypatch.setattr(SessionSupervisor, "_start_exit_monitor", lambda self: None)
    monkeypatch.setattr(SessionSupervisor, "_start_liveness_monitor", lambda self: None)
    monkeypatch.setattr(SessionSupervisor, "_boot_orphan_sweep", lambda self: None)
    monkeypatch.setattr(SessionSupervisor, "_run_boot_self_test", lambda self, timeout_seconds=3.0: True)
    monkeypatch.setattr(LiveEngine, "_is_market_open", lambda self: True)

    supervisor = SessionSupervisor(mode="paper")
    authorize_paper_session_start(supervisor)
    expected_quantities = {
        "SPY260515P00565000": 1,
        "SPY260515P00570000": -1,
        "SPY260515C00580000": -1,
        "SPY260515C00585000": 1,
    }
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
        return_value=TradingSessionDB(paper_db_path),
    ):
        try:
            assert supervisor.start() is True
            assert supervisor.engine is not None
            assert supervisor.orchestrator is not None
            assert supervisor.engine.state == ExecutionState.TRADING

            supervisor.engine._is_trading_allowed = lambda: True
            supervisor.orchestrator._build_paper_iron_condor_leg_orders = (
                lambda *args, **kwargs: list(leg_orders)
            )

            signal = {
                "strategy_id": "iron_condor",
                "strategy_type": "iron_condor",
                "symbol": "SPY",
                "action": "sell",
                "quantity": 1,
                "price": 2.15,
                "confidence": 0.8,
            }
            supervisor.orchestrator._dispatch_approved_signal(signal)

            session_db = TradingSessionDB(paper_db_path)
            trades = []
            positions = []
            deadline = time.monotonic() + 6.0
            while time.monotonic() < deadline:
                trades = list(session_db.get_trades_today() or [])
                positions = list(session_db.get_open_positions() or [])
                if len(trades) >= 4 and len(positions) >= 4:
                    break
                time.sleep(0.1)

            assert len(trades) == 4
            assert len(positions) == 4
            assert {
                str(row.get("symbol") or ""): int(row.get("quantity") or 0)
                for row in positions
            } == expected_quantities

            assert session_db.get_resume_eligible_open_positions() == []

            supervisor.stop(flatten=False)

            session_db = TradingSessionDB(paper_db_path)
            resumable_positions = list(session_db.get_resume_eligible_open_positions() or [])
            assert len(resumable_positions) == 4

            dash = _build_dashboard_stub(session_db)
            dash._render_paper_spreads_in_tree([], armed_candidate=None)

            assert dash.positions_table.topLevelItemCount() == 5
            summary = dash.positions_table.topLevelItem(0)
            summary_widget = dash.positions_table.itemWidget(summary, 0)
            assert summary_widget is not None
            label_texts = [label.text() for label in summary_widget.findChildren(QLabel)]
            assert any("ACTIVE TRADE CARRIED OVER : IRON CONDOR" in text for text in label_texts)

            leg_labels = [
                dash.positions_table.topLevelItem(index).text(0).strip()
                for index in range(1, 5)
            ]
            assert leg_labels == ["Sell Put", "Buy Put", "Sell Call", "Buy Call"]
        finally:
            if getattr(supervisor, "_running", False):
                supervisor.stop(flatten=False)
