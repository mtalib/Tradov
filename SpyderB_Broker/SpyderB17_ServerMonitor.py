#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB17_ServerMonitor.py
Purpose: IBKR Server Connection Monitoring and Validation
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-27 Time: 14:30:00  

Module Description:
    Monitors IBKR Gateway server connections in real-time, validates routing to 
    the assigned Zurich server (zdc1.ibllc.com), and provides server status tracking
    for the dashboard. Integrates with the existing Spyder architecture and provides
    PyQt6 widgets for real-time server status display with color-coded indicators.

Key Features:
    - Real-time server connection monitoring
    - Log file analysis for connection tracking  
    - Latency measurement to target servers
    - DNS validation and routing verification
    - PyQt6 dashboard integration
    - Auto-detection of server redirects
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
import pytz
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PySide6.QtCore import QTimer, QThread, Signal, Qt, QObject
from PySide6.QtGui import QColor, QFont, QIcon

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig, GatewayManager
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import Spyder utilities: {e}")
    # Fallback to standard logging
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS AND ENUMS
# ==============================================================================

# IBKR Server Endpoints
IBKR_SERVERS = {
    'zurich': 'zdc1.ibllc.com',
    'chicago': 'cdc1.ibllc.com', 
    'newark': 'ndc1.ibllc.com',
    'london': 'ldc1.ibllc.com',
    'sydney': 'sdc1.ibllc.com',
    'hongkong': 'hdc1.ibllc.com'
}

# Log directory path (standard IB Gateway location)
DEFAULT_LOG_DIR = Path.home() / "Jts" / "logs"

# DNS Resolution IPs for forcing routing
SERVER_IPS = {
    'zdc1.ibllc.com': '185.179.200.100',  # Zurich
    'cdc1.ibllc.com': '64.190.197.40',    # Chicago  
    'ndc1.ibllc.com': '64.190.197.40',    # Newark
}

class ServerStatus(Enum):
    """Server connection status"""
    CONNECTED_ZURICH = "connected_zurich"
    CONNECTED_OTHER = "connected_other" 
    CONNECTING = "connecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    UNKNOWN = "unknown"

