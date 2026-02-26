#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderG07_PrometheusMetricsDisplay.py
Group: G (GUI/User Interface)
Purpose: [DEPRECATED] GUI display widget for Prometheus metrics from SpyderB15
Author: Mohamed Talib
Date Created: 2025-08-07
Last Updated: 2026-02-25 Time: 21:45:00

DEPRECATION NOTICE:
    This module is DEPRECATED as of the Tradier+Databento migration (Feb 2026).
    It was designed to display Prometheus metrics from SpyderB15_PrometheusMetrics
    for 10 IB Gateway clients matching SpyderB08_MultiClientDataManager,
    which no longer exists.

    The system now uses:
    - SpyderB40_TradierClient for order execution (single REST API)
    - SpyderC26_DatabentoClient for market data (WebSocket)
    - SpyderG05_ConnectAPIStatus for connection status display
    - SpyderM_Monitoring for system health metrics

    This module is preserved for backward compatibility only.
"""

import warnings
warnings.warn(
    "SpyderG07_PrometheusMetricsDisplay is DEPRECATED. "
    "The system has migrated from IBKR (SpyderB15 Prometheus, 10-client IB Gateway) "
    "to Tradier API. Use SpyderG05_ConnectAPIStatus and SpyderM_Monitoring instead.",
    DeprecationWarning,
    stacklevel=2
)

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import json
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGroupBox,
    QGridLayout,
    QFrame,
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
    Slot,
    QThread,
    QObject,
)
from PySide6.QtGui import (
    QFont,
    QColor,
)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
# Add parent directory to path for imports
project_root = Path(__file__).parent.parent.absolute()
sys.path.insert(0, str(project_root))

try:
    # Import the backend B15 module for metrics data
    from SpyderB_Broker.SpyderB15_PrometheusMetrics import (
        PrometheusMetricsCollector,
        MetricsConfig,
        ClientMetrics
    )
    B15_AVAILABLE = True
except ImportError:
    B15_AVAILABLE = False
    print("⚠️ SpyderB15_PrometheusMetrics not available - using simulation mode")

# ==============================================================================
# CONSTANTS
# ==============================================================================
COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "text_dim": "#888888",
    "positive": "#00ff41",
    "negative": "#ff1744",
    "neutral": "#ffd700",
    "warning": "#ff9800",
    "active": "#00ff41",
    "inactive": "#666666",
    "cyan": "#00ffff",
}

# FIXED: Client definitions matching SpyderB08 (1-10 range with correct allocation)
CLIENT_DEFINITIONS = {
    "CLIENT 1": "Orders",        # FIXED: Order Execution (HIGHEST PRIORITY)
    "CLIENT 2": "Admin",         # FIXED: Administrative  
    "CLIENT 3": "Core",          # Core Data
    "CLIENT 4": "Options",       # SPY Options
    "CLIENT 5": "Volatility",    # Volatility Indicators
    "CLIENT 6": "Internals",     # Market Internals
    "CLIENT 7": "Major ETFs",    # Major Indices
    "CLIENT 8": "Extended",      # Extended Assets
    "CLIENT 9": "Sector ETFs",   # Sector ETFs
    "CLIENT 10": "International" # FIXED: Added International Markets
}

# ==============================================================================
# METRICS DATA WORKER (Connects to B15)
# ==============================================================================
class MetricsDataWorker(QObject):
    """Worker thread to fetch metrics from SpyderB15"""
    
    # Signals
    metrics_updated = Signal(dict)
    connection_status_changed = Signal(bool)
    error_occurred = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.collector = None
        self.running = False
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.fetch_metrics)
        
    def start(self):
        """Start fetching metrics from B15"""
        try:
            if B15_AVAILABLE:
                # Create connection to B15 metrics collector
                config = MetricsConfig(
                    client_id=11,  # FIXED: Use Client 11 for Prometheus metrics (outside main range)
                    port=9090,
                    update_interval=10
                )
                self.collector = PrometheusMetricsCollector(config)
                
                # Start the collector
                self.collector.start()
                self.connection_status_changed.emit(True)
                
                # Start update timer
                self.running = True
                self.update_timer.start(2000)  # Update every 2 seconds
                
            else:
                # Simulation mode
                self.running = True
                self.update_timer.start(2000)
                self.connection_status_changed.emit(False)
                
        except Exception as e:
            self.error_occurred.emit(f"Failed to start metrics worker: {e}")
            
    def fetch_metrics(self):
        """Fetch current metrics from B15 or simulate"""
        try:
            if B15_AVAILABLE and self.collector:
                # Get real metrics from B15
                metrics = self._get_b15_metrics()
            else:
                # Simulate metrics
                metrics = self._simulate_metrics()
                
            self.metrics_updated.emit(metrics)
            
        except Exception as e:
            self.error_occurred.emit(f"Error fetching metrics: {e}")
            
    def _get_b15_metrics(self) -> dict:
        """Get real metrics from B15 collector"""
        metrics = {
            "client_status": {},
            "active_clients": 0,
            "memory_usage": 0,
            "cpu_usage": 0,
            "api_calls_per_sec": 0
        }
        
        if self.collector:
            # Get client metrics (1-10 range)
            for client_id, client_metrics in self.collector.client_metrics.items():
                if 1 <= client_id <= 10:  # FIXED: Only include valid client range
                    client_key = f"CLIENT {client_id}"
                    metrics["client_status"][client_key] = client_metrics.connected
                    if client_metrics.connected:
                        metrics["active_clients"] += 1
            
            # Get system metrics from B15's actual psutil readings
            summary = self.collector.get_metrics_summary()
            
            # These would come from the actual Prometheus metrics
            # For now, we'll use placeholder values
            metrics["memory_usage"] = 45  # Would come from system_memory_usage gauge
            metrics["cpu_usage"] = 22     # Would come from system_cpu_usage gauge
            metrics["api_calls_per_sec"] = 127  # Would come from aggregated counters
            
        return metrics
    
    def _simulate_metrics(self) -> dict:
        """Simulate metrics when B15 is not available"""
        import random
        
        # FIXED: Simulate all 10 clients (1-10 range)
        metrics = {
            "client_status": {
                f"CLIENT {i}": random.random() > 0.1  # 90% chance active
                for i in range(1, 11)  # FIXED: 1-10 range
            },
            "active_clients": 0,
            "memory_usage": random.randint(40, 50),
            "cpu_usage": random.randint(18, 28),
            "api_calls_per_sec": random.randint(100, 150)
        }
        
        # Count active clients
        metrics["active_clients"] = sum(
            1 for status in metrics["client_status"].values() if status
        )
        
        return metrics
    
    def stop(self):
        """Stop the worker"""
        self.running = False
        self.update_timer.stop()
        
        if self.collector:
            self.collector.stop()
            self.collector = None

# ==============================================================================
# CLIENT STATUS WIDGET
# ==============================================================================
class ClientStatusWidget(QWidget):
    """Individual client status indicator widget"""
    
    def __init__(self, client_id: str, client_type: str, parent=None):
        super().__init__(parent)
        self.client_id = client_id
        self.client_type = client_type
        self.is_active = False
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the client status UI"""
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(3)
        
        # Status indicator dot
        self.status_dot = QLabel("●")
        self.status_dot.setFixedWidth(12)
        self.status_dot.setStyleSheet(f"color: {COLORS['inactive']};")
        layout.addWidget(self.status_dot)
        
        # Client label
        self.client_label = QLabel(f"{self.client_id}:")
        self.client_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
        self.client_label.setFixedWidth(65)  # FIXED: Slightly wider for "CLIENT 10"
        layout.addWidget(self.client_label)
        
        # Client type
        self.type_label = QLabel(self.client_type)
        self.type_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 10px;")
        self.type_label.setMinimumWidth(80)
        layout.addWidget(self.type_label)
        
        layout.addStretch()
        self.setLayout(layout)
        
    def set_active(self, active: bool):
        """Set client active status"""
        self.is_active = active
        color = COLORS['active'] if active else COLORS['inactive']
        self.status_dot.setStyleSheet(f"color: {color};")
        
        # Update text color based on status
        text_color = COLORS['text'] if active else COLORS['text_dim']
        self.type_label.setStyleSheet(f"color: {text_color}; font-size: 10px;")

