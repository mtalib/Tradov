#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI [Application Name] [Group Letter] [Group Name]
Module: SpyderG29_ChartWidgetPlotly.py [Application Name][Group Letter] [Module Number]_[Purpose].py
Purpose: Plotly-based chart widget
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-15 Time: 22:20:00

Module Description:
    Plotly-based chart widget for the Spyder Trading Dashboard. Provides high-performance
    interactive financial charts using Plotly embedded via PySide6's QWebEngineView.
    This approach offers superior Wayland compatibility, smooth interactions, and
    excellent financial charting capabilities while maintaining compatibility with
    the existing dashboard interface.

    This module was renumbered from SpyderG04_ChartWidgetPlotly.py as part of the
    modular refactoring effort to eliminate duplicate module numbers and improve
    code organization.

    Key advantages over matplotlib:
    - Native browser-based rendering (no OpenGL/Wayland issues)
    - Smooth zoom/pan interactions optimized for financial data
    - Built-in candlestick and technical indicator support
    - Hardware acceleration via Chromium engine
    - Efficient real-time data streaming

Module Constants:
    CHART_UPDATE_INTERVAL (int): Chart update interval in milliseconds (1000)
    DATA_POINT_LIMIT (int): Maximum number of data points to display (1000)
    DEFAULT_CHART_HEIGHT (int): Default chart height in pixels (400)
    DEFAULT_CHART_WIDTH (int): Default chart width in pixels (800)

Change Log:
    2025-10-15 (v1.6.0):
        - Renumbered from SpyderG04_ChartWidgetPlotly.py to SpyderG29_ChartWidgetPlotly.py
        - Updated module header with standard structure
        - Enhanced documentation and constants
    2025-09-27 (v1.5):
        - Initial module creation with Plotly integration
        - Added WebEngine support for Ubuntu/Wayland compatibility
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import json
import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import numpy as np
import pandas as pd

# ==============================================================================
# PYTHON PATH SETUP
# ==============================================================================
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QApplication,
    QComboBox,
    QGridLayout,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QUrl
from PySide6.QtGui import QPalette, QColor, QFont
import logging

# Import WebEngine for Plotly embedding
WEBENGINE_AVAILABLE = False
WEBENGINE_ERROR = None
QWebEngineView = None
QWebEngineSettings = None

# Try to import WebEngine components
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings

    WEBENGINE_AVAILABLE = True
    logging.info("✅ QWebEngineView available for Plotly embedding")
except ImportError as e:
    WEBENGINE_AVAILABLE = False
    WEBENGINE_ERROR = str(e)
    logging.info(f"⚠️ QWebEngineView not available: {e}")
    logging.info("   Solutions for Ubuntu/Wayland:")
    logging.info("   1. sudo apt install python3-pyside6.qtwebengine")
    logging.info("   2. sudo apt install libqt6webengine6-data")
    logging.info("   3. pip install 'PySide6>=6.5' (includes WebEngine)")

    # Create dummy classes to prevent runtime errors
    class DummyWebEngineView:
        def __init__(self, *args, **kwargs):
            raise ImportError("QWebEngineView not available")

    class DummyWebEngineSettings:
        pass

    QWebEngineView = DummyWebEngineView
    QWebEngineSettings = DummyWebEngineSettings

# Import Plotly for chart generation
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import plotly.io as pio

    PLOTLY_AVAILABLE = True
    logging.info("✅ Plotly available for financial charting")
except ImportError:
    PLOTLY_AVAILABLE = False
    logging.info("⚠️ Plotly not available - install plotly")

# ==============================================================================
# CONSTANTS & STYLING
# ==============================================================================
# Dashboard-compatible colors (matching existing theme)
COLOR_BACKGROUND = "#0a0a0a"
COLOR_PANEL = "#1a1a1a"
COLOR_BORDER = "#333333"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#888888"
COLOR_POSITIVE = "#00ff41"
COLOR_NEGATIVE = "#ff1744"
COLOR_NEUTRAL = "#ffd700"
COLOR_WARNING = "#ff9800"
COLOR_CYAN = "#00ffff"

