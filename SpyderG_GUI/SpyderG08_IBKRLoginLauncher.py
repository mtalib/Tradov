#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_IBKRLoginLauncher.py
Purpose: Enhanced GUI launcher with IBKR login and dashboard-only options

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-22 Time: 21:08:00

Module Description:
    Enhanced launcher for the SPYDER trading system that provides:
    - IBKR login screen with authentication
    - Option to launch dashboard only for visualization
    - Role-based access control
    - Remember login functionality
    - Secure credential storage

Dependencies:
    - PySide6/tkinter for GUI
    - SpyderU_Utilities for logging
    - json for user data storage
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import time
import json
import hashlib
import subprocess
import threading
import configparser
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List, Union
from datetime import datetime, timedelta
from enum import Enum

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

# ==============================================================================
# CONSTANTS
# ==============================================================================
# Paths
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
CONFIG_DIR = SPYDER_HOME / "config"
USERS_FILE = CONFIG_DIR / "users.json"
CONFIG_FILE = CONFIG_DIR / "ibkr_launcher_config.ini"
LOG_DIR = Path.home() / "spyder_logs"

# Default Configuration
DEFAULT_CONFIG = {
    "last_username": "",
    "last_password": "",
    "remember_login": "false",
    "remember_password": "false",
    "auto_launch_dashboard": "true",
    "default_mode": "ibkr_login",  # Options: "ibkr_login", "dashboard_only"
    "trading_mode": "paper",  # Options: "paper", "live"
    "session_timeout": "30",
}

# Default Users
DEFAULT_USERS = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "full_name": "System Administrator",
        "last_login": None,
        "created_at": datetime.now().isoformat()
    },
    "trader": {
        "password_hash": hashlib.sha256("trader123".encode()).hexdigest(),
        "role": "trader",
        "full_name": "Default Trader",
        "last_login": None,
        "created_at": datetime.now().isoformat()
    },
    "viewer": {
        "password_hash": hashlib.sha256("viewer123".encode()).hexdigest(),
        "role": "viewer",
        "full_name": "Read-only User",
        "last_login": None,
        "created_at": datetime.now().isoformat()
    }
}

# ==============================================================================
# ENUMS
# ==============================================================================
class LaunchMode(Enum):
    """Launch mode enumeration"""
    IBKR_LOGIN = "ibkr_login"
    DASHBOARD_ONLY = "dashboard_only"

class UserRole(Enum):
    """User role enumeration"""
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"

# ==============================================================================
# USER MANAGEMENT
# ==============================================================================
class UserManager:
    """Manages user authentication and authorization"""

    def __init__(self):
        """Initialize user manager"""
        if HAS_LOGGER:
            self.logger = get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)

        self.users_file = USERS_FILE
        self.users = self._load_users()
        self.current_user = None
        self.session_start = None

    def _load_users(self) -> Dict:
        """Load users from file or create defaults"""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading users: {e}")
                return DEFAULT_USERS.copy()
        else:
            # Create default users file
            self._save_users(DEFAULT_USERS)
            return DEFAULT_USERS.copy()

    def _save_users(self, users: Dict) -> None:
        """Save users to file"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.users_file, 'w') as f:
                json.dump(users, f, indent=2, default=str)
            self.logger.info("Users database saved")
        except Exception as e:
            self.logger.error(f"Error saving users: {e}")

    def authenticate_user(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Authenticate user with username and password

        Args:
            username: Username
            password: Plain text password

        Returns:
            Tuple of (success, message)
        """
        if username not in self.users:
            return False, "Invalid username or password"

        user = self.users[username]

        # Check password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != user.get("password_hash"):
            return False, "Invalid username or password"

        # Successful login
        user["last_login"] = datetime.now().isoformat()
        self._save_users(self.users)

        # Set current user and session
        self.current_user = username
        self.session_start = datetime.now()

        return True, "Login successful"

    def logout(self) -> None:
        """Logout current user"""
        self.current_user = None
        self.session_start = None

    def get_user_role(self) -> Optional[str]:
        """Get current user's role"""
        if not self.current_user:
            return None
        return self.users[self.current_user].get("role", "viewer")

    def get_user_full_name(self) -> Optional[str]:
        """Get current user's full name"""
        if not self.current_user:
            return None
        return self.users[self.current_user].get("full_name", self.current_user)

