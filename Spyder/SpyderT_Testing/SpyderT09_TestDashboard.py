#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.1
Module: SpyderT09_TestDashboard
Group: T [Test Modules]
Purpose: Comprehensive Test Dashboard with Expanded 2x5 Signal Monitor
Author: Mohamed Talib
Date Created: 2025-01-20
Last Updated: 2025-07-21 Time: 16:30:00

Description:
    Enhanced test dashboard with expanded Signal Monitor featuring 2x5 grid layout
    including custom metrics (GEX, DEX, OGL, DIX, SWAN) with comprehensive popup
    dialogs. Features priority-ordered signal monitoring, real-time market data
    simulation, and professional PyQt6 interface.

Changes in this version:
    - Expanded Signal Monitor from 1x5 to 2x5 grid (10 signals total)
    - Added 5 new custom metric dialogs (GEX, DEX, OGL, DIX, SWAN)
    - Adjusted layout proportions for expanded signal panel
    - Implemented priority-based button ordering
    - SWAN indicator weighted 85% green (rare events)
"""

import os
import random
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# Matplotlib for charting
import matplotlib
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import pandas as pd
# Plotly integration - no direct canvas equivalent needed
from PySide6.QtCore import (QPoint, QRect, QSize, Qt, QThread, QTimer,
                        Signal, Slot)
from PySide6.QtGui import (QBrush, QColor, QFont, QIcon, QKeySequence, QPainter,
                         QPalette, QPen, QPixmap, QShortcut, QTextCursor)
# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QGridLayout,
                            QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                            QLineEdit, QMainWindow, QMessageBox, QProgressBar,
                             QPushButton, QScrollArea, QSplitter, QTableWidget,
                             QTableWidgetItem, QTabWidget, QTextEdit, QToolTip,
                             QVBoxLayout, QWidget)

# Plotly does not require backend configuration

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Risk Parameters Dialog Import (Optional)
try:
    from SpyderG06_RiskParametersDialog import show_risk_parameters_dialog

    RISK_DIALOG_AVAILABLE = True
    print("✅ Risk Parameters Dialog loaded successfully")
except ImportError as e:
    RISK_DIALOG_AVAILABLE = False
    print(f"⚠️  Risk Parameters Dialog not available: {e}")
    print("   The RISK PARAMETERS button will show a placeholder")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Window dimensions
WINDOW_WIDTH = 1920
WINDOW_HEIGHT = 1080

# Panel widths (adjusted for expanded signal monitor)
LEFT_PANEL_WIDTH = 340
CENTER_PANEL_WIDTH = 970
RIGHT_PANEL_WIDTH = 610

# Market symbols organized by category - UPDATED WITH OPTIMIZED LIST
MARKET_SYMBOLS = {
    "S&P CORE": ["SPY", "SPX", "/ES"],
    "VOLATILITY": ["VIX", "VIX9D", "VXV", "VXMT", "VVIX", "UVXY"],
    "MARKET INTERNALS": ["$TICK", "$TRIN", "$ADD", "CPC", "PCALL", "SKEW"],
    "MAJOR INDICES": ["DIA", "QQQ", "IWM"],
    "BONDS & CREDIT": ["TLT", "LQD"],
    "CORRELATIONS": ["DXY", "GLD"],
    "CUSTOM METRICS": ["GEX", "DEX", "OGL", "DIX", "SWAN"],
}

# Symbol descriptions for tooltips
SYMBOL_DESCRIPTIONS = {
    # S&P Core
    "SPY": "SPDR S&P 500 ETF - Most liquid S&P 500 ETF",
    "SPX": "S&P 500 Index - Cash index value",
    "/ES": "E-mini S&P 500 Futures - 24/5 trading",
    # Volatility
    "VIX": "CBOE Volatility Index - 30-day implied volatility",
    "VIX9D": "CBOE 9-Day Volatility Index - Short-term volatility",
    "VXV": "CBOE 3-Month Volatility Index - 93-day implied volatility",
    "VXMT": "CBOE Mid-Term Volatility Index - 6-month volatility",
    "VVIX": "VIX of VIX - Volatility of volatility index",
    "UVXY": "ProShares Ultra VIX Short-Term Futures ETF",
    # Market Internals
    "$TICK": "NYSE Tick Index - Upticks minus downticks",
    "$TRIN": "Arms Index - Advance/Decline volume ratio",
    "$ADD": "Advance-Decline Line - Net advancing issues",
    "CPC": "CBOE Put/Call Ratio - Equity options only",
    "PCALL": "Total Put/Call Ratio - All options",
    "SKEW": "CBOE Skew Index - Tail risk measure",
    # Major Indices
    "DIA": "SPDR Dow Jones Industrial Average ETF",
    "QQQ": "Invesco QQQ Trust - NASDAQ 100 ETF",
    "IWM": "iShares Russell 2000 ETF - Small caps",
    # Bonds & Credit
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "LQD": "iShares Investment Grade Corporate Bond ETF",
    # Correlations
    "DXY": "US Dollar Index - Dollar strength",
    "GLD": "SPDR Gold Trust ETF - Gold proxy",
    # Custom Metrics
    "GEX": "Gamma Exposure - Market maker hedging pressure",
    "DEX": "Delta Exposure - Directional hedging flow",
    "OGL": "Zero Gamma Level - Key support/resistance",
    "DIX": "Dark Index - Dark pool buying percentage",
    "SWAN": "Black Swan Risk Indicator - Tail risk monitor",
}

# Update intervals
FAST_UPDATE_MS = 1000  # SPY, SPX, /ES, VIX, $TICK, SWAN (when critical)
MEDIUM_UPDATE_MS = 5000  # Other volatility, internals, indices
SLOW_UPDATE_MS = 15000  # Bonds, correlations (DXY, GLD), custom metrics

# Symbol update categories
FAST_UPDATE_SYMBOLS = ["SPY", "SPX", "/ES", "VIX", "$TICK"]
MEDIUM_UPDATE_SYMBOLS = [
    "VIX9D",
    "VXV",
    "VXMT",
    "VVIX",
    "UVXY",
    "$TRIN",
    "$ADD",
    "CPC",
    "PCALL",
    "SKEW",
    "DIA",
    "QQQ",
    "IWM",
]
SLOW_UPDATE_SYMBOLS = ["TLT", "LQD", "DXY", "GLD", "GEX", "DEX", "OGL", "DIX", "SWAN"]

# Color scheme
COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#ff1744",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "automation_active": "#00b8d4",
    "grid": "#2a2a2a",
    "orange": "#ff9800",
    "red": "#ff0000",
    "cyan": "#00ffff",
    "yellow": "#ffff00",
}

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class MarketData:
    """Market data for symbols"""

    symbol: str
    last: float
    change: float
    change_pct: float
    timestamp: datetime


@dataclass
class PositionData:
    """Position information"""

    date: str
    symbol: str
    contracts: int
    strikes: str
    expiry: str
    strategy: str
    status: str
    cost: float
    pnl: float
    auto_status: str


@dataclass
class GreekRisk:
    """Portfolio Greeks"""

    delta: float
    gamma: float
    theta: float
    vega: float


# ==============================================================================
# SIGNAL MONITOR PANEL COMPONENTS
# ==============================================================================


class TrafficLightButton(QPushButton):
    """Custom button that looks like a traffic light with label"""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.status = "green"  # green, yellow, red
        self.setFixedHeight(24)  # Keep height fixed
        self.setMinimumWidth(120)  # Minimum width for readability
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
                text-align: left;
                padding-left: 25px;
                color: #ffffff;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2a2a2a;
                border-radius: 3px;
            }
        """
        )
        self.setText(label)

    def set_status(self, status: str):
        """Set traffic light status: green, yellow, red"""
        self.status = status
        self.update()

    def paintEvent(self, event):
        """Custom paint for traffic light indicator"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw the traffic light circle
        circle_rect = self.rect().adjusted(5, 5, -self.width() + 19, -5)

        # Choose color based on status
        if self.status == "green":
            color = QColor(COLORS["positive"])
        elif self.status == "yellow":
            color = QColor(COLORS["warning"])
        else:
            color = QColor(COLORS["negative"])

        # Draw filled circle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(150), 1))
        painter.drawEllipse(circle_rect)

        # Add a subtle glow effect
        glow_color = QColor(color)
        glow_color.setAlpha(100)
        painter.setBrush(QBrush(glow_color))
        painter.setPen(Qt.PenStyle.NoPen)
        glow_rect = circle_rect.adjusted(-2, -2, 2, 2)
        painter.drawEllipse(glow_rect)


class MonitorDialog(QDialog):
    """Base dialog for monitor popups"""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)  # Non-modal so multiple can be open
        self.setMinimumSize(400, 300)
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {COLORS['background']};
                border: 2px solid {COLORS['border']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                font-family: monospace;
                font-size: 12px;
            }}
        """
        )

        # Main layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: normal; color: {COLORS['cyan']};")
        title_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        self.layout.addWidget(separator)


# ==============================================================================
# EXISTING DIALOG CLASSES (VIX, RSI, DIV, AI, RISK)
# ==============================================================================
class VIXMonitorDialog(MonitorDialog):
    """VIX Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("VIX MONITOR", parent)
        self.setMinimumSize(350, 250)

        # Content widget
        content = QWidget()
        content_layout = QGridLayout()
        content_layout.setSpacing(10)

        # VIX Value
        vix_label = QLabel("VIX:")
        vix_label.setStyleSheet("font-weight: normal;")
        self.vix_value = QLabel("15.32 ↑")
        self.vix_value.setStyleSheet(f"font-size: 18px; color: {COLORS['positive']};")

        # VIX3M Value
        vix3m_label = QLabel("VIX3M:")
        vix3m_label.setStyleSheet("font-weight: normal;")
        self.vix3m_value = QLabel("16.85")
        self.vix3m_value.setStyleSheet("font-size: 14px;")

        # Term Structure
        term_label = QLabel("Term Structure:")
        term_label.setStyleSheet("font-weight: normal;")
        self.term_value = QLabel("-9.1% CONTANGO")
        self.term_value.setStyleSheet(f"font-size: 14px; color: {COLORS['negative']};")

        # Regime
        regime_label = QLabel("Volatility Regime:")
        regime_label.setStyleSheet("font-weight: normal;")
        self.regime_value = QLabel("SELL PREMIUM")
        self.regime_value.setStyleSheet(
            f"font-size: 16px; color: {COLORS['negative']}; font-weight: normal;"
        )

        # Add to grid
        content_layout.addWidget(vix_label, 0, 0)
        content_layout.addWidget(self.vix_value, 0, 1)
        content_layout.addWidget(vix3m_label, 1, 0)
        content_layout.addWidget(self.vix3m_value, 1, 1)
        content_layout.addWidget(term_label, 2, 0)
        content_layout.addWidget(self.term_value, 2, 1)
        content_layout.addWidget(regime_label, 3, 0)
        content_layout.addWidget(self.regime_value, 3, 1)

        content.setLayout(content_layout)
        self.layout.addWidget(content)

        # Historical chart placeholder
        chart_label = QLabel("Historical Term Structure")
        chart_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(chart_label)

        self.chart_area = QTextEdit()
        self.chart_area.setReadOnly(True)
        self.chart_area.setMaximumHeight(100)
        self.chart_area.setPlainText(
            "Chart would display VIX term structure over time\n"
            + "Green zones = Backwardation (Buy Premium)\n"
            + "Red zones = Contango (Sell Premium)"
        )
        self.layout.addWidget(self.chart_area)


class RSIConfluenceDialog(MonitorDialog):
    """RSI Confluence Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("RSI CONFLUENCE MONITOR", parent)

        # RSI values grid
        rsi_widget = QWidget()
        rsi_layout = QGridLayout()
        rsi_layout.setSpacing(10)

        # Headers
        rsi_layout.addWidget(QLabel("Timeframe"), 0, 0)
        rsi_layout.addWidget(QLabel("Value"), 0, 1)
        rsi_layout.addWidget(QLabel("Status"), 0, 2)

        # 15-min RSI
        rsi_layout.addWidget(QLabel("15-min:"), 1, 0)
        self.rsi_15 = QLabel("72.5 ↑")
        self.rsi_15.setStyleSheet(f"color: {COLORS['negative']};")
        rsi_layout.addWidget(self.rsi_15, 1, 1)
        rsi_layout.addWidget(QLabel("OVERBOUGHT"), 1, 2)

        # 30-min RSI
        rsi_layout.addWidget(QLabel("30-min:"), 2, 0)
        self.rsi_30 = QLabel("68.2 →")
        self.rsi_30.setStyleSheet(f"color: {COLORS['warning']};")
        rsi_layout.addWidget(self.rsi_30, 2, 1)
        rsi_layout.addWidget(QLabel("NEUTRAL"), 2, 2)

        # 60-min RSI
        rsi_layout.addWidget(QLabel("60-min:"), 3, 0)
        self.rsi_60 = QLabel("45.3 ↓")
        self.rsi_60.setStyleSheet(f"color: {COLORS['positive']};")
        rsi_layout.addWidget(self.rsi_60, 3, 1)
        rsi_layout.addWidget(QLabel("OVERSOLD"), 3, 2)

        rsi_widget.setLayout(rsi_layout)
        self.layout.addWidget(rsi_widget)

        # Confluence Signal
        signal_frame = QFrame()
        signal_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 10px;"
        )
        signal_layout = QVBoxLayout()

        signal_label = QLabel("CONFLUENCE SIGNAL:")
        signal_label.setStyleSheet("font-weight: normal;")
        signal_layout.addWidget(signal_label)

        self.signal_text = QLabel("MIXED - NO CONFLUENCE")
        self.signal_text.setStyleSheet(
            f"color: {COLORS['warning']}; font-size: 14px; font-weight: normal;"
        )
        signal_layout.addWidget(self.signal_text)

        signal_frame.setLayout(signal_layout)
        self.layout.addWidget(signal_frame)