class ConnectionHealth(Enum):
    """Connection health status"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ServerInfo:
    """Server connection information"""
    server_name: str
    server_ip: str
    connection_time: datetime
    latency_ms: float = -1.0
    port: int = 0
    ssl_enabled: bool = False
    session_id: str = ""
    status: ServerStatus = ServerStatus.UNKNOWN

@dataclass  
class ServerMetrics:
    """Server performance metrics"""
    current_server: str
    target_server: str = "zdc1.ibllc.com"
    latency_ms: float = -1.0
    connection_uptime: timedelta = field(default_factory=lambda: timedelta())
    reconnect_count: int = 0
    redirect_count: int = 0
    last_redirect_time: Optional[datetime] = None
    health_score: float = 100.0
    health_status: ConnectionHealth = ConnectionHealth.EXCELLENT

# ==============================================================================
# SERVER MONITOR WORKER THREAD
# ==============================================================================

class ServerMonitorWorker(QThread):
    """Background thread for monitoring server status"""
    
    # Qt signals for UI updates
    statusUpdated = Signal(dict)  # Server status update
    metricsUpdated = Signal(dict)  # Performance metrics
    errorOccurred = Signal(str)   # Error notifications
    
    def __init__(self, config: GatewayConfig):
        super().__init__()
        self.config = config
        self.running = False
        self.log_dir = DEFAULT_LOG_DIR
        self.metrics_history = deque(maxlen=100)
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            
    def run(self):
        """Main worker thread loop"""
        self.running = True
        self.logger.info("Server monitor worker started")
        
        while self.running:
            try:
                # Get current server status
                server_info = self._get_current_server()
                metrics = self._calculate_metrics(server_info)
                
                # Emit updates to UI
                self.statusUpdated.emit(self._format_status_update(server_info))
                self.metricsUpdated.emit(self._format_metrics_update(metrics))
                
                # Store metrics for history
                self.metrics_history.append(metrics)
                
                # Sleep for update interval
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Server monitor error: {e}")
                self.errorOccurred.emit(str(e))
                time.sleep(10)  # Longer sleep on error
                
    def stop(self):
        """Stop the worker thread"""
        self.running = False
        self.wait()
        
    def _get_current_server(self) -> Optional[ServerInfo]:
        """Extract current server info from IB Gateway logs"""
        try:
            latest_log = self._find_latest_log()
            if not latest_log:
                return None
                
            server_info = self._parse_server_from_log(latest_log)
            if server_info:
                # Measure latency
                latency = self._ping_server(server_info.server_name)
                server_info.latency_ms = latency
                
            return server_info
            
        except Exception as e:
            self.logger.error(f"Error getting server info: {e}")
            return None
            
    def _find_latest_log(self) -> Optional[Path]:
        """Find the most recent IB Gateway log file"""
        try:
            if not self.log_dir.exists():
                return None
                
            log_files = list(self.log_dir.glob("*.txt"))
            if not log_files:
                return None
                
            # Return most recent file
            return max(log_files, key=lambda f: f.stat().st_mtime)
            
        except Exception as e:
            self.logger.error(f"Error finding log file: {e}")
            return None
            
    def _parse_server_from_log(self, log_path: Path) -> Optional[ServerInfo]:
        """Parse server connection info from log file"""
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            # Look for connection messages from end of file backwards
            for line in reversed(lines[-200:]):  # Check last 200 lines
                # Look for "Connected to" messages
                if "Connected to" in line:
                    match = re.search(r'Connected to (\S+):(\d+)(?:\s*\(SSL\))?/([0-9.]+)', line)
                    if match:
                        server_name = match.group(1)
                        port = int(match.group(2))
                        server_ip = match.group(3)
                        ssl_enabled = "(SSL)" in line
                        
                        # Extract timestamp
                        time_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                        connection_time = datetime.now()
                        if time_match:
                            try:
                                connection_time = datetime.strptime(time_match.group(1), '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                pass
                                
                        return ServerInfo(
                            server_name=server_name,
                            server_ip=server_ip,
                            connection_time=connection_time,
                            port=port,
                            ssl_enabled=ssl_enabled,
                            status=self._determine_status(server_name)
                        )
                        
        except Exception as e:
            self.logger.error(f"Error parsing log file: {e}")
            
        return None
        
    def _determine_status(self, server_name: str) -> ServerStatus:
        """Determine connection status based on server name"""
        if server_name == IBKR_SERVERS['zurich']:
            return ServerStatus.CONNECTED_ZURICH
        elif server_name in IBKR_SERVERS.values():
            return ServerStatus.CONNECTED_OTHER
        else:
            return ServerStatus.UNKNOWN
            
    def _ping_server(self, server_name: str) -> float:
        """Measure latency to server"""
        try:
            result = subprocess.run(
                ['ping', '-c', '3', server_name], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                # Extract average latency
                match = re.search(r'avg = ([\d.]+)', result.stdout)
                if match:
                    return float(match.group(1))
                    
        except Exception as e:
            self.logger.debug(f"Ping failed for {server_name}: {e}")
            
        return -1.0
        
    def _calculate_metrics(self, server_info: Optional[ServerInfo]) -> ServerMetrics:
        """Calculate performance metrics"""
        if not server_info:
            return ServerMetrics(
                current_server="Unknown",
                health_status=ConnectionHealth.CRITICAL
            )
            
        # Calculate health score based on latency and server
        health_score = 100.0
        health_status = ConnectionHealth.EXCELLENT
        
        if server_info.latency_ms > 0:
            if server_info.latency_ms > 200:
                health_score -= 30
                health_status = ConnectionHealth.POOR
            elif server_info.latency_ms > 100:
                health_score -= 15
                health_status = ConnectionHealth.FAIR
            elif server_info.latency_ms > 50:
                health_score -= 5
                health_status = ConnectionHealth.GOOD
                
        # Penalty for non-Zurich servers
        if server_info.status != ServerStatus.CONNECTED_ZURICH:
            health_score -= 20
            if health_status == ConnectionHealth.EXCELLENT:
                health_status = ConnectionHealth.GOOD
                
        return ServerMetrics(
            current_server=server_info.server_name,
            latency_ms=server_info.latency_ms,
            health_score=max(0, health_score),
            health_status=health_status
        )
        
    def _format_status_update(self, server_info: Optional[ServerInfo]) -> dict:
        """Format status update for UI"""
        if not server_info:
            return {
                'server': 'Unknown',
                'status': ServerStatus.UNKNOWN.value,
                'latency': -1,
                'color': 'red',
                'emoji': '❌'
            }
            
        color = 'green' if server_info.status == ServerStatus.CONNECTED_ZURICH else 'orange'
        emoji = '✅' if server_info.status == ServerStatus.CONNECTED_ZURICH else '⚠️'
        
        return {
            'server': server_info.server_name,
            'status': server_info.status.value,
            'latency': server_info.latency_ms,
            'port': server_info.port,
            'ssl': server_info.ssl_enabled,
            'connection_time': server_info.connection_time.isoformat(),
            'color': color,
            'emoji': emoji
        }
        
    def _format_metrics_update(self, metrics: ServerMetrics) -> dict:
        """Format metrics update for UI"""
        return {
            'current_server': metrics.current_server,
            'target_server': metrics.target_server,
            'latency_ms': metrics.latency_ms,
            'health_score': metrics.health_score,
            'health_status': metrics.health_status.value,
            'timestamp': datetime.now().isoformat()
        }

# ==============================================================================
# PYQT6 DASHBOARD WIDGET
# ==============================================================================

class IBKRServerStatusWidget(QWidget):
    """PyQt6 widget for displaying IBKR server status"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        super().__init__()
        self.config = config or GatewayConfig()
        self.setup_ui()
        self.setup_monitoring()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("🌐 IBKR Server Status")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Status display
        self.status_label = QLabel("🔄 Checking server status...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # Metrics display  
        self.metrics_label = QLabel("")
        layout.addWidget(self.metrics_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("🔄 Refresh")
        self.refresh_button.clicked.connect(self.force_refresh)
        button_layout.addWidget(self.refresh_button)
        
        self.force_zurich_button = QPushButton("🇨🇭 Force Zurich")
        self.force_zurich_button.clicked.connect(self.force_zurich_routing)
        button_layout.addWidget(self.force_zurich_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def setup_monitoring(self):
        """Setup background monitoring"""
        # Create worker thread
        self.worker = ServerMonitorWorker(self.config)
        self.worker.statusUpdated.connect(self.update_status)
        self.worker.metricsUpdated.connect(self.update_metrics)
        self.worker.errorOccurred.connect(self.handle_error)
        
        # Start monitoring
        self.worker.start()
        
    def update_status(self, status_data: dict):
        """Update status display"""
        server = status_data['server']
        emoji = status_data['emoji']
        color = status_data['color']
        latency = status_data['latency']
        port = status_data.get('port', 0)
        ssl = status_data.get('ssl', False)
        
        latency_text = f"{latency:.1f} ms" if latency > 0 else "N/A"
        ssl_text = "🔒 SSL" if ssl else "🔓 Plain"
        
        status_html = f"""
        <b><font color='{color}'>{emoji} IBKR Server:</font></b> {server}<br>
        <b>📡 Latency:</b> {latency_text}<br>
        <b>🔌 Port:</b> {port} ({ssl_text})<br>
        <b>🎯 Target:</b> {self.config.gateway_server}
        """
        
        self.status_label.setText(status_html)
        
    def update_metrics(self, metrics_data: dict):
        """Update metrics display"""
        health_score = metrics_data['health_score']
        health_status = metrics_data['health_status']
        
        # Color coding for health
        if health_score >= 90:
            health_color = 'green'
        elif health_score >= 70:
            health_color = 'orange'
        else:
            health_color = 'red'
            
        metrics_html = f"""
        <b>📊 Health Score:</b> <font color='{health_color}'>{health_score:.1f}%</font><br>
        <b>💓 Status:</b> {health_status.replace('_', ' ').title()}
        """
        
        self.metrics_label.setText(metrics_html)
        
    def handle_error(self, error_message: str):
        """Handle monitoring errors"""
        self.status_label.setText(f"❌ Error: {error_message}")
        
    def force_refresh(self):
        """Force a status refresh"""
        if hasattr(self, 'worker'):
            # Restart worker for immediate refresh
            self.worker.stop()
            self.worker.start()
            
    def force_zurich_routing(self):
        """Attempt to force routing to Zurich server"""
        try:
            # This would require admin privileges
            hosts_entry = f"{SERVER_IPS['zdc1.ibllc.com']} zdc1.ibllc.com"
            
            # Show message to user
            from PySide6.QtWidgets import QMessageBox
            
            msg = QMessageBox()
            msg.setWindowTitle("Force Zurich Routing")
            msg.setText(
                f"To force routing to Zurich server, add this line to /etc/hosts:\n\n"
                f"{hosts_entry}\n\n"
                f"This requires admin privileges and gateway restart."
            )
            msg.exec()
            
        except Exception as e:
            self.handle_error(f"Failed to configure routing: {e}")
            
    def closeEvent(self, event):
        """Clean shutdown"""
        if hasattr(self, 'worker'):
            self.worker.stop()
        event.accept()

# ==============================================================================
# MAIN SERVER MONITOR CLASS
# ==============================================================================

class ServerMonitor:
    """Main server monitoring class"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            
    def get_current_server_info(self) -> Optional[ServerInfo]:
        """Get current server connection information"""
        worker = ServerMonitorWorker(self.config)
        return worker._get_current_server()
        
    def validate_server_routing(self) -> Dict[str, Any]:
        """Validate current server routing"""
        server_info = self.get_current_server_info()
        
        result = {
            'is_zurich': False,
            'current_server': 'Unknown',
            'target_server': self.config.gateway_server,
            'routing_correct': False,
            'latency_ms': -1,
            'recommendations': []
        }
        
        if server_info:
            result['current_server'] = server_info.server_name
            result['latency_ms'] = server_info.latency_ms
            result['is_zurich'] = server_info.server_name == IBKR_SERVERS['zurich']
            result['routing_correct'] = result['is_zurich']
            
            if not result['is_zurich']:
                result['recommendations'].append("Consider forcing DNS resolution to Zurich")
                result['recommendations'].append("Check IBKR account server assignment")
                result['recommendations'].append("Restart gateway during EU trading hours")
                
        return result
        
    def generate_hosts_entry(self) -> str:
        """Generate /etc/hosts entry for Zurich routing"""
        return f"{SERVER_IPS['zdc1.ibllc.com']} zdc1.ibllc.com"

# ==============================================================================
# STANDALONE UTILITIES
# ==============================================================================

def check_server_status() -> Dict[str, Any]:
    """Standalone function to check server status"""
    monitor = ServerMonitor()
    return monitor.validate_server_routing()
    
def create_server_widget(config: Optional[GatewayConfig] = None) -> IBKRServerStatusWidget:
    """Factory function to create server status widget"""
    return IBKRServerStatusWidget(config)

# ==============================================================================
# MAIN EXECUTION AND TESTING
# ==============================================================================

def main():
    """Main execution function for testing and demonstration"""
    print("🚀 SPYDER B17 - Server Monitor")
    print("=" * 50)
    
    try:
        # Test server monitoring
        monitor = ServerMonitor()
        
        print("📡 Current Server Status:")
        status = monitor.validate_server_routing()
        
        for key, value in status.items():
            if key == 'recommendations' and value:
                print(f"  💡 {key}:")
                for rec in value:
                    print(f"     - {rec}")
            else:
                print(f"  📊 {key}: {value}")
                
        print(f"\n🔧 Hosts Entry for Zurich Routing:")
        print(f"  {monitor.generate_hosts_entry()}")
        
        print(f"\n✅ Server Monitor test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False
        
    return True

if __name__ == "__main__":
    main()