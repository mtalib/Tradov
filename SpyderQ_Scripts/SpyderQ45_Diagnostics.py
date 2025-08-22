#!/usr/bin/env python3
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Module: SpyderQ45_Diagnostics.py
# Group: Q (Scripts/Maintenance)
# Purpose: Advanced diagnostics and troubleshooting tool (ib_async compatible)
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-08-22 Time: 14:45:00
#
# Description:
#     Comprehensive diagnostic tool that identifies and helps resolve common
#     issues with the Spyder trading system. Includes automated fixes, detailed
#     error analysis, and system health recommendations. Updated to use ib_async
#     for IB Gateway 10.37 compatibility.
# ===============================================================================

import argparse
import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil

# Add Spyder to path
sys.path.insert(0, str(Path("/home/adam/Projects/Spyder")))

# ===============================================================================
# CONFIGURATION
# ===============================================================================

SPYDER_HOME = Path("/home/adam/Projects/Spyder")
LOG_DIR = SPYDER_HOME / "logs"
DATA_DIR = SPYDER_HOME / "data"
SCRIPTS_DIR = SPYDER_HOME / "scripts"
VENV_PATH = SPYDER_HOME / "spyder_venv"

# Color codes for terminal output


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


# ===============================================================================
# DATA STRUCTURES
# ===============================================================================


class IssueLevel(Enum):
    """Issue severity levels"""

    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Issue:
    """Represents a system issue"""

    category: str
    level: IssueLevel
    description: str
    details: str
    solution: Optional[str] = None
    auto_fix_available: bool = False


@dataclass
class DiagnosticResult:
    """Complete diagnostic result"""

    timestamp: datetime
    issues: List[Issue]
    system_info: Dict
    recommendations: List[str]
    health_score: int


# ===============================================================================
# DIAGNOSTIC ENGINE
# ===============================================================================


