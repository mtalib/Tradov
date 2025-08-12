#!/usr/bin/env python3
"""
PyQt6 GUI for SPY HMM AI Trading System
A comprehensive desktop interface for monitoring and controlling the HMM trading system.

Author: Manus AI
Date: August 8, 2025
Version: 1.0
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Optional
import threading
import time
import json

# PyQt6 imports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QLabel, QPushButton, QTextEdit, QTableWidget, 
    QTableWidgetItem, QTabWidget, QGroupBox, QProgressBar,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox, QSplitter,
    QFrame, QScrollArea, QStatusBar, QMenuBar, QMenu, QMessageBox
)
from PyQt6.QtCore import (
    QTimer, QThread, pyqtSignal, QObject, Qt, QSize
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPixmap, QIcon, QAction
)

# PyQtGraph for real-time plotting
import pyqtgraph as pg
from pyqtgraph import PlotWidget, plot

# Import our trading system components
from complete_hmm_trading_system import TradingSystemManager
from spy_hmm_ai_agent import MarketRegime, TradingSignal, MessageType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemWorker(QObject):
    """Worker thread for running the trading system"""
    
    # Signals for communicating with GUI
    regime_updated = pyqtSignal(str, float)  # regime_name, confidence
    signal_generated = pyqtSignal(object)  # TradingSignal object
    data_updated = pyqtSignal(object)  # market data
    system_status_changed = pyqtSignal(str)  # status message
    performance_updated = pyqtSignal(object)  # performance data
    
    def __init__(self):
        super().__init__()
        self.trading_system = None
        self.running = False
        
    def start_system(self, symbols: List[str], initial_capital: float):
        """Start the trading system"""
        try:
            self.trading_system = TradingSystemManager(symbols, initial_capital)
            self.trading_system.start_system()
            self.running = True
            self.system_status_changed.emit("System Started")
            
            # Start monitoring loop
            self.monitor_system()
            
        except Exception as e:
            logger.error(f"Error starting system: {e}")
            self.system_status_changed.emit(f"Error: {e}")
    
    def stop_system(self):
        """Stop the trading system"""
        try:
            if self.trading_system:
                self.trading_system.stop_system()
                self.running = False
                self.system_status_changed.emit("System Stopped")
        except Exception as e:
            logger.error(f"Error stopping system: {e}")
    
    def monitor_system(self):
        """Monitor system and emit signals for GUI updates"""
        while self.running and self.trading_system:
            try:
                # Check for regime updates
                current_regime = self.trading_system.hmm_agent.current_regime
                regime_confidence = self.trading_system.hmm_agent.regime_confidence
                
                if current_regime:
                    self.regime_updated.emit(current_regime.name, regime_confidence)
                
                # Check for new signals
                recent_trades = self.trading_system.execution_agent.trade_history[-5:]
                for trade in recent_trades:
                    # Convert trade dict to TradingSignal-like object for display
                    signal = type('Signal', (), trade)()
                    self.signal_generated.emit(signal)
                
                # Update performance data
                performance = self.trading_system.execution_agent.get_performance_summary()
                self.performance_updated.emit(performance)
                
                time.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in system monitoring: {e}")
                time.sleep(5)

class RegimeIndicatorWidget(QWidget):
    """Widget for displaying current market regime"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Market Regime Detection")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Regime display
        self.regime_label = QLabel("Detecting...")
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
        layout.addWidget(self.regime_label)
        
        # Confidence bar
        confidence_layout = QHBoxLayout()
        confidence_layout.addWidget(QLabel("Confidence:"))
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        confidence_layout.addWidget(self.confidence_bar)
        self.confidence_value = QLabel("0%")
        confidence_layout.addWidget(self.confidence_value)
        layout.addLayout(confidence_layout)
        
        # Regime description
        self.description_label = QLabel("Waiting for regime detection...")
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("QLabel { padding: 10px; }")
        layout.addWidget(self.description_label)
        
        self.setLayout(layout)
    
    def update_regime(self, regime_name: str, confidence: float):
        """Update the regime display"""
        self.regime_label.setText(regime_name.replace("_", " ").title())
        
        # Set color based on regime
        color_map = {
            "LOW_VOLATILITY_TRENDING": "#4CAF50",  # Green
            "HIGH_VOLATILITY_MEAN_REVERTING": "#F44336",  # Red
            "TRANSITIONAL_NEUTRAL": "#FF9800"  # Orange
        }
        
        color = color_map.get(regime_name, "#9E9E9E")
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
        confidence_pct = int(confidence * 100)
        self.confidence_bar.setValue(confidence_pct)
        self.confidence_value.setText(f"{confidence_pct}%")
        
        # Update description
        descriptions = {
            "LOW_VOLATILITY_TRENDING": "Market is in a low volatility trending state. "
                                     "Momentum strategies are favored.",
            "HIGH_VOLATILITY_MEAN_REVERTING": "Market is in a high volatility mean-reverting state. "
                                             "Contrarian strategies are favored.",
            "TRANSITIONAL_NEUTRAL": "Market is in a transitional state. "
                                  "Conservative strategies are recommended."
        }
        
        self.description_label.setText(descriptions.get(regime_name, "Unknown regime state."))

