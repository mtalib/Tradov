#!/usr/bin/env python3
"""
TRADOV - Autonomous Arbitrage Trading System v1.0

Series: TradovG_GUI [Application Name] [Group Letter] [Group Name]
Module: TradovG30_PlotlyDataBridge.py [Application Name][Group Letter] [Module Number]_[Purpose].py
Purpose: Data bridge for Plotly charts
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-06-26 Time: 13:25:07

Module Description:
    Data bridge for Plotly charts in the Tradov Trading Dashboard. Provides a
    data bridge that converts Tradov's market data format to Plotly-compatible JSON
    and handles real-time updates via JavaScript callbacks. It enables smooth
    streaming of market data to embedded Plotly charts without full chart redraws,
    optimizing performance for live trading dashboards.

    This module was renumbered from TradovG04_PlotlyDataBridge.py as part of the
    modular refactoring effort to eliminate duplicate module numbers and improve
    code organization.

Module Constants:
    DATA_UPDATE_INTERVAL (int): Data update interval in milliseconds (1000)
    MAX_DATA_POINTS (int): Maximum number of data points to display (1000)
    JAVASCRIPT_TIMEOUT (int): JavaScript execution timeout in milliseconds (5000)

Change Log:
    2025-10-15 (v1.6.0):
        - Renumbered from TradovG04_PlotlyDataBridge.py to TradovG30_PlotlyDataBridge.py
        - Updated module header with standard structure
        - Enhanced documentation and constants
    2025-09-27 (v1.5):
        - Initial module creation with Plotly data bridge
        - Added real-time data streaming capabilities
"""

# ==============================================================================
# IMPORTS
# ==============================================================================
import json
from typing import Any
from datetime import datetime, UTC
import pandas as pd
from dataclasses import dataclass, asdict
from PySide6.QtCore import QObject, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
import logging


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class MarketDataPoint:
    """Single market data point for Plotly consumption."""

    timestamp: str  # ISO format for JavaScript compatibility
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class IndicatorUpdate:
    """Technical indicator update."""

    timestamp: str
    name: str
    value: float
    color: str | None = None


@dataclass
class PlotlyUpdatePacket:
    """Complete update packet for Plotly chart."""

    action: str  # 'extend', 'restyle', 'relayout'
    data: dict[str, Any]
    trace_indices: list[int]


# ==============================================================================
# DATA CONVERSION UTILITIES
# ==============================================================================
class TradovToPlotlyConverter:
    """Converts Tradov data formats to Plotly-compatible structures."""

    @staticmethod
    def convert_market_data(tradov_data: dict[str, Any]) -> MarketDataPoint:
        """Convert Tradov market data to Plotly format."""
        # Handle both dict and object formats
        if hasattr(tradov_data, "__dict__"):
            data = tradov_data.__dict__
        else:
            data = tradov_data

        # Convert timestamp to ISO string
        timestamp = data.get("timestamp", datetime.now(UTC))
        if isinstance(timestamp, datetime):
            timestamp_str = timestamp.isoformat()
        else:
            timestamp_str = str(timestamp)

        return MarketDataPoint(
            timestamp=timestamp_str,
            open=float(data.get("open", data.get("last", 0))),
            high=float(data.get("high", data.get("last", 0))),
            low=float(data.get("low", data.get("last", 0))),
            close=float(data.get("close", data.get("last", 0))),
            volume=int(data.get("volume", 0)),
        )

    @staticmethod
    def convert_dataframe_to_plotly(df: pd.DataFrame) -> dict[str, list]:
        """Convert DataFrame to Plotly trace data format."""
        plotly_data = {}

        # Convert datetime column
        if "datetime" in df.columns:
            plotly_data["x"] = df["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S").tolist()
        elif df.index.name == "datetime" or isinstance(df.index, pd.DatetimeIndex):
            plotly_data["x"] = (
                df.index.to_series().dt.strftime("%Y-%m-%dT%H:%M:%S").tolist()
            )

        # Convert OHLCV data
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                plotly_data[col] = df[col].fillna(0).tolist()

        # Convert indicators
        for col in df.columns:
            if col not in ["datetime", "open", "high", "low", "close", "volume"]:
                plotly_data[col] = df[col].fillna(None).tolist()

        return plotly_data

    @staticmethod
    def create_candlestick_update(data_point: MarketDataPoint) -> PlotlyUpdatePacket:
        """Create candlestick chart update packet."""
        return PlotlyUpdatePacket(
            action="extend",
            data={
                "x": [[data_point.timestamp]],
                "open": [[data_point.open]],
                "high": [[data_point.high]],
                "low": [[data_point.low]],
                "close": [[data_point.close]],
            },
            trace_indices=[0],  # Candlestick is typically trace 0
        )

    @staticmethod
    def create_volume_update(data_point: MarketDataPoint) -> PlotlyUpdatePacket:
        """Create volume chart update packet."""
        # Color based on price movement
        color = "#00ff41" if data_point.close >= data_point.open else "#FF073A"

        return PlotlyUpdatePacket(
            action="extend",
            data={
                "x": [[data_point.timestamp]],
                "y": [[data_point.volume]],
                "marker.color": [[color]],
            },
            trace_indices=[1],  # Volume typically trace 1
        )

    @staticmethod
    def create_indicator_update(
        indicator: IndicatorUpdate, trace_index: int
    ) -> PlotlyUpdatePacket:
        """Create technical indicator update packet."""
        return PlotlyUpdatePacket(
            action="extend",
            data={"x": [[indicator.timestamp]], "y": [[indicator.value]]},
            trace_indices=[trace_index],
        )


