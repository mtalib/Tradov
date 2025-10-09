#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG14_GatewayControlPanel.py
Purpose: IB Gateway Control Panel (Dockable Widget)
Author: SPYDER Development Team
Year Created: 2025
Last Updated: 2025-10-09

Module Description:
    Dockable control panel for managing IB Gateway startup and 8-client
    connections. Provides visual feedback, progress tracking, and manual
    control over Gateway and client connections.

Key Features:
    • Gateway status indicator (Running/Stopped/Starting)
    • Start/Stop Gateway buttons
    • Client connection progress (0/8 → 8/8)
    • Compact log window (last 10 messages)
    • Individual client status indicators (clickable)
    • Auto-launch Gateway option
    • Dockable/floating window support

Integration:
    Works seamlessly with SpyderG05_TradingDashboard and 
    SpyderG15_ClientConnectionManager
"""

import sys
import os
import subprocess
import psutil
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextEdit, QFrame, QGroupBox, QGridLayout,
    QCheckBox, QDockWidget, QApplication, QMessageBox
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer
from PySide6.QtGui import QFont, QColor

from SpyderG_GUI.SpyderG15_ClientConnectionManager import (
    ClientConnectionThread,
    ClientStatus
)


# ==============================================================================
# CONSTANTS
# ==============================================================================

COLORS = {
    "background": "#0a0a0a",
    "panel": "#1a1a1a",
    "border": "#333333",
    "text": "#ffffff",
    "positive": "#00ff41",
    "negative": "#ff1744",
    "warning": "#ffd700",
    "neutral": "#888888",
    "connecting": "#00b8d4",
}


# ==============================================================================
# GATEWAY LAUNCHER THREAD
# ==============================================================================

class GatewayLauncherThread(QThread):
    """Background thread to launch IB Gateway"""
    
    status_update = Signal(str)
    progress_update = Signal(int)
    gateway_ready = Signal(bool)
    log_message = Signal(str)
    
    def __init__(self, config_path: Optional[Path] = None):
        super().__init__()
        self.config_path = config_path
        self._stop_requested = False
        
        # Default paths
        self.gateway_dir = Path.home() / "Jts" / "ibgateway" / "1039"
        self.ibc_path = Path.home() / "ibc"
    
    def run(self):
        """Launch Gateway in background"""
        try:
            self.log_message.emit("🚀 Starting IB Gateway launcher...")
            self.status_update.emit("Checking for existing Gateway...")
            self.progress_update.emit(10)
            
            # Check if already running
            if self._is_gateway_running():
                self.log_message.emit("⚠️ Gateway already running")
                self.status_update.emit("Gateway already running")
                self.progress_update.emit(100)
                self.gateway_ready.emit(True)
                return
            
            # Cleanup old processes
            self.status_update.emit("Cleaning up old processes...")
            self.progress_update.emit(20)
            self._cleanup_old_processes()
            time.sleep(2)
            
            # Launch Gateway
            self.status_update.emit("Launching IB Gateway...")
            self.progress_update.emit(30)
            
            if not self._launch_gateway():
                self.log_message.emit("❌ Failed to start Gateway")
                self.gateway_ready.emit(False)
                return
            
            # Wait for Gateway to be ready
            self.status_update.emit("Waiting for Gateway...")
            start_time = time.time()
            timeout = 90
            
            while time.time() - start_time < timeout:
                if self._stop_requested:
                    self.log_message.emit("🛑 Gateway launch cancelled")
                    self.gateway_ready.emit(False)
                    return
                
                elapsed = int(time.time() - start_time)
                progress = 30 + int((elapsed / timeout) * 60)
                self.progress_update.emit(min(progress, 90))
                
                if self._check_port_available():
                    self.log_message.emit("✅ Gateway ready on port 4002")
                    self.status_update.emit("Gateway ready!")
                    self.progress_update.emit(100)
                    time.sleep(3)
                    self.gateway_ready.emit(True)
                    return
                
                time.sleep(2)
            
            # Timeout
            self.log_message.emit(f"❌ Gateway startup timeout after {timeout}s")
            self.status_update.emit("Gateway startup timeout")
            self.gateway_ready.emit(False)
            
        except Exception as e:
            self.log_message.emit(f"❌ Error launching Gateway: {e}")
            self.gateway_ready.emit(False)
    
    def _is_gateway_running(self) -> bool:
        """Check if Gateway is running"""
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if 'java' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'ibgateway' in cmdline.lower():
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def _cleanup_old_processes(self):
        """Kill zombie Gateway processes"""
        killed = 0
        for proc in psutil.process_iter(['name', 'cmdline', 'pid']):
            try:
                if 'java' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'ibgateway' in cmdline.lower():
                        self.log_message.emit(f"Killing old Gateway (PID {proc.info['pid']})")
                        proc.kill()
                        killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if killed > 0:
            self.log_message.emit(f"Cleaned up {killed} old process(es)")
    
    def _launch_gateway(self) -> bool:
        """Launch Gateway using IBC"""
        try:
            ibc_script = self.ibc_path / "scripts" / "ibcstart.sh"
            
            if not ibc_script.exists():
                self.log_message.emit(f"❌ IBC script not found: {ibc_script}")
                return False
            
            env = os.environ.copy()
            env['TWS_MAJOR_VRSN'] = '1039'
            env['TRADING_MODE'] = 'paper'
            env['IBC_INI'] = str(self.ibc_path / "config.ini")
            
            cmd = [str(ibc_script), 'paper', '-g']
            
            self.log_message.emit(f"Executing: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            self.log_message.emit(f"Gateway process started (PID: {process.pid})")
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ IBC launch failed: {e}")
            return False
    
    def _check_port_available(self) -> bool:
        """Check if port 4002 is available"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(("127.0.0.1", 4002))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def stop(self):
        """Request stop"""
        self._stop_requested = True