class SpyderDiagnostics:
    """Main diagnostics engine"""

    def __init__(self, verbose: bool = False, auto_fix: bool = False):
        """Initialize diagnostics"""
        self.verbose = verbose
        self.auto_fix = auto_fix
        self.issues = []
        self.system_info = {}
        self.recommendations = []

    # ==========================================================================
    # MAIN DIAGNOSTIC METHODS
    # ==========================================================================

    def run_full_diagnostics(self) -> DiagnosticResult:
        """Run complete system diagnostics"""
        print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")
        print(f"{Colors.BLUE}  SPYDER DIAGNOSTICS TOOL{Colors.RESET}")
        print(f"{Colors.BLUE}{'='*60}{Colors.RESET}\n")

        # Collect system info
        self._collect_system_info()

        # Run diagnostic categories
        self._diagnose_environment()
        self._diagnose_dependencies()
        self._diagnose_network()
        self._diagnose_ib_gateway()
        self._diagnose_modules()
        self._diagnose_processes()
        self._diagnose_logs()
        self._diagnose_performance()
        self._diagnose_configuration()

        # Generate recommendations
        self._generate_recommendations()

        # Calculate health score
        health_score = self._calculate_health_score()

        # Create result
        result = DiagnosticResult(
            timestamp=datetime.now(),
            issues=self.issues,
            system_info=self.system_info,
            recommendations=self.recommendations,
            health_score=health_score,
        )

        # Print summary
        self._print_summary(result)

        return result

    # ==========================================================================
    # INDIVIDUAL DIAGNOSTIC METHODS
    # ==========================================================================

    def _collect_system_info(self):
        """Collect basic system information"""
        self.system_info = {
            "python_version": sys.version,
            "platform": sys.platform,
            "cpu_count": psutil.cpu_count(),
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
            "disk_space_gb": round(
                psutil.disk_usage(str(SPYDER_HOME)).total / (1024**3), 1
            ),
            "spyder_home": str(SPYDER_HOME),
            "timestamp": datetime.now().isoformat(),
        }

    def _diagnose_environment(self):
        """Diagnose Python environment"""
        print(f"{Colors.CYAN}1. Environment Diagnostics{Colors.RESET}")

        # Check Python version
        python_version = sys.version_info
        if python_version < (3, 8):
            self._add_issue(
                "Environment",
                IssueLevel.CRITICAL,
                f"Python version too old: {python_version.major}.{python_version.minor}",
                "Spyder requires Python 3.8+",
                "Upgrade Python to 3.8 or higher",
            )
        else:
            self._print_ok(f"Python {python_version.major}.{python_version.minor}.{python_version.micro}")

        # Check virtual environment
        if hasattr(sys, "real_prefix") or (
            hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
        ):
            self._print_ok("Virtual environment detected")
        else:
            self._add_issue(
                "Environment",
                IssueLevel.WARNING,
                "Not running in virtual environment",
                "May cause package conflicts",
                "Create and activate virtual environment",
            )

        # Check Spyder home
        if not SPYDER_HOME.exists():
            self._add_issue(
                "Environment",
                IssueLevel.CRITICAL,
                f"Spyder home not found: {SPYDER_HOME}",
                "Cannot locate Spyder installation",
                f"Ensure Spyder is installed at {SPYDER_HOME}",
            )
        else:
            self._print_ok(f"Spyder home found: {SPYDER_HOME}")

    def _diagnose_dependencies(self):
        """Diagnose Python dependencies"""
        print(f"\n{Colors.CYAN}2. Dependency Diagnostics{Colors.RESET}")

        critical_packages = {
            "ib_async": "IB API wrapper",
            "pandas": "Data analysis",
            "numpy": "Numerical computing",
            "PyQt6": "GUI framework",
            "prometheus_client": "Metrics",
            "psutil": "System monitoring",
        }

        for package, description in critical_packages.items():
            try:
                spec = importlib.util.find_spec(package)
                if spec is None:
                    self._add_issue(
                        "Dependencies",
                        IssueLevel.ERROR,
                        f"Missing package: {package}",
                        f"Required for: {description}",
                        f"Install with: pip install {package}",
                    )
                else:
                    self._print_ok(f"{package} installed")
            except Exception as e:
                self._add_issue(
                    "Dependencies",
                    IssueLevel.ERROR,
                    f"Error checking {package}",
                    str(e),
                    f"Reinstall with: pip install --force-reinstall {package}",
                )

    def _diagnose_network(self):
        """Diagnose network connectivity"""
        print(f"\n{Colors.CYAN}3. Network Diagnostics{Colors.RESET}")

        # Check localhost
        try:
            socket.gethostbyname("localhost")
            self._print_ok("Localhost resolves")
        except BaseException:
            self._add_issue(
                "Network",
                IssueLevel.CRITICAL,
                "Cannot resolve localhost",
                "Network configuration issue",
                "Check /etc/hosts file",
            )

        # Check IB Gateway ports
        ports_to_check = [
            (4002, "IB Gateway Paper"),
            (4001, "IB Gateway Live"),
            (8000, "Prometheus Metrics"),
        ]

        for port, service in ports_to_check:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()

            if result == 0:
                self._print_ok(f"Port {port} ({service}) is open")
            else:
                level = IssueLevel.WARNING if port == 8000 else IssueLevel.INFO
                self._add_issue(
                    "Network",
                    level,
                    f"Port {port} ({service}) is closed",
                    "Service may not be running",
                    f"Start {service}",
                )

    def _diagnose_ib_gateway(self):
        """Diagnose IB Gateway status"""
        print(f"\n{Colors.CYAN}4. IB Gateway Diagnostics{Colors.RESET}")

        # Check if IB Gateway is running
        ib_processes = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline", []))
                if "ibgateway" in cmdline.lower() or "clientportal" in cmdline.lower():
                    ib_processes.append(proc)
            except BaseException:
                pass

        if ib_processes:
            self._print_ok(f"IB Gateway running (PID: {ib_processes[0].pid})")
        else:
            self._add_issue(
                "IB Gateway",
                IssueLevel.ERROR,
                "IB Gateway not running",
                "Cannot connect to Interactive Brokers",
                "Start IB Gateway or TWS",
            )

        # Test connection to IB
        try:
            # Import ib_async for connection test
            from ib_async import IB
            
            ib = IB()
            connected = False
            
            # Try paper trading port first
            try:
                ib.connect("127.0.0.1", 4002, clientId=999)
                connected = True
                self._print_ok("Connected to IB Gateway (Paper)")
                ib.disconnect()
            except Exception:
                # Try live port
                try:
                    ib.connect("127.0.0.1", 4001, clientId=999)
                    connected = True
                    self._print_ok("Connected to IB Gateway (Live)")
                    ib.disconnect()
                except Exception as e:
                    self._add_issue(
                        "IB Gateway",
                        IssueLevel.ERROR,
                        "Cannot connect to IB Gateway",
                        str(e),
                        "Check IB Gateway is running and accessible",
                    )

        except ImportError:
            self._add_issue(
                "IB Gateway",
                IssueLevel.ERROR,
                "Cannot test IB connection",
                "ib_async not available",
                "Install ib_async: pip install ib_async",
            )

    def _diagnose_modules(self):
        """Diagnose Spyder modules"""
        print(f"\n{Colors.CYAN}5. Module Diagnostics{Colors.RESET}")

        # Key modules to check
        modules_to_check = [
            "SpyderA_Core.SpyderA01_Main",
            "SpyderB_Broker.SpyderB01_SpyderClient",
            "SpyderC_MarketData.SpyderC01_DataFeed",
            "SpyderD_Strategies.SpyderD01_BaseStrategy",
            "SpyderU_Utilities.SpyderU01_Logger",
        ]

        for module_name in modules_to_check:
            try:
                importlib.import_module(module_name)
                self._print_ok(f"{module_name} imports successfully")
            except Exception as e:
                self._add_issue(
                    "Modules",
                    IssueLevel.ERROR,
                    f"Cannot import {module_name}",
                    str(e),
                    "Check module exists and has no syntax errors",
                )

    def _diagnose_processes(self):
        """Diagnose running processes"""
        print(f"\n{Colors.CYAN}6. Process Diagnostics{Colors.RESET}")

        # Check for Spyder processes
        spyder_processes = []
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline", []))
                if "Spyder" in cmdline or "spyder" in cmdline:
                    spyder_processes.append(proc)
            except BaseException:
                pass

        if spyder_processes:
            self._print_ok(f"Found {len(spyder_processes)} Spyder process(es)")
            for proc in spyder_processes[:5]:  # Show first 5
                print(f"    PID {proc.pid}: {proc.info['name']}")
        else:
            self._print_info("No Spyder processes running")

        # Check resource usage
        cpu_percent = psutil.cpu_percent(interval=1)
        mem_percent = psutil.virtual_memory().percent

        if cpu_percent > 80:
            self._add_issue(
                "Performance",
                IssueLevel.WARNING,
                f"High CPU usage: {cpu_percent}%",
                "System may be overloaded",
                "Check for runaway processes",
            )

        if mem_percent > 85:
            self._add_issue(
                "Performance",
                IssueLevel.WARNING,
                f"High memory usage: {mem_percent}%",
                "System may run out of memory",
                "Close unnecessary applications",
            )

    def _diagnose_logs(self):
        """Diagnose log files for errors"""
        print(f"\n{Colors.CYAN}7. Log File Diagnostics{Colors.RESET}")

        if not LOG_DIR.exists():
            self._add_issue(
                "Logs",
                IssueLevel.WARNING,
                "Log directory not found",
                f"Expected at: {LOG_DIR}",
                f"Create with: mkdir -p {LOG_DIR}",
            )
            return

        # Check recent errors in logs
        error_count = 0
        critical_errors = []

        for log_file in LOG_DIR.rglob("*.log"):
            if log_file.stat().st_size > 0:
                try:
                    with open(log_file, "r", errors="ignore") as f:
                        # Read last 100 lines
                        lines = f.readlines()[-100:]
                        for line in lines:
                            if "ERROR" in line or "CRITICAL" in line:
                                error_count += 1
                                if "CRITICAL" in line:
                                    critical_errors.append(line.strip()[:100])
                except BaseException:
                    pass

        if error_count > 0:
            self._print_warning(f"Found {error_count} errors in logs")
            if critical_errors:
                self._add_issue(
                    "Logs",
                    IssueLevel.WARNING,
                    f"Critical errors found in logs",
                    f"Found {len(critical_errors)} critical errors",
                    "Review log files for details",
                )
        else:
            self._print_ok("No recent errors in logs")

    def _diagnose_performance(self):
        """Diagnose system performance"""
        print(f"\n{Colors.CYAN}8. Performance Diagnostics{Colors.RESET}")

        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        self._print_info(f"CPU usage: {cpu_percent}%")

        # Memory usage
        memory = psutil.virtual_memory()
        self._print_info(f"Memory usage: {memory.percent}% ({memory.used // (1024**3)}GB used)")

        # Disk usage
        disk = psutil.disk_usage(str(SPYDER_HOME))
        disk_percent = (disk.used / disk.total) * 100
        self._print_info(f"Disk usage: {disk_percent:.1f}%")

        # Load average (Unix only)
        try:
            load = os.getloadavg()
            self._print_info(f"Load average: {load[0]:.2f}, {load[1]:.2f}, {load[2]:.2f}")
        except OSError:
            pass  # Windows doesn't support load average

    def _diagnose_configuration(self):
        """Diagnose configuration files"""
        print(f"\n{Colors.CYAN}9. Configuration Diagnostics{Colors.RESET}")

        # Check for config files
        config_files = [
            SPYDER_HOME / "config" / "trading.json",
            SPYDER_HOME / "config" / "strategies.json",
            SPYDER_HOME / "config" / "ib_config.json",
        ]

        for config_file in config_files:
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        json.load(f)
                    self._print_ok(f"Valid config: {config_file.name}")
                except json.JSONDecodeError as e:
                    self._add_issue(
                        "Configuration",
                        IssueLevel.ERROR,
                        f"Invalid JSON in {config_file.name}",
                        str(e),
                        "Fix JSON syntax errors",
                    )
            else:
                self._print_warning(f"Config not found: {config_file.name}")

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _add_issue(
        self,
        category: str,
        level: IssueLevel,
        description: str,
        details: str,
        solution: Optional[str] = None,
    ):
        """Add an issue to the list"""
        issue = Issue(
            category=category,
            level=level,
            description=description,
            details=details,
            solution=solution,
        )
        self.issues.append(issue)

        # Print issue
        color = {
            IssueLevel.CRITICAL: Colors.RED,
            IssueLevel.ERROR: Colors.RED,
            IssueLevel.WARNING: Colors.YELLOW,
            IssueLevel.INFO: Colors.CYAN,
        }[level]

        print(f"  {color}✗ {description}{Colors.RESET}")
        if self.verbose:
            print(f"    Details: {details}")
            if solution:
                print(f"    Solution: {solution}")

    def _print_ok(self, message: str):
        """Print success message"""
        print(f"  {Colors.GREEN}✓ {message}{Colors.RESET}")

    def _print_warning(self, message: str):
        """Print warning message"""
        print(f"  {Colors.YELLOW}⚠ {message}{Colors.RESET}")

    def _print_info(self, message: str):
        """Print info message"""
        print(f"  {Colors.CYAN}ⓘ {message}{Colors.RESET}")

    def _generate_recommendations(self):
        """Generate recommendations based on issues"""
        self.recommendations = []

        # Count issues by level
        critical_count = sum(1 for i in self.issues if i.level == IssueLevel.CRITICAL)
        error_count = sum(1 for i in self.issues if i.level == IssueLevel.ERROR)
        warning_count = sum(1 for i in self.issues if i.level == IssueLevel.WARNING)

        if critical_count > 0:
            self.recommendations.append(
                f"URGENT: Fix {critical_count} critical issue(s) before running Spyder"
            )

        if error_count > 0:
            self.recommendations.append(
                f"Fix {error_count} error(s) for proper functionality"
            )

        if warning_count > 0:
            self.recommendations.append(
                f"Address {warning_count} warning(s) for optimal performance"
            )

        # Specific recommendations
        categories = {i.category for i in self.issues}

        if "Dependencies" in categories:
            self.recommendations.append("Install missing dependencies with pip")

        if "IB Gateway" in categories:
            self.recommendations.append("Ensure IB Gateway/TWS is running and accessible")

        if "Modules" in categories:
            self.recommendations.append("Check Spyder module imports and syntax")

        if len(self.issues) == 0:
            self.recommendations.append("System appears healthy - ready for trading!")

    def _calculate_health_score(self) -> int:
        """Calculate overall system health score (0-100)"""
        if not self.issues:
            return 100

        # Deduct points based on issue severity
        deductions = {
            IssueLevel.CRITICAL: 25,
            IssueLevel.ERROR: 15,
            IssueLevel.WARNING: 5,
            IssueLevel.INFO: 1,
        }

        total_deduction = sum(deductions[issue.level] for issue in self.issues)
        health_score = max(0, 100 - total_deduction)

        return health_score

    def _print_summary(self, result: DiagnosticResult):
        """Print diagnostic summary"""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
        print(f"{Colors.BLUE}  DIAGNOSTIC SUMMARY{Colors.RESET}")
        print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")

        # Health score
        if result.health_score >= 90:
            score_color = Colors.GREEN
        elif result.health_score >= 70:
            score_color = Colors.YELLOW
        else:
            score_color = Colors.RED

        print(f"\n{Colors.BOLD}Health Score: {score_color}{result.health_score}/100{Colors.RESET}")

        # Issue counts
        if result.issues:
            print(f"\n{Colors.BOLD}Issues Found:{Colors.RESET}")
            issue_counts = {}
            for issue in result.issues:
                issue_counts[issue.level] = issue_counts.get(issue.level, 0) + 1

            for level, count in issue_counts.items():
                color = {
                    IssueLevel.CRITICAL: Colors.RED,
                    IssueLevel.ERROR: Colors.RED,
                    IssueLevel.WARNING: Colors.YELLOW,
                    IssueLevel.INFO: Colors.CYAN,
                }[level]
                print(f"  {color}{level.value}: {count}{Colors.RESET}")
        else:
            print(f"\n{Colors.GREEN}No issues found!{Colors.RESET}")

        # Recommendations
        if result.recommendations:
            print(f"\n{Colors.BOLD}Recommendations:{Colors.RESET}")
            for i, rec in enumerate(result.recommendations, 1):
                print(f"  {i}. {rec}")

        print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")


