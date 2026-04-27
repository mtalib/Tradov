#!/usr/bin/env python3
"""SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG20_DashboardBuilder.py
Purpose: Extracted UI builder helpers for SpyderG05_TradingDashboard
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-04-17 Time: 00:00:00
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import logging
import os
from typing import Any

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from Spyder.SpyderG_GUI.SpyderG13_EnhancedWidgets import (
    COLORS,
    GreekBar,
    MarketSymbolWidget,
    SignalMonitorPanel,
    TradingMode,
)

logger = logging.getLogger(__name__)

try:
    from Spyder.SpyderG_GUI.SpyderG16_CircuitBreakerMonitor import create_circuit_breaker_monitor

    circuit_breaker_monitor_available = True
except ImportError:
    create_circuit_breaker_monitor = None  # type: ignore
    circuit_breaker_monitor_available = False


def build_left_panel(dashboard: Any, market_symbols: dict[str, list[str]]) -> QWidget:
    """Create the market overview panel."""
    panel = QGroupBox("MARKET OVERVIEW")
    panel.setStyleSheet(f"background-color: {COLORS['background']};")
    layout = QVBoxLayout()
    layout.setContentsMargins(0, 10, 0, 0)

    header = QWidget()
    header_layout = QHBoxLayout()
    header_layout.setContentsMargins(10, 0, 5, 0)

    symbol_header = QLabel("SYMBOL")
    symbol_header.setFixedWidth(60)
    symbol_header.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 11px; font-weight: normal;")

    last_header = QLabel("LAST")
    last_header.setFixedWidth(70)
    last_header.setAlignment(Qt.AlignmentFlag.AlignRight)
    last_header.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 11px; font-weight: normal;")

    chg_header = QLabel("CHG")
    chg_header.setFixedWidth(55)
    chg_header.setAlignment(Qt.AlignmentFlag.AlignRight)
    chg_header.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 11px; font-weight: normal;")

    chg_pct_header = QLabel("CHG%")
    chg_pct_header.setFixedWidth(55)
    chg_pct_header.setAlignment(Qt.AlignmentFlag.AlignRight)
    chg_pct_header.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 11px; font-weight: normal;")

    header_layout.addWidget(symbol_header)
    header_layout.addWidget(last_header)
    header_layout.addWidget(chg_header)
    header_layout.addWidget(chg_pct_header)
    header.setLayout(header_layout)
    layout.addWidget(header)

    separator = QFrame()
    separator.setFrameShape(QFrame.Shape.HLine)
    separator.setStyleSheet(f"color: {COLORS['border']};")
    layout.addWidget(separator)

    scroll_area = QScrollArea()
    scroll_area.setStyleSheet(f"background-color: {COLORS['background']};")
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_widget = QWidget()
    scroll_widget.setStyleSheet(f"background-color: {COLORS['background']};")
    scroll_layout = QVBoxLayout()
    scroll_layout.setSpacing(1)

    dashboard.symbol_widgets = {}
    for category, symbols in market_symbols.items():
        cat_label = QLabel(category)
        cat_label.setStyleSheet(
            f"color: {COLORS['cyan']}; font-size: 12px; padding: 3px 0px 1px 10px; font-weight: normal;",
        )
        scroll_layout.addWidget(cat_label)

        for symbol in symbols:
            widget = MarketSymbolWidget(symbol, category)
            widget.setStyleSheet(f"background-color: {COLORS['background']};")
            dashboard.symbol_widgets[symbol] = widget
            # Forward left-click → dashboard so detail dialogs (e.g. PMR) can open.
            if hasattr(dashboard, "_on_symbol_widget_clicked"):
                widget.clicked.connect(dashboard._on_symbol_widget_clicked)
            scroll_layout.addWidget(widget)

    scroll_layout.addStretch()
    scroll_widget.setLayout(scroll_layout)
    scroll_area.setWidget(scroll_widget)
    scroll_area.setWidgetResizable(True)

    layout.addWidget(scroll_area)
    panel.setLayout(layout)
    return panel


def build_center_panel(dashboard: Any) -> QWidget:
    """Create the center panel containing chart, positions, logs, and signals."""
    panel = QWidget()
    layout = QVBoxLayout()

    regime_widget = QWidget()
    regime_widget.setStyleSheet(
        f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};",
    )
    regime_widget.setFixedHeight(40)
    regime_layout = QHBoxLayout()

    regime_layout.addStretch()

    center_container = QHBoxLayout()
    center_container.setSpacing(20)

    spy_label = QLabel("SPY - 5 MIN")
    spy_label.setStyleSheet(
        f"color: {COLORS['text']}; font-size: 13px;",
    )
    center_container.addWidget(spy_label)

    separator_label0 = QLabel("|")
    separator_label0.setStyleSheet(f"color: {COLORS['text_dim']};")
    center_container.addWidget(separator_label0)

    regime_section = QHBoxLayout()
    regime_section.setSpacing(5)
    regime_label = QLabel("MARKET REGIME: ")
    regime_label.setStyleSheet(f"color: {COLORS['text']};")
    regime_section.addWidget(regime_label)

    dashboard.regime_value = QLabel("—")
    dashboard.regime_value.setStyleSheet(f"color: {COLORS['cyan']};")
    regime_section.addWidget(dashboard.regime_value)

    center_container.addLayout(regime_section)

    separator_label = QLabel("|")
    separator_label.setStyleSheet(f"color: {COLORS['text_dim']};")
    center_container.addWidget(separator_label)

    strategy_section = QHBoxLayout()
    strategy_section.setSpacing(5)
    strategy_label = QLabel("CURRENT ACTIVE STRATEGY: ")
    strategy_label.setStyleSheet(f"color: {COLORS['text']};")
    strategy_section.addWidget(strategy_label)

    dashboard.strategy_value = QLabel("—")
    dashboard.strategy_value.setStyleSheet(f"color: {COLORS['cyan']};")
    strategy_section.addWidget(dashboard.strategy_value)

    strategy_section.addSpacing(15)

    dashboard.chart_toggle_btn = QPushButton("📊")
    dashboard.chart_toggle_btn.setFixedSize(30, 30)
    dashboard.chart_toggle_btn.setToolTip("Toggle SPY Chart (5-min)")
    dashboard.chart_toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 3px;
                color: {COLORS['cyan']};
                font-size: 16px;
                padding: 2px;
                margin-top: -3px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['border']};
                border: 1px solid {COLORS['cyan']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['cyan']};
                color: {COLORS['background']};
            }}
        """)
    dashboard.chart_toggle_btn.clicked.connect(dashboard.toggle_chart)
    strategy_section.addWidget(dashboard.chart_toggle_btn)

    center_container.addLayout(strategy_section)

    regime_layout.addLayout(center_container)
    regime_layout.addStretch()

    regime_widget.setLayout(regime_layout)
    layout.addWidget(regime_widget)

    create_chart_widget(dashboard)
    dashboard.chart_visible = True
    layout.addWidget(dashboard.chart_widget, 2)

    create_chart_hidden_controls_panel(dashboard)
    dashboard.chart_hidden_controls_panel.hide()
    layout.addWidget(dashboard.chart_hidden_controls_panel, 2)

    positions_group = QGroupBox()
    positions_layout = QVBoxLayout()
    positions_layout.setContentsMargins(2, 2, 2, 2)
    positions_layout.setSpacing(2)

    pos_toolbar = QWidget()
    pos_toolbar_layout = QHBoxLayout(pos_toolbar)
    pos_toolbar_layout.setContentsMargins(0, 0, 0, 0)
    pos_toolbar_layout.setSpacing(4)
    dashboard.orders_title_label = QLabel()
    dashboard._update_orders_title()
    pos_toolbar_layout.addWidget(dashboard.orders_title_label)
    pos_toolbar_layout.addStretch()
    dashboard.refresh_orders_btn = QPushButton("⟳ Refresh")
    dashboard.refresh_orders_btn.setFixedHeight(20)
    dashboard.refresh_orders_btn.setStyleSheet(
        f"font-size: 11px; padding: 0 6px; background-color: {COLORS['panel']};"
        f" color: {COLORS['text']}; border: 1px solid {COLORS['border']}; border-radius: 3px;"
    )
    dashboard.refresh_orders_btn.setToolTip("Fetch live orders & positions from Tradier")
    dashboard.refresh_orders_btn.clicked.connect(dashboard._refresh_positions_table)
    pos_toolbar_layout.addWidget(dashboard.refresh_orders_btn)
    positions_layout.addWidget(pos_toolbar)

    # All portfolio-strip labels are now None — data is surfaced via the
    # popup dialog (dashboard._open_portfolio_summary_dialog) which reads
    # from dashboard._portfolio_summary_cache populated by _refresh_spreads_panel.
    dashboard.spreads_summary_label = None
    dashboard.atm_iv_label = None
    dashboard.iv_rank_label = None
    dashboard.realized_today_label = None
    dashboard.port_delta_label = None
    dashboard.port_gamma_label = None
    dashboard.port_theta_label = None
    dashboard.port_vega_label = None
    dashboard.bp_used_label = None

    dashboard.positions_table = create_positions_table(dashboard)
    dashboard.positions_table.setMinimumHeight(200)

    # Tree of spreads + legs (paper) or broker orders/positions (live).
    positions_layout.addWidget(dashboard.positions_table)

    # The standalone spreads_table is removed — its rows are now top-level
    # parents inside positions_table when paper mode is active. _refresh_spreads_panel
    # checks `if self.spreads_table is None` and skips its old population path.
    dashboard.spreads_table = None

    positions_group.setLayout(positions_layout)
    dashboard.positions_group = positions_group
    dashboard.spreads_group = positions_group  # backwards-compat alias
    layout.addWidget(positions_group, 1)

    logs_container = QWidget()
    logs_container.setFixedHeight(190)
    logs_container_layout = QHBoxLayout()
    logs_container_layout.setSpacing(5)
    logs_container_layout.setContentsMargins(0, 0, 0, 0)

    logs_group = QGroupBox("")  # Empty title; we'll create our own header
    logs_layout = QVBoxLayout()
    logs_layout.setContentsMargins(6, 6, 6, 6)
    logs_layout.setSpacing(3)

    # Header row: "SYSTEM LOG" label + NORMAL/DEBUG button
    logs_header_row = QWidget()
    logs_header_layout = QHBoxLayout()
    logs_header_layout.setContentsMargins(0, 0, 0, 0)
    logs_header_layout.setSpacing(6)

    logs_title = QLabel("SYSTEM LOG")
    logs_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: normal;")
    logs_header_layout.addWidget(logs_title)
    logs_header_layout.addStretch()

    dashboard.system_log_mode_btn = QPushButton("NORMAL")
    dashboard.system_log_mode_btn.setFixedWidth(72)
    dashboard.system_log_mode_btn.setToolTip("Toggle system log verbosity (NORMAL/DEBUG)")
    # Initial stylesheet with green (positive) color like START TRADING
    dashboard._system_log_mode_btn_normal_stylesheet = f"""
        QPushButton {{
            color: black;
            background-color: {COLORS["positive"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: normal;
        }}
        QPushButton:hover {{
            border: 1px solid #00ff00;
        }}
    """
    dashboard._system_log_mode_btn_debug_stylesheet = f"""
        QPushButton {{
            color: black;
            background-color: {COLORS["warning"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: normal;
        }}
        QPushButton:hover {{
            border: 1px solid #ffcc00;
        }}
    """
    dashboard.system_log_mode_btn.setStyleSheet(dashboard._system_log_mode_btn_normal_stylesheet)
    dashboard.system_log_mode_btn.clicked.connect(dashboard.toggle_system_log_verbosity)
    logs_header_layout.addWidget(dashboard.system_log_mode_btn)
    logs_header_row.setLayout(logs_header_layout)
    logs_layout.addWidget(logs_header_row)

    dashboard.system_log = QTextEdit()
    dashboard.system_log.setReadOnly(True)
    dashboard.system_log.setMaximumHeight(150)
    dashboard.system_log.setStyleSheet(
        f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 13px;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {COLORS["panel"]};
            }}
        """,
    )

    logs_layout.addWidget(dashboard.system_log)
    logs_group.setLayout(logs_layout)

    signal_group = QGroupBox("SIGNAL MONITOR")
    signal_group.setStyleSheet(
        f"QGroupBox {{ color: {COLORS['text']}; font-weight: normal; }}",
    )
    signal_layout = QVBoxLayout()
    signal_layout.setContentsMargins(5, 5, 5, 5)

    dashboard.signal_panel = SignalMonitorPanel()
    signal_layout.addWidget(dashboard.signal_panel)
    signal_group.setLayout(signal_layout)

    logs_container_layout.addWidget(logs_group, 65)
    logs_container_layout.addWidget(signal_group, 35)
    logs_container.setLayout(logs_container_layout)

    dashboard.paper_pnl_widget = None
    dashboard.backtest_pnl_widget = None
    dashboard._paper_metric_labels = {}
    dashboard._paper_status_label = None
    dashboard.backtest_controls = None

    layout.addWidget(logs_container, 0)

    panel.setLayout(layout)
    return panel


def build_right_panel(dashboard: Any) -> QWidget:
    """Create the right-hand controls and metrics panel."""
    panel = QWidget()
    panel.setMinimumWidth(580)
    layout = QVBoxLayout()
    layout.setSpacing(3)
    layout.setContentsMargins(5, 5, 5, 5)

    button_layout = QHBoxLayout()

    dashboard.start_btn = QPushButton("START TRADING")
    dashboard.start_btn.setStyleSheet(
        f"background-color: {COLORS['positive']}; color: black;",
    )
    dashboard.start_btn.setToolTip("Start automated trading")
    dashboard.start_btn.clicked.connect(dashboard.start_trading)
    button_layout.addWidget(dashboard.start_btn)

    dashboard.stop_btn = QPushButton("STOP TRADING")
    dashboard.stop_btn.setStyleSheet(f"background-color: {COLORS['warning']}; color: black;")
    dashboard.stop_btn.setToolTip("Stop trading but keep orders and positions")
    dashboard.stop_btn.clicked.connect(dashboard.stop_trading)
    button_layout.addWidget(dashboard.stop_btn)

    dashboard.emergency_btn = QPushButton("EMERGENCY CLOSE")
    dashboard.emergency_btn.setStyleSheet(f"background-color: {COLORS['negative']}; color: black;")
    dashboard.emergency_btn.setToolTip(
        "Close all orders and positions, stop trading, and disconnect from API",
    )
    dashboard.emergency_btn.clicked.connect(dashboard.emergency_close)
    button_layout.addWidget(dashboard.emergency_btn)

    layout.addLayout(button_layout)

    if circuit_breaker_monitor_available:
        try:
            circuit_breaker_widget = create_circuit_breaker_monitor(parent=dashboard)
            circuit_breaker_widget.setMaximumHeight(85)
            layout.addSpacing(8)
            layout.addWidget(circuit_breaker_widget)
        except Exception as exc:
            logger.info("⚠️ Failed to create circuit breaker monitor: %s", exc)

    account_widget = QWidget()
    account_widget.setStyleSheet(
        f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; border-radius: 5px;",
    )
    acct_grid = QGridLayout()
    acct_grid.setContentsMargins(4, 4, 4, 4)
    acct_grid.setHorizontalSpacing(3)
    acct_grid.setVerticalSpacing(3)
    acct_grid.setColumnStretch(0, 3)
    acct_grid.setColumnStretch(1, 4)
    acct_grid.setColumnStretch(2, 3)
    acct_grid.setColumnStretch(3, 4)

    cell_style = f"padding: 2px 5px; background-color: {COLORS['background']}; border: 1px solid {COLORS['border']}; font-size: 12px;"

    acct_grid.addWidget(dashboard._acct_lbl("ACCOUNT", cell_style), 0, 0)
    trading_mode_init = os.environ.get("TRADING_MODE", "paper").lower()
    display_acct_id = (
        os.environ.get("TRADIER_SANDBOX_ACCOUNT_ID", "—")
        if trading_mode_init == "paper"
        else os.environ.get("TRADIER_ACCOUNT_ID", "—")
    )
    dashboard.acct_number_lbl = dashboard._acct_lbl(display_acct_id, cell_style)
    acct_grid.addWidget(dashboard.acct_number_lbl, 0, 1)

    mode_container = QWidget()
    mode_layout = QHBoxLayout(mode_container)
    mode_layout.setContentsMargins(0, 0, 0, 0)
    mode_layout.setSpacing(2)

    dashboard.live_btn = QPushButton("LIVE TRADING")
    dashboard.live_btn.setToolTip("Switch to LIVE trading — real order execution at Tradier")
    dashboard.paper_btn = QPushButton("PAPER TRADING")
    dashboard.paper_btn.setToolTip("Switch to PAPER trading — simulated fills, Tradier sandbox")

    mode_layout.addWidget(dashboard.live_btn)
    mode_layout.addWidget(dashboard.paper_btn)
    acct_grid.addWidget(mode_container, 0, 2, 1, 2)

    dashboard.live_btn.clicked.connect(lambda: dashboard._on_mode_btn_clicked(TradingMode.LIVE))
    dashboard.paper_btn.clicked.connect(lambda: dashboard._on_mode_btn_clicked(TradingMode.PAPER))
    dashboard._update_mode_buttons()
    dashboard.mode_selector = None
    dashboard.mode_lbl = None

    acct_grid.addWidget(dashboard._acct_lbl("SETTLED CASH", cell_style), 1, 0)
    dashboard.settled_value = dashboard._acct_lbl("—", cell_style, right=True)
    acct_grid.addWidget(dashboard.settled_value, 1, 1)
    acct_grid.addWidget(dashboard._acct_lbl("BUYING POWER", cell_style), 1, 2)
    dashboard.buying_value = dashboard._acct_lbl("—", cell_style, right=True)
    acct_grid.addWidget(dashboard.buying_value, 1, 3)

    acct_grid.addWidget(dashboard._acct_lbl("REALIZED P&L", cell_style), 2, 0)
    dashboard.realized_value = dashboard._acct_lbl("—", cell_style + f"color: {COLORS['positive']};", right=True)
    acct_grid.addWidget(dashboard.realized_value, 2, 1)
    acct_grid.addWidget(dashboard._acct_lbl("UNREALIZED P&L", cell_style), 2, 2)
    dashboard.unrealized_value = dashboard._acct_lbl("—", cell_style + f"color: {COLORS['positive']};", right=True)
    acct_grid.addWidget(dashboard.unrealized_value, 2, 3)

    account_widget.setLayout(acct_grid)
    layout.addWidget(account_widget)

    pnl_group = QGroupBox("")
    pnl_group.setStyleSheet(
        f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 0px;
                padding-top: 6px;
                background-color: {COLORS['background']};
            }}
            """,
    )
    pnl_layout = QVBoxLayout()
    pnl_layout.setContentsMargins(5, 8, 5, 5)
    pnl_layout.setSpacing(1)

    dashboard.pnl_title_lbl = QLabel()
    dashboard._update_pnl_title()
    pnl_layout.addWidget(dashboard.pnl_title_lbl)

    dashboard.pnl_table = create_pnl_table()
    dashboard.pnl_table.setFixedHeight(140)
    pnl_layout.addWidget(dashboard.pnl_table)

    pnl_group.setLayout(pnl_layout)
    layout.addWidget(pnl_group)

    risk_group = QGroupBox("")
    risk_group.setStyleSheet(
        f"""
            QGroupBox {{
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 0px;
                padding-top: 6px;
                background-color: {COLORS['background']};
            }}
            """,
    )
    risk_layout = QVBoxLayout()
    risk_layout.setSpacing(2)
    risk_layout.setContentsMargins(5, 8, 5, 5)

    risk_header = QHBoxLayout()
    risk_title_lbl = QLabel("RISK MONITOR")
    risk_title_lbl.setStyleSheet(
        f"color: {COLORS['text']}; font-size: 15px; font-weight: normal; letter-spacing: 1px;",
    )
    risk_header.addWidget(risk_title_lbl)
    risk_header.addStretch()
    risk_layout.addLayout(risk_header)

    dashboard.greek_bars = {
        "delta": GreekBar("Delta", -100, 100),
        "gamma": GreekBar("Gamma", -10, 10),
        "theta": GreekBar("Theta", -400, 0),
        "vega": GreekBar("Vega", -600, 0),
    }
    for bar in dashboard.greek_bars.values():
        risk_layout.addWidget(bar)

    risk_group.setLayout(risk_layout)
    layout.addWidget(risk_group)

    # These diagnostics are shown in the chart-hidden controls panel to keep
    # the default right-hand dashboard view visually clean.
    dashboard.liquidity_candidates_value = None
    dashboard.liquidity_pass_ratio_value = None
    dashboard.liquidity_freshness_value = None
    dashboard.liquidity_top_failure_value = None
    dashboard.execution_slippage_bps_value = None
    dashboard.execution_fill_latency_value = None
    dashboard.execution_reject_rate_value = None
    dashboard.execution_partial_fill_value = None

    auto_group = QGroupBox("AUTONOMOUS AI ACTIVITY")
    auto_group.setStyleSheet(
        f"""
            QGroupBox {{
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
                margin-top: 12px;
                padding-top: 5px;
                background-color: {COLORS["background"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                top: -2px;
            }}
        """,
    )
    auto_layout = QVBoxLayout()
    auto_layout.setContentsMargins(5, 5, 5, 5)
    auto_layout.setSpacing(0)

    dashboard.auto_log = QTextEdit()
    dashboard.auto_log.setReadOnly(True)
    dashboard.auto_log.setFixedHeight(110)
    dashboard.auto_log.setStyleSheet(
        f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 13px;
                color: {COLORS["cyan"]};
                padding: 1px;
                border: 1px solid {COLORS["border"]};
                background-color: {COLORS["panel"]};
                margin: 0px;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {COLORS["panel"]};
            }}
        """,
    )
    dashboard.auto_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    dashboard.auto_log.setHorizontalScrollBarPolicy(
        Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
    )

    auto_layout.addWidget(dashboard.auto_log)
    auto_group.setLayout(auto_layout)
    layout.addWidget(auto_group)

    metrics_widget = create_unified_prometheus_metrics(dashboard)
    layout.addWidget(metrics_widget)

    panel.setLayout(layout)
    return panel


def create_chart_widget(dashboard: Any) -> None:
    """Create the chart widget and attach it to the dashboard instance."""
    dashboard.chart_widget = QWidget()
    dashboard.chart_widget.setStyleSheet(
        f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};",
    )

    layout = QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    dashboard.figure = Figure(figsize=(10, 6), dpi=100)
    dashboard.figure.patch.set_facecolor(COLORS["panel"])

    dashboard.canvas = FigureCanvas(dashboard.figure)
    dashboard.canvas.setStyleSheet("background-color: transparent;")
    layout.addWidget(dashboard.canvas)

    dashboard.chart_widget.setLayout(layout)
    dashboard.update_chart()


def create_chart_hidden_controls_panel(dashboard: Any) -> None:
    """Create chart replacement panel shown when the chart is hidden."""
    dashboard.chart_hidden_controls_panel = QWidget()
    dashboard.chart_hidden_controls_panel.setStyleSheet(
        f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};",
    )

    layout = QVBoxLayout()
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(8)

    title = QLabel("ADVANCED CONTROLS (CHART HIDDEN)")
    title.setStyleSheet(
        f"color: {COLORS['text']}; font-size: 13px; letter-spacing: 1px;",
    )
    layout.addWidget(title)

    event_clock_group = QGroupBox("EVENT-CLOCK STATUS")
    event_clock_group.setStyleSheet(f"""
        QGroupBox {{
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 4px;
            margin-top: 5px;
            padding-top: 5px;
            background-color: {COLORS["panel"]};
            font-weight: bold;
            font-size: 11px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 3px 0 3px;
        }}
    """)
    event_clock_layout = QVBoxLayout()
    event_clock_layout.setContentsMargins(5, 5, 5, 5)
    event_clock_layout.setSpacing(2)

    dashboard.event_clock_state_label = QLabel("✓ CLEAR")
    dashboard.event_clock_state_label.setStyleSheet(
        f"color: {COLORS['positive']}; font-weight: bold; font-size: 12px;"
    )
    event_clock_layout.addWidget(dashboard.event_clock_state_label)

    dashboard.event_clock_policy_label = QLabel("Policy: ✓ Enabled | Sources: calendar+manual")
    dashboard.event_clock_policy_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
    event_clock_layout.addWidget(dashboard.event_clock_policy_label)

    dashboard.event_clock_windows_label = QLabel("Blackout: -30m / +30m | Size: 25%")
    dashboard.event_clock_windows_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
    event_clock_layout.addWidget(dashboard.event_clock_windows_label)

    dashboard.event_clock_strategies_label = QLabel("Allowlist: None")
    dashboard.event_clock_strategies_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
    event_clock_layout.addWidget(dashboard.event_clock_strategies_label)

    event_clock_group.setLayout(event_clock_layout)
    dashboard.event_clock_panel = event_clock_group
    layout.addWidget(event_clock_group)

    readiness_row = QHBoxLayout()
    readiness_row.setSpacing(6)

    dashboard.readiness_btn = QPushButton("RE-EVALUATE TRADING READINESS")
    dashboard.readiness_btn.setFixedHeight(26)
    dashboard.readiness_btn.setStyleSheet(
        "background-color: #0066CC; color: white; font-size: 12px; "
        "padding: 0 12px; border: 1px solid #2A7BD6; border-radius: 3px;"
    )
    dashboard.readiness_btn.setToolTip("Evaluate trading readiness and produce NO/OK decision")
    dashboard.readiness_btn.clicked.connect(dashboard.run_trading_readiness_check_async)
    readiness_row.addWidget(dashboard.readiness_btn)

    dashboard.readiness_status_label = QLabel("<<READINESS PENDING>>")
    dashboard.readiness_status_label.setWordWrap(True)
    dashboard.readiness_status_label.setSizePolicy(
        QSizePolicy.Policy.Expanding,
        QSizePolicy.Policy.Preferred,
    )
    dashboard.readiness_status_label.setStyleSheet(
        "color: white; font-size: 13px; font-weight: 600;"
    )
    readiness_row.addWidget(dashboard.readiness_status_label, 1)  # stretch=1 → fills remaining width

    layout.addLayout(readiness_row)

    action_row = QHBoxLayout()
    action_row.setSpacing(6)

    blue_button_style = (
        "background-color: #0066CC; color: white; font-size: 12px; "
        "padding: 0 12px; border: 1px solid #2A7BD6; border-radius: 3px;"
    )
    action_button_width = 156

    dashboard.risk_params_btn = QPushButton("RISK LEVELS")
    dashboard.risk_params_btn.setFixedHeight(26)
    dashboard.risk_params_btn.setFixedWidth(action_button_width)
    dashboard.risk_params_btn.setStyleSheet(blue_button_style)
    dashboard.risk_params_btn.setToolTip("Configure global and strategy-specific risk parameters")
    dashboard.risk_params_btn.clicked.connect(dashboard.show_risk_parameters)
    action_row.addWidget(dashboard.risk_params_btn)

    dashboard.portfolio_strip_btn = QPushButton("PORTFOLIO STRIP")
    dashboard.portfolio_strip_btn.setFixedHeight(26)
    dashboard.portfolio_strip_btn.setFixedWidth(action_button_width)
    dashboard.portfolio_strip_btn.setStyleSheet(blue_button_style)
    dashboard.portfolio_strip_btn.setToolTip("Open Today's Portfolio Summary")
    dashboard.portfolio_strip_btn.clicked.connect(dashboard._open_portfolio_summary_dialog)
    action_row.addWidget(dashboard.portfolio_strip_btn)

    dashboard.decision_log_btn = QPushButton("DECISION LOG")
    dashboard.decision_log_btn.setFixedHeight(26)
    dashboard.decision_log_btn.setFixedWidth(action_button_width)
    dashboard.decision_log_btn.setStyleSheet(blue_button_style)
    dashboard.decision_log_btn.setToolTip(
        "Open the Decision Log dialog (per-poll audit: signal, regime, action)"
    )
    dashboard.decision_log_btn.clicked.connect(dashboard._open_decision_log_dialog)
    action_row.addWidget(dashboard.decision_log_btn)

    dashboard.trade_audit_btn = QPushButton("AUDIT")
    dashboard.trade_audit_btn.setFixedHeight(26)
    dashboard.trade_audit_btn.setFixedWidth(action_button_width)
    dashboard.trade_audit_btn.setStyleSheet(blue_button_style)
    dashboard.trade_audit_btn.setToolTip("Open the Trade Audit dialog (closed spreads + CSV export)")
    dashboard.trade_audit_btn.clicked.connect(dashboard._open_trade_audit_dialog)
    action_row.addWidget(dashboard.trade_audit_btn)

    action_row.addStretch(1)
    layout.addLayout(action_row)

    diagnostics_row = QHBoxLayout()
    diagnostics_row.setSpacing(8)

    liquidity_group = QGroupBox("LIQUIDITY DIAGNOSTICS")
    liquidity_group.setStyleSheet(
        f"""
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 6px;
                background-color: {COLORS['background']};
            }}
        """,
    )
    liquidity_layout = QGridLayout()
    liquidity_layout.setContentsMargins(6, 6, 6, 6)
    liquidity_layout.setHorizontalSpacing(8)
    liquidity_layout.setVerticalSpacing(3)

    label_style = f"color: {COLORS['text']}; font-size: 11px;"
    value_style = f"color: {COLORS['cyan']}; font-size: 11px;"

    liquidity_candidates_lbl = QLabel("Candidates")
    liquidity_candidates_lbl.setStyleSheet(label_style)
    dashboard.liquidity_candidates_value = QLabel("-")
    dashboard.liquidity_candidates_value.setStyleSheet(value_style)

    liquidity_pass_lbl = QLabel("Pass Ratio")
    liquidity_pass_lbl.setStyleSheet(label_style)
    dashboard.liquidity_pass_ratio_value = QLabel("-")
    dashboard.liquidity_pass_ratio_value.setStyleSheet(value_style)

    liquidity_freshness_lbl = QLabel("Freshness")
    liquidity_freshness_lbl.setStyleSheet(label_style)
    dashboard.liquidity_freshness_value = QLabel("-")
    dashboard.liquidity_freshness_value.setStyleSheet(value_style)

    liquidity_fail_lbl = QLabel("Top Failure")
    liquidity_fail_lbl.setStyleSheet(label_style)
    dashboard.liquidity_top_failure_value = QLabel("-")
    dashboard.liquidity_top_failure_value.setStyleSheet(value_style)
    dashboard.liquidity_top_failure_value.setWordWrap(True)

    liquidity_layout.addWidget(liquidity_candidates_lbl, 0, 0)
    liquidity_layout.addWidget(dashboard.liquidity_candidates_value, 0, 1)
    liquidity_layout.addWidget(liquidity_pass_lbl, 1, 0)
    liquidity_layout.addWidget(dashboard.liquidity_pass_ratio_value, 1, 1)
    liquidity_layout.addWidget(liquidity_freshness_lbl, 2, 0)
    liquidity_layout.addWidget(dashboard.liquidity_freshness_value, 2, 1)
    liquidity_layout.addWidget(liquidity_fail_lbl, 3, 0)
    liquidity_layout.addWidget(dashboard.liquidity_top_failure_value, 3, 1)
    liquidity_group.setLayout(liquidity_layout)
    diagnostics_row.addWidget(liquidity_group)

    execution_group = QGroupBox("EXECUTION HEALTH")
    execution_group.setStyleSheet(
        f"""
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 8px;
                padding-top: 6px;
                background-color: {COLORS['background']};
            }}
        """,
    )
    execution_layout = QGridLayout()
    execution_layout.setContentsMargins(6, 6, 6, 6)
    execution_layout.setHorizontalSpacing(8)
    execution_layout.setVerticalSpacing(3)

    exec_label_style = f"color: {COLORS['text']}; font-size: 11px;"
    exec_value_style = f"color: {COLORS['cyan']}; font-size: 11px;"

    execution_slippage_lbl = QLabel("Slippage")
    execution_slippage_lbl.setStyleSheet(exec_label_style)
    dashboard.execution_slippage_bps_value = QLabel("-")
    dashboard.execution_slippage_bps_value.setStyleSheet(exec_value_style)

    execution_latency_lbl = QLabel("Fill Latency")
    execution_latency_lbl.setStyleSheet(exec_label_style)
    dashboard.execution_fill_latency_value = QLabel("-")
    dashboard.execution_fill_latency_value.setStyleSheet(exec_value_style)

    execution_reject_lbl = QLabel("Reject Rate")
    execution_reject_lbl.setStyleSheet(exec_label_style)
    dashboard.execution_reject_rate_value = QLabel("-")
    dashboard.execution_reject_rate_value.setStyleSheet(exec_value_style)

    execution_partial_lbl = QLabel("Partial Fill")
    execution_partial_lbl.setStyleSheet(exec_label_style)
    dashboard.execution_partial_fill_value = QLabel("-")
    dashboard.execution_partial_fill_value.setStyleSheet(exec_value_style)

    execution_layout.addWidget(execution_slippage_lbl, 0, 0)
    execution_layout.addWidget(dashboard.execution_slippage_bps_value, 0, 1)
    execution_layout.addWidget(execution_latency_lbl, 1, 0)
    execution_layout.addWidget(dashboard.execution_fill_latency_value, 1, 1)
    execution_layout.addWidget(execution_reject_lbl, 2, 0)
    execution_layout.addWidget(dashboard.execution_reject_rate_value, 2, 1)
    execution_layout.addWidget(execution_partial_lbl, 3, 0)
    execution_layout.addWidget(dashboard.execution_partial_fill_value, 3, 1)
    execution_group.setLayout(execution_layout)
    diagnostics_row.addWidget(execution_group)

    layout.addLayout(diagnostics_row)
    layout.addStretch(1)

    dashboard.chart_hidden_controls_panel.setLayout(layout)


def create_positions_table(dashboard: Any) -> QTreeWidget:
    """Create the positions tree widget."""
    tree = QTreeWidget()
    columns = ["     LEG", "STRIKE", "CONT", "EXPIRY", "COST", "P&L", ""]
    tree.setColumnCount(len(columns))
    tree.setHeaderLabels(columns)

    for col in range(len(columns)):
        tree.headerItem().setTextAlignment(col, Qt.AlignmentFlag.AlignCenter)

    tree.setAlternatingRowColors(False)
    tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
    tree.setRootIsDecorated(False)
    tree.setAnimated(True)
    tree.setIndentation(20)
    tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tree.customContextMenuRequested.connect(dashboard._positions_context_menu)
    tree.setStyleSheet(
        f"""
            QTreeWidget {{
                font-size: 11px;
                background-color: {COLORS["background"]};
                border: none;
                outline: none;
            }}
            QTreeWidget::item {{
                padding: 2px 4px;
                border-bottom: 1px solid {COLORS["border"]};
            }}
            QTreeWidget::item:selected {{
                background-color: #2a3a4a;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: none;
                border-image: none;
            }}
            QTreeWidget::branch:open:has-children:!has-siblings,
            QTreeWidget::branch:open:has-children:has-siblings {{
                image: none;
                border-image: none;
            }}
            QHeaderView::section {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 2px;
                font-size: 12px;
                font-weight: normal;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {COLORS["panel"]};
            }}
        """,
    )

    tree.setColumnWidth(0, 100)
    tree.setColumnWidth(1, 80)
    tree.setColumnWidth(2, 45)
    tree.setColumnWidth(3, 65)
    tree.setColumnWidth(4, 90)
    tree.setColumnWidth(5, 90)
    tree.header().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
    tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    tree.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    return tree


def create_pnl_table() -> QTableWidget:
    """Create the P&L performance table."""
    table = QTableWidget(4, 8)
    headers = [
        "PERIOD",
        "P&L",
        "WIN RATE",
        "WIN/LOSS",
        "PROFIT-F",
        "SHARP",
        "SORTINO",
        "CALMAR",
    ]
    table.setHorizontalHeaderLabels(headers)

    periods = ["TODAY", "WEEK", "MONTH", "YEAR"]
    data = [
        ("—", "—", "—", "—", "—", "—", "—"),
        ("—", "—", "—", "—", "—", "—", "—"),
        ("—", "—", "—", "—", "—", "—", "—"),
        ("—", "—", "—", "—", "—", "—", "—"),
    ]

    for row, (period, values) in enumerate(zip(periods, data, strict=False)):
        period_item = QTableWidgetItem(period)
        period_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(row, 0, period_item)

        pnl_item = QTableWidgetItem(values[0])
        pnl_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pnl_item.setForeground(QColor(COLORS["positive"]))
        table.setItem(row, 1, pnl_item)

        win_rate_item = QTableWidgetItem(values[1])
        win_rate_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 2, win_rate_item)

        avg_item = QTableWidgetItem(values[2])
        avg_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 3, avg_item)

        profit_factor_item = QTableWidgetItem(values[3])
        profit_factor_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 4, profit_factor_item)

        sharp_ratio_item = QTableWidgetItem(values[4])
        sharp_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 5, sharp_ratio_item)

        sortino_ratio_item = QTableWidgetItem(values[5])
        sortino_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 6, sortino_ratio_item)

        calmar_ratio_item = QTableWidgetItem(values[6])
        calmar_ratio_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 7, calmar_ratio_item)

    table.setStyleSheet(
        """
            QTableWidget { font-size: 11px; }
            QHeaderView::section { font-weight: normal; font-size: 11px; }
            """,
    )
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(26)

    header = table.horizontalHeader()
    header.setStretchLastSection(False)
    for col in range(8):
        header.setSectionResizeMode(col, header.ResizeMode.Stretch)
    table.setColumnWidth(5, 52)
    header.setSectionResizeMode(5, header.ResizeMode.Fixed)

    header_tooltips = {
        2: "WIN RATE: percentage of trades that closed with a profit",
        3: "WIN/LOSS: average winning trade size versus average losing trade size",
        4: "PROFIT FACTOR: gross profit divided by gross loss — values above 1.0 indicate a profitable strategy",
        5: "SHARPE RATIO: return earned above the risk-free rate per unit of total volatility — higher is better",
        6: "SORTINO RATIO: like the sharpe ratio but only penalises downside volatility, not upside swings",
        7: "CALMAR RATIO: annualised return divided by maximum drawdown — measures return relative to worst loss",
    }
    for col, tip in header_tooltips.items():
        item = table.horizontalHeaderItem(col)
        if item:
            item.setToolTip(tip)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return table


def create_unified_prometheus_metrics(dashboard: Any) -> QWidget:
    """Create the unified Prometheus metrics widget."""
    container = QWidget()
    container.setStyleSheet(
        f"""
            QWidget {{
                background-color: {COLORS["panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
            }}
        """,
    )
    container.setFixedHeight(200)

    main_layout = QVBoxLayout()
    main_layout.setContentsMargins(10, 8, 10, 8)
    main_layout.setSpacing(2)

    title_layout = QHBoxLayout()
    title_label = QLabel("PROMETHEUS METRICS MONITOR")
    title_label.setStyleSheet(
        f"""
            color: {COLORS["text"]};
            font-size: 14px;
            font-weight: normal;
            padding-bottom: 1px;
        """,
    )
    title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
    title_layout.addWidget(title_label)
    title_layout.addStretch()
    main_layout.addLayout(title_layout)
    main_layout.addSpacing(8)

    grid = QGridLayout()
    grid.setSpacing(2)
    grid.setContentsMargins(0, 0, 0, 0)

    headers = [
        "SYSTEM HEALTH",
        "BROKER API",
        "DATA FEEDS",
        "INTERNAL MODULES",
    ]
    for col, header in enumerate(headers):
        header_label = QLabel(header)
        header_label.setStyleSheet(
            f"""
                color: {COLORS["cyan"]};
                font-size: 13px;
                font-weight: normal;
                padding: 2px;
                border-bottom: 1px solid {COLORS["border"]};
            """,
        )
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(header_label, 0, col)

    components = [
        ("RISK MANAGER", "●"),
        ("MARKET DATA", "●"),
        ("STRATEGY ENGINE", "●"),
        ("ML MODELS", "●"),
        ("DATABASE", "●"),
    ]
    for row, (name, status) in enumerate(components, start=1):
        component_widget = QWidget()
        component_layout = QHBoxLayout()
        component_layout.setContentsMargins(5, 1, 5, 1)
        component_layout.setSpacing(3)

        indicator = QLabel(status)
        indicator.setStyleSheet(
            "color: " + COLORS["text_dim"] + "; font-size: 14px;",
        )
        component_layout.addWidget(indicator)

        label = QLabel(name)
        label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
        component_layout.addWidget(label)
        component_layout.addStretch()

        component_widget.setLayout(component_layout)
        dashboard.system_components[name] = indicator
        grid.addWidget(component_widget, row, 0)

    broker_services = [
        ("Orders", "tradier_orders"),
        ("Account", "tradier_account"),
        ("Market Data", "tradier_market"),
        ("Options Chain", "tradier_options"),
        ("Streaming", "tradier_streaming"),
    ]
    for row, (svc_name, svc_key) in enumerate(broker_services, start=1):
        svc_widget = QWidget()
        svc_layout = QHBoxLayout()
        svc_layout.setContentsMargins(5, 1, 5, 1)
        svc_layout.setSpacing(3)

        indicator = QLabel("●")
        indicator.setStyleSheet(
            "color: " + COLORS["neutral"] + "; font-size: 14px;",
        )
        indicator.setToolTip(f"Tradier {svc_name} endpoint")
        svc_layout.addWidget(indicator)

        label = QLabel(svc_name)
        label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
        svc_layout.addWidget(label)
        svc_layout.addStretch()

        svc_widget.setLayout(svc_layout)
        dashboard.client_indicators[svc_key] = indicator
        grid.addWidget(svc_widget, row, 1)

    data_services = [
        ("Live Stream", "db_live"),
        ("Historical", "db_historical"),
        ("Options", "db_options"),
        ("Book Data", "db_book"),
        ("Replay", "db_replay"),
    ]
    for row, (feed_name, feed_key) in enumerate(data_services, start=1):
        feed_widget = QWidget()
        feed_layout = QHBoxLayout()
        feed_layout.setContentsMargins(5, 1, 5, 1)
        feed_layout.setSpacing(3)

        indicator = QLabel("●")
        indicator.setStyleSheet(
            "color: " + COLORS["neutral"] + "; font-size: 14px;",
        )
        indicator.setToolTip(feed_name)
        feed_layout.addWidget(indicator)

        label = QLabel(feed_name)
        label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
        feed_layout.addWidget(label)
        feed_layout.addStretch()

        feed_widget.setLayout(feed_layout)
        dashboard.client_indicators[feed_key] = indicator
        grid.addWidget(feed_widget, row, 2)

    internal_modules = [
        ("Custom Metrics", "custom_metrics"),
        ("Risk Calculator", "risk_calc"),
        ("ML Engine", "ml_engine"),
        ("Options Analyzer", "options"),
        ("Performance", "performance"),
    ]
    for row, (module_name, module_key) in enumerate(internal_modules, start=1):
        module_widget = QWidget()
        module_layout = QHBoxLayout()
        module_layout.setContentsMargins(5, 1, 5, 1)
        module_layout.setSpacing(3)

        indicator = QLabel("●")
        if module_key == "custom_metrics":
            indicator.setStyleSheet(
                "color: " + COLORS["warning"] + "; font-size: 14px;",
            )
        else:
            indicator.setStyleSheet(
                "color: " + COLORS["text_dim"] + "; font-size: 14px;",
            )
        module_layout.addWidget(indicator)

        label = QLabel(module_name)
        label.setStyleSheet("color: " + COLORS["text"] + "; font-size: 14px;")
        module_layout.addWidget(label)
        module_layout.addStretch()

        module_widget.setLayout(module_layout)
        if not hasattr(dashboard, "internal_module_indicators"):
            dashboard.internal_module_indicators = {}
        dashboard.internal_module_indicators[module_key] = indicator
        grid.addWidget(module_widget, row, 3)

    for col in range(4):
        grid.setColumnStretch(col, 1)

    for row in range(1, 6):
        grid.setRowMinimumHeight(row, 24)

    main_layout.addLayout(grid)
    main_layout.addStretch()
    container.setLayout(main_layout)
    return container


def build_toolbar(dashboard: Any) -> QWidget:
    """Create top toolbar with FIXED WIDTH status containers and heartbeat monitor.

    Extracted from SpyderG05_TradingDashboard.create_toolbar.
    Sets attributes on *dashboard* (the TradingDashboard instance) for all
    widgets that need to be updated at runtime.

    Args:
        dashboard: The TradingDashboard (or compatible) instance that owns the toolbar.

    Returns:
        A QWidget ready to be inserted into the dashboard layout.
    """
    import os as _os
    import pytz
    from datetime import datetime

    toolbar = QWidget()
    toolbar.setFixedHeight(60)
    toolbar.setStyleSheet(
        f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};",
    )

    layout = QHBoxLayout()

    # SPYDER logo on left
    logo_label = QLabel("S P Y D E R")
    try:
        logo_font = QFont("Michroma", 16, QFont.Weight.Normal)
    except Exception:
        logo_font = QFont("Arial", 16, QFont.Weight.Normal)
    logo_label.setFont(logo_font)
    logo_label.setStyleSheet(f"color: {COLORS['text']}; letter-spacing: 5px;")
    layout.addWidget(logo_label)

    # mode_selector removed — mode is controlled from the account info container
    dashboard.mode_selector = None

    layout.addStretch(7)

    # Center section with market indices — order matches standard convention:
    # DOW → S&P 500 (SPX) → NASDAQ (COMP) → Russell 2000 (RUT)
    center_section = QHBoxLayout()
    center_section.setSpacing(5)

    # DJI (Dow Jones Industrial Average — DIA ETF × 100 proxy)
    dji_container = QHBoxLayout()
    dji_container.setSpacing(0)
    dji_label = QLabel("DJI:")
    dji_label.setStyleSheet(f"color: {COLORS['text']};")
    dji_label.setToolTip(
        "Dow Jones Industrial Average\n"
        "Source: DIA ETF × 100  (Tradier $DJI index is ~15 min delayed)"
    )
    dji_container.addWidget(dji_label)

    dashboard.dji_value = QLabel(" ---")
    dashboard.dji_value.setStyleSheet(f"color: {COLORS['text']};")
    dashboard.dji_value.setToolTip("Dow Jones Industrial Average (DIA ETF × 100)")
    dji_container.addWidget(dashboard.dji_value)

    dashboard.dji_change = QLabel("")
    dashboard.dji_change.setStyleSheet(f"color: {COLORS['positive']};")
    dji_container.addWidget(dashboard.dji_change)

    center_section.addLayout(dji_container)
    center_section.addSpacing(10)

    # SPX (S&P 500 — direct Tradier index)
    spx_container = QHBoxLayout()
    spx_container.setSpacing(0)
    spx_label = QLabel("SPX:")
    spx_label.setStyleSheet(f"color: {COLORS['text']};")
    spx_label.setToolTip("S&P 500 Index — direct from Tradier")
    spx_container.addWidget(spx_label)

    dashboard.spx_value = QLabel(" ---")
    dashboard.spx_value.setStyleSheet(f"color: {COLORS['text']};")
    dashboard.spx_value.setToolTip("S&P 500 Index (direct from Tradier)")
    spx_container.addWidget(dashboard.spx_value)

    dashboard.spx_change = QLabel("")
    dashboard.spx_change.setStyleSheet(f"color: {COLORS['positive']};")
    spx_container.addWidget(dashboard.spx_change)

    center_section.addLayout(spx_container)
    center_section.addSpacing(10)

    # COMP (NASDAQ Composite — QQQ ETF × 37.5 proxy; IXIC not on Tradier)
    comp_container = QHBoxLayout()
    comp_container.setSpacing(0)
    comp_label = QLabel("COMP:")
    comp_label.setStyleSheet(f"color: {COLORS['text']};")
    comp_label.setToolTip(
        "NASDAQ Composite Index (3,000+ stocks)\n"
        "Source: QQQ ETF × 37.5  (Tradier IXIC/COMP not available)"
    )
    comp_container.addWidget(comp_label)

    dashboard.comp_value = QLabel(" ---")
    dashboard.comp_value.setStyleSheet(f"color: {COLORS['text']};")
    dashboard.comp_value.setToolTip("NASDAQ Composite (QQQ ETF × 37.5 proxy)")
    comp_container.addWidget(dashboard.comp_value)

    dashboard.comp_change = QLabel("")
    dashboard.comp_change.setStyleSheet(f"color: {COLORS['positive']};")
    comp_container.addWidget(dashboard.comp_change)

    center_section.addLayout(comp_container)
    center_section.addSpacing(10)

    # RUT (Russell 2000 — direct Tradier index; change% borrowed from IWM when unavailable)
    rut_container = QHBoxLayout()
    rut_container.setSpacing(0)
    rut_label = QLabel("RUT:")
    rut_label.setStyleSheet(f"color: {COLORS['text']};")
    rut_label.setToolTip(
        "Russell 2000 Index — direct from Tradier\n"
        "Change % uses IWM ETF as fallback when Tradier omits it"
    )
    rut_container.addWidget(rut_label)

    dashboard.rut_value = QLabel(" ---")
    dashboard.rut_value.setStyleSheet(f"color: {COLORS['text']};")
    dashboard.rut_value.setToolTip("Russell 2000 Index (direct from Tradier)")
    rut_container.addWidget(dashboard.rut_value)

    dashboard.rut_change = QLabel("")
    dashboard.rut_change.setStyleSheet(f"color: {COLORS['positive']};")
    rut_container.addWidget(dashboard.rut_change)

    center_section.addLayout(rut_container)

    layout.addLayout(center_section)
    layout.addStretch(1)

    # API Connection Status (Left Box) - FIXED WIDTH
    dashboard.api_status_container = QWidget()
    dashboard.api_status_container.setMinimumWidth(155)
    dashboard.api_status_container.setMaximumWidth(155)
    dashboard.api_status_container.setToolTip("Tradier execution API")
    dashboard.api_status_container.setStyleSheet(
        """
        QWidget:hover {
            background-color: #2a2a2a;
            border-radius: 3px;
            padding: 2px;
        }
    """,
    )
    api_status_layout = QHBoxLayout()
    api_status_layout.setContentsMargins(6, 3, 4, 3)
    api_status_layout.setSpacing(4)

    dashboard.api_connection_label = QLabel("TRADIER EXEC")
    dashboard.api_connection_label.setStyleSheet(
        "color: " + COLORS["negative"] + "; font-size: 14px;",
    )
    api_status_layout.addWidget(dashboard.api_connection_label)

    dashboard.api_connect_icon = QLabel("\u26a1")
    dashboard.api_connect_icon.setStyleSheet(
        "color: " + COLORS["negative"] + "; font-size: 13px;",
    )
    dashboard.api_connect_icon.setCursor(Qt.CursorShape.PointingHandCursor)
    dashboard.api_connect_icon.setToolTip("Click to connect to Tradier API")
    dashboard.api_connect_icon.mousePressEvent = dashboard.toggle_api_connection
    api_status_layout.addWidget(dashboard.api_connect_icon)

    dashboard.api_status_container.setLayout(api_status_layout)

    # Data Status — clickable only in EOD/SIMULATED states
    dashboard.data_status_container = QWidget()
    dashboard.data_status_container.setMinimumWidth(120)
    dashboard.data_status_container.setMaximumWidth(120)
    dashboard.data_status_container.setToolTip("Data is simulated — no live feed connected")
    data_status_layout = QHBoxLayout()
    data_status_layout.setContentsMargins(8, 3, 8, 3)
    data_status_layout.setSpacing(6)

    dashboard.data_status_label = QLabel("SIMULATED")
    dashboard.data_status_label.setStyleSheet(
        "color: " + COLORS["automation_active"] + "; font-size: 14px;",
    )
    dashboard.data_status_label.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
    )
    data_status_layout.addWidget(dashboard.data_status_label)

    dashboard.data_status_container.setLayout(data_status_layout)
    dashboard.data_status_container.mousePressEvent = dashboard._toggle_data_display

    # Compact always-visible Event Clock badge; full details are in the hidden-controls panel.
    dashboard.event_clock_compact_label = QLabel("EC: CLEAR")
    dashboard.event_clock_compact_label.setStyleSheet(
        f"color: {COLORS['positive']}; font-size: 13px; font-weight: normal;"
    )
    dashboard.event_clock_compact_label.setToolTip("Event Clock status")

    # Market Data Provider (label click = switch provider, ⚡ click = connect/disconnect)
    dashboard.mkt_provider_container = QWidget()
    dashboard.mkt_provider_container.setMinimumWidth(165)
    dashboard.mkt_provider_container.setMaximumWidth(165)
    dashboard.mkt_provider_container.setToolTip("Market data source")
    dashboard.mkt_provider_container.setStyleSheet(
        """
        QWidget:hover {
            background-color: #2a2a2a;
            border-radius: 3px;
            padding: 2px;
        }
    """,
    )
    mkt_layout = QHBoxLayout()
    mkt_layout.setContentsMargins(8, 3, 8, 3)
    mkt_layout.setSpacing(4)

    _current_provider = _os.getenv("MARKET_DATA_PROVIDER", "tradier").lower()
    if _current_provider not in ("tradier", "massive"):
        _current_provider = "tradier"
    # Start red (disconnected); turns green once data feed connects
    _provider_color = COLORS["negative"]

    dashboard.mkt_provider_label = QLabel(_current_provider.upper() + " DATA")
    dashboard.mkt_provider_label.setStyleSheet(f"color: {_provider_color}; font-size: 14px;")
    dashboard.mkt_provider_label.setCursor(Qt.CursorShape.PointingHandCursor)
    dashboard.mkt_provider_label.setToolTip(
        "Click to switch between Tradier and Massive data source",
    )
    dashboard.mkt_provider_label.mousePressEvent = dashboard.toggle_market_data_provider
    mkt_layout.addWidget(dashboard.mkt_provider_label)

    dashboard.mkt_connect_icon = QLabel("\u26a1")
    dashboard.mkt_connect_icon.setStyleSheet(
        f"color: {_provider_color}; font-size: 13px;",
    )
    dashboard.mkt_connect_icon.setCursor(Qt.CursorShape.PointingHandCursor)
    dashboard.mkt_connect_icon.setToolTip("Click to connect market data feed")
    dashboard.mkt_connect_icon.mousePressEvent = dashboard._toggle_mkt_data_connection
    mkt_layout.addWidget(dashboard.mkt_connect_icon)

    dashboard.mkt_provider_container.setLayout(mkt_layout)

    # RIGHT SECTION - Status labels aligned with right panel buttons below
    right_section = QHBoxLayout()
    right_section.setSpacing(0)
    right_section.setContentsMargins(0, 0, 0, 0)

    right_section.addWidget(dashboard.api_status_container)
    right_section.addWidget(dashboard.mkt_provider_container)
    right_section.addWidget(dashboard.data_status_container)
    right_section.addWidget(dashboard.event_clock_compact_label)

    layout.addLayout(right_section)

    # DATE/TIME - separate from status labels
    pipe_label = QLabel(" | ")
    pipe_label.setStyleSheet(f"color: {COLORS['text']};")
    layout.addWidget(pipe_label)
    _et_tz = pytz.timezone("US/Eastern")
    dashboard.datetime_label = QLabel(datetime.now(_et_tz).strftime("%Y-%m-%d   %H:%M:%S  ET"))
    dashboard.datetime_label.setStyleSheet("font-size: 14px;")
    layout.addWidget(dashboard.datetime_label)

    toolbar.setLayout(layout)
    return toolbar