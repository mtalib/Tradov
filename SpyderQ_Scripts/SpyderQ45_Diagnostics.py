#!/usr/bin/env python3
# ===============================================================================
# SPYDER - Autonomous Options Trading System
#
# Module: SpyderQ45_Diagnostics.py
# Group: Q (Scripts/Maintenance)
# Purpose: Advanced diagnostics and troubleshooting tool
# Author: Mohamed Talib
# Date Created: 2025-01-11
# Last Updated: 2025-01-11 Time: 12:30:00
#
# Description:
#     Comprehensive diagnostic tool that identifies and helps resolve common
#     issues with the Spyder trading system. Includes automated fixes, detailed
#     error analysis, and system health recommendations.
# ===============================================================================

import sys
import os
import time
import json
import socket
import subprocess
import traceback
import psutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import importlib.util

# Add Spyder to path
sys.path.insert(0, str(Path('/home/adam/Projects/Spyder')))

# ===============================================================================
# CONFIGURATION
# ===============================================================================

SPYDER_HOME = Path('/home/adam/Projects/Spyder')
LOG_DIR = SPYDER_HOME / "logs"
DATA_DIR = SPYDER_HOME / "data"
SCRIPTS_DIR = SPYDER_HOME / "scripts"
VENV_PATH = SPYDER_HOME / "spyder_venv"