class DivergenceDialog(MonitorDialog):
    """Divergence Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("DIVERGENCE MONITOR", parent)

        # Divergence checks
        div_widget = QWidget()
        div_layout = QVBoxLayout()
        div_layout.setSpacing(15)

        # $TICK vs SPY
        tick_frame = QFrame()
        tick_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 8px;"
        )
        tick_layout = QHBoxLayout()
        tick_layout.addWidget(QLabel("$TICK vs SPY:"))
        self.tick_status = QLabel("BEARISH DIVERGENCE ⚠️")
        self.tick_status.setStyleSheet(f"color: {COLORS['negative']}; font-weight: normal;")
        tick_layout.addWidget(self.tick_status)
        tick_frame.setLayout(tick_layout)

        # MACD vs Price
        macd_frame = QFrame()
        macd_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 8px;"
        )
        macd_layout = QHBoxLayout()
        macd_layout.addWidget(QLabel("MACD vs Price:"))
        self.macd_status = QLabel("ALIGNED ✓")
        self.macd_status.setStyleSheet(f"color: {COLORS['positive']}; font-weight: normal;")
        macd_layout.addWidget(self.macd_status)
        macd_frame.setLayout(macd_layout)

        # Volume vs Price
        vol_frame = QFrame()
        vol_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 8px;"
        )
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Volume vs Price:"))
        self.vol_status = QLabel("BULLISH DIVERGENCE 🔵")
        self.vol_status.setStyleSheet(f"color: {COLORS['positive']}; font-weight: normal;")
        vol_layout.addWidget(self.vol_status)
        vol_frame.setLayout(vol_layout)

        div_layout.addWidget(tick_frame)
        div_layout.addWidget(macd_frame)
        div_layout.addWidget(vol_frame)

        div_widget.setLayout(div_layout)
        self.layout.addWidget(div_widget)

        # Recommendation
        rec_label = QLabel("RECOMMENDATION:")
        rec_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(rec_label)

        self.recommendation = QTextEdit()
        self.recommendation.setReadOnly(True)
        self.recommendation.setMaximumHeight(60)
        self.recommendation.setPlainText(
            "Mixed divergence signals suggest caution.\nWait for confluence before taking positions."
        )
        self.layout.addWidget(self.recommendation)


class AIDecisionDialog(MonitorDialog):
    """AI Decision Matrix popup dialog"""

    def __init__(self, parent=None):
        super().__init__("AI DECISION MATRIX", parent)
        self.setMinimumSize(500, 450)

        # Primary Signals (60%)
        primary_group = QGroupBox("PRIMARY SIGNALS (60% Weight)")
        primary_group.setStyleSheet(
            f"""
            QGroupBox {{
                font-weight: normal;
                color: {COLORS['cyan']};
                padding-top: 15px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                padding: 0 5px;
            }}
        """
        )
        primary_layout = QVBoxLayout()
        primary_layout.setSpacing(8)
        primary_layout.setContentsMargins(10, 10, 10, 10)

        self.primary_rsi = QLabel("• RSI Confluence: BEARISH 🔴")
        self.primary_rsi.setStyleSheet("padding: 2px; font-size: 12px;")
        self.primary_vix = QLabel("• VIX Structure: CONTANGO ✓")
        self.primary_vix.setStyleSheet("padding: 2px; font-size: 12px;")
        self.primary_tick = QLabel("• $TICK Divergence: WARNING ⚠️")
        self.primary_tick.setStyleSheet("padding: 2px; font-size: 12px;")

        primary_layout.addWidget(self.primary_rsi)
        primary_layout.addWidget(self.primary_vix)
        primary_layout.addWidget(self.primary_tick)
        primary_group.setLayout(primary_layout)

        # Secondary Signals (30%)
        secondary_group = QGroupBox("SECONDARY SIGNALS (30% Weight)")
        secondary_group.setStyleSheet(
            f"""
            QGroupBox {{
                font-weight: normal;
                color: {COLORS['cyan']};
                padding-top: 15px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                padding: 0 5px;
            }}
        """
        )
        secondary_layout = QVBoxLayout()
        secondary_layout.setSpacing(8)
        secondary_layout.setContentsMargins(10, 10, 10, 10)

        self.secondary_macd = QLabel("• MACD Cross: NEUTRAL")
        self.secondary_macd.setStyleSheet("padding: 2px; font-size: 12px;")
        self.secondary_skew = QLabel("• SKEW: ELEVATED RISK")
        self.secondary_skew.setStyleSheet("padding: 2px; font-size: 12px;")
        self.secondary_pivot = QLabel("• Pivot Points: ABOVE R1")
        self.secondary_pivot.setStyleSheet("padding: 2px; font-size: 12px;")

        secondary_layout.addWidget(self.secondary_macd)
        secondary_layout.addWidget(self.secondary_skew)
        secondary_layout.addWidget(self.secondary_pivot)
        secondary_group.setLayout(secondary_layout)

        # Tertiary Signals (10%)
        tertiary_group = QGroupBox("TERTIARY SIGNALS (10% Weight)")
        tertiary_group.setStyleSheet(
            f"""
            QGroupBox {{
                font-weight: normal;
                color: {COLORS['cyan']};
                padding-top: 15px;
                margin-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                padding: 0 5px;
            }}
        """
        )
        tertiary_layout = QVBoxLayout()
        tertiary_layout.setSpacing(8)
        tertiary_layout.setContentsMargins(10, 10, 10, 10)

        self.tertiary_pcr = QLabel("• Put/Call Ratio: NEUTRAL")
        self.tertiary_pcr.setStyleSheet("padding: 2px; font-size: 12px;")
        self.tertiary_vwap = QLabel("• VWAP Deviation: +1.2%")
        self.tertiary_vwap.setStyleSheet("padding: 2px; font-size: 12px;")

        tertiary_layout.addWidget(self.tertiary_pcr)
        tertiary_layout.addWidget(self.tertiary_vwap)
        tertiary_group.setLayout(tertiary_layout)

        self.layout.addWidget(primary_group)
        self.layout.addWidget(secondary_group)
        self.layout.addWidget(tertiary_group)

        # Add some spacing before decision
        self.layout.addSpacing(10)

        # Overall Decision
        decision_frame = QFrame()
        decision_frame.setStyleSheet(
            f"""
            background-color: {COLORS['negative']};
            padding: 15px;
            border-radius: 5px;
            margin: 5px;
        """
        )
        decision_layout = QVBoxLayout()
        decision_layout.setSpacing(5)

        decision_label = QLabel("AI DECISION:")
        decision_label.setStyleSheet("font-weight: normal; color: white; font-size: 13px;")
        decision_layout.addWidget(decision_label)

        self.decision_text = QLabel("SELL PREMIUM (78% Confidence)")
        self.decision_text.setStyleSheet("color: white; font-size: 16px; font-weight: normal;")
        decision_layout.addWidget(self.decision_text)

        decision_frame.setLayout(decision_layout)
        self.layout.addWidget(decision_frame)


class RiskTriggersDialog(MonitorDialog):
    """Risk Triggers popup dialog"""

    def __init__(self, parent=None):
        super().__init__("RISK TRIGGERS", parent)

        # Risk indicators
        risk_widget = QWidget()
        risk_layout = QVBoxLayout()
        risk_layout.setSpacing(10)

        # SKEW Alert
        skew_frame = QFrame()
        skew_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['warning']}; padding: 8px;"
        )
        skew_layout = QVBoxLayout()
        self.skew_label = QLabel("SKEW > 140: ⚠️ ACTIVE")
        self.skew_label.setStyleSheet(f"color: {COLORS['warning']}; font-weight: normal;")
        self.skew_action = QLabel("ACTION: Reduce position size by 25%")
        skew_layout.addWidget(self.skew_label)
        skew_layout.addWidget(self.skew_action)
        skew_frame.setLayout(skew_layout)

        # $TRIN Status
        trin_frame = QFrame()
        trin_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['positive']}; padding: 8px;"
        )
        trin_layout = QVBoxLayout()
        self.trin_label = QLabel("$TRIN < 2.0: ✓ NORMAL")
        self.trin_label.setStyleSheet(f"color: {COLORS['positive']}; font-weight: normal;")
        self.trin_action = QLabel("ACTION: No adjustment needed")
        trin_layout.addWidget(self.trin_label)
        trin_layout.addWidget(self.trin_action)
        trin_frame.setLayout(trin_layout)

        # Bollinger Band Squeeze
        bb_frame = QFrame()
        bb_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['cyan']}; padding: 8px;"
        )
        bb_layout = QVBoxLayout()
        self.bb_label = QLabel("BB Squeeze: 🔵 DETECTED")
        self.bb_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")
        self.bb_action = QLabel("ACTION: Prepare for volatility expansion")
        bb_layout.addWidget(self.bb_label)
        bb_layout.addWidget(self.bb_action)
        bb_frame.setLayout(bb_layout)

        # VWAP Deviation
        vwap_frame = QFrame()
        vwap_frame.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['neutral']}; padding: 8px;"
        )
        vwap_layout = QVBoxLayout()
        self.vwap_label = QLabel("VWAP Deviation: +2.1%")
        self.vwap_label.setStyleSheet(f"color: {COLORS['neutral']}; font-weight: normal;")
        self.vwap_action = QLabel("ACTION: Consider short opportunity")
        vwap_layout.addWidget(self.vwap_label)
        vwap_layout.addWidget(self.vwap_action)
        vwap_frame.setLayout(vwap_layout)

        risk_layout.addWidget(skew_frame)
        risk_layout.addWidget(trin_frame)
        risk_layout.addWidget(bb_frame)
        risk_layout.addWidget(vwap_frame)

        risk_widget.setLayout(risk_layout)
        self.layout.addWidget(risk_widget)

        # Overall Risk Level
        overall_frame = QFrame()
        overall_frame.setStyleSheet(
            f"background-color: {COLORS['warning']}; padding: 10px; border-radius: 5px; margin-top: 10px;"
        )
        overall_layout = QHBoxLayout()
        overall_label = QLabel("OVERALL RISK LEVEL:")
        overall_label.setStyleSheet("font-weight: normal; color: black;")
        overall_value = QLabel("ELEVATED")
        overall_value.setStyleSheet("font-size: 16px; font-weight: normal; color: black;")
        overall_layout.addWidget(overall_label)
        overall_layout.addWidget(overall_value)
        overall_frame.setLayout(overall_layout)
        self.layout.addWidget(overall_frame)


# ==============================================================================
# NEW CUSTOM METRIC DIALOG CLASSES
# ==============================================================================
class GEXMonitorDialog(MonitorDialog):
    """GEX Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("GEX MONITOR", parent)
        self.setMinimumSize(400, 350)

        # GEX Values
        gex_widget = QWidget()
        gex_layout = QGridLayout()
        gex_layout.setSpacing(10)

        # Current GEX
        gex_label = QLabel("Current GEX:")
        gex_label.setStyleSheet("font-weight: normal;")
        self.gex_value = QLabel("-2.5B")
        self.gex_value.setStyleSheet(f"font-size: 18px; color: {COLORS['negative']};")

        # Change
        change_label = QLabel("Change:")
        change_label.setStyleSheet("font-weight: normal;")
        self.change_value = QLabel("-850M")
        self.change_value.setStyleSheet(f"font-size: 14px; color: {COLORS['negative']};")

        # Volatility Impact
        impact_label = QLabel("Volatility Impact:")
        impact_label.setStyleSheet("font-weight: normal;")
        self.impact_value = QLabel("HIGH VOLATILITY")
        self.impact_value.setStyleSheet(f"font-size: 14px; color: {COLORS['warning']};")

        # Key Level
        level_label = QLabel("Key GEX Level:")
        level_label.setStyleSheet("font-weight: normal;")
        self.level_value = QLabel("0 Gamma at SPY 585.50")
        self.level_value.setStyleSheet(f"font-size: 14px; color: {COLORS['cyan']};")

        # Add to grid
        gex_layout.addWidget(gex_label, 0, 0)
        gex_layout.addWidget(self.gex_value, 0, 1)
        gex_layout.addWidget(change_label, 1, 0)
        gex_layout.addWidget(self.change_value, 1, 1)
        gex_layout.addWidget(impact_label, 2, 0)
        gex_layout.addWidget(self.impact_value, 2, 1)
        gex_layout.addWidget(level_label, 3, 0)
        gex_layout.addWidget(self.level_value, 3, 1)

        gex_widget.setLayout(gex_layout)
        self.layout.addWidget(gex_widget)

        # Trading Implications
        implications_label = QLabel("TRADING IMPLICATIONS:")
        implications_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(implications_label)

        self.implications_text = QTextEdit()
        self.implications_text.setReadOnly(True)
        self.implications_text.setMaximumHeight(100)
        self.implications_text.setPlainText(
            "NEGATIVE GEX indicates market makers will be net sellers as SPY rises\n"
            + "and net buyers as SPY falls - creating volatility amplification.\n\n"
            + "STRATEGY: Expect increased volatility, consider volatility plays.\n"
            + "RISK: Large moves may accelerate due to dealer hedging flows."
        )
        self.layout.addWidget(self.implications_text)


