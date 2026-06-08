#!/usr/bin/env python3
"""
TRADOV - Autonomous Options Trading System v1.0

Series: TradovG_GUI
Module: TradovG09_RiskParametersDialog.py
Purpose: TRADOV - Automated TRAD Options Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2026-01-16 Time: 19:25:06

Module Description:
    TRADOV - Automated TRAD Options Trading System

Change Log:
    2026-01-16:
        - Applied standard Python formatting
        - Updated module header and structure
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import json
import sys
from datetime import datetime, UTC

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog,

                            QDialogButtonBox, QDoubleSpinBox, QFileDialog,
                            QGridLayout, QGroupBox,
                            QHBoxLayout, QLabel, QMessageBox,
                            QPushButton, QRadioButton, QSpinBox, QTableWidget, QTableWidgetItem,
                             QTabWidget, QVBoxLayout, QWidget)
import logging

# ==============================================================================
# CONSTANTS AND STYLING
# ==============================================================================
COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#FF073A",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "cyan": "#00ffff",
}

# Risk profile presets
RISK_PROFILES = {
    "Conservative": {
        "risk_per_trade": 0.5,
        "max_daily_loss": 2.0,
        "max_contracts": 5,
        "max_delta": 50,
        "max_vega": -100,
        "max_theta": -200,
        "allow_0dte": False,
        "max_open_positions": 3,
        "max_buying_power": 30,
        "description": "Conservative approach with minimal risk exposure",
    },
    "Moderate": {
        "risk_per_trade": 1.0,
        "max_daily_loss": 5.0,
        "max_contracts": 10,
        "max_delta": 100,
        "max_vega": -200,
        "max_theta": -300,
        "allow_0dte": True,
        "max_open_positions": 6,
        "max_buying_power": 50,
        "description": "Balanced risk-reward with controlled exposure",
    },
    "Aggressive": {
        "risk_per_trade": 2.0,
        "max_daily_loss": 10.0,
        "max_contracts": 20,
        "max_delta": 200,
        "max_vega": -400,
        "max_theta": -600,
        "allow_0dte": True,
        "max_open_positions": 12,
        "max_buying_power": 75,
        "description": "High risk-reward for experienced traders",
    },
    "Low Volatility": {
        "risk_per_trade": 1.5,
        "max_daily_loss": 3.0,
        "max_contracts": 15,
        "max_delta": 150,
        "max_vega": -300,
        "max_theta": -500,
        "allow_0dte": True,
        "max_open_positions": 10,
        "max_buying_power": 60,
        "description": "Optimized for low volatility environments",
    },
}

# ==============================================================================
# MAIN RISK LEVELS DIALOG CLASS
# ==============================================================================


class RiskParametersDialog(QDialog):
    """Professional risk levels configuration dialog with enhanced UI"""

    # Custom signals
    parameters_updated = Signal(dict)
    profile_changed = Signal(str)

    def __init__(self, parent=None, current_params: dict | None = None):
        super().__init__(parent)

        self.current_params = current_params or {}
        self.has_unsaved_changes = False
        self.original_params = None  # Store original parameters to detect real changes
        self.is_loading = True  # Start with loading flag True to prevent early change detection

        self.setup_ui()
        self.setup_styling()
        self.setup_connections()  # Connect signals before loading parameters
        self.load_current_parameters()

        # Store original state after loading and reset flags
        self.original_params = self.get_parameters()
        self.has_unsaved_changes = False
        self.is_loading = False  # Now enable change detection
        self.update_save_status()

    def setup_ui(self):
        """Setup the main dialog UI"""
        self.setWindowTitle("TRADOV - Risk Levels Configuration")
        self.setModal(True)
        self.setMinimumSize(1000, 700)

        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header with dynamic title
        header = self.create_header()
        main_layout.addWidget(header)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_global_risk_tab(), "Global Risk")
        self.tab_widget.addTab(self.create_strategy_tab(), "Strategy Settings")
        self.tab_widget.addTab(self.create_dynamic_tab(), "Dynamic Rules")
        self.tab_widget.addTab(self.create_monitoring_tab(), "Risk Monitoring")

        # Connect tab change signal to update title
        self.tab_widget.currentChanged.connect(self.update_tab_title)

        main_layout.addWidget(self.tab_widget)

        # Buttons
        button_layout = self.create_button_layout()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # Set initial tab title
        self.update_tab_title(0)

    def create_header(self) -> QWidget:
        """Create header section with dynamic title"""
        widget = QWidget()
        widget.setFixedHeight(60)
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)

        # Dynamic title that changes based on active tab
        self.title_label = QLabel("RISK LEVELS CONFIGURATION - GLOBAL RISK")
        self.title_label.setStyleSheet(
            f"""
            font-size: 16px;
            font-weight: normal;
            color: {COLORS['text']};
            letter-spacing: 2px;
        """
        )
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Status
        self.save_status = QLabel("Ready to configure")
        self.save_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
        layout.addWidget(self.save_status)

        widget.setLayout(layout)
        return widget

    def update_tab_title(self, index: int):
        """Update the title based on the active tab"""
        tab_titles = [
            "RISK LEVELS CONFIGURATION - GLOBAL RISK",
            "RISK LEVELS CONFIGURATION - STRATEGY SETTINGS",
            "RISK LEVELS CONFIGURATION - DYNAMIC RULES",
            "RISK LEVELS CONFIGURATION - RISK MONITORING",
        ]

        if 0 <= index < len(tab_titles):
            self.title_label.setText(tab_titles[index])

    def create_global_risk_tab(self) -> QWidget:
        """Create global risk parameters tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        # Risk Profile Section
        profile_group = QGroupBox("Risk Profile Templates")
        profile_layout = QVBoxLayout()

        # Profile selection
        profile_select_layout = QHBoxLayout()
        profile_select_layout.addWidget(QLabel("Select Profile:"))

        self.risk_profile_combo = QComboBox()
        self.risk_profile_combo.addItems(list(RISK_PROFILES.keys()))
        self.risk_profile_combo.setCurrentText("Moderate")
        profile_select_layout.addWidget(self.risk_profile_combo)

        profile_select_layout.addStretch()
        profile_layout.addLayout(profile_select_layout)

        # Profile description
        self.profile_description = QLabel()
        self.profile_description.setWordWrap(True)
        self.profile_description.setStyleSheet(f"color: {COLORS['text_dim']}; padding: 10px;")
        profile_layout.addWidget(self.profile_description)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # Global Risk Limits
        limits_group = QGroupBox("Global Risk Limits")
        limits_layout = QGridLayout()

        # Risk per trade
        limits_layout.addWidget(QLabel("Risk per Trade (%):"), 0, 0)
        self.risk_per_trade_spin = QDoubleSpinBox()
        self.risk_per_trade_spin.setRange(0.1, 10.0)
        self.risk_per_trade_spin.setSingleStep(0.1)
        self.risk_per_trade_spin.setSuffix("%")
        limits_layout.addWidget(self.risk_per_trade_spin, 0, 1)

        # Max daily loss
        limits_layout.addWidget(QLabel("Max Daily Loss (%):"), 0, 2)
        self.max_daily_loss_spin = QDoubleSpinBox()
        self.max_daily_loss_spin.setRange(1.0, 20.0)
        self.max_daily_loss_spin.setSingleStep(0.5)
        self.max_daily_loss_spin.setSuffix("%")
        limits_layout.addWidget(self.max_daily_loss_spin, 0, 3)

        # Max contracts
        limits_layout.addWidget(QLabel("Max Contracts:"), 1, 0)
        self.max_contracts_spin = QSpinBox()
        self.max_contracts_spin.setRange(1, 100)
        limits_layout.addWidget(self.max_contracts_spin, 1, 1)

        # Max open positions
        limits_layout.addWidget(QLabel("Max Open Positions:"), 1, 2)
        self.max_positions_spin = QSpinBox()
        self.max_positions_spin.setRange(1, 50)
        limits_layout.addWidget(self.max_positions_spin, 1, 3)

        # Max buying power
        limits_layout.addWidget(QLabel("Max Buying Power (%):"), 2, 0)
        self.max_buying_power_spin = QSpinBox()
        self.max_buying_power_spin.setRange(10, 100)
        self.max_buying_power_spin.setSuffix("%")
        limits_layout.addWidget(self.max_buying_power_spin, 2, 1)

        # Allow 0DTE
        self.allow_0dte_check = QRadioButton("Allow 0DTE Trading")
        self.allow_0dte_check.setAutoExclusive(False)  # Allow independent toggle
        limits_layout.addWidget(self.allow_0dte_check, 2, 2, 1, 2)

        limits_group.setLayout(limits_layout)
        layout.addWidget(limits_group)

        # Greeks Limits
        greeks_group = QGroupBox("Portfolio Greeks Limits")
        greeks_layout = QGridLayout()

        # Delta
        greeks_layout.addWidget(QLabel("Max Delta:"), 0, 0)
        self.max_delta_spin = QSpinBox()
        self.max_delta_spin.setRange(-500, 500)
        greeks_layout.addWidget(self.max_delta_spin, 0, 1)

        # Gamma
        greeks_layout.addWidget(QLabel("Max Gamma:"), 0, 2)
        self.max_gamma_spin = QSpinBox()
        self.max_gamma_spin.setRange(-50, 50)
        greeks_layout.addWidget(self.max_gamma_spin, 0, 3)

        # Theta
        greeks_layout.addWidget(QLabel("Max Theta:"), 1, 0)
        self.max_theta_spin = QSpinBox()
        self.max_theta_spin.setRange(-2000, 0)
        greeks_layout.addWidget(self.max_theta_spin, 1, 1)

        # Vega
        greeks_layout.addWidget(QLabel("Max Vega:"), 1, 2)
        self.max_vega_spin = QSpinBox()
        self.max_vega_spin.setRange(-2000, 0)
        greeks_layout.addWidget(self.max_vega_spin, 1, 3)

        greeks_group.setLayout(greeks_layout)
        layout.addWidget(greeks_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_strategy_tab(self) -> QWidget:
        """Create strategy-specific settings tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        # Strategy Group Settings
        strategy_group = QGroupBox("Strategy Group Settings")
        strategy_layout = QVBoxLayout()

        # Create strategy table
        # NOTE: Naked puts are prohibited — they carry unlimited downside risk
        # and are not permitted by system policy. Only defined-risk strategies
        # are listed here.
        self.strategy_table = QTableWidget(4, 4)
        self.strategy_table.setHorizontalHeaderLabels(
            ["Strategy", "Enabled", "Max Risk (%)", "Max Contracts"]
        )

        strategies = [
            "Iron Condor",
            "Credit Spreads",
            "Straddles/Strangles",
            "Calendar Spreads",
        ]

        for i, strategy in enumerate(strategies):
            self.strategy_table.setItem(i, 0, QTableWidgetItem(strategy))

            # Enabled radio button
            radio_button = QRadioButton()
            radio_button.setAutoExclusive(False)  # Allow independent toggle
            radio_button.setChecked(i < 3)  # First 3 enabled
            self.strategy_table.setCellWidget(i, 1, radio_button)

            # Max risk
            risk_spin = QDoubleSpinBox()
            risk_spin.setRange(0.5, 5.0)
            risk_spin.setValue(1.0 + i * 0.5)
            risk_spin.setSuffix("%")
            self.strategy_table.setCellWidget(i, 2, risk_spin)

            # Max contracts
            contracts_spin = QSpinBox()
            contracts_spin.setRange(1, 50)
            contracts_spin.setValue(10 - i)
            self.strategy_table.setCellWidget(i, 3, contracts_spin)

        self.strategy_table.resizeColumnsToContents()
        strategy_layout.addWidget(self.strategy_table)

        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)

        # Risk Scaling
        scaling_group = QGroupBox("Risk Scaling")
        scaling_layout = QGridLayout()

        # IV rank scaling
        self.iv_scaling_check = QRadioButton("Enable IV Rank Scaling")
        self.iv_scaling_check.setAutoExclusive(False)  # Allow independent toggle
        self.iv_scaling_check.setChecked(True)
        scaling_layout.addWidget(self.iv_scaling_check, 0, 0, 1, 2)

        scaling_layout.addWidget(QLabel("IV Reduction Threshold:"), 1, 0)
        self.iv_threshold_spin = QSpinBox()
        self.iv_threshold_spin.setRange(10, 90)
        self.iv_threshold_spin.setValue(50)
        self.iv_threshold_spin.setSuffix("%")
        scaling_layout.addWidget(self.iv_threshold_spin, 1, 1)

        # VIX scaling
        self.vix_scaling_check = QRadioButton("Enable VIX-Based Scaling")
        self.vix_scaling_check.setAutoExclusive(False)  # Allow independent toggle
        self.vix_scaling_check.setChecked(True)
        scaling_layout.addWidget(self.vix_scaling_check, 2, 0, 1, 2)

        scaling_layout.addWidget(QLabel("VIX Threshold:"), 3, 0)
        self.vix_threshold_spin = QSpinBox()
        self.vix_threshold_spin.setRange(10, 50)
        self.vix_threshold_spin.setValue(20)
        scaling_layout.addWidget(self.vix_threshold_spin, 3, 1)

        scaling_group.setLayout(scaling_layout)
        layout.addWidget(scaling_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_dynamic_tab(self) -> QWidget:
        """Create dynamic rules tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        # Market Regime Adjustments
        regime_group = QGroupBox("Market Regime Adjustments")
        regime_layout = QGridLayout()

        # High volatility rules
        regime_layout.addWidget(QLabel("High Volatility (VIX > 25):"), 0, 0)
        self.high_vol_reduction = QDoubleSpinBox()
        self.high_vol_reduction.setRange(0.1, 0.9)
        self.high_vol_reduction.setValue(0.5)
        self.high_vol_reduction.setSingleStep(0.1)
        regime_layout.addWidget(self.high_vol_reduction, 0, 1)

        # Low volatility rules
        regime_layout.addWidget(QLabel("Low Volatility (VIX < 15):"), 1, 0)
        self.low_vol_increase = QDoubleSpinBox()
        self.low_vol_increase.setRange(1.0, 2.0)
        self.low_vol_increase.setValue(1.2)
        self.low_vol_increase.setSingleStep(0.1)
        regime_layout.addWidget(self.low_vol_increase, 1, 1)

        # Trending market
        regime_layout.addWidget(QLabel("Strong Trend (RSI > 70 or < 30):"), 2, 0)
        self.trend_reduction = QDoubleSpinBox()
        self.trend_reduction.setRange(0.1, 0.9)
        self.trend_reduction.setValue(0.7)
        self.trend_reduction.setSingleStep(0.1)
        regime_layout.addWidget(self.trend_reduction, 2, 1)

        regime_group.setLayout(regime_layout)
        layout.addWidget(regime_group)

        # Time-Based Rules
        time_group = QGroupBox("Time-Based Rules")
        time_layout = QGridLayout()

        # 0DTE rules
        self.zero_dte_enabled = QRadioButton("Allow 0DTE Trading")
        self.zero_dte_enabled.setAutoExclusive(False)  # Allow independent toggle
        self.zero_dte_enabled.setChecked(True)
        time_layout.addWidget(self.zero_dte_enabled, 0, 0)

        time_layout.addWidget(QLabel("0DTE Risk Reduction:"), 0, 1)
        self.zero_dte_reduction = QDoubleSpinBox()
        self.zero_dte_reduction.setRange(0.1, 0.9)
        self.zero_dte_reduction.setValue(0.5)
        time_layout.addWidget(self.zero_dte_reduction, 0, 2)

        # Expiration week
        self.expiration_week_check = QRadioButton("Reduce Risk During Expiration Week")
        self.expiration_week_check.setAutoExclusive(False)  # Allow independent toggle
        self.expiration_week_check.setChecked(True)
        time_layout.addWidget(self.expiration_week_check, 1, 0)

        time_layout.addWidget(QLabel("Expiration Week Reduction:"), 1, 1)
        self.expiration_reduction = QDoubleSpinBox()
        self.expiration_reduction.setRange(0.1, 0.9)
        self.expiration_reduction.setValue(0.3)
        time_layout.addWidget(self.expiration_reduction, 1, 2)

        time_group.setLayout(time_layout)
        layout.addWidget(time_group)

        # Event Risk
        event_group = QGroupBox("Event Risk Management")
        event_layout = QGridLayout()

        # Earnings
        self.earnings_check = QRadioButton("Block Trading Around Earnings")
        self.earnings_check.setAutoExclusive(False)  # Allow independent toggle
        self.earnings_check.setChecked(True)
        event_layout.addWidget(self.earnings_check, 0, 0)

        event_layout.addWidget(QLabel("Earnings Blackout (hours):"), 0, 1)
        self.earnings_blackout = QSpinBox()
        self.earnings_blackout.setRange(6, 72)
        self.earnings_blackout.setValue(24)
        event_layout.addWidget(self.earnings_blackout, 0, 2)

        # FOMC
        self.fomc_check = QRadioButton("Reduce Risk Around FOMC")
        self.fomc_check.setAutoExclusive(False)  # Allow independent toggle
        self.fomc_check.setChecked(True)
        event_layout.addWidget(self.fomc_check, 1, 0)

        event_layout.addWidget(QLabel("FOMC Risk Reduction:"), 1, 1)
        self.fomc_reduction = QDoubleSpinBox()
        self.fomc_reduction.setRange(0.1, 0.9)
        self.fomc_reduction.setValue(0.5)
        event_layout.addWidget(self.fomc_reduction, 1, 2)

        event_group.setLayout(event_layout)
        layout.addWidget(event_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_monitoring_tab(self) -> QWidget:
        """Create risk monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(20)

        # Real-time Monitoring
        monitoring_group = QGroupBox("Real-Time Risk Monitoring")
        monitoring_layout = QVBoxLayout()

        # Enable monitoring
        self.monitoring_enabled = QRadioButton("Enable Real-Time Risk Monitoring")
        self.monitoring_enabled.setAutoExclusive(False)  # Allow independent toggle
        self.monitoring_enabled.setChecked(True)
        monitoring_layout.addWidget(self.monitoring_enabled)

        # Monitoring frequency
        freq_layout = QHBoxLayout()
        freq_layout.addWidget(QLabel("Update Frequency:"))
        self.update_frequency = QComboBox()
        self.update_frequency.addItems(["1 second", "5 seconds", "10 seconds", "30 seconds"])
        self.update_frequency.setCurrentText("5 seconds")
        freq_layout.addWidget(self.update_frequency)
        freq_layout.addStretch()
        monitoring_layout.addLayout(freq_layout)

        # Alert thresholds
        alert_layout = QGridLayout()

        alert_layout.addWidget(QLabel("Delta Alert Threshold (%):"), 0, 0)
        self.delta_alert_spin = QSpinBox()
        self.delta_alert_spin.setRange(50, 100)
        self.delta_alert_spin.setValue(80)
        self.delta_alert_spin.setSuffix("%")
        alert_layout.addWidget(self.delta_alert_spin, 0, 1)

        alert_layout.addWidget(QLabel("P&L Alert Threshold (%):"), 0, 2)
        self.pnl_alert_spin = QSpinBox()
        self.pnl_alert_spin.setRange(50, 100)
        self.pnl_alert_spin.setValue(75)
        self.pnl_alert_spin.setSuffix("%")
        alert_layout.addWidget(self.pnl_alert_spin, 0, 3)

        monitoring_layout.addLayout(alert_layout)
        monitoring_group.setLayout(monitoring_layout)
        layout.addWidget(monitoring_group)

        # Current Risk Status (Read-only)
        status_group = QGroupBox("Current Risk Status")
        status_layout = QGridLayout()

        self.current_delta_label = QLabel("Current Delta: 0")
        self.current_delta_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        status_layout.addWidget(self.current_delta_label, 0, 0)

        self.current_risk_label = QLabel("Risk Utilization: 0%")
        self.current_risk_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        status_layout.addWidget(self.current_risk_label, 0, 1)

        self.positions_count_label = QLabel("Open Positions: 0")
        self.positions_count_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        status_layout.addWidget(self.positions_count_label, 1, 0)

        self.buying_power_label = QLabel("Buying Power Used: 0%")
        self.buying_power_label.setStyleSheet(f"color: {COLORS['text_dim']};")
        status_layout.addWidget(self.buying_power_label, 1, 1)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_button_layout(self) -> QHBoxLayout:
        """Create dialog button layout"""
        layout = QHBoxLayout()

        # Import/Export buttons
        self.import_btn = QPushButton("Import Settings")
        self.import_btn.clicked.connect(self.import_settings)
        layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("Export Settings")
        self.export_btn.clicked.connect(self.export_settings)
        layout.addWidget(self.export_btn)

        layout.addStretch()

        # Reset button
        self.reset_btn = QPushButton("Reset to Defaults")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        layout.addWidget(self.reset_btn)

        # Apply button
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self.apply_parameters)
        layout.addWidget(self.apply_btn)

        # Standard buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_parameters)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        return layout

    def setup_styling(self):
        """Apply enhanced dark theme styling with smaller radio buttons that turn green when selected"""  # noqa: E501
        self.setStyleSheet(
            f"""
            QDialog {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
            }}
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                background-color: {COLORS['background']};
            }}
            QTabBar::tab {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                padding: 8px 15px;
                margin-right: 2px;
                border: 1px solid {COLORS['border']};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: #d3d3d3;
                color: #000000;
                border-bottom: 1px solid #d3d3d3;
                font-weight: normal;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS['border']};
            }}
            QGroupBox {{
                font-weight: normal;
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS['panel']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {COLORS['cyan']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QSpinBox, QDoubleSpinBox {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                color: {COLORS['text']};
                padding: 5px;
                min-width: 80px;
            }}
            QComboBox {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                color: {COLORS['text']};
                padding: 5px;
                min-width: 150px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['border']};
            }}
            QCheckBox {{
                color: {COLORS['text']};
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['positive']};
                border: 2px solid {COLORS['positive']};
            }}
            QCheckBox::indicator:unchecked {{
                background-color: #ffffff;
                border: 1px solid #666666;
            }}
            QRadioButton {{
                color: {COLORS['text']};
                spacing: 8px;
            }}
            QRadioButton::indicator {{
                width: 10px;
                height: 10px;
                border-radius: 5px;
                border: 1px solid #666666;
                background-color: #ffffff;
            }}
            QRadioButton::indicator:checked {{
                width: 10px;
                height: 10px;
                border-radius: 5px;
                border: 1px solid {COLORS['positive']};
                background-color: {COLORS['positive']};
            }}
            QRadioButton::indicator:hover:unchecked {{
                border: 1px solid #888888;
            }}
            QRadioButton::indicator:hover:checked {{
                border: 1px solid {COLORS['positive']};
                background-color: {COLORS['positive']};
            }}
            QTableWidget {{
                background-color: {COLORS['panel']};
                alternate-background-color: {COLORS['background']};
                color: {COLORS['text']};
                gridline-color: {COLORS['border']};
                border: 1px solid {COLORS['border']};
            }}
            QPushButton {{
                background-color: {COLORS['panel']};
                border: 1px solid {COLORS['border']};
                color: {COLORS['text']};
                padding: 8px 15px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['border']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['background']};
            }}
        """
        )

    def setup_connections(self):
        """Setup signal connections with proper change detection"""
        self.risk_profile_combo.currentTextChanged.connect(self.on_profile_changed)

        # Connect all input widgets to mark unsaved changes
        controls = [
            self.risk_per_trade_spin,
            self.max_daily_loss_spin,
            self.max_contracts_spin,
            self.max_positions_spin,
            self.max_buying_power_spin,
            self.allow_0dte_check,
            self.max_delta_spin,
            self.max_gamma_spin,
            self.max_theta_spin,
            self.max_vega_spin,
            self.iv_scaling_check,
            self.iv_threshold_spin,
            self.vix_scaling_check,
            self.vix_threshold_spin,
            self.high_vol_reduction,
            self.low_vol_increase,
            self.trend_reduction,
            self.zero_dte_enabled,
            self.zero_dte_reduction,
            self.expiration_week_check,
            self.expiration_reduction,
            self.earnings_check,
            self.earnings_blackout,
            self.fomc_check,
            self.fomc_reduction,
            self.monitoring_enabled,
            self.update_frequency,
            self.delta_alert_spin,
            self.pnl_alert_spin,
        ]

        for control in controls:
            if hasattr(control, "valueChanged"):
                control.valueChanged.connect(self.check_for_changes)
            elif hasattr(control, "toggled"):
                control.toggled.connect(self.check_for_changes)
            elif hasattr(control, "currentTextChanged"):
                control.currentTextChanged.connect(self.check_for_changes)

        # Connect strategy table changes
        self.strategy_table.cellChanged.connect(self.check_for_changes)

        # Connect signals from all widgets in the strategy table
        self.connect_strategy_table_widgets()

    def connect_strategy_table_widgets(self):
        """Connect all widgets in the strategy table to change detection"""
        for i in range(self.strategy_table.rowCount()):
            # Connect radio button (column 1)
            radio_button = self.strategy_table.cellWidget(i, 1)
            if radio_button and hasattr(radio_button, "toggled"):
                radio_button.toggled.connect(self.check_for_changes)

            # Connect risk spinbox (column 2)
            risk_spin = self.strategy_table.cellWidget(i, 2)
            if risk_spin and hasattr(risk_spin, "valueChanged"):
                risk_spin.valueChanged.connect(self.check_for_changes)

            # Connect contracts spinbox (column 3)
            contracts_spin = self.strategy_table.cellWidget(i, 3)
            if contracts_spin and hasattr(contracts_spin, "valueChanged"):
                contracts_spin.valueChanged.connect(self.check_for_changes)

    def check_for_changes(self):
        """Check if parameters have actually changed from original"""
        if self.is_loading or self.original_params is None:
            return

        try:
            current_params = self.get_parameters()

            # Simple comparison first - if they're exactly equal, no changes
            if current_params == self.original_params:
                changes_detected = False
            else:
                # More detailed comparison using JSON for edge cases
                import json

                current_json = json.dumps(current_params, sort_keys=True, default=str)
                original_json = json.dumps(self.original_params, sort_keys=True, default=str)
                changes_detected = current_json != original_json

            if changes_detected != self.has_unsaved_changes:
                self.has_unsaved_changes = changes_detected
                self.update_save_status()

        except Exception as e:
            # If comparison fails, don't change the current state
            logging.info("Change detection error: %s", e)  # Debug info

    def update_save_status(self):
        """Update the save status display"""
        if self.has_unsaved_changes:
            self.save_status.setText("Unsaved changes")
            self.save_status.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
        else:
            self.save_status.setText("All changes saved")
            self.save_status.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")

    def load_current_parameters(self):
        """Load current parameters into UI"""
        self.is_loading = True  # Prevent change detection during loading

        if self.current_params and "global" in self.current_params:
            params = self.current_params["global"]

            # Load profile if specified
            profile = params.get("active_profile", "Moderate")
            if profile in RISK_PROFILES:
                self.risk_profile_combo.setCurrentText(profile)
                self.on_profile_changed(profile)
            else:
                # Load individual parameters
                self.risk_per_trade_spin.setValue(params.get("risk_per_trade", 1.0))
                self.max_daily_loss_spin.setValue(params.get("max_daily_loss", 5.0))
                self.max_contracts_spin.setValue(params.get("max_contracts", 10))
                self.max_positions_spin.setValue(params.get("max_open_positions", 6))
                self.max_buying_power_spin.setValue(params.get("max_buying_power", 50))
                self.allow_0dte_check.setChecked(params.get("allow_0dte", True))
                self.max_delta_spin.setValue(params.get("max_delta", 100))
                self.max_gamma_spin.setValue(params.get("max_gamma", 10))
                self.max_theta_spin.setValue(params.get("max_theta", -300))
                self.max_vega_spin.setValue(params.get("max_vega", -200))
        else:
            # Load defaults
            self.on_profile_changed("Moderate")

        self.is_loading = False  # Re-enable change detection

    def on_profile_changed(self, profile_name: str):
        """Handle risk profile change"""
        if profile_name in RISK_PROFILES:
            profile = RISK_PROFILES[profile_name]

            # Temporarily disable change detection
            was_loading = self.is_loading
            self.is_loading = True

            # Update description
            self.profile_description.setText(profile["description"])

            # Update controls
            self.risk_per_trade_spin.setValue(profile["risk_per_trade"])
            self.max_daily_loss_spin.setValue(profile["max_daily_loss"])
            self.max_contracts_spin.setValue(profile["max_contracts"])
            self.max_positions_spin.setValue(profile["max_open_positions"])
            self.max_buying_power_spin.setValue(profile["max_buying_power"])
            self.allow_0dte_check.setChecked(profile["allow_0dte"])
            self.max_delta_spin.setValue(profile["max_delta"])
            self.max_gamma_spin.setValue(10)  # Default value
            self.max_theta_spin.setValue(profile["max_theta"])
            self.max_vega_spin.setValue(profile["max_vega"])

            # Restore change detection state
            self.is_loading = was_loading

            if not self.is_loading:
                self.check_for_changes()

    def get_parameters(self) -> dict:
        """Get current parameter values"""
        # Get strategy settings
        strategy_settings = {}
        for i in range(self.strategy_table.rowCount()):
            strategy_name = (
                self.strategy_table.item(i, 0).text().lower().replace(" ", "_").replace("/", "_")
            )
            radio_button = self.strategy_table.cellWidget(i, 1)
            risk_spin = self.strategy_table.cellWidget(i, 2)
            contracts_spin = self.strategy_table.cellWidget(i, 3)

            strategy_settings[strategy_name] = {
                "enabled": radio_button.isChecked(),
                "max_risk": risk_spin.value(),
                "max_contracts": contracts_spin.value(),
            }

        return {
            "global": {
                "active_profile": self.risk_profile_combo.currentText(),
                "risk_per_trade": self.risk_per_trade_spin.value(),
                "max_daily_loss": self.max_daily_loss_spin.value(),
                "max_contracts": self.max_contracts_spin.value(),
                "max_open_positions": self.max_positions_spin.value(),
                "max_buying_power": self.max_buying_power_spin.value(),
                "allow_0dte": self.allow_0dte_check.isChecked(),
                "max_delta": self.max_delta_spin.value(),
                "max_gamma": self.max_gamma_spin.value(),
                "max_theta": self.max_theta_spin.value(),
                "max_vega": self.max_vega_spin.value(),
            },
            "strategy_groups": strategy_settings,
            "dynamic_rules": {
                "enable_iv_scaling": self.iv_scaling_check.isChecked(),
                "iv_threshold": self.iv_threshold_spin.value(),
                "enable_vix_scaling": self.vix_scaling_check.isChecked(),
                "vix_threshold": self.vix_threshold_spin.value(),
                "high_vol_reduction": self.high_vol_reduction.value(),
                "low_vol_increase": self.low_vol_increase.value(),
                "trend_reduction": self.trend_reduction.value(),
                "zero_dte_enabled": self.zero_dte_enabled.isChecked(),
                "zero_dte_reduction": self.zero_dte_reduction.value(),
                "expiration_week_enabled": self.expiration_week_check.isChecked(),
                "expiration_reduction": self.expiration_reduction.value(),
                "earnings_blackout": self.earnings_check.isChecked(),
                "earnings_hours": self.earnings_blackout.value(),
                "fomc_reduction_enabled": self.fomc_check.isChecked(),
                "fomc_reduction": self.fomc_reduction.value(),
            },
            "monitoring": {
                "enabled": self.monitoring_enabled.isChecked(),
                "update_frequency": self.update_frequency.currentText(),
                "delta_alert_threshold": self.delta_alert_spin.value(),
                "pnl_alert_threshold": self.pnl_alert_spin.value(),
            },
        }

    def validate_parameters(self) -> tuple[bool, list[str]]:
        """Validate parameter values"""
        warnings = []
        errors = []

        # Check risk per trade
        if self.risk_per_trade_spin.value() > 5.0:
            warnings.append("Risk per trade > 5% is very aggressive")

        # Check daily loss limit
        if self.max_daily_loss_spin.value() > 15.0:
            warnings.append("Daily loss limit > 15% is very high")

        # Check delta limits
        if abs(self.max_delta_spin.value()) > 300:
            warnings.append("Delta limit > 300 may indicate high directional risk")

        # Check buying power
        if self.max_buying_power_spin.value() > 80:
            warnings.append("Using > 80% buying power leaves little margin for error")

        return len(errors) == 0, errors + warnings

    def import_settings(self):
        """Import settings from JSON file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Import Risk Levels", "", "JSON Files (*.json);;All Files (*)"
        )

        if filename:
            try:
                with open(filename) as f:
                    params = json.load(f)

                self.current_params = params
                self.load_current_parameters()

                # Update original parameters to reflect imported state
                self.original_params = self.get_parameters()
                self.has_unsaved_changes = False
                self.update_save_status()

                QMessageBox.information(
                    self, "Import Successful", f"Risk levels imported from:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Error importing levels:\n{str(e)}")

    def export_settings(self):
        """Export settings to JSON file"""
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Risk Levels",
            f"tradov_risk_levels_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;All Files (*)",
        )

        if filename:
            try:
                params = self.get_parameters()
                with open(filename, "w") as f:
                    json.dump(params, f, indent=4)

                QMessageBox.information(
                    self, "Export Successful", f"Risk levels exported to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Error exporting levels:\n{str(e)}")

    def reset_to_defaults(self):
        """Reset all parameters to defaults"""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "This will reset all levels to default values.\nAre you sure?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.is_loading = True
            self.risk_profile_combo.setCurrentText("Moderate")
            self.on_profile_changed("Moderate")
            self.is_loading = False

            # Update original parameters and reset change status
            self.original_params = self.get_parameters()
            self.has_unsaved_changes = False
            self.update_save_status()

    def apply_parameters(self):
        """Apply parameters without closing dialog"""
        is_valid, messages = self.validate_parameters()

        if not is_valid:
            QMessageBox.critical(
                self, "Validation Error", "Cannot apply levels:\n\n" + "\n".join(messages)
            )
            return

        if messages:  # Show warnings
            reply = QMessageBox.warning(
                self,
                "Validation Warnings",
                "The following warnings were detected:\n\n"
                + "\n".join(messages)
                + "\n\nDo you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.No:
                return

        # Emit signal with parameters
        current_params = self.get_parameters()
        self.parameters_updated.emit(current_params)

        # Update original parameters and reset change status
        self.original_params = current_params.copy()
        self.has_unsaved_changes = False
        self.update_save_status()

        QMessageBox.information(
            self,
            "Success",
            "Risk levels applied successfully.\n\n"
            "The trading system will use these levels immediately.",
        )

    def accept_parameters(self):
        """Accept parameters and close dialog"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Apply them before closing?",
                QMessageBox.Yes
                | QMessageBox.No
                | QMessageBox.Cancel,
            )

            if reply == QMessageBox.Cancel:
                return
            elif reply == QMessageBox.Yes:
                self.apply_parameters()

        super().accept()

    def reject(self):
        """Handle dialog rejection"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.No:
                return

        super().reject()


# ==============================================================================
# CONVENIENCE FUNCTION
# ==============================================================================


def show_risk_parameters_dialog(
    parent=None, current_params: dict | None = None
) -> dict | None:
    """
    Show the risk levels dialog and return the configured parameters

    Args:
        parent: Parent widget
        current_params: Dictionary of current parameters

    Returns:
        Dictionary of configured parameters if accepted, None if cancelled
    """
    dialog = RiskParametersDialog(parent, current_params)

    # Connect to parent if available
    if parent and hasattr(parent, "update_risk_parameters"):
        dialog.parameters_updated.connect(parent.update_risk_parameters)

    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        return dialog.get_parameters()

    return None


# ==============================================================================
# MAIN ENTRY POINT (FOR TESTING)
# ==============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Test the dialog standalone
    params = show_risk_parameters_dialog()

    if params:
        pass
    else:
        pass

    sys.exit(0)
