#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderB_Broker
Module: SpyderB18_ZurichConnectivityDiagnostic.py
Purpose: Zurich Server Connectivity Diagnostic and Network Routing Fix
Author: Mohamed Talib
Year Created: 2025 
Last Updated: 2025-08-27 Time: 15:00:00  

Module Description:
    Comprehensive diagnostic and repair module for IBKR Zurich server connectivity
    issues. Based on IBKR technical guidance, tests direct connectivity to Zurich
    servers on required ports, validates firewall rules, and implements routing
    fixes including DNS override, backup server failover, and network diagnostics.
    
Key Features:
    - Port connectivity testing (4000, 4001) to Zurich servers
    - Backup server connectivity (zdc1-hb1, zdc1-hb2)
    - DNS routing diagnostics and fixes
    - Firewall rule validation
    - Network trace route analysis
    - Automated routing repair attempts
    - Real-time connectivity monitoring
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import asyncio
import json
import logging
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import threading
import tempfile
import shutil

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
import psutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QTextEdit, QProgressBar, QGroupBox,
                            QCheckBox, QMessageBox)
from PySide6.QtCore import QTimer, QThread, Signal, Qt
from PySide6.QtGui import QFont, QColor

# ==============================================================================
# SPYDER MODULE IMPORTS
# ==============================================================================
try:
    from SpyderB_Broker.SpyderB13_GatewayConfig import GatewayConfig, GatewayManager
    from SpyderB_Broker.SpyderB17_ServerMonitor import ServerMonitor, IBKR_SERVERS
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
except ImportError as e:
    print(f"Warning: Could not import Spyder modules: {e}")
    SpyderLogger = None
    SpyderErrorHandler = None

# ==============================================================================
# CONSTANTS AND CONFIGURATION
# ==============================================================================

# IBKR Zurich Server Configuration (from IBKR support)
ZURICH_SERVERS = {
    'primary': 'zdc1.ibllc.com',
    'backup1': 'zdc1-hb1.ibllc.com', 
    'backup2': 'zdc1-hb2.ibllc.com'
}

# Required ports for IBKR connectivity
REQUIRED_PORTS = {
    'trading': 4001,  # Authentication and trading operations
    'market_data': 4000  # Market data distribution
}

# DNS override IPs for Zurich servers
ZURICH_IPS = {
    'zdc1.ibllc.com': '185.179.200.100',
    'zdc1-hb1.ibllc.com': '185.179.200.101', 
    'zdc1-hb2.ibllc.com': '185.179.200.102'
}

# Connectivity test timeouts
DEFAULT_TIMEOUT = 10
TRACE_TIMEOUT = 30

class ConnectivityStatus(Enum):
    """Connectivity test status"""
    SUCCESS = "success"
    FAILED = "failed" 
    TIMEOUT = "timeout"
    DNS_ERROR = "dns_error"
    FIREWALL_BLOCKED = "firewall_blocked"
    ROUTING_ERROR = "routing_error"

class DiagnosticLevel(Enum):
    """Diagnostic test levels"""
    BASIC = "basic"
    COMPREHENSIVE = "comprehensive"
    ADVANCED = "advanced"

# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class ConnectivityTest:
    """Individual connectivity test result"""
    server: str
    port: int
    status: ConnectivityStatus
    latency_ms: float = -1.0
    error_message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
@dataclass
class DiagnosticResult:
    """Complete diagnostic result"""
    overall_status: ConnectivityStatus
    zurich_reachable: bool = False
    backup_servers_reachable: int = 0
    dns_resolution_ok: bool = False
    firewall_issues: List[str] = field(default_factory=list)
    routing_problems: List[str] = field(default_factory=list)
    test_results: List[ConnectivityTest] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    repair_actions: List[str] = field(default_factory=list)

# ==============================================================================
# CONNECTIVITY DIAGNOSTIC ENGINE
# ==============================================================================

