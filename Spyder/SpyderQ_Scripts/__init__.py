#!/usr/bin/env python3
"""
SPYDER - Autonomous Options Trading System v1.0

Package: SpyderQ_Scripts
Purpose: System scripts and automation tools
Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-09-04

Package Description:
    The SpyderQ_Scripts package provides system-level scripts and automation tools
    for setup, deployment, monitoring, and maintenance of the Spyder trading system.
    This package includes shell scripts, Python utilities, and service management
    tools for comprehensive system administration.

Scripts Overview:
    • SpyderQ01_Setup.sh: Initial system setup and configuration
    • SpyderQ02_Dependencies.sh: Dependency installation and management
    • SpyderQ10_StartAll.sh: Start all Spyder services
    • SpyderQ11_StopAll.sh: Stop all Spyder services
    • SpyderQ14_MainLauncher.py: Main system launcher with GUI
    • SpyderQ20_Status.sh: System status monitoring
    • SpyderQ21_Monitor.sh: Continuous system monitoring
    • SpyderQ24_ProductionWatchdog.py: Production environment watchdog
    • SpyderQ25_SystemMonitor.py: Advanced system monitoring
    • SpyderQ30_Diagnostics.sh: System diagnostics and troubleshooting
    • SpyderQ35_VerifySystem.sh: System verification and validation
    • SpyderQ40_Cleanup.sh: System cleanup and maintenance
    • SpyderQ45_Diagnostics.py: Python-based diagnostic tools

Key Features:
    • Automated setup and deployment
    • Comprehensive system monitoring
    • Service management and control
    • Diagnostic and troubleshooting tools
    • Production environment watchdog
    • System verification and validation
"""

# ==============================================================================
# VERSION INFORMATION
# ==============================================================================
__version__ = "1.0.0"
__author__ = "Mohamed Talib"
__email__ = "mtalib@spyder-trading.com"
__status__ = "Production"

# ==============================================================================
# PYTHON MODULE IMPORTS
# ==============================================================================

# Main Launcher
try:
    from .SpyderQ14_MainLauncher import (
        MainLauncher,
        # Add main classes from MainLauncher when inspected
    )

    MAIN_LAUNCHER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderQ14_MainLauncher not available: {e}")
    MAIN_LAUNCHER_AVAILABLE = False

# Production Watchdog
try:
    from .SpyderQ24_ProductionWatchdog import (
        ProductionWatchdog,
        # Add main classes from ProductionWatchdog when inspected
    )

    PRODUCTION_WATCHDOG_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderQ24_ProductionWatchdog not available: {e}")
    PRODUCTION_WATCHDOG_AVAILABLE = False

# System Monitor
try:
    from .SpyderQ25_SystemMonitor import (
        SystemMonitor,
        # Add main classes from SystemMonitor when inspected
    )

    SYSTEM_MONITOR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderQ25_SystemMonitor not available: {e}")
    SYSTEM_MONITOR_AVAILABLE = False

# Diagnostics
try:
    from .SpyderQ45_Diagnostics import (
        DiagnosticsRunner,
        # Add main classes from Diagnostics when inspected
    )

    DIAGNOSTICS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderQ45_Diagnostics not available: {e}")
    DIAGNOSTICS_AVAILABLE = False

# Dashboard Integration Verifier
try:
    from .SpyderQ80_VerifyDashboardIntegration import (
        DashboardIntegrationVerifier,
        # Add main classes from VerifyDashboardIntegration when inspected
    )

    DASHBOARD_VERIFIER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ SpyderQ80_VerifyDashboardIntegration not available: {e}")
    DASHBOARD_VERIFIER_AVAILABLE = False

# ==============================================================================
# SCRIPT MANAGEMENT FUNCTIONS
# ==============================================================================

import os
import subprocess
from pathlib import Path


def get_script_path():
    """Get the path to the SpyderQ_Scripts directory"""
    return Path(__file__).parent