# Color codes for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

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
            health_score=health_score
        )
        
        return result
    
    # ==========================================================================
    # SYSTEM INFORMATION
    # ==========================================================================
    
    def _collect_system_info(self):
        """Collect system information"""
        print(f"{Colors.CYAN}Collecting system information...{Colors.RESET}")
        
        self.system_info = {
            'os': os.uname().sysname,
            'os_version': os.uname().version,
            'hostname': socket.gethostname(),
            'python_version': sys.version,
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
            'disk_usage_percent': psutil.disk_usage(str(SPYDER_HOME)).percent,
            'spyder_home': str(SPYDER_HOME),
            'user': os.environ.get('USER', 'unknown')
        }
        
        if self.verbose:
            print(f"  OS: {self.system_info['os']}")
            print(f"  Python: {sys.version.split()[0]}")
            print(f"  Memory: {self.system_info['memory_total_gb']}GB")
            print(f"  CPUs: {self.system_info['cpu_count']}")
    
    # ==========================================================================
    # DIAGNOSTIC CATEGORIES
    # ==========================================================================
    
    def _diagnose_environment(self):
        """Diagnose environment setup"""
        print(f"\n{Colors.CYAN}1. Environment Diagnostics{Colors.RESET}")
        
        # Check Spyder home
        if not SPYDER_HOME.exists():
            self._add_issue(
                "Environment",
                IssueLevel.CRITICAL,
                "Spyder home directory not found",
                f"Expected at: {SPYDER_HOME}",
                "Run SpyderQ01_Setup.sh to create directory structure"
            )
        else:
            self._print_ok("Spyder home exists")
        
        # Check virtual environment
        if not VENV_PATH.exists():
            self._add_issue(
                "Environment",
                IssueLevel.CRITICAL,
                "Virtual environment not found",
                f"Expected at: {VENV_PATH}",
                "Run: python3.10 -m venv {VENV_PATH}",
                auto_fix=True
            )
        else:
            self._print_ok("Virtual environment exists")
        
        # Check critical directories
        for dir_name in ['logs', 'data', 'scripts', 'config']:
            dir_path = SPYDER_HOME / dir_name
            if not dir_path.exists():
                self._add_issue(
                    "Environment",
                    IssueLevel.WARNING,
                    f"Directory missing: {dir_name}",
                    f"Expected at: {dir_path}",
                    f"Create with: mkdir -p {dir_path}",
                    auto_fix=True
                )
                if self.auto_fix:
                    dir_path.mkdir(parents=True, exist_ok=True)
                    self._print_fixed(f"Created {dir_name} directory")
    
    def _diagnose_dependencies(self):
        """Diagnose Python dependencies"""
        print(f"\n{Colors.CYAN}2. Dependency Diagnostics{Colors.RESET}")
        
        critical_packages = {
            'ib_insync': 'IB API wrapper',
            'pandas': 'Data analysis',
            'numpy': 'Numerical computing',
            'PyQt6': 'GUI framework',
            'prometheus_client': 'Metrics',
            'psutil': 'System monitoring'
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
                        f"Install with: pip install {package}"
                    )
                else:
                    self._print_ok(f"{package} installed")
            except Exception as e:
                self._add_issue(
                    "Dependencies",
                    IssueLevel.ERROR,
                    f"Error checking {package}",
                    str(e),
                    f"Reinstall with: pip install --force-reinstall {package}"
                )
    
    def _diagnose_network(self):
        """Diagnose network connectivity"""
        print(f"\n{Colors.CYAN}3. Network Diagnostics{Colors.RESET}")
        
        # Check localhost
        try:
            socket.gethostbyname('localhost')
            self._print_ok("Localhost resolves")
        except:
            self._add_issue(
                "Network",
                IssueLevel.CRITICAL,
                "Cannot resolve localhost",
                "Network configuration issue",
                "Check /etc/hosts file"
            )
        
        # Check IB Gateway ports
        ports_to_check = [
            (4002, "IB Gateway Paper"),
            (4001, "IB Gateway Live"),
            (8000, "Prometheus Metrics")
        ]
        
        for port, service in ports_to_check:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
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
                    f"Start {service}"
                )
    
    def _diagnose_ib_gateway(self):
        """Diagnose IB Gateway status"""
        print(f"\n{Colors.CYAN}4. IB Gateway Diagnostics{Colors.RESET}")
        
        # Check if IB Gateway process is running
        gateway_running = False
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if 'ibgateway' in proc.info['name'].lower():
                    gateway_running = True
                    self._print_ok(f"IB Gateway process found (PID: {proc.pid})")
                    break
            except:
                pass
        
        if not gateway_running:
            self._add_issue(
                "IB Gateway",
                IssueLevel.WARNING,
                "IB Gateway not running",
                "No ibgateway process found",
                "Start IB Gateway manually or use SpyderQ13_StartRealGateway.py"
            )
        
        # Check IB Gateway installation
        ib_paths = [
            Path.home() / "Jts",
            Path("/opt/ibgateway"),
            Path("/usr/local/ibgateway")
        ]
        
        gateway_found = False
        for path in ib_paths:
            if path.exists():
                gateway_found = True
                self._print_ok(f"IB Gateway installation found at {path}")
                break
        
        if not gateway_found:
            self._add_issue(
                "IB Gateway",
                IssueLevel.ERROR,
                "IB Gateway not installed",
                "Could not find IB Gateway installation",
                "Download and install from Interactive Brokers website"
            )
    
    def _diagnose_modules(self):
        """Diagnose Spyder module imports"""
        print(f"\n{Colors.CYAN}5. Module Import Diagnostics{Colors.RESET}")
        
        critical_modules = [
            "SpyderA_Core.SpyderA06_MasterController",
            "SpyderB_Broker.SpyderB14_MultiClientWatchdog",
            "SpyderE_Risk.SpyderE11_MaxLossProtection",
            "SpyderX_Agents.SpyderX16_MetaCoordinator"
        ]
        
        sys.path.insert(0, str(SPYDER_HOME))
        
        for module in critical_modules:
            try:
                # Try to import
                parts = module.split('.')
                exec(f"from {'.'.join(parts[:-1])} import {parts[-1]}")
                self._print_ok(f"{module.split('.')[-1]} imports OK")
            except ImportError as e:
                self._add_issue(
                    "Modules",
                    IssueLevel.ERROR,
                    f"Cannot import {module}",
                    str(e),
                    "Check if module file exists and has no syntax errors"
                )
            except Exception as e:
                self._add_issue(
                    "Modules",
                    IssueLevel.WARNING,
                    f"Error in {module}",
                    str(e),
                    "Review module code for errors"
                )
    
    def _diagnose_processes(self):
        """Diagnose running processes"""
        print(f"\n{Colors.CYAN}6. Process Diagnostics{Colors.RESET}")
        
        # Check for Spyder processes
        spyder_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info.get('cmdline', []))
                if 'Spyder' in cmdline or 'spyder' in cmdline:
                    spyder_processes.append(proc)
            except:
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
                "Check for runaway processes"
            )
        
        if mem_percent > 85:
            self._add_issue(
                "Performance",
                IssueLevel.WARNING,
                f"High memory usage: {mem_percent}%",
                "System may run out of memory",
                "Close unnecessary applications"
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
                f"Create with: mkdir -p {LOG_DIR}"
            )
            return
        
        # Check recent errors in logs
        error_count = 0
        critical_errors = []
        
        for log_file in LOG_DIR.rglob("*.log"):
            if log_file.stat().st_size > 0:
                try:
                    with open(log_file, 'r', errors='ignore') as f:
                        # Read last 100 lines
                        lines = f.readlines()[-100:]
                        for line in lines:
                            if 'ERROR' in line or 'CRITICAL' in line:
                                error_count += 1
                                if 'CRITICAL' in line:
                                    critical_errors.append(line.strip()[:100])
                except:
                    pass
        
        if error_count > 0:
            self._print_warning(f"Found {error_count} errors in logs")
            if critical_errors:
                self._add_issue(
                    "Logs",
                    IssueLevel.WARNING,
                    f"Critical errors found in logs",
                    f"Found {len(critical_errors)} critical errors",
                    "Review log files for details"
                )
        else:
            self._print_ok("No recent errors in logs")
    
    def _diagnose_performance(self):
        """Diagnose system performance"""
        print(f"\n{Colors.CYAN}8. Performance Diagnostics{Colors.RESET}")
        
        # Check disk space
        disk_usage = psutil.disk_usage(str(SPYDER_HOME))
        if disk_usage.percent > 90:
            self._add_issue(
                "Performance",
                IssueLevel.ERROR,
                f"Low disk space: {disk_usage.percent}%",
                f"Only {disk_usage.free // (1024**3)}GB free",
                "Free up disk space or add storage"
            )
        else:
            self._print_ok(f"Disk usage: {disk_usage.percent}%")
        
        # Check available memory
        mem = psutil.virtual_memory()
        if mem.available < 1024**3:  # Less than 1GB
            self._add_issue(
                "Performance",
                IssueLevel.WARNING,
                f"Low available memory: {mem.available // (1024**2)}MB",
                "System may experience slowdowns",
                "Close unnecessary applications"
            )
        else:
            self._print_ok(f"Available memory: {mem.available // (1024**3)}GB")
        
        # Check swap usage
        swap = psutil.swap_memory()
        if swap.percent > 50:
            self._add_issue(
                "Performance",
                IssueLevel.WARNING,
                f"High swap usage: {swap.percent}%",
                "System is using swap heavily",
                "Consider adding more RAM"
            )
    
    def _diagnose_configuration(self):
        """Diagnose configuration files"""
        print(f"\n{Colors.CYAN}9. Configuration Diagnostics{Colors.RESET}")
        
        config_file = SPYDER_HOME / ".env"
        
        if not config_file.exists():
            self._add_issue(
                "Configuration",
                IssueLevel.ERROR,
                "Configuration file not found",
                f"Expected at: {config_file}",
                "Copy .env.example to .env and configure"
            )
        else:
            self._print_ok("Configuration file exists")
            
            # Check file permissions
            import stat
            mode = config_file.stat().st_mode
            if mode & stat.S_IROTH:
                self._add_issue(
                    "Configuration",
                    IssueLevel.WARNING,
                    "Configuration file is world-readable",
                    "Contains sensitive information",
                    f"Fix with: chmod 600 {config_file}",
                    auto_fix=True
                )
                if self.auto_fix:
                    config_file.chmod(0o600)
                    self._print_fixed("Fixed configuration file permissions")
            
            # Check for required variables
            try:
                with open(config_file) as f:
                    content = f.read()
                    required_vars = ['IB_USERNAME', 'TRADING_MODE', 'LOG_LEVEL']
                    
                    for var in required_vars:
                        if var not in content:
                            self._add_issue(
                                "Configuration",
                                IssueLevel.WARNING,
                                f"Missing configuration: {var}",
                                "Required for proper operation",
                                f"Add {var} to .env file"
                            )
            except Exception as e:
                self._add_issue(
                    "Configuration",
                    IssueLevel.ERROR,
                    "Cannot read configuration file",
                    str(e),
                    "Check file permissions and format"
                )
    
    # ==========================================================================
    # RECOMMENDATIONS
    # ==========================================================================
    
    def _generate_recommendations(self):
        """Generate system recommendations"""
        
        # Based on issues found
        critical_count = sum(1 for i in self.issues if i.level == IssueLevel.CRITICAL)
        error_count = sum(1 for i in self.issues if i.level == IssueLevel.ERROR)
        warning_count = sum(1 for i in self.issues if i.level == IssueLevel.WARNING)
        
        if critical_count > 0:
            self.recommendations.append("🔴 Fix critical issues immediately before running the system")
        
        if error_count > 0:
            self.recommendations.append("🟠 Address error-level issues for stable operation")
        
        if warning_count > 5:
            self.recommendations.append("🟡 Review and fix warnings to improve system reliability")
        
        # Performance recommendations
        if self.system_info.get('memory_total_gb', 0) < 4:
            self.recommendations.append("💾 Consider upgrading RAM (4GB+ recommended)")
        
        if self.system_info.get('disk_usage_percent', 0) > 70:
            self.recommendations.append("💿 Free up disk space or add storage")
        
        # General recommendations
        if not (SPYDER_HOME / "backup").exists():
            self.recommendations.append("💼 Set up regular backups with SpyderQ16_SpyderControl.sh backup")
        
        if not self.issues:
            self.recommendations.append("✅ System is healthy - ready for trading!")
    
    def _calculate_health_score(self) -> int:
        """Calculate overall health score"""
        score = 100
        
        for issue in self.issues:
            if issue.level == IssueLevel.CRITICAL:
                score -= 25
            elif issue.level == IssueLevel.ERROR:
                score -= 15
            elif issue.level == IssueLevel.WARNING:
                score -= 5
        
        return max(0, score)
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _add_issue(self, category: str, level: IssueLevel, description: str,
                   details: str, solution: Optional[str] = None, auto_fix: bool = False):
        """Add an issue to the list"""
        issue = Issue(
            category=category,
            level=level,
            description=description,
            details=details,
            solution=solution,
            auto_fix_available=auto_fix
        )
        self.issues.append(issue)
        
        # Print based on level
        if level == IssueLevel.CRITICAL:
            print(f"  {Colors.RED}✗ {description}{Colors.RESET}")
        elif level == IssueLevel.ERROR:
            print(f"  {Colors.RED}✗ {description}{Colors.RESET}")
        elif level == IssueLevel.WARNING:
            print(f"  {Colors.YELLOW}⚠ {description}{Colors.RESET}")
        else:
            print(f"  {Colors.CYAN}ℹ {description}{Colors.RESET}")
        
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
        print(f"  {Colors.CYAN}ℹ {message}{Colors.RESET}")
    
    def _print_fixed(self, message: str):
        """Print auto-fix message"""
        print(f"  {Colors.GREEN}🔧 {message}{Colors.RESET}")

