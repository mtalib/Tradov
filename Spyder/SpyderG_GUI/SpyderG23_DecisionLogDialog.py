#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG23_DecisionLogDialog.py
Purpose: Decision Log viewer dialog. Reads the per-poll JSON-lines audit records
         written by SpyderR08_PaperTradingQtWorker and displays them in a
         sortable, colour-coded table with row-click JSON detail, CSV export,
         and 30-second auto-refresh so the operator can monitor gate-by-gate
         decisions in real time.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-22 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Root folder where R08 writes YYYY-MM-DD.jsonl files.
_LOG_DIR = Path("logs") / "decisions"

# Columns displayed in the table (ordered for readability).
COLUMNS = [
    "#",            # poll sequence number
    "Time",         # UTC timestamp (formatted as HH:MM:SS)
    "SPY",          # last SPY price at poll time
    "Signal",       # MA crossover signal: BUY / SELL / NEUTRAL
    "MA Gap%",      # (MA5 – MA20) / MA20 * 100
    "Action",       # outcome: SPREAD_OPENED / SPREAD_REJECTED / NO_TRADE / …
    "Detail",       # action_detail string
    "D-Loss OK",    # daily-loss-limit gate: YES / NO
    "Regime OK",    # regime guard gate: YES / NO
    "Regime",       # regime_reason string
    "SelFlag",      # selector feature flag (if any)
    "SWAN",         # Black-Swan composite score
    "S08",          # S08 pivot-MR score (or —)
    "S08 Dir",      # S08 direction label
    "Opts",         # options_mode flag (Y/N)
]

# Index of the "Action" column — coloured by outcome type.
_ACTION_COL = 5
_SELFLAG_COL = 10

# Action colour map: green for open/fill, yellow for rejected, grey for nothing.
_ACTION_COLORS: dict[str, str] = {
    "SPREAD_OPENED":  COLORS.get("positive", "#00ff41"),
    "CONDOR_OPENED":  COLORS.get("positive", "#00ff41"),
    "BUY_SHARE":      COLORS.get("positive", "#00ff41"),
    "SELL_SHARE":     COLORS.get("positive", "#00ff41"),
    "SPREAD_REJECTED": "#FFD700",   # amber / yellow
}
_ACTION_DEFAULT_COLOR = "#888888"  # dim grey for NO_TRADE / unknown


