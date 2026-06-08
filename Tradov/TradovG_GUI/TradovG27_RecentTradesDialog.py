#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG27_RecentTradesDialog.py
Purpose: Dedicated recent-trades history dialog for dashboard trade-record views
"""

from __future__ import annotations

from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

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
from Tradov.TradovG_GUI.TradovG26_RecentTradeFormatter import build_recent_trade_display
from Tradov.TradovG_GUI.TradovG39_PaperPositionsTreePresenter import (
    build_paper_spread_tree_presentation,
)


_EASTERN_TIMEZONE = ZoneInfo("America/New_York")


class RecentTradesDialog(QDialog):
    """Non-modal dialog showing the most recent trade records."""

    def __init__(self, mode_name: str, trades: list[dict], parent: Any = None) -> None:
        super().__init__(parent)
        self._trades = list(trades or [])

        self.setWindowTitle(f"Recent Trade History - {mode_name}")
        self.setModal(False)
        self.setMinimumSize(980, 520)
        self.resize(980, 520)
        self.setStyleSheet(
            f"background-color: {COLORS['background']}; color: {COLORS['text']};"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        subtitle = QLabel("Showing last 30 recent trade records")
        subtitle.setStyleSheet("font-size: 12px; color: #b8b8b8;")
        layout.addWidget(subtitle)

        self._table = QTreeWidget(self)
        self._table.setColumnCount(9)
        self._table.setHeaderLabels(["ACTION", "LEG", "STRIKE", "QTY", "PRICE", "COST", "EXPIRY", "P&L", ""])
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
        table.setHeaderLabels(["ACTION", "LEG", "STRIKE", "QTY", "PRICE", "COST", "EXPIRY", "P&L", ""])

        for trade in self._trades:
            if self._is_grouped_trade(trade):
                self._add_grouped_trade_rows(trade)
            else:
                self._add_flat_trade_rows(trade)

        if table.topLevelItemCount() <= 0:
            empty = QTreeWidgetItem(table)
            empty.setText(0, "No recent trade records found")
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
        item.setTextAlignment(4, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(5, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
        item.setTextAlignment(6, int(Qt.AlignmentFlag.AlignCenter))
        item.setTextAlignment(7, int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))

    @staticmethod
    def _is_grouped_trade(trade: dict[str, Any]) -> bool:
        legs = trade.get("legs") if isinstance(trade, dict) else None
        return isinstance(legs, list) and len(legs) > 0

    def _add_grouped_trade_rows(self, trade: dict[str, Any]) -> None:
        header, legs = build_paper_spread_tree_presentation(
            trade,
            date.today(),
            _EASTERN_TIMEZONE,
            COLORS,
            "CLOSED",
            closed=True,
        )

        header_row = QTreeWidgetItem(self._table)
        self._table.setFirstColumnSpanned(
            self._table.indexOfTopLevelItem(header_row),
            QModelIndex(),
            True,
        )

        row_widget = QWidget(self._table)
        row_widget.setMinimumHeight(22)
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(6, 0, 6, 0)
        row_layout.setSpacing(6)

        if header.timestamp_text:
            timestamp_label = QLabel(header.timestamp_text, row_widget)
            timestamp_label.setStyleSheet("color: #a8a8a8; font-weight: normal;")
            row_layout.addWidget(timestamp_label, 0)

        summary_label = QLabel(header.summary_text, row_widget)
        summary_label.setStyleSheet(
            f"color: {COLORS.get('cyan', '#00ffff')}; font-weight: normal;"
        )
        row_layout.addWidget(summary_label, 1)

        pnl_label = QLabel(header.pnl_text, row_widget)
        pnl_label.setStyleSheet(f"color: {header.pnl_color}; font-weight: normal;")
        row_layout.addWidget(pnl_label, 0, Qt.AlignmentFlag.AlignRight)
        self._table.setItemWidget(header_row, 0, row_widget)

        for spread_leg in legs:
            leg_row = QTreeWidgetItem(self._table)
            leg_row.setText(0, spread_leg.action_text)
            leg_row.setText(1, spread_leg.leg_text)
            leg_row.setText(2, spread_leg.strike_text)
            leg_row.setText(3, spread_leg.quantity_text)
            leg_row.setText(4, spread_leg.price_text)
            leg_row.setText(6, spread_leg.expiry_text)
            self._align_data_row(leg_row)
            for col in range(8):
                leg_row.setForeground(col, QColor("#ffffff"))
            if spread_leg.action_color:
                leg_row.setForeground(0, QColor(spread_leg.action_color))

            if spread_leg.cost_text:
                leg_row.setText(5, spread_leg.cost_text)
                if spread_leg.cost_color:
                    leg_row.setForeground(5, QColor(spread_leg.cost_color))
            if spread_leg.pnl_text:
                leg_row.setText(7, spread_leg.pnl_text)
                if spread_leg.pnl_color:
                    leg_row.setForeground(7, QColor(spread_leg.pnl_color))

    def _add_flat_trade_rows(self, trade: dict[str, Any]) -> None:
        display = build_recent_trade_display(trade, symbol_placeholder="-")
        timestamp = display.timestamp_text
        symbol = display.symbol
        action = display.action.replace("_", " ")

        summary_row = QTreeWidgetItem(self._table)
        summary_row.setText(0, f"{timestamp} TRADE RECORD : {symbol}  |  ACTION: {action}")
        summary_row.setForeground(0, QColor(COLORS.get("cyan", "#00ffff")))
        self._table.setFirstColumnSpanned(
            self._table.indexOfTopLevelItem(summary_row),
            QModelIndex(),
            True,
        )

        detail_row = QTreeWidgetItem(self._table)
        action_text = action.upper()
        detail_row.setText(0, action_text)
        detail_row.setText(1, symbol)
        detail_row.setText(3, display.quantity_text)
        detail_row.setText(4, display.price_text)
        detail_row.setText(5, display.cost_text)
        detail_row.setText(7, display.realized_pnl_text)
        self._align_data_row(detail_row)
        for col in range(8):
            detail_row.setForeground(col, QColor("#ffffff"))
        if action_text.startswith("BUY"):
            detail_row.setForeground(0, QColor(COLORS["positive"]))
        elif action_text.startswith("SELL"):
            detail_row.setForeground(0, QColor(COLORS["negative"]))

        if display.cost_text.startswith("$+") or display.cost_text.startswith("+"):
            detail_row.setForeground(5, QColor(COLORS["positive"]))
        elif display.cost_text.startswith("$-") or display.cost_text.startswith("-"):
            detail_row.setForeground(5, QColor(COLORS["negative"]))

        if display.realized_pnl_value > 0:
            detail_row.setForeground(7, QColor(COLORS["positive"]))
        elif display.realized_pnl_value < 0:
            detail_row.setForeground(7, QColor(COLORS["negative"]))
