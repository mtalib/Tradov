#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG22_TradeAuditDialog.py
Purpose: Closed-trade audit dialog for paper-engine spreads. Renders the
         worker's full lifecycle log with sortable columns and a CSV export
         for ML training datasets.

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-04-17 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import csv
from datetime import datetime
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import COLORS

# ==============================================================================
# CONSTANTS
# ==============================================================================
COLUMNS = [
    "ID", "Opened", "Closed", "Hold", "Origin", "Structure",
    "Strikes", "Width", "Qty", "Credit", "Debit", "Comm",
    "P&L", "% Credit", "% Risk", "Reason",
    "Entry IV", "Entry IVR", "Entry SPY",
    "Pivot Dir", "Pivot Score", "Pivot Level",
]

# Column indices that should adopt P&L colouring.
_PNL_COLOR_COLS = (12, 13, 14)
# Column index of the Pivot Dir cell — receives the reasons/penalties tooltip.
_PIVOT_DIR_COL = 19


# ==============================================================================
# DIALOG
# ==============================================================================
class TradeAuditDialog(QDialog):
    """Modal-less dialog showing every closed paper spread.

    Each row is one closed-spread audit record emitted by R08 worker. All
    columns are sortable and the table can be exported to CSV for use as
    training data (each row contains entry context + realised outcome).
    """

    def __init__(self, closed_trades: list[dict], parent: Any = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Trade Audit — Closed Paper Spreads")
        self.setModal(False)
        self.resize(1280, 600)
        self._closed_trades = list(closed_trades or [])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Summary header
        self._summary_label = QLabel()
        self._summary_label.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 12px; font-weight: bold;"
        )
        layout.addWidget(self._summary_label)

        # Table
        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)  # disabled during populate, re-enabled after
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        export_btn = QPushButton("Export CSV…")
        export_btn.clicked.connect(self._export_csv)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._populate)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(export_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._populate()

    # ------------------------------------------------------------------ public
    def update_trades(self, closed_trades: list[dict]) -> None:
        """Replace the trade list and re-render. Lets the parent dashboard
        push new emits into an open dialog without reopening it."""
        self._closed_trades = list(closed_trades or [])
        self._populate()

    # ----------------------------------------------------------------- private
    def _populate(self) -> None:
        trades = self._closed_trades
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(trades))

        wins = sum(1 for t in trades if float(t.get("realized_pnl", 0.0)) > 0)
        losses = len(trades) - wins
        total_pnl = sum(float(t.get("realized_pnl", 0.0)) for t in trades)
        win_rate = (wins / len(trades) * 100.0) if trades else 0.0
        self._summary_label.setText(
            f"Closed: {len(trades)}   "
            f"Wins: {wins}  Losses: {losses}  "
            f"Win rate: {win_rate:.1f}%   "
            f"Total realised P&L: ${total_pnl:+,.2f}"
        )

        for row, t in enumerate(trades):
            self._fill_row(row, t)

        self._table.setSortingEnabled(True)
        self._table.resizeColumnsToContents()

    def _fill_row(self, row: int, t: dict) -> None:
        opened = _fmt_ts(t.get("opened_at"))
        closed = _fmt_ts(t.get("closed_at"))
        hold = _fmt_hold(t.get("hold_seconds", 0.0))
        # Use lifecycle_state when available (richer than the bare "origin" field),
        # falling back to origin for legacy audit records that pre-date the
        # StrategyLifecycleState enum.
        origin = str(t.get("lifecycle_state") or t.get("origin", "AI"))
        structure = str(t.get("structure", ""))
        short_k = float(t.get("short_strike", 0.0))
        long_k = float(t.get("long_strike", 0.0))
        leg = str(t.get("option_type", ""))[:1]
        strikes = f"{short_k:.0f}/{long_k:.0f}{leg}"
        width = float(t.get("wing_width", 0.0))
        qty = int(t.get("qty", 0))
        credit = float(t.get("credit", 0.0))
        debit_close = float(t.get("debit_to_close", 0.0))
        comm = float(t.get("open_commission", 0.0)) + float(t.get("close_commission", 0.0))
        pnl = float(t.get("realized_pnl", 0.0))
        pct_credit = float(t.get("return_on_credit_pct", 0.0))
        pct_risk = float(t.get("return_on_risk_pct", 0.0))
        reason = str(t.get("close_reason", ""))
        e_iv = t.get("entry_atm_iv")
        e_ivr = t.get("entry_iv_rank")
        e_spy = t.get("entry_spy")
        # S08 pivot mean-reversion signal snapshot (None when signal didn't fire).
        ps = t.get("pivot_signal") or {}
        pivot_dir = str(ps.get("direction", "")) if ps else "—"
        pivot_score = ps.get("score") if ps else None
        pivot_level_name = ps.get("level_name") if ps else None
        pivot_level_price = ps.get("level_price") if ps else None
        if pivot_level_name and pivot_level_price is not None:
            pivot_level = f"{pivot_level_name}@{float(pivot_level_price):.2f}"
        else:
            pivot_level = "—"
        pivot_score_str = (
            f"{float(pivot_score):.0f}" if pivot_score is not None else "—"
        )

        cells = [
            (str(t.get("id", "")), Qt.AlignmentFlag.AlignRight),
            (opened, Qt.AlignmentFlag.AlignLeft),
            (closed, Qt.AlignmentFlag.AlignLeft),
            (hold, Qt.AlignmentFlag.AlignRight),
            (origin, Qt.AlignmentFlag.AlignCenter),
            (structure, Qt.AlignmentFlag.AlignLeft),
            (strikes, Qt.AlignmentFlag.AlignRight),
            (f"{width:.0f}", Qt.AlignmentFlag.AlignRight),
            (str(qty), Qt.AlignmentFlag.AlignRight),
            (f"${credit:.2f}", Qt.AlignmentFlag.AlignRight),
            (f"${debit_close:.2f}", Qt.AlignmentFlag.AlignRight),
            (f"${comm:.2f}", Qt.AlignmentFlag.AlignRight),
            (f"${pnl:+,.2f}", Qt.AlignmentFlag.AlignRight),
            (f"{pct_credit:+.1f}%", Qt.AlignmentFlag.AlignRight),
            (f"{pct_risk:+.2f}%", Qt.AlignmentFlag.AlignRight),
            (reason, Qt.AlignmentFlag.AlignLeft),
            (_fmt_pct(e_iv), Qt.AlignmentFlag.AlignRight),
            (_fmt_num(e_ivr, 0), Qt.AlignmentFlag.AlignRight),
            (_fmt_num(e_spy, 2, prefix="$"), Qt.AlignmentFlag.AlignRight),
            (pivot_dir, Qt.AlignmentFlag.AlignCenter),
            (pivot_score_str, Qt.AlignmentFlag.AlignRight),
            (pivot_level, Qt.AlignmentFlag.AlignRight),
        ]

        pnl_color = QColor(
            COLORS["positive"] if pnl >= 0 else COLORS["negative"]
        )
        # Build tooltip from reasons/penalties when the pivot signal fired.
        pivot_tooltip = ""
        if ps:
            reasons = ps.get("reasons") or []
            penalties = ps.get("penalties") or []
            lines = []
            if reasons:
                lines.append("Reasons:")
                lines.extend(f"  {r}" for r in reasons)
            if penalties:
                lines.append("Penalties:")
                lines.extend(f"  {p}" for p in penalties)
            pivot_tooltip = "\n".join(lines)

        for col, (text, align) in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setTextAlignment(int(align) | int(Qt.AlignmentFlag.AlignVCenter))
            # Colour the P&L and percentage columns by sign for at-a-glance scan.
            if col in _PNL_COLOR_COLS:
                item.setForeground(pnl_color)
            if col == _PIVOT_DIR_COL and pivot_tooltip:
                item.setToolTip(pivot_tooltip)
            self._table.setItem(row, col, item)

    def _export_csv(self) -> None:
        if not self._closed_trades:
            QMessageBox.information(self, "Export CSV", "No closed trades to export.")
            return
        default_name = f"spyder_trade_audit_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export trade audit", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            # Use the union of keys across all trades so partial records still
            # export cleanly. Stable column order: known fields first, then
            # any extras in the order they're encountered.
            known = [
                "id", "opened_at", "closed_at", "hold_seconds", "origin",
                "structure", "option_type", "direction", "short_strike",
                "long_strike", "wing_width", "qty", "credit", "credit_received",
                "debit_to_close", "debit_paid", "open_commission",
                "close_commission", "realized_pnl", "return_on_credit_pct",
                "return_on_risk_pct", "max_loss_per_contract", "max_loss_dollars",
                "close_reason", "entry_atm_iv", "entry_iv_rank", "entry_spy",
                # Flattened pivot signal fields (from t['pivot_signal'] dict).
                "pivot_direction", "pivot_score", "pivot_confidence",
                "pivot_level_name", "pivot_level_price", "pivot_atr_distance",
                "pivot_reasons", "pivot_penalties",
            ]
            # Build flattened rows so the nested pivot_signal dict exports as
            # plain columns instead of a Python repr string.
            flat_rows = [_flatten_pivot(t) for t in self._closed_trades]
            extras: list[str] = []
            for t in flat_rows:
                for k in t.keys():
                    if k not in known and k not in extras:
                        extras.append(k)
            fieldnames = known + extras

            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
                writer.writeheader()
                for t in flat_rows:
                    writer.writerow(t)
            QMessageBox.information(
                self, "Export CSV", f"Exported {len(self._closed_trades)} rows to:\n{path}"
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))