# ===============================================================================
# AUTO-FIX FUNCTIONALITY
# ===============================================================================


class AutoFix:
    """Automated fix implementations"""

    @staticmethod
    def fix_missing_directories():
        """Create missing directories"""
        directories = [LOG_DIR, DATA_DIR, SCRIPTS_DIR]
        for directory in directories:
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                print(f"Created directory: {directory}")

    @staticmethod
    def fix_permissions():
        """Fix file permissions"""
        try:
            # Make scripts executable
            script_files = SCRIPTS_DIR.glob("*.sh")
            for script in script_files:
                os.chmod(script, 0o755)
            print("Fixed script permissions")
        except Exception as e:
            print(f"Error fixing permissions: {e}")

    @staticmethod
    def install_missing_packages(packages: List[str]):
        """Install missing Python packages"""
        for package in packages:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", package],
                    check=True,
                    capture_output=True,
                )
                print(f"Installed {package}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {package}: {e}")


# ===============================================================================
# MAIN EXECUTION
# ===============================================================================


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Spyder System Diagnostics")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--auto-fix", "-f", action="store_true", help="Attempt automatic fixes"
    )
    parser.add_argument(
        "--output", "-o", help="Save results to JSON file"
    )
    parser.add_argument(
        "--health-check", action="store_true", help="Quick health check only"
    )

    args = parser.parse_args()

    # Initialize diagnostics
    diagnostics = SpyderDiagnostics(verbose=args.verbose, auto_fix=args.auto_fix)

    # Run diagnostics
    if args.health_check:
        # Quick health check
        print("Running quick health check...")
        diagnostics._diagnose_dependencies()
        diagnostics._diagnose_network()
        diagnostics._diagnose_ib_gateway()
    else:
        # Full diagnostics
        result = diagnostics.run_full_diagnostics()

        # Auto-fix if requested
        if args.auto_fix:
            print(f"\n{Colors.CYAN}Running auto-fixes...{Colors.RESET}")
            AutoFix.fix_missing_directories()
            AutoFix.fix_permissions()

        # Save results if requested
        if args.output:
            try:
                with open(args.output, "w") as f:
                    json.dump(asdict(result), f, indent=2, default=str)
                print(f"\nResults saved to: {args.output}")
            except Exception as e:
                print(f"Error saving results: {e}")

    print(f"\n{Colors.GREEN}Diagnostics complete!{Colors.RESET}")


if __name__ == "__main__":
    main()