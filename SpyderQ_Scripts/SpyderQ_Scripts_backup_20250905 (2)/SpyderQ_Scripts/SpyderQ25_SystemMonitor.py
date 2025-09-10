#!/usr/bin/env python3
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Module: SpyderQ25_SystemMonitor.py
# Group: Q (Scripts/Monitoring)
# Purpose: Comprehensive system monitoring with dashboard integration
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 12:00:00
#
# Description:
#     Advanced monitoring script that provides real-time status of all Spyder
#     components including IB Gateway, AI agents, risk systems, and performance
#     metrics. Can run standalone or integrate with dashboard.
# ===============================================================================

import argparse
import json
import os
import socket
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psutil

# Add Spyder to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ===============================================================================
# CONFIGURATION & CONSTANTS
# ===============================================================================

SPYDER_HOME = Path("/home/adam/Projects/Spyder")
LOG_DIR = SPYDER_HOME / "logs"
DATA_DIR = SPYDER_HOME / "data"
METRICS_PORT = 8000
IB_PAPER_PORT = 4002
IB_LIVE_PORT = 4001


class ComponentStatus(Enum):
    """Component status levels"""

    RUNNING = "✅ Running"
    STOPPED = "❌ Stopped"
    WARNING = "⚠️ Warning"
    STARTING = "🔄 Starting"
    ERROR = "🔥 Error"
    UNKNOWN = "❓ Unknown"


@dataclass
class SystemMetrics:
    """System performance metrics"""

    cpu_percent: float
    memory_percent: float
    memory_used_gb: float
    memory_total_gb: float
    disk_usage_percent: float
    network_sent_mb: float
    network_recv_mb: float
    open_files: int
    thread_count: int
    process_count: int


@dataclass
class ComponentHealth:
    """Component health information"""

    name: str
    status: ComponentStatus
    pid: Optional[int]
    cpu_percent: float
    memory_mb: float
    uptime_seconds: int
    last_error: Optional[str]
    details: Dict


# ===============================================================================
# MONITORING CORE
# ===============================================================================


