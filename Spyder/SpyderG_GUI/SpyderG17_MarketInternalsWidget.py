#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG17_MarketInternalsWidget.py
Purpose: Live Market Internals Monitor — TICK, ADD, TRIN

Author: Spyder Dev
Year Created: 2026
Last Updated: 2026-04-14 Time: 21:00:00

Description:
    Non-modal dialog that embeds live 1-day mini-charts and configurable alert
    sliders for the three core market-breadth internals:
        • $TICK  — NYSE Tick Index
        • $ADD   — NYSE Advance-Decline Difference
        • $TRIN  — NYSE Arms Index

    Data source:
        SpyderS07_CustomMetricsOrchestrator → SpyderS11_TradingViewInternals
        (Playwright headless Chromium scraping TradingView public pages).
        Connect S07.breadth_updated → dialog.on_breadth_updated to push data in.

    Auto-refresh interval: configurable (default 5 s) for manual polling fallback.
    Alert: plays native Qt MessageBeep and flashes the value label when a
    threshold is breached.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Optional

# ==============================================================================
# PATH SETUP
# ==============================================================================
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot  # noqa: E402
from PySide6.QtGui import QFont, QColor  # noqa: E402, F401
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,  # noqa: F401
    QSlider,
    QVBoxLayout,
    QWidget,
    QSpinBox,
    QFrame,
)

try:
    import pyqtgraph as pg
    pg.setConfigOptions(antialias=True)
    _PYQTGRAPH = True
except ImportError:
    _PYQTGRAPH = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from Spyder.SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    logger = SpyderLogger.get_logger("SpyderG17")
except Exception:
    logger = logging.getLogger("SpyderG17")

# ==============================================================================
# CONSTANTS — colours matching the rest of the Spyder GUI
# ==============================================================================
_BG        = "#0a0a0a"
_PANEL     = "#1a1a1a"
_BORDER    = "#333333"
_TEXT      = "#e0e0e0"
_TEXT_DIM  = "#888888"
_CYAN      = "#00bcd4"
_GREEN     = "#4caf50"
_RED       = "#FF073A"
_YELLOW    = "#ffeb3b"
_ORANGE    = "#ff9800"

# History depth – 1 trading day at 5 s resolution ≈ 1 560 points
_HISTORY_MAXLEN = 2_000

# Default alert thresholds
_DEFAULTS = {
    "TICK": {"high": 800,  "low": -800,  "unit": "",       "scale": 1},
    "ADD":  {"high": 1000, "low": -1000, "unit": "",       "scale": 1},
    "TRIN": {"high": 150,  "low": 50,    "unit": "×0.01",  "scale": 100},
    "NYMO": {"high": 40,   "low": -40,   "unit": "",       "scale": 1},
    # TRIN slider is integer×0.01 so we can use QSlider (integers only).
    # Displayed as value/100.  Thresholds: high=150→1.50, low=50→0.50.
    # NYMO: NYSE McClellan Oscillator; >+40 overbought, <−40 oversold.
}

# Colour thresholds for TICK
_TICK_COLOURS = [
    (1000,  "+∞",  _GREEN,  "Extreme breadth — strong bull surge"),
    (600,   1000,  _GREEN,  "Overbought breadth"),
    (-600,   600,  _CYAN,   "Normal breadth"),
    (-1000, -600,  _ORANGE, "Oversold breadth"),
    ("-∞",  -1000, _RED,    "Extreme breadth — strong bear flush"),
]


# ==============================================================================
# DATA FETCH WORKER
# ==============================================================================
class _FetchWorker(QThread):
    """Background thread — placeholder; real data pushed in via on_breadth_updated()."""

    # Emits dict: {"TICK": float|None, "ADD": float|None, "TRIN": float|None}
    data_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, tradier_client=None, parent=None):
        super().__init__(parent)

    def run(self):
        # Data comes from S07 → S11 (TradingView/Playwright); nothing to fetch here.
        self.data_ready.emit({"TICK": None, "ADD": None, "TRIN": None, "NYMO": None})


# ==============================================================================
# HISTORY FETCH WORKER  (1-day bars for charts)
# ==============================================================================
class _HistoryWorker(QThread):
    """Placeholder history worker — intraday bars unavailable until a Playwright history source is added."""  # noqa: E501

    history_ready = Signal(dict)  # {"TICK": [(ts, val),...], ...}

    def run(self):
        out = {"TICK": [], "ADD": [], "TRIN": [], "NYMO": []}
        # History bars unavailable — TradingView Playwright scraper returns current value only.
        self.history_ready.emit(out)


