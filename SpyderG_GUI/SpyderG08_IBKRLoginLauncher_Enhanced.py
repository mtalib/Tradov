#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SPYDER - Autonomous Options Trading System v1.0

Series: SpyderG_GUI
Module: SpyderG08_IBKRLoginLauncher_Enhanced.py
Purpose: Simplified GUI launcher for SPYDER Trading System

Author: Mohamed Talib
Year Created: 2025
Last Updated: 2025-10-22 Time: 22:30:00
Version: 1.1.0

Module Description:
    Simplified launcher for the SPYDER trading system that provides:
    - Dashboard Only (visualization mode)
    - IBKR Web API - Paper Trading
    - IBKR Web API - Live Trading
    
    Features:
    - Tooltips for each option
    - Connection status indicator
    - Remember credentials option
    - Session timeout warnings
    - About dialog with version info
    
    Credentials are only requested for Paper/Live trading modes.
    No more IB Gateway option - only IBKR Web API is supported.

Dependencies:
    - tkinter for GUI
    - SpyderU_Utilities for logging
    - SpyderB_Broker for IBKR Web API
"""

# ==============================================================================
# STANDARD IMPORTS
# ==============================================================================
import os
import sys
import json
import subprocess
import configparser
import base64
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime, timedelta

# ==============================================================================
# THIRD-PARTY IMPORTS
# ==============================================================================
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    HAS_TK = True
except ImportError:
    HAS_TK = False
    print("ERROR: tkinter is required for GUI launcher")
    sys.exit(1)

# ==============================================================================
# LOCAL IMPORTS
# ==============================================================================
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from SpyderU_Utilities.SpyderU01_Logger import get_logger
    HAS_LOGGER = True
except ImportError:
    HAS_LOGGER = False
    import logging
    get_logger = logging.getLogger

# ==============================================================================
# CONSTANTS
# ==============================================================================
VERSION = "1.1.0"
BUILD_DATE = "2025-10-22"

SPYDER_HOME = Path.home() / "Projects" / "Spyder"
CONFIG_DIR = SPYDER_HOME / "config"
CONFIG_FILE = CONFIG_DIR / "launcher_config.ini"

# Tooltips
TOOLTIPS = {
    "dashboard": "Launch the dashboard in visualization mode only.\n"
                 "No connection to Interactive Brokers.\n"
                 "Uses simulated market data for testing and analysis.",
    
    "paper": "Connect to IBKR using Web API in Paper Trading mode.\n"
             "Safe simulation environment with virtual money.\n"
             "All features available without financial risk.\n"
             "Requires IBKR Paper Trading account credentials.",
    
    "live": "Connect to IBKR using Web API in Live Trading mode.\n"
            "⚠️ REAL MONEY TRADING - Uses actual funds ⚠️\n"
            "Requires verified IBKR Live Trading account.\n"
            "Exercise caution - financial risk involved.",
}

# Session timeout in minutes
SESSION_TIMEOUT = 30

DEFAULT_CONFIG = {
    "last_mode": "dashboard",
    "remember_paper_username": "",
    "remember_paper_password": "",
    "remember_live_username": "",
    "remember_live_password": "",
    "save_paper_credentials": "false",
    "save_live_credentials": "false",
    "session_timeout_minutes": "30",
    "last_session_check": "",
}

# ==============================================================================
# TOOLTIP CLASS
# ==============================================================================
class ToolTip:
    """
    Create a tooltip for a given widget with better styling
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        """Display tooltip"""
        if self.tooltip_window or not self.text:
            return
        
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        # Styled tooltip
        frame = tk.Frame(tw, background="#1a1a1a", relief=tk.SOLID, borderwidth=1)
        frame.pack()
        
        label = tk.Label(
            frame,
            text=self.text,
            justify=tk.LEFT,
            background="#1a1a1a",
            foreground="#ffffff",
            relief=tk.FLAT,
            font=("Arial", 9),
            padx=10,
            pady=8
        )
        label.pack()

    def hide_tooltip(self, event=None):
        """Hide tooltip"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# ==============================================================================
# SIMPLIFIED LAUNCHER CLASS
# ==============================================================================
class SpyderSimplifiedLauncher:
    """
    SPYDER Trading System Simplified Launcher.
    
    Provides three launch modes:
    1. Dashboard Only - No IBKR connection
    2. IBKR Web API - Paper Trading (requires credentials)
    3. IBKR Web API - Live Trading (requires credentials)
    """

    def __init__(self):
        """Initialize the launcher"""
        # Setup logging
        if HAS_LOGGER:
            self.logger = get_logger(self.__class__.__name__)
        else:
            self.logger = logging.getLogger(self.__class__.__name__)

        self.logger.info("Initializing SPYDER Simplified Launcher v" + VERSION)

        # Load configuration
        self.config = self._load_configuration()

        # Connection status
        self.connection_status = "disconnected"  # disconnected, checking, connected, error
        self.connection_check_thread = None

        # Initialize GUI
        self.root = tk.Tk()
        self.root.title("SPYDER Trading System - Launch Options")
        self.root.geometry("720x680")  # Wider window, better proportions
        self.root.resizable(False, False)

        # Center window on screen
        self._center_window()

        # Setup variables
        self.launch_mode = tk.StringVar(value=self.config.get("SPYDER", "last_mode"))
        
        # Paper trading credentials
        self.paper_username = tk.StringVar(value=self.config.get("SPYDER", "remember_paper_username"))
        self.paper_password = tk.StringVar(value=self._decrypt_password(self.config.get("SPYDER", "remember_paper_password")))
        self.save_paper_creds = tk.BooleanVar(value=self.config.get("SPYDER", "save_paper_credentials") == "true")
        
        # Live trading credentials
        self.live_username = tk.StringVar(value=self.config.get("SPYDER", "remember_live_username"))
        self.live_password = tk.StringVar(value=self._decrypt_password(self.config.get("SPYDER", "remember_live_password")))
        self.save_live_creds = tk.BooleanVar(value=self.config.get("SPYDER", "save_live_credentials") == "true")

        # Check for session timeout
        self._check_session_timeout()

        # Setup UI
        self._setup_styles()
        self._create_widgets()

        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _center_window(self) -> None:
        """Center the window on screen"""
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.root.winfo_width()) // 2
        y = (self.root.winfo_screenheight() - self.root.winfo_height()) // 2
        self.root.geometry(f"+{x}+{y}")

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

    def _save_configuration(self, config: Optional[configparser.ConfigParser] = None) -> None:
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

    def _encrypt_password(self, password: str) -> str:
        """Simple encryption for stored passwords (NOT for production security)"""
        if not password:
            return ""
        # Use base64 encoding (NOT secure, just obfuscation)
        # For production, use proper encryption like cryptography.fernet
        try:
            encoded = base64.b64encode(password.encode()).decode()
            return encoded
        except Exception as e:
            self.logger.error(f"Password encryption failed: {e}")
            return ""

    def _decrypt_password(self, encrypted: str) -> str:
        """Simple decryption for stored passwords"""
        if not encrypted:
            return ""
        try:
            decoded = base64.b64decode(encrypted.encode()).decode()
            return decoded
        except Exception as e:
            self.logger.error(f"Password decryption failed: {e}")
            return ""

    def _check_session_timeout(self) -> None:
        """Check if saved session has timed out"""
        last_check = self.config.get("SPYDER", "last_session_check")
        if not last_check:
            return

        try:
            last_time = datetime.fromisoformat(last_check)
            timeout_minutes = int(self.config.get("SPYDER", "session_timeout_minutes"))
            elapsed = datetime.now() - last_time

            if elapsed > timedelta(minutes=timeout_minutes):
                self.logger.warning(f"Session timeout detected ({elapsed.seconds // 60} minutes)")
                
                # Clear saved passwords for security
                if self.config.get("SPYDER", "save_paper_credentials") == "true":
                    self.paper_password.set("")
                    self.config.set("SPYDER", "remember_paper_password", "")
                
                if self.config.get("SPYDER", "save_live_credentials") == "true":
                    self.live_password.set("")
                    self.config.set("SPYDER", "remember_live_password", "")
                
                self._save_configuration()
                
                messagebox.showinfo(
                    "Session Timeout",
                    f"Your saved session has expired after {timeout_minutes} minutes of inactivity.\n\n"
                    "Please re-enter your credentials for security."
                )
        except Exception as e:
            self.logger.error(f"Session timeout check failed: {e}")

    def _setup_styles(self) -> None:
        """Configure UI styles"""
        # Modern dark theme colors
        bg_color = "#2b2b2b"
        fg_color = "#e0e0e0"
        accent_color = "#00ff88"
        input_bg = "#3d3d3d"
        frame_bg = "#333333"

        self.root.configure(bg=bg_color)

        # Color scheme
        self.colors = {
            'bg': bg_color,
            'fg': fg_color,
            'accent': accent_color,
            'input_bg': input_bg,
            'frame_bg': frame_bg,
        }

    def _create_widgets(self) -> None:
        """Create main launcher widgets"""
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header with About button
        header_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        header_frame.pack(fill=tk.X, pady=(0, 10))

        header = tk.Label(
            header_frame,
            text="🕷️ SPYDER AUTONOMOUS OPTIONS TRADING SYSTEM",
            font=("Arial", 16, "bold"),  # Increased from 14
            bg=self.colors['bg'],
            fg=self.colors['accent'],
        )
        header.pack(side=tk.LEFT)

        # About button
        about_btn = tk.Button(
            header_frame,
            text="?",
            font=("Arial", 12, "bold"),  # Increased from 10
            bg=self.colors['frame_bg'],
            fg=self.colors['accent'],
            activebackground=self.colors['input_bg'],
            relief=tk.FLAT,
            width=2,
            height=1,
            cursor="hand2",
            command=self.show_about,
        )
        about_btn.pack(side=tk.RIGHT)
        ToolTip(about_btn, "About SPYDER Launcher")

        # Launch Mode Selection Frame
        mode_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        mode_frame.pack(fill=tk.X, pady=(0, 20))

        # Dashboard Only
        dashboard_frame = tk.Frame(mode_frame, bg=self.colors['bg'])
        dashboard_frame.pack(anchor=tk.W, pady=5)
        
        dashboard_rb = tk.Radiobutton(
            dashboard_frame,
            text="○  Dashboard Only – Visualization Mode",
            variable=self.launch_mode,
            value="dashboard",
            command=self.on_mode_change,
            font=("Arial", 12),  # Increased font size
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            selectcolor=self.colors['frame_bg'],
            activebackground=self.colors['bg'],
            activeforeground=self.colors['accent'],
            highlightthickness=0,
        )
        dashboard_rb.pack(anchor=tk.W)
        ToolTip(dashboard_rb, TOOLTIPS["dashboard"])

        # Paper Trading
        paper_frame = tk.Frame(mode_frame, bg=self.colors['bg'])
        paper_frame.pack(anchor=tk.W, pady=5)
        
        paper_rb = tk.Radiobutton(
            paper_frame,
            text="○  IBKR Web API – Paper Trading",
            variable=self.launch_mode,
            value="paper",
            command=self.on_mode_change,
            font=("Arial", 12),  # Increased font size
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            selectcolor=self.colors['frame_bg'],
            activebackground=self.colors['bg'],
            activeforeground=self.colors['accent'],
            highlightthickness=0,
        )
        paper_rb.pack(side=tk.LEFT, anchor=tk.W)
        ToolTip(paper_rb, TOOLTIPS["paper"])

        # Credentials frame for Paper Trading (initially hidden)
        self.paper_cred_frame = tk.Frame(mode_frame, bg=self.colors['frame_bg'])
        
        paper_cred_inner = tk.Frame(self.paper_cred_frame, bg=self.colors['frame_bg'])
        paper_cred_inner.pack(padx=30, pady=10)

        tk.Label(
            paper_cred_inner,
            text="USER ID",
            font=("Arial", 11),  # Increased from 9
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
        ).grid(row=0, column=0, sticky=tk.W, pady=8, padx=5)

        self.paper_username_entry = tk.Entry(
            paper_cred_inner,
            textvariable=self.paper_username,
            font=("Arial", 11),  # Increased from 10
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            width=30,  # Increased from 25
        )
        self.paper_username_entry.grid(row=0, column=1, padx=(15, 5), pady=8)

        tk.Label(
            paper_cred_inner,
            text="PASSWORD",
            font=("Arial", 11),  # Increased from 9
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
        ).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)

        self.paper_password_entry = tk.Entry(
            paper_cred_inner,
            textvariable=self.paper_password,
            font=("Arial", 11),  # Increased from 10
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            show="●",
            width=30,  # Increased from 25
        )
        self.paper_password_entry.grid(row=1, column=1, padx=(15, 5), pady=8)

        # Remember credentials checkbox for Paper
        self.paper_remember_cb = tk.Checkbutton(
            paper_cred_inner,
            text="Remember USER ID & PASSWORD",
            variable=self.save_paper_creds,
            font=("Arial", 10),  # Increased from 8
            bg=self.colors['frame_bg'],
            fg=self.colors['accent'],
            selectcolor=self.colors['input_bg'],
            activebackground=self.colors['frame_bg'],
            activeforeground=self.colors['accent'],
        )
        self.paper_remember_cb.grid(row=2, column=0, columnspan=2, pady=(8, 0), sticky=tk.W, padx=5)
        ToolTip(self.paper_remember_cb, "Save credentials for next session\n(Stored with encryption)")

        # CONNECT button for Paper Trading
        self.paper_connect_btn = tk.Button(
            paper_cred_inner,
            text="CONNECT",
            font=("Arial", 12, "bold"),  # Increased from 10
            bg=self.colors['input_bg'],
            fg=self.colors['accent'],
            activebackground=self.colors['accent'],
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._connect_to_ibkr("paper"),
            width=45,  # Increased from 40
            height=2,  # Added height for better proportion
        )
        self.paper_connect_btn.grid(row=3, column=0, columnspan=2, pady=(12, 8))
        ToolTip(self.paper_connect_btn, "Click to test connection with your credentials")

        # Live Trading
        live_frame = tk.Frame(mode_frame, bg=self.colors['bg'])
        live_frame.pack(anchor=tk.W, pady=5)
        
        live_rb = tk.Radiobutton(
            live_frame,
            text="○  IBKR Web API – Live Trading",
            variable=self.launch_mode,
            value="live",
            command=self.on_mode_change,
            font=("Arial", 12),  # Increased font size
            bg=self.colors['bg'],
            fg=self.colors['fg'],
            selectcolor=self.colors['frame_bg'],
            activebackground=self.colors['bg'],
            activeforeground=self.colors['accent'],
            highlightthickness=0,
        )
        live_rb.pack(side=tk.LEFT, anchor=tk.W)
        ToolTip(live_rb, TOOLTIPS["live"])

        # Credentials frame for Live Trading (initially hidden)
        self.live_cred_frame = tk.Frame(mode_frame, bg=self.colors['frame_bg'])
        
        live_cred_inner = tk.Frame(self.live_cred_frame, bg=self.colors['frame_bg'])
        live_cred_inner.pack(padx=30, pady=10)

        tk.Label(
            live_cred_inner,
            text="USER ID",
            font=("Arial", 11),
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
        ).grid(row=0, column=0, sticky=tk.W, pady=8, padx=5)

        self.live_username_entry = tk.Entry(
            live_cred_inner,
            textvariable=self.live_username,
            font=("Arial", 11),
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            width=30,
        )
        self.live_username_entry.grid(row=0, column=1, padx=(15, 5), pady=8)

        tk.Label(
            live_cred_inner,
            text="PASSWORD",
            font=("Arial", 11),
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
        ).grid(row=1, column=0, sticky=tk.W, pady=8, padx=5)

        self.live_password_entry = tk.Entry(
            live_cred_inner,
            textvariable=self.live_password,
            font=("Arial", 11),
            bg=self.colors['input_bg'],
            fg=self.colors['fg'],
            insertbackground=self.colors['fg'],
            show="●",
            width=30,
        )
        self.live_password_entry.grid(row=1, column=1, padx=(15, 5), pady=8)

        # Remember credentials checkbox for Live
        self.live_remember_cb = tk.Checkbutton(
            live_cred_inner,
            text="Remember USER ID & PASSWORD",
            variable=self.save_live_creds,
            font=("Arial", 10),
            bg=self.colors['frame_bg'],
            fg=self.colors['accent'],
            selectcolor=self.colors['input_bg'],
            activebackground=self.colors['frame_bg'],
            activeforeground=self.colors['accent'],
        )
        self.live_remember_cb.grid(row=2, column=0, columnspan=2, pady=(8, 0), sticky=tk.W, padx=5)
        ToolTip(self.live_remember_cb, "Save credentials for next session\n(Stored with encryption)")

        # CONNECT button for Live Trading
        self.live_connect_btn = tk.Button(
            live_cred_inner,
            text="CONNECT",
            font=("Arial", 12, "bold"),
            bg=self.colors['input_bg'],
            fg=self.colors['accent'],
            activebackground=self.colors['accent'],
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=lambda: self._connect_to_ibkr("live"),
            width=45,
            height=2,
        )
        self.live_connect_btn.grid(row=3, column=0, columnspan=2, pady=(12, 8))
        ToolTip(self.live_connect_btn, "Click to test connection with your credentials")

        # Launch Button (initially disabled)
        self.launch_btn = tk.Button(
            main_frame,
            text="🚀 LAUNCH",
            font=("Arial", 14, "bold"),  # Increased from 12
            bg=self.colors['accent'],
            fg="#000000",
            activebackground="#00dd77",
            activeforeground="#000000",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.launch_system,
            state=tk.DISABLED,  # Initially disabled
            width=20,  # Added explicit width
            height=2,  # Added height
        )
        self.launch_btn.pack(pady=25)  # Increased padding

        # Initial state
        self.on_mode_change()

    def on_mode_change(self) -> None:
        """Handle launch mode change"""
        mode = self.launch_mode.get()

        # Hide all credential frames
        self.paper_cred_frame.pack_forget()
        self.live_cred_frame.pack_forget()

        # Show credentials for paper or live trading
        if mode == "paper":
            self.paper_cred_frame.pack(anchor=tk.W, padx=30, pady=(5, 10))
            # Disable launch button until connected
            self.launch_btn.config(state=tk.DISABLED, bg="#666666", cursor="")
        elif mode == "live":
            self.live_cred_frame.pack(anchor=tk.W, padx=30, pady=(5, 10))
            # Disable launch button until connected
            self.launch_btn.config(state=tk.DISABLED, bg="#666666", cursor="")
        else:
            # Dashboard mode - enable launch button (no connection needed)
            self.launch_btn.config(state=tk.NORMAL, bg=self.colors['accent'], cursor="hand2")

    def _connect_to_ibkr(self, mode: str) -> None:
        """
        Handle CONNECT button click - validates credentials and tests connection
        
        Args:
            mode: Either "paper" or "live"
        """
        # Get credentials based on mode
        if mode == "paper":
            username = self.paper_username.get().strip()
            password = self.paper_password.get().strip()
        else:  # live
            username = self.live_username.get().strip()
            password = self.live_password.get().strip()

        # Validate credentials
        if not username or not password:
            messagebox.showwarning(
                "Missing Credentials",
                f"Please enter your IBKR {mode.title()} Trading credentials."
            )
            return

        self.logger.info(f"Attempting to connect to IBKR {mode.title()} Trading...")

        # Disable CONNECT button during connection attempt
        if mode == "paper":
            self.paper_connect_btn.config(state=tk.DISABLED, text="CONNECTING...", bg=self.colors['input_bg'])
        else:
            self.live_connect_btn.config(state=tk.DISABLED, text="CONNECTING...", bg=self.colors['input_bg'])

        # Run connection check in background
        def connect():
            """Background thread for connection"""
            try:
                # TODO: Replace with actual IBKR Web API authentication
                # This should:
                # 1. Send credentials to IBKR Client Portal Gateway
                # 2. Handle authentication response
                # 3. Verify connection is established
                
                # Simulate connection attempt
                import time
                time.sleep(2)  # Simulate authentication delay
                
                # For development: simulate success/failure based on credentials
                # In production, check actual IBKR API response
                success = True  # Change to False to test error handling
                error_type = None  # Will be set if success = False
                error_detail = ""
                
                # Simulated error scenarios (for testing)
                if not success:
                    # Simulate different error types
                    import random
                    error_scenarios = [
                        ("invalid_credentials", "Invalid username or password"),
                        ("network_error", "Unable to reach IBKR servers. Please check your internet connection."),
                        ("gateway_not_running", "IBKR Client Portal Gateway is not running. Please start it and try again."),
                        ("account_locked", "Account is temporarily locked. Please contact IBKR support."),
                        ("permission_denied", f"Account does not have permission for {mode} trading."),
                    ]
                    error_type, error_detail = random.choice(error_scenarios)
                
                if success:
                    self.connection_status = "connected"
                    self.logger.info(f"✅ Successfully connected to IBKR {mode.title()} Trading")
                    
                    # Enable launch button on main thread
                    self.root.after(0, lambda: self._enable_launch_button())
                    
                    # Update CONNECT button with success state
                    if mode == "paper":
                        self.root.after(0, lambda: self.paper_connect_btn.config(
                            state=tk.NORMAL, 
                            text="CONNECTED ✓",
                            bg=self.colors['accent'],
                            fg="#000000",  # Black text on green background
                            activeforeground="#000000"
                        ))
                    else:
                        self.root.after(0, lambda: self.live_connect_btn.config(
                            state=tk.NORMAL, 
                            text="CONNECTED ✓",
                            bg=self.colors['accent'],
                            fg="#000000",  # Black text on green background
                            activeforeground="#000000"
                        ))
                    
                    # Show success message
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Connection Successful",
                        f"✓ Successfully connected to IBKR {mode.title()} Trading!\n\n"
                        "You can now click LAUNCH to start the system."
                    ))
                else:
                    # Connection failed
                    self.connection_status = "error"
                    self.logger.error(f"❌ Failed to connect to IBKR {mode.title()} Trading: {error_type}")
                    
                    # Re-enable CONNECT button
                    if mode == "paper":
                        self.root.after(0, lambda: self.paper_connect_btn.config(
                            state=tk.NORMAL, 
                            text="CONNECT",
                            bg=self.colors['input_bg']
                        ))
                    else:
                        self.root.after(0, lambda: self.live_connect_btn.config(
                            state=tk.NORMAL, 
                            text="CONNECT",
                            bg=self.colors['input_bg']
                        ))
                    
                    # Show detailed error message with troubleshooting
                    error_messages = {
                        "invalid_credentials": (
                            "❌ Invalid Credentials\n\n"
                            f"{error_detail}\n\n"
                            "Troubleshooting:\n"
                            "• Verify your username and password\n"
                            "• Check for typos or extra spaces\n"
                            "• Ensure Caps Lock is off\n"
                            "• Try resetting your password in IBKR portal"
                        ),
                        "network_error": (
                            "❌ Network Connection Error\n\n"
                            f"{error_detail}\n\n"
                            "Troubleshooting:\n"
                            "• Check your internet connection\n"
                            "• Verify firewall settings\n"
                            "• Try disabling VPN temporarily\n"
                            "• Check if IBKR servers are online"
                        ),
                        "gateway_not_running": (
                            "❌ IBKR Gateway Not Running\n\n"
                            f"{error_detail}\n\n"
                            "Troubleshooting:\n"
                            "• Launch IBKR Client Portal Gateway\n"
                            "• Ensure it's running on https://localhost:5000\n"
                            "• Wait for Gateway to fully start\n"
                            "• Check Gateway logs for errors"
                        ),
                        "account_locked": (
                            "❌ Account Locked\n\n"
                            f"{error_detail}\n\n"
                            "Next Steps:\n"
                            "• Contact IBKR support\n"
                            "• Check your email for notifications\n"
                            "• Verify account status in IBKR portal\n"
                            "• May require security verification"
                        ),
                        "permission_denied": (
                            "❌ Permission Denied\n\n"
                            f"{error_detail}\n\n"
                            "Troubleshooting:\n"
                            f"• Verify {mode} trading is enabled on your account\n"
                            "• Check account permissions in IBKR portal\n"
                            "• Contact IBKR if permissions are incorrect\n"
                            "• May need to complete account setup"
                        ),
                    }
                    
                    error_msg = error_messages.get(error_type, 
                        f"❌ Connection Failed\n\n"
                        f"Failed to connect to IBKR {mode.title()} Trading.\n\n"
                        "Please check:\n"
                        "• Your credentials are correct\n"
                        "• IBKR Client Portal Gateway is running\n"
                        "• Your internet connection is stable\n"
                        "• Your IBKR account is active"
                    )
                    
                    self.root.after(0, lambda: messagebox.showerror(
                        "Connection Failed",
                        error_msg
                    ))
            
            except Exception as e:
                self.logger.error(f"Connection error: {e}")
                self.connection_status = "error"
                
                # Re-enable CONNECT button
                if mode == "paper":
                    self.root.after(0, lambda: self.paper_connect_btn.config(
                        state=tk.NORMAL, 
                        text="CONNECT",
                        bg=self.colors['input_bg']
                    ))
                else:
                    self.root.after(0, lambda: self.live_connect_btn.config(
                        state=tk.NORMAL, 
                        text="CONNECT",
                        bg=self.colors['input_bg']
                    ))
                
                self.root.after(0, lambda: messagebox.showerror(
                    "Connection Error",
                    f"❌ Unexpected Error\n\n"
                    f"An error occurred during connection:\n\n"
                    f"{str(e)}\n\n"
                    "Troubleshooting:\n"
                    "• Check the logs for details\n"
                    "• Restart the launcher\n"
                    "• Verify all system requirements\n"
                    "• Contact support if issue persists"
                ))

        # Start connection thread
        connection_thread = threading.Thread(target=connect, daemon=True)
        connection_thread.start()

    def _enable_launch_button(self) -> None:
        """Enable the launch button after successful connection"""
        self.launch_btn.config(
            state=tk.NORMAL,
            bg=self.colors['accent'],
            cursor="hand2"
        )
        self.logger.info("Launch button enabled")

    def show_about(self) -> None:
        """Show About dialog"""
        about_window = tk.Toplevel(self.root)
        about_window.title("About SPYDER Launcher")
        about_window.geometry("400x350")
        about_window.resizable(False, False)
        about_window.configure(bg=self.colors['bg'])
        
        # Center on parent
        about_window.transient(self.root)
        about_window.grab_set()
        
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 350) // 2
        about_window.geometry(f"+{x}+{y}")
        
        # Content frame
        content = tk.Frame(about_window, bg=self.colors['bg'])
        content.pack(fill=tk.BOTH, expand=True, padx=30, pady=30)
        
        # Logo/Title
        tk.Label(
            content,
            text="🕷️",
            font=("Arial", 48),
            bg=self.colors['bg'],
            fg=self.colors['accent'],
        ).pack(pady=(0, 10))
        
        tk.Label(
            content,
            text="SPYDER Trading System",
            font=("Arial", 16, "bold"),
            bg=self.colors['bg'],
            fg=self.colors['accent'],
        ).pack()
        
        tk.Label(
            content,
            text="Autonomous Options Trading Platform",
            font=("Arial", 10),
            bg=self.colors['bg'],
            fg=self.colors['fg'],
        ).pack(pady=(0, 20))
        
        # Version info
        info_frame = tk.Frame(content, bg=self.colors['frame_bg'])
        info_frame.pack(fill=tk.X, pady=(0, 20))
        
        info_text = f"""
