#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG04_ChartWidget.py
Purpose: SPYDER - Automated SPY Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    SPYDER - Automated SPY Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import datetime
from collections import deque
from dataclasses import dataclass
import sys
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import numpy as np

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS - UPDATED TO PYQT6
# ==============================================================================
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, \
    QCheckBox, QSplitter, QMenu, QApplication, QComboBox
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction
import logging
try:
    import pyqtgraph as pg

    pg.setConfigOptions(antialias=True)
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False
    logging.info("Warning: pyqtgraph not available. Install with: pip install pyqtgraph")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderA_Core.SpyderA05_EventManager import Event, EventType
except ImportError as e:
    logging.info(f"Warning: Cannot import Spyder modules: {e}")
    logging.info("Creating fallback logger...")

    # Create fallback logger
    import logging

    class FallbackLogger:
        def __init__(self, name):
            self.logger = logging.getLogger(name)
            self.logger.setLevel(logging.INFO)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)

        @classmethod
        def get_logger(cls, name):
            return cls(name).logger

    SpyderLogger = FallbackLogger

    # Create fallback Event classes
    class EventType:
        MARKET_DATA = "market_data"
        PRICE = "price"
        TRADE = "trade"

    class Event:
        def __init__(self, event_type, data=None):
            self.type = event_type
            self.data = data or {}

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Chart settings
MAX_CANDLES = 500
UPDATE_INTERVAL = 1000  # milliseconds
DEFAULT_TIMEFRAME = "5min"
CHART_REFRESH_RATE = 30  # FPS

# Color scheme
BACKGROUND_COLOR = "#1e1e1e"
GRID_COLOR = "#3d3d3d"
TEXT_COLOR = "#ffffff"
BULL_COLOR = "#00ff00"
BEAR_COLOR = "#ff0000"
VOLUME_COLOR = "#4d4d4d"
CROSSHAIR_COLOR = "#ffff00"

# Indicator colors
MA_COLORS = ["#00ffff", "#ff00ff", "#ffff00", "#00ff00"]
BB_COLOR = "#ffffff"
RSI_OVERBOUGHT_COLOR = "#ff0000"
RSI_OVERSOLD_COLOR = "#00ff00"
MACD_LINE_COLOR = "#00ff00"
MACD_SIGNAL_COLOR = "#ff0000"
MACD_HISTOGRAM_COLOR = "#4d4d4d"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ChartStyle:
    """Chart visual style configuration"""

    background_color: str = BACKGROUND_COLOR
    grid_color: str = GRID_COLOR
    text_color: str = TEXT_COLOR
    bull_color: str = BULL_COLOR
    bear_color: str = BEAR_COLOR
    volume_color: str = VOLUME_COLOR
    font_family: str = "Arial"
    font_size: int = 10


@dataclass
class DrawingTool:
    """Drawing tool data"""

    tool_type: str  # 'line', 'hline', 'vline', 'rectangle', 'fibonacci'
    points: list[tuple[float, float]]
    color: str
    width: int
    style: Qt.PenStyle


