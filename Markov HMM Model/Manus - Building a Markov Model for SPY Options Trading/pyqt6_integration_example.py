#!/usr/bin/env python3
"""
PyQt6 Integration Example for HMM Signal Provider
Demonstrates how to integrate the streamlined HMM signal provider
with existing PyQt6 dashboards.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import sys
import os
from datetime import datetime
from typing import Dict, Any

# PyQt6 imports (only for demonstration - remove if not needed)
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
        QGroupBox, QProgressBar
    )
    from PyQt6.QtCore import QTimer, QThread, pyqtSignal, QObject, Qt
    from PyQt6.QtGui import QFont, QColor
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False
    print("PyQt6 not available - showing integration patterns only")

# Import our signal provider
from hmm_signal_provider import (
    HMMSignalProvider, TradingSignal, RegimeUpdate, MarketData,
    MarketRegime, create_signal_provider
)

class SignalProviderIntegration:
    """
    Integration class for connecting HMM Signal Provider to PyQt6 applications
    This class provides a clean interface between the signal provider and your GUI
    """
    
    def __init__(self, parent_widget=None):
        """
        Initialize the integration
        
        Args:
            parent_widget: Parent PyQt6 widget (optional)
        """
        self.parent_widget = parent_widget
        self.signal_provider = None
        
        # Data storage for GUI updates
        self.latest_regime = None
        self.latest_signals = []
        self.market_data_cache = {}
        
        # Callback registry for custom handlers
        self.custom_callbacks = {
            "regime_changed": [],
            "signal_generated": [],
            "data_updated": [],
            "status_changed": []
        }
    
    def initialize_provider(self, symbols=None, config=None):
        """
        Initialize the HMM signal provider with callbacks
        
        Args:
            symbols: List of symbols to track
            config: Configuration dictionary
        """
        # Create signal provider with integrated callbacks
        self.signal_provider = create_signal_provider(
            symbols=symbols or ["SPY"],
            config=config,
            callbacks={
                "data": self._on_data_update,
                "regime": self._on_regime_update,
                "signal": self._on_signal_generated
            }
        )
        
        return self.signal_provider
    
    def start_provider(self):
        """Start the signal provider"""
        if self.signal_provider:
            self.signal_provider.start()
            self._trigger_callbacks("status_changed", {"status": "started"})
    
    def stop_provider(self):
        """Stop the signal provider"""
        if self.signal_provider:
            self.signal_provider.stop()
            self._trigger_callbacks("status_changed", {"status": "stopped"})
    
    # Callback methods for signal provider events
    
    def _on_data_update(self, market_data: MarketData):
        """Handle market data updates"""
        self.market_data_cache[market_data.symbol] = market_data
        self._trigger_callbacks("data_updated", market_data)
    
    def _on_regime_update(self, regime_update: RegimeUpdate):
        """Handle regime updates"""
        self.latest_regime = regime_update
        self._trigger_callbacks("regime_changed", regime_update)
    
    def _on_signal_generated(self, signal: TradingSignal):
        """Handle new trading signals"""
        self.latest_signals.append(signal)
        # Keep only last 50 signals
        if len(self.latest_signals) > 50:
            self.latest_signals = self.latest_signals[-50:]
        
        self._trigger_callbacks("signal_generated", signal)
    
    # Public API for PyQt6 integration
    
    def register_callback(self, event_type: str, callback_func):
        """
        Register a custom callback function
        
        Args:
            event_type: Type of event ("regime_changed", "signal_generated", etc.)
            callback_func: Function to call when event occurs
        """
        if event_type in self.custom_callbacks:
            self.custom_callbacks[event_type].append(callback_func)
    
    def _trigger_callbacks(self, event_type: str, data):
        """Trigger all registered callbacks for an event type"""
        for callback in self.custom_callbacks.get(event_type, []):
            try:
                callback(data)
            except Exception as e:
                print(f"Error in callback {callback.__name__}: {e}")
    
    def get_current_regime(self) -> Dict[str, Any]:
        """Get current regime information for GUI display"""
        if not self.latest_regime:
            return {"regime": "Unknown", "confidence": 0.0, "color": "#999999"}
        
        # Map regime to display properties
        regime_info = {
            "regime": self.latest_regime.regime.name.replace("_", " ").title(),
            "confidence": self.latest_regime.confidence,
            "timestamp": self.latest_regime.timestamp,
            "raw_regime": self.latest_regime.regime
        }
        
        # Add color coding for GUI
        color_map = {
            MarketRegime.LOW_VOLATILITY_TRENDING: "#4CAF50",  # Green
            MarketRegime.HIGH_VOLATILITY_MEAN_REVERTING: "#F44336",  # Red
            MarketRegime.TRANSITIONAL_NEUTRAL: "#FF9800"  # Orange
        }
        regime_info["color"] = color_map.get(self.latest_regime.regime, "#999999")
        
        return regime_info
    
    def get_recent_signals(self, count: int = 10) -> list:
        """Get recent signals formatted for GUI display"""
        signals = self.latest_signals[-count:] if self.latest_signals else []
        
        formatted_signals = []
        for signal in signals:
            formatted_signals.append({
                "timestamp": signal.timestamp.strftime("%H:%M:%S"),
                "symbol": signal.symbol,
                "signal_type": signal.signal_type,
                "confidence": f"{signal.confidence:.1%}",
                "regime": signal.regime.name.replace("_", " ").title(),
                "strategy": signal.strategy.title(),
                "price": f"${signal.entry_price:.2f}",
                "raw_signal": signal
            })
        
        return formatted_signals
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status for GUI display"""
        if not self.signal_provider:
            return {"status": "Not Initialized", "color": "#999999"}
        
        status = self.signal_provider.get_status()
        
        # Format for GUI
        gui_status = {
            "running": status["running"],
            "status_text": "Running" if status["running"] else "Stopped",
            "color": "#4CAF50" if status["running"] else "#F44336",
            "last_update": status["last_update"].strftime("%H:%M:%S") if status["last_update"] else "Never",
            "signals_count": status["signals_generated"],
            "regime_changes": status["regime_changes"],
            "symbols": ", ".join(status["symbols_tracked"])
        }
        
        return gui_status
    
    def force_update(self):
        """Force an immediate update"""
        if self.signal_provider:
            self.signal_provider.force_update()