# ==============================================================================
# SINGLE INTERNAL PANEL
# ==============================================================================
class _InternalPanel(QGroupBox):
    """
    One panel (TICK, ADD, or TRIN) showing:
      - Current value (large, colour-coded)
      - Status label
      - Mini pyqtgraph / fallback chart
      - Alert sliders (high / low)
    """

    alert_triggered = Signal(str, float, str)  # symbol, value, "HIGH"/"LOW"

    # ---------------------------------------------------------------------
    def __init__(self, symbol: str, parent=None):
        super().__init__(symbol, parent)
        self.symbol = symbol
        self._history: deque = deque(maxlen=_HISTORY_MAXLEN)
        self._alerted_high = False
        self._alerted_low  = False
        cfg = _DEFAULTS[symbol]
        self._high_threshold = cfg["high"]
        self._low_threshold  = cfg["low"]
        self._scale          = cfg["scale"]   # slider integer = true_value × scale
        self._unit           = cfg["unit"]

        self._setup_ui()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {_CYAN};
                border: 1px solid {_BORDER};
                border-radius: 5px;
                margin-top: 12px;
                padding-top: 4px;
                background-color: {_PANEL};
                font-size: 14px;
                font-weight: normal;
                letter-spacing: 2px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 14, 6, 6)
        root.setSpacing(4)

        # -- Value display --------------------------------------------------
        self._value_lbl = QLabel("—")
        self._value_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_lbl.setFont(QFont("Courier New", 26, QFont.Weight.Bold))
        self._value_lbl.setStyleSheet(f"color: {_TEXT};")
        self._value_lbl.setMinimumHeight(44)

        self._status_lbl = QLabel("waiting for data…")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 13px;")

        root.addWidget(self._value_lbl)
        root.addWidget(self._status_lbl)

        # -- Chart -----------------------------------------------------------
        self._chart_widget = self._make_chart()
        root.addWidget(self._chart_widget)

        # -- Alert sliders ---------------------------------------------------
        slider_frame = QFrame()
        slider_frame.setStyleSheet(
            f"background-color: {_BG}; border: 1px solid {_BORDER}; border-radius: 3px;"
        )
        sl_layout = QVBoxLayout(slider_frame)
        sl_layout.setContentsMargins(6, 4, 6, 4)
        sl_layout.setSpacing(2)

        sl_layout.addWidget(self._slider_row(
            "Alert HIGH", self._high_threshold, self._on_high_changed, color=_RED
        ))
        sl_layout.addWidget(self._slider_row(
            "Alert LOW",  self._low_threshold,  self._on_low_changed,  color=_GREEN
        ))
        root.addWidget(slider_frame)

        # -- Source label ----------------------------------------------------
        self._src_lbl = QLabel("source: TradingView (Playwright)")
        self._src_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 12px;")
        self._src_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self._src_lbl)

    # ------------------------------------------------------------------
    def _make_chart(self) -> QWidget:
        if _PYQTGRAPH:
            pw = pg.PlotWidget()
            pw.setBackground(_PANEL)
            pw.setFixedHeight(130)
            pw.getAxis("bottom").setStyle(tickFont=QFont("Courier New", 9))
            pw.getAxis("left").setStyle(tickFont=QFont("Courier New", 9))
            pw.getAxis("bottom").setPen(pg.mkPen(_BORDER))
            pw.getAxis("left").setPen(pg.mkPen(_BORDER))
            pw.showGrid(x=False, y=True, alpha=0.2)
            # Zero reference line
            pw.addItem(pg.InfiniteLine(pos=0, angle=0,
                                       pen=pg.mkPen(_TEXT_DIM, style=Qt.PenStyle.DashLine)))
            self._plot_curve = pw.plot([], pen=pg.mkPen(_CYAN, width=1.5))
            self._chart_pw   = pw
            return pw
        else:
            lbl = QLabel("Install pyqtgraph for live charts\n(pip install pyqtgraph)")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {_TEXT}; font-size: 13px;")
            lbl.setFixedHeight(130)
            self._plot_curve = None
            self._chart_pw   = None
            return lbl

    # ------------------------------------------------------------------
    def _slider_row(self, label_text: str, default: int, callback, color: str) -> QWidget:
        row = QWidget()
        rl  = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        lbl.setFixedWidth(70)

        # spinbox mirrors the slider and allows direct typing
        spin = QSpinBox()
        spin.setRange(-5000, 5000)
        spin.setValue(default)
        spin.setFixedWidth(60)
        spin.setStyleSheet(
            f"color: {_TEXT}; background-color: {_PANEL}; border: 1px solid {_BORDER}; font-size: 11px;"  # noqa: E501
        )
        if self._unit:
            spin.setSuffix(f" {self._unit}")

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-5000, 5000)
        slider.setValue(default)
        slider.setStyleSheet(f"QSlider::groove:horizontal {{ background: {_BORDER}; height: 4px; }}"
                              f"QSlider::handle:horizontal {{ background: {color}; width: 10px; height: 10px; "  # noqa: E501
                              f"margin: -3px 0; border-radius: 5px; }}")

        # bidirectional sync
        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        slider.valueChanged.connect(callback)

        rl.addWidget(lbl)
        rl.addWidget(spin)
        rl.addWidget(slider, 1)

        # Keep references so _on_xxx_changed can read them
        if "HIGH" in label_text:
            self._high_spin   = spin
            self._high_slider = slider
        else:
            self._low_spin   = spin
            self._low_slider = slider

        return row

    # ------------------------------------------------------------------
    @Slot(int)
    def _on_high_changed(self, value: int):
        self._high_threshold = value

    @Slot(int)
    def _on_low_changed(self, value: int):
        self._low_threshold = value

    # ------------------------------------------------------------------
    def update_value(self, value: Optional[float], source: str = "TradingView (Playwright)"):
        """Called from the main dialog when fresh data arrives."""
        if value is None:
            self._value_lbl.setText("N/A")
            self._status_lbl.setText("no data")
            return

        # Colour-code the value label (TICK-specific breakpoints; ADD/TRIN use same)
        display = f"{value:+.0f}" if self.symbol != "TRIN" else f"{value:.2f}"
        colour  = _CYAN  # default

        if self.symbol == "TICK":
            if   value >=  1000: colour = _GREEN  # noqa: E701
            elif value >=   600: colour = _GREEN  # noqa: E701
            elif value <=  -1000: colour = _RED  # noqa: E701
            elif value <=  -600: colour = _ORANGE  # noqa: E701
        elif self.symbol == "ADD":
            if   value >=  500: colour = _GREEN  # noqa: E701
            elif value <= -500: colour = _RED  # noqa: E701
        elif self.symbol == "TRIN":
            display = f"{value:.2f}"
            if   value >= 1.5: colour = _RED      # bearish  # noqa: E701
            elif value <= 0.7: colour = _GREEN    # bullish  # noqa: E701
            else:              colour = _CYAN  # noqa: E701

        self._value_lbl.setText(display)
        self._value_lbl.setStyleSheet(f"color: {colour};")

        # Status text
        ts = datetime.now().strftime("%H:%M:%S")
        self._status_lbl.setText(f"last update: {ts}")
        self._src_lbl.setText(f"source: {source}")

        # Append to rolling history
        self._history.append((datetime.now(), value))

        # Check alerts
        scaled_val = value * self._scale
        if scaled_val >= self._high_threshold and not self._alerted_high:
            self.alert_triggered.emit(self.symbol, value, "HIGH")
            self._alerted_high = True
        elif scaled_val < self._high_threshold:
            self._alerted_high = False

        if scaled_val <= self._low_threshold and not self._alerted_low:
            self.alert_triggered.emit(self.symbol, value, "LOW")
            self._alerted_low = True
        elif scaled_val > self._low_threshold:
            self._alerted_low = False

        # Update chart
        self._redraw_chart()

    # ------------------------------------------------------------------
    def load_history(self, rows: list):
        """Load historical bars [(datetime, float), ...] into the rolling deque."""
        self._history.clear()
        for ts, val in rows:
            self._history.append((ts, val))
        self._redraw_chart()

    # ------------------------------------------------------------------
    def _redraw_chart(self):
        if not _PYQTGRAPH or self._plot_curve is None or not self._history:
            return
        # x = elapsed minutes from first point; y = value
        t0 = self._history[0][0]
        xs = [(t - t0).total_seconds() / 60 for t, _ in self._history]
        ys = [v for _, v in self._history]
        self._plot_curve.setData(xs, ys)


