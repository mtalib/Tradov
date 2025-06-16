#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Automated SPY Options Trading System

Module: SpyderG04_OptionChainWidget.py
Group: G (User Interface)
Purpose: Option chain display widget

Description:
    This module provides a comprehensive option chain display widget showing
    real-time option prices, Greeks, and volume data in an intuitive format.

Author: Mohamed Talib
Date: 2025-06-05
Version: 1.4
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import math

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QComboBox,
    QPushButton,
    QSpinBox,
    QGroupBox,
    QTabWidget,
    QSplitter,
    QSlider,
    QCheckBox,
    QLineEdit,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QColor, QBrush, QFont

import pandas as pd
import numpy as np

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
from SpyderA_Core.SpyderA05_EventManager import EventManager, Event, EventType

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update intervals
UPDATE_INTERVAL = 2000  # 2 seconds

# Display settings
STRIKE_RANGE = 20  # Number of strikes to show above/below ATM
GREEK_DECIMALS = 4
PRICE_DECIMALS = 2

# Color scheme
COLOR_ITM = QColor(220, 255, 220)  # Light green
COLOR_OTM = QColor(255, 255, 255)  # White
COLOR_ATM = QColor(255, 255, 200)  # Light yellow
COLOR_POSITIVE = QColor(0, 150, 0)  # Green
COLOR_NEGATIVE = QColor(200, 0, 0)  # Red


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================
@dataclass
class OptionData:
    """Single option contract data"""

    strike: float
    expiration: date
    option_type: str  # 'C' or 'P'
    bid: float = 0.0
    ask: float = 0.0
    last: float = 0.0
    volume: int = 0
    open_interest: int = 0
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    implied_volatility: float = 0.0

    @property
    def mid_price(self) -> float:
        """Calculate mid price"""
        return (self.bid + self.ask) / 2 if self.bid > 0 and self.ask > 0 else 0.0

    @property
    def spread(self) -> float:
        """Calculate bid-ask spread"""
        return self.ask - self.bid if self.ask > 0 and self.bid > 0 else 0.0