# ==============================================================================
# MAIN CHART WIDGET CLASS
# ==============================================================================
class ChartWidget(QWidget):
    """
    Interactive price chart widget with technical indicators.

    Features:
    - Real-time candlestick charts
    - Multiple timeframes
    - Technical indicators (MA, RSI, MACD, BB, etc.)
    - Volume profile with delta analysis
    - Option chain visualization overlay
    - Drawing tools (lines, levels, fibonacci)
    - Trade execution markers
    - Multi-chart layout support
    - Chart templates save/load
    """

    # Signals
    timeframe_changed = Signal(str)
    indicator_toggled = Signal(str, bool)
    drawing_completed = Signal(dict)
    chart_clicked = Signal(float, float)  # price, time

    def __init__(self, event_manager=None, parent=None):
        super().__init__(parent)
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)

        # Data storage
        self.price_data = deque(maxlen=MAX_CANDLES)
        self.volume_data = deque(maxlen=MAX_CANDLES)
        self.indicators = {}
        self.current_price = 0.0
        self.session_high = 0.0
        self.session_low = float("inf")

        # Chart components
        self.main_plot = None
        self.volume_plot = None
        self.rsi_plot = None
        self.macd_plot = None
        self.indicator_plots = {}
        self.price_items = {}
        self.trade_markers = []
        self.drawings = []

        # Settings
        self.timeframe = DEFAULT_TIMEFRAME
        self.show_volume = True
        self.show_extended_hours = False
        self.auto_scroll = True
        self.active_indicators = set()
        self.chart_style = ChartStyle()

        # Drawing tools
        self.current_drawing_tool = None
        self.drawing_in_progress = False
        self.drawing_points = []

        # Setup UI
        self.setup_ui()

        # Setup timers
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_charts)
        self.update_timer.start(UPDATE_INTERVAL)

        # Register event handlers
        if self.event_manager:
            self._register_event_handlers()

        self.logger.info("ChartWidget initialized")

    # ==========================================================================
    # UI SETUP METHODS
    # ==========================================================================
    def setup_ui(self):
        """Setup the complete chart UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Top toolbar
        toolbar = self._create_toolbar()
        layout.addWidget(toolbar)

        if PYQTGRAPH_AVAILABLE:
            # Create main chart area
            self.chart_splitter = QSplitter(Qt.Orientation.Vertical)

            # Price chart - create the widget properly
            self.price_widget = pg.PlotWidget(
                title="SPY Price Chart", labels={"left": "Price ($)", "bottom": "Time"}
            )

            # Configure the chart
            self.price_widget.setBackground("k")
            self.price_widget.showGrid(x=True, y=True, alpha=0.3)
            self.price_widget.setLabel("left", "Price", units="$")
            self.price_widget.setLabel("bottom", "Time")

            # Set up the main plot
            self.main_plot = self.price_widget.plotItem

            # Setup crosshair after main_plot is available
            self._setup_crosshair()

            # Setup mouse events
            self._setup_mouse_events()

            # Add to splitter
            self.chart_splitter.addWidget(self.price_widget)

            # Indicator charts container
            self.indicator_container = QWidget()
            self.indicator_layout = QVBoxLayout(self.indicator_container)
            self.indicator_layout.setContentsMargins(0, 0, 0, 0)
            self.chart_splitter.addWidget(self.indicator_container)

            # Set initial sizes
            self.chart_splitter.setSizes([600, 200])

            layout.addWidget(self.chart_splitter)
        else:
            # Fallback UI
            self._create_fallback_ui(layout)

        self.setLayout(layout)

    def _create_toolbar(self):
        """Create comprehensive toolbar"""
        toolbar = QWidget()
        toolbar.setMaximumHeight(40)
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 0, 5, 0)

        # Timeframe selector
        layout.addWidget(QLabel("Timeframe:"))
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(
            [
                "1min",
                "3min",
                "5min",
                "15min",
                "30min",
                "1hour",
                "4hour",
                "1day",
                "1week",
            ]
        )
        self.timeframe_combo.setCurrentText(self.timeframe)
        self.timeframe_combo.currentTextChanged.connect(self._on_timeframe_changed)
        layout.addWidget(self.timeframe_combo)

        # Separator
        layout.addWidget(self._create_separator())

        # Chart type
        layout.addWidget(QLabel("Type:"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Candles", "OHLC", "Line", "Heikin Ashi"])
        self.chart_type_combo.currentTextChanged.connect(self._on_chart_type_changed)
        layout.addWidget(self.chart_type_combo)

        # Separator
        layout.addWidget(self._create_separator())

        # Indicators dropdown
        self.indicators_btn = QPushButton("Indicators")
        self.indicators_menu = self._create_indicators_menu()
        self.indicators_btn.setMenu(self.indicators_menu)
        layout.addWidget(self.indicators_btn)

        # Drawing tools
        self.drawing_btn = QPushButton("Draw")
        self.drawing_menu = self._create_drawing_menu()
        self.drawing_btn.setMenu(self.drawing_menu)
        layout.addWidget(self.drawing_btn)

        # Separator
        layout.addWidget(self._create_separator())

        # Additional controls
        self.extended_hours_cb = QCheckBox("Extended")
        self.extended_hours_cb.toggled.connect(self._toggle_extended_hours)
        layout.addWidget(self.extended_hours_cb)

        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(self.auto_scroll)
        self.auto_scroll_cb.toggled.connect(lambda x: setattr(self, "auto_scroll", x))
        layout.addWidget(self.auto_scroll_cb)

        layout.addStretch()

        # Chart actions
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save_chart)
        layout.addWidget(self.save_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.clicked.connect(self._reset_view)
        layout.addWidget(self.reset_btn)

        toolbar.setLayout(layout)
        return toolbar

    def _setup_crosshair(self):
        """Setup crosshair lines and labels"""
        if not PYQTGRAPH_AVAILABLE or not hasattr(self, "main_plot"):
            return

        try:
            # Create crosshair lines
            self.v_line = pg.InfiniteLine(angle=90, movable=False, pen="y")
            self.h_line = pg.InfiniteLine(angle=0, movable=False, pen="y")

            # Create labels
            self.crosshair_price_label = pg.TextItem(anchor=(0, 1))
            self.crosshair_time_label = pg.TextItem(anchor=(0.5, 0))
            self.info_label = pg.TextItem(anchor=(0, 1))

            # Add to plot
            self.main_plot.addItem(self.v_line, ignoreBounds=True)
            self.main_plot.addItem(self.h_line, ignoreBounds=True)
            self.main_plot.addItem(self.crosshair_price_label, ignoreBounds=True)
            self.main_plot.addItem(self.crosshair_time_label, ignoreBounds=True)
            self.main_plot.addItem(self.info_label, ignoreBounds=True)

        except Exception as e:
            self.logger.error(f"Failed to setup crosshair: {str(e)}")

    def _create_indicators_menu(self):
        """Create indicators selection menu"""
        menu = QMenu()

        # Moving Averages
        ma_menu = menu.addMenu("Moving Averages")
        for period in [9, 20, 50, 200]:
            action = QAction(f"SMA {period}", self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, p=period: self._toggle_ma(f"SMA{p}", checked, p)
            )
            ma_menu.addAction(action)

        ma_menu.addSeparator()
        for period in [9, 20, 50]:
            action = QAction(f"EMA {period}", self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, p=period: self._toggle_ma(f"EMA{p}", checked, p)
            )
            ma_menu.addAction(action)

        # Oscillators
        osc_menu = menu.addMenu("Oscillators")

        rsi_action = QAction("RSI (14)", self)
        rsi_action.setCheckable(True)
        rsi_action.triggered.connect(
            lambda checked: self._toggle_indicator("RSI", checked)
        )
        osc_menu.addAction(rsi_action)

        macd_action = QAction("MACD", self)
        macd_action.setCheckable(True)
        macd_action.triggered.connect(
            lambda checked: self._toggle_indicator("MACD", checked)
        )
        osc_menu.addAction(macd_action)

        stoch_action = QAction("Stochastic", self)
        stoch_action.setCheckable(True)
        stoch_action.triggered.connect(
            lambda checked: self._toggle_indicator("STOCH", checked)
        )
        osc_menu.addAction(stoch_action)

        # Volatility
        vol_menu = menu.addMenu("Volatility")

        bb_action = QAction("Bollinger Bands", self)
        bb_action.setCheckable(True)
        bb_action.triggered.connect(
            lambda checked: self._toggle_indicator("BB", checked)
        )
        vol_menu.addAction(bb_action)

        atr_action = QAction("ATR", self)
        atr_action.setCheckable(True)
        atr_action.triggered.connect(
            lambda checked: self._toggle_indicator("ATR", checked)
        )
        vol_menu.addAction(atr_action)

        # Volume
        vol_menu = menu.addMenu("Volume")

        vwap_action = QAction("VWAP", self)
        vwap_action.setCheckable(True)
        vwap_action.triggered.connect(
            lambda checked: self._toggle_indicator("VWAP", checked)
        )
        vol_menu.addAction(vwap_action)

        obv_action = QAction("OBV", self)
        obv_action.setCheckable(True)
        obv_action.triggered.connect(
            lambda checked: self._toggle_indicator("OBV", checked)
        )
        vol_menu.addAction(obv_action)

        return menu

    def _create_drawing_menu(self):
        """Create drawing tools menu"""
        menu = QMenu()

        # Lines
        line_action = QAction("Trend Line", self)
        line_action.triggered.connect(lambda: self._select_drawing_tool("line"))
        menu.addAction(line_action)

        hline_action = QAction("Horizontal Line", self)
        hline_action.triggered.connect(lambda: self._select_drawing_tool("hline"))
        menu.addAction(hline_action)

        vline_action = QAction("Vertical Line", self)
        vline_action.triggered.connect(lambda: self._select_drawing_tool("vline"))
        menu.addAction(vline_action)

        menu.addSeparator()

        # Shapes
        rect_action = QAction("Rectangle", self)
        rect_action.triggered.connect(lambda: self._select_drawing_tool("rectangle"))
        menu.addAction(rect_action)

        # Fibonacci
        fib_action = QAction("Fibonacci Retracement", self)
        fib_action.triggered.connect(lambda: self._select_drawing_tool("fibonacci"))
        menu.addAction(fib_action)

        menu.addSeparator()

        # Clear
        clear_action = QAction("Clear All Drawings", self)
        clear_action.triggered.connect(self._clear_drawings)
        menu.addAction(clear_action)

        return menu

    def _create_separator(self):
        """Create vertical separator"""
        sep = QLabel("|")
        sep.setStyleSheet("color: #666;")
        return sep

    def _create_fallback_ui(self, layout):
        """Create fallback UI when pyqtgraph not available"""
        fallback_label = QLabel(
            "Chart visualization requires pyqtgraph\n"
            "Install with: pip install pyqtgraph"
        )
        fallback_label.setAlignment(Qt.AlignCenter)
        fallback_label.setStyleSheet("color: #ff0000; font-size: 14px; padding: 50px;")
        layout.addWidget(fallback_label)

    # ==========================================================================
    # DATA MANAGEMENT
    # ==========================================================================
    def add_price_data(
        self,
        timestamp: datetime.datetime,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: int,
    ):
        """Add new price candle"""
        candle = {
            "timestamp": timestamp,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }

        self.price_data.append(candle)
        self.current_price = close

        # Update session high/low
        self.session_high = max(self.session_high, high)
        self.session_low = min(self.session_low, low)

        # Update indicators
        self._update_indicators()

        # Auto-update chart if enabled
        if self.auto_scroll and len(self.price_data) % 5 == 0:
            self.update_charts()

    def update_current_price(self, price: float):
        """Update current price marker"""
        self.current_price = price

        if PYQTGRAPH_AVAILABLE and self.main_plot:
            # Update or create current price line
            if "current_price" in self.price_items:
                self.price_items["current_price"].setValue(price)
                self.price_items["current_price"].label.setText(f"${price:.2f}")
            else:
                self.price_items["current_price"] = pg.InfiniteLine(
                    angle=0,
                    pos=price,
                    pen=pg.mkPen(color="y", width=2, style=Qt.PenStyle.DashLine),
                    label=f"${price:.2f}",
                    labelOpts={"position": 0.95, "color": "y"},
                )
                self.main_plot.addItem(self.price_items["current_price"])

    def update_charts(self):
        """Update all chart components"""
        if not PYQTGRAPH_AVAILABLE or not self.price_data:
            return

        try:
            # Draw main chart
            self._draw_price_chart()

            # Draw volume
            if self.show_volume:
                self._draw_volume_chart()

            # Draw indicators
            self._draw_all_indicators()

            # Update current price
            self.update_current_price(self.current_price)

            # Auto-range if enabled
            if self.auto_scroll:
                self._auto_range_visible()

        except Exception as e:
            self.logger.error(f"Error updating charts: {e}")

    def _draw_price_chart(self):
        """Draw price candles/bars"""
        if not hasattr(self, 'main_plot') or self.main_plot is None:
            return

        self.main_plot.clear()

        # Re-add persistent items
        if hasattr(self, 'v_line'):
            self.main_plot.addItem(self.v_line, ignoreBounds=True)
        if hasattr(self, 'h_line'):
            self.main_plot.addItem(self.h_line, ignoreBounds=True)
        if hasattr(self, 'crosshair_price_label'):
            self.main_plot.addItem(self.crosshair_price_label, ignoreBounds=True)
        if hasattr(self, 'crosshair_time_label'):
            self.main_plot.addItem(self.crosshair_time_label, ignoreBounds=True)
        if hasattr(self, 'info_label'):
            self.main_plot.addItem(self.info_label, ignoreBounds=True)

        # Prepare data
        timestamps = list(range(len(self.price_data)))

        # Draw based on chart type
        chart_type = self.chart_type_combo.currentText()

        if chart_type == "Candles":
            self._draw_candlesticks(timestamps)
        elif chart_type == "OHLC":
            self._draw_ohlc_bars(timestamps)
        elif chart_type == "Line":
            self._draw_line_chart(timestamps)
        elif chart_type == "Heikin Ashi":
            self._draw_heikin_ashi(timestamps)

        # Re-add trade markers
        for marker in self.trade_markers:
            self.main_plot.addItem(marker)

        # Re-add drawings
        for drawing in self.drawings:
            self._redraw_drawing(drawing)

    def _draw_candlesticks(self, timestamps):
        """Draw candlestick chart"""
        for i, candle in enumerate(self.price_data):
            color = (
                self.chart_style.bull_color
                if candle["close"] >= candle["open"]
                else self.chart_style.bear_color
            )

            # High-Low line
            high_low = pg.PlotDataItem(
                [i, i],
                [candle["low"], candle["high"]],
                pen=pg.mkPen(color=color, width=1),
            )
            self.main_plot.addItem(high_low)

            # Open-Close body
            body_height = abs(candle["close"] - candle["open"])
            if body_height > 0:
                body = pg.BarGraphItem(
                    x=[i],
                    height=[body_height],
                    y=[min(candle["open"], candle["close"])],
                    width=0.6,
                    brush=pg.mkBrush(color=color),
                    pen=pg.mkPen(color=color),
                )
                self.main_plot.addItem(body)

    def _draw_ohlc_bars(self, timestamps):
        """Draw OHLC bars"""
        # Placeholder implementation
        pass

    def _draw_line_chart(self, timestamps):
        """Draw line chart"""
        if not self.price_data:
            return

        closes = [candle["close"] for candle in self.price_data]
        self.main_plot.plot(timestamps, closes, pen=pg.mkPen(color="yellow", width=2))

    def _draw_heikin_ashi(self, timestamps):
        """Draw Heikin Ashi candles"""
        # Placeholder implementation
        pass

    def _draw_volume_chart(self):
        """Draw volume bars with buy/sell pressure"""
        if not hasattr(self, 'volume_plot') or self.volume_plot is None:
            return

        self.volume_plot.clear()

        volumes = []
        colors = []

        for _i, candle in enumerate(self.price_data):
            volumes.append(candle["volume"])
            # Color based on price action
            if candle["close"] >= candle["open"]:
                colors.append(self.chart_style.bull_color)
            else:
                colors.append(self.chart_style.bear_color)

        # Create volume bars
        volume_bars = pg.BarGraphItem(
            x=range(len(volumes)),
            height=volumes,
            width=0.8,
            brushes=colors,
            pens=colors,
        )
        self.volume_plot.addItem(volume_bars)

    # ==========================================================================
    # INDICATOR CALCULATIONS
    # ==========================================================================
    def _update_indicators(self):
        """Update all active indicators"""
        if len(self.price_data) < 20:
            return

        closes = np.array([c["close"] for c in self.price_data])
        highs = np.array([c["high"] for c in self.price_data])
        lows = np.array([c["low"] for c in self.price_data])
        volumes = np.array([c["volume"] for c in self.price_data])

        # Update each active indicator
        for indicator in self.active_indicators:
            if indicator.startswith("SMA"):
                period = int(indicator[3:])
                self.indicators[indicator] = self._calculate_sma(closes, period)
            elif indicator.startswith("EMA"):
                period = int(indicator[3:])
                self.indicators[indicator] = self._calculate_ema(closes, period)
            elif indicator == "RSI":
                self.indicators["RSI"] = self._calculate_rsi(closes)
            elif indicator == "MACD":
                (
                    self.indicators["MACD"],
                    self.indicators["MACD_signal"],
                    self.indicators["MACD_hist"],
                ) = self._calculate_macd(closes)
            elif indicator == "BB":
                (
                    self.indicators["BB_upper"],
                    self.indicators["BB_middle"],
                    self.indicators["BB_lower"],
                ) = self._calculate_bollinger_bands(closes)
            elif indicator == "VWAP":
                self.indicators["VWAP"] = self._calculate_vwap(
                    closes, volumes, highs, lows
                )
            elif indicator == "ATR":
                self.indicators["ATR"] = self._calculate_atr(highs, lows, closes)
            elif indicator == "STOCH":
                self.indicators["STOCH_K"], self.indicators["STOCH_D"] = (
                    self._calculate_stochastic(highs, lows, closes)
                )
            elif indicator == "OBV":
                self.indicators["OBV"] = self._calculate_obv(closes, volumes)

    def _calculate_sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Simple Moving Average"""
        if len(data) < period:
            return np.array([])
        return np.convolve(data, np.ones(period) / period, mode="valid")

    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Exponential Moving Average"""
        if len(data) < period:
            return np.array([])

        ema = np.zeros_like(data)
        ema[:period] = data[:period].mean()

        multiplier = 2 / (period + 1)
        for i in range(period, len(data)):
            ema[i] = (data[i] - ema[i - 1]) * multiplier + ema[i - 1]

        return ema[period - 1 :]

    def _calculate_rsi(self, data: np.ndarray, period: int = 14) -> np.ndarray:
        """Relative Strength Index"""
        if len(data) < period + 1:
            return np.array([])

        deltas = np.diff(data)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gains = np.zeros(len(gains))
        avg_losses = np.zeros(len(losses))

        avg_gains[period - 1] = gains[:period].mean()
        avg_losses[period - 1] = losses[:period].mean()

        for i in range(period, len(gains)):
            avg_gains[i] = (avg_gains[i - 1] * (period - 1) + gains[i]) / period
            avg_losses[i] = (avg_losses[i - 1] * (period - 1) + losses[i]) / period

        rs = avg_gains / (avg_losses + 1e-10)
        rsi = 100 - (100 / (1 + rs))

        return rsi[period - 1 :]

    def _calculate_macd(self, data: np.ndarray, fast=12, slow=26, signal=9):
        """MACD indicator"""
        if len(data) < slow:
            return np.array([]), np.array([]), np.array([])

        ema_fast = self._calculate_ema(data, fast)
        ema_slow = self._calculate_ema(data, slow)

        # Align arrays
        diff = len(ema_slow) - len(ema_fast)
        if diff > 0:
            ema_fast = ema_fast[diff:]

        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, signal)

        # Align for histogram
        diff = len(macd_line) - len(signal_line)
        if diff > 0:
            macd_line_aligned = macd_line[diff:]
        else:
            macd_line_aligned = macd_line

        histogram = macd_line_aligned - signal_line

        return macd_line[diff:], signal_line, histogram

    def _calculate_bollinger_bands(
        self, data: np.ndarray, period: int = 20, std_dev: int = 2
    ):
        """Bollinger Bands"""
        if len(data) < period:
            return np.array([]), np.array([]), np.array([])

        middle = self._calculate_sma(data, period)
        std = np.array(
            [
                data[max(0, i - period + 1) : i + 1].std()
                for i in range(period - 1, len(data))
            ]
        )

        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)

        return upper, middle, lower

    def _calculate_vwap(
        self,
        closes: np.ndarray,
        volumes: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
    ) -> np.ndarray:
        """Volume Weighted Average Price"""
        typical_price = (highs + lows + closes) / 3
        cumulative_tpv = np.cumsum(typical_price * volumes)
        cumulative_volume = np.cumsum(volumes)

        vwap = cumulative_tpv / (cumulative_volume + 1e-10)
        return vwap

    def _calculate_atr(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
    ) -> np.ndarray:
        """Average True Range"""
        if len(highs) < period + 1:
            return np.array([])

        # True Range
        high_low = highs[1:] - lows[1:]
        high_close = np.abs(highs[1:] - closes[:-1])
        low_close = np.abs(lows[1:] - closes[:-1])

        true_range = np.maximum(high_low, np.maximum(high_close, low_close))

        # ATR
        atr = np.zeros(len(true_range))
        atr[period - 1] = true_range[:period].mean()

        for i in range(period, len(true_range)):
            atr[i] = (atr[i - 1] * (period - 1) + true_range[i]) / period

        return atr[period - 1 :]

    def _calculate_stochastic(
        self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14
    ) -> tuple[np.ndarray, np.ndarray]:
        """Stochastic Oscillator"""
        if len(closes) < period:
            return np.array([]), np.array([])

        k_values = []
        for i in range(period - 1, len(closes)):
            high_period = highs[i - period + 1 : i + 1].max()
            low_period = lows[i - period + 1 : i + 1].min()

            if high_period > low_period:
                k = 100 * (closes[i] - low_period) / (high_period - low_period)
            else:
                k = 50

            k_values.append(k)

        k_values = np.array(k_values)
        d_values = self._calculate_sma(k_values, 3)  # 3-period SMA of %K

        return k_values, d_values

    def _calculate_obv(self, closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
        """On Balance Volume"""
        obv = np.zeros(len(closes))
        obv[0] = volumes[0]

        for i in range(1, len(closes)):
            if closes[i] > closes[i - 1]:
                obv[i] = obv[i - 1] + volumes[i]
            elif closes[i] < closes[i - 1]:
                obv[i] = obv[i - 1] - volumes[i]
            else:
                obv[i] = obv[i - 1]

        return obv

    # ==========================================================================
    # INDICATOR DRAWING
    # ==========================================================================
    def _draw_all_indicators(self):
        """Draw all active indicators"""
        timestamps = list(range(len(self.price_data)))

        # Draw overlays on main chart
        self._draw_moving_averages(timestamps)
        self._draw_bollinger_bands(timestamps)
        self._draw_vwap(timestamps)

        # Draw oscillators in separate panes
        self._draw_rsi()
        self._draw_macd()
        self._draw_stochastic()

    def _draw_moving_averages(self, timestamps):
        """Draw moving average lines"""
        for i, indicator in enumerate(
            ["SMA9", "SMA20", "SMA50", "SMA200", "EMA9", "EMA20", "EMA50"]
        ):
            if indicator in self.active_indicators and indicator in self.indicators:
                data = self.indicators[indicator]
                if len(data) > 0:
                    # Align with timestamps
                    offset = len(timestamps) - len(data)
                    x = timestamps[offset:]

                    color = MA_COLORS[i % len(MA_COLORS)]
                    self.main_plot.plot(
                        x, data, pen=pg.mkPen(color=color, width=2), name=indicator
                    )

    def _draw_bollinger_bands(self, timestamps):
        """Draw Bollinger Bands"""
        if "BB" in self.active_indicators and "BB_upper" in self.indicators:
            upper = self.indicators["BB_upper"]
            middle = self.indicators["BB_middle"]
            lower = self.indicators["BB_lower"]

            if len(upper) > 0:
                offset = len(timestamps) - len(upper)
                x = timestamps[offset:]

                # Upper band
                self.main_plot.plot(
                    x,
                    upper,
                    pen=pg.mkPen(color=BB_COLOR, width=1, style=Qt.PenStyle.DashLine),
                    name="BB Upper",
                )

                # Middle band
                self.main_plot.plot(
                    x, middle, pen=pg.mkPen(color=BB_COLOR, width=1), name="BB Middle"
                )

                # Lower band
                self.main_plot.plot(
                    x,
                    lower,
                    pen=pg.mkPen(color=BB_COLOR, width=1, style=Qt.PenStyle.DashLine),
                    name="BB Lower",
                )

                # Fill between bands
                fill = pg.FillBetweenItem(
                    pg.PlotDataItem(x, upper),
                    pg.PlotDataItem(x, lower),
                    brush=pg.mkBrush(255, 255, 255, 20),
                )
                self.main_plot.addItem(fill)

    def _draw_vwap(self, timestamps):
        """Draw VWAP line"""
        if "VWAP" in self.active_indicators and "VWAP" in self.indicators:
            vwap = self.indicators["VWAP"]
            if len(vwap) > 0:
                self.main_plot.plot(
                    timestamps[: len(vwap)],
                    vwap,
                    pen=pg.mkPen(color="orange", width=2),
                    name="VWAP",
                )

    def _draw_rsi(self):
        """Draw RSI in separate pane"""
        if "RSI" not in self.active_indicators or "RSI" not in self.indicators:
            return

        # Create RSI plot if not exists
        if not hasattr(self, "rsi_plot") or self.rsi_plot is None:
            self.rsi_plot = pg.PlotWidget()
            self._setup_plot(self.rsi_plot, "RSI", "")
            self.indicator_layout.addWidget(self.rsi_plot)

        self.rsi_plot.clear()

        rsi = self.indicators["RSI"]
        if len(rsi) > 0:
            timestamps = list(range(len(self.price_data)))
            offset = len(timestamps) - len(rsi)
            x = timestamps[offset:]

            # RSI line
            self.rsi_plot.plot(x, rsi, pen=pg.mkPen(color="cyan", width=2))

            # Overbought/oversold levels
            self.rsi_plot.addLine(
                y=70, pen=pg.mkPen(RSI_OVERBOUGHT_COLOR, width=1, style=Qt.PenStyle.DashLine)
            )
            self.rsi_plot.addLine(
                y=30, pen=pg.mkPen(RSI_OVERSOLD_COLOR, width=1, style=Qt.PenStyle.DashLine)
            )

            # Fill zones
            self.rsi_plot.plot(
                x, [70] * len(x), fillLevel=100, brush=pg.mkBrush(255, 0, 0, 30)
            )
            self.rsi_plot.plot(
                x, [30] * len(x), fillLevel=0, brush=pg.mkBrush(0, 255, 0, 30)
            )

    def _draw_macd(self):
        """Draw MACD in separate pane"""
        if "MACD" not in self.active_indicators or "MACD" not in self.indicators:
            return

        # Create MACD plot if not exists
        if not hasattr(self, "macd_plot") or self.macd_plot is None:
            self.macd_plot = pg.PlotWidget()
            self._setup_plot(self.macd_plot, "MACD", "")
            self.indicator_layout.addWidget(self.macd_plot)

        self.macd_plot.clear()

        macd = self.indicators.get("MACD", np.array([]))
        signal = self.indicators.get("MACD_signal", np.array([]))
        hist = self.indicators.get("MACD_hist", np.array([]))

        if len(hist) > 0:
            timestamps = list(range(len(self.price_data)))
            offset = len(timestamps) - len(hist)
            x = timestamps[offset:]

            # Histogram
            colors = [
                self.chart_style.bull_color if h > 0 else self.chart_style.bear_color
                for h in hist
            ]
            hist_bars = pg.BarGraphItem(x=x, height=hist, width=0.8, brushes=colors)
            self.macd_plot.addItem(hist_bars)

            # MACD and Signal lines
            if len(macd) >= len(hist):
                macd_offset = len(macd) - len(hist)
                self.macd_plot.plot(
                    x,
                    macd[macd_offset:],
                    pen=pg.mkPen(MACD_LINE_COLOR, width=2),
                    name="MACD",
                )

            self.macd_plot.plot(
                x, signal, pen=pg.mkPen(MACD_SIGNAL_COLOR, width=2), name="Signal"
            )

            # Zero line
            self.macd_plot.addLine(
                y=0, pen=pg.mkPen("white", width=1, style=Qt.PenStyle.DashLine)
            )

    def _draw_stochastic(self):
        """Draw Stochastic in separate pane"""
        if "STOCH" not in self.active_indicators:
            return

        k_values = self.indicators.get("STOCH_K", np.array([]))
        d_values = self.indicators.get("STOCH_D", np.array([]))

        if len(k_values) == 0:
            return

        # Create Stochastic plot if not exists
        if not hasattr(self, "stoch_plot") or self.stoch_plot is None:
            self.stoch_plot = pg.PlotWidget()
            self._setup_plot(self.stoch_plot, "Stochastic", "%")
            self.indicator_layout.addWidget(self.stoch_plot)

        self.stoch_plot.clear()

        timestamps = list(range(len(self.price_data)))
        offset = len(timestamps) - len(k_values)
        x = timestamps[offset:]

        # %K line
        self.stoch_plot.plot(x, k_values, pen=pg.mkPen("cyan", width=2), name="%K")

        # %D line
        if len(d_values) > 0:
            d_offset = len(k_values) - len(d_values)
            self.stoch_plot.plot(
                x[d_offset:], d_values, pen=pg.mkPen("orange", width=2), name="%D"
            )

        # Overbought/oversold levels
        self.stoch_plot.addLine(
            y=80, pen=pg.mkPen(RSI_OVERBOUGHT_COLOR, width=1, style=Qt.PenStyle.DashLine)
        )
        self.stoch_plot.addLine(
            y=20, pen=pg.mkPen(RSI_OVERSOLD_COLOR, width=1, style=Qt.PenStyle.DashLine)
        )

    # ==========================================================================
    # DRAWING TOOLS
    # ==========================================================================
    def _select_drawing_tool(self, tool_type: str):
        """Select a drawing tool"""
        self.current_drawing_tool = tool_type
        self.drawing_points = []
        self.drawing_in_progress = True

        # Change cursor
        if PYQTGRAPH_AVAILABLE:
            self.price_widget.setCursor(Qt.CursorShape.CrossCursor)

        self.logger.info(f"Selected drawing tool: {tool_type}")

    def _on_mouse_clicked(self, event):
        """Handle mouse click for drawing"""
        if not self.drawing_in_progress or not self.current_drawing_tool:
            return

        pos = event.scenePos()
        mouse_point = self.main_plot.vb.mapSceneToView(pos)

        # Add point
        self.drawing_points.append((mouse_point.x(), mouse_point.y()))

        # Check if drawing is complete
        points_needed = {
            "line": 2,
            "hline": 1,
            "vline": 1,
            "rectangle": 2,
            "fibonacci": 2,
        }

        if len(self.drawing_points) >= points_needed.get(self.current_drawing_tool, 2):
            self._complete_drawing()

    def _complete_drawing(self):
        """Complete the current drawing"""
        if not self.drawing_points:
            return

        # Create drawing object
        drawing = DrawingTool(
            tool_type=self.current_drawing_tool,
            points=self.drawing_points.copy(),
            color="yellow",
            width=2,
            style=Qt.PenStyle.SolidLine,
        )

        # Draw it
        self._draw_tool(drawing)

        # Save drawing
        self.drawings.append(drawing)

        # Reset
        self.current_drawing_tool = None
        self.drawing_points = []
        self.drawing_in_progress = False

        if PYQTGRAPH_AVAILABLE:
            self.price_widget.setCursor(Qt.CursorShape.ArrowCursor)

        # Emit signal
        self.drawing_completed.emit(
            {"tool": drawing.tool_type, "points": drawing.points}
        )

    def _draw_tool(self, drawing: DrawingTool):
        """Draw a drawing tool on chart"""
        if drawing.tool_type == "line":
            self._draw_trend_line(drawing)
        elif drawing.tool_type == "hline":
            self._draw_horizontal_line(drawing)
        elif drawing.tool_type == "vline":
            self._draw_vertical_line(drawing)
        elif drawing.tool_type == "rectangle":
            self._draw_rectangle(drawing)
        elif drawing.tool_type == "fibonacci":
            self._draw_fibonacci(drawing)

    def _draw_trend_line(self, drawing: DrawingTool):
        """Draw trend line"""
        if len(drawing.points) < 2:
            return

        x = [drawing.points[0][0], drawing.points[1][0]]
        y = [drawing.points[0][1], drawing.points[1][1]]

        line = pg.PlotDataItem(x, y, pen=pg.mkPen(drawing.color, width=drawing.width))
        self.main_plot.addItem(line)

    def _draw_horizontal_line(self, drawing: DrawingTool):
        """Draw horizontal line"""
        if not drawing.points:
            return

        line = pg.InfiniteLine(
            angle=0,
            pos=drawing.points[0][1],
            pen=pg.mkPen(drawing.color, width=drawing.width, style=drawing.style),
        )
        self.main_plot.addItem(line)

    def _draw_vertical_line(self, drawing: DrawingTool):
        """Draw vertical line"""
        if not drawing.points:
            return

        line = pg.InfiniteLine(
            angle=90,
            pos=drawing.points[0][0],
            pen=pg.mkPen(drawing.color, width=drawing.width, style=drawing.style),
        )
        self.main_plot.addItem(line)

    def _draw_rectangle(self, drawing: DrawingTool):
        """Draw rectangle"""
        # Placeholder implementation
        pass

    def _draw_fibonacci(self, drawing: DrawingTool):
        """Draw Fibonacci retracement"""
        if len(drawing.points) < 2:
            return

        # Calculate Fibonacci levels
        y1, y2 = drawing.points[0][1], drawing.points[1][1]
        diff = y2 - y1

        levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]
        colors = ["red", "orange", "yellow", "green", "cyan", "blue", "purple"]

        for level, color in zip(levels, colors, strict=False):
            y = y1 + diff * level
            line = pg.InfiniteLine(
                angle=0,
                pos=y,
                pen=pg.mkPen(color, width=1, style=Qt.PenStyle.DashLine),
                label=f"{level:.1%}",
                labelOpts={"position": 0.02, "color": color},
            )
            self.main_plot.addItem(line)

    def _clear_drawings(self):
        """Clear all drawings"""
        self.drawings.clear()
        self.update_charts()

    def _redraw_drawing(self, drawing: DrawingTool):
        """Redraw a saved drawing"""
        self._draw_tool(drawing)

    # ==========================================================================
    # TRADING FEATURES
    # ==========================================================================
    def add_trade_marker(
        self, timestamp: datetime.datetime, price: float, trade_type: str, quantity: int
    ):
        """Add trade execution marker"""
        if not PYQTGRAPH_AVAILABLE or not self.main_plot:
            return

        # Find x-coordinate
        x = len(self.price_data) - 1
        for i, candle in enumerate(self.price_data):
            if candle["timestamp"] >= timestamp:
                x = i
                break

        # Create marker
        if trade_type.upper() in ["BUY", "BUY TO OPEN"]:
            symbol = "o"
            color = self.chart_style.bull_color
        else:
            symbol = "t"
            color = self.chart_style.bear_color

        # Create scatter plot item
        scatter = pg.ScatterPlotItem(
            [x],
            [price],
            pen=pg.mkPen(None),
            brush=pg.mkBrush(color),
            size=15,
            symbol=symbol,
        )

        # Add label
        label = pg.TextItem(
            text=f"{trade_type}\n{quantity}", anchor=(0.5, 0.5), color=color
        )
        label.setPos(x, price)

        self.main_plot.addItem(scatter)
        self.main_plot.addItem(label)

        # Store for redrawing
        self.trade_markers.extend([scatter, label])

    def add_level_line(
        self, price: float, color: str, label: str, style: Qt.PenStyle = Qt.PenStyle.SolidLine
    ):
        """Add horizontal level line"""
        if not PYQTGRAPH_AVAILABLE or not self.main_plot:
            return

        line = pg.InfiniteLine(
            angle=0,
            pos=price,
            pen=pg.mkPen(color=color, width=2, style=style),
            label=label,
            labelOpts={"position": 0.05, "color": color},
        )

        self.main_plot.addItem(line)
        self.price_items[label] = line

    def highlight_session(
        self,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        color: str,
        label: str,
    ):
        """Highlight a time session"""
        if not PYQTGRAPH_AVAILABLE:
            return

        # Find x-coordinates
        start_x = None
        end_x = None

        for i, candle in enumerate(self.price_data):
            if start_x is None and candle["timestamp"] >= start_time:
                start_x = i
            if candle["timestamp"] >= end_time:
                end_x = i
                break

        if start_x is None or end_x is None:
            return

        # Create region
        region = pg.LinearRegionItem(
            values=(start_x, end_x),
            brush=pg.mkBrush(color + "20"),  # Add transparency
            movable=False,
        )

        self.main_plot.addItem(region)

    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    def _register_event_handlers(self):
        """Register event handlers"""
        # Market data events
        self.event_manager.subscribe(
            self._handle_market_data,
            event_type=EventType.MARKET_DATA,
            subscriber_id="chart_widget",
        )

        # Price updates
        self.event_manager.subscribe(
            self._handle_price_update,
            event_type=EventType.PRICE,
            subscriber_id="chart_price",
        )

        # Trade events
        self.event_manager.subscribe(
            self._handle_trade_event,
            event_type=EventType.TRADE,
            subscriber_id="chart_trades",
        )

    def _handle_market_data(self, event):
        """Handle market data updates."""
        try:
            market_data = event.get("data", {})
            symbol = market_data.get("symbol", "")

            if symbol == "SPY":
                price = market_data.get("last", 0)
                timestamp = market_data.get("timestamp", datetime.datetime.now())
                self.add_price_data(timestamp, price, price, price, price, 0)

        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")

    def _handle_price_update(self, event: Event):
        """Handle price update events"""
        if event.data.get("symbol") == "SPY":
            self.update_current_price(event.data["price"])

    def _handle_trade_event(self, event: Event):
        """Handle trade execution events"""
        self.add_trade_marker(
            timestamp=event.data["timestamp"],
            price=event.data["price"],
            trade_type=event.data["action"],
            quantity=event.data["quantity"],
        )

    def _setup_mouse_events(self):
        """Setup mouse event handlers for the chart."""
        try:
            # Ensure price_widget exists before setting up events
            if not hasattr(self, "price_widget") or self.price_widget is None:
                self.logger.warning("price_widget not available for mouse events")
                return

            if not PYQTGRAPH_AVAILABLE:
                self.logger.warning("PyQtGraph not available, skipping mouse events")
                return

            # Connect mouse move events
            self.price_widget.scene().sigMouseMoved.connect(self._on_mouse_moved)

            # Connect mouse click events
            self.price_widget.scene().sigMouseClicked.connect(self._on_mouse_clicked)

            # Enable crosshair
            self.crosshair_enabled = True

            self.logger.debug("Mouse events setup completed")

        except Exception as e:
            self.logger.error(f"Failed to setup mouse events: {str(e)}")

    def _on_mouse_moved(self, pos):
        """Handle mouse move events."""
        try:
            if not hasattr(self, 'crosshair_enabled') or not self.crosshair_enabled or not hasattr(self, "main_plot"):
                return

            # Get mouse position in plot coordinates
            mouse_point = self.main_plot.vb.mapSceneToView(pos)

            # Update crosshair position
            if hasattr(self, "v_line") and hasattr(self, "h_line"):
                self.v_line.setPos(mouse_point.x())
                self.h_line.setPos(mouse_point.y())

            # Update labels if they exist
            if hasattr(self, "crosshair_price_label"):
                self.crosshair_price_label.setPos(mouse_point.x(), mouse_point.y())
                self.crosshair_price_label.setText(f"${mouse_point.y():.2f}")

        except Exception as e:
            self.logger.error(f"Error in mouse move handler: {str(e)}")

    def _on_timeframe_changed(self, timeframe: str):
        """Handle timeframe change from combo box."""
        try:
            self.timeframe = timeframe
            self.timeframe_changed.emit(timeframe)
            self.logger.info(f"Timeframe changed to: {timeframe}")
        except Exception as e:
            self.logger.error(f"Error changing timeframe: {str(e)}")

    def _on_chart_type_changed(self, chart_type: str):
        """Handle chart type change."""
        try:
            self.update_charts()
            self.logger.info(f"Chart type changed to: {chart_type}")
        except Exception as e:
            self.logger.error(f"Error changing chart type: {str(e)}")

    def _toggle_extended_hours(self, enabled: bool):
        """Toggle extended hours display."""
        try:
            self.show_extended_hours = enabled
            self.update_charts()
            self.logger.info(f"Extended hours: {enabled}")
        except Exception as e:
            self.logger.error(f"Error toggling extended hours: {str(e)}")

    def _toggle_ma(self, ma_name: str, enabled: bool, period: int):
        """Toggle moving average display."""
        try:
            if enabled:
                self.active_indicators.add(ma_name)
            else:
                self.active_indicators.discard(ma_name)

            self._update_indicators()
            self.update_charts()
            self.indicator_toggled.emit(ma_name, enabled)
            self.logger.info(f"Moving average {ma_name}: {enabled}")
        except Exception as e:
            self.logger.error(f"Error toggling MA {ma_name}: {str(e)}")

    def _toggle_indicator(self, indicator_name: str, enabled: bool):
        """Toggle indicator display."""
        try:
            if enabled:
                self.active_indicators.add(indicator_name)
            else:
                self.active_indicators.discard(indicator_name)

            self._update_indicators()
            self.update_charts()
            self.indicator_toggled.emit(indicator_name, enabled)
            self.logger.info(f"Indicator {indicator_name}: {enabled}")
        except Exception as e:
            self.logger.error(f"Error toggling indicator {indicator_name}: {str(e)}")

    def _save_chart(self):
        """Save chart as image."""
        try:
            if PYQTGRAPH_AVAILABLE and hasattr(self, "price_widget"):
                exporter = pg.exporters.ImageExporter(self.price_widget.plotItem)
                exporter.export("chart.png")
                self.logger.info("Chart saved as chart.png")
        except Exception as e:
            self.logger.error(f"Error saving chart: {str(e)}")

    def _reset_view(self):
        """Reset chart view to default."""
        try:
            if hasattr(self, "price_widget") and self.price_widget:
                self.price_widget.autoRange()
            self.logger.info("Chart view reset")
        except Exception as e:
            self.logger.error(f"Error resetting view: {str(e)}")

    def _setup_plot(self, plot_widget, title: str, y_label: str):
        """Setup common plot properties."""
        try:
            plot_widget.setBackground("k")
            plot_widget.showGrid(x=True, y=True, alpha=0.3)
            plot_widget.setLabel("left", y_label)
            plot_widget.setLabel("bottom", "Time")
            plot_widget.setTitle(title)
        except Exception as e:
            self.logger.error(f"Error setting up plot: {str(e)}")

    def _auto_range_visible(self):
        """Auto-range to show visible data."""
        try:
            if hasattr(self, "price_widget") and self.price_widget:
                self.price_widget.autoRange()
        except Exception as e:
            self.logger.error(f"Error auto-ranging: {str(e)}")


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    app = QApplication([])

    # Create and show the chart widget
    chart = ChartWidget()
    chart.show()

    # Add some test data
    import random
    base_price = 450.0
    for i in range(100):
        timestamp = datetime.datetime.now() - datetime.timedelta(minutes=5*i)
        price_change = random.uniform(-2, 2)
        base_price += price_change

        high = base_price + random.uniform(0, 1)
        low = base_price - random.uniform(0, 1)
        close = base_price + random.uniform(-0.5, 0.5)
        volume = random.randint(1000, 10000)

        chart.add_price_data(timestamp, base_price, high, low, close, volume)

    chart.update_charts()

    app.exec()