class DEXMonitorDialog(MonitorDialog):
    """DEX Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("DEX MONITOR", parent)
        self.setMinimumSize(400, 350)

        # DEX Values
        dex_widget = QWidget()
        dex_layout = QGridLayout()
        dex_layout.setSpacing(10)

        # Current DEX
        dex_label = QLabel("Current DEX:")
        dex_label.setStyleSheet("font-weight: normal;")
        self.dex_value = QLabel("850M")
        self.dex_value.setStyleSheet(f"font-size: 18px; color: {COLORS['positive']};")

        # Market Bias
        bias_label = QLabel("Market Bias:")
        bias_label.setStyleSheet("font-weight: normal;")
        self.bias_value = QLabel("BULLISH")
        self.bias_value.setStyleSheet(f"font-size: 16px; color: {COLORS['positive']};")

        # MM Hedging Pressure
        pressure_label = QLabel("MM Hedging:")
        pressure_label.setStyleSheet("font-weight: normal;")
        self.pressure_value = QLabel("NET BUYING")
        self.pressure_value.setStyleSheet(f"font-size: 14px; color: {COLORS['positive']};")

        # Directional Flow
        flow_label = QLabel("Directional Flow:")
        flow_label.setStyleSheet("font-weight: normal;")
        self.flow_value = QLabel("POSITIVE GAMMA")
        self.flow_value.setStyleSheet(f"font-size: 14px; color: {COLORS['positive']};")

        # Add to grid
        dex_layout.addWidget(dex_label, 0, 0)
        dex_layout.addWidget(self.dex_value, 0, 1)
        dex_layout.addWidget(bias_label, 1, 0)
        dex_layout.addWidget(self.bias_value, 1, 1)
        dex_layout.addWidget(pressure_label, 2, 0)
        dex_layout.addWidget(self.pressure_value, 2, 1)
        dex_layout.addWidget(flow_label, 3, 0)
        dex_layout.addWidget(self.flow_value, 3, 1)

        dex_widget.setLayout(dex_layout)
        self.layout.addWidget(dex_widget)

        # Strategy Recommendations
        strategy_label = QLabel("STRATEGY RECOMMENDATIONS:")
        strategy_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(strategy_label)

        self.strategy_text = QTextEdit()
        self.strategy_text.setReadOnly(True)
        self.strategy_text.setMaximumHeight(100)
        self.strategy_text.setPlainText(
            "POSITIVE DEX suggests market makers have positive delta exposure\n"
            + "requiring them to buy more shares as market rises.\n\n"
            + "STRATEGY: Favor bullish strategies, expect upside momentum.\n"
            + "ENTRY: Look for dips to enter long positions."
        )
        self.layout.addWidget(self.strategy_text)


class OGLMonitorDialog(MonitorDialog):
    """OGL (Zero Gamma Level) Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("OGL MONITOR", parent)
        self.setMinimumSize(400, 320)

        # OGL Values
        ogl_widget = QWidget()
        ogl_layout = QGridLayout()
        ogl_layout.setSpacing(10)

        # Zero Gamma Level
        ogl_label = QLabel("Zero Gamma Level:")
        ogl_label.setStyleSheet("font-weight: normal;")
        self.ogl_value = QLabel("$585.50")
        self.ogl_value.setStyleSheet(f"font-size: 18px; color: {COLORS['yellow']};")

        # SPY Distance
        distance_label = QLabel("SPY Distance:")
        distance_label.setStyleSheet("font-weight: normal;")
        self.distance_value = QLabel("-$0.25 (Below)")
        self.distance_value.setStyleSheet(f"font-size: 14px; color: {COLORS['negative']};")

        # Expected Behavior
        behavior_label = QLabel("Expected Behavior:")
        behavior_label.setStyleSheet("font-weight: normal;")
        self.behavior_value = QLabel("VOLATILITY DAMPENING")
        self.behavior_value.setStyleSheet(f"font-size: 14px; color: {COLORS['positive']};")

        # Support/Resistance
        sr_label = QLabel("S/R Strength:")
        sr_label.setStyleSheet("font-weight: normal;")
        self.sr_value = QLabel("MODERATE")
        self.sr_value.setStyleSheet(f"font-size: 14px; color: {COLORS['warning']};")

        # Add to grid
        ogl_layout.addWidget(ogl_label, 0, 0)
        ogl_layout.addWidget(self.ogl_value, 0, 1)
        ogl_layout.addWidget(distance_label, 1, 0)
        ogl_layout.addWidget(self.distance_value, 1, 1)
        ogl_layout.addWidget(behavior_label, 2, 0)
        ogl_layout.addWidget(self.behavior_value, 2, 1)
        ogl_layout.addWidget(sr_label, 3, 0)
        ogl_layout.addWidget(self.sr_value, 3, 1)

        ogl_widget.setLayout(ogl_layout)
        self.layout.addWidget(ogl_widget)

        # Trading Notes
        notes_label = QLabel("TRADING NOTES:")
        notes_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(notes_label)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMaximumHeight(80)
        self.notes_text.setPlainText(
            "Zero Gamma Level acts as magnet - market tends to gravitate toward it.\n"
            + "Above OGL = Positive gamma (dampened volatility)\n"
            + "Below OGL = Negative gamma (amplified volatility)\n\n"
            + "CURRENT: SPY below OGL suggests increased volatility potential."
        )
        self.layout.addWidget(self.notes_text)


class DIXMonitorDialog(MonitorDialog):
    """DIX Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("DIX MONITOR", parent)
        self.setMinimumSize(400, 350)

        # DIX Values
        dix_widget = QWidget()
        dix_layout = QGridLayout()
        dix_layout.setSpacing(10)

        # Current DIX
        dix_label = QLabel("Current DIX:")
        dix_label.setStyleSheet("font-weight: normal;")
        self.dix_value = QLabel("42.5%")
        self.dix_value.setStyleSheet(f"font-size: 18px; color: {COLORS['warning']};")

        # Dark Pool Sentiment
        sentiment_label = QLabel("Dark Pool Sentiment:")
        sentiment_label.setStyleSheet("font-weight: normal;")
        self.sentiment_value = QLabel("NEUTRAL")
        self.sentiment_value.setStyleSheet(f"font-size: 16px; color: {COLORS['warning']};")

        # Institutional Activity
        activity_label = QLabel("Institutional Activity:")
        activity_label.setStyleSheet("font-weight: normal;")
        self.activity_value = QLabel("MODERATE")
        self.activity_value.setStyleSheet(f"font-size: 14px; color: {COLORS['neutral']};")

        # Historical Context
        context_label = QLabel("vs 20-Day Average:")
        context_label.setStyleSheet("font-weight: normal;")
        self.context_value = QLabel("+1.2% (Slightly High)")
        self.context_value.setStyleSheet(f"font-size: 14px; color: {COLORS['positive']};")

        # Add to grid
        dix_layout.addWidget(dix_label, 0, 0)
        dix_layout.addWidget(self.dix_value, 0, 1)
        dix_layout.addWidget(sentiment_label, 1, 0)
        dix_layout.addWidget(self.sentiment_value, 1, 1)
        dix_layout.addWidget(activity_label, 2, 0)
        dix_layout.addWidget(self.activity_value, 2, 1)
        dix_layout.addWidget(context_label, 3, 0)
        dix_layout.addWidget(self.context_value, 3, 1)

        dix_widget.setLayout(dix_layout)
        self.layout.addWidget(dix_widget)

        # Market Outlook
        outlook_label = QLabel("MARKET OUTLOOK:")
        outlook_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(outlook_label)

        self.outlook_text = QTextEdit()
        self.outlook_text.setReadOnly(True)
        self.outlook_text.setMaximumHeight(100)
        self.outlook_text.setPlainText(
            "DIX measures dark pool buying as % of total volume.\n"
            + "> 45%: Institutional buying (Bullish)\n"
            + "< 40%: Institutional selling (Bearish)\n"
            + "40-45%: Neutral zone\n\n"
            + "CURRENT (42.5%): Slight institutional buying bias, but not strong."
        )
        self.layout.addWidget(self.outlook_text)


class SWANMonitorDialog(MonitorDialog):
    """SWAN Monitor popup dialog"""

    def __init__(self, parent=None):
        super().__init__("BLACK SWAN MONITOR", parent)
        self.setMinimumSize(400, 380)

        # SWAN Values
        swan_widget = QWidget()
        swan_layout = QGridLayout()
        swan_layout.setSpacing(10)

        # Current SWAN
        swan_label = QLabel("SWAN Index:")
        swan_label.setStyleSheet("font-weight: normal;")
        self.swan_value = QLabel("1.85")
        self.swan_value.setStyleSheet(f"font-size: 18px; color: {COLORS['positive']};")

        # Threshold Status
        threshold_label = QLabel("Threshold Status:")
        threshold_label.setStyleSheet("font-weight: normal;")
        self.threshold_value = QLabel("NORMAL 🟢")
        self.threshold_value.setStyleSheet(f"font-size: 16px; color: {COLORS['positive']};")

        # Risk Level
        risk_label = QLabel("Risk Level:")
        risk_label.setStyleSheet("font-weight: normal;")
        self.risk_value = QLabel("LOW")
        self.risk_value.setStyleSheet(f"font-size: 14px; color: {COLORS['positive']};")

        # Next Threshold
        next_label = QLabel("Next Threshold:")
        next_label.setStyleSheet("font-weight: normal;")
        self.next_value = QLabel("YELLOW at 1.9")
        self.next_value.setStyleSheet(f"font-size: 14px; color: {COLORS['warning']};")

        # Add to grid
        swan_layout.addWidget(swan_label, 0, 0)
        swan_layout.addWidget(self.swan_value, 0, 1)
        swan_layout.addWidget(threshold_label, 1, 0)
        swan_layout.addWidget(self.threshold_value, 1, 1)
        swan_layout.addWidget(risk_label, 2, 0)
        swan_layout.addWidget(self.risk_value, 2, 1)
        swan_layout.addWidget(next_label, 3, 0)
        swan_layout.addWidget(self.next_value, 3, 1)

        swan_widget.setLayout(swan_layout)
        self.layout.addWidget(swan_widget)

        # 🆕 ADD THIS SECTION HERE:

        # Black Swan Explanation
        explanation_label = QLabel("WHAT IS A BLACK SWAN EVENT:")
        explanation_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(explanation_label)

        self.explanation_text = QLabel()
        self.explanation_text.setWordWrap(True)  # Allow text wrapping
        self.explanation_text.setStyleSheet(
            f"""
            QLabel {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                padding: 10px;
                color: {COLORS['text']};
                font-size: 12px;
                line-height: 1.3;
            }}
        """
        )
        self.explanation_text.setText(
            "A <b>Black Swan event</b> in trading refers to an <b>extremely rare, unpredictable event "
            "with severe, widespread consequences</b> that seems explainable only <i>after</i> it occurs."
        )
        self.layout.addWidget(self.explanation_text)

        # Risk Factors
        factors_label = QLabel("RISK FACTORS MONITORED:")
        factors_label.setStyleSheet("font-weight: normal; margin-top: 10px;")
        self.layout.addWidget(factors_label)

        self.factors_text = QTextEdit()
        self.factors_text.setReadOnly(True)
        self.factors_text.setMaximumHeight(80)
        self.factors_text.setPlainText(
            "• VIX spike potential  • Credit spreads widening\n"
            + "• Currency volatility  • Commodity disruptions\n"
            + "• Geopolitical events  • Central bank surprises\n"
            + "• Liquidity conditions • Market structure stress"
        )
        self.layout.addWidget(self.factors_text)

        # System Recommendations
        recommendations_label = QLabel("SYSTEM RECOMMENDATIONS:")
        recommendations_label.setStyleSheet("font-weight: normal; margin-top: 5px;")
        self.layout.addWidget(recommendations_label)

        self.recommendations_text = QTextEdit()
        self.recommendations_text.setReadOnly(True)
        self.recommendations_text.setMaximumHeight(60)
        self.recommendations_text.setPlainText(
            "CURRENT STATUS: Continue normal trading operations.\n"
            + "HEDGING: Standard portfolio hedges sufficient.\n"
            + "MONITORING: No immediate action required."
        )
        self.layout.addWidget(self.recommendations_text)


# ==============================================================================
# EXPANDED SIGNAL MONITOR PANEL (2x5 GRID)
# ==============================================================================
class SignalMonitorPanel(QWidget):
    def __init__(self):
        super().__init__()
        # RESPONSIVE SIZE: Fixed height but flexible width
        self.setFixedHeight(140)
        self.setMinimumWidth(280)  # Minimum width to ensure buttons fit
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
            }}
        """
        )

        # Create 2x5 grid layout
        layout = QGridLayout()
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(3)

        # Create traffic light buttons in priority order
        # TOP PRIORITY (Row 0)
        self.vix_button = TrafficLightButton("VIX MONITOR")
        self.ai_button = TrafficLightButton("AI DECISION")

        # HIGH PRIORITY (Row 1)
        self.gex_button = TrafficLightButton("GEX")
        self.dix_button = TrafficLightButton("DIX")

        # HIGH PRIORITY (Row 2)
        self.rsi_button = TrafficLightButton("RSI CONFLUENCE")
        self.risk_button = TrafficLightButton("RISK TRIGGERS")

        # MEDIUM PRIORITY (Row 3)
        self.ogl_button = TrafficLightButton("OGL")
        self.div_button = TrafficLightButton("DIVERGENCE")

        # MEDIUM PRIORITY (Row 4)
        self.dex_button = TrafficLightButton("DEX")
        self.swan_button = TrafficLightButton("BLACK SWAN")

        # Add buttons to grid in priority order
        # [VIX MONITOR]    [AI DECISION]
        layout.addWidget(self.vix_button, 0, 0)
        layout.addWidget(self.ai_button, 0, 1)

        # [GEX]            [DIX]
        layout.addWidget(self.gex_button, 1, 0)
        layout.addWidget(self.dix_button, 1, 1)

        # [RSI CONFLUENCE] [RISK TRIGGERS]
        layout.addWidget(self.rsi_button, 2, 0)
        layout.addWidget(self.risk_button, 2, 1)

        # [OGL]            [DIVERGENCE]
        layout.addWidget(self.ogl_button, 3, 0)
        layout.addWidget(self.div_button, 3, 1)

        # [DEX]            [SWAN]
        layout.addWidget(self.dex_button, 4, 0)
        layout.addWidget(self.swan_button, 4, 1)

        # Connect buttons to show dialogs
        # Original 5 buttons
        self.vix_button.clicked.connect(self.show_vix_dialog)
        self.rsi_button.clicked.connect(self.show_rsi_dialog)
        self.div_button.clicked.connect(self.show_div_dialog)
        self.ai_button.clicked.connect(self.show_ai_dialog)
        self.risk_button.clicked.connect(self.show_risk_dialog)

        # New custom metric buttons
        self.gex_button.clicked.connect(self.show_gex_dialog)
        self.dex_button.clicked.connect(self.show_dex_dialog)
        self.ogl_button.clicked.connect(self.show_ogl_dialog)
        self.dix_button.clicked.connect(self.show_dix_dialog)
        self.swan_button.clicked.connect(self.show_swan_dialog)

        self.setLayout(layout)

        # Store current dialog reference
        self.current_dialog = None

        # Initialize button states
        self.update_button_states()

        # Timer for updating states
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_button_states)
        self.update_timer.start(5000)  # Update every 5 seconds

    def close_current_dialog(self):
        """Close the currently open dialog if any"""
        if self.current_dialog and self.current_dialog.isVisible():
            self.current_dialog.close()
            self.current_dialog = None

    def update_button_states(self):
        """Update traffic light colors based on current conditions"""
        # Original 5 signals - random for demo
        vix_status = random.choice(["green", "yellow", "red"])
        self.vix_button.set_status(vix_status)

        rsi_status = random.choice(["green", "yellow", "red"])
        self.rsi_button.set_status(rsi_status)

        div_status = random.choice(["green", "yellow", "red"])
        self.div_button.set_status(div_status)

        ai_status = random.choice(["green", "yellow", "red"])
        self.ai_button.set_status(ai_status)

        risk_status = random.choice(["green", "yellow", "red"])
        self.risk_button.set_status(risk_status)

        # Custom metric signals
        gex_status = random.choice(["green", "yellow", "red"])
        self.gex_button.set_status(gex_status)

        dex_status = random.choice(["green", "yellow", "red"])
        self.dex_button.set_status(dex_status)

        ogl_status = random.choice(["green", "yellow", "red"])
        self.ogl_button.set_status(ogl_status)

        dix_status = random.choice(["green", "yellow", "red"])
        self.dix_button.set_status(dix_status)

        # SWAN - weighted 85% green since black swan events are rare
        swan_random = random.random()
        if swan_random < 0.85:
            swan_status = "green"
        elif swan_random < 0.95:
            swan_status = "yellow"
        else:
            swan_status = "red"
        self.swan_button.set_status(swan_status)

    # Original dialog methods
    def show_vix_dialog(self):
        """Show VIX Monitor dialog"""
        self.close_current_dialog()
        self.current_dialog = VIXMonitorDialog(self)
        self.current_dialog.show()

    def show_rsi_dialog(self):
        """Show RSI Confluence dialog"""
        self.close_current_dialog()
        self.current_dialog = RSIConfluenceDialog(self)
        self.current_dialog.show()

    def show_div_dialog(self):
        """Show Divergence Monitor dialog"""
        self.close_current_dialog()
        self.current_dialog = DivergenceDialog(self)
        self.current_dialog.show()

    def show_ai_dialog(self):
        """Show AI Decision Matrix dialog"""
        self.close_current_dialog()
        self.current_dialog = AIDecisionDialog(self)
        self.current_dialog.show()

    def show_risk_dialog(self):
        """Show Risk Triggers dialog"""
        self.close_current_dialog()
        self.current_dialog = RiskTriggersDialog(self)
        self.current_dialog.show()

    # New custom metric dialog methods
    def show_gex_dialog(self):
        """Show GEX Monitor dialog"""
        self.close_current_dialog()
        self.current_dialog = GEXMonitorDialog(self)
        self.current_dialog.show()

    def show_dex_dialog(self):
        """Show DEX Monitor dialog"""
        self.close_current_dialog()
        self.current_dialog = DEXMonitorDialog(self)
        self.current_dialog.show()

    def show_ogl_dialog(self):
        """Show OGL Monitor dialog"""
        self.close_current_dialog()
        self.current_dialog = OGLMonitorDialog(self)
        self.current_dialog.show()

    def show_dix_dialog(self):
        """Show DIX Monitor dialog"""
        self.close_current_dialog()
        self.current_dialog = DIXMonitorDialog(self)
        self.current_dialog.show()

    def show_swan_dialog(self):
        """Show SWAN Monitor dialog"""
        self.close_current_dialog()
        self.current_dialog = SWANMonitorDialog(self)
        self.current_dialog.show()


