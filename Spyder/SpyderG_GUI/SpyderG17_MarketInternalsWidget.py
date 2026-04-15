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
        • $TICK  — NYSE Tick Index (Tradier real-time)
        • $ADD   — NYSE Advance-Decline Difference (Tradier real-time)
        • $TRIN  — NYSE Arms Index (yfinance fallback)

    Data refresh priority:
        1. Tradier get_quotes() for $TICK and $ADD  (confirmed symbols April 2026)
        2. yfinance ^TRIN intraday 1-min bars for TRIN
        3. yfinance ^TICK / ^ADD as fallback if Tradier connection is absent

    Auto-refresh interval: configurable (default 5 s).
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
from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
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

try:
    import yfinance as yf
    _YFINANCE = True
except ImportError:
    _YFINANCE = False

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
_RED       = "#f44336"
_YELLOW    = "#ffeb3b"
_ORANGE    = "#ff9800"

# History depth – 1 trading day at 5 s resolution ≈ 1 560 points
_HISTORY_MAXLEN = 2_000

# Tradier symbols confirmed real-time (April 2026 production account test)
_TRADIER_SYMBOLS = {
    "TICK": "$TICK",
    "ADD":  "$ADD",
}

# yfinance fallback symbols
_YF_SYMBOLS = {
    "TICK": "^TICK",
    "ADD":  "^ADD",
    "TRIN": "^TRIN",
}

# Default alert thresholds
_DEFAULTS = {
    "TICK": {"high": 800,  "low": -800,  "unit": "",  "scale": 1},
    "ADD":  {"high": 1000, "low": -1000, "unit": "",  "scale": 1},
    "TRIN": {"high": 150,  "low": 50,    "unit": "×0.01", "scale": 100},
    # TRIN slider is integer×0.01 so we can use QSlider (integers only).
    # Displayed as value/100.  Thresholds: high=150→1.50, low=50→0.50.
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
    """Background thread — fetches fresh quotes once per trigger."""

    # Emits dict: {"TICK": float|None, "ADD": float|None, "TRIN": float|None}
    data_ready = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self, tradier_client=None, parent=None):
        super().__init__(parent)
        self._client = tradier_client

    def run(self):
        result = {"TICK": None, "ADD": None, "TRIN": None}
        try:
            # --- Tradier for TICK + ADD -----------------------------------------
            if self._client is not None:
                try:
                    symbols = list(_TRADIER_SYMBOLS.values())  # ["$TICK", "$ADD"]
                    resp = self._client.get_quotes(symbols)
                    quotes_raw = resp.get("quotes", {}).get("quote", [])
                    if isinstance(quotes_raw, dict):
                        quotes_raw = [quotes_raw]
                    for q in quotes_raw:
                        sym = q.get("symbol", "")
                        val = q.get("last") or q.get("close")
                        if val is not None:
                            if sym == "$TICK":
                                result["TICK"] = float(val)
                            elif sym == "$ADD":
                                result["ADD"] = float(val)
                except Exception as exc:
                    logger.warning("Tradier internals fetch failed: %s", exc)

            # --- yfinance fallback / TRIN -----------------------------------------
            if _YFINANCE:
                need = [k for k in ("TICK", "ADD", "TRIN") if result[k] is None]
                for key in need:
                    yf_sym = _YF_SYMBOLS[key]
                    try:
                        tick = yf.Ticker(yf_sym)
                        hist = tick.history(period="1d", interval="1m")
                        if not hist.empty:
                            result[key] = float(hist["Close"].iloc[-1])
                    except Exception as exc:
                        logger.debug("yfinance %s failed: %s", yf_sym, exc)

        except Exception as exc:
            self.error_occurred.emit(str(exc))

        self.data_ready.emit(result)


