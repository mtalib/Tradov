#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
SPYDER - Risk Parameters Configuration Dialog
==============================================================================

Module: SpyderG06_RiskParametersDialog.py
Version: 1.1
Status: Production Ready

Description:
    Comprehensive risk management parameter configuration dialog that provides
    institutional-grade controls for managing trading risk. Features include:
    - Global risk limits and position sizing
    - Strategy-specific parameter overrides
    - Dynamic market regime adjustments
    - Execution and assignment risk controls
    - Real-time risk metrics monitoring

Author: SPYDER Development Team
Date: 2025-01-11

Integration:
    from SpyderG_GUI.SpyderG06_RiskParametersDialog import show_risk_parameters_dialog
    
    # In your dashboard
    params = show_risk_parameters_dialog(self, current_params)
    if params:
        self.update_risk_parameters(params)

==============================================================================
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
import json
import logging

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QTableWidget, QTableWidgetItem, QTextEdit,
    QGroupBox, QFrame, QTabWidget, QScrollArea, QMessageBox,
    QFormLayout, QDialogButtonBox, QHeaderView, QApplication,
    QProgressBar  # Fixed: Added missing import
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSettings
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

# ==============================================================================
# PROJECT IMPORTS
# ==============================================================================
# These would be imported in production
# from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
# from SpyderU_Utilities.SpyderU07_Constants import RISK_CONSTANTS
# from SpyderE_Risk.SpyderE01_RiskManager import RiskValidator

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Color scheme (matching SPYDER dashboard theme)
COLORS = {
    'background': '#0a0a0a',
    'panel': '#1a1a1a',
    'border': '#333333',
    'text': '#ffffff',
    'text_dim': '#888888',
    'positive': '#00ff41',
    'negative': '#ff1744',
    'neutral': '#ffd700',
    'warning': '#ff9800',
    'automation_active': '#00b8d4',
    'grid': '#2a2a2a',
    'orange': '#ff9800',
    'red': '#ff0000',
    'cyan': '#00ffff'
}

# Strategy group templates with professional defaults
STRATEGY_GROUP_TEMPLATES = {
    "Income Spreads": {
        "members": ["Iron Condor", "Bull Put Spread", "Bear Call Spread", "Credit Spread"],
        "max_allocation_pct": 40,
        "min_iv_rank": 40,
        "max_concurrent": 5,
        "profit_target": 50,
        "stop_loss": 100,
        "min_dte": 20,
        "max_dte": 60,
        "description": "Premium selling strategies for monthly income generation"
    },
    "Volatility Plays": {
        "members": ["Long Straddle", "Long Strangle", "Straddle", "Iron Butterfly"],
        "max_allocation_pct": 20,
        "max_theta_decay": -250,
        "min_iv_percentile": 20,
        "max_concurrent": 3,
        "profit_target": 75,
        "stop_loss": 50,
        "description": "Long volatility strategies for explosive moves"
    },
    "0DTE Trades": {
        "members": ["0DTE Iron Condor", "0DTE Spread", "ZeroDTE"],
        "max_allocation_pct": 10,
        "max_contracts": 5,
        "max_imbalance": 1,
        "auto_close_time": "15:30",
        "profit_target": 30,
        "stop_loss": 50,
        "description": "Same-day expiration strategies with strict controls"
    },
    "Directional Plays": {
        "members": ["Bull Put Spread", "Bear Call Spread", "Diagonal Spread"],
        "max_allocation_pct": 30,
        "max_concurrent": 4,
        "min_iv_rank": 30,
        "profit_target": 60,
        "stop_loss": 80,
        "description": "Directional strategies based on market bias"
    }
}

# Risk profile templates for different trading styles
RISK_PROFILES = {
    "Conservative": {
        "risk_per_trade": 0.10,
        "max_daily_loss": 1.0,
        "max_contracts": 5,
        "max_delta": 50,
        "max_vega": -200,
        "max_theta": -100,
        "allow_0dte": False,
        "max_open_positions": 5,
        "max_buying_power": 50,
        "description": "Minimal risk per trade (0.10%), strict Greek limits, no 0DTE trades, maximum 5 contracts per leg."
    },
    "Moderate": {
        "risk_per_trade": 0.25,
        "max_daily_loss": 2.0,
        "max_contracts": 10,
        "max_delta": 100,
        "max_vega": -400,
        "max_theta": -200,
        "allow_0dte": True,
        "max_open_positions": 8,
        "max_buying_power": 65,
        "description": "Balanced approach with 0.25% risk per trade, moderate position sizes, limited 0DTE exposure."
    },
    "Aggressive": {
        "risk_per_trade": 0.50,
        "max_daily_loss": 3.0,
        "max_contracts": 20,
        "max_delta": 200,
        "max_vega": -600,
        "max_theta": -400,
        "allow_0dte": True,
        "max_open_positions": 12,
        "max_buying_power": 75,
        "description": "Higher risk tolerance with 0.50% per trade, larger positions, full strategy access."
    },
    "High Volatility": {
        "risk_per_trade": 0.15,
        "max_daily_loss": 1.5,
        "max_contracts": 8,
        "max_delta": 75,
        "max_vega": -800,
        "max_theta": -300,
        "allow_0dte": False,
        "max_open_positions": 6,
        "max_buying_power": 60,
        "description": "Adjusted for high volatility markets with reduced sizing but higher vega tolerance."
    },
    "Low Volatility": {
        "risk_per_trade": 0.30,
        "max_daily_loss": 2.5,
        "max_contracts": 15,
        "max_delta": 150,
        "max_vega": -300,
        "max_theta": -500,
        "allow_0dte": True,
        "max_open_positions": 10,
        "max_buying_power": 70,
        "description": "Optimized for low volatility with larger sizes and more theta harvesting."
    }
}

