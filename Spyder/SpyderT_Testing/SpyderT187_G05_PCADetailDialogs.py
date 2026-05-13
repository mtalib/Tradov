#!/usr/bin/env python3
"""Focused tests for G05 PCA detail dialog helpers."""

import importlib
import sys
import threading
import types
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest


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
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import MarketSymbolWidget
from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger


def _build_dashboard_stub() -> SpyderTradingDashboard:
    dash = SpyderTradingDashboard.__new__(SpyderTradingDashboard)
    dash.logger = SpyderLogger.get_logger(__name__)
    dash._last_custom_metrics_payload = {}
    dash._metrics_orchestrator = None
    dash.signal_panel = None
    dash.current_dialog = None
    return dash


def test_get_custom_metric_entry_prefers_cached_payload() -> None:
    dash = _build_dashboard_stub()
    expected = {
        "value": 1.42,
        "change": 0.18,
        "quality": 0.91,
        "details": {"source": "tradier", "status": "live"},
    }
    dash._last_custom_metrics_payload = {"PCA-PROXY": expected}

    result = dash._get_custom_metric_entry("PCA-PROXY")

    assert result == expected


def test_build_pca_proxy_details_html_includes_live_fields() -> None:
    entry = {
        "value": 1.25,
        "change": 0.50,
        "quality": 0.88,
        "details": {
            "source": "tradier",
            "status": "live",
            "explained_variance": 0.41,
            "spectral_gap": 0.18,
            "dispersion_score": 0.67,
            "universe_size": 11,
            "confidence": 0.51,
            "timestamp": "2026-05-10T21:00:00+00:00",
            "details": {
                "pc1_score": 0.91,
                "pc2_abs": 0.44,
                "symbols": ["XLC", "XLY", "XLP"],
                "recent_signal_history": [0.12, 0.20, 0.18, 0.25, 0.31],
                "history_window": 5,
                "regime_band": "Positive impulse",
                "regime_color": "#5cffa0",
                "regime_note": "The dominant sector factor is broad and currently pushing upward.",
            },
        },
    }

    html = SpyderTradingDashboard._build_pca_proxy_details_html(entry)

    assert "PCA-Proxy — Sector Eigenfactor Signal" in html
    assert "Composite signal" in html
    assert "+1.25" in html
    assert "41.0%" in html
    assert "TRADIER" in html.upper()
    assert "XLC, XLY, XLP" in html
    assert "Recent history" in html
    assert "Positive impulse" in html
    assert "Operator takeaway" in html
    assert "Broad upside impulse with sectors moving in sync." in html
    assert "How to read the number" in html
    assert "±0.35" in html


def test_build_pca_iv_details_html_shows_placeholder_state() -> None:
    entry = {
        "value": 0.0,
        "change": 0.0,
        "quality": 1.0,
        "details": {
            "source": "placeholder",
            "status": "placeholder",
            "confidence": 0.0,
            "timestamp": "2026-05-10T21:00:00+00:00",
            "details": {
                "message": "History seeding is active for the future SPY IV-surface PCA factor model.",
                "target_surface": "moneyness x dte implied-vol grid",
                "phase": "history-seeding",
                "stored_snapshots": 12,
                "min_live_snapshots": 30,
                "target_snapshots": 120,
                "readiness_progress": 0.10,
                "first_snapshot_ts": "2026-05-10T20:00:00+00:00",
                "last_snapshot_ts": "2026-05-10T21:00:00+00:00",
                "history_path": "data/cache/pca_iv_surface_history/spy_iv_surface_features.jsonl",
                "feature_columns": ["feature_level", "feature_skew"],
            },
        },
    }

    html = SpyderTradingDashboard._build_pca_iv_details_html(entry)

    assert "PCA-IV — Placeholder Signal" in html
    assert "PEND" in html
    assert "moneyness x dte implied-vol grid" in html
    assert "placeholder" in html.lower()
    assert "History seeding" in html
    assert "spy_iv_surface_features.jsonl" in html
    assert "Operator takeaway" in html
    assert "Seeding in progress" in html
    assert "How to read the states" in html
    assert "SEED" in html
    assert "HOLD" in html


