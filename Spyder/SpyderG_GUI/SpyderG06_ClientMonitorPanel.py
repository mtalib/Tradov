#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG06_ClientMonitorPanel.py
Group: G (GUI/Dashboard)
Purpose: Bottom panel widget showing System Health and Prometheus Metrics
Author: Mohamed Talib
Date Created: 2025-01-11
Last Updated: 2025-01-22 Time: 16:30:00

Description:
    This module provides the bottom panel widget for the Spyder Trading Dashboard
    displaying System Health indicators and Prometheus Metrics for all 10 IB Gateway
    clients. It creates a properly formatted panel with System Health on the left
    and correctly numbered Prometheus client metrics on the right, with proper
    title display without clipping.

    FIXED: Updated to use 1-10 client range matching SpyderB08_MultiClientDataManager.py.
    Client 1 = Order Execution (HIGHEST PRIORITY), Client 2 = Administrative.
===============================================================================
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QFrame,
    QGroupBox,
    QPushButton,
    QApplication,
    QMainWindow,
    QProgressBar,
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread, QObject
from PySide6.QtGui import QFont, QColor, QPalette

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger

    logger = SpyderLogger.get_logger(__name__)
except ImportError:
    import logging

    logger = logging.getLogger(__name__)
    logger.warning("SpyderLogger not available, using standard logging")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Dashboard Theme Colors
COLOR_BACKGROUND = "#0a0a0a"
COLOR_PANEL_BG = "#1a1a2e"
COLOR_TEXT = "#ffffff"
COLOR_TEXT_DIM = "#8a8a8a"
COLOR_GREEN = "#00ff00"
COLOR_YELLOW = "#ffaa00"
COLOR_RED = "#ff0000"
COLOR_BLUE = "#4a90e2"
COLOR_BORDER = "#2a2a3a"
COLOR_HEADER_BG = "#0a0a0a"
COLOR_SECTION_BG = "#0a0a1a"

# Font Settings
FONT_FAMILY = "Segoe UI"
FONT_SIZE_TITLE = 14
FONT_SIZE_HEADER = 12
FONT_SIZE_NORMAL = 11
FONT_SIZE_SMALL = 10

# Update Intervals
UPDATE_INTERVAL = 5000  # 5 seconds

# FIXED: Client Definitions matching SpyderB08 (1-10 range with correct allocation)
CLIENT_DEFINITIONS = [
    (1, "Orders"),        # FIXED: Order Execution (HIGHEST PRIORITY)
    (2, "Admin"),         # FIXED: Administrative
    (3, "Core"),          # Core Data
    (4, "Options"),       # SPY Options
    (5, "Volatility"),    # Volatility Indicators
    (6, "Internals"),     # Market Internals
    (7, "Major ETFs"),    # Major Indices
    (8, "Extended Assets"), # Extended Assets
    (9, "Sector ETFs"),   # Sector ETFs
    (10, "International") # FIXED: Added International Markets
]