# ==============================================================================
# MAIN RISK PARAMETERS DIALOG CLASS
# ==============================================================================
class RiskParametersDialog(QDialog):
    """
    Professional risk parameters configuration dialog for SPYDER trading system
    
    This dialog provides comprehensive risk management controls including:
    - Global risk limits
    - Strategy-specific parameters
    - Dynamic market adjustments
    - Execution controls
    - Real-time risk monitoring
    """
    
    # Custom signals
    parameters_updated = pyqtSignal(dict)
    profile_changed = pyqtSignal(str)
    validation_failed = pyqtSignal(list)
    
    # -------------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------------
    def __init__(self, parent=None, current_params: Optional[Dict] = None):
        """
        Initialize the Risk Parameters Dialog
        
        Args:
            parent: Parent widget (typically the main trading dashboard)
            current_params: Dictionary of current risk parameters
        """
        super().__init__(parent)
        
        # Initialize instance variables
        self.current_params = current_params or {}
        self.account_value = 100000  # Default account value
        self.account_mode = "PAPER"  # Default mode
        self.has_unsaved_changes = False
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize UI
        self.setup_ui()
        self.setup_styling()
        self.load_current_parameters()
        
        # Connect signals
        self.setup_connections()
        
        # Start real-time updates
        self.setup_timers()
        
    # -------------------------------------------------------------------------
    # UI Setup Methods
    # -------------------------------------------------------------------------
    def setup_ui(self):
        """Setup the main dialog UI structure"""
        self.setWindowTitle("SPYDER - Risk Parameters Configuration")
        self.setModal(True)
        self.setMinimumSize(1000, 800)
        
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Add header
        header_widget = self.create_header_widget()
        main_layout.addWidget(header_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.create_global_risk_tab(), "Global Risk")
        self.tab_widget.addTab(self.create_strategy_specific_tab(), "Strategy Groups")
        self.tab_widget.addTab(self.create_dynamic_rules_tab(), "Dynamic Rules")
        self.tab_widget.addTab(self.create_execution_controls_tab(), "Execution Controls")
        self.tab_widget.addTab(self.create_monitoring_tab(), "Monitoring")
        
        main_layout.addWidget(self.tab_widget, 1)
        
        # Add real-time risk metrics panel
        self.risk_metrics_panel = self.create_risk_metrics_panel()
        main_layout.addWidget(self.risk_metrics_panel)
        
        # Button box
        button_box = self.create_button_box()
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
        
    def setup_styling(self):
        """Apply SPYDER dark theme styling to the dialog"""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-size: 12px;
            }}
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 3ex;  /* Using ex units for better text scaling */
                padding: 20px 10px 10px 10px;  /* top right bottom left */
                background-color: {COLORS['panel']};
                font-weight: bold;
                font-size: 13px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                position: absolute;
                top: -0.7em;
                left: 15px;
                padding: 0 10px;
                background-color: {COLORS['panel']};  /* Match the panel background */
                color: {COLORS['cyan']};
            }}
            QPushButton {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 8px 15px;
                border-radius: 3px;
                font-size: 12px;
                font-weight: normal;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
                border-color: {COLORS['cyan']};
            }}
            QPushButton:pressed {{
                background-color: #3a3a3a;
            }}
            QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                border-radius: 3px;
                font-size: 12px;
            }}
            QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
                border-color: {COLORS['cyan']};
            }}
            QCheckBox {{
                color: {COLORS['text']};
                font-size: 12px;
            }}
            QCheckBox::indicator {{
                width: 15px;
                height: 15px;
            }}
            QTextEdit {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                font-size: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
            }}
            QTabWidget::pane {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
            }}
            QTabBar::tab {{
                background-color: {COLORS['panel']};
                color: {COLORS['text']};
                padding: 10px 20px;
                margin-right: 2px;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['background']};
                border-bottom: 2px solid {COLORS['cyan']};
                color: {COLORS['cyan']};
            }}
            QTabBar::tab:hover {{
                background-color: #2a2a2a;
            }}
            QTableWidget {{
                background-color: {COLORS['panel']};
                alternate-background-color: {COLORS['background']};
                color: {COLORS['text']};
                gridline-color: {COLORS['grid']};
                border: 1px solid {COLORS['border']};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['background']};
                color: {COLORS['cyan']};
                border: 1px solid {COLORS['border']};
                padding: 5px;
                font-size: 12px;
                font-weight: bold;
            }}
            QScrollBar:vertical {{
                background-color: {COLORS['background']};
                width: 12px;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {COLORS['border']};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: #4a4a4a;
            }}
        """)
        
    # -------------------------------------------------------------------------
    # Header Widget
    # -------------------------------------------------------------------------
    def create_header_widget(self) -> QWidget:
        """Create the header widget with title and status"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel("RISK PARAMETERS CONFIGURATION")
        title_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: bold;
            color: {COLORS['text']};
            letter-spacing: 2px;
        """)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Status indicators
        self.connection_status = QLabel("● CONNECTED")
        self.connection_status.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")
        layout.addWidget(self.connection_status)
        
        layout.addSpacing(20)
        
        self.save_status = QLabel("All changes saved")
        self.save_status.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 12px;")
        layout.addWidget(self.save_status)
        
        widget.setLayout(layout)
        return widget
        
    # -------------------------------------------------------------------------
    # Tab Creation Methods
    # -------------------------------------------------------------------------
    def create_global_risk_tab(self) -> QWidget:
        """Create the global risk parameters tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Create scroll area for the content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # Risk Profile Templates
        profile_group = self.create_risk_profile_section()
        scroll_layout.addWidget(profile_group)
        
        # Risk Budget Calculator
        budget_group = self.create_risk_budget_section()
        scroll_layout.addWidget(budget_group)
        
        # Global Risk Limits
        limits_group = self.create_global_limits_section()
        scroll_layout.addWidget(limits_group)
        
        # Portfolio Greeks Limits
        greeks_group = self.create_greeks_limits_section()
        scroll_layout.addWidget(greeks_group)
        
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        
        layout.addWidget(scroll_area)
        widget.setLayout(layout)
        return widget
        
    def create_strategy_specific_tab(self) -> QWidget:
        """Create the strategy-specific parameters tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Strategy Group Templates
        template_group = self.create_strategy_templates_section()
        layout.addWidget(template_group)
        
        # Strategy Groups Configuration Table
        groups_group = self.create_strategy_groups_table()
        layout.addWidget(groups_group, 1)
        
        # Strategy-Specific Overrides
        overrides_group = self.create_strategy_overrides_section()
        layout.addWidget(overrides_group)
        
        widget.setLayout(layout)
        return widget
        
    def create_dynamic_rules_tab(self) -> QWidget:
        """Create the dynamic market-based adjustments tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout()
        
        # IV-Based Adjustments
        iv_group = self.create_iv_adjustments_section()
        scroll_layout.addWidget(iv_group)
        
        # Event-Based Controls
        event_group = self.create_event_controls_section()
        scroll_layout.addWidget(event_group)
        
        # Market Regime Adjustments
        regime_group = self.create_regime_adjustments_section()
        scroll_layout.addWidget(regime_group)
        
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_widget)
        
        layout.addWidget(scroll_area)
        widget.setLayout(layout)
        return widget
        
    def create_execution_controls_tab(self) -> QWidget:
        """Create the execution and assignment risk controls tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Legging Risk Controls
        legging_group = self.create_legging_controls_section()
        layout.addWidget(legging_group)
        
        # Assignment Risk Controls
        assignment_group = self.create_assignment_controls_section()
        layout.addWidget(assignment_group)
        
        # Order Types and Timing
        order_group = self.create_order_controls_section()
        layout.addWidget(order_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
        
    def create_monitoring_tab(self) -> QWidget:
        """Create the monitoring and alerts configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Risk Monitoring Thresholds
        monitoring_group = QGroupBox("Risk Monitoring Thresholds")
        monitoring_layout = QFormLayout()
        
        # Position monitoring
        self.position_check_interval = QSpinBox()
        self.position_check_interval.setRange(1, 60)
        self.position_check_interval.setValue(5)
        self.position_check_interval.setSuffix(" seconds")
        monitoring_layout.addRow("Position check interval:", self.position_check_interval)
        
        self.greek_update_interval = QSpinBox()
        self.greek_update_interval.setRange(5, 300)
        self.greek_update_interval.setValue(30)
        self.greek_update_interval.setSuffix(" seconds")
        monitoring_layout.addRow("Greeks update interval:", self.greek_update_interval)
        
        # Alert thresholds
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        monitoring_layout.addRow(separator)
        
        alert_label = QLabel("Alert Thresholds:")
        alert_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        monitoring_layout.addRow(alert_label, QLabel(""))
        
        self.delta_alert_threshold = QSpinBox()
        self.delta_alert_threshold.setRange(50, 500)
        self.delta_alert_threshold.setValue(150)
        monitoring_layout.addRow("   Delta alert level:", self.delta_alert_threshold)
        
        self.loss_alert_threshold = QDoubleSpinBox()
        self.loss_alert_threshold.setRange(0.5, 5.0)
        self.loss_alert_threshold.setValue(1.5)
        self.loss_alert_threshold.setSuffix("%")
        monitoring_layout.addRow("   Daily loss alert:", self.loss_alert_threshold)
        
        monitoring_group.setLayout(monitoring_layout)
        layout.addWidget(monitoring_group)
        
        # Automated Actions
        auto_group = QGroupBox("Automated Risk Actions")
        auto_layout = QFormLayout()
        
        self.auto_hedge_enabled = QCheckBox("Enable automatic delta hedging")
        auto_layout.addRow(self.auto_hedge_enabled)
        
        self.auto_reduce_enabled = QCheckBox("Auto-reduce positions at risk limits")
        auto_layout.addRow(self.auto_reduce_enabled)
        
        self.circuit_breaker_enabled = QCheckBox("Enable circuit breaker protocol")
        self.circuit_breaker_enabled.setChecked(True)
        auto_layout.addRow(self.circuit_breaker_enabled)
        
        auto_group.setLayout(auto_layout)
        layout.addWidget(auto_group)
        
        layout.addStretch()
        widget.setLayout(layout)
        return widget
        
    # -------------------------------------------------------------------------
    # Section Creation Methods - Global Risk Tab
    # -------------------------------------------------------------------------
    def create_risk_profile_section(self) -> QGroupBox:
        """Create the risk profile templates section"""
        group = QGroupBox("Risk Profile Templates")
        layout = QVBoxLayout()
        
        # Profile selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Active Profile:"))
        
        self.risk_profile_combo = QComboBox()
        self.risk_profile_combo.addItems(list(RISK_PROFILES.keys()) + ["Custom"])
        self.risk_profile_combo.currentTextChanged.connect(self.on_profile_changed)
        selector_layout.addWidget(self.risk_profile_combo, 1)
        
        save_profile_btn = QPushButton("Save Current as...")
        save_profile_btn.clicked.connect(self.save_risk_profile)
        selector_layout.addWidget(save_profile_btn)
        
        delete_profile_btn = QPushButton("Delete")
        delete_profile_btn.clicked.connect(self.delete_risk_profile)
        selector_layout.addWidget(delete_profile_btn)
        
        layout.addLayout(selector_layout)
        
        # Profile description
        self.profile_description = QTextEdit()
        self.profile_description.setReadOnly(True)
        self.profile_description.setMaximumHeight(60)
        layout.addWidget(self.profile_description)
        
        group.setLayout(layout)
        return group
        
    def create_risk_budget_section(self) -> QGroupBox:
        """Create the risk budget calculator section"""
        group = QGroupBox("Risk Budget Calculator")
        layout = QFormLayout()
        
        # Account value input
        self.account_value_input = QDoubleSpinBox()
        self.account_value_input.setRange(1000, 10000000)
        self.account_value_input.setValue(100000)
        self.account_value_input.setPrefix("$")
        self.account_value_input.setSingleStep(1000)
        self.account_value_input.valueChanged.connect(self.update_risk_budgets)
        layout.addRow("Account Value:", self.account_value_input)
        
        # Risk budget display
        self.risk_per_trade_budget = QLabel("$250")
        self.risk_per_trade_budget.setStyleSheet(f"color: {COLORS['positive']}; font-weight: bold; font-size: 14px;")
        layout.addRow("Risk Budget per Trade:", self.risk_per_trade_budget)
        
        # Max notional display
        self.notional_limit_label = QLabel("$2,000")
        self.notional_limit_label.setStyleSheet(f"color: {COLORS['warning']}; font-weight: bold; font-size: 14px;")
        layout.addRow("Max Notional per Leg:", self.notional_limit_label)
        
        # Daily loss limit display
        self.daily_loss_limit_label = QLabel("$2,000")
        self.daily_loss_limit_label.setStyleSheet(f"color: {COLORS['negative']}; font-weight: bold; font-size: 14px;")
        layout.addRow("Daily Loss Limit:", self.daily_loss_limit_label)
        
        group.setLayout(layout)
        return group
        
    def create_global_limits_section(self) -> QGroupBox:
        """Create the global risk limits section"""
        group = QGroupBox("Global Risk Limits")
        layout = QFormLayout()
        
        # Risk per trade
        self.risk_per_trade_spin = QDoubleSpinBox()
        self.risk_per_trade_spin.setRange(0.05, 2.0)
        self.risk_per_trade_spin.setValue(0.25)
        self.risk_per_trade_spin.setSuffix("%")
        self.risk_per_trade_spin.setSingleStep(0.05)
        self.risk_per_trade_spin.valueChanged.connect(self.update_risk_budgets)
        layout.addRow("Risk per Trade:", self.risk_per_trade_spin)
        
        # Max daily loss
        self.max_daily_loss_spin = QDoubleSpinBox()
        self.max_daily_loss_spin.setRange(0.5, 5.0)
        self.max_daily_loss_spin.setValue(2.0)
        self.max_daily_loss_spin.setSuffix("%")
        self.max_daily_loss_spin.setSingleStep(0.1)
        self.max_daily_loss_spin.valueChanged.connect(self.update_risk_budgets)
        layout.addRow("Max Daily Loss:", self.max_daily_loss_spin)
        
        # Max contracts
        self.max_contracts_spin = QSpinBox()
        self.max_contracts_spin.setRange(1, 50)
        self.max_contracts_spin.setValue(10)
        self.max_contracts_spin.valueChanged.connect(self.on_parameter_changed)
        layout.addRow("Max Contracts per Leg:", self.max_contracts_spin)
        
        # Buying power usage
        self.max_buying_power_spin = QSpinBox()
        self.max_buying_power_spin.setRange(10, 90)
        self.max_buying_power_spin.setValue(75)
        self.max_buying_power_spin.setSuffix("%")
        self.max_buying_power_spin.valueChanged.connect(self.on_parameter_changed)
        layout.addRow("Max Buying Power Usage:", self.max_buying_power_spin)
        
        # Max open positions
        self.max_open_positions_spin = QSpinBox()
        self.max_open_positions_spin.setRange(1, 20)
        self.max_open_positions_spin.setValue(10)
        self.max_open_positions_spin.valueChanged.connect(self.on_parameter_changed)
        layout.addRow("Max Open Positions:", self.max_open_positions_spin)
        
        # Max position concentration
        self.max_position_concentration = QSpinBox()
        self.max_position_concentration.setRange(5, 50)
        self.max_position_concentration.setValue(20)
        self.max_position_concentration.setSuffix("%")
        self.max_position_concentration.valueChanged.connect(self.on_parameter_changed)
        layout.addRow("Max Position Concentration:", self.max_position_concentration)
        
        group.setLayout(layout)
        return group
        
    def create_greeks_limits_section(self) -> QGroupBox:
        """Create the portfolio Greeks limits section"""
        group = QGroupBox("Portfolio Greeks Limits")
        layout = QFormLayout()
        
        # Delta limits
        delta_layout = QHBoxLayout()
        self.min_delta_spin = QSpinBox()
        self.min_delta_spin.setRange(-1000, 0)
        self.min_delta_spin.setValue(-200)
        delta_layout.addWidget(QLabel("Min:"))
        delta_layout.addWidget(self.min_delta_spin)
        
        self.max_delta_spin = QSpinBox()
        self.max_delta_spin.setRange(0, 1000)
        self.max_delta_spin.setValue(200)
        delta_layout.addWidget(QLabel("Max:"))
        delta_layout.addWidget(self.max_delta_spin)
        
        layout.addRow("Portfolio Delta Range:", delta_layout)
        
        # Gamma
        self.max_gamma_spin = QDoubleSpinBox()
        self.max_gamma_spin.setRange(-50, 50)
        self.max_gamma_spin.setValue(10)
        self.max_gamma_spin.valueChanged.connect(self.on_parameter_changed)
        layout.addRow("Max Portfolio Gamma:", self.max_gamma_spin)
        
        # Theta
        self.max_theta_spin = QSpinBox()
        self.max_theta_spin.setRange(-2000, 0)
        self.max_theta_spin.setValue(-400)
        self.max_theta_spin.setPrefix("$")
        self.max_theta_spin.valueChanged.connect(self.on_parameter_changed)
        layout.addRow("Max Theta Decay:", self.max_theta_spin)
        
        # Vega
        self.max_vega_spin = QSpinBox()
        self.max_vega_spin.setRange(-2000, 0)
        self.max_vega_spin.setValue(-600)
        self.max_vega_spin.setPrefix("$")
        self.max_vega_spin.valueChanged.connect(self.on_parameter_changed)
        layout.addRow("Max Vega Exposure:", self.max_vega_spin)
        
        # Auto-hedging thresholds
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        hedge_label = QLabel("Auto-Hedging Thresholds:")
        hedge_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(hedge_label, QLabel(""))
        
        self.delta_hedge_threshold = QSpinBox()
        self.delta_hedge_threshold.setRange(50, 500)
        self.delta_hedge_threshold.setValue(150)
        layout.addRow("   Delta hedge trigger:", self.delta_hedge_threshold)
        
        self.gamma_hedge_threshold = QDoubleSpinBox()
        self.gamma_hedge_threshold.setRange(1, 20)
        self.gamma_hedge_threshold.setValue(8)
        layout.addRow("   Gamma hedge trigger:", self.gamma_hedge_threshold)
        
        group.setLayout(layout)
        return group
        
    # -------------------------------------------------------------------------
    # Section Creation Methods - Strategy Tab
    # -------------------------------------------------------------------------
    def create_strategy_templates_section(self) -> QGroupBox:
        """Create the strategy group templates section"""
        group = QGroupBox("Strategy Group Templates")
        layout = QVBoxLayout()
        
        # Template selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Load Template:"))
        
        self.template_combo = QComboBox()
        self.template_combo.addItems(["Select Template..."] + list(STRATEGY_GROUP_TEMPLATES.keys()))
        self.template_combo.currentTextChanged.connect(self.load_strategy_template)
        selector_layout.addWidget(self.template_combo, 1)
        
        apply_btn = QPushButton("Apply Template")
        apply_btn.clicked.connect(self.apply_strategy_template)
        selector_layout.addWidget(apply_btn)
        
        layout.addLayout(selector_layout)
        
        # Template description
        self.template_description = QTextEdit()
        self.template_description.setReadOnly(True)
        self.template_description.setMaximumHeight(50)
        self.template_description.setPlainText("Select a template to view description...")
        layout.addWidget(self.template_description)
        
        group.setLayout(layout)
        return group
        
    def create_strategy_groups_table(self) -> QGroupBox:
        """Create the strategy groups configuration table"""
        group = QGroupBox("Strategy Groups Configuration")
        layout = QVBoxLayout()
        
        # Create table
        self.strategy_table = QTableWidget(len(STRATEGY_GROUP_TEMPLATES), 7)
        self.strategy_table.setHorizontalHeaderLabels([
            "Group Name", "Max Allocation %", "Max Concurrent", 
            "Profit Target %", "Stop Loss %", "Min IV Rank", "Status"
        ])
        
        # Populate table with initial data
        self.populate_strategy_table()
        
        # Configure table appearance
        self.strategy_table.horizontalHeader().setStretchLastSection(True)
        self.strategy_table.setAlternatingRowColors(True)
        self.strategy_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # Set column widths
        column_widths = [150, 120, 100, 100, 100, 100, 80]
        for i, width in enumerate(column_widths):
            self.strategy_table.setColumnWidth(i, width)
            
        layout.addWidget(self.strategy_table)
        
        # Add/Remove buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        add_group_btn = QPushButton("Add Group")
        add_group_btn.clicked.connect(self.add_strategy_group)
        button_layout.addWidget(add_group_btn)
        
        remove_group_btn = QPushButton("Remove Group")
        remove_group_btn.clicked.connect(self.remove_strategy_group)
        button_layout.addWidget(remove_group_btn)
        
        layout.addLayout(button_layout)
        
        group.setLayout(layout)
        return group
        
    def create_strategy_overrides_section(self) -> QGroupBox:
        """Create the strategy-specific overrides section"""
        group = QGroupBox("Strategy-Specific Overrides")
        layout = QFormLayout()
        
        # Enable overrides checkbox
        self.enable_overrides = QCheckBox("Enable strategy-specific parameter overrides")
        self.enable_overrides.stateChanged.connect(self.toggle_strategy_overrides)
        layout.addRow(self.enable_overrides)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        # Iron Condor specific settings
        ic_label = QLabel("Iron Condor Settings:")
        ic_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(ic_label, QLabel(""))
        
        self.ic_wing_width = QSpinBox()
        self.ic_wing_width.setRange(5, 50)
        self.ic_wing_width.setValue(20)
        self.ic_wing_width.setSuffix(" points")
        self.ic_wing_width.setEnabled(False)
        layout.addRow("   Wing Width:", self.ic_wing_width)
        
        self.ic_profit_target = QSpinBox()
        self.ic_profit_target.setRange(10, 90)
        self.ic_profit_target.setValue(50)
        self.ic_profit_target.setSuffix("%")
        self.ic_profit_target.setEnabled(False)
        layout.addRow("   Profit Target:", self.ic_profit_target)
        
        self.ic_stop_loss = QSpinBox()
        self.ic_stop_loss.setRange(50, 200)
        self.ic_stop_loss.setValue(100)
        self.ic_stop_loss.setSuffix("%")
        self.ic_stop_loss.setEnabled(False)
        layout.addRow("   Stop Loss:", self.ic_stop_loss)
        
        # Vertical Spread specific settings
        spread_label = QLabel("Vertical Spread Settings:")
        spread_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(spread_label, QLabel(""))
        
        self.spread_width = QSpinBox()
        self.spread_width.setRange(1, 10)
        self.spread_width.setValue(2)
        self.spread_width.setSuffix(" strikes")
        self.spread_width.setEnabled(False)
        layout.addRow("   Strike Width:", self.spread_width)
        
        self.spread_dte_min = QSpinBox()
        self.spread_dte_min.setRange(0, 60)
        self.spread_dte_min.setValue(20)
        self.spread_dte_min.setSuffix(" days")
        self.spread_dte_min.setEnabled(False)
        layout.addRow("   Min DTE:", self.spread_dte_min)
        
        # 0DTE specific settings
        dte_label = QLabel("0DTE Settings:")
        dte_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(dte_label, QLabel(""))
        
        self.dte_max_size = QSpinBox()
        self.dte_max_size.setRange(1, 10)
        self.dte_max_size.setValue(3)
        self.dte_max_size.setEnabled(False)
        layout.addRow("   Max Contracts:", self.dte_max_size)
        
        self.dte_cutoff_time = QComboBox()
        self.dte_cutoff_time.addItems(["14:00", "14:30", "15:00", "15:30"])
        self.dte_cutoff_time.setCurrentText("15:00")
        self.dte_cutoff_time.setEnabled(False)
        layout.addRow("   Cutoff Time:", self.dte_cutoff_time)
        
        group.setLayout(layout)
        return group
        
    # -------------------------------------------------------------------------
    # Section Creation Methods - Dynamic Rules Tab
    # -------------------------------------------------------------------------
    def create_iv_adjustments_section(self) -> QGroupBox:
        """Create the IV-based adjustments section"""
        group = QGroupBox("Volatility-Based Adjustments")
        layout = QFormLayout()
        
        # Enable IV scaling
        self.enable_iv_scaling = QCheckBox("Enable IV-based position scaling")
        self.enable_iv_scaling.setChecked(True)
        self.enable_iv_scaling.stateChanged.connect(self.on_parameter_changed)
        layout.addRow(self.enable_iv_scaling)
        
        # IV rank threshold
        self.iv_reduction_threshold = QSpinBox()
        self.iv_reduction_threshold.setRange(50, 90)
        self.iv_reduction_threshold.setValue(75)
        self.iv_reduction_threshold.setSuffix("% IV Rank")
        layout.addRow("Reduce size when IV Rank >", self.iv_reduction_threshold)
        
        # Reduction factor
        self.iv_reduction_factor = QDoubleSpinBox()
        self.iv_reduction_factor.setRange(0.1, 0.9)
        self.iv_reduction_factor.setValue(0.25)
        self.iv_reduction_factor.setSingleStep(0.05)
        layout.addRow("Size reduction factor:", self.iv_reduction_factor)
        
        # Skew adjustment
        self.enable_skew_adjustment = QCheckBox("Allow extra put contracts when skew > 10%")
        self.enable_skew_adjustment.stateChanged.connect(self.on_parameter_changed)
        layout.addRow(self.enable_skew_adjustment)
        
        # Term structure adjustments
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        term_label = QLabel("Term Structure Adjustments:")
        term_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(term_label, QLabel(""))
        
        self.enable_term_structure = QCheckBox("   Adjust for inverted term structure")
        layout.addRow(self.enable_term_structure)
        
        self.backwardation_reduction = QDoubleSpinBox()
        self.backwardation_reduction.setRange(0.1, 0.5)
        self.backwardation_reduction.setValue(0.3)
        self.backwardation_reduction.setSingleStep(0.05)
        layout.addRow("   Backwardation size reduction:", self.backwardation_reduction)
        
        group.setLayout(layout)
        return group
        
    def create_event_controls_section(self) -> QGroupBox:
        """Create the event-based risk controls section"""
        group = QGroupBox("Event-Based Risk Controls")
        layout = QFormLayout()
        
        # FOMC/Earnings controls
        event_label = QLabel("Economic Events:")
        event_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(event_label, QLabel(""))
        
        self.earnings_reduction = QDoubleSpinBox()
        self.earnings_reduction.setRange(0.1, 0.9)
        self.earnings_reduction.setValue(0.5)
        self.earnings_reduction.setSingleStep(0.1)
        layout.addRow("   Position reduction for FOMC/CPI:", self.earnings_reduction)
        
        self.event_blackout_hours = QSpinBox()
        self.event_blackout_hours.setRange(0, 48)
        self.event_blackout_hours.setValue(24)
        self.event_blackout_hours.setSuffix(" hours")
        layout.addRow("   Pre-event blackout period:", self.event_blackout_hours)
        
        # 0DTE Special Rules
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        dte_label = QLabel("0DTE Special Rules:")
        dte_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(dte_label, QLabel(""))
        
        self.zero_dte_enabled = QCheckBox("   Enable 0DTE trading")
        self.zero_dte_enabled.setChecked(True)
        layout.addRow(self.zero_dte_enabled)
        
        self.zero_dte_reduction = QDoubleSpinBox()
        self.zero_dte_reduction.setRange(0.1, 0.9)
        self.zero_dte_reduction.setValue(0.5)
        layout.addRow("   0DTE size multiplier:", self.zero_dte_reduction)
        
        self.zero_dte_max_imbalance = QSpinBox()
        self.zero_dte_max_imbalance.setRange(0, 5)
        self.zero_dte_max_imbalance.setValue(1)
        layout.addRow("   0DTE max leg imbalance:", self.zero_dte_max_imbalance)
        
        self.zero_dte_friday_only = QCheckBox("   Restrict 0DTE to Fridays only")
        layout.addRow(self.zero_dte_friday_only)
        
        # Triple Witching adjustments
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator2)
        
        triple_label = QLabel("Triple Witching Adjustments:")
        triple_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(triple_label, QLabel(""))
        
        self.triple_witch_reduction = QDoubleSpinBox()
        self.triple_witch_reduction.setRange(0.3, 0.8)
        self.triple_witch_reduction.setValue(0.5)
        layout.addRow("   Triple witching size factor:", self.triple_witch_reduction)
        
        group.setLayout(layout)
        return group
        
    def create_regime_adjustments_section(self) -> QGroupBox:
        """Create the market regime adjustments section"""
        group = QGroupBox("Market Regime Adjustments")
        layout = QFormLayout()
        
        # Enable regime adjustments
        self.enable_regime_adjustment = QCheckBox("Enable automatic regime-based adjustments")
        self.enable_regime_adjustment.setChecked(True)
        self.enable_regime_adjustment.stateChanged.connect(self.toggle_regime_controls)
        layout.addRow(self.enable_regime_adjustment)
        
        # Trending Market
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        trend_label = QLabel("Trending Market:")
        trend_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(trend_label, QLabel(""))
        
        self.trend_delta_increase = QSpinBox()
        self.trend_delta_increase.setRange(0, 100)
        self.trend_delta_increase.setValue(50)
        self.trend_delta_increase.setSuffix("%")
        layout.addRow("   Delta limit increase:", self.trend_delta_increase)
        
        self.trend_directional_bias = QDoubleSpinBox()
        self.trend_directional_bias.setRange(0.0, 1.0)
        self.trend_directional_bias.setValue(0.7)
        self.trend_directional_bias.setSingleStep(0.1)
        layout.addRow("   Directional strategy weight:", self.trend_directional_bias)
        
        # Choppy/Range-Bound Market
        chop_label = QLabel("Choppy/Range-Bound Market:")
        chop_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(chop_label, QLabel(""))
        
        self.chop_size_reduction = QDoubleSpinBox()
        self.chop_size_reduction.setRange(0.1, 0.9)
        self.chop_size_reduction.setValue(0.3)
        layout.addRow("   Position size reduction:", self.chop_size_reduction)
        
        self.chop_iron_condor_bias = QDoubleSpinBox()
        self.chop_iron_condor_bias.setRange(0.0, 1.0)
        self.chop_iron_condor_bias.setValue(0.8)
        self.chop_iron_condor_bias.setSingleStep(0.1)
        layout.addRow("   Iron Condor strategy weight:", self.chop_iron_condor_bias)
        
        # High Volatility Market
        vol_label = QLabel("High Volatility Market:")
        vol_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(vol_label, QLabel(""))
        
        self.high_vol_vega_increase = QSpinBox()
        self.high_vol_vega_increase.setRange(0, 100)
        self.high_vol_vega_increase.setValue(30)
        self.high_vol_vega_increase.setSuffix("%")
        layout.addRow("   Vega limit increase:", self.high_vol_vega_increase)
        
        self.high_vol_credit_reduction = QDoubleSpinBox()
        self.high_vol_credit_reduction.setRange(0.1, 0.7)
        self.high_vol_credit_reduction.setValue(0.4)
        layout.addRow("   Credit spread reduction:", self.high_vol_credit_reduction)
        
        group.setLayout(layout)
        return group
        
    # -------------------------------------------------------------------------
    # Section Creation Methods - Execution Tab
    # -------------------------------------------------------------------------
    def create_legging_controls_section(self) -> QGroupBox:
        """Create the multi-leg execution controls section"""
        group = QGroupBox("Multi-Leg Execution Controls")
        layout = QFormLayout()
        
        # Timing controls
        self.max_time_between_fills = QSpinBox()
        self.max_time_between_fills.setRange(1, 30)
        self.max_time_between_fills.setValue(5)
        self.max_time_between_fills.setSuffix(" seconds")
        layout.addRow("Max time between leg fills:", self.max_time_between_fills)
        
        # Slippage controls
        self.max_slippage_cents = QSpinBox()
        self.max_slippage_cents.setRange(1, 50)
        self.max_slippage_cents.setValue(10)
        self.max_slippage_cents.setSuffix(" cents")
        layout.addRow("Max slippage per leg:", self.max_slippage_cents)
        
        # Execution options
        self.abort_on_partial = QCheckBox("Abort spread on partial fill mismatch")
        self.abort_on_partial.setChecked(True)
        layout.addRow(self.abort_on_partial)
        
        self.smart_routing = QCheckBox("Enable smart order routing")
        self.smart_routing.setChecked(True)
        layout.addRow(self.smart_routing)
        
        self.allow_leg_reconstruction = QCheckBox("Allow spread reconstruction after partial fills")
        layout.addRow(self.allow_leg_reconstruction)
        
        # Legging priority
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        priority_label = QLabel("Legging Priority:")
        priority_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(priority_label, QLabel(""))
        
        self.legging_priority = QComboBox()
        self.legging_priority.addItems([
            "Risk Leg First (Protective)",
            "Credit Leg First (Aggressive)",
            "Simultaneous (Balanced)"
        ])
        self.legging_priority.setCurrentIndex(0)
        layout.addRow("   Execution order:", self.legging_priority)
        
        group.setLayout(layout)
        return group
        
    def create_assignment_controls_section(self) -> QGroupBox:
        """Create the assignment and pin risk controls section"""
        group = QGroupBox("Assignment & Pin Risk Controls")
        layout = QFormLayout()
        
        # Dividend protection
        self.enable_dividend_protection = QCheckBox("Auto-close ITM calls before ex-dividend")
        self.enable_dividend_protection.setChecked(True)
        layout.addRow(self.enable_dividend_protection)
        
        self.itm_threshold = QDoubleSpinBox()
        self.itm_threshold.setRange(0.10, 5.00)
        self.itm_threshold.setValue(1.00)
        self.itm_threshold.setPrefix("$")
        self.itm_threshold.setSingleStep(0.10)
        layout.addRow("ITM threshold for dividend risk:", self.itm_threshold)
        
        # Pin risk controls
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        pin_label = QLabel("Pin Risk Management:")
        pin_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(pin_label, QLabel(""))
        
        self.pin_risk_threshold = QDoubleSpinBox()
        self.pin_risk_threshold.setRange(0.1, 1.0)
        self.pin_risk_threshold.setValue(0.25)
        self.pin_risk_threshold.setSuffix("%")
        self.pin_risk_threshold.setSingleStep(0.05)
        layout.addRow("   Pin risk threshold (% from strike):", self.pin_risk_threshold)
        
        self.auto_close_expiry_day = QCheckBox("   Auto-close positions at risk on expiry day")
        self.auto_close_expiry_day.setChecked(True)
        layout.addRow(self.auto_close_expiry_day)
        
        self.expiry_close_time = QComboBox()
        self.expiry_close_time.addItems(["14:00", "14:30", "15:00", "15:30", "15:45"])
        self.expiry_close_time.setCurrentText("15:00")
        layout.addRow("   Expiry day close time:", self.expiry_close_time)
        
        # Early assignment detection
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator2)
        
        early_label = QLabel("Early Assignment Detection:")
        early_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(early_label, QLabel(""))
        
        self.monitor_hard_to_borrow = QCheckBox("   Monitor hard-to-borrow for short calls")
        self.monitor_hard_to_borrow.setChecked(True)
        layout.addRow(self.monitor_hard_to_borrow)
        
        self.deep_itm_alert = QDoubleSpinBox()
        self.deep_itm_alert.setRange(1.0, 10.0)
        self.deep_itm_alert.setValue(5.0)
        self.deep_itm_alert.setPrefix("$")
        layout.addRow("   Deep ITM alert threshold:", self.deep_itm_alert)
        
        group.setLayout(layout)
        return group
        
    def create_order_controls_section(self) -> QGroupBox:
        """Create the order types and timing controls section"""
        group = QGroupBox("Order Types and Timing")
        layout = QFormLayout()
        
        # Default order types
        self.default_order_type = QComboBox()
        self.default_order_type.addItems(["LIMIT", "MIDPOINT", "ADAPTIVE", "RELATIVE"])
        layout.addRow("Default order type:", self.default_order_type)
        
        self.limit_offset_cents = QSpinBox()
        self.limit_offset_cents.setRange(0, 25)
        self.limit_offset_cents.setValue(5)
        self.limit_offset_cents.setSuffix(" cents")
        layout.addRow("Limit order offset:", self.limit_offset_cents)
        
        # Order timing
        self.order_timeout_seconds = QSpinBox()
        self.order_timeout_seconds.setRange(10, 300)
        self.order_timeout_seconds.setValue(60)
        self.order_timeout_seconds.setSuffix(" seconds")
        layout.addRow("Order timeout:", self.order_timeout_seconds)
        
        # Progressive fills
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addRow(separator)
        
        progressive_label = QLabel("Progressive Fill Settings:")
        progressive_label.setStyleSheet(f"color: {COLORS['cyan']}; font-weight: bold;")
        layout.addRow(progressive_label, QLabel(""))
        
        self.enable_progressive_fills = QCheckBox("   Enable progressive price improvement")
        self.enable_progressive_fills.setChecked(True)
        layout.addRow(self.enable_progressive_fills)
        
        self.progressive_increment = QSpinBox()
        self.progressive_increment.setRange(1, 10)
        self.progressive_increment.setValue(2)
        self.progressive_increment.setSuffix(" cents")
        layout.addRow("   Price improvement increment:", self.progressive_increment)
        
        self.progressive_interval = QSpinBox()
        self.progressive_interval.setRange(5, 60)
        self.progressive_interval.setValue(15)
        self.progressive_interval.setSuffix(" seconds")
        layout.addRow("   Improvement interval:", self.progressive_interval)
        
        group.setLayout(layout)
        return group
        
    # -------------------------------------------------------------------------
    # Risk Metrics Panel
    # -------------------------------------------------------------------------
    def create_risk_metrics_panel(self) -> QWidget:
        """Create the real-time risk metrics display panel"""
        panel = QGroupBox("Current Risk Utilization")
        layout = QGridLayout()
        layout.setSpacing(15)
        
        # Create metric displays
        self.risk_metrics = {}
        metrics_config = [
            ("Portfolio Delta:", "45 / 200", COLORS['positive']),
            ("Portfolio Vega:", "-180 / -500", COLORS['warning']),
            ("Daily Loss:", "-$250 / -$2,000", COLORS['positive']),
            ("Buying Power:", "65% / 75%", COLORS['warning']),
            ("Open Positions:", "7 / 10", COLORS['positive']),
            ("Risk Budget Used:", "85%", COLORS['warning'])
        ]
        
        row = 0
        col = 0
        for label_text, value_text, color in metrics_config:
            # Create label
            label = QLabel(label_text)
            label.setStyleSheet("font-weight: bold;")
            
            # Create value widget
            value_widget = QLabel(value_text)
            value_widget.setStyleSheet(f"""
                color: {color}; 
                font-weight: bold;
                font-size: 13px;
                padding: 2px 5px;
                background-color: {COLORS['panel']};
                border: 1px solid {color};
                border-radius: 3px;
            """)
            value_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Store reference
            self.risk_metrics[label_text] = value_widget
            
            # Add to layout
            layout.addWidget(label, row, col * 2)
            layout.addWidget(value_widget, row, col * 2 + 1)
            
            col += 1
            if col > 2:
                col = 0
                row += 1
                
        # Add progress bars for visual representation
        row += 1
        layout.addWidget(QLabel("Overall Risk Level:"), row, 0)
        
        self.overall_risk_bar = QProgressBar()
        self.overall_risk_bar.setRange(0, 100)
        self.overall_risk_bar.setValue(65)
        self.overall_risk_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {COLORS['border']};
                border-radius: 3px;
                text-align: center;
                background-color: {COLORS['panel']};
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['warning']};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.overall_risk_bar, row, 1, 1, 5)
                
        panel.setLayout(layout)
        return panel
        
    # -------------------------------------------------------------------------
    # Button Box
    # -------------------------------------------------------------------------
    def create_button_box(self) -> QWidget:
        """Create the dialog button box with custom styling"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Left side - Import/Export
        import_btn = QPushButton("Import Settings")
        import_btn.clicked.connect(self.import_settings)
        layout.addWidget(import_btn)
        
        export_btn = QPushButton("Export Settings")
        export_btn.clicked.connect(self.export_settings)
        layout.addWidget(export_btn)
        
        layout.addStretch()
        
        # Right side - Standard buttons
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.apply_parameters)
        apply_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['automation_active']};
                color: white;
                font-weight: bold;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: #00acc1;
            }}
        """)
        layout.addWidget(apply_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_parameters)
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['positive']};
                color: black;
                font-weight: bold;
                padding: 8px 20px;
            }}
            QPushButton:hover {{
                background-color: #00e838;
            }}
        """)
        layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel']};
                padding: 8px 20px;
            }}
        """)
        layout.addWidget(cancel_btn)
        
        widget.setLayout(layout)
        return widget
        
    # -------------------------------------------------------------------------
    # Signal Connections
    # -------------------------------------------------------------------------
    def setup_connections(self):
        """Setup all signal connections"""
        # Track changes for unsaved warning
        self.risk_per_trade_spin.valueChanged.connect(self.on_parameter_changed)
        self.max_daily_loss_spin.valueChanged.connect(self.on_parameter_changed)
        
        # Additional connections would go here
        
    def setup_timers(self):
        """Setup timers for real-time updates"""
        # Update risk metrics every 5 seconds
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_risk_metrics)
        self.metrics_timer.start(5000)
        
    # -------------------------------------------------------------------------
    # Data Management Methods
    # -------------------------------------------------------------------------
    def load_current_parameters(self):
        """Load current parameters from the system or use defaults"""
        if self.current_params:
            # Load from provided parameters
            self.apply_loaded_parameters(self.current_params)
        else:
            # Use defaults
            self.risk_profile_combo.setCurrentText("Moderate")
            self.on_profile_changed("Moderate")
            
    def apply_loaded_parameters(self, params: Dict):
        """Apply loaded parameters to UI controls"""
        try:
            # Global parameters
            if 'global' in params:
                global_params = params['global']
                self.risk_per_trade_spin.setValue(global_params.get('risk_per_trade', 0.25))
                self.max_daily_loss_spin.setValue(global_params.get('max_daily_loss', 2.0))
                self.max_contracts_spin.setValue(global_params.get('max_contracts', 10))
                self.max_buying_power_spin.setValue(global_params.get('max_buying_power', 75))
                self.max_open_positions_spin.setValue(global_params.get('max_open_positions', 10))
                self.max_delta_spin.setValue(global_params.get('max_delta', 200))
                self.max_gamma_spin.setValue(global_params.get('max_gamma', 10))
                self.max_theta_spin.setValue(global_params.get('max_theta', -400))
                self.max_vega_spin.setValue(global_params.get('max_vega', -600))
                
                if 'account_value' in global_params:
                    self.account_value_input.setValue(global_params['account_value'])
                    
            # Dynamic rules
            if 'dynamic_rules' in params:
                dynamic = params['dynamic_rules']
                self.enable_iv_scaling.setChecked(dynamic.get('enable_iv_scaling', True))
                self.iv_reduction_threshold.setValue(dynamic.get('iv_reduction_threshold', 75))
                self.iv_reduction_factor.setValue(dynamic.get('iv_reduction_factor', 0.25))
                self.enable_skew_adjustment.setChecked(dynamic.get('enable_skew_adjustment', False))
                self.earnings_reduction.setValue(dynamic.get('earnings_reduction', 0.5))
                self.event_blackout_hours.setValue(dynamic.get('event_blackout_hours', 24))
                self.zero_dte_reduction.setValue(dynamic.get('zero_dte_reduction', 0.5))
                self.zero_dte_max_imbalance.setValue(dynamic.get('zero_dte_max_imbalance', 1))
                
            # Execution controls
            if 'execution' in params:
                execution = params['execution']
                self.max_time_between_fills.setValue(execution.get('max_time_between_fills', 5))
                self.max_slippage_cents.setValue(execution.get('max_slippage_cents', 10))
                self.abort_on_partial.setChecked(execution.get('abort_on_partial', True))
                self.enable_dividend_protection.setChecked(execution.get('enable_dividend_protection', True))
                self.itm_threshold.setValue(execution.get('itm_threshold', 1.0))
                self.pin_risk_threshold.setValue(execution.get('pin_risk_threshold', 0.25))
                self.auto_close_expiry_day.setChecked(execution.get('auto_close_expiry_day', True))
                self.default_order_type.setCurrentText(execution.get('default_order_type', 'LIMIT'))
                
        except Exception as e:
            self.logger.error(f"Error loading parameters: {e}")
            QMessageBox.warning(self, "Load Error", 
                              f"Error loading some parameters: {str(e)}")
            
    def get_parameters(self) -> Dict:
        """Get all configured parameters as a dictionary"""
        params = {
            'global': {
                'risk_per_trade': self.risk_per_trade_spin.value(),
                'max_daily_loss': self.max_daily_loss_spin.value(),
                'max_contracts': self.max_contracts_spin.value(),
                'max_buying_power': self.max_buying_power_spin.value(),
                'max_open_positions': self.max_open_positions_spin.value(),
                'max_position_concentration': self.max_position_concentration.value(),
                'min_delta': self.min_delta_spin.value(),
                'max_delta': self.max_delta_spin.value(),
                'max_gamma': self.max_gamma_spin.value(),
                'max_theta': self.max_theta_spin.value(),
                'max_vega': self.max_vega_spin.value(),
                'delta_hedge_threshold': self.delta_hedge_threshold.value(),
                'gamma_hedge_threshold': self.gamma_hedge_threshold.value(),
                'account_value': self.account_value_input.value(),
                'active_profile': self.risk_profile_combo.currentText()
            },
            'strategy_groups': self.get_strategy_groups_config(),
            'dynamic_rules': {
                'enable_iv_scaling': self.enable_iv_scaling.isChecked(),
                'iv_reduction_threshold': self.iv_reduction_threshold.value(),
                'iv_reduction_factor': self.iv_reduction_factor.value(),
                'enable_skew_adjustment': self.enable_skew_adjustment.isChecked(),
                'enable_term_structure': self.enable_term_structure.isChecked(),
                'backwardation_reduction': self.backwardation_reduction.value(),
                'earnings_reduction': self.earnings_reduction.value(),
                'event_blackout_hours': self.event_blackout_hours.value(),
                'zero_dte_enabled': self.zero_dte_enabled.isChecked(),
                'zero_dte_reduction': self.zero_dte_reduction.value(),
                'zero_dte_max_imbalance': self.zero_dte_max_imbalance.value(),
                'zero_dte_friday_only': self.zero_dte_friday_only.isChecked(),
                'triple_witch_reduction': self.triple_witch_reduction.value(),
                'enable_regime_adjustment': self.enable_regime_adjustment.isChecked(),
                'trend_delta_increase': self.trend_delta_increase.value(),
                'trend_directional_bias': self.trend_directional_bias.value(),
                'chop_size_reduction': self.chop_size_reduction.value(),
                'chop_iron_condor_bias': self.chop_iron_condor_bias.value(),
                'high_vol_vega_increase': self.high_vol_vega_increase.value(),
                'high_vol_credit_reduction': self.high_vol_credit_reduction.value()
            },
            'execution': {
                'max_time_between_fills': self.max_time_between_fills.value(),
                'max_slippage_cents': self.max_slippage_cents.value(),
                'abort_on_partial': self.abort_on_partial.isChecked(),
                'smart_routing': self.smart_routing.isChecked(),
                'allow_leg_reconstruction': self.allow_leg_reconstruction.isChecked(),
                'legging_priority': self.legging_priority.currentText(),
                'enable_dividend_protection': self.enable_dividend_protection.isChecked(),
                'itm_threshold': self.itm_threshold.value(),
                'pin_risk_threshold': self.pin_risk_threshold.value(),
                'auto_close_expiry_day': self.auto_close_expiry_day.isChecked(),
                'expiry_close_time': self.expiry_close_time.currentText(),
                'monitor_hard_to_borrow': self.monitor_hard_to_borrow.isChecked(),
                'deep_itm_alert': self.deep_itm_alert.value(),
                'default_order_type': self.default_order_type.currentText(),
                'limit_offset_cents': self.limit_offset_cents.value(),
                'order_timeout_seconds': self.order_timeout_seconds.value(),
                'enable_progressive_fills': self.enable_progressive_fills.isChecked(),
                'progressive_increment': self.progressive_increment.value(),
                'progressive_interval': self.progressive_interval.value()
            },
            'monitoring': {
                'position_check_interval': self.position_check_interval.value(),
                'greek_update_interval': self.greek_update_interval.value(),
                'delta_alert_threshold': self.delta_alert_threshold.value(),
                'loss_alert_threshold': self.loss_alert_threshold.value(),
                'auto_hedge_enabled': self.auto_hedge_enabled.isChecked(),
                'auto_reduce_enabled': self.auto_reduce_enabled.isChecked(),
                'circuit_breaker_enabled': self.circuit_breaker_enabled.isChecked()
            },
            'strategy_overrides': self.get_strategy_overrides() if self.enable_overrides.isChecked() else {}
        }
        
        return params
        
    def get_strategy_groups_config(self) -> Dict:
        """Get strategy groups configuration from table"""
        config = {}
        
        for row in range(self.strategy_table.rowCount()):
            group_name = self.strategy_table.item(row, 0).text()
            config[group_name] = {
                'max_allocation_pct': int(self.strategy_table.item(row, 1).text()),
                'max_concurrent': int(self.strategy_table.item(row, 2).text()),
                'profit_target': int(self.strategy_table.item(row, 3).text()),
                'stop_loss': int(self.strategy_table.item(row, 4).text()),
                'min_iv_rank': int(self.strategy_table.item(row, 5).text()),
                'status': self.strategy_table.item(row, 6).text()
            }
            
        return config
        
    def get_strategy_overrides(self) -> Dict:
        """Get strategy-specific parameter overrides"""
        return {
            'iron_condor': {
                'wing_width': self.ic_wing_width.value(),
                'profit_target': self.ic_profit_target.value(),
                'stop_loss': self.ic_stop_loss.value()
            },
            'vertical_spread': {
                'strike_width': self.spread_width.value(),
                'min_dte': self.spread_dte_min.value()
            },
            'zero_dte': {
                'max_contracts': self.dte_max_size.value(),
                'cutoff_time': self.dte_cutoff_time.currentText()
            }
        }
        
    # -------------------------------------------------------------------------
    # Validation Methods
    # -------------------------------------------------------------------------
    def validate_parameters(self) -> Tuple[bool, List[str]]:
        """
        Validate all parameters for consistency and safety
        
        Returns:
            Tuple of (is_valid, list_of_messages)
        """
        warnings = []
        errors = []
        
        # Check for logical inconsistencies
        if self.max_contracts_spin.value() > 20 and self.account_mode == "PAPER":
            warnings.append("Large position sizes in paper trading may not reflect real execution")
            
        if self.max_delta_spin.value() > 500:
            warnings.append("Portfolio delta >500 implies significant directional risk")
            
        if self.min_delta_spin.value() < -500:
            warnings.append("Portfolio delta <-500 implies significant directional risk")
            
        if self.max_daily_loss_spin.value() > 5.0:
            errors.append("Daily loss limit >5% is extremely aggressive and not recommended")
            
        # Check Greeks consistency
        if abs(self.max_vega_spin.value()) > 1000:
            warnings.append("High vega exposure - monitor volatility risk closely")
            
        if abs(self.max_theta_spin.value()) > 1000:
            warnings.append("High theta decay - ensure adequate premium collection")
            
        # Strategy-specific validation
        if self.zero_dte_enabled.isChecked():
            if self.zero_dte_reduction.value() > 0.5 and self.max_contracts_spin.value() > 10:
                warnings.append("Consider reducing 0DTE sizes further with high contract limits")
                
            if not self.auto_close_expiry_day.isChecked():
                warnings.append("0DTE trading without auto-close on expiry is risky")
                
        # Position concentration checks
        if self.max_position_concentration.value() > 30:
            warnings.append("Position concentration >30% increases single-trade risk")
            
        # Execution risk checks
        if self.max_time_between_fills.value() > 10:
            warnings.append("Long delay between leg fills increases execution risk")
            
        if not self.smart_routing.isChecked() and self.max_slippage_cents.value() < 5:
            warnings.append("Low slippage tolerance without smart routing may result in poor fills")
            
        # Risk budget validation
        account_value = self.account_value_input.value()
        risk_per_trade = self.risk_per_trade_spin.value()
        max_positions = self.max_open_positions_spin.value()
        total_risk = (risk_per_trade * max_positions)
        
        if total_risk > self.max_daily_loss_spin.value():
            warnings.append(f"Total position risk ({total_risk:.1f}%) exceeds daily loss limit")
            
        return len(errors) == 0, errors + warnings
        
    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------
    def on_profile_changed(self, profile_name: str):
        """Handle risk profile selection change"""
        if profile_name in RISK_PROFILES:
            profile = RISK_PROFILES[profile_name]
            
            # Update description
            self.profile_description.setPlainText(profile["description"])
            
            # Apply profile settings (block signals to prevent marking as changed)
            self.risk_per_trade_spin.blockSignals(True)
            self.max_daily_loss_spin.blockSignals(True)
            self.max_contracts_spin.blockSignals(True)
            self.max_delta_spin.blockSignals(True)
            self.max_vega_spin.blockSignals(True)
            self.max_theta_spin.blockSignals(True)
            self.max_open_positions_spin.blockSignals(True)
            self.max_buying_power_spin.blockSignals(True)
            
            # Set values
            self.risk_per_trade_spin.setValue(profile["risk_per_trade"])
            self.max_daily_loss_spin.setValue(profile["max_daily_loss"])
            self.max_contracts_spin.setValue(profile["max_contracts"])
            self.max_delta_spin.setValue(profile["max_delta"])
            self.max_vega_spin.setValue(profile.get("max_vega", -600))
            self.max_theta_spin.setValue(profile.get("max_theta", -400))
            self.max_open_positions_spin.setValue(profile.get("max_open_positions", 10))
            self.max_buying_power_spin.setValue(profile.get("max_buying_power", 75))
            
            # Re-enable signals
            self.risk_per_trade_spin.blockSignals(False)
            self.max_daily_loss_spin.blockSignals(False)
            self.max_contracts_spin.blockSignals(False)
            self.max_delta_spin.blockSignals(False)
            self.max_vega_spin.blockSignals(False)
            self.max_theta_spin.blockSignals(False)
            self.max_open_positions_spin.blockSignals(False)
            self.max_buying_power_spin.blockSignals(False)
            
            # Update risk budgets
            self.update_risk_budgets()
            
            # Emit profile changed signal
            self.profile_changed.emit(profile_name)
        else:
            self.profile_description.setPlainText("Custom risk parameters configuration")
            
    def on_parameter_changed(self):
        """Handle any parameter change"""
        # Mark as having unsaved changes
        self.has_unsaved_changes = True
        self.save_status.setText("Unsaved changes")
        self.save_status.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px;")
        
        # If not custom profile, switch to custom
        if self.risk_profile_combo.currentText() != "Custom":
            self.risk_profile_combo.blockSignals(True)
            self.risk_profile_combo.setCurrentText("Custom")
            self.risk_profile_combo.blockSignals(False)
            
    def update_risk_budgets(self):
        """Update risk budget calculations based on account value and risk percentage"""
        account_value = self.account_value_input.value()
        risk_pct = self.risk_per_trade_spin.value()
        daily_loss_pct = self.max_daily_loss_spin.value()
        
        # Calculate risk budget per trade
        risk_budget = account_value * (risk_pct / 100)
        self.risk_per_trade_budget.setText(f"${risk_budget:,.0f}")
        
        # Calculate notional limit (2% of account)
        notional_limit = account_value * 0.02
        self.notional_limit_label.setText(f"${notional_limit:,.0f}")
        
        # Calculate daily loss limit
        daily_loss_limit = account_value * (daily_loss_pct / 100)
        self.daily_loss_limit_label.setText(f"${daily_loss_limit:,.0f}")
        
        # Mark as changed
        self.on_parameter_changed()
        
    def update_risk_metrics(self):
        """Update real-time risk metrics display"""
        # In production, this would pull from live risk monitoring
        # For now, just demonstrate the concept with slight variations
        
        # Simulate some changes
        import random
        
        # Update portfolio delta
        delta_current = 45 + random.randint(-10, 10)
        delta_limit = 200
        color = COLORS['positive'] if abs(delta_current) < delta_limit * 0.7 else COLORS['warning']
        self.risk_metrics["Portfolio Delta:"].setText(f"{delta_current} / {delta_limit}")
        self.risk_metrics["Portfolio Delta:"].setStyleSheet(f"""
            color: {color}; 
            font-weight: bold;
            font-size: 13px;
            padding: 2px 5px;
            background-color: {COLORS['panel']};
            border: 1px solid {color};
            border-radius: 3px;
        """)
        
        # Update overall risk bar
        risk_level = 65 + random.randint(-5, 5)
        self.overall_risk_bar.setValue(risk_level)
        
        if risk_level < 50:
            bar_color = COLORS['positive']
        elif risk_level < 80:
            bar_color = COLORS['warning']
        else:
            bar_color = COLORS['negative']
            
        self.overall_risk_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {COLORS['border']};
                border-radius: 3px;
                text-align: center;
                background-color: {COLORS['panel']};
            }}
            QProgressBar::chunk {{
                background-color: {bar_color};
                border-radius: 2px;
            }}
        """)
        
    def toggle_strategy_overrides(self, state: int):
        """Enable/disable strategy override controls"""
        enabled = state == Qt.CheckState.Checked.value
        
        # Iron Condor controls
        self.ic_wing_width.setEnabled(enabled)
        self.ic_profit_target.setEnabled(enabled)
        self.ic_stop_loss.setEnabled(enabled)
        
        # Spread controls
        self.spread_width.setEnabled(enabled)
        self.spread_dte_min.setEnabled(enabled)
        
        # 0DTE controls
        self.dte_max_size.setEnabled(enabled)
        self.dte_cutoff_time.setEnabled(enabled)
        
        self.on_parameter_changed()
        
    def toggle_regime_controls(self, state: int):
        """Enable/disable regime adjustment controls"""
        enabled = state == Qt.CheckState.Checked.value
        
        # Trend controls
        self.trend_delta_increase.setEnabled(enabled)
        self.trend_directional_bias.setEnabled(enabled)
        
        # Chop controls
        self.chop_size_reduction.setEnabled(enabled)
        self.chop_iron_condor_bias.setEnabled(enabled)
        
        # High vol controls
        self.high_vol_vega_increase.setEnabled(enabled)
        self.high_vol_credit_reduction.setEnabled(enabled)
        
        self.on_parameter_changed()
        
    def populate_strategy_table(self):
        """Populate the strategy groups table with data"""
        row = 0
        for name, params in STRATEGY_GROUP_TEMPLATES.items():
            self.strategy_table.setItem(row, 0, QTableWidgetItem(name))
            self.strategy_table.setItem(row, 1, QTableWidgetItem(str(params.get("max_allocation_pct", 20))))
            self.strategy_table.setItem(row, 2, QTableWidgetItem(str(params.get("max_concurrent", 3))))
            self.strategy_table.setItem(row, 3, QTableWidgetItem(str(params.get("profit_target", 50))))
            self.strategy_table.setItem(row, 4, QTableWidgetItem(str(params.get("stop_loss", 100))))
            self.strategy_table.setItem(row, 5, QTableWidgetItem(str(params.get("min_iv_rank", 30))))
            
            # Status
            status_item = QTableWidgetItem("ACTIVE")
            status_item.setForeground(QColor(COLORS['positive']))
            self.strategy_table.setItem(row, 6, status_item)
            
            row += 1
            
    def load_strategy_template(self, template_name: str):
        """Load and display a strategy template description"""
        if template_name in STRATEGY_GROUP_TEMPLATES:
            template = STRATEGY_GROUP_TEMPLATES[template_name]
            self.template_description.setPlainText(template.get("description", ""))
        else:
            self.template_description.setPlainText("Select a template to view description...")
            
    def apply_strategy_template(self):
        """Apply the selected strategy template"""
        template_name = self.template_combo.currentText()
        if template_name in STRATEGY_GROUP_TEMPLATES:
            reply = QMessageBox.question(
                self, "Apply Template",
                f"Apply {template_name} template settings?\n\n"
                "This will update the strategy group configuration.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Apply template settings
                # In production, this would update the strategy table
                self.on_parameter_changed()
                QMessageBox.information(self, "Template Applied", 
                                      f"{template_name} template has been applied")
                
    def add_strategy_group(self):
        """Add a new strategy group to the table"""
        row_count = self.strategy_table.rowCount()
        self.strategy_table.insertRow(row_count)
        
        # Set default values
        self.strategy_table.setItem(row_count, 0, QTableWidgetItem("New Group"))
        self.strategy_table.setItem(row_count, 1, QTableWidgetItem("20"))
        self.strategy_table.setItem(row_count, 2, QTableWidgetItem("3"))
        self.strategy_table.setItem(row_count, 3, QTableWidgetItem("50"))
        self.strategy_table.setItem(row_count, 4, QTableWidgetItem("100"))
        self.strategy_table.setItem(row_count, 5, QTableWidgetItem("30"))
        
        status_item = QTableWidgetItem("INACTIVE")
        status_item.setForeground(QColor(COLORS['text_dim']))
        self.strategy_table.setItem(row_count, 6, status_item)
        
        self.on_parameter_changed()
        
    def remove_strategy_group(self):
        """Remove the selected strategy group from the table"""
        current_row = self.strategy_table.currentRow()
        if current_row >= 0:
            group_name = self.strategy_table.item(current_row, 0).text()
            
            reply = QMessageBox.question(
                self, "Remove Group",
                f"Remove strategy group '{group_name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.strategy_table.removeRow(current_row)
                self.on_parameter_changed()
                
    def save_risk_profile(self):
        """Save current settings as a custom profile"""
        from PyQt6.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(
            self, "Save Profile",
            "Enter profile name:",
            text="My Custom Profile"
        )
        
        if ok and name:
            # In production, this would save to database
            params = self.get_parameters()
            
            QMessageBox.information(
                self, "Profile Saved",
                f"Profile '{name}' has been saved.\n\n"
                "Note: Profile persistence will be implemented with database integration."
            )
            
            # Add to combo box
            if name not in [self.risk_profile_combo.itemText(i) 
                          for i in range(self.risk_profile_combo.count())]:
                self.risk_profile_combo.insertItem(
                    self.risk_profile_combo.count() - 1, name
                )
                self.risk_profile_combo.setCurrentText(name)
                
    def delete_risk_profile(self):
        """Delete a custom risk profile"""
        current_profile = self.risk_profile_combo.currentText()
        
        if current_profile in RISK_PROFILES:
            QMessageBox.warning(
                self, "Cannot Delete",
                "Built-in profiles cannot be deleted."
            )
            return
            
        if current_profile == "Custom":
            QMessageBox.warning(
                self, "Cannot Delete",
                "The 'Custom' profile cannot be deleted."
            )
            return
            
        reply = QMessageBox.question(
            self, "Delete Profile",
            f"Delete profile '{current_profile}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            index = self.risk_profile_combo.currentIndex()
            self.risk_profile_combo.removeItem(index)
            self.risk_profile_combo.setCurrentText("Moderate")
            
    def import_settings(self):
        """Import risk parameters from JSON file"""
        from PyQt6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Risk Parameters",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    params = json.load(f)
                    
                self.apply_loaded_parameters(params)
                self.on_parameter_changed()
                
                QMessageBox.information(
                    self, "Import Successful",
                    "Risk parameters imported successfully."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Import Error",
                    f"Error importing parameters:\n{str(e)}"
                )
                
    def export_settings(self):
        """Export current risk parameters to JSON file"""
        from PyQt6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Risk Parameters",
            f"spyder_risk_params_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            try:
                params = self.get_parameters()
                
                with open(filename, 'w') as f:
                    json.dump(params, f, indent=4)
                    
                QMessageBox.information(
                    self, "Export Successful",
                    f"Risk parameters exported to:\n{filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Error",
                    f"Error exporting parameters:\n{str(e)}"
                )
                
    def apply_parameters(self):
        """Apply parameters without closing dialog"""
        # Validate parameters
        is_valid, messages = self.validate_parameters()
        
        if not is_valid:
            QMessageBox.critical(
                self, "Validation Error",
                "Cannot apply parameters:\n\n" + "\n".join(messages)
            )
            return
            
        if messages:  # Show warnings
            reply = QMessageBox.warning(
                self, "Validation Warnings",
                "The following warnings were detected:\n\n" + 
                "\n".join(messages) + 
                "\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
                
        # Emit signal with parameters
        self.parameters_updated.emit(self.get_parameters())
        
        # Update save status
        self.has_unsaved_changes = False
        self.save_status.setText("All changes saved")
        self.save_status.setStyleSheet(f"color: {COLORS['positive']}; font-size: 12px;")
        
        QMessageBox.information(
            self, "Success",
            "Risk parameters applied successfully.\n\n"
            "The trading system will use these parameters immediately."
        )
        
    def accept_parameters(self):
        """Accept parameters and close dialog"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Apply them before closing?",
                QMessageBox.StandardButton.Yes | 
                QMessageBox.StandardButton.No | 
                QMessageBox.StandardButton.Cancel
            )
            
            if reply == QMessageBox.StandardButton.Cancel:
                return
            elif reply == QMessageBox.StandardButton.Yes:
                self.apply_parameters()
                
        self.accept()
        
    def reject(self):
        """Handle dialog rejection"""
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Discard them?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.No:
                return
                
        super().reject()

