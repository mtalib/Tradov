#!/usr/bin/env python3
"""Focused tests for G43 custom metric detail dialog presenters."""

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch


class _BaseQtObject:
    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return None

    def __getattr__(self, _name):
        return MagicMock()


class _SignalStub:
    def connect(self, *args, **kwargs):
        return None

    def emit(self, *args, **kwargs):
        return None


class _AnyAttrModule(types.ModuleType):
    def __getattr__(self, name):
        val = _BaseQtObject
        setattr(self, name, val)
        return val


class _QtNamespace:
    def __getattr__(self, _name):
        return 0


class _QApplicationStub(_BaseQtObject):
    @classmethod
    def instance(cls):
        return None


def _install_pyside_stubs() -> None:
    qtw = _AnyAttrModule("PySide6.QtWidgets")
    qtc = _AnyAttrModule("PySide6.QtCore")
    qtg = _AnyAttrModule("PySide6.QtGui")

    for name in [
        "QApplication",
        "QDialog",
        "QDialogButtonBox",
        "QFrame",
        "QGridLayout",
        "QGroupBox",
        "QHBoxLayout",
        "QHeaderView",
        "QLabel",
        "QLineEdit",
        "QMainWindow",
        "QMenu",
        "QMessageBox",
        "QPushButton",
        "QScrollArea",
        "QSizePolicy",
        "QSplitter",
        "QTableWidget",
        "QTableWidgetItem",
        "QTextEdit",
        "QTreeWidget",
        "QTreeWidgetItem",
        "QVBoxLayout",
        "QWidget",
    ]:
        setattr(qtw, name, _BaseQtObject)
    qtw.QApplication = _QApplicationStub

    for name in [
        "QModelIndex",
        "QMetaObject",
        "QMutex",
        "QMutexLocker",
        "QObject",
        "QRect",
        "QThread",
        "QTimer",
    ]:
        setattr(qtc, name, _BaseQtObject)
    qtc.Signal = lambda *args, **kwargs: _SignalStub()
    qtc.Slot = lambda *args, **kwargs: (lambda func: func)
    qtc.Qt = _QtNamespace()

    for name in ["QBrush", "QColor", "QFont", "QPainter", "QPen", "QTextCursor"]:
        setattr(qtg, name, _BaseQtObject)

    pyside6 = _AnyAttrModule("PySide6")
    pyside6.QtWidgets = qtw
    pyside6.QtCore = qtc
    pyside6.QtGui = qtg

    sys.modules.update(
        {
            "PySide6": pyside6,
            "PySide6.QtWidgets": qtw,
            "PySide6.QtCore": qtc,
            "PySide6.QtGui": qtg,
            "PySide6.QtCharts": types.ModuleType("PySide6.QtCharts"),
            "PySide6.QtNetwork": types.ModuleType("PySide6.QtNetwork"),
        }
    )

    paper_worker = types.ModuleType(
        "Spyder.SpyderR_Runtime.SpyderR08_PaperTradingQtWorker"
    )
    paper_worker.PaperTradingQtWorker = _BaseQtObject
    sys.modules[
        "Spyder.SpyderR_Runtime.SpyderR08_PaperTradingQtWorker"
    ] = paper_worker


_install_pyside_stubs()

from Spyder.SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
from Spyder.SpyderG_GUI.SpyderG43_CustomMetricDialogPresenter import (
    build_pmr_details_html,
    build_psr_details_html,
    build_wrs_details_html,
)
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._last_custom_metrics_payload = {}
    dash._metrics_orchestrator = None
    dash.signal_panel = None
    dash.current_dialog = None
    return dash


def test_build_wrs_details_html_includes_signal_and_basket_state() -> None:
    html = build_wrs_details_html(
        {
            "wrs": 1.2142,
            "wrs_pct_rank": 83.4,
            "wrs_zscore": 1.91,
            "wrs_30d_ma": 1.1023,
            "wrs_90d_ma": 1.0445,
            "yoy_change": 9.8,
            "wrs_signal_level": "WARNING",
            "strategy_guidance": "Keep posture defensive.",
            "basket_available": ["LVMUY", "RACE", "TPR"],
            "basket_missing": ["BURBY"],
            "data_start": "2020-01-01",
            "data_end": "2026-05-14",
            "last_crossover_date": "2026-05-01",
            "last_crossover_dir": "bullish",
        }
    )

    assert "WRS — Walmart Recession Signal" in html
    assert "WARNING" in html
    assert "Keep posture defensive." in html
    assert "LVMUY, RACE, TPR" in html
    assert "BURBY" in html
    assert "83.4%" in html


