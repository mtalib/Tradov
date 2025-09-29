#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System

Spyder Version: 1.0
Module: SpyderB16_GatewayIntegration.py
Group: B (Broker/Connection)
Purpose: Integration layer for Gateway Config, Watchdog, and Prometheus Metrics
Author: Mohamed Talib
Date Created: 2025-08-03
Last Updated: 2025-08-03 Time: 14:00:00

Description:
    Integrates SpyderB13_GatewayConfig, SpyderB14_MultiClientWatchdog, and
    SpyderB15_PrometheusMetrics into a unified interface for the PySide6 dashboard.
    Manages client status updates, color coding, tooltips, system log integration,
    and provides clean data structures for dashboard consumption.
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import threading
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
import queue
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import pytz
from PySide6.QtCore import QObject, Signal, QTimer, Qt
from PySide6.QtGui import QColor

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import (
        GatewayConfig, GatewayManager, ClientConfig, 
        get_client_allocation, ClientPurpose
    )
    from SpyderB_Broker.SpyderB14_MultiClientWatchdog import (
        MultiClientWatchdog, ClientHealth, SystemHealth, 
        HealthStatus
    )
    from SpyderB_Broker.SpyderB15_PrometheusMetrics import (
        PrometheusMetricsCollector, ClientMetrics, TradingMetrics
    )
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import Spyder modules: {e}")
    # Create fallbacks
    MultiClientWatchdog = None
    PrometheusMetricsCollector = None
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Update intervals (milliseconds)
DASHBOARD_UPDATE_INTERVAL = 10000  # 10 seconds
HEALTH_CHECK_INTERVAL = 30000      # 30 seconds
METRICS_UPDATE_INTERVAL = 5000     # 5 seconds

# Latency thresholds (milliseconds)
LATENCY_EXCELLENT = 10
LATENCY_GOOD = 25
LATENCY_WARNING = 50
LATENCY_CRITICAL = 100

# Color codes for dashboard (matching existing theme)
COLOR_GREEN = "#00FF00"    # Healthy
COLOR_YELLOW = "#FFD700"   # Warning
COLOR_RED = "#FF0000"      # Critical
COLOR_GRAY = "#808080"     # Unknown/Disabled

# ==============================================================================
# ENUMS
# ==============================================================================
class ClientStatusLevel(Enum):
    """Client status levels for dashboard display"""
    HEALTHY = "●"      # Green dot
    WARNING = "⚠"      # Yellow warning
    CRITICAL = "✗"     # Red X
    UNKNOWN = "○"      # Gray circle

class SystemComponent(Enum):
    """System health components"""
    RISK_MANAGER = "RISK MANAGER"
    MARKET_DATA = "MARKET DATA"
    STRATEGY_ENGINE = "STRATEGY ENGINE"
    ML_MODELS = "ML MODELS"
    DATABASE = "DATABASE"

# ==============================================================================
# DATACLASSES
# ==============================================================================
@dataclass
class ClientDisplayInfo:
    """Information for displaying a client in the dashboard"""
    client_id: int
    name: str
    purpose: str
    status_level: ClientStatusLevel
    status_color: str
    connected: bool
    latency_ms: Optional[float]
    tooltip_data: Dict[str, Any]
    last_update: datetime

@dataclass
class DashboardData:
    """Complete data structure for dashboard update"""
    # System Health Panel
    system_components: Dict[SystemComponent, bool]
    system_health_score: int
    
    # Prometheus Metrics Panel
    client_display_info: Dict[int, ClientDisplayInfo]
    active_clients: int
    total_clients: int
    
    # Bottom Status Bar
    memory_percent: float
    cpu_percent: float
    api_calls_per_sec: int
    
    # System Log entries
    log_entries: List[str]
    
    # Timestamp
    timestamp: datetime

