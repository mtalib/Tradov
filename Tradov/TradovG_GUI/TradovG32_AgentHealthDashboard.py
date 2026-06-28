#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI
Module: TradovG32_AgentHealthDashboard.py
Purpose: Real-time agent health dashboard for X-series and Y-series agents

Author: Mohamed Talib
Year Created: 2026
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    PySide6 dashboard panel showing real-time health, liveness status, and
    runtime metrics for all registered X-series (on-demand) and Y-series
    (daemon) agents.  Data is sourced from TradovU12_AgentIntegration's
    AgentRegistry singleton and refreshed every 5 seconds.

Key Features:
    • Per-agent status indicator (UP / DEGRADED / DOWN / UNKNOWN)
    • Last heartbeat age in seconds
    • Decisions made / failed counters
    • Average latency display
    • Filter by series (X / Y / All)
    • Colour-coded rows (green → amber → red → grey)
    • HAS_QT guard — module imports safely in headless environments

Dependencies:
    • PySide6 (optional — guarded by HAS_QT)
    • TradovU12_AgentIntegration: AgentRegistry singleton
    • TradovU01_Logger (graceful fallback)
"""

from __future__ import annotations

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
from datetime import datetime, UTC
from typing import Any

# ==============================================================================
# QT GUARD
# ==============================================================================
try:
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QColor, QFont
    from PySide6.QtWidgets import (
        QComboBox,
        QFrame,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    HAS_QT = True
except ImportError:
    HAS_QT = False

# ==============================================================================
# TRADOV IMPORTS
# ==============================================================================
try:
    from Tradov.TradovU_Utilities.TradovU01_Logger import TradovLogger
    _log = TradovLogger.get_logger(__name__)
except ImportError:
    _log = logging.getLogger(__name__)

try:
    from Tradov.TradovU_Utilities.TradovU12_AgentIntegration import (
        AgentRegistry,
        get_registry,
    )
    REGISTRY_AVAILABLE = True
except ImportError:
    REGISTRY_AVAILABLE = False
    _log.warning("AgentRegistry unavailable — dashboard will show placeholder data")

# ==============================================================================
# CONSTANTS
# ==============================================================================
_REFRESH_INTERVAL_MS = 5_000   # 5 seconds

_STATUS_COLOURS: dict[str, str] = {
    "UP":      "#27ae60",   # green
    "DEGRADED":"#f39c12",   # amber
    "DOWN":    "#e74c3c",   # red
    "UNKNOWN": "#7f8c8d",   # grey
}

_TABLE_COLS = [
    "Agent ID", "Series", "Status", "Running",
    "Last HB (s)", "Decisions", "Failures", "Avg Latency ms", "Description",
]


# ==============================================================================
# WIDGET
# ==============================================================================

if HAS_QT:
    class AgentHealthDashboard(QWidget):
        """
        Real-time agent health panel.

        Embed in any QWidget layout::

            panel = AgentHealthDashboard(parent=self)
            layout.addWidget(panel)
        """

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            self._registry: AgentRegistry | None = get_registry() if REGISTRY_AVAILABLE else None
            self._filter_series = "All"
            self._setup_ui()
            self._setup_timer()
            self.refresh()

        # ------------------------------------------------------------------
        # UI construction
        # ------------------------------------------------------------------

        def _setup_ui(self) -> None:
            root = QVBoxLayout(self)
            root.setContentsMargins(8, 8, 8, 8)
            root.setSpacing(6)

            # ── Header row ────────────────────────────────────────────────
            header = QHBoxLayout()
            title = QLabel("Agent Health Dashboard")
            title_font = QFont()
            title_font.setPointSize(12)
            title.setFont(title_font)
            header.addWidget(title)
            header.addStretch()

            # Summary badges
            self._lbl_total    = self._badge("Total: —")
            self._lbl_running  = self._badge("Running: —")
            self._lbl_up       = self._badge("UP: —",       "#27ae60")
            self._lbl_degraded = self._badge("DEGRADED: —", "#f39c12")
            self._lbl_down     = self._badge("DOWN: —",     "#e74c3c")
            for lbl in (self._lbl_total, self._lbl_running, self._lbl_up,
                        self._lbl_degraded, self._lbl_down):
                header.addWidget(lbl)

            # Filter
            header.addWidget(QLabel("Series:"))
            self._series_combo = QComboBox()
            self._series_combo.addItems(["All", "X", "Y"])
            self._series_combo.currentTextChanged.connect(self._on_filter_changed)
            header.addWidget(self._series_combo)

            # Refresh button
            btn_refresh = QPushButton("Refresh")
            btn_refresh.clicked.connect(self.refresh)
            header.addWidget(btn_refresh)
            root.addLayout(header)

            # ── Separator ─────────────────────────────────────────────────
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setFrameShadow(QFrame.Sunken)
            root.addWidget(sep)

            # ── Table ─────────────────────────────────────────────────────
            self._table = QTableWidget(0, len(_TABLE_COLS))
            self._table.setHorizontalHeaderLabels(_TABLE_COLS)
            self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            self._table.horizontalHeader().setStretchLastSection(True)
            self._table.setEditTriggers(QTableWidget.NoEditTriggers)
            self._table.setAlternatingRowColors(True)
            self._table.setSelectionBehavior(QTableWidget.SelectRows)
            # Backward-compatible public alias used by legacy tests/widgets.
            self.table = self._table
            root.addWidget(self._table)

            # ── Status bar ────────────────────────────────────────────────
            self._status_lbl = QLabel("Last updated: —")
            self._status_lbl.setStyleSheet("color: #888; font-size: 10px;")
            root.addWidget(self._status_lbl)

        def _badge(self, text: str, colour: str = "#555") -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"background:{colour}; color:white; padding:2px 6px;"
                "border-radius:4px; font-size:11px;"
            )
            return lbl

        def _setup_timer(self) -> None:
            self._timer = QTimer(self)
            self._timer.setInterval(_REFRESH_INTERVAL_MS)
            self._timer.timeout.connect(self.refresh)
            self._timer.start()

        # ------------------------------------------------------------------
        # Data refresh
        # ------------------------------------------------------------------

        def refresh(self) -> None:
            """Pull latest data from AgentRegistry and repopulate the table."""
            if self._registry is None:
                self._show_placeholder()
                return

            summary = self._registry.health_summary()
            agents  = summary["agents"]

            # Apply series filter
            if self._filter_series != "All":
                agents = [a for a in agents if a["series"] == self._filter_series]

            self._update_badges(summary)
            self._populate_table(agents)
            self._status_lbl.setText(
                f"Last updated: {datetime.now(UTC).strftime('%H:%M:%S')} — "
                f"{len(agents)} agent(s) shown"
            )

        def _update_badges(self, summary: dict[str, Any]) -> None:
            by_status = summary["by_status"]
            self._lbl_total.setText(f"Total: {summary['total']}")
            self._lbl_running.setText(f"Running: {summary['running']}")
            self._lbl_up.setText(f"UP: {by_status.get('UP', 0)}")
            self._lbl_degraded.setText(f"DEGRADED: {by_status.get('DEGRADED', 0)}")
            self._lbl_down.setText(f"DOWN: {by_status.get('DOWN', 0)}")

        def _populate_table(self, agents: list[dict[str, Any]]) -> None:
            self._table.setRowCount(len(agents))
            for row, agent in enumerate(agents):
                status   = agent["status"]
                colour   = _STATUS_COLOURS.get(status, "#7f8c8d")
                bg       = QColor(colour)
                bg.setAlpha(40)   # translucent tint
                metrics  = agent.get("metrics", {})

                # Last heartbeat age
                hb_raw = agent.get("last_heartbeat")
                if hb_raw:
                    try:
                        hb_dt = datetime.fromisoformat(hb_raw)
                        if hb_dt.tzinfo is None:
                            hb_dt = hb_dt.replace(tzinfo=UTC)
                        age = (datetime.now(UTC) - hb_dt).total_seconds()
                        hb_text = f"{age:.0f}s ago"
                    except Exception:
                        hb_text = hb_raw
                else:
                    hb_text = "never"

                values = [
                    agent["agent_id"],
                    agent["series"],
                    status,
                    "Yes" if agent["running"] else "No",
                    hb_text,
                    str(metrics.get("decisions_made", 0)),
                    str(metrics.get("decisions_failed", 0)),
                    f"{metrics.get('avg_latency_ms', 0.0):.1f}",
                    agent.get("description", ""),
                ]

                for col, val in enumerate(values):
                    item = QTableWidgetItem(val)
                    item.setBackground(bg)
                    if col == 2:  # Status column — foreground colour
                        item.setForeground(QColor(colour))
                    self._table.setItem(row, col, item)

        def _show_placeholder(self) -> None:
            self._table.setRowCount(1)
            item = QTableWidgetItem("AgentRegistry not available — check TradovU12_AgentIntegration import")  # noqa: E501
            item.setForeground(QColor("#e74c3c"))
            self._table.setItem(0, 0, item)
            for col in range(1, len(_TABLE_COLS)):
                self._table.setItem(0, col, QTableWidgetItem(""))

        # ------------------------------------------------------------------
        # Filter
        # ------------------------------------------------------------------

        def _on_filter_changed(self, text: str) -> None:
            self._filter_series = text
            self.refresh()

else:
    # Headless stub so imports succeed in non-GUI environments
    class AgentHealthDashboard:  # type: ignore[no-redef]
        """Stub used when PySide6 is unavailable."""

        def __init__(self, parent: Any = None) -> None:
            _log.warning("AgentHealthDashboard: PySide6 not available — headless stub active")

        def refresh(self) -> None:
            pass