# Plotly theme configuration matching dashboard
PLOTLY_THEME = {
    "layout": {
        "paper_bgcolor": COLOR_PANEL,
        "plot_bgcolor": COLOR_PANEL,
        "font": {"color": COLOR_TEXT, "family": "Arial", "size": 12},
        "xaxis": {
            "gridcolor": "#2a2a2a",
            "linecolor": COLOR_BORDER,
            "tickcolor": COLOR_TEXT,
            "tickfont": {"color": COLOR_TEXT, "size": 10},
        },
        "yaxis": {
            "gridcolor": "#2a2a2a",
            "linecolor": COLOR_BORDER,
            "tickcolor": COLOR_TEXT,
            "tickfont": {"color": COLOR_TEXT, "size": 10},
        },
        "margin": {"l": 60, "r": 30, "t": 30, "b": 40},
    }
}


# ==============================================================================
# PLOTLY CHART WIDGET CLASS
# ==============================================================================
class PlotlyChartWidget(QWidget):
    """
    High-performance Plotly-based chart widget using WebEngine.

    This widget provides interactive financial charts with superior Wayland
    compatibility and smooth performance. It maintains the same interface
    as the existing matplotlib-based chart widgets for drop-in replacement.
    """

    # Signals - maintaining compatibility with existing dashboard
    price_updated = Signal(float)  # Current price
    indicator_updated = Signal(str, float)  # Indicator name, value
    chart_interaction = Signal(str, dict)  # Interaction type, data

    def __init__(self, symbol: str = "SPY", parent=None):
        """Initialize the Plotly chart widget."""
        super().__init__(parent)

        self.symbol = symbol
        self.df = None
        self.current_price = 0.0

        # Chart configuration - volume disabled for single-pane layout
        self.indicators = {
            "sma_20": {"enabled": True, "color": COLOR_CYAN, "period": 20},
            "sma_50": {"enabled": True, "color": COLOR_WARNING, "period": 50},
            "vwap": {"enabled": True, "color": "#BF00FF"},
            "volume": {"enabled": False},  # Disabled to remove volume bars
        }

        # Check dependencies
        if not WEBENGINE_AVAILABLE or not PLOTLY_AVAILABLE:
            self.setup_fallback_widget()
            return

        # Setup UI
        self.setup_ui()
        self.setup_webengine()
        self.setup_timers()

        # Load initial data
        self.load_sample_data()
        self.create_initial_chart()

    def setup_ui(self):
        """Setup the user interface maintaining dashboard compatibility."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # No control panel - clean chart display like Perfect version

        # Create web engine view for Plotly
        if WEBENGINE_AVAILABLE:
            self.web_view = QWebEngineView()
            self.web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            layout.addWidget(self.web_view)

        # Apply dashboard styling - EXACT match
        self.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_PANEL};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
            }}
            QPushButton {{
                background-color: #2a2a2a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 5px;
                border-radius: 3px;
                min-width: 60px;
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            QCheckBox {{
                color: {COLOR_TEXT};
                spacing: 5px;
            }}
            QCheckBox::indicator {{
                width: 13px;
                height: 13px;
            }}
            QCheckBox::indicator:unchecked {{
                border: 1px solid {COLOR_BORDER};
                background-color: {COLOR_PANEL};
            }}
            QCheckBox::indicator:checked {{
                border: 1px solid {COLOR_POSITIVE};
                background-color: {COLOR_POSITIVE};
            }}
            QComboBox {{
                background-color: #2a2a2a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 3px;
                border-radius: 3px;
                min-width: 80px;
            }}
            QComboBox:drop-down {{
                border: none;
            }}
            QComboBox::down-arrow {{
                border: none;
            }}
        """
        )

        self.setLayout(layout)

    def create_control_panel(self) -> QWidget:
        """Create control panel matching dashboard style exactly."""
        control_panel = QFrame()
        control_panel.setFixedHeight(35)
        control_panel.setStyleSheet(
            f"""
            QFrame {{
                background-color: #2a2a2a;
                border: 1px solid {COLOR_BORDER};
                border-bottom: none;
            }}
        """
        )

        layout = QHBoxLayout()
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(15)

        # Symbol label
        symbol_label = QLabel(f"{self.symbol} Chart")
        symbol_label.setStyleSheet(f"color: {COLOR_CYAN}; font-weight: bold;")
        layout.addWidget(symbol_label)

        layout.addStretch()

        # Chart style selector (simplified header)
        self.chart_style_combo = QComboBox()
        self.chart_style_combo.addItems(["Candlestick", "OHLC", "Line"])
        self.chart_style_combo.setCurrentText("Candlestick")
        layout.addWidget(self.chart_style_combo)

        # Time frame selector
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1min", "5min", "15min", "1h", "1d"])
        self.timeframe_combo.setCurrentText("5min")
        self.timeframe_combo.currentTextChanged.connect(self.change_timeframe)
        layout.addWidget(self.timeframe_combo)

        # Refresh button
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedWidth(30)
        refresh_btn.setToolTip("Refresh chart data")
        refresh_btn.clicked.connect(self.refresh_chart)
        layout.addWidget(refresh_btn)

        control_panel.setLayout(layout)
        return control_panel

    def setup_webengine(self):
        """Configure WebEngine settings for optimal Plotly performance."""
        if not hasattr(self, "web_view"):
            return

        settings = self.web_view.settings()

        # Enable hardware acceleration and GPU features
        settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)

        # Enable JavaScript for interactivity
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # Disable unnecessary features for performance
        settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
        settings.setAttribute(QWebEngineSettings.PlaybackRequiresUserGesture, False)

        logging.info("✅ WebEngine configured for optimal Plotly performance")

    def setup_timers(self):
        """Setup timers for real-time updates."""
        # Real-time data update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_real_time_data)
        self.update_timer.start(2000)  # Update every 2 seconds

        # Chart refresh timer (less frequent)
        self.chart_timer = QTimer()
        self.chart_timer.timeout.connect(self.refresh_chart_data)
        self.chart_timer.start(30000)  # Refresh every 30 seconds

    def load_sample_data(self):
        """Load sample OHLCV data for initial display."""
        # Generate realistic sample data
        periods = 100
        dates = pd.date_range(end=datetime.datetime.now(), periods=periods, freq="5min")

        # Generate realistic OHLCV data with some volatility
        np.random.seed(42)  # For reproducible sample data

        base_price = 585.0  # SPY approximate price
        price_changes = np.random.normal(0, 0.5, periods).cumsum()

        # Create OHLC data
        opens = base_price + price_changes
        closes = opens + np.random.normal(0, 0.3, periods)
        highs = np.maximum(opens, closes) + np.random.exponential(0.2, periods)
        lows = np.minimum(opens, closes) - np.random.exponential(0.2, periods)
        volumes = np.random.normal(2000000, 500000, periods).astype(int)

        # Create DataFrame
        self.df = pd.DataFrame(
            {
                "datetime": dates,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )

        # Calculate technical indicators
        self.calculate_indicators()

        # Update current price
        self.current_price = float(self.df["close"].iloc[-1])
        self.price_updated.emit(self.current_price)

    def calculate_indicators(self):
        """Calculate technical indicators."""
        if self.df is None or len(self.df) < 50:
            return

        # Simple Moving Averages
        self.df["sma_20"] = self.df["close"].rolling(window=20).mean()
        self.df["sma_50"] = self.df["close"].rolling(window=50).mean()

        # VWAP (Volume Weighted Average Price)
        typical_price = (self.df["high"] + self.df["low"] + self.df["close"]) / 3
        self.df["vwap"] = (typical_price * self.df["volume"]).cumsum() / self.df[
            "volume"
        ].cumsum()

    def calculate_fibonacci_pivots(self):
        """Calculate Classic Fibonacci Daily Pivot Points (Standard Pivots)."""
        if self.df is None or len(self.df) == 0:
            return {}

        # Use data for pivot calculations
        high = self.df["high"].max()
        low = self.df["low"].min()
        close = self.df["close"].iloc[-1]

        # Calculate Classic Pivot Point
        pivot = (high + low + close) / 3

        # Classic Pivot Point Resistances and Supports
        r1 = (2 * pivot) - low
        r2 = pivot + (high - low)
        r3 = high + 2 * (pivot - low)
        s1 = (2 * pivot) - high
        s2 = pivot - (high - low)
        s3 = low - 2 * (pivot - low)

        return {
            "Pivot": pivot,
            "R1": r1,
            "R2": r2,
            "R3": r3,
            "S1": s1,
            "S2": s2,
            "S3": s3,
        }

    def create_initial_chart(self):
        """Create the initial Plotly chart - single pane for price only."""
        if not PLOTLY_AVAILABLE or self.df is None:
            return

        # Create single plot for price chart only (no volume subplot)
        fig = go.Figure()

        # Candlestick chart
        candlestick = go.Candlestick(
            x=self.df["datetime"],
            open=self.df["open"],
            high=self.df["high"],
            low=self.df["low"],
            close=self.df["close"],
            name=self.symbol,
            increasing_line_color=COLOR_POSITIVE,
            decreasing_line_color=COLOR_NEGATIVE,
            increasing_fillcolor=COLOR_POSITIVE,
            decreasing_fillcolor=COLOR_NEGATIVE,
        )
        fig.add_trace(candlestick)

        # Technical indicators
        if self.indicators["sma_20"]["enabled"]:
            fig.add_trace(
                go.Scatter(
                    x=self.df["datetime"],
                    y=self.df["sma_20"],
                    mode="lines",
                    name="SMA20",
                    line=dict(color=self.indicators["sma_20"]["color"], width=1.5),
                    opacity=0.8,
                )
            )

        if self.indicators["sma_50"]["enabled"]:
            fig.add_trace(
                go.Scatter(
                    x=self.df["datetime"],
                    y=self.df["sma_50"],
                    mode="lines",
                    name="SMA50",
                    line=dict(color=self.indicators["sma_50"]["color"], width=1.5),
                    opacity=0.8,
                )
            )

        if self.indicators["vwap"]["enabled"]:
            fig.add_trace(
                go.Scatter(
                    x=self.df["datetime"],
                    y=self.df["vwap"],
                    mode="lines",
                    name="VWAP",
                    line=dict(color=self.indicators["vwap"]["color"], width=2),
                    opacity=0.9,
                )
            )

        # Add Fibonacci Pivot Points as horizontal lines (Classic Pivot Points)
        pivots = self.calculate_fibonacci_pivots()
        if pivots:
            # Get the last datetime for annotation positioning
            last_date = self.df["datetime"].iloc[-1]

            # Pivot line (yellow - same as Perfect)
            fig.add_hline(
                y=pivots["Pivot"],
                line_dash="solid",
                line_color="#FFFF00",  # Yellow
                line_width=1.5,
                opacity=0.7,
            )
            # Add label as text annotation
            fig.add_annotation(
                x=last_date,
                y=pivots["Pivot"],
                text=f" P: {pivots['Pivot']:.2f}",
                showarrow=False,
                font=dict(color="#FFFF00", size=9),
                xanchor="left",
                yanchor="middle",
            )

            # Resistance levels (green - same as Perfect #00FF41)
            for level in ["R1", "R2", "R3"]:
                fig.add_hline(
                    y=pivots[level],
                    line_dash="solid",
                    line_color="#00FF41",  # Green
                    line_width=1.5,
                    opacity=0.6,
                )
                # Add label as text annotation
                fig.add_annotation(
                    x=last_date,
                    y=pivots[level],
                    text=f" {level}: {pivots[level]:.2f}",
                    showarrow=False,
                    font=dict(color="#00FF41", size=8),
                    xanchor="left",
                    yanchor="middle",
                )

            # Support levels (red - same as Perfect #FF1744)
            for level in ["S1", "S2", "S3"]:
                fig.add_hline(
                    y=pivots[level],
                    line_dash="solid",
                    line_color="#FF1744",  # Red
                    line_width=1.5,
                    opacity=0.6,
                )
                # Add label as text annotation
                fig.add_annotation(
                    x=last_date,
                    y=pivots[level],
                    text=f" {level}: {pivots[level]:.2f}",
                    showarrow=False,
                    font=dict(color="#FF1744", size=8),
                    xanchor="left",
                    yanchor="middle",
                )

        # Volume chart removed - single pane layout

        # Update layout with theme - fixed height, single pane
        fig.update_layout(
            **PLOTLY_THEME["layout"],
            height=480,  # Fixed height to eliminate scrollbars
            # margin already defined in PLOTLY_THEME["layout"]
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,  # Position legend below chart
                xanchor="center",
                x=0.5,
                bgcolor="rgba(0,0,0,0)",
                font=dict(color=COLOR_TEXT, size=10),
            ),
            xaxis_rangeslider_visible=False,  # Disable range slider
            hovermode="x unified",
            title=dict(
                text=f"{self.symbol} - 5 min",  # Match Good version format
                font=dict(color=COLOR_TEXT, size=12),  # Match Good version size
                x=0.5,
                y=0.95,
            ),
        )

        # Update axes styling
        fig.update_xaxes(**PLOTLY_THEME["layout"]["xaxis"])
        fig.update_yaxes(**PLOTLY_THEME["layout"]["yaxis"])

        # Convert to HTML and load in WebEngine
        html_string = fig.to_html(include_plotlyjs="cdn", div_id="plotly-chart")

        # Add JavaScript for real-time updates and interactions
        html_string = self.add_javascript_bridge(html_string)

        if hasattr(self, "web_view"):
            self.web_view.setHtml(html_string)

    def add_javascript_bridge(self, html_string: str) -> str:
        """Add JavaScript bridge for real-time updates and interaction callbacks."""
        js_bridge = """
        <script>
        // JavaScript bridge for Qt-Plotly communication
        window.plotlyReady = false;

        // Wait for Plotly to be ready
        window.addEventListener('load', function() {
            setTimeout(function() {
                window.plotlyReady = true;
                console.log('Plotly chart ready for updates');
            }, 1000);
        });

        // Function to update chart data (called from Qt)
        function updateChartData(newData) {
            if (!window.plotlyReady) return;

            try {
                var update = JSON.parse(newData);
                Plotly.extendTraces('plotly-chart', update.data, update.traces);
            } catch (e) {
                console.error('Error updating chart:', e);
            }
        }

        // Function to update indicators (called from Qt)
        function updateIndicators(indicatorData) {
            if (!window.plotlyReady) return;

            try {
                var data = JSON.parse(indicatorData);
                Plotly.restyle('plotly-chart', data.style, data.traces);
            } catch (e) {
                console.error('Error updating indicators:', e);
            }
        }

        // Capture chart interactions and send to Qt
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                var plotDiv = document.getElementById('plotly-chart');
                if (plotDiv) {
                    plotDiv.on('plotly_hover', function(data) {
                        // Send hover data to Qt (if needed)
                        console.log('Chart hover:', data);
                    });

                    plotDiv.on('plotly_click', function(data) {
                        // Send click data to Qt (if needed)
                        console.log('Chart click:', data);
                    });

                    plotDiv.on('plotly_zoom', function(data) {
                        // Send zoom data to Qt (if needed)
                        console.log('Chart zoom:', data);
                    });
                }
            }, 2000);
        });
        </script>
        """

        # Insert JavaScript before closing body tag
        return html_string.replace("</body>", js_bridge + "</body>")

    def update_real_time_data(self):
        """Update chart with real-time data."""
        if self.df is None or len(self.df) == 0:
            return

        # Simulate new data point
        last_close = self.df["close"].iloc[-1]
        new_time = self.df["datetime"].iloc[-1] + pd.Timedelta(minutes=5)

        # Generate new OHLCV data
        price_change = np.random.normal(0, 0.3)
        new_close = last_close + price_change
        new_open = last_close
        new_high = max(new_open, new_close) + abs(np.random.normal(0, 0.1))
        new_low = min(new_open, new_close) - abs(np.random.normal(0, 0.1))
        new_volume = int(np.random.normal(2000000, 500000))

        # Add new data to DataFrame
        new_row = pd.DataFrame(
            {
                "datetime": [new_time],
                "open": [new_open],
                "high": [new_high],
                "low": [new_low],
                "close": [new_close],
                "volume": [new_volume],
            }
        )

        self.df = pd.concat([self.df, new_row], ignore_index=True)

        # Keep only last 100 periods for performance
        if len(self.df) > 100:
            self.df = self.df.tail(100).reset_index(drop=True)

        # Recalculate indicators
        self.calculate_indicators()

        # Update current price
        self.current_price = float(new_close)
        self.price_updated.emit(self.current_price)

        # Update indicators
        if not np.isnan(self.df["sma_20"].iloc[-1]):
            self.indicator_updated.emit("SMA20", float(self.df["sma_20"].iloc[-1]))
        if not np.isnan(self.df["vwap"].iloc[-1]):
            self.indicator_updated.emit("VWAP", float(self.df["vwap"].iloc[-1]))

    def refresh_chart_data(self):
        """Refresh the entire chart with latest data."""
        # Recreate chart with updated data
        self.create_initial_chart()

    def toggle_indicator(self, indicator: str, enabled: bool):
        """Toggle technical indicator on/off."""
        if indicator in self.indicators:
            self.indicators[indicator]["enabled"] = enabled
            self.create_initial_chart()  # Recreate chart with updated indicators

    def change_timeframe(self, timeframe: str):
        """Change chart timeframe."""
        # Regenerate sample data with new timeframe
        freq_map = {"1min": "1T", "5min": "5T", "15min": "15T", "1h": "1H", "1d": "1D"}

        if timeframe in freq_map:
            periods = 100
            dates = pd.date_range(
                end=datetime.datetime.now(), periods=periods, freq=freq_map[timeframe]
            )

            # Regenerate data with new frequency
            np.random.seed(42)
            base_price = 585.0
            price_changes = np.random.normal(
                0, 0.5 if "min" in timeframe else 2.0, periods
            ).cumsum()

            opens = base_price + price_changes
            closes = opens + np.random.normal(
                0, 0.3 if "min" in timeframe else 1.0, periods
            )
            highs = np.maximum(opens, closes) + np.random.exponential(
                0.2 if "min" in timeframe else 0.8, periods
            )
            lows = np.minimum(opens, closes) - np.random.exponential(
                0.2 if "min" in timeframe else 0.8, periods
            )
            volumes = np.random.normal(2000000, 500000, periods).astype(int)

            self.df = pd.DataFrame(
                {
                    "datetime": dates,
                    "open": opens,
                    "high": highs,
                    "low": lows,
                    "close": closes,
                    "volume": volumes,
                }
            )

            self.calculate_indicators()
            self.create_initial_chart()

    def refresh_chart(self):
        """Manual chart refresh."""
        self.create_initial_chart()

    def setup_fallback_widget(self):
        """Setup fallback widget when WebEngine or Plotly not available."""
        layout = QVBoxLayout()

        error_label = QLabel("📊 Chart Widget - Dependencies Missing")
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLOR_WARNING};
                font-size: 16px;
                font-weight: bold;
                padding: 20px;
                background-color: {COLOR_PANEL};
                border: 2px dashed {COLOR_BORDER};
                border-radius: 10px;
            }}
        """
        )
        layout.addWidget(error_label)

        details_label = QLabel(
            "Missing dependencies:\n"
            + ("• PySide6-WebEngine not available\n" if not WEBENGINE_AVAILABLE else "")
            + ("• Plotly not available\n" if not PLOTLY_AVAILABLE else "")
            + "\nInstall with:\n"
            + "pip install PySide6-WebEngine plotly"
        )
        details_label.setAlignment(Qt.AlignCenter)
        details_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: 12px; padding: 10px;"
        )
        layout.addWidget(details_label)

        self.setLayout(layout)

    def get_current_price(self) -> float:
        """Get current price."""
        return self.current_price

    def add_trade_marker(
        self, timestamp: datetime.datetime, price: float, trade_type: str, size: int = 1
    ):
        """Add trade marker to chart (placeholder for compatibility)."""
        # This would require JavaScript bridge to add annotations to Plotly chart
        logging.info(f"Trade marker: {trade_type} {size} @ {price} at {timestamp}")

    def clear_chart(self):
        """Clear chart data."""
        self.df = None
        if hasattr(self, "web_view"):
            self.web_view.setHtml("<html><body><h3>Chart Cleared</h3></body></html>")


# ==============================================================================
# MODULE INITIALIZATION & TESTING
# ==============================================================================
if __name__ == "__main__":
    """Test the Plotly chart widget."""
    app = QApplication(sys.argv)

    # Create and show the chart widget
    chart = PlotlyChartWidget()
    chart.setWindowTitle("Spyder Plotly Chart Widget Test")
    chart.resize(1200, 800)
    chart.show()

    # Test data updates
    def test_updates():
        print("Testing real-time updates...")

    QTimer.singleShot(5000, test_updates)

    sys.exit(app.exec())
