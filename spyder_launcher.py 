#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System
System Launcher Script

This script provides the main entry point for the Spyder trading system.
It handles system initialization, startup sequences, and provides both
CLI and GUI launch options.

Usage:
    python spyder_launcher.py [options]
    
Options:
    --mode          : Trading mode (live/paper/backtest) [default: paper]
    --config        : Path to configuration file
    --gui           : Launch with GUI [default: True]
    --headless      : Run in headless mode (no GUI)
    --debug         : Enable debug logging
    --safe-mode     : Start with minimal modules (critical only)
    --module        : Start specific module only
    --status        : Check system status and exit
    --shutdown      : Shutdown running system
    
Examples:
    python spyder_launcher.py --mode paper --gui
    python spyder_launcher.py --mode live --headless
    python spyder_launcher.py --status
    python spyder_launcher.py --module SpyderB01_SpyderClient

Author: Mohamed Talib
Date: 2025-08-07
Version: 1.0
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import sys
import os
import argparse
import json
import yaml
import signal
import time
import threading
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# ==============================================================================
# SYSTEM PATH SETUP
# ==============================================================================
# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
try:
    from SpyderI_Integration.SpyderI05_SystemOrchestrator import (
        SystemOrchestrator, SystemState
    )
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger
    from SpyderU_Utilities.SpyderU02_ErrorHandler import SpyderErrorHandler
    CORE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Core modules not available: {e}")
    print("Please ensure all Spyder modules are properly installed")
    CORE_AVAILABLE = False

# Try to import GUI
try:
    from PyQt6.QtWidgets import QApplication
    from SpyderG_GUI.SpyderG05_TradingDashboard import SpyderTradingDashboard
    GUI_AVAILABLE = True
except ImportError:
    print("⚠️ GUI modules not available - running in headless mode only")
    GUI_AVAILABLE = False

# ==============================================================================
# CONSTANTS
# ==============================================================================
DEFAULT_CONFIG = {
    'mode': 'paper',
    'ib_gateway': {
        'host': '127.0.0.1',
        'port': 7497,  # Paper trading port
        'client_id': 1
    },
    'database': {
        'path': 'spyder_trading.db'
    },
    'logging': {
        'level': 'INFO',
        'file': 'spyder.log'
    },
    'risk': {
        'max_position_size': 10000,
        'max_daily_loss': 5000,
        'max_open_positions': 20
    }
}

# Mode configurations
MODE_CONFIGS = {
    'live': {
        'ib_port': 7496,
        'safety_checks': True,
        'require_confirmation': True,
        'max_order_size': 100
    },
    'paper': {
        'ib_port': 7497,
        'safety_checks': False,
        'require_confirmation': False,
        'max_order_size': 1000
    },
    'backtest': {
        'ib_port': None,
        'safety_checks': False,
        'require_confirmation': False,
        'max_order_size': 10000
    }
}

