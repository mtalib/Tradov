#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System
================================================================================
Module: SpyderG10_CustomMetricsIntegration.py
Group: G (GUI)
Purpose: Integration bridge between Custom Metrics Client and Trading Dashboard
Author: Mohamed Talib
Date Created: 2025-01-15
Last Updated: 2025-01-15 Time: 10:30:00

Description:
    This module provides the integration layer between the Custom Metrics Client
    (Client 10 - SpyderB18) and the Trading Dashboard (SpyderG05). It handles
    data flow, formatting, real-time updates, and ensures seamless display of
    GEX, DEX, OGL, DIX, and SWAN metrics in the dashboard. The module includes
    automatic reconnection, data validation, and fallback mechanisms for
    reliable operation.

Key Features:
    - Real-time metric updates from Client 10 to dashboard
    - Automatic formatting for dashboard display
    - Color coding based on metric values and changes
    - Historical data tracking for trend visualization
    - Error handling with graceful degradation

Integration Points:
    - Subscribes to SpyderB18_CustomMetricsClient for data
    - Updates SpyderG05_TradingDashboard custom indicator widgets
    - Interfaces with SpyderB08_MultiClientDataManager
    - Reports status to SpyderB15_PrometheusMetrics
 
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import time
import threading
import queue
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque
import json

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
from PyQt6.QtCore import (
    QObject, QTimer, pyqtSignal, pyqtSlot, Qt, QThread
)
from PyQt6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout
)
from PyQt6.QtGui import QColor, QPalette

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    from SpyderB_Broker.SpyderB18_CustomMetricsClient import (
        CustomMetricsClient, get_metrics_client, MetricType, MetricResult
    )
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"⚠️ Some modules not available: {e}")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update intervals (milliseconds)
DASHBOARD_UPDATE_INTERVAL = 1000  # 1 second for dashboard refresh
RECONNECT_INTERVAL = 5000  # 5 seconds for reconnection attempts
HISTORY_SIZE = 100  # Number of historical points to keep

# Display formatting
METRIC_FORMATS = {
    'GEX': {'suffix': 'B', 'decimals': 2, 'prefix': '$'},
    'DEX': {'suffix': 'B', 'decimals': 2, 'prefix': '$'},
    'OGL': {'suffix': '', 'decimals': 1, 'prefix': ''},
    'DIX': {'suffix': '%', 'decimals': 1, 'prefix': ''},
    'SWAN': {'suffix': '', 'decimals': 1, 'prefix': ''}
}

# Color thresholds
COLOR_THRESHOLDS = {
    'GEX': {
        'extreme_negative': -5.0,
        'negative': -2.0,
        'neutral_low': 0.0,
        'neutral_high': 2.0,
        'positive': 5.0
    },
    'DEX': {
        'extreme_negative': -10.0,
        'negative': -5.0,
        'neutral_low': 0.0,
        'neutral_high': 5.0,
        'positive': 10.0
    },
    'OGL': {
        'low': 30,
        'medium': 50,
        'high': 70,
        'extreme': 85
    },
    'DIX': {
        'bearish': 40,
        'neutral_low': 45,
        'neutral_high': 50,
        'bullish': 55
    },
    'SWAN': {
        'low': 20,
        'medium': 40,
        'high': 60,
        'extreme': 80
    }
}

# Dashboard colors (matching SpyderG05)
COLORS = {
    'background': '#0A0E1A',
    'panel': '#141824',
    'border': '#1E2433',
    'text': '#E0E0E0',
    'text_dim': '#808080',
    'positive': '#00E676',
    'negative': '#FF1744',
    'neutral': '#FFD700',
    'warning': '#FF9800',
    'extreme': '#FF00FF'
}

# ==============================================================================
# DATA CLASSES
# ==============================================================================
@dataclass
class MetricDisplay:
    """Display information for a metric"""
    name: str
    value: float
    change: float
    change_pct: float
    formatted_value: str
    formatted_change: str
    color: str
    trend: str  # 'up', 'down', 'flat'
    confidence: float
    last_update: datetime