# ==============================================================================
# CLIENT MONITOR PANEL CLASS
# ==============================================================================
class ClientMonitorPanel(QWidget):
    """
    Bottom panel widget for Spyder Dashboard showing System Health and Prometheus Metrics.

    This widget creates a properly formatted bottom panel with:
    - Left column: System Health indicators
    - Right section: Prometheus Metrics with correct CLIENT 1-10 numbering
    - Fixed title display without clipping

    FIXED: Updated for 1-10 client range with correct allocation.
    """

    # Signals
    health_status_changed = Signal(str, bool)  # component_name, is_healthy
    client_status_changed = Signal(int, bool)  # client_id, is_connected

    def __init__(self, parent=None):
        """
        Initialize the Client Monitor Panel.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)

        # Initialize component states
        self.system_health = {
            "RISK MANAGER": True,
            "MARKET DATA": True,
            "STRATEGY ENGINE": True,
            "ML MODELS": True,
            "DATABASE": True,
        }

        # FIXED: Initialize client status for 1-10 range
        self.client_status = {
            i: True for i in range(1, 11)  # FIXED: 1-10 range instead of 0-8
        }  # All clients active by default
        
        # FIXED: Updated metrics data for 10 clients
        self.metrics_data = {
            "active_clients": 10,  # FIXED: 10 instead of 9
            "total_clients": 10,   # FIXED: 10 instead of 9
            "memory_usage": 45,
            "cpu_usage": 22,
            "api_calls_per_sec": 127,
        }

        # Setup UI
        self.setup_ui()

        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_metrics)
        self.update_timer.start(UPDATE_INTERVAL)

        logger.info("ClientMonitorPanel initialized successfully (FIXED: 1-10 clients)")

    # ==========================================================================
    # UI SETUP METHODS
    # ==========================================================================
    def setup_ui(self):
        """Setup the complete UI layout."""
        # Main layout with proper margins to prevent clipping
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)  # No spacing for table-like appearance

        # Set widget background
        self.setStyleSheet(
            f"""
            ClientMonitorPanel {{
                background-color: {COLOR_BACKGROUND};
            }}
        """
        )

        # Title Section - Fixed height to prevent clipping
        title_widget = self.create_title_section()
        main_layout.addWidget(title_widget)

        # Main Table Widget - Grid layout for table-like appearance
        table_widget = self.create_table_layout()
        main_layout.addWidget(table_widget)

    def create_title_section(self) -> QWidget:
        """
        Create the title section with proper height to prevent clipping.

        Returns:
            QWidget: Title section widget
        """
        title_widget = QWidget()
        title_widget.setFixedHeight(35)  # Fixed height to prevent clipping

        title_layout = QHBoxLayout(title_widget)
        title_layout.setContentsMargins(5, 5, 5, 5)

        # Title label
        title_label = QLabel("PROMETHEUS METRICS MONITOR (CLIENTS 1-10)")  # FIXED: Updated title
        title_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLOR_BLUE};
                font-size: {FONT_SIZE_TITLE}px;
                font-weight: bold;
                font-family: {FONT_FAMILY};
            }}
        """
        )

        title_layout.addWidget(title_label)
        title_layout.addStretch()

        return title_widget

    def create_table_layout(self) -> QWidget:
        """
        Create a table-like layout matching the design specification.

        Returns:
            QWidget: Table widget with grid layout
        """
        table_widget = QWidget()
        table_widget.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND};
                border: 1px solid {COLOR_BORDER};
            }}
        """
        )

        # Create grid layout for table structure
        grid_layout = QGridLayout(table_widget)
        grid_layout.setSpacing(0)  # No spacing between cells
        grid_layout.setContentsMargins(0, 0, 0, 0)

        # ==== HEADER ROW ====
        # System Health Header (Column 0)
        health_header = self.create_header_cell("SYSTEM HEALTH")
        grid_layout.addWidget(health_header, 0, 0, 1, 1)

        # Prometheus Metrics Header (Columns 1-2)
        prometheus_header = self.create_header_cell("PROMETHEUS METRICS (1-10)")  # FIXED: Updated header
        grid_layout.addWidget(prometheus_header, 0, 1, 1, 2)

        # ==== DATA ROWS ====
        # System Health Items (Column 0, Rows 1-5)
        health_items = [
            "RISK MANAGER",
            "MARKET DATA",
            "STRATEGY ENGINE",
            "ML MODELS",
            "DATABASE",
        ]
        self.health_cells = {}

        for i, item in enumerate(health_items):
            cell = self.create_health_cell(item)
            self.health_cells[item] = cell
            grid_layout.addWidget(cell, i + 1, 0)

        # FIXED: Prometheus Client Items (Columns 1-2, Rows 1-5) for 1-10 range
        self.client_cells = {}
        
        # FIXED: Updated client arrangement for 1-10 range
        clients_left = [
            (1, "Orders"),        # Client 1: Order Execution (HIGHEST PRIORITY)
            (2, "Admin"),         # Client 2: Administrative
            (3, "Core"),          # Client 3: Core Data
            (4, "Options"),       # Client 4: SPY Options
            (5, "Volatility"),    # Client 5: Volatility Indicators
        ]
        clients_right = [
            (6, "Internals"),     # Client 6: Market Internals
            (7, "Major ETFs"),    # Client 7: Major Indices
            (8, "Extended Assets"), # Client 8: Extended Assets
            (9, "Sector ETFs"),   # Client 9: Sector ETFs
            (10, "International") # Client 10: International Markets
        ]

        # Left column of clients
        for i, (client_num, client_name) in enumerate(clients_left):
            cell = self.create_client_cell(client_num, client_name)
            self.client_cells[client_num] = cell
            grid_layout.addWidget(cell, i + 1, 1)

        # Right column of clients
        for i, (client_num, client_name) in enumerate(clients_right):
            cell = self.create_client_cell(client_num, client_name)
            self.client_cells[client_num] = cell
            grid_layout.addWidget(cell, i + 1, 2)

        # ==== BOTTOM ROW - METRICS SUMMARY ====
        # System Health Score (Column 0)
        self.health_score_cell = self.create_score_cell()
        grid_layout.addWidget(self.health_score_cell, 6, 0)

        # Metrics Summary (Columns 1-2)
        self.metrics_summary_cell = self.create_metrics_summary_cell()
        grid_layout.addWidget(self.metrics_summary_cell, 6, 1, 1, 2)

        # Set column stretch to get proper proportions (1:1:1)
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setColumnStretch(2, 1)

        return table_widget

    # ==========================================================================
    # TABLE CELL CREATION METHODS
    # ==========================================================================
    def create_header_cell(self, text: str) -> QWidget:
        """
        Create a header cell for the table.

        Args:
            text: Header text

        Returns:
            QWidget: Header cell widget
        """
        cell = QWidget()
        cell.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_PANEL_BG};
                border: 1px solid {COLOR_BORDER};
                min-height: 30px;
            }}
        """
        )

        layout = QHBoxLayout(cell)
        layout.setContentsMargins(10, 5, 10, 5)

        label = QLabel(text)
        label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: {FONT_SIZE_HEADER}px;
                font-weight: bold;
                font-family: {FONT_FAMILY};
            }}
        """
        )
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        return cell

    def create_health_cell(self, component: str) -> QWidget:
        """
        Create a health status cell.

        Args:
            component: Component name

        Returns:
            QWidget: Health status cell
        """
        cell = QWidget()
        cell.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND};
                border: 1px solid {COLOR_BORDER};
                min-height: 25px;
            }}
        """
        )

        layout = QHBoxLayout(cell)
        layout.setContentsMargins(10, 3, 10, 3)

        # Status indicator
        indicator = QLabel("●")
        indicator.setObjectName(f"health_{component.replace(' ', '_')}")
        color = COLOR_GREEN if self.system_health.get(component, True) else COLOR_RED
        indicator.setStyleSheet(f"color: {color}; font-size: 12px;")
        layout.addWidget(indicator)

        # Component name
        label = QLabel(f"  {component}")
        label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: {FONT_SIZE_NORMAL}px;
                font-family: {FONT_FAMILY};
            }}
        """
        )
        layout.addWidget(label)
        layout.addStretch()

        return cell

    def create_client_cell(self, client_num: int, client_name: str) -> QWidget:
        """
        Create a client status cell.

        Args:
            client_num: Client number (1-10)  # FIXED: Updated range
            client_name: Client name

        Returns:
            QWidget: Client status cell
        """
        cell = QWidget()
        cell.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND};
                border: 1px solid {COLOR_BORDER};
                min-height: 25px;
            }}
        """
        )

        layout = QHBoxLayout(cell)
        layout.setContentsMargins(10, 3, 10, 3)

        # Status indicator
        indicator = QLabel("●")
        indicator.setObjectName(f"client_{client_num}")
        color = COLOR_GREEN if self.client_status.get(client_num, True) else COLOR_RED
        indicator.setStyleSheet(f"color: {color}; font-size: 10px;")
        layout.addWidget(indicator)

        # Client label - FIXED: Show priority for Client 1
        if client_num == 1:
            display_text = f"  CLIENT {client_num}: {client_name} (PRIORITY)"
        else:
            display_text = f"  CLIENT {client_num}: {client_name}"
            
        label = QLabel(display_text)
        label.setObjectName(f"client_label_{client_num}")
        label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLOR_TEXT};
                font-size: {FONT_SIZE_SMALL}px;
                font-family: {FONT_FAMILY};
            }}
        """
        )
        layout.addWidget(label)
        layout.addStretch()

        return cell

    def create_empty_cell(self) -> QWidget:
        """
        Create an empty cell for the table.

        Returns:
            QWidget: Empty cell
        """
        cell = QWidget()
        cell.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND};
                border: 1px solid {COLOR_BORDER};
                min-height: 25px;
            }}
        """
        )
        return cell

    def create_score_cell(self) -> QWidget:
        """
        Create the system health score cell.

        Returns:
            QWidget: Health score cell
        """
        cell = QWidget()
        cell.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND};
                border: 1px solid {COLOR_BORDER};
                min-height: 30px;
            }}
        """
        )

        layout = QHBoxLayout(cell)
        layout.setContentsMargins(10, 5, 10, 5)

        label = QLabel("System Health: ")
        label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLOR_TEXT_DIM};
                font-size: {FONT_SIZE_NORMAL}px;
                font-family: {FONT_FAMILY};
            }}
        """
        )
        layout.addWidget(label)

        self.health_score_label = QLabel("92/100")
        self.health_score_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLOR_GREEN};
                font-size: {FONT_SIZE_NORMAL}px;
                font-weight: bold;
                font-family: {FONT_FAMILY};
            }}
        """
        )
        layout.addWidget(self.health_score_label)
        layout.addStretch()

        return cell

    def create_metrics_summary_cell(self) -> QWidget:
        """
        Create the metrics summary cell.

        Returns:
            QWidget: Metrics summary cell
        """
        cell = QWidget()
        cell.setStyleSheet(
            f"""
            QWidget {{
                background-color: {COLOR_BACKGROUND};
                border: 1px solid {COLOR_BORDER};
                min-height: 30px;
            }}
        """
        )

        layout = QHBoxLayout(cell)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)

        # Store references to value labels for updates
        self.metrics_value_labels = {}

        # Active Clients - FIXED: Updated for 10 clients
        active_label = QLabel("Active Clients: ")
        active_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;"
        )
        layout.addWidget(active_label)

        active_value = QLabel("10/10")  # FIXED: 10/10 instead of 9/9
        active_value.setStyleSheet(
            f"color: {COLOR_GREEN}; font-size: {FONT_SIZE_SMALL}px; font-weight: bold;"
        )
        self.metrics_value_labels["active"] = active_value
        layout.addWidget(active_value)

        # Separator
        sep1 = QLabel(" | ")
        sep1.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;")
        layout.addWidget(sep1)

        # Memory
        memory_label = QLabel("Memory: ")
        memory_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;"
        )
        layout.addWidget(memory_label)

        memory_value = QLabel("45%")
        memory_value.setStyleSheet(
            f"color: {COLOR_YELLOW}; font-size: {FONT_SIZE_SMALL}px; font-weight: bold;"
        )
        self.metrics_value_labels["memory"] = memory_value
        layout.addWidget(memory_value)

        # Separator
        sep2 = QLabel(" | ")
        sep2.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;")
        layout.addWidget(sep2)

        # CPU
        cpu_label = QLabel("CPU: ")
        cpu_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;"
        )
        layout.addWidget(cpu_label)

        cpu_value = QLabel("22%")
        cpu_value.setStyleSheet(
            f"color: {COLOR_GREEN}; font-size: {FONT_SIZE_SMALL}px; font-weight: bold;"
        )
        self.metrics_value_labels["cpu"] = cpu_value
        layout.addWidget(cpu_value)

        # Separator
        sep3 = QLabel(" | ")
        sep3.setStyleSheet(f"color: {COLOR_TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;")
        layout.addWidget(sep3)

        # API Calls
        api_label = QLabel("API Calls/Sec: ")
        api_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-size: {FONT_SIZE_SMALL}px;"
        )
        layout.addWidget(api_label)

        api_value = QLabel("127")
        api_value.setStyleSheet(
            f"color: {COLOR_GREEN}; font-size: {FONT_SIZE_SMALL}px; font-weight: bold;"
        )
        self.metrics_value_labels["api"] = api_value
        layout.addWidget(api_value)

        layout.addStretch()

        return cell

    # ==========================================================================
    # UPDATE METHODS
    # ==========================================================================
    @Slot()
    def update_metrics(self):
        """Update metrics display (called by timer)."""
        # This would normally get data from SpyderB15_PrometheusMetrics
        # For now, using simulated data
        pass

    def update_system_health(self, component: str, is_healthy: bool):
        """
        Update system health indicator.

        Args:
            component: Component name
            is_healthy: Health status
        """
        if component in self.system_health:
            self.system_health[component] = is_healthy

            # Update UI - find the indicator in the cell
            if component in self.health_cells:
                cell = self.health_cells[component]
                indicator = cell.findChild(
                    QLabel, f"health_{component.replace(' ', '_')}"
                )
                if indicator:
                    color = COLOR_GREEN if is_healthy else COLOR_RED
                    indicator.setStyleSheet(f"color: {color}; font-size: 12px;")

            # Emit signal
            self.health_status_changed.emit(component, is_healthy)

            # Update health score
            self.update_health_score()

    def update_health_score(self):
        """Update the system health score."""
        healthy_count = sum(1 for v in self.system_health.values() if v)
        total_count = len(self.system_health)
        score = int((healthy_count / total_count) * 100)

        if hasattr(self, "health_score_label"):
            self.health_score_label.setText(f"{score}/100")

            # Update color based on score
            if score >= 80:
                color = COLOR_GREEN
            elif score >= 60:
                color = COLOR_YELLOW
            else:
                color = COLOR_RED

            self.health_score_label.setStyleSheet(
                f"""
                QLabel {{
                    color: {color};
                    font-size: {FONT_SIZE_NORMAL}px;
                    font-weight: bold;
                    font-family: {FONT_FAMILY};
                }}
            """
            )

    def update_client_status(self, client_id: int, is_connected: bool):
        """
        Update client connection status.

        Args:
            client_id: Client ID (1-10)  # FIXED: Updated range
            is_connected: Connection status
        """
        if client_id in self.client_cells:
            self.client_status[client_id] = is_connected

            # Update indicator in the cell
            cell = self.client_cells[client_id]
            indicator = cell.findChild(QLabel, f"client_{client_id}")
            if indicator:
                color = COLOR_GREEN if is_connected else COLOR_RED
                indicator.setStyleSheet(f"color: {color}; font-size: 10px;")

            # Update active clients count
            self.update_active_clients_count()

            # Emit signal
            self.client_status_changed.emit(client_id, is_connected)

    def update_active_clients_count(self):
        """Update the active clients count in metrics."""
        active_count = sum(1 for v in self.client_status.values() if v)
        self.metrics_data["active_clients"] = active_count

        # Update display
        if (
            hasattr(self, "metrics_value_labels")
            and "active" in self.metrics_value_labels
        ):
            label = self.metrics_value_labels["active"]
            label.setText(f"{active_count}/{self.metrics_data['total_clients']}")

            # Update color based on active count
            if active_count == self.metrics_data["total_clients"]:
                color = COLOR_GREEN
            elif active_count > 0:
                color = COLOR_YELLOW
            else:
                color = COLOR_RED

            label.setStyleSheet(
                f"""
                QLabel {{
                    color: {color};
                    font-size: {FONT_SIZE_SMALL}px;
                    font-weight: bold;
                    font-family: {FONT_FAMILY};
                }}
            """
            )

    def update_resource_metrics(self, memory_pct: int, cpu_pct: int, api_calls: int):
        """
        Update resource usage metrics.

        Args:
            memory_pct: Memory usage percentage
            cpu_pct: CPU usage percentage
            api_calls: API calls per second
        """
        self.metrics_data["memory_usage"] = memory_pct
        self.metrics_data["cpu_usage"] = cpu_pct
        self.metrics_data["api_calls_per_sec"] = api_calls

        if hasattr(self, "metrics_value_labels"):
            # Update Memory
            if "memory" in self.metrics_value_labels:
                label = self.metrics_value_labels["memory"]
                label.setText(f"{memory_pct}%")
                color = (
                    COLOR_RED
                    if memory_pct > 80
                    else COLOR_YELLOW if memory_pct > 40 else COLOR_GREEN
                )
                label.setStyleSheet(
                    f"""
                    QLabel {{
                        color: {color};
                        font-size: {FONT_SIZE_SMALL}px;
                        font-weight: bold;
                        font-family: {FONT_FAMILY};
                    }}
                """
                )

            # Update CPU
            if "cpu" in self.metrics_value_labels:
                label = self.metrics_value_labels["cpu"]
                label.setText(f"{cpu_pct}%")
                color = (
                    COLOR_RED
                    if cpu_pct > 80
                    else COLOR_YELLOW if cpu_pct > 40 else COLOR_GREEN
                )
                label.setStyleSheet(
                    f"""
                    QLabel {{
                        color: {color};
                        font-size: {FONT_SIZE_SMALL}px;
                        font-weight: bold;
                        font-family: {FONT_FAMILY};
                    }}
                """
                )

            # Update API Calls
            if "api" in self.metrics_value_labels:
                label = self.metrics_value_labels["api"]
                label.setText(str(api_calls))

    # FIXED: Add method to handle all 10 clients validation
    def validate_client_range(self, client_id: int) -> bool:
        """
        Validate that client ID is in valid range (1-10).
        
        Args:
            client_id: Client ID to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        return 1 <= client_id <= 10

    def get_client_purpose(self, client_id: int) -> str:
        """
        Get the purpose/name for a client ID.
        
        Args:
            client_id: Client ID (1-10)
            
        Returns:
            str: Client purpose/name
        """
        client_purposes = {
            1: "Orders",
            2: "Admin", 
            3: "Core",
            4: "Options",
            5: "Volatility",
            6: "Internals",
            7: "Major ETFs",
            8: "Extended Assets",
            9: "Sector ETFs",
            10: "International"
        }
        return client_purposes.get(client_id, "Unknown")