# ==============================================================================
# GATEWAY INTEGRATION MANAGER
# ==============================================================================
class GatewayIntegrationManager(QObject):
    """
    Central integration manager for multi-client IB Gateway monitoring.
    Coordinates between Config, Watchdog, and Metrics modules.
    """
    
    # PySide6 signals for dashboard updates
    dashboard_update = Signal(dict)  # Emits dashboard data
    system_log_update = Signal(str)  # Emits log entries
    alert_signal = Signal(str, str)  # Emits (severity, message)
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        """
        Initialize Gateway Integration Manager.
        
        Args:
            config: Gateway configuration (creates default if None)
        """
        super().__init__()
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
        
        # Initialize components
        self.config = config or GatewayConfig()
        self.gateway_manager = GatewayManager(self.config)
        self.watchdog = MultiClientWatchdog(self.config) if MultiClientWatchdog else None
        self.metrics_manager = PrometheusMetricsCollector() if PrometheusMetricsCollector else None
        
        # Client configurations
        self.client_configs = get_client_allocation()
        
        # Eastern timezone
        self.eastern_tz = pytz.timezone('US/Eastern')
        
        # Dashboard data cache
        self.dashboard_data = self._initialize_dashboard_data()
        
        # System log buffer
        self.log_buffer = deque(maxlen=100)
        
        # Update timers
        self.dashboard_timer = QTimer()
        self.dashboard_timer.timeout.connect(self.update_dashboard)
        
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.perform_health_check)
        
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_metrics)
        
        # Asyncio event loop for watchdog
        self.loop_thread = None
        self.event_loop = None
        
        self.logger.info("GatewayIntegrationManager initialized")
    
    # ==========================================================================
    # INITIALIZATION
    # ==========================================================================
    def _initialize_dashboard_data(self) -> DashboardData:
        """Initialize dashboard data structure"""
        # Initialize system components (all healthy by default)
        system_components = {
            SystemComponent.RISK_MANAGER: True,
            SystemComponent.MARKET_DATA: True,
            SystemComponent.STRATEGY_ENGINE: True,
            SystemComponent.ML_MODELS: True,
            SystemComponent.DATABASE: True
        }
        
        # Initialize client display info
        client_display_info = {}
        for client_id, config in self.client_configs.items():
            client_display_info[client_id] = ClientDisplayInfo(
                client_id=client_id,
                name=f"CLIENT {client_id}",
                purpose=self._get_client_short_name(client_id),
                status_level=ClientStatusLevel.UNKNOWN,
                status_color=COLOR_GRAY,
                connected=False,
                latency_ms=None,
                tooltip_data={},
                last_update=datetime.now(self.eastern_tz)
            )
        
        return DashboardData(
            system_components=system_components,
            system_health_score=100,
            client_display_info=client_display_info,
            active_clients=0,
            total_clients=len(self.client_configs),
            memory_percent=0.0,
            cpu_percent=0.0,
            api_calls_per_sec=0,
            log_entries=[],
            timestamp=datetime.now(self.eastern_tz)
        )
    
    def _get_client_short_name(self, client_id: int) -> str:
        """Get short display name for client"""
        names = {
            0: "Admin",
            1: "Orders",
            2: "Core",
            3: "Options",
            4: "Volatility",
            5: "Internals",
            6: "Major ETFs",
            7: "Extended",
            8: "Sector ETFs"
        }
        return names.get(client_id, f"Client {client_id}")
    
    # ==========================================================================
    # STARTUP & SHUTDOWN
    # ==========================================================================
    def start(self):
        """Start all monitoring systems"""
        try:
            self.logger.info("Starting Gateway Integration Manager...")
            
            # Start asyncio event loop in separate thread
            self.loop_thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self.loop_thread.start()
            
            # Wait for loop to start
            time.sleep(1)
            
            # Initialize watchdog clients
            if self.watchdog and self.event_loop:
                future = asyncio.run_coroutine_threadsafe(
                    self.watchdog.initialize_all_clients(),
                    self.event_loop
                )
                success = future.result(timeout=60)
                self.logger.info("Watchdog clients initialized: %s", success)
                
                # Start monitoring
                asyncio.run_coroutine_threadsafe(
                    self.watchdog.start_monitoring(),
                    self.event_loop
                )
            
            # Start metrics server
            if self.metrics_manager:
                self.metrics_manager.start_metrics_server()
            
            # Start update timers
            self.dashboard_timer.start(DASHBOARD_UPDATE_INTERVAL)
            self.health_timer.start(HEALTH_CHECK_INTERVAL)
            self.metrics_timer.start(METRICS_UPDATE_INTERVAL)
            
            # Log startup
            self.add_system_log("INFO", "Gateway Integration Manager started successfully")
            
            self.logger.info("All systems started")
            
        except Exception as e:
            self.logger.error("Failed to start: %s", e)
            self.add_system_log("ERROR", f"Startup failed: {e}")
    
    def stop(self):
        """Stop all monitoring systems"""
        try:
            self.logger.info("Stopping Gateway Integration Manager...")
            
            # Stop timers
            self.dashboard_timer.stop()
            self.health_timer.stop()
            self.metrics_timer.stop()
            
            # Stop watchdog
            if self.watchdog and self.event_loop:
                asyncio.run_coroutine_threadsafe(
                    self.watchdog.stop_monitoring(),
                    self.event_loop
                )
            
            # Stop metrics server
            if self.metrics_manager:
                self.metrics_manager.stop_metrics_server()
            
            # Stop event loop
            if self.event_loop:
                self.event_loop.call_soon_threadsafe(self.event_loop.stop)
            
            self.add_system_log("INFO", "Gateway Integration Manager stopped")
            self.logger.info("All systems stopped")
            
        except Exception as e:
            self.logger.error("Error during shutdown: %s", e)
    
    def _run_event_loop(self):
        """Run asyncio event loop in separate thread"""
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_forever()
    
    # ==========================================================================
    # HEALTH MONITORING
    # ==========================================================================
    def perform_health_check(self):
        """Perform comprehensive health check"""
        if not self.watchdog or not self.event_loop:
            return
        
        try:
            # Run health check asynchronously
            future = asyncio.run_coroutine_threadsafe(
                self.watchdog.check_all_clients(),
                self.event_loop
            )
            system_health = future.result(timeout=10)
            
            # Process health results
            self._process_health_results(system_health)
            
        except Exception as e:
            self.logger.error("Health check failed: %s", e)
    
    def _process_health_results(self, system_health: SystemHealth):
        """Process health check results and update dashboard data"""
        # Update client statuses
        for client_id, health in system_health.client_health.items():
            self._update_client_status(client_id, health)
        
        # Update system metrics
        self.dashboard_data.active_clients = system_health.active_clients
        self.dashboard_data.memory_percent = system_health.memory_usage_percent
        self.dashboard_data.cpu_percent = system_health.cpu_usage_percent
        
        # Calculate overall system health
        self.dashboard_data.system_health_score = self._calculate_system_score(system_health)
        
        # Process warnings
        for warning in system_health.warnings:
            self.add_system_log("WARNING", warning)
        
        # Check for critical alerts
        if system_health.critical_clients:
            for client_id in system_health.critical_clients:
                client_name = self._get_client_short_name(client_id)
                self.add_system_log("CRITICAL", f"CLIENT {client_id} ({client_name}) in critical state")
                self.alert_signal.emit("CRITICAL", f"Client {client_id} needs attention")
    
    def _update_client_status(self, client_id: int, health: ClientHealth):
        """Update individual client status"""
        if client_id not in self.dashboard_data.client_display_info:
            return
        
        display_info = self.dashboard_data.client_display_info[client_id]
        
        # Update connection status
        display_info.connected = health.connected
        display_info.latency_ms = health.latency_ms
        display_info.last_update = datetime.now(self.eastern_tz)
        
        # Determine status level and color
        if not health.connected:
            display_info.status_level = ClientStatusLevel.CRITICAL
            display_info.status_color = COLOR_RED
        elif health.latency_ms is None:
            display_info.status_level = ClientStatusLevel.UNKNOWN
            display_info.status_color = COLOR_GRAY
        elif health.latency_ms < LATENCY_GOOD:
            display_info.status_level = ClientStatusLevel.HEALTHY
            display_info.status_color = COLOR_GREEN
        elif health.latency_ms < LATENCY_WARNING:
            display_info.status_level = ClientStatusLevel.WARNING
            display_info.status_color = COLOR_YELLOW
        else:
            display_info.status_level = ClientStatusLevel.CRITICAL
            display_info.status_color = COLOR_RED
        
        # Update tooltip data
        display_info.tooltip_data = self._generate_tooltip_data(client_id, health)
    
    def _generate_tooltip_data(self, client_id: int, health: ClientHealth) -> Dict[str, Any]:
        """Generate tooltip data for a client"""
        config = self.client_configs.get(client_id)
        
        tooltip = {
            'title': f"CLIENT {client_id}: {config.purpose.value if config else 'Unknown'}",
            'status': 'Connected' if health.connected else 'Disconnected',
            'priority': config.priority if config else 'Unknown',
            'latency_avg': f"{health.latency_ms:.1f}ms" if health.latency_ms else 'N/A',
            'latency_max': 'N/A',  # Would need historical data
            'rate_limit': f"{config.rate_limit} req/s" if config else 'N/A',
            'health_score': health.score,
            'errors': health.error_countt,
            'last_update': health.timestamp.strftime("%H:%M:%S")
        }
        
        # Add metrics if available
        if self.metrics_manager:
            client_metrics = self.metrics_manager.client_metrics.get(str(client_id))
            if client_metrics:
                tooltip.update({
                    'orders_today': client_metrics.orders_submitted,
                    'fills': client_metrics.orders_filled,
                    'rejects': client_metrics.orders_rejected,
                    'api_calls': client_metrics.api_calls_made,
                    'data_points': client_metrics.data_points_received
                })
        
        return tooltip
    
    def _calculate_system_score(self, system_health: SystemHealth) -> int:
        """Calculate overall system health score"""
        if not system_health.client_health:
            return 0
        
        # Weight critical clients more heavily
        critical_clients = [0, 1, 2, 3]
        total_weight = 0
        weighted_score = 0
        
        for client_id, health in system_health.client_health.items():
            weight = 2 if client_id in critical_clients else 1
            weighted_score += health.score * weight
            total_weight += weight
        
        return int(weighted_score / total_weight) if total_weight > 0 else 0
    
    # ==========================================================================
    # METRICS UPDATES
    # ==========================================================================
    def update_metrics(self):
        """Update Prometheus metrics"""
        if not self.metrics_manager:
            return
        
        try:
            # Prepare metrics data
            metrics_data = self._prepare_metrics_data()
            
            # Batch update metrics
            self.metrics_manager.batch_update_metrics(metrics_data)
            
            # Get API calls per second (example calculation)
            total_api_calls = sum(
                m.api_calls_made for m in self.metrics_manager.client_metrics.values()
            )
            self.dashboard_data.api_calls_per_sec = int(total_api_calls / 10)  # Rough estimate
            
        except Exception as e:
            self.logger.error("Metrics update failed: %s", e)
    
    def _prepare_metrics_data(self) -> Dict[str, Any]:
        """Prepare metrics data for batch update"""
        metrics_data = {
            'clients': {},
            'trading': {},
            'system': {}
        }
        
        # Client metrics
        for client_id, display_info in self.dashboard_data.client_display_info.items():
            metrics_data['clients'][str(client_id)] = {
                'connected': display_info.connected,
                'latency': display_info.latency_ms / 1000 if display_info.latency_ms else None,
                'purpose': display_info.purpose
            }
        
        # System metrics
        metrics_data['system'] = {
            'health_score': self.dashboard_data.system_health_score,
            'memory_usage': {str(i): self.dashboard_data.memory_percent for i in range(9)},
            'cpu_usage': {str(i): self.dashboard_data.cpu_percent for i in range(9)}
        }
        
        return metrics_data
    
    # ==========================================================================
    # DASHBOARD UPDATES
    # ==========================================================================
    def update_dashboard(self):
        """Main dashboard update method"""
        try:
            # Update timestamp
            self.dashboard_data.timestamp = datetime.now(self.eastern_tz)
            
            # Convert dashboard data to dictionary
            dashboard_dict = self._dashboard_data_to_dict()
            
            # Emit update signal
            self.dashboard_update.emit(dashboard_dict)
            
        except Exception as e:
            self.logger.error("Dashboard update failed: %s", e)
    
    def _dashboard_data_to_dict(self) -> Dict[str, Any]:
        """Convert dashboard data to dictionary for signal emission"""
        return {
            'system_health': {
                component.value: status
                for component, status in self.dashboard_data.system_components.items()
            },
            'system_health_score': self.dashboard_data.system_health_score,
            'clients': {
                client_id: {
                    'name': info.name,
                    'purpose': info.purpose,
                    'status_level': info.status_level.value,
                    'status_color': info.status_color,
                    'connected': info.connected,
                    'tooltip': info.tooltip_data
                }
                for client_id, info in self.dashboard_data.client_display_info.items()
            },
            'stats': {
                'active_clients': self.dashboard_data.active_clients,
                'total_clients': self.dashboard_data.total_clients,
                'memory_percent': self.dashboard_data.memory_percent,
                'cpu_percent': self.dashboard_data.cpu_percent,
                'api_calls_per_sec': self.dashboard_data.api_calls_per_sec
            },
            'timestamp': self.dashboard_data.timestamp.isoformat()
        }
    
    # ==========================================================================
    # SYSTEM LOG
    # ==========================================================================
    def add_system_log(self, level: str, message: str):
        """Add entry to system log"""
        timestamp = datetime.now(self.eastern_tz).strftime("%d%b%y %H:%M:%S").upper()
        
        # Determine symbol based on level
        symbols = {
            'INFO': '●',
            'WARNING': '⚠',
            'ERROR': '✗',
            'CRITICAL': '✗',
            'SUCCESS': '✓'
        }
        symbol = symbols.get(level, '●')
        
        # Format log entry
        log_entry = f"{timestamp} - {symbol} {message}"
        
        # Add to buffer
        self.log_buffer.append(log_entry)
        self.dashboard_data.log_entries = list(self.log_buffer)
        
        # Emit to system log
        self.system_log_update.emit(log_entry)
        
        # Also log internally
        self.logger.info("System Log: %s", message)
    
    # ==========================================================================
    # PUBLIC METHODS FOR DASHBOARD
    # ==========================================================================
    def get_client_display_data(self) -> List[Tuple[int, str, str, str]]:
        """
        Get client display data for dashboard.
        
        Returns:
            List of tuples: (client_id, display_text, status_symbol, color)
        """
        result = []
        for client_id in range(9):
            info = self.dashboard_data.client_display_info.get(client_id)
            if info:
                display_text = f"{info.name}: {info.purpose}"
                result.append((
                    client_id,
                    display_text,
                    info.status_level.value,
                    info.status_color
                ))
        return result
    
    def get_system_health_display(self) -> List[Tuple[str, str, str]]:
        """
        Get system health display data.
        
        Returns:
            List of tuples: (component_name, status_symbol, color)
        """
        result = []
        for component, is_healthy in self.dashboard_data.system_components.items():
            symbol = "●" if is_healthy else "✗"
            color = COLOR_GREEN if is_healthy else COLOR_RED
            result.append((component.value, symbol, color))
        return result
    
    def get_status_bar_text(self) -> str:
        """Get formatted text for status bar"""
        return (f"System Health: {self.dashboard_data.system_health_score}/100 | "
                f"Active Clients: {self.dashboard_data.active_clients}/{self.dashboard_data.total_clients} | "
                f"Memory: {self.dashboard_data.memory_percent:.0f}% | "
                f"CPU: {self.dashboard_data.cpu_percent:.0f}% | "
                f"API Calls/Sec: {self.dashboard_data.api_calls_per_sec}")
    
    def reconnect_client(self, client_id: int):
        """Manually reconnect a specific client"""
        if self.watchdog and self.event_loop:
            self.add_system_log("INFO", f"Manual reconnection requested for Client {client_id}")
            asyncio.run_coroutine_threadsafe(
                self.watchdog.attempt_recovery(client_id),
                self.event_loop
            )
    
    def export_health_report(self, filepath: Path):
        """Export current health report"""
        report = {
            'timestamp': self.dashboard_data.timestamp.isoformat(),
            'system_health_score': self.dashboard_data.system_health_score,
            'clients': {},
            'system_metrics': {
                'memory_percent': self.dashboard_data.memory_percent,
                'cpu_percent': self.dashboard_data.cpu_percent,
                'api_calls_per_sec': self.dashboard_data.api_calls_per_sec
            }
        }
        
        for client_id, info in self.dashboard_data.client_display_info.items():
            report['clients'][client_id] = {
                'name': info.purpose,
                'connected': info.connected,
                'latency_ms': info.latency_ms,
                'status': info.status_level.name,
                'health_data': info.tooltip_data
            }
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.add_system_log("INFO", f"Health report exported to {filepath}")