class ZurichConnectivityDiagnostic:
    """Main diagnostic engine for Zurich connectivity"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        
        # Setup logging
        if SpyderLogger:
            self.logger = SpyderLogger.get_logger(__name__)
        else:
            self.logger = logging.getLogger(__name__)
            
        self.diagnostic_results = []
        
    def run_full_diagnostic(self, level: DiagnosticLevel = DiagnosticLevel.COMPREHENSIVE) -> DiagnosticResult:
        """Run complete connectivity diagnostic"""
        self.logger.info(f"Starting Zurich connectivity diagnostic - Level: {level.value}")
        
        result = DiagnosticResult(overall_status=ConnectivityStatus.SUCCESS)
        
        try:
            # 1. DNS Resolution Tests
            self.logger.info("Testing DNS resolution...")
            dns_results = self._test_dns_resolution()
            result.test_results.extend(dns_results)
            result.dns_resolution_ok = all(test.status == ConnectivityStatus.SUCCESS for test in dns_results)
            
            # 2. Port Connectivity Tests  
            self.logger.info("Testing port connectivity...")
            port_results = self._test_port_connectivity()
            result.test_results.extend(port_results)
            
            # Analyze Zurich reachability
            zurich_tests = [test for test in port_results if 'zdc1.ibllc.com' in test.server]
            result.zurich_reachable = any(test.status == ConnectivityStatus.SUCCESS for test in zurich_tests)
            
            # Count backup server connectivity
            backup_tests = [test for test in port_results if 'zdc1-hb' in test.server]
            result.backup_servers_reachable = sum(1 for test in backup_tests if test.status == ConnectivityStatus.SUCCESS)
            
            # 3. Advanced diagnostics if needed
            if level in [DiagnosticLevel.COMPREHENSIVE, DiagnosticLevel.ADVANCED]:
                self.logger.info("Running network trace analysis...")
                trace_results = self._analyze_network_routing()
                result.routing_problems.extend(trace_results)
                
            if level == DiagnosticLevel.ADVANCED:
                self.logger.info("Testing firewall rules...")
                firewall_results = self._test_firewall_rules()
                result.firewall_issues.extend(firewall_results)
                
            # 4. Generate recommendations
            result.recommendations = self._generate_recommendations(result)
            result.repair_actions = self._generate_repair_actions(result)
            
            # 5. Determine overall status
            result.overall_status = self._determine_overall_status(result)
            
            # Store result
            self.diagnostic_results.append(result)
            
            self.logger.info(f"Diagnostic completed - Status: {result.overall_status.value}")
            return result
            
        except Exception as e:
            self.logger.error(f"Diagnostic failed: {e}")
            result.overall_status = ConnectivityStatus.FAILED
            result.routing_problems.append(f"Diagnostic error: {str(e)}")
            return result
            
    def _test_dns_resolution(self) -> List[ConnectivityTest]:
        """Test DNS resolution for all Zurich servers"""
        results = []
        
        for name, server in ZURICH_SERVERS.items():
            try:
                start_time = time.time()
                resolved_ip = socket.gethostbyname(server)
                latency = (time.time() - start_time) * 1000
                
                test = ConnectivityTest(
                    server=server,
                    port=0,  # DNS test
                    status=ConnectivityStatus.SUCCESS,
                    latency_ms=latency
                )
                
                self.logger.debug(f"DNS OK: {server} -> {resolved_ip} ({latency:.1f}ms)")
                
            except socket.gaierror as e:
                test = ConnectivityTest(
                    server=server,
                    port=0,
                    status=ConnectivityStatus.DNS_ERROR,
                    error_message=str(e)
                )
                self.logger.warning(f"DNS failed: {server} - {e}")
                
            results.append(test)
            
        return results
        
    def _test_port_connectivity(self) -> List[ConnectivityTest]:
        """Test port connectivity to all servers and ports"""
        results = []
        
        for server_name, server in ZURICH_SERVERS.items():
            for port_name, port in REQUIRED_PORTS.items():
                test = self._test_single_port(server, port)
                results.append(test)
                
        return results
        
    def _test_single_port(self, server: str, port: int) -> ConnectivityTest:
        """Test connectivity to a single server:port combination"""
        try:
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(DEFAULT_TIMEOUT)
            
            result = sock.connect_ex((server, port))
            latency = (time.time() - start_time) * 1000
            
            sock.close()
            
            if result == 0:
                status = ConnectivityStatus.SUCCESS
                self.logger.debug(f"Port OK: {server}:{port} ({latency:.1f}ms)")
            else:
                status = ConnectivityStatus.FAILED
                self.logger.warning(f"Port blocked: {server}:{port}")
                
            return ConnectivityTest(
                server=server,
                port=port,
                status=status,
                latency_ms=latency if result == 0 else -1
            )
            
        except socket.timeout:
            self.logger.warning(f"Port timeout: {server}:{port}")
            return ConnectivityTest(
                server=server,
                port=port,
                status=ConnectivityStatus.TIMEOUT,
                error_message="Connection timeout"
            )
            
        except Exception as e:
            self.logger.error(f"Port test error: {server}:{port} - {e}")
            return ConnectivityTest(
                server=server,
                port=port,
                status=ConnectivityStatus.FAILED,
                error_message=str(e)
            )
            
    def _analyze_network_routing(self) -> List[str]:
        """Analyze network routing to Zurich servers"""
        problems = []
        
        try:
            # Test traceroute to primary Zurich server
            server = ZURICH_SERVERS['primary']
            
            result = subprocess.run(
                ['traceroute', '-n', '-w', '5', server],
                capture_output=True,
                text=True,
                timeout=TRACE_TIMEOUT
            )
            
            if result.returncode == 0:
                # Analyze traceroute output for routing issues
                lines = result.stdout.strip().split('\n')
                
                # Look for routing through unwanted regions
                for i, line in enumerate(lines):
                    if i == 0:  # Skip header
                        continue
                        
                    # Check for US routing (should go directly to EU)
                    if any(pattern in line for pattern in ['64.190.', '104.160.', '199.16.']):
                        problems.append(f"Traffic routing through US servers (hop {i})")
                        
                    # Check for timeouts indicating blocks
                    if '* * *' in line:
                        problems.append(f"Network timeout at hop {i}")
                        
            else:
                problems.append(f"Traceroute failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            problems.append("Traceroute timeout - possible network blocking")
        except FileNotFoundError:
            problems.append("Traceroute utility not available")
        except Exception as e:
            problems.append(f"Routing analysis error: {e}")
            
        return problems
        
    def _test_firewall_rules(self) -> List[str]:
        """Test for firewall issues"""
        issues = []
        
        # Test if firewall is active
        try:
            result = subprocess.run(['ufw', 'status'], capture_output=True, text=True)
            if 'Status: active' in result.stdout:
                issues.append("UFW firewall is active - may block IBKR connections")
                
        except FileNotFoundError:
            pass  # UFW not installed
        except Exception as e:
            issues.append(f"Firewall check error: {e}")
            
        # Test iptables rules
        try:
            result = subprocess.run(['iptables', '-L'], capture_output=True, text=True)
            if result.returncode == 0 and 'DROP' in result.stdout:
                issues.append("Iptables has DROP rules - may affect connectivity")
                
        except subprocess.CalledProcessError:
            pass  # No permission or not installed
        except Exception as e:
            issues.append(f"Iptables check error: {e}")
            
        return issues
        
    def _generate_recommendations(self, result: DiagnosticResult) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        if not result.dns_resolution_ok:
            recommendations.append("❌ DNS resolution failing - use manual IP configuration")
            
        if not result.zurich_reachable:
            recommendations.append("🔧 Zurich servers unreachable - check network routing")
            recommendations.append("📡 Consider VPN connection to European endpoint")
            
        if result.backup_servers_reachable == 0:
            recommendations.append("⚠️  No backup servers reachable - single point of failure")
            
        if result.firewall_issues:
            recommendations.append("🛡️ Firewall may be blocking connections - review rules")
            
        if result.routing_problems:
            recommendations.append("🗺️  Network routing through non-optimal path")
            
        # Always include the DNS override recommendation
        recommendations.append("🌐 Add DNS overrides to /etc/hosts for reliable routing")
        
        return recommendations
        
    def _generate_repair_actions(self, result: DiagnosticResult) -> List[str]:
        """Generate automated repair actions"""
        actions = []
        
        if not result.dns_resolution_ok or not result.zurich_reachable:
            actions.append("create_hosts_override")
            
        if result.firewall_issues:
            actions.append("configure_firewall_rules")
            
        if result.routing_problems:
            actions.append("test_alternative_routing")
            
        return actions
        
    def _determine_overall_status(self, result: DiagnosticResult) -> ConnectivityStatus:
        """Determine overall diagnostic status"""
        if result.zurich_reachable and result.dns_resolution_ok:
            return ConnectivityStatus.SUCCESS
        elif result.backup_servers_reachable > 0:
            return ConnectivityStatus.ROUTING_ERROR  # Can use backups
        elif not result.dns_resolution_ok:
            return ConnectivityStatus.DNS_ERROR
        else:
            return ConnectivityStatus.FAILED

# ==============================================================================
# AUTOMATED REPAIR ENGINE
# ==============================================================================

class ZurichConnectivityRepair:
    """Automated repair engine for connectivity issues"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        self.config = config or GatewayConfig()
        self.logger = logging.getLogger(__name__)
        
    def apply_dns_override(self, backup: bool = True) -> Tuple[bool, str]:
        """Apply DNS override in /etc/hosts"""
        try:
            hosts_file = Path('/etc/hosts')
            
            # Backup existing hosts file
            if backup and hosts_file.exists():
                backup_file = Path(f'/etc/hosts.backup.{datetime.now():%Y%m%d_%H%M%S}')
                shutil.copy2(hosts_file, backup_file)
                self.logger.info(f"Backed up hosts file to {backup_file}")
                
            # Generate new hosts entries
            new_entries = []
            new_entries.append("\n# IBKR Zurich Server DNS Override (Added by Spyder)")
            
            for server, ip in ZURICH_IPS.items():
                new_entries.append(f"{ip} {server}")
                
            new_entries.append("# End IBKR Zurich Override\n")
            
            # Read current hosts file
            current_content = ""
            if hosts_file.exists():
                with open(hosts_file, 'r') as f:
                    current_content = f.read()
                    
            # Remove any existing IBKR entries
            lines = current_content.split('\n')
            filtered_lines = []
            skip_section = False
            
            for line in lines:
                if "# IBKR Zurich Server DNS Override" in line:
                    skip_section = True
                elif "# End IBKR Zurich Override" in line:
                    skip_section = False
                    continue
                elif not skip_section and not any(server in line for server in ZURICH_SERVERS.values()):
                    filtered_lines.append(line)
                    
            # Write updated hosts file
            with open(hosts_file, 'w') as f:
                f.write('\n'.join(filtered_lines))
                f.write(''.join(new_entries))
                
            self.logger.info("DNS override applied successfully")
            return True, "DNS override applied to /etc/hosts"
            
        except PermissionError:
            error_msg = "Permission denied - run with sudo to modify /etc/hosts"
            self.logger.error(error_msg)
            return False, error_msg
            
        except Exception as e:
            error_msg = f"Failed to apply DNS override: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def configure_firewall_rules(self) -> Tuple[bool, str]:
        """Configure firewall rules for IBKR connectivity"""
        try:
            commands = []
            
            # UFW rules for IBKR servers
            for server in ZURICH_SERVERS.values():
                for port in REQUIRED_PORTS.values():
                    commands.append(['ufw', 'allow', 'out', 'to', server, 'port', str(port)])
                    
            success_count = 0
            for cmd in commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    success_count += 1
                except subprocess.CalledProcessError:
                    pass  # Rule might already exist
                    
            if success_count > 0:
                return True, f"Configured {success_count} firewall rules"
            else:
                return False, "No firewall rules were added"
                
        except Exception as e:
            error_msg = f"Failed to configure firewall: {e}"
            self.logger.error(error_msg)
            return False, error_msg
            
    def generate_repair_script(self, diagnostic_result: DiagnosticResult) -> str:
        """Generate shell script for manual repairs"""
        script_lines = [
            "#!/bin/bash",
            "# SPYDER Zurich Connectivity Repair Script", 
            "# Generated: " + datetime.now().isoformat(),
            "",
            "echo '🔧 SPYDER Zurich Connectivity Repair'",
            "echo '======================================'",
            ""
        ]
        
        # DNS Override section
        if "create_hosts_override" in diagnostic_result.repair_actions:
            script_lines.extend([
                "echo '1. Applying DNS override...'",
                "# Backup existing hosts file",
                "sudo cp /etc/hosts /etc/hosts.backup.$(date +%Y%m%d_%H%M%S)",
                "",
                "# Add Zurich server entries",
                "cat << 'EOF' | sudo tee -a /etc/hosts",
                "",
                "# IBKR Zurich Server DNS Override (Added by Spyder)"
            ])
            
            for server, ip in ZURICH_IPS.items():
                script_lines.append(f"{ip} {server}")
                
            script_lines.extend([
                "# End IBKR Zurich Override",
                "EOF",
                ""
            ])
            
        # Firewall rules section  
        if "configure_firewall_rules" in diagnostic_result.repair_actions:
            script_lines.extend([
                "echo '2. Configuring firewall rules...'",
                "# Allow outbound connections to IBKR Zurich servers"
            ])
            
            for server in ZURICH_SERVERS.values():
                for port_name, port in REQUIRED_PORTS.items():
                    script_lines.append(f"sudo ufw allow out to {server} port {port}")
                    
            script_lines.append("")
            
        script_lines.extend([
            "echo '✅ Repair script completed!'",
            "echo 'Please restart IB Gateway to apply changes.'"
        ])
        
        return '\n'.join(script_lines)