# ==============================================================================
# OPTION CHAIN WIDGET
# ==============================================================================
class OptionChainWidget(QWidget):
    """
    Advanced option chain display widget.

    Features:
    - Real-time option prices and Greeks
    - Strike selection tools
    - Volatility smile visualization
    - Volume and open interest heatmaps
    - Quick trade entry buttons
    """

    # Signals
    strike_selected = pyqtSignal(float, str, date)  # strike, type, expiration
    trade_requested = pyqtSignal(dict)  # trade parameters

    def __init__(self, event_manager: EventManager, parent=None):
        super().__init__(parent)
        self.event_manager = event_manager
        self.logger = SpyderLogger.get_logger(__name__)

        # Data storage
        self.option_chains: Dict[date, Dict[float, Dict[str, OptionData]]] = {}
        self.current_expiration: Optional[date] = None
        self.underlying_price = 0.0
        self.selected_strikes: List[Tuple[float, str]] = []

        # UI components
        self.expiration_combo: Optional[QComboBox] = None
        self.chain_table: Optional[QTableWidget] = None
        self.strike_filter: Optional[QSpinBox] = None
        self.update_timer: Optional[QTimer] = None

        # Setup UI
        self.setup_ui()

        # Register event handlers
        self._register_event_handlers()

        # Start update timer
        self.start_updates()

    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        layout.setSpacing(5)

        # Control panel
        control_panel = self._create_control_panel()
        layout.addWidget(control_panel)

        # Option chain display
        self.chain_table = self._create_chain_table()
        layout.addWidget(self.chain_table)

        # Summary panel
        summary_panel = self._create_summary_panel()
        layout.addWidget(summary_panel)

        self.setLayout(layout)

    def _create_control_panel(self) -> QWidget:
        """Create control panel for option chain"""
        panel = QGroupBox("Option Chain Controls")
        layout = QHBoxLayout()

        # Expiration selector
        layout.addWidget(QLabel("Expiration:"))
        self.expiration_combo = QComboBox()
        self.expiration_combo.currentTextChanged.connect(self._on_expiration_changed)
        layout.addWidget(self.expiration_combo)

        # Strike filter
        layout.addWidget(QLabel("Strikes ±"))
        self.strike_filter = QSpinBox()
        self.strike_filter.setRange(5, 50)
        self.strike_filter.setValue(STRIKE_RANGE)
        self.strike_filter.setSuffix(" strikes")
        self.strike_filter.valueChanged.connect(self._update_display)
        layout.addWidget(self.strike_filter)

        # Greeks display toggle
        self.show_greeks_cb = QCheckBox("Show Greeks")
        self.show_greeks_cb.setChecked(True)
        self.show_greeks_cb.stateChanged.connect(self._update_display)
        layout.addWidget(self.show_greeks_cb)

        # IV display toggle
        self.show_iv_cb = QCheckBox("Show IV")
        self.show_iv_cb.setChecked(True)
        self.show_iv_cb.stateChanged.connect(self._update_display)
        layout.addWidget(self.show_iv_cb)

        layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_data)
        layout.addWidget(refresh_btn)

        panel.setLayout(layout)
        return panel

    def _create_chain_table(self) -> QTableWidget:
        """Create the option chain table"""
        table = QTableWidget()

        # Define columns
        columns = [
            "Strike",
            # Calls
            "C Vol",
            "C OI",
            "C Bid",
            "C Ask",
            "C Last",
            "C Delta",
            "C IV",
            # Puts
            "P IV",
            "P Delta",
            "P Last",
            "P Ask",
            "P Bid",
            "P OI",
            "P Vol",
        ]

        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)

        # Configure table
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setVisible(False)

        # Set column widths
        for i in range(len(columns)):
            if "Strike" in columns[i]:
                table.setColumnWidth(i, 80)
            elif "Vol" in columns[i] or "OI" in columns[i]:
                table.setColumnWidth(i, 60)
            else:
                table.setColumnWidth(i, 70)

        # Connect selection signal
        table.itemSelectionChanged.connect(self._on_selection_changed)

        return table

    def _create_summary_panel(self) -> QWidget:
        """Create summary information panel"""
        panel = QGroupBox("Summary")
        layout = QHBoxLayout()

        # Underlying price
        self.underlying_label = QLabel("SPY: $0.00")
        self.underlying_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.underlying_label)

        # Put/Call ratio
        self.pc_ratio_label = QLabel("P/C Ratio: 0.00")
        layout.addWidget(self.pc_ratio_label)

        # Total volume
        self.total_volume_label = QLabel("Volume: 0")
        layout.addWidget(self.total_volume_label)

        # Total OI
        self.total_oi_label = QLabel("OI: 0")
        layout.addWidget(self.total_oi_label)

        layout.addStretch()

        # Quick trade buttons
        self.buy_call_btn = QPushButton("Buy Call")
        self.buy_call_btn.clicked.connect(lambda: self._quick_trade("BUY", "C"))
        self.buy_call_btn.setEnabled(False)
        layout.addWidget(self.buy_call_btn)

        self.buy_put_btn = QPushButton("Buy Put")
        self.buy_put_btn.clicked.connect(lambda: self._quick_trade("BUY", "P"))
        self.buy_put_btn.setEnabled(False)
        layout.addWidget(self.buy_put_btn)

        panel.setLayout(layout)
        return panel

    def _register_event_handlers(self):
        """Register event handlers"""
        # Option chain updates
        self.event_manager.subscribe(
            self._handle_option_chain_update,
            event_type=EventType.MARKET_DATA,
            subscriber_id="option_chain_widget",
        )

        # Underlying price updates
        self.event_manager.subscribe(
            self._handle_underlying_update,
            event_type=EventType.MARKET_DATA,
            subscriber_id="option_chain_underlying",
        )

        # Add these methods if they're missing:
        self._setup_event_subscriptions()

    def start_updates(self):
        """Start periodic updates"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(UPDATE_INTERVAL)

    def _update_display(self):
        """Update the option chain display"""
        if (
            not self.current_expiration
            or self.current_expiration not in self.option_chains
        ):
            return

        chain_data = self.option_chains[self.current_expiration]
        strikes = sorted(chain_data.keys())

        # Filter strikes based on range
        if self.underlying_price > 0:
            atm_strike = min(strikes, key=lambda x: abs(x - self.underlying_price))
            atm_index = strikes.index(atm_strike)

            # Get strikes within range
            strike_range = self.strike_filter.value()
            start_idx = max(0, atm_index - strike_range)
            end_idx = min(len(strikes), atm_index + strike_range + 1)
            display_strikes = strikes[start_idx:end_idx]
        else:
            display_strikes = strikes

        # Update table
        self.chain_table.setRowCount(len(display_strikes))

        for row, strike in enumerate(display_strikes):
            # Strike column
            strike_item = QTableWidgetItem(f"{strike:.2f}")
            strike_item.setTextAlignment(Qt.AlignCenter)

            # Color based on moneyness
            if self.underlying_price > 0:
                if abs(strike - self.underlying_price) < 1.0:
                    strike_item.setBackground(QBrush(COLOR_ATM))
                elif strike < self.underlying_price:
                    strike_item.setBackground(QBrush(COLOR_ITM))

            self.chain_table.setItem(row, 0, strike_item)

            # Call data
            if "C" in chain_data[strike]:
                call = chain_data[strike]["C"]
                self._populate_option_data(row, 1, call, "C")

            # Put data
            if "P" in chain_data[strike]:
                put = chain_data[strike]["P"]
                self._populate_option_data(row, 8, put, "P")

        # Update summary
        self._update_summary()

    def _populate_option_data(
        self, row: int, start_col: int, option: OptionData, opt_type: str
    ):
        """Populate option data in table"""
        # Volume
        vol_item = QTableWidgetItem(f"{option.volume:,}" if option.volume > 0 else "-")
        vol_item.setTextAlignment(Qt.AlignRight)
        self.chain_table.setItem(row, start_col, vol_item)

        # Open Interest
        oi_item = QTableWidgetItem(
            f"{option.open_interest:,}" if option.open_interest > 0 else "-"
        )
        oi_item.setTextAlignment(Qt.AlignRight)
        self.chain_table.setItem(row, start_col + 1, oi_item)

        # Bid
        bid_item = QTableWidgetItem(f"{option.bid:.2f}" if option.bid > 0 else "-")
        bid_item.setTextAlignment(Qt.AlignRight)
        self.chain_table.setItem(row, start_col + 2, bid_item)

        # Ask
        ask_item = QTableWidgetItem(f"{option.ask:.2f}" if option.ask > 0 else "-")
        ask_item.setTextAlignment(Qt.AlignRight)
        self.chain_table.setItem(row, start_col + 3, ask_item)

        # Last
        last_item = QTableWidgetItem(f"{option.last:.2f}" if option.last > 0 else "-")
        last_item.setTextAlignment(Qt.AlignRight)
        self.chain_table.setItem(row, start_col + 4, last_item)

        # Delta (if showing Greeks)
        if self.show_greeks_cb.isChecked():
            delta_item = QTableWidgetItem(
                f"{option.delta:.3f}" if option.delta != 0 else "-"
            )
            delta_item.setTextAlignment(Qt.AlignRight)
            # Color based on delta
            if option.delta > 0:
                delta_item.setForeground(QBrush(COLOR_POSITIVE))
            elif option.delta < 0:
                delta_item.setForeground(QBrush(COLOR_NEGATIVE))
            self.chain_table.setItem(row, start_col + 5, delta_item)

        # IV (if showing)
        if self.show_iv_cb.isChecked():
            iv_item = QTableWidgetItem(
                f"{option.implied_volatility:.1%}"
                if option.implied_volatility > 0
                else "-"
            )
            iv_item.setTextAlignment(Qt.AlignRight)
            self.chain_table.setItem(row, start_col + 6, iv_item)

    def _update_summary(self):
        """Update summary statistics"""
        if (
            not self.current_expiration
            or self.current_expiration not in self.option_chains
        ):
            return

        chain_data = self.option_chains[self.current_expiration]

        # Calculate totals
        total_call_volume = 0
        total_put_volume = 0
        total_call_oi = 0
        total_put_oi = 0

        for strike_data in chain_data.values():
            if "C" in strike_data:
                total_call_volume += strike_data["C"].volume
                total_call_oi += strike_data["C"].open_interest
            if "P" in strike_data:
                total_put_volume += strike_data["P"].volume
                total_put_oi += strike_data["P"].open_interest

        # Update labels
        if self.underlying_price > 0:
            self.underlying_label.setText(f"SPY: ${self.underlying_price:.2f}")

        pc_ratio = total_put_volume / total_call_volume if total_call_volume > 0 else 0
        self.pc_ratio_label.setText(f"P/C Ratio: {pc_ratio:.2f}")

        total_volume = total_call_volume + total_put_volume
        self.total_volume_label.setText(f"Volume: {total_volume:,}")

        total_oi = total_call_oi + total_put_oi
        self.total_oi_label.setText(f"OI: {total_oi:,}")

    def _on_expiration_changed(self, expiration_str: str):
        """Handle expiration selection change"""
        if expiration_str:
            try:
                self.current_expiration = datetime.strptime(
                    expiration_str, "%Y-%m-%d"
                ).date()
                self._update_display()
            except ValueError:
                self.logger.error(f"Invalid expiration date: {expiration_str}")

    def _on_selection_changed(self):
        """Handle strike selection"""
        selected_items = self.chain_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            strike_item = self.chain_table.item(row, 0)
            if strike_item:
                strike = float(strike_item.text())

                # Enable trade buttons
                self.buy_call_btn.setEnabled(True)
                self.buy_put_btn.setEnabled(True)

                # Store selected strike
                self.selected_strikes = [(strike, "C"), (strike, "P")]

                # Emit signal
                if self.current_expiration:
                    self.strike_selected.emit(strike, "BOTH", self.current_expiration)

    def _quick_trade(self, action: str, opt_type: str):
        """Quick trade button handler"""
        if not self.selected_strikes or not self.current_expiration:
            return

        # Find selected strike for option type
        strike = None
        for s, t in self.selected_strikes:
            if t == opt_type:
                strike = s
                break

        if strike:
            trade_params = {
                "symbol": "SPY",
                "strike": strike,
                "expiration": self.current_expiration.strftime("%Y%m%d"),
                "option_type": opt_type,
                "action": action,
                "quantity": 1,  # Default to 1 contract
            }
            self.trade_requested.emit(trade_params)

    def _refresh_data(self):
        """Refresh option chain data"""
        # Emit request for fresh data
        self.event_manager.emit(
            Event(
                EventType.MARKET_DATA,
                {
                    "request": "option_chain",
                    "symbol": "SPY",
                    "expiration": (
                        self.current_expiration.strftime("%Y%m%d")
                        if self.current_expiration
                        else None
                    ),
                },
            )
        )

    def _handle_option_chain_update(self, event: Event):
        """Handle option chain update event"""
        if event.data.get("type") != "option_chain":
            return

        chain_data = event.data.get("data", {})
        expiration_str = event.data.get("expiration")

        if expiration_str:
            try:
                expiration = datetime.strptime(expiration_str, "%Y%m%d").date()

                # Update or create chain data
                if expiration not in self.option_chains:
                    self.option_chains[expiration] = {}

                # Process chain data
                for strike_str, options in chain_data.items():
                    strike = float(strike_str)

                    if strike not in self.option_chains[expiration]:
                        self.option_chains[expiration][strike] = {}

                    # Update call data
                    if "C" in options:
                        call_data = options["C"]
                        self.option_chains[expiration][strike]["C"] = OptionData(
                            strike=strike,
                            expiration=expiration,
                            option_type="C",
                            **call_data,
                        )

                    # Update put data
                    if "P" in options:
                        put_data = options["P"]
                        self.option_chains[expiration][strike]["P"] = OptionData(
                            strike=strike,
                            expiration=expiration,
                            option_type="P",
                            **put_data,
                        )

                # Update expiration list
                self._update_expiration_list()

                # Update display if this is current expiration
                if expiration == self.current_expiration:
                    self._update_display()

            except Exception as e:
                self.logger.error(f"Error processing option chain update: {e}")

    def _handle_underlying_update(self, event: Event):
        """Handle underlying price update"""
        if event.data.get("symbol") == "SPY":
            self.underlying_price = event.data.get("last", 0.0)
            self.underlying_label.setText(f"SPY: ${self.underlying_price:.2f}")

    def _setup_event_subscriptions(self):
        """Subscribe to relevant events."""
        try:
            if self.event_manager:
                # Only subscribe if handler methods exist
                if hasattr(self, "_handle_option_data"):
                    self.event_manager.subscribe(
                        "OPTION_DATA", self._handle_option_data
                    )
                if hasattr(self, "_handle_market_data"):
                    self.event_manager.subscribe(
                        "MARKET_DATA", self._handle_market_data
                    )

        except Exception as e:
            self.logger.error(f"Failed to set up event subscriptions: {e}")

    def _handle_option_data(self, event):
        """Handle option chain data updates."""
        try:
            option_data = event.get("data", {})
            self.logger.debug(f"Option data received: {option_data}")
            # Update option chain display
        except Exception as e:
            self.logger.error(f"Error handling option data: {e}")

    def _handle_market_data(self, event):
        """Handle market data updates."""
        try:
            market_data = event.get("data", {})
            # Update underlying price if it's SPY
            if market_data.get("symbol") == "SPY":
                self.update_underlying_price(market_data.get("last", 0))
        except Exception as e:
            self.logger.error(f"Error handling market data: {e}")

    def _update_expiration_list(self):
        """Update expiration dropdown"""
        current_text = self.expiration_combo.currentText()

        self.expiration_combo.blockSignals(True)
        self.expiration_combo.clear()

        expirations = sorted(self.option_chains.keys())
        for exp in expirations:
            self.expiration_combo.addItem(exp.strftime("%Y-%m-%d"))

        # Restore selection
        if current_text:
            index = self.expiration_combo.findText(current_text)
            if index >= 0:
                self.expiration_combo.setCurrentIndex(index)
        elif self.expiration_combo.count() > 0:
            self.expiration_combo.setCurrentIndex(0)

        self.expiration_combo.blockSignals(False)

    def closeEvent(self, event):
        """Handle widget close"""
        if self.update_timer:
            self.update_timer.stop()
        event.accept()


# ==============================================================================
# MODULE INITIALIZATION
# ==============================================================================
if __name__ == "__main__":
    # Test the widget
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create test event manager
    event_manager = EventManager()

    # Create and show widget
    widget = OptionChainWidget(event_manager)
    widget.resize(1200, 600)
    widget.show()

    # Add some test data
    test_event = Event(
        EventType.MARKET_DATA,
        {
            "type": "option_chain",
            "expiration": "20250620",
            "data": {
                "445": {
                    "C": {
                        "bid": 5.20,
                        "ask": 5.30,
                        "last": 5.25,
                        "volume": 1234,
                        "open_interest": 5678,
                        "delta": 0.65,
                        "implied_volatility": 0.18,
                    },
                    "P": {
                        "bid": 2.10,
                        "ask": 2.20,
                        "last": 2.15,
                        "volume": 987,
                        "open_interest": 4321,
                        "delta": -0.35,
                        "implied_volatility": 0.19,
                    },
                },
                "450": {
                    "C": {
                        "bid": 3.10,
                        "ask": 3.20,
                        "last": 3.15,
                        "volume": 2345,
                        "open_interest": 8765,
                        "delta": 0.50,
                        "implied_volatility": 0.17,
                    },
                    "P": {
                        "bid": 3.00,
                        "ask": 3.10,
                        "last": 3.05,
                        "volume": 2100,
                        "open_interest": 7654,
                        "delta": -0.50,
                        "implied_volatility": 0.17,
                    },
                },
                "455": {
                    "C": {
                        "bid": 1.50,
                        "ask": 1.60,
                        "last": 1.55,
                        "volume": 789,
                        "open_interest": 3456,
                        "delta": 0.30,
                        "implied_volatility": 0.16,
                    },
                    "P": {
                        "bid": 4.80,
                        "ask": 4.90,
                        "last": 4.85,
                        "volume": 654,
                        "open_interest": 2345,
                        "delta": -0.70,
                        "implied_volatility": 0.18,
                    },
                },
            },
        },
    )

    # Send test data
    widget._handle_option_chain_update(test_event)

    # Set underlying price
    widget.underlying_price = 450.25
    widget._update_display()

    sys.exit(app.exec_())
