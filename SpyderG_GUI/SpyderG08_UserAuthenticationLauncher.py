#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_UserAuthenticationLauncher.py
Purpose: Enhanced GUI launcher with user authentication for SPYDER Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-22 Time: 15:45:00

Module Description:
    User authentication launcher for the SPYDER trading system. Provides
    secure login functionality with role-based access control including:
    - User authentication with username/password
    - Role-based dashboard access (Admin, Trader, Viewer)
    - Remember login functionality
    - Secure credential storage
    - User management interface
    - Session persistence

Module Constants:
    SESSION_TIMEOUT (int): Default session timeout in minutes (30)
    MAX_LOGIN_ATTEMPTS (int): Maximum failed login attempts (3)
    PASSWORD_MIN_LENGTH (int): Minimum password length (8)

Dependencies:
    - PySide6/tkinter for GUI
    - hashlib/crypt for password hashing
    - SpyderU_Utilities for logging
    - json for user data storage

Change Log:
    2025-10-22 (v1.0.0):
        - Initial release with user authentication
        - Repurposed from IB Gateway launcher
        - Added role-based access control
        - Implemented secure credential storage
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
# Security Constants
SESSION_TIMEOUT = 30  # minutes
MAX_LOGIN_ATTEMPTS = 3
PASSWORD_MIN_LENGTH = 8

# Paths
SPYDER_HOME = Path.home() / "Projects" / "Spyder"
CONFIG_DIR = SPYDER_HOME / "config"
USERS_FILE = CONFIG_DIR / "users.json"
CONFIG_FILE = CONFIG_DIR / "auth_launcher_config.ini"
LOG_DIR = Path.home() / "spyder_logs"
LOCK_FILE = Path("/tmp/spyder_auth_launcher.lock")  # Singleton lock file

# Default Configuration
DEFAULT_CONFIG = {
    "last_username": "",
    "remember_login": "false",
    "auto_launch_dashboard": "true",
    "session_timeout": str(SESSION_TIMEOUT),
    "default_role": "trader",
}

# Default Users (in production, these should be properly set up)
DEFAULT_USERS = {
    "admin": {
        "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
        "role": "admin",
        "full_name": "System Administrator",
        "last_login": None,
        "login_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now().isoformat()
    },
    "trader": {
        "password_hash": hashlib.sha256("trader123".encode()).hexdigest(),
        "role": "trader",
        "full_name": "Default Trader",
        "last_login": None,
        "login_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now().isoformat()
    },
    "viewer": {
        "password_hash": hashlib.sha256("viewer123".encode()).hexdigest(),
        "role": "viewer",
        "full_name": "Read-only User",
        "last_login": None,
        "login_attempts": 0,
        "locked_until": None,
        "created_at": datetime.now().isoformat()
    }
}


# ==============================================================================
# ENUMS
# ==============================================================================
class UserRole(Enum):
    """User role enumeration"""

    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"