# ==============================================================================
# GATEWAY CONTROL PANEL WIDGET
# ==============================================================================

class GatewayControlPanel(QWidget):
    """
    Main control panel widget for Gateway and client management.
    Can be used standalone or as a dockable widget.
    """
    
    # Signals
    gateway_started = Signal()
    gateway_stopped = Signal()
    clients_connected = Signal(int)  # connected_count
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.gateway_thread: Optional[GatewayLauncherThread] = None
        self.client_thread: Optional[ClientConnectionThread] = None
        
        self.gateway_running = False
        self.clients_connected_count = 0
        
        self.setup_ui()
        
        # Check initial Gateway status
        QTimer.singleShot(1000, self.check_gateway_status)
    
    def setup_ui(self):
        """Setup the UI"""
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS["background"]};
                color: {COLORS["text"]};
            }}
            QPushButton {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                padding: 8px;
                border-radius: 3px;
            }}
            QPushButton:hover {{
                background-color: #2a2a2a;
            }}
            QTextEdit {{
                background-color: {COLORS["panel"]};
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                font-family: monospace;
                font-size: 11px;
            }}
            QGroupBox {{
                color: {COLORS["text"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }}
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Title
        title_label = QLabel("🔧 IB GATEWAY CONTROL")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        main_layout.addWidget(title_label)
        
        # Gateway Status Section
        gateway_group = self.create_gateway_status_section()
        main_layout.addWidget(gateway_group)
        
        # Client Connection Section
        client_group = self.create_client_connection_section()
        main_layout.addWidget(client_group)
        
        # Log Section
        log_group = self.create_log_section()
        main_layout.addWidget(log_group)
        
        # Settings
        settings_group = self.create_settings_section()
        main_layout.addWidget(settings_group)
        
        main_layout.addStretch()
        
        self.setLayout(main_layout)
        self.setMinimumWidth(400)
        self.setMinimumHeight(600)
    
    def create_gateway_status_section(self) -> QGroupBox:
        """Create Gateway status section"""
        group = QGroupBox("Gateway Status")
        layout = QVBoxLayout()
        
        # Status indicator
        status_layout = QHBoxLayout()
        
        self.gateway_status_dot = QLabel("●")
        self.gateway_status_dot.setStyleSheet(
            f"color: {COLORS['negative']}; font-size: 20px;"
        )
        status_layout.addWidget(self.gateway_status_dot)
        
        self.gateway_status_label = QLabel("Gateway: Stopped")
        status_layout.addWidget(self.gateway_status_label)
        status_layout.addStretch()
        
        layout.addLayout(status_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.start_gateway_btn = QPushButton("🚀 Start Gateway")
        self.start_gateway_btn.clicked.connect(self.start_gateway)
        button_layout.addWidget(self.start_gateway_btn)
        
        self.stop_gateway_btn = QPushButton("🛑 Stop Gateway")
        self.stop_gateway_btn.clicked.connect(self.stop_gateway)
        self.stop_gateway_btn.setEnabled(False)
        button_layout.addWidget(self.stop_gateway_btn)
        
        layout.addLayout(button_layout)
        
        # Progress bar
        self.gateway_progress = QProgressBar()
        self.gateway_progress.setVisible(False)
        layout.addWidget(self.gateway_progress)
        
        group.setLayout(layout)
        return group
    
    def create_client_connection_section(self) -> QGroupBox:
        """Create client connection section"""
        group = QGroupBox("Client Connections (8 Clients)")
        layout = QVBoxLayout()
        
        # Connection status
        status_layout = QHBoxLayout()
        
        self.client_status_label = QLabel("Clients: 0/8 Connected")
        status_layout.addWidget(self.client_status_label)
        status_layout.addStretch()
        
        layout.addLayout(status_layout)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.connect_clients_btn = QPushButton("🔗 Connect All Clients")
        self.connect_clients_btn.clicked.connect(self.connect_clients)
        self.connect_clients_btn.setEnabled(False)
        button_layout.addWidget(self.connect_clients_btn)
        
        self.disconnect_clients_btn = QPushButton("🔌 Disconnect All")
        self.disconnect_clients_btn.clicked.connect(self.disconnect_clients)
        self.disconnect_clients_btn.setEnabled(False)
        button_layout.addWidget(self.disconnect_clients_btn)
        
        layout.addLayout(button_layout)
        
        # Progress bar
        self.client_progress = QProgressBar()
        self.client_progress.setMaximum(8)
        self.client_progress.setValue(0)
        self.client_progress.setVisible(False)
        layout.addWidget(self.client_progress)
        
        group.setLayout(layout)
        return group
    
    def create_log_section(self) -> QGroupBox:
        """Create log section"""
        group = QGroupBox("Activity Log")
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        layout.addWidget(self.log_text)
        
        # Clear log button
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.log_text.clear)
        layout.addWidget(clear_btn)
        
        group.setLayout(layout)
        return group
    
    def create_settings_section(self) -> QGroupBox:
        """Create settings section"""
        group = QGroupBox("Settings")
        layout = QVBoxLayout()
        
        self.auto_start_check = QCheckBox("Auto-start Gateway on dashboard launch")
        layout.addWidget(self.auto_start_check)
        
        self.auto_connect_check = QCheckBox("Auto-connect clients when Gateway ready")
        self.auto_connect_check.setChecked(True)
        layout.addWidget(self.auto_connect_check)
        
        self.auto_reconnect_check = QCheckBox("Auto-reconnect on client disconnection")
        layout.addWidget(self.auto_reconnect_check)
        
        group.setLayout(layout)
        return group
    
    # ==========================================================================
    # GATEWAY CONTROL
    # ==========================================================================
    
    @Slot()
    def start_gateway(self):
        """Start IB Gateway"""
        self.add_log("🚀 Starting IB Gateway...")
        
        self.start_gateway_btn.setEnabled(False)
        self.gateway_progress.setVisible(True)
        self.gateway_progress.setValue(0)
        
        # Launch in background thread
        self.gateway_thread = GatewayLauncherThread()
        self.gateway_thread.status_update.connect(self.update_gateway_status)
        self.gateway_thread.progress_update.connect(self.gateway_progress.setValue)
        self.gateway_thread.log_message.connect(self.add_log)
        self.gateway_thread.gateway_ready.connect(self.on_gateway_ready)
        
        self.gateway_thread.start()
    
    @Slot()
    def stop_gateway(self):
        """Stop IB Gateway"""
        reply = QMessageBox.question(
            self,
            "Stop Gateway",
            "Stop IB Gateway?\n\nThis will disconnect all clients.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.add_log("🛑 Stopping IB Gateway...")
            
            # Disconnect clients first
            if self.client_thread and self.client_thread.manager:
                self.client_thread.manager.disconnect_all_clients()
            
            # Kill Gateway processes
            killed = 0
            for proc in psutil.process_iter(['name', 'cmdline', 'pid']):
                try:
                    if 'java' in proc.info['name'].lower():
                        cmdline = ' '.join(proc.info['cmdline'] or [])
                        if 'ibgateway' in cmdline.lower():
                            proc.kill()
                            killed += 1
                except:
                    pass
            
            self.add_log(f"✅ Gateway stopped ({killed} process(es) killed)")
            self.gateway_running = False
            self.update_gateway_ui()
    
    @Slot(bool)
    def on_gateway_ready(self, success: bool):
        """Handle Gateway ready signal"""
        self.gateway_progress.setVisible(False)
        
        if success:
            self.gateway_running = True
            self.add_log("✅ Gateway is ready!")
            
            # Auto-connect clients if enabled
            if self.auto_connect_check.isChecked():
                QTimer.singleShot(2000, self.connect_clients)
        else:
            self.add_log("❌ Gateway failed to start")
        
        self.update_gateway_ui()
    
    # ==========================================================================
    # CLIENT CONTROL
    # ==========================================================================
    
    @Slot()
    def connect_clients(self):
        """Connect all clients"""
        if not self.gateway_running:
            QMessageBox.warning(
                self,
                "Gateway Not Running",
                "Please start Gateway first before connecting clients."
            )
            return
        
        self.add_log("🔗 Connecting 8 clients...")
        
        self.connect_clients_btn.setEnabled(False)
        self.client_progress.setVisible(True)
        self.client_progress.setValue(0)
        
        # Connect in background thread
        self.client_thread = ClientConnectionThread(
            host="127.0.0.1",
            port=4002,
            num_clients=8
        )
        
        self.client_thread.log_message.connect(self.add_log)
        self.client_thread.connection_progress.connect(self.update_client_progress)
        self.client_thread.all_clients_ready.connect(self.on_clients_ready)
        
        self.client_thread.start()
    
    @Slot()
    def disconnect_clients(self):
        """Disconnect all clients"""
        if self.client_thread and self.client_thread.manager:
            self.add_log("🔌 Disconnecting all clients...")
            self.client_thread.manager.disconnect_all_clients()
            self.clients_connected_count = 0
            self.update_client_ui()
    
    @Slot(int, int)
    def update_client_progress(self, current: int, total: int):
        """Update client connection progress"""
        self.client_progress.setValue(current)
        self.client_status_label.setText(f"Clients: {current}/8 Connected")
    
    @Slot(int, int)
    def on_clients_ready(self, connected: int, total: int):
        """Handle clients ready signal"""
        self.clients_connected_count = connected
        self.client_progress.setVisible(False)
        
        self.add_log(f"✅ Client connection complete: {connected}/{total}")
        
        self.update_client_ui()
        self.clients_connected.emit(connected)
    
    # ==========================================================================
    # UI UPDATES
    # ==========================================================================
    
    def update_gateway_status(self, status: str):
        """Update Gateway status label"""
        self.gateway_status_label.setText(f"Gateway: {status}")
    
    def update_gateway_ui(self):
        """Update Gateway UI based on status"""
        if self.gateway_running:
            self.gateway_status_dot.setStyleSheet(
                f"color: {COLORS['positive']}; font-size: 20px;"
            )
            self.gateway_status_label.setText("Gateway: Running")
            self.start_gateway_btn.setEnabled(False)
            self.stop_gateway_btn.setEnabled(True)
            self.connect_clients_btn.setEnabled(True)
        else:
            self.gateway_status_dot.setStyleSheet(
                f"color: {COLORS['negative']}; font-size: 20px;"
            )
            self.gateway_status_label.setText("Gateway: Stopped")
            self.start_gateway_btn.setEnabled(True)
            self.stop_gateway_btn.setEnabled(False)
            self.connect_clients_btn.setEnabled(False)
    
    def update_client_ui(self):
        """Update client UI based on status"""
        self.client_status_label.setText(
            f"Clients: {self.clients_connected_count}/8 Connected"
        )
        
        if self.clients_connected_count > 0:
            self.disconnect_clients_btn.setEnabled(True)
        else:
            self.disconnect_clients_btn.setEnabled(False)
    
    def add_log(self, message: str):
        """Add message to log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
    
    def check_gateway_status(self):
        """Check if Gateway is already running"""
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if 'java' in proc.info['name'].lower():
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'ibgateway' in cmdline.lower():
                        self.gateway_running = True
                        self.add_log("✅ Gateway already running")
                        self.update_gateway_ui()
                        return
            except:
                pass
        
        self.add_log("Gateway not running")


# ==============================================================================
# DOCKABLE WRAPPER
# ==============================================================================

def create_gateway_dock_widget(parent=None) -> QDockWidget:
    """
    Factory function to create a dockable Gateway Control Panel.
    
    Args:
        parent: Parent widget
        
    Returns:
        QDockWidget containing the Gateway Control Panel
    """
    dock = QDockWidget("IB Gateway Control", parent)
    dock.setAllowedAreas(
        Qt.DockWidgetArea.LeftDockWidgetArea | 
        Qt.DockWidgetArea.RightDockWidgetArea
    )
    
    panel = GatewayControlPanel()
    dock.setWidget(panel)
    
    return dock


# ==============================================================================
# MAIN EXECUTION - FOR TESTING
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("SPYDER G14 - Gateway Control Panel Test")
    print("=" * 60)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Create standalone panel
    panel = GatewayControlPanel()
    panel.setWindowTitle("SPYDER - IB Gateway Control")
    panel.show()
    
    sys.exit(app.exec())