# ===============================================================================
# REPORT GENERATION
# ===============================================================================

def generate_report(result: DiagnosticResult, format: str = 'text') -> str:
    """Generate diagnostic report"""
    
    if format == 'json':
        return json.dumps(asdict(result), indent=2, default=str)
    
    # Text format
    lines = []
    lines.append("=" * 60)
    lines.append("SPYDER DIAGNOSTIC REPORT")
    lines.append(f"Generated: {result.timestamp}")
    lines.append("=" * 60)
    lines.append("")
    
    # Health score
    score_color = Colors.GREEN if result.health_score >= 80 else Colors.YELLOW if result.health_score >= 60 else Colors.RED
    lines.append(f"Health Score: {score_color}{result.health_score}/100{Colors.RESET}")
    lines.append("")
    
    # Issues summary
    critical = sum(1 for i in result.issues if i.level == IssueLevel.CRITICAL)
    errors = sum(1 for i in result.issues if i.level == IssueLevel.ERROR)
    warnings = sum(1 for i in result.issues if i.level == IssueLevel.WARNING)
    
    lines.append("ISSUES FOUND:")
    lines.append(f"  Critical: {critical}")
    lines.append(f"  Errors: {errors}")
    lines.append(f"  Warnings: {warnings}")
    lines.append("")
    
    # Detailed issues
    if result.issues:
        lines.append("DETAILED ISSUES:")
        lines.append("-" * 40)
        
        for issue in sorted(result.issues, key=lambda x: x.level.value):
            icon = "🔴" if issue.level == IssueLevel.CRITICAL else "🟠" if issue.level == IssueLevel.ERROR else "🟡"
            lines.append(f"{icon} [{issue.category}] {issue.description}")
            lines.append(f"   {issue.details}")
            if issue.solution:
                lines.append(f"   → Solution: {issue.solution}")
            lines.append("")
    
    # Recommendations
    if result.recommendations:
        lines.append("RECOMMENDATIONS:")
        lines.append("-" * 40)
        for rec in result.recommendations:
            lines.append(f"  {rec}")
        lines.append("")
    
    # System info
    lines.append("SYSTEM INFORMATION:")
    lines.append("-" * 40)
    for key, value in result.system_info.items():
        lines.append(f"  {key}: {value}")
    
    return "\n".join(lines)

# ===============================================================================
# MAIN EXECUTION
# ===============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Spyder System Diagnostics')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')
    parser.add_argument('--auto-fix', '-f', action='store_true',
                       help='Automatically fix issues where possible')
    parser.add_argument('--json', action='store_true',
                       help='Output in JSON format')
    parser.add_argument('--export', type=str,
                       help='Export report to file')
    
    args = parser.parse_args()
    
    # Run diagnostics
    diagnostics = SpyderDiagnostics(verbose=args.verbose, auto_fix=args.auto_fix)
    result = diagnostics.run_full_diagnostics()
    
    # Generate report
    print("\n" + "=" * 60)
    report = generate_report(result, 'json' if args.json else 'text')
    
    if args.export:
        with open(args.export, 'w') as f:
            f.write(report)
        print(f"Report exported to: {args.export}")
    else:
        print(report)
    
    # Exit with appropriate code
    if result.health_score < 60:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()