def test_build_pca_iv_details_html_shows_live_state() -> None:
    entry = {
        "value": 0.84,
        "change": 0.50,
        "quality": 0.86,
        "details": {
            "source": "surface-history",
            "status": "live",
            "explained_variance": 0.55,
            "spectral_gap": 0.22,
            "dispersion_score": 0.18,
            "confidence": 0.68,
            "timestamp": "2026-05-10T21:30:00+00:00",
            "details": {
                "phase": "live-seeding",
                "stored_snapshots": 48,
                "min_live_snapshots": 30,
                "target_snapshots": 120,
                "readiness_progress": 0.40,
                "first_snapshot_ts": "2026-05-10T20:00:00+00:00",
                "last_snapshot_ts": "2026-05-10T21:30:00+00:00",
                "history_path": "data/cache/pca_iv_surface_history/spy_iv_surface_features.jsonl",
                "feature_columns": ["feature_level", "feature_skew"],
                "pc1_score": 0.62,
                "pc2_abs": 0.21,
                "row_count": 48,
                "feature_level": 0.23,
                "feature_skew": -0.02,
                "feature_convexity": 0.01,
                "recent_signal_history": [0.10, 0.18, 0.35, 0.44, 0.84],
                "history_window": 5,
                "regime_band": "Stress expansion",
                "regime_color": "#FF073A",
                "regime_note": "The dominant IV surface factor is aligned with higher-volatility conditions.",
                "pc1_loadings": {"feature_level": 0.61, "feature_skew": 0.44},
            },
        },
    }

    html = SpyderTradingDashboard._build_pca_iv_details_html(entry)

    assert "PCA-IV — Surface Factor Signal" in html
    assert "+0.84" in html
    assert "Stress expansion" in html
    assert "feature_level" in html
    assert "Stored snapshots" in html
    assert "Operator takeaway" in html
    assert "Stress-expansion bias across the IV surface." in html
    assert "How to read the number" in html
    assert "compression and normalization" in html


def test_build_pca_dialogs_surface_current_regime_takeaways() -> None:
    proxy_entry = {
        "value": -0.24,
        "change": 2.06,
        "quality": 1.0,
        "details": {
            "source": "tradier",
            "status": "live",
            "details": {
                "pc2_abs": 1.328,
                "regime_band": "Rotation",
            },
        },
    }
    iv_entry = {
        "value": -1.34,
        "change": 0.0,
        "quality": 1.0,
        "details": {
            "source": "surface-history",
            "status": "live",
            "details": {
                "pc2_abs": 1.135,
                "phase": "live-seeding",
                "regime_band": "Surface twist",
            },
        },
    }

    proxy_html = SpyderTradingDashboard._build_pca_proxy_details_html(proxy_entry)
    iv_html = SpyderTradingDashboard._build_pca_iv_details_html(iv_entry)

    assert "Mixed breadth with elevated internal sector rotation." in proxy_html
    assert "Compression bias with skew and curve structure still active." in iv_html


def test_market_symbol_widget_pca_tooltips_explain_sign_and_state() -> None:
    proxy_tip = MarketSymbolWidget._build_pca_proxy_tooltip(-0.24, 2.06)
    iv_live_tip = MarketSymbolWidget._build_pca_iv_tooltip(-1.34, 0.00, "live", "live-seeding")
    iv_seed_tip = MarketSymbolWidget._build_pca_iv_tooltip(0.0, 0.0, "placeholder", "history-seeding")

    assert "PCA-Proxy" in proxy_tip
    assert "Positive = sector moves align" in proxy_tip
    assert "Balanced" in proxy_tip
    assert "PCA-IV" in iv_live_tip
    assert "Negative = IV compression / normalization" in iv_live_tip
    assert "Compression" in iv_live_tip
    assert "State: SEED" in iv_seed_tip
    assert "surface history is still accumulating" in iv_seed_tip