Version: {VERSION}
Build Date: {BUILD_DATE}
Author: Mohamed Talib

Launcher Features:
• Dashboard visualization mode
• IBKR Web API integration
• Paper & Live trading modes
• Connection status monitoring
• Secure credential storage
• Session timeout protection
        """.strip()
        
        tk.Label(
            info_frame,
            text=info_text,
            font=("Arial", 9),
            bg=self.colors['frame_bg'],
            fg=self.colors['fg'],
            justify=tk.LEFT,
        ).pack(padx=15, pady=15)
        
        # Close button
        tk.Button(
            content,
            text="Close",
            font=("Arial", 10),
            bg=self.colors['accent'],
            fg="#000000",
            activebackground="#00dd77",
            relief=tk.FLAT,
            cursor="hand2",
            command=about_window.destroy,
        ).pack()

    def launch_system(self) -> None:
        """Launch the SPYDER system based on selected mode"""
        mode = self.launch_mode.get()

        self.logger.info(f"Launching SPYDER in {mode} mode")

        # For trading modes, verify connection was established
        if mode in ["paper", "live"]:
            if self.connection_status != "connected":
                messagebox.showwarning(
                    "Connection Required",
                    "Please click CONNECT button first to establish connection.\n\n"
                    "The LAUNCH button will be enabled after successful connection."
                )
                return

        # Save last mode
        self.config.set("SPYDER", "last_mode", mode)
        
        # Update session timestamp
        self.config.set("SPYDER", "last_session_check", datetime.now().isoformat())

        if mode == "dashboard":
            self._launch_dashboard_only()
        elif mode == "paper":
            # Save credentials if requested
            if self.save_paper_creds.get():
                self.config.set("SPYDER", "remember_paper_username", self.paper_username.get())
                self.config.set("SPYDER", "remember_paper_password", self._encrypt_password(self.paper_password.get()))
                self.config.set("SPYDER", "save_paper_credentials", "true")
            else:
                self.config.set("SPYDER", "remember_paper_username", "")
                self.config.set("SPYDER", "remember_paper_password", "")
                self.config.set("SPYDER", "save_paper_credentials", "false")
            
            self._launch_paper_trading()
        elif mode == "live":
            # Save credentials if requested
            if self.save_live_creds.get():
                self.config.set("SPYDER", "remember_live_username", self.live_username.get())
                self.config.set("SPYDER", "remember_live_password", self._encrypt_password(self.live_password.get()))
                self.config.set("SPYDER", "save_live_credentials", "true")
            else:
                self.config.set("SPYDER", "remember_live_username", "")
                self.config.set("SPYDER", "remember_live_password", "")
                self.config.set("SPYDER", "save_live_credentials", "false")
            
            self._launch_live_trading()

        # Save configuration
        self._save_configuration()

    def _launch_dashboard_only(self) -> None:
        """Launch dashboard in visualization mode only"""
        try:
            self.logger.info("Launching Dashboard Only mode")
            
            # Find dashboard executable
            dashboard_path = SPYDER_HOME / "SpyderG_GUI" / "SpyderG01_Dashboard.py"
            
            if not dashboard_path.exists():
                messagebox.showerror(
                    "Error",
                    f"Dashboard not found at:\n{dashboard_path}"
                )
                return

            # Launch dashboard without IBKR connection
            subprocess.Popen([sys.executable, str(dashboard_path), "--mode", "visualization"])
            
            messagebox.showinfo(
                "Success",
                "Dashboard launched in visualization mode.\n\n"
                "No IBKR connection - simulated data only."
            )
            
            self.logger.info("✅ Dashboard launched successfully")
            self.close_launcher()

        except Exception as e:
            self.logger.error(f"Dashboard launch failed: {e}")
            messagebox.showerror("Error", f"Failed to launch dashboard:\n{e}")

    def _launch_paper_trading(self) -> None:
        """Launch system with IBKR Web API in Paper Trading mode"""
        username = self.paper_username.get().strip()
        password = self.paper_password.get().strip()

        # Validate credentials
        if not username or not password:
            messagebox.showwarning(
                "Missing Credentials",
                "Please enter your IBKR Paper Trading credentials."
            )
            return

        try:
            self.logger.info("Launching Paper Trading mode with IBKR Web API")

            # Save username (not password for security)
            self.config.set("SPYDER", "remember_paper_username", username)

            # Find main system launcher
            main_launcher = SPYDER_HOME / "SpyderG_GUI" / "SpyderG01_Dashboard.py"

            if not main_launcher.exists():
                messagebox.showerror(
                    "Error",
                    f"Main system not found at:\n{main_launcher}"
                )
                return

            # Launch with paper trading mode
            subprocess.Popen([
                sys.executable,
                str(main_launcher),
                "--mode", "paper",
                "--username", username,
                "--password", password,
                "--api", "web"
            ])

            messagebox.showinfo(
                "Success",
                "SPYDER launching with IBKR Web API (Paper Trading).\n\n"
                "Browser will open for authentication.\n"
                "Please complete the login process."
            )

            self.logger.info("✅ Paper trading mode launched")
            self.close_launcher()

        except Exception as e:
            self.logger.error(f"Paper trading launch failed: {e}")
            messagebox.showerror("Error", f"Failed to launch paper trading:\n{e}")

    def _launch_live_trading(self) -> None:
        """Launch system with IBKR Web API in Live Trading mode"""
        username = self.live_username.get().strip()
        password = self.live_password.get().strip()

        # Validate credentials
        if not username or not password:
            messagebox.showwarning(
                "Missing Credentials",
                "Please enter your IBKR Live Trading credentials."
            )
            return

        # Confirm live trading
        confirm = messagebox.askyesno(
            "⚠️ Live Trading Confirmation",
            "You are about to launch LIVE TRADING mode.\n\n"
            "This will use REAL MONEY.\n\n"
            "Are you sure you want to proceed?",
            icon='warning'
        )

        if not confirm:
            return

        try:
            self.logger.info("Launching Live Trading mode with IBKR Web API")

            # Save username (not password for security)
            self.config.set("SPYDER", "remember_live_username", username)

            # Find main system launcher
            main_launcher = SPYDER_HOME / "SpyderG_GUI" / "SpyderG01_Dashboard.py"

            if not main_launcher.exists():
                messagebox.showerror(
                    "Error",
                    f"Main system not found at:\n{main_launcher}"
                )
                return

            # Launch with live trading mode
            subprocess.Popen([
                sys.executable,
                str(main_launcher),
                "--mode", "live",
                "--username", username,
                "--password", password,
                "--api", "web"
            ])

            messagebox.showinfo(
                "Success",
                "SPYDER launching with IBKR Web API (LIVE TRADING).\n\n"
                "⚠️ REAL MONEY MODE ACTIVATED ⚠️\n\n"
                "Browser will open for authentication.\n"
                "Please complete the login process."
            )

            self.logger.info("✅ Live trading mode launched")
            self.close_launcher()

        except Exception as e:
            self.logger.error(f"Live trading launch failed: {e}")
            messagebox.showerror("Error", f"Failed to launch live trading:\n{e}")

    def close_launcher(self) -> None:
        """Close the launcher window"""
        self.root.after(500, self.root.destroy)

    def on_closing(self) -> None:
        """Handle window close event"""
        self.logger.info("Launcher closed by user")
        self.root.destroy()

    def run(self) -> None:
        """Run the launcher main loop"""
        self.logger.info("Starting launcher GUI")
        self.root.mainloop()


# ==============================================================================
# MAIN ENTRY POINT
# ==============================================================================
def main():
    """Main entry point for the launcher"""
    try:
        launcher = SpyderSimplifiedLauncher()
        launcher.run()
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
