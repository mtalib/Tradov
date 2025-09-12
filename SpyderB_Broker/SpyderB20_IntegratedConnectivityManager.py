#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB20_IntegratedConnectivityManager.py
Purpose: Unified IBKR Connectivity Management Dashboard
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-28 Time: 16:30:00  

Module Description:
    Integrated connectivity management system that combines server monitoring,
    connectivity diagnostics, and VPN management into a unified dashboard widget.
    Provides automated failover, intelligent routing decisions, and seamless
    integration with IBKR Gateway startup/shutdown processes. This module serves
    as the central hub for all Zurich connectivity management operations.

Key Features:
    - Unified dashboard combining all connectivity components
    - Automated server monitoring → diagnostics → VPN failover workflow
    - Real-time connectivity status with color-coded indicators
    - Intelligent routing decisions based on server availability
    - Integration with Gateway startup/shutdown automation
    - Comprehensive logging and error handling
    - PyQt6 dashboard widgets for real-time monitoring
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import os
import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import deque, defaultdict
import traceback
import subprocess

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTextEdit, QProgressBar, QGroupBox,
                            QCheckBox, QMessageBox, QTabWidget, QListWidget,
                            QListWidgetItem, QSplitter, QFrame, QScrollArea)
from PySide6.QtCore import QTimer, QThread, Signal, Qt, QObject, QPropertyAnimation
from PySide6.QtGui import QFont, QColor, QIcon, QPalette

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig, GatewayManager
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler, TradingError, ErrorCategory, ErrorSeverity
    
    # Import our connectivity components
    from SpyderB_Broker.SpyderB17_ServerMonitor import (
        ServerMonitor, IBKRServerStatusWidget, ServerMonitorWorker,
        ServerStatus, ServerInfo, ConnectionHealth
    )
    from SpyderB_Broker.SpyderB18_ZurichConnectivityDiagnostic import (
        ZurichConnectivityDiagnostic, ZurichDiagnosticWidget, DiagnosticLevel,
        ConnectivityStatus, DiagnosticResult, ZurichConnectivityRepair
    )
    from SpyderB_Broker.SpyderB19_VPNManager import (
        VPNManager, VPNDashboardWidget, VPNStatus, VPNConnectionInfo,
        VPNAutomation, OPTIMAL_VPN_ENDPOINTS
    )
    
    CONNECTIVITY_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Some connectivity modules not available: {e}")
    CONNECTIVITY_MODULES_AVAILABLE = False
    
    # Fallback enums
    class ServerStatus(Enum):
        CONNECTED_ZURICH = "connected_zurich"
        CONNECTED_OTHER = "connected_other"
        DISCONNECTED = "disconnected"
        UNKNOWN = "unknown"
    
    class ConnectivityStatus(Enum):
        SUCCESS = "success"
        FAILED = "failed"
        TIMEOUT = "timeout"
    
    class VPNStatus(Enum):
        CONNECTED = "connected"
        DISCONNECTED = "disconnected"
        CONNECTING = "connecting"
        ERROR = "error"

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# Connectivity management states
class ConnectivityState(Enum):
    """Integrated connectivity state"""
    OPTIMAL = "optimal"              # Zurich direct, no issues
    GOOD = "good"                   # Working connection, minor issues
    DEGRADED = "degraded"           # Connection issues, VPN may help
    FAILED = "failed"               # No connectivity, requires intervention
    DIAGNOSING = "diagnosing"       # Running diagnostics
    VPN_CONNECTING = "vpn_connecting" # Attempting VPN connection
    REPAIRING = "repairing"         # Attempting repairs