class SessionStatus(Enum):
    """Session status enumeration"""

    ACTIVE = "active"
    EXPIRED = "expired"
    TERMINATED = "terminated"


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
            self.lock_fd = open(self.lock_file, "w")

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
            ["wmctrl", "-a", "SPYDER Authentication"],
            capture_output=True,
            timeout=2,
        )
    except Exception:
        # wmctrl not available or failed, that's okay
        pass


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

        # Check if account is locked
        if user.get("locked_until"):
            lock_time = datetime.fromisoformat(user["locked_until"])
            if datetime.now() < lock_time:
                remaining = (lock_time - datetime.now()).seconds // 60
                return False, f"Account locked. Try again in {remaining} minutes"
            else:
                # Lock expired, reset attempts
                user["login_attempts"] = 0
                user["locked_until"] = None
                self._save_users(self.users)

        # Check password
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash != user.get("password_hash"):
            # Increment failed attempts
            user["login_attempts"] = user.get("login_attempts", 0) + 1

            if user["login_attempts"] >= MAX_LOGIN_ATTEMPTS:
                # Lock account
                lock_time = datetime.now() + timedelta(minutes=30)
                user["locked_until"] = lock_time.isoformat()
                self._save_users(self.users)
                return False, "Too many failed attempts. Account locked for 30 minutes."

            self._save_users(self.users)
            remaining = MAX_LOGIN_ATTEMPTS - user["login_attempts"]
            return False, f"Invalid password. {remaining} attempts remaining."

        # Successful login
        user["login_attempts"] = 0
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

    def is_session_valid(self) -> bool:
        """Check if current session is still valid"""
        if not self.current_user or not self.session_start:
            return False

        session_age = (datetime.now() - self.session_start).total_seconds() / 60
        return session_age < SESSION_TIMEOUT

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

    def create_user(self, username: str, password: str, full_name: str, role: str) -> Tuple[bool, str]:
        """
        Create a new user

        Args:
            username: Username
            password: Plain text password
            full_name: User's full name
            role: User role (admin, trader, viewer)

        Returns:
            Tuple of (success, message)
        """
        if username in self.users:
            return False, "Username already exists"

        if len(password) < PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {PASSWORD_MIN_LENGTH} characters"

        if role not in [r.value for r in UserRole]:
            return False, "Invalid role"

        # Create user
        user = {
            "password_hash": hashlib.sha256(password.encode()).hexdigest(),
            "role": role,
            "full_name": full_name,
            "last_login": None,
            "login_attempts": 0,
            "locked_until": None,
            "created_at": datetime.now().isoformat()
        }

        self.users[username] = user
        self._save_users(self.users)

        return True, "User created successfully"

    def list_users(self) -> List[Dict]:
        """Get list of all users (for admin)"""
        users_list = []
        for username, data in self.users.items():
            users_list.append({
                "username": username,
                "full_name": data.get("full_name", ""),
                "role": data.get("role", ""),
                "last_login": data.get("last_login", ""),
                "created_at": data.get("created_at", "")
            })
        return users_list