# Example PyQt6 Widget Integration (only if PyQt6 is available)
if PYQT6_AVAILABLE:
    
    class HMMSignalWidget(QWidget):
        """
        Example PyQt6 widget that integrates with the HMM Signal Provider
        This shows how to create a widget for your existing dashboard
        """
        
        def __init__(self):
            super().__init__()
            self.integration = SignalProviderIntegration(self)
            self.init_ui()
            self.setup_integration()
        
        def init_ui(self):
            """Initialize the user interface"""
            layout = QVBoxLayout()
            
            # Control section
            control_group = QGroupBox("HMM Signal Provider Control")
            control_layout = QHBoxLayout()
            
            self.start_button = QPushButton("Start")
            self.stop_button = QPushButton("Stop")
            self.update_button = QPushButton("Force Update")
            
            self.start_button.clicked.connect(self.start_provider)
            self.stop_button.clicked.connect(self.stop_provider)
            self.update_button.clicked.connect(self.force_update)
            
            control_layout.addWidget(self.start_button)
            control_layout.addWidget(self.stop_button)
            control_layout.addWidget(self.update_button)
            control_group.setLayout(control_layout)
            
            # Regime display
            regime_group = QGroupBox("Current Market Regime")
            regime_layout = QVBoxLayout()
            
            self.regime_label = QLabel("Detecting...")
            self.regime_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            self.regime_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.confidence_bar = QProgressBar()
            self.confidence_bar.setRange(0, 100)
            
            regime_layout.addWidget(self.regime_label)
            regime_layout.addWidget(self.confidence_bar)
            regime_group.setLayout(regime_layout)
            
            # Signals display
            signals_group = QGroupBox("Recent Trading Signals")
            signals_layout = QVBoxLayout()
            
            self.signals_table = QTableWidget()
            self.signals_table.setColumnCount(6)
            self.signals_table.setHorizontalHeaderLabels([
                "Time", "Symbol", "Signal", "Confidence", "Regime", "Price"
            ])
            
            signals_layout.addWidget(self.signals_table)
            signals_group.setLayout(signals_layout)
            
            # Status display
            self.status_label = QLabel("Status: Not Started")
            
            # Add all to main layout
            layout.addWidget(control_group)
            layout.addWidget(regime_group)
            layout.addWidget(signals_group)
            layout.addWidget(self.status_label)
            
            self.setLayout(layout)
        
        def setup_integration(self):
            """Setup integration with signal provider"""
            # Initialize the provider
            self.integration.initialize_provider(symbols=["SPY"])
            
            # Register callbacks for GUI updates
            self.integration.register_callback("regime_changed", self.update_regime_display)
            self.integration.register_callback("signal_generated", self.update_signals_display)
            self.integration.register_callback("status_changed", self.update_status_display)
            
            # Setup timer for periodic GUI updates
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.periodic_update)
            self.update_timer.start(5000)  # Update every 5 seconds
        
        def start_provider(self):
            """Start the signal provider"""
            self.integration.start_provider()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        
        def stop_provider(self):
            """Stop the signal provider"""
            self.integration.stop_provider()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
        
        def force_update(self):
            """Force an update"""
            self.integration.force_update()
        
        def update_regime_display(self, regime_update):
            """Update regime display"""
            regime_info = self.integration.get_current_regime()
            
            self.regime_label.setText(regime_info["regime"])
            self.regime_label.setStyleSheet(f"color: {regime_info['color']};")
            
            confidence_pct = int(regime_info["confidence"] * 100)
            self.confidence_bar.setValue(confidence_pct)
        
        def update_signals_display(self, signal):
            """Update signals table"""
            signals = self.integration.get_recent_signals(10)
            
            self.signals_table.setRowCount(len(signals))
            
            for i, signal in enumerate(reversed(signals)):
                self.signals_table.setItem(i, 0, QTableWidgetItem(signal["timestamp"]))
                self.signals_table.setItem(i, 1, QTableWidgetItem(signal["symbol"]))
                
                # Color code signal type
                signal_item = QTableWidgetItem(signal["signal_type"])
                if signal["signal_type"] == "BUY":
                    signal_item.setBackground(QColor(200, 255, 200))
                elif signal["signal_type"] == "SELL":
                    signal_item.setBackground(QColor(255, 200, 200))
                self.signals_table.setItem(i, 2, signal_item)
                
                self.signals_table.setItem(i, 3, QTableWidgetItem(signal["confidence"]))
                self.signals_table.setItem(i, 4, QTableWidgetItem(signal["regime"]))
                self.signals_table.setItem(i, 5, QTableWidgetItem(signal["price"]))
        
        def update_status_display(self, status_data):
            """Update status display"""
            status = self.integration.get_system_status()
            self.status_label.setText(f"Status: {status['status_text']} | "
                                    f"Signals: {status['signals_count']} | "
                                    f"Last Update: {status['last_update']}")
            self.status_label.setStyleSheet(f"color: {status['color']};")
        
        def periodic_update(self):
            """Periodic GUI update"""
            self.update_status_display(None)
    
    class ExampleMainWindow(QMainWindow):
        """Example main window showing integration"""
        
        def __init__(self):
            super().__init__()
            self.setWindowTitle("HMM Signal Provider Integration Example")
            self.setGeometry(100, 100, 800, 600)
            
            # Create and set the HMM signal widget
            self.hmm_widget = HMMSignalWidget()
            self.setCentralWidget(self.hmm_widget)