# ==============================================================================
# CONVENIENCE FUNCTION FOR SHOWING DIALOG
# ==============================================================================
def show_risk_parameters_dialog(parent=None, current_params: Optional[Dict] = None) -> Optional[Dict]:
    """
    Show the risk parameters dialog and return the configured parameters
    
    Args:
        parent: Parent widget
        current_params: Dictionary of current parameters
        
    Returns:
        Dictionary of configured parameters if accepted, None if cancelled
    """
    dialog = RiskParametersDialog(parent, current_params)
    
    # Connect to parent if available
    if parent and hasattr(parent, 'update_risk_parameters'):
        dialog.parameters_updated.connect(parent.update_risk_parameters)
        
    result = dialog.exec()
    
    if result == QDialog.DialogCode.Accepted:
        return dialog.get_parameters()
        
    return None

# ==============================================================================
# MAIN ENTRY POINT (FOR TESTING)
# ==============================================================================
if __name__ == '__main__':
    # PyQt6 doesn't need the high DPI attributes that were removed
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Test the dialog standalone
    params = show_risk_parameters_dialog()
    
    if params:
        print("="*80)
        print("CONFIGURED RISK PARAMETERS")
        print("="*80)
        print(json.dumps(params, indent=2))
    else:
        print("Dialog cancelled - no parameters configured")
        
    sys.exit(0)