class TradingSignalsWidget(QWidget):
    """Widget for displaying trading signals"""
    
    def __init__(self):
        super().__init__()
        self.signals_history = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Trading Signals")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Signals table
        self.signals_table = QTableWidget()
        self.signals_table.setColumnCount(7)
        self.signals_table.setHorizontalHeaderLabels([
            "Time", "Symbol", "Signal", "Confidence", "Regime", "Strategy", "Price"
        ])
        
        # Set column widths
        header = self.signals_table.horizontalHeader()
        header.setStretchLastSection(True)
        
        layout.addWidget(self.signals_table)
        
        # Summary stats
        stats_layout = QHBoxLayout()
        
        self.total_signals_label = QLabel("Total Signals: 0")
        self.buy_signals_label = QLabel("Buy: 0")
        self.sell_signals_label = QLabel("Sell: 0")
        self.avg_confidence_label = QLabel("Avg Confidence: 0%")
        
        stats_layout.addWidget(self.total_signals_label)
        stats_layout.addWidget(self.buy_signals_label)
        stats_layout.addWidget(self.sell_signals_label)
        stats_layout.addWidget(self.avg_confidence_label)
        
        layout.addLayout(stats_layout)
        
        self.setLayout(layout)
    
    def add_signal(self, signal):
        """Add a new trading signal to the display"""
        self.signals_history.append(signal)
        
        # Keep only last 50 signals
        if len(self.signals_history) > 50:
            self.signals_history = self.signals_history[-50:]
        
        self.update_table()
        self.update_stats()
    
    def update_table(self):
        """Update the signals table"""
        self.signals_table.setRowCount(len(self.signals_history))
        
        for i, signal in enumerate(reversed(self.signals_history)):
            # Time
            timestamp = getattr(signal, 'timestamp', datetime.now())
            if isinstance(timestamp, str):
                time_str = timestamp
            else:
                time_str = timestamp.strftime("%H:%M:%S")
            self.signals_table.setItem(i, 0, QTableWidgetItem(time_str))
            
            # Symbol
            symbol = getattr(signal, 'symbol', 'SPY')
            self.signals_table.setItem(i, 1, QTableWidgetItem(symbol))
            
            # Signal type
            signal_type = getattr(signal, 'signal_type', 'UNKNOWN')
            item = QTableWidgetItem(signal_type)
            if signal_type == "BUY":
                item.setBackground(QColor(200, 255, 200))
            elif signal_type == "SELL":
                item.setBackground(QColor(255, 200, 200))
            self.signals_table.setItem(i, 2, item)
            
            # Confidence
            confidence = getattr(signal, 'confidence', 0.0)
            confidence_str = f"{confidence:.1%}" if isinstance(confidence, float) else str(confidence)
            self.signals_table.setItem(i, 3, QTableWidgetItem(confidence_str))
            
            # Regime
            regime = getattr(signal, 'regime', 'Unknown')
            if hasattr(regime, 'name'):
                regime = regime.name
            self.signals_table.setItem(i, 4, QTableWidgetItem(regime))
            
            # Strategy
            strategy = getattr(signal, 'strategy', 'Unknown')
            self.signals_table.setItem(i, 5, QTableWidgetItem(strategy))
            
            # Price
            price = getattr(signal, 'entry_price', 0.0)
            price_str = f"${price:.2f}" if isinstance(price, (int, float)) else str(price)
            self.signals_table.setItem(i, 6, QTableWidgetItem(price_str))
    
    def update_stats(self):
        """Update signal statistics"""
        if not self.signals_history:
            return
        
        total = len(self.signals_history)
        buy_count = sum(1 for s in self.signals_history 
                       if getattr(s, 'signal_type', '') == 'BUY')
        sell_count = sum(1 for s in self.signals_history 
                        if getattr(s, 'signal_type', '') == 'SELL')
        
        # Calculate average confidence
        confidences = [getattr(s, 'confidence', 0.0) for s in self.signals_history]
        avg_confidence = np.mean(confidences) if confidences else 0.0
        
        self.total_signals_label.setText(f"Total Signals: {total}")
        self.buy_signals_label.setText(f"Buy: {buy_count}")
        self.sell_signals_label.setText(f"Sell: {sell_count}")
        self.avg_confidence_label.setText(f"Avg Confidence: {avg_confidence:.1%}")