# ==============================================================================
# EXISTING CUSTOM WIDGETS (MarketSymbolWidget, GreekBar) - UNCHANGED
# ==============================================================================
class MarketSymbolWidget(QWidget):
    """Widget for displaying a single market symbol with tooltip support"""

    def __init__(self, symbol: str, category: str):
        super().__init__()
        self.symbol = symbol
        self.category = category
        self.setup_ui()

        # Set tooltip if available
        if symbol in SYMBOL_DESCRIPTIONS:
            self.setToolTip(SYMBOL_DESCRIPTIONS[symbol])

    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 2, 5, 2)

        # Symbol label
        self.symbol_label = QLabel(self.symbol)
        self.symbol_label.setStyleSheet(f"color: {COLORS['text']};")
        self.symbol_label.setFixedWidth(60)

        # Price label
        self.price_label = QLabel("---.--")
        self.price_label.setStyleSheet(f"color: {COLORS['text']};")
        self.price_label.setFixedWidth(70)
        self.price_label.setAlignment(Qt.AlignRight)

        # Change label
        self.change_label = QLabel("+0.00")
        self.change_label.setFixedWidth(55)
        self.change_label.setAlignment(Qt.AlignRight)

        # Percent label
        self.pct_label = QLabel("0.00%")
        self.pct_label.setFixedWidth(55)
        self.pct_label.setAlignment(Qt.AlignRight)

        layout.addWidget(self.symbol_label)
        layout.addWidget(self.price_label)
        layout.addWidget(self.change_label)
        layout.addWidget(self.pct_label)

        self.setLayout(layout)

    def update_data(self, data: MarketData):
        """Update display with new data"""
        # Format based on symbol type
        if self.symbol in ["GEX", "DEX", "OGL", "DIX", "SWAN"]:
            self._update_custom_indicator(data)
        else:
            self._update_standard_symbol(data)

    def _update_standard_symbol(self, data: MarketData):
        """Update standard market symbols"""
        self.price_label.setText(f"{data.last:.2f}")

        # Color based on change
        color = COLORS["positive"] if data.change >= 0 else COLORS["negative"]
        sign = "+" if data.change >= 0 else ""

        self.change_label.setText(f"{sign}{data.change:.2f}")
        self.change_label.setStyleSheet(f"color: {color};")

        self.pct_label.setText(f"{sign}{data.change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")

    def _update_custom_indicator(self, data: MarketData):
        """Update custom indicators with special formatting"""
        # Format last value based on indicator type
        if self.symbol == "GEX":
            # Format in billions
            value_b = data.last / 1_000_000_000
            self.price_label.setText(f"{value_b:.1f}B")
            # Color: positive = green (stable), negative = red (volatile)
            color = COLORS["positive"] if data.last > 0 else COLORS["negative"]

        elif self.symbol == "DEX":
            # Format in millions
            value_m = data.last / 1_000_000
            self.price_label.setText(f"{value_m:.0f}M")
            color = COLORS["positive"] if data.change >= 0 else COLORS["negative"]

        elif self.symbol == "OGL":
            # Price level format
            self.price_label.setText(f"{data.last:.2f}")
            # Yellow if SPY is near this level
            spy_price = 585.25  # Would get from actual SPY data
            if abs(spy_price - data.last) < 2:
                color = COLORS["warning"]
            else:
                color = COLORS["text_dim"]

        elif self.symbol == "DIX":
            # Percentage format
            self.price_label.setText(f"{data.last:.1f}%")
            # Color based on bullish/bearish threshold
            if data.last > 45:
                color = COLORS["positive"]
            elif data.last < 40:
                color = COLORS["negative"]
            else:
                color = COLORS["neutral"]

        elif self.symbol == "SWAN":
            # Value with status
            self.price_label.setText(f"{data.last:.2f}")
            # Traffic light colors (for price coloring only)
            if data.last < 1.9:
                color = COLORS["positive"]  # Green
            elif data.last < 2.0:
                color = COLORS["warning"]  # Yellow
            else:
                color = COLORS["negative"]  # Red
            # Display as BSWAN without traffic light emoji
            self.symbol_label.setText("BSWAN")

        # Update change and percentage
        sign = "+" if data.change >= 0 else ""

        # Format change based on indicator
        if self.symbol == "GEX":
            change_b = data.change / 1_000_000_000
            self.change_label.setText(f"{sign}{change_b:.1f}B")
        elif self.symbol == "DEX":
            change_m = data.change / 1_000_000
            self.change_label.setText(f"{sign}{change_m:.0f}M")
        elif self.symbol == "DIX":
            self.change_label.setText(f"{sign}{data.change:.1f}%")
        else:
            self.change_label.setText(f"{sign}{data.change:.2f}")

        self.change_label.setStyleSheet(f"color: {color};")
        self.pct_label.setText(f"{sign}{data.change_pct:.2f}%")
        self.pct_label.setStyleSheet(f"color: {color};")

    def enterEvent(self, event):
        """Show tooltip on hover"""
        if self.symbol in SYMBOL_DESCRIPTIONS:
            QToolTip.showText(
                QPoint(self.mapToGlobal(self.rect().center())), SYMBOL_DESCRIPTIONS[self.symbol]
            )
        super().enterEvent(event)


