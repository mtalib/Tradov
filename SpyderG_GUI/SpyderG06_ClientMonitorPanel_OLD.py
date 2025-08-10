#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG06_ClientMonitorPanel.py
Group: G (GUI/Dashboard)
Purpose: PyQt6 widgets for multi-client monitoring panel
Author: Mohamed Talib
Date Created: 2025-08-03
Last Updated: 2025-08-03 Time: 16:00:00

Description:
    Provides PyQt6 widgets for the bottom-right dashboard panel showing
    System Health and Prometheus Metrics for all 9 IB Gateway clients.
    Integrates with SpyderB16_GatewayIntegration for real-time updates.
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
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QGroupBox, QPushButton,
    QApplication, QMainWindow, QToolTip,
    QMenu, QMessageBox, QFileDialog
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, pyqtSlot,
    QThread, QObject, QPoint, QPropertyAnimation,
    QRect, QEasingCurve
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QAction,
    QMouseEvent, QPainter, QPen, QBrush
)

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB16_GatewayIntegration import (
        GatewayIntegrationManager, DashboardIntegrationHelper
    )
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
except ImportError as e:
    print(f"Warning: Could not import Spyder modules: {e}")
    GatewayIntegrationManager = None
    SpyderLogger = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Colors matching existing dashboard theme
COLOR_BACKGROUND = "#0A0E27"
COLOR_PANEL_BG = "#1A1E37"
COLOR_TEXT = "#FFFFFF"
COLOR_TEXT_DIM = "#808080"
COLOR_GREEN = "#00FF00"
COLOR_YELLOW = "#FFD700"
COLOR_RED = "#FF0000"
COLOR_BLUE = "#4169E1"
COLOR_BORDER = "#2A2E47"

# Font settings
FONT_FAMILY = "Consolas"
FONT_SIZE_TITLE = 11
FONT_SIZE_NORMAL = 10
FONT_SIZE_SMALL = 9

# Update intervals
UPDATE_INTERVAL = 10000  # 10 seconds

# ==============================================================================
# STYLE SHEETS
# ==============================================================================
PANEL_STYLE = """
    QFrame {
        background-color: #1A1E37;
        border: 1px solid #2A2E47;
        border-radius: 4px;
    }
"""

TITLE_STYLE = """
    QLabel {
        color: #FFFFFF;
        font-family: Consolas;
        font-size: 11px;
        font-weight: bold;
        padding: 5px;
        background-color: #0A0E27;
        border-bottom: 1px solid #2A2E47;
    }
"""

STATUS_LABEL_STYLE = """
    QLabel {
        color: #FFFFFF;
        font-family: Consolas;
        font-size: 10px;
        padding: 2px 5px;
    }
"""

BULLET_GREEN_STYLE = """
    QLabel {
        color: #00FF00;
        font-size: 14px;
        font-weight: bold;
    }
"""

BULLET_YELLOW_STYLE = """
    QLabel {
        color: #FFD700;
        font-size: 14px;
        font-weight: bold;
    }
"""

BULLET_RED_STYLE = """
    QLabel {
        color: #FF0000;
        font-size: 14px;
        font-weight: bold;
    }
"""

STATUS_BAR_STYLE = """
    QLabel {
        color: #FFFFFF;
        font-family: Consolas;
        font-size: 9px;
        padding: 3px 5px;
        background-color: #0A0E27;
        border-top: 1px solid #2A2E47;
    }
"""