# ==============================================================================
# MARKET INTERNALS DIALOG
# ==============================================================================
class MarketInternalsDialog(QDialog):
    """
    Non-modal dialog window: four side-by-side InternalPanel widgets for
    TICK, ADD, TRIN, and NYMO with a shared auto-refresh timer.

    Data is pushed in via on_breadth_updated(snap) which should be connected
    to SpyderS07_CustomMetricsOrchestrator.breadth_updated at construction time.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, tradier_client=None, orchestrator=None, parent=None):
        """tradier_client kept for signature compatibility but is no longer used."""
        super().__init__(parent)
        self._fetch_worker: Optional[_FetchWorker] = None
        self._hist_worker:  Optional[_HistoryWorker] = None
        self._orchestrator = orchestrator

        self.setWindowTitle("Market Internals Monitor — TICK | ADD | TRIN | NYMO")
        self.setMinimumSize(1060, 560)
        self.setStyleSheet(f"""
            QDialog  {{ background-color: {_BG}; }}
            QLabel   {{ color: {_TEXT}; }}
            QPushButton {{
                background-color: {_PANEL};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 3px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{ border-color: {_CYAN}; }}
        """)

        self._setup_ui()
        self._setup_timer()

        # Load 1-day history on open (non-blocking)
        self._fetch_history()

        # Connect orchestrator so live TICK/ADD/TRIN data flows in immediately.
        # _get_orchestrator() tries both import paths and caches on self._orchestrator.
        self._get_orchestrator()

    # ------------------------------------------------------------------
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # -- Title bar --------------------------------------------------
        title_row = QHBoxLayout()
        title_lbl = QLabel("MARKET BREADTH INTERNALS")
        title_lbl.setStyleSheet(
            f"color: {_CYAN}; font-size: 15px; letter-spacing: 2px;"
        )
        self._refresh_indicator = QLabel(" ● ")
        self._refresh_indicator.setStyleSheet(f"color: {_TEXT}; font-size: 14px;")
        self._refresh_indicator.setToolTip("Green while fetching data")

        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._refresh_indicator)

        root.addLayout(title_row)

        # -- Three panels -----------------------------------------------
        panels_row = QHBoxLayout()
        panels_row.setSpacing(8)

        self._panels = {}
        for sym in ("TICK", "ADD", "TRIN", "NYMO"):
            panel = _InternalPanel(sym, self)
            panel.alert_triggered.connect(self._on_alert)
            self._panels[sym] = panel
            panels_row.addWidget(panel)

        root.addLayout(panels_row, 1)

        # -- Bottom bar -------------------------------------------------
        bottom = QHBoxLayout()

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 13px;")

        # Refresh interval spinbox
        iv_lbl = QLabel("Refresh every:")
        iv_lbl.setStyleSheet(f"color: {_TEXT}; font-size: 13px;")
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(2, 3600)
        self._interval_spin.setValue(30)
        self._interval_spin.setSuffix(" s")
        self._interval_spin.setFixedWidth(65)
        self._interval_spin.setStyleSheet(
            f"color: {_TEXT}; background: {_PANEL}; border: 1px solid {_BORDER}; font-size: 11px;"
        )
        self._interval_spin.valueChanged.connect(self._on_interval_changed)

        refresh_btn = QPushButton("⟳ Refresh Now")
        refresh_btn.clicked.connect(self._refresh)

        bottom.addWidget(self._status_lbl)
        bottom.addStretch()
        bottom.addWidget(iv_lbl)
        bottom.addWidget(self._interval_spin)
        bottom.addWidget(refresh_btn)

        root.addLayout(bottom)

    # ------------------------------------------------------------------
    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.setInterval(30_000)  # default 30 s; mirrors user-visible spinbox
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    # ------------------------------------------------------------------
    @Slot(int)
    def _on_interval_changed(self, seconds: int):
        self._timer.setInterval(seconds * 1_000)

    # ------------------------------------------------------------------
    def _get_orchestrator(self):
        """Return the live S07 orchestrator, resolving it lazily if not yet set."""
        if self._orchestrator is not None:
            return self._orchestrator
        # Try both import paths (module may have been loaded under either)
        for mod_path in (
            "SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator",
            "Spyder.SpyderS_Signals.SpyderS07_CustomMetricsOrchestrator",
        ):
            try:
                import importlib
                mod = importlib.import_module(mod_path)
                orch = mod.get_metrics_orchestrator()
                if orch is not None:
                    self._orchestrator = orch
                    # Wire breadth_updated so future live pushes reach the panels
                    try:
                        orch.breadth_updated.connect(self.on_breadth_updated)
                    except Exception:
                        pass
                    # Immediately push any cached values
                    cm = getattr(orch, "current_metrics", {})
                    self._push_current_metrics(cm)
                    return orch
            except Exception:
                continue
        return None

    def _push_current_metrics(self, cm: dict):
        """Push raw flat current_metrics dict straight to the panels (no network needed)."""
        import math
        tick = cm.get("TICK", float("nan"))
        add  = cm.get("ADD",  float("nan"))
        trin = cm.get("TRIN", float("nan"))
        nymo = cm.get("NYMO", float("nan"))
        has_data = any(
            not (isinstance(v, float) and math.isnan(v))
            for v in (tick, add, trin, nymo)
        )
        if has_data:
            self.on_breadth_updated({
                "tick": tick,
                "add":  add,
                "trin": trin,
                "nymo": nymo,
                "breadth_regime": cm.get("BREADTH_REGIME", ""),
            })

    def _refresh(self):
        """Force an immediate S07 metrics update so TICK/ADD/TRIN are pushed to this dialog."""
        import threading
        orch = self._get_orchestrator()
        if orch is not None:
            self._status_lbl.setText("Refreshing…")
            threading.Thread(
                target=orch.update_all_metrics,
                name="G17-force-refresh",
                daemon=True,
            ).start()
        else:
            self._status_lbl.setText("No data source — S07 not running")

    # ------------------------------------------------------------------
    @Slot(dict)
    def on_breadth_updated(self, snap: dict):
        """Receive live TICK/ADD/TRIN/NYMO values from S07 (TradingView via Playwright).

        Connect S07.breadth_updated to this slot when constructing the dialog.

        Args:
            snap: dict with keys 'tick', 'add', 'trin', 'nymo' (floats) and optionally
                  'breadth_regime' (str) emitted by SpyderS07_CustomMetricsOrchestrator.
        """
        import math
        data = {
            "TICK": snap.get("tick"),
            "ADD":  snap.get("add"),
            "TRIN": snap.get("trin"),
            "NYMO": snap.get("nymo"),
        }
        any_updated = False
        for sym, panel in self._panels.items():
            val = data.get(sym)
            if val is not None and not (isinstance(val, float) and math.isnan(val)):
                panel.update_value(val, "TradingView (Playwright)")
                any_updated = True
        if not any_updated:
            return  # no real data — don't touch status or indicator
        ts = datetime.now().strftime("%H:%M:%S")
        regime = snap.get("breadth_regime", "")
        self._status_lbl.setText(f"Last update: {ts}  |  Regime: {regime}" if regime else f"Last update: {ts}")  # noqa: E501
        self._refresh_indicator.setStyleSheet(f"color: {_TEXT}; font-size: 14px;")

    # ------------------------------------------------------------------
    def _fetch_history(self):
        """Load 1-day 1-min historical bars (currently unavailable — no intraday source)."""
        self._hist_worker = _HistoryWorker(self)
        self._hist_worker.history_ready.connect(self._on_history_ready)
        self._hist_worker.start()

    # ------------------------------------------------------------------
    @Slot(dict)
    def _on_data_ready(self, data: dict):
        # Only update panels that have a real value — never overwrite live S07 data with None.
        for sym, panel in self._panels.items():
            val = data.get(sym)
            if val is not None:
                panel.update_value(val, "TradingView (Playwright)")

    # ------------------------------------------------------------------
    @Slot(dict)
    def _on_history_ready(self, history: dict):
        for sym, rows in history.items():
            if rows and sym in self._panels:
                self._panels[sym].load_history(rows)

    # ------------------------------------------------------------------
    @Slot(str)
    def _on_fetch_error(self, msg: str):
        self._status_lbl.setText(f"Fetch error: {msg}")
        self._refresh_indicator.setStyleSheet(f"color: {_RED}; font-size: 14px;")

    # ------------------------------------------------------------------
    @Slot(str, float, str)
    def _on_alert(self, symbol: str, value: float, direction: str):
        """Flash and log when a threshold is breached."""
        msg = f"[ALERT] {symbol} breached {direction} threshold: {value:+.1f}"
        logger.warning(msg)
        self._status_lbl.setText(msg)
        self._status_lbl.setStyleSheet(f"color: {_RED if direction == 'HIGH' else _GREEN}; font-size: 13px;")  # noqa: E501
        QTimer.singleShot(4_000, lambda: self._status_lbl.setStyleSheet(
            f"color: {_TEXT}; font-size: 13px;"
        ))

    # ------------------------------------------------------------------
    def closeEvent(self, event):
        self._timer.stop()
        if self._fetch_worker and self._fetch_worker.isRunning():
            self._fetch_worker.quit()
            self._fetch_worker.wait(1000)
        if self._hist_worker and self._hist_worker.isRunning():
            self._hist_worker.quit()
            self._hist_worker.wait(1000)
        super().closeEvent(event)


# ==============================================================================
# STANDALONE TEST
# ==============================================================================
if __name__ == "__main__":
    import os  # noqa: F401
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_REPO_ROOT / ".env"), override=True)
    except ImportError:
        pass

    app = QApplication(sys.argv)

    dlg = MarketInternalsDialog()
    dlg.show()
    sys.exit(app.exec())