# ==============================================================================
# HISTORY FETCH WORKER  (1-day bars for charts)
# ==============================================================================
class _HistoryWorker(QThread):
    """Fetches 1-day 1-min bars for all three internals via yfinance."""

    history_ready = Signal(dict)  # {"TICK": [(ts, val),...], ...}

    def run(self):
        out = {"TICK": [], "ADD": [], "TRIN": []}
        if not _YFINANCE:
            self.history_ready.emit(out)
            return
        for key, yf_sym in _YF_SYMBOLS.items():
            try:
                hist = yf.Ticker(yf_sym).history(period="1d", interval="1m")
                if not hist.empty:
                    rows = [
                        (ts.to_pydatetime(), float(val))
                        for ts, val in zip(hist.index, hist["Close"])
                    ]
                    out[key] = rows
            except Exception as exc:
                logger.debug("History fetch %s: %s", yf_sym, exc)
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
        self._status_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")

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
        self._src_lbl = QLabel(f"source: yfinance ({_YF_SYMBOLS[self.symbol]})")
        self._src_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 10px;")
        self._src_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self._src_lbl)

    # ------------------------------------------------------------------
    def _make_chart(self) -> QWidget:
        if _PYQTGRAPH:
            pw = pg.PlotWidget()
            pw.setBackground(_PANEL)
            pw.setFixedHeight(130)
            pw.getAxis("bottom").setStyle(tickFont=QFont("Courier New", 7))
            pw.getAxis("left").setStyle(tickFont=QFont("Courier New", 7))
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
            lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
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
            f"color: {_TEXT}; background-color: {_PANEL}; border: 1px solid {_BORDER}; font-size: 11px;"
        )
        if self._unit:
            spin.setSuffix(f" {self._unit}")

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-5000, 5000)
        slider.setValue(default)
        slider.setStyleSheet(f"QSlider::groove:horizontal {{ background: {_BORDER}; height: 4px; }}"
                              f"QSlider::handle:horizontal {{ background: {color}; width: 10px; height: 10px; "
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
    def update_value(self, value: Optional[float], source: str = "yfinance"):
        """Called from the main dialog when fresh data arrives."""
        if value is None:
            self._value_lbl.setText("N/A")
            self._status_lbl.setText("no data")
            return

        # Colour-code the value label (TICK-specific breakpoints; ADD/TRIN use same)
        display = f"{value:+.0f}" if self.symbol != "TRIN" else f"{value:.2f}"
        colour  = _CYAN  # default

        if self.symbol == "TICK":
            if   value >=  1000: colour = _GREEN
            elif value >=   600: colour = _GREEN
            elif value <=  -1000: colour = _RED
            elif value <=  -600: colour = _ORANGE
        elif self.symbol == "ADD":
            if   value >=  500: colour = _GREEN
            elif value <= -500: colour = _RED
        elif self.symbol == "TRIN":
            display = f"{value:.2f}"
            if   value >= 1.5: colour = _RED      # bearish
            elif value <= 0.7: colour = _GREEN    # bullish
            else:              colour = _CYAN

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
    Non-modal dialog window: three side-by-side InternalPanel widgets for
    TICK, ADD, and TRIN with a shared auto-refresh timer.

    Args:
        tradier_client: Optional live TradierClient instance for real-time
                        TICK and ADD quotes.  When None, yfinance is the
                        sole data source for all three.
        parent: Optional parent widget.
    """

    def __init__(self, tradier_client=None, parent=None):
        super().__init__(parent)
        self._client = tradier_client
        self._fetch_worker: Optional[_FetchWorker] = None
        self._hist_worker:  Optional[_HistoryWorker] = None

        self.setWindowTitle("Market Internals Monitor — TICK | ADD | TRIN")
        self.setMinimumSize(820, 560)
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
        # Immediate first refresh
        QTimer.singleShot(300, self._refresh)

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
        self._refresh_indicator.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 14px;")
        self._refresh_indicator.setToolTip("Green while fetching data")

        title_row.addWidget(title_lbl)
        title_row.addStretch()
        title_row.addWidget(self._refresh_indicator)

        root.addLayout(title_row)

        # -- Three panels -----------------------------------------------
        panels_row = QHBoxLayout()
        panels_row.setSpacing(8)

        self._panels = {}
        for sym in ("TICK", "ADD", "TRIN"):
            panel = _InternalPanel(sym, self)
            panel.alert_triggered.connect(self._on_alert)
            self._panels[sym] = panel
            panels_row.addWidget(panel)

        root.addLayout(panels_row, 1)

        # -- Bottom bar -------------------------------------------------
        bottom = QHBoxLayout()

        self._status_lbl = QLabel("Ready")
        self._status_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")

        # Refresh interval spinbox
        iv_lbl = QLabel("Refresh every:")
        iv_lbl.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(2, 60)
        self._interval_spin.setValue(5)
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
        self._timer.setInterval(5_000)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()

    # ------------------------------------------------------------------
    @Slot(int)
    def _on_interval_changed(self, seconds: int):
        self._timer.setInterval(seconds * 1_000)

    # ------------------------------------------------------------------
    def _refresh(self):
        """Kick off the background fetch worker."""
        if self._fetch_worker and self._fetch_worker.isRunning():
            return  # previous fetch still in progress — skip this tick
        self._refresh_indicator.setStyleSheet(f"color: {_GREEN}; font-size: 14px;")
        self._fetch_worker = _FetchWorker(self._client, self)
        self._fetch_worker.data_ready.connect(self._on_data_ready)
        self._fetch_worker.error_occurred.connect(self._on_fetch_error)
        self._fetch_worker.start()

    # ------------------------------------------------------------------
    def _fetch_history(self):
        """Load 1-day 1-min historical bars for all three internals."""
        if not _YFINANCE:
            return
        self._hist_worker = _HistoryWorker(self)
        self._hist_worker.history_ready.connect(self._on_history_ready)
        self._hist_worker.start()

    # ------------------------------------------------------------------
    @Slot(dict)
    def _on_data_ready(self, data: dict):
        for sym, panel in self._panels.items():
            val = data.get(sym)
            # Determine source label
            if sym in ("TICK", "ADD") and self._client is not None and val is not None:
                src = "Tradier (real-time)"
            elif val is not None:
                src = f"yfinance ({_YF_SYMBOLS.get(sym, sym)}) 15 min delay"
            else:
                src = "no data"
            panel.update_value(val, src)

        ts = datetime.now().strftime("%H:%M:%S")
        self._status_lbl.setText(f"Last refresh: {ts}"
                                  + ("" if _YFINANCE else " — install yfinance for TRIN"))
        self._refresh_indicator.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 14px;")

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
        self._status_lbl.setStyleSheet(f"color: {_RED if direction == 'HIGH' else _GREEN}; font-size: 11px;")
        QTimer.singleShot(4_000, lambda: self._status_lbl.setStyleSheet(
            f"color: {_TEXT_DIM}; font-size: 11px;"
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
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_REPO_ROOT / ".env"), override=True)
    except ImportError:
        pass

    app = QApplication(sys.argv)

    # Optionally wire a real TradierClient if credentials are present
    client = None
    api_key = os.environ.get("TRADIER_SANDBOX_API_KEY") or os.environ.get("TRADIER_API_KEY", "")
    acct_id = os.environ.get("TRADIER_SANDBOX_ACCOUNT_ID") or os.environ.get("TRADIER_ACCOUNT_ID", "")
    if api_key and acct_id:
        try:
            from Spyder.SpyderB_Broker.SpyderB40_TradierClient import TradierClient, TradingEnvironment
            env = TradingEnvironment.SANDBOX if os.environ.get("TRADIER_SANDBOX_API_KEY") else TradingEnvironment.LIVE
            client = TradierClient(api_key=api_key, account_id=acct_id, environment=env)
            print(f"[INFO] TradierClient ready ({env.value})")
        except Exception as e:
            print(f"[WARN] Could not init TradierClient: {e} — using yfinance only")

    dlg = MarketInternalsDialog(tradier_client=client)
    dlg.show()
    sys.exit(app.exec())