# ==============================================================================
# HELPERS
# ==============================================================================
def _fmt_ts(epoch: Any) -> str:
    try:
        return datetime.fromtimestamp(float(epoch)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError, OverflowError):
        return "—"


def _fmt_hold(secs: Any) -> str:
    try:
        s = float(secs)
    except (TypeError, ValueError):
        return "—"
    if s < 60:
        return f"{s:.0f}s"
    if s < 3600:
        return f"{s / 60:.1f}m"
    if s < 86400:
        return f"{s / 3600:.1f}h"
    return f"{s / 86400:.1f}d"


def _fmt_pct(v: Any) -> str:
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return "—"


def _fmt_num(v: Any, decimals: int = 2, prefix: str = "") -> str:
    try:
        return f"{prefix}{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _flatten_pivot(t: dict) -> dict:
    """Return a copy of *t* with ``pivot_signal`` expanded to ``pivot_*`` keys.

    Reasons / penalties are joined with ``" | "`` so each ends up in a single
    CSV cell. The original ``pivot_signal`` key is dropped from the copy to
    avoid a duplicated nested-dict column in the export.
    """
    out = dict(t)
    ps = out.pop("pivot_signal", None) or {}
    if not ps:
        return out
    out["pivot_direction"] = ps.get("direction")
    out["pivot_score"] = ps.get("score")
    out["pivot_confidence"] = ps.get("confidence")
    out["pivot_level_name"] = ps.get("level_name")
    out["pivot_level_price"] = ps.get("level_price")
    out["pivot_atr_distance"] = ps.get("atr_distance")
    reasons = ps.get("reasons") or []
    penalties = ps.get("penalties") or []
    out["pivot_reasons"] = " | ".join(str(r) for r in reasons)
    out["pivot_penalties"] = " | ".join(str(p) for p in penalties)
    return out