class GreekBar(QWidget):
    """Custom widget for Greek risk display with automation status"""

    def __init__(self, name: str, min_val: float, max_val: float):
        super().__init__()
        self.name = name
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = 0
        self.percentage = 0
        self.status = "NORMAL"
        self.setFixedHeight(22)

    def set_value(self, value: float, status: str = "NORMAL"):
        """Update Greek value and status"""
        self.current_val = value
        self.percentage = abs(value - self.min_val) / (self.max_val - self.min_val)
        self.percentage = min(max(self.percentage, 0), 1)
        self.status = status
        self.update()

    def paintEvent(self, event):
        """Custom paint for the Greek bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(COLORS["background"]))

        # Bar background
        bar_rect = QRect(110, 6, self.width() - 300, 10)
        painter.fillRect(bar_rect, QColor(COLORS["panel"]))

        # Determine color based on percentage
        if self.percentage < 0.6:
            color = QColor(COLORS["positive"])
        elif self.percentage < 0.8:
            color = QColor(COLORS["warning"])
        else:
            color = QColor(COLORS["negative"])

        # Fill bar
        fill_width = int(bar_rect.width() * self.percentage)
        fill_rect = QRect(bar_rect.x(), bar_rect.y(), fill_width, bar_rect.height())
        painter.fillRect(fill_rect, color)

        # Draw border
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawRect(bar_rect)

        # Draw text
        painter.setPen(QColor(COLORS["text"]))
        font = QFont()
        font.setPointSize(10)
        painter.setFont(font)

        # Greek name and value (left side)
        text = f"{self.name}: {self.current_val:.2f}"
        painter.drawText(10, 16, text)

        # Status text (right side)
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(font)
        status_rect = QRect(self.width() - 190, 0, 180, 22)
        painter.drawText(
            status_rect, Qt.AlignVCenter | Qt.AlignRight, self.status
        )


# ==============================================================================
# MAIN DASHBOARD CLASS
# ==============================================================================
class SpyderTestDashboard(QMainWindow):
    """Main automated trading dashboard window with expanded Signal Monitor"""

    def __init__(self):
        super().__init__()
        self.market_data = {}
        self.positions = []
        self.greek_risks = GreekRisk(45.5, -2.3, -156.8, -245.2)
        self.system_logs = []
        self.automation_logs = []  # New list for autonomous AI logs
        self.account_mode = "PAPER"
        self.ib_connected = True
        self.signal_panel = None  # Will be initialized in create_center_panel

        # Risk Parameters Integration
        self.current_risk_params = None
        self.risk_monitoring_active = False

        self.setup_ui()
        self.setup_timers()
        self.load_test_data()

        # Load default risk parameters
        self.load_default_risk_parameters()

    # ==========================================================================
    # INITIALIZATION METHODS
    # ==========================================================================
    def load_default_risk_parameters(self):
        """Load default risk parameters on startup"""
        if RISK_DIALOG_AVAILABLE:
            # Set default conservative parameters
            self.current_risk_params = {
                "global": {
                    "active_profile": "Conservative",
                    "risk_per_trade": 1.0,
                    "max_daily_loss": 5.0,
                    "max_contracts": 10,
                    "max_delta": 100,
                    "max_vega": -200,
                    "max_theta": -300,
                    "allow_0dte": False,
                    "max_open_positions": 5,
                    "max_buying_power": 50,
                },
                "strategy_groups": {
                    "iron_condor": {"enabled": True, "max_risk": 2.0},
                    "credit_spreads": {"enabled": True, "max_risk": 1.5},
                    "straddles_strangles": {"enabled": False, "max_risk": 3.0},
                },
                "dynamic_rules": {
                    "enable_iv_scaling": True,
                    "vix_threshold": 20.0,
                    "zero_dte_enabled": False,
                },
            }

            # Update automation log with loaded parameters
            self.add_automation_log("Default risk parameters loaded")
            self.add_automation_log(
                f"Active profile: {
                    self.current_risk_params['global']['active_profile']}"
            )

    def update_risk_parameters(self, params: dict):
        """Handle updated risk parameters from dialog"""
        self.current_risk_params = params

        # Log the update
        profile = params.get("global", {}).get("active_profile", "Unknown")
        risk_per_trade = params.get("global", {}).get("risk_per_trade", 0)
        max_contracts = params.get("global", {}).get("max_contracts", 0)

        self.add_system_log(f"Risk parameters updated - Profile: {profile}")
        self.add_automation_log(f"Risk profile changed to: {profile}")
        self.add_automation_log(f"Risk per trade: {risk_per_trade}%")
        self.add_automation_log(f"Max contracts: {max_contracts}")

        # Update automation status display
        self.update_automation_display()

        # Enable risk monitoring
        self.risk_monitoring_active = True
        self.add_automation_log("Risk monitoring activated")

        # Log strategy-specific settings
        strategy_groups = params.get("strategy_groups", {})
        for strategy, settings in strategy_groups.items():
            if settings.get("enabled"):
                self.add_automation_log(
                    f"{strategy.replace('_', ' ').title()} strategy enabled - Max risk: {settings.get('max_risk', 0)}%"
                )

        # Log dynamic rules
        dynamic_rules = params.get("dynamic_rules", {})
        if dynamic_rules.get("enable_iv_scaling"):
            self.add_automation_log("IV-based position scaling ENABLED")
        if dynamic_rules.get("zero_dte_enabled"):
            self.add_automation_log("0DTE trading ENABLED")

        # Update Greek bars with new risk status
        self.update_risk_display()

    def update_automation_display(self):
        """Update the automation status area with current risk info"""
        if not self.current_risk_params:
            return

        # Get risk info
        profile = self.current_risk_params.get("global", {}).get("active_profile", "None")
        risk_per_trade = self.current_risk_params.get("global", {}).get("risk_per_trade", 0)
        max_contracts = self.current_risk_params.get("global", {}).get("max_contracts", 0)

        # Update the first few lines to show current risk settings
        risk_summary_lines = [
            f"RISK PROFILE: {profile}",
            f"RISK/TRADE: {risk_per_trade}%",
            f"MAX CONTRACTS: {max_contracts}",
            f"MONITORING: {'ACTIVE' if self.risk_monitoring_active else 'INACTIVE'}",
            "",  # Empty line separator
        ]

        # Keep existing automation logs but prepend risk summary
        existing_logs = [
            log
            for log in self.automation_logs
            if not any(
                keyword in log
                for keyword in ["RISK PROFILE:", "RISK/TRADE:", "MAX CONTRACTS:", "MONITORING:"]
            )
        ]

        all_logs = risk_summary_lines + existing_logs[:15]  # Limit to prevent overflow

        self.auto_log.clear()
        for log_line in all_logs:
            self.auto_log.append(log_line)

    def update_risk_display(self):
        """Update risk displays based on current parameters"""
        if not self.current_risk_params:
            return

        global_params = self.current_risk_params.get("global", {})

        # Update Greek bars with risk status
        max_delta = global_params.get("max_delta", 100)
        current_delta = abs(self.greek_risks.delta)

        if current_delta > max_delta * 0.8:
            delta_status = "APPROACHING LIMIT"
        elif current_delta > max_delta * 0.6:
            delta_status = "ELEVATED"
        else:
            delta_status = "NORMAL"

        self.greek_bars["delta"].set_value(self.greek_risks.delta, delta_status)

        # Similar logic for other Greeks
        max_vega = abs(global_params.get("max_vega", -200))
        current_vega = abs(self.greek_risks.vega)

        if current_vega > max_vega * 0.8:
            vega_status = "APPROACHING LIMIT"
        else:
            vega_status = "NORMAL"

        self.greek_bars["vega"].set_value(self.greek_risks.vega, vega_status)

    # ==========================================================================
    # UI CREATION METHODS
    # ==========================================================================
    def setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("SPYDER - Autonomous Options Trading")
        self.setGeometry(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

        # Set dark theme
        self.setStyleSheet(
            f"""
            QMainWindow {{
                background-color: {COLORS['background']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: normal;
            }}
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS['background']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
            QPushButton {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 8px;
                border-radius: 3px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
            }}
            QTableWidget {{
                background-color: {COLORS['panel']};
                alternate-background-color: {COLORS['background']};
                color: {COLORS['text']};
                gridline-color: {COLORS['grid']};
                border: 1px solid {COLORS['border']};
                font-size: 11px;
            }}
            QTableWidgetItem {{
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                font-size: 10px;
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
            QScrollArea {{
                background-color: {COLORS['background']};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['background']};
                width: 10px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['border']};
                border-radius: 5px;
            }}
            QLineEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                border-radius: 3px;
            }}
            QToolTip {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
            }}
        """
        )

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(3, 3, 3, 3)
        main_layout.setSpacing(3)

        # Top toolbar
        toolbar = self.create_toolbar()
        main_layout.addWidget(toolbar)

        # Main content splitter
        content_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Market Overview
        left_panel = self.create_left_panel()
        content_splitter.addWidget(left_panel)

        # Center panel - Trading Focus
        center_panel = self.create_center_panel()
        content_splitter.addWidget(center_panel)

        # Right panel - Account & Risk
        right_panel = self.create_right_panel()
        content_splitter.addWidget(right_panel)

        # Set panel sizes
        content_splitter.setSizes([LEFT_PANEL_WIDTH, CENTER_PANEL_WIDTH, RIGHT_PANEL_WIDTH])

        main_layout.addWidget(content_splitter)

        central_widget.setLayout(main_layout)

    def create_toolbar(self) -> QWidget:
        """Create top toolbar with centered market indices"""
        toolbar = QWidget()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};"
        )

        layout = QHBoxLayout()

        # SPYDER logo on left
        logo_label = QLabel("S P Y D E R")
        try:
            logo_font = QFont("Michroma", 16, QFont.Weight.Normal)
        except BaseException:
            logo_font = QFont("Arial", 16, QFont.Weight.Normal)
        logo_label.setFont(logo_font)
        logo_label.setStyleSheet(f"color: {COLORS['text']}; letter-spacing: 5px;")
        layout.addWidget(logo_label)

        # Add stretch to push indices toward center
        layout.addStretch(1)
        layout.addSpacing(25)

        # Center section with market indices
        center_section = QHBoxLayout()
        center_section.setSpacing(15)

        # DJI
        dji_container = QHBoxLayout()
        dji_container.setSpacing(0)
        dji_label = QLabel("DJI:")
        dji_label.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(dji_label)

        self.dji_value = QLabel(" 43,900.42")
        self.dji_value.setStyleSheet(f"color: {COLORS['text']};")
        dji_container.addWidget(self.dji_value)

        self.dji_change = QLabel("  +350.35  +2.3%")
        self.dji_change.setStyleSheet(f"color: {COLORS['positive']};")
        dji_container.addWidget(self.dji_change)

        center_section.addLayout(dji_container)
        center_section.addWidget(QLabel("  ||  "))

        # SPX
        spx_container = QHBoxLayout()
        spx_container.setSpacing(0)
        spx_label = QLabel("SPX:")
        spx_label.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(spx_label)

        self.spx_value = QLabel(" 6,876.23")
        self.spx_value.setStyleSheet(f"color: {COLORS['text']};")
        spx_container.addWidget(self.spx_value)

        self.spx_change = QLabel("  +45.43  +1.2%")
        self.spx_change.setStyleSheet(f"color: {COLORS['positive']};")
        spx_container.addWidget(self.spx_change)

        center_section.addLayout(spx_container)
        center_section.addWidget(QLabel("  ||  "))

        # NDX
        ndx_container = QHBoxLayout()
        ndx_container.setSpacing(0)
        ndx_label = QLabel("NDX:")
        ndx_label.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(ndx_label)

        self.ndx_value = QLabel(" 20,275.62")
        self.ndx_value.setStyleSheet(f"color: {COLORS['text']};")
        ndx_container.addWidget(self.ndx_value)

        self.ndx_change = QLabel("  +45.23  +0.78%")
        self.ndx_change.setStyleSheet(f"color: {COLORS['positive']};")
        ndx_container.addWidget(self.ndx_change)

        center_section.addLayout(ndx_container)

        layout.addLayout(center_section)

        # Add another stretch to balance the centering
        layout.addStretch(2)

        # Right section with IB Connection and Date/Time
        right_section = QHBoxLayout()
        right_section.setSpacing(15)

        # IB Connection status
        self.connection_label = QLabel("IB CONNECTED   ")
        self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
        self.connection_label.setFixedWidth(150)
        right_section.addWidget(self.connection_label)

        # Date/Time
        self.datetime_label = QLabel(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))
        self.datetime_label.setStyleSheet("font-size: 14px;")
        right_section.addWidget(self.datetime_label)

        layout.addLayout(right_section)

        toolbar.setLayout(layout)
        return toolbar

    def create_left_panel(self) -> QWidget:
        """Create left panel with black background and cyan headers"""
        panel = QGroupBox("MARKET OVERVIEW")
        panel.setStyleSheet(f"background-color: {COLORS['background']};")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 10, 0, 0)

        # Header
        header = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 0, 5, 0)

        # Column headers - cyan and properly aligned
        symbol_header = QLabel("SYMBOL")
        symbol_header.setFixedWidth(60)
        symbol_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        last_header = QLabel("LAST")
        last_header.setFixedWidth(70)
        last_header.setAlignment(Qt.AlignRight)
        last_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        chg_header = QLabel("CHG")
        chg_header.setFixedWidth(55)
        chg_header.setAlignment(Qt.AlignRight)
        chg_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        chg_pct_header = QLabel("CHG%")
        chg_pct_header.setFixedWidth(55)
        chg_pct_header.setAlignment(Qt.AlignRight)
        chg_pct_header.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: normal;")

        header_layout.addWidget(symbol_header)
        header_layout.addWidget(last_header)
        header_layout.addWidget(chg_header)
        header_layout.addWidget(chg_pct_header)
        header.setLayout(header_layout)

        layout.addWidget(header)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        layout.addWidget(separator)

        # Scroll area for symbols
        scroll_area = QScrollArea()
        scroll_area.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet(f"background-color: {COLORS['background']};")
        scroll_layout = QVBoxLayout()
        scroll_layout.setSpacing(1)

        # Create symbol widgets
        self.symbol_widgets = {}
        for category, symbols in MARKET_SYMBOLS.items():
            # Category header - cyan, uppercase, unbold
            cat_label = QLabel(category)
            cat_label.setStyleSheet(
                f"color: {
                    COLORS['cyan']}; font-size: 12px; padding: 5px 0px 2px 10px; font-weight: normal;"
            )
            scroll_layout.addWidget(cat_label)

            # Symbol widgets
            for symbol in symbols:
                widget = MarketSymbolWidget(symbol, category)
                widget.setStyleSheet(f"background-color: {COLORS['background']};")
                self.symbol_widgets[symbol] = widget
                scroll_layout.addWidget(widget)

        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)

        layout.addWidget(scroll_area)
        panel.setLayout(layout)
        return panel

    def create_center_panel(self) -> QWidget:
        """Create center panel with chart and positions - UPDATED FOR EXPANDED SIGNAL MONITOR"""
        panel = QWidget()
        layout = QVBoxLayout()

        # Market regime indicator with red text - now centered
        regime_widget = QWidget()
        regime_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};"
        )
        regime_widget.setFixedHeight(40)
        regime_layout = QHBoxLayout()

        # Add stretch to center the content
        regime_layout.addStretch()

        # Create a container for the centered content
        center_container = QHBoxLayout()
        center_container.setSpacing(20)

        # Market Regime section
        regime_section = QHBoxLayout()
        regime_section.setSpacing(5)
        regime_label = QLabel("MARKET REGIME: ")
        regime_label.setStyleSheet(f"color: {COLORS['text']};")
        regime_section.addWidget(regime_label)

        regime_value = QLabel("Low Volatility - Range Bound")
        regime_value.setStyleSheet(f"color: {COLORS['cyan']};")
        regime_section.addWidget(regime_value)

        center_container.addLayout(regime_section)

        # Separator
        separator_label = QLabel("|")
        separator_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        center_container.addWidget(separator_label)

        # Active Strategy section
        strategy_section = QHBoxLayout()
        strategy_section.setSpacing(5)
        strategy_label = QLabel("CURRENT ACTIVE STRATEGY: ")
        strategy_label.setStyleSheet(f"color: {COLORS['text']};")
        strategy_section.addWidget(strategy_label)

        strategy_value = QLabel("Iron Condor")
        strategy_value.setStyleSheet(f"color: {COLORS['cyan']};")
        strategy_section.addWidget(strategy_value)

        center_container.addLayout(strategy_section)

        regime_layout.addLayout(center_container)
        regime_layout.addStretch()

        regime_widget.setLayout(regime_layout)
        layout.addWidget(regime_widget)

        # Chart
        self.create_chart()
        layout.addWidget(self.chart_widget, 2)

        # Positions table
        positions_group = QGroupBox("ORDERS && POSITIONS")
        positions_layout = QVBoxLayout()

        self.positions_table = self.create_positions_table()
        self.positions_table.setMaximumHeight(190)
        self.positions_table.setMinimumHeight(190)
        positions_layout.addWidget(self.positions_table)

        positions_group.setLayout(positions_layout)
        layout.addWidget(positions_group, 1)

        # System logs with EXPANDED Signal Monitor Panel - ADJUSTED PROPORTIONS
        logs_container = QWidget()
        logs_container_layout = QHBoxLayout()
        logs_container_layout.setSpacing(5)
        logs_container_layout.setContentsMargins(0, 0, 0, 0)

        # System logs (left side - REDUCED from ~70% to ~50% to make room for expanded signal panel)
        logs_group = QGroupBox("SYSTEM LOG")
        logs_layout = QVBoxLayout()

        self.system_log = QTextEdit()
        self.system_log.setReadOnly(True)
        self.system_log.setMaximumHeight(150)
        self.system_log.setStyleSheet("font-family: monospace; font-size: 13px;")

        logs_layout.addWidget(self.system_log)
        logs_group.setLayout(logs_layout)

        # EXPANDED Signal Monitor Panel (right side - INCREASED from ~30% to ~50%)
        signal_group = QGroupBox("SIGNAL MONITOR")
        signal_group.setStyleSheet(
            f"""
            QGroupBox {{
                color: {COLORS['text']};
                font-weight: normal;
            }}
        """
        )
        signal_layout = QVBoxLayout()
        signal_layout.setContentsMargins(5, 5, 5, 5)

        # Use the EXPANDED SignalMonitorPanel (2x5 grid, 460px wide)
        self.signal_panel = SignalMonitorPanel()
        signal_layout.addWidget(self.signal_panel)  # Remove center alignment
        signal_group.setLayout(signal_layout)

        # Add to container with NEW proportions (logs ~50%, expanded signal panel ~50%)
        logs_container_layout.addWidget(logs_group, 65)
        logs_container_layout.addWidget(signal_group, 35)

        logs_container.setLayout(logs_container_layout)
        layout.addWidget(logs_container, 1)

        panel.setLayout(layout)
        return panel

    def add_system_log(self, message: str):
        """Add entry to system log with date/time in descending order"""
        timestamp = datetime.now().strftime("%d%b%y %H:%M:%S").upper()
        log_entry = f"{timestamp} - {message}"
        self.system_logs.insert(0, log_entry)

        # Update display - show most recent first
        self.system_log.clear()
        for log in self.system_logs[:20]:
            self.system_log.append(log)

        # Auto-scroll to top to show newest message
        cursor = self.system_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.system_log.setTextCursor(cursor)

    def add_automation_log(self, message: str):
        """Add entry to autonomous AI activity log with date/time in descending order"""
        timestamp = datetime.now().strftime("%d%b%Y %H:%M:%S").upper()
        log_entry = f"{timestamp} - {message}"
        self.automation_logs.insert(0, log_entry)

        # Keep only last 50 entries
        if len(self.automation_logs) > 50:
            self.automation_logs = self.automation_logs[:50]

        # Update display - show most recent first
        self.auto_log.clear()
        for log in self.automation_logs:
            self.auto_log.append(log)

        # Auto-scroll to top to show newest message
        cursor = self.auto_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.auto_log.setTextCursor(cursor)

    def create_chart(self):
        """Create the SPY chart widget"""
        self.chart_widget = QWidget()
        self.chart_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']};"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Create matplotlib figure
        # Plotly figure created as needed - no persistent figure object
        self.figure.patch.set_facecolor(COLORS["panel"])

        # Plotly widgets handle their own display
        self.canvas.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.canvas)

        self.chart_widget.setLayout(layout)

    def create_positions_table(self) -> QTableWidget:
        """Create positions table without row numbers"""
        table = QTableWidget()

        # Columns (no row numbers)
        columns = [
            "DATE",
            "SYMBOL",
            "CNTR",
            "STRIKES",
            "EXPIRY",
            "STRATEGY",
            "STATUS",
            "COST",
            "P&L",
            "AUTO STATUS",
        ]

        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        # Hide row numbers
        table.verticalHeader().setVisible(False)

        # Configure table
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setStyleSheet("font-size: 11px;")

        # Set column widths
        table.setColumnWidth(0, 75)  # DATE
        table.setColumnWidth(1, 55)  # SYMBOL
        table.setColumnWidth(2, 45)  # CNTR
        table.setColumnWidth(3, 135)  # STRIKES
        table.setColumnWidth(4, 65)  # EXPIRY
        table.setColumnWidth(5, 150)  # STRATEGY
        table.setColumnWidth(6, 70)  # STATUS
        table.setColumnWidth(7, 95)  # COST
        table.setColumnWidth(8, 95)  # P&L
        table.setColumnWidth(9, 130)  # AUTO STATUS

        # Set horizontal scrollbar policy
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Set vertical scrollbar policy
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Set row height
        table.verticalHeader().setDefaultSectionSize(22)
        table.setMinimumHeight(190)
        table.setMaximumHeight(190)

        return table

    def create_right_panel(self) -> QWidget:
        """Create right panel with account info and risk metrics"""
        panel = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(5, 5, 5, 5)

        # System control buttons with tooltips
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("START SYSTEM")
        self.start_btn.setStyleSheet(f"background-color: {COLORS['positive']}; color: black;")
        self.start_btn.setToolTip("Connect to IB and start trading")
        self.start_btn.clicked.connect(self.start_system)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP SYSTEM")
        self.stop_btn.setStyleSheet(f"background-color: {COLORS['warning']};")
        self.stop_btn.setToolTip("Disconnect from IB, but let the orders and positions remain")
        self.stop_btn.clicked.connect(self.stop_system)
        button_layout.addWidget(self.stop_btn)

        self.emergency_btn = QPushButton("EMERGENCY CLOSE")
        self.emergency_btn.setStyleSheet(f"background-color: {COLORS['negative']};")
        self.emergency_btn.setToolTip(
            "Close all orders and positions, stop trading, and disconnect from IB"
        )
        self.emergency_btn.clicked.connect(self.emergency_close)
        button_layout.addWidget(self.emergency_btn)

        layout.addLayout(button_layout)

        # Account info group - table layout
        account_group = QGroupBox("")
        account_layout = QVBoxLayout()

        # Create table widget
        table_widget = QWidget()
        table_widget.setStyleSheet(
            f"background-color: {COLORS['panel']}; border: 1px solid {COLORS['border']}; padding: 5px;"
        )
        table_layout = QGridLayout()
        table_layout.setContentsMargins(8, 8, 8, 8)
        table_layout.setHorizontalSpacing(10)
        table_layout.setVerticalSpacing(6)

        # Define cell style
        cell_style = f"""
            padding: 5px 10px;
            background-color: {COLORS['background']};
            border: 1px solid {COLORS['border']};
        """

        # Row 1: ACCOUNT | DU5361048 | MODE: PAPER | RISK PARAMETERS
        account_label = QLabel("ACCOUNT")
        account_label.setStyleSheet(cell_style)
        table_layout.addWidget(account_label, 0, 0)

        account_value = QLabel("DU5361048")
        account_value.setStyleSheet(cell_style)
        table_layout.addWidget(account_value, 0, 1)

        mode_label = QLabel("MODE: PAPER")
        mode_label.setStyleSheet(cell_style + f"color: {COLORS['orange']};")
        table_layout.addWidget(mode_label, 0, 2)

        # RISK PARAMETERS button - Enhanced with integration
        self.risk_params_btn = QPushButton("RISK LEVELS")
        self.risk_params_btn.setStyleSheet("background-color: #0066CC; color: white;")
        self.risk_params_btn.setToolTip("Configure global and strategy-specific risk parameters")
        self.risk_params_btn.clicked.connect(self.show_risk_parameters)
        table_layout.addWidget(self.risk_params_btn, 0, 3)

        # Row 2: SETTLED CASH | $21,800,000.00 | REALIZED P&L | $2,030,450.00
        settled_label = QLabel("SETTLED CASH")
        settled_label.setStyleSheet(cell_style)
        table_layout.addWidget(settled_label, 1, 0)

        self.settled_value = QLabel("$21,800,000.00")
        self.settled_value.setStyleSheet(cell_style + "text-align: right;")
        self.settled_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_layout.addWidget(self.settled_value, 1, 1)

        realized_label = QLabel("REALIZED P&L")
        realized_label.setStyleSheet(cell_style)
        table_layout.addWidget(realized_label, 1, 2)

        self.realized_value = QLabel("$2,030,450.00")
        self.realized_value.setStyleSheet(
            cell_style + f"color: {COLORS['positive']}; text-align: right;"
        )
        self.realized_value.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )
        table_layout.addWidget(self.realized_value, 1, 3)

        # Row 3: BUYING POWER | $20,450,000.00 | UNREALIZED P&L | $1,385,000.00
        buying_label = QLabel("BUYING POWER")
        buying_label.setStyleSheet(cell_style)
        table_layout.addWidget(buying_label, 2, 0)

        self.buying_value = QLabel("$20,450,000.00")
        self.buying_value.setStyleSheet(cell_style + "text-align: right;")
        self.buying_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        table_layout.addWidget(self.buying_value, 2, 1)

        unrealized_label = QLabel("UNREALIZED P&L")
        unrealized_label.setStyleSheet(cell_style)
        table_layout.addWidget(unrealized_label, 2, 2)

        self.unrealized_value = QLabel("$1,385,000.00")
        self.unrealized_value.setStyleSheet(
            cell_style + f"color: {COLORS['positive']}; text-align: right;"
        )
        self.unrealized_value.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )
        table_layout.addWidget(self.unrealized_value, 2, 3)

        # Store references for updates
        self.account_labels = {
            "settled_cash": self.settled_value,
            "unrealized_pnl": self.unrealized_value,
            "realized_pnl": self.realized_value,
            "buying_power": self.buying_value,
        }

        table_widget.setLayout(table_layout)
        account_layout.addWidget(table_widget)

        account_group.setLayout(account_layout)
        layout.addWidget(account_group)

        # P&L Performance
        pnl_group = QGroupBox("P&&L PERFORMANCE")
        pnl_layout = QVBoxLayout()
        pnl_layout.setContentsMargins(5, 1, 5, 1)  # Reduced top/bottom margins to 1 pixel
        pnl_layout.setSpacing(1)  # Reduced spacing to 1 pixel

        self.pnl_table = self.create_pnl_table()
        self.pnl_table.setFixedHeight(150)  # Keep at 150px
        pnl_layout.addWidget(self.pnl_table)

        pnl_group.setLayout(pnl_layout)
        layout.addWidget(pnl_group)

        # Risk Monitor
        risk_group = QGroupBox("RISK MONITOR")
        risk_layout = QVBoxLayout()
        risk_layout.setSpacing(2)

        # Greek bars
        self.greek_bars = {
            "delta": GreekBar("Delta", -100, 100),
            "gamma": GreekBar("Gamma", -10, 10),
            "theta": GreekBar("Theta", -400, 0),
            "vega": GreekBar("Vega", -600, 0),
        }

        for bar in self.greek_bars.values():
            risk_layout.addWidget(bar)

        risk_group.setLayout(risk_layout)
        layout.addWidget(risk_group)

        # Autonomous AI Activity - UPDATED SECTION
        auto_group = QGroupBox("AUTONOMOUS AI ACTIVITY")
        auto_group.setStyleSheet(
            f"""
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding: 0px;
                background-color: {COLORS['background']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                top: -1px;
            }}
        """
        )
        auto_layout = QVBoxLayout()
        auto_layout.setContentsMargins(5, 0, 5, 0)  # Zero margins
        auto_layout.setSpacing(0)

        self.auto_log = QTextEdit()
        self.auto_log.setReadOnly(True)
        self.auto_log.setFixedHeight(146)  # Requested height increase
        self.auto_log.setStyleSheet(
            f"""
            QTextEdit {{
                font-family: monospace;
                font-size: 13px;
                color: {COLORS['cyan']};
                padding: 1px;
                border: 1px solid {COLORS['border']};
                background-color: {COLORS['panel']};
                margin: 0px;
            }}
        """
        )
        # Enable vertical scrolling
        self.auto_log.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.auto_log.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        auto_layout.addWidget(self.auto_log)
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)

        # System Health
        health_group = QGroupBox("SYSTEM HEALTH")
        health_layout = QVBoxLayout()
        health_layout.setSpacing(2)

        self.health_indicators = {
            "risk_manager": QLabel("● RISK MANAGER"),
            "market_data": QLabel("● MARKET DATA"),
            "strategy_engine": QLabel("● STRATEGY ENGINE"),
            "ml_models": QLabel("● ML MODELS"),
            "database": QLabel("● DATABASE"),
        }

        for indicator in self.health_indicators.values():
            indicator.setStyleSheet(f"color: {COLORS['positive']};")
            health_layout.addWidget(indicator)

        health_group.setLayout(health_layout)
        layout.addWidget(health_group)

        panel.setLayout(layout)
        return panel

    # ==========================================================================
    # SYSTEM CONTROL METHODS
    # ==========================================================================
    def start_system(self):
        """Handle start system button click"""
        self.ib_connected = True
        self.update_connection_status()
        self.add_system_log("System started - Connected to IB Gateway")
        self.add_automation_log("System started - Autonomous AI Engine initializing")
        print("Starting IB Gateway connection...")

    def stop_system(self):
        """Handle stop system button click"""
        self.ib_connected = False
        self.update_connection_status()
        self.add_system_log("System stopped - Disconnected from IB")
        self.add_automation_log("System stopped - Autonomous AI Engine shutdown")
        print("Stopping IB Gateway connection...")

    def emergency_close(self):
        """Handle emergency close button click"""
        self.ib_connected = False
        self.update_connection_status()
        self.add_system_log("EMERGENCY CLOSE - All positions closed, system stopped")
        self.add_automation_log("EMERGENCY PROTOCOL - All positions closed by autonomous system")
        print("EMERGENCY: Closing all positions and stopping!")

    def update_connection_status(self):
        """Update IB connection status display"""
        if self.ib_connected:
            self.connection_label.setText("IB CONNECTED   ")
            self.connection_label.setStyleSheet(f"color: {COLORS['positive']};")
        else:
            self.connection_label.setText("IB DISCONNECTED")
            self.connection_label.setStyleSheet(f"color: {COLORS['negative']};")

    def show_risk_parameters(self):
        """Enhanced risk parameters method with full integration"""
        if not RISK_DIALOG_AVAILABLE:
            # Fallback to original placeholder
            QMessageBox.information(
                self,
                "Risk Parameters",
                "Risk Parameters dialog will be implemented here.\n\n"
                "This will allow configuration of:\n"
                "• Global risk limits\n"
                "• Strategy-specific overrides\n"
                "• Dynamic market adjustments\n"
                "• Execution controls",
            )
            return

        # Show the professional risk parameters dialog
        self.add_system_log("Opening Risk Parameters dialog")

        # Show dialog with current parameters
        updated_params = show_risk_parameters_dialog(
            parent=self, current_params=self.current_risk_params
        )

        # Handle the response
        if updated_params:
            self.update_risk_parameters(updated_params)
        else:
            self.add_system_log("Risk Parameters dialog cancelled")

    def create_pnl_table(self) -> QTableWidget:
        """Create P&L performance table with 8 columns including SORTINO and CALMAR ratios"""
        table = QTableWidget(4, 8)  # Changed to 8 columns

        # Create headers with tooltips
        headers = [
            "PERIOD",
            "P&L",
            "WIN RATE",
            "AVG WIN/LOSS",
            "PROFIT-F",
            "SHARP",
            "SORTINO",
            "CALMAR",
        ]
        table.setHorizontalHeaderLabels(headers)

        # Add tooltips to the abbreviated headers
        header = table.horizontalHeader()

        # Set tooltips for the last 4 columns
        table.horizontalHeaderItem(4).setToolTip(
            "Profit Factor: Ratio of gross profit to gross loss\n(Total Winning Trades ÷ Total Losing Trades)"
        )
        table.horizontalHeaderItem(5).setToolTip(
            "Sharpe Ratio: Risk-adjusted return measure\n(Return - Risk Free Rate) ÷ Standard Deviation"
        )
        table.horizontalHeaderItem(6).setToolTip(
            "Sortino Ratio: Downside risk-adjusted return\n(Return - Risk Free Rate) ÷ Downside Deviation"
        )
        table.horizontalHeaderItem(7).setToolTip(
            "Calmar Ratio: Annual return vs maximum drawdown\n(Annual Return ÷ Maximum Drawdown)"
        )

        table.setStyleSheet("font-size: 13px;")

        # Sample data - 4 periods with 8 columns (added SORTINO and CALMAR)
        periods = ["TODAY", "WEEK", "MONTH", "YEAR"]
        data = [
            ("+$850.00", "75%", "$425/$120", "1.65", "1.85", "2.12", "1.95"),  # TODAY
            ("+$3,200.00", "68%", "$380/$150", "1.52", "1.92", "2.05", "2.18"),  # WEEK
            ("+$12,500.00", "72%", "$450/$180", "1.78", "2.15", "2.35", "2.62"),  # MONTH
            ("+$240,000,000.00", "70%", "$500/$200", "1.85", "2.35", "2.58", "3.15"),  # YEAR
        ]

        for row, (period, values) in enumerate(zip(periods, data)):
            # Period
            table.setItem(row, 0, QTableWidgetItem(period))

            # P&L - right aligned
            pnl_item = QTableWidgetItem(values[0])
            pnl_item.setTextAlignment(Qt.AlignRight)
            pnl_item.setForeground(QColor(COLORS["positive"]))
            table.setItem(row, 1, pnl_item)

            # Win Rate - centered
            win_rate_item = QTableWidgetItem(values[1])
            win_rate_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 2, win_rate_item)

            # Avg Win/Loss - centered
            avg_item = QTableWidgetItem(values[2])
            avg_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 3, avg_item)

            # Profit Factor - centered
            profit_factor_item = QTableWidgetItem(values[3])
            profit_factor_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 4, profit_factor_item)

            # Sharpe Ratio - centered
            sharp_ratio_item = QTableWidgetItem(values[4])
            sharp_ratio_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 5, sharp_ratio_item)

            # Sortino Ratio - centered
            sortino_ratio_item = QTableWidgetItem(values[5])
            sortino_ratio_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 6, sortino_ratio_item)

            # Calmar Ratio - centered
            calmar_ratio_item = QTableWidgetItem(values[6])
            calmar_ratio_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 7, calmar_ratio_item)

        # Configure table
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(22)
        header = table.horizontalHeader()

        # Optimized column widths for 8 columns - reduced to fit
        table.setColumnWidth(0, 60)  # PERIOD
        table.setColumnWidth(1, 120)  # P&L
        table.setColumnWidth(2, 60)  # WIN RATE
        table.setColumnWidth(3, 120)  # AVG WIN/LOSS
        table.setColumnWidth(4, 65)  # PROFIT-F
        table.setColumnWidth(5, 55)  # SHARP
        table.setColumnWidth(6, 65)  # SORTINO
        table.setColumnWidth(7, 65)  # CALMAR

        # Calculate total width
        total_width = 60 + 120 + 60 + 120 + 65 + 55 + 65 + 65  # = 610
        table.setFixedWidth(total_width)

        # Don't stretch any columns
        header.setStretchLastSection(False)
        for i in range(8):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)

        # Remove scrollbars
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        return table

    # ==========================================================================
    # TIMER AND UPDATE METHODS
    # ==========================================================================
    def setup_timers(self):
        """Setup update timers with different intervals"""
        # Fast timer (1 second) for critical symbols
        self.fast_timer = QTimer()
        self.fast_timer.timeout.connect(self.update_fast_symbols)
        self.fast_timer.start(FAST_UPDATE_MS)

        # Medium timer (5 seconds)
        self.medium_timer = QTimer()
        self.medium_timer.timeout.connect(self.update_medium_symbols)
        self.medium_timer.start(MEDIUM_UPDATE_MS)

        # Slow timer (15 seconds)
        self.slow_timer = QTimer()
        self.slow_timer.timeout.connect(self.update_slow_symbols)
        self.slow_timer.start(SLOW_UPDATE_MS)

        # Chart timer
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.update_chart)
        self.chart_timer.start(2000)

        # Position timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_positions)
        self.position_timer.start(2000)

        # System log timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.update_system_log)
        self.log_timer.start(10000)

        # DateTime timer
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)

        # Autonomous AI activity timer (update every 3 seconds)
        self.automation_timer = QTimer()
        self.automation_timer.timeout.connect(self.update_automation_status)
        self.automation_timer.start(3000)

    def update_datetime(self):
        """Update the date/time display"""
        self.datetime_label.setText(datetime.now().strftime("%Y-%m-%d   %H:%M:%S  ET"))

    # ==========================================================================
    # DATA LOADING AND SIMULATION METHODS
    # ==========================================================================
    def load_test_data(self):
        """Load test data for demonstration"""
        # Initialize market data with realistic values
        base_prices = {
            # S&P Core
            "SPY": 585.25,
            "SPX": 5850.75,
            "/ES": 5852.50,
            # Volatility
            "VIX": 15.32,
            "VIX9D": 14.8,
            "VXV": 16.2,
            "VXMT": 17.5,
            "VVIX": 82.45,
            "UVXY": 22.18,
            # Market Internals
            "$TICK": 234,
            "$TRIN": 0.85,
            "$ADD": 1245,
            "CPC": 0.95,
            "PCALL": 0.88,
            "SKEW": 125.5,
            # Major Indices
            "DIA": 425.33,
            "QQQ": 485.92,
            "IWM": 225.18,
            # Bonds & Credit
            "TLT": 92.45,
            "LQD": 105.32,
            # Correlations
            "DXY": 103.25,
            "GLD": 195.67,
            # Custom Metrics
            "GEX": -2500000000,  # -2.5B
            "DEX": 850000000,  # 850M
            "OGL": 585.50,  # Price level
            "DIX": 42.5,  # Percentage
            "SWAN": 1.85,  # Risk level
        }

        for symbol, price in base_prices.items():
            if symbol.startswith("$"):
                # Market internals can be positive or negative
                change = random.uniform(-50, 50) if symbol == "$TICK" else random.uniform(-0.1, 0.1)
            elif symbol in ["GEX", "DEX"]:
                # Large numbers for exposure metrics
                change = random.uniform(-500000000, 500000000)
            elif symbol == "DIX":
                # Percentage changes
                change = random.uniform(-2, 2)
            else:
                change = price * (random.random() * 0.04 - 0.02)

            self.market_data[symbol] = MarketData(
                symbol=symbol,
                last=price,
                change=change,
                change_pct=(change / price) * 100 if price != 0 else 0,
                timestamp=datetime.now(),
            )

        # Initialize positions
        self.add_test_positions()

        # Add initial system logs
        self.add_system_log("System initialized successfully")
        self.add_system_log("Connected to IB Gateway")
        self.add_system_log("Market data subscription active")
        self.add_system_log("Strategy engine started")
        self.add_system_log("Risk manager active")
        self.add_system_log("Monitoring SPY options chain")

        # Add initial autonomous AI logs
        self.add_automation_log("Autonomous AI Engine initialized successfully")
        self.add_automation_log("Machine learning models loaded")
        self.add_automation_log("Strategy patterns loaded")
        self.add_automation_log("Risk parameters validated")
        self.add_automation_log("Beginning market analysis")

        # Update initial displays
        self.update_all_symbols()
        self.update_greeks()
        self.update_chart()

    def add_test_positions(self):
        """Add test positions"""
        test_positions = [
            PositionData(
                date="16JAN25",
                symbol="SPY",
                contracts=10,
                strikes="580/582/588/590",
                expiry="17JAN25",
                strategy="Iron Condor",
                status="ACTIVE",
                cost=1250.00,
                pnl=350.00,
                auto_status="MONITORING",
            ),
            PositionData(
                date="16JAN25",
                symbol="SPY",
                contracts=20,
                strikes="582/584",
                expiry="17JAN25",
                strategy="Bull Put Spread",
                status="ACTIVE",
                cost=1700.00,
                pnl=860.00,
                auto_status="THETA HARVEST",
            ),
            PositionData(
                date="16JAN25",
                symbol="SPY",
                contracts=5,
                strikes="590/592/594/596",
                expiry="21JAN25",
                strategy="Iron Condor",
                status="STAGED",
                cost=0.00,
                pnl=0.00,
                auto_status="PENDING FILL",
            ),
        ]

        self.positions = test_positions
        self.update_positions()

    # ==========================================================================
    # UPDATE METHODS
    # ==========================================================================
    def update_fast_symbols(self):
        """Update fast symbols every second"""
        for symbol in FAST_UPDATE_SYMBOLS:
            if symbol in self.market_data:
                self._update_symbol_price(symbol)

    def update_medium_symbols(self):
        """Update medium symbols every 5 seconds"""
        for symbol in MEDIUM_UPDATE_SYMBOLS:
            if symbol in self.market_data:
                self._update_symbol_price(symbol)

    def update_slow_symbols(self):
        """Update slow symbols every 15 seconds"""
        for symbol in SLOW_UPDATE_SYMBOLS:
            if symbol in self.market_data:
                self._update_symbol_price(symbol)

    def _update_symbol_price(self, symbol: str):
        """Update individual symbol price with realistic movement"""
        data = self.market_data[symbol]

        # Different movement patterns for different symbol types
        if symbol.startswith("$"):
            # Market internals - more volatile
            if symbol == "$TICK":
                movement = random.uniform(-100, 100)
            else:
                movement = random.uniform(-0.05, 0.05)
        elif symbol in ["GEX", "DEX"]:
            # Exposure metrics - larger moves
            movement = random.uniform(-100000000, 100000000)
        elif symbol == "DIX":
            # Percentage - smaller moves
            movement = random.uniform(-0.5, 0.5)
        elif symbol == "SWAN":
            # Risk indicator - gradual changes
            movement = random.uniform(-0.05, 0.05)
            # Keep within bounds
            data.last = max(0, min(5, data.last + movement))
            movement = 0  # Recalculate below
        else:
            # Regular symbols - normal market movement
            movement = random.random() * 0.2 - 0.1

        data.last += movement
        data.change += movement
        data.change_pct = (
            (data.change / (data.last - data.change)) * 100 if (data.last - data.change) != 0 else 0
        )
        data.timestamp = datetime.now()

        # Update widget
        if symbol in self.symbol_widgets:
            self.symbol_widgets[symbol].update_data(data)

    def update_all_symbols(self):
        """Update all symbol displays"""
        for symbol, widget in self.symbol_widgets.items():
            if symbol in self.market_data:
                widget.update_data(self.market_data[symbol])

    def update_chart(self):
        """Update the SPY chart with candlesticks and indicators"""
        self.figure.clear()

        # Create sample OHLC data
        periods = 100
        dates = pd.date_range(end=datetime.now(), periods=periods, freq="5min")

        # Generate realistic OHLC data
        spy_price = self.market_data["SPY"].last if "SPY" in self.market_data else 585

        opens = []
        highs = []
        lows = []
        closes = []
        volumes = []

        current_price = spy_price - 2

        for _ in range(periods):
            # Random walk
            change = random.random() * 0.5 - 0.25
            current_price += change

            # OHLC
            open_price = current_price
            high = current_price + random.random() * 0.3
            low = current_price - random.random() * 0.3
            close = low + random.random() * (high - low)
            volume = random.randint(1000000, 5000000)  # SPY typical volume

            opens.append(open_price)
            highs.append(high)
            lows.append(low)
            closes.append(close)
            volumes.append(volume)

            current_price = close

        # Calculate indicators
        # 1. Daily Pivot Points (using yesterday's H/L/C simulation)
        prev_high = max(highs) + random.uniform(0.5, 1.5)
        prev_low = min(lows) - random.uniform(0.5, 1.5)
        prev_close = closes[-1] + random.uniform(-1, 1)

        # Fibonacci Daily Pivot Points
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)
        s1 = (2 * pivot) - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (pivot - prev_low)

        # 2. 20-period Moving Average
        ma_20 = []
        for i in range(len(closes)):
            if i < 19:
                ma_20.append(None)
            else:
                ma_20.append(sum(closes[i - 19 : i + 1]) / 20)

        # 3. VWAP (Volume Weighted Average Price)
        vwap = []
        cumulative_pv = 0
        cumulative_volume = 0
        for i in range(len(closes)):
            typical_price = (highs[i] + lows[i] + closes[i]) / 3
            cumulative_pv += typical_price * volumes[i]
            cumulative_volume += volumes[i]
            vwap.append(cumulative_pv / cumulative_volume)

        # Create plot
        ax = self.figure.add_subplot(111)
        ax.yaxis.tick_left()  # Changed to left side
        ax.yaxis.set_label_position("left")  # Changed to left side

        # Set background color first
        ax.set_facecolor(COLORS["panel"])

        # Plot Fibonacci Daily Pivot Points (behind candlesticks) - STRAIGHT LINES
        ax.axhline(
            y=pivot,
            color="#FFFF00",
            linewidth=1.5,
            linestyle="-",
            alpha=0.7,
            label="Pivot",
            zorder=1,
        )  # Bright yellow
        ax.axhline(
            y=r1, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R1", zorder=1
        )  # Straight line
        ax.axhline(
            y=r2, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R2", zorder=1
        )  # Straight line
        ax.axhline(
            y=r3, color="#00FF41", linewidth=1.5, linestyle="-", alpha=0.6, label="R3", zorder=1
        )  # Straight line
        ax.axhline(
            y=s1, color="#FF1744", linewidth=1.5, linestyle="-", alpha=0.6, label="S1", zorder=1
        )  # Straight line
        ax.axhline(
            y=s2, color="#FF1744", linewidth=1.5, linestyle="-", alpha=0.6, label="S2", zorder=1
        )  # Straight line
        ax.axhline(
            y=s3, color="#FF1744", linewidth=1.5, linestyle="-", alpha=0.6, label="S3", zorder=1
        )  # Straight line

        # Plot 20-period Moving Average (behind candlesticks)
        ma_x = [i for i, val in enumerate(ma_20) if val is not None]
        ma_y = [val for val in ma_20 if val is not None]
        go.Scatter(
            ma_x, ma_y, color="#00B8D4", linewidth=1.5, alpha=0.8, label="MA(20)", zorder=2
        )  # Normal weight

        # Plot VWAP (behind candlesticks) - CHANGED TO BRIGHT PURPLE
        go.Scatter(
            range(len(vwap)),
            vwap,
            color="#BF00FF",
            linewidth=1.5,
            alpha=0.9,
            label="VWAP",
            zorder=2,
        )  # Bright purple

        # Plot candlesticks (on top with higher zorder)
        for i in range(len(dates)):
            color = COLORS["positive"] if closes[i] >= opens[i] else COLORS["negative"]

            # High-Low line - normal weight
            go.Scatter([i, i], [lows[i], highs[i]], color=color, linewidth=1, zorder=3)

            # Open-Close box - normal weight
            height = abs(closes[i] - opens[i])
            bottom = min(opens[i], closes[i])

            rect = plt.Rectangle(
                (i - 0.3, bottom),
                0.6,
                height,
                facecolor=color,
                edgecolor=color,
                alpha=0.9,
                zorder=3,
            )
            ax.add_patch(rect)

        # Add pivot level labels on the right (no bold)
        ax.text(
            len(dates),
            pivot,
            f" P: {
                pivot:.2f}",
            color="#FFFF00",
            fontsize=9,
            va="center",
        )  # Bright yellow, no bold
        ax.text(len(dates), r1, f" R1: {r1:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), r2, f" R2: {r2:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), r3, f" R3: {r3:.2f}", color="#00FF41", fontsize=8, va="center")
        ax.text(len(dates), s1, f" S1: {s1:.2f}", color="#FF1744", fontsize=8, va="center")
        ax.text(len(dates), s2, f" S2: {s2:.2f}", color="#FF1744", fontsize=8, va="center")
        ax.text(len(dates), s3, f" S3: {s3:.2f}", color="#FF1744", fontsize=8, va="center")

        # Styling
        ax.set_title("SPY - 5 min", color=COLORS["text"], fontsize=12, pad=10)
        ax.set_xlim(-1, len(dates))
        ax.grid(True, alpha=0.2, color=COLORS["grid"], zorder=0)

        # Format x-axis with time labels
        num_labels = 6
        indices = np.linspace(0, len(dates) - 1, num_labels, dtype=int)
        ax.set_xticks(indices)

        time_labels = []
        for idx in indices:
            time_str = dates[idx].strftime("%H:%M")
            time_labels.append(time_str)

        ax.set_xticklabels(time_labels, fontsize=9)

        # Style axes - white text on left Y-axis
        ax.tick_params(colors="#FFFFFF")  # White price labels on left
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])

        # Adjust layout
        self.figure.tight_layout()
        self.canvas.draw()

    def update_positions(self):
        """Update positions table"""
        self.positions_table.setRowCount(len(self.positions))

        for row, position in enumerate(self.positions):
            # Set items with proper alignment
            date_item = QTableWidgetItem(position.date)
            date_item.setTextAlignment(Qt.AlignCenter)
            self.positions_table.setItem(row, 0, date_item)

            symbol_item = QTableWidgetItem(position.symbol)
            symbol_item.setTextAlignment(Qt.AlignCenter)
            self.positions_table.setItem(row, 1, symbol_item)

            contract_item = QTableWidgetItem(str(position.contracts))
            contract_item.setTextAlignment(Qt.AlignCenter)
            self.positions_table.setItem(row, 2, contract_item)

            strikes_item = QTableWidgetItem(position.strikes)
            strikes_item.setTextAlignment(Qt.AlignCenter)
            self.positions_table.setItem(row, 3, strikes_item)

            expiry_item = QTableWidgetItem(position.expiry)
            expiry_item.setTextAlignment(Qt.AlignCenter)
            self.positions_table.setItem(row, 4, expiry_item)

            self.positions_table.setItem(row, 5, QTableWidgetItem(position.strategy))

            status_item = QTableWidgetItem(position.status)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.positions_table.setItem(row, 6, status_item)

            cost_item = QTableWidgetItem(f"${position.cost:,.2f}")
            cost_item.setTextAlignment(Qt.AlignRight)
            self.positions_table.setItem(row, 7, cost_item)

            # P&L with color
            pnl_item = QTableWidgetItem(f"${position.pnl:+,.2f}")
            if position.pnl > 0:
                pnl_item.setForeground(QColor(COLORS["positive"]))
            elif position.pnl < 0:
                pnl_item.setForeground(QColor(COLORS["negative"]))
            pnl_item.setTextAlignment(Qt.AlignRight)
            self.positions_table.setItem(row, 8, pnl_item)

            # Auto status with color
            auto_item = QTableWidgetItem(position.auto_status)
            auto_item.setForeground(QColor(COLORS["automation_active"]))
            self.positions_table.setItem(row, 9, auto_item)

            # Color row based on status
            if position.status == "STAGED":
                for col in range(self.positions_table.columnCount()):
                    item = self.positions_table.item(row, col)
                    if item:
                        item.setBackground(QColor(30, 30, 30))
            elif position.status == "CLOSED":
                for col in range(self.positions_table.columnCount()):
                    item = self.positions_table.item(row, col)
                    if item:
                        item.setForeground(QColor(COLORS["text_dim"]))

    def update_greeks(self):
        """Update Greek risk displays"""
        # Set values with automation status
        self.greek_bars["delta"].set_value(self.greek_risks.delta, "AUTO-HEDGING OFF")
        self.greek_bars["gamma"].set_value(self.greek_risks.gamma, "NORMAL")
        self.greek_bars["theta"].set_value(self.greek_risks.theta, "HARVESTING TIME")
        self.greek_bars["vega"].set_value(self.greek_risks.vega, "NORMAL")

        # Simulate changes
        self.greek_risks.delta += random.uniform(-2, 2)
        self.greek_risks.gamma += random.uniform(-0.1, 0.1)
        self.greek_risks.theta += random.uniform(-5, 5)
        self.greek_risks.vega += random.uniform(-10, 10)

    def update_system_log(self):
        """Add periodic system log entries"""
        log_messages = [
            "Option chain updated",
            "Risk parameters checked",
            "Position delta hedged",
            "Market regime analysis complete",
            "Greeks recalculated",
            "Strategy signals evaluated",
            "Order routing verified",
            "System health check passed",
            "Data feed active",
            "ML models updated",
            "Volatility surface refreshed",
            "Correlation matrix updated",
            "SWAN indicator checked",
            "GEX levels calculated",
            "Dark pool activity monitored",
            "RSI confluence analyzed",
            "Divergence patterns scanned",
            "AI decision matrix updated",
            "Risk triggers evaluated",
            "Signal monitor refreshed",
        ]

        message = random.choice(log_messages)
        self.add_system_log(message)

    def update_automation_status(self):
        """Update autonomous AI activity with realistic AI trading activities"""
        # Define automation messages based on market conditions and AI activities
        automation_messages = [
            # Scanning and Analysis
            "AI: Scanning SPY options chain for opportunities",
            "AI: Analyzing 0DTE Iron Condor setups",
            "AI: Evaluating volatility skew for entry signals",
            "AI: Calculating optimal strike selection",
            "AI: Running ML models on current market structure",
            # Signal Detection
            "AI: SIGNAL - Iron Condor opportunity detected",
            "AI: SIGNAL - Bull Put Spread setup identified",
            "AI: SIGNAL - Volatility expansion expected",
            "AI: SIGNAL - Mean reversion trade available",
            # Order Management
            "AI: Placing order: SPY 585/587/590/592 IC @ $0.45",
            "AI: Order FILLED - Monitoring position Greeks",
            "AI: Adjusting position for delta neutrality",
            "AI: Scaling into position - 50% filled",
            # Risk Management
            "AI: Position delta exceeded - hedging required",
            "AI: Theta harvest mode - collecting $156/day",
            "AI: Risk limit approaching - reducing size",
            "AI: Stop loss triggered on position #3",
            # Strategy Decisions
            "AI: Volatility regime change - switching strategy",
            "AI: Market trending - pausing IC entries",
            "AI: VIX contango stable - selling premium",
            "AI: High SKEW detected - defensive mode",
            # Position Management
            "AI: Rolling 17JAN puts to 21JAN",
            "AI: Closing winner - 75% max profit reached",
            "AI: Defending tested spread - adding hedge",
            "AI: Converting IC to Iron Butterfly",
            # Market Analysis
            "AI: $TICK divergence detected - monitoring",
            "AI: RSI confluence achieved - preparing entry",
            "AI: VWAP deviation +2.1% - short bias",
            "AI: GEX flipped negative - expect volatility",
            # Custom Metrics Analysis
            "AI: DEX positive - MM net buying detected",
            "AI: OGL breach - volatility regime shift",
            "AI: DIX above 45% - institutional bullishness",
            "AI: SWAN level stable - normal operations",
            # Profit Taking
            "AI: Taking profits on position #1 - $850",
            "AI: Partial close - securing 50% gains",
            "AI: Target reached - closing full position",
            "AI: Quick scalp completed - $320 profit",
            # Waiting States
            "AI: Waiting for optimal entry - IV too low",
            "AI: No setups match criteria - standing by",
            "AI: Market conditions unclear - holding",
            "AI: Preparing for FOMC - reduced exposure",
        ]

        # Get current market conditions to make messages contextual
        if "VIX" in self.market_data:
            vix_value = self.market_data["VIX"].last
        else:
            vix_value = 15  # Default value

        if "SPY" in self.market_data:
            self.market_data["SPY"].last
        else:
            pass  # Default value

        # Select message based on some logic
        if vix_value > 20:
            # High volatility messages
            relevant_messages = [
                msg
                for msg in automation_messages
                if "volatility" in msg.lower() or "risk" in msg.lower()
            ]
        elif vix_value < 15:
            # Low volatility messages
            relevant_messages = [
                msg for msg in automation_messages if "premium" in msg.lower() or "IC" in msg
            ]
        else:
            # Normal conditions - all messages
            relevant_messages = automation_messages

        # Select a random message from relevant ones
        message = random.choice(relevant_messages if relevant_messages else automation_messages)

        # Add the log entry with timestamp
        self.add_automation_log(message)


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main entry point for the Expanded Spyder Test Dashboard"""
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show dashboard
    dashboard = SpyderTestDashboard()
    dashboard.show()

    print("✅ Spyder Test Dashboard v1.1 - EXPANDED Signal Monitor")
    print("🎯 New Features:")
    print("   • EXPANDED 2x5 Signal Monitor grid (10 signals total)")
    print("   • 5 NEW custom metric dialogs (GEX, DEX, OGL, DIX, SWAN)")
    print("   • Priority-ordered signal placement")
    print("   • Enhanced layout with balanced proportions")
    print("   • Real-time market data simulation for all metrics")
    print("   • Professional popup dialogs with trading insights")
    print("   • SWAN indicator weighted 85% green (rare events)")
    print("📋 Signal Monitor Layout:")
    print("   [VIX MONITOR]    [AI DECISION]")
    print("   [GEX]            [DIX]")
    print("   [RSI CONFLUENCE] [RISK TRIGGERS]")
    print("   [OGL]            [DIVERGENCE]")
    print("   [DEX]            [SWAN]")
    print("💡 Instructions:")
    print("   1. Use START SYSTEM to begin simulation")
    print("   2. Click RISK PARAMETERS to configure settings")
    print("   3. Click any signal monitor button for detailed analysis")
    print("   4. Monitor all 10 signals with traffic light indicators")
    print("   5. Custom metrics (GEX/DEX/OGL/DIX/SWAN) show in both panels")

    sys.exit(app.exec())


# ==============================================================================
# ENTRY POINT
# ==============================================================================
if __name__ == "__main__":
    print("🚀 Starting Spyder Test Dashboard...")

    try:
        print("📋 Creating QApplication...")
        # Run main expanded dashboard
        main()

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
