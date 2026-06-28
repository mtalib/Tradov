#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG60_PairTradingWidgets.py
Purpose: Pair trading dashboard widgets — positions, spread chart, scanner, risk

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    GUI widgets for the pair trading subsystem:
      - PairPositionsPanel: table of open pair positions with P&L
      - PairSpreadChart: live spread/z-score chart via matplotlib
      - PairScannerPanel: cointegration scan results table
      - PairRiskSummaryPanel: portfolio-level pair risk metrics
      - PairTradingDashboard: composite widget combining all four
"""

from __future__ import annotations

import html
from collections import deque
from datetime import datetime, UTC
import threading
from typing import Any

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QFrame,
    QComboBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from Tradov.TradovG_GUI.TradovG13_EnhancedWidgets import COLORS
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    CointegrationResult,
    PairPosition,
    PairScanResult,
    PairSide,
)
import pytz

_BODY_FONT_SIZE = 11
_NEWS_BODY_FONT_SIZE = 14
_TITLE_FONT_SIZE = 15
_TABLE_HEADER_FONT_SIZE = 14
_TABLE_HEADER_HEIGHT = 38
_NEWS_PANEL_MAX_AGE_SECONDS = 24 * 60 * 60
_TITLE_COLOR_PAPER = COLORS.get("warning", "#ff9800")
_TITLE_COLOR_REAL = COLORS.get("positive", "#00ff41")
_TITLE_COLOR_NEWS = COLORS.get("cyan", "#00ccff")
_NEWS_FRESHNESS_STALE_SECONDS = 5 * 60


def _news_item_key(news_item: Any) -> str:
    news_id = getattr(news_item, "id", "") or ""
    if news_id:
        return str(news_id)
    timestamp = getattr(news_item, "timestamp", None)
    ts_text = ""
    if hasattr(timestamp, "isoformat"):
        try:
            ts_text = timestamp.isoformat()
        except Exception:
            ts_text = ""
    return "|".join(
        str(part)
        for part in (
            ts_text,
            getattr(news_item, "source", ""),
            getattr(news_item, "title", ""),
        )
    )


def _news_item_is_recent(news_item: Any, max_age_seconds: int = 24 * 60 * 60) -> bool:
    timestamp = getattr(news_item, "timestamp", None)
    if not isinstance(timestamp, datetime):
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)
    age_seconds = (datetime.now(UTC) - timestamp).total_seconds()
    return 0.0 <= age_seconds <= max_age_seconds


def _money(v: float) -> str:
    if abs(v) >= 1e6:
        return f"${v / 1e6:.2f}M"
    if abs(v) >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:.2f}"


def _pnl_color(v: float) -> str:
    if v > 0:
        return COLORS.get("positive", "#00ff88")
    if v < 0:
        return COLORS.get("negative", "#ff4444")
    return COLORS.get("text", "#ffffff")


def _section_title_color(is_paper: bool) -> str:
    return _TITLE_COLOR_PAPER if is_paper else _TITLE_COLOR_REAL


def _set_section_title_mode(label: QLabel, base_title: str, is_paper: bool) -> None:
    suffix = "PAPER" if is_paper else "REAL"
    color = _section_title_color(is_paper)
    label.setText(f"{base_title} - {suffix}")
    label.setStyleSheet(
        f"QLabel#pairSectionTitle {{ color: {color}; font-size: {_TITLE_FONT_SIZE}px; font-weight: normal; "
        "background-color: #000000; padding: 0 0 3px 0; }"
    )


def _set_header_section_title_mode(label: QLabel, base_title: str, is_paper: bool) -> None:
    suffix = "PAPER" if is_paper else "REAL"
    color = _section_title_color(is_paper)
    label.setText(f"{base_title} - {suffix}")
    label.setStyleSheet(
        f"QLabel#pairSectionTitle {{ color: {color}; background-color: #000000; "
        f"padding: 6px 2px 6px 3px; font-size: {_TABLE_HEADER_FONT_SIZE}px; font-weight: 600; }}"
    )


def _set_news_title(label: QLabel) -> None:
    label.setText("BREAKING NEWS")
    label.setStyleSheet(
        f"QLabel#pairSectionTitle {{ color: {_TITLE_COLOR_NEWS}; font-size: {_TITLE_FONT_SIZE}px; font-weight: normal; "
        "background-color: #000000; padding: 0 0 3px 0; }"
    )


def _news_item_is_recent(news_item: Any, now: datetime | None = None) -> bool:
    timestamp = getattr(news_item, "timestamp", None)
    if not isinstance(timestamp, datetime):
        return False
    current = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)
    age_seconds = (current - timestamp).total_seconds()
    return 0.0 <= age_seconds <= _NEWS_PANEL_MAX_AGE_SECONDS


def _news_item_timestamp_utc(news_item: Any) -> datetime | None:
    """Return the best available UTC timestamp for a news item."""
    timestamp = getattr(news_item, "timestamp", None)
    received_at = getattr(news_item, "received_at", None)
    has_time = bool(getattr(news_item, "timestamp_has_time", True))
    chosen = timestamp if has_time else received_at or timestamp
    if not isinstance(chosen, datetime):
        return None
    if chosen.tzinfo is None:
        return chosen.replace(tzinfo=UTC)
    return chosen.astimezone(UTC)


def _format_news_freshness(news_item: Any, now: datetime | None = None) -> str:
    """Return a compact age string for the newest visible headline."""
    timestamp = _news_item_timestamp_utc(news_item)
    if timestamp is None:
        return "age: unknown"
    current = now or datetime.now(UTC)
    age_seconds = max(0, int((current - timestamp).total_seconds()))
    if age_seconds < 60:
        return f"age: {age_seconds}s"
    minutes, seconds = divmod(age_seconds, 60)
    if minutes < 60:
        return f"age: {minutes}m {seconds:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"age: {hours}h {minutes:02d}m"


def _style_section_title(label: QLabel, base_title: str, is_paper: bool = True) -> None:
    font = label.font()
    font.setPixelSize(_TITLE_FONT_SIZE)
    font.setBold(False)
    label.setFont(font)
    label.setObjectName("pairSectionTitle")
    label.setFixedHeight(_TITLE_FONT_SIZE + 6)
    _set_section_title_mode(label, base_title, is_paper)


def _style_header_section_title(label: QLabel, base_title: str, is_paper: bool = True) -> None:
    font = label.font()
    font.setPixelSize(_TABLE_HEADER_FONT_SIZE)
    font.setBold(True)
    label.setFont(font)
    label.setObjectName("pairSectionTitle")
    label.setFixedHeight(_TABLE_HEADER_HEIGHT)
    _set_header_section_title_mode(label, base_title, is_paper)


def _style_compact_section_title(label: QLabel, base_title: str, is_paper: bool = True) -> None:
    font = label.font()
    font.setPixelSize(_TITLE_FONT_SIZE - 1)
    font.setBold(False)
    label.setFont(font)
    label.setObjectName("pairSectionTitle")
    label.setFixedHeight(_TITLE_FONT_SIZE + 1)
    suffix = "PAPER" if is_paper else "REAL"
    color = _section_title_color(is_paper)
    label.setText(f"{base_title} - {suffix}")
    label.setStyleSheet(
        f"QLabel#pairSectionTitle {{ color: {color}; font-size: {_TITLE_FONT_SIZE - 1}px; font-weight: normal; "
        "background-color: #000000; padding: 0; margin: 0; }}"
    )


def _pair_signed_notional(pos: PairPosition) -> float:
    long_a = abs(pos.quantity_a * pos.current_price_a)
    long_b = abs(pos.quantity_b * pos.current_price_b)
    gross = long_a + long_b
    if pos.pair_side == PairSide.LONG_SHORT:
        return gross
    if pos.pair_side == PairSide.SHORT_LONG:
        return -gross
    return gross


def _pair_side_label(pos: PairPosition) -> str:
    if pos.pair_side == PairSide.SHORT_LONG:
        return "NEGATIVE"
    return "POSITIVE"


def _pair_side_color(pos: PairPosition) -> str:
    if pos.pair_side == PairSide.SHORT_LONG:
        return COLORS.get("negative", "#ff4444")
    return COLORS.get("positive", "#00ff88")


def _pair_leg_display_text(pos: PairPosition) -> str:
    symbol_a = str(pos.symbol_a or "").strip()
    symbol_b = str(pos.symbol_b or "").strip()
    if symbol_a and symbol_b:
        return f"{symbol_a} / {symbol_b}"

    pair_key = str(pos.pair_key or "").strip()
    if pair_key:
        return pair_key
    return "-"


def _pair_leg_color(pos: PairPosition, leg: str) -> str:
    if pos.pair_side == PairSide.SHORT_LONG:
        return COLORS.get("negative", "#ff4444") if leg == "a" else COLORS.get("positive", "#00ff88")
    return COLORS.get("positive", "#00ff88") if leg == "a" else COLORS.get("negative", "#ff4444")


def _pair_leg_rich_text(pos: PairPosition) -> str:
    symbol_a = str(pos.symbol_a or "").strip()
    symbol_b = str(pos.symbol_b or "").strip()
    if not (symbol_a and symbol_b):
        return html.escape(_pair_leg_display_text(pos))

    color_a = _pair_leg_color(pos, "a")
    color_b = _pair_leg_color(pos, "b")
    return (
        f"<span style='color:{color_a}; font-weight:600;'>{html.escape(symbol_a)}</span>"
        f"<span style='color:#808080;'> / </span>"
        f"<span style='color:{color_b}; font-weight:600;'>{html.escape(symbol_b)}</span>"
    )


def _pair_entry_cost(pos: PairPosition) -> float:
    return abs(pos.quantity_a * pos.entry_price_a) + abs(pos.quantity_b * pos.entry_price_b)


def _pair_funds_held(pos: PairPosition) -> float:
    metadata = pos.metadata or {}
    direct = metadata.get("cash_held_dollars")
    if direct in (None, ""):
        direct = metadata.get("buying_power_held")
    if direct in (None, ""):
        direct = metadata.get("max_loss_dollars")
    if direct in (None, ""):
        direct = metadata.get("funds_held_dollars")
    if direct not in (None, ""):
        try:
            return abs(float(direct))
        except (TypeError, ValueError):
            pass
    return _pair_entry_cost(pos)


def _apply_pair_table_chrome(
    table: QTableWidget,
    row_height: int,
    fixed_height_padding: int,
    *,
    cell_font_size: int = 13,
) -> None:
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setDefaultSectionSize(row_height)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    table.setFixedHeight(table.horizontalHeader().sizeHint().height() + (row_height * 3) + fixed_height_padding)
    font = table.font()
    font.setPointSize(cell_font_size)
    table.setFont(font)
    table.setStyleSheet(
        f"""
            QTableWidget {{
                background-color: #000000;
                color: {COLORS.get('text', '#ffffff')};
                gridline-color: #333333;
                border: 1px solid #1f1f1f;
                font-size: {cell_font_size}px;
                selection-background-color: #111111;
            }}
            QTableWidget::item {{
                background-color: #0a0a0a;
                border-bottom: 1px solid #202020;
                font-size: {cell_font_size}px;
            }}
            QTableWidget::item:alternate {{
                background-color: #111111;
            }}
            QHeaderView::section {{
                background-color: #000000;
                color: {COLORS.get('text', '#ffffff')};
                border: 1px solid #1f1f1f;
                padding: 2px;
                font-size: {_BODY_FONT_SIZE + 1}px;
                font-weight: 600;
            }}
        """
    )


def _scanner_rank_label(rank: Any) -> str:
    try:
        rank_int = int(rank)
    except (TypeError, ValueError):
        return str(rank)
    return {
        1: "First",
        2: "Second",
        3: "Third",
    }.get(rank_int, str(rank_int))


def _style_scanner_pair_item(item: QTableWidgetItem) -> None:
    item.setForeground(QColor(COLORS.get("cyan", "#00ffff")))


def _scan_result_cost(result: CointegrationResult) -> float | None:
    metadata = result.metadata or {}
    for key in (
        "entry_cost_dollars",
        "cost_dollars",
        "estimated_cost_dollars",
        "estimated_notional_dollars",
        "notional_value",
    ):
        value = metadata.get(key)
        if value in (None, ""):
            continue
        try:
            return abs(float(value))
        except (TypeError, ValueError):
            continue
    return None


def _scan_result_funds_held(result: CointegrationResult) -> float | None:
    metadata = result.metadata or {}
    for key in (
        "cash_held_dollars",
        "buying_power_held",
        "max_loss_dollars",
        "reserved_funds_dollars",
        "funds_held_dollars",
    ):
        value = metadata.get(key)
        if value in (None, ""):
            continue
        try:
            return abs(float(value))
        except (TypeError, ValueError):
            continue
    return _scan_result_cost(result)


def _build_scaffold_widget(column_labels: list[str], row_height: int, row_labels: list[str]) -> QWidget:
    widget = QWidget()
    widget.setStyleSheet("background-color: #000000;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)

    header = QWidget()
    header_layout = QHBoxLayout(header)
    header_layout.setContentsMargins(0, 0, 0, 0)
    header_layout.setSpacing(0)
    for label_text in column_labels:
        label = QLabel(label_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "color: #e0e0e0; background-color: #000000; border: 1px solid #2d2d2d; "
            "padding: 6px 2px; font-size: 14px; font-weight: 600;"
        )
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        label.setFixedHeight(38)
        header_layout.addWidget(label, 1)
    layout.addWidget(header)

    for _row_index, row_label in enumerate(row_labels, start=1):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        for col_index, _col_name in enumerate(column_labels):
            cell = QLabel(row_label if col_index == 0 else "")
            cell.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.setStyleSheet(
                "color: #cfcfcf; background-color: #000000; border: 1px solid #2a2a2a; "
                "font-size: 13px; padding: 12px 4px;"
            )
            cell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            cell.setFixedHeight(row_height)
            row_layout.addWidget(cell, 1)
        layout.addWidget(row_widget)

    widget.setMinimumHeight(38 + (row_height * len(row_labels)) + 28)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return widget


class PairPositionsPanel(QWidget):
    flatten_requested = Signal(str)
    _ROW_HEIGHT = 20
    _SCAFFOLD_TEXT = "Waiting for positions..."

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 1)
        layout.setSpacing(1)
        self.setStyleSheet("background-color: #000000;")
        self.setMinimumHeight(130)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self._title_label = QLabel()
        _style_section_title(self._title_label, "PAIR POSITIONS")
        header.addWidget(self._title_label)
        header.addStretch()
        self._count_label = QLabel("0 open")
        self._count_label.setStyleSheet(f"color: {COLORS.get('cyan', '#00ccff')}; font-size: {_BODY_FONT_SIZE}px;")
        header.addWidget(self._count_label)
        layout.addLayout(header)

        self._open_pairs_label = QLabel("Open Pair Count: 0")
        self._gross_notional_label = QLabel("Gross Notional: $0")
        self._cost_label = QLabel("Cost: $0")
        self._funds_held_label = QLabel("Funds Held by Broker: $0")
        self._net_exposure_label = QLabel("Net Exposure: $0")
        for label in (
            self._open_pairs_label,
            self._gross_notional_label,
            self._cost_label,
            self._funds_held_label,
            self._net_exposure_label,
        ):
            label.setStyleSheet(f"color: {COLORS.get('text_dim', '#888888')}; font-size: {_BODY_FONT_SIZE}px;")

        self._table = QTableWidget(0, 10)
        self._table.setHorizontalHeaderLabels([
            "SIDE", "PAIR", "QTY-A", "QTY-B", "Z-SCORE",
            "SPREAD", "COST", "FUNDS-HELD", "P&L", "DURATION",
        ])
        _apply_pair_table_chrome(self._table, self._ROW_HEIGHT, 14, cell_font_size=13)
        self._table.verticalHeader().setSectionsClickable(True)
        self._table.verticalHeader().sectionClicked.connect(self._on_row_header_clicked)
        layout.addWidget(self._table)

        self._empty_scaffold = None
        self._row_pair_keys: list[str] = []
        self._table.setVisible(True)
        self._set_placeholder_rows(0)

        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_trading_mode(self, is_paper: bool) -> None:
        _set_section_title_mode(self._title_label, "PAIR POSITIONS", is_paper)

    def _set_placeholder_rows(self, row_count: int) -> None:
        self._table.clearSpans()
        visible_rows = max(3, row_count)
        self._table.setRowCount(visible_rows)
        for row in range(visible_rows):
            self._table.setRowHeight(row, self._ROW_HEIGHT)
            if self._table.cellWidget(row, 1) is not None:
                self._table.removeCellWidget(row, 1)
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    self._table.setItem(row, col, item)
                else:
                    item.setText("")
                item.setBackground(QColor("#000000"))
                item.setForeground(QColor("#5f5f5f"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if row >= row_count:
                marker = self._table.item(row, 0)
                if marker is not None:
                    marker.setText(str(row + 1))

    def _apply_scaffold_row(self, row: int, text: str) -> None:
        self._table.setSpan(row, 0, 1, self._table.columnCount())
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item is None:
                item = QTableWidgetItem("")
                self._table.setItem(row, col, item)
            item.setForeground(QColor("#666666"))
            item.setBackground(QColor("#101010"))
            item.setText("")
        first_item = self._table.item(row, 0)
        if first_item is None:
            first_item = QTableWidgetItem("")
            self._table.setItem(row, 0, first_item)
        first_item.setText(text)
        first_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        first_item.setForeground(QColor("#666666"))

    def _on_row_header_clicked(self, row: int) -> None:
        if row < 0 or row >= len(self._row_pair_keys):
            return
        pair_key = self._row_pair_keys[row]
        if not pair_key:
            return
        self.flatten_requested.emit(pair_key)

    def update_positions(self, positions: dict[str, PairPosition]) -> None:
        has_positions = bool(positions)
        self._table.setVisible(True)
        if self._empty_scaffold is not None:
            self._empty_scaffold.setVisible(False)
        self._row_pair_keys = []
        if not has_positions:
            self._set_placeholder_rows(0)
            self._count_label.setText("0 open")
            self._open_pairs_label.setText("Open Pair Count: 0")
            self._gross_notional_label.setText("Gross Notional: $0")
            self._cost_label.setText("Cost: $0")
            self._funds_held_label.setText("Funds Held by Broker: $0")
            self._net_exposure_label.setText("Net Exposure: $0")
            return
        self._row_pair_keys = [pair_key for pair_key, _ in positions.items()]
        self._set_placeholder_rows(len(positions))
        for row, (pair_key, pos) in enumerate(positions.items()):
            self._table.setRowHeight(row, self._ROW_HEIGHT)
            side_item = QTableWidgetItem(_pair_side_label(pos))
            side_item.setForeground(QColor(_pair_side_color(pos)))
            self._table.setItem(row, 0, side_item)
            self._table.setItem(row, 2, QTableWidgetItem(str(pos.quantity_a)))
            self._table.setItem(row, 3, QTableWidgetItem(str(pos.quantity_b)))
            pair_label = QLabel(_pair_leg_rich_text(pos))
            pair_label.setTextFormat(Qt.TextFormat.RichText)
            pair_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pair_label.setToolTip(pair_key)
            pair_label.setStyleSheet(
                "background-color: transparent; color: #ffffff; font-size: 13px; font-weight: 600;"
            )
            self._table.setCellWidget(row, 1, pair_label)

            z_item = QTableWidgetItem(f"{pos.current_z:.2f}")
            z_color = _pnl_color(-pos.current_z) if pos.pair_side == PairSide.LONG_SHORT else _pnl_color(pos.current_z)
            z_item.setForeground(QColor(z_color))
            self._table.setItem(row, 4, z_item)

            self._table.setItem(row, 5, QTableWidgetItem(f"{pos.current_spread:.4f}"))
            pair_cost = _pair_entry_cost(pos)
            funds_held = _pair_funds_held(pos)
            cost_item = QTableWidgetItem(_money(pair_cost))
            cost_item.setForeground(QColor(COLORS.get("text_dim", "#888888")))
            self._table.setItem(row, 6, cost_item)

            funds_item = QTableWidgetItem(_money(funds_held))
            funds_item.setForeground(QColor(COLORS.get("orange", "#ff8800")))
            self._table.setItem(row, 7, funds_item)

            pnl_item = QTableWidgetItem(_money(pos.unrealized_pnl))
            pnl_item.setForeground(QColor(_pnl_color(pos.unrealized_pnl)))
            self._table.setItem(row, 8, pnl_item)

            dur = pos.duration
            dur_str = f"{dur.days}d {dur.seconds // 3600}h" if dur else "-"
            self._table.setItem(row, 9, QTableWidgetItem(dur_str))

        self._count_label.setText(f"{len(positions)} open")
        total_notional = sum(
            abs(p.quantity_a * p.current_price_a) + abs(p.quantity_b * p.current_price_b)
            for p in positions.values()
        )
        total_cost = sum(_pair_entry_cost(p) for p in positions.values())
        total_funds_held = sum(_pair_funds_held(p) for p in positions.values())

        signed_notional = sum(_pair_signed_notional(p) for p in positions.values())
        self._open_pairs_label.setText(f"Open Pair Count: {len(positions)}")
        self._gross_notional_label.setText(f"Gross Notional: {_money(total_notional)}")
        self._cost_label.setText(f"Cost: {_money(total_cost)}")
        self._funds_held_label.setText(f"Funds Held by Broker: {_money(total_funds_held)}")
        self._net_exposure_label.setText(f"Net Exposure: {_money(signed_notional)}")


class PairSpreadChart(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(figsize=(6, 3), facecolor="#000000")
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setMinimumHeight(180)
        self._canvas.setMaximumHeight(250)
        layout.addWidget(self._canvas)

        self._pair_key: str = ""
        self._spread_history: list[float] = []
        self._z_history: list[float] = []
        self._entry_z: float = 2.0
        self._exit_z: float = 0.5
        self._max_points: int = 200

        self.setLayout(layout)

    def set_pair(self, pair_key: str, entry_z: float = 2.0, exit_z: float = 0.5) -> None:
        self._pair_key = pair_key
        self._entry_z = entry_z
        self._exit_z = exit_z
        self._spread_history.clear()
        self._z_history.clear()

    def append_data(self, z_score: float, spread: float) -> None:
        self._z_history.append(z_score)
        self._spread_history.append(spread)
        if len(self._z_history) > self._max_points:
            self._z_history = self._z_history[-self._max_points:]
            self._spread_history = self._spread_history[-self._max_points:]
        self._redraw()

    def _redraw(self) -> None:
        self._figure.clear()
        bg = "#000000"
        text_color = COLORS.get("text", "#ffffff")
        grid_color = "#222222"

        ax1 = self._figure.add_subplot(211)
        ax1.set_facecolor(bg)
        ax1.tick_params(colors=text_color, labelsize=8)
        if self._z_history:
            ax1.plot(self._z_history, color=COLORS.get("cyan", "#00ccff"), linewidth=1)
            ax1.axhline(y=self._entry_z, color=COLORS.get("negative", "#ff4444"), linestyle="--", linewidth=0.8)
            ax1.axhline(y=-self._entry_z, color=COLORS.get("negative", "#ff4444"), linestyle="--", linewidth=0.8)
            ax1.axhline(y=self._exit_z, color=COLORS.get("positive", "#00ff88"), linestyle=":", linewidth=0.8)
            ax1.axhline(y=-self._exit_z, color=COLORS.get("positive", "#00ff88"), linestyle=":", linewidth=0.8)
            ax1.axhline(y=0, color=grid_color, linewidth=0.5)
        title = f"Z-Score: {self._pair_key}" if self._pair_key else "Z-Score"
        ax1.set_title(title, color=text_color, fontsize=9, pad=2)
        ax1.grid(True, alpha=0.2, color=grid_color)

        ax2 = self._figure.add_subplot(212)
        ax2.set_facecolor(bg)
        ax2.tick_params(colors=text_color, labelsize=8)
        if self._spread_history:
            ax2.plot(self._spread_history, color=COLORS.get("orange", "#ff8800"), linewidth=1)
        ax2.set_title("Spread", color=text_color, fontsize=9, pad=2)
        ax2.grid(True, alpha=0.2, color=grid_color)

        self._figure.tight_layout(pad=1.0)
        self._canvas.draw_idle()


class PairScannerPanel(QWidget):
    _ROW_HEIGHT = 20
    _SCAFFOLD_TEXT = "Waiting for scanner results..."
    _SCAN_IN_PROGRESS_TEXT = "SCANNING IN PROGRESS"
    _SCAN_HALTED_TEXT = "SCANNING HALTED"
    _SCAN_WARMING_TEXT = "SCANNING WARMING UP"
    bundle_selection_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(1)
        self.setStyleSheet("background-color: #000000;")
        self.setMinimumHeight(114)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(4)
        self._title_label = QLabel()
        _style_section_title(self._title_label, "SCANNER RESULTS")
        header.addWidget(self._title_label)
        header.addWidget(QLabel(" | "))
        self._scan_label = QLabel(self._SCAN_IN_PROGRESS_TEXT)
        self._scan_label.setStyleSheet(f"color: {COLORS.get('text_dim', '#888888')}; font-size: {_BODY_FONT_SIZE}px;")
        header.addWidget(self._scan_label)
        self._status_badge = QLabel("EMPTY")
        self._status_badge.setMinimumWidth(54)
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_badge.setStyleSheet(
            "background-color: #2a2a2a; color: #aaaaaa; border: 1px solid #3a3a3a; "
            f"font-size: {_BODY_FONT_SIZE}px; padding: 1px 6px; font-weight: 700;"
        )
        header.addWidget(self._status_badge)
        header.addStretch()
        self._bundle_combo = QComboBox()
        self._bundle_combo.setMinimumWidth(180)
        self._bundle_combo.setStyleSheet(
            "QComboBox { background-color: #101010; color: #ffffff; border: 1px solid #2a2a2a; padding: 2px 8px; }"
            "QComboBox QAbstractItemView { background-color: #111111; color: #ffffff; selection-background-color: #333333; }"
        )
        self._bundle_combo.currentIndexChanged.connect(lambda *_: self._emit_bundle_selection_changed())
        header.addWidget(self._bundle_combo)
        layout.addLayout(header)
        layout.addSpacing(2)

        self._table = QTableWidget(0, 10)
        self._table.setHorizontalHeaderLabels([
            "RANK", "PAIR", "P-VALUE", "SCORE", "HALF-LIFE", "HEDGE RATIO",
            "COST", "FUNDS-HELD", "SPREAD STD", "TRADEABLE",
        ])
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _apply_pair_table_chrome(self._table, self._ROW_HEIGHT, 14, cell_font_size=13)
        layout.addWidget(self._table)

        self._empty_scaffold = None
        self._table.setVisible(True)
        self._set_placeholder_rows(0)

        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._bundle_combo.addItem("AUTO")
        self._bundle_preview_name = ""
        self._bundle_preview_pair_keys: tuple[str, ...] = ()

    def set_trading_mode(self, is_paper: bool) -> None:
        _set_section_title_mode(self._title_label, "SCANNER RESULTS", is_paper)

    def set_bundle_choices(self, bundle_names: list[str] | tuple[str, ...], *, selected_bundle: str = "") -> None:
        """Populate bundle choices and select the current override."""
        current = str(selected_bundle or "").strip()
        names = [str(name).strip() for name in bundle_names if str(name).strip()]
        self._bundle_combo.blockSignals(True)
        try:
            self._bundle_combo.clear()
            self._bundle_combo.addItem("AUTO")
            for name in names:
                self._bundle_combo.addItem(name)
            index = 0
            if current:
                found = self._bundle_combo.findText(current)
                if found >= 0:
                    index = found
            self._bundle_combo.setCurrentIndex(index)
        finally:
            self._bundle_combo.blockSignals(False)
        self._emit_bundle_selection_changed()

    def selected_bundle_name(self) -> str:
        text = str(self._bundle_combo.currentText() or "").strip()
        return "" if text.upper() == "AUTO" else text

    def set_bundle_preview(self, bundle_name: str, pair_keys: list[str] | tuple[str, ...] | None = None) -> None:
        """Store the bundle used for empty-state preview rows."""
        self._bundle_preview_name = str(bundle_name or "").strip()
        self._bundle_preview_pair_keys = tuple(
            str(key or "").strip().upper()
            for key in (pair_keys or ())
            if str(key or "").strip()
        )

    def _emit_bundle_selection_changed(self) -> None:
        self.bundle_selection_changed.emit(self.selected_bundle_name())

    def set_scan_status(self, status: str) -> None:
        """Set the scanner status label independently from scan results."""
        normalized = str(status or "").strip().upper()
        if normalized in {"WARMING", "WARMING_UP", "WARMUP"}:
            self._scan_label.setText(self._SCAN_WARMING_TEXT)
            self._set_status_badge("WARMING", "#7a5c00", "#ffd86b")
        elif normalized in {"HALTED", "STOPPED", "PAUSED"}:
            self._scan_label.setText(self._SCAN_HALTED_TEXT)
            self._set_status_badge("HALTED", "#7a1f1f", "#ff8b8b")
        elif normalized in {"PREVIEW", "PREVIEW_MODE"}:
            self._scan_label.setText("SCANNER PREVIEW")
            self._set_status_badge("PREVIEW", "#2e3a1d", "#c6ff7a")
        elif normalized in {"ACTIVE", "RUNNING", "IN_PROGRESS"}:
            self._scan_label.setText(self._SCAN_IN_PROGRESS_TEXT)
            self._set_status_badge("LIVE", "#1f5f2a", "#8bffb1")

    def _set_status_badge(self, text: str, background: str, foreground: str) -> None:
        self._status_badge.setText(text)
        self._status_badge.setStyleSheet(
            f"background-color: {background}; color: {foreground}; border: 1px solid {foreground}; "
            f"font-size: {_BODY_FONT_SIZE}px; padding: 2px 8px; font-weight: 700;"
        )

    @staticmethod
    def _pair_score_color(result: PairScanResult, row_index: int) -> QColor:
        if result.is_tradeable:
            if result.p_value <= 0.05 or result.ranking_score >= 1.0:
                return QColor(COLORS.get("positive", "#00ff88"))
            return QColor(COLORS.get("orange", "#ff9800"))
        if row_index == 0 and result.ranking_score > 0.0:
            return QColor(COLORS.get("yellow", "#ffd000"))
        return QColor(COLORS.get("negative", "#ff4444"))

    def _set_placeholder_rows(self, row_count: int) -> None:
        self._table.clearSpans()
        visible_rows = max(3, row_count)
        self._table.setRowCount(visible_rows)
        for row in range(visible_rows):
            self._table.setRowHeight(row, self._ROW_HEIGHT)
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item is None:
                    item = QTableWidgetItem("")
                    self._table.setItem(row, col, item)
                else:
                    item.setText("")
                item.setBackground(QColor("#000000"))
                item.setForeground(QColor("#5f5f5f"))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if row >= row_count:
                marker = self._table.item(row, 0)
                if marker is not None:
                    marker.setText(str(row + 1))

    def _apply_scaffold_row(self, row: int, text: str) -> None:
        self._table.setSpan(row, 0, 1, self._table.columnCount())
        for col in range(self._table.columnCount()):
            item = self._table.item(row, col)
            if item is None:
                item = QTableWidgetItem("")
                self._table.setItem(row, col, item)
            item.setForeground(QColor("#666666"))
            item.setBackground(QColor("#101010"))
            item.setText("")
        first_item = self._table.item(row, 0)
        if first_item is None:
            first_item = QTableWidgetItem("")
            self._table.setItem(row, 0, first_item)
        first_item.setText(text)
        first_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        first_item.setForeground(QColor("#666666"))

    @staticmethod
    def _format_decision_text(decision_state: str, decision_reason: str) -> str:
        state = str(decision_state or "").strip().upper()
        reason = str(decision_reason or "").strip()
        if not state and not reason:
            return "-"
        if state and reason:
            return f"{state} ({reason})"
        return state or reason

    def _set_scan_meta(
        self,
        *,
        candidates: str,
        tradeable: str,
        best_score: str,
        best_pair: str,
        decision_state: str = "",
        decision_reason: str = "",
    ) -> None:
        return

    def update_scan(self, scan_result: PairScanResult, market_hours_open: bool | None = None) -> None:
        pairs = (scan_result.ranked_pairs or scan_result.validated_pairs)[:3]
        preview_pairs = list(self._bundle_preview_pair_keys[:3])
        scanner_active = bool(market_hours_open)
        self._set_placeholder_rows(len(pairs))
        if not scanner_active:
            self._scan_label.setText(self._SCAN_HALTED_TEXT)
        else:
            self._scan_label.setText(self._SCAN_IN_PROGRESS_TEXT)
        self._table.setVisible(True)
        if self._empty_scaffold is not None:
            self._empty_scaffold.setVisible(False)
        if not pairs:
            if preview_pairs:
                if not scanner_active:
                    self._set_status_badge("HALTED", "#7a1f1f", "#ff8b8b")
                    self._scan_label.setText(self._SCAN_HALTED_TEXT)
                else:
                    self._set_status_badge("PREVIEW", "#2e3a1d", "#c6ff7a")
                self._set_placeholder_rows(len(preview_pairs))
                if scanner_active:
                    self._scan_label.setText("SCANNER PREVIEW")
                self._set_scan_meta(
                    candidates=f"{len(preview_pairs)} (preview)",
                    tradeable="-",
                    best_score="-",
                    best_pair=f"{self._bundle_preview_name or '-'} (preview)",
                    decision_state="PREVIEW",
                    decision_reason="awaiting_scan",
                )
                for row, pair_key in enumerate(preview_pairs):
                    self._table.setRowHeight(row, self._ROW_HEIGHT)
                    self._table.setItem(row, 0, QTableWidgetItem(_scanner_rank_label(row + 1)))
                    pair_item = QTableWidgetItem(pair_key)
                    _style_scanner_pair_item(pair_item)
                    self._table.setItem(row, 1, pair_item)
                    for col in range(2, 9):
                        self._table.setItem(row, col, QTableWidgetItem("-"))
                    tradeable_item = QTableWidgetItem("PREVIEW")
                    tradeable_item.setForeground(QColor(COLORS.get("text_dim", "#888888")))
                    self._table.setItem(row, 9, tradeable_item)
                return
            self._set_status_badge("EMPTY", "#2a2a2a", "#aaaaaa")
            if not scanner_active:
                self._scan_label.setText(self._SCAN_HALTED_TEXT)
            total_candidates = int(getattr(scan_result, "total_candidates", 0) or 0)
            decision_state = str(getattr(scan_result, "decision_state", "unknown") or "unknown").upper()
            decision_reason = str(getattr(scan_result, "decision_reason", "") or "").strip()
            bundle_name = str(getattr(scan_result, "bundle_name", "") or "").strip()
            bundle_reason = str(getattr(scan_result, "bundle_reason", "") or "").strip()
            bundle_score = float(getattr(scan_result, "bundle_score", 0.0) or 0.0)
            self._set_scan_meta(
                candidates=str(total_candidates),
                tradeable="0",
                best_score="-",
                best_pair=(
                    f"{bundle_name or '-'}"
                    + (f" ({bundle_reason}, {bundle_score:.2f})" if bundle_name else "")
                    + (f" [{decision_state}{f' - {decision_reason}' if decision_reason else ''}]" if decision_state else "")
                ),
                decision_state=decision_state,
                decision_reason=decision_reason,
            )
            return
        tradeable_count = 0
        best_score = None
        for row, result in enumerate(pairs):
            metadata = getattr(result, "metadata", {}) or {}
            rank = metadata.get("rank", row + 1)
            self._table.setRowHeight(row, self._ROW_HEIGHT)
            self._table.setItem(row, 0, QTableWidgetItem(_scanner_rank_label(rank)))
            pair_item = QTableWidgetItem(result.pair_key)
            _style_scanner_pair_item(pair_item)
            self._table.setItem(row, 1, pair_item)

            p_item = QTableWidgetItem(f"{result.p_value:.4f}")
            p_item.setForeground(self._pair_score_color(result, row))
            self._table.setItem(row, 2, p_item)

            score_item = QTableWidgetItem(f"{result.ranking_score:.3f}")
            score_item.setForeground(QColor(COLORS.get("cyan", "#00ccff")))
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, score_item)
            if best_score is None or result.ranking_score > best_score:
                best_score = result.ranking_score

            self._table.setItem(row, 4, QTableWidgetItem(f"{result.half_life:.1f}d"))
            self._table.setItem(row, 5, QTableWidgetItem(f"{result.hedge_ratio:.4f}"))
            cost_value = _scan_result_cost(result)
            cost_item = QTableWidgetItem(_money(cost_value)) if cost_value is not None else QTableWidgetItem("-")
            cost_item.setForeground(QColor(COLORS.get("text_dim", "#888888")))
            self._table.setItem(row, 6, cost_item)

            held_value = _scan_result_funds_held(result)
            held_item = QTableWidgetItem(_money(held_value)) if held_value is not None else QTableWidgetItem("-")
            held_item.setForeground(QColor(COLORS.get("orange", "#ff8800")))
            self._table.setItem(row, 7, held_item)

            self._table.setItem(row, 8, QTableWidgetItem(f"{result.spread_std:.4f}"))

            tradeable_item = QTableWidgetItem("YES" if result.is_tradeable else "NO")
            if result.is_tradeable:
                tradeable_count += 1
            tradeable_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if result.is_tradeable:
                tradeable_item.setForeground(QColor(COLORS.get("positive", "#00ff88")))
                tradeable_item.setBackground(QColor("#123a25"))
            else:
                tradeable_item.setForeground(QColor(COLORS.get("text_dim", "#888888")))
                tradeable_item.setBackground(QColor("#1b1b1b"))
            self._table.setItem(row, 9, tradeable_item)

        total_candidates = scan_result.total_candidates
        if scanner_active:
            self._set_status_badge("LIVE", "#1f5f2a", "#8bffb1")
            self._scan_label.setText(self._SCAN_IN_PROGRESS_TEXT)
        else:
            self._set_status_badge("HALTED", "#7a1f1f", "#ff8b8b")
            self._scan_label.setText(self._SCAN_HALTED_TEXT)
        bundle_name = str(getattr(scan_result, "bundle_name", "") or "").strip()
        bundle_reason = str(getattr(scan_result, "bundle_reason", "") or "").strip()
        bundle_score = float(getattr(scan_result, "bundle_score", 0.0) or 0.0)
        best_pair = getattr(scan_result, "best_pair_key", "") or "-"
        best_age = float(getattr(scan_result, "scan_age_seconds", 0.0) or 0.0)
        decision_state = str(getattr(scan_result, "decision_state", "unknown") or "unknown").upper()
        decision_reason = str(getattr(scan_result, "decision_reason", "") or "").strip()
        self._set_scan_meta(
            candidates=str(total_candidates),
            tradeable=str(tradeable_count),
            best_score=f"{best_score:.3f}" if best_score is not None else "-",
            best_pair=(
                f"{best_pair} @ {best_age:.0f}s"
                + (f" | {bundle_name}" if bundle_name else "")
                + (f" ({bundle_reason}, {bundle_score:.2f})" if bundle_name else "")
                + (f" [{decision_state}{f' - {decision_reason}' if decision_reason else ''}]" if decision_state else "")
            ),
            decision_state=decision_state,
            decision_reason=decision_reason,
        )


class PairRiskSummaryPanel(QWidget):
    _ROW_HEIGHT = 20

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 1)
        layout.setSpacing(1)
        self.setStyleSheet("background-color: #000000;")

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(2)
        self._title_label = QLabel()
        _style_compact_section_title(self._title_label, "PAIR RISK SUMMARY")
        header.addWidget(self._title_label)
        header.addStretch()
        layout.addLayout(header)

        self._table = QTableWidget(5, 3)
        self._table.setHorizontalHeaderLabels([
            "PORTFOLIO-LEVEL RISK METRICS",
            "DESCRIPTION",
            "VALUE",
        ])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(2, 220)
        self._table.verticalHeader().setDefaultSectionSize(self._ROW_HEIGHT)
        self._table.verticalHeader().setVisible(True)
        self._table.verticalHeader().setSectionsClickable(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._table.setFixedHeight(self._table.horizontalHeader().sizeHint().height() + (self._ROW_HEIGHT * 6) + 14)
        table_font = self._table.font()
        table_font.setPointSize(13)
        self._table.setFont(table_font)
        self._table.setStyleSheet(
            f"""
                QTableWidget {{
                    background-color: #000000;
                    color: {COLORS.get('text', '#ffffff')};
                    gridline-color: #333333;
                    border: 1px solid #1f1f1f;
                    font-size: 13px;
                    selection-background-color: #111111;
                }}
                QTableWidget::item {{
                    background-color: #0a0a0a;
                    border-bottom: 1px solid #202020;
                    font-size: 13px;
                }}
                QTableWidget::item:alternate {{
                    background-color: #111111;
                }}
                QHeaderView::section {{
                    background-color: #000000;
                    color: {COLORS.get('text', '#ffffff')};
                    border: 1px solid #1f1f1f;
                    padding: 2px;
                    font-size: {_BODY_FONT_SIZE + 1}px;
                    font-weight: 600;
                }}
            """
        )
        layout.addWidget(self._table)

        self._metric_rows = [
            ("Gross Notional", "Total mark-to-market exposure across both legs", "total_notional"),
            ("Total Cost", "Combined entry cost for the open pair book", "total_cost"),
            ("Funds Held by Broker", "Capital currently reserved or tied up by the broker", "funds_held_by_broker"),
            ("Unrealized P&L", "Open profit or loss across the pair portfolio", "unrealized_pnl"),
            ("Net Dollar Exposure", "Directional net exposure after long and short offsets", "net_exposure"),
        ]
        self._metric_values = [QTableWidgetItem("-") for _ in self._metric_rows]
        for row, (metric_name, description, _value_key) in enumerate(self._metric_rows):
            self._table.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))
            metric_item = QTableWidgetItem(metric_name)
            metric_item.setForeground(QColor(COLORS.get("text", "#ffffff")))
            metric_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._table.setItem(row, 0, metric_item)

            description_item = QTableWidgetItem(description)
            description_item.setForeground(QColor(COLORS.get("text", "#ffffff")))
            description_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._table.setItem(row, 1, description_item)

            value_item = self._metric_values[row]
            value_item.setForeground(QColor(COLORS.get("text", "#ffffff")))
            value_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
            self._table.setItem(row, 2, value_item)

        self._table.setRowHeight(0, self._ROW_HEIGHT)
        self._table.setRowHeight(1, self._ROW_HEIGHT)
        self._table.setRowHeight(2, self._ROW_HEIGHT)
        self._table.setRowHeight(3, self._ROW_HEIGHT)
        self._table.setRowHeight(4, self._ROW_HEIGHT)

        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(186)

    def set_trading_mode(self, is_paper: bool) -> None:
        _set_section_title_mode(self._title_label, "PAIR RISK SUMMARY", is_paper)

    def _set_metric_value(self, row: int, value: str, color: str) -> None:
        item = self._table.item(row, 2)
        if item is None:
            item = QTableWidgetItem("")
            self._table.setItem(row, 2, item)
        item.setText(value)
        item.setForeground(QColor(color))
        item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

    def update_metrics(
        self,
        open_pairs: int = 0,
        total_notional: float = 0.0,
        total_cost: float = 0.0,
        funds_held_by_broker: float = 0.0,
        net_exposure: dict[str, float] | None = None,
        unrealized_pnl: float = 0.0,
        max_sector_pairs: int = 0,
        coint_stable_pct: float = 0.0,
    ) -> None:
        self._set_metric_value(0, _money(total_notional), COLORS.get("text", "#ffffff"))
        self._set_metric_value(1, _money(total_cost), COLORS.get("text", "#ffffff"))
        self._set_metric_value(2, _money(funds_held_by_broker), COLORS.get("text", "#ffffff"))
        self._set_metric_value(3, _money(unrealized_pnl), COLORS.get("text", "#ffffff"))

        if net_exposure:
            long_exp = sum(v for v in net_exposure.values() if v > 0)
            short_exp = sum(v for v in net_exposure.values() if v < 0)
            exposure_text = f"Long {_money(long_exp)} | Short {_money(abs(short_exp))}"
        else:
            exposure_text = "Long $0.00 | Short $0.00"
        self._set_metric_value(4, exposure_text, COLORS.get("text", "#ffffff"))


class BreakingNewsPanel(QWidget):
    news_item_received = Signal(object)
    refresh_completed = Signal(bool, str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setStyleSheet("background-color: #000000;")
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

        title_row = QWidget()
        title_row_layout = QHBoxLayout(title_row)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        title_row_layout.setSpacing(6)

        self._title_label = QLabel("BREAKING NEWS")
        self._title_label.setObjectName("pairSectionTitle")
        title_font = self._title_label.font()
        title_font.setPixelSize(_TITLE_FONT_SIZE)
        title_font.setBold(False)
        self._title_label.setFont(title_font)
        self._title_label.setStyleSheet(
            f"QLabel#pairSectionTitle {{ color: {_TITLE_COLOR_NEWS}; font-size: {_TITLE_FONT_SIZE}px; "
            "font-weight: normal; background-color: #000000; padding: 0 0 3px 0; }"
        )
        self._title_label.setFixedHeight(_TITLE_FONT_SIZE + 10)
        title_row_layout.addWidget(self._title_label)
        title_row_layout.addStretch(1)

        self._refresh_button = QPushButton("⟳")
        self._refresh_button.setToolTip("Fetch the latest news now")
        self._refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_button.setFixedSize(22, 22)
        self._refresh_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._refresh_button.setEnabled(False)
        self._refresh_button.setStyleSheet(
            """
            QPushButton {
                color: #00ffff;
                background-color: #0d0d0d;
                border: 1px solid #303030;
                border-radius: 10px;
                padding: 0px;
                font-size: 14px;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #171717;
                border-color: #4a4a4a;
            }
            QPushButton:pressed {
                background-color: #222222;
            }
            QPushButton:disabled {
                color: #666666;
                border-color: #222222;
                background-color: #0a0a0a;
            }
            """
        )
        self._refresh_button.clicked.connect(self._request_manual_refresh)
        title_row_layout.addWidget(self._refresh_button)
        layout.addWidget(title_row)

        self._scroll_area = QScrollArea()
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll_area.setStyleSheet(
            """
            QScrollArea {
                background-color: #000000;
                border: 1px solid #1f1f1f;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #111111;
            }
            """
        )

        self._news_host = QWidget()
        self._news_host.setStyleSheet("background-color: #000000;")
        self._news_layout = QVBoxLayout(self._news_host)
        self._news_layout.setContentsMargins(0, 0, 0, 0)
        self._news_layout.setSpacing(0)
        self._news_layout.addStretch(1)
        self._scroll_area.setWidget(self._news_host)

        self._scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self._scroll_area.setMinimumHeight(90)
        # Let the scroll region consume the extra height given by the parent.
        layout.addWidget(self._scroll_area, 1)

        self._news_items: deque[tuple[str, Any]] = deque()
        self._seen_ids: set[str] = set()
        self._max_rows = 18
        self._latest_url = ""
        self._news_manager = None
        self._empty_text = "WAITING FOR NEWS FEED..."
        self._last_refresh_at: datetime | None = None
        self._refresh_inflight = False
        self.news_item_received.connect(self.add_news_item)
        self.refresh_completed.connect(self._on_refresh_completed)
        self._render()

    def _clear_rows(self) -> None:
        while self._news_layout.count():
            item = self._news_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _news_key(news_item: Any) -> str:
        news_id = getattr(news_item, "id", "") or ""
        if news_id:
            return str(news_id)
        timestamp = getattr(news_item, "timestamp", None)
        ts_text = ""
        if hasattr(timestamp, "isoformat"):
            try:
                ts_text = timestamp.isoformat()
            except Exception:
                ts_text = ""
        return "|".join(
            str(part)
            for part in (
                ts_text,
                getattr(news_item, "source", ""),
                getattr(news_item, "title", ""),
            )
        )

    @staticmethod
    def _format_timestamp(news_item: Any) -> str:
        timestamp = getattr(news_item, "timestamp", None)
        received_at = getattr(news_item, "received_at", None)
        has_time = bool(getattr(news_item, "timestamp_has_time", True))
        chosen = timestamp if has_time else received_at or timestamp
        if not isinstance(chosen, datetime):
            return "-"
        try:
            if chosen.tzinfo is not None:
                chosen = chosen.astimezone()
        except Exception:
            pass
        try:
            return chosen.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return "-"

    @staticmethod
    def _format_priority(news_item: Any) -> str:
        priority = getattr(news_item, "priority", "")
        value = getattr(priority, "value", priority)
        return str(value).upper() if value not in (None, "") else "-"

    def _update_freshness_label(self) -> None:
        return

    def set_trading_mode(self, is_paper: bool) -> None:
        return

    @staticmethod
    def _format_news_line(news_item: Any) -> str:
        timestamp = BreakingNewsPanel._format_timestamp(news_item)
        headline = str(getattr(news_item, "title", "") or getattr(news_item, "summary", "") or "-").strip()
        source = str(getattr(news_item, "source", "") or "").strip().upper()
        if source and not source.startswith("FIN-"):
            source = f"FIN-{source}"
        if headline and source.startswith("FIN-"):
            suffix = source.removeprefix("FIN-").replace("-", " ").strip()
            for candidate in (
                f" - {suffix}",
                f" — {suffix}",
                f" ({suffix})",
                f" {suffix}",
            ):
                if headline.upper().endswith(candidate.upper()):
                    headline = headline[: -len(candidate)].rstrip(" -—:")
                    break
        return f"{timestamp} {source} - {headline}" if source else f"{timestamp} - {headline}"

    def _make_row_button(self, news_item: Any) -> QPushButton:
        text = self._format_news_line(news_item)
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(text)
        button.setFlat(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.setFixedHeight(30)

        url = str(getattr(news_item, "url", "") or "").strip()
        if url:
            button.clicked.connect(lambda _checked=False, target=url: QDesktopServices.openUrl(QUrl(target)))
        else:
            button.setEnabled(False)

        button.setStyleSheet(
            f"""
            QPushButton {{
                color: #ffffff;
                background-color: #000000;
                border: none;
                border-bottom: 1px solid #1f1f1f;
                padding: 5px 8px;
                text-align: left;
                font-size: {_NEWS_BODY_FONT_SIZE}px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: #101010;
            }}
            QPushButton:disabled {{
                color: #7a7a7a;
            }}
            """
        )
        return button

    def _insert_news_item(self, news_item: Any) -> None:
        if not _news_item_is_recent(news_item):
            return
        key = self._news_key(news_item)
        if key in self._seen_ids:
            return
        self._news_items.appendleft((key, news_item))
        self._seen_ids.add(key)
        self._last_refresh_at = datetime.now(UTC)
        while len(self._news_items) > self._max_rows:
            old_key, _old_item = self._news_items.pop()
            self._seen_ids.discard(old_key)
        self._render()

    def _replace_news_items(self, news_items: list[Any]) -> None:
        self._news_items.clear()
        self._seen_ids.clear()

        for news_item in reversed(news_items or []):
            if not _news_item_is_recent(news_item):
                continue
            key = self._news_key(news_item)
            if key in self._seen_ids:
                continue
            self._news_items.appendleft((key, news_item))
            self._seen_ids.add(key)

        self._render()

    def _render(self) -> None:
        self._clear_rows()
        if not self._news_items:
            self._latest_url = ""
            self._update_freshness_label()
            empty = QPushButton(self._empty_text)
            empty.setEnabled(False)
            empty.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            empty.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            empty.setFixedHeight(30)
            empty.setStyleSheet(
                f"""
                QPushButton {{
                    color: #7a7a7a;
                    background-color: #000000;
                    border: none;
                    border-bottom: 1px solid #1f1f1f;
                    padding: 5px 8px;
                    text-align: left;
                    font-size: {_NEWS_BODY_FONT_SIZE}px;
                    font-weight: normal;
                }}
                """
            )
            self._news_layout.insertWidget(0, empty)
            self._news_layout.addStretch(1)
            return

        for index, (_key, news_item) in enumerate(self._news_items):
            if index == 0:
                self._latest_url = str(getattr(news_item, "url", "") or "")
            self._news_layout.insertWidget(index, self._make_row_button(news_item))
        self._news_layout.addStretch(1)
        self._update_freshness_label()

    def _open_news_url(self, row: int, _column: int) -> None:
        url = self._latest_url.strip()
        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))

    def update_news(self, news_items: list[Any]) -> None:
        self._last_refresh_at = datetime.now(UTC)
        for news_item in reversed(news_items or []):
            self._insert_news_item(news_item)
        if not news_items:
            self._render()

    def add_news_item(self, news_item: Any) -> None:
        self._insert_news_item(news_item)

    def set_news_manager(self, news_manager: Any) -> None:
        if news_manager is self._news_manager:
            self.refresh_breaking_news()
            return
        self._news_manager = news_manager
        self._refresh_button.setEnabled(news_manager is not None)
        if news_manager is None:
            self._empty_text = "CONNECTING NEWS FEED..."
            self.clear()
            return
        if hasattr(news_manager, "register_alert_callback"):
            try:
                news_manager.register_alert_callback(self.news_item_received.emit)
            except Exception:
                pass
        self.refresh_breaking_news()

    def _request_manual_refresh(self) -> None:
        if self._refresh_inflight:
            return
        news_manager = getattr(self, "_news_manager", None)
        if news_manager is None or not hasattr(news_manager, "get_recent_news"):
            return

        self._refresh_inflight = True
        self._refresh_button.setEnabled(False)
        self._refresh_button.setText("…")

        def _worker() -> None:
            success = True
            message = ""
            try:
                if hasattr(news_manager, "refresh_now"):
                    news_manager.refresh_now(force=True)
                elif hasattr(news_manager, "_poll_news_sources_once"):
                    news_manager._poll_news_sources_once()
                else:
                    success = False
                    message = "news manager cannot refresh"
            except Exception as exc:
                success = False
                message = str(exc)
            self.refresh_completed.emit(success, message)

        threading.Thread(target=_worker, name="TradovBreakingNewsRefresh", daemon=True).start()

    def _on_refresh_completed(self, success: bool, message: str) -> None:
        self._refresh_inflight = False
        self._refresh_button.setText("⟳")
        self._refresh_button.setEnabled(self._news_manager is not None)
        if not success and message:
            self._empty_text = f"NEWS REFRESH ERROR: {message}"
        self.refresh_breaking_news()

    def refresh_breaking_news(self) -> None:
        news_manager = getattr(self, "_news_manager", None)
        if news_manager is None or not hasattr(news_manager, "get_recent_news"):
            self._empty_text = "CONNECTING NEWS FEED..."
            self.clear()
            self._refresh_button.setEnabled(False)
            return
        try:
            recent_news = news_manager.get_recent_news(limit=50)
        except Exception as exc:
            self._empty_text = f"NEWS FEED ERROR: {exc}"
            self.clear()
            return
        if not recent_news and hasattr(news_manager, "_fetch_from_finnhub"):
            try:
                if hasattr(news_manager, "refresh_now"):
                    news_manager.refresh_now(force=True)
                else:
                    news_manager._fetch_from_finnhub()
                recent_news = news_manager.get_recent_news(limit=50)
            except Exception:
                recent_news = []
        recent_news = [item for item in recent_news if _news_item_is_recent(item)]

        high_priority_news = [
            item for item in recent_news
            if str(getattr(getattr(item, "priority", None), "value", getattr(item, "priority", ""))).lower()
            in {"breaking", "high"}
        ]
        items_to_show: list[Any] = []
        seen_keys: set[str] = set()
        for bucket in (high_priority_news, recent_news):
            for item in bucket:
                key = _news_item_key(item)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                items_to_show.append(item)
                if len(items_to_show) >= 3:
                    break
            if len(items_to_show) >= 3:
                break
        self._empty_text = "NO HIGH-PRIORITY NEWS YET"
        self._replace_news_items(items_to_show[:3])

    def clear(self) -> None:
        self._news_items.clear()
        self._seen_ids.clear()
        self._last_refresh_at = datetime.now(UTC)
        self._render()


class PairTradingDashboard(QWidget):
    breaking_news_received = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)

        self._scanner_panel = PairScannerPanel()
        content_layout.addWidget(self._scanner_panel)

        self._positions_panel = PairPositionsPanel()
        content_layout.addWidget(self._positions_panel)

        self._risk_panel = PairRiskSummaryPanel()
        self._risk_panel.setFixedHeight(186)
        self._risk_panel.setStyleSheet("background-color: #000000;")
        content_layout.addWidget(self._risk_panel)

        self._breaking_news_panel = BreakingNewsPanel()
        content_layout.addWidget(self._breaking_news_panel, 1)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        layout.addWidget(content_widget)

        self._news_manager = None
        self._status_label = QLabel("OFF")
        self._status_label.hide()
        self.breaking_news_received.connect(self._handle_breaking_news)
        self._positions_panel.flatten_requested.connect(self._request_pair_flatten)

        self.setLayout(layout)
        self._pair_tracker = None

    def set_trading_mode(self, is_paper: bool) -> None:
        self._scanner_panel.set_trading_mode(is_paper)
        self._positions_panel.set_trading_mode(is_paper)
        if hasattr(self._risk_panel, "set_trading_mode"):
            self._risk_panel.set_trading_mode(is_paper)

    def set_news_manager(self, news_manager: Any) -> None:
        if news_manager is self._news_manager:
            self.refresh_breaking_news()
            return
        self._news_manager = news_manager
        if news_manager is None:
            return
        if hasattr(news_manager, "register_alert_callback"):
            try:
                news_manager.register_alert_callback(self.breaking_news_received.emit)
            except Exception:
                pass
        self.refresh_breaking_news()

    def refresh_breaking_news(self) -> None:
        news_manager = getattr(self, "_news_manager", None)
        if news_manager is None or not hasattr(news_manager, "get_recent_news"):
            return
        try:
            recent_news = news_manager.get_recent_news(limit=50)
        except Exception:
            return
        if not recent_news and hasattr(news_manager, "_fetch_from_finnhub"):
            try:
                news_manager._fetch_from_finnhub()
                recent_news = news_manager.get_recent_news(limit=50)
            except Exception:
                recent_news = []
        recent_news = [item for item in recent_news if _news_item_is_recent(item)]
        high_priority_news = [
            item for item in recent_news
            if str(getattr(getattr(item, "priority", None), "value", getattr(item, "priority", ""))).lower()
            in {"breaking", "high"}
        ]
        items_to_show: list[Any] = []
        seen_keys: set[str] = set()
        for bucket in (high_priority_news, recent_news):
            for item in bucket:
                key = _news_item_key(item)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                items_to_show.append(item)
                if len(items_to_show) >= 3:
                    break
            if len(items_to_show) >= 3:
                break
        if getattr(self, "_breaking_news_panel", None) is not None:
            self._breaking_news_panel.update_news(items_to_show[:3])

    def _handle_breaking_news(self, news_item: Any) -> None:
        if not _news_item_is_recent(news_item):
            return
        self._breaking_news_panel.add_news_item(news_item)

    def _request_pair_flatten(self, pair_key: str) -> None:
        pair_key = str(pair_key or "").strip()
        if not pair_key:
            return

        answer = QMessageBox.question(
            self,
            "Confirm Flatten",
            f"Flatten pair {pair_key}?\n\nThis will close both legs of the active pair trade.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.add_system_log(f"Flatten cancelled for pair {pair_key}")
            return

        supervisor = getattr(self, "_session_supervisor", None)
        orchestrator = getattr(supervisor, "orchestrator", None) if supervisor is not None else None
        if orchestrator is None:
            self.add_system_log(f"⚠️ Pair flatten request ignored for {pair_key}: no orchestrator")
            return

        exited = False
        flatten_pair = getattr(orchestrator, "flatten_pair_position", None)
        if callable(flatten_pair):
            try:
                exited = bool(flatten_pair(pair_key, reason="manual_pair_flatten_dashboard"))
            except Exception as exc:
                self.logger.error("Pair flatten failed for %s: %s", pair_key, exc, exc_info=True)
        if exited:
            self.add_system_log(f"🖱️ Flatten requested for pair {pair_key}")
            try:
                self._refresh_pair_trading_panels()
            except Exception:
                pass
        else:
            self.add_system_log(f"⚠️ Pair flatten request failed for {pair_key}")

    def set_pair_tracker(self, tracker: Any) -> None:
        self._pair_tracker = tracker

    def set_pair_strategy(self, strategy: Any) -> None:
        self._pair_strategy = strategy

    def update_data(self) -> None:
        tracker = getattr(self, "_pair_tracker", None)
        strategy = getattr(self, "_pair_strategy", None)

        positions = {}
        if tracker is not None and hasattr(tracker, "get_all_positions"):
            positions = tracker.get_all_positions()
        elif strategy is not None and hasattr(strategy, "get_pair_positions"):
            positions = strategy.get_pair_positions()

        self._positions_panel.update_positions(positions)

        if tracker is not None and self._risk_panel is not None:
            pnl = tracker.get_total_unrealized_pnl() if hasattr(tracker, "get_total_unrealized_pnl") else 0.0
            notional = tracker.get_total_notional() if hasattr(tracker, "get_total_notional") else 0.0
            cost = tracker.get_total_entry_cost() if hasattr(tracker, "get_total_entry_cost") else 0.0
            funds_held = tracker.get_total_funds_held() if hasattr(tracker, "get_total_funds_held") else 0.0
            exposure = tracker.get_net_dollar_exposure() if hasattr(tracker, "get_net_dollar_exposure") else {}
            self._risk_panel.update_metrics(
                open_pairs=len(positions),
                total_notional=notional,
                total_cost=cost,
                funds_held_by_broker=funds_held,
                net_exposure=exposure,
                unrealized_pnl=pnl,
            )

        self.refresh_breaking_news()

        is_enabled = len(positions) > 0 or (strategy is not None and hasattr(strategy, "state") and strategy.state == "active")
        self._status_label.setText("ACTIVE" if is_enabled else "OFF")
        self._status_label.setStyleSheet(
            f"color: {COLORS.get('positive', '#00ff88') if is_enabled else COLORS.get('text_dim', '#888888')}; "
            f"font-size: 11px; font-weight: bold;"
        )

    def update_scan_results(self, scan_result: PairScanResult, market_hours_open: bool | None = None) -> None:
        self._scanner_panel.update_scan(scan_result, market_hours_open=market_hours_open)


__all__ = [
    "PairPositionsPanel",
    "PairSpreadChart",
    "PairScannerPanel",
    "PairRiskSummaryPanel",
    "BreakingNewsPanel",
    "PairTradingDashboard",
]