class SpyderSystemMonitor:
    """Main system monitoring class"""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize monitor with configuration"""
        self.config_path = config_path or SPYDER_HOME / ".env"
        self.start_time = datetime.now()
        self.components = {}
        self.alerts = []
        self.metrics_history = []

        # Component definitions
        self.component_specs = {
            "ib_gateway": {
                "process_names": ["ibgateway", "java"],
                "identifier": "ibgateway",
                "ports": [IB_PAPER_PORT, IB_LIVE_PORT],
                "critical": True,
            },
            "master_controller": {
                "module": "SpyderA06_MasterController",
                "pidfile": LOG_DIR / "master.pid",
                "critical": True,
            },
            "watchdog": {
                "module": "SpyderB14_MultiClientWatchdog",
                "pidfile": LOG_DIR / "watchdog.pid",
                "critical": True,
            },
            "metrics": {
                "module": "SpyderB15_PrometheusMetrics",
                "pidfile": LOG_DIR / "metrics.pid",
                "port": METRICS_PORT,
                "critical": True,
            },
            "meta_coordinator": {
                "module": "SpyderX16_MetaCoordinator",
                "pidfile": LOG_DIR / "coordinator.pid",
                "critical": False,
            },
            "risk_manager": {
                "module": "SpyderE11_MaxLossProtection",
                "pidfile": LOG_DIR / "risk.pid",
                "critical": True,
            },
            "dashboard": {
                "module": "SpyderG05_TradingDashboard",
                "process_names": ["python"],
                "identifier": "TradingDashboard",
                "critical": False,
            },
        }

    # ==========================================================================
    # SYSTEM METRICS
    # ==========================================================================

    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(SPYDER_HOME))
        network = psutil.net_io_counters()

        return SystemMetrics(
            cpu_percent=psutil.cpu_percent(interval=1),
            memory_percent=memory.percent,
            memory_used_gb=memory.used / (1024**3),
            memory_total_gb=memory.total / (1024**3),
            disk_usage_percent=disk.percent,
            network_sent_mb=network.bytes_sent / (1024**2),
            network_recv_mb=network.bytes_recv / (1024**2),
            open_files=len(psutil.Process().open_files()),
            thread_count=psutil.Process().num_threads(),
            process_count=len(psutil.pids()),
        )

    # ==========================================================================
    # COMPONENT MONITORING
    # ==========================================================================

    def check_component(self, name: str, spec: Dict) -> ComponentHealth:
        """Check health of a specific component"""
        status = ComponentStatus.STOPPED
        pid = None
        cpu_percent = 0.0
        memory_mb = 0.0
        uptime_seconds = 0
        last_error = None
        details = {}

        try:
            # Check by PID file
            if "pidfile" in spec and spec["pidfile"].exists():
                with open(spec["pidfile"]) as f:
                    pid = int(f.read().strip())

                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    status = ComponentStatus.RUNNING
                    cpu_percent = proc.cpu_percent()
                    memory_mb = proc.memory_info().rss / (1024**2)
                    uptime_seconds = int(time.time() - proc.create_time())
                else:
                    status = ComponentStatus.ERROR
                    last_error = "Process died (stale PID file)"

            # Check by process name
            elif "process_names" in spec:
                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    if proc.info["name"] in spec["process_names"]:
                        if "identifier" in spec:
                            cmdline = " ".join(proc.info.get("cmdline", []))
                            if spec["identifier"] not in cmdline:
                                continue

                        pid = proc.info["pid"]
                        proc_obj = psutil.Process(pid)
                        status = ComponentStatus.RUNNING
                        cpu_percent = proc_obj.cpu_percent()
                        memory_mb = proc_obj.memory_info().rss / (1024**2)
                        uptime_seconds = int(time.time() - proc_obj.create_time())
                        break

            # Check by module name
            elif "module" in spec:
                for proc in psutil.process_iter(["pid", "cmdline"]):
                    cmdline = " ".join(proc.info.get("cmdline", []))
                    if spec["module"] in cmdline:
                        pid = proc.info["pid"]
                        proc_obj = psutil.Process(pid)
                        status = ComponentStatus.RUNNING
                        cpu_percent = proc_obj.cpu_percent()
                        memory_mb = proc_obj.memory_info().rss / (1024**2)
                        uptime_seconds = int(time.time() - proc_obj.create_time())
                        break

            # Check ports if specified
            if "port" in spec and status == ComponentStatus.RUNNING:
                if not self._check_port(spec["port"]):
                    status = ComponentStatus.WARNING
                    details["port_status"] = f"Port {spec['port']} not accessible"

            elif "ports" in spec:
                accessible_ports = [p for p in spec["ports"] if self._check_port(p)]
                if accessible_ports:
                    status = ComponentStatus.RUNNING
                    details["accessible_ports"] = accessible_ports
                else:
                    details["port_status"] = "No ports accessible"

        except Exception as e:
            status = ComponentStatus.ERROR
            last_error = str(e)

        return ComponentHealth(
            name=name,
            status=status,
            pid=pid,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            uptime_seconds=uptime_seconds,
            last_error=last_error,
            details=details,
        )

    def _check_port(self, port: int) -> bool:
        """Check if port is accessible"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result == 0

    # ==========================================================================
    # CLIENT STATUS
    # ==========================================================================

    def get_client_status(self) -> Dict:
        """Get status of all 9 trading clients"""
        client_status = {}

        try:
            # Check Prometheus metrics endpoint
            import requests

            response = requests.get(f"http://localhost:{METRICS_PORT}/metrics", timeout=2)

            if response.status_code == 200:
                metrics = response.text

                # Parse client connection status
                for line in metrics.split("\n"):
                    if "ib_client_connected" in line and "#" not in line:
                        if "client_id=" in line:
                            # Extract client ID and status
                            import re

                            match = re.search(r'client_id="(\d)".*} (\d)', line)
                            if match:
                                client_id = int(match.group(1))
                                connected = bool(int(match.group(2)))
                                client_status[client_id] = {
                                    "connected": connected,
                                    "status": "✅ Connected" if connected else "❌ Disconnected",
                                }

        except Exception as e:
            print(f"Could not fetch client metrics: {e}")

        # Fill in missing clients
        for i in range(9):
            if i not in client_status:
                client_status[i] = {"connected": False, "status": "❓ Unknown"}

        return client_status

    # ==========================================================================
    # HEALTH SCORE
    # ==========================================================================

    def calculate_health_score(self) -> int:
        """Calculate overall system health score (0-100)"""
        score = 100

        # Check critical components
        for name, spec in self.component_specs.items():
            if spec.get("critical", False):
                health = self.check_component(name, spec)
                if health.status != ComponentStatus.RUNNING:
                    score -= 20
                elif health.status == ComponentStatus.WARNING:
                    score -= 10

        # Check system resources
        metrics = self.get_system_metrics()
        if metrics.cpu_percent > 80:
            score -= 10
        if metrics.memory_percent > 85:
            score -= 10
        if metrics.disk_usage_percent > 90:
            score -= 5

        return max(0, score)

    # ==========================================================================
    # REPORTING
    # ==========================================================================

    def generate_report(self, format: str = "text") -> str:
        """Generate monitoring report"""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "uptime": str(datetime.now() - self.start_time),
            "health_score": self.calculate_health_score(),
            "system_metrics": asdict(self.get_system_metrics()),
            "components": {},
            "clients": self.get_client_status(),
            "alerts": self.alerts,
        }

        # Check all components
        for name, spec in self.component_specs.items():
            health = self.check_component(name, spec)
            report_data["components"][name] = {
                "status": health.status.value,
                "pid": health.pid,
                "cpu_percent": health.cpu_percent,
                "memory_mb": health.memory_mb,
                "uptime": str(timedelta(seconds=health.uptime_seconds)),
                "error": health.last_error,
                "details": health.details,
            }

        if format == "json":
            return json.dumps(report_data, indent=2)
        else:
            return self._format_text_report(report_data)

    def _format_text_report(self, data: Dict) -> str:
        """Format report as text"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"SPYDER SYSTEM MONITOR - {data['timestamp']}")
        lines.append("=" * 60)
        lines.append(f"Health Score: {data['health_score']}/100")
        lines.append(f"System Uptime: {data['uptime']}")
        lines.append("")

        lines.append("SYSTEM METRICS:")
        lines.append("-" * 40)
        metrics = data["system_metrics"]
        lines.append(f"  CPU: {metrics['cpu_percent']:.1f}%")
        lines.append(
            f"  Memory: {
                metrics['memory_used_gb']:.1f}/{
                metrics['memory_total_gb']:.1f} GB ({
                metrics['memory_percent']:.1f}%)"
        )
        lines.append(f"  Disk: {metrics['disk_usage_percent']:.1f}%")
        lines.append(
            f"  Network: ↑{
                metrics['network_sent_mb']:.1f} MB ↓{
                metrics['network_recv_mb']:.1f} MB"
        )
        lines.append("")

        lines.append("COMPONENTS:")
        lines.append("-" * 40)
        for name, info in data["components"].items():
            critical = "🔴" if self.component_specs[name].get("critical") else ""
            lines.append(f"  {critical} {name}: {info['status']}")
            if info["pid"]:
                lines.append(
                    f"      PID: {
                        info['pid']} | CPU: {
                        info['cpu_percent']:.1f}% | Mem: {
                        info['memory_mb']:.1f} MB | Up: {
                        info['uptime']}"
                )
            if info["error"]:
                lines.append(f"      ERROR: {info['error']}")
        lines.append("")

        lines.append("CLIENT CONNECTIONS:")
        lines.append("-" * 40)
        for client_id, info in sorted(data["clients"].items()):
            lines.append(f"  Client {client_id}: {info['status']}")
        lines.append("")

        if data["alerts"]:
            lines.append("ACTIVE ALERTS:")
            lines.append("-" * 40)
            for alert in data["alerts"]:
                lines.append(f"  ⚠️ {alert}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    # ==========================================================================
    # CONTINUOUS MONITORING
    # ==========================================================================

    def monitor_loop(self, interval: int = 5, dashboard: bool = False):
        """Run continuous monitoring loop"""
        print(f"Starting Spyder System Monitor (interval: {interval}s)")
        print("Press Ctrl+C to stop")
        print("")

        try:
            while True:
                # Clear screen if not in dashboard mode
                if not dashboard:
                    os.system("clear" if os.name == "posix" else "cls")

                # Generate and display report
                report = self.generate_report("text")
                print(report)

                # Check for critical issues
                health_score = self.calculate_health_score()
                if health_score < 50:
                    print("\n🔥 CRITICAL: System health below 50%!")

                # Sleep until next update
                time.sleep(interval)

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")

    # ==========================================================================
    # ALERT MANAGEMENT
    # ==========================================================================

    def check_alerts(self):
        """Check for system alerts"""
        self.alerts.clear()

        # Check components
        for name, spec in self.component_specs.items():
            if spec.get("critical", False):
                health = self.check_component(name, spec)
                if health.status == ComponentStatus.STOPPED:
                    self.alerts.append(f"Critical component '{name}' is not running")
                elif health.status == ComponentStatus.ERROR:
                    self.alerts.append(
                        f"Critical component '{name}' has errors: {
                            health.last_error}"
                    )

        # Check resources
        metrics = self.get_system_metrics()
        if metrics.cpu_percent > 90:
            self.alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")
        if metrics.memory_percent > 90:
            self.alerts.append(f"High memory usage: {metrics.memory_percent:.1f}%")
        if metrics.disk_usage_percent > 95:
            self.alerts.append(f"Low disk space: {metrics.disk_usage_percent:.1f}% used")


# ===============================================================================
# MAIN EXECUTION
# ===============================================================================


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Spyder System Monitor")
    parser.add_argument(
        "--interval", type=int, default=5, help="Update interval in seconds (default: 5)"
    )
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--export", type=str, help="Export report to file")
    parser.add_argument(
        "--dashboard", action="store_true", help="Run in dashboard mode (no screen clear)"
    )

    args = parser.parse_args()

    # Create monitor
    monitor = SpyderSystemMonitor()

    # Check alerts
    monitor.check_alerts()

    if args.once:
        # Single run
        report = monitor.generate_report("json" if args.json else "text")

        if args.export:
            with open(args.export, "w") as f:
                f.write(report)
            print(f"Report exported to {args.export}")
        else:
            print(report)
    else:
        # Continuous monitoring
        monitor.monitor_loop(args.interval, args.dashboard)


if __name__ == "__main__":
    main()