# ==============================================================================
# REAL-TIME DATA BRIDGE
# ==============================================================================
class PlotlyDataBridge(QObject):
    """
    Real-time data bridge for Plotly charts.

    This class manages the flow of data from Tradov's market data workers
    to embedded Plotly charts via JavaScript callbacks, enabling smooth
    real-time updates without full chart redraws.
    """

    # Signals for data updates
    data_ready = Signal(str)  # JSON data for JavaScript
    chart_update_ready = Signal(str, str)  # function_name, json_params

    def __init__(self, web_view: QWebEngineView, symbol: str = "TRAD"):
        """Initialize the data bridge."""
        super().__init__()

        self.web_view = web_view
        self.symbol = symbol
        self.converter = TradovToPlotlyConverter()

        # Data buffers
        self.market_data_buffer = []
        self.indicator_buffer = {}
        self.max_buffer_size = 1000

        # Update tracking
        self.last_update = datetime.now(UTC)
        self.update_count = 0

        # Performance monitoring
        self.performance_stats = {
            "updates_sent": 0,
            "avg_update_time": 0.0,
            "buffer_size": 0,
        }

    def connect_market_data_worker(self, worker):
        """Connect to a market data worker for real-time updates."""
        if hasattr(worker, "data_updated"):
            worker.data_updated.connect(self.handle_market_data_update)
        if hasattr(worker, "indicator_updated"):
            worker.indicator_updated.connect(self.handle_indicator_update)

    def handle_market_data_update(self, market_data: dict[str, Any]):
        """Handle incoming market data updates."""
        if self.symbol not in market_data:
            return

        symbol_data = market_data[self.symbol]
        data_point = self.converter.convert_market_data(symbol_data)

        # Add to buffer
        self.market_data_buffer.append(data_point)

        # Limit buffer size
        if len(self.market_data_buffer) > self.max_buffer_size:
            self.market_data_buffer = self.market_data_buffer[-self.max_buffer_size :]

        # Create update packets
        candlestick_update = self.converter.create_candlestick_update(data_point)
        volume_update = self.converter.create_volume_update(data_point)

        # Send updates to JavaScript
        self.send_chart_update("updateCandlestickData", candlestick_update)
        self.send_chart_update("updateVolumeData", volume_update)

        # Update performance stats
        self.performance_stats["updates_sent"] += 1
        self.performance_stats["buffer_size"] = len(self.market_data_buffer)

    def handle_indicator_update(self, indicator_name: str, value: float):
        """Handle technical indicator updates."""
        timestamp = datetime.now(UTC).isoformat()

        indicator = IndicatorUpdate(
            timestamp=timestamp, name=indicator_name, value=value
        )

        # Store in buffer
        if indicator_name not in self.indicator_buffer:
            self.indicator_buffer[indicator_name] = []

        self.indicator_buffer[indicator_name].append(indicator)

        # Limit buffer size
        if len(self.indicator_buffer[indicator_name]) > self.max_buffer_size:
            self.indicator_buffer[indicator_name] = self.indicator_buffer[
                indicator_name
            ][-self.max_buffer_size :]

        # Map indicator names to trace indices (these would be configured)
        trace_map = {"SMA20": 2, "SMA50": 3, "VWAP": 4, "RSI": 5}

        if indicator_name in trace_map:
            trace_index = trace_map[indicator_name]
            update_packet = self.converter.create_indicator_update(
                indicator, trace_index
            )
            self.send_chart_update("updateIndicatorData", update_packet)

    def send_chart_update(self, function_name: str, update_packet: PlotlyUpdatePacket):
        """Send update to JavaScript via web engine."""
        try:
            # Convert update packet to JSON
            json_data = json.dumps(
                {
                    "action": update_packet.action,
                    "data": update_packet.data,
                    "traces": update_packet.trace_indices,
                }
            )

            # Execute JavaScript function
            escaped_json = json_data.replace("'", "\\'")
            js_code = f"{function_name}('{escaped_json}')"
            self.web_view.page().runJavaScript(js_code)

            # Emit signal for debugging/monitoring
            self.chart_update_ready.emit(function_name, json_data)

        except Exception as e:
            logging.info("Error sending chart update: %s", e)

    def batch_update_indicators(self, indicators: dict[str, float]):
        """Send batch update for multiple indicators."""
        updates = []

        for name, value in indicators.items():
            timestamp = datetime.now(UTC).isoformat()
            indicator = IndicatorUpdate(timestamp=timestamp, name=name, value=value)

            # Map to trace index
            trace_map = {"SMA20": 2, "SMA50": 3, "VWAP": 4, "RSI": 5}
            if name in trace_map:
                update_packet = self.converter.create_indicator_update(
                    indicator, trace_map[name]
                )
                updates.append(update_packet)

        # Send batch update
        if updates:
            batch_data = {
                "updates": [asdict(update) for update in updates],
                "timestamp": datetime.now(UTC).isoformat(),
            }

            json_data = json.dumps(batch_data)
            escaped_json = json_data.replace("'", "\\'")
            js_code = f"batchUpdateIndicators('{escaped_json}')"
            self.web_view.page().runJavaScript(js_code)

    def initialize_chart_data(self, df: pd.DataFrame):
        """Initialize chart with historical data."""
        plotly_data = self.converter.convert_dataframe_to_plotly(df)

        # Send initial data to JavaScript
        json_data = json.dumps(plotly_data)
        escaped_json = json_data.replace("'", "\\'")
        js_code = f"initializeChartData('{escaped_json}')"
        self.web_view.page().runJavaScript(js_code)

    def clear_buffers(self):
        """Clear all data buffers."""
        self.market_data_buffer.clear()
        self.indicator_buffer.clear()
        self.performance_stats["buffer_size"] = 0

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return self.performance_stats.copy()