# ==============================================================================
# PROMETHEUS METRICS DISPLAY WIDGET (G07)
# ==============================================================================
class PrometheusMetricsDisplay(QGroupBox):
    """Main Prometheus Metrics display widget that connects to B15 backend"""
    
    # Signals
    metrics_updated = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__("PROMETHEUS METRICS", parent)
        self.client_widgets = {}
        self.current_metrics = {
            "active_clients": 0,
            "memory_usage": 0,
            "cpu_usage": 0,
            "api_calls_per_sec": 0,
            "client_status": {}
        }
        
        # Worker thread for B15 connection
        self.worker_thread = QThread()
        self.metrics_worker = MetricsDataWorker()
        self.metrics_worker.moveToThread(self.worker_thread)
        
        # Connect signals
        self.worker_thread.started.connect(self.metrics_worker.start)
        self.metrics_worker.metrics_updated.connect(self.on_metrics_received)
        self.metrics_worker.connection_status_changed.connect(self.on_connection_changed)
        self.metrics_worker.error_occurred.connect(self.on_error)
        
        # Setup UI
        self.setup_ui()
        
        # Start worker thread
        self.worker_thread.start()
        
    def setup_ui(self):
        """Setup the Prometheus Metrics UI"""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 10, 5, 5)
        main_layout.setSpacing(3)
        
        # Create two columns for clients
        clients_widget = QWidget()
        clients_layout = QGridLayout()
        clients_layout.setContentsMargins(0, 0, 0, 0)
        clients_layout.setSpacing(1)
        
        # FIXED: Create client status widgets in two columns (1-10 range)
        row = 0
        col = 0
        for client_id, client_type in CLIENT_DEFINITIONS.items():
            widget = ClientStatusWidget(client_id, client_type)
            self.client_widgets[client_id] = widget
            clients_layout.addWidget(widget, row, col)
            
            # Move to next column or row
            col += 1
            if col > 1:  # Two columns
                col = 0
                row += 1
        
        clients_widget.setLayout(clients_layout)
        main_layout.addWidget(clients_widget)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color: {COLORS['border']};")
        main_layout.addWidget(separator)
        
        # System metrics section
        metrics_widget = QWidget()
        metrics_layout = QHBoxLayout()
        metrics_layout.setContentsMargins(5, 3, 5, 3)
        metrics_layout.setSpacing(8)
        
        # System Health indicator
        self.health_label = QLabel("System Health:")
        self.health_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px;")
        metrics_layout.addWidget(self.health_label)
        
        self.health_value = QLabel("--/100")
        self.health_value.setStyleSheet(f"color: {COLORS['positive']}; font-size: 10px; font-weight: bold;")
        metrics_layout.addWidget(self.health_value)
        
        metrics_layout.addStretch()
        metrics_widget.setLayout(metrics_layout)
        main_layout.addWidget(metrics_widget)
        
        # Bottom metrics row
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(5, 2, 5, 2)
        bottom_layout.setSpacing(5)
        
        # Active Clients
        self.active_clients_label = QLabel("Active Clients:")
        self.active_clients_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        bottom_layout.addWidget(self.active_clients_label)
        
        self.active_clients_value = QLabel("0/10")  # FIXED: 0/10 instead of 0/9
        self.active_clients_value.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 9px;")
        bottom_layout.addWidget(self.active_clients_value)
        
        # Separator
        sep1 = QLabel("|")
        sep1.setStyleSheet(f"color: {COLORS['border']}; font-size: 9px;")
        bottom_layout.addWidget(sep1)
        
        # Memory
        self.memory_label = QLabel("Memory:")
        self.memory_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        bottom_layout.addWidget(self.memory_label)
        
        self.memory_value = QLabel("0%")
        self.memory_value.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 9px;")
        bottom_layout.addWidget(self.memory_value)
        
        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet(f"color: {COLORS['border']}; font-size: 9px;")
        bottom_layout.addWidget(sep2)
        
        # CPU
        self.cpu_label = QLabel("CPU:")
        self.cpu_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        bottom_layout.addWidget(self.cpu_label)
        
        self.cpu_value = QLabel("0%")
        self.cpu_value.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 9px;")
        bottom_layout.addWidget(self.cpu_value)
        
        # Separator
        sep3 = QLabel("|")
        sep3.setStyleSheet(f"color: {COLORS['border']}; font-size: 9px;")
        bottom_layout.addWidget(sep3)
        
        # API Calls
        self.api_label = QLabel("API Calls/Sec:")
        self.api_label.setStyleSheet(f"color: {COLORS['text_dim']}; font-size: 9px;")
        bottom_layout.addWidget(self.api_label)
        
        self.api_value = QLabel("0")
        self.api_value.setStyleSheet(f"color: {COLORS['cyan']}; font-size: 9px;")
        bottom_layout.addWidget(self.api_value)
        
        bottom_layout.addStretch()
        bottom_widget.setLayout(bottom_layout)
        main_layout.addWidget(bottom_widget)
        
        self.setLayout(main_layout)
        
        # Apply group box styling
        self.setStyleSheet(f"""
            QGroupBox {{
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: {COLORS['background']};
                font-size: 11px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
    
    @Slot(dict)
    def on_metrics_received(self, metrics: dict):
        """Handle metrics from B15 backend"""
        self.current_metrics = metrics
        self.update_display()
        self.metrics_updated.emit(metrics)
    
    @Slot(bool)
    def on_connection_changed(self, connected: bool):
        """Handle B15 connection status change"""
        if connected:
            print("✅ Connected to SpyderB15 Prometheus Metrics")
        else:
            print("⚠️ Running in simulation mode (B15 not available)")
    
    @Slot(str)
    def on_error(self, error: str):
        """Handle errors from worker"""
        print(f"❌ Metrics error: {error}")
        
    def update_display(self):
        """Update the display with current metrics"""
        # Update client status indicators
        for client_id, widget in self.client_widgets.items():
            is_active = self.current_metrics["client_status"].get(client_id, False)
            widget.set_active(is_active)
            
        # Update metrics values
        active = self.current_metrics["active_clients"]
        self.active_clients_value.setText(f"{active}/10")  # FIXED: /10 instead of /9
        
        memory = self.current_metrics["memory_usage"]
        self.memory_value.setText(f"{memory}%")
        self.memory_value.setStyleSheet(
            f"color: {self._get_metric_color(memory, 70, 85)}; font-size: 9px;"
        )
        
        cpu = self.current_metrics["cpu_usage"]
        self.cpu_value.setText(f"{cpu}%")
        self.cpu_value.setStyleSheet(
            f"color: {self._get_metric_color(cpu, 60, 80)}; font-size: 9px;"
        )
        
        api_calls = self.current_metrics["api_calls_per_sec"]
        self.api_value.setText(str(api_calls))
        
        # Update system health score
        health_score = self._calculate_health_score()
        self.health_value.setText(f"{health_score}/100")
        health_color = COLORS['positive'] if health_score >= 80 else \
                      COLORS['warning'] if health_score >= 60 else COLORS['negative']
        self.health_value.setStyleSheet(f"color: {health_color}; font-size: 10px; font-weight: bold;")
        
    def _get_metric_color(self, value: float, warning_threshold: float, critical_threshold: float) -> str:
        """Get color based on metric value and thresholds"""
        if value >= critical_threshold:
            return COLORS['negative']
        elif value >= warning_threshold:
            return COLORS['warning']
        else:
            return COLORS['cyan']
            
    def _calculate_health_score(self) -> int:
        """Calculate overall system health score"""
        score = 100
        
        # Deduct points for high resource usage
        if self.current_metrics["memory_usage"] > 85:
            score -= 20
        elif self.current_metrics["memory_usage"] > 70:
            score -= 10
            
        if self.current_metrics["cpu_usage"] > 80:
            score -= 15
        elif self.current_metrics["cpu_usage"] > 60:
            score -= 8
            
        # FIXED: Deduct points for inactive clients (out of 10 total)
        inactive_clients = 10 - self.current_metrics["active_clients"]
        score -= (inactive_clients * 2)
        
        # Ensure score is between 0 and 100
        return max(0, min(100, score))
    
    def cleanup(self):
        """Clean up resources when widget is destroyed"""
        if self.metrics_worker:
            self.metrics_worker.stop()
        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()

# ==============================================================================
# MODULE-LEVEL FUNCTIONS FOR BACKWARDS COMPATIBILITY
# ==============================================================================
def get_client_status(client_id: int) -> dict:
    """
    Get status for a specific client ID.
    This is a module-level function for compatibility with SpyderG05.
    
    Args:
        client_id: Client ID (1-10)  # FIXED: Updated range
        
    Returns:
        Dictionary with client status information
    """
    return {
        'connected': True,  # Default to connected for simulation
        'client_id': client_id,
        'type': _get_client_type(client_id),
        'status': 'ACTIVE'
    }

def get_system_metrics() -> dict:
    """
    Get system metrics.
    This is a module-level function for compatibility with SpyderG05.
    
    Returns:
        Dictionary with system metrics
    """
    import random
    return {
        'memory_percent': random.uniform(40, 60),
        'cpu_percent': random.uniform(20, 40),
        'api_calls_per_sec': random.randint(100, 150),
        'active_clients': 9,  # Most clients active
        'total_clients': 10   # FIXED: Total of 10 clients
    }

def _get_client_type(client_id: int) -> str:
    """FIXED: Helper to get client type from ID (1-10 range with correct allocation)"""
    client_types = {
        1: "Orders",        # FIXED: Order Execution (HIGHEST PRIORITY) 
        2: "Admin",         # FIXED: Administrative
        3: "Core",          # Core Data
        4: "Options",       # SPY Options
        5: "Volatility",    # Volatility Indicators
        6: "Internals",     # Market Internals
        7: "Major ETFs",    # Major Indices
        8: "Extended",      # Extended Assets
        9: "Sector ETFs",   # Sector ETFs
        10: "International" # FIXED: International Markets
    }
    return client_types.get(client_id, "Unknown")

# Export these functions
__all__ = ['get_client_status', 'get_system_metrics', 'PrometheusMetricsDisplay']


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Prometheus Metrics Display Test (G07) - FIXED")
    window.setGeometry(100, 100, 450, 400)  # Slightly larger for 10 clients
    
    # Set dark theme
    window.setStyleSheet(f"background-color: {COLORS['background']};")
    
    # Create and set the Prometheus widget
    prometheus_widget = PrometheusMetricsDisplay()
    window.setCentralWidget(prometheus_widget)
    
    window.show()
    
    print("\n" + "="*70)
    print("PROMETHEUS METRICS DISPLAY (G07) - FIXED")
    print("="*70)
    print("✅ FIXES APPLIED:")
    print("   • Client range updated: 0-8 → 1-10")
    print("   • Client allocation fixed: Client 1=Orders, Client 2=Admin")
    print("   • Added Client 10 for International Markets")
    print("   • Total clients updated: 9 → 10")
    print("   • _get_client_type() function completely rebuilt")
    print("   • CLIENT_DEFINITIONS dictionary updated")
    print("\n📊 CLIENT ALLOCATION (FIXED):")
    for i in range(1, 11):
        print(f"   Client {i:2d}: {_get_client_type(i)}")
    print("\n🔗 This widget connects to SpyderB15_PrometheusMetrics backend")
    print("   If B15 is not available, it runs in simulation mode")
    print("   Now fully consistent with SpyderB08 specification")
    print("="*70 + "\n")
    
    sys.exit(app.exec())