class ActionPriority(Enum):
    """Priority levels for automated actions"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

# Workflow automation settings
CONNECTIVITY_CHECK_INTERVAL = 30  # seconds
VPN_CONNECT_TIMEOUT = 60          # seconds
DIAGNOSTIC_TIMEOUT = 120          # seconds
MAX_AUTO_RETRY_ATTEMPTS = 3

# Status colors for UI
STATUS_COLORS = {
    ConnectivityState.OPTIMAL: '#4CAF50',      # Green
    ConnectivityState.GOOD: '#8BC34A',         # Light Green
    ConnectivityState.DEGRADED: '#FF9800',     # Orange
    ConnectivityState.FAILED: '#F44336',       # Red
    ConnectivityState.DIAGNOSING: '#2196F3',   # Blue
    ConnectivityState.VPN_CONNECTING: '#9C27B0', # Purple
    ConnectivityState.REPAIRING: '#FF5722'     # Deep Orange
}

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ConnectivityAction:
    """Represents an automated connectivity action"""
    action_type: str
    priority: ActionPriority
    description: str
    execution_function: Callable[[], Tuple[bool, str]]
    estimated_duration: int = 30  # seconds
    prerequisites: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ConnectivityReport:
    """Comprehensive connectivity status report"""
    timestamp: datetime = field(default_factory=datetime.now)
    overall_state: ConnectivityState = ConnectivityState.FAILED
    server_status: Optional[ServerStatus] = None
    server_name: Optional[str] = None
    server_latency: float = -1.0
    zurich_reachable: bool = False
    vpn_status: VPNStatus = VPNStatus.DISCONNECTED
    vpn_endpoint: Optional[str] = None
    diagnostic_summary: Optional[str] = None
    active_issues: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    last_successful_connection: Optional[datetime] = None
    connection_stability_score: float = 0.0

# ==============================================================================
# INTEGRATED CONNECTIVITY MANAGER
# ==============================================================================

class IntegratedConnectivityManager:
    """
    Central connectivity management system that orchestrates all components.
    
    This manager combines server monitoring, diagnostics, and VPN management
    into a unified workflow with automated decision-making and failover.
    """
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        
        # Setup logging and error handling
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            
        self.error_handler = SpyderErrorHandler() if SpyderErrorHandler else None
        
        # Initialize sub-components
        self._initialize_components()
        
        # State management
        self.current_state = ConnectivityState.UNKNOWN
        self.last_state_change = datetime.now()
        self.connectivity_history = deque(maxlen=100)
        self.active_actions = []
        self.automation_enabled = True
        self.monitoring_active = False
        
        # Performance tracking
        self.connection_attempts = 0
        self.successful_connections = 0
        self.last_diagnostic_run = None
        self.last_vpn_attempt = None
        
        # Event callbacks
        self.state_change_callbacks = []
        self.connectivity_callbacks = []
        
    def _initialize_components(self):
        """Initialize all connectivity components"""
        try:
            if CONNECTIVITY_MODULES_AVAILABLE:
                self.server_monitor = ServerMonitor(self.config)
                self.diagnostic_engine = ZurichConnectivityDiagnostic(self.config)
                self.vpn_manager = VPNManager(self.config)
                self.vpn_automation = VPNAutomation(self.vpn_manager, self.config)
                self.connectivity_repair = ZurichConnectivityRepair(self.config)
                
                self.logger.info("✅ All connectivity components initialized")
            else:
                self.logger.warning("⚠️ Running in fallback mode - limited functionality")
                self.server_monitor = None
                self.diagnostic_engine = None
                self.vpn_manager = None
                self.vpn_automation = None
                self.connectivity_repair = None
                
        except Exception as e:
            self.logger.error(f"Failed to initialize connectivity components: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "IntegratedConnectivityManager")
    
    # ==========================================================================
    # PUBLIC INTERFACE
    # ==========================================================================
    
    def start_monitoring(self) -> bool:
        """Start the integrated connectivity monitoring"""
        try:
            if self.monitoring_active:
                self.logger.warning("Connectivity monitoring already active")
                return True
                
            self.logger.info("🚀 Starting integrated connectivity monitoring")
            
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.monitoring_thread.start()
            
            # Run initial assessment
            self._perform_connectivity_assessment()
            
            self.monitoring_active = True
            self.logger.info("✅ Integrated connectivity monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start connectivity monitoring: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, "IntegratedConnectivityManager")
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop the integrated connectivity monitoring"""
        try:
            self.monitoring_active = False
            self.logger.info("🛑 Connectivity monitoring stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping connectivity monitoring: {e}")
            return False
    
    def get_connectivity_report(self) -> ConnectivityReport:
        """Generate comprehensive connectivity status report"""
        try:
            report = ConnectivityReport(
                overall_state=self.current_state,
                connection_stability_score=self._calculate_stability_score()
            )
            
            # Get server information
            if self.server_monitor:
                server_info = self.server_monitor.get_current_server_info()
                if server_info:
                    report.server_status = server_info.status
                    report.server_name = server_info.server_name
                    report.server_latency = server_info.latency_ms
                    report.zurich_reachable = server_info.status == ServerStatus.CONNECTED_ZURICH
            
            # Get VPN information
            if self.vpn_manager:
                vpn_info = self.vpn_manager.get_connection_status()
                report.vpn_status = vpn_info.status
                report.vpn_endpoint = vpn_info.endpoint
            
            # Add current issues and recommendations
            report.active_issues = self._identify_active_issues()
            report.recommended_actions = self._generate_recommendations(report)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Error generating connectivity report: {e}")
            return ConnectivityReport(overall_state=ConnectivityState.FAILED)
    
    def force_connectivity_check(self) -> ConnectivityReport:
        """Force an immediate comprehensive connectivity check"""
        self.logger.info("🔍 Forcing connectivity check...")
        self._perform_connectivity_assessment()
        return self.get_connectivity_report()
    
    def execute_automated_repair(self) -> Tuple[bool, str]:
        """Execute automated connectivity repair sequence"""
        try:
            self.logger.info("🛠️ Starting automated connectivity repair")
            self._update_state(ConnectivityState.REPAIRING)
            
            # Step 1: Run diagnostics
            if self.diagnostic_engine:
                diagnostic_result = self.diagnostic_engine.run_full_diagnostic(DiagnosticLevel.COMPREHENSIVE)
                
                # Step 2: Attempt VPN connection if needed
                if not diagnostic_result.zurich_reachable and self.vpn_manager:
                    self._update_state(ConnectivityState.VPN_CONNECTING)
                    success, message = self.vpn_manager.connect_to_optimal_endpoint()
                    
                    if success:
                        # Re-test connectivity through VPN
                        time.sleep(10)  # Allow VPN to establish
                        diagnostic_result = self.diagnostic_engine.run_full_diagnostic(DiagnosticLevel.BASIC)
                        
                        if diagnostic_result.zurich_reachable:
                            self._update_state(ConnectivityState.GOOD)
                            return True, "✅ Connectivity restored via VPN"
            
            # Step 3: Apply network repairs if available
            if hasattr(self, 'connectivity_repair') and self.connectivity_repair:
                repair_script = self.connectivity_repair.generate_repair_script(diagnostic_result)
                # Note: Actual script execution would need user consent for security
                self.logger.info("Repair script generated - manual execution may be required")
            
            self._update_state(ConnectivityState.FAILED)
            return False, "❌ Automated repair could not restore connectivity"
            
        except Exception as e:
            self.logger.error(f"Automated repair failed: {e}")
            self._update_state(ConnectivityState.FAILED)
            return False, f"Repair failed: {str(e)}"
    
    # ==========================================================================
    # AUTOMATION AND WORKFLOW
    # ==========================================================================
    
    def _monitoring_loop(self):
        """Main monitoring loop running in background thread"""
        while self.monitoring_active:
            try:
                # Perform regular assessment
                self._perform_connectivity_assessment()
                
                # Execute any pending automated actions
                self._process_automated_actions()
                
                # Sleep until next check
                time.sleep(CONNECTIVITY_CHECK_INTERVAL)
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)  # Short sleep on error
    
    def _perform_connectivity_assessment(self):
        """Perform comprehensive connectivity assessment"""
        try:
            previous_state = self.current_state
            new_state = self._determine_connectivity_state()
            
            if new_state != previous_state:
                self._update_state(new_state)
                self._trigger_state_change_actions(previous_state, new_state)
            
            # Update connectivity history
            report = self.get_connectivity_report()
            self.connectivity_history.append(report)
            
        except Exception as e:
            self.logger.error(f"Connectivity assessment failed: {e}")
            self._update_state(ConnectivityState.FAILED)
    
    def _determine_connectivity_state(self) -> ConnectivityState:
        """Determine current connectivity state based on all factors"""
        try:
            # Get server status
            server_healthy = False
            zurich_connected = False
            
            if self.server_monitor:
                server_info = self.server_monitor.get_current_server_info()
                if server_info:
                    server_healthy = server_info.status != ServerStatus.DISCONNECTED
                    zurich_connected = server_info.status == ServerStatus.CONNECTED_ZURICH
            
            # Get VPN status
            vpn_connected = False
            if self.vpn_manager:
                vpn_status = self.vpn_manager.get_connection_status()
                vpn_connected = vpn_status.status == VPNStatus.CONNECTED
            
            # Determine overall state
            if zurich_connected and server_healthy:
                return ConnectivityState.OPTIMAL
            elif server_healthy:
                return ConnectivityState.GOOD
            elif vpn_connected:
                return ConnectivityState.DEGRADED
            else:
                return ConnectivityState.FAILED
                
        except Exception as e:
            self.logger.error(f"Error determining connectivity state: {e}")
            return ConnectivityState.FAILED
    
    def _update_state(self, new_state: ConnectivityState):
        """Update connectivity state and notify callbacks"""
        if new_state != self.current_state:
            old_state = self.current_state
            self.current_state = new_state
            self.last_state_change = datetime.now()
            
            self.logger.info(f"🔄 Connectivity state: {old_state.value} → {new_state.value}")
            
            # Notify callbacks
            for callback in self.state_change_callbacks:
                try:
                    callback(old_state, new_state)
                except Exception as e:
                    self.logger.error(f"State change callback error: {e}")
    
    def _trigger_state_change_actions(self, old_state: ConnectivityState, new_state: ConnectivityState):
        """Trigger automated actions based on state changes"""
        if not self.automation_enabled:
            return
            
        try:
            # Failed state - attempt automated repair
            if new_state == ConnectivityState.FAILED and old_state != ConnectivityState.FAILED:
                self._schedule_action(ConnectivityAction(
                    action_type="automated_repair",
                    priority=ActionPriority.HIGH,
                    description="Attempt automated connectivity repair",
                    execution_function=self.execute_automated_repair
                ))
            
            # Degraded state - consider VPN connection
            elif new_state == ConnectivityState.DEGRADED and self.vpn_manager:
                if self.vpn_manager.get_connection_status().status != VPNStatus.CONNECTED:
                    self._schedule_action(ConnectivityAction(
                        action_type="vpn_connect",
                        priority=ActionPriority.MEDIUM,
                        description="Connect to optimal VPN endpoint",
                        execution_function=lambda: self.vpn_manager.connect_to_optimal_endpoint()
                    ))
                    
        except Exception as e:
            self.logger.error(f"Error triggering state change actions: {e}")
    
    def _schedule_action(self, action: ConnectivityAction):
        """Schedule an automated action for execution"""
        self.active_actions.append(action)
        self.active_actions.sort(key=lambda x: x.priority.value, reverse=True)
        self.logger.info(f"📋 Scheduled action: {action.description} (Priority: {action.priority.value})")
    
    def _process_automated_actions(self):
        """Process pending automated actions"""
        if not self.active_actions:
            return
            
        # Execute highest priority action
        action = self.active_actions.pop(0)
        
        try:
            self.logger.info(f"⚡ Executing action: {action.description}")
            success, message = action.execution_function()
            
            if success:
                self.logger.info(f"✅ Action completed: {message}")
            else:
                self.logger.warning(f"⚠️ Action failed: {message}")
                
        except Exception as e:
            self.logger.error(f"Action execution failed: {e}")
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _calculate_stability_score(self) -> float:
        """Calculate connection stability score based on history"""
        if len(self.connectivity_history) < 5:
            return 0.0
        
        recent_history = list(self.connectivity_history)[-10:]  # Last 10 reports
        stable_states = [ConnectivityState.OPTIMAL, ConnectivityState.GOOD]
        
        stable_count = sum(1 for report in recent_history if report.overall_state in stable_states)
        return (stable_count / len(recent_history)) * 100.0
    
    def _identify_active_issues(self) -> List[str]:
        """Identify current connectivity issues"""
        issues = []
        
        try:
            # Check server connectivity
            if self.server_monitor:
                server_info = self.server_monitor.get_current_server_info()
                if not server_info or server_info.status == ServerStatus.DISCONNECTED:
                    issues.append("IBKR Gateway disconnected")
                elif server_info.status != ServerStatus.CONNECTED_ZURICH:
                    issues.append("Not connected to Zurich server")
                elif server_info.latency_ms > 100:
                    issues.append(f"High latency to server ({server_info.latency_ms:.1f}ms)")
            
            # Check VPN status if needed
            if self.current_state in [ConnectivityState.DEGRADED, ConnectivityState.FAILED]:
                if self.vpn_manager:
                    vpn_status = self.vpn_manager.get_connection_status()
                    if vpn_status.status == VPNStatus.DISCONNECTED:
                        issues.append("VPN not connected")
                    elif vpn_status.status == VPNStatus.ERROR:
                        issues.append("VPN connection error")
                        
        except Exception as e:
            issues.append(f"Error checking connectivity: {str(e)}")
            
        return issues
    
    def _generate_recommendations(self, report: ConnectivityReport) -> List[str]:
        """Generate recommendations based on connectivity status"""
        recommendations = []
        
        try:
            if report.overall_state == ConnectivityState.FAILED:
                recommendations.extend([
                    "Run comprehensive connectivity diagnostic",
                    "Try connecting through VPN",
                    "Check IBKR Gateway configuration",
                    "Verify internet connection"
                ])
            elif report.overall_state == ConnectivityState.DEGRADED:
                recommendations.extend([
                    "Consider connecting through VPN for better routing",
                    "Monitor connection stability",
                    "Check for ISP routing issues"
                ])
            elif report.server_latency > 50:
                recommendations.append("High latency detected - consider VPN optimization")
                
            if report.connection_stability_score < 80:
                recommendations.append("Connection stability is low - enable automation")
                
        except Exception as e:
            recommendations.append("Error generating recommendations")
            
        return recommendations
    
    # ==========================================================================
    # CALLBACK MANAGEMENT
    # ==========================================================================
    
    def add_state_change_callback(self, callback: Callable):
        """Add a callback for state changes"""
        self.state_change_callbacks.append(callback)
    
    def add_connectivity_callback(self, callback: Callable):
        """Add a callback for connectivity events"""
        self.connectivity_callbacks.append(callback)