def test_build_psr_details_html_includes_dual_signal_assessment() -> None:
    html = build_psr_details_html(
        {
            "psr": 2.1043,
            "psr_pct_rank": 91.2,
            "psr_zscore": 2.44,
            "psr_30d_ma": 1.9911,
            "psr_90d_ma": 1.7744,
            "psr_yoy_change": 0.3211,
            "psr_fcfs_price": 128.4,
            "psr_ezpw_price": 14.9,
            "psr_xlf_price": 42.7,
            "psr_signal_level": "CRITICAL",
            "psr_strategy_guidance": "Cut size aggressively.",
            "psr_data_start": "2018-01-01",
            "psr_data_end": "2026-05-14",
            "psr_crossover_date": "2026-04-22",
            "psr_crossover_dir": "up",
        },
        "WARNING",
        {
            "regime": "SYSTEMIC_CRISIS",
            "description": "Both signals are flashing stress.",
            "trading_bias": "Iron condors only",
            "size_multiplier": "0.40",
        },
    )

    assert "PSR — Pawn Shop Ratio" in html
    assert "CRITICAL" in html
    assert "SYSTEMIC_CRISIS" in html
    assert "Iron condors only" in html
    assert "0.40×" in html
    assert "$128.40" in html


def test_build_pmr_details_html_includes_fired_state_reasons_and_penalties() -> None:
    html = build_pmr_details_html(
        {
            "enabled": True,
            "available": True,
            "fired": True,
            "direction": "fade_resistance",
            "score": 72.4,
            "level_name": "R2",
            "level_price": 531.22,
            "atr_distance": 0.38,
            "reasons": ["RSI diverged", "Dealer gamma rolled over"],
            "penalties": ["Late-day penalty"],
        }
    )

    assert "PMR — Pivot Mean-Reversion Signal" in html
    assert "FIRED" in html
    assert "fade_resistance" in html
    assert "R2 @ 531.22" in html
    assert "RSI diverged" in html
    assert "Late-day penalty" in html
    assert "MIN_FIRE_SCORE=60" in html


def test_show_wrs_details_dialog_uses_presenter_output() -> None:
    dash = _build_dashboard_stub()
    dash._show_custom_metric_html_dialog = MagicMock()

    package = types.ModuleType("SpyderS_Signals")
    package.__path__ = []
    wrs_module = types.ModuleType("SpyderS_Signals.SpyderS12_WRSSignal")
    wrs_module.get_wrs_signal = lambda: SimpleNamespace(
        get_signal_dict=lambda: {
            "wrs_signal_level": "CAUTION",
            "basket_available": ["LVMUY"],
        }
    )
    package.SpyderS12_WRSSignal = wrs_module

    with patch.dict(
        sys.modules,
        {
            "SpyderS_Signals": package,
            "SpyderS_Signals.SpyderS12_WRSSignal": wrs_module,
        },
    ):
        dash._show_wrs_details_dialog()

    dash._show_custom_metric_html_dialog.assert_called_once()
    title, html_body = dash._show_custom_metric_html_dialog.call_args.args[:2]
    assert title == "WRS — Walmart Recession Signal (S12)"
    assert "WRS — Walmart Recession Signal" in html_body
    assert "CAUTION" in html_body


def test_show_psr_details_dialog_uses_presenter_output() -> None:
    dash = _build_dashboard_stub()
    dash._show_custom_metric_html_dialog = MagicMock()

    package = types.ModuleType("SpyderS_Signals")
    package.__path__ = []

    wrs_module = types.ModuleType("SpyderS_Signals.SpyderS12_WRSSignal")
    wrs_module.get_wrs_signal = lambda: SimpleNamespace(
        get_signal_dict=lambda: {"wrs_signal_level": "WARNING"}
    )

    psr_module = types.ModuleType("SpyderS_Signals.SpyderS13_PSRSignal")
    psr_module.get_psr_signal = lambda: SimpleNamespace(
        get_signal_dict=lambda: {"psr_signal_level": "CRITICAL"}
    )
    psr_module.interpret_dual_signal = lambda psr_level, wrs_level: {
        "regime": f"{psr_level}_{wrs_level}",
        "description": "Joined signal state",
        "trading_bias": "Defensive only",
        "size_multiplier": "0.50",
    }

    package.SpyderS12_WRSSignal = wrs_module
    package.SpyderS13_PSRSignal = psr_module

    with patch.dict(
        sys.modules,
        {
            "SpyderS_Signals": package,
            "SpyderS_Signals.SpyderS12_WRSSignal": wrs_module,
            "SpyderS_Signals.SpyderS13_PSRSignal": psr_module,
        },
    ):
        dash._show_psr_details_dialog()

    dash._show_custom_metric_html_dialog.assert_called_once()
    title, html_body = dash._show_custom_metric_html_dialog.call_args.args[:2]
    assert title == "PSR — Pawn Shop Ratio (S13)"
    assert "PSR — Pawn Shop Ratio" in html_body
    assert "CRITICAL_WARNING" in html_body
    assert "Defensive only" in html_body


def test_show_pmr_details_dialog_uses_presenter_output() -> None:
    dash = _build_dashboard_stub()
    dash._show_custom_metric_html_dialog = MagicMock()
    dash.symbol_widgets = {
        "PMR": SimpleNamespace(
            _last_pmr_state={
                "enabled": True,
                "available": True,
                "fired": False,
                "direction": "fade_support",
            }
        )
    }

    dash._show_pmr_details_dialog()

    dash._show_custom_metric_html_dialog.assert_called_once()
    title, html_body = dash._show_custom_metric_html_dialog.call_args.args[:2]
    assert title == "PMR — Pivot Mean-Reversion Signal (S08)"
    assert "PMR — Pivot Mean-Reversion Signal" in html_body
    assert "ARMED" in html_body
