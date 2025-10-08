# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_EnhancedLauncher.py
Purpose: Enhanced GUI launcher for SPYDER Trading System with dual-mode support

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-08 Time: 12:00:00

Module Description:
    Comprehensive launcher interface for the SPYDER trading system. Provides
    intelligent startup options including:
    - Local IB Gateway vs Remote TWS selection
    - Paper vs Live trading mode switching
    - Smart launch with existing connection detection
    - Nuclear restart for stuck Gateway instances
    - Real-time connection status monitoring
    - Configuration persistence

Module Constants:
    DEFAULT_PAPER_PORT (int): Default port for paper trading (4002)
    DEFAULT_LIVE_PORT (int): Default port for live trading (4001)
    GATEWAY_STARTUP_TIMEOUT (int): Maximum seconds to wait for Gateway (60)
    API_CONNECTION_RETRIES (int): Number of connection retry attempts (3)
    
Dependencies:
    - PySide6/tkinter for GUI
    - psutil for process management
    - SpyderB_Broker modules for IB connectivity
    - SpyderU_Utilities for logging

Change Log:
    2025-10-08 (v1.0.0):
        - Initial production release
        - Merged spyder_launcher_enhanced.py and spyder_launcher_gui.py
        - Added comprehensive error handling
        - Implemented standard logging
        - Added type hints and docstrings
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import socket
import subprocess
import threading
import configparser
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from datetime import datetime
from enum import Enum
import fcntl  # For file locking (singleton)

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False
    print("Warning: tkinter not available")

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not available - process management limited")

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from SpyderU_Utilities.SpyderU01_Logger import SpyderLogger, get_logger
    HAS_LOGGER = True
except ImportError:
    HAS_LOGGER = False
    import logging
    get_logger = logging.getLogger

try:
    from SpyderB_Broker.SpyderB05_ConnectionManager import get_connection_manager
    HAS_CONNECTION_MANAGER = True
except ImportError:
    HAS_CONNECTION_MANAGER = False
    print("Warning: ConnectionManager not available")

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Connection Defaults
DEFAULT_PAPER_PORT = 4002
DEFAULT_LIVE_PORT = 4001
REMOTE_TWS_PAPER_PORT = 7497
REMOTE_TWS_LIVE_PORT = 7496

# Timing Constants
GATEWAY_STARTUP_TIMEOUT = 60
API_CONNECTION_RETRIES = 3
CONNECTION_CHECK_INTERVAL = 5
POST_CONNECTION_WAIT = 2

# Paths
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
IB_GATEWAY_DIR = Path.home() / "Jts" / "ibgateway" / "1039"
CONFIG_DIR = SPYDER_HOME / "config"
CONFIG_FILE = CONFIG_DIR / "launcher_config.ini"
LOG_DIR = Path.home() / "spyder_logs"
LOCK_FILE = Path("/tmp/spyder_launcher.lock")  # Singleton lock file

# Default Configuration
DEFAULT_CONFIG = {
    "trading_mode": "paper",
    "connection_type": "local_gateway",
    "remote_tws_host": "192.168.1.2",
    "last_launch_method": "smart",
    "auto_launch_dashboard": "true",
    "remember_settings": "true",
    "skip_ibc": "false",
}

# ==============================================================================
# ENUMS
# ==============================================================================
class TradingMode(Enum):
    """Trading mode enumeration"""
    PAPER = "paper"
    LIVE = "live"

class ConnectionType(Enum):
    """Connection type enumeration"""
    LOCAL_GATEWAY = "local_gateway"
    REMOTE_TWS = "remote_tws"

class LaunchMethod(Enum):
    """Launch method enumeration"""
    SMART = "smart"
    CLEAN = "clean"
    SKIP_GATEWAY = "skip_gateway"
    TEST_ONLY = "test_only"
    DASHBOARD_ONLY = "dashboard_only"