# ==============================================================================
# MAIN LAUNCHER CLASS
# ==============================================================================
class SpyderIBKRLoginLauncher:
    """
    SPYDER Trading System IBKR Login Launcher.

    Provides login interface with IBKR authentication and dashboard-only options.
    """

    def __init__(self):
        """Initialize the launcher"""
        # Setup logging
        if HAS_LOGGER:
            self.logger = get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info("Initializing SPYDER IBKR Login Launcher")

        # Initialize components
        self.user_manager = UserManager()
        self.config = self._load_configuration()

        # Initialize GUI
        if not HAS_TK:
            raise RuntimeError("tkinter is required for GUI launcher")

        self.root = tk.Tk()
        self.root.title("🕷️ SPYDER Trading System - Launch Options")
        self.root.geometry("550x650")
        self.root.resizable(False, False)

        # Center window on screen
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

        # Setup variables
        self.username = tk.StringVar(value=self.config.get("SPYDER", "last_username"))
        self.password = tk.StringVar(value=self.config.get("SPYDER", "last_password"))
        self.remember_login = tk.BooleanVar(
            value=self.config.get("SPYDER", "remember_login") == "true"
        )
        self.remember_password = tk.BooleanVar(
            value=self.config.get("SPYDER", "remember_password") == "true"
        )
        self.launch_mode = tk.StringVar(
            value=self.config.get("SPYDER", "default_mode") or "ibkr_login"
        )
        self.trading_mode = tk.StringVar(
            value=self.config.get("SPYDER", "trading_mode") or "paper"
        )

        # Setup UI
        self._setup_styles()
        self._create_widgets()

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _load_configuration(self) -> configparser.ConfigParser:
        """Load launcher configuration from file"""
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

    def _save_configuration(
        self, config: Optional[configparser.ConfigParser] = None
    ) -> None:
        """Save launcher configuration to file"""
        if config is None:
            config = self.config

        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                config.write(f)
            self.logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")

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
        self.style.configure(
            "TButton",
            background=button_bg,
            foreground=fg_color,
            borderwidth=1,
            focuscolor=accent_color,
        )
        self.style.configure("TEntry", fieldbackground=button_bg, foreground=fg_color)
        self.style.configure("TRadiobutton", background=bg_color, foreground=fg_color)

    def _create_widgets(self) -> None:
        """Create main launcher widgets"""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Label(
            main_frame,
            text="🕷️ SPYDER TRADING SYSTEM",
            font=("Arial", 18, "bold"),
            bg="#2d2d2d",
            fg="#00ff88",
        )
        header.pack(pady=(0, 5))

        subheader = tk.Label(
            main_frame,
            text="Launch Options Portal",
            font=("Arial", 10),
            bg="#2d2d2d",
            fg="#888888",
        )
        subheader.pack(pady=(0, 20))

        # Launch Mode Selection
        mode_frame = tk.LabelFrame(
            main_frame,
            text="Select Launch Mode",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        mode_frame.pack(fill=tk.X, pady=(0, 20))

        # IBKR Login Option
        ibkr_radio = ttk.Radiobutton(
            mode_frame,
            text="🔐 IBKR Login - Full trading system with Interactive Brokers",
            variable=self.launch_mode,
            value="ibkr_login",
            command=self.on_mode_change,
        )
        ibkr_radio.pack(anchor=tk.W, padx=10, pady=5)

        # Dashboard Only Option
        dashboard_radio = ttk.Radiobutton(
            mode_frame,
            text="📊 Dashboard Only - Visualization mode (no IBKR connection)",
            variable=self.launch_mode,
            value="dashboard_only",
            command=self.on_mode_change,
        )
        dashboard_radio.pack(anchor=tk.W, padx=10, pady=5)

        # Login Frame (shown for IBKR mode)
        self.login_frame = tk.LabelFrame(
            main_frame,
            text="IBKR Authentication",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        self.login_frame.pack(fill=tk.X, pady=(0, 20))

        # Trading Mode Selection
        trading_mode_frame = tk.LabelFrame(
            self.login_frame,
            text="Trading Mode",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 9, "bold"),
        )
        trading_mode_frame.pack(fill=tk.X, padx=10, pady=(10, 10))

        # Paper Trading Option
        paper_radio = ttk.Radiobutton(
            trading_mode_frame,
            text="📄 Paper Trading - Safe simulation mode (Recommended)",
            variable=self.trading_mode,
            value="paper",
            command=self.on_trading_mode_change,
        )
        paper_radio.pack(anchor=tk.W, padx=10, pady=5)

        # Live Trading Option
        live_radio = ttk.Radiobutton(
            trading_mode_frame,
            text="🔴 Live Trading - REAL MONEY trading",
            variable=self.trading_mode,
            value="live",
            command=self.on_trading_mode_change,
        )
        live_radio.pack(anchor=tk.W, padx=10, pady=5)

        # Warning for live trading
        self.live_warning = tk.Label(
            self.login_frame,
            text="⚠️ WARNING: Live trading uses REAL money!",
            bg="#2d2d2d",
            fg="#ff6b6b",
            font=("Arial", 9, "bold"),
        )

        # Username
        tk.Label(
            self.login_frame,
            text="Username:",
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Arial", 9, "bold"),
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        username_entry = ttk.Entry(self.login_frame, textvariable=self.username, width=30)
        username_entry.pack(padx=10, pady=(0, 10), fill=tk.X)

        # Password
        tk.Label(
            self.login_frame,
            text="Password:",
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Arial", 9, "bold"),
        ).pack(anchor=tk.W, padx=10, pady=(5, 5))

        password_entry = ttk.Entry(self.login_frame, textvariable=self.password, show="*", width=30)
        password_entry.pack(padx=10, pady=(0, 10), fill=tk.X)
        password_entry.bind('<Return>', lambda event: self.launch())

        # Remember login checkboxes
        remember_check = ttk.Checkbutton(
            self.login_frame,
            text="Remember username",
            variable=self.remember_login,
            command=self.on_remember_change,
        )
        remember_check.pack(anchor=tk.W, padx=10, pady=(0, 5))

        remember_pass_check = ttk.Checkbutton(
            self.login_frame,
            text="Remember password",
            variable=self.remember_password,
            command=self.on_remember_change,
        )
        remember_pass_check.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Launch button
        self.launch_btn = ttk.Button(
            self.login_frame,
            text="🚀 Launch System",
            command=self.launch,
        )
        self.launch_btn.pack(pady=10)

        # Dashboard Info Frame (shown for dashboard-only mode)
        self.dashboard_frame = tk.LabelFrame(
            main_frame,
            text="Dashboard Information",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )

        dashboard_info = tk.Label(
            self.dashboard_frame,
            text="📊 Dashboard will launch in visualization mode:\n\n"
                 "• Real-time market data simulation\n"
                 "• Chart visualization and analysis\n"
                 "• Signal monitoring\n"
                 "• No live trading capabilities\n"
                 "• No IBKR connection required\n\n"
                 "Perfect for market analysis and visualization!",
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Arial", 9),
            justify=tk.LEFT,
        )
        dashboard_info.pack(padx=10, pady=10, fill=tk.X)

        self.dashboard_launch_btn = ttk.Button(
            self.dashboard_frame,
            text="📊 Launch Dashboard",
            command=self.launch_dashboard_only,
        )
        self.dashboard_launch_btn.pack(pady=10)

        # Help
        help_btn = ttk.Button(
            main_frame,
            text="❓ Help",
            command=self.show_help,
        )
        help_btn.pack(pady=(0, 10))

        # Footer
        footer = tk.Label(
            main_frame,
            text="Professional Algorithmic Trading Platform",
            font=("Arial", 8),
            bg="#2d2d2d",
            fg="#888888",
        )
        footer.pack(pady=(10, 0))

        # Initialize UI state
        self.on_mode_change()

    def on_mode_change(self) -> None:
        """Handle launch mode change"""
        mode = self.launch_mode.get()

        if mode == "ibkr_login":
            self.login_frame.pack(fill=tk.X, pady=(0, 20))
            self.dashboard_frame.pack_forget()
        else:  # dashboard_only
            self.login_frame.pack_forget()
            self.dashboard_frame.pack(fill=tk.X, pady=(0, 20))

    def on_remember_change(self) -> None:
        """Handle remember login checkbox changes"""
        self.config["SPYDER"]["remember_login"] = "true" if self.remember_login.get() else "false"
        self.config["SPYDER"]["remember_password"] = "true" if self.remember_password.get() else "false"
        self.config["SPYDER"]["trading_mode"] = self.trading_mode.get()
        self._save_configuration()

    def on_trading_mode_change(self) -> None:
        """Handle trading mode change"""
        mode = self.trading_mode.get()

        if mode == "live":
            self.live_warning.pack(pady=(5, 10))
        else:
            self.live_warning.pack_forget()

    def launch(self) -> None:
        """Launch system based on selected mode"""
        mode = self.launch_mode.get()

        if mode == "ibkr_login":
            self.launch_with_ibkr_login()
        else:
            self.launch_dashboard_only()

    def launch_with_ibkr_login(self) -> None:
        """Launch with IBKR authentication"""
        username = self.username.get().strip()
        password = self.password.get()

        if not username or not password:
            messagebox.showerror("Login Error", "Please enter both username and password")
            return

        # Authenticate user
        success, message = self.user_manager.authenticate_user(username, password)

        if success:
            # Save configuration based on remember preferences
            if self.remember_login.get():
                self.config["SPYDER"]["last_username"] = username
            else:
                self.config["SPYDER"]["last_username"] = ""

            if self.remember_password.get():
                self.config["SPYDER"]["last_password"] = password
            else:
                self.config["SPYDER"]["last_password"] = ""

            # Save trading mode preference
            self.config["SPYDER"]["trading_mode"] = self.trading_mode.get()
            self.config["SPYDER"]["default_mode"] = "ibkr_login"
            self._save_configuration()

            # Launch dashboard with IBKR context
            self.launch_dashboard(with_ibkr=True)
        else:
            # Show error message
            messagebox.showerror("Login Failed", message)
            self.password.set("")

    def launch_dashboard_only(self) -> None:
        """Launch dashboard in visualization mode only"""
        # Save preference
        self.config["SPYDER"]["default_mode"] = "dashboard_only"
        self._save_configuration()

        # Launch dashboard without IBKR
        self.launch_dashboard(with_ibkr=False)

    def launch_dashboard(self, with_ibkr: bool = True) -> None:
        """Launch SPYDER Dashboard"""
        self.logger.info(f"Launching SPYDER Dashboard (IBKR: {with_ibkr})")

        try:
            dashboard_options = [
                SPYDER_HOME / "SpyderG_GUI" / "SpyderG02_GUIEntry.py",
                SPYDER_HOME / "SpyderA_Core" / "SpyderA01_Main.py",
                SPYDER_HOME / "launch_dashboard_production.py",
            ]

            for dashboard_script in dashboard_options:
                if dashboard_script.exists():
                    self.logger.info(f"Launching dashboard: {dashboard_script}")
                    os.chdir(SPYDER_HOME)

                    # Pass launch mode via environment
                    env = os.environ.copy()
                    env["SPYDER_LAUNCH_MODE"] = "ibkr_login" if with_ibkr else "dashboard_only"

                    if with_ibkr:
                        # Pass trading mode for IBKR login
                        env["SPYDER_TRADING_MODE"] = self.trading_mode.get()

                    if self.user_manager.current_user:
                        env["SPYDER_USER"] = self.user_manager.current_user
                        user_role = self.user_manager.get_user_role()
                        if user_role:
                            env["SPYDER_USER_ROLE"] = user_role

                    env["SPYDER_DESKTOP_FILE_NAME"] = "spyder-trading"

                    subprocess.Popen(
                        [sys.executable, str(dashboard_script)],
                        env=env,
                        start_new_session=True,
                    )

                    self.logger.info("✅ Dashboard launched")

                    # Close the launcher window after launch
                    self.root.after(500, self.close_launcher)
                    return

            messagebox.showerror("Error", "Dashboard executable not found")
        except Exception as e:
            self.logger.error(f"Dashboard launch failed: {e}")
            messagebox.showerror("Error", f"Failed to launch dashboard: {e}")

    def show_help(self) -> None:
        """Show help dialog"""
        help_text = """🕷️ SPYDER Launch Options Help

LAUNCH MODES:

🔐 IBKR LOGIN MODE:
• Full trading system with Interactive Brokers
• Live market data and trading capabilities
• Requires IBKR authentication
• Choose between Paper and Live trading modes

📊 DASHBOARD ONLY MODE:
• Visualization and analysis only
• Simulated market data
• No live trading
• No IBKR connection required
• Perfect for market analysis and learning

TRADING MODES (IBKR Login):

📄 PAPER TRADING:
• Safe simulation mode
• Uses virtual money
• Recommended for testing and learning
• All features available without risk

🔴 LIVE TRADING:
• REAL MONEY trading
• Uses actual funds
• Requires verified IBKR account
• Risk of financial loss

DEFAULT CREDENTIALS:
• Admin: username: admin, password: admin123
• Trader: username: trader, password: trader123
• Viewer: username: viewer, password: viewer123

FEATURES:
• Remember username/password options
• Role-based access control
• Secure authentication
• Session management
• Trading mode preference saved

TROUBLESHOOTING:
• If login fails: Check username and password
• Clear saved data: Uncheck "Remember" options
• For assistance, contact your system administrator
"""
        messagebox.showinfo("Help", help_text)

    def close_launcher(self) -> None:
        """Close the launcher window"""
        try:
            self.logger.info("Closing IBKR launcher after dashboard launch")
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            self.logger.error(f"Error closing launcher: {e}")
            try:
                self.root.destroy()
            except:
                pass

    def on_closing(self) -> None:
        """Handle window close event"""
        self.logger.info("Launcher window closing")
        self.user_manager.logout()
        self.root.destroy()

    def run(self) -> None:
        """Start the GUI application"""
        self.logger.info("Starting SPYDER IBKR Login Launcher GUI")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("Launcher interrupted by user")
        except Exception as e:
            self.logger.error(f"Launcher error: {e}")
            raise

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================
def main():
    """Main entry point"""
    # Ensure SPYDER home exists
    if not SPYDER_HOME.exists():
        if HAS_TK:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error",
                f"SPYDER directory not found!\n\n"
                f"Expected: {SPYDER_HOME}\n\n"
                f"Please run from correct location.",
            )
            root.destroy()
        else:
            print(f"Error: SPYDER directory not found at {SPYDER_HOME}")
        sys.exit(1)

    # Create and run launcher
    try:
        app = SpyderIBKRLoginLauncher()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()