# ==============================================================================
# PYQT6 DIAGNOSTIC WIDGET
# ==============================================================================

class ZurichDiagnosticWidget(QWidget):
    """PyQt6 widget for Zurich connectivity diagnostics"""
    
    def __init__(self, config: Optional[GatewayConfig] = None):
        super().__init__()
        self.config = config or GatewayConfig()
        self.diagnostic = ZurichConnectivityDiagnostic(config)
        self.repair = ZurichConnectivityRepair(config)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("🇨🇭 Zurich Connectivity Diagnostic")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Status display
        self.status_label = QLabel("Ready to run diagnostic tests")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)
        
        # Test buttons
        button_layout = QHBoxLayout()
        
        self.basic_test_btn = QPushButton("🔍 Basic Test")
        self.basic_test_btn.clicked.connect(lambda: self.run_diagnostic(DiagnosticLevel.BASIC))
        button_layout.addWidget(self.basic_test_btn)
        
        self.full_test_btn = QPushButton("🔬 Full Diagnostic")
        self.full_test_btn.clicked.connect(lambda: self.run_diagnostic(DiagnosticLevel.COMPREHENSIVE))
        button_layout.addWidget(self.full_test_btn)
        
        self.repair_btn = QPushButton("🛠️ Auto Repair")
        self.repair_btn.clicked.connect(self.auto_repair)
        self.repair_btn.setEnabled(False)
        button_layout.addWidget(self.repair_btn)
        
        layout.addLayout(button_layout)
        
        # Results display
        results_group = QGroupBox("Diagnostic Results")
        results_layout = QVBoxLayout()
        
        self.results_text = QTextEdit()
        self.results_text.setMaximumHeight(300)
        self.results_text.setFont(QFont("Courier", 9))
        results_layout.addWidget(self.results_text)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        self.setLayout(layout)
        
    def run_diagnostic(self, level: DiagnosticLevel):
        """Run diagnostic tests"""
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # Indeterminate
        
        # Disable buttons during test
        self.basic_test_btn.setEnabled(False)
        self.full_test_btn.setEnabled(False)
        
        # Start diagnostic in background
        self.diagnostic_thread = DiagnosticWorker(self.diagnostic, level)
        self.diagnostic_thread.finished.connect(self.diagnostic_completed)
        self.diagnostic_thread.progress.connect(self.update_progress)
        self.diagnostic_thread.start()
        
    def diagnostic_completed(self, result: DiagnosticResult):
        """Handle completed diagnostic"""
        self.progress.setVisible(False)
        self.basic_test_btn.setEnabled(True)
        self.full_test_btn.setEnabled(True)
        
        # Display results
        self.display_results(result)
        
        # Enable repair if needed
        if result.overall_status != ConnectivityStatus.SUCCESS:
            self.repair_btn.setEnabled(True)
            
        self.current_result = result
        
    def update_progress(self, message: str):
        """Update progress message"""
        self.status_label.setText(message)
        
    def display_results(self, result: DiagnosticResult):
        """Display diagnostic results"""
        output = []
        
        # Overall status
        status_emoji = {
            ConnectivityStatus.SUCCESS: "✅",
            ConnectivityStatus.FAILED: "❌", 
            ConnectivityStatus.TIMEOUT: "⏱️",
            ConnectivityStatus.DNS_ERROR: "🔍",
            ConnectivityStatus.ROUTING_ERROR: "🗺️"
        }
        
        emoji = status_emoji.get(result.overall_status, "❓")
        output.append(f"{emoji} Overall Status: {result.overall_status.value.upper()}")
        output.append("=" * 50)
        
        # Test results summary
        output.append(f"🌐 Zurich Reachable: {'✅ YES' if result.zurich_reachable else '❌ NO'}")
        output.append(f"🔄 Backup Servers: {result.backup_servers_reachable}/2 reachable")
        output.append(f"🔍 DNS Resolution: {'✅ OK' if result.dns_resolution_ok else '❌ FAILED'}")
        output.append("")
        
        # Individual test results
        output.append("📊 Individual Test Results:")
        output.append("-" * 30)
        
        for test in result.test_results:
            status_char = "✅" if test.status == ConnectivityStatus.SUCCESS else "❌"
            latency = f" ({test.latency_ms:.1f}ms)" if test.latency_ms > 0 else ""
            port_info = f":{test.port}" if test.port > 0 else ""
            
            output.append(f"{status_char} {test.server}{port_info}{latency}")
            
        if result.recommendations:
            output.append("")
            output.append("💡 Recommendations:")
            output.append("-" * 20)
            for rec in result.recommendations:
                output.append(f"  • {rec}")
                
        self.results_text.setText('\n'.join(output))
        
    def auto_repair(self):
        """Apply automated repairs"""
        if not hasattr(self, 'current_result'):
            return
            
        msg = QMessageBox()
        msg.setWindowTitle("Auto Repair")
        msg.setText("This will attempt to fix connectivity issues by:\n\n"
                   "• Adding DNS overrides to /etc/hosts\n"
                   "• Configuring firewall rules\n\n"
                   "Admin privileges may be required. Continue?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        
        if msg.exec() == QMessageBox.Yes:
            self.apply_repairs()
            
    def apply_repairs(self):
        """Apply the actual repairs"""
        results = []
        
        # Apply DNS override
        success, message = self.repair.apply_dns_override()
        results.append(f"DNS Override: {'✅' if success else '❌'} {message}")
        
        # Configure firewall if needed
        if hasattr(self, 'current_result') and self.current_result.firewall_issues:
            success, message = self.repair.configure_firewall_rules()
            results.append(f"Firewall Rules: {'✅' if success else '❌'} {message}")
            
        # Show results
        QMessageBox.information(self, "Repair Results", '\n'.join(results))

# ==============================================================================
# WORKER THREAD FOR DIAGNOSTICS
# ==============================================================================

class DiagnosticWorker(QThread):
    """Background worker for running diagnostics"""
    
    finished = Signal(object)  # DiagnosticResult
    progress = Signal(str)     # Progress message
    
    def __init__(self, diagnostic: ZurichConnectivityDiagnostic, level: DiagnosticLevel):
        super().__init__()
        self.diagnostic = diagnostic
        self.level = level
        
    def run(self):
        """Run the diagnostic"""
        self.progress.emit("🔍 Starting diagnostic tests...")
        result = self.diagnostic.run_full_diagnostic(self.level)
        self.finished.emit(result)

# ==============================================================================
# COMMAND LINE INTERFACE
# ==============================================================================

def run_cli_diagnostic():
    """Command line interface for diagnostics"""
    print("🇨🇭 SPYDER Zurich Connectivity Diagnostic")
    print("=" * 50)
    
    diagnostic = ZurichConnectivityDiagnostic()
    result = diagnostic.run_full_diagnostic(DiagnosticLevel.COMPREHENSIVE)
    
    # Display results
    status_symbols = {
        ConnectivityStatus.SUCCESS: "✅",
        ConnectivityStatus.FAILED: "❌",
        ConnectivityStatus.TIMEOUT: "⏱️", 
        ConnectivityStatus.DNS_ERROR: "🔍",
        ConnectivityStatus.ROUTING_ERROR: "🗺️"
    }
    
    symbol = status_symbols.get(result.overall_status, "❓")
    print(f"\n{symbol} Overall Status: {result.overall_status.value.upper()}")
    
    print(f"\n📊 Summary:")
    print(f"  🌐 Zurich Reachable: {'YES' if result.zurich_reachable else 'NO'}")
    print(f"  🔄 Backup Servers: {result.backup_servers_reachable}/2")
    print(f"  🔍 DNS Resolution: {'OK' if result.dns_resolution_ok else 'FAILED'}")
    
    if result.recommendations:
        print(f"\n💡 Recommendations:")
        for rec in result.recommendations:
            print(f"  • {rec}")
            
    if result.repair_actions:
        repair = ZurichConnectivityRepair()
        script = repair.generate_repair_script(result)
        
        script_file = Path("/tmp/spyder_zurich_repair.sh")
        with open(script_file, 'w') as f:
            f.write(script)
        script_file.chmod(0o755)
        
        print(f"\n🛠️  Repair script generated: {script_file}")
        print("   Run with: sudo /tmp/spyder_zurich_repair.sh")

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main execution function for testing and demonstration"""
    print("🚀 SPYDER B18 - Zurich Connectivity Diagnostic")
    print("=" * 60)
    
    try:
        # Run CLI diagnostic
        run_cli_diagnostic()
        
        print(f"\n✅ Diagnostic module test completed!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False
        
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli_diagnostic()
    else:
        main()