# ==============================================================================
# SINGLETON MANAGEMENT
# ==============================================================================
class SingletonLock:
    """
    Ensures only one instance of the launcher runs at a time.
    Uses file locking for cross-process singleton enforcement.
    """
    
    def __init__(self, lock_file: Path):
        """
        Initialize singleton lock.
        
        Args:
            lock_file: Path to lock file
        """
        self.lock_file = lock_file
        self.lock_fd = None
        
    def acquire(self) -> bool:
        """
        Acquire the singleton lock.
        
        Returns:
            True if lock acquired, False if another instance is running
        """
        try:
            # Create lock file if it doesn't exist
            self.lock_fd = open(self.lock_file, 'w')
            
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write PID to lock file
            self.lock_fd.write(str(os.getpid()))
            self.lock_fd.flush()
            
            return True
            
        except IOError:
            # Lock already held by another process
            if self.lock_fd:
                self.lock_fd.close()
                self.lock_fd = None
            return False
            
    def release(self) -> None:
        """Release the singleton lock"""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd.fileno(), fcntl.LOCK_UN)
                self.lock_fd.close()
            except Exception:
                pass
            finally:
                self.lock_fd = None
                
    def __enter__(self):
        """Context manager entry"""
        if not self.acquire():
            raise RuntimeError("Another instance is already running")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.release()

def check_existing_instance() -> bool:
    """
    Check if another instance is already running.
    
    Returns:
        True if another instance exists, False otherwise
    """
    try:
        # Try to acquire lock
        lock = SingletonLock(LOCK_FILE)
        if lock.acquire():
            lock.release()
            return False
        else:
            return True
    except Exception:
        return False

def bring_existing_window_to_front() -> None:
    """
    Attempt to bring existing launcher window to front.
    Uses wmctrl if available.
    """
    try:
        # Try using wmctrl to activate existing window
        subprocess.run(
            ['wmctrl', '-a', 'SPYDER Enhanced Trading System'],
            capture_output=True,
            timeout=2
        )
    except Exception:
        # wmctrl not available or failed, that's okay
        pass
def load_credentials_from_env() -> Dict[str, str]:
    """
    Load IB credentials from environment variables.
    
    Returns:
        Dict containing username and password for paper/live
    """
    credentials = {
        "paper_username": os.getenv("IB_USERNAME", ""),
        "paper_password": os.getenv("IB_PASSWORD", ""),
        "live_username": os.getenv("IB_LIVE_USERNAME", ""),
        "live_password": os.getenv("IB_LIVE_PASSWORD", ""),
    }
    return credentials

