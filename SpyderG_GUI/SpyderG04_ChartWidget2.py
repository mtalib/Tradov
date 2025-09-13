#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI     
Module: SpyderG04_ChartWidget.py
Purpose: High-performance real-time price and indicator charts using finplot
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-09-13 Time: 14:30:00  

Module Description:
    This module provides high-performance interactive price charts with technical
    indicators for the Spyder trading system. It displays real-time SPY price data,
    option chains, and various technical indicators used by the strategies.
    This version uses finplot for superior performance with real-time data while
    maintaining complete visual compatibility with the existing dashboard.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import datetime
import json
import gc
from typing import Dict, List, Optional, Any, Tuple, Callable
from collections import deque
from dataclasses import dataclass
import numpy as np
import pandas as pd
import threading
import time
import psutil
from pathlib import Path

# ==============================================================================
# PYTHON PATH SETUP
# ==============================================================================
# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QGroupBox, QSplitter, QMenu, QApplication,
    QComboBox, QGridLayout, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QPointF, QThread
from PySide6.QtGui import QPalette, QColor, QFont, QPen, QBrush, QPixmap, QAction

# Import finplot for high-performance financial charting
try:
    import finplot as fplt
    FINPLOT_AVAILABLE = True
    # Configure finplot to match your dark theme
    fplt.foreground = '#ffffff'  # COLOR_TEXT
    fplt.background = '#1a1a1a'  # COLOR_PANEL
    fplt.candle_bull_color = '#00ff41'  # COLOR_POSITIVE
    fplt.candle_bear_color = '#ff1744'  # COLOR_NEGATIVE
    fplt.volume_bull_color = '#00ff4180'  # Semi-transparent green
    fplt.volume_bear_color = '#ff174480'  # Semi-transparent red
    fplt.cross_hair_color = '#ffd700'  # COLOR_NEUTRAL
    fplt.draw_line_color = '#888888'
    fplt.draw_done_color = '#555555'
except ImportError:
    FINPLOT_AVAILABLE = False
    print("Warning: finplot not available. Please install: pip install finplot")

# Fallback to pyqtgraph if finplot not available
try:
    import pyqtgraph as pg
    pg.setConfigOptions(antialias=True)
    PYQTGRAPH_AVAILABLE = True
except ImportError:
    PYQTGRAPH_AVAILABLE = False

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler

# ==============================================================================
# CONSTANTS - Matching your dashboard theme
# ==============================================================================
COLOR_BACKGROUND = "#0a0a0a"
COLOR_PANEL = "#1a1a1a"
COLOR_BORDER = "#333333"
COLOR_TEXT = "#ffffff"
COLOR_POSITIVE = "#00ff41"
COLOR_NEGATIVE = "#ff1744"
COLOR_NEUTRAL = "#ffd700"
COLOR_WARNING = "#ff9800"
COLOR_CYAN = "#00ffff"

# Chart update intervals
CHART_UPDATE_MS = 1000  # 1 second for real-time updates
INDICATOR_UPDATE_MS = 5000  # 5 seconds for indicators
MEMORY_CHECK_MS = 30000  # 30 seconds for memory monitoring

# Performance constants
MAX_CANDLES = 500  # Keep last 500 candles for performance
MEMORY_WARNING_THRESHOLD = 1e9  # 1GB memory warning threshold

# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class ChartData:
    """Container for chart data."""
    timestamp: List[datetime.datetime]
    open: List[float]
    high: List[float]
    low: List[float]
    close: List[float]
    volume: List[float]
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame for finplot."""
        return pd.DataFrame({
            'time': pd.to_datetime(self.timestamp),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume
        }).set_index('time')

@dataclass
class MemoryStats:
    """Memory usage statistics."""
    rss: float  # Resident Set Size
    vms: float  # Virtual Memory Size
    percent: float  # Memory percentage
    timestamp: datetime.datetime

# ==============================================================================
# MEMORY MONITOR CLASS
# ==============================================================================
class MemoryMonitor:
    """Monitor memory usage and trigger garbage collection."""
    
    def __init__(self, logger):
        self.logger = logger
        self.process = psutil.Process()
        self.stats_history = deque(maxlen=100)
    
    def check_memory(self) -> MemoryStats:
        """Check current memory usage."""
        try:
            mem_info = self.process.memory_info()
            mem_percent = self.process.memory_percent()
            
            stats = MemoryStats(
                rss=mem_info.rss,
                vms=mem_info.vms,
                percent=mem_percent,
                timestamp=datetime.datetime.now()
            )
            
            self.stats_history.append(stats)
            
            # Trigger garbage collection if memory is high
            if mem_info.rss > MEMORY_WARNING_THRESHOLD:
                self.logger.warning(f"High memory usage: {mem_info.rss / 1e9:.2f}GB")
                gc.collect()
                
            return stats
            
        except Exception as e:
            self.logger.error(f"Memory monitoring error: {e}")
            return None
    
    def get_average_usage(self, minutes: int = 5) -> float:
        """Get average memory usage over specified minutes."""
        if not self.stats_history:
            return 0.0
            
        cutoff_time = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
        recent_stats = [s for s in self.stats_history if s.timestamp > cutoff_time]
        
        if not recent_stats:
            return 0.0
            
        return sum(s.percent for s in recent_stats) / len(recent_stats)

# ==============================================================================
# MAIN CHART WIDGET CLASS
# ==============================================================================
class ChartWidget(QWidget):
    """
    High-performance real-time chart widget using finplot.
    
    This widget provides interactive financial charts with technical indicators,
    optimized for real-time trading data visualization. It maintains complete
    compatibility with the existing SpyderG05_TradingDashboard while providing
    significant performance improvements through finplot integration.
    """
    
    # Signals - maintaining compatibility
    price_updated = Signal(float)  # Current price
    indicator_updated = Signal(str, float)  # Indicator name, value
    memory_warning = Signal(str)  # Memory warning message
    
    def __init__(self, symbol: str = "SPY", parent=None):
        """Initialize the chart widget."""
        super().__init__(parent)
        
        # Setup logging
        self.logger = SpyderLogger.get_logger(self.__class__.__name__)
        self.error_handler = SpyderErrorHandler()
        
        # Configuration
        self.symbol = symbol
        self.timeframe = "5min"  # Default 5-minute candles
        
        # Data storage
        self.chart_data = None
        self.df = None  # Pandas DataFrame for finplot
        
        # Memory monitoring
        self.memory_monitor = MemoryMonitor(self.logger)
        
        # Performance tracking
        self.max_candles = MAX_CANDLES
        self.last_gc_time = time.time()
        
        # Indicators - maintaining compatibility with dashboard
        self.indicators = {
            'sma_20': {'enabled': True, 'color': COLOR_CYAN, 'width': 1},
            'sma_50': {'enabled': True, 'color': COLOR_WARNING, 'width': 1},
            'vwap': {'enabled': True, 'color': COLOR_NEUTRAL, 'width': 2},
            'volume': {'enabled': True},
            'rsi': {'enabled': False, 'period': 14},
            'macd': {'enabled': False}
        }
        
        # Chart components
        self.chart_widget = None
        self.ax_price = None
        self.ax_volume = None
        self.plot_items = {}
        
        # UI state
        self.auto_scroll = True
        self.current_price = 0.0
        
        # Setup UI
        self.setup_ui()
        
        # Setup timers
        self.setup_timers()
        
        # Initialize with sample data
        self.load_sample_data()
        
        self.logger.info(f"Enhanced ChartWidget initialized for {symbol} with finplot")

    # ==========================================================================
    # UI SETUP
    # ==========================================================================
    def setup_ui(self):
        """Setup the user interface maintaining dashboard compatibility."""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create control panel (matches dashboard style)
        control_panel = self.create_control_panel()
        layout.addWidget(control_panel)
        
        # Create chart area
        if FINPLOT_AVAILABLE:
            self.setup_finplot_chart()
        elif PYQTGRAPH_AVAILABLE:
            self.setup_pyqtgraph_fallback()
        else:
            self.setup_placeholder()
            
        layout.addWidget(self.chart_widget)
        
        # Apply dashboard styling - EXACT match
        self.setStyleSheet(f"""
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
            }}
            QPushButton:hover {{
                background-color: #3a3a3a;
            }}
            QPushButton:checked {{
                background-color: {COLOR_POSITIVE};
                color: #000000;
            }}
            QComboBox {{
                background-color: #2a2a2a;
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                padding: 3px;
            }}
            QLabel {{
                color: {COLOR_TEXT};
                border: none;
            }}
        """)
        
        self.setLayout(layout)

    def create_control_panel(self) -> QWidget:
        """Create control panel matching dashboard style exactly."""
        panel = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Timeframe selector
        timeframe_label = QLabel("Timeframe:")
        layout.addWidget(timeframe_label)
        
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1min", "5min", "15min", "30min", "1H", "1D"])
        self.timeframe_combo.setCurrentText(self.timeframe)
        self.timeframe_combo.currentTextChanged.connect(self.on_timeframe_changed)
        layout.addWidget(self.timeframe_combo)
        
        layout.addSpacing(20)
        
        # Indicator toggles - exactly matching original
        self.sma_btn = QPushButton("SMA")
        self.sma_btn.setCheckable(True)
        self.sma_btn.setChecked(True)
        self.sma_btn.clicked.connect(lambda: self.toggle_indicator('sma'))
        layout.addWidget(self.sma_btn)
        
        self.vwap_btn = QPushButton("VWAP")
        self.vwap_btn.setCheckable(True)
        self.vwap_btn.setChecked(True)
        self.vwap_btn.clicked.connect(lambda: self.toggle_indicator('vwap'))
        layout.addWidget(self.vwap_btn)
        
        self.volume_btn = QPushButton("Volume")
        self.volume_btn.setCheckable(True)
        self.volume_btn.setChecked(True)
        self.volume_btn.clicked.connect(lambda: self.toggle_indicator('volume'))
        layout.addWidget(self.volume_btn)
        
        self.rsi_btn = QPushButton("RSI")
        self.rsi_btn.setCheckable(True)
        self.rsi_btn.clicked.connect(lambda: self.toggle_indicator('rsi'))
        layout.addWidget(self.rsi_btn)
        
        layout.addStretch()
        
        # Memory indicator
        self.memory_label = QLabel("Mem: 0%")
        self.memory_label.setStyleSheet(f"color: {COLOR_CYAN}; font-size: 10px;")
        layout.addWidget(self.memory_label)
        
        layout.addSpacing(10)
        
        # Zoom controls
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_out_btn.setMaximumWidth(30)
        layout.addWidget(zoom_out_btn)
        
        zoom_reset_btn = QPushButton("Reset")
        zoom_reset_btn.clicked.connect(self.reset_zoom)
        layout.addWidget(zoom_reset_btn)
        
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_in_btn.setMaximumWidth(30)
        layout.addWidget(zoom_in_btn)
        
        panel.setLayout(layout)
        return panel

    # ==========================================================================
    # FINPLOT SETUP
    # ==========================================================================
    def setup_finplot_chart(self):
        """Setup finplot chart with dashboard-compatible styling."""
        # Create finplot widget container
        self.chart_widget = QWidget()
        self.chart_layout = QVBoxLayout(self.chart_widget)
        self.chart_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create plot windows with proper sizing
        # Main price plot (70% of space)
        self.ax_price = fplt.create_plot(
            title=f'{self.symbol} Price',
            init_zoom_periods=100,
            maximize=False
        )
        
        # Volume plot (30% of space)
        self.ax_volume = fplt.create_plot(
            title='Volume',
            init_zoom_periods=100,
            maximize=False
        )
        
        # Link x-axes for synchronized scrolling
        self.ax_volume.setXLink(self.ax_price)
        
        # Get the finplot window and add to layout
        try:
            # This gets the Qt widget from finplot
            fplt_window = fplt.get_active_widget()
            if fplt_window:
                self.chart_layout.addWidget(fplt_window, stretch=1)
        except:
            # Fallback approach
            pass
        
        # Store plot items for management
        self.plot_items = {
            'candles': None,
            'volume': None,
            'sma_20': None,
            'sma_50': None,
            'vwap': None
        }

    def setup_pyqtgraph_fallback(self):
        """Fallback to PyQtGraph if finplot not available."""
        self.chart_widget = pg.GraphicsLayoutWidget()
        self.chart_widget.setBackground(COLOR_PANEL)
        
        # Create price plot
        self.price_plot = self.chart_widget.addPlot(title=f"{self.symbol} Price")
        self.price_plot.showGrid(x=True, y=True, alpha=0.3)
        self.price_plot.setLabel('left', 'Price', color=COLOR_TEXT)
        self.price_plot.setLabel('bottom', 'Time', color=COLOR_TEXT)
        
        self.chart_widget.nextRow()
        
        # Create volume plot
        self.volume_plot = self.chart_widget.addPlot(title="Volume")
        self.volume_plot.showGrid(x=True, y=True, alpha=0.3)
        self.volume_plot.setLabel('left', 'Volume', color=COLOR_TEXT)
        self.volume_plot.setXLink(self.price_plot)

    def setup_placeholder(self):
        """Setup placeholder when no charting library available."""
        self.chart_widget = QLabel(
            "Chart libraries not available.\n"
            "Install finplot: pip install finplot\n"
            "Or PyQtGraph: pip install pyqtgraph"
        )
        self.chart_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chart_widget.setStyleSheet(f"""
            background-color: {COLOR_PANEL};
            color: {COLOR_WARNING};
            font-size: 14px;
            padding: 50px;
        """)

    # ==========================================================================
    # DATA MANAGEMENT
    # ==========================================================================
    def load_sample_data(self):
        """Load sample data for testing and initial display."""
        # Generate sample OHLCV data
        periods = 200
        now = datetime.datetime.now()
        timestamps = [now - datetime.timedelta(minutes=5*i) for i in range(periods, 0, -1)]
        
        # Generate realistic price movement
        base_price = 450.0
        prices = []
        for i in range(periods):
            change = np.random.randn() * 0.5
            base_price += change
            prices.append(base_price)
        
        # Create OHLCV data
        data = []
        for i, (ts, price) in enumerate(zip(timestamps, prices)):
            high = price + abs(np.random.randn() * 0.3)
            low = price - abs(np.random.randn() * 0.3)
            close = np.random.uniform(low, high)
            open_price = np.random.uniform(low, high)
            volume = int(np.random.uniform(1000000, 5000000))
            
            data.append({
                'time': ts,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close,
                'volume': volume
            })
        
        # Create DataFrame and update chart
        self.df = pd.DataFrame(data).set_index('time')
        self.current_price = self.df['close'].iloc[-1]
        self.update_chart()

    def update_chart(self):
        """Update chart with current data using finplot."""
        if not FINPLOT_AVAILABLE or self.df is None or len(self.df) == 0:
            return
        
        try:
            # Clear previous plots
            fplt.clear(self.ax_price)
            fplt.clear(self.ax_volume)
            
            # Plot candlesticks
            candles = self.df[['open', 'close', 'high', 'low']]
            fplt.candlestick_ochl(candles, ax=self.ax_price)
            
            # Plot volume if enabled
            if self.indicators['volume']['enabled']:
                volumes = self.df[['open', 'close', 'volume']]
                fplt.volume_ocv(volumes, ax=self.ax_volume)
            
            # Plot technical indicators
            self._plot_indicators()
            
            # Emit current price signal
            if len(self.df) > 0:
                current_price = self.df['close'].iloc[-1]
                self.price_updated.emit(current_price)
                
        except Exception as e:
            self.error_handler.handle_error(e, "Failed to update chart")

    def _plot_indicators(self):
        """Plot technical indicators on the chart."""
        if self.df is None or len(self.df) < 50:
            return
        
        try:
            # Simple Moving Averages
            if self.indicators['sma_20']['enabled']:
                sma20 = self.df['close'].rolling(20).mean()
                fplt.plot(sma20, ax=self.ax_price,
                         color=self.indicators['sma_20']['color'],
                         width=self.indicators['sma_20']['width'],
                         legend='SMA 20')
            
            if self.indicators['sma_50']['enabled']:
                sma50 = self.df['close'].rolling(50).mean()
                fplt.plot(sma50, ax=self.ax_price,
                         color=self.indicators['sma_50']['color'],
                         width=self.indicators['sma_50']['width'],
                         legend='SMA 50')
            
            # VWAP
            if self.indicators['vwap']['enabled']:
                vwap = self.calculate_vwap()
                if vwap is not None:
                    fplt.plot(vwap, ax=self.ax_price,
                             color=self.indicators['vwap']['color'],
                             width=self.indicators['vwap']['width'],
                             legend='VWAP')
                             
        except Exception as e:
            self.logger.error(f"Error plotting indicators: {e}")

    def calculate_vwap(self) -> pd.Series:
        """Calculate VWAP (Volume Weighted Average Price)."""
        try:
            df = self.df.copy()
            df['cum_volume'] = df['volume'].cumsum()
            df['cum_volume_price'] = (df['close'] * df['volume']).cumsum()
            return df['cum_volume_price'] / df['cum_volume']
        except Exception as e:
            self.logger.error(f"VWAP calculation error: {e}")
            return None

    # ==========================================================================
    # REAL-TIME UPDATES
    # ==========================================================================
    def setup_timers(self):
        """Setup timers for real-time updates and memory monitoring."""
        # Price update timer
        self.price_timer = QTimer()
        self.price_timer.timeout.connect(self.update_real_time_data)
        self.price_timer.start(CHART_UPDATE_MS)
        
        # Indicator update timer
        self.indicator_timer = QTimer()
        self.indicator_timer.timeout.connect(self.update_indicators)
        self.indicator_timer.start(INDICATOR_UPDATE_MS)
        
        # Memory monitoring timer
        self.memory_timer = QTimer()
        self.memory_timer.timeout.connect(self.check_memory_usage)
        self.memory_timer.start(MEMORY_CHECK_MS)

    def update_real_time_data(self):
        """Simulate real-time data updates with performance optimization."""
        if self.df is None or len(self.df) == 0:
            return
        
        try:
            # Simulate new price tick
            last_close = self.df['close'].iloc[-1]
            change = np.random.randn() * 0.1
            new_price = last_close + change
            
            # Update last candle or create new one
            now = datetime.datetime.now()
            last_time = self.df.index[-1]
            
            if (now - last_time).total_seconds() >= 300:  # New 5-minute candle
                # Create new candle
                new_candle = pd.DataFrame([{
                    'open': new_price,
                    'high': new_price,
                    'low': new_price,
                    'close': new_price,
                    'volume': int(np.random.uniform(100000, 500000))
                }], index=[now])
                
                self.df = pd.concat([self.df, new_candle])
                
                # Trim to max candles for performance
                if len(self.df) > self.max_candles:
                    self.df = self.df.iloc[-self.max_candles:]
                    
            else:
                # Update last candle
                self.df.loc[last_time, 'close'] = new_price
                self.df.loc[last_time, 'high'] = max(self.df.loc[last_time, 'high'], new_price)
                self.df.loc[last_time, 'low'] = min(self.df.loc[last_time, 'low'], new_price)
                self.df.loc[last_time, 'volume'] += int(np.random.uniform(1000, 5000))
            
            # Update chart
            self.update_chart()
            
        except Exception as e:
            self.error_handler.handle_error(e, "Real-time update failed")

    def update_indicators(self):
        """Update technical indicators with memory efficiency."""
        if self.df is None or len(self.df) < 50:
            return
        
        try:
            # Calculate and emit indicator values
            sma20 = self.df['close'].rolling(20).mean().iloc[-1]
            sma50 = self.df['close'].rolling(50).mean().iloc[-1]
            
            self.indicator_updated.emit("SMA20", sma20)
            self.indicator_updated.emit("SMA50", sma50)
            
            # Calculate RSI if enabled
            if self.indicators.get('rsi', {}).get('enabled', False):
                rsi = self.calculate_rsi()
                if rsi is not None:
                    self.indicator_updated.emit("RSI", rsi)
                    
        except Exception as e:
            self.logger.error(f"Indicator update error: {e}")

    def calculate_rsi(self, period: int = 14) -> float:
        """Calculate RSI indicator efficiently."""
        try:
            delta = self.df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1]
        except Exception as e:
            self.logger.error(f"RSI calculation error: {e}")
            return None

    def check_memory_usage(self):
        """Monitor memory usage and trigger cleanup if needed."""
        try:
            stats = self.memory_monitor.check_memory()
            if stats:
                # Update memory display
                self.memory_label.setText(f"Mem: {stats.percent:.1f}%")
                
                # Change color based on usage
                if stats.percent > 80:
                    self.memory_label.setStyleSheet(f"color: {COLOR_NEGATIVE}; font-size: 10px;")
                    self.memory_warning.emit(f"High memory usage: {stats.percent:.1f}%")
                elif stats.percent > 60:
                    self.memory_label.setStyleSheet(f"color: {COLOR_WARNING}; font-size: 10px;")
                else:
                    self.memory_label.setStyleSheet(f"color: {COLOR_CYAN}; font-size: 10px;")
                
                # Trigger garbage collection periodically
                current_time = time.time()
                if current_time - self.last_gc_time > 60:  # Every minute
                    gc.collect()
                    self.last_gc_time = current_time
                    
        except Exception as e:
            self.logger.error(f"Memory monitoring error: {e}")

    # ==========================================================================
    # USER INTERACTIONS
    # ==========================================================================
    def toggle_indicator(self, indicator: str):
        """Toggle indicator visibility."""
        if indicator == 'sma':
            self.indicators['sma_20']['enabled'] = not self.indicators['sma_20']['enabled']
            self.indicators['sma_50']['enabled'] = not self.indicators['sma_50']['enabled']
        elif indicator in self.indicators:
            self.indicators[indicator]['enabled'] = not self.indicators[indicator]['enabled']
        
        self.update_chart()

    def on_timeframe_changed(self, timeframe: str):
        """Handle timeframe change."""
        self.timeframe = timeframe
        self.logger.info(f"Timeframe changed to {timeframe}")
        # In production, reload data for new timeframe
        self.load_sample_data()

    def zoom_in(self):
        """Zoom in on chart."""
        if FINPLOT_AVAILABLE:
            try:
                fplt.zoom(0.8)
            except:
                pass

    def zoom_out(self):
        """Zoom out on chart."""
        if FINPLOT_AVAILABLE:
            try:
                fplt.zoom(1.25)
            except:
                pass

    def reset_zoom(self):
        """Reset chart zoom."""
        if FINPLOT_AVAILABLE:
            try:
                fplt.reset()
            except:
                pass

    # ==========================================================================
    # PUBLIC INTERFACE - Maintaining compatibility
    # ==========================================================================
    def set_data(self, df: pd.DataFrame):
        """Set chart data from external source."""
        self.df = df.copy()
        if len(self.df) > 0:
            self.current_price = self.df['close'].iloc[-1]
        self.update_chart()

    def add_trade_marker(self, timestamp: datetime.datetime, price: float, 
                        trade_type: str, size: int = 1):
        """Add trade marker to chart."""
        if not FINPLOT_AVAILABLE:
            return
        
        try:
            color = COLOR_POSITIVE if trade_type == 'BUY' else COLOR_NEGATIVE
            marker = '^' if trade_type == 'BUY' else 'v'
            
            # Add scatter plot for trade
            fplt.plot([timestamp], [price], ax=self.ax_price,
                     color=color, style=marker, width=3)
        except Exception as e:
            self.logger.error(f"Trade marker error: {e}")

    def clear_chart(self):
        """Clear all chart data."""
        if FINPLOT_AVAILABLE:
            try:
                fplt.clear(self.ax_price)
                fplt.clear(self.ax_volume)
            except:
                pass
        self.df = None

    def get_current_price(self) -> float:
        """Get current price."""
        return self.current_price

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        stats = self.memory_monitor.check_memory()
        if stats:
            return {
                'memory_percent': stats.percent,
                'memory_rss_gb': stats.rss / 1e9,
                'average_5min': self.memory_monitor.get_average_usage(5)
            }
        return {}

# ==============================================================================
# STANDALONE TESTING
# ==============================================================================
def main():
    """Standalone testing of enhanced chart widget."""
    app = QApplication(sys.argv)
    
    # Set application style to match dashboard
    app.setStyle('Fusion')
    
    # Create and show chart widget
    chart = ChartWidget("SPY")
    chart.setWindowTitle("Spyder Chart Widget - Enhanced Performance")
    chart.resize(1200, 800)
    chart.show()
    
    # Connect signals for testing
    chart.price_updated.connect(lambda p: print(f"Price: ${p:.2f}"))
    chart.indicator_updated.connect(lambda name, val: print(f"{name}: {val:.2f}"))
    chart.memory_warning.connect(lambda msg: print(f"Memory Warning: {msg}"))
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()