def test_symbol_click_routes_pca_rows_to_detail_dialogs() -> None:
    dash = _build_dashboard_stub()
    dash._show_pmr_details_dialog = MagicMock()
    dash._show_pca_proxy_details_dialog = MagicMock()
    dash._show_pca_iv_details_dialog = MagicMock()
    dash._show_wrs_details_dialog = MagicMock()
    dash._show_psr_details_dialog = MagicMock()

    dash._on_symbol_widget_clicked("PCA-PROXY")
    dash._on_symbol_widget_clicked("PCA-IV")

    dash._show_pca_proxy_details_dialog.assert_called_once()
    dash._show_pca_iv_details_dialog.assert_called_once()
    dash._show_pmr_details_dialog.assert_not_called()


def test_on_pivot_signal_state_bridges_runtime_payload_for_d31_selector() -> None:
    class _Widget:
        def __init__(self) -> None:
            self.state = None

        def update_pmr_state(self, payload: dict) -> None:
            self.state = dict(payload)

    dash = _build_dashboard_stub()
    widget = _Widget()
    orchestrator = SimpleNamespace(market_data_cache={})
    dash.symbol_widgets = {"PMR": widget}
    dash._session_supervisor = SimpleNamespace(orchestrator=orchestrator)

    state = {
        "enabled": True,
        "available": True,
        "fired": True,
        "direction": "fade_resistance",
        "score": 78.0,
        "level_name": "R1",
        "level_price": 741.25,
        "atr_distance": 0.19,
        "reasons": ["+25 regime=RANGE"],
        "penalties": [],
    }

    dash._on_pivot_signal_state(state)

    expected = {
        "fired": True,
        "direction": "fade_resistance",
        "score": 78.0,
        "nearest_level_name": "R1",
        "atr_distance": 0.19,
    }

    assert dash._pmr_row_state == state
    assert widget.state == state
    assert orchestrator.market_data_cache["pivot_signal"] == expected
    assert orchestrator.market_data_cache["pivot_mr_signal"] == expected
    assert orchestrator.market_data_cache["market_conditions"]["pivot_signal"] == expected
    assert orchestrator.market_data_cache["market_conditions"]["pivot_mr_signal"] == expected


def test_pivot_signal_bridge_drives_d31_pmr_selection(monkeypatch) -> None:
    class _Widget:
        def __init__(self) -> None:
            self.state = None

        def update_pmr_state(self, payload: dict) -> None:
            self.state = dict(payload)

    class _StubEM:
        def subscribe(self, *args, **kwargs):
            return None

        def emit(self, *args, **kwargs):
            return None

        def publish(self, *args, **kwargs):
            return None

        def unsubscribe(self, *args, **kwargs):
            return None

    monkeypatch.setenv("SPYDER_ENABLE_PIVOT_MEAN_REVERSION", "true")

    qt_backend = types.ModuleType("matplotlib.backends.backend_qt5agg")
    qt_backend.FigureCanvasQTAgg = _BaseQtObject

    with patch.dict(
        sys.modules,
        {"matplotlib.backends.backend_qt5agg": qt_backend},
    ):
        d31_mod = importlib.import_module(
            "Spyder.SpyderD_Strategies.SpyderD31_StrategyOrchestrator"
        )
    orchestrator = d31_mod.StrategyOrchestrator(event_manager=_StubEM())
    orchestrator.market_regime.current_regime = d31_mod.MarketRegime.SIDEWAYS_LOW_VOL

    dash = _build_dashboard_stub()
    widget = _Widget()
    dash.symbol_widgets = {"PMR": widget}
    dash._session_supervisor = SimpleNamespace(orchestrator=orchestrator)

    dash._on_pivot_signal_state(
        {
            "enabled": True,
            "available": True,
            "fired": True,
            "direction": "fade_resistance",
            "score": 81.0,
            "level_name": "R1",
            "level_price": 741.25,
            "atr_distance": 0.19,
            "reasons": ["+25 regime=RANGE"],
            "penalties": [],
        }
    )

    strategy_name, reason = orchestrator._select_strategy_name_for_regime()

    assert widget.state is not None
    assert strategy_name == "PivotMeanReversion"
    assert orchestrator._last_selector_feature_flag == "SPYDER_ENABLE_PIVOT_MEAN_REVERSION"
    assert "pivot_overlay=fired" in reason