def check_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """
    Check if a port is available for connection.
    
    Args:
        port: Port number to check
        host: Host address (default: localhost)
        
    Returns:
        True if port is listening, False otherwise
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            return result == 0
    except Exception:
        return False

def is_gateway_running() -> bool:
    """
    Check if IB Gateway process is running.
    
    Returns:
        True if Gateway process found, False otherwise
    """
    if not HAS_PSUTIL:
        return False
        
    try:
        for proc in psutil.process_iter(['name']):
            if 'ibgateway' in proc.info['name'].lower():
                return True
        return False
    except Exception:
        return False

def kill_gateway_processes() -> bool:
    """
    Kill all IB Gateway related processes.
    
    Returns:
        True if successful, False otherwise
    """
    if not HAS_PSUTIL:
        return False
        
    try:
        killed = False
        for proc in psutil.process_iter(['name', 'pid']):
            proc_name = proc.info['name'].lower()
            if any(x in proc_name for x in ['ibgateway', 'ibc', 'xvfb']):
                proc.kill()
                killed = True
        return killed
    except Exception as e:
        print(f"Error killing processes: {e}")
        return False

# ==============================================================================
# MAIN LAUNCHER CLASS
# ==============================================================================
class SpyderEnhancedLauncher:
    """
    Enhanced SPYDER Trading System Launcher.
    
    Provides comprehensive GUI for launching SPYDER with various
    connection and trading mode options.
    """
    
    def __init__(self):
        """Initialize the launcher"""
        # Setup logging
        if HAS_LOGGER:
            self.logger = get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)
            
        self.logger.info("Initializing SPYDER Enhanced Launcher")
        
        # Acquire singleton lock
        self.singleton_lock = SingletonLock(LOCK_FILE)
        
        # Load credentials and configuration
        self.credentials = load_credentials_from_env()
        self.config = self._load_configuration()
        
        # Initialize GUI
        if not HAS_TK:
            raise RuntimeError("tkinter is required for GUI launcher")
            
        self.root = tk.Tk()
        
        # Set WM_CLASS for proper window grouping
        self.root.wm_class("SPYDER", "SPYDER")
        
        # Set window properties for desktop integration
        try:
            # Set _NET_WM_PID for better window management
            self.root.attributes('-type', 'normal')
        except Exception:
            pass
        
        self.progress_window = None
        
        # Setup variables
        self.trading_mode = tk.StringVar(value=self.config.get("SPYDER", "trading_mode"))
        self.connection_type = tk.StringVar(value=self.config.get("SPYDER", "connection_type"))
        self.remote_host = tk.StringVar(value=self.config.get("SPYDER", "remote_tws_host"))
        
        # Setup UI
        self._setup_window()
        self._setup_styles()
        self._create_widgets()
        
        # Check initial system status
        self.root.after(500, self.check_system_status)
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
    def _load_configuration(self) -> configparser.ConfigParser:
        """
        Load launcher configuration from file.
        
        Returns:
            ConfigParser object with launcher settings
        """
        config = configparser.ConfigParser()
        
        if CONFIG_FILE.exists():
            try:
                config.read(CONFIG_FILE)
                if "SPYDER" not in config:
                    config["SPYDER"] = {}
                # Merge with defaults
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config["SPYDER"]:
                        config["SPYDER"][key] = value
            except Exception as e:
                self.logger.error(f"Error loading config: {e}")
                config["SPYDER"] = DEFAULT_CONFIG.copy()
        else:
            config["SPYDER"] = DEFAULT_CONFIG.copy()
            self._save_configuration(config)
            
        return config
        
    def _save_configuration(self, config: Optional[configparser.ConfigParser] = None) -> None:
        """
        Save launcher configuration to file.
        
        Args:
            config: ConfigParser to save (uses self.config if None)
        """
        if config is None:
            config = self.config
            
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
            self.logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            
    def _setup_window(self) -> None:
        """Configure main window properties"""
        self.root.title("🕷️ SPYDER Enhanced Trading System")
        self.root.geometry("700x750")  # Increased height for IBC section
        self.root.resizable(False, False)
        
        # Center window on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")
        
    def _setup_styles(self) -> None:
        """Configure UI styles and theme"""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # Dark theme colors
        bg_color = "#2d2d2d"
        fg_color = "#ffffff"
        accent_color = "#00ff88"
        button_bg = "#3d3d3d"
        
        self.root.configure(bg=bg_color)
        
        # Configure styles
        self.style.configure("TFrame", background=bg_color)
        self.style.configure("TLabel", background=bg_color, foreground=fg_color)
        self.style.configure("TButton", background=button_bg, foreground=fg_color, 
                           borderwidth=1, focuscolor=accent_color)
        self.style.configure("TRadiobutton", background=bg_color, foreground=fg_color)
        self.style.configure("Status.TLabel", background=bg_color, foreground=fg_color,
                           font=("Arial", 9))
        
    def _create_widgets(self) -> None:
        """Create all GUI widgets"""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = tk.Label(main_frame, text="🕷️ SPYDER TRADING SYSTEM",
                         font=("Arial", 18, "bold"), bg="#2d2d2d", fg="#00ff88")
        header.pack(pady=(0, 5))
        
        subheader = tk.Label(main_frame, text="Enhanced Launcher v1.0",
                            font=("Arial", 10), bg="#2d2d2d", fg="#888888")
        subheader.pack(pady=(0, 20))
        
        # Connection Configuration Frame
        config_frame = tk.LabelFrame(main_frame, text="Connection Configuration",
                                     bg="#2d2d2d", fg="#00ff88", font=("Arial", 10, "bold"))
        config_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Connection Type Selection
        conn_frame = tk.Frame(config_frame, bg="#2d2d2d")
        conn_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        tk.Label(conn_frame, text="Connection:", bg="#2d2d2d", fg="#ffffff",
                font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Radiobutton(conn_frame, text="🏪 Local IB Gateway",
                       variable=self.connection_type, value="local_gateway",
                       command=self.on_config_change).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Radiobutton(conn_frame, text="🌐 Remote TWS",
                       variable=self.connection_type, value="remote_tws",
                       command=self.on_config_change).pack(side=tk.LEFT)
        
        # Trading Mode Selection
        mode_frame = tk.Frame(config_frame, bg="#2d2d2d")
        mode_frame.pack(fill=tk.X, padx=10, pady=(5, 5))
        
        tk.Label(mode_frame, text="Trading Mode:", bg="#2d2d2d", fg="#ffffff",
                font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Radiobutton(mode_frame, text="📄 Paper Trading (Safe)",
                       variable=self.trading_mode, value="paper",
                       command=self.on_config_change).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Radiobutton(mode_frame, text="🔴 LIVE Trading (Real Money)",
                       variable=self.trading_mode, value="live",
                       command=self.on_mode_change).pack(side=tk.LEFT)
        
        # Current Configuration Display
        self.config_display = ttk.Label(config_frame, text="", style="Status.TLabel")
        self.config_display.pack(padx=10, pady=(5, 10))
        self.update_config_display()
        
        # IBC Control Frame
        ibc_frame = tk.LabelFrame(main_frame, text="Gateway Launch Settings",
                                  bg="#2d2d2d", fg="#00ff88", font=("Arial", 10, "bold"))
        ibc_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Skip IBC checkbox
        self.skip_ibc = tk.BooleanVar(value=self.config.get("SPYDER", "skip_ibc") == "true")
        
        ibc_check = ttk.Checkbutton(
            ibc_frame,
            text="⚠️  SKIP IBC (Automatic IB Connection)",
            variable=self.skip_ibc,
            command=self.on_ibc_toggle
        )
        ibc_check.pack(anchor=tk.W, padx=10, pady=(10, 5))
        
        # IBC explanation
        ibc_info = tk.Label(
            ibc_frame,
            text="IBC (IBController) automates Gateway login. Skip this if:\n"
                 "• IBC is not configured or not working\n"
                 "• You prefer manual Gateway login\n"
                 "• Gateway is already running manually",
            bg="#2d2d2d",
            fg="#cccccc",
            font=("Arial", 8),
            justify=tk.LEFT
        )
        ibc_info.pack(anchor=tk.W, padx=25, pady=(0, 10))
        
        # System Status Frame
        status_frame = tk.LabelFrame(main_frame, text="System Status",
                                     bg="#2d2d2d", fg="#00ff88", font=("Arial", 10, "bold"))
        status_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.connection_status = ttk.Label(status_frame, text="🔍 Checking connection...",
                                          style="Status.TLabel")
        self.connection_status.pack(anchor=tk.W, padx=10, pady=5)
        
        self.api_status = ttk.Label(status_frame, text="🔍 Checking API...",
                                   style="Status.TLabel")
        self.api_status.pack(anchor=tk.W, padx=10, pady=5)
        
        self.spyder_status = ttk.Label(status_frame, text="🔍 Checking SPYDER...",
                                      style="Status.TLabel")
        self.spyder_status.pack(anchor=tk.W, padx=10, pady=5)
        
        # Launch Options Frame
        options_frame = tk.LabelFrame(main_frame, text="Launch Options",
                                      bg="#2d2d2d", fg="#00ff88", font=("Arial", 10, "bold"))
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Buttons in 2x3 grid
        button_frame = tk.Frame(options_frame, bg="#2d2d2d")
        button_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure grid weights
        for i in range(2):
            button_frame.columnconfigure(i, weight=1)
        for i in range(3):
            button_frame.rowconfigure(i, weight=1)
        
        # Row 1
        self.smart_btn = ttk.Button(button_frame, text="🚀 Smart Launch",
                                    command=self.smart_launch)
        self.smart_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5), pady=(0, 5))
        
        self.restart_btn = ttk.Button(button_frame, text="🔥 Nuclear Restart",
                                     command=self.nuclear_restart)
        self.restart_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0), pady=(0, 5))
        
        # Row 2
        self.test_btn = ttk.Button(button_frame, text="🧪 Test Connection",
                                   command=self.test_connection)
        self.test_btn.grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(5, 5))
        
        self.dashboard_btn = ttk.Button(button_frame, text="📊 Dashboard Only",
                                       command=self.dashboard_only)
        self.dashboard_btn.grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(5, 5))
        
        # Row 3
        self.settings_btn = ttk.Button(button_frame, text="⚙️ Settings",
                                      command=self.show_settings)
        self.settings_btn.grid(row=2, column=0, sticky="ew", padx=(0, 5), pady=(5, 0))
        
        self.help_btn = ttk.Button(button_frame, text="❓ Help",
                                   command=self.show_help)
        self.help_btn.grid(row=2, column=1, sticky="ew", padx=(5, 0), pady=(5, 0))
        
        # Footer
        footer = tk.Label(main_frame, text="Professional Algorithmic Trading Platform",
                         font=("Arial", 8), bg="#2d2d2d", fg="#888888")
        footer.pack(pady=(10, 0))
        
    def on_config_change(self) -> None:
        """Handle configuration changes"""
        self.update_config_display()
        self.save_current_config()
        
    def on_ibc_toggle(self) -> None:
        """Handle IBC skip toggle"""
        self.config["SPYDER"]["skip_ibc"] = "true" if self.skip_ibc.get() else "false"
        self._save_configuration()
        
        if self.skip_ibc.get():
            self.logger.info("IBC skipped - Gateway will need manual launch")
        else:
            self.logger.info("IBC enabled - Gateway will use automatic login")
        
    def on_mode_change(self) -> None:
        """Handle trading mode changes with warning for live mode"""
        if self.trading_mode.get() == "live":
            result = messagebox.askyesno(
                "⚠️ WARNING - LIVE TRADING",
                "You are about to switch to LIVE trading mode!\n\n"
                "This will use REAL MONEY!\n\n"
                "Are you absolutely sure?",
                icon='warning'
            )
            if not result:
                self.trading_mode.set("paper")
        self.on_config_change()
        
    def update_config_display(self) -> None:
        """Update the configuration display label"""
        conn_type = self.connection_type.get()
        mode = self.trading_mode.get()
        
        conn_text = "Local IB Gateway" if conn_type == "local_gateway" else "Remote TWS"
        mode_text = "Paper Trading" if mode == "paper" else "⚠️ LIVE TRADING ⚠️"
        mode_color = "#00ff88" if mode == "paper" else "#ff4444"
        
        port = self.get_current_port()
        host = "127.0.0.1" if conn_type == "local_gateway" else self.remote_host.get()
        
        self.config_display.configure(
            text=f"Current: {conn_text} | {mode_text} | {host}:{port}"
        )
        
    def save_current_config(self) -> None:
        """Save current configuration settings"""
        self.config["SPYDER"]["trading_mode"] = self.trading_mode.get()
        self.config["SPYDER"]["connection_type"] = self.connection_type.get()
        self.config["SPYDER"]["remote_tws_host"] = self.remote_host.get()
        self._save_configuration()
        
    def get_current_port(self) -> int:
        """
        Get the current port based on connection and trading mode.
        
        Returns:
            Port number for current configuration
        """
        conn_type = self.connection_type.get()
        mode = self.trading_mode.get()
        
        if conn_type == "local_gateway":
            return DEFAULT_LIVE_PORT if mode == "live" else DEFAULT_PAPER_PORT
        else:
            return REMOTE_TWS_LIVE_PORT if mode == "live" else REMOTE_TWS_PAPER_PORT
            
    def check_system_status(self) -> None:
        """Check and update system status indicators"""
        def check_in_thread():
            # Check Gateway/TWS connection
            port = self.get_current_port()
            host = "127.0.0.1" if self.connection_type.get() == "local_gateway" else self.remote_host.get()
            
            if check_port_available(port, host):
                self.root.after(0, lambda: self.connection_status.configure(
                    text=f"✅ Connection: Available ({host}:{port})"))
            else:
                self.root.after(0, lambda: self.connection_status.configure(
                    text=f"⚪ Connection: Not Available ({host}:{port})"))
            
            # Check API status
            # Placeholder for actual API check
            self.root.after(0, lambda: self.api_status.configure(
                text="🔍 API: Checking..."))
            
            # Check SPYDER processes
            # Placeholder for actual SPYDER check
            self.root.after(0, lambda: self.spyder_status.configure(
                text="⚪ SPYDER: Not Running"))
                
        threading.Thread(target=check_in_thread, daemon=True).start()
        
    def show_progress(self, message: str) -> None:
        """
        Show progress window with message.
        
        Args:
            message: Progress message to display
        """
        if self.progress_window is not None:
            try:
                self.progress_window.destroy()
            except:
                pass
                
        self.progress_window = tk.Toplevel(self.root)
        self.progress_window.title("Please Wait")
        self.progress_window.geometry("400x100")
        self.progress_window.transient(self.root)
        self.progress_window.grab_set()
        
        # Center on parent
        self.progress_window.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - self.progress_window.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - self.progress_window.winfo_height()) // 2
        self.progress_window.geometry(f"+{x}+{y}")
        
        label = tk.Label(self.progress_window, text=message, font=("Arial", 11))
        label.pack(expand=True)
        
        self.root.update()
        
    def hide_progress(self) -> None:
        """Hide progress window"""
        if self.progress_window is not None:
            try:
                self.progress_window.destroy()
                self.progress_window = None
            except:
                pass
                
    def smart_launch(self) -> None:
        """Smart launch - detects existing connections and launches appropriately"""
        self.logger.info("Starting smart launch")
        
        def launch_process():
            self.show_progress("🚀 Starting SPYDER...")
            
            port = self.get_current_port()
            host = "127.0.0.1" if self.connection_type.get() == "local_gateway" else self.remote_host.get()
            
            # Check if already connected
            if check_port_available(port, host):
                self.logger.info(f"Connection available at {host}:{port}, launching dashboard")
                success = self.launch_spyder_dashboard()
            else:
                self.logger.info("No connection found, full launch required")
                success = self.full_launch()
                
            self.root.after(0, self.hide_progress)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Success", "✅ SPYDER launched successfully!"))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", "❌ Launch failed. Check logs for details."))
                    
            self.root.after(0, self.check_system_status)
            
        threading.Thread(target=launch_process, daemon=True).start()
        
    def nuclear_restart(self) -> None:
        """Nuclear restart - kill everything and start fresh"""
        self.logger.info("Starting nuclear restart")
        
        result = messagebox.askyesno(
            "Nuclear Restart",
            "This will kill all Gateway/TWS processes and restart.\n\n"
            "Continue?",
            icon='warning'
        )
        
        if not result:
            return
            
        def restart_process():
            self.show_progress("🔥 Nuclear restart in progress...")
            
            # Kill processes
            self.logger.info("Killing Gateway processes")
            kill_gateway_processes()
            time.sleep(2)
            
            # Full launch
            success = self.full_launch()
            
            self.root.after(0, self.hide_progress)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Success", "✅ System restarted successfully!"))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", "❌ Restart failed. Check logs for details."))
                    
            self.root.after(0, self.check_system_status)
            
        threading.Thread(target=restart_process, daemon=True).start()
        
    def test_connection(self) -> None:
        """Test connection to Gateway/TWS"""
        self.logger.info("Testing connection")
        
        def test_process():
            self.show_progress("🧪 Testing connection...")
            
            port = self.get_current_port()
            host = "127.0.0.1" if self.connection_type.get() == "local_gateway" else self.remote_host.get()
            mode = self.trading_mode.get()
            conn_name = "Local Gateway" if self.connection_type.get() == "local_gateway" else "Remote TWS"
            
            success = check_port_available(port, host)
            
            self.root.after(0, self.hide_progress)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Connection Test",
                    f"✅ Connection Test SUCCESSFUL\n\n"
                    f"Connected to {conn_name}: {host}:{port}\n"
                    f"Mode: {mode.upper()}\n\n"
                    f"API is accessible and ready!"))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Connection Test",
                    f"❌ Connection Test FAILED\n\n"
                    f"Cannot connect to {conn_name}: {host}:{port}\n"
                    f"Mode: {mode}\n\n"
                    f"Check connection and try again."))
                    
            self.root.after(0, self.check_system_status)
            
        threading.Thread(target=test_process, daemon=True).start()
        
    def dashboard_only(self) -> None:
        """Launch SPYDER Dashboard only"""
        self.logger.info("Launching dashboard only")
        
        def dashboard_process():
            self.show_progress("📊 Launching SPYDER Dashboard...")
            success = self.launch_spyder_dashboard()
            
            self.root.after(0, self.hide_progress)
            
            if success:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Dashboard Launched", "📊 SPYDER Dashboard started!"))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error", "❌ Dashboard launch failed."))
                    
            self.root.after(0, self.check_system_status)
            
        threading.Thread(target=dashboard_process, daemon=True).start()
        
    def full_launch(self) -> bool:
        """
        Full launch sequence - Gateway/TWS + Dashboard.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn_type = self.connection_type.get()
            
            if conn_type == "local_gateway":
                # Launch local Gateway
                self.logger.info("Launching local IB Gateway")
                if not self.launch_gateway():
                    return False
            else:
                # For remote TWS, just verify connection
                port = self.get_current_port()
                host = self.remote_host.get()
                if not check_port_available(port, host):
                    self.logger.error(f"Remote TWS not available at {host}:{port}")
                    return False
                    
            # Launch dashboard
            self.logger.info("Launching SPYDER dashboard")
            return self.launch_spyder_dashboard()
            
        except Exception as e:
            self.logger.error(f"Full launch failed: {e}")
            return False
            
    def launch_gateway(self) -> bool:
        """
        Launch IB Gateway with or without IBC.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            gateway_exe = IB_GATEWAY_DIR / "ibgateway"
            
            if not gateway_exe.exists():
                self.logger.error(f"Gateway executable not found: {gateway_exe}")
                return False
                
            mode = self.trading_mode.get()
            skip_ibc = self.skip_ibc.get()
            
            if skip_ibc:
                # Manual Gateway launch without IBC
                self.logger.info("Launching Gateway without IBC (manual login required)")
                
                # Show instruction dialog
                self.root.after(0, lambda: messagebox.showinfo(
                    "Manual Gateway Launch",
                    "Gateway will launch without automatic login.\n\n"
                    "Please:\n"
                    "1. Wait for Gateway window to appear\n"
                    "2. Log in manually with your credentials\n"
                    "3. Ensure API settings are correct:\n"
                    "   • Enable ActiveX and Socket Clients\n"
                    "   • Set Socket port to 4002 (paper) or 4001 (live)\n"
                    "   • Add 127.0.0.1 to Trusted IPs\n\n"
                    "Click OK to launch Gateway..."
                ))
                
                # Launch Gateway directly (will show login window)
                self.logger.info(f"Launching Gateway in {mode} mode (manual)")
                os.chdir(IB_GATEWAY_DIR)
                subprocess.Popen([str(gateway_exe)], start_new_session=True)
                
                # Give user time to log in
                self.root.after(0, lambda: messagebox.showinfo(
                    "Waiting for Login",
                    "Waiting 60 seconds for you to complete manual login.\n\n"
                    "The launcher will check for connection when you click OK."
                ))
                
                # Wait longer for manual login
                port = self.get_current_port()
                for i in range(90):  # 90 seconds for manual login
                    if check_port_available(port):
                        self.logger.info(f"Gateway ready on port {port}")
                        time.sleep(POST_CONNECTION_WAIT)
                        return True
                    time.sleep(1)
                    
                self.logger.error("Gateway startup timeout (manual login)")
                return False
                
            else:
                # Automated launch with IBC
                self.logger.info("Launching Gateway with IBC (automatic login)")
                
                # Get credentials
                if mode == "live":
                    username = self.credentials.get("live_username") or self.credentials.get("paper_username")
                    password = self.credentials.get("live_password") or self.credentials.get("paper_password")
                else:
                    username = self.credentials.get("paper_username")
                    password = self.credentials.get("paper_password")
                    
                if not username or not password:
                    self.logger.error("Credentials not found in environment")
                    
                    # Offer to switch to manual mode
                    self.root.after(0, lambda: messagebox.showwarning(
                        "Credentials Missing",
                        "IB credentials not found in environment variables.\n\n"
                        "Would you like to launch Gateway manually instead?\n\n"
                        "Enable 'Skip IBC' option and try again."
                    ))
                    return False
                    
                # Launch Gateway using IBC
                # Note: In production, this should use IBC with proper configuration
                self.logger.info(f"Launching Gateway with IBC in {mode} mode")
                
                # TODO: Implement actual IBC launch here
                # For now, show message that IBC needs configuration
                self.root.after(0, lambda: messagebox.showinfo(
                    "IBC Launch",
                    "IBC automatic launch requires configuration.\n\n"
                    "Please ensure IBC is installed and configured at:\n"
                    f"{IBC_PATH}\n\n"
                    "Or enable 'Skip IBC' for manual launch."
                ))
                
                # Placeholder for actual IBC launch
                # In production: launch IBC with proper configuration
                
                # Wait for Gateway to be ready
                port = self.get_current_port()
                for i in range(GATEWAY_STARTUP_TIMEOUT):
                    if check_port_available(port):
                        self.logger.info(f"Gateway ready on port {port}")
                        time.sleep(POST_CONNECTION_WAIT)
                        return True
                    time.sleep(1)
                    
                self.logger.error("Gateway startup timeout")
                return False
            
        except Exception as e:
            self.logger.error(f"Gateway launch failed: {e}")
            return False
            
    def launch_spyder_dashboard(self) -> bool:
        """
        Launch SPYDER Dashboard GUI.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try multiple possible dashboard entry points
            dashboard_options = [
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "launch_dashboard_production.py",
            ]
            
            for dashboard_script in dashboard_options:
                if dashboard_script.exists():
                    self.logger.info(f"Launching dashboard: {dashboard_script}")
                    os.chdir(SPYDER_HOME)
                    subprocess.Popen([sys.executable, str(dashboard_script)], 
                                   start_new_session=True)
                    return True
                    
            self.logger.error("No dashboard entry point found")
            return False
            
        except Exception as e:
            self.logger.error(f"Dashboard launch failed: {e}")
            return False
            
    def show_settings(self) -> None:
        """Show settings dialog"""
        skip_ibc_status = "Enabled (Manual Login)" if self.skip_ibc.get() else "Disabled (IBC Automatic Login)"
        
        settings_text = (
            "⚙️ SPYDER Settings\n\n"
            "Credentials Configuration:\n"
            "• Edit ~/.bashrc for IB credentials\n"
            "• Environment variables: IB_USERNAME, IB_PASSWORD\n"
            "• Live trading: IB_LIVE_USERNAME, IB_LIVE_PASSWORD\n\n"
            "Gateway Launch:\n"
            f"• Skip IBC: {skip_ibc_status}\n"
            f"• IBC Path: {IBC_PATH}\n\n"
            "Paths:\n"
            f"• SPYDER Home: {SPYDER_HOME}\n"
            f"• Gateway: {IB_GATEWAY_DIR}\n"
            f"• Config: {CONFIG_FILE}\n"
            f"• Logs: {LOG_DIR}\n\n"
            "Current Configuration:\n"
            f"• Connection: {self.connection_type.get()}\n"
            f"• Trading Mode: {self.trading_mode.get()}\n"
            f"• Port: {self.get_current_port()}\n"
        )
        messagebox.showinfo("Settings", settings_text)
        
    def show_help(self) -> None:
        """Show help dialog"""
        help_text = """🕷️ SPYDER Launcher Help

🚀 SMART LAUNCH:
• Auto-detects system state
• Launches optimally based on current status
• Recommended for daily use

🔥 NUCLEAR RESTART:
• Forces complete Gateway restart
• Clears any stuck states
• Use when Gateway is unresponsive

🧪 TEST CONNECTION:
• Verifies Gateway/TWS API connection
• No SPYDER launch
• Good for troubleshooting

📊 DASHBOARD ONLY:
• Launches SPYDER without Gateway management
• Use when Gateway is already running
• Fastest option for trading

CONNECTION TYPES:
🏪 Local IB Gateway: Runs Gateway on this machine
🌐 Remote TWS: Connects to TWS running on another machine

TRADING MODES:
📄 Paper Trading: Safe testing with simulated money
🔴 Live Trading: Real money trading (use with caution!)

⚠️ SKIP IBC OPTION:
IBC (IBController) automates Gateway login. Skip this if:
• IBC is not installed or configured
• IBC is not working properly
• You prefer manual Gateway login
• Gateway is already running manually

When Skip IBC is enabled:
• Gateway will launch but require manual login
• You'll need to enter credentials yourself
• Useful when IBC automation fails

💡 TROUBLESHOOTING:
• If Gateway won't connect: Try Nuclear Restart
• If API test fails: Check Gateway GUI settings
• Enable "ActiveX and Socket EClients" in Gateway
• Verify localhost is in Trusted IPs
• If IBC fails: Enable "Skip IBC" and login manually
"""
        messagebox.showinfo("Help", help_text)
        
    def on_closing(self) -> None:
        """Handle window close event"""
        self.logger.info("Launcher window closing")
        self.singleton_lock.release()
        self.root.destroy()
        
    def run(self) -> None:
        """Start the GUI application"""
        self.logger.info("Starting launcher GUI")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("Launcher interrupted by user")
        except Exception as e:
            self.logger.error(f"Launcher error: {e}")
            raise
        finally:
            self.singleton_lock.release()

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main entry point"""
    # Check if another instance is already running
    if check_existing_instance():
        print("⚠️  SPYDER Launcher is already running!")
        
        # Try to bring existing window to front
        bring_existing_window_to_front()
        
        # Show dialog if tkinter available
        if HAS_TK:
            root = tk.Tk()
            root.withdraw()  # Hide root window
            messagebox.showwarning(
                "Already Running",
                "SPYDER Launcher is already running!\n\n"
                "Only one instance can run at a time.\n\n"
                "The existing launcher window has been brought to the front."
            )
            root.destroy()
        
        sys.exit(0)
    
    # Ensure SPYDER home exists
    if not SPYDER_HOME.exists():
        if HAS_TK:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error",
                f"SPYDER directory not found!\n\n"
                f"Expected: {SPYDER_HOME}\n\n"
                f"Please run from correct location."
            )
            root.destroy()
        else:
            print(f"Error: SPYDER directory not found at {SPYDER_HOME}")
        sys.exit(1)
        
    # Create and run launcher
    try:
        app = SpyderEnhancedLauncher()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()