# ==============================================================================
# DASHBOARD INTEGRATION HELPER
# ==============================================================================
class DashboardIntegrationHelper:
    """Helper class for easy PySide6 dashboard integration"""
    
    def __init__(self, integration_manager: GatewayIntegrationManager):
        """
        Initialize dashboard integration helper.
        
        Args:
            integration_manager: GatewayIntegrationManager instance
        """
        self.manager = integration_manager
    
    def connect_to_dashboard(self, dashboard_widget):
        """
        Connect integration manager to dashboard widget.
        
        Args:
            dashboard_widget: PySide6 dashboard widget with update methods
        """
        # Connect signals
        self.manager.dashboard_update.connect(dashboard_widget.on_dashboard_update)
        self.manager.system_log_update.connect(dashboard_widget.on_system_log)
        self.manager.alert_signal.connect(dashboard_widget.on_alert)
    
    def format_client_label(self, client_id: int) -> str:
        """Format client label for display"""
        info = self.manager.dashboard_data.client_display_info.get(client_id)
        if info:
            return f"{info.status_level.value} {info.name}: {info.purpose}"
        return f"CLIENT {client_id}: Unknown"
    
    def get_client_color(self, client_id: int) -> str:
        """Get client status color"""
        info = self.manager.dashboard_data.client_display_info.get(client_id)
        return info.status_color if info else COLOR_GRAY