class PerformanceWidget(QWidget):
    """Widget for displaying system performance metrics"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("System Performance")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Performance metrics grid
        metrics_layout = QGridLayout()
        
        # Create metric labels
        self.metrics = {
            "total_trades": QLabel("0"),
            "current_positions": QLabel("0"),
            "capital_utilization": QLabel("0%"),
            "avg_confidence": QLabel("0%"),
            "system_uptime": QLabel("00:00:00")
        }
        
        # Add metrics to grid
        row = 0
        for key, label in self.metrics.items():
            name_label = QLabel(key.replace("_", " ").title() + ":")
            name_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            
            value_label = label
            value_label.setFont(QFont("Arial", 12))
            value_label.setStyleSheet("QLabel { color: #2196F3; }")
            
            metrics_layout.addWidget(name_label, row, 0)
            metrics_layout.addWidget(value_label, row, 1)
            row += 1
        
        layout.addLayout(metrics_layout)
        
        # Performance chart placeholder
        self.chart_widget = PlotWidget()
        self.chart_widget.setLabel('left', 'Value')
        self.chart_widget.setLabel('bottom', 'Time')
        self.chart_widget.setTitle('System Performance Over Time')
        layout.addWidget(self.chart_widget)
        
        self.setLayout(layout)
        
        # Initialize chart data
        self.performance_data = []
        self.start_time = datetime.now()
    
    def update_performance(self, performance_data: Dict[str, Any]):
        """Update performance metrics"""
        # Update metric labels
        self.metrics["total_trades"].setText(str(performance_data.get("total_trades", 0)))
        self.metrics["current_positions"].setText(str(performance_data.get("current_positions", 0)))
        
        capital_util = performance_data.get("capital_utilization", 0.0)
        self.metrics["capital_utilization"].setText(f"{capital_util:.1%}")
        
        avg_conf = performance_data.get("average_confidence", 0.0)
        self.metrics["avg_confidence"].setText(f"{avg_conf:.1%}")
        
        # Update uptime
        uptime = datetime.now() - self.start_time
        uptime_str = str(uptime).split('.')[0]  # Remove microseconds
        self.metrics["system_uptime"].setText(uptime_str)
        
        # Update chart
        self.performance_data.append({
            "timestamp": datetime.now(),
            "total_trades": performance_data.get("total_trades", 0),
            "positions": performance_data.get("current_positions", 0)
        })
        
        # Keep only last 100 data points
        if len(self.performance_data) > 100:
            self.performance_data = self.performance_data[-100:]
        
        self.update_chart()
    
    def update_chart(self):
        """Update the performance chart"""
        if not self.performance_data:
            return
        
        # Clear previous plots
        self.chart_widget.clear()
        
        # Extract data for plotting
        timestamps = [d["timestamp"] for d in self.performance_data]
        trades = [d["total_trades"] for d in self.performance_data]
        positions = [d["positions"] for d in self.performance_data]
        
        # Convert timestamps to seconds since start
        start_time = timestamps[0] if timestamps else datetime.now()
        x_data = [(t - start_time).total_seconds() for t in timestamps]
        
        # Plot trades
        self.chart_widget.plot(x_data, trades, pen='b', name='Total Trades')
        
        # Plot positions on secondary axis (scaled)
        if max(positions) > 0:
            positions_scaled = [p * max(trades) / max(positions) for p in positions]
            self.chart_widget.plot(x_data, positions_scaled, pen='r', name='Positions (scaled)')

class SystemControlWidget(QWidget):
    """Widget for system control and configuration"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("System Control")
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("Start System")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.stop_button = QPushButton("Stop System")
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        self.stop_button.setEnabled(False)
        
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)
        
        # Configuration section
        config_group = QGroupBox("Configuration")
        config_layout = QGridLayout()
        
        # Symbol selection
        config_layout.addWidget(QLabel("Symbol:"), 0, 0)
        self.symbol_combo = QComboBox()
        self.symbol_combo.addItems(["SPY", "QQQ", "IWM"])
        config_layout.addWidget(self.symbol_combo, 0, 1)
        
        # Initial capital
        config_layout.addWidget(QLabel("Initial Capital:"), 1, 0)
        self.capital_spinbox = QDoubleSpinBox()
        self.capital_spinbox.setRange(1000, 10000000)
        self.capital_spinbox.setValue(100000)
        self.capital_spinbox.setPrefix("$")
        config_layout.addWidget(self.capital_spinbox, 1, 1)
        
        # Auto-trading checkbox
        self.auto_trading_checkbox = QCheckBox("Enable Auto-Trading")
        config_layout.addWidget(self.auto_trading_checkbox, 2, 0, 1, 2)
        
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)
        
        # Status display
        self.status_label = QLabel("System Status: Stopped")
        self.status_label.setStyleSheet("""
            QLabel {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                padding: 10px;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Log display
        log_group = QGroupBox("System Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        self.setLayout(layout)
    
    def update_status(self, status: str):
        """Update system status"""
        self.status_label.setText(f"System Status: {status}")
        
        # Update button states
        if "Started" in status or "Running" in status:
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #e8f5e8;
                    border: 1px solid #4CAF50;
                    color: #2e7d32;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
        else:
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.status_label.setStyleSheet("""
                QLabel {
                    background-color: #f0f0f0;
                    border: 1px solid #ccc;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
    
    def add_log_message(self, message: str):
        """Add a message to the log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class HMMTradingMainWindow(QMainWindow):
    """Main window for the HMM Trading System GUI"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.worker_thread = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("SPY HMM AI Trading System")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout()
        
        # Left panel - Controls and regime
        left_panel = QVBoxLayout()
        
        # System control widget
        self.control_widget = SystemControlWidget()
        left_panel.addWidget(self.control_widget)
        
        # Regime indicator widget
        self.regime_widget = RegimeIndicatorWidget()
        left_panel.addWidget(self.regime_widget)
        
        left_widget = QWidget()
        left_widget.setLayout(left_panel)
        left_widget.setMaximumWidth(400)
        
        # Right panel - Signals and performance
        right_panel = QVBoxLayout()
        
        # Create tab widget for signals and performance
        tab_widget = QTabWidget()
        
        # Trading signals tab
        self.signals_widget = TradingSignalsWidget()
        tab_widget.addTab(self.signals_widget, "Trading Signals")
        
        # Performance tab
        self.performance_widget = PerformanceWidget()
        tab_widget.addTab(self.performance_widget, "Performance")
        
        right_panel.addWidget(tab_widget)
        
        right_widget = QWidget()
        right_widget.setLayout(right_panel)
        
        # Add panels to main layout
        main_layout.addWidget(left_widget)
        main_layout.addWidget(right_widget)
        
        central_widget.setLayout(main_layout)
        
        # Connect signals
        self.control_widget.start_button.clicked.connect(self.start_system)
        self.control_widget.stop_button.clicked.connect(self.stop_system)
        
        # Create status bar
        self.statusBar().showMessage("Ready")
        
        # Create menu bar
        self.create_menu_bar()
        
        # Apply dark theme
        self.apply_theme()
    
    def create_menu_bar(self):
        """Create the menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        export_action = QAction('Export Data', self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu('Help')
        
        about_action = QAction('About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def apply_theme(self):
        """Apply a modern theme to the application"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
                background-color: white;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 2px solid #2196F3;
            }
        """)
    
    def start_system(self):
        """Start the trading system"""
        try:
            # Get configuration
            symbol = self.control_widget.symbol_combo.currentText()
            capital = self.control_widget.capital_spinbox.value()
            
            # Create worker thread
            self.worker_thread = QThread()
            self.worker = SystemWorker()
            self.worker.moveToThread(self.worker_thread)
            
            # Connect signals
            self.worker.regime_updated.connect(self.regime_widget.update_regime)
            self.worker.signal_generated.connect(self.signals_widget.add_signal)
            self.worker.performance_updated.connect(self.performance_widget.update_performance)
            self.worker.system_status_changed.connect(self.control_widget.update_status)
            self.worker.system_status_changed.connect(self.control_widget.add_log_message)
            
            # Start worker
            self.worker_thread.started.connect(
                lambda: self.worker.start_system([symbol], capital)
            )
            
            self.worker_thread.start()
            
            self.statusBar().showMessage("System starting...")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start system: {e}")
    
    def stop_system(self):
        """Stop the trading system"""
        try:
            if self.worker:
                self.worker.stop_system()
            
            if self.worker_thread:
                self.worker_thread.quit()
                self.worker_thread.wait()
            
            self.statusBar().showMessage("System stopped")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop system: {e}")
    
    def export_data(self):
        """Export trading data"""
        QMessageBox.information(self, "Export", "Export functionality not yet implemented")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(self, "About", 
                         "SPY HMM AI Trading System\n\n"
                         "A sophisticated autonomous trading system using\n"
                         "Hidden Markov Models for regime detection.\n\n"
                         "Author: Manus AI\n"
                         "Version: 1.0")
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.worker:
            self.stop_system()
        event.accept()

def main():
    """Main function to run the GUI application"""
    app = QApplication(sys.argv)
    app.setApplicationName("SPY HMM AI Trading System")
    
    # Set application icon (if available)
    # app.setWindowIcon(QIcon("icon.png"))
    
    # Create and show main window
    window = HMMTradingMainWindow()
    window.show()
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