# ==============================================================================
# MAIN LAUNCHER CLASS
# ==============================================================================
class SpyderAuthLauncher:
    """
    SPYDER Trading System Authentication Launcher.

    Provides secure login interface with role-based access control.
    """

    def __init__(self):
        """Initialize the launcher"""
        # Setup logging
        if HAS_LOGGER:
            self.logger = get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info("Initializing SPYDER Authentication Launcher")

        # Acquire singleton lock
        self.singleton_lock = SingletonLock(LOCK_FILE)

        # Initialize components
        self.user_manager = UserManager()
        self.config = self._load_configuration()

        # Initialize GUI
        if not HAS_TK:
            raise RuntimeError("tkinter is required for GUI launcher")

        self.root = tk.Tk()

        # Set WM_CLASS for proper window grouping
        try:
            self.root.wm_class("SPYDER", "SPYDER")
        except (AttributeError, TypeError):
            # wm_class not available in this tkinter version
            pass

        self.progress_window = None

        # Setup variables
        self.username = tk.StringVar(value=self.config.get("SPYDER", "last_username"))
        self.password = tk.StringVar()
        self.remember_login = tk.BooleanVar(
            value=self.config.get("SPYDER", "remember_login") == "true"
        )

        # Setup UI
        self._setup_window()
        self._setup_styles()
        self._create_login_widgets()

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

    def _save_configuration(
        self, config: Optional[configparser.ConfigParser] = None
    ) -> None:
        """
        Save launcher configuration to file.

        Args:
            config: ConfigParser to save (uses self.config if None)
        """
        if config is None:
            config = self.config

        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                config.write(f)
            self.logger.info(f"Configuration saved to {CONFIG_FILE}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")

    def _setup_window(self) -> None:
        """Configure main window properties"""
        self.root.title("🕷️ SPYDER Trading System - Login")
        self.root.geometry("500x600")
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
        self.style.configure(
            "TButton",
            background=button_bg,
            foreground=fg_color,
            borderwidth=1,
            focuscolor=accent_color,
        )
        self.style.configure("TEntry", fieldbackground=button_bg, foreground=fg_color)
        self.style.configure("TRadiobutton", background=bg_color, foreground=fg_color)
        self.style.configure(
            "Status.TLabel", background=bg_color, foreground=fg_color, font=("Arial", 9)
        )

    def _create_login_widgets(self) -> None:
        """Create login screen widgets"""
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
            text="Authentication Portal",
            font=("Arial", 10),
            bg="#2d2d2d",
            fg="#888888",
        )
        subheader.pack(pady=(0, 30))

        # Login Frame
        login_frame = tk.LabelFrame(
            main_frame,
            text="User Login",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        login_frame.pack(fill=tk.X, pady=(0, 20))

        # Username
        tk.Label(
            login_frame,
            text="Username:",
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Arial", 9, "bold"),
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        username_entry = ttk.Entry(login_frame, textvariable=self.username, width=30)
        username_entry.pack(padx=10, pady=(0, 10), fill=tk.X)

        # Password
        tk.Label(
            login_frame,
            text="Password:",
            bg="#2d2d2d",
            fg="#ffffff",
            font=("Arial", 9, "bold"),
        ).pack(anchor=tk.W, padx=10, pady=(5, 5))

        password_entry = ttk.Entry(login_frame, textvariable=self.password, show="*", width=30)
        password_entry.pack(padx=10, pady=(0, 10), fill=tk.X)
        password_entry.bind('<Return>', lambda event: self.login())

        # Remember login
        remember_check = ttk.Checkbutton(
            login_frame,
            text="Remember username",
            variable=self.remember_login,
            command=self.on_remember_change,
        )
        remember_check.pack(anchor=tk.W, padx=10, pady=(0, 10))

        # Login button
        self.login_btn = ttk.Button(
            login_frame,
            text="🔐 Login",
            command=self.login,
        )
        self.login_btn.pack(pady=10)

        # User Management Frame (for admin)
        if self.user_manager.get_user_role() == "admin":
            admin_frame = tk.LabelFrame(
                main_frame,
                text="Admin Options",
                bg="#2d2d2d",
                fg="#ffaa00",
                font=("Arial", 10, "bold"),
            )
            admin_frame.pack(fill=tk.X, pady=(0, 20))

            self.user_mgmt_btn = ttk.Button(
                admin_frame,
                text="👥 User Management",
                command=self.show_user_management,
            )
            self.user_mgmt_btn.pack(pady=10)

        # System Status
        status_frame = tk.LabelFrame(
            main_frame,
            text="System Status",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        status_frame.pack(fill=tk.X, pady=(0, 20))

        # Status details
        self.status_label = ttk.Label(
            status_frame, text="✅ Authentication System: Ready", style="Status.TLabel"
        )
        self.status_label.pack(padx=10, pady=2)

        self.users_label = ttk.Label(
            status_frame, text=f"👥 Users: {len(self.user_manager.users)} registered", style="Status.TLabel"
        )
        self.users_label.pack(padx=10, pady=2)

        self.session_label = ttk.Label(
            status_frame, text="🔐 Session: Not authenticated", style="Status.TLabel"
        )
        self.session_label.pack(padx=10, pady=2)

        # Help button
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

    def _create_main_widgets(self) -> None:
        """Create main dashboard widgets after successful login"""
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()

        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header with user info
        header_frame = tk.Frame(main_frame, bg="#2d2d2d")
        header_frame.pack(fill=tk.X, pady=(0, 20))

        header = tk.Label(
            header_frame,
            text="🕷️ SPYDER TRADING SYSTEM",
            font=("Arial", 18, "bold"),
            bg="#2d2d2d",
            fg="#00ff88",
        )
        header.pack(side=tk.LEFT)

        user_info = tk.Label(
            header_frame,
            text=f"Welcome, {self.user_manager.get_user_full_name()} ({self.user_manager.get_user_role()})",
            font=("Arial", 10),
            bg="#2d2d2d",
            fg="#ffffff",
        )
        user_info.pack(side=tk.RIGHT)

        # Launch Options Frame
        options_frame = tk.LabelFrame(
            main_frame,
            text="Launch Options",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Buttons
        button_frame = tk.Frame(options_frame, bg="#2d2d2d")
        button_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Dashboard button
        dashboard_btn = ttk.Button(
            button_frame,
            text="📊 Launch Dashboard",
            command=self.launch_dashboard,
        )
        dashboard_btn.pack(fill=tk.X, pady=5)

        # Role-specific options
        if self.user_manager.get_user_role() in ["admin", "trader"]:
            trading_btn = ttk.Button(
                button_frame,
                text="💹 Trading Interface",
                command=self.launch_trading_interface,
            )
            trading_btn.pack(fill=tk.X, pady=5)

        if self.user_manager.get_user_role() == "admin":
            admin_btn = ttk.Button(
                button_frame,
                text="⚙️ System Administration",
                command=self.launch_admin_interface,
            )
            admin_btn.pack(fill=tk.X, pady=5)

            user_mgmt_btn = ttk.Button(
                button_frame,
                text="👥 User Management",
                command=self.show_user_management,
            )
            user_mgmt_btn.pack(fill=tk.X, pady=5)

        # Logout button
        logout_btn = ttk.Button(
            button_frame,
            text="🚪 Logout",
            command=self.logout,
        )
        logout_btn.pack(fill=tk.X, pady=(20, 5))

        # Footer
        footer = tk.Label(
            main_frame,
            text="Professional Algorithmic Trading Platform",
            font=("Arial", 8),
            bg="#2d2d2d",
            fg="#888888",
        )
        footer.pack(pady=(10, 0))

    def on_remember_change(self) -> None:
        """Handle remember login checkbox change"""
        self.config["SPYDER"]["remember_login"] = "true" if self.remember_login.get() else "false"
        self._save_configuration()

    def login(self) -> None:
        """Process user login"""
        username = self.username.get().strip()
        password = self.password.get()

        if not username or not password:
            messagebox.showerror("Login Error", "Please enter both username and password")
            return

        # Authenticate user
        success, message = self.user_manager.authenticate_user(username, password)

        if success:
            # Save configuration
            if self.remember_login.get():
                self.config["SPYDER"]["last_username"] = username
            else:
                self.config["SPYDER"]["last_username"] = ""
            self._save_configuration()

            # Show success message
            messagebox.showinfo("Login Successful", f"Welcome, {self.user_manager.get_user_full_name()}!")

            # Clear password field
            self.password.set("")

            # Update status before switching
            self.status_label.configure(text="✅ Authentication System: Active")
            self.session_label.configure(text=f"🔐 Session: {self.user_manager.get_user_role()} user")

            # Switch to main interface
            self._create_main_widgets()

            # Auto-launch dashboard if enabled
            if self.config.get("SPYDER", "auto_launch_dashboard") == "true":
                self.root.after(1000, self.launch_dashboard)
        else:
            # Show error message
            messagebox.showerror("Login Failed", message)

            # Clear password field
            self.password.set("")

    def logout(self) -> None:
        """Process user logout"""
        self.user_manager.logout()
        self.username.set(self.config.get("SPYDER", "last_username"))
        self.password.set("")

        # Return to login screen
        for widget in self.root.winfo_children():
            widget.destroy()
        self._create_login_widgets()

        # Reset status
        self.status_label.configure(text="✅ Authentication System: Ready")
        self.session_label.configure(text="🔐 Session: Not authenticated")

    def launch_dashboard(self) -> None:
        """Launch SPYDER Dashboard"""
        self.logger.info("Launching SPYDER Dashboard")

        # Check session validity
        if not self.user_manager.is_session_valid():
            messagebox.showwarning("Session Expired", "Your session has expired. Please login again.")
            self.logout()
            return

        # Try to launch dashboard
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

                    # Pass user info via environment
                    env = os.environ.copy()
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
                    messagebox.showinfo("Success", "SPYDER Dashboard launched successfully!")
                    return

            messagebox.showerror("Error", "Dashboard executable not found")
        except Exception as e:
            self.logger.error(f"Dashboard launch failed: {e}")
            messagebox.showerror("Error", f"Failed to launch dashboard: {e}")

    def launch_trading_interface(self) -> None:
        """Launch trading interface (for traders)"""
        messagebox.showinfo("Trading Interface", "Trading interface would be launched here")

    def launch_admin_interface(self) -> None:
        """Launch admin interface (for administrators)"""
        messagebox.showinfo("Admin Interface", "Admin interface would be launched here")

    def show_user_management(self) -> None:
        """Show user management dialog (for administrators)"""
        if self.user_manager.get_user_role() != "admin":
            messagebox.showerror("Access Denied", "You need administrator privileges to access user management")
            return

        # Create user management window
        mgmt_window = tk.Toplevel(self.root)
        mgmt_window.title("User Management")
        mgmt_window.geometry("800x600")
        mgmt_window.transient(self.root)
        mgmt_window.grab_set()

        # Center on parent
        mgmt_window.update_idletasks()
        x = (
            self.root.winfo_x()
            + (self.root.winfo_width() - mgmt_window.winfo_width()) // 2
        )
        y = (
            self.root.winfo_y()
            + (self.root.winfo_height() - mgmt_window.winfo_height()) // 2
        )
        mgmt_window.geometry(f"+{x}+{y}")

        # Create user list
        frame = ttk.Frame(mgmt_window, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = tk.Label(
            frame,
            text="User Management",
            font=("Arial", 14, "bold"),
            bg="#2d2d2d",
            fg="#00ff88",
        )
        header.pack(pady=(0, 10))

        # Users list
        users_frame = tk.LabelFrame(
            frame,
            text="Existing Users",
            bg="#2d2d2d",
            fg="#00ff88",
            font=("Arial", 10, "bold"),
        )
        users_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview for users
        columns = ("Username", "Full Name", "Role", "Last Login")
        tree = ttk.Treeview(users_frame, columns=columns, show="headings", height=10)

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=150)

        # Add users to tree
        for user in self.user_manager.list_users():
            tree.insert("", tk.END, values=(
                user["username"],
                user["full_name"],
                user["role"],
                user["last_login"] or "Never"
            ))

        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Close button
        close_btn = ttk.Button(
            frame,
            text="Close",
            command=mgmt_window.destroy,
        )
        close_btn.pack(pady=10)

    def show_help(self) -> None:
        """Show help dialog"""
        help_text = """🕷️ SPYDER Authentication Help

DEFAULT USERS:
• Admin: username: admin, password: admin123
• Trader: username: trader, password: trader123
• Viewer: username: viewer, password: viewer123

USER ROLES:
• Admin: Full system access and user management
• Trader: Trading access and dashboard features
• Viewer: Read-only access to dashboards

SECURITY FEATURES:
• Account lockout after 3 failed attempts
• Session timeout after 30 minutes
• Secure password hashing
• Remember username option

TROUBLESHOOTING:
• If locked out: Wait 30 minutes or contact admin
• Clear saved username: Uncheck "Remember username"
• Session expired: Simply login again

For assistance, contact your system administrator.
"""
        messagebox.showinfo("Help", help_text)

    def on_closing(self) -> None:
        """Handle window close event"""
        self.logger.info("Launcher window closing")
        self.user_manager.logout()
        self.singleton_lock.release()
        self.root.destroy()

    def run(self) -> None:
        """Start the GUI application"""
        self.logger.info("Starting authentication launcher GUI")
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
        print("⚠️  SPYDER Authentication Launcher is already running!")

        # Try to bring existing window to front
        bring_existing_window_to_front()

        # Show dialog if tkinter available
        if HAS_TK:
            root = tk.Tk()
            root.withdraw()  # Hide root window
            messagebox.showwarning(
                "Already Running",
                "SPYDER Authentication Launcher is already running!\n\n"
                "Only one instance can run at a time.\n\n"
                "The existing launcher window has been brought to the front.",
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
                f"Please run from correct location.",
            )
            root.destroy()
        else:
            print(f"Error: SPYDER directory not found at {SPYDER_HOME}")
        sys.exit(1)

    # Create and run launcher
    try:
        app = SpyderAuthLauncher()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()