# Simple integration example without PyQt6
class SimpleIntegrationExample:
    """
    Simple example showing how to integrate without PyQt6
    This can be adapted for any GUI framework or console application
    """
    
    def __init__(self):
        self.integration = SignalProviderIntegration()
        self.setup_callbacks()
    
    def setup_callbacks(self):
        """Setup callbacks for handling events"""
        self.integration.register_callback("regime_changed", self.on_regime_changed)
        self.integration.register_callback("signal_generated", self.on_signal_generated)
        self.integration.register_callback("data_updated", self.on_data_updated)
    
    def on_regime_changed(self, regime_update):
        """Handle regime changes"""
        regime_info = self.integration.get_current_regime()
        print(f"Regime Changed: {regime_info['regime']} "
              f"(Confidence: {regime_info['confidence']:.1%})")
    
    def on_signal_generated(self, signal):
        """Handle new signals"""
        print(f"New Signal: {signal.signal_type} {signal.symbol} "
              f"@ ${signal.entry_price:.2f} "
              f"(Confidence: {signal.confidence:.1%})")
    
    def on_data_updated(self, market_data):
        """Handle data updates"""
        print(f"Data updated for {market_data.symbol}: "
              f"{len(market_data.data)} records")
    
    def run_example(self):
        """Run the integration example"""
        print("Starting HMM Signal Provider Integration Example...")
        
        # Initialize and start provider
        self.integration.initialize_provider(symbols=["SPY"])
        self.integration.start_provider()
        
        try:
            import time
            print("Running... Press Ctrl+C to stop")
            while True:
                time.sleep(10)
                
                # Print status
                status = self.integration.get_system_status()
                print(f"Status: {status['status_text']} | "
                      f"Signals: {status['signals_count']} | "
                      f"Last Update: {status['last_update']}")
                
        except KeyboardInterrupt:
            print("\nStopping...")
            self.integration.stop_provider()
            print("Stopped.")

def main():
    """Main function demonstrating different integration approaches"""
    if len(sys.argv) > 1 and sys.argv[1] == "--gui" and PYQT6_AVAILABLE:
        # Run PyQt6 GUI example
        app = QApplication(sys.argv)
        window = ExampleMainWindow()
        window.show()
        sys.exit(app.exec())
    else:
        # Run simple console example
        example = SimpleIntegrationExample()
        example.run_example()

if __name__ == "__main__":
    main()

