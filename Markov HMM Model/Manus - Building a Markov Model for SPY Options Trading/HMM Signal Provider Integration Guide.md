# HMM Signal Provider Integration Guide

**Author**: Manus AI  
**Version**: 1.0  
**Date**: August 8, 2025  
**Purpose**: Complete guide for integrating the streamlined HMM Signal Provider with existing PyQt6 trading systems

## Executive Summary

The HMM Signal Provider represents a sophisticated, streamlined version of our Hidden Markov Model trading system, specifically designed for seamless integration with existing PyQt6 trading dashboards. This guide provides comprehensive instructions, examples, and best practices for incorporating advanced market regime detection and signal generation capabilities into your current trading infrastructure.

Unlike the full-featured standalone system, this signal provider focuses exclusively on delivering high-quality trading signals and market regime intelligence through clean, well-documented APIs. The system maintains all the sophisticated machine learning capabilities of the original while eliminating GUI dependencies and providing flexible integration patterns suitable for any existing trading platform.

## Table of Contents

1. [Quick Start Integration](#quick-start-integration)
2. [Core Components Overview](#core-components-overview)
3. [Integration Patterns](#integration-patterns)
4. [API Reference](#api-reference)
5. [PyQt6 Widget Examples](#pyqt6-widget-examples)
6. [Configuration and Customization](#configuration-and-customization)
7. [Performance Optimization](#performance-optimization)
8. [Error Handling and Monitoring](#error-handling-and-monitoring)
9. [Advanced Integration Scenarios](#advanced-integration-scenarios)
10. [Troubleshooting Guide](#troubleshooting-guide)

## Quick Start Integration

### Minimal Integration Example

The fastest way to integrate the HMM Signal Provider into your existing system is through the simplified API interface. Here's a complete minimal example that demonstrates the core functionality:

```python
from hmm_signal_provider import create_signal_provider
from signal_provider_api import quick_start_api

# Method 1: Direct Signal Provider
def simple_integration():
    # Create and start signal provider
    provider = create_signal_provider(symbols=["SPY"])
    provider.start()
    
    # Get current regime
    regime_info = provider.get_current_regime()
    if regime_info:
        print(f"Current Regime: {regime_info.regime.name}")
        print(f"Confidence: {regime_info.confidence:.1%}")
    
    # Get latest signals
    signals = provider.get_latest_signals(5)
    for signal in signals:
        print(f"Signal: {signal.signal_type} {signal.symbol} @ ${signal.entry_price:.2f}")
    
    provider.stop()

# Method 2: API Interface
def api_integration():
    # Quick start with API
    api = quick_start_api(symbols=["SPY"])
    
    # Get system status
    status = api.get_status()
    print(f"System Status: {status}")
    
    # Get current regime
    regime = api.get_current_regime()
    print(f"Current Regime: {regime}")
    
    # Get recent signals
    signals = api.get_signals(limit=10)
    print(f"Recent Signals: {signals}")
    
    api.stop()
```

### Integration with Existing PyQt6 Dashboard

For integration with existing PyQt6 applications, use the provided integration wrapper:

```python
from pyqt6_integration_example import SignalProviderIntegration

class YourExistingTradingWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        # Initialize your existing UI
        self.init_existing_ui()
        
        # Add HMM signal provider integration
        self.hmm_integration = SignalProviderIntegration(self)
        self.setup_hmm_integration()
    
    def setup_hmm_integration(self):
        # Initialize the signal provider
        self.hmm_integration.initialize_provider(symbols=["SPY", "QQQ"])
        
        # Register callbacks for your existing UI updates
        self.hmm_integration.register_callback("regime_changed", self.on_regime_changed)
        self.hmm_integration.register_callback("signal_generated", self.on_new_signal)
        
        # Start the provider
        self.hmm_integration.start_provider()
    
    def on_regime_changed(self, regime_update):
        # Update your existing regime display
        regime_info = self.hmm_integration.get_current_regime()
        self.update_regime_display(regime_info)
    
    def on_new_signal(self, signal):
        # Add signal to your existing signal list
        self.add_signal_to_display(signal)
```

## Core Components Overview

### HMMSignalProvider Class

The `HMMSignalProvider` is the core component that encapsulates all Hidden Markov Model functionality in a streamlined, thread-safe package. This class provides the following key capabilities:

**Market Regime Detection**: The provider continuously analyzes market data using a three-state Hidden Markov Model to identify distinct market regimes. These regimes represent different market conditions that require different trading approaches:

- **Low Volatility Trending**: Markets exhibiting persistent directional movement with low volatility, favoring momentum-based strategies
- **High Volatility Mean-Reverting**: Markets showing high volatility with tendency toward mean reversion, favoring contrarian strategies  
- **Transitional/Neutral**: Markets in uncertain states requiring conservative approaches

**Real-time Signal Generation**: Based on the detected market regime, the provider generates trading signals using regime-specific machine learning models. Each signal includes confidence levels, position sizing recommendations, and risk parameters.

**Adaptive Learning**: The system continuously updates its models with new market data, ensuring that regime detection and signal generation remain current with evolving market conditions.

### SignalProviderAPI Class

The `SignalProviderAPI` provides a clean, REST-like interface for accessing signal provider functionality. This API layer offers several advantages:

**Simplified Access**: All complex functionality is exposed through simple method calls that return JSON-serializable data structures, making integration straightforward regardless of your existing architecture.

**Event Subscription**: The API supports event-driven programming patterns through callback registration, allowing your application to respond immediately to regime changes and new signals.

**Thread Safety**: All API operations are thread-safe, enabling safe access from multiple parts of your application without synchronization concerns.

**Error Handling**: Comprehensive error handling ensures that API failures don't crash your application, with detailed error messages for debugging.

### Integration Wrapper Classes

The integration wrapper classes provide pre-built patterns for common integration scenarios:

**SignalProviderIntegration**: A comprehensive wrapper that handles the most common integration patterns, including callback management, data formatting for GUI display, and lifecycle management.

**PyQt6 Widget Examples**: Complete widget implementations that demonstrate how to create professional-looking signal provider interfaces that integrate seamlessly with existing PyQt6 applications.

## Integration Patterns

### Pattern 1: Callback-Based Integration

This pattern is ideal for applications that need to respond immediately to market regime changes and new trading signals. The callback-based approach ensures minimal latency between signal generation and application response.

```python
class CallbackIntegration:
    def __init__(self):
        self.signal_provider = create_signal_provider(
            symbols=["SPY"],
            callbacks={
                "regime": self.handle_regime_change,
                "signal": self.handle_new_signal,
                "data": self.handle_data_update
            }
        )
    
    def handle_regime_change(self, regime_update):
        """Handle immediate regime changes"""
        print(f"Regime changed to: {regime_update.regime.name}")
        print(f"Confidence: {regime_update.confidence:.1%}")
        
        # Update your trading strategy based on new regime
        self.update_trading_strategy(regime_update.regime)
        
        # Update UI elements
        self.update_regime_display(regime_update)
    
    def handle_new_signal(self, signal):
        """Handle new trading signals"""
        print(f"New signal: {signal.signal_type} {signal.symbol}")
        
        # Validate signal against your risk parameters
        if self.validate_signal(signal):
            # Add to your signal queue or execute immediately
            self.process_trading_signal(signal)
        
        # Update signal display
        self.update_signal_display(signal)
    
    def handle_data_update(self, market_data):
        """Handle market data updates"""
        # Update your market data displays
        self.update_market_data_display(market_data)
```

### Pattern 2: Polling-Based Integration

For applications that prefer to check for updates on their own schedule, the polling pattern provides complete control over when and how often to retrieve new information.

```python
class PollingIntegration:
    def __init__(self):
        self.api = create_api(symbols=["SPY"])
        self.api.initialize()
        self.api.start()
        
        # Set up polling timer
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_for_updates)
        self.poll_timer.start(5000)  # Poll every 5 seconds
    
    def poll_for_updates(self):
        """Poll for updates on a schedule"""
        # Check for regime changes
        current_regime = self.api.get_current_regime()
        if self.has_regime_changed(current_regime):
            self.handle_regime_change(current_regime)
        
        # Check for new signals
        latest_signals = self.api.get_signals(limit=10)
        new_signals = self.filter_new_signals(latest_signals)
        for signal in new_signals:
            self.handle_new_signal(signal)
        
        # Update status display
        status = self.api.get_status()
        self.update_status_display(status)
```

### Pattern 3: Hybrid Integration

The hybrid pattern combines the responsiveness of callbacks for critical events with the control of polling for less time-sensitive updates.

```python
class HybridIntegration:
    def __init__(self):
        # Set up callback-based provider for immediate events
        self.integration = SignalProviderIntegration()
        self.integration.initialize_provider(symbols=["SPY"])
        
        # Register callbacks for immediate response
        self.integration.register_callback("signal_generated", self.immediate_signal_handler)
        self.integration.register_callback("regime_changed", self.immediate_regime_handler)
        
        # Set up polling for status and historical data
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.poll_for_status)
        self.poll_timer.start(30000)  # Poll every 30 seconds
        
        self.integration.start_provider()
    
    def immediate_signal_handler(self, signal):
        """Handle time-critical signals immediately"""
        if signal.confidence > 0.8:  # High confidence signals
            self.execute_immediate_action(signal)
    
    def immediate_regime_handler(self, regime_update):
        """Handle regime changes immediately"""
        self.update_strategy_parameters(regime_update.regime)
    
    def poll_for_status(self):
        """Poll for non-critical updates"""
        status = self.integration.get_system_status()
        self.update_status_dashboard(status)
        
        # Get performance metrics
        recent_signals = self.integration.get_recent_signals(50)
        self.update_performance_metrics(recent_signals)
```

## API Reference

### HMMSignalProvider Methods

#### Core Lifecycle Methods

**`start()`**
Starts the signal provider's background processing thread. This method initializes data collection, model training, and signal generation processes.

```python
provider = create_signal_provider(symbols=["SPY"])
provider.start()
```

**`stop()`**
Gracefully stops the signal provider, ensuring all threads are properly terminated and resources are cleaned up.

```python
provider.stop()
```

**`force_update()`**
Forces an immediate update of market data, regime detection, and signal generation, bypassing the normal update schedule.

```python
provider.force_update()
```

#### Data Access Methods

**`get_current_regime() -> Optional[RegimeUpdate]`**
Returns the most recent market regime detection result, including regime type, confidence level, and timestamp.

```python
regime_info = provider.get_current_regime()
if regime_info:
    print(f"Regime: {regime_info.regime.name}")
    print(f"Confidence: {regime_info.confidence:.1%}")
    print(f"Detected at: {regime_info.timestamp}")
```

**`get_latest_signals(count: int = 10) -> List[TradingSignal]`**
Returns the most recent trading signals generated by the system.

```python
signals = provider.get_latest_signals(5)
for signal in signals:
    print(f"{signal.signal_type} {signal.symbol} @ ${signal.entry_price:.2f}")
    print(f"Confidence: {signal.confidence:.1%}")
    print(f"Strategy: {signal.strategy}")
```

**`get_regime_history(count: int = 100) -> List[RegimeUpdate]`**
Returns historical regime detection results for analysis and backtesting.

```python
history = provider.get_regime_history(20)
for regime_update in history:
    print(f"{regime_update.timestamp}: {regime_update.regime.name}")
```

**`get_market_data(symbol: str = None) -> Dict[str, pd.DataFrame]`**
Returns current market data with technical indicators for specified symbols or all tracked symbols.

```python
data = provider.get_market_data("SPY")
spy_data = data["SPY"]
print(f"Latest price: ${spy_data['Close'].iloc[-1]:.2f}")
print(f"RSI: {spy_data['rsi'].iloc[-1]:.1f}")
```

**`get_status() -> Dict[str, Any]`**
Returns comprehensive system status information including running state, performance metrics, and configuration details.

```python
status = provider.get_status()
print(f"Running: {status['running']}")
print(f"Signals generated: {status['signals_generated']}")
print(f"Last update: {status['last_update']}")
```

### SignalProviderAPI Methods

#### System Control Methods

**`initialize() -> Dict[str, Any]`**
Initializes the underlying signal provider with the specified configuration.

```python
api = SignalProviderAPI(symbols=["SPY"])
result = api.initialize()
if result["success"]:
    print("API initialized successfully")
else:
    print(f"Initialization failed: {result['message']}")
```

**`start() -> Dict[str, Any]`**
Starts the signal provider through the API interface.

```python
result = api.start()
print(f"Start result: {result}")
```

**`stop() -> Dict[str, Any]`**
Stops the signal provider through the API interface.

```python
result = api.stop()
print(f"Stop result: {result}")
```

#### Data Retrieval Methods

**`get_status() -> Dict[str, Any]`**
Returns formatted system status information suitable for display in user interfaces.

```python
status = api.get_status()
print(f"System running: {status['running']}")
print(f"Symbols tracked: {status['symbols']}")
print(f"Models trained: {status['models_trained']}")
```

**`get_current_regime() -> Dict[str, Any]`**
Returns current market regime information in a JSON-serializable format.

```python
regime = api.get_current_regime()
if regime["regime"]:
    print(f"Current regime: {regime['regime']}")
    print(f"Confidence: {regime['confidence']:.1%}")
    print(f"Timestamp: {regime['timestamp']}")
```

**`get_signals(limit: int = 50) -> Dict[str, Any]`**
Returns recent trading signals with comprehensive metadata.

```python
signals_data = api.get_signals(limit=10)
print(f"Total signals: {signals_data['count']}")
for signal in signals_data['signals']:
    print(f"{signal['signal_type']} {signal['symbol']} @ ${signal['entry_price']}")
```

**`get_market_data(symbol: str = None) -> Dict[str, Any]`**
Returns formatted market data suitable for API consumption.

```python
data = api.get_market_data("SPY")
if data["success"]:
    spy_info = data["data"]["SPY"]
    print(f"Latest price: ${spy_info['latest_price']:.2f}")
    print(f"Price change: {spy_info['price_change']:.2%}")
    print(f"RSI: {spy_info['rsi']:.1f}")
```

#### Event Subscription Methods

**`subscribe_to_events(event_type: str, callback_func) -> Dict[str, Any]`**
Registers a callback function to receive real-time event notifications.

```python
def on_regime_change(data):
    print(f"Regime changed: {data['regime']}")

result = api.subscribe_to_events("regime", on_regime_change)
print(f"Subscription result: {result}")
```

**`unsubscribe_from_events(event_type: str, callback_func) -> Dict[str, Any]`**
Removes a previously registered callback function.

```python
result = api.unsubscribe_from_events("regime", on_regime_change)
print(f"Unsubscription result: {result}")
```

### Data Structures

#### TradingSignal

The `TradingSignal` dataclass represents a complete trading recommendation with all necessary information for execution and risk management.

```python
@dataclass
class TradingSignal:
    symbol: str                    # Trading symbol (e.g., "SPY")
    signal_type: str              # "BUY", "SELL", or "HOLD"
    confidence: float             # Signal confidence (0.0 to 1.0)
    regime: MarketRegime          # Market regime when signal generated
    strategy: str                 # Strategy type ("momentum", "mean_reversion", etc.)
    entry_price: float            # Recommended entry price
    stop_loss: Optional[float]    # Stop loss level
    take_profit: Optional[float]  # Take profit level
    position_size: Optional[float] # Recommended position size (as fraction of portfolio)
    timestamp: datetime           # Signal generation timestamp
    metadata: Dict[str, Any]      # Additional signal metadata
```

#### RegimeUpdate

The `RegimeUpdate` dataclass contains comprehensive information about market regime detection results.

```python
@dataclass
class RegimeUpdate:
    regime: MarketRegime              # Detected market regime
    confidence: float                 # Detection confidence (0.0 to 1.0)
    timestamp: datetime               # Detection timestamp
    regime_probabilities: Optional[np.ndarray]  # Probabilities for all regimes
    metadata: Dict[str, Any]          # Additional regime metadata
```

#### MarketData

The `MarketData` dataclass encapsulates market data with technical indicators and metadata.

```python
@dataclass
class MarketData:
    symbol: str                   # Trading symbol
    data: pd.DataFrame           # OHLCV data with technical indicators
    timestamp: datetime          # Data timestamp
    metadata: Dict[str, Any]     # Additional data metadata
```

## PyQt6 Widget Examples

### Basic Regime Display Widget

This example demonstrates how to create a simple widget that displays the current market regime with appropriate visual styling.

```python
class RegimeDisplayWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.integration = SignalProviderIntegration(self)
        self.init_ui()
        self.setup_integration()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Regime label
        self.regime_label = QLabel("Detecting Regime...")
        self.regime_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.regime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.regime_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 2px solid #ccc;
                border-radius: 10px;
                padding: 20px;
                margin: 10px;
            }
        """)
        
        # Confidence bar
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("Confidence:"))
        
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        confidence_layout.addWidget(self.confidence_bar)
        
        self.confidence_label = QLabel("0%")
        confidence_layout.addWidget(self.confidence_label)
        
        # Description
        self.description_label = QLabel("Waiting for regime detection...")
        self.description_label.setWordWrap(True)
        
        layout.addWidget(self.regime_label)
        layout.addLayout(confidence_layout)
        layout.addWidget(self.description_label)
        
        self.setLayout(layout)
    
    def setup_integration(self):
        self.integration.initialize_provider(symbols=["SPY"])
        self.integration.register_callback("regime_changed", self.update_regime_display)
        self.integration.start_provider()
    
    def update_regime_display(self, regime_update):
        regime_info = self.integration.get_current_regime()
        
        # Update regime label
        regime_name = regime_info["regime"].replace("_", " ").title()
        self.regime_label.setText(regime_name)
        
        # Update styling based on regime
        color_map = {
            "Low Volatility Trending": "#4CAF50",      # Green
            "High Volatility Mean Reverting": "#F44336", # Red
            "Transitional Neutral": "#FF9800"          # Orange
        }
        
        color = color_map.get(regime_name, "#999999")
        self.regime_label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: white;
                border: 2px solid {color};
                border-radius: 10px;
                padding: 20px;
                margin: 10px;
            }}
        """)
        
        # Update confidence
        confidence_pct = int(regime_info["confidence"] * 100)
        self.confidence_bar.setValue(confidence_pct)
        self.confidence_label.setText(f"{confidence_pct}%")
        
        # Update description
        descriptions = {
            "Low Volatility Trending": "Market is in a low volatility trending state. Momentum strategies are favored.",
            "High Volatility Mean Reverting": "Market is in a high volatility mean-reverting state. Contrarian strategies are favored.",
            "Transitional Neutral": "Market is in a transitional state. Conservative strategies are recommended."
        }
        
        self.description_label.setText(descriptions.get(regime_name, "Unknown regime state."))
```

### Advanced Signal Table Widget

This example shows how to create a comprehensive signal display table with sorting, filtering, and real-time updates.

```python
class SignalTableWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.integration = SignalProviderIntegration(self)
        self.signals_data = []
        self.init_ui()
        self.setup_integration()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        title = QLabel("Trading Signals")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title)
        
        # Filter controls
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["All Signals", "BUY Only", "SELL Only", "High Confidence"])
        self.filter_combo.currentTextChanged.connect(self.apply_filter)
        header_layout.addWidget(QLabel("Filter:"))
        header_layout.addWidget(self.filter_combo)
        
        header_layout.addStretch()
        
        # Clear button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_signals)
        header_layout.addWidget(clear_button)
        
        layout.addLayout(header_layout)
        
        # Signals table
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(8)
        self.signals_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Signal", "Confidence", "Regime", "Strategy", "Price", "Size"
        ])
        
        # Configure table
        header = self.signals_table.horizontalHeader()
        header.setStretchLastSection(True)
        self.signals_table.setSortingEnabled(True)
        self.signals_table.setAlternatingRowColors(True)
        self.signals_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.signals_table)
        
        # Statistics
        stats_layout = QHBoxLayout()
        
        self.total_label = QLabel("Total: 0")
        self.buy_label = QLabel("Buy: 0")
        self.sell_label = QLabel("Sell: 0")
        self.avg_confidence_label = QLabel("Avg Confidence: 0%")
        
        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.buy_label)
        stats_layout.addWidget(self.sell_label)
        stats_layout.addWidget(self.avg_confidence_label)
        stats_layout.addStretch()
        
        layout.addLayout(stats_layout)
        
        self.setLayout(layout)
    
    def setup_integration(self):
        self.integration.initialize_provider(symbols=["SPY"])
        self.integration.register_callback("signal_generated", self.add_signal)
        self.integration.start_provider()
    
    def add_signal(self, signal):
        # Add to internal data
        signal_data = self.integration.get_recent_signals(1)[0]  # Get formatted signal
        self.signals_data.append(signal_data)
        
        # Keep only last 100 signals
        if len(self.signals_data) > 100:
            self.signals_data = self.signals_data[-100:]
        
        # Update display
        self.update_table()
        self.update_statistics()
    
    def update_table(self):
        # Apply current filter
        filtered_data = self.get_filtered_data()
        
        self.signals_table.setRowCount(len(filtered_data))
        
        for i, signal in enumerate(reversed(filtered_data)):
            # Time
            self.signals_table.setItem(i, 0, QTableWidgetItem(signal["timestamp"]))
            
            # Symbol
            self.signals_table.setItem(i, 1, QTableWidgetItem(signal["symbol"]))
            
            # Signal type with color coding
            signal_item = QTableWidgetItem(signal["signal_type"])
            if signal["signal_type"] == "BUY":
                signal_item.setBackground(QColor(200, 255, 200))
            elif signal["signal_type"] == "SELL":
                signal_item.setBackground(QColor(255, 200, 200))
            self.signals_table.setItem(i, 2, signal_item)
            
            # Confidence
            confidence_item = QTableWidgetItem(signal["confidence"])
            confidence_val = float(signal["confidence"].rstrip('%')) / 100
            if confidence_val >= 0.8:
                confidence_item.setBackground(QColor(200, 255, 200))
            elif confidence_val <= 0.6:
                confidence_item.setBackground(QColor(255, 255, 200))
            self.signals_table.setItem(i, 3, confidence_item)
            
            # Regime
            self.signals_table.setItem(i, 4, QTableWidgetItem(signal["regime"]))
            
            # Strategy
            self.signals_table.setItem(i, 5, QTableWidgetItem(signal["strategy"]))
            
            # Price
            self.signals_table.setItem(i, 6, QTableWidgetItem(signal["price"]))
            
            # Position size
            raw_signal = signal.get("raw_signal")
            size_text = f"{raw_signal.position_size:.1%}" if raw_signal and raw_signal.position_size else "N/A"
            self.signals_table.setItem(i, 7, QTableWidgetItem(size_text))
    
    def get_filtered_data(self):
        filter_type = self.filter_combo.currentText()
        
        if filter_type == "All Signals":
            return self.signals_data
        elif filter_type == "BUY Only":
            return [s for s in self.signals_data if s["signal_type"] == "BUY"]
        elif filter_type == "SELL Only":
            return [s for s in self.signals_data if s["signal_type"] == "SELL"]
        elif filter_type == "High Confidence":
            return [s for s in self.signals_data if float(s["confidence"].rstrip('%')) >= 80]
        
        return self.signals_data
    
    def apply_filter(self):
        self.update_table()
    
    def clear_signals(self):
        self.signals_data.clear()
        self.update_table()
        self.update_statistics()
    
    def update_statistics(self):
        if not self.signals_data:
            self.total_label.setText("Total: 0")
            self.buy_label.setText("Buy: 0")
            self.sell_label.setText("Sell: 0")
            self.avg_confidence_label.setText("Avg Confidence: 0%")
            return
        
        total = len(self.signals_data)
        buy_count = sum(1 for s in self.signals_data if s["signal_type"] == "BUY")
        sell_count = sum(1 for s in self.signals_data if s["signal_type"] == "SELL")
        
        # Calculate average confidence
        confidences = [float(s["confidence"].rstrip('%')) for s in self.signals_data]
        avg_confidence = sum(confidences) / len(confidences)
        
        self.total_label.setText(f"Total: {total}")
        self.buy_label.setText(f"Buy: {buy_count}")
        self.sell_label.setText(f"Sell: {sell_count}")
        self.avg_confidence_label.setText(f"Avg Confidence: {avg_confidence:.1f}%")
```

### System Status Dashboard Widget

This example demonstrates a comprehensive status dashboard that monitors system health and performance.

```python
class StatusDashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.integration = SignalProviderIntegration(self)
        self.init_ui()
        self.setup_integration()
        self.setup_timer()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("System Status Dashboard")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Status grid
        status_group = QGroupBox("System Status")
        status_layout = QGridLayout()
        
        # Status indicators
        self.status_indicators = {}
        indicators = [
            ("System", "status_text", "Unknown"),
            ("Last Update", "last_update", "Never"),
            ("Signals Generated", "signals_count", "0"),
            ("Regime Changes", "regime_changes", "0"),
            ("Symbols Tracked", "symbols", "None"),
            ("Uptime", "uptime", "00:00:00")
        ]
        
        for i, (label, key, default) in enumerate(indicators):
            label_widget = QLabel(f"{label}:")
            label_widget.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            
            value_widget = QLabel(default)
            value_widget.setFont(QFont("Arial", 10))
            value_widget.setStyleSheet("QLabel { color: #2196F3; }")
            
            status_layout.addWidget(label_widget, i, 0)
            status_layout.addWidget(value_widget, i, 1)
            
            self.status_indicators[key] = value_widget
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # Performance metrics
        perf_group = QGroupBox("Performance Metrics")
        perf_layout = QGridLayout()
        
        self.perf_indicators = {}
        perf_metrics = [
            ("Signal Rate", "signal_rate", "0 signals/hour"),
            ("Regime Stability", "regime_stability", "N/A"),
            ("Average Confidence", "avg_confidence", "0%"),
            ("System Load", "system_load", "Normal")
        ]
        
        for i, (label, key, default) in enumerate(perf_metrics):
            label_widget = QLabel(f"{label}:")
            label_widget.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            
            value_widget = QLabel(default)
            value_widget.setFont(QFont("Arial", 10))
            value_widget.setStyleSheet("QLabel { color: #4CAF50; }")
            
            perf_layout.addWidget(label_widget, i, 0)
            perf_layout.addWidget(value_widget, i, 1)
            
            self.perf_indicators[key] = value_widget
        
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)
        
        # Control buttons
        control_group = QGroupBox("System Control")
        control_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.restart_button = QPushButton("Restart")
        self.force_update_button = QPushButton("Force Update")
        
        self.start_button.clicked.connect(self.start_system)
        self.stop_button.clicked.connect(self.stop_system)
        self.restart_button.clicked.connect(self.restart_system)
        self.force_update_button.clicked.connect(self.force_update)
        
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.stop_button)
        control_layout.addWidget(self.restart_button)
        control_layout.addWidget(self.force_update_button)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Log display
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()
        
        self.log_display = QTextEdit()
        self.log_display.setMaximumHeight(150)
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Courier", 9))
        
        log_layout.addWidget(self.log_display)
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
    
    def setup_integration(self):
        self.integration.initialize_provider(symbols=["SPY"])
        self.integration.register_callback("status_changed", self.on_status_changed)
        self.start_time = datetime.now()
    
    def setup_timer(self):
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(5000)  # Update every 5 seconds
    
    def update_status(self):
        status = self.integration.get_system_status()
        
        # Update status indicators
        self.status_indicators["status_text"].setText(status["status_text"])
        self.status_indicators["status_text"].setStyleSheet(f"QLabel {{ color: {status['color']}; }}")
        
        self.status_indicators["last_update"].setText(status["last_update"])
        self.status_indicators["signals_count"].setText(str(status["signals_count"]))
        self.status_indicators["regime_changes"].setText(str(status["regime_changes"]))
        self.status_indicators["symbols"].setText(status["symbols"])
        
        # Calculate uptime
        if status["running"]:
            uptime = datetime.now() - self.start_time
            uptime_str = str(uptime).split('.')[0]  # Remove microseconds
            self.status_indicators["uptime"].setText(uptime_str)
        
        # Update performance metrics
        self.update_performance_metrics()
        
        # Update button states
        self.start_button.setEnabled(not status["running"])
        self.stop_button.setEnabled(status["running"])
        self.restart_button.setEnabled(True)
        self.force_update_button.setEnabled(status["running"])
    
    def update_performance_metrics(self):
        # Get recent signals for performance calculation
        recent_signals = self.integration.get_recent_signals(50)
        
        if recent_signals:
            # Calculate signal rate (signals per hour)
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            recent_hour_signals = [
                s for s in recent_signals 
                if datetime.fromisoformat(s["raw_signal"].timestamp.isoformat()) > hour_ago
            ]
            signal_rate = len(recent_hour_signals)
            self.perf_indicators["signal_rate"].setText(f"{signal_rate} signals/hour")
            
            # Calculate average confidence
            confidences = [float(s["confidence"].rstrip('%')) for s in recent_signals]
            avg_confidence = sum(confidences) / len(confidences)
            self.perf_indicators["avg_confidence"].setText(f"{avg_confidence:.1f}%")
            
            # Set confidence color
            if avg_confidence >= 70:
                color = "#4CAF50"  # Green
            elif avg_confidence >= 50:
                color = "#FF9800"  # Orange
            else:
                color = "#F44336"  # Red
            
            self.perf_indicators["avg_confidence"].setStyleSheet(f"QLabel {{ color: {color}; }}")
        
        # System load (simplified)
        load_text = "Normal"
        load_color = "#4CAF50"
        
        status = self.integration.get_system_status()
        if not status["running"]:
            load_text = "Stopped"
            load_color = "#999999"
        elif status["signals_count"] > 100:
            load_text = "High Activity"
            load_color = "#FF9800"
        
        self.perf_indicators["system_load"].setText(load_text)
        self.perf_indicators["system_load"].setStyleSheet(f"QLabel {{ color: {load_color}; }}")
    
    def start_system(self):
        self.integration.start_provider()
        self.start_time = datetime.now()
        self.add_log_message("System started")
    
    def stop_system(self):
        self.integration.stop_provider()
        self.add_log_message("System stopped")
    
    def restart_system(self):
        self.stop_system()
        QTimer.singleShot(2000, self.start_system)  # Restart after 2 seconds
        self.add_log_message("System restarting...")
    
    def force_update(self):
        self.integration.force_update()
        self.add_log_message("Force update triggered")
    
    def on_status_changed(self, status_data):
        self.add_log_message(f"Status changed: {status_data}")
    
    def add_log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
```

## Configuration and Customization

### Basic Configuration

The signal provider accepts a comprehensive configuration dictionary that controls all aspects of system behavior. Here's how to customize the most important settings:

```python
# Custom configuration example
custom_config = {
    # HMM Model Configuration
    "hmm": {
        "n_components": 3,              # Number of market regimes
        "covariance_type": "diag",      # Covariance matrix type
        "n_iter": 100,                  # Maximum training iterations
        "training_window": 252,         # Training data window (days)
        "min_training_samples": 100,    # Minimum samples for training
        "retrain_frequency": 50         # Retrain every N signals
    },
    
    # Data Processing Configuration
    "data": {
        "update_interval": 30,          # Update interval (seconds)
        "lookback_period": 365,         # Historical data period (days)
        "technical_indicators": True,    # Enable technical indicators
        "data_source": "yahoo"          # Data source identifier
    },
    
    # Trading Strategy Configuration
    "strategy": {
        "min_confidence_threshold": 0.7,    # Minimum regime confidence
        "signal_strength_threshold": 0.6,   # Signal generation threshold
        "max_signals_per_day": 3,           # Maximum daily signals
        "regime_strategies": {
            MarketRegime.LOW_VOLATILITY_TRENDING: {
                "strategy_type": "momentum",
                "features": ["momentum_5", "momentum_10", "rsi", "macd"],
                "signal_threshold": 0.65
            },
            MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: {
                "strategy_type": "mean_reversion", 
                "features": ["rsi", "bb_width", "volatility", "returns"],
                "signal_threshold": 0.70
            },
            MarketRegime.TRANSITIONAL_NEUTRAL: {
                "strategy_type": "conservative",
                "features": ["volatility", "volume_ratio", "rsi"],
                "signal_threshold": 0.75
            }
        }
    },
    
    # Risk Management Configuration
    "risk": {
        "max_position_size": 0.03,      # Maximum position size (3%)
        "volatility_scaling": True,      # Enable volatility scaling
        "position_limits": {
            MarketRegime.LOW_VOLATILITY_TRENDING: 0.60,
            MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: 0.40,
            MarketRegime.TRANSITIONAL_NEUTRAL: 0.20
        }
    }
}

# Create provider with custom configuration
provider = HMMSignalProvider(
    symbols=["SPY", "QQQ"],
    config=custom_config
)
```

### Advanced Customization

For more advanced customization, you can extend the base classes to implement custom behavior:

```python
class CustomHMMSignalProvider(HMMSignalProvider):
    """Custom signal provider with additional features"""
    
    def __init__(self, symbols, config=None, custom_indicators=None):
        super().__init__(symbols, config)
        self.custom_indicators = custom_indicators or []
    
    def _add_technical_indicators(self, data):
        """Override to add custom technical indicators"""
        # Call parent method first
        data = super()._add_technical_indicators(data)
        
        # Add custom indicators
        for indicator_func in self.custom_indicators:
            data = indicator_func(data)
        
        return data
    
    def _map_state_to_regime(self, state, features):
        """Override with custom regime mapping logic"""
        # Implement your custom regime detection logic
        # This example uses a more sophisticated approach
        
        recent_features = features[-30:]  # Last 30 observations
        
        # Calculate multiple characteristics
        volatility_idx = 1
        returns_idx = 0
        rsi_idx = 2 if len(features[0]) > 2 else 1
        
        avg_volatility = np.mean(recent_features[:, volatility_idx])
        returns_autocorr = np.corrcoef(
            recent_features[:-1, returns_idx], 
            recent_features[1:, returns_idx]
        )[0, 1] if len(recent_features) > 1 else 0
        
        avg_rsi = np.mean(recent_features[:, rsi_idx]) if len(features[0]) > 2 else 50
        
        # Custom regime logic
        if avg_volatility < -0.3 and returns_autocorr > 0.1:
            return MarketRegime.LOW_VOLATILITY_TRENDING
        elif avg_volatility > 0.3 and returns_autocorr < -0.1:
            return MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING
        else:
            return MarketRegime.TRANSITIONAL_NEUTRAL

# Custom indicator functions
def custom_momentum_indicator(data):
    """Add custom momentum indicator"""
    data['custom_momentum'] = data['Close'].pct_change(20)  # 20-day momentum
    return data

def custom_volatility_indicator(data):
    """Add custom volatility indicator"""
    data['custom_vol'] = data['returns'].rolling(10).std() * np.sqrt(252)
    return data

# Use custom provider
custom_provider = CustomHMMSignalProvider(
    symbols=["SPY"],
    config=custom_config,
    custom_indicators=[custom_momentum_indicator, custom_volatility_indicator]
)
```

### Multi-Symbol Configuration

For trading multiple symbols with different configurations:

```python
class MultiSymbolSignalProvider:
    """Signal provider for multiple symbols with individual configurations"""
    
    def __init__(self, symbol_configs):
        self.providers = {}
        self.symbol_configs = symbol_configs
        
        for symbol, config in symbol_configs.items():
            self.providers[symbol] = HMMSignalProvider(
                symbols=[symbol],
                config=config
            )
    
    def start_all(self):
        """Start all symbol providers"""
        for provider in self.providers.values():
            provider.start()
    
    def stop_all(self):
        """Stop all symbol providers"""
        for provider in self.providers.values():
            provider.stop()
    
    def get_all_signals(self):
        """Get signals from all providers"""
        all_signals = []
        for symbol, provider in self.providers.items():
            signals = provider.get_latest_signals(10)
            all_signals.extend(signals)
        return sorted(all_signals, key=lambda s: s.timestamp, reverse=True)
    
    def get_all_regimes(self):
        """Get current regimes for all symbols"""
        regimes = {}
        for symbol, provider in self.providers.items():
            regime_info = provider.get_current_regime()
            regimes[symbol] = regime_info
        return regimes

# Example usage
symbol_configs = {
    "SPY": {
        "strategy": {
            "min_confidence_threshold": 0.6,
            "signal_strength_threshold": 0.55
        }
    },
    "QQQ": {
        "strategy": {
            "min_confidence_threshold": 0.7,
            "signal_strength_threshold": 0.60
        }
    },
    "IWM": {
        "strategy": {
            "min_confidence_threshold": 0.65,
            "signal_strength_threshold": 0.58
        }
    }
}

multi_provider = MultiSymbolSignalProvider(symbol_configs)
multi_provider.start_all()
```

## Performance Optimization

### Memory Management

The signal provider includes built-in memory management features, but you can optimize further for your specific use case:

```python
class OptimizedSignalProvider(HMMSignalProvider):
    """Memory-optimized signal provider"""
    
    def __init__(self, symbols, config=None, max_history=500):
        super().__init__(symbols, config)
        self.max_history = max_history
    
    def _on_signal_callback(self, signal):
        """Override to limit signal history"""
        super()._on_signal_callback(signal)
        
        # Limit signal history
        if len(self.signal_history) > self.max_history:
            self.signal_history = self.signal_history[-self.max_history:]
    
    def _on_regime_callback(self, regime_update):
        """Override to limit regime history"""
        super()._on_regime_callback(regime_update)
        
        # Limit regime history
        if len(self.regime_history) > self.max_history:
            self.regime_history = self.regime_history[-self.max_history:]
    
    def cleanup_old_data(self):
        """Periodic cleanup of old data"""
        cutoff_time = datetime.now() - timedelta(days=7)
        
        # Remove old signals
        self.signal_history = [
            s for s in self.signal_history 
            if s.timestamp > cutoff_time
        ]
        
        # Remove old regime updates
        self.regime_history = [
            r for r in self.regime_history 
            if r.timestamp > cutoff_time
        ]
```

### Processing Optimization

For high-frequency applications, you can optimize processing performance:

```python
class HighFrequencySignalProvider(HMMSignalProvider):
    """High-frequency optimized signal provider"""
    
    def __init__(self, symbols, config=None):
        # Optimize configuration for speed
        if config is None:
            config = self._high_frequency_config()
        
        super().__init__(symbols, config)
        
        # Pre-allocate arrays for better performance
        self.feature_buffer = np.zeros((1000, 9))  # Pre-allocated feature buffer
        self.buffer_index = 0
    
    def _high_frequency_config(self):
        """Configuration optimized for high frequency"""
        return {
            "hmm": {
                "n_components": 3,
                "covariance_type": "diag",
                "n_iter": 50,  # Reduced iterations for speed
                "training_window": 100,  # Smaller window
                "retrain_frequency": 25  # More frequent retraining
            },
            "data": {
                "update_interval": 10,  # Faster updates
                "lookback_period": 100,  # Less historical data
                "technical_indicators": True
            },
            "strategy": {
                "min_confidence_threshold": 0.5,  # Lower threshold for more signals
                "signal_strength_threshold": 0.5
            }
        }
    
    def _prepare_hmm_features(self, data):
        """Optimized feature preparation"""
        try:
            # Use pre-allocated buffer when possible
            features = super()._prepare_hmm_features(data)
            
            if features is not None and len(features) <= 1000:
                # Use pre-allocated buffer
                self.feature_buffer[:len(features)] = features
                return self.feature_buffer[:len(features)]
            
            return features
            
        except Exception as e:
            logger.error(f"Error in optimized feature preparation: {e}")
            return None
```

### Concurrent Processing

For applications requiring maximum throughput:

```python
import concurrent.futures
from threading import ThreadPoolExecutor

class ConcurrentSignalProvider:
    """Signal provider with concurrent processing capabilities"""
    
    def __init__(self, symbols, config=None, max_workers=4):
        self.symbols = symbols
        self.config = config
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.providers = {}
        
        # Create individual providers for each symbol
        for symbol in symbols:
            self.providers[symbol] = HMMSignalProvider([symbol], config)
    
    def start_all_concurrent(self):
        """Start all providers concurrently"""
        futures = []
        for provider in self.providers.values():
            future = self.executor.submit(provider.start)
            futures.append(future)
        
        # Wait for all to start
        concurrent.futures.wait(futures, timeout=30)
    
    def get_all_signals_concurrent(self):
        """Get signals from all providers concurrently"""
        futures = {}
        
        for symbol, provider in self.providers.items():
            future = self.executor.submit(provider.get_latest_signals, 10)
            futures[symbol] = future
        
        # Collect results
        all_signals = []
        for symbol, future in futures.items():
            try:
                signals = future.result(timeout=5)
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"Error getting signals for {symbol}: {e}")
        
        return all_signals
    
    def shutdown(self):
        """Shutdown all providers and executor"""
        for provider in self.providers.values():
            provider.stop()
        
        self.executor.shutdown(wait=True)
```

## Error Handling and Monitoring

### Comprehensive Error Handling

Robust error handling is crucial for production deployments:

```python
class RobustSignalProvider(HMMSignalProvider):
    """Signal provider with comprehensive error handling"""
    
    def __init__(self, symbols, config=None, error_callback=None):
        super().__init__(symbols, config)
        self.error_callback = error_callback
        self.error_count = 0
        self.last_error_time = None
        self.max_errors_per_hour = 10
    
    def _handle_error(self, error, context="Unknown"):
        """Centralized error handling"""
        self.error_count += 1
        self.last_error_time = datetime.now()
        
        error_info = {
            "timestamp": self.last_error_time,
            "error": str(error),
            "context": context,
            "error_count": self.error_count
        }
        
        logger.error(f"Error in {context}: {error}")
        
        # Call error callback if provided
        if self.error_callback:
            try:
                self.error_callback(error_info)
            except Exception as callback_error:
                logger.error(f"Error in error callback: {callback_error}")
        
        # Check if error rate is too high
        if self._is_error_rate_too_high():
            logger.critical("Error rate too high, stopping system")
            self.stop()
    
    def _is_error_rate_too_high(self):
        """Check if error rate exceeds threshold"""
        if self.last_error_time is None:
            return False
        
        hour_ago = datetime.now() - timedelta(hours=1)
        if self.last_error_time > hour_ago and self.error_count > self.max_errors_per_hour:
            return True
        
        return False
    
    def _update_market_data(self):
        """Override with error handling"""
        try:
            super()._update_market_data()
        except Exception as e:
            self._handle_error(e, "market_data_update")
    
    def _update_regime_detection(self):
        """Override with error handling"""
        try:
            super()._update_regime_detection()
        except Exception as e:
            self._handle_error(e, "regime_detection")
    
    def _generate_signals(self):
        """Override with error handling"""
        try:
            super()._generate_signals()
        except Exception as e:
            self._handle_error(e, "signal_generation")

# Usage with error monitoring
def error_handler(error_info):
    print(f"Error detected: {error_info['error']} in {error_info['context']}")
    
    # Send alert email, log to database, etc.
    if error_info['error_count'] > 5:
        print("High error count detected - consider investigation")

robust_provider = RobustSignalProvider(
    symbols=["SPY"],
    error_callback=error_handler
)
```

### Health Monitoring

Implement comprehensive health monitoring for production systems:

```python
class HealthMonitor:
    """Health monitoring for signal provider systems"""
    
    def __init__(self, provider, check_interval=60):
        self.provider = provider
        self.check_interval = check_interval
        self.health_history = []
        self.alerts = []
        self.monitoring = False
        self.monitor_thread = None
    
    def start_monitoring(self):
        """Start health monitoring"""
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Health monitoring started")
    
    def stop_monitoring(self):
        """Stop health monitoring"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Health monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.monitoring:
            try:
                health_status = self._check_health()
                self.health_history.append(health_status)
                
                # Keep only last 100 health checks
                if len(self.health_history) > 100:
                    self.health_history = self.health_history[-100:]
                
                # Check for alerts
                self._check_alerts(health_status)
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring: {e}")
                time.sleep(self.check_interval)
    
    def _check_health(self):
        """Perform comprehensive health check"""
        health_status = {
            "timestamp": datetime.now(),
            "overall_health": "healthy",
            "checks": {}
        }
        
        try:
            # Check if provider is running
            status = self.provider.get_status()
            health_status["checks"]["running"] = {
                "status": "pass" if status["running"] else "fail",
                "value": status["running"]
            }
            
            # Check last update time
            if status["last_update"]:
                time_since_update = (datetime.now() - status["last_update"]).total_seconds()
                health_status["checks"]["data_freshness"] = {
                    "status": "pass" if time_since_update < 300 else "warn",  # 5 minutes
                    "value": f"{time_since_update:.0f} seconds"
                }
            
            # Check signal generation rate
            signals = self.provider.get_latest_signals(10)
            if signals:
                latest_signal_time = max(s.timestamp for s in signals)
                time_since_signal = (datetime.now() - latest_signal_time).total_seconds()
                health_status["checks"]["signal_generation"] = {
                    "status": "pass" if time_since_signal < 3600 else "warn",  # 1 hour
                    "value": f"{time_since_signal:.0f} seconds since last signal"
                }
            
            # Check regime detection
            regime_info = self.provider.get_current_regime()
            if regime_info:
                health_status["checks"]["regime_detection"] = {
                    "status": "pass" if regime_info.confidence > 0.5 else "warn",
                    "value": f"{regime_info.confidence:.1%} confidence"
                }
            
            # Determine overall health
            failed_checks = [c for c in health_status["checks"].values() if c["status"] == "fail"]
            warn_checks = [c for c in health_status["checks"].values() if c["status"] == "warn"]
            
            if failed_checks:
                health_status["overall_health"] = "unhealthy"
            elif warn_checks:
                health_status["overall_health"] = "degraded"
            
        except Exception as e:
            health_status["overall_health"] = "error"
            health_status["error"] = str(e)
        
        return health_status
    
    def _check_alerts(self, health_status):
        """Check for alert conditions"""
        if health_status["overall_health"] == "unhealthy":
            alert = {
                "timestamp": datetime.now(),
                "level": "critical",
                "message": "System health check failed",
                "details": health_status
            }
            self.alerts.append(alert)
            logger.critical(f"Health alert: {alert['message']}")
        
        elif health_status["overall_health"] == "degraded":
            alert = {
                "timestamp": datetime.now(),
                "level": "warning", 
                "message": "System health degraded",
                "details": health_status
            }
            self.alerts.append(alert)
            logger.warning(f"Health alert: {alert['message']}")
    
    def get_health_summary(self):
        """Get current health summary"""
        if not self.health_history:
            return {"status": "no_data", "message": "No health data available"}
        
        latest = self.health_history[-1]
        
        # Calculate uptime percentage
        recent_checks = self.health_history[-20:]  # Last 20 checks
        healthy_checks = sum(1 for h in recent_checks if h["overall_health"] == "healthy")
        uptime_pct = (healthy_checks / len(recent_checks)) * 100
        
        return {
            "current_status": latest["overall_health"],
            "uptime_percentage": uptime_pct,
            "last_check": latest["timestamp"],
            "recent_alerts": len([a for a in self.alerts if a["timestamp"] > datetime.now() - timedelta(hours=24)]),
            "checks": latest["checks"]
        }

# Usage
provider = HMMSignalProvider(symbols=["SPY"])
monitor = HealthMonitor(provider)

provider.start()
monitor.start_monitoring()

# Get health summary
health = monitor.get_health_summary()
print(f"System health: {health}")
```

## Advanced Integration Scenarios

### Integration with Existing Risk Management Systems

For integration with sophisticated risk management systems:

```python
class RiskIntegratedSignalProvider:
    """Signal provider integrated with external risk management"""
    
    def __init__(self, symbols, config=None, risk_manager=None):
        self.signal_provider = HMMSignalProvider(symbols, config)
        self.risk_manager = risk_manager
        self.approved_signals = []
        self.rejected_signals = []
        
        # Set up signal processing pipeline
        self.signal_provider.signal_callback = self._process_signal_with_risk
    
    def _process_signal_with_risk(self, signal):
        """Process signals through risk management"""
        try:
            # Get current portfolio state
            portfolio_state = self.risk_manager.get_portfolio_state()
            
            # Perform risk assessment
            risk_assessment = self.risk_manager.assess_signal_risk(
                signal, portfolio_state
            )
            
            if risk_assessment["approved"]:
                # Adjust signal based on risk parameters
                adjusted_signal = self._adjust_signal_for_risk(signal, risk_assessment)
                self.approved_signals.append(adjusted_signal)
                
                # Notify subscribers of approved signal
                self._notify_approved_signal(adjusted_signal)
                
            else:
                # Log rejection reason
                rejection_info = {
                    "signal": signal,
                    "rejection_reason": risk_assessment["reason"],
                    "timestamp": datetime.now()
                }
                self.rejected_signals.append(rejection_info)
                
                # Notify subscribers of rejection
                self._notify_rejected_signal(rejection_info)
                
        except Exception as e:
            logger.error(f"Error in risk-integrated signal processing: {e}")
    
    def _adjust_signal_for_risk(self, signal, risk_assessment):
        """Adjust signal parameters based on risk assessment"""
        adjusted_signal = TradingSignal(
            symbol=signal.symbol,
            signal_type=signal.signal_type,
            confidence=signal.confidence,
            regime=signal.regime,
            strategy=signal.strategy,
            entry_price=signal.entry_price,
            stop_loss=risk_assessment.get("adjusted_stop_loss", signal.stop_loss),
            take_profit=risk_assessment.get("adjusted_take_profit", signal.take_profit),
            position_size=risk_assessment.get("adjusted_position_size", signal.position_size),
            metadata={
                **signal.metadata,
                "risk_adjusted": True,
                "original_position_size": signal.position_size,
                "risk_score": risk_assessment.get("risk_score", 0)
            }
        )
        
        return adjusted_signal

class ExternalRiskManager:
    """Example external risk management system"""
    
    def __init__(self, portfolio_limit=100000, max_position_pct=0.05):
        self.portfolio_limit = portfolio_limit
        self.max_position_pct = max_position_pct
        self.current_positions = {}
        self.daily_pnl = 0
    
    def get_portfolio_state(self):
        """Get current portfolio state"""
        total_exposure = sum(abs(pos["value"]) for pos in self.current_positions.values())
        
        return {
            "total_value": self.portfolio_limit,
            "total_exposure": total_exposure,
            "available_capital": self.portfolio_limit - total_exposure,
            "daily_pnl": self.daily_pnl,
            "position_count": len(self.current_positions)
        }
    
    def assess_signal_risk(self, signal, portfolio_state):
        """Assess risk for a trading signal"""
        assessment = {
            "approved": False,
            "reason": "",
            "risk_score": 0,
            "adjustments": {}
        }
        
        # Calculate position value
        position_value = signal.position_size * self.portfolio_limit
        
        # Check position size limits
        max_position_value = self.portfolio_limit * self.max_position_pct
        if position_value > max_position_value:
            assessment["adjustments"]["adjusted_position_size"] = max_position_value / self.portfolio_limit
            position_value = max_position_value
        
        # Check available capital
        if position_value > portfolio_state["available_capital"]:
            assessment["reason"] = "Insufficient available capital"
            return assessment
        
        # Check daily loss limits
        if portfolio_state["daily_pnl"] < -self.portfolio_limit * 0.02:  # 2% daily loss limit
            assessment["reason"] = "Daily loss limit exceeded"
            return assessment
        
        # Check concentration risk
        if signal.symbol in self.current_positions:
            existing_value = abs(self.current_positions[signal.symbol]["value"])
            total_symbol_exposure = existing_value + position_value
            if total_symbol_exposure > self.portfolio_limit * 0.10:  # 10% symbol limit
                assessment["reason"] = "Symbol concentration limit exceeded"
                return assessment
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(signal, portfolio_state)
        assessment["risk_score"] = risk_score
        
        # Approve if risk is acceptable
        if risk_score <= 1.0:
            assessment["approved"] = True
        else:
            assessment["reason"] = f"Risk score too high: {risk_score:.2f}"
        
        return assessment
    
    def _calculate_risk_score(self, signal, portfolio_state):
        """Calculate overall risk score"""
        # Base risk from position size
        size_risk = (signal.position_size or 0.02) / self.max_position_pct
        
        # Confidence risk (lower confidence = higher risk)
        confidence_risk = 2.0 - signal.confidence
        
        # Portfolio exposure risk
        exposure_risk = portfolio_state["total_exposure"] / self.portfolio_limit
        
        # Regime risk
        regime_risk_multipliers = {
            MarketRegime.LOW_VOLATILITY_TRENDING: 0.8,
            MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: 1.2,
            MarketRegime.TRANSITIONAL_NEUTRAL: 1.0
        }
        regime_risk = regime_risk_multipliers.get(signal.regime, 1.0)
        
        # Combined risk score
        total_risk = (size_risk + confidence_risk + exposure_risk) * regime_risk
        
        return total_risk
```

### Integration with Order Management Systems

For integration with order management and execution systems:

```python
class OrderManagementIntegration:
    """Integration with order management systems"""
    
    def __init__(self, signal_provider, order_manager):
        self.signal_provider = signal_provider
        self.order_manager = order_manager
        self.active_orders = {}
        self.order_history = []
        
        # Set up signal processing
        self.signal_provider.signal_callback = self._process_signal_for_execution
    
    def _process_signal_for_execution(self, signal):
        """Convert signals to orders"""
        try:
            # Create order from signal
            order = self._create_order_from_signal(signal)
            
            # Submit order to order management system
            order_id = self.order_manager.submit_order(order)
            
            if order_id:
                # Track active order
                self.active_orders[order_id] = {
                    "signal": signal,
                    "order": order,
                    "submit_time": datetime.now(),
                    "status": "submitted"
                }
                
                logger.info(f"Order submitted: {order_id} for signal {signal.signal_type} {signal.symbol}")
            
        except Exception as e:
            logger.error(f"Error processing signal for execution: {e}")
    
    def _create_order_from_signal(self, signal):
        """Create order object from trading signal"""
        order = {
            "symbol": signal.symbol,
            "side": "buy" if signal.signal_type == "BUY" else "sell",
            "quantity": self._calculate_quantity(signal),
            "order_type": "limit",
            "limit_price": signal.entry_price,
            "time_in_force": "day",
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "metadata": {
                "signal_id": id(signal),
                "regime": signal.regime.name,
                "strategy": signal.strategy,
                "confidence": signal.confidence
            }
        }
        
        return order
    
    def _calculate_quantity(self, signal):
        """Calculate order quantity from signal"""
        # Get current portfolio value
        portfolio_value = self.order_manager.get_portfolio_value()
        
        # Calculate position value
        position_value = portfolio_value * (signal.position_size or 0.02)
        
        # Calculate quantity
        quantity = int(position_value / signal.entry_price)
        
        return max(quantity, 1)  # Minimum 1 share
    
    def monitor_orders(self):
        """Monitor active orders and update status"""
        for order_id, order_info in list(self.active_orders.items()):
            try:
                # Get order status from order manager
                status = self.order_manager.get_order_status(order_id)
                
                if status["status"] != order_info["status"]:
                    # Status changed
                    order_info["status"] = status["status"]
                    order_info["last_update"] = datetime.now()
                    
                    if status["status"] in ["filled", "cancelled", "rejected"]:
                        # Order completed, move to history
                        order_info["completion_time"] = datetime.now()
                        self.order_history.append(order_info)
                        del self.active_orders[order_id]
                        
                        logger.info(f"Order {order_id} completed with status: {status['status']}")
                
            except Exception as e:
                logger.error(f"Error monitoring order {order_id}: {e}")

class MockOrderManager:
    """Mock order management system for testing"""
    
    def __init__(self):
        self.orders = {}
        self.next_order_id = 1
        self.portfolio_value = 100000
    
    def submit_order(self, order):
        """Submit an order"""
        order_id = f"ORD_{self.next_order_id:06d}"
        self.next_order_id += 1
        
        self.orders[order_id] = {
            **order,
            "order_id": order_id,
            "status": "submitted",
            "submit_time": datetime.now()
        }
        
        return order_id
    
    def get_order_status(self, order_id):
        """Get order status"""
        if order_id not in self.orders:
            return {"status": "not_found"}
        
        order = self.orders[order_id]
        
        # Simulate order progression
        elapsed = (datetime.now() - order["submit_time"]).total_seconds()
        
        if elapsed > 60:  # After 1 minute, mark as filled
            order["status"] = "filled"
        elif elapsed > 30:  # After 30 seconds, mark as partially filled
            order["status"] = "partially_filled"
        
        return {"status": order["status"], "order": order}
    
    def get_portfolio_value(self):
        """Get current portfolio value"""
        return self.portfolio_value
```

### Integration with Backtesting Systems

For integration with backtesting and strategy validation systems:

```python
class BacktestingIntegration:
    """Integration with backtesting systems"""
    
    def __init__(self, signal_provider, historical_data):
        self.signal_provider = signal_provider
        self.historical_data = historical_data
        self.backtest_results = []
        self.current_positions = {}
        self.portfolio_value = 100000
        self.initial_value = 100000
    
    def run_historical_backtest(self, start_date, end_date):
        """Run backtest on historical data"""
        logger.info(f"Starting backtest from {start_date} to {end_date}")
        
        # Filter historical data
        backtest_data = self.historical_data[
            (self.historical_data.index >= start_date) & 
            (self.historical_data.index <= end_date)
        ]
        
        results = []
        
        for date, row in backtest_data.iterrows():
            # Update signal provider with historical data
            daily_data = self.historical_data[self.historical_data.index <= date].tail(252)
            
            # Simulate signal generation
            signals = self._simulate_signal_generation(daily_data, date)
            
            # Process signals
            for signal in signals:
                trade_result = self._execute_backtest_trade(signal, row)
                if trade_result:
                    results.append(trade_result)
            
            # Update portfolio value
            self._update_portfolio_value(row)
        
        # Calculate performance metrics
        performance = self._calculate_backtest_performance(results)
        
        return {
            "trades": results,
            "performance": performance,
            "final_value": self.portfolio_value,
            "total_return": (self.portfolio_value - self.initial_value) / self.initial_value
        }
    
    def _simulate_signal_generation(self, data, current_date):
        """Simulate signal generation for historical data"""
        # This would integrate with your signal provider's logic
        # For demonstration, we'll create mock signals
        
        signals = []
        
        # Add technical indicators
        data_with_indicators = self.signal_provider._add_technical_indicators(data.copy())
        
        # Prepare features
        features = self.signal_provider._prepare_hmm_features(data_with_indicators)
        
        if features is not None and len(features) > 50:
            # Train HMM model
            self.signal_provider._train_hmm_model(features)
            
            # Predict regime
            regime, confidence, _ = self.signal_provider._predict_regime(features)
            
            if regime and confidence > 0.6:
                # Generate signal based on regime
                signal = self._generate_backtest_signal(data_with_indicators, regime, confidence, current_date)
                if signal:
                    signals.append(signal)
        
        return signals
    
    def _generate_backtest_signal(self, data, regime, confidence, date):
        """Generate signal for backtesting"""
        latest_price = data['Close'].iloc[-1]
        
        # Simple signal generation logic for backtesting
        if regime == MarketRegime.LOW_VOLATILITY_TRENDING:
            # Momentum signal
            momentum = data['Close'].pct_change(5).iloc[-1]
            if momentum > 0.02:  # 2% momentum
                return TradingSignal(
                    symbol="SPY",
                    signal_type="BUY",
                    confidence=confidence,
                    regime=regime,
                    strategy="momentum",
                    entry_price=latest_price,
                    position_size=0.02,
                    timestamp=date
                )
        
        elif regime == MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING:
            # Mean reversion signal
            rsi = data['rsi'].iloc[-1] if 'rsi' in data.columns else 50
            if rsi > 70:  # Overbought
                return TradingSignal(
                    symbol="SPY",
                    signal_type="SELL",
                    confidence=confidence,
                    regime=regime,
                    strategy="mean_reversion",
                    entry_price=latest_price,
                    position_size=0.02,
                    timestamp=date
                )
        
        return None
    
    def _execute_backtest_trade(self, signal, market_data):
        """Execute trade in backtest"""
        try:
            position_value = self.portfolio_value * signal.position_size
            shares = int(position_value / signal.entry_price)
            
            if shares == 0:
                return None
            
            trade = {
                "date": signal.timestamp,
                "symbol": signal.symbol,
                "signal_type": signal.signal_type,
                "entry_price": signal.entry_price,
                "shares": shares,
                "position_value": position_value,
                "regime": signal.regime.name,
                "confidence": signal.confidence
            }
            
            # Update portfolio
            if signal.signal_type == "BUY":
                self.portfolio_value -= position_value
                self.current_positions[signal.symbol] = {
                    "shares": shares,
                    "entry_price": signal.entry_price,
                    "entry_date": signal.timestamp
                }
            
            elif signal.signal_type == "SELL" and signal.symbol in self.current_positions:
                position = self.current_positions[signal.symbol]
                exit_value = position["shares"] * signal.entry_price
                self.portfolio_value += exit_value
                
                # Calculate trade P&L
                trade["exit_price"] = signal.entry_price
                trade["pnl"] = exit_value - (position["shares"] * position["entry_price"])
                trade["return_pct"] = trade["pnl"] / (position["shares"] * position["entry_price"])
                
                del self.current_positions[signal.symbol]
            
            return trade
            
        except Exception as e:
            logger.error(f"Error executing backtest trade: {e}")
            return None
    
    def _update_portfolio_value(self, market_data):
        """Update portfolio value based on current positions"""
        current_price = market_data['Close']
        
        # Update value of current positions
        for symbol, position in self.current_positions.items():
            if symbol == "SPY":  # Assuming we're only trading SPY in backtest
                position_value = position["shares"] * current_price
                # This would be added to cash value in a full implementation
    
    def _calculate_backtest_performance(self, trades):
        """Calculate performance metrics from backtest results"""
        if not trades:
            return {}
        
        df_trades = pd.DataFrame(trades)
        
        # Filter completed trades (with P&L)
        completed_trades = df_trades[df_trades['pnl'].notna()]
        
        if len(completed_trades) == 0:
            return {"message": "No completed trades"}
        
        # Calculate metrics
        total_trades = len(completed_trades)
        winning_trades = len(completed_trades[completed_trades['pnl'] > 0])
        losing_trades = len(completed_trades[completed_trades['pnl'] < 0])
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_win = completed_trades[completed_trades['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = completed_trades[completed_trades['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        total_pnl = completed_trades['pnl'].sum()
        
        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "average_win": avg_win,
            "average_loss": avg_loss,
            "total_pnl": total_pnl,
            "profit_factor": abs(avg_win * winning_trades / (avg_loss * losing_trades)) if avg_loss != 0 and losing_trades > 0 else float('inf')
        }
```

## Troubleshooting Guide

### Common Issues and Solutions

#### Issue: Signal Provider Not Starting

**Symptoms**: Provider appears to start but no signals are generated, regime detection fails

**Possible Causes**:
1. Network connectivity issues preventing data download
2. Invalid symbol configuration
3. Insufficient historical data
4. Configuration errors

**Solutions**:
```python
# Debug startup issues
def debug_startup_issues(provider):
    """Debug common startup issues"""
    
    # Check network connectivity
    try:
        import requests
        response = requests.get("https://finance.yahoo.com", timeout=10)
        print(f"Network connectivity: {'OK' if response.status_code == 200 else 'FAILED'}")
    except Exception as e:
        print(f"Network connectivity: FAILED - {e}")
    
    # Check symbol validity
    for symbol in provider.symbols:
        try:
            data = yf.download(symbol, period="5d", progress=False)
            print(f"Symbol {symbol}: {'OK' if not data.empty else 'FAILED - No data'}")
        except Exception as e:
            print(f"Symbol {symbol}: FAILED - {e}")
    
    # Check configuration
    config = provider.config
    required_sections = ["hmm", "data", "strategy", "risk"]
    for section in required_sections:
        if section in config:
            print(f"Config section {section}: OK")
        else:
            print(f"Config section {section}: MISSING")
    
    # Check data processing
    try:
        provider.force_update()
        status = provider.get_status()
        print(f"Force update: {'OK' if status['last_update'] else 'FAILED'}")
    except Exception as e:
        print(f"Force update: FAILED - {e}")

# Usage
provider = HMMSignalProvider(symbols=["SPY"])
debug_startup_issues(provider)
```

#### Issue: Poor Signal Quality

**Symptoms**: Signals generated but with low confidence or poor performance

**Possible Causes**:
1. Insufficient training data
2. Market regime not properly detected
3. Feature engineering issues
4. Model parameters need tuning

**Solutions**:
```python
def diagnose_signal_quality(provider):
    """Diagnose signal quality issues"""
    
    # Check training data quantity
    if "SPY" in provider.market_data:
        data_length = len(provider.market_data["SPY"])
        min_required = provider.config["hmm"]["min_training_samples"]
        print(f"Training data: {data_length} samples (minimum: {min_required})")
        
        if data_length < min_required:
            print("WARNING: Insufficient training data")
    
    # Check regime detection
    regime_info = provider.get_current_regime()
    if regime_info:
        print(f"Current regime: {regime_info.regime.name}")
        print(f"Regime confidence: {regime_info.confidence:.1%}")
        
        if regime_info.confidence < 0.6:
            print("WARNING: Low regime confidence")
    else:
        print("WARNING: No regime detected")
    
    # Check feature quality
    if "SPY" in provider.market_data:
        data = provider.market_data["SPY"]
        features = provider._prepare_hmm_features(data)
        
        if features is not None:
            # Check for NaN values
            nan_count = np.isnan(features).sum()
            print(f"Feature NaN count: {nan_count}")
            
            # Check feature variance
            feature_vars = np.var(features, axis=0)
            low_var_features = np.sum(feature_vars < 0.001)
            print(f"Low variance features: {low_var_features}")
            
            if nan_count > 0:
                print("WARNING: Features contain NaN values")
            if low_var_features > 0:
                print("WARNING: Some features have very low variance")
    
    # Check recent signals
    recent_signals = provider.get_latest_signals(10)
    if recent_signals:
        avg_confidence = np.mean([s.confidence for s in recent_signals])
        print(f"Average signal confidence: {avg_confidence:.1%}")
        
        if avg_confidence < 0.6:
            print("WARNING: Low average signal confidence")
    else:
        print("WARNING: No recent signals generated")

# Usage
diagnose_signal_quality(provider)
```

#### Issue: High Memory Usage

**Symptoms**: Memory usage grows over time, system becomes slow

**Possible Causes**:
1. Signal history not being limited
2. Market data accumulation
3. Memory leaks in callbacks

**Solutions**:
```python
def optimize_memory_usage(provider):
    """Optimize memory usage"""
    
    # Limit signal history
    max_signals = 1000
    if len(provider.signal_history) > max_signals:
        provider.signal_history = provider.signal_history[-max_signals:]
        print(f"Trimmed signal history to {max_signals} signals")
    
    # Limit regime history
    max_regimes = 1000
    if len(provider.regime_history) > max_regimes:
        provider.regime_history = provider.regime_history[-max_regimes:]
        print(f"Trimmed regime history to {max_regimes} entries")
    
    # Clean up old market data
    for symbol, data in provider.market_data.items():
        if len(data) > 500:  # Keep only last 500 days
            provider.market_data[symbol] = data.tail(500)
            print(f"Trimmed market data for {symbol} to 500 days")
    
    # Force garbage collection
    import gc
    gc.collect()
    print("Forced garbage collection")

# Set up periodic memory optimization
def setup_memory_optimization(provider, interval=3600):
    """Set up periodic memory optimization"""
    
    def memory_cleanup():
        optimize_memory_usage(provider)
        # Schedule next cleanup
        threading.Timer(interval, memory_cleanup).start()
    
    # Start cleanup timer
    threading.Timer(interval, memory_cleanup).start()
    print(f"Memory optimization scheduled every {interval} seconds")
```

#### Issue: API Timeouts

**Symptoms**: API calls hang or timeout, system becomes unresponsive

**Possible Causes**:
1. Network latency issues
2. Heavy processing blocking threads
3. Deadlocks in threading

**Solutions**:
```python
def add_timeout_protection(api):
    """Add timeout protection to API calls"""
    
    import signal
    from contextlib import contextmanager
    
    @contextmanager
    def timeout(duration):
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Operation timed out after {duration} seconds")
        
        # Set the signal handler
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(duration)
        
        try:
            yield
        finally:
            signal.alarm(0)  # Disable the alarm
    
    # Wrap API methods with timeout protection
    original_get_status = api.get_status
    
    def get_status_with_timeout():
        try:
            with timeout(10):  # 10 second timeout
                return original_get_status()
        except TimeoutError:
            return {"error": "Status request timed out"}
    
    api.get_status = get_status_with_timeout
    
    print("Added timeout protection to API methods")

# Usage
api = SignalProviderAPI(symbols=["SPY"])
add_timeout_protection(api)
```

### Performance Troubleshooting

#### Slow Signal Generation

```python
def profile_signal_generation(provider):
    """Profile signal generation performance"""
    import time
    import cProfile
    import pstats
    
    # Profile the signal generation process
    profiler = cProfile.Profile()
    
    start_time = time.time()
    profiler.enable()
    
    # Force signal generation
    provider.force_update()
    
    profiler.disable()
    end_time = time.time()
    
    # Print timing results
    total_time = end_time - start_time
    print(f"Total signal generation time: {total_time:.2f} seconds")
    
    # Print profiling results
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # Top 10 functions
    
    # Identify bottlenecks
    if total_time > 5:
        print("WARNING: Signal generation is slow")
        print("Consider:")
        print("- Reducing training window size")
        print("- Simplifying feature calculations")
        print("- Using faster data sources")

# Usage
profile_signal_generation(provider)
```

#### High CPU Usage

```python
def monitor_cpu_usage(provider, duration=60):
    """Monitor CPU usage during operation"""
    import psutil
    import threading
    
    cpu_samples = []
    monitoring = True
    
    def cpu_monitor():
        while monitoring:
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_samples.append(cpu_percent)
    
    # Start monitoring
    monitor_thread = threading.Thread(target=cpu_monitor, daemon=True)
    monitor_thread.start()
    
    # Run for specified duration
    time.sleep(duration)
    monitoring = False
    
    # Analyze results
    if cpu_samples:
        avg_cpu = np.mean(cpu_samples)
        max_cpu = np.max(cpu_samples)
        
        print(f"Average CPU usage: {avg_cpu:.1f}%")
        print(f"Maximum CPU usage: {max_cpu:.1f}%")
        
        if avg_cpu > 50:
            print("WARNING: High average CPU usage")
            print("Consider:")
            print("- Increasing update intervals")
            print("- Reducing number of symbols")
            print("- Optimizing feature calculations")
        
        if max_cpu > 90:
            print("WARNING: CPU spikes detected")
            print("Consider:")
            print("- Implementing rate limiting")
            print("- Using background processing")

# Usage
monitor_cpu_usage(provider, duration=120)
```

### Integration Troubleshooting

#### PyQt6 Integration Issues

```python
def debug_pyqt6_integration(integration):
    """Debug PyQt6 integration issues"""
    
    # Check PyQt6 availability
    try:
        from PyQt6.QtWidgets import QApplication
        print("PyQt6: Available")
    except ImportError as e:
        print(f"PyQt6: NOT AVAILABLE - {e}")
        return
    
    # Check integration setup
    if integration.signal_provider is None:
        print("ERROR: Signal provider not initialized")
        return
    
    # Check callback registration
    callback_count = sum(len(callbacks) for callbacks in integration.custom_callbacks.values())
    print(f"Registered callbacks: {callback_count}")
    
    # Check provider status
    if hasattr(integration.signal_provider, 'running'):
        print(f"Provider running: {integration.signal_provider.running}")
    
    # Test callback functionality
    def test_callback(data):
        print(f"Test callback received: {type(data)}")
    
    integration.register_callback("regime_changed", test_callback)
    
    # Trigger a test update
    try:
        integration.force_update()
        print("Force update: SUCCESS")
    except Exception as e:
        print(f"Force update: FAILED - {e}")

# Usage
integration = SignalProviderIntegration()
integration.initialize_provider(symbols=["SPY"])
debug_pyqt6_integration(integration)
```

This comprehensive integration guide provides everything needed to successfully integrate the HMM Signal Provider with existing PyQt6 trading systems. The modular design, extensive examples, and thorough troubleshooting information ensure that developers can implement sophisticated market regime detection and signal generation capabilities with confidence and reliability.