# ==============================================================================
# HELPER FUNCTIONS FOR INTEGRATION
# ==============================================================================
def create_bottom_panel() -> ClientMonitorPanel:
    """
    Factory function to create the bottom panel widget.

    Returns:
        ClientMonitorPanel: Configured bottom panel widget
    """
    return ClientMonitorPanel()


def integrate_with_dashboard(dashboard_window, bottom_panel_widget=None):
    """
    Integrate the ClientMonitorPanel with an existing dashboard.

    Args:
        dashboard_window: The main dashboard window
        bottom_panel_widget: Optional existing panel to replace

    Returns:
        ClientMonitorPanel: The integrated panel widget
    """
    if bottom_panel_widget is None:
        bottom_panel_widget = create_bottom_panel()

    # The dashboard should add this widget to its bottom area
    # This is a helper function - actual integration depends on dashboard structure

    return bottom_panel_widget


# ==============================================================================
# MAIN EXECUTION (FOR TESTING)
# ==============================================================================
def main():
    """Main entry point for standalone testing."""
    app = QApplication(sys.argv)

    # Create test window
    window = QMainWindow()
    window.setWindowTitle("SPYDER - Client Monitor Panel Test (FIXED: 1-10)")
    window.setGeometry(100, 100, 1200, 300)

    # Set dark theme
    window.setStyleSheet(
        f"""
        QMainWindow {{
            background-color: {COLOR_BACKGROUND};
        }}
    """
    )

    # Create and set the monitor panel
    panel = ClientMonitorPanel()
    window.setCentralWidget(panel)

    # Test updates for new range
    QTimer.singleShot(2000, lambda: panel.update_client_status(1, False))  # Orders
    QTimer.singleShot(4000, lambda: panel.update_client_status(10, False)) # International 
    QTimer.singleShot(6000, lambda: panel.update_system_health("ML MODELS", False))
    QTimer.singleShot(8000, lambda: panel.update_resource_metrics(75, 45, 250))

    window.show()

    print("\n" + "="*70)
    print("CLIENT MONITOR PANEL (G06) - FIXED")
    print("="*70)
    print("✅ FIXES APPLIED:")
    print("   • Client range updated: 0-8 → 1-10")
    print("   • Client allocation fixed: Client 1=Orders, Client 2=Admin")
    print("   • Added Client 10 for International Markets")
    print("   • Total clients updated: 9 → 10")
    print("   • CLIENT_DEFINITIONS list completely updated")
    print("   • All update methods handle 1-10 range")
    print("\n📊 CLIENT ALLOCATION (FIXED):")
    for client_id, client_name in CLIENT_DEFINITIONS:
        priority = " (PRIORITY)" if client_id == 1 else ""
        print(f"   Client {client_id:2d}: {client_name}{priority}")
    print("\n🔗 Now fully consistent with SpyderB08 specification")
    print("="*70 + "\n")

    logger.info("Client Monitor Panel test window launched (FIXED version)")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