# ==============================================================================
# MODULE TEST
# ==============================================================================
def test_integration():
    """Test the Gateway Integration Manager"""
    print("Testing Gateway Integration Manager...")
    
    # Create integration manager
    manager = GatewayIntegrationManager()
    
    print("\n1. Starting systems...")
    manager.start()
    
    # Wait for initialization
    time.sleep(3)
    
    print("\n2. Getting dashboard data...")
    
    # Get client display data
    client_data = manager.get_client_display_data()
    print("\nClient Status:")
    for client_id, text, symbol, color in client_data:
        print(f"  {symbol} {text}")
    
    # Get system health
    system_health = manager.get_system_health_display()
    print("\nSystem Health:")
    for component, symbol, color in system_health:
        print(f"  {symbol} {component}")
    
    # Get status bar
    status_text = manager.get_status_bar_text()
    print(f"\nStatus Bar: {status_text}")
    
    # Test log entries
    print("\n3. Testing system log...")
    manager.add_system_log("INFO", "Test information message")
    manager.add_system_log("WARNING", "Test warning message")
    manager.add_system_log("ERROR", "Test error message")
    
    print("\nRecent Log Entries:")
    for entry in list(manager.log_buffer)[-5:]:
        print(f"  {entry}")
    
    # Export report
    print("\n4. Exporting health report...")
    report_path = Path("integration_test_report.json")
    manager.export_health_report(report_path)
    print(f"  Report saved to {report_path}")
    
    # Simulate running for a bit
    print("\n5. Running for 30 seconds...")
    print("  (Check metrics at http://localhost:8000/metrics)")
    time.sleep(30)
    
    # Stop
    print("\n6. Stopping systems...")
    manager.stop()
    
    print("\n✓ Integration test completed")

if __name__ == "__main__":
    test_integration()