@dataclass
class MetricHistory:
    """Historical data for a metric"""
    timestamps: deque
    values: deque
    changes: deque
    
    def __init__(self, maxlen: int = HISTORY_SIZE):
        self.timestamps = deque(maxlen=maxlen)
        self.values = deque(maxlen=maxlen)
        self.changes = deque(maxlen=maxlen)
    
    def add(self, timestamp: datetime, value: float, change: float):
        """Add a data point to history"""
        self.timestamps.append(timestamp)
        self.values.append(value)
        self.changes.append(change)

# ==============================================================================
# CUSTOM METRICS INTEGRATION CLASS
# ==============================================================================
class CustomMetricsIntegration(QObject):
    """
    Integration layer between Custom Metrics Client and Trading Dashboard.
    
    Handles data flow, formatting, and real-time updates for custom metrics
    display in the SpyderG05 Trading Dashboard.
    """
    
    # Qt Signals for dashboard updates
    metric_updated = pyqtSignal(str, dict)  # metric_name, data
    all_metrics_updated = pyqtSignal(dict)  # all metrics data
    connection_status_changed = pyqtSignal(bool)  # connected status
    error_occurred = pyqtSignal(str)  # error message
    
    def __init__(self, dashboard_widget: Optional[QWidget] = None):
        """
        Initialize the Custom Metrics Integration.
        
        Args:
            dashboard_widget: Optional reference to dashboard widget
        """
        super().__init__()
        
        # Core components
        self.dashboard_widget = dashboard_widget
        self.is_running = False
        self.is_connected = False
        
        # Logging
        if MODULES_AVAILABLE:
            self.logger = SpyderLogger.get_logger('SpyderG10.Integration')
            self.error_handler = SpyderErrorHandler()
        else:
            self.logger = logging.getLogger('SpyderG10.Integration')
            self.error_handler = None
        
        # Metrics client
        self.metrics_client: Optional[CustomMetricsClient] = None
        
        # Data storage
        self.current_metrics: Dict[str, MetricDisplay] = {}
        self.metric_history: Dict[str, MetricHistory] = {
            'GEX': MetricHistory(),
            'DEX': MetricHistory(),
            'OGL': MetricHistory(),
            'DIX': MetricHistory(),
            'SWAN': MetricHistory()
        }
        
        # Update timers
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_dashboard)
        self.update_timer.setInterval(DASHBOARD_UPDATE_INTERVAL)
        
        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self.check_connection)
        self.reconnect_timer.setInterval(RECONNECT_INTERVAL)
        
        # Performance tracking
        self.update_count = 0
        self.error_count = 0
        self.last_update_time = datetime.now()
        
        # Initialize display values
        self._initialize_display_values()
        
        self.logger.info("✅ Custom Metrics Integration initialized")
    
    # ==========================================================================
    # INITIALIZATION AND CONNECTION
    # ==========================================================================
    
    def _initialize_display_values(self):
        """Initialize default display values for all metrics."""
        for metric_name in ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']:
            self.current_metrics[metric_name] = MetricDisplay(
                name=metric_name,
                value=0.0,
                change=0.0,
                change_pct=0.0,
                formatted_value=self._format_value(metric_name, 0.0),
                formatted_change=self._format_change(metric_name, 0.0, 0.0),
                color=COLORS['text_dim'],
                trend='flat',
                confidence=0.0,
                last_update=datetime.now()
            )
    
    def start(self):
        """Start the integration service."""
        if self.is_running:
            self.logger.warning("Integration already running")
            return
        
        self.logger.info("Starting Custom Metrics Integration...")
        
        # Connect to metrics client
        self._connect_to_client()
        
        # Start timers
        self.update_timer.start()
        self.reconnect_timer.start()
        
        self.is_running = True
        self.logger.info("✅ Custom Metrics Integration started")
    
    def stop(self):
        """Stop the integration service."""
        if not self.is_running:
            return
        
        self.logger.info("Stopping Custom Metrics Integration...")
        
        # Stop timers
        self.update_timer.stop()
        self.reconnect_timer.stop()
        
        # Disconnect from client
        self._disconnect_from_client()
        
        self.is_running = False
        self.logger.info("✅ Custom Metrics Integration stopped")
    
    def _connect_to_client(self):
        """Connect to the Custom Metrics Client."""
        try:
            if MODULES_AVAILABLE:
                # Get or create metrics client
                self.metrics_client = get_metrics_client()
                
                # Start client if not running
                if not self.metrics_client.is_running:
                    self.metrics_client.start()
                
                # Subscribe to metric updates
                for metric_name in ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']:
                    self.metrics_client.subscribe(
                        metric_name,
                        lambda result, name=metric_name: self._on_metric_update(name, result)
                    )
                
                self.is_connected = True
                self.connection_status_changed.emit(True)
                self.logger.info("✅ Connected to Custom Metrics Client")
            else:
                # Fallback mode with simulated data
                self.logger.warning("Running in simulation mode")
                self.is_connected = False
                self._start_simulation_mode()
                
        except Exception as e:
            self.logger.error(f"Failed to connect to metrics client: {e}")
            self.is_connected = False
            self.connection_status_changed.emit(False)
            self.error_occurred.emit(str(e))
    
    def _disconnect_from_client(self):
        """Disconnect from the Custom Metrics Client."""
        try:
            if self.metrics_client and MODULES_AVAILABLE:
                # Unsubscribe from updates
                for metric_name in ['GEX', 'DEX', 'OGL', 'DIX', 'SWAN']:
                    self.metrics_client.unsubscribe(
                        metric_name,
                        lambda result, name=metric_name: self._on_metric_update(name, result)
                    )
                
                self.is_connected = False
                self.connection_status_changed.emit(False)
                self.logger.info("Disconnected from Custom Metrics Client")
                
        except Exception as e:
            self.logger.error(f"Error disconnecting from client: {e}")
    
    @pyqtSlot()
    def check_connection(self):
        """Check and restore connection if needed."""
        if not self.is_connected and self.is_running:
            self.logger.info("Attempting to reconnect...")
            self._connect_to_client()
    
    # ==========================================================================
    # DATA RECEPTION AND PROCESSING
    # ==========================================================================
    
    def _on_metric_update(self, metric_name: str, result: MetricResult):
        """
        Handle metric update from the client.
        
        Args:
            metric_name: Name of the metric
            result: Metric calculation result
        """
        try:
            # Create display object
            display = MetricDisplay(
                name=metric_name,
                value=result.value,
                change=result.change,
                change_pct=result.change_pct,
                formatted_value=self._format_value(metric_name, result.value),
                formatted_change=self._format_change(metric_name, result.change, result.change_pct),
                color=self._get_color(metric_name, result.value, result.change),
                trend=self._get_trend(result.change),
                confidence=result.confidence,
                last_update=result.timestamp
            )
            
            # Update current metrics
            self.current_metrics[metric_name] = display
            
            # Add to history
            self.metric_history[metric_name].add(
                result.timestamp,
                result.value,
                result.change
            )
            
            # Emit update signal
            self.metric_updated.emit(metric_name, self._display_to_dict(display))
            
            self.update_count += 1
            
        except Exception as e:
            self.logger.error(f"Error processing metric update for {metric_name}: {e}")
            self.error_count += 1
    
    # ==========================================================================
    # DASHBOARD UPDATE
    # ==========================================================================
    
    @pyqtSlot()
    def update_dashboard(self):
        """Update dashboard with latest metric values."""
        try:
            if self.is_connected and self.metrics_client:
                # Get all metrics from client
                all_metrics = self.metrics_client.get_all_metrics()
                
                # Process each metric
                for metric_name, data in all_metrics.items():
                    if data:
                        # Create display object
                        display = MetricDisplay(
                            name=metric_name,
                            value=data['value'],
                            change=data['change'],
                            change_pct=data['change_pct'],
                            formatted_value=self._format_value(metric_name, data['value']),
                            formatted_change=self._format_change(
                                metric_name, data['change'], data['change_pct']
                            ),
                            color=self._get_color(metric_name, data['value'], data['change']),
                            trend=self._get_trend(data['change']),
                            confidence=data.get('confidence', 1.0),
                            last_update=data['timestamp']
                        )
                        
                        self.current_metrics[metric_name] = display
                
                # Emit update signal with all metrics
                self.all_metrics_updated.emit(self._get_all_displays())
                
            elif not self.is_connected:
                # Update with simulated data if not connected
                self._update_simulation()
                
        except Exception as e:
            self.logger.error(f"Error updating dashboard: {e}")
            self.error_occurred.emit(str(e))
    
    def update_dashboard_widget(self, widget_name: str, metric_name: str):
        """
        Update a specific dashboard widget with metric data.
        
        Args:
            widget_name: Name of the dashboard widget
            metric_name: Name of the metric to display
        """
        try:
            if metric_name not in self.current_metrics:
                return
            
            display = self.current_metrics[metric_name]
            
            # Update widget if dashboard reference exists
            if self.dashboard_widget:
                # Find the widget (this assumes the dashboard has a method to get widgets)
                widget = getattr(self.dashboard_widget, f'get_{widget_name}_widget', None)
                if widget and callable(widget):
                    metric_widget = widget()
                    if metric_widget:
                        self._update_metric_widget(metric_widget, display)
                        
        except Exception as e:
            self.logger.error(f"Error updating widget {widget_name}: {e}")
    
    def _update_metric_widget(self, widget: QWidget, display: MetricDisplay):
        """
        Update a metric widget with display data.
        
        Args:
            widget: The widget to update
            display: Display data for the metric
        """
        try:
            # Update value label
            if hasattr(widget, 'value_label'):
                widget.value_label.setText(display.formatted_value)
                widget.value_label.setStyleSheet(f"color: {display.color};")
            
            # Update change label
            if hasattr(widget, 'change_label'):
                widget.change_label.setText(display.formatted_change)
                change_color = COLORS['positive'] if display.change >= 0 else COLORS['negative']
                widget.change_label.setStyleSheet(f"color: {change_color};")
            
            # Update trend indicator
            if hasattr(widget, 'trend_indicator'):
                if display.trend == 'up':
                    widget.trend_indicator.setText('▲')
                    widget.trend_indicator.setStyleSheet(f"color: {COLORS['positive']};")
                elif display.trend == 'down':
                    widget.trend_indicator.setText('▼')
                    widget.trend_indicator.setStyleSheet(f"color: {COLORS['negative']};")
                else:
                    widget.trend_indicator.setText('─')
                    widget.trend_indicator.setStyleSheet(f"color: {COLORS['neutral']};")
                    
        except Exception as e:
            self.logger.error(f"Error updating metric widget: {e}")
    
    # ==========================================================================
    # FORMATTING AND DISPLAY
    # ==========================================================================
    
    def _format_value(self, metric_name: str, value: float) -> str:
        """
        Format metric value for display.
        
        Args:
            metric_name: Name of the metric
            value: Raw value
            
        Returns:
            Formatted string
        """
        fmt = METRIC_FORMATS.get(metric_name, {})
        prefix = fmt.get('prefix', '')
        suffix = fmt.get('suffix', '')
        decimals = fmt.get('decimals', 2)
        
        formatted = f"{prefix}{value:.{decimals}f}{suffix}"
        return formatted
    
    def _format_change(self, metric_name: str, change: float, change_pct: float) -> str:
        """
        Format metric change for display.
        
        Args:
            metric_name: Name of the metric
            change: Absolute change
            change_pct: Percentage change
            
        Returns:
            Formatted string
        """
        sign = '+' if change >= 0 else ''
        
        # Format based on metric type
        if metric_name in ['GEX', 'DEX']:
            return f"{sign}{change:.2f}B ({sign}{change_pct:.1f}%)"
        elif metric_name in ['DIX']:
            return f"{sign}{change:.1f}pp"  # percentage points
        else:
            return f"{sign}{change:.1f} ({sign}{change_pct:.1f}%)"
    
    def _get_color(self, metric_name: str, value: float, change: float) -> str:
        """
        Get display color based on metric value and thresholds.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            change: Metric change
            
        Returns:
            Color hex string
        """
        thresholds = COLOR_THRESHOLDS.get(metric_name, {})
        
        if metric_name == 'GEX':
            if value <= thresholds.get('extreme_negative', -5):
                return COLORS['extreme']
            elif value <= thresholds.get('negative', -2):
                return COLORS['negative']
            elif value >= thresholds.get('positive', 5):
                return COLORS['positive']
            else:
                return COLORS['neutral']
                
        elif metric_name == 'OGL':
            if value >= thresholds.get('extreme', 85):
                return COLORS['extreme']
            elif value >= thresholds.get('high', 70):
                return COLORS['warning']
            elif value >= thresholds.get('medium', 50):
                return COLORS['neutral']
            else:
                return COLORS['text']
                
        elif metric_name == 'SWAN':
            if value >= thresholds.get('extreme', 80):
                return COLORS['extreme']
            elif value >= thresholds.get('high', 60):
                return COLORS['negative']
            elif value >= thresholds.get('medium', 40):
                return COLORS['warning']
            else:
                return COLORS['positive']
                
        else:
            # Default color based on change
            if abs(change) < 0.1:
                return COLORS['text']
            elif change > 0:
                return COLORS['positive']
            else:
                return COLORS['negative']
    
    def _get_trend(self, change: float) -> str:
        """
        Get trend direction from change value.
        
        Args:
            change: Change value
            
        Returns:
            'up', 'down', or 'flat'
        """
        if abs(change) < 0.01:
            return 'flat'
        elif change > 0:
            return 'up'
        else:
            return 'down'
    
    def _display_to_dict(self, display: MetricDisplay) -> Dict[str, Any]:
        """
        Convert MetricDisplay to dictionary.
        
        Args:
            display: MetricDisplay object
            
        Returns:
            Dictionary representation
        """
        return {
            'name': display.name,
            'value': display.value,
            'change': display.change,
            'change_pct': display.change_pct,
            'formatted_value': display.formatted_value,
            'formatted_change': display.formatted_change,
            'color': display.color,
            'trend': display.trend,
            'confidence': display.confidence,
            'last_update': display.last_update.isoformat()
        }
    
    def _get_all_displays(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all metric displays as dictionary.
        
        Returns:
            Dictionary of all metric displays
        """
        return {
            name: self._display_to_dict(display)
            for name, display in self.current_metrics.items()
        }
    
    # ==========================================================================
    # SIMULATION MODE
    # ==========================================================================
    
    def _start_simulation_mode(self):
        """Start simulation mode for testing without live client."""
        self.logger.info("Starting simulation mode...")
        
        # Create simulation timer
        self.sim_timer = QTimer()
        self.sim_timer.timeout.connect(self._update_simulation)
        self.sim_timer.setInterval(5000)  # Update every 5 seconds
        self.sim_timer.start()
    
    def _update_simulation(self):
        """Update metrics with simulated data."""
        import random
        
        # Simulate GEX
        gex_value = random.uniform(-3, 8)
        self._update_simulated_metric('GEX', gex_value)
        
        # Simulate DEX
        dex_value = random.uniform(-15, 20)
        self._update_simulated_metric('DEX', dex_value)
        
        # Simulate OGL
        ogl_value = random.uniform(20, 80)
        self._update_simulated_metric('OGL', ogl_value)
        
        # Simulate DIX
        dix_value = random.uniform(38, 52)
        self._update_simulated_metric('DIX', dix_value)
        
        # Simulate SWAN
        swan_value = random.uniform(10, 60)
        self._update_simulated_metric('SWAN', swan_value)
        
        # Emit update signal
        self.all_metrics_updated.emit(self._get_all_displays())
    
    def _update_simulated_metric(self, metric_name: str, value: float):
        """
        Update a metric with simulated value.
        
        Args:
            metric_name: Name of the metric
            value: Simulated value
        """
        prev_display = self.current_metrics.get(metric_name)
        prev_value = prev_display.value if prev_display else 0
        
        change = value - prev_value
        change_pct = (change / prev_value * 100) if prev_value != 0 else 0
        
        display = MetricDisplay(
            name=metric_name,
            value=value,
            change=change,
            change_pct=change_pct,
            formatted_value=self._format_value(metric_name, value),
            formatted_change=self._format_change(metric_name, change, change_pct),
            color=self._get_color(metric_name, value, change),
            trend=self._get_trend(change),
            confidence=0.8,  # Lower confidence for simulated data
            last_update=datetime.now()
        )
        
        self.current_metrics[metric_name] = display
        
        # Add to history
        self.metric_history[metric_name].add(
            datetime.now(),
            value,
            change
        )
    
    # ==========================================================================
    # STATUS AND MONITORING
    # ==========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of the integration.
        
        Returns:
            Status dictionary
        """
        return {
            'is_running': self.is_running,
            'is_connected': self.is_connected,
            'update_count': self.update_count,
            'error_count': self.error_count,
            'error_rate': self.error_count / max(self.update_count, 1),
            'last_update': self.last_update_time.isoformat(),
            'current_metrics': {
                name: {
                    'value': display.value,
                    'formatted': display.formatted_value,
                    'trend': display.trend,
                    'last_update': display.last_update.isoformat()
                }
                for name, display in self.current_metrics.items()
            }
        }
    
    def get_metric_history(self, metric_name: str, 
                          points: int = 50) -> Optional[Dict[str, List]]:
        """
        Get historical data for a metric.
        
        Args:
            metric_name: Name of the metric
            points: Number of data points to return
            
        Returns:
            Dictionary with timestamps, values, and changes
        """
        if metric_name not in self.metric_history:
            return None
        
        history = self.metric_history[metric_name]
        
        # Get last N points
        n = min(points, len(history.timestamps))
        
        return {
            'timestamps': list(history.timestamps)[-n:],
            'values': list(history.values)[-n:],
            'changes': list(history.changes)[-n:]
        }

# ==============================================================================
# DASHBOARD WIDGET UPDATER
# ==============================================================================
class DashboardMetricsUpdater:
    """
    Helper class to update dashboard widgets with custom metrics.
    
    This class provides methods specifically designed to integrate with
    the existing SpyderG05_TradingDashboard structure.
    """
    
    def __init__(self, dashboard, integration: CustomMetricsIntegration):
        """
        Initialize the dashboard updater.
        
        Args:
            dashboard: Reference to SpyderG05_TradingDashboard
            integration: CustomMetricsIntegration instance
        """
        self.dashboard = dashboard
        self.integration = integration
        
        # Connect signals
        self.integration.all_metrics_updated.connect(self.update_all_widgets)
        self.integration.metric_updated.connect(self.update_single_widget)
        
        # Widget mapping (maps metric names to dashboard widget attributes)
        self.widget_mapping = {
            'GEX': 'gex_widget',
            'DEX': 'dex_widget',
            'OGL': 'ogl_widget',
            'DIX': 'dix_widget',
            'SWAN': 'swan_widget'
        }
    
    @pyqtSlot(dict)
    def update_all_widgets(self, metrics_data: Dict[str, Dict]):
        """
        Update all metric widgets in the dashboard.
        
        Args:
            metrics_data: Dictionary of all metric data
        """
        for metric_name, data in metrics_data.items():
            self._update_widget(metric_name, data)
    
    @pyqtSlot(str, dict)
    def update_single_widget(self, metric_name: str, data: Dict):
        """
        Update a single metric widget.
        
        Args:
            metric_name: Name of the metric
            data: Metric display data
        """
        self._update_widget(metric_name, data)
    
    def _update_widget(self, metric_name: str, data: Dict):
        """
        Update a specific widget with metric data.
        
        Args:
            metric_name: Name of the metric
            data: Display data
        """
        try:
            # Get widget attribute name
            widget_attr = self.widget_mapping.get(metric_name)
            if not widget_attr:
                return
            
            # Get widget from dashboard
            if hasattr(self.dashboard, widget_attr):
                widget = getattr(self.dashboard, widget_attr)
                if widget:
                    # Update widget display
                    self._apply_widget_update(widget, data)
                    
        except Exception as e:
            print(f"Error updating {metric_name} widget: {e}")
    
    def _apply_widget_update(self, widget: QWidget, data: Dict):
        """
        Apply update to a widget.
        
        Args:
            widget: Widget to update
            data: Display data
        """
        # Update based on widget structure in SpyderG05
        if hasattr(widget, 'update_data'):
            # If widget has update_data method, use it
            widget.update_data(data)
        else:
            # Manual update for custom indicator widgets
            if hasattr(widget, 'price_label'):
                widget.price_label.setText(data['formatted_value'])
                widget.price_label.setStyleSheet(f"color: {data['color']};")
            
            if hasattr(widget, 'change_label'):
                widget.change_label.setText(data['formatted_change'])
                change_color = COLORS['positive'] if data['change'] >= 0 else COLORS['negative']
                widget.change_label.setStyleSheet(f"color: {change_color};")

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================
def create_metrics_integration(dashboard=None) -> CustomMetricsIntegration:
    """
    Create a Custom Metrics Integration instance.
    
    Args:
        dashboard: Optional dashboard widget reference
        
    Returns:
        CustomMetricsIntegration instance
    """
    return CustomMetricsIntegration(dashboard)

def setup_dashboard_integration(dashboard) -> DashboardMetricsUpdater:
    """
    Setup complete integration with dashboard.
    
    Args:
        dashboard: SpyderG05_TradingDashboard instance
        
    Returns:
        DashboardMetricsUpdater instance
    """
    integration = create_metrics_integration(dashboard)
    updater = DashboardMetricsUpdater(dashboard, integration)
    integration.start()
    return updater

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main execution for testing."""
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 80)
    print("🚀 SPYDER G10 - Custom Metrics Integration")
    print("=" * 80)
    
    # Create Qt application
    app = QApplication(sys.argv)
    
    # Create main window for testing
    window = QMainWindow()
    window.setWindowTitle("Custom Metrics Integration Test")
    window.setGeometry(100, 100, 800, 600)
    
    # Create integration
    integration = create_metrics_integration()
    
    # Connect status signals
    integration.connection_status_changed.connect(
        lambda connected: print(f"📡 Connection status: {'Connected' if connected else 'Disconnected'}")
    )
    
    integration.error_occurred.connect(
        lambda error: print(f"❌ Error: {error}")
    )
    
    integration.all_metrics_updated.connect(
        lambda metrics: print(f"📊 Metrics updated: {list(metrics.keys())}")
    )
    
    # Start integration
    integration.start()
    
    print("\n✅ Integration started")
    print("📊 Monitoring custom metrics...")
    print("   - GEX: Gamma Exposure")
    print("   - DEX: Delta Exposure")
    print("   - OGL: Options Greeks Level")
    print("   - DIX: Dark Index")
    print("   - SWAN: Black Swan Indicator")
    
    # Create simple display widget
    from PyQt6.QtWidgets import QTextEdit
    display = QTextEdit()
    display.setReadOnly(True)
    window.setCentralWidget(display)
    
    # Update display with metrics
    def update_display(metrics):
        text = "CUSTOM METRICS UPDATE\n" + "=" * 40 + "\n"
        for name, data in metrics.items():
            text += f"\n{name}:\n"
            text += f"  Value: {data['formatted_value']}\n"
            text += f"  Change: {data['formatted_change']}\n"
            text += f"  Trend: {data['trend']}\n"
            text += f"  Color: {data['color']}\n"
        display.setText(text)
    
    integration.all_metrics_updated.connect(update_display)
    
    # Show window
    window.show()
    
    print("\n⏳ Running... Close window to exit")
    
    # Run application
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