# ==============================================================================
# CLIENT STATUS WIDGET
# ==============================================================================
class ClientStatusWidget(QWidget):
    """Widget for displaying individual client status"""
    
    # Signals
    clicked = pyqtSignal(int)  # Emits client_id when clicked
    
    def __init__(self, client_id: int, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.tooltip_data = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI components"""
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)
        
        # Status bullet
        self.bullet_label = QLabel("●")
        self.bullet_label.setStyleSheet(BULLET_GREEN_STYLE)
        self.bullet_label.setFixedWidth(20)
        
        # Client name
        self.name_label = QLabel(f"CLIENT {self.client_id}: Loading...")
        self.name_label.setStyleSheet(STATUS_LABEL_STYLE)
        
        layout.addWidget(self.bullet_label)
        layout.addWidget(self.name_label)
        layout.addStretch()
        
        self.setLayout(layout)
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
    
    def update_status(self, name: str, purpose: str, status_symbol: str, 
                     status_color: str, tooltip_data: Dict):
        """Update client status display"""
        # Update text
        self.name_label.setText(f"CLIENT {self.client_id}: {purpose}")
        
        # Update bullet color
        if status_color == COLOR_GREEN:
            self.bullet_label.setStyleSheet(BULLET_GREEN_STYLE)
            self.bullet_label.setText("●")
        elif status_color == COLOR_YELLOW:
            self.bullet_label.setStyleSheet(BULLET_YELLOW_STYLE)
            self.bullet_label.setText("⚠")
        else:  # RED
            self.bullet_label.setStyleSheet(BULLET_RED_STYLE)
            self.bullet_label.setText("✗")
        
        # Store tooltip data
        self.tooltip_data = tooltip_data
        
        # Update tooltip
        self.update_tooltip()
    
    def update_tooltip(self):
        """Update the tooltip with current data"""
        if not self.tooltip_data:
            return
        
        tooltip_text = f"""
<b>{self.tooltip_data.get('title', f'CLIENT {self.client_id}')}</b><br>
<hr>
Status: {self.tooltip_data.get('status', 'Unknown')}<br>
Priority: {self.tooltip_data.get('priority', 'Unknown')}<br>
Latency: {self.tooltip_data.get('latency_avg', 'N/A')}<br>
Rate Limit: {self.tooltip_data.get('rate_limit', 'N/A')}<br>
Health Score: {self.tooltip_data.get('health_score', 0)}/100<br>
<br>
<b>Today's Activity:</b><br>
Orders: {self.tooltip_data.get('orders_today', 0)}<br>
Fills: {self.tooltip_data.get('fills', 0)}<br>
Errors: {self.tooltip_data.get('errors', 0)}<br>
<br>
Last Update: {self.tooltip_data.get('last_update', 'N/A')}
        """
        
        self.setToolTip(tooltip_text)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse click"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.client_id)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """Mouse enters widget"""
        self.setStyleSheet("background-color: #2A2E47; border-radius: 3px;")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Mouse leaves widget"""
        self.setStyleSheet("")
        super().leaveEvent(event)

# ==============================================================================
# SYSTEM HEALTH PANEL
# ==============================================================================
class SystemHealthPanel(QFrame):
    """Panel showing system component health"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.components = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI components"""
        self.setStyleSheet(PANEL_STYLE)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Title
        title = QLabel("SYSTEM HEALTH")
        title.setStyleSheet(TITLE_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Components container
        component_widget = QWidget()
        component_layout = QVBoxLayout()
        component_layout.setContentsMargins(10, 10, 10, 10)
        component_layout.setSpacing(5)
        
        # System components
        components = [
            "RISK MANAGER",
            "MARKET DATA", 
            "STRATEGY ENGINE",
            "ML MODELS",
            "DATABASE"
        ]
        
        for comp_name in components:
            comp_layout = QHBoxLayout()
            
            # Bullet
            bullet = QLabel("●")
            bullet.setStyleSheet(BULLET_GREEN_STYLE)
            bullet.setFixedWidth(20)
            
            # Name
            name = QLabel(comp_name)
            name.setStyleSheet(STATUS_LABEL_STYLE)
            
            comp_layout.addWidget(bullet)
            comp_layout.addWidget(name)
            comp_layout.addStretch()
            
            component_layout.addLayout(comp_layout)
            
            # Store references
            self.components[comp_name] = bullet
        
        component_layout.addStretch()
        component_widget.setLayout(component_layout)
        layout.addWidget(component_widget)
        
        # System health score
        self.health_score_label = QLabel("System Health: 100/100")
        self.health_score_label.setStyleSheet(STATUS_LABEL_STYLE)
        self.health_score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.health_score_label)
        
        self.setLayout(layout)
    
    def update_components(self, component_status: Dict[str, bool]):
        """Update component status indicators"""
        for comp_name, is_healthy in component_status.items():
            if comp_name in self.components:
                bullet = self.components[comp_name]
                if is_healthy:
                    bullet.setStyleSheet(BULLET_GREEN_STYLE)
                    bullet.setText("●")
                else:
                    bullet.setStyleSheet(BULLET_RED_STYLE)
                    bullet.setText("✗")
    
    def update_health_score(self, score: int):
        """Update system health score"""
        self.health_score_label.setText(f"System Health: {score}/100")
        
        # Color code based on score
        if score >= 80:
            color = COLOR_GREEN
        elif score >= 60:
            color = COLOR_YELLOW
        else:
            color = COLOR_RED
        
        self.health_score_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-family: Consolas;
                font-size: 10px;
                padding: 3px;
            }}
        """)

# ==============================================================================
# PROMETHEUS METRICS PANEL
# ==============================================================================
class PrometheusMetricsPanel(QFrame):
    """Panel showing all 9 client connections in 2 columns"""
    
    # Signals
    client_clicked = pyqtSignal(int)  # Emits client_id
    reconnect_requested = pyqtSignal(int)  # Request reconnection
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.client_widgets = {}
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI components"""
        self.setStyleSheet(PANEL_STYLE)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Title
        title = QLabel("PROMETHEUS METRICS")
        title.setStyleSheet(TITLE_STYLE)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
        # Clients container
        clients_widget = QWidget()
        clients_layout = QGridLayout()
        clients_layout.setContentsMargins(10, 10, 10, 10)
        clients_layout.setSpacing(5)
        
        # Create client widgets (2 columns)
        # Column 1: Clients 0-4
        for i in range(5):
            client_widget = ClientStatusWidget(i)
            client_widget.clicked.connect(self.on_client_clicked)
            clients_layout.addWidget(client_widget, i, 0)
            self.client_widgets[i] = client_widget
        
        # Column 2: Clients 5-8
        for i in range(5, 9):
            client_widget = ClientStatusWidget(i)
            client_widget.clicked.connect(self.on_client_clicked)
            clients_layout.addWidget(client_widget, i-5, 1)
            self.client_widgets[i] = client_widget
        
        # Add empty space in column 2, row 5
        spacer = QLabel("")
        clients_layout.addWidget(spacer, 4, 1)
        
        clients_widget.setLayout(clients_layout)
        main_layout.addWidget(clients_widget)
        
        self.setLayout(main_layout)
    
    def update_clients(self, clients_data: Dict[int, Dict]):
        """Update all client displays"""
        for client_id, data in clients_data.items():
            if client_id in self.client_widgets:
                widget = self.client_widgets[client_id]
                widget.update_status(
                    name=data.get('name', f'CLIENT {client_id}'),
                    purpose=data.get('purpose', 'Unknown'),
                    status_symbol=data.get('status_level', '●'),
                    status_color=data.get('status_color', COLOR_GREEN),
                    tooltip_data=data.get('tooltip', {})
                )
    
    def on_client_clicked(self, client_id: int):
        """Handle client widget click"""
        self.client_clicked.emit(client_id)
        
        # Show context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #1A1E37;
                color: #FFFFFF;
                border: 1px solid #2A2E47;
            }
            QMenu::item:selected {
                background-color: #2A2E47;
            }
        """)
        
        # Actions
        reconnect_action = QAction(f"Reconnect Client {client_id}", self)
        reconnect_action.triggered.connect(lambda: self.reconnect_requested.emit(client_id))
        menu.addAction(reconnect_action)
        
        view_logs_action = QAction(f"View Client {client_id} Logs", self)
        view_logs_action.triggered.connect(lambda: self.view_client_logs(client_id))
        menu.addAction(view_logs_action)
        
        # Show menu at cursor position
        menu.exec(self.cursor().pos())
    
    def view_client_logs(self, client_id: int):
        """View logs for specific client"""
        QMessageBox.information(self, f"Client {client_id} Logs", 
                               f"Logs for Client {client_id} would be displayed here.\n"
                               f"Integration with log viewer pending.")

# ==============================================================================
# MAIN MONITOR PANEL
# ==============================================================================
class ClientMonitorPanel(QWidget):
    """Main monitoring panel combining System Health and Prometheus Metrics"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            import logging
            self.logger = logging.getLogger(__name__)
        
        # Integration manager
        self.integration_manager = None
        
        # Setup UI
        self.setup_ui()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.setInterval(UPDATE_INTERVAL)
    
    def setup_ui(self):
        """Setup the main UI"""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Panels container
        panels_container = QWidget()
        panels_layout = QHBoxLayout()
        panels_layout.setContentsMargins(0, 0, 0, 0)
        panels_layout.setSpacing(2)
        
        # System Health Panel (left)
        self.system_health_panel = SystemHealthPanel()
        panels_layout.addWidget(self.system_health_panel, 1)
        
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.VLine)
        divider.setStyleSheet("QFrame { color: #2A2E47; }")
        panels_layout.addWidget(divider)
        
        # Prometheus Metrics Panel (right)
        self.prometheus_panel = PrometheusMetricsPanel()
        self.prometheus_panel.client_clicked.connect(self.on_client_clicked)
        self.prometheus_panel.reconnect_requested.connect(self.on_reconnect_requested)
        panels_layout.addWidget(self.prometheus_panel, 2)
        
        panels_container.setLayout(panels_layout)
        main_layout.addWidget(panels_container)
        
        # Status bar
        self.status_bar = QLabel("System Health: --/100 | Active Clients: --/9 | Memory: --% | CPU: --% | API Calls/Sec: --")
        self.status_bar.setStyleSheet(STATUS_BAR_STYLE)
        main_layout.addWidget(self.status_bar)
        
        self.setLayout(main_layout)
        
        # Set background
        self.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")
    
    def set_integration_manager(self, manager: GatewayIntegrationManager):
        """Set the integration manager for data updates"""
        self.integration_manager = manager
        
        # Connect signals
        manager.dashboard_update.connect(self.on_dashboard_update)
        manager.system_log_update.connect(self.on_system_log)
        manager.alert_signal.connect(self.on_alert)
        
        self.logger.info("Integration manager connected")
    
    def start_monitoring(self):
        """Start monitoring updates"""
        if self.integration_manager:
            self.integration_manager.start()
        self.update_timer.start()
        self.logger.info("Monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring updates"""
        self.update_timer.stop()
        if self.integration_manager:
            self.integration_manager.stop()
        self.logger.info("Monitoring stopped")
    
    @pyqtSlot(dict)
    def on_dashboard_update(self, data: Dict):
        """Handle dashboard update from integration manager"""
        try:
            # Update system health
            if 'system_health' in data:
                self.system_health_panel.update_components(data['system_health'])
            
            if 'system_health_score' in data:
                self.system_health_panel.update_health_score(data['system_health_score'])
            
            # Update clients
            if 'clients' in data:
                self.prometheus_panel.update_clients(data['clients'])
            
            # Update status bar
            if 'stats' in data:
                stats = data['stats']
                status_text = (f"System Health: {data.get('system_health_score', 0)}/100 | "
                             f"Active Clients: {stats['active_clients']}/{stats['total_clients']} | "
                             f"Memory: {stats['memory_percent']:.0f}% | "
                             f"CPU: {stats['cpu_percent']:.0f}% | "
                             f"API Calls/Sec: {stats['api_calls_per_sec']}")
                self.status_bar.setText(status_text)
            
        except Exception as e:
            self.logger.error(f"Error updating dashboard: {e}")
    
    @pyqtSlot(str)
    def on_system_log(self, log_entry: str):
        """Handle system log entry"""
        # This would be integrated with main dashboard's log viewer
        self.logger.info(f"System log: {log_entry}")
    
    @pyqtSlot(str, str)
    def on_alert(self, severity: str, message: str):
        """Handle alert from integration manager"""
        if severity == "CRITICAL":
            # Flash or highlight the affected component
            self.logger.critical(f"Alert: {message}")
            # Could trigger visual alert here
    
    def on_client_clicked(self, client_id: int):
        """Handle client click"""
        self.logger.info(f"Client {client_id} clicked")
        # Could open detailed view
    
    def on_reconnect_requested(self, client_id: int):
        """Handle reconnection request"""
        if self.integration_manager:
            self.integration_manager.reconnect_client(client_id)
            self.logger.info(f"Reconnection requested for client {client_id}")
    
    def update_display(self):
        """Manual display update"""
        if self.integration_manager:
            self.integration_manager.update_dashboard()

# ==============================================================================
# STANDALONE TEST WINDOW
# ==============================================================================
class TestWindow(QMainWindow):
    """Test window for development"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_integration()
    
    def setup_ui(self):
        """Setup test window UI"""
        self.setWindowTitle("SPYDER - Client Monitor Panel Test")
        self.setGeometry(100, 100, 800, 400)
        
        # Set dark theme
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLOR_BACKGROUND};
            }}
        """)
        
        # Create monitor panel
        self.monitor_panel = ClientMonitorPanel()
        self.setCentralWidget(self.monitor_panel)
        
        # Add menu bar
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background-color: #0A0E27;
                color: #FFFFFF;
            }
            QMenuBar::item:selected {
                background-color: #2A2E47;
            }
        """)
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        export_action = QAction("Export Health Report", self)
        export_action.triggered.connect(self.export_health_report)
        file_menu.addAction(export_action)
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Control menu
        control_menu = menubar.addMenu("Control")
        
        start_action = QAction("Start Monitoring", self)
        start_action.triggered.connect(self.monitor_panel.start_monitoring)
        control_menu.addAction(start_action)
        
        stop_action = QAction("Stop Monitoring", self)
        stop_action.triggered.connect(self.monitor_panel.stop_monitoring)
        control_menu.addAction(stop_action)
    
    def setup_integration(self):
        """Setup integration manager"""
        if GatewayIntegrationManager:
            self.integration_manager = GatewayIntegrationManager()
            self.monitor_panel.set_integration_manager(self.integration_manager)
            
            # Start monitoring
            self.monitor_panel.start_monitoring()
        else:
            # Create mock data for testing
            self.create_mock_data()
    
    def create_mock_data(self):
        """Create mock data for testing without integration"""
        mock_data = {
            'system_health': {
                'RISK MANAGER': True,
                'MARKET DATA': True,
                'STRATEGY ENGINE': True,
                'ML MODELS': False,  # One unhealthy for testing
                'DATABASE': True
            },
            'system_health_score': 92,
            'clients': {
                0: {'name': 'CLIENT 0', 'purpose': 'Admin', 
                    'status_color': COLOR_GREEN, 'status_level': '●',
                    'tooltip': {'title': 'CLIENT 0: Admin', 'status': 'Connected'}},
                1: {'name': 'CLIENT 1', 'purpose': 'Orders', 
                    'status_color': COLOR_GREEN, 'status_level': '●',
                    'tooltip': {'title': 'CLIENT 1: Orders', 'status': 'Connected'}},
                2: {'name': 'CLIENT 2', 'purpose': 'Core', 
                    'status_color': COLOR_GREEN, 'status_level': '●',
                    'tooltip': {'title': 'CLIENT 2: Core', 'status': 'Connected'}},
                3: {'name': 'CLIENT 3', 'purpose': 'Options', 
                    'status_color': COLOR_GREEN, 'status_level': '●',
                    'tooltip': {'title': 'CLIENT 3: Options', 'status': 'Connected'}},
                4: {'name': 'CLIENT 4', 'purpose': 'Volatility', 
                    'status_color': COLOR_YELLOW, 'status_level': '⚠',
                    'tooltip': {'title': 'CLIENT 4: Volatility', 'status': 'Degraded'}},
                5: {'name': 'CLIENT 5', 'purpose': 'Internals', 
                    'status_color': COLOR_GREEN, 'status_level': '●',
                    'tooltip': {'title': 'CLIENT 5: Internals', 'status': 'Connected'}},
                6: {'name': 'CLIENT 6', 'purpose': 'Major ETFs', 
                    'status_color': COLOR_GREEN, 'status_level': '●',
                    'tooltip': {'title': 'CLIENT 6: ETFs', 'status': 'Connected'}},
                7: {'name': 'CLIENT 7', 'purpose': 'Extended', 
                    'status_color': COLOR_RED, 'status_level': '✗',
                    'tooltip': {'title': 'CLIENT 7: Extended', 'status': 'Disconnected'}},
                8: {'name': 'CLIENT 8', 'purpose': 'Sector ETFs', 
                    'status_color': COLOR_GREEN, 'status_level': '●',
                    'tooltip': {'title': 'CLIENT 8: Sectors', 'status': 'Connected'}}
            },
            'stats': {
                'active_clients': 8,
                'total_clients': 9,
                'memory_percent': 45,
                'cpu_percent': 22,
                'api_calls_per_sec': 127
            }
        }
        
        # Update with mock data
        self.monitor_panel.on_dashboard_update(mock_data)
    
    def export_health_report(self):
        """Export health report to file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Export Health Report", 
            f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON Files (*.json)"
        )
        
        if filename and self.integration_manager:
            self.integration_manager.export_health_report(Path(filename))
            QMessageBox.information(self, "Export Complete", 
                                  f"Health report exported to:\n{filename}")

# ==============================================================================
# MODULE TEST
# ==============================================================================
def main():
    """Test the monitor panel"""
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle("Fusion")
    
    # Create and show test window
    window = TestWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()