# ==============================================================================
# LAUNCHER CLASS
# ==============================================================================
class SpyderLauncher:
    """Main launcher for Spyder trading system"""
    
    def __init__(self, args: argparse.Namespace):
        """
        Initialize launcher
        
        Args:
            args: Command line arguments
        """
        self.args = args
        self.logger = None
        self.orchestrator = None
        self.gui_app = None
        self.dashboard = None
        self.config = self._load_configuration()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _load_configuration(self) -> Dict[str, Any]:
        """Load system configuration"""
        config = DEFAULT_CONFIG.copy()
        
        # Apply mode-specific config
        if self.args.mode in MODE_CONFIGS:
            mode_config = MODE_CONFIGS[self.args.mode]
            config['ib_gateway']['port'] = mode_config['ib_port']
            config.update(mode_config)
        
        # Load from config file if provided
        if self.args.config and Path(self.args.config).exists():
            with open(self.args.config, 'r') as f:
                if self.args.config.endswith('.json'):
                    user_config = json.load(f)
                elif self.args.config.endswith(('.yaml', '.yml')):
                    user_config = yaml.safe_load(f)
                else:
                    print(f"⚠️ Unknown config file format: {self.args.config}")
                    user_config = {}
                
                config.update(user_config)
        
        return config
    
    def launch(self) -> int:
        """
        Launch the Spyder system
        
        Returns:
            Exit code (0 for success)
        """
        try:
            # Check core availability
            if not CORE_AVAILABLE:
                print("❌ Cannot launch - core modules missing")
                return 1
            
            # Initialize logger
            log_level = 'DEBUG' if self.args.debug else self.config['logging']['level']
            self.logger = SpyderLogger.get_logger('SpyderLauncher')
            
            # Print startup banner
            self._print_banner()
            
            # Handle special commands
            if self.args.status:
                return self._check_status()
            
            if self.args.shutdown:
                return self._shutdown_system()
            
            # Check prerequisites
            if not self._check_prerequisites():
                return 1
            
            # Start orchestrator
            print("\n🚀 Starting System Orchestrator...")
            self.orchestrator = SystemOrchestrator(self.args.config)
            
            if self.args.module:
                # Start specific module only
                print(f"📦 Starting single module: {self.args.module}")
                success = self._start_single_module(self.args.module)
            elif self.args.safe_mode:
                # Start in safe mode
                print("🛡️ Starting in SAFE MODE (critical modules only)")
                success = self._start_safe_mode()
            else:
                # Normal startup
                success = self.orchestrator.startup()
            
            if not success:
                print("❌ System startup failed")
                return 1
            
            # Launch GUI if requested
            if self.args.gui and not self.args.headless:
                if GUI_AVAILABLE:
                    print("\n🖥️ Launching GUI Dashboard...")
                    return self._launch_gui()
                else:
                    print("⚠️ GUI not available - running in headless mode")
                    return self._run_headless()
            else:
                return self._run_headless()
                
        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")
            return 130
        except Exception as e:
            print(f"\n❌ Launch failed: {e}")
            if self.args.debug:
                import traceback
                traceback.print_exc()
            return 1
    
    def _print_banner(self) -> None:
        """Print startup banner"""
        print("\n" + "="*60)
        print("""
   _____ ______  __  ______  _____ ____  
  / ___// __ \\ \\/ / / __  / / ____|  _ \\ 
  \\__ \\/ /_/ /\\  / / / / / / |__  | |_) |
 ___/ / ____/ / / / /_/ /  / __| |  _ < 
/____/_/     /_/ /_____/  /_____/|_| \\_\\
        """)
        print("  Autonomous Options Trading System v1.0")
        print("="*60)
        print(f"\n📊 Mode: {self.args.mode.upper()}")
        print(f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📁 Root: {project_root}")
        print("="*60)
    
    def _check_prerequisites(self) -> bool:
        """Check system prerequisites"""
        print("\n🔍 Checking prerequisites...")
        
        checks = {
            'Python Version': self._check_python_version(),
            'IB Gateway': self._check_ib_gateway(),
            'Database': self._check_database(),
            'Required Modules': self._check_required_modules(),
            'Disk Space': self._check_disk_space()
        }
        
        all_passed = True
        for check, passed in checks.items():
            status = "✅" if passed else "❌"
            print(f"  {status} {check}")
            if not passed:
                all_passed = False
        
        if not all_passed and self.args.mode == 'live':
            print("\n⚠️ Cannot start in LIVE mode with failed prerequisites")
            return False
        
        return True
    
    def _check_python_version(self) -> bool:
        """Check Python version"""
        version = sys.version_info
        return version.major == 3 and version.minor >= 8
    
    def _check_ib_gateway(self) -> bool:
        """Check IB Gateway connection"""
        if self.args.mode == 'backtest':
            return True  # Not needed for backtest
        
        # Try to connect to IB Gateway
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        
        try:
            result = sock.connect_ex((
                self.config['ib_gateway']['host'],
                self.config['ib_gateway']['port']
            ))
            return result == 0
        except:
            return False
        finally:
            sock.close()
    
    def _check_database(self) -> bool:
        """Check database availability"""
        try:
            import sqlite3
            # Test database connection
            db_path = self.config['database']['path']
            conn = sqlite3.connect(db_path)
            conn.close()
            return True
        except:
            return False
    
    def _check_required_modules(self) -> bool:
        """Check required Python modules"""
        required = ['numpy', 'pandas', 'scipy', 'PyQt6']
        
        for module in required:
            try:
                __import__(module)
            except ImportError:
                if module == 'PyQt6' and self.args.headless:
                    continue  # PyQt6 not required for headless
                return False
        
        return True
    
    def _check_disk_space(self) -> bool:
        """Check available disk space"""
        import shutil
        stat = shutil.disk_usage(project_root)
        gb_free = stat.free / (1024**3)
        return gb_free > 1.0  # At least 1GB free
    
    def _start_safe_mode(self) -> bool:
        """Start system in safe mode"""
        # Only start critical modules
        critical_modules = [
            'SpyderU01_Logger',
            'SpyderU02_ErrorHandler',
            'SpyderH02_DatabaseManager',
            'SpyderB01_SpyderClient',
            'SpyderE01_RiskManager'
        ]
        
        for module in critical_modules:
            print(f"  Starting {module}...")
            if not self.orchestrator._load_module(module):
                return False
            if not self.orchestrator._start_module(module):
                return False
        
        return True
    
    def _start_single_module(self, module_name: str) -> bool:
        """Start a single module"""
        return (self.orchestrator._load_module(module_name) and 
                self.orchestrator._start_module(module_name))
    
    def _launch_gui(self) -> int:
        """Launch GUI interface"""
        try:
            # Create Qt application
            self.gui_app = QApplication(sys.argv)
            
            # Set application metadata
            self.gui_app.setApplicationName("Spyder Trading System")
            self.gui_app.setOrganizationName("Spyder")
            
            # Create and show dashboard
            self.dashboard = SpyderTradingDashboard()
            
            # Connect to orchestrator
            self.dashboard.orchestrator = self.orchestrator
            
            # Show dashboard
            self.dashboard.show()
            
            print("✅ GUI Dashboard launched successfully")
            print("\n" + "="*60)
            print(" System is running. Close the GUI to shutdown.")
            print("="*60 + "\n")
            
            # Run Qt event loop
            exit_code = self.gui_app.exec()
            
            # Shutdown on GUI close
            self._cleanup()
            
            return exit_code
            
        except Exception as e:
            print(f"❌ GUI launch failed: {e}")
            return 1
    
    def _run_headless(self) -> int:
        """Run in headless mode"""
        print("\n🤖 Running in headless mode...")
        print("Press Ctrl+C to shutdown\n")
        
        try:
            # Keep running until interrupted
            while True:
                # Get and display status periodically
                if self.orchestrator:
                    status = self.orchestrator.get_status()
                    self._display_status(status)
                
                time.sleep(30)  # Update every 30 seconds
                
        except KeyboardInterrupt:
            print("\n⚠️ Shutdown requested")
            self._cleanup()
            return 0
    
    def _display_status(self, status: Dict[str, Any]) -> None:
        """Display system status"""
        print(f"\r📊 Status: {status['state']} | "
              f"Modules: {status['modules']['active']}/{status['modules']['total']} | "
              f"CPU: {status['resources']['cpu']:.1f}% | "
              f"Memory: {status['resources']['memory']:.1f}% | "
              f"Uptime: {status['uptime']}", end='')
    
    def _check_status(self) -> int:
        """Check system status"""
        print("\n📊 Checking system status...")
        
        # Try to connect to running system
        # This would connect to a running orchestrator via IPC
        # For now, we'll check if process is running
        
        import psutil
        
        spyder_running = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'spyder_launcher.py' in ' '.join(cmdline):
                    spyder_running = True
                    print(f"✅ Spyder is running (PID: {proc.info['pid']})")
                    break
            except:
                continue
        
        if not spyder_running:
            print("❌ Spyder is not running")
            
        return 0 if spyder_running else 1
    
    def _shutdown_system(self) -> int:
        """Shutdown running system"""
        print("\n🛑 Shutting down Spyder system...")
        
        # This would send shutdown signal to running system
        # For now, we'll use process termination
        
        import psutil
        
        terminated = False
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info['cmdline']
                if cmdline and 'spyder_launcher.py' in ' '.join(cmdline):
                    if proc.info['pid'] != os.getpid():
                        proc.terminate()
                        print(f"✅ Sent shutdown signal to PID {proc.info['pid']}")
                        terminated = True
            except:
                continue
        
        if not terminated:
            print("⚠️ No running Spyder process found")
            
        return 0
    
    def _cleanup(self) -> None:
        """Clean up resources"""
        print("\n🧹 Cleaning up...")
        
        if self.orchestrator:
            print("  Shutting down orchestrator...")
            self.orchestrator.shutdown()
        
        if self.dashboard:
            print("  Closing dashboard...")
            self.dashboard.close()
        
        print("✅ Cleanup complete")
    
    def _signal_handler(self, signum, frame) -> None:
        """Handle system signals"""
        print(f"\n⚠️ Received signal {signum}")
        self._cleanup()
        sys.exit(0)

# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Spyder Autonomous Options Trading System Launcher',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Start in paper trading mode with GUI:
    python spyder_launcher.py --mode paper --gui
    
  Start in live trading mode (headless):
    python spyder_launcher.py --mode live --headless
    
  Start in safe mode (critical modules only):
    python spyder_launcher.py --safe-mode
    
  Check system status:
    python spyder_launcher.py --status
    
  Start specific module:
    python spyder_launcher.py --module SpyderB01_SpyderClient
        """
    )
    
    # Add arguments
    parser.add_argument('--mode', 
                       choices=['live', 'paper', 'backtest'],
                       default='paper',
                       help='Trading mode')
    
    parser.add_argument('--config',
                       type=str,
                       help='Path to configuration file')
    
    parser.add_argument('--gui',
                       action='store_true',
                       default=True,
                       help='Launch with GUI (default)')
    
    parser.add_argument('--headless',
                       action='store_true',
                       help='Run in headless mode (no GUI)')
    
    parser.add_argument('--debug',
                       action='store_true',
                       help='Enable debug logging')
    
    parser.add_argument('--safe-mode',
                       action='store_true',
                       help='Start with minimal modules')
    
    parser.add_argument('--module',
                       type=str,
                       help='Start specific module only')
    
    parser.add_argument('--status',
                       action='store_true',
                       help='Check system status and exit')
    
    parser.add_argument('--shutdown',
                       action='store_true',
                       help='Shutdown running system')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.headless:
        args.gui = False
    
    if args.mode == 'live':
        # Extra confirmation for live mode
        print("\n⚠️ WARNING: You are about to start in LIVE TRADING mode!")
        print("This will execute real trades with real money.")
        response = input("Are you sure? (type 'YES' to continue): ")
        if response != 'YES':
            print("Cancelled.")
            return 1
    
    # Create and run launcher
    launcher = SpyderLauncher(args)
    return launcher.launch()

# ==============================================================================
# SCRIPT ENTRY
# ==============================================================================
if __name__ == "__main__":
    sys.exit(main())