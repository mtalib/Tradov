#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG27_RecentTradesDialog.py
Purpose: Dedicated recent-trades history dialog for dashboard trade-record views
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Tradov.TradovG_GUI.TradovG13_EnhancedWidgets import COLORS
from Tradov.TradovG_GUI.TradovG26_RecentTradeFormatter import (
    build_pair_trade_banner_html,
    build_pair_trade_history_display,
    build_recent_trade_symbol_html,
)


class RecentTradesDialog(QDialog):
    """Non-modal dialog showing the most recent trade records."""

    def __init__(self, mode_name: str, trades: list[dict], parent: Any = None) -> None:
        super().__init__(parent)
        self._trades = list(trades or [])

        self.setWindowTitle(f"Pair Trade History - {mode_name}")
        self.setModal(False)
        self.setMinimumSize(980, 520)
        self.resize(980, 520)
        self.setStyleSheet(
            f"background-color: {COLORS['background']}; color: {COLORS['text']};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        subtitle = QLabel("Showing last 30 pair trade records")
        subtitle.setStyleSheet("font-size: 12px; color: #b8b8b8;")
        layout.addWidget(subtitle)

        self._table = QTreeWidget(self)
        self._table.setColumnCount(9)
        self._table.setHeaderLabels(["CLOSED", "PAIR", "SIDE", "QTY-A", "QTY-B", "ENTRY Z", "CLOSE Z", "P&L", "DURATION"])
        for column in range(self._table.columnCount()):
            self._table.headerItem().setTextAlignment(column, Qt.AlignmentFlag.AlignCenter)

        self._table.setRootIsDecorated(False)
        self._table.setAnimated(True)
        self._table.setIndentation(20)
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self._table.setStyleSheet(
            f"QTreeWidget {{ background-color: {COLORS['background']}; border: none; outline: none; font-size: 11px; }}"
            f"QTreeWidget::item {{ padding: 1px 4px; border-bottom: 1px solid {COLORS['border']}; }}"
            f"QTreeWidget::item:selected {{ background-color: #2a3a4a; }}"
            f"QTreeWidget::branch:has-children:!has-siblings:closed,"
            f"QTreeWidget::branch:closed:has-children:has-siblings {{ image: none; border-image: none; }}"
            f"QTreeWidget::branch:open:has-children:!has-siblings,"
            f"QTreeWidget::branch:open:has-children:has-siblings {{ image: none; border-image: none; }}"
            f"QHeaderView::section {{ background-color: {COLORS['panel']}; color: {COLORS['text']}; "
            f"padding: 2px; border: 1px solid {COLORS['border']}; font-size: 12px; font-weight: normal; }}"
            f"QScrollBar:vertical {{ width: 8px; background: {COLORS['panel']}; }}"
        )
        header = self._table.header()
        self._table.setColumnWidth(0, 92)
        self._table.setColumnWidth(1, 146)
        self._table.setColumnWidth(2, 68)
        self._table.setColumnWidth(3, 44)
        self._table.setColumnWidth(4, 60)
        self._table.setColumnWidth(5, 68)
        self._table.setColumnWidth(6, 60)
        self._table.setColumnWidth(7, 92)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self._table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedHeight(28)
        close_btn.setStyleSheet(
            f"font-size: 12px; padding: 0 12px; background-color: {COLORS['panel']};"
            f" color: {COLORS['text']}; border: 1px solid {COLORS['border']}; border-radius: 3px;"
        )
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.update_trades(self._trades)

    def update_trades(self, trades: list[dict]) -> None:
        """Replace the recent-trade list and refresh the table."""
        self._trades = list(trades or [])
        self._populate_table()

    def _populate_table(self) -> None:
        table = self._table
        table.clear()
        table.setHeaderLabels(["CLOSED", "PAIR", "SIDE", "QTY-A", "QTY-B", "ENTRY Z", "CLOSE Z", "P&L", "DURATION"])

        for trade in self._trades:
            self._add_pair_trade_rows(trade)

        if table.topLevelItemCount() <= 0:
            empty = QTreeWidgetItem(table)
            empty.setText(0, "No closed pair trades found")
            empty.setForeground(0, QColor(COLORS["text_dim"]))
            table.setFirstColumnSpanned(
                table.indexOfTopLevelItem(empty),
                QModelIndex(),
                True,
            )

    @staticmethod
    def _align_data_row(item: QTreeWidgetItem) -> None:
        item.setTextAlignment(0, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(1, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(2, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(3, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(4, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(5, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(6, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(7, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(8, int(Qt.AlignmentFlag.AlignCenter))

    @staticmethod
    def _pair_side_color(side_text: str) -> QColor:
        normalized = str(side_text or "").strip().upper()
        if normalized == "NEGATIVE":
            return QColor(COLORS["negative"])
        if normalized == "POSITIVE":
            return QColor(COLORS["positive"])
        return QColor(COLORS["text"])

    def _add_pair_trade_rows(self, trade: dict[str, Any]) -> None:
        display = build_pair_trade_history_display(trade, pair_placeholder="—")

        summary_row = QTreeWidgetItem(self._table)
        self._table.setFirstColumnSpanned(
            self._table.indexOfTopLevelItem(summary_row),
            QModelIndex(),
            True,
        )

        summary_widget = QLabel(self._table)
        summary_widget.setTextFormat(Qt.TextFormat.RichText)
        summary_widget.setStyleSheet("background-color: transparent; font-weight: normal;")
        summary_widget.setText(build_pair_trade_banner_html(display, colors=COLORS, pair_placeholder="—"))
        self._table.setItemWidget(summary_row, 0, summary_widget)

        detail_row = QTreeWidgetItem(self._table)
        detail_row.setText(0, display.closed_text)
        detail_row.setText(2, display.side_text)
        detail_row.setText(3, display.qty_a_text)
        detail_row.setText(4, display.qty_b_text)
        detail_row.setText(5, display.entry_z_text)
        detail_row.setText(6, display.close_z_text)
        detail_row.setText(7, display.realized_pnl_text)
        detail_row.setText(8, display.duration_text)
        self._align_data_row(detail_row)

        for col in range(self._table.columnCount()):
            detail_row.setForeground(col, QColor("#ffffff"))

        pair_widget = QLabel(self._table)
        pair_widget.setTextFormat(Qt.TextFormat.RichText)
        pair_widget.setStyleSheet("background-color: transparent; font-weight: normal;")
        pair_widget.setText(
            build_recent_trade_symbol_html(
                display.pair_text,
                side=display.side_text,
                colors=COLORS,
                symbol_placeholder="—",
            )
        )
        self._table.setItemWidget(detail_row, 1, pair_widget)

        detail_row.setForeground(0, QColor("#a8a8a8"))
        detail_row.setForeground(2, self._pair_side_color(display.side_text))
        if display.realized_pnl_value > 0:
            detail_row.setForeground(7, QColor(COLORS["positive"]))
        elif display.realized_pnl_value < 0:
            detail_row.setForeground(7, QColor(COLORS["negative"]))