def test_start_metrics_orchestrator_hydrates_cached_pca_rows() -> None:
    class _Signal:
        def __init__(self) -> None:
            self.connected = []

        def connect(self, callback) -> None:
            self.connected.append(callback)

    class _Widget:
        def __init__(self) -> None:
            self.payload = None

        def update_data(self, payload: dict) -> None:
            self.payload = payload

    class _FakeOrchestrator:
        def __init__(self) -> None:
            self.metrics_updated = _Signal()
            self.stress_level_changed = _Signal()
            self._has_published_metrics = True
            self.current_metrics = {
                "PCA-PROXY": 0.84,
                "PCA-PROXY_CHANGE": 0.18,
                "PCA-PROXY_DETAILS": {
                    "status": "live",
                    "details": {"phase": "live"},
                },
                "PCA-IV": 0.0,
                "PCA-IV_CHANGE": 0.0,
                "PCA-IV_DETAILS": {
                    "status": "placeholder",
                    "details": {"phase": "history-seeding"},
                },
            }

            def has_published_metrics_snapshot(self) -> bool:
                return True

        def _format_metrics(self, metrics: dict) -> dict:
            assert metrics["PCA-PROXY"] == 0.84
            return {
                "PCA-PROXY": {
                    "value": 0.84,
                    "change": 0.18,
                    "details": {"status": "live", "details": {"phase": "live"}},
                },
                "PCA-IV": {
                    "value": 0.0,
                    "change": 0.0,
                    "details": {
                        "status": "placeholder",
                        "details": {"phase": "history-seeding"},
                    },
                },
            }

    dash = _build_dashboard_stub()
    proxy_widget = _Widget()
    iv_widget = _Widget()
    dash.symbol_widgets = {
        "PCA-PROXY": proxy_widget,
        "PCA-IV": iv_widget,
    }
    dash.add_system_log = MagicMock()
    dash.log_autonomous_event = MagicMock()

    fake_orchestrator = _FakeOrchestrator()
    fake_s07_module = types.ModuleType(
        "SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator"
    )
    fake_s07_module.get_metrics_orchestrator = lambda: fake_orchestrator

    with patch.dict(
        sys.modules,
        {
            "SpyderS_Signals": sys.modules.get(
                "SpyderS_Signals", types.ModuleType("SpyderS_Signals")
            ),
            "SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator": fake_s07_module,
        },
    ):
        dash._start_metrics_orchestrator()

    assert dash._metrics_orchestrator is fake_orchestrator
    assert fake_orchestrator.metrics_updated.connected
    assert fake_orchestrator.stress_level_changed.connected
    assert proxy_widget.payload is not None
    assert proxy_widget.payload["last"] == pytest.approx(0.84)
    assert proxy_widget.payload["change"] == pytest.approx(0.18)
    assert proxy_widget.payload["change_pct"] == pytest.approx(27.27272727272727)
    assert proxy_widget.payload["status"] == "live"
    assert proxy_widget.payload["phase"] == "live"
    assert iv_widget.payload == {
        "last": 0.0,
        "change": 0.0,
        "change_pct": 0.0,
        "status": "placeholder",
        "phase": "history-seeding",
    }