def get_available_scripts():
    """
    Get a list of available scripts in the SpyderQ_Scripts package.

    Returns:
        dict: Dictionary with script availability status
    """
    script_path = get_script_path()
    scripts = {}

    # Shell scripts
    shell_scripts = [
        "SpyderQ01_Setup.sh",
        "SpyderQ02_Dependencies.sh",
        "SpyderQ10_StartAll.sh",
        "SpyderQ11_StopAll.sh",
        "SpyderQ16_SpyderControl.sh",
        "SpyderQ20_Status.sh",
        "SpyderQ21_Monitor.sh",
        "SpyderQ30_Diagnostics.sh",
        "SpyderQ35_VerifySystem.sh",
        "SpyderQ40_Cleanup.sh",
        "SpyderQ50_ExportData.sh",
    ]

    for script in shell_scripts:
        script_file = script_path / script
        scripts[script] = script_file.exists() and os.access(script_file, os.X_OK)

    # Python modules
    python_modules = {
        "SpyderQ14_MainLauncher.py": MAIN_LAUNCHER_AVAILABLE,
        "SpyderQ24_ProductionWatchdog.py": PRODUCTION_WATCHDOG_AVAILABLE,
        "SpyderQ25_SystemMonitor.py": SYSTEM_MONITOR_AVAILABLE,
        "SpyderQ45_Diagnostics.py": DIAGNOSTICS_AVAILABLE,
        "SpyderQ80_VerifyDashboardIntegration.py": DASHBOARD_VERIFIER_AVAILABLE,
    }

    scripts.update(python_modules)
    return scripts


def run_shell_script(script_name, args=None):
    """
    Execute a shell script from the SpyderQ_Scripts package.

    Args:
        script_name (str): Name of the script to run
        args (list): Optional arguments to pass to the script

    Returns:
        subprocess.CompletedProcess: Result of the script execution
    """
    script_path = get_script_path() / script_name

    if not script_path.exists():
        raise FileNotFoundError(f"Script not found: {script_name}")

    if not os.access(script_path, os.X_OK):
        raise PermissionError(f"Script not executable: {script_name}")

    cmd = [str(script_path)]
    if args:
        cmd.extend(args)

    return subprocess.run(cmd, capture_output=True, text=True)


def get_package_info():
    """
    Get comprehensive package information.

    Returns:
        dict: Package information including version, scripts, and capabilities
    """
    available_scripts = get_available_scripts()
    total_scripts = len(available_scripts)
    available_count = sum(available_scripts.values())

    return {
        "package_name": "SpyderQ_Scripts",
        "version": __version__,
        "author": __author__,
        "status": __status__,
        "total_scripts": total_scripts,
        "available_scripts": available_count,
        "script_status": available_scripts,
        "capabilities": {
            "main_launcher": MAIN_LAUNCHER_AVAILABLE,
            "production_watchdog": PRODUCTION_WATCHDOG_AVAILABLE,
            "system_monitoring": SYSTEM_MONITOR_AVAILABLE,
            "diagnostics": DIAGNOSTICS_AVAILABLE,
            "dashboard_verification": DASHBOARD_VERIFIER_AVAILABLE,
        },
    }


def validate_package():
    """
    Validate the package installation and script availability.

    Returns:
        bool: True if package is fully functional, False otherwise
    """
    try:
        info = get_package_info()
        print(f"📜 {info['package_name']} v{info['version']}")
        print(
            f"✅ {info['available_scripts']}/{info['total_scripts']} scripts available"
        )

        if info["available_scripts"] == info["total_scripts"]:
            print("🚀 All scripts loaded successfully")
            return True
        else:
            print("⚠️ Some scripts are missing or not executable")
            for script, status in info["script_status"].items():
                status_icon = "✅" if status else "❌"
                print(f"   {status_icon} {script}")
            return False

    except Exception as e:
        print(f"❌ Scripts package validation failed: {e}")
        return False


# ==============================================================================
# PACKAGE EXPORTS
# ==============================================================================

__all__ = [
    # Version info
    "__version__",
    "__author__",
    # Utility functions
    "get_script_path",
    "get_available_scripts",
    "run_shell_script",
    "get_package_info",
    "validate_package",
]

# Conditionally add available classes to __all__
if MAIN_LAUNCHER_AVAILABLE:
    __all__.extend(["MainLauncher"])

if PRODUCTION_WATCHDOG_AVAILABLE:
    __all__.extend(["ProductionWatchdog"])

if SYSTEM_MONITOR_AVAILABLE:
    __all__.extend(["SystemMonitor"])

if DIAGNOSTICS_AVAILABLE:
    __all__.extend(["DiagnosticsRunner"])

if DASHBOARD_VERIFIER_AVAILABLE:
    __all__.extend(["DashboardIntegrationVerifier"])

# ==============================================================================
# INITIALIZATION
# ==============================================================================

# Perform package validation on import
if __name__ != "__main__":
    validate_package()
else:
    # If running as main, show detailed package info
    print("=" * 70)
    print("SPYDER Q - SCRIPTS PACKAGE")
    print("=" * 70)
    validate_package()
    info = get_package_info()
    print("\nPackage Details:")
    for key, value in info.items():
        if key != "script_status":
            print(f"  {key}: {value}")