# ==============================================================================
# PYQT6 INTEGRATED DASHBOARD WIDGET
# ==============================================================================

class IntegratedConnectivityDashboard(QWidget):
    """
    Unified PyQt6 dashboard widget for connectivity management.
    
    This widget combines all connectivity components into a single interface
    with real-time monitoring, automated controls, and detailed status display.
    """
    
    # Qt signals
    connectivityStateChanged = Signal(str)  # ConnectivityState
    actionCompleted = Signal(str, bool)     # action_name, success
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        super().__init__()
        self.config = config or GatewayConfig()
        
        # Initialize connectivity manager
        self.connectivity_manager = IntegratedConnectivityManager(config)
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
        
        # UI state
        self.last_report = None
        self.animation_timer = None
        
        # Setup UI and monitoring
        self.setup_ui()
        self.setup_monitoring()
        self.setup_callbacks()
        
        # Start connectivity monitoring
        self.connectivity_manager.start_monitoring()
    
    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout()
        
        # Title and status
        self.create_header_section(main_layout)
        
        # Main content area with tabs
        self.create_main_content(main_layout)
        
        # Control buttons
        self.create_control_section(main_layout)
        
        # Status bar
        self.create_status_bar(main_layout)
        
        self.setLayout(main_layout)
        self.setMinimumSize(800, 600)
        self.setWindowTitle("SPYDER - Integrated Connectivity Manager")
    
    def create_header_section(self, layout):
        """Create header with title and main status"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.Shape.Box)
        header_layout = QHBoxLayout()
        
        # Title
        title_label = QLabel("🌐 SPYDER Integrated Connectivity Manager")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(16)
        title_label.setFont(title_font)
        
        # Main status indicator
        self.main_status_label = QLabel("🔄 Initializing...")
        status_font = QFont()
        status_font.setPointSize(14)
        self.main_status_label.setFont(status_font)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.main_status_label)
        
        header_frame.setLayout(header_layout)
        layout.addWidget(header_frame)
    
    def create_main_content(self, layout):
        """Create main content area with tabs"""
        self.tab_widget = QTabWidget()
        
        # Overview tab
        self.create_overview_tab()
        
        # Server Monitor tab
        self.create_server_monitor_tab()
        
        # Diagnostics tab
        self.create_diagnostics_tab()
        
        # VPN Manager tab
        self.create_vpn_manager_tab()
        
        # Automation tab
        self.create_automation_tab()
        
        layout.addWidget(self.tab_widget)
    
    def create_overview_tab(self):
        """Create overview tab with summary information"""
        overview_widget = QWidget()
        layout = QVBoxLayout()
        
        # Connectivity summary
        summary_group = QGroupBox("📊 Connectivity Summary")
        summary_layout = QVBoxLayout()
        
        self.overview_status_label = QLabel("Status: Checking...")
        self.overview_server_label = QLabel("Server: Unknown")
        self.overview_vpn_label = QLabel("VPN: Unknown")
        self.overview_stability_label = QLabel("Stability: Calculating...")
        
        summary_layout.addWidget(self.overview_status_label)
        summary_layout.addWidget(self.overview_server_label)
        summary_layout.addWidget(self.overview_vpn_label)
        summary_layout.addWidget(self.overview_stability_label)
        
        summary_group.setLayout(summary_layout)
        layout.addWidget(summary_group)
        
        # Active issues
        issues_group = QGroupBox("⚠️ Active Issues")
        issues_layout = QVBoxLayout()
        
        self.issues_list = QListWidget()
        self.issues_list.setMaximumHeight(150)
        issues_layout.addWidget(self.issues_list)
        
        issues_group.setLayout(issues_layout)
        layout.addWidget(issues_group)
        
        # Recommendations
        recommendations_group = QGroupBox("💡 Recommendations")
        recommendations_layout = QVBoxLayout()
        
        self.recommendations_list = QListWidget()
        self.recommendations_list.setMaximumHeight(150)
        recommendations_layout.addWidget(self.recommendations_list)
        
        recommendations_group.setLayout(recommendations_layout)
        layout.addWidget(recommendations_group)
        
        overview_widget.setLayout(layout)
        self.tab_widget.addTab(overview_widget, "Overview")
    
    def create_server_monitor_tab(self):
        """Create server monitoring tab"""
        if CONNECTIVITY_MODULES_AVAILABLE and hasattr(self.connectivity_manager, 'server_monitor'):
            try:
                server_widget = IBKRServerStatusWidget(self.config)
                self.tab_widget.addTab(server_widget, "Server Monitor")
            except Exception as e:
                self.logger.error(f"Failed to create server monitor tab: {e}")
                self._create_fallback_tab("Server Monitor", "Server monitoring not available")
        else:
            self._create_fallback_tab("Server Monitor", "Server monitoring module not available")
    
    def create_diagnostics_tab(self):
        """Create diagnostics tab"""
        if CONNECTIVITY_MODULES_AVAILABLE and hasattr(self.connectivity_manager, 'diagnostic_engine'):
            try:
                diagnostic_widget = ZurichDiagnosticWidget(self.config)
                self.tab_widget.addTab(diagnostic_widget, "Diagnostics")
            except Exception as e:
                self.logger.error(f"Failed to create diagnostics tab: {e}")
                self._create_fallback_tab("Diagnostics", "Diagnostics not available")
        else:
            self._create_fallback_tab("Diagnostics", "Diagnostics module not available")
    
    def create_vpn_manager_tab(self):
        """Create VPN manager tab"""
        if CONNECTIVITY_MODULES_AVAILABLE and hasattr(self.connectivity_manager, 'vpn_manager'):
            try:
                vpn_widget = VPNDashboardWidget(self.config)
                self.tab_widget.addTab(vpn_widget, "VPN Manager")
            except Exception as e:
                self.logger.error(f"Failed to create VPN manager tab: {e}")
                self._create_fallback_tab("VPN Manager", "VPN management not available")
        else:
            self._create_fallback_tab("VPN Manager", "VPN management module not available")
    
    def create_automation_tab(self):
        """Create automation settings tab"""
        automation_widget = QWidget()
        layout = QVBoxLayout()
        
        # Automation controls
        controls_group = QGroupBox("🤖 Automation Settings")
        controls_layout = QVBoxLayout()
        
        self.enable_automation_cb = QCheckBox("Enable automated connectivity management")
        self.enable_automation_cb.setChecked(True)
        self.enable_automation_cb.toggled.connect(self.toggle_automation)
        controls_layout.addWidget(self.enable_automation_cb)
        
        self.auto_vpn_cb = QCheckBox("Automatically connect VPN when needed")
        self.auto_vpn_cb.setChecked(True)
        controls_layout.addWidget(self.auto_vpn_cb)
        
        self.auto_repair_cb = QCheckBox("Attempt automated repairs")
        self.auto_repair_cb.setChecked(True)
        controls_layout.addWidget(self.auto_repair_cb)
        
        controls_group.setLayout(controls_layout)
        layout.addWidget(controls_group)
        
        # Active actions
        actions_group = QGroupBox("⚡ Active Actions")
        actions_layout = QVBoxLayout()
        
        self.active_actions_list = QListWidget()
        self.active_actions_list.setMaximumHeight(200)
        actions_layout.addWidget(self.active_actions_list)
        
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        
        # Logs
        logs_group = QGroupBox("📝 Automation Logs")
        logs_layout = QVBoxLayout()
        
        self.automation_log = QTextEdit()
        self.automation_log.setMaximumHeight(200)
        self.automation_log.setFont(QFont("Courier", 9))
        logs_layout.addWidget(self.automation_log)
        
        logs_group.setLayout(logs_layout)
        layout.addWidget(logs_group)
        
        automation_widget.setLayout(layout)
        self.tab_widget.addTab(automation_widget, "Automation")
    
    def _create_fallback_tab(self, tab_name: str, message: str):
        """Create fallback tab when component is not available"""
        fallback_widget = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel(f"⚠️ {message}")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: orange; font-size: 14px;")
        layout.addWidget(label)
        
        fallback_widget.setLayout(layout)
        self.tab_widget.addTab(fallback_widget, tab_name)
    
    def create_control_section(self, layout):
        """Create control buttons section"""
        controls_frame = QFrame()
        controls_layout = QHBoxLayout()
        
        # Force check button
        self.force_check_btn = QPushButton("🔍 Force Check")
        self.force_check_btn.clicked.connect(self.force_connectivity_check)
        controls_layout.addWidget(self.force_check_btn)
        
        # Auto repair button
        self.auto_repair_btn = QPushButton("🛠️ Auto Repair")
        self.auto_repair_btn.clicked.connect(self.execute_auto_repair)
        controls_layout.addWidget(self.auto_repair_btn)
        
        # Emergency disconnect button
        self.emergency_btn = QPushButton("🚨 Emergency Reset")
        self.emergency_btn.setStyleSheet("background-color: #f44336; color: white;")
        self.emergency_btn.clicked.connect(self.emergency_reset)
        controls_layout.addWidget(self.emergency_btn)
        
        controls_layout.addStretch()
        
        # Settings button
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.clicked.connect(self.show_settings)
        controls_layout.addWidget(self.settings_btn)
        
        controls_frame.setLayout(controls_layout)
        layout.addWidget(controls_frame)
    
    def create_status_bar(self, layout):
        """Create status bar"""
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QHBoxLayout()
        
        self.status_bar_label = QLabel("Ready")
        self.last_update_label = QLabel("")
        
        status_layout.addWidget(QLabel("Status:"))
        status_layout.addWidget(self.status_bar_label)
        status_layout.addStretch()
        status_layout.addWidget(self.last_update_label)
        
        status_frame.setLayout(status_layout)
        layout.addWidget(status_frame)
    
    def setup_monitoring(self):
        """Setup monitoring timers"""
        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(2000)  # Update every 2 seconds
        
        # Initial update
        self.update_display()
    
    def setup_callbacks(self):
        """Setup callbacks with connectivity manager"""
        self.connectivity_manager.add_state_change_callback(self.on_state_change)
    
    # ==========================================================================
    # EVENT HANDLERS
    # ==========================================================================
    
    def update_display(self):
        """Update all display elements"""
        try:
            # Get current report
            report = self.connectivity_manager.get_connectivity_report()
            self.last_report = report
            
            # Update main status
            state_emoji = {
                ConnectivityState.OPTIMAL: "✅",
                ConnectivityState.GOOD: "🟢", 
                ConnectivityState.DEGRADED: "🟡",
                ConnectivityState.FAILED: "❌",
                ConnectivityState.DIAGNOSING: "🔍",
                ConnectivityState.VPN_CONNECTING: "🔗",
                ConnectivityState.REPAIRING: "🛠️"
            }
            
            emoji = state_emoji.get(report.overall_state, "❓")
            self.main_status_label.setText(f"{emoji} {report.overall_state.value.title()}")
            
            # Set status color
            color = STATUS_COLORS.get(report.overall_state, '#666666')
            self.main_status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            
            # Update overview tab
            self.update_overview_tab(report)
            
            # Update status bar
            self.status_bar_label.setText(f"{report.overall_state.value.title()}")
            self.last_update_label.setText(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.logger.error(f"Error updating display: {e}")
    
    def update_overview_tab(self, report: ConnectivityReport):
        """Update overview tab content"""
        try:
            # Status labels
            self.overview_status_label.setText(f"Status: {report.overall_state.value.title()}")
            
            server_text = f"Server: {report.server_name or 'Unknown'}"
            if report.server_latency > 0:
                server_text += f" ({report.server_latency:.1f}ms)"
            self.overview_server_label.setText(server_text)
            
            vpn_text = f"VPN: {report.vpn_status.value.title()}"
            if report.vpn_endpoint:
                vpn_text += f" ({report.vpn_endpoint})"
            self.overview_vpn_label.setText(vpn_text)
            
            self.overview_stability_label.setText(f"Stability: {report.connection_stability_score:.1f}%")
            
            # Update issues list
            self.issues_list.clear()
            for issue in report.active_issues:
                self.issues_list.addItem(f"⚠️ {issue}")
            
            # Update recommendations list
            self.recommendations_list.clear()
            for rec in report.recommended_actions:
                self.recommendations_list.addItem(f"💡 {rec}")
                
        except Exception as e:
            self.logger.error(f"Error updating overview tab: {e}")
    
    def on_state_change(self, old_state: ConnectivityState, new_state: ConnectivityState):
        """Handle connectivity state changes"""
        self.connectivityStateChanged.emit(new_state.value)
        self.automation_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] State change: {old_state.value} → {new_state.value}")
        self.automation_log.moveCursor(self.automation_log.textCursor().End)
    
    def toggle_automation(self, enabled: bool):
        """Toggle automation on/off"""
        self.connectivity_manager.automation_enabled = enabled
        status = "enabled" if enabled else "disabled"
        self.automation_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Automation {status}")
        self.automation_log.moveCursor(self.automation_log.textCursor().End)
    
    def force_connectivity_check(self):
        """Force connectivity check"""
        self.force_check_btn.setEnabled(False)
        self.force_check_btn.setText("🔄 Checking...")
        
        try:
            report = self.connectivity_manager.force_connectivity_check()
            self.automation_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Forced check completed - State: {report.overall_state.value}")
            self.automation_log.moveCursor(self.automation_log.textCursor().End)
        finally:
            self.force_check_btn.setEnabled(True)
            self.force_check_btn.setText("🔍 Force Check")
    
    def execute_auto_repair(self):
        """Execute automated repair"""
        self.auto_repair_btn.setEnabled(False)
        self.auto_repair_btn.setText("🔄 Repairing...")
        
        try:
            success, message = self.connectivity_manager.execute_automated_repair()
            
            self.automation_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Auto repair: {message}")
            self.automation_log.moveCursor(self.automation_log.textCursor().End)
            
            self.actionCompleted.emit("auto_repair", success)
            
        finally:
            self.auto_repair_btn.setEnabled(True)
            self.auto_repair_btn.setText("🛠️ Auto Repair")
    
    def emergency_reset(self):
        """Emergency connectivity reset"""
        reply = QMessageBox.question(self, "Emergency Reset", 
                                   "This will disconnect all connections and reset the system. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # Disconnect VPN if connected
                if (self.connectivity_manager.vpn_manager and 
                    self.connectivity_manager.vpn_manager.get_connection_status().status == VPNStatus.CONNECTED):
                    self.connectivity_manager.vpn_manager.disconnect()
                
                # Reset state
                self.connectivity_manager._update_state(ConnectivityState.UNKNOWN)
                
                self.automation_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Emergency reset completed")
                self.automation_log.moveCursor(self.automation_log.textCursor().End)
                
            except Exception as e:
                self.logger.error(f"Emergency reset failed: {e}")
    
    def show_settings(self):
        """Show settings dialog"""
        # Placeholder for settings dialog
        QMessageBox.information(self, "Settings", "Settings dialog not implemented yet")
    
    def closeEvent(self, event):
        """Clean shutdown"""
        try:
            self.connectivity_manager.stop_monitoring()
            event.accept()
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            event.accept()

# ==============================================================================
# FACTORY FUNCTIONS
# ==============================================================================

def create_connectivity_manager(config: Optional[GatewayConfig] = None) -> IntegratedConnectivityManager:
    """Factory function to create connectivity manager"""
    return IntegratedConnectivityManager(config)

def create_connectivity_dashboard(config: Optional[GatewayConfig] = None) -> IntegratedConnectivityDashboard:
    """Factory function to create connectivity dashboard widget"""
    return IntegratedConnectivityDashboard(config)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function for testing and demonstration"""
    print("🚀 SPYDER B20 - Integrated Connectivity Manager")
    print("=" * 60)
    
    try:
        # Test connectivity manager
        manager = IntegratedConnectivityManager()
        print("✅ Connectivity Manager initialized")
        
        # Start monitoring
        if manager.start_monitoring():
            print("✅ Monitoring started")
            
            # Wait a bit for assessment
            time.sleep(3)
            
            # Get connectivity report
            report = manager.get_connectivity_report()
            print(f"\n📊 Connectivity Report:")
            print(f"  Overall State: {report.overall_state.value}")
            print(f"  Server: {report.server_name}")
            print(f"  Zurich Reachable: {report.zurich_reachable}")
            print(f"  VPN Status: {report.vpn_status.value}")
            print(f"  Stability Score: {report.connection_stability_score:.1f}%")
            
            if report.active_issues:
                print(f"  Issues: {len(report.active_issues)}")
                for issue in report.active_issues[:3]:
                    print(f"    - {issue}")
            
            if report.recommended_actions:
                print(f"  Recommendations: {len(report.recommended_actions)}")
                for rec in report.recommended_actions[:3]:
                    print(f"    - {rec}")
            
            # Stop monitoring
            manager.stop_monitoring()
            print("\n✅ Integrated Connectivity Manager test completed!")
        else:
            print("❌ Failed to start monitoring")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False
        
    return True

if __name__ == "__main__":
    main()