# ==============================================================================
# DIALOG
# ==============================================================================
class DecisionLogDialog(QDialog):
    """Non-modal dialog displaying R08 per-poll decision audit records.

    Reads ``logs/decisions/YYYY-MM-DD.jsonl`` (today by default).  A date
    picker combo lets the operator browse historical days.  A QTimer
    auto-refreshes every 30 seconds while the dialog is visible.  Clicking a
    row populates a JSON detail panel at the bottom.  A CSV export button
    writes the currently loaded records.
    """

    _REFRESH_MS = 30_000   # auto-refresh interval

    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Decision Log — Paper Trading Poll Audit")
        self.setModal(False)
        self.resize(1300, 680)

        self._records: list[dict] = []
        self._selected_date: date = date.today()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ── Top bar: summary label + date picker + buttons ──────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        self._summary_label = QLabel()
        self._summary_label.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 12px; font-weight: bold;"
        )
        top_bar.addWidget(self._summary_label, 1)

        date_lbl = QLabel("Date:")
        date_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
        top_bar.addWidget(date_lbl)

        self._date_combo = QComboBox()
        self._date_combo.setFixedWidth(130)
        self._date_combo.setStyleSheet(
            f"font-size: 11px; background-color: {COLORS['panel']};"
            f" color: {COLORS['text']}; border: 1px solid {COLORS['border']};"
        )
        self._populate_date_combo()
        self._date_combo.currentTextChanged.connect(self._on_date_changed)
        top_bar.addWidget(self._date_combo)

        refresh_btn = QPushButton("⟳ Refresh")
        refresh_btn.setFixedHeight(24)
        refresh_btn.setStyleSheet(self._btn_style())
        refresh_btn.setToolTip("Reload the log file now")
        refresh_btn.clicked.connect(self._load_and_populate)
        top_bar.addWidget(refresh_btn)

        export_btn = QPushButton("⬇ Export CSV…")
        export_btn.setFixedHeight(24)
        export_btn.setStyleSheet(self._btn_style())
        export_btn.clicked.connect(self._export_csv)
        top_bar.addWidget(export_btn)

        close_btn = QPushButton("✕ Close")
        close_btn.setFixedHeight(24)
        close_btn.setStyleSheet(self._btn_style())
        close_btn.clicked.connect(self.accept)
        top_bar.addWidget(close_btn)

        layout.addLayout(top_bar)

        # ── Splitter: table (top) + JSON detail panel (bottom) ──────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self._table)

        # JSON detail panel
        detail_container = QWidget()
        detail_layout = QVBoxLayout(detail_container)
        detail_layout.setContentsMargins(0, 4, 0, 0)
        detail_layout.setSpacing(2)
        detail_lbl = QLabel("Row detail (click a row above):")
        detail_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
        detail_layout.addWidget(detail_lbl)
        self._detail_pane = QTextEdit()
        self._detail_pane.setReadOnly(True)
        self._detail_pane.setMaximumHeight(160)
        self._detail_pane.setStyleSheet(
            f"background-color: {COLORS['panel']}; color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; font-family: monospace; font-size: 11px;"
        )
        detail_layout.addWidget(self._detail_pane)
        splitter.addWidget(detail_container)

        splitter.setSizes([480, 160])
        layout.addWidget(splitter, 1)

        # ── Auto-refresh timer ───────────────────────────────────────────────
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self._REFRESH_MS)
        self._refresh_timer.timeout.connect(self._load_and_populate)
        self._refresh_timer.start()

        # Initial load
        self._load_and_populate()

    # ------------------------------------------------------------------ public

    def force_refresh(self) -> None:
        """Public slot: reload from disk immediately (called by dashboard)."""
        self._load_and_populate()

    # ----------------------------------------------------------------- private

    @staticmethod
    def _btn_style() -> str:
        return (
            f"font-size: 11px; padding: 0 8px;"
            f" background-color: {COLORS['panel']};"
            f" color: {COLORS['text']};"
            f" border: 1px solid {COLORS['border']}; border-radius: 3px;"
        )

    def _populate_date_combo(self) -> None:
        """Fill the date picker with the last 14 days that have log files."""
        self._date_combo.blockSignals(True)
        self._date_combo.clear()
        today = date.today()
        found: list[str] = []
        for delta in range(0, 30):
            d = today - timedelta(days=delta)
            path = _LOG_DIR / f"{d.isoformat()}.jsonl"
            if path.exists():
                found.append(d.isoformat())
            if len(found) >= 14:
                break
        if not found:
            # Always show today even if no file yet
            found.append(today.isoformat())
        for item in found:
            self._date_combo.addItem(item)
        # Default to today (first item)
        self._date_combo.setCurrentIndex(0)
        self._date_combo.blockSignals(False)

    def _on_date_changed(self, text: str) -> None:
        try:
            self._selected_date = date.fromisoformat(text)
        except ValueError:
            self._selected_date = date.today()
        self._load_and_populate()

    def _load_and_populate(self) -> None:
        """Read the JSONL for the selected date and refresh the table."""
        path = _LOG_DIR / f"{self._selected_date.isoformat()}.jsonl"
        records: list[dict] = []
        if path.exists():
            try:
                with path.open(encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
            except OSError:
                pass
        self._records = records
        self._populate_table()
        # Refresh the date combo in case new files appeared since last open
        current = self._date_combo.currentText()
        self._populate_date_combo()
        idx = self._date_combo.findText(current)
        if idx >= 0:
            self._date_combo.blockSignals(True)
            self._date_combo.setCurrentIndex(idx)
            self._date_combo.blockSignals(False)

    def _populate_table(self) -> None:
        records = self._records
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(records))

        # Summary
        total = len(records)
        opened = sum(
            1 for r in records
            if r.get("action", "") in ("SPREAD_OPENED", "CONDOR_OPENED", "BUY_SHARE")
        )
        rejected = sum(1 for r in records if r.get("action", "") == "SPREAD_REJECTED")
        flagged = sum(
            1
            for r in records
            if str(r.get("selector_feature_flag", "")).strip() not in ("", "None")
        )
        self._summary_label.setText(
            f"Date: {self._selected_date}   Polls: {total}   "
            f"Opened: {opened}   Rejected: {rejected}   "
            f"No-trade: {total - opened - rejected}   "
            f"Flagged: {flagged}"
        )

        for row, rec in enumerate(records):
            self._fill_row(row, rec)

        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()

    def _fill_row(self, row: int, rec: dict) -> None:
        seq = str(rec.get("seq", ""))
        ts_raw = rec.get("ts", "")
        time_str = _fmt_time(ts_raw)
        spy = _fmt_num(rec.get("spy"), 2, prefix="$")
        signal = str(rec.get("signal", "—"))
        ma_gap = _fmt_pct(rec.get("ma_gap_pct"))
        action = str(rec.get("action", "—"))
        detail = str(rec.get("action_detail", ""))
        d_loss_ok = _fmt_bool(rec.get("daily_loss_ok"))
        regime_ok = _fmt_bool(rec.get("regime_ok"))
        regime_reason = str(rec.get("regime_reason", ""))
        selector_flag_raw = str(rec.get("selector_feature_flag", "")).strip()
        selector_flag = selector_flag_raw or "—"
        selector_flag_active = selector_flag_raw not in ("", "None")
        swan = _fmt_num(rec.get("swan"), 2)
        s08_score = _fmt_num(rec.get("s08_score"), 0) if rec.get("s08_score") is not None else "—"
        s08_dir = str(rec.get("s08_direction", "—")) if rec.get("s08_fired") else "—"
        opts = "Y" if rec.get("options_mode") else "N"

        cells = [
            (seq, Qt.AlignmentFlag.AlignRight),
            (time_str, Qt.AlignmentFlag.AlignLeft),
            (spy, Qt.AlignmentFlag.AlignRight),
            (signal, Qt.AlignmentFlag.AlignCenter),
            (ma_gap, Qt.AlignmentFlag.AlignRight),
            (action, Qt.AlignmentFlag.AlignCenter),
            (detail, Qt.AlignmentFlag.AlignLeft),
            (d_loss_ok, Qt.AlignmentFlag.AlignCenter),
            (regime_ok, Qt.AlignmentFlag.AlignCenter),
            (regime_reason, Qt.AlignmentFlag.AlignLeft),
            (selector_flag, Qt.AlignmentFlag.AlignLeft),
            (swan, Qt.AlignmentFlag.AlignRight),
            (s08_score, Qt.AlignmentFlag.AlignRight),
            (s08_dir, Qt.AlignmentFlag.AlignCenter),
            (opts, Qt.AlignmentFlag.AlignCenter),
        ]

        action_color = QColor(_ACTION_COLORS.get(action, _ACTION_DEFAULT_COLOR))
        selector_flag_color = QColor(COLORS.get("positive", "#00ff41"))

        for col, (text, align) in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setTextAlignment(int(align) | int(Qt.AlignmentFlag.AlignVCenter))
            if col == _ACTION_COL:
                item.setForeground(action_color)
            elif col == _SELFLAG_COL and selector_flag_active:
                item.setForeground(selector_flag_color)
            self._table.setItem(row, col, item)

    def _on_row_selected(self) -> None:
        selected = self._table.selectedItems()
        if not selected:
            return
        row = self._table.row(selected[0])
        if 0 <= row < len(self._records):
            rec = self._records[row]
            self._detail_pane.setPlainText(
                json.dumps(rec, indent=2, default=str)
            )

    def _export_csv(self) -> None:
        if not self._records:
            QMessageBox.information(self, "Export CSV", "No records to export.")
            return
        default = f"spyder_decision_log_{self._selected_date}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Decision Log", default, "CSV Files (*.csv)"
        )
        if not path:
            return
        # Build stable column order: all known keys, extras appended
        known = [
            "ts", "seq", "spy", "bid", "ask", "options_mode", "open_spreads",
            "signal", "ma5", "ma20", "ma_gap_pct", "daily_loss_pct",
            "daily_loss_ok", "regime_ok", "regime_reason",
            "selector_feature_flag",
            "swan", "dix", "gex",
            "s08_enabled", "s08_score", "s08_fired", "s08_direction",
            "action", "action_detail", "spread_id",
        ]
        extras: list[str] = []
        for rec in self._records:
            for k in rec:
                if k not in known and k not in extras:
                    extras.append(k)
        fieldnames = known + extras
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for rec in self._records:
                    writer.writerow(rec)
            QMessageBox.information(
                self, "Export CSV",
                f"Exported {len(self._records)} rows to:\n{path}"
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._refresh_timer.stop()
        super().closeEvent(event)


# ==============================================================================
# HELPERS
# ==============================================================================

def _fmt_time(ts: Any) -> str:
    """Format an ISO timestamp or epoch float to HH:MM:SS."""
    if ts is None:
        return "—"
    # Try ISO string first (R08 writes datetime.now(utc).isoformat())
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.strftime("%H:%M:%S")
        except ValueError:
            pass
    # Try epoch float
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%H:%M:%S")
    except (TypeError, ValueError, OSError, OverflowError):
        return str(ts)[:8]


def _fmt_num(v: Any, decimals: int = 2, prefix: str = "") -> str:
    try:
        return f"{prefix}{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(v: Any) -> str:
    try:
        return f"{float(v):+.2f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_bool(v: Any) -> str:
    if v is None:
        return "—"
    return "YES" if bool(v) else "NO"