# ==============================================================================
# JAVASCRIPT BRIDGE GENERATOR
# ==============================================================================
class JavaScriptBridgeGenerator:
    """Generates JavaScript code for Plotly chart interactions."""

    @staticmethod
    def generate_update_functions() -> str:
        """Generate JavaScript functions for chart updates."""
        js_code = """
        // Plotly Data Bridge - Real-time Update Functions

        // Global variables
        window.plotlyBridge = {
            initialized: false,
            chartDiv: 'plotly-chart',
            maxDataPoints: 1000,
            updateQueue: []
        };

        // Initialize chart data
        function initializeChartData(jsonData) {
            try {
                const data = JSON.parse(jsonData);
                console.log('Initializing chart with data:', data);

                // Store reference for updates
                window.plotlyBridge.initialized = true;
                window.plotlyBridge.currentData = data;

            } catch (error) {
                console.error('Error initializing chart data:', error);
            }
        }

        // Update candlestick data
        function updateCandlestickData(jsonData) {
            if (!window.plotlyBridge.initialized) {
                window.plotlyBridge.updateQueue.push(['updateCandlestickData', jsonData]);
                return;
            }

            try {
                const update = JSON.parse(jsonData);

                // Extend candlestick trace
                Plotly.extendTraces(window.plotlyBridge.chartDiv, {
                    x: update.data.x,
                    open: update.data.open,
                    high: update.data.high,
                    low: update.data.low,
                    close: update.data.close
                }, update.traces);

                // Limit data points for performance
                limitDataPoints();

            } catch (error) {
                console.error('Error updating candlestick data:', error);
            }
        }

        // Update volume data
        function updateVolumeData(jsonData) {
            if (!window.plotlyBridge.initialized) {
                window.plotlyBridge.updateQueue.push(['updateVolumeData', jsonData]);
                return;
            }

            try {
                const update = JSON.parse(jsonData);

                // Extend volume trace
                Plotly.extendTraces(window.plotlyBridge.chartDiv, {
                    x: update.data.x,
                    y: update.data.y,
                    'marker.color': update.data['marker.color']
                }, update.traces);

            } catch (error) {
                console.error('Error updating volume data:', error);
            }
        }

        // Update indicator data
        function updateIndicatorData(jsonData) {
            if (!window.plotlyBridge.initialized) {
                window.plotlyBridge.updateQueue.push(['updateIndicatorData', jsonData]);
                return;
            }

            try {
                const update = JSON.parse(jsonData);

                // Extend indicator trace
                Plotly.extendTraces(window.plotlyBridge.chartDiv, {
                    x: update.data.x,
                    y: update.data.y
                }, update.traces);

            } catch (error) {
                console.error('Error updating indicator data:', error);
            }
        }

        // Batch update indicators
        function batchUpdateIndicators(jsonData) {
            if (!window.plotlyBridge.initialized) {
                window.plotlyBridge.updateQueue.push(['batchUpdateIndicators', jsonData]);
                return;
            }

            try {
                const batch = JSON.parse(jsonData);

                batch.updates.forEach(update => {
                    Plotly.extendTraces(window.plotlyBridge.chartDiv, {
                        x: update.data.x,
                        y: update.data.y
                    }, update.trace_indices);
                });

            } catch (error) {
                console.error('Error batch updating indicators:', error);
            }
        }

        // Limit data points for performance
        function limitDataPoints() {
            const chartDiv = document.getElementById(window.plotlyBridge.chartDiv);
            if (!chartDiv || !chartDiv.data) return;

            chartDiv.data.forEach((trace, index) => {
                if (trace.x && trace.x.length > window.plotlyBridge.maxDataPoints) {
                    const excessPoints = trace.x.length - window.plotlyBridge.maxDataPoints;

                    // Remove oldest points
                    Plotly.deleteTraces(window.plotlyBridge.chartDiv,
                                      Array.from({length: excessPoints}, (_, i) => i));
                }
            });
        }

        // Process queued updates after initialization
        function processUpdateQueue() {
            while (window.plotlyBridge.updateQueue.length > 0) {
                const [funcName, data] = window.plotlyBridge.updateQueue.shift();
                window[funcName](data);
            }
        }

        // Chart ready callback
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(() => {
                window.plotlyBridge.initialized = true;
                processUpdateQueue();
                console.log('Plotly bridge ready for real-time updates');
            }, 2000);
        });
        """

        return js_code


# ==============================================================================
# EXAMPLE USAGE
# ==============================================================================
if __name__ == "__main__":
    """Example usage of the data bridge."""

    # Generate JavaScript bridge code
    js_generator = JavaScriptBridgeGenerator()
    js_code = js_generator.generate_update_functions()


    # Example data conversion
    converter = TradovToPlotlyConverter()

    # Sample market data
    sample_data = {
        "symbol": "TRAD",
        "last": 585.25,
        "open": 584.50,
        "high": 586.75,
        "low": 583.80,
        "close": 585.25,
        "volume": 2500000,
        "timestamp": datetime.now(UTC),
    }

    # Convert to Plotly format
    market_point = converter.convert_market_data(sample_data)

    # Create update packet
    update_packet = converter.create_candlestick_update(market_point)

