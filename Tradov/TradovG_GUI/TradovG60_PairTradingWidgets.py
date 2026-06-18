#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG60_PairTradingWidgets.py
Purpose: Pair trading dashboard widgets — positions, spread chart, scanner, risk

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-03 Time: 00:00:00

Module Description:
    GUI widgets for the pair trading subsystem:
      - PairPositionsPanel: table of open pair positions with P&L
      - PairSpreadChart: live spread/z-score chart via matplotlib
      - PairScannerPanel: cointegration scan results table
      - PairRiskSummaryPanel: portfolio-level pair risk metrics
      - PairTradingDashboard: composite widget combining all four
"""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from Tradov.TradovG_GUI.TradovG13_EnhancedWidgets import COLORS
from Tradov.TradovD_Strategies.TradovD50_PairTypes import (
    PairPosition,
    PairScanResult,
    PairSide,
)


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


class PairPositionsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setStyleSheet("background-color: #000000;")

        header = QHBoxLayout()
        title = QLabel("PAIR POSITIONS")
        title.setStyleSheet("color: #00ccff; font-size: 13px; font-weight: normal;")
        header.addWidget(title)
        header.addStretch()
        self._count_label = QLabel("0 open")
        self._count_label.setStyleSheet(f"color: {COLORS.get('cyan', '#00ccff')}; font-size: 11px;")
        header.addWidget(self._count_label)
        layout.addLayout(header)

        self._empty_label = QLabel("No open pair positions")
        self._empty_label.setStyleSheet(
            f"color: {COLORS.get('text_dim', '#888888')}; font-size: 11px; padding: 2px 0;"
        )
        layout.addWidget(self._empty_label)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels([
            "Pair", "Side", "Qty A", "Qty B", "Z-Score",
            "Spread", "Duration",
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setStyleSheet(
            f"""
                QTableWidget {{
                    background-color: #000000;
                    color: {COLORS.get('text', '#ffffff')};
                    gridline-color: #1f1f1f;
                    border: 1px solid #1f1f1f;
                    selection-background-color: #111111;
                }}
                QTableWidget::item {{
                    background-color: #000000;
                }}
                QHeaderView::section {{
                    background-color: #000000;
                    color: {COLORS.get('text', '#ffffff')};
                    border: 1px solid #1f1f1f;
                    padding: 2px;
                }}
            """
        )
        layout.addWidget(self._table)

        totals_layout = QHBoxLayout()
        self._total_notional_label = QLabel("Notional: $0")
        self._total_notional_label.setStyleSheet(f"color: {COLORS.get('text_dim', '#888888')}; font-size: 11px;")
        totals_layout.addStretch()
        totals_layout.addWidget(self._total_notional_label)
        layout.addLayout(totals_layout)

        self.setLayout(layout)

    def update_positions(self, positions: dict[str, PairPosition]) -> None:
        has_positions = bool(positions)
        self._empty_label.setVisible(not has_positions)
        self._table.setVisible(has_positions)
        self._table.setRowCount(len(positions))
        for row, (pair_key, pos) in enumerate(positions.items()):
            self._table.setItem(row, 0, QTableWidgetItem(pair_key))
            self._table.setItem(row, 1, QTableWidgetItem(pos.pair_side.value))
            self._table.setItem(row, 2, QTableWidgetItem(str(pos.quantity_a)))
            self._table.setItem(row, 3, QTableWidgetItem(str(pos.quantity_b)))

            z_item = QTableWidgetItem(f"{pos.current_z:.2f}")
            z_color = _pnl_color(-pos.current_z) if pos.pair_side == PairSide.LONG_SHORT else _pnl_color(pos.current_z)
            z_item.setForeground(QColor(z_color))
            self._table.setItem(row, 4, z_item)

            self._table.setItem(row, 5, QTableWidgetItem(f"{pos.current_spread:.4f}"))

            dur = pos.duration
            dur_str = f"{dur.days}d {dur.seconds // 3600}h" if dur else "-"
            self._table.setItem(row, 6, QTableWidgetItem(dur_str))

        self._count_label.setText(f"{len(positions)} open")
        total_notional = sum(
            abs(p.quantity_a * p.current_price_a) + abs(p.quantity_b * p.current_price_b)
            for p in positions.values()
        )
        self._total_notional_label.setText(f"Notional: {_money(total_notional)}")


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
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        self.setStyleSheet("background-color: #000000;")

        header = QHBoxLayout()
        title = QLabel("SCANNER RESULTS")
        title.setStyleSheet("color: #00ccff; font-size: 13px; font-weight: normal;")
        header.addWidget(title)
        header.addStretch()
        self._scan_label = QLabel("No scan")
        self._scan_label.setStyleSheet(f"color: {COLORS.get('text_dim', '#888888')}; font-size: 11px;")
        header.addWidget(self._scan_label)
        layout.addLayout(header)

        summary = QHBoxLayout()
        summary.setContentsMargins(2, 0, 2, 0)
        summary.setSpacing(10)
        self._summary_label = QLabel("Candidates: -")
        self._summary_label.setStyleSheet(f"color: {COLORS.get('text_dim', '#888888')}; font-size: 10px;")
        self._tradeable_label = QLabel("Tradeable: -")
        self._tradeable_label.setStyleSheet(f"color: {COLORS.get('positive', '#00ff88')}; font-size: 10px;")
        self._best_score_label = QLabel("Best score: -")
        self._best_score_label.setStyleSheet(f"color: {COLORS.get('cyan', '#00ccff')}; font-size: 10px;")
        summary.addWidget(self._summary_label)
        summary.addWidget(self._tradeable_label)
        summary.addWidget(self._best_score_label)
        summary.addStretch()
        layout.addLayout(summary)

        self._table = QTableWidget(0, 8)
        self._table.setHorizontalHeaderLabels([
            "Rank", "Pair", "p-value", "Score", "Half-Life", "Hedge Ratio",
            "Spread Std", "Tradeable",
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setMaximumHeight(180)
        self._table.setStyleSheet(
            f"""
                QTableWidget {{
                    background-color: #000000;
                    color: {COLORS.get('text', '#ffffff')};
                    gridline-color: #1f1f1f;
                    border: 1px solid #1f1f1f;
                    selection-background-color: #111111;
                }}
                QTableWidget::item {{
                    background-color: #000000;
                }}
                QHeaderView::section {{
                    background-color: #000000;
                    color: {COLORS.get('text', '#ffffff')};
                    border: 1px solid #1f1f1f;
                    padding: 2px;
                }}
            """
        )
        layout.addWidget(self._table)

        self.setLayout(layout)

    def update_scan(self, scan_result: PairScanResult) -> None:
        pairs = scan_result.ranked_pairs or scan_result.validated_pairs
        self._table.setRowCount(len(pairs))
        tradeable_count = 0
        best_score = None
        for row, result in enumerate(pairs):
            rank = result.metadata.get("rank", row + 1)
            self._table.setItem(row, 0, QTableWidgetItem(str(rank)))
            self._table.setItem(row, 1, QTableWidgetItem(result.pair_key))

            p_item = QTableWidgetItem(f"{result.p_value:.4f}")
            p_item.setForeground(QColor(
                COLORS.get("positive", "#00ff88") if result.p_value < 0.05 else COLORS.get("text", "#ffffff")
            ))
            self._table.setItem(row, 2, p_item)

            score_item = QTableWidgetItem(f"{result.ranking_score:.3f}")
            score_item.setForeground(QColor(COLORS.get("cyan", "#00ccff")))
            self._table.setItem(row, 3, score_item)
            if best_score is None or result.ranking_score > best_score:
                best_score = result.ranking_score

            self._table.setItem(row, 4, QTableWidgetItem(f"{result.half_life:.1f}d"))
            self._table.setItem(row, 5, QTableWidgetItem(f"{result.hedge_ratio:.4f}"))
            self._table.setItem(row, 6, QTableWidgetItem(f"{result.spread_std:.4f}"))

            tradeable_item = QTableWidgetItem("YES" if result.is_tradeable else "NO")
            if result.is_tradeable:
                tradeable_count += 1
            tradeable_item.setForeground(QColor(
                COLORS.get("positive", "#00ff88") if result.is_tradeable else COLORS.get("text_dim", "#888888")
            ))
            self._table.setItem(row, 7, tradeable_item)

        total_candidates = scan_result.total_candidates
        ranked_count = len(scan_result.ranked_pairs or scan_result.validated_pairs)
        self._scan_label.setText(
            f"{ranked_count}/{total_candidates} ranked"
        )
        self._summary_label.setText(f"Candidates: {total_candidates}")
        self._tradeable_label.setText(f"Tradeable: {tradeable_count}")
        self._best_score_label.setText(
            f"Best score: {best_score:.3f}" if best_score is not None else "Best score: -"
        )


class PairRiskSummaryPanel(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QGridLayout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)
        self.setStyleSheet("background-color: #000000;")

        title = QLabel("PAIR RISK SUMMARY")
        title.setStyleSheet("color: #00ccff; font-size: 13px; font-weight: normal;")
        layout.addWidget(title, 0, 0, 1, 4)

        label_style = "color: #ffffff; font-size: 13px; font-weight: normal;"
        value_style = "color: #ffffff; font-size: 13px; font-weight: normal;"

        self._labels: dict[str, QLabel] = {}
        metrics = [
            ("Open Pair Count", 1, 0),
            ("Gross Notional", 1, 2),
            ("Net Dollar Exposure", 1, 4),
            ("Max Sector Pair Count", 2, 0),
            ("Cointegration Stability", 2, 2),
        ]
        for name, row, col in metrics:
            lbl = QLabel(name + ":")
            lbl.setStyleSheet(label_style)
            layout.addWidget(lbl, row, col)
            val = QLabel("-")
            val.setStyleSheet(value_style)
            layout.addWidget(val, row, col + 1)
            self._labels[name] = val

        self.setLayout(layout)

    def update_metrics(
        self,
        open_pairs: int = 0,
        total_notional: float = 0.0,
        net_exposure: dict[str, float] | None = None,
        unrealized_pnl: float = 0.0,
        max_sector_pairs: int = 0,
        coint_stable_pct: float = 0.0,
    ) -> None:
        self._labels["Open Pair Count"].setText(str(open_pairs))
        self._labels["Gross Notional"].setText(_money(total_notional))
        self._labels["Max Sector Pair Count"].setText(str(max_sector_pairs))
        self._labels["Cointegration Stability"].setText(f"{coint_stable_pct:.0%}")

        if net_exposure:
            long_exp = sum(v for v in net_exposure.values() if v > 0)
            short_exp = sum(v for v in net_exposure.values() if v < 0)
            self._labels["Net Dollar Exposure"].setText(f"L:{_money(long_exp)} S:{_money(abs(short_exp))}")


class PairTradingDashboard(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        self._scanner_panel = PairScannerPanel()
        content_layout.addWidget(self._scanner_panel)

        self._positions_panel = PairPositionsPanel()
        content_layout.addWidget(self._positions_panel)

        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        layout.addWidget(content_widget)

        self._risk_panel = None

        self.setLayout(layout)
        self._pair_tracker = None

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
            exposure = tracker.get_net_dollar_exposure() if hasattr(tracker, "get_net_dollar_exposure") else {}
            self._risk_panel.update_metrics(
                open_pairs=len(positions),
                total_notional=notional,
                net_exposure=exposure,
                unrealized_pnl=pnl,
            )

        is_enabled = len(positions) > 0 or (strategy is not None and hasattr(strategy, "state") and strategy.state == "active")
        self._status_label.setText("ACTIVE" if is_enabled else "OFF")
        self._status_label.setStyleSheet(
            f"color: {COLORS.get('positive', '#00ff88') if is_enabled else COLORS.get('text_dim', '#888888')}; "
            f"font-size: 11px; font-weight: bold;"
        )

    def update_scan_results(self, scan_result: PairScanResult) -> None:
        self._scanner_panel.update_scan(scan_result)


__all__ = [
    "PairPositionsPanel",
    "PairSpreadChart",
    "PairScannerPanel",
    "PairRiskSummaryPanel",
    "PairTradingDashboard",
]
